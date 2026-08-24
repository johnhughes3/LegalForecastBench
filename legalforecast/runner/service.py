"""Outcome-blinded public release execution with durable spend control."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.live_model_solver import (
    LiveModelTransport,
    SolverResponse,
    complete_live_prompt,
    default_live_model_transport,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry_bytes,
    model_registry_entry_sha256,
)
from legalforecast.evals.output_parser import ParsedModelOutput, parse_model_output
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderCapExceededError,
    ProviderSpendControlError,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.immutable_io import read_single_link_file, write_file_create_only
from legalforecast.release import ForecastPredictionUnit, load_forecast_execution

from .ledger import (
    RunBlockedError,
    RunIdentityError,
    RunnerLedger,
    RunValidationError,
)


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Exact identity and paths for one local public release run."""

    forecast_path: Path
    artifact_root: Path
    model_registry_path: Path
    model_key: str
    ledger_path: Path
    receipts_dir: Path
    ceiling_microusd: int
    approval_reference: str
    harness: str = "native"
    ablation: str = "none"
    repeat_count: int = 1
    account: str = "default"


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Public-safe completion summary for one invocation."""

    run_identity_sha256: str
    completed_cells: int
    executed_cells: int
    resumed_cells: int
    status: str

    def to_record(self) -> dict[str, object]:
        return asdict(self)


class _RequestBodyCommitment:
    def __init__(self) -> None:
        self.request_body_sha256: str | None = None

    def observe(self, request_body: bytes) -> None:
        digest = str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                request_body,
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
        if self.request_body_sha256 is not None:
            raise RunBlockedError(
                "one logical cell attempted duplicate provider transport"
            )
        self.request_body_sha256 = digest


def execute_release_run(
    config: RunConfig,
    *,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> RunSummary:
    """Execute or resume every exact cell in a validated forecast release."""

    approval_reference = _non_empty(
        config.approval_reference,
        "approval reference",
    )
    harness = _non_empty(config.harness, "harness")
    ablation = _non_empty(config.ablation, "ablation")
    account = _non_empty(config.account, "account")
    _positive_int(config.ceiling_microusd, "ceiling_microusd")
    _positive_int(config.repeat_count, "repeat_count")
    provider, model_id = _model_key(config.model_key)

    execution = load_forecast_execution(
        config.forecast_path,
        artifact_root=config.artifact_root,
    )
    registry_bytes = read_single_link_file(
        config.model_registry_path,
        label="model registry",
    )
    registry_sha256 = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            registry_bytes,
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    registry = load_model_registry_bytes(registry_bytes)
    try:
        entry = registry.get(provider, model_id)
    except KeyError as exc:
        raise RunValidationError(
            f"model key is absent from registry: {config.model_key}"
        ) from exc
    entry_sha256 = model_registry_entry_sha256(entry)

    identity = {
        "schema_version": str(PUBLIC_RUN_IDENTITY_V1),
        "ablation": ablation,
        "account": account,
        "approval_reference": approval_reference,
        "ceiling_microusd": config.ceiling_microusd,
        "forecast_release_digest": execution.release.release_digest,
        "harness": harness,
        "model_key": entry.registry_key,
        "model_registry_entry_sha256": entry_sha256,
        "model_registry_sha256": registry_sha256,
        "repeat_count": config.repeat_count,
    }
    identity_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(identity)
    identity_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            identity,
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    config.receipts_dir.mkdir(parents=True, exist_ok=True)

    reservation_microusd = conservative_reservation_microusd(
        context_limit=entry.context_limit,
        max_output_tokens=entry.max_output_tokens,
        input_token_price=entry.input_token_price,
        output_token_price=entry.output_token_price,
        long_context_surcharge=entry.long_context_surcharge,
    )
    authority_identity_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "account": account,
                "provider": entry.provider,
                "run_identity_sha256": identity_sha256,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    policy = FrozenAttemptPolicy(
        reservation_ledger_sha256=identity_sha256,
        max_billable_attempts=1,
        failure_threshold=1,
        failure_window_seconds=86_400,
    )
    delegate = transport or default_live_model_transport
    executed_cells = 0
    resumed_cells = 0

    with RunnerLedger(config.ledger_path) as ledger:
        ledger.ensure_run(
            identity_sha256=identity_sha256,
            identity_json=identity_bytes.decode("utf-8"),
            release_digest=execution.release.release_digest,
            harness=harness,
            model_key=entry.registry_key,
            ceiling_microusd=config.ceiling_microusd,
            approval_reference=approval_reference,
        )
        with SqliteProviderSpendAuthority(
            config.ledger_path,
            authority_identity_sha256=authority_identity_sha256,
            cycle_id=execution.release.release_id,
            provider=entry.provider,
            account=account,
            cap_microusd=config.ceiling_microusd,
            policy=policy,
        ) as authority:
            for unit in execution.release.prediction_units:
                for repeat_index in range(1, config.repeat_count + 1):
                    _require_unchanged_registry(
                        config.model_registry_path,
                        registry_sha256,
                    )
                    prompt_bytes = execution.prompt_bytes(unit.unit_id)
                    try:
                        prompt = prompt_bytes.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise RunValidationError(
                            f"prompt is not UTF-8 for unit {unit.unit_id}"
                        ) from exc
                    cell_id = _cell_id(
                        identity_sha256=identity_sha256,
                        unit=unit,
                        repeat_index=repeat_index,
                    )
                    cell = ledger.reserve_cell(
                        cell_id=cell_id,
                        run_identity_sha256=identity_sha256,
                        case_id=unit.case_id,
                        unit_id=unit.unit_id,
                        repeat_index=repeat_index,
                    )
                    receipt_path = config.receipts_dir / f"{cell_id}.json"
                    if cell.status == "completed":
                        _restore_or_validate_completed_receipt(
                            receipt_path,
                            expected_sha256=cell.receipt_sha256,
                            expected_payload=cell.receipt_payload,
                            cell_id=cell_id,
                            run_identity_sha256=identity_sha256,
                        )
                        resumed_cells += 1
                        continue

                    capture = _RequestBodyCommitment()
                    completed = False
                    try:
                        response = _complete_cell(
                            entry,
                            prompt,
                            registry_sha256=registry_sha256,
                            transport=delegate,
                            request_body_observer=capture.observe,
                            environ=environ,
                            authority=authority,
                            reservation_microusd=reservation_microusd,
                            release_id=execution.release.release_id,
                            account=account,
                            harness=harness,
                            ablation=ablation,
                            unit=unit,
                            repeat_index=repeat_index,
                        )
                        request_sha256 = capture.request_body_sha256
                        if request_sha256 is None:
                            raise RunValidationError(
                                "provider response lacks a request-body commitment"
                            )
                        parsed = parse_model_output(
                            response.raw_output,
                            required_unit_ids=(unit.unit_id,),
                        )
                        metadata = response.metadata or {}
                        served_model = metadata.get("served_model_version")
                        if not isinstance(served_model, str) or not served_model:
                            raise RunValidationError(
                                "validated provider response lacks served model"
                            )
                        receipt = {
                            "schema_version": str(PUBLIC_RUN_RECEIPT_V1),
                            "cell_id": cell_id,
                            "run_identity_sha256": identity_sha256,
                            "forecast_release_digest": execution.release.release_digest,
                            "release_id": execution.release.release_id,
                            "case_id": unit.case_id,
                            "unit_id": unit.unit_id,
                            "harness": harness,
                            "model_key": entry.registry_key,
                            "model_registry_sha256": registry_sha256,
                            "model_registry_entry_sha256": entry_sha256,
                            "ablation": ablation,
                            "repeat_index": repeat_index,
                            "prompt_sha256": unit.prompt_sha256,
                            "request_body_sha256": request_sha256,
                            "served_model_version": served_model,
                            "usage": {
                                "input_tokens": response.input_tokens,
                                "output_tokens": response.output_tokens,
                                "actual_cost_microusd": math.ceil(
                                    response.estimated_cost * 1_000_000
                                ),
                            },
                            "parser_output": _public_parser_record(parsed),
                        }
                        receipt_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(receipt)
                        receipt_sha256 = str(
                            RAW_BYTES_RAW_SHA256_V1.commit(
                                receipt_bytes,
                                domain=PUBLIC_RUN_RECEIPT_V1,
                            ).digest
                        )
                        ledger.mark_completed(
                            cell_id,
                            request_body_sha256=request_sha256,
                            receipt_sha256=receipt_sha256,
                            receipt_payload=receipt_bytes,
                        )
                        completed = True
                        _restore_or_validate_completed_receipt(
                            receipt_path,
                            expected_sha256=receipt_sha256,
                            expected_payload=receipt_bytes,
                            cell_id=cell_id,
                            run_identity_sha256=identity_sha256,
                        )
                    except BaseException as exc:
                        if not completed:
                            _record_cell_failure(
                                ledger,
                                cell_id,
                                exc=exc,
                                transport_started=capture.request_body_sha256
                                is not None,
                            )
                        if isinstance(exc, ProviderSpendControlError) and (
                            capture.request_body_sha256 is None
                        ):
                            message = (
                                "provider ceiling or spend authority blocked transport"
                            )
                            if isinstance(exc, ProviderCapExceededError):
                                message = (
                                    "provider reservation would exceed run ceiling"
                                )
                            raise RunBlockedError(message) from exc
                        raise
                    executed_cells += 1
        ledger.mark_run_completed()

    completed_cells = executed_cells + resumed_cells
    return RunSummary(
        run_identity_sha256=identity_sha256,
        completed_cells=completed_cells,
        executed_cells=executed_cells,
        resumed_cells=resumed_cells,
        status="completed",
    )


def _complete_cell(
    entry: ModelRegistryEntry,
    prompt: str,
    *,
    registry_sha256: str,
    transport: LiveModelTransport,
    request_body_observer: Callable[[bytes], None],
    environ: Mapping[str, str] | None,
    authority: SqliteProviderSpendAuthority,
    reservation_microusd: int,
    release_id: str,
    account: str,
    harness: str,
    ablation: str,
    unit: ForecastPredictionUnit,
    repeat_index: int,
) -> SolverResponse:
    key = ProviderSpendKey(
        cycle_id=release_id,
        provider=entry.provider,
        account=account,
        stage=harness,
        model_key=entry.registry_key,
        case_id=f"{unit.case_id}:{unit.unit_id}",
        ablation=ablation,
        repeat_index=repeat_index,
    )
    handler = ProviderSpendAttemptHandler(
        authority=authority,
        key=key,
        reservation_microusd=reservation_microusd,
    )
    return complete_live_prompt(
        entry,
        prompt,
        model_registry_sha256=registry_sha256,
        transport=transport,
        environ=environ,
        max_attempts=1,
        attempt_handler=handler,
        request_body_observer=request_body_observer,
    )


def _record_cell_failure(
    ledger: RunnerLedger,
    cell_id: str,
    *,
    exc: BaseException,
    transport_started: bool,
) -> None:
    failure_type = type(exc).__name__
    if transport_started:
        ledger.mark_ambiguous(cell_id, failure_type=failure_type)
    else:
        ledger.mark_blocked(cell_id, failure_type=failure_type)


def _public_parser_record(parsed: ParsedModelOutput) -> dict[str, object]:
    """Project parsed output to score inputs without retaining model prose."""

    return {
        "status": parsed.status.value,
        "is_valid": parsed.is_valid,
        "invalid_output": parsed.invalid_output,
        "raw_output_sha256": parsed.raw_output_sha256,
        "required_unit_ids": list(parsed.required_unit_ids),
        "predictions": [
            {
                "unit_id": prediction.unit_id,
                "probability_fully_dismissed": (prediction.probability_fully_dismissed),
                "defaulted": prediction.defaulted,
                "invalid_reason": (
                    prediction.invalid_reason.value
                    if prediction.invalid_reason is not None
                    else None
                ),
            }
            for prediction in parsed.predictions
        ],
        "defaulted_unit_ids": list(parsed.defaulted_unit_ids),
        "issues": [
            {
                "code": issue.code.value,
                "unit_id": issue.unit_id,
            }
            for issue in parsed.issues
        ],
    }


def _restore_or_validate_completed_receipt(
    path: Path,
    *,
    expected_sha256: str | None,
    expected_payload: bytes | None,
    cell_id: str,
    run_identity_sha256: str,
) -> None:
    if expected_sha256 is None or expected_payload is None:
        raise RunValidationError("completed cell lacks durable receipt evidence")
    if not path.exists():
        write_file_create_only(path, expected_payload)
    payload = read_single_link_file(path, label="completed run receipt")
    if payload != expected_payload:
        raise RunValidationError("completed run receipt bytes changed")
    actual_sha256 = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload,
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    if actual_sha256 != expected_sha256:
        raise RunValidationError("completed run receipt digest changed")
    try:
        decoded: object = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RunValidationError("completed run receipt is invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise RunValidationError("completed run receipt must be an object")
    record = cast(Mapping[str, object], decoded)
    if ARTIFACT_CANONICAL_JSON_V1.encode(record) != payload:
        raise RunValidationError("completed run receipt is not canonical")
    if (
        record.get("schema_version") != str(PUBLIC_RUN_RECEIPT_V1)
        or record.get("cell_id") != cell_id
        or record.get("run_identity_sha256") != run_identity_sha256
    ):
        raise RunValidationError("completed run receipt identity changed")


def _cell_id(
    *,
    identity_sha256: str,
    unit: ForecastPredictionUnit,
    repeat_index: int,
) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "case_id": unit.case_id,
                "repeat_index": repeat_index,
                "run_identity_sha256": identity_sha256,
                "unit_id": unit.unit_id,
            },
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )


def _require_unchanged_registry(path: Path, expected_sha256: str) -> None:
    actual_sha256 = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            read_single_link_file(path, label="model registry"),
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    if actual_sha256 != expected_sha256:
        raise RunIdentityError("model registry bytes changed during execution")


def _model_key(value: str) -> tuple[str, str]:
    normalized = _non_empty(value, "model_key")
    provider, separator, model_id = normalized.partition(":")
    if not separator or not provider.strip() or not model_id.strip():
        raise RunValidationError("model_key must be provider:model_id")
    return provider.strip().lower(), model_id.strip()


def _non_empty(value: str, label: str) -> str:
    if not value.strip():
        raise RunValidationError(f"{label} is required")
    return value.strip()


def _positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise RunValidationError(f"{label} must be a positive integer")
    return value

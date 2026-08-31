"""Outcome-blinded public release execution with durable spend control."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import asdict, dataclass
from datetime import date
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
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
    require_official_registry_entries,
)
from legalforecast.evals.output_parser import parse_model_output, public_parser_record
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    FrozenAttemptPolicy,
    ProviderCapExceededError,
    ProviderSpendAuthority,
    ProviderSpendControlError,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.evals.provider_spend_dynamodb import DynamoDbProviderSpendAuthority
from legalforecast.evals.response_verification import (
    require_publishable_response_metadata,
)
from legalforecast.immutable_io import read_single_link_file, write_file_create_only
from legalforecast.release import (
    ForecastExecution,
    ForecastPredictionUnit,
    load_forecast_execution,
    load_forecast_run_inputs,
)

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
    approval_reference: str | None = None
    harness: str = "native"
    ablation: str = "none"
    repeat_count: int = 1
    account: str = "default"
    manifest_path: Path | None = None
    unit_id: str | None = None
    repeat_index: int | None = None
    cell_id: str | None = None
    provider_authority_table: str | None = None
    provider_authority_region: str | None = None
    provider_authority_resource_identity_sha256: str | None = None


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
    def __init__(
        self,
        *,
        request_body_sha256: str | None = None,
        observer: Callable[[str], None] | None = None,
    ) -> None:
        self.request_body_sha256 = request_body_sha256
        self._observer = observer
        self._replacement_allowed = False
        self._last_failure_was_nonbillable = False

    def observe(self, request_body: bytes) -> None:
        digest = str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                request_body,
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
        if self.request_body_sha256 is not None and not self._replacement_allowed:
            raise RunBlockedError(
                "one logical cell attempted duplicate provider transport"
            )
        if self._observer is not None:
            self._observer(digest)
        self.request_body_sha256 = digest
        self._replacement_allowed = False
        self._last_failure_was_nonbillable = False

    def observe_failure(self, ambiguous: bool) -> None:
        """Permit a replacement body only after durable nonbillable evidence."""

        self._last_failure_was_nonbillable = not ambiguous
        self._replacement_allowed = not ambiguous

    def transport_is_ambiguous(self) -> bool:
        return (
            self.request_body_sha256 is not None
            and not self._last_failure_was_nonbillable
        )


def execute_release_run(
    config: RunConfig,
    *,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> RunSummary:
    """Execute or resume every exact cell in a validated forecast release."""

    manifest_mode = config.manifest_path is not None
    approval_reference = (
        ""
        if manifest_mode
        else _non_empty(
            config.approval_reference or "",
            "approval reference",
        )
    )
    harness = _non_empty(config.harness, "harness")
    if harness != "native":
        raise RunValidationError(
            "forecast-release.v1 currently supports only the native harness"
        )
    ablation = _non_empty(config.ablation, "ablation")
    if ablation != "none":
        raise RunValidationError(
            "forecast-release.v1 contains authenticated release prompts only; "
            "non-default ablations require a separately authenticated release"
        )
    account = _non_empty(config.account, "account")
    _positive_int(config.ceiling_microusd, "ceiling_microusd")
    _positive_int(config.repeat_count, "repeat_count")
    provider, model_id = _model_key(config.model_key)

    run_inputs = (
        load_forecast_run_inputs(
            config.manifest_path,
            config.forecast_path,
            artifact_root=config.artifact_root,
        )
        if config.manifest_path is not None
        else None
    )
    execution = (
        run_inputs.execution
        if run_inputs is not None
        else load_forecast_execution(
            config.forecast_path,
            artifact_root=config.artifact_root,
        )
    )
    registry_bytes = read_single_link_file(
        config.model_registry_path,
        label="model registry",
    )
    registry_sha256 = model_registry_sha256(registry_bytes)
    registry = load_model_registry_bytes(registry_bytes)
    try:
        entry = registry.get(provider, model_id)
    except KeyError as exc:
        raise RunValidationError(
            f"model key is absent from registry: {config.model_key}"
        ) from exc
    try:
        official_entries = require_official_registry_entries((entry,))
    except ValueError as exc:
        raise RunValidationError(f"official model eligibility failed: {exc}") from exc
    _require_model_release_anchor(
        execution,
        release_anchor=earliest_eligible_decision_date(official_entries),
    )
    entry_sha256 = model_registry_entry_sha256(entry)

    identity = _run_identity_record(
        execution=execution,
        entry=entry,
        registry_sha256=registry_sha256,
        ceiling_microusd=config.ceiling_microusd,
        harness=harness,
        ablation=ablation,
        repeat_count=config.repeat_count,
        account=account,
        manifest_id=(None if run_inputs is None else str(run_inputs.manifest.run_id)),
        manifest_sha256=(None if run_inputs is None else run_inputs.manifest_sha256),
        approval_reference=(None if manifest_mode else approval_reference),
    )
    identity_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(identity)
    identity_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            identity,
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    config.receipts_dir.mkdir(parents=True, exist_ok=True)

    units = tuple(execution.release.prediction_units)
    selected_units = _select_units(units, unit_id=config.unit_id)
    repeat_indices = _select_repeats(
        repeat_count=config.repeat_count,
        repeat_index=config.repeat_index,
    )
    if (
        config.cell_id is not None
        and config.unit_id is None
        and config.repeat_index is None
    ):
        selected_cell = _select_cell(
            units,
            repeat_count=config.repeat_count,
            identity_sha256=identity_sha256,
            cell_id=config.cell_id,
        )
        selected_units = (selected_cell[0],)
        repeat_indices = (selected_cell[1],)
    selected_cells = {
        _cell_id(
            identity_sha256=identity_sha256,
            unit=unit,
            repeat_index=repeat_index,
        )
        for unit in selected_units
        for repeat_index in repeat_indices
    }
    if config.cell_id is not None:
        if len(selected_cells) != 1 or config.cell_id not in selected_cells:
            raise RunValidationError(
                "cell_id must identify the selected manifest unit and repeat"
            )

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

    if any(
        value is not None
        for value in (
            config.provider_authority_table,
            config.provider_authority_region,
            config.provider_authority_resource_identity_sha256,
        )
    ) and not all(
        value is not None
        for value in (
            config.provider_authority_table,
            config.provider_authority_region,
            config.provider_authority_resource_identity_sha256,
        )
    ):
        raise RunValidationError(
            "provider authority table, region, and resource identity must be "
            "supplied together"
        )

    with RunnerLedger(
        config.ledger_path,
        state_only_provider_attempts=config.provider_authority_table is not None,
    ) as ledger:
        ledger.ensure_run(
            identity_sha256=identity_sha256,
            identity_json=identity_bytes.decode("utf-8"),
            release_digest=execution.release.release_digest,
            harness=harness,
            model_key=entry.registry_key,
            ceiling_microusd=config.ceiling_microusd,
            approval_reference=approval_reference,
        )
        authority_context: AbstractContextManager[ProviderSpendAuthority]
        if config.provider_authority_table is not None:
            remote_authority = DynamoDbProviderSpendAuthority(
                table_name=config.provider_authority_table,
                authority_identity_sha256=authority_identity_sha256,
                resource_identity_sha256=config.provider_authority_resource_identity_sha256,
                cycle_id=execution.release.release_id,
                provider=entry.provider,
                account=account,
                cap_microusd=config.ceiling_microusd,
                policy=policy,
                region=cast(str, config.provider_authority_region),
            )
            authority_context = nullcontext(remote_authority)
        else:
            authority_context = SqliteProviderSpendAuthority(
                config.ledger_path,
                authority_identity_sha256=authority_identity_sha256,
                cycle_id=execution.release.release_id,
                provider=entry.provider,
                account=account,
                cap_microusd=config.ceiling_microusd,
                policy=policy,
            )
        with authority_context as authority:
            for unit in selected_units:
                for repeat_index in repeat_indices:
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
                    if config.cell_id is not None and cell_id != config.cell_id:
                        raise RunValidationError(
                            "cell_id does not match the selected manifest cell"
                        )
                    key = ProviderSpendKey(
                        cycle_id=execution.release.release_id,
                        provider=entry.provider,
                        account=account,
                        stage=harness,
                        model_key=entry.registry_key,
                        case_id=cell_id,
                        ablation=ablation,
                        repeat_index=repeat_index,
                    )
                    cell = ledger.inspect_cell(
                        cell_id=cell_id,
                        run_identity_sha256=identity_sha256,
                        case_id=unit.case_id,
                        unit_id=unit.unit_id,
                        repeat_index=repeat_index,
                        allow_retryable_nonbillable=True,
                        allow_pretransport_reuse=True,
                    )
                    receipt_path = config.receipts_dir / f"{cell_id}.json"
                    if cell is not None and cell.status == "completed":
                        _restore_or_validate_completed_receipt(
                            receipt_path,
                            expected_sha256=cell.receipt_sha256,
                            expected_payload=cell.receipt_payload,
                            cell_id=cell_id,
                            run_identity_sha256=identity_sha256,
                        )
                        resumed_cells += 1
                        continue

                    retryable_nonbillable_prior_attempt: AttemptLease | None = None
                    pretransport_attempt_ordinal: int | None = None
                    if (
                        cell is not None
                        and cell.status == "reserved"
                        and cell.response_payload is None
                    ):
                        if cell.provider_attempt_id is None:
                            raise RunBlockedError(
                                f"cell {cell_id} lacks its prior provider attempt"
                            )
                        if (
                            cell.provider_attempt_status == "reserved"
                            and cell.request_body_sha256 is None
                            and cell.provider_attempt_ordinal is not None
                        ):
                            pretransport_attempt_ordinal = cell.provider_attempt_ordinal
                        else:
                            if not isinstance(
                                authority,
                                SqliteProviderSpendAuthority,
                            ):
                                raise RunBlockedError(
                                    "remote provider failure lacks retryable "
                                    "replacement support"
                                )
                            retryable_nonbillable_prior_attempt = (
                                authority.recover_retryable_nonbillable_attempt(
                                    key,
                                    attempt_id=cell.provider_attempt_id,
                                )
                            )

                    replayable_response: Mapping[str, object] | None = None
                    replayable_attempt: AttemptLease | None = None
                    if (
                        cell is not None
                        and cell.response_payload is not None
                        and cell.provider_attempt_ordinal is not None
                    ):
                        replayable_response = _replayable_response(
                            cell.response_payload
                        )
                        replayable_attempt = authority.adopt_attempt(
                            key,
                            attempt_ordinal=cell.provider_attempt_ordinal,
                        )
                        if replayable_attempt.attempt_id != cell.provider_attempt_id:
                            raise RunBlockedError(
                                "replayable provider attempt differs from cell binding"
                            )

                    authorization_state: list[str | None] = [
                        None
                        if replayable_attempt is None
                        else replayable_attempt.attempt_id
                    ]

                    def persist_request_body(
                        request_body_sha256: str,
                        *,
                        bound_cell_id: str = cell_id,
                        bound_authorization_state: list[str | None] = (
                            authorization_state
                        ),
                    ) -> None:
                        authorized_attempt_id = bound_authorization_state[0]
                        if authorized_attempt_id is None:
                            raise RunBlockedError(
                                "request commitment lacks provider authorization"
                            )
                        ledger.record_request_body(
                            bound_cell_id,
                            provider_attempt_id=authorized_attempt_id,
                            request_body_sha256=request_body_sha256,
                        )

                    capture = _RequestBodyCommitment(
                        request_body_sha256=(
                            None if cell is None else cell.request_body_sha256
                        )
                        if replayable_response is not None
                        else None,
                        observer=persist_request_body,
                    )
                    completed = False

                    def reserve_authorized_cell(
                        connection: sqlite3.Connection,
                        lease: AttemptLease,
                        *,
                        bound_cell_id: str = cell_id,
                        bound_case_id: str = unit.case_id,
                        bound_unit_id: str = unit.unit_id,
                        bound_repeat_index: int = repeat_index,
                        bound_authorization_state: list[str | None] = (
                            authorization_state
                        ),
                    ) -> None:
                        ledger.reserve_cell_in_transaction(
                            connection,
                            cell_id=bound_cell_id,
                            run_identity_sha256=identity_sha256,
                            case_id=bound_case_id,
                            unit_id=bound_unit_id,
                            repeat_index=bound_repeat_index,
                            provider_attempt_id=lease.attempt_id,
                            allow_nonbillable_replacement=(lease.attempt_ordinal == 2),
                        )
                        bound_authorization_state[0] = lease.attempt_id

                    def bind_pretransport_attempt(
                        lease: AttemptLease,
                        *,
                        bound_cell_attempt_id: str | None = (
                            None if cell is None else cell.provider_attempt_id
                        ),
                        bound_authorization_state: list[str | None] = (
                            authorization_state
                        ),
                    ) -> None:
                        if lease.attempt_id != bound_cell_attempt_id:
                            raise RunBlockedError(
                                "pretransport provider attempt differs from "
                                "cell binding"
                            )
                        bound_authorization_state[0] = lease.attempt_id

                    def persist_remote_authorized_cell(
                        lease: AttemptLease,
                        *,
                        bound_cell_id: str = cell_id,
                        bound_case_id: str = unit.case_id,
                        bound_unit_id: str = unit.unit_id,
                        bound_repeat_index: int = repeat_index,
                        bound_authorization_state: list[str | None] = (
                            authorization_state
                        ),
                    ) -> None:
                        ledger.reserve_cell(
                            cell_id=bound_cell_id,
                            run_identity_sha256=identity_sha256,
                            case_id=bound_case_id,
                            unit_id=bound_unit_id,
                            repeat_index=bound_repeat_index,
                            provider_attempt_id=lease.attempt_id,
                        )
                        bound_authorization_state[0] = lease.attempt_id

                    def persist_provider_response(
                        lease: AttemptLease,
                        response: Mapping[str, object],
                        *,
                        bound_cell_id: str = cell_id,
                    ) -> None:
                        response_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(response)
                        ledger.record_response_payload(
                            bound_cell_id,
                            provider_attempt_id=lease.attempt_id,
                            response_payload=response_bytes,
                            response_payload_sha256=hashlib.sha256(
                                response_bytes
                            ).hexdigest(),
                        )

                    try:
                        response = _complete_cell(
                            entry,
                            prompt,
                            key=key,
                            registry_sha256=registry_sha256,
                            transport=delegate,
                            request_body_observer=capture.observe,
                            attempt_failure_observer=capture.observe_failure,
                            environ=environ,
                            authority=authority,
                            reservation_microusd=reservation_microusd,
                            before_authorize=(
                                None
                                if isinstance(authority, DynamoDbProviderSpendAuthority)
                                else reserve_authorized_cell
                            ),
                            after_authorize=(
                                persist_remote_authorized_cell
                                if isinstance(authority, DynamoDbProviderSpendAuthority)
                                else None
                            ),
                            retryable_nonbillable_prior_attempt=(
                                retryable_nonbillable_prior_attempt
                            ),
                            replayable_attempt=replayable_attempt,
                            replayable_response=replayable_response,
                            pretransport_attempt_ordinal=(pretransport_attempt_ordinal),
                            pretransport_attempt_observer=bind_pretransport_attempt,
                            response_observer=persist_provider_response,
                        )
                        request_sha256 = capture.request_body_sha256
                        if request_sha256 is None:
                            raise RunValidationError(
                                "provider response lacks a request-body commitment"
                            )
                        metadata = response.metadata or {}
                        try:
                            require_publishable_response_metadata(metadata)
                        except ValueError as exc:
                            raise RunValidationError(str(exc)) from exc
                        parsed = parse_model_output(
                            response.raw_output,
                            required_unit_ids=(unit.unit_id,),
                        )
                        receipt = {
                            "schema_version": str(PUBLIC_RUN_RECEIPT_V1),
                            "cell_id": cell_id,
                            "run_identity_sha256": identity_sha256,
                            "forecast_release_digest": execution.release.release_digest,
                            "release_id": execution.release.release_id,
                            "case_id": unit.case_id,
                            "unit_id": unit.unit_id,
                            "required_unit_ids": [unit.unit_id],
                            "harness": harness,
                            "model_key": entry.registry_key,
                            "model_id": entry.registry_key,
                            "model_registry_sha256": registry_sha256,
                            "model_registry_entry_sha256": entry_sha256,
                            "ablation": ablation,
                            "repeat_index": repeat_index,
                            "prompt_sha256": unit.prompt_sha256,
                            "request_body_sha256": request_sha256,
                            "served_model_version": entry.model_version_or_snapshot,
                            "usage": {
                                "input_tokens": response.input_tokens,
                                "output_tokens": response.output_tokens,
                                "estimated_cost_microusd": math.ceil(
                                    response.estimated_cost * 1_000_000
                                ),
                            },
                            "parser_output": public_parser_record(parsed),
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
                        authorized_attempt_id = authorization_state[0]
                        if not completed and authorized_attempt_id is not None:
                            _record_cell_failure(
                                ledger,
                                cell_id,
                                provider_attempt_id=authorized_attempt_id,
                                exc=exc,
                                transport_started=capture.transport_is_ambiguous(),
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
                    if replayable_response is None:
                        executed_cells += 1
                    else:
                        resumed_cells += 1
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
    key: ProviderSpendKey,
    registry_sha256: str,
    transport: LiveModelTransport,
    request_body_observer: Callable[[bytes], None],
    attempt_failure_observer: Callable[[bool], None],
    environ: Mapping[str, str] | None,
    authority: ProviderSpendAuthority,
    reservation_microusd: int,
    before_authorize: Callable[[sqlite3.Connection, AttemptLease], None] | None,
    after_authorize: Callable[[AttemptLease], None] | None,
    retryable_nonbillable_prior_attempt: AttemptLease | None,
    replayable_attempt: AttemptLease | None,
    replayable_response: Mapping[str, object] | None,
    pretransport_attempt_ordinal: int | None,
    pretransport_attempt_observer: Callable[[AttemptLease], None],
    response_observer: Callable[[AttemptLease, Mapping[str, object]], None],
) -> SolverResponse:
    handler = ProviderSpendAttemptHandler(
        authority=authority,
        key=key,
        reservation_microusd=reservation_microusd,
        before_authorize=before_authorize,
        after_authorize=after_authorize,
        failure_observer=attempt_failure_observer,
        allow_retryable_nonbillable_replacement=True,
        retryable_nonbillable_prior_attempt=retryable_nonbillable_prior_attempt,
        replayable_attempt=replayable_attempt,
        replayable_response=replayable_response,
        pretransport_attempt_ordinal=pretransport_attempt_ordinal,
        pretransport_attempt_observer=pretransport_attempt_observer,
        response_observer=response_observer,
    )
    return complete_live_prompt(
        entry,
        prompt,
        model_registry_sha256=registry_sha256,
        transport=transport,
        environ=environ,
        max_attempts=(
            1
            if retryable_nonbillable_prior_attempt is not None
            or (
                pretransport_attempt_ordinal is not None
                and pretransport_attempt_ordinal == 2
            )
            else 2
        ),
        attempt_handler=handler,
        request_body_observer=request_body_observer,
    )


def _require_model_release_anchor(
    execution: ForecastExecution,
    *,
    release_anchor: date,
) -> None:
    """Require the runner packet profile to clear the model release anchor.

    ``forecast-release.v1`` deliberately authenticates packet bytes without
    defining their internal schema.  This new runner therefore validates its
    narrower executable profile here; generic v1 validation remains unchanged.
    """

    decision_dates: dict[str, date] = {}
    for unit in execution.release.prediction_units:
        try:
            payload: object = json.loads(execution.packet_bytes(unit.unit_id))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunValidationError(
                f"runner packet is not valid JSON for unit {unit.unit_id}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise RunValidationError(
                f"runner packet must be an object for unit {unit.unit_id}"
            )
        packet = cast(Mapping[str, object], payload)
        packet_case_id = packet.get("case_id")
        if packet_case_id != unit.case_id:
            raise RunValidationError(
                f"runner packet case_id differs for unit {unit.unit_id}"
            )
        raw_decision_date = packet.get("decision_date")
        if not isinstance(raw_decision_date, str) or not raw_decision_date:
            raise RunValidationError(
                f"runner packet decision_date is required for case {unit.case_id}"
            )
        try:
            decision_date = date.fromisoformat(raw_decision_date)
        except ValueError as exc:
            raise RunValidationError(
                "runner packet decision_date must be an ISO date for case "
                f"{unit.case_id}"
            ) from exc
        if decision_date.isoformat() != raw_decision_date:
            raise RunValidationError(
                f"runner packet decision_date is not canonical for case {unit.case_id}"
            )
        prior_date = decision_dates.setdefault(unit.case_id, decision_date)
        if prior_date != decision_date:
            raise RunValidationError(
                f"authenticated runner packets disagree on decision_date for case "
                f"{unit.case_id}"
            )
        if decision_date < release_anchor:
            raise RunValidationError(
                f"case {unit.case_id} decision_date {decision_date.isoformat()} "
                f"precedes model release anchor {release_anchor.isoformat()}"
            )

    release_case_ids = {case.case_id for case in execution.release.cases}
    missing_case_dates = sorted(release_case_ids - decision_dates.keys())
    if missing_case_dates:
        raise RunValidationError(
            "forecast release cases lack an authenticated runner-packet "
            "decision_date: "
            f"{missing_case_dates}"
        )


def _replayable_response(payload: bytes) -> Mapping[str, object]:
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunValidationError("durable provider response is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise RunValidationError("durable provider response must be an object")
    response = cast(Mapping[str, object], value)
    if ARTIFACT_CANONICAL_JSON_V1.encode(response) != payload:
        raise RunValidationError("durable provider response is not canonical")
    return response


def _record_cell_failure(
    ledger: RunnerLedger,
    cell_id: str,
    *,
    provider_attempt_id: str,
    exc: BaseException,
    transport_started: bool,
) -> None:
    failure_type = type(exc).__name__
    if transport_started:
        ledger.mark_ambiguous(
            cell_id,
            provider_attempt_id=provider_attempt_id,
            failure_type=failure_type,
        )
    else:
        ledger.mark_blocked(
            cell_id,
            provider_attempt_id=provider_attempt_id,
            failure_type=failure_type,
        )


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
    return derive_cell_id(
        identity_sha256=identity_sha256,
        case_id=unit.case_id,
        unit_id=unit.unit_id,
        repeat_index=repeat_index,
    )


def derive_cell_id(
    *,
    identity_sha256: str,
    case_id: str,
    unit_id: str,
    repeat_index: int,
) -> str:
    """Derive the canonical durable ID for one frozen run cell.

    Workflow matrix construction and the runner must use the same identity
    function.  Keeping this helper public lets the official workflow build
    resumable artifact names without reimplementing the receipt contract.
    """

    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "case_id": case_id,
                "repeat_index": repeat_index,
                "run_identity_sha256": identity_sha256,
                "unit_id": unit_id,
            },
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )


def derive_run_identity_sha256(
    *,
    execution: ForecastExecution,
    entry: ModelRegistryEntry,
    registry_sha256: str,
    ceiling_microusd: int,
    harness: str,
    ablation: str,
    repeat_count: int,
    account: str,
    manifest_id: str | None = None,
    manifest_sha256: str | None = None,
    approval_reference: str | None = None,
) -> str:
    """Derive the exact run identity consumed by the public runner."""

    identity = _run_identity_record(
        execution=execution,
        entry=entry,
        registry_sha256=registry_sha256,
        ceiling_microusd=ceiling_microusd,
        harness=harness,
        ablation=ablation,
        repeat_count=repeat_count,
        account=account,
        manifest_id=manifest_id,
        manifest_sha256=manifest_sha256,
        approval_reference=approval_reference,
    )
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            identity,
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )


def _run_identity_record(
    *,
    execution: ForecastExecution,
    entry: ModelRegistryEntry,
    registry_sha256: str,
    ceiling_microusd: int,
    harness: str,
    ablation: str,
    repeat_count: int,
    account: str,
    manifest_id: str | None,
    manifest_sha256: str | None,
    approval_reference: str | None,
) -> dict[str, object]:
    if (manifest_id is None) != (manifest_sha256 is None):
        raise RunValidationError(
            "manifest ID and manifest commitment must be supplied together"
        )
    identity: dict[str, object] = {
        "schema_version": str(PUBLIC_RUN_IDENTITY_V1),
        "ablation": ablation,
        "account": account,
        "ceiling_microusd": ceiling_microusd,
        "forecast_release_digest": execution.release.release_digest,
        "harness": harness,
        "model_key": entry.registry_key,
        "model_registry_entry_sha256": model_registry_entry_sha256(entry),
        "model_registry_sha256": registry_sha256,
        "repeat_count": repeat_count,
        "served_model_version": entry.model_version_or_snapshot,
    }
    if approval_reference is not None:
        identity["approval_reference"] = approval_reference
    if manifest_id is not None and manifest_sha256 is not None:
        identity.update(
            {
                "run_manifest_id": manifest_id,
                "run_manifest_sha256": manifest_sha256,
            }
        )
    return identity


def _select_units(
    units: tuple[ForecastPredictionUnit, ...],
    *,
    unit_id: str | None,
) -> tuple[ForecastPredictionUnit, ...]:
    """Select one manifest-declared unit for a matrix worker, if requested."""

    if unit_id is None:
        return units
    if not unit_id.strip():
        raise RunValidationError("unit_id must not be empty")
    selected = tuple(unit for unit in units if unit.unit_id == unit_id)
    if not selected:
        raise RunValidationError(
            f"unit_id is not declared by the forecast release: {unit_id}"
        )
    return selected


def _select_repeats(
    *,
    repeat_count: int,
    repeat_index: int | None,
) -> tuple[int, ...]:
    """Select one repeat for a matrix worker, while preserving run identity."""

    if repeat_index is None:
        return tuple(range(1, repeat_count + 1))
    if (
        isinstance(repeat_index, bool)
        or repeat_index < 1
        or repeat_index > repeat_count
    ):
        raise RunValidationError("repeat_index must be between 1 and repeat_count")
    return (repeat_index,)


def _select_cell(
    units: tuple[ForecastPredictionUnit, ...],
    *,
    repeat_count: int,
    identity_sha256: str,
    cell_id: str,
) -> tuple[ForecastPredictionUnit, int]:
    """Resolve one supplied cell ID to its manifest unit and repeat."""

    matches = [
        (unit, repeat_index)
        for unit in units
        for repeat_index in range(1, repeat_count + 1)
        if _cell_id(
            identity_sha256=identity_sha256,
            unit=unit,
            repeat_index=repeat_index,
        )
        == cell_id
    ]
    if len(matches) != 1:
        raise RunValidationError(
            "cell_id does not identify exactly one manifest-authorized cell"
        )
    return matches[0]


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

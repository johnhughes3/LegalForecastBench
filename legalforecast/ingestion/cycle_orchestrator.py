"""Safe, receipt-backed orchestration for repeatable acquisition cycles.

The coordinator is intentionally thin: every stage is still executed by its
existing ``legalforecast acquisition`` command.  This module owns only ordered
execution, safety-boundary pauses, and immutable receipts for the exact run-card
bytes that each stage produced.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    canonical_json_bytes,
    read_unique_regular_file,
)

CONFIG_SCHEMA_VERSION = "legalforecast.acquisition_cycle_config.v1"
RECEIPT_SCHEMA_VERSION = "legalforecast.acquisition_cycle_stage_receipt.v1"
STATUS_SCHEMA_VERSION = "legalforecast.acquisition_cycle_status.v1"

_STAGE_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "cycle_id",
        "eligibility_anchor",
        "target_case_count",
        "stages",
    }
)
_STAGE_FIELDS = frozenset(
    {
        "id",
        "command",
        "boundary",
        "arguments",
        "run_card",
        "run_card_stage",
    }
)


class CycleOrchestratorError(ValueError):
    """Raised when cycle configuration, receipts, or stage output is unsafe."""


class AcquisitionBoundary(StrEnum):
    """Explicit authority boundary crossed by one existing acquisition stage."""

    PROVIDER_FREE = "provider_free"
    NETWORK = "network"
    HUMAN = "human"
    MODEL_PROVIDER = "model_provider"
    PAID = "paid"


# This is a reviewed allowlist, not an operator-supplied classification.  Commands
# outside it remain runnable directly but cannot silently enter a cycle manifest.
COMMAND_BOUNDARIES: Mapping[str, AcquisitionBoundary] = MappingProxyType(
    {
        # Identity, deterministic planning, assembly, and final reconciliation.
        "init-cycle": AcquisitionBoundary.PROVIDER_FREE,
        "project-target-cohort": AcquisitionBoundary.PROVIDER_FREE,
        "plan-public-downloads": AcquisitionBoundary.PROVIDER_FREE,
        "init-purchase-ledger": AcquisitionBoundary.PROVIDER_FREE,
        "merge-download-manifests": AcquisitionBoundary.PROVIDER_FREE,
        "materialize-cohort-documents": AcquisitionBoundary.PROVIDER_FREE,
        "bind-acquisition-component": AcquisitionBoundary.PROVIDER_FREE,
        "assemble-cycle-acquisition": AcquisitionBoundary.PROVIDER_FREE,
        "prepare-disclosure-review": AcquisitionBoundary.PROVIDER_FREE,
        "plan-disclosure-provenance": AcquisitionBoundary.PROVIDER_FREE,
        "build-disclosure-review-bundle": AcquisitionBoundary.PROVIDER_FREE,
        "clear-provenance-disclosures": AcquisitionBoundary.PROVIDER_FREE,
        "finalize-provenance-quarantine": AcquisitionBoundary.PROVIDER_FREE,
        "resolve-post-recovery-documents": AcquisitionBoundary.PROVIDER_FREE,
        "plan-parse-documents": AcquisitionBoundary.PROVIDER_FREE,
        "build-decision-texts": AcquisitionBoundary.PROVIDER_FREE,
        "plan-label-audit": AcquisitionBoundary.PROVIDER_FREE,
        "plan-packet-inputs": AcquisitionBoundary.PROVIDER_FREE,
        "build-packets": AcquisitionBoundary.PROVIDER_FREE,
        "finalize-corpus": AcquisitionBoundary.PROVIDER_FREE,
        "merge-artifacts": AcquisitionBoundary.PROVIDER_FREE,
        # Public-source discovery, downloads, and noncharging provider lookups.
        "discover-case-dev": AcquisitionBoundary.NETWORK,
        "discover-firecrawl-recap": AcquisitionBoundary.NETWORK,
        "discover-firecrawl-recap-decisions": AcquisitionBoundary.NETWORK,
        "enrich-recap-case-dev": AcquisitionBoundary.NETWORK,
        "acquire-ranked-firecrawl-dockets": AcquisitionBoundary.NETWORK,
        "discover-courtlistener": AcquisitionBoundary.NETWORK,
        "fetch-firecrawl-dockets": AcquisitionBoundary.NETWORK,
        "screen-firecrawl-dockets": AcquisitionBoundary.PROVIDER_FREE,
        "bridge-pacer-gaps": AcquisitionBoundary.NETWORK,
        "prepare-target-cohort": AcquisitionBoundary.NETWORK,
        "prepare-target-100": AcquisitionBoundary.NETWORK,
        "download-free": AcquisitionBoundary.NETWORK,
        "recover-recap-fetch-quarantine": AcquisitionBoundary.NETWORK,
        "recover-purchased": AcquisitionBoundary.NETWORK,
        # Explicit John/hardware-review boundaries.
        "record-purchase-approval": AcquisitionBoundary.HUMAN,
        "record-disclosure-review-decisions": AcquisitionBoundary.HUMAN,
        "seal-disclosure-review-bundle": AcquisitionBoundary.HUMAN,
        "apply-unitization-review": AcquisitionBoundary.HUMAN,
        "apply-lawyer-review": AcquisitionBoundary.HUMAN,
        # External parser or labeling-model calls.
        "parse-documents": AcquisitionBoundary.MODEL_PROVIDER,
        "llm-unitize": AcquisitionBoundary.MODEL_PROVIDER,
        "llm-review-stage-a": AcquisitionBoundary.MODEL_PROVIDER,
        "llm-label": AcquisitionBoundary.MODEL_PROVIDER,
        # The only supported charge-bearing CourtListener document path.
        "purchase-missing-recap-fetch": AcquisitionBoundary.PAID,
    }
)


@dataclass(frozen=True, slots=True)
class CycleStage:
    """One exact existing acquisition command and its completion run card."""

    stage_id: str
    command: str
    boundary: AcquisitionBoundary
    arguments: tuple[str, ...]
    run_card: Path
    run_card_stage: str

    @property
    def invocation(self) -> tuple[str, ...]:
        return ("legalforecast", "acquisition", self.command, *self.arguments)


@dataclass(frozen=True, slots=True)
class AcquisitionCycleConfig:
    """Immutable ordered cycle plan loaded from canonical JSON bytes."""

    cycle_id: str
    eligibility_anchor: date
    target_case_count: int
    stages: tuple[CycleStage, ...]
    config_path: Path
    config_sha256: str


@dataclass(frozen=True, slots=True)
class BoundaryPermissions:
    """Operator-granted authority for the current coordinator invocation."""

    network: bool = False
    human: bool = False
    model_provider: bool = False
    paid: bool = False

    def allows(self, boundary: AcquisitionBoundary) -> bool:
        if boundary is AcquisitionBoundary.PROVIDER_FREE:
            return True
        if boundary is AcquisitionBoundary.NETWORK:
            return self.network
        if boundary is AcquisitionBoundary.HUMAN:
            return self.human
        if boundary is AcquisitionBoundary.MODEL_PROVIDER:
            return self.network and self.model_provider
        if boundary is AcquisitionBoundary.PAID:
            return self.network and self.paid
        raise AssertionError(f"unhandled acquisition boundary: {boundary}")


StageExecutor = Callable[[str, tuple[str, ...]], int]


def load_cycle_config(path: Path) -> AcquisitionCycleConfig:
    """Read and validate one canonical, unique, regular cycle configuration."""

    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CycleOrchestratorError(str(exc)) from exc
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CycleOrchestratorError("cycle config must be valid UTF-8 JSON") from exc
    if not isinstance(raw, Mapping):
        raise CycleOrchestratorError("cycle config must be a JSON object")
    record = cast(Mapping[str, object], raw)
    if canonical_json_bytes(record) != payload:
        raise CycleOrchestratorError("cycle config must use canonical JSON bytes")
    if frozenset(record) != _TOP_LEVEL_FIELDS:
        raise CycleOrchestratorError("cycle config fields differ from the v1 schema")
    if record.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise CycleOrchestratorError("cycle config schema_version is unsupported")
    cycle_id = _required_text(record, "cycle_id")
    if not _STAGE_ID.fullmatch(cycle_id):
        raise CycleOrchestratorError("cycle_id must use lowercase safe-name characters")
    anchor_text = _required_text(record, "eligibility_anchor")
    try:
        eligibility_anchor = date.fromisoformat(anchor_text)
    except ValueError as exc:
        raise CycleOrchestratorError(
            "eligibility_anchor must be an ISO date (YYYY-MM-DD)"
        ) from exc
    target_case_count = _required_int(record, "target_case_count")
    if target_case_count < 1:
        raise CycleOrchestratorError("target_case_count must be positive")
    raw_stages = record.get("stages")
    if not isinstance(raw_stages, list):
        raise CycleOrchestratorError("stages must be a JSON list")
    stage_values = cast(list[object], raw_stages)
    stages = tuple(
        _parse_stage(value, index=index) for index, value in enumerate(stage_values)
    )
    stage_ids = [stage.stage_id for stage in stages]
    if len(stage_ids) != len(set(stage_ids)):
        raise CycleOrchestratorError("cycle stage IDs must be unique")
    config = AcquisitionCycleConfig(
        cycle_id=cycle_id,
        eligibility_anchor=eligibility_anchor,
        target_case_count=target_case_count,
        stages=stages,
        config_path=path.absolute(),
        config_sha256=hashlib.sha256(payload).hexdigest(),
    )
    _validate_cycle_stage_identity(config)
    return config


def run_acquisition_cycle(
    *,
    config_path: Path,
    state_root: Path,
    execute: bool,
    permissions: BoundaryPermissions,
    executor: StageExecutor,
) -> dict[str, object]:
    """Inspect or advance a cycle until completion or the next authority gate."""

    config = load_cycle_config(config_path)
    _validate_state_root(state_root)
    if execute:
        with _cycle_lock(state_root):
            return _advance_cycle(
                config=config,
                state_root=state_root,
                execute=True,
                permissions=permissions,
                executor=executor,
            )
    return _advance_cycle(
        config=config,
        state_root=state_root,
        execute=False,
        permissions=permissions,
        executor=executor,
    )


def _advance_cycle(
    *,
    config: AcquisitionCycleConfig,
    state_root: Path,
    execute: bool,
    permissions: BoundaryPermissions,
    executor: StageExecutor,
) -> dict[str, object]:
    """Advance one already-loaded cycle while the caller holds its lock."""

    stage_statuses: list[dict[str, object]] = []
    completed_count = 0
    next_stage: CycleStage | None = None
    stop_reason: str | None = None

    for index, stage in enumerate(config.stages):
        _require_config_unchanged(config)
        receipt_path = _receipt_path(state_root, index=index, stage=stage)
        if receipt_path.exists() or receipt_path.is_symlink():
            receipt = _verify_receipt(
                receipt_path,
                config=config,
                stage=stage,
                index=index,
            )
            completed_count += 1
            stage_statuses.append(
                _stage_status(stage, "completed", receipt_sha256=receipt)
            )
            continue

        next_stage = stage
        if not execute:
            stage_statuses.append(_stage_status(stage, "ready"))
            stop_reason = "execution_not_requested"
            break
        if not permissions.allows(stage.boundary):
            stage_statuses.append(_stage_status(stage, "blocked"))
            stop_reason = f"{stage.boundary.value}_boundary_not_authorized"
            break

        exit_code = executor(stage.command, stage.arguments)
        if exit_code != 0:
            raise CycleOrchestratorError(
                f"stage {stage.stage_id} exited with status {exit_code}"
            )
        _require_config_unchanged(config)
        run_card_payload, run_card = _verified_run_card(stage)
        receipt_payload = canonical_json_bytes(
            _receipt_record(
                config=config,
                stage=stage,
                index=index,
                run_card_payload=run_card_payload,
                run_card=run_card,
            )
        )
        _write_immutable(receipt_path, receipt_payload)
        receipt_sha256 = hashlib.sha256(receipt_payload).hexdigest()
        completed_count += 1
        stage_statuses.append(
            _stage_status(stage, "completed", receipt_sha256=receipt_sha256)
        )
        next_stage = None

    for stage in config.stages[len(stage_statuses) :]:
        stage_statuses.append(_stage_status(stage, "pending"))

    if completed_count == len(config.stages):
        status = "completed"
        next_stage = None
        stop_reason = None
    elif stop_reason == "execution_not_requested":
        status = "ready"
    else:
        status = "blocked"

    corpus_finalization_planned = (
        bool(config.stages) and config.stages[-1].command == "finalize-corpus"
    )
    corpus_target_verified = False
    clean_case_count: int | None = None
    if status == "completed" and corpus_finalization_planned:
        _, final_run_card = _verified_run_card(config.stages[-1])
        raw_clean_count = _verified_corpus_target(
            config=config,
            stage=config.stages[-1],
            run_card=final_run_card,
        )
        if raw_clean_count is None:
            raise AssertionError(
                "final cycle stage lost its corpus-finalization identity"
            )
        corpus_target_verified = True
        clean_case_count = raw_clean_count

    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "eligibility_anchor": config.eligibility_anchor.isoformat(),
        "target_case_count": config.target_case_count,
        "config_path": str(config.config_path),
        "config_sha256": config.config_sha256,
        "state_root": str(state_root.absolute()),
        "mode": "execute" if execute else "status",
        "status": status,
        "stop_reason": stop_reason,
        "completed_stage_count": completed_count,
        "stage_count": len(config.stages),
        "plan_completed": status == "completed",
        "corpus_finalization_planned": corpus_finalization_planned,
        "corpus_target_verified": corpus_target_verified,
        "clean_case_count": clean_case_count,
        "next_stage": _stage_status(
            next_stage,
            "blocked" if status == "blocked" else "ready",
        )
        if next_stage is not None
        else None,
        "stages": stage_statuses,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }


def _validate_cycle_stage_identity(config: AcquisitionCycleConfig) -> None:
    if not config.stages:
        raise CycleOrchestratorError("cycle config must contain at least one stage")
    if config.stages[0].command != "init-cycle":
        raise CycleOrchestratorError("the first cycle stage must be init-cycle")
    for stage in config.stages:
        anchor_values = _flag_values(stage.arguments, "--eligibility-anchor")
        if anchor_values and anchor_values != (config.eligibility_anchor.isoformat(),):
            raise CycleOrchestratorError(
                f"stage {stage.stage_id} eligibility anchor differs from the cycle"
            )
        if stage.command == "init-cycle" and anchor_values != (
            config.eligibility_anchor.isoformat(),
        ):
            raise CycleOrchestratorError(
                "init-cycle must receive the configured eligibility anchor"
            )
        if stage.command == "prepare-target-cohort":
            target_values = _flag_values(stage.arguments, "--target-case-count")
            if target_values != (str(config.target_case_count),):
                raise CycleOrchestratorError(
                    "prepare-target-cohort target count differs from the cycle"
                )
        if stage.command == "prepare-target-100" and config.target_case_count != 100:
            raise CycleOrchestratorError(
                "prepare-target-100 requires target_case_count 100"
            )
        if stage.command == "finalize-corpus":
            target_values = _flag_values(stage.arguments, "--target-clean-cases")
            if target_values != (str(config.target_case_count),):
                raise CycleOrchestratorError(
                    "finalize-corpus target count differs from the cycle"
                )


def _require_config_unchanged(config: AcquisitionCycleConfig) -> None:
    try:
        current = read_unique_regular_file(config.config_path)
    except (OSError, ReviewBundleError) as exc:
        raise CycleOrchestratorError("cycle config changed during execution") from exc
    if hashlib.sha256(current).hexdigest() != config.config_sha256:
        raise CycleOrchestratorError("cycle config changed during execution")


def _parse_stage(value: object, *, index: int) -> CycleStage:
    if not isinstance(value, Mapping):
        raise CycleOrchestratorError(f"stage {index} must be a JSON object")
    record = cast(Mapping[str, object], value)
    if frozenset(record) != _STAGE_FIELDS:
        raise CycleOrchestratorError(f"stage {index} fields differ from the v1 schema")
    stage_id = _required_text(record, "id")
    if not _STAGE_ID.fullmatch(stage_id):
        raise CycleOrchestratorError(f"stage {index} id is not a safe name")
    command = _required_text(record, "command")
    expected_boundary = COMMAND_BOUNDARIES.get(command)
    if expected_boundary is None:
        raise CycleOrchestratorError(
            f"stage {stage_id} command is not approved for cycle orchestration: "
            f"{command}"
        )
    boundary_text = _required_text(record, "boundary")
    try:
        boundary = AcquisitionBoundary(boundary_text)
    except ValueError as exc:
        raise CycleOrchestratorError(
            f"stage {stage_id} has an unknown authority boundary"
        ) from exc
    if boundary is not expected_boundary:
        raise CycleOrchestratorError(
            f"stage {stage_id} boundary must be {expected_boundary.value}"
        )
    arguments = _required_text_list(record, "arguments")
    if "--execute" not in arguments:
        raise CycleOrchestratorError(
            f"stage {stage_id} must be an executed acquisition command"
        )
    if "--no-resume" in arguments:
        raise CycleOrchestratorError(
            f"stage {stage_id} cannot disable deterministic resume"
        )
    run_card = Path(_required_text(record, "run_card"))
    if not run_card.is_absolute():
        raise CycleOrchestratorError(
            f"stage {stage_id} run_card must be an absolute path"
        )
    _require_exact_flag_value(
        arguments,
        flag="--run-card-output",
        expected=str(run_card),
        stage_id=stage_id,
    )
    run_card_stage = _required_text(record, "run_card_stage")
    if run_card_stage != command:
        raise CycleOrchestratorError(
            f"stage {stage_id} run_card_stage must match its acquisition command"
        )
    return CycleStage(
        stage_id=stage_id,
        command=command,
        boundary=boundary,
        arguments=arguments,
        run_card=run_card,
        run_card_stage=run_card_stage,
    )


def _verify_receipt(
    path: Path,
    *,
    config: AcquisitionCycleConfig,
    stage: CycleStage,
    index: int,
) -> str:
    try:
        receipt_parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise CycleOrchestratorError(
            f"stage receipt directory is unavailable: {path.parent}"
        ) from exc
    if receipt_parent != path.parent.absolute():
        raise CycleOrchestratorError(
            f"stage receipt directory must not contain symlinks: {path.parent}"
        )
    payload = _read_canonical_json(path, label="stage receipt")
    receipt = cast(Mapping[str, object], json.loads(payload))
    expected_fields = {
        "schema_version",
        "config_sha256",
        "stage_index",
        "stage_id",
        "command",
        "boundary",
        "arguments_sha256",
        "run_card_path",
        "run_card_stage",
        "run_card_sha256",
        "output_commitments",
    }
    if set(receipt) != expected_fields:
        raise CycleOrchestratorError(f"stage receipt fields differ: {path}")
    run_card_payload, run_card = _verified_run_card(stage)
    expected = _receipt_record(
        config=config,
        stage=stage,
        index=index,
        run_card_payload=run_card_payload,
        run_card=run_card,
    )
    if dict(receipt) != expected:
        if receipt.get("run_card_sha256") != expected["run_card_sha256"]:
            raise CycleOrchestratorError(
                f"receipted run card changed for stage {stage.stage_id}"
            )
        raise CycleOrchestratorError(
            f"stage receipt no longer matches cycle config: {stage.stage_id}"
        )
    return hashlib.sha256(payload).hexdigest()


def _verified_run_card(stage: CycleStage) -> tuple[bytes, Mapping[str, object]]:
    try:
        payload = read_unique_regular_file(stage.run_card)
    except (OSError, ReviewBundleError) as exc:
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} has no safe completion run card: {exc}"
        ) from exc
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} run card is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(raw, Mapping):
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} run card must be a JSON object"
        )
    card = cast(Mapping[str, object], raw)
    schema_version = card.get("schema_version")
    resume_evidence = card.get("resume")
    resume_verified = resume_evidence is True or (
        schema_version == "legalforecast.provenance_quarantine_clearance_run_card.v1"
        and "resume" not in card
    )
    if (
        not isinstance(schema_version, str)
        or not schema_version.startswith("legalforecast.")
        or card.get("stage") != stage.run_card_stage
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or not resume_verified
    ):
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} run card is not an executed completion"
        )
    paid_executed = card.get("paid_activity_executed")
    if not isinstance(paid_executed, bool):
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} run card lacks paid-activity evidence"
        )
    if paid_executed and stage.boundary not in {
        AcquisitionBoundary.MODEL_PROVIDER,
        AcquisitionBoundary.PAID,
    }:
        raise CycleOrchestratorError(
            f"stage {stage.stage_id} unexpectedly reports paid activity"
        )
    return payload, card


def _receipt_record(
    *,
    config: AcquisitionCycleConfig,
    stage: CycleStage,
    index: int,
    run_card_payload: bytes,
    run_card: Mapping[str, object],
) -> dict[str, object]:
    if run_card.get("stage") != stage.run_card_stage:
        raise CycleOrchestratorError(f"stage {stage.stage_id} run-card stage changed")
    _verified_corpus_target(config=config, stage=stage, run_card=run_card)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "config_sha256": config.config_sha256,
        "stage_index": index,
        "stage_id": stage.stage_id,
        "command": stage.command,
        "boundary": stage.boundary.value,
        "arguments_sha256": hashlib.sha256(
            canonical_json_bytes(list(stage.arguments))
        ).hexdigest(),
        "run_card_path": str(stage.run_card),
        "run_card_stage": stage.run_card_stage,
        "run_card_sha256": hashlib.sha256(run_card_payload).hexdigest(),
        "output_commitments": _output_commitments(run_card),
    }


def _verified_corpus_target(
    *,
    config: AcquisitionCycleConfig,
    stage: CycleStage,
    run_card: Mapping[str, object],
) -> int | None:
    if stage.command != "finalize-corpus":
        return None
    clean_count = run_card.get("clean_count")
    if (
        run_card.get("target_clean_cases") != config.target_case_count
        or run_card.get("meets_target") is not True
        or not isinstance(clean_count, int)
        or isinstance(clean_count, bool)
        or clean_count < config.target_case_count
    ):
        raise CycleOrchestratorError(
            "finalize-corpus run card does not verify the configured target"
        )
    return clean_count


def _stage_status(
    stage: CycleStage | None,
    status: str,
    *,
    receipt_sha256: str | None = None,
) -> dict[str, object]:
    if stage is None:
        raise AssertionError("stage status requires a stage")
    return {
        "id": stage.stage_id,
        "command": stage.command,
        "boundary": stage.boundary.value,
        "status": status,
        "run_card": str(stage.run_card),
        "invocation": list(stage.invocation),
        **({"receipt_sha256": receipt_sha256} if receipt_sha256 is not None else {}),
    }


def _receipt_path(state_root: Path, *, index: int, stage: CycleStage) -> Path:
    return state_root / "receipts" / f"{index:04d}-{stage.stage_id}.json"


def _validate_state_root(path: Path) -> None:
    if not path.is_absolute():
        raise CycleOrchestratorError("state_root must be an absolute path")
    if path.resolve(strict=False) != path.absolute():
        raise CycleOrchestratorError("state_root path must not contain symlinks")
    if path.is_symlink():
        raise CycleOrchestratorError("state_root must not be a symlink")
    if path.exists() and not path.is_dir():
        raise CycleOrchestratorError("state_root must be a directory")


@contextmanager
def _cycle_lock(state_root: Path) -> Generator[None]:
    """Serialize mutations and paid-boundary checks for one cycle state."""

    state_root.mkdir(parents=True, exist_ok=True)
    _validate_state_root(state_root)
    lock_path = state_root / ".run-cycle.lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise CycleOrchestratorError("cycle locking requires O_NOFOLLOW")
    try:
        descriptor = os.open(lock_path, flags | nofollow, 0o600)
    except OSError as exc:
        raise CycleOrchestratorError(f"unable to open cycle lock: {lock_path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise CycleOrchestratorError("cycle lock must be a unique regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CycleOrchestratorError(
                "another run-cycle process already owns this state root"
            ) from exc
        yield
    finally:
        os.close(descriptor)


def _read_canonical_json(path: Path, *, label: str) -> bytes:
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CycleOrchestratorError(f"{label} is not a unique regular file") from exc
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CycleOrchestratorError(f"{label} is not valid UTF-8 JSON") from exc
    if canonical_json_bytes(value) != payload:
        raise CycleOrchestratorError(f"{label} must use canonical JSON bytes")
    return payload


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        receipt_parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise CycleOrchestratorError("receipt directory is unavailable") from exc
    if receipt_parent != path.parent.absolute():
        raise CycleOrchestratorError("receipt directory must not contain symlinks")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise CycleOrchestratorError("immutable receipt writes require O_NOFOLLOW")
    flags |= nofollow
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        existing = _read_canonical_json(path, label="stage receipt")
        if existing != payload:
            raise CycleOrchestratorError(
                f"existing stage receipt differs: {path}"
            ) from None
        return
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            # Preserve the primary write/fsync failure if best-effort cleanup also
            # loses a race or encounters a filesystem error.
            pass
        raise


def _require_exact_flag_value(
    arguments: Sequence[str],
    *,
    flag: str,
    expected: str,
    stage_id: str,
) -> None:
    if any(argument.startswith(f"{flag}=") for argument in arguments):
        raise CycleOrchestratorError(
            f"stage {stage_id} must not use or repeat equals-form {flag}"
        )
    indices = [index for index, value in enumerate(arguments) if value == flag]
    if len(indices) != 1 or indices[0] + 1 >= len(arguments):
        raise CycleOrchestratorError(
            f"stage {stage_id} must provide exactly one {flag}"
        )
    if arguments[indices[0] + 1] != expected:
        raise CycleOrchestratorError(f"stage {stage_id} {flag} must match its run_card")


def _flag_values(arguments: Sequence[str], flag: str) -> tuple[str, ...]:
    if any(argument.startswith(f"{flag}=") for argument in arguments):
        raise CycleOrchestratorError(f"{flag} must not use or repeat equals form")
    values: list[str] = []
    for index, argument in enumerate(arguments):
        if argument != flag:
            continue
        if index + 1 >= len(arguments):
            raise CycleOrchestratorError(f"{flag} requires a value")
        values.append(arguments[index + 1])
    return tuple(values)


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CycleOrchestratorError(f"{field} must be a non-empty trimmed string")
    if "\x00" in value:
        raise CycleOrchestratorError(f"{field} must not contain NUL")
    return value


def _required_text_list(
    record: Mapping[str, object],
    field: str,
) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list):
        raise CycleOrchestratorError(f"{field} must be a JSON list")
    return tuple(
        _required_text({f"{field}[{index}]": item}, f"{field}[{index}]")
        for index, item in enumerate(cast(list[object], value))
    )


def _required_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CycleOrchestratorError(f"{field} must be an integer")
    return value


def _output_commitments(run_card: Mapping[str, object]) -> list[dict[str, object]]:
    raw_paths = run_card.get("output_paths")
    if not isinstance(raw_paths, list):
        raise CycleOrchestratorError("stage run card lacks output_paths")
    paths = [
        _required_text({"path": value}, "path")
        for value in cast(list[object], raw_paths)
    ]
    if len(paths) != len(set(paths)):
        raise CycleOrchestratorError("stage run card repeats an output path")
    return [_output_commitment(Path(value)) for value in paths]


def _output_commitment(path: Path) -> dict[str, object]:
    if not path.is_absolute():
        raise CycleOrchestratorError(f"stage output path must be absolute: {path}")
    absolute = path
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise CycleOrchestratorError(
            f"stage output is unavailable: {absolute}"
        ) from exc
    if resolved != absolute:
        raise CycleOrchestratorError(
            f"stage output path must not contain symlinks: {absolute}"
        )
    if absolute.suffix in {".sqlite", ".sqlite3", ".db"}:
        try:
            metadata = absolute.lstat()
        except OSError as exc:
            raise CycleOrchestratorError(
                f"mutable stage state is unavailable: {absolute}"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise CycleOrchestratorError(
                f"mutable stage state must be a unique regular file: {absolute}"
            )
        return {
            "path": str(absolute),
            "kind": "mutable_state",
        }
    if absolute.is_file():
        try:
            payload = read_unique_regular_file(absolute)
        except (OSError, ReviewBundleError) as exc:
            raise CycleOrchestratorError(
                f"stage output is not a safe regular file: {absolute}"
            ) from exc
        return {
            "path": str(absolute),
            "kind": "file",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }
    if absolute.is_dir():
        tree = _directory_tree_commitment(absolute)
        return {
            "path": str(absolute),
            "kind": "directory",
            "tree_sha256": hashlib.sha256(canonical_json_bytes(tree)).hexdigest(),
            "entry_count": len(tree),
            "file_count": sum(record["kind"] == "file" for record in tree),
        }
    raise CycleOrchestratorError(f"stage output is unavailable: {absolute}")


def _directory_tree_commitment(root: Path) -> list[dict[str, object]]:
    directory_fd = _open_directory_nofollow(root)
    try:
        root_before = os.fstat(directory_fd)
        records: list[dict[str, object]] = []
        _walk_directory_at(
            directory_fd,
            relative_parent=Path(),
            records=records,
        )
        root_after = os.fstat(directory_fd)
        try:
            root_named = root.lstat()
        except OSError as exc:
            raise CycleOrchestratorError(
                f"stage output directory changed while being read: {root}"
            ) from exc
        if not _same_output_identity(root_before, root_after, root_named):
            raise CycleOrchestratorError(
                f"stage output directory changed while being read: {root}"
            )
        return records
    finally:
        os.close(directory_fd)


def _open_directory_nofollow(path: Path) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise CycleOrchestratorError(
            "stage output authentication requires no-follow directory support"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | nofollow | directory
    absolute = Path(os.path.abspath(path))
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise CycleOrchestratorError(
            f"unable to inspect stage output directory: {path}"
        ) from exc


def _walk_directory_at(
    directory_fd: int,
    *,
    relative_parent: Path,
    records: list[dict[str, object]],
) -> None:
    try:
        with os.scandir(directory_fd) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
    except OSError as exc:
        raise CycleOrchestratorError(
            "unable to enumerate stage output directory"
        ) from exc
    directory_flags = (
        os.O_RDONLY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    file_flags = (
        os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    )
    for entry in entries:
        relative = relative_parent / entry.name
        try:
            named_before = os.stat(
                entry.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise CycleOrchestratorError(
                f"stage output directory changed while being read: {relative}"
            ) from exc
        if stat.S_ISLNK(named_before.st_mode):
            raise CycleOrchestratorError(
                f"stage output directory contains a symlink: {relative}"
            )
        if stat.S_ISDIR(named_before.st_mode):
            try:
                child_fd = os.open(
                    entry.name,
                    directory_flags,
                    dir_fd=directory_fd,
                )
            except OSError as exc:
                raise CycleOrchestratorError(
                    f"stage output directory changed while being read: {relative}"
                ) from exc
            try:
                opened = os.fstat(child_fd)
                if not _same_output_identity(named_before, opened):
                    raise CycleOrchestratorError(
                        f"stage output directory changed while being read: {relative}"
                    )
                records.append({"path": relative.as_posix(), "kind": "directory"})
                _walk_directory_at(
                    child_fd,
                    relative_parent=relative,
                    records=records,
                )
                after = os.fstat(child_fd)
                named_after = os.stat(
                    entry.name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if not _same_output_identity(opened, after, named_after):
                    raise CycleOrchestratorError(
                        f"stage output directory changed while being read: {relative}"
                    )
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(named_before.st_mode):
            raise CycleOrchestratorError(
                f"stage output directory contains a non-file: {relative}"
            )
        try:
            file_fd = os.open(entry.name, file_flags, dir_fd=directory_fd)
        except OSError as exc:
            raise CycleOrchestratorError(
                f"stage output directory changed while being read: {relative}"
            ) from exc
        try:
            opened = os.fstat(file_fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or not _same_output_identity(named_before, opened)
            ):
                raise CycleOrchestratorError(
                    f"stage output directory contains an unsafe file: {relative}"
                )
            digest = hashlib.sha256()
            byte_count = 0
            while chunk := os.read(file_fd, 1024 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
            after = os.fstat(file_fd)
            named_after = os.stat(
                entry.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if (
                not _same_output_identity(opened, after, named_after)
                or byte_count != after.st_size
            ):
                raise CycleOrchestratorError(
                    f"stage output file changed while being read: {relative}"
                )
        finally:
            os.close(file_fd)
        records.append(
            {
                "path": relative.as_posix(),
                "kind": "file",
                "sha256": digest.hexdigest(),
                "byte_count": byte_count,
            }
        )


def _same_output_identity(*records: os.stat_result) -> bool:
    fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    first, *others = records
    return all(
        all(getattr(first, field) == getattr(other, field) for field in fields)
        for other in others
    )

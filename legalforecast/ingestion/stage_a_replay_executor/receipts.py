"""Durable, replay-verified evidence emitted by the Stage A executor."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
)
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageAExecution,
    CandidateScopedStageAPlan,
    CandidateScopedStageAReceipt,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)

INVOCATION_SCHEMA_VERSION = (
    "legalforecast.candidate_scoped_stage_a_invocation_journal.v1"
)
EXECUTOR_RECEIPT_SCHEMA_VERSION = (
    "legalforecast.candidate_scoped_stage_a_executor_receipt.v1"
)


def persist_plan(
    spec: ReplaySpec, plan: CandidateScopedStageAPlan
) -> Mapping[str, object]:
    """Persist and re-authenticate the minted replay plan before provider access."""

    record = plan.to_record()
    _verify_plan_record(record, plan.plan_sha256)
    return _persist(spec.output_paths["plan_path"], record, "replay plan")


def persist_terminal_evidence(
    spec: ReplaySpec,
    *,
    plan: CandidateScopedStageAPlan | None,
    execution: CandidateScopedStageAExecution | None,
    stage_a_receipt: CandidateScopedStageAReceipt | None,
    invocations: Sequence[Mapping[str, object]],
    halt_evidence: Mapping[str, object] | None,
    lineage_evidence: Mapping[str, object] | None,
    halted: bool,
) -> Mapping[str, object]:
    """Write distinct execution/receipt/journal artifacts and the outer receipt."""

    artifacts: dict[str, Mapping[str, object] | None] = {
        "plan": None,
        "execution": None,
        "stage_a_receipt": None,
        "invocation_journal": None,
    }
    plan_path = spec.output_paths["plan_path"]
    if plan is not None:
        artifacts["plan"] = _commitment(plan_path, "replay plan")
    if execution is not None:
        record = {
            **execution.content_record(),
            "execution_sha256": execution.execution_sha256,
        }
        _verify_execution_record(record, execution.execution_sha256)
        artifacts["execution"] = _persist(
            spec.output_paths["execution_path"], record, "replay execution"
        )
    if stage_a_receipt is not None:
        record = stage_a_receipt.to_record()
        _verify_stage_a_receipt_record(record, stage_a_receipt.receipt_sha256)
        artifacts["stage_a_receipt"] = _persist(
            spec.output_paths["stage_a_receipt_path"], record, "Stage A receipt"
        )
    invocation_content: dict[str, object] = {
        "schema_version": INVOCATION_SCHEMA_VERSION,
        "replay_spec_sha256": spec.spec_sha256,
        "code_commit": spec.code_commit,
        "invocations": [dict(record) for record in invocations],
        "spend_summary": _spend_summary(spec, invocations),
    }
    invocation_record = dict(invocation_content)
    invocation_record["invocation_journal_sha256"] = hashlib.sha256(
        ARTIFACT_CANONICAL_JSON_V1.encode(invocation_content)
    ).hexdigest()
    artifacts["invocation_journal"] = _persist(
        spec.output_paths["invocation_journal_path"],
        invocation_record,
        "invocation journal",
    )
    content: dict[str, object] = {
        "schema_version": EXECUTOR_RECEIPT_SCHEMA_VERSION,
        "replay_spec_sha256": spec.spec_sha256,
        "code_commit": spec.code_commit,
        "configuration_hashes": dict(spec.config_hashes),
        "model_ids": dict(spec.model_ids),
        "model_registry_sha256": spec.model_registry_sha256,
        "provider_caps_sha256": spec.provider_caps_sha256,
        "provider_journal_path": str(spec.provider_journal_path),
        "cycle_id": spec.cycle_id,
        "authorized_candidate_ids": list(spec.candidate_ids),
        "spend_summary": invocation_content["spend_summary"],
        "plan_sha256": None if plan is None else plan.plan_sha256,
        "execution_sha256": (None if execution is None else execution.execution_sha256),
        "stage_a_receipt_sha256": (
            None if stage_a_receipt is None else stage_a_receipt.receipt_sha256
        ),
        "artifacts": artifacts,
        "lineage_evidence": (
            None if lineage_evidence is None else dict(lineage_evidence)
        ),
        "halted": halted,
        "halt_evidence": None if halt_evidence is None else dict(halt_evidence),
    }
    receipt = dict(content)
    receipt["executor_receipt_sha256"] = hashlib.sha256(
        ARTIFACT_CANONICAL_JSON_V1.encode(content)
    ).hexdigest()
    _persist(spec.output_paths["executor_receipt_path"], receipt, "executor receipt")
    verify_persisted_evidence(
        spec,
        plan=plan,
        execution=execution,
        stage_a_receipt=stage_a_receipt,
        expected_executor_receipt=receipt,
    )
    return receipt


def verify_persisted_evidence(
    spec: ReplaySpec,
    *,
    plan: CandidateScopedStageAPlan | None,
    execution: CandidateScopedStageAExecution | None,
    stage_a_receipt: CandidateScopedStageAReceipt | None,
    expected_executor_receipt: Mapping[str, object],
) -> None:
    """Reread exact bytes and replay every existing Stage A digest."""

    if plan is not None:
        record = _read_record(spec.output_paths["plan_path"], "replay plan")
        if record != plan.to_record():
            raise StageAReplayExecutorError("persisted replay plan bytes differ")
        _verify_plan_record(record, plan.plan_sha256)
    if execution is not None:
        record = _read_record(spec.output_paths["execution_path"], "replay execution")
        expected = {
            **execution.content_record(),
            "execution_sha256": execution.execution_sha256,
        }
        if record != expected:
            raise StageAReplayExecutorError("persisted replay execution bytes differ")
        _verify_execution_record(record, execution.execution_sha256)
    if stage_a_receipt is not None:
        record = _read_record(
            spec.output_paths["stage_a_receipt_path"], "Stage A receipt"
        )
        if record != stage_a_receipt.to_record():
            raise StageAReplayExecutorError("persisted Stage A receipt bytes differ")
        _verify_stage_a_receipt_record(record, stage_a_receipt.receipt_sha256)
    invocation = _read_record(
        spec.output_paths["invocation_journal_path"], "invocation journal"
    )
    _verify_invocation_journal(spec, invocation)
    outer = _read_record(spec.output_paths["executor_receipt_path"], "executor receipt")
    if outer != dict(expected_executor_receipt):
        raise StageAReplayExecutorError("persisted executor receipt bytes differ")
    content = dict(outer)
    claimed = content.pop("executor_receipt_sha256", None)
    computed = hashlib.sha256(ARTIFACT_CANONICAL_JSON_V1.encode(content)).hexdigest()
    if claimed != computed:
        raise StageAReplayExecutorError("persisted executor receipt digest differs")
    raw_artifacts = cast(Mapping[str, object], outer["artifacts"])
    for name, value in raw_artifacts.items():
        if value is None:
            continue
        commitment = cast(Mapping[str, object], value)
        path = Path(cast(str, commitment["path"]))
        payload = _read_regular(path, f"persisted {name}")
        if hashlib.sha256(payload).hexdigest() != commitment.get("raw_sha256"):
            raise StageAReplayExecutorError(f"persisted {name} raw commitment differs")


def _verify_plan_record(record: Mapping[str, object], expected: str) -> None:
    content = dict(record)
    if content.pop("plan_sha256", None) != expected:
        raise StageAReplayExecutorError("replay plan digest field differs")
    computed = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            content, domain=CANDIDATE_SCOPED_STAGE_A_REPLAY_V1
        ).digest
    )
    if computed != expected:
        raise StageAReplayExecutorError("replay plan content digest differs")


def _verify_execution_record(record: Mapping[str, object], expected: str) -> None:
    content = dict(record)
    if content.pop("execution_sha256", None) != expected:
        raise StageAReplayExecutorError("replay execution digest field differs")
    computed = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            content, domain=CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1
        ).digest
    )
    if computed != expected:
        raise StageAReplayExecutorError("replay execution content digest differs")


def _verify_stage_a_receipt_record(record: Mapping[str, object], expected: str) -> None:
    content = dict(record)
    if content.pop("receipt_sha256", None) != expected:
        raise StageAReplayExecutorError("Stage A receipt digest field differs")
    computed = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            content, domain=CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1
        ).digest
    )
    if computed != expected:
        raise StageAReplayExecutorError("Stage A receipt content digest differs")


def _verify_invocation_journal(spec: ReplaySpec, record: Mapping[str, object]) -> None:
    if set(record) != {
        "schema_version",
        "replay_spec_sha256",
        "code_commit",
        "invocations",
        "spend_summary",
        "invocation_journal_sha256",
    }:
        raise StageAReplayExecutorError("invocation journal fields differ")
    if (
        record.get("schema_version") != INVOCATION_SCHEMA_VERSION
        or record.get("replay_spec_sha256") != spec.spec_sha256
        or record.get("code_commit") != spec.code_commit
    ):
        raise StageAReplayExecutorError("invocation journal authority differs")
    content = dict(record)
    claimed = content.pop("invocation_journal_sha256")
    if (
        claimed
        != hashlib.sha256(ARTIFACT_CANONICAL_JSON_V1.encode(content)).hexdigest()
    ):
        raise StageAReplayExecutorError("invocation journal digest differs")
    raw_invocations = record.get("invocations")
    if not isinstance(raw_invocations, list):
        raise StageAReplayExecutorError("invocation journal rows must be an array")
    invocations: list[Mapping[str, object]] = []
    for raw in cast(list[object], raw_invocations):
        if not isinstance(raw, Mapping):
            raise StageAReplayExecutorError("invocation journal row must be an object")
        invocation = dict(cast(Mapping[str, object], raw))
        digest = invocation.pop("invocation_sha256", None)
        if (
            digest
            != hashlib.sha256(ARTIFACT_CANONICAL_JSON_V1.encode(invocation)).hexdigest()
        ):
            raise StageAReplayExecutorError("invocation journal row digest differs")
        invocations.append(cast(Mapping[str, object], raw))
    if record.get("spend_summary") != _spend_summary(spec, invocations):
        raise StageAReplayExecutorError("invocation spend summary differs")


def _spend_summary(
    spec: ReplaySpec, invocations: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    totals = {candidate_id: Decimal("0") for candidate_id in spec.candidate_ids}
    outcomes: dict[str, list[dict[str, object]]] = {
        candidate_id: [] for candidate_id in spec.candidate_ids
    }
    aggregate = Decimal("0")
    for invocation in invocations:
        candidate_id = invocation.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id not in totals:
            raise StageAReplayExecutorError(
                "invocation journal contains an unauthorized candidate"
            )
        raw_cost = invocation.get("actual_cost_usd")
        cost = Decimal("0") if raw_cost is None else Decimal(str(raw_cost))
        if not cost.is_finite() or cost < 0:
            raise StageAReplayExecutorError("invocation cost is invalid")
        totals[candidate_id] += cost
        aggregate += cost
        outcomes[candidate_id].append(
            {
                "stage": invocation.get("stage"),
                "status": invocation.get("status"),
                "actual_cost_usd": None if raw_cost is None else format(cost, "f"),
                "attempt_count": invocation.get("attempt_count"),
                "new_attempt_count": invocation.get("new_attempt_count"),
                "terminal_route": invocation.get("terminal_route"),
            }
        )
    return {
        "aggregate_actual_cost_usd": format(aggregate, "f"),
        "aggregate_ceiling_usd": format(spec.aggregate_ceiling_usd, "f"),
        "per_candidate": {
            candidate_id: {
                "actual_cost_usd": format(totals[candidate_id], "f"),
                "ceiling_usd": format(
                    spec.per_candidate_ceiling_usd[candidate_id], "f"
                ),
                "outcomes": outcomes[candidate_id],
            }
            for candidate_id in spec.candidate_ids
        },
    }


def _persist(
    path: Path, record: Mapping[str, object], label: str
) -> Mapping[str, object]:
    if path.exists() or path.is_symlink():
        raise StageAReplayExecutorError(f"{label} output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ARTIFACT_CANONICAL_JSON_V1.encode(record)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)
    if _read_regular(path, label) != payload:
        raise StageAReplayExecutorError(f"{label} changed after persistence")
    return {
        "path": str(path),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _commitment(path: Path, label: str) -> Mapping[str, object]:
    payload = _read_regular(path, label)
    return {
        "path": str(path),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _read_record(path: Path, label: str) -> Mapping[str, object]:
    payload = _read_regular(path, label)
    try:
        value: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(f"{label} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{label} must be an object")
    typed_value = cast(Mapping[str, object], value)
    if ARTIFACT_CANONICAL_JSON_V1.encode(typed_value) != payload:
        raise StageAReplayExecutorError(f"{label} is not canonical JSON")
    return typed_value


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    return path.read_bytes()

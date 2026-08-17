"""Mechanical spend guards and per-invocation evidence for Stage A replay."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Protocol

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor.journal import (
    StageSpend,
    StageSpendSnapshot,
)
from legalforecast.ingestion.stage_a_replay_executor.lineage import (
    VerifiedReplayLineage,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    ReplaySpendCeilingError,
    StageAReplayExecutorError,
)


class SpendMeter(Protocol):
    """Authoritative incremental spend around one callback."""

    def before(
        self,
        request: CandidateScopedStageARerunRequest,
        *,
        stage: str,
        unitize: StageAStageOutcome | None,
    ) -> StageSpendSnapshot: ...

    def after(self, before: StageSpendSnapshot) -> StageSpend: ...


class ExecutionHalt(RuntimeError):
    """Internal control flow carrying already-structured terminal evidence."""

    def __init__(self, evidence: Mapping[str, object]) -> None:
        super().__init__(str(evidence.get("reason", "Stage A execution halted")))
        self.evidence = dict(evidence)


def guarded_callback(
    request: CandidateScopedStageARerunRequest,
    *,
    stage: str,
    callback: Callable[..., StageAStageOutcome] | None,
    unitize: StageAStageOutcome | None,
    meter: SpendMeter | None,
    spec: ReplaySpec,
    lineage: VerifiedReplayLineage,
    spent_by_candidate: dict[str, Decimal],
    aggregate_spent: Decimal,
    invocations: list[dict[str, object]],
    clock: Callable[[], float] | None,
) -> tuple[StageAStageOutcome, Decimal]:
    if callback is None or meter is None:
        raise StageAReplayExecutorError("provider callback is unavailable")
    candidate_id = request.candidate_id
    reservation = spec.invocation_reservations_usd[stage]
    candidate_spent = spent_by_candidate[candidate_id]
    if aggregate_spent + reservation > spec.aggregate_ceiling_usd:
        raise _ceiling_halt(
            spec,
            request,
            stage=stage,
            reservation=reservation,
            reason="aggregate",
            invocations=invocations,
        )
    if candidate_spent + reservation > spec.per_candidate_ceiling_usd[candidate_id]:
        raise _ceiling_halt(
            spec,
            request,
            stage=stage,
            reservation=reservation,
            reason="per-candidate",
            invocations=invocations,
        )
    lineage.require_unchanged()
    before = meter.before(request, stage=stage, unitize=unitize)
    started = clock() if clock is not None else None
    outcome: StageAStageOutcome | None = None
    callback_error: Exception | None = None
    try:
        outcome = (
            callback(request, unitize) if unitize is not None else callback(request)
        )
    except Exception as exc:
        callback_error = exc
    finished = clock() if clock is not None else None
    try:
        spend = meter.after(before)
    except Exception as meter_error:
        callback_reason = (
            ""
            if callback_error is None
            else "; provider callback also failed: "
            f"{type(callback_error).__name__}: {callback_error}"
        )
        reason = (
            f"{stage} spend evidence failed: {type(meter_error).__name__}: "
            f"{meter_error}{callback_reason}"
        )
        invocations.append(
            invocation_record(
                spec,
                request,
                stage=stage,
                reservation=reservation,
                spend=None,
                before=before,
                status="halted",
                elapsed_ms=_elapsed_ms(started, finished),
                outcome=outcome,
                error=reason,
            )
        )
        raise ExecutionHalt(
            {
                "status": "halted_on_spend_evidence_failure",
                "reason": reason,
                "candidate_id": candidate_id,
                "stage": stage,
                "provider_accessed": True,
            }
        ) from meter_error

    new_candidate_spent = candidate_spent + spend.actual_usd
    new_aggregate_spent = aggregate_spent + spend.actual_usd
    status = "failed" if outcome is None else outcome.status
    reason: str | None = None
    if callback_error is not None:
        reason = f"{stage} provider callback failed: {callback_error}"
    elif spend.attempt_count > 3:
        reason = f"{stage} candidate {candidate_id} attempted a forbidden fourth call"
    elif outcome is not None and outcome.status == "unknown":
        reason = f"{stage} candidate {candidate_id} returned an unknown outcome"
    elif new_candidate_spent > spec.per_candidate_ceiling_usd[candidate_id]:
        reason = (
            f"{stage} outcome for candidate {candidate_id} exceeded the signed "
            "per-candidate ceiling"
        )
    elif new_aggregate_spent > spec.aggregate_ceiling_usd:
        reason = f"{stage} outcome exceeded the signed aggregate ceiling"
    invocations.append(
        invocation_record(
            spec,
            request,
            stage=stage,
            reservation=reservation,
            spend=spend,
            before=before,
            status="halted" if reason is not None else status,
            elapsed_ms=_elapsed_ms(started, finished),
            outcome=outcome,
            error=reason,
        )
    )
    spent_by_candidate[candidate_id] = new_candidate_spent
    if reason is not None:
        halt_status = (
            "halted_at_ceiling" if "ceiling" in reason else "halted_on_provider_outcome"
        )
        raise ExecutionHalt(
            {
                "status": halt_status,
                "reason": reason,
                "candidate_id": candidate_id,
                "stage": stage,
                "actual_cost_usd": format(spend.actual_usd, "f"),
                "aggregate_spent_usd": format(new_aggregate_spent, "f"),
                "terminal_route": (
                    "qsp.attorney_adjudication"
                    if outcome is not None
                    and outcome.status
                    in {"reconstruction_failed", "terminal_escalation"}
                    else None
                ),
            }
        )
    assert outcome is not None
    return outcome, new_aggregate_spent


def provider_accessed(invocations: Sequence[Mapping[str, object]]) -> bool:
    for record in invocations:
        value = record.get("new_attempt_count")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return True
    return False


def invocation_record(
    spec: ReplaySpec,
    request: CandidateScopedStageARerunRequest,
    *,
    stage: str,
    reservation: Decimal,
    spend: StageSpend | None,
    before: StageSpendSnapshot | None = None,
    status: str,
    error: str | None = None,
    elapsed_ms: int | None = None,
    outcome: StageAStageOutcome | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "candidate_id": request.candidate_id,
        "stage": stage,
        "code_commit": spec.code_commit,
        "config_sha256": spec.config_hashes[stage],
        "model_id": spec.model_ids[stage],
        "request_sha256": request.request_sha256,
        "reservation_usd": format(reservation, "f"),
        "actual_cost_usd": None if spend is None else format(spend.actual_usd, "f"),
        "attempt_count": _evidence_value(spend, before, "attempt_count"),
        "new_attempt_count": None if spend is None else spend.new_attempt_count,
        "logical_call_key": _evidence_value(spend, before, "logical_call_key"),
        "provider_stage": _evidence_value(spend, before, "provider_stage"),
        "prompt_sha256": _evidence_value(spend, before, "prompt_sha256"),
        "journal_attempts": []
        if spend is None
        else [dict(row) for row in spend.attempts],
        "status": status,
    }
    if elapsed_ms is not None:
        record["elapsed_ms"] = elapsed_ms
    if error is not None:
        record["error"] = error
    if outcome is not None and outcome.status in {
        "reconstruction_failed",
        "terminal_escalation",
    }:
        record["terminal_route"] = "qsp.attorney_adjudication"
        terminal_evidence = {
            name: outcome.audit[name]
            for name in (
                "terminal_escalation_sha256",
                "terminal_escalation_receipt",
            )
            if name in outcome.audit
        }
        if "unitizer_terminal_review_queue" in outcome.audit:
            terminal_evidence["unitizer_terminal_review_queue_sha256"] = hashlib.sha256(
                ARTIFACT_CANONICAL_JSON_V1.encode(
                    outcome.audit["unitizer_terminal_review_queue"]
                )
            ).hexdigest()
        record["terminal_evidence"] = terminal_evidence
    record["invocation_sha256"] = hashlib.sha256(
        ARTIFACT_CANONICAL_JSON_V1.encode(record)
    ).hexdigest()
    return record


def _ceiling_halt(
    spec: ReplaySpec,
    request: CandidateScopedStageARerunRequest,
    *,
    stage: str,
    reservation: Decimal,
    reason: str,
    invocations: list[dict[str, object]],
) -> ExecutionHalt:
    message = (
        f"{stage} invocation for candidate {request.candidate_id} would exceed "
        f"the signed {reason} replay ceiling"
    )
    error = ReplaySpendCeilingError(message, candidate_id=request.candidate_id)
    invocations.append(
        invocation_record(
            spec,
            request,
            stage=stage,
            reservation=reservation,
            spend=None,
            status="halted_at_ceiling",
            error=str(error),
        )
    )
    return ExecutionHalt(
        {
            "status": "halted_at_ceiling",
            "reason": str(error),
            "candidate_id": request.candidate_id,
            "stage": stage,
        }
    )


def _evidence_value(
    spend: StageSpend | None,
    before: StageSpendSnapshot | None,
    field: str,
) -> object:
    source = before if spend is None else spend
    return None if source is None else getattr(source, field)


def _elapsed_ms(started: float | None, finished: float | None) -> int | None:
    if started is None or finished is None:
        return None
    return max(0, round((finished - started) * 1000))

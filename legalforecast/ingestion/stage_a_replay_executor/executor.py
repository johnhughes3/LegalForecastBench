"""Canonical, authorization-bound executor for candidate-scoped Stage A replay.

The production CLI accepts one self-hashed spec. That spec supplies owner
authority, verifier inputs, frozen v5/v4 configuration, journal identity,
mechanical spend ceilings, and every output path; no execution fact is accepted
as an ad-hoc flag.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from legalforecast.config.registry import repository_root
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageAExecution,
    CandidateScopedStageAPlan,
    CandidateScopedStageAReceipt,
    CandidateScopedStageAReplayError,
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
    bind_predecessor_stage_a_lineage,
    plan_candidate_scoped_stage_a_replay,
    run_candidate_scoped_stage_a_replay,
    seal_candidate_scoped_stage_a_replay,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    ReplayOutputClaimError,
)
from legalforecast.ingestion.stage_a_replay_executor.guard import (
    ExecutionHalt,
    SpendMeter,
    guarded_callback,
    provider_accessed,
)
from legalforecast.ingestion.stage_a_replay_executor.journal import (
    JournalSpendMeter,
)
from legalforecast.ingestion.stage_a_replay_executor.lineage import (
    VerifiedReplayLineage,
    verify_replay_lineage,
)
from legalforecast.ingestion.stage_a_replay_executor.provider import (
    CanonicalProviderRuntime,
)
from legalforecast.ingestion.stage_a_replay_executor.receipts import (
    persist_plan,
    persist_terminal_evidence,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REPLAY_SPEC_SCHEMA_VERSION,
    REVIEWER_CONFIG_NAMESPACE,
    UNITIZER_CONFIG_NAMESPACE,
    ReplaySpec,
    ReplaySpendCeilingError,
    StageAReplayExecutorError,
    load_replay_spec,
)

Unitizer = Callable[[CandidateScopedStageARerunRequest], StageAStageOutcome]
Reviewer = Callable[
    [CandidateScopedStageARerunRequest, StageAStageOutcome], StageAStageOutcome
]
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class ReplayExecutionResult:
    """Minted replay objects plus the outer durable executor receipt."""

    spec_sha256: str
    plan: CandidateScopedStageAPlan | None
    execution: CandidateScopedStageAExecution | None
    stage_a_receipt: CandidateScopedStageAReceipt | None
    receipt_record: Mapping[str, object]
    halted: bool

    def to_record(self) -> dict[str, object]:
        return dict(self.receipt_record)


def current_code_commit(*, cwd: Path | None = None) -> str:
    """Return the exact checkout commit bound into an invocation."""

    checkout = cwd or repository_root()
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout:
            raise StageAReplayExecutorError(
                "runtime checkout is dirty; code commit cannot identify execution bytes"
            )
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        )
    except StageAReplayExecutorError:
        raise
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StageAReplayExecutorError(
            "cannot resolve the runtime code commit for replay receipt"
        ) from exc
    commit = completed.stdout.strip()
    if len(commit) not in range(40, 65) or any(
        char not in "0123456789abcdef" for char in commit
    ):
        raise StageAReplayExecutorError("runtime code commit is invalid")
    return commit


def execute_canonical_stage_a_replay(path: str | Path) -> ReplayExecutionResult:
    """Run the production path used by the sole CLI command."""

    spec = load_replay_spec(path)
    if spec.synthetic_fixture:
        raise StageAReplayExecutorError(
            "production replay-stage-a refuses synthetic fixture authority"
        )
    return execute_stage_a_replay(spec)


def execute_stage_a_replay(
    spec: ReplaySpec | str | Path,
    *,
    unitizer: Unitizer | None = None,
    reviewer: Reviewer | None = None,
    spend_meter: SpendMeter | None = None,
    code_commit: str | None = None,
    clock: Clock | None = None,
) -> ReplayExecutionResult:
    """Preflight, execute once, and persist terminal evidence for every outcome."""

    parsed = spec if isinstance(spec, ReplaySpec) else load_replay_spec(spec)
    if not parsed.synthetic_fixture and code_commit is not None:
        return _preflight_halt(
            parsed,
            "production execution forbids a caller-supplied code commit",
            failure_type="ProductionCodeCommitOverride",
        )
    runtime_commit = code_commit or current_code_commit()
    if runtime_commit != parsed.code_commit:
        return _preflight_halt(
            parsed,
            "runtime code commit differs from the code commit in replay-spec",
            failure_type="RuntimeCommitMismatch",
        )

    plan: CandidateScopedStageAPlan | None = None
    plan_persisted = False
    execution: CandidateScopedStageAExecution | None = None
    stage_a_receipt: CandidateScopedStageAReceipt | None = None
    lineage: VerifiedReplayLineage | None = None
    invocations: list[dict[str, object]] = []
    halt: Mapping[str, object] | None = None
    try:
        lineage = verify_replay_lineage(parsed)
        if lineage.unitizer_namespace != UNITIZER_CONFIG_NAMESPACE:
            raise ExecutionHalt(
                {
                    "status": "halted_on_preflight_failure",
                    "reason": "predecessor Stage A unitizer namespace is not frozen v5",
                    "failure_type": "StageAReplayExecutorError",
                }
            )
        if lineage.reviewer_namespace != REVIEWER_CONFIG_NAMESPACE:
            raise ExecutionHalt(
                {
                    "status": "halted_on_preflight_failure",
                    "reason": "predecessor Stage A reviewer namespace is not frozen v4",
                    "failure_type": "StageAReplayExecutorError",
                }
            )
        predecessor = bind_predecessor_stage_a_lineage(
            candidates=lineage.predecessor,
            unitizer_namespace=lineage.unitizer_namespace,
            reviewer_namespace=lineage.reviewer_namespace,
            provider_caps_sha256=parsed.provider_caps_sha256,
            provider_journal_path=parsed.provider_journal_path,
            selection_sha256=lineage.predecessor_selection_sha256,
            materialization_sha256=lineage.predecessor_materialization_sha256,
            parser_sha256=lineage.predecessor_parser_sha256,
        )
        plan = plan_candidate_scoped_stage_a_replay(
            predecessor=predecessor,
            successor_packets=lineage.successor,
            successor_selection_sha256=lineage.successor_selection_sha256,
            successor_materialization_sha256=lineage.successor_materialization_sha256,
            successor_parser_sha256=lineage.successor_parser_sha256,
            unitizer_namespace=lineage.unitizer_namespace,
            reviewer_namespace=lineage.reviewer_namespace,
            provider_caps_sha256=parsed.provider_caps_sha256,
            provider_journal_path=parsed.provider_journal_path,
        )
        if len(plan.rerun_candidate_ids) != len(parsed.candidate_ids) or set(
            plan.rerun_candidate_ids
        ) != set(parsed.candidate_ids):
            raise StageAReplayExecutorError(
                "planned rerun candidates differ from signed authorization"
            )
        lineage.require_unchanged()
        persist_plan(parsed, plan)
        plan_persisted = True
        unitizer, reviewer, spend_meter = _callbacks(
            parsed,
            lineage,
            unitizer=unitizer,
            reviewer=reviewer,
            spend_meter=spend_meter,
        )
        aggregate_spent = Decimal("0")
        committed_by_call: dict[str, Decimal] = {}
        spent_by_candidate = {
            candidate_id: Decimal("0") for candidate_id in parsed.candidate_ids
        }

        def guarded_unitizer(
            request: CandidateScopedStageARerunRequest,
        ) -> StageAStageOutcome:
            nonlocal aggregate_spent
            outcome, aggregate_spent = guarded_callback(
                request,
                stage="unitizer",
                callback=unitizer,
                unitize=None,
                meter=spend_meter,
                spec=parsed,
                lineage=lineage,
                spent_by_candidate=spent_by_candidate,
                aggregate_spent=aggregate_spent,
                committed_by_call=committed_by_call,
                invocations=invocations,
                clock=clock,
            )
            return outcome

        def guarded_reviewer(
            request: CandidateScopedStageARerunRequest,
            unitize_outcome: StageAStageOutcome,
        ) -> StageAStageOutcome:
            nonlocal aggregate_spent
            outcome, aggregate_spent = guarded_callback(
                request,
                stage="reviewer",
                callback=reviewer,
                unitize=unitize_outcome,
                meter=spend_meter,
                spec=parsed,
                lineage=lineage,
                spent_by_candidate=spent_by_candidate,
                aggregate_spent=aggregate_spent,
                committed_by_call=committed_by_call,
                invocations=invocations,
                clock=clock,
            )
            return outcome

        execution = run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=guarded_unitizer,
            reviewer=guarded_reviewer,
            clock=clock,
        )
        lineage.require_unchanged()
        stage_a_receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    except ExecutionHalt as exc:
        halt = {"provider_accessed": provider_accessed(invocations), **exc.evidence}
    except ReplayOutputClaimError:
        raise
    except (CandidateScopedStageAReplayError, StageAReplayExecutorError) as exc:
        halt = _failure_evidence(
            "halted_on_validation_failure", exc, invocations=invocations
        )
    except Exception as exc:
        halt = _failure_evidence(
            "halted_on_provider_or_artifact_failure", exc, invocations=invocations
        )
    if not plan_persisted:
        plan = None
    receipt = persist_terminal_evidence(
        parsed,
        plan=plan,
        execution=execution,
        stage_a_receipt=stage_a_receipt,
        invocations=invocations,
        halt_evidence=halt,
        lineage_evidence=None if lineage is None else lineage.evidence,
        halted=halt is not None,
    )
    return ReplayExecutionResult(
        spec_sha256=parsed.spec_sha256,
        plan=plan,
        execution=execution,
        stage_a_receipt=stage_a_receipt,
        receipt_record=receipt,
        halted=halt is not None,
    )


def _callbacks(
    spec: ReplaySpec,
    lineage: VerifiedReplayLineage,
    *,
    unitizer: Unitizer | None,
    reviewer: Reviewer | None,
    spend_meter: SpendMeter | None,
) -> tuple[Unitizer, Reviewer, SpendMeter]:
    if spec.synthetic_fixture:
        if unitizer is None or reviewer is None or spend_meter is None:
            raise StageAReplayExecutorError(
                "synthetic execution requires fake callbacks and a fake spend meter"
            )
        return unitizer, reviewer, spend_meter
    if any(value is not None for value in (unitizer, reviewer, spend_meter)):
        raise StageAReplayExecutorError(
            "production execution forbids injected provider seams"
        )
    runtime = CanonicalProviderRuntime(spec, lineage)
    return runtime.unitizer, runtime.reviewer, JournalSpendMeter(runtime)


def _failure_evidence(
    status: str,
    error: Exception,
    *,
    invocations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "status": status,
        "reason": str(error),
        "failure_type": type(error).__name__,
        "provider_accessed": provider_accessed(invocations),
    }


def _preflight_halt(
    spec: ReplaySpec, reason: str, *, failure_type: str
) -> ReplayExecutionResult:
    evidence = {
        "status": "halted_on_preflight_failure",
        "reason": reason,
        "failure_type": failure_type,
        "provider_accessed": False,
    }
    receipt = persist_terminal_evidence(
        spec,
        plan=None,
        execution=None,
        stage_a_receipt=None,
        invocations=(),
        halt_evidence=evidence,
        lineage_evidence=None,
        halted=True,
    )
    return ReplayExecutionResult(
        spec_sha256=spec.spec_sha256,
        plan=None,
        execution=None,
        stage_a_receipt=None,
        receipt_record=receipt,
        halted=True,
    )


__all__ = [
    "REPLAY_SPEC_SCHEMA_VERSION",
    "ReplayExecutionResult",
    "ReplaySpec",
    "ReplaySpendCeilingError",
    "StageAReplayExecutorError",
    "current_code_commit",
    "execute_canonical_stage_a_replay",
    "execute_stage_a_replay",
    "load_replay_spec",
]

"""Authenticated candidate-scoped Stage A successor replay tests."""

from __future__ import annotations

import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.contracts import (
    CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
)
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    PLAN_SCHEMA_VERSION,
    RECEIPT_SCHEMA_VERSION,
    REVIEWER_NAMESPACE,
    UNITIZER_NAMESPACE,
    CandidatePacketInput,
    CandidateScopedStageAExecution,
    CandidateScopedStageAPlan,
    CandidateScopedStageAReceipt,
    CandidateScopedStageAReplayError,
    CandidateScopedStageARerunRequest,
    PacketDocument,
    ParserOutputIdentity,
    PredecessorCandidateStageA,
    PredecessorStageALineage,
    StageAStageOutcome,
    bind_predecessor_stage_a_lineage,
    packet_input_identity_sha256,
    plan_candidate_scoped_stage_a_replay,
    run_candidate_scoped_stage_a_replay,
    seal_candidate_scoped_stage_a_replay,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_CAPS = "d" * 64
_SELECTION = "e" * 64
_MATERIALIZATION = "f" * 64
_PARSER = "1" * 64
_SUCCESSOR_SELECTION = "2" * 64
_SUCCESSOR_MATERIALIZATION = "3" * 64
_SUCCESSOR_PARSER = "4" * 64


class _Clock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self) -> float:
        self._t += 0.05
        return self._t


def test_unchanged_packets_reuse_prior_stage_a_without_executor_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    predecessor = _lineage(tmp_path)
    plan = _plan(tmp_path, predecessor, successor_packets=_packets())
    calls: list[str] = []

    def forbidden(
        request: CandidateScopedStageARerunRequest, *_args: object
    ) -> StageAStageOutcome:
        calls.append(request.candidate_id)
        raise AssertionError("reuse must not invoke unitizer or reviewer")

    monkeypatch.setattr(
        "legalforecast.labeling.provider_journal.ProviderAttemptJournal.__init__",
        forbidden,
    )
    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=forbidden, reviewer=forbidden, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)

    assert calls == []
    assert plan.reused_candidate_ids == ("cand-a", "cand-b", "cand-c")
    assert plan.rerun_candidate_ids == ()
    assert [record["candidate_id"] for record in receipt.unitize_records] == [
        "cand-a",
        "cand-b",
        "cand-c",
    ]
    assert _prediction_units(receipt.unitize_records[0]) == _prediction_units(
        predecessor.candidates[0].unitize_record
    )
    assert all(timing.elapsed_ms == 0 for timing in receipt.timings)
    assert receipt.provider_journal_path == predecessor.provider_journal_path


def test_changed_packet_reruns_only_that_candidate(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    unitizer_calls: list[str] = []
    reviewer_calls: list[str] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        unitizer_calls.append(request.candidate_id)
        return _unitize_outcome(request, units=["rerun-unit"])

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        reviewer_calls.append(request.candidate_id)
        return _review_outcome(
            request, flags=[{"candidate_id": request.candidate_id, "flag": "ok"}]
        )

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)

    assert plan.reused_candidate_ids == ("cand-a", "cand-c")
    assert plan.rerun_candidate_ids == ("cand-b",)
    assert unitizer_calls == ["cand-b"]
    assert reviewer_calls == ["cand-b"]
    assert _prediction_units(receipt.unitize_records[0]) == _prediction_units(
        predecessor.candidates[0].unitize_record
    )
    assert _prediction_units(receipt.unitize_records[1]) == ["rerun-unit"]
    assert _prediction_units(receipt.unitize_records[2]) == _prediction_units(
        predecessor.candidates[2].unitize_record
    )
    assert any(
        dict(flag).get("flag") == "ok" and dict(flag).get("candidate_id") == "cand-b"
        for flag in receipt.review_flags
    )
    timing = next(item for item in receipt.timings if item.candidate_id == "cand-b")
    assert timing.disposition == "rerun"
    assert timing.elapsed_ms == 100
    assert timing.unitizer_elapsed_ms == 50
    assert timing.reviewer_elapsed_ms == 50


def test_subset_successor_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    with pytest.raises(
        CandidateScopedStageAReplayError,
        match="without subsetting or hand-authoring",
    ):
        _plan(tmp_path, predecessor, successor_packets=_packets()[:2])


def test_extra_successor_candidate_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    extra = [*_packets(), _packet("cand-d", digest=_DIGEST_A)]
    with pytest.raises(
        CandidateScopedStageAReplayError,
        match="without subsetting or hand-authoring",
    ):
        _plan(tmp_path, predecessor, successor_packets=extra)


def test_v5_v4_namespace_pair_is_required(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    with pytest.raises(
        CandidateScopedStageAReplayError, match="claim-ontology-v5/claim-ontology-v4"
    ):
        plan_candidate_scoped_stage_a_replay(
            predecessor=predecessor,
            successor_packets=_packets(),
            successor_selection_sha256=_SUCCESSOR_SELECTION,
            successor_materialization_sha256=_SUCCESSOR_MATERIALIZATION,
            successor_parser_sha256=_SUCCESSOR_PARSER,
            unitizer_namespace="claim-ontology-v4",
            reviewer_namespace="claim-ontology-v4",
            provider_caps_sha256=_CAPS,
            provider_journal_path=tmp_path / "provider.sqlite3",
        )


def test_shared_journal_and_caps_are_required(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    with pytest.raises(
        CandidateScopedStageAReplayError, match="shared predecessor caps"
    ):
        plan_candidate_scoped_stage_a_replay(
            predecessor=predecessor,
            successor_packets=_packets(),
            successor_selection_sha256=_SUCCESSOR_SELECTION,
            successor_materialization_sha256=_SUCCESSOR_MATERIALIZATION,
            successor_parser_sha256=_SUCCESSOR_PARSER,
            unitizer_namespace=UNITIZER_NAMESPACE,
            reviewer_namespace=REVIEWER_NAMESPACE,
            provider_caps_sha256="9" * 64,
            provider_journal_path=tmp_path / "provider.sqlite3",
        )
    with pytest.raises(
        CandidateScopedStageAReplayError, match="shared predecessor journal"
    ):
        plan_candidate_scoped_stage_a_replay(
            predecessor=predecessor,
            successor_packets=_packets(),
            successor_selection_sha256=_SUCCESSOR_SELECTION,
            successor_materialization_sha256=_SUCCESSOR_MATERIALIZATION,
            successor_parser_sha256=_SUCCESSOR_PARSER,
            unitizer_namespace=UNITIZER_NAMESPACE,
            reviewer_namespace=REVIEWER_NAMESPACE,
            provider_caps_sha256=_CAPS,
            provider_journal_path=tmp_path / "other-journal.sqlite3",
        )


def test_terminal_predecessor_is_not_retried_when_inputs_match(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path, terminal_ids=("cand-a",))
    plan = _plan(tmp_path, predecessor)
    calls: list[str] = []

    def spy(
        request: CandidateScopedStageARerunRequest, *_args: object
    ) -> StageAStageOutcome:
        calls.append(request.candidate_id)
        return _unitize_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=spy, reviewer=spy, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert calls == []
    assert plan.decisions[0].disposition == "reused"
    assert _prediction_units(receipt.unitize_records[0]) == []


def test_changed_terminal_candidate_is_rerun(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path, terminal_ids=("cand-b",))
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    calls: list[str] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        calls.append(f"unitize:{request.candidate_id}")
        return _unitize_outcome(request, units=["fresh"])

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        calls.append(f"review:{request.candidate_id}")
        return _review_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert calls == ["unitize:cand-b", "review:cand-b"]
    assert _prediction_units(receipt.unitize_records[1]) == ["fresh"]


def test_unknown_rerun_outcome_is_nonretryable_and_unsealed(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    unitizer_calls: list[str] = []
    reviewer_calls: list[str] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        unitizer_calls.append(request.candidate_id)
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=({"candidate_id": request.candidate_id, "prediction_units": []},),
            audit={"candidate_id": request.candidate_id, "status": "unknown"},
            status="unknown",
            request_sha256=request.request_sha256,
        )

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        reviewer_calls.append(request.candidate_id)
        return _review_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    assert unitizer_calls == ["cand-a"]
    assert reviewer_calls == []
    with pytest.raises(
        CandidateScopedStageAReplayError, match="unknown Stage A outcome"
    ):
        seal_candidate_scoped_stage_a_replay(plan, execution)
    with pytest.raises(CandidateScopedStageAReplayError, match="plan already executed"):
        run_candidate_scoped_stage_a_replay(
            plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
        )
    reminted = _plan(tmp_path, predecessor, successor_packets=successor)
    with pytest.raises(CandidateScopedStageAReplayError, match="plan already executed"):
        run_candidate_scoped_stage_a_replay(
            reminted, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
        )
    assert unitizer_calls == ["cand-a"]


def test_mutated_execution_payloads_cannot_seal(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=lambda request: _unitize_outcome(request, units=["fresh"]),
        reviewer=lambda request, _unitize: _review_outcome(request),
        clock=_Clock(),
    )
    record = execution.unitize_records[0]
    assert isinstance(record, dict)
    record["prediction_units"] = ["tampered"]
    with pytest.raises(
        CandidateScopedStageAReplayError, match="execution payloads changed"
    ):
        seal_candidate_scoped_stage_a_replay(plan, execution)


def test_outcome_record_candidate_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=({"candidate_id": "cand-b", "prediction_units": ["x"]},),
            audit={"candidate_id": request.candidate_id, "status": "settled"},
            status="settled",
            request_sha256=request.request_sha256,
        )

    with pytest.raises(
        CandidateScopedStageAReplayError, match="unitizer record candidate_id"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_outcome_audit_status_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=(
                {"candidate_id": request.candidate_id, "prediction_units": ["x"]},
            ),
            audit={"candidate_id": request.candidate_id, "status": "unknown"},
            status="settled",
            request_sha256=request.request_sha256,
        )

    with pytest.raises(
        CandidateScopedStageAReplayError, match="unitizer audit status differs"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_outcome_audit_missing_status_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=(
                {"candidate_id": request.candidate_id, "prediction_units": ["x"]},
            ),
            audit={"candidate_id": request.candidate_id},
            status="settled",
            request_sha256=request.request_sha256,
        )

    with pytest.raises(CandidateScopedStageAReplayError, match="unitizer audit lacks"):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_plan_and_receipt_constructors_are_sealed() -> None:
    with pytest.raises(CandidateScopedStageAReplayError, match="authenticated bind"):
        PredecessorStageALineage()
    with pytest.raises(CandidateScopedStageAReplayError, match="authenticated replay"):
        CandidateScopedStageAPlan()
    with pytest.raises(CandidateScopedStageAReplayError, match="authenticated replay"):
        CandidateScopedStageAExecution()
    with pytest.raises(CandidateScopedStageAReplayError, match="authenticated replay"):
        CandidateScopedStageAReceipt()
    with pytest.raises(CandidateScopedStageAReplayError, match="authenticated replay"):
        CandidateScopedStageARerunRequest()


def test_mutated_predecessor_payloads_cannot_run(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    plan = _plan(tmp_path, predecessor)
    original = plan.predecessor_candidates[0]
    object.__setattr__(
        plan,
        "predecessor_candidates",
        (
            PredecessorCandidateStageA(
                packet=original.packet,
                unitize_record={
                    "candidate_id": original.packet.candidate_id,
                    "prediction_units": ["tampered"],
                },
                unitize_audit=dict(original.unitize_audit),
                review_flags=original.review_flags,
                review_audit=dict(original.review_audit),
                unitizer_status=original.unitizer_status,
                reviewer_status=original.reviewer_status,
            ),
            *plan.predecessor_candidates[1:],
        ),
    )
    with pytest.raises(
        CandidateScopedStageAReplayError, match="predecessor payloads changed"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=_unitize_outcome,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_unknown_stops_later_rerun_callbacks(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    successor[2] = _packet("cand-c", digest=_DIGEST_B)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    unitizer_calls: list[str] = []
    reviewer_calls: list[str] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        unitizer_calls.append(request.candidate_id)
        if request.candidate_id == "cand-a":
            return StageAStageOutcome(
                candidate_id=request.candidate_id,
                records=(
                    {"candidate_id": request.candidate_id, "prediction_units": []},
                ),
                audit={"candidate_id": request.candidate_id, "status": "unknown"},
                status="unknown",
                request_sha256=request.request_sha256,
            )
        return _unitize_outcome(request)

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        reviewer_calls.append(request.candidate_id)
        return _review_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    assert unitizer_calls == ["cand-a"]
    assert reviewer_calls == []
    assert execution.statuses[2] == ("cand-c", "unknown", "unknown")
    with pytest.raises(
        CandidateScopedStageAReplayError, match="unknown Stage A outcome"
    ):
        seal_candidate_scoped_stage_a_replay(plan, execution)


def test_reviewer_cannot_mutate_retained_unitizer_outcome(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def reviewer(
        request: CandidateScopedStageARerunRequest, unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        envelope = unitize.records[0]
        audit = unitize.audit
        assert isinstance(envelope, dict)
        assert isinstance(audit, dict)
        envelope["prediction_units"] = ["mutated-by-reviewer"]
        audit["status"] = "unknown"
        return _review_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=lambda request: _unitize_outcome(request, units=["fresh"]),
        reviewer=reviewer,
        clock=_Clock(),
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert _prediction_units(receipt.unitize_records[0]) == ["fresh"]
    assert receipt.unitize_audits[0]["status"] == "settled"


def test_callbacks_bind_authenticated_rerun_request(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    seen: list[CandidateScopedStageARerunRequest] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        seen.append(request)
        return _unitize_outcome(request, units=["bound"])

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        assert request.request_sha256 == seen[0].request_sha256
        return _review_outcome(request)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    request = seen[0]
    assert request.candidate_id == "cand-b"
    assert request.packet_sha256 == plan.decisions[1].successor_packet_sha256
    assert request.plan_sha256 == plan.plan_sha256
    assert request.provider_caps_sha256 == _CAPS
    assert request.provider_journal_path == Path(
        os.path.abspath(tmp_path / "provider.sqlite3")
    )
    assert request.unitizer_namespace == UNITIZER_NAMESPACE
    assert request.reviewer_namespace == REVIEWER_NAMESPACE
    assert _prediction_units(receipt.unitize_records[1]) == ["bound"]


def test_outcome_request_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=(
                {"candidate_id": request.candidate_id, "prediction_units": ["x"]},
            ),
            audit={"candidate_id": request.candidate_id, "status": "settled"},
            status="settled",
            request_sha256="0" * 64,
        )

    with pytest.raises(CandidateScopedStageAReplayError, match="request digest"):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_terminal_unitizer_rerun_can_rebind_as_predecessor(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        if request.candidate_id != "cand-b":
            return _unitize_outcome(request)
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=({"candidate_id": request.candidate_id, "prediction_units": []},),
            audit={
                "candidate_id": request.candidate_id,
                "status": "terminal_escalation",
            },
            status="terminal_escalation",
            request_sha256=request.request_sha256,
        )

    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=unitizer,
        reviewer=lambda request, _unitize: _review_outcome(request),
        clock=_Clock(),
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    rebound = bind_predecessor_stage_a_lineage(
        candidates=tuple(
            PredecessorCandidateStageA(
                packet=packet,
                unitize_record=dict(receipt.unitize_records[index]),
                unitize_audit=dict(receipt.unitize_audits[index]),
                review_flags=tuple(
                    dict(flag)
                    for flag in receipt.review_flags
                    if dict(flag).get("candidate_id") == packet.candidate_id
                ),
                review_audit=dict(receipt.review_audits[index]),
                unitizer_status=execution.statuses[index][1],
                reviewer_status=execution.statuses[index][2],
            )
            for index, packet in enumerate(successor)
        ),
        unitizer_namespace=UNITIZER_NAMESPACE,
        reviewer_namespace=REVIEWER_NAMESPACE,
        provider_caps_sha256=_CAPS,
        provider_journal_path=tmp_path / "provider.sqlite3",
        selection_sha256=_SUCCESSOR_SELECTION,
        materialization_sha256=_SUCCESSOR_MATERIALIZATION,
        parser_sha256=_SUCCESSOR_PARSER,
    )
    assert rebound.candidates[1].unitizer_status == "terminal_escalation"
    assert rebound.candidates[1].reviewer_status == "terminal_escalation"
    assert rebound.candidates[1].review_audit["status"] == "terminal_escalation"


def test_live_stage_a_audit_statuses_can_bind(tmp_path: Path) -> None:
    packet = _packet("cand-a", digest=_DIGEST_A)
    lineage = bind_predecessor_stage_a_lineage(
        candidates=(
            PredecessorCandidateStageA(
                packet=packet,
                unitize_record={
                    "candidate_id": "cand-a",
                    "prediction_units": ["unit-a"],
                },
                unitize_audit={
                    "candidate_id": "cand-a",
                    "stage": "llm-unitize",
                    "status": "succeeded",
                },
                review_flags=({"candidate_id": "cand-a", "flag": "prior"},),
                review_audit={
                    "candidate_id": "cand-a",
                    "stage": "llm-review-stage-a",
                    "status": "passed",
                },
                unitizer_status="settled",
                reviewer_status="settled",
            ),
        ),
        unitizer_namespace=UNITIZER_NAMESPACE,
        reviewer_namespace=REVIEWER_NAMESPACE,
        provider_caps_sha256=_CAPS,
        provider_journal_path=tmp_path / "provider.sqlite3",
        selection_sha256=_SELECTION,
        materialization_sha256=_MATERIALIZATION,
        parser_sha256=_PARSER,
    )
    assert lineage.candidates[0].unitize_audit["status"] == "succeeded"
    assert lineage.candidates[0].review_audit["status"] == "passed"
    assert lineage.candidates[0].unitizer_status == "settled"


def test_unknown_predecessor_audit_cannot_bind(tmp_path: Path) -> None:
    packet = _packet("cand-a", digest=_DIGEST_A)
    with pytest.raises(
        CandidateScopedStageAReplayError, match="unknown and cannot bind"
    ):
        bind_predecessor_stage_a_lineage(
            candidates=(
                PredecessorCandidateStageA(
                    packet=packet,
                    unitize_record={
                        "candidate_id": "cand-a",
                        "prediction_units": ["unit-a"],
                    },
                    unitize_audit={"candidate_id": "cand-a", "status": "unknown"},
                    review_flags=(),
                    review_audit={"candidate_id": "cand-a", "status": "passed"},
                    unitizer_status="settled",
                    reviewer_status="settled",
                ),
            ),
            unitizer_namespace=UNITIZER_NAMESPACE,
            reviewer_namespace=REVIEWER_NAMESPACE,
            provider_caps_sha256=_CAPS,
            provider_journal_path=tmp_path / "provider.sqlite3",
            selection_sha256=_SELECTION,
            materialization_sha256=_MATERIALIZATION,
            parser_sha256=_PARSER,
        )


def test_live_audit_cannot_pair_with_terminal_replay_state(tmp_path: Path) -> None:
    packet = _packet("cand-a", digest=_DIGEST_A)
    with pytest.raises(
        CandidateScopedStageAReplayError,
        match="incompatible with replay terminal state",
    ):
        bind_predecessor_stage_a_lineage(
            candidates=(
                PredecessorCandidateStageA(
                    packet=packet,
                    unitize_record={"candidate_id": "cand-a", "prediction_units": []},
                    unitize_audit={"candidate_id": "cand-a", "status": "succeeded"},
                    review_flags=(),
                    review_audit={"candidate_id": "cand-a", "status": "passed"},
                    unitizer_status="terminal_escalation",
                    reviewer_status="terminal_escalation",
                ),
            ),
            unitizer_namespace=UNITIZER_NAMESPACE,
            reviewer_namespace=REVIEWER_NAMESPACE,
            provider_caps_sha256=_CAPS,
            provider_journal_path=tmp_path / "provider.sqlite3",
            selection_sha256=_SELECTION,
            materialization_sha256=_MATERIALIZATION,
            parser_sha256=_PARSER,
        )


def test_concurrent_runs_cannot_double_claim_a_plan(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    calls: list[str] = []
    errors: list[str] = []
    barrier = threading.Barrier(2)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        calls.append(request.candidate_id)
        return _unitize_outcome(request, units=["once"])

    def worker() -> None:
        barrier.wait()
        try:
            run_candidate_scoped_stage_a_replay(
                plan,
                unitizer=unitizer,
                reviewer=lambda request, _unitize: _review_outcome(request),
                clock=_Clock(),
            )
        except CandidateScopedStageAReplayError as exc:
            errors.append(str(exc))

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    second.start()
    first.join()
    second.join()
    assert calls == ["cand-a"]
    assert any("already executed" in message for message in errors)


def test_sealed_receipt_payloads_cannot_change(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=lambda request: _unitize_outcome(request, units=["fresh"]),
        reviewer=lambda request, _unitize: _review_outcome(request),
        clock=_Clock(),
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    frozen_record = cast(dict[str, object], receipt.unitize_records[0])
    with pytest.raises(TypeError):
        frozen_record["prediction_units"] = ["tampered"]
    record = receipt.to_record()
    assert record["receipt_sha256"] == receipt.receipt_sha256
    object.__setattr__(
        receipt,
        "unitize_records",
        (
            {"candidate_id": "cand-a", "prediction_units": ["tampered"]},
            *receipt.unitize_records[1:],
        ),
    )
    with pytest.raises(
        CandidateScopedStageAReplayError, match="receipt payloads changed"
    ):
        receipt.to_record()


def test_packet_identity_is_stable_and_role_sensitive() -> None:
    first = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_A))
    second = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_A))
    changed = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_B))
    assert first == second
    assert first != changed


def test_selection_record_must_match_packet_envelope() -> None:
    packet = _packet("cand-a", digest=_DIGEST_A)
    mismatched = CandidatePacketInput(
        candidate_id=packet.candidate_id,
        case_id=packet.case_id,
        selection_record={
            "candidate_id": "cand-b",
            "case_id": packet.case_id,
            "documents": [{"source_document_id": "doc-cand-a"}],
        },
        documents=packet.documents,
        parser_outputs=packet.parser_outputs,
    )
    with pytest.raises(
        CandidateScopedStageAReplayError, match="selection_record candidate_id"
    ):
        packet_input_identity_sha256(mismatched)


def test_outcome_record_case_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=request.candidate_id,
            records=(
                {
                    "candidate_id": request.candidate_id,
                    "case_id": "case-other",
                    "prediction_units": ["x"],
                },
            ),
            audit={"candidate_id": request.candidate_id, "status": "settled"},
            status="settled",
            request_sha256=request.request_sha256,
        )

    with pytest.raises(
        CandidateScopedStageAReplayError, match="unitizer record case_id"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda request, _unitize: _review_outcome(request),
            clock=_Clock(),
        )


def test_reviewer_flag_without_candidate_id_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def reviewer(
        request: CandidateScopedStageARerunRequest, _unitize: StageAStageOutcome
    ) -> StageAStageOutcome:
        return _review_outcome(request, flags=[{"flag": "ok"}])

    with pytest.raises(CandidateScopedStageAReplayError, match="reviewer record"):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=_unitize_outcome,
            reviewer=reviewer,
            clock=_Clock(),
        )


def test_terminal_unitizer_cannot_bind_settled_reviewer(tmp_path: Path) -> None:
    packet = _packet("cand-a", digest=_DIGEST_A)
    with pytest.raises(
        CandidateScopedStageAReplayError,
        match="reviewer status must match the terminal unitizer status",
    ):
        bind_predecessor_stage_a_lineage(
            candidates=(
                PredecessorCandidateStageA(
                    packet=packet,
                    unitize_record={"candidate_id": "cand-a", "prediction_units": []},
                    unitize_audit={
                        "candidate_id": "cand-a",
                        "status": "terminal_escalation",
                    },
                    review_flags=(),
                    review_audit={"candidate_id": "cand-a", "status": "passed"},
                    unitizer_status="terminal_escalation",
                    reviewer_status="settled",
                ),
            ),
            unitizer_namespace=UNITIZER_NAMESPACE,
            reviewer_namespace=REVIEWER_NAMESPACE,
            provider_caps_sha256=_CAPS,
            provider_journal_path=tmp_path / "provider.sqlite3",
            selection_sha256=_SELECTION,
            materialization_sha256=_MATERIALIZATION,
            parser_sha256=_PARSER,
        )


def test_contract_docs_are_linked() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = (root / "docs/schemas/candidate-scoped-stage-a-replay-v1.md").read_text(
        encoding="utf-8"
    )
    index = (root / "docs/README.md").read_text(encoding="utf-8")
    module_map = (root / "docs/ingestion-module-map.md").read_text(encoding="utf-8")
    assert str(CANDIDATE_SCOPED_STAGE_A_REPLAY_V1) in contract
    assert str(CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1) in contract
    assert PLAN_SCHEMA_VERSION in contract
    assert RECEIPT_SCHEMA_VERSION in contract
    assert "claim-ontology-v5" in contract
    assert "claim-ontology-v4" in contract
    assert (
        "[candidate-scoped-stage-a-replay-v1.md]"
        "(schemas/candidate-scoped-stage-a-replay-v1.md)" in index
    )
    assert "`candidate_scoped_stage_a_replay.py`" in module_map


def test_sealed_receipt_binds_successor_lineage_and_shared_journal(
    tmp_path: Path,
) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[2] = _packet("cand-c", digest=_DIGEST_B)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=lambda request: _unitize_outcome(request, units=["c"]),
        reviewer=lambda request, _unitize: _review_outcome(request),
        clock=_Clock(),
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert receipt.successor_selection_sha256 == _SUCCESSOR_SELECTION
    assert receipt.successor_materialization_sha256 == _SUCCESSOR_MATERIALIZATION
    assert receipt.successor_parser_sha256 == _SUCCESSOR_PARSER
    assert receipt.unitizer_namespace == UNITIZER_NAMESPACE
    assert receipt.reviewer_namespace == REVIEWER_NAMESPACE
    assert receipt.provider_caps_sha256 == _CAPS
    assert receipt.candidate_ids == ("cand-a", "cand-b", "cand-c")
    assert len(receipt.timings) == 3
    record = receipt.to_record()
    assert record["schema_version"] == RECEIPT_SCHEMA_VERSION
    assert record["receipt_sha256"] == receipt.receipt_sha256


def _plan(
    tmp_path: Path,
    predecessor: PredecessorStageALineage,
    *,
    successor_packets: list[CandidatePacketInput] | None = None,
) -> CandidateScopedStageAPlan:
    return plan_candidate_scoped_stage_a_replay(
        predecessor=predecessor,
        successor_packets=successor_packets or _packets(),
        successor_selection_sha256=_SUCCESSOR_SELECTION,
        successor_materialization_sha256=_SUCCESSOR_MATERIALIZATION,
        successor_parser_sha256=_SUCCESSOR_PARSER,
        unitizer_namespace=UNITIZER_NAMESPACE,
        reviewer_namespace=REVIEWER_NAMESPACE,
        provider_caps_sha256=_CAPS,
        provider_journal_path=tmp_path / "provider.sqlite3",
    )


def _lineage(
    tmp_path: Path, *, terminal_ids: tuple[str, ...] = ()
) -> PredecessorStageALineage:
    candidates: list[PredecessorCandidateStageA] = []
    for candidate_id, digest in (
        ("cand-a", _DIGEST_A),
        ("cand-b", _DIGEST_B),
        ("cand-c", _DIGEST_C),
    ):
        terminal = candidate_id in terminal_ids
        packet = _packet(candidate_id, digest=digest)
        candidates.append(
            PredecessorCandidateStageA(
                packet=packet,
                unitize_record={
                    "candidate_id": candidate_id,
                    "prediction_units": [] if terminal else [f"unit-{candidate_id}"],
                },
                unitize_audit={
                    "candidate_id": candidate_id,
                    "status": "terminal_escalation" if terminal else "settled",
                },
                review_flags=()
                if terminal
                else ({"candidate_id": candidate_id, "flag": "prior"},),
                review_audit={
                    "candidate_id": candidate_id,
                    "status": "terminal_escalation" if terminal else "settled",
                },
                unitizer_status="terminal_escalation" if terminal else "settled",
                reviewer_status="terminal_escalation" if terminal else "settled",
            )
        )
    return bind_predecessor_stage_a_lineage(
        candidates=tuple(candidates),
        unitizer_namespace=UNITIZER_NAMESPACE,
        reviewer_namespace=REVIEWER_NAMESPACE,
        provider_caps_sha256=_CAPS,
        provider_journal_path=tmp_path / "provider.sqlite3",
        selection_sha256=_SELECTION,
        materialization_sha256=_MATERIALIZATION,
        parser_sha256=_PARSER,
    )


def _packets() -> list[CandidatePacketInput]:
    return [
        _packet("cand-a", digest=_DIGEST_A),
        _packet("cand-b", digest=_DIGEST_B),
        _packet("cand-c", digest=_DIGEST_C),
    ]


def _packet(candidate_id: str, *, digest: str) -> CandidatePacketInput:
    document_id = f"doc-{candidate_id}"
    suffix = candidate_id.rsplit("-", 1)[-1]
    return CandidatePacketInput(
        candidate_id=candidate_id,
        case_id=f"case-{suffix}",
        selection_record={
            "candidate_id": candidate_id,
            "case_id": f"case-{suffix}",
            "documents": [{"source_document_id": document_id}],
        },
        documents=(
            PacketDocument(
                source_document_id=document_id,
                document_role="motion_to_dismiss_memorandum",
                sha256=digest,
                byte_count=12,
            ),
        ),
        parser_outputs=(
            ParserOutputIdentity(
                source_document_id=document_id,
                markdown_sha256=digest,
                parser_reuse_identity_sha256=digest,
            ),
        ),
    )


def _prediction_units(record: Mapping[str, object]) -> list[object]:
    units = record["prediction_units"]
    if isinstance(units, list):
        return list(cast(list[object], units))
    if isinstance(units, tuple):
        return list(cast(tuple[object, ...], units))
    raise AssertionError("prediction_units is not a sequence")


def _unitize_outcome(
    request: CandidateScopedStageARerunRequest, *, units: list[str] | None = None
) -> StageAStageOutcome:
    candidate_id = request.candidate_id
    return StageAStageOutcome(
        candidate_id=candidate_id,
        records=(
            {
                "candidate_id": candidate_id,
                "prediction_units": list(units or [f"new-{candidate_id}"]),
            },
        ),
        audit={"candidate_id": candidate_id, "status": "settled"},
        status="settled",
        request_sha256=request.request_sha256,
    )


def _review_outcome(
    request: CandidateScopedStageARerunRequest,
    *,
    flags: list[Mapping[str, object]] | None = None,
) -> StageAStageOutcome:
    candidate_id = request.candidate_id
    return StageAStageOutcome(
        candidate_id=candidate_id,
        records=tuple(flags or ({"candidate_id": candidate_id, "flag": "none"},)),
        audit={"candidate_id": candidate_id, "status": "settled"},
        status="settled",
        request_sha256=request.request_sha256,
    )

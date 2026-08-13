"""Authenticated candidate-scoped Stage A successor replay tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

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

    def forbidden(candidate_id: str, *_args: object) -> StageAStageOutcome:
        calls.append(candidate_id)
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
    assert receipt.unitize_records[0] == predecessor.candidates[0].unitize_record
    assert all(timing.elapsed_ms == 0 for timing in receipt.timings)
    assert receipt.provider_journal_path == predecessor.provider_journal_path


def test_changed_packet_reruns_only_that_candidate(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    unitizer_calls: list[str] = []
    reviewer_calls: list[str] = []

    def unitizer(candidate_id: str) -> StageAStageOutcome:
        unitizer_calls.append(candidate_id)
        return _unitize_outcome(candidate_id, units=["rerun-unit"])

    def reviewer(candidate_id: str, _unitize: StageAStageOutcome) -> StageAStageOutcome:
        reviewer_calls.append(candidate_id)
        return _review_outcome(candidate_id, flags=[{"flag": "ok"}])

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)

    assert plan.reused_candidate_ids == ("cand-a", "cand-c")
    assert plan.rerun_candidate_ids == ("cand-b",)
    assert unitizer_calls == ["cand-b"]
    assert reviewer_calls == ["cand-b"]
    assert receipt.unitize_records[0] == predecessor.candidates[0].unitize_record
    assert receipt.unitize_records[1]["prediction_units"] == ["rerun-unit"]
    assert receipt.unitize_records[2] == predecessor.candidates[2].unitize_record
    assert {"flag": "ok"} in [dict(flag) for flag in receipt.review_flags]
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

    def spy(candidate_id: str, *_args: object) -> StageAStageOutcome:
        calls.append(candidate_id)
        return _unitize_outcome(candidate_id)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=spy, reviewer=spy, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert calls == []
    assert plan.decisions[0].disposition == "reused"
    assert receipt.unitize_records[0]["prediction_units"] == []


def test_changed_terminal_candidate_is_rerun(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path, terminal_ids=("cand-b",))
    successor = _packets()
    successor[1] = _packet("cand-b", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    calls: list[str] = []

    def unitizer(candidate_id: str) -> StageAStageOutcome:
        calls.append(f"unitize:{candidate_id}")
        return _unitize_outcome(candidate_id, units=["fresh"])

    def reviewer(candidate_id: str, _unitize: StageAStageOutcome) -> StageAStageOutcome:
        calls.append(f"review:{candidate_id}")
        return _review_outcome(candidate_id)

    execution = run_candidate_scoped_stage_a_replay(
        plan, unitizer=unitizer, reviewer=reviewer, clock=_Clock()
    )
    receipt = seal_candidate_scoped_stage_a_replay(plan, execution)
    assert calls == ["unitize:cand-b", "review:cand-b"]
    assert receipt.unitize_records[1]["prediction_units"] == ["fresh"]


def test_unknown_rerun_outcome_is_nonretryable_and_unsealed(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    unitizer_calls: list[str] = []
    reviewer_calls: list[str] = []

    def unitizer(candidate_id: str) -> StageAStageOutcome:
        unitizer_calls.append(candidate_id)
        return StageAStageOutcome(
            candidate_id=candidate_id,
            records=({"candidate_id": candidate_id, "prediction_units": []},),
            audit={"candidate_id": candidate_id, "status": "unknown"},
            status="unknown",
        )

    def reviewer(candidate_id: str, _unitize: StageAStageOutcome) -> StageAStageOutcome:
        reviewer_calls.append(candidate_id)
        return _review_outcome(candidate_id)

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
    assert unitizer_calls == ["cand-a"]


def test_mutated_execution_payloads_cannot_seal(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)
    execution = run_candidate_scoped_stage_a_replay(
        plan,
        unitizer=lambda candidate_id: _unitize_outcome(candidate_id, units=["fresh"]),
        reviewer=lambda candidate_id, _unitize: _review_outcome(candidate_id),
        clock=_Clock(),
    )
    dict(execution.unitize_records[0])  # mapping is the stored dict
    execution.unitize_records[0]["prediction_units"] = ["tampered"]
    with pytest.raises(
        CandidateScopedStageAReplayError, match="execution payloads changed"
    ):
        seal_candidate_scoped_stage_a_replay(plan, execution)


def test_outcome_record_candidate_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(candidate_id: str) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=candidate_id,
            records=({"candidate_id": "cand-b", "prediction_units": ["x"]},),
            audit={"candidate_id": candidate_id, "status": "settled"},
            status="settled",
        )

    with pytest.raises(
        CandidateScopedStageAReplayError, match="unitizer record candidate_id"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda candidate_id, _unitize: _review_outcome(candidate_id),
            clock=_Clock(),
        )


def test_outcome_audit_status_mismatch_is_rejected(tmp_path: Path) -> None:
    predecessor = _lineage(tmp_path)
    successor = _packets()
    successor[0] = _packet("cand-a", digest=_DIGEST_C)
    plan = _plan(tmp_path, predecessor, successor_packets=successor)

    def unitizer(candidate_id: str) -> StageAStageOutcome:
        return StageAStageOutcome(
            candidate_id=candidate_id,
            records=({"candidate_id": candidate_id, "prediction_units": ["x"]},),
            audit={"candidate_id": candidate_id, "status": "unknown"},
            status="settled",
        )

    with pytest.raises(
        CandidateScopedStageAReplayError, match="unitizer audit status differs"
    ):
        run_candidate_scoped_stage_a_replay(
            plan,
            unitizer=unitizer,
            reviewer=lambda candidate_id, _unitize: _review_outcome(candidate_id),
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


def test_packet_identity_is_stable_and_role_sensitive() -> None:
    first = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_A))
    second = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_A))
    changed = packet_input_identity_sha256(_packet("cand-a", digest=_DIGEST_B))
    assert first == second
    assert first != changed


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
        unitizer=lambda candidate_id: _unitize_outcome(candidate_id, units=["c"]),
        reviewer=lambda candidate_id, _unitize: _review_outcome(candidate_id),
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
    candidates = []
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


def _unitize_outcome(
    candidate_id: str, *, units: list[str] | None = None
) -> StageAStageOutcome:
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
    )


def _review_outcome(
    candidate_id: str, *, flags: list[Mapping[str, object]] | None = None
) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=candidate_id,
        records=tuple(flags or ({"candidate_id": candidate_id, "flag": "none"},)),
        audit={"candidate_id": candidate_id, "status": "settled"},
        status="settled",
    )

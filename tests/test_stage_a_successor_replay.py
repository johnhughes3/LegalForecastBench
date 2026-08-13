"""Authenticated candidate-scoped Stage A successor replay tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    STAGE_A_SUCCESSOR_REPLAY_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
)
from legalforecast.ingestion.stage_a_successor_replay import (
    REVIEWER_NAMESPACE,
    UNITIZER_NAMESPACE,
    StageAStageOutcome,
    StageASuccessorReplay,
    StageASuccessorReplayError,
    bind_stage_a_successor_replay,
    run_stage_a_successor_replay,
)
from legalforecast.ingestion.successor_rerun_impact import SuccessorRerunImpact

_COHORT = ("candidate-a", "candidate-b", "candidate-c")
_DIGEST = "a" * 64


def test_bind_keeps_full_cohort_and_routes_only_affected_candidates() -> None:
    replay = _bind()

    assert replay.predecessor_candidate_ids == _COHORT
    assert replay.successor_candidate_ids == _COHORT
    assert replay.affected_candidate_ids == ("candidate-b",)
    assert replay.reusable_candidate_ids == ("candidate-a", "candidate-c")
    assert replay.unitizer_namespace == UNITIZER_NAMESPACE
    assert replay.reviewer_namespace == REVIEWER_NAMESPACE
    assert replay.provider_activity_requested is True
    assert replay.provider_activity_executed is False
    assert replay.content_record()["authority"] == {
        "artifact": False,
        "dispatch": False,
        "execution": False,
        "freeze": False,
        "provider": False,
        "publication": False,
        "purchase": False,
    }
    assert replay.replay_sha256 == str(
        ARTIFACT_RAW_SHA256_V1.commit(
            replay.content_record(), domain=STAGE_A_SUCCESSOR_REPLAY_V1
        ).digest
    )


def test_bind_rejects_a_subset_successor_lineage() -> None:
    with pytest.raises(
        StageASuccessorReplayError,
        match="exact predecessor cohort",
    ):
        _bind(successor_candidate_ids=("candidate-b",))


def test_bind_rejects_reordered_or_hand_authored_cohort() -> None:
    with pytest.raises(
        StageASuccessorReplayError,
        match="exact predecessor cohort",
    ):
        _bind(successor_candidate_ids=("candidate-c", "candidate-a", "candidate-b"))


def test_bind_rejects_wrong_stage_a_namespace_pair() -> None:
    with pytest.raises(StageASuccessorReplayError, match="claim-ontology-v5 unitizer"):
        _bind(
            impact=_impact(namespace="claim-ontology-v4"),
            unitizer_namespace="claim-ontology-v4",
        )
    with pytest.raises(StageASuccessorReplayError, match="claim-ontology-v4 reviewer"):
        _bind(reviewer_namespace="claim-ontology-v5")


def test_bind_rejects_failed_or_incomplete_impact() -> None:
    with pytest.raises(StageASuccessorReplayError, match="not successful"):
        _bind(impact=_impact(ok=False))
    with pytest.raises(StageASuccessorReplayError, match="cover the full"):
        _bind(impact=_impact(reusable=("candidate-a",)))


def test_constructor_is_not_a_public_factory() -> None:
    with pytest.raises(StageASuccessorReplayError, match="authenticated binding"):
        StageASuccessorReplay()


def test_schema_doc_names_the_closed_contract() -> None:
    contract = Path("docs/schemas/stage-a-successor-replay-v1.md").read_text(
        encoding="utf-8"
    )
    assert "legalforecast.stage_a_successor_replay.v1" in contract
    assert "claim-ontology-v5" in contract
    assert "claim-ontology-v4" in contract
    assert "exact predecessor cohort" in contract or "full" in contract


def test_run_reuses_unaffected_outputs_and_executes_only_affected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replay = _bind()
    called: list[tuple[str, str]] = []

    def unitize(candidate_id: str) -> StageAStageOutcome:
        called.append(("unitize", candidate_id))
        return _outcome(candidate_id, stage="unitizer", retry_count=1)

    def review(candidate_id: str) -> StageAStageOutcome:
        called.append(("review", candidate_id))
        return _outcome(candidate_id, stage="reviewer", retry_count=0)

    monkeypatch.setattr(
        "legalforecast.labeling.provider_journal.ProviderAttemptJournal.__init__",
        _forbidden,
    )

    receipt = run_stage_a_successor_replay(
        replay=replay,
        prior_unitizer_records=_prior_records("unitizer"),
        prior_reviewer_records=_prior_records("reviewer"),
        unitize=unitize,
        review=review,
        monotonic=_clock((1.0, 1.5, 2.0, 3.0)),
    )

    assert called == [("unitize", "candidate-b"), ("review", "candidate-b")]
    assert [record["candidate_id"] for record in receipt.unitizer_records] == list(
        _COHORT
    )
    assert [record["source"] for record in receipt.unitizer_records] == [
        "prior-unitizer",
        "fresh-unitizer",
        "prior-unitizer",
    ]
    assert [row["disposition"] for row in receipt.candidates] == [
        "reused",
        "executed",
        "reused",
    ]
    executed = receipt.candidates[1]
    assert executed["unitizer_duration_seconds"] == "0.5"
    assert executed["reviewer_duration_seconds"] == "1.0"
    assert executed["retry_count"] == 1
    assert receipt.provider_activity_executed is True
    assert receipt.receipt_sha256 == str(
        ARTIFACT_RAW_SHA256_V1.commit(
            receipt.content_record(), domain=STAGE_A_SUCCESSOR_REPLAY_V1
        ).digest
    )


def test_run_fails_closed_when_a_reusable_prior_record_is_missing() -> None:
    replay = _bind()
    prior_unitizer = _prior_records("unitizer")
    del prior_unitizer["candidate-c"]
    with pytest.raises(StageASuccessorReplayError, match="unitizer record is missing"):
        run_stage_a_successor_replay(
            replay=replay,
            prior_unitizer_records=prior_unitizer,
            prior_reviewer_records=_prior_records("reviewer"),
            unitize=lambda candidate_id: _outcome(candidate_id, stage="unitizer"),
            review=lambda candidate_id: _outcome(candidate_id, stage="reviewer"),
            monotonic=_clock((0.0, 0.1, 0.2, 0.3)),
        )


def test_run_rejects_a_callback_that_returns_the_wrong_candidate() -> None:
    replay = _bind()
    with pytest.raises(StageASuccessorReplayError, match="unitizer outcome candidate"):
        run_stage_a_successor_replay(
            replay=replay,
            prior_unitizer_records=_prior_records("unitizer"),
            prior_reviewer_records=_prior_records("reviewer"),
            unitize=lambda _candidate_id: _outcome("candidate-a", stage="unitizer"),
            review=lambda candidate_id: _outcome(candidate_id, stage="reviewer"),
            monotonic=_clock((0.0, 0.1, 0.2, 0.3)),
        )


def _bind(
    *,
    impact: SuccessorRerunImpact | None = None,
    successor_candidate_ids: Sequence[str] = _COHORT,
    unitizer_namespace: str = UNITIZER_NAMESPACE,
    reviewer_namespace: str = REVIEWER_NAMESPACE,
) -> Any:
    return bind_stage_a_successor_replay(
        impact=impact or _impact(),
        predecessor_candidate_ids=_COHORT,
        successor_candidate_ids=successor_candidate_ids,
        predecessor_selection_sha256=_DIGEST,
        successor_selection_sha256="b" * 64,
        successor_materialization_sha256="c" * 64,
        successor_parser_sha256="d" * 64,
        provider_journal_sha256="e" * 64,
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
    )


def _impact(
    *,
    ok: bool = True,
    namespace: str = UNITIZER_NAMESPACE,
    reusable: Sequence[str] = ("candidate-a", "candidate-c"),
) -> SuccessorRerunImpact:
    record: dict[str, object] = {
        "schema_version": str(SUCCESSOR_RERUN_IMPACT_V1),
        "advisory": ok,
        "authority": {
            "artifact": False,
            "dispatch": False,
            "execution": False,
            "freeze": False,
            "provider": False,
            "publication": False,
            "purchase": False,
        },
        "warning": "ADVISORY ONLY",
        "cycle_id": "cycle-1",
        "proposal_sha256": "f" * 64,
        "proposed_global_commitments": {
            "model_key": "openai:unitizer",
            "model_provider": "openai",
            "model_registry_sha256": "1" * 64,
            "policy_sha256": "2" * 64,
            "provider_account": "primary",
            "provider_attempt_namespace": namespace,
        },
        "first_invalidated_stage": "parse-documents",
        "stages": [
            {"stage": "selection", "status": "REUSABLE"},
            {"stage": "parse-documents", "status": "AFFECTED"},
            {"stage": "llm-unitize", "status": "AFFECTED" if ok else "FAILED"},
        ],
        "affected_cases": ["case-b"],
        "affected_candidates": ["candidate-b"],
        "affected_documents": ["candidate-b/document-b"],
        "reusable_documents": ["candidate-a/document-a", "candidate-c/document-c"],
        "reusable_parser_outputs": [],
        "reusable_exact_byte_output_count": 2,
        "reusable_logical_calls": [
            {
                "candidate_id": candidate_id,
                "logical_call_key": f"call-{candidate_id}",
                "attempt_ordinal": 1,
            }
            for candidate_id in reusable
        ],
        "provider_logical_call_gaps": [
            {"candidate_id": "candidate-b", "reason": "candidate_inputs_changed"}
        ],
        "next_commands": [],
    }
    if not ok:
        record["stages"] = [
            {
                "stage": "selection",
                "status": "FAILED",
                "diagnostics": [{"code": "x", "message": "failed"}],
            }
        ]
    return SuccessorRerunImpact(record=record)


def _prior_records(stage: str) -> dict[str, dict[str, object]]:
    return {
        candidate_id: {
            "candidate_id": candidate_id,
            "source": f"prior-{stage}",
        }
        for candidate_id in ("candidate-a", "candidate-c")
    }


def _outcome(
    candidate_id: str, *, stage: str, retry_count: int = 0
) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=candidate_id,
        record={"candidate_id": candidate_id, "source": f"fresh-{stage}"},
        retry_count=retry_count,
    )


def _clock(values: Sequence[float]) -> Any:
    remaining = list(values)

    def monotonic() -> float:
        return remaining.pop(0)

    return monotonic


def _forbidden(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("replay constructed a provider journal")

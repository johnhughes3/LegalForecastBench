from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    FINALIZED_SCHEMA_VERSION,
    UnitizationReviewError,
    apply_unitization_reviews,
    verify_finalized_prediction_units,
)


def test_apply_unitization_reviews_supports_every_disposition() -> None:
    raw = [
        _candidate("accept", [_unit("a")]),
        _candidate("amend", [_unit("a")]),
        _candidate("split", [_unit("a")]),
        _candidate("merge", [_unit("a"), _unit("b")]),
        _candidate("exclude", [_unit("a")]),
    ]
    queue = [
        _review("accept", "a"),
        _review("amend", "a"),
        _review("split", "a"),
        _review("merge", "a"),
        _review("merge", "b"),
        _review("exclude", "a"),
    ]
    adjudications = [
        _adjudication("accept", "ACCEPT", ["a"]),
        _adjudication("amend", "AMEND", ["a"], [_unit("a-amended")]),
        _adjudication("split", "SPLIT", ["a"], [_unit("a-1"), _unit("a-2")]),
        _adjudication("merge", "MERGE", ["a", "b"], [_unit("ab")]),
        _adjudication(
            "exclude",
            "CANDIDATE-EXCLUSION",
            ["a"],
            exclusion_reason="stage_a_boundary_unresolvable",
        ),
    ]

    result = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )

    by_candidate = {record["candidate_id"]: record for record in result}
    assert {unit["unit_id"] for unit in by_candidate["split"]["prediction_units"]} == {
        "a-1",
        "a-2",
    }
    assert [unit["unit_id"] for unit in by_candidate["merge"]["prediction_units"]] == [
        "ab"
    ]
    assert by_candidate["exclude"]["status"] == "candidate_excluded"
    assert by_candidate["exclude"]["prediction_units"] == []
    assert all(
        record["schema_version"] == FINALIZED_SCHEMA_VERSION for record in result
    )
    verify_finalized_prediction_units(result, raw, adjudications)


def test_finalized_chain_rejects_raw_bypass_and_hash_mutation() -> None:
    raw = [_candidate("amend", [_unit("a")])]
    adjudications = [_adjudication("amend", "AMEND", ["a"], [_unit("a-amended")])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[_review("amend", "a")],
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["prediction_units"][0]["source_unit_sha256s"] = ["0" * 64]

    with pytest.raises(UnitizationReviewError, match="broken source-unit hash link"):
        verify_finalized_prediction_units([broken], raw, adjudications)
    with pytest.raises(UnitizationReviewError, match="raw or unsupported"):
        verify_finalized_prediction_units(raw, raw, adjudications)


def test_apply_unitization_reviews_requires_complete_queue_drain() -> None:
    with pytest.raises(UnitizationReviewError, match="unresolved reviews"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[],
        )


def test_candidate_exclusion_must_consume_whole_candidate() -> None:
    with pytest.raises(UnitizationReviewError, match="must consume every unit"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a"), _unit("b")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[
                _adjudication(
                    "cand",
                    "CANDIDATE-EXCLUSION",
                    ["a"],
                    exclusion_reason="unresolvable",
                )
            ],
        )


def test_apply_unitization_review_cli_writes_finalized_artifact(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.jsonl"
    queue_path = tmp_path / "queue.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    output_root = tmp_path / "out"
    _write_jsonl(raw_path, [_candidate("cand", [_unit("a")])])
    _write_jsonl(queue_path, [_review("cand", "a")])
    _write_jsonl(adjudications_path, [_adjudication("cand", "ACCEPT", ["a"])])

    assert (
        main(
            [
                "acquisition",
                "apply-unitization-review",
                "--prediction-units",
                str(raw_path),
                "--unitization-review-queue",
                str(queue_path),
                "--adjudications",
                str(adjudications_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    record = json.loads(
        (output_root / "finalized-prediction-units.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert record["schema_version"] == FINALIZED_SCHEMA_VERSION
    assert record["prediction_units"][0]["adjudication_id"] == "adj-cand"


def _candidate(candidate_id: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "prediction_units": units,
    }


def _review(candidate_id: str, unit_id: str) -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "unit_id": unit_id,
        "review_id": f"{candidate_id}:{unit_id}:stage-a-review",
        "route_reason": "fixture",
    }


def _adjudication(
    candidate_id: str,
    disposition: str,
    source_unit_ids: list[str],
    finalized_units: list[dict[str, Any]] | None = None,
    *,
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": f"adj-{candidate_id}",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "review_ids": [
            f"{candidate_id}:{unit_id}:stage-a-review" for unit_id in source_unit_ids
        ],
        "source_unit_ids": source_unit_ids,
        "disposition": disposition,
        "finalized_units": finalized_units or [],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Reviewed against blinded predecision materials.",
    }
    if exclusion_reason is not None:
        record["exclusion_reason"] = exclusion_reason
    return record


def _unit(unit_id: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [{"document_id": "complaint", "page": 1}],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

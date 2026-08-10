"""Regression tests for the read-only Stage A adjudication preflight.

The preflight rehearses ``apply_unitization_reviews`` over proposed
adjudications and prints a private grouped worklist plus a
claim-defendant matrix. These tests pin three properties: the report is
derived from the applicator's validated output (so it can never disagree
with apply), the optional finalized artifact is held to byte-level
equality with the recomputation, and the CLI writes nothing on any path.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.unitization.adjudication_preflight import (
    ADJUDICATION_PREFLIGHT_REPORT_SCHEMA_VERSION,
    AdjudicationPreflightError,
    build_adjudication_preflight_report,
)
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION,
    UnitizationReviewError,
    apply_unitization_reviews,
    canonical_sha256,
)

_COMMITMENTS = {
    "raw_prediction_units": {"path": "/private/raw.jsonl", "sha256": "sha256:raw"},
    "unitization_review_queue": {
        "path": "/private/queue.jsonl",
        "sha256": "sha256:queue",
    },
    "adjudications": {"path": "/private/adjudications.jsonl", "sha256": "sha256:adj"},
}


def _unit(
    unit_id: str,
    *,
    claim_name: str | None = None,
    defendant_group: str = "Defendant",
    challenged_by_motion: bool = True,
    challenge_scope: str = "entire_claim",
    documents: tuple[str, ...] = ("complaint",),
) -> dict[str, Any]:
    unclear = challenge_scope == "unclear"
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": claim_name if claim_name is not None else f"Claim {unit_id}",
        "defendant_group": defendant_group,
        "challenged_by_motion": challenged_by_motion,
        "challenge_scope": challenge_scope,
        "unit_confidence": 0.9,
        "source_citations": [
            {
                "document_id": document_id,
                "docket_entry_number": None,
                "page": 1,
                "paragraph": None,
                "excerpt": None,
            }
            for document_id in documents
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": "Scope is ambiguous in the motion." if unclear else None,
        "should_score": challenged_by_motion and not unclear,
    }


def _candidate(candidate_id: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "prediction_units": units,
    }


def _review(
    raw_record: dict[str, Any],
    unit_id: str,
    *,
    route: str = "structural_spurious",
) -> dict[str, Any]:
    candidate_id = raw_record["candidate_id"]
    return {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": candidate_id,
        "case_id": raw_record["case_id"],
        "unit_id": unit_id,
        "review_id": f"{candidate_id}:{unit_id}:{route}",
        "route_reason": route,
        "review_item": {
            "unit_id": unit_id,
            "reason": route,
            "notes": "Review against the cited pleadings.",
            "source_document_ids": ["complaint"],
        },
        "structural_flag_sha256": canonical_sha256({"flag": f"{unit_id}:{route}"}),
        "raw_prediction_units_sha256": canonical_sha256(raw_record),
    }


def _omission_review(raw_record: dict[str, Any], unit_id: str) -> dict[str, Any]:
    review = _review(raw_record, unit_id, route="structural_omitted")
    review["review_item"]["source_document_ids"] = ["motion"]
    return review


def _adjudication(
    candidate_id: str,
    adjudication_id: str,
    disposition: str,
    reviews: list[dict[str, Any]],
    *,
    source_unit_ids: list[str] | None = None,
    finalized_units: list[dict[str, Any]] | None = None,
    drop_reason: str | None = None,
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": (
            STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION
            if disposition == "ADD"
            else ADJUDICATION_SCHEMA_VERSION
        ),
        "adjudication_id": adjudication_id,
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "review_ids": [review["review_id"] for review in reviews],
        "disposition": disposition,
        "finalized_units": finalized_units or [],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Adjudicated for the preflight fixture.",
    }
    if source_unit_ids is not None:
        record["source_unit_ids"] = source_unit_ids
    if drop_reason is not None:
        record["drop_reason"] = drop_reason
    if exclusion_reason is not None:
        record["exclusion_reason"] = exclusion_reason
    return record


def _mixed_fixture() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Two candidates covering ACCEPT, AMEND, DROP, ADD, and exclusion."""

    cand_1 = _candidate(
        "cand-1",
        [
            _unit("a"),
            _unit("b"),
            _unit("c"),
            _unit("d", challenge_scope="unclear"),
            _unit("e", challenged_by_motion=False, challenge_scope="entire_claim"),
            _unit("f", claim_name="Shared Claim", defendant_group="Shared Defendant"),
            _unit("g", claim_name="Shared Claim", defendant_group="Shared Defendant"),
        ],
    )
    review_accept = _review(cand_1, "a", route="structural_combined")
    review_amend = _review(cand_1, "b", route="structural_mis_split")
    review_drop = _review(cand_1, "c")
    review_add = _omission_review(cand_1, "a")
    amended_unit = _unit("b-amended", claim_name="Claim b")
    added_unit = _unit("h-added", documents=("motion",))
    cand_2 = _candidate("cand-2", [_unit("z")])
    review_exclude = _review(cand_2, "z")
    reviews = [
        review_accept,
        review_amend,
        review_drop,
        review_add,
        review_exclude,
    ]
    adjudications = [
        _adjudication("cand-1", "adj-accept", "ACCEPT", [review_accept]),
        _adjudication(
            "cand-1",
            "adj-amend",
            "AMEND",
            [review_amend],
            finalized_units=[amended_unit],
        ),
        _adjudication(
            "cand-1",
            "adj-drop",
            "DROP",
            [review_drop],
            source_unit_ids=["c"],
            drop_reason="spurious_nonunit",
        ),
        _adjudication(
            "cand-1",
            "adj-add",
            "ADD",
            [review_add],
            finalized_units=[added_unit],
        ),
        _adjudication(
            "cand-2",
            "adj-exclude",
            "CANDIDATE-EXCLUSION",
            [review_exclude],
            source_unit_ids=["z"],
            exclusion_reason="not_a_covered_case",
        ),
    ]
    return [cand_1, cand_2], reviews, adjudications


def test_report_summarizes_mixed_dispositions() -> None:
    raw_records, reviews, adjudications = _mixed_fixture()

    result = build_adjudication_preflight_report(
        prediction_unit_records=raw_records,
        review_records=reviews,
        adjudication_records=adjudications,
        input_commitments=_COMMITMENTS,
    )

    report = result.report
    assert report["schema_version"] == ADJUDICATION_PREFLIGHT_REPORT_SCHEMA_VERSION
    assert report["provider_free"] is True
    assert report["read_only"] is True
    assert report["creates_adjudications"] is False
    assert report["input_commitments"] == _COMMITMENTS
    assert report["finalized_artifact"] is None

    totals = report["totals"]
    assert totals["candidate_count"] == 2
    assert totals["review_count"] == 5
    assert totals["adjudication_count"] == 5
    assert totals["excluded_candidate_count"] == 1
    assert totals["before_unit_count"] == 8
    assert totals["after_unit_count"] == 7
    assert totals["added_unit_count"] == 1
    assert totals["dropped_unit_count"] == 1
    assert totals["unclear_unit_count_before"] == 1
    assert totals["unclear_unit_count_after"] == 1
    assert totals["nonmovant_unit_count_before"] == 1
    assert totals["nonmovant_unit_count_after"] == 1
    assert totals["duplicate_claim_defendant_key_count_before"] == 1
    assert totals["duplicate_claim_defendant_key_count_after"] == 1
    assert totals["nonconforming_unit_count_before"] == 0
    assert totals["nonconforming_unit_count_after"] == 0

    first, second = report["candidates"]
    assert first["candidate_id"] == "cand-1"
    assert first["status"] == "finalized"
    assert first["before_unit_count"] == 7
    assert first["after_unit_count"] == 7
    assert first["added_unit_ids"] == ["h-added"]
    assert first["dropped_unit_ids"] == ["c"]
    assert first["automatic_accept_unit_ids"] == ["d", "e", "f", "g"]
    assert first["unclear_unit_ids_before"] == ["d"]
    assert first["unclear_unit_ids_after"] == ["d"]
    assert first["nonmovant_unit_ids_before"] == ["e"]
    assert first["nonmovant_unit_ids_after"] == ["e"]
    assert first["duplicate_claim_defendant_keys_before"] == [
        {
            "claim_name": "Shared Claim",
            "defendant_group": "Shared Defendant",
            "unit_ids": ["f", "g"],
        }
    ]
    assert first["duplicate_claim_defendant_keys_after"] == [
        {
            "claim_name": "Shared Claim",
            "defendant_group": "Shared Defendant",
            "unit_ids": ["f", "g"],
        }
    ]

    worklist = first["worklist"]
    assert [row["adjudication_id"] for row in worklist] == [
        "adj-accept",
        "adj-add",
        "adj-amend",
        "adj-drop",
    ]
    by_id = {row["adjudication_id"]: row for row in worklist}
    assert by_id["adj-accept"]["disposition"] == "ACCEPT"
    assert by_id["adj-accept"]["source_unit_ids"] == ["a"]
    assert by_id["adj-accept"]["emitted_unit_ids"] == ["a"]
    assert by_id["adj-accept"]["route_reasons"] == ["structural_combined"]
    assert by_id["adj-amend"]["source_unit_ids"] == ["b"]
    assert by_id["adj-amend"]["emitted_unit_ids"] == ["b-amended"]
    assert by_id["adj-drop"]["source_unit_ids"] == ["c"]
    assert by_id["adj-drop"]["emitted_unit_ids"] == []
    assert by_id["adj-drop"]["drop_reason"] == "spurious_nonunit"
    assert by_id["adj-add"]["source_unit_ids"] == []
    assert by_id["adj-add"]["emitted_unit_ids"] == ["h-added"]
    assert by_id["adj-add"]["reviewed_unit_ids"] == ["a"]
    assert by_id["adj-add"]["route_reasons"] == ["structural_omitted"]
    assert by_id["adj-add"]["structural_flag_sha256"] == (
        canonical_sha256({"flag": "a:structural_omitted"})
    )

    matrix = first["matrix"]
    shared = [cell for cell in matrix if cell["claim_name"] == "Shared Claim"]
    assert len(shared) == 1
    assert [entry["unit_id"] for entry in shared[0]["before_units"]] == ["f", "g"]
    assert [entry["unit_id"] for entry in shared[0]["after_units"]] == ["f", "g"]
    amended_cells = [cell for cell in matrix if cell["claim_name"] == "Claim b"]
    assert len(amended_cells) == 1
    assert [entry["unit_id"] for entry in amended_cells[0]["before_units"]] == ["b"]
    assert [entry["unit_id"] for entry in amended_cells[0]["after_units"]] == [
        "b-amended"
    ]
    assert amended_cells[0]["after_units"][0]["disposition"] == "AMEND"
    unclear_cells = [cell for cell in matrix if cell["claim_name"] == "Claim d"]
    assert unclear_cells[0]["after_units"][0]["disposition"] == "automatic-accept"
    assert unclear_cells[0]["after_units"][0]["should_score"] is False

    assert second["candidate_id"] == "cand-2"
    assert second["status"] == "candidate_excluded"
    assert second["excluded"] is True
    assert second["before_unit_count"] == 1
    assert second["after_unit_count"] == 0
    assert second["worklist"] == [
        {
            "adjudication_id": "adj-exclude",
            "disposition": "CANDIDATE-EXCLUSION",
            "adjudicator_id": "lawyer-1",
            "review_ids": ["cand-2:z:structural_spurious"],
            "reviewed_unit_ids": ["z"],
            "route_reasons": ["structural_spurious"],
            "source_unit_ids": ["z"],
            "emitted_unit_ids": [],
            "exclusion_reason": "not_a_covered_case",
        }
    ]
    assert [cell["claim_name"] for cell in second["matrix"]] == ["Claim z"]
    assert second["matrix"][0]["after_units"] == []


def test_report_is_deterministic_under_input_reordering() -> None:
    raw_records, reviews, adjudications = _mixed_fixture()

    baseline = build_adjudication_preflight_report(
        prediction_unit_records=raw_records,
        review_records=reviews,
        adjudication_records=adjudications,
        input_commitments=_COMMITMENTS,
    )
    reordered = build_adjudication_preflight_report(
        prediction_unit_records=list(reversed(raw_records)),
        review_records=reviews,
        adjudication_records=list(reversed(adjudications)),
        input_commitments=_COMMITMENTS,
    )

    assert json.dumps(baseline.report, sort_keys=True) == json.dumps(
        reordered.report, sort_keys=True
    )


def test_invariant_failures_propagate_from_apply() -> None:
    raw_records, reviews, adjudications = _mixed_fixture()
    adjudications[0]["review_ids"] = ["cand-1:missing:structural_combined"]

    with pytest.raises(UnitizationReviewError, match="unknown review"):
        build_adjudication_preflight_report(
            prediction_unit_records=raw_records,
            review_records=reviews,
            adjudication_records=adjudications,
            input_commitments=_COMMITMENTS,
        )


def test_finalized_artifact_must_match_recomputation() -> None:
    raw_records, reviews, adjudications = _mixed_fixture()
    finalized = [
        dict(record)
        for record in apply_unitization_reviews(
            prediction_unit_records=raw_records,
            review_records=reviews,
            adjudication_records=adjudications,
        )
    ]

    result = build_adjudication_preflight_report(
        prediction_unit_records=raw_records,
        review_records=reviews,
        adjudication_records=adjudications,
        finalized_records=finalized,
        input_commitments=_COMMITMENTS,
    )
    finalized_artifact = result.report["finalized_artifact"]
    assert finalized_artifact is not None
    assert finalized_artifact["matches_recomputation"] is True

    # An adjudicated unit's body is not re-hashed by the verifier, so a
    # silent edit there must still fail the recomputation equality.
    tampered = json.loads(json.dumps(finalized))
    for unit in tampered[0]["prediction_units"]:
        if unit["unit_id"] == "b-amended":
            unit["claim_name"] = "Claim b (edited)"
    with pytest.raises(AdjudicationPreflightError, match="does not match"):
        build_adjudication_preflight_report(
            prediction_unit_records=raw_records,
            review_records=reviews,
            adjudication_records=adjudications,
            finalized_records=tampered,
            input_commitments=_COMMITMENTS,
        )

    # An automatic unit is hash-linked to its raw source, so the same edit
    # there is caught by the independent verifier before any comparison.
    broken = json.loads(json.dumps(finalized))
    for unit in broken[0]["prediction_units"]:
        if unit["unit_id"] == "d":
            unit["claim_name"] = "Claim d (edited)"
    with pytest.raises(UnitizationReviewError):
        build_adjudication_preflight_report(
            prediction_unit_records=raw_records,
            review_records=reviews,
            adjudication_records=adjudications,
            finalized_records=broken,
            input_commitments=_COMMITMENTS,
        )


def test_nonconforming_adjudicated_unit_is_reported_not_fatal() -> None:
    raw = _candidate("cand-1", [_unit("a"), _unit("b")])
    review = _review(raw, "b", route="structural_mis_split")
    bare_unit = {"unit_id": "b-amended", "notes": "shape decided by the lawyer"}
    adjudication = _adjudication(
        "cand-1",
        "adj-amend",
        "AMEND",
        [review],
        finalized_units=[bare_unit],
    )

    result = build_adjudication_preflight_report(
        prediction_unit_records=[raw],
        review_records=[review],
        adjudication_records=[adjudication],
        input_commitments=_COMMITMENTS,
    )

    [candidate] = result.report["candidates"]
    assert candidate["nonconforming_unit_ids_before"] == []
    assert candidate["nonconforming_unit_ids_after"] == ["b-amended"]
    assert all(
        entry["unit_id"] != "b-amended"
        for cell in candidate["matrix"]
        for entry in cell["after_units"]
    )
    assert result.report["totals"]["nonconforming_unit_count_after"] == 1


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _stub_authentication(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lineage = SimpleNamespace(
        selection_records=(),
        parser_records=(),
        markdown_root=tmp_path,
        markdown_bytes={},
        input_commitments={},
        markdown_tree={},
        file_snapshots={},
        document_root=tmp_path,
        document_tree={},
    )

    def verify_unitization(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return lineage

    def verify_review(*args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def require_unchanged(lineage: Any) -> None:
        del lineage

    monkeypatch.setattr(cli, "_verify_stage_a_unitization_run_card", verify_unitization)
    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", verify_review)
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", require_unchanged)


def _preflight_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, list[dict[str, Any]]]:
    raw_records, reviews, adjudications = _mixed_fixture()
    raw = tmp_path / "prediction-units.jsonl"
    queue = tmp_path / "merged-review-queue.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    unit_card = tmp_path / "llm-unitize.json"
    review_card = tmp_path / "llm-review-stage-a.json"
    _write_jsonl(raw, raw_records)
    _write_jsonl(queue, reviews)
    _write_jsonl(adjudications_path, adjudications)
    unit_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")
    finalized = [
        dict(record)
        for record in apply_unitization_reviews(
            prediction_unit_records=raw_records,
            review_records=reviews,
            adjudication_records=adjudications,
        )
    ]
    return raw, queue, adjudications_path, unit_card, review_card, finalized


def _argv(
    raw: Path,
    unit_card: Path,
    review_card: Path,
    queue: Path,
    adjudications_path: Path,
    *,
    finalized: Path | None = None,
) -> list[str]:
    argv = [
        "acquisition",
        "preflight-unitization-adjudication",
        "--prediction-units",
        str(raw),
        "--llm-unitization-run-card",
        str(unit_card),
        "--llm-review-stage-a-run-card",
        str(review_card),
        "--unitization-review-queue",
        str(queue),
        "--adjudications",
        str(adjudications_path),
    ]
    if finalized is not None:
        argv.extend(["--finalized-prediction-units", str(finalized)])
    return argv


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_preflight_cli_prints_report_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_authentication(monkeypatch, tmp_path)
    raw, queue, adjudications_path, unit_card, review_card, _ = _preflight_inputs(
        tmp_path
    )
    before = _tree_snapshot(tmp_path)

    assert cli.main(_argv(raw, unit_card, review_card, queue, adjudications_path)) == 0

    assert _tree_snapshot(tmp_path) == before
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == ADJUDICATION_PREFLIGHT_REPORT_SCHEMA_VERSION
    assert report["read_only"] is True
    assert report["finalized_artifact"] is None
    commitments = report["input_commitments"]
    assert set(commitments) == {
        "raw_prediction_units",
        "llm_unitization_run_card",
        "llm_review_stage_a_run_card",
        "unitization_review_queue",
        "adjudications",
    }
    for commitment in commitments.values():
        assert commitment["sha256"].startswith("sha256:")
    assert report["totals"]["candidate_count"] == 2


def test_preflight_cli_rejects_invalid_adjudications_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_authentication(monkeypatch, tmp_path)
    raw, queue, adjudications_path, unit_card, review_card, _ = _preflight_inputs(
        tmp_path
    )
    records = [
        json.loads(line)
        for line in adjudications_path.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["review_ids"] = ["cand-1:missing:structural_combined"]
    _write_jsonl(adjudications_path, records)
    before = _tree_snapshot(tmp_path)

    assert cli.main(_argv(raw, unit_card, review_card, queue, adjudications_path)) == 2

    assert _tree_snapshot(tmp_path) == before
    assert "unknown review" in capsys.readouterr().err


def test_preflight_cli_verifies_finalized_artifact_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_authentication(monkeypatch, tmp_path)
    raw, queue, adjudications_path, unit_card, review_card, finalized = (
        _preflight_inputs(tmp_path)
    )
    finalized_path = tmp_path / "finalized-prediction-units.jsonl"
    finalized_path.write_bytes(cli._jsonl_bytes(finalized))  # pyright: ignore[reportPrivateUsage]

    assert (
        cli.main(
            _argv(
                raw,
                unit_card,
                review_card,
                queue,
                adjudications_path,
                finalized=finalized_path,
            )
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    finalized_artifact = report["finalized_artifact"]
    assert finalized_artifact is not None
    assert finalized_artifact["matches_recomputation"] is True
    assert "finalized_prediction_units" in report["input_commitments"]

    # Same canonical records, different bytes: an appended comment line is
    # invisible to record parsing but must fail the byte-level check.
    finalized_path.write_bytes(
        cli._jsonl_bytes(finalized) + b"\n"  # pyright: ignore[reportPrivateUsage]
    )
    assert (
        cli.main(
            _argv(
                raw,
                unit_card,
                review_card,
                queue,
                adjudications_path,
                finalized=finalized_path,
            )
        )
        == 2
    )
    assert "bytes do not match" in capsys.readouterr().err


def test_preflight_cli_rejects_symlinked_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_authentication(monkeypatch, tmp_path)
    raw, queue, adjudications_path, unit_card, review_card, _ = _preflight_inputs(
        tmp_path
    )
    link = tmp_path / "adjudications-link.jsonl"
    link.symlink_to(adjudications_path)

    assert cli.main(_argv(raw, unit_card, review_card, queue, link)) == 2
    assert "singly linked regular" in capsys.readouterr().err

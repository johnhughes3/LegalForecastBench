"""Regression tests for the provider-free Stage A human review bundle."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.contracts import (
    UNITIZATION_REVIEW_BUNDLE_MANIFEST_V1,
    UNITIZATION_REVIEW_BUNDLE_V1,
)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _unit(unit_id: str, source_document_id: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [{"document_id": source_document_id, "page": 1}],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _review(unit_id: str, source_document_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": unit_id,
        "review_id": f"cand-1:{unit_id}:stage-a-review",
        "route_reason": "unclear_grouping",
        "review_item": {
            "unit_id": unit_id,
            "reason": "unclear_grouping",
            "notes": "Review against the cited pleadings.",
            "source_document_ids": source_document_ids,
        },
    }


def _authenticated_lineage(markdown_root: Path) -> SimpleNamespace:
    complaint = markdown_root / "complaint.md"
    motion = markdown_root / "motion.md"
    complaint.write_text("Complaint predecision facts.", encoding="utf-8")
    motion.write_text("Motion predecision facts.", encoding="utf-8")
    return SimpleNamespace(
        selection_records=(
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "complaint",
                        "document_role": "complaint",
                        "model_visible": True,
                        "contains_target_outcome": False,
                    },
                    {
                        "source_document_id": "motion",
                        "document_role": "motion",
                        "model_visible": True,
                        "contains_target_outcome": False,
                    },
                    {
                        "source_document_id": "decision",
                        "document_role": "decision",
                        "model_visible": False,
                        "contains_target_outcome": True,
                    },
                ],
            },
        ),
        parser_records=(
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "markdown_path": "complaint.md",
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "motion",
                "markdown_path": "motion.md",
            },
        ),
        markdown_root=markdown_root,
        markdown_bytes={
            "complaint.md": complaint.read_bytes(),
            "motion.md": motion.read_bytes(),
        },
        input_commitments={
            "selection": {"path": "/authenticated/selection.jsonl", "sha256": "x"},
            "parser_manifest": {"path": "/authenticated/parser.jsonl", "sha256": "y"},
        },
        markdown_tree={},
        file_snapshots={},
        document_root=markdown_root,
        document_tree={},
    )


def _stub_authentication(
    monkeypatch: pytest.MonkeyPatch, markdown_root: Path
) -> list[dict[str, Any]]:
    lineage = _authenticated_lineage(markdown_root)
    calls: list[dict[str, Any]] = []

    def verify_unitization(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return lineage

    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_run_card",
        verify_unitization,
    )

    def verify_review(*args: Any, **kwargs: Any) -> None:
        del args
        calls.append(kwargs)

    def require_unchanged(lineage: Any) -> None:
        del lineage

    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", verify_review)
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", require_unchanged)
    return calls


def _argv(
    root: Path, raw: Path, unit_card: Path, review_card: Path, queue: Path
) -> list[str]:
    return [
        "acquisition",
        "build-unitization-review-bundle",
        "--output-root",
        str(root),
        "--prediction-units",
        str(raw),
        "--llm-unitization-run-card",
        str(unit_card),
        "--llm-review-stage-a-run-card",
        str(review_card),
        "--unitization-review-queue",
        str(queue),
        "--execute",
    ]


def test_builds_blinded_bundle_from_authenticated_stage_a_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    verification_calls = _stub_authentication(monkeypatch, markdown_root)
    raw = tmp_path / "prediction-units.jsonl"
    queue = tmp_path / "merged-review-queue.jsonl"
    unit_card = tmp_path / "llm-unitize.json"
    review_card = tmp_path / "llm-review-stage-a.json"
    _write_jsonl(
        raw,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    _unit("unit-1", "complaint"),
                    _unit("unit-2", "motion"),
                ],
            }
        ],
    )
    _write_jsonl(queue, [_review("unit-1", ["complaint"])])
    unit_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")

    output_root = tmp_path / "private-bundle"
    assert main(_argv(output_root, raw, unit_card, review_card, queue)) == 0

    [bundle] = [
        json.loads(line)
        for line in (output_root / "unitization-review-bundle.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert bundle["schema_version"] == str(UNITIZATION_REVIEW_BUNDLE_V1)
    assert bundle["review_id"] == "cand-1:unit-1:stage-a-review"
    assert [
        unit["unit_id"] for unit in bundle["raw_prediction_units"]["prediction_units"]
    ] == [
        "unit-1",
        "unit-2",
    ]
    assert [
        source["source_document_id"] for source in bundle["cited_predecision_markdown"]
    ] == [
        "complaint",
        "motion",
    ]
    assert {
        source["source_document_id"] for source in bundle["cited_predecision_markdown"]
    } == {"complaint", "motion"}
    assert {
        source["document_role"] for source in bundle["cited_predecision_markdown"]
    }.isdisjoint({"decision", "order"})
    manifest = json.loads(
        (output_root / "unitization-review-bundle-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["schema_version"] == str(UNITIZATION_REVIEW_BUNDLE_MANIFEST_V1)
    assert manifest["record_count"] == 1
    assert manifest["input_commitments"]["raw_prediction_units"]["path"] == str(
        raw.resolve()
    )
    assert verification_calls[0]["expected_review_queue_path"] == queue
    completion = json.loads(
        (output_root / "run-cards" / "build-unitization-review-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert completion["stage"] == "build-unitization-review-bundle"
    assert completion["paid_activity_executed"] is False
    assert completion["output_paths"] == [
        str(output_root / "unitization-review-bundle.jsonl"),
        str(output_root / "unitization-review-bundle-manifest.json"),
    ]


def test_builds_bundle_for_authenticated_terminal_escalation_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    _stub_authentication(monkeypatch, markdown_root)
    raw = tmp_path / "prediction-units.jsonl"
    queue = tmp_path / "merged-review-queue.jsonl"
    unit_card = tmp_path / "llm-unitize.json"
    review_card = tmp_path / "llm-review-stage-a.json"
    unit = _unit("unit-1", "complaint")
    _write_jsonl(
        raw,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [unit],
            }
        ],
    )
    terminal = _review("unit-1", ["complaint"])
    terminal["route_reason"] = "structural_reviewer_terminal_reconstruction_failure"
    terminal["review_item"].pop("source_document_ids")
    terminal["review_item"].update(
        {
            "frozen_unit": unit,
            "predecision_source_commitments": [{"source_document_id": "complaint"}],
        }
    )
    _write_jsonl(queue, [terminal])
    unit_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")

    output_root = tmp_path / "terminal-bundle"
    assert main(_argv(output_root, raw, unit_card, review_card, queue)) == 0
    [bundle] = [
        json.loads(line)
        for line in (output_root / "unitization-review-bundle.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert bundle["review_item"]["source_document_ids"] == ["complaint"]
    assert [
        source["source_document_id"] for source in bundle["cited_predecision_markdown"]
    ] == ["complaint"]

    terminal["review_item"]["frozen_unit"] = {
        **unit,
        "claim_name": "tampered frozen unit",
    }
    _write_jsonl(queue, [terminal])
    assert (
        main(_argv(tmp_path / "tampered-terminal", raw, unit_card, review_card, queue))
        == 2
    )


def test_rejects_decision_source_and_duplicate_reviews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    _stub_authentication(monkeypatch, markdown_root)
    raw = tmp_path / "prediction-units.jsonl"
    queue = tmp_path / "merged-review-queue.jsonl"
    unit_card = tmp_path / "llm-unitize.json"
    review_card = tmp_path / "llm-review-stage-a.json"
    _write_jsonl(
        raw,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [_unit("unit-1", "complaint")],
            }
        ],
    )
    unit_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")

    _write_jsonl(queue, [_review("unit-1", ["decision"])])
    assert (
        main(_argv(tmp_path / "out-decision", raw, unit_card, review_card, queue)) == 2
    )

    valid = _review("unit-1", ["complaint"])
    _write_jsonl(queue, [valid, valid])
    assert (
        main(_argv(tmp_path / "out-duplicate", raw, unit_card, review_card, queue)) == 2
    )


def test_rejects_hard_linked_authenticated_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    _stub_authentication(monkeypatch, markdown_root)
    raw = tmp_path / "prediction-units.jsonl"
    raw_alias = tmp_path / "raw-alias.jsonl"
    queue = tmp_path / "merged-review-queue.jsonl"
    unit_card = tmp_path / "llm-unitize.json"
    review_card = tmp_path / "llm-review-stage-a.json"
    _write_jsonl(
        raw,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [_unit("unit-1", "complaint")],
            }
        ],
    )
    raw_alias.hardlink_to(raw)
    _write_jsonl(queue, [_review("unit-1", ["complaint"])])
    unit_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")

    assert main(_argv(tmp_path / "out", raw, unit_card, review_card, queue)) == 2

    raw.unlink()
    raw.symlink_to(raw_alias)
    assert (
        main(_argv(tmp_path / "out-symlink", raw, unit_card, review_card, queue)) == 2
    )

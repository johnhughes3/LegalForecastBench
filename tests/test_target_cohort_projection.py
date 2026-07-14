from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.target_cohort_projection import (
    TargetCohortProjectionError,
    project_target_cohort,
)


def test_projection_selects_exact_cheapest_post_clearance_cohort() -> None:
    candidate_ids = ("case-a", "case-b", "case-c", "case-d")
    selection = [_selection(candidate_id) for candidate_id in candidate_ids]
    relevance = [
        _relevance(candidate_id, missing_count=index)
        for index, candidate_id in enumerate(candidate_ids)
    ]
    downloads = [
        _download(candidate_id, f"{candidate_id}-complaint")
        for candidate_id in candidate_ids
    ]
    clearance = [
        _clearance(candidate_id, f"{candidate_id}-complaint")
        for candidate_id in candidate_ids
    ]
    # The cheapest case is quarantined before ranking. The exact cohort must
    # therefore contain B and C, while D remains a fully ledgered frontier omit.
    clearance[0]["status"] = "quarantined"

    projection = project_target_cohort(
        selections=selection,
        case_relevance=relevance,
        download_manifest=downloads,
        clearance_records=clearance,
        target_case_count=2,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="100.00",
        max_missing_core_documents_per_case=24,
    )

    assert projection.selected_candidate_ids == ("case-b", "case-c")
    assert {row["candidate_id"] for row in projection.selections} == {
        "case-b",
        "case-c",
    }
    assert {row["candidate_id"] for row in projection.case_relevance} == {
        "case-b",
        "case-c",
    }
    assert {row["candidate_id"] for row in projection.download_manifest} == {
        "case-b",
        "case-c",
    }
    assert {row["candidate_id"] for row in projection.clearance_records} == {
        "case-b",
        "case-c",
    }
    assert {row["candidate_id"] for row in projection.restriction_evidence} == {
        "case-b",
        "case-c",
    }
    assert projection.budget_plan.target_case_count_met is True
    assert len(projection.budget_plan.case_plans) == 2
    exclusions = {row["candidate_id"]: row["reason"] for row in projection.exclusions}
    assert exclusions == {
        "case-a": "disclosure_clearance_quarantined",
        "case-d": "target_cohort_frontier_omitted",
    }
    assert projection.summary["resolved_pool_case_count"] == 4
    assert projection.summary["selected_case_count"] == 2
    assert projection.summary["selected_candidate_ids_sha256"].startswith("sha256:")


def test_projection_fails_closed_when_manifest_clearance_is_missing() -> None:
    with pytest.raises(
        TargetCohortProjectionError,
        match="manifest document lacks exactly one clearance row",
    ):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[_download("case-a", "case-a-complaint")],
            clearance_records=[],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="100.00",
            max_missing_core_documents_per_case=24,
        )


def test_projection_rejects_cross_pool_and_duplicate_records() -> None:
    duplicate = _selection("case-a")
    with pytest.raises(TargetCohortProjectionError, match="duplicate selection"):
        project_target_cohort(
            selections=[duplicate, dict(duplicate)],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[_download("case-a", "case-a-complaint")],
            clearance_records=[_clearance("case-a", "case-a-complaint")],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="100.00",
            max_missing_core_documents_per_case=24,
        )

    with pytest.raises(TargetCohortProjectionError, match="outside resolved pool"):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[_download("case-x", "case-x-complaint")],
            clearance_records=[_clearance("case-x", "case-x-complaint")],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="100.00",
            max_missing_core_documents_per_case=24,
        )


def test_projection_fails_when_post_clearance_pool_cannot_meet_target() -> None:
    clearance = _clearance("case-a", "case-a-complaint")
    clearance["status"] = "quarantined"
    with pytest.raises(TargetCohortProjectionError, match="only 0 post-clearance"):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[_download("case-a", "case-a-complaint")],
            clearance_records=[clearance],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="100.00",
            max_missing_core_documents_per_case=24,
        )


def test_projection_rejects_restricted_relevance_document() -> None:
    relevance = _relevance("case-a", missing_count=0)
    relevance["documents"][0]["redaction_or_seal_status"] = "sealed"
    relevance["documents"][0]["is_sealed"] = True
    with pytest.raises(TargetCohortProjectionError, match="sealed/private/restricted"):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[relevance],
            download_manifest=[_download("case-a", "case-a-complaint")],
            clearance_records=[_clearance("case-a", "case-a-complaint")],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="100.00",
            max_missing_core_documents_per_case=24,
        )


def test_projection_cli_binds_sources_and_limits_parse_planning(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    document_root = tmp_path / "documents"
    selection_path = source_root / "selection.jsonl"
    relevance_path = source_root / "case-relevance.jsonl"
    manifest_path = source_root / "downloads.jsonl"
    clearance_path = source_root / "clearance.jsonl"
    snapshot_manifest_path = source_root / "snapshot-manifest.json"
    preparation_summary_path = source_root / "preparation-summary.json"

    candidate_ids = ("case-a", "case-b", "case-c")
    _write_jsonl(selection_path, [_selection(case_id) for case_id in candidate_ids])
    _write_jsonl(
        relevance_path,
        [
            _relevance("case-a", missing_count=0),
            _relevance("case-b", missing_count=1),
            _relevance("case-c", missing_count=2),
        ],
    )
    manifests: list[dict[str, Any]] = []
    clearances: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        document_id = f"{candidate_id}-complaint"
        relative_path = f"{candidate_id}/{document_id}.pdf"
        path = document_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = f"%PDF fixture {candidate_id}".encode()
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        manifest = _download(candidate_id, document_id)
        manifest.update(
            {
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": len(data),
            }
        )
        clearance = _clearance(candidate_id, document_id)
        clearance.update({"sha256": digest, "byte_count": len(data)})
        manifests.append(manifest)
        clearances.append(clearance)
    _write_jsonl(manifest_path, manifests)
    _write_jsonl(clearance_path, clearances)
    snapshot_manifest = {"cycle_hash": "cycle-hash", "batch_digest": "batch-digest"}
    snapshot_manifest_path.write_text(
        json.dumps(snapshot_manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    preparation_summary_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.target_100_preparation.v1",
                "dry_run": False,
                "paid_activity_executed": False,
                "snapshot_manifest_sha256": "sha256:"
                + hashlib.sha256(snapshot_manifest_path.read_bytes()).hexdigest(),
                "snapshot_batch_digest": "batch-digest",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    output_root = tmp_path / "projection"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(output_root),
                "--selection",
                str(selection_path),
                "--case-relevance",
                str(relevance_path),
                "--download-manifest",
                str(manifest_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--preparation-summary",
                str(preparation_summary_path),
                "--snapshot-manifest",
                str(snapshot_manifest_path),
                "--target-case-count",
                "2",
                "--max-projected-budget-usd",
                "100.00",
                "--execute",
            ]
        )
        == 0
    )
    projected_selection = _read_jsonl(output_root / "target-cohort-selection.jsonl")
    assert [row["candidate_id"] for row in projected_selection] == [
        "case-a",
        "case-b",
    ]
    summary = json.loads((output_root / "target-cohort-projection.json").read_text())
    assert summary["selected_case_count"] == 2
    assert summary["next_stage"] == "generate-recap-fetch-broker-policy"
    assert summary["input_commitments"]
    assert summary["output_commitments"]

    parse_root = tmp_path / "parse-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(output_root / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(output_root / "disclosure-clearance.jsonl"),
                "--document-root",
                str(document_root),
                "--output-root",
                str(parse_root),
                "--execute",
            ]
        )
        == 0
    )
    parse_requests = _read_jsonl(parse_root / "parse-document-requests.jsonl")
    assert {row["candidate_id"] for row in parse_requests} == {"case-a", "case-b"}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _selection(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "nysd",
        "decision_date": "2026-06-30",
        "selected": True,
        "documents": [
            {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-complaint",
                "document_role": "complaint",
                "model_visible": True,
                "redaction_or_seal_status": "public",
                "is_sealed": False,
                "is_private": False,
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
            }
        ],
    }


def _relevance(candidate_id: str, *, missing_count: int) -> dict[str, Any]:
    documents: list[dict[str, Any]] = [
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-complaint",
            "setup_runner_label": "core_mtd",
            "document_role": "complaint",
            "availability_status": "available",
            "requires_paid_recovery": False,
            "model_visible": True,
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
            "restriction_evidence": ["courtlistener_public_download_record_checked"],
        }
    ]
    if missing_count == 0:
        documents.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-mtd-free",
                "setup_runner_label": "core_mtd",
                "document_role": "motion_to_dismiss_memorandum",
                "availability_status": "available",
                "requires_paid_recovery": False,
                "model_visible": True,
                "redaction_or_seal_status": "public",
                "is_sealed": False,
                "is_private": False,
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
            }
        )
    for index in range(missing_count):
        documents.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-mtd-{index}",
                "setup_runner_label": "core_mtd",
                "document_role": "motion_to_dismiss_memorandum",
                "availability_status": "unavailable",
                "requires_paid_recovery": True,
                "model_visible": True,
                "redaction_or_seal_status": "public",
                "is_sealed": False,
                "is_private": False,
                "restriction_evidence": [
                    "courtlistener_rest_recap_document_exact_match",
                    "courtlistener_rest_recap_document_is_sealed_false",
                ],
            }
        )
    return {"candidate_id": candidate_id, "documents": documents}


def _download(candidate_id: str, document_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "local_path": f"{candidate_id}/{document_id}.pdf",
        "sha256": "a" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }


def _clearance(candidate_id: str, document_id: str) -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "sha256": "a" * 64,
        "byte_count": 10,
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle-1/free-clearance",
        "reviewed_at": "2026-07-14T14:00:00Z",
        "free_or_purchased": "free",
    }

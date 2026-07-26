from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.disclosure_review_authority import (
    disclosure_authority_identity_from_cohort_policy,
)
from legalforecast.ingestion.provenance_clearance import (
    build_provenance_clearance_plan as build_provenance_plan,
)
from legalforecast.ingestion.target_cohort_projection import (
    TargetCohortProjectionError,
    project_target_cohort,
)
from tests.disclosure_review_fixtures import (
    service_disclosure_authority_from_policy_bytes,
)
from tests.test_target_100_acquisition import (
    _fixture_pdf_text,
    _purchase_fixtures,
    _purchase_policies,
    _target_100_fixture,
    _write_authenticated_reviews,
)


@pytest.fixture(autouse=True)
def _allow_signed_service_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    validate = cli_module.validate_review_receipt
    validate_lineage = cli_module.validate_authenticated_clearance_lineage
    monkeypatch.setattr(
        cli_module,
        "validate_review_receipt",
        lambda *positional, **keywords: validate(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "validate_authenticated_clearance_lineage",
        lambda *positional, **keywords: validate_lineage(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "load_main_disclosure_review_authority",
        lambda cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(
                reviewer_policy_bytes,
                identity=disclosure_authority_identity_from_cohort_policy(cohort),
            )
        ),
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


def test_projection_accepts_only_well_formed_provenance_clearance() -> None:
    candidate_id = "case-a"
    document_id = "case-a-complaint"
    clearance = _clearance(candidate_id, document_id)
    clearance.update(
        {
            "clearance_basis": "affirmative_public_provenance",
            "routing_plan_sha256": "b" * 64,
            "reviewer_id": None,
            "controlled_store_provenance": (
                "https://storage.courtlistener.com/recap/case-a/complaint.pdf"
            ),
            "reviewed_at": None,
        }
    )
    projection = project_target_cohort(
        selections=[_selection(candidate_id)],
        case_relevance=[_relevance(candidate_id, missing_count=1)],
        download_manifest=[_download(candidate_id, document_id)],
        clearance_records=[clearance],
        target_case_count=1,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="10.00",
        max_missing_core_documents_per_case=24,
    )
    assert projection.selected_candidate_ids == (candidate_id,)

    clearance["routing_plan_sha256"] = "invalid"
    with pytest.raises(TargetCohortProjectionError, match="lacks routing plan hash"):
        project_target_cohort(
            selections=[_selection(candidate_id)],
            case_relevance=[_relevance(candidate_id, missing_count=1)],
            download_manifest=[_download(candidate_id, document_id)],
            clearance_records=[clearance],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="10.00",
            max_missing_core_documents_per_case=24,
        )


@pytest.mark.parametrize("mutation", ["query_url", "purchased", "prefixed_hash"])
def test_projection_rejects_weaker_automatic_clearance_variants(
    mutation: str,
) -> None:
    candidate_id = "case-a"
    document_id = "case-a-complaint"
    manifest = _download(candidate_id, document_id)
    clearance = _clearance(candidate_id, document_id)
    clearance.update(
        {
            "clearance_basis": "affirmative_public_provenance",
            "routing_plan_sha256": "b" * 64,
            "reviewer_id": None,
            "controlled_store_provenance": (
                "https://storage.courtlistener.com/recap/case-a/complaint.pdf"
            ),
            "reviewed_at": None,
        }
    )
    if mutation == "query_url":
        clearance["controlled_store_provenance"] += "?download=1"
    elif mutation == "purchased":
        manifest["free_or_purchased"] = "purchased"
        clearance["free_or_purchased"] = "purchased"
    else:
        clearance["routing_plan_sha256"] = "sha256:" + "b" * 64

    with pytest.raises(TargetCohortProjectionError, match="clearance policy"):
        project_target_cohort(
            selections=[_selection(candidate_id)],
            case_relevance=[_relevance(candidate_id, missing_count=1)],
            download_manifest=[manifest],
            clearance_records=[clearance],
            target_case_count=1,
            cost_per_document_usd="3.05",
            max_projected_budget_usd="10.00",
            max_missing_core_documents_per_case=24,
        )


def test_projection_accepts_john_cleared_unknown_empty_restriction_evidence() -> None:
    candidate_id = "case-a"
    document_id = "case-a-complaint"
    clearance = _clearance(candidate_id, document_id)
    clearance.update(
        {
            "clearance_basis": "john_exception_review",
            "routing_plan_sha256": "b" * 64,
            "restriction_status": "unknown",
            "restriction_evidence": [],
            "reviewer_id": "John Hughes",
            "controlled_store_provenance": (
                "private-store://john/disclosure-exception-review"
            ),
        }
    )

    projection = project_target_cohort(
        selections=[_selection(candidate_id)],
        case_relevance=[_relevance(candidate_id, missing_count=1)],
        download_manifest=[_download(candidate_id, document_id)],
        clearance_records=[clearance],
        target_case_count=1,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="10.00",
        max_missing_core_documents_per_case=24,
    )

    assert projection.selected_candidate_ids == (candidate_id,)


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


def test_projection_allows_paid_only_candidate_without_manifest_rows() -> None:
    relevance = {
        "candidate_id": "case-a",
        "documents": [
            _paid_relevance_document("case-a", "complaint", "complaint"),
            _paid_relevance_document(
                "case-a",
                "mtd",
                "motion_to_dismiss_memorandum",
            ),
        ],
    }

    projection = project_target_cohort(
        selections=[_selection("case-a")],
        case_relevance=[relevance],
        download_manifest=[],
        clearance_records=[],
        target_case_count=1,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="100.00",
        max_missing_core_documents_per_case=24,
    )

    assert projection.selected_candidate_ids == ("case-a",)
    assert projection.download_manifest == ()
    assert projection.clearance_records == ()
    [case_plan] = projection.budget_plan.case_plans
    assert case_plan.purchase_document_ids == ("complaint", "mtd")
    assert projection.budget_plan.total_estimated_cost_usd == "6.10"


def test_projection_scopes_restrictions_to_acquired_manifest_documents() -> None:
    relevance = _relevance("case-a", missing_count=1)
    paid_gap = relevance["documents"][1]
    paid_gap["redaction_or_seal_status"] = "unknown"
    paid_gap["is_sealed"] = None
    paid_gap["restriction_evidence"] = ["no_positive_restriction_marker"]

    projection = project_target_cohort(
        selections=[_selection("case-a")],
        case_relevance=[relevance],
        download_manifest=[_download("case-a", "case-a-complaint")],
        clearance_records=[_clearance("case-a", "case-a-complaint")],
        target_case_count=1,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="100.00",
        max_missing_core_documents_per_case=24,
    )

    assert [
        (row["candidate_id"], row["source_document_id"])
        for row in projection.restriction_evidence
    ] == [("case-a", "case-a-complaint")]
    [case_plan] = projection.budget_plan.case_plans
    assert case_plan.purchase_document_ids == ("case-a-mtd-0",)


def test_projection_rejects_missing_manifest_for_available_document() -> None:
    with pytest.raises(
        TargetCohortProjectionError,
        match="resolved candidates lack acquired documents",
    ):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[],
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


def test_projection_rejects_unknown_restriction_status() -> None:
    relevance = _relevance("case-a", missing_count=0)
    relevance["documents"][0]["redaction_or_seal_status"] = "unknown"
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema_version", "wrong", "unsupported clearance schema"),
        ("sha256", None, "invalid manifest sha256"),
        ("byte_count", True, "invalid manifest byte_count"),
        ("byte_count", -1, "invalid manifest byte_count"),
        ("free_or_purchased", None, "invalid manifest free_or_purchased"),
        ("restriction_evidence", [""], "lacks restriction evidence"),
        ("restriction_evidence", [None], "lacks restriction evidence"),
    ),
)
def test_projection_rejects_malformed_clearance_binding(
    field: str,
    value: object,
    message: str,
) -> None:
    clearance = _clearance("case-a", "case-a-complaint")
    manifest = _download("case-a", "case-a-complaint")
    clearance[field] = value
    if field in {"sha256", "byte_count", "free_or_purchased"}:
        manifest[field] = value
    with pytest.raises(TargetCohortProjectionError, match=message):
        project_target_cohort(
            selections=[_selection("case-a")],
            case_relevance=[_relevance("case-a", missing_count=0)],
            download_manifest=[manifest],
            clearance_records=[clearance],
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
    clearance_run_card_path = source_root / "clearance-run-card.json"
    restriction_path = source_root / "restriction-evidence.jsonl"
    snapshot_manifest_path = source_root / "snapshot-manifest.json"
    preparation_summary_path = source_root / "preparation-summary.json"
    preparation_config_path = source_root / "preparation-config.json"

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
    for candidate_id in candidate_ids:
        document_id = f"{candidate_id}-complaint"
        relative_path = f"{candidate_id}/{document_id}.pdf"
        path = document_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _fixture_pdf_text(f"Public filing {candidate_id}").encode()
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
        manifests.append(manifest)
    _write_jsonl(manifest_path, manifests)
    restrictions = [
        {
            "candidate_id": row["candidate_id"],
            "source_document_id": row["source_document_id"],
            "restriction_status": "public",
            "restriction_evidence": ["courtlistener_public_download_record_checked"],
            "is_sealed": False,
            "is_private": False,
        }
        for row in manifests
    ]
    _write_jsonl(restriction_path, restrictions)
    snapshot_manifest = {"cycle_hash": "cycle-hash", "batch_digest": "batch-digest"}
    snapshot_manifest_path.write_text(
        json.dumps(snapshot_manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    config = {
        "schema_version": "legalforecast.target_100_config.v1",
        "snapshot_manifest_sha256": _path_digest(snapshot_manifest_path),
        "snapshot_cycle_hash": "cycle-hash",
        "snapshot_batch_digest": "batch-digest",
        "target_case_count": 2,
        "cost_per_document_usd": "3.05",
        "max_projected_budget_usd": "100.00",
        "max_missing_core_documents_per_case": 24,
        "driver_execute": True,
    }
    config["config_sha256"] = _canonical_digest(config)
    preparation_config_path.write_text(
        json.dumps(config, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    preparation_summary_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.target_100_preparation.v1",
                "dry_run": False,
                "paid_activity_executed": False,
                "budget_status": "provisional_pre_clearance",
                "next_stage": "clear-disclosures",
                "config_sha256": config["config_sha256"],
                "target_case_count": 2,
                "cost_per_document_usd": "3.05",
                "max_projected_budget_usd": "100.00",
                "max_missing_core_documents_per_case": 24,
                "snapshot_manifest_sha256": _path_digest(snapshot_manifest_path),
                "snapshot_batch_digest": "batch-digest",
                "stage_commitments": {
                    "03-gap-bridge": {
                        "public-packet-selection-reconciled.jsonl": _path_digest(
                            selection_path
                        ),
                        "case-relevance.jsonl": _path_digest(relevance_path),
                    },
                    "03c-merged-downloads": {
                        "document-downloads-merged.jsonl": _path_digest(manifest_path)
                    },
                    "06-clearance-inputs": {
                        "restriction-evidence.jsonl": _path_digest(restriction_path)
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    review = _write_authenticated_reviews(
        tmp_path / "signed-review",
        manifest_path=manifest_path,
        document_root=document_root,
        restriction_evidence_path=restriction_path,
        store_uri="private-store://fixture/projection",
    )
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(manifest_path),
                "--review-requests",
                str(review.requests),
                "--document-root",
                str(document_root),
                "--review-worksheet",
                str(review.worksheet),
                "--reviews",
                str(review.reviews),
                "--review-receipt",
                str(review.receipt),
                "--reviewer-policy",
                str(review.policy),
                "--cohort-policy",
                str(review.cohort_policy),
                "--restriction-evidence",
                str(restriction_path),
                "--clearance-output",
                str(clearance_path),
                "--run-card-output",
                str(clearance_run_card_path),
                "--output-root",
                str(source_root / "clearance"),
                "--execute",
            ]
        )
        == 0
    )

    output_root = tmp_path / "projection"
    projection_command = [
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
        "--clearance-run-card",
        str(clearance_run_card_path),
        "--restriction-evidence",
        str(restriction_path),
        "--preparation-summary",
        str(preparation_summary_path),
        "--preparation-config",
        str(preparation_config_path),
        "--snapshot-manifest",
        str(snapshot_manifest_path),
        "--target-case-count",
        "2",
        "--max-projected-budget-usd",
        "100.00",
        "--execute",
    ]
    assert main(projection_command) == 0
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

    original_selection = selection_path.read_bytes()
    selection_path.write_bytes(original_selection + b"\n")
    mutated_command = [
        argument.replace(str(output_root), str(tmp_path / "mutated-projection"))
        for argument in projection_command
    ]
    assert main(mutated_command) == 2
    selection_path.write_bytes(original_selection)

    cap_drift_command = [
        "101.00" if argument == "100.00" else argument
        for argument in projection_command
    ]
    cap_drift_command[cap_drift_command.index(str(output_root))] = str(
        tmp_path / "cap-drift-projection"
    )
    assert main(cap_drift_command) == 2

    canonical = _materialized_two_case_cohort(tmp_path / "canonical")
    canonical_case_ids = {
        row["candidate_id"] for row in _read_jsonl(canonical["selection"])
    }
    assert len(canonical_case_ids) == 2
    parse_root = tmp_path / "parse-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--selection",
                str(canonical["selection"]),
                "--download-manifest",
                str(canonical["manifest"]),
                "--disclosure-clearance",
                str(canonical["clearance"]),
                "--document-root",
                str(canonical["document_root"]),
                "--materialization-run-card",
                str(canonical["run_card"]),
                "--output-root",
                str(parse_root),
                "--execute",
            ]
        )
        == 0
    )
    parse_requests = _read_jsonl(parse_root / "parse-document-requests.jsonl")
    assert {row["candidate_id"] for row in parse_requests} == canonical_case_ids


def test_provenance_clearance_projects_and_materializes_two_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_marker_plan(
        review_requests: Sequence[Mapping[str, object]],
        download_manifest: Sequence[Mapping[str, object]],
        restriction_evidence: Sequence[Mapping[str, object]],
        case_relevance: Sequence[Mapping[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        return build_provenance_plan(
            review_requests,
            download_manifest,
            restriction_evidence,
            case_relevance,
            document_root=cast(Path, kwargs["document_root"]),
            review_requests_bytes=cast(bytes, kwargs["review_requests_bytes"]),
            download_manifest_bytes=cast(bytes, kwargs["download_manifest_bytes"]),
            restriction_evidence_bytes=cast(
                bytes, kwargs["restriction_evidence_bytes"]
            ),
            case_relevance_bytes=cast(bytes, kwargs["case_relevance_bytes"]),
            document_bytes_by_relative_path=cast(
                Mapping[str, bytes] | None,
                kwargs.get("document_bytes_by_relative_path"),
            ),
            marker_scanner=lambda _payload: (),
        )

    monkeypatch.setattr(cli_module, "build_provenance_clearance_plan", no_marker_plan)
    canonical = _materialized_two_case_cohort(
        tmp_path / "provenance-canonical",
        provenance_first=True,
        monkeypatch=monkeypatch,
    )
    assert len(_read_jsonl(canonical["selection"])) == 2
    manifest = _read_jsonl(canonical["manifest"])
    clearance = _read_jsonl(canonical["clearance"])
    assert len(manifest) == len(clearance)
    assert {row["clearance_basis"] for row in clearance} == {"john_exception_review"}
    assert all(row["status"] == "cleared" for row in clearance)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _path_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_provenance_clearance(
    root: Path,
    *,
    manifest_path: Path,
    review_requests_path: Path,
    case_relevance_path: Path,
    restriction_evidence_path: Path,
    document_root: Path,
    cohort_policy_path: Path,
    clearance_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_root = root / "plan"
    private_root = root.parent.parent / f"{root.parent.name}-{root.name}-private"
    assert (
        main(
            [
                "acquisition",
                "plan-disclosure-provenance",
                "--review-requests",
                str(review_requests_path),
                "--download-manifest",
                str(manifest_path),
                "--case-relevance",
                str(case_relevance_path),
                "--restriction-evidence",
                str(restriction_evidence_path),
                "--document-root",
                str(document_root),
                "--controlled-private-store-root",
                str(private_root),
                "--output-root",
                str(plan_root),
                "--execute",
            ]
        )
        == 0
    )
    worksheet_path = plan_root / "disclosure-exception-worksheet.json"
    worksheet = json.loads(worksheet_path.read_text())
    digests = iter(str(row["sha256"]) for row in worksheet["documents"])

    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    def clear_every_exception(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return next(digests)
        if prompt.startswith("Decision"):
            return "cleared"
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    monkeypatch.setattr("builtins.input", clear_every_exception)
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(worksheet_path),
                "--private-inspection-map",
                str(private_root / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(private_root),
                "--output-root",
                str(private_root / "metadata"),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "clear-provenance-disclosures",
                "--review-requests",
                str(review_requests_path),
                "--download-manifest",
                str(manifest_path),
                "--case-relevance",
                str(case_relevance_path),
                "--restriction-evidence",
                str(restriction_evidence_path),
                "--document-root",
                str(document_root),
                "--routing-plan",
                str(plan_root / "disclosure-provenance-plan.json"),
                "--exception-worksheet",
                str(worksheet_path),
                "--exception-decisions",
                str(private_root / "disclosure-review-decisions.jsonl"),
                "--exception-review-run-card",
                str(
                    private_root
                    / "metadata/run-cards/record-disclosure-review-decisions.json"
                ),
                "--cohort-policy",
                str(cohort_policy_path),
                "--output-root",
                str(clearance_root),
                "--execute",
            ]
        )
        == 0
    )


def _materialized_two_case_cohort(
    tmp_path: Path,
    *,
    provenance_first: bool = False,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> dict[str, Path]:
    """Build a real two-case signed projection and canonical materialization."""

    tmp_path.mkdir(parents=True)
    preparation = tmp_path / "preparation"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "fixture", case_count=2)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(preparation),
                "--snapshot",
                str(snapshot),
                "--expected-snapshot-manifest-sha256",
                hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest(),
                "--expected-cycle-hash",
                cycle_hash,
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    free_manifest = preparation / "03c-merged-downloads/document-downloads-merged.jsonl"
    free_restrictions = preparation / "06-clearance-inputs/restriction-evidence.jsonl"
    free_review = _write_authenticated_reviews(
        tmp_path / "free-review",
        manifest_path=free_manifest,
        document_root=preparation / "documents/free",
        review_requests_path=(
            preparation / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=free_restrictions,
        store_uri="private-store://fixture/projection-free",
    )
    free_clearance_root = tmp_path / "free-clearance"
    if provenance_first:
        assert monkeypatch is not None
        _write_provenance_clearance(
            tmp_path / "free-provenance",
            manifest_path=free_manifest,
            review_requests_path=free_review.requests,
            case_relevance_path=preparation / "03-gap-bridge/case-relevance.jsonl",
            restriction_evidence_path=free_restrictions,
            document_root=preparation / "documents/free",
            cohort_policy_path=free_review.cohort_policy,
            clearance_root=free_clearance_root,
            monkeypatch=monkeypatch,
        )
    else:
        assert (
            main(
                [
                    "acquisition",
                    "clear-disclosures",
                    "--download-manifest",
                    str(free_manifest),
                    "--review-requests",
                    str(free_review.requests),
                    "--document-root",
                    str(preparation / "documents/free"),
                    "--review-worksheet",
                    str(free_review.worksheet),
                    "--reviews",
                    str(free_review.reviews),
                    "--review-receipt",
                    str(free_review.receipt),
                    "--reviewer-policy",
                    str(free_review.policy),
                    "--cohort-policy",
                    str(free_review.cohort_policy),
                    "--restriction-evidence",
                    str(free_restrictions),
                    "--output-root",
                    str(free_clearance_root),
                    "--execute",
                ]
            )
            == 0
        )
    projection = tmp_path / "projection"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projection),
                "--selection",
                str(
                    preparation
                    / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(preparation / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(free_manifest),
                "--disclosure-clearance",
                str(free_clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(free_clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(free_restrictions),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-case-count",
                "2",
                "--execute",
            ]
        )
        == 0
    )
    selection = projection / "target-cohort-selection.jsonl"
    budget_plan = projection / "missing-core-budget-plan.json"
    purchase_policy, cohort_policy, purchase_ledger = _purchase_policies(tmp_path)
    broker_policy = tmp_path / "broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--output",
                str(broker_policy),
            ]
        )
        == 0
    )
    allowed_documents = json.loads(broker_policy.read_text())["allowed_documents"]
    purchase_cl_fixture, purchase_broker_fixture = _purchase_fixtures(
        tmp_path,
        [str(row["recap_document"]) for row in allowed_documents],
    )
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--output-root",
                str(tmp_path / "ledger-init"),
                "--execute",
            ]
        )
        == 0
    )
    purchase_root = tmp_path / "purchase"
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--output-root",
                str(purchase_root),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--courtlistener-fixture",
                str(purchase_cl_fixture),
                "--purchase-broker-fixture",
                str(purchase_broker_fixture),
                "--execute",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )
    purchase_result = purchase_root / "courtlistener-recap-fetch-purchases.json"
    attempts = json.loads(purchase_result.read_text())["attempts"]
    purchased_fixture = tmp_path / "purchased-pdfs.json"
    purchased_fixture.write_text(
        json.dumps(
            {
                attempt["download_url"]: _fixture_pdf_text("Purchased motion")
                for attempt in attempts
            }
        )
    )
    recovery = tmp_path / "recovery"
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(purchase_result),
                "--selection",
                str(selection),
                "--output-root",
                str(recovery),
                "--fixture-documents",
                str(purchased_fixture),
                "--execute",
            ]
        )
        == 0
    )
    purchased_manifest = recovery / "purchased-document-downloads.jsonl"
    purchased_rows = _read_jsonl(purchased_manifest)
    purchased_restrictions = tmp_path / "purchased-restrictions.jsonl"
    _write_jsonl(
        purchased_restrictions,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "restriction_status": "public",
                "restriction_evidence": ["courtlistener_recap_fetch_public"],
                "is_sealed": False,
                "is_private": False,
            }
            for row in purchased_rows
        ],
    )
    purchased_review = _write_authenticated_reviews(
        tmp_path / "purchased-review",
        manifest_path=purchased_manifest,
        document_root=recovery / "documents/purchased",
        restriction_evidence_path=purchased_restrictions,
        store_uri="private-store://fixture/projection-purchased",
    )
    purchased_clearance_root = tmp_path / "purchased-clearance"
    if provenance_first:
        assert monkeypatch is not None
        purchased_relevance = tmp_path / "purchased-case-relevance.jsonl"
        documents_by_candidate: dict[str, list[dict[str, object]]] = {}
        for row in purchased_rows:
            documents_by_candidate.setdefault(str(row["candidate_id"]), []).append(
                {
                    "source_document_id": row["source_document_id"],
                    "source_url_or_reference": row["source_url"],
                    "model_visible": True,
                    "contains_target_outcome": False,
                }
            )
        _write_jsonl(
            purchased_relevance,
            [
                {"candidate_id": candidate_id, "documents": documents}
                for candidate_id, documents in sorted(documents_by_candidate.items())
            ],
        )
        purchased_provenance_requests = tmp_path / "purchased-review-requests.jsonl"
        restrictions_by_key = {
            (str(row["candidate_id"]), str(row["source_document_id"])): row
            for row in _read_jsonl(purchased_restrictions)
        }
        _write_jsonl(
            purchased_provenance_requests,
            [
                {
                    "schema_version": "legalforecast.disclosure_review_request.v1",
                    "candidate_id": row["candidate_id"],
                    "source_document_id": row["source_document_id"],
                    "sha256": row["sha256"],
                    "byte_count": row["byte_count"],
                    "free_or_purchased": row["free_or_purchased"],
                    "restriction_status": restrictions_by_key[
                        (str(row["candidate_id"]), str(row["source_document_id"]))
                    ]["restriction_status"],
                    "restriction_evidence": restrictions_by_key[
                        (str(row["candidate_id"]), str(row["source_document_id"]))
                    ]["restriction_evidence"],
                    "required_human_decision": "cleared_or_quarantined",
                }
                for row in purchased_rows
            ],
        )
        _write_provenance_clearance(
            tmp_path / "purchased-provenance",
            manifest_path=purchased_manifest,
            review_requests_path=purchased_provenance_requests,
            case_relevance_path=purchased_relevance,
            restriction_evidence_path=purchased_restrictions,
            document_root=recovery / "documents/purchased",
            cohort_policy_path=purchased_review.cohort_policy,
            clearance_root=purchased_clearance_root,
            monkeypatch=monkeypatch,
        )
    else:
        assert (
            main(
                [
                    "acquisition",
                    "clear-disclosures",
                    "--download-manifest",
                    str(purchased_manifest),
                    "--review-requests",
                    str(purchased_review.requests),
                    "--document-root",
                    str(recovery / "documents/purchased"),
                    "--review-worksheet",
                    str(purchased_review.worksheet),
                    "--reviews",
                    str(purchased_review.reviews),
                    "--review-receipt",
                    str(purchased_review.receipt),
                    "--reviewer-policy",
                    str(purchased_review.policy),
                    "--cohort-policy",
                    str(purchased_review.cohort_policy),
                    "--restriction-evidence",
                    str(purchased_restrictions),
                    "--output-root",
                    str(purchased_clearance_root),
                    "--execute",
                ]
            )
            == 0
        )
    materialized = tmp_path / "materialized"
    assert (
        main(
            [
                "acquisition",
                "materialize-cohort-documents",
                "--output-root",
                str(materialized),
                "--preparation-root",
                str(preparation),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-cohort-root",
                str(projection),
                "--free-disclosure-clearance",
                str(projection / "disclosure-clearance.jsonl"),
                "--purchased-recovery-root",
                str(recovery),
                "--purchased-disclosure-clearance",
                str(purchased_clearance_root / "disclosure-clearance.jsonl"),
                "--purchased-clearance-run-card",
                str(purchased_clearance_root / "run-cards/clear-disclosures.json"),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--execute",
            ]
        )
        == 0
    )
    return {
        "selection": selection,
        "manifest": materialized / "document-downloads-merged.jsonl",
        "clearance": materialized / "disclosure-clearance.jsonl",
        "document_root": materialized / "documents",
        "run_card": materialized / "run-cards/materialize-cohort-documents.json",
    }


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


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


def _paid_relevance_document(
    candidate_id: str,
    document_id: str,
    document_role: str,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "setup_runner_label": "core_mtd",
        "document_role": document_role,
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
        "model_visible": True,
        "redaction_or_seal_status": "public",
        "is_sealed": False,
        "is_private": None,
        "restriction_evidence": [
            "courtlistener_rest_recap_document_exact_match",
            "courtlistener_rest_recap_document_is_sealed_false",
        ],
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

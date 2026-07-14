from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest

from legalforecast.ingestion.cohort_policy import generate_cohort_policy
from legalforecast.ingestion.retained_cohort_extension import (
    RetainedCohortExtensionError,
    extend_target_cohort,
)
from legalforecast.ingestion.target_cohort_projection import project_target_cohort


def test_extension_preserves_base_prefix_and_selects_only_omitted_frontier() -> None:
    inputs = _inputs()

    extension = extend_target_cohort(**inputs)

    assert extension.base_candidate_ids == tuple(_candidate_id(i) for i in range(100))
    assert extension.incremental_candidate_ids == tuple(
        _candidate_id(i) for i in range(100, 150)
    )
    assert extension.combined_candidate_ids == tuple(
        _candidate_id(i) for i in range(150)
    )
    assert set(extension.base_candidate_ids).isdisjoint(
        extension.incremental_candidate_ids
    )
    for name, base_payload in inputs["base_projection_artifacts"].items():
        if name in {
            "target-cohort-selection.jsonl",
            "case-relevance.jsonl",
            "document-downloads-merged.jsonl",
            "disclosure-clearance.jsonl",
            "restriction-evidence.jsonl",
            "core-filter-results.jsonl",
        }:
            assert extension.combined_artifacts[name].startswith(base_payload)
    exclusions = {
        json.loads(line)["candidate_id"]
        for line in extension.combined_artifacts[
            "target-cohort-exclusions.jsonl"
        ].splitlines()
    }
    assert exclusions == {_candidate_id(150)}
    assert extension.extension_record["combined_case_count"] == 150
    assert extension.extension_record["full_pool_case_count"] == 151
    assert extension.extension_record["paid_activity_requested"] is False
    assert extension.extension_record["paid_activity_executed"] is False


def test_extension_is_byte_identical_on_resume() -> None:
    inputs = _inputs()

    first = extend_target_cohort(**inputs)
    second = extend_target_cohort(**inputs)

    assert first.combined_artifacts == second.combined_artifacts
    assert first.incremental_artifacts == second.incremental_artifacts
    assert first.extension_record == second.extension_record


def test_extension_fails_when_eligible_omitted_frontier_is_insufficient() -> None:
    inputs = _inputs()
    full = dict(inputs["full_pool_artifacts"])
    records = _jsonl(full["disclosure-clearance.jsonl"])
    for record in records:
        if record["candidate_id"] in {
            _candidate_id(index) for index in range(100, 151)
        }:
            record["status"] = "quarantined"
    full["disclosure-clearance.jsonl"] = _jsonl_bytes(records)
    inputs["full_pool_artifacts"] = full

    with pytest.raises(RetainedCohortExtensionError, match="post-clearance"):
        extend_target_cohort(**inputs)


def test_extension_fails_on_changed_base_input_or_prefix() -> None:
    inputs = _inputs()
    base = dict(inputs["base_projection_artifacts"])
    rows = _jsonl(base["target-cohort-selection.jsonl"])
    rows[0]["case_name"] = "changed"
    base["target-cohort-selection.jsonl"] = _jsonl_bytes(rows)
    inputs["base_projection_artifacts"] = base

    with pytest.raises(RetainedCohortExtensionError, match="output commitment"):
        extend_target_cohort(**inputs)


def test_extension_rejects_duplicate_docket_and_motion_identities() -> None:
    for mutation, message in (
        ("docket", "duplicate docket identity"),
        ("motion", "duplicate motion identity"),
    ):
        inputs = _inputs()
        full = dict(inputs["full_pool_artifacts"])
        selections = _jsonl(full["selection.jsonl"])
        if mutation == "docket":
            selections[149]["docket_number"] = selections[148]["docket_number"]
            selections[149]["court"] = selections[148]["court"]
        else:
            selections[149]["target_motion_entry_numbers"] = selections[148][
                "target_motion_entry_numbers"
            ]
            selections[149]["case_id"] = selections[148]["case_id"]
        full["selection.jsonl"] = _jsonl_bytes(selections)
        inputs["full_pool_artifacts"] = full
        with pytest.raises(RetainedCohortExtensionError, match=message):
            extend_target_cohort(**inputs)


def test_extension_accounts_for_exact_cap_and_disjoint_obligations() -> None:
    inputs = _inputs(paid_after=100)
    inputs["max_projected_budget_usd"] = "153.50"
    inputs["reserved_obligation_usd"] = "0.50"

    exact = extend_target_cohort(**inputs)

    assert exact.combined_budget["base_projected_usd"] == "0.00"
    assert exact.combined_budget["incremental_projected_usd"] == "152.50"
    assert exact.combined_budget["reserved_obligation_usd"] == "0.50"
    assert exact.combined_budget["cumulative_obligation_usd"] == "153.00"
    inputs["max_projected_budget_usd"] = "152.99"
    with pytest.raises(RetainedCohortExtensionError, match="cannot meet"):
        extend_target_cohort(**inputs)


def test_extension_counts_unknown_and_writeoff_and_enforces_per_case_cap() -> None:
    inputs = _inputs(paid_after=100)
    inputs.update(
        {
            "max_projected_budget_usd": "160.00",
            "unknown_obligation_usd": "3.05",
            "write_off_obligation_usd": "3.05",
        }
    )
    extension = extend_target_cohort(**inputs)
    assert extension.combined_budget["unknown_obligation_usd"] == "3.05"
    assert extension.combined_budget["write_off_obligation_usd"] == "3.05"
    assert extension.combined_budget["cumulative_obligation_usd"] == "158.60"

    inputs["max_missing_core_documents_per_case"] = 0
    with pytest.raises(RetainedCohortExtensionError, match="positive"):
        extend_target_cohort(**inputs)


def _inputs(*, paid_after: int | None = None) -> dict[str, Any]:
    candidate_ids = tuple(_candidate_id(index) for index in range(151))
    selections = [_selection(index) for index in range(151)]
    relevance = [
        _relevance(index, paid=paid_after is not None and index >= paid_after)
        for index in range(151)
    ]
    downloads = [_download(index) for index in range(151)]
    clearance = [_clearance(index) for index in range(151)]
    base_projection = project_target_cohort(
        selections=selections,
        case_relevance=relevance,
        download_manifest=downloads,
        clearance_records=clearance,
        target_case_count=100,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="2250.00",
        max_missing_core_documents_per_case=24,
    )
    base_artifacts = _base_artifacts(base_projection)
    return {
        "base_projection_artifacts": base_artifacts,
        "full_pool_artifacts": {
            "selection.jsonl": _jsonl_bytes(selections),
            "case-relevance.jsonl": _jsonl_bytes(relevance),
            "document-downloads-merged.jsonl": _jsonl_bytes(downloads),
            "disclosure-clearance.jsonl": _jsonl_bytes(clearance),
        },
        "cohort_policy_artifact": _cohort_policy(),
        "snapshot_manifest_sha256": "sha256:" + "b" * 64,
        "snapshot_cycle_hash": "c" * 64,
        "snapshot_batch_digest": "d" * 64,
        "cost_per_document_usd": "3.05",
        "max_projected_budget_usd": "2250.00",
        "max_missing_core_documents_per_case": 24,
        "reserved_obligation_usd": "0.00",
        "unknown_obligation_usd": "0.00",
        "write_off_obligation_usd": "0.00",
    }


def _base_artifacts(projection: Any) -> dict[str, bytes]:
    records: dict[str, bytes] = {
        "target-cohort-selection.jsonl": _jsonl_bytes(projection.selections),
        "case-relevance.jsonl": _jsonl_bytes(projection.case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(
            projection.download_manifest
        ),
        "disclosure-clearance.jsonl": _jsonl_bytes(projection.clearance_records),
        "restriction-evidence.jsonl": _jsonl_bytes(
            projection.restriction_evidence
        ),
        "core-filter-results.jsonl": _jsonl_bytes(
            row.to_record() for row in projection.core_filter_results
        ),
        "missing-core-budget-plan.json": _json_bytes(
            projection.budget_plan.to_record()
        ),
    }
    summary = dict(projection.summary)
    summary["output_commitments"] = {
        name: _sha(payload) for name, payload in sorted(records.items())
    }
    records["target-cohort-projection.json"] = _json_bytes(summary)
    return records


def _cohort_policy() -> dict[str, Any]:
    return generate_cohort_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_acquisition_hash": "c" * 64,
            "eligibility_anchor": "2026-06-30",
            "stop_rule": {
                "mode": "target_or_deadline",
                "target_clean_cases": 150,
                "search_window_end": "2026-07-14",
                "stop_on_frontier_exhaustion": True,
                "stop_on_budget_headroom_exhaustion": True,
            },
            "window_policy": {
                "overlap_days": 1,
                "backfill_late_indexed": True,
                "refresh_before_purchase": True,
            },
            "refresh_policy": {
                "evidence_precedence": {
                    "transient": 0,
                    "excluded_refreshable": 10,
                    "accepted": 20,
                    "newly_free": 30,
                    "excluded_immutable": 100,
                },
                "transition_semantics": {
                    "higher_rank_supersedes_lower_rank": True,
                    "latest_wins_equal_rank": True,
                    "transient_supersedes_evidenced": False,
                    "immutable_reconsideration": "never",
                },
                "transient_reason_codes": ["fetch_error"],
                "refreshable_reason_codes": ["oversized_docket_soft_skip"],
                "newly_free_reason_codes": ["newly_free"],
                "accepted_reason_codes": ["strict_clean_screen_passed"],
                "immutable_reason_codes": ["decision_before_release_anchor"],
            },
            "packet_completeness": {
                "motion_or_combined_memorandum_required": True,
                "opposition_required_if_docketed": True,
                "reply_required": False,
            },
            "target_motion": {
                "selector": "earliest_eligible_mtd_then_lowest_entry_number",
                "exactly_one_per_candidate": True,
            },
            "purchase_policy": {
                "rule": "buy_cheapest_complete",
                "cycle_budget_usd": "2250.00",
                "max_per_case_usd": "73.20",
                "reservation_headroom_required": True,
            },
            "disclosure_clearance": {
                "all_documents_require_clearance": True,
                "unknown_or_unscannable": "quarantine",
                "replacement_rule": "next_cheapest_eligible_under_same_cap",
            },
            "reduced_n": {
                "target_clean_cases": 150,
                "below_minimum_action": "pilot_only_no_official_cycle",
                "claim_tiers": [
                    {
                        "maximum_clean_cases": 150,
                        "minimum_clean_cases": 1,
                        "claim_class": "target",
                        "minimum_prediction_units": None,
                        "insufficient_units_action": None,
                    }
                ],
            },
        }
    )


def _candidate_id(index: int) -> str:
    return f"case-{index:03d}"


def _selection(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "candidate_id": candidate_id,
        "case_id": f"docket-{index:03d}",
        "case_name": f"Case {index}",
        "court": "nysd",
        "docket_number": f"1:26-cv-{index:05d}",
        "target_motion_entry_numbers": [index + 10],
        "decision_date": "2026-07-01",
        "selected": True,
    }


def _relevance(index: int, *, paid: bool) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    documents = [
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
    documents.append(
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-mtd",
            "setup_runner_label": "core_mtd",
            "document_role": "motion_to_dismiss_memorandum",
            "availability_status": "unavailable" if paid else "available",
            "requires_paid_recovery": paid,
            "model_visible": True,
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
            "restriction_evidence": [
                "courtlistener_rest_recap_document_exact_match"
                if paid
                else "courtlistener_public_download_record_checked"
            ],
        }
    )
    return {"candidate_id": candidate_id, "documents": documents}


def _download(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-complaint",
        "local_path": f"{candidate_id}/complaint.pdf",
        "sha256": "a" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }


def _clearance(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-complaint",
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


def _jsonl(payload: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in payload.splitlines() if line]


def _jsonl_bytes(records: Any) -> bytes:
    return b"".join(
        (json.dumps(dict(record), sort_keys=True, allow_nan=False) + "\n").encode()
        for record in records
    )


def _json_bytes(record: dict[str, Any]) -> bytes:
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

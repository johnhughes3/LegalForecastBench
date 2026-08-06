# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnusedVariable=false

from __future__ import annotations

import hashlib
import inspect
from copy import deepcopy
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)
from legalforecast.ingestion.exact100_reserve_extension import (
    Exact100ReserveExtensionError,
    extend_exact100_reserve,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(_json_bytes(record) for record in records)


def _value_sha(value: object) -> str:
    return _sha(
        canonical_json_value_bytes(
            value, error_type=ValueError, error_message="test serialization failed"
        )
    )


def _fixture() -> dict[str, Any]:
    originals = [f"O{number:03d}" for number in range(1, 101)]
    reserves = [f"R{number}" for number in range(1, 6)]
    cleared_absent = [f"C{number}" for number in range(1, 7)]
    final_quarantine = ["Q1", "Q2", "Q3"]
    zero_cost = "C0"
    source_ids = [*originals, *reserves, *cleared_absent, *final_quarantine, zero_cost]
    assert len(source_ids) == 115

    costs = {
        "C1": (1, "3.05"),
        "C2": (2, "6.10"),
        "C3": (2, "6.10"),
        "C4": (2, "6.10"),
        "C5": (2, "6.10"),
        "C6": (3, "9.15"),
        "R1": (3, "9.15"),
        "R2": (4, "12.20"),
        "R3": (4, "12.20"),
        "R4": (4, "12.20"),
        "R5": (4, "12.20"),
    }
    for candidate_id in source_ids:
        costs.setdefault(candidate_id, (0, "0.00"))
    ordered = sorted(
        source_ids, key=lambda item: (costs[item][0], costs[item][1], item)
    )

    source = [
        {
            "candidate_id": candidate_id,
            "case_id": candidate_id,
            "case_name": f"Case {candidate_id}",
            "court": "ord",
            "decision_date": "2026-06-30",
            "selected": True,
        }
        for candidate_id in source_ids
    ]
    source_bytes = _jsonl(source)
    candidates = []
    for rank, candidate_id in enumerate(ordered, start=1):
        missing_count, cost = costs[candidate_id]
        candidates.append(
            {
                "rank": rank,
                "candidate_id": candidate_id,
                "purchase_document_ids": [
                    f"{candidate_id}-D{index}" for index in range(1, missing_count + 1)
                ],
                "missing_core_document_count": missing_count,
                "estimated_purchase_count": missing_count,
                "missing_core_roles": ["motion_to_dismiss_memorandum"] * missing_count,
                "estimated_cost_usd": cost,
                "exclusion_reasons": [],
                "court": "ord",
                "nos_macro_category": None,
                "related_family_id": None,
                "mdl_family_id": None,
                "selection_status": (
                    "selected" if candidate_id in originals else "eligible_omitted"
                ),
            }
        )
    frontier_policy = {
        "target_case_count": 100,
        "candidate_count": 115,
        "selected_candidate_count": 100,
        "frontier_truncated": False,
        "source_commitments": {
            "snapshot_manifest_sha256": _sha(b"snapshot"),
            "preparation_config_sha256": _sha(b"config"),
            "preparation_summary_sha256": _sha(b"summary"),
            "preparation_success_run_card_sha256": _sha(b"success"),
            "reconciled_selection_sha256": _sha(source_bytes),
            "case_relevance_sha256": _sha(b"relevance"),
            "download_manifest_sha256": _sha(b"manifest"),
            "core_filter_results_sha256": _sha(b"filter"),
            "provisional_budget_plan_sha256": _sha(b"budget"),
            "restriction_evidence_sha256": _sha(b"restriction"),
            "disclosure_review_requests_sha256": _sha(b"review"),
        },
        "clearance_contract": {},
        "candidates": candidates,
    }
    frontier = {
        "schema_version": "legalforecast.target_cohort_candidate_frontier.v1",
        "policy": frontier_policy,
        "policy_sha256": _value_sha(frontier_policy),
    }
    frontier_bytes = _json_bytes(frontier)
    frontier_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "materialize-target-cohort-frontier",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "record_count": 115,
        "target_case_count": 100,
        "frontier_sha256": _sha(frontier_bytes),
        "output_commitments": {"full_candidate_frontier": _sha(frontier_bytes)},
        "zero_provider_activity_evidence": True,
        "source_commitments": {
            "preparation_summary": _sha(b"summary"),
            "preparation_config": _sha(b"config"),
            "snapshot_manifest": _sha(b"snapshot"),
            "preparation_success_run_card": _sha(b"success"),
        },
    }
    frontier_card_bytes = _json_bytes(frontier_card)

    original_selection = [row for row in source if row["candidate_id"] in originals]
    original_selection_bytes = _jsonl(original_selection)
    original_reserve = []
    for reserve_rank, candidate_id in enumerate(reserves, start=1):
        row = next(item for item in candidates if item["candidate_id"] == candidate_id)
        original_reserve.append(
            {
                "schema_version": "legalforecast.target_cohort_ranked_reserve.v1",
                "candidate_id": candidate_id,
                "case_id": candidate_id,
                "court": "ord",
                "decision_date": "2026-06-30",
                "frontier_rank": 100 + reserve_rank,
                "reserve_rank": reserve_rank,
                "missing_core_document_count": row["missing_core_document_count"],
                "estimated_cost_usd": row["estimated_cost_usd"],
                "missing_core_roles": row["missing_core_roles"],
                "purchase_document_ids": row["purchase_document_ids"],
                "ranking_key": [
                    row["missing_core_document_count"],
                    row["estimated_cost_usd"],
                    candidate_id,
                ],
            }
        )
    original_reserve_bytes = _jsonl(original_reserve)
    omitted = [*reserves, *cleared_absent, *final_quarantine, zero_cost]
    original_exclusions = [
        {"candidate_id": candidate_id, "reason": "disclosure_clearance_quarantined"}
        for candidate_id in omitted
    ]
    original_exclusions_bytes = _jsonl(original_exclusions)
    original_projection = {
        "schema_version": "legalforecast.target_cohort_projection.v1",
        "target_case_count": 100,
        "selected_case_count": 100,
        "ranked_reserve_case_count": 5,
        "resolved_pool_case_count": 115,
        "post_clearance_case_count": 105,
        "ranking_policy": {
            "attributes": [
                "missing_core_document_count",
                "estimated_cost_usd",
                "candidate_id",
            ],
            "output_blind": True,
            "tie_breaker": "candidate_id",
        },
        "input_commitments": {
            "/frozen/public-packet-selection-reconciled.jsonl": _sha(source_bytes)
        },
        "output_commitments": {
            "target-cohort-selection.jsonl": _sha(original_selection_bytes),
            "target-cohort-ranked-reserve.jsonl": _sha(original_reserve_bytes),
            "target-cohort-exclusions.jsonl": _sha(original_exclusions_bytes),
        },
    }
    original_projection["projection_sha256"] = _sha(_json_bytes(original_projection))
    original_projection_bytes = _json_bytes(original_projection)

    exact_ids = [*originals[:97], "R1", "R2", zero_cost]
    exact_selection = [
        row
        for candidate_id in exact_ids
        for row in source
        if row["candidate_id"] == candidate_id
    ]
    exact_selection_bytes = _jsonl(exact_selection)
    exact_projection: dict[str, Any] = {
        "schema_version": "legalforecast.zero_cost_successor_config.v1",
        "target_case_count": 100,
        "selection_sha256": _sha(exact_selection_bytes),
        "hard_cap_usd": "567.30",
        "paid_activity_permitted": False,
        "provider_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
        "output_commitments": {
            "target-cohort-selection.jsonl": _sha(exact_selection_bytes)
        },
        "source_commitments": {
            "target_projection": _sha(_json_bytes(original_projection)),
            "disclosure_clearance": "pending",
            "disclosure_clearance_run_card": "pending",
        },
    }

    final_clearance = [
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-A",
            "status": "quarantined",
        }
        for candidate_id in final_quarantine
    ] + [
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-A",
            "status": "cleared",
        }
        for candidate_id in [*cleared_absent, zero_cost]
    ]
    final_clearance_bytes = _jsonl(final_clearance)
    final_clearance_card = {
        "schema_version": "legalforecast.provenance_model_clearance_run_card.v1",
        "stage": "finalize-provenance-quarantine",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_commitments": {
            "disclosure_clearance": {"sha256": _sha(final_clearance_bytes)}
        },
        "source_commitments": {"authenticated_source": {"sha256": _sha(b"source")}},
    }
    final_clearance_card_bytes = _json_bytes(final_clearance_card)
    exact_projection["source_commitments"]["disclosure_clearance"] = _sha(
        final_clearance_bytes
    )
    exact_projection["source_commitments"]["disclosure_clearance_run_card"] = _sha(
        final_clearance_card_bytes
    )

    current_quarantine = [
        {"candidate_id": candidate_id, "reason": "disclosure_quarantined"}
        for candidate_id in exact_ids[:4]
    ]
    current_quarantine_bytes = _jsonl(current_quarantine)
    current_quarantine_card = {
        "schema_version": "legalforecast.disclosure_quarantine_run_card.v1",
        "stage": "finalize-disclosure-quarantine",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_commitments": {
            "disclosure_quarantine": {"sha256": _sha(current_quarantine_bytes)}
        },
        "source_commitments": {"authenticated_source": {"sha256": _sha(b"source-2")}},
    }
    current_quarantine_card_bytes = _json_bytes(current_quarantine_card)
    return locals()


def _plan(inputs: dict[str, Any]):
    return extend_exact100_reserve(
        authenticated_exact_successor=inputs["exact_projection"],
        exact_successor_projection=inputs["exact_projection"],
        exact_selection_bytes=inputs["exact_selection_bytes"],
        authenticated_full_frontier=inputs.get(
            "authenticated_full_frontier", inputs["frontier"]
        ),
        full_frontier=inputs["frontier"],
        full_frontier_bytes=inputs["frontier_bytes"],
        frontier_run_card=inputs["frontier_card"],
        frontier_run_card_bytes=inputs["frontier_card_bytes"],
        source_pool_bytes=inputs["source_bytes"],
        original_projection=inputs["original_projection"],
        original_projection_bytes=inputs["original_projection_bytes"],
        original_selection_bytes=inputs["original_selection_bytes"],
        original_reserve_bytes=inputs["original_reserve_bytes"],
        original_exclusions_bytes=inputs["original_exclusions_bytes"],
        final_clearance_bytes=inputs["final_clearance_bytes"],
        final_clearance_run_card=inputs["final_clearance_card"],
        final_clearance_run_card_bytes=inputs["final_clearance_card_bytes"],
        current_quarantine_bytes=inputs["current_quarantine_bytes"],
        authenticated_current_quarantine_run_card=inputs.get(
            "authenticated_current_quarantine_run_card",
            inputs["current_quarantine_card"],
        ),
        current_quarantine_run_card=inputs["current_quarantine_card"],
        current_quarantine_run_card_bytes=inputs["current_quarantine_card_bytes"],
        required_replacement_count=4,
    )


def _reauthorize_mutated_fixture(inputs: dict[str, Any]) -> None:
    """Refresh enclosing hashes so tests reach the intended semantic gate."""

    inputs["frontier"]["policy_sha256"] = _value_sha(inputs["frontier"]["policy"])
    inputs["frontier_bytes"] = _json_bytes(inputs["frontier"])
    frontier_sha = _sha(inputs["frontier_bytes"])
    inputs["frontier_card"]["frontier_sha256"] = frontier_sha
    inputs["frontier_card"]["output_commitments"] = {
        "full_candidate_frontier": frontier_sha
    }
    inputs["frontier_card_bytes"] = _json_bytes(inputs["frontier_card"])
    inputs["final_clearance_card_bytes"] = _json_bytes(inputs["final_clearance_card"])
    inputs["current_quarantine_bytes"] = _jsonl(inputs["current_quarantine"])
    inputs["current_quarantine_card"]["output_commitments"] = {
        "disclosure_quarantine": {"sha256": _sha(inputs["current_quarantine_bytes"])}
    }
    inputs["current_quarantine_card_bytes"] = _json_bytes(
        inputs["current_quarantine_card"]
    )


def test_extension_preserves_selection_and_derives_ranked_candidates() -> None:
    inputs = _fixture()
    plan = _plan(inputs)

    assert plan.selected_cohort_bytes is inputs["exact_selection_bytes"]
    assert [row["candidate_id"] for row in plan.ranked_reserve] == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "R3",
        "R4",
        "R5",
    ]
    assert [row["candidate_id"] for row in plan.free_refresh_inputs] == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "R3",
        "R4",
        "R5",
    ]
    assert plan.cost_plan["paid_permitted"] is False
    assert plan.cost_plan["required_replacement_count"] == 4
    assert plan.cost_plan["required_replacement_max_cost_usd"] == "21.35"
    assert plan.summary["provider_activity_permitted"] is False
    assert plan.summary["paid_activity_permitted"] is False
    assert plan.summary["evaluation_authorized"] is False
    assert plan.summary["freeze_authorized"] is False
    assert plan.summary["dispatch_authorized"] is False
    assert plan.summary["output_commitments"]["target-cohort-selection.jsonl"] == (
        _sha(inputs["exact_selection_bytes"])
    )
    assert "candidate_ids" not in inspect.signature(extend_exact100_reserve).parameters


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["exact_projection"].update({"target_case_count": 99}),
            "exact successor",
        ),
        (
            lambda value: value.update({"authenticated_exact_successor": {}}),
            "exact successor replay",
        ),
        (
            lambda value: value.update({"authenticated_full_frontier": {}}),
            "full frontier replay",
        ),
        (
            lambda value: value.update(
                {"authenticated_current_quarantine_run_card": {}}
            ),
            "current quarantine replay",
        ),
        (
            lambda value: value["frontier"]["policy"]["source_commitments"].pop(
                "case_relevance_sha256"
            ),
            "frontier source commitments",
        ),
        (
            lambda value: value.update(
                {"exact_selection_bytes": value["exact_selection_bytes"] + b"\n"}
            ),
            "selection",
        ),
        (
            lambda value: value["frontier"]["policy"].update(
                {"frontier_truncated": True}
            ),
            "untruncated",
        ),
        (lambda value: value["frontier"]["policy"]["candidates"].pop(), "115"),
        (lambda value: value["frontier"]["policy"]["candidates"].reverse(), "rank"),
        (
            lambda value: value["frontier_card"].update({"status": "running"}),
            "frontier run card",
        ),
        (
            lambda value: value["original_reserve"][2].update(
                {"estimated_cost_usd": "9.15"}
            ),
            "reserve",
        ),
        (
            lambda value: value["final_clearance_card"].update({"status": "running"}),
            "clearance run card",
        ),
        (
            lambda value: value["current_quarantine"].append(
                {"candidate_id": "NOT-SELECTED", "reason": "x"}
            ),
            "outside exact selection",
        ),
    ],
)
def test_extension_fails_closed_on_tampered_authority(
    mutation: Any, message: str
) -> None:
    inputs = _fixture()
    inputs["authenticated_exact_successor"] = inputs["exact_projection"]
    mutation(inputs)
    if "original_reserve" in inputs:
        inputs["original_reserve_bytes"] = _jsonl(inputs["original_reserve"])
    _reauthorize_mutated_fixture(inputs)
    with pytest.raises(Exact100ReserveExtensionError, match=message):
        extend_exact100_reserve(
            authenticated_exact_successor=inputs["authenticated_exact_successor"],
            exact_successor_projection=inputs["exact_projection"],
            exact_selection_bytes=inputs["exact_selection_bytes"],
            authenticated_full_frontier=inputs.get(
                "authenticated_full_frontier", inputs["frontier"]
            ),
            full_frontier=inputs["frontier"],
            full_frontier_bytes=inputs["frontier_bytes"],
            frontier_run_card=inputs["frontier_card"],
            frontier_run_card_bytes=inputs["frontier_card_bytes"],
            source_pool_bytes=inputs["source_bytes"],
            original_projection=inputs["original_projection"],
            original_projection_bytes=inputs["original_projection_bytes"],
            original_selection_bytes=inputs["original_selection_bytes"],
            original_reserve_bytes=inputs["original_reserve_bytes"],
            original_exclusions_bytes=inputs["original_exclusions_bytes"],
            final_clearance_bytes=inputs["final_clearance_bytes"],
            final_clearance_run_card=inputs["final_clearance_card"],
            final_clearance_run_card_bytes=inputs["final_clearance_card_bytes"],
            current_quarantine_bytes=inputs["current_quarantine_bytes"],
            authenticated_current_quarantine_run_card=inputs.get(
                "authenticated_current_quarantine_run_card",
                inputs["current_quarantine_card"],
            ),
            current_quarantine_run_card=inputs["current_quarantine_card"],
            current_quarantine_run_card_bytes=inputs["current_quarantine_card_bytes"],
            required_replacement_count=4,
        )


def test_extension_rejects_duplicate_quarantine_and_insufficient_capacity() -> None:
    inputs = _fixture()
    inputs["current_quarantine"].append(deepcopy(inputs["current_quarantine"][0]))
    _reauthorize_mutated_fixture(inputs)
    with pytest.raises(
        Exact100ReserveExtensionError, match="duplicate current quarantine"
    ):
        _plan(inputs)

    inputs = _fixture()
    inputs["current_quarantine"] = [
        {"candidate_id": candidate_id, "reason": "disclosure_quarantined"}
        for candidate_id in inputs["exact_ids"][:10]
    ]
    _reauthorize_mutated_fixture(inputs)
    with pytest.raises(
        Exact100ReserveExtensionError, match="insufficient authenticated reserve"
    ):
        extend_exact100_reserve(
            authenticated_exact_successor=inputs["exact_projection"],
            exact_successor_projection=inputs["exact_projection"],
            exact_selection_bytes=inputs["exact_selection_bytes"],
            authenticated_full_frontier=inputs["frontier"],
            full_frontier=inputs["frontier"],
            full_frontier_bytes=inputs["frontier_bytes"],
            frontier_run_card=inputs["frontier_card"],
            frontier_run_card_bytes=inputs["frontier_card_bytes"],
            source_pool_bytes=inputs["source_bytes"],
            original_projection=inputs["original_projection"],
            original_projection_bytes=inputs["original_projection_bytes"],
            original_selection_bytes=inputs["original_selection_bytes"],
            original_reserve_bytes=inputs["original_reserve_bytes"],
            original_exclusions_bytes=inputs["original_exclusions_bytes"],
            final_clearance_bytes=inputs["final_clearance_bytes"],
            final_clearance_run_card=inputs["final_clearance_card"],
            final_clearance_run_card_bytes=inputs["final_clearance_card_bytes"],
            current_quarantine_bytes=inputs["current_quarantine_bytes"],
            authenticated_current_quarantine_run_card=inputs["current_quarantine_card"],
            current_quarantine_run_card=inputs["current_quarantine_card"],
            current_quarantine_run_card_bytes=inputs["current_quarantine_card_bytes"],
            required_replacement_count=10,
        )

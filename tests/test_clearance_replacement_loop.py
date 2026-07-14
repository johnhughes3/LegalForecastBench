from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.clearance_replacement import (
    ClearanceReplacementError,
    build_replacement_frontier,
    plan_clearance_replacements,
    verify_replacement_frontier,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)


def test_quarantined_purchase_is_replaced_once_and_writeoff_stays_committed(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)

    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        first = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
        second = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )

        assert journal.committed_amount_usd == "3.05"
        assert journal.replacement_events() == first.ledger_records

    assert first.to_record() == second.to_record()
    assert first.active_candidate_ids == ("100", "300")
    assert first.replacement_plan.case_plans[0].candidate_id == "300"
    assert first.replacement_plan.case_plans[0].purchase_document_ids == ("303",)
    assert len(first.ledger_records) == 1
    event = first.ledger_records[0]
    assert event["quarantined_candidate_id"] == "200"
    assert event["replacement_candidate_id"] == "300"
    assert event["write_off_cost_usd"] == "3.05"
    assert event["committed_spend_before_usd"] == "3.05"
    assert event["headroom_after_usd"] == "3.90"
    assert event["attempted_candidate_ids"] == ["100", "200", "300"]
    assert event["previous_record_sha256"] is None
    assert str(event["record_sha256"]).startswith("sha256:")


def test_case_mix_recomputed_from_retained_cases_and_uncapped_is_explicit(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy(hard_cap="20.00")
    policy_artifact = _purchase_policy(tmp_path, cohort, hard_cap="20.00")
    policy = verify_case_dev_purchase_policy(policy_artifact)
    rows = _frontier_rows()
    rows[0]["court"] = "Court A"
    rows[1]["court"] = "Court A"
    rows[2]["court"] = "Court A"
    rows.append(
        {
            "candidate_id": "400",
            "purchase_document_ids": ["404"],
            "missing_core_document_count": 1,
            "estimated_purchase_count": 1,
            "missing_core_roles": ["opposition"],
            "estimated_cost_usd": "3.05",
            "exclusion_reasons": [],
            "court": "Court B",
            "nos_macro_category": "nos-b",
            "related_family_id": None,
            "mdl_family_id": None,
        }
    )
    capped = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=rows,
        case_mix_max_per_bucket=1,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )
    uncapped = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=rows,
        case_mix_max_per_bucket=None,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )

    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        result = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=capped,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
    assert result.active_candidate_ids == ("100", "400")
    assert result.ledger_records[0]["case_mix_counts_after"]["court"] == {
        "Court A": 1,
        "Court B": 1,
    }
    assert uncapped["policy"]["case_mix_max_per_bucket"] is None


@pytest.mark.parametrize(
    ("hard_cap", "expected_replacement"),
    (("6.10", "300"), ("6.09", None)),
)
def test_exact_headroom_boundary_and_one_cent_over(
    tmp_path: Path, hard_cap: str, expected_replacement: str | None
) -> None:
    cohort = _cohort_policy(hard_cap=hard_cap)
    policy_artifact = _purchase_policy(tmp_path, cohort, hard_cap=hard_cap)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        result = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
    assert result.ledger_records[0]["replacement_candidate_id"] == expected_replacement
    assert result.stop_reason == (
        "target_reached" if expected_replacement else "budget_headroom_exhausted"
    )


def test_frontier_and_unresolved_purchase_fail_closed(tmp_path: Path) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)
    tampered = deepcopy(frontier)
    tampered["policy"]["candidates"][0]["rank"] = 2
    with pytest.raises(ClearanceReplacementError, match="hash"):
        verify_replacement_frontier(tampered)

    missing_b = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=(_frontier_rows()[0], _frontier_rows()[2]),
        case_mix_max_per_bucket=None,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )
    with pytest.raises(ClearanceReplacementError, match="initial selected"):
        verify_replacement_frontier(missing_b)

    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        journal.plan(_single_case_plan("200", "202"))
        assert journal.submit("202") is True
        with pytest.raises(ClearanceReplacementError, match="unresolved"):
            plan_clearance_replacements(
                cohort_policy_artifact=cohort,
                purchase_policy_artifact=policy_artifact,
                frontier_artifact=frontier,
                purchase_journal=journal,
                purchased_clearance_records=(),
                clearance_run_card_sha256="sha256:" + "1" * 64,
            )


def test_full_frontier_accepts_only_truthful_per_case_cap_exclusions(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy(hard_cap="20.00")
    policy_artifact = _purchase_policy(tmp_path, cohort, hard_cap="20.00")
    over_cap = {
        "candidate_id": "400",
        "purchase_document_ids": ["401", "402", "403", "404"],
        "missing_core_document_count": 4,
        "estimated_purchase_count": 4,
        "missing_core_roles": ["motion"],
        "estimated_cost_usd": "12.20",
        "exclusion_reasons": ["missing_core_document_cap_exceeded"],
        "court": "Court D",
        "nos_macro_category": "nos-d",
        "related_family_id": None,
        "mdl_family_id": None,
    }

    artifact = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=(*_frontier_rows(), over_cap),
        case_mix_max_per_bucket=None,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )
    assert artifact["policy"]["candidate_count"] == 4

    false_exclusion = dict(_frontier_rows()[2])
    false_exclusion["exclusion_reasons"] = ["missing_core_document_cap_exceeded"]
    with pytest.raises(ClearanceReplacementError, match="false per-case cap"):
        build_replacement_frontier(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            projection_sha256="sha256:" + "a" * 64,
            initial_selected_candidate_ids=("100", "200"),
            candidate_rows=(*_frontier_rows()[:2], false_exclusion),
            case_mix_max_per_bucket=None,
            source_commitments={"pool": "sha256:" + "b" * 64},
        )


def test_unrelated_counted_writeoff_reduces_replacement_headroom(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        journal.plan(_single_case_plan("historical", "909"))
        assert journal.submit("909") is True
        journal.mark_unknown("909", "provider outcome ambiguous")
        journal.reconcile(
            {
                "source_document_id": "909",
                "disposition": "write_off",
                "source_type": "support_confirmation",
                "source_reference": "support://ticket/1",
                "pacer_fees": None,
                "download_url": None,
            }
        )

        result = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )

    assert result.ledger_records[0]["committed_spend_before_usd"] == "6.10"
    assert result.ledger_records[0]["headroom_after_usd"] == "0.85"


def test_replacement_event_hash_chain_detects_storage_tampering(tmp_path: Path) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
        with sqlite3.connect(policy.canonical_ledger_path) as connection:
            connection.execute(
                "UPDATE replacement_events SET record_json = replace("
                "record_json, '3.05', '3.04') WHERE sequence = 0"
            )
        with pytest.raises(CaseDevPurchaseLedgerError, match="hash"):
            journal.replacement_events()


def test_replacement_event_hash_chain_detects_stored_hash_column_tampering(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    frontier = _frontier(cohort, policy_artifact)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
        with sqlite3.connect(policy.canonical_ledger_path) as connection:
            connection.execute(
                "UPDATE replacement_events SET record_sha256 = ? WHERE sequence = 0",
                ("sha256:" + "f" * 64,),
            )
        with pytest.raises(CaseDevPurchaseLedgerError, match="stored hash column"):
            journal.replacement_events()


def test_later_clearance_run_card_selects_only_the_next_unbilled_replacement(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy(hard_cap="20.00")
    policy_artifact = _purchase_policy(tmp_path, cohort, hard_cap="20.00")
    policy = verify_case_dev_purchase_policy(policy_artifact)
    rows = _frontier_rows()
    rows.append(
        {
            "candidate_id": "400",
            "purchase_document_ids": ["404"],
            "missing_core_document_count": 1,
            "estimated_purchase_count": 1,
            "missing_core_roles": ["opposition"],
            "estimated_cost_usd": "3.05",
            "exclusion_reasons": [],
            "court": "Court D",
            "nos_macro_category": "nos-d",
            "related_family_id": None,
            "mdl_family_id": None,
        }
    )
    frontier = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=rows,
        case_mix_max_per_bucket=None,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
        first = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(_clearance("200", "202", "quarantined"),),
            clearance_run_card_sha256="sha256:" + "1" * 64,
        )
        assert [plan.candidate_id for plan in first.replacement_plan.case_plans] == [
            "300"
        ]

        _confirm_candidate(journal, "300", "303", actual="3.05")
        second = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(
                _clearance("200", "202", "quarantined"),
                _clearance("300", "303", "quarantined"),
            ),
            clearance_run_card_sha256="sha256:" + "2" * 64,
        )

    assert second.active_candidate_ids == ("100", "400")
    assert [plan.candidate_id for plan in second.replacement_plan.case_plans] == ["400"]
    assert len(second.ledger_records) == 2
    assert (
        second.ledger_records[1]["previous_record_sha256"]
        == (second.ledger_records[0]["record_sha256"])
    )
    assert (
        second.ledger_records[0]["clearance_run_card_sha256"]
        != (second.ledger_records[1]["clearance_run_card_sha256"])
    )


def test_cli_separates_broad_allowlist_from_narrow_iteration(tmp_path: Path) -> None:
    cohort = _cohort_policy()
    policy_artifact = _purchase_policy(tmp_path, cohort)
    policy = verify_case_dev_purchase_policy(policy_artifact)
    cohort_path = _write_json(tmp_path / "cohort.json", cohort)
    policy_path = _write_json(tmp_path / "purchase-policy.json", policy_artifact)
    projection_path = _write_json(tmp_path / "projection.json", {"frozen": True})
    selection_path = _write_json(
        tmp_path / "initial-selection.json",
        {"selected_candidate_ids": ["100", "200"]},
    )
    candidates_path = _write_json(tmp_path / "frontier.json", _frontier_rows())
    frontier_path = tmp_path / "replacement-frontier.json"
    upfront_broad_path = tmp_path / "upfront-broker-allowlist-plan.json"

    assert (
        main(
            [
                "acquisition",
                "build-clearance-replacement-frontier",
                "--cohort-policy",
                str(cohort_path),
                "--purchase-policy",
                str(policy_path),
                "--projection",
                str(projection_path),
                "--initial-selection",
                str(selection_path),
                "--candidate-frontier",
                str(candidates_path),
                "--source",
                f"snapshot={projection_path}",
                "--output",
                str(frontier_path),
                "--broker-allowlist-plan-output",
                str(upfront_broad_path),
            ]
        )
        == 0
    )

    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path, policy=policy, allow_create=True
    ) as journal:
        _confirm_candidate(journal, "200", "202", actual="3.05")
    clearance_path = tmp_path / "purchased-clearance.jsonl"
    clearance_path.write_text(
        json.dumps(_clearance("200", "202", "quarantined")) + "\n",
        encoding="utf-8",
    )
    run_card_path = _write_json(tmp_path / "clearance-run-card.json", {"ok": True})
    result_path = tmp_path / "replacement-result.json"
    narrow_path = tmp_path / "replacement-budget-plan.json"
    broad_path = tmp_path / "broker-allowlist-plan.json"
    exclusions_path = tmp_path / "replacement-exclusions.jsonl"

    assert (
        main(
            [
                "acquisition",
                "plan-clearance-replacements",
                "--cohort-policy",
                str(cohort_path),
                "--purchase-policy",
                str(policy_path),
                "--frontier",
                str(frontier_path),
                "--purchase-ledger",
                str(policy.canonical_ledger_path),
                "--purchased-clearance",
                str(clearance_path),
                "--clearance-run-card",
                str(run_card_path),
                "--output",
                str(result_path),
                "--replacement-budget-plan-output",
                str(narrow_path),
                "--broker-allowlist-plan-output",
                str(broad_path),
                "--exclusions-output",
                str(exclusions_path),
            ]
        )
        == 0
    )
    narrow = json.loads(narrow_path.read_text())
    broad = json.loads(broad_path.read_text())
    upfront_broad = json.loads(upfront_broad_path.read_text())
    assert narrow["dry_run"] is False
    assert [row["candidate_id"] for row in narrow["case_plans"]] == ["300"]
    assert broad["dry_run"] is True
    assert [row["candidate_id"] for row in broad["case_plans"]] == ["200", "300"]
    assert all(row["dry_run"] is True for row in broad["case_plans"])
    assert broad == upfront_broad

    broker_selection_path = _write_json(
        tmp_path / "broker-selection.json", _broker_selection()
    )
    broker_policy_path = tmp_path / "broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--budget-plan",
                str(upfront_broad_path),
                "--selection",
                str(broker_selection_path),
                "--broad-frontier-allowlist",
                "--output",
                str(broker_policy_path),
            ]
        )
        == 0
    )
    broker_policy = json.loads(broker_policy_path.read_text())
    assert broker_policy["allowed_documents"] == [
        {"case_id": "200", "recap_document": "202"},
        {"case_id": "300", "recap_document": "303"},
    ]


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _broker_selection() -> list[dict[str, object]]:
    evidence = [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_sealed_false",
    ]
    return [
        {
            "candidate_id": candidate_id,
            "selected": False,
            "exclusion_reasons": ["reserve_for_clearance_replacement"],
            "documents": [
                {
                    "source_document_id": document_id,
                    "redaction_or_seal_status": "public",
                    "restriction_evidence": evidence,
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                    "is_sealed": False,
                    "is_private": None,
                }
            ],
        }
        for candidate_id, document_id in (("200", "202"), ("300", "303"))
    ]


def _frontier(
    cohort: dict[str, Any], purchase_policy: dict[str, object]
) -> dict[str, Any]:
    return build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=purchase_policy,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=("100", "200"),
        candidate_rows=_frontier_rows(),
        case_mix_max_per_bucket=None,
        source_commitments={"pool": "sha256:" + "b" * 64},
    )


def _frontier_rows() -> list[dict[str, object]]:
    return [
        {
            "candidate_id": "100",
            "purchase_document_ids": [],
            "missing_core_document_count": 0,
            "estimated_purchase_count": 0,
            "missing_core_roles": [],
            "estimated_cost_usd": "0.00",
            "exclusion_reasons": [],
            "court": "Court A",
            "nos_macro_category": "nos-a",
            "related_family_id": None,
            "mdl_family_id": None,
        },
        {
            "candidate_id": "200",
            "purchase_document_ids": ["202"],
            "missing_core_document_count": 1,
            "estimated_purchase_count": 1,
            "missing_core_roles": ["opposition"],
            "estimated_cost_usd": "3.05",
            "exclusion_reasons": [],
            "court": "Court B",
            "nos_macro_category": "nos-b",
            "related_family_id": None,
            "mdl_family_id": None,
        },
        {
            "candidate_id": "300",
            "purchase_document_ids": ["303"],
            "missing_core_document_count": 1,
            "estimated_purchase_count": 1,
            "missing_core_roles": ["opposition"],
            "estimated_cost_usd": "3.05",
            "exclusion_reasons": [],
            "court": "Court C",
            "nos_macro_category": "nos-c",
            "related_family_id": None,
            "mdl_family_id": None,
        },
    ]


def _single_case_plan(candidate_id: str, document_id: str) -> MissingCoreBudgetPlan:
    case = CaseMissingCorePurchasePlan(
        candidate_id=candidate_id,
        purchase_document_ids=(document_id,),
        missing_core_document_count=1,
        estimated_cost=Decimal("3.05"),
        audit_only_document_count=0,
        dry_run=False,
        missing_core_roles=("opposition",),
    )
    return MissingCoreBudgetPlan(
        case_plans=(case,),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("20.00"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )


def _confirm_candidate(
    journal: CaseDevPurchaseJournal,
    candidate_id: str,
    document_id: str,
    *,
    actual: str,
) -> None:
    journal.plan(_single_case_plan(candidate_id, document_id))
    assert journal.submit(document_id) is True
    journal.confirm(
        document_id,
        response={
            "acknowledgePacerFees": True,
            "pacerFees": {
                "pacerFee": actual,
                "serviceFee": "0.00",
                "total": actual,
            },
        },
        fees={"pacer_fee_usd": actual, "service_fee_usd": "0.00", "total_usd": actual},
    )


def _clearance(candidate_id: str, document_id: str, status: str) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "sha256": "2" * 64,
        "byte_count": 123,
        "status": status,
        "automated_markers": ["ssn"] if status == "quarantined" else [],
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_rest_recap_document_exact_match"],
        "reviewer_id": "reviewer",
        "controlled_store_provenance": "private-store://reviews/1",
        "reviewed_at": "2026-07-14T00:00:00Z",
        "free_or_purchased": "purchased",
    }


def _purchase_policy(
    tmp_path: Path,
    cohort: dict[str, Any],
    *,
    hard_cap: str = "10.00",
) -> dict[str, object]:
    max_per_case = str(min(Decimal("9.15"), Decimal(hard_cap)))
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": cohort["policy"]["cycle_id"],
            "cohort_policy_sha256": cohort["policy_sha256"],
            "canonical_ledger_path": str((tmp_path / "purchase.sqlite3").resolve()),
            "hard_cap_usd": hard_cap,
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": f"{Decimal(max_per_case):.2f}",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-14T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _cohort_policy(*, hard_cap: str = "10.00") -> dict[str, Any]:
    fixture = json.loads(
        Path("tests/fixtures/recap_fetch_broker_policy/cohort-policy.json").read_text()
    )
    fixture["policy"]["cycle_id"] = "cycle-replacement-test"
    fixture["policy"]["stop_rule"]["target_clean_cases"] = 2
    fixture["policy"]["reduced_n"]["target_clean_cases"] = 2
    fixture["policy"]["reduced_n"]["claim_tiers"] = [
        {
            "claim_class": "target",
            "insufficient_units_action": None,
            "maximum_clean_cases": 2,
            "minimum_clean_cases": 2,
            "minimum_prediction_units": None,
        }
    ]
    fixture["policy"]["purchase_policy"]["cycle_budget_usd"] = hard_cap
    fixture["policy"]["purchase_policy"]["max_per_case_usd"] = (
        f"{min(Decimal('9.15'), Decimal(hard_cap)):.2f}"
    )
    fixture["policy_sha256"] = _hash(fixture["policy"])
    return fixture


def _hash(value: object) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

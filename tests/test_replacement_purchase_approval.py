from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import legalforecast.ingestion.ranked_reserve_replacement as ranked_reserve_module
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    initialize_case_dev_purchase_journal,
    verify_approved_purchase_input_bytes,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.clearance_replacement import (
    bind_replacement_selection_outputs,
    build_replacement_frontier,
    plan_clearance_replacements,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    bind_ranked_reserve_outputs,
    plan_ranked_reserve_replacements,
    ranked_reserve_result_bytes,
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    UNKNOWN_STATUS_EVIDENCE,
    generate_recap_fetch_attempt_policy,
)
from legalforecast.ingestion.recap_fetch_broker_policy import (
    RecapFetchBrokerPolicyError,
    generate_recap_fetch_broker_policy,
)
from legalforecast.ingestion.replacement_purchase_approval import (
    REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA,
    REPLACEMENT_APPROVAL_SCHEMA,
    REPLACEMENT_APPROVAL_SCHEMA_V2,
    ReplacementPurchaseApprovalError,
    ReplacementPurchaseApprovalRequest,
    VerifiedReplacementPurchaseApproval,
    build_replacement_purchase_approval_request,
    generate_replacement_purchase_authority,
    record_replacement_purchase_approval,
    verify_ranked_reserve_post_purchase_replay,
    verify_replacement_purchase_approval,
    verify_replacement_purchase_authority,
)
from tests.purchase_approval_fixtures import (
    ApprovedPurchaseFixture,
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)
from tests.purchase_approval_fixtures import (
    canonical_json_bytes as _ranked_canonical_json,
)
from tests.purchase_approval_fixtures import (
    canonical_sha256 as _ranked_canonical_sha,
)
from tests.purchase_approval_fixtures import (
    jsonl_bytes as _ranked_jsonl,
)
from tests.purchase_approval_fixtures import (
    ranked_omission as _ranked_omission,
)
from tests.purchase_approval_fixtures import (
    ranked_reserve as _ranked_reserve,
)
from tests.purchase_approval_fixtures import (
    ranked_selection as _ranked_selection,
)
from tests.purchase_approval_fixtures import (
    ranked_terminal_bytes as _ranked_terminal_bytes,
)
from tests.purchase_approval_fixtures import (
    sha256_uri as _sha256_uri,
)
from tests.purchase_approval_fixtures import (
    terminal_disposition_record as _ranked_disposition_record,
)
from tests.test_clearance_replacement_loop import _clearance, _confirm_candidate


@dataclass(frozen=True)
class _RankedApprovalSetup:
    approved: ApprovedPurchaseFixture
    policy_artifact: dict[str, Any]
    policy: CaseDevPurchasePolicy
    cohort_artifact: dict[str, Any]


def _request() -> ReplacementPurchaseApprovalRequest:
    return ReplacementPurchaseApprovalRequest(
        cycle_id="cycle-1",
        cohort_policy_sha256="1" * 64,
        initial_purchase_policy_sha256="2" * 64,
        initial_approval_sha256="3" * 64,
        frontier_sha256="sha256:" + "4" * 64,
        replacement_result_sha256="5" * 64,
        replacement_budget_plan_sha256="6" * 64,
        replacement_selection_sha256="d" * 64,
        purchase_journal_state_sha256="sha256:" + "7" * 64,
        purchase_ledger_path="/private/cycle-1/purchases.sqlite3",
        purchase_ledger_initialization_receipt_path=(
            "/private/cycle-1/purchase-ledger-initialization.json"
        ),
        purchase_ledger_initialization_receipt_sha256="e" * 64,
        committed_spend_usd="100.00",
        hard_cap_usd="567.30",
        max_per_case_usd="73.20",
        remaining_headroom_before_usd="467.30",
        tranche_projected_cost_usd="6.10",
        remaining_headroom_after_usd="461.20",
        candidate_headroom=(
            ("candidate-101", "0.00", "73.20", "3.05", "70.15"),
            ("candidate-102", "0.00", "73.20", "3.05", "70.15"),
        ),
        replacement_candidate_ids=("candidate-101", "candidate-102"),
        purchase_document_ids=("9001", "9002"),
        replacement_event_record_sha256s=(
            "sha256:" + "8" * 64,
            "sha256:" + "9" * 64,
        ),
    )


def _ranked_authority_fixture(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    prior_unpaid_tranche: bool = False,
    baseline_document_id: str | None = None,
) -> dict[str, Any]:
    """Build exact ranked planner, budget-producer, and output-binder artifacts."""

    setup = _ranked_approval_setup(tmp_path, monkeypatch=monkeypatch)
    approved = setup.approved
    policy_artifact = setup.policy_artifact
    policy = setup.policy
    cohort_artifact = setup.cohort_artifact
    projection_sha256 = "sha256:" + "7" * 64
    selected = tuple(_ranked_selection(index) for index in range(100))
    reserves = tuple(_ranked_reserve(index) for index in range(100, 105))
    source_pool = tuple(
        {
            **_ranked_selection(index),
            "documents": (
                [{"source_document_id": f"doc-{index:03d}"}] if index >= 100 else []
            ),
        }
        for index in range(105)
    )
    original_exclusions = tuple(_ranked_omission(index) for index in range(100, 105))
    selected_bytes = _ranked_jsonl(selected)
    reserve_bytes = _ranked_jsonl(reserves)
    source_pool_bytes = _ranked_jsonl(source_pool)
    original_exclusions_bytes = _ranked_jsonl(original_exclusions)
    ranked_projection: dict[str, object] = {
        "schema_version": "legalforecast.target_cohort_projection.v1",
        "projection_sha256": projection_sha256,
        "resolved_pool_case_count": 105,
        "post_clearance_case_count": 105,
        "selected_case_count": 100,
        "ranked_reserve_case_count": 5,
        "selected_candidate_ids_sha256": _ranked_canonical_sha(
            [row["candidate_id"] for row in selected]
        ),
        "ranked_reserve_candidate_ids_sha256": _ranked_canonical_sha(
            [row["candidate_id"] for row in reserves]
        ),
        "ranked_reserve_sha256": _ranked_canonical_sha(reserves),
        "output_commitments": {
            "target-cohort-selection.jsonl": _sha256_uri(selected_bytes),
            "target-cohort-ranked-reserve.jsonl": _sha256_uri(reserve_bytes),
            "target-cohort-exclusions.jsonl": _sha256_uri(original_exclusions_bytes),
        },
        "input_commitments": {
            "/frozen/public-packet-selection-reconciled.jsonl": _sha256_uri(
                source_pool_bytes
            )
        },
    }
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=approved.controlled_private_root,
        initialization_receipt_path=approved.initialization_receipt,
    ) as journal:
        if baseline_document_id is not None:
            baseline_plan = MissingCoreBudgetPlan(
                case_plans=(
                    CaseMissingCorePurchasePlan(
                        candidate_id="baseline-case",
                        purchase_document_ids=(baseline_document_id,),
                        missing_core_document_count=1,
                        estimated_cost=policy.per_document_reservation_usd,
                        audit_only_document_count=0,
                        dry_run=False,
                        missing_core_roles=("motion",),
                    ),
                ),
                cost_per_document=policy.per_document_reservation_usd,
                max_projected_budget=policy.per_document_reservation_usd,
                max_missing_core_documents_per_case=1,
                dry_run=False,
                target_case_count=1,
            )
            journal.plan(baseline_plan)
            assert journal.submit(baseline_document_id)
            journal.confirm(
                baseline_document_id,
                response={"status": "delivered"},
                fees={"total_usd": f"{policy.per_document_reservation_usd:.2f}"},
            )
        terminal_bytes = _ranked_terminal_bytes("case-050")
        ranked_plan = plan_ranked_reserve_replacements(
            projection=ranked_projection,
            selected_bytes=selected_bytes,
            reserve_bytes=reserve_bytes,
            source_pool_bytes=source_pool_bytes,
            original_exclusions_bytes=original_exclusions_bytes,
            terminal_exclusions_bytes=terminal_bytes,
            expected_terminal_exclusions_sha256=_sha256_uri(terminal_bytes),
            purchase_journal=journal,
        )
        if prior_unpaid_tranche:
            terminal_bytes = _ranked_terminal_bytes("case-100")
            ranked_plan = plan_ranked_reserve_replacements(
                projection=ranked_projection,
                selected_bytes=selected_bytes,
                reserve_bytes=reserve_bytes,
                source_pool_bytes=source_pool_bytes,
                original_exclusions_bytes=original_exclusions_bytes,
                terminal_exclusions_bytes=terminal_bytes,
                expected_terminal_exclusions_sha256=_sha256_uri(terminal_bytes),
                purchase_journal=journal,
            )

    budget_bytes = _ranked_canonical_json(ranked_plan.replacement_plan.to_record())
    selection_bytes = _ranked_jsonl(ranked_plan.replacement_selection)
    result = bind_ranked_reserve_outputs(
        ranked_plan,
        active_selection_bytes=_ranked_jsonl(ranked_plan.active_selection),
        replacement_selection_bytes=selection_bytes,
        successor_exclusions_bytes=_ranked_jsonl(ranked_plan.successor_exclusions),
        replacement_budget_plan_bytes=budget_bytes,
    )
    budget_path = tmp_path / "ranked-budget.json"
    selection_path = tmp_path / "ranked-selection.jsonl"
    result_path = tmp_path / "ranked-result.json"
    budget_path.write_bytes(budget_bytes)
    selection_path.write_bytes(selection_bytes)
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "cohort_path": approved.cohort_policy,
        "cohort_artifact": cohort_artifact,
        "policy_path": approved.policy,
        "policy_artifact": policy_artifact,
        "initial_private_root": approved.controlled_private_root,
        "ledger_path": policy.canonical_ledger_path,
        "receipt_path": approved.initialization_receipt,
        "budget_path": budget_path,
        "selection_path": selection_path,
        "result_path": result_path,
        "projection_sha256": projection_sha256,
        "ranked_projection": ranked_projection,
        "selected_bytes": selected_bytes,
        "reserve_bytes": reserve_bytes,
        "source_pool_bytes": source_pool_bytes,
        "original_exclusions_bytes": original_exclusions_bytes,
        "terminal_bytes": terminal_bytes,
        "active_bytes": _ranked_jsonl(ranked_plan.active_selection),
        "successor_exclusions_bytes": _ranked_jsonl(ranked_plan.successor_exclusions),
        "policy": policy,
        "ranked_plan": ranked_plan,
    }


def _over_cap_ranked_authority_fixture(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Build canonical budget bytes around a deliberately invalid durable event."""

    setup = _ranked_approval_setup(tmp_path, monkeypatch=monkeypatch)
    approved = setup.approved
    policy_artifact = setup.policy_artifact
    policy = setup.policy
    cohort_artifact = setup.cohort_artifact
    projection_sha256 = "sha256:" + "7" * 64
    candidate_id = "ranked-reserve-candidate"
    reservation = policy.per_document_reservation_usd
    over_cap_count = int(policy.max_per_case_usd / reservation) + 1
    document_ids = [
        f"ranked-reserve-document-{index}" for index in range(over_cap_count)
    ]
    cost = reservation * len(document_ids)
    assert cost > policy.max_per_case_usd
    return _build_over_cap_ranked_artifacts(
        tmp_path,
        approved=approved,
        policy_artifact=policy_artifact,
        policy=policy,
        cohort_artifact=cohort_artifact,
        projection_sha256=projection_sha256,
        candidate_id=candidate_id,
        document_ids=document_ids,
        cost=cost,
    )


def _ranked_approval_setup(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> _RankedApprovalSetup:
    """Build and initialize the authority inputs shared by ranked fixtures."""

    projection = build_completed_projection_fixture(
        tmp_path / "ranked-projection",
        monkeypatch=monkeypatch,
    )
    approved = build_approved_purchase_fixture(
        tmp_path / "ranked-initial-authority",
        target_cohort_root=projection.root,
    )
    policy_artifact = json.loads(approved.policy.read_text(encoding="utf-8"))
    policy = verify_case_dev_purchase_policy(policy_artifact)
    cohort_artifact = json.loads(approved.cohort_policy.read_text(encoding="utf-8"))
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=approved.initialization_receipt,
        purchase_policy_file_sha256=_sha256_uri(approved.policy.read_bytes()),
        cohort_policy_file_sha256=_sha256_uri(approved.cohort_policy.read_bytes()),
        initialized_at="2026-08-04T19:00:00Z",
        controlled_private_root=approved.controlled_private_root,
    )
    return _RankedApprovalSetup(
        approved=approved,
        policy_artifact=policy_artifact,
        policy=policy,
        cohort_artifact=cohort_artifact,
    )


def _build_over_cap_ranked_artifacts(
    tmp_path: Path,
    *,
    approved: ApprovedPurchaseFixture,
    policy_artifact: dict[str, Any],
    policy: CaseDevPurchasePolicy,
    cohort_artifact: dict[str, Any],
    projection_sha256: str,
    candidate_id: str,
    document_ids: list[str],
    cost: Decimal,
) -> dict[str, Any]:
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=approved.controlled_private_root,
        initialization_receipt_path=approved.initialization_receipt,
    ) as journal:
        event = journal.append_replacement_event(
            "ranked-reserve-over-cap-test-event",
            {
                "schema_version": "legalforecast.ranked_reserve_replacement_event.v1",
                "projection_sha256": projection_sha256,
                "displaced_candidate_id": "initial-candidate",
                "promoted_candidate_id": candidate_id,
                "reserve_rank": 1,
                "estimated_cost_usd": f"{cost:.2f}",
                "purchase_document_ids": document_ids,
                "terminal_reason": "unitization_unresolvable",
                "terminal_source_stage": "apply-unitization-review",
                "terminal_source_artifact_sha256": "sha256:" + "4" * 64,
                "terminal_source_record_sha256": "sha256:" + "5" * 64,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
        )
        journal_state_sha256 = "sha256:" + journal.purchase_state_sha256()
        committed = Decimal(journal.committed_amount_usd)
    case_plan = CaseMissingCorePurchasePlan(
        candidate_id=candidate_id,
        purchase_document_ids=tuple(document_ids),
        missing_core_document_count=len(document_ids),
        estimated_cost=cost,
        audit_only_document_count=0,
        dry_run=False,
        missing_core_roles=("motion",),
    )
    budget = MissingCoreBudgetPlan(
        case_plans=(case_plan,),
        cost_per_document=policy.per_document_reservation_usd,
        max_projected_budget=policy.hard_cap_usd - committed,
        max_missing_core_documents_per_case=len(document_ids),
        dry_run=False,
        target_case_count=1,
    ).to_record()
    selection = {
        "candidate_id": candidate_id,
        "documents": [
            {"source_document_id": document_id} for document_id in document_ids
        ],
    }
    budget_path = tmp_path / "ranked-budget.json"
    selection_path = tmp_path / "ranked-selection.jsonl"
    result_path = tmp_path / "ranked-result.json"
    budget_path.write_bytes(_ranked_canonical_json(budget))
    selection_path.write_bytes(_ranked_jsonl((selection,)))
    event_hash = str(event["record_sha256"])
    reserved = cost
    result = {
        "schema_version": "legalforecast.ranked_reserve_replacement_result.v1",
        "projection_sha256": projection_sha256,
        "cycle_id": policy.cycle_id,
        "purchase_policy_sha256": "sha256:" + policy.policy_sha256,
        "purchase_journal_state_sha256": journal_state_sha256,
        "hard_cap_usd": f"{policy.hard_cap_usd:.2f}",
        "terminal_exclusions_sha256": "sha256:" + "6" * 64,
        "active_selection_sha256": "sha256:" + "1" * 64,
        "replacement_selection_sha256": _sha256_uri(selection_path.read_bytes()),
        "successor_exclusions_sha256": "sha256:" + "2" * 64,
        "replacement_budget_plan_sha256": _sha256_uri(budget_path.read_bytes()),
        "active_case_count": 100,
        "replacement_case_count": 1,
        "committed_spend_usd": f"{committed:.2f}",
        "reserved_replacement_spend_usd": f"{reserved:.2f}",
        "remaining_headroom_usd": (f"{policy.hard_cap_usd - committed - reserved:.2f}"),
        "successor_approval_required": True,
        "replacement_event_record_sha256s": [event_hash],
        "tranche_event_record_sha256s": [event_hash],
        "provider_activity_requested": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "cohort_path": approved.cohort_policy,
        "cohort_artifact": cohort_artifact,
        "policy_path": approved.policy,
        "policy_artifact": policy_artifact,
        "initial_private_root": approved.controlled_private_root,
        "ledger_path": policy.canonical_ledger_path,
        "receipt_path": approved.initialization_receipt,
        "budget_path": budget_path,
        "selection_path": selection_path,
        "result_path": result_path,
        "projection_sha256": projection_sha256,
    }


def _build_ranked_request(
    fixture: dict[str, Any],
) -> ReplacementPurchaseApprovalRequest:
    return build_replacement_purchase_approval_request(
        cohort_policy_path=fixture["cohort_path"],
        initial_purchase_policy_path=fixture["policy_path"],
        initial_controlled_private_root=fixture["initial_private_root"],
        frontier_path=None,
        replacement_result_path=fixture["result_path"],
        replacement_budget_plan_path=fixture["budget_path"],
        replacement_selection_path=fixture["selection_path"],
        purchase_ledger_path=fixture["ledger_path"],
        purchase_ledger_initialization_receipt_path=fixture["receipt_path"],
        source_authority_kind="ranked_reserve_projection",
        source_authority_sha256=fixture["projection_sha256"],
    )


def test_ranked_approval_request_preserves_wal_present_ledger_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    ledger_path = cast(Path, fixture["ledger_path"])
    anchor = sqlite3.connect(ledger_path, isolation_level=None)
    try:
        anchor.execute("PRAGMA wal_autocheckpoint=0")
        anchor.execute("BEGIN")
        anchor.execute("SELECT COUNT(*) FROM purchase_operations").fetchone()
        with sqlite3.connect(ledger_path, isolation_level=None) as writer:
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE wal_only_approval_fixture (sentinel INTEGER)")
        reserved_paths = (
            ledger_path,
            Path(f"{ledger_path}.lock"),
            Path(f"{ledger_path}-wal"),
            Path(f"{ledger_path}-shm"),
            Path(f"{ledger_path}-journal"),
        )
        before = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in reserved_paths
            if path.exists()
        }
        assert Path(f"{ledger_path}-wal") in before
        assert Path(f"{ledger_path}-shm") in before

        request = _build_ranked_request(fixture)

        after = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in reserved_paths
            if path.exists()
        }
        assert before == after
        assert set(before) == set(after)
        assert request.purchase_ledger_path == str(ledger_path)
    finally:
        anchor.close()


def test_exact_successor_approval_records_replays_and_publishes(
    tmp_path: Path,
) -> None:
    request = _request()
    private_root = (tmp_path / "successor-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-28T16:00:00Z",
    )

    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
    )
    authority = generate_replacement_purchase_authority(verified)

    assert authority["authority"]["request"] == request.to_record()
    assert authority["authority"]["decision"] == "approve"
    assert authority["authority"]["request"]["session_scope"] == (
        "exact_replacement_tranche_one_global_session"
    )
    assert authority["authority"]["request"]["max_per_case_usd"] == "73.20"
    assert authority["authority"]["request"]["candidate_headroom"] == [
        {
            "candidate_id": "candidate-101",
            "committed_spend_usd": "0.00",
            "remaining_headroom_before_usd": "73.20",
            "approved_tranche_cost_usd": "3.05",
            "remaining_headroom_after_usd": "70.15",
        },
        {
            "candidate_id": "candidate-102",
            "committed_spend_usd": "0.00",
            "remaining_headroom_before_usd": "73.20",
            "approved_tranche_cost_usd": "3.05",
            "remaining_headroom_after_usd": "70.15",
        },
    ]
    card = json.loads(run_card.read_text(encoding="utf-8"))
    assert card["schema_version"] == REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA
    assert card["run_card"]["stage"] == "record-replacement-purchase-approval"
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        assert card["run_card"][field] is False


def test_replacement_approval_preflights_both_outputs_before_writing(
    tmp_path: Path,
) -> None:
    request = _request()
    private_root = (tmp_path / "successor-private").resolve()
    run_card = private_root / "run-cards" / "record-replacement-purchase-approval.json"
    run_card.parent.mkdir(parents=True)
    run_card.write_text("stale", encoding="utf-8")

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="replacement approval output already exists",
    ):
        record_replacement_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-28T16:00:00Z",
        )

    assert not (private_root / "replacement-purchase-approval-checkpoint.json").exists()
    assert run_card.read_text(encoding="utf-8") == "stale"


def test_replacement_approval_rejects_symlinked_private_root_ancestor(
    tmp_path: Path,
) -> None:
    request = _request()
    redirected_root = tmp_path / "redirected"
    redirected_root.mkdir()
    private_root = tmp_path / "successor-private"
    private_root.symlink_to(redirected_root, target_is_directory=True)

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="cannot be safely preflighted",
    ):
        record_replacement_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-28T16:00:00Z",
        )

    assert list(redirected_root.iterdir()) == []


def test_initial_or_arbitrary_authority_cannot_mint_successor() -> None:
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="only by evidence replay",
    ):
        VerifiedReplacementPurchaseApproval(
            request=_request(),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-28T16:00:00Z",
            typed_confirmation_sha256="a" * 64,
            checkpoint_sha256="b" * 64,
            run_card_sha256="c" * 64,
        )


def test_reject_decision_is_durable_but_cannot_authorize(tmp_path: Path) -> None:
    request = _request()
    private_root = (tmp_path / "rejected-successor").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="reject",
        typed_confirmation=request.required_confirmation("reject"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-28T16:00:00Z",
    )
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="does not authorize replacement purchases",
    ):
        verify_replacement_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
        )


def test_changed_exact_tranche_fails_private_replay(tmp_path: Path) -> None:
    request = _request()
    private_root = (tmp_path / "changed-tranche").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-28T16:00:00Z",
    )
    changed = replace(
        request,
        purchase_document_ids=("9001", "attacker-document"),
    )
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="request or current journal state changed",
    ):
        verify_replacement_purchase_approval(
            request=changed,
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
        )


def test_invalid_per_case_headroom_fails_before_writing(tmp_path: Path) -> None:
    request = replace(_request(), max_per_case_usd="74.20")
    private_root = (tmp_path / "invalid-headroom").resolve()

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="request scope or headroom arithmetic is invalid",
    ):
        record_replacement_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-28T16:00:00Z",
        )

    assert not private_root.exists()


def test_explicit_clearance_source_uses_closed_v2_request_schema() -> None:
    request = replace(
        _request(),
        source_authority_kind="clearance_frontier",
        source_authority_sha256="sha256:" + "4" * 64,
    )

    record = request.to_record()

    assert "frontier_sha256" not in record
    assert record["source_authority_kind"] == "clearance_frontier"
    assert record["source_authority_sha256"] == "sha256:" + "4" * 64


@pytest.mark.parametrize(
    ("source_authority_kind", "source_authority_sha256", "expected"),
    (
        (
            "ranked_reserve_projection",
            None,
            "source authority requires a SHA-256",
        ),
        (
            None,
            "sha256:" + "4" * 64,
            "legacy authority cannot be mixed with a v2 source commitment",
        ),
        (
            "ranked_reserve_projection",
            "sha256:" + "5" * 64,
            "source authority SHA-256 is not canonical",
        ),
    ),
)
def test_request_record_rejects_invalid_source_authority(
    source_authority_kind: str | None,
    source_authority_sha256: str | None,
    expected: str,
) -> None:
    request = replace(
        _request(),
        source_authority_kind=source_authority_kind,
        source_authority_sha256=source_authority_sha256,
    )

    with pytest.raises(ReplacementPurchaseApprovalError, match=expected):
        request.to_record()


def test_v1_replacement_evidence_remains_byte_compatible(tmp_path: Path) -> None:
    request = _request()
    assert request.request_sha256 == (
        "8341cd5e110b1ea829713c6d0f302c44b337ebcc914b8d810c53b52be17a842e"
    )
    root = (tmp_path / "legacy-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-28T16:00:00Z",
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
    )

    authority = generate_replacement_purchase_authority(verified)

    assert authority["schema_version"] == REPLACEMENT_APPROVAL_SCHEMA
    assert authority["authority"]["schema_version"] == REPLACEMENT_APPROVAL_SCHEMA
    assert "frontier_sha256" in authority["authority"]["request"]
    assert "source_authority_kind" not in authority["authority"]["request"]


@pytest.mark.parametrize(
    ("source_authority_kind", "supply_frontier", "expected"),
    (
        ("unknown", False, "unsupported"),
        (
            "ranked_reserve_projection",
            True,
            "cannot be mixed with a clearance frontier",
        ),
        (
            "ranked_reserve_projection",
            False,
            "requires the replayed projection SHA-256",
        ),
    ),
)
def test_ranked_builder_rejects_unknown_or_mixed_source_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_authority_kind: str,
    supply_frontier: bool,
    expected: str,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    frontier_path = fixture["result_path"] if supply_frontier else None

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match=expected,
    ):
        build_replacement_purchase_approval_request(
            cohort_policy_path=fixture["cohort_path"],
            initial_purchase_policy_path=fixture["policy_path"],
            initial_controlled_private_root=fixture["initial_private_root"],
            frontier_path=frontier_path,
            replacement_result_path=fixture["result_path"],
            replacement_budget_plan_path=fixture["budget_path"],
            replacement_selection_path=fixture["selection_path"],
            purchase_ledger_path=fixture["ledger_path"],
            purchase_ledger_initialization_receipt_path=fixture["receipt_path"],
            source_authority_kind=source_authority_kind,
        )


def test_authenticated_ranked_result_binds_closed_terminal_disposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    result = json.loads(fixture["result_path"].read_text(encoding="utf-8"))
    disposition = _ranked_disposition_record(
        residual_sha256=str(result["terminal_exclusions_sha256"]),
        purchase_journal_state_sha256=str(result["purchase_journal_state_sha256"]),
    )
    result["schema_version"] = "legalforecast.ranked_reserve_replacement_result.v2"
    result["terminal_disposition"] = disposition
    result["terminal_disposition_sha256"] = _ranked_canonical_sha(disposition)
    fixture["result_path"].write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    request = _build_ranked_request(fixture)
    assert (
        request.replacement_result_sha256
        == hashlib.sha256(fixture["result_path"].read_bytes()).hexdigest()
    )

    residual_pairs = cast(list[object], disposition["residual_failure_pairs"])
    mutations: tuple[tuple[str, object, str], ...] = (
        (
            "partition_exhaustive",
            False,
            "activity and partition flags are invalid",
        ),
        ("terminal_candidate_count", 4, "does not match its records"),
        ("model_visible", True, "activity and partition flags are invalid"),
        (
            "residual_failure_pairs",
            [*residual_pairs, residual_pairs[0]],
            "duplicated or unordered",
        ),
        (
            "purchase_journal_state_sha256",
            "sha256:" + "9" * 64,
            "targets another journal state",
        ),
        (
            "residual_terminal_exclusions_sha256",
            "sha256:" + "8" * 64,
            "residual exclusion commitment mismatch",
        ),
    )
    for field, value, expected_error in mutations:
        tampered = json.loads(json.dumps(disposition))
        tampered[field] = value
        result["terminal_disposition"] = tampered
        result["terminal_disposition_sha256"] = _ranked_canonical_sha(tampered)
        fixture["result_path"].write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        with pytest.raises(
            ReplacementPurchaseApprovalError,
            match=expected_error,
        ):
            _build_ranked_request(fixture)


def test_current_ranked_result_binds_canonical_legacy_precursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    result = json.loads(fixture["result_path"].read_text(encoding="utf-8"))
    disposition = _ranked_disposition_record(
        residual_sha256=str(result["terminal_exclusions_sha256"]),
        purchase_journal_state_sha256=str(result["purchase_journal_state_sha256"]),
    )
    result["schema_version"] = "legalforecast.ranked_reserve_replacement_result.v2"
    result["terminal_disposition"] = disposition
    result["terminal_disposition_sha256"] = _ranked_canonical_sha(disposition)
    precursor = json.loads(ranked_reserve_result_bytes(result))
    precursor_bytes = ranked_reserve_result_bytes(precursor)
    result["schema_version"] = "legalforecast.ranked_reserve_replacement_result.v3"
    result["authenticated_legacy_replay"] = {
        "schema_version": "legalforecast.ranked_reserve_legacy_event_replay.v1",
        "precursor_result": precursor,
        "precursor_result_sha256": _sha256_uri(precursor_bytes),
        "precursor_active_selection_sha256": result["active_selection_sha256"],
        "precursor_replacement_selection_sha256": result[
            "replacement_selection_sha256"
        ],
        "precursor_successor_exclusions_sha256": result["successor_exclusions_sha256"],
        "precursor_replacement_budget_plan_sha256": result[
            "replacement_budget_plan_sha256"
        ],
        "historical_purchase_journal_state_sha256": result[
            "purchase_journal_state_sha256"
        ],
        "historical_terminal_evidence_sha256": "sha256:" + "a" * 64,
        "current_terminal_evidence_sha256": "sha256:" + "b" * 64,
        "authenticated_event_record_sha256s": result[
            "replacement_event_record_sha256s"
        ],
        "historical_state_substitution_only": True,
    }
    fixture["result_path"].write_bytes(ranked_reserve_result_bytes(result))

    request = _build_ranked_request(fixture)

    assert (
        request.replacement_result_sha256
        == hashlib.sha256(fixture["result_path"].read_bytes()).hexdigest()
    )
    original_tranche_events = result["tranche_event_record_sha256s"]
    result["tranche_event_record_sha256s"] = ["sha256:" + "d" * 64]
    fixture["result_path"].write_bytes(ranked_reserve_result_bytes(result))
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="legacy replay differs from current commitments",
    ):
        _build_ranked_request(fixture)
    result["tranche_event_record_sha256s"] = original_tranche_events
    proof = cast(dict[str, object], result["authenticated_legacy_replay"])
    proof["precursor_active_selection_sha256"] = "sha256:" + "c" * 64
    fixture["result_path"].write_bytes(ranked_reserve_result_bytes(result))
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="differs from its canonical precursor",
    ):
        _build_ranked_request(fixture)


def _post_purchase_ranked_replay_fixture(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    purchased_document_count: int | None = None,
) -> dict[str, Any]:
    fixture = _ranked_authority_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
        baseline_document_id="zzz-baseline-document",
    )
    result = cast(dict[str, object], json.loads(fixture["result_path"].read_bytes()))
    baseline_state = cast(str, result["purchase_journal_state_sha256"])
    baseline_disposition = _ranked_disposition_record(
        residual_sha256=cast(str, result["terminal_exclusions_sha256"]),
        purchase_journal_state_sha256=baseline_state,
    )
    result["schema_version"] = "legalforecast.ranked_reserve_replacement_result.v2"
    historical_state = "sha256:" + "9" * 64
    historical_disposition = _ranked_disposition_record(
        residual_sha256=cast(str, result["terminal_exclusions_sha256"]),
        purchase_journal_state_sha256=historical_state,
    )
    result["purchase_journal_state_sha256"] = historical_state
    result["terminal_disposition"] = historical_disposition
    result["terminal_disposition_sha256"] = _ranked_canonical_sha(
        historical_disposition
    )
    precursor = cast(dict[str, object], json.loads(ranked_reserve_result_bytes(result)))
    precursor_bytes = ranked_reserve_result_bytes(precursor)
    result["schema_version"] = "legalforecast.ranked_reserve_replacement_result.v3"
    result["purchase_journal_state_sha256"] = baseline_state
    result["terminal_disposition"] = baseline_disposition
    result["terminal_disposition_sha256"] = _ranked_canonical_sha(baseline_disposition)
    result["authenticated_legacy_replay"] = {
        "schema_version": "legalforecast.ranked_reserve_legacy_event_replay.v1",
        "precursor_result": precursor,
        "precursor_result_sha256": _sha256_uri(precursor_bytes),
        "precursor_active_selection_sha256": result["active_selection_sha256"],
        "precursor_replacement_selection_sha256": result[
            "replacement_selection_sha256"
        ],
        "precursor_successor_exclusions_sha256": result["successor_exclusions_sha256"],
        "precursor_replacement_budget_plan_sha256": result[
            "replacement_budget_plan_sha256"
        ],
        "historical_purchase_journal_state_sha256": historical_state,
        "historical_terminal_evidence_sha256": "sha256:" + "a" * 64,
        "current_terminal_evidence_sha256": "sha256:" + "b" * 64,
        "authenticated_event_record_sha256s": result[
            "replacement_event_record_sha256s"
        ],
        "historical_state_substitution_only": True,
    }
    prior_bytes = ranked_reserve_result_bytes(result)
    fixture["result_path"].write_bytes(prior_bytes)
    request = _build_ranked_request(fixture)
    successor_root = (tmp_path / "post-purchase-successor-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-08-06T18:00:00Z",
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
    )
    authority = generate_replacement_purchase_authority(verified)
    plan = fixture["ranked_plan"].replacement_plan
    all_documents = tuple(
        document_id
        for case_plan in plan.case_plans
        for document_id in case_plan.purchase_document_ids
    )
    limit = (
        len(all_documents)
        if purchased_document_count is None
        else purchased_document_count
    )
    with CaseDevPurchaseJournal(
        fixture["ledger_path"],
        policy=fixture["policy"],
        controlled_private_root=fixture["initial_private_root"],
        initialization_receipt_path=fixture["receipt_path"],
    ) as journal:
        journal.plan(plan)
        for document_id in all_documents[:limit]:
            assert journal.submit(document_id)
            journal.confirm(
                document_id,
                response={"status": "delivered"},
                fees={
                    "total_usd": (
                        f"{fixture['policy'].per_document_reservation_usd:.2f}"
                    )
                },
            )
    return {
        **fixture,
        "prior_result": result,
        "prior_bytes": prior_bytes,
        "request": request,
        "successor_root": successor_root,
        "authority": authority,
        "all_documents": all_documents,
        "precursor_bytes": precursor_bytes,
    }


def _verify_post_purchase_ranked_replay(fixture: Mapping[str, Any]) -> object:
    return verify_ranked_reserve_post_purchase_replay(
        prior_result=fixture["prior_result"],
        prior_result_bytes=fixture["prior_bytes"],
        authority_artifact=fixture["authority"],
        controlled_private_root=fixture["successor_root"],
        initial_purchase_policy_artifact=fixture["policy_artifact"],
        initial_controlled_private_root=fixture["initial_private_root"],
        cohort_policy_artifact=fixture["cohort_artifact"],
        budget_plan_bytes=fixture["budget_path"].read_bytes(),
        selection_bytes=fixture["selection_path"].read_bytes(),
        purchase_ledger_path=fixture["ledger_path"],
        purchase_ledger_initialization_receipt_path=fixture["receipt_path"],
    )


def test_post_purchase_ranked_replay_proves_exact_authority_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _post_purchase_ranked_replay_fixture(tmp_path, monkeypatch=monkeypatch)

    replay = cast(Any, _verify_post_purchase_ranked_replay(fixture))

    assert replay.is_replay_minted()
    assert replay.baseline_snapshot.purchase_state_sha256 == str(
        fixture["request"].purchase_journal_state_sha256
    ).removeprefix("sha256:")
    assert len(replay.baseline_snapshot.operations) == 1
    assert len(replay.successor_operation_record_sha256s) == len(
        fixture["all_documents"]
    )
    assert (
        ranked_reserve_result_bytes(
            replay.authenticated_legacy_replay["precursor_result"]
        )
        == fixture["precursor_bytes"]
    )


def test_verified_post_purchase_transition_plans_and_binds_current_v3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _post_purchase_ranked_replay_fixture(tmp_path, monkeypatch=monkeypatch)
    replay = cast(Any, _verify_post_purchase_ranked_replay(fixture))
    terminal_record = cast(
        dict[str, object], json.loads(fixture["terminal_bytes"].decode().strip())
    )
    terminal_records = {cast(str, terminal_record["candidate_id"]): terminal_record}
    current_state = "sha256:" + replay.current_snapshot.purchase_state_sha256
    current_disposition = _ranked_disposition_record(
        residual_sha256=cast(
            str, fixture["prior_result"]["terminal_exclusions_sha256"]
        ),
        purchase_journal_state_sha256=current_state,
    )
    historical_state = cast(
        str,
        replay.authenticated_legacy_replay["historical_purchase_journal_state_sha256"],
    )
    baseline_state = cast(str, fixture["prior_result"]["purchase_journal_state_sha256"])
    reconstruction_states: list[str] = []
    original_replacement_events = ranked_reserve_module._replacement_events
    tranche_budget_cap = Decimal(
        cast(str, fixture["prior_result"]["reserved_replacement_spend_usd"])
    ) + Decimal(cast(str, fixture["prior_result"]["remaining_headroom_usd"]))

    def authenticated_replacement_events(
        records: object,
        *,
        projection_sha256: str,
        reserve_by_id: object,
    ) -> tuple[dict[str, Any], ...]:
        events = original_replacement_events(
            cast(Any, records),
            projection_sha256=projection_sha256,
            reserve_by_id=cast(Any, reserve_by_id),
        )
        return tuple(
            {
                **event,
                "tranche_max_projected_budget_usd": f"{tranche_budget_cap:.2f}",
            }
            for event in events
        )

    monkeypatch.setattr(
        ranked_reserve_module,
        "_replacement_events",
        authenticated_replacement_events,
    )

    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_residual_terminal_records",
        lambda _authority, *, purchase_journal: terminal_records,
    )
    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_terminal_purchase_disposition_record",
        lambda _authority, *, purchase_journal: current_disposition,
    )
    monkeypatch.setattr(
        ranked_reserve_module,
        "_verify_terminal_records",
        lambda records, selected_ids, *, verified_retrieval_records: {
            cast(str, record["candidate_id"]): record for record in records
        },
    )

    def reconstruct(
        _authority: object,
        *,
        purchase_journal: CaseDevPurchaseJournal,
        historical_purchase_journal_state_sha256: str,
    ) -> tuple[dict[str, dict[str, object]], dict[str, object], str, str]:
        del purchase_journal
        reconstruction_states.append(historical_purchase_journal_state_sha256)
        if historical_purchase_journal_state_sha256 == historical_state:
            precursor = cast(
                dict[str, object],
                replay.authenticated_legacy_replay["precursor_result"],
            )
            return (
                terminal_records,
                cast(dict[str, object], precursor["terminal_disposition"]),
                "sha256:" + "a" * 64,
                "sha256:" + "c" * 64,
            )
        assert historical_purchase_journal_state_sha256 == baseline_state
        return (
            terminal_records,
            cast(dict[str, object], fixture["prior_result"]["terminal_disposition"]),
            "sha256:" + "b" * 64,
            "sha256:" + "c" * 64,
        )

    monkeypatch.setattr(
        ranked_reserve_module,
        "reconstruct_historical_terminal_disposition",
        reconstruct,
    )
    with CaseDevPurchaseJournal(
        fixture["ledger_path"],
        policy=fixture["policy"],
        controlled_private_root=fixture["initial_private_root"],
        initialization_receipt_path=fixture["receipt_path"],
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["ranked_projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["original_exclusions_bytes"],
            terminal_exclusions_bytes=fixture["terminal_bytes"],
            expected_terminal_exclusions_sha256=_sha256_uri(fixture["terminal_bytes"]),
            purchase_journal=journal,
            terminal_purchase_disposition_authority=cast(Any, object()),
            precommit_revalidator=lambda: None,
            allow_new_replacement_events=False,
            verified_post_purchase_replay=replay,
        )
    active_bytes = _ranked_jsonl(plan.active_selection)
    replacement_bytes = _ranked_jsonl(plan.replacement_selection)
    exclusions_bytes = _ranked_jsonl(plan.successor_exclusions)
    budget_bytes = _ranked_canonical_json(plan.replacement_plan.to_record())

    result = bind_ranked_reserve_outputs(
        plan,
        active_selection_bytes=active_bytes,
        replacement_selection_bytes=replacement_bytes,
        successor_exclusions_bytes=exclusions_bytes,
        replacement_budget_plan_bytes=budget_bytes,
    )

    assert reconstruction_states == [historical_state, baseline_state]
    assert result["purchase_journal_state_sha256"] == current_state
    assert (
        result["authenticated_legacy_replay"]
        == fixture["prior_result"]["authenticated_legacy_replay"]
    )


def test_post_purchase_ranked_replay_requires_complete_approved_complement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _post_purchase_ranked_replay_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
        purchased_document_count=0,
    )

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="is not retained as committed spend",
    ):
        _verify_post_purchase_ranked_replay(fixture)


def test_post_purchase_ranked_replay_rejects_prior_result_not_named_by_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _post_purchase_ranked_replay_fixture(tmp_path, monkeypatch=monkeypatch)
    tampered = cast(dict[str, object], json.loads(fixture["prior_bytes"]))
    tampered["remaining_headroom_usd"] = "0.01"
    fixture["prior_result"] = tampered
    fixture["prior_bytes"] = ranked_reserve_result_bytes(tampered)

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="differs from exact successor approval",
    ):
        _verify_post_purchase_ranked_replay(fixture)


def test_ranked_v2_authority_records_replays_and_verifies_exact_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    request = _build_ranked_request(fixture)
    root = (tmp_path / "ranked-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-08-04T20:00:00Z",
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
    )
    authority = generate_replacement_purchase_authority(verified)

    assert (
        json.loads(fixture["budget_path"].read_bytes())
        == fixture["ranked_plan"].replacement_plan.to_record()
    )
    assert request.source_authority_kind == "ranked_reserve_projection"
    assert request.source_authority_sha256 == fixture["projection_sha256"]
    assert "frontier_sha256" not in request.to_record()
    assert authority["schema_version"] == REPLACEMENT_APPROVAL_SCHEMA_V2
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="request or current journal state changed",
    ):
        verify_replacement_purchase_approval(
            request=replace(
                request,
                frontier_sha256="sha256:" + "9" * 64,
                source_authority_sha256="sha256:" + "9" * 64,
            ),
            controlled_private_root=root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
        )
    assert (
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=root,
            initial_purchase_policy_artifact=fixture["policy_artifact"],
            initial_controlled_private_root=fixture["initial_private_root"],
            cohort_policy_artifact=fixture["cohort_artifact"],
            budget_plan_bytes=fixture["budget_path"].read_bytes(),
            selection_bytes=fixture["selection_path"].read_bytes(),
            purchase_ledger_path=fixture["ledger_path"],
            purchase_ledger_initialization_receipt_path=fixture["receipt_path"],
        )
        == request
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    (
        ("authority", "differs from the replayed source authority"),
        ("budget", "differs from its durable event"),
        ("selection", "lacks an approved successor candidate"),
        ("journal", "purchase-journal state is stale"),
    ),
)
def test_ranked_v2_builder_rejects_changed_source_budget_selection_journal_or_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    expected: str,
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    result = json.loads(fixture["result_path"].read_text(encoding="utf-8"))
    if target == "authority":
        result["projection_sha256"] = "sha256:" + "9" * 64
    elif target == "budget":
        budget = json.loads(fixture["budget_path"].read_text(encoding="utf-8"))
        budget["case_plans"][0]["candidate_id"] = "changed-candidate"
        fixture["budget_path"].write_text(
            json.dumps(budget, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result["replacement_budget_plan_sha256"] = (
            "sha256:" + hashlib.sha256(fixture["budget_path"].read_bytes()).hexdigest()
        )
    elif target == "selection":
        selection = json.loads(fixture["selection_path"].read_text(encoding="utf-8"))
        selection["candidate_id"] = "changed-candidate"
        fixture["selection_path"].write_text(
            json.dumps(selection, sort_keys=True) + "\n", encoding="utf-8"
        )
        result["replacement_selection_sha256"] = (
            "sha256:"
            + hashlib.sha256(fixture["selection_path"].read_bytes()).hexdigest()
        )
    elif target == "journal":
        result["purchase_journal_state_sha256"] = "sha256:" + "8" * 64
    fixture["result_path"].write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(ReplacementPurchaseApprovalError, match=expected):
        _build_ranked_request(fixture)


def test_ranked_v2_builder_rejects_per_case_cap_overrun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _over_cap_ranked_authority_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
    )

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="exceeds per-case headroom",
    ):
        _build_ranked_request(fixture)


def test_ranked_v2_builder_rejects_understated_prior_unpaid_reservations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _ranked_authority_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
        prior_unpaid_tranche=True,
    )
    canonical_request = _build_ranked_request(fixture)
    budget = json.loads(fixture["budget_path"].read_text(encoding="utf-8"))
    assert (
        canonical_request.remaining_headroom_before_usd
        == budget["max_projected_budget_usd"]
    )
    result = json.loads(fixture["result_path"].read_text(encoding="utf-8"))
    assert (
        canonical_request.remaining_headroom_after_usd
        == result["remaining_headroom_usd"]
    )
    current_cost = fixture["ranked_plan"].replacement_plan.total_estimated_cost
    committed = Decimal(result["committed_spend_usd"])
    assert Decimal(result["reserved_replacement_spend_usd"]) > current_cost
    result["reserved_replacement_spend_usd"] = f"{current_cost:.2f}"
    result["remaining_headroom_usd"] = (
        f"{fixture['policy'].hard_cap_usd - committed - current_cost:.2f}"
    )
    fixture["result_path"].write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="reserved spend differs from the canonical journal",
    ):
        _build_ranked_request(fixture)


def test_cli_verifies_ranked_v2_authority_from_canonical_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _ranked_authority_fixture(tmp_path, monkeypatch=monkeypatch)
    request = _build_ranked_request(fixture)
    root = (tmp_path / "ranked-cli-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-08-04T20:00:00Z",
    )
    capsys.readouterr()

    status = cli.main(
        [
            "acquisition",
            "verify-replacement-purchase-approval",
            "--cohort-policy",
            str(fixture["cohort_path"]),
            "--initial-purchase-policy",
            str(fixture["policy_path"]),
            "--initial-controlled-private-root",
            str(fixture["initial_private_root"]),
            "--ranked-reserve-projection-sha256",
            fixture["projection_sha256"],
            "--replacement-result",
            str(fixture["result_path"]),
            "--replacement-budget-plan",
            str(fixture["budget_path"]),
            "--replacement-selection",
            str(fixture["selection_path"]),
            "--purchase-ledger",
            str(fixture["ledger_path"]),
            "--purchase-ledger-initialization-receipt",
            str(fixture["receipt_path"]),
            "--controlled-private-root",
            str(root),
            "--checkpoint",
            str(checkpoint),
            "--approval-run-card",
            str(run_card),
        ]
    )

    assert status == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True


def test_v2_replacement_requires_exact_successor_before_broker_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    projection = build_completed_projection_fixture(
        tmp_path / "projection",
        monkeypatch=monkeypatch,
    )
    approved = build_approved_purchase_fixture(
        tmp_path / "initial-authority",
        target_cohort_root=projection.root,
    )
    target_root = projection.root
    cohort_path = approved.cohort_policy
    policy_path = approved.policy
    initial_private_root = approved.controlled_private_root
    policy_artifact = json.loads(policy_path.read_text(encoding="utf-8"))
    policy = verify_case_dev_purchase_policy(policy_artifact)
    receipt_path = approved.initialization_receipt
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt_path,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        initialized_at="2026-07-28T15:00:00Z",
        controlled_private_root=initial_private_root,
    )
    initial_budget = json.loads(
        (target_root / "missing-core-budget-plan.json").read_text(encoding="utf-8")
    )
    initial_ids = tuple(
        str(plan["candidate_id"]) for plan in initial_budget["case_plans"]
    )
    quarantined_plan = initial_budget["case_plans"][0]
    quarantined_candidate = str(quarantined_plan["candidate_id"])
    quarantined_document = str(quarantined_plan["purchase_document_ids"][0])
    reservation = policy.per_document_reservation_usd
    replacement_candidate = "ranked-unselected-replacement"
    # Deliberately sorts before the pre-approval operation. Runtime replay must
    # compare the authenticated baseline by identity, not by journal row order.
    replacement_document = "1"

    def frontier_row(candidate_id: str, documents: list[str]) -> dict[str, object]:
        return {
            "candidate_id": candidate_id,
            "purchase_document_ids": documents,
            "missing_core_document_count": len(documents),
            "estimated_purchase_count": len(documents),
            "missing_core_roles": ["motion"],
            "estimated_cost_usd": f"{reservation * len(documents):.2f}",
            "exclusion_reasons": [],
            "court": "Test Court",
            "nos_macro_category": "test-nos",
            "related_family_id": None,
            "mdl_family_id": None,
        }

    rows = [
        frontier_row(
            str(plan["candidate_id"]),
            [str(value) for value in plan["purchase_document_ids"]],
        )
        for plan in initial_budget["case_plans"]
    ]
    rows.append(frontier_row(replacement_candidate, [replacement_document]))
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    frontier = build_replacement_frontier(
        cohort_policy_artifact=cohort,
        purchase_policy_artifact=policy_artifact,
        projection_sha256="sha256:" + "a" * 64,
        initial_selected_candidate_ids=initial_ids,
        candidate_rows=rows,
        case_mix_max_per_bucket=None,
        source_commitments={"projection": "sha256:" + "b" * 64},
        controlled_private_root=initial_private_root,
    )
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=initial_private_root,
        initialization_receipt_path=receipt_path,
    ) as journal:
        _confirm_candidate(
            journal,
            quarantined_candidate,
            quarantined_document,
            actual=f"{reservation:.2f}",
        )
        planned = plan_clearance_replacements(
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            frontier_artifact=frontier,
            purchase_journal=journal,
            purchased_clearance_records=(
                _clearance(
                    quarantined_candidate,
                    quarantined_document,
                    "quarantined",
                ),
            ),
            clearance_run_card_sha256="sha256:" + "c" * 64,
            controlled_private_root=initial_private_root,
        )
    assert [plan.candidate_id for plan in planned.replacement_plan.case_plans] == [
        replacement_candidate
    ]

    frontier_path = tmp_path / "replacement-frontier.json"
    result_path = tmp_path / "replacement-result.json"
    budget_path = tmp_path / "replacement-budget.json"
    selection_path = tmp_path / "replacement-selection.jsonl"
    frontier_path.write_text(
        json.dumps(frontier, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    budget_path.write_text(
        json.dumps(planned.replacement_plan.to_record(), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    selection = {
        "candidate_id": replacement_candidate,
        "selected": True,
        "exclusion_reasons": [],
        "documents": [
            {
                "source_document_id": replacement_document,
                "redaction_or_seal_status": "unknown",
                "restriction_evidence": list(UNKNOWN_STATUS_EVIDENCE),
                "availability_status": "unavailable",
                "requires_paid_recovery": True,
                "is_available": False,
                "is_sealed": None,
                "is_private": None,
            }
        ],
    }
    selection_path.write_text(json.dumps(selection) + "\n", encoding="utf-8")
    budget_bytes = budget_path.read_bytes()
    selection_bytes = selection_path.read_bytes()
    active_selection_bytes = "".join(
        json.dumps({"candidate_id": candidate_id}, sort_keys=True) + "\n"
        for candidate_id in planned.active_candidate_ids
    ).encode()
    result_record = bind_replacement_selection_outputs(
        planned,
        active_selection_sha256="sha256:"
        + hashlib.sha256(active_selection_bytes).hexdigest(),
        active_selection_count=len(planned.active_candidate_ids),
        replacement_selection_sha256="sha256:"
        + hashlib.sha256(selection_bytes).hexdigest(),
        replacement_selection_count=1,
    )
    result_path.write_text(
        json.dumps(result_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        CaseDevPurchasePolicyError,
        match="budget plan bytes differ from the exact approved projection",
    ):
        verify_approved_purchase_input_bytes(
            policy,
            controlled_private_root=initial_private_root,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
        )

    request = build_replacement_purchase_approval_request(
        cohort_policy_path=cohort_path,
        initial_purchase_policy_path=policy_path,
        initial_controlled_private_root=initial_private_root,
        frontier_path=frontier_path,
        replacement_result_path=result_path,
        replacement_budget_plan_path=budget_path,
        replacement_selection_path=selection_path,
        purchase_ledger_path=policy.canonical_ledger_path,
        purchase_ledger_initialization_receipt_path=receipt_path,
    )
    assert request.max_per_case_usd == f"{policy.max_per_case_usd:.2f}"
    headroom_by_candidate = {
        candidate_id: (committed, before, approved_cost, after)
        for candidate_id, committed, before, approved_cost, after in (
            request.candidate_headroom
        )
    }
    assert headroom_by_candidate[quarantined_candidate] == (
        f"{reservation:.2f}",
        f"{policy.max_per_case_usd - reservation:.2f}",
        "0.00",
        f"{policy.max_per_case_usd - reservation:.2f}",
    )
    assert headroom_by_candidate[replacement_candidate] == (
        "0.00",
        f"{policy.max_per_case_usd:.2f}",
        f"{reservation:.2f}",
        f"{policy.max_per_case_usd - reservation:.2f}",
    )
    tampered_selection = tmp_path / "tampered-replacement-selection.jsonl"
    tampered_selection.write_bytes(
        selection_bytes + b'{"candidate_id":"post-plan-tamper"}\n'
    )
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="replacement selection differs from the planned result",
    ):
        build_replacement_purchase_approval_request(
            cohort_policy_path=cohort_path,
            initial_purchase_policy_path=policy_path,
            initial_controlled_private_root=initial_private_root,
            frontier_path=frontier_path,
            replacement_result_path=result_path,
            replacement_budget_plan_path=budget_path,
            replacement_selection_path=tampered_selection,
            purchase_ledger_path=policy.canonical_ledger_path,
            purchase_ledger_initialization_receipt_path=receipt_path,
        )
    successor_root = (tmp_path / "successor-private").resolve()
    checkpoint, run_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-28T16:00:00Z",
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
    )
    authority = generate_replacement_purchase_authority(verified)
    assert (
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=successor_root,
            initial_purchase_policy_artifact=policy_artifact,
            initial_controlled_private_root=initial_private_root,
            cohort_policy_artifact=cohort,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            purchase_ledger_path=policy.canonical_ledger_path,
            purchase_ledger_initialization_receipt_path=receipt_path,
        )
        == request
    )

    executor_args = argparse.Namespace(
        purchase_policy=policy_path,
        controlled_private_root=initial_private_root,
        cohort_policy=cohort_path,
        budget_plan=budget_path,
        selection=selection_path,
        purchase_ledger=policy.canonical_ledger_path,
        purchase_ledger_initialization_receipt=receipt_path,
        replacement_purchase_authority=None,
        replacement_controlled_private_root=None,
    )
    with pytest.raises(
        cli.CommandError,
        match="budget plan bytes differ from the exact approved projection",
    ):
        cli._preflight_approved_purchase_input_bytes(executor_args)
    executor_args.replacement_purchase_authority = tmp_path / "successor-authority.json"
    executor_args.replacement_controlled_private_root = successor_root
    executor_args.replacement_purchase_authority.write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    executor_args.purchase_ledger_initialization_receipt = None
    with pytest.raises(
        cli.CommandError,
        match="requires the purchase-ledger initialization receipt",
    ):
        cli._preflight_approved_purchase_input_bytes(executor_args)
    executor_args.purchase_ledger_initialization_receipt = receipt_path
    cli._preflight_approved_purchase_input_bytes(executor_args)

    attempt = generate_recap_fetch_attempt_policy(
        purchase_policy_artifact=policy_artifact,
        cohort_policy_artifact=cohort,
        budget_plan=planned.replacement_plan,
        budget_plan_artifact=planned.replacement_plan.to_record(),
        selection_records=(selection,),
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
        controlled_private_root=initial_private_root,
        replacement_purchase_authority_artifact=authority,
        replacement_controlled_private_root=successor_root,
        purchase_ledger_initialization_receipt_path=receipt_path,
    )
    attempt_path = tmp_path / "replacement-attempt-policy.json"
    attempt_path.write_text(
        json.dumps(attempt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        RecapFetchBrokerPolicyError,
        match="initial exact-selection approval cannot authorize a broad frontier",
    ):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=policy_artifact,
            cohort_policy_artifact=cohort,
            budget_plan=planned.replacement_plan,
            budget_plan_artifact=planned.replacement_plan.to_record(),
            selection_records=(selection,),
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            controlled_private_root=initial_private_root,
            replacement_purchase_authority_artifact=authority,
            replacement_controlled_private_root=successor_root,
            purchase_ledger_initialization_receipt_path=receipt_path,
            attempt_policy_artifact=attempt,
            broad_frontier_allowlist=True,
        )
    broker_policy_path = tmp_path / "replacement-broker-policy.json"
    broker_stage_root = tmp_path / "replacement-broker-stage"
    assert (
        cli.main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--output-root",
                str(broker_stage_root),
                "--purchase-policy",
                str(policy_path),
                "--controlled-private-root",
                str(initial_private_root),
                "--replacement-purchase-authority",
                str(executor_args.replacement_purchase_authority),
                "--replacement-controlled-private-root",
                str(successor_root),
                "--purchase-ledger-initialization-receipt",
                str(receipt_path),
                "--cohort-policy",
                str(cohort_path),
                "--budget-plan",
                str(budget_path),
                "--selection",
                str(selection_path),
                "--attempt-policy",
                str(attempt_path),
                "--output",
                str(broker_policy_path),
                "--run-card-output",
                str(
                    broker_stage_root
                    / "run-cards"
                    / "generate-recap-fetch-broker-policy.json"
                ),
                "--execute",
                "--resume",
            ]
        )
        == 0
    )
    assert broker_policy_path.exists()
    broker_run_card = json.loads(
        (
            broker_stage_root / "run-cards" / "generate-recap-fetch-broker-policy.json"
        ).read_text(encoding="utf-8")
    )
    assert broker_run_card["stage"] == "generate-recap-fetch-broker-policy"
    assert broker_run_card["dry_run"] is False
    assert broker_run_card["paid_activity_requested"] is False
    assert broker_run_card["paid_activity_executed"] is False
    purchase_args = [
        "acquisition",
        "purchase-missing-recap-fetch",
        "--output-root",
        str(tmp_path / "replacement-purchase-binding"),
        "--budget-plan",
        str(budget_path),
        "--selection",
        str(selection_path),
        "--purchase-policy",
        str(policy_path),
        "--cohort-policy",
        str(cohort_path),
        "--purchase-ledger",
        str(policy.canonical_ledger_path),
        "--controlled-private-root",
        str(initial_private_root),
        "--purchase-ledger-initialization-receipt",
        str(receipt_path),
        "--attempt-policy",
        str(attempt_path),
        "--replacement-purchase-authority",
        str(executor_args.replacement_purchase_authority),
        "--replacement-controlled-private-root",
        str(successor_root),
        "--request-ledger",
        str(tmp_path / "replacement-request-ledger.sqlite3"),
        "--live-purchase",
        "--acknowledge-pacer-fees",
        "--execute",
    ]
    monkeypatch.setattr(
        cli,
        "CourtListenerRecapFetchClient",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("live RECAP Fetch client must not be reached")
        ),
    )
    assert cli.main(purchase_args) == 2
    assert (
        "--broker-policy is required for a live replacement purchase"
        in capsys.readouterr().err
    )
    tampered_broker_policy = tmp_path / "tampered-replacement-broker-policy.json"
    tampered_broker = json.loads(broker_policy_path.read_text(encoding="utf-8"))
    tampered_broker["allowed_documents"] = []
    tampered_broker_policy.write_text(
        json.dumps(tampered_broker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                *purchase_args,
                "--broker-policy",
                str(tampered_broker_policy),
            ]
        )
        == 2
    )
    download_path = tmp_path / "replacement-downloads.jsonl"
    clearance_path = tmp_path / "replacement-clearance.jsonl"
    clearance_card_path = tmp_path / "replacement-clearance-card.json"
    restriction_path = tmp_path / "replacement-restrictions.jsonl"
    for path in (download_path, clearance_path, restriction_path):
        path.write_text("", encoding="utf-8")
    clearance_card_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_preflight_current_purchase_snapshot", lambda _args: None)
    monkeypatch.setattr(
        cli,
        "_authenticated_clearance_lineage_inputs",
        lambda *_args, **_kwargs: ({}, ()),
    )
    monkeypatch.setattr(
        cli,
        "_build_resolved_post_recovery_dispatch",
        lambda **_kwargs: [
            {
                "candidate_id": replacement_candidate,
                "source_document_id": replacement_document,
                "record_sha256": "sha256:" + "f" * 64,
            }
        ],
    )
    monkeypatch.setattr(
        cli,
        "require_resolved_post_recovery_operation_bindings",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "write_resolved_post_recovery_documents",
        lambda path, records: Path(path).write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        ),
    )

    real_journal = cli.CaseDevPurchaseJournal

    class ResolverJournal:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> ResolverJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def purchase_state_sha256(self) -> str:
            return "a" * 64

        def operation_records(self) -> tuple[dict[str, str], ...]:
            return (
                {
                    "candidate_id": replacement_candidate,
                    "source_document_id": replacement_document,
                },
            )

        def clear_unknown_material(
            self, _document_id: str, *, resolved_record: object
        ) -> None:
            assert resolved_record

    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", ResolverJournal)
    resolve_root = tmp_path / "successor-resolve"
    assert (
        cli.main(
            [
                "acquisition",
                "resolve-post-recovery-documents",
                "--output-root",
                str(resolve_root),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--budget-plan",
                str(budget_path),
                "--purchase-ledger",
                str(policy.canonical_ledger_path),
                "--controlled-private-root",
                str(initial_private_root),
                "--purchase-ledger-initialization-receipt",
                str(receipt_path),
                "--replacement-purchase-authority",
                str(executor_args.replacement_purchase_authority),
                "--replacement-controlled-private-root",
                str(successor_root),
                "--attempt-policy",
                str(attempt_path),
                "--download-manifest",
                str(download_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--clearance-run-card",
                str(clearance_card_path),
                "--restriction-evidence",
                str(restriction_path),
                "--execute",
            ]
        )
        == 0
    )
    assert (resolve_root / "resolved-post-recovery-documents.jsonl").exists()
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", real_journal)

    with pytest.raises(
        RecapFetchBrokerPolicyError,
        match="fresh ledger namespace",
    ):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=policy_artifact,
            cohort_policy_artifact=cohort,
            budget_plan=planned.replacement_plan,
            budget_plan_artifact=planned.replacement_plan.to_record(),
            selection_records=(selection,),
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            controlled_private_root=initial_private_root,
        )
    broker = json.loads(broker_policy_path.read_text(encoding="utf-8"))
    assert broker["allowed_documents"] == [
        {
            "case_id": replacement_candidate,
            "recap_document": replacement_document,
        }
    ]
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=initial_private_root,
        initialization_receipt_path=receipt_path,
    ) as journal:
        _confirm_candidate(
            journal,
            replacement_candidate,
            replacement_document,
            actual="0.00",
        )
    assert (
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=successor_root,
            initial_purchase_policy_artifact=policy_artifact,
            initial_controlled_private_root=initial_private_root,
            cohort_policy_artifact=cohort,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            purchase_ledger_path=policy.canonical_ledger_path,
            purchase_ledger_initialization_receipt_path=receipt_path,
        )
        == request
    )
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=initial_private_root,
        initialization_receipt_path=receipt_path,
    ) as journal:
        _confirm_candidate(
            journal,
            "unapproved-post-successor-candidate",
            "2",
            actual="0.00",
        )
    with pytest.raises(
        ReplacementPurchaseApprovalError,
        match="outside the approved successor tranche",
    ):
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=successor_root,
            initial_purchase_policy_artifact=policy_artifact,
            initial_controlled_private_root=initial_private_root,
            cohort_policy_artifact=cohort,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            purchase_ledger_path=policy.canonical_ledger_path,
            purchase_ledger_initialization_receipt_path=receipt_path,
        )
    assert (
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=successor_root,
            initial_purchase_policy_artifact=policy_artifact,
            initial_controlled_private_root=initial_private_root,
            cohort_policy_artifact=cohort,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            purchase_ledger_path=policy.canonical_ledger_path,
            purchase_ledger_initialization_receipt_path=receipt_path,
            allowed_additional_operation_pairs={
                ("unapproved-post-successor-candidate", "2")
            },
        )
        == request
    )

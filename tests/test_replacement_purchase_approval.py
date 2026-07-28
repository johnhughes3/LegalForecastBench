from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
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
    ReplacementPurchaseApprovalError,
    ReplacementPurchaseApprovalRequest,
    VerifiedReplacementPurchaseApproval,
    build_replacement_purchase_approval_request,
    generate_replacement_purchase_authority,
    record_replacement_purchase_approval,
    verify_replacement_purchase_approval,
    verify_replacement_purchase_authority,
)
from tests.purchase_approval_fixtures import (
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)
from tests.test_clearance_replacement_loop import _clearance, _confirm_candidate


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
        remaining_headroom_before_usd="467.30",
        tranche_projected_cost_usd="6.10",
        remaining_headroom_after_usd="461.20",
        replacement_candidate_ids=("candidate-101", "candidate-102"),
        purchase_document_ids=("9001", "9002"),
        replacement_event_record_sha256s=(
            "sha256:" + "8" * 64,
            "sha256:" + "9" * 64,
        ),
    )


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


def test_v2_replacement_requires_exact_successor_before_broker_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
                "restriction_evidence": UNKNOWN_STATUS_EVIDENCE,
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
    assert cli.main(purchase_args) == 2
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

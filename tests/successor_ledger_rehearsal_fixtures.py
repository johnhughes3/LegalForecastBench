"""Provider-free, authenticated successor-ledger rehearsal support.

This fixture intentionally uses the production approval and SQLite-journal APIs.
It is not a shortcut around a semantic verifier: the only synthetic inputs are
the public-safe projection rows and bytes that those APIs authenticate.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseSnapshot,
    canonical_purchase_operation_sha256,
)
from legalforecast.ingestion.replacement_purchase_approval import (
    ReplacementPurchaseApprovalRequest,
    build_replacement_purchase_approval_request,
    generate_replacement_purchase_authority,
    record_replacement_purchase_approval,
    verify_replacement_purchase_approval,
)
from legalforecast.ingestion.replacement_recovery_source import (
    RecoverySourceCoordinates,
    build_recovery_source_descriptor,
)
from legalforecast.ingestion.resolved_post_recovery import (
    reconstruct_pre_resolution_purchase_snapshot,
)
from tests.test_replacement_purchase_approval import (
    _ranked_authority_fixture,  # pyright: ignore[reportPrivateUsage]
)


def _canonical_record_sha256(record: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _json_path(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path


@dataclass(frozen=True)
class SuccessorLedgerRehearsal:
    """Real initial/successor approvals plus one resolved material transition."""

    root: Path
    fixture: dict[str, Any]
    request: ReplacementPurchaseApprovalRequest
    authority_path: Path
    baseline_operation_sha256: str
    transition_before: CaseDevPurchaseSnapshot
    transition_after: CaseDevPurchaseSnapshot
    resolved_record: dict[str, object]
    initial_descriptor: Path
    successor_descriptor: Path


def build_successor_ledger_rehearsal(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> SuccessorLedgerRehearsal:
    """Build an initial-plus-successor lineage without provider/paid activity.

    The imported ranked fixture is deliberately a real production spine: it
    creates the completed projection, records/replays initial approval,
    initializes SQLite, plans a deterministic reserve promotion, and binds the
    resulting bytes.  This function extends that spine with an actual successor
    approval and a recovered-pending-clearance -> cleared-public transition.
    """

    def reject_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "successor-ledger rehearsal must not use a network provider"
        )

    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    root = tmp_path / "successor-ledger-rehearsal"
    fixture = _ranked_authority_fixture(
        root / "ranked",
        monkeypatch=monkeypatch,
        baseline_document_id="unrelated-baseline-document",
    )
    request = build_replacement_purchase_approval_request(
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
    successor_private_root = root / "successor-private"
    checkpoint, approval_card = record_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-08-07T19:00:00Z",
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=successor_private_root,
        checkpoint_path=checkpoint,
        run_card_path=approval_card,
    )
    authority_path = _json_path(
        root / "successor-authority.json",
        generate_replacement_purchase_authority(verified),
    )

    policy = fixture["policy"]
    with CaseDevPurchaseJournal(
        fixture["ledger_path"],
        policy=policy,
        controlled_private_root=fixture["initial_private_root"],
        initialization_receipt_path=fixture["receipt_path"],
    ) as journal:
        baseline = next(
            operation
            for operation in journal.operation_records()
            if operation["source_document_id"] == "unrelated-baseline-document"
        )
        baseline_operation_sha256 = canonical_purchase_operation_sha256(baseline)

        # The ranked plan is a genuine successor operation.  Its journal flow is
        # local state-machine exercise only; no PACER/provider request occurs.
        [case_plan] = fixture["ranked_plan"].replacement_plan.case_plans
        [document_id] = case_plan.purchase_document_ids
        journal.plan(fixture["ranked_plan"].replacement_plan)
        journal.authorize_unknown_material_attempts(
            {
                document_id: {
                    "case_id": case_plan.candidate_id,
                    "selection_document_sha256": "a" * 64,
                }
            },
            attempt_policy_sha256="b" * 64,
        )
        assert journal.submit(document_id) is True
        journal.queue(document_id, response={"queue_id": "fixture-queue"})
        journal.mark_material_available_for_quarantine(
            document_id,
            provider_detail_sha256="c" * 64,
            queue_response_sha256="d" * 64,
            download_url_sha256="e" * 64,
        )
        journal.record_quarantined_material_bytes(
            document_id,
            content_sha256="f" * 64,
            byte_count=37,
        )
        transition_before = journal.authenticated_snapshot()
        preclear_operation = next(
            operation
            for operation in transition_before.operations
            if operation["source_document_id"] == document_id
        )
        evidence = journal.operation_evidence(document_id)
        assert evidence is not None
        # Filler-digest convention: a repeated filler means the two fields are
        # genuinely bound and the verifier compares them, so
        # `selection_document_sha256`, `attempt_policy_sha256`,
        # `queue_response_sha256`, `download_url_sha256`, `content_sha256`, and
        # the provider-detail/`fresh_recap_detail_sha256` pair deliberately
        # reuse the journal's filler.  Every unrelated commitment field gets a
        # digest no other field uses, so a verifier that compared the wrong two
        # fields would fail closed here instead of passing on a coincidence.
        resolved_record: dict[str, object] = {
            "schema_version": "legalforecast.resolved_post_recovery_public_document.v1",
            "candidate_id": case_plan.candidate_id,
            "source_document_id": document_id,
            "recovery_origin": "unknown_status_attempt",
            "attempt_policy_sha256": "b" * 64,
            "selection_document_sha256": "a" * 64,
            "queue_response_sha256": "d" * 64,
            "fresh_recap_detail_sha256": "c" * 64,
            "download_url_sha256": "e" * 64,
            "download_record_sha256": "1" * 64,
            "content_sha256": "f" * 64,
            "byte_count": 37,
            "clearance_record_sha256": "0" * 64,
            "clearance_run_card_sha256": "2" * 64,
            "clearance_artifact_sha256": "3" * 64,
            "cohort_policy_artifact_sha256": "4" * 64,
            "restriction_evidence_artifact_sha256": "5" * 64,
            "restriction_evidence_rows_sha256": "6" * 64,
            "fresh_detail_public_evidence_sha256": "7" * 64,
            "reviews_artifact_sha256": "8" * 64,
            "review_receipt_sha256": "9" * 64,
            "review_authority_sha256": "ab" * 32,
            "purchase_policy_sha256": policy.policy_sha256,
            "purchase_operation_sha256": canonical_purchase_operation_sha256(
                preclear_operation
            ),
            "operation_key": evidence["operation_key"],
            "broker_receipt_sha256": "bc" * 32,
            "broker_receipt_state": "provider_free_fixture",
            "restriction_status": "public",
            "parser_eligible": True,
            "packet_eligible": True,
        }
        resolved_record["record_sha256"] = _canonical_record_sha256(resolved_record)
        journal.clear_unknown_material(document_id, resolved_record=resolved_record)
        transition_after = journal.authenticated_snapshot()

    # Descriptors are built by the production producer and consumed by the
    # production index command in the test.  The paths are synthetic only; the
    # initial policy, journal, selection, budget, and successor authority above
    # are authenticated production artifacts.
    initial_coordinates = RecoverySourceCoordinates(
        kind="initial_v2",
        selection_path=fixture["selection_path"],
        purchase_policy_path=fixture["policy_path"],
        cohort_policy_path=fixture["cohort_path"],
        budget_plan_path=fixture["budget_path"],
        purchase_ledger_path=fixture["ledger_path"],
        attempt_policy_path=_json_path(root / "initial-attempt-policy.json", {}),
        replacement_authority_path=None,
    )
    successor_coordinates = RecoverySourceCoordinates(
        kind="successor",
        selection_path=fixture["selection_path"],
        purchase_policy_path=fixture["policy_path"],
        cohort_policy_path=fixture["cohort_path"],
        budget_plan_path=fixture["budget_path"],
        purchase_ledger_path=fixture["ledger_path"],
        attempt_policy_path=_json_path(root / "successor-attempt-policy.json", {}),
        replacement_authority_path=authority_path,
    )
    initial_descriptor = _json_path(
        root / "sources" / "0000-initial-v2.json",
        build_recovery_source_descriptor(
            coordinates=initial_coordinates,
            ordinal=0,
            recovery_root=root / "initial-recovery",
            purchased_clearance_path=root / "initial-clearance.jsonl",
            purchased_clearance_run_card_path=root / "initial-clearance-card.json",
            resolved_post_recovery_documents_path=root / "initial-resolved.jsonl",
            replacement_controlled_private_root=None,
        ),
    )
    successor_descriptor = _json_path(
        root / "sources" / "0001-successor.json",
        build_recovery_source_descriptor(
            coordinates=successor_coordinates,
            ordinal=1,
            recovery_root=root / "successor-recovery",
            purchased_clearance_path=root / "successor-clearance.jsonl",
            purchased_clearance_run_card_path=root / "successor-clearance-card.json",
            resolved_post_recovery_documents_path=root / "successor-resolved.jsonl",
            replacement_controlled_private_root=successor_private_root,
        ),
    )
    return SuccessorLedgerRehearsal(
        root=root,
        fixture=fixture,
        request=request,
        authority_path=authority_path,
        baseline_operation_sha256=baseline_operation_sha256,
        transition_before=transition_before,
        transition_after=transition_after,
        resolved_record=resolved_record,
        initial_descriptor=initial_descriptor,
        successor_descriptor=successor_descriptor,
    )


def reconstructed_transition(
    rehearsal: SuccessorLedgerRehearsal,
) -> CaseDevPurchaseSnapshot:
    """Run the production inverse transition verifier used by downstream replay."""

    return reconstruct_pre_resolution_purchase_snapshot(
        current_snapshot=rehearsal.transition_after,
        resolved_records=(rehearsal.resolved_record,),
        policy=rehearsal.fixture["policy"],
        expected_purchase_state_before_sha256=(
            rehearsal.transition_before.purchase_state_sha256
        ),
    )

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cohort_policy import generate_cohort_policy
from legalforecast.ingestion.disclosure_clearance import SCHEMA_VERSION
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    BOUNDED_FETCH_ATTEMPT_AUTHORITY,
    RECAP_FETCH_ATTEMPT_POLICY_VERSION,
    generate_recap_fetch_attempt_policy,
)
from legalforecast.ingestion.resolved_post_recovery import (
    ResolvedPostRecoveryError,
    build_resolved_post_recovery_documents,
    require_resolved_post_recovery_documents,
    require_resolved_post_recovery_operation_bindings,
    require_resolved_post_recovery_parse_requests,
    write_resolved_post_recovery_documents,
)


def test_build_and_require_exact_unknown_origin_lineage() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)

    assert len(records) == 1
    assert records[0]["parser_eligible"] is True
    assert records[0]["packet_eligible"] is True
    assert records[0]["broker_receipt_state"] == "delivered_but_unreconciled"
    require_resolved_post_recovery_documents(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=inputs["clearance_records"],
        resolved_records=records,
        **_external_kwargs(inputs),
    )


def test_omitted_or_tampered_resolved_lineage_fails_closed() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    with pytest.raises(ResolvedPostRecoveryError, match="coverage mismatch"):
        require_resolved_post_recovery_documents(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[],
            **_external_kwargs(inputs),
        )

    tampered = deepcopy(records[0])
    tampered["content_sha256"] = "9" * 64
    with pytest.raises(ResolvedPostRecoveryError, match="hash changed"):
        require_resolved_post_recovery_documents(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[tampered],
            **_external_kwargs(inputs),
        )


def test_duplicate_or_cross_candidate_lineage_fails_closed() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    with pytest.raises(ResolvedPostRecoveryError, match="duplicate"):
        require_resolved_post_recovery_documents(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[records[0], records[0]],
            **_external_kwargs(inputs),
        )

    operation = deepcopy(inputs["purchase_operation_records"][0])
    operation["candidate_id"] = "case-other"
    with pytest.raises(ResolvedPostRecoveryError, match="coverage"):
        build_resolved_post_recovery_documents(
            **{**inputs, "purchase_operation_records": [operation]}
        )


def test_handcrafted_clearance_without_executed_authenticated_run_fails() -> None:
    inputs = _inputs()
    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["execute"] = False

    with pytest.raises(ResolvedPostRecoveryError, match="executed nonpaid"):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


def test_receipt_commitment_and_authenticated_authority_tamper_fail() -> None:
    inputs = _inputs()
    tampered_bytes = inputs["review_receipt_bytes"] + b" "
    with pytest.raises(ResolvedPostRecoveryError, match="receipt commitment"):
        build_resolved_post_recovery_documents(
            **{**inputs, "review_receipt_bytes": tampered_bytes}
        )

    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["review_authority"]["reviewer_id"] = "reviewer:other"
    with pytest.raises(ResolvedPostRecoveryError, match="review authority"):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


def test_fresh_restriction_artifact_and_public_proof_tamper_fail() -> None:
    inputs = _inputs()
    restrictions = deepcopy(inputs["restriction_records"])
    restrictions[0]["fresh_recap_detail_sha256"] = "8" * 64
    restriction_bytes = _jsonl_bytes(restrictions)
    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["source_commitments"]["restriction_evidence"]["sha256"] = hashlib.sha256(
        restriction_bytes
    ).hexdigest()

    with pytest.raises(ResolvedPostRecoveryError, match="fresh-detail public proof"):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "restriction_records": restrictions,
                "restriction_artifact_bytes": restriction_bytes,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


@pytest.mark.parametrize("mutation", ["hash", "identity"])
def test_broker_receipt_history_hash_and_identity_tamper_fail(mutation: str) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    history = operation["response"]["broker_receipts"]
    if mutation == "hash":
        history[0]["sha256"] = "0" * 64
        message = "receipt hash"
    else:
        second_receipt = deepcopy(history[0]["receipt"])
        second_receipt["reservation_id"] = "reservation-other"
        history.append({"sha256": _hash(second_receipt), "receipt": second_receipt})
        message = "receipt identity"

    with pytest.raises(ResolvedPostRecoveryError, match=message):
        build_resolved_post_recovery_documents(
            **{**inputs, "purchase_operation_records": [operation]}
        )


def test_later_failed_receipt_invalidates_prior_delivery() -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    history = operation["response"]["broker_receipts"]
    failed = deepcopy(history[0]["receipt"])
    failed.update(
        {
            "state": "failed",
            "id": None,
            "held_usd": "0.00",
            "provider_response_body_sha256": None,
            "provider_response_sha256": None,
            "updated_at": "2026-07-15T00:02:00.000Z",
            "delivered_at": None,
        }
    )
    history.append({"sha256": _hash(failed), "receipt": failed})

    with pytest.raises(ResolvedPostRecoveryError, match="terminal state"):
        build_resolved_post_recovery_documents(
            **{**inputs, "purchase_operation_records": [operation]}
        )


def test_resolved_artifact_then_journal_clearance_is_crash_replayable(
    tmp_path: Path,
) -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    artifact = tmp_path / "resolved.jsonl"
    write_resolved_post_recovery_documents(artifact, records)

    require_resolved_post_recovery_operation_bindings(
        purchase_operation_records=inputs["purchase_operation_records"],
        resolved_records=records,
    )
    cleared_operation = deepcopy(inputs["purchase_operation_records"][0])
    cleared_operation["material_state"] = "cleared_public"
    cleared_operation["resolved_document_sha256"] = records[0]["record_sha256"]
    cleared_operation["material_evidence"]["clearance_record_sha256"] = records[0][
        "clearance_record_sha256"
    ]
    require_resolved_post_recovery_operation_bindings(
        purchase_operation_records=[cleared_operation],
        resolved_records=records,
    )
    write_resolved_post_recovery_documents(artifact, records)

    changed = deepcopy(records[0])
    changed["broker_receipt_state"] = "confirmed"
    changed["record_sha256"] = _hash(
        {name: value for name, value in changed.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="overwrite"):
        write_resolved_post_recovery_documents(artifact, [changed])


def test_parse_request_must_bind_exact_resolved_record() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    request = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "expected_sha256": "5" * 64,
        "expected_byte_count": 100,
        "resolved_post_recovery_sha256": "0" * 64,
    }
    with pytest.raises(ResolvedPostRecoveryError, match="does not bind"):
        require_resolved_post_recovery_parse_requests(
            selection_records=inputs["selection_records"],
            request_records=[request],
            resolved_records=records,
        )


def test_resolve_post_recovery_cli_help_names_all_lineage_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", "resolve-post-recovery-documents", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--selection",
        "--purchase-policy",
        "--cohort-policy",
        "--budget-plan",
        "--purchase-ledger",
        "--attempt-policy",
        "--download-manifest",
        "--disclosure-clearance",
        "--clearance-run-card",
        "--reviews",
        "--review-receipt",
        "--restriction-evidence",
        "--resolved-output",
    ):
        assert flag in help_text


def test_recap_fetch_quarantine_recovery_help_names_controlled_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", "recover-recap-fetch-quarantine", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--selection",
        "--purchase-policy",
        "--cohort-policy",
        "--budget-plan",
        "--purchase-ledger",
        "--attempt-policy",
        "--courtlistener-fixture",
        "--fixture-documents",
        "--live-courtlistener-recovery",
        "--manifest-output",
        "--document-output-root",
    ):
        assert flag in help_text


def test_resolve_post_recovery_cli_publishes_and_journals_authenticated_lineage(
    tmp_path: Path,
) -> None:
    inputs = _inputs()
    selection_document = inputs["selection_records"][0]["documents"][0]
    selection_document.update(
        {
            "restriction_evidence": [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_false",
                "courtlistener_rest_recap_document_seal_status_unknown",
                "courtlistener_rest_no_positive_restriction_marker",
            ]
        }
    )
    ledger_path = (tmp_path / "purchases.sqlite3").resolve()
    cohort_decisions = cli._fixture_cohort_policy_decisions()
    cohort_decisions["cycle_id"] = "cycle-1"
    cohort_decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "3.05",
        "max_per_case_usd": "3.05",
        "reservation_headroom_required": True,
    }
    cohort_artifact = generate_cohort_policy(cohort_decisions)
    purchase_artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": cohort_artifact["policy_sha256"],
            "canonical_ledger_path": str(ledger_path),
            "hard_cap_usd": "3.05",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "3.05",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-15T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    purchase_policy = verify_case_dev_purchase_policy(purchase_artifact)
    budget_plan = MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=("123",),
                missing_core_document_count=1,
                estimated_cost=Decimal("3.05"),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("3.05"),
        max_missing_core_documents_per_case=1,
        dry_run=False,
    )
    budget_artifact = budget_plan.to_record()
    attempt_artifact = generate_recap_fetch_attempt_policy(
        purchase_policy_artifact=purchase_artifact,
        cohort_policy_artifact=cohort_artifact,
        budget_plan=budget_plan,
        budget_plan_artifact=budget_artifact,
        selection_records=inputs["selection_records"],
    )
    paths = {
        "selection": tmp_path / "selection.jsonl",
        "purchase_policy": tmp_path / "purchase-policy.json",
        "cohort_policy": tmp_path / "cohort-policy.json",
        "budget_plan": tmp_path / "budget-plan.json",
        "attempt_policy": tmp_path / "attempt-policy.json",
        "download_manifest": tmp_path / "downloads.jsonl",
        "disclosure_clearance": tmp_path / "clearance.jsonl",
        "clearance_run_card": tmp_path / "clearance-run-card.json",
        "reviews": tmp_path / "reviews.jsonl",
        "review_receipt": tmp_path / "review-receipt.json",
        "restriction_evidence": tmp_path / "restrictions.jsonl",
    }
    _write_records(paths["selection"], inputs["selection_records"])
    _write_object(paths["purchase_policy"], purchase_artifact)
    _write_object(paths["cohort_policy"], cohort_artifact)
    _write_object(paths["budget_plan"], budget_artifact)
    _write_object(paths["attempt_policy"], attempt_artifact)
    available_detail = {
        "id": 123,
        "is_available": True,
        "is_sealed": False,
        "is_private": None,
        "filepath_local": "/pdf/123.pdf",
    }
    purchase_fixture = tmp_path / "purchase-courtlistener.jsonl"
    _write_records(
        purchase_fixture,
        [
            {
                "method": "GET",
                "path": "/recap-documents/123/",
                "form": {},
                "status_code": 200,
                "payload": {
                    "id": 123,
                    "is_available": False,
                    "is_sealed": False,
                    "is_private": None,
                },
            },
            {
                "method": "GET",
                "path": "/recap-fetch/77/",
                "form": {},
                "status_code": 200,
                "payload": {"status": 2},
            },
            {
                "method": "GET",
                "path": "/recap-documents/123/",
                "form": {},
                "status_code": 200,
                "payload": available_detail,
            },
        ],
    )
    broker_fixture = tmp_path / "broker.json"
    _write_object(broker_fixture, [{"id": "77", "reservation_id": "reservation-1"}])
    with CaseDevPurchaseJournal(ledger_path, policy=purchase_policy, allow_create=True):
        pass
    purchase_output_root = tmp_path / "purchase-output"
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(paths["budget_plan"]),
                "--selection",
                str(paths["selection"]),
                "--purchase-policy",
                str(paths["purchase_policy"]),
                "--cohort-policy",
                str(paths["cohort_policy"]),
                "--purchase-ledger",
                str(ledger_path),
                "--attempt-policy",
                str(paths["attempt_policy"]),
                "--courtlistener-fixture",
                str(purchase_fixture),
                "--purchase-broker-fixture",
                str(broker_fixture),
                "--acknowledge-pacer-fees",
                "--output-root",
                str(purchase_output_root),
                "--execute",
            ]
        )
        == 2
    )
    with CaseDevPurchaseJournal(ledger_path, policy=purchase_policy) as journal:
        evidence = journal.operation_evidence("123")
        assert evidence is not None
        operation_key = str(evidence["operation_key"])
        receipt = deepcopy(inputs["purchase_operation_records"][0]["response"])[
            "broker_receipts"
        ][0]["receipt"]
        receipt.update(
            {
                "operation_key": operation_key,
                "purchase_policy_sha256": purchase_policy.policy_sha256,
                "client_code": _client_code(operation_key),
            }
        )
        journal.record_broker_receipt("123", receipt)

    recovery_detail_fixture = tmp_path / "recovery-courtlistener.jsonl"
    _write_records(
        recovery_detail_fixture,
        [
            {
                "method": "GET",
                "path": "/recap-documents/123/",
                "form": {},
                "status_code": 200,
                "payload": available_detail,
            }
        ],
    )
    pdf_content = "%PDF-1.4\ncontrolled fixture\n%%EOF\n"
    document_fixture = tmp_path / "recovery-documents.json"
    _write_object(
        document_fixture,
        {"https://www.courtlistener.com/pdf/123.pdf": pdf_content},
    )
    quarantine_root = tmp_path / "quarantine"
    recovery_command = [
        "acquisition",
        "recover-recap-fetch-quarantine",
        "--selection",
        str(paths["selection"]),
        "--purchase-policy",
        str(paths["purchase_policy"]),
        "--cohort-policy",
        str(paths["cohort_policy"]),
        "--budget-plan",
        str(paths["budget_plan"]),
        "--purchase-ledger",
        str(ledger_path),
        "--attempt-policy",
        str(paths["attempt_policy"]),
        "--courtlistener-fixture",
        str(recovery_detail_fixture),
        "--fixture-documents",
        str(document_fixture),
        "--manifest-output",
        str(paths["download_manifest"]),
        "--document-output-root",
        str(quarantine_root),
        "--output-root",
        str(tmp_path / "recovery-output"),
        "--execute",
    ]
    assert main(recovery_command) == 0
    assert main(recovery_command) == 0
    assert "courtlistener.com" not in paths["download_manifest"].read_text()
    assert "download_url" not in paths["download_manifest"].read_text()
    inputs["download_records"] = _read_records(paths["download_manifest"])
    content_bytes = pdf_content.encode()
    _retarget_clearance_inputs(
        inputs,
        content_sha256=hashlib.sha256(content_bytes).hexdigest(),
        byte_count=len(content_bytes),
        detail_sha256=_hash(available_detail),
    )
    paths["disclosure_clearance"].write_bytes(inputs["clearance_artifact_bytes"])
    _write_object(paths["clearance_run_card"], inputs["clearance_run_card"])
    paths["reviews"].write_bytes(inputs["reviews_artifact_bytes"])
    paths["review_receipt"].write_bytes(inputs["review_receipt_bytes"])
    paths["restriction_evidence"].write_bytes(inputs["restriction_artifact_bytes"])
    output_root = tmp_path / "output"
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--selection",
                str(paths["selection"]),
                "--download-manifest",
                str(paths["download_manifest"]),
                "--disclosure-clearance",
                str(paths["disclosure_clearance"]),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    registry_path = tmp_path / "registry.json"
    raw_html_dir = tmp_path / "raw-html"
    _write_records(parser_path, [])
    _write_records(units_path, [])
    _write_object(registry_path, {})
    raw_html_dir.mkdir()
    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(paths["selection"]),
                "--download-manifest",
                str(paths["download_manifest"]),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(paths["disclosure_clearance"]),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    command = [
        "acquisition",
        "resolve-post-recovery-documents",
        *[
            value
            for name, path in paths.items()
            for value in (f"--{name.replace('_', '-')}", str(path))
        ],
        "--purchase-ledger",
        str(ledger_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]
    assert main(command) == 0
    assert main(command) == 0
    resolved = _read_records(output_root / "resolved-post-recovery-documents.jsonl")
    assert len(resolved) == 1
    with CaseDevPurchaseJournal(ledger_path, policy=purchase_policy) as journal:
        evidence = journal.operation_evidence("123")
        assert evidence is not None
        assert evidence["material_state"].value == "cleared_public"
        assert evidence["resolved_document_sha256"] == resolved[0]["record_sha256"]
    run_card = json.loads(
        (output_root / "run-cards/resolve-post-recovery-documents.json").read_text()
    )
    assert run_card["paid_activity_executed"] is False
    assert (
        run_card["output_commitments"]["resolved_post_recovery_documents"]["sha256"]
        == "sha256:"
        + hashlib.sha256(
            (output_root / "resolved-post-recovery-documents.jsonl").read_bytes()
        ).hexdigest()
    )


def _inputs() -> dict[str, Any]:
    selection_document: dict[str, object] = {
        "source_document_id": "123",
        "redaction_or_seal_status": "unknown",
        "is_sealed": None,
        "is_private": None,
        "is_available": False,
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
    }
    selection = {
        "candidate_id": "case-1",
        "selected": True,
        "exclusion_reasons": [],
        "documents": [selection_document],
    }
    attempt_policy: dict[str, object] = {
        "authority": BOUNDED_FETCH_ATTEMPT_AUTHORITY,
        "allowed_documents": [
            {
                "case_id": "case-1",
                "recap_document": "123",
                "evidence_class": "unknown_status_quarantine",
                "selection_document_sha256": _hash(selection_document),
            }
        ],
    }
    attempt_artifact = {
        "schema_version": RECAP_FETCH_ATTEMPT_POLICY_VERSION,
        "policy": attempt_policy,
        "policy_sha256": _hash(attempt_policy),
    }
    operation_key = "00000000-0000-4000-8000-000000000000"
    receipt = {
        "version": "courtlistener-recap-fetch-receipt-v1",
        "state": "delivered_but_unreconciled",
        "operation_key": operation_key,
        "reservation_id": "reservation-1",
        "cycle_id": "cycle-1",
        "case_id": "case-1",
        "recap_document": "123",
        "purchase_policy_sha256": "1" * 64,
        "client_code": "lfb-3oaflyhagb6vuall5rg4gogwtb",
        "id": "77",
        "reservation_usd": "3.05",
        "held_usd": "3.05",
        "authoritative_fee_usd": None,
        "provider_response_body_sha256": "6" * 64,
        "provider_response_sha256": "7" * 64,
        "submitted_at": "2026-07-15T00:00:00.000Z",
        "updated_at": "2026-07-15T00:01:00.000Z",
        "delivered_at": "2026-07-15T00:01:00.000Z",
        "reconciled_at": None,
        "billing_evidence": None,
    }
    operation = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "status": "queued",
        "operation_key": operation_key,
        "material_authority": "unknown_status_attempt",
        "material_state": "recovered_pending_clearance",
        "attempt_policy_sha256": attempt_artifact["policy_sha256"],
        "attempt_document_sha256": _hash(selection_document),
        "resolved_document_sha256": None,
        "response": {
            "broker_receipts": [{"sha256": _hash(receipt), "receipt": receipt}]
        },
        "material_evidence": {
            "provider_detail_sha256": "2" * 64,
            "queue_response_sha256": "3" * 64,
            "download_url_sha256": "4" * 64,
            "content_sha256": "5" * 64,
            "byte_count": 100,
        },
    }
    download = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_origin": "unknown_status_attempt",
        "attempt_policy_sha256": attempt_artifact["policy_sha256"],
        "purchase_operation_key": operation_key,
        "local_path": "case-1/123.pdf",
        "sha256": "5" * 64,
        "byte_count": 100,
    }
    clearance = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": "case-1",
        "source_document_id": "123",
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["fresh_post_recovery_public_detail"],
        "sha256": "5" * 64,
        "byte_count": 100,
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://review/1",
        "reviewed_at": "2026-07-15T00:00:00Z",
    }
    reviews = [
        {
            "candidate_id": "case-1",
            "source_document_id": "123",
            "sha256": "5" * 64,
            "status": "cleared",
            "reviewer_id": "reviewer:john",
            "controlled_store_provenance": "private-store://review/1",
            "reviewed_at": "2026-07-15T00:00:00Z",
        }
    ]
    reviews_bytes = _jsonl_bytes(reviews)
    review_receipt = {
        "schema_version": "legalforecast.disclosure_review_receipt.v1",
        "review_artifact_sha256": hashlib.sha256(reviews_bytes).hexdigest(),
        "authenticated_reviewer_id": "reviewer:john",
        "controlled_store_uri": "private-store://review/1",
        "authentication_method": "cloudflare_access_oidc",
        "authenticated_at": "2026-07-15T00:00:00Z",
    }
    review_receipt_bytes = (json.dumps(review_receipt, sort_keys=True) + "\n").encode()
    restrictions = [
        {
            "schema_version": "legalforecast.post_recovery_restriction_evidence.v1",
            "candidate_id": "case-1",
            "source_document_id": "123",
            "source_provider": "courtlistener_recap_fetch_fresh_detail",
            "fresh_recap_detail_sha256": "2" * 64,
            "is_available": True,
            "is_sealed": False,
            "is_private": None,
            "redaction_or_seal_status": "public",
            "restriction_status": "public",
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
        }
    ]
    restriction_bytes = _jsonl_bytes(restrictions)
    clearance_bytes = _jsonl_bytes([clearance])
    clearance_run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "reviews": {"sha256": hashlib.sha256(reviews_bytes).hexdigest()},
            "review_receipt": {
                "sha256": hashlib.sha256(review_receipt_bytes).hexdigest()
            },
            "restriction_evidence": {
                "sha256": hashlib.sha256(restriction_bytes).hexdigest()
            },
        },
        "output_commitments": {
            "disclosure_clearance": {
                "sha256": hashlib.sha256(clearance_bytes).hexdigest()
            }
        },
        "review_authority": {
            "reviewer_id": "reviewer:john",
            "controlled_store_uri": "private-store://review/1",
            "authentication_method": "cloudflare_access_oidc",
            "authenticated_at": "2026-07-15T00:00:00Z",
            "review_artifact_sha256": (
                "sha256:" + hashlib.sha256(reviews_bytes).hexdigest()
            ),
        },
    }
    clearance_run_card_bytes = (
        json.dumps(clearance_run_card, sort_keys=True) + "\n"
    ).encode()
    return {
        "selection_records": [selection],
        "purchase_operation_records": [operation],
        "download_records": [download],
        "clearance_records": [clearance],
        "attempt_policy_artifact": attempt_artifact,
        "clearance_artifact_bytes": clearance_bytes,
        "clearance_run_card": clearance_run_card,
        "clearance_run_card_bytes": clearance_run_card_bytes,
        "reviews_artifact_bytes": reviews_bytes,
        "review_receipt_artifact": review_receipt,
        "review_receipt_bytes": review_receipt_bytes,
        "restriction_records": restrictions,
        "restriction_artifact_bytes": restriction_bytes,
    }


def _external_kwargs(inputs: dict[str, Any]) -> dict[str, Any]:
    names = (
        "clearance_artifact_bytes",
        "clearance_run_card",
        "clearance_run_card_bytes",
        "reviews_artifact_bytes",
        "review_receipt_artifact",
        "review_receipt_bytes",
        "restriction_records",
        "restriction_artifact_bytes",
    )
    return {name: inputs[name] for name in names}


def _retarget_clearance_inputs(
    inputs: dict[str, Any],
    *,
    content_sha256: str,
    byte_count: int,
    detail_sha256: str,
) -> None:
    clearance = inputs["clearance_records"][0]
    clearance.update({"sha256": content_sha256, "byte_count": byte_count})
    reviews = [
        json.loads(line)
        for line in inputs["reviews_artifact_bytes"].decode().splitlines()
        if line.strip()
    ]
    reviews[0]["sha256"] = content_sha256
    review_bytes = _jsonl_bytes(reviews)
    receipt = inputs["review_receipt_artifact"]
    receipt["review_artifact_sha256"] = hashlib.sha256(review_bytes).hexdigest()
    receipt_bytes = _object_bytes(receipt)
    restrictions = inputs["restriction_records"]
    restrictions[0]["fresh_recap_detail_sha256"] = detail_sha256
    restriction_bytes = _jsonl_bytes(restrictions)
    clearance_bytes = _jsonl_bytes([clearance])
    run_card = inputs["clearance_run_card"]
    run_card["source_commitments"]["reviews"]["sha256"] = hashlib.sha256(
        review_bytes
    ).hexdigest()
    run_card["source_commitments"]["review_receipt"]["sha256"] = hashlib.sha256(
        receipt_bytes
    ).hexdigest()
    run_card["source_commitments"]["restriction_evidence"]["sha256"] = hashlib.sha256(
        restriction_bytes
    ).hexdigest()
    run_card["output_commitments"]["disclosure_clearance"]["sha256"] = hashlib.sha256(
        clearance_bytes
    ).hexdigest()
    run_card["review_authority"]["review_artifact_sha256"] = (
        "sha256:" + hashlib.sha256(review_bytes).hexdigest()
    )
    inputs.update(
        {
            "clearance_artifact_bytes": clearance_bytes,
            "clearance_run_card_bytes": _object_bytes(run_card),
            "reviews_artifact_bytes": review_bytes,
            "review_receipt_bytes": receipt_bytes,
            "restriction_artifact_bytes": restriction_bytes,
        }
    )


def _jsonl_bytes(records: list[dict[str, object]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for record in records
    )


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_bytes(_jsonl_bytes(records))


def _read_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_object(path: Path, value: object) -> None:
    path.write_bytes(_object_bytes(value))


def _object_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _client_code(operation_key: str) -> str:
    digest = hashlib.sha256(operation_key.encode()).digest()
    encoded = base64.b32encode(digest).decode().lower().rstrip("=")
    return "lfb-" + encoded[:26]


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

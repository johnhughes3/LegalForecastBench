from __future__ import annotations

import base64
import hashlib
import inspect
import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import legalforecast.cli as cli
import legalforecast.ingestion.recap_fetch_attempt_policy as attempt_policy_module
import legalforecast.ingestion.resolved_post_recovery as resolved_module
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseSnapshot,
    canonical_purchase_state_sha256,
    generate_case_dev_purchase_policy,
    read_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cohort_policy import generate_cohort_policy
from legalforecast.ingestion.disclosure_clearance import (
    SCHEMA_VERSION,
    DisclosurePdfScan,
    ReviewAuthority,
    require_clearance_policy,
)
from legalforecast.ingestion.disclosure_model_review import DECISION_SCHEMA_VERSION
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthorityIdentity,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.provenance_clearance import (
    build_authenticated_model_provenance_clearance_records_v3,
    build_provenance_clearance_plan_v3,
    canonical_json_bytes,
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    BOUNDED_FETCH_ATTEMPT_AUTHORITY,
    RECAP_FETCH_ATTEMPT_POLICY_VERSION,
    generate_recap_fetch_attempt_policy,
)
from legalforecast.ingestion.recap_fetch_broker import recap_fetch_client_code
from legalforecast.ingestion.recap_fetch_quarantine_recovery import (
    RecapFetchQuarantineRecoveryError,
    project_purchased_case_relevance,
)
from legalforecast.ingestion.replacement_recovery_source import (
    build_recovery_source_descriptor,
    derive_recovery_source_coordinates,
)
from legalforecast.ingestion.resolved_post_recovery import (
    AuthenticatedClearanceLineage,
    ResolvedPostRecoveryError,
    build_resolved_post_recovery_documents,
    build_resolved_post_recovery_documents_with_authenticated_lineage,
    require_resolved_post_recovery_documents,
    require_resolved_post_recovery_documents_with_authenticated_lineage,
    require_resolved_post_recovery_operation_bindings,
    require_resolved_post_recovery_parse_requests,
    write_resolved_post_recovery_documents,
)
from legalforecast.ingestion.resolved_post_recovery import (
    _build_resolved_recovered_public as build_recovered,
)
from legalforecast.ingestion.resolved_post_recovery import (
    _require_resolved_recovered_public as require_recovered,
)
from tests.disclosure_review_fixtures import (
    service_review_signer,
    signed_service_review_lineage,
)
from tests.purchase_approval_fixtures import (
    allow_historical_v1_algorithm_fixtures,
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)
from tests.recovered_public_capability_helpers import (
    issue_recovered_public_capability,
    issue_terminal_disposition_capability,
)


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    original_require = attempt_policy_module.require_approved_case_dev_purchase_policy
    original_verify = attempt_policy_module.verify_approved_purchase_input_bytes
    original_cli_verify = cli.verify_approved_purchase_input_bytes

    def allow_exact_v1(policy: object, **kwargs: object) -> None:
        if (
            getattr(policy, "schema_version", None)
            == "legalforecast.case_dev_purchase_policy.v1"
        ):
            return
        original_require(policy, **kwargs)  # type: ignore[arg-type]

    def allow_exact_v1_inputs(policy: object, **kwargs: object) -> None:
        if (
            getattr(policy, "schema_version", None)
            == "legalforecast.case_dev_purchase_policy.v1"
        ):
            return
        original_verify(policy, **kwargs)  # type: ignore[arg-type]

    def allow_exact_v1_cli_inputs(policy: object, **kwargs: object) -> None:
        if (
            getattr(policy, "schema_version", None)
            == "legalforecast.case_dev_purchase_policy.v1"
        ):
            return
        original_cli_verify(policy, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        attempt_policy_module,
        "require_approved_case_dev_purchase_policy",
        allow_exact_v1,
    )
    monkeypatch.setattr(
        attempt_policy_module,
        "verify_approved_purchase_input_bytes",
        allow_exact_v1_inputs,
    )
    monkeypatch.setattr(
        cli, "verify_approved_purchase_input_bytes", allow_exact_v1_cli_inputs
    )


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_quarantine_review_requests_reject_empty_documents() -> None:
    manifest = {
        "schema_version": "legalforecast.recap_fetch_quarantine_recovery.v1",
        "candidate_id": "case-1",
        "source_document_id": "123",
        "sha256": "a" * 64,
        "byte_count": 0,
        "free_or_purchased": "purchased",
        "recovery_origin": "unknown_status_attempt",
    }
    restriction = {
        "schema_version": "legalforecast.post_recovery_restriction_evidence.v1",
        "candidate_id": "case-1",
        "source_document_id": "123",
        "restriction_status": "public",
        "redaction_or_seal_status": "public",
        "is_sealed": False,
        "is_private": False,
        "restriction_evidence": ["fresh-public-detail"],
    }

    with pytest.raises(
        cli.RecapFetchQuarantineRecoveryError,
        match="invalid quarantine manifest record",
    ):
        cli.build_recap_fetch_disclosure_review_requests([manifest], [restriction])


def test_purchased_case_relevance_projects_only_recovered_manifest_keys() -> None:
    relevance = [
        {
            "candidate_id": "case-1",
            "case_name": "Example",
            "documents": [
                {"source_document_id": "free", "availability_status": "available"},
                {
                    "source_document_id": "paid-a",
                    "availability_status": "unavailable",
                },
                {
                    "source_document_id": "paid-b",
                    "availability_status": "unavailable",
                },
                {
                    "source_document_id": "unrecovered",
                    "availability_status": "unavailable",
                },
            ],
        }
    ]
    manifest = [
        {
            "candidate_id": "case-1",
            "source_document_id": document_id,
            "free_or_purchased": "purchased",
        }
        for document_id in ("paid-a", "paid-b")
    ]

    projected = project_purchased_case_relevance(relevance, manifest)

    assert projected == (
        {
            "candidate_id": "case-1",
            "case_name": "Example",
            "documents": [
                {
                    "source_document_id": "paid-a",
                    "availability_status": "unavailable",
                },
                {
                    "source_document_id": "paid-b",
                    "availability_status": "unavailable",
                },
            ],
        },
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_recovery", "recovered quarantine manifest repeats a document"),
        ("free_phase", "recovered quarantine manifest includes a non-purchased row"),
        ("duplicate_candidate", "target case relevance repeats a candidate"),
        ("missing_documents", "target case relevance lacks documents"),
        ("invalid_document", "target case relevance has invalid document row"),
        ("duplicate_document", "target case relevance repeats a document"),
        (
            "missing_coverage",
            "recovered quarantine document lacks target case relevance",
        ),
    ],
)
def test_purchased_case_relevance_rejects_invalid_coverage(
    mutation: str,
    message: str,
) -> None:
    relevance = [
        {
            "candidate_id": "case-1",
            "documents": [{"source_document_id": "paid"}],
        }
    ]
    manifest = [
        {
            "candidate_id": "case-1",
            "source_document_id": "paid",
            "free_or_purchased": "purchased",
        }
    ]
    if mutation == "duplicate_recovery":
        manifest.append(dict(manifest[0]))
    elif mutation == "free_phase":
        manifest[0]["free_or_purchased"] = "free"
    elif mutation == "duplicate_candidate":
        relevance.append(dict(relevance[0]))
    elif mutation == "missing_documents":
        relevance[0].pop("documents")
    elif mutation == "invalid_document":
        relevance[0]["documents"] = ["invalid"]
    elif mutation == "duplicate_document":
        relevance[0]["documents"] = [
            {"source_document_id": "paid"},
            {"source_document_id": "paid"},
        ]
    else:
        manifest[0]["source_document_id"] = "absent"

    with pytest.raises(RecapFetchQuarantineRecoveryError, match=message):
        project_purchased_case_relevance(relevance, manifest)


def test_cli_purchased_case_relevance_preserves_domain_error_message() -> None:
    with pytest.raises(
        cli.CommandError,
        match="recovered quarantine manifest includes a non-purchased row",
    ):
        cli._project_purchased_case_relevance(
            [],
            [
                {
                    "candidate_id": "case-1",
                    "source_document_id": "document-1",
                    "free_or_purchased": "free",
                }
            ],
        )


def test_quarantine_materializer_binds_clearance_to_recovery_sources(
    tmp_path: Path,
) -> None:
    review_requests = tmp_path / "recovery-review-requests.jsonl"
    restriction_evidence = tmp_path / "recovery-restriction-evidence.jsonl"
    alternate_requests = tmp_path / "alternate-review-requests.jsonl"
    alternate_restrictions = tmp_path / "alternate-restriction-evidence.jsonl"
    case_relevance = tmp_path / "purchased-case-relevance.jsonl"
    alternate_relevance = tmp_path / "alternate-case-relevance.jsonl"
    for path in (
        review_requests,
        restriction_evidence,
        alternate_requests,
        alternate_restrictions,
        case_relevance,
        alternate_relevance,
    ):
        path.write_text("{}\n", encoding="utf-8")
    recovery = {
        "recovery_stage": "recover-recap-fetch-quarantine",
        "review_requests_path": review_requests,
        "restriction_path": restriction_evidence,
        "case_relevance_path": case_relevance,
    }
    matching_clearance = {
        "requests_path": review_requests,
        "restriction_path": restriction_evidence,
        "case_relevance_path": case_relevance,
    }

    cli._verify_materializer_recovery_clearance_binding(
        recovery=recovery,
        clearance_lineage=matching_clearance,
    )
    with pytest.raises(cli.CommandError, match="different review requests"):
        cli._verify_materializer_recovery_clearance_binding(
            recovery=recovery,
            clearance_lineage={
                **matching_clearance,
                "requests_path": alternate_requests,
            },
        )
    with pytest.raises(cli.CommandError, match="different restriction evidence"):
        cli._verify_materializer_recovery_clearance_binding(
            recovery=recovery,
            clearance_lineage={
                **matching_clearance,
                "restriction_path": alternate_restrictions,
            },
        )
    with pytest.raises(cli.CommandError, match="different case relevance"):
        cli._verify_materializer_recovery_clearance_binding(
            recovery=recovery,
            clearance_lineage={
                **matching_clearance,
                "case_relevance_path": alternate_relevance,
            },
        )


def test_build_and_require_exact_unknown_origin_lineage() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)

    assert len(records) == 1
    assert records[0]["parser_eligible"] is True
    assert records[0]["packet_eligible"] is True
    assert records[0]["broker_receipt_state"] == "delivered_but_unreconciled"
    assert "delivery_authority" not in records[0]
    require_resolved_post_recovery_documents(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=inputs["clearance_records"],
        resolved_records=records,
        **_external_kwargs(inputs),
    )


def test_build_and_require_authenticated_public_material_delivery_authority() -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    material = operation["material_evidence"]
    del material["queue_response_sha256"]
    operation["status"] = "unknown"
    operation["response"] = None
    operation["actual_usd"] = None
    operation["reconciliation"] = None
    operation["public_material_recovery"] = {
        "schema_version": "legalforecast.unknown_public_material_recovery.v1",
        "candidate_id": "case-1",
        "source_document_id": "123",
        "operation_key": operation["operation_key"],
        "purchase_policy_sha256": "1" * 64,
        "attempt_policy_sha256": operation["attempt_policy_sha256"],
        "attempt_document_sha256": operation["attempt_document_sha256"],
        "provider_detail_sha256": material["provider_detail_sha256"],
        "download_url_sha256": material["download_url_sha256"],
        "billing_status": "unknown",
        "reservation_retained": True,
        "no_paid_redispatch": True,
    }
    inputs["purchase_operation_records"] = [operation]

    records = build_resolved_post_recovery_documents(**inputs)

    assert records[0]["delivery_authority"] == (
        "authenticated_public_material_recovery"
    )
    assert records[0]["schema_version"] == (
        "legalforecast.resolved_post_recovery_public_document.v3"
    )
    assert "clearance_basis" not in records[0]
    assert records[0]["purchase_policy_sha256"] == "1" * 64
    assert records[0]["public_material_recovery_sha256"] == _hash(
        operation["public_material_recovery"]
    )
    assert "broker_receipt_sha256" not in records[0]
    assert "queue_response_sha256" not in records[0]
    require_resolved_post_recovery_documents(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=inputs["clearance_records"],
        resolved_records=records,
        **_external_kwargs(inputs),
    )
    require_resolved_post_recovery_operation_bindings(
        purchase_operation_records=[operation],
        resolved_records=records,
        expected_purchase_policy_sha256="1" * 64,
    )
    relabeled_v4 = deepcopy(records[0])
    relabeled_v4.update(
        {
            "schema_version": (
                "legalforecast.resolved_post_recovery_public_document.v4"
            ),
            "clearance_basis": "provider_free_recovered_public",
            "recovered_public_lineage": {},
        }
    )
    for field in (
        "reviews_artifact_sha256",
        "review_receipt_sha256",
        "review_authority_sha256",
    ):
        relabeled_v4.pop(field)
    relabeled_v4["record_sha256"] = _hash(
        {name: value for name, value in relabeled_v4.items() if name != "record_sha256"}
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="resolved document delivery authority is invalid",
    ):
        cast(Any, resolved_module._validate_resolved_record)(
            relabeled_v4, key=("case-1", "123")
        )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="purchase policy differs from attempt authority",
    ):
        require_resolved_post_recovery_operation_bindings(
            purchase_operation_records=[operation],
            resolved_records=records,
            expected_purchase_policy_sha256="9" * 64,
        )

    wrong_policy = deepcopy(operation)
    wrong_policy["public_material_recovery"]["purchase_policy_sha256"] = "9" * 64
    with pytest.raises(
        ResolvedPostRecoveryError, match="purchase policy differs from attempt"
    ):
        build_resolved_post_recovery_documents(
            **{**inputs, "purchase_operation_records": [wrong_policy]}
        )

    contradictory_queue = deepcopy(operation)
    contradictory_queue["material_evidence"]["queue_response_sha256"] = "3" * 64
    with pytest.raises(ResolvedPostRecoveryError, match="conflicts with purchase"):
        build_resolved_post_recovery_documents(
            **{**inputs, "purchase_operation_records": [contradictory_queue]}
        )


def test_resolved_recovery_accepts_exact_corrected_v2_and_rejects_tampering() -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    material = operation["material_evidence"]
    del material["queue_response_sha256"]
    operation.update(
        {
            "status": "unknown",
            "response": None,
            "actual_usd": None,
            "reconciliation": None,
            "reservation_usd": "3.05",
        }
    )
    operation["public_material_recovery"] = _corrected_public_recovery(operation)
    inputs["purchase_operation_records"] = [operation]

    records = build_resolved_post_recovery_documents(**inputs)

    assert records[0]["delivery_authority"] == (
        "authenticated_public_material_recovery"
    )
    assert records[0]["public_material_recovery_sha256"] == _hash(
        operation["public_material_recovery"]
    )
    require_resolved_post_recovery_documents(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=inputs["clearance_records"],
        resolved_records=records,
        **_external_kwargs(inputs),
    )
    require_resolved_post_recovery_operation_bindings(
        purchase_operation_records=[operation],
        resolved_records=records,
        expected_purchase_policy_sha256="1" * 64,
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="purchase policy differs from attempt authority",
    ):
        require_resolved_post_recovery_operation_bindings(
            purchase_operation_records=[operation],
            resolved_records=records,
            expected_purchase_policy_sha256="9" * 64,
        )

    for field, value in (
        ("record_sha256", "0" * 64),
        ("legacy_recovery_record_sha256", "0" * 64),
        ("legacy_download_url_sha256", material["download_url_sha256"]),
    ):
        tampered = deepcopy(operation)
        tampered["public_material_recovery"]["courtlistener_url_commitment_correction"][
            field
        ] = value
        with pytest.raises(ResolvedPostRecoveryError, match="conflicts with purchase"):
            build_resolved_post_recovery_documents(
                **{**inputs, "purchase_operation_records": [tampered]}
            )

    wrong_basis = deepcopy(records[0])
    wrong_basis["clearance_basis"] = "affirmative_public_provenance"
    wrong_basis["record_sha256"] = _hash(
        {name: value for name, value in wrong_basis.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="schema does not match"):
        require_resolved_post_recovery_documents(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[wrong_basis],
            **_external_kwargs(inputs),
        )

    contradictory_provider_free_basis = deepcopy(records[0])
    contradictory_provider_free_basis["clearance_basis"] = (
        "provider_free_recovered_public"
    )
    contradictory_provider_free_basis["record_sha256"] = _hash(
        {
            name: value
            for name, value in contradictory_provider_free_basis.items()
            if name != "record_sha256"
        }
    )
    with pytest.raises(ResolvedPostRecoveryError, match="recovered-public lineage"):
        require_resolved_post_recovery_documents(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[contradictory_provider_free_basis],
            **_external_kwargs(inputs),
        )


@pytest.mark.parametrize(
    ("status", "actual_usd", "reconciliation"),
    (
        ("failed", None, {"disposition": "failed"}),
        ("unknown", None, {"disposition": "write_off"}),
        ("confirmed", "3.05", {"disposition": "confirmed"}),
    ),
)
def test_public_material_authority_survives_later_billing_settlement(
    status: str,
    actual_usd: str | None,
    reconciliation: dict[str, str],
) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    material = operation["material_evidence"]
    del material["queue_response_sha256"]
    operation.update(
        {
            "status": status,
            "actual_usd": actual_usd,
            "reconciliation": reconciliation,
            "response": {"broker_receipts": [{"billing_only": True}]},
            "public_material_recovery": {
                "schema_version": ("legalforecast.unknown_public_material_recovery.v1"),
                "candidate_id": "case-1",
                "source_document_id": "123",
                "operation_key": operation["operation_key"],
                "purchase_policy_sha256": "1" * 64,
                "attempt_policy_sha256": operation["attempt_policy_sha256"],
                "attempt_document_sha256": operation["attempt_document_sha256"],
                "provider_detail_sha256": material["provider_detail_sha256"],
                "download_url_sha256": material["download_url_sha256"],
                "billing_status": "unknown",
                "reservation_retained": True,
                "no_paid_redispatch": True,
            },
        }
    )
    inputs["purchase_operation_records"] = [operation]

    records = build_resolved_post_recovery_documents(**inputs)

    assert records[0]["delivery_authority"] == (
        "authenticated_public_material_recovery"
    )
    require_resolved_post_recovery_operation_bindings(
        purchase_operation_records=[operation],
        resolved_records=records,
        expected_purchase_policy_sha256="1" * 64,
    )


def test_public_api_rejects_caller_fabricated_provenance_lineage(
    tmp_path: Path,
) -> None:
    inputs = _inputs()
    decisions = [
        {
            "candidate_id": "case-1",
            "source_document_id": "123",
            "status": "cleared",
            "reviewer_id": "John Hughes",
            "reviewed_at": "2026-07-15T00:00:00Z",
        }
    ]
    decisions_bytes = _jsonl_bytes(decisions)
    recorder_bytes = _object_bytes({"stage": "record-disclosure-review-decisions"})
    routing_bytes = _object_bytes({"schema_version": "routing.v1"})
    clearance_bytes = inputs["clearance_artifact_bytes"]
    cohort_bytes = inputs["cohort_policy_artifact_bytes"]
    restriction_bytes = inputs["restriction_artifact_bytes"]
    authority = {
        "kind": "provenance_first_with_john_exceptions",
        "authentication_claim": "interactive_hash_confirmation_only",
        "exception_reviewer_id": "John Hughes",
        "exception_decisions_sha256": "sha256:"
        + hashlib.sha256(decisions_bytes).hexdigest(),
        "exception_review_run_card_sha256": "sha256:"
        + hashlib.sha256(recorder_bytes).hexdigest(),
        "routing_plan_sha256": "sha256:" + hashlib.sha256(routing_bytes).hexdigest(),
    }
    run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "generated_at": "2026-07-15T00:00:00Z",
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "exception_decisions": {
                "sha256": hashlib.sha256(decisions_bytes).hexdigest()
            },
            "exception_review_run_card": {
                "sha256": hashlib.sha256(recorder_bytes).hexdigest()
            },
            "routing_plan": {"sha256": hashlib.sha256(routing_bytes).hexdigest()},
            "cohort_policy": {"sha256": hashlib.sha256(cohort_bytes).hexdigest()},
            "restriction_evidence": {
                "sha256": hashlib.sha256(restriction_bytes).hexdigest()
            },
        },
        "output_commitments": {
            "disclosure_clearance": {
                "sha256": hashlib.sha256(clearance_bytes).hexdigest()
            }
        },
        "clearance_authority": authority,
    }
    run_card_bytes = _object_bytes(run_card)
    review_authority = ReviewAuthority(
        reviewer_id="John Hughes",
        controlled_store_uri="private-store://john/disclosure-exception-review",
        authentication_method="interactive_hash_confirmation_only",
        authenticated_at="2026-07-15T00:00:00Z",
        review_artifact_sha256=hashlib.sha256(decisions_bytes).hexdigest(),
        reviewer_policy_sha256=hashlib.sha256(routing_bytes).hexdigest(),
    )
    provenance_lineage = AuthenticatedClearanceLineage(
        clearance_run_card_sha256=hashlib.sha256(run_card_bytes).hexdigest(),
        clearance_artifact_sha256=hashlib.sha256(clearance_bytes).hexdigest(),
        reviews_artifact_sha256=hashlib.sha256(decisions_bytes).hexdigest(),
        review_receipt_sha256=hashlib.sha256(recorder_bytes).hexdigest(),
        cohort_policy_artifact_sha256=hashlib.sha256(cohort_bytes).hexdigest(),
        restriction_evidence_artifact_sha256=hashlib.sha256(
            restriction_bytes
        ).hexdigest(),
        review_authority_sha256=resolved_module._sha256(authority),
        authority=review_authority,
    )
    fabricated_inputs = {
        **inputs,
        "clearance_run_card": run_card,
        "clearance_run_card_bytes": run_card_bytes,
        "reviews_artifact_bytes": decisions_bytes,
        "review_receipt_bytes": recorder_bytes,
        "reviewer_policy_bytes": routing_bytes,
        "disclosure_authority": None,
        "verified_provenance_lineage": provenance_lineage,
    }
    with pytest.raises(
        ResolvedPostRecoveryError, match="caller-supplied authenticated"
    ):
        cast(Any, build_resolved_post_recovery_documents_with_authenticated_lineage)(
            **fabricated_inputs
        )
    require_inputs = {
        name: value
        for name, value in fabricated_inputs.items()
        if name not in {"attempt_policy_artifact", "purchase_operation_records"}
    }
    with pytest.raises(
        ResolvedPostRecoveryError, match="caller-supplied authenticated"
    ):
        cast(Any, require_resolved_post_recovery_documents_with_authenticated_lineage)(
            **require_inputs,
            resolved_records=[],
        )

    private_build_inputs = {
        name: value
        for name, value in fabricated_inputs.items()
        if name != "verified_provenance_lineage"
    }
    private_require_inputs = {
        name: value
        for name, value in require_inputs.items()
        if name != "verified_provenance_lineage"
    }
    for capability_kwargs in ({}, {"verified_lineage_capability": object()}):
        with pytest.raises(ResolvedPostRecoveryError, match="authenticated capability"):
            cast(
                Any,
                resolved_module._build_resolved_post_recovery_documents_with_authenticated_lineage,
            )(**private_build_inputs, **capability_kwargs)
        with pytest.raises(ResolvedPostRecoveryError, match="authenticated capability"):
            cast(
                Any,
                resolved_module._require_resolved_post_recovery_documents_with_authenticated_lineage,
            )(
                **private_require_inputs,
                **capability_kwargs,
                resolved_records=[],
            )

    issue_capability = cast(Any, resolved_module._issue_verified_lineage_capability)
    issuer_signature = inspect.signature(issue_capability)
    assert tuple(issuer_signature.parameters) == (
        "clearance_path",
        "clearance_run_card_path",
        "expected_download_manifest_path",
        "expected_restriction_path",
        "captured_artifact_bytes",
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in issuer_signature.parameters.values()
    )
    assert issue_capability.__kwdefaults__ is None
    with pytest.raises(TypeError, match="provenance_lineage"):
        issue_capability(provenance_lineage=provenance_lineage)

    fabricated_clearance_path = tmp_path / "fabricated-clearance.jsonl"
    fabricated_run_card_path = tmp_path / "fabricated-clearance-run-card.json"
    fabricated_clearance_path.write_bytes(clearance_bytes)
    fabricated_run_card_path.write_bytes(run_card_bytes)
    fabricated_snapshot = {
        str(fabricated_clearance_path.resolve()): clearance_bytes,
        str(fabricated_run_card_path.resolve()): run_card_bytes,
    }
    with pytest.raises(
        (ResolvedPostRecoveryError, cli.CommandError),
        match=r"commitment|artifact|path|snapshot",
    ):
        issue_capability(
            clearance_path=fabricated_clearance_path,
            clearance_run_card_path=fabricated_run_card_path,
            expected_download_manifest_path=tmp_path / "fabricated-manifest.jsonl",
            expected_restriction_path=tmp_path / "fabricated-restriction.jsonl",
            captured_artifact_bytes=fabricated_snapshot,
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


def test_recovered_public_capability_builds_and_requires_resolved_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs()
    operation = inputs["purchase_operation_records"][0]
    lineage = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": "4" * 64,
        "recovery_restriction_evidence_sha256": "5" * 64,
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": _hash(operation),
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": "2" * 64,
    }
    clearance = deepcopy(inputs["clearance_records"][0])
    clearance.update(
        {
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
            "reviewer_id": None,
            "controlled_store_provenance": ("courtlistener-rest://recap-documents/123"),
            "reviewed_at": None,
            "clearance_basis": "provider_free_recovered_public",
            "routing_plan_sha256": "7" * 64,
            "recovered_public_lineage": lineage,
        }
    )
    clearance_bytes = _jsonl_bytes([clearance])
    with pytest.raises(
        cli.ProvenanceClearanceError,
        match="invalid direct queue delivery authority",
    ):
        issue_recovered_public_capability(
            monkeypatch,
            [{**lineage, "direct_queue_delivery_authority": None}],
        )
    capability = issue_recovered_public_capability(monkeypatch, [lineage])
    kwargs = {
        **inputs,
        "clearance_records": [clearance],
        "clearance_artifact_bytes": clearance_bytes,
    }
    records = build_recovered(
        **kwargs,
        verified_recovery_capability=capability,
    )

    assert records[0]["schema_version"] == (
        "legalforecast.resolved_post_recovery_public_document.v2"
    )
    assert records[0]["clearance_basis"] == "provider_free_recovered_public"
    assert records[0]["recovered_public_lineage"] == lineage
    assert "review_authority_sha256" not in records[0]
    assert "reviews_artifact_sha256" not in records[0]
    require_recovered(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=[clearance],
        resolved_records=records,
        **_external_kwargs(kwargs),
        verified_recovery_capability=capability,
    )

    changed = deepcopy(records[0])
    changed["recovered_public_lineage"]["purchase_operation_sha256"] = "8" * 64
    changed["record_sha256"] = _hash(
        {name: value for name, value in changed.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="recovered-public lineage"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=[clearance],
            resolved_records=[changed],
            **_external_kwargs(kwargs),
            verified_recovery_capability=capability,
        )
    wrong_basis = deepcopy(records[0])
    wrong_basis["clearance_basis"] = "affirmative_public_provenance"
    wrong_basis["record_sha256"] = _hash(
        {name: value for name, value in wrong_basis.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="schema does not match"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=[clearance],
            resolved_records=[wrong_basis],
            **_external_kwargs(kwargs),
            verified_recovery_capability=capability,
        )


def test_recovered_public_capability_authorizes_exact_direct_queue_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    operation["reservation_usd"] = "3.05"
    operation["response"] = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
        "queue_id": "77",
        "reservation_id": f"direct:{operation['operation_key']}",
    }
    inputs["purchase_operation_records"] = [operation]
    lineage = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": "4" * 64,
        "recovery_restriction_evidence_sha256": "5" * 64,
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": _hash(operation),
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": "2" * 64,
        **cli._direct_queue_delivery_lineage(
            operation,
            purchase_policy_sha256="1" * 64,
            recovery_run_card_sha256="3" * 64,
            recovery_manifest_sha256="4" * 64,
            recovery_restriction_sha256="5" * 64,
            purchase_state_sha256="6" * 64,
        ),
    }
    clearance = deepcopy(inputs["clearance_records"][0])
    clearance.update(
        {
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
            "reviewer_id": None,
            "controlled_store_provenance": ("courtlistener-rest://recap-documents/123"),
            "reviewed_at": None,
            "clearance_basis": "provider_free_recovered_public",
            "routing_plan_sha256": "7" * 64,
            "recovered_public_lineage": lineage,
        }
    )
    inputs.update(
        {
            "clearance_records": [clearance],
            "clearance_artifact_bytes": _jsonl_bytes([clearance]),
        }
    )
    capability = issue_recovered_public_capability(monkeypatch, [lineage])

    records = build_recovered(
        **inputs,
        verified_recovery_capability=capability,
    )

    assert records[0]["schema_version"] == (
        "legalforecast.resolved_post_recovery_public_document.v4"
    )
    assert records[0]["delivery_authority"] == (
        "authenticated_direct_courtlistener_queue"
    )
    assert (
        records[0]["direct_queue_delivery_authority"]
        == lineage["direct_queue_delivery_authority"]
    )
    assert "broker_receipt_sha256" not in records[0]
    assert "broker_receipt_state" not in records[0]
    require_recovered(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=[clearance],
        resolved_records=records,
        **_external_kwargs(inputs),
        verified_recovery_capability=capability,
    )
    resolved_module._require_resolved_recovered_public_operation_bindings(  # pyright: ignore[reportPrivateUsage]
        purchase_operation_records=[operation],
        resolved_records=records,
        expected_purchase_policy_sha256="1" * 64,
        verified_recovery_capability=capability,
    )
    cleared_operation = deepcopy(operation)
    cleared_operation["material_state"] = "cleared_public"
    cleared_operation["resolved_document_sha256"] = records[0]["record_sha256"]
    cleared_operation["material_evidence"]["clearance_record_sha256"] = records[0][
        "clearance_record_sha256"
    ]
    resolved_module._require_resolved_recovered_public_operation_bindings(  # pyright: ignore[reportPrivateUsage]
        purchase_operation_records=[cleared_operation],
        resolved_records=records,
        expected_purchase_policy_sha256="1" * 64,
        verified_recovery_capability=capability,
    )
    legacy = deepcopy(records[0])
    legacy["delivery_authority"] = "authenticated_direct_courtlistener_queue_recovery"
    legacy["queue_response_sha256"] = operation["material_evidence"][
        "queue_response_sha256"
    ]
    legacy.pop("direct_queue_delivery_authority")
    legacy["recovered_public_lineage"].pop("direct_queue_delivery_authority")
    legacy["record_sha256"] = _hash(
        {name: value for name, value in legacy.items() if name != "record_sha256"}
    )
    require_recovered(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=[clearance],
        resolved_records=[legacy],
        **_external_kwargs(inputs),
        verified_recovery_capability=capability,
    )
    lineage_without_direct = deepcopy(lineage)
    lineage_without_direct.pop("direct_queue_delivery_authority")
    nondirect_capability = issue_recovered_public_capability(
        monkeypatch, [lineage_without_direct]
    )
    with pytest.raises(ResolvedPostRecoveryError, match="lineage changed"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=[clearance],
            resolved_records=[legacy],
            **_external_kwargs(inputs),
            verified_recovery_capability=nondirect_capability,
        )
    parse_request = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_origin": "unknown_status_attempt",
        "expected_sha256": legacy["content_sha256"],
        "expected_byte_count": legacy["byte_count"],
        "resolved_post_recovery_sha256": legacy["record_sha256"],
    }
    with pytest.raises(
        ResolvedPostRecoveryError, match="verifier-issued recovery authority"
    ):
        resolved_module._require_resolved_recovered_public_parse_requests(  # pyright: ignore[reportPrivateUsage]
            selection_records=inputs["selection_records"],
            request_records=[parse_request],
            resolved_records=[legacy],
            verified_recovery_capability=nondirect_capability,
        )
    resolved_module._require_resolved_recovered_public_operation_bindings(  # pyright: ignore[reportPrivateUsage]
        purchase_operation_records=[operation],
        resolved_records=[legacy],
        expected_purchase_policy_sha256="1" * 64,
        verified_recovery_capability=capability,
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="verifier-issued recovery authority",
    ):
        require_resolved_post_recovery_operation_bindings(
            purchase_operation_records=[operation],
            resolved_records=records,
            expected_purchase_policy_sha256="1" * 64,
        )

    mutations: tuple[tuple[str, object], ...] = (
        ("status", "confirmed"),
        ("actual_usd", "0.01"),
        ("reconciliation", {}),
        ("error", "failed"),
        ("source_provider", "courtlistener"),
        ("queue_id", "0"),
        ("reservation_id", "reservation-1"),
        ("reservation_usd", "3.06"),
        ("queue_response_sha256", "8" * 64),
        ("broker_receipts", []),
    )
    for field, value in mutations:
        changed = deepcopy(operation)
        if field in {"status", "actual_usd", "reconciliation", "error"}:
            changed[field] = value
        elif field == "queue_response_sha256":
            changed["material_evidence"][field] = value
        else:
            changed["response"][field] = value
        with pytest.raises(
            ResolvedPostRecoveryError,
            match="direct queue delivery authority",
        ):
            build_recovered(
                **{**inputs, "purchase_operation_records": [changed]},
                verified_recovery_capability=capability,
            )

    tampered = deepcopy(records[0])
    tampered["direct_queue_delivery_authority"]["queue_id"] = "78"
    tampered["record_sha256"] = _hash(
        {name: value for name, value in tampered.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="direct queue"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=[clearance],
            resolved_records=[tampered],
            **_external_kwargs(inputs),
            verified_recovery_capability=capability,
        )

    open_schema = deepcopy(records[0])
    open_schema["broker_receipts"] = []
    open_schema["record_sha256"] = _hash(
        {name: value for name, value in open_schema.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="direct queue"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=[clearance],
            resolved_records=[open_schema],
            **_external_kwargs(inputs),
            verified_recovery_capability=capability,
        )


def test_recovered_public_resolver_omits_authenticated_terminal_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    operation["reservation_usd"] = "3.05"
    operation["response"] = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
        "queue_id": "77",
        "reservation_id": f"direct:{operation['operation_key']}",
    }
    inputs["purchase_operation_records"] = [operation]
    lineage = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": "4" * 64,
        "recovery_restriction_evidence_sha256": "5" * 64,
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": _hash(operation),
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": "2" * 64,
        **cli._direct_queue_delivery_lineage(
            operation,
            purchase_policy_sha256="1" * 64,
            recovery_run_card_sha256="3" * 64,
            recovery_manifest_sha256="4" * 64,
            recovery_restriction_sha256="5" * 64,
            purchase_state_sha256="6" * 64,
        ),
    }
    clearance = deepcopy(inputs["clearance_records"][0])
    clearance.update(
        {
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
            "reviewer_id": None,
            "controlled_store_provenance": "courtlistener-rest://recap-documents/123",
            "reviewed_at": None,
            "clearance_basis": "provider_free_recovered_public",
            "routing_plan_sha256": "7" * 64,
            "recovered_public_lineage": lineage,
        }
    )
    inputs.update(
        {
            "clearance_records": [clearance],
            "clearance_artifact_bytes": _jsonl_bytes([clearance]),
        }
    )

    terminal_document = {
        "source_document_id": "456",
        "redaction_or_seal_status": "unknown",
        "is_sealed": None,
        "is_private": None,
        "is_available": False,
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
    }
    inputs["selection_records"].append(
        {
            "candidate_id": "case-terminal",
            "selected": True,
            "exclusion_reasons": [],
            "documents": [terminal_document],
        }
    )
    attempt = inputs["attempt_policy_artifact"]
    policy = cast(dict[str, object], attempt["policy"])
    allowed = cast(list[dict[str, object]], policy["allowed_documents"])
    allowed.append(
        {
            "case_id": "case-terminal",
            "recap_document": "456",
            "evidence_class": "unknown_status_quarantine",
            "selection_document_sha256": _hash(terminal_document),
        }
    )
    attempt["policy_sha256"] = _hash(policy)
    operation["attempt_policy_sha256"] = attempt["policy_sha256"]
    inputs["download_records"][0]["attempt_policy_sha256"] = attempt["policy_sha256"]
    lineage["purchase_operation_sha256"] = _hash(operation)
    lineage.update(
        cli._direct_queue_delivery_lineage(
            operation,
            purchase_policy_sha256="1" * 64,
            recovery_run_card_sha256="3" * 64,
            recovery_manifest_sha256="4" * 64,
            recovery_restriction_sha256="5" * 64,
            purchase_state_sha256="6" * 64,
        )
    )
    inputs["clearance_records"][0]["recovered_public_lineage"] = lineage
    inputs["clearance_artifact_bytes"] = _jsonl_bytes(inputs["clearance_records"])
    terminal_operation = deepcopy(operation)
    terminal_operation.update(
        {
            "candidate_id": "case-terminal",
            "source_document_id": "456",
            "status": "failed",
            "attempt_document_sha256": _hash(terminal_document),
        }
    )
    inputs["purchase_operation_records"].append(terminal_operation)
    terminal = {
        "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
        "candidate_id": "case-terminal",
        "source_document_id": "456",
    }
    capability = issue_recovered_public_capability(
        monkeypatch,
        [lineage],
        terminal_records=[terminal],
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="does not exactly cover recovered documents",
    ):
        build_recovered(
            **inputs,
            verified_recovery_capability=capability,
        )
    terminal_capability = issue_terminal_disposition_capability(
        monkeypatch,
        capability,
        [terminal],
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="terminal disposition authority requires recovered-public authority",
    ):
        build_recovered(
            **inputs,
            verified_terminal_disposition_capability=terminal_capability,
        )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="terminal disposition authority requires recovered-public authority",
    ):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[],
            **_external_kwargs(inputs),
            verified_terminal_disposition_capability=terminal_capability,
        )

    records = build_recovered(
        **inputs,
        verified_recovery_capability=capability,
        verified_terminal_disposition_capability=terminal_capability,
    )

    assert [(row["candidate_id"], row["source_document_id"]) for row in records] == [
        ("case-1", "123")
    ]
    require_recovered(
        selection_records=inputs["selection_records"],
        download_records=inputs["download_records"],
        clearance_records=inputs["clearance_records"],
        resolved_records=records,
        **_external_kwargs(inputs),
        verified_recovery_capability=capability,
        verified_terminal_disposition_capability=terminal_capability,
    )

    forged_terminal = {
        **records[0],
        "candidate_id": "case-terminal",
        "source_document_id": "456",
    }
    with pytest.raises(ResolvedPostRecoveryError, match="coverage mismatch"):
        require_recovered(
            selection_records=inputs["selection_records"],
            download_records=inputs["download_records"],
            clearance_records=inputs["clearance_records"],
            resolved_records=[*records, forged_terminal],
            **_external_kwargs(inputs),
            verified_recovery_capability=capability,
            verified_terminal_disposition_capability=terminal_capability,
        )
    with pytest.raises(ResolvedPostRecoveryError, match="terminal-unavailable"):
        resolved_module._require_resolved_recovered_public_operation_bindings(  # pyright: ignore[reportPrivateUsage]
            purchase_operation_records=inputs["purchase_operation_records"],
            resolved_records=[*records, forged_terminal],
            expected_purchase_policy_sha256="1" * 64,
            verified_recovery_capability=capability,
            verified_terminal_disposition_capability=terminal_capability,
        )
    forged_request = {
        "candidate_id": "case-terminal",
        "source_document_id": "456",
        "recovery_origin": "unknown_status_attempt",
        "resolved_post_recovery_sha256": forged_terminal["record_sha256"],
    }
    with pytest.raises(ResolvedPostRecoveryError, match="overlaps parser requests"):
        resolved_module._require_resolved_recovered_public_parse_requests(  # pyright: ignore[reportPrivateUsage]
            selection_records=inputs["selection_records"],
            request_records=[forged_request],
            resolved_records=[*records, forged_terminal],
            verified_recovery_capability=capability,
            verified_terminal_disposition_capability=terminal_capability,
        )


def test_cli_derives_direct_queue_authority_from_authenticated_recovery_bytes(
    tmp_path: Path,
) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    operation["reservation_usd"] = "3.05"
    operation["response"] = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
        "queue_id": "77",
        "reservation_id": f"direct:{operation['operation_key']}",
    }
    manifest_path = tmp_path / "manifest.jsonl"
    restriction_path = tmp_path / "restrictions.jsonl"
    run_card_path = tmp_path / "run-card.json"
    manifest_record = {
        **inputs["download_records"][0],
        "fresh_recap_detail_sha256": "2" * 64,
    }
    manifest_path.write_bytes(_jsonl_bytes([manifest_record]))
    restriction_path.write_bytes(_jsonl_bytes(inputs["restriction_records"]))
    _write_object(
        run_card_path,
        {"output_commitments": {"purchase_state_sha256": "6" * 64}},
    )
    recovery = {
        "run_card_path": run_card_path,
        "manifest_records": [manifest_record],
        "historical_purchase_operations": [operation],
        "historical_purchase_state_sha256": "6" * 64,
        "purchase_policy_sha256": "1" * 64,
        "verified_artifact_bytes": {
            str(run_card_path.absolute()): run_card_path.read_bytes(),
            str(manifest_path.absolute()): manifest_path.read_bytes(),
            str(restriction_path.absolute()): restriction_path.read_bytes(),
        },
    }

    rows = cli._derive_recovered_public_lineage_rows(
        recovery,
        expected_manifest_path=manifest_path,
        expected_restriction_path=restriction_path,
    )

    assert len(rows) == 1
    authority = rows[0]["direct_queue_delivery_authority"]
    assert authority["purchase_operation_sha256"] == _hash(operation)
    assert authority["purchase_response_sha256"] == _hash(operation["response"])
    assert authority["queue_response_sha256"] == "3" * 64
    assert "broker_receipts" not in operation["response"]


@pytest.mark.parametrize(
    ("field", "value"),
    (("actual_usd", "0.01"), ("reconciliation", {}), ("error", "failed")),
)
def test_cli_refuses_direct_queue_authority_with_contradictory_queued_state(
    field: str,
    value: object,
) -> None:
    operation = deepcopy(_inputs()["purchase_operation_records"][0])
    operation["reservation_usd"] = "3.05"
    operation["response"] = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
        "queue_id": "77",
        "reservation_id": f"direct:{operation['operation_key']}",
    }
    operation[field] = value

    assert (
        cli._direct_queue_delivery_lineage(
            operation,
            purchase_policy_sha256="1" * 64,
            recovery_run_card_sha256="3" * 64,
            recovery_manifest_sha256="4" * 64,
            recovery_restriction_sha256="5" * 64,
            purchase_state_sha256="6" * 64,
        )
        == {}
    )


def test_cli_rejects_direct_queue_broker_history_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _inputs()
    operation = deepcopy(inputs["purchase_operation_records"][0])
    broker_receipts = deepcopy(operation["response"]["broker_receipts"])
    operation["reservation_usd"] = "3.05"
    operation["response"] = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
        "queue_id": "77",
        "reservation_id": f"direct:{operation['operation_key']}",
    }
    lineage = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": "4" * 64,
        "recovery_restriction_evidence_sha256": "5" * 64,
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": _hash(operation),
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": "2" * 64,
        **cli._direct_queue_delivery_lineage(
            operation,
            purchase_policy_sha256="1" * 64,
            recovery_run_card_sha256="3" * 64,
            recovery_manifest_sha256="4" * 64,
            recovery_restriction_sha256="5" * 64,
            purchase_state_sha256="6" * 64,
        ),
    }
    clearance = deepcopy(inputs["clearance_records"][0])
    clearance.update(
        {
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
            "reviewer_id": None,
            "controlled_store_provenance": "courtlistener-rest://recap-documents/123",
            "reviewed_at": None,
            "clearance_basis": "provider_free_recovered_public",
            "routing_plan_sha256": "7" * 64,
            "recovered_public_lineage": lineage,
        }
    )
    capability = issue_recovered_public_capability(monkeypatch, [lineage])
    clearance_kwargs = {
        **_external_kwargs(inputs),
        "clearance_artifact_bytes": _jsonl_bytes([clearance]),
        "_verified_recovery_capability": capability,
    }

    changed_operation = deepcopy(operation)
    changed_operation["response"]["broker_receipts"] = broker_receipts

    class ObservedJournal:
        clear_calls = 0
        operations: ClassVar[list[dict[str, Any]]] = [changed_operation]

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> ObservedJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def purchase_state_sha256(self) -> str:
            return "9" * 64

        def operation_records(self) -> list[dict[str, Any]]:
            return deepcopy(self.operations)

        def clear_unknown_material(self, *_args: object, **_kwargs: object) -> None:
            type(self).clear_calls += 1

    paths = {
        "selection": tmp_path / "selection.jsonl",
        "purchase_policy": tmp_path / "purchase-policy.json",
        "cohort_policy": tmp_path / "cohort-policy.json",
        "budget_plan": tmp_path / "budget-plan.json",
        "purchase_ledger": tmp_path / "purchases.sqlite3",
        "attempt_policy": tmp_path / "attempt-policy.json",
        "download_manifest": tmp_path / "downloads.jsonl",
        "disclosure_clearance": tmp_path / "clearance.jsonl",
        "clearance_run_card": tmp_path / "clearance-run-card.json",
        "restriction_evidence": tmp_path / "restrictions.jsonl",
    }
    _write_records(paths["selection"], inputs["selection_records"])
    _write_records(paths["download_manifest"], inputs["download_records"])
    _write_records(paths["disclosure_clearance"], [clearance])
    _write_object(paths["clearance_run_card"], {})
    _write_records(paths["restriction_evidence"], inputs["restriction_records"])
    _write_object(paths["attempt_policy"], inputs["attempt_policy_artifact"])
    for name in (
        "purchase_policy",
        "cohort_policy",
        "budget_plan",
    ):
        _write_object(paths[name], {})

    monkeypatch.setattr(cli, "_preflight_current_purchase_snapshot", lambda _args: None)
    monkeypatch.setattr(
        cli, "_preflight_approved_purchase_input_bytes", lambda _args: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy",
        lambda _artifact: SimpleNamespace(
            canonical_ledger_path=paths["purchase_ledger"].resolve(),
            policy_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli, "verify_approved_purchase_input_bytes", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(cli, "_missing_core_budget_plan", lambda _artifact: object())
    monkeypatch.setattr(
        cli, "verify_recap_fetch_attempt_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "_authenticated_clearance_lineage_inputs",
        lambda *_args, **_kwargs: (clearance_kwargs, ()),
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", ObservedJournal)

    output_root = tmp_path / "output"
    command = [
        "acquisition",
        "resolve-post-recovery-documents",
        *[
            value
            for name, path in paths.items()
            for value in (f"--{name.replace('_', '-')}", str(path))
        ],
        "--output-root",
        str(output_root),
        "--execute",
    ]
    journal_before = deepcopy(ObservedJournal.operations)

    assert cli.main(command) == 2

    assert "direct queue delivery authority conflicts with purchase" in (
        capsys.readouterr().err
    )
    assert ObservedJournal.operations == journal_before
    assert ObservedJournal.clear_calls == 0
    assert not (output_root / "resolved-post-recovery-documents.jsonl").exists()
    assert not (output_root / "run-cards/resolve-post-recovery-documents.json").exists()


def test_resolve_post_recovery_cli_collect_all_exits_nonzero_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _collect_all_inputs()
    inputs["attempt_policy_artifact"]["policy"]["allowed_documents"][0][
        "selection_document_sha256"
    ] = "0" * 64
    inputs["attempt_policy_artifact"]["policy_sha256"] = _hash(
        inputs["attempt_policy_artifact"]["policy"]
    )
    for record in inputs["purchase_operation_records"]:
        record["attempt_policy_sha256"] = inputs["attempt_policy_artifact"][
            "policy_sha256"
        ]
    for record in inputs["download_records"]:
        record["attempt_policy_sha256"] = inputs["attempt_policy_artifact"][
            "policy_sha256"
        ]

    class ObservedJournal:
        clear_calls = 0
        operations: ClassVar[list[dict[str, Any]]] = deepcopy(
            inputs["purchase_operation_records"]
        )

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> ObservedJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def purchase_state_sha256(self) -> str:
            return "9" * 64

        def operation_records(self) -> list[dict[str, Any]]:
            return deepcopy(self.operations)

        def clear_unknown_material(self, *_args: object, **_kwargs: object) -> None:
            type(self).clear_calls += 1

    paths = {
        "selection": tmp_path / "selection.jsonl",
        "purchase_policy": tmp_path / "purchase-policy.json",
        "cohort_policy": tmp_path / "cohort-policy.json",
        "budget_plan": tmp_path / "budget-plan.json",
        "purchase_ledger": tmp_path / "purchases.sqlite3",
        "attempt_policy": tmp_path / "attempt-policy.json",
        "download_manifest": tmp_path / "downloads.jsonl",
        "disclosure_clearance": tmp_path / "clearance.jsonl",
        "clearance_run_card": tmp_path / "clearance-run-card.json",
        "restriction_evidence": tmp_path / "restrictions.jsonl",
    }
    _write_records(paths["selection"], inputs["selection_records"])
    _write_records(paths["download_manifest"], inputs["download_records"])
    _write_records(paths["disclosure_clearance"], inputs["clearance_records"])
    _write_object(paths["clearance_run_card"], inputs["clearance_run_card"])
    _write_records(paths["restriction_evidence"], inputs["restriction_records"])
    _write_object(paths["attempt_policy"], inputs["attempt_policy_artifact"])
    for name in ("purchase_policy", "cohort_policy", "budget_plan"):
        _write_object(paths[name], {})

    clearance_kwargs = {
        **_external_kwargs(inputs),
        "_verified_clearance_source_snapshots": {},
    }
    monkeypatch.setattr(cli, "_preflight_current_purchase_snapshot", lambda _args: None)
    monkeypatch.setattr(
        cli, "_preflight_approved_purchase_input_bytes", lambda _args: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy",
        lambda _artifact: SimpleNamespace(
            canonical_ledger_path=paths["purchase_ledger"].resolve(),
            policy_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli, "verify_approved_purchase_input_bytes", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(cli, "_missing_core_budget_plan", lambda _artifact: object())
    monkeypatch.setattr(
        cli, "verify_recap_fetch_attempt_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "_authenticated_clearance_lineage_inputs",
        lambda *_args, **_kwargs: (clearance_kwargs, ()),
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", ObservedJournal)

    output_root = tmp_path / "output"
    command = [
        "acquisition",
        "resolve-post-recovery-documents",
        *[
            value
            for name, path in paths.items()
            for value in (f"--{name.replace('_', '-')}", str(path))
        ],
        "--output-root",
        str(output_root),
        "--execute",
        "--collect-all",
    ]

    assert cli.main(command) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["issue_count"] >= 1
    assert payload["issues"][0]["status"] in {"FAILED", "NOT_EVALUATED"}
    assert ObservedJournal.clear_calls == 0
    assert not (output_root / "resolved-post-recovery-documents.jsonl").exists()
    assert not (output_root / "run-cards/resolve-post-recovery-documents.json").exists()


def test_url_free_recovered_marker_model_clearance_reaches_source_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close recovery, AI clearance, resolution, and descriptor semantics."""

    inputs = _inputs()
    data = b"medical record cited only as a public allegation"
    content_sha256 = hashlib.sha256(data).hexdigest()
    operation = inputs["purchase_operation_records"][0]
    material = cast(dict[str, object], operation["material_evidence"])
    material["content_sha256"] = content_sha256
    material["byte_count"] = len(data)
    download = inputs["download_records"][0]
    download.update(
        {
            "local_path": "case-1/123.pdf",
            "sha256": content_sha256,
            "byte_count": len(data),
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
            "fresh_recap_detail_sha256": material["provider_detail_sha256"],
        }
    )
    download.pop("source_url", None)
    restrictions = inputs["restriction_records"]
    requests = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": "case-1",
            "source_document_id": "123",
            "sha256": content_sha256,
            "byte_count": len(data),
            "free_or_purchased": "purchased",
            "restriction_status": "public",
            "restriction_evidence": restrictions[0]["restriction_evidence"],
            "required_human_decision": "cleared_or_quarantined",
        }
    ]
    relevance = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "123",
                    "source_url_or_reference": "recap-document:123",
                    "model_visible": False,
                    "contains_target_outcome": True,
                }
            ],
        }
    ]
    document_root = tmp_path / "documents"
    document_path = document_root / "case-1/123.pdf"
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(data)
    lineage = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": hashlib.sha256(
            _jsonl_bytes([download])
        ).hexdigest(),
        "recovery_restriction_evidence_sha256": hashlib.sha256(
            _jsonl_bytes(restrictions)
        ).hexdigest(),
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": _hash(operation),
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": material["provider_detail_sha256"],
    }
    recovery_capability = issue_recovered_public_capability(monkeypatch, [lineage])
    scan = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=("medical",),
    )
    plan = build_provenance_clearance_plan_v3(
        requests,
        [download],
        restrictions,
        relevance,
        document_root=document_root,
        review_requests_bytes=_jsonl_bytes(requests),
        download_manifest_bytes=_jsonl_bytes([download]),
        restriction_evidence_bytes=_jsonl_bytes(restrictions),
        case_relevance_bytes=_jsonl_bytes(relevance),
        document_scanner=lambda _: scan,
        verified_recovery_capability=recovery_capability,
    )
    [planned] = cast(list[dict[str, object]], plan["documents"])
    assert planned["route"] == "exception_review"
    assert planned["source_url"] is None
    assert planned["recovered_public_lineage"] == lineage
    routing_sha256 = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()
    monkeypatch.setattr(
        "legalforecast.ingestion.disclosure_model_review_authority.public_disclosure_model_review_record",
        lambda _capability: {
            "routing_plan_sha256": routing_sha256,
            "reviewer_registry_key": "google:gemini-3.5-flash",
            "decision_count": 1,
            "decisions": [
                {
                    "schema_version": DECISION_SCHEMA_VERSION,
                    "candidate_id": "case-1",
                    "source_document_id": "123",
                    "document_sha256": content_sha256,
                    "prompt_sha256": "8" * 64,
                    "batch_prompt_sha256": "9" * 64,
                    "response_sha256": "a" * 64,
                    "batch_response_sha256": "b" * 64,
                    "reviewer_registry_entry_sha256": "c" * 64,
                    "status": "cleared",
                }
            ],
        },
    )
    [clearance_record] = build_authenticated_model_provenance_clearance_records_v3(
        plan,
        model_review_capability=object(),
        routing_plan_sha256=routing_sha256,
    )
    clearance = clearance_record.to_record()
    require_clearance_policy(
        clearance, key=("case-1", "123"), label="resolved document"
    )
    assert clearance["clearance_basis"] == "authenticated_model_exception_review"
    assert clearance["recovered_public_lineage"] == lineage

    clearance_bytes = _jsonl_bytes([clearance])
    inputs.update(
        {
            "download_manifest_artifact_bytes": _jsonl_bytes([download]),
            "clearance_records": [clearance],
            "clearance_artifact_bytes": clearance_bytes,
            "restriction_artifact_bytes": _jsonl_bytes(restrictions),
        }
    )
    resolved = build_recovered(
        **inputs,
        verified_recovery_capability=recovery_capability,
    )
    require_recovered(
        selection_records=inputs["selection_records"],
        download_records=[download],
        clearance_records=[clearance],
        resolved_records=resolved,
        **_external_kwargs(inputs),
        verified_recovery_capability=recovery_capability,
    )
    assert resolved[0]["recovered_public_lineage"] == lineage

    recovery_card = {
        "schema_version": "legalforecast.recap_fetch_quarantine_recovery_run_card.v2",
        "stage": "recover-recap-fetch-quarantine",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "authority_mode": "initial_projection",
        "input_paths": [
            str(tmp_path / name)
            for name in (
                "selection.jsonl",
                "case-relevance.jsonl",
                "projection-card.json",
                "purchase-policy.json",
                "cohort-policy.json",
                "budget.json",
                "purchase-ledger.sqlite3",
                "attempt-policy.json",
            )
        ],
        "source_commitments": {
            name: {"path": str(tmp_path / name), "sha256": "sha256:" + "d" * 64}
            for name in (
                "selection",
                "case_relevance",
                "target_projection_run_card",
                "purchase_policy",
                "cohort_policy",
                "budget_plan",
                "attempt_policy",
            )
        },
    }
    coordinates = derive_recovery_source_coordinates(recovery_card)
    descriptor = build_recovery_source_descriptor(
        coordinates=coordinates,
        ordinal=0,
        recovery_root=tmp_path / "recovery",
        purchased_clearance_path=tmp_path / "clearance.jsonl",
        purchased_clearance_run_card_path=tmp_path / "clearance-card.json",
        resolved_post_recovery_documents_path=tmp_path / "resolved.jsonl",
        replacement_controlled_private_root=None,
    )
    assert descriptor["kind"] == "initial_v2"
    assert descriptor["ordinal"] == 0
    assert descriptor["resolved_post_recovery_documents"] == str(
        (tmp_path / "resolved.jsonl").absolute()
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


def test_disclosure_authority_substitution_fails_closed() -> None:
    inputs = _inputs()
    substituted = replace(inputs["disclosure_authority"], authority_sha256="c" * 64)

    with pytest.raises(ResolvedPostRecoveryError, match="authority"):
        build_resolved_post_recovery_documents(
            **{**inputs, "disclosure_authority": substituted}
        )


def test_rehashed_cohort_policy_substitution_fails_closed() -> None:
    inputs = _inputs()
    substituted_bytes = _object_bytes(
        {"schema_version": "test", "policy_sha256": "c" * 64}
    )
    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["source_commitments"]["cohort_policy"]["sha256"] = hashlib.sha256(
        substituted_bytes
    ).hexdigest()

    with pytest.raises(ResolvedPostRecoveryError, match="cohort policy"):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "cohort_policy_artifact_bytes": substituted_bytes,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("disclosure_authority_sha256", "sha256:" + "c" * 64),
        ("cycle_id", "other-cycle"),
        ("cohort_policy_sha256", "sha256:" + "c" * 64),
        ("eligibility_anchor", "2026-07-01"),
        ("ssh_public_key_fingerprint", "SHA256:substituted"),
    ],
)
def test_expanded_run_card_review_authority_tamper_fails_closed(
    field: str, value: str
) -> None:
    inputs = _inputs()
    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["review_authority"][field] = value

    with pytest.raises(ResolvedPostRecoveryError, match="review authority"):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


def test_rehashed_clearance_status_tamper_fails() -> None:
    """A mutable run-card hash cannot override the signed review decision."""

    inputs = _inputs()
    tampered = deepcopy(inputs["clearance_records"])
    tampered[0]["status"] = "quarantined"
    clearance_bytes = _jsonl_bytes(tampered)
    run_card = deepcopy(inputs["clearance_run_card"])
    run_card["output_commitments"]["disclosure_clearance"]["sha256"] = hashlib.sha256(
        clearance_bytes
    ).hexdigest()
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="differs from authenticated review projection",
    ):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "clearance_records": tampered,
                "clearance_artifact_bytes": clearance_bytes,
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

    with pytest.raises(
        ResolvedPostRecoveryError,
        match=r"signed review input lineage mismatch|fresh-detail public proof",
    ):
        build_resolved_post_recovery_documents(
            **{
                **inputs,
                "restriction_records": restrictions,
                "restriction_artifact_bytes": restriction_bytes,
                "clearance_run_card": run_card,
                "clearance_run_card_bytes": _object_bytes(run_card),
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("is_sealed", 0),
        ("is_sealed", 1),
        ("is_sealed", "false"),
        ("is_private", 0),
        ("is_private", 1),
        ("is_private", "false"),
    ),
)
def test_fresh_public_restriction_rejects_non_boolean_markers(
    field: str, value: object
) -> None:
    inputs = _inputs()
    restriction = deepcopy(inputs["restriction_records"][0])
    restriction[field] = value

    with pytest.raises(ResolvedPostRecoveryError, match="fresh-detail public proof"):
        resolved_module._fresh_public_restriction_record(  # pyright: ignore[reportPrivateUsage]
            [restriction],
            key=("case-1", "123"),
            operation=inputs["purchase_operation_records"][0],
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
        expected_purchase_policy_sha256="1" * 64,
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
        expected_purchase_policy_sha256="1" * 64,
    )
    write_resolved_post_recovery_documents(artifact, records)

    changed = deepcopy(records[0])
    changed["broker_receipt_state"] = "confirmed"
    changed["record_sha256"] = _hash(
        {name: value for name, value in changed.items() if name != "record_sha256"}
    )
    with pytest.raises(ResolvedPostRecoveryError, match="overwrite"):
        write_resolved_post_recovery_documents(artifact, [changed])


def test_reconstruct_pre_resolution_snapshot_reverses_only_clearance_fields() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    preclear = deepcopy(inputs["purchase_operation_records"][0])
    cleared = deepcopy(preclear)
    cleared["material_state"] = "cleared_public"
    cleared["resolved_document_sha256"] = records[0]["record_sha256"]
    cleared["material_evidence"]["clearance_record_sha256"] = records[0][
        "clearance_record_sha256"
    ]
    policy = SimpleNamespace(
        cycle_id="cycle-1",
        cohort_policy_sha256="2" * 64,
        policy_sha256="1" * 64,
    )
    before_state = canonical_purchase_state_sha256(
        cast(Any, policy), committed_amount_usd="3.05", operations=[preclear]
    )
    after_state = canonical_purchase_state_sha256(
        cast(Any, policy), committed_amount_usd="3.05", operations=[cleared]
    )

    reconstructed = resolved_module.reconstruct_pre_resolution_purchase_snapshot(
        current_snapshot=CaseDevPurchaseSnapshot(
            operations=(cleared,),
            committed_amount_usd="3.05",
            purchase_state_sha256=after_state,
        ),
        resolved_records=records,
        policy=cast(Any, policy),
        expected_purchase_state_before_sha256=before_state,
    )

    assert reconstructed.operations == (preclear,)
    assert reconstructed.committed_amount_usd == "3.05"
    assert reconstructed.purchase_state_sha256 == before_state


@pytest.mark.parametrize(
    "mutation",
    ["billing", "resolved_digest", "clearance_digest", "before_state"],
)
def test_reconstruct_pre_resolution_snapshot_rejects_unauthorized_drift(
    mutation: str,
) -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    preclear = deepcopy(inputs["purchase_operation_records"][0])
    cleared = deepcopy(preclear)
    cleared["material_state"] = "cleared_public"
    cleared["resolved_document_sha256"] = records[0]["record_sha256"]
    cleared["material_evidence"]["clearance_record_sha256"] = records[0][
        "clearance_record_sha256"
    ]
    policy = SimpleNamespace(
        cycle_id="cycle-1",
        cohort_policy_sha256="2" * 64,
        policy_sha256="1" * 64,
    )
    before_state = canonical_purchase_state_sha256(
        cast(Any, policy), committed_amount_usd="3.05", operations=[preclear]
    )
    if mutation == "billing":
        cleared["reservation_usd"] = "0.01"
    elif mutation == "resolved_digest":
        cleared["resolved_document_sha256"] = "0" * 64
    elif mutation == "clearance_digest":
        cleared["material_evidence"]["clearance_record_sha256"] = "0" * 64
    else:
        before_state = "0" * 64

    with pytest.raises(
        ResolvedPostRecoveryError,
        match=r"clearance binding|operation commitment|prior state",
    ):
        resolved_module.reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=CaseDevPurchaseSnapshot(
                operations=(cleared,),
                committed_amount_usd="3.05",
                purchase_state_sha256="current-state",
            ),
            resolved_records=records,
            policy=cast(Any, policy),
            expected_purchase_state_before_sha256=before_state,
        )


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


def test_parse_origin_requires_lineage_after_selection_normalizes() -> None:
    inputs = _inputs()
    records = build_resolved_post_recovery_documents(**inputs)
    normalized_selection = deepcopy(inputs["selection_records"])
    normalized_document = normalized_selection[0]["documents"][0]
    normalized_document.update(
        {
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
        }
    )
    request = {
        "candidate_id": "case-1",
        "source_document_id": "123",
        "recovery_origin": "unknown_status_attempt",
        "expected_sha256": records[0]["content_sha256"],
        "expected_byte_count": records[0]["byte_count"],
        "resolved_post_recovery_sha256": records[0]["record_sha256"],
    }

    with pytest.raises(ResolvedPostRecoveryError, match="parse coverage mismatch"):
        require_resolved_post_recovery_parse_requests(
            selection_records=normalized_selection,
            request_records=[request],
            resolved_records=[],
        )

    require_resolved_post_recovery_parse_requests(
        selection_records=normalized_selection,
        request_records=[request],
        resolved_records=records,
    )

    mismatched = deepcopy(request)
    mismatched["resolved_post_recovery_sha256"] = "0" * 64
    with pytest.raises(ResolvedPostRecoveryError, match="does not bind"):
        require_resolved_post_recovery_parse_requests(
            selection_records=normalized_selection,
            request_records=[mismatched],
            resolved_records=records,
        )


def test_resolve_post_recovery_cli_help_names_all_lineage_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["acquisition", "resolve-post-recovery-documents", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--selection",
        "--purchase-policy",
        "--cohort-policy",
        "--budget-plan",
        "--purchase-ledger",
        "--replacement-purchase-authority",
        "--replacement-controlled-private-root",
        "--attempt-policy",
        "--download-manifest",
        "--disclosure-clearance",
        "--clearance-run-card",
        "--reviews",
        "--review-receipt",
        "--restriction-evidence",
        "--terminal-disposition-selection",
        "--terminal-disposition-snapshot-manifest",
        "--terminal-purchase-result",
        "--terminal-purchase-run-card",
        "--resolved-output",
    ):
        assert flag in help_text


@pytest.mark.parametrize(
    ("terminal_record_count", "bundle_present", "accepted"),
    ((0, False, True), (0, True, False), (1, False, False), (1, True, True)),
)
def test_terminal_disposition_bundle_exactly_tracks_terminal_partition(
    tmp_path: Path,
    terminal_record_count: int,
    bundle_present: bool,
    accepted: bool,
) -> None:
    source = tmp_path / "terminal-source.json"
    bundle: tuple[Path, Path, Path, Path] | tuple[()] = (
        (source, source, source, source) if bundle_present else ()
    )

    if accepted:
        cli._require_terminal_disposition_bundle(
            terminal_record_count=terminal_record_count,
            terminal_disposition_paths=bundle,
        )
        return
    with pytest.raises(
        cli.CommandError,
        match="must exactly match a nonempty terminal-unavailable recovery partition",
    ):
        cli._require_terminal_disposition_bundle(
            terminal_record_count=terminal_record_count,
            terminal_disposition_paths=bundle,
        )


def test_authenticated_snapshot_collision_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shared-authenticated-source.json"
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="authenticated source snapshot collision",
    ):
        cli._merge_authenticated_source_snapshots(
            {source: b'{"source":"recovery"}\n'},
            {source: b'{"source":"terminal"}\n'},
        )


def test_authenticated_source_drift_precedes_output_and_journal_mutation(
    tmp_path: Path,
) -> None:
    terminal_source = tmp_path / "authenticated-recovery-source.json"
    verified_bytes = b'{"status":"verified"}\n'
    terminal_source.write_bytes(verified_bytes)
    verifier_snapshots = {terminal_source: verified_bytes}
    terminal_source.write_bytes(b'{"status":"rebound"}\n')
    resolved_path = tmp_path / "resolved-post-recovery-documents.jsonl"
    cleared_document_ids: list[str] = []

    class RecordingJournal:
        def clear_unknown_material(
            self,
            source_document_id: str,
            *,
            resolved_record: Mapping[str, Any],
        ) -> None:
            del resolved_record
            cleared_document_ids.append(source_document_id)

    with pytest.raises(
        cli.CommandError,
        match="resolved post-recovery authenticated source changed during execution",
    ):
        cli._publish_resolved_post_recovery_documents(
            resolved_path=resolved_path,
            resolved_records=(
                {
                    "candidate_id": "case-1",
                    "source_document_id": "document-1",
                },
            ),
            purchase_journal=cast(CaseDevPurchaseJournal, RecordingJournal()),
            authenticated_source_snapshots=verifier_snapshots,
        )

    assert not resolved_path.exists()
    assert cleared_document_ids == []
    assert not (tmp_path / "run-cards/resolve-post-recovery-documents.json").exists()


def test_collect_all_build_validation_reports_independent_failures() -> None:
    inputs = _collect_all_inputs()
    inputs["clearance_run_card"]["review_authority"]["reviewer_id"] = "reviewer:other"
    inputs["clearance_run_card_bytes"] = _object_bytes(inputs["clearance_run_card"])
    inputs["attempt_policy_artifact"]["policy"]["allowed_documents"][0][
        "selection_document_sha256"
    ] = "0" * 64
    inputs["attempt_policy_artifact"]["policy_sha256"] = _hash(
        inputs["attempt_policy_artifact"]["policy"]
    )
    for record in inputs["purchase_operation_records"]:
        record["attempt_policy_sha256"] = inputs["attempt_policy_artifact"][
            "policy_sha256"
        ]
    for record in inputs["download_records"]:
        record["attempt_policy_sha256"] = inputs["attempt_policy_artifact"][
            "policy_sha256"
        ]
    inputs["download_records"][1]["byte_count"] = 101
    inputs["clearance_records"][2]["status"] = "quarantined"
    inputs["restriction_records"][3]["restriction_evidence"] = ["wrong"]

    result = resolved_module.collect_resolved_post_recovery_build_issues(**inputs)

    failed = [
        (issue.artifact, issue.code)
        for issue in result.issues
        if issue.status == "FAILED"
    ]
    assert failed == [
        ("case-1/101", "ATTEMPT_DOCUMENT_BINDING"),
        ("case-2/102", "DOWNLOAD_VALIDATION"),
        ("case-3/103", "CLEARANCE_VALIDATION"),
        ("case-4/104", "RESTRICTION_VALIDATION"),
        ("global", "CLEARANCE_LINEAGE_VALIDATION"),
    ]
    blocked = {
        (issue.artifact, issue.code): issue.blocked_by
        for issue in result.issues
        if issue.status == "NOT_EVALUATED"
    }
    assert blocked[("case-1/101", "PURCHASE_OPERATION_VALIDATION")] == (
        "ATTEMPT_DOCUMENT_BINDING",
    )
    assert blocked[("case-1/101", "DOWNLOAD_VALIDATION")] == (
        "PURCHASE_OPERATION_VALIDATION",
    )
    assert blocked[("case-2/102", "CLEARANCE_VALIDATION")] == ("DOWNLOAD_VALIDATION",)


def test_collect_all_build_validation_is_deterministic_across_input_order() -> None:
    baseline = resolved_module.collect_resolved_post_recovery_build_issues(
        **_collect_all_inputs()
    )
    inputs = _collect_all_inputs()
    inputs["selection_records"] = list(reversed(inputs["selection_records"]))
    inputs["purchase_operation_records"] = list(
        reversed(inputs["purchase_operation_records"])
    )
    inputs["download_records"] = list(reversed(inputs["download_records"]))
    reordered = resolved_module.collect_resolved_post_recovery_build_issues(**inputs)

    assert reordered.to_record() == baseline.to_record()


def test_collect_all_build_validation_redacts_sensitive_bytes() -> None:
    inputs = _inputs()
    secret_marker = "TOP_SECRET_REVIEW_RECEIPT_PAYLOAD"
    inputs["review_receipt_bytes"] = f'{{"broken": "{secret_marker}"'.encode()

    result = resolved_module.collect_resolved_post_recovery_build_issues(**inputs)
    rendered = json.dumps(result.to_record(), sort_keys=True)

    assert result.ok is False
    assert secret_marker not in rendered
    assert "review receipt is not valid JSON" in rendered


def test_collect_all_validation_preserves_valid_build_bytes(tmp_path: Path) -> None:
    inputs = _inputs()
    expected = build_resolved_post_recovery_documents(**inputs)
    expected_path = tmp_path / "expected.jsonl"
    write_resolved_post_recovery_documents(expected_path, expected)

    validation = resolved_module.collect_resolved_post_recovery_build_issues(**inputs)
    actual = build_resolved_post_recovery_documents(**inputs)
    actual_path = tmp_path / "actual.jsonl"
    write_resolved_post_recovery_documents(actual_path, actual)

    assert validation.ok is True
    assert actual == expected
    assert actual_path.read_bytes() == expected_path.read_bytes()


def test_recap_fetch_quarantine_recovery_help_names_controlled_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["acquisition", "recover-recap-fetch-quarantine", "--help"])

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
        "--restriction-evidence-output",
        "--terminal-unavailable-output",
        "--review-requests-output",
        "--document-output-root",
    ):
        assert flag in help_text


def test_resolve_post_recovery_cli_publishes_and_journals_authenticated_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
    signer = service_review_signer(
        reviewer_id="reviewer:john",
        controlled_store_uri="private-store://review/1",
    )
    signer["disclosure_authority"] = replace(
        signer["disclosure_authority"],
        identity=DisclosureReviewAuthorityIdentity(
            cycle_id="cycle-1",
            cohort_policy_sha256=str(cohort_artifact["policy_sha256"]),
            eligibility_anchor=date(2026, 6, 30),
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_main_disclosure_review_authority",
        lambda *_args, **_kwargs: signer["disclosure_authority"],
    )
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
        "case_relevance": tmp_path / "case-relevance.jsonl",
        "target_projection_run_card": tmp_path / "target-projection-run-card.json",
        "purchase_policy": tmp_path / "purchase-policy.json",
        "cohort_policy": tmp_path / "cohort-policy.json",
        "budget_plan": tmp_path / "budget-plan.json",
        "attempt_policy": tmp_path / "attempt-policy.json",
        "download_manifest": tmp_path / "downloads.jsonl",
        "disclosure_clearance": tmp_path / "clearance.jsonl",
        "clearance_run_card": tmp_path / "clearance-run-card.json",
        "reviews": tmp_path / "reviews.jsonl",
        "review_receipt": tmp_path / "review-receipt.json",
        "review_requests": tmp_path / "review-requests.jsonl",
        "review_worksheet": tmp_path / "review-worksheet.json",
        "reviewer_policy": tmp_path / "reviewer-policy.json",
        "restriction_evidence": tmp_path / "restrictions.jsonl",
    }
    _write_records(paths["selection"], inputs["selection_records"])
    _write_records(
        paths["case_relevance"],
        [
            {
                "candidate_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "123",
                        "availability_status": "unavailable",
                        "requires_paid_recovery": True,
                        "is_available": False,
                        "model_visible": True,
                        "contains_target_outcome": False,
                    }
                ],
            }
        ],
    )
    _write_target_projection_authority(
        paths["target_projection_run_card"],
        selection=paths["selection"],
        case_relevance=paths["case_relevance"],
    )
    _write_object(paths["purchase_policy"], purchase_artifact)
    _write_object(paths["cohort_policy"], cohort_artifact)
    paths["reviewer_policy"].write_bytes(signer["reviewer_policy_bytes"])
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
        cli.main(
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
        == 0
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
    pdf_content = cli._fixture_pdf("Public motion memorandum").decode()
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
        "--case-relevance",
        str(paths["case_relevance"]),
        "--target-projection-run-card",
        str(paths["target_projection_run_card"]),
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
        "--restriction-evidence-output",
        str(paths["restriction_evidence"]),
        "--review-requests-output",
        str(paths["review_requests"]),
        "--document-output-root",
        str(quarantine_root),
        "--output-root",
        str(tmp_path / "recovery-output"),
        "--execute",
    ]
    dry_run_root = tmp_path / "recovery-dry-run"
    dry_run_command = list(recovery_command[:-1])
    dry_run_overrides = {
        "--manifest-output": dry_run_root / "downloads.jsonl",
        "--restriction-evidence-output": dry_run_root / "restrictions.jsonl",
        "--review-requests-output": dry_run_root / "review-requests.jsonl",
        "--document-output-root": dry_run_root / "documents",
        "--output-root": dry_run_root,
    }
    for flag, value in dry_run_overrides.items():
        dry_run_command[dry_run_command.index(flag) + 1] = str(value)
    assert cli.main(dry_run_command) == 0
    dry_run_card = json.loads(
        (dry_run_root / "run-cards/recover-recap-fetch-quarantine.json").read_text()
    )
    assert dry_run_card["dry_run"] is True
    assert dry_run_card["terminal_unavailable_document_count"] == 0
    assert (dry_run_root / "terminal-unavailable-operations.jsonl").read_bytes() == b""
    successor_budget = tmp_path / "successor-budget-plan.json"
    successor_budget_record = deepcopy(budget_artifact)
    successor_budget_record["max_missing_core_documents_per_case"] = 2
    _write_object(successor_budget, successor_budget_record)
    mismatched_root = tmp_path / "mismatched-successor-dry-run"
    mismatched_command = list(dry_run_command)
    mismatched_command[mismatched_command.index("--budget-plan") + 1] = str(
        successor_budget
    )
    for flag, relative in (
        ("--manifest-output", "downloads.jsonl"),
        ("--restriction-evidence-output", "restrictions.jsonl"),
        ("--review-requests-output", "review-requests.jsonl"),
        ("--document-output-root", "documents"),
        ("--output-root", "."),
    ):
        mismatched_command[mismatched_command.index(flag) + 1] = str(
            mismatched_root / relative
        )
    capsys.readouterr()
    assert cli.main(mismatched_command) == 2
    assert "attempt policy does not match its immutable source inputs" in (
        capsys.readouterr().err
    )
    mismatched_run_card = json.loads(
        (mismatched_root / "run-cards/recover-recap-fetch-quarantine.json").read_text()
    )
    assert mismatched_run_card["status"] == "failed"
    assert mismatched_run_card["paid_activity_executed"] is False
    assert mismatched_run_card["record_count"] == 0
    assert not (mismatched_root / "downloads.jsonl").exists()
    assert not (mismatched_root / "restrictions.jsonl").exists()
    assert not (mismatched_root / "review-requests.jsonl").exists()
    assert not (mismatched_root / "documents").exists()
    assert not (mismatched_root / "terminal-unavailable-operations.jsonl").exists()
    assert cli.main(recovery_command) == 0
    assert cli.main(recovery_command) == 0
    assert "courtlistener.com" not in paths["download_manifest"].read_text()
    assert "download_url" not in paths["download_manifest"].read_text()
    inputs["download_records"] = _read_records(paths["download_manifest"])
    assert inputs["download_records"][0]["free_or_purchased"] == "purchased"
    restrictions = _read_records(paths["restriction_evidence"])
    assert restrictions[0]["schema_version"] == (
        "legalforecast.post_recovery_restriction_evidence.v1"
    )
    assert "courtlistener.com" not in paths["restriction_evidence"].read_text()
    terminal_unavailable_path = (
        tmp_path / "recovery-output" / "terminal-unavailable-operations.jsonl"
    )
    assert terminal_unavailable_path.read_bytes() == b""
    recovery_run_card = json.loads(
        (
            tmp_path
            / "recovery-output"
            / "run-cards"
            / "recover-recap-fetch-quarantine.json"
        ).read_text()
    )
    assert recovery_run_card["schema_version"] == (
        "legalforecast.recap_fetch_quarantine_recovery_run_card.v2"
    )
    commitments = recovery_run_card["output_commitments"]
    assert commitments["quarantine_download_manifest"]["sha256"] == (
        "sha256:" + hashlib.sha256(paths["download_manifest"].read_bytes()).hexdigest()
    )
    assert commitments["fresh_restriction_evidence"]["sha256"] == (
        "sha256:"
        + hashlib.sha256(paths["restriction_evidence"].read_bytes()).hexdigest()
    )
    assert commitments["terminal_unavailable_operations"]["sha256"] == (
        "sha256:" + hashlib.sha256(terminal_unavailable_path.read_bytes()).hexdigest()
    )
    assert recovery_run_card["authorized_document_count"] == 1
    assert recovery_run_card["recovered_document_count"] == 1
    assert recovery_run_card["terminal_unavailable_document_count"] == 0
    assert commitments["disclosure_review_requests"]["sha256"] == (
        "sha256:" + hashlib.sha256(paths["review_requests"].read_bytes()).hexdigest()
    )
    assert commitments["document_tree"] == {
        "case-1/123.pdf": "sha256:"
        + hashlib.sha256((quarantine_root / "case-1/123.pdf").read_bytes()).hexdigest()
    }
    purchase_snapshot = read_case_dev_purchase_snapshot(
        ledger_path, policy=purchase_policy
    )
    verified_recovery = cli._verify_materializer_recovery(
        recovery_root=tmp_path / "recovery-output",
        selection_path=paths["selection"],
        selected_document_keys={("case-1", "123")},
        purchase_policy_path=paths["purchase_policy"],
        cohort_policy_path=paths["cohort_policy"],
        ledger_path=ledger_path,
        purchase_operations=purchase_snapshot.operations,
        purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
        purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
    )
    assert verified_recovery["manifest_path"] == paths["download_manifest"]
    assert verified_recovery["document_root"] == quarantine_root
    assert verified_recovery["terminal_unavailable_path"] == (terminal_unavailable_path)
    recovery_run_card_path = (
        tmp_path
        / "recovery-output"
        / "run-cards"
        / "recover-recap-fetch-quarantine.json"
    )
    recovery_run_card_bytes = recovery_run_card_path.read_bytes()
    legacy_card = json.loads(recovery_run_card_bytes)
    legacy_card["schema_version"] = "legalforecast.acquisition_run_card.v1"
    del legacy_card["output_commitments"]["terminal_unavailable_operations"]
    legacy_card["output_paths"].remove(str(terminal_unavailable_path))
    for field in (
        "authorized_document_count",
        "recovered_document_count",
        "terminal_unavailable_document_count",
    ):
        del legacy_card[field]
    _write_object(recovery_run_card_path, legacy_card)
    verified_legacy = cli._verify_materializer_recovery(
        recovery_root=tmp_path / "recovery-output",
        selection_path=paths["selection"],
        selected_document_keys={("case-1", "123")},
        purchase_policy_path=paths["purchase_policy"],
        cohort_policy_path=paths["cohort_policy"],
        ledger_path=ledger_path,
        purchase_operations=purchase_snapshot.operations,
        purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
        purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
    )
    assert verified_legacy["terminal_unavailable_path"] is None
    legacy_card["terminal_unavailable_document_count"] = 0
    _write_object(recovery_run_card_path, legacy_card)
    with pytest.raises(cli.CommandError, match="mixes terminal fields"):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    incomplete_v2 = json.loads(recovery_run_card_bytes)
    del incomplete_v2["terminal_unavailable_document_count"]
    _write_object(recovery_run_card_path, incomplete_v2)
    with pytest.raises(cli.CommandError, match="record count differs"):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    recovery_run_card_path.write_bytes(recovery_run_card_bytes)
    terminal_unavailable_path.write_text("{}\n")
    with pytest.raises(cli.CommandError, match="commitment changed"):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    terminal_unavailable_path.write_bytes(b"")
    purchased_relevance_path = (
        tmp_path / "recovery-output" / "purchased-case-relevance.jsonl"
    )
    partition_backups = {
        paths["download_manifest"]: paths["download_manifest"].read_bytes(),
        purchased_relevance_path: purchased_relevance_path.read_bytes(),
        paths["restriction_evidence"]: paths["restriction_evidence"].read_bytes(),
        paths["review_requests"]: paths["review_requests"].read_bytes(),
        terminal_unavailable_path: terminal_unavailable_path.read_bytes(),
    }
    forged_terminal = {
        "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
        "candidate_id": "case-1",
        "source_document_id": "123",
        "source_provider": "courtlistener.recap-fetch+pacer",
        "attempt_policy_sha256": attempt_artifact["policy_sha256"],
        "attempt_document_sha256": attempt_artifact["policy"]["allowed_documents"][0][
            "selection_document_sha256"
        ],
        "purchase_operation_key": operation_key,
        "ledger_status": "failed",
        "material_state": "not_recovered",
        "terminal_reason": "recap_fetch_status_6",
        "queue_status": 6,
        "reservation_usd": "3.05",
        "cap_counted": True,
        "recovery_provider_request_executed": False,
        "paid_redispatch_executed": False,
        "ledger_operation_sha256": "sha256:" + "0" * 64,
    }
    _write_records(terminal_unavailable_path, [forged_terminal])
    for path in (
        paths["download_manifest"],
        purchased_relevance_path,
        paths["restriction_evidence"],
        paths["review_requests"],
    ):
        path.write_bytes(b"")
    forged_card = json.loads(recovery_run_card_bytes)
    for name, path in (
        ("quarantine_download_manifest", paths["download_manifest"]),
        ("purchased_case_relevance", purchased_relevance_path),
        ("fresh_restriction_evidence", paths["restriction_evidence"]),
        ("terminal_unavailable_operations", terminal_unavailable_path),
        ("disclosure_review_requests", paths["review_requests"]),
    ):
        forged_card["output_commitments"][name]["sha256"] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    forged_card["record_count"] = 0
    forged_card["recovered_document_count"] = 0
    forged_card["terminal_unavailable_document_count"] = 1
    _write_object(recovery_run_card_path, forged_card)
    with pytest.raises(
        cli.CommandError,
        match="terminal unavailable operation conflicts with purchase state",
    ):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    recovery_run_card_path.write_bytes(recovery_run_card_bytes)
    for path, payload in partition_backups.items():
        path.write_bytes(payload)
    review_request_bytes = paths["review_requests"].read_bytes()
    paths["review_requests"].write_bytes(review_request_bytes + b"{}\n")
    with pytest.raises(cli.CommandError, match="commitment changed"):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    paths["review_requests"].write_bytes(review_request_bytes)
    quarantined_document = quarantine_root / "case-1/123.pdf"
    quarantined_bytes = quarantined_document.read_bytes()
    quarantined_document.unlink()
    with pytest.raises(cli.CommandError, match="document-tree commitment mismatch"):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=purchase_snapshot.operations,
            purchase_committed_amount_usd=purchase_snapshot.committed_amount_usd,
            purchase_state_sha256=purchase_snapshot.purchase_state_sha256,
        )
    quarantined_document.write_bytes(quarantined_bytes)
    content_sha256 = hashlib.sha256(pdf_content.encode()).hexdigest()
    download_row = _read_records(paths["download_manifest"])[0]
    [review_request] = _read_records(paths["review_requests"])
    assert review_request == {
        "schema_version": "legalforecast.disclosure_review_request.v1",
        "candidate_id": download_row["candidate_id"],
        "source_document_id": download_row["source_document_id"],
        "sha256": content_sha256,
        "byte_count": len(pdf_content.encode()),
        "free_or_purchased": "purchased",
        "restriction_status": "public",
        "restriction_evidence": restrictions[0]["restriction_evidence"],
        "required_human_decision": "cleared_or_quarantined",
    }
    review_prepare_root = tmp_path / "review-prepare"
    private_review_root = tmp_path / "private-review"
    assert (
        cli.main(
            [
                "acquisition",
                "prepare-disclosure-review",
                "--review-requests",
                str(paths["review_requests"]),
                "--download-manifest",
                str(paths["download_manifest"]),
                "--document-root",
                str(quarantine_root),
                "--restriction-evidence",
                str(paths["restriction_evidence"]),
                "--reviewer-policy",
                str(paths["reviewer_policy"]),
                "--cohort-policy",
                str(paths["cohort_policy"]),
                "--worksheet-output",
                str(paths["review_worksheet"]),
                "--controlled-private-store-root",
                str(private_review_root),
                "--output-root",
                str(review_prepare_root),
                "--execute",
            ]
        )
        == 0
    )
    worksheet = json.loads(paths["review_worksheet"].read_text())
    signed = signed_service_review_lineage(
        [
            {
                "candidate_id": "case-1",
                "source_document_id": "123",
                "sha256": content_sha256,
                "status": "cleared",
                "reviewer_id": "reviewer:john",
                "controlled_store_provenance": "private-store://review/1",
                "reviewed_at": "2026-07-15T00:00:00Z",
            }
        ],
        restriction_evidence_bytes=paths["restriction_evidence"].read_bytes(),
        download_manifest_bytes=paths["download_manifest"].read_bytes(),
        review_requests_bytes=paths["review_requests"].read_bytes(),
        worksheet=worksheet,
        signer=signer,
        authenticated_at="2026-07-15T00:00:00Z",
    )
    paths["reviews"].write_bytes(signed["reviews_bytes"])
    paths["review_receipt"].write_bytes(signed["review_receipt_bytes"])
    assert paths["reviewer_policy"].read_bytes() == signed["reviewer_policy_bytes"]
    cli_validate = cli.validate_review_receipt
    resolved_validate = resolved_module.validate_review_receipt
    monkeypatch.setattr(
        cli,
        "validate_review_receipt",
        lambda *positional, **keywords: cli_validate(
            *positional, **{**keywords, "allow_test_service_identity": True}
        ),
    )
    monkeypatch.setattr(
        resolved_module,
        "validate_review_receipt",
        lambda *positional, **keywords: resolved_validate(
            *positional, **{**keywords, "allow_test_service_identity": True}
        ),
    )
    clearance_root = tmp_path / "clearance-output"
    assert (
        cli.main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(paths["download_manifest"]),
                "--review-requests",
                str(paths["review_requests"]),
                "--document-root",
                str(quarantine_root),
                "--review-worksheet",
                str(paths["review_worksheet"]),
                "--reviews",
                str(paths["reviews"]),
                "--review-receipt",
                str(paths["review_receipt"]),
                "--reviewer-policy",
                str(paths["reviewer_policy"]),
                "--cohort-policy",
                str(paths["cohort_policy"]),
                "--restriction-evidence",
                str(paths["restriction_evidence"]),
                "--output-root",
                str(clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    paths["disclosure_clearance"] = clearance_root / "disclosure-clearance.jsonl"
    paths["clearance_run_card"] = clearance_root / "run-cards/clear-disclosures.json"
    assert _read_records(clearance_root / "disclosure-quarantine.jsonl") == []
    output_root = tmp_path / "output"
    assert (
        cli.main(
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
        cli.main(
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
            if name
            not in {
                "case_relevance",
                "target_projection_run_card",
                "review_requests",
                "review_worksheet",
                "reviewer_policy",
            }
            for value in (f"--{name.replace('_', '-')}", str(path))
        ],
        "--purchase-ledger",
        str(ledger_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]
    assert cli.main(command) == 0
    assert cli.main(command) == 0
    resolved = _read_records(output_root / "resolved-post-recovery-documents.jsonl")
    assert len(resolved) == 1
    with CaseDevPurchaseJournal(ledger_path, policy=purchase_policy) as journal:
        evidence = journal.operation_evidence("123")
        assert evidence is not None
        assert evidence["material_state"].value == "cleared_public"
        assert evidence["resolved_document_sha256"] == resolved[0]["record_sha256"]
        cli._verify_materializer_purchase_operations(
            journal.operation_records(),
            purchased_manifest=_read_records(paths["download_manifest"]),
        )
    resolved_snapshot = read_case_dev_purchase_snapshot(
        ledger_path, policy=purchase_policy
    )
    assert resolved_snapshot.purchase_state_sha256 != (
        purchase_snapshot.purchase_state_sha256
    )
    replayed_recovery = cli._verify_materializer_recovery(
        recovery_root=tmp_path / "recovery-output",
        selection_path=paths["selection"],
        selected_document_keys={("case-1", "123")},
        purchase_policy_path=paths["purchase_policy"],
        cohort_policy_path=paths["cohort_policy"],
        ledger_path=ledger_path,
        purchase_operations=resolved_snapshot.operations,
        purchase_committed_amount_usd=resolved_snapshot.committed_amount_usd,
        purchase_state_sha256=resolved_snapshot.purchase_state_sha256,
    )
    assert replayed_recovery["historical_purchase_state_sha256"] == (
        purchase_snapshot.purchase_state_sha256
    )
    unrelated_mutation = [dict(row) for row in resolved_snapshot.operations]
    unrelated_mutation[0]["error"] = "forged"
    with pytest.raises(
        cli.CommandError,
        match="outputs do not partition its attempt authority",
    ):
        cli._verify_materializer_recovery(
            recovery_root=tmp_path / "recovery-output",
            selection_path=paths["selection"],
            selected_document_keys={("case-1", "123")},
            purchase_policy_path=paths["purchase_policy"],
            cohort_policy_path=paths["cohort_policy"],
            ledger_path=ledger_path,
            purchase_operations=unrelated_mutation,
            purchase_committed_amount_usd=resolved_snapshot.committed_amount_usd,
            purchase_state_sha256=cli.canonical_purchase_state_sha256(
                purchase_policy,
                committed_amount_usd=resolved_snapshot.committed_amount_usd,
                operations=unrelated_mutation,
            ),
        )
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
    resolved_path = output_root / "resolved-post-recovery-documents.jsonl"
    runtime_projection = build_completed_projection_fixture(
        tmp_path / "authenticated-materialization-projection",
        monkeypatch=monkeypatch,
    )
    runtime_approval = build_approved_purchase_fixture(
        tmp_path / "authenticated-materialization-approval",
        target_cohort_root=runtime_projection.root,
    )
    materialization_card = tmp_path / "materialization-run-card.json"
    materialization_restrictions = tmp_path / "materialization-restrictions.jsonl"
    materialization_derivations = tmp_path / "materialization-derivations.jsonl"
    materialization_summary = tmp_path / "materialization-summary.json"
    _write_records(materialization_restrictions, [])
    _write_records(materialization_derivations, [])
    _write_object(materialization_summary, {})
    _write_object(
        materialization_card,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "materialize-cohort-documents",
            "status": "completed",
            "input_paths": [
                str(runtime_projection.root),
                str(runtime_projection.root / "target-cohort-projection.json"),
                str(runtime_projection.root / "missing-core-budget-plan.json"),
                str(runtime_projection.selection),
                str(runtime_projection.root),
                str(paths["disclosure_clearance"]),
                str(tmp_path / "recovery-output"),
                str(paths["disclosure_clearance"]),
                str(paths["clearance_run_card"]),
                str(runtime_approval.policy),
                str(runtime_approval.cohort_policy),
                str(runtime_approval.ledger),
            ],
            "output_paths": [
                str(paths["download_manifest"]),
                str(paths["disclosure_clearance"]),
                str(materialization_restrictions),
                str(materialization_derivations),
                str(materialization_summary),
                str(quarantine_root),
            ],
        },
    )

    def verify_recovery_materialization(
        **kwargs: object,
    ) -> cli._VerifiedMaterializedDownstreamLineage:
        """Keep this recovery test focused on live purchase-state invalidation.

        Canonical materializer replay is covered by the target-100 end-to-end
        test. This fixture still replays the actual purchase ledger and resolved
        records so the three downstream commands fail after a later failed
        broker receipt, which is the invariant under test here.
        """

        assert kwargs["run_card_path"] == materialization_card
        assert kwargs["manifest_path"] == paths["download_manifest"]
        assert kwargs["clearance_path"] == paths["disclosure_clearance"]
        assert kwargs["document_root"] == quarantine_root
        assert kwargs["selection_path"] == paths["selection"]
        snapshot = read_case_dev_purchase_snapshot(
            ledger_path,
            policy=purchase_policy,
        )
        require_resolved_post_recovery_operation_bindings(
            purchase_operation_records=snapshot.operations,
            resolved_records=_read_records(resolved_path),
            expected_purchase_policy_sha256=purchase_policy.policy_sha256,
        )
        return cli._VerifiedMaterializedDownstreamLineage(
            paths=(
                materialization_card,
                materialization_restrictions,
                materialization_derivations,
                resolved_path,
            ),
            artifact_bytes={},
            manifest_records=tuple(_read_records(paths["download_manifest"])),
            clearance_records=tuple(_read_records(paths["disclosure_clearance"])),
            selection_records=tuple(_read_records(paths["selection"])),
            resolved_records=tuple(_read_records(resolved_path)),
            document_tree=cli._materializer_tree_snapshot(quarantine_root),
        )

    monkeypatch.setattr(
        cli,
        "_require_consistent_materialization_markers",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        verify_recovery_materialization,
    )
    lineage_arguments = [
        "--selection",
        str(paths["selection"]),
        "--disclosure-clearance",
        str(paths["disclosure_clearance"]),
        "--resolved-post-recovery-documents",
        str(resolved_path),
        "--clearance-run-card",
        str(paths["clearance_run_card"]),
        "--reviews",
        str(paths["reviews"]),
        "--review-receipt",
        str(paths["review_receipt"]),
        "--restriction-evidence",
        str(paths["restriction_evidence"]),
        "--materialization-run-card",
        str(materialization_card),
        "--controlled-private-root",
        str(runtime_approval.controlled_private_root),
    ]
    downstream_root = tmp_path / "downstream"
    plan_parse_command = [
        "acquisition",
        "plan-parse-documents",
        *lineage_arguments,
        "--download-manifest",
        str(paths["download_manifest"]),
        "--document-root",
        str(quarantine_root),
        "--output-root",
        str(downstream_root),
        "--execute",
    ]
    assert cli.main(plan_parse_command) == 0
    normalized_selection = _read_records(paths["selection"])
    normalized_selection[0]["documents"][0].update(
        {
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
        }
    )
    _write_records(paths["selection"], normalized_selection)
    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "123.md").write_text("Public motion memorandum")
    parse_command = [
        "acquisition",
        "parse-documents",
        *lineage_arguments,
        "--requests",
        str(downstream_root / "parse-document-requests.jsonl"),
        "--fixture-markdown-dir",
        str(fixture_markdown),
        "--output-root",
        str(downstream_root),
        "--execute",
    ]
    assert cli.main(parse_command) == 0
    parser_path = downstream_root / "mistral-markdown-conversions.jsonl"
    packet_command = [
        "acquisition",
        "plan-packet-inputs",
        *lineage_arguments,
        "--download-manifest",
        str(paths["download_manifest"]),
        "--parser-manifest",
        str(parser_path),
        "--prediction-units",
        str(units_path),
        "--model-registry",
        str(registry_path),
        "--raw-html-dir",
        str(raw_html_dir),
        "--document-root",
        str(quarantine_root),
        "--output-root",
        str(downstream_root),
    ]
    assert cli.main(packet_command) == 0

    with CaseDevPurchaseJournal(ledger_path, policy=purchase_policy) as journal:
        failed = deepcopy(receipt)
        failed.update(
            {
                "state": "failed",
                "held_usd": "0.00",
                "provider_response_body_sha256": None,
                "provider_response_sha256": None,
                "updated_at": "2026-07-15T00:02:00.000Z",
                "delivered_at": None,
            }
        )
        journal.record_broker_receipt("123", failed)
    assert cli.main(plan_parse_command) == 2
    assert cli.main(parse_command) == 2
    assert cli.main(packet_command) == 2

    # Reproduce the canonical receipt-enriched terminal shape through the real
    # CLI and materializer verifier. Empty fixtures make any provider request
    # fail, so success proves terminal accounting performs no recovery I/O.
    _write_records(paths["selection"], inputs["selection_records"])
    with closing(sqlite3.connect(ledger_path)) as connection:
        connection.execute(
            "UPDATE purchase_operations SET status='failed', actual_usd=NULL, "
            "reconciliation_json=NULL, error=? WHERE source_document_id='123'",
            ("CourtListenerRecapFetchError: RECAP Fetch terminal queue status 6",),
        )
        connection.execute(
            "UPDATE purchase_material_state SET status='not_recovered', "
            "provider_detail_sha256=NULL, queue_response_sha256=NULL, "
            "download_url_sha256=NULL, content_sha256=NULL, byte_count=NULL, "
            "clearance_record_sha256=NULL, resolved_record_sha256=NULL "
            "WHERE source_document_id='123'"
        )
        connection.execute(
            "DELETE FROM unknown_public_material_recoveries "
            "WHERE source_document_id='123'"
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    terminal_root = tmp_path / "terminal-recovery-output"
    terminal_fixture = tmp_path / "terminal-empty-courtlistener.jsonl"
    terminal_fixture.write_bytes(b"")
    terminal_documents = tmp_path / "terminal-empty-documents.json"
    _write_object(terminal_documents, {})
    terminal_command = list(recovery_command)
    terminal_overrides = {
        "--courtlistener-fixture": terminal_fixture,
        "--fixture-documents": terminal_documents,
        "--manifest-output": terminal_root / "downloads.jsonl",
        "--restriction-evidence-output": terminal_root / "restrictions.jsonl",
        "--review-requests-output": terminal_root / "review-requests.jsonl",
        "--document-output-root": terminal_root / "documents",
        "--output-root": terminal_root,
    }
    for flag, value in terminal_overrides.items():
        terminal_command[terminal_command.index(flag) + 1] = str(value)
    assert cli.main(terminal_command) == 0
    terminal_path = terminal_root / "terminal-unavailable-operations.jsonl"
    [terminal_record] = _read_records(terminal_path)
    assert terminal_record["queue_status"] == 6
    assert terminal_record["recovery_provider_request_executed"] is False
    assert terminal_record["paid_redispatch_executed"] is False
    assert (terminal_root / "downloads.jsonl").read_bytes() == b""
    assert (terminal_root / "restrictions.jsonl").read_bytes() == b""
    terminal_card = json.loads(
        (terminal_root / "run-cards/recover-recap-fetch-quarantine.json").read_text()
    )
    assert terminal_card["authorized_document_count"] == 1
    assert terminal_card["recovered_document_count"] == 0
    assert terminal_card["terminal_unavailable_document_count"] == 1
    terminal_snapshot = read_case_dev_purchase_snapshot(
        ledger_path, policy=purchase_policy
    )
    verified_terminal = cli._verify_materializer_recovery(
        recovery_root=terminal_root,
        selection_path=paths["selection"],
        selected_document_keys={("case-1", "123")},
        purchase_policy_path=paths["purchase_policy"],
        cohort_policy_path=paths["cohort_policy"],
        ledger_path=ledger_path,
        purchase_operations=terminal_snapshot.operations,
        purchase_committed_amount_usd=terminal_snapshot.committed_amount_usd,
        purchase_state_sha256=terminal_snapshot.purchase_state_sha256,
    )
    assert verified_terminal["terminal_unavailable_path"] == terminal_path
    for field, value in (
        ("material_authority", "forged"),
        ("attempt_policy_sha256", "f" * 64),
        ("attempt_document_sha256", "e" * 64),
    ):
        forged_operations = [dict(row) for row in terminal_snapshot.operations]
        forged_operations[0][field] = value
        with pytest.raises(
            cli.CommandError,
            match="terminal unavailable operation conflicts with purchase state",
        ):
            cli._verify_materializer_recovery(
                recovery_root=terminal_root,
                selection_path=paths["selection"],
                selected_document_keys={("case-1", "123")},
                purchase_policy_path=paths["purchase_policy"],
                cohort_policy_path=paths["cohort_policy"],
                ledger_path=ledger_path,
                purchase_operations=forged_operations,
                purchase_committed_amount_usd=(terminal_snapshot.committed_amount_usd),
                purchase_state_sha256=cli.canonical_purchase_state_sha256(
                    purchase_policy,
                    committed_amount_usd=terminal_snapshot.committed_amount_usd,
                    operations=forged_operations,
                ),
            )


def test_materializer_accepts_exact_external_document_commitment() -> None:
    manifest = [
        {
            "candidate_id": "case-external",
            "source_document_id": "doc-external",
            "sha256": "a" * 64,
        }
    ]

    # An externally completed purchase is intentionally absent from the local
    # ledger.  The verifier-issued register commitment is the only authority
    # that may fill that exact ledger gap.
    cli._verify_materializer_purchase_operations(
        [],
        purchased_manifest=manifest,
        external_document_commitments={
            ("case-external", "doc-external"): "a" * 64,
        },
    )


def test_materializer_rejects_external_document_commitment_byte_mismatch() -> None:
    manifest = [
        {
            "candidate_id": "case-external",
            "source_document_id": "doc-external",
            "sha256": "a" * 64,
        }
    ]

    with pytest.raises(
        cli.CommandError, match="external billing register document bytes differ"
    ):
        cli._verify_materializer_purchase_operations(
            [],
            purchased_manifest=manifest,
            external_document_commitments={
                ("case-external", "doc-external"): "b" * 64,
            },
        )


@pytest.mark.parametrize("commitments", [None, {}])
def test_materializer_rejects_missing_external_register_authority(
    commitments: Mapping[tuple[str, str], str] | None,
) -> None:
    manifest = [
        {
            "candidate_id": "case-external",
            "source_document_id": "doc-external",
            "sha256": "a" * 64,
        }
    ]

    with pytest.raises(
        cli.CommandError, match="purchase ledger lacks recovered document"
    ):
        cli._verify_materializer_purchase_operations(
            [],
            purchased_manifest=manifest,
            external_document_commitments=commitments,
        )


def test_materializer_preserves_legacy_confirmed_ledger_validation() -> None:
    source_url = "https://provider.example/doc-external.pdf"
    manifest = [
        {
            "candidate_id": "case-ledger",
            "source_document_id": "doc-ledger",
            "source_url": source_url,
            "sha256": "c" * 64,
            "byte_count": 7,
        }
    ]
    operations = [
        {
            "candidate_id": "case-ledger",
            "source_document_id": "doc-ledger",
            "operation_key": "operation-ledger",
            "status": "confirmed",
            "response": {"download_url": source_url},
        }
    ]

    # A normal ledger-confirmed document continues to validate without an
    # external register commitment.
    cli._verify_materializer_purchase_operations(
        operations,
        purchased_manifest=manifest,
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
        "purchase_policy_sha256": "1" * 64,
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
        "local_path": "case-1/123.pdf",
        "status": "cleared",
        "automated_markers": [],
        "restriction_status": "public",
        "restriction_evidence": ["fresh_post_recovery_public_detail"],
        "sha256": "5" * 64,
        "byte_count": 100,
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://review/1",
        "reviewed_at": "2026-07-15T00:00:00Z",
        "free_or_purchased": "purchased",
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
            "restriction_evidence": ["fresh_post_recovery_public_detail"],
        }
    ]
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
    signed_lineage = signed_service_review_lineage(
        reviews,
        restriction_evidence_bytes=restriction_bytes,
        authenticated_at="2026-07-15T00:00:00Z",
    )
    reviews = signed_lineage["reviews"]
    reviews_bytes = signed_lineage["reviews_bytes"]
    review_receipt = signed_lineage["review_receipt"]
    review_receipt_bytes = signed_lineage["review_receipt_bytes"]
    disclosure_authority = signed_lineage["disclosure_authority"]
    cohort_policy_bytes = _object_bytes(
        {
            "schema_version": "test",
            "policy_sha256": disclosure_authority.identity.cohort_policy_sha256,
        }
    )
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
            "cohort_policy": {
                "sha256": hashlib.sha256(cohort_policy_bytes).hexdigest()
            },
            "download_manifest": {
                "sha256": hashlib.sha256(
                    signed_lineage["download_manifest_bytes"]
                ).hexdigest()
            },
            "review_requests": {
                "sha256": hashlib.sha256(
                    signed_lineage["review_requests_bytes"]
                ).hexdigest()
            },
            "review_worksheet": {
                "sha256": hashlib.sha256(
                    signed_lineage["review_worksheet_bytes"]
                ).hexdigest()
            },
            "reviews": {"sha256": hashlib.sha256(reviews_bytes).hexdigest()},
            "review_receipt": {
                "sha256": hashlib.sha256(review_receipt_bytes).hexdigest()
            },
            "reviewer_policy": {
                "sha256": hashlib.sha256(
                    signed_lineage["reviewer_policy_bytes"]
                ).hexdigest()
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
            "authentication_method": "controlled_store_service_ssh_signature",
            "authenticated_at": "2026-07-15T00:00:00Z",
            "review_artifact_sha256": (
                "sha256:" + hashlib.sha256(reviews_bytes).hexdigest()
            ),
            "reviewer_policy_sha256": (
                "sha256:" + signed_lineage["reviewer_policy_sha256"]
            ),
            "disclosure_authority_sha256": (
                "sha256:" + disclosure_authority.authority_sha256
            ),
            "cycle_id": disclosure_authority.identity.cycle_id,
            "cohort_policy_sha256": (
                "sha256:" + disclosure_authority.identity.cohort_policy_sha256
            ),
            "eligibility_anchor": (
                disclosure_authority.identity.eligibility_anchor.isoformat()
            ),
            "ssh_public_key_fingerprint": (
                disclosure_authority.ssh_public_key_fingerprint
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
        "review_requests_artifact_bytes": signed_lineage["review_requests_bytes"],
        "review_worksheet_artifact": signed_lineage["review_worksheet"],
        "review_worksheet_bytes": signed_lineage["review_worksheet_bytes"],
        "reviewer_policy_bytes": signed_lineage["reviewer_policy_bytes"],
        "disclosure_authority": disclosure_authority,
        "cohort_policy_artifact_bytes": cohort_policy_bytes,
        "download_manifest_artifact_bytes": signed_lineage["download_manifest_bytes"],
        "restriction_records": restrictions,
        "restriction_artifact_bytes": restriction_bytes,
        "allow_test_service_identity": True,
    }


def _collect_all_inputs() -> dict[str, Any]:
    selection_records: list[dict[str, object]] = []
    allowed_documents: list[dict[str, object]] = []
    purchase_operations: list[dict[str, object]] = []
    download_records: list[dict[str, object]] = []
    clearance_records: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    restriction_records: list[dict[str, object]] = []

    for index in range(1, 5):
        candidate_id = f"case-{index}"
        document_id = str(100 + index)
        operation_key = f"00000000-0000-4000-8000-{index:012d}"
        provider_detail_sha256 = f"{index}" * 64
        queue_response_sha256 = f"{index + 1}" * 64
        download_url_sha256 = f"{index + 2}" * 64
        content_sha256 = f"{index + 3}" * 64
        selection_document = {
            "source_document_id": document_id,
            "redaction_or_seal_status": "unknown",
            "is_sealed": None,
            "is_private": None,
            "is_available": False,
            "availability_status": "unavailable",
            "requires_paid_recovery": True,
        }
        selection_records.append(
            {
                "candidate_id": candidate_id,
                "selected": True,
                "exclusion_reasons": [],
                "documents": [selection_document],
            }
        )
        allowed_documents.append(
            {
                "case_id": candidate_id,
                "recap_document": document_id,
                "evidence_class": "unknown_status_quarantine",
                "selection_document_sha256": _hash(selection_document),
            }
        )
        receipt = {
            "version": "courtlistener-recap-fetch-receipt-v1",
            "state": "delivered_but_unreconciled",
            "operation_key": operation_key,
            "reservation_id": f"reservation-{index}",
            "cycle_id": "cycle-1",
            "case_id": candidate_id,
            "recap_document": document_id,
            "purchase_policy_sha256": "1" * 64,
            "client_code": recap_fetch_client_code(operation_key),
            "id": str(70 + index),
            "reservation_usd": "3.05",
            "held_usd": "3.05",
            "authoritative_fee_usd": None,
            "provider_response_body_sha256": f"{index + 4}" * 64,
            "provider_response_sha256": f"{index + 5}" * 64,
            "submitted_at": "2026-07-15T00:00:00.000Z",
            "updated_at": "2026-07-15T00:01:00.000Z",
            "delivered_at": "2026-07-15T00:01:00.000Z",
            "reconciled_at": None,
            "billing_evidence": None,
        }
        purchase_operations.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "queued",
                "operation_key": operation_key,
                "material_authority": "unknown_status_attempt",
                "material_state": "recovered_pending_clearance",
                "attempt_policy_sha256": _hash(
                    {
                        "authority": BOUNDED_FETCH_ATTEMPT_AUTHORITY,
                        "purchase_policy_sha256": "1" * 64,
                        "allowed_documents": allowed_documents,
                    }
                ),
                "attempt_document_sha256": _hash(selection_document),
                "resolved_document_sha256": None,
                "response": {
                    "broker_receipts": [{"sha256": _hash(receipt), "receipt": receipt}]
                },
                "material_evidence": {
                    "provider_detail_sha256": provider_detail_sha256,
                    "queue_response_sha256": queue_response_sha256,
                    "download_url_sha256": download_url_sha256,
                    "content_sha256": content_sha256,
                    "byte_count": 100,
                },
            }
        )
        download_records.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "recovery_origin": "unknown_status_attempt",
                "attempt_policy_sha256": "",
                "purchase_operation_key": operation_key,
                "local_path": f"{candidate_id}/{document_id}.pdf",
                "sha256": content_sha256,
                "byte_count": 100,
            }
        )
        clearance_records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "local_path": f"{candidate_id}/{document_id}.pdf",
                "status": "cleared",
                "automated_markers": [],
                "restriction_status": "public",
                "restriction_evidence": ["fresh_post_recovery_public_detail"],
                "sha256": content_sha256,
                "byte_count": 100,
                "reviewer_id": "reviewer:john",
                "controlled_store_provenance": "private-store://review/1",
                "reviewed_at": "2026-07-15T00:00:00Z",
                "free_or_purchased": "purchased",
            }
        )
        review_rows.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "sha256": content_sha256,
                "status": "cleared",
                "reviewer_id": "reviewer:john",
                "controlled_store_provenance": "private-store://review/1",
                "reviewed_at": "2026-07-15T00:00:00Z",
                "restriction_evidence": ["fresh_post_recovery_public_detail"],
            }
        )
        restriction_records.append(
            {
                "schema_version": "legalforecast.post_recovery_restriction_evidence.v1",
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "source_provider": "courtlistener_recap_fetch_fresh_detail",
                "fresh_recap_detail_sha256": provider_detail_sha256,
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
        )

    attempt_policy = {
        "authority": BOUNDED_FETCH_ATTEMPT_AUTHORITY,
        "purchase_policy_sha256": "1" * 64,
        "allowed_documents": allowed_documents,
    }
    attempt_artifact = {
        "schema_version": RECAP_FETCH_ATTEMPT_POLICY_VERSION,
        "policy": attempt_policy,
        "policy_sha256": _hash(attempt_policy),
    }
    for operation in purchase_operations:
        operation["attempt_policy_sha256"] = attempt_artifact["policy_sha256"]
    for download in download_records:
        download["attempt_policy_sha256"] = attempt_artifact["policy_sha256"]

    restriction_bytes = _jsonl_bytes(restriction_records)
    signed_lineage = signed_service_review_lineage(
        review_rows,
        restriction_evidence_bytes=restriction_bytes,
        authenticated_at="2026-07-15T00:00:00Z",
    )
    disclosure_authority = signed_lineage["disclosure_authority"]
    cohort_policy_bytes = _object_bytes(
        {
            "schema_version": "test",
            "policy_sha256": disclosure_authority.identity.cohort_policy_sha256,
        }
    )
    clearance_bytes = _jsonl_bytes(clearance_records)
    clearance_run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "cohort_policy": {
                "sha256": hashlib.sha256(cohort_policy_bytes).hexdigest()
            },
            "download_manifest": {
                "sha256": hashlib.sha256(
                    signed_lineage["download_manifest_bytes"]
                ).hexdigest()
            },
            "review_requests": {
                "sha256": hashlib.sha256(
                    signed_lineage["review_requests_bytes"]
                ).hexdigest()
            },
            "review_worksheet": {
                "sha256": hashlib.sha256(
                    signed_lineage["review_worksheet_bytes"]
                ).hexdigest()
            },
            "reviews": {
                "sha256": hashlib.sha256(signed_lineage["reviews_bytes"]).hexdigest()
            },
            "review_receipt": {
                "sha256": hashlib.sha256(
                    signed_lineage["review_receipt_bytes"]
                ).hexdigest()
            },
            "reviewer_policy": {
                "sha256": hashlib.sha256(
                    signed_lineage["reviewer_policy_bytes"]
                ).hexdigest()
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
            "authentication_method": "controlled_store_service_ssh_signature",
            "authenticated_at": "2026-07-15T00:00:00Z",
            "review_artifact_sha256": (
                "sha256:" + hashlib.sha256(signed_lineage["reviews_bytes"]).hexdigest()
            ),
            "reviewer_policy_sha256": (
                "sha256:" + signed_lineage["reviewer_policy_sha256"]
            ),
            "disclosure_authority_sha256": (
                "sha256:" + disclosure_authority.authority_sha256
            ),
            "cycle_id": disclosure_authority.identity.cycle_id,
            "cohort_policy_sha256": (
                "sha256:" + disclosure_authority.identity.cohort_policy_sha256
            ),
            "eligibility_anchor": (
                disclosure_authority.identity.eligibility_anchor.isoformat()
            ),
            "ssh_public_key_fingerprint": (
                disclosure_authority.ssh_public_key_fingerprint
            ),
        },
    }
    return {
        "selection_records": selection_records,
        "purchase_operation_records": purchase_operations,
        "download_records": download_records,
        "clearance_records": clearance_records,
        "attempt_policy_artifact": attempt_artifact,
        "clearance_artifact_bytes": clearance_bytes,
        "clearance_run_card": clearance_run_card,
        "clearance_run_card_bytes": _object_bytes(clearance_run_card),
        "reviews_artifact_bytes": signed_lineage["reviews_bytes"],
        "review_receipt_artifact": signed_lineage["review_receipt"],
        "review_receipt_bytes": signed_lineage["review_receipt_bytes"],
        "review_requests_artifact_bytes": signed_lineage["review_requests_bytes"],
        "review_worksheet_artifact": signed_lineage["review_worksheet"],
        "review_worksheet_bytes": signed_lineage["review_worksheet_bytes"],
        "reviewer_policy_bytes": signed_lineage["reviewer_policy_bytes"],
        "disclosure_authority": disclosure_authority,
        "cohort_policy_artifact_bytes": cohort_policy_bytes,
        "download_manifest_artifact_bytes": signed_lineage["download_manifest_bytes"],
        "restriction_records": restriction_records,
        "restriction_artifact_bytes": restriction_bytes,
        "allow_test_service_identity": True,
    }


def _external_kwargs(inputs: dict[str, Any]) -> dict[str, Any]:
    names = (
        "clearance_artifact_bytes",
        "clearance_run_card",
        "clearance_run_card_bytes",
        "reviews_artifact_bytes",
        "review_receipt_artifact",
        "review_receipt_bytes",
        "review_requests_artifact_bytes",
        "review_worksheet_artifact",
        "review_worksheet_bytes",
        "reviewer_policy_bytes",
        "disclosure_authority",
        "cohort_policy_artifact_bytes",
        "download_manifest_artifact_bytes",
        "restriction_records",
        "restriction_artifact_bytes",
        "allow_test_service_identity",
    )
    return {name: inputs[name] for name in names}


def _retarget_review_inputs(
    inputs: dict[str, Any],
    *,
    content_sha256: str,
) -> None:
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
    inputs.update(
        {
            "reviews_artifact_bytes": review_bytes,
            "review_receipt_bytes": receipt_bytes,
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


def _write_target_projection_authority(
    path: Path, *, selection: Path, case_relevance: Path
) -> None:
    _write_object(
        path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "project-target-cohort",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "output_paths": [str(selection), str(case_relevance)],
            "output_commitments": {
                str(selection): "sha256:"
                + hashlib.sha256(selection.read_bytes()).hexdigest(),
                str(case_relevance): "sha256:"
                + hashlib.sha256(case_relevance.read_bytes()).hexdigest(),
            },
        },
    )


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


def _corrected_public_recovery(operation: Mapping[str, Any]) -> dict[str, object]:
    material = operation["material_evidence"]
    legacy_digest = "a" * 64
    corrected_digest = material["download_url_sha256"]
    base = {
        "candidate_id": operation["candidate_id"],
        "source_document_id": operation["source_document_id"],
        "operation_key": operation["operation_key"],
        "purchase_policy_sha256": "1" * 64,
        "attempt_policy_sha256": operation["attempt_policy_sha256"],
        "attempt_document_sha256": operation["attempt_document_sha256"],
        "provider_detail_sha256": material["provider_detail_sha256"],
        "download_url_sha256": legacy_digest,
        "billing_status": "unknown",
        "reservation_retained": True,
        "no_paid_redispatch": True,
    }
    legacy = {
        "schema_version": "legalforecast.unknown_public_material_recovery.v1",
        **base,
    }
    correction_without_digest = {
        "schema_version": ("legalforecast.unknown_public_url_commitment_correction.v1"),
        "purchase_policy_sha256": "1" * 64,
        "candidate_id": operation["candidate_id"],
        "source_document_id": operation["source_document_id"],
        "operation_key": operation["operation_key"],
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": operation["reservation_usd"],
        "attempt_policy_sha256": operation["attempt_policy_sha256"],
        "attempt_document_sha256": operation["attempt_document_sha256"],
        "provider_detail_sha256": material["provider_detail_sha256"],
        "legacy_download_url_sha256": legacy_digest,
        "corrected_download_url_sha256": corrected_digest,
        "legacy_recovery_record_sha256": _hash(legacy),
        "billing_authority": {
            "state": "unknown_public_unreconciled",
            "reservation_retained": True,
            "no_paid_redispatch": True,
        },
        "material_authority": "unknown_status_attempt",
        "material_status": "available_pending_quarantine",
        "pre_byte_correction": True,
    }
    correction = {
        **correction_without_digest,
        "record_sha256": _hash(correction_without_digest),
    }
    return {
        "schema_version": "legalforecast.unknown_public_material_recovery.v2",
        **base,
        "download_url_sha256": corrected_digest,
        "courtlistener_url_commitment_correction": correction,
    }

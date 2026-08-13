"""Focused contract tests for the generic missing-document successor."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest
from legalforecast.ingestion.missing_document_successor import (
    AcquisitionObservation,
    MissingDocumentSuccessorError,
    RepairApproval,
    project_missing_document_successor,
    verify_repair_approval,
)


def _manifest_bytes(*, free_count: int = 1, cost: float = 0.0) -> bytes:
    record = {
        "candidate_id": "case-1",
        "recommendation": "repair",
        "cost_usd": cost,
        "missing_docs": [
            {
                "entry": 12,
                "role": "opposition",
                "cost_usd": cost,
                "free_document_count": free_count,
                "pacer_only_document_count": 0 if free_count else 1,
                "source": "pass1",
                "evidence": "docket and briefing audit",
                "opinion_derived": False,
            }
        ],
        "byte_mismatches": [
            {
                "entry": 4,
                "selected_role": "amended_complaint",
                "observed_role": "summons",
                "basis": "AO 440 body",
            }
        ],
    }
    return (json.dumps(record, sort_keys=True) + "\n").encode()


def _approval(manifest: bytes, *, maximum: str = "3.00") -> RepairApproval:
    return verify_repair_approval(
        manifest,
        {
            "schema_version": "legalforecast.repair_manifest_approval.v1",
            "decision": "approve",
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "maximum_cost_usd": maximum,
            "candidate_count": 1,
            "repair_count": 1,
            "keep_count": 0,
            "replace_count": 0,
            "missing_slot_count": 1,
        },
    )


def _observation(
    *,
    entry: int = 12,
    document_selector: str = "main",
    requested_role: str = "opposition",
    source_kind: str = "free",
    status: str = "acquired",
    cost: str = "0.00",
    markdown: str | None = "PLAINTIFF'S RESPONSE IN OPPOSITION TO MOTION",
) -> AcquisitionObservation:
    payload = b"opposition-pdf"
    return AcquisitionObservation(
        candidate_id="case-1",
        docket_entry_number=entry,
        document_selector=document_selector,
        requested_role=requested_role,
        source_document_id=(f"case-1-entry-{entry}-{document_selector}-{source_kind}"),
        source_kind=source_kind,
        status=status,
        cost_usd=Decimal(cost),
        content=payload if status == "acquired" else None,
        markdown=markdown if status == "acquired" else None,
        clearance_status="cleared" if status == "acquired" else None,
        is_private=False if status == "acquired" else None,
        is_sealed=False if status == "acquired" else None,
    )


def _base_selection() -> tuple[dict[str, object], ...]:
    return (
        {
            "candidate_id": "case-1",
            "selected": True,
            "documents": [
                {
                    "docket_entry_number": 4,
                    "source_document_id": "case-1-entry-4-amended-complaint",
                    "document_role": "amended_complaint",
                },
                {
                    "docket_entry_number": 10,
                    "source_document_id": "case-1-entry-10-motion",
                    "document_role": "motion_to_dismiss_memorandum",
                },
            ],
        },
    )


def test_successor_removes_wrong_bytes_and_admits_free_role_match() -> None:
    manifest = _manifest_bytes()

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(_observation(),),
    )

    documents = result.selection_records[0]["documents"]
    assert [document["docket_entry_number"] for document in documents] == [10, 12]
    assert result.inclusion_ledger[0]["source_kind"] == "free"
    assert result.exclusion_ledger[0]["reason"] == "selected_bytes_mismatch_role"
    assert result.state["status"] == "sealed"
    assert result.state["manifest_sha256"] == hashlib.sha256(manifest).hexdigest()
    assert result.state["paid_cost_usd"] == "0.00"
    assert result.state["output_sha256s"] == {
        "exclusion-ledger.jsonl": hashlib.sha256(
            result.exclusion_ledger_bytes
        ).hexdigest(),
        "inclusion-ledger.jsonl": hashlib.sha256(
            result.inclusion_ledger_bytes
        ).hexdigest(),
        "target-cohort-selection.jsonl": hashlib.sha256(
            result.selection_bytes
        ).hexdigest(),
    }


def test_paid_acquisition_requires_prior_free_exhaustion() -> None:
    manifest = _manifest_bytes(free_count=1, cost=3.0)

    with pytest.raises(
        MissingDocumentSuccessorError,
        match="PACER acquisition preceded free-source exhaustion",
    ):
        project_missing_document_successor(
            base_selection=_base_selection(),
            manifest_bytes=manifest,
            approval=_approval(manifest),
            acquisitions=(_observation(source_kind="pacer", cost="3.00"),),
        )


def test_paid_acquisition_is_admitted_after_free_exhaustion_within_approval() -> None:
    manifest = _manifest_bytes(free_count=1, cost=3.0)

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(
            _observation(source_kind="free", status="unavailable"),
            _observation(source_kind="pacer", cost="3.00"),
        ),
    )

    assert result.state["paid_cost_usd"] == "3.00"
    assert result.inclusion_ledger[0]["source_kind"] == "pacer"


def test_role_mismatch_is_excluded_and_slot_is_terminal() -> None:
    manifest = _manifest_bytes()

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(_observation(markdown="DECLARATION OF ROBERT SANTORA"),),
    )

    assert len(result.inclusion_ledger) == 0
    assert [row["reason"] for row in result.exclusion_ledger] == [
        "selected_bytes_mismatch_role",
        "acquired_bytes_mismatch_requested_role",
    ]
    assert result.state["approved_slot_count"] == 1
    assert result.state["terminal_slot_count"] == 1


def test_approval_must_bind_exact_manifest_and_paid_ceiling() -> None:
    manifest = _manifest_bytes(free_count=0, cost=3.0)
    wrong_manifest = manifest.replace(
        b'"recommendation": "repair"',
        b'"recommendation":  "repair"',
    )
    with pytest.raises(MissingDocumentSuccessorError, match="approval manifest digest"):
        project_missing_document_successor(
            base_selection=_base_selection(),
            manifest_bytes=wrong_manifest,
            approval=_approval(manifest),
            acquisitions=(_observation(source_kind="pacer", cost="3.00"),),
        )

    with pytest.raises(MissingDocumentSuccessorError, match="approved cost ceiling"):
        project_missing_document_successor(
            base_selection=_base_selection(),
            manifest_bytes=manifest,
            approval=_approval(manifest, maximum="2.99"),
            acquisitions=(_observation(source_kind="pacer", cost="3.00"),),
        )


def test_every_approved_slot_requires_a_terminal_observation() -> None:
    manifest = _manifest_bytes()

    with pytest.raises(MissingDocumentSuccessorError, match="terminal disposition"):
        project_missing_document_successor(
            base_selection=_base_selection(),
            manifest_bytes=manifest,
            approval=_approval(manifest),
            acquisitions=(),
        )


def test_same_entry_documents_are_distinct_by_selector_and_role() -> None:
    missing_docs = [
        {
            "entry": 5,
            "document_selector": selector,
            "role": "motion_memorandum",
            "cost_usd": 3.0,
            "free_document_count": 0,
        }
        for selector in ("main", "attachment_1")
    ]
    manifest = (
        json.dumps(
            {
                "candidate_id": "case-1",
                "recommendation": "repair",
                "missing_docs": missing_docs,
                "byte_mismatches": [],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    approval = verify_repair_approval(
        manifest,
        {
            "schema_version": "legalforecast.repair_manifest_approval.v1",
            "decision": "approve",
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "maximum_cost_usd": "6.00",
            "candidate_count": 1,
            "repair_count": 1,
            "keep_count": 0,
            "replace_count": 0,
            "missing_slot_count": 2,
        },
    )

    result = project_missing_document_successor(
        base_selection=({"candidate_id": "case-1", "selected": True, "documents": []},),
        manifest_bytes=manifest,
        approval=approval,
        acquisitions=tuple(
            _observation(
                entry=5,
                document_selector=selector,
                requested_role="motion_memorandum",
                source_kind="pacer",
                cost="3.00",
                markdown="Memorandum in Support of Motion to Dismiss",
            )
            for selector in ("main", "attachment_1")
        ),
    )

    assert [
        document["document_selector"]
        for document in result.selection_records[0]["documents"]
    ] == ["main", "attachment_1"]


def test_replacement_recommendation_is_terminally_excluded() -> None:
    manifest = (
        json.dumps(
            {
                "candidate_id": "case-1",
                "recommendation": "replace",
                "missing_docs": [],
                "byte_mismatches": [],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    approval = verify_repair_approval(
        manifest,
        {
            "schema_version": "legalforecast.repair_manifest_approval.v1",
            "decision": "approve",
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "maximum_cost_usd": "0.00",
            "candidate_count": 1,
            "repair_count": 0,
            "keep_count": 0,
            "replace_count": 1,
            "missing_slot_count": 0,
        },
    )

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=approval,
        acquisitions=(),
    )

    assert result.selection_records[0]["selected"] is False
    assert result.selection_records[0]["documents"] == []
    assert result.exclusion_ledger[0]["reason"] == (
        "manifest_replacement_recommendation"
    )
    assert result.state["replacement_candidate_count"] == 1

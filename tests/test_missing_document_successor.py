"""Focused contract tests for the generic missing-document successor."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import pytest
from legalforecast.ingestion.missing_document_successor import (
    AcquisitionObservation,
    MissingDocumentSuccessorError,
    RepairApproval,
    build_missing_document_acquisition_plan,
    project_missing_document_successor,
    seal_missing_document_successor,
    verify_repair_approval,
    verify_repair_plan_approval,
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
    source_document_id: str | None = None,
) -> AcquisitionObservation:
    payload = b"opposition-pdf"
    return AcquisitionObservation(
        candidate_id="case-1",
        docket_entry_number=entry,
        document_selector=document_selector,
        requested_role=requested_role,
        source_document_id=source_document_id
        or (f"case-1-entry-{entry}-{document_selector}-{source_kind}"),
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


def test_v1_projection_preserves_legacy_main_selector_bytes() -> None:
    manifest = _manifest_bytes()

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(_observation(),),
    )

    assert result.inclusion_ledger[0]["document_selector"] == "main"
    assert result.selection_records[0]["documents"][-1]["document_selector"] == "main"
    assert b'"document_selector":"main"' in result.inclusion_ledger_bytes
    assert b'"document_selector":"main_document"' not in result.inclusion_ledger_bytes


def test_v1_projection_rejects_explicit_null_selector() -> None:
    record = json.loads(_manifest_bytes().decode())
    record["missing_docs"][0]["document_selector"] = None
    manifest = (json.dumps(record, sort_keys=True) + "\n").encode()

    with pytest.raises(MissingDocumentSuccessorError, match="document selector"):
        _approval(manifest)
    with pytest.raises(MissingDocumentSuccessorError, match="document selector"):
        _plan(manifest, cap="3.00")


def test_v1_projection_treats_main_aliases_as_one_slot() -> None:
    record = json.loads(_manifest_bytes().decode())
    first = dict(record["missing_docs"][0])
    record["missing_docs"] = [
        {**first, "document_selector": "main"},
        {**first, "document_selector": "main_document"},
    ]
    manifest = (json.dumps(record, sort_keys=True) + "\n").encode()

    with pytest.raises(MissingDocumentSuccessorError, match="duplicated"):
        _approval(manifest)


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
        for selector in ("main_document", "attachment_1")
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
            for selector in ("main_document", "attachment_1")
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


def _plan_manifest_bytes(*records: Mapping[str, object]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def _repair(
    candidate_id: str,
    *,
    missing: list[dict[str, object]],
    mismatch: list[dict[str, object]] | None = None,
    current: list[dict[str, object]] | None = None,
    required: list[dict[str, object]] | None = None,
    extra: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    cost = sum(Decimal(str(row["cost_usd"])) for row in missing)
    return {
        "candidate_id": candidate_id,
        "recommendation": "repair",
        "cost_usd": float(cost),
        "missing_docs": missing,
        "byte_mismatches": mismatch or [],
        "current_selection": current or [],
        "required_entries": required or [],
        "extra_selected": extra or [],
    }


def _missing(
    entry: int,
    role: str,
    *,
    free: int,
    paid: int,
    selector: str = "main_document",
) -> dict[str, object]:
    return {
        "entry": entry,
        "document_selector": selector,
        "role": role,
        "cost_usd": 0.0 if free else 3.0,
        "free_document_count": free,
        "pacer_only_document_count": paid,
        "evidence": "synthetic regression fixture",
        "source": "pass1",
        "opinion_derived": False,
    }


def _public_acquired(
    evidence: dict[str, object], *, cost: str = "0.00"
) -> dict[str, object]:
    return {
        **evidence,
        "clearance_status": "cleared",
        "is_private": False,
        "is_sealed": False,
        "cost_usd": cost,
    }


def _plan(manifest: bytes, *, cap: str = "453.00") -> Any:
    rows = [json.loads(line) for line in manifest.splitlines() if line]
    return build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=verify_repair_plan_approval(
            manifest,
            {
                "schema_version": "legalforecast.repair_manifest_approval.v2",
                "decision": "approve",
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "maximum_cost_usd": cap,
                "max_per_document_usd": "3.00",
                "candidate_count": len(rows),
                "repair_count": sum(row["recommendation"] == "repair" for row in rows),
                "keep_count": sum(row["recommendation"] == "keep" for row in rows),
                "replace_count": sum(
                    row["recommendation"] == "replace" for row in rows
                ),
                "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
            },
        ),
    )


def test_plan_is_bound_to_exact_approved_plan_manifest_bytes() -> None:
    manifest = _plan_manifest_bytes(
        _repair("70754103", missing=[_missing(12, "response", free=0, paid=1)])
    )

    with pytest.raises((MissingDocumentSuccessorError, json.JSONDecodeError)):
        _plan(manifest + b" ")


def test_plan_orders_free_recovery_before_paid_and_is_deterministic() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[
                _missing(12, "response", free=0, paid=1),
                _missing(13, "reply", free=1, paid=0),
            ],
        ),
        _repair(
            "71212565",
            missing=[_missing(23, "crossclaim", free=0, paid=1)],
        ),
    )

    plan = _plan(manifest)

    assert [item.acquisition_method for item in plan.items] == [
        "courtlistener_free",
        "pacer_purchase",
        "pacer_purchase",
    ]
    assert [(item.candidate_id, item.docket_entry_number) for item in plan.items] == [
        ("70754103", 13),
        ("70754103", 12),
        ("71212565", 23),
    ]
    assert plan.projected_paid_cost_usd == Decimal("6.00")
    assert plan.to_record() == _plan(manifest).to_record()


def test_plan_distinguishes_same_entry_main_document_and_attachment() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "73569789",
            missing=[
                _missing(5, "motion", free=0, paid=1),
                _missing(
                    5,
                    "supporting_memorandum",
                    free=0,
                    paid=1,
                    selector="attachment_1",
                ),
            ],
        )
    )

    plan = _plan(manifest)

    assert [
        (item.docket_entry_number, item.document_selector) for item in plan.items
    ] == [
        (5, "attachment_1"),
        (5, "main_document"),
    ]


def test_plan_rejects_replacement_recommendation() -> None:
    manifest = _plan_manifest_bytes(
        {
            "candidate_id": "70754103",
            "recommendation": "replace",
            "cost_usd": 0.0,
            "missing_docs": [],
            "byte_mismatches": [],
            "current_selection": [{"entry": 12, "role": "complaint"}],
            "required_entries": [{"entry": 12, "role": "complaint"}],
            "extra_selected": [{"entry": 12, "role": "complaint"}],
        }
    )

    plan = _plan(manifest)
    assert plan.items == ()
    assert plan.existing_document_ledger == ()
    assert plan.manifest_repair_count == 0


def test_plan_refuses_per_document_and_aggregate_approval_overruns() -> None:
    wrong_price = _plan_manifest_bytes(
        {
            **_repair(
                "70754103",
                missing=[_missing(12, "response", free=0, paid=1)],
            ),
            "cost_usd": 4.0,
            "missing_docs": [
                {
                    **_missing(12, "response", free=0, paid=1),
                    "cost_usd": 4.0,
                }
            ],
        }
    )
    with pytest.raises(MissingDocumentSuccessorError, match="per-document cap"):
        _plan(wrong_price)

    two_paid = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[
                _missing(12, "response", free=0, paid=1),
                _missing(13, "reply", free=0, paid=1),
            ],
        )
    )
    with pytest.raises(MissingDocumentSuccessorError, match="approved maximum"):
        _plan(two_paid, cap="3.00")


def test_seal_requires_role_matching_bytes_before_inclusion() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[_missing(1, "complaint", free=0, paid=1)],
            mismatch=[
                {
                    "entry": 4,
                    "selected_role": "amended_complaint",
                    "observed_role": "summons",
                    "verdict": "mismatch",
                    "evidence": "AO 440 summons",
                }
            ],
        )
    )
    plan = _plan(manifest)
    evidence = _public_acquired(
        {
            "candidate_id": "70754103",
            "docket_entry_number": 1,
            "document_role": "complaint",
            "source_document_id": "70754103-entry-1",
            "source": "pacer_purchase",
            "sha256": hashlib.sha256(b"AO 440 summons").hexdigest(),
            "byte_count": len(b"AO 440 summons"),
            "document_bytes": b"AO 440 summons",
        },
        cost="3.00",
    )

    with pytest.raises(MissingDocumentSuccessorError, match="role-byte mismatch"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[evidence],
            exclusions=[],
            role_bytes_match=lambda role, body: (
                role != "complaint" or b"complaint" in body
            ),
        )


def test_sealed_successor_has_complete_inclusion_exclusion_ledger() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[
                _missing(12, "response", free=0, paid=1),
                _missing(13, "reply", free=1, paid=0),
            ],
        )
    )
    plan = _plan(manifest)
    reply_bytes = b"reply to response"
    evidence = _public_acquired(
        {
            "candidate_id": "70754103",
            "docket_entry_number": 13,
            "document_role": "reply",
            "source_document_id": "70754103-entry-13",
            "source": "courtlistener_free",
            "sha256": hashlib.sha256(reply_bytes).hexdigest(),
            "byte_count": len(reply_bytes),
            "document_bytes": reply_bytes,
        }
    )

    sealed = seal_missing_document_successor(
        plan=plan,
        acquired_documents=[evidence],
        exclusions=[
            {
                "candidate_id": "70754103",
                "docket_entry_number": 12,
                "document_role": "response",
                "reason": "sealed_or_unavailable",
            }
        ],
        role_bytes_match=lambda _role, _body: True,
    )

    assert sealed.status == "sealed"
    assert len(sealed.ledger) == len(plan.items) == 2
    assert [row["disposition"] for row in sealed.ledger] == [
        "included",
        "excluded",
    ]
    assert sealed.included_document_keys == frozenset(
        {("70754103", 13, "main_document")}
    )
    with pytest.raises(MissingDocumentSuccessorError, match="complete ledger"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[evidence],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )


def test_plan_accounts_for_retained_extra_and_byte_mismatch_entries() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[_missing(1, "complaint", free=0, paid=1)],
            current=[
                {"entry": 4, "role": "amended_complaint"},
                {"entry": 10, "role": "motion_to_dismiss_memorandum"},
            ],
            required=[
                {"entry": 1, "role": "complaint"},
                {"entry": 10, "role": "target_motion"},
            ],
            extra=[{"entry": 4, "role": "amended_complaint"}],
            mismatch=[
                {
                    "entry": 4,
                    "selected_role": "amended_complaint",
                    "observed_role": "summons",
                    "verdict": "mismatch",
                    "evidence": "AO 440 summons",
                }
            ],
        )
    )

    plan = _plan(manifest)

    assert [row["disposition"] for row in plan.existing_document_ledger] == [
        "rejected_byte_role",
        "retained",
    ]
    assert plan.existing_document_ledger[0]["reason"] == "byte_role_mismatch"
    assert plan.existing_document_ledger[1]["docket_entry_number"] == 10


def test_plan_carries_byte_mismatches_without_current_selection() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[_missing(1, "complaint", free=0, paid=1)],
            mismatch=[
                {
                    "entry": 4,
                    "selected_role": "amended_complaint",
                    "observed_role": "summons",
                    "verdict": "mismatch",
                    "evidence": "AO 440 summons",
                }
            ],
        )
    )

    plan = _plan(manifest)

    assert [dict(row) for row in plan.existing_document_ledger] == [
        {
            "candidate_id": "70754103",
            "docket_entry_number": 4,
            "document_selector": "main_document",
            "document_role": "amended_complaint",
            "disposition": "rejected_byte_role",
            "reason": "byte_role_mismatch",
            "observed_role": "summons",
            "evidence": "AO 440 summons",
        }
    ]


def test_plan_carries_same_entry_main_and_attachment_mismatches() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "73569789",
            missing=[_missing(1, "complaint", free=0, paid=1)],
            mismatch=[
                {
                    "entry": 5,
                    "document_selector": "main_document",
                    "selected_role": "motion",
                    "observed_role": "notice",
                    "verdict": "mismatch",
                    "evidence": "notice of hearing",
                },
                {
                    "entry": 5,
                    "document_selector": "attachment_1",
                    "selected_role": "supporting_memorandum",
                    "observed_role": "exhibit",
                    "verdict": "mismatch",
                    "evidence": "exhibit A",
                },
            ],
        )
    )

    plan = _plan(manifest)

    assert [
        (row["docket_entry_number"], row["document_selector"], row["document_role"])
        for row in plan.existing_document_ledger
    ] == [
        (5, "attachment_1", "supporting_memorandum"),
        (5, "main_document", "motion"),
    ]


def test_plan_rejects_blank_manifest_lines() -> None:
    row = json.dumps(
        _repair("70754103", missing=[_missing(12, "response", free=0, paid=1)]),
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest = f"{row}\n\n{row}\n".encode()

    with pytest.raises(MissingDocumentSuccessorError, match="invalid JSON"):
        _plan(manifest)


def test_seal_rejects_wrong_bytes_and_unplanned_paid_substitution() -> None:
    manifest = _plan_manifest_bytes(
        _repair("70754103", missing=[_missing(13, "reply", free=1, paid=0)])
    )
    plan = _plan(manifest)
    body = b"reply"
    evidence = {
        "candidate_id": "70754103",
        "docket_entry_number": 13,
        "document_role": "reply",
        "source_document_id": "70754103-entry-13",
        "source": "pacer_purchase",
        "sha256": hashlib.sha256(body).hexdigest(),
        "byte_count": len(body),
        "document_bytes": body,
    }

    with pytest.raises(MissingDocumentSuccessorError, match="planned method"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[evidence],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )

    evidence["source"] = "courtlistener_free"
    evidence["sha256"] = "0" * 64
    with pytest.raises(MissingDocumentSuccessorError, match="SHA-256"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[evidence],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )


def test_seal_rejects_reused_source_document_id() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[
                _missing(12, "response", free=1, paid=0),
                _missing(13, "reply", free=1, paid=0),
            ],
        )
    )
    plan = _plan(manifest)
    response = b"response"
    reply = b"reply"

    def _evidence(entry: int, role: str, body: bytes) -> dict[str, object]:
        return _public_acquired(
            {
                "candidate_id": "70754103",
                "docket_entry_number": entry,
                "document_role": role,
                "source_document_id": "reused-id",
                "source": "courtlistener_free",
                "sha256": hashlib.sha256(body).hexdigest(),
                "byte_count": len(body),
                "document_bytes": body,
            }
        )

    with pytest.raises(MissingDocumentSuccessorError, match="source document"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[
                _evidence(12, "response", response),
                _evidence(13, "reply", reply),
            ],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )


def test_plan_allows_zero_aggregate_ceiling_for_free_only_work() -> None:
    manifest = _plan_manifest_bytes(
        _repair("70754103", missing=[_missing(13, "reply", free=1, paid=0)])
    )

    plan = _plan(manifest, cap="0.00")

    assert plan.approved_maximum_usd == Decimal("0.00")
    assert plan.projected_paid_cost_usd == Decimal("0.00")


def test_plan_rejects_collapsed_multi_document_acquisition_rows() -> None:
    manifest = _plan_manifest_bytes(
        _repair(
            "70754103",
            missing=[_missing(13, "reply", free=2, paid=0)],
        )
    )

    with pytest.raises(MissingDocumentSuccessorError, match="multiple acquisition"):
        _plan(manifest)


def test_seal_refuses_uncleared_or_over_ceiling_paid_cost() -> None:
    manifest = _plan_manifest_bytes(
        _repair("70754103", missing=[_missing(12, "response", free=0, paid=1)])
    )
    plan = _plan(manifest)
    body = b"opposition"
    evidence = _public_acquired(
        {
            "candidate_id": "70754103",
            "docket_entry_number": 12,
            "document_role": "response",
            "source_document_id": "70754103-entry-12",
            "source": "pacer_purchase",
            "sha256": hashlib.sha256(body).hexdigest(),
            "byte_count": len(body),
            "document_bytes": body,
        },
        cost="3.00",
    )

    with pytest.raises(MissingDocumentSuccessorError, match="clearance_status"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[{**evidence, "clearance_status": "held"}],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )

    with pytest.raises(MissingDocumentSuccessorError, match="cost_usd"):
        seal_missing_document_successor(
            plan=plan,
            acquired_documents=[{**evidence, "cost_usd": "2.99"}],
            exclusions=[],
            role_bytes_match=lambda _role, _body: True,
        )


def test_projector_refuses_accumulated_pacer_spend_over_slot_ceiling() -> None:
    manifest = _manifest_bytes(free_count=0, cost=3.0)

    with pytest.raises(MissingDocumentSuccessorError, match="approved cost ceiling"):
        project_missing_document_successor(
            base_selection=_base_selection(),
            manifest_bytes=manifest,
            approval=_approval(manifest),
            acquisitions=(
                _observation(source_kind="free", status="unavailable"),
                _observation(
                    source_kind="pacer",
                    cost="2.00",
                    status="unavailable",
                    markdown=None,
                    source_document_id="case-1-pacer-attempt-1",
                ),
                _observation(
                    source_kind="pacer",
                    cost="2.00",
                    source_document_id="case-1-pacer-attempt-2",
                ),
            ),
        )


def test_projector_requires_briefing_support_token_for_opposition() -> None:
    manifest = _manifest_bytes()

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(_observation(markdown="PLAINTIFF'S OPPOSITION"),),
    )

    assert [
        row["reason"]
        for row in result.exclusion_ledger
        if str(row["reason"]).startswith("acquired")
    ] == ["acquired_bytes_mismatch_requested_role"]

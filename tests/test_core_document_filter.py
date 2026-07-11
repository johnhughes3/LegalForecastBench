from __future__ import annotations

import json

from legalforecast.ingestion.core_document_filter import (
    filter_core_documents,
    filter_core_documents_from_jsonl,
)


def test_filter_selects_only_core_documents_for_purchase_plan() -> None:
    result = filter_core_documents(
        [
            _record(
                "complaint",
                label="other_substantive",
                role="complaint",
                available=False,
                entry_number=1,
            ),
            _record(
                "motion",
                label="core_mtd",
                role="motion_to_dismiss_memorandum",
                available=False,
                entry_number=34,
            ),
            _record(
                "exhibit",
                label="core_exhibit",
                role="other",
                available=False,
                entry_number=35,
            ),
            _record(
                "non-target-motion",
                label="other_substantive",
                role="other",
                available=False,
                entry_number=40,
            ),
            _record(
                "certificate",
                label="procedural_minor",
                role="other",
                available=False,
                entry_number=41,
            ),
        ]
    )[0]

    assert result.operative_complaint_document_id == "complaint"
    assert result.missing_operative_complaint is False
    assert result.purchase_document_ids == ("complaint", "motion", "exhibit")
    assert result.core_missing_documents == ("complaint", "motion", "exhibit")
    assert result.core_exhibit_documents == ("exhibit",)
    assert result.audit_only_document_ids == ("non-target-motion", "certificate")
    assert result.exclusion_reasons == ()


def test_filter_reports_missing_operative_complaint() -> None:
    result = filter_core_documents(
        [
            _record(
                "motion",
                label="core_mtd",
                role="motion_to_dismiss_memorandum",
                available=True,
                entry_number=21,
            )
        ]
    )[0]

    assert result.missing_operative_complaint is True
    assert result.operative_complaint_document_id is None
    assert result.purchase_document_ids == ()
    assert result.exclusion_reasons == ("missing_operative_complaint",)


def test_filter_jsonl_ignores_ambiguous_complaint_like_docket_text() -> None:
    payload = "\n".join(
        json.dumps(record)
        for record in (
            {
                "candidate_id": "cand-1",
                "source_document_id": "notice",
                "docket_entry_number": 12,
                "docket_entry_text": "Notice of amended complaint deadline",
                "setup_runner_label": "other_substantive",
                "availability_status": "available",
            },
            _record(
                "motion",
                label="core_mtd",
                role="motion_to_dismiss_notice",
                available=True,
                entry_number=20,
            ),
        )
    )

    result = filter_core_documents_from_jsonl(payload)[0]

    assert result.missing_operative_complaint is True
    assert result.operative_complaint_document_id is None
    assert "notice" not in result.model_visible_document_ids
    assert result.to_record()["core_missing_documents"] == []


def test_filter_purchases_missing_decision_for_labeling_without_mounting_it() -> None:
    result = filter_core_documents(
        [
            _record(
                "complaint",
                label="core_mtd",
                role="complaint",
                available=True,
                entry_number=1,
            ),
            _record(
                "motion",
                label="core_mtd",
                role="motion_to_dismiss_notice",
                available=True,
                entry_number=5,
            ),
            _record(
                "decision",
                label="other_substantive",
                role="decision",
                available=False,
                entry_number=16,
            ),
        ]
    )[0]

    assert result.purchase_document_ids == ("decision",)
    assert result.core_missing_documents == ("decision",)
    assert "decision" not in result.model_visible_document_ids
    assert result.audit_only_document_ids == ("decision",)


def _record(
    source_document_id: str,
    *,
    label: str,
    role: str,
    available: bool,
    entry_number: int,
) -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_id": f"entry-{entry_number}",
        "docket_entry_number": entry_number,
        "docket_entry_text": source_document_id.replace("-", " "),
        "setup_runner_label": label,
        "document_role": role,
        "availability_status": "available" if available else "unavailable",
        "requires_paid_recovery": not available,
    }

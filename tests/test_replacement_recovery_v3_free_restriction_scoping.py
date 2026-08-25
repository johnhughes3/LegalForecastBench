"""v3 free-path restriction scoping for canonical vs legacy clearance rows."""

from __future__ import annotations

import json

import pytest
from legalforecast.ingestion.replacement_recovery_v3_register import (
    admit_authenticated_v3_free_clearance_rows,
)


def _v3_admission_jsonl(values: list[dict[str, object]]) -> bytes:
    return b"".join(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        for value in values
    )


def _admit(
    manifest: dict[str, object],
    clearance: dict[str, object],
    restriction: dict[str, object],
) -> tuple[dict[str, object], ...]:
    return admit_authenticated_v3_free_clearance_rows(
        manifest_records=[manifest],
        clearance_records=[clearance],
        restriction_records=[restriction],
        authenticated_clearance_records=[clearance],
        authenticated_clearance_bytes=_v3_admission_jsonl([clearance]),
        authenticated_restriction_bytes=_v3_admission_jsonl([restriction]),
    )


def _legacy_free_rows() -> tuple[
    dict[str, object], dict[str, object], dict[str, object]
]:
    manifest: dict[str, object] = {
        "candidate_id": "C001",
        "source_document_id": "C001-entry-1-decision",
        "free_or_purchased": "free",
        "local_path": "C001/C001-entry-1-decision.pdf",
        "sha256": "f" * 64,
        "byte_count": 625640,
    }
    clearance: dict[str, object] = {
        "byte_count": 625640,
        "candidate_id": "C001",
        "clearance_basis": "courtlistener_public_download",
        "free_or_purchased": "free",
        "sha256": "f" * 64,
        "source_document_id": "C001-entry-1-decision",
        "status": "cleared",
    }
    restriction: dict[str, object] = {
        "candidate_id": "C001",
        "is_private": False,
        "is_sealed": False,
        "restriction_evidence": [
            "courtlistener_public_download_record_checked",
            "document_repair_byte_role_validation_match",
        ],
        "restriction_status": "public",
        "source_document_id": "C001-entry-1-decision",
    }
    return manifest, clearance, restriction


def _canonical_free_rows(
    *,
    is_private: object,
    is_sealed: object,
    restriction_status: str,
    clearance_evidence: list[str],
    restriction_evidence: list[str],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manifest: dict[str, object] = {
        "candidate_id": "C001",
        "source_document_id": "C001-entry-1-decision",
        "free_or_purchased": "free",
        "local_path": "C001/C001-entry-1-decision.pdf",
        "sha256": "c" * 64,
        "byte_count": 12,
    }
    clearance: dict[str, object] = {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        **manifest,
        "status": "cleared",
        "clearance_basis": "affirmative_public_provenance",
        "restriction_status": restriction_status,
        "restriction_evidence": clearance_evidence,
    }
    restriction: dict[str, object] = {
        "candidate_id": "C001",
        "source_document_id": "C001-entry-1-decision",
        "is_private": is_private,
        "is_sealed": is_sealed,
        "restriction_status": restriction_status,
        "restriction_evidence": restriction_evidence,
    }
    return manifest, clearance, restriction


def test_canonical_v1_free_row_with_null_restriction_booleans_is_admitted() -> None:
    manifest, clearance, restriction = _canonical_free_rows(
        is_private=None,
        is_sealed=None,
        restriction_status="public",
        clearance_evidence=["courtlistener_public_download_record_checked"],
        restriction_evidence=["courtlistener_public_download_record_checked"],
    )

    admitted = _admit(manifest, clearance, restriction)

    assert admitted == (clearance,)


def test_canonical_v1_free_row_admits_permuted_restriction_evidence() -> None:
    clearance_evidence = [
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "docket_entry_exact_match",
        "docket_exact_match",
        "public_download_url_allowlisted",
        "recap_document_exact_match",
    ]
    restriction_evidence = [
        "docket_exact_match",
        "docket_entry_exact_match",
        "recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "public_download_url_allowlisted",
    ]
    manifest, clearance, restriction = _canonical_free_rows(
        is_private=None,
        is_sealed=None,
        restriction_status="unknown",
        clearance_evidence=clearance_evidence,
        restriction_evidence=restriction_evidence,
    )

    admitted = _admit(manifest, clearance, restriction)

    assert admitted == (clearance,)
    assert restriction["restriction_evidence"] != clearance["restriction_evidence"]


def test_legacy_free_row_with_non_false_restriction_booleans_is_refused() -> None:
    manifest, clearance, restriction = _legacy_free_rows()
    restriction["is_private"] = None

    with pytest.raises(ValueError, match="exact restriction booleans differ"):
        _admit(manifest, clearance, restriction)


def test_canonical_v1_free_row_with_distinct_restriction_evidence_is_refused() -> None:
    manifest, clearance, restriction = _canonical_free_rows(
        is_private=None,
        is_sealed=None,
        restriction_status="public",
        clearance_evidence=["courtlistener_public_download_record_checked"],
        restriction_evidence=["different_authenticated_evidence"],
    )

    with pytest.raises(ValueError, match="differs from clearance"):
        _admit(manifest, clearance, restriction)

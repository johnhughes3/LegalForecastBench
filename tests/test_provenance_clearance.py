from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.provenance_clearance import (
    ProvenanceClearanceError,
    build_provenance_clearance_plan,
    build_provenance_clearance_records,
    canonical_json_bytes,
    exception_review_worksheet,
)

PUBLIC_EVIDENCE = ["courtlistener_public_download_record_checked"]
REST_PUBLIC_EVIDENCE = [
    "courtlistener_rest_docket_exact_match",
    "courtlistener_rest_docket_entry_exact_match",
    "courtlistener_rest_recap_document_exact_match",
    "courtlistener_rest_recap_document_is_available_true",
    "courtlistener_rest_recap_document_is_sealed_unknown",
    "courtlistener_rest_public_download_url_allowlisted",
]


def _jsonl(rows: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


@dataclass(frozen=True, slots=True)
class Inputs:
    document_root: Path
    manifest: list[dict[str, object]]
    restrictions: list[dict[str, object]]
    requests: list[dict[str, object]]
    relevance: list[dict[str, object]]


def _inputs(tmp_path: Path) -> Inputs:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    data = {
        "public-safe": b"public-safe",
        "rest-safe": b"rest-safe",
        "marker": b"marker",
        "restricted": b"restricted",
        "contradiction": b"contradiction",
    }
    manifest: list[dict[str, object]] = []
    restrictions: list[dict[str, object]] = []
    relevance_documents: list[dict[str, object]] = []
    for document_id, payload in data.items():
        path = f"case-a/{document_id}.pdf"
        target = document_root / path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(payload)
        manifest.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "local_path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_count": len(payload),
                "free_or_purchased": "free",
                "source_provider": "courtlistener",
                "source_url": (
                    f"https://storage.courtlistener.com/recap/case/{document_id}.pdf"
                ),
            }
        )
        status = "unknown" if document_id == "rest-safe" else "public"
        evidence = REST_PUBLIC_EVIDENCE if status == "unknown" else PUBLIC_EVIDENCE
        if document_id == "restricted":
            status = "public"
            evidence = ["courtlistener_recap_document_is_sealed_true"]
        restrictions.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "restriction_status": status,
                "restriction_evidence": evidence,
                "is_sealed": None,
                "is_private": None,
            }
        )
        relevance_documents.append(
            {
                "source_document_id": document_id,
                "source_url_or_reference": manifest[-1]["source_url"],
                "model_visible": True,
                "contains_target_outcome": document_id == "contradiction",
            }
        )
    requests = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": row["candidate_id"],
            "source_document_id": row["source_document_id"],
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
            "free_or_purchased": row["free_or_purchased"],
            "restriction_status": restriction["restriction_status"],
            "restriction_evidence": restriction["restriction_evidence"],
            "required_human_decision": "cleared_or_quarantined",
        }
        for row, restriction in zip(manifest, restrictions, strict=True)
    ]
    relevance_documents.append(
        {
            "source_document_id": "missing-paid",
            "availability_status": "unavailable",
            "requires_paid_recovery": True,
            "is_available": False,
            "model_visible": True,
            "contains_target_outcome": False,
        }
    )
    relevance: list[dict[str, object]] = [
        {"candidate_id": "case-a", "documents": relevance_documents}
    ]
    return Inputs(document_root, manifest, restrictions, requests, relevance)


def _plan(tmp_path: Path) -> dict[str, object]:
    values = _inputs(tmp_path)
    return build_provenance_clearance_plan(
        values.requests,
        values.manifest,
        values.restrictions,
        values.relevance,
        document_root=values.document_root,
        review_requests_bytes=_jsonl(values.requests),
        download_manifest_bytes=_jsonl(values.manifest),
        restriction_evidence_bytes=_jsonl(values.restrictions),
        case_relevance_bytes=_jsonl(values.relevance),
        marker_scanner=lambda payload: (
            ("extraction_page_count_mismatch",)
            if payload in {b"marker", b"restricted", b"contradiction"}
            else ()
        ),
    )


def _documents(artifact: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = artifact["documents"]
    assert isinstance(raw, list)
    assert all(isinstance(row, Mapping) for row in cast(list[object], raw))
    return cast(list[Mapping[str, object]], raw)


def _route_reasons(document: Mapping[str, object]) -> list[str]:
    reasons = document["route_reasons"]
    assert isinstance(reasons, list)
    raw_reasons = cast(list[object], reasons)
    assert all(isinstance(item, str) for item in raw_reasons)
    return cast(list[str], raw_reasons)


def test_plan_auto_clears_only_structural_diagnostics_after_public_gates(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    documents = {cast(str, row["source_document_id"]): row for row in _documents(plan)}

    assert plan["document_count"] == 5
    assert plan["auto_clear_count"] == 3
    assert plan["john_review_count"] == 2
    assert documents["public-safe"]["route"] == "auto_clear"
    assert documents["rest-safe"]["route"] == "auto_clear"
    assert documents["marker"]["route"] == "auto_clear"
    assert documents["marker"]["automated_markers"] == [
        "extraction_page_count_mismatch"
    ]
    assert "automated_marker_present" not in _route_reasons(documents["marker"])
    assert documents["marker"]["human_clearance_permitted"] is True
    assert documents["restricted"]["route"] == "john_exception_review"
    assert documents["restricted"]["human_clearance_permitted"] is False
    assert documents["restricted"]["automated_markers"] == [
        "extraction_page_count_mismatch"
    ]
    assert documents["contradiction"]["route"] == "john_exception_review"
    assert documents["contradiction"]["human_clearance_permitted"] is False
    assert documents["contradiction"]["automated_markers"] == [
        "extraction_page_count_mismatch"
    ]

    worksheet = exception_review_worksheet(plan)
    assert worksheet["document_count"] == 2
    assert {row["source_document_id"] for row in _documents(worksheet)} == {
        "restricted",
        "contradiction",
    }


@pytest.mark.parametrize("substantive_marker", ["medical", "ssn", "future_marker"])
def test_plan_keeps_every_substantive_marker_in_review(
    tmp_path: Path, substantive_marker: str
) -> None:
    values = _inputs(tmp_path)

    plan = build_provenance_clearance_plan(
        values.requests,
        values.manifest,
        values.restrictions,
        values.relevance,
        document_root=values.document_root,
        review_requests_bytes=_jsonl(values.requests),
        download_manifest_bytes=_jsonl(values.manifest),
        restriction_evidence_bytes=_jsonl(values.restrictions),
        case_relevance_bytes=_jsonl(values.relevance),
        marker_scanner=lambda payload: (
            (substantive_marker,) if payload == b"marker" else ()
        ),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["automated_markers"] == [substantive_marker]
    assert "automated_marker_present" in _route_reasons(marker)
    assert marker["human_clearance_permitted"] is True


def test_structural_diagnostic_does_not_suppress_substantive_marker(
    tmp_path: Path,
) -> None:
    values = _inputs(tmp_path)

    plan = build_provenance_clearance_plan(
        values.requests,
        values.manifest,
        values.restrictions,
        values.relevance,
        document_root=values.document_root,
        review_requests_bytes=_jsonl(values.requests),
        download_manifest_bytes=_jsonl(values.manifest),
        restriction_evidence_bytes=_jsonl(values.restrictions),
        case_relevance_bytes=_jsonl(values.relevance),
        marker_scanner=lambda payload: (
            ("extraction_page_count_mismatch", "medical")
            if payload == b"marker"
            else ()
        ),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["automated_markers"] == [
        "extraction_page_count_mismatch",
        "medical",
    ]
    assert "automated_marker_present" in _route_reasons(marker)


@pytest.mark.parametrize(
    ("restriction_status", "restriction_evidence"),
    [
        ("under seal", []),
        ("unknown", ["courtlistener is sealed true"]),
    ],
)
def test_plan_forbids_human_clearance_for_spaced_positive_restrictions(
    tmp_path: Path,
    restriction_status: str,
    restriction_evidence: list[str],
) -> None:
    values = _inputs(tmp_path)
    restriction = next(
        row for row in values.restrictions if row["source_document_id"] == "marker"
    )
    request = next(
        row for row in values.requests if row["source_document_id"] == "marker"
    )
    restriction["restriction_status"] = restriction_status
    restriction["restriction_evidence"] = restriction_evidence
    request["restriction_status"] = restriction_status
    request["restriction_evidence"] = restriction_evidence

    plan = build_provenance_clearance_plan(
        values.requests,
        values.manifest,
        values.restrictions,
        values.relevance,
        document_root=values.document_root,
        review_requests_bytes=_jsonl(values.requests),
        download_manifest_bytes=_jsonl(values.manifest),
        restriction_evidence_bytes=_jsonl(values.restrictions),
        case_relevance_bytes=_jsonl(values.relevance),
        marker_scanner=lambda _payload: (),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["human_clearance_permitted"] is False
    assert "positive_restriction_evidence" in _route_reasons(marker)


def test_structural_diagnostic_does_not_clear_unproven_unknown_restriction(
    tmp_path: Path,
) -> None:
    values = _inputs(tmp_path)
    restriction = next(
        row for row in values.restrictions if row["source_document_id"] == "marker"
    )
    request = next(
        row for row in values.requests if row["source_document_id"] == "marker"
    )
    restriction["restriction_status"] = "unknown"
    restriction["restriction_evidence"] = ["courtlistener_rest_docket_exact_match"]
    request["restriction_status"] = restriction["restriction_status"]
    request["restriction_evidence"] = restriction["restriction_evidence"]

    plan = build_provenance_clearance_plan(
        values.requests,
        values.manifest,
        values.restrictions,
        values.relevance,
        document_root=values.document_root,
        review_requests_bytes=_jsonl(values.requests),
        download_manifest_bytes=_jsonl(values.manifest),
        restriction_evidence_bytes=_jsonl(values.restrictions),
        case_relevance_bytes=_jsonl(values.relevance),
        marker_scanner=lambda payload: (
            ("extraction_page_count_mismatch",) if payload == b"marker" else ()
        ),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["human_clearance_permitted"] is True
    assert "affirmative_public_provenance_unproven" in _route_reasons(marker)
    assert "automated_marker_present" not in _route_reasons(marker)


def test_plan_rejects_changed_bytes(tmp_path: Path) -> None:
    values = _inputs(tmp_path)
    document_root = values.document_root
    (document_root / "case-a/public-safe.pdf").write_bytes(b"changed")

    with pytest.raises(ProvenanceClearanceError, match="manifest commitment"):
        build_provenance_clearance_plan(
            values.requests,
            values.manifest,
            values.restrictions,
            values.relevance,
            document_root=document_root,
            review_requests_bytes=_jsonl(values.requests),
            download_manifest_bytes=_jsonl(values.manifest),
            restriction_evidence_bytes=_jsonl(values.restrictions),
            case_relevance_bytes=_jsonl(values.relevance),
        )


@pytest.mark.parametrize("field,value", [("is_sealed", "true"), ("is_private", 1)])
def test_plan_rejects_malformed_restriction_flags(
    tmp_path: Path, field: str, value: object
) -> None:
    values = _inputs(tmp_path)
    restriction = next(
        row for row in values.restrictions if row["source_document_id"] == "public-safe"
    )
    restriction[field] = value

    with pytest.raises(ProvenanceClearanceError, match=f"restriction {field}"):
        build_provenance_clearance_plan(
            values.requests,
            values.manifest,
            values.restrictions,
            values.relevance,
            document_root=values.document_root,
            review_requests_bytes=_jsonl(values.requests),
            download_manifest_bytes=_jsonl(values.manifest),
            restriction_evidence_bytes=_jsonl(values.restrictions),
            case_relevance_bytes=_jsonl(values.relevance),
        )


@pytest.mark.parametrize(
    "field,value", [("model_visible", 1), ("contains_target_outcome", 0)]
)
def test_plan_rejects_numeric_visibility_flags(
    tmp_path: Path, field: str, value: object
) -> None:
    values = _inputs(tmp_path)
    raw_documents = values.relevance[0]["documents"]
    assert isinstance(raw_documents, list)
    visibility = next(
        row
        for row in cast(list[dict[str, object]], raw_documents)
        if row["source_document_id"] == "public-safe"
    )
    visibility[field] = value

    with pytest.raises(ProvenanceClearanceError, match=f"visibility {field}"):
        build_provenance_clearance_plan(
            values.requests,
            values.manifest,
            values.restrictions,
            values.relevance,
            document_root=values.document_root,
            review_requests_bytes=_jsonl(values.requests),
            download_manifest_bytes=_jsonl(values.manifest),
            restriction_evidence_bytes=_jsonl(values.restrictions),
            case_relevance_bytes=_jsonl(values.relevance),
        )


def test_plan_rejects_unexplained_extra_relevance_document(tmp_path: Path) -> None:
    values = _inputs(tmp_path)
    documents = values.relevance[0]["documents"]
    assert isinstance(documents, list)
    extra = cast(dict[str, object], documents[-1])
    extra["requires_paid_recovery"] = False

    with pytest.raises(ProvenanceClearanceError, match="not a missing paid gap"):
        build_provenance_clearance_plan(
            values.requests,
            values.manifest,
            values.restrictions,
            values.relevance,
            document_root=values.document_root,
            review_requests_bytes=_jsonl(values.requests),
            download_manifest_bytes=_jsonl(values.manifest),
            restriction_evidence_bytes=_jsonl(values.restrictions),
            case_relevance_bytes=_jsonl(values.relevance),
        )


def test_plan_rejects_document_symlink(tmp_path: Path) -> None:
    values = _inputs(tmp_path)
    document = values.document_root / "case-a/public-safe.pdf"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(document.read_bytes())
    document.unlink()
    document.symlink_to(outside)

    with pytest.raises(ProvenanceClearanceError, match="unsafe document path"):
        build_provenance_clearance_plan(
            values.requests,
            values.manifest,
            values.restrictions,
            values.relevance,
            document_root=values.document_root,
            review_requests_bytes=_jsonl(values.requests),
            download_manifest_bytes=_jsonl(values.manifest),
            restriction_evidence_bytes=_jsonl(values.restrictions),
            case_relevance_bytes=_jsonl(values.relevance),
        )


def test_clearance_requires_exact_hash_bound_exception_coverage(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    exception_rows: list[dict[str, object]] = [
        {
            "candidate_id": "case-a",
            "source_document_id": document_id,
            "status": "quarantined",
            "reviewed_at": "2026-07-26T03:00:00Z",
            "inspected_at": "2026-07-26T03:00:00Z",
            "inspected_sha256": next(
                row["sha256"]
                for row in _documents(plan)
                if row["source_document_id"] == document_id
            ),
            "recording_method": "interactive_review_cli",
            "intended_reviewer_id": "John Hughes",
        }
        for document_id in ("contradiction", "restricted")
    ]
    confirmation = hashlib.sha256(_jsonl(exception_rows)).hexdigest()
    decisions: list[dict[str, object]] = [
        {**row, "batch_confirmation_sha256": confirmation} for row in exception_rows
    ]
    plan_sha256 = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()

    records = build_provenance_clearance_records(
        plan,
        decisions,
        routing_plan_sha256=plan_sha256,
    )
    by_id = {row.source_document_id: row.to_record() for row in records}
    assert by_id["public-safe"]["status"] == "cleared"
    assert by_id["public-safe"]["clearance_basis"] == ("affirmative_public_provenance")
    assert by_id["marker"]["status"] == "cleared"
    assert by_id["marker"]["clearance_basis"] == "affirmative_public_provenance"
    assert by_id["restricted"]["status"] == "quarantined"
    assert by_id["contradiction"]["status"] == "quarantined"

    with pytest.raises(ProvenanceClearanceError, match="coverage mismatch"):
        build_provenance_clearance_records(
            plan,
            decisions[:-1],
            routing_plan_sha256=plan_sha256,
        )

    for unsafe_index in range(len(decisions)):
        unsafe: list[dict[str, object]] = [dict(row) for row in decisions]
        unsafe[unsafe_index]["status"] = "cleared"
        unsafe_bases: list[dict[str, object]] = [
            {
                key: value
                for key, value in row.items()
                if key != "batch_confirmation_sha256"
            }
            for row in unsafe
        ]
        unsafe_pin = hashlib.sha256(_jsonl(unsafe_bases)).hexdigest()
        unsafe = [{**row, "batch_confirmation_sha256": unsafe_pin} for row in unsafe]
        with pytest.raises(ProvenanceClearanceError, match="cannot be cleared"):
            build_provenance_clearance_records(
                plan,
                unsafe,
                routing_plan_sha256=plan_sha256,
            )

    forged = [dict(row) for row in decisions]
    forged[0]["intended_reviewer_id"] = "Mallory"
    forged_bases = [
        {key: value for key, value in row.items() if key != "batch_confirmation_sha256"}
        for row in forged
    ]
    forged_pin = hashlib.sha256(_jsonl(forged_bases)).hexdigest()
    forged = [{**row, "batch_confirmation_sha256": forged_pin} for row in forged]
    with pytest.raises(ProvenanceClearanceError, match="reviewer must be John"):
        build_provenance_clearance_records(
            plan,
            forged,
            routing_plan_sha256=plan_sha256,
        )

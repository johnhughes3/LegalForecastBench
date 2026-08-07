from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.disclosure_clearance import (
    PDF_SCAN_SCHEMA_VERSION,
    PDF_SCAN_SCHEMA_VERSION_V1,
    DisclosurePdfScan,
    scan_disclosure_document,
    scan_disclosure_document_v1,
)
from legalforecast.ingestion.provenance_clearance import (
    ProvenanceClearanceError,
    build_provenance_clearance_plan,
    build_provenance_clearance_records,
    cache_disclosure_document_scans,
    canonical_json_bytes,
    document_scanner_for_plan,
    exception_review_worksheet,
    validate_exception_review_worksheet,
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


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf"), "\ud800"))
def test_canonical_json_rejects_noncanonical_values(value: object) -> None:
    with pytest.raises(ProvenanceClearanceError, match="canonical JSON"):
        canonical_json_bytes({"value": value})


@dataclass(frozen=True, slots=True)
class Inputs:
    document_root: Path
    manifest: list[dict[str, object]]
    restrictions: list[dict[str, object]]
    requests: list[dict[str, object]]
    relevance: list[dict[str, object]]


def _complete_scan(*markers: str) -> DisclosurePdfScan:
    return DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=("legacy_extraction_page_count_mismatch",),
        automated_markers=tuple(sorted(markers)),
    )


def _incomplete_scan() -> DisclosurePdfScan:
    return DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(1,),
        coverage_status="incomplete",
        diagnostics=("page_text_empty:1",),
        automated_markers=(
            "extraction_page_coverage_incomplete",
            "unscannable_or_image_only",
        ),
    )


def _scanner(
    scans_by_payload: Mapping[bytes, DisclosurePdfScan],
):
    def scan(payload: bytes) -> DisclosurePdfScan:
        return scans_by_payload.get(payload, _complete_scan())

    return scan


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
        document_scanner=_scanner(
            {
                b"marker": _complete_scan(),
                b"restricted": _complete_scan(),
                b"contradiction": _complete_scan(),
            }
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


def test_plan_auto_clears_only_complete_marker_free_scans_after_public_gates(
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
    assert documents["marker"]["automated_markers"] == []
    assert documents["marker"]["disclosure_pdf_scan"]["coverage_status"] == "complete"
    assert "automated_marker_present" not in _route_reasons(documents["marker"])
    assert documents["marker"]["human_clearance_permitted"] is True
    assert documents["restricted"]["route"] == "john_exception_review"
    assert documents["restricted"]["human_clearance_permitted"] is False
    assert documents["restricted"]["automated_markers"] == []
    assert documents["contradiction"]["route"] == "john_exception_review"
    assert documents["contradiction"]["human_clearance_permitted"] is False
    assert documents["contradiction"]["automated_markers"] == []

    worksheet = exception_review_worksheet(plan)
    assert worksheet["document_count"] == 2
    assert {row["source_document_id"] for row in _documents(worksheet)} == {
        "restricted",
        "contradiction",
    }


@pytest.mark.parametrize(
    "source_url",
    (
        "https://storage.courtlistener.com:443/recap/case/public-safe.pdf",
        "https://storage.courtlistener.com/recap/../private/public-safe.pdf",
    ),
)
def test_plan_rejects_noncanonical_public_recap_provenance(
    tmp_path: Path,
    source_url: str,
) -> None:
    values = _inputs(tmp_path)
    source = next(
        row for row in values.manifest if row["source_document_id"] == "public-safe"
    )
    source["source_url"] = source_url
    relevance_documents = cast(
        list[dict[str, object]], values.relevance[0]["documents"]
    )
    visibility = next(
        row for row in relevance_documents if row["source_document_id"] == "public-safe"
    )
    visibility["source_url_or_reference"] = source_url

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
        document_scanner=_scanner({}),
    )

    public_safe = next(
        row for row in _documents(plan) if row["source_document_id"] == "public-safe"
    )
    assert public_safe["route"] == "john_exception_review"
    assert "affirmative_public_provenance_unproven" in _route_reasons(public_safe)


def test_incomplete_page_coverage_remains_review_routed(
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
        document_scanner=_scanner({b"marker": _incomplete_scan()}),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["automated_markers"] == [
        "extraction_page_coverage_incomplete",
        "unscannable_or_image_only",
    ]
    assert "page_scan_coverage_incomplete" in _route_reasons(marker)
    assert "automated_marker_present" in _route_reasons(marker)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_field",
        "extra_field",
        "overlapping_pages",
        "out_of_range_page",
        "unsupported_ocr_claim",
    ],
)
def test_closed_pdf_scan_schema_rejects_invalid_coverage(
    tmp_path: Path, mutation: str
) -> None:
    plan = _plan(tmp_path)
    cloned = cast(dict[str, object], json.loads(json.dumps(plan)))
    documents = cast(list[dict[str, object]], cloned["documents"])
    scan = cast(dict[str, object], documents[0]["disclosure_pdf_scan"])
    if mutation == "missing_field":
        del scan["method"]
    elif mutation == "extra_field":
        scan["unexpected"] = True
    elif mutation == "overlapping_pages":
        scan["unscanned_page_numbers"] = [1]
        scan["coverage_status"] = "incomplete"
    elif mutation == "out_of_range_page":
        scan["text_scanned_page_numbers"] = [2]
    else:
        scan["text_scanned_page_numbers"] = []
        scan["text_scanned_page_count"] = 0
        scan["ocr_scanned_page_numbers"] = [1]
        scan["ocr_scanned_page_count"] = 1

    with pytest.raises(ProvenanceClearanceError, match="PDF scan"):
        exception_review_worksheet(cloned)


def test_closed_exception_worksheet_rejects_nested_scan_drift(tmp_path: Path) -> None:
    worksheet = exception_review_worksheet(_plan(tmp_path))
    assert len(validate_exception_review_worksheet(worksheet)) == 2
    documents = cast(list[dict[str, object]], worksheet["documents"])
    scan = cast(dict[str, object], documents[0]["disclosure_pdf_scan"])
    scan["unexpected"] = True

    with pytest.raises(ProvenanceClearanceError, match="PDF scan"):
        validate_exception_review_worksheet(worksheet)


def test_scan_page_validation_error_identifies_document(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    documents = cast(list[dict[str, object]], plan["documents"])
    document = documents[0]
    key = (document["candidate_id"], document["source_document_id"])
    scan = cast(dict[str, object], document["disclosure_pdf_scan"])
    scan["text_scanned_page_numbers"] = "not-a-list"

    with pytest.raises(
        ProvenanceClearanceError,
        match=rf"text_scanned_page_numbers must be a list: {re.escape(str(key))}",
    ):
        exception_review_worksheet(plan)


def test_immutable_plan_selects_its_versioned_scanner(tmp_path: Path) -> None:
    current = _plan(tmp_path)
    assert document_scanner_for_plan(current) is scan_disclosure_document

    historical = cast(dict[str, object], json.loads(json.dumps(current)))
    historical_documents = cast(list[dict[str, object]], historical["documents"])
    for document in historical_documents:
        scan = cast(dict[str, object], document["disclosure_pdf_scan"])
        scan["schema_version"] = PDF_SCAN_SCHEMA_VERSION_V1
        scan["method"] = "pypdf_page_text_v1"
    assert document_scanner_for_plan(historical) is scan_disclosure_document_v1

    mixed = cast(dict[str, object], json.loads(json.dumps(historical)))
    mixed_documents = cast(list[dict[str, object]], mixed["documents"])
    mixed_scan = cast(dict[str, object], mixed_documents[0]["disclosure_pdf_scan"])
    mixed_scan["schema_version"] = PDF_SCAN_SCHEMA_VERSION
    mixed_scan["method"] = "pypdf_page_text_v2"
    with pytest.raises(ProvenanceClearanceError, match="mixed PDF scanner versions"):
        document_scanner_for_plan(mixed)
    with pytest.raises(ProvenanceClearanceError, match="mixed PDF scanner versions"):
        exception_review_worksheet(mixed)


def test_document_scan_cache_is_content_addressed_and_operation_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)
    result = _complete_scan()
    calls: list[bytes] = []

    def scanner(data: bytes) -> DisclosurePdfScan:
        calls.append(data)
        return result

    monkeypatch.setattr(
        "legalforecast.ingestion.provenance_clearance.scan_disclosure_document",
        scanner,
    )
    with cache_disclosure_document_scans():
        assert document_scanner_for_plan(plan)(b"same-pdf") is result
        assert document_scanner_for_plan(plan)(b"same-pdf") is result
        assert document_scanner_for_plan(plan)(b"different-pdf") is result
    assert calls == [b"same-pdf", b"different-pdf"]

    with cache_disclosure_document_scans():
        assert document_scanner_for_plan(plan)(b"same-pdf") is result
    assert calls == [b"same-pdf", b"different-pdf", b"same-pdf"]


def test_empty_plan_uses_current_scanner_and_builds_empty_worksheet(
    tmp_path: Path,
) -> None:
    plan = build_provenance_clearance_plan(
        [],
        [],
        [],
        [],
        document_root=tmp_path,
        review_requests_bytes=b"",
        download_manifest_bytes=b"",
        restriction_evidence_bytes=b"",
        case_relevance_bytes=b"",
    )

    assert document_scanner_for_plan(plan) is scan_disclosure_document
    assert exception_review_worksheet(plan)["documents"] == []


def test_builder_rejects_stateful_mixed_scanner_output(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    current = _complete_scan()
    historical = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=(),
        schema_version=PDF_SCAN_SCHEMA_VERSION_V1,
        method="pypdf_page_text_v1",
    )
    calls = 0

    def stateful_scanner(_: bytes) -> DisclosurePdfScan:
        nonlocal calls
        calls += 1
        return current if calls == 1 else historical

    with pytest.raises(ProvenanceClearanceError, match="mixed PDF scanner versions"):
        build_provenance_clearance_plan(
            inputs.requests,
            inputs.manifest,
            inputs.restrictions,
            inputs.relevance,
            document_root=inputs.document_root,
            review_requests_bytes=_jsonl(inputs.requests),
            download_manifest_bytes=_jsonl(inputs.manifest),
            restriction_evidence_bytes=_jsonl(inputs.restrictions),
            case_relevance_bytes=_jsonl(inputs.relevance),
            document_scanner=stateful_scanner,
        )


def test_closed_plan_rejects_marker_route_bypass(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    documents = cast(list[dict[str, object]], plan["documents"])
    restricted = next(
        row for row in documents if row["source_document_id"] == "restricted"
    )
    restricted["route"] = "auto_clear"
    restricted["route_reasons"] = []

    with pytest.raises(ProvenanceClearanceError, match="routing plan decision"):
        exception_review_worksheet(plan)


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
        document_scanner=_scanner({b"marker": _complete_scan(substantive_marker)}),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["automated_markers"] == [substantive_marker]
    assert "automated_marker_present" in _route_reasons(marker)
    assert marker["human_clearance_permitted"] is True


def test_complete_page_coverage_does_not_suppress_substantive_marker(
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
        document_scanner=_scanner({b"marker": _complete_scan("medical")}),
    )

    marker = next(
        row for row in _documents(plan) if row["source_document_id"] == "marker"
    )
    assert marker["route"] == "john_exception_review"
    assert marker["automated_markers"] == ["medical"]
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
        document_scanner=_scanner({}),
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
        document_scanner=_scanner({b"marker": _complete_scan()}),
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

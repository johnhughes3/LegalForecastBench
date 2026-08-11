from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from legalforecast.ingestion.disclosure_clearance import (
    PDF_SCAN_SCHEMA_VERSION,
    PDF_SCAN_SCHEMA_VERSION_V1,
    ClearedDocumentEvidence,
    DisclosureClearanceError,
    ReviewAuthority,
    build_clearance_records,
    ranked_replacement,
    require_cleared_artifact_keys,
    require_cleared_documents,
    require_cleared_parse_requests,
    require_cleared_parser_records,
    scan_disclosure_document,
    scan_disclosure_document_v1,
)
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject
from reportlab.pdfgen.canvas import Canvas


def _document(tmp_path: Path, content: bytes) -> dict[str, object]:
    path = tmp_path / "cand-1" / "doc-1.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "local_path": "cand-1/doc-1.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_count": len(content),
        "free_or_purchased": "free",
    }


def _review(
    document: dict[str, object], *, status: str = "cleared"
) -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "sha256": document["sha256"],
        "status": status,
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle1/reviews/batch-001",
        "reviewed_at": "2026-07-12T18:00:00Z",
    }


def _public_evidence() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "restriction_status": "public",
        "restriction_evidence": "courtlistener-public-docket",
    }


def _authority() -> ReviewAuthority:
    return ReviewAuthority(
        reviewer_id="reviewer:john",
        controlled_store_uri="private-store://cycle1/reviews/batch-001",
        authentication_method="human_hardware_ssh_signature",
        authenticated_at="2026-07-12T18:00:00Z",
        review_artifact_sha256="0" * 64,
        reviewer_policy_sha256="1" * 64,
    )


def test_ssn_bearing_document_is_quarantined_without_review(tmp_path: Path) -> None:
    document = _document(tmp_path, _text_pdf(b"Client SSN 123-45-6789"))
    [record] = build_clearance_records([document], document_root=tmp_path, reviews=[])
    assert record.status == "quarantined"
    assert "ssn" in record.automated_markers


def test_image_only_pdf_is_quarantined(tmp_path: Path) -> None:
    document = _document(tmp_path, b"%PDF-1.7\n/Type /Image\nstream\x00\x01endstream")
    [record] = build_clearance_records([document], document_root=tmp_path, reviews=[])
    assert "unscannable_or_image_only" in record.automated_markers
    assert record.status == "quarantined"


def test_page_scanner_records_complete_and_incomplete_page_text_coverage() -> None:
    complete = scan_disclosure_document(
        _multipage_pdf(("Motion memorandum", "Opposition memorandum"))
    )
    assert complete.parsed_page_count == 2
    assert complete.text_scanned_page_numbers == (1, 2)
    assert complete.unscanned_page_numbers == ()
    assert complete.coverage_status == "complete"
    assert complete.automated_markers == ()
    partial = scan_disclosure_document(_multipage_pdf(("Motion memorandum", "")))
    assert partial.text_scanned_page_numbers == (1,)
    assert partial.unscanned_page_numbers == (2,)
    assert partial.coverage_status == "incomplete"
    assert "extraction_page_coverage_incomplete" in partial.automated_markers
    assert "unscannable_or_image_only" in partial.automated_markers


def test_page_scanner_covers_every_page_when_one_page_has_multiple_streams() -> None:
    scan = scan_disclosure_document(_multi_stream_pdf("Motion memorandum"))

    assert scan.parsed_page_count == 1
    assert scan.text_scanned_page_numbers == (1,)
    assert scan.unscanned_page_numbers == ()
    assert scan.coverage_status == "complete"
    assert scan.automated_markers == ()


def test_page_scanner_does_not_repeat_legacy_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_legacy_extraction(_data: bytes) -> object:
        raise AssertionError("legacy extractor must not run")

    monkeypatch.setattr(
        "legalforecast.ingestion.disclosure_clearance."
        "extract_pdf_text_with_ocr_fallback",
        unexpected_legacy_extraction,
    )

    scan = scan_disclosure_document(_multipage_pdf(("Motion memorandum",)))

    assert scan.coverage_status == "complete"
    assert scan.automated_markers == ()


def test_v1_scanner_replays_legacy_diagnostics_without_affecting_v2() -> None:
    data = _multi_stream_pdf("Motion memorandum")

    historical = scan_disclosure_document_v1(data)
    current = scan_disclosure_document(data)

    assert historical.schema_version == PDF_SCAN_SCHEMA_VERSION_V1
    assert historical.method == "pypdf_page_text_v1"
    assert "legacy_extraction_page_count_mismatch" in historical.diagnostics
    assert current.schema_version == PDF_SCAN_SCHEMA_VERSION
    assert current.method == "pypdf_page_text_v2"
    assert not any(
        value.startswith("legacy_extraction_") for value in current.diagnostics
    )
    assert historical.automated_markers == current.automated_markers == ()


def test_page_scanner_fails_closed_on_encrypted_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EncryptedReader:
        is_encrypted = True

        @property
        def pages(self) -> object:
            raise AssertionError("encrypted pages must not be read")

    monkeypatch.setattr(
        "legalforecast.ingestion.disclosure_clearance.PdfReader",
        lambda *_args, **_kwargs: EncryptedReader(),
    )

    scan = scan_disclosure_document(b"encrypted")

    assert scan.parsed_page_count == 0
    assert scan.text_scanned_page_numbers == ()
    assert scan.unscanned_page_numbers == ()
    assert scan.coverage_status == "incomplete"
    assert "pdf_encrypted" in scan.diagnostics
    assert "extraction_page_coverage_incomplete" in scan.automated_markers


def test_page_scanner_fails_closed_on_per_page_extraction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TextPage:
        @staticmethod
        def extract_text() -> str:
            return "Motion memorandum"

    class BrokenPage:
        @staticmethod
        def extract_text() -> str:
            raise ValueError("synthetic page failure")

    class PartialReader:
        is_encrypted = False
        pages = (TextPage(), BrokenPage())

    monkeypatch.setattr(
        "legalforecast.ingestion.disclosure_clearance.PdfReader",
        lambda *_args, **_kwargs: PartialReader(),
    )

    scan = scan_disclosure_document(b"partial")

    assert scan.parsed_page_count == 2
    assert scan.text_scanned_page_numbers == (1,)
    assert scan.unscanned_page_numbers == (2,)
    assert scan.coverage_status == "incomplete"
    assert "page_text_extraction_failed:2" in scan.diagnostics
    assert "extraction_page_coverage_incomplete" in scan.automated_markers


def test_page_scanner_fails_closed_on_parser_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenReader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise ValueError("synthetic parser failure")

    monkeypatch.setattr(
        "legalforecast.ingestion.disclosure_clearance.PdfReader", BrokenReader
    )
    scan = scan_disclosure_document(_multipage_pdf(("Motion memorandum",)))

    assert scan.coverage_status == "incomplete"
    assert scan.parsed_page_count == 0
    assert "pdf_parse_failed" in scan.diagnostics
    assert "extraction_page_coverage_incomplete" in scan.automated_markers


def test_substantive_marker_on_later_page_forces_review_marker() -> None:
    scan = scan_disclosure_document(
        _multipage_pdf(("Motion memorandum", "The medical record is attached."))
    )

    assert scan.coverage_status == "complete"
    assert scan.text_scanned_page_numbers == (1, 2)
    assert scan.automated_markers == ("medical",)


def test_substantive_marker_cannot_span_pdf_page_boundary() -> None:
    scan = scan_disclosure_document(
        _multipage_pdf(("The date of birth:", "01/01/1990"))
    )

    assert scan.coverage_status == "complete"
    assert scan.text_scanned_page_numbers == (1, 2)
    assert scan.automated_markers == ()


@pytest.mark.parametrize(
    ("marker", "whole_page_text", "split_pages"),
    (
        (
            "dob",
            "The date of birth: 01/01/1990",
            ("The date", "of", "birth: 01/01/1990"),
        ),
        (
            "minor",
            "The child identified as A.B.",
            ("The child", "identified as A.B."),
        ),
        (
            "medical",
            "The medical record is attached.",
            ("The medical", "record is attached."),
        ),
    ),
)
def test_substantive_markers_do_not_combine_across_page_boundaries(
    marker: str,
    whole_page_text: str,
    split_pages: tuple[str, ...],
) -> None:
    whole_page = scan_disclosure_document(_multipage_pdf((whole_page_text,)))
    split = scan_disclosure_document(_multipage_pdf(split_pages))

    assert whole_page.automated_markers == (marker,)
    assert split.coverage_status == "complete"
    assert split.text_scanned_page_numbers == tuple(range(1, len(split_pages) + 1))
    assert split.automated_markers == ()


def test_sealed_evidence_fails_closed_and_cleared_hash_is_recorded(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    [quarantined] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[],
        restriction_records=[
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "is_sealed": True,
            }
        ],
    )
    assert quarantined.status == "quarantined"
    assert "field_issealed" in quarantined.automated_markers

    [cleared] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    assert cleared.status == "cleared"
    assert cleared.reviewer_id == "reviewer:john"
    assert cleared.sha256 == document["sha256"]


@pytest.mark.parametrize("malformed_value", ("true", "false", 1, 0))
def test_malformed_restriction_flags_cannot_be_cleared_as_public(
    tmp_path: Path,
    malformed_value: object,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    public = _public_evidence()
    public["is_sealed"] = malformed_value

    [record] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[public],
    )

    assert record.status == "quarantined"
    assert "field_issealed_malformed" in record.automated_markers


def test_null_restriction_flag_does_not_override_independent_public_evidence(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    public = _public_evidence()
    public["is_sealed"] = None

    [record] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[public],
    )

    assert record.status == "cleared"
    assert "field_issealed" not in record.automated_markers


def test_parse_gate_rejects_uncleared_and_tampered_documents(tmp_path: Path) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    with pytest.raises(DisclosureClearanceError, match="coverage mismatch"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[]
        )
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    (tmp_path / str(document["local_path"])).write_bytes(b"tampered")
    with pytest.raises(DisclosureClearanceError, match=r"hash mismatch|bytes changed"):
        require_cleared_documents(
            [document],
            document_root=tmp_path,
            clearance_records=[clearance.to_record()],
        )
    parser_record = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "source_sha256": clearance.sha256,
        "source_byte_count": clearance.byte_count + 1,
    }
    with pytest.raises(DisclosureClearanceError, match="byte-count mismatch"):
        require_cleared_parser_records([parser_record], [clearance.to_record()])


def test_clearance_returns_invocation_scoped_exact_file_evidence(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )

    clearance_record = clearance.to_record()
    [evidence] = require_cleared_documents(
        [document],
        document_root=tmp_path,
        clearance_records=[clearance_record],
    )

    path = tmp_path / str(document["local_path"])
    metadata = path.stat()
    assert isinstance(evidence, ClearedDocumentEvidence)
    assert evidence.canonical_path == path.resolve()
    assert (evidence.device, evidence.inode) == (metadata.st_dev, metadata.st_ino)
    assert evidence.byte_count == len(path.read_bytes())
    assert evidence.sha256 == document["sha256"]
    assert dict(evidence.authenticated_clearance) == clearance.to_record()

    clearance_record["restriction_evidence"].append("later-mutation")  # type: ignore[attr-defined]
    assert (
        "later-mutation" not in evidence.authenticated_clearance["restriction_evidence"]
    )


def test_unknown_restriction_and_missing_review_timestamp_fail_closed(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    review = _review(document)
    with pytest.raises(DisclosureClearanceError, match="verified controlled-store"):
        build_clearance_records(
            [document],
            document_root=tmp_path,
            reviews=[review],
            restriction_records=[_public_evidence()],
        )
    [unknown] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[review],
        review_authority=_authority(),
    )
    assert unknown.status == "quarantined"
    assert "restriction_status_unknown" in unknown.automated_markers

    missing_timestamp = _review(document)
    missing_timestamp.pop("reviewed_at")
    with pytest.raises(DisclosureClearanceError, match="requires reviewed_at"):
        build_clearance_records(
            [document],
            document_root=tmp_path,
            reviews=[missing_timestamp],
            review_authority=_authority(),
            restriction_records=[_public_evidence()],
        )


@pytest.mark.parametrize("evidence", [None, "", [], [" "]])
def test_clearance_gates_reject_public_status_without_restriction_evidence(
    tmp_path: Path, evidence: object
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    forged = clearance.to_record()
    forged["restriction_evidence"] = evidence
    with pytest.raises(DisclosureClearanceError, match="restriction evidence"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[forged]
        )
    request = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "expected_sha256": clearance.sha256,
        "expected_byte_count": clearance.byte_count,
    }
    with pytest.raises(DisclosureClearanceError, match="restriction evidence"):
        require_cleared_parse_requests([request], [forged])


@pytest.mark.parametrize("provenance", [None, "", "https://example.com/review"])
def test_clearance_gates_reject_missing_or_foreign_store_provenance(
    tmp_path: Path, provenance: object
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    forged = clearance.to_record()
    forged["controlled_store_provenance"] = provenance
    with pytest.raises(DisclosureClearanceError, match=r"provenance|private store"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[forged]
        )
    parser_record = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "source_sha256": clearance.sha256,
        "source_byte_count": clearance.byte_count,
    }
    with pytest.raises(DisclosureClearanceError, match=r"provenance|private store"):
        require_cleared_parser_records([parser_record], [forged])


def test_ranked_replacement_uses_next_cheapest_under_same_cap() -> None:
    frontier = [
        {
            "candidate_id": "a",
            "missing_required_document_count": 0,
            "projected_paid_cost_usd": "0.00",
        },
        {
            "candidate_id": "b",
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "3.05",
        },
        {
            "candidate_id": "c",
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "3.05",
        },
        {
            "candidate_id": "d",
            "missing_required_document_count": 2,
            "projected_paid_cost_usd": "6.10",
        },
    ]
    selected = ranked_replacement(
        frontier,
        quarantined_candidate_id="b",
        already_selected_candidate_ids=("a",),
        spent_or_reserved_usd="3.05",
        max_projected_cost_usd="9.15",
    )
    assert selected.replacement_candidate_id == "c"
    assert selected.write_off_cost_usd == "3.05"


def test_model_reviewed_marker_document_accepts_exact_direct_public_provenance(
    tmp_path: Path,
) -> None:
    content = _text_pdf(b"public marker-only filing")
    document = _document(tmp_path, content)
    clearance = {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        **document,
        "status": "cleared",
        "automated_markers": ["minor"],
        "restriction_status": "unknown",
        "restriction_evidence": [
            "courtlistener_rest_docket_entry_exact_match",
            "courtlistener_rest_docket_exact_match",
            "courtlistener_rest_public_download_url_allowlisted",
            "courtlistener_rest_recap_document_exact_match",
            "courtlistener_rest_recap_document_is_available_true",
            "courtlistener_rest_recap_document_is_sealed_unknown",
        ],
        "reviewer_id": "google:gemini-3.5-flash",
        "controlled_store_provenance": "private-store://disclosure/model-review",
        "reviewed_at": None,
        "clearance_basis": "authenticated_model_exception_review",
        "routing_plan_sha256": "a" * 64,
    }

    require_cleared_documents(
        [document], document_root=tmp_path, clearance_records=[clearance]
    )

    for field, value in (
        ("restriction_status", "private"),
        (
            "restriction_evidence",
            [
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_public_download_url_allowlisted",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_true",
                "courtlistener_rest_recap_document_is_sealed_true",
            ],
        ),
        (
            "restriction_evidence",
            [
                "courtlistener_rest_docket_entry_exact_match",
                ["courtlistener_rest_docket_exact_match"],
            ],
        ),
    ):
        changed = {**clearance, field: value}
        with pytest.raises(DisclosureClearanceError, match="restriction is not public"):
            require_cleared_documents(
                [document], document_root=tmp_path, clearance_records=[changed]
            )


def test_mixed_provenance_clearance_reaches_every_downstream_gate(
    tmp_path: Path,
) -> None:
    documents: list[dict[str, object]] = []
    clearances: list[dict[str, object]] = []
    routing_sha256 = "a" * 64
    cases = (
        (
            "public-auto",
            "public",
            ["courtlistener_public_download_record_checked"],
            "affirmative_public_provenance",
        ),
        (
            "rest-auto",
            "unknown",
            [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_true",
                "courtlistener_rest_recap_document_is_sealed_unknown",
                "courtlistener_rest_public_download_url_allowlisted",
            ],
            "affirmative_public_provenance",
        ),
        (
            "john-exception",
            "unknown",
            [],
            "john_exception_review",
        ),
    )
    for candidate_id, restriction_status, evidence, basis in cases:
        content = _text_pdf(candidate_id.encode())
        relative_path = f"{candidate_id}/doc.pdf"
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        documents.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": "doc",
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": len(content),
                "free_or_purchased": "free",
            }
        )
        automatic = basis == "affirmative_public_provenance"
        clearances.append(
            {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": candidate_id,
                "source_document_id": "doc",
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": len(content),
                "status": "cleared",
                "automated_markers": [],
                "restriction_status": restriction_status,
                "restriction_evidence": evidence,
                "reviewer_id": None if automatic else "John Hughes",
                "controlled_store_provenance": (
                    "https://storage.courtlistener.com/recap/example.pdf"
                    if automatic
                    else "private-store://john/disclosure-exception-review"
                ),
                "reviewed_at": None if automatic else "2026-07-25T00:00:00Z",
                "free_or_purchased": "free",
                "clearance_basis": basis,
                "routing_plan_sha256": routing_sha256,
            }
        )

    require_cleared_documents(
        documents, document_root=tmp_path, clearance_records=clearances
    )
    parse_requests = [
        {
            "candidate_id": row["candidate_id"],
            "source_document_id": "doc",
            "expected_sha256": row["sha256"],
            "expected_byte_count": row["byte_count"],
        }
        for row in documents
    ]
    require_cleared_parse_requests(parse_requests, clearances)
    parser_records = [
        {
            "candidate_id": row["candidate_id"],
            "source_document_id": "doc",
            "source_sha256": row["sha256"],
            "source_byte_count": row["byte_count"],
        }
        for row in documents
    ]
    require_cleared_parser_records(parser_records, clearances)
    require_cleared_artifact_keys(
        [(str(row["candidate_id"]), "doc") for row in documents], clearances
    )

    for invalid_public_provenance in (
        "https://example.com/recap.pdf",
        "https://storage.courtlistener.com:443/recap/example.pdf",
        "https://storage.courtlistener.com:invalid/recap/example.pdf",
        "https://storage.courtlistener.com/recap/../private/example.pdf",
    ):
        forged = dict(clearances[0])
        forged["controlled_store_provenance"] = invalid_public_provenance
        with pytest.raises(DisclosureClearanceError, match="allowlisted public"):
            require_cleared_documents(
                documents,
                document_root=tmp_path,
                clearance_records=[forged, *clearances[1:]],
            )

    for invalid_private_provenance in (
        "private-store://",
        "private-store://user@john/disclosure-exception-review",
        "private-store://john:8443/disclosure-exception-review",
        "private-store://john/reviews/../disclosure-exception-review",
    ):
        forged_exception = dict(clearances[2])
        forged_exception["controlled_store_provenance"] = invalid_private_provenance
        with pytest.raises(DisclosureClearanceError, match="controlled private store"):
            require_cleared_documents(
                documents,
                document_root=tmp_path,
                clearance_records=[*clearances[:2], forged_exception],
            )

    for field, value in (
        ("restriction_status", "sealed"),
        ("restriction_status", "under seal"),
        ("restriction_evidence", ["courtlistener_is_sealed_true"]),
        ("restriction_evidence", ["courtlistener is sealed true"]),
    ):
        forged_exception = dict(clearances[2])
        forged_exception[field] = value
        with pytest.raises(
            DisclosureClearanceError, match="positive restriction evidence"
        ):
            require_cleared_documents(
                documents,
                document_root=tmp_path,
                clearance_records=[*clearances[:2], forged_exception],
            )
        with pytest.raises(
            DisclosureClearanceError, match="positive restriction evidence"
        ):
            require_cleared_parser_records(
                parser_records, [*clearances[:2], forged_exception]
            )


def test_clearance_rejects_symlinked_document_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    document = _document(real_root, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=real_root,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)
    with pytest.raises(DisclosureClearanceError, match=r"document_root.*symlink"):
        require_cleared_documents(
            [document],
            document_root=linked_root,
            clearance_records=[clearance.to_record()],
        )


def _text_pdf(text: bytes) -> bytes:
    return b"%PDF-1.4\n/Type /Page\n<< >>\nstream\nBT (" + text + b") Tj ET\nendstream"


def _multipage_pdf(page_texts: tuple[str, ...]) -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    for text in page_texts:
        if text:
            canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def _multi_stream_pdf(text: str) -> bytes:
    reader = PdfReader(BytesIO(_multipage_pdf((text,))))
    page = reader.pages[0]
    contents = page.raw_get("/Contents")
    page[NameObject("/Contents")] = ArrayObject([contents, contents])
    writer = PdfWriter()
    writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

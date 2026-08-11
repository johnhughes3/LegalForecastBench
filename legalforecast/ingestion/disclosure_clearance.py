"""Fail-closed, hash-bound disclosure clearance for acquired documents."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from types import MappingProxyType
from typing import cast

from pypdf import PdfReader

from legalforecast.extraction.pdf_text import (
    PDFExtractionError,
    extract_pdf_text_with_ocr_fallback,
)
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthority,
)
from legalforecast.ingestion.disclosure_uri import (
    is_allowlisted_public_recap_uri,
    is_canonical_private_store_uri,
)
from legalforecast.ingestion.restricted_material import restricted_material_markers

SCHEMA_VERSION = "legalforecast.disclosure_clearance.v1"
REVIEW_RECEIPT_SCHEMA_VERSION = "legalforecast.disclosure_review_receipt.v2"
PDF_SCAN_SCHEMA_VERSION_V1 = "legalforecast.disclosure_pdf_scan.v1"
PDF_SCAN_SCHEMA_VERSION = "legalforecast.disclosure_pdf_scan.v2"
_CLEAR = "cleared"
_QUARANTINED = "quarantined"
_RESTRICTED_STATUSES = frozenset({"private", "restricted", "sealed", "under_seal"})
_PUBLIC_STATUSES = frozenset({"public", "redacted"})
_PROVENANCE_PUBLIC_EVIDENCE = frozenset(
    {"courtlistener_public_download_record_checked"}
)
_PROVENANCE_REST_PUBLIC_EVIDENCE = frozenset(
    {
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    }
)
_POSITIVE_RESTRICTION_EVIDENCE = re.compile(
    r"(?:^|_)(?:sealed|private|restricted|under_seal)(?:_true|$)"
)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_DOB = re.compile(
    r"\b(?:date\s+of\s+birth|d\.o\.b\.|dob)\s*[:\-]?\s*"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
_MINOR = re.compile(
    r"\b(?:minor(?:'s)?\s+(?:name|child)|juvenile|child\s+identified\s+as)\b",
    re.IGNORECASE,
)
_MEDICAL = re.compile(
    r"\b(?:medical\s+record|diagnos(?:is|ed)|patient\s+history)\b",
    re.IGNORECASE,
)


class DisclosureClearanceError(ValueError):
    """Raised when clearance evidence is missing, inconsistent, or unsafe."""


@dataclass(frozen=True, slots=True)
class ClearedDocumentEvidence:
    """Invocation-scoped exact-file evidence from clearance verification.

    This is deliberately not serializable: it is valid only for the caller
    which performed the authenticated clearance recheck.
    """

    candidate_id: str
    source_document_id: str
    canonical_path: Path
    device: int
    inode: int
    byte_count: int
    sha256: str
    authenticated_clearance: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DisclosurePdfPage:
    """Nonempty text extracted from one page of an exact PDF byte string."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class DisclosurePdfPageExtraction:
    """Closed page-text extraction result over one exact PDF byte string."""

    parsed_page_count: int
    pages: tuple[DisclosurePdfPage, ...]
    unscanned_page_numbers: tuple[int, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DisclosurePdfScan:
    """Closed page-coverage evidence derived from one exact PDF byte string."""

    parsed_page_count: int
    text_scanned_page_numbers: tuple[int, ...]
    ocr_scanned_page_numbers: tuple[int, ...]
    unscanned_page_numbers: tuple[int, ...]
    coverage_status: str
    diagnostics: tuple[str, ...]
    automated_markers: tuple[str, ...]
    schema_version: str = PDF_SCAN_SCHEMA_VERSION
    method: str = "pypdf_page_text_v2"

    def to_record(self) -> dict[str, object]:
        """Return the closed JSON representation embedded in routing plans."""

        return {
            "schema_version": self.schema_version,
            "method": self.method,
            "parsed_page_count": self.parsed_page_count,
            "text_scanned_page_numbers": list(self.text_scanned_page_numbers),
            "text_scanned_page_count": len(self.text_scanned_page_numbers),
            "ocr_scanned_page_numbers": list(self.ocr_scanned_page_numbers),
            "ocr_scanned_page_count": len(self.ocr_scanned_page_numbers),
            "unscanned_page_numbers": list(self.unscanned_page_numbers),
            "coverage_status": self.coverage_status,
            "diagnostics": list(self.diagnostics),
            "automated_markers": list(self.automated_markers),
        }


@dataclass(frozen=True, slots=True)
class ClearanceRecord:
    """One terminal, hash-bound disclosure decision."""

    candidate_id: str
    source_document_id: str
    local_path: str
    sha256: str
    byte_count: int
    status: str
    automated_markers: tuple[str, ...]
    restriction_status: str
    restriction_evidence: tuple[str, ...]
    reviewer_id: str | None
    controlled_store_provenance: str | None
    reviewed_at: str | None
    free_or_purchased: str
    clearance_basis: str = "legacy_authenticated_review"
    routing_plan_sha256: str | None = None
    recovered_public_lineage: Mapping[str, object] | None = None

    def to_record(self) -> dict[str, object]:
        """Return the stable artifact row without sensitive matched values."""

        record: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "local_path": self.local_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "status": self.status,
            "automated_markers": list(self.automated_markers),
            "restriction_status": self.restriction_status,
            "restriction_evidence": list(self.restriction_evidence),
            "reviewer_id": self.reviewer_id,
            "controlled_store_provenance": self.controlled_store_provenance,
            "reviewed_at": self.reviewed_at,
            "free_or_purchased": self.free_or_purchased,
        }
        if self.clearance_basis != "legacy_authenticated_review":
            record["clearance_basis"] = self.clearance_basis
            record["routing_plan_sha256"] = self.routing_plan_sha256
        if self.recovered_public_lineage is not None:
            record["recovered_public_lineage"] = dict(self.recovered_public_lineage)
        return record


@dataclass(frozen=True, slots=True)
class ReplacementDecision:
    """Ledger evidence for one quarantined candidate replacement."""

    quarantined_candidate_id: str
    replacement_candidate_id: str | None
    replacement_rank: int | None
    write_off_cost_usd: str
    replacement_cost_usd: str | None
    reason: str

    def to_record(self) -> dict[str, object]:
        """Return a stable replacement-ledger row."""

        return {
            "quarantined_candidate_id": self.quarantined_candidate_id,
            "replacement_candidate_id": self.replacement_candidate_id,
            "replacement_rank": self.replacement_rank,
            "write_off_cost_usd": self.write_off_cost_usd,
            "replacement_cost_usd": self.replacement_cost_usd,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReviewAuthority:
    """Verified controlled-store receipt for the human review artifact."""

    reviewer_id: str
    controlled_store_uri: str
    authentication_method: str
    authenticated_at: str
    review_artifact_sha256: str
    reviewer_policy_sha256: str


def validate_review_receipt(
    review_artifact: bytes,
    receipt: Mapping[str, object],
    *,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    worksheet_bytes: bytes,
    worksheet: Mapping[str, object],
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> ReviewAuthority:
    """Verify signed reviewer authority and every exact input-lineage byte stream."""

    from legalforecast.ingestion.disclosure_review_bundle import (
        ReviewBundleError,
        verify_review_receipt,
    )

    try:
        verified = verify_review_receipt(
            review_artifact,
            receipt,
            reviewer_policy_bytes=reviewer_policy_bytes,
            disclosure_authority=disclosure_authority,
            worksheet_bytes=worksheet_bytes,
            worksheet=worksheet,
            review_requests_bytes=review_requests_bytes,
            download_manifest_bytes=download_manifest_bytes,
            restriction_evidence_bytes=restriction_evidence_bytes,
            allow_test_service_identity=allow_test_service_identity,
        )
    except ReviewBundleError as exc:
        raise DisclosureClearanceError(str(exc)) from exc
    return ReviewAuthority(
        reviewer_id=verified.reviewer_id,
        controlled_store_uri=verified.controlled_store_uri,
        authentication_method=verified.authentication_method,
        authenticated_at=verified.authenticated_at,
        review_artifact_sha256=verified.review_artifact_sha256,
        reviewer_policy_sha256=verified.reviewer_policy_sha256,
    )


def build_clearance_records(
    documents: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    reviews: Sequence[Mapping[str, object]],
    review_authority: ReviewAuthority | None = None,
    restriction_records: Sequence[Mapping[str, object]] = (),
) -> tuple[ClearanceRecord, ...]:
    """Scan every manifest document and apply controlled human decisions."""

    review_index = _unique_index(reviews, "review")
    restriction_index = _restriction_index(restriction_records)
    output: list[ClearanceRecord] = []
    seen: set[tuple[str, str]] = set()
    for document in documents:
        key = _document_key(document)
        if key in seen:
            raise DisclosureClearanceError(f"duplicate document manifest key: {key}")
        seen.add(key)
        path = _safe_document_path(document_root, _required_str(document, "local_path"))
        data = _read_document(path, key)
        digest = hashlib.sha256(data).hexdigest()
        _verify_manifest_commitments(
            document, digest=digest, byte_count=len(data), key=key
        )

        review = review_index.get(key)
        # Reviewer decisions authorize disclosure but cannot manufacture the
        # underlying docket-derived public/seal status.
        evidence = restriction_index.get(key, ())
        restriction_status, restriction_evidence, restriction_markers = (
            _restriction_classification(evidence)
        )
        markers = set(_scan_pdf(data))
        markers.update(restriction_markers)
        if restriction_status == "unknown":
            markers.add("restriction_status_unknown")

        reviewer_id: str | None = None
        provenance: str | None = None
        reviewed_at: str | None = None
        requested_status = _QUARANTINED
        if review is not None:
            if review_authority is None:
                raise DisclosureClearanceError(
                    f"review lacks a verified controlled-store receipt: {key}"
                )
            _verify_review_hash(review, digest=digest, key=key)
            requested_status = _required_str(review, "status")
            if requested_status not in {_CLEAR, _QUARANTINED}:
                raise DisclosureClearanceError(f"invalid review status: {key}")
            reviewer_id = _optional_str(review, "reviewer_id")
            provenance = _optional_str(review, "controlled_store_provenance")
            reviewed_at = _optional_str(review, "reviewed_at")
            if reviewer_id is None or provenance is None:
                raise DisclosureClearanceError(
                    f"review requires authenticated identity and provenance: {key}"
                )
            if reviewer_id != review_authority.reviewer_id:
                raise DisclosureClearanceError(
                    f"reviewer identity does not match authenticated receipt: {key}"
                )
            if provenance != review_authority.controlled_store_uri:
                raise DisclosureClearanceError(
                    f"review provenance does not match controlled-store receipt: {key}"
                )
            if reviewed_at is None:
                raise DisclosureClearanceError(f"review requires reviewed_at: {key}")

        # Automated sensitive/restriction findings are not self-overridable. A
        # later controlled legal-review workflow can issue a new artifact version.
        status = _CLEAR if requested_status == _CLEAR and not markers else _QUARANTINED
        output.append(
            ClearanceRecord(
                candidate_id=key[0],
                source_document_id=key[1],
                local_path=path.relative_to(document_root.resolve()).as_posix(),
                sha256=digest,
                byte_count=len(data),
                status=status,
                automated_markers=tuple(sorted(markers)),
                restriction_status=restriction_status,
                restriction_evidence=restriction_evidence,
                reviewer_id=reviewer_id,
                controlled_store_provenance=provenance,
                reviewed_at=reviewed_at,
                free_or_purchased=_required_phase(document),
            )
        )
    return tuple(output)


def require_cleared_documents(
    documents: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    clearance_records: Sequence[Mapping[str, object]],
) -> tuple[ClearedDocumentEvidence, ...]:
    """Require exact artifact coverage and return invocation-scoped file evidence."""

    index = _unique_index(clearance_records, "clearance")
    document_keys = {_document_key(document) for document in documents}
    if set(index) != document_keys:
        missing = sorted(document_keys - set(index))
        extra = sorted(set(index) - document_keys)
        raise DisclosureClearanceError(
            f"clearance coverage mismatch; missing={missing}; extra={extra}"
        )
    evidence: list[ClearedDocumentEvidence] = []
    for document in documents:
        key = _document_key(document)
        clearance = index[key]
        if clearance.get("schema_version") != SCHEMA_VERSION:
            raise DisclosureClearanceError(f"unsupported clearance schema: {key}")
        if clearance.get("status") != _CLEAR:
            raise DisclosureClearanceError(f"document lacks clearance: {key}")
        require_clearance_policy(clearance, key=key, label="document")
        path = _safe_document_path(document_root, _required_str(document, "local_path"))
        data, device, inode = _read_document_with_identity(path, key)
        digest = hashlib.sha256(data).hexdigest()
        _verify_manifest_commitments(
            document, digest=digest, byte_count=len(data), key=key
        )
        if digest != _digest(clearance, "sha256"):
            raise DisclosureClearanceError(f"cleared document bytes changed: {key}")
        if len(data) != _positive_int(clearance, "byte_count"):
            raise DisclosureClearanceError(
                f"cleared document byte count changed: {key}"
            )
        evidence.append(
            ClearedDocumentEvidence(
                candidate_id=key[0],
                source_document_id=key[1],
                canonical_path=path,
                device=device,
                inode=inode,
                byte_count=len(data),
                sha256=digest,
                authenticated_clearance=MappingProxyType(deepcopy(dict(clearance))),
            )
        )
    return tuple(evidence)


def verify_parse_request_bytes(request: Mapping[str, object]) -> None:
    """Close the plan-to-parser TOCTOU gap immediately before parser spawn."""

    key = _document_key(request)
    path = Path(_required_str(request, "input_path"))
    if not path.is_file() or path.is_symlink():
        raise DisclosureClearanceError(f"parse input is not a regular file: {key}")
    data = _read_document(path, key)
    if hashlib.sha256(data).hexdigest() != _digest(request, "expected_sha256"):
        raise DisclosureClearanceError(
            f"parse input bytes changed after planning: {key}"
        )
    if len(data) != _positive_int(request, "expected_byte_count"):
        raise DisclosureClearanceError(
            f"parse input byte count changed after planning: {key}"
        )


def require_cleared_parse_requests(
    requests: Sequence[Mapping[str, object]],
    clearance_records: Sequence[Mapping[str, object]],
) -> None:
    """Independently bind parser requests to the reviewed clearance artifact."""

    index = _validated_clearance_index(clearance_records)
    request_keys = {_document_key(request) for request in requests}
    if set(index) != request_keys:
        raise DisclosureClearanceError(
            "clearance artifact does not exactly cover parse requests"
        )
    for request in requests:
        key = _document_key(request)
        row = index[key]
        if _digest(request, "expected_sha256") != _digest(row, "sha256"):
            raise DisclosureClearanceError(
                f"parse request clearance hash mismatch: {key}"
            )
        if _positive_int(request, "expected_byte_count") != _positive_int(
            row, "byte_count"
        ):
            raise DisclosureClearanceError(
                f"parse request clearance byte-count mismatch: {key}"
            )


def require_cleared_parser_records(
    parser_records: Sequence[Mapping[str, object]],
    clearance_records: Sequence[Mapping[str, object]],
) -> None:
    """Require finalized parser artifacts to remain hash-bound to clearance."""

    index = _validated_clearance_index(clearance_records)
    parser_keys = {_document_key(record) for record in parser_records}
    if set(index) != parser_keys:
        raise DisclosureClearanceError(
            "clearance artifact does not exactly cover parser documents"
        )
    for record in parser_records:
        key = _document_key(record)
        if _digest(record, "source_sha256") != _digest(index[key], "sha256"):
            raise DisclosureClearanceError(
                f"parser artifact clearance hash mismatch: {key}"
            )
        if _positive_int(record, "source_byte_count") != _positive_int(
            index[key], "byte_count"
        ):
            raise DisclosureClearanceError(
                f"parser artifact clearance byte-count mismatch: {key}"
            )


def require_cleared_artifact_keys(
    required_keys: Iterable[tuple[str, str]],
    clearance_records: Sequence[Mapping[str, object]],
) -> None:
    """Validate terminal clearance coverage when source bytes are not an input."""

    required = set(required_keys)
    index = _validated_clearance_index(clearance_records)
    if set(index) != required:
        raise DisclosureClearanceError(
            "clearance artifact does not exactly cover parser documents"
        )


def _validated_clearance_index(
    clearance_records: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    index = _unique_index(clearance_records, "clearance")
    for key, row in index.items():
        if row.get("schema_version") != SCHEMA_VERSION or row.get("status") != _CLEAR:
            raise DisclosureClearanceError(
                f"parser document lacks terminal clearance: {key}"
            )
        _digest(row, "sha256")
        _positive_int(row, "byte_count")
        require_clearance_policy(row, key=key, label="parser document")
    return index


def require_clearance_policy(
    row: Mapping[str, object], *, key: tuple[str, str], label: str
) -> None:
    """Validate one clearance row under the canonical downstream policy."""

    _require_clearance_restriction(row, key=key, label=label)
    _require_clearance_provenance(row, key=key)


def _require_public_restriction(
    row: Mapping[str, object], *, key: tuple[str, str], label: str
) -> None:
    if _required_str(row, "restriction_status") not in _PUBLIC_STATUSES:
        raise DisclosureClearanceError(f"{label} restriction is not public: {key}")
    evidence = row.get("restriction_evidence")
    if isinstance(evidence, str):
        has_evidence = bool(evidence.strip())
    elif isinstance(evidence, (list, tuple)):
        has_evidence = any(
            isinstance(item, str) and bool(item.strip())
            for item in cast("Sequence[object]", evidence)
        )
    else:
        has_evidence = False
    if not has_evidence:
        raise DisclosureClearanceError(f"{label} lacks restriction evidence: {key}")


def _require_clearance_restriction(
    row: Mapping[str, object], *, key: tuple[str, str], label: str
) -> None:
    basis = row.get("clearance_basis")
    if basis == "john_exception_review":
        status = _required_str(row, "restriction_status")
        evidence_value = row.get("restriction_evidence")
        if not isinstance(evidence_value, (list, tuple)) or not all(
            isinstance(item, str) and bool(item.strip())
            for item in cast(Sequence[object], evidence_value)
        ):
            raise DisclosureClearanceError(
                f"John-reviewed {label} has malformed restriction evidence: {key}"
            )
        if normalize_restriction_token(status) in _RESTRICTED_STATUSES or any(
            _POSITIVE_RESTRICTION_EVIDENCE.search(normalize_restriction_token(item))
            for item in cast(Sequence[str], evidence_value)
        ):
            raise DisclosureClearanceError(
                f"John-reviewed {label} has positive restriction evidence: {key}"
            )
        return
    recovered_model_review = (
        basis == "authenticated_model_exception_review"
        and isinstance(row.get("recovered_public_lineage"), Mapping)
    )
    if basis == "authenticated_model_exception_review" and not recovered_model_review:
        evidence_value = row.get("restriction_evidence")
        if (
            row.get("restriction_status") == "unknown"
            and isinstance(evidence_value, (list, tuple))
            and all(
                isinstance(item, str) for item in cast(Sequence[object], evidence_value)
            )
            and frozenset(cast(Sequence[str], evidence_value))
            == _PROVENANCE_REST_PUBLIC_EVIDENCE
        ):
            return
    if basis == "provider_free_recovered_public" or recovered_model_review:
        evidence_value = row.get("restriction_evidence")
        accepted = {
            (
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ),
            (
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_unknown",
                "courtlistener_recap_fetch_no_positive_private_marker",
                "courtlistener_recap_fetch_public_download_url_allowlisted",
            ),
        }
        if (
            row.get("restriction_status") != "public"
            or not isinstance(evidence_value, (list, tuple))
            or tuple(cast(Sequence[str], evidence_value)) not in accepted
        ):
            raise DisclosureClearanceError(
                f"recovered-public {label} lacks exact public evidence: {key}"
            )
        return
    if basis != "affirmative_public_provenance":
        _require_public_restriction(row, key=key, label=label)
        return
    evidence_value = row.get("restriction_evidence")
    if not isinstance(evidence_value, (list, tuple)) or not all(
        isinstance(item, str) and bool(item.strip())
        for item in cast(Sequence[object], evidence_value)
    ):
        raise DisclosureClearanceError(f"{label} lacks restriction evidence: {key}")
    evidence = frozenset(cast(Sequence[str], evidence_value))
    status = row.get("restriction_status")
    if not (
        (status == "public" and evidence == _PROVENANCE_PUBLIC_EVIDENCE)
        or (status == "unknown" and evidence == _PROVENANCE_REST_PUBLIC_EVIDENCE)
    ):
        raise DisclosureClearanceError(
            f"automatic {label} lacks exact public provenance evidence: {key}"
        )


def _require_direct_queue_delivery_lineage(
    lineage: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    """Validate the closed direct CourtListener queue proof in recovery lineage."""

    raw = lineage.get("direct_queue_delivery_authority")
    if not isinstance(raw, Mapping):
        raise DisclosureClearanceError(
            f"recovered-public direct queue lineage is invalid: {key}"
        )
    authority = cast(Mapping[str, object], raw)
    fields = {
        "schema_version",
        "source_provider",
        "purchase_status",
        "operation_key",
        "queue_id",
        "reservation_id",
        "reservation_usd",
        "queue_response_sha256",
        "purchase_policy_sha256",
        "purchase_operation_sha256",
        "purchase_response_sha256",
        "recovery_run_card_sha256",
        "recovery_manifest_sha256",
        "recovery_restriction_evidence_sha256",
        "purchase_state_sha256",
    }
    operation_key = authority.get("operation_key")
    queue_id = authority.get("queue_id")
    reservation_usd = authority.get("reservation_usd")
    if (
        set(authority) != fields
        or authority.get("schema_version")
        != "legalforecast.direct_courtlistener_queue_delivery_authority.v1"
        or authority.get("source_provider") != "courtlistener.recap-fetch+pacer"
        or authority.get("purchase_status") != "queued"
        or operation_key != lineage.get("purchase_operation_key")
        or authority.get("purchase_operation_sha256")
        != lineage.get("purchase_operation_sha256")
        or authority.get("recovery_run_card_sha256")
        != lineage.get("recovery_run_card_sha256")
        or authority.get("recovery_manifest_sha256")
        != lineage.get("recovery_manifest_sha256")
        or authority.get("recovery_restriction_evidence_sha256")
        != lineage.get("recovery_restriction_evidence_sha256")
        or authority.get("purchase_state_sha256")
        != lineage.get("purchase_state_sha256")
        or not isinstance(operation_key, str)
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            operation_key,
        )
        is None
        or authority.get("reservation_id") != f"direct:{operation_key}"
        or not isinstance(queue_id, str)
        or re.fullmatch(r"[1-9][0-9]*", queue_id) is None
        or not isinstance(reservation_usd, str)
        or re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", reservation_usd) is None
    ):
        raise DisclosureClearanceError(
            f"recovered-public direct queue lineage is invalid: {key}"
        )
    for field in (
        "queue_response_sha256",
        "purchase_policy_sha256",
        "purchase_operation_sha256",
        "purchase_response_sha256",
        "recovery_run_card_sha256",
        "recovery_manifest_sha256",
        "recovery_restriction_evidence_sha256",
        "purchase_state_sha256",
    ):
        value = authority.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise DisclosureClearanceError(
                f"recovered-public direct queue lineage hash is invalid: {key}"
            )


def _require_clearance_provenance(
    row: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    basis = row.get("clearance_basis")
    recovered_model_review = (
        basis == "authenticated_model_exception_review"
        and isinstance(row.get("recovered_public_lineage"), Mapping)
    )
    if basis == "provider_free_recovered_public" or recovered_model_review:
        reviewer_id = _optional_str(row, "reviewer_id")
        if basis == "provider_free_recovered_public" and (
            row.get("reviewed_at") is not None or reviewer_id is not None
        ):
            raise DisclosureClearanceError(
                f"recovered-public clearance unexpectedly has a reviewer: {key}"
            )
        if recovered_model_review and (
            row.get("reviewed_at") is not None or reviewer_id is None
        ):
            raise DisclosureClearanceError(
                f"model-reviewed recovered-public clearance lacks authority: {key}"
            )
        provenance = _optional_str(row, "controlled_store_provenance")
        if (
            provenance != f"courtlistener-rest://recap-documents/{key[1]}"
            or row.get("free_or_purchased") != "purchased"
        ):
            raise DisclosureClearanceError(
                f"recovered-public clearance has invalid CourtListener identity: {key}"
            )
        raw_lineage = row.get("recovered_public_lineage")
        expected_fields = {
            "candidate_id",
            "source_document_id",
            "recovery_run_card_sha256",
            "recovery_manifest_sha256",
            "recovery_restriction_evidence_sha256",
            "purchase_state_sha256",
            "purchase_operation_sha256",
            "purchase_operation_key",
            "fresh_recap_detail_sha256",
        }
        if not isinstance(raw_lineage, Mapping):
            raise DisclosureClearanceError(
                f"recovered-public clearance lacks closed lineage: {key}"
            )
        lineage = cast(Mapping[str, object], raw_lineage)
        lineage_fields = set(lineage)
        if lineage_fields != expected_fields and lineage_fields != expected_fields | {
            "direct_queue_delivery_authority"
        }:
            raise DisclosureClearanceError(
                f"recovered-public clearance lacks closed lineage: {key}"
            )
        if (
            lineage.get("candidate_id") != key[0]
            or lineage.get("source_document_id") != key[1]
        ):
            raise DisclosureClearanceError(
                f"recovered-public clearance lineage identity changed: {key}"
            )
        for field in (
            "recovery_run_card_sha256",
            "recovery_manifest_sha256",
            "recovery_restriction_evidence_sha256",
            "purchase_state_sha256",
            "purchase_operation_sha256",
            "fresh_recap_detail_sha256",
        ):
            value = lineage.get(field)
            if (
                not isinstance(value, str)
                or re.fullmatch(r"[0-9a-f]{64}", value) is None
            ):
                raise DisclosureClearanceError(
                    f"recovered-public clearance lineage hash is invalid: {key}"
                )
        operation_key = lineage.get("purchase_operation_key")
        if (
            not isinstance(operation_key, str)
            or re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                operation_key,
            )
            is None
        ):
            raise DisclosureClearanceError(
                f"recovered-public clearance operation identity is invalid: {key}"
            )
        if "direct_queue_delivery_authority" in lineage:
            _require_direct_queue_delivery_lineage(lineage, key=key)
        _require_routing_plan_hash(row, key=key)
        return
    if basis == "affirmative_public_provenance":
        if row.get("reviewed_at") is not None or row.get("reviewer_id") is not None:
            raise DisclosureClearanceError(
                f"automatic clearance unexpectedly has a reviewer: {key}"
            )
        provenance = _optional_str(row, "controlled_store_provenance")
        if provenance is None:
            raise DisclosureClearanceError(
                f"automatic clearance lacks public source provenance: {key}"
            )
        if (
            not is_allowlisted_public_recap_uri(provenance)
            or row.get("free_or_purchased") != "free"
        ):
            raise DisclosureClearanceError(
                f"automatic clearance provenance is not an allowlisted public "
                f"CourtListener source: {key}"
            )
        _require_routing_plan_hash(row, key=key)
        return
    if basis == "authenticated_model_exception_review":
        _require_routing_plan_hash(row, key=key)
        if row.get("reviewed_at") is not None:
            raise DisclosureClearanceError(
                f"model-reviewed clearance has a human review timestamp: {key}"
            )
        reviewer_id = _optional_str(row, "reviewer_id")
        provenance = _optional_str(row, "controlled_store_provenance")
        if (
            reviewer_id is None
            or provenance != "private-store://disclosure/model-review"
        ):
            raise DisclosureClearanceError(
                f"model-reviewed clearance lacks model authority provenance: {key}"
            )
        return
    if basis == "john_exception_review":
        _require_routing_plan_hash(row, key=key)
    elif basis is not None:
        raise DisclosureClearanceError(f"unsupported clearance basis: {key}")
    reviewed_at = _optional_str(row, "reviewed_at")
    reviewer_id = _optional_str(row, "reviewer_id")
    provenance = _optional_str(row, "controlled_store_provenance")
    if reviewed_at is None or reviewer_id is None or provenance is None:
        raise DisclosureClearanceError(f"clearance lacks review provenance: {key}")
    if not is_canonical_private_store_uri(provenance):
        raise DisclosureClearanceError(
            f"clearance provenance is not from the controlled private store: {key}"
        )


def _require_routing_plan_hash(
    row: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    value = row.get("routing_plan_sha256")
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DisclosureClearanceError(
            f"provenance clearance lacks routing plan hash: {key}"
        )


def ranked_replacement(
    frontier: Sequence[Mapping[str, object]],
    *,
    quarantined_candidate_id: str,
    already_selected_candidate_ids: Iterable[str],
    spent_or_reserved_usd: str,
    max_projected_cost_usd: str,
) -> ReplacementDecision:
    """Choose one next candidate under the frozen frontier order and same cap."""

    selected = set(already_selected_candidate_ids)
    selected.add(quarantined_candidate_id)
    spent = _decimal(spent_or_reserved_usd, "spent_or_reserved_usd")
    cap = _decimal(max_projected_cost_usd, "max_projected_cost_usd")
    by_id: dict[str, Mapping[str, object]] = {}
    for row in frontier:
        candidate_id = _required_str(row, "candidate_id")
        if candidate_id in by_id:
            raise DisclosureClearanceError(
                f"duplicate frontier candidate: {candidate_id}"
            )
        by_id[candidate_id] = row
    quarantined = by_id.get(quarantined_candidate_id)
    write_off = _cost(quarantined) if quarantined is not None else Decimal("0.00")
    ordered = sorted(
        frontier,
        key=lambda row: (
            _missing_document_count(row),
            _cost(row),
            _required_str(row, "candidate_id").casefold(),
            _required_str(row, "candidate_id"),
        ),
    )
    for rank, row in enumerate(ordered, start=1):
        candidate_id = _required_str(row, "candidate_id")
        cost = _cost(row)
        if (
            candidate_id in selected
            or row.get("exclusion_reasons") not in (None, [], ())
            or spent + cost > cap
        ):
            continue
        return ReplacementDecision(
            quarantined_candidate_id=quarantined_candidate_id,
            replacement_candidate_id=candidate_id,
            replacement_rank=rank,
            write_off_cost_usd=f"{write_off:.2f}",
            replacement_cost_usd=f"{cost:.2f}",
            reason="next_cheapest_eligible_under_same_cap",
        )
    return ReplacementDecision(
        quarantined_candidate_id=quarantined_candidate_id,
        replacement_candidate_id=None,
        replacement_rank=None,
        write_off_cost_usd=f"{write_off:.2f}",
        replacement_cost_usd=None,
        reason="frontier_exhausted_or_cap_insufficient",
    )


def _scan_pdf(data: bytes) -> tuple[str, ...]:
    try:
        extraction = extract_pdf_text_with_ocr_fallback(data)
    except PDFExtractionError:
        return ("invalid_pdf",)
    unsafe_quality = {
        "empty_text",
        "no_text_layer",
        "ocr_engine_unavailable",
        "ocr_failed",
        "ocr_recommended",
        "page_count_mismatch",
    }
    markers = {
        f"extraction_{flag}"
        for flag in extraction.quality_flags
        if flag in unsafe_quality
    }
    for name, pattern in (
        ("ssn", _SSN),
        ("dob", _DOB),
        ("minor", _MINOR),
        ("medical", _MEDICAL),
    ):
        if pattern.search(extraction.text):
            markers.add(name)
    if not extraction.text.strip():
        markers.add("unscannable_or_image_only")
    return tuple(sorted(markers))


def extract_disclosure_pdf_pages(data: bytes) -> DisclosurePdfPageExtraction:
    """Extract nonempty page text from one exact PDF byte string."""

    diagnostics: set[str] = set()
    parsed_page_count = 0
    pages: list[DisclosurePdfPage] = []
    unscanned_pages: list[int] = []
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            diagnostics.add("pdf_encrypted")
        else:
            parsed_page_count = len(reader.pages)
            if parsed_page_count == 0:
                diagnostics.add("pdf_has_no_pages")
            for page_number, page in enumerate(reader.pages, start=1):
                try:
                    normalized = (page.extract_text() or "").strip()
                except Exception:
                    diagnostics.add(f"page_text_extraction_failed:{page_number}")
                    unscanned_pages.append(page_number)
                    continue
                if not normalized:
                    diagnostics.add(f"page_text_empty:{page_number}")
                    unscanned_pages.append(page_number)
                    continue
                pages.append(
                    DisclosurePdfPage(page_number=page_number, text=normalized)
                )
    except Exception:
        diagnostics.add("pdf_parse_failed")

    all_pages = set(range(1, parsed_page_count + 1))
    covered_pages = {page.page_number for page in pages}
    missing_pages = all_pages - covered_pages
    unscanned_pages = sorted(set(unscanned_pages) | missing_pages)
    return DisclosurePdfPageExtraction(
        parsed_page_count=parsed_page_count,
        pages=tuple(pages),
        unscanned_page_numbers=tuple(unscanned_pages),
        diagnostics=tuple(sorted(diagnostics)),
    )


def disclosure_markers_for_text(text: str) -> tuple[str, ...]:
    """Return substantive disclosure marker categories in one text string."""

    markers = {
        name
        for name, pattern in (
            ("ssn", _SSN),
            ("dob", _DOB),
            ("minor", _MINOR),
            ("medical", _MEDICAL),
        )
        if pattern.search(text)
    }
    return tuple(sorted(markers))


def scan_disclosure_document(data: bytes) -> DisclosurePdfScan:
    """Scan every parsed PDF page once and return closed coverage evidence."""

    return _scan_disclosure_document(data, include_legacy_diagnostics=False)


def scan_disclosure_document_v1(data: bytes) -> DisclosurePdfScan:
    """Replay the historical v1 scan, including its legacy diagnostics pass."""

    return _scan_disclosure_document(data, include_legacy_diagnostics=True)


def _scan_disclosure_document(
    data: bytes, *, include_legacy_diagnostics: bool
) -> DisclosurePdfScan:
    """Build versioned page-coverage evidence from exact PDF bytes."""

    extraction = extract_disclosure_pdf_pages(data)
    diagnostics = set(extraction.diagnostics)
    if include_legacy_diagnostics:
        try:
            legacy = extract_pdf_text_with_ocr_fallback(data)
        except PDFExtractionError:
            diagnostics.add("legacy_extraction_failed")
        else:
            diagnostics.update(
                f"legacy_extraction_{flag}" for flag in legacy.quality_flags
            )

    text_pages = [page.page_number for page in extraction.pages]
    unscanned_pages = list(extraction.unscanned_page_numbers)
    parsed_page_count = extraction.parsed_page_count
    coverage_complete = parsed_page_count > 0 and not unscanned_pages
    markers = {
        marker
        for page in extraction.pages
        for marker in disclosure_markers_for_text(page.text)
    }
    if not coverage_complete:
        markers.update(
            {"extraction_page_coverage_incomplete", "unscannable_or_image_only"}
        )
    return DisclosurePdfScan(
        parsed_page_count=parsed_page_count,
        text_scanned_page_numbers=tuple(text_pages),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=tuple(unscanned_pages),
        coverage_status="complete" if coverage_complete else "incomplete",
        diagnostics=tuple(sorted(diagnostics)),
        automated_markers=tuple(sorted(markers)),
        schema_version=(
            PDF_SCAN_SCHEMA_VERSION_V1
            if include_legacy_diagnostics
            else PDF_SCAN_SCHEMA_VERSION
        ),
        method=(
            "pypdf_page_text_v1" if include_legacy_diagnostics else "pypdf_page_text_v2"
        ),
    )


def scan_disclosure_markers(data: bytes) -> tuple[str, ...]:
    """Return privacy, restriction, and extraction markers for exact PDF bytes."""

    return _scan_pdf(data)


def _restriction_classification(
    records: Sequence[Mapping[str, object]],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    markers = restricted_material_markers(records=records)
    if markers:
        return "restricted", tuple(f"marker:{item}" for item in markers), markers
    statuses: set[str] = set()
    evidence: set[str] = set()
    for record in records:
        for field in ("redaction_or_seal_status", "restriction_status"):
            value = _optional_str(record, field)
            if value is not None:
                statuses.add(normalize_restriction_token(value))
        item = record.get("restriction_evidence")
        if isinstance(item, str) and item.strip():
            evidence.add(item.strip())
        elif isinstance(item, (list, tuple)):
            for evidence_item in cast("list[object] | tuple[object, ...]", item):
                if isinstance(evidence_item, str) and evidence_item.strip():
                    evidence.add(evidence_item.strip())
    if statuses & _RESTRICTED_STATUSES:
        return "restricted", tuple(sorted(evidence)), ("restricted_status",)
    public = statuses & _PUBLIC_STATUSES
    if len(public) == 1 and evidence:
        return next(iter(public)), tuple(sorted(evidence)), ()
    return "unknown", tuple(sorted(evidence)), ()


def normalize_restriction_token(value: str) -> str:
    """Canonicalize restriction text for exact denylist comparisons."""

    return re.sub(r"[\s-]+", "_", value.strip().casefold())


def _safe_document_path(root: Path, local_path: str) -> Path:
    path = Path(local_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DisclosureClearanceError("local_path must be relative to document_root")
    current = Path(root.anchor) if root.is_absolute() else Path.cwd()
    parts = root.parts[1:] if root.is_absolute() else root.parts
    for part in parts:
        if part == ".":
            continue
        if part == "..":
            current = current.parent
            continue
        current /= part
        if current.is_symlink():
            raise DisclosureClearanceError("document_root traverses a symlink")
    if not current.is_dir():
        raise DisclosureClearanceError("document_root is not a directory")
    root_resolved = root.resolve()
    candidate = (root_resolved / path).resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise DisclosureClearanceError("local_path escapes document_root")
    current = root_resolved
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise DisclosureClearanceError("local_path traverses a symlink")
    return candidate


def safe_disclosure_document_path(root: Path, local_path: str) -> Path:
    """Resolve one contained document path while rejecting every symlink hop."""

    return _safe_document_path(root, local_path)


def _verify_manifest_commitments(
    document: Mapping[str, object],
    *,
    digest: str,
    byte_count: int,
    key: tuple[str, str],
) -> None:
    if digest != _digest(document, "sha256"):
        raise DisclosureClearanceError(f"download hash mismatch: {key}")
    if byte_count != _positive_int(document, "byte_count"):
        raise DisclosureClearanceError(f"download byte-count mismatch: {key}")


def _verify_review_hash(
    review: Mapping[str, object], *, digest: str, key: tuple[str, str]
) -> None:
    if _digest(review, "sha256") != digest:
        raise DisclosureClearanceError(f"review hash mismatch: {key}")


def _read_document(path: Path, key: tuple[str, str]) -> bytes:
    payload, _device, _inode = _read_document_with_identity(path, key)
    return payload


def _read_document_with_identity(
    path: Path, key: tuple[str, str]
) -> tuple[bytes, int, int]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DisclosureClearanceError(f"document cannot be read: {key}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DisclosureClearanceError(
                f"document is not a singly linked regular file: {key}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read()
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or after.st_nlink != 1:
            raise DisclosureClearanceError(f"document changed while being read: {key}")
        return payload, before.st_dev, before.st_ino
    except OSError as exc:
        raise DisclosureClearanceError(f"document cannot be read: {key}") from exc
    finally:
        os.close(descriptor)


def _unique_index(
    records: Sequence[Mapping[str, object]], label: str
) -> dict[tuple[str, str], Mapping[str, object]]:
    output: dict[tuple[str, str], Mapping[str, object]] = {}
    for record in records:
        key = _document_key(record)
        if key in output:
            raise DisclosureClearanceError(f"duplicate {label} key: {key}")
        output[key] = record
    return output


def _restriction_index(
    records: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], tuple[Mapping[str, object], ...]]:
    output: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for record in records:
        output.setdefault(_document_key(record), []).append(record)
    return {key: tuple(value) for key, value in output.items()}


def _document_key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _required_str(record, "candidate_id"),
        _required_str(record, "source_document_id"),
    )


def _required_phase(document: Mapping[str, object]) -> str:
    phase = _required_str(document, "free_or_purchased")
    if phase not in {"free", "purchased"}:
        raise DisclosureClearanceError("free_or_purchased must be free or purchased")
    return phase


def _digest(record: Mapping[str, object], field: str) -> str:
    value = _required_str(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise DisclosureClearanceError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _positive_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DisclosureClearanceError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DisclosureClearanceError(f"{field} must be a non-negative integer")
    return value


def _missing_document_count(record: Mapping[str, object]) -> int:
    field = (
        "missing_required_document_count"
        if "missing_required_document_count" in record
        else "estimated_purchase_count"
    )
    return _nonnegative_int(record, field)


def _cost(record: Mapping[str, object] | None) -> Decimal:
    if record is None:
        return Decimal("0.00")
    value = record.get("projected_paid_cost_usd", record.get("estimated_cost_usd"))
    if not isinstance(value, (str, int)):
        raise DisclosureClearanceError("frontier row requires projected cost")
    return _decimal(str(value), "projected cost")


def _decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise DisclosureClearanceError(f"{field} must be decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise DisclosureClearanceError(f"{field} must be non-negative")
    return parsed


def _required_str(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DisclosureClearanceError(f"{field} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, object], field: str) -> str | None:
    value = record.get(field)
    return value if isinstance(value, str) and value.strip() else None

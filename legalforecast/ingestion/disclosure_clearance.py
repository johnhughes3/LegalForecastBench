"""Fail-closed, hash-bound disclosure clearance for acquired documents."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from legalforecast.extraction.pdf_text import (
    PDFExtractionError,
    extract_pdf_text_with_ocr_fallback,
)
from legalforecast.ingestion.restricted_material import restricted_material_markers

SCHEMA_VERSION = "legalforecast.disclosure_clearance.v1"
_CLEAR = "cleared"
_QUARANTINED = "quarantined"
_RESTRICTED_STATUSES = frozenset({"private", "restricted", "sealed", "under_seal"})
_PUBLIC_STATUSES = frozenset({"public", "redacted"})
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

    def to_record(self) -> dict[str, object]:
        """Return the stable artifact row without sensitive matched values."""

        return {
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


def build_clearance_records(
    documents: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    reviews: Sequence[Mapping[str, object]],
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
            _verify_review_hash(review, digest=digest, key=key)
            requested_status = _required_str(review, "status")
            if requested_status not in {_CLEAR, _QUARANTINED}:
                raise DisclosureClearanceError(f"invalid review status: {key}")
            reviewer_id = _optional_str(review, "reviewer_id")
            provenance = _optional_str(review, "controlled_store_provenance")
            reviewed_at = _optional_str(review, "reviewed_at")
            if not reviewer_id and not provenance:
                raise DisclosureClearanceError(
                    f"review requires authenticated identity or provenance: {key}"
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
) -> None:
    """Require exact artifact coverage and re-hash the bytes about to be used."""

    index = _unique_index(clearance_records, "clearance")
    document_keys = {_document_key(document) for document in documents}
    if set(index) != document_keys:
        missing = sorted(document_keys - set(index))
        extra = sorted(set(index) - document_keys)
        raise DisclosureClearanceError(
            f"clearance coverage mismatch; missing={missing}; extra={extra}"
        )
    for document in documents:
        key = _document_key(document)
        clearance = index[key]
        if clearance.get("schema_version") != SCHEMA_VERSION:
            raise DisclosureClearanceError(f"unsupported clearance schema: {key}")
        if clearance.get("status") != _CLEAR:
            raise DisclosureClearanceError(f"document lacks clearance: {key}")
        if _required_str(clearance, "restriction_status") not in _PUBLIC_STATUSES:
            raise DisclosureClearanceError(f"document restriction is not public: {key}")
        path = _safe_document_path(document_root, _required_str(document, "local_path"))
        data = _read_document(path, key)
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
        if _optional_str(clearance, "reviewed_at") is None or not (
            _optional_str(clearance, "reviewer_id")
            or _optional_str(clearance, "controlled_store_provenance")
        ):
            raise DisclosureClearanceError(f"clearance lacks review provenance: {key}")


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
        if _required_str(row, "restriction_status") not in _PUBLIC_STATUSES:
            raise DisclosureClearanceError(
                f"parser document restriction is not public: {key}"
            )
        if _optional_str(row, "reviewed_at") is None or not (
            _optional_str(row, "reviewer_id")
            or _optional_str(row, "controlled_store_provenance")
        ):
            raise DisclosureClearanceError(f"clearance lacks review provenance: {key}")
    return index


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
    by_id = {_required_str(row, "candidate_id"): row for row in frontier}
    quarantined = by_id.get(quarantined_candidate_id)
    write_off = _cost(quarantined) if quarantined is not None else Decimal("0.00")
    ordered = sorted(
        frontier,
        key=lambda row: (
            _nonnegative_int(row, "estimated_purchase_count"),
            _cost(row),
            _required_str(row, "candidate_id"),
        ),
    )
    for rank, row in enumerate(ordered, start=1):
        candidate_id = _required_str(row, "candidate_id")
        cost = _cost(row)
        if candidate_id in selected or spent + cost > cap:
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
    text = extraction.text
    for name, pattern in (
        ("ssn", _SSN),
        ("dob", _DOB),
        ("minor", _MINOR),
        ("medical", _MEDICAL),
    ):
        if pattern.search(text):
            markers.add(name)
    if not text.strip():
        markers.add("unscannable_or_image_only")
    return tuple(sorted(markers))


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
                statuses.add(value.casefold().replace("-", "_"))
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


def _safe_document_path(root: Path, local_path: str) -> Path:
    path = Path(local_path)
    if path.is_absolute():
        raise DisclosureClearanceError("local_path must be relative to document_root")
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
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DisclosureClearanceError(f"document cannot be read: {key}") from exc


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
    if parsed < 0:
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

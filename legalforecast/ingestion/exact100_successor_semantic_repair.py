"""Byte-bound semantic document-role repairs for an exact-100 successor.

Original acquisition metadata remains immutable. This module recognizes only
an operative amended complaint embedded in a removal bundle and a motion notice
that also contains its supporting memorandum. Persisted records are evidence,
not authority; a producer replay must authenticate inputs before private mint.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from io import BytesIO
from types import MappingProxyType
from typing import Any, cast

from pypdf import PdfReader

import legalforecast.contracts as contracts
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.provenance import DocumentRole

JsonRecord = dict[str, Any]
DocumentKey = tuple[str, str]
SCHEMA_VERSION = str(
    getattr(
        contracts,
        "EXACT100_SUCCESSOR_SEMANTIC_REPAIR_V1",
        "legalforecast.exact100_successor_semantic_repair.v1",
    )
)
_VERIFICATION_SEAL = object()
_EMBEDDED_COMPLAINT_SOURCE_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT.value,
        DocumentRole.DOCKET_HISTORY.value,
        DocumentRole.OTHER.value,
    }
)


class Exact100SuccessorSemanticRepairError(ValueError):
    """Raised when semantic-repair inputs or replay do not reconcile."""


class SemanticRepairKind(StrEnum):
    """Closed repairs supported by the Cycle 1 successor."""

    EMBEDDED_OPERATIVE_AMENDED_COMPLAINT = "embedded_operative_amended_complaint"
    COMBINED_MTD_MEMORANDUM = "combined_mtd_memorandum"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100SuccessorSemanticRepairs:
    """Semantic repairs sealed after exact metadata and PDF-byte verification."""

    records: tuple[JsonRecord, ...]
    records_bytes: bytes
    source_documents: tuple[JsonRecord, ...]
    source_document_bytes: Mapping[DocumentKey, bytes]
    source_commitments: Mapping[str, str]
    commitment_sha256: str
    _verification_seal: object = field(repr=False, compare=False)

    def derived_roles_for(
        self, *, candidate_id: str, source_document_id: str
    ) -> tuple[str, ...]:
        """Return replay-verified derived roles for one exact source document."""

        return tuple(
            cast(str, record["derived_document_role"])
            for record in self.records
            if record["candidate_id"] == candidate_id
            and record["source_document_id"] == source_document_id
        )

    def semantic_roles_for(
        self, *, candidate_id: str, source_document_id: str
    ) -> tuple[str, ...]:
        """Return the immutable original role followed by derived roles."""

        document = next(
            (
                record
                for record in self.source_documents
                if record["candidate_id"] == candidate_id
                and record["source_document_id"] == source_document_id
            ),
            None,
        )
        if document is None:
            return ()
        original = cast(str, document["document_role"])
        derived = self.derived_roles_for(
            candidate_id=candidate_id, source_document_id=source_document_id
        )
        return tuple(dict.fromkeys((original, *derived)))


def _mint_verified_exact100_successor_semantic_repairs(  # pyright: ignore[reportUnusedFunction]
    *,
    document_records: Sequence[Mapping[str, Any]],
    document_bytes_by_key: Mapping[DocumentKey, bytes],
) -> VerifiedExact100SuccessorSemanticRepairs:
    """Mint repairs from document snapshots authenticated by the caller."""

    documents = tuple(
        sorted(
            (dict(record) for record in document_records),
            key=lambda record: (
                _required_text(record, "candidate_id"),
                _required_text(record, "source_document_id"),
            ),
        )
    )
    by_key = _validate_source_documents(documents, document_bytes_by_key)
    records: list[JsonRecord] = []
    for key in sorted(by_key):
        document = by_key[key]
        original_role = _required_text(document, "document_role")
        if original_role not in (
            *_EMBEDDED_COMPLAINT_SOURCE_ROLES,
            DocumentRole.MTD_NOTICE.value,
        ):
            continue
        pages = _extract_normalized_pdf_pages(document_bytes_by_key[key], key=key)
        if original_role in _EMBEDDED_COMPLAINT_SOURCE_ROLES:
            evidence = _embedded_amended_complaint_evidence(pages)
            kind = SemanticRepairKind.EMBEDDED_OPERATIVE_AMENDED_COMPLAINT
            derived_role = DocumentRole.AMENDED_COMPLAINT
        else:
            evidence = _combined_mtd_memorandum_evidence(pages)
            kind = SemanticRepairKind.COMBINED_MTD_MEMORANDUM
            derived_role = DocumentRole.MTD_MEMORANDUM
        if evidence is None:
            continue
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": key[0],
                "source_document_id": key[1],
                "docket_entry_number": _optional_positive_int(
                    document, "docket_entry_number"
                ),
                "original_document_role": original_role,
                "derived_document_role": derived_role.value,
                "repair_kind": kind.value,
                "source_sha256": _raw_sha(document["sha256"]),
                "source_byte_count": cast(int, document["byte_count"]),
                "source_metadata_sha256": _sha(_canonical_bytes(document)),
                "evidence_cues": list(evidence),
            }
        )

    records_tuple = tuple(records)
    records_bytes = _jsonl_bytes(records_tuple)
    source_bytes = MappingProxyType(
        {
            key: bytes(document_bytes_by_key[key])
            for key in sorted(document_bytes_by_key)
        }
    )
    source_commitments = MappingProxyType(
        {
            "document_metadata": _sha(_jsonl_bytes(documents)),
            "document_bytes_tree": _document_bytes_tree_sha256(source_bytes),
        }
    )
    result = object.__new__(VerifiedExact100SuccessorSemanticRepairs)
    for name, value in (
        ("records", records_tuple),
        ("records_bytes", records_bytes),
        ("source_documents", documents),
        ("source_document_bytes", source_bytes),
        ("source_commitments", source_commitments),
        ("commitment_sha256", _sha(records_bytes)),
        ("_verification_seal", _VERIFICATION_SEAL),
    ):
        object.__setattr__(result, name, value)
    return result


def _replay_verified_exact100_successor_semantic_repairs(  # pyright: ignore[reportUnusedFunction]
    *,
    persisted_repairs_bytes: bytes,
    document_records: Sequence[Mapping[str, Any]],
    document_bytes_by_key: Mapping[DocumentKey, bytes],
) -> VerifiedExact100SuccessorSemanticRepairs:
    """Reconstruct repairs and require exact canonical persisted bytes."""

    repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=document_records,
        document_bytes_by_key=document_bytes_by_key,
    )
    if persisted_repairs_bytes != repairs.records_bytes:
        raise Exact100SuccessorSemanticRepairError(
            "semantic repair records differ from authenticated replay"
        )
    return repairs


def verify_exact100_successor_semantic_repairs(
    **_unattested: Any,
) -> VerifiedExact100SuccessorSemanticRepairs:
    """Refuse raw caller evidence; authenticated producer replay is required."""

    raise Exact100SuccessorSemanticRepairError(
        "direct semantic repair verification is disabled; replay authenticated "
        "document metadata and bytes"
    )


def require_verified_exact100_successor_semantic_repairs(
    repairs: VerifiedExact100SuccessorSemanticRepairs,
) -> None:
    """Reject a caller-constructed, altered, or stale semantic capability."""

    if (
        type(repairs) is not VerifiedExact100SuccessorSemanticRepairs
        or getattr(repairs, "_verification_seal", None) is not _VERIFICATION_SEAL
    ):
        raise Exact100SuccessorSemanticRepairError(
            "semantic repairs were not produced by authenticated replay"
        )
    replayed = _mint_verified_exact100_successor_semantic_repairs(
        document_records=repairs.source_documents,
        document_bytes_by_key=repairs.source_document_bytes,
    )
    if (
        repairs.records != replayed.records
        or repairs.records_bytes != replayed.records_bytes
        or dict(repairs.source_commitments) != dict(replayed.source_commitments)
        or repairs.commitment_sha256 != replayed.commitment_sha256
    ):
        raise Exact100SuccessorSemanticRepairError(
            "semantic repairs changed after authenticated replay"
        )


def _validate_source_documents(
    documents: Sequence[JsonRecord],
    document_bytes_by_key: Mapping[DocumentKey, object],
) -> dict[DocumentKey, JsonRecord]:
    by_key: dict[DocumentKey, JsonRecord] = {}
    for document in documents:
        key = (
            _required_text(document, "candidate_id"),
            _required_text(document, "source_document_id"),
        )
        if key in by_key:
            raise Exact100SuccessorSemanticRepairError(
                f"duplicate source document: {key[0]}/{key[1]}"
            )
        try:
            DocumentRole(_required_text(document, "document_role"))
        except ValueError as exc:
            raise Exact100SuccessorSemanticRepairError(
                f"source document has invalid role: {key[0]}/{key[1]}"
            ) from exc
        byte_count = document.get("byte_count")
        if type(byte_count) is not int or byte_count < 0:
            raise Exact100SuccessorSemanticRepairError(
                f"source document has invalid byte_count: {key[0]}/{key[1]}"
            )
        _raw_sha(document.get("sha256"))
        by_key[key] = document
    if set(document_bytes_by_key) != set(by_key):
        raise Exact100SuccessorSemanticRepairError(
            "document bytes differ from exact source metadata coverage"
        )
    for key, document in by_key.items():
        payload = document_bytes_by_key[key]
        if not isinstance(payload, bytes):
            raise Exact100SuccessorSemanticRepairError(
                f"source document bytes are invalid: {key[0]}/{key[1]}"
            )
        if len(payload) != document["byte_count"] or hashlib.sha256(
            payload
        ).hexdigest() != _raw_sha(document["sha256"]):
            raise Exact100SuccessorSemanticRepairError(
                f"source document bytes differ from metadata: {key[0]}/{key[1]}"
            )
    return by_key


def _extract_normalized_pdf_pages(
    payload: bytes, *, key: DocumentKey
) -> tuple[str, ...]:
    try:
        reader = PdfReader(BytesIO(payload), strict=False)
        if reader.is_encrypted or not reader.pages:
            raise ValueError
        pages = tuple(
            _normalize_pdf_text(page.extract_text() or "") for page in reader.pages
        )
    except Exception as exc:
        raise Exact100SuccessorSemanticRepairError(
            f"source document is not a readable text PDF: {key[0]}/{key[1]}"
        ) from exc
    if not any(pages):
        raise Exact100SuccessorSemanticRepairError(
            f"source document has no PDF text layer: {key[0]}/{key[1]}"
        )
    return pages


def _embedded_amended_complaint_evidence(
    pages: Sequence[str],
) -> tuple[JsonRecord, ...] | None:
    notice_page = _first_page_with(pages[:5], "NOTICE OF REMOVAL")
    attachment_page = _first_page_matching(
        pages[:10],
        lambda text: (
            "A TRUE AND CORRECT COPY OF THE FIRST AMENDED COMPLAINT" in text
            and "ATTACHED HERETO AS EXHIBIT B" in text
        ),
    )
    exhibit_page = _first_page_matching(
        pages, lambda text: text.startswith("EXHIBIT B ") or text == "EXHIBIT B"
    )
    complaint_page = (
        _first_page_with(
            pages[exhibit_page:],
            "VERIFIED FIRST AMENDED COMPLAINT",
            page_number_offset=exhibit_page,
        )
        if exhibit_page is not None
        else None
    )
    if (
        None in {notice_page, attachment_page, exhibit_page, complaint_page}
        or not cast(int, notice_page)
        <= cast(int, attachment_page)
        < cast(int, exhibit_page)
        < cast(int, complaint_page)
        or cast(int, complaint_page) > cast(int, exhibit_page) + 2
    ):
        return None
    return (
        {"cue": "notice_of_removal", "page_number": notice_page},
        {
            "cue": "first_amended_complaint_attached_as_exhibit_b",
            "page_number": attachment_page,
        },
        {"cue": "exhibit_b_cover", "page_number": exhibit_page},
        {
            "cue": "verified_first_amended_complaint",
            "page_number": complaint_page,
        },
    )


def _combined_mtd_memorandum_evidence(
    pages: Sequence[str],
) -> tuple[JsonRecord, ...] | None:
    title_page = _first_page_matching(
        pages[:5],
        lambda text: (
            "NOTICE OF MOTION AND MOTION TO DISMISS" in text
            and "MEMORANDUM OF POINTS AND AUTHORITIES" in text
        ),
    )
    memorandum_page = _first_page_matching(
        pages,
        lambda text: (
            "MEMORANDUM OF POINTS AND AUTHORITIES" in text
            and re.search(r"(?:^| )INTRODUCTION(?: |$)", text) is not None
            and "TABLE OF CONTENTS" not in text
        ),
    )
    argument_page = (
        _first_page_matching(
            pages[memorandum_page - 1 :],
            lambda text: re.search(r"(?:^| )ARGUMENT I(?:\.| )", text) is not None,
            page_number_offset=memorandum_page - 1,
        )
        if memorandum_page is not None
        else None
    )
    if None in {title_page, memorandum_page, argument_page} or not cast(
        int, title_page
    ) <= cast(int, memorandum_page) <= cast(int, argument_page):
        return None
    return (
        {
            "cue": "notice_of_motion_and_motion_to_dismiss",
            "page_number": title_page,
        },
        {
            "cue": "memorandum_of_points_and_authorities_introduction",
            "page_number": memorandum_page,
        },
        {"cue": "argument_heading", "page_number": argument_page},
    )


def _first_page_with(
    pages: Sequence[str], cue: str, *, page_number_offset: int = 0
) -> int | None:
    return _first_page_matching(
        pages, lambda text: cue in text, page_number_offset=page_number_offset
    )


def _first_page_matching(
    pages: Sequence[str],
    predicate: Callable[[str], bool],
    *,
    page_number_offset: int = 0,
) -> int | None:
    return next(
        (
            index
            for index, text in enumerate(pages, start=page_number_offset + 1)
            if predicate(text)
        ),
        None,
    )


def _normalize_pdf_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().upper()


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise Exact100SuccessorSemanticRepairError(f"source document lacks {field}")
    return value


def _optional_positive_int(record: Mapping[str, Any], field: str) -> int | None:
    value = record.get(field)
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise Exact100SuccessorSemanticRepairError(
            f"source document has invalid {field}"
        )
    return value


def _raw_sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise Exact100SuccessorSemanticRepairError("source document has invalid sha256")
    return value


def _document_bytes_tree_sha256(
    document_bytes_by_key: Mapping[DocumentKey, bytes],
) -> str:
    tree = {
        f"{candidate_id}/{source_document_id}": hashlib.sha256(payload).hexdigest()
        for (candidate_id, source_document_id), payload in sorted(
            document_bytes_by_key.items()
        )
    }
    return _sha(_canonical_bytes(tree))


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(record)) for record in records)


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorSemanticRepairError,
        error_message="semantic repair serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

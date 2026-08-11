"""Derive the closed exact-100 successor for one public support memorandum.

The executor and CLI own authenticated input replay and filesystem publication.
This module is deliberately pure: it can only transform an already-verified v2
projection plus the one verified, plan-bound ECF-14 evidence record.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.contracts import EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.core_document_filter import filter_core_documents

JsonRecord = dict[str, Any]
DocumentKey = tuple[str, str]

SCHEMA_VERSION = str(EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1)
SUPPORT_CANDIDATE_ID = "73327542"
SUPPORT_DOCUMENT_ID = "73327542-entry-14-motion-to-dismiss-memorandum"
SUPPORT_DOCUMENT_ROLE = "motion_to_dismiss_memorandum"
SUPPORT_DOCKET_ENTRY_NUMBER = 14
SUPPORT_SOURCE_URL = (
    "https://storage.courtlistener.com/recap/gov.uscourts.nysd.663802/"
    "gov.uscourts.nysd.663802.14.0.pdf"
)


class SupportingDocumentSuccessorError(ValueError):
    """Raised when the closed ECF-14 successor cannot be reconstructed."""


@dataclass(frozen=True, slots=True)
class SupportingDocumentSuccessor:
    """Deterministic projection surfaces after adding the single support memo."""

    selection_records: tuple[JsonRecord, ...]
    case_relevance: tuple[JsonRecord, ...]
    free_manifest: tuple[JsonRecord, ...]
    free_clearance: tuple[JsonRecord, ...]
    restriction_records: tuple[JsonRecord, ...]
    core_filter_records: tuple[JsonRecord, ...]
    selected_document_keys: frozenset[DocumentKey]

    @property
    def selection_bytes(self) -> bytes:
        return _jsonl_bytes(self.selection_records)

    @property
    def case_relevance_bytes(self) -> bytes:
        return _jsonl_bytes(self.case_relevance)

    @property
    def free_manifest_bytes(self) -> bytes:
        return _jsonl_bytes(self.free_manifest)

    @property
    def free_clearance_bytes(self) -> bytes:
        return _jsonl_bytes(self.free_clearance)

    @property
    def restriction_bytes(self) -> bytes:
        return _jsonl_bytes(self.restriction_records)

    @property
    def core_filter_bytes(self) -> bytes:
        return _jsonl_bytes(self.core_filter_records)


def build_supporting_document_successor(
    *,
    base_projection: Mapping[str, object],
    addition: Mapping[str, object],
    addition_clearance: Mapping[str, object],
    addition_restriction: Mapping[str, object],
) -> SupportingDocumentSuccessor:
    """Add exactly the closed support memorandum to a verified v2 projection.

    The caller must have already reauthenticated the v2 projection and plan.
    This function refuses a caller-selected alternate document, a duplicate,
    missing support candidate, or evidence whose identity does not match the
    only allowed tuple.
    """

    _validate_addition(addition, label="support memorandum download")
    _validate_addition(addition_clearance, label="support memorandum clearance")
    _validate_addition(addition_restriction, label="support memorandum restriction")
    _require_matching_document_evidence(
        addition,
        addition_clearance,
        addition_restriction,
    )
    if addition_clearance.get("status") != "cleared":
        raise SupportingDocumentSuccessorError("support memorandum is not cleared")
    if (
        addition_restriction.get("is_private") is not False
        or addition_restriction.get("is_sealed") is not False
    ):
        raise SupportingDocumentSuccessorError("support memorandum is not public")

    selection = _records(base_projection, "selection_records")
    relevance = _records(base_projection, "case_relevance")
    manifest = _records(base_projection, "free_manifest")
    clearance = _records(base_projection, "free_clearance")
    restrictions = _records(base_projection, "restriction_records")
    key = _key(addition)
    if key in {_key(record) for record in manifest}:
        raise SupportingDocumentSuccessorError("support memorandum already exists")

    selection_records = _append_document_to_candidate(
        selection, document=_selection_document(addition), label="selection"
    )
    relevance_records = _append_document_to_candidate(
        relevance, document=_relevance_document(addition), label="case relevance"
    )
    free_manifest = tuple((*manifest, dict(addition)))
    free_clearance = tuple((*clearance, dict(addition_clearance)))
    restriction_records = tuple((*restrictions, dict(addition_restriction)))
    try:
        core_filter_records = tuple(
            result.to_record() for result in filter_core_documents(relevance_records)
        )
    except ValueError as exc:
        raise SupportingDocumentSuccessorError(
            "support memorandum case relevance cannot be core-filtered"
        ) from exc
    selected_keys = {
        (candidate_id, source_document_id)
        for record in selection_records
        for candidate_id, source_document_id in _document_keys_from_selection(record)
    }
    if key not in selected_keys:
        raise SupportingDocumentSuccessorError(
            "support memorandum was not added to the selected document ledger"
        )
    if {_key(record) for record in free_manifest} - selected_keys:
        raise SupportingDocumentSuccessorError(
            "free manifest is outside the selected document ledger"
        )
    return SupportingDocumentSuccessor(
        selection_records=selection_records,
        case_relevance=relevance_records,
        free_manifest=free_manifest,
        free_clearance=free_clearance,
        restriction_records=restriction_records,
        core_filter_records=core_filter_records,
        selected_document_keys=frozenset(selected_keys),
    )


def _validate_addition(record: Mapping[str, object], *, label: str) -> None:
    if _key(record) != (SUPPORT_CANDIDATE_ID, SUPPORT_DOCUMENT_ID):
        raise SupportingDocumentSuccessorError(f"{label} is outside the allowlist")
    if record.get("document_role") != SUPPORT_DOCUMENT_ROLE:
        raise SupportingDocumentSuccessorError(f"{label} has the wrong document role")
    if record.get("free_or_purchased") != "free":
        raise SupportingDocumentSuccessorError(f"{label} is not a free document")
    if record.get("docket_entry_number") != SUPPORT_DOCKET_ENTRY_NUMBER:
        raise SupportingDocumentSuccessorError(f"{label} has the wrong docket entry")
    if record.get("source_url") != SUPPORT_SOURCE_URL:
        raise SupportingDocumentSuccessorError(f"{label} has the wrong source URL")


def _require_matching_document_evidence(
    addition: Mapping[str, object],
    clearance: Mapping[str, object],
    restriction: Mapping[str, object],
) -> None:
    """Keep the three successor evidence rows bound to the same exact bytes."""

    for field in ("local_path", "sha256", "byte_count"):
        expected = addition.get(field)
        if expected is None or any(
            record.get(field) != expected for record in (clearance, restriction)
        ):
            raise SupportingDocumentSuccessorError(
                f"support memorandum {field} evidence differs"
            )


def _records(source: Mapping[str, object], field: str) -> tuple[JsonRecord, ...]:
    value = source.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SupportingDocumentSuccessorError(f"v2 projection lacks {field}")
    values = cast(Sequence[object], value)
    records: tuple[JsonRecord, ...] = tuple(
        dict(cast(Mapping[str, Any], record))
        for record in values
        if isinstance(record, Mapping)
    )
    if len(records) != len(values):
        raise SupportingDocumentSuccessorError(f"v2 projection has invalid {field}")
    return records


def _append_document_to_candidate(
    records: Sequence[JsonRecord], *, document: JsonRecord, label: str
) -> tuple[JsonRecord, ...]:
    matched = 0
    output: list[JsonRecord] = []
    for record in records:
        updated = dict(record)
        if updated.get("candidate_id") == SUPPORT_CANDIDATE_ID:
            matched += 1
            documents = updated.get("documents")
            if not isinstance(documents, list):
                raise SupportingDocumentSuccessorError(f"{label} lacks document ledger")
            if any(
                isinstance(item, Mapping)
                and cast(Mapping[str, object], item).get("source_document_id")
                == SUPPORT_DOCUMENT_ID
                for item in cast(list[object], documents)
            ):
                raise SupportingDocumentSuccessorError(
                    f"{label} already includes the support memorandum"
                )
            updated["documents"] = [*documents, document]
        output.append(updated)
    if matched != 1:
        raise SupportingDocumentSuccessorError(
            f"{label} lacks exactly one support-memorandum candidate"
        )
    return tuple(output)


def _selection_document(record: Mapping[str, object]) -> JsonRecord:
    return {
        "availability_status": "available",
        "candidate_id": SUPPORT_CANDIDATE_ID,
        "contains_target_outcome": False,
        "courtlistener_docket_entry_id": None,
        "description": "Memorandum of Law in Support",
        "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
        "document_role": SUPPORT_DOCUMENT_ROLE,
        "file_extension": "pdf",
        "is_available": True,
        "is_predecision_material": True,
        "is_private": False,
        "is_sealed": False,
        "model_visible": True,
        "redaction_or_seal_status": "public",
        "requires_paid_recovery": False,
        "resolved_from_paid_gap": False,
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "source_document_id": SUPPORT_DOCUMENT_ID,
        "source_provider": "courtlistener_public",
        "source_url": SUPPORT_SOURCE_URL,
        "source_url_or_reference": SUPPORT_SOURCE_URL,
    }


def _relevance_document(record: Mapping[str, object]) -> JsonRecord:
    return {
        "availability_status": "available",
        "candidate_id": SUPPORT_CANDIDATE_ID,
        "contains_target_outcome": False,
        "docket_entry_id": None,
        "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
        "docket_entry_text": "Memorandum of Law in Support",
        "document_role": SUPPORT_DOCUMENT_ROLE,
        "is_available": True,
        "is_private": False,
        "is_sealed": False,
        "model_visible": True,
        "redaction_or_seal_status": "public",
        "requires_paid_recovery": False,
        "resolved_from_paid_gap": False,
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "setup_runner_label": "core_mtd",
        "source_document_id": SUPPORT_DOCUMENT_ID,
        "source_url_or_reference": SUPPORT_SOURCE_URL,
    }


def _document_keys_from_selection(
    record: Mapping[str, object],
) -> tuple[DocumentKey, ...]:
    candidate_id = record.get("candidate_id")
    documents = record.get("documents")
    if not isinstance(candidate_id, str) or not isinstance(documents, list):
        raise SupportingDocumentSuccessorError("selected document ledger is malformed")
    keys: list[DocumentKey] = []
    for document in cast(list[object], documents):
        if not isinstance(document, Mapping):
            raise SupportingDocumentSuccessorError(
                "selected document ledger is malformed"
            )
        source_document_id = cast(Mapping[str, object], document).get(
            "source_document_id"
        )
        if not isinstance(source_document_id, str):
            raise SupportingDocumentSuccessorError("selected document ID is malformed")
        keys.append((candidate_id, source_document_id))
    return tuple(keys)


def _key(record: Mapping[str, object]) -> DocumentKey:
    candidate_id = record.get("candidate_id")
    source_document_id = record.get("source_document_id")
    if not isinstance(candidate_id, str) or not isinstance(source_document_id, str):
        raise SupportingDocumentSuccessorError("document identity is malformed")
    return candidate_id, source_document_id


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(
        canonical_json_bytes(
            dict(record),
            error_type=SupportingDocumentSuccessorError,
            error_message="supporting-document successor is not canonicalizable",
        )
        for record in records
    )

"""Core-document purchase filtering for setup-runner relevance output."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.acquisition_contract import (
    SetupRunnerDocumentLabel,
    contract_for_setup_runner_label,
    normalize_setup_runner_label,
)
from legalforecast.ingestion.docket_sync import classify_document_role
from legalforecast.ingestion.provenance import AvailabilityStatus, DocumentRole

_COMPLAINT_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
    }
)
_TARGET_MTD_ROLES = frozenset(
    {
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
    }
)
_MODEL_VISIBLE_SETUP_LABELS = frozenset(
    {
        SetupRunnerDocumentLabel.CORE_MTD,
        SetupRunnerDocumentLabel.CORE_EXHIBIT,
    }
)


@dataclass(frozen=True, slots=True)
class SetupRunnerDocumentRecord:
    """One setup-runner document relevance record."""

    candidate_id: str
    source_document_id: str
    setup_runner_label: SetupRunnerDocumentLabel
    document_role: DocumentRole
    docket_entry_id: str | None = None
    docket_entry_number: int | None = None
    docket_entry_text: str | None = None
    source_url_or_reference: str | None = None
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    requires_paid_recovery: bool = False
    document_role_inferred: bool = False

    @property
    def is_operative_complaint(self) -> bool:
        if self.document_role not in _COMPLAINT_ROLES:
            return False
        if not self.document_role_inferred:
            return True
        return _looks_like_operative_complaint_text(self.docket_entry_text)

    @property
    def is_target_mtd_record(self) -> bool:
        return self.document_role in _TARGET_MTD_ROLES

    @property
    def is_core_exhibit(self) -> bool:
        return self.setup_runner_label is SetupRunnerDocumentLabel.CORE_EXHIBIT

    @property
    def is_available_without_purchase(self) -> bool:
        return (
            self.availability_status is AvailabilityStatus.AVAILABLE
            and not self.requires_paid_recovery
        )

    @property
    def should_mount_in_model_packet(self) -> bool:
        if self.is_operative_complaint:
            return True
        contract = contract_for_setup_runner_label(self.setup_runner_label)
        return contract.model_visible_by_default

    @property
    def should_purchase_for_packet(self) -> bool:
        return (
            self.should_mount_in_model_packet
            or self.document_role in {DocumentRole.ORDER, DocumentRole.DECISION}
        ) and not self.is_available_without_purchase

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "setup_runner_label": self.setup_runner_label.value,
            "document_role": self.document_role.value,
            "docket_entry_id": self.docket_entry_id,
            "docket_entry_number": self.docket_entry_number,
            "docket_entry_text": self.docket_entry_text,
            "source_url_or_reference": self.source_url_or_reference,
            "availability_status": self.availability_status.value,
            "requires_paid_recovery": self.requires_paid_recovery,
            "is_operative_complaint": self.is_operative_complaint,
            "is_target_mtd_record": self.is_target_mtd_record,
            "should_mount_in_model_packet": self.should_mount_in_model_packet,
            "should_purchase_for_packet": self.should_purchase_for_packet,
        }


@dataclass(frozen=True, slots=True)
class CoreDocumentFilterResult:
    """Per-case setup-runner purchase plan and exclusion summary."""

    candidate_id: str
    purchase_document_ids: tuple[str, ...]
    core_mtd_documents: tuple[str, ...]
    core_exhibit_documents: tuple[str, ...]
    model_visible_document_ids: tuple[str, ...]
    operative_complaint_document_id: str | None
    operative_complaint_documents: tuple[str, ...]
    audit_only_document_ids: tuple[str, ...]
    core_missing_documents: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]

    @property
    def missing_operative_complaint(self) -> bool:
        return self.operative_complaint_document_id is None

    @property
    def excluded(self) -> bool:
        return bool(self.exclusion_reasons)

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "purchase_document_ids": list(self.purchase_document_ids),
            "core_mtd_documents": list(self.core_mtd_documents),
            "core_exhibit_documents": list(self.core_exhibit_documents),
            "model_visible_document_ids": list(self.model_visible_document_ids),
            "operative_complaint_document_id": self.operative_complaint_document_id,
            "operative_complaint_documents": list(self.operative_complaint_documents),
            "audit_only_document_ids": list(self.audit_only_document_ids),
            "core_missing_documents": list(self.core_missing_documents),
            "missing_operative_complaint": self.missing_operative_complaint,
            "exclusion_reasons": list(self.exclusion_reasons),
            "excluded": self.excluded,
        }


def filter_core_documents(
    records: Iterable[Mapping[str, Any]],
) -> tuple[CoreDocumentFilterResult, ...]:
    """Build per-case purchase plans from case-relevance JSONL records."""

    grouped: dict[str, list[SetupRunnerDocumentRecord]] = defaultdict(list)
    for document in iter_setup_runner_document_records(records):
        grouped[document.candidate_id].append(document)
    return tuple(
        _filter_candidate_documents(candidate_id, tuple(documents))
        for candidate_id, documents in sorted(grouped.items())
    )


def iter_setup_runner_document_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[SetupRunnerDocumentRecord, ...]:
    """Flatten flat or case-level setup-runner records into document records."""

    documents: list[SetupRunnerDocumentRecord] = []
    for record in records:
        parent_candidate_id = _optional_str(record, "candidate_id")
        nested = _document_sequence(record.get("documents"))
        if nested is not None:
            for nested_record in nested:
                documents.append(
                    _setup_runner_document_record(
                        nested_record,
                        parent_candidate_id=parent_candidate_id,
                    )
                )
            continue
        documents.append(
            _setup_runner_document_record(
                record,
                parent_candidate_id=parent_candidate_id,
            )
        )
    return tuple(documents)


def filter_core_documents_from_jsonl(
    jsonl_text: str,
) -> tuple[CoreDocumentFilterResult, ...]:
    """Build core-document filter results from in-memory case-relevance JSONL."""

    return filter_core_documents(_case_relevance_jsonl_records(jsonl_text.splitlines()))


def read_case_relevance_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read case-relevance JSONL records from disk."""

    with Path(path).open(encoding="utf-8") as handle:
        return _case_relevance_jsonl_records(handle)


def write_core_document_filter_results(
    results: Iterable[CoreDocumentFilterResult],
    path: str | Path,
) -> Path:
    """Write core-document filter results as stable JSONL."""

    output_path = Path(path)
    with output_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result.to_record(), sort_keys=True))
            handle.write("\n")
    return output_path


def _case_relevance_jsonl_records(lines: Iterable[str]) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        value: object = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row {line_number} must be an object")
        raw_record = cast(dict[object, object], value)
        if not all(isinstance(key, str) for key in raw_record):
            raise ValueError(f"JSONL row {line_number} keys must be strings")
        records.append(cast(dict[str, Any], raw_record))
    return tuple(records)


def _filter_candidate_documents(
    candidate_id: str,
    documents: tuple[SetupRunnerDocumentRecord, ...],
) -> CoreDocumentFilterResult:
    purchase_documents = tuple(
        document for document in documents if document.should_purchase_for_packet
    )
    model_visible_documents = tuple(
        document for document in documents if document.should_mount_in_model_packet
    )
    core_mtd_documents = tuple(
        document.source_document_id
        for document in documents
        if document.setup_runner_label is SetupRunnerDocumentLabel.CORE_MTD
    )
    core_exhibit_documents = tuple(
        document.source_document_id
        for document in documents
        if document.is_core_exhibit
    )
    operative_complaint_documents = tuple(
        document.source_document_id
        for document in documents
        if document.is_operative_complaint
    )
    model_visible_document_id_set = frozenset(
        document.source_document_id for document in model_visible_documents
    )
    return CoreDocumentFilterResult(
        candidate_id=candidate_id,
        purchase_document_ids=tuple(
            document.source_document_id for document in purchase_documents
        ),
        core_mtd_documents=core_mtd_documents,
        core_exhibit_documents=core_exhibit_documents,
        model_visible_document_ids=tuple(
            document.source_document_id for document in model_visible_documents
        ),
        operative_complaint_document_id=(
            operative_complaint_documents[0] if operative_complaint_documents else None
        ),
        operative_complaint_documents=operative_complaint_documents,
        audit_only_document_ids=tuple(
            document.source_document_id
            for document in documents
            if document.source_document_id not in model_visible_document_id_set
        ),
        core_missing_documents=tuple(
            document.source_document_id for document in purchase_documents
        ),
        exclusion_reasons=_exclusion_reasons(documents),
    )


def _exclusion_reasons(
    documents: tuple[SetupRunnerDocumentRecord, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not any(document.is_operative_complaint for document in documents):
        reasons.append("missing_operative_complaint")
    if not any(
        document.document_role is DocumentRole.MTD_MEMORANDUM
        and document.setup_runner_label in _MODEL_VISIBLE_SETUP_LABELS
        for document in documents
    ):
        reasons.append("missing_target_mtd_memorandum")
    return tuple(reasons)


def _setup_runner_document_record(
    record: Mapping[str, Any],
    *,
    parent_candidate_id: str | None,
) -> SetupRunnerDocumentRecord:
    candidate_id = _optional_str(record, "candidate_id") or parent_candidate_id
    if candidate_id is None:
        raise ValueError("candidate_id is required")
    docket_entry_text = _optional_str(record, "docket_entry_text") or _optional_str(
        record,
        "entry_text",
    )
    document_role, role_inferred = _document_role(record, docket_entry_text)
    return SetupRunnerDocumentRecord(
        candidate_id=candidate_id,
        source_document_id=_required_str_any(
            record,
            ("source_document_id", "document_id"),
        ),
        setup_runner_label=normalize_setup_runner_label(
            _required_str_any(
                record,
                ("setup_runner_label", "relevance_label", "label"),
            )
        ),
        document_role=document_role,
        docket_entry_id=_optional_str(record, "docket_entry_id"),
        docket_entry_number=_optional_int(record, "docket_entry_number")
        or _optional_int(record, "entry_number"),
        docket_entry_text=docket_entry_text,
        source_url_or_reference=_optional_str(record, "source_url_or_reference"),
        availability_status=_availability_status(record),
        requires_paid_recovery=_optional_bool(record, "requires_paid_recovery"),
        document_role_inferred=role_inferred,
    )


def _document_role(
    record: Mapping[str, Any],
    docket_entry_text: str | None,
) -> tuple[DocumentRole, bool]:
    role = _optional_str(record, "document_role")
    if role is not None:
        return DocumentRole(role), False
    if docket_entry_text is not None:
        return classify_document_role(docket_entry_text), True
    return DocumentRole.OTHER, True


def _availability_status(record: Mapping[str, Any]) -> AvailabilityStatus:
    status = _optional_str(record, "availability_status")
    if status is not None:
        return AvailabilityStatus(status)
    if _optional_bool(record, "requires_paid_recovery"):
        return AvailabilityStatus.UNAVAILABLE
    return AvailabilityStatus.AVAILABLE


def _looks_like_operative_complaint_text(text: str | None) -> bool:
    if text is None:
        return True
    normalized = " ".join(text.lower().split())
    if normalized.startswith(
        (
            "complaint",
            "amended complaint",
            "first amended complaint",
            "second amended complaint",
            "third amended complaint",
        )
    ):
        return True
    procedural_markers = (
        "notice",
        "deadline",
        "order",
        "summons",
        "certificate",
        "proof of service",
        "motion",
        "briefing",
    )
    return "complaint" in normalized and not any(
        marker in normalized for marker in procedural_markers
    )


def _document_sequence(value: object) -> tuple[Mapping[str, Any], ...] | None:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return None
    documents: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            return None
        documents.append(cast(Mapping[str, Any], item))
    return tuple(documents)


def _required_str_any(record: Mapping[str, Any], field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        value = _optional_str(record, field_name)
        if value is not None:
            return value
    joined = ", ".join(field_names)
    raise ValueError(f"one of {joined} is required")


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = value.strip()
    return stripped or None


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError(f"{field_name} must be an integer")


def _optional_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")

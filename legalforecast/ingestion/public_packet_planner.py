"""Plan free public document downloads for candidate MTD packets."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadRequest,
)
from legalforecast.ingestion.provenance import DocumentRole

_OPTIONAL_BRIEF_ROLES = frozenset(
    {CourtListenerEntryRole.OPPOSITION, CourtListenerEntryRole.REPLY}
)


@dataclass(frozen=True, slots=True)
class PublicPacketDocumentPlan:
    candidate_id: str
    source_document_id: str
    docket_entry_number: int | None
    document_role: DocumentRole
    source_url: str
    description: str
    model_visible: bool
    contains_target_outcome: bool

    def to_download_request(self) -> FreeDocumentDownloadRequest:
        return FreeDocumentDownloadRequest(
            candidate_id=self.candidate_id,
            source_provider="courtlistener",
            source_document_id=self.source_document_id,
            docket_entry_number=self.docket_entry_number,
            document_role=self.document_role,
            source_url=self.source_url,
            file_extension="pdf",
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url,
            "description": self.description,
            "model_visible": self.model_visible,
            "contains_target_outcome": self.contains_target_outcome,
        }


@dataclass(frozen=True, slots=True)
class PublicPacketCandidatePlan:
    candidate_id: str
    case_id: str
    case_name: str | None
    court: str | None
    docket_number: str | None
    source_url: str | None
    selected: bool
    exclusion_reasons: tuple[str, ...]
    target_motion_entry_numbers: tuple[int, ...]
    decision_entry_numbers: tuple[int, ...]
    documents: tuple[PublicPacketDocumentPlan, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "court": self.court,
            "docket_number": self.docket_number,
            "source_url": self.source_url,
            "selected": self.selected,
            "exclusion_reasons": list(self.exclusion_reasons),
            "target_motion_entry_numbers": list(self.target_motion_entry_numbers),
            "decision_entry_numbers": list(self.decision_entry_numbers),
            "documents": [document.to_record() for document in self.documents],
        }


@dataclass(frozen=True, slots=True)
class PublicPacketDownloadPlan:
    target_clean_cases: int
    allow_inferred_target_mtd: bool
    screened_case_count: int
    selected_case_count: int
    download_request_count: int
    candidate_plans: tuple[PublicPacketCandidatePlan, ...]

    @property
    def selected_cases(self) -> tuple[PublicPacketCandidatePlan, ...]:
        return tuple(plan for plan in self.candidate_plans if plan.selected)

    @property
    def download_requests(self) -> tuple[FreeDocumentDownloadRequest, ...]:
        return tuple(
            document.to_download_request()
            for plan in self.selected_cases
            for document in plan.documents
        )

    def summary_record(self) -> dict[str, Any]:
        return {
            "target_clean_cases": self.target_clean_cases,
            "allow_inferred_target_mtd": self.allow_inferred_target_mtd,
            "screened_case_count": self.screened_case_count,
            "selected_case_count": self.selected_case_count,
            "download_request_count": self.download_request_count,
            "shortfall": max(0, self.target_clean_cases - self.selected_case_count),
        }


def plan_public_packet_downloads(
    screened_case_records: Iterable[Mapping[str, Any]],
    *,
    raw_html_dir: str | Path | None = None,
    target_clean_cases: int = 25,
    allow_inferred_target_mtd: bool = False,
    use_embedded_entries: bool = False,
) -> PublicPacketDownloadPlan:
    """Select public/free packet candidates and emit document download requests."""

    if target_clean_cases <= 0:
        raise ValueError("target_clean_cases must be positive")
    if raw_html_dir is None and not use_embedded_entries:
        raise ValueError("raw_html_dir is required unless use_embedded_entries=True")
    html_root = Path(raw_html_dir) if raw_html_dir is not None else None
    candidate_plans: list[PublicPacketCandidatePlan] = []
    selected_count = 0
    for record in screened_case_records:
        plan = _candidate_plan(
            record,
            raw_html_dir=html_root,
            selected=selected_count < target_clean_cases,
            allow_inferred_target_mtd=allow_inferred_target_mtd,
            use_embedded_entries=use_embedded_entries,
        )
        if plan.selected:
            selected_count += 1
        candidate_plans.append(plan)
    selected_cases = tuple(plan for plan in candidate_plans if plan.selected)
    request_count = sum(len(plan.documents) for plan in selected_cases)
    return PublicPacketDownloadPlan(
        target_clean_cases=target_clean_cases,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
        screened_case_count=len(candidate_plans),
        selected_case_count=len(selected_cases),
        download_request_count=request_count,
        candidate_plans=tuple(candidate_plans),
    )


def _candidate_plan(
    record: Mapping[str, Any],
    *,
    raw_html_dir: Path | None,
    selected: bool,
    allow_inferred_target_mtd: bool,
    use_embedded_entries: bool,
) -> PublicPacketCandidatePlan:
    candidate = _mapping(record, "candidate")
    metadata = _mapping(candidate, "metadata")
    candidate_id = _required_str(candidate, "docket_id", "candidate_key")
    html_path = raw_html_dir / f"{candidate_id}.html" if raw_html_dir else None
    target_entries = _entry_number_tuple(
        _mapping(record, "ai").get("target_motion_entry_numbers")
    )
    decision_entries = _entry_number_tuple(
        _mapping(record, "ai").get("decision_entry_numbers")
    )
    source_url = _optional_str(candidate, "url")
    page: CourtListenerWebDocketPage | None = None
    if html_path is not None and html_path.exists():
        page = parse_courtlistener_docket_html(
            html_path.read_text(encoding="utf-8"),
            source_url=source_url,
            docket_id=candidate_id,
        )
    elif use_embedded_entries:
        page = _page_from_embedded_selected_entries(
            record,
            candidate_id=candidate_id,
            source_url=source_url,
        )
    if page is None:
        reason = (
            "embedded_entries_missing" if use_embedded_entries else "raw_html_missing"
        )
        return _excluded_plan(
            candidate_id,
            metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason=reason,
        )
    documents, reasons = _documents_for_candidate(
        candidate_id,
        page=page,
        target_entries=target_entries,
        decision_entries=decision_entries,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
    )
    return PublicPacketCandidatePlan(
        candidate_id=candidate_id,
        case_id=_optional_str(metadata, "case_id") or candidate_id,
        case_name=_optional_str(metadata, "case_name"),
        court=_optional_str(metadata, "court"),
        docket_number=_optional_str(metadata, "docket_number"),
        source_url=source_url,
        selected=selected and not reasons,
        exclusion_reasons=reasons,
        target_motion_entry_numbers=target_entries,
        decision_entry_numbers=decision_entries,
        documents=documents if not reasons else (),
    )


def _documents_for_candidate(
    candidate_id: str,
    *,
    page: CourtListenerWebDocketPage,
    target_entries: tuple[int, ...],
    decision_entries: tuple[int, ...],
    allow_inferred_target_mtd: bool,
) -> tuple[tuple[PublicPacketDocumentPlan, ...], tuple[str, ...]]:
    decision_floor = min(decision_entries) if decision_entries else _max_entry(page)
    complaint = _operative_complaint_entry(page, before_entry=decision_floor)
    target_mtd_entries = _target_mtd_entries(
        page,
        target_entries=target_entries,
        decision_floor=decision_floor,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
    )
    decision_entry_plans = _decision_entries(page, decision_entries=decision_entries)
    reasons: list[str] = []
    if complaint is None:
        reasons.append("no_free_operative_complaint")
    if not target_mtd_entries:
        reasons.append("no_free_target_mtd_document")
    if not decision_entry_plans:
        reasons.append("no_free_decision_document")
    if reasons:
        return (), tuple(reasons)
    assert complaint is not None
    documents: list[PublicPacketDocumentPlan] = [
        _document_plan(
            candidate_id,
            complaint,
            role=_complaint_role(complaint),
            model_visible=True,
            contains_target_outcome=False,
        )
    ]
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=_mtd_role(entry),
            model_visible=True,
            contains_target_outcome=False,
        )
        for entry in target_mtd_entries
    )
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=_brief_role(entry),
            model_visible=True,
            contains_target_outcome=False,
        )
        for entry in _optional_brief_entries(page, before_entry=decision_floor)
    )
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=DocumentRole.DECISION,
            model_visible=False,
            contains_target_outcome=True,
        )
        for entry in decision_entry_plans
    )
    return tuple(_dedupe_documents(documents)), ()


def _page_from_embedded_selected_entries(
    record: Mapping[str, Any],
    *,
    candidate_id: str,
    source_url: str | None,
) -> CourtListenerWebDocketPage | None:
    entries_value = record.get("selected_entries")
    if not isinstance(entries_value, Sequence) or isinstance(entries_value, str):
        return None
    entry_records = (
        cast(Mapping[str, Any], entry_record)
        for entry_record in cast(Sequence[object], entries_value)
        if isinstance(entry_record, Mapping)
    )
    entries = tuple(
        _entry_from_embedded_record(entry_record) for entry_record in entry_records
    )
    if not entries:
        return None
    return CourtListenerWebDocketPage(
        docket_id=candidate_id,
        source_url=source_url,
        title=None,
        entries=_dedupe_entries(entries),
        has_next_page=False,
    )


def _entry_from_embedded_record(
    record: Mapping[str, Any],
) -> CourtListenerWebDocketEntry:
    documents_value = record.get("documents")
    documents: tuple[CourtListenerWebDocument, ...] = ()
    if isinstance(documents_value, Sequence) and not isinstance(documents_value, str):
        document_records = (
            cast(Mapping[str, Any], document_record)
            for document_record in cast(Sequence[object], documents_value)
            if isinstance(document_record, Mapping)
        )
        documents = tuple(
            _document_from_embedded_record(document_record)
            for document_record in document_records
        )
    return CourtListenerWebDocketEntry(
        row_id=_optional_str(record, "row_id") or "",
        entry_number=_optional_str(record, "entry_number"),
        filed_at=_optional_str(record, "filed_at"),
        text=_optional_str(record, "text") or "",
        documents=documents,
    )


def _document_from_embedded_record(
    record: Mapping[str, Any],
) -> CourtListenerWebDocument:
    return CourtListenerWebDocument(
        kind=_optional_str(record, "kind") or "",
        description=_optional_str(record, "description") or "",
        href=_optional_str(record, "href"),
        action_label=_optional_str(record, "action_label"),
        pacer_only=bool(record.get("pacer_only", False)),
    )


def _dedupe_entries(
    entries: Iterable[CourtListenerWebDocketEntry],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[CourtListenerWebDocketEntry] = []
    for entry in entries:
        key = (entry.row_id, entry.entry_number, entry.text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return tuple(deduped)


def _operative_complaint_entry(
    page: CourtListenerWebDocketPage,
    *,
    before_entry: int | None,
) -> CourtListenerWebDocketEntry | None:
    candidates = [
        entry
        for entry in page.entries
        if _entry_is_before(entry, before_entry) and _looks_like_complaint(entry)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda entry: _entry_number(entry) or -1)[-1]


def _target_mtd_entries(
    page: CourtListenerWebDocketPage,
    *,
    target_entries: tuple[int, ...],
    decision_floor: int | None,
    allow_inferred_target_mtd: bool,
) -> tuple[CourtListenerWebDocketEntry, ...]:
    exact = tuple(
        entry
        for entry in page.entries
        if _entry_number(entry) in set(target_entries) and _is_mtd_entry(entry)
    )
    if exact or not allow_inferred_target_mtd:
        return exact
    return tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, decision_floor) and _is_mtd_entry(entry)
    )


def _optional_brief_entries(
    page: CourtListenerWebDocketPage,
    *,
    before_entry: int | None,
) -> tuple[CourtListenerWebDocketEntry, ...]:
    return tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, before_entry) and _is_optional_brief_entry(entry)
    )


def _decision_entries(
    page: CourtListenerWebDocketPage,
    *,
    decision_entries: tuple[int, ...],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    exact = tuple(
        entry
        for entry in page.entries
        if _entry_number(entry) in set(decision_entries)
        and _best_free_document(entry, DocumentRole.DECISION) is not None
    )
    if decision_entries:
        return exact
    return tuple(
        entry
        for entry in page.entries
        if _is_decision_entry(entry)
        and _best_free_document(entry, DocumentRole.DECISION) is not None
    )


def _document_plan(
    candidate_id: str,
    entry: CourtListenerWebDocketEntry,
    *,
    role: DocumentRole,
    model_visible: bool,
    contains_target_outcome: bool,
) -> PublicPacketDocumentPlan:
    document = _best_free_document(entry, role)
    if document is None:
        raise ValueError(f"entry has no free document for role: {role.value}")
    entry_number = _entry_number(entry)
    source_document_id = (
        f"entry-{entry.entry_number or 'unknown'}-{role.value}".replace("_", "-")
    )
    return PublicPacketDocumentPlan(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        docket_entry_number=entry_number,
        document_role=role,
        source_url=document.href or "",
        description=document.description,
        model_visible=model_visible,
        contains_target_outcome=contains_target_outcome,
    )


def _dedupe_documents(
    documents: Iterable[PublicPacketDocumentPlan],
) -> tuple[PublicPacketDocumentPlan, ...]:
    seen: set[str] = set()
    deduped: list[PublicPacketDocumentPlan] = []
    for document in documents:
        key = document.source_url
        if key in seen:
            continue
        seen.add(key)
        deduped.append(document)
    return tuple(deduped)


def _excluded_plan(
    candidate_id: str,
    metadata: Mapping[str, Any],
    *,
    source_url: str | None,
    target_entries: tuple[int, ...],
    decision_entries: tuple[int, ...],
    reason: str,
) -> PublicPacketCandidatePlan:
    return PublicPacketCandidatePlan(
        candidate_id=candidate_id,
        case_id=_optional_str(metadata, "case_id") or candidate_id,
        case_name=_optional_str(metadata, "case_name"),
        court=_optional_str(metadata, "court"),
        docket_number=_optional_str(metadata, "docket_number"),
        source_url=source_url,
        selected=False,
        exclusion_reasons=(reason,),
        target_motion_entry_numbers=target_entries,
        decision_entry_numbers=decision_entries,
        documents=(),
    )


def _complaint_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    return (
        DocumentRole.AMENDED_COMPLAINT
        if _best_free_document(entry, DocumentRole.AMENDED_COMPLAINT) is not None
        else DocumentRole.COMPLAINT
    )


def _mtd_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    return (
        DocumentRole.MTD_MEMORANDUM
        if _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
        else DocumentRole.MTD_NOTICE
    )


def _brief_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    if entry.role is CourtListenerEntryRole.REPLY:
        return DocumentRole.REPLY
    return DocumentRole.OPPOSITION


def _looks_like_complaint(entry: CourtListenerWebDocketEntry) -> bool:
    if (
        _best_free_document(entry, DocumentRole.COMPLAINT) is not None
        or _best_free_document(entry, DocumentRole.AMENDED_COMPLAINT) is not None
    ):
        return True
    text = entry.text.lower()
    if re.search(r"\banswer\s+to\s+(?:amended\s+)?complaint\b", text):
        return False
    if _contains_procedural_complaint_reference(text):
        return False
    return bool(
        re.match(
            r"^\s*\d*\s*(?:[a-z]{3,9}\s+\d{1,2},\s+\d{4}\s+)?"
            r"(?:amended\s+)?complaint\s+(?:against|filed|by|with)\b",
            text,
        )
        or re.search(r"\bnotice\s+of\s+removal\s+from\b", text)
    )


def _is_mtd_entry(entry: CourtListenerWebDocketEntry) -> bool:
    if entry.role not in {
        CourtListenerEntryRole.MTD_NOTICE,
        CourtListenerEntryRole.MTD_MEMORANDUM,
    }:
        return False
    return (
        _best_free_document(entry, DocumentRole.MTD_NOTICE) is not None
        or _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
    )


def _is_optional_brief_entry(entry: CourtListenerWebDocketEntry) -> bool:
    if entry.role not in _OPTIONAL_BRIEF_ROLES:
        return False
    role = _brief_role(entry)
    if _best_free_document(entry, role) is None:
        return False
    descriptions = _document_descriptions(entry)
    text = entry.text.lower()
    if re.search(r"\b(?:scheduling|extension|notice|order)\b", descriptions):
        return False
    opposition_pattern = (
        r"\b(?:opposition|response in opposition|brief in opposition)\b"
    )
    return bool(
        re.search(opposition_pattern, descriptions)
        or re.search(r"\breply(?: memorandum| brief)?\b", descriptions)
        or re.search(opposition_pattern, text)
        or re.search(r"\breply(?: memorandum| brief)?\b", text)
    )


def _is_decision_entry(entry: CourtListenerWebDocketEntry) -> bool:
    descriptions = _document_descriptions(entry)
    text = entry.text.lower()
    return bool(
        entry.role is CourtListenerEntryRole.DECISION
        or "order on motion to dismiss" in descriptions
        or "order on motion to dismiss" in text
    )


def _document_descriptions(entry: CourtListenerWebDocketEntry) -> str:
    return " ".join(document.description for document in entry.documents).lower()


def _best_free_document(
    entry: CourtListenerWebDocketEntry,
    role: DocumentRole,
):
    matching_documents = tuple(
        document
        for document in entry.documents
        if document.freely_available
        and document.href
        and _document_matches_role(document.description, role)
    )
    if matching_documents:
        return matching_documents[0]
    if role is DocumentRole.DECISION:
        return next(
            (
                document
                for document in entry.documents
                if document.freely_available and document.href
            ),
            None,
        )
    return None


def _document_matches_role(description: str, role: DocumentRole) -> bool:
    text = " ".join(description.lower().split())
    if not text and role is DocumentRole.MTD_NOTICE:
        return False
    if role is DocumentRole.COMPLAINT:
        return _looks_like_complaint_document_description(text, amended=False)
    if role is DocumentRole.AMENDED_COMPLAINT:
        return _looks_like_complaint_document_description(text, amended=True)
    if role is DocumentRole.MTD_NOTICE:
        return bool(
            (
                re.search(r"\b(?:motion\s+to\s+)?dismiss(?:al)?\b", text)
                or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text)
            )
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.MTD_MEMORANDUM:
        return bool(
            re.search(r"\b(?:memorandum|brief)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.OPPOSITION:
        return bool(
            re.search(r"\b(?:opposition|response\s+in\s+opposition)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.REPLY:
        return bool(
            re.search(r"\breply\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.DECISION:
        return bool(
            re.search(r"\b(?:order|opinion|decision|judgment)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    return False


def _looks_like_complaint_document_description(text: str, *, amended: bool) -> bool:
    if not text:
        return False
    if _contains_procedural_complaint_reference(text):
        return False
    if amended:
        if "alleged in" in text or "timeline" in text:
            return False
        return bool(
            re.fullmatch(
                r"(?:exhibit\s+)?(?:exh\s+[a-z0-9]+\s+)?"
                r"(?:(?:first|second|third)\s+)?amended complaint",
                text,
            )
        )
    return text in {
        "civil case - complaint",
        "complaint",
        "notice of removal",
        "notice of removal (attorney civil case opening)",
    }


def _contains_procedural_complaint_reference(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:answer|extension|initial order|standing order|order|stipulation|"
            r"proposed|summons|service|notice of appearance|cover sheet|certificate|"
            r"motion|deadline|responsive pleading)\b",
            text,
        )
    )


def _contains_non_merits_motion_marker(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:extension|adjourn|appear pro hac|appearance|withdraw|serve|"
            r"subpoena|discovery|scheduling|proposed order|stipulation|notice)\b",
            text,
        )
    )


def _entry_number(entry: CourtListenerWebDocketEntry) -> int | None:
    if entry.entry_number is None:
        return None
    match = re.match(r"\d+", entry.entry_number)
    return int(match.group(0)) if match is not None else None


def _entry_is_before(
    entry: CourtListenerWebDocketEntry,
    before_entry: int | None,
) -> bool:
    entry_number = _entry_number(entry)
    return entry_number is not None and (
        before_entry is None or entry_number < before_entry
    )


def _max_entry(page: CourtListenerWebDocketPage) -> int | None:
    numbers = [_entry_number(entry) for entry in page.entries]
    present = [number for number in numbers if number is not None]
    return max(present) if present else None


def _entry_number_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, int):
            numbers.append(item)
            continue
        if isinstance(item, str) and item.strip().isdigit():
            numbers.append(int(item.strip()))
    return tuple(numbers)


def _mapping(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = record.get(key)
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _required_str(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    joined = ", ".join(keys)
    raise ValueError(f"record missing required string field: {joined}")


def _optional_str(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value.strip() else None

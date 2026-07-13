"""Strict operative-complaint selection for CourtListener docket records."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
)


class OperativeComplaintKind(StrEnum):
    """Pleading role established by affirmative docket evidence."""

    COMPLAINT = "complaint"
    AMENDED_COMPLAINT = "amended_complaint"


@dataclass(frozen=True, slots=True)
class OperativeComplaintSelection:
    """A strictly identified pre-motion pleading entry and its role."""

    entry: CourtListenerWebDocketEntry
    kind: OperativeComplaintKind


def select_operative_complaint_entry(
    entries: Iterable[CourtListenerWebDocketEntry],
    *,
    before_entry: int,
) -> OperativeComplaintSelection | None:
    """Return the latest affirmative pleading filing before the target motion."""

    candidates: list[
        tuple[int, CourtListenerWebDocketEntry, OperativeComplaintKind]
    ] = []
    for entry in entries:
        number = _positive_entry_number(entry.entry_number)
        if number is None or number >= before_entry:
            continue
        kind = _complaint_entry_kind(entry)
        if kind is not None:
            candidates.append((number, entry, kind))
    if not candidates:
        return None
    _, entry, kind = max(candidates, key=lambda item: item[0])
    return OperativeComplaintSelection(entry=entry, kind=kind)


def select_operative_complaint_document(
    entry: CourtListenerWebDocketEntry,
    *,
    require_free: bool,
) -> CourtListenerWebDocument | None:
    """Select one exact pleading document without relying on generic mentions."""

    text = _normalized(entry.text)
    if _is_removal_entry(text):
        removal_pleadings = _removal_pleading_documents(entry.documents)
        if len(removal_pleadings) != 1:
            return None
        pleading = removal_pleadings[0]
        return pleading if not require_free or pleading.freely_available else None

    available = tuple(
        document
        for document in entry.documents
        if not require_free or document.freely_available
    )
    described = tuple(
        document
        for document in available
        if _complaint_document_kind(document.description) is not None
    )
    if len(described) == 1:
        return described[0]
    if len(described) > 1:
        amended = tuple(
            document
            for document in described
            if _complaint_document_kind(document.description)
            is OperativeComplaintKind.AMENDED_COMPLAINT
        )
        return amended[0] if len(amended) == 1 else None

    main_documents = tuple(
        document for document in available if "main" in _normalized(document.kind)
    )
    if len(main_documents) == 1 and _complaint_entry_kind(entry) is not None:
        return main_documents[0]
    return None


def _complaint_entry_kind(
    entry: CourtListenerWebDocketEntry,
) -> OperativeComplaintKind | None:
    text = _normalized(entry.text)
    if re.search(r"\banswer\s+to\s+(?:amended\s+)?complaint\b", text):
        return None
    procedural_pattern = (
        r"\b(?:answer to|order|opinion|memorandum decision|memo endorsement|"
        r"motion to|certificate|summons|notice of appearance)\b"
    )
    descriptions = tuple(
        kind
        for document in entry.documents
        if (kind := _complaint_document_kind(document.description)) is not None
    )
    filing_match = re.search(
        r"\b(?:(?P<amended>(?:(?:first|second|third)\s+)?amended)\s+)?"
        r"(?:pro\s+se\s+)?(?:transferred\s*)?complaint\s*"
        r"(?:against|filed|by|with)\b",
        text,
    )
    if filing_match is not None:
        if re.search(procedural_pattern, text[: filing_match.start()]):
            return None
        return (
            OperativeComplaintKind.AMENDED_COMPLAINT
            if filing_match.group("amended") is not None
            else OperativeComplaintKind.COMPLAINT
        )
    if re.search(r"\bcivil case - complaint, amended\s+filed\b", text):
        return OperativeComplaintKind.AMENDED_COMPLAINT
    described_main = tuple(
        kind
        for document in entry.documents
        if "main" in _normalized(document.kind)
        and (kind := _complaint_document_kind(document.description)) is not None
    )
    if len(described_main) == 1 and not re.search(procedural_pattern, text):
        return described_main[0]
    removal_documents = _removal_pleading_documents(entry.documents)
    if _is_removal_entry(text) and len(removal_documents) == 1:
        return (
            OperativeComplaintKind.AMENDED_COMPLAINT
            if OperativeComplaintKind.AMENDED_COMPLAINT in descriptions
            else OperativeComplaintKind.COMPLAINT
        )
    return None


def _complaint_document_kind(description: str) -> OperativeComplaintKind | None:
    text = _normalized(description)
    if re.fullmatch(
        r"(?:civil case - )?(?:(?:first|second|third)\s+)?amended complaint"
        r"|civil case - complaint, amended",
        text,
    ):
        return OperativeComplaintKind.AMENDED_COMPLAINT
    if re.fullmatch(
        r"(?:civil case - )?complaint"
        r"|pro se complaint"
        r"|complaint - pro se"
        r"|complaint \(removal/transfer\) - court use only",
        text,
    ):
        return OperativeComplaintKind.COMPLAINT
    return None


def _is_removal_entry(text: str) -> bool:
    return bool(
        re.search(r"^(?:\d+\s+)?notice of removal\b", text)
        or re.search(r"\bnotice of removal from\b", text)
        or re.search(r"\bnotice of removal with jury demand\b", text)
        or re.search(r"\bpetition \(removal/transfer\) received from\b", text)
    )


def _removal_pleading_documents(
    documents: Iterable[CourtListenerWebDocument],
) -> tuple[CourtListenerWebDocument, ...]:
    candidates = tuple(documents)
    explicit = tuple(
        document
        for document in candidates
        if _complaint_document_kind(document.description) is not None
        or _looks_like_removal_petition_attachment(document.description)
    )
    if explicit:
        return explicit
    return tuple(
        document
        for document in candidates
        if _looks_like_generic_removal_exhibit(document.description)
    )


def _looks_like_removal_petition_attachment(description: str) -> bool:
    text = _normalized(description)
    return bool(
        re.fullmatch(
            r"(?:original\s+)?petition"
            r"|(?:exhibit(?:\(s\))?|exh\.?)\s+[a-z0-9]+\s*-\s*"
            r"(?:original\s+)?petition",
            text,
        )
    )


def _looks_like_generic_removal_exhibit(description: str) -> bool:
    text = _normalized(description)
    if re.search(r"\b(?:civil cover sheet|certificate|notice|summons|service)\b", text):
        return False
    return bool(
        re.fullmatch(r"(?:exhibit|exh\.?)\s+[a-z0-9](?:\s*-\s*[a-z0-9])?", text)
    )


def _positive_entry_number(value: str | None) -> int | None:
    if value is None or not value.strip().isdigit():
        return None
    number = int(value)
    return number if number > 0 else None


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())

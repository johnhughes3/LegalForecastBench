"""Strict operative-complaint selection for CourtListener docket records."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
    explicit_motion_reference_numbers,
)


class OperativeComplaintKind(StrEnum):
    """Pleading role established by affirmative docket evidence.

    ``other_claim_bearing_filing`` is the cohort-policy v3 fallback role for a
    claim-bearing pleading whose docket label does not match one of the named
    kinds. Docket-label recognition never infers it; it exists so an approved
    repair slot can request that role and still have its bytes validated.
    """

    COMPLAINT = "complaint"
    AMENDED_COMPLAINT = "amended_complaint"
    COUNTERCLAIM = "counterclaim"
    CROSSCLAIM = "crossclaim"
    THIRD_PARTY_COMPLAINT = "third_party_complaint"
    INTERPLEADER_COMPLAINT = "interpleader_complaint"
    OTHER_CLAIM_BEARING_FILING = "other_claim_bearing_filing"


@dataclass(frozen=True, slots=True)
class OperativeComplaintSelection:
    """A strictly identified pre-motion pleading entry and its role."""

    entry: CourtListenerWebDocketEntry
    kind: OperativeComplaintKind


def motion_attacked_entry_numbers(
    entries: Iterable[CourtListenerWebDocketEntry],
    *,
    target_entry_numbers: Iterable[int],
) -> frozenset[int]:
    """Return the docket entries the target motions explicitly name.

    A motion to dismiss cites the pleading it attacks by entry number. Those
    citations are the only affirmative evidence on the docket of which
    pleading is actually under attack, so they are collected from the target
    motion rows only — never from arbitrary later filings.
    """

    targets = frozenset(target_entry_numbers)
    cited: set[int] = set()
    for entry in entries:
        number = _positive_entry_number(entry.entry_number)
        if number is None or number not in targets:
            continue
        cited.update(explicit_motion_reference_numbers(entry))
    return frozenset(cited)


def select_operative_complaint_entry(
    entries: Iterable[CourtListenerWebDocketEntry],
    *,
    before_entry: int,
    body_text_by_entry: Mapping[int, str] | None = None,
    attacked_entry_numbers: Iterable[int] | None = None,
) -> OperativeComplaintSelection | None:
    """Return the pleading the target motion attacks, else the latest one.

    When authenticated extracted body text is supplied, every docket-label
    candidate must have matching body evidence. Docket ``narrative_text`` is
    intentionally not used because it is row metadata, not document content.

    ``attacked_entry_numbers`` carries the entries the target motion
    explicitly names (see :func:`motion_attacked_entry_numbers`). When any
    candidate pleading is among them, selection is restricted to those
    candidates, so a later counterclaim no longer displaces the earlier
    complaint the motion is actually attacking. When the motion names no
    candidate pleading — an unnumbered or purely narrative reference — the
    latest pre-motion pleading remains the fallback rather than a refusal,
    because that is the pre-existing behaviour the exact-100 goldens pin.
    """

    candidates: list[
        tuple[int, CourtListenerWebDocketEntry, OperativeComplaintKind]
    ] = []
    for entry in entries:
        number = _positive_entry_number(entry.entry_number)
        if number is None or number >= before_entry:
            continue
        kind = _complaint_entry_kind(entry)
        if kind is None:
            continue
        if body_text_by_entry is not None:
            body = body_text_by_entry.get(number)
            if body is None or not pleading_body_matches_kind(body, kind):
                continue
        candidates.append((number, entry, kind))
    if not candidates:
        return None
    if attacked_entry_numbers is not None:
        attacked = frozenset(attacked_entry_numbers)
        directly_attacked = [
            candidate for candidate in candidates if candidate[0] in attacked
        ]
        if directly_attacked:
            candidates = directly_attacked
    _, entry, kind = max(candidates, key=lambda item: item[0])
    return OperativeComplaintSelection(entry=entry, kind=kind)


def select_operative_complaint_document(
    entry: CourtListenerWebDocketEntry,
    *,
    require_free: bool,
) -> CourtListenerWebDocument | None:
    """Select one exact pleading document without relying on generic mentions."""

    text = _normalized(entry.text)
    if _is_removal_entry(text, entry.documents):
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


def pleading_body_matches_kind(
    body: str,
    kind: OperativeComplaintKind,
) -> bool:
    """Return whether observed document text can satisfy a pleading label.

    Docket labels remain useful discovery evidence, but obvious form bytes such
    as summonses and civil cover sheets cannot be admitted as claim pleadings.
    """

    text = _normalized(body)
    if not text:
        return False
    if re.search(
        r"\bao\s*440\b|\bsummons\s+in\s+a\s+civil\s+action\b|"
        r"\bproof\s+of\s+service\b|\bcivil\s+cover\s+sheet\b|"
        r"\badversary\s+proceeding\s+cover\s+sheet\b|\bofficial\s+form\s+1040\b",
        text,
    ):
        return False
    patterns = {
        OperativeComplaintKind.COMPLAINT: r"\bcomplaint\b",
        OperativeComplaintKind.AMENDED_COMPLAINT: (
            r"\b(?:(?:first|second|third)\s+)?amended\s+complaint\b"
        ),
        OperativeComplaintKind.COUNTERCLAIM: r"\bcounterclaims?\b",
        OperativeComplaintKind.CROSSCLAIM: r"\bcross-?claims?\b",
        OperativeComplaintKind.THIRD_PARTY_COMPLAINT: (r"\bthird-?party\s+complaint\b"),
        OperativeComplaintKind.INTERPLEADER_COMPLAINT: (
            r"\binterpleader(?:\s+(?:complaint|counterclaim))?\b"
        ),
    }
    if kind is OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING:
        # Generic motions routinely discuss another party's claims and close
        # with a prayer to dismiss them.  The fallback therefore requires a
        # claim-bearing filing title as well as affirmative claim or prayer
        # language attributable to that filing.
        title_lines = tuple(
            line.strip().lower() for line in body.splitlines()[:80] if line.strip()
        )
        has_claim_bearing_title = any(
            re.search(
                r"^(?:(?:(?:first|second|third)\s+)?amended\s+)?"
                r"(?:petition\b|statement\s+of\s+claim\b|claim\s+for\s+relief\b|"
                r"complaint\s+in\s+intervention\b|plea\s+in\s+intervention\b)",
                line,
            )
            for line in title_lines
        )
        asserts_claim = re.search(
            r"\b(?:(?:first|second|third|fourth|fifth|\d+(?:st|nd|rd|th))\s+)?"
            r"cause\s+of\s+action\b|\bclaims?\s+for\s+relief\b|"
            r"\bprayer\s+for\s+relief\b|\bwherefore\b.{0,160}?"
            r"\b(?:petitioner|claimant|intervenor|plaintiff)\s+"
            r"(?:prays?|requests?|demands?)\b",
            text,
        )
        return has_claim_bearing_title and asserts_claim is not None
    if kind is OperativeComplaintKind.COMPLAINT and re.search(
        patterns[OperativeComplaintKind.AMENDED_COMPLAINT], text
    ):
        return False
    return re.search(patterns[kind], text) is not None


def _complaint_entry_kind(
    entry: CourtListenerWebDocketEntry,
) -> OperativeComplaintKind | None:
    text = _normalized(entry.text)
    claim_kind = _non_complaint_claim_kind(text)
    if claim_kind is not None:
        return claim_kind
    if re.search(r"\banswer\s+to\s+(?:amended\s+)?complaint\b", text):
        return None
    procedural_pattern = (
        r"\b(?:answer to|order|opinion|memorandum decision|memo endorsement|"
        r"motion (?:to|for)|reply|response|stipulation|extension|letter|"
        r"certificate|certification|summons|minute entry|clerk'?s notice|"
        r"notice)\b"
    )
    descriptions = tuple(
        kind
        for document in entry.documents
        if (kind := _complaint_document_kind(document.description)) is not None
    )
    if re.search(r"\bcivil case - complaint, amended\s+filed\b", text):
        return OperativeComplaintKind.AMENDED_COMPLAINT
    filing_match = re.search(
        r"\b(?:(?P<amended>(?:(?:first|second|third)\s+)?amended)\s+)?"
        r"(?:pro\s+se\s+)?(?:transferred\s*)?complaint\s*"
        r"(?:\(\s*verified\s*\)\s*)?"
        r"(?:against|filed|by|with|to\s+filed)\b",
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
    if re.fullmatch(r"(?:\d+\s+)?(?:adversary\s+)?complaint\s*\(fee\)", text):
        return OperativeComplaintKind.COMPLAINT
    described_main = tuple(
        kind
        for document in entry.documents
        if "main" in _normalized(document.kind)
        and (kind := _complaint_document_kind(document.description)) is not None
    )
    if len(described_main) == 1:
        described_filing_match = re.search(
            r"\b(?:complaint|(?:(?:first|second|third)\s+)?amended complaint)\b"
            r".{0,300}?(?:against|filed|by|with|to\s+filed)\b",
            text,
        )
        if described_filing_match is not None and not re.search(
            procedural_pattern, text[: described_filing_match.start()]
        ):
            return described_main[0]
        if not re.search(procedural_pattern, text):
            return described_main[0]
    removal_documents = _removal_pleading_documents(entry.documents)
    if _is_removal_entry(text, entry.documents) and len(removal_documents) == 1:
        return _removal_pleading_document_kind(removal_documents[0].description) or (
            OperativeComplaintKind.AMENDED_COMPLAINT
            if OperativeComplaintKind.AMENDED_COMPLAINT in descriptions
            else OperativeComplaintKind.COMPLAINT
        )
    return None


def _complaint_document_kind(description: str) -> OperativeComplaintKind | None:
    text = _normalized(description)
    claim_kind = _non_complaint_claim_kind(text)
    if claim_kind is not None:
        return claim_kind
    if re.fullmatch(
        r"(?:civil case - )?(?:(?:first|second|third)\s+)?amended complaint"
        r"|civil case - complaint, amended",
        text,
    ):
        return OperativeComplaintKind.AMENDED_COMPLAINT
    if re.fullmatch(
        r"(?:civil case - )?complaint"
        r"|(?:adversary\s+)?complaint\s*\(fee\)"
        r"|adversary complaint"
        r"|pro se complaint"
        r"|complaint - pro se"
        r"|attorney complaint \(credit card required\)"
        r"|complaint \(removal/transfer\) - court use only",
        text,
    ):
        return OperativeComplaintKind.COMPLAINT
    return None


def _non_complaint_claim_kind(text: str) -> OperativeComplaintKind | None:
    patterns = (
        (OperativeComplaintKind.CROSSCLAIM, r"\bcross-?claims?\b"),
        (OperativeComplaintKind.COUNTERCLAIM, r"\bcounterclaims?\b"),
        (
            OperativeComplaintKind.THIRD_PARTY_COMPLAINT,
            r"\bthird-?party\s+complaint\b",
        ),
        (
            OperativeComplaintKind.INTERPLEADER_COMPLAINT,
            r"\binterpleader(?:\s+(?:complaint|counterclaim))?\b",
        ),
    )
    for kind, pattern in patterns:
        if re.search(pattern, text):
            return kind
    return None


def _is_removal_entry(
    text: str,
    documents: Iterable[CourtListenerWebDocument] = (),
) -> bool:
    if bool(
        re.search(r"^(?:\d+\s+)?notice of removal\b", text)
        or re.search(r"\bnotice of removal from\b", text)
        or re.search(r"\bnotice of removal with jury demand\b", text)
        or re.search(r"\bpetition \(removal/transfer\) received from\b", text)
    ):
        return True
    return bool(
        re.search(r"\bnotice of removal\b", text)
        and any(
            "main" in _normalized(document.kind)
            and _normalized(document.description) == "notice of removal"
            for document in documents
        )
    )


def _removal_pleading_documents(
    documents: Iterable[CourtListenerWebDocument],
) -> tuple[CourtListenerWebDocument, ...]:
    candidates = tuple(documents)
    explicit = tuple(
        document
        for document in candidates
        if _removal_pleading_document_kind(document.description) is not None
    )
    if explicit:
        return explicit
    return tuple(
        document
        for document in candidates
        if _looks_like_generic_removal_exhibit(document.description)
    )


def _removal_pleading_document_kind(
    description: str,
) -> OperativeComplaintKind | None:
    direct_kind = _complaint_document_kind(description)
    if direct_kind is not None:
        return direct_kind
    text = _normalized(description)
    match = re.fullmatch(
        r"(?:original\s+)?(?P<direct>petition|complaint)"
        r"|(?:exhibit(?:\(s\))?|exh\.?)\s+[a-z0-9]+\s*-\s*"
        r"(?:original\s+)?(?P<exhibit>petition|"
        r"(?:(?:first|second|third)\s+)?amended complaint|complaint)",
        text,
    )
    if match is None:
        return None
    exhibit = match.group("exhibit")
    return (
        OperativeComplaintKind.AMENDED_COMPLAINT
        if exhibit is not None and exhibit.endswith("amended complaint")
        else OperativeComplaintKind.COMPLAINT
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

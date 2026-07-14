"""Deterministic linkage between MTD docket entries and dispositions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.ingestion.docket_sync import (
    DocketRetrievalResult,
    NormalizedDocketEntry,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionStage,
)


class MotionLinkageExclusionReason(StrEnum):
    NO_TARGET_MOTION = "no_target_motion"
    NO_WRITTEN_DISPOSITION = "no_written_disposition"
    AMBIGUOUS_MOTION_TO_ORDER_LINKAGE = "ambiguous_motion_to_order_linkage"


@dataclass(frozen=True, slots=True)
class MotionDispositionLink:
    """A clean link between target MTD entry or entries and disposition entries."""

    candidate_id: str
    case_id: str
    motion_entry_ids: tuple[str, ...]
    disposition_entry_ids: tuple[str, ...]
    linkage_basis: tuple[str, ...]
    contains_non_mtd_relief: bool = False
    includes_report_and_recommendation: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty_tuple(self.motion_entry_ids, "motion_entry_ids")
        _require_non_empty_tuple(
            self.disposition_entry_ids,
            "disposition_entry_ids",
        )
        _require_non_empty_tuple(self.linkage_basis, "linkage_basis")

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "motion_entry_ids": list(self.motion_entry_ids),
            "disposition_entry_ids": list(self.disposition_entry_ids),
            "linkage_basis": list(self.linkage_basis),
            "contains_non_mtd_relief": self.contains_non_mtd_relief,
            "includes_report_and_recommendation": (
                self.includes_report_and_recommendation
            ),
        }


@dataclass(frozen=True, slots=True)
class MotionLinkageResult:
    """Motion-to-disposition links plus exclusion-ledger entries."""

    candidate_id: str
    case_id: str
    links: tuple[MotionDispositionLink, ...]
    exclusion_entries: tuple[ExclusionLedgerEntry, ...] = ()

    @property
    def is_clean(self) -> bool:
        return bool(self.links) and not self.exclusion_entries

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "is_clean": self.is_clean,
            "links": [link.to_record() for link in self.links],
            "exclusion_entries": [
                exclusion.to_record() for exclusion in self.exclusion_entries
            ],
        }


def link_retrieved_candidate(result: DocketRetrievalResult) -> MotionLinkageResult:
    """Link target MTD entries in a retrieved candidate result."""

    return link_mtd_dispositions(
        result.docket_entries,
        candidate_id=result.candidate_id,
        case_id=result.case_id,
    )


def link_mtd_dispositions(
    docket_entries: Iterable[NormalizedDocketEntry],
    *,
    candidate_id: str,
    case_id: str,
) -> MotionLinkageResult:
    """Link MTD docket entries to the written dispositions that resolve them."""

    entries = tuple(docket_entries)
    motions = _distinct_target_motions(
        tuple(entry for entry in entries if _is_mtd_motion(entry))
    )
    if not motions:
        return _excluded(
            candidate_id=candidate_id,
            case_id=case_id,
            reason=MotionLinkageExclusionReason.NO_TARGET_MOTION,
            entries=entries,
            notes="No docket entry has a target motion-to-dismiss role.",
        )

    dispositions = tuple(entry for entry in entries if _is_disposition(entry))
    if not dispositions:
        return _excluded(
            candidate_id=candidate_id,
            case_id=case_id,
            reason=MotionLinkageExclusionReason.NO_WRITTEN_DISPOSITION,
            entries=motions,
            notes="No written disposition entry was found for the target MTD.",
        )

    explicit_link = _link_by_explicit_references(
        candidate_id=candidate_id,
        case_id=case_id,
        motions=motions,
        dispositions=dispositions,
    )
    if explicit_link is not None:
        return MotionLinkageResult(
            candidate_id=candidate_id,
            case_id=case_id,
            links=(explicit_link,),
        )

    if len(motions) == 1:
        return MotionLinkageResult(
            candidate_id=candidate_id,
            case_id=case_id,
            links=(
                _build_link(
                    candidate_id=candidate_id,
                    case_id=case_id,
                    motions=motions,
                    dispositions=_resolving_dispositions(dispositions),
                    basis=("single_target_motion_single_disposition_path",),
                ),
            ),
        )

    if _single_plural_order_resolves_all_motions(motions, dispositions):
        return MotionLinkageResult(
            candidate_id=candidate_id,
            case_id=case_id,
            links=(
                _build_link(
                    candidate_id=candidate_id,
                    case_id=case_id,
                    motions=motions,
                    dispositions=dispositions,
                    basis=("single_plural_order_resolves_all_mtds",),
                ),
            ),
        )

    return _excluded(
        candidate_id=candidate_id,
        case_id=case_id,
        reason=MotionLinkageExclusionReason.AMBIGUOUS_MOTION_TO_ORDER_LINKAGE,
        entries=(*motions, *dispositions),
        notes=(
            "Multiple target MTD entries exist and no disposition explicitly "
            "identifies which motion or motions it resolves."
        ),
    )


def _link_by_explicit_references(
    *,
    candidate_id: str,
    case_id: str,
    motions: tuple[NormalizedDocketEntry, ...],
    dispositions: tuple[NormalizedDocketEntry, ...],
) -> MotionDispositionLink | None:
    motion_by_number = {
        number: motion
        for motion in motions
        if (number := _entry_number_as_int(motion.entry_number)) is not None
    }
    if not motion_by_number:
        return None

    referenced_numbers: set[int] = set()
    referenced_dispositions: list[NormalizedDocketEntry] = []
    for disposition in dispositions:
        disposition_refs = referenced_entry_numbers(disposition.entry_text)
        matched_refs = disposition_refs & motion_by_number.keys()
        if not matched_refs:
            continue
        referenced_numbers.update(matched_refs)
        referenced_dispositions.append(disposition)

    if not referenced_numbers:
        return None

    referenced_motions = tuple(
        motion
        for number, motion in motion_by_number.items()
        if number in referenced_numbers
    )
    if not referenced_motions or not referenced_dispositions:
        return None

    return _build_link(
        candidate_id=candidate_id,
        case_id=case_id,
        motions=referenced_motions,
        dispositions=tuple(referenced_dispositions),
        basis=("explicit_docket_entry_reference",),
    )


def _build_link(
    *,
    candidate_id: str,
    case_id: str,
    motions: tuple[NormalizedDocketEntry, ...],
    dispositions: tuple[NormalizedDocketEntry, ...],
    basis: tuple[str, ...],
) -> MotionDispositionLink:
    clean_dispositions = _resolving_dispositions(dispositions)
    selected_motion = min(motions, key=_target_motion_sort_key)
    return MotionDispositionLink(
        candidate_id=candidate_id,
        case_id=case_id,
        motion_entry_ids=(selected_motion.docket_entry_id,),
        disposition_entry_ids=tuple(
            entry.docket_entry_id for entry in clean_dispositions
        ),
        linkage_basis=(
            *_linkage_basis(basis, clean_dispositions),
            "deterministic_earliest_eligible_target_motion",
        ),
        contains_non_mtd_relief=any(
            _contains_non_mtd_relief(entry.entry_text) for entry in clean_dispositions
        ),
        includes_report_and_recommendation=any(
            _is_report_and_recommendation(entry.entry_text)
            or _is_adoption_order(entry.entry_text)
            for entry in clean_dispositions
        ),
    )


def _target_motion_sort_key(entry: NormalizedDocketEntry) -> tuple[str, int, str]:
    """Order eligible MTDs deterministically by filing date and docket number."""

    return (
        entry.filed_at or "9999-12-31",
        _entry_number_as_int(entry.entry_number) or 2**31 - 1,
        entry.docket_entry_id,
    )


def _resolving_dispositions(
    dispositions: tuple[NormalizedDocketEntry, ...],
) -> tuple[NormalizedDocketEntry, ...]:
    report_entries = tuple(
        entry
        for entry in dispositions
        if _is_report_and_recommendation(entry.entry_text)
    )
    adoption_entries = tuple(
        entry for entry in dispositions if _is_adoption_order(entry.entry_text)
    )
    resolving = tuple(
        entry for entry in dispositions if _resolves_mtd(entry.entry_text)
    )
    if report_entries and adoption_entries:
        return _unique_entries((*report_entries, *adoption_entries))
    if resolving:
        return resolving
    return dispositions


def _excluded(
    *,
    candidate_id: str,
    case_id: str,
    reason: MotionLinkageExclusionReason,
    entries: tuple[NormalizedDocketEntry, ...],
    notes: str,
) -> MotionLinkageResult:
    return MotionLinkageResult(
        candidate_id=candidate_id,
        case_id=case_id,
        links=(),
        exclusion_entries=(
            ExclusionLedgerEntry(
                candidate_id=candidate_id,
                case_id=case_id,
                stage=ExclusionStage.MOTION_LINKAGE,
                reason=reason.value,
                source_entry_ids=tuple(entry.docket_entry_id for entry in entries),
                notes=notes,
            ),
        ),
    )


def _is_mtd_motion(entry: NormalizedDocketEntry) -> bool:
    return entry.document_role in {
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
    }


def _distinct_target_motions(
    motions: tuple[NormalizedDocketEntry, ...],
) -> tuple[NormalizedDocketEntry, ...]:
    """Drop support memoranda that explicitly identify their notice entry."""

    notice_numbers = {
        number
        for motion in motions
        if motion.document_role is DocumentRole.MTD_NOTICE
        if (number := _entry_number_as_int(motion.entry_number)) is not None
    }
    return tuple(
        motion
        for motion in motions
        if not (
            motion.document_role is DocumentRole.MTD_MEMORANDUM
            and bool(referenced_mtd_entry_numbers(motion.entry_text) & notice_numbers)
        )
    )


def _is_disposition(entry: NormalizedDocketEntry) -> bool:
    return entry.document_role in {DocumentRole.ORDER, DocumentRole.DECISION}


def _single_plural_order_resolves_all_motions(
    motions: tuple[NormalizedDocketEntry, ...],
    dispositions: tuple[NormalizedDocketEntry, ...],
) -> bool:
    return (
        len(motions) > 1
        and len(dispositions) == 1
        and "motions to dismiss" in dispositions[0].entry_text.lower()
    )


def _resolves_mtd(text: str) -> bool:
    normalized = text.lower()
    return _references_motion_to_dismiss(normalized) and any(
        term in normalized
        for term in (
            "grant",
            "deny",
            "denied",
            "dismissed",
            "dismissal",
            "leave to amend",
            "with prejudice",
            "without prejudice",
            "recommend",
        )
    )


def _linkage_basis(
    basis: tuple[str, ...],
    dispositions: tuple[NormalizedDocketEntry, ...],
) -> tuple[str, ...]:
    extras: list[str] = []
    if any(_contains_non_mtd_relief(entry.entry_text) for entry in dispositions):
        extras.append("mixed_non_mtd_relief_preserved")
    if any(
        _is_report_and_recommendation(entry.entry_text)
        or _is_adoption_order(entry.entry_text)
        for entry in dispositions
    ):
        extras.append("report_and_recommendation_adoption_path")
    return (*basis, *extras)


def _contains_non_mtd_relief(text: str) -> bool:
    normalized = text.lower()
    return any(
        term in normalized
        for term in (
            "preliminary injunction",
            "temporary restraining order",
            "summary judgment",
            "class certification",
        )
    )


def _references_motion_to_dismiss(normalized_text: str) -> bool:
    return (
        "motion to dismiss" in normalized_text
        or "motions to dismiss" in normalized_text
        or "rule 12" in normalized_text
        or "mtd" in normalized_text
    )


def _is_report_and_recommendation(text: str) -> bool:
    normalized = text.lower()
    return "report and recommendation" in normalized or "r&r" in normalized


def _is_adoption_order(text: str) -> bool:
    normalized = text.lower()
    return "adopt" in normalized and (
        "report and recommendation" in normalized
        or "recommendation" in normalized
        or "r&r" in normalized
    )


def referenced_entry_numbers(text: str) -> set[int]:
    """Return docket numbers explicitly referenced by one disposition text."""

    numbers: set[int] = set()
    for match in _DOCKET_REFERENCE_RE.finditer(text):
        numbers.update(_numbers_in_text(match.group("numbers")))
    for match in _RELATED_DOCUMENT_REFERENCE_RE.finditer(text):
        numbers.update(_numbers_in_text(match.group("numbers")))
    for match in _BRACKET_REFERENCE_RE.finditer(text):
        numbers.add(int(match.group("number")))
    for pattern in _NUMBERED_MTD_REFERENCE_RES:
        numbers.update(int(match.group("number")) for match in pattern.finditer(text))
    return numbers


def courtlistener_relationship_entry_numbers(text: str) -> set[int]:
    """Return only entry numbers in CourtListener relationship annotations.

    These narrow forms are safe for fetching or promoting an otherwise generic
    row. Broader docket and bracket citations remain useful for linking already
    classified motions, but do not prove that a generic row is the target.
    """

    numbers: set[int] = set()
    for pattern in _COURTLISTENER_RELATIONSHIP_REFERENCE_RES:
        for match in pattern.finditer(text):
            numbers.update(_numbers_in_text(match.group("numbers")))
    return numbers


def referenced_mtd_entry_numbers(text: str) -> set[int]:
    """Return only numbers syntactically coupled to an MTD reference."""

    numbers: set[int] = set()
    for pattern in _NUMBERED_MTD_REFERENCE_RES:
        numbers.update(int(match.group("number")) for match in pattern.finditer(text))
    return numbers


def _numbers_in_text(text: str) -> set[int]:
    return {int(value) for value in re.findall(r"\d+", text)}


def _entry_number_as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _unique_entries(
    entries: tuple[NormalizedDocketEntry, ...],
) -> tuple[NormalizedDocketEntry, ...]:
    seen: set[str] = set()
    result: list[NormalizedDocketEntry] = []
    for entry in entries:
        if entry.docket_entry_id in seen:
            continue
        seen.add(entry.docket_entry_id)
        result.append(entry)
    return tuple(result)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_empty_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not values:
        raise ValueError(f"{field_name} is required")
    for value in values:
        _require_non_empty(value, field_name)


_DOCKET_REFERENCE_RE = re.compile(
    r"(?:\b(?:ecf|dkt\.?|docket|doc(?:ument)?\.?|entry)\s*"
    r"(?:(?:no|nos)\.?\s*|#\s*)?|#\s*)"
    r"(?P<numbers>[0-9][0-9,\sand-]*)",
    re.IGNORECASE,
)
_RELATED_DOCUMENT_REFERENCE_RE = re.compile(
    r"\brelated\s+documents?(?:\s*\(\s*s\s*\))?\s*"
    r"(?:(?:no|nos)\.?\s*|#\s*|:\s*)?"
    r"(?P<numbers>[0-9][0-9,\sand-]*)",
    re.IGNORECASE,
)
_BRACKET_REFERENCE_RE = re.compile(r"\[(?P<number>\d+)\]")
_COURTLISTENER_RELATIONSHIP_REFERENCE_RES = (
    re.compile(
        r"\brelated\s+document(?:\(s\)|s)\s*:?[ \t]*"
        r"(?P<numbers>[1-9][0-9]*(?:[ \t]*(?:,|and)[ \t]*#?[ \t]*"
        r"[1-9][0-9]*)*)(?![ \t]*(?:[0-9/,\-]|\band\b))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bre[ \t]*:[ \t]*#[ \t]*"
        r"(?P<numbers>[1-9][0-9]*(?:[ \t]*(?:,|and)[ \t]*#?[ \t]*"
        r"[1-9][0-9]*)*)(?![ \t]*(?:[0-9/,\-]|\band\b))",
        re.IGNORECASE,
    ),
)
_NUMBERED_MTD_REFERENCE_RES = (
    re.compile(
        r"\b(?P<number>\d+)\s+motions?\s+to\s+dismiss\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmotions?\s+to\s+dismiss(?:\s+for\s+(?:failure\s+to\s+state\s+"
        r"a\s+claim|lack\s+of\s+jurisdiction))?\s+(?P<number>\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmotions?\s+to\s+dismiss\b[^.;:\n]{0,60}?"
        r"\b(?:ecf|dkt\.?|docket|doc(?:ument)?\.?|entry)\s*"
        r"(?:(?:no|nos)\.?\s*|#\s*)?(?P<number>\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ecf|dkt\.?|docket|doc(?:ument)?\.?|entry)\s*"
        r"(?:(?:no|nos)\.?\s*|#\s*)?(?P<number>\d+)\b"
        r"[^.;:\n]{0,60}?\bmotions?\s+to\s+dismiss\b",
        re.IGNORECASE,
    ),
)

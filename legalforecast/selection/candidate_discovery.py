"""Recall-oriented MTD candidate discovery from docket-entry text."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

DISCOVERY_SEARCH_TERMS = (
    "motion to dismiss",
    "motions to dismiss",
    "MTD",
    "Rule 12",
    "Fed. R. Civ. P. 12",
    "12(b)(1)",
    "12(b)(2)",
    "12(b)(6)",
    "12(c)",
    "dismiss complaint",
    "dismiss amended complaint",
    "dismiss the complaint",
    "dismissal of complaint",
    "order granting motion to dismiss",
    "order denying motion to dismiss",
    "order granting in part and denying in part motion to dismiss",
    "memorandum opinion and order",
    "opinion and order",
    "decision and order",
    "dismissed with leave to amend",
    "dismissed without prejudice",
    "dismissed with prejudice",
)


class DiscoveryTriggerKind(StrEnum):
    """Kinds of docket-entry signals used during MTD discovery."""

    MTD = "mtd"
    ORDER = "order"
    FALSE_POSITIVE = "false_positive"


@dataclass(frozen=True, slots=True)
class TriggerPattern:
    term: str
    kind: DiscoveryTriggerKind
    pattern: re.Pattern[str]

    def matches(self, text: str) -> bool:
        return self.pattern.search(text) is not None


@dataclass(frozen=True, slots=True)
class DocketEntryRecord:
    """Minimal docket-entry record used for candidate discovery."""

    case_id: str
    docket_entry_id: str
    entry_text: str
    entry_number: str | None = None
    filed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id is required")
        if not self.docket_entry_id.strip():
            raise ValueError("docket_entry_id is required")
        if not self.entry_text.strip():
            raise ValueError("entry_text is required")

    @classmethod
    def from_mapping(cls, record: Mapping[str, object]) -> DocketEntryRecord:
        """Build a docket-entry record from common case.dev-style field names."""

        return cls(
            case_id=_required_string(record, "case_id", "caseId"),
            docket_entry_id=_required_string(
                record, "docket_entry_id", "docketEntryId", "id"
            ),
            entry_text=_required_string(record, "entry_text", "docket_text", "text"),
            entry_number=_optional_string(record, "entry_number", "entryNumber"),
            filed_at=_optional_string(record, "filed_at", "date_filed", "filedAt"),
        )


@dataclass(frozen=True, slots=True)
class DocketEntryDiscoverySignals:
    """Trigger diagnostics for one docket entry."""

    entry: DocketEntryRecord
    mtd_trigger_terms: tuple[str, ...]
    order_trigger_terms: tuple[str, ...]
    false_positive_terms: tuple[str, ...]

    @property
    def has_mtd_signal(self) -> bool:
        return bool(self.mtd_trigger_terms)

    @property
    def has_order_signal(self) -> bool:
        return bool(self.order_trigger_terms)

    @property
    def has_false_positive_signal(self) -> bool:
        return bool(self.false_positive_terms)

    @property
    def is_qualifying_mtd_entry(self) -> bool:
        return self.has_mtd_signal and not self.has_false_positive_signal

    @property
    def is_linkable_order_entry(self) -> bool:
        return self.has_order_signal and not self.has_false_positive_signal


@dataclass(frozen=True, slots=True)
class MtdDiscoveryCandidate:
    """Case-level candidate with diagnostic trigger terms."""

    case_id: str
    candidate_entry_ids: tuple[str, ...]
    qualifying_mtd_entry_ids: tuple[str, ...]
    order_entry_ids: tuple[str, ...]
    false_positive_entry_ids: tuple[str, ...]
    mtd_trigger_terms: tuple[str, ...]
    order_trigger_terms: tuple[str, ...]
    false_positive_terms: tuple[str, ...]

    @property
    def trigger_terms(self) -> tuple[str, ...]:
        return _unique_ordered(
            (
                *self.mtd_trigger_terms,
                *self.order_trigger_terms,
                *self.false_positive_terms,
            )
        )

    @property
    def has_linked_false_positive(self) -> bool:
        return bool(self.false_positive_entry_ids)

    def to_record(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "candidate_entry_ids": list(self.candidate_entry_ids),
            "qualifying_mtd_entry_ids": list(self.qualifying_mtd_entry_ids),
            "order_entry_ids": list(self.order_entry_ids),
            "false_positive_entry_ids": list(self.false_positive_entry_ids),
            "mtd_trigger_terms": list(self.mtd_trigger_terms),
            "order_trigger_terms": list(self.order_trigger_terms),
            "false_positive_terms": list(self.false_positive_terms),
            "trigger_terms": list(self.trigger_terms),
        }


def _pattern(
    term: str,
    pattern: str,
    kind: DiscoveryTriggerKind = DiscoveryTriggerKind.MTD,
) -> TriggerPattern:
    return TriggerPattern(term=term, kind=kind, pattern=re.compile(pattern, re.I))


_MTD_PATTERNS = (
    _pattern("motion to dismiss", r"\bmotions?\s+to\s+dismiss\b"),
    _pattern("MTD", r"\bMTDs?\b"),
    _pattern("Rule 12", r"\brule\s+12\b"),
    _pattern(
        "Fed. R. Civ. P. 12",
        r"\bfed\.?\s*r\.?\s*civ\.?\s*p\.?\s*12\b",
    ),
    _pattern("12(b)(1)", r"\b12\s*\(\s*b\s*\)\s*\(\s*1\s*\)"),
    _pattern("12(b)(2)", r"\b12\s*\(\s*b\s*\)\s*\(\s*2\s*\)"),
    _pattern("12(b)(6)", r"\b12\s*\(\s*b\s*\)\s*\(\s*6\s*\)"),
    _pattern("12(c)", r"\b12\s*\(\s*c\s*\)"),
    _pattern(
        "dismiss complaint",
        r"\bdismiss(?:ing|ed)?\s+(?:the\s+)?complaint\b",
    ),
    _pattern(
        "dismiss amended complaint",
        r"\bdismiss(?:ing|ed)?\s+(?:the\s+)?(?:first\s+|second\s+)?"
        r"amended\s+complaint\b",
    ),
    _pattern(
        "dismiss the complaint",
        r"\bdismiss(?:ing|ed)?\s+the\s+complaint\b",
    ),
    _pattern(
        "dismissal of complaint",
        r"\bdismissal\s+of\s+(?:the\s+)?(?:amended\s+)?complaint\b",
    ),
)

_ORDER_PATTERNS = (
    _pattern(
        "order granting motion to dismiss",
        r"\border\s+grant(?:ing|ed)\b.*\bmotions?\s+to\s+dismiss\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "order denying motion to dismiss",
        r"\border\s+deny(?:ing|ied)\b.*\bmotions?\s+to\s+dismiss\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "order granting in part and denying in part motion to dismiss",
        r"\border\b.*\bgrant(?:ing|ed)\s+in\s+part\b.*\bdeny(?:ing|ied)\s+"
        r"in\s+part\b.*\bmotions?\s+to\s+dismiss\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "memorandum opinion and order",
        r"\bmemorandum\s+opinion\s+and\s+order\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "opinion and order",
        r"\bopinion\s+and\s+order\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "decision and order",
        r"\bdecision\s+and\s+order\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "dismissed with leave to amend",
        r"\bdismissed\s+with\s+leave\s+to\s+amend\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "dismissed without prejudice",
        r"\bdismissed\s+without\s+prejudice\b",
        DiscoveryTriggerKind.ORDER,
    ),
    _pattern(
        "dismissed with prejudice",
        r"\bdismissed\s+with\s+prejudice\b",
        DiscoveryTriggerKind.ORDER,
    ),
)

_FALSE_POSITIVE_PATTERNS = (
    _pattern(
        "notice of voluntary dismissal",
        r"\bnotice\s+of\s+voluntary\s+dismissal\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "stipulation of dismissal",
        r"\bstipulation\s+(?:and\s+order\s+)?of\s+dismissal\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "voluntary dismissal",
        r"\bvoluntary\s+dismissal\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "dismissal for failure to prosecute",
        r"\bdismissal\s+for\s+failure\s+to\s+prosecute\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "clerk's judgment",
        r"\bclerk'?s\s+judg(?:e)?ment\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "administrative closure",
        r"\badministrative(?:ly)?\s+clos(?:ure|ed)\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "motion to dismiss appeal",
        r"\bmotion\s+to\s+dismiss\s+(?:the\s+)?appeal\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "motion to dismiss counterclaim only",
        r"\bmotion\s+to\s+dismiss\s+(?:the\s+)?counterclaims?\s+only\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
    _pattern(
        "order of dismissal with no linked Rule 12-style motion",
        r"\border\s+of\s+dismissal\b",
        DiscoveryTriggerKind.FALSE_POSITIVE,
    ),
)


def mtd_discovery_search_terms() -> tuple[str, ...]:
    """Return canonical case.dev docket-search terms for MTD discovery."""

    return DISCOVERY_SEARCH_TERMS


def classify_docket_entry(
    entry: DocketEntryRecord | Mapping[str, object],
) -> DocketEntryDiscoverySignals:
    """Classify one docket entry and record all matching trigger terms."""

    docket_entry = _coerce_entry(entry)
    text = _normalize_text(docket_entry.entry_text)
    return DocketEntryDiscoverySignals(
        entry=docket_entry,
        mtd_trigger_terms=_matching_terms(text, _MTD_PATTERNS),
        order_trigger_terms=_matching_terms(text, _ORDER_PATTERNS),
        false_positive_terms=_matching_terms(text, _FALSE_POSITIVE_PATTERNS),
    )


def discover_mtd_candidates(
    entries: Iterable[DocketEntryRecord | Mapping[str, object]],
) -> tuple[MtdDiscoveryCandidate, ...]:
    """Return case-level MTD candidates from recall-oriented docket signals.

    A case is returned only when at least one entry has an identifiable MTD
    signal that is not itself a common false positive. Generic dismissal orders
    and voluntary-dismissal entries are kept as diagnostics when linked to a
    qualifying MTD entry, but they cannot create a candidate on their own.
    """

    grouped: dict[str, list[DocketEntryDiscoverySignals]] = defaultdict(list)
    for entry in entries:
        signals = classify_docket_entry(entry)
        grouped[signals.entry.case_id].append(signals)

    candidates: list[MtdDiscoveryCandidate] = []
    for case_id, case_signals in grouped.items():
        qualifying = tuple(
            signal for signal in case_signals if signal.is_qualifying_mtd_entry
        )
        if not qualifying:
            continue

        orders = tuple(
            signal for signal in case_signals if signal.is_linkable_order_entry
        )
        false_positives = tuple(
            signal for signal in case_signals if signal.has_false_positive_signal
        )
        signal_entries = tuple(
            signal
            for signal in case_signals
            if (
                signal.is_qualifying_mtd_entry
                or signal.is_linkable_order_entry
                or signal.has_false_positive_signal
            )
        )
        candidates.append(
            MtdDiscoveryCandidate(
                case_id=case_id,
                candidate_entry_ids=tuple(
                    signal.entry.docket_entry_id for signal in signal_entries
                ),
                qualifying_mtd_entry_ids=tuple(
                    signal.entry.docket_entry_id for signal in qualifying
                ),
                order_entry_ids=tuple(
                    signal.entry.docket_entry_id for signal in orders
                ),
                false_positive_entry_ids=tuple(
                    signal.entry.docket_entry_id for signal in false_positives
                ),
                mtd_trigger_terms=_unique_mtd_terms(qualifying),
                order_trigger_terms=_unique_order_terms(case_signals),
                false_positive_terms=_unique_false_positive_terms(false_positives),
            )
        )

    return tuple(candidates)


def _coerce_entry(entry: DocketEntryRecord | Mapping[str, object]) -> DocketEntryRecord:
    if isinstance(entry, DocketEntryRecord):
        return entry
    return DocketEntryRecord.from_mapping(entry)


def _matching_terms(
    normalized_text: str,
    patterns: tuple[TriggerPattern, ...],
) -> tuple[str, ...]:
    return tuple(
        pattern.term for pattern in patterns if pattern.matches(normalized_text)
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _unique_ordered(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


def _unique_mtd_terms(
    signals: Iterable[DocketEntryDiscoverySignals],
) -> tuple[str, ...]:
    terms: list[str] = []
    for signal in signals:
        terms.extend(signal.mtd_trigger_terms)
    return _unique_ordered(terms)


def _unique_order_terms(
    signals: Iterable[DocketEntryDiscoverySignals],
) -> tuple[str, ...]:
    terms: list[str] = []
    for signal in signals:
        terms.extend(signal.order_trigger_terms)
    return _unique_ordered(terms)


def _unique_false_positive_terms(
    signals: Iterable[DocketEntryDiscoverySignals],
) -> tuple[str, ...]:
    terms: list[str] = []
    for signal in signals:
        terms.extend(signal.false_positive_terms)
    return _unique_ordered(terms)


def _required_string(record: Mapping[str, object], *field_names: str) -> str:
    value = _optional_string(record, *field_names)
    if value is None:
        joined = ", ".join(field_names)
        raise ValueError(f"missing required docket-entry field: {joined}")
    return value


def _optional_string(record: Mapping[str, object], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None

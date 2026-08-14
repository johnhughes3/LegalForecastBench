"""Deterministic free-first / page-count pricing for document-need buckets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from legalforecast.document_need.cycle_config import DocumentNeedCycleView, format_usd
from legalforecast.document_need.types import (
    Chronology,
    ChronologyEntry,
    DocketDocument,
    EntryVerdict,
    NeedBucket,
)

_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class PricedEntry:
    """One chronology entry after bucket assignment and cost math."""

    entry: int
    bucket: NeedBucket
    asserted_role: str | None
    rationale: str
    cost_usd: Decimal
    free_first_applied: bool
    paid_document_count: int
    unknown_page_count: bool

    def to_record(self) -> dict[str, object]:
        return {
            "entry": self.entry,
            "bucket": self.bucket.value,
            "asserted_role": self.asserted_role,
            "rationale": self.rationale,
            "cost_usd": format_usd(self.cost_usd),
            "free_first_applied": self.free_first_applied,
            "paid_document_count": self.paid_document_count,
            "unknown_page_count": self.unknown_page_count,
        }


@dataclass(frozen=True, slots=True)
class CaseCosts:
    """Per-case min/max purchase cost from bucketed, priced entries."""

    candidate_id: str
    min_cost: Decimal
    max_cost: Decimal
    entries: tuple[PricedEntry, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "min_cost_usd": format_usd(self.min_cost),
            "max_cost_usd": format_usd(self.max_cost),
            "entries": [entry.to_record() for entry in self.entries],
        }


def price_document(
    document: DocketDocument,
    *,
    free_first: bool,
    per_page: Decimal,
    cap: Decimal,
) -> Decimal:
    """Return the estimated PACER cost of one document."""

    if document.restricted:
        return _ZERO
    if (free_first and document.freely_available) or (
        document.freely_available and not document.pacer_only
    ):
        return _ZERO
    if not document.pacer_only:
        return _ZERO
    if document.page_count is None:
        return cap
    return min(per_page * document.page_count, cap)


def price_entry(
    entry: ChronologyEntry,
    *,
    free_first: bool,
    per_page: Decimal,
    cap: Decimal,
) -> tuple[Decimal, bool, int, bool]:
    """Return (cost, free_first_applied, paid_document_count, unknown_page_count)."""

    cost = _ZERO
    paid = 0
    unknown_pages = False
    free_applied = False
    for document in entry.documents:
        item_cost = price_document(
            document, free_first=free_first, per_page=per_page, cap=cap
        )
        if document.freely_available and free_first:
            free_applied = True
        if document.pacer_only and not document.restricted:
            paid += 1
            if document.page_count is None:
                unknown_pages = True
        cost += item_cost
    return cost, free_applied, paid, unknown_pages


def price_case(
    chronology: Chronology,
    buckets: Mapping[int, EntryVerdict],
    view: DocumentNeedCycleView,
) -> CaseCosts:
    """Price every chronology entry and compute min_cost / max_cost.

    min_cost is the sum of paid clearly-required entries (free-first).
    max_cost is min_cost plus every conditional entry. clearly_not_required
    entries do not contribute.
    """

    expected = chronology.entry_numbers()
    got = frozenset(buckets)
    if got != expected:
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        raise ValueError(
            f"bucket coverage must match chronology exactly "
            f"(missing={missing}, extra={extra})"
        )
    priced: list[PricedEntry] = []
    min_cost = _ZERO
    conditional = _ZERO
    by_number = chronology.by_number()
    for entry_number in sorted(expected):
        verdict = buckets[entry_number]
        if verdict.entry != entry_number:
            raise ValueError("verdict entry number disagrees with map key")
        cost, free_applied, paid, unknown_pages = price_entry(
            by_number[entry_number],
            free_first=view.free_first,
            per_page=view.pacer_per_page_usd,
            cap=view.per_document_price_cap_usd,
        )
        priced.append(
            PricedEntry(
                entry=entry_number,
                bucket=verdict.bucket,
                asserted_role=verdict.asserted_role,
                rationale=verdict.rationale,
                cost_usd=cost,
                free_first_applied=free_applied,
                paid_document_count=paid,
                unknown_page_count=unknown_pages,
            )
        )
        if verdict.bucket is NeedBucket.CLEARLY_REQUIRED:
            min_cost += cost
        elif verdict.bucket is NeedBucket.CONDITIONAL:
            conditional += cost
    return CaseCosts(
        candidate_id=chronology.candidate_id,
        min_cost=min_cost,
        max_cost=min_cost + conditional,
        entries=tuple(priced),
    )

"""Acquire ranked CourtListener dockets through the canonical Firecrawl ledger."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketBundle,
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
    may_stop_at_anchor_boundary,
    paginate_courtlistener_docket,
)


class BudgetedDocketAcquisitionError(ValueError):
    """Raised when ranked input cannot produce a complete screening artifact."""


@dataclass(frozen=True, slots=True)
class RankedDocketTarget:
    """Validated selective acquisition target from free Case.dev ranking."""

    docket_id: str
    docket_url: str
    rank: int


@dataclass(frozen=True, slots=True)
class BudgetedDocketAcquisitionResult:
    """Only complete-for-window bundles, in Case.dev cost order."""

    bundles: tuple[CourtListenerDocketBundle, ...]
    failed_docket_ids: tuple[str, ...]
    credit_summary: Mapping[str, object]


def ranked_docket_targets(
    records: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[RankedDocketTarget, ...]:
    """Validate and preserve the free Case.dev cost order."""

    if limit <= 0:
        raise BudgetedDocketAcquisitionError("limit must be positive")
    targets: list[RankedDocketTarget] = []
    seen: set[str] = set()
    for rank, record in enumerate(records):
        identity = record.get("identity")
        if not isinstance(identity, Mapping):
            raise BudgetedDocketAcquisitionError("ranked record identity is missing")
        typed_identity = cast(Mapping[str, object], identity)
        docket_id = typed_identity.get("courtlistener_docket_id")
        docket_url = typed_identity.get("courtlistener_url")
        if not isinstance(docket_id, str) or not docket_id.isdigit():
            raise BudgetedDocketAcquisitionError("ranked docket id is invalid")
        if not isinstance(docket_url, str):
            raise BudgetedDocketAcquisitionError("ranked docket URL is missing")
        if docket_id in seen:
            raise BudgetedDocketAcquisitionError(
                f"duplicate ranked docket: {docket_id}"
            )
        # Canonical construction is also the strict same-host/same-docket validator.
        try:
            canonical_courtlistener_docket_page_url(docket_url, page_number=1)
        except CourtListenerDocketPaginationError as exc:
            raise BudgetedDocketAcquisitionError(str(exc)) from exc
        seen.add(docket_id)
        targets.append(RankedDocketTarget(docket_id, docket_url, rank))
        if len(targets) == limit:
            break
    return tuple(targets)


def acquire_ranked_dockets(
    *,
    records: Iterable[Mapping[str, Any]],
    scheduler: BudgetedFirecrawlScheduler,
    limit: int,
    max_pages_per_docket: int,
    decision_anchor: date,
) -> BudgetedDocketAcquisitionResult:
    """Acquire docket pages in waves and expose no incomplete bundle.

    Each page wave is submitted as one scheduler batch, retaining its widest-first
    retry behavior across dockets. A failed target is isolated; auth, budget,
    billing, rate, challenge, and circuit errors still propagate from the scheduler.
    """

    if max_pages_per_docket <= 0:
        raise BudgetedDocketAcquisitionError("max_pages_per_docket must be positive")
    ranked = ranked_docket_targets(records, limit=limit)
    active = {target.docket_id: target for target in ranked}
    pages: dict[str, dict[str, str]] = {target.docket_id: {} for target in ranked}
    failed: set[str] = set()
    summary: Mapping[str, object] = {}

    for page_number in range(1, max_pages_per_docket + 1):
        if not active:
            break
        specs: list[FirecrawlTargetSpec] = []
        urls: dict[str, str] = {}
        for target in active.values():
            url = canonical_courtlistener_docket_page_url(
                target.docket_url, page_number=page_number
            )
            target_id = _target_id(target.docket_id, page_number)
            urls[target.docket_id] = url
            specs.append(
                FirecrawlTargetSpec(
                    target_id=target_id,
                    target_kind="docket",
                    source_url=url,
                    page_number=page_number,
                    ordinal=target.rank,
                )
            )
        run = scheduler.run(specs)
        summary = run.summary
        acquired = {page.target_id: page for page in run.pages}
        for docket_id, _target in tuple(active.items()):
            target_id = _target_id(docket_id, page_number)
            page = acquired.get(target_id)
            if page is None:
                failed.add(docket_id)
                del active[docket_id]
                continue
            pages[docket_id][page.source_url] = page.raw_html
            parsed = parse_courtlistener_docket_html(
                page.raw_html, source_url=page.source_url, docket_id=docket_id
            )
            observed = [
                parse_courtlistener_docket_html(
                    html, source_url=url, docket_id=docket_id
                )
                for url, html in pages[docket_id].items()
            ]
            if not parsed.has_next_page or may_stop_at_anchor_boundary(
                observed, anchor=decision_anchor
            ):
                del active[docket_id]
    failed.update(active)

    bundles: list[CourtListenerDocketBundle] = []
    for target in ranked:
        if target.docket_id in failed:
            continue
        cached = pages[target.docket_id]
        try:
            bundle = paginate_courtlistener_docket(
                target.docket_url,
                fetch=lambda url, cached=cached: cached[url],
                max_pages=max_pages_per_docket,
                decision_anchor=decision_anchor,
            )
        except (KeyError, CourtListenerDocketPaginationError) as exc:
            raise BudgetedDocketAcquisitionError(
                f"complete docket reconstruction failed: {target.docket_id}"
            ) from exc
        if not bundle.complete_for_anchor_window:
            raise BudgetedDocketAcquisitionError("incomplete docket reached output")
        bundles.append(bundle)
    return BudgetedDocketAcquisitionResult(
        bundles=tuple(bundles),
        failed_docket_ids=tuple(
            target.docket_id for target in ranked if target.docket_id in failed
        ),
        credit_summary=summary,
    )


def _target_id(docket_id: str, page_number: int) -> str:
    value = f"{docket_id}:{page_number}"
    return "docket-" + hashlib.sha256(value.encode()).hexdigest()[:24]

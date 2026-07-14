"""Acquire ranked CourtListener dockets through the canonical Firecrawl ledger."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import Any, cast

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
)
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

    candidate_id: str
    docket_id: str
    docket_url: str
    rank: int


@dataclass(frozen=True, slots=True)
class BudgetedDocketAcquisitionResult:
    """Only complete-for-window bundles, in Case.dev cost order."""

    bundles: tuple[CourtListenerDocketBundle, ...]
    failures: tuple[DocketAcquisitionFailure, ...]
    credit_summary: Mapping[str, object]

    @property
    def failed_docket_ids(self) -> tuple[str, ...]:
        """Return failed docket IDs in deterministic Case.dev rank order."""

        return tuple(failure.docket_id for failure in self.failures)


@dataclass(frozen=True, slots=True)
class DocketAcquisitionFailure:
    """Candidate-local terminal failure safe for the public exclusion ledger."""

    candidate_id: str
    docket_id: str
    reason: str
    failure_stage: str
    failure_reason: str

    def as_record(self) -> dict[str, str]:
        """Render the deterministic acquisition failure/exclusion record."""

        return {
            "case_id": self.candidate_id,
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "reason": self.reason,
            "failure_stage": self.failure_stage,
            "failure_reason": self.failure_reason,
        }


def materialize_selected_slice_batch(
    *,
    store: CycleAcquisitionStore,
    parent_batch_id: str,
    selected_batch_id: str,
    records: Iterable[Mapping[str, Any]],
    limit: int,
) -> tuple[RankedDocketTarget, ...]:
    """Create an honest terminal batch containing only ranked selected dockets.

    This does not claim that the parent discovery is saturated. The child batch
    binds its immutable configuration to the parent digest and exact ranked
    selection, so completeness and snapshot publication are scoped to the
    selected acquisition slice while the original partial pool remains partial.
    """

    materialized = tuple(records)
    targets = ranked_docket_targets(materialized, limit=limit)
    parent_ids = set(store.candidate_ids(parent_batch_id))
    missing = [
        target.candidate_id
        for target in targets
        if target.candidate_id not in parent_ids
    ]
    if missing:
        raise BudgetedDocketAcquisitionError(
            "selected docket was not discovered in parent batch: " + ",".join(missing)
        )
    selection_payload = [
        {
            "candidate_id": target.candidate_id,
            "courtlistener_url": target.docket_url,
            "cost_rank": target.rank,
        }
        for target in targets
    ]
    selection_hash = hashlib.sha256(
        json.dumps(selection_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    store.ensure_batch(
        selected_batch_id,
        {
            "schema_version": "legalforecast.selected_acquisition_slice.v1",
            "parent_batch_id": parent_batch_id,
            "parent_batch_digest": store.batch_digest(parent_batch_id),
            "selection_hash": selection_hash,
            "selection_count": len(targets),
            "parent_discovery_saturation_claimed": False,
        },
    )
    term = "selected-ranked-slice"
    store.ensure_terms(selected_batch_id, (term,))
    store.commit_search_page(
        selected_batch_id,
        term,
        None,
        (
            DiscoveryHit(
                provider_hit_id=f"selected-{target.docket_id}",
                candidate_id=target.candidate_id,
                payload=selection_payload[index],
            )
            for index, target in enumerate(targets)
        ),
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )
    return targets


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
        targets.append(
            RankedDocketTarget(
                candidate_id=f"courtlistener-docket-{docket_id}",
                docket_id=docket_id,
                docket_url=docket_url,
                rank=rank,
            )
        )
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
    failures_by_docket: dict[str, DocketAcquisitionFailure] = {}
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
                    ordinal=(page_number - 1) * len(ranked) + target.rank,
                )
            )
        run = scheduler.run(specs)
        summary = run.summary
        acquired = {page.target_id: page for page in run.pages}
        for docket_id, _target in tuple(active.items()):
            target_id = _target_id(docket_id, page_number)
            page = acquired.get(target_id)
            if page is None:
                failures_by_docket[docket_id] = _failure(
                    target=_target,
                    reason="fetch_failed",
                    stage="docket_page_acquisition",
                    detail=f"page_{page_number}_not_acquired",
                )
                del active[docket_id]
                continue
            pages[docket_id][page.source_url] = page.raw_html
            try:
                parsed = parse_courtlistener_docket_html(
                    page.raw_html, source_url=page.source_url, docket_id=docket_id
                )
                observed = [
                    parse_courtlistener_docket_html(
                        html, source_url=url, docket_id=docket_id
                    )
                    for url, html in pages[docket_id].items()
                ]
            except CourtListenerWebParseError as exc:
                failures_by_docket[docket_id] = _failure(
                    target=_target,
                    reason="docket_reconstruction_failed",
                    stage="complete_docket_reconstruction",
                    detail=f"invalid_docket_page_artifact:{exc}",
                )
                del active[docket_id]
                continue
            if not parsed.has_next_page or may_stop_at_anchor_boundary(
                observed, anchor=decision_anchor
            ):
                del active[docket_id]
    for docket_id, target in active.items():
        failures_by_docket[docket_id] = _failure(
            target=target,
            reason="fetch_failed",
            stage="docket_page_acquisition",
            detail="pagination_page_limit_reached",
        )

    bundles: list[CourtListenerDocketBundle] = []
    for target in ranked:
        if target.docket_id in failures_by_docket:
            continue
        cached = pages[target.docket_id]
        try:
            bundle = paginate_courtlistener_docket(
                target.docket_url,
                fetch=lambda url, cached=cached: cached[url],
                max_pages=max_pages_per_docket,
                decision_anchor=decision_anchor,
            )
        except KeyError:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail="cached_page_missing",
            )
            continue
        except CourtListenerDocketPaginationError as exc:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail=str(exc),
            )
            continue
        except CourtListenerWebParseError as exc:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail=f"invalid_docket_page_artifact:{exc}",
            )
            continue
        if not bundle.complete_for_anchor_window:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail="incomplete_anchor_window",
            )
            continue
        bundles.append(bundle)
    return BudgetedDocketAcquisitionResult(
        bundles=tuple(bundles),
        failures=tuple(
            failures_by_docket[target.docket_id]
            for target in ranked
            if target.docket_id in failures_by_docket
        ),
        credit_summary=summary,
    )


def render_complete_docket_html(bundle: CourtListenerDocketBundle) -> str:
    """Render a deterministic single-page screening view of a proven bundle."""

    if not bundle.complete_for_anchor_window:
        raise BudgetedDocketAcquisitionError("cannot render incomplete docket")
    rows: list[str] = []
    for entry in bundle.entries:
        document_rows: list[str] = []
        for document in entry.documents:
            link_class = "open_buy_pacer_modal" if document.pacer_only else ""
            action_label = document.action_label or (
                "Buy on PACER" if document.pacer_only else "Download PDF"
            )
            link = ""
            if document.href is not None:
                link = (
                    f'<a class="{link_class}" href="{escape(document.href)}">'
                    f"{escape(action_label)}</a>"
                )
            document_rows.append(
                '<div class="row recap-documents">'
                f"<div>{escape(document.kind)}</div>"
                f"<div>{escape(document.description)}"
                + (" Document is sealed." if document.restriction_markers else "")
                + f"</div>{link}</div>"
            )
        restriction_notice = (
            '<span class="restriction-notice">Document is sealed.</span>'
            if entry.restriction_markers
            else ""
        )
        rows.append(
            f'<div id="{escape(entry.row_id)}" class="row">'
            f'<div class="col-xs-1">{escape(entry.entry_number or "")}</div>'
            '<div class="col-xs-3">'
            f'<span title="{escape(entry.filed_at or "")}">'
            f"{escape(entry.filed_at or '')}</span></div>"
            f'<div class="col-xs-8">{escape(entry.text)}{restriction_notice}'
            f"{''.join(document_rows)}</div></div>"
        )
    return (
        "<html><head><title>"
        + escape(bundle.title or f"CourtListener docket {bundle.docket_id}")
        + '</title></head><body><div id="docket-entry-table">'
        + "".join(rows)
        + "</div></body></html>"
    )


def _target_id(docket_id: str, page_number: int) -> str:
    value = f"{docket_id}:{page_number}"
    return "docket-" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _failure(
    *, target: RankedDocketTarget, reason: str, stage: str, detail: str
) -> DocketAcquisitionFailure:
    return DocketAcquisitionFailure(
        candidate_id=target.candidate_id,
        docket_id=target.docket_id,
        reason=reason,
        failure_stage=stage,
        failure_reason=detail,
    )

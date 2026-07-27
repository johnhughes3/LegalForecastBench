"""Observe an exact frozen priority batch through paginated Firecrawl HTML.

This adapter changes only the transport used to obtain CourtListener docket
pages. Candidate identity, acquisition order, eligibility, linkage, leakage,
and reason-code policy remain bound to the frozen source batch.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.budgeted_firecrawl import (
    TARGET_HTTP_PRESSURE_POLICY_VERSION,
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_acquisition import (
    screen_courtlistener_docket_page,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerDocket
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketPage,
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    cohort_reason_policy_taxonomy,
)
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketBundle,
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
    paginate_courtlistener_docket,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    courtlistener_public_docket_url_from_case_dev,
    screen_case_dev_docket_metadata,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    BATCH_001_REOBSERVATION_TERM,
    DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
    RecapApiBatchDriverError,
    config_window_end,
    observation_priority,
    validate_frozen_eligibility_anchor,
)
from legalforecast.ingestion.recap_api_discovery import (
    REST_DOCKET_ENTRY_SOFT_CAP,
    observe_prescreened_reason,
)

FROZEN_BATCH_FIRECRAWL_RUN_SCHEMA = (
    "legalforecast.frozen_batch_firecrawl_observation_run.v1"
)
FIRECRAWL_OBSERVATION_PROVIDER = "firecrawl-courtlistener-html-v1"


class FrozenBatchFirecrawlObservationError(ValueError):
    """Raised before provider use when the frozen observation scope is invalid."""


@dataclass(frozen=True, slots=True)
class FrozenFirecrawlCandidate:
    """One unresolved frozen candidate in its committed acquisition order."""

    candidate_id: str
    docket_id: str
    payload: Mapping[str, Any]
    frozen_ordinal: int


@dataclass(frozen=True, slots=True)
class FrozenBatchFirecrawlPlan:
    """Immutable selected scope and run configuration for a resumable pass."""

    candidates: tuple[FrozenFirecrawlCandidate, ...]
    run_config: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FrozenBatchFirecrawlTally:
    """Outcome counts for one bounded observation pass."""

    selected: int
    skipped_already_observed: int
    attempted: int
    accepted: int
    excluded_by_reason: Mapping[str, int]
    transient_by_reason: Mapping[str, int]
    credit_summary: Mapping[str, object]

    def to_record(self) -> dict[str, object]:
        return {
            "selected": self.selected,
            "skipped_already_observed": self.skipped_already_observed,
            "attempted": self.attempted,
            "accepted": self.accepted,
            "excluded_by_reason": dict(sorted(self.excluded_by_reason.items())),
            "transient_by_reason": dict(sorted(self.transient_by_reason.items())),
            "firecrawl": dict(self.credit_summary),
        }


def select_frozen_firecrawl_candidates(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    requested_candidate_ids: Sequence[str] = (),
) -> tuple[FrozenFirecrawlCandidate, ...]:
    """Validate and return an exact unresolved subset in frozen priority order.

    An explicit candidate list is a set selector, not a new ranking surface.
    Its caller-provided order is therefore ignored after duplicate validation.
    Without an explicit list, every candidate lacking a current terminal
    observation is selected. Transient observations are intentionally retried
    because they never become the store's current observation.
    """

    ordered = _ordered_frozen_candidates(store, batch_id=batch_id)
    candidate_ids = tuple(candidate.candidate_id for candidate in ordered)
    candidate_id_set = frozenset(candidate_ids)
    requested = _validate_requested_candidate_ids(
        requested_candidate_ids,
        candidate_id_set=candidate_id_set,
        batch_id=batch_id,
    )
    for candidate_id in requested:
        if store.current_observation(candidate_id) is not None:
            raise FrozenBatchFirecrawlObservationError(
                f"candidate {candidate_id!r} already has a terminal observation"
            )
    selected_ids = (
        frozenset(requested)
        if requested
        else frozenset(
            candidate_id
            for candidate_id in candidate_ids
            if store.current_observation(candidate_id) is None
        )
    )
    return tuple(
        candidate for candidate in ordered if candidate.candidate_id in selected_ids
    )


def plan_frozen_firecrawl_observation(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    run_id: str,
    eligibility_anchor: date,
    artifact_dir: str | Path,
    max_pages_per_docket: int,
    max_attempts_per_page: int,
    provider_breaker_threshold: int,
    max_workers: int,
    requested_candidate_ids: Sequence[str] = (),
    limit: int | None = None,
    firecrawl_proxy: str,
    firecrawl_force_browser: bool,
    reserved_credits_per_attempt: int,
) -> FrozenBatchFirecrawlPlan:
    """Freeze or verify one exact candidate scope before any provider request."""

    if not run_id.strip():
        raise FrozenBatchFirecrawlObservationError("run_id must be nonempty")
    if max_pages_per_docket <= 0:
        raise FrozenBatchFirecrawlObservationError(
            "max_pages_per_docket must be positive"
        )
    if max_attempts_per_page <= 0:
        raise FrozenBatchFirecrawlObservationError(
            "max_attempts_per_page must be positive"
        )
    if provider_breaker_threshold <= 0:
        raise FrozenBatchFirecrawlObservationError(
            "provider_breaker_threshold must be positive"
        )
    if not 1 <= max_workers <= 10:
        raise FrozenBatchFirecrawlObservationError(
            "max_workers must be between 1 and 10"
        )
    if limit is not None and limit <= 0:
        raise FrozenBatchFirecrawlObservationError("limit must be positive")
    validate_frozen_eligibility_anchor(store, eligibility_anchor)

    ordered = _ordered_frozen_candidates(store, batch_id=batch_id)
    candidate_id_set = frozenset(candidate.candidate_id for candidate in ordered)
    requested = _validate_requested_candidate_ids(
        requested_candidate_ids,
        candidate_id_set=candidate_id_set,
        batch_id=batch_id,
    )
    try:
        existing = store.firecrawl_run_config(run_id)
    except KeyError:
        existing = None

    if existing is None:
        for candidate_id in requested:
            if store.current_observation(candidate_id) is not None:
                raise FrozenBatchFirecrawlObservationError(
                    f"candidate {candidate_id!r} already has a terminal observation"
                )
        selected = tuple(
            candidate
            for candidate in ordered
            if (
                candidate.candidate_id in frozenset(requested)
                if requested
                else store.current_observation(candidate.candidate_id) is None
            )
        )
        if limit is not None:
            selected = selected[:limit]
    else:
        if existing.get("schema_version") != FROZEN_BATCH_FIRECRAWL_RUN_SCHEMA:
            raise FrozenBatchFirecrawlObservationError(
                f"Firecrawl run {run_id!r} belongs to another purpose"
            )
        raw_selected = existing.get("selected_candidate_ids")
        if not isinstance(raw_selected, list):
            raise FrozenBatchFirecrawlObservationError(
                "existing Firecrawl run lacks a valid frozen candidate scope"
            )
        selected_objects = cast(list[object], raw_selected)
        if not all(isinstance(candidate_id, str) for candidate_id in selected_objects):
            raise FrozenBatchFirecrawlObservationError(
                "existing Firecrawl run lacks a valid frozen candidate scope"
            )
        stored_ids = tuple(cast(list[str], selected_objects))
        if requested and frozenset(requested) != frozenset(stored_ids):
            raise FrozenBatchFirecrawlObservationError(
                "requested candidate ids do not match the resumed Firecrawl run"
            )
        selected_set = frozenset(stored_ids)
        if len(selected_set) != len(stored_ids) or not selected_set <= candidate_id_set:
            raise FrozenBatchFirecrawlObservationError(
                "existing Firecrawl run candidate scope is invalid"
            )
        selected = tuple(
            candidate for candidate in ordered if candidate.candidate_id in selected_set
        )

    selected_ids = tuple(candidate.candidate_id for candidate in selected)
    batch_config = store.batch_config(batch_id)
    config: dict[str, object] = {
        "schema_version": FROZEN_BATCH_FIRECRAWL_RUN_SCHEMA,
        "purpose": "observe-frozen-priority-batch-through-courtlistener-html",
        "source_batch_id": batch_id,
        "source_batch_digest": store.batch_digest(batch_id),
        "source_cycle_hash": store.cycle_hash,
        "eligibility_anchor": eligibility_anchor.isoformat(),
        "decision_window_end": batch_config.get("decision_window_end"),
        "ranking_policy_sha256": batch_config.get("ranking_policy_sha256"),
        "deferred_frontier_sha256": batch_config.get("deferred_frontier_sha256"),
        "selected_candidate_ids": list(selected_ids),
        "selected_candidate_set_sha256": _string_set_sha256(selected_ids),
        "selected_candidate_order_sha256": _string_sequence_sha256(selected_ids),
        "frozen_batch_candidate_count": len(ordered),
        "raw_artifact_root": str(Path(artifact_dir).resolve()),
        "max_pages_per_docket": max_pages_per_docket,
        "max_attempts_per_page": max_attempts_per_page,
        "provider_breaker_threshold": provider_breaker_threshold,
        "target_http_pressure_policy_version": (TARGET_HTTP_PRESSURE_POLICY_VERSION),
        "workers": max_workers,
        "firecrawl_proxy": firecrawl_proxy,
        "firecrawl_force_browser": firecrawl_force_browser,
        "reserved_credits_per_attempt": reserved_credits_per_attempt,
    }
    if existing is not None and dict(existing) != config:
        raise FrozenBatchFirecrawlObservationError(
            f"Firecrawl run config mismatch for {run_id}: refusing unsafe resume"
        )
    return FrozenBatchFirecrawlPlan(candidates=selected, run_config=config)


def run_frozen_firecrawl_observation(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    scheduler: BudgetedFirecrawlScheduler,
    plan: FrozenBatchFirecrawlPlan,
    eligibility_anchor: date,
    max_pages_per_docket: int,
) -> FrozenBatchFirecrawlTally:
    """Acquire, screen, and durably observe the frozen scope.

    Terminal observations and cheap deterministic prescreens are skipped before
    page acquisition. Every incomplete fetch or reconstruction is appended only
    as a transient event, leaving the candidate unresolved for a later resume.
    """

    validate_frozen_eligibility_anchor(store, eligibility_anchor)
    _validate_execution_plan(
        store,
        batch_id=batch_id,
        scheduler=scheduler,
        plan=plan,
        eligibility_anchor=eligibility_anchor,
        max_pages_per_docket=max_pages_per_docket,
    )
    decision_window_end = config_window_end(store, batch_id)
    skipped = 0
    attempted = 0
    accepted = 0
    excluded: dict[str, int] = {}
    transient: dict[str, int] = {}
    fetch_candidates: list[FrozenFirecrawlCandidate] = []

    for candidate in plan.candidates:
        if store.current_observation(candidate.candidate_id) is not None:
            skipped += 1
            continue
        prescreen = observe_prescreened_reason(candidate.payload)
        if prescreen is not None:
            observation = _record_observation(
                store,
                batch_id=batch_id,
                candidate=candidate,
                state="excluded",
                reason_code=prescreen,
                evidence={"prescreen_exclusion_reason": prescreen},
            )
            attempted += 1
            _tally_observation(observation, excluded=excluded, transient=transient)
            continue
        lower_bound = _decision_entry_lower_bound(candidate.payload)
        if lower_bound is not None and lower_bound > REST_DOCKET_ENTRY_SOFT_CAP:
            observation = _record_observation(
                store,
                batch_id=batch_id,
                candidate=candidate,
                state="excluded",
                reason_code="oversized_docket_soft_skip",
                evidence={
                    "entry_number_lower_bound": lower_bound,
                    "rest_docket_entry_soft_cap": REST_DOCKET_ENTRY_SOFT_CAP,
                    "sampling_exclusion": True,
                },
            )
            attempted += 1
            _tally_observation(observation, excluded=excluded, transient=transient)
            continue
        if "opinion_resolution_evidence" in candidate.payload:
            observation = _record_observation(
                store,
                batch_id=batch_id,
                candidate=candidate,
                state="transient_failure",
                reason_code="parse_failure",
                evidence={
                    "error": (
                        "Firecrawl docket HTML does not authenticate the separate "
                        "opinion-resolution evidence"
                    )
                },
            )
            attempted += 1
            _tally_observation(observation, excluded=excluded, transient=transient)
            continue
        fetch_candidates.append(candidate)

    bundles, failures, credit_summary = _acquire_candidates(
        scheduler=scheduler,
        candidates=tuple(fetch_candidates),
        frozen_batch_candidate_count=cast(
            int, plan.run_config["frozen_batch_candidate_count"]
        ),
        max_pages_per_docket=max_pages_per_docket,
    )
    by_docket = {candidate.docket_id: candidate for candidate in fetch_candidates}
    for failure in failures:
        candidate = by_docket[failure[0]]
        observation = _record_observation(
            store,
            batch_id=batch_id,
            candidate=candidate,
            state="transient_failure",
            reason_code="temporarily_unavailable",
            evidence={
                "failure_stage": failure[1],
                "error": failure[2],
                "pagination_complete_for_anchor_window": False,
            },
        )
        attempted += 1
        _tally_observation(observation, excluded=excluded, transient=transient)

    for bundle in bundles:
        candidate = by_docket[bundle.docket_id]
        observation = _screen_bundle(
            store,
            batch_id=batch_id,
            candidate=candidate,
            bundle=bundle,
            eligibility_anchor=eligibility_anchor,
            decision_window_end=decision_window_end,
        )
        attempted += 1
        if observation.state == "accepted":
            accepted += 1
        _tally_observation(observation, excluded=excluded, transient=transient)

    return FrozenBatchFirecrawlTally(
        selected=len(plan.candidates),
        skipped_already_observed=skipped,
        attempted=attempted,
        accepted=accepted,
        excluded_by_reason=excluded,
        transient_by_reason=transient,
        credit_summary=credit_summary,
    )


def _validate_execution_plan(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    scheduler: BudgetedFirecrawlScheduler,
    plan: FrozenBatchFirecrawlPlan,
    eligibility_anchor: date,
    max_pages_per_docket: int,
) -> None:
    try:
        durable = store.firecrawl_run_config(scheduler.run_id)
    except KeyError as exc:
        raise FrozenBatchFirecrawlObservationError(
            "Firecrawl run must be frozen before observation"
        ) from exc
    if dict(durable) != dict(plan.run_config):
        raise FrozenBatchFirecrawlObservationError(
            "observation plan does not match the durable Firecrawl run"
        )
    if (
        durable.get("schema_version") != FROZEN_BATCH_FIRECRAWL_RUN_SCHEMA
        or durable.get("source_batch_id") != batch_id
        or durable.get("source_batch_digest") != store.batch_digest(batch_id)
        or durable.get("source_cycle_hash") != store.cycle_hash
        or durable.get("eligibility_anchor") != eligibility_anchor.isoformat()
        or durable.get("max_pages_per_docket") != max_pages_per_docket
    ):
        raise FrozenBatchFirecrawlObservationError(
            "durable Firecrawl run does not match the requested frozen batch"
        )
    raw_ids = durable.get("selected_candidate_ids")
    if not isinstance(raw_ids, list):
        raise FrozenBatchFirecrawlObservationError(
            "durable Firecrawl run has an invalid selected candidate scope"
        )
    selected_ids = tuple(candidate.candidate_id for candidate in plan.candidates)
    if raw_ids != list(selected_ids):
        raise FrozenBatchFirecrawlObservationError(
            "observation plan candidate order does not match the durable run"
        )
    canonical_by_id = {
        candidate.candidate_id: candidate
        for candidate in _ordered_frozen_candidates(store, batch_id=batch_id)
    }
    if any(
        canonical_by_id.get(candidate.candidate_id) != candidate
        for candidate in plan.candidates
    ):
        raise FrozenBatchFirecrawlObservationError(
            "observation plan candidate evidence drifted from the frozen batch"
        )
    batch_count = durable.get("frozen_batch_candidate_count")
    if type(batch_count) is not int or batch_count != len(canonical_by_id):
        raise FrozenBatchFirecrawlObservationError(
            "durable Firecrawl run has an invalid frozen batch count"
        )


def _ordered_frozen_candidates(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
) -> tuple[FrozenFirecrawlCandidate, ...]:
    store.batch_digest(batch_id)
    batch_config = store.batch_config(batch_id)
    if batch_config.get("discovery_mode") != DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA:
        raise FrozenBatchFirecrawlObservationError(
            "Firecrawl observation requires a frozen direct-search priority batch"
        )

    payloads = {
        hit.candidate_id: hit.payload
        for hit in store.candidate_discovery_hits(
            batch_id,
            deprioritized_terms=(BATCH_001_REOBSERVATION_TERM,),
        )
    }
    candidate_ids = store.candidate_ids(batch_id)
    missing_payloads = tuple(
        candidate_id for candidate_id in candidate_ids if candidate_id not in payloads
    )
    if missing_payloads:
        raise FrozenBatchFirecrawlObservationError(
            f"candidate {missing_payloads[0]} has no frozen discovery payload"
        )

    try:
        ordered = sorted(
            candidate_ids,
            key=lambda candidate_id: observation_priority(
                candidate_id,
                payloads[candidate_id],
                priority_batch=True,
                ranking_policy_sha256=cast(
                    str | None, batch_config.get("ranking_policy_sha256")
                ),
                priority_frontier_sha256=cast(
                    str | None, batch_config.get("deferred_frontier_sha256")
                ),
                ranking_record_commitments=cast(
                    Mapping[str, object] | None,
                    batch_config.get("selected_ranking_record_commitments"),
                ),
            ),
        )
    except RecapApiBatchDriverError as exc:
        raise FrozenBatchFirecrawlObservationError(str(exc)) from exc

    selected: list[FrozenFirecrawlCandidate] = []
    for frozen_ordinal, candidate_id in enumerate(ordered):
        payload = payloads[candidate_id]
        docket_id = payload.get("docket_id")
        expected_candidate_id = f"courtlistener-docket-{docket_id}"
        if (
            not isinstance(docket_id, str)
            or not docket_id.isdigit()
            or expected_candidate_id != candidate_id
        ):
            raise FrozenBatchFirecrawlObservationError(
                f"candidate {candidate_id!r} has an invalid frozen docket identity"
            )
        selected.append(
            FrozenFirecrawlCandidate(
                candidate_id=candidate_id,
                docket_id=docket_id,
                payload=payload,
                frozen_ordinal=frozen_ordinal,
            )
        )
    return tuple(selected)


def _validate_requested_candidate_ids(
    requested_candidate_ids: Sequence[str],
    *,
    candidate_id_set: frozenset[str],
    batch_id: str,
) -> tuple[str, ...]:
    requested = tuple(requested_candidate_ids)
    if len(set(requested)) != len(requested):
        raise FrozenBatchFirecrawlObservationError(
            "requested candidate ids must be unique"
        )
    for candidate_id in requested:
        if candidate_id not in candidate_id_set:
            raise FrozenBatchFirecrawlObservationError(
                f"candidate {candidate_id!r} is not in frozen batch {batch_id!r}"
            )
    return requested


def _acquire_candidates(
    *,
    scheduler: BudgetedFirecrawlScheduler,
    candidates: tuple[FrozenFirecrawlCandidate, ...],
    frozen_batch_candidate_count: int,
    max_pages_per_docket: int,
) -> tuple[
    tuple[CourtListenerDocketBundle, ...],
    tuple[tuple[str, str, str], ...],
    Mapping[str, object],
]:
    active = {candidate.docket_id: candidate for candidate in candidates}
    pages: dict[str, dict[str, str]] = {
        candidate.docket_id: {} for candidate in candidates
    }
    base_urls: dict[str, str] = {}
    failures: dict[str, tuple[str, str, str]] = {}
    summary: Mapping[str, object] = {}
    for candidate in candidates:
        url = courtlistener_public_docket_url_from_case_dev(candidate.payload)
        if url is None:
            failures[candidate.docket_id] = (
                candidate.docket_id,
                "docket_page_acquisition",
                "frozen payload cannot construct a canonical CourtListener docket URL",
            )
            active.pop(candidate.docket_id, None)
        else:
            try:
                canonical_courtlistener_docket_page_url(url, page_number=1)
            except CourtListenerDocketPaginationError as exc:
                failures[candidate.docket_id] = (
                    candidate.docket_id,
                    "docket_page_acquisition",
                    str(exc),
                )
                active.pop(candidate.docket_id, None)
            else:
                base_urls[candidate.docket_id] = url

    for page_number in range(1, max_pages_per_docket + 1):
        if not active:
            break
        specs: list[FirecrawlTargetSpec] = []
        for candidate in active.values():
            source_url = canonical_courtlistener_docket_page_url(
                base_urls[candidate.docket_id],
                page_number=page_number,
            )
            specs.append(
                FirecrawlTargetSpec(
                    target_id=_page_target_id(candidate.docket_id, page_number),
                    target_kind="docket",
                    source_url=source_url,
                    page_number=page_number,
                    ordinal=(
                        (page_number - 1) * frozen_batch_candidate_count
                        + candidate.frozen_ordinal
                    ),
                )
            )
        run = scheduler.run(specs)
        summary = run.summary
        acquired = {page.target_id: page for page in run.pages}
        for docket_id, _candidate in tuple(active.items()):
            target_id = _page_target_id(docket_id, page_number)
            page = acquired.get(target_id)
            if page is None:
                failures[docket_id] = (
                    docket_id,
                    "docket_page_acquisition",
                    f"page_{page_number}_not_acquired",
                )
                del active[docket_id]
                continue
            pages[docket_id][page.source_url] = page.raw_html
            try:
                parsed = parse_courtlistener_docket_html(
                    page.raw_html,
                    source_url=page.source_url,
                    docket_id=docket_id,
                )
            except CourtListenerWebParseError as exc:
                failures[docket_id] = (
                    docket_id,
                    "complete_docket_reconstruction",
                    f"invalid_docket_page_artifact:{exc}",
                )
                del active[docket_id]
                continue
            if not parsed.has_next_page:
                del active[docket_id]

    for docket_id in active:
        failures[docket_id] = (
            docket_id,
            "docket_page_acquisition",
            "pagination_page_limit_reached",
        )

    bundles: list[CourtListenerDocketBundle] = []
    for candidate in candidates:
        if candidate.docket_id in failures:
            continue
        cached = pages[candidate.docket_id]
        try:
            bundle = paginate_courtlistener_docket(
                base_urls[candidate.docket_id],
                fetch=lambda url, cached=cached: cached[url],
                max_pages=max_pages_per_docket,
                decision_anchor=None,
            )
        except (
            KeyError,
            CourtListenerDocketPaginationError,
            CourtListenerWebParseError,
        ) as exc:
            failures[candidate.docket_id] = (
                candidate.docket_id,
                "complete_docket_reconstruction",
                str(exc) or type(exc).__name__,
            )
            continue
        if not bundle.is_exhaustive:
            failures[candidate.docket_id] = (
                candidate.docket_id,
                "complete_docket_reconstruction",
                "incomplete_docket_history",
            )
            continue
        bundles.append(bundle)
    return (
        tuple(bundles),
        tuple(
            failures[candidate.docket_id]
            for candidate in candidates
            if candidate.docket_id in failures
        ),
        summary,
    )


def _screen_bundle(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    candidate: FrozenFirecrawlCandidate,
    bundle: CourtListenerDocketBundle,
    eligibility_anchor: date,
    decision_window_end: date | None,
) -> CandidateObservation:
    payload = candidate.payload
    docket = CourtListenerDocket(
        docket_id=candidate.docket_id,
        court_id=_optional_text(payload.get("court_id")),
        docket_number=_optional_text(payload.get("docket_number")),
        case_name=_optional_text(payload.get("case_name"))
        or bundle.title
        or f"CourtListener docket {candidate.docket_id}",
        date_filed=_optional_text(payload.get("date_filed")),
        source_url=bundle.base_url,
        raw=payload,
    )
    query = payload.get("query_term")
    metadata_screen = screen_case_dev_docket_metadata(
        {
            "id": docket.docket_id,
            "court_id": docket.court_id,
            "docket_number": docket.docket_number,
            "case_name": docket.case_name,
        },
        query=query if isinstance(query, str) else None,
    )
    screening_page = CourtListenerWebDocketPage(
        docket_id=bundle.docket_id,
        source_url=canonical_courtlistener_docket_page_url(
            bundle.base_url,
            page_number=1,
        ),
        title=bundle.title,
        entries=bundle.entries,
        has_next_page=False,
    )
    canonical, exclusion = screen_courtlistener_docket_page(
        docket=docket,
        metadata_screen=metadata_screen,
        page=screening_page,
        decision_filed_on_or_after=eligibility_anchor,
        decision_filed_on_or_before=decision_window_end,
    )
    pagination = _pagination_evidence(bundle)
    if canonical is not None:
        return _record_observation(
            store,
            batch_id=batch_id,
            candidate=candidate,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                **dict(canonical),
                "canonical_firecrawl_screen_complete": True,
                "pagination_proof": pagination,
            },
        )
    if exclusion is None:
        raise FrozenBatchFirecrawlObservationError(
            "canonical Firecrawl screen returned neither a case nor exclusion"
        )
    exclusion_record = exclusion.to_record()
    if exclusion.reason == "parse_error":
        return _record_observation(
            store,
            batch_id=batch_id,
            candidate=candidate,
            state="transient_failure",
            reason_code="parse_failure",
            evidence={
                "canonical_screen_exclusion": exclusion_record,
                "pagination_proof": pagination,
                "error": exclusion.notes,
            },
        )
    registered_reasons = {
        reason
        for reasons in cohort_reason_policy_taxonomy().values()
        for reason in reasons
    }
    reason_code = (
        exclusion.reason
        if exclusion.reason in registered_reasons
        else "strict_clean_screen_failed"
    )
    return _record_observation(
        store,
        batch_id=batch_id,
        candidate=candidate,
        state="excluded",
        reason_code=reason_code,
        evidence={
            "canonical_screen_exclusion": exclusion_record,
            "pagination_proof": pagination,
        },
    )


def _record_observation(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    candidate: FrozenFirecrawlCandidate,
    state: str,
    reason_code: str,
    evidence: Mapping[str, object],
) -> CandidateObservation:
    return store.record_observation(
        candidate.candidate_id,
        batch_id=batch_id,
        state=state,
        reason_code=reason_code,
        evidence={
            "candidate_id": candidate.candidate_id,
            "docket_id": candidate.docket_id,
            "provider": FIRECRAWL_OBSERVATION_PROVIDER,
            "frozen_ordinal": candidate.frozen_ordinal,
            **dict(evidence),
        },
    )


def _tally_observation(
    observation: CandidateObservation,
    *,
    excluded: dict[str, int],
    transient: dict[str, int],
) -> None:
    if observation.state == "excluded":
        excluded[observation.reason_code] = excluded.get(observation.reason_code, 0) + 1
    elif observation.state == "transient_failure":
        transient[observation.reason_code] = (
            transient.get(observation.reason_code, 0) + 1
        )


def _pagination_evidence(bundle: CourtListenerDocketBundle) -> dict[str, object]:
    return {
        "base_url": bundle.base_url,
        "is_exhaustive": bundle.is_exhaustive,
        "stopped_at_anchor_boundary": bundle.stopped_at_anchor_boundary,
        "complete_for_anchor_window": bundle.complete_for_anchor_window,
        "pages": [
            {
                "page_number": page.page_number,
                "source_url": page.source_url,
                "sha256": page.sha256,
                "entry_row_ids": list(page.entry_row_ids),
                "has_next_page": page.has_next_page,
            }
            for page in bundle.pages
        ],
    }


def _decision_entry_lower_bound(payload: Mapping[str, Any]) -> int | None:
    evidence = payload.get("decision_entry_evidence")
    if not isinstance(evidence, Mapping):
        return None
    raw = cast(Mapping[str, object], evidence).get("entry_number")
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _page_target_id(docket_id: str, page_number: int) -> str:
    value = f"{docket_id}:{page_number}"
    return "docket-" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _string_set_sha256(values: Sequence[str]) -> str:
    return _canonical_sha256(sorted(values))


def _string_sequence_sha256(values: Sequence[str]) -> str:
    return _canonical_sha256(list(values))


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()

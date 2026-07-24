"""One-command drivers for the Cycle 1 batch-002 RECAP REST v4 pipeline.

The heavy lifting already lives in :mod:`legalforecast.ingestion.recap_api_discovery`
(decision-first search, fail-closed docket reconstruction, strict-screen
observation) and :mod:`legalforecast.ingestion.discovery_scheduler` (resumable,
per-term bounded materialization).  This module is the thin composition layer the
operator drives through the CLI: it wires those primitives to the durable
:class:`~legalforecast.ingestion.cycle_acquisition_store.CycleAcquisitionStore`
and emits funnel-style summaries.

The phases and transfer paths are resumable through the store and fail closed:

``discover``
    Attach the batch config, materialize each frozen decision-first term's own
    top-K, and report the discovery funnel.

``observe``
    Reconstruct + strict-screen every candidate lacking a current terminal
    observation, token-gated and politely paced, and report eligible/excluded
    tallies.  Re-running skips candidates that already carry a current
    observation.

``seed-batch-001-leads``
    Read the batch-001 store (read-only) for the candidates that never reached a
    terminal observation -- the Case.dev enrichment failures -- and seed their
    docket ids into the batch-002 store under a dedicated re-observation term so
    ``observe`` covers them.  Idempotent.

``seed-direct-search``
    Verify a saturated direct CourtListener search batch, transfer its exact
    docket union into a source-bound REST reconstruction batch, and preserve the
    cheapest safe prescreens and triggering-entry lower bounds. No provider
    request is made by this phase.

``rebind-direct-search``
    Verify the same complete source, transfer its exact lead set into a distinct
    current-code cycle, and commit both cycle identities. This is the explicit
    provider-free bridge after screening code changes; ordinary same-cycle
    transfers remain on ``seed-direct-search``.

``seed-novel-direct-search``
    Verify one or more complete saturated prior screening snapshots, then seed
    only provider-source dockets absent from their candidate-ID union. This is
    priority dedupe only: prior outcomes never become current-cycle exclusions.

Nothing here mutates the frozen screening files or the source batch-001 store.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.courtlistener_opinion_discovery import (
    OPINION_API_PAGE_SIZE,
    OPINION_MTD_SEARCH_TERMS,
    OpinionApiDiscoverySource,
    build_opinion_batch_config,
)
from legalforecast.ingestion.courtlistener_unrestricted_recap_discovery import (
    UNRESTRICTED_RECAP_PAGE_SIZE,
    UNRESTRICTED_RECAP_SEARCH_TERMS,
    run_unrestricted_recap_discovery,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    SnapshotVerificationError,
    cohort_reason_policy_taxonomy,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
    materialize_independent_term_sets,
)
from legalforecast.ingestion.recap_api_discovery import (
    RECAP_API_PROVIDER,
    RecapApiDiscoverySource,
    RecapApiResponseError,
    RequestPacer,
    build_recap_api_batch_config,
    candidate_docket_id,
    observe_prescreened_reason,
    observe_recap_api_candidate,
    prescreen_recap_candidate,
    require_reconstruction_auth,
    resolve_auth_mode,
)

# The dedicated term under which batch-001 re-observation leads are seeded. It is
# deliberately *not* one of the eight frozen decision-first search terms: those
# are provider search queries, this one is a synthetic carrier for docket ids
# recovered from a prior batch.  Keeping it separate means the eight real terms
# still reach their own independent terminal states.
BATCH_001_REOBSERVATION_TERM = "batch-001-case-dev-reobservation"
BATCH_001_REOBSERVATION_PROVENANCE_SCHEMA = (
    "legalforecast.batch_001_reobservation_lead.v1"
)
# Batch-001 recorded Case.dev enrichment outcomes only for the dockets that
# *succeeded*; a failed enrichment left the candidate with no terminal
# observation at all (``candidates.current_observation_id IS NULL``).  That NULL
# state -- corroborated by ``checkpoints/case-dev-recap-failures.jsonl`` -- is the
# authoritative marker of an enrichment failure, so it is the seed selector.
BATCH_001_ENRICHMENT_FAILURE_CLASS = "case_dev_enrichment_failure"
DIRECT_SEARCH_TRANSFER_TERM = "courtlistener-direct-search-transfer-v1"
DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA = (
    "legalforecast.courtlistener_direct_search_transfer.v1"
)
DIRECT_SEARCH_CYCLE_REBIND_TERM = "courtlistener-direct-search-cycle-rebind-v1"
DIRECT_SEARCH_CYCLE_REBIND_PROVENANCE_SCHEMA = (
    "legalforecast.courtlistener_direct_search_cycle_rebind.v1"
)
DIRECT_SEARCH_NOVEL_TRANSFER_TERM = "courtlistener-novel-direct-search-transfer-v1"
DIRECT_SEARCH_NOVEL_TRANSFER_PROVENANCE_SCHEMA = (
    "legalforecast.courtlistener_novel_direct_search_transfer.v1"
)
DIRECT_SEARCH_PRIORITY_TRANCHE_TERM = "courtlistener-direct-search-priority-tranche-v1"
DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA = (
    "legalforecast.direct_search_priority_tranche.v1"
)
DIRECT_SEARCH_DEFERRED_FRONTIER_SCHEMA = (
    "legalforecast.direct_search_deferred_frontier.v1"
)
_DIRECT_SEARCH_TARGET_MOTION_TOKENS = (
    "motion to dismiss",
    "judgment on the pleadings",
    "rule 12",
    "12(b)",
    "12(c)",
    "rule 7012",
    "7012(b)",
    "adversary complaint",
    "adversary proceeding",
)
_DIRECT_SEARCH_TARGET_MOTION_PATTERN = (
    r"\b(?:motions?\s+(?:to\s+dismiss|for\s+judgment\s+on\s+(?:the\s+)?pleadings)|"
    r"rule\s+12(?:\([bc]\)(?:\(\d+\))?)?|12\([bc]\)(?:\(\d+\))?|"
    r"(?:rule\s+)?7012(?:\(b\))?|"
    r"adversary\s+(?:complaint|proceeding))\b"
)
_DIRECT_SEARCH_ADJUDICATIVE_DOCUMENT_PATTERN = (
    r"\b(?:order|opinion|memorandum\s+(?:opinion|decision)|"
    r"memorandum\s+and\s+order|judgment)\b"
)
_DIRECT_SEARCH_SUBSTANTIVE_RECOMMENDATION_PATTERN = (
    r"\b(?:report\s+(?:and|&)\s+recommendation|"
    r"findings\s+(?:and|&)\s+recommendation|r\s*&?\s*r)\b"
)
_DIRECT_SEARCH_NON_DECISION_DOCUMENT_PATTERN = (
    r"(?:\b(?:proposed|standing)\s+order\b|"
    r"^\s*(?:reply|response|opposition|memorandum\s+in\s+support)\b|"
    r"\b(?:plaintiff|petitioner)'?s\s+motion\s+to\s+dismiss\b|"
    r"\b(?:page\s+limits?|extension\s+of\s+time|briefing\s+schedule)\b|"
    r"\b(?:notified|advised)\b[^.;:\n]{0,160}\bmotion\s+to\s+dismiss\b)"
)
_DIRECT_SEARCH_DISPOSITION_PATTERN = (
    r"\b(?:grant(?:ed|ing)?|den(?:y|ied|ying)|dismiss(?:ed|ing)|"
    r"adopt(?:ed|ing)?|recommend(?:ed|ing)?|moot(?:ed)?)\b"
)
PRIOR_SNAPSHOT_PRIORITY_DEDUPE_SCHEMA = (
    "legalforecast.prior_screening_snapshot_priority_dedupe.v1"
)
_DIRECT_SEARCH_PRIORITY_POLICY: dict[str, object] = {
    "schema_version": "legalforecast.direct_search_decision_signal_ranking.v2",
    "semantics": "rank_only_no_membership_exclusion",
    "structural_order": (
        "prescreen_clean_or_deferred_authoritative_bankruptcy",
        "known_prescreen_reason_deferred_not_excluded",
    ),
    "signal_order": (
        "action_linked_disposition_or_substantive_recommendation",
        "anchored_adjudicative_event",
        "generic_motion_or_brief",
        "no_decision_entry_evidence",
    ),
    "date_semantics": "valid_post_anchor_provider_metadata_only",
    "free_availability_semantics": (
        "secondary_rank_only_never_eligibility_or_completeness"
    ),
    "target_motion_vocabulary": _DIRECT_SEARCH_TARGET_MOTION_TOKENS,
    "target_motion_pattern": _DIRECT_SEARCH_TARGET_MOTION_PATTERN,
    "adjudicative_document_pattern": _DIRECT_SEARCH_ADJUDICATIVE_DOCUMENT_PATTERN,
    "substantive_recommendation_pattern": (
        _DIRECT_SEARCH_SUBSTANTIVE_RECOMMENDATION_PATTERN
    ),
    "non_decision_document_pattern": _DIRECT_SEARCH_NON_DECISION_DOCUMENT_PATTERN,
    "disposition_pattern": _DIRECT_SEARCH_DISPOSITION_PATTERN,
    "tie_breakers": (
        "prescreen_structural_rank",
        "decision_signal_rank",
        "newest_valid_entry_date",
        "lowest_entry_number",
        "numeric_docket_id",
        "candidate_id",
    ),
}
DIRECT_SEARCH_PRIORITY_POLICY_SHA256 = hashlib.sha256(
    json.dumps(
        _DIRECT_SEARCH_PRIORITY_POLICY,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()
_POSITIVE_ASCII_INTEGER = re.compile(r"[1-9][0-9]*")
_SNAPSHOT_METADATA_FILES = (
    "manifest.json",
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
)


class RecapApiBatchDriverError(RuntimeError):
    """Raised when a batch-002 driver phase cannot proceed safely."""


# ---------------------------------------------------------------------------
# Phase 1: discover.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TermFunnelRow:
    """Per-term discovery progress for the funnel print."""

    term: str
    hit_count: int
    terminal_status: str


@dataclass(frozen=True, slots=True)
class DiscoverFunnel:
    """Funnel-style summary of a batch-002 discovery pass."""

    batch_id: str
    terms_total: int
    terms_terminal: int
    total_hits: int
    distinct_candidates: int
    prescreen_exclusions_by_reason: Mapping[str, int]
    per_term: tuple[TermFunnelRow, ...]
    complete: bool
    saturated: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.batch_002_discover_funnel.v1",
            "batch_id": self.batch_id,
            "terms_total": self.terms_total,
            "terms_terminal": self.terms_terminal,
            "total_hits": self.total_hits,
            "distinct_candidates": self.distinct_candidates,
            "prescreen_exclusions_total": sum(
                self.prescreen_exclusions_by_reason.values()
            ),
            "prescreen_exclusions_by_reason": dict(
                sorted(self.prescreen_exclusions_by_reason.items())
            ),
            "per_term": [
                {
                    "term": row.term,
                    "hit_count": row.hit_count,
                    "terminal_status": row.terminal_status,
                }
                for row in self.per_term
            ],
            "complete": self.complete,
            "saturated": self.saturated,
        }


def run_discover(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    client: CourtListenerClient,
    decision_window_start: date,
    decision_window_end: date,
    top_k_per_term: int = 5_000,
    page_size: int = 100,
    pacer: RequestPacer | None = None,
) -> DiscoverFunnel:
    """Attach the batch, materialize each frozen term, and summarize the funnel.

    The cycle identity must already be frozen on ``store`` (the CLI handler owns
    that step so the source-neutral cycle policy stays in one place).  Resume is
    automatic: :func:`materialize_independent_term_sets` reads durable per-term
    cursors, so a re-run continues where a prior run stopped and cannot skip or
    double-count candidates.
    """

    auth_mode = resolve_auth_mode(client)
    config = build_recap_api_batch_config(
        decision_window_start=decision_window_start,
        decision_window_end=decision_window_end,
        auth_mode=auth_mode,
        page_size=page_size,
        top_k_per_term=top_k_per_term,
    )
    store.ensure_batch(batch_id, config)
    query_terms = tuple(cast(Sequence[str], config["query_terms"]))
    source = RecapApiDiscoverySource(
        client=client,
        entry_date_filed_after=decision_window_start,
        entry_date_filed_before=decision_window_end,
        pacer=pacer,
        auth_mode=auth_mode,
    )
    summary = materialize_independent_term_sets(
        source=source,
        store=store,
        batch_id=batch_id,
        query_terms=query_terms,
        top_k_per_term=top_k_per_term,
        page_size=page_size,
    )

    per_term: list[TermFunnelRow] = []
    total_hits = 0
    terms_terminal = 0
    for term in query_terms:
        progress = store.term_progress(batch_id, term)
        total_hits += progress.hit_count
        status = summary.terminal_status_by_term.get(term)
        if status is not None:
            terms_terminal += 1
        per_term.append(
            TermFunnelRow(
                term=term,
                hit_count=progress.hit_count,
                terminal_status=status.value if status is not None else "incomplete",
            )
        )

    prescreen = _prescreen_exclusion_counts(store, batch_id)
    return DiscoverFunnel(
        batch_id=batch_id,
        terms_total=len(query_terms),
        terms_terminal=terms_terminal,
        total_hits=total_hits,
        distinct_candidates=len(summary.candidate_ids),
        prescreen_exclusions_by_reason=prescreen,
        per_term=tuple(per_term),
        complete=summary.complete,
        saturated=summary.saturated,
    )


def run_opinion_discover(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    client: CourtListenerClient,
    decision_window_start: date,
    decision_window_end: date,
    query_terms: Sequence[str] = OPINION_MTD_SEARCH_TERMS,
    top_k_per_term: int = 5_000,
    pacer: RequestPacer | None = None,
) -> DiscoverFunnel:
    """Materialize a durable CourtListener opinion-cluster discovery union.

    Opinion search supplies a high-precision written-decision lead: the cluster
    is retained as the provider-hit identity while its explicit ``docket_id``
    becomes the candidate identity consumed by ``seed-direct-search``.  The
    downstream authenticated docket reconstruction remains authoritative for
    motion linkage and first-disposition eligibility.
    """

    config = build_opinion_batch_config(
        decision_window_start=decision_window_start,
        decision_window_end=decision_window_end,
        query_terms=query_terms,
        top_k_per_term=top_k_per_term,
    )
    terms = tuple(cast(Sequence[str], config["query_terms"]))
    store.ensure_batch(batch_id, config)
    source = OpinionApiDiscoverySource(
        client=client,
        decision_window_start=decision_window_start,
        decision_window_end=decision_window_end,
        pacer=pacer,
    )
    summary = materialize_independent_term_sets(
        source=source,
        store=store,
        batch_id=batch_id,
        query_terms=terms,
        top_k_per_term=top_k_per_term,
        page_size=OPINION_API_PAGE_SIZE,
    )

    per_term: list[TermFunnelRow] = []
    total_hits = 0
    terms_terminal = 0
    for term in terms:
        progress = store.term_progress(batch_id, term)
        total_hits += progress.hit_count
        status = summary.terminal_status_by_term.get(term)
        if status is not None:
            terms_terminal += 1
        per_term.append(
            TermFunnelRow(
                term=term,
                hit_count=progress.hit_count,
                terminal_status=status.value if status is not None else "incomplete",
            )
        )

    return DiscoverFunnel(
        batch_id=batch_id,
        terms_total=len(terms),
        terms_terminal=terms_terminal,
        total_hits=total_hits,
        distinct_candidates=len(summary.candidate_ids),
        prescreen_exclusions_by_reason=_prescreen_exclusion_counts(store, batch_id),
        per_term=tuple(per_term),
        complete=summary.complete,
        saturated=summary.saturated,
    )


def run_unrestricted_discover(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    client: CourtListenerClient,
    decision_window_start: date,
    decision_window_end: date,
    query_terms: Sequence[str] = UNRESTRICTED_RECAP_SEARCH_TERMS,
    top_k_per_term: int = 5_000,
    pacer: RequestPacer | None = None,
) -> DiscoverFunnel:
    """Materialize filing-level RECAP leads without an availability filter."""

    summary = run_unrestricted_recap_discovery(
        store=store,
        batch_id=batch_id,
        client=client,
        search_window_start=decision_window_start,
        search_window_end=decision_window_end,
        auth_mode="authenticated",
        query_terms=query_terms,
        page_size=UNRESTRICTED_RECAP_PAGE_SIZE,
        top_k_per_term=top_k_per_term,
        pacer=pacer,
    )
    config = store.batch_config(batch_id)
    terms = tuple(cast(Sequence[str], config["query_terms"]))
    per_term: list[TermFunnelRow] = []
    total_hits = 0
    terms_terminal = 0
    for term in terms:
        progress = store.term_progress(batch_id, term)
        total_hits += progress.hit_count
        status = summary.terminal_status_by_term.get(term)
        if status is not None:
            terms_terminal += 1
        per_term.append(
            TermFunnelRow(
                term=term,
                hit_count=progress.hit_count,
                terminal_status=status.value if status is not None else "incomplete",
            )
        )
    return DiscoverFunnel(
        batch_id=batch_id,
        terms_total=len(terms),
        terms_terminal=terms_terminal,
        total_hits=total_hits,
        distinct_candidates=len(summary.candidate_ids),
        prescreen_exclusions_by_reason=_prescreen_exclusion_counts(store, batch_id),
        per_term=tuple(per_term),
        complete=summary.complete,
        saturated=summary.saturated,
    )


def _prescreen_exclusion_counts(
    store: CycleAcquisitionStore, batch_id: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in store.candidate_discovery_hits(batch_id):
        reason = observe_prescreened_reason(hit.payload)
        if reason is not None:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Phase 2: observe.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObserveTally:
    """Running tallies for a batch-002 observation pass."""

    considered: int
    skipped_already_observed: int
    observed: int
    eligible: int
    excluded_by_reason: Mapping[str, int]
    transient_by_reason: Mapping[str, int]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.batch_002_observe_tally.v1",
            "considered": self.considered,
            "skipped_already_observed": self.skipped_already_observed,
            "observed": self.observed,
            "eligible": self.eligible,
            "excluded_total": sum(self.excluded_by_reason.values()),
            "excluded_by_reason": dict(sorted(self.excluded_by_reason.items())),
            "transient_total": sum(self.transient_by_reason.values()),
            "transient_by_reason": dict(sorted(self.transient_by_reason.items())),
        }


# Observation states the strict-screen route can emit through the store.
_ELIGIBLE_STATES = frozenset({"accepted", "newly_free"})
_INTEGER_PREFIX = re.compile(r"^\s*(\d+)")


def _positive_integer_prefix(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if not isinstance(value, str):
        return None
    match = _INTEGER_PREFIX.match(value)
    return int(match.group(1)) if match is not None else None


def _observation_priority(
    candidate_id: str, payload: Mapping[str, Any]
) -> tuple[int, int, int, int, int, int, str]:
    """Order unresolved candidates by expected free-screening cost.

    The sort key uses only frozen discovery evidence, so it changes traversal
    order without changing candidate membership or selected evidence.  Stored
    prescreens are zero-request outcomes.  A low triggering entry number is the
    strongest available proxy for a short docket; unknown sizes precede dockets
    already proven likely to exceed the six-page reconstruction cap.  Direct
    decision-search hits then outrank synthetic batch-001 retry leads, with
    recent decisions and newer docket ids as stable final cost proxies.
    """

    prescreen_rank = 0 if observe_prescreened_reason(payload) is not None else 1
    raw_evidence = payload.get("decision_entry_evidence")
    evidence = (
        cast("Mapping[str, object]", raw_evidence)
        if isinstance(raw_evidence, Mapping)
        else None
    )
    direct_rank = 0 if evidence is not None else 1
    entry_number: int | None = None
    decision_ordinal = 0
    if evidence is not None:
        entry_number = _positive_integer_prefix(evidence.get("entry_number"))
        raw_decision_date = evidence.get("entry_date_filed")
        if isinstance(raw_decision_date, str):
            try:
                decision_ordinal = date.fromisoformat(raw_decision_date).toordinal()
            except ValueError:
                # Malformed provider dates remain unknown and keep the neutral
                # rank; eligibility parsing later still fails closed.
                decision_ordinal = 0
    if entry_number is None:
        entry_bucket, entry_value = 1, 0
    elif entry_number > 600:
        entry_bucket, entry_value = 2, entry_number
    else:
        entry_bucket, entry_value = 0, entry_number
    docket_number = _positive_integer_prefix(payload.get("docket_id"))
    if docket_number is None:
        docket_number = _positive_integer_prefix(
            candidate_id.removeprefix("courtlistener-docket-")
        )
    return (
        prescreen_rank,
        entry_bucket,
        entry_value,
        direct_rank,
        -decision_ordinal,
        -(docket_number or 0),
        candidate_id,
    )


def _config_window_end(store: CycleAcquisitionStore, batch_id: str) -> date | None:
    """Read the frozen decision-window upper bound from the batch config."""

    raw = store.batch_config(batch_id).get("decision_window_end")
    if isinstance(raw, str) and raw.strip():
        return date.fromisoformat(raw)
    return None


def _validate_frozen_eligibility_anchor(
    store: CycleAcquisitionStore, requested: date
) -> None:
    """Fail closed unless ``requested`` matches the frozen cycle policy."""

    raw = store.cycle_policy.get("eligibility_anchor")
    if not isinstance(raw, str) or not raw.strip():
        raise RecapApiBatchDriverError(
            "frozen cycle policy is missing eligibility_anchor"
        )
    try:
        frozen = date.fromisoformat(raw)
    except ValueError as exc:
        raise RecapApiBatchDriverError(
            f"frozen cycle policy has invalid eligibility_anchor: {raw!r}"
        ) from exc
    if requested != frozen:
        raise RecapApiBatchDriverError(
            "eligibility anchor mismatch: "
            f"requested {requested.isoformat()}, frozen {frozen.isoformat()}"
        )


def _refine_excluded_reason(observation: CandidateObservation) -> str:
    """Expose the underlying strict-screen reason for operator visibility.

    ``_map_screen_outcome`` collapses every strict-screen exclusion into
    ``strict_clean_screen_failed``; the finer screen reason survives in the
    observation evidence, so the tally recovers it as
    ``strict_clean_screen_failed:<screen_reason>`` when present.
    """

    reason = observation.reason_code
    if reason != "strict_clean_screen_failed":
        return reason
    screen: object = observation.evidence.get("screen")
    if isinstance(screen, Mapping):
        reasons: object = cast("Mapping[str, object]", screen).get("exclusion_reasons")
        if isinstance(reasons, (list, tuple)) and reasons:
            return f"{reason}:{reasons[0]!s}"
    return reason


def run_observe(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    client: CourtListenerClient,
    eligibility_anchor: date,
    pacer: RequestPacer | None = None,
    limit: int | None = None,
    refresh_reason_codes: Sequence[str] = (),
    revalidate_candidate_ids: Sequence[str] = (),
    refresh_campaign_cutoff: str | None = None,
    progress_callback: Callable[[ObserveTally], None] | None = None,
) -> ObserveTally:
    """Reconstruct, screen, and durably observe every unresolved candidate.

    Fails closed *before any network request* when no CourtListener API token is
    configured, because docket reconstruction needs one.  A candidate that
    already carries a current (terminal) observation is skipped, so re-running is
    safe and resumes exactly where a prior pass stopped; a candidate whose only
    prior observation was a transient failure is retried (transient failures
    never become the current observation). ``refresh_reason_codes`` is an
    explicit, auditable escape hatch for re-running current observations whose
    policy class is refreshable after a screening implementation correction.
    ``revalidate_candidate_ids`` narrowly re-runs named accepted candidates
    after a documented false-positive correction. Refresh/revalidation campaigns
    require a frozen UTC cutoff; only observations predating it are eligible, so
    repeated limited invocations advance instead of consuming requests on the
    same candidates.
    """

    store.batch_digest(batch_id)
    _validate_frozen_eligibility_anchor(store, eligibility_anchor)
    require_reconstruction_auth(client)
    decision_window_end = _config_window_end(store, batch_id)
    refresh_reasons = frozenset(refresh_reason_codes)
    campaign_requested = bool(refresh_reasons or revalidate_candidate_ids)
    if campaign_requested and refresh_campaign_cutoff is None:
        raise RecapApiBatchDriverError(
            "refresh/revalidation requires --refresh-campaign-cutoff"
        )
    campaign_cutoff = (
        _utc_timestamp(refresh_campaign_cutoff, "refresh_campaign_cutoff")
        if refresh_campaign_cutoff is not None
        else None
    )
    allowed_refresh_reasons = frozenset(
        cohort_reason_policy_taxonomy()["refreshable_reason_codes"]
    )
    invalid_refresh_reasons = refresh_reasons - allowed_refresh_reasons
    if invalid_refresh_reasons:
        invalid = sorted(invalid_refresh_reasons)[0]
        raise RecapApiBatchDriverError(f"reason code {invalid!r} is not refreshable")

    payloads = {
        hit.candidate_id: hit.payload
        for hit in store.candidate_discovery_hits(
            batch_id,
            deprioritized_terms=(BATCH_001_REOBSERVATION_TERM,),
        )
    }

    considered = 0
    skipped = 0
    observed = 0
    eligible = 0
    excluded: dict[str, int] = {}
    transient: dict[str, int] = {}

    candidate_ids = store.candidate_ids(batch_id)
    candidate_id_set = frozenset(candidate_ids)
    revalidate_ids = frozenset(revalidate_candidate_ids)
    unknown_revalidation_ids = revalidate_ids - candidate_id_set
    if unknown_revalidation_ids:
        unknown = sorted(unknown_revalidation_ids)[0]
        raise RecapApiBatchDriverError(
            f"revalidation candidate {unknown!r} is not in batch {batch_id}"
        )
    missing_payloads = tuple(
        candidate_id for candidate_id in candidate_ids if candidate_id not in payloads
    )
    if missing_payloads:
        raise RecapApiBatchDriverError(
            f"candidate {missing_payloads[0]} has no discovery hit payload to observe"
        )
    current_observations = {
        candidate_id: store.current_observation(candidate_id)
        for candidate_id in candidate_ids
    }
    for candidate_id in sorted(revalidate_ids):
        current = current_observations[candidate_id]
        if current is None or current.state not in {"accepted", "newly_free"}:
            raise RecapApiBatchDriverError(
                f"revalidation candidate {candidate_id!r} is not currently accepted"
            )

    def predates_campaign(candidate_id: str) -> bool:
        current = current_observations[candidate_id]
        return bool(
            current is not None
            and campaign_cutoff is not None
            and _utc_timestamp(current.observed_at, "observation observed_at")
            < campaign_cutoff
        )

    def selected_for_campaign(candidate_id: str) -> bool:
        current = current_observations[candidate_id]
        return predates_campaign(candidate_id) and bool(
            candidate_id in revalidate_ids
            or (current is not None and current.reason_code in refresh_reasons)
        )

    def refresh_rank(candidate_id: str) -> int:
        return 0 if selected_for_campaign(candidate_id) else 1

    ordered_candidate_ids = sorted(
        candidate_ids,
        key=lambda candidate_id: (
            refresh_rank(candidate_id),
            _observation_priority(candidate_id, payloads[candidate_id]),
        ),
    )

    for candidate_id in ordered_candidate_ids:
        if limit is not None and observed >= limit:
            break
        considered += 1
        current = current_observations[candidate_id]
        if current is not None and not selected_for_campaign(candidate_id):
            skipped += 1
            continue
        payload = payloads[candidate_id]
        observation = observe_recap_api_candidate(
            store,
            batch_id,
            payload,
            client=client,
            eligibility_anchor=eligibility_anchor,
            decision_window_end=decision_window_end,
            pacer=pacer,
        )
        observed += 1
        if observation.state in _ELIGIBLE_STATES:
            eligible += 1
        elif observation.state == "excluded":
            reason_key = _refine_excluded_reason(observation)
            excluded[reason_key] = excluded.get(reason_key, 0) + 1
        elif observation.state == "transient_failure":
            transient[observation.reason_code] = (
                transient.get(observation.reason_code, 0) + 1
            )
        if progress_callback is not None:
            progress_callback(
                ObserveTally(
                    considered=considered,
                    skipped_already_observed=skipped,
                    observed=observed,
                    eligible=eligible,
                    excluded_by_reason=dict(excluded),
                    transient_by_reason=dict(transient),
                )
            )

    return ObserveTally(
        considered=considered,
        skipped_already_observed=skipped,
        observed=observed,
        eligible=eligible,
        excluded_by_reason=excluded,
        transient_by_reason=transient,
    )


def _utc_timestamp(raw: str, field: str) -> datetime:
    """Parse one timezone-aware timestamp and normalize it to UTC."""

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecapApiBatchDriverError(
            f"{field} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise RecapApiBatchDriverError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


# ---------------------------------------------------------------------------
# Phase 3: seed batch-001 Case.dev enrichment-failure leads.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Batch001Lead:
    """One batch-001 candidate whose Case.dev enrichment never resolved."""

    candidate_id: str
    docket_id: str
    source_first_batch_id: str
    case_name: str | None
    docket_number: str | None
    court_id: str | None


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Outcome of a batch-001 re-observation seeding pass."""

    batch_id: str
    leads_selected: int
    leads_seeded: int
    already_seeded: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.batch_002_seed_result.v1",
            "batch_id": self.batch_id,
            "term": BATCH_001_REOBSERVATION_TERM,
            "leads_selected": self.leads_selected,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
        }


@dataclass(frozen=True, slots=True)
class DirectSearchHitProvenance:
    """Immutable identity of one source search hit contributing a docket lead."""

    provider_hit_id: str
    query_term: str
    payload_sha256: str

    def to_record(self) -> dict[str, str]:
        return {
            "provider_hit_id": self.provider_hit_id,
            "query_term": self.query_term,
            "payload_sha256": self.payload_sha256,
        }


@dataclass(frozen=True, slots=True)
class DirectSearchLead:
    """One numeric direct-search candidate transferred for REST reconstruction."""

    docket_id: str
    source_provider_hit_id: str
    source_query_term: str
    source_payload_sha256: str
    source_hits: tuple[DirectSearchHitProvenance, ...]
    court_id: str | None
    docket_number: str | None
    case_name: str | None
    decision_entry_evidence: Mapping[str, object] | None
    opinion_resolution_evidence: Mapping[str, object] | None = None
    priority_decision_evidence: Mapping[str, object] | None = None

    @property
    def candidate_id(self) -> str:
        return f"courtlistener-docket-{self.docket_id}"

    def commitment_record(self) -> dict[str, object]:
        """Return the canonical source record covered by the set commitment."""

        record: dict[str, object] = {
            "docket_id": self.docket_id,
            "court_id": self.court_id,
            "docket_number": self.docket_number,
            "case_name": self.case_name,
            "decision_entry_evidence": (
                None
                if self.decision_entry_evidence is None
                else dict(self.decision_entry_evidence)
            ),
            "opinion_resolution_evidence": (
                None
                if self.opinion_resolution_evidence is None
                else dict(self.opinion_resolution_evidence)
            ),
            "source_hits": [hit.to_record() for hit in self.source_hits],
        }
        if self.priority_decision_evidence is not None:
            record["priority_decision_evidence"] = dict(self.priority_decision_evidence)
        return record


@dataclass(frozen=True, slots=True)
class DirectSearchSeedSource:
    """Verified saturated direct-search source and its deterministic leads."""

    source_batch_id: str
    source_batch_digest: str
    source_cycle_hash: str
    source_schema_version: str | None
    source_search_type: str | None
    source_available_only_present: bool
    source_available_only: str | None
    source_query_expression_present: bool
    source_query_expression: str | None
    source_query_terms: tuple[str, ...]
    source_candidate_set_sha256: str
    source_hit_set_sha256: str
    source_eligibility_anchor: str | None
    search_window_start: date
    search_window_end: date
    leads: tuple[DirectSearchLead, ...]
    source_lineage_commitments: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class DirectSearchSeedResult:
    """Outcome of a source-bound direct-search transfer pass."""

    batch_id: str
    source_batch_id: str
    source_batch_digest: str
    source_candidate_set_sha256: str
    leads_selected: int
    leads_seeded: int
    already_seeded: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.direct_search_seed_result.v1",
            "batch_id": self.batch_id,
            "term": DIRECT_SEARCH_TRANSFER_TERM,
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "source_candidate_set_sha256": self.source_candidate_set_sha256,
            "leads_selected": self.leads_selected,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
        }


@dataclass(frozen=True, slots=True)
class DirectSearchRebindResult:
    """Outcome of an explicit provider-free cross-cycle source rebind."""

    batch_id: str
    source_batch_id: str
    source_batch_digest: str
    source_cycle_hash: str
    target_cycle_hash: str
    source_candidate_set_sha256: str
    leads_selected: int
    leads_seeded: int
    already_seeded: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.direct_search_cycle_rebind_result.v1",
            "batch_id": self.batch_id,
            "term": DIRECT_SEARCH_CYCLE_REBIND_TERM,
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "source_cycle_hash": self.source_cycle_hash,
            "target_cycle_hash": self.target_cycle_hash,
            "source_candidate_set_sha256": self.source_candidate_set_sha256,
            "leads_selected": self.leads_selected,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }


@dataclass(frozen=True, slots=True)
class PriorScreeningSnapshot:
    """One fully verified terminal snapshot used only for priority dedupe."""

    path: Path
    manifest_sha256: str
    cycle_hash: str
    snapshot_id: str
    batch_id: str
    batch_digest: str
    candidate_ids: tuple[str, ...]
    candidate_set_sha256: str

    def commitment_record(self, *, source_cycle_hash: str) -> dict[str, object]:
        return {
            "snapshot_path": str(self.path),
            "snapshot_manifest_sha256": self.manifest_sha256,
            "cycle_hash": self.cycle_hash,
            "cycle_compatible_with_source": self.cycle_hash == source_cycle_hash,
            "snapshot_id": self.snapshot_id,
            "batch_id": self.batch_id,
            "batch_digest": self.batch_digest,
            "candidate_count": len(self.candidate_ids),
            "candidate_set_sha256": self.candidate_set_sha256,
        }


@dataclass(frozen=True, slots=True)
class NovelDirectSearchSeedResult:
    """Outcome of a source-bound priority-dedupe transfer."""

    batch_id: str
    source_batch_id: str
    source_batch_digest: str
    source_cycle_hash: str
    source_candidate_set_sha256: str
    prior_snapshot_commitment_sha256: str
    prior_snapshot_count: int
    cross_cycle_snapshot_count: int
    leads_selected: int
    leads_excluded_from_target: int
    selected_candidate_set_sha256: str
    excluded_candidate_set_sha256: str
    leads_seeded: int
    already_seeded: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.novel_direct_search_seed_result.v1",
            "batch_id": self.batch_id,
            "term": DIRECT_SEARCH_NOVEL_TRANSFER_TERM,
            "selection_semantics": "priority_dedupe_only",
            "prior_outcomes_authoritative": False,
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "source_cycle_hash": self.source_cycle_hash,
            "source_candidate_set_sha256": self.source_candidate_set_sha256,
            "prior_snapshot_commitment_sha256": (self.prior_snapshot_commitment_sha256),
            "prior_snapshot_count": self.prior_snapshot_count,
            "cross_cycle_snapshot_count": self.cross_cycle_snapshot_count,
            "leads_selected": self.leads_selected,
            "leads_excluded_from_target": self.leads_excluded_from_target,
            "selected_candidate_set_sha256": self.selected_candidate_set_sha256,
            "excluded_candidate_set_sha256": self.excluded_candidate_set_sha256,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
        }


@dataclass(frozen=True, slots=True)
class DirectSearchPriorityTrancheResult:
    """One exact rank-only tranche and its committed deferred frontier."""

    batch_id: str
    source_batch_id: str
    source_batch_digest: str
    source_candidate_set_sha256: str
    ranking_policy_sha256: str
    tranche_ordinal: int
    selected_candidate_ids: tuple[str, ...]
    deferred_candidate_ids: tuple[str, ...]
    cumulative_selected_count: int
    frontier_sha256: str
    frontier: Mapping[str, object]
    leads_seeded: int
    already_seeded: bool

    @property
    def selected_count(self) -> int:
        return len(self.selected_candidate_ids)

    @property
    def deferred_count(self) -> int:
        return len(self.deferred_candidate_ids)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
            "batch_id": self.batch_id,
            "term": DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,
            "selection_semantics": "rank_only_no_membership_exclusion",
            "deferred_disposition": "unscreened_not_excluded",
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "source_candidate_set_sha256": self.source_candidate_set_sha256,
            "ranking_policy_sha256": self.ranking_policy_sha256,
            "tranche_ordinal": self.tranche_ordinal,
            "selected_count": self.selected_count,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "deferred_count": self.deferred_count,
            "deferred_candidate_ids": list(self.deferred_candidate_ids),
            "cumulative_selected_count": self.cumulative_selected_count,
            "chain_terminal": self.deferred_count == 0,
            "ranking_frontier_exhausted": self.deferred_count == 0,
            "global_source_saturated": False,
            "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
            "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
            "frontier_sha256": self.frontier_sha256,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "evaluation_activity_executed": False,
            "freeze_activity_executed": False,
            "dispatch_activity_executed": False,
        }


def read_saturated_direct_search_leads(
    source_store_path: str | Path,
    *,
    source_batch_id: str,
) -> DirectSearchSeedSource:
    """Read one fully exhausted CourtListener direct-search batch, read-only."""

    path = Path(source_store_path)
    if not path.exists():
        raise RecapApiBatchDriverError(f"direct-search source store not found: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        batch = connection.execute(
            "SELECT config_json, config_digest FROM batches WHERE batch_id = ?",
            (source_batch_id,),
        ).fetchone()
        if batch is None:
            raise RecapApiBatchDriverError(
                f"direct-search source batch not found: {source_batch_id}"
            )
        config_json = str(batch["config_json"])
        source_batch_digest = str(batch["config_digest"])
        if hashlib.sha256(config_json.encode()).hexdigest() != source_batch_digest:
            raise RecapApiBatchDriverError(
                "direct-search source batch config digest is invalid"
            )
        decoded = cast(object, json.loads(config_json))
        if not isinstance(decoded, dict):
            raise RecapApiBatchDriverError(
                "direct-search batch config is not an object"
            )
        config = cast(dict[str, object], decoded)
        lineage_fields = (
            "discovery_mode",
            "selection_semantics",
            "source_batch_id",
            "source_batch_digest",
            "source_cycle_hash",
            "source_candidate_count",
            "source_candidate_set_sha256",
            "prior_snapshot_dedupe_schema",
            "prior_snapshot_commitment_sha256",
            "prior_snapshot_count",
            "cross_cycle_snapshot_count",
            "selected_candidate_count",
            "selected_candidate_set_sha256",
            "excluded_from_target_candidate_count",
            "excluded_from_target_candidate_set_sha256",
        )
        source_lineage_commitments = {
            field: config[field] for field in lineage_fields if field in config
        }
        source_lineage_commitments["authoritative_source_batch_digest"] = (
            source_batch_digest
        )
        source_lineage_commitment_sha256 = _canonical_record_sha256(
            source_lineage_commitments
        )
        if config.get("provider") not in {"courtlistener", RECAP_API_PROVIDER}:
            raise RecapApiBatchDriverError(
                "direct-search source batch is not CourtListener-authoritative"
            )
        raw_search_type = config.get("search_type")
        if raw_search_type is None:
            source_search_type = None
        elif (
            isinstance(raw_search_type, str)
            and raw_search_type
            and raw_search_type == raw_search_type.strip()
        ):
            source_search_type = raw_search_type
        else:
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid search_type"
            )
        raw_schema_version = config.get("schema_version")
        source_schema_version = (
            raw_schema_version
            if isinstance(raw_schema_version, str)
            and raw_schema_version
            and raw_schema_version == raw_schema_version.strip()
            else None
        )
        source_available_only_present = "available_only" in config
        raw_available_only = config.get("available_only")
        source_available_only = (
            raw_available_only
            if isinstance(raw_available_only, str)
            and raw_available_only
            and raw_available_only == raw_available_only.strip()
            else None
        )
        source_query_expression_present = "query_expression" in config
        raw_query_expression = config.get("query_expression")
        if not source_query_expression_present:
            source_query_expression = None
        elif (
            isinstance(raw_query_expression, str)
            and raw_query_expression
            and raw_query_expression == raw_query_expression.strip()
        ):
            source_query_expression = raw_query_expression
        else:
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid query_expression"
            )
        query_terms = config.get("query_terms")
        if not isinstance(query_terms, list) or not query_terms:
            raise RecapApiBatchDriverError(
                "direct-search source batch lacks frozen query terms"
            )
        raw_terms = cast(list[object], query_terms)
        if not all(
            isinstance(term, str) and bool(term) and term == term.strip()
            for term in raw_terms
        ):
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid frozen query terms"
            )
        terms = tuple(cast(list[str], raw_terms))
        if len(set(terms)) != len(terms):
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid frozen query terms"
            )
        progress_rows = connection.execute(
            "SELECT term, terminal_status FROM term_progress WHERE batch_id = ?",
            (source_batch_id,),
        ).fetchall()
        progress = {str(row["term"]): row["terminal_status"] for row in progress_rows}
        if set(progress) != set(terms) or any(
            progress.get(term) != TermTerminalStatus.EXHAUSTED for term in terms
        ):
            raise RecapApiBatchDriverError(
                "direct-search source batch is not fully exhausted"
            )
        try:
            raw_window_start = (
                config["search_window_start"]
                if "search_window_start" in config
                else config["decision_window_start"]
            )
            raw_window_end = (
                config["search_window_end"]
                if "search_window_end" in config
                else config["decision_window_end"]
            )
            window_start = date.fromisoformat(str(raw_window_start))
            window_end = date.fromisoformat(str(raw_window_end))
        except (KeyError, ValueError) as exc:
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid search window"
            ) from exc
        if window_end < window_start:
            raise RecapApiBatchDriverError(
                "direct-search source batch search window is inverted"
            )
        cycle = connection.execute(
            "SELECT schema_version, policy_json, policy_hash "
            "FROM cycle_identity WHERE singleton = 1"
        ).fetchone()
        if cycle is None:
            raise RecapApiBatchDriverError(
                "direct-search source store lacks frozen cycle identity"
            )
        rows = connection.execute(
            """
            SELECT candidate_id, term, provider_hit_id, payload_json
            FROM discovery_hits
            WHERE batch_id = ?
            ORDER BY candidate_id, term, provider_hit_id
            """,
            (source_batch_id,),
        ).fetchall()
        policy_json = str(cycle["policy_json"])
        source_cycle_hash = str(cycle["policy_hash"])
        decoded_policy = cast(object, json.loads(policy_json))
        if not isinstance(decoded_policy, dict):
            raise RecapApiBatchDriverError(
                "direct-search source cycle policy is not an object"
            )
        canonical_cycle_identity = json.dumps(
            {
                "schema_version": str(cycle["schema_version"]),
                "policy": decoded_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if (
            hashlib.sha256(canonical_cycle_identity.encode()).hexdigest()
            != source_cycle_hash
        ):
            raise RecapApiBatchDriverError(
                "direct-search source cycle policy digest is invalid"
            )
        raw_eligibility_anchor = cast(dict[str, object], decoded_policy).get(
            "eligibility_anchor"
        )
        source_eligibility_anchor = (
            raw_eligibility_anchor if isinstance(raw_eligibility_anchor, str) else None
        )
    except (json.JSONDecodeError, sqlite3.DatabaseError) as exc:
        raise RecapApiBatchDriverError(
            f"direct-search source store is unreadable: {path}: {exc}"
        ) from exc
    finally:
        connection.close()

    grouped: dict[
        str,
        list[
            tuple[
                str,
                str,
                str,
                dict[str, object],
                tuple[int, int, str, dict[str, object]] | None,
                tuple[dict[str, object], ...],
            ]
        ],
    ] = {}
    try:
        for row in rows:
            stored_candidate_id = str(row["candidate_id"])
            stored_numeric = stored_candidate_id.removeprefix("courtlistener-docket-")
            if _POSITIVE_ASCII_INTEGER.fullmatch(stored_numeric) is None:
                raise RecapApiBatchDriverError(
                    "direct-search candidate id is not numeric or not a canonical "
                    f"positive integer: {stored_candidate_id!r}"
                )
            payload_json = str(row["payload_json"])
            parsed = cast(object, json.loads(payload_json))
            if not isinstance(parsed, dict):
                raise RecapApiBatchDriverError(
                    f"direct-search payload is not an object: {stored_candidate_id}"
                )
            payload = cast(dict[str, object], parsed)
            raw_payload_docket_id = payload.get("docket_id")
            if isinstance(raw_payload_docket_id, bool) or not isinstance(
                raw_payload_docket_id, str | int
            ):
                raise RecapApiBatchDriverError(
                    f"direct-search payload docket id is invalid: {stored_candidate_id}"
                )
            docket_id = str(raw_payload_docket_id)
            if _POSITIVE_ASCII_INTEGER.fullmatch(
                docket_id
            ) is None or stored_candidate_id not in {
                docket_id,
                f"courtlistener-docket-{docket_id}",
            }:
                raise RecapApiBatchDriverError(
                    f"direct-search payload docket id mismatch: {stored_candidate_id}"
                )
            evidence = _minimum_direct_search_entry_evidence(payload, docket_id)
            priority_options = _direct_search_priority_evidence_options(
                payload, docket_id
            )
            grouped.setdefault(docket_id, []).append(
                (
                    str(row["term"]),
                    str(row["provider_hit_id"]),
                    payload_json,
                    payload,
                    evidence,
                    priority_options,
                )
            )
    except json.JSONDecodeError as exc:
        raise RecapApiBatchDriverError(
            f"direct-search source contains invalid payload JSON: {exc}"
        ) from exc

    leads_list: list[DirectSearchLead] = []
    for docket_id, docket_rows in grouped.items():
        docket_rows.sort(key=lambda item: (item[2], item[0], item[1]))
        primary = docket_rows[0][3]
        evidence_rows = [item for item in docket_rows if item[4] is not None]
        representative = (
            min(evidence_rows, key=lambda item: cast(tuple[object, ...], item[4])[:3])
            if evidence_rows
            else docket_rows[0]
        )
        minimum_evidence = (
            representative[4][3] if representative[4] is not None else None
        )
        priority_options = tuple(evidence for row in docket_rows for evidence in row[5])
        priority_evidence = (
            min(
                priority_options,
                key=lambda evidence: _priority_evidence_sort_key(
                    evidence,
                    window_start=window_start,
                    window_end=window_end,
                    eligibility_anchor=source_eligibility_anchor,
                ),
            )
            if priority_options
            else None
        )
        raw_transfer = primary.get("direct_search_provenance")
        if isinstance(raw_transfer, Mapping):
            transfer = cast(Mapping[str, object], raw_transfer)
            raw_source_hits = transfer.get("source_hits")
            if not isinstance(raw_source_hits, list):
                raise RecapApiBatchDriverError(
                    f"direct-search transfer source hits are invalid: {docket_id}"
                )
            transferred_hits: list[DirectSearchHitProvenance] = []
            for raw_hit in cast(list[object], raw_source_hits):
                if not isinstance(raw_hit, Mapping):
                    raise RecapApiBatchDriverError(
                        f"direct-search transfer source hit is invalid: {docket_id}"
                    )
                hit = cast(Mapping[str, object], raw_hit)
                provider_hit_id = hit.get("provider_hit_id")
                query_term = hit.get("query_term")
                payload_sha256 = hit.get("payload_sha256")
                if (
                    not isinstance(provider_hit_id, str)
                    or not provider_hit_id
                    or not isinstance(query_term, str)
                    or not query_term
                    or not isinstance(payload_sha256, str)
                    or re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is None
                ):
                    raise RecapApiBatchDriverError(
                        f"direct-search transfer source hit is invalid: {docket_id}"
                    )
                transferred_hits.append(
                    DirectSearchHitProvenance(
                        provider_hit_id=provider_hit_id,
                        query_term=query_term,
                        payload_sha256=payload_sha256,
                    )
                )
            source_hits = tuple(
                sorted(
                    transferred_hits,
                    key=lambda hit: (
                        hit.query_term,
                        hit.provider_hit_id,
                        hit.payload_sha256,
                    ),
                )
            )
            source_provider_hit_id = transfer.get("source_provider_hit_id")
            source_query_term = transfer.get("source_query_term")
            source_payload_sha256 = transfer.get("source_payload_sha256")
            representative_hit = DirectSearchHitProvenance(
                provider_hit_id=(
                    source_provider_hit_id
                    if isinstance(source_provider_hit_id, str)
                    else ""
                ),
                query_term=source_query_term
                if isinstance(source_query_term, str)
                else "",
                payload_sha256=(
                    source_payload_sha256
                    if isinstance(source_payload_sha256, str)
                    else ""
                ),
            )
            if representative_hit not in source_hits:
                raise RecapApiBatchDriverError(
                    f"direct-search transfer representative hit is invalid: {docket_id}"
                )
        else:
            representative_hit = DirectSearchHitProvenance(
                provider_hit_id=representative[1],
                query_term=representative[0],
                payload_sha256=hashlib.sha256(representative[2].encode()).hexdigest(),
            )
            source_hits = tuple(
                sorted(
                    (
                        DirectSearchHitProvenance(
                            provider_hit_id=provider_hit_id,
                            query_term=term,
                            payload_sha256=hashlib.sha256(
                                payload_json.encode()
                            ).hexdigest(),
                        )
                        for (
                            term,
                            provider_hit_id,
                            payload_json,
                            _payload,
                            _evidence,
                            _priority_options,
                        ) in docket_rows
                    ),
                    key=lambda hit: (
                        hit.query_term,
                        hit.provider_hit_id,
                        hit.payload_sha256,
                    ),
                )
            )
        leads_list.append(
            DirectSearchLead(
                docket_id=docket_id,
                source_provider_hit_id=representative_hit.provider_hit_id,
                source_query_term=representative_hit.query_term,
                source_payload_sha256=representative_hit.payload_sha256,
                source_hits=source_hits,
                court_id=_optional_str(primary.get("court_id")),
                docket_number=_optional_str(primary.get("docket_number"))
                or _optional_str(primary.get("docketNumber")),
                case_name=_optional_str(primary.get("case_name"))
                or _optional_str(primary.get("caseName")),
                decision_entry_evidence=minimum_evidence,
                priority_decision_evidence=priority_evidence,
                opinion_resolution_evidence=(
                    cast(Mapping[str, object], primary["opinion_resolution_evidence"])
                    if isinstance(primary.get("opinion_resolution_evidence"), Mapping)
                    else None
                ),
            )
        )
    leads = tuple(sorted(leads_list, key=lambda lead: int(lead.docket_id)))
    hit_set_sha256 = hashlib.sha256(
        json.dumps(
            [
                {
                    "docket_id": lead.docket_id,
                    "source_hit": hit.to_record(),
                }
                for lead in leads
                for hit in lead.source_hits
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    candidate_set_sha256 = hashlib.sha256(
        json.dumps(
            [lead.commitment_record() for lead in leads],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    frozen_selected_sha256 = config.get("selected_candidate_set_sha256")
    if (
        frozen_selected_sha256 is not None
        and frozen_selected_sha256 != candidate_set_sha256
    ):
        raise RecapApiBatchDriverError(
            "direct-search transferred candidate set changed after its frozen dedupe"
        )
    return DirectSearchSeedSource(
        source_batch_id=source_batch_id,
        source_batch_digest=source_batch_digest,
        source_cycle_hash=source_cycle_hash,
        source_schema_version=source_schema_version,
        source_search_type=source_search_type,
        source_available_only_present=source_available_only_present,
        source_available_only=source_available_only,
        source_query_expression_present=source_query_expression_present,
        source_query_expression=source_query_expression,
        source_query_terms=terms,
        source_candidate_set_sha256=candidate_set_sha256,
        source_hit_set_sha256=hit_set_sha256,
        source_eligibility_anchor=source_eligibility_anchor,
        search_window_start=window_start,
        search_window_end=window_end,
        leads=leads,
        source_lineage_commitments={
            **source_lineage_commitments,
            "source_lineage_commitment_sha256": (source_lineage_commitment_sha256),
        },
    )


def read_verified_priority_dedupe_snapshots(
    snapshot_paths: Sequence[str | Path],
    *,
    expected_manifest_sha256: Sequence[str],
) -> tuple[PriorScreeningSnapshot, ...]:
    """Verify terminal snapshots and return deterministic priority-dedupe inputs.

    Snapshot outcomes are deliberately not imported. Only the exact candidate-ID
    union is used to defer already-screened dockets from a priority batch. This
    remains valid when a snapshot belongs to an older cycle, without laundering
    that cycle's eligibility or exclusion decisions into the current cycle.
    """

    if not snapshot_paths:
        raise RecapApiBatchDriverError(
            "novel transfer requires at least one prior screening snapshot"
        )
    if len(snapshot_paths) != len(expected_manifest_sha256):
        raise RecapApiBatchDriverError(
            "each prior snapshot requires one ordered expected manifest SHA-256"
        )
    snapshots: list[PriorScreeningSnapshot] = []
    seen_paths: set[Path] = set()
    seen_manifest_hashes: set[str] = set()
    for index, (raw_path, expected_hash) in enumerate(
        zip(snapshot_paths, expected_manifest_sha256, strict=True), start=1
    ):
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise RecapApiBatchDriverError(
                f"prior snapshot {index} expected manifest SHA-256 is invalid"
            )
        supplied_path = Path(raw_path)
        if supplied_path.is_symlink() or not supplied_path.is_dir():
            raise RecapApiBatchDriverError(
                f"prior snapshot {index} is not a regular directory: {supplied_path}"
            )
        try:
            path = supplied_path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RecapApiBatchDriverError(
                f"prior snapshot {index} cannot be resolved: {supplied_path}"
            ) from exc
        if path in seen_paths:
            raise RecapApiBatchDriverError("prior snapshot paths must be distinct")
        seen_paths.add(path)
        for filename in _SNAPSHOT_METADATA_FILES:
            metadata_path = path / filename
            if metadata_path.is_symlink() or not metadata_path.is_file():
                raise RecapApiBatchDriverError(
                    f"prior snapshot metadata is not a regular file: {metadata_path}"
                )
        try:
            manifest_bytes = (path / "manifest.json").read_bytes()
        except OSError as exc:
            raise RecapApiBatchDriverError(
                f"prior snapshot manifest is unreadable: {path}"
            ) from exc
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_hash != expected_hash:
            raise RecapApiBatchDriverError(
                f"prior snapshot manifest SHA-256 mismatch: {path}"
            )
        if manifest_hash in seen_manifest_hashes:
            raise RecapApiBatchDriverError(
                "prior snapshots must have distinct manifest commitments"
            )
        seen_manifest_hashes.add(manifest_hash)
        try:
            parsed_expected_manifest = cast(object, json.loads(manifest_bytes))
            if not isinstance(parsed_expected_manifest, dict):
                raise RecapApiBatchDriverError(
                    f"prior snapshot manifest is not an object: {path}"
                )
            expected_manifest = cast(dict[str, object], parsed_expected_manifest)
            verified_manifest = verify_snapshot(
                path,
                require_complete=True,
                require_saturated=True,
            )
            if verified_manifest != expected_manifest:
                raise RecapApiBatchDriverError(
                    f"prior snapshot manifest changed during verification: {path}"
                )
            candidate_payload = _read_committed_snapshot_file(
                path / "candidates.jsonl",
                manifest=expected_manifest,
                filename="candidates.jsonl",
            )
            candidate_ids = _priority_dedupe_candidate_ids(candidate_payload)
        except json.JSONDecodeError as exc:
            raise RecapApiBatchDriverError(
                f"prior snapshot manifest is invalid JSON: {path}"
            ) from exc
        except SnapshotVerificationError as exc:
            raise RecapApiBatchDriverError(
                f"prior snapshot verification failed: {path}: {exc}"
            ) from exc
        cycle_hash = _snapshot_sha256_field(expected_manifest, "cycle_hash", path)
        batch_digest = _snapshot_sha256_field(expected_manifest, "batch_digest", path)
        snapshot_id = _snapshot_text_field(expected_manifest, "snapshot_id", path)
        batch_id = _snapshot_text_field(expected_manifest, "batch_id", path)
        snapshots.append(
            PriorScreeningSnapshot(
                path=path,
                manifest_sha256=manifest_hash,
                cycle_hash=cycle_hash,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
                batch_digest=batch_digest,
                candidate_ids=candidate_ids,
                candidate_set_sha256=_candidate_id_set_sha256(candidate_ids),
            )
        )
    return tuple(
        sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.manifest_sha256,
                str(snapshot.path),
            ),
        )
    )


def _read_committed_snapshot_file(
    path: Path,
    *,
    manifest: Mapping[str, object],
    filename: str,
) -> bytes:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise RecapApiBatchDriverError("prior snapshot file manifest is invalid")
    raw_commitment = cast(Mapping[str, object], files).get(filename)
    if not isinstance(raw_commitment, Mapping):
        raise RecapApiBatchDriverError(
            f"prior snapshot lacks a commitment for {filename}"
        )
    commitment = cast(Mapping[str, object], raw_commitment)
    expected_sha256 = commitment.get("sha256")
    expected_byte_count = commitment.get("byte_count")
    expected_row_count = commitment.get("row_count")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise RecapApiBatchDriverError(
            f"prior snapshot candidates are unreadable: {path}"
        ) from exc
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or not isinstance(expected_byte_count, int)
        or isinstance(expected_byte_count, bool)
        or not isinstance(expected_row_count, int)
        or isinstance(expected_row_count, bool)
        or hashlib.sha256(payload).hexdigest() != expected_sha256
        or len(payload) != expected_byte_count
        or payload.count(b"\n") != expected_row_count
    ):
        raise RecapApiBatchDriverError(
            f"prior snapshot file changed after verification: {path}"
        )
    return payload


def _priority_dedupe_candidate_ids(payload: bytes) -> tuple[str, ...]:
    candidate_ids: set[str] = set()
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise RecapApiBatchDriverError(
            "prior snapshot candidates are not valid UTF-8"
        ) from exc
    for row_number, line in enumerate(lines, start=1):
        try:
            parsed = cast(object, json.loads(line))
        except json.JSONDecodeError as exc:
            raise RecapApiBatchDriverError(
                f"prior snapshot candidate row {row_number} is invalid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise RecapApiBatchDriverError(
                f"prior snapshot candidate row {row_number} is not an object"
            )
        candidate_id = cast(dict[str, object], parsed).get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise RecapApiBatchDriverError(
                f"prior snapshot candidate row {row_number} has invalid identity"
            )
        if candidate_id in candidate_ids:
            raise RecapApiBatchDriverError(
                f"prior snapshot contains duplicate candidate: {candidate_id}"
            )
        candidate_ids.add(candidate_id)
    return tuple(sorted(candidate_ids))


def _snapshot_sha256_field(
    manifest: Mapping[str, object], field: str, path: Path
) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RecapApiBatchDriverError(f"prior snapshot has invalid {field}: {path}")
    return value


def _snapshot_text_field(manifest: Mapping[str, object], field: str, path: Path) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RecapApiBatchDriverError(f"prior snapshot has invalid {field}: {path}")
    return value


def _candidate_id_set_sha256(candidate_ids: Sequence[str]) -> str:
    return hashlib.sha256(
        json.dumps(
            list(candidate_ids),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _lead_set_sha256(leads: Sequence[DirectSearchLead]) -> str:
    return hashlib.sha256(
        json.dumps(
            [lead.commitment_record() for lead in leads],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _minimum_direct_search_entry_evidence(
    payload: Mapping[str, object], docket_id: str
) -> tuple[int, int, str, dict[str, object]] | None:
    raw_documents = payload.get("recap_documents")
    if raw_documents is None:
        transferred = payload.get("decision_entry_evidence")
        if transferred is None:
            return None
        if not isinstance(transferred, Mapping):
            raise RecapApiBatchDriverError(
                f"direct-search decision entry evidence is not an object: {docket_id}"
            )
        evidence = dict(cast(Mapping[str, object], transferred))
        entry_number = _positive_integer_prefix(evidence.get("entry_number"))
        if entry_number is None or entry_number <= 0:
            return None
        evidence["entry_number"] = entry_number
        canonical = json.dumps(
            evidence, sort_keys=True, separators=(",", ":"), default=str
        )
        return (entry_number, 0, canonical, evidence)
    if not isinstance(raw_documents, list):
        raise RecapApiBatchDriverError(
            f"direct-search recap_documents is not a list: {docket_id}"
        )
    options: list[tuple[int, int, str, dict[str, object]]] = []
    for raw_document in cast(list[object], raw_documents):
        if not isinstance(raw_document, Mapping):
            raise RecapApiBatchDriverError(
                f"direct-search recap document is not an object: {docket_id}"
            )
        document = cast(Mapping[str, object], raw_document)
        entry_number = _positive_integer_prefix(document.get("entry_number"))
        if entry_number is None or entry_number <= 0:
            continue
        evidence: dict[str, object] = {
            "id": document.get("id"),
            "docket_entry_id": document.get("docket_entry_id"),
            "entry_number": entry_number,
            "document_number": document.get("document_number"),
            "description": document.get("description")
            or document.get("short_description"),
            "entry_date_filed": document.get("entry_date_filed"),
            "absolute_url": document.get("absolute_url"),
        }
        attachment_rank = 0 if document.get("attachment_number") is None else 1
        canonical_document = json.dumps(
            dict(document), sort_keys=True, separators=(",", ":"), default=str
        )
        options.append((entry_number, attachment_rank, canonical_document, evidence))
    return min(options, key=lambda item: item[:3]) if options else None


def _direct_search_priority_evidence_options(
    payload: Mapping[str, object], docket_id: str
) -> tuple[dict[str, object], ...]:
    transferred = payload.get("priority_decision_evidence")
    if transferred is not None:
        if not isinstance(transferred, Mapping):
            raise RecapApiBatchDriverError(
                f"direct-search priority evidence is not an object: {docket_id}"
            )
        evidence = dict(cast(Mapping[str, object], transferred))
        entry_number = _positive_integer_prefix(evidence.get("entry_number"))
        if entry_number is None or entry_number <= 0:
            raise RecapApiBatchDriverError(
                f"direct-search priority evidence has invalid entry: {docket_id}"
            )
        evidence["entry_number"] = entry_number
        raw_available = evidence.get("is_available")
        if raw_available is not None and not isinstance(raw_available, bool):
            raise RecapApiBatchDriverError(
                f"direct-search priority evidence availability is invalid: {docket_id}"
            )
        return (evidence,)
    raw_documents = payload.get("recap_documents")
    if raw_documents is None:
        return ()
    if not isinstance(raw_documents, list):
        raise RecapApiBatchDriverError(
            f"direct-search recap_documents is not a list: {docket_id}"
        )
    options: list[dict[str, object]] = []
    for raw_document in cast(list[object], raw_documents):
        if not isinstance(raw_document, Mapping):
            raise RecapApiBatchDriverError(
                f"direct-search recap document is not an object: {docket_id}"
            )
        document = cast(Mapping[str, object], raw_document)
        entry_number = _positive_integer_prefix(document.get("entry_number"))
        if entry_number is None or entry_number <= 0:
            continue
        raw_available = document.get("is_available")
        if raw_available is not None and not isinstance(raw_available, bool):
            raise RecapApiBatchDriverError(
                f"direct-search recap availability is invalid: {docket_id}"
            )
        options.append(
            {
                "id": document.get("id"),
                "docket_entry_id": document.get("docket_entry_id"),
                "entry_number": entry_number,
                "document_number": document.get("document_number"),
                "description": document.get("description")
                or document.get("short_description"),
                "entry_date_filed": document.get("entry_date_filed"),
                "absolute_url": document.get("absolute_url"),
                "is_available": raw_available,
            }
        )
    return tuple(options)


def seed_direct_search_leads(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    source: DirectSearchSeedSource,
    page_size: int = 100,
) -> DirectSearchSeedResult:
    """Attach and resumably seed a REST-only screening batch from direct search."""

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be from 1 through 100")
    if store.cycle_hash != source.source_cycle_hash:
        raise RecapApiBatchDriverError(
            "direct-search source and REST target cycle identities differ"
        )
    if batch_id == source.source_batch_id:
        raise RecapApiBatchDriverError(
            "direct-search source and target batch ids must differ"
        )
    result = _seed_direct_search_leads(
        store,
        batch_id=batch_id,
        source=source,
        page_size=page_size,
        transfer_term=DIRECT_SEARCH_TRANSFER_TERM,
        provenance_schema=DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA,
        cross_cycle_rebind=False,
    )
    return DirectSearchSeedResult(
        batch_id=result.batch_id,
        source_batch_id=result.source_batch_id,
        source_batch_digest=result.source_batch_digest,
        source_candidate_set_sha256=result.source_candidate_set_sha256,
        leads_selected=result.leads_selected,
        leads_seeded=result.leads_seeded,
        already_seeded=result.already_seeded,
    )


def rebind_direct_search_leads(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    source: DirectSearchSeedSource,
    page_size: int = 100,
) -> DirectSearchRebindResult:
    """Rebind one complete source union into a distinct current screening cycle.

    The source is already verified and read through a SQLite read-only
    connection by :func:`read_saturated_direct_search_leads`. This phase merely
    commits that exact lead set and its old/new cycle lineage into the target
    store; it has no provider client and cannot perform paid activity.
    """

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be from 1 through 100")
    if store.cycle_hash == source.source_cycle_hash:
        raise RecapApiBatchDriverError(
            "direct-search source already matches target cycle; use "
            "seed-direct-search instead"
        )
    if batch_id == source.source_batch_id:
        raise RecapApiBatchDriverError(
            "direct-search source and target batch ids must differ"
        )
    result = _seed_direct_search_leads(
        store,
        batch_id=batch_id,
        source=source,
        page_size=page_size,
        transfer_term=DIRECT_SEARCH_CYCLE_REBIND_TERM,
        provenance_schema=DIRECT_SEARCH_CYCLE_REBIND_PROVENANCE_SCHEMA,
        cross_cycle_rebind=True,
    )
    return DirectSearchRebindResult(
        batch_id=result.batch_id,
        source_batch_id=result.source_batch_id,
        source_batch_digest=result.source_batch_digest,
        source_cycle_hash=source.source_cycle_hash,
        target_cycle_hash=store.cycle_hash,
        source_candidate_set_sha256=result.source_candidate_set_sha256,
        leads_selected=result.leads_selected,
        leads_seeded=result.leads_seeded,
        already_seeded=result.already_seeded,
    )


def _seed_direct_search_leads(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    source: DirectSearchSeedSource,
    page_size: int,
    transfer_term: str,
    provenance_schema: str,
    cross_cycle_rebind: bool,
) -> DirectSearchSeedResult:
    """Materialize one already-validated direct-search source lead set."""

    target_cycle_hash = store.cycle_hash
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(transfer_term,),
        page_size=page_size,
        top_k_per_term=max(len(source.leads), 1),
    )
    config.update(
        {
            "discovery_mode": provenance_schema,
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_search_type": source.source_search_type,
            "source_candidate_count": len(source.leads),
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
        }
    )
    if cross_cycle_rebind:
        config.update(
            {
                "source_cycle_hash": source.source_cycle_hash,
                "target_cycle_hash": target_cycle_hash,
                "cross_cycle_rebind": True,
                "provider_activity_requested": False,
                "provider_activity_executed": False,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            }
        )
    store.ensure_batch(batch_id, config)
    store.ensure_terms(batch_id, (transfer_term,))
    progress = store.term_progress(batch_id, transfer_term)
    if progress.terminal_status is not None:
        return DirectSearchSeedResult(
            batch_id=batch_id,
            source_batch_id=source.source_batch_id,
            source_batch_digest=source.source_batch_digest,
            source_candidate_set_sha256=source.source_candidate_set_sha256,
            leads_selected=len(source.leads),
            leads_seeded=0,
            already_seeded=True,
        )
    offset = progress.hit_count
    starting_offset = offset
    if offset > len(source.leads):
        raise RecapApiBatchDriverError(
            "direct-search transfer progress exceeds frozen lead count"
        )
    while offset < len(source.leads):
        page = source.leads[offset : offset + page_size]
        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(source.leads) else None
        terminal = None if next_cursor is not None else TermTerminalStatus.EXHAUSTED
        progress = store.commit_search_page(
            batch_id,
            transfer_term,
            progress.cursor,
            tuple(
                _direct_search_lead_to_hit(
                    lead,
                    source,
                    transfer_term=transfer_term,
                    provenance_schema=provenance_schema,
                    target_cycle_hash=(
                        target_cycle_hash if cross_cycle_rebind else None
                    ),
                )
                for lead in page
            ),
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
        offset = next_offset
    if not source.leads:
        store.commit_search_page(
            batch_id,
            transfer_term,
            progress.cursor,
            (),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    return DirectSearchSeedResult(
        batch_id=batch_id,
        source_batch_id=source.source_batch_id,
        source_batch_digest=source.source_batch_digest,
        source_candidate_set_sha256=source.source_candidate_set_sha256,
        leads_selected=len(source.leads),
        leads_seeded=len(source.leads) - starting_offset,
        already_seeded=False,
    )


def seed_novel_direct_search_leads(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    source: DirectSearchSeedSource,
    prior_snapshots: Sequence[PriorScreeningSnapshot],
    page_size: int = 100,
) -> NovelDirectSearchSeedResult:
    """Seed only source leads unseen in verified prior terminal snapshots.

    This is a scheduling optimization, not an import of historical outcomes.
    Candidates found in a prior snapshot are excluded only from this priority
    target batch. They remain available from the committed complete source and
    are never written to the current cycle's exclusion ledger by this transfer.
    """

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be from 1 through 100")
    if not prior_snapshots:
        raise RecapApiBatchDriverError(
            "novel transfer requires at least one verified prior snapshot"
        )
    if store.cycle_hash != source.source_cycle_hash:
        raise RecapApiBatchDriverError(
            "direct-search source and REST target cycle identities differ"
        )
    if batch_id == source.source_batch_id:
        raise RecapApiBatchDriverError(
            "direct-search source and target batch ids must differ"
        )
    manifest_hashes = [snapshot.manifest_sha256 for snapshot in prior_snapshots]
    if len(set(manifest_hashes)) != len(manifest_hashes):
        raise RecapApiBatchDriverError(
            "novel transfer prior snapshot commitments must be distinct"
        )
    ordered_snapshots = tuple(
        sorted(
            prior_snapshots,
            key=lambda snapshot: (
                snapshot.manifest_sha256,
                str(snapshot.path),
            ),
        )
    )
    prior_records = [
        snapshot.commitment_record(source_cycle_hash=source.source_cycle_hash)
        for snapshot in ordered_snapshots
    ]
    prior_snapshot_commitment_sha256 = hashlib.sha256(
        json.dumps(prior_records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    prior_candidate_ids = {
        candidate_id
        for snapshot in ordered_snapshots
        for candidate_id in snapshot.candidate_ids
    }
    selected = tuple(
        lead for lead in source.leads if lead.candidate_id not in prior_candidate_ids
    )
    excluded = tuple(
        lead for lead in source.leads if lead.candidate_id in prior_candidate_ids
    )
    if len(selected) + len(excluded) != len(source.leads):
        raise RecapApiBatchDriverError(
            "novel transfer source partition does not reconcile"
        )
    selected_candidate_set_sha256 = _lead_set_sha256(selected)
    excluded_candidate_set_sha256 = _lead_set_sha256(excluded)
    cross_cycle_snapshot_count = sum(
        snapshot.cycle_hash != source.source_cycle_hash
        for snapshot in ordered_snapshots
    )
    preexisting_observations: list[str] = []
    for lead in selected:
        observation = store.current_observation(lead.candidate_id)
        if observation is not None and observation.batch_id != batch_id:
            preexisting_observations.append(lead.candidate_id)
    if preexisting_observations:
        raise RecapApiBatchDriverError(
            "novel transfer selected candidates already have canonical "
            "observations and cannot be safely seeded: "
            + ", ".join(preexisting_observations)
        )
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(DIRECT_SEARCH_NOVEL_TRANSFER_TERM,),
        page_size=page_size,
        top_k_per_term=max(len(selected), 1),
    )
    config.update(
        {
            "discovery_mode": DIRECT_SEARCH_NOVEL_TRANSFER_PROVENANCE_SCHEMA,
            "prior_snapshot_dedupe_schema": PRIOR_SNAPSHOT_PRIORITY_DEDUPE_SCHEMA,
            "selection_semantics": "priority_dedupe_only",
            "prior_outcomes_authoritative": False,
            "seen_candidate_disposition": (
                "deferred_from_priority_batch_not_merits_excluded"
            ),
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_cycle_hash": source.source_cycle_hash,
            "source_search_type": source.source_search_type,
            "source_candidate_count": len(source.leads),
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "prior_snapshot_count": len(ordered_snapshots),
            "cross_cycle_snapshot_count": cross_cycle_snapshot_count,
            "prior_snapshot_commitment_sha256": (prior_snapshot_commitment_sha256),
            "prior_snapshots": prior_records,
            "selected_candidate_count": len(selected),
            "selected_candidate_set_sha256": selected_candidate_set_sha256,
            "excluded_from_target_candidate_count": len(excluded),
            "excluded_from_target_candidate_set_sha256": (
                excluded_candidate_set_sha256
            ),
        }
    )
    store.ensure_batch(batch_id, config)
    store.ensure_terms(batch_id, (DIRECT_SEARCH_NOVEL_TRANSFER_TERM,))
    progress = store.term_progress(batch_id, DIRECT_SEARCH_NOVEL_TRANSFER_TERM)

    def result(*, seeded: int, already_seeded: bool) -> NovelDirectSearchSeedResult:
        return NovelDirectSearchSeedResult(
            batch_id=batch_id,
            source_batch_id=source.source_batch_id,
            source_batch_digest=source.source_batch_digest,
            source_cycle_hash=source.source_cycle_hash,
            source_candidate_set_sha256=source.source_candidate_set_sha256,
            prior_snapshot_commitment_sha256=prior_snapshot_commitment_sha256,
            prior_snapshot_count=len(ordered_snapshots),
            cross_cycle_snapshot_count=cross_cycle_snapshot_count,
            leads_selected=len(selected),
            leads_excluded_from_target=len(excluded),
            selected_candidate_set_sha256=selected_candidate_set_sha256,
            excluded_candidate_set_sha256=excluded_candidate_set_sha256,
            leads_seeded=seeded,
            already_seeded=already_seeded,
        )

    if progress.terminal_status is not None:
        return result(seeded=0, already_seeded=True)
    offset = progress.hit_count
    starting_offset = offset
    if offset > len(selected):
        raise RecapApiBatchDriverError(
            "novel direct-search transfer progress exceeds frozen lead count"
        )
    selection_provenance = {
        "schema_version": DIRECT_SEARCH_NOVEL_TRANSFER_PROVENANCE_SCHEMA,
        "selection_semantics": "priority_dedupe_only",
        "prior_outcomes_authoritative": False,
        "prior_snapshot_commitment_sha256": prior_snapshot_commitment_sha256,
        "selected_candidate_set_sha256": selected_candidate_set_sha256,
        "excluded_from_target_candidate_set_sha256": excluded_candidate_set_sha256,
    }
    while offset < len(selected):
        page = selected[offset : offset + page_size]
        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(selected) else None
        terminal = None if next_cursor is not None else TermTerminalStatus.EXHAUSTED
        hits = tuple(
            _direct_search_lead_to_hit(
                lead,
                source,
                transfer_term=DIRECT_SEARCH_NOVEL_TRANSFER_TERM,
                selection_provenance=selection_provenance,
            )
            for lead in page
        )
        progress = store.commit_search_page(
            batch_id,
            DIRECT_SEARCH_NOVEL_TRANSFER_TERM,
            progress.cursor,
            hits,
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
        offset = next_offset
    if not selected:
        store.commit_search_page(
            batch_id,
            DIRECT_SEARCH_NOVEL_TRANSFER_TERM,
            progress.cursor,
            (),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    return result(
        seeded=len(selected) - starting_offset,
        already_seeded=False,
    )


def _canonical_record_sha256(record: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(record),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _priority_date_status(
    lead: DirectSearchLead, source: DirectSearchSeedSource
) -> tuple[int, int, str]:
    evidence = lead.priority_decision_evidence or lead.decision_entry_evidence
    return _priority_date_status_for_evidence(
        evidence,
        window_start=source.search_window_start,
        window_end=source.search_window_end,
        eligibility_anchor=source.source_eligibility_anchor,
    )


def _priority_date_status_for_evidence(
    evidence: Mapping[str, object] | None,
    *,
    window_start: date,
    window_end: date,
    eligibility_anchor: str | None,
) -> tuple[int, int, str]:
    raw_date = None if evidence is None else evidence.get("entry_date_filed")
    if not isinstance(raw_date, str):
        return 1, 0, "missing"
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return 1, 0, "invalid"
    anchor = window_start
    if eligibility_anchor is not None:
        try:
            anchor = max(anchor, date.fromisoformat(eligibility_anchor))
        except ValueError as exc:
            raise RecapApiBatchDriverError(
                "direct-search source has invalid eligibility anchor"
            ) from exc
    if not anchor <= parsed <= window_end:
        return 1, parsed.toordinal(), "outside_committed_window"
    return 0, parsed.toordinal(), "valid_post_anchor"


def _priority_signal(lead: DirectSearchLead) -> tuple[int, str]:
    return _priority_signal_for_evidence(
        lead.priority_decision_evidence or lead.decision_entry_evidence
    )


def _priority_signal_for_evidence(
    evidence: Mapping[str, object] | None,
) -> tuple[int, str]:
    if evidence is None:
        return 3, "no_decision_entry_evidence"
    raw_description = evidence.get("description")
    description = raw_description.lower() if isinstance(raw_description, str) else ""
    target_motion = re.search(_DIRECT_SEARCH_TARGET_MOTION_PATTERN, description)
    target_pending = re.search(
        rf"(?:"
        rf"(?:{_DIRECT_SEARCH_TARGET_MOTION_PATTERN})"
        r"[^.;:\n]{0,96}\b(?:remains?|is|are)\s+pending\b|"
        r"\bpending\s+"
        rf"(?:{_DIRECT_SEARCH_TARGET_MOTION_PATTERN})"
        r")",
        description,
    )
    if re.search(_DIRECT_SEARCH_NON_DECISION_DOCUMENT_PATTERN, description):
        return 2, "generic_motion_or_brief"
    disposition = _description_patterns_share_clause(
        description,
        _DIRECT_SEARCH_TARGET_MOTION_PATTERN,
        _DIRECT_SEARCH_DISPOSITION_PATTERN,
    )
    substantive_recommendation = _description_patterns_share_clause(
        description,
        _DIRECT_SEARCH_TARGET_MOTION_PATTERN,
        _DIRECT_SEARCH_SUBSTANTIVE_RECOMMENDATION_PATTERN,
    )
    # The target phrase itself contains ``judgment`` for Rule 12(c) motions.
    # Remove that phrase before treating ``judgment`` as a decision-document
    # signal, so a bare motion cannot outrank an actual order.
    adjudicative_context = re.sub(
        r"\b(?:motion\s+for\s+)?judgment\s+on\s+the\s+pleadings\b",
        "",
        description,
    )
    adjudicative_document = _description_patterns_share_clause(
        adjudicative_context,
        _DIRECT_SEARCH_TARGET_MOTION_PATTERN,
        _DIRECT_SEARCH_ADJUDICATIVE_DOCUMENT_PATTERN,
    )
    if (
        target_motion is not None
        and target_pending is None
        and (disposition or substantive_recommendation)
    ):
        return 0, "action_linked_disposition_or_substantive_recommendation"
    if target_motion is not None and target_pending is None and adjudicative_document:
        return 1, "anchored_adjudicative_event"
    return 2, "generic_motion_or_brief"


def _description_patterns_share_clause(
    description: str,
    left_pattern: str,
    right_pattern: str,
) -> bool:
    """Return whether two metadata signals occur in one short docket-text clause."""

    separator_free_gap = r"[^.;:\n]{0,128}"
    return (
        re.search(
            rf"(?:{left_pattern}){separator_free_gap}(?:{right_pattern})|"
            rf"(?:{right_pattern}){separator_free_gap}(?:{left_pattern})",
            description,
        )
        is not None
    )


def _priority_evidence_sort_key(
    evidence: Mapping[str, object],
    *,
    window_start: date,
    window_end: date,
    eligibility_anchor: str | None,
) -> tuple[int, int, int, int, int, str]:
    signal_rank, _reason = _priority_signal_for_evidence(evidence)
    date_rank, ordinal, _status = _priority_date_status_for_evidence(
        evidence,
        window_start=window_start,
        window_end=window_end,
        eligibility_anchor=eligibility_anchor,
    )
    free_rank = 0 if evidence.get("is_available") is True else 1
    entry_number = _positive_integer_prefix(evidence.get("entry_number"))
    return (
        signal_rank,
        date_rank,
        -ordinal,
        free_rank,
        entry_number if entry_number is not None else 2**31,
        json.dumps(dict(evidence), sort_keys=True, separators=(",", ":"), default=str),
    )


def _rank_direct_search_leads(
    source: DirectSearchSeedSource,
) -> tuple[tuple[DirectSearchLead, ...], tuple[dict[str, object], ...]]:
    ranked: list[
        tuple[
            tuple[int, int, int, int, int, int, int, str],
            DirectSearchLead,
            dict[str, object],
        ]
    ] = []
    for lead in source.leads:
        prescreen_reason = prescreen_recap_candidate(
            court_id=lead.court_id,
            docket_number=lead.docket_number,
            case_name=lead.case_name,
            defer_bankruptcy_to_authoritative_docket=(source.source_search_type == "o"),
        )
        structural_rank = 0 if prescreen_reason is None else 1
        signal_rank, signal_reason = _priority_signal(lead)
        date_rank, decision_ordinal, date_status = _priority_date_status(lead, source)
        evidence = lead.priority_decision_evidence or lead.decision_entry_evidence
        entry_number = (
            None
            if evidence is None
            else _positive_integer_prefix(evidence.get("entry_number"))
        )
        entry_sort = entry_number if entry_number is not None else 2**31
        docket_number = _positive_integer_prefix(lead.docket_id)
        docket_sort = docket_number if docket_number is not None else 2**63
        free_rank = (
            0 if evidence is not None and evidence.get("is_available") is True else 1
        )
        key = (
            structural_rank,
            signal_rank,
            date_rank,
            -decision_ordinal,
            free_rank,
            entry_sort,
            docket_sort,
            lead.candidate_id,
        )
        ranked.append(
            (
                key,
                lead,
                {
                    "candidate_id": lead.candidate_id,
                    "structural_rank": structural_rank,
                    "prescreen_exclusion_reason": prescreen_reason,
                    "signal_rank": signal_rank,
                    "signal_reason": signal_reason,
                    "date_status": date_status,
                    "entry_date_filed": (
                        None if evidence is None else evidence.get("entry_date_filed")
                    ),
                    "entry_number": entry_number,
                    "is_available": (
                        None if evidence is None else evidence.get("is_available")
                    ),
                    "description": (
                        None if evidence is None else evidence.get("description")
                    ),
                    "lead_commitment_sha256": _canonical_record_sha256(
                        lead.commitment_record()
                    ),
                },
            )
        )
    ranked.sort(key=lambda item: item[0])
    leads = tuple(item[1] for item in ranked)
    records = tuple(
        {"rank": rank, **item[2]} for rank, item in enumerate(ranked, start=1)
    )
    return leads, records


def _validate_priority_frontier(
    frontier: Mapping[str, object],
    *,
    source: DirectSearchSeedSource,
    ranked_ids: tuple[str, ...],
    source_lineage: Mapping[str, object],
    source_lineage_hash: str,
) -> tuple[tuple[str, ...], int, str]:
    supplied = dict(frontier)
    claimed_hash = supplied.pop("frontier_sha256", None)
    if (
        not isinstance(claimed_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", claimed_hash) is None
        or _canonical_record_sha256(supplied) != claimed_hash
    ):
        raise RecapApiBatchDriverError("deferred frontier self-hash is invalid")
    expected_fields: dict[str, object] = {
        "schema_version": DIRECT_SEARCH_DEFERRED_FRONTIER_SCHEMA,
        "source_batch_id": source.source_batch_id,
        "source_batch_digest": source.source_batch_digest,
        "source_cycle_hash": source.source_cycle_hash,
        "source_candidate_set_sha256": source.source_candidate_set_sha256,
        "source_candidate_id_set_sha256": _candidate_id_set_sha256(
            tuple(sorted(ranked_ids))
        ),
        "source_lineage_commitments": dict(source_lineage),
        "source_lineage_commitment_sha256": source_lineage_hash,
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "ranked_candidate_ids": list(ranked_ids),
    }
    for field, expected in expected_fields.items():
        if supplied.get(field) != expected:
            raise RecapApiBatchDriverError(
                f"deferred frontier {field} does not match current "
                "source/ranking policy"
            )
    raw_cumulative = supplied.get("cumulative_selected_candidate_ids")
    raw_deferred = supplied.get("deferred_candidate_ids")
    raw_ordinal = supplied.get("tranche_ordinal")
    if not isinstance(raw_cumulative, list) or not isinstance(raw_deferred, list):
        raise RecapApiBatchDriverError("deferred frontier structure is invalid")
    cumulative_values = cast(list[object], raw_cumulative)
    deferred_values = cast(list[object], raw_deferred)
    if (
        not all(isinstance(value, str) for value in cumulative_values)
        or not all(isinstance(value, str) for value in deferred_values)
        or isinstance(raw_ordinal, bool)
        or not isinstance(raw_ordinal, int)
        or raw_ordinal < 1
    ):
        raise RecapApiBatchDriverError("deferred frontier structure is invalid")
    cumulative = tuple(cast(list[str], cumulative_values))
    deferred = tuple(cast(list[str], deferred_values))
    if cumulative + deferred != ranked_ids or len(set(ranked_ids)) != len(ranked_ids):
        raise RecapApiBatchDriverError(
            "deferred frontier does not exactly partition the ranked source"
        )
    return deferred, raw_ordinal, claimed_hash


def materialize_direct_search_priority_tranche(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    source: DirectSearchSeedSource,
    tranche_size: int,
    predecessor_frontier: Mapping[str, object] | None = None,
    page_size: int = 100,
) -> DirectSearchPriorityTrancheResult:
    """Materialize a provider-free rank-only tranche and exact deferred frontier."""

    if tranche_size < 1:
        raise ValueError("tranche_size must be positive")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be from 1 through 100")
    if store.cycle_hash != source.source_cycle_hash:
        raise RecapApiBatchDriverError(
            "direct-search source and priority target cycle identities differ"
        )
    if batch_id == source.source_batch_id:
        raise RecapApiBatchDriverError(
            "direct-search source and priority target batch ids must differ"
        )
    source_lineage = dict(source.source_lineage_commitments or {})
    claimed_lineage_hash = source_lineage.pop("source_lineage_commitment_sha256", None)
    if claimed_lineage_hash is None:
        source_lineage = {
            "authoritative_source_batch_digest": source.source_batch_digest
        }
        claimed_lineage_hash = _canonical_record_sha256(source_lineage)
    if (
        not isinstance(claimed_lineage_hash, str)
        or _canonical_record_sha256(source_lineage) != claimed_lineage_hash
    ):
        raise RecapApiBatchDriverError(
            "direct-search source lineage commitment is invalid"
        )
    prior_snapshot_hash = source_lineage.get("prior_snapshot_commitment_sha256")
    prior_snapshot_count = source_lineage.get("prior_snapshot_count")
    if (
        source_lineage.get("discovery_mode")
        != DIRECT_SEARCH_NOVEL_TRANSFER_PROVENANCE_SCHEMA
        or source_lineage.get("selection_semantics") != "priority_dedupe_only"
        or not isinstance(prior_snapshot_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", prior_snapshot_hash) is None
        or isinstance(prior_snapshot_count, bool)
        or not isinstance(prior_snapshot_count, int)
        or prior_snapshot_count < 1
    ):
        raise RecapApiBatchDriverError(
            "priority tranche requires a complete manifest-pinned novel "
            "direct-search source"
        )
    ranked, ranking_records = _rank_direct_search_leads(source)
    ranked_ids = tuple(lead.candidate_id for lead in ranked)
    source_candidate_id_set_sha256 = _candidate_id_set_sha256(tuple(sorted(ranked_ids)))
    if len(set(ranked_ids)) != len(ranked_ids) or set(ranked_ids) != {
        lead.candidate_id for lead in source.leads
    }:
        raise RecapApiBatchDriverError(
            "priority ranking does not exactly preserve the complete source"
        )
    if predecessor_frontier is None:
        remaining_ids = ranked_ids
        predecessor_ordinal = 0
        predecessor_hash = None
    else:
        remaining_ids, predecessor_ordinal, predecessor_hash = (
            _validate_priority_frontier(
                predecessor_frontier,
                source=source,
                ranked_ids=ranked_ids,
                source_lineage=source_lineage,
                source_lineage_hash=claimed_lineage_hash,
            )
        )
    if not remaining_ids:
        raise RecapApiBatchDriverError("deferred frontier is already empty")
    tranche_ordinal = predecessor_ordinal + 1
    selected_ids = remaining_ids[:tranche_size]
    deferred_ids = remaining_ids[len(selected_ids) :]
    cumulative_count = len(ranked_ids) - len(deferred_ids)
    cumulative_ids = ranked_ids[:cumulative_count]
    leads_by_id = {lead.candidate_id: lead for lead in ranked}
    selected = tuple(leads_by_id[candidate_id] for candidate_id in selected_ids)
    deferred = tuple(leads_by_id[candidate_id] for candidate_id in deferred_ids)
    if cumulative_ids + deferred_ids != ranked_ids:
        raise RecapApiBatchDriverError(
            "priority tranche union does not reconcile with complete source"
        )
    frontier_without_hash: dict[str, object] = {
        "schema_version": DIRECT_SEARCH_DEFERRED_FRONTIER_SCHEMA,
        "selection_semantics": "rank_only_no_membership_exclusion",
        "deferred_disposition": "unscreened_not_excluded",
        "source_batch_id": source.source_batch_id,
        "source_batch_digest": source.source_batch_digest,
        "source_cycle_hash": source.source_cycle_hash,
        "source_candidate_count": len(source.leads),
        "source_candidate_set_sha256": source.source_candidate_set_sha256,
        "source_candidate_id_set_sha256": source_candidate_id_set_sha256,
        "source_lineage_commitments": source_lineage,
        "source_lineage_commitment_sha256": claimed_lineage_hash,
        "ranking_policy": dict(_DIRECT_SEARCH_PRIORITY_POLICY),
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "ranking_records": list(ranking_records),
        "ranked_candidate_ids": list(ranked_ids),
        "predecessor_frontier_sha256": predecessor_hash,
        "tranche_ordinal": tranche_ordinal,
        "requested_tranche_size": tranche_size,
        "selected_candidate_ids": list(selected_ids),
        "selected_candidate_set_sha256": _lead_set_sha256(selected),
        "cumulative_selected_candidate_ids": list(cumulative_ids),
        "deferred_candidate_ids": list(deferred_ids),
        "deferred_candidate_set_sha256": _lead_set_sha256(deferred),
        "chain_terminal": len(deferred) == 0,
        "ranking_frontier_exhausted": len(deferred) == 0,
        "global_source_saturated": False,
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
        "provider_activity_executed": False,
        "paid_activity_executed": False,
    }
    frontier_hash = _canonical_record_sha256(frontier_without_hash)
    frontier = {**frontier_without_hash, "frontier_sha256": frontier_hash}
    preexisting = [
        candidate_id
        for candidate_id in selected_ids
        if (observation := store.current_observation(candidate_id)) is not None
        and observation.batch_id != batch_id
    ]
    if preexisting:
        raise RecapApiBatchDriverError(
            "priority tranche selected candidates already have canonical "
            "observations: " + ", ".join(preexisting)
        )
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,),
        page_size=page_size,
        top_k_per_term=max(len(selected), 1),
    )
    config.update(
        {
            "discovery_mode": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
            "selection_semantics": "rank_only_no_membership_exclusion",
            "deferred_disposition": "unscreened_not_excluded",
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_cycle_hash": source.source_cycle_hash,
            "source_candidate_count": len(source.leads),
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "source_candidate_id_set_sha256": source_candidate_id_set_sha256,
            "source_lineage_commitment_sha256": claimed_lineage_hash,
            "source_lineage_commitments": source_lineage,
            "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
            "tranche_ordinal": tranche_ordinal,
            "requested_tranche_size": tranche_size,
            "predecessor_frontier_sha256": predecessor_hash,
            "selected_candidate_count": len(selected),
            "selected_candidate_set_sha256": _lead_set_sha256(selected),
            "cumulative_selected_count": cumulative_count,
            "deferred_candidate_count": len(deferred),
            "deferred_candidate_set_sha256": _lead_set_sha256(deferred),
            "deferred_frontier_sha256": frontier_hash,
            "chain_terminal": len(deferred) == 0,
            "ranking_frontier_exhausted": len(deferred) == 0,
            "global_source_saturated": False,
            "provisional_frontier": True,
            "final_cohort_eligible": False,
            "full_source_terminal": False,
            "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
            "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
            "provider_activity_requested": False,
            "paid_activity_requested": False,
        }
    )
    store.ensure_batch(batch_id, config)
    store.ensure_terms(batch_id, (DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,))
    progress = store.term_progress(batch_id, DIRECT_SEARCH_PRIORITY_TRANCHE_TERM)

    def result(*, seeded: int, already: bool) -> DirectSearchPriorityTrancheResult:
        return DirectSearchPriorityTrancheResult(
            batch_id=batch_id,
            source_batch_id=source.source_batch_id,
            source_batch_digest=source.source_batch_digest,
            source_candidate_set_sha256=source.source_candidate_set_sha256,
            ranking_policy_sha256=DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
            tranche_ordinal=tranche_ordinal,
            selected_candidate_ids=selected_ids,
            deferred_candidate_ids=deferred_ids,
            cumulative_selected_count=cumulative_count,
            frontier_sha256=frontier_hash,
            frontier=frontier,
            leads_seeded=seeded,
            already_seeded=already,
        )

    if progress.terminal_status is not None:
        return result(seeded=0, already=True)
    offset = progress.hit_count
    starting_offset = offset
    if offset > len(selected):
        raise RecapApiBatchDriverError(
            "priority tranche progress exceeds frozen selected count"
        )
    selection_provenance = {
        "schema_version": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "frontier_sha256": frontier_hash,
        "tranche_ordinal": tranche_ordinal,
        "selection_semantics": "rank_only_no_membership_exclusion",
        "deferred_disposition": "unscreened_not_excluded",
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
    }
    while offset < len(selected):
        page = selected[offset : offset + page_size]
        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(selected) else None
        terminal = None if next_cursor is not None else TermTerminalStatus.EXHAUSTED
        progress = store.commit_search_page(
            batch_id,
            DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,
            progress.cursor,
            tuple(
                _direct_search_lead_to_hit(
                    lead,
                    source,
                    transfer_term=DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,
                    provenance_schema=DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
                    selection_provenance=selection_provenance,
                )
                for lead in page
            ),
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
        offset = next_offset
    return result(seeded=len(selected) - starting_offset, already=False)


def _direct_search_lead_to_hit(
    lead: DirectSearchLead,
    source: DirectSearchSeedSource,
    *,
    transfer_term: str = DIRECT_SEARCH_TRANSFER_TERM,
    provenance_schema: str = DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA,
    target_cycle_hash: str | None = None,
    selection_provenance: Mapping[str, object] | None = None,
) -> DiscoveryHit:
    prescreen_reason = prescreen_recap_candidate(
        court_id=lead.court_id,
        docket_number=lead.docket_number,
        case_name=lead.case_name,
        defer_bankruptcy_to_authoritative_docket=(source.source_search_type == "o"),
    )
    payload: dict[str, Any] = {
        "candidate_id": lead.candidate_id,
        "docket_id": lead.docket_id,
        "courtlistener_docket_id": lead.docket_id,
        "court_id": lead.court_id,
        "docket_number": lead.docket_number,
        "case_name": lead.case_name,
        "provider": RECAP_API_PROVIDER,
        "prescreen_exclusion_reason": prescreen_reason,
        "query_term": transfer_term,
        "direct_search_provenance": {
            "schema_version": provenance_schema,
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "source_provider_hit_id": lead.source_provider_hit_id,
            "source_query_term": lead.source_query_term,
            "source_payload_sha256": lead.source_payload_sha256,
            "source_hits": [hit.to_record() for hit in lead.source_hits],
        },
    }
    if target_cycle_hash is not None:
        provenance = cast(dict[str, object], payload["direct_search_provenance"])
        provenance["source_cycle_hash"] = source.source_cycle_hash
        provenance["target_cycle_hash"] = target_cycle_hash
    if selection_provenance is not None:
        payload["priority_dedupe_provenance"] = dict(selection_provenance)
    if lead.decision_entry_evidence is not None:
        payload["decision_entry_evidence"] = dict(lead.decision_entry_evidence)
    if lead.priority_decision_evidence is not None:
        payload["priority_decision_evidence"] = dict(lead.priority_decision_evidence)
    if lead.opinion_resolution_evidence is not None:
        payload["opinion_resolution_evidence"] = dict(lead.opinion_resolution_evidence)
    return DiscoveryHit(
        provider_hit_id=(
            f"{transfer_term}:{source.source_batch_digest}:{lead.docket_id}"
        ),
        candidate_id=lead.candidate_id,
        payload=payload,
    )


def read_batch_001_enrichment_failure_leads(
    source_store_path: str | Path,
    *,
    source_batch_id: str | None = None,
) -> tuple[Batch001Lead, ...]:
    """Read batch-001 candidates that failed Case.dev enrichment, read-only.

    The connection is opened ``mode=ro`` through a URI so the source store is
    never locked or mutated (the official/batch stores are append-only evidence).
    Enrichment failures are exactly the candidates that never reached a terminal
    observation (``current_observation_id IS NULL``); each carries its docket id
    inside its ``discovery_hits`` payload, and the candidate id itself encodes the
    docket id, so both are recovered here.
    """

    path = Path(source_store_path)
    if not path.exists():
        raise RecapApiBatchDriverError(f"batch-001 source store not found: {path}")
    uri = f"file:{path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        query = (
            "SELECT c.candidate_id AS candidate_id, "
            "c.first_batch_id AS first_batch_id, h.payload_json AS payload_json "
            "FROM candidates c "
            "JOIN discovery_hits h ON h.candidate_id = c.candidate_id "
            "AND h.batch_id = c.first_batch_id "
            "WHERE c.current_observation_id IS NULL"
        )
        params: tuple[object, ...] = ()
        if source_batch_id is not None:
            query += " AND c.first_batch_id = ?"
            params = (source_batch_id,)
        rows = connection.execute(query, params).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RecapApiBatchDriverError(
            f"batch-001 source store is not a readable acquisition store: {path}: {exc}"
        ) from exc
    finally:
        connection.close()

    # A candidate can have several discovery hits; keep the lexicographically
    # first payload deterministically so the seed page is stable across runs.
    by_candidate: dict[str, tuple[str, str, Mapping[str, Any]]] = {}
    for row in rows:
        candidate_id = str(row["candidate_id"])
        payload_json = str(row["payload_json"])
        first_batch_id = str(row["first_batch_id"])
        existing = by_candidate.get(candidate_id)
        if existing is None or payload_json < existing[0]:
            parsed = cast(object, json.loads(payload_json))
            payload = cast(
                Mapping[str, Any], parsed if isinstance(parsed, dict) else {}
            )
            by_candidate[candidate_id] = (payload_json, first_batch_id, payload)

    leads: list[Batch001Lead] = []
    for candidate_id, (_payload_json, first_batch_id, payload) in by_candidate.items():
        docket_id = _docket_id_from_candidate(candidate_id, payload)
        if docket_id is None:
            continue
        leads.append(
            Batch001Lead(
                candidate_id=candidate_id,
                docket_id=docket_id,
                source_first_batch_id=first_batch_id,
                case_name=_optional_str(payload.get("case_name"))
                or _optional_str(payload.get("caseName")),
                docket_number=_optional_str(payload.get("docket_number"))
                or _optional_str(payload.get("docketNumber")),
                court_id=_optional_str(payload.get("court_id"))
                or _optional_str(payload.get("court")),
            )
        )
    leads.sort(key=_lead_sort_key)
    return tuple(leads)


def seed_batch_001_leads(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    leads: Sequence[Batch001Lead],
) -> SeedResult:
    """Seed batch-001 enrichment-failure leads into the batch-002 store.

    The target batch must already be attached (run ``discover`` first); seeding
    only adds discovery hits, it does not freeze the batch config.  Leads are
    Non-empty leads are committed as a single exhausted page under
    :data:`BATCH_001_REOBSERVATION_TERM`, so the operation is idempotent: a re-run
    finds the term already terminal and seeds nothing new. An empty selection
    leaves the term non-terminal so a corrected source selection can be retried.
    """

    store.batch_digest(batch_id)
    store.ensure_terms(batch_id, (BATCH_001_REOBSERVATION_TERM,))
    progress = store.term_progress(batch_id, BATCH_001_REOBSERVATION_TERM)
    if progress.terminal_status is not None:
        return SeedResult(
            batch_id=batch_id,
            leads_selected=len(leads),
            leads_seeded=0,
            already_seeded=True,
        )

    if not leads:
        return SeedResult(
            batch_id=batch_id,
            leads_selected=0,
            leads_seeded=0,
            already_seeded=False,
        )

    hits = tuple(_lead_to_hit(lead) for lead in leads)
    store.commit_search_page(
        batch_id,
        BATCH_001_REOBSERVATION_TERM,
        None,
        hits,
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )
    return SeedResult(
        batch_id=batch_id,
        leads_selected=len(leads),
        leads_seeded=len(hits),
        already_seeded=False,
    )


def _lead_to_hit(lead: Batch001Lead) -> DiscoveryHit:
    prescreen_reason = prescreen_recap_candidate(
        court_id=lead.court_id,
        docket_number=lead.docket_number,
        case_name=lead.case_name,
    )
    payload: dict[str, Any] = {
        "candidate_id": lead.candidate_id,
        "docket_id": lead.docket_id,
        "courtlistener_docket_id": lead.docket_id,
        "court_id": lead.court_id,
        "docket_number": lead.docket_number,
        "case_name": lead.case_name,
        "provider": RECAP_API_PROVIDER,
        "prescreen_exclusion_reason": prescreen_reason,
        "reobservation_provenance": {
            "schema_version": BATCH_001_REOBSERVATION_PROVENANCE_SCHEMA,
            "failure_class": BATCH_001_ENRICHMENT_FAILURE_CLASS,
            "source_candidate_id": lead.candidate_id,
            "source_first_batch_id": lead.source_first_batch_id,
        },
    }
    return DiscoveryHit(
        provider_hit_id=f"{BATCH_001_REOBSERVATION_TERM}:{lead.docket_id}",
        candidate_id=lead.candidate_id,
        payload=payload,
    )


def _docket_id_from_candidate(
    candidate_id: str, payload: Mapping[str, Any]
) -> str | None:
    try:
        return candidate_docket_id({"candidate_id": candidate_id, **dict(payload)})
    except RecapApiResponseError:
        # A lead whose docket id cannot be recovered is dropped rather than
        # seeded with an unusable identity.
        return None


def _lead_sort_key(lead: Batch001Lead) -> tuple[int, int, str]:
    # Numeric docket ids sort numerically; anything non-numeric sorts after, by
    # string, so the seed page order is fully deterministic.
    try:
        return (0, int(lead.docket_id), lead.docket_id)
    except ValueError:
        return (1, 0, lead.docket_id)


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

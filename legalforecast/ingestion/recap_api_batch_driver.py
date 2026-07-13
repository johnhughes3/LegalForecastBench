"""One-command drivers for the Cycle 1 batch-002 RECAP REST v4 pipeline.

The heavy lifting already lives in :mod:`legalforecast.ingestion.recap_api_discovery`
(decision-first search, fail-closed docket reconstruction, strict-screen
observation) and :mod:`legalforecast.ingestion.discovery_scheduler` (resumable,
per-term bounded materialization).  This module is the thin composition layer the
operator drives through the CLI: it wires those primitives to the durable
:class:`~legalforecast.ingestion.cycle_acquisition_store.CycleAcquisitionStore`
and emits funnel-style summaries.

Three phases, each resumable through the store and each fail-closed:

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

Nothing here mutates the frozen screening files or the source batch-001 store.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
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


def _config_window_end(store: CycleAcquisitionStore, batch_id: str) -> date | None:
    """Read the frozen decision-window upper bound from the batch config."""

    raw = store.batch_config(batch_id).get("decision_window_end")
    if isinstance(raw, str) and raw.strip():
        return date.fromisoformat(raw)
    return None


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
    progress_callback: Callable[[ObserveTally], None] | None = None,
) -> ObserveTally:
    """Reconstruct, screen, and durably observe every unresolved candidate.

    Fails closed *before any network request* when no CourtListener API token is
    configured, because docket reconstruction needs one.  A candidate that
    already carries a current (terminal) observation is skipped, so re-running is
    safe and resumes exactly where a prior pass stopped; a candidate whose only
    prior observation was a transient failure is retried (transient failures
    never become the current observation).
    """

    require_reconstruction_auth(client)
    store.batch_digest(batch_id)
    decision_window_end = _config_window_end(store, batch_id)

    payloads = {
        hit.candidate_id: hit.payload
        for hit in store.candidate_discovery_hits(batch_id)
    }

    considered = 0
    skipped = 0
    observed = 0
    eligible = 0
    excluded: dict[str, int] = {}
    transient: dict[str, int] = {}

    for candidate_id in store.candidate_ids(batch_id):
        if limit is not None and observed >= limit:
            break
        considered += 1
        if store.current_observation(candidate_id) is not None:
            skipped += 1
            continue
        payload = payloads.get(candidate_id)
        if payload is None:
            raise RecapApiBatchDriverError(
                f"candidate {candidate_id} has no discovery hit payload to observe"
            )
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
    committed as a single exhausted page under
    :data:`BATCH_001_REOBSERVATION_TERM`, so the operation is idempotent: a re-run
    finds the term already terminal and seeds nothing new.
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

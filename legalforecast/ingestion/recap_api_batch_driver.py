"""One-command drivers for the Cycle 1 batch-002 RECAP REST v4 pipeline.

The heavy lifting already lives in :mod:`legalforecast.ingestion.recap_api_discovery`
(decision-first search, fail-closed docket reconstruction, strict-screen
observation) and :mod:`legalforecast.ingestion.discovery_scheduler` (resumable,
per-term bounded materialization).  This module is the thin composition layer the
operator drives through the CLI: it wires those primitives to the durable
:class:`~legalforecast.ingestion.cycle_acquisition_store.CycleAcquisitionStore`
and emits funnel-style summaries.

Four phases, each resumable through the store and each fail-closed:

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
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    cohort_reason_policy_taxonomy,
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

    @property
    def candidate_id(self) -> str:
        return f"courtlistener-docket-{self.docket_id}"

    def commitment_record(self) -> dict[str, object]:
        """Return the canonical source record covered by the set commitment."""

        return {
            "docket_id": self.docket_id,
            "court_id": self.court_id,
            "docket_number": self.docket_number,
            "case_name": self.case_name,
            "decision_entry_evidence": (
                None
                if self.decision_entry_evidence is None
                else dict(self.decision_entry_evidence)
            ),
            "source_hits": [hit.to_record() for hit in self.source_hits],
        }


@dataclass(frozen=True, slots=True)
class DirectSearchSeedSource:
    """Verified saturated direct-search source and its deterministic leads."""

    source_batch_id: str
    source_batch_digest: str
    source_cycle_hash: str
    source_candidate_set_sha256: str
    search_window_start: date
    search_window_end: date
    leads: tuple[DirectSearchLead, ...]


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
        decoded = cast(object, json.loads(str(batch["config_json"])))
        if not isinstance(decoded, dict):
            raise RecapApiBatchDriverError(
                "direct-search batch config is not an object"
            )
        config = cast(dict[str, object], decoded)
        if config.get("provider") != "courtlistener":
            raise RecapApiBatchDriverError(
                "direct-search source batch is not CourtListener-authoritative"
            )
        query_terms = config.get("query_terms")
        if not isinstance(query_terms, list) or not query_terms:
            raise RecapApiBatchDriverError(
                "direct-search source batch lacks frozen query terms"
            )
        terms = tuple(str(term).strip() for term in cast(list[object], query_terms))
        if any(not term for term in terms) or len(set(terms)) != len(terms):
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
            window_start = date.fromisoformat(str(config["search_window_start"]))
            window_end = date.fromisoformat(str(config["search_window_end"]))
        except (KeyError, ValueError) as exc:
            raise RecapApiBatchDriverError(
                "direct-search source batch has invalid search window"
            ) from exc
        if window_end < window_start:
            raise RecapApiBatchDriverError(
                "direct-search source batch search window is inverted"
            )
        cycle = connection.execute(
            "SELECT policy_hash FROM cycle_identity WHERE singleton = 1"
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
        source_batch_digest = str(batch["config_digest"])
        source_cycle_hash = str(cycle["policy_hash"])
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
            ]
        ],
    ] = {}
    try:
        for row in rows:
            docket_id = str(row["candidate_id"])
            if not docket_id.isascii() or not docket_id.isdigit():
                raise RecapApiBatchDriverError(
                    f"direct-search candidate id is not numeric: {docket_id!r}"
                )
            payload_json = str(row["payload_json"])
            parsed = cast(object, json.loads(payload_json))
            if not isinstance(parsed, dict):
                raise RecapApiBatchDriverError(
                    f"direct-search payload is not an object: {docket_id}"
                )
            payload = cast(dict[str, object], parsed)
            if str(payload.get("docket_id")) != docket_id:
                raise RecapApiBatchDriverError(
                    f"direct-search payload docket id mismatch: {docket_id}"
                )
            evidence = _minimum_direct_search_entry_evidence(payload, docket_id)
            grouped.setdefault(docket_id, []).append(
                (
                    str(row["term"]),
                    str(row["provider_hit_id"]),
                    payload_json,
                    payload,
                    evidence,
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
            )
        )
    leads = tuple(sorted(leads_list, key=lambda lead: int(lead.docket_id)))
    candidate_set_sha256 = hashlib.sha256(
        json.dumps(
            [lead.commitment_record() for lead in leads],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return DirectSearchSeedSource(
        source_batch_id=source_batch_id,
        source_batch_digest=source_batch_digest,
        source_cycle_hash=source_cycle_hash,
        source_candidate_set_sha256=candidate_set_sha256,
        search_window_start=window_start,
        search_window_end=window_end,
        leads=leads,
    )


def _minimum_direct_search_entry_evidence(
    payload: Mapping[str, object], docket_id: str
) -> tuple[int, int, str, dict[str, object]] | None:
    raw_documents = payload.get("recap_documents")
    if raw_documents is None:
        return None
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
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(DIRECT_SEARCH_TRANSFER_TERM,),
        page_size=page_size,
        top_k_per_term=max(len(source.leads), 1),
    )
    config.update(
        {
            "discovery_mode": DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA,
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_candidate_count": len(source.leads),
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
        }
    )
    store.ensure_batch(batch_id, config)
    store.ensure_terms(batch_id, (DIRECT_SEARCH_TRANSFER_TERM,))
    progress = store.term_progress(batch_id, DIRECT_SEARCH_TRANSFER_TERM)
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
        hits = tuple(_direct_search_lead_to_hit(lead, source) for lead in page)
        progress = store.commit_search_page(
            batch_id,
            DIRECT_SEARCH_TRANSFER_TERM,
            progress.cursor,
            hits,
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
        offset = next_offset
    if not source.leads:
        store.commit_search_page(
            batch_id,
            DIRECT_SEARCH_TRANSFER_TERM,
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


def _direct_search_lead_to_hit(
    lead: DirectSearchLead,
    source: DirectSearchSeedSource,
) -> DiscoveryHit:
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
        "query_term": DIRECT_SEARCH_TRANSFER_TERM,
        "direct_search_provenance": {
            "schema_version": DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA,
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "source_provider_hit_id": lead.source_provider_hit_id,
            "source_query_term": lead.source_query_term,
            "source_payload_sha256": lead.source_payload_sha256,
            "source_hits": [hit.to_record() for hit in lead.source_hits],
        },
    }
    if lead.decision_entry_evidence is not None:
        payload["decision_entry_evidence"] = dict(lead.decision_entry_evidence)
    return DiscoveryHit(
        provider_hit_id=(
            f"{DIRECT_SEARCH_TRANSFER_TERM}:{source.source_batch_digest}:"
            f"{lead.docket_id}"
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

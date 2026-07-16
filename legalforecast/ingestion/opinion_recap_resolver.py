"""Resolve CourtListener opinion leads to strict RECAP docket identities.

CourtListener's opinion-search ``docket_id`` belongs to the case-law database
and is not necessarily the numeric RECAP docket identifier.  This module maps
only frozen, fully exhausted opinion-source leads.  It uses noncharging
Case.dev search first and authenticated CourtListener ``type=r`` search as a
fallback, never ``available_only`` and never a PACER or RECAP Fetch endpoint.

Every logical provider request and every terminal lead outcome is committed to
an fsync-backed SQLite journal.  Only after all selected leads are terminal is
the resolved union materialized as a source-bound saturated discovery batch
accepted by the existing direct-search transfer commands.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal, cast

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevDocketHit,
    CaseDevServerError,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudgetExhausted,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, TermTerminalStatus
from legalforecast.ingestion.opinion_recap_firecrawl import (
    OpinionRecapFirecrawlResolver,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    DirectSearchLead,
    DirectSearchSeedSource,
    RecapApiBatchDriverError,
    read_saturated_direct_search_leads,
)

OPINION_RECAP_RESOLUTION_SCHEMA = "legalforecast.opinion_recap_resolution.v1"
OPINION_RECAP_RESOLVER_POLICY_SCHEMA = "legalforecast.opinion_recap_resolver_policy.v1"
OPINION_RECAP_RESOLVED_BATCH_SCHEMA = "legalforecast.opinion_recap_resolved_source.v1"
OPINION_RECAP_RESOLUTION_TERM = "opinion-recap-resolution-v1"
_OPINION_SOURCE_SCHEMA = "legalforecast.courtlistener_opinion_discovery.v1"
_OPINION_EVIDENCE_SCHEMA = "legalforecast.courtlistener_opinion_hit.v1"
_CASE_DEV_PAGE_SIZE = 100
_COURTLISTENER_PAGE_SIZE = 20
_DEFAULT_MAX_PAGES = 25
_DEFAULT_SIMILARITY_THRESHOLD = 0.90
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OpinionRecapResolutionError(RuntimeError):
    """Raised when source, matching, checkpoint, or output proof is invalid."""


class _CaseDevPaginationExhaustionUnproven(RuntimeError):
    """Signal that a full Case.dev page cannot support a uniqueness claim."""


class _UnrepresentableSourceQuery(OpinionRecapResolutionError):
    """Signal that a frozen source caption cannot safely be sent as a query."""

    def __init__(self, message: str, *, evidence_code: str) -> None:
        super().__init__(message)
        self.evidence_code = evidence_code


@dataclass(frozen=True, slots=True)
class OpinionRecapResolutionSummary:
    source_batch_id: str
    output_batch_id: str
    source_leads: int
    resolved: int
    deferred: int
    excluded: int
    case_dev_requests: int
    courtlistener_requests: int
    complete: bool
    saturated: bool
    resolver_policy_sha256: str
    outcome_set_sha256: str

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.opinion_recap_resolution_summary.v1",
            "source_batch_id": self.source_batch_id,
            "output_batch_id": self.output_batch_id,
            "source_leads": self.source_leads,
            "resolved": self.resolved,
            "deferred": self.deferred,
            "excluded": self.excluded,
            "case_dev_requests": self.case_dev_requests,
            "courtlistener_requests": self.courtlistener_requests,
            "complete": self.complete,
            "saturated": self.saturated,
            "resolver_policy_sha256": self.resolver_policy_sha256,
            "outcome_set_sha256": self.outcome_set_sha256,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }


@dataclass(frozen=True, slots=True)
class _ProviderCandidate:
    docket_id: str
    court_id: str | None
    docket_number: str | None
    case_name: str | None
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ProviderResults:
    provider: str
    query: str
    candidates: tuple[_ProviderCandidate, ...]
    response_sha256: str
    page_count: int


@dataclass(frozen=True, slots=True)
class _Match:
    candidate: _ProviderCandidate | None
    method: str | None
    similarity: float | None
    reason_code: str | None
    proof: Mapping[str, object]


class _ResolutionJournal:
    def __init__(self, path: str | Path, policy: Mapping[str, object]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS resolver_policy(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                policy_json TEXT NOT NULL,
                policy_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS request_attempts(
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_candidate_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                request_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('started','succeeded','failed')),
                response_sha256 TEXT,
                error_type TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS outcomes(
                source_candidate_id TEXT PRIMARY KEY,
                ordinal INTEGER NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK(state IN ('resolved','deferred','excluded')),
                reason_code TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                committed_at TEXT NOT NULL
            );
            """
        )
        policy_json = _canonical_json(policy)
        policy_sha256 = _sha256_text(policy_json)
        row = self.connection.execute(
            "SELECT policy_json, policy_sha256 FROM resolver_policy WHERE singleton=1"
        ).fetchone()
        if row is None:
            self.connection.execute(
                "INSERT INTO resolver_policy VALUES(1, ?, ?)",
                (policy_json, policy_sha256),
            )
            self.connection.commit()
        elif (
            str(row["policy_json"]) != policy_json
            or str(row["policy_sha256"]) != policy_sha256
        ):
            raise OpinionRecapResolutionError(
                "resolver journal policy differs from the requested run"
            )
        self.policy_sha256 = policy_sha256

    def __enter__(self) -> _ResolutionJournal:
        return self

    def __exit__(self, *_args: object) -> None:
        self.connection.close()

    def outcome_ids(self) -> frozenset[str]:
        return frozenset(
            str(row[0])
            for row in self.connection.execute(
                "SELECT source_candidate_id FROM outcomes"
            )
        )

    def start_request(
        self,
        *,
        source_candidate_id: str,
        provider: str,
        request: Mapping[str, object],
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO request_attempts(
                source_candidate_id, provider, request_json, state, started_at
            ) VALUES(?, ?, ?, 'started', ?)
            """,
            (
                source_candidate_id,
                provider,
                _canonical_json(request),
                _utc_now(),
            ),
        )
        self.connection.commit()
        attempt_id = cursor.lastrowid
        if attempt_id is None:
            raise OpinionRecapResolutionError("resolver request attempt ID is missing")
        return attempt_id

    def finish_request(
        self,
        attempt_id: int,
        *,
        response_sha256: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        state = "failed" if error is not None else "succeeded"
        self.connection.execute(
            """
            UPDATE request_attempts
            SET state=?, response_sha256=?, error_type=?, completed_at=?
            WHERE attempt_id=? AND state='started'
            """,
            (
                state,
                response_sha256,
                None if error is None else type(error).__name__,
                _utc_now(),
                attempt_id,
            ),
        )
        self.connection.commit()

    def commit_outcome(
        self,
        *,
        source_candidate_id: str,
        ordinal: int,
        state: Literal["resolved", "deferred", "excluded"],
        reason_code: str,
        evidence: Mapping[str, object],
    ) -> None:
        evidence_json = _canonical_json(evidence)
        existing = self.connection.execute(
            "SELECT * FROM outcomes WHERE source_candidate_id=?",
            (source_candidate_id,),
        ).fetchone()
        if existing is not None:
            if (
                int(existing["ordinal"]) != ordinal
                or str(existing["state"]) != state
                or str(existing["reason_code"]) != reason_code
                or str(existing["evidence_json"]) != evidence_json
            ):
                raise OpinionRecapResolutionError(
                    "conflicting terminal outcome for opinion lead "
                    f"{source_candidate_id}"
                )
            return
        self.connection.execute(
            """
            INSERT INTO outcomes VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                source_candidate_id,
                ordinal,
                state,
                reason_code,
                evidence_json,
                _utc_now(),
            ),
        )
        self.connection.commit()

    def outcomes(self) -> tuple[dict[str, object], ...]:
        rows = self.connection.execute(
            "SELECT * FROM outcomes ORDER BY ordinal"
        ).fetchall()
        return tuple(
            {
                "source_candidate_id": str(row["source_candidate_id"]),
                "ordinal": int(row["ordinal"]),
                "state": str(row["state"]),
                "reason_code": str(row["reason_code"]),
                "evidence": cast(dict[str, object], json.loads(row["evidence_json"])),
                "committed_at": str(row["committed_at"]),
            }
            for row in rows
        )


def read_resolution_outcomes(path: str | Path) -> tuple[dict[str, object], ...]:
    """Read deterministic terminal resolver outcomes for audit/reporting."""

    journal_path = Path(path)
    if not journal_path.exists():
        raise OpinionRecapResolutionError(f"resolver journal not found: {journal_path}")
    connection = sqlite3.connect(f"file:{journal_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT * FROM outcomes ORDER BY ordinal").fetchall()
        return tuple(
            {
                "source_candidate_id": str(row["source_candidate_id"]),
                "ordinal": int(row["ordinal"]),
                "state": str(row["state"]),
                "reason_code": str(row["reason_code"]),
                "evidence": cast(dict[str, object], json.loads(row["evidence_json"])),
                "committed_at": str(row["committed_at"]),
            }
            for row in rows
        )
    except (sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        raise OpinionRecapResolutionError(
            f"resolver journal is unreadable: {journal_path}: {exc}"
        ) from exc
    finally:
        connection.close()


def resolve_opinion_recap_batch(
    *,
    source_store_path: str | Path,
    source_batch_id: str,
    journal_path: str | Path,
    output_store_path: str | Path,
    output_batch_id: str,
    case_dev_client: CaseDevClient | None,
    courtlistener_client: CourtListenerClient,
    firecrawl_resolver: OpinionRecapFirecrawlResolver | None = None,
    prior_candidate_ids: frozenset[str] = frozenset(),
    prior_snapshot_commitment_sha256: str | None = None,
    max_pages_per_lead: int = _DEFAULT_MAX_PAGES,
    case_name_similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
) -> OpinionRecapResolutionSummary:
    """Resolve and checkpoint every frozen opinion lead, then emit a source batch."""

    if output_batch_id == source_batch_id:
        raise OpinionRecapResolutionError("output batch must differ from source batch")
    if max_pages_per_lead <= 0:
        raise ValueError("max_pages_per_lead must be positive")
    if not 0.0 < case_name_similarity_threshold <= 1.0:
        raise ValueError("case_name_similarity_threshold must be in (0, 1]")
    if case_dev_client is not None and case_dev_client.max_retries != 0:
        raise OpinionRecapResolutionError(
            "Case.dev resolver client must disable internal retries so every "
            "physical request is journaled"
        )
    if prior_candidate_ids and (
        prior_snapshot_commitment_sha256 is None
        or _SHA256.fullmatch(prior_snapshot_commitment_sha256) is None
    ):
        raise OpinionRecapResolutionError(
            "prior candidate IDs require an exact snapshot commitment SHA-256"
        )
    source, source_payloads = _read_opinion_source(
        source_store_path, source_batch_id=source_batch_id
    )
    policy: dict[str, object] = {
        "schema_version": OPINION_RECAP_RESOLVER_POLICY_SCHEMA,
        "source_store": str(Path(source_store_path).resolve()),
        "source_batch_id": source.source_batch_id,
        "source_batch_digest": source.source_batch_digest,
        "source_cycle_hash": source.source_cycle_hash,
        "source_candidate_set_sha256": source.source_candidate_set_sha256,
        "source_lead_count": len(source.leads),
        "output_store": str(Path(output_store_path).resolve()),
        "output_batch_id": output_batch_id,
        "provider_order": [
            *(["case.dev"] if case_dev_client is not None else []),
            "courtlistener_rest",
            *(
                ["courtlistener_html_via_firecrawl"]
                if firecrawl_resolver is not None
                else []
            ),
        ],
        "case_dev_search_live_pacer": False,
        "case_dev_server_error_fallback": "courtlistener_rest",
        "provider_query_contract": "quoted_exact_case_name_v1",
        "unrepresentable_source_query_action": "terminal_exclusion_v1",
        "courtlistener_search_type": "r",
        "courtlistener_available_only": "omitted",
        "case_dev_page_size": _CASE_DEV_PAGE_SIZE,
        "courtlistener_page_size": _COURTLISTENER_PAGE_SIZE,
        "max_pages_per_lead": max_pages_per_lead,
        "case_name_similarity_threshold": case_name_similarity_threshold,
        "prior_candidate_count": len(prior_candidate_ids),
        "prior_candidate_set_sha256": _sha256_json(sorted(prior_candidate_ids)),
        "prior_snapshot_commitment_sha256": prior_snapshot_commitment_sha256,
        "paid_activity_allowed": False,
    }
    if firecrawl_resolver is not None:
        policy["firecrawl_fallback_policy"] = dict(firecrawl_resolver.policy)
    case_dev_start = 0 if case_dev_client is None else case_dev_client.request_count
    courtlistener_start = courtlistener_client.request_count
    with _ResolutionJournal(journal_path, policy) as journal:
        completed = journal.outcome_ids()
        for ordinal, lead in enumerate(source.leads):
            opinion_candidate_id = lead.docket_id
            if opinion_candidate_id in completed:
                continue
            payload = source_payloads[opinion_candidate_id]
            _resolve_one_lead(
                journal=journal,
                ordinal=ordinal,
                lead=lead,
                source_payload=payload,
                source=source,
                case_dev_client=case_dev_client,
                courtlistener_client=courtlistener_client,
                firecrawl_resolver=firecrawl_resolver,
                prior_candidate_ids=prior_candidate_ids,
                max_pages=max_pages_per_lead,
                similarity_threshold=case_name_similarity_threshold,
            )
        outcomes = journal.outcomes()
        if len(outcomes) != len(source.leads):
            raise OpinionRecapResolutionError(
                "resolver did not reconcile every frozen opinion lead"
            )
        outcome_commitments = [
            {
                "source_candidate_id": row["source_candidate_id"],
                "ordinal": row["ordinal"],
                "state": row["state"],
                "reason_code": row["reason_code"],
                "evidence": row["evidence"],
            }
            for row in outcomes
        ]
        outcome_set_sha256 = _sha256_json(outcome_commitments)
        policy_sha256 = journal.policy_sha256
    _materialize_resolved_batch(
        output_store_path=output_store_path,
        output_batch_id=output_batch_id,
        source=source,
        outcomes=outcomes,
        resolver_policy_sha256=policy_sha256,
        outcome_set_sha256=outcome_set_sha256,
        prior_snapshot_commitment_sha256=prior_snapshot_commitment_sha256,
    )
    counts = {state: 0 for state in ("resolved", "deferred", "excluded")}
    for outcome in outcomes:
        counts[cast(str, outcome["state"])] += 1
    return OpinionRecapResolutionSummary(
        source_batch_id=source_batch_id,
        output_batch_id=output_batch_id,
        source_leads=len(source.leads),
        resolved=counts["resolved"],
        deferred=counts["deferred"],
        excluded=counts["excluded"],
        case_dev_requests=(
            0
            if case_dev_client is None
            else case_dev_client.request_count - case_dev_start
        ),
        courtlistener_requests=(
            courtlistener_client.request_count - courtlistener_start
        ),
        complete=True,
        saturated=True,
        resolver_policy_sha256=policy_sha256,
        outcome_set_sha256=outcome_set_sha256,
    )


def _resolve_one_lead(
    *,
    journal: _ResolutionJournal,
    ordinal: int,
    lead: DirectSearchLead,
    source_payload: Mapping[str, object],
    source: DirectSearchSeedSource,
    case_dev_client: CaseDevClient | None,
    courtlistener_client: CourtListenerClient,
    firecrawl_resolver: OpinionRecapFirecrawlResolver | None,
    prior_candidate_ids: frozenset[str],
    max_pages: int,
    similarity_threshold: float,
) -> None:
    if lead.court_id is None or lead.case_name is None:
        journal.commit_outcome(
            source_candidate_id=lead.docket_id,
            ordinal=ordinal,
            state="excluded",
            reason_code="source_identity_incomplete",
            evidence={"court_id": lead.court_id, "case_name": lead.case_name},
        )
        return
    try:
        query = _quoted_case_name_query(lead.case_name)
    except _UnrepresentableSourceQuery as exc:
        journal.commit_outcome(
            source_candidate_id=lead.docket_id,
            ordinal=ordinal,
            state="excluded",
            reason_code="source_query_unrepresentable",
            evidence={
                "court_id": lead.court_id,
                "docket_number": lead.docket_number,
                "case_name_length": len(lead.case_name),
                "query_error": exc.evidence_code,
            },
        )
        return
    if case_dev_client is not None:
        try:
            results = _case_dev_results(
                journal,
                source_candidate_id=lead.docket_id,
                query=query,
                client=case_dev_client,
                max_pages=max_pages,
            )
        except (_CaseDevPaginationExhaustionUnproven, CaseDevServerError):
            # Case.dev sometimes returns a full page without a continuation field.
            # That response is useful as a lead but cannot prove there was only one
            # matching docket. Query-specific upstream 5xx failures are likewise
            # not identity evidence. In either case, rely on CourtListener's
            # explicit pagination rather than aborting the remaining frozen leads.
            pass
        else:
            match = _strict_match(
                lead,
                results,
                similarity_threshold=similarity_threshold,
            )
            if match.reason_code in {"exact_identity_ambiguous", "fallback_ambiguous"}:
                _commit_failed_match(journal, ordinal=ordinal, lead=lead, match=match)
                return
            if match.candidate is not None:
                _commit_resolved_match(
                    journal,
                    ordinal=ordinal,
                    lead=lead,
                    source_payload=source_payload,
                    source=source,
                    results=results,
                    match=match,
                    prior_candidate_ids=prior_candidate_ids,
                )
                return
    try:
        results = _courtlistener_results(
            journal,
            source_candidate_id=lead.docket_id,
            query=query,
            client=courtlistener_client,
            max_pages=max_pages,
        )
    except CourtListenerRequestBudgetExhausted:
        if firecrawl_resolver is None:
            raise
        results = _firecrawl_results(
            journal,
            source_candidate_id=lead.docket_id,
            source_ordinal=ordinal,
            query=query,
            court_id=lead.court_id,
            resolver=firecrawl_resolver,
        )
    match = _strict_match(
        lead,
        results,
        similarity_threshold=similarity_threshold,
    )
    if match.candidate is None:
        _commit_failed_match(journal, ordinal=ordinal, lead=lead, match=match)
        return
    _commit_resolved_match(
        journal,
        ordinal=ordinal,
        lead=lead,
        source_payload=source_payload,
        source=source,
        results=results,
        match=match,
        prior_candidate_ids=prior_candidate_ids,
    )


def _case_dev_results(
    journal: _ResolutionJournal,
    *,
    source_candidate_id: str,
    query: str,
    client: CaseDevClient,
    max_pages: int,
) -> _ProviderResults:
    candidates: list[_ProviderCandidate] = []
    payloads: list[Mapping[str, Any]] = []
    cursor: str | None = None
    returned_count = 0
    reported_found: int | None = None
    seen_docket_ids: set[str] = set()
    for _page_index in range(max_pages):
        request: dict[str, object] = {
            "method": "POST",
            "path": "/legal/v1/docket",
            "body": {"type": "search", "query": query, "limit": _CASE_DEV_PAGE_SIZE},
            "cursor": cursor,
            "live": False,
            "acknowledgePacerFees": False,
        }
        attempt = journal.start_request(
            source_candidate_id=source_candidate_id,
            provider="case.dev",
            request=request,
        )
        try:
            page = client.search_docket_entries(
                query,
                cursor=cursor,
                limit=_CASE_DEV_PAGE_SIZE,
            )
        except BaseException as exc:
            journal.finish_request(attempt, error=exc)
            raise
        page_sha256 = _sha256_json(page.raw)
        journal.finish_request(attempt, response_sha256=page_sha256)
        payloads.append(page.raw)
        page_candidates = tuple(_candidate_from_case_dev(hit) for hit in page.items)
        page_docket_ids = [candidate.docket_id for candidate in page_candidates]
        if len(page_docket_ids) != len(set(page_docket_ids)) or any(
            docket_id in seen_docket_ids for docket_id in page_docket_ids
        ):
            raise OpinionRecapResolutionError(
                "Case.dev resolver returned duplicate docket IDs across result rows"
            )
        seen_docket_ids.update(page_docket_ids)
        candidates.extend(page_candidates)
        returned_count = len(seen_docket_ids)
        page_found = _case_dev_reported_found(page.raw)
        if page_found is not None:
            if reported_found is not None and page_found != reported_found:
                raise OpinionRecapResolutionError(
                    "Case.dev resolver found total changed across pages"
                )
            reported_found = page_found
        if reported_found is not None and reported_found < returned_count:
            raise OpinionRecapResolutionError(
                "Case.dev resolver found total is below returned row count"
            )
        if (
            page.next_cursor is not None
            and reported_found is not None
            and reported_found == returned_count
        ):
            raise OpinionRecapResolutionError(
                "Case.dev resolver returned a continuation after reported found total"
            )
        if page.next_cursor is None:
            exhaustion_unproven = (
                len(page.items) >= _CASE_DEV_PAGE_SIZE
                if reported_found is None
                else reported_found > returned_count
            )
            if exhaustion_unproven:
                raise _CaseDevPaginationExhaustionUnproven(
                    "Case.dev resolver pagination exhaustion is unproven"
                )
            break
        cursor = page.next_cursor
    else:
        raise OpinionRecapResolutionError(
            f"case.dev mapping pagination exceeded {max_pages} pages for "
            f"opinion lead {source_candidate_id}"
        )
    return _ProviderResults(
        provider="case.dev",
        query=query,
        candidates=_deduped_candidates(candidates),
        response_sha256=_response_commitment(payloads),
        page_count=len(payloads),
    )


def _courtlistener_results(
    journal: _ResolutionJournal,
    *,
    source_candidate_id: str,
    query: str,
    client: CourtListenerClient,
    max_pages: int,
) -> _ProviderResults:
    candidates: list[_ProviderCandidate] = []
    payloads: list[Mapping[str, Any]] = []
    cursor: str | None = None
    params: dict[str, object] = {
        "type": "r",
        "q": query,
        "order_by": "score desc",
        "page_size": _COURTLISTENER_PAGE_SIZE,
    }
    for _page_index in range(max_pages):
        request = {
            "method": "GET",
            "path": "/search/",
            "params": dict(params),
            "cursor": cursor,
            "available_only": "omitted",
        }
        attempt = journal.start_request(
            source_candidate_id=source_candidate_id,
            provider="courtlistener_rest",
            request=request,
        )
        try:
            page = client.search_raw(params, cursor=cursor)
            if "results" not in page.raw or not isinstance(page.raw["results"], list):
                raise OpinionRecapResolutionError(
                    "CourtListener resolver response lacks explicit results"
                )
            if "next" not in page.raw:
                raise OpinionRecapResolutionError(
                    "CourtListener resolver response lacks explicit pagination proof"
                )
        except BaseException as exc:
            journal.finish_request(attempt, error=exc)
            raise
        page_sha256 = _sha256_json(page.raw)
        journal.finish_request(attempt, response_sha256=page_sha256)
        payloads.append(page.raw)
        candidates.extend(
            _candidate_from_courtlistener(record) for record in page.items
        )
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    else:
        raise OpinionRecapResolutionError(
            f"CourtListener mapping pagination exceeded {max_pages} pages for "
            f"opinion lead {source_candidate_id}"
        )
    return _ProviderResults(
        provider="courtlistener_rest",
        query=query,
        candidates=_deduped_candidates(candidates),
        response_sha256=_response_commitment(payloads),
        page_count=len(payloads),
    )


def _firecrawl_results(
    journal: _ResolutionJournal,
    *,
    source_candidate_id: str,
    source_ordinal: int,
    query: str,
    court_id: str,
    resolver: OpinionRecapFirecrawlResolver,
) -> _ProviderResults:
    request = {
        "method": "GET",
        "route": "courtlistener_public_search_via_firecrawl",
        "query": query,
        "court_id": court_id,
        "available_only": "omitted",
        "paid_activity_allowed": False,
    }
    attempt = journal.start_request(
        source_candidate_id=source_candidate_id,
        provider="courtlistener_html_via_firecrawl",
        request=request,
    )
    try:
        results = resolver.search(
            source_candidate_id=source_candidate_id,
            source_ordinal=source_ordinal,
            query=query,
            court_id=court_id,
        )
    except BaseException as exc:
        journal.finish_request(attempt, error=exc)
        raise
    journal.finish_request(attempt, response_sha256=results.response_sha256)
    return _ProviderResults(
        provider="courtlistener_html_via_firecrawl",
        query=query,
        candidates=tuple(
            _ProviderCandidate(
                docket_id=candidate.docket_id,
                court_id=candidate.court_id,
                docket_number=candidate.docket_number,
                case_name=candidate.case_name,
                raw=candidate.raw,
            )
            for candidate in results.candidates
        ),
        response_sha256=results.response_sha256,
        page_count=results.page_count,
    )


def _strict_match(
    lead: DirectSearchLead,
    results: _ProviderResults,
    *,
    similarity_threshold: float,
) -> _Match:
    normalized_court = _normalize_identifier(lead.court_id)
    normalized_docket = _normalize_docket(lead.docket_number)
    same_court = tuple(
        candidate
        for candidate in results.candidates
        if _normalize_identifier(candidate.court_id) == normalized_court
    )
    exact = tuple(
        candidate
        for candidate in same_court
        if normalized_docket
        and _normalize_docket(candidate.docket_number) == normalized_docket
    )
    fallback_scores = tuple(
        (candidate, _case_name_similarity(lead.case_name, candidate.case_name))
        for candidate in same_court
    )
    fallback = tuple(
        (candidate, score)
        for candidate, score in fallback_scores
        if score >= similarity_threshold
    )
    proof = {
        "provider_result_count": len(results.candidates),
        "distinct_result_count": len({item.docket_id for item in results.candidates}),
        "same_court_result_count": len(same_court),
        "exact_identity_match_count": len(exact),
        "fallback_match_count": len(fallback),
        "matching_docket_ids": sorted(
            {item.docket_id for item in exact}
            or {item.docket_id for item, _score in fallback},
            key=int,
        ),
        "provider_page_count": results.page_count,
    }
    if len(exact) == 1:
        return _Match(exact[0], "exact_court_normalized_docket", None, None, proof)
    if len(exact) > 1:
        return _Match(None, None, None, "exact_identity_ambiguous", proof)
    if len(fallback) == 1:
        candidate, score = fallback[0]
        return _Match(
            candidate,
            "unique_court_case_name_similarity_fallback",
            score,
            None,
            proof,
        )
    if len(fallback) > 1:
        return _Match(None, None, None, "fallback_ambiguous", proof)
    return _Match(None, None, None, "strict_identity_not_found", proof)


def _commit_resolved_match(
    journal: _ResolutionJournal,
    *,
    ordinal: int,
    lead: DirectSearchLead,
    source_payload: Mapping[str, object],
    source: DirectSearchSeedSource,
    results: _ProviderResults,
    match: _Match,
    prior_candidate_ids: frozenset[str],
) -> None:
    candidate = match.candidate
    assert candidate is not None and match.method is not None
    opinion = source_payload.get("opinion_discovery_evidence")
    if not isinstance(opinion, Mapping):
        raise OpinionRecapResolutionError(
            f"opinion lead {lead.docket_id} lacks strict discovery evidence"
        )
    opinion_record = cast(Mapping[str, object], opinion)
    if opinion_record.get("schema_version") != _OPINION_EVIDENCE_SCHEMA:
        raise OpinionRecapResolutionError(
            f"opinion lead {lead.docket_id} lacks strict discovery evidence"
        )
    evidence: dict[str, object] = {
        "schema_version": OPINION_RECAP_RESOLUTION_SCHEMA,
        "source_opinion": {
            "candidate_id": lead.docket_id,
            "cluster_id": opinion_record.get("cluster_id"),
            "date_filed": opinion_record.get("date_filed"),
            "absolute_url": opinion_record.get("absolute_url"),
            "sub_opinions": opinion_record.get("sub_opinions", []),
            "provider_hit_id": lead.source_provider_hit_id,
            "query_term": lead.source_query_term,
            "payload_sha256": lead.source_payload_sha256,
            "source_hits": [hit.to_record() for hit in lead.source_hits],
        },
        "resolved_recap": {
            "docket_id": candidate.docket_id,
            "court_id": candidate.court_id,
            "docket_number": candidate.docket_number,
            "case_name": candidate.case_name,
        },
        "resolver": {
            "provider": results.provider,
            "query": results.query,
            "match_method": match.method,
            "normalized_source_court": _normalize_identifier(lead.court_id),
            "normalized_source_docket_number": _normalize_docket(lead.docket_number),
            "normalized_resolved_court": _normalize_identifier(candidate.court_id),
            "normalized_resolved_docket_number": _normalize_docket(
                candidate.docket_number
            ),
            "case_name_similarity": match.similarity,
        },
        "ambiguity_proof": dict(match.proof),
        "commitments": {
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "resolver_policy_sha256": journal.policy_sha256,
            "provider_response_sha256": results.response_sha256,
            "provider_result_sha256": _sha256_json(candidate.raw),
        },
    }
    payload: dict[str, object] = {
        "docket_id": candidate.docket_id,
        "court_id": candidate.court_id,
        "docket_number": candidate.docket_number,
        "case_name": candidate.case_name,
        "provider": "courtlistener",
        "opinion_resolution_evidence": evidence,
    }
    target_candidate_id = f"courtlistener-docket-{candidate.docket_id}"
    if target_candidate_id in prior_candidate_ids:
        journal.commit_outcome(
            source_candidate_id=lead.docket_id,
            ordinal=ordinal,
            state="deferred",
            reason_code="seen_in_prior_screening_snapshot",
            evidence={
                "target_candidate_id": target_candidate_id,
                "opinion_resolution_evidence": evidence,
            },
        )
        return
    journal.commit_outcome(
        source_candidate_id=lead.docket_id,
        ordinal=ordinal,
        state="resolved",
        reason_code="strict_recap_identity_resolved",
        evidence={
            "target_candidate_id": target_candidate_id,
            "payload": payload,
            "opinion_resolution_evidence": evidence,
        },
    )


def _commit_failed_match(
    journal: _ResolutionJournal,
    *,
    ordinal: int,
    lead: DirectSearchLead,
    match: _Match,
) -> None:
    journal.commit_outcome(
        source_candidate_id=lead.docket_id,
        ordinal=ordinal,
        state="excluded",
        reason_code=match.reason_code or "strict_identity_not_found",
        evidence={
            "source_candidate_id": lead.docket_id,
            "court_id": lead.court_id,
            "docket_number": lead.docket_number,
            "case_name": lead.case_name,
            "ambiguity_proof": dict(match.proof),
        },
    )


def _materialize_resolved_batch(
    *,
    output_store_path: str | Path,
    output_batch_id: str,
    source: DirectSearchSeedSource,
    outcomes: Sequence[Mapping[str, object]],
    resolver_policy_sha256: str,
    outcome_set_sha256: str,
    prior_snapshot_commitment_sha256: str | None,
) -> None:
    resolved = tuple(row for row in outcomes if row["state"] == "resolved")
    resolved_by_docket: dict[str, list[Mapping[str, object]]] = {}
    for row in resolved:
        evidence = cast(Mapping[str, object], row["evidence"])
        payload = cast(Mapping[str, object], evidence["payload"])
        resolved_by_docket.setdefault(str(payload["docket_id"]), []).append(row)
    config: dict[str, object] = {
        "schema_version": OPINION_RECAP_RESOLVED_BATCH_SCHEMA,
        "provider": "courtlistener",
        "search_type": "r",
        "available_only": "omitted",
        "query_terms": [OPINION_RECAP_RESOLUTION_TERM],
        "query_term_order_is_frozen": True,
        "search_window_start": source.search_window_start.isoformat(),
        "search_window_end": source.search_window_end.isoformat(),
        "source_batch_id": source.source_batch_id,
        "source_batch_digest": source.source_batch_digest,
        "source_cycle_hash": source.source_cycle_hash,
        "source_candidate_set_sha256": source.source_candidate_set_sha256,
        "source_lead_count": len(source.leads),
        "resolution_outcome_count": len(outcomes),
        "resolved_lead_count": len(resolved),
        "resolved_candidate_count": len(resolved_by_docket),
        "resolver_policy_sha256": resolver_policy_sha256,
        "outcome_set_sha256": outcome_set_sha256,
        "prior_snapshot_commitment_sha256": prior_snapshot_commitment_sha256,
        "source_bound": True,
        "complete": True,
        "saturated": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    hits: list[DiscoveryHit] = []
    for docket_id, docket_rows in sorted(
        resolved_by_docket.items(), key=lambda item: int(item[0])
    ):
        docket_rows.sort(key=lambda row: int(cast(str, row["source_candidate_id"])))
        primary_row = docket_rows[0]
        primary_evidence = cast(Mapping[str, object], primary_row["evidence"])
        payload = dict(cast(Mapping[str, object], primary_evidence["payload"]))
        primary_resolution = dict(
            cast(
                Mapping[str, object],
                primary_evidence["opinion_resolution_evidence"],
            )
        )
        additional_resolutions: list[Mapping[str, object]] = []
        for row in docket_rows[1:]:
            row_evidence = cast(Mapping[str, object], row["evidence"])
            row_payload = cast(Mapping[str, object], row_evidence["payload"])
            if any(
                row_payload.get(field) != payload.get(field)
                for field in ("docket_id", "court_id", "docket_number", "case_name")
            ):
                raise OpinionRecapResolutionError(
                    f"resolved opinion leads contradict for RECAP docket {docket_id}"
                )
            additional_resolutions.append(
                cast(
                    Mapping[str, object],
                    row_evidence["opinion_resolution_evidence"],
                )
            )
        primary_resolution["additional_resolutions"] = additional_resolutions
        payload["opinion_resolution_evidence"] = primary_resolution
        hits.append(
            DiscoveryHit(
                provider_hit_id=(
                    f"{OPINION_RECAP_RESOLUTION_TERM}:"
                    f"{primary_row['source_candidate_id']}:{docket_id}"
                ),
                candidate_id=docket_id,
                payload=payload,
            )
        )
    hits.sort(key=lambda hit: int(hit.candidate_id))
    with CycleAcquisitionStore(output_store_path) as store:
        if store.cycle_hash != source.source_cycle_hash:
            raise OpinionRecapResolutionError(
                "resolved output store cycle differs from opinion source cycle"
            )
        store.ensure_batch(output_batch_id, config)
        store.ensure_terms(output_batch_id, (OPINION_RECAP_RESOLUTION_TERM,))
        progress = store.term_progress(output_batch_id, OPINION_RECAP_RESOLUTION_TERM)
        if progress.terminal_status is not None:
            return
        if progress.hit_count:
            raise OpinionRecapResolutionError(
                "resolved output batch has unexpected partial materialization"
            )
        store.commit_search_page(
            output_batch_id,
            OPINION_RECAP_RESOLUTION_TERM,
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )


def _read_opinion_source(
    path: str | Path,
    *,
    source_batch_id: str,
) -> tuple[DirectSearchSeedSource, Mapping[str, Mapping[str, object]]]:
    source_path = Path(path)
    try:
        source = read_saturated_direct_search_leads(
            source_path, source_batch_id=source_batch_id
        )
    except RecapApiBatchDriverError as exc:
        raise OpinionRecapResolutionError(str(exc)) from exc
    connection = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        batch = connection.execute(
            "SELECT config_json FROM batches WHERE batch_id=?", (source_batch_id,)
        ).fetchone()
        if batch is None:
            raise OpinionRecapResolutionError("opinion source batch not found")
        config = cast(dict[str, object], json.loads(batch["config_json"]))
        if (
            config.get("schema_version") != _OPINION_SOURCE_SCHEMA
            or config.get("provider") != "courtlistener"
            or config.get("search_type") != "o"
        ):
            raise OpinionRecapResolutionError(
                "resolver source must be a CourtListener opinion-search batch"
            )
        rows = connection.execute(
            """
            SELECT candidate_id, term, provider_hit_id, payload_json
            FROM discovery_hits WHERE batch_id=?
            ORDER BY candidate_id, term, provider_hit_id
            """,
            (source_batch_id,),
        ).fetchall()
    except (sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        raise OpinionRecapResolutionError(
            f"opinion source is unreadable: {exc}"
        ) from exc
    finally:
        connection.close()
    payloads: dict[str, Mapping[str, object]] = {}
    for row in rows:
        candidate_id = str(row["candidate_id"])
        payload = cast(dict[str, object], json.loads(row["payload_json"]))
        evidence = payload.get("opinion_discovery_evidence")
        if not isinstance(evidence, Mapping):
            raise OpinionRecapResolutionError(
                f"opinion lead {candidate_id} lacks discovery evidence"
            )
        existing = payloads.get(candidate_id)
        if existing is None or _canonical_json(payload) < _canonical_json(existing):
            payloads[candidate_id] = payload
    if set(payloads) != {lead.docket_id for lead in source.leads}:
        raise OpinionRecapResolutionError(
            "opinion source payloads do not reconcile with saturated lead union"
        )
    return source, payloads


def _candidate_from_case_dev(hit: CaseDevDocketHit) -> _ProviderCandidate:
    raw = hit.raw.get("legal_docket")
    if not isinstance(raw, Mapping):
        raise OpinionRecapResolutionError("case.dev mapping hit lacks legal_docket")
    record = cast(Mapping[str, Any], raw)
    return _provider_candidate(record, id_fields=("id",))


def _candidate_from_courtlistener(record: Mapping[str, Any]) -> _ProviderCandidate:
    return _provider_candidate(record, id_fields=("docket_id",))


def _provider_candidate(
    record: Mapping[str, Any], *, id_fields: Sequence[str]
) -> _ProviderCandidate:
    docket_id = _first_text(record, *id_fields)
    if (
        docket_id is None
        or not docket_id.isascii()
        or not docket_id.isdigit()
        or int(docket_id) <= 0
    ):
        raise OpinionRecapResolutionError(
            "resolver provider result lacks a positive numeric RECAP docket ID"
        )
    return _ProviderCandidate(
        docket_id=docket_id,
        court_id=_first_text(record, "court_id", "courtId", "court"),
        docket_number=_first_text(
            record, "docket_number", "docketNumber", "case_number"
        ),
        case_name=_first_text(record, "case_name", "caseName", "caption", "name"),
        raw=dict(record),
    )


def _deduped_candidates(
    candidates: Sequence[_ProviderCandidate],
) -> tuple[_ProviderCandidate, ...]:
    by_id: dict[str, _ProviderCandidate] = {}
    for candidate in candidates:
        existing = by_id.get(candidate.docket_id)
        if existing is not None and _canonical_json(existing.raw) != _canonical_json(
            candidate.raw
        ):
            raise OpinionRecapResolutionError(
                f"provider returned contradictory rows for docket {candidate.docket_id}"
            )
        by_id[candidate.docket_id] = candidate
    return tuple(sorted(by_id.values(), key=lambda item: int(item.docket_id)))


def _normalize_identifier(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def _quoted_case_name_query(case_name: str) -> str:
    if any(unicodedata.category(character).startswith("C") for character in case_name):
        raise _UnrepresentableSourceQuery(
            "opinion lead case name contains a disallowed Unicode category-C character",
            evidence_code="unicode_category_c_character",
        )
    phrase = " ".join(re.sub(r'["\\]+', " ", case_name).split())
    query = f'"{phrase}"'
    if len(phrase) < 2 or len(query) > 500:
        raise _UnrepresentableSourceQuery(
            "opinion lead case name cannot form a valid exact-phrase query",
            evidence_code="query_length_out_of_range",
        )
    return query


def _case_dev_reported_found(payload: Mapping[str, Any]) -> int | None:
    if "found" not in payload:
        return None
    value = payload["found"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OpinionRecapResolutionError(
            "Case.dev resolver found total must be a non-negative integer"
        )
    return value


def _normalize_docket(value: str | None) -> str:
    return _normalize_identifier(value)


def _normalize_case_name(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    ignored = {"llc", "inc", "corp", "corporation", "ltd", "pllc"}
    return " ".join(token for token in tokens if token not in ignored)


def _case_name_similarity(source: str | None, candidate: str | None) -> float:
    left = _normalize_case_name(source)
    right = _normalize_case_name(candidate)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _first_text(record: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _response_commitment(payloads: Sequence[Mapping[str, Any]]) -> str:
    if len(payloads) == 1:
        return _sha256_json(payloads[0])
    return _sha256_json([_sha256_json(payload) for payload in payloads])


def _sha256_json(value: object) -> str:
    return _sha256_text(_canonical_json(value))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

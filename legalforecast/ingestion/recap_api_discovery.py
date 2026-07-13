"""Decision-first CourtListener REST v4 RECAP discovery and docket reconstruction.

Batch-001 discovery searched the CourtListener RECAP *web* UI with motion-first,
free-text queries and reconstructed dockets by scraping docket HTML.  That path
was noisy (majority bankruptcy) and lossy (most enrichment failed).  This module
replaces both halves with the authenticated-or-anonymous REST v4 JSON API:

* discovery runs ``type=rd`` document-index searches whose ``description`` field
  carries frozen *decision-language* boolean queries, anchored to an
  ``entry_date_filed`` window and ordered newest-document-first, walking
  CourtListener cursor pagination; and
* reconstruction fetches the docket record plus every docket entry through the
  cursor-paginated ``docket-entries`` endpoint and rebuilds the exact
  :class:`CourtListenerWebDocketPage` the strict MTD screen consumes, with an
  explicit completeness proof.

Everything here fails closed: a rate limit, a truncated page set, a repeated or
non-advancing cursor, a duplicated docket entry, or a missing required field is
raised, never silently absorbed.  The Firecrawl HTML routes are left intact as an
alternative; this module adds a parallel API route rather than replacing them.

The module never mutates the frozen screening files.  It only *calls*
``screen_courtlistener_docket_for_mtd_decision`` and constructs the
web-docket-page value object that screen already accepts.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerDocket,
    CourtListenerDocketEntry,
    CourtListenerResponseError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
)
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, DiscoveryPage
from legalforecast.ingestion.mtd_acquisition_screen import (
    MtdDocketDecisionScreen,
    MtdDocketScreenStatus,
    courtlistener_case_name_slug,
    screen_courtlistener_docket_for_mtd_decision,
)

# ---------------------------------------------------------------------------
# Frozen decision-first vocabulary (ordered; this order is a versioned input).
# ---------------------------------------------------------------------------

RECAP_API_PROVIDER = "courtlistener-recap-rest-v4"
RECAP_API_POLICY_SCHEMA = "legalforecast.recap_api_discovery_batch.v1"

# The ``description`` field of a ``type=rd`` search carries the docket-entry text.
# These queries target the *decision* itself (order granting/denying, memorandum
# opinion, report & recommendation) rather than the motion filing, so the pool is
# dominated by actual dispositions instead of dockets that merely mention a
# motion.  Additions or reordering require an intentional code change and a fresh
# batch config digest.
DECISION_FIRST_RECAP_API_SEARCH_TERMS: tuple[str, ...] = (
    'order AND granting AND "motion to dismiss"',
    'order AND denying AND "motion to dismiss"',
    '"motion to dismiss" AND "granted in part"',
    '"order on motion to dismiss"',
    '"memorandum opinion" AND "motion to dismiss"',
    '"report and recommendation" AND "motion to dismiss"',
    'order AND (granting OR denying) AND "judgment on the pleadings"',
    'order AND (granting OR denying) AND "12(b)(6)"',
)

_ANONYMOUS_MIN_INTERVAL_SECONDS = 3.0
_DEFAULT_PAGE_SIZE = 100
_CANDIDATE_PREFIX = "courtlistener-docket-"
_CRIMINAL_DOCKET_TOKEN = re.compile(r"-cr-", re.IGNORECASE)
_CRIMINAL_SLUG_PREFIXES = ("usa-v-", "united-states-v-")

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class RecapApiDiscoveryError(RuntimeError):
    """Base class for decision-first RECAP API discovery failures."""


class RecapApiResponseError(RecapApiDiscoveryError):
    """Raised when a CourtListener search result is missing required fields."""


class RecapDocketReconstructionError(RecapApiDiscoveryError):
    """Raised when a docket cannot be proven completely reconstructed."""


# ---------------------------------------------------------------------------
# Request pacing (conservative anonymous spacing; auth-mode aware).
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RequestPacer:
    """Enforce a minimum wall-clock spacing between metered wire requests.

    Anonymous CourtListener access is rate limited, so the default spacing for an
    unauthenticated caller is conservative.  ``clock``/``sleep`` are injectable so
    the pacing contract is unit-testable without real time.
    """

    min_interval_seconds: float = _ANONYMOUS_MIN_INTERVAL_SECONDS
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last_request_at: float | None = field(default=None, init=False, repr=False)

    def wait(self) -> None:
        if self.min_interval_seconds <= 0:
            self._last_request_at = self.clock()
            return
        now = self.clock()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                self.sleep(remaining)
                now = self.clock()
        self._last_request_at = now


def resolve_auth_mode(client: CourtListenerClient) -> str:
    """Return ``authenticated`` when a token is configured, else ``anonymous``."""

    return "authenticated" if client.config.api_token else "anonymous"


def pacer_for_client(
    client: CourtListenerClient,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> RequestPacer:
    """Build a pacer whose spacing matches the client's authentication mode."""

    interval = 0.0 if client.config.api_token else _ANONYMOUS_MIN_INTERVAL_SECONDS
    return RequestPacer(min_interval_seconds=interval, clock=clock, sleep=sleep)


# ---------------------------------------------------------------------------
# Batch-002 configuration.
# ---------------------------------------------------------------------------


def build_recap_api_batch_config(
    *,
    decision_window_start: date,
    decision_window_end: date,
    auth_mode: str,
    query_terms: Sequence[str] = DECISION_FIRST_RECAP_API_SEARCH_TERMS,
    page_size: int = _DEFAULT_PAGE_SIZE,
    top_k_per_term: int = 5_000,
) -> dict[str, object]:
    """Return the canonical, resumable batch-002 discovery configuration.

    The digest deliberately differs from batch-001: a different provider and a
    frozen *decision-first* term list.  ``ensure_batch`` freezes this mapping, so
    a resumed run with any changed field fails closed rather than mixing configs.
    """

    if isinstance(decision_window_start, datetime) or isinstance(
        decision_window_end, datetime
    ):
        raise TypeError("decision window bounds must be dates, not datetimes")
    if decision_window_start > decision_window_end:
        raise ValueError("decision_window_start must be on or before the end")
    if auth_mode not in {"authenticated", "anonymous"}:
        raise ValueError("auth_mode must be 'authenticated' or 'anonymous'")
    terms = _validated_terms(query_terms)
    if page_size <= 0 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")
    if top_k_per_term <= 0:
        raise ValueError("top_k_per_term must be positive")
    return {
        "schema_version": RECAP_API_POLICY_SCHEMA,
        "provider": RECAP_API_PROVIDER,
        "search_type": "rd",
        "query_field": "description",
        "order_by": "entry_date_filed desc",
        "query_terms": list(terms),
        "query_term_order_is_frozen": True,
        "decision_window_start": decision_window_start.isoformat(),
        "decision_window_end": decision_window_end.isoformat(),
        "page_size": page_size,
        "top_k_per_term": top_k_per_term,
        "auth_mode": auth_mode,
    }


# ---------------------------------------------------------------------------
# Cheap pre-screen (before any docket fetch).
# ---------------------------------------------------------------------------

# These map onto the store's *immutable* reason codes so a pre-screened
# exclusion is never silently reconsidered by a later observation.
PRESCREEN_BANKRUPTCY_REASON = "bankruptcy_court"
PRESCREEN_CRIMINAL_REASON = "criminal_case"


def prescreen_recap_candidate(
    *,
    court_id: str | None,
    docket_number: str | None,
    case_name: str | None,
) -> str | None:
    """Return an immutable exclusion reason for cheaply-excludable dockets.

    Bankruptcy court ids end in ``b`` (for example ``nysb``); criminal dockets
    carry a ``-cr-`` number token or a ``United States v.`` caption.  Excluding
    these before any docket fetch keeps the API budget on eligible civil cases.
    """

    if court_id is not None and court_id.strip().lower().endswith("b"):
        return PRESCREEN_BANKRUPTCY_REASON
    if docket_number is not None and _CRIMINAL_DOCKET_TOKEN.search(docket_number):
        return PRESCREEN_CRIMINAL_REASON
    if case_name is not None and case_name.strip():
        slug = courtlistener_case_name_slug(case_name)
        if any(slug.startswith(prefix) for prefix in _CRIMINAL_SLUG_PREFIXES):
            return PRESCREEN_CRIMINAL_REASON
    return None


# ---------------------------------------------------------------------------
# Discovery hit parsing.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecapDecisionHit:
    """One decision-language RECAP document hit from a ``type=rd`` search."""

    recap_document_id: str
    docket_id: str
    docket_entry_id: str | None
    entry_number: str | None
    document_number: str | None
    description: str | None
    entry_date_filed: str | None
    court_id: str | None
    docket_number: str | None
    case_name: str | None
    source_url: str | None

    @property
    def candidate_id(self) -> str:
        return f"{_CANDIDATE_PREFIX}{self.docket_id}"

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RecapDecisionHit:
        recap_document_id = _optional_string(record, "id", "recap_document_id")
        docket_id = _optional_string(record, "docket_id", "docketId", "docket")
        if docket_id is None:
            raise RecapApiResponseError(
                "RECAP document search hit is missing docket_id"
            )
        if recap_document_id is None:
            # A stable within-page identity is required to commit and dedupe.
            raise RecapApiResponseError(
                f"RECAP document search hit for docket {docket_id} is missing id"
            )
        return cls(
            recap_document_id=recap_document_id,
            docket_id=docket_id,
            docket_entry_id=_optional_string(
                record, "docket_entry_id", "docketEntryId"
            ),
            entry_number=_optional_string(record, "entry_number", "entryNumber"),
            document_number=_optional_string(
                record, "document_number", "documentNumber"
            ),
            description=_optional_string(
                record, "description", "short_description", "snippet"
            ),
            entry_date_filed=_optional_string(
                record, "entry_date_filed", "dateFiled", "date_filed"
            ),
            court_id=_court_identifier(record),
            docket_number=_optional_string(record, "docketNumber", "docket_number"),
            case_name=_optional_string(record, "caseName", "case_name", "caption"),
            source_url=_optional_string(record, "absolute_url", "url"),
        )

    def candidate_payload(self, *, query_term: str, auth_mode: str) -> dict[str, Any]:
        """Docket-level candidate payload with triggering decision-entry evidence.

        The evidence block is what a later motion-linkage / MTD screen uses to
        tie a candidate back to the exact decision entry that surfaced it.
        """

        prescreen_reason = prescreen_recap_candidate(
            court_id=self.court_id,
            docket_number=self.docket_number,
            case_name=self.case_name,
        )
        return {
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "courtlistener_docket_id": self.docket_id,
            "courtlistener_url": self.source_url,
            "court_id": self.court_id,
            "docket_number": self.docket_number,
            "case_name": self.case_name,
            "provider": RECAP_API_PROVIDER,
            "auth_mode": auth_mode,
            "query_term": query_term,
            "prescreen_exclusion_reason": prescreen_reason,
            "decision_entry_evidence": {
                "recap_document_id": self.recap_document_id,
                "docket_entry_id": self.docket_entry_id,
                "entry_number": self.entry_number,
                "document_number": self.document_number,
                "description": self.description,
                "entry_date_filed": self.entry_date_filed,
            },
        }


@dataclass(frozen=True, slots=True)
class RecapApiDiscoverySource:
    """Expose decision-first ``type=rd`` search pages to the shared scheduler.

    The scheduler + cycle-acquisition store own resume/checkpoint semantics; this
    adapter only turns one cursor page into :class:`DiscoveryHit` values and a
    continuation cursor.  Docket-level dedupe happens in the store because every
    hit for a docket shares one ``courtlistener-docket-<id>`` candidate id.
    """

    client: CourtListenerClient
    entry_date_filed_after: date
    entry_date_filed_before: date | None = None
    pacer: RequestPacer | None = None
    auth_mode: str | None = None

    def _resolved_auth_mode(self) -> str:
        return self.auth_mode or resolve_auth_mode(self.client)

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        if self.pacer is not None:
            self.pacer.wait()
        params: dict[str, Any] = {
            "type": "rd",
            "description": term,
            "entry_date_filed_after": self.entry_date_filed_after.isoformat(),
            "order_by": "entry_date_filed desc",
            "page_size": page_size,
        }
        if self.entry_date_filed_before is not None:
            params["entry_date_filed_before"] = self.entry_date_filed_before.isoformat()
        page = self.client.search_raw(params, cursor=cursor)
        auth_mode = self._resolved_auth_mode()
        hits: list[DiscoveryHit] = []
        for record in page.items:
            hit = RecapDecisionHit.from_record(record)
            hits.append(
                DiscoveryHit(
                    provider_hit_id=hit.recap_document_id,
                    candidate_id=hit.candidate_id,
                    payload=hit.candidate_payload(query_term=term, auth_mode=auth_mode),
                )
            )
        # A missing continuation cursor is CourtListener's exhaustion signal for
        # cursor-paginated search, so the term is provably saturated.
        return DiscoveryPage(
            hits=tuple(hits),
            next_cursor=page.next_cursor,
            exhausted=True if page.next_cursor is None else None,
        )


# ---------------------------------------------------------------------------
# API docket reconstruction with an explicit completeness proof.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecapReconstructionProof:
    """Auditable evidence that a docket was completely reconstructed."""

    docket_id: str
    pages_fetched: int
    entry_count: int
    cursor_exhausted: bool
    duplicate_entry_ids: tuple[str, ...]
    entry_numbers_monotonic: bool

    @property
    def complete(self) -> bool:
        return (
            self.cursor_exhausted
            and not self.duplicate_entry_ids
            and self.entry_numbers_monotonic
        )

    def to_record(self) -> dict[str, object]:
        return {
            "docket_id": self.docket_id,
            "pages_fetched": self.pages_fetched,
            "entry_count": self.entry_count,
            "cursor_exhausted": self.cursor_exhausted,
            "duplicate_entry_ids": list(self.duplicate_entry_ids),
            "entry_numbers_monotonic": self.entry_numbers_monotonic,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class ReconstructedDocket:
    """A completely reconstructed docket ready for the strict MTD screen."""

    docket: CourtListenerDocket
    page: CourtListenerWebDocketPage
    proof: RecapReconstructionProof


def reconstruct_docket_page(
    client: CourtListenerClient,
    docket_id: str,
    *,
    pacer: RequestPacer | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> ReconstructedDocket:
    """Rebuild the strict-screen docket page from the REST v4 API, fail-closed.

    Fetches the docket record and walks every ``docket-entries`` cursor page.
    Reconstruction is rejected unless the cursor is exhausted, no docket entry id
    repeats across pages (the pagination-duplicate invariant), and the observed
    entry numbers are monotonically non-decreasing.
    """

    if not docket_id.strip():
        raise ValueError("docket_id is required")
    if pacer is not None:
        pacer.wait()
    docket = client.get_docket(docket_id)

    entries: list[CourtListenerDocketEntry] = []
    seen_entry_ids: set[str] = set()
    duplicate_entry_ids: list[str] = []
    seen_cursors: set[str] = set()
    cursor: str | None = None
    pages_fetched = 0
    while True:
        if pacer is not None:
            pacer.wait()
        result = client.list_docket_entries(
            docket_id, cursor=cursor, page_size=page_size
        )
        pages_fetched += 1
        for entry in result.items:
            if entry.docket_id != docket_id:
                raise RecapDocketReconstructionError(
                    f"docket {docket_id} returned an entry for docket {entry.docket_id}"
                )
            if entry.docket_entry_id in seen_entry_ids:
                duplicate_entry_ids.append(entry.docket_entry_id)
            else:
                seen_entry_ids.add(entry.docket_entry_id)
            entries.append(entry)
        next_cursor = result.next_cursor
        if next_cursor is None:
            break
        if next_cursor in seen_cursors or next_cursor == cursor:
            raise RecapDocketReconstructionError(
                f"docket {docket_id} pagination cursor did not advance"
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    proof = RecapReconstructionProof(
        docket_id=docket_id,
        pages_fetched=pages_fetched,
        entry_count=len(entries),
        cursor_exhausted=True,
        duplicate_entry_ids=tuple(sorted(set(duplicate_entry_ids))),
        entry_numbers_monotonic=_entry_numbers_monotonic(entries),
    )
    if duplicate_entry_ids:
        raise RecapDocketReconstructionError(
            f"docket {docket_id} returned duplicate docket entries across pages: "
            + ", ".join(proof.duplicate_entry_ids)
        )
    if not proof.entry_numbers_monotonic:
        raise RecapDocketReconstructionError(
            f"docket {docket_id} docket entries are not in a monotonic sequence"
        )

    page = CourtListenerWebDocketPage(
        docket_id=docket_id,
        source_url=docket.source_url,
        title=docket.case_name,
        entries=tuple(_web_entry_from_api(entry) for entry in entries),
        # Every entry has been fetched, so the reconstructed page is single-page
        # by construction; the screen rejects multi-page HTML scrapes, and this
        # API route is exhaustive rather than truncated.
        has_next_page=False,
    )
    return ReconstructedDocket(docket=docket, page=page, proof=proof)


def _web_entry_from_api(
    entry: CourtListenerDocketEntry,
) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=(
            f"entry-{entry.entry_number}"
            if entry.entry_number is not None
            else f"minute-entry-{entry.docket_entry_id}"
        ),
        entry_number=entry.entry_number,
        # The strict screen's date parser expects a long "Month DD, YYYY" string
        # (it was built for scraped HTML), so an ISO API date is rendered into
        # that form; an unparseable date is passed through untouched and simply
        # fails the screen's date-window test, which is the safe direction.
        filed_at=_long_us_date(entry.filed_at),
        text=entry.entry_text,
        documents=(),
    )


def _entry_numbers_monotonic(entries: Sequence[CourtListenerDocketEntry]) -> bool:
    previous: int | None = None
    for entry in entries:
        if entry.entry_number is None:
            continue
        try:
            current = int(entry.entry_number)
        except ValueError:
            # Non-numeric entry numbers cannot be range-checked; ignore them
            # rather than assert a false ordering.
            continue
        if previous is not None and current < previous:
            return False
        previous = current
    return True


def _long_us_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    match = re.match(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", raw.strip())
    if match is None:
        return raw
    month_index = int(match.group("month"))
    if not 1 <= month_index <= 12:
        return raw
    return (
        f"{_MONTHS[month_index - 1]} {int(match.group('day'))}, {match.group('year')}"
    )


# ---------------------------------------------------------------------------
# Shared field helpers.
# ---------------------------------------------------------------------------


def _validated_terms(terms: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(terms)
    if not normalized:
        raise ValueError("at least one decision-first search term is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("decision-first search terms must be unique")
    for term in normalized:
        if not term.strip():
            raise ValueError("decision-first search terms must be non-empty")
    return normalized


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _court_identifier(record: Mapping[str, Any]) -> str | None:
    value = _optional_string(record, "court_id", "courtId", "court")
    if value is None:
        return None
    match = re.search(r"/courts/([^/]+)/?$", value)
    if match is not None:
        return match.group(1)
    return value


def observe_prescreened_reason(payload: Mapping[str, Any]) -> str | None:
    """Return the stored pre-screen exclusion reason for a candidate payload."""

    reason = payload.get("prescreen_exclusion_reason")
    if reason is None:
        return None
    if not isinstance(reason, str) or not reason.strip():
        raise RecapApiResponseError(
            "candidate prescreen_exclusion_reason must be a non-empty string"
        )
    return reason


def candidate_docket_id(payload: Mapping[str, Any]) -> str:
    """Extract the CourtListener docket id from a candidate payload."""

    value = payload.get("docket_id") or payload.get("courtlistener_docket_id")
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    candidate_id = payload.get("candidate_id")
    if isinstance(candidate_id, str) and candidate_id.startswith(_CANDIDATE_PREFIX):
        return candidate_id[len(_CANDIDATE_PREFIX) :]
    raise RecapApiResponseError("candidate payload is missing a docket id")


# ---------------------------------------------------------------------------
# Observation orchestration: reconstruct -> strict screen -> store.
#
# This ties the discovery candidate to the durable observation store using only
# the *unmodified* strict screen. Screen outcomes and the first-disposition
# anchor are mapped onto the store's fixed reason-code taxonomy.
# ---------------------------------------------------------------------------

# Strict posture exclusions the screen already emits as store-compatible codes.
_POSTURE_REASON_CODES = frozenset(
    {
        "habeas_or_immigration_detention_posture",
        "bankruptcy_posture",
        "criminal_posture",
    }
)


def observe_recap_api_candidate(
    store: CycleAcquisitionStore,
    batch_id: str,
    payload: Mapping[str, Any],
    *,
    client: CourtListenerClient,
    eligibility_anchor: date,
    pacer: RequestPacer | None = None,
) -> CandidateObservation:
    """Reconstruct, screen, and durably observe one discovered candidate.

    A pre-screened candidate is excluded immutably without any docket fetch. All
    others are reconstructed and run through the strict screen; the screen's
    outcome (and whether the *first* MTD disposition predates the anchor) is
    mapped onto the store's reason-code taxonomy. Rate-limit and server errors
    are deliberately *not* caught so the surrounding pass fails closed; only a
    genuinely absent docket or an unparseable/incomplete reconstruction is
    recorded as a transient observation.
    """

    docket_id = candidate_docket_id(payload)
    candidate_id = f"{_CANDIDATE_PREFIX}{docket_id}"
    base_evidence: dict[str, object] = {
        "candidate_id": candidate_id,
        "docket_id": docket_id,
        "provider": RECAP_API_PROVIDER,
    }
    if "decision_entry_evidence" in payload:
        base_evidence["decision_entry_evidence"] = payload["decision_entry_evidence"]

    prescreen = observe_prescreened_reason(payload)
    if prescreen is not None:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code=prescreen,
            evidence={**base_evidence, "prescreen_exclusion_reason": prescreen},
        )

    try:
        reconstructed = reconstruct_docket_page(client, docket_id, pacer=pacer)
    except CourtListenerUnavailableError as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code="courtlistener_docket_unavailable",
            evidence={**base_evidence, "error": str(error)},
        )
    except (CourtListenerResponseError, RecapDocketReconstructionError) as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code="parse_failure",
            evidence={**base_evidence, "error": str(error)},
        )

    anchored = screen_courtlistener_docket_for_mtd_decision(
        reconstructed.page, decision_filed_on_or_after=eligibility_anchor
    )
    unbounded = screen_courtlistener_docket_for_mtd_decision(reconstructed.page)
    state, reason_code = _map_screen_outcome(
        anchored=anchored,
        unbounded=unbounded,
        eligibility_anchor=eligibility_anchor,
    )
    evidence = {
        **base_evidence,
        "screen": anchored.to_record(),
        "reconstruction_proof": reconstructed.proof.to_record(),
    }
    return store.record_observation(
        candidate_id,
        batch_id=batch_id,
        state=state,
        reason_code=reason_code,
        evidence=evidence,
    )


def _map_screen_outcome(
    *,
    anchored: MtdDocketDecisionScreen,
    unbounded: MtdDocketDecisionScreen,
    eligibility_anchor: date,
) -> tuple[str, str]:
    earliest = _earliest_decision_date(unbounded)
    if earliest is not None and earliest < eligibility_anchor:
        # The first written MTD disposition predates the eligibility anchor, so
        # the case is permanently ineligible regardless of later dispositions.
        return "excluded", "decision_before_release_anchor"
    if anchored.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION:
        return "accepted", "strict_clean_screen_passed"
    if anchored.status is MtdDocketScreenStatus.ACTUAL_MTD_DECISION_REVIEW_OR_EXCLUDED:
        for reason in anchored.exclusion_reasons:
            if reason in _POSTURE_REASON_CODES:
                return "excluded", reason
        return "excluded", "strict_clean_screen_failed"
    return "excluded", "strict_clean_screen_failed"


def _earliest_decision_date(screen: MtdDocketDecisionScreen) -> date | None:
    earliest: date | None = None
    for entry in screen.decision_entries:
        parsed = _parse_long_us_date(entry.filed_at)
        if parsed is None:
            continue
        if earliest is None or parsed < earliest:
            earliest = parsed
    return earliest


_LONG_US_DATE = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})"
)
_MONTH_INDEX = {name.lower(): index for index, name in enumerate(_MONTHS, start=1)}


def _parse_long_us_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    match = _LONG_US_DATE.match(raw.strip())
    if match is None:
        return None
    month = _MONTH_INDEX.get(match.group("month").lower())
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None

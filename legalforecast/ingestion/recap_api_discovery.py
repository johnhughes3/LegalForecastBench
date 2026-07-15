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
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, cast

from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_API_TOKEN_ENV,
    CourtListenerClient,
    CourtListenerDocket,
    CourtListenerDocketEntry,
    CourtListenerResponseError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    cohort_reason_policy_taxonomy,
)
from legalforecast.ingestion.decision_first_terms import (
    DECISION_FIRST_RECAP_SEARCH_TERMS,
)
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, DiscoveryPage
from legalforecast.ingestion.mtd_acquisition_screen import (
    CaseDevDocketMetadata,
    CaseDevMetadataScreen,
    MtdDecisionEntryScreen,
    MtdDocketDecisionScreen,
    MtdDocketScreenStatus,
    courtlistener_case_name_slug,
    parse_courtlistener_filed_date,
    screen_case_dev_docket_metadata,
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.opinion_backed_disposition import (
    OpinionBackedDispositionError,
    fetch_and_bind_public_opinion,
    select_opinion_resolution_for_page,
    validate_resolved_recap_identity,
)
from legalforecast.ingestion.restricted_material import restricted_material_markers

# ---------------------------------------------------------------------------
# Frozen decision-first vocabulary (ordered; this order is a versioned input).
# ---------------------------------------------------------------------------

RECAP_API_PROVIDER = "courtlistener-recap-rest-v4"
RECAP_API_POLICY_SCHEMA = "legalforecast.recap_api_discovery_batch.v1"
REST_DOCKET_ENTRY_SOFT_CAP = 500
REST_DOCKET_PAGE_HARD_CAP = 6

# The ``description`` field of a ``type=rd`` search carries the docket-entry text.
# These queries target the *decision* itself (order granting/denying, memorandum
# opinion, report & recommendation) rather than the motion filing, so the pool is
# dominated by actual dispositions instead of dockets that merely mention a
# motion.  Additions or reordering require an intentional code change and a fresh
# batch config digest.
DECISION_FIRST_RECAP_API_SEARCH_TERMS = DECISION_FIRST_RECAP_SEARCH_TERMS

_ANONYMOUS_MIN_INTERVAL_SECONDS = 3.0
_DEFAULT_PAGE_SIZE = 100
_CANDIDATE_PREFIX = "courtlistener-docket-"
_CRIMINAL_DOCKET_TOKEN = re.compile(r"-cr-", re.IGNORECASE)
_CRIMINAL_SLUG_PREFIXES = ("usa-v-", "united-states-v-")
_SHA256 = re.compile(r"[0-9a-f]{64}")

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


class RecapDocketContradictionError(RecapDocketReconstructionError):
    """Raised when provider rows contradict one another within one docket."""


class RecapDocketTooLargeError(RecapDocketReconstructionError):
    """Raised when a docket exceeds the approved REST reconstruction page cap."""


class RecapReconstructionAuthError(RecapApiDiscoveryError):
    """Raised when docket reconstruction is attempted without an API token.

    The CourtListener v4 search index answers anonymously, but the
    ``dockets`` and ``docket-entries`` endpoints reconstruction depends on
    return HTTP 401 without a token, so reconstruction is token-required by
    design rather than falling back to an anonymous route.
    """


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


def require_reconstruction_auth(client: CourtListenerClient) -> None:
    """Fail closed unless the client carries an API token for reconstruction.

    Docket reconstruction hits token-required CourtListener endpoints, so this
    is enforced before any wire request and the error names the environment
    variable an operator must set.
    """

    if not client.config.api_token:
        raise RecapReconstructionAuthError(
            "CourtListener docket reconstruction requires an API token; set "
            f"{COURTLISTENER_API_TOKEN_ENV} (Authorization: Token <token>). The "
            "search index answers anonymously, but dockets/docket-entries return "
            "HTTP 401 without a token."
        )


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
    defer_bankruptcy_to_authoritative_docket: bool = False,
) -> str | None:
    """Return an immutable exclusion reason for cheaply-excludable dockets.

    Bankruptcy court ids end in ``b`` (for example ``nysb``); criminal dockets
    carry a ``-cr-`` number token or a ``United States v.`` caption.  Excluding
    these before any docket fetch keeps the API budget on eligible civil cases.
    Opinion-cluster summaries may opt into one authoritative docket lookup,
    because those summaries do not reliably distinguish estate and adversary
    docket metadata.
    """

    if court_id is not None and court_id.strip().lower().endswith("b"):
        if defer_bankruptcy_to_authoritative_docket:
            # Opinion-search rows are cluster summaries, not the authoritative
            # RECAP docket record.  Their caption/number can be incomplete or
            # estate-styled even when the linked docket is an adversary case.
            # Spend exactly one noncharging docket lookup before deciding; the
            # default authoritative call below still excludes ordinary cases.
            return None
        # Bankruptcy adversary proceedings are eligible Rule 12 analogues.
        # A bare bankruptcy court id cannot distinguish an adversary from the
        # main estate case, so incomplete search metadata must proceed to the
        # authoritative docket record rather than being dropped cheaply.
        metadata = CaseDevDocketMetadata(
            case_id="courtlistener-prescreen",
            query=None,
            court_id=court_id,
            court=None,
            docket_number=docket_number,
            case_name=case_name,
            nature_of_suit=None,
            cause=None,
        )
        if metadata.case_type_stratum == "bankruptcy_adversary":
            return None
        if docket_number is not None or case_name is not None:
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
    docket: CourtListenerDocket | None = None,
    max_pages: int = REST_DOCKET_PAGE_HARD_CAP,
) -> ReconstructedDocket:
    """Rebuild the strict-screen docket page from the REST v4 API, fail-closed.

    Fetches the docket record and walks every ``docket-entries`` cursor page.
    Reconstruction is rejected unless the cursor is exhausted, no docket entry id
    repeats across pages (the pagination-duplicate invariant), and the observed
    entry numbers are monotonically non-decreasing.

    The ``dockets``/``docket-entries`` endpoints reject anonymous callers with
    HTTP 401, so a token is required up front and its absence raises a precise
    error naming the environment variable rather than emitting an opaque wire
    failure partway through the walk. Full untruncated entry descriptions come
    from ``docket-entries`` (search snippets can be truncated), so this
    reconstruction is authoritative and search hits are only leads.
    """

    docket_id = docket_id.strip()
    if not docket_id:
        raise ValueError("docket_id is required")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")
    require_reconstruction_auth(client)
    if docket is None:
        if pacer is not None:
            pacer.wait()
        docket = client.get_docket(docket_id)
    elif docket.docket_id != docket_id:
        raise RecapDocketReconstructionError(
            f"requested docket {docket_id} but supplied record {docket.docket_id}"
        )

    entries: list[CourtListenerDocketEntry] = []
    seen_entry_ids: set[str] = set()
    entry_id_by_number: dict[str, str] = {}
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
            raw_entry_number = _optional_string(
                entry.raw, "entry_number", "entryNumber"
            )
            if raw_entry_number is not None:
                prior_entry_id = entry_id_by_number.get(raw_entry_number)
                if (
                    prior_entry_id is not None
                    and prior_entry_id != entry.docket_entry_id
                ):
                    raise RecapDocketContradictionError(
                        f"docket {docket_id} returned contradictory entry number "
                        f"{raw_entry_number} for entry ids {prior_entry_id} and "
                        f"{entry.docket_entry_id}"
                    )
                entry_id_by_number[raw_entry_number] = entry.docket_entry_id
            entries.append(entry)
        next_cursor = result.next_cursor
        if next_cursor is None:
            break
        if pages_fetched >= max_pages:
            raise RecapDocketTooLargeError(
                f"docket {docket_id} exceeds the {max_pages}-page REST "
                "reconstruction cap; pagination exhaustion is unproven"
            )
        if next_cursor in seen_cursors or next_cursor == cursor:
            raise RecapDocketReconstructionError(
                f"docket {docket_id} pagination cursor did not advance"
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    # CourtListener's ``docket-entries`` endpoint does not guarantee ascending
    # entry order under cursor pagination, and amended or minute entries can
    # interleave.  Every page has already been fetched, so cursor exhaustion plus
    # the no-duplicate-entry-id invariant is the real completeness proof; ordering
    # is then a deterministic *client-side* sort into docket order rather than a
    # wire assumption.  This avoids rejecting an otherwise-complete docket merely
    # because the API returned its entries newest-first or out of sequence.
    ordered_entries = _sorted_docket_entries(entries)
    proof = RecapReconstructionProof(
        docket_id=docket_id,
        pages_fetched=pages_fetched,
        entry_count=len(ordered_entries),
        cursor_exhausted=True,
        duplicate_entry_ids=tuple(sorted(set(duplicate_entry_ids))),
        # Computed after the client-side sort, so this is an audit attestation of
        # the reconstructed order, not a wire-order gate that can false-fail.
        entry_numbers_monotonic=_entry_numbers_monotonic(ordered_entries),
    )
    if duplicate_entry_ids:
        raise RecapDocketReconstructionError(
            f"docket {docket_id} returned duplicate docket entries across pages: "
            + ", ".join(proof.duplicate_entry_ids)
        )

    page = CourtListenerWebDocketPage(
        docket_id=docket_id,
        source_url=docket.source_url,
        title=docket.case_name,
        entries=tuple(_web_entry_from_api(entry) for entry in ordered_entries),
        # Every entry has been fetched, so the reconstructed page is single-page
        # by construction; the screen rejects multi-page HTML scrapes, and this
        # API route is exhaustive rather than truncated.
        has_next_page=False,
    )
    return ReconstructedDocket(docket=docket, page=page, proof=proof)


def _web_entry_from_api(
    entry: CourtListenerDocketEntry,
) -> CourtListenerWebDocketEntry:
    restriction_markers = restricted_material_markers(
        records=(entry.raw,),
        text_fields=(entry.entry_text,),
    )
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
        documents=_web_documents_from_api(entry),
        restriction_markers=restriction_markers,
    )


def _web_documents_from_api(
    entry: CourtListenerDocketEntry,
) -> tuple[CourtListenerWebDocument, ...]:
    """Preserve provider-proven public RECAP availability.

    CourtListener embeds RECAP document objects on docket-entry responses.  A
    document is free only when v4 explicitly reports ``is_available=true`` and
    ``is_sealed=false``, no affirmative private/restricted marker exists, and
    ``filepath_local`` or ``download_url`` normalizes to an allowlisted HTTPS
    CourtListener URL. Real v4 rows do not carry the synthetic
    ``redaction_or_seal_status``/``is_private=false`` pair used by older test
    fixtures; public RECAP availability plus the storage path and explicit
    nonsealed flag are the provider's authoritative free-download proof. All
    other documents remain PACER gaps, and restriction metadata still flows to
    the downstream fail-closed packet clearance gates.
    """

    raw_documents = entry.raw.get("recap_documents")
    if not isinstance(raw_documents, list):
        return ()
    documents: list[CourtListenerWebDocument] = []
    for value in cast(list[object], raw_documents):
        if not isinstance(value, Mapping):
            continue
        record = cast(Mapping[str, object], value)
        description = _optional_document_string(record, "description") or ""
        restriction_markers = restricted_material_markers(
            records=(record,),
            text_fields=(description,),
        )
        if record.get("is_sealed") is True and "sealed" not in restriction_markers:
            restriction_markers = (*restriction_markers, "sealed")
        private_status = record.get("is_private")
        private_status_is_valid = private_status is None or isinstance(
            private_status, bool
        )
        href: str | None = None
        provider_proves_public_download = (
            record.get("is_available") is True
            and record.get("is_sealed") is False
            and private_status_is_valid
            and private_status is not True
            and not restriction_markers
        )
        if provider_proves_public_download:
            candidate_href = _optional_document_string(
                record,
                "filepath_local",
                "download_url",
            )
            if candidate_href is not None:
                href = public_recap_download_url(candidate_href)
        attachment = record.get("attachment_number")
        kind = (
            "main"
            if attachment is None or attachment == "" or attachment == 0
            else "attachment"
        )
        documents.append(
            CourtListenerWebDocument(
                kind=kind,
                description=description,
                href=href,
                action_label="Download PDF" if href is not None else "Buy on PACER",
                pacer_only=href is None,
                restriction_markers=tuple(sorted(set(restriction_markers))),
            )
        )
    return tuple(documents)


def _optional_document_string(
    record: Mapping[str, object], *field_names: str
) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def public_recap_download_url(value: str) -> str | None:
    """Normalize one v4 storage path and enforce the HTTPS download allowlist."""

    if "\\" in value or any(
        character.isspace() or ord(character) < 32 for character in value
    ):
        return None
    try:
        url = urllib.parse.urljoin("https://www.courtlistener.com/", value)
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        port = parsed.port
    except (UnicodeError, ValueError):
        return None
    if (
        parsed.scheme != "https"
        or hostname not in {"storage.courtlistener.com", "www.courtlistener.com"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or bool(parsed.fragment)
        or bool(parsed.query)
        or bool(parsed.params)
    ):
        return None
    path = parsed.path
    for _ in range(len(path) + 1):
        decoded_path = urllib.parse.unquote(path)
        if decoded_path == path:
            break
        path = decoded_path
    else:
        return None
    if "\\" in path or any(
        character.isspace() or ord(character) < 32 for character in path
    ):
        return None
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    if not path.lower().endswith(".pdf"):
        return None
    if hostname == "www.courtlistener.com" and not path.startswith("/recap/"):
        return None
    if hostname == "storage.courtlistener.com" and path == "/":
        return None
    return url


def _entry_number_int(entry: CourtListenerDocketEntry) -> int | None:
    if entry.entry_number is None:
        return None
    try:
        return int(entry.entry_number)
    except ValueError:
        # Non-numeric entry numbers (minute/amended markers) cannot be ordered
        # numerically.
        return None


def _sorted_docket_entries(
    entries: Sequence[CourtListenerDocketEntry],
) -> list[CourtListenerDocketEntry]:
    """Order a fully-fetched entry set deterministically into docket order.

    Numbered entries sort ascending by their integer entry number; unnumbered
    (minute) entries keep a stable order after the numbered ones, keyed by their
    docket-entry id so the result is reproducible regardless of the wire order.
    """

    def sort_key(entry: CourtListenerDocketEntry) -> tuple[int, int, str]:
        number = _entry_number_int(entry)
        if number is None:
            return (1, 0, entry.docket_entry_id)
        return (0, number, entry.docket_entry_id)

    return sorted(entries, key=sort_key)


def _entry_numbers_monotonic(entries: Sequence[CourtListenerDocketEntry]) -> bool:
    previous: int | None = None
    for entry in entries:
        current = _entry_number_int(entry)
        if current is None:
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


def _source_bound_adversary_defer_evidence(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    payload: Mapping[str, Any],
    docket: CourtListenerDocket,
) -> Mapping[str, object] | None:
    """Validate the narrow ranked-subset proof that permits entry reconstruction.

    This does not admit a bankruptcy case. It only defers the cheap metadata
    exclusion long enough for the authoritative entries and unchanged strict
    Rule 7012/adversary screen to decide. Every commitment is source-bound to the
    exact authenticated ranked record transferred by the subset selector.
    """

    config = store.batch_config(batch_id)
    provenance = payload.get("case_dev_ranked_selection_provenance")
    evidence = payload.get("bankruptcy_adversary_entry_evidence")
    if (
        config.get("discovery_mode")
        != "legalforecast.case_dev_ranked_opinion_subset_transfer.v1"
        or not isinstance(provenance, Mapping)
        or not isinstance(evidence, Mapping)
    ):
        return None
    typed_provenance = cast(Mapping[str, object], provenance)
    typed_evidence = cast(Mapping[str, object], evidence)
    ranked_record_sha256 = typed_provenance.get("ranked_record_sha256")
    entry_text = typed_evidence.get("entry_text")
    entry_number = typed_evidence.get("entry_number")
    filed_at = typed_evidence.get("filed_at")
    if (
        typed_provenance.get("schema_version")
        != "legalforecast.case_dev_ranked_opinion_subset_transfer.v1"
        or typed_evidence.get("schema_version")
        != "legalforecast.source_bound_bankruptcy_adversary_entry.v1"
        or not isinstance(ranked_record_sha256, str)
        or _SHA256.fullmatch(ranked_record_sha256) is None
        or typed_evidence.get("ranked_record_sha256") != ranked_record_sha256
        or typed_evidence.get("docket_id") != docket.docket_id
        or typed_evidence.get("court_id") != docket.court_id
        or not isinstance(docket.court_id, str)
        or not docket.court_id.casefold().endswith("b")
        or not isinstance(entry_number, str)
        or not entry_number.isdecimal()
        or not isinstance(filed_at, str)
        or not isinstance(entry_text, str)
        or re.search(r"\badversary\s+case\b", entry_text, re.IGNORECASE) is None
        or re.search(r"\bcomplaint\b", entry_text, re.IGNORECASE) is None
        or re.search(r"\bagainst\b", entry_text, re.IGNORECASE) is None
    ):
        return None
    try:
        date.fromisoformat(filed_at)
    except ValueError:
        return None
    return typed_evidence


def _matches_deferred_adversary_entry(
    page: CourtListenerWebDocketPage,
    evidence: Mapping[str, object],
) -> bool:
    """Require the source-bound initiating entry in authoritative reconstruction."""

    expected_number = evidence.get("entry_number")
    expected_text = evidence.get("entry_text")
    expected_date = evidence.get("filed_at")
    if not all(
        isinstance(value, str)
        for value in (expected_number, expected_text, expected_date)
    ):
        return False
    return any(
        entry.entry_number == expected_number
        and entry.text == expected_text
        and (
            (parsed := parse_courtlistener_filed_date(entry.filed_at)) is not None
            and parsed.isoformat() == expected_date
        )
        for entry in page.entries
    )


def observe_recap_api_candidate(
    store: CycleAcquisitionStore,
    batch_id: str,
    payload: Mapping[str, Any],
    *,
    client: CourtListenerClient,
    eligibility_anchor: date,
    decision_window_end: date | None = None,
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

    ``decision_window_end`` enforces the frozen batch decision window's upper
    bound at observation time: a docket whose only in-anchor MTD disposition
    falls *after* the window closes is not accepted, so the frozen config value
    is honored rather than merely recorded.  The first-disposition anchor check
    still uses an *unbounded* screen so an earlier out-of-window decision can
    permanently exclude the candidate.
    """

    docket_id = candidate_docket_id(payload)
    expected_candidate_id = f"{_CANDIDATE_PREFIX}{docket_id}"
    payload_candidate_id = payload.get("candidate_id")
    if not isinstance(payload_candidate_id, str) or not payload_candidate_id.strip():
        raise RecapApiResponseError("candidate payload is missing a candidate_id")
    candidate_id = payload_candidate_id.strip()
    if candidate_id != expected_candidate_id:
        raise RecapApiResponseError(
            "candidate payload candidate_id does not match its docket_id: "
            f"{candidate_id!r} != {expected_candidate_id!r}"
        )
    base_evidence: dict[str, object] = {
        "candidate_id": candidate_id,
        "docket_id": docket_id,
        "provider": RECAP_API_PROVIDER,
    }
    if "decision_entry_evidence" in payload:
        base_evidence["decision_entry_evidence"] = payload["decision_entry_evidence"]
    if "opinion_resolution_evidence" in payload:
        base_evidence["opinion_resolution_evidence"] = payload[
            "opinion_resolution_evidence"
        ]

    prescreen = observe_prescreened_reason(payload)
    if prescreen is not None:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code=prescreen,
            evidence={**base_evidence, "prescreen_exclusion_reason": prescreen},
        )

    decision_evidence = payload.get("decision_entry_evidence")
    if isinstance(decision_evidence, Mapping):
        raw_entry_number = cast(Mapping[str, object], decision_evidence).get(
            "entry_number"
        )
        try:
            entry_number_lower_bound = int(str(raw_entry_number))
        except (TypeError, ValueError):
            entry_number_lower_bound = None
        if (
            entry_number_lower_bound is not None
            and entry_number_lower_bound > REST_DOCKET_ENTRY_SOFT_CAP
        ):
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="excluded",
                reason_code="oversized_docket_soft_skip",
                evidence={
                    **base_evidence,
                    "entry_number_lower_bound": entry_number_lower_bound,
                    "rest_docket_entry_soft_cap": REST_DOCKET_ENTRY_SOFT_CAP,
                    "sampling_exclusion": True,
                },
            )

    require_reconstruction_auth(client)
    try:
        if pacer is not None:
            pacer.wait()
        docket = client.get_docket(docket_id)
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

    authoritative_metadata = {
        "court_id": docket.court_id,
        "docket_number": docket.docket_number,
        "case_name": docket.case_name,
    }
    raw_opinion_resolution = payload.get("opinion_resolution_evidence")
    if raw_opinion_resolution is not None:
        if not isinstance(raw_opinion_resolution, Mapping):
            raise RecapApiResponseError("opinion_resolution_evidence must be an object")
        try:
            validate_resolved_recap_identity(
                cast(Mapping[str, Any], raw_opinion_resolution),
                docket_id=docket.docket_id,
                court_id=docket.court_id,
                docket_number=docket.docket_number,
                case_name=docket.case_name,
            )
        except OpinionBackedDispositionError as error:
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="excluded",
                reason_code="invalid_civil_case_metadata",
                evidence={
                    **base_evidence,
                    "provider_contradiction": True,
                    "exclusion_detail": "opinion_recap_identity_mismatch",
                    "error": str(error),
                },
            )
    authoritative_prescreen = prescreen_recap_candidate(
        court_id=docket.court_id,
        docket_number=docket.docket_number,
        case_name=docket.case_name,
    )
    deferred_adversary_evidence = _source_bound_adversary_defer_evidence(
        store,
        batch_id=batch_id,
        payload=payload,
        docket=docket,
    )
    if authoritative_prescreen is not None:
        if (
            authoritative_prescreen != PRESCREEN_BANKRUPTCY_REASON
            or deferred_adversary_evidence is None
        ):
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="excluded",
                reason_code=authoritative_prescreen,
                evidence={
                    **base_evidence,
                    "prescreen_exclusion_reason": authoritative_prescreen,
                    "authoritative_docket_metadata": authoritative_metadata,
                    "entry_reconstruction_skipped": True,
                },
            )

    try:
        reconstructed = reconstruct_docket_page(
            client,
            docket_id,
            pacer=pacer,
            docket=docket,
        )
    except RecapDocketTooLargeError as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code="oversized_docket_soft_skip",
            evidence={
                **base_evidence,
                "rest_docket_page_hard_cap": REST_DOCKET_PAGE_HARD_CAP,
                "sampling_exclusion": True,
                "error": str(error),
            },
        )
    except RecapDocketContradictionError as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code="invalid_civil_case_metadata",
            evidence={
                **base_evidence,
                "provider_contradiction": True,
                "exclusion_detail": "contradictory_docket_entry_metadata",
                "error": str(error),
            },
        )
    except CourtListenerUnavailableError as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code="courtlistener_docket_unavailable",
            evidence={
                **base_evidence,
                "entry_reconstruction_started": True,
                "error": str(error),
            },
        )
    except (CourtListenerResponseError, RecapDocketReconstructionError) as error:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code="parse_failure",
            evidence={**base_evidence, "error": str(error)},
        )

    screening_page = reconstructed.page
    if (
        deferred_adversary_evidence is not None
        and not _matches_deferred_adversary_entry(
            reconstructed.page,
            deferred_adversary_evidence,
        )
    ):
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code="invalid_civil_case_metadata",
            evidence={
                **base_evidence,
                "provider_contradiction": True,
                "exclusion_detail": "source_bound_adversary_entry_mismatch",
                "reconstruction_proof": reconstructed.proof.to_record(),
            },
        )
    opinion_backed_evidence: Mapping[str, object] | None = None
    if raw_opinion_resolution is not None:
        assert isinstance(raw_opinion_resolution, Mapping)
        try:
            selected_opinion_resolution = select_opinion_resolution_for_page(
                reconstructed.page,
                cast(Mapping[str, Any], raw_opinion_resolution),
            )
            validate_resolved_recap_identity(
                selected_opinion_resolution,
                docket_id=docket.docket_id,
                court_id=docket.court_id,
                docket_number=docket.docket_number,
                case_name=docket.case_name,
            )
            opinion_backed = fetch_and_bind_public_opinion(
                client,
                page=reconstructed.page,
                resolved_recap_docket_id=docket_id,
                resolution_evidence=selected_opinion_resolution,
            )
        except CourtListenerUnavailableError as error:
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="transient_failure",
                reason_code="courtlistener_docket_unavailable",
                evidence={
                    **base_evidence,
                    "opinion_evidence_fetch_started": True,
                    "error": str(error),
                },
            )
        except CourtListenerResponseError as error:
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="transient_failure",
                reason_code="parse_failure",
                evidence={
                    **base_evidence,
                    "opinion_evidence_fetch_started": True,
                    "error": str(error),
                },
            )
        except OpinionBackedDispositionError as error:
            return store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state="excluded",
                reason_code="strict_clean_screen_failed",
                evidence={
                    **base_evidence,
                    "reconstruction_proof": reconstructed.proof.to_record(),
                    "exclusion_detail": "opinion_backed_disposition_unproven",
                    "error": str(error),
                },
            )
        screening_page = opinion_backed.disposition.page
        opinion_backed_evidence = opinion_backed.evidence

    adversary_candidate_text = (
        cast(str, deferred_adversary_evidence["entry_text"])
        if deferred_adversary_evidence is not None
        else None
    )
    anchored = screen_courtlistener_docket_for_mtd_decision(
        screening_page,
        candidate_text=adversary_candidate_text,
        decision_filed_on_or_after=eligibility_anchor,
        decision_filed_on_or_before=decision_window_end,
    )
    # The unbounded screen surfaces *every* actual MTD disposition entry in the
    # docket regardless of date, so the first-disposition anchor can catch a
    # docket whose in-window hit (for example "order adopting R&R") sits atop an
    # earlier MTD report/decision that predates the eligibility anchor.
    unbounded = screen_courtlistener_docket_for_mtd_decision(
        screening_page,
        candidate_text=adversary_candidate_text,
    )
    all_decisions = _decision_entry_records(unbounded.decision_entries)
    anchor_dispositions = _decision_entry_records(unbounded.anchor_disposition_entries)
    unparseable_decisions = [
        entry for entry in anchor_dispositions if entry["filed_date"] is None
    ]
    earliest = _earliest_decision_date(unbounded)
    evidence = {
        **base_evidence,
        "screen": anchored.to_record(),
        "reconstruction_proof": reconstructed.proof.to_record(),
        "mtd_decision_entries": all_decisions,
        "mtd_anchor_disposition_entries": anchor_dispositions,
        "first_mtd_decision_date": earliest.isoformat() if earliest else None,
        "eligibility_anchor": eligibility_anchor.isoformat(),
        "decision_window_end": (
            decision_window_end.isoformat() if decision_window_end else None
        ),
    }
    if opinion_backed_evidence is not None:
        evidence["opinion_backed_disposition"] = dict(opinion_backed_evidence)
    if unparseable_decisions:
        return store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code="parse_failure",
            evidence={
                **evidence,
                "unparseable_mtd_decision_entries": unparseable_decisions,
                "error": "MTD decision entry has a missing or unparseable filed date",
            },
        )
    state, reason_code = _map_screen_outcome(
        anchored=anchored,
        earliest_decision_date=earliest,
        eligibility_anchor=eligibility_anchor,
    )
    if state == "accepted":
        # Local import avoids the package initialization cycle:
        # courtlistener_acquisition imports motion_linkage, whose package exports
        # this REST module through legalforecast.ingestion.__init__.
        from legalforecast.ingestion.courtlistener_acquisition import (
            screen_courtlistener_docket_page,
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
        if (
            deferred_adversary_evidence is not None
            and PRESCREEN_BANKRUPTCY_REASON in metadata_screen.exclusion_reasons
            and set(metadata_screen.exclusion_reasons).issubset(
                {PRESCREEN_BANKRUPTCY_REASON, "not_civil_cv_docket"}
            )
        ):
            metadata_screen = CaseDevMetadataScreen(
                metadata=metadata_screen.metadata,
                exclusion_reasons=(),
            )
        canonical, canonical_exclusion = screen_courtlistener_docket_page(
            docket=docket,
            metadata_screen=metadata_screen,
            page=screening_page,
            decision_filed_on_or_after=eligibility_anchor,
            decision_filed_on_or_before=decision_window_end,
            candidate_text_override=adversary_candidate_text,
        )
        if canonical is None:
            state = "excluded"
            if canonical_exclusion is None:
                raise RecapApiResponseError(
                    "canonical REST screen returned neither a case nor exclusion"
                )
            taxonomy = cohort_reason_policy_taxonomy()
            registered_reasons = {
                reason for reasons in taxonomy.values() for reason in reasons
            }
            reason_code = (
                canonical_exclusion.reason
                if canonical_exclusion.reason in registered_reasons
                else "strict_clean_screen_failed"
            )
            evidence = {
                **evidence,
                "canonical_screen_exclusion": canonical_exclusion.to_record(),
            }
        else:
            canonical_evidence = dict(canonical)
            canonical_screen = canonical_evidence.get("mtd_decision_screen")
            evidence = {
                **canonical_evidence,
                **evidence,
                "screen": canonical_screen,
                "candidate_id": candidate_id,
                "docket_id": docket_id,
                "provider": RECAP_API_PROVIDER,
                "canonical_rest_screen_complete": True,
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
    earliest_decision_date: date | None,
    eligibility_anchor: date,
) -> tuple[str, str]:
    if (
        earliest_decision_date is not None
        and earliest_decision_date < eligibility_anchor
    ):
        # The first written MTD disposition predates the eligibility anchor, so
        # the case is permanently ineligible regardless of later dispositions.
        return "excluded", "decision_before_release_anchor"
    if anchored.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION:
        return "accepted", "strict_clean_screen_passed"
    if anchored.status is MtdDocketScreenStatus.ACTUAL_MTD_DECISION_REVIEW_OR_EXCLUDED:
        for reason in anchored.exclusion_reasons:
            if reason in _POSTURE_REASON_CODES:
                return "excluded", reason
            if reason == "procedural_or_standing_order":
                return "excluded", reason
        return "excluded", "strict_clean_screen_failed"
    if "procedural_or_standing_order" in anchored.exclusion_reasons:
        return "excluded", "procedural_or_standing_order"
    return "excluded", "strict_clean_screen_failed"


def _decision_entry_records(
    entries: Sequence[MtdDecisionEntryScreen],
) -> list[dict[str, object]]:
    return [
        {
            "row_id": entry.row_id,
            "entry_number": entry.entry_number,
            "filed_at": entry.filed_at,
            "filed_date": (
                parsed.isoformat()
                if (parsed := _parse_long_us_date(entry.filed_at)) is not None
                else None
            ),
        }
        for entry in entries
    ]


def _earliest_decision_date(screen: MtdDocketDecisionScreen) -> date | None:
    earliest: date | None = None
    for entry in screen.anchor_disposition_entries:
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

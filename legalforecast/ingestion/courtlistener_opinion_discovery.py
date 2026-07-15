"""Fail-closed CourtListener opinion-cluster discovery for MTD leads.

CourtListener's supported v4 case-law search returns opinion *clusters* with an
explicit ``docket_id``.  The cluster is stable discovery provenance; the docket
ID is the only candidate identity passed to the authenticated RECAP docket
reconstruction.  Opinion text and snippets are intentionally discarded so this
source cannot become an outcome-text path into model-visible packet inputs.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, cast

from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, DiscoveryPage

OPINION_API_PROVIDER = "courtlistener"
OPINION_API_POLICY_SCHEMA = "legalforecast.courtlistener_opinion_discovery.v1"
OPINION_HIT_EVIDENCE_SCHEMA = "legalforecast.courtlistener_opinion_hit.v1"
OPINION_API_PAGE_SIZE = 20

# An opinion is already a written decision, so outcome verbs such as "granting"
# would needlessly reduce recall.  The downstream docket screen remains the
# authority for motion linkage, disposition outcome, and first-decision timing.
OPINION_MTD_SEARCH_TERMS: tuple[str, ...] = (
    '"motion to dismiss"',
    '"Rule 12(b)(6)" OR "12(b)(6)"',
    '"judgment on the pleadings" OR "Rule 12(c)"',
    '"Rule 7012" OR "motion to dismiss adversary complaint"',
)

# CourtListener defaults opinion searches to Published unless at least one
# status checkbox is explicit.  Freeze every documented v4 opinion status so
# unpublished district orders and bankruptcy decisions are not silently lost.
OPINION_STATUS_FILTERS: tuple[str, ...] = (
    "stat_Published",
    "stat_Unpublished",
    "stat_Errata",
    "stat_Separate",
    "stat_In-chambers",
    "stat_Relating-to",
    "stat_Unknown",
)

# CourtListener federal-bankruptcy identifiers.  Most corresponding district
# identifiers use the same stem with ``d`` in place of the terminal ``b``.
# ``mpb`` is the exception: its district court is ``nmid``, not ``mpd``.
FEDERAL_BANKRUPTCY_COURT_IDS: tuple[str, ...] = (
    "akb",
    "almb",
    "alnb",
    "alsb",
    "areb",
    "arwb",
    "azb",
    "cacb",
    "caeb",
    "canb",
    "casb",
    "cob",
    "ctb",
    "dcb",
    "deb",
    "flmb",
    "flnb",
    "flsb",
    "gamb",
    "ganb",
    "gasb",
    "gub",
    "hib",
    "ianb",
    "iasb",
    "idb",
    "ilcb",
    "ilnb",
    "ilsb",
    "innb",
    "insb",
    "ksb",
    "kyeb",
    "kywb",
    "laeb",
    "lamb",
    "lawb",
    "mab",
    "mdb",
    "meb",
    "mieb",
    "miwb",
    "mnb",
    "moeb",
    "mowb",
    "mpb",
    "msnb",
    "mssb",
    "mtb",
    "nceb",
    "ncmb",
    "ncwb",
    "ndb",
    "neb",
    "nhb",
    "njb",
    "nmb",
    "nvb",
    "nyeb",
    "nynb",
    "nysb",
    "nywb",
    "ohnb",
    "ohsb",
    "okeb",
    "oknb",
    "okwb",
    "orb",
    "paeb",
    "pamb",
    "pawb",
    "prb",
    "rib",
    "scb",
    "sdb",
    "tneb",
    "tnmb",
    "tnwb",
    "txeb",
    "txnb",
    "txsb",
    "txwb",
    "utb",
    "vaeb",
    "vawb",
    "vib",
    "vtb",
    "waeb",
    "wawb",
    "wieb",
    "wiwb",
    "wvnb",
    "wvsb",
    "wyb",
)
FEDERAL_DISTRICT_COURT_IDS: tuple[str, ...] = tuple(
    sorted(
        {
            f"{court_id[:-1]}d"
            for court_id in FEDERAL_BANKRUPTCY_COURT_IDS
            if court_id != "mpb"
        }
        | {"nmid"}
    )
)
FEDERAL_TRIAL_COURT_IDS: tuple[str, ...] = tuple(
    sorted({*FEDERAL_BANKRUPTCY_COURT_IDS, *FEDERAL_DISTRICT_COURT_IDS})
)

_OPINION_SEARCH_PATH = "/api/rest/v4/search/"
_OPINION_URL = re.compile(r"^/opinion/(?P<cluster_id>[1-9][0-9]*)/[^/?#]+/$")


class OpinionApiDiscoveryError(RuntimeError):
    """Raised when opinion-search identity or completeness is unproven."""


class RequestPacer(Protocol):
    """Minimal pacing surface shared with the existing REST acquisition path."""

    def wait(self) -> None: ...


def build_opinion_batch_config(
    *,
    decision_window_start: date,
    decision_window_end: date,
    query_terms: Sequence[str] = OPINION_MTD_SEARCH_TERMS,
    top_k_per_term: int = 5_000,
) -> dict[str, object]:
    """Freeze one transfer-compatible CourtListener opinion-search batch."""

    if isinstance(decision_window_start, datetime) or isinstance(
        decision_window_end, datetime
    ):
        raise TypeError("decision window bounds must be dates, not datetimes")
    if decision_window_start > decision_window_end:
        raise ValueError("decision_window_start must be on or before the end")
    terms = _validated_query_terms(query_terms)
    if top_k_per_term <= 0:
        raise ValueError("top_k_per_term must be positive")
    if top_k_per_term % OPINION_API_PAGE_SIZE:
        raise ValueError(
            f"top_k_per_term must be a multiple of {OPINION_API_PAGE_SIZE}"
        )
    return {
        "schema_version": OPINION_API_POLICY_SCHEMA,
        # ``seed-direct-search`` intentionally accepts this exact authority name.
        "provider": OPINION_API_PROVIDER,
        "search_type": "o",
        "query_field": "q",
        "order_by": "dateFiled desc",
        "query_terms": list(terms),
        "query_term_order_is_frozen": True,
        "search_window_start": decision_window_start.isoformat(),
        "search_window_end": decision_window_end.isoformat(),
        "page_size": OPINION_API_PAGE_SIZE,
        "provider_page_size_is_fixed": True,
        "top_k_per_term": top_k_per_term,
        "court_ids": list(FEDERAL_TRIAL_COURT_IDS),
        "status_filters": list(OPINION_STATUS_FILTERS),
        "highlight": False,
    }


@dataclass(frozen=True, slots=True)
class OpinionDecisionHit:
    """Metadata-only identity for one opinion cluster and its linked docket."""

    cluster_id: str
    docket_id: str
    absolute_url: str
    court_id: str
    docket_number: str | None
    case_name: str | None
    date_filed: date
    status: str
    sub_opinions: tuple[Mapping[str, object], ...]

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
        *,
        decision_window_start: date,
        decision_window_end: date,
        allowed_court_ids: frozenset[str],
    ) -> OpinionDecisionHit:
        cluster_id = _positive_identifier(record.get("cluster_id"), "cluster_id")
        docket_id = _positive_identifier(record.get("docket_id"), "docket_id")
        absolute_url = _required_string(record, "absolute_url")
        match = _OPINION_URL.fullmatch(absolute_url)
        if match is None:
            raise OpinionApiDiscoveryError(
                f"opinion absolute_url is invalid for cluster {cluster_id}"
            )
        if match.group("cluster_id") != cluster_id:
            raise OpinionApiDiscoveryError(
                f"opinion absolute_url cluster id mismatch: {cluster_id}"
            )
        court_id = _required_string(record, "court_id")
        if court_id not in allowed_court_ids:
            raise OpinionApiDiscoveryError(
                f"opinion result is not in a frozen federal trial court: {court_id}"
            )
        raw_date = _required_string(record, "dateFiled")
        try:
            date_filed = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise OpinionApiDiscoveryError(
                f"opinion dateFiled is invalid: {raw_date!r}"
            ) from exc
        if not decision_window_start <= date_filed <= decision_window_end:
            raise OpinionApiDiscoveryError(
                f"opinion dateFiled is outside frozen decision window: {raw_date}"
            )
        return cls(
            cluster_id=cluster_id,
            docket_id=docket_id,
            absolute_url=absolute_url,
            court_id=court_id,
            docket_number=_optional_string(record, "docketNumber"),
            case_name=_optional_string(record, "caseName"),
            date_filed=date_filed,
            status=_required_string(record, "status"),
            sub_opinions=_public_opinion_references(record.get("opinions")),
        )

    def to_discovery_hit(self) -> DiscoveryHit:
        """Return a source-batch hit without opinion text or docket-entry claims."""

        return DiscoveryHit(
            provider_hit_id=self.cluster_id,
            candidate_id=self.docket_id,
            payload={
                "docket_id": self.docket_id,
                "court_id": self.court_id,
                "docket_number": self.docket_number,
                "case_name": self.case_name,
                "provider": OPINION_API_PROVIDER,
                "opinion_discovery_evidence": {
                    "schema_version": OPINION_HIT_EVIDENCE_SCHEMA,
                    "cluster_id": self.cluster_id,
                    "absolute_url": self.absolute_url,
                    "date_filed": self.date_filed.isoformat(),
                    "status": self.status,
                    "sub_opinions": [dict(item) for item in self.sub_opinions],
                },
            },
        )


def _public_opinion_references(value: object) -> tuple[Mapping[str, object], ...]:
    """Retain public artifact identity while discarding all decision text."""

    if value is None:
        return ()
    if not isinstance(value, list):
        raise OpinionApiDiscoveryError("opinion result opinions must be a list")
    references: list[Mapping[str, object]] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, Mapping):
            raise OpinionApiDiscoveryError("opinion result opinion must be an object")
        record = cast(Mapping[str, Any], raw)
        references.append(
            {
                "opinion_id": _positive_identifier(record.get("id"), "opinion id"),
                "absolute_url": _optional_string(record, "absolute_url"),
                "download_url": _optional_string(record, "download_url"),
                "local_path": _optional_string(record, "local_path"),
            }
        )
    return tuple(
        sorted(references, key=lambda item: int(cast(str, item["opinion_id"])))
    )


@dataclass(frozen=True, slots=True)
class OpinionApiDiscoverySource:
    """Expose strict ``type=o`` cursor pages to the durable scheduler."""

    client: CourtListenerClient
    decision_window_start: date
    decision_window_end: date
    pacer: RequestPacer | None = None
    court_ids: tuple[str, ...] = FEDERAL_TRIAL_COURT_IDS

    def __post_init__(self) -> None:
        if self.decision_window_start > self.decision_window_end:
            raise ValueError("decision_window_start must be on or before the end")
        if not self.court_ids or any(
            not court_id.strip() for court_id in self.court_ids
        ):
            raise ValueError("court_ids must include non-empty identifiers")
        if len(set(self.court_ids)) != len(self.court_ids):
            raise ValueError("court_ids must be unique")

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        if page_size != OPINION_API_PAGE_SIZE:
            raise ValueError(
                f"CourtListener opinion search page_size must be exactly "
                f"{OPINION_API_PAGE_SIZE}"
            )
        normalized_term = term.strip()
        if not normalized_term:
            raise ValueError("opinion query term is required")
        params = self._request_params(normalized_term)
        if self.pacer is not None:
            self.pacer.wait()
        page = self.client.search_raw(params, cursor=cursor)
        _validate_page_shape(page.raw)
        next_cursor = _validated_next_cursor(page.raw["next"], expected_params=params)
        allowed_courts = frozenset(self.court_ids)
        hits = tuple(
            OpinionDecisionHit.from_record(
                record,
                decision_window_start=self.decision_window_start,
                decision_window_end=self.decision_window_end,
                allowed_court_ids=allowed_courts,
            ).to_discovery_hit()
            for record in page.items
        )
        return DiscoveryPage(
            hits=hits,
            next_cursor=next_cursor,
            exhausted=True if next_cursor is None else None,
        )

    def _request_params(self, term: str) -> dict[str, str]:
        return {
            "type": "o",
            "q": term,
            "filed_after": self.decision_window_start.isoformat(),
            "filed_before": self.decision_window_end.isoformat(),
            "order_by": "dateFiled desc",
            "court": " ".join(self.court_ids),
            **{name: "on" for name in OPINION_STATUS_FILTERS},
        }


def _validated_query_terms(query_terms: Sequence[str]) -> tuple[str, ...]:
    terms = tuple(term.strip() for term in query_terms)
    if not terms or any(not term for term in terms):
        raise ValueError("query terms must include at least one non-empty term")
    if len(set(terms)) != len(terms):
        raise ValueError("query terms must be unique")
    return terms


def _validate_page_shape(payload: Mapping[str, Any]) -> None:
    if "results" not in payload:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion page lacks explicit results"
        )
    if not isinstance(payload["results"], list):
        raise OpinionApiDiscoveryError(
            "CourtListener opinion page results must be a list"
        )
    if "next" not in payload:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion page lacks explicit next pagination evidence"
        )


def _validated_next_cursor(
    raw_next: object,
    *,
    expected_params: Mapping[str, str],
) -> str | None:
    if raw_next is None:
        return None
    if not isinstance(raw_next, str) or not raw_next.strip():
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation must be a non-empty URL or null"
        )
    try:
        parsed = urllib.parse.urlparse(raw_next)
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation URL is invalid"
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.courtlistener.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation origin is invalid"
        )
    if parsed.path != _OPINION_SEARCH_PATH:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation path is invalid"
        )
    try:
        pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation query is invalid"
        ) from exc
    values: dict[str, list[str]] = {}
    for key, value in pairs:
        values.setdefault(key, []).append(value)
    cursor_values = values.pop("cursor", [])
    if len(cursor_values) != 1 or not cursor_values[0]:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation query lacks one cursor"
        )
    expected = {key: [value] for key, value in expected_params.items()}
    if values != expected:
        raise OpinionApiDiscoveryError(
            "CourtListener opinion continuation query changed frozen parameters"
        )
    return cursor_values[0]


def _positive_identifier(value: object, field_name: str) -> str:
    if isinstance(value, bool):
        raise OpinionApiDiscoveryError(f"opinion {field_name} must be positive")
    if isinstance(value, int):
        if value > 0:
            return str(value)
        raise OpinionApiDiscoveryError(f"opinion {field_name} must be positive")
    if isinstance(value, str) and value.isascii() and value.isdigit():
        parsed = int(value)
        if parsed > 0 and value == str(parsed):
            return value
    raise OpinionApiDiscoveryError(f"opinion {field_name} must be positive")


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise OpinionApiDiscoveryError(
            f"opinion result requires non-empty {field_name}"
        )
    return value.strip()


def _optional_string(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise OpinionApiDiscoveryError(f"opinion {field_name} must be a string")
    stripped = value.strip()
    return stripped or None

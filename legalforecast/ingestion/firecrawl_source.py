"""Strict Firecrawl source for allowlisted public CourtListener HTML.

Each call performs one cache-disabled scrape. ``basic`` requests are capped at
one credit; explicitly configured ``auto`` or ``enhanced`` requests may use
Firecrawl's stealth proxy but are capped at five credits. URL validation is
deliberately narrow so this source cannot become a general-purpose proxy.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol, cast
from urllib.parse import parse_qsl, urlparse

FIRECRAWL_API_KEY_ENV = "FIRECRAWL_API_KEY"
FIRECRAWL_SCRAPE_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
_COURTLISTENER_HOSTS = frozenset({"courtlistener.com", "www.courtlistener.com"})
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[0-9]+)(?:/[^/]+)?/?$")
_DOCKET_PAGINATION_QUERY = re.compile(r"^order_by=desc&page=(?P<page>[1-9][0-9]*)$")
_RECAP_SEARCH_REQUIRED_KEYS = frozenset(
    {
        "type",
        "q",
        "entry_date_filed_after",
        "entry_date_filed_before",
        "order_by",
    }
)
_RECAP_SEARCH_OPTIONAL_KEYS = frozenset({"page"})
_US_DATE = re.compile(r"^(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<year>[0-9]{4})$")
FirecrawlProxy = Literal["basic", "auto", "enhanced"]


class FirecrawlError(RuntimeError):
    """Base class for Firecrawl source failures."""


class FirecrawlMissingAPIKeyError(FirecrawlError):
    """Raised when ``FIRECRAWL_API_KEY`` is missing or blank."""


class FirecrawlAuthError(FirecrawlError):
    """Raised when Firecrawl rejects the API credentials."""


class FirecrawlPaymentRequiredError(FirecrawlError):
    """Raised when the Firecrawl account has insufficient credits."""


class FirecrawlRateLimitError(FirecrawlError):
    """Raised when Firecrawl rate-limits the request."""


class FirecrawlServerError(FirecrawlError):
    """Raised when Firecrawl reports a server-side failure."""


class FirecrawlResponseError(FirecrawlError):
    """Raised for malformed or policy-violating Firecrawl responses."""


class FirecrawlURLValidationError(FirecrawlError):
    """Raised when a source URL is not a public CourtListener docket URL."""


@dataclass(frozen=True, slots=True)
class FirecrawlConfig:
    """Configuration for a bounded Firecrawl scrape request."""

    api_key: str
    request_timeout_seconds: float = 70.0
    proxy: FirecrawlProxy = "basic"
    force_browser: bool = False

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise FirecrawlMissingAPIKeyError(
                f"{FIRECRAWL_API_KEY_ENV} is required for Firecrawl docket fetches"
            )
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if self.proxy not in {"basic", "auto", "enhanced"}:
            raise ValueError("proxy must be 'basic', 'auto', or 'enhanced'")

    @property
    def max_credits_per_scrape(self) -> int:
        """Return the non-configurable per-request billing ceiling."""

        return 1 if self.proxy == "basic" else 5

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        request_timeout_seconds: float = 70.0,
        proxy: FirecrawlProxy = "basic",
        force_browser: bool = False,
    ) -> FirecrawlConfig:
        values = os.environ if environ is None else environ
        return cls(
            api_key=values.get(FIRECRAWL_API_KEY_ENV, ""),
            request_timeout_seconds=request_timeout_seconds,
            proxy=proxy,
            force_browser=force_browser,
        )


@dataclass(frozen=True, slots=True)
class FirecrawlHTTPResponse:
    status_code: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=lambda: {})


class FirecrawlTransport(Protocol):
    """Transport seam that keeps unit tests offline and deterministic."""

    def scrape(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> FirecrawlHTTPResponse:
        raise NotImplementedError


class UrlLibFirecrawlTransport:
    """Standard-library transport for explicitly authorized live scrapes."""

    def scrape(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> FirecrawlHTTPResponse:
        if endpoint != FIRECRAWL_SCRAPE_ENDPOINT:
            raise FirecrawlError("Firecrawl endpoint must be the v2 scrape endpoint")
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(dict(payload)).encode("utf-8"),
            method="POST",
            headers=dict(headers),
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - fixed HTTPS endpoint above
                request,
                timeout=timeout_seconds,
            ) as response:
                return FirecrawlHTTPResponse(
                    status_code=int(response.status),
                    payload=_decode_payload(response.read()),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return FirecrawlHTTPResponse(
                status_code=exc.code,
                payload=_decode_error_payload(exc.read()),
                headers=dict(exc.headers.items()),
            )
        except urllib.error.URLError as exc:
            raise FirecrawlServerError(
                "Firecrawl request failed before receiving an HTTP response"
            ) from exc


class FirecrawlFixtureTransport:
    """Ordered offline response transport that also records every request."""

    def __init__(self, responses: Sequence[FirecrawlHTTPResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, object]] = []

    def scrape(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> FirecrawlHTTPResponse:
        self.requests.append(
            {
                "endpoint": endpoint,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self._responses:
            raise AssertionError("unexpected Firecrawl fixture request")
        return self._responses.pop(0)


@dataclass(frozen=True, slots=True)
class FirecrawlScrapeResult:
    source_url: str
    docket_id: str | None
    raw_html: str
    target_status_code: int
    proxy_requested: FirecrawlProxy
    proxy_used: str | None
    cache_state: str | None
    credits_used: float | None
    raw: Mapping[str, Any]


class FirecrawlCourtListenerHTMLSource:
    """Fetch raw HTML for one allowlisted CourtListener docket page."""

    def __init__(
        self,
        config: FirecrawlConfig | None = None,
        *,
        transport: FirecrawlTransport | None = None,
    ) -> None:
        self.config = config or FirecrawlConfig.from_env()
        self.transport = transport or UrlLibFirecrawlTransport()

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        """Fetch one docket page and return parser-compatible raw HTML."""

        return self.scrape(docket_id=docket_id, source_url=source_url).raw_html

    def scrape(self, *, docket_id: str, source_url: str) -> FirecrawlScrapeResult:
        """Perform exactly one bounded Firecrawl request."""

        normalized_docket_id = validate_courtlistener_docket_url(
            source_url, expected_docket_id=docket_id
        )
        return self._scrape_validated_url(
            source_url=source_url, docket_id=normalized_docket_id
        )

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        """Scrape one strictly allowlisted docket or RECAP search URL.

        Docket callers that already possess an expected identity should keep
        using :meth:`scrape`, which additionally enforces that identity match.
        """

        docket_id: str | None
        try:
            docket_id = validate_courtlistener_docket_url(source_url)
        except FirecrawlURLValidationError:
            try:
                validate_courtlistener_recap_search_url(source_url)
            except FirecrawlURLValidationError as exc:
                raise FirecrawlURLValidationError(
                    "source URL is not an allowlisted CourtListener docket or "
                    "RECAP search URL"
                ) from exc
            docket_id = None
        return self._scrape_validated_url(source_url=source_url, docket_id=docket_id)

    def _scrape_validated_url(
        self, *, source_url: str, docket_id: str | None
    ) -> FirecrawlScrapeResult:
        response = self.transport.scrape(
            endpoint=FIRECRAWL_SCRAPE_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.config.api_key.strip()}",
                "Content-Type": "application/json",
            },
            payload=_scrape_payload(
                source_url,
                proxy=self.config.proxy,
                force_browser=self.config.force_browser,
            ),
            timeout_seconds=self.config.request_timeout_seconds,
        )
        _raise_for_status(response.status_code)
        return _validated_result(
            response.payload,
            source_url=source_url,
            docket_id=docket_id,
            proxy_requested=self.config.proxy,
            max_credits=self.config.max_credits_per_scrape,
        )


def _scrape_payload(
    source_url: str,
    *,
    proxy: FirecrawlProxy = "basic",
    force_browser: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "url": source_url,
        "formats": ["rawHtml"],
        "onlyMainContent": False,
        "onlyCleanContent": False,
        "maxAge": 0,
        "storeInCache": False,
        "proxy": proxy,
        "timeout": 60000,
        "skipTlsVerification": False,
        "parsers": [],
        "waitFor": 0,
        "blockAds": False,
        "lockdown": False,
        "redactPII": False,
    }
    if force_browser:
        payload["actions"] = [{"type": "wait", "milliseconds": 1}]
    return payload


def validate_courtlistener_docket_url(
    source_url: str, *, expected_docket_id: str | None = None
) -> str:
    if expected_docket_id is not None and (
        not expected_docket_id.isascii() or not expected_docket_id.isdigit()
    ):
        raise FirecrawlURLValidationError("CourtListener docket ID must be numeric")
    parsed = urlparse(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _COURTLISTENER_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.params
    ):
        raise FirecrawlURLValidationError(
            "source URL must be a public HTTPS CourtListener docket URL"
        )
    match = _DOCKET_PATH.fullmatch(parsed.path)
    if match is None:
        raise FirecrawlURLValidationError(
            "source URL must contain a numeric CourtListener docket ID"
        )
    url_docket_id = match.group("docket_id")
    if expected_docket_id is not None and url_docket_id != expected_docket_id:
        raise FirecrawlURLValidationError(
            "source URL docket ID does not match the requested docket ID"
        )
    if parsed.query:
        query_match = _DOCKET_PAGINATION_QUERY.fullmatch(parsed.query)
        if query_match is None:
            raise FirecrawlURLValidationError(
                "docket pagination must use canonical order_by=desc&page=N"
            )
    return url_docket_id


def validate_courtlistener_recap_search_url(source_url: str) -> None:
    """Fail closed unless *source_url* is a bounded public RECAP search URL.

    The accepted form is CourtListener's root search with ``type=r``, one
    nonempty query, explicit U.S.-formatted filing-date bounds, newest-document
    ordering, and an optional positive page number. Duplicate or unknown query
    parameters are rejected.
    """

    parsed = urlparse(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _COURTLISTENER_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/"
        or parsed.fragment
        or parsed.params
    ):
        raise FirecrawlURLValidationError(
            "source URL must be a public HTTPS CourtListener RECAP search URL"
        )
    try:
        pairs = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=6,
        )
    except ValueError as exc:
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search query is malformed"
        ) from exc
    values = dict(pairs)
    keys = frozenset(values)
    if len(values) != len(pairs) or not (
        _RECAP_SEARCH_REQUIRED_KEYS <= keys
        and keys <= _RECAP_SEARCH_REQUIRED_KEYS | _RECAP_SEARCH_OPTIONAL_KEYS
    ):
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search has duplicate, missing, or unknown parameters"
        )
    if values["type"] != "r":
        raise FirecrawlURLValidationError("CourtListener search type must be RECAP")
    query = values["q"]
    if (
        not query.strip()
        or len(query) > 500
        or any(ord(character) < 32 or ord(character) == 127 for character in query)
    ):
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search query must be bounded nonempty text"
        )
    filed_after = _parse_us_date(
        values["entry_date_filed_after"], field_name="entry_date_filed_after"
    )
    filed_before = _parse_us_date(
        values["entry_date_filed_before"], field_name="entry_date_filed_before"
    )
    if filed_after > filed_before:
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search filing-date bounds are reversed"
        )
    if values["order_by"] != "entry_date_filed desc":
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search must order newest documents first"
        )
    page = values.get("page")
    if page is not None and re.fullmatch(r"[1-9][0-9]*", page) is None:
        raise FirecrawlURLValidationError(
            "CourtListener RECAP search page must be a positive canonical integer"
        )


def _parse_us_date(value: str, *, field_name: str) -> date:
    match = _US_DATE.fullmatch(value)
    if match is None:
        raise FirecrawlURLValidationError(
            f"CourtListener RECAP search {field_name} must use MM/DD/YYYY"
        )
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as exc:
        raise FirecrawlURLValidationError(
            f"CourtListener RECAP search {field_name} is not a valid date"
        ) from exc


def _validated_result(
    payload: Mapping[str, Any],
    *,
    source_url: str,
    docket_id: str | None,
    proxy_requested: FirecrawlProxy,
    max_credits: int,
) -> FirecrawlScrapeResult:
    if payload.get("success") is not True:
        raise FirecrawlResponseError("Firecrawl response did not report success")
    data = _mapping(payload.get("data"), "data")
    raw_html = data.get("rawHtml")
    if not isinstance(raw_html, str) or not raw_html.strip():
        raise FirecrawlResponseError("Firecrawl response is missing nonempty rawHtml")
    metadata = _mapping(data.get("metadata"), "data.metadata")
    status_code = metadata.get("statusCode")
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        raise FirecrawlResponseError(
            "Firecrawl target statusCode is missing or invalid"
        )
    if status_code != 200:
        raise FirecrawlResponseError(
            f"CourtListener target returned unexpected status {status_code}"
        )

    proxy_used = _optional_string(metadata, data, "proxyUsed")
    if proxy_used is None:
        raise FirecrawlResponseError("Firecrawl response did not report proxyUsed")
    normalized_proxy_used = proxy_used.lower()
    if proxy_requested == "basic":
        allowed_proxies = frozenset({"basic"})
    elif proxy_requested == "enhanced":
        allowed_proxies = frozenset({"stealth"})
    else:
        allowed_proxies = frozenset({"basic", "stealth"})
    if normalized_proxy_used not in allowed_proxies:
        raise FirecrawlResponseError(
            f"Firecrawl used disallowed proxy mode {proxy_used!r}"
        )
    cache_state = _optional_string(metadata, data, "cacheState")
    if cache_state is not None and cache_state.lower() == "hit":
        raise FirecrawlResponseError("Firecrawl unexpectedly served a cache hit")
    credits_used = _optional_number(metadata, data, "creditsUsed")
    if credits_used is None:
        raise FirecrawlResponseError("Firecrawl response did not report creditsUsed")
    if not math.isfinite(credits_used) or not 0 <= credits_used <= max_credits:
        cap_name = "one-credit" if max_credits == 1 else "five-credit"
        raise FirecrawlResponseError(
            f"Firecrawl scrape exceeded {cap_name} cap: {credits_used:g}"
        )
    return FirecrawlScrapeResult(
        source_url=source_url,
        docket_id=docket_id,
        raw_html=raw_html,
        target_status_code=status_code,
        proxy_requested=proxy_requested,
        proxy_used=proxy_used,
        cache_state=cache_state,
        credits_used=credits_used,
        raw=payload,
    )


def _raise_for_status(status_code: int) -> None:
    if status_code in {401, 403}:
        raise FirecrawlAuthError(
            f"Firecrawl rejected the API credentials (HTTP {status_code})"
        )
    if status_code == 402:
        raise FirecrawlPaymentRequiredError(
            "Firecrawl account has insufficient credits (HTTP 402)"
        )
    if status_code == 429:
        raise FirecrawlRateLimitError("Firecrawl rate limit reached (HTTP 429)")
    if status_code >= 500:
        raise FirecrawlServerError(f"Firecrawl server failure (HTTP {status_code})")
    if status_code < 200 or status_code >= 300:
        raise FirecrawlResponseError(
            f"Firecrawl returned unexpected HTTP status {status_code}"
        )


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FirecrawlResponseError(f"Firecrawl {field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _optional_string(
    primary: Mapping[str, Any], fallback: Mapping[str, Any], key: str
) -> str | None:
    value = primary.get(key, fallback.get(key))
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise FirecrawlResponseError(f"Firecrawl {key} must be a nonempty string")
    return value.strip()


def _optional_number(
    primary: Mapping[str, Any], fallback: Mapping[str, Any], key: str
) -> float | None:
    value = primary.get(key, fallback.get(key))
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FirecrawlResponseError(f"Firecrawl {key} must be numeric")
    return float(value)


def _decode_payload(raw: bytes) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FirecrawlResponseError("Firecrawl returned invalid JSON") from exc
    return _mapping(payload, "response")


def _decode_error_payload(raw: bytes) -> Mapping[str, Any]:
    """Preserve HTTP status classification even when an error body is not JSON."""

    try:
        return _decode_payload(raw)
    except FirecrawlResponseError:
        return {}

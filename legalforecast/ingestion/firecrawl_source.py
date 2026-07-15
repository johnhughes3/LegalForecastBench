"""Strict Firecrawl source for allowlisted public CourtListener HTML.

Each call performs one cache-disabled scrape. ``basic`` requests are capped at
one credit; explicitly configured ``auto`` or ``enhanced`` requests may use
Firecrawl's stealth proxy but are capped at five credits. URL validation is
deliberately narrow so this source cannot become a general-purpose proxy.
"""

from __future__ import annotations

import hashlib
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
from urllib.parse import parse_qsl, urlencode, urlparse, urlunsplit

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
_RECAP_SEARCH_CANONICAL_KEYS = (
    "type",
    "q",
    "entry_date_filed_after",
    "entry_date_filed_before",
    "order_by",
)
_US_DATE = re.compile(r"^(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<year>[0-9]{4})$")
_FAILURE_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_CHALLENGE_SCAN_LIMIT = 256_000
_CHALLENGE_MARKERS = (
    "cf-chl-",
    "challenge-platform",
    "checking your browser before accessing",
    "attention required! | cloudflare",
)
FirecrawlProxy = Literal["basic", "auto", "enhanced"]


class FirecrawlError(RuntimeError):
    """Base class for Firecrawl source failures."""

    default_failure_code = "firecrawl_error"
    transient = False

    def __init__(
        self,
        message: str,
        *,
        failure_code: str | None = None,
        provider_http_status: int | None = None,
        response_sha256: str | None = None,
    ) -> None:
        code = failure_code or self.default_failure_code
        if _FAILURE_CODE.fullmatch(code) is None:
            raise ValueError("Firecrawl failure_code must be canonical snake_case")
        self.failure_code = code
        self.safe_message = _safe_failure_message(message)
        self.provider_http_status = provider_http_status
        self.response_sha256 = response_sha256
        super().__init__(self.safe_message)

    def attach_response_evidence(
        self,
        *,
        provider_http_status: int,
        response_sha256: str,
    ) -> None:
        """Attach non-secret response evidence without replacing prior evidence."""

        if self.provider_http_status is None:
            self.provider_http_status = provider_http_status
        if self.response_sha256 is None:
            self.response_sha256 = response_sha256


class FirecrawlMissingAPIKeyError(FirecrawlError):
    """Raised when ``FIRECRAWL_API_KEY`` is missing or blank."""

    default_failure_code = "missing_api_key"


class FirecrawlAuthError(FirecrawlError):
    """Raised when Firecrawl rejects the API credentials."""

    default_failure_code = "provider_auth_error"


class FirecrawlPaymentRequiredError(FirecrawlError):
    """Raised when the Firecrawl account has insufficient credits."""

    default_failure_code = "provider_payment_required"


class FirecrawlRateLimitError(FirecrawlError):
    """Raised when Firecrawl rate-limits the request."""

    default_failure_code = "provider_rate_limit"


class FirecrawlServerError(FirecrawlError):
    """Raised when Firecrawl reports a server-side failure."""

    default_failure_code = "provider_server_error"
    transient = True


class FirecrawlResponseError(FirecrawlError):
    """Raised for malformed or policy-violating Firecrawl responses."""

    default_failure_code = "invalid_provider_response"


class FirecrawlTargetHTTPError(FirecrawlResponseError):
    """Raised when the allowlisted target itself returns a non-200 status."""

    def __init__(
        self,
        target_status_code: int,
        *,
        reported_credits: float,
        proxy_used: str,
    ) -> None:
        self.target_status_code = target_status_code
        self.reported_credits = reported_credits
        self.proxy_used = proxy_used
        super().__init__(
            "CourtListener target returned a non-success status",
            failure_code="target_http_status_invalid",
        )


class FirecrawlChallengeError(FirecrawlError):
    """Raised when a successful scrape contains confirmed challenge HTML."""

    default_failure_code = "courtlistener_challenge_html"


class FirecrawlURLValidationError(FirecrawlError):
    """Raised when a source URL is not a public CourtListener docket URL."""

    default_failure_code = "source_url_not_allowlisted"


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
    response_sha256: str | None = None


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
                raw_response = response.read()
                return FirecrawlHTTPResponse(
                    status_code=int(response.status),
                    payload=_decode_payload(raw_response),
                    headers=dict(response.headers.items()),
                    response_sha256=hashlib.sha256(raw_response).hexdigest(),
                )
        except urllib.error.HTTPError as exc:
            raw_response = exc.read()
            return FirecrawlHTTPResponse(
                status_code=exc.code,
                payload=_decode_error_payload(raw_response),
                headers=dict(exc.headers.items()),
                response_sha256=hashlib.sha256(raw_response).hexdigest(),
            )
        except (urllib.error.URLError, TimeoutError) as exc:
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
    resolved_url: str


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
        response_sha256 = response.response_sha256 or _payload_sha256(response.payload)
        try:
            _raise_for_status(response.status_code)
            return _validated_result(
                response.payload,
                source_url=source_url,
                docket_id=docket_id,
                proxy_requested=self.config.proxy,
                max_credits=self.config.max_credits_per_scrape,
            )
        except FirecrawlError as error:
            error.attach_response_evidence(
                provider_http_status=response.status_code,
                response_sha256=response_sha256,
            )
            raise


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

    The accepted form is CourtListener's root RECAP entry (``type=r``) search,
    including decision-first presets, with one nonempty query,
    explicit U.S.-formatted filing-date bounds, newest-document ordering, and an
    optional positive page number. Duplicate or unknown parameters are rejected.
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


def canonicalize_courtlistener_source_url(source_url: str) -> str:
    """Return a security identity for an allowlisted CourtListener source URL.

    Docket slugs and the optional ``www`` host are presentation redirects, so a
    docket identity is the numeric docket plus its exact newest-first page.
    RECAP searches retain every decoded query value while normalizing parameter
    order, host, encoding, and an explicit ``page=1`` to the implicit first page.
    """

    try:
        docket_id = validate_courtlistener_docket_url(source_url)
    except FirecrawlURLValidationError:
        validate_courtlistener_recap_search_url(source_url)
    else:
        parsed = urlparse(source_url)
        query = parsed.query
        return urlunsplit(
            (
                "https",
                "www.courtlistener.com",
                f"/docket/{docket_id}/",
                query,
                "",
            )
        )

    parsed = urlparse(source_url)
    values = dict(parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True))
    pairs = [(key, values[key]) for key in _RECAP_SEARCH_CANONICAL_KEYS]
    page = values.get("page")
    if page is not None and page != "1":
        pairs.append(("page", page))
    return urlunsplit(
        (
            "https",
            "www.courtlistener.com",
            "/",
            urlencode(pairs),
            "",
        )
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
        raise FirecrawlResponseError(
            "Firecrawl response did not report success",
            failure_code="provider_unsuccessful_response",
        )
    data = _mapping(payload.get("data"), "data")
    raw_html = data.get("rawHtml")
    if not isinstance(raw_html, str) or not raw_html.strip():
        raise FirecrawlResponseError(
            "Firecrawl response is missing nonempty rawHtml",
            failure_code="raw_html_missing",
        )
    metadata = _mapping(data.get("metadata"), "data.metadata")
    status_code = metadata.get("statusCode")
    if (
        not isinstance(status_code, int)
        or isinstance(status_code, bool)
        or not 100 <= status_code <= 599
    ):
        raise FirecrawlResponseError(
            "Firecrawl target statusCode is missing or invalid"
        )
    if _contains_challenge_html(raw_html):
        raise FirecrawlChallengeError(
            "CourtListener returned marker-confirmed challenge HTML"
        )

    resolved_values = tuple(
        value
        for value in (
            _optional_string(metadata, data, "sourceURL"),
            _optional_string(metadata, data, "url"),
        )
        if value is not None
    )
    if not resolved_values:
        raise FirecrawlResponseError(
            "Firecrawl response did not report its resolved source URL",
            failure_code="resolved_url_missing",
        )
    authorized_url = canonicalize_courtlistener_source_url(source_url)
    try:
        resolved_urls = tuple(
            canonicalize_courtlistener_source_url(value) for value in resolved_values
        )
    except FirecrawlURLValidationError as exc:
        raise FirecrawlResponseError(
            "Firecrawl resolved URL is not an allowlisted CourtListener target",
            failure_code="resolved_url_not_allowlisted",
        ) from exc
    if any(value != authorized_url for value in resolved_urls):
        raise FirecrawlResponseError(
            "resolved CourtListener URL did not match the authorized target",
            failure_code="resolved_url_mismatch",
        )

    proxy_used = _optional_string(metadata, data, "proxyUsed")
    if proxy_used is None:
        raise FirecrawlResponseError(
            "Firecrawl response did not report proxyUsed",
            failure_code="proxy_used_missing",
        )
    normalized_proxy_used = proxy_used.lower()
    if proxy_requested == "basic":
        allowed_proxies = frozenset({"basic"})
    elif proxy_requested == "enhanced":
        allowed_proxies = frozenset({"stealth"})
    else:
        allowed_proxies = frozenset({"basic", "stealth"})
    if normalized_proxy_used not in allowed_proxies:
        raise FirecrawlResponseError(
            "Firecrawl used a disallowed proxy mode",
            failure_code="proxy_used_disallowed",
        )
    cache_state = _optional_string(metadata, data, "cacheState")
    if cache_state is not None and cache_state.lower() == "hit":
        raise FirecrawlResponseError(
            "Firecrawl unexpectedly served a cache hit",
            failure_code="cache_hit_disallowed",
        )
    credits_used = _optional_number(metadata, data, "creditsUsed")
    if credits_used is None:
        raise FirecrawlResponseError(
            "Firecrawl response did not report creditsUsed",
            failure_code="credits_used_missing",
        )
    if not math.isfinite(credits_used) or not 0 <= credits_used <= max_credits:
        cap_name = "one-credit" if max_credits == 1 else "five-credit"
        raise FirecrawlResponseError(
            f"Firecrawl scrape exceeded the {cap_name} cap",
            failure_code="credits_used_exceeded_reservation",
        )
    if not credits_used.is_integer():
        raise FirecrawlResponseError(
            "Firecrawl creditsUsed must be integral",
            failure_code="credits_used_not_integral",
        )
    if status_code != 200:
        raise FirecrawlTargetHTTPError(
            status_code,
            reported_credits=credits_used,
            proxy_used=proxy_used,
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
        resolved_url=authorized_url,
    )


def _contains_challenge_html(raw_html: str) -> bool:
    """Inspect a bounded prefix for specific Cloudflare challenge markers."""

    bounded = raw_html[:_CHALLENGE_SCAN_LIMIT].casefold()
    return any(marker in bounded for marker in _CHALLENGE_MARKERS)


def _raise_for_status(status_code: int) -> None:
    if status_code in {401, 403}:
        raise FirecrawlAuthError(
            f"Firecrawl rejected the API credentials (HTTP {status_code})",
            provider_http_status=status_code,
        )
    if status_code == 402:
        raise FirecrawlPaymentRequiredError(
            "Firecrawl account has insufficient credits (HTTP 402)",
            provider_http_status=status_code,
        )
    if status_code == 429:
        raise FirecrawlRateLimitError(
            "Firecrawl rate limit reached (HTTP 429)",
            provider_http_status=status_code,
        )
    if status_code == 408:
        raise FirecrawlServerError(
            "Firecrawl request timed out (HTTP 408)",
            provider_http_status=status_code,
        )
    if status_code >= 500:
        raise FirecrawlServerError(
            f"Firecrawl server failure (HTTP {status_code})",
            provider_http_status=status_code,
        )
    if status_code < 200 or status_code >= 300:
        raise FirecrawlResponseError(
            f"Firecrawl returned unexpected HTTP status {status_code}",
            failure_code="provider_http_status_unexpected",
            provider_http_status=status_code,
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
        raise FirecrawlResponseError(
            "Firecrawl returned invalid JSON",
            failure_code="provider_json_invalid",
            response_sha256=hashlib.sha256(raw).hexdigest(),
        ) from exc
    return _mapping(payload, "response")


def _decode_error_payload(raw: bytes) -> Mapping[str, Any]:
    """Preserve HTTP status classification even when an error body is not JSON."""

    try:
        return _decode_payload(raw)
    except FirecrawlResponseError:
        return {}


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_failure_message(message: str) -> str:
    normalized = " ".join(message.split())
    if not normalized:
        return "Firecrawl request failed"
    return normalized[:300]

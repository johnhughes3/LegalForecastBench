"""Strict Firecrawl source for public CourtListener docket HTML.

The source deliberately uses Firecrawl's basic proxy exactly once per fetch.
It disables cache reads/writes and rejects responses that indicate a more
expensive proxy, a cache hit, or more than one credit of usage.
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
from typing import Any, Protocol, cast
from urllib.parse import urlparse

FIRECRAWL_API_KEY_ENV = "FIRECRAWL_API_KEY"
FIRECRAWL_SCRAPE_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
_COURTLISTENER_HOSTS = frozenset({"courtlistener.com", "www.courtlistener.com"})
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[0-9]+)(?:/[^/]+)?/?$")


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

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise FirecrawlMissingAPIKeyError(
                f"{FIRECRAWL_API_KEY_ENV} is required for Firecrawl docket fetches"
            )
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        request_timeout_seconds: float = 70.0,
    ) -> FirecrawlConfig:
        values = os.environ if environ is None else environ
        return cls(
            api_key=values.get(FIRECRAWL_API_KEY_ENV, ""),
            request_timeout_seconds=request_timeout_seconds,
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
    ) -> FirecrawlHTTPResponse: ...


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
                f"Firecrawl request failed: {exc.reason}"
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
    docket_id: str
    raw_html: str
    target_status_code: int
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
        """Perform exactly one bounded basic-proxy Firecrawl request."""

        normalized_docket_id = _validate_courtlistener_docket_url(
            source_url, expected_docket_id=docket_id
        )
        response = self.transport.scrape(
            endpoint=FIRECRAWL_SCRAPE_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.config.api_key.strip()}",
                "Content-Type": "application/json",
            },
            payload=_scrape_payload(source_url),
            timeout_seconds=self.config.request_timeout_seconds,
        )
        _raise_for_status(response.status_code)
        return _validated_result(
            response.payload,
            source_url=source_url,
            docket_id=normalized_docket_id,
        )


def _scrape_payload(source_url: str) -> dict[str, object]:
    return {
        "url": source_url,
        "formats": ["rawHtml"],
        "onlyMainContent": False,
        "onlyCleanContent": False,
        "maxAge": 0,
        "storeInCache": False,
        "proxy": "basic",
        "timeout": 60000,
        "skipTlsVerification": False,
        "parsers": [],
        "waitFor": 0,
        "blockAds": False,
        "lockdown": False,
        "redactPII": False,
    }


def _validate_courtlistener_docket_url(
    source_url: str, *, expected_docket_id: str
) -> str:
    if not expected_docket_id.isascii() or not expected_docket_id.isdigit():
        raise FirecrawlURLValidationError("CourtListener docket ID must be numeric")
    parsed = urlparse(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _COURTLISTENER_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
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
    if url_docket_id != expected_docket_id:
        raise FirecrawlURLValidationError(
            "source URL docket ID does not match the requested docket ID"
        )
    return url_docket_id


def _validated_result(
    payload: Mapping[str, Any], *, source_url: str, docket_id: str
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
    if proxy_used.lower() != "basic":
        raise FirecrawlResponseError(
            f"Firecrawl used disallowed proxy mode {proxy_used!r}"
        )
    cache_state = _optional_string(metadata, data, "cacheState")
    if cache_state is not None and cache_state.lower() == "hit":
        raise FirecrawlResponseError("Firecrawl unexpectedly served a cache hit")
    credits_used = _optional_number(metadata, data, "creditsUsed")
    if credits_used is None:
        raise FirecrawlResponseError("Firecrawl response did not report creditsUsed")
    if not math.isfinite(credits_used) or not 0 <= credits_used <= 1:
        raise FirecrawlResponseError(
            f"Firecrawl scrape exceeded one-credit cap: {credits_used:g}"
        )
    return FirecrawlScrapeResult(
        source_url=source_url,
        docket_id=docket_id,
        raw_html=raw_html,
        target_status_code=status_code,
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

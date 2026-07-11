"""CourtListener fallback client with offline fixture transport support."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

from legalforecast.ingestion.http_config import validate_https_base_url
from legalforecast.logging import get_logger, pipeline_log_extra

DEFAULT_COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
COURTLISTENER_ALLOWED_BASE_HOSTS = frozenset({"www.courtlistener.com"})
COURTLISTENER_API_TOKEN_ENV = "COURTLISTENER_API_TOKEN"
COURTLISTENER_BASE_URL_ENV = "COURTLISTENER_BASE_URL"
COURTLISTENER_TIMEOUT_SECONDS_ENV = "COURTLISTENER_TIMEOUT_SECONDS"

_LOGGER = get_logger(__name__)
T = TypeVar("T")
ResponseParser = Callable[[Mapping[str, Any]], T]


class CourtListenerClientError(RuntimeError):
    """Base class for CourtListener fallback client errors."""


class CourtListenerAuthError(CourtListenerClientError):
    """Raised for authentication or authorization failures."""


class CourtListenerRateLimitError(CourtListenerClientError):
    """Raised for rate-limit responses."""


class CourtListenerServerError(CourtListenerClientError):
    """Raised for retryable server responses."""


class CourtListenerUnavailableError(CourtListenerClientError):
    """Raised when requested public fallback material is unavailable."""


class CourtListenerResponseError(CourtListenerClientError):
    """Raised for malformed CourtListener responses."""


@dataclass(frozen=True, slots=True)
class CourtListenerConfig:
    """Runtime settings for CourtListener fallback retrieval."""

    api_token: str | None = None
    base_url: str = DEFAULT_COURTLISTENER_BASE_URL
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> CourtListenerConfig:
        values = os.environ if environ is None else environ
        return cls(
            api_token=_optional_text(values.get(COURTLISTENER_API_TOKEN_ENV)),
            base_url=_base_url(values.get(COURTLISTENER_BASE_URL_ENV)),
            timeout_seconds=_positive_float(
                values.get(COURTLISTENER_TIMEOUT_SECONDS_ENV),
                COURTLISTENER_TIMEOUT_SECONDS_ENV,
                default=30.0,
            ),
        )


@dataclass(frozen=True, slots=True)
class CourtListenerHTTPResponse:
    status_code: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=lambda: {})


class CourtListenerTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> CourtListenerHTTPResponse: ...


@dataclass(frozen=True, slots=True)
class CourtListenerPage[T]:
    items: tuple[T, ...]
    next_cursor: str | None
    raw: Mapping[str, Any]

    @staticmethod
    def from_payload(
        payload: Mapping[str, Any],
        parser: ResponseParser[T],
    ) -> CourtListenerPage[T]:
        return _page_from_payload(payload, parser)


@dataclass(frozen=True, slots=True)
class CourtListenerDocket:
    docket_id: str
    court_id: str | None
    docket_number: str | None
    case_name: str
    date_filed: str | None
    source_url: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CourtListenerDocket:
        return cls(
            docket_id=_required_string(record, "id", "docket_id", "docketId"),
            court_id=_court_identifier(record),
            docket_number=_optional_string(record, "docket_number", "docketNumber"),
            case_name=_required_string(
                record,
                "case_name",
                "caseName",
                "case_name_full",
                "caption",
            ),
            date_filed=_optional_string(record, "date_filed", "dateFiled"),
            source_url=_optional_string(record, "absolute_url", "url", "resource_uri"),
            raw=record,
        )


@dataclass(frozen=True, slots=True)
class CourtListenerDocketEntry:
    docket_entry_id: str
    docket_id: str
    entry_number: str | None
    entry_text: str
    filed_at: str | None
    recap_document_ids: tuple[str, ...]
    source_url: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CourtListenerDocketEntry:
        return cls(
            docket_entry_id=_required_string(record, "id", "docket_entry_id"),
            docket_id=_required_string(record, "docket", "docket_id", "docketId"),
            entry_number=_optional_string(
                record,
                "entry_number",
                "entryNumber",
                "recap_sequence_number",
            ),
            entry_text=_required_string(
                record,
                "description",
                "entry_text",
                "docket_text",
                "text",
            ),
            filed_at=_optional_string(
                record, "date_filed", "dateFiled", "date_entered"
            ),
            recap_document_ids=_recap_document_ids(record),
            source_url=_optional_string(record, "absolute_url", "url", "resource_uri"),
            raw=record,
        )

    @property
    def has_recap_documents(self) -> bool:
        return bool(self.recap_document_ids)


@dataclass(frozen=True, slots=True)
class CourtListenerRecapSearchHit:
    """Minimal RECAP search hit used to discover candidate dockets."""

    docket_id: str
    docket_entry_id: str | None
    description: str | None
    entry_date_filed: str | None
    source_url: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
    ) -> CourtListenerRecapSearchHit:
        docket = record.get("docket")
        docket_record = (
            cast(Mapping[str, Any], docket) if isinstance(docket, Mapping) else None
        )
        docket_id = _optional_string(record, "docket_id", "docketId")
        if docket_id is None and docket_record is not None:
            docket_id = _optional_string(docket_record, "id", "docket_id")
        if (
            docket_id is None
            and isinstance(docket, str | int)
            and not isinstance(
                docket,
                bool,
            )
        ):
            docket_id = str(docket)
        if docket_id is None:
            raise CourtListenerResponseError(
                "missing required CourtListener field: docket_id"
            )
        return cls(
            docket_id=docket_id,
            docket_entry_id=_optional_string(
                record,
                "docket_entry_id",
                "docketEntryId",
            ),
            description=_optional_string(
                record,
                "description",
                "short_description",
                "snippet",
            ),
            entry_date_filed=_optional_string(
                record,
                "entry_date_filed",
                "date_filed",
                "dateFiled",
            ),
            source_url=_optional_string(record, "absolute_url", "url"),
            raw=record,
        )


class UrlLibCourtListenerTransport:
    """Network transport used only when explicitly configured by the caller."""

    def __init__(self, base_url: str) -> None:
        self._base_url = validate_https_base_url(
            base_url,
            field_name=COURTLISTENER_BASE_URL_ENV,
            allowed_hosts=COURTLISTENER_ALLOWED_BASE_HOSTS,
            error_type=CourtListenerClientError,
        )

    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> CourtListenerHTTPResponse:
        normalized_method = method.upper()
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            method=normalized_method,
            headers=dict(headers),
        )
        try:
            # Base URL is validated as HTTPS and host-allowlisted in __init__.
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=timeout_seconds,
            ) as response:
                return CourtListenerHTTPResponse(
                    status_code=response.status,
                    payload=_json_payload(response.read()),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return CourtListenerHTTPResponse(
                status_code=exc.code,
                payload=_json_payload(exc.read()),
                headers=dict(exc.headers.items()) if exc.headers else {},
            )
        except urllib.error.URLError as exc:
            raise CourtListenerClientError(
                f"CourtListener request failed: {exc.reason}"
            ) from exc


@dataclass(frozen=True, slots=True)
class RecordedCourtListenerResponse:
    method: str
    path: str
    params: Mapping[str, Any]
    status_code: int
    payload: Mapping[str, Any]

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
    ) -> RecordedCourtListenerResponse:
        return cls(
            method=_required_string(record, "method").upper(),
            path=_required_string(record, "path"),
            params=_primitive_mapping(record.get("params", {}), "params"),
            status_code=_required_int(record, "status_code"),
            payload=_mapping(record.get("payload"), "payload"),
        )


class CourtListenerFixtureTransport:
    """Replay recorded CourtListener responses without network access."""

    def __init__(self, responses: Sequence[RecordedCourtListenerResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    @classmethod
    def from_records(
        cls,
        records: Sequence[Mapping[str, Any]],
    ) -> CourtListenerFixtureTransport:
        return cls(
            tuple(
                RecordedCourtListenerResponse.from_record(record) for record in records
            )
        )

    @classmethod
    def from_jsonl(cls, path: str | Path) -> CourtListenerFixtureTransport:
        responses: list[RecordedCourtListenerResponse] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw: object = json.loads(line)
                if not isinstance(raw, Mapping):
                    raise CourtListenerResponseError(
                        f"recorded response line {line_number} must be an object"
                    )
                responses.append(
                    RecordedCourtListenerResponse.from_record(
                        cast(Mapping[str, Any], raw)
                    )
                )
        return cls(responses)

    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> CourtListenerHTTPResponse:
        del headers, timeout_seconds
        if not self._responses:
            raise CourtListenerClientError("no recorded CourtListener responses remain")
        response = self._responses.pop(0)
        normalized_method = method.upper()
        normalized_params = dict(params)
        self.requests.append((normalized_method, path, normalized_params))
        if response.method != normalized_method or response.path != path:
            raise CourtListenerClientError(
                "recorded CourtListener response request mismatch"
            )
        if dict(response.params) != normalized_params:
            raise CourtListenerClientError(
                "recorded CourtListener response params mismatch"
            )
        return CourtListenerHTTPResponse(
            status_code=response.status_code,
            payload=response.payload,
        )


class CourtListenerClient:
    def __init__(
        self,
        *,
        config: CourtListenerConfig | None = None,
        transport: CourtListenerTransport | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self.config = CourtListenerConfig.from_env() if config is None else config
        self.transport = (
            UrlLibCourtListenerTransport(self.config.base_url)
            if transport is None
            else transport
        )
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.request_count = 0

    def get_docket(self, docket_id: str) -> CourtListenerDocket:
        payload = self._request_json("GET", f"/dockets/{docket_id}/", {})
        return CourtListenerDocket.from_record(payload)

    def search_recap_documents(
        self,
        query: str,
        *,
        cursor: str | None = None,
        page_size: int = 50,
    ) -> CourtListenerPage[CourtListenerRecapSearchHit]:
        """Search public RECAP filings with the CourtListener v4 search API."""

        if not query.strip():
            raise CourtListenerResponseError("CourtListener search query is required")
        if page_size <= 0 or page_size > 100:
            raise CourtListenerResponseError(
                "CourtListener search page_size must be between 1 and 100"
            )
        params: dict[str, Any] = {
            "q": query,
            "type": "r",
            "order_by": "score desc",
            "available_only": "on",
            "page_size": page_size,
        }
        if cursor is not None:
            params["cursor"] = cursor
        payload = self._request_json("GET", "/search/", params)
        parser: ResponseParser[CourtListenerRecapSearchHit] = (
            CourtListenerRecapSearchHit.from_record
        )
        return _page_from_payload(payload, parser)

    def list_docket_entries(
        self,
        docket_id: str,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> CourtListenerPage[CourtListenerDocketEntry]:
        params: dict[str, Any] = {"docket": docket_id}
        if cursor is not None:
            params["cursor"] = cursor
        if page_size is not None:
            params["page_size"] = page_size
        payload = self._request_json("GET", "/docket-entries/", params)
        parser: ResponseParser[CourtListenerDocketEntry] = (
            CourtListenerDocketEntry.from_record
        )
        return _page_from_payload(payload, parser)

    def iter_docket_entries(
        self,
        docket_id: str,
        *,
        page_size: int | None = None,
    ) -> Iterator[CourtListenerDocketEntry]:
        cursor: str | None = None
        while True:
            page = self.list_docket_entries(
                docket_id,
                cursor=cursor,
                page_size=page_size,
            )
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def _request_json(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        headers = self._headers()
        attempt = 0
        while True:
            response = self.transport.request(
                method=method,
                path=path,
                params=params,
                headers=headers,
                timeout_seconds=self.config.timeout_seconds,
            )
            self.request_count += 1
            self._log_request(path, response.status_code)
            if 200 <= response.status_code < 300:
                return response.payload

            error = _error_for_response(response, path)
            if (
                isinstance(
                    error, CourtListenerRateLimitError | CourtListenerServerError
                )
                and attempt < self.max_retries
            ):
                attempt += 1
                if self.retry_backoff_seconds:
                    time.sleep(self.retry_backoff_seconds)
                continue
            raise error

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.api_token is not None:
            headers["Authorization"] = f"Token {self.config.api_token}"
        return headers

    def _log_request(self, path: str, status_code: int) -> None:
        _LOGGER.info(
            "CourtListener request",
            extra={
                **pipeline_log_extra(
                    stage="courtlistener_request",
                    request_count=self.request_count,
                    cost_usd=None,
                ),
                "courtlistener_path": path,
                "courtlistener_status_code": status_code,
            },
        )


def _error_for_response(
    response: CourtListenerHTTPResponse,
    path: str,
) -> CourtListenerClientError:
    message = _optional_string(response.payload, "detail", "error", "message") or (
        f"CourtListener request to {path} failed with status {response.status_code}"
    )
    if response.status_code in {401, 403}:
        return CourtListenerAuthError(message)
    if response.status_code == 404:
        return CourtListenerUnavailableError(message)
    if response.status_code == 429:
        return CourtListenerRateLimitError(message)
    if response.status_code >= 500:
        return CourtListenerServerError(message)
    return CourtListenerClientError(message)


def _page_from_payload[TPageItem](
    payload: Mapping[str, Any],
    parser: ResponseParser[TPageItem],
) -> CourtListenerPage[TPageItem]:
    raw_items_object: object = payload.get("results", payload.get("items"))
    if raw_items_object is None:
        raw_items_object = []
    if not isinstance(raw_items_object, list):
        raise CourtListenerResponseError(
            "CourtListener page must include results or items"
        )
    raw_items = cast(list[object], raw_items_object)
    return CourtListenerPage(
        items=tuple(parser(_mapping(item, "page item")) for item in raw_items),
        next_cursor=_next_cursor(payload),
        raw=payload,
    )


def _json_payload(raw_body: bytes) -> Mapping[str, Any]:
    if not raw_body:
        return {}
    decoded: object = json.loads(raw_body.decode("utf-8"))
    return _mapping(decoded, "response payload")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CourtListenerResponseError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _primitive_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CourtListenerResponseError(f"{label} must be an object")
    result: dict[str, Any] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str) or not isinstance(
            item,
            str | int | float | bool,
        ):
            raise CourtListenerResponseError(
                f"{label} must contain string keys and primitive values"
            )
        result[key] = item
    return result


def _required_string(record: Mapping[str, Any], *field_names: str) -> str:
    value = _optional_string(record, *field_names)
    if value is None:
        joined = ", ".join(field_names)
        raise CourtListenerResponseError(
            f"missing required CourtListener field: {joined}"
        )
    return value


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CourtListenerResponseError(f"{field_name} must be an integer")
    return value


def _recap_document_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    raw_documents_object: object = record.get(
        "recap_documents",
        record.get("recapDocumentIds"),
    )
    if raw_documents_object is None:
        return ()
    if not isinstance(raw_documents_object, list):
        raise CourtListenerResponseError("recap_documents must be a list")
    raw_documents = cast(list[object], raw_documents_object)
    ids: list[str] = []
    for raw_document in raw_documents:
        if isinstance(raw_document, str | int) and not isinstance(raw_document, bool):
            ids.append(str(raw_document))
            continue
        document = _mapping(raw_document, "recap document")
        ids.append(_required_string(document, "id", "recap_document_id"))
    return tuple(ids)


def _court_identifier(record: Mapping[str, Any]) -> str | None:
    value = _optional_string(record, "court_id", "courtId", "court")
    if value is None:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.path:
        match = re.search(r"/courts/([^/]+)/?$", parsed.path)
        if match is not None:
            return match.group(1)
    return value


def _next_cursor(payload: Mapping[str, Any]) -> str | None:
    raw_next = _optional_string(payload, "next", "next_cursor", "nextCursor")
    if raw_next is None:
        return None
    parsed = urllib.parse.urlparse(raw_next)
    if parsed.scheme and parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        for key in ("cursor", "page"):
            values = query.get(key)
            if values:
                return values[0]
    return raw_next


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _base_url(value: str | None) -> str:
    base_url = _optional_text(value) or DEFAULT_COURTLISTENER_BASE_URL
    return validate_https_base_url(
        base_url,
        field_name=COURTLISTENER_BASE_URL_ENV,
        allowed_hosts=COURTLISTENER_ALLOWED_BASE_HOSTS,
        error_type=CourtListenerResponseError,
    )


def _positive_float(value: str | None, field_name: str, *, default: float) -> float:
    text = _optional_text(value)
    if text is None:
        return default
    try:
        parsed = float(text)
    except ValueError as exc:
        raise CourtListenerResponseError(f"{field_name} must be a number") from exc
    if parsed <= 0:
        raise CourtListenerResponseError(f"{field_name} must be positive")
    return parsed

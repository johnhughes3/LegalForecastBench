"""Typed case.dev client with offline fixture transport support."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from http.client import HTTPMessage
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

from legalforecast.ingestion.case_dev_config import (
    CASE_DEV_ALLOWED_BASE_HOSTS,
    CASE_DEV_BASE_URL_ENV,
    CaseDevConfig,
    CaseDevUsageEstimate,
)
from legalforecast.ingestion.http_config import validate_https_base_url
from legalforecast.logging import get_logger, pipeline_log_extra

_LOGGER = get_logger(__name__)
T = TypeVar("T")
ResponseParser = Callable[[Mapping[str, Any]], T]


class CaseDevClientError(RuntimeError):
    """Base class for case.dev client errors."""


class CaseDevAuthError(CaseDevClientError):
    """Raised for authentication or authorization failures."""


class CaseDevRateLimitError(CaseDevClientError):
    """Raised when case.dev returns a rate-limit response."""


class CaseDevServerError(CaseDevClientError):
    """Raised when case.dev returns a retryable server failure."""


class CaseDevFeatureUnavailableError(CaseDevClientError):
    """Raised when a documented case.dev feature is not available yet."""


class CaseDevResponseError(CaseDevClientError):
    """Raised when case.dev returns malformed or incomplete data."""


class CaseDevRedirectError(CaseDevClientError):
    """Raised when an authenticated case.dev redirect violates policy."""


class CaseDevPurchaseOutcomeUnknownError(CaseDevClientError):
    """Raised when a paid POST redirects and its outcome cannot be proven."""


@dataclass(frozen=True, slots=True)
class CaseDevHTTPResponse:
    status_code: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=lambda: {})


class CaseDevTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> CaseDevHTTPResponse: ...


@dataclass(frozen=True, slots=True)
class CaseDevDocketHit:
    case_id: str
    docket_id: str | None
    docket_entry_id: str
    entry_number: str | None
    entry_text: str
    filed_at: str | None
    source_url: str | None
    source_document_ids: tuple[str, ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CaseDevDocketHit:
        return cls(
            case_id=_required_string(record, "case_id", "caseId"),
            docket_id=_optional_string(record, "docket_id", "docketId"),
            docket_entry_id=_required_string(
                record, "docket_entry_id", "docketEntryId", "id"
            ),
            entry_number=_optional_string(record, "entry_number", "entryNumber"),
            entry_text=_required_string(record, "entry_text", "docket_text", "text"),
            filed_at=_optional_string(record, "filed_at", "date_filed", "filedAt"),
            source_url=_optional_string(record, "source_url", "url"),
            source_document_ids=_document_ids(record),
            raw=record,
        )


@dataclass(frozen=True, slots=True)
class CaseDevCase:
    case_id: str
    caption: str
    court: str | None
    docket_number: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CaseDevCase:
        return cls(
            case_id=_required_string(record, "case_id", "caseId", "id"),
            caption=_required_string(
                record,
                "caption",
                "case_name",
                "caseName",
                "name",
            ),
            court=_optional_string(record, "court", "court_id", "courtId"),
            docket_number=_optional_string(
                record,
                "docket_number",
                "docketNumber",
                "case_number",
            ),
            raw=record,
        )


@dataclass(frozen=True, slots=True)
class CaseDevDocument:
    document_id: str
    case_id: str
    document_type: str | None
    text: str | None
    source_url: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CaseDevDocument:
        return cls(
            document_id=_required_string(record, "document_id", "documentId", "id"),
            case_id=_required_string(record, "case_id", "caseId"),
            document_type=_optional_string(record, "document_type", "type"),
            text=_optional_string(record, "text", "plain_text", "content"),
            source_url=_optional_string(record, "source_url", "url"),
            raw=record,
        )


@dataclass(frozen=True, slots=True)
class CaseDevPage[T]:
    items: tuple[T, ...]
    next_cursor: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        parser: ResponseParser[T],
    ) -> CaseDevPage[T]:
        raw_items = payload.get("results", payload.get("items"))
        if not isinstance(raw_items, list):
            raise CaseDevResponseError("case.dev page must include results or items")

        items = cast(list[object], raw_items)
        parsed_items = tuple(parser(_mapping(item, "page item")) for item in items)
        return cls(
            items=parsed_items,
            next_cursor=_optional_string(payload, "next_cursor", "nextCursor"),
            raw=payload,
        )


class _CaseDevOpener(Protocol):
    def open(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> Any: ...


class _NoAutomaticRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


class UrlLibCaseDevTransport:
    """Network transport used only for explicitly enabled live runs."""

    def __init__(
        self,
        base_url: str,
        *,
        _opener: _CaseDevOpener | None = None,
    ) -> None:
        self._base_url = validate_https_base_url(
            base_url,
            field_name=CASE_DEV_BASE_URL_ENV,
            allowed_hosts=CASE_DEV_ALLOWED_BASE_HOSTS,
            error_type=CaseDevClientError,
        )
        self._base_origin = _https_origin(self._base_url)
        self._opener = _opener or urllib.request.build_opener(
            _NoAutomaticRedirectHandler()
        )

    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> CaseDevHTTPResponse:
        normalized_method = method.upper()
        url = f"{self._base_url}{path}"
        query = "" if normalized_method == "POST" else urllib.parse.urlencode(params)
        if query:
            url = f"{url}?{query}"
        request_headers = dict(headers)
        data: bytes | None = None
        if normalized_method == "POST":
            request_headers.setdefault("Content-Type", "application/json")
            data = json.dumps(dict(params)).encode("utf-8")
        for redirect_count in range(6):
            request = urllib.request.Request(
                url,
                data=data,
                method=normalized_method,
                headers=request_headers,
            )
            try:
                # Redirects are disabled in the opener and handled below only
                # after validating the target against the authenticated origin.
                with self._opener.open(request, timeout=timeout_seconds) as response:
                    payload = _json_payload(response.read())
                    return CaseDevHTTPResponse(
                        status_code=response.status,
                        payload=payload,
                        headers=dict(response.headers.items()),
                    )
            except TimeoutError as exc:
                return _synthetic_timeout_response(exc)
            except urllib.error.HTTPError as exc:
                if 300 <= exc.code < 400:
                    headers = dict(exc.headers.items()) if exc.headers else {}
                    if request.get_method() != "GET":
                        message = (
                            "case.dev paid purchase redirected; outcome is unknown"
                            if _is_pacer_purchase_path(path)
                            else "case.dev authenticated POST redirect refused"
                        )
                        return CaseDevHTTPResponse(
                            status_code=exc.code,
                            payload={"error": message},
                            headers=headers,
                        )
                    try:
                        url = self._validated_redirect_url(
                            request=request,
                            response=exc,
                            redirect_count=redirect_count,
                        )
                    except CaseDevRedirectError as redirect_error:
                        return CaseDevHTTPResponse(
                            status_code=exc.code,
                            payload={"error": str(redirect_error)},
                            headers=headers,
                        )
                    continue
                payload = _json_payload(exc.read())
                return CaseDevHTTPResponse(
                    status_code=exc.code,
                    payload=payload,
                    headers=dict(exc.headers.items()) if exc.headers else {},
                )
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    return _synthetic_timeout_response(exc.reason)
                raise CaseDevClientError(
                    f"case.dev request failed: {exc.reason}"
                ) from exc
        raise CaseDevRedirectError("case.dev request exceeded five redirects")

    def _validated_redirect_url(
        self,
        *,
        request: urllib.request.Request,
        response: urllib.error.HTTPError,
        redirect_count: int,
    ) -> str:
        if redirect_count >= 5:
            raise CaseDevRedirectError("case.dev request exceeded five redirects")
        location = response.headers.get("Location") if response.headers else None
        if not location:
            raise CaseDevRedirectError("case.dev redirect is missing Location")
        target = urllib.parse.urljoin(request.full_url, location)
        if _https_origin(target) != self._base_origin:
            raise CaseDevRedirectError(
                "case.dev redirect target must remain on the authenticated HTTPS origin"
            )
        return target


def _https_origin(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise CaseDevRedirectError(
            "case.dev redirect target must use credential-free HTTPS"
        )
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise CaseDevRedirectError("case.dev redirect target has invalid port") from exc
    return parsed.scheme, parsed.hostname.lower(), port


def _is_pacer_purchase_path(path: str) -> bool:
    return bool(re.fullmatch(r"/legal/v1/documents/[^/]+/pacer", path))


@dataclass(frozen=True, slots=True)
class RecordedCaseDevResponse:
    method: str
    path: str
    params: Mapping[str, Any]
    status_code: int
    payload: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RecordedCaseDevResponse:
        return cls(
            method=_required_string(record, "method").upper(),
            path=_required_string(record, "path"),
            params=_primitive_mapping(record.get("params", {}), "params"),
            status_code=_required_int(record, "status_code"),
            payload=_mapping(record.get("payload"), "payload"),
        )


class CaseDevFixtureTransport:
    """Replay recorded case.dev responses without network access."""

    def __init__(self, responses: Sequence[RecordedCaseDevResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    @classmethod
    def from_records(
        cls, records: Sequence[Mapping[str, Any]]
    ) -> CaseDevFixtureTransport:
        return cls(
            tuple(RecordedCaseDevResponse.from_record(record) for record in records)
        )

    @classmethod
    def from_jsonl(cls, path: str | Path) -> CaseDevFixtureTransport:
        responses: list[RecordedCaseDevResponse] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw: object = json.loads(line)
                if not isinstance(raw, Mapping):
                    raise CaseDevResponseError(
                        f"recorded response line {line_number} must be an object"
                    )
                responses.append(
                    RecordedCaseDevResponse.from_record(cast(Mapping[str, Any], raw))
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
    ) -> CaseDevHTTPResponse:
        del headers, timeout_seconds
        if not self._responses:
            raise CaseDevClientError("no recorded case.dev responses remain")
        response = self._responses.pop(0)
        normalized_method = method.upper()
        normalized_params = dict(params)
        self.requests.append((normalized_method, path, normalized_params))
        if response.method != normalized_method or response.path != path:
            raise CaseDevClientError("recorded case.dev response request mismatch")
        if dict(response.params) != normalized_params:
            raise CaseDevClientError("recorded case.dev response params mismatch")
        return CaseDevHTTPResponse(
            status_code=response.status_code,
            payload=response.payload,
        )


class CaseDevClient:
    def __init__(
        self,
        *,
        config: CaseDevConfig | None = None,
        transport: CaseDevTransport | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self.config = CaseDevConfig.from_env() if config is None else config
        self.transport = (
            UrlLibCaseDevTransport(self.config.base_url)
            if transport is None
            else transport
        )
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.request_count = 0
        self._last_request_monotonic: float | None = None

    @classmethod
    def live_from_env(cls) -> CaseDevClient:
        return cls(config=CaseDevConfig.from_env(require_api_key=True))

    def search_docket_entries(
        self,
        query: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> CaseDevPage[CaseDevDocketHit]:
        params: dict[str, Any] = {"type": "search", "query": query}
        if cursor is not None:
            params["offset"] = int(cursor)
        if limit is not None:
            params["limit"] = limit
        payload = self._request_json("POST", "/legal/v1/docket", params)
        return _legal_docket_search_page(payload, query=query)

    def get_case_docket_entries(
        self,
        case_id: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> CaseDevPage[CaseDevDocketHit]:
        params: dict[str, Any] = {
            "type": "lookup",
            "docketId": case_id,
            "includeEntries": True,
        }
        if cursor is not None:
            params["offset"] = int(cursor)
        if limit is not None:
            params["limit"] = limit
        payload = self._request_json("POST", "/legal/v1/docket", params)
        return _legal_docket_entries_page(payload, case_id=case_id)

    def iter_case_docket_entries(
        self,
        case_id: str,
        *,
        page_size: int | None = None,
    ) -> Iterator[CaseDevDocketHit]:
        cursor: str | None = None
        while True:
            page = self.get_case_docket_entries(case_id, cursor=cursor, limit=page_size)
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def iter_docket_entry_search(
        self,
        query: str,
        *,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> Iterator[CaseDevDocketHit]:
        cursor: str | None = None
        yielded = 0
        while True:
            page = self.search_docket_entries(
                query,
                cursor=cursor,
                limit=page_size,
            )
            for item in page.items:
                if max_results is not None and yielded >= max_results:
                    return
                yield item
                yielded += 1
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def get_case(self, case_id: str) -> CaseDevCase:
        payload = self._request_json(
            "POST",
            "/legal/v1/docket",
            {"type": "lookup", "docketId": case_id},
        )
        docket = payload.get("docket", payload)
        return CaseDevCase.from_record(_mapping(docket, "docket"))

    def get_document(self, document_id: str) -> CaseDevDocument:
        payload = self._request_json("GET", f"/v1/documents/{document_id}", {})
        return CaseDevDocument.from_record(payload)

    def purchase_pacer_document(
        self,
        document_id: str,
        *,
        acknowledge_pacer_fees: bool,
    ) -> Mapping[str, Any]:
        """Low-level fee-acknowledged PACER document recovery request."""

        return self._request_json(
            "POST",
            f"/legal/v1/documents/{urllib.parse.quote(document_id, safe='')}/pacer",
            {"live": True, "acknowledgePacerFees": acknowledge_pacer_fees},
        )

    def usage_estimate(self) -> CaseDevUsageEstimate:
        return self.config.usage_estimate(self.request_count)

    def _request_json(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        headers = self._headers()
        attempt = 0
        while True:
            self._throttle_if_needed()
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
                isinstance(error, CaseDevRateLimitError | CaseDevServerError)
                and attempt < self.max_retries
            ):
                attempt += 1
                if self.retry_backoff_seconds:
                    time.sleep(self.retry_backoff_seconds)
                continue
            raise error

    def _throttle_if_needed(self) -> None:
        limit = self.config.rate_limit_per_minute
        if limit is None:
            return
        interval_seconds = 60.0 / limit
        now = time.monotonic()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            remaining = interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
        self._last_request_monotonic = now

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.api_key is not None:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _log_request(self, path: str, status_code: int) -> None:
        estimate = self.config.usage_estimate(self.request_count)
        _LOGGER.info(
            "case.dev request",
            extra={
                **pipeline_log_extra(
                    stage="case_dev_request",
                    request_count=self.request_count,
                    cost_usd=estimate.estimated_cost_usd,
                ),
                "case_dev_path": path,
                "case_dev_status_code": status_code,
            },
        )


def _error_for_response(response: CaseDevHTTPResponse, path: str) -> CaseDevClientError:
    message = _optional_string(response.payload, "error", "message") or (
        f"case.dev request to {path} failed with status {response.status_code}"
    )
    if 300 <= response.status_code < 400:
        if _is_pacer_purchase_path(path):
            return CaseDevPurchaseOutcomeUnknownError(message)
        return CaseDevRedirectError(message)
    if response.status_code in {401, 403}:
        return CaseDevAuthError(message)
    if response.status_code == 429:
        return CaseDevRateLimitError(message)
    if response.status_code >= 500:
        if response.status_code == 501:
            return CaseDevFeatureUnavailableError(message)
        return CaseDevServerError(message)
    return CaseDevClientError(message)


def _synthetic_timeout_response(exc: TimeoutError) -> CaseDevHTTPResponse:
    return CaseDevHTTPResponse(
        status_code=504,
        payload={"error": f"case.dev request timed out: {exc}"},
    )


def _json_payload(raw_body: bytes) -> Mapping[str, Any]:
    if not raw_body:
        return {}
    decoded: object = json.loads(raw_body.decode("utf-8"))
    return _mapping(decoded, "response payload")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseDevResponseError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _primitive_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseDevResponseError(f"{label} must be an object")
    mapping = cast(Mapping[object, object], value)
    result: dict[str, Any] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not isinstance(item, str | int | bool):
            raise CaseDevResponseError(
                f"{label} must contain string keys and primitive values"
            )
        result[key] = item
    return result


def _required_string(record: Mapping[str, Any], *field_names: str) -> str:
    value = _optional_string(record, *field_names)
    if value is None:
        joined = ", ".join(field_names)
        raise CaseDevResponseError(f"missing required case.dev field: {joined}")
    return value


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CaseDevResponseError(f"{field_name} must be an integer")
    return value


def _document_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    list_value = record.get("document_ids", record.get("documentIds"))
    if isinstance(list_value, list):
        values = cast(list[object], list_value)
        if not all(isinstance(item, str) and item.strip() for item in values):
            raise CaseDevResponseError("document_ids must contain strings")
        return tuple(cast(list[str], values))
    single_value = _optional_string(record, "document_id", "documentId")
    return () if single_value is None else (single_value,)


def _legal_docket_search_page(
    payload: Mapping[str, Any],
    *,
    query: str,
) -> CaseDevPage[CaseDevDocketHit]:
    raw_dockets = payload.get("dockets")
    if not isinstance(raw_dockets, list):
        raise CaseDevResponseError("case.dev docket search must include dockets")
    dockets = cast(list[object], raw_dockets)
    hits = tuple(
        _hit_from_legal_docket_search_record(_mapping(item, "docket"), query=query)
        for item in dockets
    )
    return CaseDevPage(
        items=hits,
        next_cursor=_legal_next_cursor(payload),
        raw=payload,
    )


def _legal_docket_entries_page(
    payload: Mapping[str, Any],
    *,
    case_id: str,
) -> CaseDevPage[CaseDevDocketHit]:
    docket = _mapping(payload.get("docket", payload), "docket")
    raw_entries = docket.get("entries", payload.get("entries", []))
    if not isinstance(raw_entries, list):
        raise CaseDevResponseError("case.dev docket lookup entries must be a list")
    entries = cast(list[object], raw_entries)
    hits = tuple(
        _hit_from_legal_docket_entry_record(
            _mapping(item, "docket entry"),
            case_id=case_id,
        )
        for item in entries
    )
    return CaseDevPage(
        items=hits,
        next_cursor=_legal_next_cursor(payload),
        raw=payload,
    )


def _legal_next_cursor(payload: Mapping[str, Any]) -> str | None:
    """Return only an explicit Case.dev continuation cursor or offset."""

    continuations: list[tuple[str, str]] = []
    for field_name in ("next_cursor", "nextCursor", "next_offset", "nextOffset"):
        if field_name not in payload:
            continue
        value = payload[field_name]
        if value is None:
            continue
        if field_name in {"next_offset", "nextOffset"}:
            normalized = _legal_next_offset(value, field_name=field_name)
        elif isinstance(value, str) and value.strip():
            normalized = value.strip()
        elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            normalized = str(value)
        else:
            raise CaseDevResponseError(
                f"case.dev {field_name} must be a non-negative integer or "
                "non-empty string"
            )
        continuations.append((field_name, normalized))
    if not continuations:
        return None
    distinct_values = {value for _, value in continuations}
    if len(distinct_values) != 1:
        fields = ", ".join(field for field, _ in continuations)
        raise CaseDevResponseError(
            f"case.dev returned conflicting continuation fields: {fields}"
        )
    return continuations[0][1]


def _legal_next_offset(value: object, *, field_name: str) -> str:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdecimal():
            return str(int(stripped))
    raise CaseDevResponseError(
        f"case.dev {field_name} must be a non-negative integer or numeric string"
    )


def _hit_from_legal_docket_search_record(
    record: Mapping[str, Any],
    *,
    query: str,
) -> CaseDevDocketHit:
    docket_id = _required_string(record, "id", "docketId")
    case_name = _optional_string(record, "caseName", "caption", "name") or "unknown"
    cause = _optional_string(record, "cause")
    nature_of_suit = _optional_string(record, "natureOfSuit")
    entry_text = "; ".join(
        part
        for part in (
            f"case.dev docket search hit for query: {query}",
            f"case: {case_name}",
            f"cause: {cause}" if cause is not None else None,
            (
                f"nature of suit: {nature_of_suit}"
                if nature_of_suit is not None
                else None
            ),
        )
        if part is not None
    )
    docket_entry_id = f"{docket_id}:search:{_slug(query)}"
    raw: Mapping[str, Any] = {
        "case_id": docket_id,
        "docket_id": docket_id,
        "docket_entry_id": docket_entry_id,
        "entry_text": entry_text,
        "filed_at": _optional_string(record, "dateFiled", "filed_at", "filedAt"),
        "source_url": _optional_string(record, "url"),
        "legal_docket": dict(record),
    }
    return CaseDevDocketHit(
        case_id=docket_id,
        docket_id=docket_id,
        docket_entry_id=docket_entry_id,
        entry_number=None,
        entry_text=entry_text,
        filed_at=_optional_string(record, "dateFiled", "filed_at", "filedAt"),
        source_url=_optional_string(record, "url"),
        source_document_ids=(),
        raw=raw,
    )


def _hit_from_legal_docket_entry_record(
    record: Mapping[str, Any],
    *,
    case_id: str,
) -> CaseDevDocketHit:
    entry_number = record.get("entryNumber", record.get("entry_number"))
    entry_number_text = None if entry_number is None else str(entry_number)
    docket_entry_id = _optional_string(record, "id", "docketEntryId")
    if docket_entry_id is None:
        docket_entry_id = f"entry-{entry_number_text or 'unknown'}"
    return CaseDevDocketHit(
        case_id=case_id,
        docket_id=case_id,
        docket_entry_id=docket_entry_id,
        entry_number=entry_number_text,
        entry_text=_legal_entry_text(record, entry_number_text),
        filed_at=_optional_string(record, "date", "dateFiled", "filed_at"),
        source_url=_optional_string(record, "url"),
        source_document_ids=_document_ids_from_legal_entry(record),
        raw=record,
    )


def _legal_entry_text(
    record: Mapping[str, Any],
    entry_number_text: str | None,
) -> str:
    entry_text = _optional_string(record, "description", "entry_text", "text")
    if entry_text is not None:
        return entry_text
    document_descriptions = tuple(
        description
        for document in _entry_documents(record)
        if (description := _optional_string(document, "description")) is not None
    )
    if document_descriptions:
        return "; ".join(document_descriptions)
    return f"Docket entry {entry_number_text or 'unknown'}"


def _document_ids_from_legal_entry(record: Mapping[str, Any]) -> tuple[str, ...]:
    documents = _entry_documents(record)
    if not documents:
        return _document_ids(record)
    ids: list[str] = []
    for document in documents:
        document_id = _optional_string(document, "id")
        if document_id is not None:
            ids.append(document_id)
    return tuple(ids)


def _entry_documents(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    documents = record.get("documents")
    if not isinstance(documents, list):
        return ()
    return tuple(
        cast(Mapping[str, Any], document)
        for document in cast(list[object], documents)
        if isinstance(document, Mapping)
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "query"

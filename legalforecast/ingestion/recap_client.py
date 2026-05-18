"""RECAP fallback client with offline fixture transport support."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.ingestion.http_config import validate_https_base_url
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.logging import get_logger, pipeline_log_extra

DEFAULT_RECAP_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
RECAP_ALLOWED_BASE_HOSTS = frozenset({"www.courtlistener.com"})
RECAP_API_TOKEN_ENV = "RECAP_API_TOKEN"
COURTLISTENER_API_TOKEN_ENV = "COURTLISTENER_API_TOKEN"
RECAP_BASE_URL_ENV = "RECAP_BASE_URL"
RECAP_TIMEOUT_SECONDS_ENV = "RECAP_TIMEOUT_SECONDS"

_LOGGER = get_logger(__name__)


class RecapClientError(RuntimeError):
    """Base class for RECAP fallback client errors."""


class RecapAuthError(RecapClientError):
    """Raised for authentication or authorization failures."""


class RecapRateLimitError(RecapClientError):
    """Raised for rate-limit responses."""


class RecapServerError(RecapClientError):
    """Raised for retryable server responses."""


class RecapDocumentUnavailableError(RecapClientError):
    """Raised when a public RECAP document is unavailable."""


class RecapResponseError(RecapClientError):
    """Raised for malformed RECAP responses."""


@dataclass(frozen=True, slots=True)
class RecapConfig:
    """Runtime settings for RECAP fallback retrieval."""

    api_token: str | None = None
    base_url: str = DEFAULT_RECAP_BASE_URL
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RecapConfig:
        values = os.environ if environ is None else environ
        return cls(
            api_token=(
                _optional_text(values.get(RECAP_API_TOKEN_ENV))
                or _optional_text(values.get(COURTLISTENER_API_TOKEN_ENV))
            ),
            base_url=_base_url(values.get(RECAP_BASE_URL_ENV)),
            timeout_seconds=_positive_float(
                values.get(RECAP_TIMEOUT_SECONDS_ENV),
                RECAP_TIMEOUT_SECONDS_ENV,
                default=30.0,
            ),
        )


@dataclass(frozen=True, slots=True)
class RecapHTTPResponse:
    status_code: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=lambda: {})


class RecapTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapHTTPResponse: ...


@dataclass(frozen=True, slots=True)
class RecapDocument:
    recap_document_id: str
    docket_id: str | None
    docket_entry_id: str | None
    description: str | None
    plain_text: str | None
    download_url: str | None
    source_url: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RecapDocument:
        return cls(
            recap_document_id=_required_string(record, "id", "recap_document_id"),
            docket_id=_optional_string(record, "docket", "docket_id", "docketId"),
            docket_entry_id=_optional_string(
                record,
                "docket_entry",
                "docket_entry_id",
                "docketEntryId",
            ),
            description=_optional_string(record, "description", "short_description"),
            plain_text=_optional_string(record, "plain_text", "text", "ocr_text"),
            download_url=_optional_string(
                record,
                "download_url",
                "file",
                "filepath_local",
            ),
            source_url=_optional_string(record, "absolute_url", "url", "resource_uri"),
            raw=record,
        )

    @property
    def is_available(self) -> bool:
        return self.plain_text is not None or self.download_url is not None

    @property
    def availability_status(self) -> AvailabilityStatus:
        return (
            AvailabilityStatus.AVAILABLE
            if self.is_available
            else AvailabilityStatus.UNAVAILABLE
        )

    def to_provenance(
        self,
        *,
        source_case_id: str,
        court: str,
        docket_number: str,
        document_role: DocumentRole,
        retrieved_at: datetime,
        docket_entry_number: int | None = None,
        is_predecision_material: bool = True,
        is_mounted_for_model: bool = True,
        contains_target_outcome: bool = False,
    ) -> SourceDocumentProvenance:
        if is_mounted_for_model and not self.is_available:
            raise RecapDocumentUnavailableError(
                "unavailable RECAP document cannot be mounted for model use"
            )
        return SourceDocumentProvenance(
            source_provider="recap",
            source_case_id=source_case_id,
            source_document_id=self.recap_document_id,
            court=court,
            docket_number=docket_number,
            docket_entry_number=docket_entry_number,
            document_role=document_role,
            retrieved_at=retrieved_at,
            source_url_or_reference=(
                self.download_url or self.source_url or self.recap_document_id
            ),
            sha256=sha256_text(_hash_material(self)),
            is_predecision_material=is_predecision_material,
            is_mounted_for_model=is_mounted_for_model,
            availability_status=self.availability_status,
            contains_target_outcome=contains_target_outcome,
            notes=(
                None
                if self.plain_text is not None
                else "RECAP metadata was available without plain text content."
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "recap_document_id": self.recap_document_id,
            "docket_id": self.docket_id,
            "docket_entry_id": self.docket_entry_id,
            "description": self.description,
            "plain_text_available": self.plain_text is not None,
            "download_url": self.download_url,
            "source_url": self.source_url,
            "availability_status": self.availability_status.value,
        }


class UrlLibRecapTransport:
    """Network transport used only when explicitly configured by the caller."""

    def __init__(self, base_url: str) -> None:
        self._base_url = validate_https_base_url(
            base_url,
            field_name=RECAP_BASE_URL_ENV,
            allowed_hosts=RECAP_ALLOWED_BASE_HOSTS,
            error_type=RecapClientError,
        )

    def request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapHTTPResponse:
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
                return RecapHTTPResponse(
                    status_code=response.status,
                    payload=_json_payload(response.read()),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return RecapHTTPResponse(
                status_code=exc.code,
                payload=_json_payload(exc.read()),
                headers=dict(exc.headers.items()) if exc.headers else {},
            )
        except urllib.error.URLError as exc:
            raise RecapClientError(f"RECAP request failed: {exc.reason}") from exc


@dataclass(frozen=True, slots=True)
class RecordedRecapResponse:
    method: str
    path: str
    params: Mapping[str, Any]
    status_code: int
    payload: Mapping[str, Any]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RecordedRecapResponse:
        return cls(
            method=_required_string(record, "method").upper(),
            path=_required_string(record, "path"),
            params=_primitive_mapping(record.get("params", {}), "params"),
            status_code=_required_int(record, "status_code"),
            payload=_mapping(record.get("payload"), "payload"),
        )


class RecapFixtureTransport:
    """Replay recorded RECAP responses without network access."""

    def __init__(self, responses: Sequence[RecordedRecapResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    @classmethod
    def from_records(
        cls, records: Sequence[Mapping[str, Any]]
    ) -> RecapFixtureTransport:
        return cls(
            tuple(RecordedRecapResponse.from_record(record) for record in records)
        )

    @classmethod
    def from_jsonl(cls, path: str | Path) -> RecapFixtureTransport:
        responses: list[RecordedRecapResponse] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw: object = json.loads(line)
                if not isinstance(raw, Mapping):
                    raise RecapResponseError(
                        f"recorded response line {line_number} must be an object"
                    )
                responses.append(
                    RecordedRecapResponse.from_record(cast(Mapping[str, Any], raw))
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
    ) -> RecapHTTPResponse:
        del headers, timeout_seconds
        if not self._responses:
            raise RecapClientError("no recorded RECAP responses remain")
        response = self._responses.pop(0)
        normalized_method = method.upper()
        normalized_params = dict(params)
        self.requests.append((normalized_method, path, normalized_params))
        if response.method != normalized_method or response.path != path:
            raise RecapClientError("recorded RECAP response request mismatch")
        if dict(response.params) != normalized_params:
            raise RecapClientError("recorded RECAP response params mismatch")
        return RecapHTTPResponse(
            status_code=response.status_code,
            payload=response.payload,
        )


class RecapClient:
    def __init__(
        self,
        *,
        config: RecapConfig | None = None,
        transport: RecapTransport | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self.config = RecapConfig.from_env() if config is None else config
        self.transport = (
            UrlLibRecapTransport(self.config.base_url)
            if transport is None
            else transport
        )
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.request_count = 0

    def get_document(self, recap_document_id: str) -> RecapDocument:
        payload = self._request_json(
            "GET",
            f"/recap-documents/{recap_document_id}/",
            {},
        )
        return RecapDocument.from_record(payload)

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
                isinstance(error, RecapRateLimitError | RecapServerError)
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
            "RECAP request",
            extra={
                **pipeline_log_extra(
                    stage="recap_request",
                    request_count=self.request_count,
                    cost_usd=None,
                ),
                "recap_path": path,
                "recap_status_code": status_code,
            },
        )


def _error_for_response(response: RecapHTTPResponse, path: str) -> RecapClientError:
    message = _optional_string(response.payload, "detail", "error", "message") or (
        f"RECAP request to {path} failed with status {response.status_code}"
    )
    if response.status_code in {401, 403}:
        return RecapAuthError(message)
    if response.status_code == 404:
        return RecapDocumentUnavailableError(message)
    if response.status_code == 429:
        return RecapRateLimitError(message)
    if response.status_code >= 500:
        return RecapServerError(message)
    return RecapClientError(message)


def _hash_material(document: RecapDocument) -> str:
    if document.plain_text is not None:
        return document.plain_text
    return json.dumps(dict(document.raw), sort_keys=True)


def _json_payload(raw_body: bytes) -> Mapping[str, Any]:
    if not raw_body:
        return {}
    decoded: object = json.loads(raw_body.decode("utf-8"))
    return _mapping(decoded, "response payload")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecapResponseError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _primitive_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecapResponseError(f"{label} must be an object")
    result: dict[str, Any] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str) or not isinstance(
            item,
            str | int | float | bool,
        ):
            raise RecapResponseError(
                f"{label} must contain string keys and primitive values"
            )
        result[key] = item
    return result


def _required_string(record: Mapping[str, Any], *field_names: str) -> str:
    value = _optional_string(record, *field_names)
    if value is None:
        joined = ", ".join(field_names)
        raise RecapResponseError(f"missing required RECAP field: {joined}")
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
        raise RecapResponseError(f"{field_name} must be an integer")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _base_url(value: str | None) -> str:
    base_url = _optional_text(value) or DEFAULT_RECAP_BASE_URL
    return validate_https_base_url(
        base_url,
        field_name=RECAP_BASE_URL_ENV,
        allowed_hosts=RECAP_ALLOWED_BASE_HOSTS,
        error_type=RecapResponseError,
    )


def _positive_float(value: str | None, field_name: str, *, default: float) -> float:
    text = _optional_text(value)
    if text is None:
        return default
    try:
        parsed = float(text)
    except ValueError as exc:
        raise RecapResponseError(f"{field_name} must be a number") from exc
    if parsed <= 0:
        raise RecapResponseError(f"{field_name} must be positive")
    return parsed

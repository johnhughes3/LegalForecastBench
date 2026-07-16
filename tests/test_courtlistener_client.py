from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Self

import pytest
from legalforecast.ingestion import (
    CourtListenerAuthError,
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    CourtListenerRateLimitError,
    CourtListenerResponseError,
    CourtListenerServerError,
    CourtListenerUnavailableError,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_BASE_URL_ENV,
    CourtListenerDocketEntry,
    CourtListenerHTTPResponse,
    UrlLibCourtListenerTransport,
    _RejectCourtListenerRedirectHandler,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudget,
)


def test_courtlistener_reconstructs_public_docket_entries() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/123/",
                    payload={
                        "id": 123,
                        "court": "nysd",
                        "docket_number": "1:26-cv-00001",
                        "case_name": "Fixture v. Example",
                        "date_filed": "2026-05-01",
                        "absolute_url": "https://www.courtlistener.com/docket/123/",
                    },
                ),
                _response(
                    path="/docket-entries/",
                    params={"docket": "123", "page_size": 100},
                    payload={
                        "results": [
                            {
                                "id": 7001,
                                "docket": 123,
                                "entry_number": 12,
                                "description": "Motion to dismiss complaint",
                                "date_filed": "2026-05-03",
                                "recap_documents": [{"id": 9001}, {"id": "9002"}],
                                "absolute_url": (
                                    "https://www.courtlistener.com/docket/123/#entry-12"
                                ),
                            }
                        ],
                        "next": None,
                    },
                ),
            )
        ),
    )

    docket = client.get_docket("123")
    page = client.list_docket_entries("123", page_size=100)

    assert docket.docket_id == "123"
    assert docket.court_id == "nysd"
    assert docket.docket_number == "1:26-cv-00001"
    assert page.items[0].docket_entry_id == "7001"
    assert page.items[0].entry_number == "12"
    assert page.items[0].recap_document_ids == ("9001", "9002")
    assert page.items[0].has_recap_documents is True
    assert client.request_count == 2


def test_courtlistener_fetches_typed_opinion_cluster_and_opinion() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/clusters/10927691/",
                    payload={
                        "id": 10927691,
                        "docket": (
                            "https://www.courtlistener.com/api/rest/v4/"
                            "dockets/73614335/"
                        ),
                        "date_filed": "2026-07-14",
                        "blocked": False,
                        "absolute_url": "/opinion/10927691/example/",
                        "sub_opinions": [
                            "https://www.courtlistener.com/api/rest/v4/"
                            "opinions/11395231/"
                        ],
                    },
                ),
                _response(
                    path="/opinions/11395231/",
                    payload={
                        "id": 11395231,
                        "cluster": (
                            "https://www.courtlistener.com/api/rest/v4/"
                            "clusters/10927691/"
                        ),
                        "plain_text": "The motion to dismiss is denied.",
                        "local_path": "pdf/2026/07/14/example.pdf",
                        "download_url": "https://ecf.example/show_public_doc",
                        "absolute_url": "/opinion/10927691/example/",
                    },
                ),
            )
        ),
    )

    cluster = client.get_opinion_cluster("10927691")
    opinion = client.get_opinion("11395231")

    assert cluster.cluster_id == "10927691"
    assert cluster.docket_id == "73614335"
    assert cluster.date_filed == "2026-07-14"
    assert cluster.blocked is False
    assert cluster.sub_opinion_ids == ("11395231",)
    assert opinion.opinion_id == "11395231"
    assert opinion.cluster_id == "10927691"
    assert opinion.plain_text == "The motion to dismiss is denied."
    assert opinion.local_path == "pdf/2026/07/14/example.pdf"
    assert client.request_count == 2


def test_courtlistener_opinion_rejects_foreign_reference_shape() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/clusters/10927691/",
                    payload={
                        "id": 10927691,
                        "docket": "https://evil.example/dockets/73614335/",
                        "date_filed": "2026-07-14",
                        "blocked": False,
                        "sub_opinions": [],
                    },
                ),
            )
        ),
    )

    with pytest.raises(CourtListenerResponseError, match="docket reference shape"):
        client.get_opinion_cluster("10927691")


def test_courtlistener_live_v4_entry_with_blank_description_normalizes_to_blank() -> (
    None
):
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "courtlistener"
        / "docket-entry-with-blank-description-v4.json"
    )
    record = json.loads(fixture_path.read_text(encoding="utf-8"))

    entry = CourtListenerDocketEntry.from_record(record)

    assert entry.docket_entry_id == "469359369"
    assert entry.docket_id == "70649963"
    assert entry.entry_number == "86"
    assert entry.entry_text == ""
    assert entry.filed_at == "2026-06-30"
    assert entry.recap_document_ids == ("484692641",)
    assert entry.source_url is None


@pytest.mark.parametrize("description", ["", "   ", None])
def test_courtlistener_blank_docket_entry_description_normalizes_to_blank(
    description: str | None,
) -> None:
    entry = CourtListenerDocketEntry.from_record(
        {
            "id": 7001,
            "docket": 123,
            "description": description,
        }
    )

    assert entry.entry_text == ""


def test_courtlistener_blank_description_falls_back_to_entry_text_alias() -> None:
    entry = CourtListenerDocketEntry.from_record(
        {
            "id": 7001,
            "docket": 123,
            "description": "   ",
            "entry_text": "ORDER granting motion to dismiss",
        }
    )

    assert entry.entry_text == "ORDER granting motion to dismiss"


def test_courtlistener_missing_all_docket_entry_text_fields_fails_closed() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/docket-entries/",
                    params={"docket": "123"},
                    payload={"results": [{"id": 7001, "docket": 123}]},
                ),
            )
        ),
    )

    with pytest.raises(
        CourtListenerResponseError,
        match="one of description, entry_text, docket_text, or text is required",
    ):
        client.list_docket_entries("123")


@pytest.mark.parametrize(
    ("field_name", "description"),
    [
        (field_name, description)
        for field_name in ("description", "entry_text", "docket_text", "text")
        for description in (7, True, [], {})
    ],
)
def test_courtlistener_malformed_docket_entry_description_fails_closed(
    field_name: str,
    description: object,
) -> None:
    with pytest.raises(
        CourtListenerResponseError,
        match=rf"{field_name} must be a string or null",
    ):
        CourtListenerDocketEntry.from_record(
            {
                "id": 7001,
                "docket": 123,
                field_name: description,
            }
        )


def test_docket_entry_extracts_id_from_hyperlinked_foreign_key() -> None:
    entry = CourtListenerDocketEntry.from_record(
        {
            "id": 7001,
            "docket": "https://www.courtlistener.com/api/rest/v4/dockets/4328339/",
            "entry_number": 12,
            "description": "ORDER granting motion to dismiss",
            "date_filed": "2026-07-05",
        }
    )
    assert entry.docket_id == "4328339"


def test_docket_entry_accepts_bare_integer_foreign_key() -> None:
    entry = CourtListenerDocketEntry.from_record(
        {
            "id": 7001,
            "docket": 4328339,
            "description": "ORDER",
        }
    )
    assert entry.docket_id == "4328339"


def test_docket_entry_rejects_unrecognized_foreign_key_shape() -> None:
    with pytest.raises(CourtListenerResponseError, match="docket reference shape"):
        CourtListenerDocketEntry.from_record(
            {
                "id": 7001,
                "docket": "not-a-docket-reference",
                "description": "ORDER",
            }
        )


def test_courtlistener_unavailable_auth_rate_and_server_errors() -> None:
    unavailable = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/missing/",
                    status_code=404,
                    payload={"detail": "not found"},
                ),
            )
        ),
    )
    with pytest.raises(CourtListenerUnavailableError, match="not found"):
        unavailable.get_docket("missing")

    auth = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/123/",
                    status_code=403,
                    payload={"detail": "token required"},
                ),
            )
        ),
    )
    with pytest.raises(CourtListenerAuthError, match="token required"):
        auth.get_docket("123")

    limited = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/123/",
                    status_code=429,
                    payload={"detail": "too many requests"},
                ),
            )
        ),
        max_retries=0,
    )
    with pytest.raises(CourtListenerRateLimitError, match="too many requests"):
        limited.get_docket("123")

    server = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/123/",
                    status_code=503,
                    payload={"detail": "try later"},
                ),
            )
        ),
        max_retries=0,
    )
    with pytest.raises(CourtListenerServerError, match="try later"):
        server.get_docket("123")


def test_courtlistener_rate_limit_retries_before_success() -> None:
    reservations: list[tuple[str, str]] = []
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/dockets/123/",
                    status_code=429,
                    payload={"detail": "too many requests"},
                ),
                _response(
                    path="/dockets/123/",
                    payload={"id": 123, "case_name": "Retried v. Fixture"},
                ),
            )
        ),
        max_retries=1,
        before_request=lambda method, path: reservations.append((method, path)),
    )

    docket = client.get_docket("123")

    assert docket.case_name == "Retried v. Fixture"
    assert client.request_count == 2
    assert reservations == [("GET", "/dockets/123/"), ("GET", "/dockets/123/")]


def test_courtlistener_transport_timeout_retries_before_success() -> None:
    class TimeoutThenSuccess:
        def __init__(self) -> None:
            self.calls = 0

        def request(self, **_: object) -> CourtListenerHTTPResponse:
            self.calls += 1
            if self.calls == 1:
                raise CourtListenerServerError("CourtListener request timed out")
            return CourtListenerHTTPResponse(
                status_code=200,
                payload={"id": 123, "case_name": "Retried v. Fixture"},
            )

    transport = TimeoutThenSuccess()
    reservations: list[tuple[str, str]] = []
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=1,
        before_request=lambda method, path: reservations.append((method, path)),
    )

    docket = client.get_docket("123")

    assert docket.case_name == "Retried v. Fixture"
    assert transport.calls == 2
    assert client.request_count == 2
    assert reservations == [("GET", "/dockets/123/"), ("GET", "/dockets/123/")]


def test_urllib_transport_maps_bare_read_timeout_to_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def time_out(*_: object, **__: object) -> object:
        raise TimeoutError("read operation timed out")

    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    monkeypatch.setattr(transport._opener, "open", time_out)

    with pytest.raises(CourtListenerServerError, match="read operation timed out"):
        transport.request(
            method="GET",
            path="/dockets/123/",
            params={},
            headers={},
            timeout_seconds=1,
        )


@pytest.mark.parametrize(
    ("body", "reason"),
    (
        (b"", "empty"),
        (b'{"results":[', "malformed JSON"),
        (b"<html><body>upstream error</body></html>", "malformed JSON"),
        (b"{not-json}", "malformed JSON"),
    ),
    ids=("empty", "truncated", "html", "malformed-json"),
)
def test_urllib_transport_classifies_invalid_success_body_as_retryable(
    body: bytes,
    reason: str,
) -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener((body,))

    with pytest.raises(CourtListenerServerError, match=reason):
        transport.request(
            method="GET",
            path="/search/",
            params={"q": "motion to dismiss", "type": "r"},
            headers={},
            timeout_seconds=1,
        )


def test_invalid_search_body_retries_and_reconciles_durable_attempts(
    tmp_path: Path,
) -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener(
        (
            b"<html><body>temporary upstream error</body></html>",
            b'{"results":[],"next":null}',
        )
    )
    budget = CourtListenerRequestBudget(tmp_path / "requests.sqlite3")
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=1,
        before_request=budget.before_request,
    )

    page = client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert page.items == ()
    assert client.request_count == 2
    assert budget.local_reservations == 2
    assert budget.total_reservations() == 2
    assert transport._opener.request_count == 2


def test_valid_json_search_schema_error_is_not_retried(tmp_path: Path) -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener((b'{"results":"not-a-list"}',))
    budget = CourtListenerRequestBudget(tmp_path / "requests.sqlite3")
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=2,
        before_request=budget.before_request,
    )

    with pytest.raises(CourtListenerResponseError, match="results or items"):
        client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert client.request_count == 1
    assert budget.total_reservations() == 1
    assert transport._opener.request_count == 1


def test_invalid_error_body_preserves_nonretryable_http_status() -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener(
        (
            urllib.error.HTTPError(
                "https://www.courtlistener.com/api/rest/v4/search/",
                404,
                "Not Found",
                {},
                io.BytesIO(b""),
            ),
        )
    )
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=2,
    )

    with pytest.raises(CourtListenerUnavailableError, match="status 404"):
        client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert client.request_count == 1
    assert transport._opener.request_count == 1


@pytest.mark.parametrize(
    "body",
    (b"[]", b"null", b'"oops"'),
    ids=("list", "null", "string"),
)
def test_non_object_server_error_body_retries_before_success(body: bytes) -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener(
        (
            urllib.error.HTTPError(
                "https://www.courtlistener.com/api/rest/v4/search/",
                503,
                "Service Unavailable",
                {},
                io.BytesIO(body),
            ),
            b'{"results":[],"next":null}',
        )
    )
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=1,
    )

    page = client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert page.items == ()
    assert client.request_count == 2
    assert transport._opener.request_count == 2


def test_non_object_server_error_body_fails_closed_after_retries() -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener(
        tuple(
            urllib.error.HTTPError(
                "https://www.courtlistener.com/api/rest/v4/search/",
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b"[]"),
            )
            for _ in range(2)
        )
    )
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=1,
    )

    with pytest.raises(CourtListenerServerError, match="status 503"):
        client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert client.request_count == 2
    assert transport._opener.request_count == 2


def test_non_object_not_found_body_preserves_http_status() -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener(
        (
            urllib.error.HTTPError(
                "https://www.courtlistener.com/api/rest/v4/search/",
                404,
                "Not Found",
                {},
                io.BytesIO(b"[]"),
            ),
        )
    )
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=2,
    )

    with pytest.raises(CourtListenerUnavailableError, match="status 404"):
        client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert client.request_count == 1
    assert transport._opener.request_count == 1


def test_non_object_success_body_is_not_retried() -> None:
    transport = UrlLibCourtListenerTransport(
        "https://www.courtlistener.com/api/rest/v4"
    )
    transport._opener = _RawSequenceOpener((b"[]",))
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=transport,
        max_retries=2,
    )

    with pytest.raises(CourtListenerResponseError, match="must be an object"):
        client.search_raw({"q": "motion to dismiss", "type": "r"})

    assert client.request_count == 1
    assert transport._opener.request_count == 1


def test_authenticated_redirect_rejects_cross_host_before_forwarding_header() -> None:
    handler = _RejectCourtListenerRedirectHandler()
    original = urllib.request.Request(
        "https://www.courtlistener.com/api/rest/v4/dockets/123/",
        headers={"Authorization": "Token sentinel-secret"},
    )
    received_authorization: list[str | None] = []

    def record_if_forwarded(target: str) -> None:
        redirected = handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            target,
        )
        assert redirected is not None
        received_authorization.append(redirected.get_header("Authorization"))

    with pytest.raises(CourtListenerClientError, match="redirects are disabled"):
        record_if_forwarded("https://evil.example/collect")

    assert received_authorization == []


@pytest.mark.parametrize(
    "target",
    (
        "http://www.courtlistener.com/api/rest/v4/dockets/123/",
        "https://storage.courtlistener.com/api/rest/v4/dockets/123/",
        "https://www.courtlistener.com:444/api/rest/v4/dockets/123/",
        "https://user:password@www.courtlistener.com/api/rest/v4/dockets/123/",
    ),
    ids=("https-downgrade", "cross-host", "port-change", "credentials"),
)
def test_authenticated_redirect_policy_rejects_unsafe_target(target: str) -> None:
    handler = _RejectCourtListenerRedirectHandler()
    original = urllib.request.Request(
        "https://www.courtlistener.com/api/rest/v4/dockets/123/",
        headers={"Authorization": "Token sentinel-secret"},
    )

    with pytest.raises(CourtListenerClientError, match="redirects are disabled"):
        handler.redirect_request(original, None, 302, "Found", {}, target)


def test_authenticated_redirect_rejects_same_host_to_preserve_accounting() -> None:
    handler = _RejectCourtListenerRedirectHandler()
    original = urllib.request.Request(
        "https://www.courtlistener.com/api/rest/v4/dockets/123/",
        headers={"Authorization": "Token sentinel-secret"},
    )

    with pytest.raises(CourtListenerClientError, match="durable reservation"):
        handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "/api/rest/v4/dockets/123/?page=2",
        )


def test_courtlistener_page_extracts_cursor_from_next_url() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/docket-entries/",
                    params={"docket": "123", "page_size": 1},
                    payload={
                        "results": [
                            {
                                "id": 7001,
                                "docket": 123,
                                "description": "Motion to dismiss",
                            }
                        ],
                        "next": (
                            "https://www.courtlistener.com/api/rest/v4/"
                            "docket-entries/?cursor=abc123"
                        ),
                    },
                ),
                _response(
                    path="/docket-entries/",
                    params={"docket": "123", "cursor": "abc123", "page_size": 1},
                    payload={
                        "results": [
                            {
                                "id": 7002,
                                "docket": 123,
                                "description": "Opposition to motion to dismiss",
                            }
                        ],
                        "next": None,
                    },
                ),
            )
        ),
    )

    entries = tuple(client.iter_docket_entries("123", page_size=1))

    assert [entry.docket_entry_id for entry in entries] == ["7001", "7002"]


@pytest.mark.parametrize(
    "base_url",
    [
        "http://www.courtlistener.com/api/rest/v4",
        "https://www.courtlistener.com@evil.example/api/rest/v4",
        "https://evil.example/api/rest/v4",
        "https://www.courtlistener.com:444/api/rest/v4",
    ],
)
def test_courtlistener_config_rejects_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(CourtListenerResponseError, match=COURTLISTENER_BASE_URL_ENV):
        CourtListenerConfig.from_env({COURTLISTENER_BASE_URL_ENV: base_url})


def _response(
    *,
    method: str = "GET",
    path: str,
    params: dict[str, object] | None = None,
    status_code: int = 200,
    payload: dict[str, object],
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method=method,
        path=path,
        params={} if params is None else params,
        status_code=status_code,
        payload=payload,
    )


class _RawResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self._body = body
        self.status = status
        self.headers: dict[str, str] = {"Content-Type": "application/json"}

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    def read(self) -> bytes:
        return self._body


class _RawSequenceOpener:
    def __init__(self, responses: tuple[bytes | BaseException, ...]) -> None:
        self._responses = list(responses)
        self.request_count = 0

    def open(self, *_: object, **__: object) -> _RawResponse:
        self.request_count += 1
        if not self._responses:
            raise AssertionError("unexpected additional CourtListener request")
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return _RawResponse(response)

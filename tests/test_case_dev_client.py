from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPMessage
from io import BytesIO
from types import TracebackType
from typing import Any, Self, cast

import legalforecast.ingestion.case_dev_client as case_dev_client_module
import pytest
from legalforecast.ingestion import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevFixtureTransport,
    CaseDevRateLimitError,
    CaseDevResponseError,
)
from legalforecast.ingestion.case_dev_client import (
    CaseDevRateLimiter,
    RecordedCaseDevResponse,
    UrlLibCaseDevTransport,
)
from legalforecast.ingestion.case_dev_config import (
    CASE_DEV_API_KEY_ENV,
    CaseDevConfig,
    CaseDevConfigError,
)


def _config() -> CaseDevConfig:
    return CaseDevConfig(
        api_key=None,
        base_url="https://api.case.dev",
        estimated_cost_per_request_usd=0.05,
    )


def _recorded_response(
    *,
    method: str = "POST",
    path: str = "/legal/v1/docket",
    params: dict[str, object] | None = None,
    status_code: int = 200,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> RecordedCaseDevResponse:
    return RecordedCaseDevResponse(
        method=method,
        path=path,
        params={} if params is None else params,
        status_code=status_code,
        payload={} if payload is None else payload,
        headers={} if headers is None else headers,
    )


class _FakeURLResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = body
        self.status = status
        self.headers = {} if headers is None else headers

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc, traceback
        return False


class _CallbackOpener:
    def __init__(self, callback: object) -> None:
        self._callback = callback

    def open(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        callback = self._callback
        assert callable(callback)
        return callback(request, timeout=timeout)


class _SequenceOpener:
    def __init__(self, *responses: _FakeURLResponse | BaseException) -> None:
        self._responses = list(responses)
        self.requests: list[urllib.request.Request] = []

    def open(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        del timeout
        self.requests.append(request)
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _redirect(
    *,
    source_url: str,
    target_url: str,
    status: int = 302,
) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        source_url,
        status,
        "Redirect",
        {"Location": target_url},
        BytesIO(b""),
    )


def test_default_transport_installs_handler_that_disables_automatic_redirects() -> None:
    transport = UrlLibCaseDevTransport("https://api.case.dev")
    handlers = transport._opener.handlers
    handler = next(
        item
        for item in handlers
        if isinstance(item, case_dev_client_module._NoAutomaticRedirectHandler)
    )
    request = urllib.request.Request(
        "https://api.case.dev/v1/documents/doc-1",
        headers={"Authorization": "Bearer case-dev-token"},
    )

    redirected = handler.redirect_request(
        request,
        BytesIO(b""),
        302,
        "Redirect",
        HTTPMessage(),
        "https://attacker.example/steal",
    )

    assert redirected is None


def test_search_docket_entries_parses_successful_response() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss", "limit": 2},
                payload={
                    "dockets": [
                        {
                            "id": "docket-1",
                            "caseName": "Fixture v. Example",
                            "docketNumber": "1:26-cv-00001",
                            "court": "S.D.N.Y.",
                            "dateFiled": "2026-05-01",
                            "url": "https://case.dev/example",
                        }
                    ],
                },
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    page = client.search_docket_entries("motion to dismiss", limit=2)

    assert len(page.items) == 1
    assert page.items[0].case_id == "docket-1"
    assert page.items[0].docket_entry_id == "docket-1:search:motion-to-dismiss"
    assert "motion to dismiss" in page.items[0].entry_text
    assert page.items[0].filed_at == "2026-05-01"
    assert client.request_count == 1
    assert client.usage_estimate().estimated_cost_usd == pytest.approx(0.05)


def test_search_docket_entries_surfaces_explicit_next_offset() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss", "limit": 1},
                payload={
                    "dockets": [
                        {
                            "id": "docket-1",
                            "caseName": "Fixture v. Example",
                        }
                    ],
                    "nextOffset": 1,
                },
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    page = client.search_docket_entries("motion to dismiss", limit=1)

    assert page.next_cursor == "1"


def test_search_docket_entries_ignores_null_cursor_before_later_offset() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss", "limit": 1},
                payload={
                    "dockets": [],
                    "next_cursor": None,
                    "nextCursor": None,
                    "nextOffset": "07",
                },
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    page = client.search_docket_entries("motion to dismiss", limit=1)

    assert page.next_cursor == "7"


def test_search_docket_entries_rejects_conflicting_continuations() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss"},
                payload={
                    "dockets": [],
                    "nextCursor": "opaque-cursor",
                    "nextOffset": 2,
                },
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    with pytest.raises(CaseDevResponseError, match="conflicting continuation"):
        client.search_docket_entries("motion to dismiss")


@pytest.mark.parametrize("next_offset", [True, -1, 1.5, "", "not-a-number"])
def test_search_docket_entries_rejects_malformed_next_offset(
    next_offset: object,
) -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss"},
                payload={"dockets": [], "nextOffset": next_offset},
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    with pytest.raises(CaseDevResponseError, match="nextOffset"):
        client.search_docket_entries("motion to dismiss")


def test_search_response_missing_required_fields_fails() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "motion to dismiss"},
                payload={"dockets": [{"caseName": "Fixture v. Example"}]},
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    with pytest.raises(CaseDevResponseError, match="id"):
        client.search_docket_entries("motion to dismiss")


def test_docket_entries_use_doc_description_when_entry_description_missing() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={
                    "type": "lookup",
                    "docketId": "case-1",
                    "includeEntries": True,
                },
                payload={
                    "docket": {
                        "id": "case-1",
                        "entries": [
                            {
                                "entryNumber": 7,
                                "date": "2026-05-01",
                                "description": None,
                                "documents": [
                                    {
                                        "id": "doc-7",
                                        "description": "Order on Motion to Dismiss",
                                    }
                                ],
                            }
                        ],
                    }
                },
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    page = client.get_case_docket_entries("case-1")

    assert page.items[0].entry_text == "Order on Motion to Dismiss"
    assert page.items[0].source_document_ids == ("doc-7",)


def test_docket_entries_without_ids_get_distinct_content_based_identities() -> None:
    entries = [
        {
            "entryNumber": 7,
            "date": "2026-05-01",
            "description": "First event",
            "documents": [{"id": "doc-7"}],
        },
        {
            "entryNumber": 7,
            "date": "2026-05-02",
            "description": "Second event",
            "documents": [{"id": "doc-8"}],
        },
    ]
    response = _recorded_response(
        params={
            "type": "lookup",
            "docketId": "case-1",
            "includeEntries": True,
        },
        payload={"docket": {"id": "case-1", "entries": entries}},
    )
    client = CaseDevClient(
        config=_config(), transport=CaseDevFixtureTransport([response])
    )

    page = client.get_case_docket_entries("case-1")

    assert len({item.docket_entry_id for item in page.items}) == 2
    assert all(item.docket_entry_id.startswith("entry-7-") for item in page.items)


def test_iter_docket_entry_search_caps_results() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "Rule 12", "limit": 1},
                payload={
                    "dockets": [
                        {
                            "id": "case-1",
                            "caseName": "Rule 12 Plaintiff v. One",
                            "docketNumber": "1:26-cv-00001",
                            "court": "S.D.N.Y.",
                        },
                        {
                            "id": "case-2",
                            "caseName": "Rule 12 Plaintiff v. Two",
                            "docketNumber": "1:26-cv-00002",
                            "court": "D. Del.",
                        },
                    ]
                },
            ),
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    results = list(
        client.iter_docket_entry_search("Rule 12", page_size=1, max_results=1)
    )

    assert [hit.case_id for hit in results] == ["case-1"]
    assert client.request_count == 1


def test_rate_limit_retries_before_success() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "MTD"},
                status_code=429,
                payload={"error": "slow down"},
            ),
            _recorded_response(
                params={"type": "search", "query": "MTD"},
                payload={"dockets": []},
            ),
        ]
    )
    client = CaseDevClient(
        config=_config(),
        transport=transport,
        max_retries=1,
        rate_limiter=CaseDevRateLimiter(
            rate_limit_per_minute=None,
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        retry_jitter=lambda _upper: 0.0,
    )

    page = client.search_docket_entries("MTD")

    assert page.items == ()
    assert client.request_count == 2


def test_rate_limit_honors_retry_after_on_shared_governor() -> None:
    now = 100.0
    sleep_calls: list[float] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleep_calls.append(seconds)
        now += seconds

    limiter = CaseDevRateLimiter(
        rate_limit_per_minute=None,
        monotonic=monotonic,
        sleep=sleep,
    )
    client = CaseDevClient(
        config=_config(),
        transport=CaseDevFixtureTransport(
            [
                _recorded_response(
                    params={"type": "search", "query": "MTD"},
                    status_code=429,
                    payload={"error": "slow down"},
                    headers={"Retry-After": "7"},
                ),
                _recorded_response(
                    params={"type": "search", "query": "MTD"},
                    payload={"dockets": []},
                ),
            ]
        ),
        max_retries=1,
        rate_limiter=limiter,
        retry_jitter=lambda _upper: 0.0,
    )

    assert client.search_docket_entries("MTD").items == ()
    assert sleep_calls == pytest.approx([7.0])


def test_rate_limit_honors_http_date_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 100.0
    sleep_calls: list[float] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleep_calls.append(seconds)
        now += seconds

    monkeypatch.setattr(case_dev_client_module.time, "time", lambda: 0.0)
    limiter = CaseDevRateLimiter(
        rate_limit_per_minute=None,
        monotonic=monotonic,
        sleep=sleep,
    )
    client = CaseDevClient(
        config=_config(),
        transport=CaseDevFixtureTransport(
            [
                _recorded_response(
                    params={"type": "search", "query": "MTD"},
                    status_code=429,
                    payload={"error": "slow down"},
                    headers={"Retry-After": "Thu, 01 Jan 1970 00:00:07 GMT"},
                ),
                _recorded_response(
                    params={"type": "search", "query": "MTD"},
                    payload={"dockets": []},
                ),
            ]
        ),
        max_retries=1,
        rate_limiter=limiter,
        retry_jitter=lambda _upper: 0.0,
    )

    assert client.search_docket_entries("MTD").items == ()
    assert sleep_calls == pytest.approx([7.0])


def test_rate_limit_uses_bounded_exponential_shared_cooldown() -> None:
    now = 100.0
    sleep_calls: list[float] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleep_calls.append(seconds)
        now += seconds

    limiter = CaseDevRateLimiter(
        rate_limit_per_minute=None,
        monotonic=monotonic,
        sleep=sleep,
    )
    responses = [
        _recorded_response(
            params={"type": "search", "query": "MTD"},
            status_code=429,
            payload={"error": "slow down"},
        ),
        _recorded_response(
            params={"type": "search", "query": "MTD"},
            status_code=429,
            payload={"error": "still slow"},
        ),
        _recorded_response(
            params={"type": "search", "query": "MTD"},
            payload={"dockets": []},
        ),
    ]
    client = CaseDevClient(
        config=_config(),
        transport=CaseDevFixtureTransport(responses),
        max_retries=2,
        rate_limiter=limiter,
        retry_jitter=lambda _upper: 0.0,
    )

    assert client.search_docket_entries("MTD").items == ()
    assert sleep_calls == pytest.approx([5.0, 10.0])


def test_terminal_rate_limit_opens_shared_circuit_before_returning() -> None:
    now = 100.0
    sleep_calls: list[float] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleep_calls.append(seconds)
        now += seconds

    limiter = CaseDevRateLimiter(
        rate_limit_per_minute=None,
        monotonic=monotonic,
        sleep=sleep,
    )
    limited_transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "MTD"},
                status_code=429,
                payload={"error": "slow down"},
                headers={"Retry-After": "11"},
            )
        ]
    )
    sibling_transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "sibling"},
                payload={"dockets": []},
            )
        ]
    )
    limited = CaseDevClient(
        config=_config(),
        transport=limited_transport,
        max_retries=0,
        rate_limiter=limiter,
        retry_jitter=lambda _upper: 0.0,
    )
    sibling = CaseDevClient(
        config=_config(),
        transport=sibling_transport,
        max_retries=0,
        rate_limiter=limiter,
        retry_jitter=lambda _upper: 0.0,
    )

    with pytest.raises(CaseDevRateLimitError, match="slow down"):
        limited.search_docket_entries("MTD")
    with pytest.raises(CaseDevRateLimitError, match="circuit is open"):
        sibling.search_docket_entries("sibling")

    assert sleep_calls == pytest.approx([11.0])
    assert len(limited_transport.requests) == 1
    assert sibling_transport.requests == []


def test_url_timeout_retries_before_success() -> None:
    calls = 0

    def fake_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        del request, timeout
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("read operation timed out")
        return _FakeURLResponse(b'{"dockets": []}', status=200)

    client = CaseDevClient(
        config=_config(),
        transport=UrlLibCaseDevTransport(
            "https://api.case.dev",
            _opener=_CallbackOpener(fake_urlopen),
        ),
        max_retries=1,
    )

    page = client.search_docket_entries("MTD")

    assert page.items == ()
    assert client.request_count == 2


def test_configured_rate_limit_spaces_request_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter([100.0, 100.25, 101.0])
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        case_dev_client_module.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(case_dev_client_module.time, "sleep", sleep_calls.append)
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "lookup", "docketId": "case-1"},
                payload={"id": "case-1", "caption": "One v. Fixture"},
            ),
            _recorded_response(
                params={"type": "lookup", "docketId": "case-2"},
                payload={"id": "case-2", "caption": "Two v. Fixture"},
            ),
        ]
    )
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key=None,
            base_url="https://api.case.dev",
            rate_limit_per_minute=60,
        ),
        transport=transport,
    )

    assert client.get_case("case-1").case_id == "case-1"
    assert client.get_case("case-2").case_id == "case-2"

    assert sleep_calls == pytest.approx([0.75])


def test_shared_rate_limiter_applies_one_aggregate_cap_across_clients() -> None:
    now = 100.0
    sleep_calls: list[float] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleep_calls.append(seconds)
        now += seconds

    config = CaseDevConfig(
        api_key=None,
        base_url="https://api.case.dev",
        rate_limit_per_minute=60,
    )
    limiter = CaseDevRateLimiter(
        rate_limit_per_minute=60,
        monotonic=monotonic,
        sleep=sleep,
    )
    clients = tuple(
        CaseDevClient(
            config=config,
            transport=CaseDevFixtureTransport(
                [
                    _recorded_response(
                        params={"type": "lookup", "docketId": case_id},
                        payload={"id": case_id, "caption": f"{case_id} v. Fixture"},
                    )
                ]
            ),
            rate_limiter=limiter,
        )
        for case_id in ("case-1", "case-2", "case-3", "case-4", "case-5")
    )
    barrier = threading.Barrier(6)

    def get_case(client: CaseDevClient, case_id: str) -> str:
        barrier.wait()
        return client.get_case(case_id).case_id

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = tuple(
            executor.submit(get_case, client, f"case-{index}")
            for index, client in enumerate(clients, start=1)
        )
        barrier.wait()
        assert {future.result() for future in futures} == {
            "case-1",
            "case-2",
            "case-3",
            "case-4",
            "case-5",
        }

    assert sleep_calls == pytest.approx([1.0, 1.0, 1.0, 1.0])


@pytest.mark.parametrize("invalid_limit", [True, 1.0, float("nan")])
def test_rate_limiter_rejects_non_concrete_integer_limits(
    invalid_limit: object,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        CaseDevRateLimiter(rate_limit_per_minute=cast(Any, invalid_limit))


def test_rate_limit_without_retry_raises() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                params={"type": "search", "query": "MTD"},
                status_code=429,
                payload={"error": "slow down"},
            )
        ]
    )
    client = CaseDevClient(
        config=_config(),
        transport=transport,
        max_retries=0,
        rate_limiter=CaseDevRateLimiter(
            rate_limit_per_minute=None,
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        retry_jitter=lambda _upper: 0.0,
    )

    with pytest.raises(CaseDevRateLimitError, match="slow down"):
        client.search_docket_entries("MTD")


def test_auth_failure_is_classified() -> None:
    transport = CaseDevFixtureTransport(
        [
            _recorded_response(
                path="/legal/v1/docket",
                params={"type": "lookup", "docketId": "case-1"},
                status_code=401,
                payload={"error": "bad token"},
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport)

    with pytest.raises(CaseDevAuthError, match="bad token"):
        client.get_case("case-1")


def test_recorded_jsonl_fixture_replay(tmp_path) -> None:
    fixture_path = tmp_path / "case_dev.jsonl"
    fixture_path.write_text(
        json.dumps(
            {
                "method": "GET",
                "path": "/v1/documents/doc-1",
                "params": {},
                "status_code": 200,
                "payload": {
                    "document_id": "doc-1",
                    "case_id": "case-1",
                    "document_type": "motion",
                    "text": "Motion to dismiss",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = CaseDevClient(
        config=_config(),
        transport=CaseDevFixtureTransport.from_jsonl(fixture_path),
    )

    document = client.get_document("doc-1")

    assert document.document_id == "doc-1"
    assert document.case_id == "case-1"
    assert document.text == "Motion to dismiss"


def test_live_client_default_configuration_refuses_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CASE_DEV_API_KEY_ENV, raising=False)

    def fail_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        del request, timeout
        raise AssertionError("live case.dev tests must not open sockets by default")

    monkeypatch.setattr(case_dev_client_module.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(CaseDevConfigError, match=CASE_DEV_API_KEY_ENV):
        CaseDevClient.live_from_env()


def test_url_lib_transport_builds_url_headers_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["accept"] = request.get_header("Accept")
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _FakeURLResponse(
            b'{"ok": true}',
            status=200,
            headers={"X-Trace-Id": "trace-1"},
        )

    monkeypatch.setattr(case_dev_client_module.urllib.request, "urlopen", fake_urlopen)

    response = UrlLibCaseDevTransport(
        "https://api.case.dev/",
        _opener=_CallbackOpener(fake_urlopen),
    ).request(
        method="GET",
        path="/v1/dockets/search",
        params={"q": "motion to dismiss", "limit": "2"},
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer case-dev-token",
        },
        timeout_seconds=12.5,
    )

    assert captured == {
        "url": "https://api.case.dev/v1/dockets/search?q=motion+to+dismiss&limit=2",
        "method": "GET",
        "accept": "application/json",
        "authorization": "Bearer case-dev-token",
        "timeout": 12.5,
    }
    assert response.status_code == 200
    assert response.payload == {"ok": True}
    assert response.headers == {"X-Trace-Id": "trace-1"}


def test_url_lib_transport_posts_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = request.data
        captured["timeout"] = timeout
        return _FakeURLResponse(b'{"ok": true}', status=200)

    monkeypatch.setattr(case_dev_client_module.urllib.request, "urlopen", fake_urlopen)

    response = UrlLibCaseDevTransport(
        "https://api.case.dev/",
        _opener=_CallbackOpener(fake_urlopen),
    ).request(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": "motion to dismiss", "limit": 2},
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer case-dev-token",
        },
        timeout_seconds=12.5,
    )

    assert captured["url"] == "https://api.case.dev/legal/v1/docket"
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/json"
    assert json.loads(captured["body"]) == {
        "type": "search",
        "query": "motion to dismiss",
        "limit": 2,
    }
    assert captured["timeout"] == 12.5
    assert response.payload == {"ok": True}


def test_url_lib_transport_returns_http_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        del request, timeout
        raise urllib.error.HTTPError(
            "https://api.case.dev/v1/cases/case-1",
            403,
            "Forbidden",
            {"X-Request-Id": "req-1"},
            BytesIO(b'{"error": "bad token"}'),
        )

    monkeypatch.setattr(case_dev_client_module.urllib.request, "urlopen", fake_urlopen)

    response = UrlLibCaseDevTransport(
        "https://api.case.dev",
        _opener=_CallbackOpener(fake_urlopen),
    ).request(
        method="GET",
        path="/v1/cases/case-1",
        params={},
        headers={"Accept": "application/json"},
        timeout_seconds=10.0,
    )

    assert response.status_code == 403
    assert response.payload == {"error": "bad token"}
    assert response.headers == {"X-Request-Id": "req-1"}


def test_url_lib_transport_classifies_url_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _FakeURLResponse:
        del request, timeout
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(case_dev_client_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(
        case_dev_client_module.CaseDevClientError,
        match=r"case\.dev request failed: connection refused",
    ):
        UrlLibCaseDevTransport(
            "https://api.case.dev",
            _opener=_CallbackOpener(fake_urlopen),
        ).request(
            method="GET",
            path="/v1/cases/case-1",
            params={},
            headers={"Accept": "application/json"},
            timeout_seconds=10.0,
        )


@pytest.mark.parametrize(
    "target_url",
    (
        "https://attacker.example/steal",
        "http://api.case.dev/v1/documents/doc-1",
    ),
)
def test_authenticated_get_rejects_untrusted_redirect_before_second_request(
    target_url: str,
) -> None:
    source_url = "https://api.case.dev/v1/documents/doc-1"
    opener = _SequenceOpener(
        _redirect(source_url=source_url, target_url=target_url),
    )
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key="case-dev-token",
            base_url="https://api.case.dev",
        ),
        transport=UrlLibCaseDevTransport(
            "https://api.case.dev",
            _opener=opener,
        ),
        max_retries=0,
    )

    with pytest.raises(case_dev_client_module.CaseDevRedirectError):
        client.get_document("doc-1")

    assert client.request_count == 1
    assert len(opener.requests) == 1
    assert opener.requests[0].get_header("Authorization") == ("Bearer case-dev-token")


def test_authenticated_get_follows_same_origin_redirect_with_auth() -> None:
    source_url = "https://api.case.dev/v1/documents/doc-1"
    opener = _SequenceOpener(
        _redirect(source_url=source_url, target_url="/v1/documents/doc-1-final"),
        _FakeURLResponse(b'{"ok": true}', status=200),
    )
    response = UrlLibCaseDevTransport(
        "https://api.case.dev",
        _opener=opener,
    ).request(
        method="GET",
        path="/v1/documents/doc-1",
        params={},
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer case-dev-token",
        },
        timeout_seconds=10.0,
    )

    assert response.payload == {"ok": True}
    assert [request.full_url for request in opener.requests] == [
        source_url,
        "https://api.case.dev/v1/documents/doc-1-final",
    ]
    assert opener.requests[1].get_header("Authorization") == ("Bearer case-dev-token")


def test_authenticated_get_revalidates_every_redirect_hop() -> None:
    source_url = "https://api.case.dev/v1/documents/doc-1"
    same_origin_url = "https://api.case.dev/v1/documents/intermediate"
    opener = _SequenceOpener(
        _redirect(source_url=source_url, target_url=same_origin_url),
        _redirect(
            source_url=same_origin_url,
            target_url="https://attacker.example/second-hop",
        ),
    )
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key="case-dev-token",
            base_url="https://api.case.dev",
        ),
        transport=UrlLibCaseDevTransport(
            "https://api.case.dev",
            _opener=opener,
        ),
        max_retries=0,
    )

    with pytest.raises(case_dev_client_module.CaseDevRedirectError):
        client.get_document("doc-1")

    assert client.request_count == 1
    assert len(opener.requests) == 2
    assert all(
        request.full_url.startswith("https://api.case.dev/")
        for request in opener.requests
    )


@pytest.mark.parametrize("status", tuple(range(300, 400)))
def test_paid_post_never_follows_any_redirect_status(status: int) -> None:
    source_url = "https://api.case.dev/legal/v1/documents/doc-1/pacer"
    opener = _SequenceOpener(
        _redirect(
            source_url=source_url,
            target_url="https://api.case.dev/redirected-purchase",
            status=status,
        )
    )
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key="case-dev-token",
            base_url="https://api.case.dev",
        ),
        transport=UrlLibCaseDevTransport(
            "https://api.case.dev",
            _opener=opener,
        ),
        max_retries=0,
    )

    with pytest.raises(case_dev_client_module.CaseDevPurchaseOutcomeUnknownError):
        client.purchase_pacer_document("doc-1", acknowledge_pacer_fees=True)

    assert client.request_count == 1
    assert len(opener.requests) == 1
    assert opener.requests[0].get_method() == "POST"


@pytest.mark.case_dev_live
def test_live_case_dev_client_can_be_constructed_when_enabled() -> None:
    client = CaseDevClient.live_from_env()

    assert client.config.live_tests_available is True

from __future__ import annotations

import re

import legalforecast.ingestion.firecrawl_source as firecrawl_source
import pytest
from legalforecast.ingestion.firecrawl_source import (
    FIRECRAWL_SCRAPE_ENDPOINT,
    FirecrawlAuthError,
    FirecrawlChallengeError,
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlMissingAPIKeyError,
    FirecrawlPaymentRequiredError,
    FirecrawlRateLimitError,
    FirecrawlResponseError,
    FirecrawlServerError,
    FirecrawlTargetHTTPError,
    FirecrawlURLValidationError,
    UrlLibFirecrawlTransport,
    canonicalize_courtlistener_source_url,
    validate_courtlistener_recap_search_url,
)

_URL = "https://www.courtlistener.com/docket/70649963/sam-v-easy-honda/"


def test_url_lib_transport_classifies_socket_read_timeout_as_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError("read operation timed out")

    monkeypatch.setattr(firecrawl_source.urllib.request, "urlopen", timeout)

    with pytest.raises(FirecrawlServerError) as raised:
        UrlLibFirecrawlTransport().scrape(
            endpoint=FIRECRAWL_SCRAPE_ENDPOINT,
            headers={"Authorization": "Bearer redacted"},
            payload={"url": _URL},
            timeout_seconds=1.0,
        )

    assert raised.value.failure_code == "provider_server_error"
    assert raised.value.transient is True
    assert str(raised.value) == (
        "Firecrawl request failed before receiving an HTTP response"
    )


def _success_response(
    *,
    status_code: int = 200,
    proxy_used: str = "basic",
    cache_state: str = "miss",
    credits_used: float = 1,
    source_url: str = _URL,
) -> FirecrawlHTTPResponse:
    return FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": "<html><table id='docket-entry-table'></table></html>",
                "metadata": {
                    "statusCode": status_code,
                    "proxyUsed": proxy_used,
                    "cacheState": cache_state,
                    "creditsUsed": credits_used,
                    "sourceURL": source_url,
                },
            },
        },
    )


def test_source_posts_exact_bounded_request_once_and_returns_raw_html() -> None:
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    raw_html = source.fetch(docket_id="70649963", source_url=_URL)

    assert raw_html == "<html><table id='docket-entry-table'></table></html>"
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request["endpoint"] == FIRECRAWL_SCRAPE_ENDPOINT
    assert request["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    assert request["timeout_seconds"] == 70.0
    assert request["payload"] == {
        "url": _URL,
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
    }
    assert "redactPII" not in request["payload"]


def test_scrape_exposes_validated_cost_and_delivery_metadata() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport([_success_response()]),
    )

    result = source.scrape(docket_id="70649963", source_url=_URL)

    assert result.target_status_code == 200
    assert result.proxy_requested == "basic"
    assert result.proxy_used == "basic"
    assert result.cache_state == "miss"
    assert result.credits_used == 1.0
    assert result.resolved_url == canonicalize_courtlistener_source_url(_URL)


@pytest.mark.parametrize(
    "raw_html",
    [
        "<html><title>Attention Required! | Cloudflare</title></html>",
        "<script src='/cdn-cgi/challenge-platform/h/g/orchestrate'></script>",
        "<div id='cf-chl-widget'>Checking your browser before accessing</div>",
    ],
)
def test_marker_confirmed_challenge_html_stops_as_infrastructure_failure(
    raw_html: str,
) -> None:
    response = _success_response()
    payload = dict(response.payload)
    data = dict(payload["data"])  # type: ignore[arg-type]
    data["rawHtml"] = raw_html
    payload["data"] = data
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [FirecrawlHTTPResponse(status_code=200, payload=payload)]
        ),
    )

    with pytest.raises(FirecrawlChallengeError) as raised:
        source.scrape(docket_id="70649963", source_url=_URL)

    assert raised.value.failure_code == "courtlistener_challenge_html"
    assert raised.value.provider_http_status == 200
    assert re.fullmatch(r"[0-9a-f]{64}", raised.value.response_sha256 or "")
    assert raw_html not in raised.value.safe_message


def test_normal_page_mentioning_cloudflare_is_not_a_confirmed_challenge() -> None:
    response = _success_response()
    payload = dict(response.payload)
    data = dict(payload["data"])  # type: ignore[arg-type]
    data["rawHtml"] = "<html><p>CourtListener uses Cloudflare.</p></html>"
    payload["data"] = data
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [FirecrawlHTTPResponse(status_code=200, payload=payload)]
        ),
    )

    assert source.scrape(docket_id="70649963", source_url=_URL).raw_html


def test_resolved_docket_url_allows_safe_same_identity_redirect() -> None:
    redirected_same_docket = "https://courtlistener.com/docket/70649963/canonical-slug/"
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [_success_response(source_url=redirected_same_docket)]
        ),
    )

    result = source.scrape(docket_id="70649963", source_url=_URL)

    assert result.resolved_url == ("https://www.courtlistener.com/docket/70649963/")


def test_resolved_docket_url_mismatch_fails_closed_with_safe_evidence() -> None:
    secret_slug = "must-not-be-persisted"
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [
                _success_response(
                    source_url=(
                        f"https://www.courtlistener.com/docket/999/{secret_slug}/"
                    )
                )
            ]
        ),
    )

    with pytest.raises(FirecrawlResponseError) as raised:
        source.scrape(docket_id="70649963", source_url=_URL)

    error = raised.value
    assert error.failure_code == "resolved_url_mismatch"
    assert error.transient is False
    assert error.provider_http_status == 200
    assert re.fullmatch(r"[0-9a-f]{64}", error.response_sha256 or "")
    assert secret_slug not in error.safe_message


def test_success_without_resolved_source_url_fails_closed() -> None:
    response = _success_response()
    payload = dict(response.payload)
    data = dict(payload["data"])  # type: ignore[arg-type]
    metadata = dict(data["metadata"])  # type: ignore[arg-type]
    metadata.pop("sourceURL")
    data["metadata"] = metadata
    payload["data"] = data
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [FirecrawlHTTPResponse(status_code=200, payload=payload)]
        ),
    )

    with pytest.raises(FirecrawlResponseError) as raised:
        source.scrape(docket_id="70649963", source_url=_URL)

    assert raised.value.failure_code == "resolved_url_missing"


def test_auto_proxy_is_bounded_to_five_credits_and_reports_actual_proxy() -> None:
    transport = FirecrawlFixtureTransport(
        [_success_response(proxy_used="stealth", credits_used=5)]
    )
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"), transport=transport
    )

    result = source.scrape(docket_id="70649963", source_url=_URL)

    assert transport.requests[0]["payload"]["proxy"] == "auto"  # type: ignore[index]
    assert result.proxy_requested == "auto"
    assert result.proxy_used == "stealth"
    assert result.credits_used == 5.0


@pytest.mark.parametrize(
    ("proxy", "proxy_used", "expected_credit_cap"),
    [
        ("basic", "basic", 1),
        ("auto", "basic", 5),
        ("enhanced", "stealth", 5),
    ],
)
def test_force_browser_adds_only_bounded_wait_action_without_changing_credit_cap(
    proxy: str, proxy_used: str, expected_credit_cap: int
) -> None:
    transport = FirecrawlFixtureTransport(
        [_success_response(proxy_used=proxy_used, credits_used=expected_credit_cap)]
    )
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(
            api_key="test-key",
            proxy=proxy,  # type: ignore[arg-type]
            force_browser=True,
        ),
        transport=transport,
    )

    result = source.scrape(docket_id="70649963", source_url=_URL)

    payload = transport.requests[0]["payload"]
    assert payload["actions"] == [{"type": "wait", "milliseconds": 1}]  # type: ignore[index]
    assert source.config.max_credits_per_scrape == expected_credit_cap
    assert result.credits_used == float(expected_credit_cap)


def test_default_payload_does_not_request_browser_actions() -> None:
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    source.fetch(docket_id="70649963", source_url=_URL)

    assert "actions" not in transport.requests[0]["payload"]  # type: ignore[operator]


def test_auto_proxy_rejects_more_than_five_credits() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"),
        transport=FirecrawlFixtureTransport(
            [_success_response(proxy_used="stealth", credits_used=6)]
        ),
    )

    with pytest.raises(FirecrawlResponseError, match="five-credit cap"):
        source.fetch(docket_id="70649963", source_url=_URL)


def test_enhanced_proxy_is_bounded_to_five_credits_and_requires_stealth() -> None:
    transport = FirecrawlFixtureTransport(
        [_success_response(proxy_used="stealth", credits_used=5)]
    )
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="enhanced"), transport=transport
    )

    result = source.scrape(docket_id="70649963", source_url=_URL)

    assert transport.requests[0]["payload"]["proxy"] == "enhanced"  # type: ignore[index]
    assert result.proxy_requested == "enhanced"
    assert result.proxy_used == "stealth"
    assert result.credits_used == 5.0
    assert source.config.max_credits_per_scrape == 5


def test_enhanced_proxy_rejects_basic_actual_proxy() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="enhanced"),
        transport=FirecrawlFixtureTransport([_success_response(proxy_used="basic")]),
    )

    with pytest.raises(FirecrawlResponseError, match="disallowed proxy mode"):
        source.fetch(docket_id="70649963", source_url=_URL)


def test_config_rejects_unbounded_proxy_modes() -> None:
    with pytest.raises(
        ValueError, match="proxy must be 'basic', 'auto', or 'enhanced'"
    ):
        FirecrawlConfig(api_key="test-key", proxy="stealth")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "url,docket_id",
    [
        ("http://www.courtlistener.com/docket/70649963/case/", "70649963"),
        ("https://example.com/docket/70649963/case/", "70649963"),
        ("https://www.courtlistener.com/docket/not-numeric/case/", "70649963"),
        ("https://www.courtlistener.com/docket/70649963/case/?page=2", "70649963"),
        (
            "https://www.courtlistener.com/docket/70649963/case/?page=2&order_by=desc",
            "70649963",
        ),
        (
            "https://www.courtlistener.com/docket/70649963/case/?order_by=asc&page=2",
            "70649963",
        ),
        (
            "https://www.courtlistener.com/docket/70649963/case/?order_by=desc&page=02",
            "70649963",
        ),
        (
            "https://www.courtlistener.com/docket/70649963/case/?order_by=desc&page=2&x=1",
            "70649963",
        ),
        (_URL, "99"),
        (_URL, "not-numeric"),
    ],
)
def test_source_rejects_non_allowlisted_or_mismatched_urls_before_transport(
    url: str, docket_id: str
) -> None:
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    with pytest.raises(FirecrawlURLValidationError):
        source.fetch(docket_id=docket_id, source_url=url)

    assert transport.requests == []


def test_source_accepts_canonical_newest_first_docket_pagination() -> None:
    paginated_url = f"{_URL}?order_by=desc&page=2"
    transport = FirecrawlFixtureTransport([_success_response(source_url=paginated_url)])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    source.fetch(docket_id="70649963", source_url=paginated_url)

    assert transport.requests[0]["payload"]["url"] == paginated_url  # type: ignore[index]


def test_recap_search_url_validator_accepts_only_bounded_search_shape() -> None:
    validate_courtlistener_recap_search_url(
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc&page=2"
    )


def test_generic_scrape_accepts_strict_recap_search_url() -> None:
    search_url = (
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc&page=2"
    )
    resolved_url = (
        "https://courtlistener.com/?order_by=entry_date_filed+desc&page=2"
        "&entry_date_filed_before=07%2F12%2F2026&q=motion+to+dismiss"
        "&type=r&entry_date_filed_after=06%2F30%2F2026"
    )
    transport = FirecrawlFixtureTransport([_success_response(source_url=resolved_url)])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"), transport=transport
    )

    result = source.scrape_url(source_url=search_url)

    assert result.source_url == search_url
    assert result.docket_id is None
    assert result.raw_html.startswith("<html>")
    assert result.resolved_url == canonicalize_courtlistener_source_url(search_url)
    assert transport.requests[0]["payload"]["url"] == search_url  # type: ignore[index]


def test_resolved_recap_search_must_preserve_the_exact_search_identity() -> None:
    search_url = (
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc&page=2"
    )
    changed_page = search_url[:-1] + "3"
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"),
        transport=FirecrawlFixtureTransport(
            [_success_response(source_url=changed_page)]
        ),
    )

    with pytest.raises(FirecrawlResponseError) as raised:
        source.scrape_url(source_url=search_url)

    assert raised.value.failure_code == "resolved_url_mismatch"


def test_generic_scrape_accepts_strict_docket_url_without_requested_identity() -> None:
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    result = source.scrape_url(source_url=_URL)

    assert result.docket_id == "70649963"


def test_generic_scrape_rejects_arbitrary_url_before_transport() -> None:
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    with pytest.raises(FirecrawlURLValidationError, match="allowlisted"):
        source.scrape_url(source_url="https://example.com/")

    assert transport.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc",
        "https://www.courtlistener.com/search/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc",
        "https://www.courtlistener.com/?type=o&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc",
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+asc",
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=2026-06-30"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc",
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss&q=duplicate"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc",
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc&page=0",
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc&unexpected=1",
    ],
)
def test_recap_search_url_validator_rejects_other_urls(url: str) -> None:
    with pytest.raises(FirecrawlURLValidationError):
        validate_courtlistener_recap_search_url(url)


def test_config_requires_firecrawl_api_key() -> None:
    with pytest.raises(FirecrawlMissingAPIKeyError, match="FIRECRAWL_API_KEY"):
        FirecrawlConfig.from_env({})


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, FirecrawlAuthError),
        (403, FirecrawlAuthError),
        (402, FirecrawlPaymentRequiredError),
        (408, FirecrawlServerError),
        (429, FirecrawlRateLimitError),
        (500, FirecrawlServerError),
    ],
)
def test_http_failures_have_explicit_error_types(
    status_code: int, error_type: type[Exception]
) -> None:
    transport = FirecrawlFixtureTransport(
        [FirecrawlHTTPResponse(status_code=status_code, payload={"success": False})]
    )
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"), transport=transport
    )

    with pytest.raises(error_type):
        source.fetch(docket_id="70649963", source_url=_URL)

    assert len(transport.requests) == 1


def test_provider_http_timeout_is_transient() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [FirecrawlHTTPResponse(status_code=408, payload={"success": False})]
        ),
    )

    with pytest.raises(FirecrawlServerError) as raised:
        source.fetch(docket_id="70649963", source_url=_URL)

    assert raised.value.transient is True
    assert raised.value.provider_http_status == 408
    assert raised.value.failure_code == "provider_server_error"


def test_http_failure_does_not_expose_provider_response_body() -> None:
    secret_marker = "upstream-secret-body"
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport(
            [
                FirecrawlHTTPResponse(
                    status_code=503,
                    payload={"success": False, "error": secret_marker},
                )
            ]
        ),
    )

    with pytest.raises(FirecrawlServerError) as raised:
        source.fetch(docket_id="70649963", source_url=_URL)

    assert secret_marker not in str(raised.value)


@pytest.mark.parametrize(
    "response",
    [
        FirecrawlHTTPResponse(status_code=200, payload={"success": False}),
        FirecrawlHTTPResponse(
            status_code=200,
            payload={"success": True, "data": {"rawHtml": "", "metadata": {}}},
        ),
        _success_response(status_code=404),
        _success_response(proxy_used="enhanced"),
        _success_response(cache_state="hit"),
        _success_response(credits_used=5),
        FirecrawlHTTPResponse(
            status_code=200,
            payload={
                "success": True,
                "data": {
                    "rawHtml": "<html></html>",
                    "metadata": {"statusCode": 200, "creditsUsed": 1},
                },
            },
        ),
        FirecrawlHTTPResponse(
            status_code=200,
            payload={
                "success": True,
                "data": {
                    "rawHtml": "<html></html>",
                    "metadata": {"statusCode": 200, "proxyUsed": "basic"},
                },
            },
        ),
    ],
)
def test_malformed_or_policy_violating_responses_fail_closed(
    response: FirecrawlHTTPResponse,
) -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport([response]),
    )

    with pytest.raises(FirecrawlResponseError):
        source.fetch(docket_id="70649963", source_url=_URL)


def test_target_http_failure_preserves_target_status_for_caller_policy() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport([_success_response(status_code=410)]),
    )

    with pytest.raises(FirecrawlTargetHTTPError) as raised:
        source.fetch(docket_id="70649963", source_url=_URL)

    assert raised.value.target_status_code == 410
    assert raised.value.reported_credits == 1
    assert raised.value.proxy_used == "basic"
    assert raised.value.failure_code == "target_http_status_invalid"


@pytest.mark.parametrize(
    "response",
    [
        _success_response(status_code=700),
        _success_response(status_code=404, credits_used=0.5),
    ],
)
def test_target_http_failure_requires_fully_validated_billing_and_status(
    response: FirecrawlHTTPResponse,
) -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key"),
        transport=FirecrawlFixtureTransport([response]),
    )

    with pytest.raises(FirecrawlResponseError) as raised:
        source.fetch(docket_id="70649963", source_url=_URL)

    assert not isinstance(raised.value, FirecrawlTargetHTTPError)

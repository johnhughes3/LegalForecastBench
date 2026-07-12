from __future__ import annotations

import pytest
from legalforecast.ingestion.firecrawl_source import (
    FIRECRAWL_SCRAPE_ENDPOINT,
    FirecrawlAuthError,
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlMissingAPIKeyError,
    FirecrawlPaymentRequiredError,
    FirecrawlRateLimitError,
    FirecrawlResponseError,
    FirecrawlServerError,
    FirecrawlURLValidationError,
    validate_courtlistener_recap_search_url,
)

_URL = "https://www.courtlistener.com/docket/70649963/sam-v-easy-honda/"


def _success_response(
    *,
    status_code: int = 200,
    proxy_used: str = "basic",
    cache_state: str = "miss",
    credits_used: int = 1,
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
        "redactPII": False,
    }


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


def test_auto_proxy_rejects_more_than_five_credits() -> None:
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"),
        transport=FirecrawlFixtureTransport(
            [_success_response(proxy_used="stealth", credits_used=6)]
        ),
    )

    with pytest.raises(FirecrawlResponseError, match="five-credit cap"):
        source.fetch(docket_id="70649963", source_url=_URL)


def test_config_rejects_unbounded_proxy_modes() -> None:
    with pytest.raises(ValueError, match="proxy must be 'basic' or 'auto'"):
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
    transport = FirecrawlFixtureTransport([_success_response()])
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
    transport = FirecrawlFixtureTransport([_success_response()])
    source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="test-key", proxy="auto"), transport=transport
    )

    result = source.scrape_url(source_url=search_url)

    assert result.source_url == search_url
    assert result.docket_id is None
    assert result.raw_html.startswith("<html>")
    assert transport.requests[0]["payload"]["url"] == search_url  # type: ignore[index]


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

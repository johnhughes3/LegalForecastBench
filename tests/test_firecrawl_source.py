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
    assert result.proxy_used == "basic"
    assert result.cache_state == "miss"
    assert result.credits_used == 1.0


@pytest.mark.parametrize(
    "url,docket_id",
    [
        ("http://www.courtlistener.com/docket/70649963/case/", "70649963"),
        ("https://example.com/docket/70649963/case/", "70649963"),
        ("https://www.courtlistener.com/docket/not-numeric/case/", "70649963"),
        ("https://www.courtlistener.com/docket/70649963/case/?page=2", "70649963"),
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

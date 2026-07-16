from __future__ import annotations

import pytest
from legalforecast.ingestion.case_dev_config import (
    CASE_DEV_API_KEY_ENV,
    CASE_DEV_BASE_URL_ENV,
    CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV,
    CASE_DEV_LIVE_TESTS_ENV,
    CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV,
    CASE_DEV_TIMEOUT_SECONDS_ENV,
    DEFAULT_CASE_DEV_RATE_LIMIT_PER_MINUTE,
    CaseDevConfig,
    CaseDevConfigError,
    case_dev_live_skip_reason,
)


def test_case_dev_config_defaults_are_offline_safe() -> None:
    config = CaseDevConfig.from_env({})

    assert config.api_key is None
    assert config.base_url == "https://api.case.dev"
    assert config.live_tests_enabled is False
    assert config.live_tests_available is False
    assert config.rate_limit_per_minute == DEFAULT_CASE_DEV_RATE_LIMIT_PER_MINUTE
    assert config.timeout_seconds == 30.0


def test_case_dev_config_reads_live_settings_without_exposing_secret() -> None:
    config = CaseDevConfig.from_env(
        {
            CASE_DEV_API_KEY_ENV: "case-dev-secret-token",
            CASE_DEV_BASE_URL_ENV: "https://sandbox.case.dev/",
            CASE_DEV_LIVE_TESTS_ENV: "1",
            CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV: "60",
            CASE_DEV_TIMEOUT_SECONDS_ENV: "12.5",
            CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV: "0.03",
        }
    )

    assert config.api_key == "case-dev-secret-token"
    assert config.redacted_api_key == "case...oken"
    assert config.base_url == "https://sandbox.case.dev"
    assert config.live_tests_available is True
    assert config.rate_limit_per_minute == 60
    assert config.timeout_seconds == 12.5
    assert config.usage_estimate(4).estimated_cost_usd == pytest.approx(0.12)


def test_case_dev_config_requires_api_key_when_requested() -> None:
    with pytest.raises(CaseDevConfigError, match=CASE_DEV_API_KEY_ENV):
        CaseDevConfig.from_env({}, require_api_key=True)


def test_case_dev_live_skip_reason_is_clear_for_default_offline_tests() -> None:
    assert case_dev_live_skip_reason({}) == (
        "set CASE_DEV_LIVE_TESTS=1 to run live case.dev tests"
    )
    assert case_dev_live_skip_reason({CASE_DEV_LIVE_TESTS_ENV: "1"}) == (
        "set CASE_DEV_API_KEY to run live case.dev tests"
    )
    assert (
        case_dev_live_skip_reason(
            {
                CASE_DEV_LIVE_TESTS_ENV: "1",
                CASE_DEV_API_KEY_ENV: "case-dev-secret-token",
            }
        )
        is None
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (CASE_DEV_BASE_URL_ENV, "http://api.case.dev"),
        (CASE_DEV_BASE_URL_ENV, "https://api.case.dev@evil.example"),
        (CASE_DEV_BASE_URL_ENV, "https://evil.example"),
        (CASE_DEV_BASE_URL_ENV, "https://api.case.dev:444"),
        (CASE_DEV_LIVE_TESTS_ENV, "sometimes"),
        (CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV, "0"),
        (CASE_DEV_TIMEOUT_SECONDS_ENV, "-1"),
        (CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV, "-0.01"),
    ],
)
def test_case_dev_config_rejects_invalid_values(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(CaseDevConfigError, match=field_name):
        CaseDevConfig.from_env({field_name: value})

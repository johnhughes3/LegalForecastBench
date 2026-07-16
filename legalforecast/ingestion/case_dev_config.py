"""Runtime configuration for case.dev ingestion."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from legalforecast.ingestion.http_config import validate_https_base_url

CASE_DEV_API_KEY_ENV = "CASE_DEV_API_KEY"
CASE_DEV_BASE_URL_ENV = "CASE_DEV_BASE_URL"
CASE_DEV_LIVE_TESTS_ENV = "CASE_DEV_LIVE_TESTS"
CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV = "CASE_DEV_RATE_LIMIT_PER_MINUTE"
CASE_DEV_TIMEOUT_SECONDS_ENV = "CASE_DEV_TIMEOUT_SECONDS"
CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV = "CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD"

DEFAULT_CASE_DEV_BASE_URL = "https://api.case.dev"
DEFAULT_CASE_DEV_TIMEOUT_SECONDS = 30.0
DEFAULT_CASE_DEV_RATE_LIMIT_PER_MINUTE = 30
CASE_DEV_ALLOWED_BASE_HOSTS = frozenset({"api.case.dev", "sandbox.case.dev"})

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_FALSEY_VALUES = {"0", "false", "no", "off", ""}


class CaseDevConfigError(ValueError):
    """Raised when case.dev runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class CaseDevUsageEstimate:
    """Billing-relevant request usage estimate for case.dev calls."""

    request_count: int
    estimated_cost_usd: float | None


@dataclass(frozen=True, slots=True)
class CaseDevConfig:
    """case.dev runtime settings loaded from environment variables.

    ``rate_limit_per_minute`` is an aggregate process allowance. Concurrent
    workers share one limiter rather than each receiving this many requests.
    """

    api_key: str | None
    base_url: str = DEFAULT_CASE_DEV_BASE_URL
    live_tests_enabled: bool = False
    rate_limit_per_minute: int | None = None
    timeout_seconds: float = DEFAULT_CASE_DEV_TIMEOUT_SECONDS
    estimated_cost_per_request_usd: float | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_api_key: bool = False,
    ) -> CaseDevConfig:
        """Load case.dev settings without reading secrets from tracked files."""

        values = os.environ if environ is None else environ
        api_key = _optional_text(values.get(CASE_DEV_API_KEY_ENV))
        if require_api_key and api_key is None:
            raise CaseDevConfigError(f"{CASE_DEV_API_KEY_ENV} is required")

        return cls(
            api_key=api_key,
            base_url=_base_url(values.get(CASE_DEV_BASE_URL_ENV)),
            live_tests_enabled=_bool_env(
                values.get(CASE_DEV_LIVE_TESTS_ENV),
                CASE_DEV_LIVE_TESTS_ENV,
            ),
            rate_limit_per_minute=(
                _optional_positive_int(
                    values.get(CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV),
                    CASE_DEV_RATE_LIMIT_PER_MINUTE_ENV,
                )
                or DEFAULT_CASE_DEV_RATE_LIMIT_PER_MINUTE
            ),
            timeout_seconds=_positive_float(
                values.get(CASE_DEV_TIMEOUT_SECONDS_ENV),
                CASE_DEV_TIMEOUT_SECONDS_ENV,
                DEFAULT_CASE_DEV_TIMEOUT_SECONDS,
            ),
            estimated_cost_per_request_usd=_optional_nonnegative_float(
                values.get(CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV),
                CASE_DEV_ESTIMATED_COST_PER_REQUEST_USD_ENV,
            ),
        )

    @property
    def live_tests_available(self) -> bool:
        return self.live_tests_enabled and self.api_key is not None

    @property
    def redacted_api_key(self) -> str | None:
        if self.api_key is None:
            return None
        if len(self.api_key) <= 8:
            return "<redacted>"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def usage_estimate(self, request_count: int) -> CaseDevUsageEstimate:
        if request_count < 0:
            raise CaseDevConfigError("request_count must be nonnegative")
        estimated_cost = None
        if self.estimated_cost_per_request_usd is not None:
            estimated_cost = request_count * self.estimated_cost_per_request_usd
        return CaseDevUsageEstimate(
            request_count=request_count,
            estimated_cost_usd=estimated_cost,
        )


def case_dev_live_skip_reason(environ: Mapping[str, str] | None = None) -> str | None:
    """Return why a live case.dev test should skip, or ``None`` if it can run."""

    config = CaseDevConfig.from_env(environ)
    if not config.live_tests_enabled:
        return f"set {CASE_DEV_LIVE_TESTS_ENV}=1 to run live case.dev tests"
    if config.api_key is None:
        return f"set {CASE_DEV_API_KEY_ENV} to run live case.dev tests"
    return None


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _base_url(value: str | None) -> str:
    base_url = _optional_text(value) or DEFAULT_CASE_DEV_BASE_URL
    return validate_https_base_url(
        base_url,
        field_name=CASE_DEV_BASE_URL_ENV,
        allowed_hosts=CASE_DEV_ALLOWED_BASE_HOSTS,
        error_type=CaseDevConfigError,
    )


def _bool_env(value: str | None, field_name: str) -> bool:
    normalized = "" if value is None else value.strip().lower()
    if normalized in _TRUTHY_VALUES:
        return True
    if normalized in _FALSEY_VALUES:
        return False
    raise CaseDevConfigError(
        f"{field_name} must be one of: 1, 0, true, false, yes, no, on, off"
    )


def _optional_positive_int(value: str | None, field_name: str) -> int | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = int(text)
    except ValueError as exc:
        raise CaseDevConfigError(f"{field_name} must be an integer") from exc
    if parsed <= 0:
        raise CaseDevConfigError(f"{field_name} must be positive")
    return parsed


def _positive_float(
    value: str | None,
    field_name: str,
    default: float,
) -> float:
    text = _optional_text(value)
    if text is None:
        return default
    try:
        parsed = float(text)
    except ValueError as exc:
        raise CaseDevConfigError(f"{field_name} must be a number") from exc
    if parsed <= 0:
        raise CaseDevConfigError(f"{field_name} must be positive")
    return parsed


def _optional_nonnegative_float(value: str | None, field_name: str) -> float | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = float(text)
    except ValueError as exc:
        raise CaseDevConfigError(f"{field_name} must be a number") from exc
    if parsed < 0:
        raise CaseDevConfigError(f"{field_name} must be nonnegative")
    return parsed

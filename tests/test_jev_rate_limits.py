"""The Jev retry policy never repeats uncertain or access-denied requests."""

import pytest
from legalforecast.evals.live_model_solver import LiveModelProviderError
from legalforecast.jev import rate_limits


@pytest.mark.parametrize("status", [401, 403, 500, None])
def test_non_429_failure_is_not_retried(monkeypatch, status):
    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    calls = []

    def call():
        calls.append(1)
        raise LiveModelProviderError(
            "other failure", status_code=status, retryable=True
        )

    with pytest.raises(LiveModelProviderError):
        rate_limits.call_with_rate_limit_retries(call)
    assert len(calls) == 1
    assert sleeps == []


def test_429_retries_until_eighth_attempt_then_returns_success(monkeypatch):
    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    calls = []

    def call():
        calls.append(1)
        if len(calls) < 8:
            raise LiveModelProviderError("capacity", status_code=429)
        return {"answers": {"unit-1": {"probability": 0.75}}}

    payload = rate_limits.call_with_rate_limit_retries(call)

    assert len(calls) == 8
    assert sleeps == [30, 60, 120, 240, 300, 300, 300]
    assert payload == {
        "answers": {"unit-1": {"probability": 0.75}},
        "_jev_request_count": 8,
    }


@pytest.mark.parametrize("retryable", [True, False, None])
def test_all_429s_exhaust_after_eight_attempts(monkeypatch, retryable):
    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    calls = []

    def call():
        calls.append(1)
        raise LiveModelProviderError("capacity", status_code=429, retryable=retryable)

    with pytest.raises(LiveModelProviderError) as failure:
        rate_limits.call_with_rate_limit_retries(call)

    assert failure.value.status_code == 429
    assert failure.value.retryable is True
    assert len(calls) == 8
    assert sleeps == [30, 60, 120, 240, 300, 300, 300]

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

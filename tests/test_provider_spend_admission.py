"""Concurrent budget admission waits without repeating paid provider requests."""

from dataclasses import replace

import pytest
from legalforecast.evals import provider_spend_admission as admission
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.provider_spend_control import (
    CircuitBreakerOpenError,
    ProviderCapExceededError,
)
from tenacity import Retrying
from tests.test_provider_spend_dynamodb import InMemoryDynamoRunner, _authority, _key


def test_waiting_case_runs_once_after_another_reservation_settles(monkeypatch):
    authority = _authority(InMemoryDynamoRunner(), cap_microusd=1_000_000)
    busy = authority.authorize_attempt(
        _key(case_id="busy"), reservation_microusd=700_000
    )
    sleeps = []

    def settle_while_waiting(seconds):
        sleeps.append(seconds)
        authority.record_response(
            busy,
            input_tokens=1,
            output_tokens=1,
            actual_microusd=100_000,
            response_sha256="a" * 64,
        )

    class ImmediateRetrying(Retrying):
        def __init__(self, **kwargs):
            super().__init__(sleep=settle_while_waiting, **kwargs)

    monkeypatch.setattr(admission, "Retrying", ImmediateRetrying)
    calls = []
    handler = ProviderSpendAttemptHandler(
        authority,
        _key(case_id="waiting"),
        600_000,
        capacity_snapshot=authority.snapshot,
    )

    def provider_call():
        calls.append("called")
        return {"output": "unchanged response"}

    result = handler.run_attempt(1, provider_call)
    assert result == {"output": "unchanged response"}
    assert calls == ["called"]
    assert sleeps == [5.0]
    assert authority.snapshot().attempt_count == 2
    assert authority.snapshot().committed_microusd == 700_000


@pytest.mark.parametrize("ambiguous", [False, True])
def test_true_or_ambiguous_spend_does_not_wait(monkeypatch, ambiguous):
    authority = _authority(InMemoryDynamoRunner(), cap_microusd=1_000_000)
    prior = authority.authorize_attempt(
        _key(case_id="prior"), reservation_microusd=700_000
    )
    if ambiguous:
        authority.record_failure(prior, failure_type="timeout", ambiguous=True)
    else:
        authority.record_response(
            prior,
            input_tokens=1,
            output_tokens=1,
            actual_microusd=700_000,
            response_sha256="a" * 64,
        )
    calls = []
    handler = ProviderSpendAttemptHandler(
        authority,
        _key(case_id="next"),
        600_000,
        capacity_snapshot=authority.snapshot,
    )
    with pytest.raises(ProviderCapExceededError):
        handler.run_attempt(1, lambda: calls.append("called") or {})
    assert calls == []
    assert authority.snapshot().attempt_count == 1


def test_authorization_wait_is_bounded_and_keeps_existing_reservation():
    authority = _authority(InMemoryDynamoRunner(), cap_microusd=1_000_000)
    authority.authorize_attempt(_key(case_id="busy"), reservation_microusd=700_000)
    with pytest.raises(ProviderCapExceededError):
        admission.authorize_when_capacity_available(
            authority,
            _key(case_id="waiting"),
            reservation_microusd=600_000,
            snapshot=authority.snapshot,
            max_wait_seconds=0,
        )
    assert authority.snapshot().attempt_count == 1
    assert authority.snapshot().committed_microusd == 700_000


def test_circuit_breaker_is_not_retried(monkeypatch):
    authority = _authority(InMemoryDynamoRunner())
    calls = []

    def refuse(*args, **kwargs):
        calls.append("admission")
        raise CircuitBreakerOpenError("blocked")

    monkeypatch.setattr(authority, "authorize_attempt", refuse)
    with pytest.raises(CircuitBreakerOpenError):
        admission.authorize_when_capacity_available(
            authority,
            _key(),
            reservation_microusd=1,
            snapshot=lambda: replace(authority.snapshot(), reserved_attempt_count=1),
        )
    assert calls == ["admission"]

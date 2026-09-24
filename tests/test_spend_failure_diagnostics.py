"""Spending refusals retain their safe error class before any provider call."""

from pathlib import Path

import pytest
from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    AttemptLimitExceededError,
    AuthorityIdentityMismatchError,
    AuthorityPoisonedError,
    BeforeAttemptCommit,
    CircuitBreakerOpenError,
    ProviderCapExceededError,
    ProviderSpendControlError,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.runner import RunBlockedError, execute_release_run
from tests.test_public_runner import CountingTransport, _config, _fixture_environ


@pytest.mark.parametrize(
    "error_type",
    [
        ProviderCapExceededError,
        AttemptLimitExceededError,
        CircuitBreakerOpenError,
        AuthorityIdentityMismatchError,
        AuthorityPoisonedError,
    ],
)
def test_pretransport_refusal_names_cause_without_exposing_error_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[ProviderSpendControlError],
) -> None:
    def refuse(
        self: SqliteProviderSpendAuthority,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
        before_commit: BeforeAttemptCommit,
    ) -> AttemptLease:
        raise error_type("sensitive authority details")

    monkeypatch.setattr(
        SqliteProviderSpendAuthority, "authorize_attempt_with_transaction", refuse
    )
    transport = CountingTransport()
    with pytest.raises(RunBlockedError) as caught:
        execute_release_run(
            _config(tmp_path), transport=transport, environ=_fixture_environ()
        )
    assert error_type.__name__ in str(caught.value)
    assert "sensitive authority details" not in str(caught.value)
    assert transport.calls == 0

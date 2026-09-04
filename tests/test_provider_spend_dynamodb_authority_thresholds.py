from __future__ import annotations

import pytest
from legalforecast.evals.provider_spend_control import AuthorityIdentityMismatchError
from tests.test_provider_spend_dynamodb import (
    InMemoryDynamoRunner,
    _authority,
    _key,
)


def test_remote_authority_raises_stored_failure_threshold() -> None:
    runner = InMemoryDynamoRunner()
    _authority(runner, failure_threshold=1)
    raised = _authority(runner, failure_threshold=3)
    assert runner.items["LEDGER"]["failure_threshold"] == {"N": "3"}
    lease = raised.authorize_attempt(
        _key(case_id="isolated-failure"), reservation_microusd=1
    )
    raised.record_failure(lease, failure_type="TimeoutError", ambiguous=True)
    raised.authorize_attempt(_key(case_id="still-open"), reservation_microusd=1)
    with pytest.raises(AuthorityIdentityMismatchError, match="failure_threshold"):
        _authority(runner, failure_threshold=1)


def test_remote_authority_does_not_raise_threshold_on_other_policy_drift() -> None:
    runner = InMemoryDynamoRunner()
    _authority(runner, failure_threshold=1)
    with pytest.raises(AuthorityIdentityMismatchError):
        _authority(runner, failure_threshold=3, cap_microusd=2_000_000)
    assert runner.items["LEDGER"]["failure_threshold"] == {"N": "1"}

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import cast

import pytest
from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    AttemptStateError,
    FrozenAttemptPolicy,
)
from legalforecast.evals.provider_spend_dynamodb import (
    DynamoDbConditionalError,
    DynamoDbProviderSpendAuthority,
)

AttributeValue = dict[str, str]
AttributeMap = dict[str, AttributeValue]

_TABLE_ARN = "arn:aws:dynamodb:us-east-1:123456789012:table/authority-table"
_TABLE_IDENTITY = hashlib.sha256(_TABLE_ARN.encode()).hexdigest()
_LOGICAL_CALL_KEY = "c" * 64
_ATTEMPT_ID = "a" * 64
_RESERVATION_MICROUSD = 4_309_200
_INPUT_TOKENS = 11
_OUTPUT_TOKENS = 7
_ACTUAL_MICROUSD = 407_889
_RESPONSE_SHA256 = "b" * 64


class _ContendedRunner:
    """Small remote-state double for a canceled settlement transaction."""

    def __init__(self, *, settle_on_first_conflict: bool = False) -> None:
        self.items: dict[str, AttributeMap] = {}
        self.attempt_key = ""
        self.transaction_calls = 0
        self.settle_on_first_conflict = settle_on_first_conflict

    def __call__(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if operation == "describe-table":
            return {
                "Table": {
                    "TableArn": _TABLE_ARN,
                    "KeySchema": [
                        {"AttributeName": "authority_key", "KeyType": "HASH"},
                        {"AttributeName": "record_key", "KeyType": "RANGE"},
                    ],
                    "AttributeDefinitions": [
                        {"AttributeName": "authority_key", "AttributeType": "S"},
                        {"AttributeName": "record_key", "AttributeType": "S"},
                    ],
                }
            }
        if operation == "get-item":
            key = cast(AttributeMap, payload["Key"])
            item = self.items.get(key["record_key"]["S"])
            return {} if item is None else {"Item": item}
        if operation == "put-item":
            item = cast(AttributeMap, payload["Item"])
            self.items[item["record_key"]["S"]] = item
            return {}
        if operation == "transact-write-items":
            return self._transact()
        raise AssertionError(f"unexpected DynamoDB operation: {operation}")

    def install_attempt(
        self,
        authority: DynamoDbProviderSpendAuthority,
        lease: AttemptLease,
    ) -> None:
        self.attempt_key = (
            f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"
        )
        self.items[self.attempt_key] = {
            "authority_key": _s(authority.authority_key),
            "record_key": _s(self.attempt_key),
            "attempt_id": _s(lease.attempt_id),
            "authority_identity_sha256": _s(lease.authority_identity_sha256),
            "logical_call_key": _s(lease.logical_call_key),
            "attempt_ordinal": _n(lease.attempt_ordinal),
            "reservation_microusd": _n(lease.reservation_microusd),
            "status": _s("reserved"),
        }
        self.items["LEDGER"]["committed_microusd"] = _n(lease.reservation_microusd)
        self.items["LEDGER"]["reserved_attempt_count"] = _n(1)

    def _transact(self) -> Mapping[str, object]:
        self.transaction_calls += 1
        if self.transaction_calls == 1:
            if self.settle_on_first_conflict:
                self._set_attempt(actual_microusd=_ACTUAL_MICROUSD + 1)
            raise DynamoDbConditionalError("simulated transaction contention")
        self._set_attempt(actual_microusd=_ACTUAL_MICROUSD)
        ledger = self.items["LEDGER"]
        ledger["committed_microusd"] = _n(_ACTUAL_MICROUSD)
        ledger["reserved_attempt_count"] = _n(0)
        ledger["settled_attempt_count"] = _n(1)
        return {}

    def _set_attempt(self, *, actual_microusd: int) -> None:
        attempt = self.items[self.attempt_key]
        attempt.update(
            {
                "status": _s("settled"),
                "input_tokens": _n(_INPUT_TOKENS),
                "output_tokens": _n(_OUTPUT_TOKENS),
                "actual_microusd": _n(actual_microusd),
                "response_sha256": _s(_RESPONSE_SHA256),
            }
        )


def test_record_response_retries_reserved_attempt_after_transaction_contention() -> (
    None
):
    runner = _ContendedRunner()
    authority = _authority(runner)
    lease = _install_attempt(runner, authority)

    authority.record_response(
        lease,
        input_tokens=_INPUT_TOKENS,
        output_tokens=_OUTPUT_TOKENS,
        actual_microusd=_ACTUAL_MICROUSD,
        response_sha256=_RESPONSE_SHA256,
    )

    assert runner.transaction_calls == 2
    assert runner.items[runner.attempt_key]["status"] == _s("settled")
    assert runner.items[runner.attempt_key]["actual_microusd"] == _n(_ACTUAL_MICROUSD)
    assert runner.items["LEDGER"]["committed_microusd"] == _n(_ACTUAL_MICROUSD)


def test_record_response_still_rejects_changed_settled_evidence() -> None:
    runner = _ContendedRunner(settle_on_first_conflict=True)
    authority = _authority(runner)
    lease = _install_attempt(runner, authority)

    with pytest.raises(AttemptStateError, match="evidence changed"):
        authority.record_response(
            lease,
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            actual_microusd=_ACTUAL_MICROUSD,
            response_sha256=_RESPONSE_SHA256,
        )

    assert runner.transaction_calls == 1
    assert runner.items[runner.attempt_key]["status"] == _s("settled")
    assert runner.items[runner.attempt_key]["actual_microusd"] == _n(
        _ACTUAL_MICROUSD + 1
    )


def test_record_response_rejects_missing_settlement_reservation_accounting() -> None:
    runner = _ContendedRunner()
    authority = _authority(runner)
    lease = _install_attempt(runner, authority)
    runner.items["LEDGER"]["committed_microusd"] = _n(0)

    with pytest.raises(AttemptStateError, match="reservation accounting changed"):
        authority.record_response(
            lease,
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            actual_microusd=_ACTUAL_MICROUSD,
            response_sha256=_RESPONSE_SHA256,
        )

    assert runner.transaction_calls == 1
    assert runner.items[runner.attempt_key]["status"] == _s("reserved")


def _authority(runner: _ContendedRunner) -> DynamoDbProviderSpendAuthority:
    return DynamoDbProviderSpendAuthority(
        table_name="authority-table",
        authority_identity_sha256=_TABLE_IDENTITY,
        cycle_id="cycle-1",
        provider="openai",
        account="primary-account-alias",
        cap_microusd=10_000_000,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256="f" * 64,
            max_billable_attempts=3,
            failure_threshold=3,
            failure_window_seconds=300,
        ),
        region="us-east-1",
        runner=runner,
        clock=lambda: 1_700_000_000.0,
    )


def _install_attempt(
    runner: _ContendedRunner,
    authority: DynamoDbProviderSpendAuthority,
) -> AttemptLease:
    lease = AttemptLease(
        attempt_id=_ATTEMPT_ID,
        authority_identity_sha256=authority.authority_identity_sha256,
        logical_call_key=_LOGICAL_CALL_KEY,
        attempt_ordinal=1,
        reservation_microusd=_RESERVATION_MICROUSD,
    )
    runner.install_attempt(authority, lease)
    return lease


def _s(value: str) -> AttributeValue:
    return {"S": value}


def _n(value: int) -> AttributeValue:
    return {"N": str(value)}

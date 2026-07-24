from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from typing import cast

import pytest
from legalforecast.evals.provider_spend_control import (
    AttemptLimitExceededError,
    AttemptStateError,
    AuthorityIdentityMismatchError,
    AuthorityPoisonedError,
    CircuitBreakerOpenError,
    FrozenAttemptPolicy,
    ProviderCapExceededError,
    ProviderSpendKey,
    ReconciliationMismatchError,
    SettlementError,
)
from legalforecast.evals.provider_spend_dynamodb import (
    AwsCliDynamoCommandRunner,
    DynamoDbConditionalError,
    DynamoDbProviderSpendAuthority,
)

AttributeValue = dict[str, str]
AttributeMap = dict[str, AttributeValue]


class InMemoryDynamoRunner:
    """Transactional contract double for the authority's DynamoDB expression subset."""

    def __init__(self) -> None:
        self.items: dict[str, AttributeMap] = {}
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self.lock = threading.RLock()
        self.table_arn = _TABLE_ARN
        self.key_schema: list[dict[str, str]] = [
            {"AttributeName": "authority_key", "KeyType": "HASH"},
            {"AttributeName": "record_key", "KeyType": "RANGE"},
        ]

    def __call__(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        with self.lock:
            return self._call_locked(operation, payload)

    def _call_locked(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.calls.append((operation, payload))
        if operation == "describe-table":
            return {
                "Table": {
                    "TableArn": self.table_arn,
                    "KeySchema": self.key_schema,
                }
            }
        if operation == "get-item":
            key = cast(AttributeMap, payload["Key"])
            item = self.items.get(key["record_key"]["S"])
            return {} if item is None else {"Item": item}
        if operation == "put-item":
            item = cast(AttributeMap, payload["Item"])
            record_key = item["record_key"]["S"]
            if record_key in self.items:
                raise DynamoDbConditionalError("conditional put rejected")
            self.items[record_key] = item
            return {}
        if operation == "transact-write-items":
            self._apply_transaction(payload)
            return {}
        raise AssertionError(f"unexpected DynamoDB operation: {operation}")

    def _apply_transaction(self, payload: Mapping[str, object]) -> None:
        transaction = cast(list[dict[str, object]], payload["TransactItems"])
        next_items = deepcopy(self.items)
        try:
            for action in transaction:
                if "Update" in action:
                    self._apply_update(
                        next_items,
                        cast(dict[str, object], action["Update"]),
                    )
                elif "Put" in action:
                    self._apply_put(
                        next_items,
                        cast(dict[str, object], action["Put"]),
                    )
                elif "ConditionCheck" in action:
                    self._apply_condition_check(
                        next_items,
                        cast(dict[str, object], action["ConditionCheck"]),
                    )
                else:
                    raise AssertionError(f"unsupported transaction action: {action}")
        except DynamoDbConditionalError:
            raise
        self.items = next_items

    def _apply_update(
        self,
        items: dict[str, AttributeMap],
        update: Mapping[str, object],
    ) -> None:
        key = cast(AttributeMap, update["Key"])
        record_key = key["record_key"]["S"]
        item = items.get(record_key)
        values = cast(
            AttributeMap,
            update.get("ExpressionAttributeValues", {}),
        )
        names = cast(dict[str, str], update.get("ExpressionAttributeNames", {}))
        condition = update.get("ConditionExpression")
        if isinstance(condition, str) and not _condition_holds(
            condition,
            item,
            values=values,
            names=names,
        ):
            raise DynamoDbConditionalError(
                f"conditional update rejected for {record_key}"
            )
        if item is None:
            item = deepcopy(key)
            items[record_key] = item
        _apply_update_expression(
            item,
            cast(str, update["UpdateExpression"]),
            values=values,
            names=names,
        )

    def _apply_put(
        self,
        items: dict[str, AttributeMap],
        put: Mapping[str, object],
    ) -> None:
        item = deepcopy(cast(AttributeMap, put["Item"]))
        record_key = item["record_key"]["S"]
        existing = items.get(record_key)
        values = cast(AttributeMap, put.get("ExpressionAttributeValues", {}))
        names = cast(dict[str, str], put.get("ExpressionAttributeNames", {}))
        condition = put.get("ConditionExpression")
        if isinstance(condition, str) and not _condition_holds(
            condition,
            existing,
            values=values,
            names=names,
        ):
            raise DynamoDbConditionalError(f"conditional put rejected for {record_key}")
        items[record_key] = item

    def _apply_condition_check(
        self,
        items: dict[str, AttributeMap],
        check: Mapping[str, object],
    ) -> None:
        key = cast(AttributeMap, check["Key"])
        record_key = key["record_key"]["S"]
        values = cast(
            AttributeMap,
            check.get("ExpressionAttributeValues", {}),
        )
        names = cast(dict[str, str], check.get("ExpressionAttributeNames", {}))
        if not _condition_holds(
            cast(str, check["ConditionExpression"]),
            items.get(record_key),
            values=values,
            names=names,
        ):
            raise DynamoDbConditionalError(f"condition check rejected for {record_key}")


_CONDITION_TOKEN = re.compile(
    r"\s*(attribute_not_exists|attribute_exists|AND|OR|<=|>=|<>|=|<|>|\(|\)|"
    r"#[A-Za-z0-9_]+|:[A-Za-z0-9_]+|[A-Za-z_][A-Za-z0-9_]*)"
)


class _ConditionParser:
    def __init__(
        self,
        expression: str,
        item: AttributeMap | None,
        *,
        values: AttributeMap,
        names: Mapping[str, str],
    ) -> None:
        self.tokens = _CONDITION_TOKEN.findall(expression)
        self.position = 0
        self.item = {} if item is None else item
        self.values = values
        self.names = names

    def parse(self) -> bool:
        result = self._parse_or()
        if self.position != len(self.tokens):
            raise AssertionError(
                f"unsupported condition tail: {self.tokens[self.position :]}"
            )
        return result

    def _parse_or(self) -> bool:
        result = self._parse_and()
        while self._peek() == "OR":
            self._take("OR")
            right = self._parse_and()
            result = result or right
        return result

    def _parse_and(self) -> bool:
        result = self._parse_atom()
        while self._peek() == "AND":
            self._take("AND")
            right = self._parse_atom()
            result = result and right
        return result

    def _parse_atom(self) -> bool:
        if self._peek() == "(":
            self._take("(")
            result = self._parse_or()
            self._take(")")
            return result
        if self._peek() in {"attribute_not_exists", "attribute_exists"}:
            predicate = self._next()
            self._take("(")
            field = self._field(self._next())
            self._take(")")
            exists = field in self.item
            return not exists if predicate == "attribute_not_exists" else exists

        field = self._field(self._next())
        operator = self._next()
        right_token = self._next()
        left = self.item.get(field)
        right = (
            self.values[right_token]
            if right_token.startswith(":")
            else self.item.get(self._field(right_token))
        )
        if left is None or right is None:
            return False
        return _compare_attribute_values(left, operator, right)

    def _field(self, token: str) -> str:
        return self.names.get(token, token)

    def _peek(self) -> str | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _next(self) -> str:
        token = self._peek()
        if token is None:
            raise AssertionError("unexpected end of DynamoDB condition")
        self.position += 1
        return token

    def _take(self, expected: str) -> None:
        actual = self._next()
        if actual != expected:
            raise AssertionError(f"expected {expected!r}, got {actual!r}")


def _condition_holds(
    expression: str,
    item: AttributeMap | None,
    *,
    values: AttributeMap,
    names: Mapping[str, str],
) -> bool:
    return _ConditionParser(
        expression,
        item,
        values=values,
        names=names,
    ).parse()


def _compare_attribute_values(
    left: AttributeValue,
    operator: str,
    right: AttributeValue,
) -> bool:
    if "N" in left and "N" in right:
        left_value: object = Decimal(left["N"])
        right_value: object = Decimal(right["N"])
    else:
        left_value = left
        right_value = right
    if operator == "=":
        return left_value == right_value
    if operator == "<>":
        return left_value != right_value
    if operator == "<":
        return cast(Decimal, left_value) < cast(Decimal, right_value)
    if operator == "<=":
        return cast(Decimal, left_value) <= cast(Decimal, right_value)
    if operator == ">":
        return cast(Decimal, left_value) > cast(Decimal, right_value)
    if operator == ">=":
        return cast(Decimal, left_value) >= cast(Decimal, right_value)
    raise AssertionError(f"unsupported DynamoDB condition operator: {operator}")


def _apply_update_expression(
    item: AttributeMap,
    expression: str,
    *,
    values: AttributeMap,
    names: Mapping[str, str],
) -> None:
    sections = list(re.finditer(r"\b(SET|ADD)\b", expression))
    if not sections:
        raise AssertionError(f"unsupported DynamoDB update expression: {expression}")
    for index, match in enumerate(sections):
        end = (
            sections[index + 1].start()
            if index + 1 < len(sections)
            else len(expression)
        )
        body = expression[match.end() : end].strip()
        if match.group(1) == "SET":
            for assignment in body.split(","):
                field_token, value_token = (
                    part.strip() for part in assignment.split("=", maxsplit=1)
                )
                item[names.get(field_token, field_token)] = deepcopy(
                    values[value_token]
                )
        else:
            for addition in body.split(","):
                field_token, value_token = addition.strip().split()
                field = names.get(field_token, field_token)
                current = Decimal(item.get(field, _n(0))["N"])
                delta = Decimal(values[value_token]["N"])
                item[field] = _decimal_attribute(current + delta)


def _decimal_attribute(value: Decimal) -> AttributeValue:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return {"N": rendered or "0"}


def test_authorization_uses_one_remote_ledger_and_atomic_three_record_write() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)

    lease = authority.authorize_attempt(_key(), reservation_microusd=250_000)

    operations = [operation for operation, _ in runner.calls]
    assert operations[:4] == [
        "describe-table",
        "get-item",
        "put-item",
        "get-item",
    ]
    reads = [payload for operation, payload in runner.calls if operation == "get-item"]
    assert all(payload["ConsistentRead"] is True for payload in reads)
    operation, payload = runner.calls[-1]
    assert operation == "transact-write-items"
    items = cast(list[dict[str, object]], payload["TransactItems"])
    assert [next(iter(item)) for item in items] == ["Update", "Update", "Put"]
    assert len(items) == 3
    assert lease.attempt_ordinal == 1

    rendered = json.dumps(payload, sort_keys=True)
    assert "cycle-1" in rendered
    assert "official-eval" in rendered
    assert "primary-account-alias" not in rendered
    assert "workflow" not in rendered.lower()
    assert all(
        item["authority_key"]["S"] == authority.authority_key
        for item in runner.items.values()
    )
    assert set(runner.items) == {
        "LEDGER",
        f"CELL#{_key().logical_call_key}",
        f"ATTEMPT#{_key().logical_call_key}#0001",
    }


def test_constructor_rejects_different_table_arn_or_key_schema() -> None:
    wrong_arn = InMemoryDynamoRunner()
    wrong_arn.table_arn = f"{_TABLE_ARN}-other"
    with pytest.raises(AuthorityIdentityMismatchError, match="table ARN"):
        _authority(wrong_arn)

    wrong_keys = InMemoryDynamoRunner()
    wrong_keys.key_schema = [{"AttributeName": "authority_key", "KeyType": "HASH"}]
    with pytest.raises(AuthorityIdentityMismatchError, match="key schema"):
        _authority(wrong_keys)


def test_labeling_and_eval_share_the_same_cycle_provider_account_ledger() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner, cap_microusd=500_000)
    authority.authorize_attempt(
        _key(stage="llm-label", case_id="label"),
        reservation_microusd=300_000,
    )

    with pytest.raises(ProviderCapExceededError):
        authority.authorize_attempt(
            _key(stage="official-eval", case_id="eval"),
            reservation_microusd=250_000,
        )

    assert sum(op == "transact-write-items" for op, _ in runner.calls) == 1


def test_concurrent_remote_writers_cannot_jointly_exceed_frozen_cap() -> None:
    runner = InMemoryDynamoRunner()
    authorities = [_authority(runner) for _ in range(12)]
    start = threading.Barrier(len(authorities))

    def reserve(index: int) -> bool:
        start.wait()
        try:
            authorities[index].authorize_attempt(
                _key(case_id=f"case-{index}"),
                reservation_microusd=250_000,
            )
        except ProviderCapExceededError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=len(authorities)) as executor:
        accepted = list(executor.map(reserve, range(len(authorities))))

    assert sum(accepted) == 4
    assert runner.items["LEDGER"]["committed_microusd"] == _n(1_000_000)


def test_authorization_refuses_open_breaker_immediately_before_transaction() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner, clock=lambda: 1_100.0)
    _set_failure_events(runner, [900.0, 1_000.0, 1_000.25])

    with pytest.raises(CircuitBreakerOpenError):
        authority.authorize_attempt(_key(), reservation_microusd=1)

    assert not any(op == "transact-write-items" for op, _ in runner.calls)


def test_concurrent_injected_failures_open_remote_breaker_for_all_new_calls() -> None:
    runner = InMemoryDynamoRunner()
    authorities = [_authority(runner) for _ in range(4)]
    leases = [
        authority.authorize_attempt(
            _key(case_id=f"in-flight-{index}"),
            reservation_microusd=100_000,
        )
        for index, authority in enumerate(authorities)
    ]
    start = threading.Barrier(len(authorities))

    def fail(index: int) -> None:
        start.wait()
        authorities[index].record_failure(
            leases[index],
            failure_type="TimeoutError",
            ambiguous=True,
        )

    with ThreadPoolExecutor(max_workers=len(authorities)) as executor:
        list(executor.map(fail, range(len(authorities))))

    assert runner.items["LEDGER"]["failure_count"] == _n(3)
    failure_events = json.loads(runner.items["LEDGER"]["failure_events_json"]["S"])
    assert isinstance(failure_events, list)
    assert len(failure_events) == 3
    assert failure_events == sorted(failure_events)
    assert runner.items["LEDGER"]["committed_microusd"] == _n(400_000)
    for index in range(8):
        with pytest.raises(CircuitBreakerOpenError):
            _authority(runner).authorize_attempt(
                _key(case_id=f"blocked-{index}"),
                reservation_microusd=1,
            )


def test_remote_breaker_uses_true_trailing_window_across_prior_boundary() -> None:
    runner = InMemoryDynamoRunner()
    now = [100.0]

    def fail(case_id: str, failed_at: float) -> None:
        now[0] = failed_at
        authority = _authority(
            runner,
            failure_threshold=3,
            clock=lambda: now[0],
        )
        lease = authority.authorize_attempt(
            _key(case_id=case_id), reservation_microusd=100_000
        )
        authority.record_failure(
            lease,
            failure_type="TimeoutError",
            ambiguous=False,
        )

    fail("old-expired", 100.0)
    fail("still-live", 200.0)
    fail("after-boundary-1", 401.0)
    fail("after-boundary-2", 402.0)

    now[0] = 403.0
    authority = _authority(
        runner,
        failure_threshold=3,
        clock=lambda: now[0],
    )
    with pytest.raises(CircuitBreakerOpenError):
        authority.authorize_attempt(
            _key(case_id="must-be-blocked"), reservation_microusd=1
        )

    ledger = runner.items["LEDGER"]
    assert json.loads(ledger["failure_events_json"]["S"]) == [200.0, 401.0, 402.0]
    assert ledger["failure_count"] == _n(3)


def test_concurrent_same_cell_writers_get_distinct_bounded_ordinals() -> None:
    runner = InMemoryDynamoRunner()
    authorities = [_authority(runner, max_billable_attempts=3) for _ in range(12)]
    start = threading.Barrier(len(authorities))

    def reserve(authority: DynamoDbProviderSpendAuthority) -> int | None:
        start.wait()
        try:
            return authority.authorize_attempt(
                _key(), reservation_microusd=100_000
            ).attempt_ordinal
        except AttemptLimitExceededError:
            return None

    with ThreadPoolExecutor(max_workers=len(authorities)) as executor:
        ordinals = list(executor.map(reserve, authorities))

    accepted = sorted(ordinal for ordinal in ordinals if ordinal is not None)
    assert accepted == [1, 2, 3]
    assert runner.items[f"CELL#{_key().logical_call_key}"]["attempt_count"] == _n(3)
    assert runner.items["LEDGER"]["attempt_count"] == _n(3)


def test_durable_cell_count_refuses_attempt_beyond_frozen_limit() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner, max_billable_attempts=2)
    cell_key = f"CELL#{_key().logical_call_key}"
    runner.items[cell_key] = {
        "authority_key": _s(authority.authority_key),
        "record_key": _s(cell_key),
        "attempt_count": _n(2),
        "logical_call_key": _s(_key().logical_call_key),
    }

    with pytest.raises(AttemptLimitExceededError):
        authority.authorize_attempt(_key(), reservation_microusd=1)

    assert not any(op == "transact-write-items" for op, _ in runner.calls)


def test_ambiguous_failure_keeps_reservation_and_updates_shared_breaker() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner, clock=lambda: 1_000.25)
    lease = authority.authorize_attempt(_key(), reservation_microusd=250_000)

    authority.record_failure(lease, failure_type="TimeoutError", ambiguous=True)

    _, payload = runner.calls[-1]
    rendered = json.dumps(payload, sort_keys=True)
    assert "ambiguous_attempt_count :one" in rendered
    assert "failure_count" in rendered
    assert "committed_microusd :release" not in rendered
    assert '"N": "1000.25"' in rendered

    attempt = runner.items[
        f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"
    ]
    ledger = runner.items["LEDGER"]
    assert attempt["status"] == _s("ambiguous")
    assert attempt["failure_type"] == _s("TimeoutError")
    assert ledger["committed_microusd"] == _n(250_000)
    assert ledger["reserved_attempt_count"] == _n(0)
    assert ledger["ambiguous_attempt_count"] == _n(1)
    assert ledger["failure_count"] == _n(1)


def test_definite_failure_releases_reservation_but_still_counts_for_breaker() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    lease = authority.authorize_attempt(_key(), reservation_microusd=250_000)

    authority.record_failure(lease, failure_type="HTTP400", ambiguous=False)

    _, payload = runner.calls[-1]
    rendered = json.dumps(payload, sort_keys=True)
    assert "failed_attempt_count :one" in rendered
    assert "committed_microusd :release" in rendered
    assert '"N": "-250000"' in rendered

    attempt = runner.items[
        f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"
    ]
    ledger = runner.items["LEDGER"]
    assert attempt["status"] == _s("failed_nonbillable")
    assert ledger["committed_microusd"] == _n(0)
    assert ledger["reserved_attempt_count"] == _n(0)
    assert ledger["failed_attempt_count"] == _n(1)
    assert ledger["failure_count"] == _n(1)


def test_response_settlement_is_atomic_with_ledger_release() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    lease = authority.authorize_attempt(_key(), reservation_microusd=250_000)

    authority.record_response(
        lease,
        input_tokens=100,
        output_tokens=20,
        actual_microusd=75_000,
        response_sha256="a" * 64,
    )

    operation, payload = runner.calls[-1]
    assert operation == "transact-write-items"
    items = cast(list[dict[str, object]], payload["TransactItems"])
    assert len(items) == 2
    rendered = json.dumps(payload, sort_keys=True)
    assert "#status = :reserved" in rendered
    assert '"N": "-175000"' in rendered
    assert "settled_attempt_count :one" in rendered

    attempt = runner.items[
        f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"
    ]
    ledger = runner.items["LEDGER"]
    assert attempt["status"] == _s("settled")
    assert attempt["actual_microusd"] == _n(75_000)
    assert ledger["committed_microusd"] == _n(75_000)
    assert ledger["reserved_attempt_count"] == _n(0)
    assert ledger["settled_attempt_count"] == _n(1)


def test_usage_marker_is_single_use_and_same_attempt_retry_is_idempotent() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    first = authority.authorize_attempt(
        _key(case_id="first"), reservation_microusd=400_000
    )
    second = authority.authorize_attempt(
        _key(case_id="second"), reservation_microusd=400_000
    )
    authority.record_failure(first, failure_type="TimeoutError", ambiguous=True)
    authority.record_failure(second, failure_type="TimeoutError", ambiguous=True)

    for _ in range(2):
        authority.reconcile_ambiguous(
            first,
            usage_record_id="provider-usage-record-1",
            usage_record_sha256="7" * 64,
            billed_microusd=None,
        )

    with pytest.raises(ReconciliationMismatchError):
        authority.reconcile_ambiguous(
            second,
            usage_record_id="provider-usage-record-1",
            usage_record_sha256="7" * 64,
            billed_microusd=None,
        )

    ledger = runner.items["LEDGER"]
    assert ledger["committed_microusd"] == _n(400_000)
    assert ledger["ambiguous_attempt_count"] == _n(1)
    assert sum(record_key.startswith("USAGE#") for record_key in runner.items) == 1


def test_remote_authority_rejects_mutated_and_foreign_leases() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    lease = authority.authorize_attempt(_key(), reservation_microusd=500_000)

    with pytest.raises(AttemptStateError):
        authority.record_failure(
            replace(lease, reservation_microusd=499_999),
            failure_type="TimeoutError",
            ambiguous=True,
        )
    with pytest.raises(AttemptStateError):
        authority.record_response(
            replace(lease, attempt_id="0" * 64),
            input_tokens=1,
            output_tokens=1,
            actual_microusd=1,
            response_sha256="1" * 64,
        )
    with pytest.raises(AttemptStateError):
        authority.record_failure(
            replace(lease, authority_identity_sha256="8" * 64),
            failure_type="TimeoutError",
            ambiguous=True,
        )

    attempt = runner.items[
        f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"
    ]
    assert attempt["status"] == _s("reserved")
    assert runner.items["LEDGER"]["committed_microusd"] == _n(500_000)


def test_above_reservation_cost_poisons_remote_authority() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    lease = authority.authorize_attempt(_key(), reservation_microusd=500_000)

    with pytest.raises(SettlementError, match="poisoned"):
        authority.record_response(
            lease,
            input_tokens=1,
            output_tokens=1,
            actual_microusd=500_001,
            response_sha256="3" * 64,
        )
    with pytest.raises(AuthorityPoisonedError):
        authority.authorize_attempt(
            _key(case_id="after-under-reservation"), reservation_microusd=1
        )

    snapshot = authority.snapshot()
    assert snapshot.authority_poisoned is True
    assert snapshot.breaker_open is True
    assert snapshot.committed_microusd == 500_000
    poison_transaction = next(
        payload
        for operation, payload in reversed(runner.calls)
        if operation == "transact-write-items"
    )
    assert isinstance(poison_transaction.get("ClientRequestToken"), str)


def test_remote_attempt_is_adopted_after_crash_and_settled_idempotently() -> None:
    runner = InMemoryDynamoRunner()
    key = _key()
    original_authority = _authority(runner)
    original = original_authority.authorize_attempt(key, reservation_microusd=500_000)

    recovered = _authority(runner)
    adopted = recovered.adopt_attempt(
        key,
        attempt_ordinal=original.attempt_ordinal,
    )
    assert adopted == original
    for _ in range(2):
        recovered.record_response(
            adopted,
            input_tokens=10,
            output_tokens=5,
            actual_microusd=125_000,
            response_sha256="4" * 64,
        )

    snapshot = recovered.snapshot()
    assert snapshot.committed_microusd == 125_000
    assert snapshot.reserved_attempt_count == 0
    assert snapshot.settled_attempt_count == 1


def test_every_remote_transition_has_an_idempotency_token() -> None:
    runner = InMemoryDynamoRunner()
    authority = _authority(runner)
    response = authority.authorize_attempt(
        _key(case_id="response"), reservation_microusd=100_000
    )
    authority.record_response(
        response,
        input_tokens=1,
        output_tokens=1,
        actual_microusd=50_000,
        response_sha256="5" * 64,
    )
    ambiguous = authority.authorize_attempt(
        _key(case_id="ambiguous"), reservation_microusd=100_000
    )
    authority.record_failure(
        ambiguous,
        failure_type="TimeoutError",
        ambiguous=True,
    )
    authority.reconcile_ambiguous(
        ambiguous,
        usage_record_id="usage-token-check",
        usage_record_sha256="6" * 64,
        billed_microusd=None,
    )

    transactions = [
        payload
        for operation, payload in runner.calls
        if operation == "transact-write-items"
    ]
    assert len(transactions) == 5
    assert all(
        isinstance(payload.get("ClientRequestToken"), str)
        and len(cast(str, payload["ClientRequestToken"])) == 36
        for payload in transactions
    )


def test_aws_cli_runner_passes_json_without_shell_or_environment_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        args: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed["args"] = args
        observed.update(kwargs)
        return subprocess.CompletedProcess(args, 0, stdout='{"Item": {}}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = AwsCliDynamoCommandRunner(region="us-east-1")
    result = runner("get-item", {"TableName": "authority-table"})

    args = cast(tuple[str, ...], observed["args"])
    assert args[:3] == ("aws", "dynamodb", "get-item")
    assert args[args.index("--cli-input-json") + 1] == (
        '{"TableName":"authority-table"}'
    )
    assert "shell" not in observed
    assert "env" not in observed
    assert result == {"Item": {}}


@pytest.mark.parametrize(
    "message",
    ("ConditionalCheckFailedException", "TransactionCanceledException"),
)
def test_aws_cli_runner_classifies_conditional_failures_for_safe_retry(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    def fake_run(
        args: tuple[str, ...], **_: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 255, stdout="", stderr=message)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(DynamoDbConditionalError):
        AwsCliDynamoCommandRunner(region="us-east-1")("get-item", {})


def _authority(
    runner: InMemoryDynamoRunner,
    *,
    cap_microusd: int = 1_000_000,
    max_billable_attempts: int = 3,
    failure_threshold: int = 3,
    clock: Callable[[], float] | None = None,
) -> DynamoDbProviderSpendAuthority:
    return DynamoDbProviderSpendAuthority(
        table_name="authority-table",
        authority_identity_sha256=hashlib.sha256(_TABLE_ARN.encode()).hexdigest(),
        cycle_id="cycle-1",
        provider="openai",
        account="primary-account-alias",
        cap_microusd=cap_microusd,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256="f" * 64,
            max_billable_attempts=max_billable_attempts,
            failure_threshold=failure_threshold,
            failure_window_seconds=300,
        ),
        region="us-east-1",
        runner=runner,
        clock=clock,
    )


def _key(
    *,
    stage: str = "official-eval",
    case_id: str = "case-1",
) -> ProviderSpendKey:
    return ProviderSpendKey(
        cycle_id="cycle-1",
        provider="openai",
        account="primary-account-alias",
        stage=stage,
        model_key="openai:gpt-test",
        case_id=case_id,
        ablation="full_packet",
        repeat_index=1,
    )


def _s(value: str) -> AttributeValue:
    return {"S": value}


def _n(value: int | float) -> AttributeValue:
    return {"N": str(value)}


def _set_failure_events(
    runner: InMemoryDynamoRunner,
    events: list[float],
) -> None:
    rendered = json.dumps(events, separators=(",", ":"))
    ledger = runner.items["LEDGER"]
    ledger["failure_count"] = _n(len(events))
    ledger["failure_events_json"] = _s(rendered)
    ledger["failure_events_sha256"] = _s(hashlib.sha256(rendered.encode()).hexdigest())


_TABLE_ARN = "arn:aws:dynamodb:us-east-1:123456789012:table/authority-table"

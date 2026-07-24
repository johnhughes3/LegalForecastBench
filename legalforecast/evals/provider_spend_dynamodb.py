"""DynamoDB implementation of the official provider spend authority."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from legalforecast.evals.provider_spend_control import (
    AttemptLease,
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
    SpendControlSnapshot,
)

DYNAMODB_AUTHORITY_SCHEMA_VERSION = "legalforecast.provider_spend_dynamodb.v2"
_LEDGER_RECORD_KEY = "LEDGER"
_MAX_TRANSACTION_RETRIES = 8

JsonObject = dict[str, object]
AttributeValue = dict[str, str]
AttributeMap = dict[str, AttributeValue]


class DynamoDbAuthorityError(RuntimeError):
    """Raised when the remote authority cannot prove a safe state transition."""


class DynamoDbConditionalError(DynamoDbAuthorityError):
    """Raised when DynamoDB rejects a conditional or transactional write."""


class DynamoDbIndeterminateError(DynamoDbAuthorityError):
    """Raised when a transaction may have committed without an observed result."""


class DynamoCommandRunner(Protocol):
    """Minimal DynamoDB command surface used by the spend authority."""

    def __call__(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class AwsCliDynamoCommandRunner:
    """Invoke the installed AWS CLI without a shell or credential logging."""

    region: str
    executable: str = "aws"
    timeout_seconds: float = 30.0

    def __call__(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        try:
            completed = subprocess.run(
                (
                    self.executable,
                    "dynamodb",
                    operation,
                    "--region",
                    self.region,
                    "--cli-input-json",
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    "--output",
                    "json",
                    "--no-cli-pager",
                ),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            error_type: type[DynamoDbAuthorityError] = (
                DynamoDbIndeterminateError
                if operation == "transact-write-items"
                else DynamoDbAuthorityError
            )
            raise error_type(
                f"aws dynamodb {operation} did not return before the safe timeout"
            ) from exc
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            if (
                "ConditionalCheckFailed" in message
                or "TransactionCanceledException" in message
            ):
                raise DynamoDbConditionalError(
                    f"aws dynamodb {operation} rejected a conditional write"
                )
            error_type = (
                DynamoDbIndeterminateError
                if operation == "transact-write-items"
                else DynamoDbAuthorityError
            )
            raise error_type(
                f"aws dynamodb {operation} failed with exit "
                f"{completed.returncode}; provider details were suppressed"
            )
        if not completed.stdout.strip():
            return {}
        try:
            loaded: object = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DynamoDbAuthorityError(
                f"aws dynamodb {operation} returned invalid JSON"
            ) from exc
        if not isinstance(loaded, dict):
            raise DynamoDbAuthorityError(
                f"aws dynamodb {operation} returned a non-object payload"
            )
        return cast(JsonObject, loaded)


class DynamoDbProviderSpendAuthority:
    """Cross-runner provider/account authority using conditional transactions."""

    def __init__(
        self,
        *,
        table_name: str,
        authority_identity_sha256: str,
        cycle_id: str,
        provider: str,
        account: str,
        cap_microusd: int,
        policy: FrozenAttemptPolicy,
        region: str,
        runner: DynamoCommandRunner | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.table_name = _identity(table_name, "table_name")
        self.authority_identity_sha256 = _sha256(
            authority_identity_sha256,
            "authority_identity_sha256",
        )
        self.cycle_id = _identity(cycle_id, "cycle_id")
        self.provider = _identity(provider, "provider").lower()
        self.account = _identity(account, "account")
        self.account_sha256 = hashlib.sha256(self.account.encode()).hexdigest()
        self.cap_microusd = _positive_int(cap_microusd, "cap_microusd")
        self.policy = policy
        self._runner = runner or AwsCliDynamoCommandRunner(
            region=_identity(region, "region")
        )
        self._clock = clock or _time
        self._verify_table_identity()
        self.authority_key = hashlib.sha256(
            (
                f"{self.authority_identity_sha256}\0{self.cycle_id}\0"
                f"{self.provider}\0{self.account_sha256}"
            ).encode()
        ).hexdigest()
        self._ensure_ledger()

    def _verify_table_identity(self) -> None:
        """Bind the policy hash to the actual table ARN and composite key schema."""

        result = self._runner("describe-table", {"TableName": self.table_name})
        raw_table = result.get("Table")
        if not isinstance(raw_table, dict):
            raise DynamoDbAuthorityError("DynamoDB DescribeTable lacks Table")
        table = cast(Mapping[str, object], raw_table)
        raw_arn = table.get("TableArn")
        if not isinstance(raw_arn, str) or not raw_arn.strip():
            raise DynamoDbAuthorityError("DynamoDB DescribeTable lacks TableArn")
        actual_identity = hashlib.sha256(raw_arn.strip().encode()).hexdigest()
        if actual_identity != self.authority_identity_sha256:
            raise AuthorityIdentityMismatchError(
                "DynamoDB table ARN differs from frozen authority identity"
            )
        raw_key_schema = table.get("KeySchema")
        if not isinstance(raw_key_schema, list):
            raise AuthorityIdentityMismatchError(
                "DynamoDB authority table key schema differs from frozen contract"
            )
        key_schema = cast(list[object], raw_key_schema)
        actual_key_schema: set[tuple[object, object]] = set()
        for raw_key in key_schema:
            if not isinstance(raw_key, Mapping):
                raise AuthorityIdentityMismatchError(
                    "DynamoDB authority table key schema differs from frozen contract"
                )
            key = cast(Mapping[object, object], raw_key)
            actual_key_schema.add((key.get("AttributeName"), key.get("KeyType")))
        expected_key_schema = {
            ("authority_key", "HASH"),
            ("record_key", "RANGE"),
        }
        if actual_key_schema != expected_key_schema or len(key_schema) != 2:
            raise AuthorityIdentityMismatchError(
                "DynamoDB authority table key schema differs from frozen contract"
            )

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        """Atomically reserve cap, increment the cell, and create an attempt."""

        self._verify_key_scope(key)
        reservation = _positive_int(
            reservation_microusd,
            "reservation_microusd",
        )
        for _ in range(_MAX_TRANSACTION_RETRIES):
            ledger = self._get_required(_LEDGER_RECORD_KEY)
            self._verify_ledger(ledger)
            self._raise_if_poisoned(ledger)
            now = self._clock()
            active_failures = self._active_failure_events(ledger, now=now)
            if len(active_failures) >= self.policy.failure_threshold:
                raise CircuitBreakerOpenError(
                    f"provider/account circuit breaker is open for "
                    f"{self.provider}/{self.account}"
                )
            committed = _number(ledger, "committed_microusd")
            if committed + reservation > self.cap_microusd:
                raise ProviderCapExceededError(
                    f"provider reservation would exceed frozen {self.provider}/"
                    f"{self.account} cap"
                )
            cell_record_key = f"CELL#{key.logical_call_key}"
            cell = self._get_optional(cell_record_key)
            current_attempts = 0 if cell is None else _number(cell, "attempt_count")
            if current_attempts >= self.policy.max_billable_attempts:
                raise AttemptLimitExceededError(
                    "logical provider call reached its frozen billable-attempt limit"
                )
            ordinal = current_attempts + 1
            attempt_id = hashlib.sha256(
                f"{self.authority_key}\0{key.logical_call_key}\0{ordinal}".encode()
            ).hexdigest()
            transaction = self._authorization_transaction(
                key=key,
                reservation=reservation,
                expected_attempts=current_attempts,
                ordinal=ordinal,
                attempt_id=attempt_id,
                now=now,
                expected_failure_events_sha256=_text(ledger, "failure_events_sha256"),
            )
            try:
                self._runner(
                    "transact-write-items",
                    _with_client_token(transaction),
                )
            except DynamoDbConditionalError:
                continue
            except DynamoDbIndeterminateError:
                adopted = self._adopt_exact_if_present(
                    key,
                    attempt_ordinal=ordinal,
                    attempt_id=attempt_id,
                    reservation_microusd=reservation,
                )
                if adopted is None:
                    raise
                return adopted
            return AttemptLease(
                attempt_id=attempt_id,
                authority_identity_sha256=self.authority_identity_sha256,
                logical_call_key=key.logical_call_key,
                attempt_ordinal=ordinal,
                reservation_microusd=reservation,
            )
        raise DynamoDbAuthorityError(
            "provider spend authorization could not converge after concurrent writes"
        )

    def adopt_attempt(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int | None = None,
    ) -> AttemptLease:
        """Adopt a crash-reserved attempt without consuming another ordinal."""

        self._verify_key_scope(key)
        ledger = self._get_required(_LEDGER_RECORD_KEY)
        self._verify_ledger(ledger)
        self._raise_if_poisoned(ledger)
        if attempt_ordinal is None:
            cell = self._get_required(f"CELL#{key.logical_call_key}")
            ordinal = _number(cell, "attempt_count")
        else:
            ordinal = _positive_int(attempt_ordinal, "attempt_ordinal")
        attempt = self._get_required(f"ATTEMPT#{key.logical_call_key}#{ordinal:04d}")
        if _text(attempt, "status") not in {"reserved", "settled"}:
            raise AttemptStateError(
                "provider attempt adoption requires a replayable attempt"
            )
        return self._lease_from_attempt(attempt)

    def record_response(
        self,
        lease: AttemptLease,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_microusd: int,
        response_sha256: str,
    ) -> None:
        """Settle one response and release unused reservation atomically."""

        if input_tokens < 0 or output_tokens < 0:
            raise SettlementError("provider token counts cannot be negative")
        if actual_microusd < 0:
            raise SettlementError("provider actual cost cannot be negative")
        attempt = self._attempt_for_lease(lease)
        stored_reservation = _number(attempt, "reservation_microusd")
        if actual_microusd > stored_reservation:
            self._poison_authority(
                lease,
                reason="observed provider cost exceeds frozen reservation",
            )
            raise SettlementError(
                "provider actual cost exceeds the frozen conservative reservation; "
                "authority is poisoned"
            )
        response_digest = _sha256(response_sha256, "response_sha256")
        delta = actual_microusd - stored_reservation
        transaction: JsonObject = {
            "TransactItems": [
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_attempt_record_key(lease)),
                        "UpdateExpression": (
                            "SET #status = :settled, input_tokens = :input, "
                            "output_tokens = :output, actual_microusd = :actual, "
                            "response_sha256 = :response, completed_at_epoch = :now"
                        ),
                        "ConditionExpression": (
                            "#status = :reserved AND attempt_id = :attempt_id AND "
                            "logical_call_key = :logical AND "
                            "attempt_ordinal = :ordinal AND "
                            "reservation_microusd = :reservation AND "
                            "authority_identity_sha256 = :identity"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":settled": _s("settled"),
                            ":reserved": _s("reserved"),
                            ":attempt_id": _s(lease.attempt_id),
                            ":logical": _s(lease.logical_call_key),
                            ":ordinal": _n(lease.attempt_ordinal),
                            ":reservation": _n(stored_reservation),
                            ":identity": _s(self.authority_identity_sha256),
                            ":input": _n(input_tokens),
                            ":output": _n(output_tokens),
                            ":actual": _n(actual_microusd),
                            ":response": _s(response_digest),
                            ":now": _n(self._clock()),
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_LEDGER_RECORD_KEY),
                        "UpdateExpression": (
                            "ADD committed_microusd :delta, "
                            "reserved_attempt_count :minus_one, "
                            "settled_attempt_count :one"
                        ),
                        "ConditionExpression": (
                            "authority_identity_sha256 = :identity AND "
                            "authority_poisoned = :zero AND "
                            "committed_microusd >= :reservation"
                        ),
                        "ExpressionAttributeValues": {
                            ":delta": _n(delta),
                            ":minus_one": _n(-1),
                            ":one": _n(1),
                            ":identity": _s(self.authority_identity_sha256),
                            ":zero": _n(0),
                            ":reservation": _n(stored_reservation),
                        },
                    }
                },
            ]
        }
        try:
            self._runner("transact-write-items", _with_client_token(transaction))
        except (DynamoDbConditionalError, DynamoDbIndeterminateError) as exc:
            attempt = self._get_required(_attempt_record_key(lease))
            expected = (
                "settled",
                input_tokens,
                output_tokens,
                actual_microusd,
                response_digest,
            )
            actual = (
                _text(attempt, "status"),
                _number(attempt, "input_tokens"),
                _number(attempt, "output_tokens"),
                _number(attempt, "actual_microusd"),
                _text(attempt, "response_sha256"),
            )
            if actual != expected:
                if isinstance(exc, DynamoDbIndeterminateError):
                    raise
                raise AttemptStateError(
                    "settled DynamoDB provider response evidence changed"
                ) from None

    def record_failure(
        self,
        lease: AttemptLease,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        """Record a failure and update the shared failure window atomically."""

        normalized_failure = _identity(failure_type, "failure_type")
        target = "ambiguous" if ambiguous else "failed_nonbillable"
        for _ in range(_MAX_TRANSACTION_RETRIES):
            attempt = self._attempt_for_lease(lease)
            status = _text(attempt, "status")
            if (
                status == target
                and _text(attempt, "failure_type") == normalized_failure
            ):
                return
            if status != "reserved":
                raise AttemptStateError(
                    f"provider failure cannot transition attempt in {status} state"
                )
            ledger = self._get_required(_LEDGER_RECORD_KEY)
            self._verify_ledger(ledger)
            self._raise_if_poisoned(ledger)
            now = self._clock()
            active_events = self._active_failure_events(ledger, now=now)
            event_time = max(now, active_events[-1] if active_events else now)
            next_events = (*active_events, event_time)[-self.policy.failure_threshold :]
            next_events_json = _canonical_json(list(next_events))
            next_events_sha256 = hashlib.sha256(next_events_json.encode()).hexdigest()
            try:
                self._runner(
                    "transact-write-items",
                    _with_client_token(
                        self._failure_transaction(
                            lease=lease,
                            failure_type=normalized_failure,
                            target=target,
                            ambiguous=ambiguous,
                            now=now,
                            stored_reservation=_number(attempt, "reservation_microusd"),
                            expected_failure_events_sha256=_text(
                                ledger, "failure_events_sha256"
                            ),
                            next_failure_events_json=next_events_json,
                            next_failure_events_sha256=next_events_sha256,
                            next_failure_count=len(next_events),
                        )
                    ),
                )
            except DynamoDbConditionalError:
                continue
            except DynamoDbIndeterminateError:
                observed = self._attempt_for_lease(lease)
                if (
                    _text(observed, "status") == target
                    and _text(observed, "failure_type") == normalized_failure
                ):
                    return
                raise
            return
        raise DynamoDbAuthorityError(
            "provider failure recording could not converge after concurrent writes"
        )

    def reconcile_ambiguous(
        self,
        lease: AttemptLease,
        *,
        usage_record_id: str,
        usage_record_sha256: str,
        billed_microusd: int | None,
    ) -> None:
        """Reconcile ambiguity or a crash-reserved attempt with one-time evidence."""

        usage_id = _identity(usage_record_id, "usage_record_id")
        usage_sha256 = _sha256(usage_record_sha256, "usage_record_sha256")
        if billed_microusd is not None and billed_microusd < 0:
            raise SettlementError("reconciled provider cost cannot be negative")
        attempt = self._attempt_for_lease(lease)
        stored_reservation = _number(attempt, "reservation_microusd")
        if billed_microusd is not None and billed_microusd > stored_reservation:
            self._poison_authority(
                lease,
                reason="reconciled provider cost exceeds frozen reservation",
            )
            raise SettlementError(
                "reconciled provider cost exceeds the frozen reservation; "
                "authority is poisoned"
            )
        target = "reconciled_unbilled" if billed_microusd is None else "settled"
        actual_cost = 0 if billed_microusd is None else billed_microusd
        delta = actual_cost - stored_reservation
        settled_increment = 0 if billed_microusd is None else 1
        unbilled_increment = 1 if billed_microusd is None else 0
        source_status = _text(attempt, "status")
        if source_status in {"settled", "reconciled_unbilled"}:
            self._verify_reconciliation_result(
                lease,
                attempt=attempt,
                target=target,
                actual_cost=actual_cost,
                usage_id=usage_id,
                usage_sha256=usage_sha256,
            )
            return
        if source_status not in {"ambiguous", "reserved"}:
            raise AttemptStateError(
                "only ambiguous or crash-reserved attempts can be reconciled, "
                f"got {source_status}"
            )
        reserved_decrement = -1 if source_status == "reserved" else 0
        ambiguous_decrement = -1 if source_status == "ambiguous" else 0
        usage_record_key = _usage_record_key(usage_id)
        transaction: JsonObject = {
            "TransactItems": [
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_attempt_record_key(lease)),
                        "UpdateExpression": (
                            "SET #status = :target, actual_microusd = :actual, "
                            "usage_record_id = :usage_id, "
                            "usage_record_sha256 = :usage_sha, "
                            "completed_at_epoch = :now"
                        ),
                        "ConditionExpression": (
                            "#status = :source AND attempt_id = :attempt_id AND "
                            "logical_call_key = :logical AND "
                            "attempt_ordinal = :ordinal AND "
                            "reservation_microusd = :reservation AND "
                            "authority_identity_sha256 = :identity"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":target": _s(target),
                            ":actual": _n(actual_cost),
                            ":usage_id": _s(usage_id),
                            ":usage_sha": _s(usage_sha256),
                            ":now": _n(self._clock()),
                            ":source": _s(source_status),
                            ":attempt_id": _s(lease.attempt_id),
                            ":logical": _s(lease.logical_call_key),
                            ":ordinal": _n(lease.attempt_ordinal),
                            ":reservation": _n(stored_reservation),
                            ":identity": _s(self.authority_identity_sha256),
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_LEDGER_RECORD_KEY),
                        "UpdateExpression": (
                            "ADD committed_microusd :delta, "
                            "reserved_attempt_count :reserved_delta, "
                            "ambiguous_attempt_count :ambiguous_delta, "
                            "settled_attempt_count :settled, "
                            "reconciled_unbilled_count :unbilled"
                        ),
                        "ConditionExpression": (
                            "authority_identity_sha256 = :identity AND "
                            "authority_poisoned = :zero AND "
                            "committed_microusd >= :reservation"
                        ),
                        "ExpressionAttributeValues": {
                            ":delta": _n(delta),
                            ":reserved_delta": _n(reserved_decrement),
                            ":ambiguous_delta": _n(ambiguous_decrement),
                            ":settled": _n(settled_increment),
                            ":unbilled": _n(unbilled_increment),
                            ":identity": _s(self.authority_identity_sha256),
                            ":zero": _n(0),
                            ":reservation": _n(stored_reservation),
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": self.table_name,
                        "Item": {
                            **self._key(usage_record_key),
                            "attempt_id": _s(lease.attempt_id),
                            "usage_record_id_sha256": _s(
                                hashlib.sha256(usage_id.encode()).hexdigest()
                            ),
                            "usage_record_sha256": _s(usage_sha256),
                            "actual_microusd": _n(actual_cost),
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(authority_key) AND "
                            "attribute_not_exists(record_key)"
                        ),
                    }
                },
            ]
        }
        try:
            self._runner("transact-write-items", _with_client_token(transaction))
        except (DynamoDbConditionalError, DynamoDbIndeterminateError) as exc:
            attempt = self._get_required(_attempt_record_key(lease))
            try:
                self._verify_reconciliation_result(
                    lease,
                    attempt=attempt,
                    target=target,
                    actual_cost=actual_cost,
                    usage_id=usage_id,
                    usage_sha256=usage_sha256,
                )
            except ReconciliationMismatchError:
                if isinstance(exc, DynamoDbIndeterminateError):
                    raise
                raise

    def snapshot(self) -> SpendControlSnapshot:
        """Read exact accounting and breaker state from the ledger singleton."""

        ledger = self._get_required(_LEDGER_RECORD_KEY)
        self._verify_ledger(ledger)
        poisoned = _number(ledger, "authority_poisoned") == 1
        now = self._clock()
        active_failures = len(self._active_failure_events(ledger, now=now))
        return SpendControlSnapshot(
            authority_identity_sha256=self.authority_identity_sha256,
            cycle_id=self.cycle_id,
            provider=self.provider,
            account=self.account,
            cap_microusd=self.cap_microusd,
            committed_microusd=_number(ledger, "committed_microusd"),
            attempt_count=_number(ledger, "attempt_count"),
            reserved_attempt_count=_number(ledger, "reserved_attempt_count"),
            ambiguous_attempt_count=_number(ledger, "ambiguous_attempt_count"),
            settled_attempt_count=_number(ledger, "settled_attempt_count"),
            failure_count_in_window=active_failures,
            breaker_open=(active_failures >= self.policy.failure_threshold or poisoned),
            authority_poisoned=poisoned,
        )

    def _ensure_ledger(self) -> None:
        existing = self._get_optional(_LEDGER_RECORD_KEY)
        if existing is None:
            try:
                self._runner(
                    "put-item",
                    {
                        "TableName": self.table_name,
                        "Item": self._initial_ledger(),
                        "ConditionExpression": (
                            "attribute_not_exists(authority_key) AND "
                            "attribute_not_exists(record_key)"
                        ),
                    },
                )
            except DynamoDbConditionalError:
                existing = self._get_required(_LEDGER_RECORD_KEY)
            else:
                existing = self._get_required(_LEDGER_RECORD_KEY)
        self._verify_ledger(existing)

    def _initial_ledger(self) -> AttributeMap:
        empty_events = _canonical_json([])
        return {
            **self._key(_LEDGER_RECORD_KEY),
            "schema_version": _s(DYNAMODB_AUTHORITY_SCHEMA_VERSION),
            "authority_identity_sha256": _s(self.authority_identity_sha256),
            "cycle_id": _s(self.cycle_id),
            "provider": _s(self.provider),
            "account_sha256": _s(self.account_sha256),
            "cap_microusd": _n(self.cap_microusd),
            "reservation_ledger_sha256": _s(self.policy.reservation_ledger_sha256),
            "max_billable_attempts": _n(self.policy.max_billable_attempts),
            "failure_threshold": _n(self.policy.failure_threshold),
            "failure_window_seconds": _n(self.policy.failure_window_seconds),
            "committed_microusd": _n(0),
            "attempt_count": _n(0),
            "reserved_attempt_count": _n(0),
            "ambiguous_attempt_count": _n(0),
            "settled_attempt_count": _n(0),
            "failed_attempt_count": _n(0),
            "reconciled_unbilled_count": _n(0),
            "failure_count": _n(0),
            "failure_events_json": _s(empty_events),
            "failure_events_sha256": _s(
                hashlib.sha256(empty_events.encode()).hexdigest()
            ),
            "authority_poisoned": _n(0),
        }

    def _verify_ledger(self, item: Mapping[str, AttributeValue]) -> None:
        expected = {
            "schema_version": DYNAMODB_AUTHORITY_SCHEMA_VERSION,
            "authority_identity_sha256": self.authority_identity_sha256,
            "cycle_id": self.cycle_id,
            "provider": self.provider,
            "account_sha256": self.account_sha256,
            "reservation_ledger_sha256": self.policy.reservation_ledger_sha256,
        }
        for field_name, expected_value in expected.items():
            if _text(item, field_name) != expected_value:
                raise AuthorityIdentityMismatchError(
                    f"DynamoDB authority {field_name} differs from frozen identity"
                )
        expected_numbers = {
            "cap_microusd": self.cap_microusd,
            "max_billable_attempts": self.policy.max_billable_attempts,
            "failure_threshold": self.policy.failure_threshold,
            "failure_window_seconds": self.policy.failure_window_seconds,
        }
        for field_name, expected_value in expected_numbers.items():
            if _number(item, field_name) != expected_value:
                raise AuthorityIdentityMismatchError(
                    f"DynamoDB authority {field_name} differs from frozen policy"
                )

    def _authorization_transaction(
        self,
        *,
        key: ProviderSpendKey,
        reservation: int,
        expected_attempts: int,
        ordinal: int,
        attempt_id: str,
        now: float,
        expected_failure_events_sha256: str,
    ) -> JsonObject:
        remaining = self.cap_microusd - reservation
        cell_key = f"CELL#{key.logical_call_key}"
        attempt_key = f"ATTEMPT#{key.logical_call_key}#{ordinal:04d}"
        cell_condition = (
            "attribute_not_exists(attempt_count)"
            if expected_attempts == 0
            else "attempt_count = :expected"
        )
        cell_values: dict[str, AttributeValue] = {
            ":next": _n(ordinal),
            ":logical": _s(key.logical_call_key),
        }
        if expected_attempts:
            cell_values[":expected"] = _n(expected_attempts)
        return {
            "TransactItems": [
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_LEDGER_RECORD_KEY),
                        "UpdateExpression": (
                            "ADD committed_microusd :reservation, attempt_count :one, "
                            "reserved_attempt_count :one"
                        ),
                        "ConditionExpression": (
                            "authority_identity_sha256 = :identity AND "
                            "authority_poisoned = :zero AND "
                            "committed_microusd <= :remaining AND "
                            "failure_events_sha256 = :failure_events_sha"
                        ),
                        "ExpressionAttributeValues": {
                            ":reservation": _n(reservation),
                            ":one": _n(1),
                            ":identity": _s(self.authority_identity_sha256),
                            ":zero": _n(0),
                            ":remaining": _n(remaining),
                            ":failure_events_sha": _s(expected_failure_events_sha256),
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(cell_key),
                        "UpdateExpression": (
                            "SET attempt_count = :next, logical_call_key = :logical"
                        ),
                        "ConditionExpression": cell_condition,
                        "ExpressionAttributeValues": cell_values,
                    }
                },
                {
                    "Put": {
                        "TableName": self.table_name,
                        "Item": {
                            **self._key(attempt_key),
                            "attempt_id": _s(attempt_id),
                            "authority_identity_sha256": _s(
                                self.authority_identity_sha256
                            ),
                            "logical_call_key": _s(key.logical_call_key),
                            "attempt_ordinal": _n(ordinal),
                            "cycle_id": _s(key.cycle_id),
                            "provider": _s(key.provider),
                            "account_sha256": _s(self.account_sha256),
                            "stage": _s(key.stage),
                            "model_key": _s(key.model_key),
                            "case_id": _s(key.case_id),
                            "ablation": _s(key.ablation),
                            "repeat_index": _n(key.repeat_index),
                            "reservation_microusd": _n(reservation),
                            "status": _s("reserved"),
                            "authorized_at_epoch": _n(now),
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(authority_key) AND "
                            "attribute_not_exists(record_key)"
                        ),
                    }
                },
            ]
        }

    def _failure_transaction(
        self,
        *,
        lease: AttemptLease,
        failure_type: str,
        target: str,
        ambiguous: bool,
        now: float,
        stored_reservation: int,
        expected_failure_events_sha256: str,
        next_failure_events_json: str,
        next_failure_events_sha256: str,
        next_failure_count: int,
    ) -> JsonObject:
        ledger_values: dict[str, AttributeValue] = {
            ":identity": _s(self.authority_identity_sha256),
            ":zero": _n(0),
            ":expected_failure_events_sha": _s(expected_failure_events_sha256),
            ":failure_events": _s(next_failure_events_json),
            ":failure_events_sha": _s(next_failure_events_sha256),
            ":failure_count": _n(next_failure_count),
            ":one": _n(1),
            ":minus_one": _n(-1),
        }
        update_expression = (
            "SET failure_count = :failure_count, "
            "failure_events_json = :failure_events, "
            "failure_events_sha256 = :failure_events_sha "
            "ADD reserved_attempt_count :minus_one"
        )
        if ambiguous:
            update_expression += ", ambiguous_attempt_count :one"
        else:
            update_expression += (
                ", failed_attempt_count :one, committed_microusd :release"
            )
            ledger_values[":release"] = _n(-stored_reservation)
        return {
            "TransactItems": [
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_attempt_record_key(lease)),
                        "UpdateExpression": (
                            "SET #status = :target, failure_type = :failure, "
                            "completed_at_epoch = :now"
                        ),
                        "ConditionExpression": (
                            "#status = :reserved AND attempt_id = :attempt_id AND "
                            "logical_call_key = :logical AND "
                            "attempt_ordinal = :ordinal AND "
                            "reservation_microusd = :reservation AND "
                            "authority_identity_sha256 = :identity"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":target": _s(target),
                            ":failure": _s(failure_type),
                            ":now": _n(now),
                            ":reserved": _s("reserved"),
                            ":attempt_id": _s(lease.attempt_id),
                            ":logical": _s(lease.logical_call_key),
                            ":ordinal": _n(lease.attempt_ordinal),
                            ":reservation": _n(stored_reservation),
                            ":identity": _s(self.authority_identity_sha256),
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_LEDGER_RECORD_KEY),
                        "UpdateExpression": update_expression,
                        "ConditionExpression": (
                            "authority_identity_sha256 = :identity AND "
                            "authority_poisoned = :zero AND "
                            "failure_events_sha256 = :expected_failure_events_sha"
                        ),
                        "ExpressionAttributeValues": ledger_values,
                    }
                },
            ]
        }

    def _active_failure_events(
        self,
        ledger: Mapping[str, AttributeValue],
        *,
        now: float,
    ) -> tuple[float, ...]:
        raw_events = _text(ledger, "failure_events_json")
        expected_sha256 = _text(ledger, "failure_events_sha256")
        if hashlib.sha256(raw_events.encode()).hexdigest() != expected_sha256:
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event payload differs from its durable digest"
            )
        try:
            loaded: object = json.loads(raw_events)
        except json.JSONDecodeError as exc:
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event payload is not valid JSON"
            ) from exc
        if not isinstance(loaded, list):
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event payload is not a numeric timestamp list"
            )
        loaded_events = cast(list[object], loaded)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in loaded_events
        ):
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event payload is not a numeric timestamp list"
            )
        events = tuple(float(cast(int | float, value)) for value in loaded_events)
        if any(value < 0 for value in events) or tuple(sorted(events)) != events:
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event timestamps are not monotonic"
            )
        if len(events) != _number(ledger, "failure_count"):
            raise DynamoDbAuthorityError(
                "DynamoDB failure-event count differs from its durable payload"
            )
        cutoff = now - self.policy.failure_window_seconds
        return tuple(value for value in events if value >= cutoff)

    def _attempt_for_lease(self, lease: AttemptLease) -> AttributeMap:
        if lease.authority_identity_sha256 != self.authority_identity_sha256:
            raise AttemptStateError("provider attempt authority identity differs")
        attempt = self._get_required(_attempt_record_key(lease))
        expected = (
            lease.attempt_id,
            self.authority_identity_sha256,
            lease.logical_call_key,
            lease.attempt_ordinal,
            lease.reservation_microusd,
        )
        actual = (
            _text(attempt, "attempt_id"),
            _text(attempt, "authority_identity_sha256"),
            _text(attempt, "logical_call_key"),
            _number(attempt, "attempt_ordinal"),
            _number(attempt, "reservation_microusd"),
        )
        if actual != expected:
            raise AttemptStateError("provider attempt lease identity differs")
        return attempt

    def _lease_from_attempt(
        self,
        attempt: Mapping[str, AttributeValue],
    ) -> AttemptLease:
        if (
            _text(attempt, "authority_identity_sha256")
            != self.authority_identity_sha256
        ):
            raise AttemptStateError("provider attempt authority identity differs")
        return AttemptLease(
            attempt_id=_text(attempt, "attempt_id"),
            authority_identity_sha256=self.authority_identity_sha256,
            logical_call_key=_text(attempt, "logical_call_key"),
            attempt_ordinal=_number(attempt, "attempt_ordinal"),
            reservation_microusd=_number(attempt, "reservation_microusd"),
        )

    def _adopt_exact_if_present(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int,
        attempt_id: str,
        reservation_microusd: int,
    ) -> AttemptLease | None:
        attempt = self._get_optional(
            f"ATTEMPT#{key.logical_call_key}#{attempt_ordinal:04d}"
        )
        if attempt is None:
            return None
        lease = self._lease_from_attempt(attempt)
        if (
            lease.attempt_id != attempt_id
            or lease.reservation_microusd != reservation_microusd
            or _text(attempt, "status") != "reserved"
        ):
            raise AttemptStateError(
                "indeterminate authorization produced conflicting durable state"
            )
        return lease

    def _raise_if_poisoned(self, ledger: Mapping[str, AttributeValue]) -> None:
        if _number(ledger, "authority_poisoned") == 1:
            raise AuthorityPoisonedError(
                "provider spend authority is poisoned by an integrity violation"
            )

    def _poison_authority(self, lease: AttemptLease, *, reason: str) -> None:
        attempt = self._attempt_for_lease(lease)
        stored_reservation = _number(attempt, "reservation_microusd")
        transaction: JsonObject = {
            "TransactItems": [
                {
                    "ConditionCheck": {
                        "TableName": self.table_name,
                        "Key": self._key(_attempt_record_key(lease)),
                        "ConditionExpression": (
                            "attempt_id = :attempt_id AND "
                            "authority_identity_sha256 = :identity AND "
                            "logical_call_key = :logical AND "
                            "attempt_ordinal = :ordinal AND "
                            "reservation_microusd = :reservation"
                        ),
                        "ExpressionAttributeValues": {
                            ":attempt_id": _s(lease.attempt_id),
                            ":identity": _s(self.authority_identity_sha256),
                            ":logical": _s(lease.logical_call_key),
                            ":ordinal": _n(lease.attempt_ordinal),
                            ":reservation": _n(stored_reservation),
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": self.table_name,
                        "Key": self._key(_LEDGER_RECORD_KEY),
                        "UpdateExpression": (
                            "SET authority_poisoned = :one, "
                            "poison_reason_sha256 = :reason"
                        ),
                        "ConditionExpression": (
                            "authority_identity_sha256 = :identity"
                        ),
                        "ExpressionAttributeValues": {
                            ":one": _n(1),
                            ":reason": _s(hashlib.sha256(reason.encode()).hexdigest()),
                            ":identity": _s(self.authority_identity_sha256),
                        },
                    }
                },
            ]
        }
        try:
            self._runner("transact-write-items", _with_client_token(transaction))
        except (DynamoDbConditionalError, DynamoDbIndeterminateError):
            ledger = self._get_required(_LEDGER_RECORD_KEY)
            self._verify_ledger(ledger)
            if _number(ledger, "authority_poisoned") != 1:
                raise

    def _verify_reconciliation_result(
        self,
        lease: AttemptLease,
        *,
        attempt: Mapping[str, AttributeValue],
        target: str,
        actual_cost: int,
        usage_id: str,
        usage_sha256: str,
    ) -> None:
        self._attempt_for_lease(lease)
        if _text(attempt, "status") != target:
            raise ReconciliationMismatchError(
                "DynamoDB provider usage reconciliation did not commit"
            )
        expected = (target, actual_cost, usage_id, usage_sha256)
        actual = (
            _text(attempt, "status"),
            _number(attempt, "actual_microusd"),
            _text(attempt, "usage_record_id"),
            _text(attempt, "usage_record_sha256"),
        )
        if actual != expected:
            raise ReconciliationMismatchError(
                "DynamoDB provider usage reconciliation evidence changed"
            )
        marker = self._get_required(_usage_record_key(usage_id))
        marker_expected = (
            lease.attempt_id,
            hashlib.sha256(usage_id.encode()).hexdigest(),
            usage_sha256,
            actual_cost,
        )
        marker_actual = (
            _text(marker, "attempt_id"),
            _text(marker, "usage_record_id_sha256"),
            _text(marker, "usage_record_sha256"),
            _number(marker, "actual_microusd"),
        )
        if marker_actual != marker_expected:
            raise ReconciliationMismatchError(
                "DynamoDB provider usage evidence is bound to another attempt"
            )

    def _get_optional(self, record_key: str) -> AttributeMap | None:
        result = self._runner(
            "get-item",
            {
                "TableName": self.table_name,
                "Key": self._key(record_key),
                "ConsistentRead": True,
            },
        )
        raw_item = result.get("Item")
        if raw_item is None:
            return None
        if not isinstance(raw_item, dict):
            raise DynamoDbAuthorityError("DynamoDB Item must be an object")
        return cast(AttributeMap, raw_item)

    def _get_required(self, record_key: str) -> AttributeMap:
        item = self._get_optional(record_key)
        if item is None:
            raise DynamoDbAuthorityError(
                f"DynamoDB authority record is missing: {record_key}"
            )
        return item

    def _key(self, record_key: str) -> AttributeMap:
        return {
            "authority_key": _s(self.authority_key),
            "record_key": _s(record_key),
        }

    def _verify_key_scope(self, key: ProviderSpendKey) -> None:
        if (key.cycle_id, key.provider, key.account) != (
            self.cycle_id,
            self.provider,
            self.account,
        ):
            raise AuthorityIdentityMismatchError(
                "provider attempt key differs from DynamoDB authority scope"
            )


def _time() -> float:
    import time

    return time.time()


def _attempt_record_key(lease: AttemptLease) -> str:
    return f"ATTEMPT#{lease.logical_call_key}#{lease.attempt_ordinal:04d}"


def _usage_record_key(usage_record_id: str) -> str:
    return f"USAGE#{hashlib.sha256(usage_record_id.encode()).hexdigest()}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _with_client_token(transaction: JsonObject) -> JsonObject:
    payload = _canonical_json(transaction)
    return {
        **transaction,
        "ClientRequestToken": hashlib.sha256(payload.encode()).hexdigest()[:36],
    }


def _identity(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _sha256(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return normalized


def _s(value: str) -> AttributeValue:
    return {"S": value}


def _n(value: int | float) -> AttributeValue:
    if isinstance(value, float):
        rendered = format(value, ".6f").rstrip("0").rstrip(".")
    else:
        rendered = str(value)
    return {"N": rendered or "0"}


def _text(item: Mapping[str, AttributeValue], field_name: str) -> str:
    try:
        return item[field_name]["S"]
    except KeyError as exc:
        raise DynamoDbAuthorityError(
            f"DynamoDB authority record lacks string {field_name}"
        ) from exc


def _number(item: Mapping[str, AttributeValue], field_name: str) -> int:
    try:
        raw = item[field_name]["N"]
        return int(raw)
    except (KeyError, ValueError) as exc:
        raise DynamoDbAuthorityError(
            f"DynamoDB authority record lacks integer {field_name}"
        ) from exc

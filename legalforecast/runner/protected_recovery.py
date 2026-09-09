"""Plan and apply bounded recovery of official provider spend state.

The plan path performs only DynamoDB reads.  The apply path re-reads the same
authority, reconciles validated terminal transcripts first, then reserves only
cells that still need provider transport.  A canonical benchmark workflow can
therefore adopt the prepared reservations without duplicating calls.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Literal, cast

from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    FrozenAttemptPolicy,
    ProviderSpendKey,
)
from legalforecast.evals.provider_spend_dynamodb import (
    DYNAMODB_AUTHORITY_SCHEMA_VERSION,
    DynamoCommandRunner,
    DynamoDbProviderSpendAuthority,
)

AttributeMap = Mapping[str, Mapping[str, str]]
RecoveryDisposition = Literal[
    "completed",
    "replay_terminal",
    "settle_terminal",
    "reconcile_terminal",
    "adopt_pretransport",
    "reserve_replacement",
    "authorize_on_dispatch",
    "blocked",
]


class ProtectedRecoveryError(RuntimeError):
    """Raised when recovery cannot prove that another provider call is safe."""


@dataclass(frozen=True, slots=True)
class TerminalResponseEvidence:
    """Validated provider response accounting derived from a saved transcript."""

    transcript_sha256: str
    input_tokens: int
    output_tokens: int
    billed_microusd: int
    response_sha256: str


@dataclass(frozen=True, slots=True)
class RecoveryCell:
    """Frozen local evidence for one exact benchmark cell."""

    cell_id: str
    stage: str
    ablation: str
    repeat_index: int
    completed: bool = False
    local_attempt_id: str | None = None
    terminal_response: TerminalResponseEvidence | None = None
    evidence_error: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryRun:
    """Identity and authority boundary reconstructed from frozen run artifacts."""

    source_run_id: int
    source_run_attempt: int
    cycle_id: str
    model_key: str
    provider: str
    account: str
    run_identity_sha256: str
    ceiling_microusd: int
    table_name: str
    region: str
    resource_identity_sha256: str
    owner_reference: str

    @property
    def authority_identity_sha256(self) -> str:
        from legalforecast.contracts import (
            ARTIFACT_RAW_SHA256_V1,
            PUBLIC_RUN_IDENTITY_V1,
        )

        return str(
            ARTIFACT_RAW_SHA256_V1.commit(
                {
                    "account": self.account,
                    "provider": self.provider,
                    "run_identity_sha256": self.run_identity_sha256,
                },
                domain=PUBLIC_RUN_IDENTITY_V1,
            ).digest
        )

    @property
    def authority_key(self) -> str:
        account_sha256 = hashlib.sha256(self.account.encode()).hexdigest()
        return hashlib.sha256(
            (
                f"{self.authority_identity_sha256}\0{self.cycle_id}\0"
                f"{self.provider}\0{account_sha256}"
            ).encode()
        ).hexdigest()

    def spend_key(self, cell: RecoveryCell) -> ProviderSpendKey:
        return ProviderSpendKey(
            cycle_id=self.cycle_id,
            provider=self.provider,
            account=self.account,
            stage=cell.stage,
            model_key=self.model_key,
            case_id=cell.cell_id,
            ablation=cell.ablation,
            repeat_index=cell.repeat_index,
        )


@dataclass(frozen=True, slots=True)
class RecoveryOperation:
    """One cell's currently safe next transition."""

    cell_id: str
    logical_call_key: str
    disposition: RecoveryDisposition
    attempt_id: str | None = None
    attempt_ordinal: int | None = None
    reservation_microusd: int = 0
    failure_type: str | None = None
    reason: str | None = None
    failure_epoch: float | None = None


@dataclass(frozen=True, slots=True)
class ProtectedRecoveryPlan:
    """Read-only census and aggregate cap decision for one source run."""

    source_run_id: int
    source_run_attempt: int
    authority_identity_sha256: str
    authority_key: str
    cap_microusd: int
    committed_microusd: int
    projected_committed_microusd: int
    failure_threshold: int
    failure_window_seconds: int
    operations: tuple[RecoveryOperation, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def dispatch_safe(self) -> bool:
        return not self.blocked_reasons

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record.update(
            {
                "schema_version": "legalforecast.protected-recovery-plan.v1",
                "dispatch_safe": self.dispatch_safe,
            }
        )
        return record


def build_protected_recovery_plan(
    run: RecoveryRun,
    cells: Sequence[RecoveryCell],
    *,
    reservation_microusd: int,
    runner: DynamoCommandRunner,
) -> ProtectedRecoveryPlan:
    """Read exact authority state and classify every cell without mutation."""

    if not cells:
        raise ProtectedRecoveryError("recovery source has no benchmark cells")
    if reservation_microusd <= 0 or isinstance(reservation_microusd, bool):
        raise ProtectedRecoveryError("recovery reservation must be positive")
    if len({cell.cell_id for cell in cells}) != len(cells):
        raise ProtectedRecoveryError("recovery source contains duplicate cells")
    _verify_table(run, runner)
    ledger = _required_item(run, "LEDGER", runner)
    failure_threshold, failure_window = _verify_ledger(run, ledger)
    cap = _number(ledger, "cap_microusd")
    committed = _number(ledger, "committed_microusd")
    operations: list[RecoveryOperation] = []
    blocked: list[str] = []
    projected = committed
    fresh_cells = 0

    for cell in sorted(cells, key=lambda item: item.cell_id):
        key = run.spend_key(cell)
        if cell.completed:
            operations.append(
                RecoveryOperation(cell.cell_id, key.logical_call_key, "completed")
            )
            continue
        if cell.evidence_error is not None:
            reason = f"cell {cell.cell_id}: {cell.evidence_error}"
            blocked.append(reason)
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "blocked",
                    reason=reason,
                )
            )
            continue
        remote_cell = _optional_item(run, f"CELL#{key.logical_call_key}", runner)
        if remote_cell is None:
            fresh_cells += 1
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "authorize_on_dispatch",
                    reservation_microusd=reservation_microusd,
                )
            )
            continue
        ordinal = _number(remote_cell, "attempt_count")
        attempt = _required_item(
            run,
            f"ATTEMPT#{key.logical_call_key}#{ordinal:04d}",
            runner,
        )
        attempt_id = _text(attempt, "attempt_id")
        status = _text(attempt, "status")
        held = _number(attempt, "reservation_microusd")
        successor_of_local = (
            status == "reserved"
            and cell.terminal_response is None
            and "transport_started_at_epoch" not in attempt
            and cell.local_attempt_id is not None
            and _optional_text(attempt, "acknowledged_attempt_id")
            == cell.local_attempt_id
        )
        if (
            cell.local_attempt_id is not None
            and cell.local_attempt_id != attempt_id
            and not successor_of_local
        ):
            reason = f"cell {cell.cell_id}: local and latest remote attempts differ"
            blocked.append(reason)
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "blocked",
                    attempt_id,
                    ordinal,
                    held,
                    reason=reason,
                )
            )
            continue
        terminal = cell.terminal_response
        if terminal is not None and terminal.billed_microusd > held:
            reason = (
                f"cell {cell.cell_id}: terminal cost exceeds its frozen reservation"
            )
            blocked.append(reason)
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "blocked",
                    attempt_id,
                    ordinal,
                    held,
                    reason=reason,
                )
            )
            continue
        if terminal is not None and status == "reserved":
            projected += terminal.billed_microusd - held
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "settle_terminal",
                    attempt_id,
                    ordinal,
                    held,
                )
            )
        elif terminal is not None and status == "settled":
            reason = _settled_response_mismatch(attempt, terminal)
            if reason is not None:
                blocked.append(f"cell {cell.cell_id}: {reason}")
                operations.append(
                    RecoveryOperation(
                        cell.cell_id,
                        key.logical_call_key,
                        "blocked",
                        attempt_id,
                        ordinal,
                        held,
                        reason=reason,
                    )
                )
            else:
                operations.append(
                    RecoveryOperation(
                        cell.cell_id,
                        key.logical_call_key,
                        "replay_terminal",
                        attempt_id,
                        ordinal,
                        held,
                    )
                )
        elif terminal is not None and status == "ambiguous":
            projected += terminal.billed_microusd - held
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "reconcile_terminal",
                    attempt_id,
                    ordinal,
                    held,
                    _text(attempt, "failure_type"),
                    failure_epoch=_float_number(attempt, "completed_at_epoch"),
                )
            )
        elif status == "reserved" and "transport_started_at_epoch" not in attempt:
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "adopt_pretransport",
                    attempt_id,
                    ordinal,
                    held,
                )
            )
        elif status == "ambiguous":
            projected += min(reservation_microusd, held)
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "reserve_replacement",
                    attempt_id,
                    ordinal,
                    min(reservation_microusd, held),
                    _text(attempt, "failure_type"),
                    failure_epoch=_float_number(attempt, "completed_at_epoch"),
                )
            )
        else:
            reason = (
                f"cell {cell.cell_id}: remote attempt is {status} without "
                "replayable terminal evidence"
            )
            blocked.append(reason)
            operations.append(
                RecoveryOperation(
                    cell.cell_id,
                    key.logical_call_key,
                    "blocked",
                    attempt_id,
                    ordinal,
                    held,
                    reason=reason,
                )
            )

    if projected > cap:
        blocked.append(
            "recovery requires "
            f"{projected - committed} additional microusd but only "
            f"{cap - committed} remain under the frozen cap"
        )
    elif fresh_cells and projected + reservation_microusd > cap:
        blocked.append(
            "recovery leaves no room for one fresh provider reservation under "
            "the frozen cap"
        )
    return ProtectedRecoveryPlan(
        source_run_id=run.source_run_id,
        source_run_attempt=run.source_run_attempt,
        authority_identity_sha256=run.authority_identity_sha256,
        authority_key=run.authority_key,
        cap_microusd=cap,
        committed_microusd=committed,
        projected_committed_microusd=projected,
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window,
        operations=tuple(operations),
        blocked_reasons=tuple(blocked),
    )


def apply_protected_recovery(
    run: RecoveryRun,
    cells: Sequence[RecoveryCell],
    *,
    reservation_microusd: int,
    runner: DynamoCommandRunner,
) -> ProtectedRecoveryPlan:
    """Apply a safe current plan and return the idempotent post-apply plan."""

    plan = build_protected_recovery_plan(
        run, cells, reservation_microusd=reservation_microusd, runner=runner
    )
    if not plan.dispatch_safe:
        raise ProtectedRecoveryError("; ".join(plan.blocked_reasons))
    policy = FrozenAttemptPolicy(
        reservation_ledger_sha256=run.run_identity_sha256,
        max_billable_attempts=1,
        failure_threshold=plan.failure_threshold,
        failure_window_seconds=plan.failure_window_seconds,
    )
    authority = DynamoDbProviderSpendAuthority(
        table_name=run.table_name,
        authority_identity_sha256=run.authority_identity_sha256,
        resource_identity_sha256=run.resource_identity_sha256,
        cycle_id=run.cycle_id,
        provider=run.provider,
        account=run.account,
        cap_microusd=run.ceiling_microusd,
        policy=policy,
        region=run.region,
        runner=runner,
    )
    by_id = {cell.cell_id: cell for cell in cells}
    # Terminal evidence returns unused held budget before new reservations.
    for operation in plan.operations:
        if operation.disposition not in {"settle_terminal", "reconcile_terminal"}:
            continue
        cell = by_id[operation.cell_id]
        terminal = cell.terminal_response
        assert terminal is not None
        lease = _lease(run, operation)
        if operation.disposition == "settle_terminal":
            authority.record_response(
                lease,
                input_tokens=terminal.input_tokens,
                output_tokens=terminal.output_tokens,
                actual_microusd=terminal.billed_microusd,
                response_sha256=terminal.response_sha256,
            )
        else:
            authority.reconcile_ambiguous(
                lease,
                usage_record_id=(
                    f"benchmark-recovery:{run.source_run_id}:"
                    f"{run.source_run_attempt}:{cell.cell_id}"
                ),
                usage_record_sha256=terminal.transcript_sha256,
                billed_microusd=terminal.billed_microusd,
                input_tokens=terminal.input_tokens,
                output_tokens=terminal.output_tokens,
                response_sha256=terminal.response_sha256,
            )
    replacement_operations = [
        operation
        for operation in plan.operations
        if operation.disposition == "reserve_replacement"
    ]
    ledger = _required_item(run, "LEDGER", runner)
    retained_failure_epochs = _failure_events(ledger)
    # A full breaker window can acknowledge one of its retained events first.
    # An older evicted event cannot reduce that full window, so process it only
    # after a retained event has made room.
    replacement_operations.sort(
        key=lambda operation: (
            operation.failure_epoch not in retained_failure_epochs,
            -(operation.failure_epoch or 0.0),
        )
    )
    for operation in replacement_operations:
        cell = by_id[operation.cell_id]
        key = run.spend_key(cell)
        ledger = _required_item(run, "LEDGER", runner)
        assert operation.attempt_id is not None
        assert operation.attempt_ordinal is not None
        assert operation.failure_type is not None
        authority.authorize_additional_attempt(
            key,
            reservation_microusd=operation.reservation_microusd,
            acknowledged_attempt_id=operation.attempt_id,
            acknowledged_failure_type=operation.failure_type,
            acknowledged_failure_events_sha256=_text(ledger, "failure_events_sha256"),
            acknowledged_attempt_ordinal=operation.attempt_ordinal,
            owner_reference=run.owner_reference,
        )
    return build_protected_recovery_plan(
        run, cells, reservation_microusd=reservation_microusd, runner=runner
    )


def _lease(run: RecoveryRun, operation: RecoveryOperation) -> AttemptLease:
    if operation.attempt_id is None or operation.attempt_ordinal is None:
        raise ProtectedRecoveryError("recovery operation lacks an exact attempt")
    return AttemptLease(
        attempt_id=operation.attempt_id,
        authority_identity_sha256=run.authority_identity_sha256,
        logical_call_key=operation.logical_call_key,
        attempt_ordinal=operation.attempt_ordinal,
        reservation_microusd=operation.reservation_microusd,
    )


def _verify_table(run: RecoveryRun, runner: DynamoCommandRunner) -> None:
    response = runner("describe-table", {"TableName": run.table_name})
    table = response.get("Table")
    if not isinstance(table, Mapping):
        raise ProtectedRecoveryError("DynamoDB DescribeTable lacks Table")
    arn = cast(Mapping[str, object], table).get("TableArn")
    if not isinstance(arn, str) or hashlib.sha256(arn.encode()).hexdigest() != (
        run.resource_identity_sha256
    ):
        raise ProtectedRecoveryError("DynamoDB table differs from frozen authority")


def _verify_ledger(run: RecoveryRun, item: AttributeMap) -> tuple[int, int]:
    expected = {
        "schema_version": DYNAMODB_AUTHORITY_SCHEMA_VERSION,
        "authority_identity_sha256": run.authority_identity_sha256,
        "cycle_id": run.cycle_id,
        "provider": run.provider,
        "account_sha256": hashlib.sha256(run.account.encode()).hexdigest(),
        "reservation_ledger_sha256": run.run_identity_sha256,
    }
    for field, value in expected.items():
        if _text(item, field) != value:
            raise ProtectedRecoveryError(
                f"DynamoDB authority {field} differs from frozen run"
            )
    if _number(item, "authority_poisoned") != 0:
        raise ProtectedRecoveryError("DynamoDB authority is poisoned")
    if _number(item, "max_billable_attempts") != 1:
        raise ProtectedRecoveryError("DynamoDB attempt policy differs from recovery")
    cap = _number(item, "cap_microusd")
    if cap < run.ceiling_microusd:
        raise ProtectedRecoveryError("DynamoDB cap is below the frozen run ceiling")
    if cap > run.ceiling_microusd and not all(
        _optional_text(item, name)
        for name in ("cap_amendment_owner_reference", "cap_amendment_reference")
    ):
        raise ProtectedRecoveryError("DynamoDB cap increased without an amendment")
    return (
        _number(item, "failure_threshold"),
        _number(item, "failure_window_seconds"),
    )


def _required_item(
    run: RecoveryRun, record_key: str, runner: DynamoCommandRunner
) -> AttributeMap:
    item = _optional_item(run, record_key, runner)
    if item is None:
        raise ProtectedRecoveryError(f"DynamoDB record is missing: {record_key}")
    return item


def _optional_item(
    run: RecoveryRun, record_key: str, runner: DynamoCommandRunner
) -> AttributeMap | None:
    response = runner(
        "get-item",
        {
            "TableName": run.table_name,
            "Key": {
                "authority_key": {"S": run.authority_key},
                "record_key": {"S": record_key},
            },
            "ConsistentRead": True,
        },
    )
    raw = response.get("Item")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ProtectedRecoveryError("DynamoDB item is malformed")
    return cast(AttributeMap, raw)


def _text(item: AttributeMap, name: str) -> str:
    value = _optional_text(item, name)
    if value is None:
        raise ProtectedRecoveryError(f"DynamoDB field {name} is missing")
    return value


def _optional_text(item: AttributeMap, name: str) -> str | None:
    value = item.get(name)
    if not isinstance(value, Mapping):
        return None
    text = value.get("S")
    return text if isinstance(text, str) and text else None


def _number(item: AttributeMap, name: str) -> int:
    value = item.get(name)
    raw = value.get("N") if isinstance(value, Mapping) else None
    try:
        number = int(cast(str, raw))
    except (TypeError, ValueError) as exc:
        raise ProtectedRecoveryError(f"DynamoDB field {name} is invalid") from exc
    if number < 0:
        raise ProtectedRecoveryError(f"DynamoDB field {name} is negative")
    return number


def _float_number(item: AttributeMap, name: str) -> float:
    value = item.get(name)
    raw = value.get("N") if isinstance(value, Mapping) else None
    try:
        number = float(cast(str, raw))
    except (TypeError, ValueError) as exc:
        raise ProtectedRecoveryError(f"DynamoDB field {name} is invalid") from exc
    if not math.isfinite(number) or number < 0:
        raise ProtectedRecoveryError(f"DynamoDB field {name} is invalid")
    return number


def _failure_events(item: AttributeMap) -> frozenset[float]:
    try:
        value = json.loads(_text(item, "failure_events_json"))
    except json.JSONDecodeError as exc:
        raise ProtectedRecoveryError("DynamoDB failure events are invalid") from exc
    if not isinstance(value, list):
        raise ProtectedRecoveryError("DynamoDB failure events are invalid")
    epochs = cast(list[object], value)
    if any(
        isinstance(epoch, bool) or not isinstance(epoch, (int, float))
        for epoch in epochs
    ):
        raise ProtectedRecoveryError("DynamoDB failure events are invalid")
    return frozenset(float(cast(int | float, epoch)) for epoch in epochs)


def _settled_response_mismatch(
    attempt: AttributeMap,
    terminal: TerminalResponseEvidence,
) -> str | None:
    expected = {
        "input_tokens": terminal.input_tokens,
        "output_tokens": terminal.output_tokens,
        "actual_microusd": terminal.billed_microusd,
    }
    for name, value in expected.items():
        if _number(attempt, name) != value:
            return f"settled remote {name} differs from terminal transcript"
    if _text(attempt, "response_sha256") != terminal.response_sha256:
        return "settled remote response differs from terminal transcript"
    return None


def terminal_response_evidence(
    *,
    transcript_bytes: bytes,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    raw_output: str,
) -> TerminalResponseEvidence:
    """Convert already validated transcript output into exact spend evidence."""

    if input_tokens < 0 or output_tokens < 0:
        raise ProtectedRecoveryError("terminal transcript has negative usage")
    if not math.isfinite(estimated_cost_usd) or estimated_cost_usd < 0:
        raise ProtectedRecoveryError("terminal transcript has invalid cost")
    return TerminalResponseEvidence(
        transcript_sha256=hashlib.sha256(transcript_bytes).hexdigest(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        billed_microusd=math.ceil(estimated_cost_usd * 1_000_000),
        response_sha256=hashlib.sha256(raw_output.encode()).hexdigest(),
    )


def canonical_json(record: Mapping[str, object]) -> str:
    """Serialize a plan or receipt deterministically for workflow artifacts."""

    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"

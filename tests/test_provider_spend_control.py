from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

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
    SqliteProviderSpendAuthority,
)


def test_concurrent_workers_never_reserve_above_provider_account_cap(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path):
        pass
    start = threading.Barrier(12)
    callbacks: list[int] = []
    callback_lock = threading.Lock()

    def reserve(index: int) -> bool:
        start.wait()
        try:
            with _authority(path) as authority:
                authority.authorize_attempt(
                    _key(case_id=f"case-{index}"),
                    reservation_microusd=250_000,
                )
        except ProviderCapExceededError:
            return False
        with callback_lock:
            callbacks.append(index)
        return True

    with ThreadPoolExecutor(max_workers=12) as executor:
        accepted = list(executor.map(reserve, range(12)))

    assert sum(accepted) == 4
    assert len(callbacks) == 4
    with _authority(path) as authority:
        snapshot = authority.snapshot()
    assert snapshot.committed_microusd == 1_000_000
    assert snapshot.reserved_attempt_count == 4


def test_labeling_and_eval_draw_on_the_same_provider_account_cap(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        authority.authorize_attempt(
            _key(stage="llm-label", case_id="label-1"),
            reservation_microusd=600_000,
        )

    with _authority(path) as authority:
        with pytest.raises(ProviderCapExceededError):
            authority.authorize_attempt(
                _key(stage="official-eval", case_id="eval-1"),
                reservation_microusd=500_000,
            )


def test_ambiguous_attempt_retains_reservation_until_usage_reconciliation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        lease = authority.authorize_attempt(
            _key(),
            reservation_microusd=700_000,
        )
        authority.record_failure(lease, failure_type="TimeoutError", ambiguous=True)

    with _authority(path) as authority:
        with pytest.raises(ProviderCapExceededError):
            authority.authorize_attempt(
                _key(case_id="other-case"),
                reservation_microusd=400_000,
            )
        authority.reconcile_ambiguous(
            lease,
            usage_record_id="usage-2026-07-16-1",
            usage_record_sha256="a" * 64,
            billed_microusd=None,
        )
        replacement = authority.authorize_attempt(
            _key(case_id="other-case"),
            reservation_microusd=400_000,
        )

    assert replacement.attempt_ordinal == 1


def test_ambiguous_reconciliation_is_idempotent_and_rejects_changed_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        lease = authority.authorize_attempt(_key(), reservation_microusd=500_000)
        authority.record_failure(lease, failure_type="TimeoutError", ambiguous=True)
        authority.reconcile_ambiguous(
            lease,
            usage_record_id="usage-1",
            usage_record_sha256="b" * 64,
            billed_microusd=125_000,
        )
        authority.reconcile_ambiguous(
            lease,
            usage_record_id="usage-1",
            usage_record_sha256="b" * 64,
            billed_microusd=125_000,
        )
        with pytest.raises(ReconciliationMismatchError):
            authority.reconcile_ambiguous(
                lease,
                usage_record_id="usage-2",
                usage_record_sha256="c" * 64,
                billed_microusd=None,
            )
        snapshot = authority.snapshot()

    assert snapshot.committed_microusd == 125_000
    assert snapshot.settled_attempt_count == 1


def test_usage_record_is_single_use_and_same_attempt_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        first = authority.authorize_attempt(
            _key(case_id="first"), reservation_microusd=400_000
        )
        second = authority.authorize_attempt(
            _key(case_id="second"), reservation_microusd=400_000
        )
        authority.record_failure(first, failure_type="TimeoutError", ambiguous=True)
        authority.record_failure(second, failure_type="TimeoutError", ambiguous=True)

        evidence = {
            "usage_record_id": "provider-usage-record-1",
            "usage_record_sha256": "7" * 64,
            "billed_microusd": None,
        }
        authority.reconcile_ambiguous(first, **evidence)
        authority.reconcile_ambiguous(first, **evidence)

        with pytest.raises(ReconciliationMismatchError):
            authority.reconcile_ambiguous(second, **evidence)

        snapshot = authority.snapshot()

    assert snapshot.committed_microusd == 400_000
    assert snapshot.ambiguous_attempt_count == 1
    assert snapshot.reserved_attempt_count == 0


def test_max_attempts_survives_reopen_and_counts_definite_provider_calls(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    for index in range(2):
        with _authority(path, max_billable_attempts=2) as authority:
            lease = authority.authorize_attempt(
                _key(),
                reservation_microusd=100_000,
            )
            authority.record_failure(
                lease,
                failure_type=f"HTTP{400 + index}",
                ambiguous=False,
            )

    with _authority(path, max_billable_attempts=2) as authority:
        with pytest.raises(AttemptLimitExceededError):
            authority.authorize_attempt(_key(), reservation_microusd=100_000)
        assert authority.snapshot().attempt_count == 2


def test_windowed_breaker_refuses_then_reopens_with_injected_clock(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    now = [1_000.0]
    for index in range(2):
        with _authority(path, failure_threshold=2, clock=lambda: now[0]) as authority:
            lease = authority.authorize_attempt(
                _key(case_id=f"failed-{index}"),
                reservation_microusd=100_000,
            )
            authority.record_failure(
                lease,
                failure_type="TimeoutError",
                ambiguous=True,
            )

    now[0] = 1_299.0
    with _authority(path, failure_threshold=2, clock=lambda: now[0]) as authority:
        with pytest.raises(CircuitBreakerOpenError):
            authority.authorize_attempt(
                _key(case_id="blocked"), reservation_microusd=100_000
            )

    now[0] = 1_301.0
    with _authority(path, failure_threshold=2, clock=lambda: now[0]) as authority:
        lease = authority.authorize_attempt(
            _key(case_id="after-window"), reservation_microusd=100_000
        )
    assert lease.attempt_ordinal == 1


def test_breaker_uses_true_trailing_window_across_prior_window_boundary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    now = [100.0]

    def fail(case_id: str, failed_at: float) -> None:
        now[0] = failed_at
        with _authority(
            path,
            failure_threshold=3,
            clock=lambda: now[0],
        ) as authority:
            lease = authority.authorize_attempt(
                _key(case_id=case_id), reservation_microusd=100_000
            )
            authority.record_failure(
                lease,
                failure_type="TimeoutError",
                ambiguous=False,
            )

    # A tumbling window anchored at t=100 would discard the still-live t=200
    # event when t=401 arrives. A trailing window must retain t=200, t=401,
    # and t=402 and therefore refuse the next call at t=403.
    fail("old-expired", 100.0)
    fail("still-live", 200.0)
    fail("after-boundary-1", 401.0)
    fail("after-boundary-2", 402.0)

    now[0] = 403.0
    with _authority(
        path,
        failure_threshold=3,
        clock=lambda: now[0],
    ) as authority:
        snapshot = authority.snapshot()
        with pytest.raises(CircuitBreakerOpenError):
            authority.authorize_attempt(
                _key(case_id="must-be-blocked"), reservation_microusd=1
            )

    assert snapshot.failure_count_in_window == 3
    assert snapshot.breaker_open is True


def test_breaker_scope_is_shared_by_stage_but_isolated_by_account(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path, failure_threshold=1) as authority:
        lease = authority.authorize_attempt(
            _key(stage="llm-label"), reservation_microusd=100_000
        )
        authority.record_failure(lease, failure_type="TimeoutError", ambiguous=True)

    with _authority(path, failure_threshold=1) as authority:
        with pytest.raises(CircuitBreakerOpenError):
            authority.authorize_attempt(
                _key(stage="official-eval", case_id="eval"),
                reservation_microusd=100_000,
            )

    other_path = tmp_path / "other-account.sqlite3"
    with _authority(other_path, account="secondary", failure_threshold=1) as authority:
        lease = authority.authorize_attempt(
            _key(account="secondary"), reservation_microusd=100_000
        )
    assert lease.attempt_ordinal == 1


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens", "actual_microusd"),
    ((-1, 1, 10), (1, -1, 10), (1, 1, -1), (1, 1, 500_001)),
)
def test_settlement_rejects_invalid_or_above_reservation_usage(
    tmp_path: Path,
    input_tokens: int,
    output_tokens: int,
    actual_microusd: int,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        lease = authority.authorize_attempt(_key(), reservation_microusd=500_000)
        with pytest.raises(SettlementError):
            authority.record_response(
                lease,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                actual_microusd=actual_microusd,
                response_sha256="d" * 64,
            )
        assert authority.snapshot().committed_microusd == 500_000


def test_actual_cost_above_reservation_poison_refuses_new_authorizations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        lease = authority.authorize_attempt(_key(), reservation_microusd=500_000)
        with pytest.raises(SettlementError, match="exceeds"):
            authority.record_response(
                lease,
                input_tokens=1,
                output_tokens=1,
                actual_microusd=500_001,
                response_sha256="d" * 64,
            )

        with pytest.raises(AuthorityPoisonedError):
            authority.authorize_attempt(
                _key(case_id="after-under-reservation"),
                reservation_microusd=1,
            )

        snapshot = authority.snapshot()

    assert snapshot.committed_microusd == 500_000
    assert snapshot.reserved_attempt_count == 1
    assert snapshot.authority_poisoned is True


def test_sqlite_rejects_mutated_or_cross_authority_leases(tmp_path: Path) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
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


def test_sqlite_adopts_reserved_attempt_after_crash_and_settles_idempotently(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    key = _key()
    with _authority(path) as authority:
        original = authority.authorize_attempt(key, reservation_microusd=500_000)

    with _authority(path) as recovered:
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
                response_sha256="2" * 64,
            )
        snapshot = recovered.snapshot()

    assert snapshot.committed_microusd == 125_000
    assert snapshot.reserved_attempt_count == 0
    assert snapshot.settled_attempt_count == 1


def test_authority_reopen_rejects_cap_policy_or_resource_identity_drift(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path):
        pass

    with pytest.raises(AuthorityIdentityMismatchError):
        _authority(path, cap_microusd=2_000_000)
    with pytest.raises(AuthorityIdentityMismatchError):
        _authority(path, failure_threshold=4)
    with pytest.raises(AuthorityIdentityMismatchError):
        _authority(path, authority_identity_sha256="e" * 64)


def test_attempt_identity_distinguishes_ablation_repeat_and_account() -> None:
    baseline = _key()
    variants = (
        _key(ablation="no_history"),
        _key(repeat_index=2),
        _key(account="secondary"),
    )
    assert (
        len({baseline.logical_call_key, *(item.logical_call_key for item in variants)})
        == 4
    )


def test_sqlite_schema_records_integer_money_only(tmp_path: Path) -> None:
    path = tmp_path / "spend-control.sqlite3"
    with _authority(path) as authority:
        authority.authorize_attempt(_key(), reservation_microusd=333_333)

    with sqlite3.connect(path) as connection:
        [(declared_type,)] = connection.execute(
            "SELECT type FROM pragma_table_info('provider_attempts') "
            "WHERE name = 'reservation_microusd'"
        ).fetchall()
    assert declared_type == "INTEGER"


def test_methods_states_spend_control_boundary_and_gateway_upgrade() -> None:
    methods = (Path(__file__).parents[1] / "docs/METHODS.md").read_text(
        encoding="utf-8"
    )

    assert "accidental-overspend control" in methods
    assert "not a privilege-enforced spending boundary" in methods
    assert "separately administered capped gateway or proxy" in methods


def _policy(
    *,
    max_billable_attempts: int = 3,
    failure_threshold: int = 3,
) -> FrozenAttemptPolicy:
    return FrozenAttemptPolicy(
        reservation_ledger_sha256="f" * 64,
        max_billable_attempts=max_billable_attempts,
        failure_threshold=failure_threshold,
        failure_window_seconds=300,
    )


def _authority(
    path: Path,
    *,
    cap_microusd: int = 1_000_000,
    account: str = "primary",
    max_billable_attempts: int = 3,
    failure_threshold: int = 3,
    authority_identity_sha256: str = "9" * 64,
    clock: Callable[[], float] | None = None,
) -> SqliteProviderSpendAuthority:
    return SqliteProviderSpendAuthority(
        path,
        authority_identity_sha256=authority_identity_sha256,
        cycle_id="cycle-1",
        provider="openai",
        account=account,
        cap_microusd=cap_microusd,
        policy=_policy(
            max_billable_attempts=max_billable_attempts,
            failure_threshold=failure_threshold,
        ),
        clock=clock,
    )


def _key(
    *,
    account: str = "primary",
    stage: str = "official-eval",
    case_id: str = "case-1",
    ablation: str = "full_packet",
    repeat_index: int = 1,
) -> ProviderSpendKey:
    return ProviderSpendKey(
        cycle_id="cycle-1",
        provider="openai",
        account=account,
        stage=stage,
        model_key="openai:gpt-test",
        case_id=case_id,
        ablation=ablation,
        repeat_index=repeat_index,
    )

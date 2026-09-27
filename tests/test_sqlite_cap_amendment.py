from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legalforecast.evals.provider_spend_control import (
    AuthorityIdentityMismatchError,
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)


def _authority(
    path: Path,
    *,
    cap: int = 1_000,
    old_cap: int | None = None,
    account: str = "primary",
    failure_threshold: int = 3,
) -> SqliteProviderSpendAuthority:
    return SqliteProviderSpendAuthority(
        path,
        authority_identity_sha256="a" * 64,
        cycle_id="cycle-1",
        provider="openai",
        account=account,
        cap_microusd=cap,
        amend_cap_from_microusd=old_cap,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256="b" * 64,
            max_billable_attempts=1,
            failure_threshold=failure_threshold,
            failure_window_seconds=300,
        ),
    )


def _key(case_id: str) -> ProviderSpendKey:
    return ProviderSpendKey(
        cycle_id="cycle-1",
        provider="openai",
        account="primary",
        stage="summary",
        model_key="openai:test",
        case_id=case_id,
        ablation="full_packet",
        repeat_index=1,
    )


def _dump(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return list(connection.iterdump())


def test_cap_change_requires_explicit_amendment(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with _authority(path):
        pass
    before = _dump(path)
    with pytest.raises(AuthorityIdentityMismatchError):
        _authority(path, cap=2_000)
    assert _dump(path) == before


def test_amendment_preserves_charges_failures_and_poison(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with _authority(path) as authority:
        settled = authority.authorize_attempt(_key("settled"), reservation_microusd=400)
        authority.record_response(
            settled,
            input_tokens=10,
            output_tokens=5,
            actual_microusd=200,
            response_sha256="c" * 64,
        )
        ambiguous = authority.authorize_attempt(
            _key("ambiguous"), reservation_microusd=500
        )
        authority.record_failure(ambiguous, failure_type="ReadError", ambiguous=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_spend_metadata "
            "SET authority_poisoned = 1, poison_reason = 'test'"
        )
    before = _dump(path)
    with _authority(path, cap=2_000, old_cap=1_000) as authority:
        snapshot = authority.snapshot()
        assert snapshot.committed_microusd == 700
        assert snapshot.settled_attempt_count == 1
        assert snapshot.authority_poisoned
        assert snapshot.failure_count_in_window == 1
    after = _dump(path)
    assert len(before) == len(after)
    changes = [
        (left, right)
        for left, right in zip(before, after, strict=True)
        if left != right
    ]
    assert len(changes) == 1
    assert changes[0][0].replace(",1000,", ",2000,") == changes[0][1]
    with _authority(path, cap=2_000, old_cap=1_000):
        pass
    assert _dump(path) == after


@pytest.mark.parametrize(
    ("cap", "old_cap", "account", "failure_threshold", "error"),
    [
        (2_000, 999, "primary", 3, AuthorityIdentityMismatchError),
        (2_000, 1_000, "different", 3, AuthorityIdentityMismatchError),
        (2_000, 1_000, "primary", 4, AuthorityIdentityMismatchError),
        (500, 1_000, "primary", 3, ValueError),
        (1_000, 1_000, "primary", 3, ValueError),
        (2_000, 0, "primary", 3, ValueError),
    ],
)
def test_invalid_amendment_leaves_ledger_unchanged(
    tmp_path: Path,
    cap: int,
    old_cap: int,
    account: str,
    failure_threshold: int,
    error: type[Exception],
) -> None:
    path = tmp_path / "ledger.sqlite3"
    with _authority(path):
        pass
    before = _dump(path)
    with pytest.raises(error):
        _authority(
            path,
            cap=cap,
            old_cap=old_cap,
            account=account,
            failure_threshold=failure_threshold,
        )
    assert _dump(path) == before


def test_amendment_cannot_create_ledger(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(AuthorityIdentityMismatchError, match="existing ledger"):
        _authority(path, cap=2_000, old_cap=1_000)
    assert not path.exists()

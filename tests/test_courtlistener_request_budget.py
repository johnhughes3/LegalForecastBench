from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudget,
    CourtListenerRequestBudgetError,
    CourtListenerRequestBudgetExhausted,
    CourtListenerRequestLimits,
)


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_minute_window_waits_before_durable_reservation(tmp_path: Path) -> None:
    clock = FakeClock()
    budget = CourtListenerRequestBudget(
        tmp_path / "requests.sqlite3",
        limits=CourtListenerRequestLimits(per_minute=2, per_hour=10, per_day=20),
        max_wait_seconds=61,
        clock=clock,
        sleep=clock.sleep,
    )

    budget.reserve("GET", "/search/")
    budget.reserve("GET", "/search/")
    third = budget.reserve("GET", "/search/")

    assert clock.sleeps == [pytest.approx(60.001)]
    assert third.reserved_at == pytest.approx(1_000_060.001)
    assert budget.total_reservations() == 3


def test_day_window_fails_closed_instead_of_waiting_all_day(tmp_path: Path) -> None:
    clock = FakeClock()
    budget = CourtListenerRequestBudget(
        tmp_path / "requests.sqlite3",
        limits=CourtListenerRequestLimits(per_minute=1, per_hour=1, per_day=1),
        max_wait_seconds=120,
        clock=clock,
        sleep=clock.sleep,
    )
    budget.reserve("GET", "/dockets/1/")

    with pytest.raises(CourtListenerRequestBudgetExhausted, match="rolling day"):
        budget.reserve("GET", "/dockets/2/")

    assert clock.sleeps == []
    assert budget.total_reservations() == 1


def test_reservation_survives_process_reopen(tmp_path: Path) -> None:
    path = tmp_path / "requests.sqlite3"
    limits = CourtListenerRequestLimits(per_minute=2, per_hour=3, per_day=4)
    first = CourtListenerRequestBudget(path, limits=limits)
    first.reserve("GET", "/search/")

    reopened = CourtListenerRequestBudget(path, limits=limits)

    assert reopened.total_reservations() == 1


def test_reopen_rejects_changed_limits(tmp_path: Path) -> None:
    path = tmp_path / "requests.sqlite3"
    CourtListenerRequestBudget(
        path,
        limits=CourtListenerRequestLimits(per_minute=2, per_hour=3, per_day=4),
    )

    with pytest.raises(CourtListenerRequestBudgetError, match="configuration mismatch"):
        CourtListenerRequestBudget(
            path,
            limits=CourtListenerRequestLimits(per_minute=2, per_hour=4, per_day=5),
        )


def test_invalid_request_is_not_reserved(tmp_path: Path) -> None:
    budget = CourtListenerRequestBudget(tmp_path / "requests.sqlite3")

    with pytest.raises(ValueError, match="absolute API endpoint"):
        budget.reserve("GET", "https://evil.example/")

    assert budget.total_reservations() == 0


def test_concurrent_process_analogues_cannot_overreserve(tmp_path: Path) -> None:
    path = tmp_path / "requests.sqlite3"
    limits = CourtListenerRequestLimits(per_minute=1, per_hour=1, per_day=1)
    first = CourtListenerRequestBudget(path, limits=limits, max_wait_seconds=0)
    second = CourtListenerRequestBudget(path, limits=limits, max_wait_seconds=0)

    def attempt(budget: CourtListenerRequestBudget) -> str:
        try:
            budget.reserve("GET", "/search/")
        except CourtListenerRequestBudgetExhausted:
            return "exhausted"
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(attempt, (first, second)))

    assert outcomes == ["exhausted", "reserved"]
    assert first.total_reservations() == 1


def test_reservation_timestamp_is_sampled_after_writer_lock(tmp_path: Path) -> None:
    path = tmp_path / "requests.sqlite3"
    budget = CourtListenerRequestBudget(path)
    blocker = sqlite3.connect(path)
    blocker.execute("BEGIN IMMEDIATE")
    started = time.time()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(budget.reserve, "GET", "/search/")
        time.sleep(0.1)
        blocker.commit()
        reservation = pending.result(timeout=2)

    blocker.close()
    assert reservation.reserved_at - started >= 0.08


def test_lock_acquisition_counts_against_monotonic_deadline(tmp_path: Path) -> None:
    monotonic_values = iter((0.0, 0.0, 2.0))
    budget = CourtListenerRequestBudget(
        tmp_path / "requests.sqlite3",
        max_wait_seconds=1.0,
        monotonic_clock=lambda: next(monotonic_values),
    )

    with pytest.raises(CourtListenerRequestBudgetExhausted, match="ledger lock"):
        budget.reserve("GET", "/search/")

    assert budget.total_reservations() == 0


def test_local_reservation_count_excludes_other_budget_instances(
    tmp_path: Path,
) -> None:
    path = tmp_path / "requests.sqlite3"
    first = CourtListenerRequestBudget(path)
    second = CourtListenerRequestBudget(path)

    first.before_request("GET", "/search/")
    second.before_request("GET", "/dockets/1/")

    assert first.local_reservations == 1
    assert second.local_reservations == 1
    assert first.total_reservations() == 2


def test_transient_writer_lock_retries_then_reserves_before_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    budget = CourtListenerRequestBudget(
        tmp_path / "requests.sqlite3",
        max_wait_seconds=1.0,
        clock=clock,
        monotonic_clock=clock,
        sleep=clock.sleep,
    )
    real_connect = budget._connect
    attempts = 0

    def flaky_connect(*, timeout_seconds: float = 30.0) -> sqlite3.Connection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(timeout_seconds=timeout_seconds)

    monkeypatch.setattr(budget, "_connect", flaky_connect)

    reservation = budget.reserve("GET", "/search/")

    assert reservation.reserved_at == pytest.approx(1_000_000.05)
    assert attempts == 2
    assert clock.sleeps == [pytest.approx(0.05)]
    assert budget.total_reservations() == 1


def test_persistent_writer_lock_exhausts_the_single_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    budget = CourtListenerRequestBudget(
        tmp_path / "requests.sqlite3",
        max_wait_seconds=0.11,
        monotonic_clock=clock,
        sleep=clock.sleep,
    )

    def locked_connect(*, timeout_seconds: float = 30.0) -> sqlite3.Connection:
        del timeout_seconds
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(budget, "_connect", locked_connect)

    with pytest.raises(CourtListenerRequestBudgetExhausted, match="ledger lock"):
        budget.reserve("GET", "/search/")

    assert sum(clock.sleeps) == pytest.approx(0.11)
    assert max(clock.sleeps) <= 0.05

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

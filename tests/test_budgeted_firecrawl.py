from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import Event, Lock, get_ident

import pytest
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlCircuitOpenError,
    FirecrawlTargetSpec,
    load_successful_firecrawl_pages,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    FirecrawlBudgetExceededError,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlAuthError,
    FirecrawlChallengeError,
    FirecrawlPaymentRequiredError,
    FirecrawlRateLimitError,
    FirecrawlResponseError,
    FirecrawlScrapeResult,
    FirecrawlServerError,
    FirecrawlTargetHTTPError,
)


class FixtureSource:
    def __init__(
        self,
        responses: Mapping[
            str,
            list[FirecrawlScrapeResult | BaseException],
        ],
        *,
        before_scrape: Callable[[str], None] | None = None,
    ) -> None:
        self.responses = {
            url: deque(url_responses) for url, url_responses in responses.items()
        }
        self.before_scrape = before_scrape
        self.calls: list[str] = []

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls.append(source_url)
        if self.before_scrape is not None:
            self.before_scrape(source_url)
        response = self.responses[source_url].popleft()
        if isinstance(response, BaseException):
            raise response
        return response


class _ConcurrentSource:
    def __init__(
        self, targets: list[FirecrawlTargetSpec], *, release_after: int
    ) -> None:
        self._results = {
            target.source_url: _success(target, f"<html>{target.target_id}</html>")
            for target in targets
        }
        self._release_after = release_after
        self._started = 0
        self._active = 0
        self.peak_active = 0
        self._lock = Lock()
        self._release = Event()

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        with self._lock:
            self._started += 1
            self._active += 1
            self.peak_active = max(self.peak_active, self._active)
            if self._started >= self._release_after:
                self._release.set()
        assert self._release.wait(timeout=5)
        try:
            return self._results[source_url]
        finally:
            with self._lock:
                self._active -= 1


def _store(tmp_path: Path, *, credit_cap: int = 45_000) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
    store.ensure_batch("batch-001", {"terms": ["motion to dismiss"]})
    store.ensure_firecrawl_run(
        "run-001",
        batch_id="batch-001",
        config={"proxy": "auto", "max_attempts": 3},
        credit_cap=credit_cap,
        reserved_credits_per_attempt=5,
    )
    return store


def _target(name: str, ordinal: int) -> FirecrawlTargetSpec:
    return FirecrawlTargetSpec(
        target_id=name,
        target_kind="search" if name.startswith("search") else "docket",
        source_url=f"https://www.courtlistener.com/{name}",
        page_number=1,
        ordinal=ordinal,
    )


def _success(target: FirecrawlTargetSpec, html: str) -> FirecrawlScrapeResult:
    return FirecrawlScrapeResult(
        source_url=target.source_url,
        docket_id=target.target_id,
        raw_html=html,
        target_status_code=200,
        proxy_requested="auto",
        proxy_used="stealth",
        cache_state="miss",
        credits_used=5.0,
        raw={"success": True},
        resolved_url=target.source_url,
    )


def test_scheduler_authorizes_before_network_and_materializes_success(
    tmp_path: Path,
) -> None:
    target = _target("docket-a", 0)
    with _store(tmp_path) as store:
        network_thread_ids: list[int] = []

        def record_network_thread(_url: str) -> None:
            network_thread_ids.append(get_ident())

        source = FixtureSource(
            {target.source_url: [_success(target, "<html>A</html>")]},
            before_scrape=record_network_thread,
        )
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([target])

        assert source.calls == [target.source_url]
        assert network_thread_ids != [get_ident()]
        assert len(result.pages) == 1
        page = result.pages[0]
        assert page.raw_html == "<html>A</html>"
        assert page.artifact_path.read_text() == page.raw_html
        assert (
            page.artifact_sha256 == hashlib.sha256(page.raw_html.encode()).hexdigest()
        )
        attempt = store.firecrawl_attempts("run-001")[0]
        assert attempt.status == "succeeded"
        assert attempt.reported_credits == 5
        assert attempt.proxy_used == "stealth"
        assert attempt.target_http_status == 200
        assert result.summary["reserved_credits"] == 5
        assert result.summary["reported_credits"] == 5


def test_invalid_artifact_is_terminal_before_commit(tmp_path: Path) -> None:
    target = _target("search-semantic", 0)
    invalid = _success(target, "<html>invalid</html>")

    def validate(raw_html: str, source_url: str) -> None:
        assert source_url == target.source_url
        if "invalid" in raw_html:
            raise ValueError("invalid fixture markup")

    with _store(tmp_path) as store:
        source = FixtureSource({target.source_url: [invalid]})
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            artifact_validator=validate,
            semantic_failure_quarantine_dir=tmp_path / "quarantine",
        ).run([target])

        assert source.calls == [target.source_url]
        assert result.pages == ()
        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.status for attempt in attempts] == ["target_error"]
        assert attempts[0].failure_code == "invalid_target_artifact"
        assert attempts[0].artifact_path is None
        quarantined = tuple((tmp_path / "quarantine").glob("*.semantic-invalid.html"))
        assert len(quarantined) == 1
        assert quarantined[0].read_text() == "<html>invalid</html>"
        assert hashlib.sha256(quarantined[0].read_bytes()).hexdigest() in (
            quarantined[0].name
        )
        assert result.summary["run_reserved_credits"] == 5
        assert result.summary["run_reported_credits"] == 5


def test_scheduler_bounds_live_network_concurrency_and_commits_in_rank_order(
    tmp_path: Path,
) -> None:
    targets = [_target(f"docket-{index:02d}", index) for index in range(12)]
    source = _ConcurrentSource(targets, release_after=10)
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=10,
        ).run(tuple(reversed(targets)))

        assert source.peak_active == 10
        assert [page.target_id for page in result.pages] == [
            target.target_id for target in targets
        ]
        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.target_id for attempt in attempts] == [
            target.target_id for target in targets
        ]
        assert all(attempt.status == "succeeded" for attempt in attempts)


def test_scheduler_rejects_more_than_ten_workers(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        with pytest.raises(ValueError, match="must not exceed 10"):
            BudgetedFirecrawlScheduler(
                store=store,
                source=FixtureSource({}),
                run_id="run-001",
                artifact_dir=tmp_path / "raw",
                max_workers=11,
            )


def test_scheduler_drains_and_finalizes_in_flight_work_before_global_failure(
    tmp_path: Path,
) -> None:
    first = _target("docket-a", 0)
    second = _target("docket-b", 1)
    second_completed = Event()

    class FatalThenSuccessSource:
        def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
            if source_url == first.source_url:
                assert second_completed.wait(timeout=5)
                raise FirecrawlAuthError("HTTP 401")
            second_completed.set()
            return _success(second, "second")

    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=FatalThenSuccessSource(),
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=2,
        )

        with pytest.raises(FirecrawlAuthError):
            scheduler.run([first, second])

        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.status for attempt in attempts] == [
            "provider_error",
            "succeeded",
        ]
        assert len(list((tmp_path / "raw").glob("*.html"))) == 1


def test_scheduler_drains_unexpected_worker_exception_before_reraising(
    tmp_path: Path,
) -> None:
    first = _target("docket-a", 0)
    second = _target("docket-b", 1)
    second_completed = Event()

    class UnexpectedThenSuccessSource:
        def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
            if source_url == first.source_url:
                assert second_completed.wait(timeout=5)
                raise RuntimeError("unexpected worker failure")
            second_completed.set()
            return _success(second, "second")

    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=UnexpectedThenSuccessSource(),
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=2,
        )

        with pytest.raises(RuntimeError, match="unexpected worker failure"):
            scheduler.run([first, second])

        assert [attempt.status for attempt in store.firecrawl_attempts("run-001")] == [
            "interrupted",
            "succeeded",
        ]
        assert len(list((tmp_path / "raw").glob("*.html"))) == 1


def test_concurrent_circuit_open_remains_durable_after_in_flight_success(
    tmp_path: Path,
) -> None:
    targets = [_target(f"docket-{index}", index) for index in range(6)]
    source = FixtureSource(
        {
            **{
                target.source_url: [FirecrawlServerError("HTTP 500")]
                for target in targets[:5]
            },
            targets[5].source_url: [_success(targets[5], "in flight success")],
        }
    )
    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=6,
        )
        with pytest.raises(FirecrawlCircuitOpenError, match="5 consecutive"):
            scheduler.run(targets)

        assert store.firecrawl_run_status("run-001") == "circuit_open"
        assert [attempt.status for attempt in store.firecrawl_attempts("run-001")] == [
            "provider_error",
            "provider_error",
            "provider_error",
            "provider_error",
            "provider_error",
            "succeeded",
        ]

        resumed_source = FixtureSource({})
        with pytest.raises(FirecrawlCircuitOpenError, match="durably open"):
            BudgetedFirecrawlScheduler(
                store=store,
                source=resumed_source,
                run_id="run-001",
                artifact_dir=tmp_path / "raw",
                max_workers=6,
            ).run(targets)
        assert resumed_source.calls == []


def test_scheduler_is_widest_first_and_isolates_provider_5xx(tmp_path: Path) -> None:
    first = _target("docket-a", 0)
    second = _target("docket-b", 1)
    source = FixtureSource(
        {
            first.source_url: [
                FirecrawlServerError("Firecrawl server failure (HTTP 500)"),
                _success(first, "first"),
            ],
            second.source_url: [
                FirecrawlServerError("Firecrawl server failure (HTTP 503)"),
                _success(second, "second"),
            ],
        }
    )
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([second, first])

        assert source.calls == [
            first.source_url,
            second.source_url,
            first.source_url,
            second.source_url,
        ]
        assert [page.target_id for page in result.pages] == ["docket-a", "docket-b"]
        assert result.summary["attempt_status_counts"] == {
            "provider_error": 2,
            "succeeded": 2,
        }
        failed_attempts = [
            attempt
            for attempt in store.firecrawl_attempts("run-001")
            if attempt.status == "provider_error"
        ]
        assert all(
            attempt.failure_code == "provider_server_error"
            for attempt in failed_attempts
        )
        assert all(attempt.failure_transient is True for attempt in failed_attempts)


def test_scheduler_retries_provider_http_timeout_within_attempt_cap(
    tmp_path: Path,
) -> None:
    target = _target("search-timeout", 0)
    source = FixtureSource(
        {
            target.source_url: [
                FirecrawlServerError(
                    "Firecrawl request timed out (HTTP 408)",
                    provider_http_status=408,
                ),
                _success(target, "recovered"),
            ]
        }
    )
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([target])

        assert [page.target_id for page in result.pages] == [target.target_id]
        assert source.calls == [target.source_url, target.source_url]
        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.status for attempt in attempts] == [
            "transport_error",
            "succeeded",
        ]
        assert attempts[0].provider_http_status == 408
        assert attempts[0].failure_transient is True


def test_scheduler_does_not_retry_deterministic_response_errors_and_persists_evidence(
    tmp_path: Path,
) -> None:
    target = _target("docket-a", 0)
    response_hash = "a" * 64
    source = FixtureSource(
        {
            target.source_url: [
                FirecrawlResponseError(
                    "resolved CourtListener URL did not match the authorized target",
                    failure_code="resolved_url_mismatch",
                    provider_http_status=200,
                    response_sha256=response_hash,
                ),
                _success(target, "must not run"),
            ]
        }
    )
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([target])

        assert result.pages == ()
        assert source.calls == [target.source_url]
        [attempt] = store.firecrawl_attempts("run-001")
        assert attempt.status == "target_error"
        assert attempt.failure_code == "resolved_url_mismatch"
        assert attempt.failure_message == (
            "resolved CourtListener URL did not match the authorized target"
        )
        assert attempt.failure_transient is False
        assert attempt.failure_response_sha256 == response_hash
        assert attempt.provider_http_status == 200
        assert store.firecrawl_targets("run-001")[0].status == "terminal_error"


def test_scheduler_stops_pool_on_confirmed_challenge_and_persists_evidence(
    tmp_path: Path,
) -> None:
    first = _target("search-a", 0)
    second = _target("docket-b", 1)
    response_hash = "c" * 64
    source = FixtureSource(
        {
            first.source_url: [
                FirecrawlChallengeError(
                    "CourtListener returned marker-confirmed challenge HTML",
                    provider_http_status=200,
                    response_sha256=response_hash,
                )
            ],
            second.source_url: [_success(second, "must not run")],
        }
    )
    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )

        with pytest.raises(FirecrawlChallengeError):
            scheduler.run([first, second])

        assert source.calls == [first.source_url]
        [attempt] = store.firecrawl_attempts("run-001")
        assert attempt.status == "provider_error"
        assert attempt.failure_code == "courtlistener_challenge_html"
        assert attempt.failure_response_sha256 == response_hash
        assert attempt.failure_message == (
            "CourtListener returned marker-confirmed challenge HTML"
        )
        assert store.firecrawl_targets("run-001")[0].status == "in_progress"
        assert list((tmp_path / "raw").glob("*")) == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (FirecrawlAuthError("HTTP 401"), 401),
        (FirecrawlPaymentRequiredError("HTTP 402"), 402),
        (FirecrawlRateLimitError("HTTP 429"), 429),
    ],
)
def test_scheduler_stops_immediately_on_global_provider_errors(
    tmp_path: Path, error: BaseException, status: int
) -> None:
    first = _target("docket-a", 0)
    second = _target("docket-b", 1)
    source = FixtureSource(
        {
            first.source_url: [error],
            second.source_url: [_success(second, "should not run")],
        }
    )
    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )
        with pytest.raises(type(error)):
            scheduler.run([first, second])

        assert source.calls == [first.source_url]
        attempt = store.firecrawl_attempts("run-001")[0]
        assert attempt.status == "provider_error"
        assert attempt.provider_http_status == status


def test_scheduler_opens_circuit_after_five_consecutive_provider_5xx(
    tmp_path: Path,
) -> None:
    targets = [_target(f"docket-{index}", index) for index in range(6)]
    source = FixtureSource(
        {
            target.source_url: [FirecrawlServerError("provider failure (HTTP 500)")]
            for target in targets
        }
    )
    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )
        with pytest.raises(FirecrawlCircuitOpenError, match="5 consecutive"):
            scheduler.run(targets)

        assert source.calls == [target.source_url for target in targets[:5]]
        assert [
            attempt.provider_http_status
            for attempt in store.firecrawl_attempts("run-001")
        ] == [
            500,
        ] * 5


def test_scheduler_permanently_reserves_worst_case_budget(tmp_path: Path) -> None:
    first = _target("docket-a", 0)
    second = _target("docket-b", 1)
    source = FixtureSource(
        {
            first.source_url: [_success(first, "first")],
            second.source_url: [_success(second, "must not run")],
        }
    )
    with _store(tmp_path, credit_cap=5) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )
        with pytest.raises(FirecrawlBudgetExceededError):
            scheduler.run([first, second])

        assert source.calls == [first.source_url]
        assert store.firecrawl_run_summary("run-001")["remaining_authorization"] == 0


def test_scheduler_exhausts_retries_and_resume_does_not_repeat_work(
    tmp_path: Path,
) -> None:
    good = _target("docket-a", 0)
    bad = _target("docket-b", 1)
    source = FixtureSource(
        {
            good.source_url: [_success(good, "good")],
            bad.source_url: [
                FirecrawlServerError("HTTP 500"),
                FirecrawlServerError("HTTP 500"),
                FirecrawlServerError("HTTP 500"),
            ],
        }
    )
    with _store(tmp_path) as store:
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )
        first_result = scheduler.run([bad, good])
        assert source.calls == [
            good.source_url,
            bad.source_url,
            bad.source_url,
            bad.source_url,
        ]
        assert [page.target_id for page in first_result.pages] == ["docket-a"]
        assert {
            target.target_id: target.status
            for target in store.firecrawl_targets("run-001")
        } == {
            "docket-a": "succeeded",
            "docket-b": "retry_exhausted",
        }

        empty_source = FixtureSource({})
        resumed = BudgetedFirecrawlScheduler(
            store=store,
            source=empty_source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([good, bad])
        assert empty_source.calls == []
        assert [page.raw_html for page in resumed.pages] == ["good"]
        assert {
            key: resumed.summary[key] for key in store.firecrawl_run_summary("run-001")
        } == store.firecrawl_run_summary("run-001")


def test_load_successful_pages_reconstructs_and_verifies_durable_run(
    tmp_path: Path,
) -> None:
    target = _target("search-a", 0)
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=FixtureSource(
                {target.source_url: [_success(target, "<html>search</html>\n")]}
            ),
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([target])

        loaded = load_successful_firecrawl_pages(store=store, run_id="run-001")

        assert loaded == result.pages

        loaded[0].artifact_path.write_text("tampered")
        with pytest.raises(FirecrawlArtifactError, match=r"artifact .* mismatch"):
            load_successful_firecrawl_pages(store=store, run_id="run-001")


def test_scheduler_marks_crash_window_authorization_interrupted_before_retry(
    tmp_path: Path,
) -> None:
    target = _target("docket-a", 0)
    with _store(tmp_path) as store:
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target.target_id,
            target_kind=target.target_kind,
            source_url=target.source_url,
            ordinal=target.ordinal,
        )
        store.authorize_firecrawl_attempt(
            "run-001",
            target_id=target.target_id,
            page_number=target.page_number,
            request_url=target.source_url,
        )
        source = FixtureSource({target.source_url: [_success(target, "retried")]})
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([target])

        assert [attempt.status for attempt in store.firecrawl_attempts("run-001")] == [
            "interrupted",
            "succeeded",
        ]
        assert result.pages[0].attempt_number == 2


def test_scheduler_resumes_legacy_terminal_202_and_interrupted_authorization(
    tmp_path: Path,
) -> None:
    succeeded = _target("docket-a", 0)
    accepted = _target("docket-b", 1)
    interrupted = _target("docket-c", 2)
    pending = _target("docket-d", 3)
    with _store(tmp_path) as store:
        BudgetedFirecrawlScheduler(
            store=store,
            source=FixtureSource(
                {succeeded.source_url: [_success(succeeded, "already durable")]}
            ),
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        ).run([succeeded])

        for target in (accepted, interrupted, pending):
            store.ensure_firecrawl_target(
                "run-001",
                target_id=target.target_id,
                target_kind=target.target_kind,
                source_url=target.source_url,
                ordinal=target.ordinal,
            )
        accepted_attempt = store.authorize_firecrawl_attempt(
            "run-001",
            target_id=accepted.target_id,
            page_number=accepted.page_number,
            request_url=accepted.source_url,
        )
        store.finalize_firecrawl_attempt(
            accepted_attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=202,
            failure_code="target_http_status_invalid",
            failure_message="CourtListener target returned a non-success status",
            failure_transient=False,
            failure_response_sha256="a" * 64,
        )
        store.set_firecrawl_target_status(
            "run-001", accepted.target_id, "terminal_error"
        )
        store.authorize_firecrawl_attempt(
            "run-001",
            target_id=interrupted.target_id,
            page_number=interrupted.page_number,
            request_url=interrupted.source_url,
        )

        resumed_source = FixtureSource(
            {
                accepted.source_url: [_success(accepted, "accepted recovered")],
                interrupted.source_url: [
                    _success(interrupted, "interrupted recovered")
                ],
                pending.source_url: [_success(pending, "pending acquired")],
            }
        )
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=resumed_source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            sleeper=lambda _seconds: None,
        ).run([succeeded, accepted, interrupted, pending])

        assert resumed_source.calls == [
            pending.source_url,
            accepted.source_url,
            interrupted.source_url,
        ]
        assert [page.target_id for page in result.pages] == [
            succeeded.target_id,
            accepted.target_id,
            interrupted.target_id,
            pending.target_id,
        ]
        assert {
            target.target_id: target.status
            for target in store.firecrawl_targets("run-001")
        } == {
            succeeded.target_id: "succeeded",
            accepted.target_id: "succeeded",
            interrupted.target_id: "succeeded",
            pending.target_id: "succeeded",
        }
        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.status for attempt in attempts] == [
            "succeeded",
            "target_error",
            "interrupted",
            "succeeded",
            "succeeded",
            "succeeded",
        ]
        assert result.summary["run_reserved_credits"] == 30
        assert result.summary["run_reported_credits"] == 25


def test_scheduler_bounds_retried_target_202_to_existing_attempt_cap(
    tmp_path: Path,
) -> None:
    target = _target("docket-accepted", 0)
    with _store(tmp_path) as store:
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target.target_id,
            target_kind=target.target_kind,
            source_url=target.source_url,
            ordinal=target.ordinal,
        )
        legacy_attempt = store.authorize_firecrawl_attempt(
            "run-001",
            target_id=target.target_id,
            page_number=target.page_number,
            request_url=target.source_url,
        )
        store.finalize_firecrawl_attempt(
            legacy_attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=202,
            failure_code="target_http_status_invalid",
            failure_message="CourtListener target returned a non-success status",
            failure_transient=False,
            failure_response_sha256="b" * 64,
        )
        store.set_firecrawl_target_status("run-001", target.target_id, "terminal_error")
        source = FixtureSource(
            {
                target.source_url: [
                    FirecrawlTargetHTTPError(
                        202, reported_credits=5, proxy_used="stealth"
                    ),
                    FirecrawlTargetHTTPError(
                        202, reported_credits=5, proxy_used="stealth"
                    ),
                    _success(target, "must not exceed attempt cap"),
                ]
            }
        )

        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            sleeper=lambda _seconds: None,
        ).run([target])

        assert result.pages == ()
        assert source.calls == [target.source_url, target.source_url]
        assert [
            (attempt.status, attempt.target_http_status, attempt.failure_transient)
            for attempt in store.firecrawl_attempts("run-001")
        ] == [
            ("target_error", 202, False),
            ("target_error", 202, True),
            ("target_error", 202, True),
        ]
        assert store.firecrawl_targets("run-001")[0].status == "retry_exhausted"
        assert result.summary["run_reserved_credits"] == 15
        assert result.summary["run_reported_credits"] == 15


def test_scheduler_does_not_recover_legacy_202_without_strict_response_evidence(
    tmp_path: Path,
) -> None:
    target = _target("docket-unproven-accepted", 0)
    with _store(tmp_path) as store:
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target.target_id,
            target_kind=target.target_kind,
            source_url=target.source_url,
            ordinal=target.ordinal,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-001",
            target_id=target.target_id,
            page_number=target.page_number,
            request_url=target.source_url,
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=202,
            failure_code="target_http_status_invalid",
            failure_message="CourtListener target returned a non-success status",
            failure_transient=False,
            failure_response_sha256=None,
        )
        store.set_firecrawl_target_status("run-001", target.target_id, "terminal_error")
        source = FixtureSource(
            {target.source_url: [_success(target, "must not be trusted to retry")]}
        )

        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            sleeper=lambda _seconds: None,
        ).run([target])

        assert result.pages == ()
        assert source.calls == []
        assert len(store.firecrawl_attempts("run-001")) == 1
        assert store.firecrawl_targets("run-001")[0].status == "terminal_error"


def test_scheduler_resumes_recent_eight_of_ten_202s_at_two_workers_after_cooldown(
    tmp_path: Path,
) -> None:
    targets = [_target(f"docket-{index:02d}", index) for index in range(54)]
    already_succeeded = targets[:2]
    accepted = targets[2:10]
    pending = targets[10:]
    cooldowns: list[float] = []
    with _store(tmp_path) as store:
        for target in targets:
            store.ensure_firecrawl_target(
                "run-001",
                target_id=target.target_id,
                target_kind=target.target_kind,
                source_url=target.source_url,
                ordinal=target.ordinal,
            )
        for target in already_succeeded:
            attempt = store.authorize_firecrawl_attempt(
                "run-001",
                target_id=target.target_id,
                page_number=target.page_number,
                request_url=target.source_url,
            )
            store.commit_firecrawl_artifact(
                attempt.attempt_id,
                tmp_path / "raw" / f"{target.target_id}.html",
                f"<html>{target.target_id}</html>".encode(),
                reported_credits=5,
                proxy_used="stealth",
                target_http_status=200,
            )
        for index, target in enumerate(accepted):
            attempt = store.authorize_firecrawl_attempt(
                "run-001",
                target_id=target.target_id,
                page_number=target.page_number,
                request_url=target.source_url,
            )
            store.finalize_firecrawl_attempt(
                attempt.attempt_id,
                status="target_error",
                reported_credits=5,
                proxy_used="stealth",
                provider_http_status=200,
                target_http_status=202,
                failure_code="target_http_status_invalid",
                failure_message=("CourtListener target returned a non-success status"),
                failure_transient=False,
                failure_response_sha256=f"{index + 1:064x}",
            )
            store.set_firecrawl_target_status(
                "run-001", target.target_id, "terminal_error"
            )

        source = FixtureSource(
            {
                target.source_url: [_success(target, f"recovered {target.target_id}")]
                for target in (*accepted, *pending)
            }
        )
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=10,
            sleeper=cooldowns.append,
        ).run(targets)

        assert cooldowns == [5.0]
        assert result.summary["configured_max_workers"] == 10
        assert result.summary["initial_effective_workers"] == 2
        assert result.summary["minimum_effective_workers"] == 2
        assert result.summary["final_effective_workers"] == 10
        assert result.summary["target_http_202_cooldown_count"] == 1
        assert set(source.calls[:44]) == {target.source_url for target in pending}
        assert set(source.calls[44:]) == {target.source_url for target in accepted}
        attempts = store.firecrawl_attempts("run-001")
        assert [attempt.target_id for attempt in attempts[10:54]] == [
            target.target_id for target in pending
        ]
        assert [attempt.target_id for attempt in attempts[54:]] == [
            target.target_id for target in accepted
        ]
        assert len(result.pages) == len(targets)
        assert result.summary["run_reserved_credits"] == 310
        assert result.summary["run_reported_credits"] == 310


def test_scheduler_exponentially_cools_repeated_202_pressure_windows(
    tmp_path: Path,
) -> None:
    targets = [_target(f"docket-pressure-{index:02d}", index) for index in range(41)]
    accepted_indexes = {0, 10, 19, 27, 34}
    cooldowns: list[float] = []

    def accepted_error(index: int) -> FirecrawlTargetHTTPError:
        error = FirecrawlTargetHTTPError(
            202,
            reported_credits=5,
            proxy_used="stealth",
        )
        error.attach_response_evidence(
            provider_http_status=200,
            response_sha256=f"{index + 1:064x}",
        )
        return error

    source = FixtureSource(
        {
            target.source_url: (
                [accepted_error(index), _success(target, "recovered")]
                if index in accepted_indexes
                else [_success(target, "clean")]
            )
            for index, target in enumerate(targets)
        }
    )
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            max_workers=10,
            sleeper=cooldowns.append,
        ).run(targets)

        assert cooldowns == [5.0, 10.0, 20.0, 40.0, 60.0]
        assert result.summary["configured_max_workers"] == 10
        assert result.summary["initial_effective_workers"] == 10
        assert result.summary["minimum_effective_workers"] == 5
        assert result.summary["final_effective_workers"] == 7
        assert result.summary["target_http_202_cooldown_count"] == 5
        assert result.summary["target_http_202_maximum_cooldown_seconds"] == 60.0
        assert len(result.pages) == len(targets)
        assert len(store.firecrawl_attempts("run-001")) == len(targets) + 5


def test_scheduler_cooldown_interruption_authorizes_no_new_attempt(
    tmp_path: Path,
) -> None:
    accepted = _target("docket-accepted", 0)
    pending = _target("docket-pending", 1)
    with _store(tmp_path) as store:
        for target in (accepted, pending):
            store.ensure_firecrawl_target(
                "run-001",
                target_id=target.target_id,
                target_kind=target.target_kind,
                source_url=target.source_url,
                ordinal=target.ordinal,
            )
        attempt = store.authorize_firecrawl_attempt(
            "run-001",
            target_id=accepted.target_id,
            page_number=accepted.page_number,
            request_url=accepted.source_url,
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=202,
            failure_code="target_http_status_invalid",
            failure_message="CourtListener target returned a non-success status",
            failure_transient=False,
            failure_response_sha256="c" * 64,
        )
        store.set_firecrawl_target_status(
            "run-001", accepted.target_id, "terminal_error"
        )

        def interrupt(_seconds: float) -> None:
            raise RuntimeError("controlled stop during cooldown")

        source = FixtureSource(
            {
                accepted.source_url: [_success(accepted, "must not run")],
                pending.source_url: [_success(pending, "must not run")],
            }
        )
        with pytest.raises(RuntimeError, match="controlled stop"):
            BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id="run-001",
                artifact_dir=tmp_path / "raw",
                max_workers=10,
                sleeper=interrupt,
            ).run([accepted, pending])

        assert source.calls == []
        assert len(store.firecrawl_attempts("run-001")) == 1
        assert store.firecrawl_run_summary("run-001")["run_reserved_credits"] == 5


def test_target_202_pressure_does_not_increment_provider_5xx_breaker(
    tmp_path: Path,
) -> None:
    first = _target("docket-server-a", 0)
    accepted = _target("docket-accepted", 1)
    second = _target("docket-server-b", 2)
    accepted_error = FirecrawlTargetHTTPError(
        202,
        reported_credits=5,
        proxy_used="stealth",
    )
    accepted_error.attach_response_evidence(
        provider_http_status=200,
        response_sha256="d" * 64,
    )
    source = FixtureSource(
        {
            first.source_url: [
                FirecrawlServerError("HTTP 500"),
                _success(first, "first recovered"),
            ],
            accepted.source_url: [
                accepted_error,
                _success(accepted, "accepted recovered"),
            ],
            second.source_url: [
                FirecrawlServerError("HTTP 500"),
                _success(second, "second recovered"),
            ],
        }
    )
    with _store(tmp_path) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
            provider_5xx_circuit_threshold=2,
            sleeper=lambda _seconds: None,
        ).run([first, accepted, second])

        assert len(result.pages) == 3
        assert store.firecrawl_run_status("run-001") == "active"
        assert [
            (attempt.status, attempt.failure_code)
            for attempt in store.firecrawl_attempts("run-001")
        ] == [
            ("provider_error", "provider_server_error"),
            ("target_error", "target_http_status_retryable"),
            ("provider_error", "provider_server_error"),
            ("succeeded", None),
            ("succeeded", None),
            ("succeeded", None),
        ]

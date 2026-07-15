from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from legalforecast.ingestion.budgeted_courtlistener_html_source import (
    DurableBudgetedCourtListenerHTMLSource,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlScrapeResult,
)

_RUN_ID = "courtlistener-docket-html-v1"
_DOCKET_ID = "70649963"
_SOURCE_URL = f"https://www.courtlistener.com/docket/{_DOCKET_ID}/"
_HTML = "<html><table id='docket-entry-table'></table></html>"


class _CountingSource:
    def __init__(self, result: FirecrawlScrapeResult | None) -> None:
        self.result = result
        self.calls = 0

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls += 1
        if self.result is None:
            raise AssertionError("resume must not issue another provider request")
        assert source_url == self.result.source_url
        return self.result


class _UnexpectedProviderFailureSource:
    def __init__(self) -> None:
        self.calls = 0

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls += 1
        assert source_url == _SOURCE_URL
        raise RuntimeError("fixture provider outcome unknown")


def _store(tmp_path: Path, *, reserved_credits: int) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
    store.ensure_batch("batch-001", {"source": "firecrawl"})
    store.ensure_firecrawl_run(
        _RUN_ID,
        batch_id="batch-001",
        config={"proxy": "basic", "max_attempts": 1},
        credit_cap=100,
        reserved_credits_per_attempt=reserved_credits,
    )
    return store


def _target() -> FirecrawlTargetSpec:
    return FirecrawlTargetSpec(
        target_id=f"courtlistener-docket:{_DOCKET_ID}",
        target_kind="docket",
        source_url=_SOURCE_URL,
        page_number=1,
        ordinal=int(_DOCKET_ID),
    )


def _result() -> FirecrawlScrapeResult:
    return FirecrawlScrapeResult(
        source_url=_SOURCE_URL,
        docket_id=_DOCKET_ID,
        raw_html=_HTML,
        target_status_code=200,
        proxy_requested="basic",
        proxy_used="basic",
        cache_state="miss",
        credits_used=1.0,
        raw={"success": True},
        resolved_url=_SOURCE_URL,
    )


def _response() -> FirecrawlHTTPResponse:
    return FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": _HTML,
                "metadata": {
                    "statusCode": 200,
                    "proxyUsed": "basic",
                    "cacheState": "miss",
                    "creditsUsed": 1,
                    "sourceURL": _SOURCE_URL,
                },
            },
        },
    )


def _adapter(
    store: CycleAcquisitionStore,
    raw_html_dir: Path,
    transport: FirecrawlFixtureTransport,
) -> DurableBudgetedCourtListenerHTMLSource:
    return DurableBudgetedCourtListenerHTMLSource(
        store=store,
        source=FirecrawlCourtListenerHTMLSource(
            FirecrawlConfig(api_key="test-key", proxy="basic"),
            transport=transport,
        ),
        run_id=_RUN_ID,
        raw_html_dir=raw_html_dir,
    )


def test_post_result_commit_failure_is_terminal_and_stops_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _target()
    source = _CountingSource(_result())
    with _store(tmp_path, reserved_credits=1) as store:

        def fail_before_write(*_args: object, **_kwargs: object) -> None:
            raise OSError("fixture commit failure")

        monkeypatch.setattr(store, "commit_firecrawl_artifact", fail_before_write)
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id=_RUN_ID,
            artifact_dir=tmp_path / "raw",
            max_attempts=1,
            terminalize_abandoned_authorizations=True,
        )

        with pytest.raises(OSError, match="fixture commit failure"):
            scheduler.run((target,))

        [attempt] = store.firecrawl_attempts(_RUN_ID)
        assert attempt.status == "interrupted"
        assert attempt.failure_code == "result_commit_failed"
        assert attempt.failure_transient is False
        assert attempt.reserved_credits == 1
        assert attempt.reported_credits == 1
        assert attempt.proxy_used == "basic"
        assert attempt.target_http_status == 200
        [stored_target] = store.firecrawl_targets(_RUN_ID)
        assert stored_target.status == "terminal_error"
        assert source.calls == 1

        resumed_source = _CountingSource(None)
        resumed = BudgetedFirecrawlScheduler(
            store=store,
            source=resumed_source,
            run_id=_RUN_ID,
            artifact_dir=tmp_path / "raw",
            max_attempts=1,
            terminalize_abandoned_authorizations=True,
        ).run((target,))

        assert resumed.pages == ()
        assert resumed_source.calls == 0
        assert len(store.firecrawl_attempts(_RUN_ID)) == 1


def test_legacy_scheduler_still_raises_and_can_retry_ordinary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _target()
    first_source = _CountingSource(_result())
    with _store(tmp_path, reserved_credits=1) as store:
        original_commit: Callable[..., object] = store.commit_firecrawl_artifact

        def fail_before_write(*_args: object, **_kwargs: object) -> None:
            raise OSError("fixture legacy commit failure")

        monkeypatch.setattr(store, "commit_firecrawl_artifact", fail_before_write)
        with pytest.raises(OSError, match="legacy commit failure"):
            BudgetedFirecrawlScheduler(
                store=store,
                source=first_source,
                run_id=_RUN_ID,
                artifact_dir=tmp_path / "raw",
                max_attempts=2,
            ).run((target,))

        [interrupted] = store.firecrawl_attempts(_RUN_ID)
        assert interrupted.status == "interrupted"
        assert interrupted.failure_code is None
        assert first_source.calls == 1

        monkeypatch.setattr(store, "commit_firecrawl_artifact", original_commit)
        retry_source = _CountingSource(_result())
        resumed = BudgetedFirecrawlScheduler(
            store=store,
            source=retry_source,
            run_id=_RUN_ID,
            artifact_dir=tmp_path / "raw",
            max_attempts=2,
        ).run((target,))

        assert len(resumed.pages) == 1
        assert resumed.pages[0].attempt_number == 2
        assert retry_source.calls == 1
        assert [attempt.status for attempt in store.firecrawl_attempts(_RUN_ID)] == [
            "interrupted",
            "succeeded",
        ]


def test_unexpected_provider_failure_remains_candidate_local(
    tmp_path: Path,
) -> None:
    source = _UnexpectedProviderFailureSource()
    with _store(tmp_path, reserved_credits=1) as store:
        result = BudgetedFirecrawlScheduler(
            store=store,
            source=source,
            run_id=_RUN_ID,
            artifact_dir=tmp_path / "raw",
            max_attempts=1,
            terminalize_abandoned_authorizations=True,
        ).run((_target(),))

        assert result.pages == ()
        [attempt] = store.firecrawl_attempts(_RUN_ID)
        assert attempt.status == "interrupted"
        assert attempt.failure_code == "authorization_abandoned"
        assert attempt.reported_credits is None
        assert attempt.proxy_used is None
        assert attempt.target_http_status is None
        assert source.calls == 1


def test_adapter_stops_on_orphaned_commit_failure_and_quarantines_on_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_html_dir = tmp_path / "raw"
    destination = raw_html_dir / f"{_DOCKET_ID}.html"
    with _store(tmp_path, reserved_credits=1) as store:
        original_commit: Callable[..., object] = store.commit_firecrawl_artifact

        def fail_after_write(
            _attempt_id: int,
            artifact_path: str | Path,
            content: bytes,
            **_kwargs: object,
        ) -> None:
            path = Path(artifact_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            raise OSError("fixture failure after artifact publication")

        monkeypatch.setattr(store, "commit_firecrawl_artifact", fail_after_write)
        first_transport = FirecrawlFixtureTransport([_response()])
        first = _adapter(store, raw_html_dir, first_transport)

        with pytest.raises(OSError, match="failure after artifact publication"):
            first.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        [attempt] = store.firecrawl_attempts(_RUN_ID)
        assert attempt.status == "interrupted"
        assert attempt.failure_code == "result_commit_failed_with_orphan"
        assert attempt.failure_transient is False
        assert attempt.reserved_credits == 1
        assert attempt.reported_credits == 1
        assert attempt.proxy_used == "basic"
        assert attempt.target_http_status == 200
        assert destination.read_text(encoding="utf-8") == _HTML
        assert tuple((tmp_path / "firecrawl-untrusted-orphans").glob("*")) == ()
        assert len(first_transport.requests) == 1

        monkeypatch.setattr(store, "commit_firecrawl_artifact", original_commit)
        resumed_transport = FirecrawlFixtureTransport([])
        resumed = _adapter(store, raw_html_dir, resumed_transport)
        with pytest.raises(FirecrawlArtifactError, match="result_commit_failed"):
            resumed.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        assert destination.exists() is False
        quarantine = tuple(
            (tmp_path / "firecrawl-untrusted-orphans").glob(
                f"docket-{_DOCKET_ID}-attempt-{attempt.attempt_id}-*.html"
            )
        )
        assert len(quarantine) == 1
        assert quarantine[0].read_text(encoding="utf-8") == _HTML
        assert resumed_transport.requests == []
        assert len(store.firecrawl_attempts(_RUN_ID)) == 1
        [stored_target] = store.firecrawl_targets(_RUN_ID)
        assert stored_target.status == "terminal_error"

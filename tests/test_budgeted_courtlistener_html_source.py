from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.ingestion.budgeted_courtlistener_html_source import (
    DurableBudgetedCourtListenerHTMLSource,
)
from legalforecast.ingestion.budgeted_firecrawl import FirecrawlArtifactError
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlURLValidationError,
)

_DOCKET_ID = "70649963"
_SOURCE_URL = (
    "https://www.courtlistener.com/docket/70649963/sam-v-easy-honda-the-clerks/"
)
_CANONICAL_URL = "https://www.courtlistener.com/docket/70649963/"
_HTML = "<html><table id='docket-entry-table'></table></html>"


def _store(tmp_path: Path) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
    store.ensure_batch("batch-001", {"source": "courtlistener-rest-firecrawl-html"})
    store.ensure_firecrawl_run(
        "courtlistener-docket-html-v1",
        batch_id="batch-001",
        config={
            "schema_version": "legalforecast.firecrawl_docket_html_run.v1",
            "proxy": "basic",
        },
        credit_cap=100,
        reserved_credits_per_attempt=1,
    )
    return store


def _response(
    *,
    target_status: int = 200,
    source_url: str = _CANONICAL_URL,
    proxy_used: str = "basic",
    credits_used: int = 1,
) -> FirecrawlHTTPResponse:
    return FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": _HTML,
                "metadata": {
                    "statusCode": target_status,
                    "proxyUsed": proxy_used,
                    "cacheState": "miss",
                    "creditsUsed": credits_used,
                    "sourceURL": source_url,
                },
            },
        },
    )


def _adapter(
    *,
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
        run_id="courtlistener-docket-html-v1",
        raw_html_dir=raw_html_dir,
    )


def test_adapter_validates_docket_identity_before_durable_authorization(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        transport = FirecrawlFixtureTransport([_response()])
        source = _adapter(
            store=store,
            raw_html_dir=tmp_path / "raw",
            transport=transport,
        )

        with pytest.raises(FirecrawlURLValidationError):
            source.fetch(docket_id="999", source_url=_SOURCE_URL)

        assert transport.requests == []
        assert store.firecrawl_targets("courtlistener-docket-html-v1") == ()
        assert store.firecrawl_attempts("courtlistener-docket-html-v1") == ()


def test_adapter_commits_exact_docket_artifact_and_cumulative_audit(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw"
    with _store(tmp_path) as store:
        transport = FirecrawlFixtureTransport([_response()])
        source = _adapter(
            store=store,
            raw_html_dir=raw_html_dir,
            transport=transport,
        )

        assert source.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL) == _HTML

        destination = raw_html_dir / f"{_DOCKET_ID}.html"
        assert destination.read_text(encoding="utf-8") == _HTML
        [attempt] = store.firecrawl_attempts("courtlistener-docket-html-v1")
        assert attempt.artifact_path == destination.resolve()
        assert attempt.request_url == _CANONICAL_URL
        assert attempt.reported_credits == 1
        assert attempt.target_http_status == 200
        assert len(transport.requests) == 1
        assert transport.requests[0]["payload"]["url"] == _CANONICAL_URL  # type: ignore[index]

        summary = source.audit_summary()
        assert summary["run_id"] == "courtlistener-docket-html-v1"
        assert summary["run_reserved_credits"] == 1
        assert summary["run_reported_credits"] == 1
        assert summary["successful_docket_count"] == 1
        assert summary["unavailable_docket_count"] == 0


def test_successful_resume_verifies_committed_source_path_and_hash(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw"
    with _store(tmp_path) as store:
        first_transport = FirecrawlFixtureTransport([_response()])
        first = _adapter(
            store=store,
            raw_html_dir=raw_html_dir,
            transport=first_transport,
        )
        assert first.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL) == _HTML

        resumed_transport = FirecrawlFixtureTransport([])
        resumed = _adapter(
            store=store,
            raw_html_dir=raw_html_dir,
            transport=resumed_transport,
        )
        assert resumed.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL) == _HTML
        assert resumed_transport.requests == []
        assert (
            resumed.verify_existing_raw_html(
                _DOCKET_ID,
                _SOURCE_URL,
                raw_html_dir / f"{_DOCKET_ID}.html",
            )
            == _HTML
        )

        (raw_html_dir / f"{_DOCKET_ID}.html").write_text(
            "untrusted replacement", encoding="utf-8"
        )
        with pytest.raises(FirecrawlArtifactError, match=r"artifact .* mismatch"):
            resumed.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)
        assert resumed_transport.requests == []


def test_untracked_existing_raw_html_is_never_trusted_or_authorized(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw"
    raw_html_dir.mkdir()
    raw_path = raw_html_dir / f"{_DOCKET_ID}.html"
    raw_path.write_text(_HTML, encoding="utf-8")
    with _store(tmp_path) as store:
        transport = FirecrawlFixtureTransport([])
        source = _adapter(
            store=store,
            raw_html_dir=raw_html_dir,
            transport=transport,
        )

        with pytest.raises(FirecrawlArtifactError, match="no unique durable target"):
            source.verify_existing_raw_html(_DOCKET_ID, _SOURCE_URL, raw_path)
        with pytest.raises(FirecrawlArtifactError, match="no unique durable target"):
            source.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        assert transport.requests == []
        assert store.firecrawl_targets("courtlistener-docket-html-v1") == ()
        assert store.firecrawl_attempts("courtlistener-docket-html-v1") == ()


@pytest.mark.parametrize("target_status", [404, 410])
def test_fully_valid_target_unavailable_is_terminal_and_resumes_without_call(
    tmp_path: Path, target_status: int
) -> None:
    with _store(tmp_path) as store:
        first_transport = FirecrawlFixtureTransport(
            [_response(target_status=target_status)]
        )
        source = _adapter(
            store=store,
            raw_html_dir=tmp_path / "raw",
            transport=first_transport,
        )

        with pytest.raises(CourtListenerUnavailableError):
            source.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        [attempt] = store.firecrawl_attempts("courtlistener-docket-html-v1")
        assert attempt.status == "target_error"
        assert attempt.target_http_status == target_status
        assert attempt.provider_http_status == 200
        assert attempt.reported_credits == 1
        assert attempt.proxy_used == "basic"
        assert attempt.failure_code == "target_http_status_invalid"
        assert source.audit_summary()["unavailable_docket_count"] == 1

        resumed_transport = FirecrawlFixtureTransport([])
        resumed = _adapter(
            store=store,
            raw_html_dir=tmp_path / "raw",
            transport=resumed_transport,
        )
        with pytest.raises(CourtListenerUnavailableError):
            resumed.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)
        assert resumed_transport.requests == []
        assert len(store.firecrawl_attempts("courtlistener-docket-html-v1")) == 1


def test_target_unavailable_requires_fully_validated_provider_metadata(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        source = _adapter(
            store=store,
            raw_html_dir=tmp_path / "raw",
            transport=FirecrawlFixtureTransport(
                [_response(target_status=404, proxy_used="stealth")]
            ),
        )

        with pytest.raises(FirecrawlArtifactError, match="did not produce"):
            source.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        [attempt] = store.firecrawl_attempts("courtlistener-docket-html-v1")
        assert attempt.failure_code == "proxy_used_disallowed"
        assert attempt.target_http_status is None


def test_adapter_rejects_non_basic_source_before_any_attempt(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        with pytest.raises(ValueError, match="basic proxy"):
            DurableBudgetedCourtListenerHTMLSource(
                store=store,
                source=FirecrawlCourtListenerHTMLSource(
                    FirecrawlConfig(api_key="test-key", proxy="auto"),
                    transport=FirecrawlFixtureTransport([]),
                ),
                run_id="courtlistener-docket-html-v1",
                raw_html_dir=tmp_path / "raw",
            )


def test_other_validated_target_status_fails_closed_not_as_unavailable(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        source = _adapter(
            store=store,
            raw_html_dir=tmp_path / "raw",
            transport=FirecrawlFixtureTransport([_response(target_status=500)]),
        )

        with pytest.raises(FirecrawlArtifactError, match="did not produce"):
            source.fetch(docket_id=_DOCKET_ID, source_url=_SOURCE_URL)

        assert source.audit_summary()["unavailable_docket_count"] == 0

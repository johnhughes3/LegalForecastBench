from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Any, cast

import legalforecast.ingestion.courtlistener_acquisition as acquisition_module
import legalforecast.ingestion.courtlistener_live_html_source as live_html_source_module
import pytest
from legalforecast.ingestion.courtlistener_acquisition import (
    LiveCourtListenerDocketHTMLSource,
    discover_courtlistener_mtd_candidates,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerBotChallengeError,
    CourtListenerClient,
    CourtListenerClientError,
)
from legalforecast.ingestion.courtlistener_live_html_source import (
    ChallengeStoppingCourtListenerDocketHTMLSource,
)
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, DiscoveryPage

_SOURCE_URL = "https://www.courtlistener.com/docket/70649963/"
_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "courtlistener"
_CHALLENGE_BODY_SCAN_LIMIT = 256_000


class _Response(AbstractContextManager["_Response"]):
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body))

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return _SOURCE_URL

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class _Opener:
    def __init__(self, response: _Response | urllib.error.HTTPError) -> None:
        self.response = response

    def open(self, request: object, *, timeout: float) -> _Response:
        del request, timeout
        if isinstance(self.response, urllib.error.HTTPError):
            raise self.response
        return self.response


def _opener_factory(
    response: _Response | urllib.error.HTTPError,
) -> Callable[..., _Opener]:
    def build_opener(*handlers: object) -> _Opener:
        del handlers
        return _Opener(response)

    return build_opener


def _http_error(status: int, body: bytes) -> urllib.error.HTTPError:
    return _http_error_with_content_type(status, body, "text/html; charset=utf-8")


def _http_error_with_content_type(
    status: int,
    body: bytes,
    content_type: str,
) -> urllib.error.HTTPError:
    headers = Message()
    headers["Content-Type"] = content_type
    return urllib.error.HTTPError(
        _SOURCE_URL,
        status,
        "injected",
        headers,
        io.BytesIO(body),
    )


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (200, b"<title>Attention Required! | Cloudflare</title>"),
        (
            403,
            (
                b"<html><script src='/cdn-cgi/challenge-platform/x'></script>"
                b"<div id='cf-chl-widget'></div></html>"
            ),
        ),
        (
            429,
            (
                b"<html><div id='cf-chl-widget'>"
                b"Checking your browser before accessing"
                b"</div></html>"
            ),
        ),
    ],
)
def test_live_html_source_classifies_only_marker_confirmed_bounded_bodies(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: bytes,
) -> None:
    response: _Response | urllib.error.HTTPError
    response = (
        _Response(body, status=status) if status == 200 else _http_error(status, body)
    )
    monkeypatch.setattr(
        acquisition_module.urllib.request,
        "build_opener",
        _opener_factory(response),
    )

    with pytest.raises(CourtListenerBotChallengeError) as raised:
        ChallengeStoppingCourtListenerDocketHTMLSource(
            source=LiveCourtListenerDocketHTMLSource()
        ).fetch(
            docket_id="70649963",
            source_url=_SOURCE_URL,
        )

    assert "Branch C" in str(raised.value)
    assert body.decode() not in str(raised.value)


@pytest.mark.parametrize("status", [403, 429])
def test_unmarked_http_status_is_not_a_bot_challenge(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    monkeypatch.setattr(
        acquisition_module.urllib.request,
        "build_opener",
        _opener_factory(
            _http_error(status, b"<html><p>ordinary error page</p></html>")
        ),
    )

    with pytest.raises(CourtListenerClientError) as raised:
        ChallengeStoppingCourtListenerDocketHTMLSource(
            source=LiveCourtListenerDocketHTMLSource()
        ).fetch(
            docket_id="70649963",
            source_url=_SOURCE_URL,
        )

    assert not isinstance(raised.value, CourtListenerBotChallengeError)
    assert f"status {status}" in str(raised.value)


def test_valid_docket_with_injected_challenge_platform_script_is_returned() -> None:
    raw_html = (
        "<html><head>"
        "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"
        "</head><body><div id='docket-entry-table'></div></body></html>"
    )

    class _InjectedScriptDocketSource:
        def fetch(self, *, docket_id: str, source_url: str) -> str:
            del docket_id, source_url
            return raw_html

    source = ChallengeStoppingCourtListenerDocketHTMLSource(
        source=_InjectedScriptDocketSource()
    )

    assert source.fetch(docket_id="70649963", source_url=_SOURCE_URL) == raw_html


def test_successful_unicode_html_is_bounded_before_challenge_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_html = "<html>" + ("🙂" * 300_000) + "</html>"
    classified_body_lengths: list[int] = []

    class _OversizedUnicodeDocketSource:
        def fetch(self, *, docket_id: str, source_url: str) -> str:
            del docket_id, source_url
            return raw_html

    def record_classified_body(
        body: bytes,
        *,
        content_type: str | None,
    ) -> None:
        del content_type
        classified_body_lengths.append(len(body))

    monkeypatch.setattr(
        live_html_source_module,
        "_raise_for_docket_html_challenge",
        record_classified_body,
    )
    source = ChallengeStoppingCourtListenerDocketHTMLSource(
        source=_OversizedUnicodeDocketSource()
    )

    assert source.fetch(docket_id="70649963", source_url=_SOURCE_URL) == raw_html
    assert classified_body_lengths == [_CHALLENGE_BODY_SCAN_LIMIT]


def test_challenge_marker_beyond_bounded_prefix_is_not_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"x" * _CHALLENGE_BODY_SCAN_LIMIT + b"cf-chl-widget"
    monkeypatch.setattr(
        acquisition_module.urllib.request,
        "build_opener",
        _opener_factory(_http_error(403, body)),
    )

    with pytest.raises(CourtListenerClientError) as raised:
        ChallengeStoppingCourtListenerDocketHTMLSource(
            source=LiveCourtListenerDocketHTMLSource()
        ).fetch(
            docket_id="70649963",
            source_url=_SOURCE_URL,
        )

    assert not isinstance(raised.value, CourtListenerBotChallengeError)


def test_challenge_marker_inside_json_is_not_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        acquisition_module.urllib.request,
        "build_opener",
        _opener_factory(
            _http_error_with_content_type(
                403,
                b'{"detail":"the literal cf-chl-marker is diagnostic text"}',
                "application/json",
            )
        ),
    )

    with pytest.raises(CourtListenerClientError) as raised:
        ChallengeStoppingCourtListenerDocketHTMLSource(
            source=LiveCourtListenerDocketHTMLSource()
        ).fetch(
            docket_id="70649963",
            source_url=_SOURCE_URL,
        )

    assert not isinstance(raised.value, CourtListenerBotChallengeError)


def _store(tmp_path: Path) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle(
        {
            "policy_schema": "legalforecast.cycle_acquisition_policy.v1",
            "eligibility_anchor": "2026-06-30",
        }
    )
    store.ensure_batch(
        "durable-batch",
        {
            "provider": "courtlistener",
            "window": ["2026-07-11", "2026-07-15"],
        },
    )
    return store


def test_marker_confirmed_html_stops_run_after_prior_candidate_state_is_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits = tuple(
        DiscoveryHit(
            provider_hit_id=f"hit-{candidate_id}",
            candidate_id=candidate_id,
            payload={"id": candidate_id, "docket_id": candidate_id},
        )
        for candidate_id in ("101", "102")
    )

    class _SearchSource:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def fetch_page(
            self,
            *,
            term: str,
            cursor: str | None,
            page_size: int,
        ) -> DiscoveryPage:
            del self, term, cursor, page_size
            return DiscoveryPage(hits=hits, next_cursor=None, exhausted=True)

    challenge_source = ChallengeStoppingCourtListenerDocketHTMLSource(
        source=LiveCourtListenerDocketHTMLSource()
    )
    challenge_body = (
        b"<html><div id='cf-chl-widget'>"
        b"Checking your browser before accessing"
        b"</div></html>"
    )
    monkeypatch.setattr(
        acquisition_module.urllib.request,
        "build_opener",
        _opener_factory(_Response(challenge_body)),
    )

    def screen_candidate(**kwargs: Any) -> tuple[dict[str, object], None]:
        candidate_id = cast(str, kwargs["docket_id"])
        if candidate_id == "102":
            challenge_source.fetch(docket_id="70649963", source_url=_SOURCE_URL)
            raise AssertionError("challenge fetch must stop the run")
        return (
            {
                "candidate": {
                    "docket_id": candidate_id,
                    "metadata": {"case_id": candidate_id},
                },
                "first_written_mtd_disposition_date": "2026-07-14",
            },
            None,
        )

    monkeypatch.setattr(
        acquisition_module,
        "_DurableCourtListenerSearchSource",
        _SearchSource,
    )
    monkeypatch.setattr(acquisition_module, "_screen_candidate", screen_candidate)

    with _store(tmp_path) as store:
        with pytest.raises(CourtListenerBotChallengeError, match="Branch C"):
            discover_courtlistener_mtd_candidates(
                client=cast(CourtListenerClient, object()),
                html_source=challenge_source,
                raw_html_dir=tmp_path / "raw",
                decision_filed_on_or_after=date(2026, 6, 30),
                search_window_start=date(2026, 7, 11),
                search_window_end=date(2026, 7, 15),
                query_terms=("motion to dismiss",),
                target_clean_cases=100,
                max_candidates=10,
                search_page_size=2,
                progress_store=store,
                batch_id="durable-batch",
            )

        durable = store.batch_terminal_observation("durable-batch", "101")
        interrupted = store.batch_terminal_observation("durable-batch", "102")

    assert durable is not None
    assert durable.state == "accepted"
    assert interrupted is None


def _fixture_pairs() -> Iterator[tuple[Path, Path]]:
    for html_path in sorted(_FIXTURE_ROOT.glob("docket-structural-*.html")):
        yield html_path, html_path.with_suffix(".provenance.json")


def test_sanitized_structural_fixtures_parse_and_carry_provenance() -> None:
    pairs = tuple(_fixture_pairs())

    assert len(pairs) == 2
    for html_path, provenance_path in pairs:
        html = html_path.read_text(encoding="utf-8")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        page = parse_courtlistener_docket_html(
            html,
            source_url=provenance["source_url"],
        )

        assert page.entries
        assert provenance["fetch_date"] == "2026-07-28"
        assert provenance["raw_page_retained"] is False
        assert provenance["alterations"]
        assert provenance["fixture_sha256"] == hashlib.sha256(html.encode()).hexdigest()
        assert "Sam v. Easy Honda" not in html
        assert "Easy Honda" not in html
        assert "DOE" not in html
        assert "ABC CORPORATION" not in html

    single_page = _FIXTURE_ROOT / "docket-structural-single-page-2026-07-28.html"
    paginated = _FIXTURE_ROOT / "docket-structural-paginated-2026-07-28.html"
    assert (
        parse_courtlistener_docket_html(single_page.read_text(encoding="utf-8"))
        .entries[0]
        .documents[0]
        .pacer_only
        is True
    )
    assert (
        parse_courtlistener_docket_html(
            paginated.read_text(encoding="utf-8")
        ).has_next_page
        is True
    )

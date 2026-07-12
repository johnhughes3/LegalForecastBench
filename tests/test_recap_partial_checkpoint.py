from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from legalforecast.ingestion.budgeted_firecrawl import FirecrawlPageRecord
from legalforecast.ingestion.firecrawl_recap_discovery import build_recap_search_url
from legalforecast.ingestion.recap_partial_checkpoint import (
    RecapPartialProjectionError,
    project_partial_recap_checkpoint,
)

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 12)


def _article(
    *,
    docket_id: str,
    document_number: str,
    entry_date: str = "2026-07-02",
    description: str = "Order denying motion to dismiss",
    attachment_number: int | None = None,
) -> str:
    attachment_segment = (
        f"{attachment_number}/" if attachment_number is not None else ""
    )
    return (
        '<article><h3 class="bottom serif">'
        f'<a href="/docket/{docket_id}/case/" class="visitable">'
        f'Case {docket_id}</a></h3><div class="bottom">'
        '<div class="col-md-offset-half"><h4>'
        f'<a href="/docket/{docket_id}/{document_number}/{attachment_segment}case/" '
        f'class="visitable">{description} — Document #{document_number}</a>'
        '</h4><div class="date-block"><span>Date Filed:</span>'
        f'<time datetime="{entry_date}">{entry_date}</time></div>'
        '<div class="inline-block"><span>Description:</span>'
        f'<span class="meta-data-value">{description}</span>'
        "</div></div></div></article>"
    )


def _search_html(
    *,
    articles: str,
    total_results: int,
    page: int = 1,
    total_pages: int = 1,
    next_url: str | None = None,
) -> str:
    pagination = ""
    if total_pages > 1:
        next_link = (
            f'<a href="{next_url}" rel="next" class="btn">Next</a>'
            if next_url is not None
            else ""
        )
        pagination = (
            '<div class="well"><div class="text-center large">'
            f"Page {page} of {total_pages}</div>{next_link}</div>"
        )
    title = f"Search Results for test — {total_results:,} Results — CourtListener.com"
    return (
        f"<!doctype html><html><head><title>{title}</title></head><body>"
        f'<main id="search-results">{articles}</main>{pagination}</body></html>'
    )


def _record(
    *,
    term: str,
    html: str,
    ordinal: int,
    attempt_id: int,
    page: int = 1,
    target_id: str | None = None,
    artifact_path: Path | None = None,
) -> FirecrawlPageRecord:
    source_url = build_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=page,
    )
    raw = html.encode("utf-8")
    return FirecrawlPageRecord(
        target_id=target_id or f"{term}:{page}",
        target_kind="search",
        source_url=source_url,
        page_number=page,
        ordinal=ordinal,
        attempt_id=attempt_id,
        attempt_number=1,
        raw_html=html,
        artifact_path=artifact_path or Path(f"/artifacts/{attempt_id}.html"),
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_byte_count=len(raw),
        reported_credits=5,
        proxy_used="stealth",
        target_http_status=200,
    )


def test_projects_verified_pages_into_explicitly_partial_checkpoints() -> None:
    first = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=(
                _article(docket_id="20", document_number="2")
                + _article(docket_id="3", document_number="1")
            ),
            total_results=2,
        ),
        ordinal=0,
        attempt_id=101,
    )
    second = _record(
        term="order on motion to dismiss",
        html=_search_html(
            articles=(
                _article(docket_id="3", document_number="1")
                + _article(docket_id="11", document_number="4")
            ),
            total_results=2,
        ),
        ordinal=1,
        attempt_id=102,
    )

    result = project_partial_recap_checkpoint((second, first))

    assert [page.attempt_id for page in result.pages] == [101, 102]
    assert [entry.entry_key for entry in result.entries] == [
        "3:document:1",
        "11:document:4",
        "20:document:2",
    ]
    duplicated_entry = result.entries[0]
    assert duplicated_entry.matched_terms == (
        "motion to dismiss",
        "order on motion to dismiss",
    )
    assert duplicated_entry.source_attempt_ids == (101, 102)
    assert len(duplicated_entry.source_artifact_sha256s) == 2
    assert [docket.docket_id for docket in result.candidates] == ["3", "11", "20"]
    assert all(candidate.checkpoint_only for candidate in result.candidates)
    assert all(candidate.complete is False for candidate in result.candidates)
    assert all(candidate.saturated is False for candidate in result.candidates)
    assert result.summary.acquired_page_count == 2
    assert result.summary.raw_hit_count == 4
    assert result.summary.unique_entry_count == 3
    assert result.summary.duplicate_entry_count == 1
    assert result.summary.unique_docket_count == 3
    assert result.summary.reported_credits_total == 10
    assert result.summary.checkpoint_only is True
    assert result.summary.complete is False
    assert result.summary.saturated is False
    assert result.summary.provider_completeness_status == "unproven"


def test_projection_is_deterministic_under_input_reordering() -> None:
    records = (
        _record(
            term="motion to dismiss denied",
            html=_search_html(
                articles=_article(docket_id="7", document_number="8"),
                total_results=1,
            ),
            ordinal=3,
            attempt_id=301,
        ),
        _record(
            term="motion to dismiss",
            html=_search_html(
                articles=_article(docket_id="5", document_number="6"),
                total_results=1,
            ),
            ordinal=2,
            attempt_id=201,
        ),
    )

    assert project_partial_recap_checkpoint(
        records
    ) == project_partial_recap_checkpoint(tuple(reversed(records)))


def test_document_attachments_have_distinct_checkpoint_entry_identities() -> None:
    record = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=(
                _article(docket_id="5", document_number="6", attachment_number=1)
                + _article(docket_id="5", document_number="6", attachment_number=3)
            ),
            total_results=2,
        ),
        ordinal=0,
        attempt_id=1,
    )

    result = project_partial_recap_checkpoint((record,))

    assert [entry.entry_key for entry in result.entries] == [
        "5:document:6:attachment:1",
        "5:document:6:attachment:3",
    ]
    assert {entry.source_entry_key for entry in result.entries} == {"5:document:6"}
    assert result.summary.raw_hit_count == 2
    assert result.summary.unique_entry_count == 2


def test_empty_projection_remains_an_explicit_non_saturated_checkpoint() -> None:
    result = project_partial_recap_checkpoint(())

    assert result.pages == ()
    assert result.entries == ()
    assert result.candidates == ()
    assert result.summary.acquired_page_count == 0
    assert result.summary.complete is False
    assert result.summary.saturated is False


@pytest.mark.parametrize("broken_field", ["hash", "bytes", "page", "kind", "status"])
def test_rejects_records_that_do_not_reconcile_to_verified_artifacts(
    broken_field: str,
) -> None:
    record = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=_article(docket_id="5", document_number="6"),
            total_results=1,
        ),
        ordinal=0,
        attempt_id=1,
    )
    if broken_field == "hash":
        broken = replace(record, artifact_sha256="0" * 64)
    elif broken_field == "bytes":
        broken = replace(record, artifact_byte_count=record.artifact_byte_count + 1)
    elif broken_field == "page":
        broken = replace(record, page_number=2)
    elif broken_field == "kind":
        broken = replace(record, target_kind="docket")
    else:
        broken = replace(record, target_http_status=404)

    with pytest.raises(RecapPartialProjectionError):
        project_partial_recap_checkpoint((broken,))


def test_rejects_conflicting_duplicate_entry_identity() -> None:
    first = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=_article(
                docket_id="5", document_number="6", entry_date="2026-07-01"
            ),
            total_results=1,
        ),
        ordinal=0,
        attempt_id=1,
    )
    conflicting = _record(
        term="order on motion to dismiss",
        html=_search_html(
            articles=_article(
                docket_id="5", document_number="6", entry_date="2026-07-02"
            ),
            total_results=1,
        ),
        ordinal=1,
        attempt_id=2,
    )

    with pytest.raises(
        RecapPartialProjectionError, match="conflicting duplicate entry"
    ):
        project_partial_recap_checkpoint((first, conflicting))


@pytest.mark.parametrize("conflict", ["attempt", "target", "ordinal", "artifact_path"])
def test_rejects_conflicting_durable_page_provenance(conflict: str) -> None:
    first = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=_article(docket_id="5", document_number="6"),
            total_results=1,
        ),
        ordinal=0,
        attempt_id=1,
    )
    kwargs: dict[str, object] = {
        "ordinal": 1,
        "attempt_id": 2,
        "target_id": "other:1",
        "artifact_path": Path("/artifacts/2.html"),
    }
    if conflict == "attempt":
        kwargs["attempt_id"] = first.attempt_id
    elif conflict == "target":
        kwargs["target_id"] = first.target_id
    elif conflict == "ordinal":
        kwargs["ordinal"] = first.ordinal
    else:
        kwargs["artifact_path"] = first.artifact_path
    second = _record(
        term="motion to dismiss denied",
        html=_search_html(
            articles=_article(docket_id="7", document_number="8"),
            total_results=1,
        ),
        **kwargs,  # type: ignore[arg-type]
    )

    with pytest.raises(
        RecapPartialProjectionError, match="conflicting page provenance"
    ):
        project_partial_recap_checkpoint((first, second))


def test_rejects_two_artifacts_for_the_same_search_page() -> None:
    first_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    assert urlsplit(first_url).query
    first = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=_article(docket_id="5", document_number="6"),
            total_results=1,
        ),
        ordinal=0,
        attempt_id=1,
    )
    second = _record(
        term="motion to dismiss",
        html=_search_html(
            articles=_article(docket_id="7", document_number="8"),
            total_results=1,
        ),
        ordinal=1,
        attempt_id=2,
        target_id="same-search-page-retry",
    )

    with pytest.raises(RecapPartialProjectionError, match="duplicate search page"):
        project_partial_recap_checkpoint((first, second))

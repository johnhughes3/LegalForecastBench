from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.courtlistener_web import (
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
    may_stop_at_anchor_boundary,
    paginate_courtlistener_docket,
)

BASE_URL = "https://www.courtlistener.com/docket/73320440/doe-v-abc/"


def test_paginates_newest_first_and_preserves_page_provenance() -> None:
    fetched_urls: list[str] = []
    responses = {
        canonical_courtlistener_docket_page_url(BASE_URL, page_number=1): _page_html(
            entries=(
                ("entry-9", "9", "July 10, 2026", "ORDER granting MOTION TO DISMISS."),
            ),
            has_next=True,
        ),
        canonical_courtlistener_docket_page_url(BASE_URL, page_number=2): _page_html(
            entries=(("entry-2", "2", "June 1, 2026", "MOTION TO DISMISS filed."),),
            has_next=False,
        ),
    }

    def fetch(source_url: str) -> str:
        fetched_urls.append(source_url)
        return responses[source_url]

    bundle = paginate_courtlistener_docket(
        BASE_URL,
        fetch=fetch,
        max_pages=4,
    )

    assert fetched_urls == [
        f"{BASE_URL}?order_by=desc&page=1",
        f"{BASE_URL}?order_by=desc&page=2",
    ]
    assert bundle.docket_id == "73320440"
    assert [entry.row_id for entry in bundle.entries] == ["entry-9", "entry-2"]
    assert bundle.is_exhaustive is True
    assert bundle.complete_for_anchor_window is True
    assert bundle.stopped_at_anchor_boundary is False
    assert [page.page_number for page in bundle.pages] == [1, 2]
    assert bundle.pages[0].entry_row_ids == ("entry-9",)
    assert bundle.pages[1].entry_row_ids == ("entry-2",)
    assert bundle.pages[0].sha256 != bundle.pages[1].sha256
    assert bundle.as_docket_page().has_next_page is False


def test_stops_after_proven_descending_anchor_boundary() -> None:
    responses = {
        f"{BASE_URL}?order_by=desc&page=1": _page_html(
            entries=(("entry-9", "9", "July 10, 2026", "ORDER on MOTION TO DISMISS."),),
            has_next=True,
        ),
        f"{BASE_URL}?order_by=desc&page=2": _page_html(
            entries=(("entry-2", "2", "June 29, 2026", "MOTION TO DISMISS filed."),),
            has_next=True,
        ),
    }
    fetched_urls: list[str] = []

    def fetch(source_url: str) -> str:
        fetched_urls.append(source_url)
        return responses[source_url]

    bundle = paginate_courtlistener_docket(
        BASE_URL,
        fetch=fetch,
        max_pages=8,
        decision_anchor=date(2026, 6, 30),
    )

    assert len(fetched_urls) == 2
    assert bundle.is_exhaustive is False
    assert bundle.stopped_at_anchor_boundary is True
    assert bundle.complete_for_anchor_window is True
    with pytest.raises(CourtListenerDocketPaginationError, match="cannot masquerade"):
        bundle.as_docket_page()


def test_anchor_helper_requires_every_observed_date_and_global_order() -> None:
    missing_date = parse_courtlistener_docket_html(
        _page_html(
            entries=(("entry-1", "1", None, "MOTION TO DISMISS filed."),),
            has_next=True,
        ),
        source_url=f"{BASE_URL}?order_by=desc&page=1",
        docket_id="73320440",
    )
    reversed_order = parse_courtlistener_docket_html(
        _page_html(
            entries=(
                ("entry-1", "1", "June 29, 2026", "MOTION TO DISMISS filed."),
                ("entry-2", "2", "July 1, 2026", "ORDER on MOTION TO DISMISS."),
            ),
            has_next=True,
        ),
        source_url=f"{BASE_URL}?order_by=desc&page=1",
        docket_id="73320440",
    )

    assert (
        may_stop_at_anchor_boundary((missing_date,), anchor=date(2026, 6, 30)) is False
    )
    assert (
        may_stop_at_anchor_boundary((reversed_order,), anchor=date(2026, 6, 30))
        is False
    )


def test_missing_date_exhausts_pages_instead_of_unsafe_anchor_stop() -> None:
    responses = {
        f"{BASE_URL}?order_by=desc&page=1": _page_html(
            entries=(("entry-9", "9", "July 10, 2026", "ORDER on MOTION TO DISMISS."),),
            has_next=True,
        ),
        f"{BASE_URL}?order_by=desc&page=2": _page_html(
            entries=(("entry-2", "2", None, "MOTION TO DISMISS filed."),),
            has_next=True,
        ),
        f"{BASE_URL}?order_by=desc&page=3": _page_html(
            entries=(("entry-1", "1", "May 1, 2026", "Complaint filed."),),
            has_next=False,
        ),
    }
    fetched_urls: list[str] = []

    def fetch(source_url: str) -> str:
        fetched_urls.append(source_url)
        return responses[source_url]

    bundle = paginate_courtlistener_docket(
        BASE_URL,
        fetch=fetch,
        max_pages=3,
        decision_anchor=date(2026, 6, 30),
    )

    assert len(fetched_urls) == 3
    assert bundle.is_exhaustive is True
    assert bundle.stopped_at_anchor_boundary is False


def test_overlapping_rows_merge_unique_documents_and_keep_both_page_sources() -> None:
    page_one = _with_document(
        _page_html(
            entries=(("entry-9", "9", "July 10, 2026", "ORDER on MOTION TO DISMISS."),),
            has_next=True,
        ),
        text="ORDER on MOTION TO DISMISS.",
        href="https://storage.courtlistener.com/recap/order.pdf",
    )
    page_two = _with_document(
        _page_html(
            entries=(
                ("entry-9", "9", "July 10, 2026", "ORDER on MOTION TO DISMISS."),
                ("entry-2", "2", "June 1, 2026", "MOTION TO DISMISS filed."),
            ),
            has_next=False,
        ),
        text="ORDER on MOTION TO DISMISS.",
        href="https://storage.courtlistener.com/recap/order-attachment.pdf",
    )
    responses = {
        f"{BASE_URL}?order_by=desc&page=1": page_one,
        f"{BASE_URL}?order_by=desc&page=2": page_two,
    }

    bundle = paginate_courtlistener_docket(
        BASE_URL,
        fetch=responses.__getitem__,
        max_pages=2,
    )

    assert [entry.row_id for entry in bundle.entries] == ["entry-9", "entry-2"]
    assert [document.href for document in bundle.entries[0].documents] == [
        "https://storage.courtlistener.com/recap/order.pdf",
        "https://storage.courtlistener.com/recap/order-attachment.pdf",
    ]
    assert bundle.pages[0].entry_row_ids == ("entry-9",)
    assert bundle.pages[1].entry_row_ids == ("entry-9", "entry-2")


def test_conflicting_overlapping_row_fails_closed() -> None:
    responses = {
        f"{BASE_URL}?order_by=desc&page=1": _page_html(
            entries=(("entry-9", "9", "July 10, 2026", "First text."),),
            has_next=True,
        ),
        f"{BASE_URL}?order_by=desc&page=2": _page_html(
            entries=(("entry-9", "9", "July 10, 2026", "Conflicting text."),),
            has_next=False,
        ),
    }

    with pytest.raises(
        CourtListenerDocketPaginationError,
        match="duplicate_entry_conflict",
    ):
        paginate_courtlistener_docket(
            BASE_URL,
            fetch=responses.__getitem__,
            max_pages=2,
        )


def test_repeated_content_fails_without_returning_partial_bundle() -> None:
    repeated = _page_html(
        entries=(("entry-9", "9", "July 10, 2026", "ORDER on MOTION TO DISMISS."),),
        has_next=True,
    )

    with pytest.raises(CourtListenerDocketPaginationError, match="repeated_content"):
        paginate_courtlistener_docket(
            BASE_URL,
            fetch=lambda _source_url: repeated,
            max_pages=3,
        )


def test_nonterminal_page_at_cap_fails_closed() -> None:
    with pytest.raises(CourtListenerDocketPaginationError, match="page_limit"):
        paginate_courtlistener_docket(
            BASE_URL,
            fetch=lambda _source_url: _page_html(
                entries=(("entry-9", "9", "July 10, 2026", "ORDER."),),
                has_next=True,
            ),
            max_pages=1,
        )


@pytest.mark.parametrize("max_pages", [0, -1])
def test_rejects_nonpositive_page_cap(max_pages: int) -> None:
    with pytest.raises(CourtListenerDocketPaginationError, match="positive"):
        paginate_courtlistener_docket(
            BASE_URL,
            fetch=lambda _source_url: "unused",
            max_pages=max_pages,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://www.courtlistener.com/docket/73320440/doe-v-abc/",
        "https://courtlistener.com/docket/73320440/doe-v-abc/",
        "https://www.courtlistener.com/docket/not-numeric/doe-v-abc/",
        "https://www.courtlistener.com/docket/73320440/doe-v-abc/?order_by=asc",
        "https://www.courtlistener.com/docket/73320440/doe-v-abc/#fragment",
    ],
)
def test_rejects_noncanonical_or_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(CourtListenerDocketPaginationError):
        canonical_courtlistener_docket_page_url(base_url, page_number=1)


def test_page_url_helper_requires_positive_page_number() -> None:
    with pytest.raises(CourtListenerDocketPaginationError, match="positive"):
        canonical_courtlistener_docket_page_url(BASE_URL, page_number=0)


def _page_html(
    *,
    entries: tuple[tuple[str, str, str | None, str], ...],
    has_next: bool,
) -> str:
    next_class = "btn btn-default" if has_next else "btn btn-default disabled"
    rows = "".join(
        _entry_html(
            row_id=row_id,
            entry_number=entry_number,
            filed_at=filed_at,
            text=text,
        )
        for row_id, entry_number, filed_at, text in entries
    )
    return f"""
    <html>
      <head><title>DOE v. ABC CORPORATION - CourtListener.com</title></head>
      <body>
        <a rel="next" class="{next_class}" href="?page=2">Next</a>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row bold"><div>Document Number</div></div>
          {rows}
        </div>
      </body>
    </html>
    """


def _entry_html(
    *,
    row_id: str,
    entry_number: str,
    filed_at: str | None,
    text: str,
) -> str:
    date_html = (
        "" if filed_at is None else f'<span title="{filed_at}">{filed_at}</span>'
    )
    return f"""
      <div class="row odd" id="{row_id}">
        <div class="col-xs-1 text-center"><p>{entry_number}</p></div>
        <div class="col-xs-3 col-sm-2"><p>{date_html}</p></div>
        <div class="col-xs-8 col-lg-7"><p>{text}</p></div>
      </div>
    """


def _with_document(raw_html: str, *, text: str, href: str) -> str:
    document_html = f"""
      <div class="row recap-documents">
        <div class="col-xs-3"><p>Main Document</p></div>
        <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
        <div class="btn-group"><a href="{href}">Download PDF</a></div>
      </div>
    """
    return raw_html.replace(f"<p>{text}</p>", f"<p>{text}</p>{document_html}", 1)

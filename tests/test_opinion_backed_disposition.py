"""Tests for binding CourtListener opinions to resolved RECAP dockets."""

from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.opinion_backed_disposition import (
    OpinionBackedDispositionError,
    bind_public_opinion_to_docket,
    fetch_and_bind_public_opinion,
    public_opinion_pdf_url,
    select_opinion_resolution_for_page,
    verbatim_mtd_disposition_excerpt,
)


def _page(*entries: CourtListenerWebDocketEntry) -> CourtListenerWebDocketPage:
    return CourtListenerWebDocketPage(
        docket_id="71878956",
        source_url="/docket/71878956/example/",
        title="Example v. Example",
        entries=entries,
        has_next_page=False,
    )


def _entry(
    number: int,
    filed_at: str,
    text: str,
    *,
    pacer_only: bool = False,
) -> CourtListenerWebDocketEntry:
    documents = (
        (
            CourtListenerWebDocument(
                kind="main",
                description=text,
                href=None,
                action_label="Buy on PACER",
                pacer_only=True,
            ),
        )
        if pacer_only
        else ()
    )
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{number}",
        entry_number=str(number),
        filed_at=filed_at,
        text=text,
        documents=documents,
    )


def test_public_opinion_pdf_url_normalizes_storage_path() -> None:
    assert (
        public_opinion_pdf_url("pdf/2026/07/14/example_v._example.pdf")
        == "https://storage.courtlistener.com/pdf/2026/07/14/example_v._example.pdf"
    )


@pytest.mark.parametrize(
    "value",
    (
        "../secret.pdf",
        "pdf/../../secret.pdf",
        "pdf/example.txt",
        "https://evil.example/example.pdf",
        "pdf/example.pdf?token=secret",
        "pdf/example.pdf%3Ftoken.pdf",
        "pdf/example.pdf%253Ftoken.pdf",
        "pdf/example.pdf%23fragment.pdf",
        "pdf/example.pdf%3Bparams.pdf",
        "pdf/example pdf.pdf",
    ),
)
def test_public_opinion_pdf_url_rejects_unsafe_or_non_pdf_paths(value: str) -> None:
    assert public_opinion_pdf_url(value) is None


def test_bind_public_opinion_augments_unique_same_day_mtd_order() -> None:
    page = _page(
        _entry(1, "October 30, 2025", "Complaint"),
        _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
        _entry(
            8,
            "July 14, 2026",
            "Order on Motion to Dismiss",
            pacer_only=True,
        ),
    )

    result = bind_public_opinion_to_docket(
        page,
        opinion_id="11395231",
        opinion_date=date(2026, 7, 14),
        plain_text=(
            "The defendant moved to dismiss the complaint under Rule 12(b)(6). "
            "For the foregoing reasons, the motion to dismiss is granted in part "
            "and denied in part."
        ),
        local_path="pdf/2026/07/14/example_v._example.pdf",
    )

    assert result.decision_row_id == "entry-8"
    assert result.decision_entry_number == "8"
    assert result.public_pdf_url.endswith("example_v._example.pdf")
    augmented = result.page.entries[-1]
    assert "granted in part and denied in part" in augmented.text
    assert len(augmented.documents) == 1
    assert augmented.documents[0].pacer_only is False
    assert augmented.documents[0].href == result.public_pdf_url
    assert result.screen.strict_clean is True


def test_bind_public_opinion_fails_closed_on_same_day_ambiguity() -> None:
    page = _page(
        _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
        _entry(8, "July 14, 2026", "Order on Motion to Dismiss"),
        _entry(9, "July 14, 2026", "Order on Motion to Dismiss Counterclaim"),
    )

    with pytest.raises(OpinionBackedDispositionError, match="exactly one"):
        bind_public_opinion_to_docket(
            page,
            opinion_id="11395231",
            opinion_date=date(2026, 7, 14),
            plain_text="The motion to dismiss is granted.",
            local_path="pdf/2026/07/14/example.pdf",
        )


def test_bind_public_opinion_rejects_text_without_actual_mtd_disposition() -> None:
    page = _page(
        _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
        _entry(8, "July 14, 2026", "Order on Motion to Dismiss"),
    )

    with pytest.raises(OpinionBackedDispositionError, match="actual MTD disposition"):
        bind_public_opinion_to_docket(
            page,
            opinion_id="11395231",
            opinion_date=date(2026, 7, 14),
            plain_text="The court recounts the procedural history of the case.",
            local_path="pdf/2026/07/14/example.pdf",
        )


def test_verbatim_excerpt_uses_conclusion_without_unrelated_posture_text() -> None:
    conclusion = (
        "For the foregoing reasons, the defendant's motion to dismiss under "
        "Rule 12(b)(6) is denied."
    )
    full_text = (
        "The court first discusses an unrelated criminal prosecution cited by "
        "one party.\n\n"
        f"{conclusion}"
    )

    assert verbatim_mtd_disposition_excerpt(full_text) == conclusion

    result = bind_public_opinion_to_docket(
        _page(
            _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
            _entry(8, "July 14, 2026", "Order on Motion to Dismiss"),
        ),
        opinion_id="11395231",
        opinion_date=date(2026, 7, 14),
        plain_text=full_text,
        local_path="pdf/2026/07/14/example.pdf",
    )

    assert result.screen.strict_clean is True
    assert "criminal prosecution" not in result.page.entries[-1].text
    assert result.disposition_excerpt == conclusion


def test_verbatim_excerpt_uses_final_disposition_not_historical_outcome() -> None:
    historical = "Earlier in the litigation, the motion to dismiss was denied."
    operative = (
        "For the foregoing reasons, Defendant's renewed motion to dismiss is "
        "granted with prejudice."
    )

    assert verbatim_mtd_disposition_excerpt(f"{historical}\n\n{operative}") == operative


def test_fetch_and_bind_public_opinion_validates_frozen_resolution_evidence() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                RecordedCourtListenerResponse(
                    method="GET",
                    path="/clusters/10927691/",
                    params={},
                    status_code=200,
                    payload={
                        "id": 10927691,
                        "docket": (
                            "https://www.courtlistener.com/api/rest/v4/"
                            "dockets/73614335/"
                        ),
                        "date_filed": "2026-07-14",
                        "blocked": False,
                        "absolute_url": "/opinion/10927691/example/",
                        "sub_opinions": [
                            "https://www.courtlistener.com/api/rest/v4/"
                            "opinions/11395231/"
                        ],
                    },
                ),
                RecordedCourtListenerResponse(
                    method="GET",
                    path="/opinions/11395231/",
                    params={},
                    status_code=200,
                    payload={
                        "id": 11395231,
                        "cluster": (
                            "https://www.courtlistener.com/api/rest/v4/"
                            "clusters/10927691/"
                        ),
                        "plain_text": (
                            "The defendant moved under Rule 12(b)(6). The motion "
                            "to dismiss is denied."
                        ),
                        "local_path": "pdf/2026/07/14/example.pdf",
                        "download_url": "https://ecf.example/show_public_doc",
                        "absolute_url": "/opinion/10927691/example/",
                    },
                ),
            )
        ),
    )
    page = _page(
        _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
        _entry(8, "July 14, 2026", "Order on Motion to Dismiss"),
    )
    resolution = {
        "schema_version": "legalforecast.opinion_recap_resolution.v1",
        "source_opinion": {
            "candidate_id": "73614335",
            "cluster_id": "10927691",
            "date_filed": "2026-07-14",
            "absolute_url": "/opinion/10927691/example/",
            "sub_opinions": [
                {
                    "opinion_id": "11395231",
                    "absolute_url": "/opinion/10927691/example/",
                    "download_url": "https://ecf.example/show_public_doc",
                    "local_path": "pdf/2026/07/14/example.pdf",
                }
            ],
        },
        "resolved_recap": {
            "docket_id": "71878956",
            "court_id": "dcd",
            "docket_number": "1:25-cv-03820",
            "case_name": "EXAMPLE v. EXAMPLE",
        },
    }

    result = fetch_and_bind_public_opinion(
        client,
        page=page,
        resolved_recap_docket_id="71878956",
        resolution_evidence=resolution,
    )

    assert result.disposition.decision_entry_number == "8"
    assert result.evidence["cluster_id"] == "10927691"
    assert result.evidence["opinion_id"] == "11395231"
    assert len(str(result.evidence["cluster_response_sha256"])) == 64
    assert len(str(result.evidence["opinion_response_sha256"])) == 64
    assert client.request_count == 2


def test_fetch_and_bind_public_opinion_rejects_resolved_docket_mismatch() -> None:
    with pytest.raises(OpinionBackedDispositionError, match="resolved RECAP docket"):
        fetch_and_bind_public_opinion(
            CourtListenerClient(
                config=CourtListenerConfig(),
                transport=CourtListenerFixtureTransport(()),
            ),
            page=_page(),
            resolved_recap_docket_id="999",
            resolution_evidence={
                "schema_version": "legalforecast.opinion_recap_resolution.v1",
                "source_opinion": {},
                "resolved_recap": {"docket_id": "71878956"},
            },
        )


def test_select_opinion_resolution_uses_unique_matching_docket_date() -> None:
    primary = {
        "schema_version": "legalforecast.opinion_recap_resolution.v1",
        "source_opinion": {
            "candidate_id": "700",
            "cluster_id": "800",
            "date_filed": "2026-07-13",
        },
        "resolved_recap": {"docket_id": "71878956"},
        "additional_resolutions": [
            {
                "schema_version": "legalforecast.opinion_recap_resolution.v1",
                "source_opinion": {
                    "candidate_id": "701",
                    "cluster_id": "801",
                    "date_filed": "2026-07-14",
                },
                "resolved_recap": {"docket_id": "71878956"},
            }
        ],
    }
    page = _page(
        _entry(4, "December 15, 2025", "Motion to Dismiss Complaint"),
        _entry(8, "July 14, 2026", "Order on Motion to Dismiss"),
    )

    selected = select_opinion_resolution_for_page(page, primary)

    assert selected["source_opinion"]["cluster_id"] == "801"

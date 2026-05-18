from __future__ import annotations

from legalforecast.ingestion.docket_markdown import (
    ControlledDocketMarkdownEntry,
    DocketMarkdownMetadata,
    render_controlled_docket_markdown,
)


def test_model_visible_markdown_excludes_target_outcome_entries() -> None:
    artifacts = render_controlled_docket_markdown(_metadata(), _entries())

    markdown = artifacts.model_visible_markdown

    assert "# Controlled Docket: Example Investor v. Issuer Inc." in markdown
    assert "- Candidate ID: cand-1" in markdown
    assert "- Court: S.D.N.Y." in markdown
    assert "- Docket number: 1:26-cv-00001" in markdown
    assert "- Search query: order on motion to dismiss" in markdown
    assert "Complaint filed by Example Investor." in markdown
    assert "Motion to dismiss memorandum filed by Issuer Inc." in markdown
    assert "https://www.courtlistener.com/docket/123/example/" in markdown
    assert "Opinion and order granting motion to dismiss" not in markdown
    assert "packet_section=post_decision" not in markdown


def test_audit_markdown_preserves_full_docket_with_packet_sections() -> None:
    artifacts = render_controlled_docket_markdown(_metadata(), _entries())

    markdown = artifacts.audit_markdown

    assert "## Audit Docket Entries" in markdown
    assert "packet_section=filings" in markdown
    assert "packet_section=exhibits" in markdown
    assert "packet_section=post_decision" in markdown
    assert "Complaint filed by Example Investor." in markdown
    assert "Exhibit A to motion to dismiss." in markdown
    assert "Opinion and order granting motion to dismiss." in markdown
    assert "contains_target_outcome=true" in markdown


def _metadata() -> DocketMarkdownMetadata:
    return DocketMarkdownMetadata(
        candidate_id="cand-1",
        case_id="case-1",
        case_name="Example Investor v. Issuer Inc.",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_url="https://www.courtlistener.com/docket/123/example/",
        search_query="order on motion to dismiss",
        search_window="2026-05-01 to 2026-05-17",
        discovered_at="2026-05-17T14:00:00Z",
    )


def _entries() -> tuple[ControlledDocketMarkdownEntry, ...]:
    return (
        ControlledDocketMarkdownEntry(
            docket_entry_id="entry-1",
            entry_number="1",
            filed_at="2026-01-02",
            entry_text="Complaint filed by Example Investor.",
            packet_section="filings",
            source_url="https://www.courtlistener.com/docket/123/#entry-1",
            source_document_ids=("doc-1",),
        ),
        ControlledDocketMarkdownEntry(
            docket_entry_id="entry-34",
            entry_number="34",
            filed_at="2026-03-01",
            entry_text="Motion to dismiss memorandum filed by Issuer Inc.",
            packet_section="filings",
            source_url="https://www.courtlistener.com/docket/123/#entry-34",
            source_document_ids=("doc-34",),
        ),
        ControlledDocketMarkdownEntry(
            docket_entry_id="entry-35",
            entry_number="35",
            filed_at="2026-03-01",
            entry_text="Exhibit A to motion to dismiss.",
            packet_section="exhibits",
            source_url="https://www.courtlistener.com/docket/123/#entry-35",
            source_document_ids=("doc-35",),
        ),
        ControlledDocketMarkdownEntry(
            docket_entry_id="entry-99",
            entry_number="99",
            filed_at="2026-05-10",
            entry_text="Opinion and order granting motion to dismiss.",
            packet_section="post_decision",
            source_url="https://www.courtlistener.com/docket/123/#entry-99",
            source_document_ids=("doc-99",),
            is_predecision_material=False,
            contains_target_outcome=True,
        ),
    )

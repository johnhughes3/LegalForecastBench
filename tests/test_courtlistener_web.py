from __future__ import annotations

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
    CourtListenerWebParseError,
    classify_courtlistener_entry_role,
    estimate_briefing_completeness,
    parse_courtlistener_docket_html,
    rank_cheapest_complete_candidates,
    starts_with_dispositive_motion,
)


def test_duplicated_metadata_prefix_does_not_let_proposed_order_mask_mtd() -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-24",
        entry_number="24",
        filed_at="Dec 5, 2025",
        text=(
            "24 Dec 5, 2025 24 Dec 5, 2025 MOTION to Dismiss Plaintiff's "
            "Complaint filed by Defendant with Brief/Memorandum in Support. "
            "(Attachments: # 1 Proposed Order)"
        ),
        documents=(
            CourtListenerWebDocument(
                kind="Main Document",
                description="",
                href="https://storage.courtlistener.com/recap/motion.pdf",
                action_label="Download PDF",
                pacer_only=False,
            ),
            CourtListenerWebDocument(
                kind="Attachment 1",
                description="Proposed Order",
                href="https://storage.courtlistener.com/recap/proposed-order.pdf",
                action_label="Download PDF",
                pacer_only=False,
            ),
        ),
    )

    assert classify_courtlistener_entry_role(entry) is CourtListenerEntryRole.MTD_NOTICE


def test_support_appendix_reference_does_not_look_like_leading_motion() -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-25",
        entry_number="25",
        filed_at="Dec 5, 2025",
        text=(
            "25 Dec 5, 2025 25 Dec 5, 2025 Appendix in Support filed by "
            "Defendant re 24 MOTION to Dismiss Plaintiff's Complaint"
        ),
    )

    assert starts_with_dispositive_motion(entry.text) is False


def test_parse_public_docket_html_extracts_entries_documents_and_availability() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    assert page.docket_id == "73320440"
    assert page.is_single_page is True
    assert page.exclusion_reason is None
    assert page.title == "DOE v. ABC CORPORATION"
    assert len(page.entries) == 4

    order = page.mtd_decision_entries[0]
    assert order.entry_number == "5"
    assert order.filed_at == "May 9, 2026, 9:39 a.m."
    assert order.role is CourtListenerEntryRole.DECISION
    assert order.documents[0].description == "Order on Motion to Dismiss"
    assert order.documents[0].freely_available is True
    assert order.documents[0].pacer_only is False

    motion = page.entries[0]
    assert motion.role is CourtListenerEntryRole.MTD_NOTICE
    assert motion.narrative_text is not None
    assert "MOTION TO DISMISS" in motion.narrative_text
    assert "Main Document" not in motion.narrative_text
    assert "Buy on PACER" not in motion.narrative_text
    assert motion.documents[0].pacer_only is True
    assert motion.documents[0].freely_available is False


def test_parser_omits_structurally_empty_document_placeholder() -> None:
    html = (
        "<html><head><title>Minute-only docket</title></head><body>"
        '<div id="docket-entry-table">'
        '<div class="row" id="minute-entry-181045070">'
        '<div class="col-xs-1"></div>'
        '<div class="col-xs-3"><span title="Nov 22, 2021">Nov 22, 2021</span></div>'
        '<div class="col-xs-8">SUMMONS Issued as to Defendants'
        '<div class="row recap-documents"><div></div><div></div></div>'
        "</div></div></div></body></html>"
    )

    page = parse_courtlistener_docket_html(
        html,
        source_url=(
            "https://www.courtlistener.com/docket/61568804/"
            "mcdonald-v-m2-management-inc/"
        ),
    )

    [entry] = page.entries
    assert entry.documents == ()


def test_parser_flags_active_next_page_for_automatic_exclusion() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(next_enabled=True),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    assert page.is_single_page is False
    assert page.has_next_page is True
    assert page.exclusion_reason == "courtlistener_docket_more_than_one_page"


def test_briefing_completeness_counts_roles_and_purchase_pressure() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    estimate = estimate_briefing_completeness(page)

    assert estimate.has_mtd_decision is True
    assert estimate.role_counts == {
        "decision": 1,
        "mtd_notice": 1,
        "opposition": 1,
        "reply": 1,
    }
    assert estimate.missing_core_roles == ()
    assert estimate.pacer_only_document_count == 2
    assert estimate.freely_available_document_count == 2
    assert estimate.estimated_purchase_count == 2


def test_briefing_completeness_counts_judgment_on_pleadings_decision() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            next_enabled=False,
            order_text="ORDER granting Motion for Judgment on the Pleadings.",
            order_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    estimate = estimate_briefing_completeness(page)

    assert estimate.has_mtd_decision is True
    assert estimate.role_counts["decision"] == 1


def test_motion_with_attachment_exhibits_stays_motion_notice() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False).replace(
            "MOTION TO DISMISS filed by ABC CORPORATION.",
            (
                "MOTION to Dismiss by ABC CORPORATION. "
                "(Attachments: # 1 Exhibit A, # 2 Proposed Order)"
            ),
        ),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    assert page.entries[0].role is CourtListenerEntryRole.MTD_NOTICE


def test_joint_motion_with_proposed_order_stays_motion_notice() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False).replace(
            "MOTION TO DISMISS filed by ABC CORPORATION.",
            (
                "Joint MOTION TO DISMISS FOR FAILURE TO STATE A CLAIM filed by "
                "Defendants. Memorandum, Text of Proposed Order."
            ),
        ),
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    assert page.entries[0].role is CourtListenerEntryRole.MTD_NOTICE


def test_parser_prefers_direct_storage_pdf_over_document_landing_page() -> None:
    html = _docket_html(next_enabled=False).replace(
        '<a\n                    href="https://storage.courtlistener.com/recap/order.pdf"',
        '<a href="https://www.courtlistener.com/docket/73320440/5/doe-v-abc/">'
        "View Document</a>"
        '<a\n                    href="https://storage.courtlistener.com/recap/order.pdf"',
    )

    page = parse_courtlistener_docket_html(
        html,
        source_url="https://www.courtlistener.com/docket/73320440/doe-v-abc/",
    )

    order_document = page.mtd_decision_entries[0].documents[0]
    assert order_document.href == "https://storage.courtlistener.com/recap/order.pdf"
    assert order_document.action_label == "Download PDF"


def test_cheapest_candidate_ranking_prefers_fewer_missing_pacer_documents() -> None:
    cheap = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False, motion_is_free=True),
        source_url="https://www.courtlistener.com/docket/1/cheap/",
    )
    expensive = parse_courtlistener_docket_html(
        _docket_html(next_enabled=False, motion_is_free=False),
        source_url="https://www.courtlistener.com/docket/2/expensive/",
    )

    ranked = rank_cheapest_complete_candidates((expensive, cheap))

    assert [estimate.docket_id for estimate in ranked] == ["1", "2"]
    assert ranked[0].estimated_purchase_count < ranked[1].estimated_purchase_count


def test_missing_docket_table_raises_clear_parse_error() -> None:
    try:
        parse_courtlistener_docket_html("<html><title>Page not found</title></html>")
    except CourtListenerWebParseError as exc:
        assert "docket-entry table" in str(exc)
    else:
        raise AssertionError("expected CourtListenerWebParseError")


def _docket_html(
    *,
    next_enabled: bool,
    motion_is_free: bool = False,
    order_text: str = "ORDER granting 4 MOTION TO DISMISS.",
    order_description: str = "Order on Motion to Dismiss",
) -> str:
    next_class = "btn btn-default" if next_enabled else "btn btn-default disabled"
    next_href = "/docket/73320440/doe-v-abc/?page=2" if next_enabled else "#"
    motion_href = (
        "https://storage.courtlistener.com/recap/gov.uscourts.paed.654376.4.0.pdf"
        if motion_is_free
        else "https://ecf.paed.uscourts.gov/doc1/153189999?caseid=654376"
    )
    motion_action = "Download PDF" if motion_is_free else "Buy on PACER"
    motion_class = (
        "btn btn-default btn-xs"
        if motion_is_free
        else ("open_buy_pacer_modal btn btn-default btn-xs")
    )
    return f"""
    <html>
      <head><title>DOE v. ABC CORPORATION - CourtListener.com</title></head>
      <body>
        <h1>DOE v. ABC CORPORATION</h1>
        <a rel="next" class="{next_class}" href="{next_href}">Next</a>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row bold"><div>Document Number</div></div>
          <div class="row odd" id="entry-4">
            <div class="col-xs-1 text-center"><p>4</p></div>
            <div class="col-xs-3 col-sm-2">
              <p><span title="May 9, 2026, 9:31 a.m.">May 9, 2026</span></p>
            </div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION TO DISMISS filed by ABC CORPORATION.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Motion to Dismiss</p></div>
                <div class="btn-group">
                  <a href="{motion_href}" class="{motion_class}">{motion_action}</a>
                </div>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-4-1">
            <div class="col-xs-1 text-center"><p>4-1</p></div>
            <div class="col-xs-3 col-sm-2">
              <p><span title="May 9, 2026, 9:32 a.m.">May 9, 2026</span></p>
            </div>
            <div class="col-xs-8 col-lg-7">
              <p>RESPONSE in Opposition re Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Opposition to Motion to Dismiss</p></div>
                <div class="btn-group">
                  <a href="https://storage.courtlistener.com/recap/opp.pdf">
                    Download PDF
                  </a>
                </div>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-4-2">
            <div class="col-xs-1 text-center"><p>4-2</p></div>
            <div class="col-xs-3 col-sm-2">
              <p><span title="May 9, 2026, 9:33 a.m.">May 9, 2026</span></p>
            </div>
            <div class="col-xs-8 col-lg-7">
              <p>REPLY in support of Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Reply in Support of Motion to Dismiss</p></div>
                <div class="btn-group">
                  <a
                    href="https://ecf.paed.uscourts.gov/doc1/reply"
                    class="open_buy_pacer_modal btn btn-default btn-xs"
                  >
                    Buy on PACER
                  </a>
                </div>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2">
              <p><span title="May 9, 2026, 9:39 a.m.">May 9, 2026</span></p>
            </div>
            <div class="col-xs-8 col-lg-7">
              <p>{order_text}</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>{order_description}</p></div>
                <div class="btn-group">
                  <a
                    href="https://storage.courtlistener.com/recap/order.pdf"
                    class="btn btn-default btn-xs"
                  >
                    Download PDF
                  </a>
                  <a
                    href="https://ecf.paed.uscourts.gov/doc1/order"
                    class="open_buy_pacer_modal btn btn-default btn-xs"
                  >
                    Buy on PACER
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """

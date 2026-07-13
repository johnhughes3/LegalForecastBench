from __future__ import annotations

from datetime import date

from legalforecast.ingestion.courtlistener_acquisition import _linkage_entries
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.mtd_acquisition_screen import (
    LOW_YIELD_MTD_DISCOVERY_TERMS,
    OPTIMIZED_MTD_DECISION_SEARCH_TERMS,
    SECONDARY_MTD_DECISION_SEARCH_TERMS,
    MtdDocketScreenStatus,
    TargetYieldEstimate,
    courtlistener_case_name_slug,
    courtlistener_public_docket_url_from_case_dev,
    screen_case_dev_docket_metadata,
    screen_courtlistener_docket_for_mtd_decision,
    screen_courtlistener_entry_for_mtd_decision,
)
from legalforecast.ingestion.provenance import DocumentRole


def test_optimized_search_terms_prioritize_decision_language() -> None:
    assert OPTIMIZED_MTD_DECISION_SEARCH_TERMS == ("order on motion to dismiss",)
    assert "motion to dismiss" not in OPTIMIZED_MTD_DECISION_SEARCH_TERMS
    assert "order granting motion to dismiss" in SECONDARY_MTD_DECISION_SEARCH_TERMS
    assert "motion to dismiss" in LOW_YIELD_MTD_DISCOVERY_TERMS


def test_public_courtlistener_url_uses_case_dev_docket_id_and_slug() -> None:
    url = courtlistener_public_docket_url_from_case_dev(
        {
            "id": "73341673",
            "caseName": (
                "International Painters and Allied Trades Industry Pension Fund "
                "v. C3 Industrial Blasting & Coatings, Inc."
            ),
            "url": "https://www.courtlistener.com/api/rest/v4/dockets/73341673/",
        }
    )

    assert url == (
        "https://www.courtlistener.com/docket/73341673/"
        "international-painters-and-allied-trades-industry-pension-fund-v-c3-"
        "industrial-blasting-and-coatings-inc/"
    )


def test_courtlistener_case_name_slug_normalizes_punctuation() -> None:
    assert courtlistener_case_name_slug("L.M.L v. Martin") == "l-m-l-v-martin"


def test_case_dev_metadata_screen_accepts_federal_civil_docket() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "73320440",
            "courtId": "flmd",
            "court": "District Court, M.D. Florida",
            "docketNumber": "8:26-cv-00123",
            "caseName": "Doe v. ABC Corporation",
        },
        query="order on motion to dismiss",
    )

    assert screen.accepted_for_scrape is True
    assert screen.exclusion_reasons == ()


def test_case_dev_metadata_screen_excludes_non_civil_and_detention_postures() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "70000000",
            "courtId": "caed",
            "court": "District Court, E.D. California",
            "docketNumber": "2:26-cv-00123",
            "caseName": "Garcia v. Warden, Mesa Verde Detention Facility",
            "natureOfSuit": "Habeas Corpus: Alien Detainee",
        },
        query="order on motion to dismiss",
    )

    assert screen.accepted_for_scrape is False
    assert "habeas_or_immigration_detention_posture" in screen.exclusion_reasons


def test_case_dev_metadata_screen_admits_potential_bankruptcy_adversary() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000001",
            "courtId": "flmb",
            "court": "Bankruptcy Court, M.D. Florida",
            "docketNumber": "6:26-ap-00106",
            "caseName": "Trustee v. Defendant LLC",
        },
        query="order on motion to dismiss",
    )

    assert screen.accepted_for_scrape is True
    assert screen.metadata.case_type_stratum == "bankruptcy_adversary"


def test_case_dev_metadata_screen_still_excludes_main_bankruptcy_case() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000002",
            "courtId": "flmb",
            "court": "Bankruptcy Court, M.D. Florida",
            "docketNumber": "6:26-bk-06489",
            "caseName": "In re Debtor",
        },
        query="order on motion to dismiss case",
    )

    assert screen.accepted_for_scrape is False
    assert screen.exclusion_reasons[0] == "bankruptcy_court"


def test_actual_mtd_decision_entry_accepts_order_on_motion_to_dismiss() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html("ORDER granting 12 Motion to Dismiss."),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_actual_mtd_decision_entry_accepts_report_recommending_mtd_disposition() -> (
    None
):
    page = parse_courtlistener_docket_html(
        _docket_html(
            "REPORT AND RECOMMENDATION re 12 Motion to Dismiss. The Court "
            "recommends that the motion be granted."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_actual_mtd_decision_entry_rejects_procedural_order() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html("Standing Order governing motions to dismiss in this case."),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


def test_actual_mtd_decision_entry_rejects_extension_order() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting extension of time to respond to motion to dismiss."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


def test_actual_mtd_decision_entry_rejects_motion_filing_only() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "Defendant ABC Corporation MOTION to Dismiss complaint.",
            document_description="Motion to Dismiss",
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert screen.exclusion_reasons == ("motion_filing_only",)


def test_actual_mtd_decision_entry_rejects_notice_of_removal_attachment() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "NOTICE OF REMOVAL (STATE COURT COMPLAINT - Complaint) "
            "No answer / motion to dismiss filed.",
            document_description="Notice of Removal AND Order on Motion to Dismiss",
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "notice_of_removal_or_state_record" in screen.exclusion_reasons


def test_actual_mtd_decision_entry_rejects_proposed_order_attachment() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "MOTION to Dismiss filed by Live Oak Banking Company. "
            "Responses due by 5/22/2026. Attachments: Proposed Order "
            "ORDER ON MOTION TO DISMISS.",
            document_description="Proposed Order ORDER ON MOTION TO DISMISS",
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "proposed_order_not_decision" in screen.exclusion_reasons


def test_docket_screen_tracks_actual_but_not_strict_habeas_case() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting 8 Motion to Dismiss.",
            title="Garcia v. Warden, Mesa Verde Detention Facility",
        ),
        source_url="https://www.courtlistener.com/docket/2/garcia-v-warden/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.has_actual_mtd_decision is True
    assert screen.strict_clean is False
    assert screen.status is MtdDocketScreenStatus.ACTUAL_MTD_DECISION_REVIEW_OR_EXCLUDED
    assert "habeas_or_immigration_detention_posture" in screen.exclusion_reasons


def test_docket_screen_can_require_recent_decision_entry_date() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html("ORDER granting 12 Motion to Dismiss."),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        decision_filed_on_or_after=date(2026, 5, 10),
    )

    assert screen.has_actual_mtd_decision is False
    assert screen.status is MtdDocketScreenStatus.EXCLUDED
    assert screen.exclusion_reasons == ("mtd_decision_outside_date_window",)


def test_docket_screen_accepts_rule_7012_adversary_claim_merits_disposition() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-ap-00106",
            entries=(
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (
                    4,
                    "July 3, 2026",
                    "MOTION to Dismiss Count I under Fed. R. Bankr. P. 7012 "
                    "and Fed. R. Civ. P. 12(b)(6).",
                ),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Count I."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000001/trustee-v-defendant/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text=(
            "flmb Bankruptcy Court, M.D. Florida 6:26-ap-00106 Trustee v. Defendant LLC"
        ),
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


def test_docket_screen_rejects_ambiguous_dismiss_adversary_text() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-ap-00106",
            entries=(
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (4, "July 3, 2026", "MOTION to Dismiss Adversary Proceeding."),
                (8, "July 10, 2026", "ORDER granting Motion to Dismiss Adversary."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000001/trustee-v-defendant/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="flmb Bankruptcy Court 6:26-ap-00106",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is False
    assert "bankruptcy_adversary_rule_basis_unproven" in screen.exclusion_reasons


def test_docket_screen_rejects_bankruptcy_main_case_despite_rule_12_words() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="In re Debtor - 6:26-bk-06489",
            entries=(
                (1, "July 1, 2026", "Voluntary Chapter 13 Petition."),
                (4, "July 3, 2026", "Trustee MOTION to Dismiss Case under Rule 12."),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Case."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000002/in-re-debtor/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="flmb Bankruptcy Court 6:26-bk-06489",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is False
    assert "bankruptcy_posture" in screen.exclusion_reasons


def test_adversary_linkage_cannot_promote_generic_dismissal_motion() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-ap-00106",
            entries=(
                (4, "July 3, 2026", "MOTION to Dismiss Adversary Proceeding."),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Adversary."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000001/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-8"},
        docket_id="74000001",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.document_role for entry in normalized] == [DocumentRole.DECISION]


def test_target_yield_estimate_extrapolates_needed_screening_depth() -> None:
    estimate = TargetYieldEstimate(
        screened_count=320,
        actual_decision_count=55,
        strict_clean_count=18,
        target_count=150,
    )

    assert estimate.estimated_screened_for_actual_target == 873
    assert estimate.estimated_screened_for_strict_target == 2667


def _docket_html(
    entry_text: str,
    *,
    title: str = "DOE v. ABC CORPORATION",
    document_description: str = "Order on Motion to Dismiss",
) -> str:
    return f"""
    <html>
      <head><title>{title} - CourtListener.com</title></head>
      <body>
        <h1>{title}</h1>
        <a rel="next" class="btn btn-default disabled" href="#">Next</a>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-12">
            <div class="col-xs-1 text-center"><p>12</p></div>
            <div class="col-xs-3 col-sm-2">
              <p><span title="May 9, 2026, 9:39 a.m.">May 9, 2026</span></p>
            </div>
            <div class="col-xs-8 col-lg-7">
              <p>{entry_text}</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>{document_description}</p></div>
                <div class="btn-group">
                  <a href="https://storage.courtlistener.com/recap/order.pdf">
                    Download PDF
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _multi_entry_docket_html(
    *,
    title: str,
    entries: tuple[tuple[int, str, str], ...],
) -> str:
    rows = "".join(
        f"""
        <div class="row odd" id="entry-{number}">
          <div class="col-xs-1 text-center"><p>{number}</p></div>
          <div class="col-xs-3 col-sm-2">
            <p><span title="{filed_date}, 9:39 a.m.">{filed_date}</span></p>
          </div>
          <div class="col-xs-8 col-lg-7">
            <p>{text}</p>
            <div class="row recap-documents">
              <div class="col-xs-3"><p>Main Document</p></div>
              <div class="col-xs-6"><p>{text}</p></div>
              <a href="https://storage.courtlistener.com/recap/{number}.pdf">
                Download PDF
              </a>
            </div>
          </div>
        </div>
        """
        for number, filed_date, text in entries
    )
    return f"""
    <html><head><title>{title}</title></head><body>
      <a rel="next" class="btn btn-default disabled" href="#">Next</a>
      <div class="fake-table col-xs-12" id="docket-entry-table">{rows}</div>
    </body></html>
    """

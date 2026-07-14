from __future__ import annotations

from datetime import date

import pytest
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
from legalforecast.selection.motion_linkage import link_mtd_dispositions


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


def test_case_dev_metadata_screen_admits_adversary_caption_with_local_number() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000003",
            "courtId": "nysb",
            "court": "Bankruptcy Court, S.D. New York",
            "docketNumber": "26-01028",
            "caseName": "Higgins v. Celsius Network LLC",
        },
        query="order on motion to dismiss",
    )

    assert screen.accepted_for_scrape is True
    assert screen.metadata.case_type_stratum == "bankruptcy_adversary"


@pytest.mark.parametrize("designation", ("Adversary Proceeding", "Adversary Case"))
def test_case_dev_metadata_screen_admits_explicit_adversary_designation(
    designation: str,
) -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000007",
            "courtId": "nysb",
            "court": "Bankruptcy Court, S.D. New York",
            "docketNumber": "26-01030",
            "caseName": f"{designation} No. 26-01030",
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


def test_adversarial_caption_cannot_promote_explicit_bk_docket() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000004",
            "courtId": "flmb",
            "court": "Bankruptcy Court, M.D. Florida",
            "docketNumber": "8:26-bk-04258",
            "caseName": "Creditor LLC v. Robert Scott Super",
        },
        query="order on motion to dismiss case",
    )

    assert screen.accepted_for_scrape is False
    assert screen.exclusion_reasons[0] == "bankruptcy_court"


def test_adversary_designation_cannot_promote_explicit_bk_docket() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000008",
            "courtId": "flmb",
            "court": "Bankruptcy Court, M.D. Florida",
            "docketNumber": "8:26-bk-04258",
            "caseName": "Adversary Proceeding concerning Robert Scott Super",
        },
        query="order on motion to dismiss case",
    )

    assert screen.accepted_for_scrape is False
    assert screen.exclusion_reasons[0] == "bankruptcy_court"


def test_debtor_middle_initial_is_not_an_adversarial_caption() -> None:
    screen = screen_case_dev_docket_metadata(
        {
            "id": "74000006",
            "courtId": "nysb",
            "court": "Bankruptcy Court, S.D. New York",
            "docketNumber": "26-01029",
            "caseName": "In re David V. Reynolds",
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


def test_actual_mtd_decision_entry_accepts_singular_magistrate_recommendation() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "RECOMMENDATION of United States Magistrate Judge re 12 partial "
            "Motion to Dismiss. The Court recommends granting in part and "
            "denying in part the motion.",
            document_description="Main Document",
        ),
        source_url="https://www.courtlistener.com/docket/70873021/example/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_actual_mtd_decision_entry_accepts_substantive_rr_with_objection_order() -> (
    None
):
    page = parse_courtlistener_docket_html(
        _docket_html(
            "REPORT AND RECOMMENDATION re 18 Motion to Dismiss. The Court "
            "recommends that the motion be granted in part and denied in part. "
            "Objections must comply with the District Judge's Standing Order.",
            document_description="Main Document",
        ),
        source_url="https://www.courtlistener.com/docket/69942279/example/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_actual_mtd_decision_entry_accepts_explicit_court_minute_disposition() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "MINUTE (IN CHAMBERS) THE COURT GRANTS IN PART AND DENIES IN PART "
            "DEFENDANT'S MOTION TO DISMISS (DKT. #20).",
            document_description="Main Document",
        ),
        source_url="https://www.courtlistener.com/docket/72310061/example/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_actual_mtd_decision_entry_accepts_motion_by_party_syntax() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "MEMORANDUM OPINION AND ORDER: The 8 MOTION by Defendant Example LLC "
            "to Dismiss 1 Complaint is GRANTED IN PART and DENIED IN PART.",
            document_description="Main Document",
        ),
        source_url="https://www.courtlistener.com/docket/70450240/example/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_motion_by_party_syntax_survives_screening_linkage() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Example v. Defendant",
            entries=(
                (1, "January 2, 2026", "COMPLAINT filed by Plaintiff."),
                (
                    8,
                    "February 2, 2026",
                    "MOTION by Defendant Example LLC to Dismiss 1 Complaint.",
                ),
                (
                    21,
                    "July 9, 2026",
                    "MEMORANDUM OPINION AND ORDER: The 8 MOTION by Defendant "
                    "Example LLC to Dismiss 1 Complaint is GRANTED IN PART and "
                    "DENIED IN PART.",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/70450240/example/",
    )
    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={entry.row_id for entry in screen.decision_entries},
        docket_id="70450240",
        source_url=page.source_url or "",
    )

    assert screen.strict_clean is True
    assert [entry.document_role for entry in normalized] == [
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ]


def test_actual_mtd_decision_entry_rejects_procedural_order() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html("Standing Order governing motions to dismiss in this case."),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


def test_explicit_disposition_reference_selects_motion_over_support_appendix() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Plaintiff v. Defendant",
            entries=(
                (
                    24,
                    "December 5, 2025",
                    "MOTION to Dismiss Plaintiff's Complaint filed by Defendant "
                    "with Brief/Memorandum in Support. "
                    "(Attachments: # 1 Proposed Order)",
                ),
                (
                    25,
                    "December 5, 2025",
                    "Appendix in Support filed by Defendant re 24 MOTION to "
                    "Dismiss Plaintiff's Complaint.",
                ),
                (
                    31,
                    "July 9, 2026",
                    "MEMORANDUM OPINION AND ORDER granting Defendant's 24 Motion "
                    "to Dismiss.",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/70476447/example/",
    )
    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={entry.row_id for entry in screen.decision_entries},
        docket_id="70476447",
        source_url=page.source_url or "",
    )

    linkage = link_mtd_dispositions(
        normalized,
        candidate_id="70476447:entry-31",
        case_id="70476447",
    )

    assert screen.strict_clean is True
    assert linkage.is_clean is True
    assert linkage.links[0].motion_entry_ids == ("entry-24",)


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


def test_actual_mtd_decision_entry_rejects_show_cause_before_future_mtd_ruling() -> (
    None
):
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER by the Court DIRECTING Plaintiff TO SHOW CAUSE why Dkt. No. 9 "
            "Defendants' motion to dismiss should not be granted for failure to "
            "file a response. Plaintiff shall file a statement by July 20, 2026."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


def test_actual_mtd_decision_entry_rejects_conditional_amend_or_brief_order() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER re Motion to Dismiss. Plaintiff shall file any amended "
            "complaint by August 10, 2026. If Plaintiff amends, Defendants "
            "shall answer or file a new motion to dismiss, and the Court will "
            "deny the previously filed motion to dismiss as moot. If no "
            "amended complaint is filed, Plaintiff shall serve any opposition "
            "to the motion by August 10, 2026."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


def test_amendment_deadline_does_not_hide_present_mtd_grant() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting Defendant's Motion to Dismiss. Plaintiff shall "
            "file an amended complaint by August 10, 2026. If Plaintiff "
            "amends, Defendant shall respond or file a new motion to dismiss."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "entry_text",
    (
        "The Motion to Dismiss shall be granted if Plaintiff does not file "
        "an amended complaint by August 10, 2026.",
        "The Motion to Dismiss will be denied as moot upon filing of an "
        "amended complaint.",
    ),
)
def test_future_conditional_mtd_ruling_is_not_a_disposition(entry_text: str) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            entry_text,
            document_description="Order on Motion to Dismiss",
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


@pytest.mark.parametrize(
    "entry_text",
    (
        "Upon consideration of the briefs, Defendant's Motion to Dismiss is GRANTED.",
        "ORDER granting Defendant's Motion to Dismiss upon finding that the "
        "Complaint fails to state a claim.",
    ),
)
def test_completed_mtd_ruling_with_upon_is_retained(entry_text: str) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "entry_text",
    (
        "ORDER granting Defendant's Motion to Dismiss because, even if all "
        "allegations are accepted as true, the Complaint fails to state a claim.",
        "ORDER denying the Motion to Dismiss even if the Court assumes the "
        "disputed facts in Defendant's favor.",
    ),
)
def test_merits_reasoning_with_if_is_not_a_prospective_condition(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "entry_text",
    (
        (
            "ORDER: Plaintiffs' Unopposed Motion [Doc. 23] is GRANTED. "
            "Plaintiffs' deadline to respond to the pending Motion to Dismiss "
            "is extended through December 1, 2025."
        ),
        (
            "ORDER granting 18 Motion to Stay. All pretrial and discovery "
            "deadlines are STAYED pending resolution of the Motion to Dismiss."
        ),
        (
            "ORDER Granting 17 Motion to Stay Discovery. The parties shall file "
            "a discovery plan after entry of an order adjudicating defendant's "
            "5 Motion to Dismiss."
        ),
        (
            "ORDER granting motion for leave to exceed the page limit for the "
            "brief in support of the pending Motion to Dismiss."
        ),
        (
            "ORDER granting motion to expedite the briefing schedule on the "
            "pending Motion to Dismiss."
        ),
        (
            "ORDER granting Defendants' Motion to Exceed Page Limit for "
            "Defendants' Motion to Dismiss (Doc. 9). Defendants' Motion to "
            "Dismiss (Doc. 8) is considered within the page limit. IT IS "
            "FURTHER ORDERED granting the parties' Stipulation of Time to File "
            "Response to Motion to Dismiss (Doc. 13). Plaintiff's Response to "
            "Defendants' Motion to Dismiss (Doc. 8) shall be filed no later "
            "than July 17, 2026."
        ),
    ),
)
def test_actual_mtd_decision_entry_rejects_relief_about_pending_mtd(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text, document_description="Order"),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert "procedural_or_standing_order" in screen.exclusion_reasons


@pytest.mark.parametrize(
    "event_form",
    (
        "Order on Motion to Dismiss",
        "Order on Motion to Dismiss for Failure to State a Claim",
        "Order on Motion to Dismiss/Failure to State a Claim",
        "Order on Motion to Dismiss/Lack of Jurisdiction",
        "Order on Motion to Dismiss / Lack of Jurisdiction",
        "Order on Motion to Dismiss/General",
        "Order on Motion for Judgment on the Pleadings",
    ),
)
def test_exact_court_event_form_without_disposition_is_unproven(
    event_form: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            f"Main Document {event_form} Buy on PACER",
            document_description=event_form,
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert screen.exclusion_reasons == ("mtd_disposition_unproven",)


def test_exact_order_event_does_not_replace_dispositive_docket_text() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER filed by the Court re Motion to Dismiss.",
            document_description="Order on Motion to Dismiss",
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert screen.exclusion_reasons == ("mtd_disposition_unproven",)


@pytest.mark.parametrize(
    ("entry_text", "document_description", "expected_reason"),
    (
        (
            "Defendant filed a Motion to Dismiss.",
            "Motion to Dismiss",
            "motion_filing_only",
        ),
        (
            "Defendant filed a Motion to Dismiss.",
            "Order on Motion to Dismiss",
            "mtd_disposition_unproven",
        ),
        (
            "MOTION to Dismiss. Attachments: Proposed Order.",
            "Proposed Order on Motion to Dismiss",
            "proposed_order_not_decision",
        ),
        (
            "Standing Order governing motions to dismiss.",
            "Standing Order on Motions to Dismiss",
            "procedural_or_standing_order",
        ),
        (
            "Order setting the Motion to Dismiss briefing schedule.",
            "Order on Motion to Dismiss Briefing Schedule",
            "procedural_or_standing_order",
        ),
        (
            "Plaintiff's Motion to Dismiss this action voluntarily.",
            "Order on Motion to Dismiss",
            "self_or_voluntary_dismissal",
        ),
    ),
)
def test_actual_mtd_decision_entry_does_not_broaden_beyond_exact_event_forms(
    entry_text: str,
    document_description: str,
    expected_reason: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text, document_description=document_description),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False
    assert expected_reason in screen.exclusion_reasons


@pytest.mark.parametrize(
    "entry_text",
    (
        "ORDER granting 12 Motion to Dismiss.",
        "ORDER denying 12 Motion to Dismiss as moot.",
        "ORDER terminating 12 Motion to Dismiss as moot.",
        (
            "REPORT AND RECOMMENDATION re 12 Motion to Dismiss. The Court "
            "recommends that the motion be granted."
        ),
    ),
)
def test_actual_mtd_decision_entry_preserves_substantive_and_moot_dispositions(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "entry_text",
    (
        "ORDER: Defendant's Motion to Dismiss GRANTED.",
        "ORDER: Defendant's Motion to Dismiss DENIED AS MOOT.",
        "ORDER denying Defendant's Rule 12 motion.",
        "ORDER denying Defendant's Rule 12(b)(1) motion.",
        "ORDER denying Defendant's Rule 12(b)(2) motion.",
        "ORDER denying Defendant's Rule 12(b)(6) motion.",
        "ORDER denying Defendant's Rule 12(c) motion.",
        "MEMORANDUM AND ORDER denying Rule 12(c) judgment on the pleadings.",
        "ORDER denying Defendant's motion under Rule 12(b)(6).",
        "ORDER: Motion to Dismiss is moot.",
        "ORDER finding Motion to Dismiss moot.",
        "ORDER denying Motion to Stay and Motion to Dismiss.",
    ),
)
def test_actual_mtd_decision_entry_accepts_bare_and_rule_12_dispositions(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text, document_description="Order"),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "entry_text",
    (
        (
            "REPORT AND RECOMMENDATION re Motion to Dismiss. The Court "
            "recommends that plaintiff be granted an extension to respond."
        ),
        (
            "REPORT AND RECOMMENDATION re Motion to Dismiss. The Court "
            "recommends granting an extension to respond to the motion."
        ),
        (
            "ORDER: Motion to Dismiss briefing is terminated; an amended "
            "briefing schedule will follow."
        ),
    ),
)
def test_actual_mtd_decision_entry_rejects_target_first_procedural_relief(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(entry_text, document_description="Order"),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is False


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


def test_docket_screen_excludes_social_security_merits_jop() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "MEMORANDUM AND ORDER denying Plaintiff's Motion for Judgment on "
            "the Pleadings and affirming the decision of the Administrative "
            "Law Judge.",
            title="KARNS v. COMMISSIONER OF SOCIAL SECURITY",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/2/karns-v-commissioner/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.has_actual_mtd_decision is True
    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


@pytest.mark.parametrize(
    ("title", "entry_text", "document_description", "has_actual_disposition"),
    (
        (
            "GARCIA v. COMMISSIONER OF SOCIAL SECURITY, 2:24-cv-09276",
            "OPINION and ORDER denying 7 Motion for Judgment on the Pleadings.",
            "Order on Motion for Judgment on the Pleadings",
            True,
        ),
        (
            "GARCIA v. COMMISSIONER OF SOCIAL SECURITY, 2:24-cv-09276",
            "OPINION and ORDER denying 7 Motion for Judgment on Pleadings.",
            "Order on Motion for Judgment on Pleadings",
            True,
        ),
        (
            "Terranova v. Commissioner of Social Security, 2:24-cv-07794",
            "ORDER withdrawing 16 Motion for Judgment on the Pleadings without "
            "prejudice to refiling after the appearance of counsel.",
            "Order on Motion for Judgment on the Pleadings",
            False,
        ),
        (
            "Charles v. Commissioner of Social Security, 5:25-cv-00248",
            "Order (PUBLIC) AND Order on Motion for Judgment on the Pleadings "
            "AND Order on Report and Recommendations",
            "Order on Motion for Judgment on the Pleadings",
            False,
        ),
    ),
)
def test_named_social_security_caption_excludes_bare_jop_disposition(
    title: str,
    entry_text: str,
    document_description: str,
    has_actual_disposition: bool,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            entry_text,
            title=title,
            document_description=document_description,
        ),
        source_url="https://www.courtlistener.com/docket/2/ssa-merits-review/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.has_actual_mtd_decision is has_actual_disposition
    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


def test_social_security_agency_employment_jop_is_not_disability_review() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting Defendant's Motion for Judgment on the Pleadings "
            "on Plaintiff's Title VII employment discrimination claims.",
            title="DOE v. SOCIAL SECURITY ADMINISTRATION",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/2/ssa-employment/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.has_actual_mtd_decision is True
    assert screen.strict_clean is True
    assert "social_security_merits_review_posture" not in screen.exclusion_reasons


def test_unrelated_rule_12_row_does_not_clear_social_security_merits_jop() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="DOE v. COMMISSIONER OF SOCIAL SECURITY",
            entries=(
                (
                    3,
                    "June 1, 2026",
                    "ORDER denying an unrelated third-party Rule 12 motion to dismiss.",
                ),
                (
                    9,
                    "June 30, 2026",
                    "MEMORANDUM AND ORDER denying Plaintiff's Motion for Judgment "
                    "on the Pleadings and affirming the decision of the "
                    "Administrative Law Judge.",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/2/doe-v-commissioner/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.has_actual_mtd_decision is True
    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


def test_social_security_aliases_and_alj_abbreviation_remain_excluded() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER denying Claimant's Motion for Judgment on the Pleadings and "
            "affirming the ALJ.",
            title="DOE v. ACTING COMMISSIONER OF THE SSA",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/2/doe-v-commissioner/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


def test_surname_only_social_security_caption_uses_decision_row_signature() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting Plaintiff's Motion for Judgment on the Pleadings, "
            "reversing the Commissioner's final decision, and remanding for "
            "further administrative proceedings.",
            title="JANE D. v. BISIGNANO",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/2/jane-d-v-bisignano/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.has_actual_mtd_decision is True
    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


@pytest.mark.parametrize(
    "entry_text",
    (
        "ORDER granting Plaintiff's Motion for Judgment on the Pleadings, "
        "reversing the Commissioner's final decision, and remanding for "
        "further administrative proceedings.",
        "MEMORANDUM AND ORDER denying Plaintiff's Motion for Judgment on the "
        "Pleadings and affirming the ALJ's determination. The Commissioner's "
        "earlier motion to dismiss had been withdrawn.",
    ),
)
def test_ssa_merits_variants_lack_disposition_linked_rule_12_basis(
    entry_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            entry_text,
            title="DOE v. ACTING COMMISSIONER OF THE SSA",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/2/doe-v-commissioner/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.strict_clean is False
    assert "social_security_merits_review_posture" in screen.exclusion_reasons


def test_same_decision_rule_12_basis_retains_social_security_dismissal() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting the Commissioner's Rule 12(b)(1) Motion to Dismiss "
            "the Complaint for lack of jurisdiction over the ALJ appeal.",
            title="DOE v. COMMISSIONER OF SOCIAL SECURITY",
            document_description="Order on Motion to Dismiss/Lack of Jurisdiction",
        ),
        source_url="https://www.courtlistener.com/docket/2/doe-v-commissioner/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.strict_clean is True
    assert screen.exclusion_reasons == ()


def test_same_decision_rule_7012_basis_retains_adversary_jop() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title=("COMMISSIONER OF SOCIAL SECURITY v. DEBTOR LLC - 6:26-ap-00106"),
            entries=(
                (1, "June 1, 2026", "Adversary COMPLAINT filed."),
                (
                    4,
                    "June 3, 2026",
                    "MOTION for Judgment on the Pleadings under Bankruptcy Rule "
                    "7012 as to Count I.",
                ),
                (
                    8,
                    "June 30, 2026",
                    "ORDER granting the Commissioner's Bankruptcy Rule 7012 "
                    "Motion for Judgment on the Pleadings and dismissing Count I "
                    "of the ALJ-related Complaint.",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000001/commissioner-v-debtor/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


def test_docket_screen_retains_true_rule_12c_disposition() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting Defendant's Rule 12(c) Motion for Judgment on the "
            "Pleadings and dismissing Count I of the Complaint.",
            title="DOE v. ABC CORPORATION",
            document_description="Order on Motion for Judgment on the Pleadings",
        ),
        source_url="https://www.courtlistener.com/docket/3/doe-v-abc/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(page)

    assert screen.strict_clean is True
    assert screen.exclusion_reasons == ()


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


def test_docket_screen_treats_full_and_abbreviated_anchor_dates_identically() -> None:
    screens = []
    for filed_date in ("June 30, 2026", "Jun 30, 2026", "Jun. 30, 2026"):
        page = parse_courtlistener_docket_html(
            _multi_entry_docket_html(
                title="DOE v. ABC CORPORATION",
                entries=((12, filed_date, "ORDER granting 10 Motion to Dismiss."),),
            ),
            source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
        )
        screens.append(
            screen_courtlistener_docket_for_mtd_decision(
                page,
                decision_filed_on_or_after=date(2026, 6, 30),
            )
        )

    assert all(screen.strict_clean for screen in screens)
    assert all(screen.exclusion_reasons == () for screen in screens)


def test_abbreviated_date_does_not_promote_non_merits_orders() -> None:
    for entry_text, expected_reason in (
        (
            "Defendant's Motion to Dismiss or, in the alternative, Transfer "
            "is GRANTED in part. The Clerk shall transfer this action.",
            "transfer_only",
        ),
        (
            "Before the Court is Defendant's Motion to File Instanter Reply "
            "to Plaintiff's Opposition to Motion to Dismiss. The Court GRANTS "
            "Defendant leave to file his reply brief late.",
            "procedural_or_standing_order",
        ),
    ):
        page = parse_courtlistener_docket_html(
            _multi_entry_docket_html(
                title="DOE v. ABC CORPORATION",
                entries=((12, "Jul. 10, 2026", entry_text),),
            ),
            source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
        )

        screen = screen_courtlistener_docket_for_mtd_decision(
            page,
            decision_filed_on_or_after=date(2026, 6, 30),
        )

        assert screen.strict_clean is False
        assert expected_reason in screen.exclusion_reasons


def test_reply_leave_language_does_not_hide_mtd_merits_disposition() -> None:
    page = parse_courtlistener_docket_html(
        _docket_html(
            "ORDER granting leave to file a late reply and DENYING "
            "Defendant's Motion to Dismiss."
        ),
        source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def test_alternative_transfer_caption_does_not_hide_mtd_merits_grant() -> None:
    for outcome in ("The Motion to Dismiss is GRANTED.", "Dismissal is GRANTED."):
        page = parse_courtlistener_docket_html(
            _docket_html(
                "ORDER on Defendant's Motion to Dismiss or, in the alternative, "
                f"Transfer. {outcome}"
            ),
            source_url="https://www.courtlistener.com/docket/1/doe-v-abc/",
        )

        screen = screen_courtlistener_entry_for_mtd_decision(page.entries[0])

        assert screen.actual_mtd_decision is True
        assert screen.exclusion_reasons == ()


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


def test_docket_screen_accepts_adversary_caption_with_local_number() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Docket 26-01028",
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
        source_url="https://www.courtlistener.com/docket/73183894/higgins-v-celsius/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="nysb 26-01028 Higgins v. Celsius Network LLC",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


@pytest.mark.parametrize("designation", ("Adversary Proceeding", "Adversary Case"))
def test_docket_screen_accepts_explicit_adversary_designation(
    designation: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Docket 26-01030",
            entries=(
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (4, "July 3, 2026", f"Motion to Dismiss {designation}"),
                (
                    8,
                    "July 10, 2026",
                    "Memorandum Opinion and Order granting 4 Motion to Dismiss.",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000007/adversary-proceeding/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text=f"26-01030 {designation} No. 26-01030",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


@pytest.mark.parametrize(
    ("entries", "expected_reason"),
    (
        (
            (
                (4, "July 3, 2026", "Motion to Dismiss Adversary Proceeding"),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss."),
            ),
            "bankruptcy_adversary_initiating_pleading_unproven",
        ),
        (
            (
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (
                    4,
                    "July 3, 2026",
                    "Plaintiff's voluntary Motion to Dismiss Adversary Proceeding",
                ),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss."),
            ),
            "bankruptcy_adversary_rule_basis_unproven",
        ),
        (
            (
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (4, "July 3, 2026", "Motion to Dismiss Adversary Proceeding"),
            ),
            "motion_filing_only",
        ),
        (
            (
                (1, "June 1, 2026", "Adversary COMPLAINT filed."),
                (4, "June 3, 2026", "Motion to Dismiss Adversary Proceeding"),
                (8, "June 29, 2026", "ORDER granting 4 Motion to Dismiss."),
            ),
            "mtd_decision_outside_date_window",
        ),
    ),
)
def test_explicit_adversary_designation_retains_all_downstream_gates(
    entries: tuple[tuple[int, str, str], ...],
    expected_reason: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(title="Docket 26-01030", entries=entries),
        source_url="https://www.courtlistener.com/docket/74000007/adversary-proceeding/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="nysb 26-01030 Adversary Proceeding No. 26-01030",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is False
    assert expected_reason in screen.exclusion_reasons


def test_entry_only_adversary_designation_cannot_establish_identity() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Docket 26-01031",
            entries=(
                (1, "July 1, 2026", "COMPLAINT filed."),
                (4, "July 3, 2026", "Motion to Dismiss Adversary Proceeding"),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000009/debtor/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="nysb 26-01031 Debtor",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is False
    assert "bankruptcy_posture" in screen.exclusion_reasons


def test_rule_7012_entries_establish_bankruptcy_context_without_candidate_text() -> (
    None
):
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Higgins v. Celsius Network LLC - 26-01028",
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
        source_url="https://www.courtlistener.com/docket/73183894/higgins-v-celsius/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


def test_civil_docket_number_7012_does_not_create_bankruptcy_context() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Doe v. ABC Corporation - 1:26-cv-7012",
            entries=(
                (1, "July 1, 2026", "COMPLAINT filed."),
                (4, "July 3, 2026", "MOTION to Dismiss Count I."),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Count I."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/73183895/doe-v-abc/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="nysd 1:26-cv-7012 Doe v. ABC Corporation",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "district_civil"
    assert "bankruptcy_posture" not in screen.exclusion_reasons


@pytest.mark.parametrize(
    "motion_text",
    (
        "Motion, Dismiss Adversary Proceeding",
        "Motion to Dismiss the Adversary Complaint",
    ),
)
def test_docket_screen_accepts_explicit_adversary_mtd_without_rule_citation(
    motion_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Higgins v. Celsius Network LLC - 26-01028",
            entries=(
                (1, "April 10, 2026", "Complaint (fee)"),
                (2, "May 1, 2026", motion_text),
                (
                    12,
                    "July 6, 2026",
                    "Memorandum Opinion and Order, Signed on 7/6/2026, "
                    "Granting the Motion to Dismiss. (related document(s)2)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/73183894/higgins-v-celsius/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="nysb 26-01028 Higgins v. Celsius Network LLC",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


@pytest.mark.parametrize(
    "motion_text",
    (
        "Debtor's Motion to Dismiss Bankruptcy Case",
        "Administrative Motion to Close Adversary Proceeding",
        "Plaintiff's Voluntary Motion to Dismiss Adversary Proceeding",
        "Notice of Voluntary Dismissal of Adversary Proceeding",
    ),
)
def test_adversary_screen_does_not_promote_nonmerits_dismissals(
    motion_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-ap-00106",
            entries=(
                (1, "July 1, 2026", "Adversary COMPLAINT filed."),
                (4, "July 3, 2026", motion_text),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss."),
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


def test_explicit_adversary_mtd_still_requires_initiating_pleading() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-ap-00106",
            entries=(
                (4, "July 3, 2026", "Motion, Dismiss Adversary Proceeding"),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss."),
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
    assert (
        "bankruptcy_adversary_initiating_pleading_unproven" in screen.exclusion_reasons
    )


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


def test_docket_screen_does_not_treat_ordinary_b_suffix_tokens_as_bankruptcy() -> None:
    for token in ("Feb", "CAB", "JLB"):
        page = parse_courtlistener_docket_html(
            _multi_entry_docket_html(
                title=f"Doe v. {token} Corporation - 6:26-cv-00106",
                entries=(
                    (1, "July 1, 2026", "COMPLAINT filed."),
                    (4, "July 3, 2026", "MOTION to Dismiss Count I."),
                    (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Count I."),
                ),
            ),
            source_url=(
                "https://www.courtlistener.com/docket/74000003/"
                f"doe-v-{token.lower()}-corporation/"
            ),
        )

        screen = screen_courtlistener_docket_for_mtd_decision(
            page,
            candidate_text=f"Civil action assigned to Judge {token}.",
            decision_filed_on_or_after=date(2026, 6, 30),
        )

        assert screen.strict_clean is True, token
        assert screen.case_type_stratum == "district_civil", token
        assert "bankruptcy_posture" not in screen.exclusion_reasons, token


def test_docket_screen_still_recognizes_bankruptcy_court_identifier() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="In re Debtor - flmb 6:26-06489",
            entries=(
                (1, "July 1, 2026", "Voluntary Chapter 13 Petition."),
                (4, "July 3, 2026", "Trustee MOTION to Dismiss Case under Rule 12."),
                (8, "July 10, 2026", "ORDER granting 4 Motion to Dismiss Case."),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000004/in-re-debtor/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="flmb 6:26-06489",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is False
    assert "bankruptcy_posture" in screen.exclusion_reasons


def test_docket_screen_accepts_adv_marker_for_rule_7012_adversary() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant LLC - 6:26-adv-00107",
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
        source_url=(
            "https://www.courtlistener.com/docket/74000005/trustee-v-defendant/"
        ),
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="flmb 6:26-adv-00107 Trustee v. Defendant LLC",
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"


def test_adversary_linkage_promotes_explicit_adversary_dismissal_motion() -> None:
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

    assert [entry.document_role for entry in normalized] == [
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ]


def test_adversary_linkage_recovers_higgins_comma_form_from_exact_reference() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Higgins v. Celsius Network LLC - 26-01028",
            entries=(
                (1, "April 13, 2026", "Complaint (fee)"),
                (2, "May 15, 2026", "Motion, Dismiss Adversary Proceeding"),
                (
                    12,
                    "July 6, 2026",
                    "Memorandum Opinion and Order Granting the Motion to Dismiss. "
                    "(related document(s)2)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/73183894/higgins-v-celsius/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-12"},
        docket_id="73183894",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["2", "12"]
    assert [entry.document_role for entry in normalized] == [
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ]


def test_adversary_jop_does_not_promote_osborne_generic_motion_reference() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Osborne v. Moeinifar - 25-01237",
            entries=(
                (1, "June 27, 2025", "Complaint"),
                (
                    103,
                    "March 24, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (
                    170,
                    "July 6, 2026",
                    "Order Denying Motion for Judgment on the Pleadings and "
                    "Granting Dismissal of Counts IX through XV without "
                    "Prejudice. (Re: # 103)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/70652482/osborne-v-moeinifar/",
    )

    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="flsb 25-01237 Osborne v. Moeinifar",
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={entry.row_id for entry in screen.decision_entries},
        docket_id="70652482",
        source_url=page.source_url or "",
        case_type_stratum=screen.case_type_stratum,
    )

    assert screen.strict_clean is True
    assert screen.case_type_stratum == "bankruptcy_adversary"
    assert [entry.entry_number for entry in normalized] == ["170"]
    assert [entry.document_role for entry in normalized] == [DocumentRole.DECISION]


def test_adversary_jop_does_not_promote_ambiguous_generic_motion_references() -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (103, "July 2, 2026", "Miscellaneous Motion"),
                (104, "July 2, 2026", "Miscellaneous Motion"),
                (
                    170,
                    "July 6, 2026",
                    "Order Denying Motion for Judgment on the Pleadings as to "
                    "Count I. (Re: # 103 and # 104)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]
    assert [entry.document_role for entry in normalized] == [DocumentRole.DECISION]


def test_adversary_jop_does_not_assign_generic_reference_in_multi_motion_order() -> (
    None
):
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (
                    103,
                    "July 2, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (
                    170,
                    "July 6, 2026",
                    "Order Granting Motion for Judgment on the Pleadings as to "
                    "Count I and Denying Motion to Seal. (Re: # 103)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]
    assert [entry.document_role for entry in normalized] == [DocumentRole.DECISION]


@pytest.mark.parametrize(
    "secondary_relief",
    (
        "Granting Application to Seal",
        "Denying Request for Sanctions",
        "Overruling Objection to Claim",
        "Denying Petition for Compensation",
        "Granting Stay",
        "Awarding Sanctions",
        "Quashing Subpoena",
        "Granting Motion to Compel",
    ),
)
def test_adversary_jop_does_not_assign_generic_reference_for_secondary_relief(
    secondary_relief: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (
                    103,
                    "July 2, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (
                    170,
                    "July 6, 2026",
                    "Order Denying Motion for Judgment on the Pleadings and "
                    f"{secondary_relief}. (Re: # 103)",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]
    assert [entry.document_role for entry in normalized] == [DocumentRole.DECISION]


@pytest.mark.parametrize("uncoupled_reference", ("Attachment [103]", "Exhibit [103]"))
def test_adversary_jop_does_not_promote_uncoupled_bracket_number(
    uncoupled_reference: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (
                    103,
                    "July 2, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (
                    170,
                    "July 6, 2026",
                    "Order Denying Motion for Judgment on the Pleadings. "
                    f"{uncoupled_reference}",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]


@pytest.mark.parametrize(
    "decision_text",
    (
        "Order Granting Stay and Denying Motion for Judgment on the "
        "Pleadings. (Re: # 103)",
        "Order Awarding Sanctions; Denying Motion for Judgment on the "
        "Pleadings. (Re: # 103)",
        "Granting Stay before Order Denying Motion for Judgment on the "
        "Pleadings. (Re: # 103)",
    ),
)
def test_adversary_jop_does_not_promote_allowed_suffix_after_prior_relief(
    decision_text: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (
                    103,
                    "July 2, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (170, "July 6, 2026", decision_text),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]


@pytest.mark.parametrize(
    "trailing_relief",
    (
        "and Granting Stay",
        "and Awarding Sanctions",
        "and Quashing Subpoena",
    ),
)
def test_adversary_jop_does_not_promote_relief_after_relationship_annotation(
    trailing_relief: str,
) -> None:
    page = parse_courtlistener_docket_html(
        _multi_entry_docket_html(
            title="Trustee v. Defendant - 2:26-ap-00123",
            entries=(
                (1, "July 1, 2026", "Adversary Complaint"),
                (
                    103,
                    "July 2, 2026",
                    "Main Doc \xadument Miscellaneous Motion Buy on PACER",
                ),
                (
                    170,
                    "July 6, 2026",
                    "Order Denying Motion for Judgment on the Pleadings. "
                    f"(Re: # 103) {trailing_relief}",
                ),
            ),
        ),
        source_url="https://www.courtlistener.com/docket/74000123/trustee-v-defendant/",
    )

    normalized = _linkage_entries(
        page.entries,
        actual_decision_row_ids={"entry-170"},
        docket_id="74000123",
        source_url=page.source_url or "",
        case_type_stratum="bankruptcy_adversary",
    )

    assert [entry.entry_number for entry in normalized] == ["170"]


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

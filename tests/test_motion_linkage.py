from __future__ import annotations

from legalforecast.ingestion.docket_sync import (
    NormalizedDocketEntry,
    classify_document_role,
)
from legalforecast.selection.motion_linkage import (
    MotionLinkageExclusionReason,
    courtlistener_relationship_entry_numbers,
    link_mtd_dispositions,
    referenced_entry_numbers,
    referenced_mtd_entry_numbers,
)


def _entry(
    entry_number: int,
    text: str,
    *,
    entry_id: str | None = None,
    filed_at: str = "2026-05-14",
) -> NormalizedDocketEntry:
    return NormalizedDocketEntry(
        source_provider="case.dev",
        source_case_id="case-1",
        docket_entry_id=entry_id or f"entry-{entry_number}",
        entry_number=str(entry_number),
        entry_text=text,
        filed_at=filed_at,
        document_role=classify_document_role(text),
        source_document_ids=(f"doc-{entry_number}",),
        source_url=None,
    )


def test_links_single_mtd_to_written_order_by_entry_reference() -> None:
    result = link_mtd_dispositions(
        (
            _entry(12, "Motion to dismiss complaint"),
            _entry(35, "Order granting motion to dismiss at ECF No. 12"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-12",)
    assert result.links[0].disposition_entry_ids == ("entry-35",)
    assert result.links[0].linkage_basis == (
        "explicit_docket_entry_reference",
        "deterministic_earliest_eligible_target_motion",
    )


def test_selects_one_deterministic_target_when_order_resolves_multiple_mtds() -> None:
    result = link_mtd_dispositions(
        (
            _entry(
                20, "Defendant A motion to dismiss complaint", filed_at="2026-02-02"
            ),
            _entry(
                21,
                "Defendant B motion to dismiss amended complaint",
                filed_at="2026-02-01",
            ),
            _entry(
                50,
                "Opinion and order granting motions to dismiss at ECF Nos. 20 and 21",
            ),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-21",)
    assert result.links[0].disposition_entry_ids == ("entry-50",)


def test_target_motion_selector_breaks_same_date_tie_by_entry_number() -> None:
    result = link_mtd_dispositions(
        (
            _entry(21, "Defendant B motion to dismiss complaint"),
            _entry(20, "Defendant A motion to dismiss complaint"),
            _entry(50, "Order granting motions to dismiss at ECF Nos. 20 and 21"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.links[0].motion_entry_ids == ("entry-20",)


def test_mixed_mtd_preliminary_injunction_order_still_links_mtd_part() -> None:
    result = link_mtd_dispositions(
        (
            _entry(34, "Motion to dismiss complaint"),
            _entry(40, "Motion for preliminary injunction", entry_id="entry-pi"),
            _entry(
                55,
                "Order granting motion to dismiss at ECF No. 34 and denying "
                "preliminary injunction at ECF No. 40",
            ),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-34",)
    assert result.links[0].contains_non_mtd_relief is True
    assert "mixed_non_mtd_relief_preserved" in result.links[0].linkage_basis


def test_report_and_recommendation_adoption_path_links_both_dispositions() -> None:
    result = link_mtd_dispositions(
        (
            _entry(18, "Motion to dismiss under Rule 12(b)(6)"),
            _entry(
                42,
                "Report and recommendation recommending motion to dismiss be granted",
            ),
            _entry(47, "Order adopting report and recommendation"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-18",)
    assert result.links[0].disposition_entry_ids == ("entry-42", "entry-47")
    assert result.links[0].includes_report_and_recommendation is True
    assert "report_and_recommendation_adoption_path" in result.links[0].linkage_basis


def test_ambiguous_multiple_mtd_linkage_routes_to_exclusion_ledger() -> None:
    result = link_mtd_dispositions(
        (
            _entry(12, "Defendant A motion to dismiss complaint"),
            _entry(13, "Defendant B motion to dismiss complaint"),
            _entry(30, "Order granting motion to dismiss"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is False
    assert result.links == ()
    assert result.exclusion_entries[0].reason == (
        MotionLinkageExclusionReason.AMBIGUOUS_MOTION_TO_ORDER_LINKAGE.value
    )
    assert result.exclusion_entries[0].stage.value == "motion_linkage"
    assert result.exclusion_entries[0].source_entry_ids == (
        "entry-12",
        "entry-13",
        "entry-30",
    )


def test_support_memorandum_explicitly_linked_to_notice_is_not_second_motion() -> None:
    result = link_mtd_dispositions(
        (
            _entry(10, "Motion to dismiss for failure to state a claim"),
            _entry(
                11,
                "Memorandum in support of Motion to Dismiss for Failure to "
                "State a Claim 10",
            ),
            _entry(22, "Order on Motion to Dismiss for Failure to State a Claim"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-10",)
    assert result.links[0].disposition_entry_ids == ("entry-22",)


def test_case_number_does_not_link_support_memorandum_to_notice() -> None:
    result = link_mtd_dispositions(
        (
            _entry(10, "Motion to dismiss complaint"),
            _entry(
                11,
                "Memorandum in support of Motion to Dismiss; Civil Action No. 10-1234",
            ),
            _entry(22, "Order on Motion to Dismiss"),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert (
        referenced_mtd_entry_numbers("Motion to Dismiss in Civil Action No. 10-1234")
        == set()
    )
    assert result.is_clean is False
    assert result.exclusion_entries[0].reason == (
        MotionLinkageExclusionReason.AMBIGUOUS_MOTION_TO_ORDER_LINKAGE.value
    )


def test_referenced_entry_numbers_parses_courtlistener_related_document_form() -> None:
    assert referenced_entry_numbers(
        "Memorandum Opinion and Order Granting the Motion to Dismiss. "
        "(related document(s)2)"
    ) == {2}
    assert referenced_entry_numbers("Order (related document(s): 103)") == {103}


def test_courtlistener_relationship_parser_is_narrow_and_syntactically_coupled() -> (
    None
):
    assert courtlistener_relationship_entry_numbers(
        "Order (related document(s)106, 63)"
    ) == {63, 106}
    assert courtlistener_relationship_entry_numbers("Order (Re: # 103)") == {103}
    assert courtlistener_relationship_entry_numbers("Order (Re: #103 and # 104)") == {
        103,
        104,
    }
    assert courtlistener_relationship_entry_numbers("Attachment [103]") == set()
    assert courtlistener_relationship_entry_numbers("Exhibit [103]") == set()
    assert courtlistener_relationship_entry_numbers("Docket 103") == set()
    assert courtlistener_relationship_entry_numbers("Order (Re: #103-104)") == set()
    assert courtlistener_relationship_entry_numbers("Order (Re: #103/104)") == set()
    assert (
        courtlistener_relationship_entry_numbers("Order (related document(s)103-104)")
        == set()
    )
    assert (
        courtlistener_relationship_entry_numbers("Order (related document(s)103/104)")
        == set()
    )

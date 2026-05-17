from __future__ import annotations

from legalforecast.ingestion.docket_sync import (
    NormalizedDocketEntry,
    classify_document_role,
)
from legalforecast.selection.motion_linkage import (
    MotionLinkageExclusionReason,
    link_mtd_dispositions,
)


def _entry(
    entry_number: int,
    text: str,
    *,
    entry_id: str | None = None,
) -> NormalizedDocketEntry:
    return NormalizedDocketEntry(
        source_provider="case.dev",
        source_case_id="case-1",
        docket_entry_id=entry_id or f"entry-{entry_number}",
        entry_number=str(entry_number),
        entry_text=text,
        filed_at="2026-05-14",
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
    assert result.links[0].linkage_basis == ("explicit_docket_entry_reference",)


def test_links_multiple_mtds_resolved_together_by_one_order() -> None:
    result = link_mtd_dispositions(
        (
            _entry(20, "Defendant A motion to dismiss complaint"),
            _entry(21, "Defendant B motion to dismiss amended complaint"),
            _entry(
                50,
                "Opinion and order granting motions to dismiss at ECF Nos. 20 and 21",
            ),
        ),
        candidate_id="cand-1",
        case_id="case-1",
    )

    assert result.is_clean is True
    assert result.links[0].motion_entry_ids == ("entry-20", "entry-21")
    assert result.links[0].disposition_entry_ids == ("entry-50",)


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

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.courtlistener_acquisition import (
    _linkage_entries,
    screen_courtlistener_docket_html,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerDocket
from legalforecast.ingestion.courtlistener_web import CourtListenerWebDocketEntry
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_case_dev_docket_metadata,
    screen_courtlistener_entry_for_mtd_decision,
)
from legalforecast.selection.motion_linkage import link_mtd_dispositions

_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "courtlistener"
    / "bankruptcy-adversary-role-regressions.json"
)


def test_corbin_exact_reference_keeps_reply_out_of_target_motion_role() -> None:
    case = _case("corbin")
    entries = _entries(case)

    normalized = _linkage_entries(
        entries,
        actual_decision_row_ids={"entry-115"},
        docket_id="69533541",
        source_url="https://www.courtlistener.com/docket/69533541/corbin/",
        case_type_stratum="bankruptcy_adversary",
    )
    linkage = link_mtd_dispositions(
        normalized,
        candidate_id="69533541",
        case_id="courtlistener-docket-69533541",
    )

    assert linkage.is_clean is True
    assert linkage.links[0].motion_entry_ids == ("entry-77",)
    assert "entry-85" not in {
        entry.docket_entry_id
        for entry in normalized
        if entry.document_role.value == "motion_to_dismiss_notice"
    }


def test_corbin_full_screen_selects_actual_motion_and_decision() -> None:
    case = _case("corbin")

    screened, exclusion = _screen_case(case)

    assert exclusion is None
    assert screened is not None
    assert screened["ai"] == {
        "target_motion_entry_numbers": ["77"],
        "decision_entry_numbers": ["115"],
    }


def test_collins_bnc_mailing_is_not_a_written_disposition() -> None:
    case = _case("collins")
    entries = {entry.entry_number: entry for entry in _entries(case)}

    assert (
        screen_courtlistener_entry_for_mtd_decision(entries["231"]).actual_mtd_decision
        is True
    )
    mailing = screen_courtlistener_entry_for_mtd_decision(entries["243"])
    assert mailing.actual_mtd_decision is False
    assert mailing.exclusion_reasons == ("procedural_or_standing_order",)


def test_service_reference_after_actual_order_does_not_hide_disposition() -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-20",
        entry_number="20",
        filed_at="July 7, 2026",
        text=(
            "20 July 7, 2026 Order Denying Motion to Dismiss and Directing "
            "Certificate of Service be filed."
        ),
    )

    assert screen_courtlistener_entry_for_mtd_decision(entry).actual_mtd_decision


def test_response_phrase_inside_actual_motion_does_not_hide_target() -> None:
    entries = (
        CourtListenerWebDocketEntry(
            row_id="entry-10",
            entry_number="10",
            filed_at="May 1, 2026",
            text="Motion to Dismiss in Response to the Amended Complaint.",
        ),
        CourtListenerWebDocketEntry(
            row_id="entry-20",
            entry_number="20",
            filed_at="July 1, 2026",
            text="Order Denying Motion to Dismiss (related document(s)10).",
        ),
    )

    normalized = _linkage_entries(
        entries,
        actual_decision_row_ids={"entry-20"},
        docket_id="fixture",
        source_url="https://www.courtlistener.com/docket/1/fixture/",
    )

    assert [entry.entry_number for entry in normalized] == ["10", "20"]


def test_collins_missing_pre_motion_operative_complaint_fails_closed() -> None:
    case = _case("collins")
    screened, exclusion = _screen_case(case)

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "bankruptcy_adversary_initiating_pleading_unproven"
    assert exclusion.source_entry_ids == ("entry-188",)


def test_collins_complete_history_uses_pre_motion_complaint_and_only_order() -> None:
    case = _case("collins")
    complaint = {
        "entry_number": 102,
        "filed_at": "March 27, 2026, 10:00 a.m.",
        "text": (
            "Receiver's Second Amended Complaint filed by Royal B. Lea III "
            "for Plaintiff John Patrick Lowe. Main Document Amended Complaint"
        ),
    }

    screened, exclusion = _screen_case(case, extra_entries=(complaint,))

    assert exclusion is None
    assert screened is not None
    assert screened["ai"] == {
        "target_motion_entry_numbers": ["188"],
        "decision_entry_numbers": ["231"],
    }


def _screen_case(
    case: dict[str, Any],
    *,
    extra_entries: tuple[dict[str, Any], ...] = (),
) -> tuple[dict[str, Any] | None, Any]:
    docket_id = cast(str, case["docket_id"])
    case_name = cast(str, case["case_name"])
    docket_number = cast(str, case["docket_number"])
    court_id = cast(str, case["court_id"])
    case_id = f"courtlistener-docket-{docket_id}"
    source_url = f"https://www.courtlistener.com/docket/{docket_id}/fixture/"
    raw = {
        "case_id": case_id,
        "case_name": case_name,
        "court_id": court_id,
        "docket_number": docket_number,
        "date_filed": "2025-06-06",
        "case_type_stratum": "bankruptcy_adversary",
    }
    screened, exclusion = screen_courtlistener_docket_html(
        docket=CourtListenerDocket(
            docket_id=docket_id,
            court_id=court_id,
            docket_number=docket_number,
            case_name=case_name,
            date_filed="2025-06-06",
            source_url=source_url,
            raw=raw,
        ),
        metadata_screen=screen_case_dev_docket_metadata(raw),
        raw_html=_html(case, extra_entries=extra_entries),
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    return cast(dict[str, Any] | None, screened), exclusion


def _case(name: str) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(_FIXTURE.read_text(encoding="utf-8")))
    return next(
        cast(dict[str, Any], case)
        for case in cast(list[object], payload["cases"])
        if cast(dict[str, Any], case)["name"] == name
    )


def _entries(case: dict[str, Any]) -> tuple[CourtListenerWebDocketEntry, ...]:
    return tuple(
        CourtListenerWebDocketEntry(
            row_id=f"entry-{entry['entry_number']}",
            entry_number=str(entry["entry_number"]),
            filed_at=cast(str, entry["filed_at"]),
            text=cast(str, entry["text"]),
        )
        for entry in cast(list[dict[str, Any]], case["entries"])
    )


def _html(
    case: dict[str, Any],
    *,
    extra_entries: tuple[dict[str, Any], ...] = (),
) -> str:
    entries = (*extra_entries, *cast(list[dict[str, Any]], case["entries"]))
    rows = "".join(
        f"""
        <div class="row" id="entry-{entry["entry_number"]}">
          <div class="col-xs-1">{entry["entry_number"]}</div>
          <div class="col-xs-3"><span title="{entry["filed_at"]}">
            {entry["filed_at"]}
          </span></div>
          <div class="col-xs-8"><p>{entry["text"]}</p></div>
        </div>
        """
        for entry in entries
    )
    return (
        f"<html><head><title>{case['title']}</title></head><body>"
        f'<div id="docket-entry-table">{rows}</div></body></html>'
    )

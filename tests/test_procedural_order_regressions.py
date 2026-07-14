from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_courtlistener_entry_for_mtd_decision,
)

_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "courtlistener"
    / "procedural-order-regressions.json"
)


@pytest.mark.parametrize(
    "case_name",
    (
        "lageman",
        "shteerman",
        "wahl",
        "kepler",
        "coordinated_summary_judgment",
        "coordinated_mtd_jop",
    ),
)
def test_saved_orders_require_grammatically_proven_merits_disposition(
    case_name: str,
) -> None:
    record = _record(case_name)
    entry = _entry(record)

    screen = screen_courtlistener_entry_for_mtd_decision(entry)

    expected = cast(bool, record["expected_actual_mtd_decision"])
    assert screen.actual_mtd_decision is expected
    assert bool(screen.exclusion_reasons) is not expected


@pytest.mark.parametrize(
    "text",
    (
        "ORDER denying Defendant's Motion to Dismiss. IT IS FURTHER ORDERED "
        "granting leave to file an oversized reply brief.",
        "ORDER granting in part and denying in part the Motion for Judgment on "
        "the Pleadings and extending the deadline to amend the complaint.",
        "ORDER denying as moot 26 Motion for Judgment on the Pleadings.",
        "ORDER denying without prejudice Defendant's Motion to Dismiss.",
        "ORDER granting with prejudice Defendant's Motion to Dismiss.",
    ),
)
def test_actual_merits_disposition_survives_ancillary_procedural_relief(
    text: str,
) -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-positive",
        entry_number="100",
        filed_at="July 13, 2026",
        text=text,
    )

    screen = screen_courtlistener_entry_for_mtd_decision(entry)

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


@pytest.mark.parametrize(
    "text",
    (
        "ORDER granting Defendant's request for oral argument on the Motion "
        "to Dismiss.",
        "ORDER granting Plaintiff's request to supplement the record "
        "regarding Defendant's Motion to Dismiss.",
        "ORDER granting a hearing on Defendant's Motion to Dismiss.",
        "ORDER granting Motion by Defendant for leave to file late Motion to Dismiss.",
        "ORDER granting Motion by Defendant for an extension to respond to the "
        "Motion to Dismiss.",
        "ORDER: Motion by Defendant for leave to file late Motion to Dismiss "
        "is granted.",
    ),
)
def test_ancillary_request_is_not_the_disposition_object(text: str) -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-ancillary",
        entry_number="101",
        filed_at="July 13, 2026",
        text=text,
    )

    screen = screen_courtlistener_entry_for_mtd_decision(entry)

    assert screen.actual_mtd_decision is False
    assert screen.exclusion_reasons


def test_bounded_motion_by_party_disposition_remains_proven() -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-motion-by-party",
        entry_number="102",
        filed_at="July 13, 2026",
        text="ORDER: Motion by Defendant Smith to Dismiss is denied.",
    )

    screen = screen_courtlistener_entry_for_mtd_decision(entry)

    assert screen.actual_mtd_decision is True
    assert screen.exclusion_reasons == ()


def _record(name: str) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(_FIXTURE.read_text(encoding="utf-8")))
    return cast(
        dict[str, Any],
        next(record for record in payload["cases"] if record["name"] == name),
    )


def _entry(record: dict[str, Any]) -> CourtListenerWebDocketEntry:
    description = cast(str, record["document_description"])
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{record['entry_number']}",
        entry_number=cast(str, record["entry_number"]),
        filed_at=cast(str, record["filed_at"]),
        text=cast(str, record["text"]),
        documents=(
            CourtListenerWebDocument(
                kind="Main Document",
                description=description,
                href=f"https://example.test/{record['docket_id']}.pdf",
                action_label="Download PDF",
                pacer_only=False,
            ),
        ),
    )

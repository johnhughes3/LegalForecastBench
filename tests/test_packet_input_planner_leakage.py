from __future__ import annotations

from datetime import UTC, datetime

import pytest
from legalforecast.ingestion.courtlistener_web import CourtListenerWebDocketEntry
from legalforecast.ingestion.packet_input_planner import (
    PacketInputPlanningError,
    _docket_entries,
)


def test_packet_time_leakage_screen_excludes_adversarial_docket_entries() -> None:
    selection = _selection(decision_entry_numbers=[50])
    plan = _docket_entries(
        (
            CourtListenerWebDocketEntry(
                row_id="entry-20",
                entry_number="20",
                filed_at="May 2, 2026",
                text="Minute order granting the motion to dismiss after oral ruling.",
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-30",
                entry_number="30",
                filed_at="May 3, 2026",
                text=(
                    "Report and recommendation recommends granting defendants' "
                    "motion to dismiss."
                ),
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-40",
                entry_number="40",
                filed_at="May 4, 2026",
                text="Tentative ruling denies the motion to dismiss.",
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-50",
                entry_number="50",
                filed_at="May 5, 2026",
                text="Order deciding the motion to dismiss.",
            ),
        ),
        selection=selection,
        source_document_ids_by_entry={},
        generated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )

    leaky_entries = plan.entries[:3]
    assert all(not entry.model_visible for entry in leaky_entries)
    assert all(entry.contains_target_outcome for entry in leaky_entries)
    assert plan.exclusion_ledger_records
    assert plan.exclusion_ledger_records[0]["reason"] == "outcome_leakage"
    assert {
        "minute_order_resolving_target",
        "rr_already_resolving_target",
        "tentative_ruling_revealing_target",
    }.issubset(set(plan.exclusion_ledger_records[0]["secondary_exclusion_reasons"]))


def test_packet_docket_planning_rejects_missing_decision_entry_numbers() -> None:
    with pytest.raises(PacketInputPlanningError, match="decision_entry_numbers"):
        _docket_entries(
            (
                CourtListenerWebDocketEntry(
                    row_id="entry-1",
                    entry_number="1",
                    filed_at="May 1, 2026",
                    text="Complaint.",
                ),
            ),
            selection=_selection(decision_entry_numbers=[]),
            source_document_ids_by_entry={},
            generated_at=datetime(2026, 5, 6, tzinfo=UTC),
        )


def _selection(*, decision_entry_numbers: list[int]) -> dict[str, object]:
    return {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "decision_date": "2026-05-05",
        "decision_entry_numbers": decision_entry_numbers,
    }

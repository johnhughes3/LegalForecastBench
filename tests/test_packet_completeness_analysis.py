from __future__ import annotations

from scripts.analyze_packet_completeness import analyze_packet_completeness


def test_analysis_reports_both_yields_from_same_records() -> None:
    record = {
        "candidate": {
            "docket_id": "cand-1",
            "metadata": {"case_id": "case-1"},
        },
        "ai": {
            "target_motion_entry_numbers": [5],
            "decision_entry_numbers": [16],
        },
        "first_written_mtd_disposition_date": "2026-07-01",
        "selected_entries": [
            _entry(1, "Complaint", "Complaint"),
            _entry(5, "Motion to Dismiss", "Motion to Dismiss"),
            _entry(16, "Order on Motion to Dismiss", "Order"),
        ],
    }

    result = analyze_packet_completeness((record,))

    assert result["legacy_optional_opposition_bare_notice_yield"] == 1
    assert result["approved_conditional_opposition_memorandum_yield"] == 0


def _entry(number: int, text: str, description: str) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "Jul 1, 2026",
        "text": text,
        "documents": [
            {
                "description": description,
                "href": f"https://example.invalid/{number}.pdf",
                "action_label": "Download PDF",
                "pacer_only": False,
            }
        ],
    }

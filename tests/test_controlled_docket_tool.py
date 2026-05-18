from __future__ import annotations

import json

import pytest
from legalforecast.evals.tools import (
    ControlledDocketEntry,
    ControlledDocketTool,
    DocketToolDenialReason,
)


def test_controlled_docket_tool_reads_allowed_entries_and_logs_call() -> None:
    tool = _tool()

    result = tool.read_docket_entry(34)

    assert result.ok is True
    assert result.entry is not None
    assert result.entry.docket_text == "Defendant moves to dismiss Count I."
    assert tool.call_count == 1
    assert tool.call_logs[0].tool_name == "read_docket_entry"
    assert tool.call_logs[0].entry_number == 34
    assert tool.call_logs[0].status == "allowed"
    json.dumps(result.to_record())


def test_controlled_docket_tool_denies_forbidden_entries_without_content_leak() -> None:
    tool = _tool()

    result = tool.read_docket_entry(50)
    record = result.to_record()
    serialized = json.dumps(record)

    assert result.ok is False
    assert result.denial_reason is DocketToolDenialReason.ENTRY_NOT_ALLOWED
    assert record["entry"] is None
    assert "Motion granted in full" not in serialized
    assert tool.call_logs[0].denial_reason is DocketToolDenialReason.ENTRY_NOT_ALLOWED


def test_controlled_docket_tool_reports_missing_entries_without_content() -> None:
    tool = _tool()

    result = tool.read_docket_entry(99)

    assert result.ok is False
    assert result.denial_reason is DocketToolDenialReason.ENTRY_NOT_FOUND
    assert result.to_record()["entry"] is None


def test_controlled_docket_tool_enforces_call_cap_and_logs_denial() -> None:
    tool = _tool(max_tool_calls=1)

    first = tool.read_docket_entry(34)
    second = tool.read_docket_entry(41)

    assert first.ok is True
    assert second.ok is False
    assert second.denial_reason is DocketToolDenialReason.CALL_CAP_EXHAUSTED
    assert tool.call_count == 2
    assert tool.remaining_calls == 0
    assert tool.call_logs[1].denial_reason is (
        DocketToolDenialReason.CALL_CAP_EXHAUSTED
    )


def test_list_available_entries_exposes_only_allowed_entry_summaries() -> None:
    tool = _tool()

    result = tool.list_available_docket_entries()
    record = result.to_record()

    assert result.ok is True
    assert [entry["entry_number"] for entry in record["available_entries"]] == [34, 41]
    assert "docket_text" not in record["available_entries"][0]
    assert "Motion granted in full" not in json.dumps(record)


def test_allowed_list_cannot_include_unmounted_or_outcome_material() -> None:
    with pytest.raises(ValueError, match="post-decision"):
        ControlledDocketTool(
            case_id="case-1",
            entries=_entries(),
            allowed_entry_numbers=(34, 50),
            max_tool_calls=5,
        )


def _tool(*, max_tool_calls: int = 5) -> ControlledDocketTool:
    return ControlledDocketTool(
        case_id="case-1",
        entries=_entries(),
        allowed_entry_numbers=(34, 41),
        max_tool_calls=max_tool_calls,
    )


def _entries() -> tuple[ControlledDocketEntry, ...]:
    return (
        ControlledDocketEntry(
            entry_number=34,
            docket_text="Defendant moves to dismiss Count I.",
            description="Motion to dismiss",
            source_document_ids=("mtd-memo",),
        ),
        ControlledDocketEntry(
            entry_number=41,
            docket_text="Plaintiff opposes the motion to dismiss.",
            description="Opposition",
            source_document_ids=("opposition",),
        ),
        ControlledDocketEntry(
            entry_number=50,
            docket_text="Motion granted in full. Count I is dismissed.",
            description="Decision",
            source_document_ids=("decision",),
            is_predecision_material=False,
            contains_target_outcome=True,
            is_mounted_for_model=False,
        ),
    )

"""Controlled docket-entry read tools for model harnesses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DocketToolStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class DocketToolDenialReason(StrEnum):
    ENTRY_NOT_ALLOWED = "entry_not_allowed"
    ENTRY_NOT_FOUND = "entry_not_found"
    CALL_CAP_EXHAUSTED = "call_cap_exhausted"
    OUTCOME_OR_POST_DECISION_MATERIAL = "outcome_or_post_decision_material"


@dataclass(frozen=True, slots=True)
class ControlledDocketEntry:
    """One docket entry known to the controlled tool."""

    entry_number: int
    docket_text: str
    source_document_ids: tuple[str, ...] = ()
    description: str | None = None
    is_predecision_material: bool = True
    contains_target_outcome: bool = False
    is_mounted_for_model: bool = True

    def __post_init__(self) -> None:
        _require_positive(self.entry_number, "entry_number")
        _require_non_empty(self.docket_text, "docket_text")
        for source_document_id in self.source_document_ids:
            _require_non_empty(source_document_id, "source_document_ids")
        if self.description is not None:
            _require_non_empty(self.description, "description")

    @property
    def is_readable(self) -> bool:
        return (
            self.is_predecision_material
            and not self.contains_target_outcome
            and self.is_mounted_for_model
        )

    def to_read_record(self) -> dict[str, Any]:
        return {
            "entry_number": self.entry_number,
            "docket_text": self.docket_text,
            "source_document_ids": list(self.source_document_ids),
            "description": self.description,
        }

    def to_list_record(self) -> dict[str, Any]:
        return {
            "entry_number": self.entry_number,
            "source_document_ids": list(self.source_document_ids),
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class DocketToolCallLog:
    """Audit log record for one controlled docket-tool call."""

    case_id: str
    tool_name: str
    status: DocketToolStatus
    call_index: int
    entry_number: int | None = None
    denial_reason: DocketToolDenialReason | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.tool_name, "tool_name")
        _require_positive(self.call_index, "call_index")
        if self.entry_number is not None:
            _require_positive(self.entry_number, "entry_number")
        if self.status is DocketToolStatus.DENIED and self.denial_reason is None:
            raise ValueError("denied tool calls require denial_reason")
        if self.status is DocketToolStatus.ALLOWED and self.denial_reason is not None:
            raise ValueError("allowed tool calls must not set denial_reason")

    def to_record(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "call_index": self.call_index,
            "entry_number": self.entry_number,
            "denial_reason": (
                self.denial_reason.value if self.denial_reason is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class DocketToolResult:
    """Structured result returned to the harness for one tool call."""

    status: DocketToolStatus
    call_log: DocketToolCallLog
    entry: ControlledDocketEntry | None = None
    available_entries: tuple[ControlledDocketEntry, ...] = ()
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status is DocketToolStatus.ALLOWED:
            if self.call_log.status is not DocketToolStatus.ALLOWED:
                raise ValueError("allowed results require allowed call log")
            if self.entry is None and not self.available_entries:
                raise ValueError("allowed results require entry or available_entries")
        else:
            if self.call_log.status is not DocketToolStatus.DENIED:
                raise ValueError("denied results require denied call log")
            if self.entry is not None or self.available_entries:
                raise ValueError("denied results must not expose entries")

    @property
    def ok(self) -> bool:
        return self.status is DocketToolStatus.ALLOWED

    @property
    def denial_reason(self) -> DocketToolDenialReason | None:
        return self.call_log.denial_reason

    def to_record(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status.value,
            "entry": self.entry.to_read_record() if self.entry is not None else None,
            "available_entries": [
                entry.to_list_record() for entry in self.available_entries
            ],
            "message": self.message,
            "call_log": self.call_log.to_record(),
        }


class ControlledDocketTool:
    """Per-case docket read tool with allow-listing, caps, and audit logs."""

    def __init__(
        self,
        *,
        case_id: str,
        entries: tuple[ControlledDocketEntry, ...],
        allowed_entry_numbers: tuple[int, ...],
        max_tool_calls: int,
    ) -> None:
        _require_non_empty(case_id, "case_id")
        _require_positive(max_tool_calls, "max_tool_calls")
        self.case_id = case_id
        self.max_tool_calls = max_tool_calls
        self._entries = _index_entries(entries)
        self._allowed_entry_numbers = frozenset(allowed_entry_numbers)
        self._logs: list[DocketToolCallLog] = []
        self._validate_allow_list()

    @property
    def call_logs(self) -> tuple[DocketToolCallLog, ...]:
        return tuple(self._logs)

    @property
    def call_count(self) -> int:
        return len(self._logs)

    @property
    def remaining_calls(self) -> int:
        return max(self.max_tool_calls - self.call_count, 0)

    def read_docket_entry(self, entry_number: int) -> DocketToolResult:
        _require_positive(entry_number, "entry_number")
        cap_result = self._deny_if_cap_exhausted(
            "read_docket_entry",
            entry_number=entry_number,
        )
        if cap_result is not None:
            return cap_result

        entry = self._entries.get(entry_number)
        if entry is None:
            return self._deny(
                "read_docket_entry",
                entry_number=entry_number,
                reason=DocketToolDenialReason.ENTRY_NOT_FOUND,
                message="Docket entry is not available to this case packet.",
            )
        if entry_number not in self._allowed_entry_numbers:
            return self._deny(
                "read_docket_entry",
                entry_number=entry_number,
                reason=DocketToolDenialReason.ENTRY_NOT_ALLOWED,
                message="Docket entry is outside the per-case allowed-entry list.",
            )
        if not entry.is_readable:
            return self._deny(
                "read_docket_entry",
                entry_number=entry_number,
                reason=DocketToolDenialReason.OUTCOME_OR_POST_DECISION_MATERIAL,
                message="Docket entry is not pre-decision model-visible material.",
            )

        log = self._append_log(
            tool_name="read_docket_entry",
            status=DocketToolStatus.ALLOWED,
            entry_number=entry_number,
            denial_reason=None,
        )
        return DocketToolResult(
            status=DocketToolStatus.ALLOWED,
            call_log=log,
            entry=entry,
        )

    def list_available_docket_entries(self) -> DocketToolResult:
        cap_result = self._deny_if_cap_exhausted(
            "list_available_docket_entries",
            entry_number=None,
        )
        if cap_result is not None:
            return cap_result

        entries = tuple(
            self._entries[entry_number]
            for entry_number in sorted(self._allowed_entry_numbers)
        )
        log = self._append_log(
            tool_name="list_available_docket_entries",
            status=DocketToolStatus.ALLOWED,
            entry_number=None,
            denial_reason=None,
        )
        return DocketToolResult(
            status=DocketToolStatus.ALLOWED,
            call_log=log,
            available_entries=entries,
        )

    def call_log_records(self) -> list[dict[str, Any]]:
        return [log.to_record() for log in self.call_logs]

    def _validate_allow_list(self) -> None:
        for entry_number in self._allowed_entry_numbers:
            entry = self._entries.get(entry_number)
            if entry is None:
                raise ValueError(
                    f"allowed_entry_numbers contains missing entry: {entry_number}"
                )
            if not entry.is_readable:
                raise ValueError(
                    "allowed_entry_numbers must not include post-decision, "
                    f"outcome, or unmounted material: {entry_number}"
                )

    def _deny_if_cap_exhausted(
        self,
        tool_name: str,
        *,
        entry_number: int | None,
    ) -> DocketToolResult | None:
        if self.call_count < self.max_tool_calls:
            return None
        return self._deny(
            tool_name,
            entry_number=entry_number,
            reason=DocketToolDenialReason.CALL_CAP_EXHAUSTED,
            message="Docket tool-call cap exhausted.",
        )

    def _deny(
        self,
        tool_name: str,
        *,
        entry_number: int | None,
        reason: DocketToolDenialReason,
        message: str,
    ) -> DocketToolResult:
        log = self._append_log(
            tool_name=tool_name,
            status=DocketToolStatus.DENIED,
            entry_number=entry_number,
            denial_reason=reason,
        )
        return DocketToolResult(
            status=DocketToolStatus.DENIED,
            call_log=log,
            message=message,
        )

    def _append_log(
        self,
        *,
        tool_name: str,
        status: DocketToolStatus,
        entry_number: int | None,
        denial_reason: DocketToolDenialReason | None,
    ) -> DocketToolCallLog:
        log = DocketToolCallLog(
            case_id=self.case_id,
            tool_name=tool_name,
            status=status,
            call_index=len(self._logs) + 1,
            entry_number=entry_number,
            denial_reason=denial_reason,
        )
        self._logs.append(log)
        return log


def _index_entries(
    entries: tuple[ControlledDocketEntry, ...],
) -> dict[int, ControlledDocketEntry]:
    indexed: dict[int, ControlledDocketEntry] = {}
    for entry in entries:
        if entry.entry_number in indexed:
            raise ValueError(f"duplicate docket entry number: {entry.entry_number}")
        indexed[entry.entry_number] = entry
    return indexed


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")

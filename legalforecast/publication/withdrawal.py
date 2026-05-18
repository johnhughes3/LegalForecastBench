"""Withdrawal ledgers and public errata records for official cycles."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast._hashing import is_sha256_digest

WITHDRAWAL_LEDGER_SCHEMA_VERSION = "legalforecast-withdrawal-ledger-v1"
PUBLIC_ERRATA_SCHEMA_VERSION = "legalforecast-withdrawal-errata-v1"


class WithdrawalScope(StrEnum):
    """Type of benchmark material affected by a withdrawal."""

    CASE = "case"
    DOCUMENT = "document"
    PACKET = "packet"
    PUBLIC_ARTIFACT = "public_artifact"


class WithdrawalReason(StrEnum):
    """Suggested public reason codes for withdrawn material."""

    SEALED_OR_RESTRICTED = "sealed_or_restricted"
    COURT_TAKEDOWN = "court_takedown"
    SENSITIVE_PARTY_CONCERN = "sensitive_party_concern"
    SOURCE_TERMS_REVIEW = "source_terms_review"
    CORRECTION = "correction"


@dataclass(frozen=True, slots=True)
class WithdrawalLedgerEntry:
    """One durable private record that blocks future use of affected material."""

    withdrawal_id: str
    cycle_id: str
    scope: WithdrawalScope
    reason: str
    public_reason: str
    effective_at: datetime
    case_id: str | None = None
    candidate_id: str | None = None
    source_document_ids: tuple[str, ...] = ()
    packet_object_keys: tuple[str, ...] = ()
    public_artifact_paths: tuple[str, ...] = ()
    private_tombstone_key: str | None = None
    errata_path: str | None = None
    supersedes_manifest_sha256: str | None = None
    replacement_manifest_sha256: str | None = None
    score_bundle_superseded: bool = False
    future_use_blocked: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.withdrawal_id, "withdrawal_id")
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_non_empty(self.reason, "reason")
        _require_non_empty(self.public_reason, "public_reason")
        _require_aware_datetime(self.effective_at, "effective_at")
        if not self.future_use_blocked:
            raise ValueError("withdrawal entries must block future use")
        if self.case_id is not None:
            _require_non_empty(self.case_id, "case_id")
        if self.candidate_id is not None:
            _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty_values(self.source_document_ids, "source_document_ids")
        _require_non_empty_values(self.packet_object_keys, "packet_object_keys")
        _require_non_empty_values(self.public_artifact_paths, "public_artifact_paths")
        for key in self.packet_object_keys:
            _require_prefixed_safe_path(
                key, "packet_object_keys", allowed_prefixes=("model-packets/",)
            )
        for path in self.public_artifact_paths:
            _require_safe_path(path, "public_artifact_paths")
        if self.private_tombstone_key is not None:
            _require_prefixed_safe_path(
                self.private_tombstone_key,
                "private_tombstone_key",
                allowed_prefixes=("withdrawn/", "quarantine/"),
            )
        if self.errata_path is not None:
            _require_prefixed_safe_path(
                self.errata_path,
                "errata_path",
                allowed_prefixes=("manifests/", "reports/"),
            )
        _require_sha256_or_none(
            self.supersedes_manifest_sha256, "supersedes_manifest_sha256"
        )
        _require_sha256_or_none(
            self.replacement_manifest_sha256, "replacement_manifest_sha256"
        )
        if self.scope is WithdrawalScope.CASE and self.case_id is None:
            raise ValueError("case withdrawals require case_id")
        if self.scope is WithdrawalScope.DOCUMENT and not self.source_document_ids:
            raise ValueError("document withdrawals require source_document_ids")
        if self.scope is WithdrawalScope.PACKET and not self.packet_object_keys:
            raise ValueError("packet withdrawals require packet_object_keys")
        if (
            self.scope is WithdrawalScope.PUBLIC_ARTIFACT
            and not self.public_artifact_paths
        ):
            raise ValueError(
                "public artifact withdrawals require public_artifact_paths"
            )

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> WithdrawalLedgerEntry:
        """Parse a ledger entry record loaded from JSONL."""

        schema_version = _required_str(record.get("schema_version"), "schema_version")
        if schema_version != WITHDRAWAL_LEDGER_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported withdrawal ledger schema_version: {schema_version}"
            )
        return cls(
            withdrawal_id=_required_str(record.get("withdrawal_id"), "withdrawal_id"),
            cycle_id=_required_str(record.get("cycle_id"), "cycle_id"),
            scope=WithdrawalScope(_required_str(record.get("scope"), "scope")),
            reason=_required_str(record.get("reason"), "reason"),
            public_reason=_required_str(record.get("public_reason"), "public_reason"),
            effective_at=_parse_datetime(record.get("effective_at"), "effective_at"),
            case_id=_optional_str(record.get("case_id"), "case_id"),
            candidate_id=_optional_str(record.get("candidate_id"), "candidate_id"),
            source_document_ids=_optional_str_tuple(
                record.get("source_document_ids"), "source_document_ids"
            ),
            packet_object_keys=_optional_str_tuple(
                record.get("packet_object_keys"), "packet_object_keys"
            ),
            public_artifact_paths=_optional_str_tuple(
                record.get("public_artifact_paths"), "public_artifact_paths"
            ),
            private_tombstone_key=_optional_str(
                record.get("private_tombstone_key"), "private_tombstone_key"
            ),
            errata_path=_optional_str(record.get("errata_path"), "errata_path"),
            supersedes_manifest_sha256=_optional_str(
                record.get("supersedes_manifest_sha256"),
                "supersedes_manifest_sha256",
            ),
            replacement_manifest_sha256=_optional_str(
                record.get("replacement_manifest_sha256"),
                "replacement_manifest_sha256",
            ),
            score_bundle_superseded=_optional_bool(
                record.get("score_bundle_superseded"), "score_bundle_superseded"
            ),
            future_use_blocked=_optional_bool(
                record.get("future_use_blocked"), "future_use_blocked", default=True
            ),
        )

    def to_record(self) -> dict[str, object]:
        """Return the private JSONL ledger representation."""

        return {
            "schema_version": WITHDRAWAL_LEDGER_SCHEMA_VERSION,
            "withdrawal_id": self.withdrawal_id,
            "cycle_id": self.cycle_id,
            "scope": self.scope.value,
            "reason": self.reason,
            "public_reason": self.public_reason,
            "effective_at": _format_datetime(self.effective_at),
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "source_document_ids": list(self.source_document_ids),
            "packet_object_keys": list(self.packet_object_keys),
            "public_artifact_paths": list(self.public_artifact_paths),
            "private_tombstone_key": self.private_tombstone_key,
            "errata_path": self.errata_path,
            "supersedes_manifest_sha256": self.supersedes_manifest_sha256,
            "replacement_manifest_sha256": self.replacement_manifest_sha256,
            "score_bundle_superseded": self.score_bundle_superseded,
            "future_use_blocked": self.future_use_blocked,
        }

    def blocks_run_input(self, record: Mapping[str, object]) -> bool:
        """Return whether this withdrawal should remove a matrix input row."""

        case_id = _optional_str(record.get("case_id"), "case_id")
        candidate_id = _optional_str(record.get("candidate_id"), "candidate_id")
        packet_key = _first_optional_str(
            record,
            ("packet_object_key", "packet_key", "model_packet_key"),
        )
        source_document_ids = _optional_str_tuple(
            record.get("source_document_ids"), "source_document_ids"
        )
        return (
            (self.case_id is not None and self.case_id == case_id)
            or (self.candidate_id is not None and self.candidate_id == candidate_id)
            or (packet_key is not None and packet_key in set(self.packet_object_keys))
            or bool(set(source_document_ids).intersection(self.source_document_ids))
        )


@dataclass(frozen=True, slots=True)
class WithdrawalLedger:
    """Private withdrawal ledger consumed before official run matrix creation."""

    entries: tuple[WithdrawalLedgerEntry, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.withdrawal_id in seen:
                raise ValueError("withdrawal_id values must be unique")
            seen.add(entry.withdrawal_id)

    def add(self, entry: WithdrawalLedgerEntry) -> WithdrawalLedger:
        return WithdrawalLedger((*self.entries, entry))

    def blocks_run_input(self, record: Mapping[str, object]) -> bool:
        return any(entry.blocks_run_input(record) for entry in self.entries)

    def filter_run_inputs(
        self, records: Iterable[Mapping[str, object]]
    ) -> list[dict[str, object]]:
        """Remove withdrawn cases, documents, and packet rows from run inputs."""

        return [dict(record) for record in records if not self.blocks_run_input(record)]

    def to_records(self) -> list[dict[str, object]]:
        return [entry.to_record() for entry in self.entries]

    def to_jsonl(self) -> str:
        return "\n".join(
            json.dumps(record, sort_keys=True) for record in self.to_records()
        )

    def write_jsonl(self, path: str | Path) -> Path:
        output_path = Path(path)
        payload = self.to_jsonl()
        if payload:
            payload = f"{payload}\n"
        output_path.write_text(payload, encoding="utf-8")
        return output_path


def load_withdrawal_ledger(path: str | Path) -> WithdrawalLedger:
    """Load and validate a private withdrawal ledger JSONL file."""

    ledger_path = Path(path)
    entries: list[WithdrawalLedgerEntry] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw_record: object = json.loads(line)
            if not isinstance(raw_record, dict):
                raise ValueError(f"withdrawal ledger line {line_number} is not object")
            entries.append(
                WithdrawalLedgerEntry.from_record(
                    cast(Mapping[str, object], raw_record)
                )
            )
    return WithdrawalLedger(tuple(entries))


def filter_withdrawn_run_inputs(
    records: Iterable[Mapping[str, object]], ledger: WithdrawalLedger
) -> list[dict[str, object]]:
    """Convenience wrapper for removing withdrawn matrix rows."""

    return ledger.filter_run_inputs(records)


def build_public_errata_record(
    entry: WithdrawalLedgerEntry,
    *,
    issued_at: datetime,
    summary: str,
) -> dict[str, object]:
    """Build the non-sensitive errata record suitable for public artifacts."""

    _require_aware_datetime(issued_at, "issued_at")
    _require_non_empty(summary, "summary")
    return {
        "schema_version": PUBLIC_ERRATA_SCHEMA_VERSION,
        "withdrawal_id": entry.withdrawal_id,
        "cycle_id": entry.cycle_id,
        "scope": entry.scope.value,
        "case_id": entry.case_id,
        "candidate_id": entry.candidate_id,
        "reason": entry.reason,
        "public_reason": entry.public_reason,
        "summary": summary,
        "effective_at": _format_datetime(entry.effective_at),
        "issued_at": _format_datetime(issued_at),
        "errata_path": entry.errata_path,
        "supersedes_manifest_sha256": entry.supersedes_manifest_sha256,
        "replacement_manifest_sha256": entry.replacement_manifest_sha256,
        "score_bundle_superseded": entry.score_bundle_superseded,
        "future_use_blocked": entry.future_use_blocked,
    }


def _format_datetime(value: datetime) -> str:
    return format_utc_iso_z(value)


def _parse_datetime(value: object, field_name: str) -> datetime:
    text = _required_str(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO 8601 datetime") from exc
    _require_aware_datetime(parsed, field_name)
    return parsed


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _required_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    _require_non_empty(value, field_name)
    return value


def _optional_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    _require_non_empty(value, field_name)
    return value


def _optional_bool(value: object, field_name: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    values: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain strings")
        _require_non_empty(item, field_name)
        values.append(item)
    return tuple(values)


def _first_optional_str(
    record: Mapping[str, object], field_names: tuple[str, ...]
) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if value is not None:
            return _optional_str(value, field_name)
    return None


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_empty_values(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_non_empty(value, field_name)


def _require_safe_path(value: str, field_name: str) -> None:
    if value.startswith("/") or "\\" in value:
        raise ValueError(f"{field_name} must be a relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        raise ValueError(f"{field_name} must not contain unsafe path components")


def _require_prefixed_safe_path(
    value: str, field_name: str, *, allowed_prefixes: tuple[str, ...]
) -> None:
    _require_safe_path(value, field_name)
    if not value.startswith(allowed_prefixes):
        allowed = ", ".join(allowed_prefixes)
        raise ValueError(f"{field_name} must start with one of: {allowed}")


def _require_sha256_or_none(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not is_sha256_digest(value, allow_prefix=True):
        raise ValueError(f"{field_name} must be a sha256 digest")

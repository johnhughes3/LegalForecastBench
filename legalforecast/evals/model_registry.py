"""Model registry and run-matrix schema for benchmark evaluations."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast.selection import ModelRunMetadata, TrainingCutoffStatus


class ToolPolicy(StrEnum):
    NO_TOOLS = "no_tools"
    CONTROLLED_DOCKET_TOOL_ONLY = "controlled_docket_tool_only"


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    """One frozen model/run configuration used by all benchmark components."""

    provider: str
    model_id: str
    display_name: str
    model_version_or_snapshot: str
    provider_training_cutoff_status: TrainingCutoffStatus
    temperature: float
    top_p: float
    max_output_tokens: int
    network_disabled: bool
    search_disabled: bool
    tool_policy: ToolPolicy
    context_limit: int
    pricing_source: str
    input_token_price: float
    output_token_price: float
    release_timestamp: datetime | None = None
    provider_training_cutoff: date | None = None
    known_cutoff_publicity_caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, "provider")
        _require_non_empty(self.model_id, "model_id")
        _require_non_empty(self.display_name, "display_name")
        _require_non_empty(self.model_version_or_snapshot, "model_version_or_snapshot")
        _require_non_empty(self.pricing_source, "pricing_source")

        if self.release_timestamp is not None:
            _require_aware(self.release_timestamp, "release_timestamp")
        if self.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN:
            if self.provider_training_cutoff is None:
                raise ValueError(
                    "provider_training_cutoff is required when cutoff status is known"
                )
        elif self.provider_training_cutoff is not None:
            raise ValueError(
                "provider_training_cutoff must be omitted unless cutoff status is known"
            )

        _require_non_negative(self.temperature, "temperature")
        _require_between(self.top_p, "top_p", lower=0, upper=1)
        _require_positive_int(self.max_output_tokens, "max_output_tokens")
        _require_positive_int(self.context_limit, "context_limit")
        _require_non_negative(self.input_token_price, "input_token_price")
        _require_non_negative(self.output_token_price, "output_token_price")

    @property
    def registry_key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    def to_model_run_metadata(self, evaluation_timestamp: datetime) -> ModelRunMetadata:
        return ModelRunMetadata(
            provider=self.provider,
            model_name=self.model_id,
            model_version_or_snapshot=self.model_version_or_snapshot,
            evaluation_timestamp=evaluation_timestamp,
            network_disabled=self.network_disabled,
            search_disabled=self.search_disabled,
            provider_training_cutoff_status=self.provider_training_cutoff_status,
            provider_training_cutoff=self.provider_training_cutoff,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "model_version_or_snapshot": self.model_version_or_snapshot,
            "release_timestamp": (
                _iso_datetime(self.release_timestamp)
                if self.release_timestamp is not None
                else None
            ),
            "provider_training_cutoff_status": (
                self.provider_training_cutoff_status.value
            ),
            "provider_training_cutoff": (
                self.provider_training_cutoff.isoformat()
                if self.provider_training_cutoff is not None
                else None
            ),
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
            "network_disabled": self.network_disabled,
            "search_disabled": self.search_disabled,
            "tool_policy": self.tool_policy.value,
            "context_limit": self.context_limit,
            "pricing_source": self.pricing_source,
            "input_token_price": self.input_token_price,
            "output_token_price": self.output_token_price,
            "known_cutoff_publicity_caveats": list(self.known_cutoff_publicity_caveats),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ModelRegistryEntry:
        return cls(
            provider=_required_str(record, "provider"),
            model_id=_required_str(record, "model_id"),
            display_name=_required_str(record, "display_name"),
            model_version_or_snapshot=_required_str(
                record, "model_version_or_snapshot"
            ),
            release_timestamp=_optional_datetime(record, "release_timestamp"),
            provider_training_cutoff_status=TrainingCutoffStatus(
                _required_str(record, "provider_training_cutoff_status")
            ),
            provider_training_cutoff=_optional_date(record, "provider_training_cutoff"),
            temperature=_required_number(record, "temperature"),
            top_p=_required_number(record, "top_p"),
            max_output_tokens=_required_int(record, "max_output_tokens"),
            network_disabled=_required_bool(record, "network_disabled"),
            search_disabled=_required_bool(record, "search_disabled"),
            tool_policy=ToolPolicy(_required_str(record, "tool_policy")),
            context_limit=_required_int(record, "context_limit"),
            pricing_source=_required_str(record, "pricing_source"),
            input_token_price=_required_number(record, "input_token_price"),
            output_token_price=_required_number(record, "output_token_price"),
            known_cutoff_publicity_caveats=_optional_string_tuple(
                record, "known_cutoff_publicity_caveats"
            ),
        )


@dataclass(frozen=True, slots=True)
class ModelRegistry:
    """Validated collection of frozen model registry entries."""

    entries: tuple[ModelRegistryEntry, ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("model registry must contain at least one entry")
        seen: set[str] = set()
        duplicates: set[str] = set()
        for entry in self.entries:
            if entry.registry_key in seen:
                duplicates.add(entry.registry_key)
            seen.add(entry.registry_key)
        if duplicates:
            raise ValueError(f"duplicate model registry entries: {sorted(duplicates)}")

    def get(self, provider: str, model_id: str) -> ModelRegistryEntry:
        registry_key = f"{provider}:{model_id}"
        for entry in self.entries:
            if entry.registry_key == registry_key:
                return entry
        raise KeyError(registry_key)

    def to_records(self) -> list[dict[str, Any]]:
        return [entry.to_record() for entry in self.entries]

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, Any]]) -> ModelRegistry:
        return cls(tuple(ModelRegistryEntry.from_record(record) for record in records))


def latest_release_timestamp(entries: Sequence[ModelRegistryEntry]) -> datetime:
    """Return the latest release timestamp for an official evaluated model set."""

    if not entries:
        raise ValueError("at least one model registry entry is required")
    missing = sorted(
        entry.registry_key for entry in entries if entry.release_timestamp is None
    )
    if missing:
        raise ValueError(
            "official runs require release_timestamp for every model registry entry: "
            f"{missing}"
        )
    timestamps = tuple(
        entry.release_timestamp
        for entry in entries
        if entry.release_timestamp is not None
    )
    return max(timestamps)


def earliest_buffered_decision_date(entries: Sequence[ModelRegistryEntry]) -> date:
    """Return the first allowed decision date after the release-anchor buffer."""

    latest_release = latest_release_timestamp(entries)
    return latest_release.astimezone(UTC).date() + timedelta(days=2)


def require_official_registry_entries(
    entries: Sequence[ModelRegistryEntry],
) -> tuple[ModelRegistryEntry, ...]:
    """Fail closed unless registry entries are anchored for official evaluation."""

    latest_release_timestamp(entries)
    mutable_aliases = sorted(
        entry.registry_key
        for entry in entries
        if entry.model_version_or_snapshot == entry.model_id
        and any(marker in entry.model_id.lower() for marker in ("preview", "latest"))
    )
    if mutable_aliases:
        raise ValueError(
            "official runs require pinned dated snapshots, not mutable aliases: "
            f"{mutable_aliases}"
        )
    return tuple(entries)


def load_model_registry(path: str | Path) -> ModelRegistry:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw_records: object = json.load(handle)
    if not isinstance(raw_records, list):
        raise ValueError("model registry file must contain a JSON array")
    return ModelRegistry.from_records(_mapping_records(cast(list[object], raw_records)))


def dump_model_registry(registry: ModelRegistry, path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(registry.to_records(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _mapping_records(records: Iterable[object]) -> tuple[Mapping[str, Any], ...]:
    mapping_records: list[Mapping[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"model registry record {index} must be an object")
        mapping_records.append(cast(Mapping[str, Any], record))
    return tuple(mapping_records)


def _required(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in record:
        raise ValueError(f"{field_name} is required")
    return record[field_name]


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _required(record, field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = _required(record, field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = _required(record, field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _required_number(record: Mapping[str, Any], field_name: str) -> float:
    value = _required(record, field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _optional_datetime(record: Mapping[str, Any], field_name: str) -> datetime | None:
    value = record.get(field_name)
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO timestamp")
    return _parse_datetime(value, field_name)


def _optional_date(record: Mapping[str, Any], field_name: str) -> date | None:
    value = record.get(field_name)
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date")
    return date.fromisoformat(value)


def _optional_string_tuple(
    record: Mapping[str, Any], field_name: str
) -> tuple[str, ...]:
    value = record.get(field_name)
    if value is None or value == "":
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of non-empty strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise ValueError(f"{field_name} must be a list of non-empty strings")
    return tuple(cast(list[str], items))


def _parse_datetime(value: str, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _require_aware(parsed, field_name)


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _require_non_negative(value: float, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_between(
    value: float, field_name: str, *, lower: float, upper: float
) -> None:
    if value < lower or value > upper:
        raise ValueError(f"{field_name} must be between {lower} and {upper}")

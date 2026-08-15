"""Load, write, and check the reviewed architecture baseline."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import cast

from legalforecast.testing.architecture_rules.cli_compatibility import (
    UPWARD_IMPORT_ALLOWLIST,
    CliMetrics,
    CompatibilityInventory,
)
from legalforecast.testing.architecture_rules.inventory import (
    OVERSIZED_LINE_THRESHOLD,
    WATCH_LINE_THRESHOLD,
    DirectoryRecord,
    FileInventoryRecord,
    RepositoryInventory,
    is_reviewed_inventory_record,
    requires_manual_disposition,
    scan_repository,
)

DIRECTORY_REVIEW_FLOOR = 20


def load_baseline(path: Path) -> RepositoryInventory:
    """Load and validate a checked-in architecture snapshot."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("architecture baseline must be a JSON object")
    payload = cast(dict[str, object], raw)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported architecture baseline schema")
    metrics = _dataclass_from_mapping(CliMetrics, payload, "cli_metrics")
    compatibility = _dataclass_from_mapping(
        CompatibilityInventory, payload, "compatibility"
    )
    upward = _string_tuple(payload, "upward_cli_dependencies")
    inventory_raw = payload.get("inventory")
    files, directories, cycles = _load_inventory_section(inventory_raw)
    return RepositoryInventory(
        cli_metrics=metrics,
        upward_cli_dependencies=upward,
        compatibility=compatibility,
        files=files,
        directories=directories,
        cycles=cycles,
    )


def write_baseline(path: Path, snapshot: RepositoryInventory) -> None:
    """Write a normalized reviewed snapshot."""

    reviewed_files = [
        record for record in snapshot.files if is_reviewed_inventory_record(record)
    ]
    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(snapshot.cli_metrics),
        "upward_cli_dependencies": list(snapshot.upward_cli_dependencies),
        "compatibility": asdict(snapshot.compatibility),
        "inventory": {
            "cycles": [list(component) for component in snapshot.cycles],
            "directories": {
                record.path: record.python_file_count for record in snapshot.directories
            },
            "files": {
                record.path: {
                    "cycle_id": record.cycle_id,
                    "disposition_kind": record.disposition_kind,
                    "disposition_owner": record.disposition_owner,
                    "fan_in": record.fan_in,
                    "fan_out": record.fan_out,
                    "flags": list(record.flags),
                    "lane_owner": record.lane_owner,
                    "largest_symbol": record.largest_symbol,
                    "largest_symbol_lines": record.largest_symbol_lines,
                    "layer": record.layer,
                    "line_count": record.line_count,
                    "nonblank_line_count": record.nonblank_line_count,
                    "top_level_definition_count": record.top_level_definition_count,
                }
                for record in reviewed_files
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_baseline(root: Path, baseline_path: Path | None = None) -> tuple[str, ...]:
    """Return reviewed architecture-ratchet violations, if any."""

    resolved_root = root.resolve()
    path = baseline_path or Path("legalforecast/testing/architecture_baseline.json")
    baseline = load_baseline(path if path.is_absolute() else resolved_root / path)
    current = scan_repository(resolved_root)
    violations: list[str] = []
    violations.extend(_cli_metric_violations(current, baseline))
    violations.extend(_upward_violations(current, baseline))
    violations.extend(_compatibility_violations(current, baseline))
    violations.extend(_inventory_violations(current, baseline))
    return tuple(violations)


def _cli_metric_violations(
    current: RepositoryInventory, baseline: RepositoryInventory
) -> list[str]:
    violations: list[str] = []
    baseline_metrics = baseline.cli_metrics
    current_metrics = current.cli_metrics
    for field in (
        "line_count",
        "nonblank_line_count",
        "top_level_definition_count",
        "top_level_class_count",
        "parser_line_count",
        "command_handler_count",
        "command_handler_lines",
        "verifier_family_count",
        "verifier_family_lines",
    ):
        observed = getattr(current_metrics, field)
        allowed = getattr(baseline_metrics, field)
        if observed > allowed:
            violations.append(f"cli_metrics.{field}: {observed} > reviewed {allowed}")
        elif observed < allowed:
            violations.append(
                f"stale cli_metrics.{field} must be reduced: "
                f"reviewed {allowed} > observed {observed}"
            )
    return violations


def _upward_violations(
    current: RepositoryInventory, baseline: RepositoryInventory
) -> list[str]:
    violations: list[str] = []
    unexpected_upward = sorted(
        set(current.upward_cli_dependencies) - set(baseline.upward_cli_dependencies)
    )
    if unexpected_upward:
        violations.append(
            "new upward CLI dependencies: " + ", ".join(unexpected_upward)
        )
    stale_upward = sorted(
        set(baseline.upward_cli_dependencies) - set(current.upward_cli_dependencies)
    )
    if stale_upward:
        violations.append(
            "stale upward CLI dependencies must be removed: " + ", ".join(stale_upward)
        )
    unexpected_allowlist = sorted(
        set(current.upward_cli_dependencies) - UPWARD_IMPORT_ALLOWLIST
    )
    if unexpected_allowlist:
        violations.append(
            "upward CLI dependency outside the upward-import allowlist: "
            + ", ".join(unexpected_allowlist)
        )
    return violations


def _compatibility_violations(
    current: RepositoryInventory, baseline: RepositoryInventory
) -> list[str]:
    violations: list[str] = []
    current_compat = current.compatibility
    baseline_compat = baseline.compatibility
    for field in (
        "cli_import_files",
        "private_cli_files",
        "private_cli_targets",
        "public_cli_files",
        "public_cli_targets",
        "monkeypatch_targets",
    ):
        observed = set(getattr(current_compat, field))
        allowed = set(getattr(baseline_compat, field))
        additions = sorted(observed - allowed)
        if additions:
            violations.append(f"new compatibility.{field}: {', '.join(additions)}")
        removals = sorted(allowed - observed)
        if removals:
            violations.append(
                f"stale compatibility.{field} must be removed: {', '.join(removals)}"
            )
    for field in (
        "cli_import_occurrences",
        "private_cli_occurrences",
        "public_cli_occurrences",
        "monkeypatch_occurrences",
    ):
        observed = Counter(cast(tuple[str, ...], getattr(current_compat, field)))
        allowed = Counter(cast(tuple[str, ...], getattr(baseline_compat, field)))
        additions = sorted((observed - allowed).elements())
        if additions:
            violations.append(f"new compatibility.{field}: {', '.join(additions)}")
        removals = sorted((allowed - observed).elements())
        if removals:
            violations.append(
                f"stale compatibility.{field} must be removed: {', '.join(removals)}"
            )
    return violations


def _inventory_violations(
    current: RepositoryInventory, baseline: RepositoryInventory
) -> list[str]:
    if not baseline.files and not baseline.directories:
        return []
    violations: list[str] = []
    current_by_path = {record.path: record for record in current.files}
    baseline_by_path = {record.path: record for record in baseline.files}
    for path, observed in sorted(current_by_path.items()):
        if not is_reviewed_inventory_record(observed):
            continue
        reviewed = baseline_by_path.get(path)
        if reviewed is None:
            violations.append(
                f"new inventory file {path} ({observed.line_count} lines, "
                f"lane={observed.lane_owner}) is absent from the reviewed inventory"
            )
            continue
        if not observed.lane_owner:
            violations.append(f"inventory file {path} has no package-lane owner")
        if (
            reviewed.line_count >= OVERSIZED_LINE_THRESHOLD
            and observed.line_count > reviewed.line_count
        ):
            violations.append(
                f"inventory {path} line_count: {observed.line_count} > "
                f"reviewed {reviewed.line_count}"
            )
        elif (
            reviewed.line_count < OVERSIZED_LINE_THRESHOLD
            and observed.line_count >= OVERSIZED_LINE_THRESHOLD
        ):
            violations.append(
                f"inventory {path} grew from watch-tier {reviewed.line_count} "
                f"to oversized {observed.line_count} without a manual disposition"
            )
        if (
            reviewed.largest_symbol_lines >= 400
            and observed.largest_symbol_lines > reviewed.largest_symbol_lines
        ):
            violations.append(
                f"inventory {path} largest_symbol_lines: "
                f"{observed.largest_symbol_lines} > reviewed "
                f"{reviewed.largest_symbol_lines}"
            )
        elif (
            reviewed.largest_symbol_lines < 400 and observed.largest_symbol_lines >= 400
        ):
            violations.append(
                f"inventory {path} largest symbol {observed.largest_symbol} "
                f"grew to {observed.largest_symbol_lines} lines without disposition"
            )
        if requires_manual_disposition(
            line_count=observed.line_count,
            largest_symbol_lines=observed.largest_symbol_lines,
            flags=observed.flags,
        ) and observed.disposition_kind in {"watch", "below-watch"}:
            violations.append(
                f"inventory {path} requires a manual disposition "
                f"(kind={observed.disposition_kind})"
            )
        added_flags = sorted(set(observed.flags) - set(reviewed.flags))
        if added_flags:
            violations.append(f"inventory {path} new flags: {', '.join(added_flags)}")
        removed_flags = sorted(set(reviewed.flags) - set(observed.flags))
        if removed_flags:
            violations.append(
                f"inventory {path} stale flags must be removed: "
                f"{', '.join(removed_flags)}"
            )
    for path, reviewed in sorted(baseline_by_path.items()):
        observed = current_by_path.get(path)
        if observed is None:
            violations.append(f"stale inventory entry must be removed: {path}")
            continue
        if (
            observed.line_count < WATCH_LINE_THRESHOLD
            and not observed.flags
            and reviewed.disposition_kind == "watch"
        ):
            violations.append(
                f"stale inventory entry must be removed after shrink: {path}"
            )
    current_directories = {
        record.path: record.python_file_count for record in current.directories
    }
    reviewed_directories = {record.path for record in baseline.directories}
    for reviewed in baseline.directories:
        observed_count = current_directories.get(reviewed.path, 0)
        ceiling = max(DIRECTORY_REVIEW_FLOOR, reviewed.python_file_count)
        if observed_count > ceiling:
            violations.append(
                f"directory {reviewed.path} python_file_count: {observed_count} > "
                f"reviewed ceiling {ceiling}"
            )
    for path, observed_count in sorted(current_directories.items()):
        if path in reviewed_directories or observed_count <= DIRECTORY_REVIEW_FLOOR:
            continue
        violations.append(
            f"directory {path} python_file_count: {observed_count} > "
            f"reviewed ceiling {DIRECTORY_REVIEW_FLOOR}"
        )
    unexpected_cycles = [
        ",".join(component)
        for component in current.cycles
        if component not in set(baseline.cycles)
    ]
    if unexpected_cycles:
        violations.append("new import cycles: " + "; ".join(unexpected_cycles))
    stale_cycles = [
        ",".join(component)
        for component in baseline.cycles
        if component not in set(current.cycles)
    ]
    if stale_cycles:
        violations.append(
            "stale import cycles must be removed: " + "; ".join(stale_cycles)
        )
    return violations


def _load_inventory_section(
    inventory_raw: object,
) -> tuple[
    tuple[FileInventoryRecord, ...],
    tuple[DirectoryRecord, ...],
    tuple[tuple[str, ...], ...],
]:
    if inventory_raw is None:
        return (), (), ()
    if not isinstance(inventory_raw, dict):
        raise ValueError("architecture baseline inventory must be an object")
    payload = cast(dict[str, object], inventory_raw)
    files_raw = payload.get("files", {})
    if not isinstance(files_raw, dict):
        raise ValueError("architecture baseline inventory.files must be an object")
    files: list[FileInventoryRecord] = []
    for path, record_raw in sorted(cast(dict[str, object], files_raw).items()):
        if not isinstance(record_raw, dict):
            raise ValueError(
                f"architecture baseline inventory.files.{path} must be an object"
            )
        record = cast(dict[str, object], record_raw)
        files.append(
            FileInventoryRecord(
                path=path,
                line_count=_int_field(record, "line_count"),
                nonblank_line_count=_int_field(record, "nonblank_line_count"),
                top_level_definition_count=_int_field(
                    record, "top_level_definition_count"
                ),
                largest_symbol=_str_field(record, "largest_symbol"),
                largest_symbol_lines=_int_field(record, "largest_symbol_lines"),
                lane_owner=_str_field(record, "lane_owner"),
                layer=_str_field(record, "layer"),
                fan_in=_int_field(record, "fan_in"),
                fan_out=_int_field(record, "fan_out"),
                cycle_id=_str_field(record, "cycle_id"),
                churn_90d=(
                    _int_field(record, "churn_90d") if "churn_90d" in record else 0
                ),
                flags=_string_tuple(record, "flags") if "flags" in record else (),
                disposition_kind=_str_field(record, "disposition_kind"),
                disposition_owner=_str_field(record, "disposition_owner"),
            )
        )
    directories_raw = payload.get("directories", {})
    if not isinstance(directories_raw, dict):
        raise ValueError(
            "architecture baseline inventory.directories must be an object"
        )
    directories = tuple(
        DirectoryRecord(path=directory, python_file_count=_as_int(count, directory))
        for directory, count in sorted(cast(dict[str, object], directories_raw).items())
    )
    cycles_raw = payload.get("cycles", [])
    if not isinstance(cycles_raw, list):
        raise ValueError("architecture baseline inventory.cycles must be a list")
    cycles = tuple(
        _string_list(component, "cycles")
        for component in cast(list[object], cycles_raw)
    )
    return tuple(files), directories, cycles


def _dataclass_from_mapping[T](
    cls: type[T], payload: Mapping[str, object], field: str
) -> T:
    raw = payload.get(field)
    if not isinstance(raw, dict):
        raise ValueError(f"architecture baseline field {field} must be an object")
    normalized = cast(dict[str, object], raw).copy()
    for name, value in tuple(normalized.items()):
        if isinstance(value, list):
            values = cast(list[object], value)
            if not all(isinstance(item, str) for item in values):
                raise ValueError(
                    f"architecture baseline field {field}.{name} must be a string list"
                )
            normalized[name] = tuple(cast(list[str], values))
    try:
        return cls(**normalized)
    except TypeError as exc:
        raise ValueError(f"invalid architecture baseline field {field}") from exc


def _string_tuple(payload: Mapping[str, object], field: str) -> tuple[str, ...]:
    raw = payload.get(field)
    if not isinstance(raw, list):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    values = cast(list[object], raw)
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    return tuple(cast(list[str], values))


def _string_list(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    values = cast(list[object], raw)
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    return tuple(cast(list[str], values))


def _int_field(payload: Mapping[str, object], field: str) -> int:
    raw = payload.get(field)
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"architecture baseline field {field} must be an integer")
    return raw


def _str_field(payload: Mapping[str, object], field: str) -> str:
    raw = payload.get(field)
    if not isinstance(raw, str):
        raise ValueError(f"architecture baseline field {field} must be a string")
    return raw


def _as_int(raw: object, field: str) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"architecture baseline field {field} must be an integer")
    return raw

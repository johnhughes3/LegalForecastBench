"""The ``legalforecast study report`` command adapter.

The study service owns validation, strict scoring, and inference.  This module
only translates the two public JSON inputs into validated public artifact
objects and serializes the resulting report.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast import cli_support as _cli_support
from legalforecast.evals.model_registry import load_model_registry_bytes
from legalforecast.immutable_io import read_single_link_file
from legalforecast.release import (
    load_run_manifest,
    validate_release,
)
from legalforecast.studies.models import StudyArmInput, StudySpec
from legalforecast.studies.service import evaluate_study

_ARM_CONTAINER_KEYS = frozenset({"arms", "arm_inputs"})
_COMMON_INPUT_KEYS = frozenset({"artifact_root", "schema_version"})
_ARM_INPUT_KEYS = frozenset(
    {
        "artifact_root",
        "base_rate",
        "expected_model_registry_sha256",
        "forecast",
        "forecast_release",
        "forecast_release_path",
        "labels",
        "labels_release",
        "labels_release_path",
        "manifest",
        "manifest_path",
        "model_registry",
        "model_registry_path",
        "registry",
        "run_records",
        "run_records_path",
        "runs",
    }
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register the study report command on the root parser."""

    study = subparsers.add_parser(
        "study",
        help="Compute reproducible evaluation-study reports from public artifacts.",
    )
    commands = study.add_subparsers(dest="study_command", metavar="COMMAND")
    report = commands.add_parser(
        "report",
        help="Evaluate a frozen study specification and write its JSON report.",
        description=(
            "Read a StudySpec JSON and an arm-to-artifact JSON mapping. "
            "The mapping may omit an arm or set run_records to null for a "
            "typed missing-arm observation."
        ),
    )
    report.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Frozen public study specification JSON.",
    )
    report.add_argument(
        "--inputs",
        type=Path,
        required=True,
        help=(
            "JSON object mapping arm IDs to forecast, labels, manifest, registry, "
            "and optional run-record paths."
        ),
    )
    report.add_argument(
        "--artifact-root",
        type=Path,
        help=(
            "Default root for paths referenced by each release. An arm-level "
            "artifact_root takes precedence; otherwise the forecast directory "
            "is used."
        ),
    )
    report.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON report.",
    )
    report.add_argument(
        "--json",
        action="store_true",
        help="Emit the stable JSON report (the default output format).",
    )
    report.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Load public study inputs, evaluate them, and write one JSON report."""

    spec_path = cast(Path, args.spec)
    inputs_path = cast(Path, args.inputs)
    output_path = cast(Path, args.output)
    spec = StudySpec.model_validate(
        _json_sequences_to_tuples(
            _read_json_object(spec_path, label="study specification")
        )
    )
    input_payload = _read_json_object(inputs_path, label="study inputs")
    arm_inputs = _load_arm_inputs(
        input_payload,
        spec=spec,
        inputs_path=inputs_path,
        default_artifact_root=cast(Path | None, args.artifact_root),
    )
    report = evaluate_study(spec, arm_inputs=arm_inputs)
    _cli_support.write_json(output_path, report.to_record())
    _cli_support.log_event(
        "study",
        "artifact_written",
        output_path,
        len(report.comparisons),
    )
    return 0


def _load_arm_inputs(
    payload: Mapping[str, Any],
    *,
    spec: StudySpec,
    inputs_path: Path,
    default_artifact_root: Path | None,
) -> dict[str, StudyArmInput]:
    """Capture and validate the public artifacts listed by an inputs object."""

    arm_records, payload_artifact_root = _arm_records(payload)
    effective_default_root = default_artifact_root
    if effective_default_root is None and payload_artifact_root is not None:
        effective_default_root = _resolve_path(payload_artifact_root, inputs_path)

    known_arm_ids = {arm.arm_id for arm in spec.arms}
    unknown_arm_ids = sorted(set(arm_records) - known_arm_ids)
    if unknown_arm_ids:
        raise ValueError(
            "study inputs contain unknown arm IDs: " + ", ".join(unknown_arm_ids)
        )

    result: dict[str, StudyArmInput] = {}
    for arm_id, raw_record in arm_records.items():
        if raw_record is None:
            # A null mapping is an explicit, durable missing-arm declaration.
            continue
        if not isinstance(raw_record, Mapping):
            raise ValueError(
                f"study input for arm {arm_id!r} must be an object or null"
            )
        if _is_explicit_missing_arm(cast(Mapping[str, Any], raw_record)):
            continue
        result[arm_id] = _load_one_arm(
            arm_id,
            cast(Mapping[str, Any], raw_record),
            inputs_path=inputs_path,
            default_artifact_root=effective_default_root,
        )
    return result


def _is_explicit_missing_arm(record: Mapping[str, Any]) -> bool:
    """Recognize a null-only run binding as an explicit missing arm."""

    if not set(record) <= {"run_records", "run_records_path", "runs"}:
        return False
    return not record or all(record.get(name) is None for name in record)


def _arm_records(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """Accept either a direct arm map or an ``arms`` wrapper."""

    wrapper_keys = set(payload).intersection(_ARM_CONTAINER_KEYS)
    if len(wrapper_keys) > 1:
        raise ValueError("study inputs may contain only one of 'arms' or 'arm_inputs'")
    if wrapper_keys:
        wrapper_key = next(iter(wrapper_keys))
        raw_arms = payload[wrapper_key]
        if not isinstance(raw_arms, Mapping):
            raise ValueError(f"{wrapper_key} must be an object mapping arm IDs")
        unknown = set(payload) - wrapper_keys - _COMMON_INPUT_KEYS
        if unknown:
            raise ValueError(
                "study inputs contain unknown top-level fields: "
                + ", ".join(sorted(unknown))
            )
        return dict(cast(Mapping[str, Any], raw_arms)), _optional_string(
            payload.get("artifact_root"), "artifact_root"
        )

    if "artifact_root" in payload or "schema_version" in payload:
        arm_payload = {
            key: value
            for key, value in payload.items()
            if key not in _COMMON_INPUT_KEYS
        }
        return arm_payload, _optional_string(
            payload.get("artifact_root"), "artifact_root"
        )
    return dict(payload), None


def _load_one_arm(
    arm_id: str,
    record: Mapping[str, Any],
    *,
    inputs_path: Path,
    default_artifact_root: Path | None,
) -> StudyArmInput:
    unknown = set(record) - _ARM_INPUT_KEYS
    if unknown:
        raise ValueError(
            f"study input for arm {arm_id!r} contains unknown fields: "
            + ", ".join(sorted(unknown))
        )

    forecast_path = _required_path(
        record,
        ("forecast_release", "forecast", "forecast_release_path"),
        arm_id=arm_id,
        inputs_path=inputs_path,
    )
    labels_path = _required_path(
        record,
        ("labels_release", "labels", "labels_release_path"),
        arm_id=arm_id,
        inputs_path=inputs_path,
    )
    manifest_path = _required_path(
        record,
        ("manifest", "manifest_path"),
        arm_id=arm_id,
        inputs_path=inputs_path,
    )
    registry_path = _required_path(
        record,
        ("model_registry", "registry", "model_registry_path"),
        arm_id=arm_id,
        inputs_path=inputs_path,
    )
    artifact_root = _optional_path(
        record.get("artifact_root"),
        field_name="artifact_root",
        inputs_path=inputs_path,
    )
    if artifact_root is None:
        artifact_root = default_artifact_root or forecast_path.parent

    forecast, labels = validate_release(
        forecast_path,
        labels_path,
        artifact_root=artifact_root,
    )
    manifest = load_run_manifest(manifest_path).manifest
    registry_bytes = read_single_link_file(registry_path, label="model registry")
    registry = load_model_registry_bytes(registry_bytes)

    run_records_value = record.get(
        "run_records",
        record.get("run_records_path", record.get("runs")),
    )
    run_records = (
        None
        if run_records_value is None
        else tuple(
            _read_run_records(
                _resolve_path_value(
                    run_records_value,
                    field_name="run_records",
                    inputs_path=inputs_path,
                ),
                arm_id=arm_id,
            )
        )
    )
    expected_registry_digest = _optional_string(
        record.get("expected_model_registry_sha256"),
        "expected_model_registry_sha256",
    )
    base_rate_value = record.get("base_rate")
    if base_rate_value is not None and (
        isinstance(base_rate_value, bool)
        or not isinstance(base_rate_value, (int, float))
    ):
        raise ValueError(f"base_rate for arm {arm_id!r} must be a number or null")
    return StudyArmInput(
        forecast_release=forecast,
        labels_release=labels,
        manifest=manifest,
        model_registry=registry,
        run_records=run_records,
        expected_model_registry_sha256=expected_registry_digest,
        base_rate=None if base_rate_value is None else float(base_rate_value),
    )


def _read_run_records(path: Path, *, arm_id: str) -> list[Mapping[str, Any]]:
    """Read persisted JSONL receipts, with JSON array/object convenience support."""

    try:
        raw = read_single_link_file(path, label=f"run records for arm {arm_id}")
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"run records for arm {arm_id!r} are not UTF-8 JSON") from exc
    if not text.strip():
        return []
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError:
        records: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"run records for arm {arm_id!r} line {line_number} is invalid JSON"
                ) from exc
            records.append(
                _record_mapping(value, arm_id=arm_id, line_number=line_number)
            )
        return records
    if isinstance(parsed, list):
        values = cast(list[object], parsed)
        return [
            _record_mapping(value, arm_id=arm_id, line_number=index)
            for index, value in enumerate(values, start=1)
        ]
    return [_record_mapping(parsed, arm_id=arm_id, line_number=1)]


def _record_mapping(
    value: object, *, arm_id: str, line_number: int
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"run records for arm {arm_id!r} line {line_number} must be an object"
        )
    return cast(Mapping[str, Any], value)


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = read_single_link_file(path, label=label)
        value: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return dict(cast(Mapping[str, Any], value))


def _json_sequences_to_tuples(value: object) -> object:
    """Adapt JSON arrays to the immutable tuple fields of the public models."""

    if isinstance(value, list):
        values = cast(list[object], value)
        return tuple(_json_sequences_to_tuples(item) for item in values)
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value).items()
        return {str(key): _json_sequences_to_tuples(item) for key, item in items}
    return value


def _required_path(
    record: Mapping[str, Any],
    names: tuple[str, ...],
    *,
    arm_id: str,
    inputs_path: Path,
) -> Path:
    for name in names:
        if name in record:
            return _resolve_path_value(
                record[name], field_name=name, inputs_path=inputs_path
            )
    raise ValueError(
        f"study input for arm {arm_id!r} requires one of: {', '.join(names)}"
    )


def _optional_path(
    value: object,
    *,
    field_name: str,
    inputs_path: Path,
) -> Path | None:
    if value is None:
        return None
    return _resolve_path_value(value, field_name=field_name, inputs_path=inputs_path)


def _resolve_path_value(value: object, *, field_name: str, inputs_path: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty path string")
    path = Path(value)
    return path if path.is_absolute() else inputs_path.parent / path


def _resolve_path(value: str, inputs_path: Path) -> Path:
    return _resolve_path_value(
        value, field_name="artifact_root", inputs_path=inputs_path
    )


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string or null")
    return value

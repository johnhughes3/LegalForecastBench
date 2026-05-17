"""Freeze protocol artifacts and detect post-freeze drift."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast.protocol.manifest import hash_payload
from legalforecast.protocol.preregistration import load_preregistration

_CHUNK_SIZE = 1024 * 1024


class FreezeProtocolError(ValueError):
    """Base error for invalid or drifting freeze artifacts."""


class MissingFreezeArtifactError(FreezeProtocolError):
    """Raised when a required freeze artifact path is absent."""


class FrozenArtifactName(StrEnum):
    MANIFEST = "manifest"
    UNITS = "units"
    LABELS = "labels"
    PROMPT = "prompt"
    SCORER = "scorer"
    HARNESS = "harness"
    MODEL_REGISTRY = "model_registry"
    BASELINES = "baselines"


REQUIRED_FREEZE_ARTIFACTS: tuple[FrozenArtifactName, ...] = (
    FrozenArtifactName.MANIFEST,
    FrozenArtifactName.UNITS,
    FrozenArtifactName.LABELS,
    FrozenArtifactName.PROMPT,
    FrozenArtifactName.SCORER,
    FrozenArtifactName.HARNESS,
    FrozenArtifactName.MODEL_REGISTRY,
    FrozenArtifactName.BASELINES,
)
_PREREG_HASH_FIELDS: Mapping[FrozenArtifactName, str] = {
    FrozenArtifactName.MANIFEST: "manifest_sha256",
    FrozenArtifactName.UNITS: "units_sha256",
    FrozenArtifactName.LABELS: "labels_sha256",
    FrozenArtifactName.PROMPT: "prompt_sha256",
    FrozenArtifactName.SCORER: "scorer_sha256",
    FrozenArtifactName.HARNESS: "harness_sha256",
}


@dataclass(frozen=True, slots=True)
class FrozenArtifact:
    """One immutable artifact included in a cycle freeze."""

    name: FrozenArtifactName
    path: Path
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, f"{self.name.value}.sha256")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")

    def to_record(self, *, root_path: Path | None = None) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "path": _path_for_record(self.path, root_path=root_path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FreezeDrift:
    """A missing or modified artifact after a freeze."""

    name: FrozenArtifactName
    path: Path
    expected_sha256: str
    actual_sha256: str | None

    @property
    def is_missing(self) -> bool:
        return self.actual_sha256 is None

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "path": str(self.path),
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "is_missing": self.is_missing,
        }


@dataclass(frozen=True, slots=True)
class FreezeBundle:
    """Frozen hash bundle for one benchmark cycle."""

    cycle_id: str
    freeze_timestamp: datetime
    artifacts: tuple[FrozenArtifact, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_aware_datetime(self.freeze_timestamp, "freeze_timestamp")
        if not self.artifacts:
            raise ValueError("freeze bundle requires at least one artifact")
        seen: set[FrozenArtifactName] = set()
        duplicates: set[str] = set()
        for artifact in self.artifacts:
            if artifact.name in seen:
                duplicates.add(artifact.name.value)
            seen.add(artifact.name)
        if duplicates:
            raise ValueError(f"duplicate freeze artifacts: {sorted(duplicates)}")

    @property
    def bundle_sha256(self) -> str:
        return hash_payload(self.to_record(include_bundle_hash=False))

    def artifact(self, name: FrozenArtifactName) -> FrozenArtifact:
        for artifact in self.artifacts:
            if artifact.name is name:
                return artifact
        raise KeyError(name.value)

    def frozen_artifact_hashes(self) -> dict[str, str]:
        return {
            field_name: self.artifact(artifact_name).sha256
            for artifact_name, field_name in _PREREG_HASH_FIELDS.items()
        }

    def to_record(
        self,
        *,
        root_path: Path | None = None,
        include_bundle_hash: bool = True,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "cycle_id": self.cycle_id,
            "freeze_timestamp": _iso_datetime(self.freeze_timestamp),
            "artifacts": [
                artifact.to_record(root_path=root_path)
                for artifact in sorted(self.artifacts, key=_artifact_sort_key)
            ],
            "frozen_artifacts": self.frozen_artifact_hashes(),
            "model_registry": {
                "path": _path_for_record(
                    self.artifact(FrozenArtifactName.MODEL_REGISTRY).path,
                    root_path=root_path,
                ),
                "sha256": self.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256,
            },
            "baselines": {
                "path": _path_for_record(
                    self.artifact(FrozenArtifactName.BASELINES).path,
                    root_path=root_path,
                ),
                "sha256": self.artifact(FrozenArtifactName.BASELINES).sha256,
            },
        }
        if include_bundle_hash:
            record["hash_bundle_sha256"] = hash_payload(record)
        return record


def sha256_file(path: str | Path) -> str:
    """Compute a SHA-256 hash over raw file bytes."""

    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise MissingFreezeArtifactError(f"freeze artifact missing: {artifact_path}")
    digest = hashlib.sha256()
    with artifact_path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_cycle(
    cycle_id: str,
    artifact_paths: Mapping[FrozenArtifactName | str, str | Path],
    *,
    freeze_timestamp: datetime | None = None,
    required_artifacts: Sequence[FrozenArtifactName] = REQUIRED_FREEZE_ARTIFACTS,
    base_protocol_path: str | Path | None = None,
    base_protocol_record: Mapping[str, Any] | None = None,
    protocol_output_path: str | Path | None = None,
    bundle_output_path: str | Path | None = None,
) -> FreezeBundle:
    """Hash all cycle artifacts and optionally write protocol and bundle files."""

    if base_protocol_path is not None and base_protocol_record is not None:
        raise ValueError("pass either base_protocol_path or base_protocol_record")

    bundle = FreezeBundle(
        cycle_id=cycle_id,
        freeze_timestamp=freeze_timestamp or datetime.now(UTC),
        artifacts=_collect_artifacts(artifact_paths, required_artifacts),
    )

    base_record = (
        load_preregistration(base_protocol_path)
        if base_protocol_path is not None
        else base_protocol_record
    )
    if protocol_output_path is not None:
        write_preregistration_protocol(
            protocol_output_path,
            bundle,
            base_record=base_record,
        )
    if bundle_output_path is not None:
        write_hash_bundle(bundle_output_path, bundle)
    return bundle


def build_preregistration_record(
    bundle: FreezeBundle,
    *,
    base_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge generated freeze fields into a preregistration record."""

    record = _deep_copy_record(base_record) if base_record is not None else {}
    existing_cycle_id = record.get("cycle_id")
    if existing_cycle_id not in {None, "", bundle.cycle_id}:
        raise ValueError(
            f"base preregistration cycle_id {existing_cycle_id!r} "
            f"does not match freeze cycle {bundle.cycle_id!r}"
        )
    record["cycle_id"] = bundle.cycle_id
    record["freeze_timestamp"] = _iso_datetime(bundle.freeze_timestamp)

    frozen_artifacts = _ensure_mapping(record, "frozen_artifacts")
    frozen_artifacts.update(bundle.frozen_artifact_hashes())

    model_registry_artifact = bundle.artifact(FrozenArtifactName.MODEL_REGISTRY)
    model_registry = _ensure_mapping(record, "model_registry")
    model_registry["path"] = str(model_registry_artifact.path)
    model_registry["sha256"] = model_registry_artifact.sha256

    baselines_artifact = bundle.artifact(FrozenArtifactName.BASELINES)
    baselines = _ensure_mapping(record, "baselines")
    baselines["path"] = str(baselines_artifact.path)
    baselines["sha256"] = baselines_artifact.sha256

    return record


def write_preregistration_protocol(
    path: str | Path,
    bundle: FreezeBundle,
    *,
    base_record: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Write protocols/<cycle_id>.preregistration.yaml with generated hashes."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = build_preregistration_record(bundle, base_record=base_record)
    output_path.write_text(dump_simple_yaml(record), encoding="utf-8")
    return record


def write_hash_bundle(
    path: str | Path,
    bundle: FreezeBundle,
    *,
    root_path: str | Path | None = None,
) -> Mapping[str, Any]:
    """Write a machine-readable final hash bundle."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = Path(root_path) if root_path is not None else None
    record = bundle.to_record(root_path=root)
    output_path.write_text(
        f"{json.dumps(record, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return record


def detect_freeze_drift(bundle: FreezeBundle) -> tuple[FreezeDrift, ...]:
    """Return every frozen artifact that is now missing or modified."""

    drift: list[FreezeDrift] = []
    for artifact in bundle.artifacts:
        try:
            actual_sha256 = sha256_file(artifact.path)
        except MissingFreezeArtifactError:
            drift.append(
                FreezeDrift(
                    name=artifact.name,
                    path=artifact.path,
                    expected_sha256=artifact.sha256,
                    actual_sha256=None,
                )
            )
            continue
        if actual_sha256 != artifact.sha256:
            drift.append(
                FreezeDrift(
                    name=artifact.name,
                    path=artifact.path,
                    expected_sha256=artifact.sha256,
                    actual_sha256=actual_sha256,
                )
            )
    return tuple(drift)


def verify_no_freeze_drift(bundle: FreezeBundle) -> None:
    """Raise when any frozen artifact is missing or has changed."""

    drift = detect_freeze_drift(bundle)
    if not drift:
        return
    messages = [
        (
            f"{item.name.value} missing at {item.path}"
            if item.is_missing
            else f"{item.name.value} hash changed at {item.path}"
        )
        for item in drift
    ]
    raise FreezeProtocolError("; ".join(messages))


def dump_simple_yaml(record: Mapping[str, Any]) -> str:
    """Dump the subset of YAML accepted by preregistration.parse_simple_yaml."""

    return "".join(_yaml_mapping_lines(record, indent=0))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast freeze",
        description="Freeze LegalForecast-MTD cycle artifacts and write hashes.",
    )
    parser.add_argument("cycle_id")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--units", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--scorer", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model-registry", required=True)
    parser.add_argument("--baselines", required=True)
    parser.add_argument("--timestamp")
    parser.add_argument("--base-protocol")
    parser.add_argument("--protocol-output")
    parser.add_argument("--bundle-output")
    return parser


def cli_freeze(argv: Sequence[str]) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    cycle_id = cast(str, args.cycle_id)
    protocol_output = (
        Path(cast(str, args.protocol_output))
        if args.protocol_output is not None
        else Path("protocols") / f"{cycle_id}.preregistration.yaml"
    )
    bundle_output = (
        Path(cast(str, args.bundle_output))
        if args.bundle_output is not None
        else Path("manifests") / f"{cycle_id}.freeze.json"
    )

    bundle = freeze_cycle(
        cycle_id,
        {
            FrozenArtifactName.MANIFEST: Path(cast(str, args.manifest)),
            FrozenArtifactName.UNITS: Path(cast(str, args.units)),
            FrozenArtifactName.LABELS: Path(cast(str, args.labels)),
            FrozenArtifactName.PROMPT: Path(cast(str, args.prompt)),
            FrozenArtifactName.SCORER: Path(cast(str, args.scorer)),
            FrozenArtifactName.HARNESS: Path(cast(str, args.harness)),
            FrozenArtifactName.MODEL_REGISTRY: Path(cast(str, args.model_registry)),
            FrozenArtifactName.BASELINES: Path(cast(str, args.baselines)),
        },
        freeze_timestamp=(
            _parse_timestamp(cast(str, args.timestamp))
            if args.timestamp is not None
            else None
        ),
        base_protocol_path=(
            Path(cast(str, args.base_protocol))
            if args.base_protocol is not None
            else None
        ),
        protocol_output_path=protocol_output,
        bundle_output_path=bundle_output,
    )
    print(json.dumps(bundle.to_record(root_path=Path.cwd()), sort_keys=True))
    return 0


def _collect_artifacts(
    artifact_paths: Mapping[FrozenArtifactName | str, str | Path],
    required_artifacts: Sequence[FrozenArtifactName],
) -> tuple[FrozenArtifact, ...]:
    paths_by_name: dict[FrozenArtifactName, Path] = {}
    for raw_name, raw_path in artifact_paths.items():
        name = (
            raw_name
            if isinstance(raw_name, FrozenArtifactName)
            else FrozenArtifactName(raw_name)
        )
        if name in paths_by_name:
            raise ValueError(f"duplicate freeze artifact path: {name.value}")
        paths_by_name[name] = Path(raw_path)

    missing_names = [
        artifact_name.value
        for artifact_name in required_artifacts
        if artifact_name not in paths_by_name
    ]
    if missing_names:
        raise MissingFreezeArtifactError(
            f"freeze artifacts are required: {', '.join(missing_names)}"
        )

    artifacts: list[FrozenArtifact] = []
    for name in REQUIRED_FREEZE_ARTIFACTS:
        path = paths_by_name.get(name)
        if path is None:
            continue
        artifacts.append(
            FrozenArtifact(
                name=name,
                path=path,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return tuple(artifacts)


def _artifact_sort_key(artifact: FrozenArtifact) -> int:
    try:
        return REQUIRED_FREEZE_ARTIFACTS.index(artifact.name)
    except ValueError:
        return len(REQUIRED_FREEZE_ARTIFACTS)


def _deep_copy_record(record: Mapping[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in record.items():
        copied[str(key)] = _deep_copy_value(value)
    return copied


def _deep_copy_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _deep_copy_record(cast(Mapping[str, Any], value))
    if isinstance(value, list):
        return [_deep_copy_value(item) for item in cast(list[Any], value)]
    if isinstance(value, tuple):
        return [_deep_copy_value(item) for item in cast(tuple[Any, ...], value)]
    return value


def _ensure_mapping(record: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = record.get(field_name)
    if value is None or value == "":
        nested: dict[str, Any] = {}
        record[field_name] = nested
        return nested
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    nested = _deep_copy_record(cast(Mapping[str, Any], value))
    record[field_name] = nested
    return nested


def _yaml_mapping_lines(record: Mapping[str, Any], *, indent: int) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in record.items():
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{key}:\n")
            lines.extend(
                _yaml_mapping_lines(
                    cast(Mapping[str, Any], value),
                    indent=indent + 2,
                )
            )
            continue
        if isinstance(value, list):
            lines.extend(_yaml_list_lines(key, cast(list[Any], value), indent=indent))
            continue
        lines.append(f"{prefix}{key}: {_yaml_scalar(value)}\n")
    return lines


def _yaml_list_lines(key: str, values: list[Any], *, indent: int) -> list[str]:
    prefix = " " * indent
    if not values:
        return [f"{prefix}{key}: []\n"]
    lines = [f"{prefix}{key}:\n"]
    item_prefix = " " * (indent + 2)
    for value in values:
        if isinstance(value, Mapping | list):
            raise TypeError("simple preregistration YAML only supports scalar lists")
        lines.append(f"{item_prefix}- {_yaml_scalar(value)}\n")
    return lines


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        return json.dumps(value, sort_keys=True)
    if value == "":
        return '""'
    if _is_plain_yaml_scalar(value):
        return value
    return json.dumps(value)


def _is_plain_yaml_scalar(value: str) -> bool:
    return not any(character in value for character in ("\n", "#", "{", "}", "[", "]"))


def _path_for_record(path: Path, *, root_path: Path | None) -> str:
    if root_path is None:
        return str(path)
    try:
        return str(path.relative_to(root_path))
    except ValueError:
        return str(path)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require_aware_datetime(parsed, "timestamp")
    return parsed


def _iso_datetime(value: datetime) -> str:
    _require_aware_datetime(value, "datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hash")

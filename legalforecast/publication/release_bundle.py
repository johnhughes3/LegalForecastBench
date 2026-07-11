"""Build v0.1 alpha release bundle manifests from generated artifacts."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast.protocol import sha256_file

RELEASE_BUNDLE_SCHEMA_VERSION = "legalforecast.release_bundle.v1"
RELEASE_CHANNEL = "v0.1-public-feedback-alpha"
RELEASE_STATUS = "public-feedback-alpha"
ALLOWED_SOURCE_CLASSES = ("package_build", "release_metadata", "synthetic_fixture")
REQUIRED_FIXTURE_ARTIFACTS = (
    "artifact-index.json",
    "artifact-manifest.json",
    "manifests/cycle_fixture_e2e.freeze.json",
    "report/leaderboard.json",
    "report/leaderboard.md",
)
RELEASE_METADATA_PATHS = (
    Path("README.md"),
    Path("MODEL_RELEASE_DATES.md"),
    Path("CITATION.cff"),
    Path("LICENSE"),
    Path("docs/METHODS.md"),
    Path("docs/multiharness-adapter-spec.md"),
    Path("docs/community-submissions.md"),
    Path("docs/adapters/provider-baselines.md"),
    Path("docs/adapters/hermes-agent.md"),
    Path("docs/adapters/lq-ai.md"),
    Path("docs/adapters/openclaw.md"),
)
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")

JsonRecord = dict[str, object]


class ReleaseBundleError(RuntimeError):
    """Raised when alpha release bundle inputs are incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class ReleaseBundleConfig:
    """Inputs for a regenerable v0.1 alpha release artifact bundle."""

    fixture_output_dir: Path
    output_dir: Path
    release_commit: str
    package_version: str
    release_tag: str
    repo_root: Path
    dist_dir: Path | None = None
    generated_at: datetime | None = None


def build_release_bundle(config: ReleaseBundleConfig) -> JsonRecord:
    """Copy alpha-safe artifacts into a bundle directory and write a manifest."""

    _validate_config(config)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[JsonRecord] = []
    artifacts.extend(_copy_fixture_artifacts(config.fixture_output_dir, output_dir))
    artifacts.extend(_copy_release_metadata(config.repo_root, output_dir))
    if config.dist_dir is not None:
        artifacts.extend(_copy_dist_artifacts(config.dist_dir, output_dir))

    manifest: JsonRecord = {
        "schema_version": RELEASE_BUNDLE_SCHEMA_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "release_tag": config.release_tag,
        "package_version": config.package_version,
        "release_commit": config.release_commit,
        "generated_at": _iso_datetime(config.generated_at or datetime.now(UTC)),
        "release_status": RELEASE_STATUS,
        "canonical_leaderboard": False,
        "paid_source_material_included": False,
        "allowed_source_classes": list(ALLOWED_SOURCE_CLASSES),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    manifest_path = output_dir / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _validate_config(config: ReleaseBundleConfig) -> None:
    if not _COMMIT_RE.fullmatch(config.release_commit):
        raise ReleaseBundleError("release_commit must be a git SHA")
    for value, field_name in (
        (config.package_version, "package_version"),
        (config.release_tag, "release_tag"),
    ):
        if not value.strip():
            raise ReleaseBundleError(f"{field_name} is required")
    if config.generated_at is not None and config.generated_at.tzinfo is None:
        raise ReleaseBundleError("generated_at must be timezone-aware")


def _copy_fixture_artifacts(
    fixture_output_dir: Path,
    output_dir: Path,
) -> list[JsonRecord]:
    manifest = _read_json_object(fixture_output_dir / "artifact-manifest.json")
    manifest_paths = _required_string_sequence(
        manifest.get("artifacts"),
        "artifact-manifest.artifacts",
    )
    for raw_path in manifest_paths:
        _safe_relative_path(raw_path)

    missing = [
        required
        for required in REQUIRED_FIXTURE_ARTIFACTS
        if required not in manifest_paths
    ]
    if missing:
        formatted = ", ".join(missing)
        raise ReleaseBundleError(
            f"fixture output missing required artifacts: {formatted}"
        )

    index_by_path = _fixture_index_records(fixture_output_dir / "artifact-index.json")
    records: list[JsonRecord] = []
    for raw_path in manifest_paths:
        relative_path = _safe_relative_path(raw_path)
        source_path = fixture_output_dir / relative_path
        if not source_path.is_file():
            raise ReleaseBundleError(f"fixture artifact missing: {raw_path}")

        expected = index_by_path.get(raw_path)
        if expected is not None:
            actual_sha256 = sha256_file(source_path)
            if actual_sha256 != expected["sha256"]:
                raise ReleaseBundleError(f"fixture artifact hash mismatch: {raw_path}")

        destination = output_dir / "fixture-e2e" / relative_path
        _copy_file(source_path, destination)
        records.append(
            _artifact_record(
                output_dir,
                destination,
                bundle_role=_fixture_bundle_role(raw_path),
                source_class="synthetic_fixture",
                category=(
                    str(expected["category"])
                    if expected is not None
                    else "fixture_metadata"
                ),
            )
        )
    return records


def _copy_release_metadata(repo_root: Path, output_dir: Path) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for relative_path in RELEASE_METADATA_PATHS:
        source_path = repo_root / relative_path
        if not source_path.is_file():
            raise ReleaseBundleError(
                f"release metadata artifact missing: {relative_path}"
            )
        destination = output_dir / "release-metadata" / relative_path
        _copy_file(source_path, destination)
        records.append(
            _artifact_record(
                output_dir,
                destination,
                bundle_role=_release_metadata_role(relative_path),
                source_class="release_metadata",
                category="release_metadata",
            )
        )
    return records


def _copy_dist_artifacts(dist_dir: Path, output_dir: Path) -> list[JsonRecord]:
    if not dist_dir.is_dir():
        raise ReleaseBundleError(f"dist_dir does not exist: {dist_dir}")
    candidates = tuple(sorted((*dist_dir.glob("*.whl"), *dist_dir.glob("*.tar.gz"))))
    if not candidates:
        raise ReleaseBundleError("dist_dir must contain a wheel or sdist")

    records: list[JsonRecord] = []
    for source_path in candidates:
        destination = output_dir / "dist" / source_path.name
        _copy_file(source_path, destination)
        records.append(
            _artifact_record(
                output_dir,
                destination,
                bundle_role="package_build",
                source_class="package_build",
                category="package_build",
            )
        )
    return records


def _fixture_index_records(index_path: Path) -> dict[str, JsonRecord]:
    index = _read_json_object(index_path)
    records = _required_record_sequence(
        index.get("artifacts"),
        "artifact-index.artifacts",
    )
    records_by_path: dict[str, JsonRecord] = {}
    for record in records:
        raw_path = _required_str(record, "path")
        _safe_relative_path(raw_path)
        records_by_path[raw_path] = {
            "category": _required_str(record, "category"),
            "sha256": _required_str(record, "sha256"),
        }
    return records_by_path


def _artifact_record(
    output_dir: Path,
    path: Path,
    *,
    bundle_role: str,
    source_class: str,
    category: str,
) -> JsonRecord:
    return {
        "path": str(path.relative_to(output_dir)),
        "bundle_role": bundle_role,
        "source_class": source_class,
        "category": category,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _fixture_bundle_role(relative_path: str) -> str:
    if relative_path.startswith("report/"):
        return "fixture_report"
    if relative_path.startswith("manifests/"):
        return "freeze_bundle"
    if relative_path in {"artifact-index.json", "artifact-manifest.json"}:
        return "fixture_manifest"
    return "fixture_workflow"


def _release_metadata_role(relative_path: Path) -> str:
    if relative_path.name == "README.md":
        return "readme"
    if relative_path.name == "MODEL_RELEASE_DATES.md":
        return "model_release_anchors"
    if relative_path.name == "CITATION.cff":
        return "citation_metadata"
    if relative_path.name == "LICENSE":
        return "license"
    if relative_path.name == "multiharness-adapter-spec.md":
        return "adapter_spec"
    if relative_path.name == "community-submissions.md":
        return "community_submission_docs"
    if "adapters" in relative_path.parts:
        return "adapter_documentation"
    if "plans" in relative_path.parts:
        return "implementation_plan"
    return "release_metadata"


def _copy_file(source_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)


def _safe_relative_path(raw_path: str) -> Path:
    if "\\" in raw_path:
        raise ReleaseBundleError(f"unsafe bundle path: {raw_path}")
    path = Path(raw_path)
    if str(path) in {"", "."} or path.is_absolute() or ".." in path.parts:
        raise ReleaseBundleError(f"unsafe bundle path: {raw_path}")
    return path


def _read_json_object(path: Path) -> JsonRecord:
    if not path.is_file():
        raise ReleaseBundleError(f"JSON artifact missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseBundleError(f"{path} must contain a JSON object")
    return cast(JsonRecord, value)


def _required_record_sequence(value: object, field_name: str) -> tuple[JsonRecord, ...]:
    if not isinstance(value, list):
        raise ReleaseBundleError(f"{field_name} must be a list of objects")
    records: list[JsonRecord] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise ReleaseBundleError(f"{field_name} must be a list of objects")
        records.append(cast(JsonRecord, item))
    return tuple(records)


def _required_string_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ReleaseBundleError(f"{field_name} must be a list of strings")
    strings: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise ReleaseBundleError(f"{field_name} must be a list of strings")
        strings.append(item)
    return tuple(strings)


def _required_str(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value:
        raise ReleaseBundleError(f"{field_name} is required")
    return value


def _iso_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ReleaseBundleError("datetime must be timezone-aware")
    return format_utc_iso_z(value)

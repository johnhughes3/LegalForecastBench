"""Build a versioned, provider-free Hugging Face benchmark package."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from legalforecast._canonical import sha256_file
from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
)
from legalforecast.immutable_io import (
    ImmutableIOError,
    publish_tree_create_only,
    read_single_link_file,
)
from legalforecast.path_safety import safe_path_component
from legalforecast.publication.official_report_validation import (
    OfficialBundle,
    load_official_bundle,
    validate_official_arithmetic,
)
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)
from legalforecast.publication.static_sites import render_official_results_site
from legalforecast.reporting.result_class import (
    SUPPLEMENTARY_CAVEAT,
    SUPPLEMENTARY_MARKER,
)

OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION = "legalforecast-official-hf-publication-v1"
OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION = (
    "legalforecast-official-hf-publication-v2"
)
"""Manifest shape that additionally commits to a supplementary release path.

Cycle 1 change control freezes the bytes of every emitted schema id, so the
supplementary commitment fields are a new schema id rather than optional fields
on ``-v1``. A publication without supplementary models still emits ``-v1``, byte
for byte as before.
"""

OFFICIAL_HF_UPLOAD_PLAN_SCHEMA_VERSION = "legalforecast-official-hf-upload-plan-v1"
RETAINED_HF_PUBLICATION_SCHEMA_VERSION = "legalforecast-retained-hf-publication-v1"
RETAINED_HF_AGGREGATE_SCHEMA_VERSION = "legalforecast-retained-hf-aggregate-v1"
RETAINED_HF_SOURCE_SCHEMA_VERSION = "legalforecast-retained-hf-source-v1"
_SUPPLEMENTARY_DIRECTORY = "supplementary"
_MUTABLE_REVISIONS = frozenset(
    {"default", "develop", "head", "latest", "main", "master", "trunk"}
)
_REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)


class OfficialHFPublicationError(ValueError):
    """Raised when an official HF package cannot be created or verified."""


@dataclass(frozen=True, slots=True)
class OfficialHFPublicationConfig:
    """Inputs for a create-only official Hugging Face package."""

    official_artifacts_dir: Path
    output_dir: Path
    release_version: str
    dataset_repository: str
    supplementary_artifacts_dir: Path | None = None

    def __post_init__(self) -> None:
        _validate_release_version(self.release_version)
        if _REPOSITORY_PATTERN.fullmatch(self.dataset_repository) is None:
            raise OfficialHFPublicationError(
                "dataset_repository must be an owner/name Hugging Face repository id"
            )


@dataclass(frozen=True, slots=True)
class OfficialHFPublicationResult:
    """Paths and commitments emitted by an official HF package build."""

    output_dir: Path
    publication_manifest_path: Path
    upload_plan_path: Path
    readme_path: Path
    eval_path: Path
    cycle_id: str
    release_version: str
    artifact_count: int
    aggregate_artifact_index_sha256: str
    site_artifact_index_sha256: str
    supplementary_artifact_index_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class RetainedHFPublicationConfig:
    """Inputs for the retained fan-in's public Hugging Face package."""

    score_path: Path
    unit_scores_path: Path
    report_dir: Path
    output_dir: Path
    cycle_id: str
    release_version: str
    dataset_repository: str

    def __post_init__(self) -> None:
        _validate_release_version(self.release_version)
        try:
            safe_path_component(self.cycle_id, field_name="cycle_id")
        except ValueError as exc:
            raise OfficialHFPublicationError(str(exc)) from exc
        if _REPOSITORY_PATTERN.fullmatch(self.dataset_repository) is None:
            raise OfficialHFPublicationError(
                "dataset_repository must be an owner/name Hugging Face repository id"
            )


@dataclass(frozen=True, slots=True)
class RetainedHFPublicationResult:
    """Paths and commitments emitted by a retained fan-in HF package build."""

    output_dir: Path
    publication_manifest_path: Path
    upload_plan_path: Path
    readme_path: Path
    eval_path: Path
    cycle_id: str
    release_version: str
    artifact_count: int


_RETAINED_PUBLIC_IDENTITY_FIELDS = (
    "run_manifest_id",
    "run_manifest_sha256",
    "forecast_release_id",
    "forecast_release_digest",
    "labels_release_id",
    "labels_release_digest",
    "labels_forecast_release_digest",
    "run_identity_sha256",
    "model_registry_sha256",
    "models",
)
_RETAINED_REPORT_FILES = (
    "leaderboard.json",
    "leaderboard.csv",
    "leaderboard.md",
    "leaderboard.html",
)


def build_retained_hf_publication(
    config: RetainedHFPublicationConfig,
) -> RetainedHFPublicationResult:
    """Build a gated package from the retained protected fan-in outputs.

    The retained fan-in is the authority for scoring and report generation. This
    adapter deliberately consumes those already-validated outputs rather than
    reconstructing a private acquisition or aggregate runtime in the public
    repository.
    """

    if os.path.lexists(config.output_dir):
        raise OfficialHFPublicationError(
            f"publication output already exists: {config.output_dir}"
        )
    score = _read_json(config.score_path, "retained score artifact")
    identity = _retained_public_identity(score)
    report = _read_json(config.report_dir / "leaderboard.json", "retained leaderboard")
    provenance_value = report.get("provenance")
    if not isinstance(provenance_value, Mapping):
        raise OfficialHFPublicationError("retained leaderboard lacks score provenance")
    provenance = cast(Mapping[str, Any], provenance_value)
    for field in _RETAINED_PUBLIC_IDENTITY_FIELDS:
        if provenance.get(field) != identity[field]:
            raise OfficialHFPublicationError(
                f"retained leaderboard provenance differs for {field}"
            )
    summaries = score.get("summaries")
    if not isinstance(summaries, Sequence) or isinstance(summaries, str | bytes):
        raise OfficialHFPublicationError("retained score artifact lacks summaries")
    if not summaries:
        raise OfficialHFPublicationError("retained score artifact has no summaries")
    unit_records = _retained_unit_records(config.unit_scores_path)
    release_path = f"releases/{config.release_version}/{config.cycle_id}"

    config.output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{config.output_dir.name}.", dir=config.output_dir.parent
    ) as directory:
        root = Path(directory)
        aggregate_root = root / release_path / "aggregate"
        _copy_retained_file(
            config.score_path, aggregate_root / "scores.json", "score artifact"
        )
        _copy_retained_file(
            config.unit_scores_path,
            aggregate_root / "unit-scores.jsonl",
            "unit-score artifact",
        )
        for name in _RETAINED_REPORT_FILES:
            _copy_retained_file(
                config.report_dir / name,
                aggregate_root / "report" / name,
                f"retained report artifact {name}",
            )
        write_json_object(
            aggregate_root / "source-identity.json",
            {
                "schema_version": RETAINED_HF_SOURCE_SCHEMA_VERSION,
                "cycle_id": config.cycle_id,
                "score_sha256": _prefixed_digest(config.score_path),
                "unit_scores_sha256": _prefixed_digest(config.unit_scores_path),
                "leaderboard_sha256": _prefixed_digest(
                    config.report_dir / "leaderboard.json"
                ),
                "identity": identity,
            },
        )
        aggregate_digest = _write_retained_artifact_index(
            aggregate_root, config.cycle_id
        )

        site_root = root / release_path / "site"
        site_root.mkdir(parents=True, exist_ok=True)
        (site_root / "index.html").write_text(
            _retained_site_html(config.cycle_id, config.release_version),
            encoding="utf-8",
        )
        write_json_object(
            site_root / "site-manifest.json",
            {
                "schema_version": "legalforecast-retained-hf-site-v1",
                "index": "index.html",
            },
        )
        site_digest = _write_retained_artifact_index(site_root, config.cycle_id)
        (root / "eval.yaml").write_text(
            _eval_yaml(config.cycle_id, config.release_version), encoding="utf-8"
        )
        (root / "README.md").write_text(
            _dataset_card(
                cycle_id=config.cycle_id,
                release_version=config.release_version,
                release_path=release_path,
                dataset_repository=config.dataset_repository,
                aggregate_digest=aggregate_digest,
                site_digest=site_digest,
            ),
            encoding="utf-8",
        )
        records = _artifact_records(root)
        write_json_object(
            root / "hf-upload-plan.json",
            {
                "schema_version": OFFICIAL_HF_UPLOAD_PLAN_SCHEMA_VERSION,
                "repository": config.dataset_repository,
                "revision_policy": "immutable-commit",
                "release_path": release_path,
                "upload": "protected-oidc-only",
                "artifacts": records,
            },
        )
        records = _artifact_records(root)
        write_json_object(
            root / "publication-manifest.json",
            {
                "schema_version": RETAINED_HF_PUBLICATION_SCHEMA_VERSION,
                "cycle_id": config.cycle_id,
                "release_version": config.release_version,
                "release_path": release_path,
                "dataset_repository": config.dataset_repository,
                "revision_policy": "immutable-release-path",
                "manual_gate": {
                    "mode": "manual",
                    "scope": "dataset_repository",
                    "repository_setting_required": True,
                },
                "aggregate_artifact_index_sha256": aggregate_digest,
                "site_artifact_index_sha256": site_digest,
                "source_identity": identity,
                "unit_score_count": len(unit_records),
                "artifacts": records,
            },
        )
        enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))
        payloads = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        try:
            publish_tree_create_only(config.output_dir, payloads)
        except ImmutableIOError as exc:
            raise OfficialHFPublicationError(str(exc)) from exc

    return validate_retained_hf_publication(config.output_dir)


def validate_retained_hf_publication(root: Path) -> RetainedHFPublicationResult:
    """Verify every byte and identity commitment in a retained HF package."""

    manifest_path = root / "publication-manifest.json"
    manifest = _read_json(manifest_path, "retained publication manifest")
    if manifest.get("schema_version") != RETAINED_HF_PUBLICATION_SCHEMA_VERSION:
        raise OfficialHFPublicationError(
            "retained publication manifest has an unknown schema"
        )
    cycle_id = _required_text(manifest, "cycle_id")
    release_version = _required_text(manifest, "release_version")
    _validate_release_version(release_version)
    release_path = _required_text(manifest, "release_path")
    expected_release_path = f"releases/{release_version}/{cycle_id}"
    if release_path != expected_release_path:
        raise OfficialHFPublicationError(
            "retained publication release_path does not match its version and cycle"
        )
    manual_gate_value = manifest.get("manual_gate")
    if not isinstance(manual_gate_value, Mapping):
        raise OfficialHFPublicationError("retained publication must be manually gated")
    manual_gate = cast(Mapping[str, Any], manual_gate_value)
    if manual_gate.get("mode") != "manual":
        raise OfficialHFPublicationError("retained publication must be manually gated")
    listed: set[str] = set()
    for record in _mapping_rows(manifest.get("artifacts")):
        relative = _required_text(record, "path")
        _safe_relative(relative, "retained publication artifact")
        path = root / relative
        if relative in listed or not path.is_file() or path.is_symlink():
            raise OfficialHFPublicationError(
                f"retained publication artifact is missing or duplicated: {relative}"
            )
        listed.add(relative)
        if _prefixed_digest(path) != _required_text(record, "sha256"):
            raise OfficialHFPublicationError(
                f"retained publication artifact hash mismatch: {relative}"
            )
        if path.stat().st_size != record.get("size_bytes"):
            raise OfficialHFPublicationError(
                f"retained publication artifact size mismatch: {relative}"
            )
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if actual != listed | {"publication-manifest.json"}:
        raise OfficialHFPublicationError(
            "retained publication tree contains files not covered by its manifest"
        )
    aggregate_root = root / release_path / "aggregate"
    site_root = root / release_path / "site"
    if _prefixed_digest(aggregate_root / "artifact-index.json") != manifest.get(
        "aggregate_artifact_index_sha256"
    ):
        raise OfficialHFPublicationError("retained aggregate index digest mismatch")
    if _prefixed_digest(site_root / "artifact-index.json") != manifest.get(
        "site_artifact_index_sha256"
    ):
        raise OfficialHFPublicationError("retained site index digest mismatch")
    source = _read_json(
        aggregate_root / "source-identity.json", "retained source identity"
    )
    if source.get("schema_version") != RETAINED_HF_SOURCE_SCHEMA_VERSION:
        raise OfficialHFPublicationError(
            "retained source identity has an unknown schema"
        )
    if source.get("cycle_id") != cycle_id:
        raise OfficialHFPublicationError("retained source identity cycle differs")
    if source.get("identity") != manifest.get("source_identity"):
        raise OfficialHFPublicationError("retained source identity differs")
    if not (site_root / "index.html").is_file():
        raise OfficialHFPublicationError("retained site is missing index.html")
    enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))
    return RetainedHFPublicationResult(
        output_dir=root,
        publication_manifest_path=manifest_path,
        upload_plan_path=root / "hf-upload-plan.json",
        readme_path=root / "README.md",
        eval_path=root / "eval.yaml",
        cycle_id=cycle_id,
        release_version=release_version,
        artifact_count=len(actual),
    )


def _retained_public_identity(score: Mapping[str, Any]) -> dict[str, Any]:
    identity_value = score.get("identity")
    if not isinstance(identity_value, Mapping):
        raise OfficialHFPublicationError(
            "retained score artifact lacks identity metadata"
        )
    identity = cast(Mapping[str, Any], identity_value)
    result: dict[str, Any] = {
        field: identity.get(field) for field in _RETAINED_PUBLIC_IDENTITY_FIELDS
    }
    for field in _RETAINED_PUBLIC_IDENTITY_FIELDS:
        if result[field] is None:
            raise OfficialHFPublicationError(f"retained score identity lacks {field}")
    for field in (
        "run_manifest_sha256",
        "forecast_release_digest",
        "labels_release_digest",
        "labels_forecast_release_digest",
        "run_identity_sha256",
        "model_registry_sha256",
    ):
        value = result[field]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise OfficialHFPublicationError(
                f"retained score identity {field} is not a lowercase SHA-256"
            )
    if not isinstance(result["models"], list) or not result["models"]:
        raise OfficialHFPublicationError("retained score identity lacks model bindings")
    return result


def _retained_unit_records(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.is_file() or path.is_symlink():
        raise OfficialHFPublicationError(
            f"unit-score artifact is not a regular file: {path}"
        )
    try:
        records = tuple(
            read_jsonl_objects(
                path,
                error_factory=OfficialHFPublicationError,
                missing_message=lambda item: (
                    f"unit-score artifact does not exist: {item}"
                ),
                non_object_message=lambda item, line: (
                    f"unit-score line {line} must be an object: {item}"
                ),
            )
        )
    except OfficialHFPublicationError:
        raise
    if not records:
        raise OfficialHFPublicationError("unit-score artifact has no records")
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (
            _required_text(record, "model_id"),
            _required_text(record, "unit_id"),
        )
        if key in seen:
            raise OfficialHFPublicationError("unit-score artifact has duplicate units")
        seen.add(key)
        _required_text(record, "case_id")
    return records


def _copy_retained_file(source: Path, destination: Path, label: str) -> None:
    if not source.is_file() or source.is_symlink():
        raise OfficialHFPublicationError(f"{label} is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _write_retained_artifact_index(root: Path, cycle_id: str) -> str:
    artifacts = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _prefixed_digest(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact-index.json"
    ]
    write_json_object(
        root / "artifact-index.json",
        {
            "schema_version": RETAINED_HF_AGGREGATE_SCHEMA_VERSION,
            "cycle_id": cycle_id,
            "artifacts": artifacts,
        },
    )
    return _prefixed_digest(root / "artifact-index.json")


def _retained_site_html(cycle_id: str, release_version: str) -> str:
    title = html.escape(f"LegalForecastBench {cycle_id} Official Results")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body><main><h1>{title}</h1>
<p>This immutable release was verified and published by the protected
LegalForecastBench fan-in workflow.</p>
<p>Release version: <code>{html.escape(release_version)}</code></p>
<ul>
<li><a href="../aggregate/report/leaderboard.html">Leaderboard</a></li>
<li><a href="../aggregate/report/leaderboard.json">Leaderboard JSON</a></li>
<li><a href="../aggregate/unit-scores.jsonl">Unit scores</a></li>
</ul></main></body></html>
"""


def build_official_hf_publication(
    config: OfficialHFPublicationConfig,
) -> OfficialHFPublicationResult:
    """Build a deterministic local package without contacting Hugging Face."""

    if os.path.lexists(config.output_dir):
        raise OfficialHFPublicationError(
            f"publication output already exists: {config.output_dir}"
        )
    bundle = load_official_bundle(config.official_artifacts_dir)
    _validate_arithmetic(bundle)
    cycle_id = _bundle_cycle_id(bundle)
    safe_path_component(cycle_id, field_name="cycle_id")
    release_path = f"releases/{config.release_version}/{cycle_id}"

    config.output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{config.output_dir.name}.", dir=config.output_dir.parent
    ) as directory:
        root = Path(directory)
        aggregate_root = root / release_path / "aggregate"
        _copy_bundle(
            bundle,
            source_root=config.official_artifacts_dir,
            destination_root=aggregate_root,
            label="official aggregate",
        )

        supplementary_root: Path | None = None
        if config.supplementary_artifacts_dir is not None:
            supplementary_bundle = load_official_bundle(
                config.supplementary_artifacts_dir
            )
            _require_disjoint_solver_ids(bundle, supplementary_bundle)
            supplementary_root = root / release_path / _SUPPLEMENTARY_DIRECTORY
            _copy_bundle(
                supplementary_bundle,
                source_root=config.supplementary_artifacts_dir,
                destination_root=supplementary_root,
                label="supplementary aggregate",
            )

        site_root = root / release_path / "site"
        render_official_results_site(
            official_artifacts_dir=aggregate_root,
            output_dir=site_root,
            supplementary_artifacts_dir=supplementary_root,
        )
        aggregate_digest = _prefixed_digest(aggregate_root / "artifact-index.json")
        site_digest = _prefixed_digest(site_root / "artifact-index.json")
        supplementary_digest = (
            None
            if supplementary_root is None
            else _prefixed_digest(supplementary_root / "artifact-index.json")
        )
        (root / "eval.yaml").write_text(
            _eval_yaml(cycle_id, config.release_version), encoding="utf-8"
        )
        (root / "README.md").write_text(
            _dataset_card(
                cycle_id=cycle_id,
                release_version=config.release_version,
                release_path=release_path,
                dataset_repository=config.dataset_repository,
                aggregate_digest=aggregate_digest,
                site_digest=site_digest,
                supplementary_digest=supplementary_digest,
            ),
            encoding="utf-8",
        )
        records = _artifact_records(root)
        write_json_object(
            root / "hf-upload-plan.json",
            {
                "schema_version": OFFICIAL_HF_UPLOAD_PLAN_SCHEMA_VERSION,
                "repository": config.dataset_repository,
                "revision_policy": "immutable-commit",
                "release_path": release_path,
                "upload": "operator-authorized-only",
                "artifacts": records,
            },
        )
        records = _artifact_records(root)
        manifest: dict[str, object] = {
            "schema_version": OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION,
            "cycle_id": cycle_id,
            "release_version": config.release_version,
            "release_path": release_path,
            "dataset_repository": config.dataset_repository,
            "revision_policy": "immutable-release-path",
            "manual_gate": {
                "mode": "manual",
                "scope": "dataset_repository",
                "repository_setting_required": True,
            },
            "aggregate_artifact_index_sha256": aggregate_digest,
            "site_artifact_index_sha256": site_digest,
            "artifacts": records,
        }
        if supplementary_digest is not None:
            manifest["schema_version"] = (
                OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION
            )
            manifest["supplementary_path"] = (
                f"{release_path}/{_SUPPLEMENTARY_DIRECTORY}"
            )
            manifest["supplementary_artifact_index_sha256"] = supplementary_digest
        write_json_object(root / "publication-manifest.json", manifest)
        enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))
        payloads = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        try:
            publish_tree_create_only(config.output_dir, payloads)
        except ImmutableIOError as exc:
            raise OfficialHFPublicationError(str(exc)) from exc

    return validate_official_hf_publication(config.output_dir)


def validate_official_hf_publication(root: Path) -> OfficialHFPublicationResult:
    """Verify every byte of a previously built local package."""

    manifest_path = root / "publication-manifest.json"
    manifest = _read_json(manifest_path, "publication manifest")
    schema_version = manifest.get("schema_version")
    if schema_version not in {
        OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION,
        OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION,
    }:
        raise OfficialHFPublicationError("publication manifest has an unknown schema")
    declares_supplementary = (
        schema_version == OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION
    )
    cycle_id = _required_text(manifest, "cycle_id")
    release_version = _required_text(manifest, "release_version")
    _validate_release_version(release_version)
    release_path = _required_text(manifest, "release_path")
    expected_release_path = f"releases/{release_version}/{cycle_id}"
    if release_path != expected_release_path:
        raise OfficialHFPublicationError(
            "publication release_path does not match its version and cycle"
        )
    listed: set[str] = set()
    artifacts = _mapping_rows(manifest.get("artifacts"))
    for record in artifacts:
        relative = _required_text(record, "path")
        _safe_relative(relative, "publication artifact")
        path = root / relative
        if relative in listed or not path.is_file():
            raise OfficialHFPublicationError(
                f"publication artifact is missing or duplicated: {relative}"
            )
        listed.add(relative)
        if _prefixed_digest(path) != _required_text(record, "sha256"):
            raise OfficialHFPublicationError(
                f"publication artifact hash mismatch: {relative}"
            )
        if path.stat().st_size != record.get("size_bytes"):
            raise OfficialHFPublicationError(
                f"publication artifact size mismatch: {relative}"
            )
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if actual != listed | {"publication-manifest.json"}:
        raise OfficialHFPublicationError(
            "publication tree contains files not covered by its manifest"
        )
    aggregate_index = root / release_path / "aggregate" / "artifact-index.json"
    site_index = root / release_path / "site" / "artifact-index.json"
    aggregate_digest = _prefixed_digest(aggregate_index)
    site_digest = _prefixed_digest(site_index)
    if aggregate_digest != manifest.get("aggregate_artifact_index_sha256"):
        raise OfficialHFPublicationError("aggregate artifact index digest mismatch")
    if site_digest != manifest.get("site_artifact_index_sha256"):
        raise OfficialHFPublicationError("site artifact index digest mismatch")
    official_bundle = load_official_bundle(aggregate_index.parent)
    if _bundle_cycle_id(official_bundle) != cycle_id:
        raise OfficialHFPublicationError(
            "publication manifest cycle_id differs from the official bundle"
        )
    if not (site_index.parent / "index.html").is_file():
        raise OfficialHFPublicationError("rendered site is missing index.html")
    supplementary_digest = _validate_supplementary_split(
        root,
        manifest,
        official_bundle=official_bundle,
        release_path=release_path,
        listed=listed,
        declares_supplementary=declares_supplementary,
    )
    enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))
    return OfficialHFPublicationResult(
        output_dir=root,
        publication_manifest_path=manifest_path,
        upload_plan_path=root / "hf-upload-plan.json",
        readme_path=root / "README.md",
        eval_path=root / "eval.yaml",
        cycle_id=cycle_id,
        release_version=release_version,
        artifact_count=len(actual),
        aggregate_artifact_index_sha256=aggregate_digest,
        site_artifact_index_sha256=site_digest,
        supplementary_artifact_index_sha256=supplementary_digest,
    )


def _validate_supplementary_split(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    official_bundle: OfficialBundle,
    release_path: str,
    listed: set[str],
    declares_supplementary: bool,
) -> str | None:
    """Verify the supplementary split, or that the tree has none at all.

    Both directions matter: a ``-v2`` manifest must actually commit to the
    supplementary tree it names, and a ``-v1`` manifest must not smuggle
    supplementary files, or a dangling supplementary commitment, into a package
    that claims to carry only official results.
    """

    # Containment is by path segment, not by string prefix: a sibling directory
    # such as ``supplementary-extra`` is not part of the supplementary split and
    # must never be counted as though it were.
    supplementary_relative = PurePosixPath(release_path) / _SUPPLEMENTARY_DIRECTORY
    carries_files = any(
        PurePosixPath(relative).is_relative_to(supplementary_relative)
        for relative in listed
    )
    if not declares_supplementary:
        if "supplementary_artifact_index_sha256" in manifest:
            raise OfficialHFPublicationError(
                "official-only publication manifest declares a supplementary digest"
            )
        if carries_files or "supplementary_path" in manifest:
            raise OfficialHFPublicationError(
                "official-only publication manifest carries supplementary artifacts"
            )
        return None
    if _required_text(manifest, "supplementary_path") != (
        supplementary_relative.as_posix()
    ):
        raise OfficialHFPublicationError(
            "publication supplementary_path does not match its release path"
        )
    if not carries_files:
        raise OfficialHFPublicationError(
            "supplementary publication manifest lists no supplementary artifacts"
        )
    supplementary_root = root / supplementary_relative
    if not supplementary_root.resolve().is_relative_to(root.resolve()):
        raise OfficialHFPublicationError(
            "supplementary directory escapes the publication tree"
        )
    digest = _prefixed_digest(supplementary_root / "artifact-index.json")
    if digest != manifest.get("supplementary_artifact_index_sha256"):
        raise OfficialHFPublicationError("supplementary artifact index digest mismatch")
    supplementary_bundle = load_official_bundle(supplementary_root)
    if _bundle_cycle_id(supplementary_bundle) != _bundle_cycle_id(official_bundle):
        raise OfficialHFPublicationError(
            "supplementary bundle cycle_id differs from the official bundle"
        )
    _require_disjoint_solver_ids(official_bundle, supplementary_bundle)
    return digest


def _require_disjoint_solver_ids(
    official_bundle: OfficialBundle,
    supplementary_bundle: OfficialBundle,
) -> None:
    """Refuse a supplementary model that also appears in the official split."""

    shared = sorted(
        _bundle_solver_ids(official_bundle) & _bundle_solver_ids(supplementary_bundle)
    )
    if shared:
        raise OfficialHFPublicationError(
            f"supplementary solvers must not appear in the official split: {shared}"
        )


def _bundle_solver_ids(bundle: OfficialBundle) -> set[str]:
    """Return the evaluated solver ids, which are the models' stable identity.

    A published ``model_id`` is a display label the solver run chooses, so two
    different models can carry the same one; ``solver_id`` is the registry key
    that ``load_official_bundle`` already pins to the run card's frozen model
    set. Baseline rows are excluded: the same frozen baseline legitimately
    appears in both bundles.
    """

    return {
        _required_text(row, "solver_id")
        for row in _mapping_rows(bundle.scores.get("summaries"))
        if row.get("row_type") == "model"
    }


def _copy_bundle(
    bundle: OfficialBundle,
    *,
    source_root: Path,
    destination_root: Path,
    label: str,
) -> None:
    for relative in bundle.artifact_paths:
        _safe_relative(relative, f"{label} artifact")
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = read_single_link_file(source_root / relative, label=label)
        except ImmutableIOError as exc:
            raise OfficialHFPublicationError(str(exc)) from exc
        destination.write_bytes(payload)


def _validate_arithmetic(bundle: OfficialBundle) -> None:
    validate_official_arithmetic(
        _mapping_rows(bundle.report.get("rows")),
        report=bundle.report,
        score_summary=bundle.scores,
        unit_scores=bundle.unit_scores,
        run_card=bundle.run_card,
        cycle_power=bundle.cycle_power,
    )


def _bundle_cycle_id(bundle: OfficialBundle) -> str:
    values = {
        record.get("cycle_id")
        for record in (
            bundle.report,
            bundle.scores,
            bundle.run_card,
            bundle.cycle_power,
        )
    }
    if len(values) != 1:
        raise OfficialHFPublicationError("official bundle has no single cycle_id")
    value = next(iter(values))
    if not isinstance(value, str) or not value:
        raise OfficialHFPublicationError("official bundle has no single cycle_id")
    return value


def _artifact_records(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _prefixed_digest(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "publication-manifest.json"
    ]


def _eval_yaml(cycle_id: str, release_version: str) -> str:
    task_id = "legalforecast_mtd_" + cycle_id.replace("-", "_")
    description = f"LegalForecastBench {cycle_id} pinned release {release_version}"
    return "\n".join(
        (
            "name: LegalForecastBench",
            "description: >-",
            "  Outcome forecasting on predecision federal motion-to-dismiss records.",
            "evaluation_framework: legalforecastbench",
            "tasks:",
            f"  - id: {json.dumps(task_id)}",
            "    description: >-",
            f"      {json.dumps(description)}",
            f"    config: {json.dumps(cycle_id)}",
            "    split: test",
            "",
        )
    )


def _dataset_card(
    *,
    cycle_id: str,
    release_version: str,
    release_path: str,
    dataset_repository: str,
    aggregate_digest: str,
    site_digest: str,
    supplementary_digest: str | None = None,
) -> str:
    supplementary_config = (
        ""
        if supplementary_digest is None
        else f"""
- config_name: {cycle_id}_supplementary
  data_files:
  - split: supplementary
    path: {release_path}/{_SUPPLEMENTARY_DIRECTORY}/unit-scores.jsonl"""
    )
    supplementary_section = (
        ""
        if supplementary_digest is None
        else f"""
## Supplementary (unofficial) results

{SUPPLEMENTARY_CAVEAT}

Supplementary rows are published in their own `{cycle_id}_supplementary` config
and `supplementary` split, under `{release_path}/{_SUPPLEMENTARY_DIRECTORY}` with
artifact-index commitment `{supplementary_digest}`. They are never present in
the official `{cycle_id}` config or its `test` split.

They carry the `{SUPPLEMENTARY_MARKER}` marker on the rendered result page and
are excluded from ranking, from the best-model figure, and from every
delta-vs-best interval. They must not be reported as official
LegalForecastBench results.
"""
    )
    return f"""---
pretty_name: LegalForecastBench Official Results
tags:
- benchmark
- legal-evaluation
- probabilistic-forecasting
license: other
license_name: LegalForecastBench Controlled-Access Terms v1
gated: manual
configs:
- config_name: {cycle_id}
  data_files:
  - split: test
    path: {release_path}/aggregate/unit-scores.jsonl{supplementary_config}
extra_gated_prompt: >-
  By requesting access, you agree to the Controlled-Access Terms below.
extra_gated_fields:
  Intended use: text
  Organization: text
  I agree to the Controlled-Access Terms: checkbox
---

# LegalForecastBench Official Results

This is the official `{cycle_id}` result surface, released as
`{release_version}`. Official and community results are separate.

The immutable release path is `{release_path}`. Its aggregate artifact-index
commitment is `{aggregate_digest}` and its site commitment is `{site_digest}`.
The target repository is `{dataset_repository}`. It must remain public and
discoverable with Hugging Face manual approval required for file access.
{supplementary_section}
## Controlled-Access Terms

By requesting or using access, you agree that, for each court record in the
dataset, you submit to the jurisdiction of the court from which that record was
obtained for matters concerning your possession, use, or disclosure of the
record. You will promptly comply with any applicable order of that court to
delete or destroy information that the court determines was made public
inadvertently. You will take reasonable precautions not to republish dataset
material in a manner that exposes sensitive information included in a court
filing.

These terms are conditions of access. They do not claim that court records are
proprietary, grant rights in third-party material, or displace applicable law or
court orders.
"""


def _validate_release_version(value: str) -> None:
    try:
        safe_path_component(value, field_name="release_version")
    except ValueError as exc:
        raise OfficialHFPublicationError(str(exc)) from exc
    if value.lower() in _MUTABLE_REVISIONS:
        raise OfficialHFPublicationError(
            "release_version must identify an immutable release, not a mutable revision"
        )


def _safe_relative(value: str, label: str) -> None:
    parts = value.split("/")
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise OfficialHFPublicationError(f"{label} must be a safe relative path")


def _prefixed_digest(path: Path) -> str:
    return "sha256:" + sha256_file(path)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=OfficialHFPublicationError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise OfficialHFPublicationError(f"record requires non-empty {key}")
    return value


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(
        cast(Mapping[str, Any], item)
        for item in cast(Sequence[object], value)
        if isinstance(item, Mapping)
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Build one local Hugging Face publication package."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-artifacts-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--dataset-repository", required=True)
    parser.add_argument(
        "--supplementary-artifacts-dir",
        type=Path,
        default=None,
        help=(
            "Separately aggregated bundle of post-anchor models. Published under "
            "a supplementary/ path and its own dataset config; never merged into "
            "the official split."
        ),
    )
    parser.add_argument(
        "--score",
        type=Path,
        help="Retained protected fan-in scores.json output.",
    )
    parser.add_argument(
        "--unit-scores",
        type=Path,
        help="Retained protected fan-in unit-scores.jsonl output.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Directory containing retained leaderboard report outputs.",
    )
    parser.add_argument(
        "--cycle-id",
        help="Retained fan-in cycle identifier bound into the release path.",
    )
    args = parser.parse_args(argv)
    retained_args = (args.score, args.unit_scores, args.report_dir, args.cycle_id)
    if any(value is not None for value in retained_args):
        if any(value is None for value in retained_args):
            parser.error(
                "--score, --unit-scores, --report-dir, and --cycle-id must be "
                "provided together"
            )
        result = build_retained_hf_publication(
            RetainedHFPublicationConfig(
                score_path=args.score,
                unit_scores_path=args.unit_scores,
                report_dir=args.report_dir,
                output_dir=args.output_dir,
                cycle_id=args.cycle_id,
                release_version=args.release_version,
                dataset_repository=args.dataset_repository,
            )
        )
    else:
        if args.official_artifacts_dir is None:
            parser.error(
                "--official-artifacts-dir is required unless retained fan-in "
                "inputs are provided"
            )
        result = build_official_hf_publication(
            OfficialHFPublicationConfig(
                official_artifacts_dir=args.official_artifacts_dir,
                output_dir=args.output_dir,
                release_version=args.release_version,
                dataset_repository=args.dataset_repository,
                supplementary_artifacts_dir=args.supplementary_artifacts_dir,
            )
        )
    print(
        json.dumps({"cycle_id": result.cycle_id, "output_dir": str(result.output_dir)})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

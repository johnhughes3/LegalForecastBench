"""Community submission packaging and validation for multi-harness runs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, cast

from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
)
from legalforecast.multiharness.spec import (
    ArtifactRecord,
    ConformanceReport,
    ContributorCredit,
    RunManifest,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    optional_bool,
    optional_mapping,
    optional_non_negative_int,
    optional_sequence,
    optional_str,
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
    validate_unique_ids,
)
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)

COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_submission_manifest.v1"
)
COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_run_summary.v1"
)
COMMUNITY_SHARD_SCHEMA_VERSION = "legalforecast.multiharness.community_shard.v1"
COMMUNITY_ARTIFACT_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_artifact_manifest.v1"
)
COMMUNITY_PUBLIC_SUMMARY_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_public_summary.v1"
)
COMMUNITY_SELECTION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_selection_manifest.v1"
)
HF_UPLOAD_PLAN_SCHEMA_VERSION = "legalforecast.multiharness.hf_upload_plan.v1"

ATTEST_NOT_OFFICIAL = "not_official_legalforecastbench_result"
ATTEST_NO_PRIVATE_OR_SEALED = "no_private_or_sealed_material_in_public_artifacts"
ATTEST_RIGHT_TO_SUBMIT = "right_to_submit_artifacts"
ATTEST_PROVIDER_TERMS = "provider_terms_acknowledged"
REQUIRED_ATTESTATIONS = frozenset(
    {
        ATTEST_NOT_OFFICIAL,
        ATTEST_NO_PRIVATE_OR_SEALED,
        ATTEST_RIGHT_TO_SUBMIT,
        ATTEST_PROVIDER_TERMS,
    }
)
REQUIRED_CONTRIBUTOR_ROLES = frozenset(
    {
        "run_operator",
        "adapter_author",
        "task_source",
        "benchmark_infrastructure",
    }
)

_SUBMISSION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,96}$")


@dataclass(frozen=True, slots=True)
class CommunityArtifactReference:
    """Artifact reference included in a community submission package."""

    artifact_id: str
    path: str
    sha256: str
    media_type: str
    public: bool = True
    size_bytes: int | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        validate_safe_relative_path(self.path, "path")
        validate_sha256(self.sha256, "sha256")
        _require_non_empty(self.media_type, "media_type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise MultiHarnessValidationError("size_bytes must be non-negative")
        if self.source_url is not None:
            _validate_immutable_url(self.source_url)
        if self.public:
            _validate_public_artifact_path(self.path)
            validate_public_record(self.to_record(), "community_artifact")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "public": self.public,
        }
        if self.size_bytes is not None:
            record["size_bytes"] = self.size_bytes
        if self.source_url is not None:
            record["source_url"] = self.source_url
        return record

    def to_artifact_record(self) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=self.artifact_id,
            path=self.path,
            sha256=self.sha256,
            media_type=self.media_type,
            public=self.public,
            size_bytes=self.size_bytes,
        )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return cls(
            artifact_id=require_str(record, "artifact_id"),
            path=require_str(record, "path"),
            sha256=require_str(record, "sha256"),
            media_type=require_str(record, "media_type"),
            public=optional_bool(record, "public"),
            size_bytes=optional_non_negative_int(record, "size_bytes"),
            source_url=optional_str(record, "source_url"),
        )


@dataclass(frozen=True, slots=True)
class CommunityRunSummary:
    """Public summary for one submitted multi-harness run."""

    run_id: str
    run_manifest_sha256: str
    selection_sha256: str
    selection_label: str
    run_config_sha256: str
    row_count: int
    result_status_counts: Mapping[str, int]
    families: tuple[str, ...]
    scoring_modes: tuple[str, ...]
    adapter_ids: tuple[str, ...]
    model_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, "run_id")
        validate_sha256(self.run_manifest_sha256, "run_manifest_sha256")
        validate_sha256(self.selection_sha256, "selection_sha256")
        _require_non_empty(self.selection_label, "selection_label")
        validate_sha256(self.run_config_sha256, "run_config_sha256")
        if self.row_count <= 0:
            raise MultiHarnessValidationError("row_count must be positive")
        _validate_int_mapping(self.result_status_counts, "result_status_counts")
        for field_name, values in (
            ("families", self.families),
            ("adapter_ids", self.adapter_ids),
            ("model_keys", self.model_keys),
        ):
            _require_non_empty_tuple(values, field_name)
        for value in self.scoring_modes:
            _require_non_empty(value, "scoring_modes")
        validate_public_record(self.to_record(), "community_run_summary")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION,
            "run_id": self.run_id,
            "run_manifest_sha256": self.run_manifest_sha256,
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "run_config_sha256": self.run_config_sha256,
            "row_count": self.row_count,
            "result_status_counts": dict(sorted(self.result_status_counts.items())),
            "families": list(self.families),
            "scoring_modes": list(self.scoring_modes),
            "adapter_ids": list(self.adapter_ids),
            "model_keys": list(self.model_keys),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION)
        row_count = optional_non_negative_int(record, "row_count")
        if row_count is None:
            raise MultiHarnessValidationError("row_count is required")
        return cls(
            run_id=require_str(record, "run_id"),
            run_manifest_sha256=require_str(record, "run_manifest_sha256"),
            selection_sha256=require_str(record, "selection_sha256"),
            selection_label=require_str(record, "selection_label"),
            run_config_sha256=require_str(record, "run_config_sha256"),
            row_count=row_count,
            result_status_counts=_int_mapping(
                require_mapping(record, "result_status_counts"),
                "result_status_counts",
            ),
            families=_str_tuple(require_sequence(record, "families"), "families"),
            scoring_modes=_str_tuple(
                optional_sequence(record, "scoring_modes") or (),
                "scoring_modes",
            ),
            adapter_ids=_str_tuple(
                require_sequence(record, "adapter_ids"),
                "adapter_ids",
            ),
            model_keys=_str_tuple(require_sequence(record, "model_keys"), "model_keys"),
        )


@dataclass(frozen=True, slots=True)
class CommunitySubmissionShard:
    """One compatible partial-run shard in a community submission."""

    shard_id: str
    compatible_shard_group_id: str
    selection_sha256: str
    selection_label: str
    source_suite: str
    suite_version: str
    task_selectors: Mapping[str, Any]
    task_ids: tuple[str, ...]
    adapter_id: str
    adapter_version: str
    model_key: str
    sandbox_policy_hash: str
    run_config_hash: str
    contributor_credits: tuple[ContributorCredit, ...]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("shard_id", self.shard_id),
            ("compatible_shard_group_id", self.compatible_shard_group_id),
            ("selection_label", self.selection_label),
            ("source_suite", self.source_suite),
            ("suite_version", self.suite_version),
            ("adapter_id", self.adapter_id),
            ("adapter_version", self.adapter_version),
            ("model_key", self.model_key),
        ):
            _require_non_empty(value, field_name)
        validate_sha256(self.selection_sha256, "selection_sha256")
        validate_sha256(self.sandbox_policy_hash, "sandbox_policy_hash")
        validate_sha256(self.run_config_hash, "run_config_hash")
        _require_non_empty_tuple(self.task_ids, "task_ids")
        validate_unique_ids(self.task_ids, "task_ids")
        _require_contributor_roles(
            self.contributor_credits,
            REQUIRED_CONTRIBUTOR_ROLES,
            "contributor_credits",
        )
        validate_public_record(dict(self.task_selectors), "task_selectors")
        validate_public_record(self.to_record(), "community_shard")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_SHARD_SCHEMA_VERSION,
            "shard_id": self.shard_id,
            "compatible_shard_group_id": self.compatible_shard_group_id,
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "source_suite": self.source_suite,
            "suite_version": self.suite_version,
            "task_selectors": dict(self.task_selectors),
            "task_ids": list(self.task_ids),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_key": self.model_key,
            "sandbox_policy_hash": self.sandbox_policy_hash,
            "run_config_hash": self.run_config_hash,
            "contributor_credits": [
                credit.to_record() for credit in self.contributor_credits
            ],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_SHARD_SCHEMA_VERSION)
        return cls(
            shard_id=require_str(record, "shard_id"),
            compatible_shard_group_id=require_str(
                record,
                "compatible_shard_group_id",
            ),
            selection_sha256=require_str(record, "selection_sha256"),
            selection_label=require_str(record, "selection_label"),
            source_suite=require_str(record, "source_suite"),
            suite_version=require_str(record, "suite_version"),
            task_selectors=optional_mapping(record, "task_selectors") or {},
            task_ids=_str_tuple(require_sequence(record, "task_ids"), "task_ids"),
            adapter_id=require_str(record, "adapter_id"),
            adapter_version=require_str(record, "adapter_version"),
            model_key=require_str(record, "model_key"),
            sandbox_policy_hash=require_str(record, "sandbox_policy_hash"),
            run_config_hash=require_str(record, "run_config_hash"),
            contributor_credits=_credit_tuple(
                require_sequence(record, "contributor_credits")
            ),
        )


@dataclass(frozen=True, slots=True)
class CommunitySubmissionManifest:
    """PR-reviewed community submission manifest."""

    submission_id: str
    submitter: ContributorCredit
    contributors: tuple[ContributorCredit, ...]
    benchmark_credit: tuple[ContributorCredit, ...]
    run_summary: CommunityRunSummary
    artifacts: tuple[CommunityArtifactReference, ...]
    attestations: tuple[str, ...]
    shards: tuple[CommunitySubmissionShard, ...]

    def __post_init__(self) -> None:
        if _SUBMISSION_ID_PATTERN.fullmatch(self.submission_id) is None:
            raise MultiHarnessValidationError(
                "submission_id must be lowercase URL-safe text"
            )
        _require_contributor_roles(
            self.contributors,
            REQUIRED_CONTRIBUTOR_ROLES,
            "contributors",
        )
        _require_contributor_roles(
            self.benchmark_credit,
            frozenset({"benchmark_infrastructure"}),
            "benchmark_credit",
        )
        validate_unique_ids(
            (artifact.artifact_id for artifact in self.artifacts),
            "artifacts",
        )
        validate_unique_ids((shard.shard_id for shard in self.shards), "shards")
        missing = REQUIRED_ATTESTATIONS.difference(self.attestations)
        if missing:
            formatted = ", ".join(sorted(missing))
            raise MultiHarnessValidationError(
                f"attestations missing required value(s): {formatted}"
            )
        validate_public_record(self.to_record(), "community_submission_manifest")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION,
            "submission_id": self.submission_id,
            "submitter": self.submitter.to_record(),
            "contributors": [credit.to_record() for credit in self.contributors],
            "benchmark_credit": [
                credit.to_record() for credit in self.benchmark_credit
            ],
            "run_summary": self.run_summary.to_record(),
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "attestations": list(self.attestations),
            "shards": [shard.to_record() for shard in self.shards],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION)
        validate_public_record(record, "community_submission_manifest")
        return cls(
            submission_id=require_str(record, "submission_id"),
            submitter=ContributorCredit.from_record(
                require_mapping(record, "submitter")
            ),
            contributors=_credit_tuple(require_sequence(record, "contributors")),
            benchmark_credit=_credit_tuple(
                require_sequence(record, "benchmark_credit")
            ),
            run_summary=CommunityRunSummary.from_record(
                require_mapping(record, "run_summary")
            ),
            artifacts=_community_artifact_tuple(require_sequence(record, "artifacts")),
            attestations=_str_tuple(
                require_sequence(record, "attestations"),
                "attestations",
            ),
            shards=_community_shard_tuple(require_sequence(record, "shards")),
        )


@dataclass(frozen=True, slots=True)
class CommunityPackageConfig:
    """Inputs for turning a local run directory into a PR-ready package."""

    run_dir: Path
    output_dir: Path
    submission_id: str
    submitter: ContributorCredit
    contributors: tuple[ContributorCredit, ...]
    benchmark_credit: tuple[ContributorCredit, ...]
    attestations: tuple[str, ...]
    conformance_report_path: Path | None = None
    hf_upload_plan: bool = False


@dataclass(frozen=True, slots=True)
class CommunityPackageResult:
    """Files generated for a community submission package."""

    manifest: CommunitySubmissionManifest
    output_dir: Path
    artifact_manifest_path: Path
    submission_path: Path


def package_community_submission(
    config: CommunityPackageConfig,
) -> CommunityPackageResult:
    """Create a PR-ready community submission package from a local run directory."""

    if not config.run_dir.is_dir():
        raise ValueError(f"run directory does not exist: {config.run_dir}")
    config.output_dir.mkdir(parents=True, exist_ok=True)

    run_manifest_source = config.run_dir / "run-manifest.json"
    row_results_source = config.run_dir / "row-results.jsonl"
    run_manifest = RunManifest.from_record(_read_json(run_manifest_source, "run"))
    rows = _read_jsonl(row_results_source, "row results")
    if not rows:
        raise ValueError("row-results.jsonl must contain at least one row")
    conformance_source = config.conformance_report_path or (
        config.run_dir / "conformance-report.json"
    )
    conformance = ConformanceReport.from_record(
        _read_json(conformance_source, "conformance report")
    )

    copied_paths = _copy_run_public_artifacts(config.run_dir, config.output_dir)
    conformance_path = config.output_dir / "conformance-report.json"
    shutil.copy2(conformance_source, conformance_path)
    copied_paths.append(conformance_path)

    request_records = _request_records_for_rows(config.run_dir, rows)
    public_summary = _public_summary_record(
        run_manifest=run_manifest,
        rows=rows,
        requests=request_records,
        conformance=conformance,
        submission_id=config.submission_id,
    )
    public_summary_path = config.output_dir / "public-summary.json"
    write_json_object(public_summary_path, public_summary)

    selection_manifest = _selection_manifest_record(
        run_manifest=run_manifest,
        rows=rows,
        requests=request_records,
    )
    selection_manifest_path = config.output_dir / "selection-manifest.json"
    write_json_object(selection_manifest_path, selection_manifest)

    base_paths = [
        *copied_paths,
        public_summary_path,
        selection_manifest_path,
    ]
    base_artifacts = tuple(
        _artifact_reference_for(config.output_dir, path) for path in base_paths
    )
    artifact_manifest_path = config.output_dir / "artifact-manifest.json"
    write_json_object(
        artifact_manifest_path,
        {
            "schema_version": COMMUNITY_ARTIFACT_MANIFEST_SCHEMA_VERSION,
            "artifacts": [artifact.to_record() for artifact in base_artifacts],
        },
    )
    artifact_manifest_artifact = _artifact_reference_for(
        config.output_dir,
        artifact_manifest_path,
    )
    if config.hf_upload_plan:
        write_json_object(
            config.output_dir / "hf-upload-plan.json",
            _hf_upload_plan_record((*base_artifacts, artifact_manifest_artifact)),
        )

    manifest = CommunitySubmissionManifest(
        submission_id=config.submission_id,
        submitter=config.submitter,
        contributors=config.contributors,
        benchmark_credit=config.benchmark_credit,
        run_summary=CommunityRunSummary.from_record(public_summary["run_summary"]),
        artifacts=(*base_artifacts, artifact_manifest_artifact),
        attestations=tuple(sorted(set(config.attestations))),
        shards=_submission_shards(
            run_manifest=run_manifest,
            rows=rows,
            requests=request_records,
            contributors=config.contributors,
        ),
    )
    submission_path = config.output_dir / "submission.json"
    write_json_object(submission_path, manifest.to_record())
    validate_submission_file(submission_path)
    return CommunityPackageResult(
        manifest=manifest,
        output_dir=config.output_dir,
        artifact_manifest_path=artifact_manifest_path,
        submission_path=submission_path,
    )


def validate_submission_file(path: Path) -> CommunitySubmissionManifest:
    """Validate a submission manifest and its local artifact hashes."""

    manifest = CommunitySubmissionManifest.from_record(
        _read_json(path, "community submission")
    )
    validate_submission_manifest(manifest, root=path.parent)
    return manifest


def validate_submission_manifest(
    manifest: CommunitySubmissionManifest,
    *,
    root: Path | None = None,
) -> None:
    """Validate a parsed community submission manifest."""

    validate_public_record(manifest.to_record(), "community_submission_manifest")
    if root is None:
        return
    public_paths: list[Path] = []
    for artifact in manifest.artifacts:
        if artifact.source_url is not None:
            continue
        artifact_path = root / artifact.path
        if not artifact_path.is_file():
            raise ValueError(f"artifact does not exist: {artifact.path}")
        actual_sha256 = _file_sha256(artifact_path)
        if actual_sha256 != artifact.sha256:
            raise ValueError(
                f"artifact hash mismatch for {artifact.path}: "
                f"expected {artifact.sha256}, got {actual_sha256}"
            )
        if artifact.public:
            public_paths.append(artifact_path)
    if public_paths:
        enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))


def _copy_run_public_artifacts(run_dir: Path, output_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for relative in (
        "run-manifest.json",
        "row-results.jsonl",
        "canonical-runs.jsonl",
        "lab/task-results.jsonl",
        "lfb/runs.jsonl",
    ):
        source = run_dir / relative
        if not source.is_file():
            continue
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _public_summary_record(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
    conformance: ConformanceReport,
    submission_id: str,
) -> dict[str, Any]:
    summary = CommunityRunSummary(
        run_id=run_manifest.run_id,
        run_manifest_sha256=_file_sha256_from_record(run_manifest.to_record()),
        selection_sha256=run_manifest.selection_sha256,
        selection_label=_selection_label(requests),
        run_config_sha256=run_manifest.run_config_sha256,
        row_count=len(rows),
        result_status_counts=_counter_record(
            _required_row_str(row, "status") for row in rows
        ),
        families=_sorted_unique(_required_row_str(row, "family") for row in rows),
        scoring_modes=_sorted_unique(
            _request_task_field(request, "scoring_mode")
            for request in requests.values()
        ),
        adapter_ids=_sorted_unique(
            _required_row_str(row, "adapter_id") for row in rows
        ),
        model_keys=_sorted_unique(_required_row_str(row, "model_key") for row in rows),
    )
    return {
        "schema_version": COMMUNITY_PUBLIC_SUMMARY_SCHEMA_VERSION,
        "submission_id": submission_id,
        "run_summary": summary.to_record(),
        "conformance": {
            "report_id": conformance.report_id,
            "adapter_id": conformance.adapter_id,
            "adapter_version": conformance.adapter_version,
            "status": conformance.status,
        },
    }


def _selection_manifest_record(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    task_ids = tuple(_required_row_str(row, "task_id") for row in rows)
    return {
        "schema_version": COMMUNITY_SELECTION_MANIFEST_SCHEMA_VERSION,
        "run_id": run_manifest.run_id,
        "selection_sha256": run_manifest.selection_sha256,
        "selection_label": _selection_label(requests),
        "task_ids": list(task_ids),
        "task_selectors": {"task_ids": list(task_ids)},
        "families": list(
            _sorted_unique(_required_row_str(row, "family") for row in rows)
        ),
        "scoring_modes": list(
            _sorted_unique(
                _request_task_field(request, "scoring_mode")
                for request in requests.values()
            )
        ),
    }


def _submission_shards(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
    contributors: tuple[ContributorCredit, ...],
) -> tuple[CommunitySubmissionShard, ...]:
    groups: dict[tuple[str, str, str, str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        request = requests[_required_row_str(row, "row_id")]
        family = _required_row_str(row, "family")
        scoring_mode = _request_task_field(request, "scoring_mode")
        suite_version = _request_task_field(request, "suite_version")
        adapter_id = _required_row_str(row, "adapter_id")
        adapter_version = _required_row_str(row, "adapter_version")
        model_key = _required_row_str(row, "model_key")
        groups.setdefault(
            (
                family,
                scoring_mode,
                suite_version,
                adapter_id,
                adapter_version,
                model_key,
            ),
            [],
        ).append(row)

    shards: list[CommunitySubmissionShard] = []
    for index, (key, shard_rows) in enumerate(sorted(groups.items()), start=1):
        (
            family,
            scoring_mode,
            suite_version,
            adapter_id,
            adapter_version,
            model_key,
        ) = key
        task_ids = tuple(_required_row_str(row, "task_id") for row in shard_rows)
        sandbox_policy_hashes = tuple(
            sorted({_sandbox_policy_hash_for_row(row, requests) for row in shard_rows})
        )
        if len(sandbox_policy_hashes) != 1:
            raise MultiHarnessValidationError(
                "shard rows disagree on sandbox_policy_hash for "
                f"{family}:{scoring_mode}:{suite_version}:{adapter_id}:"
                f"{adapter_version}:{model_key}"
            )
        shards.append(
            CommunitySubmissionShard(
                shard_id=f"shard-{index:03d}",
                compatible_shard_group_id=(
                    f"{family}:{scoring_mode}:{suite_version}:"
                    f"{run_manifest.selection_sha256}"
                ),
                selection_sha256=run_manifest.selection_sha256,
                selection_label=_selection_label(requests),
                source_suite=family,
                suite_version=suite_version,
                task_selectors={"task_ids": list(task_ids)},
                task_ids=task_ids,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                model_key=model_key,
                sandbox_policy_hash=sandbox_policy_hashes[0],
                run_config_hash=run_manifest.run_config_sha256,
                contributor_credits=contributors,
            )
        )
    return tuple(shards)


def _request_records_for_rows(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    requests: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        row_id = _required_row_str(row, "row_id")
        workspace = _row_workspace(row)
        if not workspace.is_dir():
            workspace = run_dir / "rows" / row_id
        requests[row_id] = _read_json(workspace / "request.json", "run request")
    return requests


def _row_workspace(row: Mapping[str, Any]) -> Path:
    value = row.get("workspace")
    if isinstance(value, str) and value.strip():
        return Path(value)
    return Path("rows") / _required_row_str(row, "row_id")


def _artifact_reference_for(root: Path, path: Path) -> CommunityArtifactReference:
    relative = path.relative_to(root).as_posix()
    return CommunityArtifactReference(
        artifact_id=_artifact_id(relative),
        path=relative,
        sha256=_file_sha256(path),
        media_type=_media_type(path),
        public=True,
        size_bytes=path.stat().st_size,
    )


def _hf_upload_plan_record(
    artifacts: Sequence[CommunityArtifactReference],
) -> dict[str, Any]:
    return {
        "schema_version": HF_UPLOAD_PLAN_SCHEMA_VERSION,
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "path": artifact.path,
                "sha256": artifact.sha256,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
            }
            for artifact in artifacts
        ],
    }


def _read_json(path: Path, label: str) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    return read_jsonl_objects(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item, line: (
            f"{label} row {line} in {item} must be an object"
        ),
    )


def _credit_tuple(records: Sequence[Any]) -> tuple[ContributorCredit, ...]:
    return tuple(
        ContributorCredit.from_record(_require_item_mapping(item, "contributors"))
        for item in records
    )


def _community_artifact_tuple(
    records: Sequence[Any],
) -> tuple[CommunityArtifactReference, ...]:
    return tuple(
        CommunityArtifactReference.from_record(_require_item_mapping(item, "artifacts"))
        for item in records
    )


def _community_shard_tuple(
    records: Sequence[Any],
) -> tuple[CommunitySubmissionShard, ...]:
    return tuple(
        CommunitySubmissionShard.from_record(_require_item_mapping(item, "shards"))
        for item in records
    )


def _require_item_mapping(item: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(item, Mapping):
        raise MultiHarnessValidationError(f"{field_name} entries must be objects")
    return cast(Mapping[str, Any], item)


def _str_tuple(records: Sequence[Any], field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for item in records:
        if not isinstance(item, str) or not item.strip():
            raise MultiHarnessValidationError(
                f"{field_name} must contain non-empty strings"
            )
        values.append(item)
    return tuple(values)


def _int_mapping(record: Mapping[str, Any], field_name: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, value in record.items():
        if not key.strip():
            raise MultiHarnessValidationError(f"{field_name} keys must be strings")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise MultiHarnessValidationError(
                f"{field_name}.{key} must be a non-negative integer"
            )
        result[key] = value
    return result


def _validate_int_mapping(record: Mapping[str, int], field_name: str) -> None:
    for key, value in record.items():
        _require_non_empty(key, f"{field_name} key")
        if isinstance(value, bool) or value < 0:
            raise MultiHarnessValidationError(
                f"{field_name}.{key} must be a non-negative integer"
            )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise MultiHarnessValidationError(f"{field_name} must be non-empty")


def _require_non_empty_tuple(values: Sequence[str], field_name: str) -> None:
    if not values:
        raise MultiHarnessValidationError(f"{field_name} must not be empty")
    for value in values:
        _require_non_empty(value, field_name)


def _require_contributor_roles(
    contributors: Sequence[ContributorCredit],
    required_roles: frozenset[str],
    field_name: str,
) -> None:
    if not contributors:
        raise MultiHarnessValidationError(f"{field_name} must not be empty")
    roles = {credit.role for credit in contributors}
    missing = required_roles.difference(roles)
    if missing:
        formatted = ", ".join(sorted(missing))
        raise MultiHarnessValidationError(
            f"{field_name} missing required role(s): {formatted}"
        )


def _validate_immutable_url(value: str) -> None:
    if not value.startswith("https://"):
        raise MultiHarnessValidationError("source_url must be an https URL")
    lowered = value.lower()
    if any(marker in lowered for marker in ("/latest", "raw/main", "raw/master")):
        raise MultiHarnessValidationError(
            "source_url must be immutable, not a moving branch/latest URL"
        )


def _validate_public_artifact_path(path: str) -> None:
    lowered_parts = tuple(part.lower() for part in path.split("/"))
    if any(part.startswith("private") for part in lowered_parts):
        raise MultiHarnessValidationError(
            "public artifact paths must not include private path segments"
        )


def _required_row_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _request_task_field(request: Mapping[str, Any], field_name: str) -> str:
    task = require_mapping(request, "task")
    return require_str(task, field_name)


def _sandbox_policy_hash_for_row(
    row: Mapping[str, Any],
    requests: Mapping[str, Mapping[str, Any]],
) -> str:
    request = requests[_required_row_str(row, "row_id")]
    sandbox_policy = require_mapping(request, "sandbox_policy")
    return _file_or_record_sha256(
        _row_workspace(row) / "sandbox.plan.json",
        sandbox_policy,
    )


def _selection_label(requests: Mapping[str, Mapping[str, Any]]) -> str:
    for request in requests.values():
        task = require_mapping(request, "task")
        metadata = optional_mapping(task, "metadata") or {}
        value = metadata.get("selection_label")
        if isinstance(value, str) and value.strip():
            return value
    return "submitted-run"


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value.strip()}))


def _counter_record(values: Iterable[str]) -> dict[str, int]:
    counter: Counter[str] = Counter(values)
    return dict(sorted(counter.items()))


def _file_or_record_sha256(path: Path, record: Mapping[str, Any]) -> str:
    if path.is_file():
        return _file_sha256(path)
    return _file_sha256_from_record(record)


def _file_sha256_from_record(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _artifact_id(relative_path: str) -> str:
    return relative_path.removesuffix(".json").removesuffix(".jsonl").replace("/", ":")


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/jsonl"
    if suffix == ".md":
        return "text/markdown"
    if suffix in {".txt", ".log"}:
        return "text/plain"
    return "application/octet-stream"

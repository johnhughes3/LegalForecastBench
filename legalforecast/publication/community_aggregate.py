"""Community multi-harness aggregation and static report publication."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast._json_io import (
    read_json_object,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.multiharness.community import (
    CommunitySubmissionManifest,
    validate_submission_file,
)
from legalforecast.multiharness.reporting import (
    CommunityComparisonRow,
    render_community_comparison_csv,
    render_community_comparison_html,
    render_community_comparison_json,
    render_community_comparison_markdown,
)
from legalforecast.multiharness.spec import ArtifactRecord
from legalforecast.multiharness.validation import validate_public_record
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)
from legalforecast.publication.static_sites import render_community_results_site

COMMUNITY_AGGREGATE_BUNDLE_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_aggregate_bundle.v1"
)


@dataclass(frozen=True, slots=True)
class CommunityAggregateConfig:
    """Inputs for rebuilding the community aggregate bundle."""

    submissions_dir: Path
    output_dir: Path


@dataclass(frozen=True, slots=True)
class CommunitySubmissionInput:
    """Validated submission plus its package root."""

    path: Path
    root: Path
    manifest: CommunitySubmissionManifest


@dataclass(frozen=True, slots=True)
class CommunityAggregateResult:
    """Generated community aggregate bundle."""

    output_dir: Path
    rows: tuple[CommunityComparisonRow, ...]
    submission_count: int


@dataclass(slots=True)
class _GroupAccumulator:
    compatible_shard_group_id: str
    selection_sha256: str
    selection_label: str
    shards: list[dict[str, Any]]
    task_ids: set[str]


def build_community_aggregate(
    config: CommunityAggregateConfig,
) -> CommunityAggregateResult:
    """Build the reviewed community registry and static comparison reports."""

    submissions = _load_submission_inputs(config.submissions_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    registry_dir = config.output_dir / "registry"
    reports_dir = config.output_dir / "reports"
    public_submissions_dir = config.output_dir / "submissions"
    registry_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    public_submissions_dir.mkdir(parents=True, exist_ok=True)

    group_task_ids = _group_task_ids(submissions)
    rows = _comparison_rows(submissions, group_task_ids)
    registry_records = [_normalized_submission_record(item) for item in submissions]
    coverage_records = _coverage_records(rows)
    contributors = _contributor_index(submissions)
    adapter_model_index = _adapter_model_index(rows)
    shard_groups = _compatible_shard_groups(submissions, rows)

    write_jsonl_objects(registry_dir / "submissions.jsonl", registry_records)
    write_jsonl_objects(registry_dir / "task-coverage.jsonl", coverage_records)
    write_json_object(registry_dir / "contributors.json", contributors)
    write_json_object(registry_dir / "adapters-models.json", adapter_model_index)
    write_json_object(registry_dir / "compatible-shard-groups.json", shard_groups)
    write_json_object(
        registry_dir / "site-summary.json",
        _site_summary(submissions, rows, shard_groups),
    )
    for item in submissions:
        write_json_object(
            public_submissions_dir / f"{item.manifest.submission_id}.json",
            _normalized_submission_record(item),
        )

    _write_reports(reports_dir, rows)
    render_community_results_site(
        community_aggregate_dir=config.output_dir,
        output_dir=config.output_dir / "site",
    )
    enforce_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(config.output_dir,))
    )
    _write_artifact_manifests(config.output_dir)
    return CommunityAggregateResult(
        output_dir=config.output_dir,
        rows=tuple(rows),
        submission_count=len(submissions),
    )


def _load_submission_inputs(
    submissions_dir: Path,
) -> tuple[CommunitySubmissionInput, ...]:
    paths = tuple(sorted(submissions_dir.rglob("submission.json")))
    if not paths:
        raise ValueError(f"no community submissions found in {submissions_dir}")
    return tuple(
        CommunitySubmissionInput(
            path=path,
            root=path.parent,
            manifest=validate_submission_file(path),
        )
        for path in paths
    )


def _group_task_ids(
    submissions: Sequence[CommunitySubmissionInput],
) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for item in submissions:
        for shard in item.manifest.shards:
            groups.setdefault(shard.compatible_shard_group_id, set()).update(
                shard.task_ids
            )
    return groups


def _comparison_rows(
    submissions: Sequence[CommunitySubmissionInput],
    group_task_ids: Mapping[str, set[str]],
) -> list[CommunityComparisonRow]:
    rows: list[CommunityComparisonRow] = []
    strict_groups: dict[
        tuple[str, ...], list[tuple[CommunitySubmissionInput, int]]
    ] = {}
    for item in submissions:
        conformance_status = _conformance_status(item)
        for index, shard in enumerate(item.manifest.shards):
            family, scoring_mode = _family_and_scoring(shard.compatible_shard_group_id)
            group_size = len(group_task_ids[shard.compatible_shard_group_id])
            coverage = 100 * len(shard.task_ids) / group_size
            rows.append(
                CommunityComparisonRow(
                    row_id=f"{item.manifest.submission_id}:{shard.shard_id}",
                    row_type="single-shard",
                    submission_ids=(item.manifest.submission_id,),
                    shard_ids=(shard.shard_id,),
                    family=family,
                    scoring_mode=scoring_mode,
                    selection_sha256=shard.selection_sha256,
                    selection_label=shard.selection_label,
                    suite_version=shard.suite_version,
                    adapter_id=shard.adapter_id,
                    adapter_version=shard.adapter_version,
                    model_key=shard.model_key,
                    conformance_status=conformance_status,
                    task_count=len(shard.task_ids),
                    coverage_percentage=coverage,
                    status_counts=item.manifest.run_summary.result_status_counts,
                    contributor_credit=tuple(
                        credit.to_record() for credit in shard.contributor_credits
                    ),
                    artifact_ids=tuple(
                        artifact.artifact_id for artifact in item.manifest.artifacts
                    ),
                )
            )
            strict_groups.setdefault(_strict_composite_key(shard), []).append(
                (item, index)
            )
    rows.extend(_composite_rows(strict_groups, group_task_ids))
    return sorted(rows, key=lambda row: (row.family, row.model_key, row.row_id))


def _composite_rows(
    strict_groups: Mapping[
        tuple[str, ...], Sequence[tuple[CommunitySubmissionInput, int]]
    ],
    group_task_ids: Mapping[str, set[str]],
) -> list[CommunityComparisonRow]:
    rows: list[CommunityComparisonRow] = []
    for key, items in sorted(strict_groups.items()):
        if len(items) < 2:
            continue
        all_task_ids: list[str] = []
        for item, shard_index in items:
            all_task_ids.extend(item.manifest.shards[shard_index].task_ids)
        if len(all_task_ids) != len(set(all_task_ids)):
            continue
        first_item, first_index = items[0]
        first = first_item.manifest.shards[first_index]
        family, scoring_mode = _family_and_scoring(first.compatible_shard_group_id)
        group_size = len(group_task_ids[first.compatible_shard_group_id])
        status_counts: Counter[str] = Counter()
        for item, _shard_index in items:
            status_counts.update(item.manifest.run_summary.result_status_counts)
        submission_ids = tuple(item.manifest.submission_id for item, _ in items)
        shard_ids = tuple(item.manifest.shards[index].shard_id for item, index in items)
        rows.append(
            CommunityComparisonRow(
                row_id=f"composite:{_digest(':'.join(key))}",
                row_type="compatible-composite",
                submission_ids=submission_ids,
                shard_ids=shard_ids,
                family=family,
                scoring_mode=scoring_mode,
                selection_sha256=first.selection_sha256,
                selection_label=first.selection_label,
                suite_version=first.suite_version,
                adapter_id=first.adapter_id,
                adapter_version=first.adapter_version,
                model_key=first.model_key,
                conformance_status=_combined_conformance_status(items),
                task_count=len(all_task_ids),
                coverage_percentage=100 * len(all_task_ids) / group_size,
                status_counts=dict(sorted(status_counts.items())),
                contributor_credit=_dedupe_credit(
                    credit.to_record()
                    for item, index in items
                    for credit in item.manifest.shards[index].contributor_credits
                ),
                artifact_ids=tuple(
                    artifact.artifact_id
                    for item, _index in items
                    for artifact in item.manifest.artifacts
                ),
            )
        )
    return rows


def _coverage_records(rows: Sequence[CommunityComparisonRow]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.row_id,
            "row_type": row.row_type,
            "family": row.family,
            "scoring_mode": row.scoring_mode,
            "selection_sha256": row.selection_sha256,
            "model_key": row.model_key,
            "task_count": row.task_count,
            "coverage_percentage": row.coverage_percentage,
        }
        for row in rows
    ]


def _normalized_submission_record(item: CommunitySubmissionInput) -> dict[str, Any]:
    manifest = item.manifest
    record = {
        "submission_id": manifest.submission_id,
        "run_summary": manifest.run_summary.to_record(),
        "attestations": list(manifest.attestations),
        "contributors": [credit.to_record() for credit in manifest.contributors],
        "benchmark_credit": [
            credit.to_record() for credit in manifest.benchmark_credit
        ],
        "shards": [shard.to_record() for shard in manifest.shards],
        "artifact_ids": [artifact.artifact_id for artifact in manifest.artifacts],
    }
    validate_public_record(record, "normalized_submission")
    return record


def _contributor_index(
    submissions: Sequence[CommunitySubmissionInput],
) -> dict[str, Any]:
    entries: dict[tuple[str, str], set[str]] = {}
    for item in submissions:
        credits = (
            item.manifest.contributors
            + item.manifest.benchmark_credit
            + (item.manifest.submitter,)
        )
        for credit in credits:
            entries.setdefault((credit.role, credit.name), set()).add(
                item.manifest.submission_id
            )
    return {
        "contributors": [
            {
                "role": role,
                "name": name,
                "submissions": sorted(submission_ids),
            }
            for (role, name), submission_ids in sorted(entries.items())
        ]
    }


def _adapter_model_index(rows: Sequence[CommunityComparisonRow]) -> dict[str, Any]:
    adapters = sorted(
        {(row.adapter_id, row.adapter_version, row.conformance_status) for row in rows}
    )
    models = sorted({row.model_key for row in rows})
    return {
        "adapters": [
            {
                "adapter_id": adapter_id,
                "adapter_version": adapter_version,
                "conformance_status": status,
            }
            for adapter_id, adapter_version, status in adapters
        ],
        "models": [{"model_key": model_key} for model_key in models],
    }


def _compatible_shard_groups(
    submissions: Sequence[CommunitySubmissionInput],
    rows: Sequence[CommunityComparisonRow],
) -> dict[str, Any]:
    groups: dict[str, _GroupAccumulator] = {}
    for item in submissions:
        for shard in item.manifest.shards:
            entry = groups.setdefault(
                shard.compatible_shard_group_id,
                _GroupAccumulator(
                    compatible_shard_group_id=shard.compatible_shard_group_id,
                    selection_sha256=shard.selection_sha256,
                    selection_label=shard.selection_label,
                    shards=[],
                    task_ids=set(),
                ),
            )
            entry.shards.append(
                {
                    "submission_id": item.manifest.submission_id,
                    "shard_id": shard.shard_id,
                    "task_ids": list(shard.task_ids),
                }
            )
            entry.task_ids.update(shard.task_ids)
    composite_rows = [row for row in rows if row.row_type == "compatible-composite"]
    output_groups: list[dict[str, Any]] = []
    for entry in groups.values():
        output_groups.append(
            {
                "compatible_shard_group_id": entry.compatible_shard_group_id,
                "selection_sha256": entry.selection_sha256,
                "selection_label": entry.selection_label,
                "shards": entry.shards,
                "task_ids": sorted(entry.task_ids),
                "composite_rows": [
                    row.to_record()
                    for row in composite_rows
                    if row.selection_sha256 == entry.selection_sha256
                ],
            }
        )
    return {"groups": output_groups}


def _site_summary(
    submissions: Sequence[CommunitySubmissionInput],
    rows: Sequence[CommunityComparisonRow],
    shard_groups: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": COMMUNITY_AGGREGATE_BUNDLE_SCHEMA_VERSION,
        "submission_count": len(submissions),
        "row_count": len(rows),
        "families": sorted({row.family for row in rows}),
        "scoring_modes": sorted({row.scoring_mode for row in rows}),
        "rows": [row.to_record() for row in rows],
        "compatible_shard_groups": shard_groups["groups"],
    }


def _write_reports(output_dir: Path, rows: Sequence[CommunityComparisonRow]) -> None:
    (output_dir / "community-comparison.json").write_text(
        render_community_comparison_json(rows) + "\n",
        encoding="utf-8",
    )
    (output_dir / "community-comparison.csv").write_text(
        render_community_comparison_csv(rows),
        encoding="utf-8",
    )
    (output_dir / "community-comparison.md").write_text(
        render_community_comparison_markdown(rows),
        encoding="utf-8",
    )
    (output_dir / "community-comparison.html").write_text(
        render_community_comparison_html(rows),
        encoding="utf-8",
    )


def _write_artifact_manifests(output_dir: Path) -> None:
    artifacts = [
        _artifact_for(output_dir, path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
        and path.name not in {"artifact-index.json", "artifact-manifest.json"}
    ]
    write_json_object(
        output_dir / "artifact-manifest.json",
        {"artifacts": [artifact.to_record() for artifact in artifacts]},
    )
    artifact_manifest = _artifact_for(output_dir, output_dir / "artifact-manifest.json")
    write_json_object(
        output_dir / "artifact-index.json",
        {
            "schema_version": COMMUNITY_AGGREGATE_BUNDLE_SCHEMA_VERSION,
            "artifacts": [
                artifact.to_record() for artifact in (*artifacts, artifact_manifest)
            ],
        },
    )


def _artifact_for(root: Path, path: Path) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=path.relative_to(root).as_posix().replace("/", ":"),
        path=path.relative_to(root).as_posix(),
        sha256=_file_sha256(path),
        media_type=_media_type(path),
        public=True,
        size_bytes=path.stat().st_size,
    )


def _strict_composite_key(shard: Any) -> tuple[str, ...]:
    return (
        shard.compatible_shard_group_id,
        shard.suite_version,
        shard.adapter_id,
        shard.adapter_version,
        shard.model_key,
        shard.sandbox_policy_hash,
        shard.run_config_hash,
    )


def _family_and_scoring(group_id: str) -> tuple[str, str]:
    family, scoring_mode, _selection = group_id.split(":", 2)
    return family, scoring_mode


def _conformance_status(item: CommunitySubmissionInput) -> str:
    for artifact in item.manifest.artifacts:
        if artifact.path == "conformance-report.json":
            record = read_json_object(
                item.root / artifact.path,
                error_factory=ValueError,
                missing_message=lambda path: f"conformance report missing: {path}",
                non_object_message=lambda path: (
                    f"conformance report must be an object: {path}"
                ),
            )
            status = record.get("status")
            if isinstance(status, str) and status.strip():
                return status
    return "unknown"


def _combined_conformance_status(
    items: Sequence[tuple[CommunitySubmissionInput, int]],
) -> str:
    statuses = {_conformance_status(item) for item, _index in items}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    if statuses == {"passed"}:
        return "passed"
    return "mixed"


def _dedupe_credit(
    records: Iterable[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    deduped = {
        (str(record.get("role", "")), str(record.get("name", ""))): dict(record)
        for record in records
    }
    return tuple(deduped[key] for key in sorted(deduped))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/jsonl"
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".html":
        return "text/html"
    return "application/octet-stream"

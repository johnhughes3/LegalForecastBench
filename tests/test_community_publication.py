from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.multiharness.community import (
    ATTEST_NO_PRIVATE_OR_SEALED,
    ATTEST_NOT_OFFICIAL,
    ATTEST_PROVIDER_TERMS,
    ATTEST_RIGHT_TO_SUBMIT,
    CommunityArtifactReference,
    CommunityRunSummary,
    CommunitySubmissionManifest,
    CommunitySubmissionShard,
)
from legalforecast.multiharness.spec import (
    CONFORMANCE_REPORT_SCHEMA_VERSION,
    ContributorCredit,
)
from legalforecast.publication import community_aggregate
from legalforecast.publication.community_aggregate import (
    CommunityAggregateConfig,
    build_community_aggregate,
)
from legalforecast.publication.publication_guardrails import PublicationGuardrailError

JsonRecord = dict[str, Any]
SHA1 = "sha256:" + "1" * 64
SHA2 = "sha256:" + "2" * 64
SHA3 = "sha256:" + "3" * 64
SHA4 = "sha256:" + "4" * 64


def test_community_aggregate_outputs_registry_reports_and_composites(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-2",),
    )
    output_dir = tmp_path / "aggregate"

    assert (
        main(
            [
                "multiharness",
                "community",
                "aggregate",
                "--submissions-dir",
                str(submissions_dir),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    submissions = _read_jsonl(output_dir / "registry" / "submissions.jsonl")
    coverage = _read_jsonl(output_dir / "registry" / "task-coverage.jsonl")
    contributors = _read_json(output_dir / "registry" / "contributors.json")
    adapters_models = _read_json(output_dir / "registry" / "adapters-models.json")
    shard_groups = _read_json(output_dir / "registry" / "compatible-shard-groups.json")
    site_summary = _read_json(output_dir / "registry" / "site-summary.json")

    assert len(submissions) == 2
    assert any(row["row_type"] == "compatible-composite" for row in coverage)
    composite = next(
        row for row in coverage if row["row_type"] == "compatible-composite"
    )
    assert composite["coverage_percentage"] == 100
    assert any(
        item["role"] == "adapter_author" for item in contributors["contributors"]
    )
    assert adapters_models["models"] == [{"model_key": "fixture-model"}]
    assert shard_groups["groups"][0]["composite_rows"]
    assert site_summary["submission_count"] == 2
    assert (output_dir / "reports" / "community-comparison.json").is_file()
    assert (output_dir / "reports" / "community-comparison.csv").is_file()
    assert (output_dir / "reports" / "community-comparison.md").is_file()
    assert (output_dir / "reports" / "community-comparison.html").is_file()
    assert (output_dir / "submissions" / "fixture-one.json").is_file()
    artifact_manifest = _read_json(output_dir / "artifact-manifest.json")
    assert all(
        "private" not in artifact["path"] for artifact in artifact_manifest["artifacts"]
    )


def test_community_reports_keep_lfb_and_lab_sections_separate(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="lab-submission",
        task_ids=("lab-task",),
        family="harvey_lab",
        scoring_mode="lab_native",
    )
    _write_submission(
        submissions_dir,
        submission_id="lfb-submission",
        task_ids=("lfb-task",),
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
    )
    output_dir = tmp_path / "aggregate"

    build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=output_dir,
        )
    )

    markdown = (output_dir / "reports" / "community-comparison.md").read_text(
        encoding="utf-8"
    )
    assert "Harvey LAB (lab_native)" in markdown
    assert "LegalForecastBench/LFB (lfb_brier)" in markdown
    assert "family, scoring mode, and suite version" in markdown
    assert "selection hash" not in markdown
    assert "not ranked across incompatible metrics" in markdown


def test_community_aggregate_rejects_public_secret_leak(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="leaky-submission",
        task_ids=("task-1",),
        public_summary_text='{"OPENAI_API_KEY": "sk-secretsecret"}',
    )

    with pytest.raises(PublicationGuardrailError, match="secret"):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=submissions_dir,
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_skips_overlapping_composite(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-1",),
    )
    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=tmp_path / "aggregate",
        )
    )

    assert [row.row_type for row in result.rows] == ["single-shard", "single-shard"]


def test_community_aggregate_composes_disjoint_selection_run_configs(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1",),
        selection_sha256=SHA2,
        run_config_hash=SHA3,
    )
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-2",),
        selection_sha256=SHA4,
        run_config_hash=SHA4,
    )
    output_dir = tmp_path / "aggregate"

    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=output_dir,
        )
    )

    composite_rows = [
        row for row in result.rows if row.row_type == "compatible-composite"
    ]
    assert len(composite_rows) == 1
    assert composite_rows[0].task_count == 2
    submissions = _read_jsonl(output_dir / "registry" / "submissions.jsonl")
    assert {
        record["submission_id"]: record["shards"][0]["run_config_hash"]
        for record in submissions
    } == {"fixture-one": SHA3, "fixture-two": SHA4}


def test_community_aggregate_does_not_use_official_aggregate() -> None:
    source = inspect.getsource(community_aggregate)
    assert "official_aggregate" not in source


def _write_submission(
    submissions_dir: Path,
    *,
    submission_id: str,
    task_ids: tuple[str, ...],
    family: str = "harvey_lab",
    scoring_mode: str = "lab_native",
    public_summary_text: str | None = None,
    selection_sha256: str = SHA2,
    run_config_hash: str = SHA3,
) -> Path:
    root = submissions_dir / "2026" / submission_id
    root.mkdir(parents=True)
    public_summary_path = root / "public-summary.json"
    public_summary_path.write_text(
        public_summary_text
        or json.dumps({"submission_id": submission_id, "family": family}),
        encoding="utf-8",
    )
    conformance_path = root / "conformance-report.json"
    _write_json(
        conformance_path,
        {
            "schema_version": CONFORMANCE_REPORT_SCHEMA_VERSION,
            "report_id": f"{submission_id}-conformance",
            "adapter_id": "fixture-cli",
            "adapter_version": "0.1.0",
            "status": "passed",
            "checks": {"fixture": "passed: ok"},
            "artifacts": [],
        },
    )
    selection_path = root / "selection-manifest.json"
    _write_json(
        selection_path,
        {
            "schema_version": "fixture.selection.v1",
            "task_ids": list(task_ids),
            "family": family,
            "scoring_mode": scoring_mode,
        },
    )
    artifacts = (
        _artifact(root, public_summary_path, "public-summary"),
        _artifact(root, conformance_path, "conformance-report"),
        _artifact(root, selection_path, "selection-manifest"),
    )
    contributors = _contributors()
    run_summary = CommunityRunSummary(
        run_id=f"{submission_id}-run",
        run_manifest_sha256=SHA1,
        selection_sha256=selection_sha256,
        selection_label="fixture-selection",
        run_config_sha256=run_config_hash,
        row_count=len(task_ids),
        result_status_counts={"succeeded": len(task_ids)},
        families=(family,),
        scoring_modes=(scoring_mode,),
        adapter_ids=("fixture-cli",),
        model_keys=("fixture-model",),
    )
    shard = CommunitySubmissionShard(
        shard_id="shard-001",
        compatible_shard_group_id=(f"{family}:{scoring_mode}:{family}-fixture"),
        selection_sha256=selection_sha256,
        selection_label="fixture-selection",
        source_suite=family,
        suite_version=f"{family}-fixture",
        task_selectors={"task_ids": list(task_ids)},
        task_ids=task_ids,
        adapter_id="fixture-cli",
        adapter_version="0.1.0",
        model_key="fixture-model",
        sandbox_policy_hash=SHA1,
        run_config_hash=run_config_hash,
        contributor_credits=contributors,
    )
    manifest = CommunitySubmissionManifest(
        submission_id=submission_id,
        submitter=ContributorCredit(role="submitter", name="John Hughes"),
        contributors=contributors,
        benchmark_credit=(
            ContributorCredit(
                role="benchmark_infrastructure",
                name="LegalForecastBench",
            ),
        ),
        run_summary=run_summary,
        artifacts=artifacts,
        attestations=(
            ATTEST_NOT_OFFICIAL,
            ATTEST_NO_PRIVATE_OR_SEALED,
            ATTEST_RIGHT_TO_SUBMIT,
            ATTEST_PROVIDER_TERMS,
        ),
        shards=(shard,),
    )
    _write_json(root / "submission.json", manifest.to_record())
    return root


def _contributors() -> tuple[ContributorCredit, ...]:
    return (
        ContributorCredit(role="run_operator", name="John Hughes"),
        ContributorCredit(role="adapter_author", name="Fixture Adapter Authors"),
        ContributorCredit(role="task_source", name="Harvey LAB"),
        ContributorCredit(role="benchmark_infrastructure", name="LegalForecastBench"),
    )


def _artifact(
    root: Path,
    path: Path,
    artifact_id: str,
) -> CommunityArtifactReference:
    return CommunityArtifactReference(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=_file_sha256(path),
        media_type="application/json",
        public=True,
        size_bytes=path.stat().st_size,
    )


def _write_json(path: Path, payload: JsonRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text("utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)


def _read_jsonl(path: Path) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line in path.read_text("utf-8").splitlines():
        value = json.loads(line)
        assert isinstance(value, dict)
        records.append(cast(JsonRecord, value))
    return records


def _file_sha256(path: Path) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"

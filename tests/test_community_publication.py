from __future__ import annotations

import inspect
import json
from collections import Counter
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
    RUN_COMPATIBILITY_SCHEMA_VERSION,
    ContributorCredit,
    RunManifest,
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
    composite = composite_rows[0]
    assert composite.task_count == 2
    assert composite.selection_sha256 not in {SHA2, SHA4}
    assert composite.selection_label == "compatible composite (2 selections)"
    submissions = _read_jsonl(output_dir / "registry" / "submissions.jsonl")
    assert {
        record["submission_id"]: record["shards"][0]["run_config_hash"]
        for record in submissions
    } == {"fixture-one": SHA3, "fixture-two": SHA4}
    shard_groups = _read_json(output_dir / "registry" / "compatible-shard-groups.json")
    group = shard_groups["groups"][0]
    assert group["selection_sha256"] == composite.selection_sha256
    assert group["selection_label"] == "compatible shard group (2 selections)"
    assert {
        (selection["selection_sha256"], selection["selection_label"])
        for selection in group["selections"]
    } == {(SHA2, "fixture-selection"), (SHA4, "fixture-selection")}
    shard_provenance = {
        (
            shard["selection_sha256"],
            shard["run_config_hash"],
            shard["run_compatibility_hash"],
        )
        for shard in group["shards"]
    }
    assert {
        (selection, run_config) for selection, run_config, _ in shard_provenance
    } == {
        (SHA2, SHA3),
        (SHA4, SHA4),
    }
    compatibility_hashes = {compatibility for _, _, compatibility in shard_provenance}
    assert len(compatibility_hashes) == 1
    assert None not in compatibility_hashes
    assert [row["row_id"] for row in group["composite_rows"]] == [composite.row_id]


def test_community_aggregate_rejects_incompatible_run_configurations(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1",),
        selection_sha256=SHA2,
        run_config_hash=SHA3,
        run_compatibility_id="first",
    )
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-2",),
        selection_sha256=SHA4,
        run_config_hash=SHA4,
        run_compatibility_id="second",
    )

    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=tmp_path / "aggregate",
        )
    )

    assert [row.row_type for row in result.rows] == [
        "single-shard",
        "single-shard",
    ]


def test_legacy_shards_without_compatibility_hash_do_not_compose(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1",),
        run_compatibility_id=None,
    )
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-2",),
        run_compatibility_id=None,
    )

    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=tmp_path / "aggregate",
        )
    )

    assert [row.row_type for row in result.rows] == [
        "single-shard",
        "single-shard",
    ]


@pytest.mark.parametrize("forged_hash", [SHA2, None])
def test_community_aggregate_rejects_unbound_run_compatibility_hash(
    tmp_path: Path,
    forged_hash: str | None,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    record = _read_json(root / "submission.json")
    shard = cast(list[JsonRecord], record["shards"])[0]
    if forged_hash is None:
        shard.pop("run_compatibility_hash")
    else:
        shard["run_compatibility_hash"] = forged_hash
    _write_json(root / "submission.json", record)

    with pytest.raises(
        ValueError,
        match=r"run_compatibility_hash does not match run-manifest.json",
    ):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_recomputes_run_compatibility_preimage(
    tmp_path: Path,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    submission = _read_json(root / "submission.json")
    shard = cast(list[JsonRecord], submission["shards"])[0]
    shard["run_compatibility_hash"] = SHA2
    run_manifest_path = root / "run-manifest.json"
    run_manifest = _read_json(run_manifest_path)
    run_manifest["run_compatibility_sha256"] = SHA2
    _write_json(run_manifest_path, run_manifest)
    run_summary = cast(JsonRecord, submission["run_summary"])
    run_summary["run_manifest_sha256"] = _record_sha256(run_manifest)
    artifacts = cast(list[JsonRecord], submission["artifacts"])
    run_manifest_artifact = next(
        artifact for artifact in artifacts if artifact["path"] == "run-manifest.json"
    )
    run_manifest_artifact["sha256"] = _file_sha256(run_manifest_path)
    run_manifest_artifact["size_bytes"] = run_manifest_path.stat().st_size
    _write_json(root / "submission.json", submission)

    with pytest.raises(
        ValueError,
        match=r"run_compatibility_sha256 does not match run-compatibility.json",
    ):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_rejects_unroutable_shard_model_pair(
    tmp_path: Path,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    submission = _read_json(root / "submission.json")
    compatibility = _read_json(root / "run-compatibility.json")
    run_config = cast(JsonRecord, compatibility["run_config"])
    adapters = cast(list[JsonRecord], run_config["adapters"])
    adapters.append(
        {
            "adapter_id": "other-cli",
            "adapter_version": "0.2.0",
        }
    )
    model_configs = cast(list[JsonRecord], run_config["model_configs"])
    model_configs[0]["adapter_id"] = "fixture-cli"
    capabilities = cast(list[JsonRecord], compatibility["adapter_capabilities"])
    other_capabilities = dict(capabilities[0])
    other_capabilities.update(
        {
            "adapter_id": "other-cli",
            "adapter_version": "0.2.0",
        }
    )
    capabilities.append(other_capabilities)
    shard = cast(list[JsonRecord], submission["shards"])[0]
    shard["adapter_id"] = "other-cli"
    shard["adapter_version"] = "0.2.0"
    _rebind_run_compatibility(
        root,
        compatibility,
        submission_record=submission,
    )

    with pytest.raises(ValueError, match=r"model route is absent"):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_rejects_unsupported_shard_capability(
    tmp_path: Path,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    compatibility = _read_json(root / "run-compatibility.json")
    capabilities = cast(list[JsonRecord], compatibility["adapter_capabilities"])
    capabilities[0]["supported_families"] = ["legalforecast_mtd"]
    _rebind_run_compatibility(root, compatibility)

    with pytest.raises(ValueError, match=r"capability does not support shard"):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unknown-model-adapter", "model route references unknown adapter_id"),
        ("duplicate-model-route", "duplicate model route"),
        ("overlapping-model-route", "overlapping model routes"),
        ("duplicate-adapter-id", "duplicate adapter_id"),
    ],
)
def test_community_aggregate_rejects_ambiguous_compatibility_routes(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    compatibility = _read_json(root / "run-compatibility.json")
    run_config = cast(JsonRecord, compatibility["run_config"])
    if mutation == "unknown-model-adapter":
        model_configs = cast(list[JsonRecord], run_config["model_configs"])
        model_configs[0]["adapter_id"] = "missing-cli"
    elif mutation == "duplicate-model-route":
        model_configs = cast(list[JsonRecord], run_config["model_configs"])
        model_configs.append(dict(model_configs[0]))
    elif mutation == "overlapping-model-route":
        model_configs = cast(list[JsonRecord], run_config["model_configs"])
        adapter_route = dict(model_configs[0])
        adapter_route["adapter_id"] = "fixture-cli"
        model_configs.append(adapter_route)
    else:
        adapters = cast(list[JsonRecord], run_config["adapters"])
        adapters.append(
            {
                "adapter_id": "fixture-cli",
                "adapter_version": "0.2.0",
            }
        )
        capabilities = cast(
            list[JsonRecord],
            compatibility["adapter_capabilities"],
        )
        extra_capabilities = dict(capabilities[0])
        extra_capabilities["adapter_version"] = "0.2.0"
        capabilities.append(extra_capabilities)
    _rebind_run_compatibility(root, compatibility)

    with pytest.raises(ValueError, match=message):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_scans_run_compatibility_as_public_record(
    tmp_path: Path,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    submission = _read_json(root / "submission.json")
    for artifact in cast(list[JsonRecord], submission["artifacts"]):
        artifact["public"] = False
    compatibility = _read_json(root / "run-compatibility.json")
    run_config = cast(JsonRecord, compatibility["run_config"])
    sandbox_policy = cast(JsonRecord, run_config["sandbox_policy"])
    sandbox_policy["policy_id"] = "Authorization: Bearer fixturetoken"
    _rebind_run_compatibility(
        root,
        compatibility,
        submission_record=submission,
    )

    with pytest.raises(
        ValueError,
        match=r"run_compatibility.*authorization_header",
    ):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


@pytest.mark.parametrize(
    "field_level",
    [
        "root",
        "run_config",
        "task_index",
        "adapter",
        "model_config",
        "sandbox_policy",
        "adapter_capability",
    ],
)
def test_community_aggregate_rejects_extra_run_compatibility_fields(
    tmp_path: Path,
    field_level: str,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    compatibility = _read_json(root / "run-compatibility.json")
    run_config = cast(JsonRecord, compatibility["run_config"])
    targets = {
        "root": compatibility,
        "run_config": run_config,
        "task_index": cast(JsonRecord, run_config["task_index"]),
        "adapter": cast(list[JsonRecord], run_config["adapters"])[0],
        "model_config": cast(list[JsonRecord], run_config["model_configs"])[0],
        "sandbox_policy": cast(JsonRecord, run_config["sandbox_policy"]),
        "adapter_capability": cast(
            list[JsonRecord],
            compatibility["adapter_capabilities"],
        )[0],
    }
    targets[field_level]["telemetry"] = "extra"
    _rebind_run_compatibility(root, compatibility)

    with pytest.raises(ValueError, match=r"unexpected field.*telemetry"):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing-adapter-id", r"model_config.*missing field.*adapter_id"),
        ("missing-lfb-fixture", r"model_config.*missing field.*lfb_fixture"),
        ("nonboolean-lfb-fixture", r"lfb_fixture must be a boolean"),
        ("invalid-incomplete-policy", r"incomplete_run_policy must be one of"),
    ],
)
def test_community_aggregate_rejects_noncanonical_compatibility_values(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    compatibility = _read_json(root / "run-compatibility.json")
    run_config = cast(JsonRecord, compatibility["run_config"])
    model_config = cast(list[JsonRecord], run_config["model_configs"])[0]
    if mutation == "missing-adapter-id":
        model_config.pop("adapter_id")
    elif mutation == "missing-lfb-fixture":
        model_config.pop("lfb_fixture")
    elif mutation == "nonboolean-lfb-fixture":
        model_config["lfb_fixture"] = "false"
    else:
        run_config["incomplete_run_policy"] = "continue_anyway"
    _rebind_run_compatibility(root, compatibility)

    with pytest.raises(ValueError, match=message):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_community_aggregate_rejects_noncanonical_new_group_id(
    tmp_path: Path,
) -> None:
    root = _write_submission(
        tmp_path / "submissions",
        submission_id="fixture-one",
        task_ids=("task-1",),
    )
    record = _read_json(root / "submission.json")
    shard = cast(list[JsonRecord], record["shards"])[0]
    shard["compatible_shard_group_id"] = "harvey_lab:lab_native:wrong-suite"
    _write_json(root / "submission.json", record)

    with pytest.raises(
        ValueError,
        match="suite identity must match suite_version",
    ):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=tmp_path / "submissions",
                output_dir=tmp_path / "aggregate",
            )
        )


def test_composite_row_digest_uses_unambiguous_part_encoding() -> None:
    assert community_aggregate._digest_parts(("a:b", "c")) != (
        community_aggregate._digest_parts(("a", "b:c"))
    )


def test_community_aggregate_counts_statuses_per_shard(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    first_root = _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1", "task-extra"),
        result_statuses=("succeeded", "failed"),
    )
    _split_second_task_into_other_suite(first_root)
    _write_submission(
        submissions_dir,
        submission_id="fixture-two",
        task_ids=("task-2",),
        result_statuses=("skipped",),
    )

    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_dir,
            output_dir=tmp_path / "aggregate",
        )
    )

    rows = {row.row_id: row for row in result.rows}
    assert rows["fixture-one:shard-001"].status_counts == {"succeeded": 1}
    assert rows["fixture-one:shard-002"].status_counts == {"failed": 1}
    composite = next(
        row for row in result.rows if row.row_type == "compatible-composite"
    )
    assert composite.status_counts == {"skipped": 1, "succeeded": 1}


def test_community_aggregate_rejects_missing_declared_shard_row(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    root = _write_submission(
        submissions_dir,
        submission_id="fixture-one",
        task_ids=("task-1", "task-extra"),
        result_statuses=("succeeded", "failed"),
    )
    _split_second_task_into_other_suite(root)
    _replace_row_results(root, _read_jsonl(root / "row-results.jsonl")[:1])

    with pytest.raises(ValueError, match=r"missing .* declared shard row"):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=submissions_dir,
                output_dir=tmp_path / "aggregate",
            )
        )


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
    run_compatibility_id: str | None = "default",
    result_statuses: tuple[str, ...] | None = None,
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
    statuses = result_statuses or tuple("succeeded" for _ in task_ids)
    if len(statuses) != len(task_ids):
        raise ValueError("result_statuses must match task_ids")
    row_results_path = root / "row-results.jsonl"
    _write_jsonl(
        row_results_path,
        [
            {
                "row_id": f"row-{index}",
                "task_id": task_id,
                "family": family,
                "scoring_mode": scoring_mode,
                "adapter_id": "fixture-cli",
                "adapter_version": "0.1.0",
                "model_key": "fixture-model",
                "status": status,
            }
            for index, (task_id, status) in enumerate(
                zip(task_ids, statuses, strict=True),
                start=1,
            )
        ],
    )
    run_compatibility_record = (
        _run_compatibility_record(run_compatibility_id, family, scoring_mode)
        if run_compatibility_id is not None
        else None
    )
    run_compatibility_hash = (
        _record_sha256(run_compatibility_record)
        if run_compatibility_record is not None
        else None
    )
    run_compatibility_path = root / "run-compatibility.json"
    if run_compatibility_record is not None:
        _write_json(run_compatibility_path, run_compatibility_record)
    run_manifest = RunManifest(
        run_id=f"{submission_id}-run",
        selection_sha256=selection_sha256,
        run_config_sha256=run_config_hash,
        request_ids=tuple(f"row-{index}" for index in range(1, len(task_ids) + 1)),
        result_ids=tuple(
            f"row-{index}:result" for index in range(1, len(task_ids) + 1)
        ),
        run_compatibility_sha256=run_compatibility_hash,
    )
    run_manifest_path = root / "run-manifest.json"
    _write_json(run_manifest_path, run_manifest.to_record())
    artifact_paths = [
        public_summary_path,
        conformance_path,
        selection_path,
        row_results_path,
        run_manifest_path,
    ]
    if run_compatibility_record is not None:
        artifact_paths.append(run_compatibility_path)
    artifacts = tuple(_artifact(root, path, path.stem) for path in artifact_paths)
    contributors = _contributors()
    run_summary = CommunityRunSummary(
        run_id=f"{submission_id}-run",
        run_manifest_sha256=_record_sha256(run_manifest.to_record()),
        selection_sha256=selection_sha256,
        selection_label="fixture-selection",
        run_config_sha256=run_config_hash,
        row_count=len(task_ids),
        result_status_counts=dict(sorted(Counter(statuses).items())),
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
        run_compatibility_hash=run_compatibility_hash,
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


def _run_compatibility_record(
    compatibility_id: str,
    family: str,
    scoring_mode: str,
) -> JsonRecord:
    return {
        "schema_version": RUN_COMPATIBILITY_SCHEMA_VERSION,
        "run_config": {
            "task_index": {
                "index_id": f"fixture-index-{compatibility_id}",
                "index_sha256": SHA1,
                "selection_namespace": "fixture",
            },
            "adapters": [
                {
                    "adapter_id": "fixture-cli",
                    "adapter_version": "0.1.0",
                }
            ],
            "model_configs": [
                {
                    "adapter_id": None,
                    "model_key": "fixture-model",
                    "lfb_fixture": False,
                }
            ],
            "sandbox_policy": {
                "policy_id": "fixture",
                "policy_sha256": SHA2,
            },
            "incomplete_run_policy": "record_failure",
        },
        "adapter_capabilities": [
            {
                "schema_version": (
                    "legalforecast.multiharness.adapter_capabilities.v1"
                ),
                "adapter_id": "fixture-cli",
                "adapter_version": "0.1.0",
                "supported_families": [family],
                "supported_scoring_modes": [scoring_mode],
                "supports_sandbox_policy": True,
                "capabilities_sha256": SHA1,
            }
        ],
    }


def _split_second_task_into_other_suite(root: Path) -> None:
    record = _read_json(root / "submission.json")
    shards = cast(list[JsonRecord], record["shards"])
    first = dict(shards[0])
    second = dict(shards[0])
    first["task_ids"] = ["task-1"]
    first["task_selectors"] = {"task_ids": ["task-1"]}
    second["shard_id"] = "shard-002"
    second["task_ids"] = ["task-extra"]
    second["task_selectors"] = {"task_ids": ["task-extra"]}
    second["compatible_shard_group_id"] = "harvey_lab:lab_native:other-suite"
    second["suite_version"] = "other-suite"
    record["shards"] = [first, second]
    rows = _read_jsonl(root / "row-results.jsonl")
    _replace_row_results(root, rows, submission_record=record)


def _replace_row_results(
    root: Path,
    rows: list[JsonRecord],
    *,
    submission_record: JsonRecord | None = None,
) -> None:
    row_results_path = root / "row-results.jsonl"
    _write_jsonl(row_results_path, rows)
    record = submission_record or _read_json(root / "submission.json")
    artifacts = cast(list[JsonRecord], record["artifacts"])
    artifact = next(item for item in artifacts if item["path"] == "row-results.jsonl")
    artifact["sha256"] = _file_sha256(row_results_path)
    artifact["size_bytes"] = row_results_path.stat().st_size
    _write_json(root / "submission.json", record)


def _rebind_run_compatibility(
    root: Path,
    compatibility_record: JsonRecord,
    *,
    submission_record: JsonRecord | None = None,
) -> None:
    compatibility_path = root / "run-compatibility.json"
    _write_json(compatibility_path, compatibility_record)
    compatibility_hash = _record_sha256(compatibility_record)

    run_manifest_path = root / "run-manifest.json"
    run_manifest = _read_json(run_manifest_path)
    run_manifest["run_compatibility_sha256"] = compatibility_hash
    _write_json(run_manifest_path, run_manifest)

    submission = submission_record or _read_json(root / "submission.json")
    for shard in cast(list[JsonRecord], submission["shards"]):
        shard["run_compatibility_hash"] = compatibility_hash
    run_summary = cast(JsonRecord, submission["run_summary"])
    run_summary["run_manifest_sha256"] = _record_sha256(run_manifest)
    artifacts = cast(list[JsonRecord], submission["artifacts"])
    for path in (compatibility_path, run_manifest_path):
        artifact = next(
            item
            for item in artifacts
            if item["path"] == path.relative_to(root).as_posix()
        )
        artifact["sha256"] = _file_sha256(path)
        artifact["size_bytes"] = path.stat().st_size
    _write_json(root / "submission.json", submission)


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


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


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


def _record_sha256(record: JsonRecord) -> str:
    import hashlib

    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

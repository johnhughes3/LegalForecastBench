from __future__ import annotations

import hashlib
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
    REQUIRED_ATTESTATIONS,
    CommunityArtifactReference,
    CommunityPackageConfig,
    CommunitySubmissionManifest,
    package_community_submission,
    validate_submission_file,
)
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION,
    SOLVER_INPUT_LAYOUT_ID,
    SOLVER_INPUT_PAYLOAD_SCHEMA_VERSION,
)
from legalforecast.multiharness.spec import (
    ADAPTER_MANIFEST_SCHEMA_VERSION,
    CONFORMANCE_REPORT_SCHEMA_VERSION,
    RUN_COMPATIBILITY_SCHEMA_VERSION,
    RUN_MANIFEST_SCHEMA_VERSION,
    RUN_REQUEST_SCHEMA_VERSION,
    RUN_RESULT_SCHEMA_VERSION,
    SANDBOX_POLICY_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION,
    TOOL_REQUEST_SCHEMA_VERSION,
    ContributorCredit,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError
from legalforecast.publication.publication_guardrails import PublicationGuardrailError

JsonRecord = dict[str, Any]
SHA1 = "sha256:" + "1" * 64
SHA2 = "sha256:" + "2" * 64
SHA3 = "sha256:" + "3" * 64
SHA4 = "sha256:" + "4" * 64


def test_community_package_cli_writes_pr_ready_submission(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    output_dir = tmp_path / "community-submission"
    canonical_runs = _read_jsonl(run_dir / "canonical-runs.jsonl")
    canonical_runs[0]["artifacts"] = [
        {
            "artifact_id": "private-forecast",
            "path": "private-logs/forecast.json",
            "sha256": SHA1,
            "media_type": "application/json",
            "public": False,
            "size_bytes": 1,
        }
    ]
    _write_jsonl(run_dir / "canonical-runs.jsonl", canonical_runs)

    assert (
        main(
            [
                "multiharness",
                "community",
                "package",
                "--run-dir",
                str(run_dir),
                "--conformance-report",
                str(run_dir / "conformance-report.json"),
                "--output-dir",
                str(output_dir),
                "--submission-id",
                "fixture-submission",
                "--submitter-name",
                "John Hughes",
                "--submitter-github",
                "johnhughes3",
                "--run-operator-name",
                "John Hughes",
                "--adapter-author-name",
                "Fixture Adapter Authors",
                "--task-source-credit-name",
                "Harvey LAB",
                "--benchmark-credit-name",
                "LegalForecastBench",
                "--acknowledge-required-attestations",
                "--hf-upload-plan",
            ]
        )
        == 0
    )

    manifest = validate_submission_file(output_dir / "submission.json")
    assert manifest.submission_id == "fixture-submission"
    assert set(manifest.attestations) == REQUIRED_ATTESTATIONS
    assert manifest.run_summary.row_count == 1
    assert manifest.shards[0].compatible_shard_group_id == (
        "harvey_lab:lab_native:harvey-lab-fixture"
    )
    compatibility_record = _read_json(output_dir / "run-compatibility.json")
    assert manifest.shards[0].run_compatibility_hash == _record_sha256(
        compatibility_record
    )
    assert (output_dir / "public-summary.json").is_file()
    assert (output_dir / "conformance-report.json").is_file()
    assert (output_dir / "selection-manifest.json").is_file()
    assert (output_dir / "artifact-manifest.json").is_file()
    assert (output_dir / "hf-upload-plan.json").is_file()
    upload_plan = _read_json(output_dir / "hf-upload-plan.json")
    assert upload_plan["mirror_repository"] == (
        "https://huggingface.co/datasets/johnhughes3/"
        "legalforecastbench-community-artifacts"
    )
    assert upload_plan["revision_policy"] == "immutable-commit"
    packaged_rows = _read_jsonl(output_dir / "row-results.jsonl")
    assert "workspace" not in packaged_rows[0]
    packaged_runs = _read_jsonl(output_dir / "canonical-runs.jsonl")
    assert packaged_runs[0]["artifacts"] == []
    assert "private-logs" not in json.dumps(packaged_runs, sort_keys=True)


def test_missing_required_attestation_is_rejected(tmp_path: Path) -> None:
    record = _valid_submission_record(tmp_path)
    record["attestations"] = [
        ATTEST_NOT_OFFICIAL,
        ATTEST_NO_PRIVATE_OR_SEALED,
        ATTEST_RIGHT_TO_SUBMIT,
    ]

    with pytest.raises(MultiHarnessValidationError, match=ATTEST_PROVIDER_TERMS):
        CommunitySubmissionManifest.from_record(record)


def test_artifact_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    output_dir = _write_valid_package(tmp_path)
    (output_dir / "public-summary.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        validate_submission_file(output_dir / "submission.json")


@pytest.mark.parametrize("commit_length", (40, 64))
def test_mirrored_artifact_requires_designated_hf_commit_url(
    commit_length: int,
) -> None:
    artifact = CommunityArtifactReference(
        artifact_id="large-public-output",
        path="large-public-output.jsonl",
        sha256=SHA1,
        media_type="application/jsonl",
        source_url=(
            "https://huggingface.co/datasets/johnhughes3/"
            "legalforecastbench-community-artifacts/resolve/"
            f"{'a' * commit_length}/nested/large-public-output.jsonl"
        ),
    )

    assert artifact.source_url is not None


@pytest.mark.parametrize(
    "artifact_path",
    (
        "../output.jsonl",
        "./output.jsonl",
        ".hidden/output.jsonl",
        "nested//output.jsonl",
        "nested/",
        "%2e%2e/output.jsonl",
        "nested/%2E/output.jsonl",
        "nested%2foutput.jsonl",
        "nested%5Coutput.jsonl",
        "%252e%252e/output.jsonl",
        "nested%252foutput.jsonl",
        "nested%255Coutput.jsonl",
    ),
)
def test_mirrored_artifact_rejects_unsafe_resolved_path(
    artifact_path: str,
) -> None:
    source_url = (
        "https://huggingface.co/datasets/johnhughes3/"
        "legalforecastbench-community-artifacts/resolve/"
        f"{'a' * 40}/{artifact_path}"
    )

    with pytest.raises(
        MultiHarnessValidationError,
        match="source_url artifact path",
    ):
        CommunityArtifactReference(
            artifact_id="large-public-output",
            path="large-public-output.jsonl",
            sha256=SHA1,
            media_type="application/jsonl",
            source_url=source_url,
        )


@pytest.mark.parametrize(
    "source_url",
    [
        (
            "https://huggingface.co/datasets/johnhughes3/"
            "legalforecastbench-community-artifacts/resolve/main/output.jsonl"
        ),
        (
            "https://huggingface.co/datasets/another-owner/"
            f"another-repo/resolve/{'a' * 40}/output.jsonl"
        ),
        (
            "https://huggingface.co/datasets/johnhughes3/"
            "legalforecastbench-community-artifacts/resolve/"
            f"{'a' * 40}/output.jsonl?download=true"
        ),
    ],
)
def test_mutable_or_unapproved_mirror_url_is_rejected(source_url: str) -> None:
    with pytest.raises(MultiHarnessValidationError, match="source_url"):
        CommunityArtifactReference(
            artifact_id="large-public-output",
            path="large-public-output.jsonl",
            sha256=SHA1,
            media_type="application/jsonl",
            source_url=source_url,
        )


def test_unsafe_public_artifact_path_is_rejected(tmp_path: Path) -> None:
    output_dir = _write_valid_package(tmp_path)
    unsafe_path = output_dir / "source-documents" / "raw.json"
    unsafe_path.parent.mkdir(parents=True)
    unsafe_path.write_text("{}", encoding="utf-8")
    record = _read_json(output_dir / "submission.json")
    artifacts = cast(list[JsonRecord], record["artifacts"])
    artifacts.append(
        {
            "artifact_id": "unsafe-raw",
            "path": "source-documents/raw.json",
            "sha256": _file_sha256(unsafe_path),
            "media_type": "application/json",
            "public": True,
            "size_bytes": unsafe_path.stat().st_size,
        }
    )
    _write_json(output_dir / "submission.json", record)

    with pytest.raises(PublicationGuardrailError, match="private path"):
        validate_submission_file(output_dir / "submission.json")


def test_legacy_public_classification_fields_are_rejected(tmp_path: Path) -> None:
    record = _valid_submission_record(tmp_path)
    record["result_tier"] = "verified-community"

    with pytest.raises(
        MultiHarnessValidationError,
        match="prohibited legacy public classification",
    ):
        CommunitySubmissionManifest.from_record(record)


def test_shard_compatibility_fields_are_required(tmp_path: Path) -> None:
    record = _valid_submission_record(tmp_path)
    shard = cast(dict[str, Any], cast(list[Any], record["shards"])[0])
    shard.pop("compatible_shard_group_id")

    with pytest.raises(MultiHarnessValidationError, match="compatible_shard_group_id"):
        CommunitySubmissionManifest.from_record(record)


def test_package_splits_shards_by_suite_version(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    _append_run_row(
        run_dir,
        row_id="row-2",
        suite_version="harvey-lab-fixture-v2",
    )
    output_dir = tmp_path / "submission-package"

    result = package_community_submission(_package_config(run_dir, output_dir))

    manifest = validate_submission_file(result.submission_path)
    assert len(manifest.shards) == 2
    assert sorted(shard.suite_version for shard in manifest.shards) == [
        "harvey-lab-fixture",
        "harvey-lab-fixture-v2",
    ]
    assert all(
        shard.compatible_shard_group_id.endswith(f":{shard.suite_version}")
        for shard in manifest.shards
    )


def test_package_group_id_is_independent_of_partial_selection_hash(
    tmp_path: Path,
) -> None:
    first_run = _write_run_dir(tmp_path / "first")
    second_run = _write_run_dir(tmp_path / "second")
    _set_run_selection_sha256(second_run, SHA4)

    first = package_community_submission(
        _package_config(first_run, tmp_path / "first-package")
    ).manifest
    second = package_community_submission(
        _package_config(second_run, tmp_path / "second-package")
    ).manifest

    assert first.run_summary.selection_sha256 != second.run_summary.selection_sha256
    assert first.shards[0].compatible_shard_group_id == (
        second.shards[0].compatible_shard_group_id
    )
    assert first.shards[0].compatible_shard_group_id == (
        "harvey_lab:lab_native:harvey-lab-fixture"
    )


def test_package_revalidates_successful_live_container_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    _mark_first_row_live(run_dir, receipt_sha256=SHA1)
    calls: list[Path] = []
    expected_tree = _read_json(
        run_dir / "rows" / "row-1" / "private-logs" / "solver-input-manifest.json"
    )["input_tree_sha256"]

    def _validate(*args: object, **kwargs: object) -> str:
        receipt_path = kwargs.get("receipt_path", args[0] if args else None)
        assert isinstance(receipt_path, Path)
        assert kwargs["input_tree_sha256"] == expected_tree
        calls.append(receipt_path)
        return SHA1

    monkeypatch.setattr(
        "legalforecast.multiharness.community.validate_container_resume",
        _validate,
    )

    package_community_submission(
        _package_config(run_dir, tmp_path / "submission-package")
    )

    assert calls == [
        run_dir
        / "rows"
        / "row-1"
        / "private-logs"
        / "tool-container"
        / "execution-receipt.json"
    ]


def test_package_plan_only_legacy_run_does_not_require_compatibility(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    (run_dir / "run-compatibility.json").unlink()
    manifest_path = run_dir / "run-manifest.json"
    manifest = _read_json(manifest_path)
    del manifest["run_compatibility_sha256"]
    _write_json(manifest_path, manifest)

    result = package_community_submission(
        _package_config(run_dir, tmp_path / "submission-package")
    )

    assert result.submission_path.is_file()


def test_package_projects_legacy_canonical_result_without_artifacts(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    canonical_runs = _read_jsonl(run_dir / "canonical-runs.jsonl")
    del canonical_runs[0]["artifacts"]
    _write_jsonl(run_dir / "canonical-runs.jsonl", canonical_runs)

    result = package_community_submission(
        _package_config(run_dir, tmp_path / "submission-package")
    )

    packaged_runs = _read_jsonl(result.output_dir / "canonical-runs.jsonl")
    assert packaged_runs[0]["artifacts"] == []


def test_package_accepts_current_container_compatibility_fields(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    compatibility_path = run_dir / "run-compatibility.json"
    compatibility = _read_json(compatibility_path)
    compatibility["run_config"]["container_execution"] = "live_tools"
    compatibility["adapter_capabilities"][0]["tool_protocol_version"] = (
        TOOL_REQUEST_SCHEMA_VERSION
    )
    _write_json(compatibility_path, compatibility)
    manifest_path = run_dir / "run-manifest.json"
    manifest = _read_json(manifest_path)
    manifest["run_compatibility_sha256"] = _record_sha256(compatibility)
    _write_json(manifest_path, manifest)

    package = package_community_submission(
        _package_config(run_dir, tmp_path / "submission-package")
    )

    assert package.manifest.run_summary.row_count == 1


@pytest.mark.parametrize("tool_protocol_version", (None, "unsupported.v0"))
def test_package_rejects_live_compatibility_without_current_tool_protocol(
    tmp_path: Path,
    tool_protocol_version: str | None,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    compatibility_path = run_dir / "run-compatibility.json"
    compatibility = _read_json(compatibility_path)
    compatibility["run_config"]["container_execution"] = "live_tools"
    if tool_protocol_version is not None:
        compatibility["adapter_capabilities"][0]["tool_protocol_version"] = (
            tool_protocol_version
        )
    _write_json(compatibility_path, compatibility)
    manifest_path = run_dir / "run-manifest.json"
    manifest = _read_json(manifest_path)
    manifest["run_compatibility_sha256"] = _record_sha256(compatibility)
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="live_tools requires every adapter"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "submission-package")
        )


def test_package_rejects_mismatched_live_container_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    _mark_first_row_live(run_dir, receipt_sha256=SHA1)
    monkeypatch.setattr(
        "legalforecast.multiharness.community.validate_container_resume",
        lambda *_args, **_kwargs: SHA2,
    )

    with pytest.raises(ValueError, match="receipt commitment"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "submission-package")
        )


def test_package_rejects_solver_input_manifest_not_bound_to_run(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    _mark_first_row_live(run_dir, receipt_sha256=SHA1)
    manifest_path = (
        run_dir / "rows" / "row-1" / "private-logs" / "solver-input-manifest.json"
    )
    manifest = _read_json(manifest_path)
    manifest["solver_input_index_sha256"] = SHA3
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="index does not match"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "submission-package")
        )


def test_package_rejects_boolean_solver_input_size(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    _mark_first_row_live(run_dir, receipt_sha256=SHA1)
    manifest_path = (
        run_dir / "rows" / "row-1" / "private-logs" / "solver-input-manifest.json"
    )
    manifest = _read_json(manifest_path)
    materialization = cast(JsonRecord, manifest["materialization"])
    entries = cast(list[JsonRecord], materialization["entries"])
    entries[0]["size_bytes"] = True
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="materialized prompt does not match"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "submission-package")
        )


def test_package_scrubs_lfb_raw_output_from_public_submission(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    lfb_runs_path = run_dir / "lfb" / "runs.jsonl"
    _write_jsonl(
        lfb_runs_path,
        [
            {
                "sample_id": "sample-1",
                "raw_output": "private chain of thought and provider transcript",
                "raw_output_sha256": SHA4,
                "score": 0.12,
            }
        ],
    )
    output_dir = tmp_path / "submission-package"

    package_community_submission(_package_config(run_dir, output_dir))

    copied = _read_jsonl(output_dir / "lfb" / "runs.jsonl")
    assert copied == [
        {
            "sample_id": "sample-1",
            "raw_output_sha256": SHA4,
            "score": 0.12,
        }
    ]
    assert '"raw_output"' not in (output_dir / "lfb" / "runs.jsonl").read_text(
        encoding="utf-8"
    )


def test_package_rejects_mixed_sandbox_policy_hash_in_one_shard(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    _append_run_row(
        run_dir,
        row_id="row-2",
        suite_version="harvey-lab-fixture",
        sandbox_timeout_seconds=31,
    )

    with pytest.raises(MultiHarnessValidationError, match="sandbox_policy_hash"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "submission-package")
        )


def test_required_credit_roles_are_enforced(tmp_path: Path) -> None:
    record = _valid_submission_record(tmp_path)
    record["contributors"] = [
        item
        for item in cast(list[JsonRecord], record["contributors"])
        if item["role"] != "adapter_author"
    ]

    with pytest.raises(MultiHarnessValidationError, match="adapter_author"):
        CommunitySubmissionManifest.from_record(record)


def _valid_submission_record(tmp_path: Path) -> JsonRecord:
    output_dir = _write_valid_package(tmp_path)
    return _read_json(output_dir / "submission.json")


def _write_valid_package(tmp_path: Path) -> Path:
    run_dir = _write_run_dir(tmp_path)
    output_dir = tmp_path / "submission-package"
    assert (
        main(
            [
                "multiharness",
                "community",
                "package",
                "--run-dir",
                str(run_dir),
                "--conformance-report",
                str(run_dir / "conformance-report.json"),
                "--output-dir",
                str(output_dir),
                "--submission-id",
                "fixture-submission",
                "--submitter-name",
                "John Hughes",
                "--run-operator-name",
                "John Hughes",
                "--adapter-author-name",
                "Fixture Adapter Authors",
                "--task-source-credit-name",
                "Harvey LAB",
                "--benchmark-credit-name",
                "LegalForecastBench",
                "--attestation",
                ATTEST_NOT_OFFICIAL,
                "--attestation",
                ATTEST_NO_PRIVATE_OR_SEALED,
                "--attestation",
                ATTEST_RIGHT_TO_SUBMIT,
                "--attestation",
                ATTEST_PROVIDER_TERMS,
            ]
        )
        == 0
    )
    return output_dir


def _package_config(run_dir: Path, output_dir: Path) -> CommunityPackageConfig:
    return CommunityPackageConfig(
        run_dir=run_dir,
        output_dir=output_dir,
        submission_id="fixture-submission",
        submitter=ContributorCredit(role="submitter", name="John Hughes"),
        contributors=(
            ContributorCredit(role="run_operator", name="John Hughes"),
            ContributorCredit(role="adapter_author", name="Fixture Adapter Authors"),
            ContributorCredit(role="task_source", name="Harvey LAB"),
            ContributorCredit(
                role="benchmark_infrastructure",
                name="LegalForecastBench",
            ),
        ),
        benchmark_credit=(
            ContributorCredit(
                role="benchmark_infrastructure",
                name="LegalForecastBench",
            ),
        ),
        attestations=tuple(sorted(REQUIRED_ATTESTATIONS)),
        conformance_report_path=run_dir / "conformance-report.json",
    )


def _mark_first_row_live(run_dir: Path, *, receipt_sha256: str) -> None:
    rows = _read_jsonl(run_dir / "row-results.jsonl")
    rows[0]["container_execution"] = {
        "mode": "live_tools",
        "status": "succeeded",
        "receipt_sha256": receipt_sha256,
    }
    _write_jsonl(run_dir / "row-results.jsonl", rows)
    canonical_result = _read_jsonl(run_dir / "canonical-runs.jsonl")[0]
    _write_json(
        run_dir / "rows" / "row-1" / "result.json",
        canonical_result,
    )
    compatibility_path = run_dir / "run-compatibility.json"
    compatibility = _read_json(compatibility_path)
    compatibility["run_config"]["solver_input_index_sha256"] = SHA2
    _write_json(compatibility_path, compatibility)
    manifest_path = run_dir / "run-manifest.json"
    run_manifest = _read_json(manifest_path)
    run_manifest["run_compatibility_sha256"] = _record_sha256(compatibility)
    _write_json(manifest_path, run_manifest)
    request = _read_json(run_dir / "rows" / "row-1" / "request.json")
    request["task"]["metadata"]["prompt_sha256"] = SHA1
    _write_json(run_dir / "rows" / "row-1" / "request.json", request)
    private_logs = run_dir / "rows" / "row-1" / "private-logs"
    private_logs.mkdir(parents=True, exist_ok=True)
    _write_json(
        private_logs / "solver-input-manifest.json",
        _solver_input_manifest(request),
    )


def _solver_input_manifest(request: JsonRecord) -> JsonRecord:
    task = cast(JsonRecord, request["task"])
    prompt_file = {
        "source_path": "tasks/fixture/prompt.txt",
        "destination_path": SOLVER_INPUT_ENTRY_PATH,
        "media_type": "text/plain",
        "sha256": SHA1,
        "size_bytes": 1,
        "solver_visible": True,
    }
    source_file = {
        "source_path": "tasks/fixture/source/model-packet.json",
        "destination_path": "source/model-packet.json",
        "media_type": "application/json",
        "sha256": task["task_sha256"],
        "size_bytes": 1,
        "solver_visible": False,
    }
    tree_sha256 = _record_sha256_with_newline(
        {
            "schema_version": SOLVER_INPUT_PAYLOAD_SCHEMA_VERSION,
            "files": [
                {
                    "destination_path": SOLVER_INPUT_ENTRY_PATH,
                    "media_type": "text/plain",
                    "sha256": SHA1,
                    "size_bytes": 1,
                }
            ],
        }
    )
    solver_entry = {
        "task_id": task["task_id"],
        "task_sha256": task["task_sha256"],
        "prompt_sha256": SHA1,
        "entrypoint_path": SOLVER_INPUT_ENTRY_PATH,
        "files": [prompt_file, source_file],
        "tree_sha256": tree_sha256,
    }
    materialization_content = {
        "schema_version": "legalforecast.multiharness.task_materialization.v1",
        "task_id": task["task_id"],
        "task_sha256": task["task_sha256"],
        "layout_id": SOLVER_INPUT_LAYOUT_ID,
        "entries": [
            {
                "artifact_id": "solver_input:0",
                "source_path": "tasks/fixture/prompt.txt",
                "destination_path": SOLVER_INPUT_ENTRY_PATH,
                "sha256": SHA1.removeprefix("sha256:"),
                "size_bytes": 1,
            }
        ],
        "evaluator_private_artifact_ids": [],
        "semantic_bytes_sha256": "1" * 64,
        "total_size_bytes": 1,
    }
    materialization = {
        **materialization_content,
        "manifest_sha256": _bare_record_sha256(materialization_content),
    }
    return {
        "schema_version": SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION,
        "task_id": task["task_id"],
        "task_sha256": task["task_sha256"],
        "entrypoint_path": SOLVER_INPUT_ENTRY_PATH,
        "input_tree_sha256": tree_sha256,
        "solver_input_index_sha256": SHA2,
        "solver_input_entry": solver_entry,
        "materialization": materialization,
    }


def _write_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    row_dir = run_dir / "rows" / "row-1"
    row_dir.mkdir(parents=True)
    run_compatibility = {
        "schema_version": RUN_COMPATIBILITY_SCHEMA_VERSION,
        "run_config": {
            "task_index": {
                "index_id": "fixture-index",
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
                "supported_families": ["harvey_lab"],
                "supported_scoring_modes": ["lab_native"],
                "supports_sandbox_policy": True,
                "capabilities_sha256": SHA1,
            }
        ],
    }
    _write_json(run_dir / "run-compatibility.json", run_compatibility)
    run_manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "run_id": "fixture-run",
        "selection_sha256": SHA1,
        "run_config_sha256": SHA2,
        "run_compatibility_sha256": _record_sha256(run_compatibility),
        "request_ids": ["row-1"],
        "result_ids": ["row-1:result"],
    }
    _write_json(run_dir / "run-manifest.json", run_manifest)
    row = {
        "row_id": "row-1",
        "task_id": "harvey_lab:corporate/merger",
        "family": "harvey_lab",
        "adapter_id": "fixture-cli",
        "adapter_version": "0.1.0",
        "model_key": "fixture-model",
        "request_id": "row-1",
        "request_sha256": SHA3,
        "result_id": "row-1:result",
        "status": "succeeded",
        "workspace": row_dir.as_posix(),
        "resumed": False,
    }
    _write_jsonl(run_dir / "row-results.jsonl", [row])
    _write_jsonl(
        run_dir / "canonical-runs.jsonl",
        [
            {
                "schema_version": RUN_RESULT_SCHEMA_VERSION,
                "result_id": "row-1:result",
                "request_id": "row-1",
                "status": "succeeded",
                "result_sha256": SHA4,
                "artifacts": [],
                "public_summary": {"task_id": "harvey_lab:corporate/merger"},
            }
        ],
    )
    request = {
        "schema_version": RUN_REQUEST_SCHEMA_VERSION,
        "request_id": "row-1",
        "task": {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": "harvey_lab:corporate/merger",
            "family": "harvey_lab",
            "scoring_mode": "lab_native",
            "suite_version": "harvey-lab-fixture",
            "source_id": "merger-review",
            "task_sha256": SHA1,
            "metadata": {"selection_label": "fixture-selection"},
            "artifacts": [],
        },
        "adapter": {
            "schema_version": ADAPTER_MANIFEST_SCHEMA_VERSION,
            "adapter_id": "fixture-cli",
            "display_name": "Fixture CLI Adapter",
            "adapter_version": "0.1.0",
            "command": ["fixture-cli"],
            "contributors": [],
        },
        "model_key": "fixture-model",
        "sandbox_policy": {
            "schema_version": SANDBOX_POLICY_SCHEMA_VERSION,
            "policy_id": "fixture-sandbox",
            "backend": "docker",
            "image": "python:3.12-slim",
            "network_policy": "none",
            "timeout_seconds": 30,
            "mounts": [],
            "working_directory": "/workspace",
            "uid_gid": None,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "pids_limit": 256,
            "memory_limit": "2g",
            "cpu_limit": "1",
            "allowed_provider_env_vars": [],
        },
        "request_sha256": SHA3,
    }
    _write_json(row_dir / "request.json", request)
    _write_json(
        row_dir / "sandbox.plan.json",
        {"backend": "docker", "argv": [], "policy": request["sandbox_policy"]},
    )
    _write_json(
        run_dir / "conformance-report.json",
        {
            "schema_version": CONFORMANCE_REPORT_SCHEMA_VERSION,
            "report_id": "conformance-fixture",
            "adapter_id": "fixture-cli",
            "adapter_version": "0.1.0",
            "status": "passed",
            "checks": {"fixture": "passed: ok"},
            "artifacts": [],
        },
    )
    return run_dir


def _set_run_selection_sha256(run_dir: Path, selection_sha256: str) -> None:
    run_manifest = _read_json(run_dir / "run-manifest.json")
    run_manifest["selection_sha256"] = selection_sha256
    _write_json(run_dir / "run-manifest.json", run_manifest)


def _append_run_row(
    run_dir: Path,
    *,
    row_id: str,
    suite_version: str,
    sandbox_timeout_seconds: int = 30,
) -> None:
    row_dir = run_dir / "rows" / row_id
    row_dir.mkdir(parents=True)
    task_id = f"harvey_lab:corporate/{row_id}"
    rows = _read_jsonl(run_dir / "row-results.jsonl")
    row = dict(rows[0])
    row.update(
        {
            "row_id": row_id,
            "task_id": task_id,
            "request_id": row_id,
            "result_id": f"{row_id}:result",
            "workspace": row_dir.as_posix(),
        }
    )
    rows.append(row)
    _write_jsonl(run_dir / "row-results.jsonl", rows)

    canonical_runs = _read_jsonl(run_dir / "canonical-runs.jsonl")
    canonical_result = dict(canonical_runs[0])
    canonical_result.update(
        {
            "result_id": f"{row_id}:result",
            "request_id": row_id,
            "public_summary": {"task_id": task_id},
        }
    )
    canonical_runs.append(canonical_result)
    _write_jsonl(run_dir / "canonical-runs.jsonl", canonical_runs)

    run_manifest = _read_json(run_dir / "run-manifest.json")
    request_ids = cast(list[str], run_manifest["request_ids"])
    result_ids = cast(list[str], run_manifest["result_ids"])
    request_ids.append(row_id)
    result_ids.append(f"{row_id}:result")
    _write_json(run_dir / "run-manifest.json", run_manifest)

    request = _read_json(run_dir / "rows" / "row-1" / "request.json")
    request["request_id"] = row_id
    request["request_sha256"] = SHA3
    task = cast(JsonRecord, request["task"])
    task["task_id"] = task_id
    task["suite_version"] = suite_version
    task["source_id"] = f"merger-review-{row_id}"
    sandbox_policy = cast(JsonRecord, request["sandbox_policy"])
    sandbox_policy["policy_id"] = f"{row_id}-sandbox"
    sandbox_policy["timeout_seconds"] = sandbox_timeout_seconds
    _write_json(row_dir / "request.json", request)
    _write_json(
        row_dir / "sandbox.plan.json",
        {"backend": "docker", "argv": [], "policy": request["sandbox_policy"]},
    )


def _write_json(path: Path, payload: JsonRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        "utf-8",
    )


def _record_sha256(record: JsonRecord) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _bare_record_sha256(record: JsonRecord) -> str:
    return _record_sha256(record).removeprefix("sha256:")


def _record_sha256_with_newline(record: JsonRecord) -> str:
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _read_jsonl(path: Path) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line in path.read_text("utf-8").splitlines():
        value = json.loads(line)
        assert isinstance(value, dict)
        records.append(cast(JsonRecord, value))
    return records


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text("utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)


def _file_sha256(path: Path) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _credit(role: str, name: str) -> ContributorCredit:
    return ContributorCredit(role=role, name=name)

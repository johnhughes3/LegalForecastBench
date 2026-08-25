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
    _validate_canonical_run_aggregate,
    _validate_release_harness_receipts,
    package_community_submission,
    validate_submission_file,
)
from legalforecast.multiharness.release_adapters import NeutralApiFixtureAdapter
from legalforecast.multiharness.release_harness import release_record_sha256
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION,
    SOLVER_INPUT_LAYOUT_ID,
    SOLVER_INPUT_PAYLOAD_SCHEMA_VERSION,
    SolverInputStore,
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
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.multiharness.validation import MultiHarnessValidationError
from legalforecast.publication.publication_guardrails import PublicationGuardrailError
from legalforecast.release.synthetic import issue_synthetic_release

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
    _write_json(run_dir / "rows" / "row-1" / "result.json", canonical_runs[0])

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


def test_package_emits_v2_summary_when_score_artifacts_exist(tmp_path: Path) -> None:
    import hashlib

    from legalforecast.multiharness.community import (
        COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2,
        CommunityRunSummary,
    )
    from legalforecast.multiharness.scoring import (
        SCORE_ARTIFACT_SCHEMA_VERSION,
        ScoreArtifact,
    )

    run_dir = _write_run_dir(tmp_path)
    content = {
        "schema_version": SCORE_ARTIFACT_SCHEMA_VERSION,
        "evaluation_receipt_sha256": SHA1,
        "evaluation_spec_sha256": SHA2,
        "raw_result_sha256": SHA3,
        "metric_definition_sha256": SHA4,
        "score_value": 1,
        "unit": "binary",
        "n_passed": 23,
        "n_criteria": 23,
    }
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    score = ScoreArtifact(
        **content,
        score_sha256="sha256:" + hashlib.sha256(encoded).hexdigest(),
    )
    _write_jsonl(run_dir / "score-artifacts.jsonl", [score.to_record()])
    output_dir = tmp_path / "v2-package"
    result = package_community_submission(_package_config(run_dir, output_dir))
    summary = result.manifest.run_summary
    assert summary.schema_version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2
    assert summary.artifact_bindings is not None
    assert summary.artifact_bindings.score_artifact_sha256 == score.score_sha256
    assert summary.coverage_kind == "full"
    assert summary.claim_kind == "full"
    restored = CommunityRunSummary.from_v2_record(summary.to_record())
    assert restored.artifact_bindings is not None
    assert restored.artifact_bindings.score_artifact_sha256 == score.score_sha256
    assert (output_dir / "score-artifacts.jsonl").is_file()


def test_missing_run_selection_manifest_fails_closed_on_package(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    (run_dir / "selection-manifest.json").unlink(missing_ok=True)

    with pytest.raises(MultiHarnessValidationError, match="selection-manifest"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "missing-selection")
        )


def test_package_preserves_release_harness_receipts(tmp_path: Path) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    receipts = _read_jsonl(run_dir / "release-harness-receipts.jsonl")
    lfb_records = _read_jsonl(run_dir / "lfb/runs.jsonl")
    output_dir = tmp_path / "release-receipt-package"

    package_community_submission(_package_config(run_dir, output_dir))

    assert _read_jsonl(output_dir / "release-harness-receipts.jsonl") == receipts
    assert _read_jsonl(output_dir / "lfb/runs.jsonl") == lfb_records


def test_package_rejects_forged_release_lfb_projection(tmp_path: Path) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    lfb_records = _read_jsonl(run_dir / "lfb/runs.jsonl")
    parser_output = cast(JsonRecord, lfb_records[0]["parser_output"])
    parser_output["is_valid"] = False
    _write_jsonl(run_dir / "lfb/runs.jsonl", lfb_records)

    with pytest.raises(ValueError, match="release LFB aggregate does not match"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "forged-release-lfb")
        )


def test_unscoreable_release_row_packages_receipt_without_lfb_record(
    tmp_path: Path,
) -> None:
    run_dir = _write_release_run_dir(tmp_path, task_offset=2)
    output_dir = tmp_path / "unscoreable-release-package"

    package_community_submission(_package_config(run_dir, output_dir))

    receipts = _read_jsonl(output_dir / "release-harness-receipts.jsonl")
    assert len(receipts) == 1
    assert receipts[0]["unit_id"] == "unit-003"
    assert receipts[0]["should_score"] is False
    assert not (run_dir / "lfb/runs.jsonl").exists()
    assert not (output_dir / "lfb/runs.jsonl").exists()


def test_package_rejects_invalid_release_harness_receipt(tmp_path: Path) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    receipt = _read_jsonl(run_dir / "release-harness-receipts.jsonl")[0]
    _write_jsonl(
        run_dir / "release-harness-receipts.jsonl",
        [
            {
                **receipt,
                "receipt_sha256": SHA1,
            }
        ],
    )

    with pytest.raises(ValueError, match="digest does not match"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "invalid-release-receipt")
        )


def test_package_rejects_semantically_empty_release_harness_receipt(
    tmp_path: Path,
) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    content = {
        "schema_version": "legalforecast.multiharness.release_harness_receipt.v1",
        "receipt_id": "fixture-receipt",
    }
    _write_jsonl(
        run_dir / "release-harness-receipts.jsonl",
        [
            {
                **content,
                "receipt_sha256": release_record_sha256(content),
            }
        ],
    )

    with pytest.raises(ValueError, match="fields are invalid"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "empty-release-receipt")
        )


def test_package_rejects_self_rehashed_release_receipt_not_bound_to_rows(
    tmp_path: Path,
) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    receipt = _read_jsonl(run_dir / "release-harness-receipts.jsonl")[0]
    adapter = cast(JsonRecord, receipt["adapter"])
    adapter["model_key"] = "forged-model"
    receipt["treatment_id"] = (
        f"{receipt['harness_track']}:{adapter['adapter_id']}:"
        f"{adapter['adapter_version']}:forged-model"
    )
    content = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = release_record_sha256(content)
    _write_jsonl(run_dir / "release-harness-receipts.jsonl", [receipt])

    with pytest.raises(ValueError, match="does not match run rows"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "forged-release-receipt")
        )


def test_package_rejects_symlinked_release_receipt_aggregate(tmp_path: Path) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    receipt_path = run_dir / "release-harness-receipts.jsonl"
    outside = tmp_path / "outside-release-harness-receipts.jsonl"
    receipt_path.rename(outside)
    receipt_path.symlink_to(outside)

    with pytest.raises(ValueError, match="unavailable or invalid"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "symlinked-release-receipt")
        )


def test_package_uses_one_request_snapshot_after_release_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    row_id = cast(str, _read_jsonl(run_dir / "row-results.jsonl")[0]["row_id"])
    request_path = run_dir / "rows" / row_id / "request.json"
    original_request = _read_json(request_path)
    original_suite = cast(JsonRecord, original_request["task"])["suite_version"]
    original_validate = _validate_release_harness_receipts

    def mutate_after_validation(*args: Any, **kwargs: Any):
        receipts = original_validate(*args, **kwargs)
        mutated = _read_json(request_path)
        cast(JsonRecord, mutated["task"])["suite_version"] = "forged-suite"
        _write_json(request_path, mutated)
        return receipts

    monkeypatch.setattr(
        "legalforecast.multiharness.community._validate_release_harness_receipts",
        mutate_after_validation,
    )
    output_dir = tmp_path / "request-snapshot-package"

    result = package_community_submission(_package_config(run_dir, output_dir))

    assert result.manifest.shards[0].suite_version == original_suite
    assert "forged-suite" not in (output_dir / "submission.json").read_text("utf-8")


def test_package_uses_reconstructed_lfb_snapshot_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _write_release_run_dir(tmp_path)
    lfb_path = run_dir / "lfb/runs.jsonl"
    expected = _read_jsonl(lfb_path)
    original_validate = _validate_release_harness_receipts

    def mutate_after_validation(*args: Any, **kwargs: Any):
        artifacts = original_validate(*args, **kwargs)
        forged = _read_jsonl(lfb_path)
        cast(JsonRecord, forged[0]["parser_output"])["is_valid"] = False
        _write_jsonl(lfb_path, forged)
        return artifacts

    monkeypatch.setattr(
        "legalforecast.multiharness.community._validate_release_harness_receipts",
        mutate_after_validation,
    )
    output_dir = tmp_path / "lfb-snapshot-package"

    package_community_submission(_package_config(run_dir, output_dir))

    assert _read_jsonl(output_dir / "lfb/runs.jsonl") == expected


@pytest.mark.parametrize(
    "field_name",
    [
        "task_id",
        "family",
        "scoring_mode",
        "adapter_id",
        "adapter_version",
        "model_key",
        "request_id",
        "request_sha256",
        "result_id",
        "status",
    ],
)
def test_package_rejects_row_claim_drift(tmp_path: Path, field_name: str) -> None:
    run_dir = _write_run_dir(tmp_path)
    rows = _read_jsonl(run_dir / "row-results.jsonl")
    rows[0][field_name] = SHA1 if field_name.endswith("sha256") else "forged"
    _write_jsonl(run_dir / "row-results.jsonl", rows)

    with pytest.raises(ValueError, match=field_name):
        package_community_submission(
            _package_config(run_dir, tmp_path / f"forged-{field_name}")
        )


def test_package_rejects_duplicate_row_id(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    rows = _read_jsonl(run_dir / "row-results.jsonl")
    _write_jsonl(run_dir / "row-results.jsonl", [rows[0], dict(rows[0])])

    with pytest.raises(ValueError, match="duplicate row_id"):
        package_community_submission(_package_config(run_dir, tmp_path / "duplicate"))


def test_package_rejects_durable_result_request_mismatch(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    result_path = run_dir / "rows" / "row-1" / "result.json"
    result = _read_json(result_path)
    result["request_id"] = "forged-request"
    _write_json(result_path, result)

    with pytest.raises(ValueError, match="result does not match run request"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "result-request-mismatch")
        )


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_package_rejects_linked_required_source(tmp_path: Path, link_kind: str) -> None:
    run_dir = _write_run_dir(tmp_path)
    source = run_dir / "canonical-runs.jsonl"
    outside = tmp_path / f"outside-{link_kind}.jsonl"
    source.rename(outside)
    if link_kind == "symlink":
        source.symlink_to(outside)
    else:
        source.hardlink_to(outside)

    with pytest.raises(ValueError, match="unavailable or invalid"):
        package_community_submission(
            _package_config(run_dir, tmp_path / f"linked-{link_kind}")
        )


def test_package_uses_canonical_snapshot_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _write_run_dir(tmp_path)
    expected = _read_jsonl(run_dir / "canonical-runs.jsonl")
    original_validate = _validate_canonical_run_aggregate

    def mutate_after_validation(*args: Any, **kwargs: Any) -> None:
        original_validate(*args, **kwargs)
        forged = _read_jsonl(run_dir / "canonical-runs.jsonl")
        cast(JsonRecord, forged[0]["public_summary"])["task_id"] = "forged"
        _write_jsonl(run_dir / "canonical-runs.jsonl", forged)

    monkeypatch.setattr(
        "legalforecast.multiharness.community._validate_canonical_run_aggregate",
        mutate_after_validation,
    )
    output_dir = tmp_path / "canonical-snapshot"

    package_community_submission(_package_config(run_dir, output_dir))

    assert _read_jsonl(output_dir / "canonical-runs.jsonl") == expected


def test_package_rejects_forged_generic_lfb_projection(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    inspect_record = _bind_generic_lfb_record(run_dir)
    forged = dict(inspect_record)
    forged["score"] = 0.99
    _write_jsonl(run_dir / "lfb" / "runs.jsonl", [forged])

    with pytest.raises(ValueError, match="generic LFB aggregate does not match"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "forged-generic-lfb")
        )


def test_package_requires_fresh_output_directory(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    output_dir = tmp_path / "existing-output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="must be fresh"):
        package_community_submission(_package_config(run_dir, output_dir))


def test_unknown_coverage_kind_fails_closed_on_package(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    _write_json(
        run_dir / "selection-manifest.json",
        {
            "schema_version": "legalforecast.multiharness.selection_manifest.v1",
            "selection_sha256": SHA1,
            "selection_label": "full",
            "coverage_kind": "scope",
            "claim_kind": "full",
            "task_ids": ["harvey_lab:corporate/merger"],
        },
    )

    with pytest.raises(MultiHarnessValidationError, match="coverage_kind"):
        package_community_submission(
            _package_config(run_dir, tmp_path / "unknown-coverage")
        )


def test_row_scoped_coverage_cannot_be_packaged_as_full(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    _write_json(
        run_dir / "selection-manifest.json",
        {
            "schema_version": "legalforecast.multiharness.selection_manifest.v1",
            "selection_sha256": SHA1,
            "selection_label": "full",
            "coverage_kind": "full",
            "claim_kind": "full",
            "task_ids": ["harvey_lab:corporate/merger"],
        },
    )
    rows = _read_jsonl(run_dir / "row-results.jsonl")
    rows[0]["coverage_kind"] = "scoped"
    _write_jsonl(run_dir / "row-results.jsonl", rows)

    with pytest.raises(MultiHarnessValidationError, match="scoped"):
        package_community_submission(_package_config(run_dir, tmp_path / "row-scoped"))


def test_deleting_scoped_selection_label_fails_claim_validation(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path)
    _write_json(
        run_dir / "selection-manifest.json",
        {
            "schema_version": "legalforecast.multiharness.selection_manifest.v1",
            "selection_sha256": SHA1,
            "selection_label": "scoped:task_ids",
            "coverage_kind": "scoped",
            "claim_kind": "scoped",
            "task_ids": ["harvey_lab:corporate/merger"],
        },
    )
    output_dir = tmp_path / "scoped-submission"
    package_community_submission(_package_config(run_dir, output_dir))
    validate_submission_file(output_dir / "submission.json")

    submission_path = output_dir / "submission.json"
    record = _read_json(submission_path)
    record["run_summary"]["selection_label"] = "full"
    _write_json(submission_path, record)

    with pytest.raises(MultiHarnessValidationError, match="scoped selection_label"):
        validate_submission_file(submission_path)


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
    inspect_record = {
        "sample_id": "sample-1",
        "raw_output": "private chain of thought and provider transcript",
        "raw_output_sha256": SHA4,
        "score": 0.12,
    }
    _write_jsonl(lfb_runs_path, [inspect_record])
    _write_json(run_dir / "rows" / "row-1" / "lfb-inspect-record.json", inspect_record)
    result = _read_json(run_dir / "rows" / "row-1" / "result.json")
    result["result_sha256"] = _record_sha256(inspect_record)
    _write_json(run_dir / "rows" / "row-1" / "result.json", result)
    _write_jsonl(run_dir / "canonical-runs.jsonl", [result])
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


def _write_release_run_dir(tmp_path: Path, *, task_offset: int = 0) -> Path:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[task_offset]
    unit_id = cast(str, task.metadata["unit_id"])
    adapter = NeutralApiFixtureAdapter(
        raw_output=(
            '{"case_assessment":"fixture","predictions":'
            f'[{{"unit_id":"{unit_id}","probability_fully_dismissed":0.5}}]}}'
        )
    )
    run_dir = tmp_path / "release-run"
    run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    model_key="neutral:fixture",
                    adapter_id=adapter.manifest.adapter_id,
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="release-community-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
                timeout_seconds=30,
                network_policy="none",
            ),
            output_dir=run_dir,
            selection=TaskSelection(task_ids=(task.task_id,)),
            solver_inputs=SolverInputStore.load(solver_root),
            incomplete_run_policy="fail_fast",
        )
    )
    _write_json(
        run_dir / "conformance-report.json",
        {
            "schema_version": CONFORMANCE_REPORT_SCHEMA_VERSION,
            "report_id": "release-neutral-conformance",
            "adapter_id": adapter.manifest.adapter_id,
            "adapter_version": adapter.manifest.adapter_version,
            "status": "passed",
            "checks": {"release_fixture": "passed: provider-free release run"},
            "artifacts": [],
        },
    )
    return run_dir


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
        "task_record_sha256": _record_sha256_with_newline(task),
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
        "scoring_mode": "lab_native",
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
        row_dir / "result.json", _read_jsonl(run_dir / "canonical-runs.jsonl")[0]
    )
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
    _write_json(
        run_dir / "selection-manifest.json",
        {
            "schema_version": "legalforecast.multiharness.selection_manifest.v1",
            "selection_sha256": SHA1,
            "selection_label": "fixture-selection",
            "coverage_kind": "full",
            "claim_kind": "full",
            "task_ids": ["harvey_lab:corporate/merger"],
        },
    )
    return run_dir


def _bind_generic_lfb_record(run_dir: Path) -> JsonRecord:
    inspect_record: JsonRecord = {
        "sample_id": "sample-1",
        "raw_output": "private chain of thought and provider transcript",
        "raw_output_sha256": SHA4,
        "score": 0.12,
    }
    _write_jsonl(run_dir / "lfb" / "runs.jsonl", [inspect_record])
    _write_json(run_dir / "rows" / "row-1" / "lfb-inspect-record.json", inspect_record)
    result = _read_json(run_dir / "rows" / "row-1" / "result.json")
    result["result_sha256"] = _record_sha256(inspect_record)
    _write_json(run_dir / "rows" / "row-1" / "result.json", result)
    _write_jsonl(run_dir / "canonical-runs.jsonl", [result])
    return inspect_record


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
    _write_json(row_dir / "result.json", canonical_result)

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

from __future__ import annotations

import pytest
from legalforecast.multiharness import (
    SCHEMA_VERSIONS,
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    CanonicalTask,
    CommunityAggregate,
    CommunitySubmission,
    ConformanceReport,
    ContributorCredit,
    RunManifest,
    RunRequest,
    RunResult,
    SandboxPolicy,
    TaskIndex,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    validate_public_record,
    validate_safe_relative_path,
)

SHA256 = "sha256:" + "a" * 64
OTHER_SHA256 = "sha256:" + "b" * 64


def test_schema_versions_are_explicit_for_public_contracts() -> None:
    assert set(SCHEMA_VERSIONS) == {
        "task",
        "task_index",
        "adapter_manifest",
        "adapter_capabilities",
        "sandbox_policy",
        "run_request",
        "run_result",
        "run_manifest",
        "conformance_report",
        "community_submission",
        "community_aggregate",
    }
    assert all(
        version.startswith("legalforecast.multiharness.")
        for version in SCHEMA_VERSIONS.values()
    )


def test_task_index_serialization_round_trip() -> None:
    task = _task("lfb.case-1")
    index = TaskIndex(
        index_id="fixture-index",
        selection_namespace="lfb-fixture",
        tasks=(task,),
        index_sha256=SHA256,
    )

    assert TaskIndex.from_record(index.to_record()) == index


def test_adapter_and_run_records_round_trip() -> None:
    contributor = ContributorCredit(
        role="adapter_author",
        name="Legal Quants",
        identifiers={"url": "https://example.test"},
    )
    adapter = AdapterManifest(
        adapter_id="fixture-adapter",
        display_name="Fixture Adapter",
        adapter_version="0.1.0",
        command=("fixture-adapter",),
        contributors=(contributor,),
    )
    capabilities = AdapterCapabilities(
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        capabilities_sha256=SHA256,
    )
    sandbox = SandboxPolicy(
        policy_id="fixture-sandbox",
        backend="dry-run",
        image="python:3.12-slim",
        network_policy="provider_egress_host_only",
        timeout_seconds=60,
        allowed_provider_env_vars=("OPENAI_API_KEY",),
        policy_sha256=OTHER_SHA256,
    )
    request = RunRequest(
        request_id="row-1",
        task=_task("lfb.case-1"),
        adapter=adapter,
        model_key="fixture/model",
        sandbox_policy=sandbox,
        request_sha256=SHA256,
    )
    result = RunResult(
        result_id="row-1-result",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=OTHER_SHA256,
        artifacts=(_artifact(),),
        public_summary={"score": "fixture"},
    )
    manifest = RunManifest(
        run_id="run-1",
        selection_sha256=SHA256,
        run_config_sha256=OTHER_SHA256,
        request_ids=(request.request_id,),
        result_ids=(result.result_id,),
    )

    assert AdapterManifest.from_record(adapter.to_record()) == adapter
    assert AdapterCapabilities.from_record(capabilities.to_record()) == capabilities
    assert SandboxPolicy.from_record(sandbox.to_record()) == sandbox
    assert RunRequest.from_record(request.to_record()) == request
    assert RunResult.from_record(result.to_record()) == result
    assert RunManifest.from_record(manifest.to_record()) == manifest


def test_conformance_submission_and_aggregate_round_trip() -> None:
    submitter = ContributorCredit(role="submitter", name="John Hughes")
    artifact = _artifact()
    report = ConformanceReport(
        report_id="conf-1",
        adapter_id="fixture-adapter",
        adapter_version="0.1.0",
        status="passed",
        checks={"manifest": "passed"},
        artifacts=(artifact,),
    )
    submission = CommunitySubmission(
        submission_id="2026-fixture",
        submitter=submitter,
        contributors=(submitter,),
        run_manifest_sha256=SHA256,
        artifacts=(artifact,),
        attestations=("not an official LegalForecastBench result",),
        public_summary={"conformance_report_id": report.report_id},
    )
    aggregate = CommunityAggregate(
        aggregate_id="community-aggregate",
        submissions=(submission.submission_id,),
        aggregate_sha256=OTHER_SHA256,
        public_summary={"family": "legalforecast_mtd"},
    )

    assert ConformanceReport.from_record(report.to_record()) == report
    assert CommunitySubmission.from_record(submission.to_record()) == submission
    assert CommunityAggregate.from_record(aggregate.to_record()) == aggregate


def test_invalid_schema_version_is_rejected() -> None:
    record = _task("lfb.case-1").to_record()
    record["schema_version"] = "wrong-version"

    with pytest.raises(MultiHarnessValidationError, match="schema_version"):
        CanonicalTask.from_record(record)


def test_unsafe_paths_are_rejected() -> None:
    with pytest.raises(MultiHarnessValidationError, match="relative"):
        validate_safe_relative_path("/tmp/output.json", "path")

    with pytest.raises(MultiHarnessValidationError, match="parent"):
        ArtifactRecord(
            artifact_id="bad",
            path="reports/../secret.json",
            sha256=SHA256,
            media_type="application/json",
        )


def test_malformed_hashes_are_rejected() -> None:
    with pytest.raises(MultiHarnessValidationError, match="SHA-256"):
        _task("lfb.case-1", task_sha256="sha256:not-a-real-digest")


def test_duplicate_ids_are_rejected() -> None:
    task = _task("duplicate")

    with pytest.raises(MultiHarnessValidationError, match="duplicate"):
        TaskIndex(
            index_id="fixture-index",
            selection_namespace="lfb-fixture",
            tasks=(task, task),
            index_sha256=SHA256,
        )


def test_secret_like_public_fields_are_rejected() -> None:
    with pytest.raises(MultiHarnessValidationError, match="secret field"):
        validate_public_record({"OPENAI_API_KEY": "sk-fixture"}, "public")

    with pytest.raises(MultiHarnessValidationError, match="secret-like value"):
        validate_public_record(
            {"message": "Authorization: Bearer secret-token-12345"},
            "public",
        )


def test_deprecated_result_tier_fields_and_values_are_rejected() -> None:
    with pytest.raises(MultiHarnessValidationError, match="deprecated result-tier"):
        validate_public_record({"result_tier": "community-unverified"}, "public")

    with pytest.raises(MultiHarnessValidationError, match="deprecated result-tier"):
        CommunityAggregate(
            aggregate_id="aggregate",
            submissions=("sub-1",),
            aggregate_sha256=SHA256,
            public_summary={"status": "verified-community"},
        )


def _task(task_id: str, *, task_sha256: str = SHA256) -> CanonicalTask:
    return CanonicalTask(
        task_id=task_id,
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-v1",
        source_id="fixture-source",
        task_sha256=task_sha256,
        metadata={"case_id": "case-1"},
        artifacts=(_artifact(),),
    )


def _artifact() -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id="prompt",
        path="reports/prompt.json",
        sha256=SHA256,
        media_type="application/json",
        public=True,
        size_bytes=123,
    )

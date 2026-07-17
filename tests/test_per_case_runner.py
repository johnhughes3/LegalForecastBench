from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.evals import per_case_runner
from legalforecast.evals.inspect_task import HarnessRequest, SolverKind, SolverResponse
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
)
from legalforecast.evals.per_case_runner import (
    PacketManifestError,
    PerCaseRunnerConfig,
    PerCaseRunnerError,
    run_per_case_evaluation,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text
from legalforecast.protocol.freeze import sha256_file
from legalforecast.protocol.policy_artifacts import generate_execution_policy
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_per_case_runner_verifies_packet_and_publishes_safe_outputs(
    tmp_path: Path,
) -> None:
    packet_text = "Operative complaint text for the isolated packet."
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
    )
    output_dir = tmp_path / "runner-output"
    results_root = tmp_path / "results-store"

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256
    assert {path.name for path in artifacts.local_paths} == {
        "accounting.jsonl",
        "cell-completion.json",
        "metrics.json",
        "runner-log.jsonl",
        "runs.jsonl",
    }
    assert all(path.is_file() for path in artifacts.local_paths)
    assert not (output_dir / "model-packet.json").exists()

    runs = _read_jsonl(output_dir / "runs.jsonl")
    assert runs[0]["case_id"] == "case-1"
    assert "packet" not in runs[0]
    assert "prompt" not in runs[0]

    log_text = (output_dir / "runner-log.jsonl").read_text(encoding="utf-8")
    metrics_text = (output_dir / "metrics.json").read_text(encoding="utf-8")
    accounting_text = (output_dir / "accounting.jsonl").read_text(encoding="utf-8")
    for text in (log_text, metrics_text, accounting_text):
        assert packet_text not in text
        assert "CASE_DEV_API_KEY" not in text

    uploaded_paths = {
        path.relative_to(results_root).as_posix()
        for path in results_root.rglob("*")
        if path.is_file()
    }
    assert uploaded_paths
    assert all(path.startswith(("metrics/", "reports/")) for path in uploaded_paths)
    assert not any(
        path.startswith(
            (
                "audit-bundles/",
                "extracted-text/",
                "model-packets/",
                "source-documents/",
                "withdrawn/",
            )
        )
        for path in uploaded_paths
    )


def test_per_case_runner_resumes_complete_durable_outputs_without_rerun(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"

    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.25),
        )
    )

    second = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    assert second.run_id == first.run_id
    assert second.uploaded_uris == first.uploaded_uris[:3]
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    log_text = (tmp_path / "second-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resumed_existing_artifacts" in log_text


def test_per_case_runner_does_not_resume_incomplete_durable_outputs(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    partial_dir = results_root / "metrics" / "cycle-1"
    partial_dir.mkdir(parents=True)
    (
        partial_dir / "case-1-full_packet-offline-fixture-d2945393d77a.runs.jsonl"
    ).write_text(
        "",
        encoding="utf-8",
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert "0.91" in runs[0]["raw_output"]


def test_per_case_runner_replaces_stale_complete_durable_outputs(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text="original packet"),
    )
    results_root = tmp_path / "results-store"
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.25),
        )
    )
    _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text="refrozen packet"),
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.91" in runs[0]["raw_output"]
    assert "0.25" not in runs[0]["raw_output"]
    log_text = (tmp_path / "second-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resume_existing_rejected" in log_text
    assert "packet_sha256 does not match" in log_text


def test_per_case_runner_recovers_paid_generation_after_canonical_upload_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    runner_module = cast(Any, per_case_runner)
    original_upload = runner_module._upload_path
    failed = False

    def fail_first_accounting_upload(
        source: Path,
        destination_uri: str,
        *,
        content_type: str,
    ) -> None:
        nonlocal failed
        if destination_uri.endswith(".accounting.jsonl") and not failed:
            failed = True
            raise OSError("simulated canonical upload failure")
        original_upload(source, destination_uri, content_type=content_type)

    monkeypatch.setattr(per_case_runner, "_upload_path", fail_first_accounting_upload)
    with pytest.raises(PerCaseRunnerError, match="simulated canonical upload failure"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "failed-output",
                solver_id="offline:fixture",
                mock_output=_mock_output(probability=0.25),
            )
        )
    monkeypatch.setattr(per_case_runner, "_upload_path", original_upload)

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "resumed-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "resumed-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    log_text = (tmp_path / "resumed-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resumed_recovery_bundle" in log_text


def test_per_case_runner_accepts_exported_packet_sha256_field(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
        hash_field="packet_sha256",
    )

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256


@pytest.mark.parametrize(
    ("expected_object_key", "expected_sha256", "error_match"),
    (
        (
            "model-packets/cycle-1/case-1/drifted.json",
            None,
            "pre-fanout packet object key",
        ),
        (
            None,
            "0" * 64,
            "pre-fanout packet SHA-256",
        ),
    ),
)
def test_per_case_runner_rejects_pre_fanout_packet_identity_drift_before_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_object_key: str | None,
    expected_sha256: str | None,
    error_match: str,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
        hash_field="packet_sha256",
    )
    packet_object_key = "model-packets/cycle-1/case-1/full_packet.json"

    def reject_fetch(_uri: str, _destination: Path) -> None:
        raise AssertionError("packet fetch occurred before identity verification")

    monkeypatch.setattr(per_case_runner, "_fetch_uri", reject_fetch)

    with pytest.raises(PerCaseRunnerError, match=error_match):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                solver_id="offline:fixture",
                mock_output=_mock_output(),
                expected_packet_object_key=(expected_object_key or packet_object_key),
                expected_packet_sha256=expected_sha256 or packet_sha256,
            )
        )


def test_live_per_case_runner_requires_pre_fanout_packet_identity(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="pre-fanout packet identity"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            backend=per_case_runner.PerCaseExecutionBackend.LIVE,
            model_registry_uri=str(tmp_path / "registry.json"),
            model_key="provider:model",
        )


def test_per_case_runner_refuses_hash_mismatch_without_retaining_packet(
    tmp_path: Path,
) -> None:
    packet_text = "Hash mismatch packet text must not be retained."
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
        manifest_sha256="0" * 64,
    )
    output_dir = tmp_path / "runner-output"

    with pytest.raises(PerCaseRunnerError, match="SHA-256 mismatch"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                mock_output=_mock_output(),
            )
        )

    assert (output_dir / "runner-log.jsonl").is_file()
    assert not (output_dir / "runs.jsonl").exists()
    assert packet_text not in (output_dir / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )


def test_per_case_runner_refuses_audit_only_packet_objects(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": "audit-bundles/cycle-1/case-1/full_packet.json",
                    "sha256": "1" * 64,
                }
            ],
        },
    )

    with pytest.raises(PacketManifestError, match="model packet object key"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(tmp_path / "store"),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
            )
        )


def test_eval_run_case_cli_writes_artifact_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "cli-output"

    assert (
        main(
            [
                "eval",
                "run-case",
                "--manifest",
                str(manifest_path),
                "--packet-store-root",
                str(store_root),
                "--expected-packet-object-key",
                "model-packets/cycle-1/case-1/full_packet.json",
                "--expected-packet-sha256",
                packet_sha256,
                "--case-id",
                "case-1",
                "--ablation",
                "full_packet",
                "--output-dir",
                str(output_dir),
                "--mock-output",
                _mock_output(),
                "--evaluation-timestamp",
                "2026-05-17T12:00:00Z",
                "--timeout-seconds",
                "300",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["case_id"] == "case-1"
    assert (output_dir / "runs.jsonl").is_file()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["evaluation_timestamp"] == "2026-05-17T12:00:00Z"


def test_per_case_runner_repeats_prebudgeted_subset_rows(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            mock_output=_mock_output(),
            repeat_count=3,
        )
    )

    runs = _read_jsonl(output_dir / "runs.jsonl")
    accounting = _read_jsonl(output_dir / "accounting.jsonl")
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert [record["repeat_index"] for record in runs] == [1, 2, 3]
    assert [record["repeat_sampling_role"] for record in runs] == [
        "primary",
        "repeat",
        "repeat",
    ]
    assert {record["repeat_group_id"] for record in runs} == {"cand-1"}
    assert len(accounting) == 3
    assert all(record["repeat_count"] == 3 for record in accounting)
    assert metrics["repeat_count"] == 3
    assert metrics["primary_run_record_count"] == 1
    assert metrics["run_record_count"] == 3


def test_repeat_policy_mismatch_fails_before_resume_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    execution_path, execution_sha256 = _write_execution_policy(tmp_path, repeat_count=3)

    monkeypatch.setattr(
        per_case_runner,
        "_try_resume_existing_outputs",
        lambda **_kwargs: pytest.fail("repeat mismatch reached resume"),
    )
    monkeypatch.setattr(
        per_case_runner,
        "_solver_for_config",
        lambda *_args, **_kwargs: pytest.fail("repeat mismatch reached provider"),
    )

    with pytest.raises(PerCaseRunnerError, match="repeat_count does not match frozen"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                repeat_count=2,
                execution_policy_uri=str(execution_path),
                expected_execution_policy_sha256=execution_sha256,
                resume_existing=True,
            )
        )


def test_repeat_policy_identity_changes_durable_run_id(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    first_path, first_sha256 = _write_execution_policy(tmp_path, repeat_count=2)
    second_path, second_sha256 = _write_execution_policy(
        tmp_path, repeat_count=3, name="execution-policy-second.json"
    )

    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first",
            mock_output=_mock_output(),
            repeat_count=2,
            execution_policy_uri=str(first_path),
            expected_execution_policy_sha256=first_sha256,
        )
    )
    second = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second",
            mock_output=_mock_output(),
            repeat_count=3,
            execution_policy_uri=str(second_path),
            expected_execution_policy_sha256=second_sha256,
        )
    )

    assert first.run_id != second.run_id
    first_metrics = json.loads(
        (tmp_path / "first" / "metrics.json").read_text(encoding="utf-8")
    )
    second_metrics = json.loads(
        (tmp_path / "second" / "metrics.json").read_text(encoding="utf-8")
    )
    assert (
        first_metrics["repeat_policy_sha256"] != second_metrics["repeat_policy_sha256"]
    )


def test_resume_hard_fails_different_execution_policy_with_same_repeat_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results"
    first_policy, first_sha256 = _write_execution_policy(tmp_path, repeat_count=2)
    second_policy, second_sha256 = _write_execution_policy(
        tmp_path,
        repeat_count=2,
        max_billable_attempts=3,
        name="execution-policy-second.json",
    )
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first",
            mock_output=_mock_output(),
            repeat_count=2,
            execution_policy_uri=str(first_policy),
            expected_execution_policy_sha256=first_sha256,
        )
    )
    durable_before = _snapshot_files(results_root)
    monkeypatch.setattr(
        per_case_runner,
        "_solver_for_config",
        lambda *_args, **_kwargs: pytest.fail("policy mismatch reached provider"),
    )

    with pytest.raises(
        PerCaseRunnerError, match="execution_policy_sha256 does not match"
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second",
                mock_output=_mock_output(),
                repeat_count=2,
                execution_policy_uri=str(second_policy),
                expected_execution_policy_sha256=second_sha256,
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before


def test_per_case_runner_does_not_publish_retryable_or_grounded_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"
    solver = _ResponseVerificationSolver(
        raw_output='{"case_assessment": "cut off"',
        metadata={
            "provider": "example-provider",
            "model_id": "example-model",
            "model_version_or_snapshot": "2026-05-14",
            "response_verification_schema_version": (
                "legalforecast.response_verification.v1"
            ),
            "response_grounding_artifacts_detected": "true",
            "response_grounding_artifact_paths": (
                '["$.output[0].type=web_search_call"]'
            ),
            "response_finish_reason": "max_tokens",
            "response_truncated": "true",
            "response_retryable_ops_event": "true",
            "response_retryable_ops_event_reason": "response_truncated:max_tokens",
            "response_content_filter": "false",
        },
    )

    def fake_solver_for_config(*_args: Any, **_kwargs: Any) -> Any:
        return solver

    monkeypatch.setattr(per_case_runner, "_solver_for_config", fake_solver_for_config)
    with pytest.raises(PerCaseRunnerError, match="grounding or search artifacts"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                mock_output=_mock_output(),
            )
        )

    assert not (output_dir / "runs.jsonl").exists()
    assert not (output_dir / "accounting.jsonl").exists()
    assert not (output_dir / "metrics.json").exists()
    log_text = (output_dir / "runner-log.jsonl").read_text(encoding="utf-8")
    assert "runner_failed" in log_text


def test_per_case_runner_rejects_retryable_response_before_publish() -> None:
    runner_module = cast(Any, per_case_runner)

    with pytest.raises(PerCaseRunnerError, match="requires retry"):
        runner_module._require_publishable_response_verification(
            {
                "grounding_artifacts_detected": False,
                "retryable_ops_event_count": 1,
            }
        )


def test_per_case_runner_rejects_nonpositive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            timeout_seconds=0,
        )


def test_per_case_runner_rejects_nonpositive_repeat_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repeat_count must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            repeat_count=0,
        )


def test_per_case_runner_resolves_model_registry_entry(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert runs[0]["solver_id"] == "example-provider:example-model"
    metadata = cast(dict[str, Any], runs[0]["metadata"])
    assert metadata["provider"] == "example-provider"
    metrics = json.loads(
        (tmp_path / "runner-output" / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["model_key"] == "example-provider:example-model"
    assert metrics["model_registry_sha256"] == sha256_file(registry_path)
    assert len(metrics["model_registry_entry_sha256"]) == 64


def test_resume_accepts_amended_registry_when_model_entry_is_unchanged(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    amended_registry_path = tmp_path / "model-registry-amended.json"
    _write_model_registry(amended_registry_path, ("example-model", "expensive-model"))

    resumed = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            mock_output=_mock_output(probability=0.91),
            model_registry_uri=str(amended_registry_path),
            model_key="example-provider:example-model",
            resume_existing=True,
        )
    )

    assert resumed.run_id == first.run_id
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]


def test_resume_accepts_legacy_metrics_with_matching_registry_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    metrics_path = results_root / "metrics" / "cycle-1" / f"{first.run_id}.metrics.json"
    legacy_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    del legacy_metrics["model_registry_entry_sha256"]
    _write_json(metrics_path, legacy_metrics)
    durable_before_resume = _snapshot_files(results_root)

    def reject_republish(*_args: object, **_kwargs: object) -> None:
        pytest.fail("legacy resume attempted to republish durable outputs")

    monkeypatch.setattr(per_case_runner, "_upload_path", reject_republish)

    resumed = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            mock_output=_mock_output(probability=0.91),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
            resume_existing=True,
        )
    )

    assert resumed.run_id == first.run_id
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    assert _snapshot_files(results_root) == durable_before_resume


def test_resume_hard_fails_legacy_metrics_with_unknown_registry_hash(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    metrics_path = results_root / "metrics" / "cycle-1" / f"{first.run_id}.metrics.json"
    legacy_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    del legacy_metrics["model_registry_entry_sha256"]
    legacy_metrics["model_registry_sha256"] = "0" * 64
    _write_json(metrics_path, legacy_metrics)
    durable_before_resume = _snapshot_files(results_root)

    with pytest.raises(
        PerCaseRunnerError,
        match="model_registry_sha256 does not match",
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before_resume


def test_resume_rejects_amended_registry_when_model_entry_changed(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    amended_registry_path = tmp_path / "model-registry-amended.json"
    _write_model_registry(
        amended_registry_path,
        ("example-model", "expensive-model"),
        input_price_by_model={"example-model": 9.99},
    )
    durable_before_resume = _snapshot_files(results_root)

    with pytest.raises(
        PerCaseRunnerError,
        match="model_registry_entry_sha256 does not match",
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                model_registry_uri=str(amended_registry_path),
                model_key="example-provider:example-model",
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before_resume


def test_per_case_runner_rejects_unknown_model_key(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    with pytest.raises(PerCaseRunnerError, match="model_key not found"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:missing",
            )
        )


def test_per_case_runner_rejects_packet_before_release_anchor(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-13"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    with pytest.raises(PerCaseRunnerError, match="precedes release anchor"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
            )
        )


@dataclass(frozen=True, slots=True)
class _ResponseVerificationSolver:
    raw_output: str
    metadata: Mapping[str, str]

    @property
    def solver_id(self) -> str:
        return "example-provider:example-model"

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.CONFIGURED_MODEL_STUB

    def solve(self, _request: HarnessRequest) -> SolverResponse:
        return SolverResponse(
            raw_output=self.raw_output,
            input_tokens=10,
            output_tokens=2,
            estimated_cost=0.01,
            metadata=self.metadata,
        )


def _write_store_fixture(
    tmp_path: Path,
    *,
    packet_record: dict[str, object],
    manifest_sha256: str | None = None,
    hash_field: str = "sha256",
) -> tuple[Path, Path, str]:
    store_root = tmp_path / "packet-store"
    packet_key = "model-packets/cycle-1/case-1/full_packet.json"
    packet_path = store_root / packet_key
    _write_json(packet_path, packet_record)
    packet_sha256 = sha256_file(packet_path)
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": packet_key,
                    hash_field: manifest_sha256 or packet_sha256,
                    "size_bytes": packet_path.stat().st_size,
                    "content_type": "application/json",
                    "decision_date": packet_record.get("decision_date"),
                }
            ],
        },
    )
    return store_root, manifest_path, packet_sha256


def _packet_record(
    *,
    decision_date: str = "2026-05-17",
    packet_text: str = "Fixture complaint text.",
) -> dict[str, object]:
    document = PacketDocument(
        source_document_id="doc-complaint",
        document_role=DocumentRole.COMPLAINT,
        docket_entry_number=12,
        source_provider="fixture",
        source_url_or_reference="fixture://case-1/doc-complaint",
        source_sha256=sha256_text(packet_text),
        text=packet_text,
        text_sha256=sha256_text(packet_text),
        packet_section="filings",
    )
    unit = PredictionUnit(
        unit_id="unit-1",
        count="I",
        claim_name="Breach of contract",
        defendant_group="Example Defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.97,
        source_citations=(
            SourceCitation(
                document_id="doc-complaint",
                docket_entry_number=12,
                excerpt="Breach of contract claim.",
            ),
        ),
    )
    packet = ModelPacket(
        candidate_id="cand-1",
        case_id="case-1",
        court="D. Example",
        docket_number="1:26-cv-00001",
        ablation=PacketAblation.FULL_PACKET,
        metadata={"decision_date": decision_date, "fixture": "true"},
        documents=(document,),
        prediction_units=(unit,),
        excluded_document_ids=(),
        decision_date=decision_date,
    )
    return packet.to_record()


def _mock_output(*, probability: float = 0.25) -> str:
    return json.dumps(
        {
            "case_assessment": "The motion has modest dismissal risk.",
            "predictions": [
                {
                    "unit_id": "unit-1",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_model_registry(
    path: Path,
    model_ids: tuple[str, ...],
    *,
    input_price_by_model: dict[str, float] | None = None,
) -> None:
    prices = input_price_by_model or {}
    _write_json(
        path,
        [
            {
                "provider": "example-provider",
                "model_id": model_id,
                "display_name": model_id,
                "model_version_or_snapshot": f"{model_id}-2026-05-14",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": prices.get(model_id, 0.25),
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": [],
            }
            for model_id in model_ids
        ],
    )


def _write_execution_policy(
    tmp_path: Path,
    *,
    repeat_count: int,
    max_billable_attempts: int = 2,
    name: str = "execution-policy.json",
) -> tuple[Path, str]:
    artifact = generate_execution_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_series": "official",
            "allow_no_baselines": True,
            "labeling_policy_sha256": "a" * 64,
            "cohort_policy_sha256": "b" * 64,
            "cohort_observation_manifest_sha256": "c" * 64,
            "lifecycle": {
                "labeling_policy_published_at": "2026-07-12T20:00:00Z",
                "production_labeling_started_at": "2026-07-13T00:00:00Z",
                "cohort_policy_published_at": "2026-07-12T19:00:00Z",
                "batch_002_started_at": "2026-07-12T21:00:00Z",
            },
            "shard_schedule": {
                "shard_count": 2,
                "dispatch_unit": "model_key_ablation",
                "shards": [
                    {"model_key": "fixture:model-a", "ablation": ablation}
                    for ablation in ("full_packet", "metadata_only")
                ],
            },
            "concurrency_policy": {
                "mode": "shard_identity",
                "identity_fields": ["cycle_id", "model_key", "ablation"],
            },
            "receipt_policy": {
                "write_once_per_attempt": True,
                "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
                "result_commitment_required": True,
            },
            "attempt_policy": {
                "reservation_ledger_sha256": "d" * 64,
                "max_billable_attempts": max_billable_attempts,
            },
            "repeat_policy": {"case_ids": ["case-1"], "count": repeat_count},
            "cadence_counts": {
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count_source": "frozen_units",
                "reject_operator_mismatch": True,
            },
        }
    )
    path = tmp_path / name
    _write_json(path, artifact)
    return path, cast(str, artifact["policy_sha256"])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _snapshot_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

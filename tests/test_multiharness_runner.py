from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast._json_io import read_jsonl_objects
from legalforecast.evals.inspect_task import HarnessSolver, OfflineMockSolver
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketText,
    build_model_packet,
)
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterError,
)
from legalforecast.multiharness.host_environment import HostEnvironmentError
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
    validate_no_secret_values,
)
from legalforecast.multiharness.sandbox import (
    NETWORK_NONE,
    PROVIDER_EGRESS_HOST_ONLY,
    sandbox_policy,
)
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    CanonicalTask,
    ContributorCredit,
    TaskIndex,
)
from legalforecast.multiharness.task_loaders import LfbTaskLoader
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

SHA256 = "sha256:" + "a" * 64


def test_runner_writes_deterministic_artifacts_and_lfb_projection(
    tmp_path: Path,
) -> None:
    packet = _model_packet()
    task = LfbTaskLoader(suite_version="fixture-suite").task_from_record(
        packet.to_record()
    )
    adapter = LfbNativeAdapter()
    solver = OfflineMockSolver(
        solver_id="offline-fixture",
        raw_output=_raw_output(probability=0.7),
        input_tokens=5,
        output_tokens=3,
        estimated_cost=0.01,
    )

    first = run_multi_harness(
        _native_config(
            output_dir=tmp_path / "run-a",
            task=task,
            adapter=adapter,
            packet=packet,
            solver=solver,
        )
    )
    second = run_multi_harness(
        _native_config(
            output_dir=tmp_path / "run-b",
            task=task,
            adapter=adapter,
            packet=packet,
            solver=solver,
        )
    )

    assert first.manifest.request_ids == second.manifest.request_ids
    assert first.manifest.run_compatibility_sha256 == (
        second.manifest.run_compatibility_sha256
    )
    assert first.manifest.run_compatibility_sha256 is not None
    compatibility_path = first.output_dir / "run-compatibility.json"
    compatibility_record = json.loads(compatibility_path.read_text(encoding="utf-8"))
    assert first.manifest.run_compatibility_sha256 == _record_sha256(
        compatibility_record
    )
    row = first.rows[0]
    row_dir = first.output_dir / "rows" / row.row_id
    request_record = json.loads((row_dir / "request.json").read_text(encoding="utf-8"))
    assert request_record["request_sha256"] == row.request.request_sha256
    assert (row_dir / "sandbox.plan.json").is_file()
    assert (row_dir / "result.json").is_file()
    assert (row_dir / "private-logs").is_dir()
    assert row.result.status == "succeeded"

    canonical_rows = _jsonl(first.output_dir / "canonical-runs.jsonl")
    lfb_rows = _jsonl(first.output_dir / "lfb" / "runs.jsonl")
    artifact_index = json.loads(
        (first.output_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    artifact_records = cast(list[dict[str, object]], artifact_index["artifacts"])
    artifact_paths = {artifact["path"] for artifact in artifact_records}
    assert canonical_rows[0]["result_id"] == row.result.result_id
    assert lfb_rows[0]["raw_output"] == _raw_output(probability=0.7)
    assert lfb_rows[0]["model_id"] == "lfb-native:fixture-model"
    assert "lfb/runs.jsonl" in artifact_paths
    assert "canonical-runs.jsonl" in artifact_paths
    assert "run-compatibility.json" in artifact_paths
    assert f"rows/{row.row_id}/request.json" in artifact_paths


def test_runner_resumes_matching_request_hash(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"

    first = run_multi_harness(
        _command_config(output_dir=output_dir, task=task, adapter=adapter)
    )
    second = run_multi_harness(
        _command_config(output_dir=output_dir, task=task, adapter=adapter, resume=True)
    )

    assert second.rows[0].resumed is True
    assert first.rows[0].result.result_id == second.rows[0].result.result_id
    assert first.manifest.run_config_sha256 == second.manifest.run_config_sha256
    assert first.manifest.run_compatibility_sha256 == (
        second.manifest.run_compatibility_sha256
    )
    assert (first.rows[0].workspace / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "1"


def test_runner_does_not_resume_result_containing_provider_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "opaque-provider-value-7Jx9"
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", secret)
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"
    base_config = _command_config(output_dir=output_dir, task=task, adapter=adapter)
    config = replace(
        base_config,
        sandbox_policy=replace(
            base_config.sandbox_policy,
            network_policy=PROVIDER_EGRESS_HOST_ONLY,
            allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
        ),
    )
    first = run_multi_harness(config)
    result_path = first.rows[0].workspace / "result.json"
    stale_result = json.loads(result_path.read_text(encoding="utf-8"))
    stale_result["public_summary"]["leaked_value"] = secret
    result_path.write_text(json.dumps(stale_result), encoding="utf-8")

    second = run_multi_harness(replace(config, resume=True))

    assert second.rows[0].resumed is False
    assert (second.rows[0].workspace / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "2"
    assert secret not in result_path.read_text(encoding="utf-8")


def test_runner_does_not_resume_after_provider_environment_policy_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"
    base_config = _command_config(
        output_dir=output_dir,
        task=task,
        adapter=adapter,
    )
    monkeypatch.setenv("FIRST_PROVIDER_KEY", "first-provider-value")
    first_config = replace(
        base_config,
        sandbox_policy=replace(
            base_config.sandbox_policy,
            allowed_provider_env_vars=("FIRST_PROVIDER_KEY",),
        ),
    )
    first = run_multi_harness(first_config)

    monkeypatch.setenv("SECOND_PROVIDER_KEY", "second-provider-value")
    second_config = replace(
        base_config,
        resume=True,
        sandbox_policy=replace(
            base_config.sandbox_policy,
            allowed_provider_env_vars=("SECOND_PROVIDER_KEY",),
        ),
    )
    second = run_multi_harness(second_config)

    assert second.rows[0].resumed is False
    assert first.rows[0].request.request_sha256 != second.rows[0].request.request_sha256
    assert (second.rows[0].workspace / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "2"


def test_runner_does_not_resume_failed_result(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        fail_run=True,
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"
    first = run_multi_harness(
        _command_config(output_dir=output_dir, task=task, adapter=adapter)
    )
    assert first.rows[0].result.status == "failed"
    script_path = Path(adapter.manifest.command[1])
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace(
            "FAIL_RUN = True",
            "FAIL_RUN = False",
        ),
        encoding="utf-8",
    )

    second = run_multi_harness(
        _command_config(
            output_dir=output_dir,
            task=task,
            adapter=adapter,
            resume=True,
        )
    )

    assert second.rows[0].resumed is False
    assert second.rows[0].result.status == "succeeded"
    assert (second.rows[0].workspace / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "1"


def test_config_rejects_provider_environment_without_host_egress(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)

    with pytest.raises(ValueError, match="provider egress"):
        replace(
            config,
            sandbox_policy=replace(
                config.sandbox_policy,
                network_policy=NETWORK_NONE,
                allowed_provider_env_vars=("OPENAI_API_KEY",),
            ),
        )


def test_runner_rejects_missing_provider_environment_before_capability_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"
    config = _command_config(output_dir=output_dir, task=task, adapter=adapter)
    config = replace(
        config,
        sandbox_policy=replace(
            config.sandbox_policy,
            allowed_provider_env_vars=("MISSING_PROVIDER_KEY",),
        ),
    )
    monkeypatch.delenv("MISSING_PROVIDER_KEY", raising=False)

    with pytest.raises(HostEnvironmentError, match="MISSING_PROVIDER_KEY"):
        run_multi_harness(config)

    assert not output_dir.exists()


def test_runner_redacts_provider_values_from_public_failure_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "opaque-provider-value-7Jx9"
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", secret)
    adapter = _ProviderValueErrorAdapter(secret)
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = MultiHarnessRunConfig(
        task_index=_task_index(task),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
            ),
        ),
        sandbox_policy=replace(
            _sandbox(),
            allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
        ),
        output_dir=tmp_path / "run",
    )

    run = run_multi_harness(config)

    public_result = json.dumps(run.rows[0].result.to_record(), sort_keys=True)
    assert run.rows[0].result.status == "failed"
    assert secret not in public_result
    assert run.rows[0].result.public_summary["error_message"] == (
        "adapter failed; see private logs"
    )


def test_runner_redacts_provider_value_that_occurs_in_generic_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "private logs"
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", secret)
    adapter = _ProviderValueErrorAdapter(secret)
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = MultiHarnessRunConfig(
        task_index=_task_index(task),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
            ),
        ),
        sandbox_policy=replace(
            _sandbox(),
            allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
        ),
        output_dir=tmp_path / "run",
    )

    run = run_multi_harness(config)

    public_result = json.dumps(run.rows[0].result.to_record(), sort_keys=True)
    assert run.rows[0].result.status == "failed"
    assert secret not in public_result
    assert run.rows[0].result.public_summary == {}


def test_runner_fail_fast_keeps_rejected_command_result_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "opaque-provider-value-7Jx9"
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", secret)
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        public_summary_env_name="DECLARED_PROVIDER_VALUE",
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    base_config = _command_config(
        output_dir=tmp_path / "run",
        task=task,
        adapter=adapter,
    )
    config = replace(
        base_config,
        incomplete_run_policy="fail_fast",
        sandbox_policy=replace(
            base_config.sandbox_policy,
            allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
        ),
    )

    with pytest.raises(ValueError, match="declared provider environment value"):
        run_multi_harness(config)

    row_directories = tuple((config.output_dir / "rows").iterdir())
    assert len(row_directories) == 1
    row_directory = row_directories[0]
    assert not (row_directory / "result.json").exists()
    private_result = row_directory / "private-logs" / "run-result.raw.json"
    assert private_result.is_file()
    assert secret in private_result.read_text(encoding="utf-8")


def test_runner_fail_fast_removes_native_result_after_post_run_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = _model_packet()
    task = LfbTaskLoader(suite_version="fixture-suite").task_from_record(
        packet.to_record()
    )
    config = replace(
        _native_config(
            output_dir=tmp_path / "run",
            task=task,
            adapter=LfbNativeAdapter(),
            packet=packet,
            solver=OfflineMockSolver(
                solver_id="offline-fixture",
                raw_output=_raw_output(probability=0.7),
            ),
        ),
        incomplete_run_policy="fail_fast",
    )
    original_validate = validate_no_secret_values

    def reject_post_run_result(
        value: object,
        secret_values: tuple[str, ...],
        context: str,
    ) -> None:
        if context == "run result":
            raise ValueError("forced post-run secret rejection")
        original_validate(value, secret_values, context)

    monkeypatch.setattr(
        "legalforecast.multiharness.runner.validate_no_secret_values",
        reject_post_run_result,
    )

    with pytest.raises(ValueError, match="forced post-run secret rejection"):
        run_multi_harness(config)

    row_directories = tuple((config.output_dir / "rows").iterdir())
    assert len(row_directories) == 1
    assert not (row_directories[0] / "result.json").exists()


def test_runner_fail_fast_clears_stale_result_before_row_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = _command_config(
        output_dir=tmp_path / "run",
        task=task,
        adapter=adapter,
    )
    first = run_multi_harness(config)
    row_directory = first.rows[0].workspace
    result_path = row_directory / "result.json"
    assert result_path.is_file()
    original_capabilities = CommandAdapter.capabilities

    def fail_row_capabilities(
        current_adapter: CommandAdapter,
        workspace: Path,
    ) -> AdapterCapabilities:
        if "rows" in workspace.parts:
            raise CommandAdapterError("fixture row capability failure")
        return original_capabilities(current_adapter, workspace)

    monkeypatch.setattr(CommandAdapter, "capabilities", fail_row_capabilities)

    with pytest.raises(CommandAdapterError, match="row capability failure"):
        run_multi_harness(replace(config, incomplete_run_policy="fail_fast"))

    assert not result_path.exists()


def test_config_rejects_matrix_global_credentials_for_multiple_models(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)

    with pytest.raises(ValueError, match="one adapter and one model"):
        replace(
            config,
            model_configs=(ModelConfig("first"), ModelConfig("second")),
            sandbox_policy=replace(
                config.sandbox_policy,
                network_policy=PROVIDER_EGRESS_HOST_ONLY,
                allowed_provider_env_vars=("OPENAI_API_KEY",),
            ),
        )


def test_config_rejects_matrix_global_credentials_for_multiple_adapters(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    config = _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)

    with pytest.raises(ValueError, match="one adapter and one model"):
        replace(
            config,
            adapters=(adapter, adapter),
            sandbox_policy=replace(
                config.sandbox_policy,
                network_policy=PROVIDER_EGRESS_HOST_ONLY,
                allowed_provider_env_vars=("OPENAI_API_KEY",),
            ),
        )


def test_run_compatibility_hash_excludes_selection_and_run_identity(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    first_config = _command_config(
        output_dir=tmp_path / "run-a",
        task=task,
        adapter=adapter,
    )
    second_config = replace(
        first_config,
        output_dir=tmp_path / "run-b",
        selection=TaskSelection.full(label="different-selection-label"),
        run_id="different-run-id",
        max_parallelism=2,
    )
    incompatible_config = replace(
        first_config,
        output_dir=tmp_path / "run-c",
        incomplete_run_policy="fail_fast",
    )

    first = run_multi_harness(first_config)
    second = run_multi_harness(second_config)
    incompatible = run_multi_harness(incompatible_config)

    assert first.manifest.run_config_sha256 != second.manifest.run_config_sha256
    assert first.manifest.run_compatibility_sha256 == (
        second.manifest.run_compatibility_sha256
    )
    assert first.manifest.run_compatibility_sha256 != (
        incompatible.manifest.run_compatibility_sha256
    )


def test_run_compatibility_hash_includes_resolved_adapter_capabilities(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    first = run_multi_harness(
        _command_config(
            output_dir=tmp_path / "run-a",
            task=task,
            adapter=adapter,
        )
    )
    script_path = Path(adapter.manifest.command[1])
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace("'a' * 64", "'c' * 64"),
        encoding="utf-8",
    )
    second = run_multi_harness(
        _command_config(
            output_dir=tmp_path / "run-b",
            task=task,
            adapter=adapter,
        )
    )

    assert first.manifest.run_config_sha256 == second.manifest.run_config_sha256
    assert first.manifest.run_compatibility_sha256 != (
        second.manifest.run_compatibility_sha256
    )


def test_runner_marks_capability_probe_artifacts_private(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        write_private_capability_probe=True,
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")

    run = run_multi_harness(
        _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)
    )

    artifact_index = json.loads(
        (run.output_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    artifacts = {
        artifact["path"]: artifact["public"]
        for artifact in cast(list[dict[str, object]], artifact_index["artifacts"])
    }
    capability_root = "adapter-capabilities/command-fixture"
    assert artifacts[f"{capability_root}/adapter-capabilities.json"] is True
    assert artifacts[f"{capability_root}/lab-command-capabilities.json"] is False
    assert artifacts[f"{capability_root}/private-logs/capabilities-stdout.log"] is False
    assert artifacts[f"{capability_root}/private-logs/capabilities-stderr.log"] is False
    row_root = f"rows/{run.rows[0].row_id}"
    assert artifacts[f"{row_root}/adapter-capabilities.json"] is True
    assert artifacts[f"{row_root}/lab-command-capabilities.json"] is False
    assert artifacts[f"{row_root}/private-logs/capabilities-stdout.log"] is False
    assert artifacts[f"{row_root}/private-logs/run-result.raw.json"] is False
    assert artifacts[f"{row_root}/result.json"] is True


def test_runner_records_failures_and_keeps_lab_outputs_separate(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("harvey_lab",),
        supported_scoring_modes=("lab_native",),
        fail_run=True,
    )
    task = _task("harvey_lab:module/task", "harvey_lab", "lab_native")

    run = run_multi_harness(
        _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)
    )

    assert run.rows[0].result.status == "failed"
    assert (run.rows[0].workspace / "private-logs" / "error.txt").is_file()
    lab_rows = _jsonl(run.output_dir / "lab" / "task-results.jsonl")
    assert lab_rows[0]["task_id"] == "harvey_lab:module/task"
    assert lab_rows[0]["result"]["status"] == "failed"
    assert not (run.output_dir / "lfb" / "runs.jsonl").exists()


def test_runner_validates_compatibility_before_row_execution(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("harvey_lab:module/task", "harvey_lab", "lab_native")
    output_dir = tmp_path / "run"

    with pytest.raises(ValueError, match="no compatible adapter"):
        run_multi_harness(
            _command_config(output_dir=output_dir, task=task, adapter=adapter)
        )

    assert not (output_dir / "rows").exists()


def _native_config(
    *,
    output_dir: Path,
    task: CanonicalTask,
    adapter: LfbNativeAdapter,
    packet: ModelPacket,
    solver: HarnessSolver,
) -> MultiHarnessRunConfig:
    return MultiHarnessRunConfig(
        task_index=_task_index(task),
        selection=TaskSelection.full(),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
                lfb_packet=packet,
                lfb_solver=solver,
            ),
        ),
        sandbox_policy=_sandbox(),
        output_dir=output_dir,
    )


def _command_config(
    *,
    output_dir: Path,
    task: CanonicalTask,
    adapter: CommandAdapter,
    resume: bool = False,
) -> MultiHarnessRunConfig:
    return MultiHarnessRunConfig(
        task_index=_task_index(task),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
            ),
        ),
        sandbox_policy=_sandbox(),
        output_dir=output_dir,
        resume=resume,
    )


def _command_adapter(
    tmp_path: Path,
    *,
    supported_families: tuple[str, ...],
    supported_scoring_modes: tuple[str, ...],
    fail_run: bool = False,
    write_private_capability_probe: bool = False,
    public_summary_env_name: str | None = None,
) -> CommandAdapter:
    script = tmp_path / f"adapter_{len(list(tmp_path.glob('adapter_*.py')))}.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json, os, sys",
                f"SUPPORTED_FAMILIES = {supported_families!r}",
                f"SUPPORTED_SCORING_MODES = {supported_scoring_modes!r}",
                f"FAIL_RUN = {fail_run!r}",
                f"WRITE_PRIVATE_CAPABILITY_PROBE = {write_private_capability_probe!r}",
                f"PUBLIC_SUMMARY_ENV_NAME = {public_summary_env_name!r}",
                "parser = argparse.ArgumentParser()",
                "sub = parser.add_subparsers(dest='command', required=True)",
                "cap = sub.add_parser('capabilities')",
                "cap.add_argument('--output', required=True)",
                "run = sub.add_parser('run')",
                "run.add_argument('--request', required=True)",
                "run.add_argument('--output', required=True)",
                "run.add_argument('--workspace', required=True)",
                "args = parser.parse_args()",
                "if args.command == 'capabilities':",
                "    payload = {",
                "        'schema_version': (",
                "            'legalforecast.multiharness.adapter_capabilities.v1'",
                "        ),",
                "        'adapter_id': 'command-fixture',",
                "        'adapter_version': '0.1.0',",
                "        'supported_families': list(SUPPORTED_FAMILIES),",
                "        'supported_scoring_modes': list(SUPPORTED_SCORING_MODES),",
                "        'supports_sandbox_policy': True,",
                "        'capabilities_sha256': 'sha256:' + 'a' * 64,",
                "    }",
                "    if WRITE_PRIVATE_CAPABILITY_PROBE:",
                "        probe_path = str(args.output).replace(",
                "            'adapter-capabilities.json',",
                "            'lab-command-capabilities.json',",
                "        )",
                "        open(probe_path, 'w', encoding='utf-8').write(",
                "            json.dumps({'lab_root': '/private/local/checkout'})",
                "        )",
                "    open(args.output, 'w', encoding='utf-8').write(",
                "        json.dumps(payload)",
                "    )",
                "else:",
                "    if FAIL_RUN:",
                "        print('fixture failure', file=sys.stderr)",
                "        raise SystemExit(2)",
                "    request = json.load(open(args.request, encoding='utf-8'))",
                "    count_path = f'{args.workspace}/run-count.txt'",
                "    try:",
                "        count = int(open(count_path, encoding='utf-8').read()) + 1",
                "    except FileNotFoundError:",
                "        count = 1",
                "    open(count_path, 'w', encoding='utf-8').write(str(count))",
                "    result = {",
                "        'schema_version': 'legalforecast.multiharness.run_result.v1',",
                "        'result_id': request['request_id'] + ':result',",
                "        'request_id': request['request_id'],",
                "        'status': 'succeeded',",
                "        'result_sha256': 'sha256:' + 'b' * 64,",
                "        'artifacts': [],",
                "        'public_summary': {'run_count': count},",
                "    }",
                "    if PUBLIC_SUMMARY_ENV_NAME:",
                "        result['public_summary']['provider_value'] = (",
                "            os.environ[PUBLIC_SUMMARY_ENV_NAME]",
                "        )",
                "    open(args.output, 'w', encoding='utf-8').write(",
                "        json.dumps(result)",
                "    )",
            ]
        ),
        encoding="utf-8",
    )
    manifest = AdapterManifest(
        adapter_id="command-fixture",
        display_name="Command Fixture",
        adapter_version="0.1.0",
        command=(sys.executable, str(script)),
        contributors=(ContributorCredit(role="adapter_author", name="Fixture"),),
    )
    return CommandAdapter(manifest=manifest)


class _ProviderValueErrorAdapter:
    def __init__(self, secret: str) -> None:
        self.secret = secret
        self.manifest = AdapterManifest(
            adapter_id="provider-value-error",
            display_name="Provider Value Error",
            adapter_version="0.1.0",
            command=("provider-value-error",),
        )

    def capabilities(self, _workspace: Path) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
            capabilities_sha256=SHA256,
        )

    def run(self, _request: object, _workspace: Path) -> object:
        raise RuntimeError(self.secret)


def _task_index(task: CanonicalTask) -> TaskIndex:
    return TaskIndex(
        index_id="fixture-index",
        selection_namespace="fixture",
        tasks=(task,),
        index_sha256=SHA256,
    )


def _task(task_id: str, family: str, scoring_mode: str) -> CanonicalTask:
    return CanonicalTask(
        task_id=task_id,
        family=family,
        scoring_mode=scoring_mode,
        suite_version="fixture-suite",
        source_id=task_id,
        task_sha256=SHA256,
        metadata={},
    )


def _sandbox():
    return sandbox_policy(
        policy_id="fixture",
        backend="docker",
        image="python:3.12-slim",
        mounts=(),
        timeout_seconds=30,
    )


def _model_packet():
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                _document("complaint", DocumentRole.COMPLAINT, 1),
                _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            ),
        ),
        prediction_units=(_unit(),),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
        ),
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"case.dev://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=True,
        is_mounted_for_model=True,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=False,
        packet_section="filings",
    )


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count_i_issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )


def _raw_output(*, probability: float) -> str:
    return json.dumps(
        {
            "case_assessment": "The count is likely dismissed.",
            "predictions": [
                {
                    "unit_id": "count_i_issuer",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_objects(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"missing JSONL: {item}",
        non_object_message=lambda item, line: f"bad JSONL row {line} in {item}",
    )


def _record_sha256(record: object) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
from legalforecast.multiharness.claude_code_harvey_lab import (
    ClaudeCodeHarveyLabMeasurementResult,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

from test_harvey_lab_projection import FIXTURE_PIN
from test_multiharness_claude_clean_native_lab_e2e import (
    _hosts,
    _install_binaries,
    _make_writable,
)


def test_container_workspace_stages_task_read_only_and_needs_no_issuer(
    tmp_path: Path,
) -> None:
    env = _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    try:
        result = run_claude_code_clean_native_harvey_lab(
            adapter=ClaudeCodeCliAdapter(
                execution_service=_ContainerMappingService(env),  # type: ignore[arg-type]
            ),
            pin=FIXTURE_PIN,
            evaluator_execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            container_workspace=True,
            **hosts,
        )
        assert isinstance(result, ClaudeCodeHarveyLabMeasurementResult)
    finally:
        _make_writable(tmp_path)

    add_dirs = tuple(
        result.solver_spec.argv[index + 1]
        for index, token in enumerate(result.solver_spec.argv[:-1])
        if token == "--add-dir"
    )
    assert add_dirs == ("/workspace", "/workspace/task")
    assert (hosts["sandbox_root"] / "task" / "instructions.txt").is_file()
    assert result.score.score_value == 1
    assert result.score.n_passed == result.score.n_criteria == 23
    assert not (hosts["overlay_root"] / "evaluation-output.json").exists()


class _ContainerMappingService:
    """Offline stand-in for the container's /workspace bind mount."""

    def __init__(self, parent_env: dict[str, str]) -> None:
        self._delegate = LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=parent_env,
        )

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        host_workspace = spec.working_directory.as_posix()
        translated = replace(
            spec,
            argv=tuple(
                token.replace("/workspace", host_workspace) for token in spec.argv
            ),
            spec_sha256="",
        )
        observed = self._delegate.execute(translated)
        return ExecutionReceipt.from_transcript(
            spec,
            stdout=observed.stdout,
            stderr=observed.stderr,
            returncode=observed.returncode,
            status=observed.status,
            duration_ms=observed.duration_ms,
            served_model=observed.served_model,
            usage=observed.usage,
            cost_usd=observed.cost_usd,
        )

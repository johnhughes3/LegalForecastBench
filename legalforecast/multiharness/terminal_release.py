"""One local coding-terminal run from a blinded release through scoring."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from legalforecast._json_io import write_json_object_safe
from legalforecast.immutable_io import ensure_private_directory
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRun,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import (
    PROVIDER_EGRESS_HOST_ONLY,
    sandbox_policy,
)
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import SolverInputStore
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.multiharness.terminal_release_cli import TerminalReleaseOptions
from legalforecast.multiharness.terminal_release_package import (
    load_terminal_release_run,
)
from legalforecast.release.models import ForecastRelease, LabelsRelease
from legalforecast.release.service import load_forecast_execution, validate_release

ReleaseScorer = Callable[
    [MultiHarnessRun, ForecastRelease, LabelsRelease], Mapping[str, Any]
]


def terminal_case_count(
    options: TerminalReleaseOptions, forecast: ForecastRelease
) -> int:
    """Validate the case scope before building an adapter or spending."""

    if options.case_id is None:
        return len(forecast.cases)
    if options.case_id not in {case.case_id for case in forecast.cases}:
        raise ValueError(f"unknown release case ID: {options.case_id}")
    if not any(
        unit.case_id == options.case_id and unit.should_score
        for unit in forecast.prediction_units
    ):
        raise ValueError(f"selected case has no scoreable units: {options.case_id}")
    return 1


def _execute_blinded_release(
    options: TerminalReleaseOptions,
    *,
    adapter: HarnessAdapter,
    forecast: ForecastRelease,
) -> MultiHarnessRun:
    """Stage only blinded inputs and execute one case call per release case."""

    terminal_case_count(options, forecast)
    if options.output_dir.exists() or options.output_dir.is_symlink():
        raise ValueError("--output-dir must be a fresh, absent path")
    ensure_private_directory(options.output_dir)
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        options.forecast_release,
        artifact_root=options.artifact_root,
        solver_input_root=options.output_dir / "solver-inputs",
        case_batching=True,
    )
    write_json_object_safe(
        options.output_dir / "task-index.json", task_index.to_record()
    )
    inputs = SolverInputStore.load(options.output_dir / "solver-inputs")
    policy = sandbox_policy(
        policy_id="claude-code-terminal-release",
        backend=options.backend,
        image=options.image,
        mounts=(),
        timeout_seconds=options.timeout_seconds,
        network_policy=PROVIDER_EGRESS_HOST_ONLY,
        uid_gid=f"{os.getuid()}:{os.getgid()}",
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    model_key=options.model_key,
                    adapter_id=adapter.manifest.adapter_id,
                ),
            ),
            sandbox_policy=policy,
            output_dir=options.output_dir,
            selection=(
                TaskSelection(case_ids=(options.case_id,))
                if options.case_id is not None
                else TaskSelection.full()
            ),
            run_id=options.run_id,
            max_parallelism=1,
            incomplete_run_policy="record_failure",
            container_execution="headless_cli",
            solver_inputs=inputs,
        )
    )
    return run


def execute_terminal_release(
    options: TerminalReleaseOptions,
    *,
    adapter: HarnessAdapter,
    score: ReleaseScorer,
) -> Mapping[str, Any]:
    """Run and score the existing one-command release convenience flow."""

    if options.labels_release is None:
        raise ValueError("release-run requires --labels-release")
    forecast, labels = validate_release(
        options.forecast_release,
        options.labels_release,
        artifact_root=options.artifact_root,
    )
    run = _execute_blinded_release(options, adapter=adapter, forecast=forecast)
    report = dict(score(run, forecast, labels))
    write_json_object_safe(options.output_dir / "scores.json", report)
    return report


def execute_terminal_release_only(
    options: TerminalReleaseOptions,
    *,
    adapter: HarnessAdapter,
) -> MultiHarnessRun:
    """Execute a forecast release without loading labels or scoring."""

    forecast = load_forecast_execution(
        options.forecast_release,
        artifact_root=options.artifact_root,
    ).release
    return _execute_blinded_release(options, adapter=adapter, forecast=forecast)


def score_terminal_release(
    *,
    run_dir: Path,
    forecast_release_path: Path,
    labels_release_path: Path,
    artifact_root: Path,
    score: ReleaseScorer,
    output_path: Path | None = None,
) -> Mapping[str, Any]:
    """Score a saved scoreless run using labels loaded only on this path."""

    forecast, labels = validate_release(
        forecast_release_path,
        labels_release_path,
        artifact_root=artifact_root,
    )
    run = load_terminal_release_run(run_dir)
    report = dict(score(run, forecast, labels))
    destination = output_path or run_dir / "scores.json"
    write_json_object_safe(destination, report)
    return report

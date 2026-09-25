"""One local coding-terminal run from a blinded release through scoring."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
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
from legalforecast.release.models import ForecastRelease, LabelsRelease
from legalforecast.release.service import validate_release

ReleaseScorer = Callable[
    [MultiHarnessRun, ForecastRelease, LabelsRelease], Mapping[str, Any]
]


def execute_terminal_release(
    options: TerminalReleaseOptions,
    *,
    adapter: HarnessAdapter,
    score: ReleaseScorer,
) -> Mapping[str, Any]:
    """Stage only blinded inputs, execute one case call, and score the census."""

    forecast, labels = validate_release(
        options.forecast_release,
        options.labels_release,
        artifact_root=options.artifact_root,
    )
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
            selection=TaskSelection.full(),
            run_id=options.run_id,
            max_parallelism=1,
            incomplete_run_policy="record_failure",
            container_execution="headless_cli",
            solver_inputs=inputs,
        )
    )
    report = dict(score(run, forecast, labels))
    write_json_object_safe(options.output_dir / "scores.json", report)
    return report

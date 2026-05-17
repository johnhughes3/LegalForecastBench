"""Inspect harness, scorers, baselines, and inference."""

from legalforecast.evals.inspect_ai_adapter import (
    InspectAITaskBuild,
    build_headline_inspect_ai_task,
)
from legalforecast.evals.inspect_task import (
    ConfiguredModelStubSolver,
    InspectTaskRun,
    InspectTaskSample,
    OfflineMockSolver,
    RunExecutionBackend,
    build_inspect_samples,
    render_model_prompt,
    run_inspect_fixture,
)
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    ToolPolicy,
    dump_model_registry,
    load_model_registry,
)
from legalforecast.evals.per_case_runner import (
    PerCaseRunArtifacts,
    PerCaseRunnerConfig,
    run_per_case_evaluation,
)

__all__ = [
    "ConfiguredModelStubSolver",
    "InspectAITaskBuild",
    "InspectTaskRun",
    "InspectTaskSample",
    "ModelRegistry",
    "ModelRegistryEntry",
    "OfflineMockSolver",
    "PerCaseRunArtifacts",
    "PerCaseRunnerConfig",
    "RunExecutionBackend",
    "ToolPolicy",
    "build_headline_inspect_ai_task",
    "build_inspect_samples",
    "dump_model_registry",
    "load_model_registry",
    "render_model_prompt",
    "run_inspect_fixture",
    "run_per_case_evaluation",
]

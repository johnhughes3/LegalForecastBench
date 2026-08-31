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
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelResponseError,
    LiveModelSolver,
    LiveModelSolverError,
)
from legalforecast.evals.model_registry import (
    LongContextSurcharge,
    ModelRegistry,
    ModelRegistryEntry,
    OpenAIReasoningEffort,
    ToolPolicy,
    dump_model_registry,
    load_model_registry,
)

__all__ = [
    "ConfiguredModelStubSolver",
    "InspectAITaskBuild",
    "InspectTaskRun",
    "InspectTaskSample",
    "LiveModelConfigError",
    "LiveModelResponseError",
    "LiveModelSolver",
    "LiveModelSolverError",
    "LongContextSurcharge",
    "ModelRegistry",
    "ModelRegistryEntry",
    "OfflineMockSolver",
    "OpenAIReasoningEffort",
    "RunExecutionBackend",
    "ToolPolicy",
    "build_headline_inspect_ai_task",
    "build_inspect_samples",
    "dump_model_registry",
    "load_model_registry",
    "render_model_prompt",
    "run_inspect_fixture",
]

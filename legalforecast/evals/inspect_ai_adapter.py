"""Optional Inspect AI adapter for headline benchmark tasks."""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from legalforecast.evals.inspect_task import (
    InspectTaskSample,
    RunExecutionBackend,
)
from legalforecast.evals.output_parser import parse_model_output

DEFAULT_INSPECT_TASK_NAME = "legalforecast_mtd_headline"
OUTPUT_CONTRACT_SCORER_NAME = "legalforecast_output_contract"


class TaskFactory(Protocol):
    """Factory compatible with inspect_ai.Task."""

    def __call__(
        self,
        *,
        dataset: Sequence[object],
        solver: object,
        scorer: object,
        sandbox: str | None,
    ) -> object: ...


class SampleFactory(Protocol):
    """Factory compatible with inspect_ai.dataset.Sample."""

    def __call__(
        self,
        *,
        id: str,
        input: str,
        target: str,
        metadata: Mapping[str, object],
    ) -> object: ...


class NoArgFactory(Protocol):
    """No-argument Inspect factory such as inspect_ai.solver.generate."""

    def __call__(self) -> object: ...


@dataclass(frozen=True, slots=True)
class InspectAIAdapterFactories:
    """Injectable factories for the real Inspect package or a test double."""

    task_factory: TaskFactory
    sample_factory: SampleFactory
    solver_factory: NoArgFactory
    scorer_factory: NoArgFactory
    dependency_name: str = "inspect_ai"


@dataclass(frozen=True, slots=True)
class InspectAISampleRecord:
    """Serializable dataset record passed into Inspect AI."""

    sample_id: str
    input: str
    target: str
    metadata: Mapping[str, object]

    def to_record(self) -> dict[str, object]:
        return {
            "id": self.sample_id,
            "input_sha256": self.metadata["prompt_sha256"],
            "target": self.target,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class InspectAIContractScore:
    """Deterministic output-contract score used by the Inspect adapter."""

    value: str
    valid: bool
    explanation: str
    metadata: Mapping[str, object]

    def to_record(self) -> dict[str, object]:
        return {
            "value": self.value,
            "valid": self.valid,
            "explanation": self.explanation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class InspectAIShimSample:
    """Dependency-free stand-in for inspect_ai.dataset.Sample."""

    id: str
    input: str
    target: str
    metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class InspectAIShimSolver:
    """Dependency-free stand-in for Inspect's default generate() solver."""

    solver_name: str = "inspect_ai.solver.generate"


@dataclass(frozen=True, slots=True)
class InspectAIShimScorer:
    """Dependency-free scorer that checks the LegalForecast output contract."""

    scorer_name: str = OUTPUT_CONTRACT_SCORER_NAME

    def score_output(self, raw_output: str, target: str) -> InspectAIContractScore:
        return score_output_contract(raw_output, target)


@dataclass(frozen=True, slots=True)
class InspectAIShimTask:
    """Dependency-free stand-in for an Inspect Task."""

    dataset: tuple[InspectAIShimSample, ...]
    solver: InspectAIShimSolver
    scorer: InspectAIShimScorer
    sandbox: str | None = None


@dataclass(frozen=True, slots=True)
class InspectAITaskBuild:
    """Built Inspect task plus LegalForecast run metadata."""

    task_name: str
    task: object
    inspect_samples: tuple[object, ...]
    sample_records: tuple[InspectAISampleRecord, ...]
    execution_backend: RunExecutionBackend
    dependency_name: str
    dependency_available: bool
    dependency_boundary: str
    scorer_name: str = OUTPUT_CONTRACT_SCORER_NAME
    solver_name: str = "inspect_ai.solver.generate"

    @property
    def sample_count(self) -> int:
        return len(self.sample_records)

    def run_metadata(self) -> dict[str, str]:
        return {
            "task_name": self.task_name,
            "execution_backend": self.execution_backend.value,
            "inspect_ai_dependency": self.dependency_name,
            "inspect_ai_dependency_available": str(self.dependency_available),
            "solver_name": self.solver_name,
            "scorer_name": self.scorer_name,
        }

    def to_record(self) -> dict[str, object]:
        return {
            "task_name": self.task_name,
            "execution_backend": self.execution_backend.value,
            "dependency_name": self.dependency_name,
            "dependency_available": self.dependency_available,
            "dependency_boundary": self.dependency_boundary,
            "solver_name": self.solver_name,
            "scorer_name": self.scorer_name,
            "sample_count": self.sample_count,
            "dataset": [record.to_record() for record in self.sample_records],
            "run_metadata": self.run_metadata(),
        }


def build_headline_inspect_ai_task(
    samples: Sequence[InspectTaskSample],
    *,
    task_name: str = DEFAULT_INSPECT_TASK_NAME,
    factories: InspectAIAdapterFactories | None = None,
    force_shim: bool = False,
) -> InspectAITaskBuild:
    """Build a real Inspect AI task, falling back to a deterministic shim."""

    _require_non_empty(task_name, "task_name")
    if not samples:
        raise ValueError("at least one sample is required")
    if factories is not None and force_shim:
        raise ValueError("factories and force_shim may not both be supplied")

    backend = RunExecutionBackend.INSPECT_AI
    dependency_available = True
    dependency_boundary = (
        "Built with real inspect_ai Task/Sample/generate/scorer factories. "
        "LegalForecast still owns packet construction, output parsing, "
        "accounting, and official Brier scoring."
    )
    resolved_factories = factories
    if resolved_factories is None:
        resolved_factories = None if force_shim else _load_real_factories()
    if resolved_factories is None:
        resolved_factories = _shim_factories()
        backend = RunExecutionBackend.INSPECT_AI_SHIM
        dependency_available = False
        dependency_boundary = (
            "inspect_ai is not installed or the shim was requested. The shim "
            "preserves the dataset, solver, scorer, and metadata contract "
            "without importing Inspect or calling model providers."
        )

    sample_records = tuple(
        _sample_record(sample, task_name=task_name, execution_backend=backend)
        for sample in samples
    )
    inspect_samples = tuple(
        resolved_factories.sample_factory(
            id=record.sample_id,
            input=record.input,
            target=record.target,
            metadata=record.metadata,
        )
        for record in sample_records
    )
    task = resolved_factories.task_factory(
        dataset=inspect_samples,
        solver=resolved_factories.solver_factory(),
        scorer=resolved_factories.scorer_factory(),
        sandbox=None,
    )
    return InspectAITaskBuild(
        task_name=task_name,
        task=task,
        inspect_samples=inspect_samples,
        sample_records=sample_records,
        execution_backend=backend,
        dependency_name=resolved_factories.dependency_name,
        dependency_available=dependency_available,
        dependency_boundary=dependency_boundary,
    )


def score_output_contract(raw_output: str, target: str) -> InspectAIContractScore:
    """Score whether a model output satisfies the LegalForecast JSON contract."""

    target_result = _required_unit_ids_from_target(target)
    if isinstance(target_result, InspectAIContractScore):
        return target_result

    parsed = parse_model_output(raw_output, required_unit_ids=target_result)
    issue_codes = tuple(issue.code.value for issue in parsed.issues)
    metadata: dict[str, object] = {
        "parser_status": parsed.status.value,
        "required_unit_count": len(target_result),
        "issue_codes": list(issue_codes),
    }
    if parsed.is_valid:
        return InspectAIContractScore(
            value="C",
            valid=True,
            explanation="model output satisfied the LegalForecast JSON contract",
            metadata=metadata,
        )
    return InspectAIContractScore(
        value="I",
        valid=False,
        explanation=f"model output failed parser status {parsed.status.value}",
        metadata=metadata,
    )


def _sample_record(
    sample: InspectTaskSample,
    *,
    task_name: str,
    execution_backend: RunExecutionBackend,
) -> InspectAISampleRecord:
    target_payload = {
        "required_unit_ids": list(sample.required_unit_ids),
        "scoring_note": (
            "Inspect scorer validates output contract; LegalForecast downstream "
            "scorers compute Brier and leaderboard metrics after labels attach."
        ),
    }
    metadata = sample.to_record()
    metadata.update(
        {
            "benchmark": "LegalForecast-MTD",
            "task_name": task_name,
            "execution_backend": execution_backend.value,
            "scorer_name": OUTPUT_CONTRACT_SCORER_NAME,
        }
    )
    return InspectAISampleRecord(
        sample_id=sample.sample_id,
        input=sample.prompt,
        target=json.dumps(target_payload, sort_keys=True),
        metadata=metadata,
    )


def _required_unit_ids_from_target(
    target: str,
) -> tuple[str, ...] | InspectAIContractScore:
    try:
        payload_object: object = json.loads(target)
    except json.JSONDecodeError as error:
        return _invalid_contract_target(f"target JSON is invalid: {error.msg}")
    if not isinstance(payload_object, Mapping):
        return _invalid_contract_target("target JSON must be an object")
    payload = cast(Mapping[str, object], payload_object)
    raw_unit_ids_object: object | None = payload.get("required_unit_ids")
    if not isinstance(raw_unit_ids_object, Sequence) or isinstance(
        raw_unit_ids_object,
        str,
    ):
        return _invalid_contract_target("target.required_unit_ids must be a list")
    raw_unit_ids = cast(Sequence[object], raw_unit_ids_object)
    unit_ids: list[str] = []
    for unit_id in raw_unit_ids:
        if not isinstance(unit_id, str) or not unit_id.strip():
            return _invalid_contract_target(
                "target.required_unit_ids must contain non-empty strings"
            )
        unit_ids.append(unit_id)
    if not unit_ids:
        return _invalid_contract_target("target.required_unit_ids must not be empty")
    if len(unit_ids) != len(set(unit_ids)):
        return _invalid_contract_target("target.required_unit_ids must be unique")
    return tuple(unit_ids)


def _invalid_contract_target(explanation: str) -> InspectAIContractScore:
    return InspectAIContractScore(
        value="I",
        valid=False,
        explanation=explanation,
        metadata={"parser_status": "invalid_target"},
    )


def _load_real_factories() -> InspectAIAdapterFactories | None:
    try:
        inspect_ai = importlib.import_module("inspect_ai")
        dataset_module = importlib.import_module("inspect_ai.dataset")
        solver_module = importlib.import_module("inspect_ai.solver")
        scorer_module = importlib.import_module("inspect_ai.scorer")
    except ModuleNotFoundError:
        return None

    return InspectAIAdapterFactories(
        task_factory=cast(TaskFactory, inspect_ai.Task),
        sample_factory=cast(SampleFactory, dataset_module.Sample),
        solver_factory=cast(NoArgFactory, solver_module.generate),
        scorer_factory=lambda: _build_real_contract_scorer(scorer_module),
    )


def _build_real_contract_scorer(scorer_module: Any) -> object:
    score_class: Any = scorer_module.Score
    scorer_decorator: Any = scorer_module.scorer
    accuracy_factory: Any = scorer_module.accuracy
    correct_value: object = getattr(scorer_module, "CORRECT", "C")
    incorrect_value: object = getattr(scorer_module, "INCORRECT", "I")

    def legalforecast_output_contract() -> object:
        async def score(state: object, target: object) -> object:
            contract_score = score_output_contract(
                _completion_from_state(state),
                _target_text(target),
            )
            return score_class(
                value=correct_value if contract_score.valid else incorrect_value,
                answer=_completion_from_state(state),
                explanation=contract_score.explanation,
                metadata=dict(contract_score.metadata),
            )

        return score

    decorated = scorer_decorator(metrics=[accuracy_factory()])(
        legalforecast_output_contract
    )
    return decorated()


def _completion_from_state(state: object) -> str:
    output = getattr(state, "output", None)
    completion = getattr(output, "completion", "")
    return completion if isinstance(completion, str) else ""


def _target_text(target: object) -> str:
    if isinstance(target, str):
        return target
    text = getattr(target, "text", "")
    return text if isinstance(text, str) else ""


def _shim_factories() -> InspectAIAdapterFactories:
    return InspectAIAdapterFactories(
        task_factory=_build_shim_task,
        sample_factory=_build_shim_sample,
        solver_factory=InspectAIShimSolver,
        scorer_factory=InspectAIShimScorer,
        dependency_name="inspect_ai_shim",
    )


def _build_shim_sample(
    *,
    id: str,
    input: str,
    target: str,
    metadata: Mapping[str, object],
) -> object:
    return InspectAIShimSample(
        id=id,
        input=input,
        target=target,
        metadata=dict(metadata),
    )


def _build_shim_task(
    *,
    dataset: Sequence[object],
    solver: object,
    scorer: object,
    sandbox: str | None,
) -> object:
    return InspectAIShimTask(
        dataset=tuple(cast(InspectAIShimSample, sample) for sample in dataset),
        solver=cast(InspectAIShimSolver, solver),
        scorer=cast(InspectAIShimScorer, scorer),
        sandbox=sandbox,
    )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")

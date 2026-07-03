"""Inspect-style task and solver wiring for local benchmark runs.

The production benchmark should run under Inspect AI, but the core harness
logic is kept dependency-light here so fixture runs can execute in CI without
provider credentials or network access.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
from legalforecast.evals.packet_builder import ModelPacket
from legalforecast.evals.tools import ControlledDocketEntry, ControlledDocketTool

DEFAULT_TOOL_CALL_CAP = 10


class SolverKind(StrEnum):
    """Solver categories supported by the neutral benchmark harness."""

    OFFLINE_MOCK = "offline_mock"
    CONFIGURED_MODEL_STUB = "configured_model_stub"
    INSPECT_AI = "inspect_ai"


class RunExecutionBackend(StrEnum):
    """Execution backend that produced a run artifact."""

    LOCAL_FIXTURE = "local_fixture"
    INSPECT_AI = "inspect_ai"
    INSPECT_AI_SHIM = "inspect_ai_shim"


class HarnessSolver(Protocol):
    """Minimal solver interface used by the local Inspect-compatible runner."""

    @property
    def solver_id(self) -> str: ...

    @property
    def solver_kind(self) -> SolverKind: ...

    def solve(self, request: HarnessRequest) -> SolverResponse: ...


@dataclass(frozen=True, slots=True)
class InspectTaskSample:
    """One motion/case sample passed to the model harness."""

    sample_id: str
    packet: ModelPacket
    prompt: str
    allowed_entry_numbers: tuple[int, ...]
    max_tool_calls: int = DEFAULT_TOOL_CALL_CAP
    run_label: str | None = None
    use_docket_tool: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.sample_id, "sample_id")
        _require_non_empty(self.prompt, "prompt")
        _require_positive(self.max_tool_calls, "max_tool_calls")
        if self.run_label is not None:
            _require_non_empty(self.run_label, "run_label")
        if len(self.allowed_entry_numbers) != len(set(self.allowed_entry_numbers)):
            raise ValueError("allowed_entry_numbers must be unique")
        for entry_number in self.allowed_entry_numbers:
            _require_positive(entry_number, "allowed_entry_numbers")

    @property
    def required_unit_ids(self) -> tuple[str, ...]:
        return tuple(
            unit.unit_id for unit in self.packet.prediction_units if unit.should_score
        )

    def build_docket_tool(self) -> ControlledDocketTool:
        if not self.use_docket_tool and not self.allowed_entry_numbers:
            return ControlledDocketTool(
                case_id=self.packet.case_id,
                entries=(),
                allowed_entry_numbers=(),
                max_tool_calls=self.max_tool_calls,
            )
        return ControlledDocketTool(
            case_id=self.packet.case_id,
            entries=_controlled_entries_from_packet(self.packet),
            allowed_entry_numbers=self.allowed_entry_numbers,
            max_tool_calls=self.max_tool_calls,
        )

    @property
    def effective_run_label(self) -> str:
        return self.run_label or self.packet.ablation.value

    def to_record(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "candidate_id": self.packet.candidate_id,
            "case_id": self.packet.case_id,
            "court": self.packet.court,
            "docket_number": self.packet.docket_number,
            "run_label": self.effective_run_label,
            "ablation": self.packet.ablation.value,
            "required_unit_ids": list(self.required_unit_ids),
            "allowed_entry_numbers": list(self.allowed_entry_numbers),
            "max_tool_calls": self.max_tool_calls,
            "use_docket_tool": self.use_docket_tool,
            "packet": self.packet.to_record(),
            "prompt_sha256": _sha256_prefixed(self.prompt),
        }


@dataclass(frozen=True, slots=True)
class HarnessRequest:
    """Per-sample request object passed into a solver."""

    sample: InspectTaskSample
    docket_tool: ControlledDocketTool


@dataclass(frozen=True, slots=True)
class SolverResponse:
    """Raw model response plus run-accounting facts before strict parsing."""

    raw_output: str
    request_count: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    metadata: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.raw_output, "raw_output")
        if self.request_count < 0:
            raise ValueError("request_count cannot be negative")
        if self.input_tokens < 0:
            raise ValueError("input_tokens cannot be negative")
        if self.output_tokens < 0:
            raise ValueError("output_tokens cannot be negative")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")
        if self.metadata is not None:
            for key, value in self.metadata.items():
                _require_non_empty(key, "metadata key")
                _require_non_empty(value, f"metadata[{key}]")

    @property
    def raw_output_sha256(self) -> str:
        return _sha256_prefixed(self.raw_output)

    @property
    def estimated_total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class InspectCaseRunResult:
    """Run artifact for one sample/solver pair."""

    sample_id: str
    candidate_id: str
    case_id: str
    related_family_id: str | None
    mdl_family_id: str | None
    solver_id: str
    solver_kind: SolverKind
    run_label: str
    ablation: str
    raw_output: str
    raw_output_sha256: str
    required_unit_ids: tuple[str, ...]
    request_count: int
    input_tokens: int
    output_tokens: int
    estimated_total_tokens: int
    estimated_cost: float
    tool_call_logs: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, str] | None = None
    execution_backend: RunExecutionBackend = RunExecutionBackend.LOCAL_FIXTURE

    def to_record(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
            "solver_id": self.solver_id,
            "solver_kind": self.solver_kind.value,
            "run_label": self.run_label,
            "ablation": self.ablation,
            "raw_output": self.raw_output,
            "raw_output_sha256": self.raw_output_sha256,
            "required_unit_ids": list(self.required_unit_ids),
            "request_count": self.request_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "estimated_cost": self.estimated_cost,
            "tool_call_logs": [dict(log) for log in self.tool_call_logs],
            "metadata": dict(self.metadata or {}),
            "execution_backend": self.execution_backend.value,
        }


@dataclass(frozen=True, slots=True)
class InspectTaskRun:
    """Complete local fixture run for one or more samples and solvers."""

    results: tuple[InspectCaseRunResult, ...]

    def __post_init__(self) -> None:
        if not self.results:
            raise ValueError("inspect task run requires at least one result")

    @property
    def case_count(self) -> int:
        return len({result.case_id for result in self.results})

    @property
    def solver_count(self) -> int:
        return len({result.solver_id for result in self.results})

    @property
    def total_estimated_cost(self) -> float:
        return sum(result.estimated_cost for result in self.results)

    @property
    def total_tool_calls(self) -> int:
        return sum(len(result.tool_call_logs) for result in self.results)

    def to_records(self) -> list[dict[str, Any]]:
        return [result.to_record() for result in self.results]

    def to_jsonl(self) -> str:
        return "".join(
            f"{json.dumps(record, sort_keys=True)}\n" for record in self.to_records()
        )


@dataclass(frozen=True, slots=True)
class OfflineMockSolver:
    """Deterministic local solver used for fixture and parser tests."""

    solver_id: str
    raw_output: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    use_docket_tool: bool = True

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.OFFLINE_MOCK

    def solve(self, request: HarnessRequest) -> SolverResponse:
        if self.use_docket_tool:
            _exercise_controlled_tool(request.docket_tool)
        return SolverResponse(
            raw_output=self.raw_output,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            estimated_cost=self.estimated_cost,
            metadata={"solver_mode": "offline_fixture"},
        )


@dataclass(frozen=True, slots=True)
class ConfiguredModelStubSolver:
    """No-network stand-in for a real configured model registry entry."""

    registry_entry: ModelRegistryEntry
    stub_raw_output: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0

    def __post_init__(self) -> None:
        _require_non_empty(self.stub_raw_output, "stub_raw_output")
        if not self.registry_entry.network_disabled:
            raise ValueError("configured model stubs require network_disabled=True")
        if not self.registry_entry.search_disabled:
            raise ValueError("configured model stubs require search_disabled=True")

    @property
    def solver_id(self) -> str:
        return self.registry_entry.registry_key

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.CONFIGURED_MODEL_STUB

    def solve(self, request: HarnessRequest) -> SolverResponse:
        if self.registry_entry.tool_policy is ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY:
            _exercise_controlled_tool(request.docket_tool)
        return SolverResponse(
            raw_output=self.stub_raw_output,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            estimated_cost=self.estimated_cost,
            metadata={
                "provider": self.registry_entry.provider,
                "model_id": self.registry_entry.model_id,
                "model_version_or_snapshot": (
                    self.registry_entry.model_version_or_snapshot
                ),
                "tool_policy": self.registry_entry.tool_policy.value,
            },
        )


def build_inspect_samples(
    packets: Iterable[ModelPacket],
    *,
    max_tool_calls: int = DEFAULT_TOOL_CALL_CAP,
    run_label: str | None = None,
    use_docket_tool: bool = True,
) -> tuple[InspectTaskSample, ...]:
    """Build deterministic local samples from frozen model packets."""

    _require_positive(max_tool_calls, "max_tool_calls")
    samples: list[InspectTaskSample] = []
    for packet in packets:
        allowed_entries = _allowed_entry_numbers(packet)
        samples.append(
            InspectTaskSample(
                sample_id=packet.candidate_id,
                packet=packet,
                prompt=render_model_prompt(packet, use_docket_tool=use_docket_tool),
                allowed_entry_numbers=allowed_entries,
                max_tool_calls=max_tool_calls,
                run_label=run_label,
                use_docket_tool=use_docket_tool,
            )
        )
    if not samples:
        raise ValueError("at least one packet is required")
    return tuple(samples)


def render_model_prompt(packet: ModelPacket, *, use_docket_tool: bool = True) -> str:
    """Render the neutral prompt text supplied to the model."""

    units = [
        {
            "unit_id": unit.unit_id,
            "count": unit.count,
            "claim_name": unit.claim_name,
            "defendant_group": unit.defendant_group,
        }
        for unit in packet.prediction_units
        if unit.should_score
    ]
    if not units:
        raise ValueError("prompt requires at least one scorable prediction unit")

    documents = [
        {
            "source_document_id": document.source_document_id,
            "document_role": document.document_role.value,
            "docket_entry_number": document.docket_entry_number,
            "text": document.text,
        }
        for document in packet.documents
    ]
    payload = {
        "task": "Predict federal motion-to-dismiss outcomes.",
        "response_format": (
            "Return only a valid JSON object. Do not include markdown, tables, "
            "code fences, headings, or explanatory text outside JSON."
        ),
        "required_output": {
            "case_assessment": "string, no more than 300 words",
            "predictions": [
                {
                    "unit_id": "string from prediction_units",
                    "probability_fully_dismissed": "number from 0 to 1",
                }
            ],
        },
        "case": {
            "candidate_id": packet.candidate_id,
            "case_id": packet.case_id,
            "court": packet.court,
            "docket_number": packet.docket_number,
            "metadata": dict(packet.metadata),
            "missing_optional_sections": list(packet.missing_optional_sections),
        },
        "prediction_units": units,
        "documents": documents,
        "tools": _tool_prompt_payload(use_docket_tool),
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def run_inspect_fixture(
    samples: Sequence[InspectTaskSample],
    solvers: Sequence[HarnessSolver],
) -> InspectTaskRun:
    """Run a local no-network fixture evaluation over samples and solvers."""

    if not samples:
        raise ValueError("at least one sample is required")
    if not solvers:
        raise ValueError("at least one solver is required")

    results: list[InspectCaseRunResult] = []
    for sample in samples:
        for solver in solvers:
            docket_tool = sample.build_docket_tool()
            response = solver.solve(
                HarnessRequest(sample=sample, docket_tool=docket_tool)
            )
            results.append(
                InspectCaseRunResult(
                    sample_id=sample.sample_id,
                    candidate_id=sample.packet.candidate_id,
                    case_id=sample.packet.case_id,
                    related_family_id=sample.packet.related_family_id,
                    mdl_family_id=sample.packet.mdl_family_id,
                    solver_id=solver.solver_id,
                    solver_kind=solver.solver_kind,
                    run_label=sample.effective_run_label,
                    ablation=sample.packet.ablation.value,
                    raw_output=response.raw_output,
                    raw_output_sha256=response.raw_output_sha256,
                    required_unit_ids=sample.required_unit_ids,
                    request_count=response.request_count,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    estimated_total_tokens=response.estimated_total_tokens,
                    estimated_cost=response.estimated_cost,
                    tool_call_logs=tuple(docket_tool.call_log_records()),
                    metadata=response.metadata,
                    execution_backend=_execution_backend(response.metadata),
                )
            )
    return InspectTaskRun(results=tuple(results))


def _tool_prompt_payload(use_docket_tool: bool) -> dict[str, Any]:
    if not use_docket_tool:
        return {
            "available": [],
            "rule": "No tools are available for this run mode.",
        }
    return {
        "available": [
            "list_available_docket_entries",
            "read_docket_entry(entry_number)",
        ],
        "rule": "Use only pre-decision allowed docket entries.",
    }


def _allowed_entry_numbers(packet: ModelPacket) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                document.docket_entry_number
                for document in packet.documents
                if document.docket_entry_number is not None
            }
        )
    )


def _controlled_entries_from_packet(
    packet: ModelPacket,
) -> tuple[ControlledDocketEntry, ...]:
    grouped: dict[int, list[tuple[str, str, str]]] = {}
    for document in packet.documents:
        if document.docket_entry_number is None:
            continue
        grouped.setdefault(document.docket_entry_number, []).append(
            (
                document.source_document_id,
                document.document_role.value,
                document.text,
            )
        )

    entries: list[ControlledDocketEntry] = []
    for entry_number, values in sorted(grouped.items()):
        source_document_ids = tuple(value[0] for value in values)
        descriptions = ", ".join(value[1] for value in values)
        text = "\n\n".join(value[2] for value in values)
        entries.append(
            ControlledDocketEntry(
                entry_number=entry_number,
                docket_text=text,
                source_document_ids=source_document_ids,
                description=descriptions,
                is_predecision_material=True,
                contains_target_outcome=False,
                is_mounted_for_model=True,
            )
        )
    if not entries:
        raise ValueError(
            "model packet must expose at least one controlled docket entry"
        )
    return tuple(entries)


def _exercise_controlled_tool(docket_tool: ControlledDocketTool) -> None:
    listed = docket_tool.list_available_docket_entries()
    if not listed.ok or not listed.available_entries:
        return
    docket_tool.read_docket_entry(listed.available_entries[0].entry_number)


def _execution_backend(
    metadata: Mapping[str, str] | None,
) -> RunExecutionBackend:
    if metadata is None:
        return RunExecutionBackend.LOCAL_FIXTURE
    value = metadata.get("execution_backend")
    if value is None:
        return RunExecutionBackend.LOCAL_FIXTURE
    return RunExecutionBackend(value)


def _sha256_prefixed(value: str) -> str:
    encoded = value.encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")

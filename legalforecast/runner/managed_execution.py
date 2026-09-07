"""Managed OpenAI agent runtime for the official document-tool condition."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from openai.types.responses import Response
from pydantic import BaseModel, Field
from pydantic_ai import (
    Agent,
    AgentRetries,
    ModelAPIError,
    ModelHTTPError,
    ModelResponse,
    RunContext,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.live_model_solver import (
    LiveModelProviderError,
    SolverResponse,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.response_verification import (
    require_publishable_response_metadata,
    verify_provider_response,
)
from legalforecast.multiharness.adapters import ToolExecutor
from legalforecast.multiharness.tool_protocol import ToolRequest
from legalforecast.release import ForecastExecution, ForecastPredictionUnit
from legalforecast.runner.ledger import RunValidationError

MAX_AGENT_REQUESTS = 24
MAX_AGENT_TOOL_CALLS = 96


class ManagedToolAgentError(RuntimeError):
    """The managed official agent did not produce a publishable result."""


@dataclass(frozen=True, slots=True)
class ManagedCaseInput:
    """The locations and bytes exposed to one official tool container."""

    case_id: str
    required_unit_ids: tuple[str, ...]
    documents: Mapping[str, bytes]
    unit_descriptions: tuple[Mapping[str, str], ...]
    document_descriptions: tuple[Mapping[str, str], ...]
    cell_id: str


class _ObservedTierOpenAIResponsesModel(OpenAIResponsesModel):
    """Retain OpenAI's actual Responses service tier in normalized metadata."""

    def _process_response(
        self,
        response: Response,
        model_settings: OpenAIResponsesModelSettings,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        normalized = super()._process_response(
            response, model_settings, model_request_parameters
        )
        service_tier = getattr(response, "service_tier", None)
        details = dict(normalized.provider_details or {})
        if isinstance(service_tier, str) and service_tier:
            details["service_tier"] = service_tier
        return replace(normalized, provider_details=details or None)


class ForecastPrediction(BaseModel):
    """One model-authored prediction in a case envelope."""

    unit_id: str = Field(min_length=1)
    probability_fully_dismissed: float = Field(ge=0.0, le=1.0)


class ForecastEnvelope(BaseModel):
    """The single final result returned for every unit in one case."""

    case_assessment: str = Field(min_length=1)
    predictions: tuple[ForecastPrediction, ...] = Field(min_length=1)


@dataclass(slots=True)
class ManagedToolAgentDeps:
    """Container-backed tools and invocation state for one case."""

    executor: ToolExecutor
    workspace: Path
    request_id: str
    call_count: int = 0
    called_tools: list[str] = field(default_factory=list[str])

    def invoke(self, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Execute one typed request through the network-disabled container."""

        self.call_count += 1
        request = ToolRequest(
            request_id=f"{self.request_id}:tool:{self.call_count}",
            operation=operation,
            arguments=dict(arguments),
            input_paths=(),
        )
        response = self.executor.execute(request, self.workspace)
        if response.request_id != request.request_id:
            raise ManagedToolAgentError("tool response request id does not match")
        if response.status != "succeeded":
            return {"error": response.error_code or "tool_failed"}
        self.called_tools.append(operation)
        return dict(response.output)


async def bash(ctx: RunContext[ManagedToolAgentDeps], command: str) -> dict[str, Any]:
    """Run a command in the persistent, network-disabled workspace shell."""

    return ctx.deps.invoke("bash", {"command": command})


async def read(
    ctx: RunContext[ManagedToolAgentDeps],
    file_path: str,
    offset: int = 0,
    limit: int = 2000,
) -> dict[str, Any]:
    """Read a UTF-8 workspace file, optionally selecting a range of lines."""

    return ctx.deps.invoke(
        "read", {"file_path": file_path, "offset": offset, "limit": limit}
    )


async def write(
    ctx: RunContext[ManagedToolAgentDeps], file_path: str, content: str
) -> dict[str, Any]:
    """Write a UTF-8 file under the workspace output directory."""

    return ctx.deps.invoke("write", {"file_path": file_path, "content": content})


async def edit(
    ctx: RunContext[ManagedToolAgentDeps],
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> dict[str, Any]:
    """Replace exact text in a file under the workspace output directory."""

    return ctx.deps.invoke(
        "edit",
        {
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": replace_all,
        },
    )


async def glob(
    ctx: RunContext[ManagedToolAgentDeps], pattern: str, path: str | None = None
) -> dict[str, Any]:
    """List workspace files matching a glob, defaulting to the documents tree."""

    arguments: dict[str, Any] = {"pattern": pattern}
    if path is not None:
        arguments["path"] = path
    return ctx.deps.invoke("glob", arguments)


async def grep(
    ctx: RunContext[ManagedToolAgentDeps],
    pattern: str,
    path: str | None = None,
    glob: str = "*",
    output_mode: str = "files_with_matches",
) -> dict[str, Any]:
    """Search workspace documents with a regular expression."""

    arguments: dict[str, Any] = {
        "pattern": pattern,
        "glob": glob,
        "output_mode": output_mode,
    }
    if path is not None:
        arguments["path"] = path
    return ctx.deps.invoke("grep", arguments)


MANAGED_TOOLS = (bash, read, write, edit, glob, grep)


@dataclass(frozen=True, slots=True)
class ManagedToolAgentResult:
    """Final envelope and aggregate usage from one managed agent run."""

    raw_output: str
    request_count: int
    input_tokens: int
    output_tokens: int
    served_model: str
    finish_reason: str
    service_tier: str
    called_tools: tuple[str, ...]
    response_usages: tuple[tuple[int, int], ...]


def run_managed_tool_agent(
    entry: ModelRegistryEntry,
    *,
    initial_prompt: str,
    required_unit_ids: Sequence[str],
    executor: ToolExecutor,
    workspace: Path,
    request_id: str,
    api_key: str | None = None,
    model: Model | None = None,
) -> ManagedToolAgentResult:
    """Run one case with Pydantic AI's native tool loop and bounded usage."""

    if entry.provider != "openai":
        raise ManagedToolAgentError("managed document tools currently require OpenAI")
    if not required_unit_ids:
        raise ManagedToolAgentError("managed agent requires prediction unit ids")
    resolved_model = model or _ObservedTierOpenAIResponsesModel(
        cast(Any, entry.model_id),
        provider=OpenAIProvider(api_key=api_key),
    )
    settings = OpenAIResponsesModelSettings(
        max_tokens=entry.max_output_tokens,
        parallel_tool_calls=False,
        openai_service_tier="flex",
        openai_store=False,
    )
    if entry.reasoning_effort is not None:
        settings["openai_reasoning_effort"] = cast(Any, entry.reasoning_effort.value)
    unit_ids = json.dumps(list(required_unit_ids), separators=(",", ":"))
    agent = Agent(
        resolved_model,
        output_type=ForecastEnvelope,
        deps_type=ManagedToolAgentDeps,
        instructions=(
            "Forecast the actual first written court disposition of the identified "
            "motion to dismiss, not what the court should decide or whether "
            "dismissal would be legally correct. For each prediction unit, forecast "
            "whether its frozen claim against the identified defendant or defendant "
            "group is fully dismissed in that disposition. A full dismissal leaves "
            "no material part of the unit alive; a partial dismissal that leaves "
            "any theory, claim, defendant group, or requested relief in that unit "
            "alive is not a "
            "full dismissal. Leave to amend does not change a full-dismissal outcome. "
            "Use the workspace tools to inspect the available pre-decision evidence; "
            "web access is unavailable. The docket may refer to documents that are not "
            "included in the workspace. Do not substitute later orders, amendments, "
            "appeals, settlements, or later voluntary dismissals for the first written "
            "disposition. Return one prediction for every required unit id exactly "
            "once, with probability_fully_dismissed from 0 to 1. Required unit ids: "
            f"{unit_ids}."
        ),
        tools=list(MANAGED_TOOLS),
        model_settings=settings,
        retries=AgentRetries(tools=1, output=1),
        tool_timeout=60.0,
    )
    deps = ManagedToolAgentDeps(
        executor=executor,
        workspace=workspace,
        request_id=request_id,
    )
    usage = RunUsage()
    result = agent.run_sync(
        initial_prompt,
        deps=deps,
        usage=usage,
        usage_limits=UsageLimits(
            request_limit=MAX_AGENT_REQUESTS,
            tool_calls_limit=MAX_AGENT_TOOL_CALLS,
        ),
    )
    output_ids = tuple(item.unit_id for item in result.output.predictions)
    if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(
        required_unit_ids
    ):
        raise ManagedToolAgentError("managed agent returned the wrong prediction units")
    responses = tuple(
        message
        for message in result.all_messages()
        if isinstance(message, ModelResponse)
    )
    served_models = {
        response.model_name
        for response in responses
        if isinstance(response.model_name, str) and response.model_name
    }
    if len(served_models) != 1:
        raise ManagedToolAgentError(
            "provider responses changed or omitted served model"
        )
    served_model = served_models.pop()
    response = result.response
    finish_reason = response.finish_reason
    if not isinstance(finish_reason, str) or not finish_reason:
        raise ManagedToolAgentError("provider response did not report finish reason")
    service_tiers = {
        tier
        for item in responses
        if isinstance((tier := (item.provider_details or {}).get("service_tier")), str)
        and tier
    }
    if len(service_tiers) != 1 or any(
        not isinstance((item.provider_details or {}).get("service_tier"), str)
        for item in responses
    ):
        raise ManagedToolAgentError(
            "provider responses changed or omitted service tier"
        )
    service_tier = service_tiers.pop()
    return ManagedToolAgentResult(
        raw_output=result.output.model_dump_json(),
        request_count=usage.requests,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        served_model=served_model,
        finish_reason=finish_reason,
        service_tier=service_tier,
        called_tools=tuple(deps.called_tools),
        response_usages=tuple(
            (item.usage.input_tokens, item.usage.output_tokens) for item in responses
        ),
    )


def uses_managed_document_tools(entry: ModelRegistryEntry) -> bool:
    """Select the owner-authorized official Luna tool condition."""

    return entry.provider == "openai" and entry.model_id == "gpt-5.6-luna"


def build_managed_case_input(
    execution: ForecastExecution,
    units: tuple[ForecastPredictionUnit, ...],
    model_visible_document_indexes: tuple[int, ...],
    cell_id: str,
) -> ManagedCaseInput:
    """Stage only model-visible bytes and minimal public case identity."""

    case_id = units[0].case_id
    case = next(
        release_case
        for release_case in execution.release.cases
        if release_case.case_id == case_id
    )
    first_unit_id = units[0].unit_id
    documents: dict[str, bytes] = {}
    document_descriptions: list[Mapping[str, str]] = []
    for index in model_visible_document_indexes:
        document = case.documents[index]
        suffix = Path(document.path).suffix or ".txt"
        destination = f"documents/{index:04d}{suffix}"
        documents[destination] = execution.document_bytes(first_unit_id, index)
        description = {
            "path": f"/workspace/{destination}",
            "document_id": document.document_id,
            "role": document.role,
        }
        if document.supporting_side is not None:
            description["supporting_side"] = document.supporting_side
        if document.supporting_kind is not None:
            description["supporting_kind"] = document.supporting_kind
        if document.target_motion_document_id is not None:
            description["target_motion_document_id"] = (
                document.target_motion_document_id
            )
        document_descriptions.append(description)
    return ManagedCaseInput(
        case_id=case_id,
        required_unit_ids=tuple(unit.unit_id for unit in units),
        documents=documents,
        unit_descriptions=tuple(
            {
                "unit_id": unit.unit_id,
                "claim_name": unit.claim_name,
                "defendant_group": unit.defendant_group,
                "count": unit.count,
            }
            for unit in units
        ),
        document_descriptions=tuple(document_descriptions),
        cell_id=cell_id,
    )


def case_prompt(
    entry: ModelRegistryEntry,
    execution: ForecastExecution,
    units: tuple[ForecastPredictionUnit, ...],
    model_visible_document_indexes: tuple[int, ...],
    cell_id: str,
) -> str | ManagedCaseInput:
    """Return a minimized tool task or the authenticated legacy prompt."""

    if uses_managed_document_tools(entry):
        return build_managed_case_input(
            execution, units, model_visible_document_indexes, cell_id
        )
    prompt_bytes = execution.prompt_bytes(units[0].unit_id)
    try:
        return prompt_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunValidationError(
            f"prompt is not UTF-8 for unit {units[0].unit_id}"
        ) from exc


def complete_managed_tool_cell(
    entry: ModelRegistryEntry,
    *,
    handler: ProviderSpendAttemptHandler,
    managed_case: ManagedCaseInput,
    request_body_observer: Callable[[bytes], None],
    environ: Mapping[str, str] | None,
    registry_sha256: str,
) -> SolverResponse:
    """Authorize, run, and settle one entire managed agent session as one case."""

    from legalforecast.runner.tool_runtime import open_official_tool_session

    initial_prompt = _managed_initial_prompt(managed_case)
    commitment = ARTIFACT_CANONICAL_JSON_V1.encode(
        {
            "model": entry.model_id,
            "case_id": managed_case.case_id,
            "required_unit_ids": list(managed_case.required_unit_ids),
            "initial_prompt": initial_prompt,
            "tools": ["bash", "read", "write", "edit", "glob", "grep"],
        }
    )
    values = environ if environ is not None else os.environ
    api_key = values.get("OPENAI_API_KEY")
    if api_key is None or not api_key.strip():
        raise RunValidationError("OPENAI_API_KEY is required")

    def call(executor: ToolExecutor, workspace: Path) -> Mapping[str, object]:
        request_body_observer(commitment)
        try:
            result = run_managed_tool_agent(
                entry,
                initial_prompt=initial_prompt,
                required_unit_ids=managed_case.required_unit_ids,
                executor=executor,
                workspace=workspace,
                request_id=managed_case.cell_id,
                api_key=api_key.strip(),
            )
        except ModelHTTPError as exc:
            raise LiveModelProviderError(
                "managed OpenAI agent request failed",
                status_code=exc.status_code,
                retryable=False,
            ) from exc
        except ModelAPIError as exc:
            raise LiveModelProviderError(
                "managed OpenAI agent request failed",
                retryable=False,
            ) from exc
        if not result.called_tools:
            raise ManagedToolAgentError(
                "managed official agent returned without reading case documents"
            )
        estimated_cost_usd = _managed_estimated_cost(
            entry, response_usages=result.response_usages
        )
        return {
            "raw_output": result.raw_output,
            "request_count": result.request_count,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "served_model": result.served_model,
            "finish_reason": result.finish_reason,
            "service_tier": result.service_tier,
            "called_tools": list(result.called_tools),
            "estimated_cost_usd": estimated_cost_usd,
        }

    if handler.replayable_response is not None:

        def refuse_replay_transport() -> Mapping[str, object]:
            raise RuntimeError("replay attempted to invoke provider transport")

        payload = handler.run_attempt(1, refuse_replay_transport)
    else:
        # Local setup can fail without making a billable request. Complete it
        # before reserving spend or marking provider transport as started.
        with TemporaryDirectory(prefix="lfb-official-tools-") as temporary:
            workspace = Path(temporary)
            with open_official_tool_session(
                documents=managed_case.documents,
                workspace=workspace,
                session_id=managed_case.cell_id,
                environ=environ,
            ) as executor:
                payload = handler.run_attempt(1, lambda: call(executor, workspace))
    durable_attempt_ordinal = handler.durable_attempt_ordinal(1)
    try:
        raw_output = _managed_required_str(payload, "raw_output")
        request_count = _managed_required_int(payload, "request_count", positive=True)
        input_tokens = _managed_required_int(payload, "input_tokens")
        output_tokens = _managed_required_int(payload, "output_tokens")
        served_model = _managed_required_str(payload, "served_model")
        finish_reason = _managed_required_str(payload, "finish_reason")
        service_tier = _managed_required_str(payload, "service_tier")
        estimated_cost = _managed_required_float(payload, "estimated_cost_usd")
        if served_model != entry.model_version_or_snapshot:
            raise RunValidationError(
                "managed provider served model differs from frozen registry"
            )
        if service_tier != "flex":
            raise RunValidationError(
                "managed OpenAI response did not use requested Flex service tier"
            )
        verification = verify_provider_response(
            {"finish_reason": finish_reason}, provider="openai"
        )
        metadata = {
            "provider": entry.provider,
            "model": entry.model_id,
            "model_id": entry.model_id,
            "model_version_or_snapshot": entry.model_version_or_snapshot,
            "served_model_version": served_model,
            "execution_backend": "pydantic_ai",
            "provider_attempt_count": str(request_count),
            "model_registry_sha256": registry_sha256,
            "tool_policy": "closed_harvey_tools",
            "service_tier": service_tier,
            "requested_service_tier": "flex",
            "observed_service_tier": service_tier,
            **verification.to_metadata(),
        }
        require_publishable_response_metadata(metadata)
    except BaseException as exc:
        handler.record_post_response_failure(
            durable_attempt_ordinal,
            failure_type=type(exc).__name__,
        )
        raise
    handler.settle_attempt(
        durable_attempt_ordinal,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        actual_cost_usd=estimated_cost,
        raw_output=raw_output,
    )
    return SolverResponse(
        raw_output=raw_output,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        metadata=metadata,
    )


def _managed_initial_prompt(managed_case: ManagedCaseInput) -> str:
    return json.dumps(
        {
            "case_id": managed_case.case_id,
            "task": "forecast_motion_to_dismiss",
            "prediction_units": list(managed_case.unit_descriptions),
            "documents": list(managed_case.document_descriptions),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _managed_required_str(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


def _managed_required_int(
    payload: Mapping[str, object], field_name: str, *, positive: bool = False
) -> int:
    value = payload.get(field_name)
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


def _managed_estimated_cost(
    entry: ModelRegistryEntry,
    *,
    response_usages: Sequence[tuple[int, int]],
) -> float:
    total = 0.0
    for input_tokens, output_tokens in response_usages:
        input_price = entry.input_token_price
        output_price = entry.output_token_price
        surcharge = entry.long_context_surcharge
        if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
            input_price *= surcharge.input_price_multiplier
            output_price *= surcharge.output_price_multiplier
        total += (input_tokens * input_price) + (output_tokens * output_price)
    return total / 1_000_000


def _managed_required_float(payload: Mapping[str, object], field_name: str) -> float:
    value = payload.get(field_name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return float(value)


__all__ = [
    "ForecastEnvelope",
    "ManagedCaseInput",
    "ManagedToolAgentDeps",
    "ManagedToolAgentError",
    "ManagedToolAgentResult",
    "build_managed_case_input",
    "case_prompt",
    "complete_managed_tool_cell",
    "run_managed_tool_agent",
    "uses_managed_document_tools",
]

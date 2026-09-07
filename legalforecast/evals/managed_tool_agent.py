"""Managed OpenAI agent runtime for the official document-tool condition."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from openai.types.responses import Response
from pydantic import BaseModel, Field
from pydantic_ai import Agent, AgentRetries, ModelResponse, RunContext
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.adapters import ToolExecutor
from legalforecast.multiharness.tool_protocol import ToolRequest

MAX_AGENT_REQUESTS = 24
MAX_AGENT_TOOL_CALLS = 96


class ManagedToolAgentError(RuntimeError):
    """The managed official agent did not produce a publishable result."""


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
            "Forecast the disposition of the identified motion from only the "
            "documents available in the workspace. Use the workspace tools to "
            "read whatever evidence you need; web access is unavailable. Return "
            "one prediction for every required unit id exactly once. Required "
            f"unit ids: {unit_ids}."
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


__all__ = [
    "ForecastEnvelope",
    "ManagedToolAgentDeps",
    "ManagedToolAgentError",
    "ManagedToolAgentResult",
    "run_managed_tool_agent",
]

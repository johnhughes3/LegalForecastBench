"""Pinned Claude Agent SDK community baseline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import platform
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.evals.output_parser import parse_model_output
from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.multiharness.validation import validate_public_record

CLAUDE_AGENT_SDK_ADAPTER_ID = "claude-agent-sdk-baseline"
CLAUDE_AGENT_SDK_ADAPTER_VERSION = "1.0.0"
CLAUDE_AGENT_SDK_VERSION = "0.2.143"
CLAUDE_BUNDLED_CLI_VERSION = "2.1.238"
CLAUDE_BUNDLED_CLI_SHA256_BY_PLATFORM: Mapping[str, str] = {
    "darwin-arm64": (
        "sha256:1c196c456373b57818ae87df84aecee96cb659448c0d6a6bbb401ac5758431b2"
    ),
    "darwin-x86_64": (
        "sha256:d10bc7bb1720435f8830aa3ee74085f09348d2b1a2a152bdee251b770d76cc73"
    ),
    "linux-aarch64": (
        "sha256:28d736120a6b14c5eae1ad1470e73371818c9c2fa41e0b3c7040207aa2d4edee"
    ),
    "linux-x86_64": (
        "sha256:0933b286cf94e1b2504b35ac165ab76b8f822735d53371c56393988c23040d58"
    ),
    "win32-x86_64": (
        "sha256:223bc058b5aef48138876e28de5d00387e4fd7362a18e733143bf00819c01aab"
    ),
}
CLAUDE_PROVIDER_ENV_VAR = "ANTHROPIC_API_KEY"
CLAUDE_MAX_TURNS = 8
CLAUDE_MAX_BUDGET_USD = 0.5
CLAUDE_OUTPUT_CONTRACT_VERSION = "legalforecast.claude_agent_sdk.output.v1"
CLAUDE_PROMPT_VERSION = "legalforecast.claude_agent_sdk.prompt.v1"
CLAUDE_TOOL_CONTRACT_VERSION = "legalforecast.claude_agent_sdk.tool.v1"

_MCP_SERVER_NAME = "legalforecast"
_READ_TASK_TOOL_NAME = "read_canonical_task"
_QUALIFIED_READ_TASK_TOOL_NAME = f"mcp__{_MCP_SERVER_NAME}__{_READ_TASK_TOOL_NAME}"
_SUBSCRIPTION_CREDENTIAL_ENV_VARS = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_AUTH_TOKEN",
)


class ClaudeAgentSDKAdapterError(RuntimeError):
    """A request or SDK response violated the baseline contract."""


def claude_bundled_runtime_pin(
    *,
    sys_platform: str | None = None,
    machine: str | None = None,
) -> tuple[str, str]:
    """Return the executable name and digest for the locked platform wheel."""

    observed_platform = sys.platform if sys_platform is None else sys_platform
    observed_machine = platform.machine() if machine is None else machine
    normalized_machine = observed_machine.strip().lower()
    if normalized_machine in {"amd64", "x86_64"}:
        normalized_machine = "x86_64"
    elif normalized_machine in {"arm64", "aarch64"}:
        normalized_machine = "arm64" if observed_platform == "darwin" else "aarch64"
    platform_key = f"{observed_platform}-{normalized_machine}"
    expected_sha256 = CLAUDE_BUNDLED_CLI_SHA256_BY_PLATFORM.get(platform_key)
    if expected_sha256 is None:
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK platform is not pinned")
    executable_name = "claude.exe" if observed_platform == "win32" else "claude"
    return executable_name, expected_sha256


class ToolTransport(Protocol):
    """Transport from the provider adapter to the host-owned tool runtime."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute one bounded canonical tool request."""

        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ClaudeSDKRunConfig:
    """Provider-independent configuration supplied to an SDK executor."""

    request_id: str
    requested_model: str
    prompt: str
    output_schema: Mapping[str, Any]
    working_directory: Path
    config_directory: Path
    session_id: str
    max_turns: int = CLAUDE_MAX_TURNS
    max_budget_usd: float = CLAUDE_MAX_BUDGET_USD


@dataclass(frozen=True, slots=True)
class ClaudeSDKExecution:
    """Validated facts returned by one isolated SDK execution."""

    structured_output: object
    served_model: str
    sdk_version: str
    bundled_cli_version: str
    bundled_cli_sha256: str
    tool_call_count: int
    num_turns: int
    duration_ms: int
    duration_api_ms: int
    total_cost_usd: float
    usage: Mapping[str, object]


class ClaudeSDKExecutor(Protocol):
    """Execution seam implemented by the pinned SDK and offline fakes."""

    def execute(
        self,
        config: ClaudeSDKRunConfig,
        *,
        tool_transport: ToolTransport,
    ) -> ClaudeSDKExecution:
        """Execute one provider request in an isolated SDK session."""

        raise NotImplementedError


def build_capabilities() -> AdapterCapabilities:
    """Return the exact public capabilities of the real baseline."""

    semantics = {
        "adapter_id": CLAUDE_AGENT_SDK_ADAPTER_ID,
        "adapter_version": CLAUDE_AGENT_SDK_ADAPTER_VERSION,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
        "max_budget_usd": CLAUDE_MAX_BUDGET_USD,
        "max_turns": CLAUDE_MAX_TURNS,
        "output_contract_version": CLAUDE_OUTPUT_CONTRACT_VERSION,
        "prompt_version": CLAUDE_PROMPT_VERSION,
        "sdk_name": "claude-agent-sdk",
        "sdk_version": CLAUDE_AGENT_SDK_VERSION,
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "supports_sandbox_policy": True,
        "tool_contract_version": CLAUDE_TOOL_CONTRACT_VERSION,
        "tool_protocol_version": TOOL_REQUEST_SCHEMA_VERSION,
    }
    return AdapterCapabilities(
        adapter_id=CLAUDE_AGENT_SDK_ADAPTER_ID,
        adapter_version=CLAUDE_AGENT_SDK_ADAPTER_VERSION,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        supports_sandbox_policy=True,
        tool_protocol_version=TOOL_REQUEST_SCHEMA_VERSION,
        capabilities_sha256=_record_sha256(semantics),
    )


def run_offline_protocol_fixture(request: RunRequest, workspace: Path) -> RunResult:
    """Return a credential-free fixture result for standard conformance."""

    _validate_request(request)
    if request.task.metadata.get("fixture") != "adapter-conformance":
        raise ClaudeAgentSDKAdapterError(
            "ordinary run is restricted to the adapter conformance fixture"
        )
    if request.sandbox_policy.allowed_provider_env_vars:
        raise ClaudeAgentSDKAdapterError(
            "offline conformance must not receive provider environment grants"
        )
    summary: dict[str, Any] = {
        "adapter_id": CLAUDE_AGENT_SDK_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": CLAUDE_AGENT_SDK_ADAPTER_VERSION,
        "auth_mode": "none-offline-protocol-fixture",
        "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
        "model_key": request.model_key,
        "offline_protocol_fixture": True,
        "provider": "anthropic",
        "provider_request_count": 0,
        "requested_model": request.model_key,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "sdk_name": "claude-agent-sdk",
        "sdk_version": CLAUDE_AGENT_SDK_VERSION,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": 0,
    }
    validate_public_record(summary, "claude_agent_sdk.offline_summary")
    workspace.mkdir(parents=True, exist_ok=True)
    return RunResult(
        result_id=f"{request.request_id}:claude-agent-sdk:offline-fixture",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_record_sha256(summary),
        public_summary=summary,
    )


def run_claude_agent_sdk(
    request: RunRequest,
    workspace: Path,
    *,
    tool_transport: ToolTransport,
    executor: ClaudeSDKExecutor,
) -> RunResult:
    """Run one pinned Claude Agent SDK session for a canonical LFB task."""

    _validate_request(request)
    validate_provider_grant(request)
    requested_model = _requested_model(request.model_key)
    required_unit_ids = _required_unit_ids(request)
    private_logs = workspace / "private-logs"
    working_directory = private_logs / "claude-workdir"
    config_directory = private_logs / "claude-config"
    for directory in (private_logs, working_directory, config_directory):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
    config = ClaudeSDKRunConfig(
        request_id=request.request_id,
        requested_model=requested_model,
        prompt=_prompt(request, required_unit_ids),
        output_schema=_output_schema(required_unit_ids),
        working_directory=working_directory,
        config_directory=config_directory,
        session_id=_session_id(request.request_id),
    )
    try:
        execution = executor.execute(config, tool_transport=tool_transport)
    except ClaudeAgentSDKAdapterError:
        raise
    except Exception:
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK request failed") from None
    _validate_execution(execution)
    if execution.tool_call_count != 1:
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK must call the canonical task tool exactly once"
        )
    _validate_structured_output_shape(
        execution.structured_output,
        required_unit_ids,
    )
    encoded_output = _encoded_structured_output(execution.structured_output)
    parsed = parse_model_output(
        encoded_output.decode("utf-8"),
        required_unit_ids=required_unit_ids,
    )
    if not parsed.is_valid:
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK structured output is invalid"
        )
    output_path = private_logs / "claude-structured-output.json"
    output_path.write_bytes(encoded_output)
    output_path.chmod(0o600)
    output_sha256 = f"sha256:{hashlib.sha256(encoded_output).hexdigest()}"
    summary = _successful_summary(
        request=request,
        execution=execution,
        requested_model=requested_model,
        output_sha256=output_sha256,
    )
    validate_public_record(summary, "claude_agent_sdk.public_summary")
    commitment = {
        "parsed_output": parsed.to_record(),
        "public_summary": summary,
        "request_sha256": request.request_sha256,
    }
    return RunResult(
        result_id=f"{request.request_id}:claude-agent-sdk",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_record_sha256(commitment),
        artifacts=(
            ArtifactRecord(
                artifact_id="claude-structured-output-private",
                path="private-logs/claude-structured-output.json",
                sha256=output_sha256,
                media_type="application/json",
                public=False,
                size_bytes=len(encoded_output),
            ),
        ),
        public_summary=summary,
    )


def validate_provider_grant(request: RunRequest) -> None:
    """Fail unless the live request grants only the pinned provider key."""

    if request.sandbox_policy.allowed_provider_env_vars != (CLAUDE_PROVIDER_ENV_VAR,):
        raise ClaudeAgentSDKAdapterError(
            "provider environment grant must contain exactly ANTHROPIC_API_KEY"
        )


def validate_process_auth_environment(environ: Mapping[str, str]) -> None:
    """Reject subscription or alternate auth material in the live process."""

    for name in _SUBSCRIPTION_CREDENTIAL_ENV_VARS:
        if environ.get(name, "").strip():
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK live runs permit API-key authentication only"
            )


def _validate_request(request: RunRequest) -> None:
    if request.adapter.adapter_id != CLAUDE_AGENT_SDK_ADAPTER_ID:
        raise ClaudeAgentSDKAdapterError("request adapter id does not match")
    if request.adapter.adapter_version != CLAUDE_AGENT_SDK_ADAPTER_VERSION:
        raise ClaudeAgentSDKAdapterError("request adapter version does not match")
    if request.task.family != "legalforecast_mtd":
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK baseline supports only legalforecast_mtd"
        )
    if request.task.scoring_mode != "lfb_brier":
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK baseline supports only lfb_brier"
        )


def _requested_model(model_key: str) -> str:
    prefix = "anthropic:"
    if not model_key.startswith(prefix) or len(model_key) == len(prefix):
        raise ClaudeAgentSDKAdapterError(
            "model_key must use the anthropic:<model> namespace"
        )
    return model_key[len(prefix) :]


def _required_unit_ids(request: RunRequest) -> tuple[str, ...]:
    value = request.task.metadata.get("required_unit_ids")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ClaudeAgentSDKAdapterError(
            "task metadata required_unit_ids must be an array"
        )
    unit_ids: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ClaudeAgentSDKAdapterError(
                "task metadata required_unit_ids must contain non-empty strings"
            )
        unit_ids.append(item)
    if not unit_ids or len(unit_ids) != len(set(unit_ids)):
        raise ClaudeAgentSDKAdapterError(
            "task metadata required_unit_ids must be non-empty and unique"
        )
    return tuple(unit_ids)


def _prompt(request: RunRequest, required_unit_ids: Sequence[str]) -> str:
    identity = json.dumps(
        {
            "request_id": request.request_id,
            "required_unit_ids": list(required_unit_ids),
            "task_id": request.task.task_id,
            "task_sha256": request.task.task_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        "Produce one LegalForecastBench forecast. First call "
        f"{_QUALIFIED_READ_TASK_TOOL_NAME} exactly once to read the complete "
        "host-authenticated solver prompt. Use no information outside that "
        "prompt. Return "
        "only the required structured output, with a non-empty case_assessment "
        "and exactly one probability_fully_dismissed from 0 through 1 for each "
        f"required unit. Public task identity: {identity}"
    )


def _output_schema(required_unit_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "case_assessment": {"type": "string", "minLength": 1},
            "predictions": {
                "type": "array",
                "minItems": len(required_unit_ids),
                "maxItems": len(required_unit_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "unit_id": {
                            "type": "string",
                            "enum": list(required_unit_ids),
                        },
                        "probability_fully_dismissed": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": [
                        "unit_id",
                        "probability_fully_dismissed",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["case_assessment", "predictions"],
        "additionalProperties": False,
    }


def _session_id(request_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"legalforecast:{request_id}"))


def _validate_execution(execution: ClaudeSDKExecution) -> None:
    if execution.sdk_version != CLAUDE_AGENT_SDK_VERSION:
        raise ClaudeAgentSDKAdapterError(
            "installed Claude Agent SDK version does not match"
        )
    if execution.bundled_cli_version != CLAUDE_BUNDLED_CLI_VERSION:
        raise ClaudeAgentSDKAdapterError("bundled Claude Code version does not match")
    _, expected_sha256 = claude_bundled_runtime_pin()
    if execution.bundled_cli_sha256 != expected_sha256:
        raise ClaudeAgentSDKAdapterError("bundled Claude Code digest does not match")
    if not execution.served_model.strip():
        raise ClaudeAgentSDKAdapterError("served model identity is missing")
    for value, name in (
        (execution.tool_call_count, "tool_call_count"),
        (execution.num_turns, "num_turns"),
        (execution.duration_ms, "duration_ms"),
        (execution.duration_api_ms, "duration_api_ms"),
    ):
        _validate_non_negative_int(value, name)
    _validate_non_negative_number(execution.total_cost_usd, "total_cost_usd")


def _validate_non_negative_int(value: object, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ClaudeAgentSDKAdapterError(f"{field_name} is invalid")


def _validate_non_negative_number(value: object, field_name: str) -> None:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ClaudeAgentSDKAdapterError(f"{field_name} is invalid")


def _encoded_structured_output(value: object) -> bytes:
    if not isinstance(value, Mapping):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK structured output must be an object"
        )
    try:
        return (
            json.dumps(
                dict(cast(Mapping[str, object], value)),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK structured output must be JSON"
        ) from None


def _validate_structured_output_shape(
    value: object,
    required_unit_ids: Sequence[str],
) -> None:
    if not isinstance(value, Mapping):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK structured output must be an object"
        )
    record = cast(Mapping[object, object], value)
    if set(record) != {"case_assessment", "predictions"}:
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK structured output has unexpected fields"
        )
    assessment = record["case_assessment"]
    if not isinstance(assessment, str) or not assessment.strip():
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK case assessment is invalid")
    predictions = record["predictions"]
    if not isinstance(predictions, list):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK predictions must be an array"
        )
    observed_unit_ids: list[str] = []
    for prediction_value in cast(list[object], predictions):
        if not isinstance(prediction_value, Mapping):
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK prediction must be an object"
            )
        prediction = cast(Mapping[object, object], prediction_value)
        if not {"unit_id", "probability_fully_dismissed"} <= set(prediction) or not set(
            prediction
        ) <= {"unit_id", "probability_fully_dismissed", "rationale"}:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK prediction has unexpected fields"
            )
        unit_id = prediction["unit_id"]
        if not isinstance(unit_id, str) or not unit_id:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK prediction unit id is invalid"
            )
        rationale = prediction.get("rationale")
        if rationale is not None and not isinstance(rationale, str):
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK prediction rationale is invalid"
            )
        observed_unit_ids.append(unit_id)
    if len(observed_unit_ids) != len(set(observed_unit_ids)) or tuple(
        sorted(observed_unit_ids)
    ) != tuple(sorted(required_unit_ids)):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK prediction unit ids do not match the task"
        )


def _successful_summary(
    *,
    request: RunRequest,
    execution: ClaudeSDKExecution,
    requested_model: str,
    output_sha256: str,
) -> dict[str, Any]:
    usage = _validated_usage(execution.usage)
    return {
        "adapter_id": CLAUDE_AGENT_SDK_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": CLAUDE_AGENT_SDK_ADAPTER_VERSION,
        "auth_mode": "anthropic-api-key",
        "bundled_cli_sha256": execution.bundled_cli_sha256,
        "bundled_cli_version": execution.bundled_cli_version,
        "duration_api_ms": execution.duration_api_ms,
        "duration_ms": execution.duration_ms,
        "max_budget_usd": CLAUDE_MAX_BUDGET_USD,
        "max_turns": CLAUDE_MAX_TURNS,
        "model_key": request.model_key,
        "num_turns": execution.num_turns,
        "output_contract_version": CLAUDE_OUTPUT_CONTRACT_VERSION,
        "prompt_version": CLAUDE_PROMPT_VERSION,
        "provider": "anthropic",
        "python_version": sys.version.split()[0],
        "requested_model": requested_model,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "sdk_name": "claude-agent-sdk",
        "sdk_version": execution.sdk_version,
        "served_model": execution.served_model,
        "structured_output_sha256": output_sha256,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": execution.tool_call_count,
        "tool_contract_version": CLAUDE_TOOL_CONTRACT_VERSION,
        "total_cost_usd": float(execution.total_cost_usd),
        **usage,
    }


def _validated_usage(usage: Mapping[str, object]) -> dict[str, int]:
    allowed = (
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "input_tokens",
        "output_tokens",
    )
    result: dict[str, int] = {}
    for field_name in allowed:
        if field_name not in usage:
            raise ClaudeAgentSDKAdapterError(
                f"Claude Agent SDK usage {field_name} is missing"
            )
        value = usage[field_name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ClaudeAgentSDKAdapterError(
                f"Claude Agent SDK usage {field_name} is invalid"
            )
        result[field_name] = value
    result["total_tokens"] = (
        result["input_tokens"]
        + result["output_tokens"]
        + result["cache_creation_input_tokens"]
        + result["cache_read_input_tokens"]
    )
    return result


def adapter_bundle_sha256() -> str:
    """Commit to the executable adapter, manifest, and locked dependency state."""

    project_root = Path(__file__).resolve().parents[2]
    relative_paths = (
        "legalforecast/multiharness/claude_agent_sdk.py",
        "legalforecast/multiharness/claude_agent_sdk_cli.py",
        "examples/adapters/claude-agent-sdk/adapter-manifest.json",
        "pyproject.toml",
        "uv.lock",
    )
    digest = hashlib.sha256()
    for relative_path in relative_paths:
        name = relative_path.encode("utf-8")
        try:
            payload = (project_root / relative_path).read_bytes()
        except OSError:
            raise ClaudeAgentSDKAdapterError(
                "adapter bundle provenance requires a source checkout"
            ) from None
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def run_async(coroutine: Any) -> Any:
    """Run one SDK coroutine from the synchronous command-adapter boundary."""

    return asyncio.run(coroutine)


def current_process_environment() -> Mapping[str, str]:
    """Return the live process environment through a narrow test seam."""

    return os.environ

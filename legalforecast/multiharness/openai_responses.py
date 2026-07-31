"""Pinned OpenAI Responses API community baseline."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.multiharness.validation import validate_public_record

OPENAI_RESPONSES_ADAPTER_ID = "openai-responses-baseline"
OPENAI_RESPONSES_ADAPTER_VERSION = "1.0.0"
OPENAI_SDK_VERSION = "2.46.0"
OPENAI_PROVIDER_ENV_VAR = "OPENAI_API_KEY"

_READ_TASK_TOOL_NAME = "read_canonical_task"
_READ_TASK_TOOL: dict[str, Any] = {
    "type": "function",
    "name": _READ_TASK_TOOL_NAME,
    "description": (
        "Read the public canonical task record staged by the host-owned tool container."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    "strict": True,
}


class OpenAIResponsesAdapterError(RuntimeError):
    """A request or provider response violated the baseline contract."""


class ResponsesResource(Protocol):
    """Typed subset of the pinned SDK Responses resource."""

    def create(self, **kwargs: Any) -> object:
        """Create one Responses API turn."""

        raise NotImplementedError


class OpenAIClient(Protocol):
    """Typed subset of the pinned OpenAI client."""

    responses: ResponsesResource


class ToolTransport(Protocol):
    """Transport from the provider adapter to the host-owned tool runtime."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute one bounded canonical tool request."""

        raise NotImplementedError


def build_capabilities() -> AdapterCapabilities:
    """Return the exact public capabilities of the real baseline."""

    semantics = {
        "adapter_id": OPENAI_RESPONSES_ADAPTER_ID,
        "adapter_version": OPENAI_RESPONSES_ADAPTER_VERSION,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "sdk_name": "openai",
        "sdk_version": OPENAI_SDK_VERSION,
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "supports_sandbox_policy": True,
        "tool_protocol_version": TOOL_REQUEST_SCHEMA_VERSION,
    }
    return AdapterCapabilities(
        adapter_id=OPENAI_RESPONSES_ADAPTER_ID,
        adapter_version=OPENAI_RESPONSES_ADAPTER_VERSION,
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
        raise OpenAIResponsesAdapterError(
            "ordinary run is restricted to the adapter conformance fixture"
        )
    if request.sandbox_policy.allowed_provider_env_vars:
        raise OpenAIResponsesAdapterError(
            "offline conformance must not receive provider environment grants"
        )
    requested_model = request.model_key
    summary: dict[str, Any] = {
        "adapter_id": OPENAI_RESPONSES_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": OPENAI_RESPONSES_ADAPTER_VERSION,
        "auth_mode": "none-offline-protocol-fixture",
        "model_key": request.model_key,
        "offline_protocol_fixture": True,
        "provider": "openai",
        "provider_request_count": 0,
        "requested_model": requested_model,
        "sdk_name": "openai",
        "sdk_version": OPENAI_SDK_VERSION,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": 0,
    }
    validate_public_record(summary, "openai_responses.offline_summary")
    workspace.mkdir(parents=True, exist_ok=True)
    return RunResult(
        result_id=f"{request.request_id}:openai-responses:offline-fixture",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_record_sha256(summary),
        public_summary=summary,
    )


def run_openai_responses(
    request: RunRequest,
    workspace: Path,
    *,
    tool_transport: ToolTransport,
    client: OpenAIClient,
    max_tool_calls: int = 8,
) -> RunResult:
    """Run the pinned Responses function-tool loop for one canonical task."""

    _validate_request(request)
    validate_provider_grant(request)
    if max_tool_calls <= 0:
        raise OpenAIResponsesAdapterError("max_tool_calls must be positive")

    requested_model = _requested_model(request.model_key)
    required_unit_ids = _required_unit_ids(request)
    conversation: list[Any] = _initial_input(request, required_unit_ids)
    common: dict[str, Any] = {
        "include": ["reasoning.encrypted_content"],
        "instructions": _instructions(required_unit_ids),
        "model": requested_model,
        "store": False,
        "tools": [_READ_TASK_TOOL],
    }
    response = _provider_request(
        client,
        **common,
        input=list(conversation),
        tool_choice="required",
    )
    provider_request_count = 1
    tool_call_count = 0
    seen_call_ids: set[str] = set()
    served_model: str | None = None
    input_tokens = 0
    output_tokens = 0

    while True:
        _require_completed_response(response)
        observed_model = _required_response_str(response, "model")
        if served_model is None:
            served_model = observed_model
        elif served_model != observed_model:
            raise OpenAIResponsesAdapterError(
                "OpenAI Responses served model changed within one run"
            )
        turn_input, turn_output = _response_usage(response)
        input_tokens += turn_input
        output_tokens += turn_output
        response_items = _response_output_items(response)
        calls = _function_calls(response_items)
        if calls:
            if tool_call_count + len(calls) > max_tool_calls:
                raise OpenAIResponsesAdapterError(
                    "OpenAI Responses tool call limit exceeded"
                )
            conversation.extend(response_items)
            for call in calls:
                call_id = _required_item_str(call, "call_id")
                if call_id in seen_call_ids:
                    raise OpenAIResponsesAdapterError(
                        "OpenAI Responses returned a duplicate function call id"
                    )
                seen_call_ids.add(call_id)
                name = _required_item_str(call, "name")
                if name != _READ_TASK_TOOL_NAME:
                    raise OpenAIResponsesAdapterError(
                        "OpenAI Responses requested an unsupported tool"
                    )
                _validate_empty_arguments(_required_item_str(call, "arguments"))
                tool_call_count += 1
                tool_request = ToolRequest(
                    request_id=(f"{request.request_id}:openai-tool:{tool_call_count}"),
                    operation="read_text",
                    arguments={"encoding": "utf-8"},
                    input_paths=("task.json",),
                )
                tool_response = tool_transport.execute(tool_request)
                if tool_response.request_id != tool_request.request_id:
                    raise OpenAIResponsesAdapterError(
                        "host tool response request id does not match"
                    )
                if tool_response.status != "succeeded":
                    raise OpenAIResponsesAdapterError("host tool request failed")
                conversation.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(
                            tool_response.to_record()["output"],
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                )
            response = _provider_request(
                client,
                **common,
                input=list(conversation),
                tool_choice="auto",
            )
            provider_request_count += 1
            continue

        output_text = _required_response_str(response, "output_text")
        forecast = _validated_forecast(output_text, required_unit_ids)
        return _successful_result(
            request=request,
            workspace=workspace,
            forecast=forecast,
            requested_model=requested_model,
            served_model=served_model,
            provider_request_count=provider_request_count,
            tool_call_count=tool_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _provider_request(client: OpenAIClient, **kwargs: Any) -> object:
    try:
        return client.responses.create(**kwargs)
    except OpenAIResponsesAdapterError:
        raise
    except Exception as exc:
        raise OpenAIResponsesAdapterError("OpenAI Responses request failed") from exc


def _successful_result(
    *,
    request: RunRequest,
    workspace: Path,
    forecast: Mapping[str, Any],
    requested_model: str,
    served_model: str,
    provider_request_count: int,
    tool_call_count: int,
    input_tokens: int,
    output_tokens: int,
) -> RunResult:
    private_logs = workspace / "private-logs"
    private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_logs.chmod(0o700)
    forecast_path = private_logs / "openai-forecast.json"
    encoded_forecast = (
        json.dumps(forecast, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    forecast_path.write_bytes(encoded_forecast)
    forecast_path.chmod(0o600)
    forecast_sha256 = f"sha256:{hashlib.sha256(encoded_forecast).hexdigest()}"
    summary: dict[str, Any] = {
        "adapter_id": OPENAI_RESPONSES_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": OPENAI_RESPONSES_ADAPTER_VERSION,
        "auth_mode": "api-key-by-user-environment",
        "forecast_sha256": forecast_sha256,
        "input_tokens": input_tokens,
        "model_key": request.model_key,
        "output_tokens": output_tokens,
        "provider": "openai",
        "provider_request_count": provider_request_count,
        "python_version": sys.version.split()[0],
        "requested_model": requested_model,
        "sdk_name": "openai",
        "sdk_version": OPENAI_SDK_VERSION,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "served_model": served_model,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": tool_call_count,
        "total_tokens": input_tokens + output_tokens,
    }
    validate_public_record(summary, "openai_responses.public_summary")
    commitment = {
        "forecast": dict(forecast),
        "public_summary": summary,
        "request_sha256": request.request_sha256,
    }
    return RunResult(
        result_id=f"{request.request_id}:openai-responses",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_record_sha256(commitment),
        artifacts=(
            ArtifactRecord(
                artifact_id="openai-forecast-private",
                path="private-logs/openai-forecast.json",
                sha256=forecast_sha256,
                media_type="application/json",
                public=False,
                size_bytes=len(encoded_forecast),
            ),
        ),
        public_summary=summary,
    )


def validate_provider_grant(request: RunRequest) -> None:
    """Fail unless the live request grants only the pinned provider key."""

    if request.sandbox_policy.allowed_provider_env_vars != (OPENAI_PROVIDER_ENV_VAR,):
        raise OpenAIResponsesAdapterError(
            "provider environment grant must contain exactly OPENAI_API_KEY"
        )


def _validate_request(request: RunRequest) -> None:
    if request.adapter.adapter_id != OPENAI_RESPONSES_ADAPTER_ID:
        raise OpenAIResponsesAdapterError("request adapter id does not match")
    if request.adapter.adapter_version != OPENAI_RESPONSES_ADAPTER_VERSION:
        raise OpenAIResponsesAdapterError("request adapter version does not match")
    if request.task.family != "legalforecast_mtd":
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses baseline supports only legalforecast_mtd"
        )
    if request.task.scoring_mode != "lfb_brier":
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses baseline supports only lfb_brier"
        )


def _requested_model(model_key: str) -> str:
    prefix = "openai:"
    if not model_key.startswith(prefix) or len(model_key) == len(prefix):
        raise OpenAIResponsesAdapterError(
            "model_key must use the openai:<model> namespace"
        )
    return model_key[len(prefix) :]


def _required_unit_ids(request: RunRequest) -> tuple[str, ...]:
    value = request.task.metadata.get("required_unit_ids")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise OpenAIResponsesAdapterError(
            "task metadata required_unit_ids must be an array"
        )
    unit_ids: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise OpenAIResponsesAdapterError(
                "task metadata required_unit_ids must contain non-empty strings"
            )
        unit_ids.append(item)
    if not unit_ids or len(unit_ids) != len(set(unit_ids)):
        raise OpenAIResponsesAdapterError(
            "task metadata required_unit_ids must be non-empty and unique"
        )
    return tuple(unit_ids)


def _instructions(required_unit_ids: Sequence[str]) -> str:
    encoded_ids = json.dumps(list(required_unit_ids), separators=(",", ":"))
    return (
        "You are producing a LegalForecastBench community baseline forecast. "
        "Use only the public canonical task record available through "
        f"{_READ_TASK_TOOL_NAME}. Return only JSON with one predictions array. "
        "Each prediction must contain unit_id and probability_fully_dismissed. "
        f"The exact required unit IDs are {encoded_ids}; probabilities must be "
        "finite numbers from 0 through 1. Do not include analysis or prose."
    )


def _initial_input(
    request: RunRequest,
    required_unit_ids: Sequence[str],
) -> list[dict[str, Any]]:
    public_identity = {
        "request_id": request.request_id,
        "task_id": request.task.task_id,
        "task_sha256": request.task.task_sha256,
        "required_unit_ids": list(required_unit_ids),
    }
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": json.dumps(
                        public_identity,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            ],
        }
    ]


def _response_output_items(response: object) -> tuple[object, ...]:
    output = getattr(response, "output", None)
    if not isinstance(output, Sequence) or isinstance(output, str | bytes):
        raise OpenAIResponsesAdapterError("OpenAI Responses output must be a sequence")
    return tuple(cast(Sequence[object], output))


def _function_calls(output: Sequence[object]) -> tuple[object, ...]:
    return tuple(
        item for item in output if getattr(item, "type", None) == "function_call"
    )


def _validate_empty_arguments(arguments: str) -> None:
    try:
        decoded = cast(object, json.loads(arguments))
    except json.JSONDecodeError as exc:
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses tool arguments must be valid JSON"
        ) from exc
    if decoded != {}:
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses tool arguments must be empty"
        )


def _validated_forecast(
    output_text: str,
    required_unit_ids: Sequence[str],
) -> dict[str, Any]:
    try:
        decoded = cast(object, json.loads(output_text))
    except json.JSONDecodeError as exc:
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses forecast must be valid JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses forecast must be a JSON object"
        )
    record = cast(dict[str, Any], decoded)
    if set(record) != {"predictions"}:
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses forecast has unexpected fields"
        )
    predictions = record["predictions"]
    if not isinstance(predictions, list):
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses forecast predictions must be an array"
        )
    observed: list[str] = []
    for value in cast(list[object], predictions):
        if not isinstance(value, dict):
            raise OpenAIResponsesAdapterError(
                "OpenAI Responses forecast prediction must be an object"
            )
        prediction = cast(dict[str, object], value)
        if set(prediction) != {"unit_id", "probability_fully_dismissed"}:
            raise OpenAIResponsesAdapterError(
                "OpenAI Responses forecast prediction has unexpected fields"
            )
        unit_id = prediction["unit_id"]
        probability = prediction["probability_fully_dismissed"]
        if not isinstance(unit_id, str) or not unit_id:
            raise OpenAIResponsesAdapterError(
                "OpenAI Responses forecast unit_id is invalid"
            )
        if (
            not isinstance(probability, int | float)
            or isinstance(probability, bool)
            or not math.isfinite(float(probability))
            or not 0 <= float(probability) <= 1
        ):
            raise OpenAIResponsesAdapterError(
                "OpenAI Responses forecast probability is invalid"
            )
        observed.append(unit_id)
    if len(observed) != len(set(observed)) or set(observed) != set(required_unit_ids):
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses forecast unit IDs do not match the task"
        )
    return record


def _response_usage(response: object) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return (
        _non_negative_int(getattr(usage, "input_tokens", 0), "input_tokens"),
        _non_negative_int(getattr(usage, "output_tokens", 0), "output_tokens"),
    )


def _required_response_str(response: object, field_name: str) -> str:
    value = getattr(response, field_name, None)
    if not isinstance(value, str) or not value.strip():
        raise OpenAIResponsesAdapterError(f"OpenAI Responses {field_name} is missing")
    return value


def _require_completed_response(response: object) -> None:
    if getattr(response, "status", None) != "completed":
        raise OpenAIResponsesAdapterError(
            "OpenAI Responses request did not complete successfully"
        )


def _required_item_str(item: object, field_name: str) -> str:
    value = getattr(item, field_name, None)
    if not isinstance(value, str) or not value.strip():
        raise OpenAIResponsesAdapterError(
            f"OpenAI Responses function call {field_name} is missing"
        )
    return value


def _non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OpenAIResponsesAdapterError(
            f"OpenAI Responses usage {field_name} is invalid"
        )
    return value


def adapter_bundle_sha256() -> str:
    """Commit to the executable adapter, manifest, and locked dependency state."""

    project_root = Path(__file__).resolve().parents[2]
    relative_paths = (
        "legalforecast/multiharness/openai_responses.py",
        "legalforecast/multiharness/openai_responses_cli.py",
        "examples/adapters/openai-responses/adapter-manifest.json",
        "pyproject.toml",
        "uv.lock",
    )
    digest = hashlib.sha256()
    for relative_path in relative_paths:
        name = relative_path.encode("utf-8")
        payload = (project_root / relative_path).read_bytes()
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

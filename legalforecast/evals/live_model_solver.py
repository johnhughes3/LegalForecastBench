"""Provider-backed harness solver for live model evaluation runs."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from legalforecast.evals.inspect_task import (
    HarnessRequest,
    RunExecutionBackend,
    SolverKind,
    SolverResponse,
)
from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

DEFAULT_TIMEOUT_SECONDS = 120.0
_PRICE_UNITS_PER_TOKEN = 1_000_000

JsonRecord = Mapping[str, object]
BuildRequest = Callable[[ModelRegistryEntry, str, str], urllib.request.Request]
ExtractOutput = Callable[[JsonRecord], str]
ExtractUsage = Callable[[JsonRecord], tuple[int, int]]


class LiveModelSolverError(RuntimeError):
    """Base class for live provider solver failures."""


class LiveModelConfigError(LiveModelSolverError):
    """Raised when a registry entry or environment cannot support a live run."""


class LiveModelProviderError(LiveModelSolverError):
    """Raised when a provider request fails."""


class LiveModelResponseError(LiveModelSolverError):
    """Raised when a provider response is malformed or incomplete."""


class LiveModelTransport(Protocol):
    """Callable transport used to make tests network-free."""

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> JsonRecord: ...


@dataclass(frozen=True, slots=True)
class LiveModelSolver:
    """HarnessSolver-compatible solver that calls supported provider APIs."""

    registry_entry: ModelRegistryEntry
    model_registry_sha256: str | None = None
    transport: LiveModelTransport | None = None
    environ: Mapping[str, str] | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.registry_entry.network_disabled:
            raise LiveModelConfigError(
                "live provider harness requires network_disabled=True"
            )
        if not self.registry_entry.search_disabled:
            raise LiveModelConfigError(
                "live provider harness requires search_disabled=True"
            )
        if self.timeout_seconds <= 0:
            raise LiveModelConfigError("timeout_seconds must be positive")
        _provider_config(self.registry_entry.provider)

    @property
    def solver_id(self) -> str:
        return self.registry_entry.registry_key

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.INSPECT_AI

    def solve(self, request: HarnessRequest) -> SolverResponse:
        provider = _provider_config(self.registry_entry.provider)
        api_key = _api_key(provider.api_key_env, self.environ)
        prompt = _prompt_with_controlled_docket_context(
            request,
            tool_policy=self.registry_entry.tool_policy,
        )
        provider_request = provider.build_request(
            self.registry_entry,
            prompt,
            api_key,
        )
        started = time.perf_counter()
        payload = self._transport(provider_request, self.timeout_seconds)
        latency_ms = (time.perf_counter() - started) * 1000
        raw_output = provider.extract_output(payload)
        input_tokens, output_tokens = provider.extract_usage(payload)
        return SolverResponse(
            raw_output=raw_output,
            request_count=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=_estimated_cost(
                self.registry_entry,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            metadata={
                "provider": self.registry_entry.provider,
                "model": self.registry_entry.model_id,
                "model_id": self.registry_entry.model_id,
                "model_version_or_snapshot": (
                    self.registry_entry.model_version_or_snapshot
                ),
                "execution_backend": RunExecutionBackend.INSPECT_AI.value,
                "latency_ms": f"{latency_ms:.3f}",
                "model_registry_sha256": self.model_registry_sha256 or "unrecorded",
                "tool_policy": self.registry_entry.tool_policy.value,
            },
        )

    def _transport(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> JsonRecord:
        transport = self.transport or _urlopen_json
        return transport(request, timeout_seconds)


@dataclass(frozen=True, slots=True)
class _ProviderConfig:
    api_key_env: str
    build_request: BuildRequest
    extract_output: ExtractOutput
    extract_usage: ExtractUsage


def _provider_config(provider: str) -> _ProviderConfig:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return _ProviderConfig(
            api_key_env=OPENAI_API_KEY_ENV,
            build_request=_openai_request,
            extract_output=_openai_output,
            extract_usage=_openai_usage,
        )
    if normalized == "anthropic":
        return _ProviderConfig(
            api_key_env=ANTHROPIC_API_KEY_ENV,
            build_request=_anthropic_request,
            extract_output=_anthropic_output,
            extract_usage=_anthropic_usage,
        )
    if normalized in {"google", "gemini"}:
        return _ProviderConfig(
            api_key_env=GEMINI_API_KEY_ENV,
            build_request=_gemini_request,
            extract_output=_gemini_output,
            extract_usage=_gemini_usage,
        )
    raise LiveModelConfigError(f"unsupported provider: {provider}")


def _prompt_with_controlled_docket_context(
    request: HarnessRequest,
    *,
    tool_policy: ToolPolicy,
) -> str:
    if tool_policy is not ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY:
        return request.sample.prompt

    listed = request.docket_tool.list_available_docket_entries()
    transcript: JsonRecord
    if not listed.ok:
        transcript = {
            "tool": "controlled_docket_tool",
            "list_available_docket_entries": listed.to_record(),
            "read_docket_entry_results": [],
        }
    else:
        read_results: list[object] = []
        for entry in listed.available_entries:
            result = request.docket_tool.read_docket_entry(entry.entry_number)
            read_results.append(result.to_record())
            if request.docket_tool.remaining_calls <= 0:
                break
        transcript = {
            "tool": "controlled_docket_tool",
            "list_available_docket_entries": listed.to_record(),
            "read_docket_entry_results": read_results,
        }
    return "Controlled docket tool transcript:\n" + json.dumps(
        {
            "base_prompt": _base_prompt_payload(request.sample.prompt),
            "controlled_docket_tool_transcript": transcript,
        },
        sort_keys=True,
        indent=2,
    )


def _base_prompt_payload(prompt: str) -> object:
    try:
        return json.loads(prompt)
    except json.JSONDecodeError:
        return prompt


def _openai_request(
    entry: ModelRegistryEntry,
    prompt: str,
    api_key: str,
) -> urllib.request.Request:
    payload: dict[str, object] = {
        "model": entry.model_id,
        "input": prompt,
        "temperature": entry.temperature,
        "top_p": entry.top_p,
        "max_output_tokens": entry.max_output_tokens,
        "tools": [],
    }
    return _json_request(
        OPENAI_RESPONSES_URL,
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )


def _anthropic_request(
    entry: ModelRegistryEntry,
    prompt: str,
    api_key: str,
) -> urllib.request.Request:
    payload: dict[str, object] = {
        "model": entry.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": entry.max_output_tokens,
        "temperature": entry.temperature,
        "top_p": entry.top_p,
        "tools": [],
    }
    return _json_request(
        ANTHROPIC_MESSAGES_URL,
        payload,
        headers={
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
    )


def _gemini_request(
    entry: ModelRegistryEntry,
    prompt: str,
    api_key: str,
) -> urllib.request.Request:
    model = urllib.parse.quote(entry.model_id, safe="")
    payload: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": entry.temperature,
            "topP": entry.top_p,
            "maxOutputTokens": entry.max_output_tokens,
        },
        "tools": [],
    }
    return _json_request(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model=model),
        payload,
        headers={"x-goog-api-key": api_key},
    )


def _json_request(
    url: str,
    payload: JsonRecord,
    *,
    headers: Mapping[str, str],
) -> urllib.request.Request:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **headers,
    }
    return urllib.request.Request(
        url,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )


def _urlopen_json(
    request: urllib.request.Request,
    timeout_seconds: float,
) -> JsonRecord:
    try:
        with urllib.request.urlopen(  # nosec B310
            request,
            timeout=timeout_seconds,
        ) as response:
            return _json_payload(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LiveModelProviderError(
            f"provider returned HTTP {exc.code}: {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise LiveModelProviderError(f"provider request failed: {exc.reason}") from exc


def _json_payload(raw: bytes) -> JsonRecord:
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise LiveModelResponseError("provider response was not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise LiveModelResponseError("provider response must be a JSON object")
    return cast(JsonRecord, payload)


def _openai_output(payload: JsonRecord) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    choices = _object_list(payload.get("choices"))
    if choices:
        first = _mapping(choices[0])
        if first is not None:
            message = _mapping(first.get("message"))
            if message is not None:
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content

    output = _object_list(payload.get("output"))
    if output:
        text_parts: list[str] = []
        for item in output:
            item_record = _mapping(item)
            if item_record is None:
                continue
            content = _object_list(item_record.get("content"))
            if not content:
                continue
            text_parts.extend(_text_parts(content))
        if text_parts:
            return "".join(text_parts)

    raise LiveModelResponseError("OpenAI response did not include output text")


def _anthropic_output(payload: JsonRecord) -> str:
    content = _object_list(payload.get("content"))
    if content:
        text_parts = _text_parts(content)
        if text_parts:
            return "".join(text_parts)
    raise LiveModelResponseError("Anthropic response did not include text content")


def _gemini_output(payload: JsonRecord) -> str:
    candidates = _object_list(payload.get("candidates"))
    if candidates:
        first = _mapping(candidates[0])
        if first is not None:
            content = _mapping(first.get("content"))
            if content is not None:
                parts = _object_list(content.get("parts"))
                if parts:
                    text_parts = _text_parts(parts)
                    if text_parts:
                        return "".join(text_parts)
    raise LiveModelResponseError("Gemini response did not include candidate text")


def _text_parts(parts: list[object]) -> list[str]:
    text_parts: list[str] = []
    for part in parts:
        part_record = _mapping(part)
        if part_record is None:
            continue
        text = part_record.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)
    return text_parts


def _openai_usage(payload: JsonRecord) -> tuple[int, int]:
    usage = _mapping_or_empty(payload.get("usage"))
    return (
        _int_field(usage, "input_tokens", "prompt_tokens"),
        _int_field(usage, "output_tokens", "completion_tokens"),
    )


def _anthropic_usage(payload: JsonRecord) -> tuple[int, int]:
    usage = _mapping_or_empty(payload.get("usage"))
    return (
        _int_field(usage, "input_tokens"),
        _int_field(usage, "output_tokens"),
    )


def _gemini_usage(payload: JsonRecord) -> tuple[int, int]:
    usage = _mapping_or_empty(payload.get("usageMetadata"))
    return (
        _int_field(usage, "promptTokenCount"),
        _int_field(usage, "candidatesTokenCount"),
    )


def _mapping(value: object) -> JsonRecord | None:
    if isinstance(value, Mapping):
        return cast(JsonRecord, value)
    return None


def _mapping_or_empty(value: object) -> JsonRecord:
    record = _mapping(value)
    if record is not None:
        return record
    return {}


def _object_list(value: object) -> list[object]:
    if isinstance(value, list):
        return cast(list[object], value)
    return []


def _int_field(record: JsonRecord, *field_names: str) -> int:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return 0


def _estimated_cost(
    entry: ModelRegistryEntry,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    return (
        (input_tokens * entry.input_token_price)
        + (output_tokens * entry.output_token_price)
    ) / _PRICE_UNITS_PER_TOKEN


def _api_key(env_name: str, environ: Mapping[str, str] | None) -> str:
    values = os.environ if environ is None else environ
    value = values.get(env_name)
    if value is None or not value.strip():
        raise LiveModelConfigError(f"{env_name} is required")
    return value.strip()

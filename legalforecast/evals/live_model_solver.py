"""Provider-backed harness solver for live model evaluation runs."""

from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol, cast

from legalforecast.evals.inspect_task import (
    HarnessRequest,
    RunExecutionBackend,
    SolverKind,
    SolverResponse,
)
from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
from legalforecast.evals.response_verification import verify_provider_response

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
ANTHROPIC_RUNTIME_ENV = "LFB_ANTHROPIC_RUNTIME"
ANTHROPIC_BEDROCK_MODEL_ID_ENV = "LFB_ANTHROPIC_BEDROCK_MODEL_ID"

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
_PRICE_UNITS_PER_TOKEN = 1_000_000
_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4

JsonRecord = Mapping[str, object]
BuildRequest = Callable[[ModelRegistryEntry, str, str], urllib.request.Request]
ExtractOutput = Callable[[JsonRecord], str]
ExtractUsage = Callable[[JsonRecord], tuple[int, int]]
ExtractServedVersion = Callable[[JsonRecord], str]


class LiveModelSolverError(RuntimeError):
    """Base class for live provider solver failures."""


class LiveModelConfigError(LiveModelSolverError):
    """Raised when a registry entry or environment cannot support a live run."""


class LiveModelProviderError(LiveModelSolverError):
    """Raised when a provider request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS

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
        if self.max_attempts <= 0:
            raise LiveModelConfigError("max_attempts must be positive")
        if self.retry_backoff_seconds < 0:
            raise LiveModelConfigError("retry_backoff_seconds cannot be negative")
        _provider_config(self.registry_entry.provider)

    @property
    def solver_id(self) -> str:
        return self.registry_entry.registry_key

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.INSPECT_AI

    def solve(self, request: HarnessRequest) -> SolverResponse:
        prompt = _prompt_with_controlled_docket_context(
            request,
            tool_policy=self.registry_entry.tool_policy,
        )
        return complete_live_prompt(
            self.registry_entry,
            prompt,
            model_registry_sha256=self.model_registry_sha256,
            transport=self.transport,
            environ=self.environ,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )

    def _transport(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> JsonRecord:
        transport = self.transport or _urlopen_json
        return transport(request, timeout_seconds)


def complete_live_prompt(
    registry_entry: ModelRegistryEntry,
    prompt: str,
    *,
    model_registry_sha256: str | None = None,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> SolverResponse:
    """Call a registry-backed provider with a raw prompt and return accounting."""

    if not prompt.strip():
        raise LiveModelConfigError("prompt is required")
    if timeout_seconds <= 0:
        raise LiveModelConfigError("timeout_seconds must be positive")
    if max_attempts <= 0:
        raise LiveModelConfigError("max_attempts must be positive")
    if retry_backoff_seconds < 0:
        raise LiveModelConfigError("retry_backoff_seconds cannot be negative")
    if not registry_entry.network_disabled:
        raise LiveModelConfigError(
            "live provider harness requires network_disabled=True"
        )
    if not registry_entry.search_disabled:
        raise LiveModelConfigError(
            "live provider harness requires search_disabled=True"
        )
    estimated_prompt_tokens, prompt_input_token_budget = _validate_prompt_token_budget(
        registry_entry,
        prompt,
    )

    provider = _provider_config(registry_entry.provider)
    if _uses_bedrock_anthropic_runtime(registry_entry.provider, environ):
        return _complete_bedrock_anthropic_prompt(
            registry_entry,
            prompt,
            model_registry_sha256=model_registry_sha256,
            environ=environ,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    api_key = _api_key(provider.api_key_env, environ)
    provider_request = provider.build_request(registry_entry, prompt, api_key)
    started = time.perf_counter()
    payload, request_count = _call_with_provider_retries(
        lambda: (transport or _urlopen_json)(provider_request, timeout_seconds),
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    raw_output = provider.extract_output(payload)
    input_tokens, output_tokens = provider.extract_usage(payload)
    served_model_version = provider.extract_served_version(payload)
    _validate_served_model_version(registry_entry, served_model_version)
    response_verification = verify_provider_response(
        payload,
        provider=registry_entry.provider,
    )
    return SolverResponse(
        raw_output=raw_output,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=_estimated_cost(
            registry_entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        metadata={
            "provider": registry_entry.provider,
            "model": registry_entry.model_id,
            "model_id": registry_entry.model_id,
            "model_version_or_snapshot": registry_entry.model_version_or_snapshot,
            "served_model_version": served_model_version,
            "estimated_prompt_input_tokens": str(estimated_prompt_tokens),
            "prompt_input_token_budget": str(prompt_input_token_budget),
            "context_limit": str(registry_entry.context_limit),
            "max_output_tokens": str(registry_entry.max_output_tokens),
            **_sampling_policy_metadata(registry_entry),
            "execution_backend": RunExecutionBackend.INSPECT_AI.value,
            "latency_ms": f"{latency_ms:.3f}",
            "provider_attempt_count": str(request_count),
            "model_registry_sha256": model_registry_sha256 or "unrecorded",
            "tool_policy": registry_entry.tool_policy.value,
            **response_verification.to_metadata(),
        },
    )


def _complete_bedrock_anthropic_prompt(
    registry_entry: ModelRegistryEntry,
    prompt: str,
    *,
    model_registry_sha256: str | None,
    environ: Mapping[str, str] | None,
    timeout_seconds: float,
    max_attempts: int,
    retry_backoff_seconds: float,
) -> SolverResponse:
    bedrock_model_id = _bedrock_anthropic_model_id(registry_entry, environ)
    request_payload = _bedrock_anthropic_payload(registry_entry, prompt)
    started = time.perf_counter()
    payload, request_count = _call_with_provider_retries(
        lambda: _invoke_bedrock_runtime_json(
            bedrock_model_id,
            request_payload,
            environ=environ,
            timeout_seconds=timeout_seconds,
        ),
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    raw_output = _anthropic_output(payload)
    input_tokens, output_tokens = _anthropic_usage(payload)
    served_model_version = _optional_str_field(payload, "model") or bedrock_model_id
    _validate_served_model_version(registry_entry, served_model_version)
    response_verification = verify_provider_response(
        payload,
        provider=registry_entry.provider,
    )
    return SolverResponse(
        raw_output=raw_output,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=_estimated_cost(
            registry_entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        metadata={
            "provider": registry_entry.provider,
            "provider_runtime": "bedrock",
            "bedrock_model_id": bedrock_model_id,
            "model": registry_entry.model_id,
            "model_id": registry_entry.model_id,
            "model_version_or_snapshot": registry_entry.model_version_or_snapshot,
            "served_model_version": served_model_version,
            "estimated_prompt_input_tokens": str(estimated_prompt_tokens(prompt)),
            "prompt_input_token_budget": str(
                _prompt_input_token_budget(registry_entry)
            ),
            "context_limit": str(registry_entry.context_limit),
            "max_output_tokens": str(registry_entry.max_output_tokens),
            **_sampling_policy_metadata(registry_entry),
            "execution_backend": RunExecutionBackend.INSPECT_AI.value,
            "latency_ms": f"{latency_ms:.3f}",
            "provider_attempt_count": str(request_count),
            "model_registry_sha256": model_registry_sha256 or "unrecorded",
            "tool_policy": registry_entry.tool_policy.value,
            **response_verification.to_metadata(),
        },
    )


@dataclass(frozen=True, slots=True)
class _ProviderConfig:
    api_key_env: str
    build_request: BuildRequest
    extract_output: ExtractOutput
    extract_usage: ExtractUsage
    extract_served_version: ExtractServedVersion


def _provider_config(provider: str) -> _ProviderConfig:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return _ProviderConfig(
            api_key_env=OPENAI_API_KEY_ENV,
            build_request=_openai_request,
            extract_output=_openai_output,
            extract_usage=_openai_usage,
            extract_served_version=_openai_served_model_version,
        )
    if normalized == "anthropic":
        return _ProviderConfig(
            api_key_env=ANTHROPIC_API_KEY_ENV,
            build_request=_anthropic_request,
            extract_output=_anthropic_output,
            extract_usage=_anthropic_usage,
            extract_served_version=_anthropic_served_model_version,
        )
    if normalized in {"google", "gemini"}:
        return _ProviderConfig(
            api_key_env=GEMINI_API_KEY_ENV,
            build_request=_gemini_request,
            extract_output=_gemini_output,
            extract_usage=_gemini_usage,
            extract_served_version=_gemini_served_model_version,
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
        "tools": [],
    }
    if not _anthropic_requires_provider_default_sampling(entry):
        payload["temperature"] = entry.temperature
    return _json_request(
        ANTHROPIC_MESSAGES_URL,
        payload,
        headers={
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
    )


def _bedrock_anthropic_payload(
    entry: ModelRegistryEntry,
    prompt: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
        "max_tokens": entry.max_output_tokens,
    }
    if not _anthropic_requires_provider_default_sampling(entry):
        payload["temperature"] = entry.temperature
        if entry.top_p < 1.0:
            payload["top_p"] = entry.top_p
    return payload


def _anthropic_requires_provider_default_sampling(
    entry: ModelRegistryEntry,
) -> bool:
    """Return whether Anthropic requires omitted sampling controls for this model."""

    return entry.provider.strip().lower() == "anthropic" and "claude-sonnet-5" in {
        _canonical_model_version(entry.model_id),
        _canonical_model_version(entry.model_version_or_snapshot),
    }


def _sampling_policy_metadata(entry: ModelRegistryEntry) -> dict[str, str]:
    """Separate registry intent from sampling controls applied by the provider."""

    if not _anthropic_requires_provider_default_sampling(entry):
        return {"temperature": _format_number(entry.temperature)}
    return {
        "registry_temperature": _format_number(entry.temperature),
        "registry_top_p": _format_number(entry.top_p),
        "provider_sampling_policy": "provider_default",
    }


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
            "responseMimeType": "application/json",
        },
        "tools": [],
    }
    return _json_request(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model=model),
        payload,
        headers={"x-goog-api-key": api_key},
    )


def _uses_bedrock_anthropic_runtime(
    provider: str,
    environ: Mapping[str, str] | None,
) -> bool:
    if provider.strip().lower() != "anthropic":
        return False
    values = os.environ if environ is None else environ
    runtime = values.get(ANTHROPIC_RUNTIME_ENV) or values.get("ANTHROPIC_RUNTIME")
    if runtime is None:
        return False
    return runtime.strip().lower() in {"bedrock", "aws-bedrock", "aws_bedrock"}


def _bedrock_anthropic_model_id(
    entry: ModelRegistryEntry,
    environ: Mapping[str, str] | None,
) -> str:
    values = os.environ if environ is None else environ
    explicit = values.get(ANTHROPIC_BEDROCK_MODEL_ID_ENV) or values.get(
        "ANTHROPIC_BEDROCK_MODEL_ID"
    )
    if explicit is not None and explicit.strip():
        explicit_model_id = explicit.strip()
        _validate_bedrock_model_id_override(entry, explicit_model_id)
        return explicit_model_id
    if entry.model_id.startswith(("anthropic.", "us.anthropic.", "arn:aws:bedrock:")):
        return entry.model_id
    return f"us.anthropic.{entry.model_id}"


def _invoke_bedrock_runtime_json(
    model_id: str,
    payload: JsonRecord,
    *,
    environ: Mapping[str, str] | None,
    timeout_seconds: float,
) -> JsonRecord:
    if not model_id.strip():
        raise LiveModelConfigError("Bedrock model id is required")
    process_env = dict(os.environ if environ is None else environ)
    with TemporaryDirectory(prefix="lfb-bedrock-") as tmpdir:
        request_path = Path(tmpdir) / "request.json"
        response_path = Path(tmpdir) / "response.json"
        request_path.write_text(json.dumps(dict(payload)), encoding="utf-8")
        command = [
            "aws",
            "bedrock-runtime",
            "invoke-model",
            "--model-id",
            model_id,
            "--content-type",
            "application/json",
            "--accept",
            "application/json",
            "--body",
            f"fileb://{request_path}",
            "--cli-binary-format",
            "raw-in-base64-out",
            str(response_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                env=process_env,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise LiveModelConfigError(
                "aws CLI is required for Bedrock runtime"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise LiveModelProviderError(
                "Bedrock request timed out",
                retryable=True,
            ) from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise LiveModelProviderError(
                f"Bedrock request failed: {detail}",
                retryable=_retryable_provider_message(detail),
            )
        if not response_path.exists():
            raise LiveModelResponseError("Bedrock response file was not written")
        return _json_payload(response_path.read_bytes())


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
            f"provider returned HTTP {exc.code}: {body}",
            status_code=exc.code,
            retryable=_retryable_http_error(exc.code, body),
        ) from exc
    except urllib.error.URLError as exc:
        raise LiveModelProviderError(
            f"provider request failed: {exc.reason}",
            retryable=_retryable_url_error(exc.reason),
        ) from exc
    except OSError as exc:
        raise LiveModelProviderError(
            f"provider request failed: {exc}",
            retryable=_retryable_url_error(exc),
        ) from exc


def _call_with_provider_retries(
    call: Callable[[], JsonRecord],
    *,
    max_attempts: int,
    retry_backoff_seconds: float,
) -> tuple[JsonRecord, int]:
    """Retry provider transport failures that are plausibly temporary."""

    for attempt in range(1, max_attempts + 1):
        try:
            return call(), attempt
        except LiveModelProviderError as exc:
            if attempt >= max_attempts or not _is_retryable_provider_error(exc):
                raise
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds * (2 ** (attempt - 1)))
    raise LiveModelProviderError("provider request retry loop exhausted")


def _is_retryable_provider_error(exc: LiveModelProviderError) -> bool:
    if exc.retryable is not None:
        return exc.retryable
    if exc.status_code is not None:
        return _retryable_http_error(exc.status_code, str(exc))
    return _retryable_provider_message(str(exc))


def _retryable_http_error(status_code: int, body: str) -> bool:
    if _nonretryable_provider_message(body):
        return False
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def _retryable_url_error(reason: object) -> bool:
    if isinstance(reason, TimeoutError | socket.timeout):
        return True
    return _retryable_provider_message(str(reason))


def _retryable_provider_message(message: str) -> bool:
    if _nonretryable_provider_message(message):
        return False
    normalized = message.lower()
    retry_markers = (
        "rate limit",
        "rate_limit",
        "too many requests",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "try again",
        "connection reset",
        "connection aborted",
        "connection refused",
        "remote end closed connection",
        "dns",
        "name resolution",
        "name or service not known",
        "nodename nor servname provided",
        "temporary failure",
        "throttl",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
        "429",
        "500",
        "502",
        "503",
        "504",
    )
    return any(marker in normalized for marker in retry_markers)


def _nonretryable_provider_message(message: str) -> bool:
    normalized = message.lower()
    nonretry_markers = (
        "insufficient_quota",
        "insufficient quota",
        "insufficient credits",
        "exceeded your current quota",
        "quota exceeded",
        "check your plan",
        "credit balance",
        "prepaid credits",
        "billing hard limit",
        "billing details",
        "payment required",
        "invalid api key",
        "incorrect api key",
        "unauthorized",
        "permission denied",
        "forbidden",
        "model_not_found",
        "model not found",
        "context_length_exceeded",
        "maximum context length",
        "invalid_request_error",
        "bad request",
    )
    return any(marker in normalized for marker in nonretry_markers)


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


def _openai_served_model_version(payload: JsonRecord) -> str:
    return _required_str_field(payload, "model", provider_name="OpenAI")


def _anthropic_served_model_version(payload: JsonRecord) -> str:
    return _required_str_field(payload, "model", provider_name="Anthropic")


def _gemini_served_model_version(payload: JsonRecord) -> str:
    return _required_str_field(payload, "modelVersion", provider_name="Gemini")


def _validate_served_model_version(
    entry: ModelRegistryEntry,
    served_model_version: str,
    *,
    source: str = "provider served model version",
) -> None:
    if not _same_model_version(served_model_version, entry.model_version_or_snapshot):
        raise LiveModelResponseError(
            f"{source} {served_model_version!r} did not match frozen registry "
            f"version {entry.model_version_or_snapshot!r} for {entry.registry_key}"
        )


def _validate_bedrock_model_id_override(
    entry: ModelRegistryEntry,
    model_id: str,
) -> None:
    if not _same_model_version(model_id, entry.model_version_or_snapshot):
        raise LiveModelConfigError(
            f"Bedrock model-ID override {model_id!r} did not match frozen "
            f"registry version {entry.model_version_or_snapshot!r} for "
            f"{entry.registry_key}"
        )


def _same_model_version(left: str, right: str) -> bool:
    return _canonical_model_version(left) == _canonical_model_version(right)


def _canonical_model_version(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("arn:aws:bedrock:") and "/" in normalized:
        normalized = normalized.rsplit("/", maxsplit=1)[1]
    if normalized.startswith("foundation-model/"):
        normalized = normalized.removeprefix("foundation-model/")
    if normalized.startswith("models/"):
        normalized = normalized.removeprefix("models/")
    if normalized.startswith("us.anthropic."):
        normalized = normalized.removeprefix("us.anthropic.")
    if normalized.startswith("anthropic."):
        normalized = normalized.removeprefix("anthropic.")
    return normalized.lower()


def _validate_prompt_token_budget(
    entry: ModelRegistryEntry,
    prompt: str,
) -> tuple[int, int]:
    budget = _prompt_input_token_budget(entry)
    if budget <= 0:
        raise LiveModelConfigError(
            "registry context_limit must exceed max_output_tokens for "
            f"{entry.registry_key}"
        )
    estimated_tokens = estimated_prompt_tokens(prompt)
    if estimated_tokens > budget:
        raise LiveModelConfigError(
            "estimated prompt input tokens exceed registry prompt budget for "
            f"{entry.registry_key}: estimated={estimated_tokens}, budget={budget}, "
            f"context_limit={entry.context_limit}, "
            f"max_output_tokens={entry.max_output_tokens}"
        )
    return estimated_tokens, budget


def estimated_prompt_tokens(prompt: str) -> int:
    """Conservative tokenizer-free prompt-token estimate for budget gating."""

    return math.ceil(len(prompt.encode("utf-8")) / _TOKEN_ESTIMATE_BYTES_PER_TOKEN)


def _prompt_input_token_budget(entry: ModelRegistryEntry) -> int:
    return entry.context_limit - entry.max_output_tokens


def _format_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _required_str_field(
    record: JsonRecord,
    field_name: str,
    *,
    provider_name: str,
) -> str:
    value = _optional_str_field(record, field_name)
    if value is None:
        raise LiveModelResponseError(
            f"{provider_name} response did not include served model version "
            f"field {field_name}"
        )
    return value


def _optional_str_field(record: JsonRecord, field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LiveModelResponseError(f"{field_name} must be a non-empty string")
    return value.strip()


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

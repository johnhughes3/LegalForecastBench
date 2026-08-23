"""Provider-backed harness solver for live model evaluation runs."""

from __future__ import annotations

import hashlib
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
from dataclasses import dataclass, replace
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

# Official OpenAI eval uses Flex processing: Batch-rate tokens, slower replies.
# Retryable 429/503 on Flex fall back to standard (`default`) for remaining attempts.
OPENAI_SERVICE_TIER = "flex"
OPENAI_FALLBACK_SERVICE_TIER = "default"
OPENAI_FLEX_TIMEOUT_SECONDS = 900.0
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
_PRICE_UNITS_PER_TOKEN = 1_000_000
_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4

JsonRecord = Mapping[str, object]
BuildRequest = Callable[
    [ModelRegistryEntry, str, str, Mapping[str, object] | None],
    urllib.request.Request,
]
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


@dataclass(frozen=True, slots=True)
class ValidatedProviderResponseFields:
    """Provider response fields extracted under the live solver's exact rules."""

    raw_output: str
    input_tokens: int
    output_tokens: int
    served_model_version: str


class LiveModelTransport(Protocol):
    """Callable transport used to make tests network-free."""

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> JsonRecord: ...


class ProviderAttemptHandler(Protocol):
    """Durably wrap and settle individual provider HTTP attempts."""

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord: ...

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None: ...

    def durable_attempt_ordinal(self, local_ordinal: int) -> int: ...

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None: ...


ProviderAttemptHandlerFactory = Callable[[HarnessRequest], ProviderAttemptHandler]
OpenAIServiceTierObserver = Callable[[HarnessRequest, str], None]


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
    attempt_handler_factory: ProviderAttemptHandlerFactory | None = None
    openai_service_tier_observer: OpenAIServiceTierObserver | None = None

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
        expected_prompt_sha256 = request.sample.committed_prompt_sha256
        if expected_prompt_sha256 is not None:
            actual_prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            if actual_prompt_sha256 != expected_prompt_sha256:
                raise LiveModelConfigError(
                    "actual provider prompt does not match the manifest "
                    "prompt_sha256 commitment"
                )
        attempt_handler = (
            self.attempt_handler_factory(request)
            if self.attempt_handler_factory is not None
            else None
        )
        tier_observer = self.openai_service_tier_observer
        return complete_live_prompt(
            self.registry_entry,
            prompt,
            model_registry_sha256=self.model_registry_sha256,
            transport=self.transport,
            environ=self.environ,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
            attempt_handler=attempt_handler,
            openai_service_tier_observer=(
                None
                if tier_observer is None
                else lambda tier: tier_observer(request, tier)
            ),
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
    attempt_handler: ProviderAttemptHandler | None = None,
    response_json_schema: Mapping[str, object] | None = None,
    max_output_tokens_override: int | None = None,
    openai_service_tier_observer: Callable[[str], None] | None = None,
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
    if max_output_tokens_override is not None:
        if (
            type(max_output_tokens_override) is not int
            or max_output_tokens_override <= 0
        ):
            raise LiveModelConfigError(
                "max_output_tokens_override must be a positive integer"
            )
        if max_output_tokens_override > registry_entry.max_output_tokens:
            raise LiveModelConfigError(
                "max_output_tokens_override cannot exceed registry max_output_tokens"
            )
        registry_entry = replace(
            registry_entry,
            max_output_tokens=max_output_tokens_override,
        )
    timeout_seconds = _effective_timeout_seconds(registry_entry, timeout_seconds)
    estimated_prompt_tokens, prompt_input_token_budget = _validate_prompt_token_budget(
        registry_entry,
        prompt,
    )

    provider = _provider_config(registry_entry.provider)
    if response_json_schema is not None and not provider.supports_response_json_schema:
        raise LiveModelConfigError(
            "response_json_schema is only supported for Google Gemini"
        )
    if _uses_bedrock_anthropic_runtime(registry_entry.provider, environ):
        return _complete_bedrock_anthropic_prompt(
            registry_entry,
            prompt,
            model_registry_sha256=model_registry_sha256,
            environ=environ,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            attempt_handler=attempt_handler,
        )

    started = time.perf_counter()
    payload, request_count, durable_attempt_ordinal, used_tier, fell_back = (
        _call_live_http_provider(
            registry_entry,
            prompt,
            api_key_supplier=lambda: _api_key(provider.api_key_env, environ),
            response_json_schema=response_json_schema,
            transport=transport or _urlopen_json,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            attempt_handler=attempt_handler,
        )
    )
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        response_fields = validate_provider_response_fields(registry_entry, payload)
        raw_output = response_fields.raw_output
        input_tokens = response_fields.input_tokens
        output_tokens = response_fields.output_tokens
        served_model_version = response_fields.served_model_version
        response_verification = verify_provider_response(
            payload,
            provider=registry_entry.provider,
        )
        estimated_cost = _estimated_cost(
            registry_entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except BaseException as exc:
        _record_post_response_failure(
            attempt_handler,
            durable_attempt_ordinal,
            exc,
        )
        raise
    if attempt_handler is not None:
        attempt_handler.settle_attempt(
            durable_attempt_ordinal,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=estimated_cost,
            raw_output=raw_output,
        )
    if openai_service_tier_observer is not None and _is_openai_provider(registry_entry):
        openai_service_tier_observer(_observed_openai_service_tier(payload))
    return SolverResponse(
        raw_output=raw_output,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
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
            **_openai_service_tier_metadata(
                registry_entry,
                used_tier=used_tier,
                fell_back=fell_back,
            ),
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
    attempt_handler: ProviderAttemptHandler | None,
) -> SolverResponse:
    bedrock_model_id = _bedrock_anthropic_model_id(registry_entry, environ)
    _reject_unsupported_legacy_bedrock_model(
        registry_entry,
        bedrock_model_id,
        environ,
    )
    request_payload = _bedrock_anthropic_payload(registry_entry, prompt)
    started = time.perf_counter()
    payload, request_count, durable_attempt_ordinal = _call_with_provider_retries(
        lambda: _invoke_bedrock_runtime_json(
            bedrock_model_id,
            request_payload,
            environ=environ,
            timeout_seconds=timeout_seconds,
        ),
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
        attempt_handler=attempt_handler,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        raw_output = _anthropic_output(payload)
        input_tokens, output_tokens = _anthropic_usage(payload)
        served_model_version = _optional_str_field(payload, "model") or bedrock_model_id
        _validate_served_model_version(registry_entry, served_model_version)
        response_verification = verify_provider_response(
            payload,
            provider=registry_entry.provider,
        )
        estimated_cost = _estimated_cost(
            registry_entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except BaseException as exc:
        _record_post_response_failure(
            attempt_handler,
            durable_attempt_ordinal,
            exc,
        )
        raise
    if attempt_handler is not None:
        attempt_handler.settle_attempt(
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
    supports_response_json_schema: bool


def _provider_config(provider: str) -> _ProviderConfig:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return _ProviderConfig(
            api_key_env=OPENAI_API_KEY_ENV,
            build_request=_openai_request,
            extract_output=_openai_output,
            extract_usage=_openai_usage,
            extract_served_version=_openai_served_model_version,
            supports_response_json_schema=False,
        )
    if normalized == "anthropic":
        return _ProviderConfig(
            api_key_env=ANTHROPIC_API_KEY_ENV,
            build_request=_anthropic_request,
            extract_output=_anthropic_output,
            extract_usage=_anthropic_usage,
            extract_served_version=_anthropic_served_model_version,
            supports_response_json_schema=False,
        )
    if normalized in {"google", "gemini"}:
        return _ProviderConfig(
            api_key_env=GEMINI_API_KEY_ENV,
            build_request=_gemini_request,
            extract_output=_gemini_output,
            extract_usage=_gemini_usage,
            extract_served_version=_gemini_served_model_version,
            supports_response_json_schema=True,
        )
    raise LiveModelConfigError(f"unsupported provider: {provider}")


def validate_provider_response_fields(
    registry_entry: ModelRegistryEntry,
    payload: Mapping[str, object],
) -> ValidatedProviderResponseFields:
    """Extract and validate the fields used to settle one provider response."""

    provider = _provider_config(registry_entry.provider)
    raw_output = provider.extract_output(payload)
    input_tokens, output_tokens = provider.extract_usage(payload)
    served_model_version = provider.extract_served_version(payload)
    _validate_served_model_version(registry_entry, served_model_version)
    return ValidatedProviderResponseFields(
        raw_output=raw_output,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        served_model_version=served_model_version,
    )


def _prompt_with_controlled_docket_context(
    request: HarnessRequest,
    *,
    tool_policy: ToolPolicy,
) -> str:
    if (
        tool_policy is not ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY
        or not request.sample.use_docket_tool
    ):
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
    response_json_schema: Mapping[str, object] | None,
    *,
    service_tier: str = OPENAI_SERVICE_TIER,
) -> urllib.request.Request:
    del response_json_schema
    payload: dict[str, object] = {
        "model": entry.model_id,
        "input": prompt,
        "max_output_tokens": entry.max_output_tokens,
        "service_tier": service_tier,
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
    response_json_schema: Mapping[str, object] | None,
) -> urllib.request.Request:
    del response_json_schema
    payload: dict[str, object] = {
        "model": entry.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": entry.max_output_tokens,
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
    return payload


def _sampling_policy_metadata(entry: ModelRegistryEntry) -> dict[str, str]:
    """Record the sampling policy without exposing legacy controls as settings."""

    del entry
    return {"provider_sampling_policy": "provider_default"}


def _is_openai_provider(entry: ModelRegistryEntry) -> bool:
    return entry.provider.strip().lower() == "openai"


def _effective_timeout_seconds(
    entry: ModelRegistryEntry,
    timeout_seconds: float,
) -> float:
    """Keep Flex OpenAI requests alive for the provider-documented window."""

    if not _is_openai_provider(entry):
        return timeout_seconds
    return max(timeout_seconds, OPENAI_FLEX_TIMEOUT_SECONDS)


def _openai_service_tier_metadata(
    entry: ModelRegistryEntry,
    *,
    used_tier: str | None = None,
    fell_back: bool = False,
) -> dict[str, str]:
    if not _is_openai_provider(entry):
        return {}
    metadata = {
        "service_tier": used_tier or OPENAI_SERVICE_TIER,
        "requested_service_tier": OPENAI_SERVICE_TIER,
    }
    if fell_back:
        metadata["service_tier_fallback"] = "flex_unavailable"
    return metadata


def _observed_openai_service_tier(payload: JsonRecord | None) -> str:
    if payload is None:
        return "unreported"
    value = payload.get("service_tier")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unreported"


def _is_openai_flex_unavailable(exc: LiveModelProviderError) -> bool:
    return exc.status_code in {429, 503}


def _gemini_request(
    entry: ModelRegistryEntry,
    prompt: str,
    api_key: str,
    response_json_schema: Mapping[str, object] | None,
) -> urllib.request.Request:
    model = urllib.parse.quote(entry.model_id, safe="")
    payload: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": entry.max_output_tokens,
            "responseMimeType": "application/json",
        },
        "tools": [],
    }
    if response_json_schema is not None:
        generation_config = cast(dict[str, object], payload["generationConfig"])
        generation_config["responseJsonSchema"] = dict(response_json_schema)
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


def _reject_unsupported_legacy_bedrock_model(
    entry: ModelRegistryEntry,
    bedrock_model_id: str,
    environ: Mapping[str, str] | None,
) -> None:
    resolved_versions = {
        _canonical_model_version(entry.model_id),
        _canonical_model_version(entry.model_version_or_snapshot),
        _canonical_model_version(bedrock_model_id),
    }
    if "claude-sonnet-5" not in resolved_versions:
        return
    values = os.environ if environ is None else environ
    runtime_env = ANTHROPIC_RUNTIME_ENV
    runtime = values.get(runtime_env)
    if not runtime:
        runtime_env = "ANTHROPIC_RUNTIME"
        runtime = values.get(runtime_env)
    raise LiveModelConfigError(
        f"model {bedrock_model_id!r} is unsupported by the legacy Bedrock "
        f"InvokeModel runtime selected by {runtime_env}={runtime!r}; "
        f"unset {runtime_env} to use the direct Anthropic API"
    )


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


def _call_live_http_provider(
    registry_entry: ModelRegistryEntry,
    prompt: str,
    *,
    api_key_supplier: Callable[[], str],
    response_json_schema: Mapping[str, object] | None,
    transport: LiveModelTransport,
    timeout_seconds: float,
    max_attempts: int,
    retry_backoff_seconds: float,
    attempt_handler: ProviderAttemptHandler | None,
) -> tuple[JsonRecord, int, int, str | None, bool]:
    """POST one live HTTP provider call, with OpenAI Flex-to-standard fallback."""

    if not _is_openai_provider(registry_entry):
        provider = _provider_config(registry_entry.provider)

        def provider_call() -> JsonRecord:
            provider_request = provider.build_request(
                registry_entry,
                prompt,
                api_key_supplier(),
                response_json_schema,
            )
            return transport(provider_request, timeout_seconds)

        payload, request_count, durable_attempt_ordinal = _call_with_provider_retries(
            provider_call,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            attempt_handler=attempt_handler,
        )
        return payload, request_count, durable_attempt_ordinal, None, False

    used_tier = OPENAI_SERVICE_TIER
    fell_back = False

    def openai_call() -> JsonRecord:
        request = _openai_request(
            registry_entry,
            prompt,
            api_key_supplier(),
            response_json_schema,
            service_tier=used_tier,
        )
        return transport(request, timeout_seconds)

    def on_retryable_error(exc: LiveModelProviderError) -> None:
        nonlocal used_tier, fell_back
        if used_tier == OPENAI_SERVICE_TIER and _is_openai_flex_unavailable(exc):
            used_tier = OPENAI_FALLBACK_SERVICE_TIER
            fell_back = True

    payload, request_count, durable_attempt_ordinal = _call_with_provider_retries(
        openai_call,
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
        attempt_handler=attempt_handler,
        on_retryable_error=on_retryable_error,
    )
    return payload, request_count, durable_attempt_ordinal, used_tier, fell_back


def _call_with_provider_retries(
    call: Callable[[], JsonRecord],
    *,
    max_attempts: int,
    retry_backoff_seconds: float,
    attempt_handler: ProviderAttemptHandler | None = None,
    on_retryable_error: Callable[[LiveModelProviderError], None] | None = None,
) -> tuple[JsonRecord, int, int]:
    """Retry provider transport failures that are plausibly temporary."""

    request_count = 0

    def counted_call() -> JsonRecord:
        nonlocal request_count
        request_count += 1
        return call()

    for attempt in range(1, max_attempts + 1):
        try:
            payload = (
                attempt_handler.run_attempt(attempt, counted_call)
                if attempt_handler is not None
                else counted_call()
            )
            durable_attempt_ordinal = (
                attempt_handler.durable_attempt_ordinal(attempt)
                if attempt_handler is not None
                else attempt
            )
            return payload, request_count, durable_attempt_ordinal
        except LiveModelProviderError as exc:
            if attempt >= max_attempts or not _is_retryable_provider_error(exc):
                raise
            if on_retryable_error is not None:
                on_retryable_error(exc)
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds * (2 ** (attempt - 1)))
    raise LiveModelProviderError("provider request retry loop exhausted")


def _record_post_response_failure(
    attempt_handler: ProviderAttemptHandler | None,
    durable_attempt_ordinal: int,
    exc: BaseException,
) -> None:
    if attempt_handler is None:
        return
    # Fail closed if the spend authority cannot durably record an ambiguous
    # post-response attempt. The original exception remains available through
    # exception chaining, but must not hide the stronger authority failure.
    attempt_handler.record_post_response_failure(
        durable_attempt_ordinal,
        failure_type=type(exc).__name__,
    )


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
    input_price = entry.input_token_price
    output_price = entry.output_token_price
    surcharge = entry.long_context_surcharge
    if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
        input_price *= surcharge.input_price_multiplier
        output_price *= surcharge.output_price_multiplier
    return (
        (input_tokens * input_price) + (output_tokens * output_price)
    ) / _PRICE_UNITS_PER_TOKEN


def _api_key(env_name: str, environ: Mapping[str, str] | None) -> str:
    values = os.environ if environ is None else environ
    value = values.get(env_name)
    if value is None or not value.strip():
        raise LiveModelConfigError(f"{env_name} is required")
    return value.strip()

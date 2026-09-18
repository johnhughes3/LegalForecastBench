"""Native Jev probabilities through the supported Vercel evaluation SDK."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.request import Request

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.live_model_solver import (
    LiveModelProviderError,
    LiveModelTransport,
    SolverResponse,
    default_live_model_transport,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.response_verification import verify_provider_response
from legalforecast.immutable_io import read_single_link_file
from legalforecast.release import ForecastExecution, ForecastPredictionUnit

from .packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    require_request_fits,
)
from .summaries import SummaryCache


class _TypeSafeRawHttpResponse(Protocol):
    content: bytes
    headers: Mapping[str, str]


class _TypeSafeResponse(Protocol):
    raw_http_response: _TypeSafeRawHttpResponse


class _TypeSafeClient(Protocol):
    system_one: Callable[..., _TypeSafeResponse]


@dataclass(frozen=True)
class JevCaseInput:
    """One complete, size-checked evaluation request."""

    request: Mapping[str, object]
    unit_ids: tuple[str, ...]


def build_jev_case_input(
    entry: ModelRegistryEntry,
    execution: ForecastExecution,
    units: tuple[ForecastPredictionUnit, ...],
    summaries_path: Path | None,
) -> JevCaseInput:
    """Read frozen source bytes and, when requested, the frozen summaries."""

    documents = case_documents(execution, units)
    summaries: dict[str, str] | None = None
    if entry.jev_input_mode == "luna_summaries":
        if summaries_path is None:
            raise ValueError("Jev Luna-summary mode requires --jev-summaries")
        raw = read_single_link_file(summaries_path, label="Jev summaries")
        digest = str(
            RAW_BYTES_RAW_SHA256_V1.commit(raw, domain=PUBLIC_RUN_RECEIPT_V1).digest
        )
        if digest != entry.jev_summaries_sha256:
            raise ValueError("Jev summary cache differs from frozen registry")
        cache = SummaryCache.from_bytes(raw, execution.release.release_digest)
        summaries = {}
        for document in documents:
            summary = cache.get(
                units[0].case_id,
                document.document_id,
                document.source_sha256,
                "gpt-5.6-luna",
                JEV_REQUEST_BYTE_BUDGET,
            )
            if summary is None:
                raise ValueError(f"missing or stale summary: {document.document_id}")
            summaries[document.document_id] = summary.text
    elif entry.jev_input_mode != "full_text" or summaries_path is not None:
        raise ValueError("invalid Jev input mode or unexpected summary cache")
    request = case_request(
        units,
        documents,
        summaries=summaries,
        provider=entry.provider,
        model_id=entry.model_id,
    )
    require_request_fits(request)
    return JevCaseInput(request, tuple(u.unit_id for u in units))


def validate_jev_inputs(
    entry: ModelRegistryEntry, execution: ForecastExecution, summaries_path: Path | None
) -> None:
    """Check every case before purchasing any forecast."""

    for case in execution.release.cases:
        units = tuple(
            u for u in execution.release.prediction_units if u.case_id == case.case_id
        )
        build_jev_case_input(entry, execution, units, summaries_path)


def _sdk_call(body: bytes, values: Mapping[str, str]) -> Mapping[str, object]:
    node = shutil.which("node")
    script = Path(__file__).resolve().parents[2] / "integrations/jev/evaluate.mjs"
    if node is None or not script.is_file():
        raise ValueError(
            "Jev requires Node and the pinned integrations/jev SDK installation"
        )
    result = subprocess.run(
        [node, str(script)],
        input=body,
        capture_output=True,
        timeout=150,
        env={
            "PATH": values.get("PATH", os.defpath),
            "AI_GATEWAY_API_KEY": values["AI_GATEWAY_API_KEY"],
        },
        check=False,
    )
    if result.returncode:
        # Retain bounded diagnostics without logging SDK request bodies or keys.
        try:
            error: object = json.loads(result.stderr)
        except (ValueError, UnicodeDecodeError):
            error = {}
        details = cast(dict[str, object], error) if isinstance(error, dict) else {}
        name = details.get("error_name", "SDKError")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
            name = "SDKError"
        api_key = values.get("AI_GATEWAY_API_KEY", "")
        message = details.get("error_message")
        if isinstance(message, str):
            if api_key:
                message = message.replace(api_key, "[REDACTED]")
            message = re.sub(
                r"\b(?:authorization|proxy-authorization)\s*[:=]?\s*[\"']?(?:bearer|basic|token)\s+[^\s,;\"']+",
                "[REDACTED_AUTHORIZATION]",
                message,
                flags=re.IGNORECASE,
            )
            message = re.sub(
                r"\b(?:api[-_ ]?key|x-api-key|access[-_ ]?token|token|key)"
                r"\s*[:=]\s*[\"']?[^\s,;}\"']+",
                "[REDACTED_KEY]",
                message,
                flags=re.IGNORECASE,
            )
            message = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", message).strip()[:512]
        else:
            message = ""
        generation_id = details.get("generation_id")
        if (
            not isinstance(generation_id, str)
            or bool(api_key and api_key in generation_id)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", generation_id)
        ):
            generation_id = None
        status = details.get("status_code")
        status_code = status if type(status) is int else None
        diagnostic = f": {message}" if message else ""
        if status_code is not None:
            diagnostic += f" [status_code={status_code}]"
        if generation_id is not None:
            diagnostic += f" [generation_id={generation_id}]"
        raise LiveModelProviderError(
            f"Jev evaluation SDK failed: {name}{diagnostic} (exit {result.returncode})",
            status_code=status_code,
            retryable=status_code == 429 and details.get("retryable") is True,
        )
    payload: object = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("Jev SDK response is not an object")
    return cast(dict[str, object], payload)


def _typesafe_sdk_call(
    body: bytes,
    values: Mapping[str, str],
    *,
    provider_metadata: MutableMapping[str, object] | None = None,
) -> Mapping[str, object]:
    """Call TypeSafe's first-party SDK once and return its native JSON body."""

    try:
        from typesafe_sdk import (
            RetryPolicy,
            TypeSafeAPIError,
            TypeSafeClient,
            TypeSafeRateLimitError,
            __version__,
        )
    except ImportError as exc:
        raise ValueError(
            "Install the pinned TypeSafe Python SDK before execution"
        ) from exc

    request = json.loads(body)
    if not isinstance(request, dict):
        raise ValueError("TypeSafe request must be an object")
    request = cast(dict[str, object], request)
    model = request.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("TypeSafe request model must be a non-empty string")
    api_key = values.get("TYPESAFE_API_KEY", "")
    if not api_key.strip():
        raise ValueError("TYPESAFE_API_KEY is required")
    try:
        with TypeSafeClient(
            api_key=api_key,
            model=model,
            retry=RetryPolicy(max_retries=0),
            timeout=120.0,
        ) as client:
            typed_client = cast(_TypeSafeClient, client)
            system_one = typed_client.system_one
            response = system_one(
                state=request["state"],
                questions=request["questions"],
                model=model,
                retry=RetryPolicy(max_retries=0),
                timeout=120.0,
            )
            raw = response.raw_http_response.content
            payload: object = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("TypeSafe response is not an object")
            if provider_metadata is not None:
                provider_metadata["sdk"] = f"typesafe-sdk/{__version__}"
                request_id = response.raw_http_response.headers.get(
                    "x-typesafe-request-id"
                )
                if request_id:
                    provider_metadata["request_id"] = request_id
            return cast(dict[str, object], payload)
    except TypeSafeAPIError as exc:
        status = getattr(exc, "status", None)
        status_code = status if type(status) is int else None
        request_id = getattr(exc, "request_id", None)
        diagnostic = "TypeSafe SDK request failed"
        if status_code is not None:
            diagnostic += f" [status_code={status_code}]"
        if isinstance(request_id, str) and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id
        ):
            diagnostic += f" [request_id={request_id}]"
        raise LiveModelProviderError(
            diagnostic,
            status_code=status_code,
            retryable=isinstance(exc, TypeSafeRateLimitError),
        ) from exc


def complete_jev_cell(
    entry: ModelRegistryEntry,
    *,
    handler: ProviderSpendAttemptHandler,
    case: JevCaseInput,
    transport: LiveModelTransport,
    request_body_observer: Callable[[bytes], None],
    environ: Mapping[str, str] | None,
    registry_sha256: str,
) -> SolverResponse:
    """Make one SDK evaluation with no retry or generated-probability layer."""

    values = environ if environ is not None else os.environ
    direct_typesafe = entry.provider.strip().casefold() == "typesafe"
    api_key_name = "TYPESAFE_API_KEY" if direct_typesafe else "AI_GATEWAY_API_KEY"
    if handler.replayable_response is None and not values.get(api_key_name, "").strip():
        raise ValueError(f"{api_key_name} is required")
    if (
        handler.replayable_response is None
        and transport is default_live_model_transport
    ):
        if not direct_typesafe:
            script = (
                Path(__file__).resolve().parents[2] / "integrations/jev/evaluate.mjs"
            )
            if (
                shutil.which("node") is None
                or not (script.parent / "node_modules/ai").exists()
            ):
                raise ValueError("Install the pinned Jev Node SDK before execution")
    body = ARTIFACT_CANONICAL_JSON_V1.encode(dict(case.request))
    direct_provider_metadata: dict[str, object] = {}

    def call() -> Mapping[str, object]:
        request_body_observer(body)
        if transport is default_live_model_transport:
            if direct_typesafe:
                return _typesafe_sdk_call(
                    body,
                    values,
                    provider_metadata=direct_provider_metadata,
                )
            return _sdk_call(body, values)
        # Explicitly injected provider-free transports exercise the same payload.
        return transport(
            Request(
                "https://api.typesafe.ai/v1/systemone"
                if direct_typesafe
                else "https://ai-gateway.vercel.sh",
                data=body,
            ),
            120.0,
        )

    payload = handler.run_attempt(1, call)
    ordinal = handler.durable_attempt_ordinal(1)
    try:
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("Jev answers must be an object")
        answers = cast(dict[str, object], answers)
        if set(answers) != set(case.unit_ids):
            raise ValueError("Jev must return exactly one answer for every frozen unit")
        predictions: list[dict[str, object]] = []
        for unit_id in case.unit_ids:
            answer = answers[unit_id]
            if not isinstance(answer, dict):
                raise ValueError("Jev answer must be an object")
            answer = cast(dict[str, object], answer)
            expected_type = "noul" if direct_typesafe else "boolean"
            if answer.get("type") != expected_type:
                raise ValueError("Jev answer must be a native Boolean probability")
            probability = answer.get("noul" if direct_typesafe else "probability")
            if (
                isinstance(probability, bool)
                or not isinstance(probability, (int, float))
                or not math.isfinite(probability)
                or not 0 <= probability <= 1
            ):
                raise ValueError(
                    "Jev probability must be finite and between zero and one"
                )
            predictions.append(
                {"unit_id": unit_id, "probability_fully_dismissed": probability}
            )
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Jev response is missing usage")
        usage = cast(dict[str, object], usage)
        usage_keys = (
            ("input_tokens", "output_tokens")
            if direct_typesafe
            else (
                "inputTokens",
                "outputTokens",
            )
        )
        input_tokens, output_tokens = (
            usage.get(usage_keys[0]),
            usage.get(usage_keys[1]),
        )
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
        ):
            raise ValueError("Jev token usage is invalid")
        raw_output = ARTIFACT_CANONICAL_JSON_V1.encode(
            {
                "case_assessment": (
                    "Native Jev Boolean probabilities; no generated rationale."
                ),
                "predictions": predictions,
            }
        ).decode("utf-8")
        cost = (
            input_tokens * entry.input_token_price
            + output_tokens * entry.output_token_price
        ) / 1_000_000
        served_model_version = payload.get("model") if direct_typesafe else "unreported"
        if direct_typesafe and served_model_version != entry.model_id:
            raise ValueError(
                "TypeSafe response model does not match the frozen registry"
            )
        verification = verify_provider_response(payload, provider=entry.provider)
        metadata = {
            "provider": entry.provider,
            "model": entry.model_id,
            "served_model_version": (
                cast(str, served_model_version) if direct_typesafe else "unreported"
            ),
            "model_registry_sha256": registry_sha256,
            "execution_backend": (
                "typesafe_python_sdk" if direct_typesafe else "vercel_ai_sdk_evaluate"
            ),
            "execution_condition": f"jev_{entry.jev_input_mode}",
            "provider_attempt_count": "1",
            "provider_metadata": json.dumps(
                direct_provider_metadata
                if direct_typesafe
                else payload.get("providerMetadata", {})
            ),
            **verification.to_metadata(),
        }
    except BaseException as exc:
        handler.record_post_response_failure(ordinal, failure_type=type(exc).__name__)
        raise
    handler.settle_attempt(
        ordinal,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        actual_cost_usd=cost,
        raw_output=raw_output,
    )
    return SolverResponse(raw_output, 1, input_tokens, output_tokens, cost, metadata)

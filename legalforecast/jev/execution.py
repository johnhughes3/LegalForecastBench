"""Native Jev probabilities through the supported Vercel evaluation SDK."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
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
    request = case_request(units, documents, summaries=summaries)
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
        # Retain error class/status without logging SDK request bodies or keys.
        try:
            error: object = json.loads(result.stderr)
        except (ValueError, UnicodeDecodeError):
            error = {}
        details = cast(dict[str, object], error) if isinstance(error, dict) else {}
        name = details.get("error_name", "SDKError")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
            name = "SDKError"
        status = details.get("status_code")
        raise LiveModelProviderError(
            f"Jev evaluation SDK failed: {name} (exit {result.returncode})",
            status_code=status if type(status) is int else None,
            retryable=False,
        )
    payload: object = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("Jev SDK response is not an object")
    return cast(dict[str, object], payload)


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
    if (
        handler.replayable_response is None
        and not values.get("AI_GATEWAY_API_KEY", "").strip()
    ):
        raise ValueError("AI_GATEWAY_API_KEY is required")
    if (
        handler.replayable_response is None
        and transport is default_live_model_transport
    ):
        script = Path(__file__).resolve().parents[2] / "integrations/jev/evaluate.mjs"
        if (
            shutil.which("node") is None
            or not (script.parent / "node_modules/ai").exists()
        ):
            raise ValueError("Install the pinned Jev Node SDK before execution")
    body = ARTIFACT_CANONICAL_JSON_V1.encode(dict(case.request))

    def call() -> Mapping[str, object]:
        request_body_observer(body)
        if transport is default_live_model_transport:
            return _sdk_call(body, values)
        # Explicitly injected provider-free transports exercise the same payload.
        return transport(Request("https://ai-gateway.vercel.sh", data=body), 120.0)

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
            if answer.get("type") != "boolean":
                raise ValueError("Jev answer must be a native Boolean probability")
            probability = answer.get("probability")
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
        input_tokens, output_tokens = (
            usage.get("inputTokens"),
            usage.get("outputTokens"),
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
        verification = verify_provider_response(payload, provider="vercel_ai_gateway")
        metadata = {
            "provider": entry.provider,
            "model": entry.model_id,
            "served_model_version": "unreported",
            "model_registry_sha256": registry_sha256,
            "execution_backend": "vercel_ai_sdk_evaluate",
            "execution_condition": f"jev_{entry.jev_input_mode}",
            "provider_attempt_count": "1",
            "provider_metadata": json.dumps(payload.get("providerMetadata", {})),
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

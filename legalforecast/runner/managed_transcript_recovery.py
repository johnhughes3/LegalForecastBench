# pyright: reportPrivateUsage=false

"""Provider-free recovery of completed managed-agent transcripts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic_ai import ModelMessagesTypeAdapter, ModelResponse
from pydantic_ai.messages import (
    ModelMessage,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

import legalforecast.runner.managed_execution as managed_execution
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.response_verification import (
    require_publishable_response_metadata,
    verify_provider_response,
)
from legalforecast.immutable_io import read_single_link_file
from legalforecast.runner.anthropic_cache import anthropic_cache_cost
from legalforecast.runner.ledger import CellRecord, RunnerLedger, RunValidationError

# The shared managed runtime owns these projections.  Keeping the recovery path
# on the same implementation prevents replay accounting from drifting from live
# execution accounting.

_MANAGED_TOOL_NAMES = frozenset({"bash", "read", "write", "edit", "glob", "grep"})
_TRANSCRIPT_KEYS = frozenset({"model", "cell", "agent_status", "messages"})


@dataclass(frozen=True, slots=True)
class ManagedTranscriptRecovery:
    """The validated replay payload restored for one durable provider cell."""

    cell_id: str
    provider_attempt_id: str
    payload_sha256: str
    response_sha256: str
    estimated_cost_usd: float
    result: managed_execution.ManagedToolAgentResult


def recover_managed_transcript(
    ledger: RunnerLedger,
    *,
    entry: ModelRegistryEntry,
    transcript_path: Path,
    cell_id: str,
) -> ManagedTranscriptRecovery:
    """Validate one terminal transcript and install its replay payload.

    This function never creates a model or opens provider transport.  It binds
    the transcript to the durable request commitment, frozen registry entry,
    cell identity, typed forecast envelope, and shared response accounting
    before handing bytes to the ledger's normal replay path.
    """

    cell = ledger.read_cell_for_recovery(cell_id)
    if cell.status not in {"ambiguous", "reserved"}:
        raise RunValidationError(
            f"cell {cell_id} has {cell.status} state; transcript recovery "
            "requires an unfinished provider cell"
        )
    if cell.provider_attempt_id is None:
        raise RunValidationError(f"cell {cell_id} lacks its provider attempt")
    if cell.request_body_sha256 is None:
        raise RunValidationError(f"cell {cell_id} lacks its request commitment")
    result = managed_result_from_transcript(
        transcript_path,
        entry=entry,
        cell=cell,
    )
    payload = managed_replay_payload(result, entry=entry)
    payload_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(payload)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    persisted_payload_sha256 = payload_sha256
    if cell.response_payload is not None:
        if cell.response_payload_sha256 is None:
            raise RunValidationError("existing durable response lacks its digest")
        matches_current_payload = (
            cell.response_payload_sha256 == payload_sha256
            and cell.response_payload == payload_bytes
        )
        matches_legacy_payload = False
        if not matches_current_payload:
            legacy_payload = _legacy_managed_replay_payload(result, entry=entry)
            if legacy_payload is not None:
                legacy_payload_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(legacy_payload)
                matches_legacy_payload = (
                    cell.response_payload_sha256
                    == hashlib.sha256(legacy_payload_bytes).hexdigest()
                    and cell.response_payload == legacy_payload_bytes
                )
        if not matches_current_payload and not matches_legacy_payload:
            raise RunValidationError(
                "existing durable response differs from transcript recovery"
            )
        if matches_legacy_payload:
            persisted_payload_sha256 = cell.response_payload_sha256
    else:
        ledger.restore_ambiguous_response_payload(
            cell_id,
            provider_attempt_id=cell.provider_attempt_id,
            response_payload=payload_bytes,
            response_payload_sha256=payload_sha256,
        )
    return ManagedTranscriptRecovery(
        cell_id=cell_id,
        provider_attempt_id=cell.provider_attempt_id,
        payload_sha256=persisted_payload_sha256,
        response_sha256=hashlib.sha256(result.raw_output.encode("utf-8")).hexdigest(),
        estimated_cost_usd=managed_execution._managed_result_cost(
            entry,
            result=result,
        ),
        result=result,
    )


def managed_result_from_transcript(
    transcript_path: Path,
    *,
    entry: ModelRegistryEntry,
    cell: CellRecord,
) -> managed_execution.ManagedToolAgentResult:
    """Project a recorded SDK conversation through live-run validations."""

    try:
        raw = read_single_link_file(transcript_path, label="managed transcript")
        record_value: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunValidationError("managed transcript is not valid JSON") from exc
    if not isinstance(record_value, Mapping):
        raise RunValidationError("managed transcript must be an object")
    record = cast(Mapping[str, object], record_value)
    if frozenset(record) != _TRANSCRIPT_KEYS:
        raise RunValidationError("managed transcript has an unexpected shape")
    if record.get("model") != entry.registry_key:
        raise RunValidationError("managed transcript model differs from registry")
    if record.get("cell") != cell.cell_id:
        raise RunValidationError("managed transcript cell differs from ledger")
    agent_status = record.get("agent_status")
    if agent_status not in {"succeeded", "failed"}:
        raise RunValidationError("managed transcript has an invalid agent status")
    messages_value = record.get("messages")
    if not isinstance(messages_value, list) or not messages_value:
        raise RunValidationError("managed transcript has no SDK messages")
    try:
        messages = tuple(ModelMessagesTypeAdapter.validate_python(messages_value))
    except (TypeError, ValueError) as exc:
        raise RunValidationError("managed transcript messages are invalid") from exc

    _verify_managed_prompt(messages, entry=entry, cell=cell)
    provider = entry.provider.strip().lower()
    calls, _returns, final_call = _verify_tool_history(
        messages, require_final_result=provider != "anthropic"
    )
    if final_call is None:
        output = _verify_native_final_envelope(
            messages, required_unit_ids=cell.required_unit_ids
        )
    else:
        output = _verify_final_envelope(
            final_call, required_unit_ids=cell.required_unit_ids
        )
    responses = tuple(
        message for message in messages if isinstance(message, ModelResponse)
    )
    if not responses:
        raise RunValidationError("managed transcript has no provider responses")
    served_models = {
        response.model_name
        for response in responses
        if isinstance(response.model_name, str) and response.model_name
    }
    if len(served_models) != 1:
        raise RunValidationError("managed transcript changed or omitted served model")
    if provider not in {
        "openai",
        "anthropic",
        "google",
        "gemini",
        "vercel_ai_gateway",
    }:
        raise RunValidationError(
            "managed transcript recovery requires OpenAI, Anthropic, Google, "
            "or Vercel AI Gateway provider"
        )
    provider_names = {
        response.provider_name.strip().lower()
        for response in responses
        if isinstance(response.provider_name, str) and response.provider_name.strip()
    }
    allowed_provider_names = {provider}
    expected_provider: str | None = None
    if provider == "vercel_ai_gateway":
        expected_provider = managed_execution.gateway_route_provider(entry.model_id)
        # The Gateway transport uses PydanticAI's OpenAI-compatible adapter, so
        # native SDK responses identify the adapter as ``openai`` while their
        # Gateway routing metadata retains the actual provider route.
        allowed_provider_names.update({"openai", expected_provider})
    if provider_names and not provider_names.issubset(allowed_provider_names):
        raise RunValidationError("managed transcript provider differs from registry")
    served_model = next(iter(served_models))
    if provider == "vercel_ai_gateway":
        try:
            served_model = managed_execution.gateway_normalize_model_identity(
                entry.model_version_or_snapshot,
                served_model,
            )
        except ValueError as exc:
            raise RunValidationError(str(exc)) from exc
    elif served_model != entry.model_version_or_snapshot:
        raise RunValidationError(
            "managed transcript served model differs from registry"
        )
    finish_reason = responses[-1].finish_reason
    if not isinstance(finish_reason, str) or not finish_reason:
        raise RunValidationError("managed transcript lacks finish reason")
    verification = verify_provider_response(
        {"finish_reason": finish_reason}, provider=provider
    )
    require_publishable_response_metadata(verification.to_metadata())
    service_tier = _service_tier(responses, provider=provider)

    gateway_response_metadata: tuple[Mapping[str, str], ...] = ()
    if provider == "vercel_ai_gateway":
        assert expected_provider is not None
        metadata_rows: list[Mapping[str, str]] = []
        for response in responses:
            row = (response.provider_details or {}).get("gateway_metadata")
            if not isinstance(row, Mapping):
                raise RunValidationError(
                    "managed transcript omitted Gateway routing and usage metadata"
                )
            try:
                metadata_rows.append(
                    managed_execution.validate_gateway_metadata(
                        cast(Mapping[str, object], row),
                        expected_model_id=entry.model_id,
                        expected_provider=expected_provider,
                    )
                )
            except ValueError as exc:
                raise RunValidationError(str(exc)) from exc
        gateway_response_metadata = tuple(metadata_rows)

    response_usages: list[tuple[int, int]] = []
    thoughts_tokens = 0
    for response in responses:
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        if input_tokens < 0 or output_tokens < 0:
            raise RunValidationError("managed transcript has invalid token usage")
        try:
            item_thoughts = managed_execution._response_thoughts_tokens(response)
        except managed_execution.ManagedToolAgentError as exc:
            raise RunValidationError(
                "managed transcript has invalid thought usage"
            ) from exc
        response_usages.append((input_tokens, output_tokens))
        thoughts_tokens += item_thoughts
    response_cache_usages = (
        tuple(
            (response.usage.cache_read_tokens, response.usage.cache_write_tokens)
            for response in responses
        )
        if provider == "anthropic"
        else ()
    )
    input_tokens = sum(item[0] for item in response_usages)
    output_tokens = sum(item[1] for item in response_usages)
    result = managed_execution.ManagedToolAgentResult(
        raw_output=output.model_dump_json(),
        request_count=len(responses),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        served_model=served_model,
        finish_reason=finish_reason,
        service_tier=service_tier,
        called_tools=tuple(
            call.tool_name for call in calls if call.tool_name != "final_result"
        ),
        response_usages=tuple(response_usages),
        thoughts_tokens=thoughts_tokens,
        gateway_response_metadata=gateway_response_metadata,
        response_cache_usages=response_cache_usages,
    )
    try:
        estimated_cost = managed_execution._managed_result_cost(
            entry,
            result=result,
        )
    except (managed_execution.ManagedToolAgentError, ValueError) as exc:
        raise RunValidationError(str(exc)) from exc
    if not math.isfinite(estimated_cost) or estimated_cost < 0:
        raise RunValidationError("managed transcript has invalid estimated cost")
    return result


def managed_replay_payload(
    result: managed_execution.ManagedToolAgentResult,
    *,
    entry: ModelRegistryEntry,
) -> dict[str, object]:
    """Encode the same response fields emitted by live managed execution."""

    # Recompute from the per-response usage captured in the transcript so the
    # persisted payload remains derived data rather than a caller-supplied claim.
    cache_evidence: dict[str, object] = {}
    if entry.provider.strip().lower() == "anthropic" and result.response_cache_usages:
        _, cache_evidence = anthropic_cache_cost(
            entry,
            result.response_usages,
            result.response_cache_usages,
        )
        cache_evidence.update(
            {
                "cache_read_tokens": sum(
                    row[0] for row in result.response_cache_usages
                ),
                "cache_write_tokens": sum(
                    row[1] for row in result.response_cache_usages
                ),
            }
        )
    payload: dict[str, object] = {
        **({"anthropic_cache_evidence": cache_evidence} if cache_evidence else {}),
        "raw_output": result.raw_output,
        "request_count": result.request_count,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "served_model": result.served_model,
        "finish_reason": result.finish_reason,
        "service_tier": result.service_tier,
        "called_tools": list(result.called_tools),
        "thoughts_tokens": result.thoughts_tokens,
        "gateway_response_metadata": [
            dict(row) for row in result.gateway_response_metadata
        ],
        "estimated_cost_usd": managed_execution._managed_result_cost(
            entry,
            result=result,
        ),
    }
    return payload


def _legacy_managed_replay_payload(
    result: managed_execution.ManagedToolAgentResult,
    *,
    entry: ModelRegistryEntry,
) -> dict[str, object] | None:
    """Encode the pre-Gateway payload shape for non-Gateway replay matches."""

    provider = entry.provider.strip().lower()
    if provider == "anthropic":
        # Pydantic AI deserializes older Anthropic transcripts with omitted
        # cache fields as explicit zero-valued fields.  Permit their original
        # durable payload to match by removing only the newly derived evidence
        # when every cache dimension is zero.  A positive cache count must use
        # the current cache-aware payload and can never match this candidate.
        if not result.response_cache_usages or any(
            cache_read or cache_write
            for cache_read, cache_write in result.response_cache_usages
        ):
            return None
        payload = managed_replay_payload(result, entry=entry)
        payload.pop("anthropic_cache_evidence", None)
        return payload
    if provider not in {"openai", "google", "gemini"}:
        return None
    if result.gateway_response_metadata:
        return None
    payload = managed_replay_payload(result, entry=entry)
    payload.pop("gateway_response_metadata", None)
    return payload


def _service_tier(responses: Sequence[ModelResponse], *, provider: str) -> str:
    tiers = {
        tier
        for response in responses
        if isinstance(
            (tier := (response.provider_details or {}).get("service_tier")), str
        )
        and tier
    }
    if len(tiers) > 1 and provider != "vercel_ai_gateway":
        raise RunValidationError("managed transcript changed service tier")
    if provider == "openai":
        if len(tiers) != 1 or any(
            not isinstance((response.provider_details or {}).get("service_tier"), str)
            for response in responses
        ):
            raise RunValidationError("managed transcript lacks service tier")
        return next(iter(tiers))
    return "mixed" if len(tiers) > 1 else next(iter(tiers), "unreported")


def _verify_managed_prompt(
    messages: Sequence[ModelMessage],
    *,
    entry: ModelRegistryEntry,
    cell: CellRecord,
) -> None:
    if not messages or not hasattr(messages[0], "parts"):
        raise RunValidationError("managed transcript lacks initial request")
    prompt_parts = [
        part for part in messages[0].parts if isinstance(part, UserPromptPart)
    ]
    if len(prompt_parts) != 1 or not isinstance(prompt_parts[0].content, str):
        raise RunValidationError("managed transcript initial prompt is invalid")
    prompt_text = prompt_parts[0].content
    try:
        prompt_value: object = json.loads(prompt_text)
    except json.JSONDecodeError as exc:
        raise RunValidationError(
            "managed transcript initial prompt is not JSON"
        ) from exc
    if not isinstance(prompt_value, Mapping):
        raise RunValidationError("managed transcript initial prompt is malformed")
    prompt = cast(Mapping[str, object], prompt_value)
    canonical_prompt = json.dumps(
        prompt,
        sort_keys=True,
        separators=(",", ":"),
    )
    if canonical_prompt != prompt_text:
        raise RunValidationError("managed transcript initial prompt is not canonical")
    if prompt.get("case_id") != cell.case_id or prompt.get("task") != (
        "forecast_motion_to_dismiss"
    ):
        raise RunValidationError("managed transcript initial prompt differs from cell")
    prediction_units = prompt.get("prediction_units")
    if not isinstance(prediction_units, list):
        raise RunValidationError("managed transcript prompt has no prediction units")
    prompt_unit_ids: list[str] = []
    for unit in cast(list[object], prediction_units):
        if not isinstance(unit, Mapping):
            raise RunValidationError("managed transcript prompt unit is malformed")
        typed_unit = cast(Mapping[str, object], unit)
        if not isinstance(typed_unit.get("unit_id"), str):
            raise RunValidationError("managed transcript prompt unit is malformed")
        prompt_unit_ids.append(cast(str, typed_unit["unit_id"]))
    if tuple(prompt_unit_ids) != cell.required_unit_ids:
        raise RunValidationError("managed transcript prompt units differ from cell")
    expected_commitment = ARTIFACT_CANONICAL_JSON_V1.encode(
        {
            "model": entry.model_id,
            "case_id": cell.case_id,
            "required_unit_ids": list(cell.required_unit_ids),
            "initial_prompt": prompt_text,
            "tools": ["bash", "read", "write", "edit", "glob", "grep"],
        }
    )
    expected_digest = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            expected_commitment,
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    if cell.request_body_sha256 != expected_digest:
        raise RunValidationError("managed transcript request differs from cell")


def _verify_tool_history(
    messages: Sequence[ModelMessage],
    *,
    require_final_result: bool = True,
) -> tuple[tuple[ToolCallPart, ...], dict[str, ToolReturnPart], ToolCallPart | None]:
    calls: list[ToolCallPart] = []
    returns: dict[str, ToolReturnPart] = {}
    call_ids: set[str] = set()
    final_calls: list[ToolCallPart] = []
    for message in messages:
        for part in getattr(message, "parts", ()):
            if isinstance(part, ToolCallPart):
                if not part.tool_call_id or part.tool_call_id in call_ids:
                    raise RunValidationError(
                        "managed transcript has duplicate tool call"
                    )
                if (
                    part.tool_name != "final_result"
                    and part.tool_name not in _MANAGED_TOOL_NAMES
                ):
                    raise RunValidationError(
                        "managed transcript contains an unknown tool"
                    )
                call_ids.add(part.tool_call_id)
                calls.append(part)
                if part.tool_name == "final_result":
                    final_calls.append(part)
            elif isinstance(part, ToolReturnPart):
                if not part.tool_call_id or part.tool_call_id in returns:
                    raise RunValidationError(
                        "managed transcript has duplicate tool return"
                    )
                returns[part.tool_call_id] = part
    if require_final_result and len(final_calls) != 1:
        raise RunValidationError("managed transcript must contain one final result")
    if not require_final_result and len(final_calls) > 1:
        raise RunValidationError("managed transcript has multiple final results")
    if set(returns) != call_ids:
        raise RunValidationError("managed transcript tool calls lack matching returns")
    if final_calls and returns[final_calls[0].tool_call_id].outcome != "success":
        raise RunValidationError("managed transcript final result was not accepted")
    successful_read = any(
        call.tool_name in {"bash", "read", "grep"}
        and returns[call.tool_call_id].outcome == "success"
        for call in calls
    )
    if not successful_read:
        raise RunValidationError("managed transcript has no successful document tool")
    response_indexes = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, ModelResponse)
    ]
    if final_calls:
        final_index = next(
            index
            for index, message in enumerate(messages)
            if any(
                isinstance(part, ToolCallPart)
                and part.tool_call_id == final_calls[0].tool_call_id
                for part in getattr(message, "parts", ())
            )
        )
        if not response_indexes or final_index != response_indexes[-1]:
            raise RunValidationError("final result is not the last provider response")
    return tuple(calls), returns, final_calls[0] if final_calls else None


def _verify_native_final_envelope(
    messages: Sequence[ModelMessage],
    *,
    required_unit_ids: tuple[str, ...],
) -> managed_execution.ForecastEnvelope:
    """Validate Anthropic native JSON output represented by a ``TextPart``."""

    responses = [
        (index, message)
        for index, message in enumerate(messages)
        if isinstance(message, ModelResponse)
    ]
    if not responses:
        raise RunValidationError("managed transcript has no provider responses")
    final_index, final_response = responses[-1]
    if final_index != len(messages) - 1:
        raise RunValidationError("native output is not the last provider response")
    text_parts = [part for part in final_response.parts if isinstance(part, TextPart)]
    if len(text_parts) != 1:
        raise RunValidationError("managed transcript must contain one native output")
    try:
        envelope = managed_execution.ForecastEnvelope.model_validate_json(
            text_parts[0].content
        )
    except ValueError as exc:
        raise RunValidationError(
            "managed native output is not a forecast envelope"
        ) from exc
    output_ids = tuple(item.unit_id for item in envelope.predictions)
    if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(
        required_unit_ids
    ):
        raise RunValidationError("managed native output has the wrong prediction units")
    return envelope


def _verify_final_envelope(
    final_call: ToolCallPart,
    *,
    required_unit_ids: tuple[str, ...],
) -> managed_execution.ForecastEnvelope:
    try:
        args = final_call.args_as_dict(raise_if_invalid=True)
    except (AssertionError, ValueError) as exc:
        raise RunValidationError(
            "managed final result arguments are not a valid object"
        ) from exc
    try:
        envelope = managed_execution.ForecastEnvelope.model_validate(args)
    except ValueError as exc:
        raise RunValidationError(
            "managed final result is not a forecast envelope"
        ) from exc
    output_ids = tuple(item.unit_id for item in envelope.predictions)
    if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(
        required_unit_ids
    ):
        raise RunValidationError("managed final result has the wrong prediction units")
    return envelope

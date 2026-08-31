"""Pins for the generic OpenAI-compatible chat-completions adapter.

Every assertion here encodes a documented provider fact, not a guess about what
"OpenAI-compatible" implies. Two of them exist because the equivalent mistakes
were made for real on the Gemini lane: a reasoning parameter sent at the wrong
nesting, and billed reasoning tokens reported in a usage field the accounting
never read. The first fails loudly at the provider; the second fails silently
and under-reports spend against an owner cost cap.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelResponseError,
    LiveModelSolver,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry, load_model_registry
from legalforecast.evals.openai_compatible_provider import (
    DEEPINFRA_API_KEY_ENV,
    DEEPINFRA_CHAT_COMPLETIONS_URL,
    DEEPINFRA_PROVIDER,
    XAI_API_KEY_ENV,
    XAI_CHAT_COMPLETIONS_URL,
    XAI_PROVIDER,
    ReasoningTokenAccounting,
    deepinfra_model_metadata_url,
    openai_compatible_provider,
    openai_compatible_provider_names,
)

XAI_ENV = {XAI_API_KEY_ENV: "xai-secret"}
DEEPINFRA_ENV = {DEEPINFRA_API_KEY_ENV: "deepinfra-secret"}


def test_xai_request_body_pins_every_documented_field() -> None:
    """Pin the exact request body, especially the reasoning parameter's nesting.

    xAI's Chat Completions API takes a flat top-level ``reasoning_effort``. Its
    sibling Responses API nests the same setting as ``reasoning: {"effort": ...}``
    and the two are not interchangeable, so the flat spelling is pinned here.
    Source: https://docs.x.ai/developers/model-capabilities/text/reasoning and
    https://docs.x.ai/developers/rest-api-reference/inference/chat, checked
    2026-08-30.
    """

    transport = _FixtureTransport(_xai_payload())
    complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=transport,
        environ=XAI_ENV,
    )

    request = transport.only_request()
    assert request.full_url == XAI_CHAT_COMPLETIONS_URL
    assert request.get_header("Authorization") == "Bearer xai-secret"
    body = _json_body(request)
    assert body == {
        "model": "grok-4.6",
        "messages": [{"role": "user", "content": "Predict the case outcome."}],
        "max_completion_tokens": 4096,
        "stream": False,
        # Flat, not nested under "reasoning".
        "reasoning_effort": "high",
        # https://docs.x.ai/developers/tools/web-search, checked 2026-08-30:
        # mode "off" means "no search performed".
        "search_parameters": {"mode": "off"},
    }


def test_xai_request_never_nests_reasoning_the_responses_api_way() -> None:
    """The Responses-API spelling would be silently ignored by chat completions."""

    transport = _FixtureTransport(_xai_payload())
    complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=transport,
        environ=XAI_ENV,
    )

    body = _json_body(transport.only_request())
    assert "reasoning" not in body
    assert body["reasoning_effort"] == "high"


def test_adapter_refuses_an_entry_with_no_explicit_reasoning_setting() -> None:
    """Owner directive (bead legalforecastbench-1xko): never a silent default.

    xAI documents a default of "high", but its REST reference page contradicts
    the capability page about what that default is. Relying on either is how a
    run silently executes at the wrong reasoning depth.
    """

    entry = _xai_entry(reasoning_effort=None)
    with pytest.raises(LiveModelConfigError, match="explicit reasoning_effort"):
        complete_live_prompt(
            entry,
            "Predict the case outcome.",
            transport=_FixtureTransport(_xai_payload()),
            environ=XAI_ENV,
        )


def test_xai_usage_adds_reasoning_tokens_to_the_billed_output_count() -> None:
    """Reasoning tokens are EXCLUDED from completion_tokens on xAI and additive.

    Verified from the docs' own worked example
    (https://docs.x.ai/developers/rest-api-reference/inference/chat, checked
    2026-08-30): prompt 32 + completion 9 + reasoning 94 == total 135. The
    OpenAI-style ``completion_tokens_details`` nesting conventionally implies
    the opposite, which is exactly why this is pinned. Reading only
    ``completion_tokens`` would under-report billed spend by the reasoning
    count -- here, by more than 10x.
    """

    payload = _xai_payload()
    payload["usage"] = {
        "prompt_tokens": 32,
        "completion_tokens": 9,
        "total_tokens": 135,
        "completion_tokens_details": {"reasoning_tokens": 94},
    }
    transport = _FixtureTransport(payload)

    response = complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=transport,
        environ=XAI_ENV,
    )

    assert response.input_tokens == 32
    assert response.output_tokens == 9 + 94
    # And the settled cost follows the billed count, not the visible one.
    billed = ((32 * 0.25) + (103 * 1.0)) / 1_000_000
    visible_only = ((32 * 0.25) + (9 * 1.0)) / 1_000_000
    assert response.estimated_cost == billed
    assert response.estimated_cost > visible_only


def test_xai_usage_handles_a_response_that_reports_no_reasoning_tokens() -> None:
    """A missing reasoning field is zero, never a refusal."""

    payload = _xai_payload()
    payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 4}
    response = complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=_FixtureTransport(payload),
        environ=XAI_ENV,
    )

    assert (response.input_tokens, response.output_tokens) == (10, 4)


def test_adapter_refuses_an_empty_content_rather_than_settling_it() -> None:
    """Reasoning text is never substituted for the graded answer.

    Several OpenAI-compatible stacks return thinking in ``reasoning_content``
    and can leave ``content`` empty. Settling that as an empty answer would
    score as unparseable while still being billed.
    """

    payload = _xai_payload()
    payload["choices"] = [
        {
            "finish_reason": "stop",
            "message": {"content": "", "reasoning_content": "thinking text"},
        }
    ]

    with pytest.raises(LiveModelResponseError, match=r"message\.content was empty"):
        complete_live_prompt(
            _xai_entry(),
            "Predict the case outcome.",
            transport=_FixtureTransport(payload),
            environ=XAI_ENV,
        )


def test_adapter_refuses_a_served_model_that_is_not_the_frozen_version() -> None:
    """Substitution detection.

    xAI publishes no dated snapshot for grok-4.6 and has a documented precedent
    for silently redirecting a resolving slug to a different model at different
    pricing (https://docs.x.ai/developers/migration/may-15-retirement, checked
    2026-08-30). The echoed ``model`` field is the one signal that catches it.
    """

    payload = _xai_payload()
    payload["model"] = "grok-4.3"

    with pytest.raises(LiveModelResponseError, match="did not match frozen registry"):
        complete_live_prompt(
            _xai_entry(),
            "Predict the case outcome.",
            transport=_FixtureTransport(payload),
            environ=XAI_ENV,
        )


def test_xai_structured_output_uses_the_chat_completions_nesting() -> None:
    """response_format.json_schema, not the Responses API's text.format shape.

    Source: https://docs.x.ai/developers/model-capabilities/text/structured-outputs,
    checked 2026-08-30.
    """

    schema = {"type": "object", "properties": {"outcome": {"type": "string"}}}
    transport = _FixtureTransport(_xai_payload())
    complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=transport,
        environ=XAI_ENV,
        response_json_schema=schema,
    )

    body = _json_body(transport.only_request())
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "legalforecast_response",
            "schema": schema,
            "strict": True,
        },
    }


def test_adapter_requires_the_provider_api_key() -> None:
    with pytest.raises(LiveModelConfigError, match=XAI_API_KEY_ENV):
        complete_live_prompt(
            _xai_entry(),
            "Predict the case outcome.",
            transport=_FixtureTransport(_xai_payload()),
            environ={},
        )


def test_solver_accepts_the_adapter_provider_and_reports_its_registry_key() -> None:
    solver = LiveModelSolver(
        registry_entry=_xai_entry(),
        transport=_FixtureTransport(_xai_payload()),
        environ=XAI_ENV,
    )
    assert solver.solver_id == "xai:grok-4.6"


def test_provider_spec_lookup_is_case_insensitive_and_enumerable() -> None:
    assert openai_compatible_provider("XAI") is XAI_PROVIDER
    assert openai_compatible_provider("  xai  ") is XAI_PROVIDER
    assert openai_compatible_provider("not-a-provider") is None
    assert "xai" in openai_compatible_provider_names()


def test_every_declared_provider_states_its_reasoning_accounting() -> None:
    """A provider spec must not leave the billed-token question implicit."""

    for name in openai_compatible_provider_names():
        spec = openai_compatible_provider(name)
        assert spec is not None
        assert spec.reasoning_token_accounting in set(ReasoningTokenAccounting)
        assert spec.chat_completions_url.startswith("https://")


def test_deepinfra_request_body_pins_the_kimi_k3_shape() -> None:
    """Different host, different URL and key, same documented reasoning spelling."""

    transport = _FixtureTransport(_deepinfra_payload())
    complete_live_prompt(
        _kimi_entry(),
        "Predict the case outcome.",
        transport=transport,
        environ=DEEPINFRA_ENV,
    )

    request = transport.only_request()
    assert request.full_url == DEEPINFRA_CHAT_COMPLETIONS_URL
    assert request.get_header("Authorization") == "Bearer deepinfra-secret"
    assert _json_body(request) == {
        "model": "moonshotai/Kimi-K3",
        "messages": [{"role": "user", "content": "Predict the case outcome."}],
        "max_completion_tokens": 4096,
        "stream": False,
        "reasoning_effort": "high",
    }


def test_deepinfra_sends_glm_5_3_the_flat_reasoning_effort_not_the_5_2_shape() -> None:
    """GLM 5.3 rides the Kimi K3 spelling; GLM 5.2's nested toggle is not it.

    GLM 5.2 nested a separate ``thinking: {type}`` object beside a seven-value
    effort control. GLM 5.3 replaced that with a flat top-level
    ``reasoning_effort`` accepting exactly ``low`` / ``high`` / ``max``
    (https://huggingface.co/zai-org/GLM-5.3, checked 2026-08-30) -- the same
    three values Kimi K3 takes, which is why no second
    ``ReasoningParameterStyle`` was needed.

    The failure this guards is silent, not loud: the card states an
    unrecognized value falls back to ``max`` rather than erroring, so sending
    the 5.2 shape would run every cell at a reasoning budget the official four
    never had, with nothing in the response to show it. The entry is loaded
    from the shipped registry rather than a fixture so the payload pinned here
    is the one a real dispatch would send.
    """

    registry = load_model_registry(
        Path(__file__).resolve().parents[1]
        / "model_registries"
        / "cycle-1-supplementary-glm-5.3-2026-08-30.json"
    )
    entry = registry.get("deepinfra", "zai-org/GLM-5.3")
    payload = _deepinfra_payload()
    payload["model"] = "zai-org/GLM-5.3"
    transport = _FixtureTransport(payload)

    complete_live_prompt(
        entry,
        "Predict the case outcome.",
        transport=transport,
        environ=DEEPINFRA_ENV,
    )

    request = transport.only_request()
    assert request.full_url == DEEPINFRA_CHAT_COMPLETIONS_URL
    body = _json_body(request)
    assert body["model"] == "zai-org/GLM-5.3"
    assert body["reasoning_effort"] == "high"
    assert body["max_completion_tokens"] == 128000
    assert "thinking" not in body
    assert "reasoning" not in body


def test_deepinfra_counts_undocumented_reasoning_tokens_conservatively() -> None:
    """Unverified accounting must over-report, never under-report.

    DeepInfra's docs contain no occurrence of
    ``completion_tokens_details.reasoning_tokens`` and no response example
    locating reasoning tokens (checked 2026-08-30). Together documents the same
    model's as INCLUDED and xAI documents its own as EXCLUDED, so neighbours do
    not settle it. Under-reporting spend against an owner cap is the
    unrecoverable direction, so the unverified state adds them.
    """

    assert (
        DEEPINFRA_PROVIDER.reasoning_token_accounting
        is ReasoningTokenAccounting.UNVERIFIED_CONSERVATIVE
    )
    assert DEEPINFRA_PROVIDER.adds_reasoning_tokens is True

    payload = _deepinfra_payload()
    payload["usage"] = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "completion_tokens_details": {"reasoning_tokens": 500},
    }
    response = complete_live_prompt(
        _kimi_entry(),
        "Predict the case outcome.",
        transport=_FixtureTransport(payload),
        environ=DEEPINFRA_ENV,
    )

    assert response.output_tokens == 20 + 500


def test_unverified_accounting_is_published_in_response_metadata() -> None:
    """A run on unverified accounting must not look like a verified one."""

    response = complete_live_prompt(
        _kimi_entry(),
        "Predict the case outcome.",
        transport=_FixtureTransport(_deepinfra_payload()),
        environ=DEEPINFRA_ENV,
    )
    assert response.metadata["reasoning_token_accounting"] == "unverified_conservative"

    xai_response = complete_live_prompt(
        _xai_entry(),
        "Predict the case outcome.",
        transport=_FixtureTransport(_xai_payload()),
        environ=XAI_ENV,
    )
    assert xai_response.metadata["reasoning_token_accounting"] == "additive"


def test_deepinfra_drift_detection_url_is_the_documented_metadata_endpoint() -> None:
    """Drift DETECTION, not a request-level pin.

    No US host offers request-level version pinning for these models. DeepInfra
    is the only one publishing machine-readable ``version`` and
    ``quantization`` without a key, which is what lets preflight refuse a
    dispatch whose served artifact changed since the freeze.
    """

    assert (
        deepinfra_model_metadata_url("moonshotai/Kimi-K3")
        == "https://api.deepinfra.com/models/moonshotai/Kimi-K3"
    )


def _kimi_entry(*, max_output_tokens: int = 4096) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "deepinfra",
            "model_id": "moonshotai/Kimi-K3",
            "display_name": "Kimi K3",
            "model_version_or_snapshot": "moonshotai/Kimi-K3",
            "release_timestamp": "2026-07-17T00:00:00Z",
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": "unknown",
            "max_output_tokens": max_output_tokens,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1048576,
            "pricing_source": "fixture price sheet",
            "input_token_price": 2.85,
            "output_token_price": 14.25,
            "reasoning_effort": "high",
            "known_cutoff_publicity_caveats": [],
        }
    )


def _deepinfra_payload() -> dict[str, Any]:
    return {
        "model": "moonshotai/Kimi-K3",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": '{"predictions":[]}',
                    "reasoning_content": "internal thinking trace",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 250,
            "total_tokens": 1250,
        },
    }


def _xai_entry(
    *,
    reasoning_effort: str | None = "high",
    max_output_tokens: int = 4096,
) -> ModelRegistryEntry:
    record: dict[str, object] = {
        "provider": "xai",
        "model_id": "grok-4.6",
        "display_name": "Grok 4.6",
        "model_version_or_snapshot": "grok-4.6",
        "release_timestamp": "2026-08-12T00:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "unknown",
        "max_output_tokens": max_output_tokens,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 500000,
        "pricing_source": "fixture price sheet",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }
    if reasoning_effort is not None:
        record["reasoning_effort"] = reasoning_effort
    return ModelRegistryEntry.from_record(record)


def _xai_payload() -> dict[str, Any]:
    return {
        "model": "grok-4.6",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"predictions":[]}'},
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 250,
            "total_tokens": 1250,
        },
    }


@dataclass(slots=True)
class _FixtureTransport:
    payload: dict[str, Any]
    requests: list[urllib.request.Request] = field(default_factory=lambda: [])

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        del timeout_seconds
        self.requests.append(request)
        return self.payload

    def only_request(self) -> urllib.request.Request:
        assert len(self.requests) == 1
        return self.requests[0]


def _json_body(request: urllib.request.Request) -> dict[str, Any]:
    data = request.data
    assert isinstance(data, bytes)
    payload: object = json.loads(data.decode("utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)

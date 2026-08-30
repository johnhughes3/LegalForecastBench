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
from typing import Any, cast

import pytest
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelResponseError,
    LiveModelSolver,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.openai_compatible_provider import (
    XAI_API_KEY_ENV,
    XAI_CHAT_COMPLETIONS_URL,
    XAI_PROVIDER,
    openai_compatible_provider,
    openai_compatible_provider_names,
)

XAI_ENV = {XAI_API_KEY_ENV: "xai-secret"}


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
        assert isinstance(spec.reasoning_tokens_are_additive, bool)
        assert spec.chat_completions_url.startswith("https://")


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

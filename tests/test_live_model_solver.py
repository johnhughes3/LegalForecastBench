from __future__ import annotations

import hashlib
import json
import re
import socket
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.evals.live_model_solver as live_model_solver
import pytest
from legalforecast.evals.inspect_task import SolverKind
from legalforecast.evals.live_model_solver import (
    ANTHROPIC_MESSAGES_URL,
    GEMINI_GENERATE_CONTENT_URL_TEMPLATE,
    OPENAI_FALLBACK_SERVICE_TIER,
    OPENAI_FLEX_TIMEOUT_SECONDS,
    OPENAI_RESPONSES_URL,
    OPENAI_SERVICE_TIER,
    LiveModelConfigError,
    LiveModelProviderError,
    LiveModelResponseError,
    LiveModelSolver,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.tools import ControlledDocketEntry, ControlledDocketTool


def test_openai_solver_posts_responses_request_and_maps_usage() -> None:
    transport = _FixtureTransport(
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
    )

    request = _request("Predict the case outcome.")
    response = solver.solve(request)

    assert solver.solver_id == "openai:gpt-test"
    assert solver.solver_kind is SolverKind.INSPECT_AI
    assert response.raw_output == '{"predictions":[]}'
    assert response.request_count == 1
    assert response.input_tokens == 1000
    assert response.output_tokens == 250
    assert abs(response.estimated_cost - 0.0005) < 0.000000000001
    assert request.docket_tool.call_count == 2
    assert response.metadata is not None
    assert response.metadata["provider"] == "openai"
    assert response.metadata["model"] == "gpt-test"
    assert response.metadata["model_id"] == "gpt-test"
    assert response.metadata["model_version_or_snapshot"] == "gpt-test-2026-05-14"
    assert response.metadata["served_model_version"] == "gpt-test-2026-05-14"
    assert response.metadata["context_limit"] == "200000"
    assert response.metadata["max_output_tokens"] == "4096"
    assert response.metadata["prompt_input_token_budget"] == "195904"
    assert response.metadata["temperature"] == "0"
    assert response.metadata["service_tier"] == OPENAI_SERVICE_TIER
    assert response.metadata["requested_service_tier"] == OPENAI_SERVICE_TIER
    assert "service_tier_fallback" not in response.metadata
    assert response.metadata["execution_backend"] == "inspect_ai"
    assert response.metadata["model_registry_sha256"] == "unrecorded"
    assert response.metadata["tool_policy"] == "controlled_docket_tool_only"
    assert float(response.metadata["latency_ms"]) >= 0

    captured = transport.only_request()
    assert captured.full_url == OPENAI_RESPONSES_URL
    assert captured.get_method() == "POST"
    assert captured.headers["Authorization"] == "Bearer openai-secret"
    assert transport.timeouts == [OPENAI_FLEX_TIMEOUT_SECONDS]
    body = _json_body(captured)
    assert body == {
        "model": "gpt-test",
        "input": body["input"],
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "service_tier": OPENAI_SERVICE_TIER,
        "tools": [],
    }
    assert body["input"].startswith("Controlled docket tool transcript:")
    assert "Predict the case outcome." in body["input"]
    assert "read_docket_entry_results" in body["input"]


def test_openai_solver_refuses_actual_payload_that_differs_from_commitment() -> None:
    """The manifest commitment must gate the post-transformation HTTP prompt."""

    attempt_handler_requests: list[Any] = []

    def record_attempt_handler_request(request: Any) -> Any:
        attempt_handler_requests.append(request)
        raise AssertionError("spend handler constructed for a refused prompt")

    transport = _FixtureTransport(
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        attempt_handler_factory=record_attempt_handler_request,
    )
    prompt = "Predict the case outcome."

    with pytest.raises(
        LiveModelConfigError,
        match="actual provider prompt does not match",
    ):
        solver.solve(
            _request(
                prompt,
                committed_prompt_sha256=hashlib.sha256(
                    prompt.encode("utf-8")
                ).hexdigest(),
            )
        )

    assert transport.requests == []
    assert attempt_handler_requests == []


def test_openai_solver_no_docket_sends_exact_committed_prompt() -> None:
    """The official --no-docket-tool mode must preserve the frozen prompt bytes."""

    transport = _FixtureTransport(
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
    )
    prompt = "Predict the case outcome without docket tools."
    request = _request(
        prompt,
        use_docket_tool=False,
        committed_prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )

    solver.solve(request)

    assert _json_body(transport.only_request())["input"] == prompt
    assert request.docket_tool.call_count == 0


def test_openai_solver_keeps_caller_timeout_above_flex_floor() -> None:
    transport = _FixtureTransport(
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        timeout_seconds=1_200.0,
    )

    solver.solve(_request("Predict the case outcome."))

    assert transport.timeouts == [1_200.0]


def test_anthropic_solver_posts_messages_request_and_maps_content() -> None:
    transport = _FixtureTransport(
        {
            "model": "claude-test-2026-05-14",
            "content": [{"type": "text", "text": '{"anthropic":true}'}],
            "usage": {"input_tokens": 200, "output_tokens": 40},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("anthropic", "claude-test"),
        transport=transport,
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
    )

    request = _request("Use the benchmark packet.")
    response = solver.solve(request)

    assert response.raw_output == '{"anthropic":true}'
    assert request.docket_tool.call_count == 2
    assert response.input_tokens == 200
    assert response.output_tokens == 40
    assert abs(response.estimated_cost - 0.00009) < 0.000000000001

    captured = transport.only_request()
    assert captured.full_url == ANTHROPIC_MESSAGES_URL
    assert captured.headers["X-api-key"] == "anthropic-secret"
    assert captured.headers["Anthropic-version"] == "2023-06-01"
    assert transport.timeouts == [120.0]
    assert "service_tier" not in response.metadata
    body = _json_body(captured)
    assert body == {
        "model": "claude-test",
        "messages": [{"role": "user", "content": body["messages"][0]["content"]}],
        "max_tokens": 4096,
        "temperature": 0,
        "tools": [],
    }
    assert "top_p" not in body
    assert body["messages"][0]["content"].startswith(
        "Controlled docket tool transcript:"
    )
    assert "Use the benchmark packet." in body["messages"][0]["content"]


@pytest.mark.parametrize("model_id", ("claude-sonnet-5", "claude-opus-4-8"))
def test_anthropic_thinking_models_omit_sampling_controls_but_preserve_registry_policy(
    model_id: str,
) -> None:
    transport = _FixtureTransport(
        {
            "model": model_id,
            "content": [{"type": "text", "text": '{"thinking_model":true}'}],
            "usage": {"input_tokens": 200, "output_tokens": 40},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            model_id,
            model_version_or_snapshot=model_id,
        ),
        model_registry_sha256="cycle-1-registry-sha256",
        transport=transport,
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
    )

    response = solver.solve(_request("Use the benchmark packet."))

    body = _json_body(transport.only_request())
    assert "temperature" not in body
    assert "top_p" not in body
    assert "top_k" not in body
    assert body["tools"] == []
    assert response.metadata is not None
    assert "temperature" not in response.metadata
    assert "top_p" not in response.metadata
    assert response.metadata["registry_temperature"] == "0"
    assert response.metadata["registry_top_p"] == "1"
    assert response.metadata["provider_sampling_policy"] == "provider_default"
    assert response.metadata["served_model_version"] == model_id
    assert response.metadata["model_registry_sha256"] == "cycle-1-registry-sha256"


def test_anthropic_solver_can_use_bedrock_runtime_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_bedrock(
        model_id: str,
        payload: live_model_solver.JsonRecord,
        *,
        environ: Mapping[str, str] | None,
        timeout_seconds: float,
    ) -> live_model_solver.JsonRecord:
        assert environ == {"LFB_ANTHROPIC_RUNTIME": "bedrock"}
        assert timeout_seconds == 120.0
        payload_dict = dict(payload)
        calls.append((model_id, payload_dict))
        return {
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": '{"bedrock":true}'}],
            "usage": {"input_tokens": 220, "output_tokens": 55},
        }

    monkeypatch.setattr(
        live_model_solver,
        "_invoke_bedrock_runtime_json",
        fake_bedrock,
    )

    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            "claude-sonnet-4-6",
            model_version_or_snapshot="claude-sonnet-4-6",
        ),
        environ={"LFB_ANTHROPIC_RUNTIME": "bedrock"},
    )

    response = solver.solve(_request("Use AWS Bedrock."))

    assert response.raw_output == '{"bedrock":true}'
    assert response.input_tokens == 220
    assert response.output_tokens == 55
    assert abs(response.estimated_cost - 0.00011) < 0.000000000001
    assert response.metadata is not None
    assert response.metadata["provider"] == "anthropic"
    assert response.metadata["provider_runtime"] == "bedrock"
    assert response.metadata["bedrock_model_id"] == "us.anthropic.claude-sonnet-4-6"
    assert response.metadata["served_model_version"] == "claude-sonnet-4-6"

    assert len(calls) == 1
    model_id, body = calls[0]
    assert model_id == "us.anthropic.claude-sonnet-4-6"
    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": body["messages"][0]["content"][0]["text"],
                    }
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0,
    }
    assert body["messages"][0]["content"][0]["text"].startswith(
        "Controlled docket tool transcript:"
    )
    assert "Use AWS Bedrock." in body["messages"][0]["content"][0]["text"]


def test_bedrock_malformed_response_marks_authorized_attempt_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _RecordingAttemptHandler()

    monkeypatch.setattr(
        live_model_solver,
        "_invoke_bedrock_runtime_json",
        lambda *args, **kwargs: {
            "model": "claude-sonnet-4-6",
            "usage": {"input_tokens": 220, "output_tokens": 55},
        },
    )

    with pytest.raises(LiveModelResponseError):
        live_model_solver.complete_live_prompt(
            _registry_entry(
                "anthropic",
                "claude-sonnet-4-6",
                model_version_or_snapshot="claude-sonnet-4-6",
            ),
            "Use AWS Bedrock.",
            environ={"LFB_ANTHROPIC_RUNTIME": "bedrock"},
            attempt_handler=handler,
        )

    assert handler.events == [
        ("run", 1),
        ("post_response_failure", 41, "LiveModelResponseError"),
    ]


def test_sonnet_5_legacy_bedrock_fails_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_bedrock(*args: object, **kwargs: object) -> None:
        pytest.fail("legacy Bedrock transport must not be invoked for Sonnet 5")

    monkeypatch.setattr(
        live_model_solver, "_invoke_bedrock_runtime_json", unexpected_bedrock
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            "claude-sonnet-5",
            model_version_or_snapshot="claude-sonnet-5",
        ),
        model_registry_sha256="cycle-1-registry-sha256",
        environ={"LFB_ANTHROPIC_RUNTIME": "bedrock"},
    )

    with pytest.raises(
        LiveModelConfigError,
        match=(
            r"claude-sonnet-5.*LFB_ANTHROPIC_RUNTIME='bedrock'.*"
            r"unset LFB_ANTHROPIC_RUNTIME"
        ),
    ):
        solver.solve(_request("Use AWS Bedrock."))


def test_sonnet_5_legacy_bedrock_error_names_legacy_runtime_env_var() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            "claude-sonnet-5",
            model_version_or_snapshot="claude-sonnet-5",
        ),
        environ={"ANTHROPIC_RUNTIME": "bedrock"},
    )

    with pytest.raises(
        LiveModelConfigError,
        match=(
            r"claude-sonnet-5.*ANTHROPIC_RUNTIME='bedrock'.*"
            r"unset ANTHROPIC_RUNTIME"
        ),
    ):
        solver.solve(_request("Use legacy AWS Bedrock."))


@pytest.mark.parametrize(
    "model_id",
    (
        "anthropic.claude-sonnet-5",
        "us.anthropic.claude-sonnet-5",
        "arn:aws:bedrock:us-east-1:123456789012:foundation-model/anthropic.claude-sonnet-5",
    ),
)
def test_sonnet_5_legacy_bedrock_override_ids_fail_closed(model_id: str) -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            "claude-sonnet-5",
            model_version_or_snapshot="claude-sonnet-5",
        ),
        environ={
            "LFB_ANTHROPIC_RUNTIME": "bedrock",
            "LFB_ANTHROPIC_BEDROCK_MODEL_ID": model_id,
        },
    )

    with pytest.raises(LiveModelConfigError, match=re.escape(model_id)):
        solver.solve(_request("Use AWS Bedrock."))


def test_gemini_solver_posts_generate_content_request_and_maps_usage() -> None:
    transport = _FixtureTransport(
        {
            "modelVersion": "models/gemini-test-2026-05-14",
            "candidates": [{"content": {"parts": [{"text": '{"gemini":true}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 300,
                "candidatesTokenCount": 60,
            },
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("google", "gemini-test"),
        transport=transport,
        environ={"GEMINI_API_KEY": "gemini-secret"},
    )

    request = _request("Return JSON.")
    response = solver.solve(request)

    assert response.raw_output == '{"gemini":true}'
    assert request.docket_tool.call_count == 2
    assert response.input_tokens == 300
    assert response.output_tokens == 60
    assert abs(response.estimated_cost - 0.000135) < 0.000000000001

    captured = transport.only_request()
    assert captured.full_url == GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(
        model="gemini-test"
    )
    assert captured.headers["X-goog-api-key"] == "gemini-secret"
    assert transport.timeouts == [120.0]
    assert "service_tier" not in response.metadata
    body = _json_body(captured)
    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": body["contents"][0]["parts"][0]["text"]}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "topP": 1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
        "tools": [],
    }
    assert body["contents"][0]["parts"][0]["text"].startswith(
        "Controlled docket tool transcript:"
    )
    assert "Return JSON." in body["contents"][0]["parts"][0]["text"]


def test_complete_live_prompt_passes_explicit_json_schema_only_to_gemini() -> None:
    transport = _FixtureTransport(
        {
            "modelVersion": "models/gemini-test-2026-05-14",
            "candidates": [{"content": {"parts": [{"text": '{"flags":[]}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 300,
                "candidatesTokenCount": 60,
            },
        }
    )
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"flags": {"type": "array", "items": {"type": "object"}}},
        "required": ["flags"],
        "additionalProperties": False,
    }

    complete_live_prompt(
        _registry_entry("google", "gemini-test"),
        "Return structured JSON.",
        transport=transport,
        environ={"GEMINI_API_KEY": "gemini-secret"},
        response_json_schema=schema,
    )

    body = _json_body(transport.only_request())
    assert body["generationConfig"]["responseJsonSchema"] == schema


def test_complete_live_prompt_rejects_json_schema_for_unsupported_provider() -> None:
    with pytest.raises(LiveModelConfigError, match="only supported for Google Gemini"):
        complete_live_prompt(
            _registry_entry("openai", "gpt-test"),
            "Return structured JSON.",
            environ={"OPENAI_API_KEY": "openai-secret"},
            response_json_schema={"type": "object"},
        )


@pytest.mark.parametrize(
    ("provider", "model_id", "payload", "environ", "path_fragment"),
    (
        (
            "openai",
            "gpt-test",
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"openai":true}',
                "output": [{"type": "web_search_call", "status": "completed"}],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
            {"OPENAI_API_KEY": "openai-secret"},
            "web_search_call",
        ),
        (
            "anthropic",
            "claude-test",
            {
                "model": "claude-test-2026-05-14",
                "content": [
                    {"type": "server_tool_use", "name": "web_search"},
                    {"type": "text", "text": '{"anthropic":true}'},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
            {"ANTHROPIC_API_KEY": "anthropic-secret"},
            "server_tool_use",
        ),
        (
            "google",
            "gemini-test",
            {
                "modelVersion": "models/gemini-test-2026-05-14",
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"gemini":true}'}]},
                        "groundingMetadata": {"webSearchQueries": ["law"]},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 2,
                },
            },
            {"GEMINI_API_KEY": "gemini-secret"},
            "groundingMetadata",
        ),
    ),
)
def test_solver_flags_grounding_artifacts_from_provider_payloads(
    provider: str,
    model_id: str,
    payload: dict[str, Any],
    environ: dict[str, str],
    path_fragment: str,
) -> None:
    response = LiveModelSolver(
        registry_entry=_registry_entry(provider, model_id),
        transport=_FixtureTransport(payload),
        environ=environ,
    ).solve(_request("prompt"))

    assert response.metadata is not None
    assert response.metadata["response_grounding_artifacts_detected"] == "true"
    paths = json.loads(response.metadata["response_grounding_artifact_paths"])
    assert any(path_fragment in path for path in paths)


def test_solver_does_not_flag_empty_optional_grounding_metadata() -> None:
    response = LiveModelSolver(
        registry_entry=_registry_entry("google", "gemini-test"),
        transport=_FixtureTransport(
            {
                "modelVersion": "models/gemini-test-2026-05-14",
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"gemini":true}'}]},
                        "groundingMetadata": {},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 2,
                },
            }
        ),
        environ={"GEMINI_API_KEY": "gemini-secret"},
    ).solve(_request("prompt"))

    assert response.metadata is not None
    assert response.metadata["response_grounding_artifacts_detected"] == "false"
    assert response.metadata["response_grounding_artifact_paths"] == "[]"


def test_solver_records_retryable_truncated_finish_reason() -> None:
    response = LiveModelSolver(
        registry_entry=_registry_entry("anthropic", "claude-test"),
        transport=_FixtureTransport(
            {
                "model": "claude-test-2026-05-14",
                "content": [{"type": "text", "text": '{"partial":'}],
                "stop_reason": "max_tokens",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
        ),
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
    ).solve(_request("prompt"))

    assert response.metadata is not None
    assert response.metadata["response_finish_reason"] == "max_tokens"
    assert response.metadata["response_truncated"] == "true"
    assert response.metadata["response_retryable_ops_event"] == "true"
    assert (
        response.metadata["response_retryable_ops_event_reason"]
        == "response_truncated:max_tokens"
    )


def test_solver_records_content_filtered_finish_reason() -> None:
    response = LiveModelSolver(
        registry_entry=_registry_entry("google", "gemini-test"),
        transport=_FixtureTransport(
            {
                "modelVersion": "models/gemini-test-2026-05-14",
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"blocked":true}'}]},
                        "finishReason": "SAFETY",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 2,
                },
            }
        ),
        environ={"GEMINI_API_KEY": "gemini-secret"},
    ).solve(_request("prompt"))

    assert response.metadata is not None
    assert response.metadata["response_finish_reason"] == "SAFETY"
    assert response.metadata["response_content_filter"] == "true"


def test_solver_rejects_registry_entries_that_allow_model_network_or_search() -> None:
    record = _registry_record("openai", "gpt-test")
    record["network_disabled"] = False

    with pytest.raises(LiveModelConfigError, match="network_disabled"):
        LiveModelSolver(registry_entry=ModelRegistryEntry.from_record(record))

    record = _registry_record("openai", "gpt-test")
    record["search_disabled"] = False

    with pytest.raises(LiveModelConfigError, match="search_disabled"):
        LiveModelSolver(registry_entry=ModelRegistryEntry.from_record(record))


def test_solver_requires_the_matching_provider_api_key() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport({"output_text": "{}"}),
        environ={},
    )

    with pytest.raises(LiveModelConfigError, match="OPENAI_API_KEY"):
        solver.solve(_request("prompt"))


def test_solver_rejects_prompt_that_exceeds_registry_context_budget() -> None:
    transport = _FixtureTransport(
        {
            "model": "gpt-test-2026-05-14",
            "output_text": "{}",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "openai",
            "gpt-test",
            context_limit=32,
            max_output_tokens=8,
        ),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
    )

    with pytest.raises(LiveModelConfigError, match="prompt input tokens exceed"):
        solver.solve(_request("x" * 500))
    assert transport.requests == []


def test_solver_rejects_provider_served_model_version_mismatch() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport(
            {
                "model": "gpt-test-latest",
                "output_text": "{}",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        ),
        environ={"OPENAI_API_KEY": "openai-secret"},
    )

    with pytest.raises(LiveModelResponseError, match="did not match frozen registry"):
        solver.solve(_request("prompt"))


def test_anthropic_bedrock_model_override_must_match_registry() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry(
            "anthropic",
            "claude-sonnet-4-6",
            model_version_or_snapshot="claude-sonnet-4-6",
        ),
        environ={
            "LFB_ANTHROPIC_RUNTIME": "bedrock",
            "LFB_ANTHROPIC_BEDROCK_MODEL_ID": "us.anthropic.claude-opus-4-6",
        },
    )

    with pytest.raises(LiveModelConfigError, match="Bedrock model-ID override"):
        solver.solve(_request("prompt"))


def test_solver_rejects_malformed_provider_output() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry("anthropic", "claude-test"),
        transport=_FixtureTransport({"content": []}),
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
    )

    with pytest.raises(LiveModelResponseError, match="text content"):
        solver.solve(_request("prompt"))


def test_solver_retries_transient_provider_failures_without_leaving_flex() -> None:
    transport = _RetryTransport(
        (
            LiveModelProviderError(
                "provider returned HTTP 500: internal server error",
                status_code=500,
            ),
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"predictions":[]}',
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            },
        )
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        retry_backoff_seconds=0,
    )

    response = solver.solve(_request("prompt"))

    assert response.request_count == 2
    assert response.metadata is not None
    assert response.metadata["provider_attempt_count"] == "2"
    assert response.metadata["service_tier"] == OPENAI_SERVICE_TIER
    assert "service_tier_fallback" not in response.metadata
    assert [_json_body(item)["service_tier"] for item in transport.requests] == [
        OPENAI_SERVICE_TIER,
        OPENAI_SERVICE_TIER,
    ]
    assert len(transport.requests) == 2
    assert transport.timeouts == [
        OPENAI_FLEX_TIMEOUT_SECONDS,
        OPENAI_FLEX_TIMEOUT_SECONDS,
    ]


@pytest.mark.parametrize("status_code", (429, 503))
def test_openai_flex_falls_back_to_standard_on_capacity_errors(
    status_code: int,
) -> None:
    transport = _RetryTransport(
        (
            LiveModelProviderError(
                f"provider returned HTTP {status_code}: resource unavailable",
                status_code=status_code,
            ),
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"predictions":[]}',
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            },
        )
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        retry_backoff_seconds=0,
    )

    response = solver.solve(_request("prompt"))

    assert response.request_count == 2
    assert response.metadata is not None
    assert response.metadata["service_tier"] == OPENAI_FALLBACK_SERVICE_TIER
    assert response.metadata["requested_service_tier"] == OPENAI_SERVICE_TIER
    assert response.metadata["service_tier_fallback"] == "flex_unavailable"
    assert [_json_body(item)["service_tier"] for item in transport.requests] == [
        OPENAI_SERVICE_TIER,
        OPENAI_FALLBACK_SERVICE_TIER,
    ]


@pytest.mark.parametrize(
    "transport_error",
    (
        TimeoutError("read timed out"),
        socket.gaierror(-2, "Name or service not known"),
    ),
)
def test_default_transport_retries_raw_timeout_and_dns_failures(
    monkeypatch: pytest.MonkeyPatch,
    transport_error: OSError,
) -> None:
    outcomes: list[BaseException | _UrlResponse] = [
        transport_error,
        _UrlResponse(
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"predictions":[]}',
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            }
        ),
    ]

    def fake_urlopen(*_args: Any, **_kwargs: Any) -> _UrlResponse:
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        environ={"OPENAI_API_KEY": "openai-secret"},
        retry_backoff_seconds=0,
    )

    response = solver.solve(_request("prompt"))

    assert response.request_count == 2
    assert outcomes == []


def test_solver_does_not_retry_nonrecoverable_credit_failures() -> None:
    transport = _RetryTransport(
        (
            LiveModelProviderError(
                "provider returned HTTP 429: insufficient_quota credit balance",
                status_code=429,
            ),
        )
    )
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        retry_backoff_seconds=0,
    )

    with pytest.raises(LiveModelProviderError, match="insufficient_quota"):
        solver.solve(_request("prompt"))
    assert len(transport.requests) == 1
    assert _json_body(transport.requests[0])["service_tier"] == OPENAI_SERVICE_TIER


def test_solver_creates_attempt_handler_per_harness_request_and_settles() -> None:
    first_request = _request("first prompt")
    second_request = _request("second prompt")
    observed_requests: list[object] = []
    handlers: list[_RecordingAttemptHandler] = []

    def make_handler(item: object) -> _RecordingAttemptHandler:
        observed_requests.append(item)
        handler = _RecordingAttemptHandler()
        handlers.append(handler)
        return handler

    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport(
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"predictions":[]}',
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            }
        ),
        environ={"OPENAI_API_KEY": "openai-secret"},
        attempt_handler_factory=make_handler,
    )

    solver.solve(first_request)
    solver.solve(second_request)

    assert observed_requests == [first_request, second_request]
    assert len(handlers) == 2
    assert handlers[0] is not handlers[1]
    assert handlers[0].events[0] == ("run", 1)
    assert handlers[0].events[1][:4] == ("settle", 41, 1000, 250)
    assert handlers[1].events[0] == ("run", 1)
    assert handlers[1].events[1][:4] == ("settle", 41, 1000, 250)


def test_malformed_response_marks_authorized_attempt_ambiguous() -> None:
    handler = _RecordingAttemptHandler()
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport(
            {
                "model": "gpt-test-2026-05-14",
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            }
        ),
        environ={"OPENAI_API_KEY": "openai-secret"},
        attempt_handler_factory=lambda _request: handler,
    )

    with pytest.raises(LiveModelResponseError):
        solver.solve(_request("prompt"))

    assert handler.events == [
        ("run", 1),
        ("post_response_failure", 41, "LiveModelResponseError"),
    ]


def test_post_response_recording_failure_surfaces_as_authority_failure() -> None:
    class FailingRecordHandler(_RecordingAttemptHandler):
        def record_post_response_failure(
            self,
            durable_attempt_ordinal: int,
            *,
            failure_type: str,
        ) -> None:
            raise RuntimeError("durable failure recording unavailable")

    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport(
            {
                "model": "gpt-test-2026-05-14",
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            }
        ),
        environ={"OPENAI_API_KEY": "openai-secret"},
        attempt_handler_factory=lambda _request: FailingRecordHandler(),
    )

    with pytest.raises(
        RuntimeError,
        match="durable failure recording unavailable",
    ) as exc_info:
        solver.solve(_request("prompt"))

    assert isinstance(exc_info.value.__context__, LiveModelResponseError)


@pytest.mark.parametrize("interruption_type", [KeyboardInterrupt, SystemExit])
def test_post_response_interrupt_marks_authorized_attempt_ambiguous_before_reraise(
    monkeypatch: pytest.MonkeyPatch,
    interruption_type: type[BaseException],
) -> None:
    handler = _RecordingAttemptHandler()

    def interrupt_after_response(_payload: live_model_solver.JsonRecord) -> str:
        raise interruption_type

    monkeypatch.setattr(live_model_solver, "_openai_output", interrupt_after_response)
    solver = LiveModelSolver(
        registry_entry=_registry_entry("openai", "gpt-test"),
        transport=_FixtureTransport(
            {
                "model": "gpt-test-2026-05-14",
                "output_text": '{"predictions":[]}',
                "usage": {"input_tokens": 1000, "output_tokens": 250},
            }
        ),
        environ={"OPENAI_API_KEY": "openai-secret"},
        attempt_handler_factory=lambda _request: handler,
    )

    with pytest.raises(interruption_type):
        solver.solve(_request("prompt"))

    assert handler.events == [
        ("run", 1),
        ("post_response_failure", 41, interruption_type.__name__),
    ]


@dataclass(slots=True)
class _FixtureTransport:
    payload: dict[str, Any]
    requests: list[urllib.request.Request] = field(default_factory=lambda: [])
    timeouts: list[float] = field(default_factory=lambda: [])

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.timeouts.append(timeout_seconds)
        self.requests.append(request)
        return self.payload

    def only_request(self) -> urllib.request.Request:
        assert len(self.requests) == 1
        return self.requests[0]


@dataclass(slots=True)
class _RetryTransport:
    outcomes: tuple[dict[str, Any] | BaseException, ...]
    requests: list[urllib.request.Request] = field(default_factory=lambda: [])
    timeouts: list[float] = field(default_factory=lambda: [])

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.timeouts.append(timeout_seconds)
        self.requests.append(request)
        outcome = self.outcomes[len(self.requests) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass(slots=True)
class _RecordingAttemptHandler:
    events: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Any,
    ) -> Mapping[str, object]:
        self.events.append(("run", attempt_ordinal))
        return cast(Mapping[str, object], call())

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        self.events.append(
            (
                "settle",
                attempt_ordinal,
                input_tokens,
                output_tokens,
                actual_cost_usd,
                raw_output,
            )
        )

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        return local_ordinal + 40

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        self.events.append(
            ("post_response_failure", durable_attempt_ordinal, failure_type)
        )


@dataclass(slots=True)
class _UrlResponse:
    payload: dict[str, Any]

    def __enter__(self) -> _UrlResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _request(
    prompt: str,
    *,
    use_docket_tool: bool = True,
    committed_prompt_sha256: str | None = None,
) -> Any:
    docket_tool = ControlledDocketTool(
        case_id="case-test",
        entries=(
            ControlledDocketEntry(
                entry_number=1,
                docket_text="Complaint and motion briefing text.",
                source_document_ids=("doc-1",),
                description="complaint",
            ),
        ),
        allowed_entry_numbers=(1,),
        max_tool_calls=3,
    )
    return SimpleNamespace(
        sample=SimpleNamespace(
            prompt=prompt,
            use_docket_tool=use_docket_tool,
            committed_prompt_sha256=committed_prompt_sha256,
        ),
        docket_tool=docket_tool,
    )


def _json_body(request: urllib.request.Request) -> dict[str, Any]:
    data = request.data
    assert isinstance(data, bytes)
    payload: object = json.loads(data.decode("utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _registry_entry(
    provider: str,
    model_id: str,
    *,
    model_version_or_snapshot: str | None = None,
    context_limit: int = 200000,
    max_output_tokens: int = 4096,
) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        _registry_record(
            provider,
            model_id,
            model_version_or_snapshot=model_version_or_snapshot,
            context_limit=context_limit,
            max_output_tokens=max_output_tokens,
        )
    )


def _registry_record(
    provider: str,
    model_id: str,
    *,
    model_version_or_snapshot: str | None = None,
    context_limit: int = 200000,
    max_output_tokens: int = 4096,
) -> dict[str, object]:
    return {
        "provider": provider,
        "model_id": model_id,
        "display_name": f"{provider} {model_id}",
        "model_version_or_snapshot": (
            model_version_or_snapshot or f"{model_id}-2026-05-14"
        ),
        "release_timestamp": "2026-05-14T09:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": max_output_tokens,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": context_limit,
        "pricing_source": "provider-price-sheet-2026-05-14",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }

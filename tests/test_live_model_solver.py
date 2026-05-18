from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.evals.inspect_task import SolverKind
from legalforecast.evals.live_model_solver import (
    ANTHROPIC_MESSAGES_URL,
    GEMINI_GENERATE_CONTENT_URL_TEMPLATE,
    OPENAI_RESPONSES_URL,
    LiveModelConfigError,
    LiveModelResponseError,
    LiveModelSolver,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.tools import ControlledDocketEntry, ControlledDocketTool


def test_openai_solver_posts_responses_request_and_maps_usage() -> None:
    transport = _FixtureTransport(
        {
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
    assert response.metadata["model_version_or_snapshot"] == "2026-05-14"
    assert response.metadata["execution_backend"] == "inspect_ai"
    assert response.metadata["model_registry_sha256"] == "unrecorded"
    assert response.metadata["tool_policy"] == "controlled_docket_tool_only"
    assert float(response.metadata["latency_ms"]) >= 0

    captured = transport.only_request()
    assert captured.full_url == OPENAI_RESPONSES_URL
    assert captured.get_method() == "POST"
    assert captured.headers["Authorization"] == "Bearer openai-secret"
    body = _json_body(captured)
    assert body == {
        "model": "gpt-test",
        "input": body["input"],
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "tools": [],
    }
    assert body["input"].startswith("Controlled docket tool transcript:")
    assert "Predict the case outcome." in body["input"]
    assert "read_docket_entry_results" in body["input"]


def test_anthropic_solver_posts_messages_request_and_maps_content() -> None:
    transport = _FixtureTransport(
        {
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
    body = _json_body(captured)
    assert body == {
        "model": "claude-test",
        "messages": [{"role": "user", "content": body["messages"][0]["content"]}],
        "max_tokens": 4096,
        "temperature": 0,
        "top_p": 1,
        "tools": [],
    }
    assert body["messages"][0]["content"].startswith(
        "Controlled docket tool transcript:"
    )
    assert "Use the benchmark packet." in body["messages"][0]["content"]


def test_gemini_solver_posts_generate_content_request_and_maps_usage() -> None:
    transport = _FixtureTransport(
        {
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
        },
        "tools": [],
    }
    assert body["contents"][0]["parts"][0]["text"].startswith(
        "Controlled docket tool transcript:"
    )
    assert "Return JSON." in body["contents"][0]["parts"][0]["text"]


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


def test_solver_rejects_malformed_provider_output() -> None:
    solver = LiveModelSolver(
        registry_entry=_registry_entry("anthropic", "claude-test"),
        transport=_FixtureTransport({"content": []}),
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
    )

    with pytest.raises(LiveModelResponseError, match="text content"):
        solver.solve(_request("prompt"))


@dataclass(slots=True)
class _FixtureTransport:
    payload: dict[str, Any]
    requests: list[urllib.request.Request] = field(default_factory=lambda: [])

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        assert timeout_seconds == 120.0
        self.requests.append(request)
        return self.payload

    def only_request(self) -> urllib.request.Request:
        assert len(self.requests) == 1
        return self.requests[0]


def _request(prompt: str) -> Any:
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
        sample=SimpleNamespace(prompt=prompt),
        docket_tool=docket_tool,
    )


def _json_body(request: urllib.request.Request) -> dict[str, Any]:
    data = request.data
    assert isinstance(data, bytes)
    payload: object = json.loads(data.decode("utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _registry_entry(provider: str, model_id: str) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(_registry_record(provider, model_id))


def _registry_record(provider: str, model_id: str) -> dict[str, object]:
    return {
        "provider": provider,
        "model_id": model_id,
        "display_name": f"{provider} {model_id}",
        "model_version_or_snapshot": "2026-05-14",
        "release_timestamp": "2026-05-14T09:00:00Z",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "provider-price-sheet-2026-05-14",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }

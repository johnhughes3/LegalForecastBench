"""Every supplied response schema reaches the provider as native structured output.

2026-10-01: OpenAI and Anthropic refused ``response_json_schema``, so callers
sent it only to Gemini and the other judges read the schema as prompt prose
(gpt-6.1-sol answered an enum field as a JSON list on 1,929 of 3,116 findings).
These tests pin the outgoing request body for each provider.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

import legalforecast.evals.live_model_solver as live_model_solver
import pytest
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelProviderError,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.structured_output import openai_strict_json_schema
from legalforecast.openai_transport import (
    OPENAI_SERVICE_TIER,
    VERCEL_AI_GATEWAY_RESPONSES_URL,
    resolve_openai_transport,
)

FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["merits", "procedural"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "notes": {"type": "string"},
                },
                "required": ["kind", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

OPENAI_PAYLOAD: dict[str, Any] = {
    "model": "gpt-test-2026-05-14",
    "output_text": '{"findings":[]}',
    "service_tier": OPENAI_SERVICE_TIER,
    "status": "completed",
    "usage": {"input_tokens": 10, "output_tokens": 2},
}
ANTHROPIC_PAYLOAD: dict[str, Any] = {
    "model": "claude-test-2026-05-14",
    "content": [{"type": "text", "text": '{"findings":[]}'}],
    "usage": {"input_tokens": 10, "output_tokens": 2},
}


@dataclass(slots=True)
class _Transport:
    outcomes: list[dict[str, Any] | BaseException]
    requests: list[urllib.request.Request] = field(default_factory=lambda: [])

    def __call__(
        self, request: urllib.request.Request, timeout_seconds: float
    ) -> dict[str, Any]:
        del timeout_seconds
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _body(request: urllib.request.Request) -> dict[str, Any]:
    assert isinstance(request.data, bytes)
    return cast(dict[str, Any], json.loads(request.data))


def _entry(provider: str, model_id: str) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": provider,
            "model_id": model_id,
            "display_name": f"{provider} {model_id}",
            "model_version_or_snapshot": f"{model_id}-2026-05-14",
            "release_timestamp": "2026-05-14T09:00:00Z",
            "release_timestamp_source": "fixture release note",
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
    )


def _openai_text_format(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "legalforecast_response",
            "schema": openai_strict_json_schema(schema),
            "strict": True,
        }
    }


def test_openai_request_carries_the_schema_as_strict_text_format() -> None:
    transport = _Transport([OPENAI_PAYLOAD])

    complete_live_prompt(
        _entry("openai", "gpt-test"),
        "Return findings.",
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        response_json_schema=FINDINGS_SCHEMA,
    )

    (request,) = transport.requests
    assert _body(request)["text"] == _openai_text_format(FINDINGS_SCHEMA)


def test_openai_strict_schema_requires_every_property_and_nulls_optional_ones() -> None:
    item = openai_strict_json_schema(FINDINGS_SCHEMA)["properties"]["findings"]["items"]

    assert item["required"] == ["kind", "confidence", "notes"]
    assert item["additionalProperties"] is False
    assert item["properties"]["kind"] == {
        "type": "string",
        "enum": ["merits", "procedural"],
    }
    assert item["properties"]["notes"] == {"type": ["string", "null"]}


def test_openai_strict_schema_nulls_optional_enum_and_ref_properties() -> None:
    schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["a", "b"]},
            "span": {"$ref": "#/$defs/span"},
        },
        "required": [],
        "additionalProperties": False,
        "$defs": {
            "span": {
                "type": "object",
                "properties": {"start": {"type": "integer"}},
                "required": ["start"],
            }
        },
    }

    strict = openai_strict_json_schema(schema)

    assert strict["properties"]["kind"] == {
        "type": ["string", "null"],
        "enum": ["a", "b", None],
    }
    assert strict["properties"]["span"] == {
        "anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]
    }
    assert strict["$defs"]["span"]["additionalProperties"] is False


def test_openai_schema_survives_retries_unchanged() -> None:
    transport = _Transport(
        [
            LiveModelProviderError("HTTP 500: internal", status_code=500),
            OPENAI_PAYLOAD,
        ]
    )

    complete_live_prompt(
        _entry("openai", "gpt-test"),
        "Return findings.",
        transport=transport,
        environ={"OPENAI_API_KEY": "openai-secret"},
        retry_backoff_seconds=0,
        response_json_schema=FINDINGS_SCHEMA,
    )

    assert len(transport.requests) == 2
    assert [_body(r)["text"] for r in transport.requests] == [
        _openai_text_format(FINDINGS_SCHEMA)
    ] * 2


def test_openai_vercel_gateway_request_carries_the_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = resolve_openai_transport("gpt-5.6-sol", on_date_utc=date(2026, 9, 18))
    monkeypatch.setattr(
        live_model_solver,
        "resolve_openai_transport",
        lambda _, *, use_vercel_gateway=None: route,
    )
    transport = _Transport([{**OPENAI_PAYLOAD, "model": "gpt-5.6-sol-2026-05-14"}])

    complete_live_prompt(
        _entry("openai", "gpt-5.6-sol"),
        "Return findings.",
        transport=transport,
        environ={
            "OPENAI_API_KEY": "gateway-secret",
            "LFB_OPENAI_USE_VERCEL_GATEWAY": "true",
        },
        response_json_schema=FINDINGS_SCHEMA,
    )

    (request,) = transport.requests
    assert request.full_url == VERCEL_AI_GATEWAY_RESPONSES_URL
    assert _body(request)["text"] == _openai_text_format(FINDINGS_SCHEMA)


def test_anthropic_request_carries_the_schema_as_output_config_format() -> None:
    transport = _Transport([ANTHROPIC_PAYLOAD])

    complete_live_prompt(
        _entry("anthropic", "claude-test"),
        "Return findings.",
        transport=transport,
        environ={"ANTHROPIC_API_KEY": "anthropic-secret"},
        response_json_schema=FINDINGS_SCHEMA,
    )

    (request,) = transport.requests
    output_format = _body(request)["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    item = output_format["schema"]["properties"]["findings"]["items"]
    # Anthropic rejects numeric bounds; the SDK transform moves them into the
    # description, and the caller's parser stays authoritative for them.
    assert "minimum" not in item["properties"]["confidence"]
    assert item["properties"]["kind"]["enum"] == ["merits", "procedural"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["kind", "confidence"]


def test_bedrock_anthropic_request_carries_the_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def fake_bedrock(
        model_id: str,
        payload: live_model_solver.JsonRecord,
        *,
        environ: Mapping[str, str] | None,
        timeout_seconds: float,
    ) -> live_model_solver.JsonRecord:
        del model_id, environ, timeout_seconds
        payloads.append(dict(payload))
        return {**ANTHROPIC_PAYLOAD, "model": "claude-sonnet-4-6"}

    monkeypatch.setattr(live_model_solver, "_invoke_bedrock_runtime_json", fake_bedrock)
    entry = ModelRegistryEntry.from_record(
        {
            **_entry("anthropic", "claude-sonnet-4-6").to_record(),
            "model_version_or_snapshot": "claude-sonnet-4-6",
        }
    )

    complete_live_prompt(
        entry,
        "Return findings.",
        environ={"LFB_ANTHROPIC_RUNTIME": "bedrock"},
        response_json_schema=FINDINGS_SCHEMA,
    )

    (payload,) = payloads
    assert payload["output_config"]["format"]["type"] == "json_schema"
    assert payload["output_config"]["format"]["schema"]["required"] == ["findings"]


def test_gemini_request_carries_the_schema_as_response_json_schema() -> None:
    transport = _Transport(
        [
            {
                "modelVersion": "models/gemini-test-2026-05-14",
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2},
            }
        ]
    )

    complete_live_prompt(
        _entry("google", "gemini-test"),
        "Return findings.",
        transport=transport,
        environ={"GEMINI_API_KEY": "gemini-secret"},
        response_json_schema=FINDINGS_SCHEMA,
    )

    (request,) = transport.requests
    generation = _body(request)["generationConfig"]
    assert generation["responseMimeType"] == "application/json"
    assert generation["responseJsonSchema"] == FINDINGS_SCHEMA


# OpenAI-compatible providers (xAI, DeepInfra) already send response_format
# json_schema strict:true; tests/test_openai_compatible_provider.py pins it.


@pytest.mark.parametrize(
    ("provider", "environ"),
    (
        ("openai", {"OPENAI_API_KEY": "secret"}),
        ("anthropic", {"ANTHROPIC_API_KEY": "secret"}),
    ),
)
@pytest.mark.parametrize(
    "schema",
    (
        {"type": "string", "enum": ["pass", "fail"]},
        {
            "type": "object",
            "properties": {"free": {"type": "object"}},
            "required": ["free"],
        },
        {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "additionalProperties": True,
        },
    ),
)
def test_schema_the_provider_cannot_enforce_strictly_fails_before_transport(
    provider: str,
    environ: dict[str, str],
    schema: dict[str, Any],
) -> None:
    transport = _Transport([OPENAI_PAYLOAD])

    with pytest.raises(LiveModelConfigError, match="strict structured output"):
        complete_live_prompt(
            _entry(provider, "model-test"),
            "Return findings.",
            transport=transport,
            environ=environ,
            response_json_schema=schema,
        )

    assert transport.requests == []

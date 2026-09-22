from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import httpx2
import legalforecast.jev.luna as luna
import pytest
from anthropic import AsyncAnthropic as RealAsyncAnthropic
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from openai import AsyncOpenAI as RealAsyncOpenAI

ROOT = Path(__file__).resolve().parents[1]
_BASE_REGISTRY = (
    ROOT / "model_registries/cycle-1-luna-summaries-one-shot-high-2026-09-22.json"
)


def _entry(provider: str, model_id: str, effort: str) -> ModelRegistryEntry:
    record = cast(list[dict[str, object]], json.loads(_BASE_REGISTRY.read_text()))[0]
    record.update(
        provider=provider,
        model_id=model_id,
        model_version_or_snapshot=model_id,
        display_name=f"{model_id} summary comparison {effort}",
        reasoning_effort=effort,
        pricing_source="fixture pricing",
        jev_input_mode="luna_summaries",
        jev_summaries_sha256="a" * 64,
    )
    return ModelRegistryEntry.from_record(record)


class _Case:
    request: Mapping[str, object] = {
        "state": {"case_id": "case-1", "record": "frozen summary state"},
        "questions": {
            "unit-a": {"type": "boolean", "question": "Is the motion granted?"},
            "unit-b": {"type": "boolean", "question": "Is the motion granted?"},
        },
    }
    unit_ids = ("unit-a", "unit-b")


class _SpendHandler:
    replayable_response: Mapping[str, object] | None = None

    def __init__(self) -> None:
        self.attempts = 0
        self.settlement: dict[str, object] | None = None
        self.failures: list[str] = []

    def run_attempt(self, attempt_ordinal: int, call: Any) -> Mapping[str, object]:
        assert attempt_ordinal == 1
        self.attempts += 1
        return call()

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        return local_ordinal

    def record_post_response_failure(
        self, durable_attempt_ordinal: int, *, failure_type: str
    ) -> None:
        assert durable_attempt_ordinal == 1
        self.failures.append(failure_type)

    def settle_attempt(
        self,
        durable_attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        assert durable_attempt_ordinal == 1
        self.settlement = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "actual_cost_usd": actual_cost_usd,
            "raw_output": raw_output,
        }


def _response_body(provider: str, model_id: str) -> dict[str, object]:
    predictions = [
        {"unit_id": "unit-a", "probability_fully_dismissed": 0.25},
        {"unit_id": "unit-b", "probability_fully_dismissed": 0.75},
    ]
    output_text = json.dumps({"predictions": predictions})
    if provider == "openai":
        return {
            "id": "resp_fixture",
            "object": "response",
            "created_at": 1_725_000_000,
            "model": model_id,
            "status": "completed",
            "output": [
                {
                    "id": "msg_fixture",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": output_text,
                            "annotations": [],
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 8,
                "total_tokens": 108,
            },
        }
    return {
        "id": "msg_fixture",
        "type": "message",
        "role": "assistant",
        "model": model_id,
        "content": [{"type": "text", "text": output_text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 8,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [item for nested in value.values() for item in _strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _strings(nested)]
    return []


def _use_anthropic_http_client(
    monkeypatch: pytest.MonkeyPatch,
    http_client: httpx2.AsyncClient,
    captured_kwargs: dict[str, object],
) -> None:
    original_init = RealAsyncAnthropic.__init__

    def client_init(self: RealAsyncAnthropic, *args: Any, **kwargs: Any) -> None:
        captured_kwargs.update(kwargs)
        kwargs["http_client"] = http_client
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(RealAsyncAnthropic, "__init__", client_init)


@pytest.mark.parametrize(
    ("provider", "model_id", "effort"),
    (
        ("openai", "gpt-5.6-luna", "none"),
        ("openai", "gpt-5.6-luna", "high"),
        ("openai", "gpt-6-sol", "high"),
        ("openai", "gpt-6-luna", "none"),
        ("anthropic", "claude-opus-5-5", "low"),
        ("anthropic", "claude-opus-5-5", "high"),
    ),
)
def test_summary_comparator_uses_one_native_no_tool_request_and_settles(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model_id: str,
    effort: str,
) -> None:
    entry = _entry(provider, model_id, effort)
    requests: list[dict[str, object]] = []
    request_headers: list[Mapping[str, str]] = []
    response_model = model_id

    async def response_handler(request: httpx2.Request) -> httpx2.Response:
        body = cast(dict[str, object], json.loads(await request.aread()))
        requests.append(body)
        request_headers.append(request.headers)
        return httpx2.Response(
            200,
            json=_response_body(provider, response_model),
            request=request,
        )

    base_url = (
        "https://api.openai.com/v1"
        if provider == "openai"
        else "https://api.anthropic.com"
    )
    http_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(response_handler),
        base_url=base_url,
    )
    client_kwargs: dict[str, object] = {}
    if provider == "openai":

        def client_factory(**kwargs: Any) -> RealAsyncOpenAI:
            client_kwargs.update(kwargs)
            return RealAsyncOpenAI(http_client=http_client, **kwargs)

        monkeypatch.setattr(luna, "AsyncOpenAI", client_factory)
        key_name = "OPENAI_API_KEY"
    else:
        _use_anthropic_http_client(monkeypatch, http_client, client_kwargs)
        key_name = "ANTHROPIC_API_KEY"

    spend = _SpendHandler()
    observed_bodies: list[bytes] = []
    response = luna.complete_luna_cell(
        entry,
        handler=cast(ProviderSpendAttemptHandler, spend),
        case=cast(Any, _Case()),
        transport=luna.default_live_model_transport,
        request_body_observer=observed_bodies.append,
        environ={key_name: "fixture-key"},
        registry_sha256="fixture-registry-sha256",
    )
    asyncio.run(http_client.aclose())

    assert client_kwargs["max_retries"] == 0
    assert spend.attempts == 1
    assert spend.failures == []
    assert spend.settlement is not None
    assert spend.settlement["input_tokens"] == 100
    assert spend.settlement["output_tokens"] == 8
    assert response.input_tokens == 100
    assert response.output_tokens == 8
    assert response.request_count == 1
    assert len(requests) == 1
    assert len(request_headers) == 1
    assert len(observed_bodies) == 1
    wire_request = requests[0]
    expected_packet = ARTIFACT_CANONICAL_JSON_V1.encode(
        {"state": _Case.request["state"], "questions": _Case.request["questions"]}
    ).decode()
    assert expected_packet in "\n".join(_strings(wire_request))
    assert "unit-a" in json.dumps(wire_request)
    assert "unit-b" in json.dumps(wire_request)
    assert wire_request["model"] == model_id
    assert wire_request.get("tools", []) == []
    if provider == "openai":
        assert request_headers[0]["authorization"] == "Bearer fixture-key"
    else:
        assert request_headers[0]["x-api-key"] == "fixture-key"

    if provider == "openai":
        assert wire_request["service_tier"] == "flex"
        reasoning = cast(dict[str, object], wire_request["reasoning"])
        assert reasoning["effort"] == effort
        if model_id == "gpt-5.6-luna":
            assert reasoning["context"] == "all_turns"
        assert "text" in wire_request
        assert response.metadata["requested_service_tier"] == "flex"
        assert response.metadata["execution_condition"] == (
            f"luna_summary_comparator_reasoning_{effort}"
            if model_id == "gpt-5.6-luna"
            else (
                f"openai_{model_id.replace('-', '_')}"
                f"_summary_comparator_reasoning_{effort}"
            )
        )
    else:
        assert "service_tier" not in wire_request
        assert "requested_service_tier" not in response.metadata
        assert wire_request["thinking"] == {"type": "adaptive"}
        output_config = cast(dict[str, object], wire_request["output_config"])
        assert output_config["effort"] == effort
        assert "format" in output_config
        assert "tools" not in wire_request
        assert response.metadata["execution_condition"] == (
            f"anthropic_{model_id.replace('-', '_')}"
            f"_summary_comparator_reasoning_{effort}"
        )
    assert response.metadata["served_model_version"] == model_id
    assert response.metadata["model_registry_sha256"] == "fixture-registry-sha256"
    assert response.metadata["provider_attempt_count"] == "1"
    settled_output = json.loads(response.raw_output)
    if provider == "openai" and model_id == "gpt-5.6-luna":
        assert settled_output["case_assessment"] == (
            "Luna estimated probabilities from the Jev summary packet; "
            "no generated rationale."
        )
    assert set(
        prediction["unit_id"] for prediction in settled_output["predictions"]
    ) == {"unit-a", "unit-b"}


def test_summary_comparator_rejects_anthropic_served_model_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = "anthropic"
    model_id = "claude-opus-5-5"
    entry = _entry(provider, model_id, "low")

    async def response_handler(request: httpx2.Request) -> httpx2.Response:
        await request.aread()
        return httpx2.Response(
            200,
            json=_response_body(provider, "claude-opus-5-5-unexpected"),
            request=request,
        )

    http_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(response_handler),
        base_url="https://api.anthropic.com",
    )

    _use_anthropic_http_client(monkeypatch, http_client, {})
    with pytest.raises(ValueError, match="differs from the frozen registry"):
        luna._sdk_call(  # pyright: ignore[reportPrivateUsage]
            ARTIFACT_CANONICAL_JSON_V1.encode(
                {"state": {"case_id": "case-1"}, "questions": {"unit-a": {}}}
            ),
            {"ANTHROPIC_API_KEY": "fixture-key"},
            entry,
        )
    asyncio.run(http_client.aclose())


def test_openai_sdk_metadata_is_canonicalizable_before_spend_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = "openai"
    model_id = "gpt-5.6-luna"
    entry = _entry(provider, model_id, "none")
    saved_payloads: list[bytes] = []

    async def response_handler(request: httpx2.Request) -> httpx2.Response:
        await request.aread()
        return httpx2.Response(
            200,
            json=_response_body(provider, model_id),
            request=request,
        )

    http_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(response_handler),
        base_url="https://api.openai.com/v1",
    )

    def client_factory(**kwargs: Any) -> RealAsyncOpenAI:
        return RealAsyncOpenAI(http_client=http_client, **kwargs)

    monkeypatch.setattr(luna, "AsyncOpenAI", client_factory)

    def persist_response(_lease: AttemptLease, response: Mapping[str, object]) -> None:
        saved_payloads.append(ARTIFACT_CANONICAL_JSON_V1.encode(response))

    key = ProviderSpendKey(
        cycle_id="cycle-1",
        provider=provider,
        account="fixture",
        stage="official-eval",
        model_key=entry.registry_key,
        case_id="case-1",
        ablation="full_packet",
        repeat_index=1,
    )
    policy = FrozenAttemptPolicy(
        reservation_ledger_sha256="f" * 64,
        max_billable_attempts=1,
        failure_threshold=3,
        failure_window_seconds=300,
    )
    authority = SqliteProviderSpendAuthority(
        tmp_path / "spend.sqlite3",
        authority_identity_sha256="9" * 64,
        cycle_id="cycle-1",
        provider=provider,
        account="fixture",
        cap_microusd=1_000_000,
        policy=policy,
    )
    try:
        handler = ProviderSpendAttemptHandler(
            authority=authority,
            key=key,
            reservation_microusd=100_000,
            response_observer=persist_response,
        )
        response = luna.complete_luna_cell(
            entry,
            handler=handler,
            case=cast(Any, _Case()),
            transport=luna.default_live_model_transport,
            request_body_observer=lambda _body: None,
            environ={"OPENAI_API_KEY": "fixture-key"},
            registry_sha256="fixture-registry-sha256",
        )
        snapshot = authority.snapshot()
    finally:
        authority.close()
        asyncio.run(http_client.aclose())

    assert response.request_count == 1
    assert len(saved_payloads) == 1
    persisted = json.loads(saved_payloads[0])
    provider_metadata = cast(dict[str, object], persisted["providerMetadata"])
    details = cast(dict[str, object], provider_metadata["provider_details"])
    assert details["timestamp"] == "2024-08-30T06:40:00Z"
    assert snapshot.settled_attempt_count == 1
    assert snapshot.ambiguous_attempt_count == 0
    assert snapshot.reserved_attempt_count == 0

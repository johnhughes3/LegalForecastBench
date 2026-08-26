from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.multiharness import tier0_production_factory
from legalforecast.multiharness.tier0_production_factory import (
    JUDGE_SETTINGS,
    REQUIRED_ANTHROPIC_SDK_VERSION,
    anthropic_messages_transport,
)


def test_anthropic_transport_uses_provider_default_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class _Messages:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="pass")],
                model="claude-sonnet-4-6",
                usage=SimpleNamespace(input_tokens=12, output_tokens=1),
                to_json=lambda: '{"ok":true}',
            )

    sdk = SimpleNamespace(
        __version__=REQUIRED_ANTHROPIC_SDK_VERSION,
        Anthropic=lambda *, api_key: SimpleNamespace(messages=_Messages()),
    )
    monkeypatch.setattr(tier0_production_factory, "import_module", lambda _: sdk)

    result = anthropic_messages_transport(
        api_key="stub-key",
        model="claude-sonnet-4-6",
        system="system",
        prompt="prompt",
        max_output_tokens=16,
    )

    assert result.verdict_text == "pass"
    assert calls[0] == {
        "model": "claude-sonnet-4-6",
        "max_tokens": 16,
        "system": "system",
        "messages": [{"role": "user", "content": "prompt"}],
    }
    assert "temperature" not in calls[0] and "top_p" not in calls[0]
    assert JUDGE_SETTINGS["provider_sampling_policy"] == "provider_default"
    assert "temperature" not in JUDGE_SETTINGS and "top_p" not in JUDGE_SETTINGS


def test_anthropic_v1_sdk_round_trips_frozen_messages_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterize the paid request shape against the pinned real SDK."""

    sdk = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")
    assert sdk.__version__ == REQUIRED_ANTHROPIC_SDK_VERSION
    seen: dict[str, Any] = {}

    def handler(request: Any) -> Any:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = {key.lower(): value for key, value in request.headers.items()}
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            request=request,
            json={
                "id": "msg_characterization",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "pass"}],
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 12, "output_tokens": 1},
            },
        )

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = sdk.Anthropic(api_key="fixture-key", http_client=http_client)
        monkeypatch.setattr(sdk, "Anthropic", lambda *, api_key: client)
        monkeypatch.setattr(tier0_production_factory, "import_module", lambda _: sdk)
        result = anthropic_messages_transport(
            api_key="fixture-key",
            model="claude-sonnet-4-6",
            system="system",
            prompt="prompt",
            max_output_tokens=16,
        )

    assert seen["method"] == "POST"
    assert str(seen["url"]).endswith("/v1/messages")
    assert seen["headers"]["x-api-key"] == "fixture-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"] == {
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "prompt"}],
        "model": "claude-sonnet-4-6",
        "system": "system",
    }
    assert result.verdict_text == "pass"
    assert result.resolved_model == "claude-sonnet-4-6"
    assert result.input_tokens == 12
    assert result.output_tokens == 1
    assert json.loads(result.raw_response)["id"] == "msg_characterization"

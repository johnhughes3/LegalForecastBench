from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.multiharness import tier0_production_factory
from legalforecast.multiharness.tier0_production_factory import (
    JUDGE_SETTINGS,
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
        __version__="0.116.0",
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

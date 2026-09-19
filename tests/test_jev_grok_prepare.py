from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.jev.packets import case_documents
from legalforecast.release import ForecastExecution, load_forecast_execution
from legalforecast.runner import issue_runner_fixture
from pydantic_ai.usage import RequestUsage


def _entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "vercel_ai_gateway",
            "model_id": "spacexai/grok-4.6",
            "display_name": "Grok 4.6 via Vercel AI Gateway",
            "model_version_or_snapshot": "spacexai/grok-4.6",
            "release_timestamp": "2026-08-12T00:00:00Z",
            "release_timestamp_source": "fixture",
            "provider_training_cutoff_status": "unknown",
            "reasoning_effort": "high",
            "max_output_tokens": 128000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 500000,
            "pricing_source": "fixture",
            "input_token_price": 2.0,
            "output_token_price": 6.0,
            "long_context_surcharge": {
                "threshold_input_tokens": 200000,
                "input_price_multiplier": 2.0,
                "output_price_multiplier": 2.0,
            },
            "known_cutoff_publicity_caveats": [],
        }
    )


def _execution(tmp_path: Path) -> ForecastExecution:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    return load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )


def _documents(execution: ForecastExecution) -> tuple[Any, ...]:
    return tuple(
        document
        for case in execution.release.cases
        for document in case_documents(
            execution,
            tuple(
                unit
                for unit in execution.release.prediction_units
                if unit.case_id == case.case_id
            ),
        )
    )


class _FakeResult:
    def __init__(self, output: object, usage: object) -> None:
        self.output = output
        self.usage = usage


class _FakeAgent:
    def __init__(self, owner: _FakeAgentFactory, model: object) -> None:
        self.owner = owner
        self.model = model

    def run_sync(self, prompt: str, *, usage_limits: object) -> _FakeResult:
        del usage_limits
        self.owner.prompts.append(prompt)
        self.owner.models.append(self.model)
        return _FakeResult(self.owner.output, self.owner.usage)


class _FakeAgentFactory:
    def __init__(self) -> None:
        self.output = "Faithful source summary."
        self.usage = RequestUsage(input_tokens=10, output_tokens=10)
        self.prompts: list[str] = []
        self.models: list[Any] = []
        self.kwargs: list[dict[str, object]] = []

    def __call__(self, model: object, **kwargs: object) -> _FakeAgent:
        self.kwargs.append(kwargs)
        return _FakeAgent(self, model)


def _model_settings(kwargs: Mapping[str, object]) -> Mapping[str, object]:
    value = kwargs.get("model_settings")
    if not isinstance(value, Mapping):
        raise AssertionError("summary agent settings are missing")
    return cast(Mapping[str, object], value)


def test_grok_gateway_summary_uses_xai_route_and_gateway_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    factory = _FakeAgentFactory()
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-gateway-key")

    result = prepare.prepare_summaries(
        execution,
        entry=_entry(),
        cache_path=tmp_path / "grok-summaries.json",
        ledger_path=tmp_path / "grok-ledger.sqlite3",
        ceiling_microusd=20_000_000,
    )

    documents = _documents(execution)
    assert result["created"] == len(documents)
    assert result["reused"] == 0
    assert len(factory.prompts) == len(documents)
    assert all(model.provider.client.max_retries == 0 for model in factory.models)
    assert all(
        str(model.provider.client.base_url).startswith(
            "https://ai-gateway.vercel.sh/v1"
        )
        for model in factory.models
    )
    assert all(
        _model_settings(kwargs)["extra_body"]
        == {"providerOptions": {"gateway": {"only": ["xai"]}}}
        for kwargs in factory.kwargs
    )
    assert all(
        _model_settings(kwargs)["openai_reasoning_effort"] == "high"
        for kwargs in factory.kwargs
    )
    assert all(
        kwargs["instructions"] == prepare.SUMMARY_INSTRUCTIONS
        for kwargs in factory.kwargs
    )
    cache_records = json.loads((tmp_path / "grok-summaries.json").read_text())[
        "records"
    ]
    assert all(
        record["model"] == "spacexai/grok-4.6"
        for documents_by_case in cache_records.values()
        for record in documents_by_case.values()
    )

    with sqlite3.connect(tmp_path / "grok-ledger.sqlite3") as connection:
        providers = {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT provider FROM provider_attempts"
            ).fetchall()
        }
    assert providers == {"vercel_ai_gateway"}

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.jev.packets import case_documents
from legalforecast.release import ForecastExecution, load_forecast_execution
from legalforecast.runner import issue_runner_fixture
from pydantic_ai.usage import RequestUsage


def _entry(*, surcharge_threshold: int = 272_000) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "openai",
            "model_id": "gpt-5.6-luna",
            "display_name": "GPT-5.6 Luna",
            "model_version_or_snapshot": "gpt-5.6-luna",
            "release_timestamp": "2026-06-26T00:00:00Z",
            "release_timestamp_source": "fixture",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-02-16",
            "reasoning_effort": "high",
            "max_output_tokens": 16000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1_050_000,
            "pricing_source": "fixture",
            "input_token_price": 1.0,
            "output_token_price": 6.0,
            "long_context_surcharge": {
                "threshold_input_tokens": surcharge_threshold,
                "input_price_multiplier": 2.0,
                "output_price_multiplier": 1.5,
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
    def __init__(self, *, output: object, usage: object) -> None:
        self.output = output
        self.usage = usage
        self.prompts: list[str] = []
        self.models: list[Any] = []

    def __call__(self, model: object, **kwargs: object) -> _FakeAgent:
        del kwargs
        return _FakeAgent(self, model)


def _attempt_counts(ledger_path: Path) -> tuple[int, int, list[str]]:
    with sqlite3.connect(ledger_path) as connection:
        attempts = int(
            connection.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
        )
        failures = int(
            connection.execute(
                "SELECT COUNT(*) FROM provider_failure_events"
            ).fetchone()[0]
        )
        statuses = [
            str(row[0])
            for row in connection.execute(
                "SELECT status FROM provider_attempts ORDER BY attempt_id"
            ).fetchall()
        ]
    return attempts, failures, statuses


def test_nonpositive_ceiling_fails_before_cache_or_ledger(
    tmp_path: Path,
) -> None:
    execution = _execution(tmp_path)
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"

    with pytest.raises(ValueError, match="positive integer"):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=0,
        )

    assert not cache_path.exists()
    assert not ledger_path.exists()


def test_cached_documents_are_reused_without_provider_purchase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    entry = _entry()
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    expected = len(_documents(execution))
    factory = _FakeAgentFactory(
        output="Faithful source summary.",
        usage=RequestUsage(input_tokens=10, output_tokens=5),
    )
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    first = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=100_000_000,
    )

    def fail_if_called(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("cached summaries must not construct an agent")

    monkeypatch.setattr(prepare, "Agent", fail_if_called)
    result = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=100_000_000,
    )

    assert result == {
        "created": 0,
        "reused": expected,
        "spent_microusd": first["spent_microusd"],
    }
    assert _attempt_counts(ledger_path) == (expected, 0, ["settled"] * expected)


def test_summary_uses_whole_document_no_sdk_retries_and_long_context_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    entry = _entry(surcharge_threshold=1)
    factory = _FakeAgentFactory(
        output="Faithful source summary.",
        usage=RequestUsage(input_tokens=10, output_tokens=10),
    )
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"

    result = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=100_000_000,
    )

    documents = _documents(execution)
    assert result["created"] == len(documents)
    assert result["reused"] == 0
    expected_per_call = math.ceil(10 * 2.0 + 10 * 9.0)
    assert result["spent_microusd"] == expected_per_call * len(documents)
    assert len(factory.prompts) == len(documents)
    assert documents[0].text.strip() in factory.prompts[0]
    assert all(model.provider.client.max_retries == 0 for model in factory.models)


def test_oversized_paid_summary_is_persisted_and_not_repurchased(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    entry = _entry()
    factory = _FakeAgentFactory(
        output="x" * 4_000,
        usage=RequestUsage(input_tokens=10, output_tokens=10),
    )
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"

    with pytest.raises(ValueError, match="exceeds its byte budget"):
        prepare.prepare_summaries(
            execution,
            entry=entry,
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=100_000_000,
        )
    assert len(factory.prompts) == 1

    def fail_if_called(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("an oversized paid summary must be reused for refusal")

    monkeypatch.setattr(prepare, "Agent", fail_if_called)
    with pytest.raises(ValueError, match="exceeds its byte budget"):
        prepare.prepare_summaries(
            execution,
            entry=entry,
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=100_000_000,
        )

    assert _attempt_counts(ledger_path) == (1, 0, ["settled"])


def test_cached_summary_recovers_a_crash_before_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    entry = _entry()
    factory = _FakeAgentFactory(
        output="Faithful source summary.",
        usage=RequestUsage(input_tokens=10, output_tokens=5),
    )
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    original_settle = prepare.ProviderSpendAttemptHandler.settle_attempt
    crashed = False

    def crash_once(
        self: Any,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        nonlocal crashed
        if not crashed:
            crashed = True
            raise RuntimeError("simulated settlement crash")
        original_settle(
            self,
            attempt_ordinal,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=actual_cost_usd,
            raw_output=raw_output,
        )

    monkeypatch.setattr(
        prepare.ProviderSpendAttemptHandler, "settle_attempt", crash_once
    )
    with pytest.raises(RuntimeError, match="simulated settlement crash"):
        prepare.prepare_summaries(
            execution,
            entry=entry,
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=100_000_000,
        )
    assert _attempt_counts(ledger_path) == (1, 0, ["reserved"])

    monkeypatch.setattr(
        prepare.ProviderSpendAttemptHandler, "settle_attempt", original_settle
    )
    factory.prompts.clear()
    result = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=100_000_000,
    )

    expected = len(_documents(execution))
    assert result["created"] == expected - 1
    assert result["reused"] == 1
    assert len(factory.prompts) == expected - 1
    assert _attempt_counts(ledger_path) == (expected, 0, ["settled"] * expected)


def test_invalid_paid_response_is_journaled_as_ambiguous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    factory = _FakeAgentFactory(
        output=object(),
        usage=RequestUsage(input_tokens=10, output_tokens=10),
    )
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")

    with pytest.raises(ValueError, match="response payload is invalid"):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=tmp_path / "summaries.json",
            ledger_path=tmp_path / "ledger.sqlite3",
            ceiling_microusd=100_000_000,
        )

    assert _attempt_counts(tmp_path / "ledger.sqlite3") == (1, 1, ["ambiguous"])

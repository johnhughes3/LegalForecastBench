from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_control import (
    AttemptLimitExceededError,
    AttemptStateError,
    AuthorityIdentityMismatchError,
    ProviderCapExceededError,
)
from legalforecast.jev.packets import case_documents
from legalforecast.jev.summaries import SHORT_SUMMARY_PROMPT_VERSION
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


class _FlakySummaryAgent:
    def __init__(self, *, failures: int = 1) -> None:
        self.calls = 0
        self.failures = failures

    def run_sync(self, prompt: str, *, usage_limits: object) -> _FakeResult:
        del prompt, usage_limits
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("transport result unknown")
        return _FakeResult(
            "Faithful source summary.",
            RequestUsage(input_tokens=10, output_tokens=10),
        )


def _ambiguous_attempt_id(ledger_path: Path) -> str:
    with sqlite3.connect(ledger_path) as connection:
        row = connection.execute(
            "SELECT attempt_id FROM provider_attempts WHERE status = 'ambiguous'"
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_exact_ambiguous_retry_retains_hold_then_reuses_settled_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    agent = _FlakySummaryAgent()
    monkeypatch.setattr(prepare, "_summary_agent", lambda *_args, **_kwargs: agent)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-gateway-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    ceiling = 20_000_000

    with pytest.raises(ConnectionError):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling,
            summary_profile="short",
        )
    attempt_id = _ambiguous_attempt_id(ledger_path)
    with pytest.raises(AttemptLimitExceededError):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling,
            summary_profile="short",
        )
    with pytest.raises(AttemptStateError):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling,
            summary_profile="short",
            retry_ambiguous_attempt_id="f" * 64,
        )
    assert agent.calls == 1

    result = prepare.prepare_summaries(
        execution,
        entry=_entry(),
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=ceiling,
        summary_profile="short",
        retry_ambiguous_attempt_id=attempt_id,
    )
    assert result["created"] == len(_documents(execution))
    assert agent.calls == len(_documents(execution)) + 1
    with sqlite3.connect(ledger_path) as connection:
        first_two = connection.execute(
            "SELECT attempt_ordinal, status, reservation_microusd, actual_microusd "
            "FROM provider_attempts WHERE logical_call_key = "
            "(SELECT logical_call_key FROM provider_attempts WHERE attempt_id = ?) "
            "ORDER BY attempt_ordinal",
            (attempt_id,),
        ).fetchall()
        failure_events = connection.execute(
            "SELECT COUNT(*) FROM provider_failure_events WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        cap = connection.execute(
            "SELECT cap_microusd FROM provider_spend_metadata"
        ).fetchone()
        cumulative = connection.execute(
            "SELECT SUM(CASE WHEN status = 'settled' THEN actual_microusd "
            "ELSE reservation_microusd END) FROM provider_attempts"
        ).fetchone()
    assert [(row[0], row[1]) for row in first_two] == [
        (1, "ambiguous"),
        (2, "settled"),
    ]
    assert first_two[0][2] > 0
    assert first_two[0][3] is None
    assert failure_events == (1,)
    assert cap == (ceiling,)
    assert cumulative == (result["spent_microusd"],)
    assert result["spent_microusd"] <= ceiling

    monkeypatch.setattr(
        prepare,
        "_summary_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("settled summaries must not call provider")
        ),
    )
    reused = prepare.prepare_summaries(
        execution,
        entry=_entry(),
        cache_path=cache_path,
        ledger_path=ledger_path,
        ceiling_microusd=ceiling,
        summary_profile="short",
        retry_ambiguous_attempt_id=attempt_id,
    )
    assert reused["reused"] == len(_documents(execution))
    assert reused["spent_microusd"] == result["spent_microusd"]


def test_exact_ambiguous_retry_respects_unchanged_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    agent = _FlakySummaryAgent()
    monkeypatch.setattr(prepare, "_summary_agent", lambda *_args, **_kwargs: agent)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-gateway-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    ceiling = 1_000_000
    with pytest.raises(ConnectionError):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling,
            summary_profile="short",
        )
    attempt_id = _ambiguous_attempt_id(ledger_path)
    with pytest.raises(ProviderCapExceededError):
        prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling,
            summary_profile="short",
            retry_ambiguous_attempt_id=attempt_id,
        )
    assert agent.calls == 1
    with sqlite3.connect(ledger_path) as connection:
        assert connection.execute(
            "SELECT status FROM provider_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone() == ("ambiguous",)


def test_failed_ambiguous_replacement_cannot_buy_a_third_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    agent = _FlakySummaryAgent(failures=2)
    monkeypatch.setattr(prepare, "_summary_agent", lambda *_args, **_kwargs: agent)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-gateway-key")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"

    def run(attempt_id: str | None = None) -> dict[str, int]:
        return prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=20_000_000,
            summary_profile="short",
            retry_ambiguous_attempt_id=attempt_id,
        )

    with pytest.raises(ConnectionError):
        run()
    attempt_id = _ambiguous_attempt_id(ledger_path)
    with pytest.raises(ConnectionError):
        run(attempt_id)
    with pytest.raises(AttemptStateError, match="already reserved or failed"):
        run(attempt_id)
    assert agent.calls == 2
    with sqlite3.connect(ledger_path) as connection:
        assert connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall() == [(1, "ambiguous"), (2, "ambiguous")]


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
    factory.usage = RequestUsage(input_tokens=10, output_tokens=15167)
    reservations: list[dict[str, Any]] = []
    reserve = prepare.conservative_reservation_microusd

    def capture_reservation(**kwargs: Any) -> int:
        reservations.append(kwargs)
        return reserve(**kwargs)

    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setattr(
        prepare,
        "conservative_reservation_microusd",
        capture_reservation,
    )
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
        _model_settings(kwargs)["max_tokens"] == 8192 for kwargs in factory.kwargs
    )
    assert reservations
    assert {item["max_output_tokens"] for item in reservations} == {128000}
    assert all(
        item["context_limit"] - item["max_output_tokens"] > 0 for item in reservations
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


def test_short_summary_profile_uses_full_sources_and_new_ledger_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    entry = _entry()
    factory = _FakeAgentFactory()
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-gateway-key")

    standard_cache = tmp_path / "standard-summaries.json"
    standard_ledger = tmp_path / "standard-ledger.sqlite3"
    prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=standard_cache,
        ledger_path=standard_ledger,
        ceiling_microusd=100_000_000,
    )
    standard_prompts = [json.loads(prompt) for prompt in factory.prompts]

    factory.prompts.clear()
    short_cache = tmp_path / "short-summaries.json"
    short_ledger = tmp_path / "short-ledger.sqlite3"
    result = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=short_cache,
        ledger_path=short_ledger,
        ceiling_microusd=100_000_000,
        summary_profile="short",
    )
    short_prompts = [json.loads(prompt) for prompt in factory.prompts]
    source_documents = _documents(execution)

    assert result["created"] == len(source_documents)
    assert result["reused"] == 0
    assert len(short_prompts) == len(standard_prompts) == len(source_documents)
    assert [prompt["text"] for prompt in short_prompts] == [
        document.text for document in source_documents
    ]
    assert all(
        short["maximum_summary_utf8_bytes"] < standard["maximum_summary_utf8_bytes"]
        for standard, short in zip(standard_prompts, short_prompts, strict=True)
    )
    assert all("brevity_instructions" in prompt for prompt in short_prompts)

    records = json.loads(short_cache.read_text())["records"]
    assert {
        summary["prompt_version"]
        for documents in records.values()
        for summary in documents.values()
    } == {SHORT_SUMMARY_PROMPT_VERSION}

    with sqlite3.connect(standard_ledger) as standard_db:
        standard_identity = standard_db.execute(
            "SELECT authority_identity_sha256 FROM provider_spend_metadata"
        ).fetchone()[0]
    with sqlite3.connect(short_ledger) as short_db:
        short_identity = short_db.execute(
            "SELECT authority_identity_sha256 FROM provider_spend_metadata"
        ).fetchone()[0]
    assert short_identity != standard_identity

    prompts_before_mismatch = len(factory.prompts)
    with pytest.raises(AuthorityIdentityMismatchError):
        prepare.prepare_summaries(
            execution,
            entry=entry,
            cache_path=standard_cache,
            ledger_path=standard_ledger,
            ceiling_microusd=100_000_000,
            summary_profile="short",
        )
    assert len(factory.prompts) == prompts_before_mismatch

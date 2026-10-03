from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import legalforecast.cli_commands.jev as jev_cli
import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.evals.provider_spend_control import AuthorityIdentityMismatchError
from tests.test_jev_grok_prepare import (
    _entry,  # pyright: ignore[reportPrivateUsage]
    _execution,  # pyright: ignore[reportPrivateUsage]
    _FakeAgentFactory,  # pyright: ignore[reportPrivateUsage]
)


def test_summary_resume_amends_budget_without_rebuying_cached_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _FakeAgentFactory()
    monkeypatch.setattr(prepare, "Agent", factory)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-key")
    execution = _execution(tmp_path)
    cache = tmp_path / "cache.json"
    ledger = tmp_path / "ledger.sqlite3"

    def run(cap: int, old: int | None = None) -> dict[str, int]:
        return prepare.prepare_summaries(
            execution,
            entry=_entry(),
            cache_path=cache,
            ledger_path=ledger,
            ceiling_microusd=cap,
            amend_cap_from_microusd=old,
            summary_profile="short",
        )

    first = run(20_000_000)
    saved = cache.read_bytes()
    requests = len(factory.prompts)
    with sqlite3.connect(ledger) as connection:
        attempts = connection.execute("SELECT * FROM provider_attempts").fetchall()
    with pytest.raises(AuthorityIdentityMismatchError):
        run(40_000_000)
    for _ in range(2):
        result = run(40_000_000, 20_000_000)
        assert result["created"] == 0
        assert result["reused"] == first["created"]
        assert cache.read_bytes() == saved
        assert len(factory.prompts) == requests
        with sqlite3.connect(ledger) as connection:
            assert (
                connection.execute("SELECT * FROM provider_attempts").fetchall()
                == attempts
            )
            assert connection.execute(
                "SELECT cap_microusd FROM provider_spend_metadata"
            ).fetchone() == (40_000_000,)


@pytest.mark.parametrize(
    ("option", "value", "expected_key"),
    [
        ("--amend-cap-from-microusd", "18003132", "amend_cap_from_microusd"),
        ("--retry-interrupted-attempt-id", "a" * 64, "retry_interrupted_attempt_id"),
    ],
)
def test_cli_forwards_explicit_summary_recovery(
    monkeypatch: pytest.MonkeyPatch, option: str, value: str, expected_key: str
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Prepare Jev Summaries")
    received: dict[str, object] = {}

    def capture(**kwargs: object) -> dict[str, int]:
        received.update(kwargs)
        return {"created": 0}

    monkeypatch.setattr(
        jev_cli,
        "load_forecast_run_inputs",
        lambda *a, **kw: SimpleNamespace(execution="fixture"),
    )
    monkeypatch.setattr(
        jev_cli,
        "load_model_registry",
        lambda *a: SimpleNamespace(get=lambda *a: _entry()),
    )
    monkeypatch.setattr(jev_cli, "prepare_summaries", capture)
    parser = argparse.ArgumentParser()
    jev_cli.register(parser.add_subparsers())
    assert (
        jev_cli.run_inputs(
            parser.parse_args(
                [
                    "jev",
                    "prepare",
                    "--manifest",
                    "manifest.json",
                    "--forecast",
                    "forecast.json",
                    "--artifact-root",
                    "artifacts",
                    "--summary-registry",
                    "registry.json",
                    "--cache",
                    "cache.json",
                    "--ledger",
                    "ledger.sqlite3",
                    "--summary-model",
                    "grok",
                    "--ceiling-microusd",
                    "38003132",
                    option,
                    value,
                    "--interrupted-source-run-id",
                    "42",
                ]
            )
        )
        == 0
    )
    assert received["interrupted_source_run_id"] == 42
    assert received["ceiling_microusd"] == 38_003_132
    assert received[expected_key] == (
        int(value) if option == "--amend-cap-from-microusd" else value
    )


def test_interrupted_paid_cli_refuses_local_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="protected preparation workflow"):
        jev_cli.run_inputs(argparse.Namespace(retry_interrupted_attempt_id="a" * 64))

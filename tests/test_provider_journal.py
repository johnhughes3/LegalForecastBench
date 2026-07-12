from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legalforecast.evals.live_model_solver import (
    LiveModelProviderError,
    _call_with_provider_retries,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderBudgetExceededError,
    ProviderCallIdentity,
)


def test_journal_replays_raw_response_without_reissuing_provider_call(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    calls = 0

    def provider() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"output_text": '{"unit_seeds":[]}', "request_id": "req-1"}

    with _journal(path) as journal:
        assert journal.run_attempt(1, provider)["request_id"] == "req-1"
        journal.settle_attempt(
            1,
            input_tokens=10,
            output_tokens=2,
            actual_cost_usd=0.01,
            raw_output='{"unit_seeds":[]}',
        )
        journal.commit_reconstruction({"prediction_units": []})

    with _journal(path) as replay:
        assert replay.run_attempt(1, provider)["request_id"] == "req-1"
        replay.settle_attempt(
            1,
            input_tokens=10,
            output_tokens=2,
            actual_cost_usd=0.01,
            raw_output='{"unit_seeds":[]}',
        )
        assert replay.stage_cost_total("llm-unitize") == pytest.approx(0.01)

    assert calls == 1
    with sqlite3.connect(path) as connection:
        [(prompt_text, raw, normalized, reconstructed)] = connection.execute(
            "SELECT prompt_text, raw_response_json, normalized_response_json, "
            "reconstructed_result_json FROM provider_attempts"
        ).fetchall()
    assert prompt_text == "frozen prompt"
    assert '"request_id":"req-1"' in raw
    assert '"input_tokens":10' in normalized
    assert reconstructed == '{"prediction_units":[]}'


def test_journal_recovers_response_received_before_settlement(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    calls = 0

    def provider() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"output_text": "{}", "request_id": "durable-before-crash"}

    with _journal(path) as journal:
        journal.run_attempt(1, provider)

    with _journal(path) as replay:
        payload = replay.run_attempt(1, provider)
        assert payload["request_id"] == "durable-before-crash"
        replay.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.02,
            raw_output="{}",
        )
        replay.commit_reconstruction({"prediction_units": []})

    assert calls == 1


def test_ambiguous_attempt_retains_reservation_and_blocks_cap(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path, reservation=0.6, cap=1.0) as journal:
        with pytest.raises(LiveModelProviderError):
            journal.run_attempt(
                1,
                lambda: _raise_provider_error(
                    LiveModelProviderError("timeout", retryable=True)
                ),
            )
        with pytest.raises(ProviderBudgetExceededError):
            journal.run_attempt(2, lambda: {"unexpected": True})

    with sqlite3.connect(path) as connection:
        [(status,)] = connection.execute(
            "SELECT status FROM provider_attempts"
        ).fetchall()
    assert status == "ambiguous"


def test_definite_failure_restarts_as_new_durable_attempt(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        with pytest.raises(LiveModelProviderError):
            journal.run_attempt(
                1,
                lambda: _raise_provider_error(
                    LiveModelProviderError(
                        "invalid request", status_code=400, retryable=False
                    )
                ),
            )

    with _journal(path) as replay:
        assert replay.run_attempt(1, lambda: {"request_id": "retry"}) == {
            "request_id": "retry"
        }
        replay.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        replay.commit_reconstruction({"prediction_units": []})

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "failed"), (2, "settled")]


def test_retry_replay_skips_ambiguous_prefix_and_preserves_attempt_count(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    calls = 0

    def flaky_provider() -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LiveModelProviderError("timeout", retryable=True)
        return {"request_id": "attempt-2"}

    with _journal(path, cap=1.0) as journal:
        payload, attempt_count = _call_with_provider_retries(
            flaky_provider,
            max_attempts=3,
            retry_backoff_seconds=0,
            attempt_handler=journal,
        )
        assert payload["request_id"] == "attempt-2"
        assert attempt_count == 2
        journal.settle_attempt(
            attempt_count,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.commit_reconstruction({"prediction_units": []})

    with _journal(path, cap=1.0) as replay:
        replayed, replay_attempt_count = _call_with_provider_retries(
            flaky_provider,
            max_attempts=3,
            retry_backoff_seconds=0,
            attempt_handler=replay,
        )
    assert replayed["request_id"] == "attempt-2"
    assert replay_attempt_count == 2
    assert calls == 2


def test_two_judges_have_distinct_candidate_model_call_rows(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    for model_key in ("openai:judge-a", "openai:judge-b"):
        with _journal(path, stage="llm-label", model_key=model_key) as journal:
            journal.run_attempt(1, lambda key=model_key: {"model_key": key})
            journal.settle_attempt(
                1,
                input_tokens=4,
                output_tokens=2,
                actual_cost_usd=0.03,
                raw_output="{}",
            )
            journal.commit_reconstruction({"labels": [{"unit_id": "unit-1"}]})

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT stage, candidate_id, model_key, attempt_ordinal "
            "FROM provider_attempts ORDER BY model_key"
        ).fetchall()
    assert rows == [
        ("llm-label", "cand-1", "openai:judge-a", 1),
        ("llm-label", "cand-1", "openai:judge-b", 1),
    ]


def _journal(
    path: Path,
    *,
    stage: str = "llm-unitize",
    model_key: str = "openai:judge-a",
    reservation: float = 0.1,
    cap: float = 1.0,
) -> ProviderAttemptJournal:
    return ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage=stage,
            candidate_id="cand-1",
            model_key=model_key,
            prompt="frozen prompt",
            model_registry_sha256="registry-sha256",
        ),
        provider="openai",
        reservation_usd=reservation,
        cycle_cap_usd=cap,
    )


def _raise_provider_error(error: LiveModelProviderError) -> dict[str, object]:
    raise error

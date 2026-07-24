from __future__ import annotations

import json
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
    ProviderJournalError,
    ProviderJournalReplayMismatchError,
    load_provider_cycle_caps,
)


def test_journal_closes_connection_when_pragma_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingConnection:
        closed = False
        row_factory: object = None

        def execute(self, statement: str) -> None:
            raise sqlite3.OperationalError(f"failed pragma: {statement}")

        def close(self) -> None:
            self.closed = True

    connection = FailingConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connection)

    with pytest.raises(sqlite3.OperationalError, match="failed pragma"):
        _journal(tmp_path / "provider-attempts.sqlite3")

    assert connection.closed is True


def test_provider_cycle_caps_load_externally_bounded_provider_caps(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(
        """{
          "schema_version": "legalforecast.provider_cycle_caps.v1",
          "cycle_id": "cycle-1",
          "providers": [{
            "provider": "openai",
            "cycle_reservation_cap_usd": "100.00",
            "external_spend_limit_usd": "215.00",
            "external_limit_scope": "organization monthly spend limit",
            "external_limit_source": "operator verification 2026-07-12",
            "verified_at": "2026-07-12T16:00:00Z"
          }]
        }"""
    )

    caps = load_provider_cycle_caps(path)

    assert caps.cycle_id == "cycle-1"
    assert caps.cap_usd("openai") == 100.0
    assert caps.cap_usd("OpenAI") == 100.0


def test_provider_cycle_caps_bind_prelabeling_remote_authority_policy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(
        """{
          "schema_version": "legalforecast.provider_cycle_caps.v1",
          "cycle_id": "cycle-1",
          "spend_authority": {
            "backend": "dynamodb",
            "resource_identity_sha256": "IDENTITY_SHA256",
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "max_billable_attempts": 2,
            "failure_threshold": 3,
            "failure_window_seconds": 300
          },
          "providers": [{
            "provider": "openai",
            "account": "primary",
            "cycle_reservation_cap_usd": "100.000001",
            "external_spend_limit_usd": "215.00",
            "external_limit_scope": "organization monthly spend limit",
            "external_limit_source": "operator verification 2026-07-12",
            "verified_at": "2026-07-12T16:00:00Z"
          }]
        }""".replace("IDENTITY_SHA256", "a" * 64)
    )

    caps = load_provider_cycle_caps(path)
    policy = caps.require_spend_authority()

    assert caps.account("OpenAI") == "primary"
    assert caps.cap_microusd("openai") == 100_000_001
    assert policy.backend == "dynamodb"
    assert policy.resource_identity_sha256 == "a" * 64
    assert policy.ledger_scope_fields == ("cycle_id", "provider", "account")
    assert policy.max_billable_attempts == 2
    assert policy.failure_threshold == 3
    assert policy.failure_window_seconds == 300
    assert caps.execution_attempt_policy("b" * 64) == {
        "authority_backend": "dynamodb",
        "authority_resource_identity_sha256": "a" * 64,
        "ledger_scope_fields": ["cycle_id", "provider", "account"],
        "provider_account_caps": [
            {
                "provider": "openai",
                "account": "primary",
                "cap_microusd": 100_000_001,
            }
        ],
        "reservation_ledger_sha256": "b" * 64,
        "max_billable_attempts": 2,
        "failure_threshold": 3,
        "failure_window_seconds": 300,
    }


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("artifact", "unexpected"),
        ("spend_authority", "table_arn"),
        ("provider", "aws_account_id"),
    ],
)
def test_provider_cycle_caps_reject_unknown_schema_keys(
    tmp_path: Path,
    location: str,
    field: str,
) -> None:
    payload = _remote_provider_caps_payload()
    if location == "artifact":
        payload[field] = "must-not-be-accepted"
    elif location == "spend_authority":
        spend_authority = payload["spend_authority"]
        assert isinstance(spend_authority, dict)
        spend_authority[field] = "must-not-be-accepted"
    else:
        providers = payload["providers"]
        assert isinstance(providers, list)
        provider = providers[0]
        assert isinstance(provider, dict)
        provider[field] = "must-not-be-accepted"
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProviderJournalError, match="keys mismatch"):
        load_provider_cycle_caps(path)


@pytest.mark.parametrize(
    "account",
    [
        "123456789012",
        "account-123456789012",
        "arn:aws:iam::123456789012:role/labeling",
        "primary account",
        " primary",
        "AKIAIOSFODNN7EXAMPLE",
        "sk-project-secret",
        "provider-token",
        "primary/secondary",
    ],
)
def test_provider_cycle_caps_reject_nonpublic_account_aliases(
    tmp_path: Path,
    account: str,
) -> None:
    payload = _remote_provider_caps_payload()
    providers = payload["providers"]
    assert isinstance(providers, list)
    provider = providers[0]
    assert isinstance(provider, dict)
    provider["account"] = account
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProviderJournalError, match="public account alias") as exc_info:
        load_provider_cycle_caps(path)

    assert account not in str(exc_info.value)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ('"backend": "sqlite"', "backend must be dynamodb"),
        (
            '"ledger_scope_fields": ["cycle_id", "provider", "account", "stage"]',
            "must share one ledger across stages",
        ),
        ('"max_billable_attempts": 0', "max_billable_attempts"),
    ],
)
def test_provider_cycle_caps_reject_unsafe_remote_authority_policy(
    tmp_path: Path,
    replacement: str,
    message: str,
) -> None:
    payload = """{
      "schema_version": "legalforecast.provider_cycle_caps.v1",
      "cycle_id": "cycle-1",
      "spend_authority": {
        "backend": "dynamodb",
        "resource_identity_sha256": "IDENTITY_SHA256",
        "ledger_scope_fields": ["cycle_id", "provider", "account"],
        "max_billable_attempts": 2,
        "failure_threshold": 3,
        "failure_window_seconds": 300
      },
      "providers": [{
        "provider": "openai",
        "account": "primary",
        "cycle_reservation_cap_usd": "100.00",
        "external_spend_limit_usd": "215.00",
        "external_limit_scope": "organization monthly spend limit",
        "external_limit_source": "operator verification 2026-07-12",
        "verified_at": "2026-07-12T16:00:00Z"
      }]
    }""".replace("IDENTITY_SHA256", "a" * 64)
    if replacement.startswith('"backend"'):
        payload = payload.replace('"backend": "dynamodb"', replacement)
    elif replacement.startswith('"ledger_scope_fields"'):
        payload = payload.replace(
            '"ledger_scope_fields": ["cycle_id", "provider", "account"]',
            replacement,
        )
    else:
        payload = payload.replace('"max_billable_attempts": 2', replacement)
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(payload)

    with pytest.raises(ProviderJournalError, match=message):
        load_provider_cycle_caps(path)


def test_legacy_provider_caps_cannot_be_used_as_remote_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(
        """{
          "schema_version": "legalforecast.provider_cycle_caps.v1",
          "cycle_id": "cycle-1",
          "providers": [{
            "provider": "openai",
            "cycle_reservation_cap_usd": "100.00",
            "external_spend_limit_usd": "215.00",
            "external_limit_scope": "organization monthly spend limit",
            "external_limit_source": "operator verification 2026-07-12",
            "verified_at": "2026-07-12T16:00:00Z"
          }]
        }"""
    )

    caps = load_provider_cycle_caps(path)

    with pytest.raises(ProviderJournalError, match="lacks spend_authority"):
        caps.require_spend_authority()
    with pytest.raises(ProviderJournalError, match="lacks account alias"):
        caps.account("openai")


def test_provider_cycle_caps_reject_cap_above_external_limit(tmp_path: Path) -> None:
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(
        """{
          "schema_version": "legalforecast.provider_cycle_caps.v1",
          "cycle_id": "cycle-1",
          "providers": [{
            "provider": "anthropic",
            "cycle_reservation_cap_usd": "200.01",
            "external_spend_limit_usd": "200.00",
            "external_limit_scope": "organization monthly spend limit",
            "external_limit_source": "operator verification 2026-07-12",
            "verified_at": "2026-07-12T16:00:00Z"
          }]
        }"""
    )

    with pytest.raises(ProviderJournalError, match="exceeds documented external"):
        load_provider_cycle_caps(path)


def test_provider_cycle_caps_reject_missing_provider(tmp_path: Path) -> None:
    path = tmp_path / "provider-cycle-caps.json"
    path.write_text(
        """{
          "schema_version": "legalforecast.provider_cycle_caps.v1",
          "cycle_id": "cycle-1",
          "providers": [{
            "provider": "openai",
            "cycle_reservation_cap_usd": "100",
            "external_spend_limit_usd": "215",
            "external_limit_scope": "organization monthly spend limit",
            "external_limit_source": "operator verification 2026-07-12",
            "verified_at": "2026-07-12T16:00:00Z"
          }]
        }"""
    )

    with pytest.raises(ProviderJournalError, match="no entry for 'google'"):
        load_provider_cycle_caps(path).cap_usd("google")


def _remote_provider_caps_payload() -> dict[str, object]:
    return {
        "schema_version": "legalforecast.provider_cycle_caps.v1",
        "cycle_id": "cycle-1",
        "spend_authority": {
            "backend": "dynamodb",
            "resource_identity_sha256": "a" * 64,
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "max_billable_attempts": 2,
            "failure_threshold": 3,
            "failure_window_seconds": 300,
        },
        "providers": [
            {
                "provider": "openai",
                "account": "primary",
                "cycle_reservation_cap_usd": "100.00",
                "external_spend_limit_usd": "215.00",
                "external_limit_scope": "organization monthly spend limit",
                "external_limit_source": "operator verification 2026-07-12",
                "verified_at": "2026-07-12T16:00:00Z",
            }
        ],
    }


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


def test_post_response_validation_failure_is_durable_and_retains_reservation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        journal.run_attempt(1, lambda: {"malformed": True})
        journal.record_post_response_failure(
            1,
            failure_type="LiveModelResponseError",
        )

    with sqlite3.connect(path) as connection:
        status, failure_type = connection.execute(
            "SELECT status, failure_type FROM provider_attempts"
        ).fetchone()
    assert (status, failure_type) == ("ambiguous", "LiveModelResponseError")


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


def test_journal_adopts_replayable_response_identity_after_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        journal.run_attempt(1, lambda: {"request_id": "durable-before-crash"})

    with _journal(path) as recovered:
        recovered.adopt_attempt(7)
        assert recovered.durable_attempt_ordinal(7) == 1


def test_journal_terminalizes_invalid_reconstruction_without_losing_accounting(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"

    with _journal(path) as journal:
        with pytest.raises(LiveModelProviderError):
            journal.run_attempt(
                1,
                lambda: _raise_provider_error(
                    LiveModelProviderError("timeout", retryable=True)
                ),
            )
        journal.run_attempt(2, lambda: {"output_text": "{}"})
        journal.settle_attempt(
            2,
            input_tokens=10,
            output_tokens=2,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.record_reconstruction_failure(ValueError("invalid schema"))
        assert journal.stage_cost_total("llm-unitize") == pytest.approx(0.01)

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd, failure_type "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows[0][:2] == (1, "ambiguous")
    assert rows[1][0:2] == (2, "reconstruction_failed")
    assert rows[1][2] == pytest.approx(0.01)
    assert rows[1][3] == "ValueError"

    with _journal(path) as retry:
        assert retry.run_attempt(1, lambda: {"request_id": "replacement"}) == {
            "output_text": "{}"
        }
        assert retry.durable_attempt_ordinal(1) == 2
        retry.settle_attempt(
            2,
            input_tokens=10,
            output_tokens=2,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        with pytest.raises(
            ProviderJournalError,
            match="reconstruction-failed provider accounting evidence changed",
        ):
            retry.settle_attempt(
                2,
                input_tokens=11,
                output_tokens=2,
                actual_cost_usd=0.01,
                raw_output="{}",
            )


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


def test_ambiguous_attempt_restarts_as_new_durable_attempt(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        with pytest.raises(LiveModelProviderError):
            journal.run_attempt(
                1,
                lambda: _raise_provider_error(
                    LiveModelProviderError("timeout", retryable=True)
                ),
            )

    with _journal(path) as replay:
        assert replay.run_attempt(1, lambda: {"request_id": "retry"}) == {
            "request_id": "retry"
        }
        assert replay.durable_attempt_ordinal(1) == 2


def test_non_provider_exception_is_ambiguous_and_never_reuses_reservation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        with pytest.raises(ValueError, match="invalid response"):
            journal.run_attempt(1, lambda: _raise_value_error("invalid response"))

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT status FROM provider_attempts WHERE attempt_ordinal = 1"
        ).fetchone() == ("ambiguous",)

    with _journal(path) as replay:
        replay.run_attempt(1, lambda: {"request_id": "fresh"})
        assert replay.durable_attempt_ordinal(1) == 2


def test_reserved_attempt_after_crash_is_never_reissued(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        journal._reserve(1)

    calls = 0

    def provider() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"request_id": "fresh"}

    with _journal(path) as replay:
        assert replay.run_attempt(1, provider)["request_id"] == "fresh"
        assert replay.durable_attempt_ordinal(1) == 2
    assert calls == 1

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "reserved"), (2, "response_received")]


def test_settle_attempt_rejects_missing_row_and_allows_settled_replay(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path) as journal:
        with pytest.raises(ProviderJournalError, match="does not exist"):
            journal.settle_attempt(
                1,
                input_tokens=1,
                output_tokens=1,
                actual_cost_usd=0.01,
                raw_output="{}",
            )
        journal.run_attempt(1, lambda: {"request_id": "first"})
        journal.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.commit_reconstruction({"prediction_units": []})
        journal.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )


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
        payload, request_count, durable_ordinal = _call_with_provider_retries(
            flaky_provider,
            max_attempts=3,
            retry_backoff_seconds=0,
            attempt_handler=journal,
        )
        assert payload["request_id"] == "attempt-2"
        assert request_count == 2
        assert durable_ordinal == 2
        journal.settle_attempt(
            durable_ordinal,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.commit_reconstruction({"prediction_units": []})

    with _journal(path, cap=1.0) as replay:
        replayed, replay_request_count, replay_durable_ordinal = (
            _call_with_provider_retries(
                flaky_provider,
                max_attempts=3,
                retry_backoff_seconds=0,
                attempt_handler=replay,
            )
        )
    assert replayed["request_id"] == "attempt-2"
    assert replay_request_count == 0
    assert replay_durable_ordinal == 2
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


def test_journal_rejects_changed_cycle_caps_or_canonical_path(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path):
        pass

    with pytest.raises(ProviderJournalReplayMismatchError, match="caps artifact"):
        _journal(path, caps_sha256="sha256:mutated")

    moved = tmp_path / "different-root" / "provider-attempts.sqlite3"
    moved.parent.mkdir()
    moved.write_bytes(path.read_bytes())
    with pytest.raises(ProviderJournalReplayMismatchError, match="canonical path"):
        _journal(moved)


def test_one_cycle_cap_is_shared_across_provider_stages(tmp_path: Path) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    with _journal(path, stage="llm-unitize", reservation=0.6, cap=1.0) as unitize:
        unitize.run_attempt(1, lambda: {"request_id": "unitize"})
        unitize.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.6,
            raw_output="{}",
        )
        unitize.commit_reconstruction({"prediction_units": []})

    with _journal(path, stage="llm-label", reservation=0.5, cap=1.0) as label:
        with pytest.raises(ProviderBudgetExceededError, match="cycle cap"):
            label.run_attempt(1, lambda: {"request_id": "must-not-run"})


def _journal(
    path: Path,
    *,
    stage: str = "llm-unitize",
    model_key: str = "openai:judge-a",
    reservation: float = 0.1,
    cap: float = 1.0,
    cycle_id: str = "cycle-1",
    caps_sha256: str = "sha256:frozen-caps",
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
        cycle_id=cycle_id,
        provider_cycle_caps_sha256=caps_sha256,
    )


def _raise_provider_error(error: LiveModelProviderError) -> dict[str, object]:
    raise error


def _raise_value_error(message: str) -> dict[str, object]:
    raise ValueError(message)

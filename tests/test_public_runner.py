from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from urllib.request import Request

import legalforecast.evals.live_model_solver as live_model_solver
import legalforecast.runner.service as runner_service
import pytest
from legalforecast.cli import main
from legalforecast.contracts import PUBLIC_RUN_RECEIPT_V1, RAW_BYTES_RAW_SHA256_V1
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelProviderError,
    LiveModelResponseError,
)
from legalforecast.evals.provider_spend_control import AttemptLimitExceededError
from legalforecast.immutable_io import ImmutableIOError
from legalforecast.runner import (
    RunBlockedError,
    RunConfig,
    RunIdentityError,
    RunValidationError,
    execute_release_run,
    issue_runner_fixture,
)
from legalforecast.runner.fixture import FIXTURE_MODEL_KEY, FixtureModelTransport

JsonRecord = Mapping[str, object]


class CountingTransport:
    def __init__(
        self,
        response: Callable[[Request], JsonRecord] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.calls = 0
        self._response = response or _valid_response
        self._error = error

    def __call__(self, request: Request, timeout_seconds: float) -> JsonRecord:
        del timeout_seconds
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._response(request)


def test_runner_fixture_is_byte_identical_and_create_only(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    issue_runner_fixture(first)
    issue_runner_fixture(second)

    assert _tree_payloads(first) == _tree_payloads(second)
    with pytest.raises(ImmutableIOError, match="output already exists"):
        issue_runner_fixture(first)


def test_run_cli_issues_and_executes_provider_free_three_case_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = tmp_path / "fixture"
    ledger = tmp_path / "run.sqlite3"
    receipts = tmp_path / "receipts"

    assert main(["run", "issue-fixture", "--output-dir", str(fixture)]) == 0
    issued = json.loads(capsys.readouterr().out)
    assert issued == {
        "forecast_release": str(fixture / "release" / "forecast-release.json"),
        "labels_release": str(fixture / "release" / "labels-release.json"),
        "model_key": FIXTURE_MODEL_KEY,
        "model_registry": str(fixture / "model-registry.json"),
    }

    (fixture / "release" / "labels-release.json").unlink()
    assert (
        main(
            [
                "run",
                "execute",
                "--forecast",
                str(fixture / "release" / "forecast-release.json"),
                "--artifact-root",
                str(fixture / "release"),
                "--model-registry",
                str(fixture / "model-registry.json"),
                "--model-key",
                FIXTURE_MODEL_KEY,
                "--ledger",
                str(ledger),
                "--receipts-dir",
                str(receipts),
                "--ceiling-microusd",
                "30000",
                "--approval-reference",
                "owner-approved-fixture",
                "--dry-run",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["completed_cells"] == 3
    assert summary["executed_cells"] == 3
    assert summary["resumed_cells"] == 0
    assert summary["status"] == "completed"
    assert len(tuple(receipts.glob("*.json"))) == 3


def test_run_cli_help_exposes_complete_release_only_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["run", "execute", "--help"])
    help_text = capsys.readouterr().out
    for option in (
        "--forecast",
        "--artifact-root",
        "--model-registry",
        "--model-key",
        "--ledger",
        "--receipts-dir",
        "--ceiling-microusd",
        "--approval-reference",
        "--harness",
        "--ablation",
        "--repeat-count",
        "--dry-run",
    ):
        assert option in help_text
    assert "labels" not in help_text.lower()


def test_runner_refuses_missing_approval_reference_before_creating_ledger(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, approval_reference="")

    with pytest.raises(RunValidationError, match="approval reference"):
        execute_release_run(config, transport=CountingTransport())

    assert not config.ledger_path.exists()


def test_runner_rejects_unauthenticated_ablation_before_creating_ledger(
    tmp_path: Path,
) -> None:
    config = replace(_config(tmp_path), ablation="metadata-only")
    transport = CountingTransport(error=AssertionError("transport called"))

    with pytest.raises(RunValidationError, match="authenticated release prompts"):
        execute_release_run(config, transport=transport)

    assert transport.calls == 0
    assert not config.ledger_path.exists()


def test_runner_rejects_unsupported_harness_before_creating_ledger(
    tmp_path: Path,
) -> None:
    config = replace(_config(tmp_path), harness="inspect")
    transport = CountingTransport(error=AssertionError("transport called"))

    with pytest.raises(RunValidationError, match="native harness"):
        execute_release_run(config, transport=transport)

    assert transport.calls == 0
    assert not config.ledger_path.exists()


def test_run_cli_rejects_unsupported_harness_before_creating_ledger(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "run",
                "execute",
                "--forecast",
                str(config.forecast_path),
                "--artifact-root",
                str(config.artifact_root),
                "--model-registry",
                str(config.model_registry_path),
                "--model-key",
                config.model_key,
                "--ledger",
                str(config.ledger_path),
                "--receipts-dir",
                str(config.receipts_dir),
                "--ceiling-microusd",
                str(config.ceiling_microusd),
                "--approval-reference",
                config.approval_reference,
                "--harness",
                "inspect",
            ]
        )

    assert not config.ledger_path.exists()


def test_runner_rejects_ineligible_model_before_creating_ledger(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    records = cast(
        list[dict[str, object]], json.loads(config.model_registry_path.read_bytes())
    )
    records[0]["release_timestamp"] = None
    config.model_registry_path.write_text(json.dumps(records), encoding="utf-8")
    transport = CountingTransport(error=AssertionError("transport called"))

    with pytest.raises(RunValidationError, match="official model eligibility"):
        execute_release_run(config, transport=transport)

    assert transport.calls == 0
    assert not config.ledger_path.exists()


def test_runner_rejects_packet_before_selected_model_release_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    units = (
        SimpleNamespace(
            case_id="case-001",
            unit_id="unit-001",
            prompt_sha256="1" * 64,
        ),
        SimpleNamespace(
            case_id="case-002",
            unit_id="unit-002",
            prompt_sha256="2" * 64,
        ),
    )
    release = SimpleNamespace(
        release_digest="3" * 64,
        release_id="release-anchor-regression",
        cases=(
            SimpleNamespace(case_id="case-001"),
            SimpleNamespace(case_id="case-002"),
        ),
        prediction_units=units,
    )

    class IneligibleExecution:
        def __init__(self) -> None:
            self.release = release

        def packet_bytes(self, unit_id: str) -> bytes:
            case_id = "case-001" if unit_id == "unit-001" else "case-002"
            decision_date = "2026-08-23" if unit_id == "unit-001" else "2026-08-22"
            return runner_service.ARTIFACT_CANONICAL_JSON_V1.encode(
                {
                    "case_id": case_id,
                    "decision_date": decision_date,
                    "unit_id": unit_id,
                }
            )

        def prompt_bytes(self, unit_id: str) -> bytes:
            raise AssertionError(f"prompt read for ineligible unit {unit_id}")

    monkeypatch.setattr(
        runner_service,
        "load_forecast_execution",
        lambda *_args, **_kwargs: IneligibleExecution(),
    )
    transport = CountingTransport(error=AssertionError("transport called"))

    with pytest.raises(RunValidationError, match="precedes model release anchor"):
        execute_release_run(config, transport=transport)

    assert transport.calls == 0
    assert not config.ledger_path.exists()


def test_runner_refuses_exact_ledger_identity_drift_without_transport(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    first_transport = FixtureModelTransport()
    execute_release_run(config, transport=first_transport, environ=_fixture_environ())
    assert first_transport.call_count == 3
    drifted = replace(config, account="different-account")
    second_transport = CountingTransport(error=AssertionError("transport reused"))

    with pytest.raises(RunIdentityError, match="ledger identity"):
        execute_release_run(
            drifted,
            transport=second_transport,
            environ=_fixture_environ(),
        )

    assert second_transport.calls == 0


def test_runner_falls_back_after_explicit_nonbillable_429(
    tmp_path: Path,
) -> None:
    class FlexFallbackTransport:
        def __init__(self) -> None:
            self.requests: list[Request] = []

        def __call__(self, request: Request, timeout_seconds: float) -> JsonRecord:
            del timeout_seconds
            self.requests.append(request)
            if len(self.requests) == 1:
                raise LiveModelProviderError(
                    "provider returned HTTP 429: flex unavailable",
                    status_code=429,
                    retryable=True,
                )
            response = dict(_valid_response(request))
            response["service_tier"] = "default"
            return response

    config = _config(tmp_path)
    transport = FlexFallbackTransport()

    summary = execute_release_run(
        config,
        transport=transport,
        environ=_fixture_environ(),
    )

    assert summary.executed_cells == 3
    assert summary.completed_cells == 3
    assert len(transport.requests) == 4
    assert [
        cast(str, _request_body(request)["service_tier"])
        for request in transport.requests
    ] == ["flex", "default", "flex", "flex"]
    first_cell_receipt = next(
        payload
        for payload in (
            json.loads(path.read_bytes()) for path in config.receipts_dir.glob("*.json")
        )
        if payload["unit_id"] == "unit-001"
    )
    fallback_body = cast(bytes, transport.requests[1].data)
    expected_request_sha256 = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            fallback_body,
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    assert first_cell_receipt["request_body_sha256"] == expected_request_sha256
    with sqlite3.connect(config.ledger_path) as connection:
        attempts = connection.execute(
            "SELECT attempt_id, attempt_ordinal, status FROM provider_attempts "
            "ORDER BY authorized_at_epoch, attempt_ordinal"
        ).fetchall()
        first_cell = connection.execute(
            "SELECT status, provider_attempt_id FROM public_runner_cells "
            "WHERE unit_id = 'unit-001'"
        ).fetchone()
    assert [attempt[1:] for attempt in attempts[:2]] == [
        (1, "failed_nonbillable"),
        (2, "settled"),
    ]
    assert first_cell == ("completed", attempts[1][0])
    resumed_transport = CountingTransport(error=AssertionError("fallback cell retried"))
    resumed = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )
    assert resumed.executed_cells == 0
    assert resumed.resumed_cells == 3
    assert resumed_transport.calls == 0


def test_runner_recovers_retryable_429_after_crash_before_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SimulatedCrash(BaseException):
        pass

    config = _config(tmp_path)
    first = CountingTransport(
        error=LiveModelProviderError(
            "provider returned HTTP 429: flex unavailable",
            status_code=429,
            retryable=True,
        )
    )

    def crash_before_fallback(*_args: object, **_kwargs: object) -> None:
        raise SimulatedCrash

    monkeypatch.setattr(
        runner_service.SqliteProviderSpendAuthority,
        "authorize_nonbillable_replacement_with_transaction",
        crash_before_fallback,
    )
    monkeypatch.setattr(
        runner_service,
        "_record_cell_failure",
        crash_before_fallback,
    )
    with pytest.raises(SimulatedCrash):
        execute_release_run(config, transport=first, environ=_fixture_environ())
    assert first.calls == 1

    monkeypatch.undo()

    class RecoveryTransport:
        def __init__(self) -> None:
            self.requests: list[Request] = []

        def __call__(self, request: Request, timeout_seconds: float) -> JsonRecord:
            del timeout_seconds
            self.requests.append(request)
            response = dict(_valid_response(request))
            response["service_tier"] = _request_body(request)["service_tier"]
            return response

    recovery = RecoveryTransport()
    summary = execute_release_run(
        config,
        transport=recovery,
        environ=_fixture_environ(),
    )

    assert summary.executed_cells == 3
    assert [
        cast(str, _request_body(request)["service_tier"])
        for request in recovery.requests
    ] == ["default", "flex", "flex"]
    with sqlite3.connect(config.ledger_path) as connection:
        attempts = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY authorized_at_epoch, attempt_ordinal"
        ).fetchall()
    assert attempts[:2] == [(1, "failed_nonbillable"), (2, "settled")]

    no_retry = CountingTransport(error=AssertionError("recovered cell retried"))
    resumed = execute_release_run(
        config,
        transport=no_retry,
        environ=_fixture_environ(),
    )
    assert resumed.executed_cells == 0
    assert resumed.resumed_cells == 3
    assert no_retry.calls == 0


def test_runner_does_not_retry_nonretryable_429(tmp_path: Path) -> None:
    config = _config(tmp_path)
    rejected = CountingTransport(
        error=LiveModelProviderError(
            "provider returned HTTP 429: insufficient_quota",
            status_code=429,
            retryable=False,
        )
    )

    with pytest.raises(LiveModelProviderError, match="insufficient_quota"):
        execute_release_run(config, transport=rejected, environ=_fixture_environ())

    assert rejected.calls == 1
    retry = CountingTransport(error=AssertionError("nonretryable 429 retried"))
    with pytest.raises(RunBlockedError, match="ambiguous"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())
    assert retry.calls == 0


def test_runner_does_not_retry_ambiguous_503(tmp_path: Path) -> None:
    config = _config(tmp_path)
    unavailable = CountingTransport(
        error=LiveModelProviderError(
            "provider returned HTTP 503: temporarily unavailable",
            status_code=503,
            retryable=True,
        )
    )

    with pytest.raises(AttemptLimitExceededError):
        execute_release_run(config, transport=unavailable, environ=_fixture_environ())

    assert unavailable.calls == 1
    retry = CountingTransport(error=AssertionError("ambiguous 503 retried"))
    with pytest.raises(RunBlockedError, match="ambiguous"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())
    assert retry.calls == 0


def test_runner_redacts_untrusted_extra_unit_ids_from_public_receipts(
    tmp_path: Path,
) -> None:
    sentinel = "MODEL_PROSE_SENTINEL_DO_NOT_PUBLISH"

    def extra_unit_response(request: Request) -> JsonRecord:
        body = _request_body(request)
        output = cast(
            dict[str, object],
            json.loads(_output_for_prompt(cast(str, body["input"]))),
        )
        predictions = cast(list[dict[str, object]], output["predictions"])
        predictions.append(
            {
                "unit_id": sentinel,
                "probability_fully_dismissed": 0.5,
            }
        )
        response = dict(_valid_response(request))
        response["output_text"] = json.dumps(output, sort_keys=True)
        return response

    config = _config(tmp_path)
    summary = execute_release_run(
        config,
        transport=CountingTransport(extra_unit_response),
        environ=_fixture_environ(),
    )

    assert summary.completed_cells == 3
    receipt_payloads = [
        path.read_bytes() for path in sorted(config.receipts_dir.glob("*.json"))
    ]
    assert len(receipt_payloads) == 3
    assert all(sentinel.encode() not in payload for payload in receipt_payloads)
    for payload in receipt_payloads:
        receipt = json.loads(payload)
        extra_issue = next(
            issue
            for issue in receipt["parser_output"]["issues"]
            if issue["code"] == "extra_unit"
        )
        assert extra_issue["unit_id"] is None


@pytest.mark.parametrize(
    ("response_metadata", "message"),
    (
        (
            {"groundingMetadata": {"webSearchQueries": ["case outcome"]}},
            "grounding or search",
        ),
        (
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
            },
            "retryable",
        ),
        (
            {"finish_reason": "content_filter"},
            "content filter",
        ),
    ),
)
def test_runner_rejects_unpublishable_provider_response_without_retry(
    tmp_path: Path,
    response_metadata: Mapping[str, object],
    message: str,
) -> None:
    def unpublishable_response(request: Request) -> JsonRecord:
        return {**_valid_response(request), **response_metadata}

    config = _config(tmp_path)
    first = CountingTransport(unpublishable_response)

    with pytest.raises(RunValidationError, match=message):
        execute_release_run(config, transport=first, environ=_fixture_environ())

    assert first.calls == 1
    assert tuple(config.receipts_dir.glob("*.json")) == ()
    retry = CountingTransport(error=AssertionError("unpublishable response retried"))
    with pytest.raises(RunBlockedError, match="ambiguous"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())
    assert retry.calls == 0


def test_runner_spend_keys_use_injective_cell_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    units = (
        SimpleNamespace(
            case_id="a",
            unit_id="b:c",
            prompt_sha256="1" * 64,
        ),
        SimpleNamespace(
            case_id="a:b",
            unit_id="c",
            prompt_sha256="2" * 64,
        ),
    )
    release = SimpleNamespace(
        release_digest="3" * 64,
        release_id="collision-release",
        cases=(
            SimpleNamespace(case_id="a"),
            SimpleNamespace(case_id="a:b"),
        ),
        prediction_units=units,
    )

    class CollisionExecution:
        def __init__(self) -> None:
            self.release = release

        def prompt_bytes(self, unit_id: str) -> bytes:
            return f"Forecast exact unit {unit_id}".encode()

        def packet_bytes(self, unit_id: str) -> bytes:
            case_id = "a" if unit_id == "b:c" else "a:b"
            return runner_service.ARTIFACT_CANONICAL_JSON_V1.encode(
                {
                    "case_id": case_id,
                    "decision_date": "2026-08-23",
                    "unit_id": unit_id,
                }
            )

    monkeypatch.setattr(
        runner_service,
        "load_forecast_execution",
        lambda *_args, **_kwargs: CollisionExecution(),
    )

    def collision_response(request: Request) -> JsonRecord:
        prompt = cast(str, _request_body(request)["input"])
        unit_id = "b:c" if "b:c" in prompt else "c"
        return {
            "model": "legalforecast-fixture-2026-08-23",
            "output_text": json.dumps(
                {
                    "case_assessment": "Collision regression.",
                    "predictions": [
                        {
                            "unit_id": unit_id,
                            "probability_fully_dismissed": 0.5,
                        }
                    ],
                },
                sort_keys=True,
            ),
            "service_tier": "flex",
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }

    summary = execute_release_run(
        config,
        transport=CountingTransport(collision_response),
        environ=_fixture_environ(),
    )

    assert summary.completed_cells == 2
    with sqlite3.connect(config.ledger_path) as connection:
        keys = connection.execute(
            "SELECT logical_call_key FROM provider_attempts ORDER BY attempt_id"
        ).fetchall()
    assert len(keys) == 2
    assert len({key[0] for key in keys}) == 2

    resume = CountingTransport(error=AssertionError("colliding cell retried"))
    resumed = execute_release_run(
        config,
        transport=resume,
        environ=_fixture_environ(),
    )
    assert resumed.executed_cells == 0
    assert resumed.resumed_cells == 2
    assert resume.calls == 0


def test_runner_never_publishes_raw_bedrock_arn_as_served_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    records = cast(
        list[dict[str, object]],
        json.loads(config.model_registry_path.read_bytes()),
    )
    records[0].update(
        provider="anthropic",
        model_id="claude-opus-4-8",
        model_version_or_snapshot="claude-opus-4-8",
    )
    config.model_registry_path.write_bytes(
        runner_service.ARTIFACT_CANONICAL_JSON_V1.encode(records)
    )
    config = replace(config, model_key="anthropic:claude-opus-4-8")
    raw_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:inference-profile/"
        "us.anthropic.claude-opus-4-8"
    )

    monkeypatch.setattr(
        live_model_solver,
        "_bedrock_aws_cli_executable",
        lambda _environ: "/usr/bin/aws",
    )

    def fake_bedrock(
        _model_id: str,
        payload: JsonRecord,
        *,
        environ: Mapping[str, str] | None,
        timeout_seconds: float,
    ) -> JsonRecord:
        del environ, timeout_seconds
        messages = cast(list[dict[str, object]], payload["messages"])
        content = cast(list[dict[str, object]], messages[0]["content"])
        prompt = cast(str, content[0]["text"])
        return {
            "model": raw_arn,
            "content": [{"type": "text", "text": _output_for_prompt(prompt)}],
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }

    monkeypatch.setattr(
        live_model_solver,
        "_invoke_bedrock_runtime_json",
        fake_bedrock,
    )

    summary = execute_release_run(
        config,
        environ={
            "LFB_ANTHROPIC_RUNTIME": "bedrock",
            "LFB_ANTHROPIC_BEDROCK_MODEL_ID": raw_arn,
        },
    )

    assert summary.completed_cells == 3
    for path in config.receipts_dir.glob("*.json"):
        payload = path.read_bytes()
        receipt = json.loads(payload)
        assert receipt["served_model_version"] == "claude-opus-4-8"
        assert b"123456789012" not in payload
        assert raw_arn.encode() not in payload


def test_runner_resumes_completed_cells_without_duplicate_transport(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    first_transport = FixtureModelTransport()
    first = execute_release_run(
        config,
        transport=first_transport,
        environ=_fixture_environ(),
    )
    assert first.executed_cells == 3
    assert first_transport.call_count == 3
    second_transport = CountingTransport(error=AssertionError("transport reused"))

    second = execute_release_run(
        config,
        transport=second_transport,
        environ=_fixture_environ(),
    )

    assert second.executed_cells == 0
    assert second.resumed_cells == 3
    assert second_transport.calls == 0


def test_runner_restores_receipt_after_ledger_commit_without_duplicate_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    first_transport = FixtureModelTransport()

    def simulate_crash_before_receipt_publish(path: Path, payload: bytes) -> None:
        del path, payload
        raise OSError("simulated crash before receipt publication")

    monkeypatch.setattr(
        runner_service,
        "write_file_create_only",
        simulate_crash_before_receipt_publish,
    )
    with pytest.raises(OSError, match="simulated crash"):
        execute_release_run(
            config,
            transport=first_transport,
            environ=_fixture_environ(),
        )
    assert first_transport.call_count == 1
    assert tuple(config.receipts_dir.glob("*.json")) == ()

    monkeypatch.undo()
    resumed_transport = FixtureModelTransport()
    summary = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )

    assert summary.resumed_cells == 1
    assert summary.executed_cells == 2
    assert resumed_transport.call_count == 2
    assert len(tuple(config.receipts_dir.glob("*.json"))) == 3


def test_runner_replays_settled_response_after_crash_before_cell_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SimulatedCrash(BaseException):
        pass

    config = _config(tmp_path)
    first_transport = FixtureModelTransport()
    original_mark_completed = runner_service.RunnerLedger.mark_completed
    crashed = False

    def crash_after_provider_settlement(
        ledger: runner_service.RunnerLedger,
        cell_id: str,
        **kwargs: object,
    ) -> None:
        nonlocal crashed
        if not crashed:
            crashed = True
            raise SimulatedCrash
        original_mark_completed(ledger, cell_id, **kwargs)

    monkeypatch.setattr(
        runner_service.RunnerLedger,
        "mark_completed",
        crash_after_provider_settlement,
    )
    monkeypatch.setattr(
        runner_service,
        "_record_cell_failure",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(SimulatedCrash):
        execute_release_run(
            config,
            transport=first_transport,
            environ=_fixture_environ(),
        )
    assert first_transport.call_count == 1
    with sqlite3.connect(config.ledger_path) as connection:
        cell = connection.execute(
            "SELECT status, request_body_sha256, response_payload "
            "FROM public_runner_cells"
        ).fetchone()
        attempt = connection.execute("SELECT status FROM provider_attempts").fetchone()
    assert cell is not None
    assert cell[0] == "reserved"
    assert cell[1] is not None
    assert cell[2] is not None
    assert attempt == ("settled",)

    monkeypatch.setattr(
        runner_service.RunnerLedger,
        "mark_completed",
        original_mark_completed,
    )
    monkeypatch.undo()
    resumed_transport = FixtureModelTransport()
    summary = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )

    assert summary.resumed_cells == 1
    assert summary.executed_cells == 2
    assert resumed_transport.call_count == 2
    assert len(tuple(config.receipts_dir.glob("*.json"))) == 3


def test_runner_replays_response_after_crash_before_provider_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SimulatedCrash(BaseException):
        pass

    config = _config(tmp_path)
    first_transport = FixtureModelTransport()
    original_record_response = (
        runner_service.SqliteProviderSpendAuthority.record_response
    )
    crashed = False

    def crash_before_provider_settlement(
        authority: runner_service.SqliteProviderSpendAuthority,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal crashed
        if not crashed:
            crashed = True
            raise SimulatedCrash
        original_record_response(authority, *args, **kwargs)

    monkeypatch.setattr(
        runner_service.SqliteProviderSpendAuthority,
        "record_response",
        crash_before_provider_settlement,
    )
    monkeypatch.setattr(
        runner_service,
        "_record_cell_failure",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(SimulatedCrash):
        execute_release_run(
            config,
            transport=first_transport,
            environ=_fixture_environ(),
        )
    assert first_transport.call_count == 1
    with sqlite3.connect(config.ledger_path) as connection:
        cell = connection.execute(
            "SELECT status, request_body_sha256, response_payload "
            "FROM public_runner_cells"
        ).fetchone()
        attempt = connection.execute("SELECT status FROM provider_attempts").fetchone()
    assert cell is not None
    assert cell[0] == "reserved"
    assert cell[1] is not None
    assert cell[2] is not None
    assert attempt == ("reserved",)

    monkeypatch.undo()
    resumed_transport = FixtureModelTransport()
    summary = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )

    assert summary.resumed_cells == 1
    assert summary.executed_cells == 2
    assert resumed_transport.call_count == 2
    assert len(tuple(config.receipts_dir.glob("*.json"))) == 3

    completed_transport = CountingTransport(error=AssertionError("cell retried"))
    completed = execute_release_run(
        config,
        transport=completed_transport,
        environ=_fixture_environ(),
    )
    assert completed.executed_cells == 0
    assert completed.resumed_cells == 3
    assert completed_transport.calls == 0


def test_runner_retries_repaired_pretransport_failure_without_duplicate_call(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    transport = FixtureModelTransport()

    with pytest.raises(LiveModelConfigError, match="OPENAI_API_KEY"):
        execute_release_run(config, transport=transport, environ={})
    assert transport.call_count == 0

    summary = execute_release_run(
        config,
        transport=transport,
        environ=_fixture_environ(),
    )

    assert summary.executed_cells == 3
    assert summary.resumed_cells == 0
    assert transport.call_count == 3


def test_runner_rolls_back_cell_when_atomic_spend_reservation_is_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    transport = FixtureModelTransport()
    original = runner_service.RunnerLedger.reserve_cell_in_transaction

    class SimulatedCrash(BaseException):
        pass

    def crash_during_atomic_reservation(
        ledger: runner_service.RunnerLedger,
        connection: sqlite3.Connection,
        **kwargs: object,
    ) -> None:
        assert connection.in_transaction
        original(ledger, connection, **kwargs)
        assert (
            connection.execute("SELECT COUNT(*) FROM public_runner_cells").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
            == 1
        )
        raise SimulatedCrash

    monkeypatch.setattr(
        runner_service.RunnerLedger,
        "reserve_cell_in_transaction",
        crash_during_atomic_reservation,
    )
    with pytest.raises(SimulatedCrash):
        execute_release_run(
            config,
            transport=transport,
            environ=_fixture_environ(),
        )
    assert transport.call_count == 0
    with sqlite3.connect(config.ledger_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM public_runner_cells").fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
            == 0
        )

    monkeypatch.undo()
    summary = execute_release_run(
        config,
        transport=transport,
        environ=_fixture_environ(),
    )
    assert summary.executed_cells == 3
    assert transport.call_count == 3


def test_runner_reuses_exact_pretransport_reservation_after_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    original_attempt_id = _strand_pretransport_reservation(config, monkeypatch)

    resumed_transport = FixtureModelTransport()
    summary = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )

    assert summary.executed_cells == 3
    assert resumed_transport.call_count == 3
    with sqlite3.connect(config.ledger_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone() == (3,)
        assert connection.execute(
            "SELECT COUNT(*) FROM public_runner_cells WHERE status = 'completed'"
        ).fetchone() == (3,)
        assert connection.execute(
            "SELECT provider_attempt_id FROM public_runner_cells ORDER BY rowid LIMIT 1"
        ).fetchone() == (original_attempt_id,)


def test_runner_preflights_before_reusing_pretransport_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    _strand_pretransport_reservation(config, monkeypatch)

    for _ in range(2):
        preflight_transport = CountingTransport(
            error=AssertionError("transport after failed preflight")
        )
        with pytest.raises(LiveModelConfigError, match="OPENAI_API_KEY"):
            execute_release_run(config, transport=preflight_transport, environ={})
        assert preflight_transport.calls == 0
        with sqlite3.connect(config.ledger_path) as connection:
            assert connection.execute(
                "SELECT status, request_body_sha256, response_payload "
                "FROM public_runner_cells"
            ).fetchone() == ("reserved", None, None)
            assert connection.execute(
                "SELECT status FROM provider_attempts"
            ).fetchone() == ("reserved",)

    resumed_transport = FixtureModelTransport()
    summary = execute_release_run(
        config,
        transport=resumed_transport,
        environ=_fixture_environ(),
    )
    assert summary.executed_cells == 3
    assert resumed_transport.call_count == 3


@pytest.mark.parametrize(
    "unsafe_state",
    ("request_observed", "attempt_not_reserved", "attempt_binding_mismatch"),
)
def test_runner_refuses_unsafe_pretransport_reservation_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_state: str,
) -> None:
    config = _config(tmp_path)
    _strand_pretransport_reservation(config, monkeypatch)

    with sqlite3.connect(config.ledger_path) as connection:
        if unsafe_state == "request_observed":
            connection.execute(
                "UPDATE public_runner_cells SET request_body_sha256 = ?",
                ("0" * 64,),
            )
        elif unsafe_state == "attempt_not_reserved":
            connection.execute("UPDATE provider_attempts SET status = 'ambiguous'")
        else:
            connection.execute(
                "UPDATE public_runner_cells SET provider_attempt_id = ?",
                ("f" * 64,),
            )
        connection.commit()

    retry = CountingTransport(error=AssertionError("unsafe reservation retried"))
    with pytest.raises(RunBlockedError, match="provider state"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())
    assert retry.calls == 0


@pytest.mark.parametrize("raced_state", ("request_committed", "attempt_settled"))
def test_runner_request_commitment_rechecks_pretransport_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raced_state: str,
) -> None:
    config = _config(tmp_path)
    attempt_id = _strand_pretransport_reservation(config, monkeypatch)
    with sqlite3.connect(config.ledger_path) as connection:
        cell_id = cast(
            str,
            connection.execute("SELECT cell_id FROM public_runner_cells").fetchone()[0],
        )
        if raced_state == "attempt_settled":
            connection.execute("UPDATE provider_attempts SET status = 'settled'")
            connection.commit()

    with runner_service.RunnerLedger(config.ledger_path) as ledger:
        if raced_state == "request_committed":
            ledger.record_request_body(
                cell_id,
                provider_attempt_id=attempt_id,
                request_body_sha256="a" * 64,
            )
        with pytest.raises(RunBlockedError, match="request commitment"):
            ledger.record_request_body(
                cell_id,
                provider_attempt_id=attempt_id,
                request_body_sha256="b" * 64,
            )


def test_runner_retains_interrupted_reservation_and_refuses_duplicate_call(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    interrupted = CountingTransport(error=TimeoutError("response unknown"))

    with pytest.raises(TimeoutError, match="response unknown"):
        execute_release_run(
            config,
            transport=interrupted,
            environ=_fixture_environ(),
        )
    assert interrupted.calls == 1
    retry = CountingTransport(error=AssertionError("duplicate transport"))

    with pytest.raises(RunBlockedError, match=r"ambiguous|reserved"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())

    assert retry.calls == 0


def test_runner_refuses_cap_exhaustion_before_transport(tmp_path: Path) -> None:
    config = _config(tmp_path, ceiling_microusd=1)
    transport = CountingTransport(error=AssertionError("overspend transport"))

    with pytest.raises(RunBlockedError, match=r"ceiling|cap"):
        execute_release_run(config, transport=transport, environ=_fixture_environ())

    assert transport.calls == 0


def test_runner_unknown_usage_stops_all_future_calls(tmp_path: Path) -> None:
    def missing_usage(request: Request) -> JsonRecord:
        body = _request_body(request)
        return {
            "model": "legalforecast-fixture-2026-08-23",
            "output_text": _output_for_prompt(cast(str, body["input"])),
            "service_tier": "flex",
        }

    config = _config(tmp_path)
    unknown = CountingTransport(missing_usage)

    with pytest.raises(LiveModelResponseError, match="usage"):
        execute_release_run(config, transport=unknown, environ=_fixture_environ())
    assert unknown.calls == 1
    retry = CountingTransport(error=AssertionError("duplicate transport"))

    with pytest.raises(RunBlockedError, match=r"ambiguous|reserved"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())

    assert retry.calls == 0


def test_runner_served_model_drift_is_ambiguous_and_never_retried(
    tmp_path: Path,
) -> None:
    def wrong_model(request: Request) -> JsonRecord:
        response = dict(_valid_response(request))
        response["model"] = "different-served-model"
        return response

    config = _config(tmp_path)
    drifted = CountingTransport(wrong_model)

    with pytest.raises(LiveModelResponseError, match="served model version"):
        execute_release_run(config, transport=drifted, environ=_fixture_environ())
    assert drifted.calls == 1
    retry = CountingTransport(error=AssertionError("duplicate transport"))

    with pytest.raises(RunBlockedError, match=r"ambiguous|reserved"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())

    assert retry.calls == 0


def test_runner_refuses_tampered_completed_receipt_before_transport(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    execute_release_run(
        config,
        transport=FixtureModelTransport(),
        environ=_fixture_environ(),
    )
    receipt = next(config.receipts_dir.glob("*.json"))
    payload = json.loads(receipt.read_bytes())
    payload["usage"]["output_tokens"] += 1
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    retry = CountingTransport(error=AssertionError("transport after tamper"))

    with pytest.raises(RunValidationError, match="receipt"):
        execute_release_run(config, transport=retry, environ=_fixture_environ())

    assert retry.calls == 0


def test_public_receipts_are_normalized_hash_only_and_label_blind(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    (config.artifact_root / "labels-release.json").unlink()

    summary = execute_release_run(
        config,
        transport=FixtureModelTransport(),
        environ=_fixture_environ(),
    )

    assert summary.completed_cells == 3
    receipts = [
        json.loads(path.read_bytes())
        for path in sorted(config.receipts_dir.glob("*.json"))
    ]
    assert {receipt["unit_id"] for receipt in receipts} == {
        "unit-001",
        "unit-002",
        "unit-003",
    }
    for receipt in receipts:
        assert receipt["schema_version"] == "legalforecast.public-run-receipt.v1"
        assert receipt["parser_output"]["status"] == "valid"
        assert len(receipt["parser_output"]["predictions"]) == 1
        assert len(receipt["prompt_sha256"]) == 64
        assert len(receipt["request_body_sha256"]) == 64
        assert receipt["served_model_version"] == ("legalforecast-fixture-2026-08-23")
        assert "estimated_cost_microusd" in receipt["usage"]
        assert "actual_cost_microusd" not in receipt["usage"]
        serialized = json.dumps(receipt, sort_keys=True).lower()
        for forbidden in (
            "deterministic provider-free fixture",
            "labels-release",
            "unit_outcome",
            'raw_output"',
            "raw_provider",
            "synthetic predecision material",
        ):
            assert forbidden not in serialized


def _strand_pretransport_reservation(
    config: RunConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    class SimulatedCrash(BaseException):
        pass

    original_authorize = (
        runner_service.SqliteProviderSpendAuthority.authorize_attempt_with_transaction
    )

    def crash_after_atomic_reservation(
        authority: runner_service.SqliteProviderSpendAuthority,
        *args: object,
        **kwargs: object,
    ) -> None:
        original_authorize(authority, *args, **kwargs)
        raise SimulatedCrash

    transport = FixtureModelTransport()
    with monkeypatch.context() as crash_patch:
        crash_patch.setattr(
            runner_service.SqliteProviderSpendAuthority,
            "authorize_attempt_with_transaction",
            crash_after_atomic_reservation,
        )
        crash_patch.setattr(
            runner_service,
            "_record_cell_failure",
            lambda *_args, **_kwargs: None,
        )
        with pytest.raises(SimulatedCrash):
            execute_release_run(
                config,
                transport=transport,
                environ=_fixture_environ(),
            )

    assert transport.call_count == 0
    with sqlite3.connect(config.ledger_path) as connection:
        assert connection.execute(
            "SELECT status, request_body_sha256, response_payload "
            "FROM public_runner_cells"
        ).fetchone() == ("reserved", None, None)
        attempt = connection.execute(
            "SELECT attempt_id, status FROM provider_attempts"
        ).fetchone()
        assert attempt is not None
        assert attempt[1] == "reserved"
        return cast(str, attempt[0])


def _config(
    tmp_path: Path,
    *,
    approval_reference: str = "owner-approved-fixture",
    ceiling_microusd: int = 30_000,
) -> RunConfig:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    return RunConfig(
        forecast_path=fixture / "release" / "forecast-release.json",
        artifact_root=fixture / "release",
        model_registry_path=fixture / "model-registry.json",
        model_key=FIXTURE_MODEL_KEY,
        ledger_path=tmp_path / "run.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=ceiling_microusd,
        approval_reference=approval_reference,
        harness="native",
        ablation="none",
        repeat_count=1,
    )


def _fixture_environ() -> dict[str, str]:
    return {"OPENAI_API_KEY": "provider-free-fixture-key"}


def _valid_response(request: Request) -> JsonRecord:
    body = _request_body(request)
    return {
        "model": "legalforecast-fixture-2026-08-23",
        "output_text": _output_for_prompt(cast(str, body["input"])),
        "service_tier": "flex",
        "usage": {"input_tokens": 20, "output_tokens": 10},
    }


def _request_body(request: Request) -> dict[str, object]:
    assert request.data is not None
    return cast(dict[str, object], json.loads(cast(bytes, request.data)))


def _output_for_prompt(prompt: str) -> str:
    unit_id = next(
        unit_id for unit_id in ("unit-001", "unit-002", "unit-003") if unit_id in prompt
    )
    probability = {
        "unit-001": 0.2,
        "unit-002": 0.8,
        "unit-003": 0.5,
    }[unit_id]
    return json.dumps(
        {
            "case_assessment": "Deterministic provider-free fixture.",
            "predictions": [
                {
                    "unit_id": unit_id,
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _tree_payloads(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

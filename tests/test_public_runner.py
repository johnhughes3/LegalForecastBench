from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast
from urllib.request import Request

import legalforecast.runner.service as runner_service
import pytest
from legalforecast.cli import main
from legalforecast.evals.live_model_solver import (
    LiveModelConfigError,
    LiveModelResponseError,
)
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


def test_runner_refuses_exact_ledger_identity_drift_without_transport(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    first_transport = FixtureModelTransport()
    execute_release_run(config, transport=first_transport, environ=_fixture_environ())
    assert first_transport.call_count == 3
    drifted = replace(config, harness="different-harness")
    second_transport = CountingTransport(error=AssertionError("transport reused"))

    with pytest.raises(RunIdentityError, match="ledger identity"):
        execute_release_run(
            drifted,
            transport=second_transport,
            environ=_fixture_environ(),
        )

    assert second_transport.calls == 0


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

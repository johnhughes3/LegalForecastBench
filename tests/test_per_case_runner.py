from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.evals import per_case_runner
from legalforecast.evals.inspect_task import (
    ConfiguredModelStubSolver,
    HarnessRequest,
    SolverKind,
    SolverResponse,
    render_model_prompt,
)
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
)
from legalforecast.evals.per_case_runner import (
    PacketManifestError,
    PerCaseRunnerConfig,
    PerCaseRunnerError,
    run_per_case_evaluation,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text
from legalforecast.protocol.freeze import sha256_file
from legalforecast.protocol.policy_artifacts import generate_execution_policy
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_per_case_runner_verifies_packet_and_publishes_safe_outputs(
    tmp_path: Path,
) -> None:
    packet_text = "Operative complaint text for the isolated packet."
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
    )
    output_dir = tmp_path / "runner-output"
    results_root = tmp_path / "results-store"

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256
    assert {path.name for path in artifacts.local_paths} == {
        "accounting.jsonl",
        "cell-completion.json",
        "metrics.json",
        "runner-log.jsonl",
        "runs.jsonl",
    }
    assert all(path.is_file() for path in artifacts.local_paths)
    assert not (output_dir / "model-packet.json").exists()

    runs = _read_jsonl(output_dir / "runs.jsonl")
    assert runs[0]["case_id"] == "case-1"
    assert "packet" not in runs[0]
    assert "prompt" not in runs[0]

    log_text = (output_dir / "runner-log.jsonl").read_text(encoding="utf-8")
    metrics_text = (output_dir / "metrics.json").read_text(encoding="utf-8")
    accounting_text = (output_dir / "accounting.jsonl").read_text(encoding="utf-8")
    for text in (log_text, metrics_text, accounting_text):
        assert packet_text not in text
        assert "CASE_DEV_API_KEY" not in text

    uploaded_paths = {
        path.relative_to(results_root).as_posix()
        for path in results_root.rglob("*")
        if path.is_file()
    }
    assert uploaded_paths
    assert all(path.startswith(("metrics/", "reports/")) for path in uploaded_paths)
    assert not any(
        path.startswith(
            (
                "audit-bundles/",
                "extracted-text/",
                "model-packets/",
                "source-documents/",
                "withdrawn/",
            )
        )
        for path in uploaded_paths
    )


def test_per_case_runner_records_observed_openai_tier_only_in_runner_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"

    class ObservedTierSolver:
        solver_id = "offline:fixture"
        solver_kind = SolverKind.INSPECT_AI

        def __init__(self, observer: Any) -> None:
            self.observer = observer

        def solve(self, request: HarnessRequest) -> SolverResponse:
            self.observer(request, "flex")
            return SolverResponse(raw_output=_mock_output())

    def fake_solver_for_config(
        *_args: Any,
        openai_service_tier_observer: Any,
        **_kwargs: Any,
    ) -> ObservedTierSolver:
        return ObservedTierSolver(openai_service_tier_observer)

    monkeypatch.setattr(per_case_runner, "_solver_for_config", fake_solver_for_config)
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    runs_text = (output_dir / "runs.jsonl").read_text(encoding="utf-8")
    accounting_text = (output_dir / "accounting.jsonl").read_text(encoding="utf-8")
    metrics_text = (output_dir / "metrics.json").read_text(encoding="utf-8")
    assert "observed_service_tier" not in runs_text
    assert "observed_service_tier" not in accounting_text
    assert "observed_service_tier" not in metrics_text

    log_records = _read_jsonl(output_dir / "runner-log.jsonl")
    tier_records = [
        record
        for record in log_records
        if record["event"] == "openai_service_tier_observed"
    ]
    assert tier_records == [
        {
            "ablation": "full_packet",
            "case_id": "case-1",
            "event": "openai_service_tier_observed",
            "observed_service_tier": "flex",
            "repeat_index": 1,
            "sample_id": "cand-1",
            "schema_version": "legalforecast.per_case_runner_log.v1",
            "timestamp": tier_records[0]["timestamp"],
        }
    ]


def _committed_prompt_sha256(
    packet_record: dict[str, object],
    *,
    use_docket_tool: bool = True,
) -> str:
    """Render the prompt exactly as the runner will, and hash it."""

    packet = per_case_runner._model_packet_from_record(packet_record)
    return sha256_text(render_model_prompt(packet, use_docket_tool=use_docket_tool))


def test_per_case_runner_refuses_a_prompt_that_differs_from_its_commitment(
    tmp_path: Path,
) -> None:
    """Drive the PRODUCTION entry, not the helper.

    This pins the enforcement to its call site inside run_per_case_evaluation:
    deleting that line makes this test go green-to-red, which calling the
    helper directly never could.
    """

    packet_record = _packet_record()
    store_root, manifest_path, _ = _write_store_fixture(
        tmp_path,
        packet_record=packet_record,
        extra_packet_fields={"prompt_sha256": "0" * 64},
    )

    with pytest.raises(PacketManifestError, match="does not match the prompt_sha256"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(tmp_path / "results-store"),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                solver_id="offline:fixture",
                mock_output=_mock_output(),
            )
        )


def test_per_case_runner_runs_when_the_prompt_matches_its_commitment(
    tmp_path: Path,
) -> None:
    """The committed-prompt path must still execute the authorized prompt."""

    packet_record = _packet_record()
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=packet_record,
        extra_packet_fields={"prompt_sha256": _committed_prompt_sha256(packet_record)},
    )

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(tmp_path / "results-store"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256


def test_per_case_runner_carries_manifest_commitment_to_solver_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The manifest digest must reach the sample passed to the production solver."""

    packet_record = _packet_record()
    committed = _committed_prompt_sha256(packet_record)
    store_root, manifest_path, _ = _write_store_fixture(
        tmp_path,
        packet_record=packet_record,
        extra_packet_fields={"prompt_sha256": committed},
    )
    original_runner = per_case_runner.run_inspect_fixture

    def checked_runner(samples: Any, solvers: Any) -> Any:
        assert len(samples) == 1
        assert samples[0].committed_prompt_sha256 == committed
        return original_runner(samples, solvers)

    monkeypatch.setattr(per_case_runner, "run_inspect_fixture", checked_runner)

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(tmp_path / "results-store"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )


def test_per_case_runner_enforcement_runs_before_any_solver_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused prompt must cost nothing: no solver call, no output written."""

    packet_record = _packet_record()
    store_root, manifest_path, _ = _write_store_fixture(
        tmp_path,
        packet_record=packet_record,
        extra_packet_fields={"prompt_sha256": "0" * 64},
    )
    output_dir = tmp_path / "runner-output"

    def _fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("solver ran despite a refused prompt commitment")

    monkeypatch.setattr(per_case_runner, "run_inspect_fixture", _fail_if_called)

    with pytest.raises(PacketManifestError):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(tmp_path / "results-store"),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                solver_id="offline:fixture",
                mock_output=_mock_output(),
            )
        )

    assert not (output_dir / "runs.jsonl").exists()


def test_per_case_runner_resumes_complete_durable_outputs_without_rerun(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"

    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.25),
        )
    )

    second = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    assert second.run_id == first.run_id
    assert second.uploaded_uris == first.uploaded_uris[:3]
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    log_text = (tmp_path / "second-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resumed_existing_artifacts" in log_text


def test_per_case_runner_does_not_resume_incomplete_durable_outputs(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    partial_dir = results_root / "metrics" / "cycle-1"
    partial_dir.mkdir(parents=True)
    (
        partial_dir / "case-1-full_packet-offline-fixture-d2945393d77a.runs.jsonl"
    ).write_text(
        "",
        encoding="utf-8",
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert "0.91" in runs[0]["raw_output"]


def test_per_case_runner_replaces_stale_complete_durable_outputs(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text="original packet"),
    )
    results_root = tmp_path / "results-store"
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.25),
        )
    )
    _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text="refrozen packet"),
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.91" in runs[0]["raw_output"]
    assert "0.25" not in runs[0]["raw_output"]
    log_text = (tmp_path / "second-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resume_existing_rejected" in log_text
    assert "packet_sha256 does not match" in log_text


def test_per_case_runner_recovers_paid_generation_after_canonical_upload_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    runner_module = cast(Any, per_case_runner)
    original_upload = runner_module._upload_path
    failed = False

    def fail_first_accounting_upload(
        source: Path,
        destination_uri: str,
        *,
        content_type: str,
    ) -> None:
        nonlocal failed
        if destination_uri.endswith(".accounting.jsonl") and not failed:
            failed = True
            raise OSError("simulated canonical upload failure")
        original_upload(source, destination_uri, content_type=content_type)

    monkeypatch.setattr(per_case_runner, "_upload_path", fail_first_accounting_upload)
    with pytest.raises(PerCaseRunnerError, match="simulated canonical upload failure"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "failed-output",
                solver_id="offline:fixture",
                mock_output=_mock_output(probability=0.25),
            )
        )
    monkeypatch.setattr(per_case_runner, "_upload_path", original_upload)

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "resumed-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(probability=0.91),
            resume_existing=True,
        )
    )

    runs = _read_jsonl(tmp_path / "resumed-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    log_text = (tmp_path / "resumed-output" / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "resumed_recovery_bundle" in log_text


def test_per_case_runner_accepts_exported_packet_sha256_field(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
        hash_field="packet_sha256",
    )

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256


@pytest.mark.parametrize(
    ("expected_object_key", "expected_sha256", "error_match"),
    (
        (
            "model-packets/cycle-1/case-1/drifted.json",
            None,
            "pre-fanout packet object key",
        ),
        (
            None,
            "0" * 64,
            "pre-fanout packet SHA-256",
        ),
    ),
)
def test_per_case_runner_rejects_pre_fanout_packet_identity_drift_before_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_object_key: str | None,
    expected_sha256: str | None,
    error_match: str,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
        hash_field="packet_sha256",
    )
    packet_object_key = "model-packets/cycle-1/case-1/full_packet.json"

    def reject_fetch(_uri: str, _destination: Path) -> None:
        raise AssertionError("packet fetch occurred before identity verification")

    monkeypatch.setattr(per_case_runner, "_fetch_uri", reject_fetch)

    with pytest.raises(PerCaseRunnerError, match=error_match):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                solver_id="offline:fixture",
                mock_output=_mock_output(),
                expected_packet_object_key=(expected_object_key or packet_object_key),
                expected_packet_sha256=expected_sha256 or packet_sha256,
            )
        )


def test_live_per_case_runner_requires_pre_fanout_packet_identity(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="pre-fanout packet identity"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            backend=per_case_runner.PerCaseExecutionBackend.LIVE,
            model_registry_uri=str(tmp_path / "registry.json"),
            model_key="provider:model",
        )


def test_live_per_case_runner_requires_frozen_spend_authority_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="execution_policy_uri"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            backend=per_case_runner.PerCaseExecutionBackend.LIVE,
            model_registry_uri=str(tmp_path / "registry.json"),
            model_key="provider:model",
            expected_packet_object_key=(
                "model-packets/cycle-1/case-1/full_packet.json"
            ),
            expected_packet_sha256="a" * 64,
        )


def test_live_solver_binds_frozen_account_cap_breaker_and_repeat_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.json"
    _write_model_registry(
        registry_path,
        ("example-model",),
        provider="openai",
        context_limit=1_050_000,
        max_output_tokens=128_000,
        input_price_by_model={"example-model": 5.0},
        output_token_price=30.0,
        long_context_surcharge={
            "threshold_input_tokens": 272_000,
            "input_price_multiplier": 2.0,
            "output_price_multiplier": 1.5,
        },
    )
    registry_entry = load_model_registry(registry_path).entries[0]
    execution_policy_path = tmp_path / "execution-policy.json"
    execution_policy_sha256 = _write_execution_policy(
        execution_policy_path, provider="openai"
    )
    captured: dict[str, object] = {}

    class FakeDynamoAuthority:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "legalforecast.evals.provider_spend_dynamodb.DynamoDbProviderSpendAuthority",
        FakeDynamoAuthority,
    )
    config = PerCaseRunnerConfig(
        manifest_uri=str(tmp_path / "manifest.json"),
        case_id="case-1",
        ablation="full_packet",
        output_dir=tmp_path / "runner-output",
        backend=per_case_runner.PerCaseExecutionBackend.LIVE,
        model_registry_uri=str(registry_path),
        model_key="openai:example-model",
        expected_packet_object_key=("model-packets/cycle-1/case-1/full_packet.json"),
        expected_packet_sha256="a" * 64,
        execution_policy_uri=str(execution_policy_path),
        expected_execution_policy_sha256=execution_policy_sha256,
        workflow_run_id="123",
        workflow_run_attempt=1,
        provider_authority_table="authority-table",
        provider_authority_region="us-east-2",
    )

    runner_module = cast(Any, per_case_runner)
    solver = runner_module._solver_for_config(
        config,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        cycle_id="cycle-1",
    )
    assert solver.max_attempts == 2
    assert captured["cap_microusd"] == 1_000_000_000
    assert captured["authority_identity_sha256"] == "e" * 64
    assert captured["region"] == "us-east-2"
    handler = solver.attempt_handler_factory(
        SimpleNamespace(
            sample=SimpleNamespace(
                sample_id="case-1__repeat_02",
                packet=SimpleNamespace(
                    case_id="case-1",
                    ablation=PacketAblation.FULL_PACKET,
                ),
            )
        )
    )
    assert handler.key.repeat_index == 2
    assert handler.key.stage == "official-eval"
    assert handler.key.account == "primary"
    assert handler.reservation_microusd == 14_980_000


def test_live_resume_requires_exact_raw_execution_policy_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "registry.json"
    _write_model_registry(registry_path, ("example-model",), provider="openai")
    execution_policy_path = tmp_path / "execution-policy.json"
    execution_policy_sha256 = _write_execution_policy(
        execution_policy_path, provider="openai"
    )

    def fake_solver_for_config(
        config: PerCaseRunnerConfig,
        *,
        registry_entry: Any,
        **_kwargs: Any,
    ) -> ConfiguredModelStubSolver:
        return ConfiguredModelStubSolver(
            registry_entry=registry_entry,
            stub_raw_output=cast(str, config.mock_output),
            input_tokens=100,
            output_tokens=25,
            estimated_cost=0.0,
        )

    monkeypatch.setattr(per_case_runner, "_solver_for_config", fake_solver_for_config)
    base: dict[str, Any] = {
        "manifest_uri": str(manifest_path),
        "packet_store_root": str(store_root),
        "results_store_root": str(results_root),
        "case_id": "case-1",
        "ablation": "full_packet",
        "backend": per_case_runner.PerCaseExecutionBackend.LIVE,
        "model_registry_uri": str(registry_path),
        "model_key": "openai:example-model",
        "expected_packet_object_key": ("model-packets/cycle-1/case-1/full_packet.json"),
        "expected_packet_sha256": packet_sha256,
        "execution_policy_uri": str(execution_policy_path),
        "expected_execution_policy_sha256": execution_policy_sha256,
        "workflow_run_id": "123",
        "workflow_run_attempt": 1,
        "provider_authority_table": "authority-table",
        "provider_account": "primary",
    }
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            **base,
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
        )
    )
    metrics_path = next((results_root / "metrics").rglob("*.metrics.json"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    binding = metrics["execution_policy_binding"]
    assert binding["execution_policy_sha256"] == sha256_file(execution_policy_path)
    assert binding["reservation_ledger_sha256"] == "d" * 64
    assert binding["authority_resource_identity_sha256"] == "e" * 64
    assert binding["provider"] == "openai"
    assert binding["account"] == "primary"

    execution_policy_path.write_bytes(execution_policy_path.read_bytes() + b"\n")
    durable_before_resume = _snapshot_files(results_root)
    with pytest.raises(PerCaseRunnerError, match="execution policy binding"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                **base,
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                resume_existing=True,
            )
        )
    assert _snapshot_files(results_root) == durable_before_resume


def test_live_resume_rejects_legacy_unbound_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "registry.json"
    _write_model_registry(registry_path, ("example-model",), provider="openai")
    execution_policy_path = tmp_path / "execution-policy.json"
    execution_policy_sha256 = _write_execution_policy(
        execution_policy_path, provider="openai"
    )

    def fake_solver_for_config(
        config: PerCaseRunnerConfig,
        *,
        registry_entry: Any,
        **_kwargs: Any,
    ) -> ConfiguredModelStubSolver:
        return ConfiguredModelStubSolver(
            registry_entry=registry_entry,
            stub_raw_output=cast(str, config.mock_output),
            input_tokens=100,
            output_tokens=25,
            estimated_cost=0.0,
        )

    monkeypatch.setattr(per_case_runner, "_solver_for_config", fake_solver_for_config)
    base: dict[str, Any] = {
        "manifest_uri": str(manifest_path),
        "packet_store_root": str(store_root),
        "results_store_root": str(results_root),
        "case_id": "case-1",
        "ablation": "full_packet",
        "backend": per_case_runner.PerCaseExecutionBackend.LIVE,
        "model_registry_uri": str(registry_path),
        "model_key": "openai:example-model",
        "expected_packet_object_key": ("model-packets/cycle-1/case-1/full_packet.json"),
        "expected_packet_sha256": packet_sha256,
        "execution_policy_uri": str(execution_policy_path),
        "expected_execution_policy_sha256": execution_policy_sha256,
        "workflow_run_id": "123",
        "workflow_run_attempt": 1,
        "provider_authority_table": "authority-table",
        "provider_account": "primary",
    }
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            **base,
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
        )
    )
    metrics_path = next((results_root / "metrics").rglob("*.metrics.json"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    del metrics["execution_policy_binding"]
    _write_json(metrics_path, metrics)
    durable_before_resume = _snapshot_files(results_root)

    with pytest.raises(PerCaseRunnerError, match="execution policy binding"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                **base,
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                resume_existing=True,
            )
        )
    assert _snapshot_files(results_root) == durable_before_resume


def test_live_resume_verifies_policy_before_inspecting_durable_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "registry.json"
    _write_model_registry(registry_path, ("example-model",), provider="openai")
    execution_policy_path = tmp_path / "execution-policy.json"
    _write_execution_policy(execution_policy_path, provider="openai")
    artifact = json.loads(execution_policy_path.read_text(encoding="utf-8"))
    artifact["policy_sha256"] = "0" * 64
    _write_json(execution_policy_path, artifact)

    def forbidden_resume(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("resume inspection occurred before execution-policy verification")

    monkeypatch.setattr(
        per_case_runner,
        "_try_resume_existing_outputs",
        forbidden_resume,
    )
    with pytest.raises(PerCaseRunnerError, match="execution policy"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                backend=per_case_runner.PerCaseExecutionBackend.LIVE,
                model_registry_uri=str(registry_path),
                model_key="openai:example-model",
                expected_packet_object_key=(
                    "model-packets/cycle-1/case-1/full_packet.json"
                ),
                expected_packet_sha256=packet_sha256,
                execution_policy_uri=str(execution_policy_path),
                expected_execution_policy_sha256="0" * 64,
                workflow_run_id="123",
                workflow_run_attempt=1,
                provider_authority_table="authority-table",
                provider_account="primary",
                resume_existing=True,
            )
        )


def test_live_policy_verifier_rejects_valid_policy_with_wrong_expected_hash(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    _write_model_registry(registry_path, ("example-model",), provider="openai")
    registry_entry = load_model_registry(registry_path).entries[0]
    execution_policy_path = tmp_path / "execution-policy.json"
    _write_execution_policy(execution_policy_path, provider="openai")
    config = PerCaseRunnerConfig(
        manifest_uri=str(tmp_path / "manifest.json"),
        case_id="case-1",
        ablation="full_packet",
        output_dir=tmp_path / "runner-output",
        backend=per_case_runner.PerCaseExecutionBackend.LIVE,
        model_registry_uri=str(registry_path),
        model_key="openai:example-model",
        expected_packet_object_key="model-packets/cycle-1/case-1/full_packet.json",
        expected_packet_sha256="a" * 64,
        execution_policy_uri=str(execution_policy_path),
        expected_execution_policy_sha256="0" * 64,
        workflow_run_id="123",
        workflow_run_attempt=1,
        provider_authority_table="authority-table",
        provider_account="primary",
    )
    runner_module = cast(Any, per_case_runner)

    with pytest.raises(PerCaseRunnerError, match="execution policy"):
        runner_module._verified_execution_policy_for_config(
            config,
            registry_entry=registry_entry,
            cycle_id="cycle-1",
        )


def test_per_case_runner_refuses_hash_mismatch_without_retaining_packet(
    tmp_path: Path,
) -> None:
    packet_text = "Hash mismatch packet text must not be retained."
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
        manifest_sha256="0" * 64,
    )
    output_dir = tmp_path / "runner-output"

    with pytest.raises(PerCaseRunnerError, match="SHA-256 mismatch"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                mock_output=_mock_output(),
            )
        )

    assert (output_dir / "runner-log.jsonl").is_file()
    assert not (output_dir / "runs.jsonl").exists()
    assert packet_text not in (output_dir / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )


def test_per_case_runner_refuses_audit_only_packet_objects(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": "audit-bundles/cycle-1/case-1/full_packet.json",
                    "sha256": "1" * 64,
                }
            ],
        },
    )

    with pytest.raises(PacketManifestError, match="model packet object key"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(tmp_path / "store"),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
            )
        )


def test_eval_run_case_cli_writes_artifact_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "cli-output"

    assert (
        main(
            [
                "eval",
                "run-case",
                "--manifest",
                str(manifest_path),
                "--packet-store-root",
                str(store_root),
                "--expected-packet-object-key",
                "model-packets/cycle-1/case-1/full_packet.json",
                "--expected-packet-sha256",
                packet_sha256,
                "--case-id",
                "case-1",
                "--ablation",
                "full_packet",
                "--output-dir",
                str(output_dir),
                "--mock-output",
                _mock_output(),
                "--evaluation-timestamp",
                "2026-05-17T12:00:00Z",
                "--timeout-seconds",
                "300",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["case_id"] == "case-1"
    assert (output_dir / "runs.jsonl").is_file()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["evaluation_timestamp"] == "2026-05-17T12:00:00Z"


def test_eval_run_case_cli_reports_live_config_error_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "eval",
            "run-case",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--case-id",
            "case-1",
            "--output-dir",
            str(tmp_path / "runner-output"),
            "--backend",
            "live",
            "--model-registry",
            str(tmp_path / "model-registry.json"),
            "--model-key",
            "openai:gpt-test",
            "--expected-packet-object-key",
            "model-packets/cycle-1/case-1/full_packet.json",
            "--expected-packet-sha256",
            "a" * 64,
            "--execution-policy",
            str(tmp_path / "execution-policy.json"),
            "--expected-execution-policy-sha256",
            "b" * 64,
            "--workflow-run-id",
            "123",
            "--workflow-run-attempt",
            "1",
        ]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "legalforecast: provider_authority_table is required for live backend\n"
    )


def test_per_case_runner_repeats_prebudgeted_subset_rows(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            mock_output=_mock_output(),
            repeat_count=3,
        )
    )

    runs = _read_jsonl(output_dir / "runs.jsonl")
    accounting = _read_jsonl(output_dir / "accounting.jsonl")
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert [record["repeat_index"] for record in runs] == [1, 2, 3]
    assert [record["repeat_sampling_role"] for record in runs] == [
        "primary",
        "repeat",
        "repeat",
    ]
    assert {record["repeat_group_id"] for record in runs} == {"cand-1"}
    assert len(accounting) == 3
    assert all(record["repeat_count"] == 3 for record in accounting)
    assert metrics["repeat_count"] == 3
    assert metrics["primary_run_record_count"] == 1
    assert metrics["run_record_count"] == 3


def test_repeat_policy_mismatch_fails_before_resume_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    execution_path, execution_sha256 = _write_repeat_execution_policy(
        tmp_path, repeat_count=3
    )

    monkeypatch.setattr(
        per_case_runner,
        "_try_resume_existing_outputs",
        lambda **_kwargs: pytest.fail("repeat mismatch reached resume"),
    )
    monkeypatch.setattr(
        per_case_runner,
        "_solver_for_config",
        lambda *_args, **_kwargs: pytest.fail("repeat mismatch reached provider"),
    )

    with pytest.raises(PerCaseRunnerError, match="repeat_count does not match frozen"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                repeat_count=2,
                execution_policy_uri=str(execution_path),
                expected_execution_policy_sha256=execution_sha256,
                resume_existing=True,
            )
        )


def test_repeat_policy_identity_changes_durable_run_id(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    first_path, first_sha256 = _write_repeat_execution_policy(tmp_path, repeat_count=2)
    second_path, second_sha256 = _write_repeat_execution_policy(
        tmp_path, repeat_count=3, name="execution-policy-second.json"
    )

    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first",
            mock_output=_mock_output(),
            repeat_count=2,
            execution_policy_uri=str(first_path),
            expected_execution_policy_sha256=first_sha256,
        )
    )
    second = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second",
            mock_output=_mock_output(),
            repeat_count=3,
            execution_policy_uri=str(second_path),
            expected_execution_policy_sha256=second_sha256,
        )
    )

    assert first.run_id != second.run_id
    first_metrics = json.loads(
        (tmp_path / "first" / "metrics.json").read_text(encoding="utf-8")
    )
    second_metrics = json.loads(
        (tmp_path / "second" / "metrics.json").read_text(encoding="utf-8")
    )
    assert (
        first_metrics["repeat_policy_sha256"] != second_metrics["repeat_policy_sha256"]
    )


def test_resume_hard_fails_different_execution_policy_with_same_repeat_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results"
    first_policy, first_sha256 = _write_repeat_execution_policy(
        tmp_path, repeat_count=2
    )
    second_policy, second_sha256 = _write_repeat_execution_policy(
        tmp_path,
        repeat_count=2,
        max_billable_attempts=3,
        name="execution-policy-second.json",
    )
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first",
            mock_output=_mock_output(),
            repeat_count=2,
            execution_policy_uri=str(first_policy),
            expected_execution_policy_sha256=first_sha256,
        )
    )
    durable_before = _snapshot_files(results_root)
    monkeypatch.setattr(
        per_case_runner,
        "_solver_for_config",
        lambda *_args, **_kwargs: pytest.fail("policy mismatch reached provider"),
    )

    with pytest.raises(
        PerCaseRunnerError, match="execution_policy_sha256 does not match"
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second",
                mock_output=_mock_output(),
                repeat_count=2,
                execution_policy_uri=str(second_policy),
                expected_execution_policy_sha256=second_sha256,
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before


def test_per_case_runner_does_not_publish_retryable_or_grounded_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"
    solver = _ResponseVerificationSolver(
        raw_output='{"case_assessment": "cut off"',
        metadata={
            "provider": "example-provider",
            "model_id": "example-model",
            "model_version_or_snapshot": "2026-05-14",
            "response_verification_schema_version": (
                "legalforecast.response_verification.v1"
            ),
            "response_grounding_artifacts_detected": "true",
            "response_grounding_artifact_paths": (
                '["$.output[0].type=web_search_call"]'
            ),
            "response_finish_reason": "max_tokens",
            "response_truncated": "true",
            "response_retryable_ops_event": "true",
            "response_retryable_ops_event_reason": "response_truncated:max_tokens",
            "response_content_filter": "false",
        },
    )

    def fake_solver_for_config(*_args: Any, **_kwargs: Any) -> Any:
        return solver

    monkeypatch.setattr(per_case_runner, "_solver_for_config", fake_solver_for_config)
    with pytest.raises(PerCaseRunnerError, match="grounding or search artifacts"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                mock_output=_mock_output(),
            )
        )

    assert not (output_dir / "runs.jsonl").exists()
    assert not (output_dir / "accounting.jsonl").exists()
    assert not (output_dir / "metrics.json").exists()
    log_text = (output_dir / "runner-log.jsonl").read_text(encoding="utf-8")
    assert "runner_failed" in log_text


def test_per_case_runner_rejects_retryable_response_before_publish() -> None:
    runner_module = cast(Any, per_case_runner)

    with pytest.raises(PerCaseRunnerError, match="requires retry"):
        runner_module._require_publishable_response_verification(
            {
                "grounding_artifacts_detected": False,
                "retryable_ops_event_count": 1,
            }
        )


def test_per_case_runner_rejects_nonpositive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            timeout_seconds=0,
        )


def test_per_case_runner_rejects_nonpositive_repeat_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repeat_count must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            repeat_count=0,
        )


def test_per_case_runner_resolves_model_registry_entry(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert runs[0]["solver_id"] == "example-provider:example-model"
    metadata = cast(dict[str, Any], runs[0]["metadata"])
    assert metadata["provider"] == "example-provider"
    metrics = json.loads(
        (tmp_path / "runner-output" / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["model_key"] == "example-provider:example-model"
    assert metrics["model_registry_sha256"] == sha256_file(registry_path)
    assert len(metrics["model_registry_entry_sha256"]) == 64


def test_resume_accepts_amended_registry_when_model_entry_is_unchanged(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    amended_registry_path = tmp_path / "model-registry-amended.json"
    _write_model_registry(amended_registry_path, ("example-model", "expensive-model"))

    resumed = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            mock_output=_mock_output(probability=0.91),
            model_registry_uri=str(amended_registry_path),
            model_key="example-provider:example-model",
            resume_existing=True,
        )
    )

    assert resumed.run_id == first.run_id
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]


def test_resume_accepts_legacy_metrics_with_matching_registry_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    metrics_path = results_root / "metrics" / "cycle-1" / f"{first.run_id}.metrics.json"
    legacy_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    del legacy_metrics["model_registry_entry_sha256"]
    _write_json(metrics_path, legacy_metrics)
    durable_before_resume = _snapshot_files(results_root)

    def reject_republish(*_args: object, **_kwargs: object) -> None:
        pytest.fail("legacy resume attempted to republish durable outputs")

    monkeypatch.setattr(per_case_runner, "_upload_path", reject_republish)

    resumed = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "second-output",
            mock_output=_mock_output(probability=0.91),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
            resume_existing=True,
        )
    )

    assert resumed.run_id == first.run_id
    runs = _read_jsonl(tmp_path / "second-output" / "runs.jsonl")
    assert "0.25" in runs[0]["raw_output"]
    assert "0.91" not in runs[0]["raw_output"]
    assert _snapshot_files(results_root) == durable_before_resume


def test_resume_hard_fails_legacy_metrics_with_unknown_registry_hash(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    first = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    metrics_path = results_root / "metrics" / "cycle-1" / f"{first.run_id}.metrics.json"
    legacy_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    del legacy_metrics["model_registry_entry_sha256"]
    legacy_metrics["model_registry_sha256"] = "0" * 64
    _write_json(metrics_path, legacy_metrics)
    durable_before_resume = _snapshot_files(results_root)

    with pytest.raises(
        PerCaseRunnerError,
        match="model_registry_sha256 does not match",
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before_resume


def test_resume_rejects_amended_registry_when_model_entry_changed(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    results_root = tmp_path / "results-store"
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(registry_path, ("example-model",))
    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "first-output",
            mock_output=_mock_output(probability=0.25),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )
    amended_registry_path = tmp_path / "model-registry-amended.json"
    _write_model_registry(
        amended_registry_path,
        ("example-model", "expensive-model"),
        input_price_by_model={"example-model": 9.99},
    )
    durable_before_resume = _snapshot_files(results_root)

    with pytest.raises(
        PerCaseRunnerError,
        match="model_registry_entry_sha256 does not match",
    ):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                results_store_root=str(results_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "second-output",
                mock_output=_mock_output(probability=0.91),
                model_registry_uri=str(amended_registry_path),
                model_key="example-provider:example-model",
                resume_existing=True,
            )
        )

    assert _snapshot_files(results_root) == durable_before_resume


def test_per_case_runner_rejects_unknown_model_key(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    with pytest.raises(PerCaseRunnerError, match="model_key not found"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:missing",
            )
        )


def test_per_case_runner_rejects_packet_before_release_anchor_after_one_registry_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-13"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )
    original_loader = per_case_runner.load_model_registry
    registry_load_count = 0

    def counted_loader(path: Path) -> Any:
        nonlocal registry_load_count
        registry_load_count += 1
        return original_loader(path)

    monkeypatch.setattr(per_case_runner, "load_model_registry", counted_loader)

    with pytest.raises(PerCaseRunnerError, match="precedes release anchor"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
            )
        )
    assert registry_load_count == 1


@dataclass(frozen=True, slots=True)
class _ResponseVerificationSolver:
    raw_output: str
    metadata: Mapping[str, str]

    @property
    def solver_id(self) -> str:
        return "example-provider:example-model"

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.CONFIGURED_MODEL_STUB

    def solve(self, _request: HarnessRequest) -> SolverResponse:
        return SolverResponse(
            raw_output=self.raw_output,
            input_tokens=10,
            output_tokens=2,
            estimated_cost=0.01,
            metadata=self.metadata,
        )


def _write_store_fixture(
    tmp_path: Path,
    *,
    packet_record: dict[str, object],
    manifest_sha256: str | None = None,
    hash_field: str = "sha256",
    extra_packet_fields: Mapping[str, object] | None = None,
) -> tuple[Path, Path, str]:
    store_root = tmp_path / "packet-store"
    packet_key = "model-packets/cycle-1/case-1/full_packet.json"
    packet_path = store_root / packet_key
    _write_json(packet_path, packet_record)
    packet_sha256 = sha256_file(packet_path)
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": packet_key,
                    hash_field: manifest_sha256 or packet_sha256,
                    "size_bytes": packet_path.stat().st_size,
                    "content_type": "application/json",
                    "decision_date": packet_record.get("decision_date"),
                    **dict(extra_packet_fields or {}),
                }
            ],
        },
    )
    return store_root, manifest_path, packet_sha256


def _packet_record(
    *,
    decision_date: str = "2026-05-17",
    packet_text: str = "Fixture complaint text.",
) -> dict[str, object]:
    document = PacketDocument(
        source_document_id="doc-complaint",
        document_role=DocumentRole.COMPLAINT,
        docket_entry_number=12,
        source_provider="fixture",
        source_url_or_reference="fixture://case-1/doc-complaint",
        source_sha256=sha256_text(packet_text),
        text=packet_text,
        text_sha256=sha256_text(packet_text),
        packet_section="filings",
    )
    unit = PredictionUnit(
        unit_id="unit-1",
        count="I",
        claim_name="Breach of contract",
        defendant_group="Example Defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.97,
        source_citations=(
            SourceCitation(
                document_id="doc-complaint",
                docket_entry_number=12,
                excerpt="Breach of contract claim.",
            ),
        ),
    )
    packet = ModelPacket(
        candidate_id="cand-1",
        case_id="case-1",
        court="D. Example",
        docket_number="1:26-cv-00001",
        ablation=PacketAblation.FULL_PACKET,
        metadata={"decision_date": decision_date, "fixture": "true"},
        documents=(document,),
        prediction_units=(unit,),
        excluded_document_ids=(),
        decision_date=decision_date,
    )
    return packet.to_record()


def _mock_output(*, probability: float = 0.25) -> str:
    return json.dumps(
        {
            "case_assessment": "The motion has modest dismissal risk.",
            "predictions": [
                {
                    "unit_id": "unit-1",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_model_registry(
    path: Path,
    model_ids: tuple[str, ...],
    *,
    input_price_by_model: dict[str, float] | None = None,
    provider: str = "example-provider",
    context_limit: int = 200_000,
    max_output_tokens: int = 4_096,
    output_token_price: float = 1.0,
    long_context_surcharge: dict[str, int | float] | None = None,
    release_timestamp: str = "2026-05-14T09:00:00Z",
) -> None:
    prices = input_price_by_model or {}
    records: list[dict[str, Any]] = []
    for model_id in model_ids:
        record: dict[str, Any] = {
            "provider": provider,
            "model_id": model_id,
            "display_name": model_id,
            "model_version_or_snapshot": f"{model_id}-2026-05-14",
            "release_timestamp": release_timestamp,
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": "not_disclosed",
            "provider_training_cutoff": None,
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": max_output_tokens,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": context_limit,
            "pricing_source": "fixture",
            "input_token_price": prices.get(model_id, 0.25),
            "output_token_price": output_token_price,
            "known_cutoff_publicity_caveats": [],
        }
        if long_context_surcharge is not None:
            record["long_context_surcharge"] = long_context_surcharge
        records.append(record)
    _write_json(
        path,
        records,
    )


def _write_execution_policy(
    path: Path,
    *,
    provider: str = "example-provider",
) -> str:
    artifact = generate_execution_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_series": "official",
            "allow_no_baselines": True,
            "labeling_policy_sha256": "a" * 64,
            "cohort_policy_sha256": "b" * 64,
            "cohort_observation_manifest_sha256": "c" * 64,
            "lifecycle": {
                "labeling_policy_published_at": "2026-07-12T20:00:00Z",
                "production_labeling_started_at": "2026-07-13T00:00:00Z",
                "cohort_policy_published_at": "2026-07-12T19:00:00Z",
                "batch_002_started_at": "2026-07-12T21:00:00Z",
            },
            "shard_schedule": {
                "shard_count": 2,
                "dispatch_unit": "model_key_ablation",
                "shards": [
                    {
                        "model_key": f"{provider}:example-model",
                        "ablation": ablation,
                    }
                    for ablation in ("full_packet", "metadata_only")
                ],
            },
            "concurrency_policy": {
                "mode": "shard_identity",
                "identity_fields": ["cycle_id", "model_key", "ablation"],
            },
            "receipt_policy": {
                "write_once_per_attempt": True,
                "identity_fields": [
                    "workflow_run_id",
                    "workflow_run_attempt",
                ],
                "result_commitment_required": True,
            },
            "attempt_policy": {
                "authority_backend": "dynamodb",
                "authority_resource_identity_sha256": "e" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "provider_account_caps": [
                    {
                        "provider": provider,
                        "account": "primary",
                        "cap_microusd": 1_000_000_000,
                    }
                ],
                "reservation_ledger_sha256": "d" * 64,
                "max_billable_attempts": 2,
                "failure_threshold": 3,
                "failure_window_seconds": 300,
            },
            "repeat_policy": {"case_ids": ["case-1"], "count": 1},
            "cadence_counts": {
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count_source": "frozen_units",
                "reject_operator_mismatch": True,
            },
        }
    )
    _write_json(path, artifact)
    return cast(str, artifact["policy_sha256"])


def _write_repeat_execution_policy(
    tmp_path: Path,
    *,
    repeat_count: int,
    max_billable_attempts: int = 2,
    name: str = "execution-policy.json",
) -> tuple[Path, str]:
    artifact = generate_execution_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_series": "official",
            "allow_no_baselines": True,
            "labeling_policy_sha256": "a" * 64,
            "cohort_policy_sha256": "b" * 64,
            "cohort_observation_manifest_sha256": "c" * 64,
            "lifecycle": {
                "labeling_policy_published_at": "2026-07-12T20:00:00Z",
                "production_labeling_started_at": "2026-07-13T00:00:00Z",
                "cohort_policy_published_at": "2026-07-12T19:00:00Z",
                "batch_002_started_at": "2026-07-12T21:00:00Z",
            },
            "shard_schedule": {
                "shard_count": 2,
                "dispatch_unit": "model_key_ablation",
                "shards": [
                    {"model_key": "fixture:model-a", "ablation": ablation}
                    for ablation in ("full_packet", "metadata_only")
                ],
            },
            "concurrency_policy": {
                "mode": "shard_identity",
                "identity_fields": ["cycle_id", "model_key", "ablation"],
            },
            "receipt_policy": {
                "write_once_per_attempt": True,
                "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
                "result_commitment_required": True,
            },
            "attempt_policy": {
                "authority_backend": "dynamodb",
                "authority_resource_identity_sha256": "e" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "provider_account_caps": [
                    {
                        "provider": "fixture",
                        "account": "primary",
                        "cap_microusd": 1_000_000_000,
                    }
                ],
                "reservation_ledger_sha256": "d" * 64,
                "max_billable_attempts": max_billable_attempts,
                "failure_threshold": 3,
                "failure_window_seconds": 300,
            },
            "repeat_policy": {"case_ids": ["case-1"], "count": repeat_count},
            "cadence_counts": {
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count_source": "frozen_units",
                "reject_operator_mismatch": True,
            },
        }
    )
    path = tmp_path / name
    _write_json(path, artifact)
    return path, cast(str, artifact["policy_sha256"])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _snapshot_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_supplementary_mode_executes_a_post_anchor_model_end_to_end(
    tmp_path: Path,
) -> None:
    """Drive the REAL execution path with a post-anchor registry.

    This is the execution proof for the supplementary lane. It runs
    ``run_per_case_evaluation`` -- the same entry the Actions provider cell
    calls -- against a registry whose model was released after the packet's
    decision date, which is precisely the configuration the official
    release-anchor gate refuses. It must produce a complete run record.

    Provider-free: ``mock_output`` stands in for the provider response, so no
    HTTP call and no spend occur.
    """

    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-13"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(
        registry_path,
        ("example-model",),
        release_timestamp="2026-08-13T00:00:00Z",
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
            supplementary=True,
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert runs[0]["solver_id"] == "example-provider:example-model"
    metrics = json.loads(
        (tmp_path / "runner-output" / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["model_key"] == "example-provider:example-model"
    assert metrics["model_registry_sha256"] == sha256_file(registry_path)


def test_official_mode_still_refuses_the_same_post_anchor_registry(
    tmp_path: Path,
) -> None:
    """The identical inputs without the flag must still be refused."""

    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-13"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(
        registry_path,
        ("example-model",),
        release_timestamp="2026-08-13T00:00:00Z",
    )

    with pytest.raises(PerCaseRunnerError, match="precedes release anchor"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
            )
        )


def test_supplementary_mode_refuses_an_official_classed_model(
    tmp_path: Path,
) -> None:
    """The inverted gate is fail-closed the other way too.

    A pre-anchor (official-classed) model must not be routable through the
    supplementary lane, or the lane would become a way around the official
    gates.
    """

    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-17"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_model_registry(
        registry_path,
        ("example-model",),
        release_timestamp="2026-05-14T09:00:00Z",
    )

    with pytest.raises(PerCaseRunnerError, match="requires a post-anchor model"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
                supplementary=True,
            )
        )

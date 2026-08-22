from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals import per_case_runner
from legalforecast.evals.inspect_task import HarnessRequest
from legalforecast.evals.live_model_solver import LiveModelSolver
from legalforecast.evals.per_case_runner import (
    PerCaseRunnerConfig,
    PerCaseRunnerError,
    run_per_case_evaluation,
)
from tests.test_per_case_runner import (  # pyright: ignore[reportPrivateUsage]
    _committed_prompt_sha256,
    _packet_record,
    _write_execution_policy,
    _write_model_registry,
    _write_store_fixture,
)


def test_live_runner_binds_manifest_prompt_at_live_solver_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIVE must carry the manifest hash into the real solver before spend/HTTP."""

    packet_record = _packet_record()
    committed = _committed_prompt_sha256(packet_record)
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=packet_record,
        extra_packet_fields={"prompt_sha256": committed},
    )
    registry_path = tmp_path / "registry.json"
    _write_model_registry(registry_path, ("example-model",), provider="openai")
    execution_policy_path = tmp_path / "execution-policy.json"
    execution_policy_sha256 = _write_execution_policy(
        execution_policy_path, provider="openai"
    )
    spend_requests: list[HarnessRequest] = []
    transport_requests: list[object] = []

    def forbidden_attempt_handler(request: HarnessRequest) -> Any:
        spend_requests.append(request)
        raise AssertionError("spend handler constructed for refused prompt")

    def forbidden_transport(request: object, _timeout_seconds: float) -> Any:
        transport_requests.append(request)
        raise AssertionError("provider transport called for refused prompt")

    def live_solver_for_config(
        _config: PerCaseRunnerConfig,
        *,
        registry_entry: Any,
        model_registry_sha256: str | None,
        **_kwargs: Any,
    ) -> LiveModelSolver:
        return LiveModelSolver(
            registry_entry=registry_entry,
            model_registry_sha256=model_registry_sha256,
            transport=forbidden_transport,
            environ={"OPENAI_API_KEY": "fixture-secret"},
            attempt_handler_factory=forbidden_attempt_handler,
        )

    monkeypatch.setattr(per_case_runner, "_solver_for_config", live_solver_for_config)

    with pytest.raises(
        PerCaseRunnerError,
        match="actual provider prompt does not match",
    ):
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
                execution_policy_uri=str(execution_policy_path),
                expected_execution_policy_sha256=execution_policy_sha256,
                workflow_run_id="123",
                workflow_run_attempt=1,
                expected_packet_object_key=(
                    "model-packets/cycle-1/case-1/full_packet.json"
                ),
                expected_packet_sha256=packet_sha256,
                provider_authority_table="authority-table",
                provider_account="primary",
            )
        )

    assert spend_requests == []
    assert transport_requests == []

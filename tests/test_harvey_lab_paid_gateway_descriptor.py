"""Provider-free tests for the native Harvey LAB paid descriptor issuer."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import legalforecast.multiharness.harvey_lab_paid_gateway_descriptor as issuer
import legalforecast.multiharness.harvey_lab_protected_operator as protected_operator
import pytest
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
    load_paid_gateway_config,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.harvey_lab_protected_operator import (
    ProtectedHarveyLabOperatorRequest,
)
from legalforecast.multiharness.paid_gateway_descriptor import (
    PAID_GATEWAY_MAX_REQUESTS_PER_CASE,
    write_paid_gateway_descriptor,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
)

from test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from test_paid_gateway_descriptor import (
    _CEILING_MICROUSD,
    _ENVIRONMENT,
    _registry_bytes,
)


def test_issuer_binds_authentic_lab_inputs_and_loads_for_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, projection, private, registry = _prepared_inputs(tmp_path)
    monkeypatch.setattr(issuer, "harvey_lab_v1_1_pin", lambda: FIXTURE_PIN)

    descriptor = issuer.issue_harvey_lab_paid_gateway_descriptor(
        source_root=source,
        projection_root=projection,
        evaluator_private_root=private,
        model_registry_path=registry,
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    output = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(output, descriptor)
    loaded = load_paid_gateway_config(
        output,
        model_registry_path=registry,
        environment=_ENVIRONMENT,
    )

    assert loaded.harness_id == CLAUDE_CODE_HARVEY_LAB_HARNESS_ID
    assert loaded.max_requests == PAID_GATEWAY_MAX_REQUESTS_PER_CASE
    assert loaded.harvey_lab_task_id == ISSUE_196_LAB_TASK_ID
    assert loaded.harvey_lab_source_commit == FIXTURE_PIN.commit
    assert loaded.harvey_lab_source_tree == FIXTURE_PIN.tree
    assert loaded.harvey_lab_projection_manifest_sha256
    assert loaded.harvey_lab_private_material_sha256
    record = json.loads(output.read_text(encoding="utf-8"))
    assert "forecast_release_digest" not in record
    assert "approval_reference" not in record
    assert "ANTHROPIC_API_KEY" not in output.read_text(encoding="utf-8")


def test_issuer_reprojects_private_rubric_before_emitting_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, projection, private, registry = _prepared_inputs(tmp_path)
    monkeypatch.setattr(issuer, "harvey_lab_v1_1_pin", lambda: FIXTURE_PIN)
    _make_writable(private)
    task_path = private / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["criteria"][0]["match_criteria"] = "modified private rubric"
    task_path.write_text(json.dumps(task), encoding="utf-8")

    with pytest.raises(
        ProtectedTerminalPaidError,
        match="evaluator-private bytes",
    ):
        issuer.issue_harvey_lab_paid_gateway_descriptor(
            source_root=source,
            projection_root=projection,
            evaluator_private_root=private,
            model_registry_path=registry,
            model_key="anthropic:claude-sonnet-4-5",
            ceiling_microusd=_CEILING_MICROUSD,
            account="official",
            environment=_ENVIRONMENT,
        )


def test_protected_runtime_consumes_descriptor_issued_from_authentic_lab_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, projection, private, registry = _prepared_inputs(tmp_path)
    monkeypatch.setattr(issuer, "harvey_lab_v1_1_pin", lambda: FIXTURE_PIN)
    descriptor = issuer.issue_harvey_lab_paid_gateway_descriptor(
        source_root=source,
        projection_root=projection,
        evaluator_private_root=private,
        model_registry_path=registry,
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    paid_config = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(paid_config, descriptor)
    for name, value in _ENVIRONMENT.items():
        monkeypatch.setenv(name, value)

    adapter = ClaudeCodeCliAdapter(
        execution_service=SimpleNamespace(parent_env={}),  # type: ignore[arg-type]
        output_format="stream-json",
        verbose=True,
    )
    observed_factory: dict[str, object] = {}

    def build_adapter(**kwargs: object) -> SimpleNamespace:
        observed_factory.update(kwargs)
        return SimpleNamespace(delegate=adapter)

    monkeypatch.setattr(
        protected_operator,
        "build_claude_code_container_adapter",
        build_adapter,
    )
    monkeypatch.setattr(
        protected_operator,
        "build_dynamodb_spend_authority",
        lambda *_args, **_kwargs: object(),
    )
    request = ProtectedHarveyLabOperatorRequest(
        source_root=source,
        projection_root=projection,
        evaluator_private_root=private,
        run_root=tmp_path / "run",
        evaluator_bin_dir=tmp_path / "bin",
        paid_config_path=paid_config,
        model_registry_path=registry,
        solver_image_digest="sha256:" + "a" * 64,
        gateway_image_digest="sha256:" + "b" * 64,
        model_key="anthropic:claude-sonnet-4-5",
        pin=FIXTURE_PIN,
    )

    runtime = protected_operator.build_protected_harvey_lab_runtime(request)

    assert runtime.model == "claude-sonnet-4-5"
    assert runtime.ceiling_microusd == _CEILING_MICROUSD
    assert runtime.adapter is adapter
    assert observed_factory["paid_config_path"] == paid_config.resolve()
    assert observed_factory["model_registry_path"] == registry.resolve()
    assert observed_factory["harness_id"] == "claude-code-harvey-lab"


def _prepared_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source = _issue_196_source(tmp_path / "source")
    projection = tmp_path / "projection"
    private = tmp_path / "private"
    project_harvey_lab_suite(
        source_root=source,
        solver_root=projection,
        evaluator_private_root=private,
        pin=FIXTURE_PIN,
    )
    registry = tmp_path / "model-registry.json"
    registry.write_bytes(_registry_bytes())
    return source, projection, private, registry


def _make_writable(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o755)
        else:
            path.chmod(0o644)
    root.chmod(0o755)

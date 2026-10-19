# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import io
import json
import zipfile
from functools import partial
from pathlib import Path

import legalforecast.multiharness.harvey_lab_protected_operator as protected_operator
import pytest
from legalforecast.evals.provider_spend_control import AttemptLease, ProviderSpendKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
)
from legalforecast.multiharness.harvey_lab.core_cli import register
from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionHarveyLabEvaluatorRunner,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.harvey_lab_protected_operator import (
    ProtectedHarveyLabOperatorRequest,
    ProtectedHarveyLabRuntime,
    _evaluator_configuration,
    run_protected_harvey_lab_operator,
)
from legalforecast.multiharness.harvey_lab_protected_spend import (
    ProtectedHarveyLabJudgeBoundary,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import UsageObservation

from test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from test_model_gateway_paid import _ENVIRONMENT, _files
from test_multiharness_claude_clean_native_lab_e2e import (
    _install_binaries,
    _make_writable,
)

PRICING_SHA256 = "sha256:" + "9" * 64


class _AuthorityDouble:
    def __init__(self) -> None:
        self.key: ProviderSpendKey | None = None
        self.marked: AttemptLease | None = None
        self.response: dict[str, object] | None = None

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        self.key = key
        return AttemptLease(
            attempt_id="1" * 64,
            authority_identity_sha256="2" * 64,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=1,
            reservation_microusd=reservation_microusd,
        )

    def mark_transport_started(self, lease: AttemptLease) -> None:
        self.marked = lease

    def record_response(self, lease: AttemptLease, **values: object) -> None:
        self.response = {"lease": lease, **values}


def test_protected_judge_boundary_uses_descriptor_authority_and_settles_response(
    tmp_path: Path,
) -> None:
    from legalforecast.multiharness.container_harness.model_gateway_paid import (
        load_paid_gateway_config,
    )

    config_path, registry_path, _record = _files(tmp_path)
    config = load_paid_gateway_config(
        config_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )
    authority = _AuthorityDouble()
    boundary = ProtectedHarveyLabJudgeBoundary(
        authority=authority,  # type: ignore[arg-type]
        config=config,
    )
    request = HarveyLabJudgeRequest(ordinal=1, criterion_id="c01")
    lease = boundary.before_judge_call(request)
    boundary.mark_transport_started(request)
    response = ProductionJudgeResponse(
        verdict="pass",
        judge_resolved_identity=config.registry_entry.model_id,
        usage=UsageObservation(
            basis="estimated_from_pricing_snapshot",
            pricing_snapshot_sha256=PRICING_SHA256,
            input_tokens=10,
            output_tokens=1,
            reported_cost_usd="0.000123",
        ),
        raw_response=b"provider response",
    )
    boundary.after_judge_response(request, lease, response)

    assert authority.key is not None
    assert authority.key.cycle_id == config.spend.cycle_id
    assert authority.key.case_id == "harvey-lab-judge-1:gateway:1"
    assert authority.marked == lease
    assert authority.response is not None
    assert authority.response["actual_microusd"] == 123
    assert authority.response["input_tokens"] == 10
    assert authority.response["output_tokens"] == 1


class _SolverDouble:
    def __init__(self) -> None:
        self.parent_env: dict[str, str] = {}
        self.calls = 0

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        self.calls += 1
        output = spec.working_directory / "output"
        output.mkdir(exist_ok=True)
        (output / "issue-identification-memo.docx").write_bytes(_docx_bytes())
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "model": "claude-sonnet-4-6",
                "result": {"deliverable": "memo", "status": "complete"},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return ExecutionReceipt.from_transcript(
            spec,
            stdout=stdout,
            served_model="claude-sonnet-4-6",
        )


class _JudgeBoundaryDouble(HarveyLabJudgeRequestBoundary):
    def __init__(self) -> None:
        self.before: list[tuple[int, int]] = []
        self.after: list[tuple[int, int]] = []

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        ordinal = request.ordinal
        attempt = request.attempt_index
        self.before.append((ordinal, attempt))
        return (ordinal, attempt)

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        identity = (request.ordinal, request.attempt_index)
        assert reservation == identity
        assert isinstance(observation, UsageObservation)
        self.after.append(identity)


def test_run_clean_native_cli_consumes_prepared_inputs_and_calls_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _issue_196_source(tmp_path / "source")
    projection = tmp_path / "projection"
    private = tmp_path / "private"
    project_harvey_lab_suite(
        source_root=source,
        solver_root=projection,
        evaluator_private_root=private,
        pin=FIXTURE_PIN,
    )
    env = _install_binaries(tmp_path)
    solver = _SolverDouble()
    boundary = _JudgeBoundaryDouble()
    runtime = _protected_runtime(solver=solver, boundary=boundary, env=env)
    run_root = tmp_path / "run"
    args = _run_clean_native_args(
        tmp_path=tmp_path,
        source=source,
        projection=projection,
        private=private,
        run_root=run_root,
    )
    _install_runtime_double(monkeypatch, runtime)
    try:
        assert args.handler(args) == 0
    finally:
        _make_writable(tmp_path)

    report = json.loads(capsys.readouterr().out)
    assert report == {
        "execution_mode": "production",
        "n_criteria": 23,
        "n_passed": 23,
        "score": 1,
        "task_id": "employment-labor/identify-issues-in-counterparty-motion-brief",
    }
    assert len(boundary.before) == len(boundary.after) == 23
    assert solver.calls == 1
    assert (run_root / "sealed" / "issue-identification-memo.docx").is_file()


def test_run_clean_native_cli_rejects_modified_private_criterion_pretransport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _issue_196_source(tmp_path / "source")
    projection = tmp_path / "projection"
    private = tmp_path / "private"
    project_harvey_lab_suite(
        source_root=source,
        solver_root=projection,
        evaluator_private_root=private,
        pin=FIXTURE_PIN,
    )
    _make_writable(private)
    task_json = private / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
    task = json.loads(task_json.read_text(encoding="utf-8"))
    task["criteria"][0]["match_criteria"] = "tampered criterion"
    task_json.write_text(json.dumps(task, sort_keys=True), encoding="utf-8")

    solver = _SolverDouble()
    boundary = _JudgeBoundaryDouble()
    runtime = _protected_runtime(
        solver=solver,
        boundary=boundary,
        env=_install_binaries(tmp_path),
    )
    args = _run_clean_native_args(
        tmp_path=tmp_path,
        source=source,
        projection=projection,
        private=private,
        run_root=tmp_path / "run",
    )
    _install_runtime_double(monkeypatch, runtime)

    with pytest.raises(
        ClaudeCodeCliAdapterError,
        match="prepared Harvey LAB evaluator-private bytes",
    ) as exc_info:
        args.handler(args)

    assert solver.calls == 0
    assert boundary.before == []
    assert "tampered criterion" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("tamper", "error_match"),
    [
        ("missing", "file census.*missing:.*gold-answers.json"),
        ("extra", "file census.*extra:.*unexpected.json"),
        ("symlink", "must not contain symlinks"),
    ],
)
def test_run_clean_native_cli_rejects_invalid_private_tree_pretransport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    error_match: str,
) -> None:
    source = _issue_196_source(tmp_path / "source")
    projection = tmp_path / "projection"
    private = tmp_path / "private"
    project_harvey_lab_suite(
        source_root=source,
        solver_root=projection,
        evaluator_private_root=private,
        pin=FIXTURE_PIN,
    )
    _make_writable(private)
    task_root = private / "tasks" / ISSUE_196_LAB_TASK_ID
    if tamper == "missing":
        (task_root / "gold-answers.json").unlink()
    elif tamper == "extra":
        (task_root / "unexpected.json").write_text("{}", encoding="utf-8")
    else:
        task_json = task_root / "task.json"
        task_json.unlink()
        task_json.symlink_to(source / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json")

    solver = _SolverDouble()
    boundary = _JudgeBoundaryDouble()
    runtime = _protected_runtime(
        solver=solver,
        boundary=boundary,
        env=_install_binaries(tmp_path),
    )
    args = _run_clean_native_args(
        tmp_path=tmp_path,
        source=source,
        projection=projection,
        private=private,
        run_root=tmp_path / "run",
    )
    _install_runtime_double(monkeypatch, runtime)

    with pytest.raises(ClaudeCodeCliAdapterError, match=error_match):
        args.handler(args)

    assert solver.calls == 0
    assert boundary.before == []


def _protected_runtime(
    *,
    solver: _SolverDouble,
    boundary: _JudgeBoundaryDouble,
    env: dict[str, str],
) -> ProtectedHarveyLabRuntime:
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=_judge_call,
        attempt_writer=lambda _call, _response: None,
        max_attempts=1,
        expected_judge_identity="claude-sonnet-4-6",
    )
    provenance = _evaluator_configuration(
        FIXTURE_PIN,
        model_id="claude-sonnet-4-6",
        pricing_sha256=PRICING_SHA256,
    )
    return ProtectedHarveyLabRuntime(
        adapter=ClaudeCodeCliAdapter(
            execution_service=solver,  # type: ignore[arg-type]
            output_format="stream-json",
            verbose=True,
        ),
        evaluator_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=env,
        ),
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance.provenance_for_execution,
        model="claude-sonnet-4-6",
        ceiling_microusd=1_000_000,
    )


def _run_clean_native_args(
    *,
    tmp_path: Path,
    source: Path,
    projection: Path,
    private: Path,
    run_root: Path,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers())
    return parser.parse_args(
        [
            "harvey-lab",
            "run-clean-native",
            "--source-root",
            str(source),
            "--projection-dir",
            str(projection),
            "--evaluator-private-dir",
            str(private),
            "--run-dir",
            str(run_root),
            "--evaluator-bin-dir",
            str(tmp_path / "bin"),
            "--paid-config",
            str(tmp_path / "paid.json"),
            "--model-registry",
            str(tmp_path / "registry.json"),
            "--solver-image",
            "sha256:" + "a" * 64,
            "--gateway-image",
            "sha256:" + "b" * 64,
            "--model-key",
            "anthropic:claude-sonnet-4-6",
        ]
    )


def _install_runtime_double(
    monkeypatch: pytest.MonkeyPatch,
    runtime: ProtectedHarveyLabRuntime,
) -> None:
    def run_double(request: ProtectedHarveyLabOperatorRequest):
        return run_protected_harvey_lab_operator(request, runtime=runtime)

    monkeypatch.setattr(
        protected_operator,
        "run_protected_harvey_lab_operator",
        run_double,
    )
    request_type = ProtectedHarveyLabOperatorRequest
    monkeypatch.setattr(
        protected_operator,
        "ProtectedHarveyLabOperatorRequest",
        partial(request_type, pin=FIXTURE_PIN),
    )


def _judge_call(call: ProductionJudgeCall) -> ProductionJudgeResponse:
    return ProductionJudgeResponse(
        verdict="pass",
        judge_resolved_identity="claude-sonnet-4-6",
        usage=UsageObservation(
            basis="estimated_from_pricing_snapshot",
            pricing_snapshot_sha256=PRICING_SHA256,
            input_tokens=10,
            output_tokens=1,
            reported_cost_usd="0.000001",
        ),
        raw_response=f"judge-{call.request.ordinal}".encode(),
    )


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
                "Fixture legal memorandum"
                "</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
    return buffer.getvalue()

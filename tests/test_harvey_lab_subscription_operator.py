# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import io
import json
import zipfile
from functools import partial
from pathlib import Path

import pytest
from legalforecast.multiharness import (
    harvey_lab_subscription_operator as subscription_operator,
)
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
from legalforecast.multiharness.harvey_lab_subscription_judge import (
    SubscriptionJudgeBoundary,
    SubscriptionProvenanceProvider,
)
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    CommunitySubscriptionOperatorRequest,
    CommunitySubscriptionRuntime,
    build_community_subscription_runtime,
    run_community_subscription_harvey_lab,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import UsageObservation

from test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from test_multiharness_claude_clean_native_lab_e2e import (
    _install_binaries,
    _make_writable,
)


def test_subscription_judge_boundary_accepts_only_unallocable_usage() -> None:
    boundary = SubscriptionJudgeBoundary()
    request = HarveyLabJudgeRequest(ordinal=1, criterion_id="c01")
    reservation = boundary.before_judge_call(request)
    observation = UsageObservation(
        basis="subscription_unallocable",
        input_tokens=10,
        output_tokens=1,
        unknown_reason="flat_subscription_has_no_per_call_allocation",
    )
    boundary.after_judge_call(request, reservation, observation)


def test_runtime_uses_distinct_subscription_services_and_blinds_private_root(
    tmp_path: Path,
) -> None:
    request = CommunitySubscriptionOperatorRequest(
        source_root=tmp_path / "source",
        projection_root=tmp_path / "projection",
        evaluator_private_root=tmp_path / "private",
        run_root=tmp_path / "run",
        evaluator_bin_dir=tmp_path / "bin",
        claude_version="fixture-version",
        claude_sha256="a" * 64,
        solver_model="sonnet",
        judge_model="sonnet",
        pin=FIXTURE_PIN,
    )

    runtime = build_community_subscription_runtime(request)
    solver_service = runtime.adapter.execution_service

    assert solver_service is not runtime.judge_service
    assert solver_service.auth_profile == "contributor-subscription"
    assert runtime.judge_service.auth_profile == "contributor-subscription"
    assert solver_service.credential_source is None
    assert runtime.judge_service.credential_source is None
    assert solver_service.filesystem_read_paths == (request.projection_root,)
    assert request.evaluator_private_root not in solver_service.filesystem_read_paths
    assert solver_service.filesystem_write_paths == (
        request.run_root / "solver-workspace",
    )
    assert runtime.judge_service.filesystem_read_paths == ()


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


def test_run_community_subscription_cli_seals_then_judges_with_null_cost(
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
    runtime = _subscription_runtime(solver=solver, boundary=boundary, env=env)
    run_root = tmp_path / "run"
    args = _run_subscription_args(
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
    assert report["auth_profile"] == "contributor-subscription"
    assert report["cost"] == {
        "amount_usd": None,
        "basis": "subscription_unallocable",
        "unknown_reason": "flat_subscription_has_no_per_call_allocation",
    }
    assert report["execution_mode"] == "community-subscription"
    assert report["score"] == 1
    assert report["solver_model_requested"] == "sonnet"
    assert report["solver_model_observed"] == "claude-sonnet-4-6"
    assert report["judge_model_requested"] == "sonnet"
    assert report["judge_model_observed"] == "anthropic/claude-sonnet-4-6"
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
    runtime = _subscription_runtime(
        solver=solver,
        boundary=boundary,
        env=_install_binaries(tmp_path),
    )
    args = _run_subscription_args(
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
    runtime = _subscription_runtime(
        solver=solver,
        boundary=boundary,
        env=_install_binaries(tmp_path),
    )
    args = _run_subscription_args(
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


def _subscription_runtime(
    *,
    solver: _SolverDouble,
    boundary: _JudgeBoundaryDouble,
    env: dict[str, str],
) -> CommunitySubscriptionRuntime:
    solver.parent_env = env
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=_judge_call,
        attempt_writer=lambda _call, _response: None,
        max_attempts=1,
        allow_subscription_unallocable=True,
    )
    provenance = SubscriptionProvenanceProvider(
        pin=FIXTURE_PIN,
        requested_model="sonnet",
        claude_sha256="a" * 64,
    )
    return CommunitySubscriptionRuntime(
        adapter=ClaudeCodeCliAdapter(
            execution_service=solver,  # type: ignore[arg-type]
            output_format="stream-json",
            verbose=True,
        ),
        judge_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=env,
        ),
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance,
    )


def _run_subscription_args(
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
            "run-community-subscription",
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
            "--claude-version",
            "fixture-version",
            "--claude-sha256",
            "a" * 64,
            "--solver-model",
            "sonnet",
            "--judge-model",
            "sonnet",
        ]
    )


def _install_runtime_double(
    monkeypatch: pytest.MonkeyPatch,
    runtime: CommunitySubscriptionRuntime,
) -> None:
    def run_double(request: CommunitySubscriptionOperatorRequest):
        return run_community_subscription_harvey_lab(request, runtime=runtime)

    monkeypatch.setattr(
        subscription_operator,
        "run_community_subscription_harvey_lab",
        run_double,
    )
    request_type = CommunitySubscriptionOperatorRequest
    monkeypatch.setattr(
        subscription_operator,
        "CommunitySubscriptionOperatorRequest",
        partial(request_type, pin=FIXTURE_PIN),
    )


def _judge_call(call: ProductionJudgeCall) -> ProductionJudgeResponse:
    return ProductionJudgeResponse(
        verdict="pass",
        judge_resolved_identity="anthropic/claude-sonnet-4-6",
        usage=UsageObservation(
            basis="subscription_unallocable",
            input_tokens=10,
            output_tokens=1,
            unknown_reason="flat_subscription_has_no_per_call_allocation",
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

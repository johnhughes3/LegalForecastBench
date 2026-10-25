# pyright: reportPrivateUsage=false

"""Offline behavior checks for native Codex plus the common subscription judge."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapterError
from legalforecast.multiharness.codex_cli import CodexCliAdapter, CodexCliAdapterError
from legalforecast.multiharness.harvey_lab_projection import project_harvey_lab_suite
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    CommunitySubscriptionOperatorError,
    CommunitySubscriptionOperatorRequest,
    build_community_subscription_runtime,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from tests.test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from tests.test_harvey_lab_subscription_operator import (
    _install_runtime_double,
    _JudgeBoundaryDouble,
    _role_configs,
    _run_subscription_args,
    _SolverDouble,
    _subscription_runtime,
)
from tests.test_multiharness_claude_clean_native_lab_e2e import (
    _install_binaries,
    _make_writable,
)
from tests.test_tier0_operator_half import _docx_bytes


def _request(tmp_path: Path) -> CommunitySubscriptionOperatorRequest:
    solver, judge = _role_configs(tmp_path)
    (solver / ".credentials.json").unlink()
    auth = solver / "auth.json"
    auth.write_text("synthetic", encoding="utf-8")
    auth.chmod(0o600)
    return CommunitySubscriptionOperatorRequest(
        source_root=tmp_path / "source",
        projection_root=tmp_path / "projection",
        evaluator_private_root=tmp_path / "private",
        run_root=tmp_path / "run",
        evaluator_bin_dir=tmp_path / "bin",
        solver_config_dir=solver,
        judge_config_dir=judge,
        claude_version="claude-fixture",
        claude_sha256="a" * 64,
        codex_version="codex-fixture",
        codex_sha256="b" * 64,
        harness="codex",
        solver_model="gpt-fixture",
        judge_model="sonnet",
        pin=FIXTURE_PIN,
    )


def test_codex_runtime_has_separate_native_pins_and_auth_roots(tmp_path: Path) -> None:
    request = _request(tmp_path)
    runtime = build_community_subscription_runtime(request)
    assert isinstance(runtime.adapter, CodexCliAdapter)
    solver = runtime.adapter.execution_service
    assert isinstance(solver, LocalCliExecutionService)
    assert solver.auth_profile == CONTRIBUTOR_SUBSCRIPTION
    assert solver.credential_source is None
    assert solver.executable_pin is not None
    assert solver.executable_pin.basename == "codex"
    assert solver.executable_pin.sha256 == "b" * 64
    assert "--ignore-user-config" in solver.executable_pin.required_flags
    assert runtime.judge_service.executable_pin is not None
    assert runtime.judge_service.executable_pin.basename == "claude"
    assert runtime.judge_service.credential_source is None
    assert solver.filesystem_read_paths == (request.projection_root,)
    assert runtime.judge_service.filesystem_read_paths == ()


@pytest.mark.parametrize("missing", ["codex_version", "codex_sha256"])
def test_codex_pin_must_be_explicit(tmp_path: Path, missing: str) -> None:
    request = replace(_request(tmp_path), **{missing: None})
    with pytest.raises(CommunitySubscriptionOperatorError, match="explicit --codex"):
        build_community_subscription_runtime(request)


@pytest.mark.parametrize("mode", ["success", "tampered-private", "turn-failed"])
def test_codex_subscription_cli_seals_then_uses_same_claude_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
) -> None:
    source = _issue_196_source(tmp_path / "source")
    projection, private = tmp_path / "projection", tmp_path / "private"
    project_harvey_lab_suite(
        source_root=source,
        solver_root=projection,
        evaluator_private_root=private,
        pin=FIXTURE_PIN,
    )
    if mode == "tampered-private":
        _make_writable(private)
        task_json = next(private.rglob("task.json"))
        private_task = json.loads(task_json.read_text())
        private_task["criteria"][0]["match_criteria"] = "modified criterion"
        task_json.write_text(json.dumps(private_task))
    env = _install_binaries(tmp_path)
    # Only basename presence is used; actual model execution below is an offline double.
    (tmp_path / "bin" / "codex").touch(mode=0o700)
    boundary = _JudgeBoundaryDouble()
    runtime = _subscription_runtime(solver=_SolverDouble(), boundary=boundary, env=env)
    service = LocalCliExecutionService(
        auth_profile=CONTRIBUTOR_SUBSCRIPTION, parent_env=env
    )
    runtime = replace(
        runtime,
        adapter=CodexCliAdapter(
            execution_service=service, auth_profile=CONTRIBUTOR_SUBSCRIPTION
        ),
    )
    args = _run_subscription_args(
        tmp_path=tmp_path,
        source=source,
        projection=projection,
        private=private,
        run_root=tmp_path / "run",
    )
    args.harness, args.solver_model = "codex", "gpt-fixture"
    args.codex_version, args.codex_sha256 = "codex-fixture", "b" * 64
    executed: list[RunSpec] = []
    original_execute = LocalCliExecutionService.execute

    def execute_double(
        self: LocalCliExecutionService, spec: RunSpec
    ) -> ExecutionReceipt:
        if spec.argv[0] != "codex":
            return original_execute(self, spec)
        executed.append(spec)
        assert not (spec.working_directory / "task" / "gold-answers.json").exists()
        output = spec.working_directory / "output"
        output.mkdir(exist_ok=True)
        (output / "issue-identification-memo.docx").write_bytes(
            _docx_bytes("Fixture memo")
        )
        events = [
            {
                "type": "thread.started",
                "thread_id": "fixture",
                "actual_model": "gpt-fixture",
            },
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "Completed memo"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        ]
        if mode == "turn-failed":
            events[-1] = {"type": "turn.failed", "error": {"message": "failed"}}
        return ExecutionReceipt.from_transcript(
            spec, stdout="\n".join(json.dumps(event) for event in events)
        )

    monkeypatch.setattr(LocalCliExecutionService, "execute", execute_double)
    _install_runtime_double(monkeypatch, runtime)
    try:
        if mode == "success":
            assert args.handler(args) == 0
        else:
            with pytest.raises(
                ClaudeCodeCliAdapterError
                if mode == "tampered-private"
                else CodexCliAdapterError
            ):
                args.handler(args)
            assert boundary.before == []
            assert len(executed) == (0 if mode == "tampered-private" else 1)
            return
    finally:
        _make_writable(tmp_path)
    report = json.loads(capsys.readouterr().out)
    assert report["harness"] == "codex"
    assert report["solver_model_observed"] == "gpt-fixture"
    assert report["judge_model_observed"] == "anthropic/claude-sonnet-4-6"
    assert report["cost"]["amount_usd"] is None
    assert report["cost"]["basis"] == "subscription_unallocable"
    assert report["score"] == 1
    assert len(boundary.before) == len(boundary.after) == 23
    assert len(executed) == 1
    assert "--ignore-user-config" in executed[0].argv
    assert "--ignore-rules" in executed[0].argv
    assert "--ephemeral" in executed[0].argv

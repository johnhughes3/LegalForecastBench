# pyright: reportPrivateUsage=false
"""Exercise native preflight followed by the real contained execution service."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Literal

import pytest
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.claude_code import build_claude_invocation_plan
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    CommunitySubscriptionOperatorError,
    CommunitySubscriptionOperatorRequest,
    build_community_subscription_runtime,
    preflight_community_subscription_runtime,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_identity import sha256_file
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

from test_harvey_lab_projection import FIXTURE_PIN
from test_harvey_lab_subscription_judge import _production_judge_call


@pytest.mark.parametrize(
    ("harness", "claude_supports_allowed_tools"),
    [("claude-code", True), ("codex", True), ("claude-code", False), ("codex", False)],
)
def test_native_preflight_then_actual_solver_and_bound_judge_launch(
    tmp_path: Path,
    harness: Literal["claude-code", "codex"],
    claude_supports_allowed_tools: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # These credential-free doubles exercise a local subscription runtime.
    # The production CI refusal has separate negative coverage.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    binary_root = tmp_path / "bin"
    binary_root.mkdir()
    flags = (
        "--print --output-format --json-schema --tools --allowedTools "
        "--strict-mcp-config "
        "--no-session-persistence --setting-sources --model --add-dir --safe-mode "
        "--json --color --ephemeral --skip-git-repo-check --strict-config "
        "--ignore-user-config --ignore-rules --sandbox --cd --config "
        "--output-last-message"
    )
    for executable in ("claude", "codex"):
        binary = binary_root / executable
        help_flags = (
            flags.replace("--allowedTools ", "")
            if executable == "claude" and not claude_supports_allowed_tools
            else flags
        )
        # Use the system shell rather than PATH-selected Python: hosted runners
        # can select a second toolcache interpreter outside the contained paths.
        terminal = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "modelUsage": {"claude-sonnet-fixture": {"inputTokens": 2}},
                "structured_output": {"verdict": "pass"},
            }
        )
        binary.write_text(
            "#!/bin/sh\n"
            'case "$*" in\n'
            "  --version) printf '%s\\n' '1.2.3' ;;\n"
            f"  *--help*) printf '%s\\n' {shlex.quote(help_flags)} ;;\n"
            "  'auth status --json') printf '%s\\n' "
            '\'{"loggedIn":true,"authMethod":"claude.ai",'
            '"subscriptionType":"max"}\' ;;\n'
            "  'login status') printf '%s\\n' 'Logged in using ChatGPT' >&2 ;;\n"
            "  *) printf '%s\\n' \"$@\" > native-argv.txt\n"
            "     cat >/dev/null\n"
            f"     printf '%s\\n' {shlex.quote(terminal)} ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        binary.chmod(0o700)
    role_roots: list[Path] = []
    for role, filename in (
        ("solver", "auth.json" if harness == "codex" else ".credentials.json"),
        ("judge", ".credentials.json"),
    ):
        root = tmp_path / f"{role}-auth"
        root.mkdir(mode=0o700)
        credential = root / filename
        credential.write_text("synthetic", encoding="utf-8")
        credential.chmod(0o600)
        role_roots.append(root)
    projection = tmp_path / "projection"
    projection.mkdir()
    request = CommunitySubscriptionOperatorRequest(
        source_root=tmp_path / "source",
        projection_root=projection,
        evaluator_private_root=tmp_path / "private",
        run_root=tmp_path / "run",
        evaluator_bin_dir=binary_root,
        solver_config_dir=role_roots[0],
        judge_config_dir=role_roots[1],
        claude_version="1.2.3",
        claude_sha256=sha256_file(binary_root / "claude"),
        codex_version="1.2.3",
        codex_sha256=sha256_file(binary_root / "codex"),
        harness=harness,
        solver_model="fixture-model",
        judge_model="sonnet",
        pin=FIXTURE_PIN,
    )
    original = build_community_subscription_runtime(request)
    if harness == "claude-code" and not claude_supports_allowed_tools:
        with pytest.raises(
            CommunitySubscriptionOperatorError, match="capability preflight"
        ):
            preflight_community_subscription_runtime(request, original)
        assert not request.run_root.exists()
        return
    runtime = preflight_community_subscription_runtime(request, original)
    service = runtime.adapter.execution_service
    assert isinstance(service, LocalCliExecutionService)
    assert service.executable_pin is not None
    assert service.executable_pin.required_flags == ()
    original_service = original.adapter.execution_service
    assert isinstance(original_service, LocalCliExecutionService)
    assert original_service.executable_pin is not None
    assert original_service.executable_pin.required_flags
    assert service.executable_pin.sha256 == original_service.executable_pin.sha256
    workspace = request.run_root / "solver-workspace"
    workspace.mkdir(parents=True)
    argv = ("codex" if harness == "codex" else "claude", "fixture-run")
    if harness == "claude-code":
        plan = build_claude_invocation_plan(
            prompt="Create the requested fixture deliverable.",
            model=request.solver_model,
            required_unit_ids=(),
            workspace=workspace,
            output_schema_path=workspace / "output-schema.json",
            allowed_tools=("Read", "Bash", "Write"),
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        )
        argv = plan.argv
    receipt = service.execute(
        RunSpec(
            spec_id="native-launch-regression",
            argv=argv,
            working_directory=workspace,
            environment={},
            timeout_seconds=30,
            stdin_bytes=b"fixture prompt",
        )
    )
    assert receipt.status == "succeeded", receipt.stderr
    assert json.loads(receipt.stdout)["subtype"] == "success"
    if harness == "claude-code":
        native_argv = (
            (workspace / "native-argv.txt").read_text(encoding="utf-8").splitlines()
        )
        assert native_argv[native_argv.index("--tools") + 1] == "Read,Bash,Write"
        assert native_argv[native_argv.index("--allowedTools") + 1] == (
            "Read,Bash,Write"
        )
    # Invoke the runner's actual bound judge callable, not a separately built judge.
    response = runtime.evaluator_runner._provider_call(_production_judge_call(tmp_path))
    assert response.verdict == "pass"
    assert response.judge_resolved_identity == "anthropic/claude-sonnet-fixture"

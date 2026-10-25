# pyright: reportPrivateUsage=false
"""Exercise native preflight followed by the real contained execution service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    CommunitySubscriptionOperatorRequest,
    build_community_subscription_runtime,
    preflight_community_subscription_runtime,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_identity import sha256_file
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

from test_harvey_lab_projection import FIXTURE_PIN
from test_harvey_lab_subscription_judge import _production_judge_call


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
def test_native_preflight_then_actual_solver_and_bound_judge_launch(
    tmp_path: Path, harness: Literal["claude-code", "codex"]
) -> None:
    binary_root = tmp_path / "bin"
    binary_root.mkdir()
    flags = (
        "--print --output-format --json-schema --tools --strict-mcp-config "
        "--no-session-persistence --setting-sources --model --add-dir --safe-mode "
        "--json --color --ephemeral --skip-git-repo-check --strict-config "
        "--ignore-user-config --ignore-rules --sandbox --cd --config "
        "--output-last-message"
    )
    for executable in ("claude", "codex"):
        binary = binary_root / executable
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']:\n"
            "    print('1.2.3')\n"
            "elif '--help' in args:\n"
            f"    print({flags!r})\n"
            "elif args == ['auth', 'status', '--json']:\n"
            "    print(json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', "
            "'subscriptionType': 'max'}))\n"
            "elif args == ['login', 'status']:\n"
            "    print('Logged in using ChatGPT', file=sys.stderr)\n"
            "else:\n"
            "    sys.stdin.read()\n"
            "    print(json.dumps({'type': 'result', 'subtype': 'success', "
            "'is_error': False, 'modelUsage': {'claude-sonnet-fixture': "
            "{'inputTokens': 2}}, 'structured_output': {'verdict': 'pass'}}))\n",
            encoding="utf-8",
        )
        binary.chmod(0o700)
    role_roots = []
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
    runtime = preflight_community_subscription_runtime(request, original)
    service = runtime.adapter.execution_service
    assert isinstance(service, LocalCliExecutionService)
    assert service.executable_pin is not None
    assert service.executable_pin.required_flags == ()
    assert original.adapter.execution_service.executable_pin is not None
    assert original.adapter.execution_service.executable_pin.required_flags
    assert service.executable_pin.sha256 == (
        original.adapter.execution_service.executable_pin.sha256
    )
    workspace = request.run_root / "solver-workspace"
    workspace.mkdir(parents=True)
    receipt = service.execute(
        RunSpec(
            spec_id="native-launch-regression",
            argv=("codex" if harness == "codex" else "claude", "fixture-run"),
            working_directory=workspace,
            environment={},
            timeout_seconds=30,
            stdin_bytes=b"fixture prompt",
        )
    )
    assert receipt.status == "succeeded"
    assert json.loads(receipt.stdout)["subtype"] == "success"
    # Invoke the runner's actual bound judge callable, not a separately built judge.
    response = runtime.evaluator_runner._provider_call(_production_judge_call(tmp_path))
    assert response.verdict == "pass"
    assert response.judge_resolved_identity == "anthropic/claude-sonnet-fixture"

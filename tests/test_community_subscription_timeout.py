# pyright: reportPrivateUsage=false

"""The community timeout must reach the native solver and subscription judge."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest
from legalforecast.multiharness.claude_code import claude_code_local_manifest
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapter,
    load_codex_local_cli_manifest,
)
from legalforecast.multiharness.community_subscription_sandbox import (
    CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION,
)
from legalforecast.multiharness.harvey_lab_projection import project_harvey_lab_suite
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    build_community_subscription_runtime,
    run_community_subscription_harvey_lab,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_identity import sha256_file
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

from test_codex_lab_subscription_operator import _request
from test_harvey_lab_projection import _issue_196_source
from test_harvey_lab_subscription_judge import _production_judge_call


class _ReachedNativeLaunch(Exception):
    pass


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
@pytest.mark.parametrize("timeout", [45, 900])
def test_community_timeout_reaches_solver_and_judge_specs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: Literal["claude-code", "codex"],
    timeout: int,
) -> None:
    request = replace(_request(tmp_path), harness=harness, timeout_seconds=timeout)
    if harness == "claude-code":
        request = replace(
            request, claude_version=CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION
        )
        (request.solver_config_dir / "auth.json").rename(
            request.solver_config_dir / ".credentials.json"
        )
    _issue_196_source(request.source_root)
    project_harvey_lab_suite(
        source_root=request.source_root,
        solver_root=request.projection_root,
        evaluator_private_root=request.evaluator_private_root,
        pin=request.pin,
    )
    # PATH presence is checked before the captured execute boundary. Provide
    # fixture executables rather than depending on locally installed vendors.
    monkeypatch.setenv("PATH", "/usr/bin")
    request.evaluator_bin_dir.mkdir()
    for executable in ("claude", "codex"):
        binary = request.evaluator_bin_dir / executable
        binary.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        binary.chmod(0o700)
    if harness == "codex":
        request = replace(
            request,
            codex_sha256=sha256_file(request.evaluator_bin_dir / "codex"),
        )
    runtime = build_community_subscription_runtime(request)
    observed: list[RunSpec] = []

    def capture_launch(
        _service: LocalCliExecutionService, spec: RunSpec
    ) -> ExecutionReceipt:
        observed.append(spec)
        raise _ReachedNativeLaunch

    monkeypatch.setattr(LocalCliExecutionService, "execute", capture_launch)
    with pytest.raises(_ReachedNativeLaunch):
        run_community_subscription_harvey_lab(request, runtime=runtime)
    assert observed[-1].timeout_seconds == timeout
    # Both paths use the actual operator-built production runner's judge closure.
    with pytest.raises(_ReachedNativeLaunch):
        runtime.evaluator_runner._provider_call(_production_judge_call(tmp_path))
    assert observed[-1].timeout_seconds == timeout
    # The operator overrides only its own runtime, not checked-in adapter defaults.
    default = (
        load_codex_local_cli_manifest()
        if isinstance(runtime.adapter, CodexCliAdapter)
        else claude_code_local_manifest()
    )
    assert default.timeout_retry.timeout_seconds == 120

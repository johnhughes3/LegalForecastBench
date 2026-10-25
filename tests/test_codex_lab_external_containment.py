# pyright: reportPrivateUsage=false
"""The subscription Codex mode keeps the whole-process filesystem boundary."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapterError,
    plan_contained_codex_exec,
)
from legalforecast.multiharness.codex_cli_harvey_lab_invocation import (
    externally_contained_plan,
)
from legalforecast.multiharness.contributor_boundary import (
    LINUX_LANDLOCK_FS_SCOPE,
    wrap_argv_for_contributor_boundary,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService


def test_external_plan_preserves_native_controls_and_reports_actual_mode(
    tmp_path: Path,
) -> None:
    plan = plan_contained_codex_exec(
        prompt="Read task files and write output.",
        model="test-model",
        workspace=tmp_path,
        timeout_seconds=900,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    service = LocalCliExecutionService(
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        filesystem_scope=LINUX_LANDLOCK_FS_SCOPE,
    )
    external = externally_contained_plan(plan, service)
    assert plan.public_config()["sandbox"] == "workspace-write"
    assert external.public_config()["sandbox"] == "danger-full-access"
    expected = list(plan.argv)
    expected[expected.index("--sandbox") + 1] = "danger-full-access"
    assert external.argv == tuple(expected)
    assert external.stdin == plan.stdin


@pytest.mark.parametrize(
    "profile,scope",
    [
        (CONTRIBUTOR_SUBSCRIPTION, None),
        ("fixture_none", LINUX_LANDLOCK_FS_SCOPE),
    ],
)
def test_external_plan_refuses_missing_subscription_or_landlock(
    tmp_path: Path,
    profile: str,
    scope: str | None,
) -> None:
    plan = plan_contained_codex_exec(
        prompt="Write output.",
        model="test-model",
        workspace=tmp_path,
        timeout_seconds=900,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    service = LocalCliExecutionService(auth_profile=profile, filesystem_scope=scope)
    with pytest.raises(
        CodexCliAdapterError, match="subscription execution with Landlock"
    ):
        externally_contained_plan(plan, service)


def test_external_shell_retains_private_read_and_write_denial(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    private = tmp_path / "private-rubric.txt"
    private.write_text("synthetic private rubric")
    # Shell positional arguments avoid interpolating paths into command text.
    argv = (
        "/bin/sh",
        "-c",
        'printf memo > output.txt; if cat "$1"; then exit 91; fi; '
        'if printf changed > "$1"; then exit 92; fi; cat output.txt',
        "probe",
        str(private),
    )
    wrapped, _identity = wrap_argv_for_contributor_boundary(
        argv, scratch_root=workspace
    )
    result = subprocess.run(
        wrapped,
        cwd=workspace,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "memo"
    assert "Permission denied" in result.stderr
    assert private.read_text() == "synthetic private rubric"
    assert (workspace / "output.txt").read_text() == "memo"

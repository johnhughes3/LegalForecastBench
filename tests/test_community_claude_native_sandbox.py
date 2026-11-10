"""Opt-in native Claude startup enforcement without login or model requests."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    SubscriptionRuntimeAccess,
)
from legalforecast.multiharness.claude_code import build_claude_invocation_plan
from legalforecast.multiharness.community_subscription_sandbox import (
    CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION,
    claude_plan,
)
from legalforecast.multiharness.contributor_boundary import LINUX_LANDLOCK_FS_SCOPE
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService


@pytest.mark.skipif(
    os.environ.get("LFB_CLAUDE_SANDBOX_E2E") != "1",
    reason="set LFB_CLAUDE_SANDBOX_E2E=1 for credential-free native Claude startup",
)
def test_actual_claude_refuses_unavailable_sandbox_before_auth_or_model(
    tmp_path: Path,
) -> None:
    located = shutil.which("claude")
    assert located is not None
    executable = Path(located).resolve(strict=True)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "synthetic-auth"
    empty_bin = tmp_path / "empty-bin"
    for directory in (workspace, auth, empty_bin):
        directory.mkdir(mode=0o700)
    alias = empty_bin / "claude"
    alias.symlink_to(executable)
    pin = executable_pin_for(
        alias,
        version=CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION,
        distribution_kind="standalone-cli",
    )
    assert pin.sha256 == (
        "bfb3703ad5380242328459bc62ada4bde8ae7ba57c6e1eeadb9c00e08874c478"
    )
    canary = auth / ".credentials.json"
    canary.write_text("synthetic-not-a-credential", encoding="utf-8")
    canary.chmod(0o600)

    class SyntheticPresence:
        def prove(self, parent_env: object) -> SubscriptionRuntimeAccess:
            del parent_env
            return SubscriptionRuntimeAccess(
                environment=(("CLAUDE_CONFIG_DIR", str(auth)),),
                read_paths=(auth,),
                write_paths=(auth,),
            )

    plan = claude_plan(
        build_claude_invocation_plan(
            prompt="Unused: sandbox startup must refuse before a model request.",
            model="unused",
            required_unit_ids=("synthetic-unit",),
            workspace=workspace,
            output_schema_path=workspace / "schema.json",
            allowed_tools=("Read", "Bash", "Write", "Edit"),
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        ),
        auth_root=auth,
    )
    # Keep only the pinned Claude alias in PATH, hiding bwrap/socat discovery.
    # The remaining argv/settings and the execution service are production paths.
    service = LocalCliExecutionService(
        adapter_id="claude-native-startup-e2e",
        adapter_version=CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
        executable_pin=pin,
        parent_env={"PATH": str(empty_bin)},
        filesystem_scope=LINUX_LANDLOCK_FS_SCOPE,
        subscription_presence=SyntheticPresence(),
        filesystem_write_paths=(workspace,),
        run_in_working_directory=True,
    )
    receipt = service.execute(
        RunSpec(
            spec_id="claude-native-required-sandbox",
            argv=plan.argv,
            working_directory=workspace,
            timeout_seconds=30,
        )
    )
    assert receipt.status == "failed", receipt.stderr
    assert receipt.returncode == 1
    assert "sandbox required but unavailable" in receipt.stderr
    assert "sandbox.failIfUnavailable is set" in receipt.stderr
    assert "refusing to start without a working sandbox" in receipt.stderr
    assert not receipt.stdout
    assert canary.read_text(encoding="utf-8") == "synthetic-not-a-credential"

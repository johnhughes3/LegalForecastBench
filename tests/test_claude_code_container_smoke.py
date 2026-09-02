"""One live, in-container Claude Code run against the operator's subscription.

This is the pathfinder for the whole multiharness lane, so it is the test that
is allowed to be slow and is not allowed to be reassuring.  It runs the real
CLI, with its real tools, inside the digest-pinned image, behind the allowlist
egress proxy, on the real login, and then asserts the things that make the
result mean anything:

1. the run completed and the answer projected;
2. the harness actually called at least one of its own tools -- a tools-on lane
   whose runs use no tools has measured the bare API through a costly wrapper;
3. general internet was refused -- the run itself attempts one non-allowlisted
   host and the proxy's refusal list has to show it;
4. no provider-executed web retrieval was possible or happened -- the run's
   own ``init`` event lists no web tool, and the provider's own
   ``server_tool_use`` counters come back at zero.  Both are evidence, rather
   than a claim about the argv that was meant to remove them;
5. the answer is the one that required reading a file in the workspace, so the
   tools were load-bearing rather than decorative.

It is skipped unless ``LFB_LIVE_SMOKE=1``.  One attempt, no retries: a failure
here is a real result and is reported as one.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.container_harness.parsers import (
    parse_claude_code_stream,
)
from legalforecast.multiharness.harness_lane.adapter import ContainerCliAdapter
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("LFB_LIVE_SMOKE") != "1",
    reason="set LFB_LIVE_SMOKE=1 to run one live containerized Claude Code smoke",
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "examples"
    / "adapters"
    / "claude-code-native"
    / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "claude-code-container-tools-on"
BUILD_COMMAND = (
    "docker build -t lfb-harness/claude-code:2.1.251 "
    "-f infra/harness-images/claude-code/Dockerfile "
    "infra/harness-images/claude-code"
)
# Not a word the model can guess, so answering it is proof the file was read.
SENTINEL = "PLANTAGENET"
BLOCKED_HOST = "example.com"
SMOKE_MODEL = os.environ.get("LFB_LIVE_SMOKE_MODEL", "sonnet")
SMOKE_PROMPT = (
    "Do these three steps in order, using your tools.\n"
    "1. Run this bash command and note whether it succeeded or was blocked: "
    f"curl -sS --max-time 15 https://{BLOCKED_HOST}/\n"
    "2. Read the file case.txt in your working directory.\n"
    "3. Reply with exactly the single word that case.txt contains, "
    "and nothing else."
)
PROVIDER_HOSTS = ("api.anthropic.com", "platform.claude.com")


def test_live_containerized_claude_code_uses_its_tools_behind_the_fence(
    tmp_path: Path,
) -> None:
    manifest = LocalCliAdapterManifest.from_record(
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    )
    image = manifest.executable.container_image_digest
    assert image is not None
    _require_local_image(image)
    config_dir = _stage_subscription_login(tmp_path)

    workspace = tmp_path / "run"
    container_workspace = workspace / "container-workspace"
    container_workspace.mkdir(mode=0o700, parents=True)
    (container_workspace / "case.txt").write_text(f"{SENTINEL}\n", encoding="utf-8")

    adapter = builtin_adapter_registry().get(
        REGISTRY_NAME,
        local_cli_manifest=manifest,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        allow_hosts=PROVIDER_HOSTS,
        parent_env={"CLAUDE_CONFIG_DIR": str(config_dir)},
    )
    assert isinstance(adapter, ContainerCliAdapter)

    # No provider key reaches the container by construction: the child
    # environment is HOME plus the proxy variables plus whatever the harness
    # descriptor declares, and for `claude` that is nothing.
    spec = adapter.container_spec(_request(manifest), workspace)
    assert "ANTHROPIC_API_KEY" not in spec.environment
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in spec.environment

    result = adapter.run(_request(manifest), workspace)
    stdout = (workspace / "container-logs").glob("*.stdout")
    transcript = next(iter(sorted(stdout))).read_text(encoding="utf-8")
    parsed = parse_claude_code_stream(transcript)
    summary = result.public_summary

    # (1) it completed and the answer projected.
    assert summary["exit_code"] == 0, f"exit {summary['exit_code']}"
    assert summary["timed_out"] is False
    assert parsed.failure_class is None, (
        f"terminal event says subtype={parsed.subtype!r} "
        f"stop_reason={parsed.stop_reason!r} is_error={parsed.is_error}"
    )
    assert result.status == "succeeded"

    # (2) it used its own tools. Without this the lane has measured nothing.
    assert parsed.used_any_tool, (
        "the harness completed WITHOUT CALLING A SINGLE TOOL, so this run "
        "measured the bare API through a container, not the harness"
    )

    # (3) general internet was refused, proved by the run's own attempt.
    refused_hosts = {record["host"] for record in summary["egress_refused"]}
    assert BLOCKED_HOST in refused_hosts, (
        f"the proxy never refused {BLOCKED_HOST}; refusals were {refused_hosts}"
    )
    assert set(summary["egress_allowlist"]["hosts"]) == set(PROVIDER_HOSTS)

    # (4) the provider-executed web tools were not on the table, per the run's
    # own init event rather than per the flag that was meant to remove them.
    assert parsed.server_side_web_tools_available == (), (
        "server-side web tools were still available to this run: "
        f"{parsed.server_side_web_tools_available}"
    )
    # ...and the provider's own count of server-executed retrievals is zero,
    # which is the half the init tool list cannot cover: this CLI can surface
    # further tool schemas mid-run.
    assert parsed.server_side_web_requests == 0, (
        f"{parsed.server_side_web_requests} provider-executed web retrievals "
        "happened, entirely outside the container's egress fence"
    )
    # apiKeySource "none" means the subscription login was spent, not a key.
    assert parsed.api_key_source == "none"

    # (5) the deliverable is the answer, and the answer required the file.
    assert SENTINEL in parsed.answer.upper()


def _require_local_image(image: str) -> None:
    completed = subprocess.run(
        ("docker", "image", "inspect", "--format", "{{.Id}}", image),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        pytest.skip(
            f"{image} is not present in the local rootless Docker store; "
            f"build it with: {BUILD_COMMAND}"
        )


def _stage_subscription_login(tmp_path: Path) -> Path:
    """Copy only the Claude subscription login into a throwaway config dir.

    The operator's real credentials file also carries OAuth tokens for
    unrelated MCP services -- a court-records service among them -- and none of
    that belongs in a run whose whole premise is that it cannot reach the case
    outcomes.
    """

    source = Path.home() / ".claude" / ".credentials.json"
    if not source.is_file():
        pytest.skip(
            "no contributor-subscription login on this host; run 'claude' and "
            "complete the interactive login"
        )
    record = json.loads(source.read_text(encoding="utf-8"))
    login = record.get("claudeAiOauth")
    if not isinstance(login, dict):
        pytest.skip("the local Claude login has no claudeAiOauth section")
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir(mode=0o700)
    credentials = config_dir / ".credentials.json"
    credentials.write_text(json.dumps({"claudeAiOauth": login}), encoding="utf-8")
    credentials.chmod(0o600)
    return config_dir


def _request(manifest: LocalCliAdapterManifest) -> RunRequest:
    adapter_manifest = manifest.to_adapter_manifest(
        command=("legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",)
    )
    return RunRequest(
        request_id="claude-code-container-live-smoke",
        task=CanonicalTask(
            task_id="lfb:live-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="live-smoke",
            task_sha256="sha256:" + "1" * 64,
            metadata={"solver_prompt": SMOKE_PROMPT},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key=SMOKE_MODEL,
        sandbox_policy=SandboxPolicy(
            policy_id="live-smoke",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=manifest.timeout_retry.timeout_seconds,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )

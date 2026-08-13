"""Env-gated live smoke for the Codex CLI adapter envelope parser.

This module is skipped unless ``LFB_LIVE_SMOKE=1``. It runs one cheap
``codex exec`` with the exact non-interactive argv the offline plan produces,
stdin attached as a closed pipe (no TTY, so an approval prompt would hang and
trip the timeout). Live auth binding is ``LegalForecastBench-dm0g.4.4.10``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness.codex_cli import (
    build_codex_invocation_plan,
    parse_codex_jsonl,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("LFB_LIVE_SMOKE") != "1",
    reason="set LFB_LIVE_SMOKE=1 to run one cheap Codex exec smoke",
)

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "codex_cli_adapter" / "transcripts" / "success.json"
)
SMOKE_MODEL = os.environ.get("LFB_LIVE_SMOKE_MODEL", "gpt-5.1")
SMOKE_PROMPT = "Reply with the single word ok."
SHA256 = "sha256:" + "1" * 64


def test_live_codex_exec_completes_without_prompting_and_parses(
    tmp_path: Path,
) -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip(
            "plan argv uses --ignore-user-config; ChatGPT config.toml login "
            "is stripped. Set OPENAI_API_KEY after LegalForecastBench-dm0g.4.4.10."
        )
    request = _request(tmp_path)
    plan = build_codex_invocation_plan(request, tmp_path, prompt=SMOKE_PROMPT)
    assert "--ask-for-approval" not in plan.argv
    assert "--approve-for-me" not in plan.argv
    assert 'approval_policy="never"' in plan.argv
    assert plan.argv[-1] == "-"

    sqlite_home = tmp_path / "codex-sqlite"
    sqlite_home.mkdir()
    (tmp_path / "private-logs").mkdir(mode=0o700)
    env = dict(os.environ)
    env["CODEX_SQLITE_HOME"] = str(sqlite_home)
    # Prompt is delivered on stdin, then the pipe is closed (no TTY). An
    # approval prompt would hang and trip the timeout instead of completing.
    completed = subprocess.run(
        list(plan.argv),
        cwd=tmp_path,
        env=env,
        input=plan.stdin,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    envelope = parse_codex_jsonl(
        completed.stdout,
        requested_model_name=plan.requested_model,
        returncode=completed.returncode,
        timed_out=False,
        crashed=False,
    )
    fixture_types = _fixture_event_types()
    real_types = [
        str(event.get("type", ""))
        for event in envelope.events
        if str(event.get("type", ""))
    ]
    report = {
        "argv": list(plan.argv),
        "returncode": completed.returncode,
        "failure_class": envelope.failure_class,
        "real_event_types": real_types,
        "fixture_event_types": fixture_types,
        "stderr_preview": completed.stderr[:500],
        "model": SMOKE_MODEL,
        "reasoning_effort": plan.reasoning_effort,
        "input_tokens": envelope.input_tokens,
        "output_tokens": envelope.output_tokens,
    }
    (tmp_path / "live-smoke-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    assert completed.returncode == 0
    assert envelope.failure_class is None
    assert envelope.last_message.strip()


def _fixture_event_types() -> list[str]:
    body = "\n".join(
        line
        for line in SUCCESS_FIXTURE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("//")
    )
    record = cast(dict[str, Any], json.loads(body))
    events = record.get("envelope")
    if not isinstance(events, list):
        return []
    types: list[str] = []
    for event in events:
        if isinstance(event, dict) and isinstance(event.get("type"), str):
            types.append(str(event["type"]))
    return types


def _request(workspace: Path) -> RunRequest:
    del workspace
    return RunRequest(
        request_id="live-smoke",
        task=CanonicalTask(
            task_id="lfb:live-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="live-smoke",
            task_sha256=SHA256,
            metadata={"prompt": SMOKE_PROMPT, "reasoning_effort": "low"},
        ),
        adapter=AdapterManifest(
            adapter_id="codex-cli-offline",
            display_name="Codex CLI Offline Adapter",
            adapter_version="0.1.0",
            command=("python", "-m", "legalforecast.multiharness.codex_cli_cli"),
        ),
        model_key=f"codex:{SMOKE_MODEL}",
        sandbox_policy=SandboxPolicy(
            policy_id="live-smoke",
            backend="docker",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=90,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )

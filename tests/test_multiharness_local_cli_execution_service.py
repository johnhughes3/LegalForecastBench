from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapter,
    claude_code_manifest,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spec import CanonicalTask, RunRequest, SandboxPolicy

SOLVER_MODEL_KEY = "anthropic:claude-sonnet-4-6"
SUCCESS_ENVELOPE = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "model": "claude-sonnet-4-6",
    "total_cost_usd": 0.0,
    "usage": {
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "input_tokens": 11,
        "output_tokens": 7,
    },
    "result": {
        "case_assessment": "The public fixture supports a balanced forecast.",
        "predictions": [
            {
                "unit_id": "count_i",
                "probability_fully_dismissed": 0.7,
                "rationale": "Fixture rationale.",
            }
        ],
    },
}


def test_claude_adapter_uses_contained_service_without_vendor_binary(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    workspace = tmp_path / "workspace"
    payload = json.dumps(SUCCESS_ENVELOPE, separators=(",", ":"))
    _write_executable(
        bin_dir / "claude",
        "import sys; sys.stdout.write(" + repr(payload) + ")",
    )
    adapter = ClaudeCodeCliAdapter(
        execution_service=LocalCliExecutionService(parent_env=_parent_env(bin_dir))
    )
    result = adapter.run(_run_request(), workspace)
    assert result.status == "succeeded"
    assert "failure_class" not in result.public_summary
    assert result.artifacts[0].path == "deliverable-sealed/forecast.json"
    _make_writable(workspace / "deliverable-sealed")


def _parent_env(bin_dir: Path) -> dict[str, str]:
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
        "OPENAI_API_KEY": "ambient-openai-canary",
        "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    }


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!" + sys.executable + "\n" + body.strip() + "\n", encoding="utf-8"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        item.chmod(item.stat().st_mode | 0o200)


def _run_request() -> RunRequest:
    task = CanonicalTask(
        task_id="lfb:case-1:full_packet",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="legalforecast-mtd-v1",
        source_id="case-1",
        task_sha256="sha256:" + "1" * 64,
        metadata={
            "required_unit_ids": ["count_i"],
            "solver_prompt": "Forecast this fixture case.",
        },
    )
    policy = SandboxPolicy(
        policy_id="offline-cli",
        backend="none",
        image="none",
        network_policy="none",
        timeout_seconds=30,
        allowed_provider_env_vars=(),
    )
    return RunRequest(
        request_id="request-1",
        task=task,
        adapter=claude_code_manifest(),
        model_key=SOLVER_MODEL_KEY,
        sandbox_policy=policy,
        request_sha256="sha256:" + "3" * 64,
    )

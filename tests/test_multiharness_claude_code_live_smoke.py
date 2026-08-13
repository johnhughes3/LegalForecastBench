"""Env-gated live smoke for the Claude Code adapter envelope parser.

This module is excluded from the default suite. Set ``LFB_LIVE_SMOKE=1`` to
run one haiku-tier ``claude -p`` invocation using the same argv the offline
plan produces. Live auth binding is ``LegalForecastBench-dm0g.4.4.9``; this
smoke is optional verification, not CI.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness.claude_code import (
    build_claude_invocation_plan,
    classify_execution,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("LFB_LIVE_SMOKE") != "1",
    reason="set LFB_LIVE_SMOKE=1 to run one haiku-tier Claude Code smoke",
)

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "claude_code" / "transcripts" / "success.json"
)
SMOKE_MODEL = "claude-haiku-4-5"
SMOKE_PROMPT = 'Reply with JSON only: {"haiku": "ok"}'


def test_live_haiku_envelope_parses_and_is_compared_to_success_fixture(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "output-schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"haiku": {"type": "string"}},
                "required": ["haiku"],
                "additionalProperties": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    plan = build_claude_invocation_plan(
        prompt=SMOKE_PROMPT,
        model=SMOKE_MODEL,
        required_unit_ids=("count_i",),
        workspace=tmp_path,
        output_schema_path=schema_path,
    )
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN",
        }
    }
    env["HOME"] = str(isolated_home)
    completed = subprocess.run(
        list(plan.argv),
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    spec = RunSpec(
        spec_id="live-smoke",
        argv=plan.argv,
        working_directory=tmp_path,
        json_schema=plan.json_schema,
    )
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
        status="failed" if completed.returncode else "succeeded",
    )
    classified = classify_execution(
        spec,
        receipt,
        required_unit_ids=("count_i",),
        requested_model=SMOKE_MODEL,
    )
    real_envelope = _json_object(completed.stdout)
    fixture_envelope = _json_object(
        "\n".join(
            line
            for line in SUCCESS_FIXTURE.read_text(encoding="utf-8").splitlines()
            if not line.startswith("//")
        )
    )["envelope"]
    if not isinstance(fixture_envelope, dict):
        raise AssertionError("success fixture envelope must be an object")
    fixture_keys = set(cast(dict[str, Any], fixture_envelope))
    missing = sorted(fixture_keys.difference(real_envelope))
    extra = sorted(set(real_envelope).difference(fixture_keys))
    (tmp_path / "live-smoke-report.json").write_text(
        json.dumps(
            {
                "returncode": completed.returncode,
                "failure_class": (
                    None
                    if classified.failure_class is None
                    else classified.failure_class.value
                ),
                "cost_usd": real_envelope.get("total_cost_usd"),
                "missing_from_real": missing,
                "extra_in_real": extra,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    assert real_envelope.get("type") == "result"


def _json_object(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    decoded: object = json.loads(text)
    if not isinstance(decoded, dict):
        raise AssertionError("expected a JSON object")
    return cast(dict[str, Any], decoded)

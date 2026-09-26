"""Provider-free scored release smoke through the pinned rootless Claude image.

Opt in with ``LFB_TERMINAL_RELEASE_E2E_IMAGE=<local image ID>``. The fixture is
a local Anthropic-compatible server; no model provider or AWS call is made.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from legalforecast.release.synthetic import issue_synthetic_release

FIXTURE_SOURCE = (
    Path(__file__).parent / "fixtures" / "claude_code" / "release_fixture_server.py"
)


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *args),
        check=check,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _fixture_ready(container: str) -> None:
    for _attempt in range(50):
        probe = _docker(
            "exec",
            container,
            "/usr/bin/python3",
            "-c",
            "import socket; socket.create_connection(('127.0.0.1', 8081), 1).close()",
            check=False,
        )
        if probe.returncode == 0:
            return
        time.sleep(0.1)
    raise AssertionError(
        f"fixture server did not start: {_docker('logs', container).stdout}"
    )


def _read_json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _assert_bash_read(stdout_path: Path) -> str:
    records = [
        cast(dict[str, Any], json.loads(line))
        for line in stdout_path.read_text().splitlines()
    ]
    init = next(record for record in records if record.get("type") == "system")
    assert set(init["tools"]) == {"Bash", "StructuredOutput"}
    terminal = next(record for record in records if record.get("type") == "result")
    assert terminal["subtype"] == "success"
    assert terminal["is_error"] is False
    assert terminal["usage"]["server_tool_use"]["web_search_requests"] == 0
    assert terminal["usage"]["server_tool_use"]["web_fetch_requests"] == 0
    content: list[str] = []
    for record in records:
        if record.get("type") != "user":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        message = cast(dict[str, object], message)
        items = message.get("content")
        if not isinstance(items, list):
            continue
        for raw_item in cast(list[object], items):
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, object], raw_item)
            value = item.get("content")
            if (
                item.get("type") == "tool_result"
                and item.get("is_error") is False
                and isinstance(value, str)
            ):
                content.append(value)
    assert len(content) == 1
    text = content[0]
    unit_id = next(
        unit for unit in ("unit-001", "unit-002", "unit-003") if unit in text
    )
    assert f"Forecast whether {unit_id}" in text
    expected_document_count = 13 if unit_id == "unit-001" else 2
    assert text.count("Synthetic predecision material") == expected_document_count
    return unit_id


@pytest.mark.skipif(
    shutil.which("docker") is None
    or not os.environ.get("LFB_TERMINAL_RELEASE_E2E_IMAGE"),
    reason="set LFB_TERMINAL_RELEASE_E2E_IMAGE to a locally built Claude image ID",
)
@pytest.mark.parametrize("separate_scoring", [False, True])
@pytest.mark.parametrize("case_id", [None, "case-001"])
def test_rootless_release_run_reads_and_scores_every_selected_unit(
    tmp_path: Path,
    separate_scoring: bool,
    case_id: str | None,
) -> None:
    image_id = os.environ["LFB_TERMINAL_RELEASE_E2E_IMAGE"]
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    output_root = tmp_path / "run"
    suffix = uuid4().hex[:12]
    network = f"lfb-release-fixture-{suffix}"
    fixture = f"lfb-release-server-{suffix}"
    _docker("network", "create", network)
    try:
        started = _docker(
            "run",
            "-d",
            "--name",
            fixture,
            "--network",
            network,
            "--network-alias",
            "fixture-upstream",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--mount",
            f"type=bind,src={FIXTURE_SOURCE},dst=/opt/fixture.py,readonly",
            "--entrypoint",
            "/usr/bin/python3",
            image_id,
            "/opt/fixture.py",
        )
        assert started.stdout.strip(), started.stderr
        _fixture_ready(fixture)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("ANTHROPIC_", "AWS_"))
        }
        command = [
            "uv",
            "run",
            "legalforecast",
            "multiharness",
            "release-execute" if separate_scoring else "release-run",
            "--forecast-release",
            str(release_root / "forecast-release.json"),
            "--artifact-root",
            str(release_root),
            "--output-dir",
            str(output_root),
            "--model-key",
            "anthropic:claude-opus-5-5",
            "--image",
            image_id,
            "--fixture-base-url",
            "http://fixture-upstream:8081/v1",
            "--fixture-egress-network",
            network,
            "--timeout-seconds",
            "90",
            "--run-id",
            f"release-smoke-{suffix}",
        ]
        if case_id is not None:
            command.extend(("--case-id", case_id))
        if not separate_scoring:
            command.extend(
                ("--labels-release", str(release_root / "labels-release.json"))
            )
        run = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=420,
        )
        assert run.returncode == 0, run.stderr

        if separate_scoring:
            moved_root = tmp_path / "downloaded-run"
            shutil.move(output_root, moved_root)
            output_root = moved_root
            scored = subprocess.run(
                (
                    "uv",
                    "run",
                    "legalforecast",
                    "multiharness",
                    "release-score",
                    "--run-dir",
                    str(output_root),
                    "--forecast-release",
                    str(release_root / "forecast-release.json"),
                    "--labels-release",
                    str(release_root / "labels-release.json"),
                    "--artifact-root",
                    str(release_root),
                ),
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=60,
            )
            assert scored.returncode == 0, scored.stderr

        scores = _read_json(output_root / "scores.json")
        assert scores["selection"]["complete"] is True
        model = scores["models"][0]
        expected_count = 1 if case_id is not None else 2
        assert scores["selection"]["coverage_kind"] == (
            "scoped" if case_id is not None else "full"
        )
        assert scores["selection"]["full_release_selected"] is (case_id is None)
        assert model["selected_unit_count"] == expected_count
        assert model["completed_unit_count"] == expected_count
        assert model["failed_unit_count"] == 0
        expected_brier = 0.0625 if case_id is not None else 0.3125
        assert model["micro_brier"] == pytest.approx(expected_brier)
        assert model["equal_case_brier"] == pytest.approx(expected_brier)

        packages = sorted((output_root / "container-runs").glob("*/package"))
        assert len(packages) == (1 if case_id is not None else 3)
        observed_units: set[str] = set()
        for package in packages:
            result = _read_json(package / "result.json")
            usage = result["gateway_usage"]
            assert result["exit_code"] == 0
            assert result["timed_out"] is False
            assert usage["request_count"] == 3
            assert usage["rejected_count"] == 0
            proxy = _read_json(package / "proxy-logs.json")
            assert proxy["allowed_hosts"] == ["fixture-upstream"]
            assert proxy["decision_count"] == 3
            stdout = next(package.parent.glob("logs/*harness.stdout"))
            observed_units.add(_assert_bash_read(stdout))
        assert observed_units == (
            {"unit-001"}
            if case_id is not None
            else {"unit-001", "unit-002", "unit-003"}
        )

        requests = [
            json.loads(line) for line in _docker("logs", fixture).stdout.splitlines()
        ]
        assert len(requests) == 3 * len(packages)
        assert {item["unit_id"] for item in requests} == observed_units
        assert {item["path"] for item in requests} == {"/v1/messages?beta=true"}
    finally:
        _docker("rm", "-f", fixture, check=False)
        _docker("network", "rm", network, check=False)

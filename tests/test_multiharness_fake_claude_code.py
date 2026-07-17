from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

FAKE_CLAUDE = Path(__file__).parent / "fixtures" / "claude_code" / "fake_claude.py"
REQUESTED_MODEL = "claude-sonnet-4-6"
SECRET_CANARY = "fixture-secret-canary-7Jx9"


def test_fake_claude_version_and_help_are_offline_and_stable(tmp_path: Path) -> None:
    assert os.access(FAKE_CLAUDE, os.X_OK)
    version = _run(tmp_path, "--version")
    help_result = _run(tmp_path, "--help")

    assert version.returncode == 0
    assert version.stdout.strip() == "2.1.211 (Claude Code fixture)"
    assert help_result.returncode == 0
    for required_flag in (
        "--print",
        "--output-format",
        "--model",
        "--resume",
        "--session-id",
    ):
        assert required_flag in help_result.stdout


def test_fake_claude_stream_success_is_byte_deterministic(tmp_path: Path) -> None:
    first = _run_stream(tmp_path)
    second = _run_stream(tmp_path)

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout
    events = _events(first.stdout)
    assert [event["type"] for event in events] == ["system", "assistant", "result"]
    assert events[0]["subtype"] == "init"
    assert events[0]["model"] == REQUESTED_MODEL
    assert events[0]["tools"] == ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
    receipt = events[-1]
    assert receipt["subtype"] == "success"
    assert receipt["is_error"] is False
    assert receipt["session_id"] == "fixture-session-0001"
    assert receipt["usage"] == {
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "input_tokens": 11,
        "output_tokens": 7,
    }


@pytest.mark.parametrize(
    ("mode", "returncode", "subtype"),
    (
        ("nonzero", 23, "error_during_execution"),
        ("resume_mismatch", 9, "resume_mismatch"),
    ),
)
def test_fake_claude_failure_modes_end_with_typed_sanitized_receipt(
    tmp_path: Path,
    mode: str,
    returncode: int,
    subtype: str,
) -> None:
    result = _run_stream(
        tmp_path,
        mode=mode,
        extra_env={"LFB_FAKE_CLAUDE_SECRET_CANARY": SECRET_CANARY},
    )

    assert result.returncode == returncode
    receipt = _events(result.stdout)[-1]
    assert receipt["type"] == "result"
    assert receipt["subtype"] == subtype
    assert receipt["is_error"] is True
    assert SECRET_CANARY not in json.dumps(receipt, sort_keys=True)


def test_fake_claude_partial_result_omits_terminal_event(tmp_path: Path) -> None:
    result = _run_stream(tmp_path, mode="partial_result")

    assert result.returncode == 0
    assert [event["type"] for event in _events(result.stdout)] == [
        "system",
        "assistant",
    ]


@pytest.mark.parametrize("mode", ("mixed_output", "malformed_event"))
def test_fake_claude_stream_corruption_modes_retain_final_failure_receipt(
    tmp_path: Path,
    mode: str,
) -> None:
    result = _run_stream(tmp_path, mode=mode)

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    if mode == "mixed_output":
        assert lines[1] == "FAKE_CLAUDE_MIXED_STDOUT"
    else:
        assert lines[1] == '{"type":"assistant"'
    assert len(lines) == 2


def test_fake_claude_secret_canary_is_confined_to_intentional_raw_output(
    tmp_path: Path,
) -> None:
    result = _run_stream(
        tmp_path,
        mode="secret_canary",
        extra_env={"LFB_FAKE_CLAUDE_SECRET_CANARY": SECRET_CANARY},
    )

    assert result.returncode == 0
    assert SECRET_CANARY in result.stdout
    assert SECRET_CANARY in result.stderr
    receipt = _events(result.stdout)[-1]
    assert receipt["type"] == "result"
    assert SECRET_CANARY not in json.dumps(receipt, sort_keys=True)


def test_fake_claude_tool_request_is_structured(tmp_path: Path) -> None:
    result = _run_stream(tmp_path, mode="tool_request")
    events = _events(result.stdout)

    tool_use = events[1]["message"]["content"][0]
    assert tool_use == {
        "id": "toolu_fixture_0001",
        "input": {"file_path": "task/input.txt"},
        "name": "Read",
        "type": "tool_use",
    }
    assert events[-1]["subtype"] == "success"


@pytest.mark.parametrize(
    ("mode", "field", "expected"),
    (
        ("model_drift", "model", "claude-opus-4-1-fixture-drift"),
        ("version_drift", "claude_code_version", "9.9.9-fixture-drift"),
    ),
)
def test_fake_claude_identity_drift_is_explicit(
    tmp_path: Path,
    mode: str,
    field: str,
    expected: str,
) -> None:
    result = _run_stream(tmp_path, mode=mode)

    assert _events(result.stdout)[0][field] == expected


def test_fake_claude_resume_mismatch_records_requested_session(tmp_path: Path) -> None:
    result = _run_stream(
        tmp_path,
        mode="resume_mismatch",
        extra_args=("--resume", "expected-session"),
    )

    receipt = _events(result.stdout)[-1]
    assert receipt["requested_session_id"] == "expected-session"
    assert receipt["session_id"] == "fixture-session-mismatch"


def test_fake_claude_timeout_requires_runtime_termination(tmp_path: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        _run_stream(tmp_path, mode="timeout", timeout=0.1)

    assert "fixture-session-0001" in _stream_text(exc_info.value.stdout)
    assert SECRET_CANARY not in _stream_text(exc_info.value.stderr)


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal contract")
def test_fake_claude_cancellation_emits_typed_receipt(tmp_path: Path) -> None:
    env, network_marker, real_claude_marker = _isolated_environment(
        tmp_path,
        mode="cancellation",
    )
    process = subprocess.Popen(
        _argv(
            "--print",
            "fixture prompt",
            "--output-format",
            "stream-json",
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert process.stdout is not None
    init_line = process.stdout.readline()
    process.send_signal(signal.SIGTERM)
    stdout_tail, stderr = process.communicate(timeout=5)

    events = _events(init_line + stdout_tail)
    assert process.returncode == 130
    assert events[-1]["subtype"] == "cancelled"
    assert events[-1]["is_error"] is True
    assert stderr == ""
    assert not network_marker.exists()
    assert not real_claude_marker.exists()


@pytest.mark.parametrize("output_format", ("json", "text"))
def test_fake_claude_supports_non_stream_output_formats(
    tmp_path: Path,
    output_format: str,
) -> None:
    result = _run(
        tmp_path,
        "--print",
        "fixture prompt",
        "--model",
        REQUESTED_MODEL,
        "--output-format",
        output_format,
    )

    assert result.returncode == 0
    if output_format == "json":
        assert json.loads(result.stdout)["subtype"] == "success"
    else:
        assert result.stdout == "fixture response\n"


def test_fake_claude_unknown_mode_fails_closed(tmp_path: Path) -> None:
    result = _run_stream(tmp_path, mode="not-a-mode")

    assert result.returncode == 64
    assert result.stdout == ""
    assert result.stderr == "fake claude: unsupported mode\n"


def _run_stream(
    tmp_path: Path,
    *,
    mode: str = "success",
    extra_args: tuple[str, ...] = (),
    extra_env: dict[str, str] | None = None,
    timeout: float = 5,
) -> subprocess.CompletedProcess[str]:
    return _run(
        tmp_path,
        "--print",
        "fixture prompt",
        "--model",
        REQUESTED_MODEL,
        "--output-format",
        "stream-json",
        "--verbose",
        *extra_args,
        mode=mode,
        extra_env=extra_env,
        timeout=timeout,
    )


def _run(
    tmp_path: Path,
    *args: str,
    mode: str = "success",
    extra_env: dict[str, str] | None = None,
    timeout: float = 5,
) -> subprocess.CompletedProcess[str]:
    env, network_marker, real_claude_marker = _isolated_environment(
        tmp_path,
        mode=mode,
        extra_env=extra_env,
    )
    result = subprocess.run(
        _argv(*args),
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    assert not network_marker.exists(), "fake attempted a network socket"
    assert not real_claude_marker.exists(), "fake invoked the real claude command"
    return result


def _argv(*args: str) -> list[str]:
    return [sys.executable, str(FAKE_CLAUDE), *args]


def _isolated_environment(
    tmp_path: Path,
    *,
    mode: str,
    extra_env: dict[str, str] | None = None,
) -> tuple[dict[str, str], Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    real_claude_marker = tmp_path / "real-claude-invoked"
    claude_trap = bin_dir / "claude"
    claude_trap.write_text(
        '#!/bin/sh\nprintf invoked > "$REAL_CLAUDE_MARKER"\nexit 99\n',
        encoding="utf-8",
    )
    claude_trap.chmod(0o755)

    network_marker = tmp_path / "network-attempted"
    site_dir = tmp_path / "site"
    site_dir.mkdir(exist_ok=True)
    (site_dir / "sitecustomize.py").write_text(
        "import os, pathlib, socket\n"
        "_real_socket = socket.socket\n"
        "def _blocked_socket(*args, **kwargs):\n"
        "    pathlib.Path(os.environ['NETWORK_MARKER']).write_text('attempted')\n"
        "    raise RuntimeError('network disabled in fake Claude test')\n"
        "socket.socket = _blocked_socket\n",
        encoding="utf-8",
    )

    env = {
        "HOME": str(tmp_path / "home"),
        "LFB_FAKE_CLAUDE_MODE": mode,
        "NETWORK_MARKER": str(network_marker),
        "PATH": str(bin_dir),
        "PYTHONPATH": str(site_dir),
        "REAL_CLAUDE_MARKER": str(real_claude_marker),
    }
    if extra_env:
        env.update(extra_env)
    return env, network_marker, real_claude_marker


def _events(stdout: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]


def _stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

FAKE_CODEX = Path(__file__).parent / "fakes" / "fake_codex_cli.py"
EXPECTED_THREAD_ID = "00000000-0000-7000-8000-000000000001"


def test_fake_codex_version_is_stable_and_offline() -> None:
    assert os.access(FAKE_CODEX, os.X_OK)
    completed = _invoke("--version")

    assert completed.returncode == 0
    assert completed.stdout == "codex-cli 0.0.0-legalforecast-fake\n"
    assert completed.stderr == ""


def test_success_emits_deterministic_jsonl_and_last_message(tmp_path: Path) -> None:
    output_path = tmp_path / "last-message.txt"

    first = _exec(tmp_path, output_path=output_path, prompt="solve fixture")
    second = _exec(tmp_path, output_path=output_path, prompt="solve fixture")

    _assert_same_process_result(first, second)
    assert first.returncode == 0
    assert first.stderr == ""
    assert _events(first) == [
        {"thread_id": EXPECTED_THREAD_ID, "type": "thread.started"},
        {"type": "turn.started"},
        {
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
            "type": "item.completed",
        },
        {
            "type": "turn.completed",
            "usage": {
                "cached_input_tokens": 0,
                "input_tokens": 3,
                "output_tokens": 4,
            },
        },
    ]
    assert output_path.read_text(encoding="utf-8") == (
        "LEGALFORECAST_FAKE_CODEX_RESULT\n"
    )


@pytest.mark.parametrize(
    ("mode", "returncode", "event_types"),
    [
        ("nonzero", 17, ["thread.started", "turn.started", "error", "turn.failed"]),
        ("partial_result", 0, ["thread.started", "turn.started", "item.completed"]),
        (
            "tool_request",
            0,
            [
                "thread.started",
                "turn.started",
                "item.started",
                "item.completed",
                "item.completed",
                "turn.completed",
            ],
        ),
        (
            "secret_canary",
            0,
            ["thread.started", "turn.started", "item.completed", "turn.completed"],
        ),
    ],
)
def test_structured_modes_are_deterministic(
    tmp_path: Path,
    mode: str,
    returncode: int,
    event_types: list[str],
) -> None:
    first = _exec(tmp_path, mode=mode)
    second = _exec(tmp_path, mode=mode)

    _assert_same_process_result(first, second)
    assert first.returncode == returncode
    assert [event["type"] for event in _events(first)] == event_types


def test_secret_canary_is_confined_to_the_intentional_event(tmp_path: Path) -> None:
    completed = _exec(tmp_path, mode="secret_canary")

    assert completed.stderr == ""
    events = _events(completed)
    assert events[2]["item"]["text"] == "LEGALFORECAST_SECRET_CANARY_7f3a"


@pytest.mark.parametrize("mode", ["invalid_json", "mixed_output"])
def test_malformed_output_modes_are_reproducible(tmp_path: Path, mode: str) -> None:
    first = _exec(tmp_path, mode=mode)
    second = _exec(tmp_path, mode=mode)

    _assert_same_process_result(first, second)
    assert first.returncode == 0
    lines = first.stdout.splitlines()
    assert json.loads(lines[0])["type"] == "thread.started"
    with pytest.raises(json.JSONDecodeError):
        json.loads(lines[2])


def test_model_and_version_drift_are_explicit(tmp_path: Path) -> None:
    version = _invoke("--version", mode="model_drift")
    completed = _exec(tmp_path, mode="model_drift", model="expected-model")

    assert version.stdout == "codex-cli 99.0.0-drift\n"
    started = _events(completed)[0]
    assert started["requested_model"] == "expected-model"
    assert started["actual_model"] == "unexpected-model"


def test_resume_mismatch_fails_with_structured_sanitized_evidence(
    tmp_path: Path,
) -> None:
    completed = _invoke(
        "exec",
        "resume",
        "wrong-thread",
        "--json",
        cwd=tmp_path,
        mode="resume_mismatch",
    )

    assert completed.returncode == 18
    assert completed.stderr == ""
    events = _events(completed)
    assert [event["type"] for event in events] == [
        "thread.started",
        "turn.started",
        "error",
        "turn.failed",
    ]
    assert events[-1]["error"]["message"] == "resume identity mismatch"
    assert "wrong-thread" not in completed.stdout


def test_timeout_mode_can_be_cancelled_without_credentials_or_network(
    tmp_path: Path,
) -> None:
    command, env = _exec_command(tmp_path, mode="timeout")
    process = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate("solve fixture", timeout=0.1)
        pytest.fail(f"fake timeout mode exited unexpectedly: {stdout=} {stderr=}")
    except subprocess.TimeoutExpired:
        process.terminate()
        stdout, stderr = process.communicate(timeout=2)

    assert process.returncode is not None
    assert stderr == ""
    assert [json.loads(line)["type"] for line in stdout.splitlines()] == [
        "thread.started",
        "turn.started",
    ]


@pytest.mark.parametrize(
    ("cancellation_signal", "returncode"),
    [(signal.SIGINT, 130), (signal.SIGTERM, 143)],
)
def test_cancellation_mode_emits_deterministic_structured_failure(
    tmp_path: Path,
    cancellation_signal: signal.Signals,
    returncode: int,
) -> None:
    command, env = _exec_command(tmp_path, mode="cancellation")
    command[-1] = "solve fixture"
    process = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    prefix = [process.stdout.readline(), process.stdout.readline()]
    os.kill(process.pid, cancellation_signal)
    remainder, stderr = process.communicate(timeout=2)

    assert process.returncode == returncode
    assert stderr == ""
    events = [json.loads(line) for line in [*prefix, *remainder.splitlines()]]
    assert [event["type"] for event in events] == [
        "thread.started",
        "turn.started",
        "error",
        "turn.failed",
    ]
    assert events[-1]["error"]["message"] == "execution cancelled"


def test_unknown_mode_and_unsupported_invocation_fail_closed(tmp_path: Path) -> None:
    unknown_mode = _exec(tmp_path, mode="not-a-mode")
    unsupported = _invoke("login", cwd=tmp_path)

    assert unknown_mode.returncode == 64
    assert unknown_mode.stdout == ""
    assert unknown_mode.stderr == "fake codex: unsupported mode\n"
    assert unsupported.returncode == 64
    assert unsupported.stdout == ""
    assert unsupported.stderr == "fake codex: unsupported invocation\n"


def _exec(
    cwd: Path,
    *,
    mode: str = "success",
    model: str = "gpt-5.3-codex",
    output_path: Path | None = None,
    prompt: str = "solve fixture",
) -> subprocess.CompletedProcess[str]:
    command, env = _exec_command(
        cwd,
        mode=mode,
        model=model,
        output_path=output_path,
    )
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=prompt,
        capture_output=True,
        check=False,
        text=True,
        timeout=2,
    )


def _exec_command(
    cwd: Path,
    *,
    mode: str,
    model: str = "gpt-5.3-codex",
    output_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    command = [
        sys.executable,
        str(FAKE_CODEX),
        "exec",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(cwd),
        "--model",
        model,
        "--json",
    ]
    if output_path is not None:
        command.extend(["--output-last-message", str(output_path)])
    command.append("-")
    env = {"LEGALFORECAST_FAKE_CODEX_MODE": mode}
    return command, env


def _invoke(
    *args: str,
    cwd: Path | None = None,
    mode: str = "success",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(FAKE_CODEX), *args],
        cwd=cwd,
        env={"LEGALFORECAST_FAKE_CODEX_MODE": mode},
        capture_output=True,
        check=False,
        text=True,
        timeout=2,
    )


def _events(completed: subprocess.CompletedProcess[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in completed.stdout.splitlines()]


def _assert_same_process_result(
    first: subprocess.CompletedProcess[str],
    second: subprocess.CompletedProcess[str],
) -> None:
    assert first.returncode == second.returncode
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr

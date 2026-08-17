"""Mid-stream drain tests: runaway spew must not fill the disk cap."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    execute_local_cli,
)
from legalforecast.multiharness.local_cli_stream import StreamDrain, join_pipe_drains

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_SPEW_BYTES = 32 * 1024 * 1024
_CAPTURE_BYTES = 1_048_576
_MAX_PEAK_SCRATCH_BYTES = 8 * 1024 * 1024
_CANARY_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "LC_CTYPE": "C.UTF-8",
    "HOME": "/private/operator-home",
}


def test_stream_drain_truncates_capture_and_keeps_rolling_tail() -> None:
    drain = StreamDrain(max_capture_bytes=16, tail_bytes=8)
    drain.feed(b"abcdefgh")
    drain.feed(b"ijklmnop")
    drain.feed(b"qrstuv")
    captured, truncated = drain.finish()
    assert truncated is True
    assert len(captured) == 16
    assert captured.endswith(b"\n[truncated]\n")
    assert drain.tail_bytes_copy() == b"opqrstuv"
    assert drain.total == 22


def test_spew_is_drained_during_execution_and_does_not_fill_disk(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "spew-disk"
    peak = {"bytes": 0}
    stop = threading.Event()

    def _watch() -> None:
        while not stop.wait(0.02):
            peak["bytes"] = max(peak["bytes"], _resident_scratch_bytes(scratch))

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    try:
        result = execute_local_cli(
            _spew_spec(timeout_seconds=30),
            scratch,
            parent_env=_CANARY_ENV,
            max_capture_bytes=_CAPTURE_BYTES,
        )
    finally:
        stop.set()
        watcher.join(timeout=2)
        peak["bytes"] = max(peak["bytes"], _resident_scratch_bytes(scratch))

    assert result.status == "completed"
    assert result.stdout_truncated is True
    assert result.stderr_truncated is False
    assert len(result.stdout) == _CAPTURE_BYTES
    assert result.stdout.endswith(b"\n[truncated]\n")
    assert peak["bytes"] < _MAX_PEAK_SCRATCH_BYTES
    assert peak["bytes"] < _SPEW_BYTES // 2


def test_spew_then_cost_still_parses_cost_from_rolling_tail(tmp_path: Path) -> None:
    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="spew-cost",
            manifest=_manifest(),
            auth_profile=FIXTURE_NONE,
            extra_args=("--mode", "spew-then-cost"),
            timeout_seconds=10,
        ),
        tmp_path / "spew-cost",
        parent_env=_CANARY_ENV,
        max_capture_bytes=_CAPTURE_BYTES,
    )
    assert result.stdout_truncated is True
    assert result.cost_usd == 1.25


def test_join_pipe_drains_reports_unfinished_threads() -> None:
    blocker = threading.Event()

    def hang() -> None:
        blocker.wait(timeout=5)

    thread = threading.Thread(target=hang, daemon=True)
    thread.start()
    assert join_pipe_drains((thread,), timeout_seconds=0.05) is False
    blocker.set()
    assert join_pipe_drains((thread,), timeout_seconds=1.0) is True


def test_unfinished_drain_join_is_recorded_as_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unfinished(threads: object, *, timeout_seconds: float) -> bool:
        del threads, timeout_seconds
        return False

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime.join_pipe_drains",
        unfinished,
    )
    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="join-timeout",
            manifest=_manifest(),
            auth_profile=FIXTURE_NONE,
            extra_args=("--mode", "succeed-json"),
        ),
        tmp_path / "join-timeout",
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    public = result.to_public_record()
    assert public["stdout_truncated"] is True
    assert public["stderr_truncated"] is True


def test_mark_truncated_sets_the_flag_without_touching_capture() -> None:
    drain = StreamDrain(max_capture_bytes=16, tail_bytes=8)
    drain.feed(b"abc")
    assert drain.finish() == (b"abc", False)
    drain.mark_truncated()
    captured, truncated = drain.finish()
    assert truncated is True
    assert captured.startswith(b"abc")
    assert captured.endswith(b"\n[truncated]\n")
    assert drain.total == 3


def test_unfinished_drain_join_publishes_no_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incomplete capture must not publish a cost from the rolling tail.

    The trailing ``total_cost_usd`` envelope may still be sitting unread in
    the pipe, so the newest JSON object in the tail is an earlier one.
    """

    complete = execute_local_cli(
        _cost_spec("join-cost-baseline"),
        tmp_path / "baseline",
        parent_env=_CANARY_ENV,
    )
    assert complete.cost_usd == 1.25

    def unfinished(threads: object, *, timeout_seconds: float) -> bool:
        del threads, timeout_seconds
        return False

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime.join_pipe_drains",
        unfinished,
    )
    result = execute_local_cli(
        _cost_spec("join-cost-missed"),
        tmp_path / "missed",
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    assert result.cost_usd is None
    assert result.to_public_record()["cost_usd"] is None


def _cost_spec(spec_id: str) -> LocalCliRunSpec:
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=_manifest(),
        auth_profile=FIXTURE_NONE,
        extra_args=("--mode", "spew-then-cost"),
        timeout_seconds=10,
    )


def _spew_spec(*, timeout_seconds: float) -> LocalCliRunSpec:
    return LocalCliRunSpec(
        spec_id="spew-disk",
        manifest=_manifest(),
        auth_profile=FIXTURE_NONE,
        extra_args=("--mode", "spew", "--bytes", str(_SPEW_BYTES)),
        timeout_seconds=timeout_seconds,
    )


def _manifest() -> LocalCliAdapterManifest:
    path = _FAKE_CLI.resolve()
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(path)),
        executable=executable_pin_for(path, version="0.1.0"),
        supported_auth_profiles=(FIXTURE_NONE,),
        version_probe_args=("--mode", "version"),
    )


def _resident_scratch_bytes(scratch: Path) -> int:
    """Sum visible files plus this process's unlinked fds under scratch."""

    total = 0
    if scratch.exists():
        for path in scratch.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
    scratch_text = str(scratch.resolve())
    fd_root = Path("/proc/self/fd")
    if not fd_root.is_dir():
        return total
    for fd_path in fd_root.iterdir():
        try:
            target = os.readlink(fd_path)
        except OSError:
            continue
        if scratch_text not in target:
            continue
        try:
            total += os.fstat(int(fd_path.name)).st_size
        except (OSError, ValueError):
            continue
    return total

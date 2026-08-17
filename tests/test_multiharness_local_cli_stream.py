"""Mid-stream drain tests: runaway spew must not fill the disk cap."""

from __future__ import annotations

import contextlib
import errno
import io
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import IO, cast

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    execute_local_cli,
)
from legalforecast.multiharness.local_cli_stream import (
    StreamDrain,
    _drain_pipe,
    join_pipe_drains,
    start_pipe_drain,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_SPEW_BYTES = 32 * 1024 * 1024
_CAPTURE_BYTES = 1_048_576
_COST_ENVELOPE = b'{"type":"result","subtype":"success","total_cost_usd":1.25}'
_COST_LINE = _COST_ENVELOPE + b"\n"
_STDOUT_STREAM = 0
_STDERR_STREAM = 1
_DrainTarget = Callable[[IO[bytes], StreamDrain], None]
_DrainStarter = Callable[[IO[bytes], StreamDrain], threading.Thread]
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
    assert drain.completed_tail() is None
    drain.mark_completed()
    assert drain.completed_tail() == b"opqrstuv"
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


def test_drain_pipe_signals_completion_at_end_of_file() -> None:
    drain = StreamDrain(max_capture_bytes=256, tail_bytes=256)
    thread = start_pipe_drain(io.BytesIO(_COST_LINE), drain)
    thread.join(timeout=5)
    assert thread.is_alive() is False
    assert drain.completed_tail() == _COST_LINE


def test_read_error_leaves_the_stream_incomplete_though_the_tail_parses() -> None:
    """A drain that died mid-read is not a stream that was drained.

    ``_drain_pipe`` has no ``except`` around the read, so an ``OSError``
    propagates and kills the thread after ``finally: pipe.close()``. What it
    leaves behind can still parse as a cost envelope while the stream is
    short, which is why only the explicit end-of-file signal unlocks the tail.
    """

    drain = StreamDrain(max_capture_bytes=256, tail_bytes=256)
    pipe = _RaiseAtEofPipe(io.BytesIO(_COST_LINE))
    with pytest.raises(OSError, match="input/output error"):
        _drain_pipe(cast("IO[bytes]", pipe), drain)
    assert pipe.closed is True
    assert drain.completed_tail() is None
    captured, _ = drain.finish()
    assert _COST_ENVELOPE in captured


def test_missed_stdout_drain_join_publishes_no_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incomplete stdout capture must not publish a cost (GitHub #719).

    The trailing ``total_cost_usd`` envelope may still be sitting unread in
    the pipe, so the newest JSON object in the tail is an earlier one.
    """

    complete = execute_local_cli(
        _succeed_spec("stdout-miss-baseline"),
        tmp_path / "baseline",
        parent_env=_CANARY_ENV,
    )
    assert complete.cost_usd == 0.0

    _shorten_drain_join(monkeypatch)
    release = threading.Event()
    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime.start_pipe_drain",
        _replace_drain_for_stream(_STDOUT_STREAM, _hold_pipe_open(release)),
    )
    try:
        result = execute_local_cli(
            _succeed_spec("stdout-miss"),
            tmp_path / "missed",
            parent_env=_CANARY_ENV,
            termination_grace_seconds=0.2,
        )
    finally:
        release.set()
    assert result.status == "completed"
    assert result.cost_usd is None
    assert result.to_public_record()["cost_usd"] is None
    assert result.stdout_truncated is True


def test_missed_stderr_drain_join_keeps_the_stdout_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only stdout carries the cost envelope, so only stdout can void it.

    A stderr drain that misses its join still marks the receipt truncated,
    but the stdout drain read its own stream to end of file and the amount it
    parsed is a real paid one (GitHub #771).
    """

    _shorten_drain_join(monkeypatch)
    release = threading.Event()
    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime.start_pipe_drain",
        _replace_drain_for_stream(_STDERR_STREAM, _hold_pipe_open(release)),
    )
    try:
        result = execute_local_cli(
            _cost_spec("stderr-miss"),
            tmp_path / "stderr-miss",
            parent_env=_CANARY_ENV,
            termination_grace_seconds=0.2,
            max_capture_bytes=4 * 1024 * 1024,
        )
    finally:
        release.set()
    assert result.status == "completed"
    assert result.cost_usd == 1.25
    assert result.to_public_record()["cost_usd"] == 1.25
    assert result.stderr_truncated is True
    assert result.stdout_truncated is False


def test_stdout_drain_read_error_suppresses_a_parsable_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finished thread is not proof the stdout stream reached its end.

    The drain here runs the real read loop against a pipe that fails the read
    that would have returned end of file. Every byte it already fed is in the
    capture, so the cost envelope parses -- and is still refused, because the
    same dead-thread state can hide a short read (GitHub #771).
    """

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime.start_pipe_drain",
        _replace_drain_for_stream(_STDOUT_STREAM, _drain_until_read_error),
    )
    result = execute_local_cli(
        _cost_spec("stdout-read-error"),
        tmp_path / "read-error",
        parent_env=_CANARY_ENV,
        max_capture_bytes=4 * 1024 * 1024,
    )
    assert result.status == "completed"
    assert _COST_ENVELOPE in result.stdout
    assert result.cost_usd is None
    assert result.to_public_record()["cost_usd"] is None


class _RaiseAtEofPipe:
    """Pipe wrapper that fails the read which would have returned EOF."""

    def __init__(self, pipe: IO[bytes]) -> None:
        self._pipe = pipe
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        chunk = self._pipe.read(size)
        if not chunk:
            raise OSError(errno.EIO, "input/output error")
        return chunk

    def close(self) -> None:
        self.closed = True
        self._pipe.close()


def _drain_until_read_error(pipe: IO[bytes], drain: StreamDrain) -> None:
    """Run the production drain against a pipe that never reaches EOF.

    Only the thread-boundary ``OSError`` is swallowed, and only to keep the
    test quiet: the drain state left behind is exactly what the unguarded
    production thread leaves when a read fails.
    """

    with contextlib.suppress(OSError):
        _drain_pipe(cast("IO[bytes]", _RaiseAtEofPipe(pipe)), drain)


def _replace_drain_for_stream(
    index: int,
    replacement: _DrainTarget,
) -> _DrainStarter:
    """Swap one stream's drain thread, leaving the other in production form.

    ``_run_contained_cli`` starts stdout first and stderr second, so ``index``
    picks the stream whose drain misbehaves.
    """

    calls: list[int] = []

    def start(pipe: IO[bytes], drain: StreamDrain) -> threading.Thread:
        position = len(calls)
        calls.append(position)
        if position != index:
            return start_pipe_drain(pipe, drain)
        thread = threading.Thread(
            target=replacement,
            args=(pipe, drain),
            daemon=True,
            name="test-drain-stand-in",
        )
        thread.start()
        return thread

    return start


def _hold_pipe_open(release: threading.Event) -> _DrainTarget:
    """Build a stand-in drain that never reads, so its join really times out."""

    def run(pipe: IO[bytes], drain: StreamDrain) -> None:
        del drain
        try:
            release.wait(timeout=30)
        finally:
            pipe.close()

    return run


def _shorten_drain_join(monkeypatch: pytest.MonkeyPatch) -> None:
    """Halve the join budget: the idle stand-in always burns all of it.

    It stays a whole second so the real drain on the other stream still
    finishes inside the budget on a loaded box.
    """

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_runtime._DRAIN_JOIN_SECONDS",
        1.0,
    )


def _succeed_spec(spec_id: str) -> LocalCliRunSpec:
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=_manifest(),
        auth_profile=FIXTURE_NONE,
        extra_args=("--mode", "succeed-json"),
        timeout_seconds=10,
    )


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

"""The managed runtime receives the declared bounded case time budget."""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness import openclaw_runtime
from legalforecast.multiharness.openclaw import OpenClawError
from legalforecast.multiharness.openclaw_runtime import GatewayRuntimeConfig
from legalforecast.multiharness.openclaw_worker import StagedPromptTransport

from test_multiharness_openclaw import request


@pytest.mark.parametrize("budget", [900, 30, 1])
def test_managed_deadlines_follow_case_budget_and_refuse_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget: int
) -> None:
    _assert_timeout_cleanup(tmp_path, monkeypatch, budget=budget)


def test_timeout_waits_for_active_reader_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_timeout_cleanup(tmp_path, monkeypatch, budget=1, slow_cleanup=True)


def _assert_timeout_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    budget: int,
    slow_cleanup: bool = False,
) -> None:
    original = request()
    value = replace(
        original,
        model_key="anthropic:claude-opus-5-5",
        sandbox_policy=replace(
            original.sandbox_policy,
            allowed_provider_env_vars=(),
            timeout_seconds=budget,
        ),
    )
    monkeypatch.setattr(
        openclaw_runtime, "verify_runtime", lambda _: tmp_path / "entry"
    )
    monkeypatch.setattr(openclaw_runtime.shutil, "which", lambda _: "/usr/bin/node")
    sockets: list[socket.socket] = []
    socketpair = socket.socketpair

    def capture_socketpair() -> tuple[socket.socket, socket.socket]:
        pair = socketpair()
        sockets.extend(pair)
        return pair

    monkeypatch.setattr(openclaw_runtime.socket, "socketpair", capture_socketpair)
    calls: list[list[str]] = []
    reader_ready = threading.Event()
    readers: list[threading.Thread] = []

    def slow_reader_cleanup(channel: socket.socket, *args: object) -> None:
        # A makefile retains the socket fd after socket.close(). Model a reader
        # that is scheduled later than the main thread's exception cleanup.
        readers.append(threading.current_thread())
        try:
            with channel.makefile("rb") as reader:
                reader_ready.set()
                reader.readline(1024)
                time.sleep(0.05)
        finally:
            channel.close()

    if slow_cleanup:
        monkeypatch.setattr(openclaw_runtime, "bridge_read", slow_reader_cleanup)

    def time_out(argv: list[str], *, timeout: int, **kwargs: object) -> None:
        calls.append(argv)
        assert argv[argv.index("--timeout") + 1] == str(max(1, budget - 10))
        assert timeout == max(1, budget - 5)
        assert sockets[0].gettimeout() == max(1, budget - 5)
        if slow_cleanup:
            assert reader_ready.wait(timeout=1), "reader did not acquire its io-ref"
        raise subprocess.TimeoutExpired(argv, timeout)

    monkeypatch.setattr(openclaw_runtime.subprocess, "run", time_out)
    with pytest.raises(OpenClawError, match="managed run timed out"):
        openclaw_runtime.run_openclaw(
            value,
            tmp_path,
            StagedPromptTransport(tmp_path),
            gateway=GatewayRuntimeConfig("synthetic-capability", 100000, 4096),
        )
    assert len(calls) == 1
    assert all(channel.fileno() == -1 for channel in sockets)
    assert all(not reader.is_alive() for reader in readers)
    assert not (tmp_path / "private-logs/openclaw-forecast.json").exists()


def test_cleanup_before_worker_start_preserves_original_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = request()
    value = replace(
        original,
        model_key="anthropic:claude-opus-5-5",
        sandbox_policy=replace(original.sandbox_policy, allowed_provider_env_vars=()),
    )
    monkeypatch.setattr(
        openclaw_runtime, "verify_runtime", lambda _: tmp_path / "entry"
    )
    monkeypatch.setattr(openclaw_runtime.shutil, "which", lambda _: "/usr/bin/node")

    def refuse_config(*args: object, **kwargs: object) -> None:
        raise PermissionError("config write refused before reader start")

    monkeypatch.setattr(openclaw_runtime, "write_json_object", refuse_config)
    with pytest.raises(PermissionError, match="config write refused"):
        openclaw_runtime.run_openclaw(
            value,
            tmp_path,
            StagedPromptTransport(tmp_path),
            gateway=GatewayRuntimeConfig("synthetic-capability", 100000, 4096),
        )

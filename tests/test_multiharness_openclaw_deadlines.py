"""The managed runtime receives the declared bounded case time budget."""

from __future__ import annotations

import socket
import subprocess
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

    def time_out(argv: list[str], *, timeout: int, **kwargs: object) -> None:
        calls.append(argv)
        assert argv[argv.index("--timeout") + 1] == str(max(1, budget - 10))
        assert timeout == max(1, budget - 5)
        assert sockets[0].gettimeout() == max(1, budget - 5)
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
    assert not (tmp_path / "private-logs/openclaw-forecast.json").exists()

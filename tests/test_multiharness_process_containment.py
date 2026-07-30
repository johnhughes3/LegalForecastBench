from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness import (
    process_containment as process_containment_module,
)
from legalforecast.multiharness.process_containment import (
    ProcessContainmentHandle,
    cleanup_process_containment,
)
from legalforecast.multiharness.spec import LINUX_SYSTEMD_SCOPE_CONTAINMENT


def test_systemd_cleanup_evidence_distinguishes_denied_kill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle, process = _fake_populated_handle(tmp_path)
    monkeypatch.setattr(
        process_containment_module,
        "_cgroup_is_populated",
        _populated,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_signal_cgroup_members",
        _signal_members,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_wait_for_cgroup_empty",
        _never_empty,
    )

    def deny_kill(file_descriptor: int) -> None:
        del file_descriptor
        raise PermissionError

    monkeypatch.setattr(process_containment_module, "_kill_cgroup", deny_kill)

    evidence = cleanup_process_containment(handle, process, 0.01)

    assert evidence.cleanup_requested is True
    assert evidence.termination_requested is True
    assert evidence.forced_kill is False
    assert evidence.cleanup_outcome == "denied"
    assert evidence.populated_after_cleanup is True


def test_systemd_cleanup_evidence_distinguishes_incomplete_kill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle, process = _fake_populated_handle(tmp_path)
    monkeypatch.setattr(
        process_containment_module,
        "_cgroup_is_populated",
        _populated,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_signal_cgroup_members",
        _signal_members,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_wait_for_cgroup_empty",
        _never_empty,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_kill_cgroup",
        _allow_kill,
    )

    evidence = cleanup_process_containment(handle, process, 0.01)

    assert evidence.cleanup_requested is True
    assert evidence.termination_requested is True
    assert evidence.forced_kill is True
    assert evidence.cleanup_outcome == "incomplete"
    assert evidence.populated_after_cleanup is True


def test_graceful_signal_revalidates_pid_membership_after_pidfd_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = iter(((4812,), ()))
    signal_calls: list[tuple[int, signal.Signals]] = []

    def process_ids(_cgroup_fd: int) -> tuple[int, ...]:
        return next(snapshots)

    def open_pidfd(_process_id: int) -> int:
        return os.open("/dev/null", os.O_RDONLY)

    def send_signal(pid_fd: int, requested_signal: signal.Signals) -> None:
        signal_calls.append((pid_fd, requested_signal))

    monkeypatch.setattr(
        process_containment_module,
        "_cgroup_process_ids",
        process_ids,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_pidfd_open",
        open_pidfd,
    )
    monkeypatch.setattr(
        process_containment_module,
        "_pidfd_send_signal",
        send_signal,
    )

    delivered = process_containment_module._signal_cgroup_members(  # pyright: ignore[reportPrivateUsage]
        17,
        signal.SIGTERM,
    )

    assert delivered is False
    assert signal_calls == []


def _fake_populated_handle(
    tmp_path: Path,
) -> tuple[ProcessContainmentHandle, subprocess.Popen[bytes]]:
    cgroup_directory = tmp_path / "cgroup"
    cgroup_directory.mkdir()
    cgroup_fd = os.open(
        cgroup_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    process = subprocess.Popen(
        ("/bin/true",),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    process.wait(timeout=1)
    return (
        ProcessContainmentHandle(
            requested=LINUX_SYSTEMD_SCOPE_CONTAINMENT,
            unit_name="lfb-command-fixture.scope",
            invocation_id="a" * 32,
            control_group="/fixture/lfb-command-fixture.scope",
            cgroup_fd=cgroup_fd,
        ),
        process,
    )


def _populated(file_descriptor: int) -> bool:
    del file_descriptor
    return True


def _signal_members(
    file_descriptor: int,
    requested_signal: signal.Signals,
) -> bool:
    del file_descriptor, requested_signal
    return True


def _never_empty(
    file_descriptor: int,
    timeout_seconds: float,
    *,
    repeated_signal: signal.Signals | None = None,
) -> bool:
    del file_descriptor, timeout_seconds, repeated_signal
    return False


def _allow_kill(file_descriptor: int) -> None:
    del file_descriptor

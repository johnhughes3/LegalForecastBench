"""Host-owned lifecycle containment for command-adapter subprocesses."""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.spec import (
    LINUX_SYSTEMD_SCOPE_CONTAINMENT,
    POSIX_PROCESS_GROUP_CONTAINMENT,
)

_CGROUP_ROOT = Path("/sys/fs/cgroup")
_SYSTEMD_IDENTITY_TIMEOUT_SECONDS = 2.0
_LIBC = ctypes.CDLL(None, use_errno=True)


class ProcessContainmentError(RuntimeError):
    """Raised when a requested host process-containment boundary is unavailable."""

    def __init__(self, message: str, *, establishment: str = "failed") -> None:
        super().__init__(message)
        self.establishment = establishment


@dataclass(frozen=True, slots=True)
class ProcessContainmentEvidence:
    """Private evidence describing establishment and cleanup of one boundary."""

    requested: str
    establishment: str
    mechanism: str
    cleanup_requested: bool = False
    termination_requested: bool = False
    forced_kill: bool = False
    cleanup_outcome: str = "not_required"
    populated_after_cleanup: bool | None = None
    unit_name: str | None = None
    invocation_id: str | None = None
    control_group: str | None = None

    def to_private_record(self) -> dict[str, Any]:
        """Return the private, path-bearing containment evidence."""

        return {
            "requested": self.requested,
            "establishment": self.establishment,
            "mechanism": self.mechanism,
            "cleanup_requested": self.cleanup_requested,
            "termination_requested": self.termination_requested,
            "forced_kill": self.forced_kill,
            "cleanup_outcome": self.cleanup_outcome,
            "populated_after_cleanup": self.populated_after_cleanup,
            "unit_name": self.unit_name,
            "invocation_id": self.invocation_id,
            "control_group": self.control_group,
        }


@dataclass(frozen=True, slots=True)
class PreparedContainedCommand:
    """A command wrapped for an already-preflighted containment backend."""

    requested: str
    argv: tuple[str, ...]
    unit_name: str | None = None
    control_address: str | None = None
    control_token: str | None = None
    listener: socket.socket | None = None


@dataclass(slots=True)
class ProcessContainmentHandle:
    """Opaque live handle used for identity-bound cleanup."""

    requested: str
    process_group_id: int | None = None
    unit_name: str | None = None
    invocation_id: str | None = None
    control_group: str | None = None
    cgroup_fd: int | None = None
    gate_pid: int | None = None
    gate_pidfd: int | None = None
    control: socket.socket | None = None


def preflight_process_containment(requested: str) -> None:
    """Prove the requested backend works before provider values are resolved."""

    if requested == POSIX_PROCESS_GROUP_CONTAINMENT:
        if os.name != "posix":
            raise ProcessContainmentError(
                "POSIX process-group containment is unavailable",
                establishment="unsupported",
            )
        return
    if requested != LINUX_SYSTEMD_SCOPE_CONTAINMENT:
        raise ProcessContainmentError(
            "unknown host process-containment mode",
            establishment="unsupported",
        )
    _require_systemd_scope_primitives()
    _exercise_systemd_scope_preflight()


def containment_launcher_environment(requested: str) -> dict[str, str]:
    """Return value-free variables needed only by the containment launcher."""

    if requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT:
        return _manager_environment()
    return {}


def prepare_contained_command(
    requested: str,
    argv: tuple[str, ...],
    *,
    private_logs: Path,
    runtime_max_seconds: float,
) -> PreparedContainedCommand:
    """Wrap argv without launching it."""

    if requested == POSIX_PROCESS_GROUP_CONTAINMENT:
        return PreparedContainedCommand(requested=requested, argv=argv)
    if requested != LINUX_SYSTEMD_SCOPE_CONTAINMENT:
        raise ProcessContainmentError(
            "unknown host process-containment mode",
            establishment="unsupported",
        )

    systemd_run = _required_executable("systemd-run")
    nonce = secrets.token_hex(16)
    unit_name = f"lfb-command-{nonce}.scope"
    control_token = secrets.token_hex(32)
    del private_logs
    control_address = f"\0lfb-command-{nonce}"
    control_argument = f"@lfb-command-{nonce}"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(control_address)
        listener.listen(1)
    except BaseException:
        listener.close()
        raise
    gate_wrapper = Path(__file__).with_name("_contained_exec.py")
    wrapped = (
        systemd_run,
        "--user",
        "--scope",
        "--quiet",
        f"--unit={unit_name}",
        "--property=Delegate=no",
        f"--property=RuntimeMaxSec={max(1.0, runtime_max_seconds):.3f}s",
        "--",
        sys.executable,
        str(gate_wrapper),
        "--socket",
        control_argument,
        "--token",
        control_token,
        "--",
        *argv,
    )
    return PreparedContainedCommand(
        requested=requested,
        argv=wrapped,
        unit_name=unit_name,
        control_address=control_address,
        control_token=control_token,
        listener=listener,
    )


def establish_process_containment(
    prepared: PreparedContainedCommand,
    process: subprocess.Popen[bytes],
    handle: ProcessContainmentHandle,
) -> ProcessContainmentHandle:
    """Attest the live identity, then release the adapter executable gate."""

    if prepared.requested == POSIX_PROCESS_GROUP_CONTAINMENT:
        handle.process_group_id = process.pid
        return handle
    if (
        prepared.unit_name is None
        or prepared.control_address is None
        or prepared.control_token is None
        or prepared.listener is None
    ):
        raise ProcessContainmentError("systemd scope preparation is incomplete")

    try:
        prepared.listener.settimeout(_SYSTEMD_IDENTITY_TIMEOUT_SECONDS)
        connection, _ = prepared.listener.accept()
        handle.control = connection
        gate_pid = _authenticate_gate_peer(
            connection,
            prepared.control_token,
        )
        handle.gate_pid = gate_pid
        properties = _wait_for_systemd_scope(prepared.unit_name, process)
        handle.invocation_id = properties["InvocationID"]
        control_group = properties["ControlGroup"]
        handle.control_group = control_group
        handle.cgroup_fd = _open_verified_cgroup(
            prepared.unit_name,
            control_group,
        )
        handle.gate_pidfd = _pidfd_open(gate_pid)
        _require_exact_process_cgroup(gate_pid, control_group)
    finally:
        prepared.listener.close()
    return handle


def release_contained_command(
    handle: ProcessContainmentHandle,
    environment: Mapping[str, str],
) -> None:
    """Deliver provider values only after the gate process is identity-bound."""

    if handle.requested == POSIX_PROCESS_GROUP_CONTAINMENT:
        return
    if handle.control is None or handle.gate_pid is None or handle.gate_pidfd is None:
        raise ProcessContainmentError("contained command gate is unavailable")
    _require_exact_process_cgroup(handle.gate_pid, handle.control_group or "")
    payload = json.dumps(
        {"environment": dict(sorted(environment.items()))},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    try:
        handle.control.sendall(payload + b"\n")
    except OSError as exc:
        raise ProcessContainmentError(
            "contained command gate could not be released"
        ) from exc
    finally:
        handle.control.close()
        handle.control = None


def abandon_prepared_containment(prepared: PreparedContainedCommand) -> None:
    """Close private preparation artifacts after a launch failure."""

    if prepared.listener is not None:
        prepared.listener.close()


def cleanup_process_containment(
    handle: ProcessContainmentHandle,
    process: subprocess.Popen[bytes],
    grace_seconds: float,
) -> ProcessContainmentEvidence:
    """Stop and positively account for the owned process boundary."""

    if handle.requested == POSIX_PROCESS_GROUP_CONTAINMENT:
        termination_requested, forced_kill = _terminate_process_group(
            process,
            handle.process_group_id,
            grace_seconds,
        )
        cleanup_requested = termination_requested or forced_kill
        return ProcessContainmentEvidence(
            requested=handle.requested,
            establishment="established",
            mechanism="posix_process_group",
            cleanup_requested=cleanup_requested,
            termination_requested=termination_requested,
            forced_kill=forced_kill,
            cleanup_outcome=("succeeded" if cleanup_requested else "not_required"),
            populated_after_cleanup=False if cleanup_requested else None,
        )

    if handle.cgroup_fd is None:
        return ProcessContainmentEvidence(
            requested=handle.requested,
            establishment="failed",
            mechanism="systemd_user_scope_cgroup_v2",
            cleanup_outcome="incomplete",
            unit_name=handle.unit_name,
            invocation_id=handle.invocation_id,
            control_group=handle.control_group,
        )
    try:
        return _cleanup_systemd_scope(handle, process, grace_seconds)
    finally:
        if handle.control is not None:
            handle.control.close()
            handle.control = None
        if handle.gate_pidfd is not None:
            os.close(handle.gate_pidfd)
            handle.gate_pidfd = None
        os.close(handle.cgroup_fd)
        handle.cgroup_fd = None


def launch_failure_evidence(
    requested: str,
    *,
    establishment: str = "failed",
) -> ProcessContainmentEvidence:
    """Build truthful evidence for a command that never crossed its gate."""

    mechanism = (
        "systemd_user_scope_cgroup_v2"
        if requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT
        else "posix_process_group"
    )
    return ProcessContainmentEvidence(
        requested=requested,
        establishment=establishment,
        mechanism=mechanism,
        cleanup_outcome="not_required",
        populated_after_cleanup=False,
    )


def _cleanup_systemd_scope(
    handle: ProcessContainmentHandle,
    process: subprocess.Popen[bytes],
    grace_seconds: float,
) -> ProcessContainmentEvidence:
    cgroup_fd = handle.cgroup_fd
    assert cgroup_fd is not None
    try:
        populated = _cgroup_is_populated(cgroup_fd)
    except OSError:
        populated = None
    if populated is False:
        child_stopped = _wait_for_direct_child(process, grace_seconds)
        return _systemd_evidence(
            handle,
            cleanup_requested=not child_stopped,
            cleanup_outcome="not_required" if child_stopped else "incomplete",
            populated_after_cleanup=False,
        )
    if populated is None:
        return _systemd_evidence(
            handle,
            cleanup_outcome="incomplete",
            populated_after_cleanup=None,
        )

    termination_requested = False
    graceful_signal_denied = False
    try:
        termination_requested = _signal_cgroup_members(cgroup_fd, signal.SIGTERM)
    except PermissionError:
        graceful_signal_denied = True
    if not graceful_signal_denied and _wait_for_cgroup_empty(
        cgroup_fd, grace_seconds, repeated_signal=signal.SIGTERM
    ):
        child_stopped = _wait_for_direct_child(process, grace_seconds)
        return _systemd_evidence(
            handle,
            cleanup_requested=True,
            termination_requested=termination_requested,
            cleanup_outcome="succeeded" if child_stopped else "incomplete",
            populated_after_cleanup=False,
        )

    try:
        _kill_cgroup(cgroup_fd)
    except PermissionError:
        return _systemd_evidence(
            handle,
            cleanup_requested=True,
            termination_requested=termination_requested,
            cleanup_outcome="denied",
            populated_after_cleanup=True,
        )
    except OSError:
        return _systemd_evidence(
            handle,
            cleanup_requested=True,
            termination_requested=termination_requested,
            cleanup_outcome="incomplete",
            populated_after_cleanup=None,
        )

    emptied = _wait_for_cgroup_empty(cgroup_fd, grace_seconds)
    child_stopped = False
    if emptied:
        child_stopped = _wait_for_direct_child(process, grace_seconds)
    return _systemd_evidence(
        handle,
        cleanup_requested=True,
        termination_requested=termination_requested,
        forced_kill=True,
        cleanup_outcome=("succeeded" if emptied and child_stopped else "incomplete"),
        populated_after_cleanup=not emptied,
    )


def _systemd_evidence(
    handle: ProcessContainmentHandle,
    *,
    cleanup_requested: bool = False,
    termination_requested: bool = False,
    forced_kill: bool = False,
    cleanup_outcome: str,
    populated_after_cleanup: bool | None,
) -> ProcessContainmentEvidence:
    return ProcessContainmentEvidence(
        requested=handle.requested,
        establishment="established",
        mechanism="systemd_user_scope_cgroup_v2",
        cleanup_requested=cleanup_requested,
        termination_requested=termination_requested,
        forced_kill=forced_kill,
        cleanup_outcome=cleanup_outcome,
        populated_after_cleanup=populated_after_cleanup,
        unit_name=handle.unit_name,
        invocation_id=handle.invocation_id,
        control_group=handle.control_group,
    )


def _require_systemd_scope_primitives() -> None:
    if sys.platform != "linux":
        raise ProcessContainmentError(
            "systemd scope containment requires Linux",
            establishment="unsupported",
        )
    if not (_CGROUP_ROOT / "cgroup.controllers").is_file():
        raise ProcessContainmentError(
            "systemd scope containment requires unified cgroup v2",
            establishment="unsupported",
        )
    _required_executable("systemd-run")
    _required_executable("systemctl")
    if not hasattr(_LIBC, "pidfd_open") or not hasattr(_LIBC, "pidfd_send_signal"):
        raise ProcessContainmentError(
            "systemd scope containment requires pidfd signaling",
            establishment="unsupported",
        )


def _exercise_systemd_scope_preflight() -> None:
    systemd_run = _required_executable("systemd-run")
    unit_name = f"lfb-preflight-{secrets.token_hex(16)}.scope"
    process = subprocess.Popen(
        (
            systemd_run,
            "--user",
            "--scope",
            "--quiet",
            f"--unit={unit_name}",
            "--property=Delegate=no",
            "--property=RuntimeMaxSec=5s",
            "--",
            "/bin/sleep",
            "60",
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_manager_environment(),
        start_new_session=True,
    )
    cgroup_fd: int | None = None
    try:
        properties = _wait_for_systemd_scope(unit_name, process)
        cgroup_fd = _open_verified_cgroup(unit_name, properties["ControlGroup"])
        process_ids = _cgroup_process_ids(cgroup_fd)
        if not process_ids:
            raise ProcessContainmentError(
                "systemd scope preflight found no contained process"
            )
        pid_fd = _pidfd_open(process_ids[0])
        try:
            _pidfd_send_signal(pid_fd, 0)
        finally:
            os.close(pid_fd)
        _kill_cgroup(cgroup_fd)
        if not _wait_for_cgroup_empty(cgroup_fd, 1.0):
            raise ProcessContainmentError(
                "systemd scope preflight cleanup was incomplete"
            )
        process.wait(timeout=1.0)
    except PermissionError as exc:
        raise ProcessContainmentError(
            "systemd scope containment was denied",
            establishment="denied",
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProcessContainmentError(
            "systemd scope containment preflight failed"
        ) from exc
    finally:
        if cgroup_fd is not None:
            os.close(cgroup_fd)
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass


def _wait_for_systemd_scope(
    unit_name: str,
    process: subprocess.Popen[bytes],
) -> dict[str, str]:
    deadline = time.monotonic() + _SYSTEMD_IDENTITY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        properties = _systemd_scope_properties(unit_name)
        if (
            properties.get("ActiveState") == "active"
            and properties.get("InvocationID")
            and properties.get("ControlGroup")
        ):
            return properties
        if process.poll() is not None:
            break
        time.sleep(0.01)
    raise ProcessContainmentError(
        "systemd scope identity could not be established",
        establishment="failed",
    )


def _systemd_scope_properties(unit_name: str) -> dict[str, str]:
    result = subprocess.run(
        (
            _required_executable("systemctl"),
            "--user",
            "show",
            unit_name,
            "--property=ActiveState",
            "--property=ControlGroup",
            "--property=InvocationID",
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=_manager_environment(),
        timeout=1.0,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return {}
    return {
        key: value
        for line in result.stdout.splitlines()
        if "=" in line
        for key, value in (line.split("=", 1),)
    }


def _open_verified_cgroup(unit_name: str, control_group: str) -> int:
    if (
        not control_group.startswith("/")
        or ".." in Path(control_group).parts
        or Path(control_group).name != unit_name
    ):
        raise ProcessContainmentError("systemd returned an invalid control group")
    cgroup_path = _CGROUP_ROOT / control_group.lstrip("/")
    try:
        cgroup_fd = os.open(
            cgroup_path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise ProcessContainmentError(
            "systemd control group could not be opened"
        ) from exc
    try:
        for required_file, flags in (
            ("cgroup.events", os.O_RDONLY),
            ("cgroup.procs", os.O_RDONLY),
            ("cgroup.kill", os.O_WRONLY),
        ):
            file_descriptor = os.open(
                required_file,
                flags,
                dir_fd=cgroup_fd,
            )
            os.close(file_descriptor)
    except OSError as exc:
        os.close(cgroup_fd)
        raise ProcessContainmentError(
            "systemd control group lacks required cgroup-v2 controls",
            establishment="unsupported",
        ) from exc
    return cgroup_fd


def _authenticate_gate_peer(control: socket.socket, expected_token: str) -> int:
    credentials = control.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )
    peer_pid, peer_uid, _ = struct.unpack("3i", credentials)
    if peer_uid != os.getuid():
        raise ProcessContainmentError("contained command gate peer has wrong UID")
    payload = bytearray()
    while b"\n" not in payload:
        chunk = control.recv(4096)
        if not chunk:
            raise ProcessContainmentError("contained command gate peer disconnected")
        payload.extend(chunk)
        if len(payload) > 4096:
            raise ProcessContainmentError("contained command gate handshake is invalid")
    line, remainder = bytes(payload).split(b"\n", 1)
    if remainder:
        raise ProcessContainmentError("contained command gate handshake is invalid")
    try:
        record = cast(object, json.loads(line))
    except (UnicodeError, ValueError) as exc:
        raise ProcessContainmentError(
            "contained command gate handshake is invalid"
        ) from exc
    if (
        not isinstance(record, dict)
        or cast(dict[object, object], record).get("token") != expected_token
        or cast(dict[object, object], record).get("pid") != peer_pid
    ):
        raise ProcessContainmentError("contained command gate identity mismatch")
    return peer_pid


def _require_exact_process_cgroup(process_id: int, control_group: str) -> None:
    try:
        lines = (
            Path(f"/proc/{process_id}/cgroup").read_text(encoding="ascii").splitlines()
        )
    except OSError as exc:
        raise ProcessContainmentError(
            "contained command gate process disappeared"
        ) from exc
    memberships = [
        line.split(":", 2)[2]
        for line in lines
        if line.startswith("0::") and line.count(":") >= 2
    ]
    if memberships != [control_group]:
        raise ProcessContainmentError(
            "contained command gate is outside the verified control group"
        )


def _signal_cgroup_members(
    cgroup_fd: int,
    requested_signal: signal.Signals,
) -> bool:
    delivered = False
    for process_id in _cgroup_process_ids(cgroup_fd):
        try:
            pid_fd = _pidfd_open(process_id)
        except ProcessLookupError:
            continue
        try:
            # Pin the process first, then re-read membership through the retained
            # cgroup descriptor. A reused numeric PID outside this exact cgroup
            # must never receive the graceful signal.
            if process_id not in _cgroup_process_ids(cgroup_fd):
                continue
            _pidfd_send_signal(pid_fd, requested_signal)
        except ProcessLookupError:
            continue
        finally:
            os.close(pid_fd)
        delivered = True
    return delivered


def _cgroup_process_ids(cgroup_fd: int) -> tuple[int, ...]:
    file_descriptor = os.open("cgroup.procs", os.O_RDONLY, dir_fd=cgroup_fd)
    try:
        with os.fdopen(file_descriptor, "rb", closefd=False) as handle:
            raw = handle.read()
    finally:
        os.close(file_descriptor)
    return tuple(int(value) for value in raw.split())


def _kill_cgroup(cgroup_fd: int) -> None:
    file_descriptor = os.open("cgroup.kill", os.O_WRONLY, dir_fd=cgroup_fd)
    try:
        os.write(file_descriptor, b"1")
    finally:
        os.close(file_descriptor)


def _wait_for_cgroup_empty(
    cgroup_fd: int,
    timeout_seconds: float,
    *,
    repeated_signal: signal.Signals | None = None,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _cgroup_is_populated(cgroup_fd):
            return True
        if repeated_signal is not None:
            _signal_cgroup_members(cgroup_fd, repeated_signal)
        time.sleep(min(0.01, timeout_seconds))
    return not _cgroup_is_populated(cgroup_fd)


def _cgroup_is_populated(cgroup_fd: int) -> bool:
    try:
        file_descriptor = os.open("cgroup.events", os.O_RDONLY, dir_fd=cgroup_fd)
    except FileNotFoundError:
        # A cgroup cannot be removed while populated. An anchored directory
        # descriptor whose controls vanished therefore proves terminal emptiness.
        return False
    try:
        raw = os.read(file_descriptor, 4096)
    finally:
        os.close(file_descriptor)
    values = {
        key: value
        for line in raw.decode("ascii").splitlines()
        for key, value in (line.split(maxsplit=1),)
    }
    if values.get("populated") not in {"0", "1"}:
        raise OSError("cgroup.events lacks populated state")
    return values["populated"] == "1"


def _wait_for_direct_child(
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> bool:
    if process.poll() is not None:
        return True
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return False
    return True


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    process_group_id: int | None,
    grace_seconds: float,
) -> tuple[bool, bool]:
    """Retain the explicitly weaker compatibility cleanup."""

    if process_group_id is None or not _process_group_exists(process_group_id):
        process.poll()
        if process.returncode is None:
            try:
                process.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                return False, False
        return False, False

    termination_requested = _signal_process_group(process_group_id, signal.SIGTERM)
    if _wait_for_process_group_exit(process, process_group_id, grace_seconds):
        return termination_requested, False

    forced_kill = _signal_process_group(process_group_id, signal.SIGKILL)
    _wait_for_process_group_exit(process, process_group_id, grace_seconds)
    if process.poll() is None:
        try:
            process.kill()
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    return termination_requested, forced_kill


def _wait_for_process_group_exit(
    process: subprocess.Popen[bytes],
    process_group_id: int,
    timeout_seconds: float,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        process.poll()
        if not _process_group_exists(process_group_id):
            return True
        time.sleep(min(0.01, timeout_seconds))
    process.poll()
    return not _process_group_exists(process_group_id)


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process_group(
    process_group_id: int,
    requested_signal: signal.Signals,
) -> bool:
    try:
        os.killpg(process_group_id, requested_signal)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _manager_environment() -> dict[str, str]:
    names = ("DBUS_SESSION_BUS_ADDRESS", "PATH", "XDG_RUNTIME_DIR")
    return {name: os.environ[name] for name in names if os.environ.get(name)}


def _required_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise ProcessContainmentError(
            f"{name} is required for systemd scope containment",
            establishment="unsupported",
        )
    return executable


def _pidfd_open(process_id: int) -> int:
    function = _LIBC.pidfd_open
    function.argtypes = (ctypes.c_int, ctypes.c_uint)
    function.restype = ctypes.c_int
    file_descriptor = int(function(process_id, 0))
    if file_descriptor < 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    return file_descriptor


def _pidfd_send_signal(
    file_descriptor: int,
    requested_signal: int | signal.Signals,
) -> None:
    function = _LIBC.pidfd_send_signal
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    if int(function(file_descriptor, int(requested_signal), None, 0)) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))

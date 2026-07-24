"""Language-agnostic command adapter implementation."""

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import tempfile
import threading
import time
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, BinaryIO

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.adapters import (
    AdapterError,
    AdapterPreparation,
)
from legalforecast.multiharness.host_environment import (
    HostEnvironmentError,
    build_host_subprocess_environment,
    require_provider_environment_values,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import (
    validate_no_secret_values,
    validate_safe_relative_path,
)


class CommandAdapterError(AdapterError):
    """Raised when a command adapter fails or returns invalid data."""


@dataclass(frozen=True, slots=True)
class CommandExecutionLog:
    """Private log files captured from one command-adapter subprocess."""

    phase: str
    stdout_path: Path
    stderr_path: Path
    returncode: int | None
    status: str = "completed"
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    termination_requested: bool = False
    forced_kill: bool = False

    def to_private_record(self) -> dict[str, Any]:
        return {
            "schema_version": "legalforecast.multiharness.command_execution_log.v1",
            "phase": self.phase,
            "status": self.status,
            "stdout_path": self.stdout_path.as_posix(),
            "stderr_path": self.stderr_path.as_posix(),
            "returncode": self.returncode,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "termination_requested": self.termination_requested,
            "forced_kill": self.forced_kill,
        }


@dataclass(frozen=True, slots=True)
class CommandAdapter:
    """Run an adapter described by an argv-array command manifest."""

    manifest: AdapterManifest
    base_dir: Path | None = None
    timeout_seconds: float = 300
    termination_grace_seconds: float = 1
    max_private_log_bytes: int = 1_048_576

    @classmethod
    def from_manifest_file(
        cls,
        path: Path,
        *,
        timeout_seconds: float = 300,
        termination_grace_seconds: float = 1,
        max_private_log_bytes: int = 1_048_576,
    ) -> CommandAdapter:
        record = read_json_object(
            path,
            error_factory=CommandAdapterError,
            missing_message=lambda item: f"adapter manifest does not exist: {item}",
            non_object_message=lambda item: (
                f"adapter manifest must be an object: {item}"
            ),
        )
        return cls(
            manifest=AdapterManifest.from_record(record),
            base_dir=path.parent,
            timeout_seconds=timeout_seconds,
            termination_grace_seconds=termination_grace_seconds,
            max_private_log_bytes=max_private_log_bytes,
        )

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        output_path = workspace / "adapter-capabilities.json"
        self._invoke(
            "capabilities",
            ("capabilities", "--output", str(output_path)),
            workspace=workspace,
        )
        capabilities = AdapterCapabilities.from_record(
            _read_command_json(output_path, "adapter capabilities")
        )
        if capabilities.adapter_id != self.manifest.adapter_id:
            raise CommandAdapterError("adapter capabilities ID does not match manifest")
        if capabilities.adapter_version != self.manifest.adapter_version:
            raise CommandAdapterError(
                "adapter capabilities version does not match manifest"
            )
        return capabilities

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        capabilities = self.capabilities(workspace)
        if request.adapter.adapter_id != self.manifest.adapter_id:
            raise CommandAdapterError("run request adapter ID does not match manifest")
        if request.adapter.adapter_version != self.manifest.adapter_version:
            raise CommandAdapterError(
                "run request adapter version does not match manifest"
            )
        if request.task.family not in capabilities.supported_families:
            raise CommandAdapterError(
                f"adapter does not support task family: {request.task.family}"
            )
        if request.task.scoring_mode not in capabilities.supported_scoring_modes:
            raise CommandAdapterError(
                f"adapter does not support scoring mode: {request.task.scoring_mode}"
            )
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        workspace.mkdir(parents=True, exist_ok=True)
        request_path = workspace / "request.json"
        output_path = workspace / "result.json"
        private_output_path = workspace / "private-logs" / "run-result.raw.json"
        output_path.unlink(missing_ok=True)
        self.prepare(request, workspace)
        private_output_path.unlink(missing_ok=True)
        write_json_object(request_path, request.to_record())
        self._invoke(
            "run",
            (
                "run",
                "--request",
                str(request_path),
                "--output",
                str(private_output_path),
                "--workspace",
                str(workspace),
            ),
            workspace=workspace,
            allowed_provider_env_vars=(
                request.sandbox_policy.allowed_provider_env_vars
            ),
        )
        result = RunResult.from_record(
            _read_command_json(private_output_path, "run result")
        )
        if result.request_id != request.request_id:
            raise CommandAdapterError("run result request_id does not match request")
        _validate_result_artifacts(result)
        provider_values = require_provider_environment_values(
            request.sandbox_policy.allowed_provider_env_vars
        )
        validate_no_secret_values(
            result.to_record(),
            tuple(provider_values.values()),
            "run result",
        )
        write_json_object(output_path, result.to_record())
        return result

    def _invoke(
        self,
        phase: str,
        args: Sequence[str],
        *,
        workspace: Path,
        allowed_provider_env_vars: Sequence[str] = (),
    ) -> CommandExecutionLog:
        if self.timeout_seconds <= 0:
            raise CommandAdapterError("timeout_seconds must be positive")
        if self.termination_grace_seconds <= 0:
            raise CommandAdapterError("termination_grace_seconds must be positive")
        if self.max_private_log_bytes <= 0:
            raise CommandAdapterError("max_private_log_bytes must be positive")
        if os.name != "posix":
            raise CommandAdapterError(
                "command adapter process-group cleanup requires POSIX process groups"
            )
        workspace.mkdir(parents=True, exist_ok=True)
        private_logs = workspace / "private-logs"
        private_logs.mkdir(parents=True, exist_ok=True)
        stdout_path = private_logs / f"{phase}-stdout.log"
        stderr_path = private_logs / f"{phase}-stderr.log"
        execution_path = private_logs / f"{phase}-execution.json"
        argv = (*self._resolved_command(), *args)
        try:
            environment = build_host_subprocess_environment(
                private_logs,
                allowed_provider_env_vars,
            )
        except HostEnvironmentError as exc:
            raise CommandAdapterError(str(exc)) from exc

        status = "launch_failed"
        returncode: int | None = None
        termination_requested = False
        forced_kill = False
        pending_error: BaseException | None = None
        with (
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stdout_handle,
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stderr_handle,
        ):
            try:
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    env=environment,
                    start_new_session=True,
                )
            except OSError as exc:
                pending_error = exc
            else:
                try:
                    with _command_cancellation_signal_handlers():
                        process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    status = "timed_out"
                    termination_requested, forced_kill = _terminate_process_group(
                        process,
                        self.termination_grace_seconds,
                    )
                except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
                    status = "cancelled"
                    pending_error = exc
                    termination_requested, forced_kill = _terminate_process_group(
                        process,
                        self.termination_grace_seconds,
                    )
                except Exception as exc:
                    status = "exception"
                    pending_error = exc
                    termination_requested, forced_kill = _terminate_process_group(
                        process,
                        self.termination_grace_seconds,
                    )
                else:
                    returncode = process.returncode
                    status = "completed" if returncode == 0 else "failed"
                    termination_requested, forced_kill = _terminate_process_group(
                        process,
                        self.termination_grace_seconds,
                    )
                    if returncode == 0 and (termination_requested or forced_kill):
                        status = "process_group_cleanup_requested"
                returncode = process.returncode

            stdout_content, stdout_truncated = _bounded_private_log(
                stdout_handle,
                self.max_private_log_bytes,
            )
            stderr_content, stderr_truncated = _bounded_private_log(
                stderr_handle,
                self.max_private_log_bytes,
            )

        _write_private_bytes(stdout_path, stdout_content)
        _write_private_bytes(stderr_path, stderr_content)
        execution = CommandExecutionLog(
            phase=phase,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            returncode=returncode,
            status=status,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            termination_requested=termination_requested,
            forced_kill=forced_kill,
        )
        _write_private_record(execution_path, execution.to_private_record())

        if status == "timed_out":
            raise CommandAdapterError(
                f"command adapter {phase} timed out after {self.timeout_seconds}s"
            )
        if status == "cancelled":
            raise CommandAdapterError(f"command adapter {phase} was cancelled") from (
                pending_error
            )
        if pending_error is not None:
            raise CommandAdapterError(
                f"command adapter {phase} could not complete; see private logs"
            ) from pending_error
        if status == "process_group_cleanup_requested":
            raise CommandAdapterError(
                f"command adapter {phase} left processes in its original process "
                "group; group-scoped cleanup was requested; see private logs"
            )
        if returncode != 0:
            raise CommandAdapterError(
                f"command adapter {phase} failed with exit code "
                f"{returncode}; see private logs"
            )
        return execution

    def _resolved_command(self) -> tuple[str, ...]:
        command = self.manifest.command
        executable = command[0]
        if _looks_like_relative_path(executable):
            if self.base_dir is None:
                raise CommandAdapterError("relative adapter command requires base_dir")
            resolved = self.base_dir / executable
            return (str(resolved), *command[1:])
        return command


def _read_command_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
        path,
        error_factory=CommandAdapterError,
        missing_message=lambda item: f"{label} was not written: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _validate_result_artifacts(result: RunResult) -> None:
    for artifact in result.artifacts:
        validate_safe_relative_path(artifact.path, "artifact.path")


def _looks_like_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and (
        value.startswith(".") or "/" in value or "\\" in value
    )


_TRUNCATION_MARKER = b"\n...[truncated by LegalForecastBench]...\n"


class _CommandCancellationSignal(BaseException):
    """Internal interruption raised while a command-adapter subprocess is active."""


def _raise_command_cancellation_signal(
    requested_signal: int,
    frame: FrameType | None,
) -> None:
    del requested_signal, frame
    raise _CommandCancellationSignal


@contextmanager
def _command_cancellation_signal_handlers() -> Generator[None, None, None]:
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _raise_command_cancellation_signal)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    grace_seconds: float,
) -> tuple[bool, bool]:
    """Best-effort cleanup of the adapter leader's original process group.

    Descendants that create a new session or process group are outside this
    helper's scope. The returned booleans report whether SIGTERM and SIGKILL
    were delivered to the original group, not whether every descendant stopped.
    """
    process_group_id = process.pid
    if not _process_group_exists(process_group_id):
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
            pass  # The leader exited or is no longer signalable; preserve the receipt.
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        return termination_requested, forced_kill
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
    process_group_id: int, requested_signal: signal.Signals
) -> bool:
    try:
        os.killpg(process_group_id, requested_signal)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _bounded_private_log(
    handle: BinaryIO,
    max_bytes: int,
) -> tuple[bytes, bool]:
    handle.flush()
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(0)
    raw = handle.read(max_bytes)
    normalized = raw.decode("utf-8", errors="replace").encode("utf-8")
    truncated = size > max_bytes or len(normalized) > max_bytes
    if truncated:
        marker = _TRUNCATION_MARKER[:max_bytes]
        prefix_budget = max_bytes - len(marker)
        prefix = normalized[:prefix_budget].decode("utf-8", errors="ignore")
        normalized = prefix.encode("utf-8") + marker
    return normalized, truncated


def _write_private_record(path: Path, record: Mapping[str, Any]) -> None:
    payload = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    _write_private_bytes(path, payload + b"\n")


def _write_private_bytes(path: Path, payload: bytes) -> None:
    try:
        path_info = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(path_info.st_mode):
            raise CommandAdapterError("private execution paths must not be symlinks")
        if not stat.S_ISREG(path_info.st_mode):
            raise CommandAdapterError("private execution paths must be regular files")
        try:
            path.unlink()
        except OSError as exc:
            raise CommandAdapterError(
                "private execution path could not be replaced"
            ) from exc

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        file_descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise CommandAdapterError(
            "private execution path could not be created"
        ) from exc
    try:
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = -1
            handle.write(payload)
            handle.flush()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)

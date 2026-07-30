"""Language-agnostic command adapter implementation."""

from __future__ import annotations

import json
import os
import selectors
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
    ToolExecutor,
)
from legalforecast.multiharness.host_environment import (
    HostEnvironmentError,
    build_host_subprocess_environment,
    require_provider_environment_values,
)
from legalforecast.multiharness.process_containment import (
    ProcessContainmentError,
    ProcessContainmentEvidence,
    ProcessContainmentHandle,
    abandon_prepared_containment,
    cleanup_process_containment,
    containment_launcher_environment,
    establish_process_containment,
    launch_failure_evidence,
    preflight_process_containment,
    prepare_contained_command,
    release_contained_command,
)
from legalforecast.multiharness.spec import (
    LINUX_SYSTEMD_SCOPE_CONTAINMENT,
    POSIX_PROCESS_GROUP_CONTAINMENT,
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolResponse,
    decode_tool_request,
    encode_tool_message,
)
from legalforecast.multiharness.validation import (
    validate_no_secret_values,
    validate_safe_relative_path,
)


class CommandAdapterError(AdapterError):
    """Raised when a command adapter fails or returns invalid data."""


_MAX_TOOL_EXCHANGES = 256


@dataclass(frozen=True, slots=True)
class CommandExecutionLog:
    """Private log files captured from one command-adapter subprocess."""

    phase: str
    stdout_path: Path
    stderr_path: Path
    returncode: int | None
    containment: ProcessContainmentEvidence
    status: str = "completed"
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    termination_requested: bool = False
    forced_kill: bool = False

    def to_private_record(self) -> dict[str, Any]:
        return {
            "schema_version": "legalforecast.multiharness.command_execution_log.v2",
            "phase": self.phase,
            "status": self.status,
            "stdout_path": self.stdout_path.as_posix(),
            "stderr_path": self.stderr_path.as_posix(),
            "returncode": self.returncode,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "termination_requested": self.termination_requested,
            "forced_kill": self.forced_kill,
            "containment": self.containment.to_private_record(),
        }


@dataclass(slots=True)
class _ContainedProcessOwnership:
    """Caller-visible ownership before cancellation can cross the return boundary."""

    process: subprocess.Popen[bytes] | None = None
    handle: ProcessContainmentHandle | None = None


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

    def capabilities(
        self,
        workspace: Path,
        *,
        host_process_containment: str = POSIX_PROCESS_GROUP_CONTAINMENT,
    ) -> AdapterCapabilities:
        output_path = workspace / "adapter-capabilities.json"
        output_path.unlink(missing_ok=True)
        self._invoke(
            "capabilities",
            ("capabilities", "--output", str(output_path)),
            workspace=workspace,
            host_process_containment=host_process_containment,
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
        requested_containment = request.sandbox_policy.host_process_containment
        if requested_containment == POSIX_PROCESS_GROUP_CONTAINMENT:
            capabilities = self.capabilities(workspace)
        else:
            capabilities = self.capabilities(
                workspace,
                host_process_containment=requested_containment,
            )
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
            host_process_containment=(request.sandbox_policy.host_process_containment),
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

    def run_with_tools(
        self,
        request: RunRequest,
        workspace: Path,
        tool_executor: ToolExecutor,
    ) -> RunResult:
        """Run an adapter over a bounded duplex JSONL tool channel."""

        workspace.mkdir(parents=True, exist_ok=True)
        request_path = workspace / "request.json"
        output_path = workspace / "result.json"
        private_output_path = (
            workspace / "private-logs" / "run-with-tools-result.raw.json"
        )
        output_path.unlink(missing_ok=True)
        preparation = self.prepare(request, workspace)
        if (
            preparation.capabilities.tool_protocol_version
            != TOOL_REQUEST_SCHEMA_VERSION
        ):
            raise CommandAdapterError(
                "adapter does not advertise tool protocol "
                f"{TOOL_REQUEST_SCHEMA_VERSION}"
            )
        private_output_path.unlink(missing_ok=True)
        write_json_object(request_path, request.to_record())
        self._invoke_with_tools(
            (
                "run-with-tools",
                "--request",
                str(request_path),
                "--output",
                str(private_output_path),
                "--workspace",
                str(workspace),
            ),
            request=request,
            workspace=workspace,
            tool_executor=tool_executor,
        )
        result = RunResult.from_record(
            _read_command_json(private_output_path, "run-with-tools result")
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

    def _invoke_with_tools(
        self,
        args: Sequence[str],
        *,
        request: RunRequest,
        workspace: Path,
        tool_executor: ToolExecutor,
    ) -> CommandExecutionLog:
        phase = "run-with-tools"
        self._validate_execution_settings()
        workspace.mkdir(parents=True, exist_ok=True)
        private_logs = workspace / "private-logs"
        private_logs.mkdir(parents=True, exist_ok=True)
        stdout_path = private_logs / f"{phase}-stdout.log"
        stderr_path = private_logs / f"{phase}-stderr.log"
        execution_path = private_logs / f"{phase}-execution.json"
        argv = (*self._resolved_command(), *args)
        requested_containment = request.sandbox_policy.host_process_containment

        status = "launch_failed"
        returncode: int | None = None
        containment = launch_failure_evidence(requested_containment)
        pending_error: BaseException | None = None
        with (
            _deferred_command_cancellation_signal_handlers() as lifecycle_deferred,
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stdout_handle,
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stderr_handle,
        ):
            ownership = _ContainedProcessOwnership()
            try:
                with _command_cancellation_signal_handlers():
                    _launch_contained_adapter(
                        argv,
                        ownership=ownership,
                        requested=requested_containment,
                        private_logs=private_logs,
                        allowed_provider_env_vars=(
                            request.sandbox_policy.allowed_provider_env_vars
                        ),
                        runtime_max_seconds=(
                            self.timeout_seconds
                            + (2 * self.termination_grace_seconds)
                            + 5
                        ),
                        termination_grace_seconds=self.termination_grace_seconds,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=stderr_handle,
                    )
                assert ownership.process is not None
                assert ownership.handle is not None
                process = ownership.process
                containment_handle = ownership.handle
            except _ContainedLaunchError as exc:
                pending_error = exc.public_error
                containment = exc.evidence
                status = exc.status
            except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
                status = "cancelled"
                pending_error = exc
                if ownership.process is not None and ownership.handle is not None:
                    with _deferred_command_cancellation_signal_handlers():
                        containment = _cleanup_contained_process(
                            ownership.handle,
                            ownership.process,
                            self.termination_grace_seconds,
                        )
            else:
                try:
                    with _command_cancellation_signal_handlers():
                        _exchange_tool_messages(
                            process,
                            stdout_handle,
                            tool_executor,
                            workspace,
                            self.timeout_seconds,
                        )
                except subprocess.TimeoutExpired:
                    status = "timed_out"
                except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
                    status = "cancelled"
                    pending_error = exc
                except Exception as exc:
                    status = "exception"
                    pending_error = exc
                else:
                    returncode = process.returncode
                    status = "completed" if returncode == 0 else "failed"
                with _deferred_command_cancellation_signal_handlers() as deferred:
                    containment = _cleanup_contained_process(
                        containment_handle,
                        process,
                        self.termination_grace_seconds,
                    )
                if deferred.received:
                    status = "cancelled"
                    pending_error = _CommandCancellationSignal()
                returncode = process.returncode
                if (
                    status == "completed"
                    and returncode == 0
                    and containment.cleanup_requested
                ):
                    status = (
                        "process_group_cleanup_requested"
                        if requested_containment == POSIX_PROCESS_GROUP_CONTAINMENT
                        else "descendant_cleanup_requested"
                    )

            stdout_content, stdout_truncated = _bounded_private_log(
                stdout_handle,
                self.max_private_log_bytes,
            )
            stderr_content, stderr_truncated = _bounded_private_log(
                stderr_handle,
                self.max_private_log_bytes,
            )
            if lifecycle_deferred.received:
                status = "cancelled"
                pending_error = _CommandCancellationSignal()
            _write_private_bytes(stdout_path, stdout_content)
            _write_private_bytes(stderr_path, stderr_content)
            execution = CommandExecutionLog(
                phase=phase,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                returncode=returncode,
                containment=containment,
                status=status,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                termination_requested=containment.termination_requested,
                forced_kill=containment.forced_kill,
            )
            _write_private_record(execution_path, execution.to_private_record())
        if lifecycle_deferred.received and execution.status != "cancelled":
            pending_error = _CommandCancellationSignal()
            execution = CommandExecutionLog(
                phase=execution.phase,
                stdout_path=execution.stdout_path,
                stderr_path=execution.stderr_path,
                returncode=execution.returncode,
                containment=execution.containment,
                status="cancelled",
                stdout_truncated=execution.stdout_truncated,
                stderr_truncated=execution.stderr_truncated,
                termination_requested=execution.termination_requested,
                forced_kill=execution.forced_kill,
            )
            _write_private_record(execution_path, execution.to_private_record())
        _raise_for_execution(
            execution,
            pending_error=pending_error,
            timeout_seconds=self.timeout_seconds,
        )
        return execution

    def _invoke(
        self,
        phase: str,
        args: Sequence[str],
        *,
        workspace: Path,
        allowed_provider_env_vars: Sequence[str] = (),
        host_process_containment: str = POSIX_PROCESS_GROUP_CONTAINMENT,
    ) -> CommandExecutionLog:
        self._validate_execution_settings()
        workspace.mkdir(parents=True, exist_ok=True)
        private_logs = workspace / "private-logs"
        private_logs.mkdir(parents=True, exist_ok=True)
        stdout_path = private_logs / f"{phase}-stdout.log"
        stderr_path = private_logs / f"{phase}-stderr.log"
        execution_path = private_logs / f"{phase}-execution.json"
        argv = (*self._resolved_command(), *args)

        status = "launch_failed"
        returncode: int | None = None
        containment = launch_failure_evidence(host_process_containment)
        pending_error: BaseException | None = None
        with (
            _deferred_command_cancellation_signal_handlers() as lifecycle_deferred,
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stdout_handle,
            tempfile.TemporaryFile(mode="w+b", dir=private_logs) as stderr_handle,
        ):
            ownership = _ContainedProcessOwnership()
            try:
                with _command_cancellation_signal_handlers():
                    _launch_contained_adapter(
                        argv,
                        ownership=ownership,
                        requested=host_process_containment,
                        private_logs=private_logs,
                        allowed_provider_env_vars=allowed_provider_env_vars,
                        runtime_max_seconds=(
                            self.timeout_seconds
                            + (2 * self.termination_grace_seconds)
                            + 5
                        ),
                        termination_grace_seconds=self.termination_grace_seconds,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                    )
                assert ownership.process is not None
                assert ownership.handle is not None
                process = ownership.process
                containment_handle = ownership.handle
            except _ContainedLaunchError as exc:
                pending_error = exc.public_error
                containment = exc.evidence
                status = exc.status
            except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
                status = "cancelled"
                pending_error = exc
                if ownership.process is not None and ownership.handle is not None:
                    with _deferred_command_cancellation_signal_handlers():
                        containment = _cleanup_contained_process(
                            ownership.handle,
                            ownership.process,
                            self.termination_grace_seconds,
                        )
            else:
                try:
                    with _command_cancellation_signal_handlers():
                        process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    status = "timed_out"
                except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
                    status = "cancelled"
                    pending_error = exc
                except Exception as exc:
                    status = "exception"
                    pending_error = exc
                else:
                    returncode = process.returncode
                    status = "completed" if returncode == 0 else "failed"
                with _deferred_command_cancellation_signal_handlers() as deferred:
                    containment = _cleanup_contained_process(
                        containment_handle,
                        process,
                        self.termination_grace_seconds,
                    )
                if deferred.received:
                    status = "cancelled"
                    pending_error = _CommandCancellationSignal()
                returncode = process.returncode
                if (
                    status == "completed"
                    and returncode == 0
                    and containment.cleanup_requested
                ):
                    status = (
                        "process_group_cleanup_requested"
                        if host_process_containment == POSIX_PROCESS_GROUP_CONTAINMENT
                        else "descendant_cleanup_requested"
                    )

            stdout_content, stdout_truncated = _bounded_private_log(
                stdout_handle,
                self.max_private_log_bytes,
            )
            stderr_content, stderr_truncated = _bounded_private_log(
                stderr_handle,
                self.max_private_log_bytes,
            )
            if lifecycle_deferred.received:
                status = "cancelled"
                pending_error = _CommandCancellationSignal()
            _write_private_bytes(stdout_path, stdout_content)
            _write_private_bytes(stderr_path, stderr_content)
            execution = CommandExecutionLog(
                phase=phase,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                returncode=returncode,
                containment=containment,
                status=status,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                termination_requested=containment.termination_requested,
                forced_kill=containment.forced_kill,
            )
            _write_private_record(execution_path, execution.to_private_record())
        if lifecycle_deferred.received and execution.status != "cancelled":
            pending_error = _CommandCancellationSignal()
            execution = CommandExecutionLog(
                phase=execution.phase,
                stdout_path=execution.stdout_path,
                stderr_path=execution.stderr_path,
                returncode=execution.returncode,
                containment=execution.containment,
                status="cancelled",
                stdout_truncated=execution.stdout_truncated,
                stderr_truncated=execution.stderr_truncated,
                termination_requested=execution.termination_requested,
                forced_kill=execution.forced_kill,
            )
            _write_private_record(execution_path, execution.to_private_record())
        _raise_for_execution(
            execution,
            pending_error=pending_error,
            timeout_seconds=self.timeout_seconds,
        )
        return execution

    def _validate_execution_settings(self) -> None:
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

    def _resolved_command(self) -> tuple[str, ...]:
        command = self.manifest.command
        executable = command[0]
        if _looks_like_relative_path(executable):
            if self.base_dir is None:
                raise CommandAdapterError("relative adapter command requires base_dir")
            resolved = self.base_dir / executable
            return (str(resolved), *command[1:])
        return command


class _ContainedLaunchError(Exception):
    """Internal launch failure carrying truthful private evidence."""

    def __init__(
        self,
        public_error: CommandAdapterError,
        evidence: ProcessContainmentEvidence,
        *,
        status: str = "launch_failed",
    ) -> None:
        super().__init__(str(public_error))
        self.public_error = public_error
        self.evidence = evidence
        self.status = status


def _launch_contained_adapter(
    argv: tuple[str, ...],
    *,
    ownership: _ContainedProcessOwnership,
    requested: str,
    private_logs: Path,
    allowed_provider_env_vars: Sequence[str],
    runtime_max_seconds: float,
    termination_grace_seconds: float,
    stdin: Any,
    stdout: Any,
    stderr: Any,
) -> None:
    try:
        preflight_process_containment(requested)
        deferred_provider_environment = requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT
        environment = build_host_subprocess_environment(
            private_logs,
            () if deferred_provider_environment else allowed_provider_env_vars,
        )
        environment.update(containment_launcher_environment(requested))
        prepared = prepare_contained_command(
            requested,
            argv,
            private_logs=private_logs,
            runtime_max_seconds=runtime_max_seconds,
        )
    except ProcessContainmentError as exc:
        raise _ContainedLaunchError(
            CommandAdapterError(
                "required host process containment was unavailable before "
                f"adapter launch: {exc}"
            ),
            launch_failure_evidence(
                requested,
                establishment=exc.establishment,
            ),
        ) from exc
    except HostEnvironmentError as exc:
        raise _ContainedLaunchError(
            CommandAdapterError(str(exc)),
            launch_failure_evidence(requested),
        ) from exc
    except (KeyboardInterrupt, _CommandCancellationSignal) as exc:
        raise _ContainedLaunchError(
            CommandAdapterError("command adapter launch was cancelled"),
            launch_failure_evidence(requested),
            status="cancelled",
        ) from exc

    process: subprocess.Popen[bytes] | None = None
    handle: ProcessContainmentHandle | None = None
    try:
        process = subprocess.Popen(
            prepared.argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=environment,
            start_new_session=True,
        )
        handle = ProcessContainmentHandle(
            requested=requested,
            unit_name=prepared.unit_name,
        )
        handle = establish_process_containment(prepared, process, handle)
        if deferred_provider_environment:
            provider_environment = require_provider_environment_values(
                allowed_provider_env_vars
            )
            release_contained_command(handle, provider_environment)
        ownership.process = process
        ownership.handle = handle
    except OSError as exc:
        if process is None:
            abandon_prepared_containment(prepared)
            evidence = launch_failure_evidence(requested)
        elif handle is None or handle.cgroup_fd is None:
            abandon_prepared_containment(prepared)
            _discard_partial_containment_handle(handle)
            _stop_unreleased_direct_child(process, termination_grace_seconds)
            evidence = _unverified_launch_cleanup_evidence(
                requested,
                unit_name=prepared.unit_name,
            )
        else:
            with _deferred_command_cancellation_signal_handlers():
                evidence = _cleanup_contained_process(
                    handle,
                    process,
                    termination_grace_seconds,
                )
        raise _ContainedLaunchError(
            CommandAdapterError("command adapter could not complete; see private logs"),
            evidence,
        ) from exc
    except (
        HostEnvironmentError,
        ProcessContainmentError,
        KeyboardInterrupt,
        _CommandCancellationSignal,
    ) as exc:
        if handle is None or (
            requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT and handle.cgroup_fd is None
        ):
            abandon_prepared_containment(prepared)
            _discard_partial_containment_handle(handle)
            if process is not None:
                _stop_unreleased_direct_child(process, termination_grace_seconds)
            if process is None:
                evidence = launch_failure_evidence(
                    requested,
                    establishment=(
                        exc.establishment
                        if isinstance(exc, ProcessContainmentError)
                        else "failed"
                    ),
                )
            else:
                evidence = _unverified_launch_cleanup_evidence(
                    requested,
                    unit_name=prepared.unit_name,
                )
        else:
            assert process is not None
            with _deferred_command_cancellation_signal_handlers():
                evidence = _cleanup_contained_process(
                    handle,
                    process,
                    termination_grace_seconds,
                )
        if isinstance(exc, (KeyboardInterrupt, _CommandCancellationSignal)):
            public_error = CommandAdapterError("command adapter launch was cancelled")
            status = "cancelled"
        elif isinstance(exc, HostEnvironmentError):
            public_error = CommandAdapterError(str(exc))
            status = "launch_failed"
        else:
            public_error = CommandAdapterError(
                "required host process containment failed before adapter "
                f"execution: {exc}"
            )
            status = "launch_failed"
        raise _ContainedLaunchError(
            public_error,
            evidence,
            status=status,
        ) from exc
    return None


def _discard_partial_containment_handle(
    handle: ProcessContainmentHandle | None,
) -> None:
    if handle is None:
        return
    if handle.control is not None:
        handle.control.close()
        handle.control = None
    if handle.gate_pidfd is not None:
        os.close(handle.gate_pidfd)
        handle.gate_pidfd = None
    if handle.cgroup_fd is not None:
        os.close(handle.cgroup_fd)
        handle.cgroup_fd = None


def _unverified_launch_cleanup_evidence(
    requested: str,
    *,
    unit_name: str | None,
) -> ProcessContainmentEvidence:
    mechanism = (
        "systemd_user_scope_cgroup_v2"
        if requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT
        else "posix_process_group"
    )
    return ProcessContainmentEvidence(
        requested=requested,
        establishment="failed",
        mechanism=mechanism,
        cleanup_requested=True,
        termination_requested=True,
        cleanup_outcome="incomplete",
        populated_after_cleanup=None,
        unit_name=unit_name,
    )


def _stop_unreleased_direct_child(
    process: subprocess.Popen[bytes],
    grace_seconds: float,
) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass


def _cleanup_contained_process(
    handle: ProcessContainmentHandle,
    process: subprocess.Popen[bytes],
    grace_seconds: float,
) -> ProcessContainmentEvidence:
    try:
        return cleanup_process_containment(handle, process, grace_seconds)
    except (OSError, ProcessContainmentError):
        mechanism = (
            "systemd_user_scope_cgroup_v2"
            if handle.requested == LINUX_SYSTEMD_SCOPE_CONTAINMENT
            else "posix_process_group"
        )
        return ProcessContainmentEvidence(
            requested=handle.requested,
            establishment="established",
            mechanism=mechanism,
            cleanup_requested=True,
            cleanup_outcome="incomplete",
            populated_after_cleanup=None,
            unit_name=handle.unit_name,
            invocation_id=handle.invocation_id,
            control_group=handle.control_group,
        )


def _raise_for_execution(
    execution: CommandExecutionLog,
    *,
    pending_error: BaseException | None,
    timeout_seconds: float,
) -> None:
    phase = execution.phase
    containment = execution.containment
    if containment.cleanup_outcome not in {"not_required", "succeeded"}:
        raise CommandAdapterError(
            f"command adapter {phase} containment cleanup was "
            f"{containment.cleanup_outcome}; see private logs"
        ) from pending_error
    if execution.status == "timed_out":
        raise CommandAdapterError(
            f"command adapter {phase} timed out after {timeout_seconds}s"
        )
    if execution.status == "cancelled":
        raise CommandAdapterError(f"command adapter {phase} was cancelled") from (
            pending_error
        )
    if isinstance(pending_error, CommandAdapterError):
        raise pending_error
    if pending_error is not None:
        raise CommandAdapterError(
            f"command adapter {phase} could not complete; see private logs"
        ) from pending_error
    if execution.status in {
        "descendant_cleanup_requested",
        "process_group_cleanup_requested",
    }:
        if containment.requested == POSIX_PROCESS_GROUP_CONTAINMENT:
            detail = "its original process group; group-scoped"
        else:
            detail = "its verified control group; descendant"
        raise CommandAdapterError(
            f"command adapter {phase} left processes in {detail} cleanup was "
            "requested; see private logs"
        )
    if execution.returncode != 0:
        raise CommandAdapterError(
            f"command adapter {phase} failed with exit code "
            f"{execution.returncode}; see private logs"
        )


def _exchange_tool_messages(
    process: subprocess.Popen[bytes],
    stdout_log: BinaryIO,
    tool_executor: ToolExecutor,
    workspace: Path,
    timeout_seconds: float,
) -> None:
    """Exchange bounded request/response lines until the adapter exits."""

    if process.stdin is None or process.stdout is None:
        raise CommandAdapterError("tool request stream was not connected")
    stdin = process.stdin
    stdout = process.stdout
    os.set_blocking(stdin.fileno(), False)
    os.set_blocking(stdout.fileno(), False)
    deadline = time.monotonic() + timeout_seconds
    request_buffer = bytearray()
    response_buffer = bytearray()
    seen_request_ids: set[str] = set()
    stdout_open = True
    stdin_registered = False

    try:
        with selectors.DefaultSelector() as selector:
            selector.register(stdout, selectors.EVENT_READ)
            while stdout_open or response_buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(process.args, timeout_seconds)
                if response_buffer and not stdin_registered:
                    selector.register(stdin, selectors.EVENT_WRITE)
                    stdin_registered = True

                events = selector.select(remaining)
                if not events:
                    raise subprocess.TimeoutExpired(process.args, timeout_seconds)
                for key, event_mask in events:
                    if key.fileobj is stdout and event_mask & selectors.EVENT_READ:
                        try:
                            chunk = os.read(stdout.fileno(), 65_536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(stdout)
                            stdout_open = False
                            if request_buffer:
                                raise CommandAdapterError(
                                    "invalid tool request stream; trailing partial line"
                                )
                            continue
                        stdout_log.write(chunk)
                        request_buffer.extend(chunk)
                        if (
                            len(request_buffer) > MAX_TOOL_MESSAGE_BYTES
                            and b"\n" not in request_buffer
                        ):
                            raise CommandAdapterError(
                                "invalid tool request stream; message exceeds maximum "
                                "size"
                            )
                        newline_index = request_buffer.find(b"\n") + 1
                        if newline_index:
                            line = bytes(request_buffer[:newline_index])
                            del request_buffer[:newline_index]
                            try:
                                tool_request = decode_tool_request(line)
                            except ValueError as exc:
                                raise CommandAdapterError(
                                    "invalid tool request stream; see private logs"
                                ) from exc
                            if tool_request.request_id in seen_request_ids:
                                raise CommandAdapterError(
                                    "invalid tool request stream; duplicate request_id"
                                )
                            if len(seen_request_ids) >= _MAX_TOOL_EXCHANGES:
                                raise CommandAdapterError(
                                    "tool request stream exceeded exchange limit"
                                )
                            seen_request_ids.add(tool_request.request_id)
                            tool_response = _require_tool_response(
                                tool_executor.execute(
                                    tool_request,
                                    workspace,
                                )
                            )
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(
                                    process.args,
                                    timeout_seconds,
                                )
                            if tool_response.request_id != tool_request.request_id:
                                raise CommandAdapterError(
                                    "tool response request_id does not match request"
                                )
                            try:
                                response_buffer.extend(
                                    encode_tool_message(tool_response)
                                )
                            except ValueError as exc:
                                raise CommandAdapterError(
                                    "tool executor returned an invalid response"
                                ) from exc
                            if len(response_buffer) > MAX_TOOL_MESSAGE_BYTES:
                                raise CommandAdapterError(
                                    "tool response stream exceeds maximum size"
                                )
                            if request_buffer:
                                raise CommandAdapterError(
                                    "invalid tool request stream; pipelined requests "
                                    "are not allowed"
                                )

                    if key.fileobj is stdin and event_mask & selectors.EVENT_WRITE:
                        try:
                            written = os.write(stdin.fileno(), response_buffer)
                        except (BrokenPipeError, OSError) as exc:
                            raise CommandAdapterError(
                                "adapter closed the tool response stream"
                            ) from exc
                        del response_buffer[:written]
                        if not response_buffer:
                            selector.unregister(stdin)
                            stdin_registered = False

            if response_buffer:
                raise CommandAdapterError(
                    "adapter exited before accepting its tool response"
                )
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
    finally:
        stdin.close()
        stdout.close()


def _require_tool_response(value: object) -> ToolResponse:
    if not isinstance(value, ToolResponse):
        raise CommandAdapterError("tool executor returned an invalid response")
    return value


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


@dataclass(slots=True)
class _DeferredCommandCancellation:
    """Cancellation observed while exact-identity cleanup must finish."""

    received: bool = False


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

    watched = (signal.SIGINT, signal.SIGTERM)
    previous_handlers = {
        requested_signal: signal.getsignal(requested_signal)
        for requested_signal in watched
    }
    for requested_signal in watched:
        signal.signal(requested_signal, _raise_command_cancellation_signal)
    try:
        yield
    finally:
        for requested_signal, previous_handler in previous_handlers.items():
            signal.signal(requested_signal, previous_handler)


@contextmanager
def _deferred_command_cancellation_signal_handlers() -> Generator[
    _DeferredCommandCancellation, None, None
]:
    state = _DeferredCommandCancellation()
    if threading.current_thread() is not threading.main_thread():
        yield state
        return

    watched = (signal.SIGINT, signal.SIGTERM)
    previous_handlers = {
        requested_signal: signal.getsignal(requested_signal)
        for requested_signal in watched
    }

    def record_cancellation(
        requested_signal: int,
        frame: FrameType | None,
    ) -> None:
        del requested_signal, frame
        state.received = True

    for requested_signal in watched:
        signal.signal(requested_signal, record_cancellation)
    try:
        yield state
    finally:
        for requested_signal, previous_handler in previous_handlers.items():
            signal.signal(requested_signal, previous_handler)


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

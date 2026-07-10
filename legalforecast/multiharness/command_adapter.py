"""Language-agnostic command adapter implementation."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    returncode: int

    def to_private_record(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "stdout_path": self.stdout_path.as_posix(),
            "stderr_path": self.stderr_path.as_posix(),
            "returncode": self.returncode,
        }


@dataclass(frozen=True, slots=True)
class CommandAdapter:
    """Run an adapter described by an argv-array command manifest."""

    manifest: AdapterManifest
    base_dir: Path | None = None
    timeout_seconds: float = 300

    @classmethod
    def from_manifest_file(
        cls,
        path: Path,
        *,
        timeout_seconds: float = 300,
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
        workspace.mkdir(parents=True, exist_ok=True)
        private_logs = workspace / "private-logs"
        private_logs.mkdir(parents=True, exist_ok=True)
        stdout_path = private_logs / f"{phase}-stdout.log"
        stderr_path = private_logs / f"{phase}-stderr.log"
        argv = (*self._resolved_command(), *args)
        try:
            environment = build_host_subprocess_environment(
                private_logs,
                allowed_provider_env_vars,
            )
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
                errors="replace",
                text=True,
                timeout=self.timeout_seconds,
            )
        except HostEnvironmentError as exc:
            raise CommandAdapterError(str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(_stream_text(exc.stdout), encoding="utf-8")
            stderr_path.write_text(_stream_text(exc.stderr), encoding="utf-8")
            raise CommandAdapterError(
                f"command adapter {phase} timed out after {self.timeout_seconds}s"
            ) from exc
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise CommandAdapterError(
                f"command adapter {phase} failed with exit code "
                f"{completed.returncode}; see private logs"
            )
        return CommandExecutionLog(
            phase=phase,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            returncode=completed.returncode,
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


def _stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

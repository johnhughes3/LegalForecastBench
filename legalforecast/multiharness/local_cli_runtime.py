"""Shared local CLI execution service for contained solver processes.

Adapters call this service instead of spawning CLIs themselves. Scheduling and
concurrency enforcement belong to ``dm0g.4.2.10``; this module only exposes
hooks. B1's adapter-manifest fields are stubbed here until ``dm0g.4.4.1``
freezes them.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from legalforecast.multiharness.auth_profiles import (
    AuthProfileError,
    ResolvedAuthProfile,
    require_auth_profile_id,
    resolve_auth_profile,
)
from legalforecast.multiharness.local_cli_environment import (
    CredentialSource,
    build_local_cli_environment,
    project_profile_credentials,
)
from legalforecast.multiharness.process_containment import (
    ProcessContainmentError,
    ProcessContainmentHandle,
    cleanup_process_containment,
    establish_process_containment,
    launch_failure_evidence,
    prepare_contained_command,
)
from legalforecast.multiharness.spec import POSIX_PROCESS_GROUP_CONTAINMENT
from legalforecast.multiharness.validation import (
    validate_env_var_names,
    validate_no_secret_values,
    validate_public_record,
)

LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.local_cli_adapter_manifest.v1"
)
LOCAL_CLI_EXECUTION_SCHEMA_VERSION = "legalforecast.multiharness.local_cli_execution.v1"
_PUBLICATION_ENVELOPE_IMPORTS = frozenset(
    {
        "legalforecast.contracts",
        "legalforecast.multiharness.community",
        "legalforecast.ingestion",
        "legalforecast.labeling",
        "legalforecast.cli",
    }
)
_MAX_CAPTURE_BYTES = 1_048_576
_TRUNCATION_MARKER = b"\n[truncated]\n"
_DEFAULT_GRACE_SECONDS = 1.0


class LocalCliRuntimeError(RuntimeError):
    """Raised when the shared local CLI execution service cannot run a spec."""


@dataclass(frozen=True, slots=True)
class LocalCliAdapterManifest:
    """Stub manifest until B1 freezes generic local-CLI adapter fields."""

    adapter_id: str
    display_name: str
    adapter_version: str
    command: tuple[str, ...]
    supported_auth_profiles: tuple[str, ...]
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not self.adapter_id.strip():
            raise LocalCliRuntimeError("adapter_id must not be empty")
        if not self.display_name.strip():
            raise LocalCliRuntimeError("display_name must not be empty")
        if not self.adapter_version.strip():
            raise LocalCliRuntimeError("adapter_version must not be empty")
        if not self.command:
            raise LocalCliRuntimeError("command must not be empty")
        for index, value in enumerate(self.command):
            if not value.strip():
                raise LocalCliRuntimeError(f"command[{index}] must not be empty")
        if not self.supported_auth_profiles:
            raise LocalCliRuntimeError("supported_auth_profiles must not be empty")
        seen: set[str] = set()
        for profile_id, env_names in self.profile_env_vars:
            canonical = require_auth_profile_id(profile_id)
            if canonical in seen:
                raise LocalCliRuntimeError(
                    "profile_env_vars contains duplicate profiles"
                )
            seen.add(canonical)
            validate_env_var_names(env_names, "profile_env_vars")

    def env_vars_for_profile(self, profile_id: str) -> tuple[str, ...]:
        """Return projected environment names declared for one profile."""

        canonical = require_auth_profile_id(profile_id)
        for declared_id, env_names in self.profile_env_vars:
            if declared_id == canonical:
                return env_names
        return ()

    def identity_record(self) -> dict[str, object]:
        """Return non-secret manifest identity used in spec hashes."""

        return {
            "schema_version": LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "command": list(self.command),
            "supported_auth_profiles": list(self.supported_auth_profiles),
            "profile_env_vars": [
                {"auth_profile": profile_id, "env_vars": list(env_names)}
                for profile_id, env_names in self.profile_env_vars
            ],
        }


@dataclass(frozen=True, slots=True)
class LocalCliRunSpec:
    """Requested local CLI execution independent of publication envelopes."""

    spec_id: str
    manifest: LocalCliAdapterManifest
    auth_profile: str
    extra_args: tuple[str, ...] = ()
    timeout_seconds: float = 30
    infisical_env: str = "dev"
    stdin_bytes: bytes = b""
    resume_of_spec_sha256: str | None = None
    host_process_containment: str = POSIX_PROCESS_GROUP_CONTAINMENT

    def argv(self) -> tuple[str, ...]:
        """Return the exact argv the service will launch."""

        return (*self.manifest.command, *self.extra_args)

    def resolved_profile(self) -> ResolvedAuthProfile:
        """Bind the declared profile to this manifest's projection names."""

        return resolve_auth_profile(
            self.auth_profile,
            supported_profiles=self.manifest.supported_auth_profiles,
            projected_env_vars=self.manifest.env_vars_for_profile(self.auth_profile),
            infisical_env=self.infisical_env,
        )

    def spec_sha256(self) -> str:
        """Return a reproducible identity over non-secret request bytes."""

        record = {
            "spec_id": self.spec_id,
            "manifest": self.manifest.identity_record(),
            "auth_profile": require_auth_profile_id(self.auth_profile),
            "extra_args": list(self.extra_args),
            "timeout_seconds": self.timeout_seconds,
            "infisical_env": self.infisical_env,
            "stdin_sha256": _sha256_bytes(self.stdin_bytes),
            "host_process_containment": self.host_process_containment,
        }
        return _sha256_record(record)


@dataclass(frozen=True, slots=True)
class LocalCliExecutionResult:
    """Structured result of one local CLI invocation."""

    spec_id: str
    spec_sha256: str
    auth_profile: str
    status: str
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    cwd: str
    duration_ms: int
    cost_usd: float | None
    containment_establishment: str

    def to_public_record(self) -> dict[str, object]:
        """Return the secret-free public receipt."""

        record: dict[str, object] = {
            "schema_version": LOCAL_CLI_EXECUTION_SCHEMA_VERSION,
            "spec_id": self.spec_id,
            "spec_sha256": self.spec_sha256,
            "auth_profile": self.auth_profile,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "cost_usd": self.cost_usd,
            "containment_establishment": self.containment_establishment,
        }
        validate_public_record(record, "local CLI execution receipt")
        return record


class ExecutionScheduler(Protocol):
    """Hook replaced by ``dm0g.4.2.10``; this runtime does not schedule."""

    def before_execute(self, spec: LocalCliRunSpec) -> None:
        """Acquire any future concurrency/cap slot."""

    def after_execute(
        self,
        spec: LocalCliRunSpec,
        result: LocalCliExecutionResult,
    ) -> None:
        """Release any future concurrency/cap slot."""


class NullScheduler:
    """No-op scheduler. Sequencing semantics are intentionally unimplemented."""

    def before_execute(self, spec: LocalCliRunSpec) -> None:
        del spec

    def after_execute(
        self,
        spec: LocalCliRunSpec,
        result: LocalCliExecutionResult,
    ) -> None:
        del spec, result


def execute_local_cli(
    spec: LocalCliRunSpec,
    scratch_root: Path,
    *,
    credential_source: CredentialSource | None = None,
    scheduler: ExecutionScheduler | None = None,
    parent_env: Mapping[str, str] | None = None,
    termination_grace_seconds: float = _DEFAULT_GRACE_SECONDS,
    max_capture_bytes: int = _MAX_CAPTURE_BYTES,
) -> LocalCliExecutionResult:
    """Run one CLI under the declared profile's sanitized environment."""

    _reject_publication_envelope_imports()
    if spec.timeout_seconds <= 0:
        raise LocalCliRuntimeError("timeout_seconds must be positive")
    if max_capture_bytes <= 0:
        raise LocalCliRuntimeError("max_capture_bytes must be positive")
    try:
        spec_sha256 = spec.spec_sha256()
        if (
            spec.resume_of_spec_sha256 is not None
            and spec.resume_of_spec_sha256 != spec_sha256
        ):
            raise LocalCliRuntimeError("resume token does not match this run spec")
        profile = spec.resolved_profile()
    except AuthProfileError as exc:
        raise LocalCliRuntimeError(str(exc)) from exc
    parent = os.environ if parent_env is None else parent_env
    try:
        projected = project_profile_credentials(
            profile,
            credential_source=credential_source,
            parent_env=parent,
        )
        environment = build_local_cli_environment(
            profile,
            scratch_root,
            projected_credentials=projected,
            parent_env=parent,
        )
    except AuthProfileError as exc:
        raise LocalCliRuntimeError(str(exc)) from exc
    active_scheduler = scheduler if scheduler is not None else NullScheduler()
    active_scheduler.before_execute(spec)
    result: LocalCliExecutionResult | None = None
    try:
        result = _run_contained_cli(
            spec,
            spec_sha256=spec_sha256,
            profile=profile,
            environment=environment,
            scratch_root=scratch_root,
            projected_values=tuple(projected.values()),
            termination_grace_seconds=termination_grace_seconds,
            max_capture_bytes=max_capture_bytes,
        )
        return result
    finally:
        active_scheduler.after_execute(
            spec,
            result
            or LocalCliExecutionResult(
                spec_id=spec.spec_id,
                spec_sha256=spec_sha256,
                auth_profile=profile.profile_id,
                status="scheduler_release",
                exit_code=None,
                stdout=b"",
                stderr=b"",
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                cwd=str(scratch_root),
                duration_ms=0,
                cost_usd=None,
                containment_establishment="not_started",
            ),
        )


def _run_contained_cli(
    spec: LocalCliRunSpec,
    *,
    spec_sha256: str,
    profile: ResolvedAuthProfile,
    environment: Mapping[str, str],
    scratch_root: Path,
    projected_values: Sequence[str],
    termination_grace_seconds: float,
    max_capture_bytes: int,
) -> LocalCliExecutionResult:
    scratch_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    argv = spec.argv()
    requested = spec.host_process_containment
    status = "launch_failed"
    exit_code: int | None = None
    timed_out = False
    stdout = b""
    stderr = b""
    stdout_truncated = False
    stderr_truncated = False
    establishment = "failed"
    process: subprocess.Popen[bytes] | None = None
    handle: ProcessContainmentHandle | None = None
    started = time.monotonic()
    try:
        prepared = prepare_contained_command(
            requested,
            argv,
            private_logs=scratch_root,
            runtime_max_seconds=spec.timeout_seconds
            + (2 * termination_grace_seconds)
            + 5,
        )
        with (
            tempfile.TemporaryFile(mode="w+b", dir=scratch_root) as stdout_handle,
            tempfile.TemporaryFile(mode="w+b", dir=scratch_root) as stderr_handle,
        ):
            stdin_file = None
            stdin_handle: object = subprocess.DEVNULL
            if spec.stdin_bytes:
                stdin_file = tempfile.TemporaryFile(mode="w+b", dir=scratch_root)
                stdin_file.write(spec.stdin_bytes)
                stdin_file.seek(0)
                stdin_handle = stdin_file
            try:
                process = subprocess.Popen(
                    prepared.argv,
                    stdin=stdin_handle,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    cwd=scratch_root,
                    env=dict(environment),
                    start_new_session=True,
                )
                handle = ProcessContainmentHandle(
                    requested=requested,
                    unit_name=prepared.unit_name,
                )
                handle = establish_process_containment(prepared, process, handle)
                establishment = "established"
                try:
                    exit_code = process.wait(timeout=spec.timeout_seconds)
                    status = "completed" if exit_code == 0 else "nonzero"
                except subprocess.TimeoutExpired:
                    timed_out = True
                    status = "timed_out"
            finally:
                if stdin_file is not None:
                    stdin_file.close()
                if handle is not None and process is not None:
                    evidence = cleanup_process_containment(
                        handle,
                        process,
                        termination_grace_seconds,
                    )
                    establishment = evidence.establishment
                    if process.returncode is not None:
                        exit_code = process.returncode
                stdout, stdout_truncated = _bounded_capture(
                    stdout_handle,
                    max_capture_bytes,
                )
                stderr, stderr_truncated = _bounded_capture(
                    stderr_handle,
                    max_capture_bytes,
                )
    except ProcessContainmentError as exc:
        raise LocalCliRuntimeError(
            f"required host process containment was unavailable: {exc}"
        ) from exc
    except OSError as exc:
        if handle is None:
            launch_failure_evidence(requested)
        raise LocalCliRuntimeError(
            "local CLI executable could not be launched"
        ) from exc

    result = LocalCliExecutionResult(
        spec_id=spec.spec_id,
        spec_sha256=spec_sha256,
        auth_profile=profile.profile_id,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        timed_out=timed_out,
        cwd=str(scratch_root.resolve()),
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        cost_usd=_optional_cost_usd(stdout),
        containment_establishment=establishment,
    )
    validate_no_secret_values(
        result.to_public_record(),
        projected_values,
        "local CLI execution receipt",
    )
    return result


def _bounded_capture(handle: BinaryIO, max_bytes: int) -> tuple[bytes, bool]:
    stream = handle
    stream.flush()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    raw = stream.read(max_bytes)
    truncated = size > max_bytes
    if truncated:
        marker = _TRUNCATION_MARKER[:max_bytes]
        raw = raw[: max(0, max_bytes - len(marker))] + marker
    return raw, truncated


def _optional_cost_usd(stdout: bytes) -> float | None:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped.startswith(b"{"):
            continue
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(decoded, dict):
            continue
        payload = cast(dict[object, object], decoded)
        value = payload.get("total_cost_usd")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value < 0:
            continue
        return float(value)
    return None


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _sha256_record(record: Mapping[str, object]) -> str:
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _reject_publication_envelope_imports() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    blocked = sorted(
        name
        for name in imported
        if name in _PUBLICATION_ENVELOPE_IMPORTS
        or any(
            name.startswith(f"{prefix}.") for prefix in _PUBLICATION_ENVELOPE_IMPORTS
        )
    )
    if blocked:
        raise LocalCliRuntimeError(
            "local CLI runtime must not import publication envelopes"
        )

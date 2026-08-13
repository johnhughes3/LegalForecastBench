"""Shared local-CLI execution types for Claude and Codex adapters.

Bead ``LegalForecastBench-dm0g.4.4.26`` owns this module as the single
source for ``RunSpec``, ``ExecutionReceipt``, ``LocalCliFailureClass``
(including ``sandbox_denial``), fixture transcripts, and the in-process
fake service. Bead ``LegalForecastBench-dm0g.4.1.4`` owns the durable
schema freeze plus the harness-independent identity keys in
``legalforecast.multiharness.identity``. Do not treat these dataclasses as
authenticated byte contracts. Bead ``LegalForecastBench-dm0g.4.2.7`` owns
the contained runtime that adapters rebind to.

Adapter cores must not spawn processes. They call
``LocalCliExecutionService.execute``. Neither adapter may land a parallel
contracts module, a second RunSpec/ExecutionReceipt family, or a private
failure-class tuple.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self, cast

from legalforecast.multiharness.identity import (
    RunIdentity,
    SolverIdentity,
    TaskIdentity,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    optional_mapping,
    optional_str,
    require_known_fields,
    require_schema_version,
    require_str,
    validate_env_var_names,
    validate_public_record,
    validate_sha256,
)

LOCAL_CLI_RUN_SPEC_SCHEMA_VERSION = (
    # contract-ratchet: allow draft local-cli run spec until 4.1.4
    "legalforecast.multiharness.local_cli_run_spec.v1"
)
LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION = (
    # contract-ratchet: allow draft local-cli receipt until 4.1.4
    "legalforecast.multiharness.local_cli_execution_receipt.v1"
)
LOCAL_CLI_OUTPUT_FORMAT_JSON = "json"
LOCAL_CLI_RECEIPT_STATUSES = frozenset({"succeeded", "failed", "timeout"})
_RUN_SPEC_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "spec_id",
        "argv",
        "working_directory",
        "environment",
        "timeout_seconds",
        "output_format",
        "spec_sha256",
    }
)
_RUN_SPEC_OPTIONAL_FIELDS = frozenset({"json_schema", "max_budget_usd", "stdin_sha256"})
_PUBLIC_RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "receipt_id",
        "spec_sha256",
        "status",
        "returncode",
        "executable_name",
        "stdout_sha256",
        "stderr_sha256",
        "duration_ms",
        "usage",
    }
)
_PUBLIC_RECEIPT_OPTIONAL_FIELDS = frozenset(
    {
        "served_model",
        "executable_version",
        "cost_usd",
        "runtime_policy_sha256",
        "deliverable_manifest_sha256",
        "failure_class",
        "task_identity_key",
        "solver_identity_key",
        "run_identity_key",
    }
)
_FULL_RECEIPT_REQUIRED_FIELDS = _PUBLIC_RECEIPT_REQUIRED_FIELDS | frozenset(
    {"stdout", "stderr"}
)
CREDENTIAL_ENV_VAR_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
        "OPENAI_ADMIN_KEY",
    }
)


class LocalCliFailureClass(StrEnum):
    """Fail-closed classification for one local CLI execution.

    Unknown class names coerce to ``schema_violation``. Both adapters must
    import this enum; do not keep a parallel string tuple.
    """

    TIMEOUT = "timeout"
    REFUSAL = "refusal"
    SCHEMA_VIOLATION = "schema_violation"
    CRASH = "crash"
    SANDBOX_DENIAL = "sandbox_denial"


LOCAL_CLI_FAILURE_CLASSES = tuple(item.value for item in LocalCliFailureClass)
LOCAL_CLI_SANDBOX_DENIAL_MARKERS = (
    "sandbox denied",
    "sandbox denial",
    "landlock",
    "seccomp",
)


def declared_local_cli_failure_classes() -> tuple[str, ...]:
    """Return the closed failure taxonomy both adapters must classify."""

    return LOCAL_CLI_FAILURE_CLASSES


def coerce_local_cli_failure_class(value: str) -> LocalCliFailureClass:
    """Map an unknown class to schema_violation instead of succeeding."""

    try:
        return LocalCliFailureClass(value)
    except ValueError:
        return LocalCliFailureClass.SCHEMA_VIOLATION


def is_local_cli_sandbox_denial(text: str) -> bool:
    """Return whether error text names a sandbox denial.

    Callers must pass error-path text only. Successful payloads that mention
    landlocked parcels or seccomp-style discovery stay successes.
    """

    folded = text.casefold()
    return any(marker in folded for marker in LOCAL_CLI_SANDBOX_DENIAL_MARKERS)


class LocalCliContractError(ValueError):
    """A local CLI contract record was invalid or mixed in credentials."""


@dataclass(frozen=True, slots=True)
class RunSpec:
    """4.1.4 draft: requested local CLI configuration, never a shell string."""

    spec_id: str
    argv: tuple[str, ...]
    working_directory: Path
    environment: Mapping[str, str] = field(default_factory=lambda: {})
    timeout_seconds: float = 120.0
    output_format: str = LOCAL_CLI_OUTPUT_FORMAT_JSON
    json_schema: Mapping[str, object] | None = None
    max_budget_usd: float | None = None
    stdin_bytes: bytes = b""
    stdin_sha256: str = ""
    spec_sha256: str = ""
    schema_version: str = LOCAL_CLI_RUN_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_non_empty(self.spec_id, "spec_id")
        if not self.argv:
            raise LocalCliContractError("argv must not be empty")
        _require_executable_name(self.argv[0])
        if any(token in {"sh", "bash"} for token in self.argv):
            raise LocalCliContractError("argv must not invoke a shell")
        if self.timeout_seconds <= 0:
            raise LocalCliContractError("timeout_seconds must be positive")
        if self.output_format != LOCAL_CLI_OUTPUT_FORMAT_JSON:
            raise LocalCliContractError("RunSpec output_format must be json")
        if self.max_budget_usd is not None and self.max_budget_usd < 0:
            raise LocalCliContractError("max_budget_usd must be non-negative")
        if type(self.stdin_bytes) is not bytes:
            raise LocalCliContractError("stdin_bytes must be bytes")
        expected_stdin = _sha256_bytes(self.stdin_bytes) if self.stdin_bytes else ""
        if self.stdin_sha256:
            _require_prefixed_digest(self.stdin_sha256, "stdin_sha256")
            if expected_stdin and self.stdin_sha256 != expected_stdin:
                raise LocalCliContractError("stdin_sha256 does not match stdin_bytes")
        else:
            object.__setattr__(self, "stdin_sha256", expected_stdin)
        env_names = tuple(self.environment)
        validate_env_var_names(env_names, "environment")
        forbidden = CREDENTIAL_ENV_VAR_NAMES.intersection(env_names)
        if forbidden:
            raise LocalCliContractError(
                "RunSpec environment must not contain credential variables"
            )
        for name, value in self.environment.items():
            if not value:
                raise LocalCliContractError(
                    f"environment[{name}] must be a non-empty string"
                )
        if self.schema_version != LOCAL_CLI_RUN_SPEC_SCHEMA_VERSION:
            raise LocalCliContractError(
                f"schema_version must be {LOCAL_CLI_RUN_SPEC_SCHEMA_VERSION!r}"
            )
        expected = _record_sha256(self._hash_payload())
        if self.spec_sha256:
            validate_sha256(self.spec_sha256, "spec_sha256")
            if self.spec_sha256 != expected:
                raise LocalCliContractError("spec_sha256 does not match argv identity")
        else:
            object.__setattr__(self, "spec_sha256", expected)

    def _hash_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "argv": list(self.argv),
            "environment": dict(sorted(self.environment.items())),
            "output_format": self.output_format,
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "timeout_seconds": self.timeout_seconds,
            "working_directory": self.working_directory.as_posix(),
        }
        if self.json_schema is not None:
            payload["json_schema"] = dict(self.json_schema)
        if self.max_budget_usd is not None:
            payload["max_budget_usd"] = self.max_budget_usd
        if self.stdin_sha256:
            payload["stdin_sha256"] = self.stdin_sha256
        return payload

    def to_record(self) -> dict[str, object]:
        record = self._hash_payload()
        record["spec_sha256"] = self.spec_sha256
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        """Round-trip a RunSpec from its canonical record."""

        try:
            _closed_record(
                record,
                required=_RUN_SPEC_REQUIRED_FIELDS,
                optional=_RUN_SPEC_OPTIONAL_FIELDS,
                field_name="run_spec",
            )
            require_schema_version(record, LOCAL_CLI_RUN_SPEC_SCHEMA_VERSION)
            argv = record["argv"]
            if not isinstance(argv, list) or not argv:
                raise LocalCliContractError("argv must be a non-empty array")
            argv_tokens: list[str] = []
            for item in cast(list[object], argv):
                if not isinstance(item, str) or not item:
                    raise LocalCliContractError("argv must contain non-empty strings")
                argv_tokens.append(item)
            environment = _require_str_str_mapping(record, "environment")
            timeout = record["timeout_seconds"]
            if not isinstance(timeout, int | float) or isinstance(timeout, bool):
                raise LocalCliContractError("timeout_seconds must be a positive number")
            json_schema = optional_mapping(record, "json_schema")
            max_budget = record.get("max_budget_usd")
            if max_budget is not None and (
                not isinstance(max_budget, int | float) or isinstance(max_budget, bool)
            ):
                raise LocalCliContractError("max_budget_usd must be a number")
            return cls(
                spec_id=require_str(record, "spec_id"),
                argv=tuple(argv_tokens),
                working_directory=Path(require_str(record, "working_directory")),
                environment=environment,
                timeout_seconds=timeout,
                output_format=require_str(record, "output_format"),
                json_schema=None if json_schema is None else dict(json_schema),
                max_budget_usd=max_budget,
                stdin_sha256=optional_str(record, "stdin_sha256") or "",
                spec_sha256=require_str(record, "spec_sha256"),
                schema_version=require_str(record, "schema_version"),
            )
        except MultiHarnessValidationError as exc:
            raise LocalCliContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """Actual local CLI execution bound to a RunSpec and optional identity keys."""

    receipt_id: str
    spec_sha256: str
    status: str
    returncode: int | None
    executable_name: str
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str
    duration_ms: int = 0
    served_model: str | None = None
    executable_version: str | None = None
    usage: Mapping[str, int] = field(default_factory=lambda: {})
    cost_usd: float | None = None
    runtime_policy_sha256: str | None = None
    deliverable_manifest_sha256: str | None = None
    failure_class: str | None = None
    task_identity_key: str | None = None
    solver_identity_key: str | None = None
    run_identity_key: str | None = None
    schema_version: str = LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_non_empty(self.receipt_id, "receipt_id")
        validate_sha256(self.spec_sha256, "spec_sha256")
        if self.status not in LOCAL_CLI_RECEIPT_STATUSES:
            raise LocalCliContractError("status is not a local CLI receipt status")
        _require_executable_name(self.executable_name)
        if self.returncode is not None and (
            type(self.returncode) is not int or self.returncode < 0
        ):
            raise LocalCliContractError("returncode must be a non-negative integer")
        if type(self.duration_ms) is not int or self.duration_ms < 0:
            raise LocalCliContractError("duration_ms must be a non-negative integer")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise LocalCliContractError("cost_usd must be non-negative")
        if self.failure_class is not None:
            object.__setattr__(
                self,
                "failure_class",
                coerce_local_cli_failure_class(self.failure_class).value,
            )
        if self.status == "succeeded" and self.failure_class is not None:
            raise LocalCliContractError("successful receipts cannot set failure_class")
        expected_stdout = _sha256_text(self.stdout)
        expected_stderr = _sha256_text(self.stderr)
        validate_sha256(self.stdout_sha256, "stdout_sha256")
        validate_sha256(self.stderr_sha256, "stderr_sha256")
        if self.stdout_sha256 != expected_stdout:
            raise LocalCliContractError("stdout_sha256 does not match stdout")
        if self.stderr_sha256 != expected_stderr:
            raise LocalCliContractError("stderr_sha256 does not match stderr")
        for key, value in self.usage.items():
            _require_non_empty(key, "usage key")
            if type(value) is not int or value < 0:
                raise LocalCliContractError(f"usage[{key}] must be a non-negative int")
        for field_name in (
            "runtime_policy_sha256",
            "deliverable_manifest_sha256",
        ):
            digest = getattr(self, field_name)
            if digest is not None:
                validate_sha256(digest, field_name)
        _require_identity_keys(
            self.task_identity_key,
            self.solver_identity_key,
            self.run_identity_key,
        )
        if self.schema_version != LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION:
            raise LocalCliContractError(
                f"schema_version must be {LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION!r}"
            )
        validate_public_record(self.to_public_record(), "execution_receipt")

    def to_public_record(self) -> dict[str, object]:
        """Return the credential-free, transcript-free public receipt."""

        record: dict[str, object] = {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "spec_sha256": self.spec_sha256,
            "status": self.status,
            "returncode": self.returncode,
            "executable_name": self.executable_name,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "duration_ms": self.duration_ms,
            "usage": dict(sorted(self.usage.items())),
        }
        if self.served_model is not None:
            record["served_model"] = self.served_model
        if self.executable_version is not None:
            record["executable_version"] = self.executable_version
        if self.cost_usd is not None:
            record["cost_usd"] = self.cost_usd
        if self.runtime_policy_sha256 is not None:
            record["runtime_policy_sha256"] = self.runtime_policy_sha256
        if self.deliverable_manifest_sha256 is not None:
            record["deliverable_manifest_sha256"] = self.deliverable_manifest_sha256
        if self.failure_class is not None:
            record["failure_class"] = self.failure_class
        if self.task_identity_key is not None:
            record["task_identity_key"] = self.task_identity_key
        if self.solver_identity_key is not None:
            record["solver_identity_key"] = self.solver_identity_key
        if self.run_identity_key is not None:
            record["run_identity_key"] = self.run_identity_key
        return record

    def to_record(self) -> dict[str, object]:
        """Return the full receipt, including transcript text for round-trip."""

        record = self.to_public_record()
        record["stdout"] = self.stdout
        record["stderr"] = self.stderr
        return record

    def with_identity_keys(
        self,
        *,
        task: TaskIdentity,
        solver: SolverIdentity,
        run: RunIdentity,
    ) -> Self:
        """Return a copy bound to harness-independent identity keys."""

        if run.task_identity_key != task.key or run.solver_identity_key != solver.key:
            raise LocalCliContractError(
                "run identity does not bind the supplied task and solver keys"
            )
        return replace(
            self,
            task_identity_key=task.key,
            solver_identity_key=solver.key,
            run_identity_key=run.key,
        )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        """Round-trip a full execution receipt, including transcript bytes."""

        try:
            _closed_record(
                record,
                required=_FULL_RECEIPT_REQUIRED_FIELDS,
                optional=_PUBLIC_RECEIPT_OPTIONAL_FIELDS,
                field_name="execution_receipt",
            )
            require_schema_version(record, LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION)
            usage = _require_usage(record)
            returncode = record["returncode"]
            if returncode is not None and type(returncode) is not int:
                raise LocalCliContractError("returncode must be a non-negative integer")
            duration = record["duration_ms"]
            if type(duration) is not int:
                raise LocalCliContractError(
                    "duration_ms must be a non-negative integer"
                )
            return cls(
                receipt_id=require_str(record, "receipt_id"),
                spec_sha256=require_str(record, "spec_sha256"),
                status=require_str(record, "status"),
                returncode=returncode,
                executable_name=require_str(record, "executable_name"),
                stdout=_require_text(record, "stdout"),
                stderr=_require_text(record, "stderr"),
                stdout_sha256=require_str(record, "stdout_sha256"),
                stderr_sha256=require_str(record, "stderr_sha256"),
                duration_ms=duration,
                served_model=optional_str(record, "served_model"),
                executable_version=optional_str(record, "executable_version"),
                usage=usage,
                cost_usd=_optional_float(record, "cost_usd"),
                runtime_policy_sha256=optional_str(record, "runtime_policy_sha256"),
                deliverable_manifest_sha256=optional_str(
                    record, "deliverable_manifest_sha256"
                ),
                failure_class=optional_str(record, "failure_class"),
                task_identity_key=optional_str(record, "task_identity_key"),
                solver_identity_key=optional_str(record, "solver_identity_key"),
                run_identity_key=optional_str(record, "run_identity_key"),
                schema_version=require_str(record, "schema_version"),
            )
        except MultiHarnessValidationError as exc:
            raise LocalCliContractError(str(exc)) from exc

    @classmethod
    def from_transcript(
        cls,
        spec: RunSpec,
        *,
        stdout: str,
        stderr: str = "",
        returncode: int | None = 0,
        status: str = "succeeded",
        duration_ms: int = 0,
        served_model: str | None = None,
        executable_version: str | None = None,
        usage: Mapping[str, int] | None = None,
        cost_usd: float | None = None,
        failure_class: str | None = None,
        deliverable_manifest_sha256: str | None = None,
    ) -> Self:
        """Bind a fixture or service transcript to the requested RunSpec."""

        return cls(
            receipt_id=f"{spec.spec_id}:receipt",
            spec_sha256=spec.spec_sha256,
            status=status,
            returncode=returncode,
            executable_name=spec.argv[0],
            stdout=stdout,
            stderr=stderr,
            stdout_sha256=_sha256_text(stdout),
            stderr_sha256=_sha256_text(stderr),
            duration_ms=duration_ms,
            served_model=served_model,
            executable_version=executable_version,
            usage=dict(usage or {}),
            cost_usd=cost_usd,
            failure_class=failure_class,
            deliverable_manifest_sha256=deliverable_manifest_sha256,
        )


class LocalCliExecutionService(Protocol):
    """B2 execute seam. Concrete type lives in ``local_cli_runtime``.

    Tests inject ``FakeLocalCliExecutionService``. Production rebind is
    ``LegalForecastBench-dm0g.4.4.19`` / ``.4.4.30``.
    """

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        """Run one local CLI spec and return a bound execution receipt."""
        ...


@dataclass(frozen=True, slots=True)
class FixtureTranscript:
    """Offline execution fixture used by tests in place of a live process."""

    stdout: str
    stderr: str = ""
    returncode: int | None = 0
    status: str = "succeeded"
    duration_ms: int = 0
    served_model: str | None = None
    executable_version: str | None = None
    usage: Mapping[str, int] = field(default_factory=lambda: {})
    cost_usd: float | None = None
    failure_class: str | None = None


@dataclass(frozen=True, slots=True)
class FakeLocalCliExecutionService:
    """In-process B2 stand-in. Never starts a process."""

    transcript: FixtureTranscript

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        transcript = self.transcript
        return ExecutionReceipt.from_transcript(
            spec,
            stdout=transcript.stdout,
            stderr=transcript.stderr,
            returncode=transcript.returncode,
            status=transcript.status,
            duration_ms=transcript.duration_ms,
            served_model=transcript.served_model,
            executable_version=transcript.executable_version,
            usage=transcript.usage,
            cost_usd=transcript.cost_usd,
            failure_class=transcript.failure_class,
        )


def validate_public_execution_receipt(record: Mapping[str, Any]) -> None:
    """Validate a public receipt fixture and name any missing required field."""

    try:
        _closed_record(
            record,
            required=_PUBLIC_RECEIPT_REQUIRED_FIELDS,
            optional=_PUBLIC_RECEIPT_OPTIONAL_FIELDS,
            field_name="execution_receipt",
        )
        require_schema_version(record, LOCAL_CLI_EXECUTION_RECEIPT_SCHEMA_VERSION)
        require_str(record, "receipt_id")
        require_str(record, "spec_sha256")
        require_str(record, "status")
        require_str(record, "executable_name")
        require_str(record, "stdout_sha256")
        require_str(record, "stderr_sha256")
        _require_identity_keys(
            record.get("task_identity_key"),
            record.get("solver_identity_key"),
            record.get("run_identity_key"),
        )
        validate_public_record(record, "execution_receipt")
    except MultiHarnessValidationError as exc:
        raise LocalCliContractError(str(exc)) from exc


def _require_identity_keys(
    task_identity_key: object,
    solver_identity_key: object,
    run_identity_key: object,
) -> None:
    keys = (task_identity_key, solver_identity_key, run_identity_key)
    if any(key is None for key in keys) and any(key is not None for key in keys):
        raise LocalCliContractError(
            "task_identity_key, solver_identity_key, and run_identity_key "
            "must be set together"
        )
    for field_name, value in zip(
        ("task_identity_key", "solver_identity_key", "run_identity_key"),
        keys,
        strict=True,
    ):
        if value is None:
            continue
        if not isinstance(value, str):
            raise LocalCliContractError(f"{field_name} must be a string")
        _require_prefixed_digest(value, field_name)


def _require_prefixed_digest(value: str, field_name: str) -> None:
    try:
        validate_sha256(value, field_name, allow_prefix=True)
    except MultiHarnessValidationError as exc:
        raise LocalCliContractError(str(exc)) from exc
    if not value.startswith("sha256:"):
        raise LocalCliContractError(f"{field_name} must use the sha256: prefix")


def _require_text(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if type(value) is not str:
        raise LocalCliContractError(f"{field_name} must be a string")
    return value


def _require_str_str_mapping(
    record: Mapping[str, Any], field_name: str
) -> dict[str, str]:
    raw = record.get(field_name)
    if not isinstance(raw, Mapping):
        raise LocalCliContractError(f"{field_name} must be an object")
    values: dict[str, str] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if type(key) is not str or type(value) is not str:
            raise LocalCliContractError(f"{field_name} keys and values must be strings")
        values[key] = value
    return values


def _require_usage(record: Mapping[str, Any]) -> dict[str, int]:
    raw = record.get("usage")
    if not isinstance(raw, Mapping):
        raise LocalCliContractError("usage must be an object")
    usage: dict[str, int] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if type(key) is not str or not key.strip():
            raise LocalCliContractError("usage key must be a non-empty string")
        if type(value) is not int or value < 0:
            raise LocalCliContractError(f"usage[{key}] must be a non-negative int")
        usage[key] = value
    return usage


def _closed_record(
    record: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str],
    field_name: str,
) -> None:
    try:
        require_known_fields(
            record,
            required=required,
            optional=optional,
            field_name=field_name,
        )
    except MultiHarnessValidationError as exc:
        raise LocalCliContractError(str(exc)) from exc


def _optional_float(record: Mapping[str, Any], field_name: str) -> float | None:
    value = record.get(field_name)
    if value is None:
        return None
    if type(value) not in {int, float} or isinstance(value, bool):
        raise LocalCliContractError(f"{field_name} must be a number")
    return float(value)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise LocalCliContractError(f"{field_name} must be a non-empty string")


def _require_executable_name(value: str) -> None:
    _require_non_empty(value, "executable_name")
    if "/" in value or "\\" in value or value in {".", ".."}:
        raise LocalCliContractError(
            "executable_name must be a basename, not a filesystem path"
        )


# contract-ratchet: allow non-persisted local-cli stdin digest
def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


# contract-ratchet: allow non-persisted local-cli stdout digest
def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


# contract-ratchet: allow non-persisted local-cli spec digest
def _record_sha256(record: Mapping[str, object]) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

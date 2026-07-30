"""Live host-owned container tool sessions and resumable receipts."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Protocol, Self, cast

from legalforecast.multiharness.adapters import ToolExecutor
from legalforecast.multiharness.host_environment import (
    HostEnvironmentError,
    build_container_backend_environment,
    require_local_pinned_container_image,
    require_rootless_container_daemon,
)
from legalforecast.multiharness.sandbox import (
    LIVE_SESSION_LABEL,
    build_live_container_plan,
    resolve_container_backend,
    validate_container_backend_path,
    validate_live_container_policy,
)
from legalforecast.multiharness.spec import RunRequest, RunResult, SandboxPolicy
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolRequest,
    ToolResponse,
    decode_tool_response,
    encode_tool_message,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError

CONTAINER_RECEIPT_SCHEMA_VERSION = "legalforecast.multiharness.container_receipt.v1"
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "backend",
        "image",
        "policy_sha256",
        "request_id",
        "request_sha256",
        "input_sha256",
        "result_id",
        "result_sha256",
        "result_record_sha256",
        "exchange_count",
        "successful_exchange_count",
        "transcript_sha256",
        "container_exit_code",
        "cleanup_confirmed",
        "receipt_sha256",
    }
)


class ContainerRuntimeError(RuntimeError):
    """A live tool container violated its execution or receipt contract."""


class _Process(Protocol):
    @property
    def stdin(self) -> IO[bytes] | None: ...

    @property
    def stdout(self) -> IO[bytes] | None: ...

    @property
    def stderr(self) -> IO[bytes] | None: ...

    @property
    def returncode(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ContainerExecutionReceipt:
    """Sanitized commitment to one successful, fully cleaned tool session."""

    backend: str
    image: str
    policy_sha256: str
    request_id: str
    request_sha256: str
    input_sha256: str
    result_id: str
    result_sha256: str
    result_record_sha256: str
    exchange_count: int
    successful_exchange_count: int
    transcript_sha256: str
    container_exit_code: int
    cleanup_confirmed: bool
    receipt_sha256: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": CONTAINER_RECEIPT_SCHEMA_VERSION,
            "backend": self.backend,
            "image": self.image,
            "policy_sha256": self.policy_sha256,
            "request_id": self.request_id,
            "request_sha256": self.request_sha256,
            "input_sha256": self.input_sha256,
            "result_id": self.result_id,
            "result_sha256": self.result_sha256,
            "result_record_sha256": self.result_record_sha256,
            "exchange_count": self.exchange_count,
            "successful_exchange_count": self.successful_exchange_count,
            "transcript_sha256": self.transcript_sha256,
            "container_exit_code": self.container_exit_code,
            "cleanup_confirmed": self.cleanup_confirmed,
            "receipt_sha256": self.receipt_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        if frozenset(record) != _RECEIPT_FIELDS:
            raise ContainerRuntimeError("container receipt has unexpected fields")
        if record.get("schema_version") != CONTAINER_RECEIPT_SCHEMA_VERSION:
            raise ContainerRuntimeError("unsupported container receipt schema")
        receipt = cls(
            backend=_required_str(record, "backend"),
            image=_required_str(record, "image"),
            policy_sha256=_required_digest(record, "policy_sha256"),
            request_id=_required_str(record, "request_id"),
            request_sha256=_required_digest(record, "request_sha256"),
            input_sha256=_required_digest(record, "input_sha256"),
            result_id=_required_str(record, "result_id"),
            result_sha256=_required_digest(record, "result_sha256"),
            result_record_sha256=_required_digest(record, "result_record_sha256"),
            exchange_count=_required_positive_int(record, "exchange_count"),
            successful_exchange_count=_required_positive_int(
                record, "successful_exchange_count"
            ),
            transcript_sha256=_required_digest(record, "transcript_sha256"),
            container_exit_code=_required_int(record, "container_exit_code"),
            cleanup_confirmed=_required_bool(record, "cleanup_confirmed"),
            receipt_sha256=_required_digest(record, "receipt_sha256"),
        )
        if receipt.successful_exchange_count > receipt.exchange_count:
            raise ContainerRuntimeError(
                "successful exchange count exceeds total exchange count"
            )
        expected = _record_sha256(_receipt_content(receipt))
        if receipt.receipt_sha256 != expected:
            raise ContainerRuntimeError(
                "container receipt sha256 does not match content"
            )
        return receipt


class ContainerToolSession(ToolExecutor):
    """Lazy, long-lived JSONL tool process owned by one benchmark row."""

    def __init__(
        self,
        policy: SandboxPolicy,
        run_request: RunRequest,
        workspace: Path,
    ) -> None:
        if run_request.sandbox_policy != policy:
            raise ContainerRuntimeError("run request sandbox policy does not match")
        self._policy = policy
        self._request = run_request
        self._workspace = workspace.resolve()
        self._runtime_directory = self._workspace / "private-logs" / "tool-container"
        self._input_directory = self._runtime_directory / "input"
        self._cidfile = self._runtime_directory / "container.cid"
        self._receipt_path = self._runtime_directory / "execution-receipt.json"
        self._session_token = secrets.token_hex(16)
        self._container_name = _container_name(run_request, self._session_token)
        self._process: _Process | None = None
        self._transcript = hashlib.sha256()
        self._exchange_count = 0
        self._successful_exchange_count = 0
        self._closed = False
        self._cleanup_confirmed = False
        self._input_sha256 = ""
        try:
            self._backend_environment = build_container_backend_environment()
            validate_live_container_policy(self._policy)
            self._backend_path = resolve_container_backend(self._policy)
            require_rootless_container_daemon(
                self._backend_path,
                self._policy.backend,
                self._backend_environment,
            )
            require_local_pinned_container_image(
                self._backend_path,
                self._policy.image,
                self._backend_environment,
            )
        except (HostEnvironmentError, RuntimeError, ValueError) as exc:
            raise ContainerRuntimeError(
                "live container policy or backend is unavailable"
            ) from exc
        self._reset_runtime_directory()
        self._stage_canonical_task()
        try:
            self._plan = build_live_container_plan(
                self._policy,
                input_root=self._input_directory,
                container_name=self._container_name,
                session_token=self._session_token,
                cidfile=self._cidfile,
                backend_path=self._backend_path,
            )
        except (RuntimeError, ValueError) as exc:
            raise ContainerRuntimeError(
                "live container policy or backend is unavailable"
            ) from exc

    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        """Exchange one bounded request/response frame with the live tool."""

        if workspace.resolve() != self._workspace:
            raise ContainerRuntimeError(
                "tool workspace does not match session workspace"
            )
        if self._closed:
            raise ContainerRuntimeError("container tool session is closed")
        process = self._ensure_started()
        stdin = process.stdin
        stdout = process.stdout
        if stdin is None or stdout is None:
            self.abort()
            raise ContainerRuntimeError("container tool process pipes are unavailable")
        encoded_request = encode_tool_message(request)
        try:
            stdin.write(encoded_request)
            stdin.flush()
            encoded_response = _readline_with_timeout(
                stdout, self._policy.timeout_seconds
            )
        except TimeoutError as exc:
            self.abort()
            raise ContainerRuntimeError("container tool response timed out") from exc
        except (BrokenPipeError, OSError) as exc:
            self.abort()
            raise ContainerRuntimeError("container tool exchange failed") from exc
        try:
            response = decode_tool_response(encoded_response)
        except MultiHarnessValidationError as exc:
            self.abort()
            raise ContainerRuntimeError(
                "container returned a malformed response"
            ) from exc
        if response.request_id != request.request_id:
            self.abort()
            raise ContainerRuntimeError("container response request id does not match")
        self._transcript.update(_frame_commitment(encoded_request, encoded_response))
        self._exchange_count += 1
        if response.status == "succeeded":
            self._successful_exchange_count += 1
        return response

    def finalize(self, result: RunResult) -> ContainerExecutionReceipt:
        """Stop, clean, verify, and commit one successful session."""

        if self._closed:
            raise ContainerRuntimeError("container tool session is closed")
        if result.request_id != self._request.request_id:
            self.abort()
            raise ContainerRuntimeError("result request id does not match session")
        if result.status != "succeeded":
            self.abort()
            raise ContainerRuntimeError("result is not successful")
        if self._successful_exchange_count < 1:
            self.abort()
            raise ContainerRuntimeError("session has no successful tool exchange")
        process = self._process
        if process is None:
            self.abort()
            raise ContainerRuntimeError("container tool process was never started")
        if process.stdin is not None:
            process.stdin.close()
        try:
            exit_code = process.wait(timeout=self._policy.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            self.abort()
            raise ContainerRuntimeError("container tool process did not exit") from exc
        cleanup_confirmed = self._cleanup()
        self._closed = True
        if exit_code != 0:
            raise ContainerRuntimeError(
                f"container tool process exited with status {exit_code}"
            )
        if not cleanup_confirmed:
            raise ContainerRuntimeError("container cleanup could not be confirmed")
        receipt = _build_receipt(
            policy=self._policy,
            request=self._request,
            result=result,
            exchange_count=self._exchange_count,
            successful_exchange_count=self._successful_exchange_count,
            transcript_sha256=f"sha256:{self._transcript.hexdigest()}",
            exit_code=exit_code,
        )
        _write_json(self._receipt_path, receipt.to_record())
        return receipt

    def abort(self) -> None:
        """Terminate the session and force-remove only its exact container."""

        if self._closed:
            return
        process = self._process
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        cleanup_confirmed = self._cleanup()
        self._closed = True
        if not cleanup_confirmed:
            raise ContainerRuntimeError("container cleanup could not be confirmed")

    def _stage_canonical_task(self) -> None:
        private_logs = self._workspace / "private-logs"
        private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_logs.chmod(0o700)
        self._runtime_directory.mkdir(mode=0o700)
        self._input_directory.mkdir(mode=0o755)
        self._runtime_directory.chmod(0o700)
        self._input_directory.chmod(0o755)
        task_path = self._input_directory / "task.json"
        _write_json(task_path, self._request.task.to_record())
        task_path.chmod(0o444)
        self._input_sha256 = _bytes_sha256(task_path.read_bytes())

    def _reset_runtime_directory(self) -> None:
        private_logs = self._workspace / "private-logs"
        for path in (private_logs, self._runtime_directory):
            if path.is_symlink():
                raise ContainerRuntimeError(
                    "container runtime directory must not be a symlink"
                )
        if self._runtime_directory.exists():
            if not self._runtime_directory.is_dir():
                raise ContainerRuntimeError(
                    "container runtime path must be a directory"
                )
            shutil.rmtree(self._runtime_directory)

    def _ensure_started(self) -> _Process:
        if self._process is not None:
            return self._process
        self._validate_staged_input()
        try:
            self._backend_path = validate_container_backend_path(self._backend_path)
            self._backend_environment = build_container_backend_environment()
            require_rootless_container_daemon(
                self._backend_path,
                self._policy.backend,
                self._backend_environment,
            )
            require_local_pinned_container_image(
                self._backend_path,
                self._policy.image,
                self._backend_environment,
            )
            self._plan = build_live_container_plan(
                self._policy,
                input_root=self._input_directory,
                container_name=self._container_name,
                session_token=self._session_token,
                cidfile=self._cidfile,
                backend_path=self._backend_path,
            )
        except (HostEnvironmentError, RuntimeError, ValueError) as exc:
            raise ContainerRuntimeError("staged container roots changed") from exc
        try:
            container_id = _create_container(
                self._plan.argv,
                self._backend_environment,
                self._policy.timeout_seconds,
            )
            _verify_cidfile(self._cidfile, container_id)
            self._process = _start_process(
                (
                    str(self._backend_path),
                    "start",
                    "--attach",
                    "--interactive",
                    container_id,
                ),
                self._backend_environment,
            )
        except (ContainerRuntimeError, OSError) as exc:
            self.abort()
            raise ContainerRuntimeError(
                "container tool process could not start"
            ) from exc
        return self._process

    def _validate_staged_input(self) -> None:
        entries = tuple(self._input_directory.iterdir())
        task_path = self._input_directory / "task.json"
        if entries != (task_path,) or task_path.is_symlink() or not task_path.is_file():
            raise ContainerRuntimeError("staged container input tree changed")
        if _bytes_sha256(task_path.read_bytes()) != self._input_sha256:
            raise ContainerRuntimeError("staged canonical task changed")

    def _cleanup(self) -> bool:
        candidates = _session_container_ids(
            self._backend_path,
            self._container_name,
            self._session_token,
            self._backend_environment,
        )
        if candidates is None or len(candidates) > 1:
            self._cleanup_confirmed = False
            return False
        if candidates:
            _run_backend_command(
                (
                    str(self._backend_path),
                    "rm",
                    "--force",
                    candidates[0],
                ),
                self._backend_environment,
            )
        remaining = _session_container_ids(
            self._backend_path,
            self._container_name,
            self._session_token,
            self._backend_environment,
        )
        self._cleanup_confirmed = remaining == ()
        return self._cleanup_confirmed


def validate_container_resume(
    receipt_path: Path,
    *,
    request: RunRequest,
    result: RunResult,
    policy: SandboxPolicy,
) -> str:
    """Validate an untrusted successful receipt against exact row identities."""

    if request.sandbox_policy != policy:
        raise ContainerRuntimeError("resume policy does not match run request")
    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContainerRuntimeError("container receipt is unreadable") from exc
    if not isinstance(raw, Mapping):
        raise ContainerRuntimeError("container receipt must be a JSON object")
    receipt = ContainerExecutionReceipt.from_record(cast(Mapping[str, Any], raw))
    expected = {
        "backend": policy.backend,
        "image": policy.image,
        "policy_sha256": _policy_sha256(policy),
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "input_sha256": _canonical_task_sha256(request),
        "result_id": result.result_id,
        "result_sha256": result.result_sha256,
        "result_record_sha256": _result_record_sha256(result),
    }
    actual = {
        "backend": receipt.backend,
        "image": receipt.image,
        "policy_sha256": receipt.policy_sha256,
        "request_id": receipt.request_id,
        "request_sha256": receipt.request_sha256,
        "input_sha256": receipt.input_sha256,
        "result_id": receipt.result_id,
        "result_sha256": receipt.result_sha256,
        "result_record_sha256": receipt.result_record_sha256,
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value:
            raise ContainerRuntimeError(f"container receipt {field} does not match")
    if result.status != "succeeded":
        raise ContainerRuntimeError("container receipt result is not successful")
    if receipt.container_exit_code != 0 or not receipt.cleanup_confirmed:
        raise ContainerRuntimeError("container receipt is not a successful clean run")
    return receipt.receipt_sha256


def _build_receipt(
    *,
    policy: SandboxPolicy,
    request: RunRequest,
    result: RunResult,
    exchange_count: int,
    successful_exchange_count: int,
    transcript_sha256: str,
    exit_code: int,
) -> ContainerExecutionReceipt:
    content: dict[str, Any] = {
        "schema_version": CONTAINER_RECEIPT_SCHEMA_VERSION,
        "backend": policy.backend,
        "image": policy.image,
        "policy_sha256": _policy_sha256(policy),
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "input_sha256": _canonical_task_sha256(request),
        "result_id": result.result_id,
        "result_sha256": result.result_sha256,
        "result_record_sha256": _result_record_sha256(result),
        "exchange_count": exchange_count,
        "successful_exchange_count": successful_exchange_count,
        "transcript_sha256": transcript_sha256,
        "container_exit_code": exit_code,
        "cleanup_confirmed": True,
    }
    return ContainerExecutionReceipt(
        backend=policy.backend,
        image=policy.image,
        policy_sha256=cast(str, content["policy_sha256"]),
        request_id=request.request_id,
        request_sha256=request.request_sha256,
        input_sha256=cast(str, content["input_sha256"]),
        result_id=result.result_id,
        result_sha256=result.result_sha256,
        result_record_sha256=cast(str, content["result_record_sha256"]),
        exchange_count=exchange_count,
        successful_exchange_count=successful_exchange_count,
        transcript_sha256=transcript_sha256,
        container_exit_code=exit_code,
        cleanup_confirmed=True,
        receipt_sha256=_record_sha256(content),
    )


def _receipt_content(receipt: ContainerExecutionReceipt) -> dict[str, Any]:
    record = receipt.to_record()
    record.pop("receipt_sha256")
    return record


def _policy_sha256(policy: SandboxPolicy) -> str:
    record = policy.to_record()
    record.pop("policy_sha256", None)
    return _record_sha256(record)


def _frame_commitment(request: bytes, response: bytes) -> bytes:
    return hashlib.sha256(b"request\0" + request + b"\0response\0" + response).digest()


def _container_name(request: RunRequest, session_token: str) -> str:
    digest = hashlib.sha256(
        f"{request.request_id}\0{request.request_sha256}".encode()
    ).hexdigest()
    return f"lfb-tool-{digest[:16]}-{session_token}"


def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        record, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _canonical_task_sha256(request: RunRequest) -> str:
    return _bytes_sha256(_json_bytes(request.task.to_record()))


def _result_record_sha256(result: RunResult) -> str:
    return _bytes_sha256(_json_bytes(result.to_record()))


def _bytes_sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _json_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _write_json(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_json_bytes(record))
    temporary.replace(path)


def _readline_with_timeout(stream: IO[bytes], timeout_seconds: int) -> bytes:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(stream.readline, MAX_TOOL_MESSAGE_BYTES + 1)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _start_process(
    argv: tuple[str, ...],
    environment: Mapping[str, str],
) -> _Process:
    return subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
    )


def _create_container(
    argv: tuple[str, ...],
    environment: Mapping[str, str],
    timeout_seconds: int,
) -> str:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContainerRuntimeError("container creation failed") from exc
    if completed.returncode != 0 or len(completed.stdout) > 256:
        raise ContainerRuntimeError("container creation failed")
    try:
        container_id = completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ContainerRuntimeError(
            "container creation returned an invalid ID"
        ) from exc
    if not _valid_container_id(container_id):
        raise ContainerRuntimeError("container creation returned an invalid ID")
    return container_id


def _verify_cidfile(cidfile: Path, expected_id: str) -> None:
    actual_id = _read_container_id(cidfile)
    if actual_id != expected_id:
        raise ContainerRuntimeError(
            "container cidfile does not match created container"
        )


def _run_backend_command(
    argv: tuple[str, ...],
    environment: Mapping[str, str],
) -> int:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return -1
    return completed.returncode


def _session_container_ids(
    backend_path: Path,
    container_name: str,
    session_token: str,
    environment: Mapping[str, str],
) -> tuple[str, ...] | None:
    try:
        completed = subprocess.run(
            (
                str(backend_path),
                "ps",
                "--all",
                "--no-trunc",
                "--quiet",
                "--filter",
                f"name=^{container_name}$",
                "--filter",
                f"label={LIVE_SESSION_LABEL}={session_token}",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or len(completed.stdout) > 1_024:
        return None
    try:
        values = tuple(
            line.strip()
            for line in completed.stdout.decode("ascii").splitlines()
            if line.strip()
        )
    except UnicodeDecodeError:
        return None
    if len(set(values)) != len(values) or not all(
        _valid_container_id(value) for value in values
    ):
        return None
    return values


def _read_container_id(cidfile: Path) -> str | None:
    try:
        value = cidfile.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value if _valid_container_id(value) else None


def _valid_container_id(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ContainerRuntimeError(f"container receipt {field} must be a string")
    return value


def _required_digest(record: Mapping[str, Any], field: str) -> str:
    value = _required_str(record, field)
    raw = value.removeprefix("sha256:")
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise ContainerRuntimeError(f"container receipt {field} must be a SHA-256")
    return value


def _required_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContainerRuntimeError(f"container receipt {field} must be an integer")
    return value


def _required_positive_int(record: Mapping[str, Any], field: str) -> int:
    value = _required_int(record, field)
    if value < 1:
        raise ContainerRuntimeError(f"container receipt {field} must be positive")
    return value


def _required_bool(record: Mapping[str, Any], field: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise ContainerRuntimeError(f"container receipt {field} must be a boolean")
    return value

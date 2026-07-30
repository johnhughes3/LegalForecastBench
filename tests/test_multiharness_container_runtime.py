from __future__ import annotations

import io
import json
import stat
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.container_runtime import (
    ContainerExecutionReceipt,
    ContainerRuntimeError,
    ContainerToolSession,
    validate_container_resume,
)
from legalforecast.multiharness.sandbox import ContainerRuntimePlan
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    RunResult,
    SandboxPolicy,
)
from legalforecast.multiharness.tool_protocol import (
    ToolRequest,
    ToolResponse,
    decode_tool_request,
    encode_tool_message,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError

SHA256 = "sha256:" + "a" * 64
CONTAINER_ID = "e" * 64


class _RecordingInput(io.BytesIO):
    def __init__(self, process: _FakeProcess) -> None:
        super().__init__()
        self._process = process

    def write(self, data: bytes) -> int:
        request = decode_tool_request(data)
        self._process.requests.append(request)
        response = self._process.response_for(request)
        self._process.stdout.response = response
        return len(data)


class _ResponseStream(io.BytesIO):
    response: bytes = b""

    def readline(self, size: int = -1) -> bytes:
        del size
        response = self.response
        self.response = b""
        return response


class _FakeProcess:
    def __init__(
        self,
        response_for: Callable[[ToolRequest], bytes],
        *,
        returncode: int = 0,
    ) -> None:
        self.response_for = response_for
        self.returncode = returncode
        self.requests: list[ToolRequest] = []
        self.stdin = _RecordingInput(self)
        self.stdout = _ResponseStream()
        self.stderr = io.BytesIO()
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_session_stages_task_starts_lazily_and_records_sanitized_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    result = _run_result(request)
    process = _FakeProcess(
        lambda tool_request: encode_tool_message(
            ToolResponse(
                request_id=tool_request.request_id,
                status="succeeded",
                output={"text": "fixture"},
            )
        )
    )
    commands = _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)

    assert process.requests == []
    runtime = tmp_path / "private-logs" / "tool-container"
    task_path = runtime / "input" / "task.json"
    assert json.loads(task_path.read_text()) == request.task.to_record()
    assert stat.S_IMODE((tmp_path / "private-logs").stat().st_mode) == 0o700
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o700
    assert stat.S_IMODE(task_path.stat().st_mode) == 0o444
    assert not (runtime / "output").exists()

    response = session.execute(
        ToolRequest(request_id="tool-1", operation="read_text"),
        tmp_path,
    )
    receipt = session.finalize(result)

    assert response.status == "succeeded"
    assert len(process.requests) == 1
    assert receipt.request_sha256 == request.request_sha256
    assert receipt.input_sha256.startswith("sha256:")
    assert receipt.result_sha256 == result.result_sha256
    assert receipt.successful_exchange_count == 1
    assert receipt.container_exit_code == 0
    assert receipt.cleanup_confirmed is True
    serialized = json.dumps(receipt.to_record(), sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "fixture" not in serialized
    assert any(command[1:3] == ("rm", "--force") for command in commands)
    assert (
        validate_container_resume(
            tmp_path / "private-logs" / "tool-container" / "execution-receipt.json",
            request=request,
            result=result,
            policy=request.sandbox_policy,
        )
        == receipt.receipt_sha256
    )


@pytest.mark.parametrize(
    ("response", "match"),
    (
        (b"not-json\n", "malformed"),
        (
            encode_tool_message(ToolResponse(request_id="other", status="succeeded")),
            "request id",
        ),
    ),
)
def test_session_rejects_malformed_or_mismatched_responses_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response: bytes,
    match: str,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: response)
    commands = _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)

    with pytest.raises(ContainerRuntimeError, match=match):
        session.execute(
            ToolRequest(request_id="tool-1", operation="read_text"),
            tmp_path,
        )

    assert any(command[1:3] == ("rm", "--force") for command in commands)


def test_session_normalizes_response_timeout_and_forces_exact_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: b"")
    commands = _install_fake_backend(monkeypatch, process)

    def _timeout(_stream: Any, _timeout_seconds: int) -> bytes:
        raise TimeoutError

    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._readline_with_timeout",
        _timeout,
    )
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)

    with pytest.raises(ContainerRuntimeError, match="timed out"):
        session.execute(
            ToolRequest(request_id="tool-1", operation="read_text"),
            tmp_path,
        )

    cleanup = next(command for command in commands if command[1:3] == ("rm", "--force"))
    assert cleanup[3] == CONTAINER_ID
    assert len(cleanup) == 4


def test_abort_uses_exact_session_fallback_when_cidfile_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: b"not-json\n")
    commands = _install_fake_backend(monkeypatch, process, write_cid=False)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)

    with pytest.raises(ContainerRuntimeError, match="malformed"):
        session.execute(
            ToolRequest(request_id="tool-1", operation="read_text"),
            tmp_path,
        )

    cleanup = next(command for command in commands if command[1:3] == ("rm", "--force"))
    assert cleanup[3] == CONTAINER_ID


def test_session_rejects_staged_task_tampering_before_backend_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: b"")
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    task_path = tmp_path / "private-logs" / "tool-container" / "input" / "task.json"
    task_path.chmod(0o644)
    task_path.write_text('{"changed":true}\n', encoding="utf-8")

    with pytest.raises(ContainerRuntimeError, match="canonical task changed"):
        session.execute(
            ToolRequest(request_id="tool-1", operation="read_text"),
            tmp_path,
        )

    assert process.requests == []


def test_new_session_replaces_only_its_owned_stale_runtime_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    runtime = tmp_path / "private-logs" / "tool-container"
    (runtime / "output").mkdir(parents=True)
    (runtime / "output" / "stale.txt").write_text("stale", encoding="utf-8")
    neighboring_log = tmp_path / "private-logs" / "adapter.log"
    neighboring_log.write_text("preserve", encoding="utf-8")
    process = _FakeProcess(lambda _: b"")
    _install_fake_backend(monkeypatch, process)

    ContainerToolSession(request.sandbox_policy, request, tmp_path)

    assert not (runtime / "output" / "stale.txt").exists()
    assert not (runtime / "output").exists()
    assert neighboring_log.read_text(encoding="utf-8") == "preserve"


def test_finalize_rejects_unsuccessful_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    failed = encode_tool_message(
        ToolResponse(
            request_id="tool-1",
            status="failed",
            error_code="fixture_failure",
        )
    )
    process = _FakeProcess(lambda _: failed, returncode=9)
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    session.execute(ToolRequest(request_id="tool-1", operation="read_text"), tmp_path)

    with pytest.raises(ContainerRuntimeError, match="result is not successful"):
        session.finalize(_run_result(request, status="failed"))


def test_finalize_requires_successful_exchange_before_accepting_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    failed = encode_tool_message(
        ToolResponse(
            request_id="tool-1",
            status="failed",
            error_code="fixture_failure",
        )
    )
    process = _FakeProcess(lambda _: failed)
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    session.execute(ToolRequest(request_id="tool-1", operation="read_text"), tmp_path)

    with pytest.raises(ContainerRuntimeError, match="successful tool exchange"):
        session.finalize(_run_result(request))


def test_finalize_rejects_nonzero_container_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(
        lambda tool_request: encode_tool_message(
            ToolResponse(request_id=tool_request.request_id, status="succeeded")
        ),
        returncode=9,
    )
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    session.execute(ToolRequest(request_id="tool-1", operation="read_text"), tmp_path)

    with pytest.raises(ContainerRuntimeError, match="status 9"):
        session.finalize(_run_result(request))


def test_finalize_requires_confirmed_container_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(
        lambda tool_request: encode_tool_message(
            ToolResponse(request_id=tool_request.request_id, status="succeeded")
        )
    )
    _install_fake_backend(monkeypatch, process)
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._session_container_ids",
        lambda _backend, _name, _token, _environment: (CONTAINER_ID,),
    )
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    session.execute(ToolRequest(request_id="tool-1", operation="read_text"), tmp_path)

    with pytest.raises(ContainerRuntimeError, match="cleanup"):
        session.finalize(_run_result(request))


def test_abort_propagates_unconfirmed_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: b"")
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._session_container_ids",
        lambda _backend, _name, _token, _environment: None,
    )

    with pytest.raises(ContainerRuntimeError, match="cleanup"):
        session.abort()


def test_exchange_cleanup_failure_preserves_malformed_response_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    process = _FakeProcess(lambda _: b"not-json\n")
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._session_container_ids",
        lambda _backend, _name, _token, _environment: None,
    )

    with pytest.raises(ContainerRuntimeError, match="cleanup") as exc_info:
        session.execute(
            ToolRequest(request_id="tool-1", operation="read_text"),
            tmp_path,
        )

    assert isinstance(exc_info.value.__cause__, MultiHarnessValidationError)


def test_resume_validation_rejects_tampering_and_binding_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _run_request()
    result = _run_result(request)
    process = _FakeProcess(
        lambda tool_request: encode_tool_message(
            ToolResponse(request_id=tool_request.request_id, status="succeeded")
        )
    )
    _install_fake_backend(monkeypatch, process)
    session = ContainerToolSession(request.sandbox_policy, request, tmp_path)
    session.execute(ToolRequest(request_id="tool-1", operation="read_text"), tmp_path)
    receipt = session.finalize(result)
    path = tmp_path / "private-logs" / "tool-container" / "execution-receipt.json"
    record = receipt.to_record()
    record["exchange_count"] = 99
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ContainerRuntimeError, match="receipt sha256"):
        validate_container_resume(
            path,
            request=request,
            result=result,
            policy=request.sandbox_policy,
        )

    path.write_text(json.dumps(receipt.to_record()), encoding="utf-8")
    with pytest.raises(ContainerRuntimeError, match="result"):
        validate_container_resume(
            path,
            request=request,
            result=_run_result(request, result_sha256="sha256:" + "b" * 64),
            policy=request.sandbox_policy,
        )

    tampered_result = replace(result, public_summary={"tampered": True})
    with pytest.raises(ContainerRuntimeError, match="result_record_sha256"):
        validate_container_resume(
            path,
            request=request,
            result=tampered_result,
            policy=request.sandbox_policy,
        )


def test_receipt_parser_rejects_extra_fields() -> None:
    record = _receipt_record()
    record["host_path"] = "/secret"

    with pytest.raises(ContainerRuntimeError, match="fields"):
        ContainerExecutionReceipt.from_record(record)


def _install_fake_backend(
    monkeypatch: pytest.MonkeyPatch,
    process: _FakeProcess,
    *,
    write_cid: bool = True,
) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    active = False
    planned_cidfile: Path | None = None
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime.resolve_container_backend",
        lambda _policy: Path("/usr/bin/true"),
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime.validate_container_backend_path",
        lambda path: path,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime.require_rootless_container_daemon",
        lambda _path, _backend, _environment: None,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime.require_local_pinned_container_image",
        lambda _path, _image, _environment: None,
    )

    def _plan(
        policy: SandboxPolicy,
        *,
        input_root: Path,
        container_name: str,
        session_token: str,
        cidfile: Path,
        backend_path: Path,
    ) -> ContainerRuntimePlan:
        nonlocal planned_cidfile
        del input_root, session_token
        planned_cidfile = cidfile
        return ContainerRuntimePlan(
            backend=policy.backend,
            argv=(
                str(backend_path),
                "create",
                "--name",
                container_name,
                policy.image,
            ),
            policy=policy,
        )

    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime.build_live_container_plan",
        _plan,
    )

    def _create(
        _argv: tuple[str, ...],
        _environment: object,
        _timeout_seconds: int,
    ) -> str:
        nonlocal active
        active = True
        assert planned_cidfile is not None
        planned_cidfile.write_text(CONTAINER_ID, encoding="ascii")
        return CONTAINER_ID

    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._create_container",
        _create,
    )

    def _start(_argv: tuple[str, ...], _environment: object) -> _FakeProcess:
        if not write_cid:
            assert planned_cidfile is not None
            planned_cidfile.unlink()
        return process

    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._start_process",
        _start,
    )

    def _command(
        argv: tuple[str, ...],
        _environment: object,
    ) -> int:
        nonlocal active
        commands.append(argv)
        if len(argv) > 1 and argv[1] == "rm":
            active = False
        return 0

    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._run_backend_command",
        _command,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_runtime._session_container_ids",
        lambda _backend, _name, _token, _environment: (CONTAINER_ID,) if active else (),
    )
    return commands


def _run_request() -> RunRequest:
    policy = SandboxPolicy(
        policy_id="fixture",
        backend="docker",
        image="example.invalid/tool@sha256:" + "d" * 64,
        network_policy="none",
        timeout_seconds=5,
        uid_gid="1000:1000",
        memory_limit="1g",
        cpu_limit="1",
    )
    task = CanonicalTask(
        task_id="fixture-task",
        family="contract_only",
        scoring_mode="contract_only",
        suite_version="fixture",
        source_id="fixture-source",
        task_sha256=SHA256,
    )
    adapter = AdapterManifest(
        adapter_id="fixture-adapter",
        display_name="Fixture",
        adapter_version="1",
        command=("fixture",),
    )
    return RunRequest(
        request_id="run-1",
        task=task,
        adapter=adapter,
        model_key="fixture-model",
        sandbox_policy=policy,
        request_sha256=SHA256,
    )


def _run_result(
    request: RunRequest,
    *,
    status: str = "succeeded",
    result_sha256: str = "sha256:" + "c" * 64,
) -> RunResult:
    return RunResult(
        result_id="result-1",
        request_id=request.request_id,
        status=status,
        result_sha256=result_sha256,
    )


def _receipt_record() -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.multiharness.container_receipt.v1",
        "backend": "docker",
        "image": "example.invalid/tool@sha256:" + "d" * 64,
        "policy_sha256": SHA256,
        "request_id": "run-1",
        "request_sha256": SHA256,
        "input_sha256": SHA256,
        "result_id": "result-1",
        "result_sha256": SHA256,
        "result_record_sha256": SHA256,
        "exchange_count": 1,
        "successful_exchange_count": 1,
        "transcript_sha256": SHA256,
        "container_exit_code": 0,
        "cleanup_confirmed": True,
        "receipt_sha256": SHA256,
    }

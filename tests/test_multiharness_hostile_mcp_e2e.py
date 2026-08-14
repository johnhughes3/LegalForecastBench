"""Hostile MCP-mediated E2E: protocol, live plan, planes, and JSONL worker.

synthetic: true — the JSONL worker is tests/fixtures/local_cli_fake_cli.py
``--mode mcp-jsonl``. No live container pull and no provider spend.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.container_runtime import (
    ContainerRuntimeError,
    validate_container_resume,
)
from legalforecast.multiharness.contributor_boundary import (
    HOSTILE_DENIED,
    HOSTILE_QUARANTINED,
    LINUX_LANDLOCK_FS_SCOPE,
    classify_hostile_probe,
)
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_redaction import (
    PRIVATE_EXECUTION_DIR,
    LocalCliRedactionError,
    verify_execution_artifacts,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    execute_local_cli,
)
from legalforecast.multiharness.material_separation import (
    EVALUATOR_PRIVATE_TARGET,
    MaterialAccessError,
    MaterialSeparationLayout,
    materialize_separated_task,
    solver_material_access,
)
from legalforecast.multiharness.materialization import TaskArtifactProjection
from legalforecast.multiharness.sandbox import (
    BACKEND_DOCKER,
    LIVE_INPUT_TARGET,
    PROVIDER_EGRESS_HOST_ONLY,
    build_live_container_plan,
    sandbox_policy,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    ArtifactRecord,
    CanonicalTask,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import (
    ToolRequest,
    decode_tool_response,
    encode_tool_message,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_PINNED_IMAGE = (
    "ghcr.io/example/legalforecast-tool"
    "@sha256:0123456789abcdef0123456789abcdef"
    "0123456789abcdef0123456789abcdef"
)
_SHA256 = "sha256:" + "a" * 64
_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    "AWS_SECRET_ACCESS_KEY": "ambient-aws-canary",
    "HOME": "/private/operator-home",
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "LC_CTYPE": "C.UTF-8",
}


def test_live_container_plan_refuses_network_env_and_evaluator_private(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    evaluator_private = tmp_path / "evaluator-private"
    evaluator_private.mkdir()
    policy = sandbox_policy(
        policy_id="mcp-hostile",
        backend=BACKEND_DOCKER,
        image=_PINNED_IMAGE,
        mounts=(),
        network_policy=PROVIDER_EGRESS_HOST_ONLY,
        uid_gid="65532:65532",
        timeout_seconds=30,
        working_directory="/workspace",
        pids_limit=64,
        memory_limit="512m",
        cpu_limit="1",
        allowed_provider_env_vars=(),
    )
    plan = build_live_container_plan(
        policy,
        input_root=input_root,
        container_name="lfb-tool-hostile",
        session_token="a" * 32,
        cidfile=tmp_path / "container.cid",
        backend_path=Path("/usr/bin/true"),
    )
    argv = " ".join(plan.argv)
    assert "--network=none" in plan.argv
    assert "--read-only" in plan.argv
    assert f"dst={LIVE_INPUT_TARGET},readonly" in argv
    assert EVALUATOR_PRIVATE_TARGET not in argv
    assert str(evaluator_private) not in argv
    assert "OPENAI_API_KEY" not in argv
    assert "ANTHROPIC_API_KEY" not in argv
    assert "-e" not in plan.argv


def test_tool_protocol_refuses_path_escape() -> None:
    with pytest.raises(MultiHarnessValidationError, match="parent"):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            input_paths=("../secret",),
        )
    with pytest.raises(MultiHarnessValidationError):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            input_paths=("/etc/passwd",),
        )
    assert (
        classify_hostile_probe(
            in_scope=False,
            denied=True,
            tampered=False,
        )
        == HOSTILE_DENIED
    )


def test_solver_plane_cannot_read_evaluator_private(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    solver_file = source_root / "public.txt"
    solver_payload = b"solver-visible"
    solver_file.write_bytes(solver_payload)
    private_file = source_root / "gold.txt"
    private_payload = b"EVALUATOR_PRIVATE_CANARY"
    private_file.write_bytes(private_payload)
    task = CanonicalTask(
        task_id="harvey_lab:fixture/mcp-hostile",
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="fixture",
        source_id="fixture-task",
        task_sha256="f" * 64,
        artifacts=(
            ArtifactRecord(
                artifact_id="public",
                path="public.txt",
                sha256=hashlib.sha256(solver_payload).hexdigest(),
                media_type="text/plain",
                size_bytes=len(solver_payload),
            ),
            ArtifactRecord(
                artifact_id="gold",
                path="gold.txt",
                sha256=hashlib.sha256(private_payload).hexdigest(),
                media_type="text/plain",
                size_bytes=len(private_payload),
            ),
        ),
    )
    separated = materialize_separated_task(
        task,
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="mcp-hostile.v1",
            solver_artifacts=(TaskArtifactProjection("public", "public.txt"),),
            evaluator_private_artifacts=(TaskArtifactProjection("gold", "gold.txt"),),
        ),
    )
    solver_access = solver_material_access(separated)
    with pytest.raises(MaterialAccessError, match="not mounted"):
        solver_access.read_bytes(f"{EVALUATOR_PRIVATE_TARGET}/gold.txt")
    assert (tmp_path / "solver" / "gold.txt").exists() is False


def test_mcp_jsonl_worker_denies_out_of_scope_write_and_env(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "pwned.txt"
    request = ToolRequest(
        request_id="write-1",
        operation="write_probe",
        arguments={"path": str(target), "payload": "pwned"},
    )
    result = execute_local_cli(
        _worker_spec(
            "mcp-write",
            ("--mode", "mcp-jsonl"),
            stdin_bytes=encode_tool_message(request),
        ),
        scratch,
        parent_env=_CANARY_ENV,
    )
    assert result.exit_code != 0
    assert not target.exists()
    response = decode_tool_response(result.stdout)
    assert response.status == "failed"
    assert response.error_code == "denied"
    assert (
        classify_hostile_probe(
            in_scope=False,
            denied=not target.exists(),
            tampered=False,
        )
        == HOSTILE_DENIED
    )

    dump = ToolRequest(request_id="env-1", operation="dump_env")
    env_result = execute_local_cli(
        _worker_spec(
            "mcp-env",
            ("--mode", "mcp-jsonl"),
            stdin_bytes=encode_tool_message(dump),
        ),
        tmp_path / "env-scratch",
        parent_env=_CANARY_ENV,
    )
    env_response = decode_tool_response(env_result.stdout)
    environ = env_response.output["environ"]
    assert isinstance(environ, Mapping)
    env_map = cast(Mapping[str, object], environ)
    assert "OPENAI_API_KEY" not in env_map
    assert "ANTHROPIC_API_KEY" not in env_map
    assert "ambient-openai-canary" not in json.dumps(dict(env_map))


def test_mcp_worker_receipt_tamper_is_quarantined(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    request = ToolRequest(
        request_id="ok-1",
        operation="dump_env",
    )
    result = execute_local_cli(
        _worker_spec(
            "mcp-ok",
            ("--mode", "mcp-jsonl"),
            stdin_bytes=encode_tool_message(request),
        ),
        scratch,
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    receipt = scratch / PRIVATE_EXECUTION_DIR / "receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["status"] = "forged-success"
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(LocalCliRedactionError, match="digest mismatch"):
        verify_execution_artifacts(scratch)
    assert (
        classify_hostile_probe(
            in_scope=True,
            denied=False,
            tampered=True,
        )
        == HOSTILE_QUARANTINED
    )


def test_container_resume_refuses_tampered_receipt(tmp_path: Path) -> None:
    request = _run_request()
    result = RunResult(
        result_id="result-1",
        request_id=request.request_id,
        status="succeeded",
        result_sha256="sha256:" + "c" * 64,
    )
    path = tmp_path / "execution-receipt.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.container_receipt.v2",
                "backend": request.sandbox_policy.backend,
                "image": request.sandbox_policy.image,
                "policy_sha256": "sha256:" + "d" * 64,
                "request_id": request.request_id,
                "request_sha256": request.request_sha256,
                "input_tree_sha256": request.task.task_sha256,
                "result_id": result.result_id,
                "result_sha256": result.result_sha256,
                "result_record_sha256": "sha256:" + "e" * 64,
                "exchange_count": 1,
                "successful_exchange_count": 1,
                "transcript_sha256": "sha256:" + "f" * 64,
                "container_exit_code": 0,
                "cleanup_confirmed": True,
                "receipt_sha256": "sha256:" + "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ContainerRuntimeError):
        validate_container_resume(
            path,
            request=request,
            result=result,
            policy=request.sandbox_policy,
        )


def _worker_spec(
    spec_id: str,
    extra_args: tuple[str, ...],
    *,
    stdin_bytes: bytes = b"",
) -> LocalCliRunSpec:
    path = _FAKE_CLI.resolve()
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=LocalCliAdapterManifest(
            adapter_id="mcp-hostile-worker",
            display_name="MCP hostile worker",
            adapter_version="0.1.0",
            command=(sys.executable, str(path)),
            executable=executable_pin_for(path, version="0.1.0"),
            supported_auth_profiles=(FIXTURE_NONE,),
            version_probe_args=("--mode", "version"),
        ),
        auth_profile=FIXTURE_NONE,
        extra_args=extra_args,
        timeout_seconds=5,
        stdin_bytes=stdin_bytes,
        filesystem_scope=LINUX_LANDLOCK_FS_SCOPE,
    )


def _run_request() -> RunRequest:
    policy = sandbox_policy(
        policy_id="mcp-resume",
        backend=BACKEND_DOCKER,
        image=_PINNED_IMAGE,
        mounts=(),
        network_policy="none",
        uid_gid="65532:65532",
        timeout_seconds=5,
        working_directory="/workspace",
        pids_limit=64,
        memory_limit="512m",
        cpu_limit="1",
    )
    return RunRequest(
        request_id="run-1",
        task=CanonicalTask(
            task_id="fixture-task",
            family="contract_only",
            scoring_mode="contract_only",
            suite_version="fixture",
            source_id="fixture-source",
            task_sha256=_SHA256,
        ),
        adapter=AdapterManifest(
            adapter_id="fixture-adapter",
            display_name="Fixture",
            adapter_version="1",
            command=("fixture",),
        ),
        model_key="fixture-model",
        sandbox_policy=policy,
        request_sha256=_SHA256,
    )

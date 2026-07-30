from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness.container_runtime import (
    ContainerExecutionReceipt,
    ContainerToolSession,
)
from legalforecast.multiharness.host_environment import (
    build_container_backend_environment,
)
from legalforecast.multiharness.sandbox import (
    SUPPORTED_CONTAINER_BACKENDS,
    sandbox_policy,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import ToolRequest

SHA256 = "sha256:" + "a" * 64
PROVIDER_CANARY = "must-not-reach-container"


def test_rootless_container_negative_controls_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise a purpose-built local worker image when explicitly requested."""

    if os.environ.get("LEGALFORECAST_CONTAINER_E2E") != "1":
        pytest.skip("set LEGALFORECAST_CONTAINER_E2E=1 for the rootless runtime test")
    backend = os.environ.get("LEGALFORECAST_CONTAINER_E2E_BACKEND", "")
    image = os.environ.get("LEGALFORECAST_CONTAINER_E2E_IMAGE", "")
    if backend not in SUPPORTED_CONTAINER_BACKENDS:
        pytest.fail("LEGALFORECAST_CONTAINER_E2E_BACKEND must be docker or podman")
    if not image:
        pytest.fail(
            "LEGALFORECAST_CONTAINER_E2E_IMAGE must be an immutable local image"
        )
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_CANARY)
    backend_environment = build_container_backend_environment()

    policy = sandbox_policy(
        policy_id="container-negative-control",
        backend=backend,
        image=image,
        mounts=(),
        network_policy="none",
        uid_gid="65532:65532",
        timeout_seconds=30,
    )
    task = CanonicalTask(
        task_id="fixture:container-negative-control",
        family="contract_only",
        scoring_mode="contract_only",
        suite_version="fixture",
        source_id="fixture",
        task_sha256=SHA256,
    )
    adapter = AdapterManifest(
        adapter_id="container-negative-control",
        display_name="Container Negative Control",
        adapter_version="0.1.0",
        command=("fixture",),
    )
    request = RunRequest(
        request_id="container-negative-control",
        task=task,
        adapter=adapter,
        model_key="fixture",
        sandbox_policy=policy,
        request_sha256=SHA256,
    )
    result = RunResult(
        result_id="container-negative-control:result",
        request_id=request.request_id,
        status="succeeded",
        result_sha256="sha256:" + "b" * 64,
    )
    session = ContainerToolSession(policy, request, tmp_path)
    receipt: ContainerExecutionReceipt | None = None
    try:
        task_response = session.execute(
            ToolRequest(
                request_id="read-task-1",
                operation="read_text",
                input_paths=("task.json",),
            ),
            tmp_path,
        )
        assert task_response.status == "succeeded"
        task_text = task_response.output["text"]
        assert isinstance(task_text, str)
        decoded_task = cast(object, json.loads(task_text))
        assert isinstance(decoded_task, dict)
        task_record = cast(Mapping[str, Any], decoded_task)
        assert task_record.get("task_id") == task.task_id
        response = session.execute(
            ToolRequest(
                request_id="negative-control-1",
                operation="negative_control",
            ),
            tmp_path,
        )
        container_id = (
            (tmp_path / "private-logs" / "tool-container" / "container.cid")
            .read_text(encoding="ascii")
            .strip()
        )
        inspection = _inspect_container(
            backend,
            container_id,
            backend_environment,
        )
        _assert_live_boundary(
            inspection,
            image=image,
            input_root=(
                tmp_path / "private-logs" / "tool-container" / "input"
            ).resolve(),
        )
        assert response.status == "succeeded"
        assert response.output["effective_uid"] == 65532
        assert response.output["network_denied"] is True
        assert response.output["home_probe"] == "permission_denied"
        assert response.output["runtime_socket_probes"] == {
            "/run/docker.sock": "absent",
            "/run/podman/podman.sock": "absent",
            "/var/run/docker.sock": "absent",
        }
        assert response.output["rootfs_write_denied"] is True
        assert response.output["tmpfs_write_succeeded"] is True
        assert response.output["scoped_output_write_succeeded"] is True
        assert response.output["provider_env_names"] == ()
        assert isinstance(response.output["background_child_pid"], int)
        receipt = session.finalize(result)
    finally:
        if receipt is None:
            session.abort()

    if receipt is None:
        raise AssertionError("successful session did not produce a receipt")
    assert receipt.cleanup_confirmed is True
    completed = subprocess.run(
        (
            backend,
            "ps",
            "--all",
            "--quiet",
            "--filter",
            f"id={container_id}",
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=backend_environment,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == b""


def _inspect_container(
    backend: str,
    container_id: str,
    environment: Mapping[str, str],
) -> Mapping[str, Any]:
    completed = subprocess.run(
        (backend, "inspect", container_id),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=environment,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    decoded = cast(object, json.loads(completed.stdout))
    assert isinstance(decoded, list)
    records = cast(list[object], decoded)
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, dict)
    return cast(Mapping[str, Any], record)


def _assert_live_boundary(
    inspection: Mapping[str, Any],
    *,
    image: str,
    input_root: Path,
) -> None:
    host = _mapping(inspection, "HostConfig")
    config = _mapping(inspection, "Config")
    state = _mapping(inspection, "State")
    assert state.get("Running") is True
    assert host.get("NetworkMode") == "none"
    assert host.get("ReadonlyRootfs") is True
    assert config.get("User") == "65532:65532"
    assert config.get("OpenStdin") is True
    assert "ALL" in _string_sequence(host, "CapDrop")
    assert any(
        value.startswith("no-new-privileges")
        for value in _string_sequence(host, "SecurityOpt")
    )
    assert host.get("PidsLimit") == 256
    assert host.get("Memory") == 2 * 1024 * 1024 * 1024
    assert host.get("NanoCpus") == 1_000_000_000

    tmpfs = _mapping(host, "Tmpfs")
    assert set(tmpfs) == {"/tmp", "/workspace/output"}
    for destination in ("/tmp", "/workspace/output"):
        tmp_options = tmpfs.get(destination)
        assert isinstance(tmp_options, str)
        for option in ("noexec", "nosuid", "nodev"):
            assert option in tmp_options.split(",")
        assert "size=67108864" in tmp_options or "size=64m" in tmp_options

    raw_mounts = cast(object, inspection.get("Mounts"))
    assert isinstance(raw_mounts, list)
    mounts = cast(list[object], raw_mounts)
    bind_mounts = {
        cast(str, typed_mount["Destination"]): typed_mount
        for mount in mounts
        if isinstance(mount, dict)
        for typed_mount in (cast(Mapping[str, Any], mount),)
        if str(typed_mount.get("Type", "")).lower() == "bind"
    }
    assert set(bind_mounts) == {"/workspace/input"}
    assert Path(cast(str, bind_mounts["/workspace/input"]["Source"])) == input_root
    assert bind_mounts["/workspace/input"]["RW"] is False

    environment = _string_sequence(config, "Env")
    assert all(not value.startswith("OPENAI_API_KEY=") for value in environment)
    assert all(PROVIDER_CANARY not in value for value in environment)
    expected_image_id = "sha256:" + image.removeprefix("sha256:")
    assert inspection.get("Image") == expected_image_id


def _mapping(record: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = record.get(field)
    assert isinstance(value, dict)
    return cast(Mapping[str, Any], value)


def _string_sequence(record: Mapping[str, Any], field: str) -> tuple[str, ...]:
    raw_value = cast(object, record.get(field))
    assert isinstance(raw_value, list)
    value = cast(list[object], raw_value)
    assert all(isinstance(item, str) for item in value)
    return tuple(cast(list[str], value))

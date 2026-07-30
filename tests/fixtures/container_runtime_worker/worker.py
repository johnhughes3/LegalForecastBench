#!/usr/bin/env python3
"""Auditable JSONL worker for the opt-in container-runtime negative control."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, cast

MAX_MESSAGE_BYTES = 1_048_576
INPUT_ROOT = Path("/workspace/input")
OUTPUT_ROOT = Path("/workspace/output")
REQUEST_SCHEMA = "legalforecast.multiharness.tool_request.v1"
RESPONSE_SCHEMA = "legalforecast.multiharness.tool_response.v1"


def main() -> int:
    while line := sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1):
        request_id = "invalid-request"
        try:
            request = _request(line)
            request_id = request["request_id"]
            output = _execute(request)
            response: dict[str, Any] = {
                "schema_version": RESPONSE_SCHEMA,
                "request_id": request_id,
                "status": "succeeded",
                "output": output,
            }
        except (OSError, ValueError, json.JSONDecodeError):
            response = {
                "schema_version": RESPONSE_SCHEMA,
                "request_id": request_id,
                "status": "failed",
                "output": {},
                "error_code": "invalid_or_failed_request",
            }
        encoded = (json.dumps(response, sort_keys=True) + "\n").encode()
        if len(encoded) > MAX_MESSAGE_BYTES:
            return 2
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    return 0


def _request(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
        raise ValueError("request is not one bounded JSON line")
    decoded = cast(object, json.loads(line))
    if not isinstance(decoded, dict):
        raise ValueError("request must be a JSON object")
    value = cast(dict[str, Any], decoded)
    if value.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("request schema does not match")
    request_id = value.get("request_id")
    operation = value.get("operation")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request_id is invalid")
    if not isinstance(operation, str) or not operation:
        raise ValueError("operation is invalid")
    return value


def _execute(request: dict[str, Any]) -> dict[str, Any]:
    operation = request["operation"]
    if operation == "read_text":
        raw_paths = cast(object, request.get("input_paths"))
        if not isinstance(raw_paths, list):
            raise ValueError("read_text requires one input path")
        paths = cast(list[object], raw_paths)
        if len(paths) != 1:
            raise ValueError("read_text requires one input path")
        source = _safe_input_path(paths[0])
        data = source.read_bytes()
        if len(data) > MAX_MESSAGE_BYTES // 2:
            raise ValueError("input is too large")
        return {"text": data.decode("utf-8")}
    if operation == "negative_control":
        return _negative_control()
    raise ValueError("unsupported operation")


def _safe_input_path(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("input path must be a string")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError("input path is unsafe")
    source = INPUT_ROOT.joinpath(*relative.parts)
    if source.is_symlink() or not source.is_file():
        raise ValueError("input path is unavailable")
    return source


def _negative_control() -> dict[str, Any]:
    network_denied = False
    try:
        connection = socket.create_connection(("1.1.1.1", 53), timeout=0.5)
    except OSError:
        network_denied = True
    else:
        connection.close()

    try:
        tuple(Path("/root").iterdir())
    except OSError:
        home_read_denied = True
    else:
        home_read_denied = False

    runtime_socket_read_denied = not any(
        path.exists()
        for path in (
            Path("/var/run/docker.sock"),
            Path("/run/docker.sock"),
            Path("/run/podman/podman.sock"),
        )
    )

    try:
        Path("/rootfs-write-probe").write_text("unexpected", encoding="utf-8")
    except OSError:
        rootfs_write_denied = True
    else:
        rootfs_write_denied = False

    Path("/tmp/negative-control.tmp").write_text("tmpfs", encoding="utf-8")
    output_canary = OUTPUT_ROOT / "negative-control.txt"
    output_canary.write_text("scoped-output\n", encoding="utf-8")
    child = subprocess.Popen(
        ("sleep", "120"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "background_child_pid": child.pid,
        "effective_uid": os.geteuid(),
        "home_read_denied": home_read_denied,
        "network_denied": network_denied,
        "provider_env_names": sorted(
            name
            for name in os.environ
            if name.endswith("_API_KEY") or name.endswith("_TOKEN")
        ),
        "rootfs_write_denied": rootfs_write_denied,
        "runtime_socket_read_denied": runtime_socket_read_denied,
        "scoped_output_write_succeeded": output_canary.is_file(),
        "tmpfs_write_succeeded": Path("/tmp/negative-control.tmp").is_file(),
    }


if __name__ == "__main__":
    raise SystemExit(main())

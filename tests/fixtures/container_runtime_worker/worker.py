#!/usr/bin/env python3
"""JSONL worker for the network-disabled Harvey tool container fixture."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, "/opt/legalforecast")
from harvey_tools import HarveyToolExecutor

MAX_MESSAGE_BYTES = 1_048_576
INPUT_ROOT = Path("/workspace/input")
OUTPUT_ROOT = Path("/workspace/output")
REQUEST_SCHEMA = "legalforecast.multiharness.tool_request.v1"
RESPONSE_SCHEMA = "legalforecast.multiharness.tool_response.v1"
TOOLS = HarveyToolExecutor(
    INPUT_ROOT,
    documents_root=INPUT_ROOT / "documents",
    output_root=OUTPUT_ROOT,
)


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
    TOOLS.close()
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
    if not isinstance(value.get("request_id"), str) or not value["request_id"]:
        raise ValueError("request_id is invalid")
    if not isinstance(value.get("operation"), str) or not value["operation"]:
        raise ValueError("operation is invalid")
    return value


def _execute(request: dict[str, Any]) -> dict[str, Any]:
    if request["operation"] == "negative_control":
        return _negative_control()
    arguments = request.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    return TOOLS.handle(request["operation"], cast(dict[str, Any], arguments))


def _negative_control() -> dict[str, Any]:
    network_denied = False
    try:
        connection = socket.create_connection(("1.1.1.1", 53), timeout=0.5)
    except OSError:
        network_denied = True
    else:
        connection.close()

    home_path = Path("/root")
    if not home_path.exists():
        home_probe = "absent"
    else:
        try:
            tuple(home_path.iterdir())
        except PermissionError:
            home_probe = "permission_denied"
        except OSError:
            home_probe = "other_error"
        else:
            home_probe = "readable"

    runtime_socket_probes = {
        str(path): _path_probe(path)
        for path in (
            Path("/var/run/docker.sock"),
            Path("/run/docker.sock"),
            Path("/run/podman/podman.sock"),
        )
    }
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
        "home_probe": home_probe,
        "network_denied": network_denied,
        "provider_env_names": sorted(
            name
            for name in os.environ
            if name.endswith("_API_KEY") or name.endswith("_TOKEN")
        ),
        "rootfs_write_denied": rootfs_write_denied,
        "runtime_socket_probes": runtime_socket_probes,
        "scoped_output_write_succeeded": output_canary.is_file(),
        "tmpfs_write_succeeded": Path("/tmp/negative-control.tmp").is_file(),
    }


def _path_probe(path: Path) -> str:
    if not path.exists():
        return "absent"
    try:
        path.read_bytes()
    except PermissionError:
        return "permission_denied"
    except OSError:
        return "other_error"
    return "readable"


if __name__ == "__main__":
    raise SystemExit(main())

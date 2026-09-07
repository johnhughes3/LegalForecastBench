#!/usr/bin/env python3
"""Production network-disabled JSONL entrypoint for Harvey workspace tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, "/opt/legalforecast")
from harvey_tools import HarveyToolExecutor

MAX_MESSAGE_BYTES = 1_048_576
REQUEST_SCHEMA = "legalforecast.multiharness.tool_request.v1"
RESPONSE_SCHEMA = "legalforecast.multiharness.tool_response.v1"
INPUT_ROOT = Path("/workspace/input")
OUTPUT_ROOT = Path("/workspace/output")
TOOLS = HarveyToolExecutor(
    INPUT_ROOT,
    documents_root=INPUT_ROOT / "documents",
    output_root=OUTPUT_ROOT,
)


def main() -> int:
    for line in sys.stdin.buffer:
        request_id = "invalid-request"
        try:
            request = _request(line)
            request_id = request["request_id"]
            arguments = request.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object")
            output = TOOLS.handle(request["operation"], cast(dict[str, Any], arguments))
            response: dict[str, Any] = {
                "schema_version": RESPONSE_SCHEMA,
                "request_id": request_id,
                "status": "succeeded",
                "output": output,
            }
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
            response = {
                "schema_version": RESPONSE_SCHEMA,
                "request_id": request_id,
                "status": "failed",
                "output": {},
                "error_code": "invalid_or_failed_request",
            }
        encoded = (json.dumps(response, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > MAX_MESSAGE_BYTES:
            return 2
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    TOOLS.close()
    return 0


def _request(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
        raise ValueError("request is not one bounded JSON line")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("request must be an object")
    request = cast(dict[str, Any], value)
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("request schema does not match")
    if not isinstance(request.get("request_id"), str) or not request["request_id"]:
        raise ValueError("request_id is invalid")
    if not isinstance(request.get("operation"), str) or not request["operation"]:
        raise ValueError("operation is invalid")
    return request


if __name__ == "__main__":
    raise SystemExit(main())

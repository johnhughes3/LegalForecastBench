"""Read-only canonical prompt worker for the network-disabled tool container."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import BinaryIO

from legalforecast.immutable_io import read_single_link_file
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolResponse,
    decode_tool_request,
    encode_tool_message,
)


def serve(incoming: BinaryIO, outgoing: BinaryIO, input_root: Path) -> int:
    """Serve only the host-staged canonical prompt over bounded JSONL frames."""

    while line := incoming.readline(MAX_TOOL_MESSAGE_BYTES + 1):
        request_id = "invalid-request"
        try:
            request = decode_tool_request(line)
            request_id = request.request_id
            if (
                request.operation != "read_text"
                or request.input_paths != (SOLVER_INPUT_ENTRY_PATH,)
                or dict(request.arguments) != {"encoding": "utf-8"}
            ):
                raise ValueError("only the canonical prompt may be read")
            payload = read_single_link_file(
                input_root / SOLVER_INPUT_ENTRY_PATH, label="canonical prompt"
            )
            if len(payload) > MAX_TOOL_MESSAGE_BYTES:
                raise ValueError("canonical prompt exceeds the tool frame limit")
            response = ToolResponse(
                request_id=request_id,
                status="succeeded",
                output={"text": payload.decode("utf-8")},
            )
            encoded = encode_tool_message(response)
        except (OSError, ValueError, UnicodeError):
            encoded = encode_tool_message(
                ToolResponse(
                    request_id=request_id,
                    status="failed",
                    output={},
                    error_code="invalid_canonical_task_request",
                )
            )
        outgoing.write(encoded)
        outgoing.flush()
    return 0


def main() -> int:
    """Run inside the canonical read-only, network-disabled container policy."""

    return serve(sys.stdin.buffer, sys.stdout.buffer, Path("/workspace/input"))


if __name__ == "__main__":
    raise SystemExit(main())

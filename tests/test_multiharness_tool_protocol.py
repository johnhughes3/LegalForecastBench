from __future__ import annotations

import pytest
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolRequest,
    ToolResponse,
    decode_tool_request,
    decode_tool_response,
    encode_tool_message,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError


def test_tool_protocol_round_trip() -> None:
    request = ToolRequest(
        request_id="tool-1",
        operation="read_text",
        arguments={"encoding": "utf-8"},
        input_paths=("documents/complaint.txt",),
    )
    response = ToolResponse(
        request_id=request.request_id,
        status="succeeded",
        output={"text": "fixture"},
    )

    assert decode_tool_request(encode_tool_message(request)) == request
    assert decode_tool_response(encode_tool_message(response)) == response


@pytest.mark.parametrize(
    "data",
    (
        b"{}",
        b"{}\n{}\n",
        b"not-json\n",
        b"[]\n",
    ),
)
def test_tool_protocol_rejects_malformed_frames(data: bytes) -> None:
    with pytest.raises(MultiHarnessValidationError):
        decode_tool_request(data)


def test_tool_protocol_rejects_path_traversal() -> None:
    with pytest.raises(MultiHarnessValidationError, match="parent"):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            input_paths=("../secret",),
        )


def test_tool_protocol_rejects_oversized_messages() -> None:
    oversized = b"{" + b" " * MAX_TOOL_MESSAGE_BYTES + b"}\n"

    with pytest.raises(MultiHarnessValidationError, match="maximum size"):
        decode_tool_request(oversized)


def test_failed_tool_response_requires_error_code() -> None:
    with pytest.raises(MultiHarnessValidationError, match="error_code"):
        ToolResponse(request_id="tool-1", status="failed")

from __future__ import annotations

from types import MappingProxyType
from typing import Any, cast

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
        arguments={"options": {"encoding": "utf-8", "fallbacks": ["ascii"]}},
        input_paths=("documents/complaint.txt",),
    )
    response = ToolResponse(
        request_id=request.request_id,
        status="succeeded",
        output={"results": [{"text": "fixture", "metadata": {"pages": 1}}]},
    )

    assert decode_tool_request(encode_tool_message(request)) == request
    assert decode_tool_response(encode_tool_message(response)) == response


def test_tool_protocol_accepts_non_dict_mapping_implementations() -> None:
    request = ToolRequest(
        request_id="tool-1",
        operation="read_text",
        arguments=MappingProxyType({"encoding": "utf-8"}),
    )
    response = ToolResponse(
        request_id="tool-1",
        status="succeeded",
        output=MappingProxyType({"text": "fixture"}),
    )

    assert decode_tool_request(encode_tool_message(request)).arguments == {
        "encoding": "utf-8"
    }
    assert decode_tool_response(encode_tool_message(response)).output == {
        "text": "fixture"
    }


def test_tool_protocol_snapshots_caller_owned_payloads_recursively() -> None:
    request_options: dict[str, Any] = {"encoding": "utf-8"}
    request_arguments: dict[str, Any] = {"options": request_options}
    response_row: dict[str, Any] = {"text": "fixture"}
    response_output: dict[str, Any] = {"rows": [response_row]}
    request = ToolRequest(
        request_id="tool-1",
        operation="read_text",
        arguments=request_arguments,
    )
    response = ToolResponse(
        request_id="tool-1",
        status="succeeded",
        output=response_output,
    )

    request_arguments["late"] = {1: "lossy key"}
    request_options["encoding"] = "latin-1"
    response_output["late"] = {2: "lossy key"}
    response_row["text"] = "mutated"

    assert request.to_record()["arguments"] == {"options": {"encoding": "utf-8"}}
    assert response.to_record()["output"] == {"rows": [{"text": "fixture"}]}


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


def test_tool_request_rejects_non_string_mapping_keys_recursively() -> None:
    arguments = cast(
        dict[str, Any],
        {"nested": [{"valid": {1: "lossy key"}}]},
    )

    with pytest.raises(
        MultiHarnessValidationError,
        match=r"arguments\.nested\[0\]\.valid mapping key 1 must be a string",
    ):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            arguments=arguments,
        )


def test_tool_request_rejects_encoder_incompatible_mapping_key_precisely() -> None:
    arguments = cast(
        dict[str, Any],
        {("tuple", "key"): "not JSON-compatible"},
    )

    with pytest.raises(
        MultiHarnessValidationError,
        match=r"arguments mapping key \('tuple', 'key'\) must be a string",
    ):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            arguments=arguments,
        )


def test_tool_response_rejects_non_string_mapping_keys_recursively() -> None:
    output = cast(
        dict[str, Any],
        {"rows": [{2: "lossy key"}]},
    )

    with pytest.raises(
        MultiHarnessValidationError,
        match=r"output\.rows\[0\] mapping key 2 must be a string",
    ):
        ToolResponse(
            request_id="tool-1",
            status="succeeded",
            output=output,
        )


def test_tool_protocol_normalizes_cyclic_values_as_validation_errors() -> None:
    arguments: dict[str, Any] = {}
    arguments["self"] = arguments

    with pytest.raises(MultiHarnessValidationError, match="JSON-compatible"):
        ToolRequest(
            request_id="tool-1",
            operation="read_text",
            arguments=arguments,
        )


def test_tool_protocol_rejects_oversized_messages() -> None:
    oversized = b"{" + b" " * MAX_TOOL_MESSAGE_BYTES + b"}\n"

    with pytest.raises(MultiHarnessValidationError, match="maximum size"):
        decode_tool_request(oversized)


def test_failed_tool_response_requires_error_code() -> None:
    with pytest.raises(MultiHarnessValidationError, match="error_code"):
        ToolResponse(request_id="tool-1", status="failed")

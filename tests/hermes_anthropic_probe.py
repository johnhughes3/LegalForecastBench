"""Pinned Hermes native Anthropic wire fixture; all network access is denied."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import socket
import sys
from pathlib import Path


def main() -> None:
    checkout, runtime_path, private_home = map(Path, sys.argv[1:4])
    os.environ.clear()
    os.environ.update(
        {
            "HERMES_HOME": str(private_home),
            "HERMES_SAFE_MODE": "1",
            "HERMES_IGNORE_RULES": "1",
        }
    )
    (private_home / "config.yaml").write_text(
        json.dumps(
            {
                "tools": {"tool_search": {"enabled": "off"}},
                "memory": {"memory_enabled": False, "user_profile_enabled": False},
            }
        )
    )

    def denied(*_args, **_kwargs):
        raise OSError("offline Anthropic conformance forbids network")

    socket.socket.connect = denied
    httpx = importlib.import_module("httpx")
    httpx.Client.send = denied
    importlib.import_module("requests").Session.request = denied
    calls = []

    def send(_self, request, **_kwargs):
        assert str(request.url) == "http://127.0.0.1:12345/v1/messages"
        assert request.headers["x-api-key"] == "synthetic-capability"
        wire = json.loads(request.content)
        assert wire["model"] == "claude-sonnet-4-5"
        assert wire["stream"] is True
        tools = [
            block
            for message in wire["messages"]
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert {tool["name"] for tool in wire["tools"]} == {
            "read_canonical_task",
            "read_release_document",
        }
        if tools:
            content = tools[-1]["content"]
            if isinstance(content, list):
                content = "".join(item["text"] for item in content)
            assert (
                json.loads(content)["text"]
                == [
                    "PRIVATE canonical forecast task",
                    '["documents/record.txt"]',
                    "PRIVATE full pleading evidence",
                ][len(calls) - 1]
            )
        if len(calls) == 3:
            block = {"type": "text", "text": ""}
            delta = {
                "type": "text_delta",
                "text": json.dumps(
                    {
                        "case_assessment": "Fixture only",
                        "predictions": [
                            {
                                "unit_id": "count_i",
                                "probability_fully_dismissed": 0.7,
                            }
                        ],
                    }
                ),
            }
            stop = "end_turn"
        else:
            block = {
                "type": "tool_use",
                "id": f"read_{len(calls) + 1}",
                "name": "read_canonical_task" if not calls else "read_release_document",
                "input": {},
            }
            arguments = {"offset": 0}
            if len(calls) == 2:
                arguments["path"] = "documents/record.txt"
            delta = {"type": "input_json_delta", "partial_json": json.dumps(arguments)}
            stop = "tool_use"
        events = [
            {
                "type": "message_start",
                "message": {
                    "id": "fixture",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": wire["model"],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
            {"type": "content_block_start", "index": 0, "content_block": block},
            {"type": "content_block_delta", "index": 0, "delta": delta},
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop, "stop_sequence": None},
                "usage": {"output_tokens": 4},
            },
            {"type": "message_stop"},
        ]
        response = "".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
        )
        calls.append(
            {"body": wire, "headers": dict(request.headers), "response": response}
        )
        return httpx.Response(
            200,
            request=request,
            content=response.encode(),
            headers={"content-type": "text/event-stream"},
        )

    # Intercept the class before importing Hermes: rebuilt SDK clients cannot escape.
    httpx.Client.send = send
    sys.path.insert(0, str(checkout))
    factory = importlib.import_module("run_agent").AIAgent
    registry = importlib.import_module("tools.registry").registry
    spec = importlib.util.spec_from_file_location("bridge", runtime_path)
    assert spec is not None and spec.loader is not None
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    outputs = [
        {"text": "PRIVATE canonical forecast task"},
        {"text": '["documents/record.txt"]', "next_offset": 24, "complete": True},
        {"text": "PRIVATE full pleading evidence", "next_offset": 30, "complete": True},
    ]
    for output in outputs[1:]:
        output["next_offset"] = len(output["text"])
    incoming = io.StringIO(
        "".join(
            json.dumps(
                {
                    "schema_version": "legalforecast.multiharness.tool_response.v1",
                    "request_id": f"case:hermes-tool:{index}",
                    "status": "succeeded",
                    "output": output,
                }
            )
            + "\n"
            for index, output in enumerate(outputs, 1)
        )
    )
    outgoing = io.StringIO()
    result = bridge.execute(
        {
            "request_id": "case",
            "model": "claude-sonnet-4-5",
            "session_id": "offline-anthropic",
            "required_unit_ids": ["count_i"],
            "working_directory": str(private_home),
            "solver_input_path": "prompt.txt",
            "tool_request_schema": "legalforecast.multiharness.tool_request.v1",
            "tool_response_schema": "legalforecast.multiharness.tool_response.v1",
            "gateway": {
                "base_url": "http://127.0.0.1:12345",
                "capability_token": "synthetic-capability",
                "max_output_tokens": 128000,
                "reasoning_config": {"effort": "high"},
            },
        },
        factory,
        registry,
        incoming,
        outgoing,
    )
    assert result["result"]["completed"] is True
    assert result["tool_call_count"] == 3
    assert result["document_tool_call_count"] == 2
    assert len(calls) == 4
    assert [
        json.loads(line)["operation"] for line in outgoing.getvalue().splitlines()
    ] == ["read_text", "read_release_document", "read_release_document"]
    (private_home / "wire.json").write_text(json.dumps(calls))
    print("Pinned Hermes Anthropic conversation passed (SDK wire fixtures only)")


if __name__ == "__main__":
    main()

"""Local Anthropic-compatible SSE fixture for the rootless release smoke test."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

DOCUMENTS = {
    "unit-001": [
        f"/workspace/documents/{index:04d}-{name}.txt"
        for index, name in enumerate(
            (
                "full-01-amended_complaint",
                "full-02-complaint",
                "full-03-counterclaim",
                "full-04-crossclaim",
                "full-05-interpleader_complaint",
                "full-06-motion_to_dismiss_memorandum",
                "full-07-motion_to_dismiss_notice",
                "full-08-opposition",
                "full-09-other_claim_bearing_filing",
                "full-10-reply",
                "full-11-supplemental_brief",
                "full-12-surreply",
                "full-13-third_party_complaint",
            )
        )
    ],
    "unit-002": [
        "/workspace/documents/0000-case-002-complaint.txt",
        "/workspace/documents/0001-case-002-memorandum.txt",
    ],
    "unit-003": [
        "/workspace/documents/0000-case-003-counterclaim.txt",
        "/workspace/documents/0001-case-003-reply.txt",
    ],
}


def _message_start(model: str, unit_id: str) -> dict[str, Any]:
    return {
        "type": "message_start",
        "message": {
            "id": f"msg_{unit_id}",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": 3,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 0,
            },
        },
    }


def _events(model: str, unit_id: str, *, had_tool_result: bool) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [_message_start(model, unit_id), {"type": "ping"}]
    if not had_tool_result:
        command = "cat " + " ".join(("/workspace/prompt.txt", *DOCUMENTS[unit_id]))
        events.extend(
            (
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": f"toolu_{unit_id}",
                        "name": "Bash",
                        "input": {},
                    },
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps({"command": command}),
                    },
                },
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {"output_tokens": 2},
                },
                {"type": "message_stop"},
            )
        )
    else:
        forecast = {
            "case_assessment": "fixture evidence read",
            "predictions": [{"unit_id": unit_id, "probability_fully_dismissed": 0.25}],
        }
        events.extend(
            (
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": json.dumps(forecast)},
                },
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 3},
                },
                {"type": "message_stop"},
            )
        )
    return events


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["content-length"]))
        payload: dict[str, Any] = json.loads(body)
        wire = body.decode("utf-8")
        unit_id = next((unit for unit in DOCUMENTS if unit in wire), "unit-001")
        had_tool_result = _has_tool_result(payload)
        print(
            json.dumps(
                {
                    "path": self.path,
                    "unit_id": unit_id,
                    "had_tool_result": had_tool_result,
                }
            ),
            flush=True,
        )
        response = b"".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()
            for event in _events(
                payload["model"], unit_id, had_tool_result=had_tool_result
            )
        )
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        del format, args
        pass


def _has_tool_result(payload: dict[str, Any]) -> bool:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return False
    for raw_message in cast(list[object], messages):
        if not isinstance(raw_message, dict):
            continue
        message = cast(dict[str, object], raw_message)
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for raw_item in cast(list[object], content):
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, object], raw_item)
            if item.get("type") == "tool_result":
                return True
    return False


ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()

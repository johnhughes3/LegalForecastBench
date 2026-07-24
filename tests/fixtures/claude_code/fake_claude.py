#!/usr/bin/env python3
"""Deterministic, offline Claude Code CLI fixture for adapter tests."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from collections.abc import Mapping
from typing import Any, NoReturn

FIXTURE_VERSION = "2.1.211 (Claude Code fixture)"
FIXTURE_CLAUDE_CODE_VERSION = "2.1.211"
FIXTURE_SESSION_ID = "fixture-session-0001"
FIXTURE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
FIXTURE_USAGE = {
    "input_tokens": 11,
    "output_tokens": 7,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}
MODES = {
    "cancellation",
    "invalid_json",
    "malformed_event",
    "mixed_output",
    "model_drift",
    "nonzero",
    "partial_result",
    "resume_mismatch",
    "secret_canary",
    "success",
    "timeout",
    "tool_request",
    "version_drift",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude",
        description="Offline deterministic Claude Code test fixture.",
    )
    parser.add_argument("-p", "--print", dest="prompt")
    parser.add_argument(
        "--output-format",
        choices=("stream-json", "json", "text"),
        default="text",
    )
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--resume")
    parser.add_argument("--session-id")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=FIXTURE_VERSION)
    return parser


def _emit(event: Mapping[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)


def _init_event(args: argparse.Namespace, mode: str) -> dict[str, Any]:
    model = "claude-opus-4-1-fixture-drift" if mode == "model_drift" else args.model
    version = (
        "9.9.9-fixture-drift"
        if mode == "version_drift"
        else FIXTURE_CLAUDE_CODE_VERSION
    )
    return {
        "type": "system",
        "subtype": "init",
        "session_id": args.session_id or FIXTURE_SESSION_ID,
        "model": model,
        "claude_code_version": version,
        "tools": FIXTURE_TOOLS,
    }


def _assistant_event(*, tool_request: bool = False) -> dict[str, Any]:
    content: list[dict[str, Any]]
    if tool_request:
        content = [
            {
                "type": "tool_use",
                "id": "toolu_fixture_0001",
                "name": "Read",
                "input": {"file_path": "task/input.txt"},
            }
        ]
    else:
        content = [{"type": "text", "text": "fixture response"}]
    return {
        "type": "assistant",
        "session_id": FIXTURE_SESSION_ID,
        "message": {
            "id": "msg_fixture_0001",
            "role": "assistant",
            "content": content,
        },
    }


def _result_event(
    *,
    subtype: str = "success",
    is_error: bool = False,
    session_id: str = FIXTURE_SESSION_ID,
    requested_session_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "result",
        "subtype": subtype,
        "is_error": is_error,
        "session_id": session_id,
        "result": "" if is_error else "fixture response",
        "usage": FIXTURE_USAGE,
    }
    if requested_session_id is not None:
        event["requested_session_id"] = requested_session_id
    return event


def _install_cancellation_handler() -> None:
    def cancel(_signum: int, _frame: object) -> NoReturn:
        _emit(_result_event(subtype="cancelled", is_error=True))
        raise SystemExit(130)

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)


def _wait_forever() -> NoReturn:
    while True:
        time.sleep(60)


def _run_stream(args: argparse.Namespace, mode: str) -> int:
    if mode == "cancellation":
        # Install before the first observable byte so a caller can safely signal
        # as soon as it reads the init event without racing default SIGTERM.
        _install_cancellation_handler()
    _emit(_init_event(args, mode))

    if mode == "timeout":
        time.sleep(60)
        return 0
    if mode == "cancellation":
        _wait_forever()
    if mode == "mixed_output":
        print("FAKE_CLAUDE_MIXED_STDOUT", flush=True)
        return 0
    if mode in {"invalid_json", "malformed_event"}:
        print('{"type":"assistant"', flush=True)
        return 0
    if mode == "nonzero":
        _emit(_result_event(subtype="error_during_execution", is_error=True))
        return 23
    if mode == "partial_result":
        _emit(_assistant_event())
        return 0
    if mode == "resume_mismatch":
        _emit(
            _result_event(
                subtype=mode,
                is_error=True,
                session_id="fixture-session-mismatch",
                requested_session_id=args.resume,
            )
        )
        return 9
    if mode == "secret_canary":
        canary = os.environ.get(
            "LFB_FAKE_CLAUDE_SECRET_CANARY", "fixture-secret-not-configured"
        )
        _emit(
            {
                "type": "assistant",
                "session_id": FIXTURE_SESSION_ID,
                "message": {
                    "id": "msg_fixture_secret",
                    "role": "assistant",
                    "content": [{"type": "text", "text": canary}],
                },
            }
        )
        print(f"provider stderr contained secret: {canary}", file=sys.stderr)
        _emit(_result_event())
        return 0

    _emit(_assistant_event(tool_request=mode == "tool_request"))
    _emit(_result_event())
    return 0


def main() -> int:
    args = _parser().parse_args()
    mode = os.environ.get("LFB_FAKE_CLAUDE_MODE", "success")
    if mode not in MODES:
        print("fake claude: unsupported mode", file=sys.stderr)
        return 64

    if args.output_format == "stream-json":
        return _run_stream(args, mode)
    if args.output_format == "json":
        _emit(_result_event())
        return 0
    print("fixture response")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

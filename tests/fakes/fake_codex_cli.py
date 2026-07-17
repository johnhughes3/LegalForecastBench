#!/usr/bin/env python3
"""Deterministic offline stand-in for the Codex CLI JSONL interface."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

THREAD_ID = "00000000-0000-7000-8000-000000000001"
FAKE_VERSION = "codex-cli 0.0.0-legalforecast-fake"
DRIFT_VERSION = "codex-cli 99.0.0-drift"
RESULT = "LEGALFORECAST_FAKE_CODEX_RESULT"
SECRET_CANARY = "LEGALFORECAST_SECRET_CANARY_7f3a"
MODE_ENV = "LEGALFORECAST_FAKE_CODEX_MODE"
MODES = {
    "invalid_json",
    "mixed_output",
    "model_drift",
    "nonzero",
    "partial_result",
    "resume_mismatch",
    "secret_canary",
    "success",
    "timeout",
    "tool_request",
}


def main(argv: list[str] | None = None) -> int:
    """Run the intentionally small supported subset of the Codex CLI."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    mode = os.environ.get(MODE_ENV, "success")
    if mode not in MODES:
        return _usage_error("unsupported mode")

    if arguments in (["--version"], ["-V"]):
        print(DRIFT_VERSION if mode == "model_drift" else FAKE_VERSION)
        return 0
    if not arguments or arguments[0] != "exec" or "--json" not in arguments:
        return _usage_error("unsupported invocation")

    is_resume = len(arguments) > 1 and arguments[1] == "resume"
    if mode == "resume_mismatch" and not is_resume:
        return _usage_error("resume_mismatch requires exec resume")

    requested_model = _option_value(arguments, "--model", "-m")
    output_path = _option_value(arguments, "--output-last-message", "-o")
    _consume_prompt(arguments)

    started: dict[str, Any] = {"type": "thread.started", "thread_id": THREAD_ID}
    if mode == "model_drift":
        started.update(
            requested_model=requested_model,
            actual_model="unexpected-model",
        )
    _emit(started)
    _emit({"type": "turn.started"})

    if mode == "timeout":
        time.sleep(3600)
        return 70
    if mode == "invalid_json":
        print('{"type":', flush=True)
        return 0
    if mode == "mixed_output":
        print("non-json output on the JSONL stream", flush=True)
        return 0
    if mode == "resume_mismatch":
        return _fail("resume identity mismatch", 18)
    if mode == "nonzero":
        return _fail("fake provider failure", 17)
    if mode == "tool_request":
        _emit_tool_request()

    final_message = SECRET_CANARY if mode == "secret_canary" else RESULT
    _emit_agent_message(final_message)
    if output_path is not None:
        Path(output_path).write_text(f"{final_message}\n", encoding="utf-8")
    if mode == "partial_result":
        return 0

    _emit(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 3,
                "cached_input_tokens": 0,
                "output_tokens": 4,
            },
        }
    )
    return 0


def _usage_error(message: str) -> int:
    print(f"fake codex: {message}", file=sys.stderr)
    return 64


def _option_value(arguments: list[str], *names: str) -> str | None:
    for name in names:
        try:
            position = arguments.index(name)
        except ValueError:
            continue
        if position + 1 >= len(arguments):
            return None
        return arguments[position + 1]
    return None


def _consume_prompt(arguments: list[str]) -> str:
    if "-" in arguments or arguments[-1] in {"exec", "--json"}:
        return sys.stdin.read()
    return arguments[-1]


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)


def _emit_agent_message(text: str) -> None:
    _emit(
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": text},
        }
    )


def _emit_tool_request() -> None:
    started = {
        "id": "item_tool_0",
        "type": "command_execution",
        "command": "printf fixture",
        "status": "in_progress",
    }
    _emit({"type": "item.started", "item": started})
    completed = {
        **started,
        "status": "completed",
        "aggregated_output": "fixture",
        "exit_code": 0,
    }
    _emit({"type": "item.completed", "item": completed})


def _fail(message: str, returncode: int) -> int:
    _emit({"type": "error", "message": message})
    _emit({"type": "turn.failed", "error": {"message": message}})
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())

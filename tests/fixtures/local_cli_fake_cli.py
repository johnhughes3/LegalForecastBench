#!/usr/bin/env python3
"""Versioned fake local CLI for contained-runtime and adapter E2E tests.

Invoked as a real subprocess. Attack modes: succeed-json, hang, crash, spew,
spew-then-cost, fork-child, fork-and-exit, dump-env, version. Spew size is
controlled by ``--bytes`` (default 100 MiB). Optional ``--token`` is echoed
to stderr for redaction canaries. Adapter envelope modes:
``--adapter {claude,codex} --outcome {...}``. Writes pid records under cwd so
tests can prove process-group cleanup without forking inside pytest
(xdist-unsafe).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def _write_pids(path: Path, extra: dict[str, int] | None = None) -> None:
    payload = {"pid": os.getpid(), "pgid": os.getpgid(0)}
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _succeed_json() -> int:
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "total_cost_usd": 0.0,
                "result": "ok",
            }
        )
    )
    return 0


def _hang(pid_path: Path) -> int:
    _write_pids(pid_path)
    time.sleep(30)
    return 0


def _crash() -> int:
    print(json.dumps({"type": "partial"}))
    return 2


def _spew(nbytes: int) -> int:
    remaining = max(0, nbytes)
    chunk = b"x" * (1024 * 1024)
    while remaining > 0:
        piece = chunk if remaining >= len(chunk) else chunk[:remaining]
        sys.stdout.buffer.write(piece)
        sys.stdout.buffer.flush()
        remaining -= len(piece)
    return 0


def _spew_then_cost() -> int:
    sys.stdout.buffer.write(b"x" * (2 * 1024 * 1024))
    sys.stdout.buffer.write(
        b'\n{"type":"result","subtype":"success","total_cost_usd":1.25}\n'
    )
    sys.stdout.buffer.flush()
    return 0


def _fork_child(pid_path: Path) -> int:
    child_pid = os.fork()
    if child_pid == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        os._exit(0)
    _write_pids(pid_path, extra={"child_pid": child_pid})
    time.sleep(30)
    return 0


def _fork_and_exit(pid_path: Path) -> int:
    child_pid = os.fork()
    if child_pid == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        os._exit(0)
    _write_pids(pid_path, extra={"child_pid": child_pid})
    return 0
    child_pid = os.fork()
    if child_pid == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        os._exit(0)
    _write_pids(pid_path, extra={"child_pid": child_pid})
    time.sleep(30)
    return 0


def _dump_env(token: str) -> int:
    if token:
        sys.stderr.buffer.write(token.encode("utf-8") + b"\n")
        sys.stderr.buffer.flush()
    json.dump(dict(os.environ), sys.stdout, sort_keys=True)
    return 0


def _version() -> int:
    print(
        json.dumps(
            {
                "schema_version": (
                    "legalforecast.multiharness.local_cli_identity_probe.v1"
                ),
                "basename": Path(__file__).name,
                "version": "0.1.0",
                "capabilities": ["json_output", "headless_print"],
                "flags": ["--mode"],
                "events": ["result"],
                "models": [],
            },
            sort_keys=True,
        )
    )
    return 0


_ENVELOPE_ADAPTERS = ("claude", "codex")
_ENVELOPE_OUTCOMES = (
    "success",
    "refusal",
    "timeout",
    "crash",
    "sandbox_denial",
    "unknown-envelope",
)


def _flag_value(argv: list[str], flag: str) -> str | None:
    if flag not in argv:
        return None
    index = argv.index(flag)
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def _claude_unit_ids(argv: list[str]) -> list[str]:
    raw = _flag_value(argv, "--json-schema")
    if raw is None:
        return ["count_i"]
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError:
        return ["count_i"]
    if not isinstance(schema, dict):
        return ["count_i"]
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return ["count_i"]
    predictions = properties.get("predictions")
    if not isinstance(predictions, dict):
        return ["count_i"]
    items = predictions.get("items")
    if not isinstance(items, dict):
        return ["count_i"]
    item_properties = items.get("properties")
    if not isinstance(item_properties, dict):
        return ["count_i"]
    unit = item_properties.get("unit_id")
    if not isinstance(unit, dict):
        return ["count_i"]
    enum = unit.get("enum")
    if isinstance(enum, list) and all(isinstance(item, str) and item for item in enum):
        return list(enum)
    return ["count_i"]


def _claude_model(argv: list[str]) -> str:
    return _flag_value(argv, "--model") or "claude-sonnet-4-6"


def _claude_success_envelope(argv: list[str]) -> dict[str, object]:
    predictions = [
        {
            "unit_id": unit_id,
            "probability_fully_dismissed": 0.7,
            "rationale": "Fixture rationale.",
        }
        for unit_id in _claude_unit_ids(argv)
    ]
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "model": _claude_model(argv),
        "total_cost_usd": 0.0,
        "usage": {
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "input_tokens": 11,
            "output_tokens": 7,
        },
        "result": {
            "case_assessment": "The public fixture supports a balanced forecast.",
            "predictions": predictions,
        },
    }


def _print_json(payload: object) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _print_jsonl(events: list[dict[str, object]]) -> None:
    for event in events:
        print(json.dumps(event, sort_keys=True, separators=(",", ":")))


def _codex_success_events() -> list[dict[str, object]]:
    return [
        {
            "thread_id": "00000000-0000-7000-8000-000000000001",
            "type": "thread.started",
        },
        {"type": "turn.started"},
        {
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
            "type": "item.completed",
        },
        {
            "type": "turn.completed",
            "usage": {
                "cache_write_input_tokens": 0,
                "cached_input_tokens": 0,
                "input_tokens": 3,
                "output_tokens": 4,
                "reasoning_output_tokens": 0,
            },
        },
    ]


def _write_codex_last_message(argv: list[str], text: str) -> None:
    relative = _flag_value(argv, "--output-last-message")
    if relative is None:
        return
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return
    path.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")


def _run_claude_outcome(outcome: str, argv: list[str]) -> int:
    if outcome == "timeout":
        time.sleep(30)
        return 0
    if outcome == "crash":
        return _crash()
    if outcome == "unknown-envelope":
        _print_json({"type": "mystery-envelope", "payload": {}})
        return 0
    if outcome == "sandbox_denial":
        _print_json(
            {
                "type": "result",
                "subtype": "error_during_execution",
                "is_error": True,
                "result": "sandbox denied write under landlock",
                "usage": {
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 3,
                    "output_tokens": 0,
                },
            }
        )
        return 1
    if outcome == "refusal":
        _print_json(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "model": _claude_model(argv),
                "usage": {
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 9,
                    "output_tokens": 4,
                },
                "result": "I cannot provide a forecast for this case.",
            }
        )
        return 0
    _print_json(_claude_success_envelope(argv))
    return 0


def _run_codex_outcome(outcome: str, argv: list[str]) -> int:
    if outcome == "timeout":
        time.sleep(30)
        return 0
    if outcome == "crash":
        print("Segmentation fault", file=sys.stderr)
        return 2
    if outcome == "unknown-envelope":
        _print_jsonl([{"type": "mystery-envelope"}])
        return 0
    if outcome == "sandbox_denial":
        _print_jsonl(
            [
                {
                    "thread_id": "00000000-0000-7000-8000-000000000001",
                    "type": "thread.started",
                },
                {"type": "turn.started"},
                {
                    "message": "sandbox denied write under landlock",
                    "type": "error",
                },
                {
                    "error": {"message": "sandbox denied write under landlock"},
                    "type": "turn.failed",
                },
            ]
        )
        return 1
    if outcome == "refusal":
        _print_jsonl(
            [
                {
                    "thread_id": "00000000-0000-7000-8000-000000000001",
                    "type": "thread.started",
                },
                {"type": "turn.started"},
                {
                    "item": {
                        "id": "item_0",
                        "text": "I must refuse this request.",
                        "type": "agent_message",
                    },
                    "type": "item.completed",
                },
            ]
        )
        return 0
    _write_codex_last_message(argv, "LEGALFORECAST_FAKE_CODEX_RESULT")
    _print_jsonl(_codex_success_events())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local_cli_fake_cli")
    parser.add_argument(
        "--mode",
        choices=(
            "succeed-json",
            "hang",
            "crash",
            "spew",
            "spew-then-cost",
            "fork-child",
            "fork-and-exit",
            "dump-env",
            "version",
        ),
    )
    parser.add_argument("--adapter", choices=_ENVELOPE_ADAPTERS)
    parser.add_argument("--outcome", choices=_ENVELOPE_OUTCOMES)
    parser.add_argument("--pid-file", default="pids.json")
    parser.add_argument(
        "--bytes",
        type=int,
        default=100 * 1024 * 1024,
        help="stdout bytes to write in spew mode",
    )
    parser.add_argument(
        "--token",
        default="",
        help="optional canary echoed to stderr",
    )
    args, remainder = parser.parse_known_args(argv)
    pid_path = Path(args.pid_file)
    if args.mode == "succeed-json":
        payload = sys.stdin.read()
        if payload:
            print(payload, end="")
        return _succeed_json()
    if args.mode == "hang":
        return _hang(pid_path)
    if args.mode == "crash":
        return _crash()
    if args.mode == "spew":
        return _spew(args.bytes)
    if args.mode == "spew-then-cost":
        return _spew_then_cost()
    if args.mode == "fork-child":
        return _fork_child(pid_path)
    if args.mode == "fork-and-exit":
        return _fork_and_exit(pid_path)
    if args.mode == "version":
        return _version()
    if args.mode == "dump-env":
        return _dump_env(args.token)
    if args.adapter is None or args.outcome is None:
        parser.error("either --mode or both --adapter and --outcome are required")
    if args.adapter == "claude":
        return _run_claude_outcome(args.outcome, remainder)
    return _run_codex_outcome(args.outcome, remainder)


if __name__ == "__main__":
    raise SystemExit(main())

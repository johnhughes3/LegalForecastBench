#!/usr/bin/env python3
"""Versioned fake local CLI for contained-runtime attack tests.

Invoked as a real subprocess. Modes: succeed-json, hang, crash, spew,
spew-then-cost, fork-child, fork-and-exit, dump-env, version. Writes pid
records under cwd so tests can prove process-group cleanup without forking
inside pytest (xdist-unsafe).
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


def _spew() -> int:
    chunk = b"x" * 1024 * 1024
    for _ in range(100):
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
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


def _dump_env() -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local_cli_fake_cli")
    parser.add_argument(
        "--mode",
        required=True,
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
    parser.add_argument("--pid-file", default="pids.json")
    args = parser.parse_args(argv)
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
        return _spew()
    if args.mode == "spew-then-cost":
        return _spew_then_cost()
    if args.mode == "fork-child":
        return _fork_child(pid_path)
    if args.mode == "fork-and-exit":
        return _fork_and_exit(pid_path)
    if args.mode == "version":
        return _version()
    return _dump_env()


if __name__ == "__main__":
    raise SystemExit(main())

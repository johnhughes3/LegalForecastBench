"""Recover an Infisical-wrapped child's exit status for systemd."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

CHILD_RECEIPT_SCHEMA: Final = "legalforecast.infisical_child_status.v1"
LAUNCH_RECEIPT_SCHEMA: Final = "legalforecast.infisical_systemd_launch.v1"
EXIT_USAGE: Final = 64
EXIT_MISSING_CHILD_RECEIPT: Final = 70
EXIT_OUTPUT_ERROR: Final = 74
_NONCE_HEX_LENGTH: Final = 64
_ALLOWED_SANDBOX_PATHS: Final = frozenset(
    {
        "/agents/sandbox/legalforecastbench-acquisition",
        "/agents/sandbox/legalforecastbench/parser",
        "/agents/sandbox/legalforecastbench/labeling",
    }
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_returncode(returncode: int) -> int:
    if returncode >= 0:
        return min(returncode, 255)
    return min(128 + abs(returncode), 255)


def _command_sha256(command: Sequence[str]) -> str:
    encoded = json.dumps(
        list(command),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _valid_nonce(value: str) -> bool:
    return len(value) == _NONCE_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in value
    )


def _run_recording_child(
    *,
    receipt: Path,
    nonce: str,
    command: Sequence[str],
) -> int:
    if not _valid_nonce(nonce) or not command:
        return EXIT_USAGE
    try:
        completed = subprocess.run(list(command), check=False)
        child_exit_status = _normalize_returncode(completed.returncode)
    except FileNotFoundError:
        child_exit_status = 127
    except PermissionError:
        child_exit_status = 126
    _atomic_write_json(
        receipt,
        {
            "schema": CHILD_RECEIPT_SCHEMA,
            "nonce": nonce,
            "child_exit_status": child_exit_status,
            "recorded_at": _utc_now(),
        },
    )
    return child_exit_status


def _read_child_status(receipt: Path, nonce: str) -> int | None:
    try:
        decoded = cast(object, json.loads(receipt.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    payload = cast(dict[str, object], decoded)
    if payload.get("schema") != CHILD_RECEIPT_SCHEMA:
        return None
    if payload.get("nonce") != nonce:
        return None
    status = payload.get("child_exit_status")
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    if not 0 <= status <= 255:
        return None
    return status


def _run_infisical_launcher(
    *,
    sandbox_path: str,
    receipt_output: Path,
    command: Sequence[str],
) -> int:
    if sandbox_path not in _ALLOWED_SANDBOX_PATHS or not command:
        return EXIT_USAGE

    nonce = secrets.token_hex(_NONCE_HEX_LENGTH // 2)
    started_at = _utc_now()
    with tempfile.TemporaryDirectory(
        prefix="legalforecast-infisical-status-"
    ) as temporary_directory:
        child_receipt = Path(temporary_directory) / "child-status.json"
        sandbox_command = [
            "infisical-agent-sandbox",
            "run",
            "--path",
            sandbox_path,
            "--",
            sys.executable,
            "-m",
            "legalforecast.ingestion.infisical_systemd_launcher",
            "_record-child-status",
            "--receipt",
            str(child_receipt),
            "--nonce",
            nonce,
            "--",
            *command,
        ]
        try:
            sandbox_process = subprocess.run(sandbox_command, check=False)
            sandbox_exit_status = _normalize_returncode(sandbox_process.returncode)
        except FileNotFoundError:
            sandbox_exit_status = 127
        except PermissionError:
            sandbox_exit_status = 126
        child_exit_status = _read_child_status(child_receipt, nonce)

    child_receipt_observed = child_exit_status is not None
    if child_exit_status is not None and child_exit_status != 0:
        effective_exit_status = child_exit_status
    elif sandbox_exit_status != 0:
        effective_exit_status = sandbox_exit_status
    elif child_exit_status == 0:
        effective_exit_status = 0
    else:
        effective_exit_status = EXIT_MISSING_CHILD_RECEIPT

    launch_receipt: dict[str, object] = {
        "schema": LAUNCH_RECEIPT_SCHEMA,
        "sandbox_path": sandbox_path,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "command_sha256": _command_sha256(command),
        "child_receipt_observed": child_receipt_observed,
        "child_exit_status": child_exit_status,
        "sandbox_exit_status": sandbox_exit_status,
        "sandbox_failure_observed": sandbox_exit_status != 0,
        "effective_exit_status": effective_exit_status,
        "sandbox_status_was_masked": (
            child_exit_status is not None
            and child_exit_status != 0
            and sandbox_exit_status == 0
        ),
    }
    try:
        _atomic_write_json(receipt_output, launch_receipt)
    except OSError:
        return EXIT_OUTPUT_ERROR
    return effective_exit_status


def _child_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def _launcher_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run an acquisition command through infisical-agent-sandbox while "
            "recovering the wrapped child's exact exit status for systemd."
        )
    )
    parser.add_argument(
        "--sandbox-path",
        required=True,
        help="Narrow Infisical path at or below /agents/sandbox.",
    )
    parser.add_argument(
        "--receipt-output",
        required=True,
        type=Path,
        help=(
            "Secret-free JSON launch receipt. Downstream launchers must verify "
            "effective_exit_status and child_receipt_observed."
        ),
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def _command_after_separator(command: Sequence[str]) -> list[str]:
    result = list(command)
    if result and result[0] == "--":
        result = result[1:]
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run the private child recorder or the public systemd-safe launcher."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "_record-child-status":
        parsed = _child_parser().parse_args(arguments[1:])
        return _run_recording_child(
            receipt=parsed.receipt,
            nonce=parsed.nonce,
            command=_command_after_separator(parsed.command),
        )

    parsed = _launcher_parser().parse_args(arguments)
    return _run_infisical_launcher(
        sandbox_path=parsed.sandbox_path,
        receipt_output=parsed.receipt_output,
        command=_command_after_separator(parsed.command),
    )


if __name__ == "__main__":
    raise SystemExit(main())

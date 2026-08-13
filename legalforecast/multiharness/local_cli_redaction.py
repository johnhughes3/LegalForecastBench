"""Blessed redaction path for local CLI transcripts, events, and errors.

Every persisted execution artifact and public diagnostic goes through this
module. In-memory private stdout/stderr returned to adapters stay raw so
parsers can read provider envelopes; disk bytes do not.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path

from legalforecast.multiharness.local_cli_environment import (
    ensure_private_scratch_directory,
)
from legalforecast.multiharness.validation import SECRET_FIELD_PATTERN

REDACTED = "[redacted]"
PRIVATE_EXECUTION_DIR = "private-execution"
_SKIP_ENV_NAMES = frozenset(
    {
        "HOME",
        "LC_CTYPE",
        "LOGNAME",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
    }
)
_MIN_ARG_SECRET_LENGTH = 16


class LocalCliRedactionError(RuntimeError):
    """Raised when redacted artifacts cannot be written fail-closed."""


def redaction_secret_values(
    *,
    projected: Mapping[str, str],
    parent_env: Mapping[str, str],
    extra_args: Sequence[str] = (),
) -> tuple[str, ...]:
    """Collect exact values that must never appear in persisted bytes."""

    values: set[str] = {value for value in projected.values() if value}
    for name, value in parent_env.items():
        if not value or name in _SKIP_ENV_NAMES:
            continue
        if SECRET_FIELD_PATTERN.search(name) is not None or name.startswith("CANARY"):
            values.add(value)
    values.update(_arg_secret_values(extra_args))
    return tuple(sorted(values, key=len, reverse=True))


def _arg_secret_values(extra_args: Sequence[str]) -> set[str]:
    values: set[str] = set()
    for arg in extra_args:
        if arg.startswith("-"):
            _, separator, assigned = arg.partition("=")
            if separator and len(assigned) >= _MIN_ARG_SECRET_LENGTH:
                values.add(assigned)
            continue
        if len(arg) >= _MIN_ARG_SECRET_LENGTH:
            values.add(arg)
    return values


def redact_text(text: str, secret_values: Sequence[str]) -> str:
    """Replace every exact secret occurrence in a diagnostic string."""

    redacted = text
    for secret in secret_values:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    return redacted


def redact_bytes(payload: bytes, secret_values: Sequence[str]) -> bytes:
    """Replace every exact secret occurrence in persisted transcript bytes."""

    redacted = payload
    for secret in secret_values:
        if not secret:
            continue
        encoded = secret.encode("utf-8")
        if encoded:
            redacted = redacted.replace(encoded, REDACTED.encode("utf-8"))
    return redacted


def redact_json_record(
    record: Mapping[str, object],
    secret_values: Sequence[str],
) -> dict[str, object]:
    """Dump-and-reload a record so nested secret strings are rewritten."""

    encoded = json.dumps(dict(record), ensure_ascii=False, sort_keys=True)
    return dict(json.loads(redact_text(encoded, secret_values)))


def persist_execution_artifacts(
    scratch_root: Path,
    *,
    receipt: Mapping[str, object],
    argv: Sequence[str],
    stdout: bytes,
    stderr: bytes,
    secret_values: Sequence[str],
    error_message: str | None = None,
) -> Path:
    """Write redacted receipt, event log, and transcripts under scratch."""

    ensure_private_scratch_directory(scratch_root)
    artifact_dir = _ensure_private_artifact_dir(scratch_root)
    receipt_bytes = (
        json.dumps(redact_json_record(receipt, secret_values), sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_private_bytes(artifact_dir / "receipt.json", receipt_bytes)
    event = redact_json_record(
        {
            "event": "launch",
            "argv": list(argv),
        },
        secret_values,
    )
    event_line = json.dumps(event, sort_keys=True) + "\n"
    _write_private_bytes(
        artifact_dir / "events.jsonl",
        event_line.encode("utf-8"),
    )
    _write_private_bytes(
        artifact_dir / "stdout.transcript",
        redact_bytes(stdout, secret_values),
    )
    _write_private_bytes(
        artifact_dir / "stderr.transcript",
        redact_bytes(stderr, secret_values),
    )
    if error_message is not None:
        _write_private_bytes(
            artifact_dir / "error.txt",
            (redact_text(error_message, secret_values) + "\n").encode("utf-8"),
        )
    return artifact_dir


def artifact_dir_contains_secret(root: Path, secret: str) -> bool:
    """Return whether any file under ``root`` contains the exact secret bytes."""

    if not secret:
        return False
    encoded = secret.encode("utf-8")
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if encoded in path.read_bytes():
            return True
    return False


def _ensure_private_artifact_dir(scratch_root: Path) -> Path:
    artifact_dir = scratch_root / PRIVATE_EXECUTION_DIR
    if artifact_dir.is_symlink():
        raise LocalCliRedactionError("CLI scratch paths must not be symlinks")
    artifact_dir.mkdir(mode=0o700, exist_ok=True)
    if artifact_dir.is_symlink() or not artifact_dir.is_dir():
        raise LocalCliRedactionError("CLI scratch paths must be directories")
    artifact_dir.chmod(0o700)
    return artifact_dir


def _write_private_bytes(path: Path, payload: bytes) -> None:
    try:
        path_info = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(path_info.st_mode):
            raise LocalCliRedactionError("private execution paths must not be symlinks")
        if not stat.S_ISREG(path_info.st_mode):
            raise LocalCliRedactionError(
                "private execution paths must be regular files"
            )
        try:
            path.unlink()
        except OSError as exc:
            raise LocalCliRedactionError(
                "private execution path could not be replaced"
            ) from exc

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        file_descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise LocalCliRedactionError(
            "private execution path could not be created"
        ) from exc
    try:
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = -1
            handle.write(payload)
            handle.flush()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)

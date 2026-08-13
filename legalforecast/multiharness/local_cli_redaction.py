"""Blessed redaction path for local CLI transcripts, events, and errors.

Every persisted execution artifact and public diagnostic goes through this
module. In-memory private stdout/stderr returned to adapters stay raw so
parsers can read provider envelopes; disk bytes do not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

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
    for arg in extra_args:
        if arg.startswith("-") or len(arg) < _MIN_ARG_SECRET_LENGTH:
            continue
        values.add(arg)
    return tuple(sorted(values, key=len, reverse=True))


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

    artifact_dir = scratch_root / PRIVATE_EXECUTION_DIR
    artifact_dir.mkdir(parents=True, exist_ok=True)
    receipt_bytes = (
        json.dumps(redact_json_record(receipt, secret_values), sort_keys=True) + "\n"
    ).encode("utf-8")
    (artifact_dir / "receipt.json").write_bytes(receipt_bytes)
    event = redact_json_record(
        {
            "event": "launch",
            "argv": list(argv),
        },
        secret_values,
    )
    event_line = json.dumps(event, sort_keys=True) + "\n"
    (artifact_dir / "events.jsonl").write_text(event_line, encoding="utf-8")
    (artifact_dir / "stdout.transcript").write_bytes(
        redact_bytes(stdout, secret_values)
    )
    (artifact_dir / "stderr.transcript").write_bytes(
        redact_bytes(stderr, secret_values)
    )
    if error_message is not None:
        (artifact_dir / "error.txt").write_text(
            redact_text(error_message, secret_values) + "\n",
            encoding="utf-8",
        )
    return artifact_dir


def artifact_dir_contains_secret(root: Path, secret: str) -> bool:
    """Return whether any file under ``root`` contains the exact secret bytes."""

    if not secret:
        return False
    encoded = secret.encode("utf-8")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if encoded in path.read_bytes():
            return True
    return False

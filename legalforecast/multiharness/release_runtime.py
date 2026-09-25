"""Shared file and record primitives for the release harness."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import FORECAST_RELEASE_V1, RAW_BYTES_PREFIXED_SHA256_V1
from legalforecast.immutable_io import (
    ImmutableIOError,
    read_single_link_file,
    write_file_create_only,
)


class ReleaseHarnessError(ValueError):
    """Raised when release-backed harness data violates its protocol."""


def read_release_regular_file(path: Path) -> bytes:
    """Read one immutable single-link file without following any symlink."""

    try:
        return read_single_link_file(path, label="release harness input")
    except ImmutableIOError as exc:
        raise ReleaseHarnessError("release harness input is unavailable") from exc


def write_release_create_only(path: Path, payload: bytes, *, mode: int) -> None:
    try:
        write_file_create_only(path, payload, mode=mode)
    except ImmutableIOError as exc:
        raise ReleaseHarnessError(
            "release harness staging path is unavailable"
        ) from exc


def write_release_json_create_only(path: Path, record: Mapping[str, Any]) -> None:
    """Write one canonical release-runtime record without following links."""

    write_release_create_only(path, release_canonical_bytes(record), mode=0o600)


def release_canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(record), sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def release_record_sha256(record: Mapping[str, Any]) -> str:
    return release_bytes_sha256(release_canonical_bytes(record))


def release_bytes_sha256(payload: bytes) -> str:
    commitment = RAW_BYTES_PREFIXED_SHA256_V1.commit(
        payload,
        domain=FORECAST_RELEASE_V1,
    )
    return str(commitment.digest)


def read_release_object(path: Path, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(read_release_regular_file(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseHarnessError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ReleaseHarnessError(f"{label} must be an object")
    return cast(dict[str, Any], decoded)

"""Internal JSON and JSONL object I/O helpers."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.immutable_io import (
    ImmutableIOError,
    read_single_link_file,
    write_file_replace_safe,
)

JsonRecord = dict[str, Any]
ErrorFactory = Callable[[str], Exception]


def read_json_object(
    path: Path,
    *,
    error_factory: ErrorFactory,
    missing_message: Callable[[Path], str],
    non_object_message: Callable[[Path], str],
) -> JsonRecord:
    """Read a JSON object from path with caller-provided error messages."""
    if not path.is_file():
        raise error_factory(missing_message(path))
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise error_factory(non_object_message(path))
    return cast(JsonRecord, value)


def read_jsonl_objects(
    path: Path,
    *,
    error_factory: ErrorFactory,
    missing_message: Callable[[Path], str],
    non_object_message: Callable[[Path, int], str],
) -> list[JsonRecord]:
    """Read JSONL object records from path with caller-provided error messages."""
    if not path.is_file():
        raise error_factory(missing_message(path))
    records: list[JsonRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise error_factory(non_object_message(path, line_number))
            records.append(cast(JsonRecord, value))
    return records


def write_json_object(
    path: Path,
    payload: Mapping[str, Any],
    *,
    indent: int = 2,
    sort_keys: bool = True,
    trailing_newline: bool = True,
) -> None:
    """Write a JSON object using stable formatting options."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=indent, sort_keys=sort_keys)
    if trailing_newline:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_jsonl_objects(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    sort_keys: bool = True,
) -> None:
    """Write JSONL object records using stable formatting options."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(dict(record), sort_keys=sort_keys) + "\n" for record in records
        ),
        encoding="utf-8",
    )


def read_json_object_safe(
    path: Path,
    *,
    error_factory: ErrorFactory,
    missing_message: Callable[[Path], str],
    non_object_message: Callable[[Path], str],
) -> JsonRecord:
    """Read one JSON object without following a symlink or hardlink."""

    try:
        payload = read_single_link_file(path, label="JSON object")
        value: object = json.loads(payload.decode("utf-8"))
    except (ImmutableIOError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise error_factory(missing_message(path)) from exc
    if not isinstance(value, dict):
        raise error_factory(non_object_message(path))
    return cast(JsonRecord, value)


def write_json_object_safe(
    path: Path,
    payload: Mapping[str, Any],
    *,
    indent: int = 2,
    sort_keys: bool = True,
    trailing_newline: bool = True,
) -> None:
    """Write JSON through an anchored, no-follow owner-controlled file."""

    text = json.dumps(payload, indent=indent, sort_keys=sort_keys)
    if trailing_newline:
        text += "\n"
    write_file_replace_safe(path, text.encode("utf-8"))


def write_jsonl_objects_safe(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    sort_keys: bool = True,
) -> None:
    """Write JSONL through an anchored, no-follow owner-controlled file."""

    payload = "".join(
        json.dumps(dict(record), sort_keys=sort_keys) + "\n" for record in records
    )
    write_file_replace_safe(path, payload.encode("utf-8"))

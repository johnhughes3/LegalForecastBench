"""Canonical JSON serialization shared by ingestion trust boundaries."""

from __future__ import annotations

import json


def canonical_json_bytes(
    value: object,
    *,
    error_type: type[ValueError],
    error_message: str,
) -> bytes:
    """Serialize *value* canonically, mapping failures to a domain error."""

    return (
        canonical_json_value_bytes(
            value,
            error_type=error_type,
            error_message=error_message,
        )
        + b"\n"
    )


def canonical_json_value_bytes(
    value: object,
    *,
    error_type: type[ValueError],
    error_message: str,
) -> bytes:
    """Serialize one JSON value canonically without an artifact newline."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise error_type(error_message) from exc

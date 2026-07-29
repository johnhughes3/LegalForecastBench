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

    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return (serialized + "\n").encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise error_type(error_message) from exc

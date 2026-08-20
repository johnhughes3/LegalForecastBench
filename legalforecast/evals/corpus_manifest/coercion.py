"""JSON coercion helpers for the corpus manifest schema.

Each helper states the exact shape it will accept and raises
``CorpusManifestError`` otherwise, so a malformed manifest fails at the field
that is wrong rather than somewhere downstream.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.ingestion.provenance import DocumentRole


class CorpusManifestError(ValueError):
    """Raised when a corpus manifest is malformed, unbound, or unsafe."""


def document_role(record: Mapping[str, Any]) -> DocumentRole:
    raw = required_str(record, "document_role")
    try:
        return DocumentRole(raw)
    except ValueError as exc:
        raise CorpusManifestError(f"unknown document_role: {raw}") from exc


def mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CorpusManifestError("expected a JSON object")
    return cast("Mapping[str, Any]", value)


def required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise CorpusManifestError(f"{field_name} is required")
    return value


def optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CorpusManifestError(f"{field_name} must be a non-empty string or null")
    return value


def required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise CorpusManifestError(f"{field_name} must be a boolean")
    return value


def optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise CorpusManifestError(f"{field_name} must be an integer or null")
    return value


def optional_int_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[int, ...]:
    value = record.get(field_name)
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CorpusManifestError(f"{field_name} must be a list of integers")
    entries: list[int] = []
    for item in cast("Sequence[object]", value):
        if not isinstance(item, int) or isinstance(item, bool):
            raise CorpusManifestError(f"{field_name} must be a list of integers")
        entries.append(item)
    return tuple(entries)


def optional_str_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    value = record.get(field_name)
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CorpusManifestError(f"{field_name} must be a list of strings")
    entries: list[str] = []
    for item in cast("Sequence[object]", value):
        if not isinstance(item, str) or not item.strip():
            raise CorpusManifestError(f"{field_name} must be a list of strings")
        entries.append(item)
    return tuple(entries)


def require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise CorpusManifestError(f"{field_name} is required")


def require_digest(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise CorpusManifestError(
            f"{field_name} must be 64 lowercase hexadecimal characters"
        )

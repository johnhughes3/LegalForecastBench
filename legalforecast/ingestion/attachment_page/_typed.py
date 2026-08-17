"""Narrow validators for reading attachment-menu artifacts back from disk.

Artifacts arrive as untyped JSON. These helpers turn each field into a typed
value or a domain error, so a malformed artifact fails at its first bad field
rather than somewhere downstream holding a charge-bearing decision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar, cast

_ErrorT = TypeVar("_ErrorT", bound=ValueError)


def mapping(
    value: object, label: str, *, error: type[ValueError]
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise error(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def sequence(value: object, label: str, *, error: type[ValueError]) -> Sequence[object]:
    if not isinstance(value, list):
        raise error(f"{label} must be an array")
    return cast(Sequence[object], value)


def text(value: object, label: str, *, error: type[ValueError]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error(f"{label} must be a nonempty string")
    return value


def optional_text(value: object, label: str, *, error: type[ValueError]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise error(f"{label} must be a string when present")
    return value


def integer(value: object, label: str, *, error: type[ValueError]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error(f"{label} must be an integer")
    return value

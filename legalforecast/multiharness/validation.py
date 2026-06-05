"""Validation helpers for multi-harness public schemas."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any, cast

from legalforecast._hashing import is_sha256_digest

DEPRECATED_RESULT_TIER_FIELDS = frozenset(
    {
        "result_tier",
        "tier",
    }
)
DEPRECATED_RESULT_TIER_VALUES = frozenset(
    {
        "official",
        "verified-community",
        "community-unverified",
        "alpha-non-canonical",
        "private-debug",
    }
)
SECRET_FIELD_PATTERN = re.compile(
    r"(?:api[_-]?key|secret|access[_-]?token|authorization|password|credential)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*Bearer\s+\S+")),
    ("api_key_assignment", re.compile(r"\bapi[_-]?key\s*[:=]\s*\S{8,}", re.I)),
    ("secret_assignment", re.compile(r"\bsecret\s*[:=]\s*\S{8,}", re.I)),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)
PROVIDER_ACCOUNT_FIELD_PATTERN = re.compile(
    r"(?:provider[_-]?account[_-]?id|organization[_-]?id|org[_-]?id)",
    re.IGNORECASE,
)
ENV_VAR_NAME_PATTERN = re.compile(r"[A-Z_][A-Z0-9_]*")


class MultiHarnessValidationError(ValueError):
    """Raised when a multi-harness schema record is invalid."""


def require_mapping(record: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    """Return a required nested mapping field."""

    value = record.get(field_name)
    if not isinstance(value, Mapping):
        raise MultiHarnessValidationError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def optional_mapping(
    record: Mapping[str, Any], field_name: str
) -> Mapping[str, Any] | None:
    """Return an optional nested mapping field."""

    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise MultiHarnessValidationError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def require_sequence(record: Mapping[str, Any], field_name: str) -> Sequence[Any]:
    """Return a required JSON array field."""

    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise MultiHarnessValidationError(f"{field_name} must be an array")
    return cast(Sequence[Any], value)


def optional_sequence(
    record: Mapping[str, Any], field_name: str
) -> Sequence[Any] | None:
    """Return an optional JSON array field."""

    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise MultiHarnessValidationError(f"{field_name} must be an array")
    return cast(Sequence[Any], value)


def require_str(record: Mapping[str, Any], field_name: str) -> str:
    """Return a required non-empty string field."""

    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MultiHarnessValidationError(f"{field_name} must be a non-empty string")
    return value


def optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    """Return an optional non-empty string field."""

    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise MultiHarnessValidationError(f"{field_name} must be a non-empty string")
    return value


def optional_bool(record: Mapping[str, Any], field_name: str) -> bool:
    """Return an optional boolean field, defaulting to False."""

    value = record.get(field_name, False)
    if not isinstance(value, bool):
        raise MultiHarnessValidationError(f"{field_name} must be a boolean")
    return value


def optional_non_negative_int(record: Mapping[str, Any], field_name: str) -> int | None:
    """Return an optional non-negative integer field."""

    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MultiHarnessValidationError(
            f"{field_name} must be a non-negative integer"
        )
    return value


def require_schema_version(
    record: Mapping[str, Any],
    expected_version: str,
    *,
    field_name: str = "schema_version",
) -> None:
    """Require that a JSON-like record has the expected schema version."""

    actual_version = require_str(record, field_name)
    if actual_version != expected_version:
        raise MultiHarnessValidationError(
            f"{field_name} must be {expected_version!r}, got {actual_version!r}"
        )


def validate_sha256(value: str, field_name: str, *, allow_prefix: bool = True) -> str:
    """Validate and return a SHA-256 digest."""

    if not is_sha256_digest(value, allow_prefix=allow_prefix):
        prefix = "prefixed " if allow_prefix else ""
        raise MultiHarnessValidationError(
            f"{field_name} must be a lowercase {prefix}SHA-256 digest"
        )
    return value


def validate_safe_relative_path(value: str, field_name: str) -> str:
    """Validate a public relative POSIX path without traversal or hidden segments."""

    if not value.strip():
        raise MultiHarnessValidationError(f"{field_name} must be a non-empty path")
    if "\\" in value:
        raise MultiHarnessValidationError(
            f"{field_name} must use POSIX separators, not backslashes"
        )
    path = PurePosixPath(value)
    if path.is_absolute():
        raise MultiHarnessValidationError(f"{field_name} must be relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise MultiHarnessValidationError(
            f"{field_name} must not contain empty, current, or parent segments"
        )
    if any(part.startswith(".") for part in parts):
        raise MultiHarnessValidationError(
            f"{field_name} must not contain hidden path segments"
        )
    return path.as_posix()


def validate_env_var_names(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    """Validate environment variable names recorded in sandbox/provider policy."""

    env_names = tuple(values)
    for value in env_names:
        if ENV_VAR_NAME_PATTERN.fullmatch(value) is None:
            raise MultiHarnessValidationError(
                f"{field_name} contains invalid environment variable name {value!r}"
            )
    return env_names


def validate_unique_ids(values: Iterable[str], field_name: str) -> None:
    """Require all IDs in an iterable to be unique."""

    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        formatted = ", ".join(sorted(duplicates))
        raise MultiHarnessValidationError(
            f"{field_name} contains duplicate IDs: {formatted}"
        )


def validate_public_record(
    record: Mapping[str, Any], field_name: str = "record"
) -> None:
    """Reject fields that must not appear in public multi-harness records."""

    _scan_public_value(record, field_name)


def _scan_public_value(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, Any], value)
        for raw_key, child_value in mapping.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            _validate_public_key(key, child_path)
            _scan_public_value(child_value, child_path)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        sequence = cast(Sequence[Any], value)
        for index, child_value in enumerate(sequence):
            _scan_public_value(child_value, f"{path}[{index}]")
        return
    if isinstance(value, str):
        _validate_public_string(value, path)


def _validate_public_key(key: str, path: str) -> None:
    normalized = key.strip().lower().replace("_", "-")
    if key.lower() in DEPRECATED_RESULT_TIER_FIELDS:
        raise MultiHarnessValidationError(
            f"{path} uses deprecated result-tier field {key!r}"
        )
    if normalized in DEPRECATED_RESULT_TIER_VALUES:
        raise MultiHarnessValidationError(
            f"{path} uses deprecated result-tier value {key!r}"
        )
    if SECRET_FIELD_PATTERN.search(key) is not None:
        raise MultiHarnessValidationError(f"{path} looks like a secret field")
    if PROVIDER_ACCOUNT_FIELD_PATTERN.search(key) is not None:
        raise MultiHarnessValidationError(f"{path} looks like a provider account field")


def _validate_public_string(value: str, path: str) -> None:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in DEPRECATED_RESULT_TIER_VALUES:
        raise MultiHarnessValidationError(
            f"{path} uses deprecated result-tier value {value!r}"
        )
    for name, pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value) is not None:
            raise MultiHarnessValidationError(
                f"{path} contains secret-like value matching {name}"
            )

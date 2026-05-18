"""Helpers for safely deriving local artifact paths from external IDs."""

from __future__ import annotations

import re
from pathlib import Path

_SAFE_PATH_COMPONENT_RE = re.compile(r"[A-Za-z0-9._-]+")


def safe_path_component(value: str, *, field_name: str) -> str:
    """Return ``value`` only when it is safe as one local path component."""

    if not value:
        raise ValueError(f"{field_name} must be a non-empty path component")
    if value in {".", ".."}:
        raise ValueError(f"{field_name} must not be a relative path component")
    if Path(value).name != value or "\\" in value:
        raise ValueError(f"{field_name} must not contain path separators")
    if _SAFE_PATH_COMPONENT_RE.fullmatch(value) is None:
        raise ValueError(
            f"{field_name} must contain only letters, numbers, dots, underscores, "
            "or hyphens"
        )
    return value

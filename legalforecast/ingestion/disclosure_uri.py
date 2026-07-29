"""Shared URI validation for disclosure provenance boundaries."""

from __future__ import annotations

import re
from urllib.parse import SplitResult, unquote_to_bytes, urlsplit

_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _is_valid_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _validated_urlsplit(value: str) -> tuple[SplitResult, int | None] | None:
    if not _is_valid_utf8(value) or _has_control_character(value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        return parsed, parsed.port
    except ValueError:
        return None


def _has_canonical_path(value: str) -> bool:
    if not _is_valid_utf8(value):
        return False
    if not value:
        return True
    if not value.startswith("/") or "\\" in value or _has_control_character(value):
        return False
    segments = value[1:].split("/")
    if segments and segments[-1] == "":
        segments.pop()
    if any(not segment for segment in segments):
        return False
    for segment in segments:
        if _INVALID_PERCENT_ESCAPE.search(segment):
            return False
        try:
            decoded = unquote_to_bytes(segment).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return False
        if (
            decoded in {".", ".."}
            or "/" in decoded
            or "\\" in decoded
            or _has_control_character(decoded)
        ):
            return False
    return True


def is_allowlisted_public_recap_uri(value: str) -> bool:
    """Return whether *value* is a canonical public RECAP storage URI."""

    parsed_uri = _validated_urlsplit(value)
    if parsed_uri is None:
        return False
    parsed, port = parsed_uri
    return (
        parsed.scheme == "https"
        and parsed.hostname == "storage.courtlistener.com"
        and port is None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith("/recap/")
        and parsed.path != "/recap/"
        and _has_canonical_path(parsed.path)
    )


def is_canonical_private_store_uri(value: str) -> bool:
    """Return whether *value* has canonical controlled-store URI structure."""

    parsed_uri = _validated_urlsplit(value)
    if parsed_uri is None:
        return False
    parsed, port = parsed_uri
    return (
        parsed.scheme == "private-store"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
        and _has_canonical_path(parsed.path)
    )

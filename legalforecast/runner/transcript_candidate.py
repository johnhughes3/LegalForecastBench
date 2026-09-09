"""Recognize terminal evidence before strict transcript validation."""

from __future__ import annotations

import json
import re
from typing import cast


def has_terminal_transcript_candidate(raw: bytes) -> bool:
    """Retain malformed terminal-looking evidence for explicit repair."""
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return bool(
            re.search(rb'"agent_status"\s*:\s*"(?:succeeded|failed)"', raw)
            and re.search(rb'"messages"\s*:\s*\[\s*\{', raw)
            and re.search(rb'"tool_name"\s*:\s*"final_result"', raw)
        )
    return has_terminal_result_candidate(value)


def has_terminal_result_candidate(value: object) -> bool:
    """Recognize a nonempty SDK history containing terminal output."""
    if not isinstance(value, dict):
        return False
    record = cast(dict[str, object], value)
    if record.get("agent_status") not in {"succeeded", "failed"}:
        return False
    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        return False
    if record.get("agent_status") == "succeeded":
        return True
    for message in cast(list[object], messages):
        if not isinstance(message, dict):
            continue
        response = cast(dict[str, object], message)
        parts = response.get("parts")
        if response.get("kind") != "response" or not isinstance(parts, list):
            continue
        for part in cast(list[object], parts):
            if not isinstance(part, dict):
                continue
            item = cast(dict[str, object], part)
            if (
                item.get("part_kind") == "tool-call"
                and item.get("tool_name") == "final_result"
            ):
                return True
    return False

"""Authenticate exact Cycle 1 execution evidence from Beads comment bytes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.immutable_io import ImmutableIOError, read_single_link_file

COORDINATION_BEAD_ID: Final = "legalforecastbench-3ak.38"
OWNER_AUTHOR: Final = "John Hughes"
SUCCESSOR_REGISTRY_PATH: Final = (
    "model_registries/cycle-1-2026-06-30-claude-fable-5-successor-2026-08-31.json"
)
CONTAMINATION_LINE: Final = (
    "contamination: replace claude-sonnet-5 with claude-opus-4-8"
)
SUCCESSOR_REGISTRY_KEYS: Final = frozenset(
    {
        "openai:gpt-5.6-sol",
        "openai:gpt-5.6-terra",
        "openai:gpt-5.6-luna",
        "anthropic:claude-fable-5",
    }
)
_MANIFEST_APPROVAL: Final = re.compile(
    r"I approve corpus manifest (?P<digest>[0-9a-f]{64}) as the frozen Cycle 1 "
    r"forecast corpus\.\Z"
)
_SPEND_APPROVAL: Final = re.compile(
    r"I approve up to USD (?P<ceiling>[0-9]+(?:\.[0-9]{1,2})?) of provider "
    r"spend for the Cycle 1 forecast run, estimated USD "
    r"(?P<estimate>[0-9]+(?:\.[0-9]{1,2})?), across the four models in `?"
    r"(?P<registry>[^`]+?)`?\.\Z"
)


class BeadsObservationError(ValueError):
    """Raised when Beads bytes do not contain exact authentic evidence."""


def parse_authentic_beads_comments(
    payload: bytes,
    *,
    model_registry: Path,
    model_registry_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Select the newest exact owner records from authentic comment JSON."""

    if not model_registry.as_posix().endswith(SUCCESSOR_REGISTRY_PATH):
        raise BeadsObservationError("model registry is not the Cycle 1 successor path")
    registry = load_model_registry_bytes(
        model_registry_bytes
        if model_registry_bytes is not None
        else _read_regular(model_registry, "successor model registry")
    )
    entries = require_official_registry_entries(registry.entries)
    if frozenset(entry.registry_key for entry in entries) != SUCCESSOR_REGISTRY_KEYS:
        raise BeadsObservationError("model registry does not contain the successor set")
    try:
        loaded: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BeadsObservationError("raw Beads observation is not JSON") from exc
    if not isinstance(loaded, list):
        raise BeadsObservationError("raw Beads observation must be a comment array")
    comments = _owner_comments(cast(list[object], loaded))
    manifest_candidates = [
        (comment, match)
        for comment in comments
        if (match := _MANIFEST_APPROVAL.fullmatch(comment["text"])) is not None
    ]
    spend_candidates = [
        (comment, match)
        for comment in comments
        if (match := _SPEND_APPROVAL.fullmatch(comment["text"])) is not None
        and match.group("registry") == SUCCESSOR_REGISTRY_PATH
    ]
    contamination_candidates = [
        comment for comment in comments if comment["text"] == CONTAMINATION_LINE
    ]
    if not manifest_candidates:
        raise BeadsObservationError(
            "raw Beads observation lacks a digest-bound manifest approval"
        )
    if not spend_candidates:
        raise BeadsObservationError(
            "raw Beads observation lacks final successor-registry spend approval"
        )
    if not contamination_candidates:
        raise BeadsObservationError(
            "raw Beads observation lacks exact contamination replacement ruling"
        )
    manifest_comment, manifest_match = max(
        manifest_candidates, key=lambda item: item[0]["created_at"]
    )
    spend_comment, spend_match = max(
        spend_candidates, key=lambda item: item[0]["created_at"]
    )
    contamination_comment = max(
        contamination_candidates, key=lambda item: item["created_at"]
    )
    ceiling = _money(spend_match.group("ceiling"), "ceiling_usd")
    estimate = _money(spend_match.group("estimate"), "estimate_usd")
    if estimate > ceiling:
        raise BeadsObservationError("Beads spend estimate exceeds ceiling")
    return {
        "manifest": {
            **_comment_evidence(manifest_comment),
            "manifest_sha256": manifest_match.group("digest"),
        },
        "contamination": _comment_evidence(contamination_comment),
        "final_provider_spend": {
            **_comment_evidence(spend_comment),
            "registry_path": SUCCESSOR_REGISTRY_PATH,
            "ceiling_usd": f"{ceiling:.2f}",
            "estimate_usd": f"{estimate:.2f}",
        },
    }


def _owner_comments(rows: list[object]) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    fields = ("id", "issue_id", "author", "text", "created_at")
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise BeadsObservationError("Beads comment fields are not exact")
        raw_map = cast(Mapping[str, Any], raw)
        if set(raw_map) != set(fields):
            raise BeadsObservationError("Beads comment fields are not exact")
        comment = {name: _required_text(raw_map, name) for name in fields}
        if comment["issue_id"] != COORDINATION_BEAD_ID:
            raise BeadsObservationError("Beads comment issue_id differs")
        _timestamp(comment["created_at"], "created_at")
        if comment["author"] == OWNER_AUTHOR:
            comments.append(comment)
    if not comments:
        raise BeadsObservationError("Beads observation contains no owner comments")
    return comments


def _comment_evidence(comment: Mapping[str, str]) -> dict[str, str]:
    text = _required_text(comment, "text")
    return {
        "comment_id": _required_text(comment, "id"),
        "created_at": _required_text(comment, "created_at"),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _money(value: str, name: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise BeadsObservationError(f"{name} must be decimal USD") from exc
    exponent = amount.as_tuple().exponent
    if amount < 0 or not isinstance(exponent, int) or exponent < -2:
        raise BeadsObservationError(f"{name} must be non-negative cents")
    return amount


def _read_regular(path: Path, label: str) -> bytes:
    try:
        return read_single_link_file(path, label=label)
    except ImmutableIOError as exc:
        raise BeadsObservationError(str(exc)) from exc


def _required_text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise BeadsObservationError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: str, name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BeadsObservationError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BeadsObservationError(f"{name} must be timezone-aware")

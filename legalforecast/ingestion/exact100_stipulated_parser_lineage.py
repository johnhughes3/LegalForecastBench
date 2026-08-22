"""Bind stipulated exclusions to predecessor-authenticated source bytes.

The eligibility-audit replay already reconstructs materialization, parse-plan,
parser run-card/manifest, and Markdown from the audit card's own committed
paths. That reconstruction is internally hash-consistent, so a caller-owned
parallel tree can mint a stipulated verdict without touching the successor
predecessor's download manifest.

This module is the remaining producer-lineage bridge: the ineligible
document's parser source commitment must equal the unique predecessor
download-manifest row. It does not mint terminal evidence and does not
add fields to frozen exclusion records.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

JsonRecord = dict[str, Any]


class StipulatedParserLineageError(ValueError):
    """Raised when stipulated parser source bytes are not predecessor-bound."""


def require_stipulated_source_matches_predecessor_download(
    *,
    candidate_id: str,
    source_document_id: str,
    parser_record: Mapping[str, Any],
    predecessor_download_manifest_bytes: bytes,
) -> None:
    """Refuse a stipulated exclusion whose PDF is not the predecessor download."""

    if (
        parser_record.get("candidate_id") != candidate_id
        or parser_record.get("source_document_id") != source_document_id
    ):
        raise StipulatedParserLineageError(
            "stipulated target parser record is not the selected document"
        )
    source_sha256 = parser_record.get("source_sha256")
    source_byte_count = parser_record.get("source_byte_count")
    if not isinstance(source_sha256, str) or not source_sha256.strip():
        raise StipulatedParserLineageError(
            "stipulated target parser record lacks a source commitment"
        )
    if type(source_byte_count) is not int:
        raise StipulatedParserLineageError(
            "stipulated target parser record lacks a source commitment"
        )
    matches = [
        record
        for record in _jsonl_records(
            predecessor_download_manifest_bytes,
            "authenticated predecessor download manifest",
        )
        if record.get("candidate_id") == candidate_id
        and record.get("source_document_id") == source_document_id
    ]
    if len(matches) != 1:
        raise StipulatedParserLineageError(
            "stipulated target lacks one authenticated predecessor download"
        )
    authenticated_download = matches[0]
    if (
        not _same_sha(authenticated_download.get("sha256"), source_sha256)
        or authenticated_download.get("byte_count") != source_byte_count
    ):
        raise StipulatedParserLineageError(
            "stipulated target PDF differs from authenticated predecessor download"
        )


def parser_record_for_document(
    parser_records: Sequence[Mapping[str, Any]],
    *,
    candidate_id: str,
    source_document_id: str,
) -> Mapping[str, Any]:
    """Return the unique parser row for one selected stipulated document."""

    matches = [
        record
        for record in parser_records
        if record.get("candidate_id") == candidate_id
        and record.get("source_document_id") == source_document_id
    ]
    if len(matches) != 1:
        raise StipulatedParserLineageError(
            "stipulated target lacks one authenticated parser record"
        )
    return matches[0]


def _jsonl_records(payload: bytes, label: str) -> tuple[JsonRecord, ...]:
    """Parse predecessor JSONL without renormalizing producer codecs."""

    if not payload:
        raise StipulatedParserLineageError(f"{label} is empty")
    lines = payload.splitlines(keepends=True)
    if any(not line.endswith(b"\n") for line in lines) or any(
        line == b"\n" for line in lines
    ):
        raise StipulatedParserLineageError(f"{label} is not valid JSONL")
    records: list[JsonRecord] = []
    for line in lines:
        try:
            decoded = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StipulatedParserLineageError(
                f"{label} contains invalid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise StipulatedParserLineageError(f"{label} is not valid JSONL")
        records.append(cast(JsonRecord, decoded))
    return tuple(records)


def _same_sha(value: object, expected: str) -> bool:
    return isinstance(value, str) and value.removeprefix(
        "sha256:"
    ) == expected.removeprefix("sha256:")

"""Provider-free attorney review for exhausted Stage A unitizer calls.

This is intentionally separate from the frozen unit review queue: an exhausted
unitizer produced no prediction units, so representing it as a unit-subject row
would invent both a unit and its legal conclusion.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from legalforecast.contracts import (
    LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1,
    UNITIZER_TERMINAL_REVIEW_BUNDLE_V1,
    UNITIZER_TERMINAL_REVIEW_QUEUE_V1,
)
from legalforecast.unitization.review import canonical_sha256

JsonRecord = dict[str, Any]

_SHA256 = re.compile(r"[0-9a-f]{64}")
_PREFIXED_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_RECEIPT_FIELDS = {
    "schema_version",
    "candidate_id",
    "case_id",
    "unitizer_model_key",
    "model_registry_sha256",
    "provider_attempt_namespace",
    "prompt",
    "prompt_sha256",
    "predecision_source_commitments",
    "failed_attempts",
}
_SOURCE_COMMITMENT_FIELDS = {
    "source_document_id",
    "document_role",
    "docket_entry_number",
    "description",
    "markdown_sha256",
}
_ATTEMPT_FIELDS = {
    "attempt_ordinal",
    "raw_response_sha256",
    "normalized_response_sha256",
    "failure_type",
    "failure_message",
}
_SOURCE_FIELDS = {
    "source_document_id",
    "document_role",
    "docket_entry_number",
    "description",
    "markdown",
}
_ALLOWED_ACTIONS = ["ADD", "CANDIDATE-EXCLUSION"]
_PREDECISION_ROLES = {
    "complaint",
    "amended_complaint",
    "motion_to_dismiss_notice",
    "motion_to_dismiss_memorandum",
    "opposition",
    "reply",
    "docket_history",
}


class UnitizerTerminalReviewError(ValueError):
    """Raised when terminal evidence cannot support an honest attorney item."""


def build_unitizer_terminal_review_queue_record(
    receipt: object,
) -> JsonRecord:
    """Project one authenticated terminal receipt into a candidate review item."""

    terminal = _validated_receipt(receipt)
    candidate_id = _required_str(terminal, "candidate_id", "terminal receipt")
    case_id = _required_str(terminal, "case_id", "terminal receipt")
    digest = canonical_sha256(terminal)
    source_commitments = _mapping_sequence(
        terminal, "predecision_source_commitments", "terminal receipt"
    )
    attempts = _mapping_sequence(terminal, "failed_attempts", "terminal receipt")
    return {
        "schema_version": str(UNITIZER_TERMINAL_REVIEW_QUEUE_V1),
        "status": "pending_adjudication",
        "review_id": f"{candidate_id}:unitizer-terminal:{digest[:16]}",
        "review_subject": "candidate",
        "candidate_id": candidate_id,
        "case_id": case_id,
        "reason": {
            "code": "unitizer_terminal_reconstruction_failure",
            "class": "technical",
            "summary": (
                "Stage A unitization exhausted its authenticated reconstruction "
                "attempts without producing accepted prediction units."
            ),
        },
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "suggested_actions": [],
        "terminal_escalation_sha256": digest,
        "review_item": {
            "unitizer_model_key": _required_str(
                terminal, "unitizer_model_key", "terminal receipt"
            ),
            "model_registry_sha256": _required_str(
                terminal, "model_registry_sha256", "terminal receipt"
            ),
            "provider_attempt_namespace": _required_str(
                terminal, "provider_attempt_namespace", "terminal receipt"
            ),
            "prompt_sha256": _required_str(
                terminal, "prompt_sha256", "terminal receipt"
            ),
            "predecision_source_document_ids": [
                _required_str(source, "source_document_id", "source commitment")
                for source in source_commitments
            ],
            "predecision_source_commitments": [
                dict(source) for source in source_commitments
            ],
            "attempt_commitments": [dict(attempt) for attempt in attempts],
            "notes": (
                "No prediction unit or legal conclusion was accepted from the "
                "failed responses. Review the authenticated predecision sources."
            ),
        },
    }


def build_unitizer_terminal_review_bundle(
    *,
    receipt: object,
    queue_record: Mapping[str, object],
    predecision_sources: object,
) -> JsonRecord:
    """Bind the candidate item to exact, blinded predecision Markdown."""

    if not isinstance(predecision_sources, Sequence) or isinstance(
        predecision_sources, (str, bytes)
    ):
        raise UnitizerTerminalReviewError("predecision sources must be a sequence")
    terminal = _validated_receipt(receipt)
    expected_queue = build_unitizer_terminal_review_queue_record(terminal)
    if dict(queue_record) != expected_queue:
        raise UnitizerTerminalReviewError(
            "terminal unitizer queue record differs from its receipt"
        )
    commitments = _mapping_sequence(
        terminal, "predecision_source_commitments", "terminal receipt"
    )
    commitment_by_id = {
        _required_str(item, "source_document_id", "source commitment"): item
        for item in commitments
    }
    supplied_by_id: dict[str, Mapping[str, object]] = {}
    for source in cast(Sequence[object], predecision_sources):
        if not isinstance(source, Mapping):
            raise UnitizerTerminalReviewError("predecision source must be an object")
        record = cast(Mapping[str, object], source)
        if set(record) != _SOURCE_FIELDS:
            raise UnitizerTerminalReviewError(
                "predecision source has unsupported fields"
            )
        source_id = _required_str(record, "source_document_id", "predecision source")
        if source_id in supplied_by_id:
            raise UnitizerTerminalReviewError(
                f"duplicate predecision source_document_id: {source_id}"
            )
        supplied_by_id[source_id] = record
    if set(supplied_by_id) != set(commitment_by_id):
        raise UnitizerTerminalReviewError(
            "terminal review bundle source coverage differs from receipt"
        )
    bundled_sources: list[JsonRecord] = []
    for commitment in commitments:
        source_id = _required_str(commitment, "source_document_id", "source commitment")
        source = supplied_by_id[source_id]
        role = _required_str(source, "document_role", "predecision source")
        if role not in _PREDECISION_ROLES:
            raise UnitizerTerminalReviewError(
                f"terminal bundle source is not predecision material: {source_id}"
            )
        for field in ("document_role", "docket_entry_number", "description"):
            if source.get(field) != commitment.get(field):
                raise UnitizerTerminalReviewError(
                    f"predecision source metadata differs from receipt: {source_id}"
                )
        markdown = _required_str(source, "markdown", "predecision source")
        markdown_digest = "sha256:" + hashlib.sha256(markdown.encode()).hexdigest()
        if markdown_digest != commitment.get("markdown_sha256"):
            raise UnitizerTerminalReviewError(
                f"predecision source markdown commitment mismatch: {source_id}"
            )
        bundled_sources.append(dict(source))
    return {
        "schema_version": str(UNITIZER_TERMINAL_REVIEW_BUNDLE_V1),
        "review_id": expected_queue["review_id"],
        "candidate_id": expected_queue["candidate_id"],
        "case_id": expected_queue["case_id"],
        "review_subject": "candidate",
        "reason": expected_queue["reason"],
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "terminal_escalation_sha256": expected_queue["terminal_escalation_sha256"],
        "review_item": expected_queue["review_item"],
        "cited_predecision_markdown": bundled_sources,
    }


def _validated_receipt(receipt: object) -> JsonRecord:
    if not isinstance(receipt, Mapping):
        raise UnitizerTerminalReviewError("terminal receipt must be an object")
    terminal = dict(cast(Mapping[str, object], receipt))
    if set(terminal) != _RECEIPT_FIELDS:
        raise UnitizerTerminalReviewError("terminal receipt field set is invalid")
    if terminal.get("schema_version") != str(
        LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1
    ):
        raise UnitizerTerminalReviewError("terminal receipt schema is unsupported")
    for field in (
        "candidate_id",
        "case_id",
        "unitizer_model_key",
        "provider_attempt_namespace",
        "prompt",
    ):
        _required_str(terminal, field, "terminal receipt")
    for field in ("model_registry_sha256", "prompt_sha256"):
        value = _required_str(terminal, field, "terminal receipt")
        if _SHA256.fullmatch(value) is None:
            raise UnitizerTerminalReviewError(
                f"terminal receipt {field} must be a lowercase SHA-256"
            )
    prompt = _required_str(terminal, "prompt", "terminal receipt")
    if hashlib.sha256(prompt.encode()).hexdigest() != terminal["prompt_sha256"]:
        raise UnitizerTerminalReviewError("terminal receipt prompt commitment differs")
    sources = _mapping_sequence(
        terminal, "predecision_source_commitments", "terminal receipt"
    )
    if not sources:
        raise UnitizerTerminalReviewError(
            "terminal receipt lacks predecision source commitments"
        )
    source_ids: list[str] = []
    for source in sources:
        if set(source) != _SOURCE_COMMITMENT_FIELDS:
            raise UnitizerTerminalReviewError("source commitment field set is invalid")
        source_ids.append(
            _required_str(source, "source_document_id", "source commitment")
        )
        _required_str(source, "document_role", "source commitment")
        _required_str(source, "description", "source commitment")
        docket_number = source.get("docket_entry_number")
        if docket_number is not None and (
            not isinstance(docket_number, int)
            or isinstance(docket_number, bool)
            or docket_number <= 0
        ):
            raise UnitizerTerminalReviewError(
                "source commitment docket_entry_number is invalid"
            )
        markdown_sha = _required_str(source, "markdown_sha256", "source commitment")
        if _PREFIXED_SHA256.fullmatch(markdown_sha) is None:
            raise UnitizerTerminalReviewError(
                "source commitment markdown_sha256 must be a prefixed SHA-256"
            )
    if len(source_ids) != len(set(source_ids)):
        raise UnitizerTerminalReviewError(
            "terminal receipt has duplicate source_document_id"
        )
    attempts = _mapping_sequence(terminal, "failed_attempts", "terminal receipt")
    if not attempts:
        raise UnitizerTerminalReviewError("terminal receipt has no failed attempt")
    ordinals: list[int] = []
    for attempt in attempts:
        if set(attempt) != _ATTEMPT_FIELDS:
            raise UnitizerTerminalReviewError(
                "terminal failed attempt field set is invalid"
            )
        ordinal = attempt.get("attempt_ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal <= 0:
            raise UnitizerTerminalReviewError(
                "terminal failed attempt ordinal is invalid"
            )
        ordinals.append(ordinal)
        for field in ("raw_response_sha256", "normalized_response_sha256"):
            value = _required_str(attempt, field, "terminal failed attempt")
            if _PREFIXED_SHA256.fullmatch(value) is None:
                raise UnitizerTerminalReviewError(
                    f"terminal failed attempt {field} must be a prefixed SHA-256"
                )
        _required_str(attempt, "failure_type", "terminal failed attempt")
        _required_str(attempt, "failure_message", "terminal failed attempt")
    if ordinals != [1, 2, 3]:
        raise UnitizerTerminalReviewError(
            "terminal receipt must bind exactly failed attempts 1, 2, and 3"
        )
    return terminal


def _mapping_sequence(
    record: Mapping[str, object], field: str, label: str
) -> tuple[Mapping[str, object], ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UnitizerTerminalReviewError(f"{label} {field} must be a sequence")
    items = cast(Sequence[object], value)
    mappings: tuple[Mapping[str, object], ...] = tuple(
        cast(Mapping[str, object], item) for item in items if isinstance(item, Mapping)
    )
    if len(mappings) != len(items):
        raise UnitizerTerminalReviewError(f"{label} {field} contains a non-object")
    return mappings


def read_terminal_jsonl(payload: bytes, *, label: str) -> list[JsonRecord]:
    """Parse terminal-apply JSONL, refusing duplicate object keys."""

    records: list[JsonRecord] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeError as error:
        raise UnitizerTerminalReviewError(f"{label} must be UTF-8 JSONL") from error
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            loaded = json.loads(
                line,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_unsupported_json_constant,
            )
        except UnitizerTerminalReviewError:
            raise
        except json.JSONDecodeError as error:
            raise UnitizerTerminalReviewError(
                f"{label}:{line_number} is invalid JSON: {error.msg}"
            ) from error
        except ValueError as error:
            raise UnitizerTerminalReviewError(
                f"{label}:{line_number} {error}"
            ) from error
        if not isinstance(loaded, Mapping):
            raise UnitizerTerminalReviewError(
                f"{label}:{line_number} must contain a JSON object"
            )
        records.append(dict(cast(Mapping[str, object], loaded)))
    return records


def _unsupported_json_constant(value: str) -> object:
    raise UnitizerTerminalReviewError(f"JSON numeric constant {value} is not supported")


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, value in pairs:
        if key in record:
            raise UnitizerTerminalReviewError(
                f"JSON object contains duplicate key {key!r}"
            )
        record[key] = value
    return record


def _required_str(record: Mapping[str, object], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UnitizerTerminalReviewError(f"{label} {field} must be nonempty")
    return value


__all__ = [
    "UnitizerTerminalReviewError",
    "build_unitizer_terminal_review_bundle",
    "build_unitizer_terminal_review_queue_record",
    "read_terminal_jsonl",
]

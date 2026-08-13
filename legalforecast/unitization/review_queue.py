"""Candidate-aware projection of the Stage A human-review queue.

The authoritative queue (``legalforecast.unitization_review_queue.v1``) carries
one row per *unit* and encodes the routing rationale in a single free-form
``route_reason`` string.  That conflates four separate things a reviewer needs
kept apart: what is under review (a unit or a whole candidate), why it is under
review, what the system will actually accept as a resolution, and what an
unverified model merely *suggested*.

This module builds a parallel v2 projection that keeps those four distinct.  It
is deliberately a projection and never a mutation: ``docs/cycle-1-change-control.md``
freezes the authenticated v1 byte contract for the rest of Cycle 1 and routes
new observational data into non-authoritative sidecars.  Nothing here feeds
:func:`legalforecast.unitization.review.apply_unitization_reviews`; the frozen
adjudication validators still consume v1 rows only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast._record_validation import required_int, required_str
from legalforecast.contracts.schemas import (
    UNITIZATION_REVIEW_QUEUE_V1,
    UNITIZATION_REVIEW_QUEUE_V2,
)

JsonRecord = dict[str, Any]

SCHEMA_VERSION = str(UNITIZATION_REVIEW_QUEUE_V2)
V1_SCHEMA_VERSION = str(UNITIZATION_REVIEW_QUEUE_V1)
TERMINAL_ROUTE_REASON = "structural_reviewer_terminal_reconstruction_failure"
UNCLASSIFIED_VALIDATOR_CODE = "unclassified"
MIXED_VALIDATOR_CODE = "structural_review_validator_mixed"


class ReviewQueueError(Exception):
    """Raised when a review-queue projection cannot be built honestly."""


def review_queue_v2_sidecar_path(queue_path: Path) -> Path:
    """Return the sidecar path a v1 queue's v2 projection is written beside."""

    return queue_path.with_name(f"{queue_path.stem}-v2{queue_path.suffix}")


class ReviewSubject(StrEnum):
    """What a queue item asks a reviewer to decide about."""

    UNIT = "unit"
    CANDIDATE = "candidate"


class ReviewReasonClass(StrEnum):
    """Whether an item is about the law or about the machinery."""

    SUBSTANTIVE = "substantive"
    TECHNICAL = "technical"


class ReviewAction(StrEnum):
    """The closed vocabulary of actions a v2 item may offer.

    The first seven mirror ``review.UnitizationDisposition`` exactly, because
    those are the only dispositions the frozen adjudication validators accept.
    The last three name possible future technical operations, but Cycle 1 has
    no candidate-level consumer for them, so they are never authoritative
    ``allowed_actions`` in this frozen observational projection.
    """

    ACCEPT = "ACCEPT"
    ADD = "ADD"
    AMEND = "AMEND"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    DROP = "DROP"
    CANDIDATE_EXCLUSION = "CANDIDATE-EXCLUSION"
    RETRY_STRUCTURAL_REVIEW = "RETRY-STRUCTURAL-REVIEW"
    WAIVE_STRUCTURAL_REVIEW = "WAIVE-STRUCTURAL-REVIEW"
    EXCLUDE_CANDIDATE = "EXCLUDE-CANDIDATE"


# Every disposition that can consume a single unit-subject review, derived from
# `_validate_disposition_shape`.  ADD is excluded here because that validator
# additionally requires an `structural_omitted` review, and CANDIDATE-EXCLUSION
# is included because it consumes source units like the rest.
_UNIT_ACTIONS: tuple[ReviewAction, ...] = (
    ReviewAction.ACCEPT,
    ReviewAction.AMEND,
    ReviewAction.SPLIT,
    ReviewAction.MERGE,
    ReviewAction.DROP,
    ReviewAction.CANDIDATE_EXCLUSION,
)
_OMISSION_ACTIONS: tuple[ReviewAction, ...] = (ReviewAction.ADD, *_UNIT_ACTIONS)


@dataclass(frozen=True, slots=True)
class ReviewReason:
    """An immutable routing rationale with its own fixed summary and actions."""

    code: str
    reason_class: ReviewReasonClass
    subject: ReviewSubject
    summary: str
    allowed_actions: tuple[ReviewAction, ...]

    def to_record(self) -> JsonRecord:
        return {
            "code": self.code,
            "class": self.reason_class.value,
            "summary": self.summary,
        }


def _substantive(code: str, summary: str) -> ReviewReason:
    return ReviewReason(
        code=code,
        reason_class=ReviewReasonClass.SUBSTANTIVE,
        subject=ReviewSubject.UNIT,
        summary=summary,
        allowed_actions=(
            _OMISSION_ACTIONS if code == "structural_omitted" else _UNIT_ACTIONS
        ),
    )


# Exhaustive for the unitization review queue: three construction reasons
# (`UnitizationReviewReason`), four structural flag types rendered as
# `structural_{flag_type}`, and the terminal escalation route.
REVIEW_REASONS: Mapping[str, ReviewReason] = {
    reason.code: reason
    for reason in (
        _substantive(
            "unclear_claim_or_defendant",
            "Stage A could not resolve the asserted claim or the moving defendant.",
        ),
        _substantive(
            "unclear_grouping",
            "Stage A could not resolve whether these propositions are one unit.",
        ),
        _substantive(
            "low_confidence",
            "Stage A produced this unit below the confidence floor.",
        ),
        _substantive(
            "structural_omitted",
            "The structural reviewer flagged an asserted legal right with no unit.",
        ),
        _substantive(
            "structural_combined",
            "The structural reviewer flagged independently disposable rights as "
            "one unit.",
        ),
        _substantive(
            "structural_mis_split",
            "The structural reviewer flagged one nonseparable right split across "
            "units.",
        ),
        _substantive(
            "structural_spurious",
            "The structural reviewer flagged a unit that asserts no legal right.",
        ),
        ReviewReason(
            code=TERMINAL_ROUTE_REASON,
            reason_class=ReviewReasonClass.TECHNICAL,
            subject=ReviewSubject.CANDIDATE,
            summary=(
                "Structural review never produced an accepted flag: every "
                "reconstruction attempt failed local validation. No unit was "
                "adjudicated and no flag was accepted."
            ),
            # Frozen Cycle 1 has no candidate-subject adjudication consumer.
            # Naming technical operations here as authoritative would falsely
            # advertise an executable resolution path.
            allowed_actions=(),
        ),
    )
}

_FLAG_TYPE_SUGGESTIONS: Mapping[str, ReviewAction] = {
    "omitted": ReviewAction.ADD,
    "combined": ReviewAction.SPLIT,
    "mis_split": ReviewAction.MERGE,
    "spurious": ReviewAction.DROP,
}

# (failure_type, exact message) -> (validator_code, invalid_field).  Messages are
# the literals raised by `validate_structural_review_flags` and
# `_document_line_span`; anything else classifies as `unclassified` with the
# original message preserved verbatim.
_VALIDATOR_CLASSIFICATIONS: Mapping[tuple[str, str], tuple[str, str]] = {
    ("LlmResponseValidationError", message): classification
    for message, classification in (
        (
            "structural reviewer may not rewrite units",
            ("structural_flag_rewrite_forbidden", "structural_flags"),
        ),
        (
            "affected_unit_ids must uniquely reference existing frozen units",
            ("structural_flag_affected_unit_ids_invalid", "affected_unit_ids"),
        ),
        (
            "v4 structural flag contains unsupported fields",
            ("structural_flag_fields_unsupported", "structural_flags"),
        ),
        (
            "v4 structural evidence span contains unsupported fields",
            ("structural_evidence_span_fields_unsupported", "evidence_spans"),
        ),
        (
            "v4 structural evidence_spans requires unique document ids",
            ("structural_evidence_span_documents_duplicated", "evidence_spans"),
        ),
        (
            "structural flag source_document_id must reference a supplied "
            "predecision document",
            ("structural_evidence_span_document_unknown", "source_document_id"),
        ),
        (
            "citation line range is outside the source document",
            ("structural_evidence_span_line_range_invalid", "evidence_spans"),
        ),
        (
            "citation line range may not exceed 12 lines",
            ("structural_evidence_span_line_range_too_long", "evidence_spans"),
        ),
        (
            "citation line range is empty",
            ("structural_evidence_span_line_range_empty", "evidence_spans"),
        ),
        (
            "v4 structural flag requires nonempty evidence_spans",
            ("structural_evidence_spans_missing", "evidence_spans"),
        ),
        (
            "v4 omitted structural flag requires complaint or amended-complaint "
            "evidence",
            ("structural_omitted_complaint_evidence_missing", "evidence_spans"),
        ),
        (
            "v4 omitted structural flag requires target motion-to-dismiss notice "
            "or memorandum evidence",
            ("structural_omitted_motion_evidence_missing", "evidence_spans"),
        ),
        (
            "structural flag requires source_document_ids",
            ("structural_flag_source_documents_missing", "source_document_ids"),
        ),
        (
            "structural flag source_document_ids must reference supplied "
            "predecision documents",
            ("structural_flag_source_documents_unknown", "source_document_ids"),
        ),
        (
            "v3 structural flag requires exactly one source_document_id",
            ("structural_flag_source_document_count_invalid", "source_document_ids"),
        ),
        (
            "structural flag citation_excerpt does not appear in any cited "
            "predecision document",
            ("structural_flag_citation_excerpt_unverified", "citation_excerpt"),
        ),
    )
}

# Parameterized messages carry a value, so they are matched on a declared prefix
# rather than by equality.  Order is fixed for determinism.
_VALIDATOR_PREFIX_CLASSIFICATIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "LlmResponseValidationError",
        "unsupported structural flag_type: ",
        "structural_flag_type_unsupported",
        "flag_type",
    ),
)


def classify_structural_validator_failure(
    *, failure_type: str, failure_message: str
) -> tuple[str, str | None]:
    """Map a journaled reconstruction failure to a stable validator code.

    Returns ``(validator_code, invalid_field)``.  Unrecognized failures return
    ``(UNCLASSIFIED_VALIDATOR_CODE, None)``; callers keep the exact message so
    nothing about the original failure is lost to the classification.
    """

    classification = _VALIDATOR_CLASSIFICATIONS.get((failure_type, failure_message))
    if classification is not None:
        return classification
    for prefix_type, prefix, code, field in _VALIDATOR_PREFIX_CLASSIFICATIONS:
        if failure_type == prefix_type and failure_message.startswith(prefix):
            return code, field
    return UNCLASSIFIED_VALIDATOR_CODE, None


def _as_record(value: object) -> JsonRecord | None:
    """Narrow an untyped JSON value to a record, or None if it is not one."""

    if not isinstance(value, Mapping):
        return None
    return dict(cast(Mapping[str, Any], value))


def _as_sequence(value: object) -> tuple[object, ...] | None:
    """Narrow an untyped JSON value to a list-like, or None if it is not one."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    return tuple(cast(Sequence[object], value))


def review_reason_code(record: Mapping[str, Any]) -> str:
    """Read the routing rationale from either a v1 or a v2 queue row."""

    reason = _as_record(record.get("reason"))
    if reason is not None:
        return required_str(reason, "code")
    return required_str(record, "route_reason")


def safe_parsed_structural_flags(
    normalized_response_json: str,
    *,
    expected_sha256: str,
    frozen_unit_ids: Iterable[str],
) -> tuple[JsonRecord, ...]:
    """Recover individually well-formed flags from a rejected reviewer response.

    The response bytes are authenticated against their journaled commitment
    *before* being parsed, so a tampered or mismatched body never reaches the
    JSON decoder.  After that, each flag stands or falls on its own: a response
    that failed whole-payload validation may still contain flags that are
    perfectly well formed, and those are worth showing a reviewer as
    non-authoritative suggestions.  Nothing here is ever accepted as a flag.
    """

    digest = hashlib.sha256(normalized_response_json.encode("utf-8")).hexdigest()
    if digest != expected_sha256.removeprefix("sha256:"):
        raise ReviewQueueError(
            "normalized structural-review response does not match its commitment"
        )
    allowed_unit_ids = set(frozen_unit_ids)
    try:
        payload = _as_record(json.loads(normalized_response_json))
    except json.JSONDecodeError:
        return ()
    if payload is None:
        return ()
    raw_flags = _as_sequence(payload.get("structural_flags"))
    if raw_flags is None:
        return ()
    safe: list[JsonRecord] = []
    for raw_flag in raw_flags:
        flag = _as_record(raw_flag)
        if flag is None:
            continue
        flag_type = flag.get("flag_type")
        explanation = flag.get("explanation")
        affected = _as_sequence(flag.get("affected_unit_ids"))
        if not isinstance(flag_type, str) or flag_type not in _FLAG_TYPE_SUGGESTIONS:
            continue
        if not isinstance(explanation, str) or not explanation.strip():
            continue
        if affected is None:
            continue
        unit_ids = [item for item in affected if isinstance(item, str)]
        if (
            not unit_ids
            or len(unit_ids) != len(affected)
            or len(unit_ids) != len(set(unit_ids))
            or not set(unit_ids) <= allowed_unit_ids
        ):
            continue
        safe.append(
            {
                "flag_type": flag_type,
                "affected_unit_ids": list(unit_ids),
                "explanation": explanation,
            }
        )
    return tuple(safe)


def _suggested_actions(flags: Sequence[Mapping[str, Any]]) -> list[JsonRecord]:
    return [
        {
            "authoritative": False,
            "action": _FLAG_TYPE_SUGGESTIONS[required_str(flag, "flag_type")].value,
            "affected_unit_ids": list(
                _as_sequence(flag.get("affected_unit_ids")) or ()
            ),
            "rationale": required_str(flag, "explanation"),
            "source": "rejected_structural_review_response",
        }
        for flag in flags
    ]


def _reason_for(code: str) -> ReviewReason:
    reason = REVIEW_REASONS.get(code)
    if reason is None:
        raise ReviewQueueError(f"unsupported review queue route_reason: {code}")
    return reason


def _attempt_commitments(
    review_item: Mapping[str, Any],
) -> tuple[list[JsonRecord], list[str], list[str | None]]:
    commitments: list[JsonRecord] = []
    codes: list[str] = []
    fields: list[str | None] = []
    raw_attempts = _as_sequence(review_item.get("failed_attempts"))
    if raw_attempts is None:
        raise ReviewQueueError("terminal review item lacks failed_attempts")
    for raw_attempt in raw_attempts:
        attempt = _as_record(raw_attempt)
        if attempt is None:
            raise ReviewQueueError("terminal review attempt is not a record")
        failure_type = required_str(attempt, "failure_type")
        failure_message = required_str(attempt, "failure_message")
        code, field = classify_structural_validator_failure(
            failure_type=failure_type, failure_message=failure_message
        )
        codes.append(code)
        fields.append(field)
        commitments.append(
            {
                "attempt_ordinal": required_int(attempt, "attempt_ordinal"),
                "raw_response_sha256": required_str(attempt, "raw_response_sha256"),
                "normalized_response_sha256": required_str(
                    attempt, "normalized_response_sha256"
                ),
                "validator_code": code,
                "invalid_field": field,
                "failure_type": failure_type,
                "failure_message": failure_message,
            }
        )
    return commitments, codes, fields


@dataclass(frozen=True, slots=True)
class _TerminalGroup:
    """Every terminal signal seen for one candidate, in first-seen order."""

    candidate_id: str
    case_id: str
    review_item: JsonRecord
    escalation_sha256: str
    provenance: JsonRecord
    affected_unit_ids: list[str]
    absorbed_review_ids: list[str]
    terminal_evidence_review_ids: list[str]


def _terminal_record(record: Mapping[str, Any]) -> JsonRecord | None:
    """Return the terminal payload a v1 row carries, standalone or coalesced."""

    if record.get("route_reason") == TERMINAL_ROUTE_REASON:
        return dict(record)
    return _as_record(record.get("terminal_escalation"))


def _provenance(record: Mapping[str, Any]) -> JsonRecord:
    return {
        key: record[key]
        for key in (
            "reviewer_model_key",
            "model_registry_sha256",
            "raw_prediction_units_sha256",
            "terminal_escalation_receipt",
        )
        if key in record
    }


def review_queue_v2_records(
    v1_records: Iterable[Mapping[str, Any]],
    *,
    normalized_responses: Mapping[tuple[str, int], str] | None = None,
) -> tuple[JsonRecord, ...]:
    """Project the merged v1 queue into candidate-aware, typed-reason items.

    Unit rows translate one-for-one and keep their ``review_id``.  Every
    terminal structural-review row for a candidate collapses into a single
    candidate-subject technical item, because a reconstruction failure is one
    fact about the reviewer run, not N independent findings about N units.

    ``normalized_responses`` optionally supplies rejected reviewer bodies keyed
    by ``(candidate_id, attempt_ordinal)``.  Each is authenticated against the
    commitment already in the queue row before being parsed; supplying nothing
    yields no suggested actions rather than a guess.
    """

    responses = dict(normalized_responses or {})
    unit_items: list[JsonRecord] = []
    groups: dict[str, _TerminalGroup] = {}
    for record in v1_records:
        candidate_id = required_str(record, "candidate_id")
        case_id = required_str(record, "case_id")
        unit_id = required_str(record, "unit_id")
        review_id = required_str(record, "review_id")
        code = review_reason_code(record)
        reason = _reason_for(code)
        terminal = _terminal_record(record)
        group: _TerminalGroup | None = None
        if terminal is not None:
            terminal_item = _as_record(terminal.get("review_item"))
            if terminal_item is None:
                raise ReviewQueueError("terminal review row lacks a review_item")
            escalation_sha256 = required_str(terminal, "terminal_escalation_sha256")
            group = groups.get(candidate_id)
            if group is None:
                group = _TerminalGroup(
                    candidate_id=candidate_id,
                    case_id=case_id,
                    review_item=dict(terminal_item),
                    escalation_sha256=escalation_sha256,
                    provenance=_provenance(terminal),
                    affected_unit_ids=[],
                    absorbed_review_ids=[],
                    terminal_evidence_review_ids=[],
                )
                groups[candidate_id] = group
            elif group.escalation_sha256 != escalation_sha256:
                # Two different reviewer runs cannot collapse into one item
                # without silently choosing which evidence a lawyer sees.
                raise ReviewQueueError(
                    f"conflicting terminal escalations for candidate {candidate_id}"
                )
            if unit_id not in group.affected_unit_ids:
                group.affected_unit_ids.append(unit_id)
            group.terminal_evidence_review_ids.append(review_id)
        if reason.subject is ReviewSubject.CANDIDATE:
            # A standalone terminal row raises no substantive question of its
            # own, so the candidate item takes its place in the projection.
            if group is None:
                raise ReviewQueueError(
                    f"terminal review row lacks terminal evidence: {review_id}"
                )
            group.absorbed_review_ids.append(review_id)
            continue
        unit_items.append(
            {
                "schema_version": SCHEMA_VERSION,
                "status": required_str(record, "status"),
                "review_id": review_id,
                "review_subject": ReviewSubject.UNIT.value,
                "candidate_id": candidate_id,
                "case_id": case_id,
                "unit_id": unit_id,
                "reason": reason.to_record(),
                "allowed_actions": [action.value for action in reason.allowed_actions],
                "suggested_actions": [],
                "review_item": _as_record(record.get("review_item")) or {},
                "source_review_ids": [review_id],
            }
        )
    candidate_items = [
        _candidate_item(group, responses=responses) for group in groups.values()
    ]
    return (*unit_items, *candidate_items)


def _candidate_item(
    group: _TerminalGroup, *, responses: Mapping[tuple[str, int], str]
) -> JsonRecord:
    reason = _reason_for(TERMINAL_ROUTE_REASON)
    commitments, codes, fields = _attempt_commitments(group.review_item)
    if not commitments:
        raise ReviewQueueError(
            f"terminal escalation for {group.candidate_id} records no failed attempt"
        )
    if len(set(codes)) == 1:
        validator_code = codes[0]
        invalid_field = fields[0]
    else:
        # Attempts failed different validators; naming one would misdescribe the
        # run, so the per-attempt detail below stays the only specific claim.
        validator_code = MIXED_VALIDATOR_CODE
        invalid_field = None
    safe_flags: list[JsonRecord] = []
    for commitment in commitments:
        body = responses.get((group.candidate_id, commitment["attempt_ordinal"]))
        if body is None:
            continue
        safe_flags.extend(
            safe_parsed_structural_flags(
                body,
                expected_sha256=str(commitment["normalized_response_sha256"]),
                frozen_unit_ids=group.affected_unit_ids,
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_adjudication",
        "review_id": (
            f"{group.candidate_id}:structural-terminal:{group.escalation_sha256[:16]}"
        ),
        "review_subject": ReviewSubject.CANDIDATE.value,
        "candidate_id": group.candidate_id,
        "case_id": group.case_id,
        "reason": reason.to_record(),
        "allowed_actions": [action.value for action in reason.allowed_actions],
        "suggested_actions": _suggested_actions(safe_flags),
        "review_item": {
            "validator_code": validator_code,
            "invalid_field": invalid_field,
            "attempt_commitments": commitments,
            "safe_parsed_flags": safe_flags,
            "affected_unit_ids": list(group.affected_unit_ids),
            "notes": group.review_item.get("notes"),
            "reviewer_prompt_sha256": group.review_item.get("reviewer_prompt_sha256"),
            "predecision_source_commitments": list(
                _as_sequence(group.review_item.get("predecision_source_commitments"))
                or ()
            ),
        },
        "affected_unit_ids": list(group.affected_unit_ids),
        "terminal_escalation_sha256": group.escalation_sha256,
        "source_review_ids": list(group.absorbed_review_ids),
        "terminal_evidence_review_ids": list(group.terminal_evidence_review_ids),
        **group.provenance,
    }


def verify_review_queue_v2_coverage(
    v1_records: Iterable[Mapping[str, Any]],
    v2_records: Iterable[Mapping[str, Any]],
) -> None:
    """Recheck that the projection neither drops nor invents review work.

    Coverage is keyed on ``review_id`` because that is the queue's identity:
    every v1 row must be represented by exactly one v2 item, and every unit
    named by v1 must still be named by v2.  This runs independently of the
    projection so a bug in it cannot certify itself.
    """

    v1_by_id: dict[str, Mapping[str, Any]] = {}
    v1_units: set[tuple[str, str]] = set()
    for record in v1_records:
        if record.get("schema_version") != V1_SCHEMA_VERSION:
            raise ReviewQueueError("review queue v1 record has the wrong schema")
        review_id = required_str(record, "review_id")
        if review_id in v1_by_id:
            raise ReviewQueueError(f"duplicate v1 review_id: {review_id}")
        v1_by_id[review_id] = record
        v1_units.add(
            (required_str(record, "candidate_id"), required_str(record, "unit_id"))
        )
    covered: set[str] = set()
    v2_units: set[tuple[str, str]] = set()
    for record in v2_records:
        if record.get("schema_version") != SCHEMA_VERSION:
            raise ReviewQueueError("review queue v2 record has the wrong schema")
        candidate_id = required_str(record, "candidate_id")
        raw_subject = required_str(record, "review_subject")
        try:
            subject = ReviewSubject(raw_subject)
        except ValueError as error:
            raise ReviewQueueError(
                f"review queue v2 record has an unknown review_subject: {raw_subject}"
            ) from error
        if subject is ReviewSubject.UNIT:
            v2_units.add((candidate_id, required_str(record, "unit_id")))
        else:
            for unit_id in _as_sequence(record.get("affected_unit_ids")) or ():
                v2_units.add((candidate_id, str(unit_id)))
        source_ids = _as_sequence(record.get("source_review_ids"))
        if source_ids is None:
            raise ReviewQueueError("review queue v2 record lacks source_review_ids")
        for source_id in source_ids:
            source = str(source_id)
            if source not in v1_by_id:
                raise ReviewQueueError(f"review queue v2 invents review work: {source}")
            if source in covered:
                raise ReviewQueueError(
                    f"review queue v2 covers a review twice: {source}"
                )
            covered.add(source)
    missing = sorted(set(v1_by_id) - covered)
    if missing:
        raise ReviewQueueError(f"review queue v2 drops review work: {missing}")
    dropped_units = sorted(v1_units - v2_units)
    if dropped_units:
        raise ReviewQueueError(f"review queue v2 drops units: {dropped_units}")
    invented_units = sorted(v2_units - v1_units)
    if invented_units:
        raise ReviewQueueError(f"review queue v2 invents units: {invented_units}")

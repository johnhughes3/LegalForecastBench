"""Provider-free attorney packet for a frozen Stage A review bundle.

The v1 bundle remains the only review/adjudication authority.  Queue v2 is a
reviewer-facing projection only: this module authenticates its exact sidecar
bytes and makes terminal structural-review failures readable once per
candidate without turning them into candidate-level actions.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.contracts import (
    SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V1,
    SUCCESSOR_ATTORNEY_PACKET_VIEW_V1,
    UNITIZATION_REVIEW_BUNDLE_V1,
    UNITIZATION_REVIEW_QUEUE_V2,
    PrefixedSha256,
)
from legalforecast.unitization.review_queue import (
    REVIEW_REASONS,
    TERMINAL_ROUTE_REASON,
    ReviewAction,
    ReviewSubject,
    classify_structural_validator_failure,
)

JsonRecord = dict[str, Any]
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}")


class AttorneyPacketError(ValueError):
    """Raised when the private packet inputs do not make an honest packet."""


@dataclass(frozen=True, slots=True)
class SuccessorAttorneyPacket:
    """Authenticated manifest and a derived, explicitly observational view."""

    manifest: JsonRecord
    attorney_view: JsonRecord


def build_successor_attorney_packet(
    authoritative_v1_bundle_bytes: bytes,
    observational_v2_queue_bytes: bytes,
) -> SuccessorAttorneyPacket:
    """Authenticate exact inputs and derive a candidate-grouped attorney view.

    The caller supplies bytes rather than parsed values deliberately.  The
    manifest therefore binds the exact frozen v1 bundle and exact v2 sidecar,
    including whitespace and record ordering.  This function performs neither
    provider, retrieval, purchase, evaluation, freeze, nor dispatch work.
    """

    bundle_records = _jsonl_records(authoritative_v1_bundle_bytes, "v1 bundle")
    queue_records = _jsonl_records(observational_v2_queue_bytes, "v2 review queue")
    bundle_by_id = _validate_bundle(bundle_records)
    _validate_queue_lineage(bundle_by_id, queue_records)
    attorney_view = _build_attorney_view(bundle_records, queue_records)
    manifest: JsonRecord = {
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V1),
        "authoritative_v1_bundle": _input_commitment(
            authoritative_v1_bundle_bytes,
            schema_version=str(UNITIZATION_REVIEW_BUNDLE_V1),
            count_field="review_count",
            count=len(bundle_records),
        ),
        "observational_v2_review_queue": _input_commitment(
            observational_v2_queue_bytes,
            schema_version=str(UNITIZATION_REVIEW_QUEUE_V2),
            count_field="record_count",
            count=len(queue_records),
        ),
        "review_id_coverage": {
            "authoritative_v1_review_count": len(bundle_by_id),
            "observational_v2_source_review_count": len(bundle_by_id),
            "exactly_once": True,
        },
        "provider_free": True,
        "authoritative_adjudication_source": "unitization_review_bundle_v1",
        "observational_sidecar": "unitization_review_queue_v2",
    }
    return SuccessorAttorneyPacket(manifest=manifest, attorney_view=attorney_view)


def _input_commitment(
    payload: bytes,
    *,
    schema_version: str,
    count_field: str,
    count: int,
) -> JsonRecord:
    return {
        "schema_version": schema_version,
        "byte_count": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        count_field: count,
    }


def _jsonl_records(payload: bytes, label: str) -> tuple[JsonRecord, ...]:
    if not payload or not payload.endswith(b"\n"):
        raise AttorneyPacketError(f"{label} must be nonempty newline-terminated JSONL")
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise AttorneyPacketError(
                f"{label} line {line_number} is not JSON"
            ) from exc
        if not isinstance(value, dict):
            raise AttorneyPacketError(f"{label} line {line_number} must be an object")
        records.append(cast(JsonRecord, value))
    return tuple(records)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> JsonRecord:
    record: JsonRecord = {}
    for key, value in pairs:
        if key in record:
            raise AttorneyPacketError(f"JSON object contains duplicate key {key!r}")
        record[key] = value
    return record


def _validate_bundle(records: Sequence[Mapping[str, object]]) -> dict[str, JsonRecord]:
    by_id: dict[str, JsonRecord] = {}
    for record in records:
        if record.get("schema_version") != str(UNITIZATION_REVIEW_BUNDLE_V1):
            raise AttorneyPacketError("v1 bundle has unsupported schema")
        review_id = _required_str(record, "review_id", "v1 bundle")
        if review_id in by_id:
            raise AttorneyPacketError(f"duplicate v1 bundle review_id: {review_id}")
        _required_str(record, "candidate_id", "v1 bundle")
        _required_str(record, "case_id", "v1 bundle")
        by_id[review_id] = dict(record)
    return by_id


def _validate_queue_lineage(
    bundle_by_id: Mapping[str, JsonRecord],
    queue_records: Sequence[Mapping[str, object]],
) -> None:
    covered: set[str] = set()
    for record in queue_records:
        if record.get("schema_version") != str(UNITIZATION_REVIEW_QUEUE_V2):
            raise AttorneyPacketError("v2 review queue has unsupported schema")
        candidate_id = _required_str(record, "candidate_id", "v2 review queue")
        case_id = _required_str(record, "case_id", "v2 review queue")
        source_ids = _string_sequence(record, "source_review_ids")
        for source_id in source_ids:
            if not source_id:
                raise AttorneyPacketError(
                    "v2 source_review_ids must be nonempty strings"
                )
            _bundle_for_source(
                bundle_by_id, source_id, candidate_id, case_id, "source_review_ids"
            )
            if source_id in covered:
                raise AttorneyPacketError(
                    f"v2 queue covers a v1 review_id more than once: {source_id}"
                )
            covered.add(source_id)
        subject = _required_str(record, "review_subject", "v2 review queue")
        if subject == "unit":
            _validate_unit_lineage(record, source_ids, bundle_by_id)
        elif subject == "candidate":
            _validate_terminal_lineage(record, source_ids, bundle_by_id)
        else:
            raise AttorneyPacketError(f"unsupported v2 review subject: {subject}")
    if set(bundle_by_id) != covered:
        raise AttorneyPacketError(
            "v2 queue does not cover every v1 review_id exactly once"
        )


def _validate_unit_lineage(
    record: Mapping[str, object],
    source_ids: Sequence[str],
    bundle_by_id: Mapping[str, JsonRecord],
) -> None:
    if len(source_ids) != 1:
        raise AttorneyPacketError("v2 unit item must have exactly one source_review_id")
    review_id = _required_str(record, "review_id", "v2 unit item")
    if review_id != source_ids[0]:
        raise AttorneyPacketError(
            "v2 unit item review_id must equal its source_review_id"
        )
    unit_id = _required_str(record, "unit_id", "v2 unit item")
    bundle = bundle_by_id[source_ids[0]]
    review_item = _required_mapping(bundle, "review_item", "v1 bundle")
    if _required_str(review_item, "unit_id", "v1 bundle review_item") != unit_id:
        raise AttorneyPacketError("v2 unit item unit_id differs from its v1 review")
    route_reason = _required_str(bundle, "route_reason", "v1 bundle")
    reason = REVIEW_REASONS.get(route_reason)
    if reason is None or reason.subject is not ReviewSubject.UNIT:
        raise AttorneyPacketError(
            "v1 bundle route_reason cannot project to a unit item"
        )
    if record.get("reason") != reason.to_record():
        raise AttorneyPacketError("v2 unit item reason differs from its v1 projection")
    if record.get("allowed_actions") != [
        action.value for action in reason.allowed_actions
    ]:
        raise AttorneyPacketError(
            "v2 unit item allowed_actions differ from its v1 projection"
        )
    if record.get("suggested_actions") != []:
        raise AttorneyPacketError("v2 unit item must not advertise suggestions")


def _validate_terminal_lineage(
    record: Mapping[str, object],
    source_ids: Sequence[str],
    bundle_by_id: Mapping[str, JsonRecord],
) -> None:
    terminal_reason = REVIEW_REASONS[TERMINAL_ROUTE_REASON].to_record()
    if record.get("reason") != terminal_reason:
        raise AttorneyPacketError("candidate v2 item has unsupported terminal reason")
    if record.get("allowed_actions") != []:
        raise AttorneyPacketError(
            "candidate v2 item must not advertise candidate actions"
        )
    candidate_id = _required_str(record, "candidate_id", "v2 terminal item")
    case_id = _required_str(record, "case_id", "v2 terminal item")
    digest = _required_str(record, "terminal_escalation_sha256", "v2 terminal item")
    if _LOWER_SHA256.fullmatch(digest) is None:
        raise AttorneyPacketError("v2 terminal item has invalid escalation digest")
    if _required_str(record, "review_id", "v2 terminal item") != (
        f"{candidate_id}:structural-terminal:{digest[:16]}"
    ):
        raise AttorneyPacketError("v2 terminal item review_id differs from escalation")
    affected_unit_ids = _string_sequence(record, "affected_unit_ids")
    if not affected_unit_ids or len(set(affected_unit_ids)) != len(affected_unit_ids):
        raise AttorneyPacketError("v2 terminal item affected_unit_ids must be unique")
    evidence_ids = _string_sequence(record, "terminal_evidence_review_ids")
    if not evidence_ids or len(set(evidence_ids)) != len(evidence_ids):
        raise AttorneyPacketError(
            "v2 terminal item terminal_evidence_review_ids must be unique"
        )
    if not set(source_ids).issubset(evidence_ids):
        raise AttorneyPacketError("v2 terminal source IDs must be terminal evidence")
    evidence_unit_ids: set[str] = set()
    for review_id in evidence_ids:
        bundle = _bundle_for_source(
            bundle_by_id,
            review_id,
            candidate_id,
            case_id,
            "terminal_evidence_review_ids",
        )
        review_item = _required_mapping(bundle, "review_item", "v1 bundle")
        unit_id = _required_str(review_item, "unit_id", "v1 bundle review_item")
        evidence_unit_ids.add(unit_id)
    if set(affected_unit_ids) != evidence_unit_ids:
        raise AttorneyPacketError(
            "v2 terminal affected_unit_ids differ from terminal v1 evidence"
        )
    _validate_suggested_actions(record, affected_unit_ids)
    provenance = _required_mapping(record, "review_item", "v2 terminal item")
    attempts = _string_or_object_sequence(provenance, "attempt_commitments")
    if not attempts:
        raise AttorneyPacketError("v2 terminal item lacks attempt commitments")
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            raise AttorneyPacketError(
                "v2 terminal attempt commitment must be an object"
            )
        typed_attempt = cast(Mapping[str, object], attempt)
        _validate_attempt_commitment(typed_attempt)


def _validate_attempt_commitment(attempt: Mapping[str, object]) -> None:
    expected_fields = {
        "attempt_ordinal",
        "raw_response_sha256",
        "normalized_response_sha256",
        "validator_code",
        "invalid_field",
        "failure_type",
        "failure_message",
    }
    if set(attempt) != expected_fields:
        raise AttorneyPacketError("v2 terminal attempt commitment field set is invalid")
    ordinal = attempt.get("attempt_ordinal")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        raise AttorneyPacketError("v2 terminal attempt ordinal is invalid")
    for field in ("raw_response_sha256", "normalized_response_sha256"):
        digest = _required_str(attempt, field, "v2 terminal attempt")
        try:
            PrefixedSha256(digest)
        except ValueError as exc:
            raise AttorneyPacketError(
                f"v2 terminal attempt {field} is not a prefixed SHA-256"
            ) from exc
    failure_type = _required_str(attempt, "failure_type", "v2 terminal attempt")
    failure_message = _required_str(attempt, "failure_message", "v2 terminal attempt")
    expected_code, expected_field = classify_structural_validator_failure(
        failure_type=failure_type, failure_message=failure_message
    )
    if attempt.get("validator_code") != expected_code:
        raise AttorneyPacketError("v2 terminal attempt validator_code is invalid")
    if attempt.get("invalid_field") != expected_field:
        raise AttorneyPacketError("v2 terminal attempt invalid_field is invalid")


def _validate_suggested_actions(
    record: Mapping[str, object], affected_unit_ids: Sequence[str]
) -> None:
    suggestions = _string_or_object_sequence(record, "suggested_actions")
    allowed_actions = {
        ReviewAction.ADD.value,
        ReviewAction.SPLIT.value,
        ReviewAction.MERGE.value,
        ReviewAction.DROP.value,
    }
    for suggestion in suggestions:
        if not isinstance(suggestion, Mapping):
            raise AttorneyPacketError("v2 terminal suggestion must be an object")
        typed_suggestion = cast(Mapping[str, object], suggestion)
        if set(typed_suggestion) != {
            "authoritative",
            "action",
            "affected_unit_ids",
            "rationale",
            "source",
        }:
            raise AttorneyPacketError("v2 terminal suggestion field set is invalid")
        if typed_suggestion.get("authoritative") is not False:
            raise AttorneyPacketError(
                "v2 terminal suggestion must be non-authoritative"
            )
        action = _required_str(typed_suggestion, "action", "v2 terminal suggestion")
        if action not in allowed_actions:
            raise AttorneyPacketError("v2 terminal suggestion action is unsupported")
        _required_str(typed_suggestion, "rationale", "v2 terminal suggestion")
        if typed_suggestion.get("source") != "rejected_structural_review_response":
            raise AttorneyPacketError("v2 terminal suggestion source is unsupported")
        suggested_units = _string_sequence(typed_suggestion, "affected_unit_ids")
        if not suggested_units or len(set(suggested_units)) != len(suggested_units):
            raise AttorneyPacketError("v2 terminal suggestion lacks affected units")
        if not set(suggested_units).issubset(affected_unit_ids):
            raise AttorneyPacketError(
                "v2 terminal suggestion names an out-of-cohort unit"
            )


def _bundle_for_source(
    bundle_by_id: Mapping[str, JsonRecord],
    review_id: str,
    candidate_id: str,
    case_id: str,
    relation: str,
) -> JsonRecord:
    bundle = bundle_by_id.get(review_id)
    if bundle is None:
        raise AttorneyPacketError(f"v2 queue invents v1 review_id: {review_id}")
    if (
        _required_str(bundle, "candidate_id", "v1 bundle") != candidate_id
        or _required_str(bundle, "case_id", "v1 bundle") != case_id
    ):
        raise AttorneyPacketError(f"v2 {relation} crosses v1 candidate or case")
    return bundle


def _string_sequence(record: Mapping[str, object], field: str) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AttorneyPacketError(f"v2 queue item lacks {field}")
    items = cast(Sequence[object], value)
    strings = tuple(item for item in items if isinstance(item, str) and item)
    if len(strings) != len(items):
        raise AttorneyPacketError(f"v2 queue {field} must be nonempty strings")
    return strings


def _string_or_object_sequence(
    record: Mapping[str, object], field: str
) -> tuple[object, ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AttorneyPacketError(f"v2 terminal item lacks {field}")
    return tuple(cast(Sequence[object], value))


def _required_mapping(
    record: Mapping[str, object], field: str, label: str
) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise AttorneyPacketError(f"{label} {field} must be an object")
    return cast(Mapping[str, object], value)


def _build_attorney_view(
    bundle_records: Sequence[JsonRecord], queue_records: Sequence[JsonRecord]
) -> JsonRecord:
    bundles_by_candidate: dict[str, list[JsonRecord]] = defaultdict(list)
    cases_by_candidate: dict[str, str] = {}
    for bundle in bundle_records:
        candidate_id = _required_str(bundle, "candidate_id", "v1 bundle")
        case_id = _required_str(bundle, "case_id", "v1 bundle")
        existing_case_id = cases_by_candidate.setdefault(candidate_id, case_id)
        if existing_case_id != case_id:
            raise AttorneyPacketError(
                f"v1 bundle has inconsistent case_id: {candidate_id}"
            )
        bundles_by_candidate[candidate_id].append(bundle)

    units_by_candidate: dict[str, list[JsonRecord]] = defaultdict(list)
    terminal_by_candidate: dict[str, JsonRecord] = {}
    for item in queue_records:
        candidate_id = _required_str(item, "candidate_id", "v2 review queue")
        case_id = _required_str(item, "case_id", "v2 review queue")
        if cases_by_candidate.get(candidate_id) != case_id:
            raise AttorneyPacketError(
                f"v2 queue case_id differs from v1 bundle: {candidate_id}"
            )
        subject = _required_str(item, "review_subject", "v2 review queue")
        if subject == "unit":
            units_by_candidate[candidate_id].append(item)
            continue
        if subject != "candidate":
            raise AttorneyPacketError(f"unsupported v2 review subject: {subject}")
        reason = item.get("reason")
        if not isinstance(reason, Mapping):
            raise AttorneyPacketError("candidate v2 item must be a technical item")
        typed_reason = cast(Mapping[str, object], reason)
        if typed_reason.get("class") != "technical":
            raise AttorneyPacketError("candidate v2 item must be a technical item")
        allowed_actions = item.get("allowed_actions")
        if allowed_actions != []:
            raise AttorneyPacketError(
                "candidate v2 item must not advertise candidate actions"
            )
        if candidate_id in terminal_by_candidate:
            raise AttorneyPacketError(
                f"v2 queue has more than one terminal technical item: {candidate_id}"
            )
        terminal_by_candidate[candidate_id] = item

    candidates: list[JsonRecord] = []
    for candidate_id in sorted(bundles_by_candidate):
        authoritative = bundles_by_candidate[candidate_id]
        candidates.append(
            {
                "candidate_id": candidate_id,
                "case_id": cases_by_candidate[candidate_id],
                "authoritative_v1": {
                    "review_ids": [
                        _required_str(record, "review_id", "v1 bundle")
                        for record in authoritative
                    ],
                    "bundle_records": authoritative,
                },
                "observational_v2": {
                    "unit_items": units_by_candidate[candidate_id],
                    **(
                        {"terminal_technical_item": terminal_by_candidate[candidate_id]}
                        if candidate_id in terminal_by_candidate
                        else {}
                    ),
                },
            }
        )
    return {
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_VIEW_V1),
        "authoritative_source": str(UNITIZATION_REVIEW_BUNDLE_V1),
        "observational_source": str(UNITIZATION_REVIEW_QUEUE_V2),
        "candidates": candidates,
    }


def _required_str(record: Mapping[str, object], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise AttorneyPacketError(f"{label} {field} must be a nonempty string")
    return value

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
    LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1,
    SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V1,
    SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V2,
    SUCCESSOR_ATTORNEY_PACKET_VIEW_V1,
    SUCCESSOR_ATTORNEY_PACKET_VIEW_V2,
    UNITIZATION_REVIEW_BUNDLE_V1,
    UNITIZATION_REVIEW_QUEUE_V2,
    UNITIZER_TERMINAL_REVIEW_BUNDLE_V1,
    UNITIZER_TERMINAL_REVIEW_QUEUE_V1,
    PrefixedSha256,
)
from legalforecast.unitization.review_queue import (
    REVIEW_REASONS,
    TERMINAL_ROUTE_REASON,
    ReviewAction,
    ReviewSubject,
    classify_structural_validator_failure,
)
from legalforecast.unitization.unitizer_terminal_review import (
    UnitizerTerminalReviewError,
    build_unitizer_terminal_review_bundle,
    build_unitizer_terminal_review_queue_record,
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


def build_successor_attorney_packet_with_unitizer_terminals(
    authoritative_v1_bundle_bytes: bytes,
    observational_v2_queue_bytes: bytes,
    unitizer_terminal_receipt_bytes: bytes,
    unitizer_terminal_queue_bytes: bytes,
    unitizer_terminal_bundle_bytes: bytes,
) -> SuccessorAttorneyPacket:
    """Build packet v2 by adding candidates with no accepted Stage A units.

    The original packet builder and both frozen unit-review inputs remain
    unchanged.  Terminal-unitizer candidates enter through separate exact-byte
    inputs because they have no frozen unit row to place honestly in v1/v2.
    """

    if authoritative_v1_bundle_bytes or observational_v2_queue_bytes:
        if not authoritative_v1_bundle_bytes or not observational_v2_queue_bytes:
            raise AttorneyPacketError(
                "ordinary v1 bundle and v2 queue must both be empty or both be nonempty"
            )
        base = build_successor_attorney_packet(
            authoritative_v1_bundle_bytes, observational_v2_queue_bytes
        )
    else:
        base = _empty_successor_attorney_packet(
            authoritative_v1_bundle_bytes, observational_v2_queue_bytes
        )
    terminal_receipts = _jsonl_records(
        unitizer_terminal_receipt_bytes, "unitizer terminal escalation receipts"
    )
    terminal_queue = _jsonl_records(
        unitizer_terminal_queue_bytes, "unitizer terminal review queue"
    )
    terminal_bundles = _jsonl_records(
        unitizer_terminal_bundle_bytes, "unitizer terminal review bundle"
    )
    terminals = _validated_unitizer_terminals(
        terminal_receipts, terminal_queue, terminal_bundles
    )
    existing_candidates = {
        _required_str(candidate, "candidate_id", "attorney view candidate")
        for candidate in cast(
            Sequence[Mapping[str, object]], base.attorney_view["candidates"]
        )
    }
    overlap = existing_candidates.intersection(terminals)
    if overlap:
        raise AttorneyPacketError(
            "candidate appears in both frozen-unit and terminal-unitizer review: "
            + ", ".join(sorted(overlap))
        )
    candidates = list(cast(Sequence[JsonRecord], base.attorney_view["candidates"]))
    for candidate_id in sorted(terminals):
        queue_record, bundle_record = terminals[candidate_id]
        candidates.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(
                    queue_record, "case_id", "unitizer terminal queue"
                ),
                "unitizer_terminal": {
                    "queue_record": queue_record,
                    "bundle_record": bundle_record,
                },
            }
        )
    candidates.sort(key=lambda candidate: str(candidate["candidate_id"]))
    manifest = {
        **base.manifest,
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V2),
        "unitizer_terminal_escalation_receipts": _input_commitment(
            unitizer_terminal_receipt_bytes,
            schema_version=str(LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1),
            count_field="record_count",
            count=len(terminal_receipts),
        ),
        "unitizer_terminal_review_queue": _input_commitment(
            unitizer_terminal_queue_bytes,
            schema_version=str(UNITIZER_TERMINAL_REVIEW_QUEUE_V1),
            count_field="record_count",
            count=len(terminal_queue),
        ),
        "unitizer_terminal_review_bundle": _input_commitment(
            unitizer_terminal_bundle_bytes,
            schema_version=str(UNITIZER_TERMINAL_REVIEW_BUNDLE_V1),
            count_field="record_count",
            count=len(terminal_bundles),
        ),
        "unitizer_terminal_candidate_count": len(terminals),
    }
    attorney_view = {
        **base.attorney_view,
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_VIEW_V2),
        "unitizer_terminal_authoritative_source": str(
            UNITIZER_TERMINAL_REVIEW_BUNDLE_V1
        ),
        "candidates": candidates,
    }
    return SuccessorAttorneyPacket(manifest=manifest, attorney_view=attorney_view)


def _empty_successor_attorney_packet(
    authoritative_v1_bundle_bytes: bytes,
    observational_v2_queue_bytes: bytes,
) -> SuccessorAttorneyPacket:
    """Construct the authenticated empty ordinary base used only by packet v2."""

    manifest: JsonRecord = {
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V1),
        "authoritative_v1_bundle": _input_commitment(
            authoritative_v1_bundle_bytes,
            schema_version=str(UNITIZATION_REVIEW_BUNDLE_V1),
            count_field="review_count",
            count=0,
        ),
        "observational_v2_review_queue": _input_commitment(
            observational_v2_queue_bytes,
            schema_version=str(UNITIZATION_REVIEW_QUEUE_V2),
            count_field="record_count",
            count=0,
        ),
        "review_id_coverage": {
            "authoritative_v1_review_count": 0,
            "observational_v2_source_review_count": 0,
            "exactly_once": True,
        },
        "provider_free": True,
        "authoritative_adjudication_source": "unitization_review_bundle_v1",
        "observational_sidecar": "unitization_review_queue_v2",
    }
    attorney_view: JsonRecord = {
        "schema_version": str(SUCCESSOR_ATTORNEY_PACKET_VIEW_V1),
        "authoritative_source": str(UNITIZATION_REVIEW_BUNDLE_V1),
        "observational_source": str(UNITIZATION_REVIEW_QUEUE_V2),
        "candidates": [],
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


def _validated_unitizer_terminals(
    receipt_records: Sequence[Mapping[str, object]],
    queue_records: Sequence[Mapping[str, object]],
    bundle_records: Sequence[Mapping[str, object]],
) -> dict[str, tuple[JsonRecord, JsonRecord]]:
    if not queue_records:
        raise AttorneyPacketError("unitizer terminal review queue must be nonempty")
    queue_by_id: dict[str, JsonRecord] = {}
    for queue in queue_records:
        if queue.get("schema_version") != str(UNITIZER_TERMINAL_REVIEW_QUEUE_V1):
            raise AttorneyPacketError(
                "unitizer terminal review queue has unsupported schema"
            )
        review_id = _required_str(queue, "review_id", "unitizer terminal queue")
        if review_id in queue_by_id:
            raise AttorneyPacketError(
                f"duplicate unitizer terminal review_id: {review_id}"
            )
        if queue.get("status") != "pending_adjudication":
            raise AttorneyPacketError("unitizer terminal queue item is not pending")
        if queue.get("review_subject") != "candidate":
            raise AttorneyPacketError(
                "unitizer terminal queue item is not candidate-level"
            )
        if queue.get("allowed_actions") != ["ADD", "CANDIDATE-EXCLUSION"]:
            raise AttorneyPacketError(
                "unitizer terminal queue allowed actions are invalid"
            )
        if queue.get("suggested_actions") != []:
            raise AttorneyPacketError(
                "unitizer terminal queue invents a legal suggestion"
            )
        digest = _required_str(
            queue, "terminal_escalation_sha256", "unitizer terminal queue"
        )
        if _LOWER_SHA256.fullmatch(digest) is None:
            raise AttorneyPacketError("unitizer terminal escalation digest is invalid")
        candidate_id = _required_str(queue, "candidate_id", "unitizer terminal queue")
        if review_id != f"{candidate_id}:unitizer-terminal:{digest[:16]}":
            raise AttorneyPacketError(
                "unitizer terminal review_id differs from escalation"
            )
        _required_str(queue, "case_id", "unitizer terminal queue")
        review_item = _required_mapping(queue, "review_item", "unitizer terminal queue")
        if "prompt" in review_item or "prediction_units" in queue:
            raise AttorneyPacketError(
                "unitizer terminal queue leaks or invents content"
            )
        queue_by_id[review_id] = dict(queue)

    receipt_queues: dict[str, tuple[JsonRecord, Mapping[str, object]]] = {}
    for receipt in receipt_records:
        try:
            derived_queue = build_unitizer_terminal_review_queue_record(receipt)
        except UnitizerTerminalReviewError as exc:
            raise AttorneyPacketError(
                f"unitizer terminal receipt is invalid: {exc}"
            ) from exc
        review_id = _required_str(derived_queue, "review_id", "receipt-derived queue")
        if review_id in receipt_queues:
            raise AttorneyPacketError(
                f"duplicate unitizer terminal receipt: {review_id}"
            )
        receipt_queues[review_id] = (derived_queue, receipt)
    if set(receipt_queues) != set(queue_by_id):
        raise AttorneyPacketError("unitizer terminal receipt coverage differs")
    for review_id, queue in queue_by_id.items():
        if receipt_queues[review_id][0] != queue:
            raise AttorneyPacketError(
                "unitizer terminal receipt-derived queue differs from supplied queue"
            )

    bundle_by_id: dict[str, JsonRecord] = {}
    for bundle in bundle_records:
        if bundle.get("schema_version") != str(UNITIZER_TERMINAL_REVIEW_BUNDLE_V1):
            raise AttorneyPacketError(
                "unitizer terminal review bundle has unsupported schema"
            )
        review_id = _required_str(bundle, "review_id", "unitizer terminal bundle")
        if review_id in bundle_by_id:
            raise AttorneyPacketError(
                f"duplicate unitizer terminal bundle: {review_id}"
            )
        bundle_by_id[review_id] = dict(bundle)
    if set(queue_by_id) != set(bundle_by_id):
        raise AttorneyPacketError("unitizer terminal review bundle coverage differs")

    by_candidate: dict[str, tuple[JsonRecord, JsonRecord]] = {}
    for review_id, queue in queue_by_id.items():
        bundle = bundle_by_id[review_id]
        receipt = receipt_queues[review_id][1]
        for field in (
            "candidate_id",
            "case_id",
            "review_subject",
            "reason",
            "allowed_actions",
            "terminal_escalation_sha256",
            "review_item",
        ):
            if bundle.get(field) != queue.get(field):
                label = (
                    "terminal escalation"
                    if field == "terminal_escalation_sha256"
                    else f"unitizer terminal {field}"
                )
                raise AttorneyPacketError(f"{label} differs between queue and bundle")
        sources = bundle.get("cited_predecision_markdown")
        if (
            not isinstance(sources, Sequence)
            or isinstance(sources, (str, bytes))
            or not sources
        ):
            raise AttorneyPacketError(
                "unitizer terminal bundle lacks predecision sources"
            )
        review_item = _required_mapping(queue, "review_item", "unitizer terminal queue")
        source_ids = _string_sequence(review_item, "predecision_source_document_ids")
        commitments_value = review_item.get("predecision_source_commitments")
        if not isinstance(commitments_value, Sequence) or isinstance(
            commitments_value, (str, bytes)
        ):
            raise AttorneyPacketError(
                "unitizer terminal queue lacks source commitments"
            )
        commitments: dict[str, Mapping[str, object]] = {}
        for commitment in cast(Sequence[object], commitments_value):
            if not isinstance(commitment, Mapping):
                raise AttorneyPacketError(
                    "unitizer terminal source commitment is invalid"
                )
            typed_commitment = cast(Mapping[str, object], commitment)
            commitment_id = _required_str(
                typed_commitment,
                "source_document_id",
                "unitizer terminal source commitment",
            )
            if commitment_id in commitments:
                raise AttorneyPacketError(
                    "unitizer terminal source commitments are duplicated"
                )
            commitments[commitment_id] = typed_commitment
        if tuple(commitments) != source_ids:
            raise AttorneyPacketError(
                "unitizer terminal source commitments differ from source IDs"
            )
        bundled_ids: list[str] = []
        for source in cast(Sequence[object], sources):
            if not isinstance(source, Mapping):
                raise AttorneyPacketError("unitizer terminal bundle source is invalid")
            typed_source = cast(Mapping[str, object], source)
            role = _required_str(
                typed_source, "document_role", "terminal bundle source"
            )
            if role.casefold() in {"decision", "order"}:
                raise AttorneyPacketError(
                    "unitizer terminal bundle includes outcome material"
                )
            _required_str(typed_source, "markdown", "terminal bundle source")
            markdown = _required_str(typed_source, "markdown", "terminal bundle source")
            commitment = commitments[
                _required_str(
                    typed_source,
                    "source_document_id",
                    "terminal bundle source",
                )
            ]
            for field in ("document_role", "docket_entry_number", "description"):
                if typed_source.get(field) != commitment.get(field):
                    raise AttorneyPacketError(
                        "unitizer terminal source metadata differs from commitment"
                    )
            expected_markdown_sha = (
                "sha256:" + hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            )
            if commitment.get("markdown_sha256") != expected_markdown_sha:
                raise AttorneyPacketError(
                    "unitizer terminal source markdown commitment differs"
                )
            bundled_ids.append(
                _required_str(
                    typed_source, "source_document_id", "terminal bundle source"
                )
            )
        if tuple(bundled_ids) != source_ids:
            raise AttorneyPacketError("unitizer terminal bundle source order differs")
        try:
            derived_bundle = build_unitizer_terminal_review_bundle(
                receipt=receipt,
                queue_record=queue,
                predecision_sources=cast(Sequence[Mapping[str, object]], sources),
            )
        except UnitizerTerminalReviewError as exc:
            raise AttorneyPacketError(
                f"unitizer terminal bundle is invalid: {exc}"
            ) from exc
        if derived_bundle != bundle:
            raise AttorneyPacketError(
                "unitizer terminal receipt-derived bundle differs from supplied bundle"
            )
        candidate_id = _required_str(queue, "candidate_id", "unitizer terminal queue")
        if candidate_id in by_candidate:
            raise AttorneyPacketError(
                f"multiple unitizer terminal items: {candidate_id}"
            )
        by_candidate[candidate_id] = (queue, bundle)
    return by_candidate


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

"""Replay-minted post-selection terminal exclusion authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from legalforecast.contracts import (
    ACQUISITION_RUN_CARD_V1,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1,
    EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2,
    EXACT100_ZERO_COST_RECOVERY_REQUEST_V2,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1,
    EXACT100_ZERO_COST_RECOVERY_RUN_V2,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.target_document_eligibility import (
    is_stipulated_or_voluntary_target_document,
)

JsonRecord = dict[str, Any]

EXCLUSION_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1)
RECOVERY_REQUEST_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_REQUEST_V2)
RECOVERY_RECEIPT_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2)
RECOVERY_RUN_CARD_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_RUN_V2)
REST_OBSERVATION_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1)
REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION = str(
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1
)

_TARGET_COUNT = 100
_VERIFICATION_SEAL = object()
_TARGET_ROLES = frozenset(
    {DocumentRole.MTD_NOTICE.value, DocumentRole.MTD_MEMORANDUM.value}
)


class PostSelectionTerminalExclusionError(ValueError):
    """Raised when terminal evidence is not exact and replay-authenticated."""


class TerminalExclusionReason(StrEnum):
    """Closed post-selection terminal grounds."""

    STIPULATED_INELIGIBLE = "stipulated_ineligible"
    TERMINAL_MISSING_CORE_DOCUMENT = "terminal_missing_core_document"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedTerminalExclusionEvidence:
    """One reason-specific terminal fact minted from supplied evidence bytes."""

    candidate_id: str
    source_document_id: str
    reason: TerminalExclusionReason
    evidence_kind: str
    evidence_commitments: Mapping[str, str]
    _verification_seal: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True, init=False)
class VerifiedPostSelectionTerminalExclusions:
    """Canonical terminal subset accepted by the successor projector."""

    records: tuple[JsonRecord, ...]
    records_bytes: bytes
    selection_sha256: str
    commitment_sha256: str
    _verification_seal: object = field(repr=False, compare=False)

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(cast(str, record["candidate_id"]) for record in self.records)


def verify_stipulated_target_evidence(
    *,
    selection_bytes: bytes,
    candidate_id: str,
    source_document_id: str,
    parser_record: Mapping[str, Any],
    parser_requests_bytes: bytes,
    parser_manifest_bytes: bytes,
    parser_run_card_bytes: bytes,
    markdown_bytes: bytes,
    source_document_bytes: bytes,
) -> VerifiedTerminalExclusionEvidence:
    """Mint terminal evidence only for the selected parsed target document."""

    selection = _selection_index(selection_bytes)
    selected = selection.get(candidate_id)
    if selected is None:
        raise PostSelectionTerminalExclusionError(
            "stipulated target candidate is outside the exact selection"
        )
    selected_document = _selected_document(
        selected, source_document_id=source_document_id, label="stipulated target"
    )
    role = _required_text(selected_document, "document_role")
    if role not in _TARGET_ROLES:
        raise PostSelectionTerminalExclusionError(
            "stipulated evidence is not the selected target-motion document"
        )
    parser_requests = _jsonl_records(parser_requests_bytes, "parser requests")
    matching_requests = [
        request
        for request in parser_requests
        if request.get("candidate_id") == candidate_id
        and request.get("source_document_id") == source_document_id
    ]
    if len(matching_requests) != 1:
        raise PostSelectionTerminalExclusionError(
            "stipulated target lacks one authenticated parser request"
        )
    parser_request = matching_requests[0]
    source_sha256 = _sha(source_document_bytes)
    source_byte_count = len(source_document_bytes)
    if (
        not _same_sha(parser_request.get("expected_sha256"), source_sha256)
        or parser_request.get("expected_byte_count") != source_byte_count
        or not _nonempty_text(parser_request.get("input_path"))
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target parser request source commitment mismatch"
        )
    if (
        parser_record.get("candidate_id") != candidate_id
        or parser_record.get("source_document_id") != source_document_id
        or parser_record.get("status") != "succeeded"
        or parser_record.get("quality_flags") != []
        or parser_record.get("input_path") != parser_request["input_path"]
        or not _same_sha(parser_record.get("source_sha256"), source_sha256)
        or parser_record.get("source_byte_count") != source_byte_count
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target parser record is not a clean exact match"
        )
    parser_config = parser_record.get("parser_config")
    extracted = parser_record.get("extracted_text")
    if not isinstance(parser_config, Mapping) or not isinstance(extracted, Mapping):
        raise PostSelectionTerminalExclusionError(
            "stipulated target parser record lacks pinned parser provenance"
        )
    parser_config_record = cast(Mapping[str, object], parser_config)
    extracted_record = cast(Mapping[str, object], extracted)
    expected_text_sha = extracted_record.get("text_sha256")
    if (
        not isinstance(expected_text_sha, str)
        or expected_text_sha.removeprefix("sha256:")
        != hashlib.sha256(markdown_bytes).hexdigest()
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target Markdown differs from the parser record"
        )
    if (
        parser_config_record.get("engine") != "mistral"
        or parser_config_record.get("parser_revision") != EXPECTED_PARSER_REVISION
        or parser_config_record.get("expected_parser_revision")
        != EXPECTED_PARSER_REVISION
        or extracted_record.get("source_document_id") != source_document_id
        or extracted_record.get("extraction_method") != "mistral_parser_markdown"
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target parser record lacks pinned live-Mistral provenance"
        )
    manifest_records = _jsonl_records(parser_manifest_bytes, "parser manifest")
    if sum(record == dict(parser_record) for record in manifest_records) != 1:
        raise PostSelectionTerminalExclusionError(
            "stipulated target parser record is not uniquely committed by the manifest"
        )
    run_card = _json_object(parser_run_card_bytes, "parser run card")
    _verify_stipulated_parser_run_card(
        run_card,
        parser_requests_bytes=parser_requests_bytes,
        parser_manifest_bytes=parser_manifest_bytes,
        parser_record_count=len(manifest_records),
    )
    try:
        markdown = markdown_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PostSelectionTerminalExclusionError(
            "stipulated target Markdown is not UTF-8"
        ) from exc
    if not is_stipulated_or_voluntary_target_document(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        document_role=role,
        markdown=markdown,
    ):
        raise PostSelectionTerminalExclusionError(
            "target document does not prove stipulated or voluntary ineligibility"
        )
    return _mint_terminal_evidence(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        reason=TerminalExclusionReason.STIPULATED_INELIGIBLE,
        evidence_kind="authenticated_selected_target_parser_replay",
        evidence_commitments={
            "selection": _sha(selection_bytes),
            "source_document": _sha(source_document_bytes),
            "parser_requests": _sha(parser_requests_bytes),
            "parser_manifest": _sha(parser_manifest_bytes),
            "parser_run_card": _sha(parser_run_card_bytes),
            "parser_record": _sha(_canonical_bytes(dict(parser_record))),
            "markdown": _sha(markdown_bytes),
        },
    )


def verify_terminal_recovery_evidence(
    *,
    selection_bytes: bytes,
    request: Mapping[str, object],
    request_bytes: bytes,
    receipt: Mapping[str, object],
    receipt_bytes: bytes,
    run_card: Mapping[str, object],
    run_card_bytes: bytes,
    rest_observation: Mapping[str, object],
    rest_observation_bytes: bytes,
    rest_observation_transcript_bytes: bytes,
    rest_observation_response_bytes: bytes,
) -> VerifiedTerminalExclusionEvidence:
    """Mint missing-document terminality from a closed noncharging receipt."""

    _verify_object_bytes(request, request_bytes, "zero-cost recovery request")
    _verify_object_bytes(receipt, receipt_bytes, "zero-cost recovery receipt")
    _verify_object_bytes(run_card, run_card_bytes, "zero-cost recovery run card")
    _verify_object_bytes(
        rest_observation,
        rest_observation_bytes,
        "zero-cost recovery REST observation",
    )
    candidate_id = _required_text(request, "candidate_id")
    source_document_id = _required_text(request, "source_document_id")
    selected = _selection_index(selection_bytes).get(candidate_id)
    if selected is None:
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery candidate is outside the exact selection"
        )
    selected_document = _selected_document(
        selected, source_document_id=source_document_id, label="zero-cost recovery"
    )
    selected_docket_id = _selected_courtlistener_docket_id(selected)
    selected_docket_entry_id = _required_text(
        selected_document, "courtlistener_docket_entry_id"
    )
    if (
        set(request)
        != {
            "schema_version",
            "candidate_id",
            "source_document_id",
            "document_role",
            "courtlistener_docket_id",
            "courtlistener_docket_entry_id",
            "recovery_mode",
            "paid_permitted",
            "pacer_permitted",
            "recap_fetch_permitted",
            "selection_sha256",
        }
        or request.get("schema_version") != RECOVERY_REQUEST_SCHEMA_VERSION
        or request.get("document_role") not in _TARGET_ROLES
        or request.get("recovery_mode") != "courtlistener_rest_noncharging_only"
        or request.get("paid_permitted") is not False
        or request.get("pacer_permitted") is not False
        or request.get("recap_fetch_permitted") is not False
        or request.get("selection_sha256") != _sha(selection_bytes)
        or request.get("document_role") != selected_document.get("document_role")
        or request.get("courtlistener_docket_id") != selected_docket_id
        or request.get("courtlistener_docket_entry_id") != selected_docket_entry_id
    ):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery request is not the closed noncharging contract"
        )
    expected_receipt_fields = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "document_role",
        "recovery_mode",
        "terminal_status",
        "completed",
        "retryable",
        "recovered",
        "paid_activity_executed",
        "pacer_activity_executed",
        "recap_fetch_activity_executed",
        "fee_acknowledged",
        "request_sha256",
        "rest_observation_sha256",
        "rest_observation_transcript_sha256",
    }
    request_sha = _sha(request_bytes)
    if (
        set(receipt) != expected_receipt_fields
        or receipt.get("schema_version") != RECOVERY_RECEIPT_SCHEMA_VERSION
        or receipt.get("candidate_id") != candidate_id
        or receipt.get("source_document_id") != source_document_id
        or receipt.get("document_role") != request.get("document_role")
        or receipt.get("recovery_mode") != request.get("recovery_mode")
        or receipt.get("terminal_status") != "unavailable"
        or receipt.get("completed") is not True
        or receipt.get("retryable") is not False
        or receipt.get("recovered") is not False
        or receipt.get("paid_activity_executed") is not False
        or receipt.get("pacer_activity_executed") is not False
        or receipt.get("recap_fetch_activity_executed") is not False
        or receipt.get("fee_acknowledged") is not False
        or receipt.get("request_sha256") != request_sha
        or receipt.get("rest_observation_sha256") != _sha(rest_observation_bytes)
        or receipt.get("rest_observation_transcript_sha256")
        != _sha(rest_observation_transcript_bytes)
    ):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery receipt does not prove terminal noncharging failure"
        )
    _verify_closed_rest_observation(
        observation=rest_observation,
        transcript_bytes=rest_observation_transcript_bytes,
        response_bytes=rest_observation_response_bytes,
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        document_role=_required_text(request, "document_role"),
        docket_id=selected_docket_id,
        docket_entry_id=selected_docket_entry_id,
        request_sha256=request_sha,
    )
    expected_run_card_fields = {
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "record_count",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "pacer_activity_executed",
        "recap_fetch_activity_executed",
        "fee_acknowledged",
        "input_commitments",
        "output_commitments",
    }
    if (
        set(run_card) != expected_run_card_fields
        or run_card.get("schema_version") != RECOVERY_RUN_CARD_SCHEMA_VERSION
        or run_card.get("stage") != "recover-exact100-target-document-zero-cost"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("record_count") != 1
        or run_card.get("provider_activity_requested") is not True
        or run_card.get("provider_activity_executed") is not True
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or run_card.get("pacer_activity_executed") is not False
        or run_card.get("recap_fetch_activity_executed") is not False
        or run_card.get("fee_acknowledged") is not False
        or run_card.get("input_commitments")
        != {"request": request_sha, "selection": _sha(selection_bytes)}
        or run_card.get("output_commitments")
        != {
            "receipt": _sha(receipt_bytes),
            "rest_observation": _sha(rest_observation_bytes),
            "rest_observation_transcript": _sha(rest_observation_transcript_bytes),
            "rest_observation_response": _sha(rest_observation_response_bytes),
        }
    ):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery run card does not authenticate the terminal receipt"
        )
    return _mint_terminal_evidence(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        reason=TerminalExclusionReason.TERMINAL_MISSING_CORE_DOCUMENT,
        evidence_kind="completed_courtlistener_rest_noncharging_recovery",
        evidence_commitments={
            "selection": _sha(selection_bytes),
            "recovery_request": request_sha,
            "recovery_receipt": _sha(receipt_bytes),
            "recovery_run_card": _sha(run_card_bytes),
            "rest_observation": _sha(rest_observation_bytes),
            "rest_observation_transcript": _sha(rest_observation_transcript_bytes),
            "rest_observation_response": _sha(rest_observation_response_bytes),
        },
    )


def _verify_stipulated_parser_run_card(
    run_card: Mapping[str, object],
    *,
    parser_requests_bytes: bytes,
    parser_manifest_bytes: bytes,
    parser_record_count: int,
) -> None:
    """Require the completed pinned live-Mistral run that committed both JSONLs."""

    execution = run_card.get("parser_execution")
    source_commitments = run_card.get("source_commitments")
    output_commitments = run_card.get("output_commitments")
    if (
        run_card.get("schema_version") != str(ACQUISITION_RUN_CARD_V1)
        or run_card.get("stage") != "parse-documents"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("record_count") != parser_record_count
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or not isinstance(execution, Mapping)
        or not isinstance(source_commitments, Mapping)
        or not isinstance(output_commitments, Mapping)
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target lacks an executed pinned live-Mistral run card"
        )
    execution_record = cast(Mapping[str, object], execution)
    source_commitment_records = cast(Mapping[str, object], source_commitments)
    output_commitment_records = cast(Mapping[str, object], output_commitments)
    if (
        execution_record.get("mode") != "live_mistral"
        or execution_record.get("engine") != "mistral"
        or execution_record.get("parser_revision") != EXPECTED_PARSER_REVISION
        or execution_record.get("fixture_markdown") is not False
    ):
        raise PostSelectionTerminalExclusionError(
            "stipulated target lacks an executed pinned live-Mistral run card"
        )
    _verify_run_card_file_commitment(
        source_commitment_records.get("requests"),
        payload=parser_requests_bytes,
        label="parser requests",
    )
    _verify_run_card_file_commitment(
        output_commitment_records.get("parser_manifest"),
        payload=parser_manifest_bytes,
        label="parser manifest",
    )


def _verify_run_card_file_commitment(
    commitment: object, *, payload: bytes, label: str
) -> None:
    if not isinstance(commitment, Mapping):
        raise PostSelectionTerminalExclusionError(
            f"stipulated target parser run card lacks {label} commitment"
        )
    commitment_record = cast(Mapping[str, object], commitment)
    if not _nonempty_text(commitment_record.get("path")) or not _same_sha(
        commitment_record.get("sha256"), _sha(payload)
    ):
        raise PostSelectionTerminalExclusionError(
            f"stipulated target parser run card lacks {label} commitment"
        )


def _verify_closed_rest_observation(
    *,
    observation: Mapping[str, object],
    transcript_bytes: bytes,
    response_bytes: bytes,
    candidate_id: str,
    source_document_id: str,
    document_role: str,
    docket_id: str,
    docket_entry_id: str,
    request_sha256: str,
) -> None:
    """Verify the versioned, bounded REST transcript instead of a claimed count."""

    transcript = _jsonl_records(
        transcript_bytes, "zero-cost recovery REST observation transcript"
    )
    expected_observation_fields = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "document_role",
        "courtlistener_docket_id",
        "courtlistener_docket_entry_id",
        "request_sha256",
        "terminal_status",
        "completed",
        "retryable",
        "recovered",
        "transcript_sha256",
        "transcript_record_count",
    }
    if (
        set(observation) != expected_observation_fields
        or observation.get("schema_version") != REST_OBSERVATION_SCHEMA_VERSION
        or observation.get("candidate_id") != candidate_id
        or observation.get("source_document_id") != source_document_id
        or observation.get("document_role") != document_role
        or observation.get("courtlistener_docket_id") != docket_id
        or observation.get("courtlistener_docket_entry_id") != docket_entry_id
        or observation.get("request_sha256") != request_sha256
        or observation.get("terminal_status") != "unavailable"
        or observation.get("completed") is not True
        or observation.get("retryable") is not False
        or observation.get("recovered") is not False
        or observation.get("transcript_sha256") != _sha(transcript_bytes)
        or observation.get("transcript_record_count") != 1
        or len(transcript) != 1
    ):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery REST observation is not a closed exact match"
        )
    expected_record_fields = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "document_role",
        "courtlistener_docket_id",
        "courtlistener_docket_entry_id",
        "request_method",
        "request_path",
        "status_code",
        "response_sha256",
        "terminal_status",
        "terminal",
    }
    record = transcript[0]
    if (
        set(record) != expected_record_fields
        or record.get("schema_version") != REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION
        or record.get("candidate_id") != candidate_id
        or record.get("source_document_id") != source_document_id
        or record.get("document_role") != document_role
        or record.get("courtlistener_docket_id") != docket_id
        or record.get("courtlistener_docket_entry_id") != docket_entry_id
        or record.get("request_method") != "GET"
        or record.get("request_path")
        != f"/api/rest/v4/recap-documents/{source_document_id}/"
        or record.get("status_code") != 404
        or record.get("response_sha256") != _sha(response_bytes)
        or record.get("terminal_status") != "unavailable"
        or record.get("terminal") is not True
    ):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery REST observation transcript is not closed"
        )


def _selected_document(
    selected: Mapping[str, object], *, source_document_id: str, label: str
) -> Mapping[str, object]:
    documents = _mapping_sequence(selected.get("documents"), "selection documents")
    matches = [
        document
        for document in documents
        if document.get("source_document_id") == source_document_id
    ]
    if len(matches) != 1:
        raise PostSelectionTerminalExclusionError(
            f"{label} document is not unique in the selected candidate"
        )
    return matches[0]


def _selected_courtlistener_docket_id(selected: Mapping[str, object]) -> str:
    identity = selected.get("identity_resolution")
    if not isinstance(identity, Mapping):
        raise PostSelectionTerminalExclusionError(
            "zero-cost recovery selection lacks CourtListener docket identity"
        )
    return _required_text(
        cast(Mapping[str, object], identity), "courtlistener_docket_id"
    )


def verify_post_selection_terminal_exclusions(
    *,
    selection_bytes: bytes,
    evidence: Sequence[VerifiedTerminalExclusionEvidence],
) -> VerifiedPostSelectionTerminalExclusions:
    """Close verified terminal facts into exact selection order."""

    selected = _selection_index(selection_bytes)
    by_candidate: dict[str, VerifiedTerminalExclusionEvidence] = {}
    for item in evidence:
        require_verified_terminal_exclusion_evidence(item)
        if item.candidate_id not in selected:
            raise PostSelectionTerminalExclusionError(
                "terminal exclusion candidate is outside the exact selection"
            )
        if item.candidate_id in by_candidate:
            raise PostSelectionTerminalExclusionError(
                f"duplicate terminal exclusion candidate: {item.candidate_id}"
            )
        if item.evidence_commitments.get("selection") != _sha(selection_bytes):
            raise PostSelectionTerminalExclusionError(
                "terminal evidence binds a different exact selection"
            )
        by_candidate[item.candidate_id] = item
    if not by_candidate:
        raise PostSelectionTerminalExclusionError(
            "successor replacement requires at least one terminal exclusion"
        )
    records = tuple(
        {
            "schema_version": EXCLUSION_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_document_id": by_candidate[candidate_id].source_document_id,
            "reason": by_candidate[candidate_id].reason.value,
            "evidence_kind": by_candidate[candidate_id].evidence_kind,
            "evidence_commitments": dict(
                sorted(by_candidate[candidate_id].evidence_commitments.items())
            ),
        }
        for candidate_id in selected
        if candidate_id in by_candidate
    )
    records_bytes = _jsonl_bytes(records)
    result = object.__new__(VerifiedPostSelectionTerminalExclusions)
    object.__setattr__(result, "records", records)
    object.__setattr__(result, "records_bytes", records_bytes)
    object.__setattr__(result, "selection_sha256", _sha(selection_bytes))
    object.__setattr__(result, "commitment_sha256", _sha(records_bytes))
    object.__setattr__(result, "_verification_seal", _VERIFICATION_SEAL)
    return result


def require_verified_terminal_exclusion_evidence(
    evidence: VerifiedTerminalExclusionEvidence,
) -> None:
    """Reject evidence not minted by a reason-specific verifier."""

    if (
        type(evidence) is not VerifiedTerminalExclusionEvidence
        or getattr(evidence, "_verification_seal", None) is not _VERIFICATION_SEAL
    ):
        raise PostSelectionTerminalExclusionError(
            "terminal exclusion evidence was not produced by verified replay"
        )


def require_verified_post_selection_terminal_exclusions(
    authority: VerifiedPostSelectionTerminalExclusions,
) -> None:
    """Reject a changed or caller-constructed terminal subset."""

    if (
        type(authority) is not VerifiedPostSelectionTerminalExclusions
        or getattr(authority, "_verification_seal", None) is not _VERIFICATION_SEAL
        or authority.records_bytes != _jsonl_bytes(authority.records)
        or authority.commitment_sha256 != _sha(authority.records_bytes)
    ):
        raise PostSelectionTerminalExclusionError(
            "terminal exclusions were not produced by verified replay"
        )


def _mint_terminal_evidence(
    *,
    candidate_id: str,
    source_document_id: str,
    reason: TerminalExclusionReason,
    evidence_kind: str,
    evidence_commitments: Mapping[str, str],
) -> VerifiedTerminalExclusionEvidence:
    value = object.__new__(VerifiedTerminalExclusionEvidence)
    object.__setattr__(value, "candidate_id", candidate_id)
    object.__setattr__(value, "source_document_id", source_document_id)
    object.__setattr__(value, "reason", reason)
    object.__setattr__(value, "evidence_kind", evidence_kind)
    object.__setattr__(value, "evidence_commitments", dict(evidence_commitments))
    object.__setattr__(value, "_verification_seal", _VERIFICATION_SEAL)
    return value


def _selection_index(selection_bytes: bytes) -> dict[str, JsonRecord]:
    records = _jsonl_records(selection_bytes, "exact selection")
    result: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _required_text(record, "candidate_id")
        if candidate_id in result:
            raise PostSelectionTerminalExclusionError(
                "exact selection contains a duplicate candidate"
            )
        result[candidate_id] = record
    if len(result) != _TARGET_COUNT:
        raise PostSelectionTerminalExclusionError(
            "terminal exclusions require the exact 100-case selection"
        )
    return result


def _verify_object_bytes(
    value: Mapping[str, object], payload: bytes, label: str
) -> None:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PostSelectionTerminalExclusionError(f"{label} is not valid JSON") from exc
    if not isinstance(decoded, dict) or decoded != dict(value):
        raise PostSelectionTerminalExclusionError(
            f"{label} differs from supplied bytes"
        )
    if _canonical_bytes(dict(value)) != payload:
        raise PostSelectionTerminalExclusionError(f"{label} is not canonical JSON")


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PostSelectionTerminalExclusionError(f"{label} is not valid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise PostSelectionTerminalExclusionError(f"{label} is not an object")
    return cast(Mapping[str, object], decoded)


def _jsonl_records(payload: bytes, label: str) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line.strip():
            raise PostSelectionTerminalExclusionError(f"{label} has a blank line")
        try:
            record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PostSelectionTerminalExclusionError(
                f"{label} line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise PostSelectionTerminalExclusionError(
                f"{label} line {line_number} is not an object"
            )
        records.append(cast(JsonRecord, record))
    if _jsonl_bytes(records) != payload:
        raise PostSelectionTerminalExclusionError(f"{label} is not canonical JSONL")
    return records


def _mapping_sequence(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise PostSelectionTerminalExclusionError(f"{label} is malformed")
    output: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise PostSelectionTerminalExclusionError(f"{label} is malformed")
        output.append(cast(Mapping[str, Any], item))
    return tuple(output)


def _required_text(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PostSelectionTerminalExclusionError(f"record lacks required {field_name}")
    return value.strip()


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _same_sha(value: object, expected: str) -> bool:
    return isinstance(value, str) and value.removeprefix(
        "sha256:"
    ) == expected.removeprefix("sha256:")


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=PostSelectionTerminalExclusionError,
        error_message="terminal exclusion serialization failed",
    )


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical_bytes(dict(record)) for record in records)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

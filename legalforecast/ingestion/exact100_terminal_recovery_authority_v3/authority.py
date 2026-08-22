"""In-process v3 proof: terminal 404 identity without 404-body equality."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field

from legalforecast.contracts import EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    PostSelectionTerminalExclusionError,
    TerminalExclusionReason,
    VerifiedTerminalExclusionEvidence,
    _mint_terminal_evidence,  # pyright: ignore[reportPrivateUsage]
    require_verified_terminal_exclusion_evidence,
    validate_terminal_recovery_evidence,
)

AUTHORITY_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3)
_VERIFICATION_SEAL = object()
_TERMINAL_STATUS = "unavailable"
_RECOVERY_MODE = "courtlistener_rest_noncharging_only"
_EVIDENCE_KIND = "completed_courtlistener_rest_noncharging_recovery"
_TERMINAL_STATUS_CODE = 404


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100TerminalRecoveryAuthorityV3:
    """Opaque fresh-404 capability that does not bind response body bytes.

    This object is never a caller-supplied artifact.  Only the live producer
    mint, or authorize after checking a sealed producer capability, can create
    one.  Persisted recovery bytes cannot construct it.
    """

    schema_version: str
    candidate_id: str
    source_document_id: str
    document_role: str
    courtlistener_docket_id: str
    courtlistener_docket_entry_id: str
    selection_sha256: str
    recovery_request_sha256: str
    terminal_status: str
    observation_status_code: int
    recovery_mode: str
    _verification_seal: object = field(repr=False, compare=False)


def mint_exact100_terminal_recovery_authority_v3(
    *,
    selection_bytes: bytes,
    request: Mapping[str, object],
    request_bytes: bytes,
    observation_status_code: int,
) -> VerifiedExact100TerminalRecoveryAuthorityV3:
    """Mint v3 authority from a live terminal 404 and its bound request tuple."""

    if observation_status_code != _TERMINAL_STATUS_CODE:
        raise PostSelectionTerminalExclusionError(
            "fresh CourtListener observation is not a terminal 404"
        )
    identity = _request_identity(request, request_bytes=request_bytes)
    if identity["selection_sha256"] != _sha(selection_bytes):
        raise PostSelectionTerminalExclusionError(
            "live recovery authority does not bind the persisted terminal identity"
        )
    return _seal_authority(
        candidate_id=identity["candidate_id"],
        source_document_id=identity["source_document_id"],
        document_role=identity["document_role"],
        courtlistener_docket_id=identity["courtlistener_docket_id"],
        courtlistener_docket_entry_id=identity["courtlistener_docket_entry_id"],
        selection_sha256=identity["selection_sha256"],
        recovery_request_sha256=_sha(request_bytes),
        terminal_status=_TERMINAL_STATUS,
        observation_status_code=_TERMINAL_STATUS_CODE,
        recovery_mode=_RECOVERY_MODE,
    )


def require_verified_exact100_terminal_recovery_authority_v3(
    authority: VerifiedExact100TerminalRecoveryAuthorityV3,
) -> None:
    """Reject a caller-constructed or mutated v3 capability."""

    if (
        type(authority) is not VerifiedExact100TerminalRecoveryAuthorityV3
        or getattr(authority, "_verification_seal", None) is not _VERIFICATION_SEAL
        or authority.schema_version != AUTHORITY_SCHEMA_VERSION
        or authority.terminal_status != _TERMINAL_STATUS
        or authority.observation_status_code != _TERMINAL_STATUS_CODE
        or authority.recovery_mode != _RECOVERY_MODE
    ):
        raise PostSelectionTerminalExclusionError(
            "terminal recovery authority was not produced by verified replay"
        )


def authorize_persisted_terminal_recovery_evidence_v3(
    *,
    live_evidence: VerifiedTerminalExclusionEvidence,
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
    """Authorize saved v2 recovery bytes with a fresh v3 404 identity proof.

    Persisted output commitments stay the saved bundle's hashes so successor
    replay remains reproducible.  The live capability must bind the same
    selection and recovery request; it must not be a resume leftover, and the
    raw 404 sidecar may differ from the live observation bytes.
    """

    require_verified_terminal_exclusion_evidence(live_evidence)
    validate_terminal_recovery_evidence(
        selection_bytes=selection_bytes,
        request=request,
        request_bytes=request_bytes,
        receipt=receipt,
        receipt_bytes=receipt_bytes,
        run_card=run_card,
        run_card_bytes=run_card_bytes,
        rest_observation=rest_observation,
        rest_observation_bytes=rest_observation_bytes,
        rest_observation_transcript_bytes=rest_observation_transcript_bytes,
        rest_observation_response_bytes=rest_observation_response_bytes,
    )
    authority = _authority_from_live_evidence(
        live_evidence,
        selection_bytes=selection_bytes,
        request=request,
        request_bytes=request_bytes,
    )
    require_verified_exact100_terminal_recovery_authority_v3(authority)
    return _mint_terminal_evidence(
        candidate_id=authority.candidate_id,
        source_document_id=authority.source_document_id,
        reason=TerminalExclusionReason.TERMINAL_MISSING_CORE_DOCUMENT,
        evidence_kind=_EVIDENCE_KIND,
        evidence_commitments={
            "selection": _sha(selection_bytes),
            "recovery_request": _sha(request_bytes),
            "recovery_receipt": _sha(receipt_bytes),
            "recovery_run_card": _sha(run_card_bytes),
            "rest_observation": _sha(rest_observation_bytes),
            "rest_observation_transcript": _sha(rest_observation_transcript_bytes),
            "rest_observation_response": _sha(rest_observation_response_bytes),
        },
    )


def _authority_from_live_evidence(
    live_evidence: VerifiedTerminalExclusionEvidence,
    *,
    selection_bytes: bytes,
    request: Mapping[str, object],
    request_bytes: bytes,
) -> VerifiedExact100TerminalRecoveryAuthorityV3:
    """Derive v3 identity from a sealed producer 404 capability.

    The live v2 evidence map still records the fresh 404 body.  v3 reads only
    the selection and request commitments plus the producer-minted reason.
    """

    expected_selection = _sha(selection_bytes)
    expected_request = _sha(request_bytes)
    live_commitments = dict(live_evidence.evidence_commitments)
    identity = _request_identity(request, request_bytes=request_bytes)
    if (
        live_evidence.candidate_id != identity["candidate_id"]
        or live_evidence.source_document_id != identity["source_document_id"]
        or live_evidence.reason
        is not TerminalExclusionReason.TERMINAL_MISSING_CORE_DOCUMENT
        or live_evidence.evidence_kind != _EVIDENCE_KIND
        or live_commitments.get("selection") != expected_selection
        or live_commitments.get("recovery_request") != expected_request
        or identity["selection_sha256"] != expected_selection
    ):
        raise PostSelectionTerminalExclusionError(
            "live recovery authority does not bind the persisted terminal identity"
        )
    return _seal_authority(
        candidate_id=identity["candidate_id"],
        source_document_id=identity["source_document_id"],
        document_role=identity["document_role"],
        courtlistener_docket_id=identity["courtlistener_docket_id"],
        courtlistener_docket_entry_id=identity["courtlistener_docket_entry_id"],
        selection_sha256=expected_selection,
        recovery_request_sha256=expected_request,
        terminal_status=_TERMINAL_STATUS,
        observation_status_code=_TERMINAL_STATUS_CODE,
        recovery_mode=_RECOVERY_MODE,
    )


def _request_identity(
    request: Mapping[str, object], *, request_bytes: bytes
) -> dict[str, str]:
    selection_sha256 = request.get("selection_sha256")
    if (
        request.get("recovery_mode") != _RECOVERY_MODE
        or not isinstance(selection_sha256, str)
        or not selection_sha256
    ):
        raise PostSelectionTerminalExclusionError(
            "live recovery authority does not bind the persisted terminal identity"
        )
    return {
        "candidate_id": _required_text(request, "candidate_id"),
        "source_document_id": _required_text(request, "source_document_id"),
        "document_role": _required_text(request, "document_role"),
        "courtlistener_docket_id": _required_text(request, "courtlistener_docket_id"),
        "courtlistener_docket_entry_id": _required_text(
            request, "courtlistener_docket_entry_id"
        ),
        "selection_sha256": selection_sha256,
        "recovery_request_sha256": _sha(request_bytes),
    }


def _seal_authority(
    *,
    candidate_id: str,
    source_document_id: str,
    document_role: str,
    courtlistener_docket_id: str,
    courtlistener_docket_entry_id: str,
    selection_sha256: str,
    recovery_request_sha256: str,
    terminal_status: str,
    observation_status_code: int,
    recovery_mode: str,
) -> VerifiedExact100TerminalRecoveryAuthorityV3:
    value = object.__new__(VerifiedExact100TerminalRecoveryAuthorityV3)
    object.__setattr__(value, "schema_version", AUTHORITY_SCHEMA_VERSION)
    object.__setattr__(value, "candidate_id", candidate_id)
    object.__setattr__(value, "source_document_id", source_document_id)
    object.__setattr__(value, "document_role", document_role)
    object.__setattr__(value, "courtlistener_docket_id", courtlistener_docket_id)
    object.__setattr__(
        value, "courtlistener_docket_entry_id", courtlistener_docket_entry_id
    )
    object.__setattr__(value, "selection_sha256", selection_sha256)
    object.__setattr__(value, "recovery_request_sha256", recovery_request_sha256)
    object.__setattr__(value, "terminal_status", terminal_status)
    object.__setattr__(value, "observation_status_code", observation_status_code)
    object.__setattr__(value, "recovery_mode", recovery_mode)
    object.__setattr__(value, "_verification_seal", _VERIFICATION_SEAL)
    return value


def _required_text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise PostSelectionTerminalExclusionError(
            "live recovery authority does not bind the persisted terminal identity"
        )
    return value


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

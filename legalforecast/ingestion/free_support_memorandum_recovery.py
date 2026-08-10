"""Derive the one free support-memorandum recovery plan without retrieval.

The historic public-packet projection missed a CourtListener memorandum that
the authenticated raw docket explicitly linked to the selected motion.  This
module deliberately does *not* download, parse, materialize, or select
anything.  It turns the already-verified raw-docket bridge into one canonical
plan that a separately authorized execution path may later reauthenticate.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    explicit_motion_reference_numbers,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.target_raw_docket_auxiliary_provenance import (
    TargetRawDocketAuxiliaryProvenanceError,
    VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
    load_verified_target_raw_docket_auxiliary_provenance_bridge,
)

JsonRecord = dict[str, Any]

FREE_SUPPORT_MEMORANDUM_RECOVERY_PLAN_SCHEMA = (
    "legalforecast.free_support_memorandum_recovery_plan.v1"
)

_CANDIDATE_ID = "73327542"
_BRIDGE_CANDIDATE_ID = f"courtlistener-docket-{_CANDIDATE_ID}"
_TARGET_ENTRY_NUMBER = 13
_SUPPORT_ENTRY_NUMBER = 14
_SOURCE_DOCUMENT_ID = "73327542-entry-14-motion-to-dismiss-memorandum"
_COURTLISTENER_STORAGE_HOST = "storage.courtlistener.com"
_RECAP_PDF_PATH = re.compile(r"/recap/[A-Za-z0-9._/-]+\.pdf\Z")


class FreeSupportMemorandumRecoveryError(ValueError):
    """Raised when the bounded no-retrieval recovery plan cannot be derived."""


@dataclass(frozen=True, slots=True)
class FreeSupportMemorandumRecoveryPlan:
    """Canonical, non-executable recovery plan for the one known memorandum."""

    record: JsonRecord
    record_bytes: bytes


def derive_free_support_memorandum_recovery_plan(
    *, bridge_descriptor_path: Path
) -> FreeSupportMemorandumRecoveryPlan:
    """Derive the sole permitted plan from an authenticated raw-docket bridge.

    The descriptor path is reloaded through the existing raw-docket bridge
    authenticator before any plan field is derived.  In particular, callers
    cannot substitute a caller-constructed ``Verified...Bridge`` object, URL,
    document identifier, candidate, or entry number.  A later executor must
    call :func:`verify_free_support_memorandum_recovery_plan` before it may use
    the resulting record.
    """

    bridge = _load_verified_bridge(bridge_descriptor_path)
    return _derive_from_verified_bridge(bridge)


def _derive_from_verified_bridge(
    bridge: VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
) -> FreeSupportMemorandumRecoveryPlan:
    """Derive a plan only after the public entry point authenticates ``bridge``."""

    selection_sha256 = _selected_target_selection_sha256(bridge)
    if _BRIDGE_CANDIDATE_ID not in bridge.selected_candidate_ids:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge does not select the support-memorandum candidate"
        )
    try:
        raw_html = bridge.raw_artifact_bytes_by_candidate[_BRIDGE_CANDIDATE_ID]
    except KeyError as exc:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge lacks the support-memorandum raw docket"
        ) from exc
    if not raw_html:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge has invalid support-memorandum raw docket bytes"
        )
    try:
        page = parse_courtlistener_docket_html(
            raw_html.decode("utf-8"), docket_id=_CANDIDATE_ID
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise FreeSupportMemorandumRecoveryError(
            "authenticated support-memorandum raw docket does not parse"
        ) from exc

    support_entry = _exact_support_entry(page.entries)
    source_url, description = _free_main_document(support_entry)
    record: JsonRecord = {
        "schema_version": FREE_SUPPORT_MEMORANDUM_RECOVERY_PLAN_SCHEMA,
        "candidate_id": _CANDIDATE_ID,
        "selection_sha256": selection_sha256,
        "raw_docket_bridge_sha256": bridge.bridge_sha256,
        "raw_artifacts_manifest_sha256": bridge.raw_artifacts_manifest_sha256,
        "raw_docket_sha256": _sha256(raw_html),
        "raw_docket_byte_count": len(raw_html),
        "target_motion_entry_number": _TARGET_ENTRY_NUMBER,
        "supporting_entry_number": _SUPPORT_ENTRY_NUMBER,
        "source_document_id": _SOURCE_DOCUMENT_ID,
        "document_role": "motion_to_dismiss_memorandum",
        "description": description,
        "source_url": source_url,
        "linkage_basis": "explicit_in_support_re_target_motion",
        "paid_permitted": False,
        "pacer_permitted": False,
        "recap_fetch_permitted": False,
        "provider_permitted": False,
        "retrieval_permitted": False,
        "parse_permitted": False,
        "materialization_permitted": False,
        "selection_mutation_permitted": False,
        "evaluation_permitted": False,
        "freeze_permitted": False,
        "dispatch_permitted": False,
    }
    return FreeSupportMemorandumRecoveryPlan(
        record=record,
        record_bytes=_canonical_bytes(record),
    )


def verify_free_support_memorandum_recovery_plan(
    *,
    persisted_plan_bytes: bytes,
    bridge_descriptor_path: Path,
) -> FreeSupportMemorandumRecoveryPlan:
    """Require persisted plan bytes to be the exact current derived plan.

    This verifier is intentionally useful only to a later authenticated
    executor.  It provides no execution authority itself.
    """

    persisted = _canonical_object(persisted_plan_bytes, "support-memorandum plan")
    expected = derive_free_support_memorandum_recovery_plan(
        bridge_descriptor_path=bridge_descriptor_path
    )
    if persisted_plan_bytes != _canonical_bytes(persisted):
        raise FreeSupportMemorandumRecoveryError(
            "support-memorandum plan is not canonical bytes"
        )
    if persisted_plan_bytes != expected.record_bytes:
        raise FreeSupportMemorandumRecoveryError(
            "support-memorandum plan differs from authenticated rederivation"
        )
    return expected


def _load_verified_bridge(
    bridge_descriptor_path: Path,
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    if not isinstance(cast(object, bridge_descriptor_path), Path):
        raise FreeSupportMemorandumRecoveryError(
            "support-memorandum bridge descriptor path is invalid"
        )
    try:
        return load_verified_target_raw_docket_auxiliary_provenance_bridge(
            bridge_descriptor_path
        )
    except (OSError, TargetRawDocketAuxiliaryProvenanceError) as exc:
        raise FreeSupportMemorandumRecoveryError(
            "support-memorandum raw-docket bridge is not authenticated"
        ) from exc


def _selected_target_selection_sha256(
    bridge: VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
) -> str:
    """Re-read the bridge descriptor to bind the exact selected target row."""

    try:
        descriptor_bytes = bridge.bridge_path.read_bytes()
    except OSError as exc:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge descriptor is unavailable"
        ) from exc
    if _sha256(descriptor_bytes) != bridge.bridge_sha256:
        raise FreeSupportMemorandumRecoveryError("raw-docket bridge descriptor drifted")
    descriptor = _canonical_object(descriptor_bytes, "raw-docket bridge descriptor")
    if set(descriptor) != {"schema_version", "bridge", "bridge_sha256"}:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge descriptor has unexpected fields"
        )
    body = _mapping(descriptor.get("bridge"), "raw-docket bridge body")
    selection = _mapping(body.get("selection"), "raw-docket bridge selection")
    if set(selection) != {
        "path",
        "sha256",
        "candidate_count",
        "candidate_id_set_sha256",
    }:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection commitment is malformed"
        )
    selection_path = selection.get("path")
    selection_sha256 = selection.get("sha256")
    if not isinstance(selection_path, str) or not isinstance(selection_sha256, str):
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection commitment is invalid"
        )
    selection_artifact = Path(selection_path)
    if not selection_artifact.is_absolute():
        selection_artifact = bridge.bridge_path.parent / selection_artifact
    try:
        selection_bytes = selection_artifact.read_bytes()
    except OSError as exc:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection artifact is unavailable"
        ) from exc
    if _sha256(selection_bytes) != selection_sha256:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection artifact drifted"
        )
    selected_rows = _selected_rows(selection_bytes)
    if len(selected_rows) != 1:
        raise FreeSupportMemorandumRecoveryError(
            "support-memorandum candidate is not selected exactly once"
        )
    target_entries = selected_rows[0].get("target_motion_entry_numbers")
    if target_entries != [_TARGET_ENTRY_NUMBER]:
        raise FreeSupportMemorandumRecoveryError(
            "selected support-memorandum target motion is not entry 13"
        )
    return selection_sha256


def _selected_rows(selection_bytes: bytes) -> list[Mapping[str, object]]:
    try:
        lines = selection_bytes.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection artifact is not JSONL"
        ) from exc
    if not rows or any(not isinstance(row, Mapping) for row in rows):
        raise FreeSupportMemorandumRecoveryError(
            "raw-docket bridge selection artifact is malformed"
        )
    return [
        cast(Mapping[str, object], row)
        for row in rows
        if row.get("candidate_id") == _CANDIDATE_ID and row.get("selected") is True
    ]


def _exact_support_entry(
    entries: tuple[CourtListenerWebDocketEntry, ...],
) -> CourtListenerWebDocketEntry:
    matching = tuple(
        entry
        for entry in entries
        if entry.entry_number == str(_SUPPORT_ENTRY_NUMBER)
        and entry.role is CourtListenerEntryRole.MTD_MEMORANDUM
        and explicit_motion_reference_numbers(entry)
        == frozenset({_TARGET_ENTRY_NUMBER})
    )
    if len(matching) != 1:
        raise FreeSupportMemorandumRecoveryError(
            "authenticated raw docket lacks one explicit support memorandum "
            "for target 13"
        )
    return matching[0]


def _free_main_document(entry: CourtListenerWebDocketEntry) -> tuple[str, str]:
    documents = tuple(
        document
        for document in entry.documents
        if document.freely_available
        and document.href is not None
        and "main" in document.kind.lower()
    )
    if len(documents) != 1:
        raise FreeSupportMemorandumRecoveryError(
            "support memorandum does not expose exactly one free main document"
        )
    document = documents[0]
    source_url = document.href
    if source_url is None:
        raise FreeSupportMemorandumRecoveryError(
            "support memorandum free main document URL is absent"
        )
    _require_canonical_courtlistener_pdf(source_url)
    return source_url, document.description


def _require_canonical_courtlistener_pdf(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != _COURTLISTENER_STORAGE_HOST
        or parsed.query
        or parsed.fragment
        or _RECAP_PDF_PATH.fullmatch(parsed.path) is None
    ):
        raise FreeSupportMemorandumRecoveryError(
            "support memorandum free main document URL is not canonical "
            "CourtListener storage"
        )


def _canonical_object(payload: bytes, label: str) -> JsonRecord:
    try:
        record = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreeSupportMemorandumRecoveryError(f"{label} is not JSON") from exc
    if not isinstance(record, Mapping):
        raise FreeSupportMemorandumRecoveryError(f"{label} is not an object")
    return dict(cast(Mapping[str, Any], record))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FreeSupportMemorandumRecoveryError(f"{label} is not an object")
    return cast(Mapping[str, object], value)


def _canonical_bytes(record: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(
        dict(record),
        error_type=FreeSupportMemorandumRecoveryError,
        error_message="support-memorandum plan cannot be canonicalized",
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

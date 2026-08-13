"""Project approved missing-document repairs into a sealed successor.

The repair manifest is observational evidence, not authority. Authority comes
from an approval bound to the manifest's exact bytes; admission additionally
requires an acquired document whose body matches the requested role.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from legalforecast.contracts import (
    MISSING_DOCUMENT_EXCLUSION_V1,
    MISSING_DOCUMENT_INCLUSION_V1,
    MISSING_DOCUMENT_SUCCESSOR_STATE_V1,
    REPAIR_MANIFEST_APPROVAL_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    pleading_body_matches_kind,
)

JsonRecord = dict[str, Any]
SlotKey = tuple[str, int, str]

STATE_SCHEMA_VERSION = str(MISSING_DOCUMENT_SUCCESSOR_STATE_V1)
INCLUSION_SCHEMA_VERSION = str(MISSING_DOCUMENT_INCLUSION_V1)
EXCLUSION_SCHEMA_VERSION = str(MISSING_DOCUMENT_EXCLUSION_V1)
APPROVAL_SCHEMA_VERSION = str(REPAIR_MANIFEST_APPROVAL_V1)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOURCE_KINDS = frozenset({"free", "pacer"})
_STATUSES = frozenset({"acquired", "unavailable"})
ROLE_VALIDATOR_VERSION = "legalforecast.document_body_role_validator.v1"
_ROLE_ALIASES = {
    "interpleader": "interpleader_complaint",
    "response": "opposition",
    "supplemental": "supplemental_brief",
    "target_motion": "motion_to_dismiss_memorandum",
}
_PLEADING_KINDS = {
    "complaint": OperativeComplaintKind.COMPLAINT,
    "amended_complaint": OperativeComplaintKind.AMENDED_COMPLAINT,
    "counterclaim": OperativeComplaintKind.COUNTERCLAIM,
    "crossclaim": OperativeComplaintKind.CROSSCLAIM,
    "third_party_complaint": OperativeComplaintKind.THIRD_PARTY_COMPLAINT,
    "interpleader_complaint": OperativeComplaintKind.INTERPLEADER_COMPLAINT,
}


class MissingDocumentSuccessorError(ValueError):
    """Raised when an approved repair cannot be projected fail-closed."""


_APPROVAL_MINT = object()


@dataclass(frozen=True, slots=True, init=False)
class RepairApproval:
    """Replay-verified authority bound to an exact manifest and paid ceiling."""

    manifest_sha256: str
    maximum_cost_usd: Decimal
    approval_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise MissingDocumentSuccessorError(
            "RepairApproval can be created only by exact evidence replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint_token is _APPROVAL_MINT


def verify_repair_approval(
    manifest_bytes: bytes,
    approval_record: Mapping[str, object],
) -> RepairApproval:
    """Verify and mint authority over one exact repair-manifest byte string."""

    expected_keys = {
        "schema_version",
        "decision",
        "manifest_sha256",
        "maximum_cost_usd",
        "candidate_count",
        "repair_count",
        "keep_count",
        "replace_count",
        "missing_slot_count",
    }
    if set(approval_record) != expected_keys:
        raise MissingDocumentSuccessorError("repair approval fields differ")
    if approval_record.get("schema_version") != APPROVAL_SCHEMA_VERSION:
        raise MissingDocumentSuccessorError("unsupported repair approval schema")
    if approval_record.get("decision") != "approve":
        raise MissingDocumentSuccessorError("repair manifest is not approved")
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    if approval_record.get("manifest_sha256") != digest:
        raise MissingDocumentSuccessorError(
            "approval manifest digest differs from repair manifest"
        )
    maximum = _decimal(approval_record.get("maximum_cost_usd"), "approved cost ceiling")
    manifest = _parse_manifest(manifest_bytes)
    recommendations = [
        _text(record.get("recommendation"), "repair recommendation")
        for record in manifest
    ]
    slots, _mismatches = _repair_work(manifest)
    expected_counts = {
        "candidate_count": len(manifest),
        "repair_count": recommendations.count("repair"),
        "keep_count": recommendations.count("keep"),
        "replace_count": recommendations.count("replace"),
        "missing_slot_count": len(slots),
    }
    if any(
        approval_record.get(field) != value for field, value in expected_counts.items()
    ):
        raise MissingDocumentSuccessorError(
            "repair approval counts differ from manifest"
        )
    approval = object.__new__(RepairApproval)
    object.__setattr__(approval, "manifest_sha256", digest)
    object.__setattr__(approval, "maximum_cost_usd", maximum)
    object.__setattr__(
        approval,
        "approval_sha256",
        hashlib.sha256(_canonical_bytes(approval_record)).hexdigest(),
    )
    object.__setattr__(approval, "_mint_token", _APPROVAL_MINT)
    return approval


@dataclass(frozen=True, slots=True)
class AcquisitionObservation:
    """One terminal or successful attempt for an approved manifest slot."""

    candidate_id: str
    docket_entry_number: int
    requested_role: str
    source_document_id: str
    source_kind: str
    status: str
    cost_usd: Decimal
    content: bytes | None
    markdown: str | None
    clearance_status: str | None
    is_private: bool | None
    is_sealed: bool | None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.source_document_id.strip():
            raise MissingDocumentSuccessorError(
                "acquisition document identity must be nonempty"
            )
        if self.docket_entry_number <= 0:
            raise MissingDocumentSuccessorError(
                "acquisition docket entry must be positive"
            )
        if self.source_kind not in _SOURCE_KINDS:
            raise MissingDocumentSuccessorError("unsupported acquisition source kind")
        if self.status not in _STATUSES:
            raise MissingDocumentSuccessorError("unsupported acquisition status")
        if (
            not self.cost_usd.is_finite()
            or self.cost_usd < 0
            or not _has_cent_precision(self.cost_usd)
        ):
            raise MissingDocumentSuccessorError(
                "acquisition cost must be nonnegative cents"
            )
        if self.source_kind == "free" and self.cost_usd != 0:
            raise MissingDocumentSuccessorError("free acquisition cannot have a cost")
        if self.status == "acquired":
            if (
                self.content is None
                or not self.content
                or self.markdown is None
                or not self.markdown.strip()
                or self.clearance_status is None
                or self.is_private is None
                or self.is_sealed is None
            ):
                raise MissingDocumentSuccessorError(
                    "acquired document lacks byte, markdown, or clearance evidence"
                )
        elif any(
            value is not None
            for value in (
                self.content,
                self.markdown,
                self.clearance_status,
                self.is_private,
                self.is_sealed,
            )
        ):
            raise MissingDocumentSuccessorError(
                "unavailable acquisition cannot carry document evidence"
            )

    @property
    def sha256(self) -> str | None:
        return (
            None if self.content is None else hashlib.sha256(self.content).hexdigest()
        )

    @property
    def byte_count(self) -> int | None:
        return None if self.content is None else len(self.content)


@dataclass(frozen=True, slots=True)
class MissingDocumentSuccessor:
    """Deterministic successor selection and its complete repair ledgers."""

    selection_records: tuple[JsonRecord, ...]
    inclusion_ledger: tuple[JsonRecord, ...]
    exclusion_ledger: tuple[JsonRecord, ...]
    state: JsonRecord

    @property
    def selection_bytes(self) -> bytes:
        return _jsonl_bytes(self.selection_records)

    @property
    def inclusion_ledger_bytes(self) -> bytes:
        return _jsonl_bytes(self.inclusion_ledger)

    @property
    def exclusion_ledger_bytes(self) -> bytes:
        return _jsonl_bytes(self.exclusion_ledger)

    @property
    def state_bytes(self) -> bytes:
        return _canonical_bytes(self.state)


@dataclass(frozen=True, slots=True)
class _RepairSlot:
    candidate_id: str
    entry: int
    requested_role: str
    free_document_count: int
    approved_cost_usd: Decimal

    @property
    def key(self) -> SlotKey:
        return (self.candidate_id, self.entry, self.requested_role)


def project_missing_document_successor(
    *,
    base_selection: Sequence[Mapping[str, object]],
    manifest_bytes: bytes,
    approval: RepairApproval,
    acquisitions: Sequence[AcquisitionObservation],
) -> MissingDocumentSuccessor:
    """Apply one approved manifest with free-first, byte-validated admission."""

    if not approval.is_replay_minted():
        raise MissingDocumentSuccessorError(
            "repair approval lacks exact evidence replay"
        )
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if approval.manifest_sha256 != manifest_sha256:
        raise MissingDocumentSuccessorError(
            "approval manifest digest differs from repair manifest"
        )
    manifest = _parse_manifest(manifest_bytes)
    slots, mismatch_rows = _repair_work(manifest)
    slot_by_key = {slot.key: slot for slot in slots}
    attempts: dict[SlotKey, list[AcquisitionObservation]] = {
        key: [] for key in slot_by_key
    }
    seen_document_ids: set[str] = set()
    paid_phase_started = False
    for observation in acquisitions:
        if observation.source_kind == "pacer":
            paid_phase_started = True
        elif paid_phase_started:
            raise MissingDocumentSuccessorError(
                "free acquisition observed after PACER phase began"
            )
        key = (
            observation.candidate_id,
            observation.docket_entry_number,
            observation.requested_role,
        )
        if key not in slot_by_key:
            raise MissingDocumentSuccessorError(
                "acquisition is outside the approved repair manifest"
            )
        if observation.source_document_id in seen_document_ids:
            raise MissingDocumentSuccessorError(
                "acquisition source document identity is duplicated"
            )
        seen_document_ids.add(observation.source_document_id)
        attempts[key].append(observation)

    predecessor_selection_bytes = _jsonl_bytes(
        tuple(dict(record) for record in base_selection)
    )
    selection, mismatch_exclusions = _remove_mismatched_selections(
        base_selection, mismatch_rows
    )
    selection_candidate_ids = {
        cast(str, record["candidate_id"]) for record in selection
    }
    if {slot.candidate_id for slot in slots} - selection_candidate_ids:
        raise MissingDocumentSuccessorError(
            "approved repair candidate is absent from base selection"
        )
    inclusions: list[JsonRecord] = []
    slot_exclusions: list[JsonRecord] = []
    additions: dict[str, list[JsonRecord]] = {}
    paid_cost = Decimal("0.00")
    for slot in slots:
        inclusion, exclusion, paid = _resolve_slot(slot, attempts[slot.key])
        paid_cost += paid
        if paid_cost > approval.maximum_cost_usd:
            raise MissingDocumentSuccessorError(
                "PACER acquisition exceeds approved cost ceiling"
            )
        if inclusion is not None:
            inclusions.append(inclusion)
            additions.setdefault(slot.candidate_id, []).append(
                _selection_document(inclusion)
            )
        elif exclusion is not None:
            slot_exclusions.append(exclusion)
        else:
            raise MissingDocumentSuccessorError(
                "approved repair slot lacks terminal disposition"
            )

    successor_selection = _add_inclusions(selection, additions)
    inclusion_records = tuple(inclusions)
    exclusion_records = (*mismatch_exclusions, *slot_exclusions)
    selection_bytes = _jsonl_bytes(successor_selection)
    inclusion_bytes = _jsonl_bytes(inclusion_records)
    exclusion_bytes = _jsonl_bytes(exclusion_records)
    state: JsonRecord = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "sealed",
        "manifest_sha256": manifest_sha256,
        "approval_sha256": approval.approval_sha256,
        "predecessor_selection_sha256": hashlib.sha256(
            predecessor_selection_bytes
        ).hexdigest(),
        "approved_cost_usd": _money(approval.maximum_cost_usd),
        "paid_cost_usd": _money(paid_cost),
        "approved_slot_count": len(slots),
        "included_slot_count": len(inclusion_records),
        "excluded_slot_count": len(slot_exclusions),
        "terminal_slot_count": len(inclusion_records) + len(slot_exclusions),
        "removed_mismatch_count": len(mismatch_exclusions),
        "output_sha256s": {
            "exclusion-ledger.jsonl": hashlib.sha256(exclusion_bytes).hexdigest(),
            "inclusion-ledger.jsonl": hashlib.sha256(inclusion_bytes).hexdigest(),
            "target-cohort-selection.jsonl": hashlib.sha256(
                selection_bytes
            ).hexdigest(),
        },
    }
    return MissingDocumentSuccessor(
        selection_records=successor_selection,
        inclusion_ledger=inclusion_records,
        exclusion_ledger=exclusion_records,
        state=state,
    )


def _parse_manifest(payload: bytes) -> tuple[JsonRecord, ...]:
    if not payload or not payload.endswith(b"\n"):
        raise MissingDocumentSuccessorError(
            "repair manifest must be nonempty newline-terminated JSONL"
        )
    records: list[JsonRecord] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        try:
            value = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MissingDocumentSuccessorError(
                f"repair manifest line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise MissingDocumentSuccessorError(
                f"repair manifest line {line_number} must be an object"
            )
        records.append(cast(JsonRecord, value))
    return tuple(records)


def _repair_work(
    manifest: Sequence[Mapping[str, object]],
) -> tuple[tuple[_RepairSlot, ...], tuple[JsonRecord, ...]]:
    slots: list[_RepairSlot] = []
    mismatches: list[JsonRecord] = []
    candidate_ids: set[str] = set()
    slot_keys: set[SlotKey] = set()
    for row in manifest:
        candidate_id = _text(row.get("candidate_id"), "candidate_id")
        recommendation = _text(row.get("recommendation"), "repair recommendation")
        if recommendation not in {"keep", "repair", "replace"}:
            raise MissingDocumentSuccessorError(
                "repair manifest recommendation is unsupported"
            )
        if recommendation == "replace":
            raise MissingDocumentSuccessorError(
                "replacement recommendation is outside this successor"
            )
        if candidate_id in candidate_ids:
            raise MissingDocumentSuccessorError(
                "repair manifest candidate identity is duplicated"
            )
        candidate_ids.add(candidate_id)
        raw_slots = _mapping_list(row.get("missing_docs"), "missing_docs")
        raw_mismatches = _mapping_list(row.get("byte_mismatches"), "byte_mismatches")
        if recommendation == "keep" and (raw_slots or raw_mismatches):
            raise MissingDocumentSuccessorError(
                "keep recommendation contains repair work"
            )
        for raw_slot in raw_slots:
            entry = _positive_int(raw_slot.get("entry"), "missing document entry")
            role = _text(raw_slot.get("role"), "missing document role")
            key = (candidate_id, entry, role)
            if key in slot_keys:
                raise MissingDocumentSuccessorError(
                    "repair manifest slot is duplicated"
                )
            slot_keys.add(key)
            slots.append(
                _RepairSlot(
                    candidate_id=candidate_id,
                    entry=entry,
                    requested_role=role,
                    free_document_count=_nonnegative_int(
                        raw_slot.get("free_document_count"),
                        "free document count",
                    ),
                    approved_cost_usd=_decimal(
                        raw_slot.get("cost_usd"), "missing document cost"
                    ),
                )
            )
        for raw_mismatch in raw_mismatches:
            mismatches.append(
                {
                    "candidate_id": candidate_id,
                    "entry": _positive_int(
                        raw_mismatch.get("entry"), "byte mismatch entry"
                    ),
                    "selected_role": _text(
                        raw_mismatch.get("selected_role"),
                        "byte mismatch selected role",
                    ),
                    "observed_role": _text(
                        raw_mismatch.get("observed_role"),
                        "byte mismatch observed role",
                    ),
                    "basis": _text(raw_mismatch.get("basis"), "byte mismatch basis"),
                }
            )
    return tuple(slots), tuple(mismatches)


def _resolve_slot(
    slot: _RepairSlot,
    attempts: Sequence[AcquisitionObservation],
) -> tuple[JsonRecord | None, JsonRecord | None, Decimal]:
    free_exhausted = slot.free_document_count == 0
    paid_cost = Decimal("0.00")
    if not attempts:
        return None, None, paid_cost
    for index, attempt in enumerate(attempts):
        if attempt.source_kind == "pacer":
            if not free_exhausted:
                raise MissingDocumentSuccessorError(
                    "PACER acquisition preceded free-source exhaustion"
                )
            paid_cost += attempt.cost_usd
            if attempt.cost_usd > slot.approved_cost_usd:
                raise MissingDocumentSuccessorError(
                    "PACER acquisition exceeds approved cost ceiling"
                )
        elif attempt.status == "unavailable":
            free_exhausted = True
        if attempt.status == "unavailable":
            if index == len(attempts) - 1:
                return (
                    None,
                    _slot_exclusion(slot, attempt, reason="document_unavailable"),
                    paid_cost,
                )
            continue
        if index != len(attempts) - 1:
            raise MissingDocumentSuccessorError(
                "acquired slot has observations after terminal disposition"
            )
        assert attempt.markdown is not None
        if (
            attempt.clearance_status != "cleared"
            or attempt.is_private is not False
            or attempt.is_sealed is not False
        ):
            return (
                None,
                _slot_exclusion(
                    slot,
                    attempt,
                    reason="acquired_document_not_publicly_cleared",
                ),
                paid_cost,
            )
        if not _body_matches_role(attempt.markdown, slot.requested_role):
            return (
                None,
                _slot_exclusion(
                    slot,
                    attempt,
                    reason="acquired_bytes_mismatch_requested_role",
                ),
                paid_cost,
            )
        return _inclusion(slot, attempt), None, paid_cost
    return None, None, paid_cost


def _remove_mismatched_selections(
    base_selection: Sequence[Mapping[str, object]],
    mismatches: Sequence[Mapping[str, object]],
) -> tuple[tuple[JsonRecord, ...], tuple[JsonRecord, ...]]:
    by_candidate: dict[str, list[Mapping[str, object]]] = {}
    for mismatch in mismatches:
        by_candidate.setdefault(cast(str, mismatch["candidate_id"]), []).append(
            mismatch
        )
    output: list[JsonRecord] = []
    exclusions: list[JsonRecord] = []
    seen_candidates: set[str] = set()
    for raw_record in base_selection:
        record = dict(raw_record)
        candidate_id = _text(record.get("candidate_id"), "selection candidate_id")
        if candidate_id in seen_candidates:
            raise MissingDocumentSuccessorError(
                "base selection candidate identity is duplicated"
            )
        seen_candidates.add(candidate_id)
        documents = _mapping_list(record.get("documents"), "selection documents")
        retained: list[JsonRecord] = []
        pending = list(by_candidate.get(candidate_id, ()))
        for document in documents:
            entry = document.get("docket_entry_number")
            role = document.get("document_role")
            matched = next(
                (
                    mismatch
                    for mismatch in pending
                    if mismatch["entry"] == entry and mismatch["selected_role"] == role
                ),
                None,
            )
            if matched is None:
                retained.append(dict(document))
                continue
            pending.remove(matched)
            exclusions.append(
                {
                    "schema_version": EXCLUSION_SCHEMA_VERSION,
                    "candidate_id": candidate_id,
                    "docket_entry_number": matched["entry"],
                    "requested_role": matched["selected_role"],
                    "source_document_id": document.get("source_document_id"),
                    "source_kind": "inherited",
                    "reason": "selected_bytes_mismatch_role",
                    "observed_role": matched["observed_role"],
                    "basis": matched["basis"],
                }
            )
        if pending:
            raise MissingDocumentSuccessorError(
                "byte mismatch does not identify a selected document"
            )
        record["documents"] = retained
        output.append(record)
    unknown_candidates = set(by_candidate) - seen_candidates
    if unknown_candidates:
        raise MissingDocumentSuccessorError(
            "repair manifest byte mismatch candidate is absent from selection"
        )
    return tuple(output), tuple(exclusions)


def _add_inclusions(
    selection: Sequence[JsonRecord],
    additions: Mapping[str, Sequence[JsonRecord]],
) -> tuple[JsonRecord, ...]:
    output: list[JsonRecord] = []
    seen: set[str] = set()
    for raw_record in selection:
        record = dict(raw_record)
        candidate_id = cast(str, record["candidate_id"])
        seen.add(candidate_id)
        documents = cast(list[object], record["documents"])
        existing_ids = {
            cast(Mapping[str, object], document).get("source_document_id")
            for document in documents
            if isinstance(document, Mapping)
        }
        candidate_additions = additions.get(candidate_id, ())
        if any(
            addition["source_document_id"] in existing_ids
            for addition in candidate_additions
        ):
            raise MissingDocumentSuccessorError(
                "included source document already exists in selection"
            )
        record["documents"] = [*documents, *candidate_additions]
        output.append(record)
    if set(additions) - seen:
        raise MissingDocumentSuccessorError(
            "approved repair candidate is absent from base selection"
        )
    return tuple(output)


def _body_matches_role(markdown: str, requested_role: str) -> bool:
    normalized_role = _ROLE_ALIASES.get(requested_role, requested_role)
    pleading_kind = _PLEADING_KINDS.get(normalized_role)
    if pleading_kind is not None:
        return pleading_body_matches_kind(markdown, pleading_kind)
    text = " ".join(markdown.lower().split())
    if normalized_role == "opposition":
        return bool(re.search(r"\b(?:opposition|response)\b", text))
    if normalized_role == "reply":
        return bool(re.search(r"\breply\b", text))
    if normalized_role == "surreply":
        return bool(re.search(r"\bsur-?reply\b", text))
    if normalized_role == "supplemental_brief":
        return bool(re.search(r"\bsupplemental\b.{0,80}\b(?:brief|memorandum)\b", text))
    if normalized_role == "motion_to_dismiss_memorandum":
        return bool(
            re.search(
                r"\b(?:motion\s+to\s+dismiss|judgment\s+on\s+the\s+pleadings|"
                r"rule\s+12)\b",
                text,
            )
        )
    return False


def _inclusion(slot: _RepairSlot, observation: AcquisitionObservation) -> JsonRecord:
    assert observation.sha256 is not None
    assert observation.byte_count is not None
    return {
        "schema_version": INCLUSION_SCHEMA_VERSION,
        "candidate_id": slot.candidate_id,
        "docket_entry_number": slot.entry,
        "requested_role": slot.requested_role,
        "admitted_role": _ROLE_ALIASES.get(slot.requested_role, slot.requested_role),
        "source_document_id": observation.source_document_id,
        "source_kind": observation.source_kind,
        "cost_usd": _money(observation.cost_usd),
        "sha256": observation.sha256,
        "byte_count": observation.byte_count,
        "byte_role_verdict": "match",
        "role_validator_version": ROLE_VALIDATOR_VERSION,
        "markdown_sha256": hashlib.sha256(
            cast(str, observation.markdown).encode("utf-8")
        ).hexdigest(),
    }


def _slot_exclusion(
    slot: _RepairSlot,
    observation: AcquisitionObservation,
    *,
    reason: str,
) -> JsonRecord:
    return {
        "schema_version": EXCLUSION_SCHEMA_VERSION,
        "candidate_id": slot.candidate_id,
        "docket_entry_number": slot.entry,
        "requested_role": slot.requested_role,
        "source_document_id": observation.source_document_id,
        "source_kind": observation.source_kind,
        "reason": reason,
        "observed_role": None,
        "basis": "terminal acquisition observation",
    }


def _selection_document(inclusion: Mapping[str, object]) -> JsonRecord:
    return {
        "availability_status": "available",
        "candidate_id": inclusion["candidate_id"],
        "contains_target_outcome": False,
        "docket_entry_number": inclusion["docket_entry_number"],
        "document_role": inclusion["admitted_role"],
        "is_available": True,
        "is_predecision_material": True,
        "is_private": False,
        "is_sealed": False,
        "model_visible": True,
        "redaction_or_seal_status": "public",
        "requires_paid_recovery": False,
        "resolved_from_paid_gap": inclusion["source_kind"] == "pacer",
        "source_document_id": inclusion["source_document_id"],
        "source_provider": (
            "courtlistener_public" if inclusion["source_kind"] == "free" else "pacer"
        ),
        "sha256": inclusion["sha256"],
        "byte_count": inclusion["byte_count"],
    }


def _mapping_list(value: object, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise MissingDocumentSuccessorError(f"{field} must be an array")
    records: list[Mapping[str, object]] = []
    for item in cast(list[object], value):
        if not isinstance(item, Mapping):
            raise MissingDocumentSuccessorError(f"{field} must contain objects")
        records.append(cast(Mapping[str, object], item))
    return tuple(records)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissingDocumentSuccessorError(f"{field} must be nonempty text")
    return value


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MissingDocumentSuccessorError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MissingDocumentSuccessorError(f"{field} must be a nonnegative integer")
    return value


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        raise MissingDocumentSuccessorError(f"{field} must be a decimal amount")
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or not _has_cent_precision(amount):
        raise MissingDocumentSuccessorError(f"{field} must be nonnegative cents")
    return amount


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _has_cent_precision(value: Decimal) -> bool:
    exponent = value.as_tuple().exponent
    return isinstance(exponent, int) and exponent >= -2


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical_bytes(record) for record in records)


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=MissingDocumentSuccessorError,
        error_message="successor artifact is not canonical JSON",
    )

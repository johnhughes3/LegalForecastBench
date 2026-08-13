"""Project approved missing-document repairs into a sealed successor.

The repair manifest is observational evidence, not authority. Authority comes
from an approval bound to the manifest's exact bytes. Planning performs no
network or provider operation; admission requires an acquired document whose
body matches the requested role.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    DOCUMENT_BODY_ROLE_VALIDATOR_V1,
    EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
    EXACT100_MISSING_DOCUMENT_SUCCESSOR_V2,
    MISSING_DOCUMENT_EXCLUSION_V1,
    MISSING_DOCUMENT_INCLUSION_V1,
    MISSING_DOCUMENT_SUCCESSOR_STATE_V1,
    RAW_BYTES_RAW_SHA256_V1,
    REPAIR_MANIFEST_APPROVAL_V1,
    REPAIR_MANIFEST_APPROVAL_V2,
    SchemaIdentifier,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    pleading_body_matches_kind,
)

JsonRecord = dict[str, Any]
SlotKey = tuple[str, int, str, str]

STATE_SCHEMA_VERSION = str(MISSING_DOCUMENT_SUCCESSOR_STATE_V1)
INCLUSION_SCHEMA_VERSION = str(MISSING_DOCUMENT_INCLUSION_V1)
EXCLUSION_SCHEMA_VERSION = str(MISSING_DOCUMENT_EXCLUSION_V1)
APPROVAL_SCHEMA_VERSION = str(REPAIR_MANIFEST_APPROVAL_V1)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOURCE_KINDS = frozenset({"free", "pacer"})
_STATUSES = frozenset({"acquired", "unavailable"})
ROLE_VALIDATOR_VERSION = str(DOCUMENT_BODY_ROLE_VALIDATOR_V1)
_ROLE_ALIASES = {
    "interpleader": "interpleader_complaint",
    "response": "opposition",
    "supplemental": "supplemental_brief",
    "target_motion": "motion_to_dismiss_memorandum",
    "motion_memorandum": "motion_to_dismiss_memorandum",
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
    """Raised when an approved repair cannot be planned or sealed fail-closed."""


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


@dataclass(frozen=True, slots=True, init=False)
class RepairPlanApproval:
    manifest_sha256: str
    maximum_cost_usd: Decimal
    max_per_document_usd: Decimal
    approval_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise MissingDocumentSuccessorError(
            "RepairPlanApproval requires evidence replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint_token is _APPROVAL_MINT


def verify_repair_plan_approval(
    manifest_bytes: bytes, record: Mapping[str, object]
) -> RepairPlanApproval:
    keys = {
        "schema_version",
        "decision",
        "manifest_sha256",
        "maximum_cost_usd",
        "max_per_document_usd",
        "candidate_count",
        "repair_count",
        "keep_count",
        "replace_count",
        "missing_slot_count",
    }
    if (
        set(record) != keys
        or record.get("schema_version") != str(REPAIR_MANIFEST_APPROVAL_V2)
        or record.get("decision") != "approve"
    ):
        raise MissingDocumentSuccessorError("repair plan approval is invalid")
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    if record.get("manifest_sha256") != digest:
        raise MissingDocumentSuccessorError(
            "approval manifest digest differs from repair manifest"
        )
    manifest = _parse_manifest(manifest_bytes)
    recommendations = [
        _text(row.get("recommendation"), "repair recommendation") for row in manifest
    ]
    slots, _ = _repair_work(manifest)
    counts = {
        "candidate_count": len(manifest),
        "repair_count": recommendations.count("repair"),
        "keep_count": recommendations.count("keep"),
        "replace_count": recommendations.count("replace"),
        "missing_slot_count": len(slots),
    }
    if any(record.get(key) != value for key, value in counts.items()):
        raise MissingDocumentSuccessorError(
            "repair plan approval counts differ from manifest"
        )
    approval = object.__new__(RepairPlanApproval)
    for name, value in (
        ("manifest_sha256", digest),
        (
            "maximum_cost_usd",
            _decimal(record.get("maximum_cost_usd"), "approved cost ceiling"),
        ),
        (
            "max_per_document_usd",
            _decimal(record.get("max_per_document_usd"), "per-document cap"),
        ),
        ("approval_sha256", hashlib.sha256(_canonical_bytes(record)).hexdigest()),
        ("_mint_token", _APPROVAL_MINT),
    ):
        object.__setattr__(approval, name, value)
    return approval


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
    document_selector: str
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
        if not self.document_selector.strip():
            raise MissingDocumentSuccessorError(
                "acquisition document selector must be nonempty"
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
    # contract-ratchet: allow raw acquired-byte evidence digest
    def sha256(self) -> str | None:
        if self.content is None:
            return None
        return str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                self.content,
                domain=MISSING_DOCUMENT_INCLUSION_V1,
            ).digest
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
    document_selector: str
    requested_role: str
    free_document_count: int
    approved_cost_usd: Decimal

    @property
    def key(self) -> SlotKey:
        return (
            self.candidate_id,
            self.entry,
            self.document_selector,
            self.requested_role,
        )


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
    replacement_candidate_ids = frozenset(
        _text(row.get("candidate_id"), "candidate_id")
        for row in manifest
        if row.get("recommendation") == "replace"
    )
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
            _document_selector(observation.document_selector),
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
    selection, replacement_exclusions = _apply_replacement_recommendations(
        base_selection,
        replacement_candidate_ids,
    )
    selection, mismatch_exclusions = _remove_mismatched_selections(
        selection, mismatch_rows
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
    exclusion_records = (
        *replacement_exclusions,
        *mismatch_exclusions,
        *slot_exclusions,
    )
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
        "replacement_candidate_count": len(replacement_candidate_ids),
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
        if recommendation == "replace" and (raw_slots or raw_mismatches):
            raise MissingDocumentSuccessorError(
                "replacement recommendation contains document repair work"
            )
        for raw_slot in raw_slots:
            entry = _positive_int(raw_slot.get("entry"), "missing document entry")
            role = _text(raw_slot.get("role"), "missing document role")
            document_selector = _selector_from_record(raw_slot)
            key = (candidate_id, entry, document_selector, role)
            if key in slot_keys:
                raise MissingDocumentSuccessorError(
                    "repair manifest slot is duplicated"
                )
            slot_keys.add(key)
            slots.append(
                _RepairSlot(
                    candidate_id=candidate_id,
                    entry=entry,
                    document_selector=document_selector,
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
                    "document_selector": _selector_from_record(raw_mismatch),
                    "selected_role": _text(
                        raw_mismatch.get("selected_role"),
                        "byte mismatch selected role",
                    ),
                    "observed_role": _text(
                        raw_mismatch.get("observed_role"),
                        "byte mismatch observed role",
                    ),
                    "basis": _text(
                        raw_mismatch.get("basis", raw_mismatch.get("evidence")),
                        "byte mismatch basis",
                    ),
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


def _apply_replacement_recommendations(
    base_selection: Sequence[Mapping[str, object]],
    replacement_candidate_ids: frozenset[str],
) -> tuple[tuple[JsonRecord, ...], tuple[JsonRecord, ...]]:
    output: list[JsonRecord] = []
    exclusions: list[JsonRecord] = []
    remaining = set(replacement_candidate_ids)
    for raw_record in base_selection:
        record = dict(raw_record)
        candidate_id = _text(record.get("candidate_id"), "selection candidate_id")
        if candidate_id not in remaining:
            output.append(record)
            continue
        remaining.remove(candidate_id)
        record["selected"] = False
        record["documents"] = []
        output.append(record)
        exclusions.append(
            {
                "schema_version": EXCLUSION_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "docket_entry_number": None,
                "document_selector": None,
                "requested_role": "candidate",
                "source_document_id": None,
                "source_kind": "inherited",
                "reason": "manifest_replacement_recommendation",
                "observed_role": None,
                "basis": "approved manifest requires reserve replacement",
            }
        )
    if remaining:
        raise MissingDocumentSuccessorError(
            "replacement candidate is absent from base selection"
        )
    return tuple(output), tuple(exclusions)


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
                    if mismatch["entry"] == entry
                    and _document_selector(mismatch["document_selector"])
                    == _document_selector(document.get("document_selector"))
                    and mismatch["selected_role"] == role
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
                    "document_selector": _v1_selector_spelling(
                        _document_selector(matched["document_selector"])
                    ),
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
        "document_selector": _v1_selector_spelling(slot.document_selector),
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
        "document_selector": _v1_selector_spelling(slot.document_selector),
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
        "document_selector": inclusion["document_selector"],
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


DocumentKey = tuple[str, int, str]
PLAN_SCHEMA_VERSION = str(EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2)
SUCCESSOR_SCHEMA_VERSION = str(EXACT100_MISSING_DOCUMENT_SUCCESSOR_V2)
_ALLOWED_METHODS = frozenset({"courtlistener_free", "pacer_purchase"})
_ALLOWED_RECOMMENDATIONS = frozenset({"keep", "repair", "replace"})
_SEAL = object()


@dataclass(frozen=True, slots=True)
class MissingDocumentAcquisitionItem:
    """One deterministic, manifest-bound acquisition obligation."""

    candidate_id: str
    docket_entry_number: int
    document_selector: str
    document_role: str
    acquisition_method: str
    projected_cost_usd: Decimal
    evidence: str
    opinion_derived: bool

    @property
    def key(self) -> DocumentKey:
        return self.candidate_id, self.docket_entry_number, self.document_selector

    def to_record(self) -> JsonRecord:
        return {
            "candidate_id": self.candidate_id,
            "docket_entry_number": self.docket_entry_number,
            "document_selector": self.document_selector,
            "document_role": self.document_role,
            "acquisition_method": self.acquisition_method,
            "projected_cost_usd": _money(self.projected_cost_usd),
            "evidence": self.evidence,
            "opinion_derived": self.opinion_derived,
        }


@dataclass(frozen=True, slots=True)
class MissingDocumentAcquisitionPlan:
    """A deterministic free-first plan bound to one approved sidecar."""

    manifest_sha256: str
    approval_sha256: str
    approved_maximum_usd: Decimal
    max_per_document_usd: Decimal
    items: tuple[MissingDocumentAcquisitionItem, ...]
    existing_document_ledger: tuple[Mapping[str, object], ...]
    manifest_candidate_count: int
    manifest_repair_count: int
    plan_sha256: str

    @property
    def projected_paid_cost_usd(self) -> Decimal:
        return sum((item.projected_cost_usd for item in self.items), Decimal("0.00"))

    def content_record(self) -> JsonRecord:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "manifest_sha256": self.manifest_sha256,
            "approval_sha256": self.approval_sha256,
            "approved_maximum_usd": _money(self.approved_maximum_usd),
            "max_per_document_usd": _money(self.max_per_document_usd),
            "projected_paid_cost_usd": _money(self.projected_paid_cost_usd),
            "manifest_candidate_count": self.manifest_candidate_count,
            "manifest_repair_count": self.manifest_repair_count,
            "items": [item.to_record() for item in self.items],
            "existing_document_ledger": [
                dict(record) for record in self.existing_document_ledger
            ],
        }

    def to_record(self) -> JsonRecord:
        return {**self.content_record(), "plan_sha256": self.plan_sha256}


@dataclass(frozen=True, slots=True, init=False)
class SealedMissingDocumentSuccessor:
    """Immutable complete disposition ledger for an approved repair plan."""

    status: str
    plan_sha256: str
    manifest_sha256: str
    ledger: tuple[Mapping[str, object], ...]
    included_document_keys: frozenset[DocumentKey]
    successor_sha256: str
    _seal: object

    def _content_record(self) -> JsonRecord:
        return {
            "schema_version": SUCCESSOR_SCHEMA_VERSION,
            "status": self.status,
            "plan_sha256": self.plan_sha256,
            "manifest_sha256": self.manifest_sha256,
            "ledger": [dict(record) for record in self.ledger],
        }

    def to_record(self) -> JsonRecord:
        return {**self._content_record(), "successor_sha256": self.successor_sha256}

    @property
    def successor_bytes(self) -> bytes:
        return canonical_json_bytes(
            self.to_record(),
            error_type=MissingDocumentSuccessorError,
            error_message="missing-document successor is not canonicalizable",
        )


def build_missing_document_acquisition_plan(
    *,
    manifest_bytes: bytes,
    approval: RepairPlanApproval,
) -> MissingDocumentAcquisitionPlan:
    """Authenticate an observational repair sidecar and derive its work plan."""

    actual_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if (
        type(approval) is not RepairPlanApproval
        or not approval.is_replay_minted()
        or approval.manifest_sha256 != actual_digest
    ):
        raise MissingDocumentSuccessorError(
            "repair manifest lacks replay-verified approval"
        )
    maximum = _positive_money(approval.maximum_cost_usd, "approved maximum")
    per_document = _positive_money(approval.max_per_document_usd, "per-document cap")
    records = _read_manifest(manifest_bytes)
    seen_candidates: set[str] = set()
    seen_items: set[DocumentKey] = set()
    items: list[MissingDocumentAcquisitionItem] = []
    existing_ledger: list[Mapping[str, object]] = []
    repair_count = 0
    for record in records:
        candidate_id = _required_text(record, "candidate_id")
        if candidate_id in seen_candidates:
            raise MissingDocumentSuccessorError(
                f"duplicate repair-manifest candidate: {candidate_id}"
            )
        seen_candidates.add(candidate_id)
        recommendation = _required_text(record, "recommendation")
        if recommendation not in _ALLOWED_RECOMMENDATIONS:
            raise MissingDocumentSuccessorError("unsupported repair recommendation")
        missing = _record_list(record, "missing_docs")
        byte_mismatches = _record_list(record, "byte_mismatches")
        current = _record_list(record, "current_selection", required=False)
        required = _record_list(record, "required_entries", required=False)
        extras = _record_list(record, "extra_selected", required=False)
        if recommendation == "keep" and (missing or byte_mismatches):
            raise MissingDocumentSuccessorError("keep row contains repair obligations")
        if recommendation == "repair":
            repair_count += 1
        row_cost = Decimal("0.00")
        for missing_record in missing:
            entry = _positive_int(missing_record.get("entry"), "missing entry")
            selector = _selector_from_record(missing_record)
            key = candidate_id, entry, selector
            if key in seen_items:
                raise MissingDocumentSuccessorError(
                    f"duplicate repair-manifest document: {candidate_id}/{entry}"
                )
            seen_items.add(key)
            free_count = _nonnegative_int(
                missing_record.get("free_document_count"), "free document count"
            )
            paid_count = _nonnegative_int(
                missing_record.get("pacer_only_document_count"),
                "PACER-only document count",
            )
            if free_count == 0 and paid_count == 0:
                raise MissingDocumentSuccessorError(
                    f"repair document has no acquisition path: {candidate_id}/{entry}"
                )
            cost = _money_value(missing_record.get("cost_usd"), "document cost")
            method = "courtlistener_free" if free_count else "pacer_purchase"
            if method not in _ALLOWED_METHODS:
                raise MissingDocumentSuccessorError("unsupported acquisition method")
            expected_cost = Decimal("0.00") if free_count else per_document
            if cost != expected_cost:
                if cost > per_document:
                    raise MissingDocumentSuccessorError(
                        f"document exceeds per-document cap: {candidate_id}/{entry}"
                    )
                raise MissingDocumentSuccessorError(
                    "document cost differs from acquisition method: "
                    f"{candidate_id}/{entry}"
                )
            row_cost += cost
            items.append(
                MissingDocumentAcquisitionItem(
                    candidate_id=candidate_id,
                    docket_entry_number=entry,
                    document_selector=selector,
                    document_role=_required_text(missing_record, "role"),
                    acquisition_method=method,
                    projected_cost_usd=cost,
                    evidence=_required_text(missing_record, "evidence"),
                    opinion_derived=_required_bool(missing_record, "opinion_derived"),
                )
            )
        if row_cost != _money_value(record.get("cost_usd"), "candidate cost"):
            raise MissingDocumentSuccessorError(
                f"candidate cost does not reconcile: {candidate_id}"
            )
        mismatch_keys: set[tuple[int, str]] = set()
        mismatch_roles: set[tuple[int, str]] = set()
        for mismatch in byte_mismatches:
            entry = _positive_int(mismatch.get("entry"), "mismatch entry")
            selector = _selector_from_record(mismatch)
            key = (entry, selector)
            if key in mismatch_keys:
                raise MissingDocumentSuccessorError(
                    f"duplicate byte-role mismatch: {candidate_id}/{entry}"
                )
            mismatch_keys.add(key)
            mismatch_roles.add((entry, _required_text(mismatch, "selected_role")))
            existing_ledger.append(_validated_mismatch(candidate_id, mismatch))
        extra_keys = {
            (
                _positive_int(row.get("entry"), "extra entry"),
                _required_text(row, "role"),
            )
            for row in extras
        }
        missing_keys = {
            (
                _positive_int(row.get("entry"), "missing entry"),
                _required_text(row, "role"),
            )
            for row in missing
        }
        current_keys = {
            (
                _positive_int(row.get("entry"), "selected entry"),
                _required_text(row, "role"),
            )
            for row in current
        }
        current_entries = {entry for entry, _role in current_keys}
        relevant = current_keys | {
            (
                _positive_int(row.get("entry"), "required entry"),
                _required_text(row, "role"),
            )
            for row in required
            if _positive_int(row.get("entry"), "required entry") not in current_entries
        }
        for entry, role in sorted(relevant):
            if (entry, role) in missing_keys or (entry, role) in mismatch_roles:
                continue
            if (entry, role) in extra_keys:
                existing_ledger.append(
                    MappingProxyType(
                        {
                            "candidate_id": candidate_id,
                            "docket_entry_number": entry,
                            "document_role": role,
                            "disposition": "excluded_extra",
                            "reason": "not_required_by_repair_manifest",
                        }
                    )
                )
            else:
                existing_ledger.append(
                    MappingProxyType(
                        {
                            "candidate_id": candidate_id,
                            "docket_entry_number": entry,
                            "document_role": role,
                            "disposition": "retained",
                        }
                    )
                )

    items.sort(
        key=lambda item: (
            item.acquisition_method != "courtlistener_free",
            item.candidate_id,
            item.docket_entry_number,
            item.document_selector,
            item.document_role,
        )
    )
    projected = sum((item.projected_cost_usd for item in items), Decimal("0.00"))
    if projected > maximum:
        raise MissingDocumentSuccessorError(
            "projected paid cost exceeds approved maximum"
        )
    existing_rows = tuple(
        MappingProxyType(dict(record))
        for record in sorted(
            existing_ledger,
            key=lambda row: (
                cast(str, row["candidate_id"]),
                cast(int, row["docket_entry_number"]),
                cast(str, row.get("document_selector") or ""),
                cast(str, row["document_role"]),
            ),
        )
    )
    provisional = MissingDocumentAcquisitionPlan(
        manifest_sha256=actual_digest,
        approval_sha256=approval.approval_sha256,
        approved_maximum_usd=maximum,
        max_per_document_usd=per_document,
        items=tuple(items),
        existing_document_ledger=existing_rows,
        manifest_candidate_count=len(records),
        manifest_repair_count=repair_count,
        plan_sha256="",
    )
    return MissingDocumentAcquisitionPlan(
        manifest_sha256=provisional.manifest_sha256,
        approval_sha256=provisional.approval_sha256,
        approved_maximum_usd=provisional.approved_maximum_usd,
        max_per_document_usd=provisional.max_per_document_usd,
        items=provisional.items,
        existing_document_ledger=provisional.existing_document_ledger,
        manifest_candidate_count=provisional.manifest_candidate_count,
        manifest_repair_count=provisional.manifest_repair_count,
        plan_sha256=_commit_record(
            provisional.content_record(),
            domain=EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
        ),
    )


def seal_missing_document_successor(
    *,
    plan: MissingDocumentAcquisitionPlan,
    acquired_documents: Sequence[Mapping[str, object]],
    exclusions: Sequence[Mapping[str, object]],
    role_bytes_match: Callable[[str, bytes], bool],
) -> SealedMissingDocumentSuccessor:
    """Seal a successor only after byte validation and complete accounting."""

    _require_valid_plan(plan)
    planned = {item.key: item for item in plan.items}
    dispositions: dict[DocumentKey, Mapping[str, object]] = {}
    seen_source_ids: set[str] = set()
    for evidence in acquired_documents:
        key = _document_key(evidence)
        item = planned.get(key)
        if item is None:
            raise MissingDocumentSuccessorError("acquired document is outside the plan")
        if key in dispositions:
            raise MissingDocumentSuccessorError("duplicate document disposition")
        role = _required_text(evidence, "document_role")
        if role != item.document_role:
            raise MissingDocumentSuccessorError(
                "acquired document role differs from plan"
            )
        source = _required_text(evidence, "source")
        if source != item.acquisition_method:
            raise MissingDocumentSuccessorError(
                "acquired document differs from planned method"
            )
        body = evidence.get("document_bytes")
        if not isinstance(body, bytes):
            raise MissingDocumentSuccessorError("acquired document bytes are missing")
        digest = _raw_sha256(evidence.get("sha256"), "document SHA-256")
        if hashlib.sha256(body).hexdigest() != digest:
            raise MissingDocumentSuccessorError("document SHA-256 differs from bytes")
        if evidence.get("byte_count") != len(body):
            raise MissingDocumentSuccessorError(
                "document byte count differs from bytes"
            )
        if not role_bytes_match(role, body):
            raise MissingDocumentSuccessorError(
                f"role-byte mismatch: {key[0]}/{key[1]} as {role}"
            )
        source_document_id = _required_text(evidence, "source_document_id")
        if source_document_id in seen_source_ids:
            raise MissingDocumentSuccessorError(
                "acquired documents reuse a source document identity"
            )
        seen_source_ids.add(source_document_id)
        dispositions[key] = MappingProxyType(
            {
                "candidate_id": key[0],
                "docket_entry_number": key[1],
                "document_selector": key[2],
                "document_role": role,
                "disposition": "included",
                "acquisition_method": source,
                "source_document_id": source_document_id,
                "sha256": digest,
                "byte_count": len(body),
            }
        )
    for exclusion in exclusions:
        key = _document_key(exclusion)
        item = planned.get(key)
        if item is None:
            raise MissingDocumentSuccessorError("exclusion is outside the plan")
        if key in dispositions:
            raise MissingDocumentSuccessorError("duplicate document disposition")
        role = _required_text(exclusion, "document_role")
        if role != item.document_role:
            raise MissingDocumentSuccessorError("exclusion role differs from plan")
        dispositions[key] = MappingProxyType(
            {
                "candidate_id": key[0],
                "docket_entry_number": key[1],
                "document_selector": key[2],
                "document_role": role,
                "disposition": "excluded",
                "reason": _required_text(exclusion, "reason"),
            }
        )
    if set(dispositions) != set(planned):
        raise MissingDocumentSuccessorError(
            "complete ledger required; every planned document must be included "
            "or excluded"
        )
    ledger = tuple(dispositions[item.key] for item in plan.items) + tuple(
        plan.existing_document_ledger
    )
    content = {
        "schema_version": SUCCESSOR_SCHEMA_VERSION,
        "status": "sealed",
        "plan_sha256": plan.plan_sha256,
        "manifest_sha256": plan.manifest_sha256,
        "ledger": [dict(record) for record in ledger],
    }
    result = object.__new__(SealedMissingDocumentSuccessor)
    for name, value in (
        ("status", "sealed"),
        ("plan_sha256", plan.plan_sha256),
        ("manifest_sha256", plan.manifest_sha256),
        ("ledger", ledger),
        (
            "included_document_keys",
            frozenset(
                key
                for key, record in dispositions.items()
                if record["disposition"] == "included"
            ),
        ),
        (
            "successor_sha256",
            _commit_record(content, domain=EXACT100_MISSING_DOCUMENT_SUCCESSOR_V2),
        ),
        ("_seal", _SEAL),
    ):
        object.__setattr__(result, name, value)
    return result


def _require_valid_plan(plan: MissingDocumentAcquisitionPlan) -> None:
    if type(plan) is not MissingDocumentAcquisitionPlan:
        raise MissingDocumentSuccessorError("invalid acquisition plan")
    if plan.plan_sha256 != _commit_record(
        plan.content_record(),
        domain=EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
    ):
        raise MissingDocumentSuccessorError("acquisition plan changed after approval")
    if plan.projected_paid_cost_usd > plan.approved_maximum_usd:
        raise MissingDocumentSuccessorError("acquisition plan exceeds approved maximum")


def _read_manifest(payload: bytes) -> tuple[JsonRecord, ...]:
    records = _parse_manifest(payload)
    if not records:
        raise MissingDocumentSuccessorError("repair manifest is empty")
    return records


def _validated_mismatch(
    candidate_id: str, record: Mapping[str, object]
) -> Mapping[str, object]:
    verdict = _required_text(record, "verdict")
    if verdict not in {"mismatch", "unverifiable"}:
        raise MissingDocumentSuccessorError("unsupported byte-role verdict")
    return {
        "candidate_id": candidate_id,
        "docket_entry_number": _positive_int(record.get("entry"), "mismatch entry"),
        "document_selector": _selector_from_record(record),
        "document_role": _required_text(record, "selected_role"),
        "disposition": "rejected_byte_role",
        "reason": f"byte_role_{verdict}",
        "observed_role": _required_text(record, "observed_role"),
        "evidence": _required_text(record, "evidence"),
    }


def _record_list(
    record: Mapping[str, object], field: str, *, required: bool = True
) -> tuple[JsonRecord, ...]:
    value = record.get(field)
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise MissingDocumentSuccessorError(f"repair manifest {field} is invalid")
    values = cast(list[object], value)
    if any(not isinstance(item, dict) for item in values):
        raise MissingDocumentSuccessorError(f"repair manifest {field} is invalid")
    return tuple(cast(JsonRecord, item) for item in values)


def _document_key(record: Mapping[str, object]) -> DocumentKey:
    return (
        _required_text(record, "candidate_id"),
        _positive_int(record.get("docket_entry_number"), "docket entry number"),
        _selector_from_record(record),
    )


def _document_selector(value: object) -> str:
    if isinstance(value, Mapping):
        value = cast(Mapping[str, object], value).get("document_selector")
    if value is None:
        return "main_document"
    if value in {"main", "main_document"}:
        return "main_document"
    if isinstance(value, str) and re.fullmatch(r"attachment_[1-9][0-9]*", value):
        return value
    raise MissingDocumentSuccessorError("document selector is invalid")


def _selector_from_record(record: Mapping[str, object]) -> str:
    if "document_selector" not in record:
        return _document_selector(None)
    value = record.get("document_selector")
    if value is None:
        raise MissingDocumentSuccessorError("document selector is invalid")
    return _document_selector(value)


def _v1_selector_spelling(canonical: str) -> str:
    return "main" if canonical == "main_document" else canonical


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MissingDocumentSuccessorError(f"{field} must be nonempty text")
    return value


def _required_bool(record: Mapping[str, object], field: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise MissingDocumentSuccessorError(f"{field} must be boolean")
    return value


def _money_value(value: object, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MissingDocumentSuccessorError(f"{label} is invalid") from exc
    if (
        not amount.is_finite()
        or amount < 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise MissingDocumentSuccessorError(f"{label} is invalid")
    return amount


def _positive_money(value: object, label: str) -> Decimal:
    amount = _money_value(value, label)
    if amount <= 0:
        raise MissingDocumentSuccessorError(f"{label} must be positive")
    return amount


def _raw_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MissingDocumentSuccessorError(f"{label} must be lowercase SHA-256")
    return value


def _commit_record(record: Mapping[str, object], *, domain: SchemaIdentifier) -> str:
    return str(ARTIFACT_RAW_SHA256_V1.commit(dict(record), domain=domain).digest)

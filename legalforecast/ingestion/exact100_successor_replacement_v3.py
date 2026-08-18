"""Versioned exact-100 successor admitting N exclusions and owner replacements.

v1 and v2 remain frozen, and this module does not touch either.  It supersedes
them the way v2 superseded v1: a new pinned projector with its own schemas and
its own sealed authority, chained to the current cohort head.

Three things are new here, and each answers a blocker the executability audit
recorded against the earlier executors:

* **N exclusions per run.** v2 required exactly one sealed terminal candidate,
  so a cohort carrying three ineligible targets could not be repaired at all.
  v3 admits a set, on the condition that every exclusion is paired with its own
  replacement, which is what keeps the emitted cohort at exactly 100.
* **A wider exclusion vocabulary, by supersession.** ``TerminalExclusionReason``
  is a closed pair frozen under ``…terminal_exclusion.v1``.  Rather than edit
  it, :class:`TerminalExclusionGroundV2` carries those two grounds forward and
  adds the owner-judgment ground the detector cannot reach -- a plaintiff's own
  Rule 41(a)(2) voluntary dismissal, which is not an adversarial
  claim-sufficiency motion and so is not a stipulation the detector matches.
* **Owner-adjudicated promotions.** v2 derived its promotion from the sealed
  wider-rank horizon.  Owner decision B4:A admits replacements adjudicated by
  the owner once that horizon is exhausted, so every promotion record here
  carries an explicit ``provenance_class`` distinguishing the two sources and
  refuses without complete provenance.

Everything else is deliberately unchanged from the v2 contract: exact-100
output, byte-canonical artifacts, no provider, retrieval, paid, model,
evaluation, freeze or dispatch capability, and no path or candidate-selection
API on the projector itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_PROMOTION_V3,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V3,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V2,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.owner_adjudicated_replacement import (
    VerifiedOwnerAdjudicatedReplacement,
    require_verified_owner_adjudicated_replacement,
)

JsonRecord = dict[str, Any]
DocumentKey = tuple[str, str]

CONFIG_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V3)
STATE_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
PROMOTION_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_PROMOTION_V3)
EXCLUSION_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V2)
STAGE = "project-exact100-successor-replacement-v3"

_TARGET_COUNT = 100
_BASE_SEAL = object()
_EXCLUSION_SEAL = object()


class Exact100SuccessorReplacementV3Error(ValueError):
    """Raised when v3 successor evidence does not reconcile exactly."""


class TerminalExclusionGroundV2(StrEnum):
    """Terminal grounds admitted by v3, superseding the frozen v1 pair.

    The first two are the v1 grounds, carried forward verbatim so an exclusion
    minted under v1 evidence keeps its meaning.  The third exists because the
    eligibility detector cannot reach a plaintiff's own Rule 41(a)(2) voluntary
    dismissal: it is not a stipulated dismissal and not an adversarial motion,
    so only an owner judgment can classify it.
    """

    STIPULATED_INELIGIBLE = "stipulated_ineligible"
    TERMINAL_MISSING_CORE_DOCUMENT = "terminal_missing_core_document"
    OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL = (
        "owner_adjudicated_rule_41_a_2_voluntary_dismissal"
    )


class PromotionProvenanceClass(StrEnum):
    """Where a promoted candidate came from.

    Recorded on every promotion so a reader never has to infer it, and so the
    Cycle 1 methods disclosure can be derived from the artifacts rather than
    from a lane's memory.
    """

    WIDER_RANK_DERIVED = "wider_rank_derived"
    OWNER_ADJUDICATED = "owner_adjudicated"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100V3Base:
    """Authenticated predecessor cohort surface, sealed after replay."""

    predecessor_run_card_bytes: bytes
    predecessor_schema_version: str
    predecessor_stage: str
    selection: tuple[JsonRecord, ...]
    selection_bytes: bytes
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    source_commitments: Mapping[str, str]
    integrity_sha256: str
    _verification_seal: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100V3TerminalExclusions:
    """Canonical N-member terminal subset accepted by the v3 projector."""

    records: tuple[JsonRecord, ...]
    records_bytes: bytes
    selection_sha256: str
    commitment_sha256: str
    _verification_seal: object = field(repr=False, compare=False)

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(cast(str, record["candidate_id"]) for record in self.records)


@dataclass(frozen=True, slots=True)
class Exact100SuccessorReplacementV3:
    """Closed v3 projection and its complete replay surface."""

    selection: tuple[JsonRecord, ...]
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    terminal_exclusions: tuple[JsonRecord, ...]
    promotions: tuple[JsonRecord, ...]
    config: JsonRecord
    state: JsonRecord

    @property
    def selection_bytes(self) -> bytes:
        return _jsonl_bytes(self.selection)

    @property
    def case_relevance_bytes(self) -> bytes:
        return _jsonl_bytes(self.case_relevance)

    @property
    def download_manifest_bytes(self) -> bytes:
        return _jsonl_bytes(self.download_manifest)

    @property
    def disclosure_clearance_bytes(self) -> bytes:
        return _jsonl_bytes(self.disclosure_clearance)

    @property
    def restriction_evidence_bytes(self) -> bytes:
        return _jsonl_bytes(self.restriction_evidence)

    @property
    def core_filter_results_bytes(self) -> bytes:
        return _jsonl_bytes(self.core_filter_results)

    @property
    def terminal_exclusions_bytes(self) -> bytes:
        return _jsonl_bytes(self.terminal_exclusions)

    @property
    def promotions_bytes(self) -> bytes:
        return _jsonl_bytes(self.promotions)

    @property
    def config_bytes(self) -> bytes:
        return _canonical_bytes(self.config)


def mint_verified_exact100_v3_base(
    *,
    predecessor_run_card_bytes: bytes,
    predecessor_schema_version: str,
    predecessor_stage: str,
    selection_rows: Sequence[Mapping[str, Any]],
    case_relevance_rows: Sequence[Mapping[str, Any]],
    download_manifest_rows: Sequence[Mapping[str, Any]],
    disclosure_rows: Sequence[Mapping[str, Any]],
    restriction_rows: Sequence[Mapping[str, Any]],
    core_filter_rows: Sequence[Mapping[str, Any]],
    source_commitments: Mapping[str, str],
) -> VerifiedExact100V3Base:
    """Seal the predecessor cohort surface after the CLI authenticated it."""

    selection = tuple(dict(row) for row in selection_rows)
    case_relevance = tuple(dict(row) for row in case_relevance_rows)
    manifest = tuple(dict(row) for row in download_manifest_rows)
    clearance = tuple(dict(row) for row in disclosure_rows)
    restriction = tuple(dict(row) for row in restriction_rows)
    core_filter = tuple(dict(row) for row in core_filter_rows)
    commitments = _validated_commitments(source_commitments)
    if not predecessor_schema_version or not predecessor_stage:
        raise Exact100SuccessorReplacementV3Error(
            "v3 predecessor lacks its schema or stage identity"
        )
    _require_unique_candidate_rows(selection, label="predecessor selection")
    if len(selection) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementV3Error(
            "v3 predecessor is not exactly 100 candidates"
        )
    selected_ids = {_candidate_id(row) for row in selection}
    _require_candidate_coverage(
        case_relevance, selected_ids, label="predecessor case relevance"
    )
    _require_candidate_coverage(
        core_filter, selected_ids, label="predecessor core filter"
    )
    _require_evidence_coverage(
        manifest,
        clearance=clearance,
        restriction=restriction,
        allowed_candidate_ids=selected_ids,
        label="predecessor",
    )
    integrity = _base_integrity_sha256(
        predecessor_run_card_bytes=predecessor_run_card_bytes,
        selection=selection,
        case_relevance=case_relevance,
        manifest=manifest,
        clearance=clearance,
        restriction=restriction,
        core_filter=core_filter,
        source_commitments=commitments,
    )
    value = object.__new__(VerifiedExact100V3Base)
    for name, item in (
        ("predecessor_run_card_bytes", bytes(predecessor_run_card_bytes)),
        ("predecessor_schema_version", predecessor_schema_version),
        ("predecessor_stage", predecessor_stage),
        ("selection", selection),
        ("selection_bytes", _jsonl_bytes(selection)),
        ("case_relevance", case_relevance),
        ("download_manifest", manifest),
        ("disclosure_clearance", clearance),
        ("restriction_evidence", restriction),
        ("core_filter_results", core_filter),
        ("source_commitments", MappingProxyType(commitments)),
        ("integrity_sha256", integrity),
        ("_verification_seal", _BASE_SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


def require_verified_exact100_v3_base(base: VerifiedExact100V3Base) -> None:
    """Reject a caller-created or mutated predecessor capability."""

    if (
        type(base) is not VerifiedExact100V3Base
        or getattr(base, "_verification_seal", None) is not _BASE_SEAL
        or base.selection_bytes != _jsonl_bytes(base.selection)
        or base.integrity_sha256
        != _base_integrity_sha256(
            predecessor_run_card_bytes=base.predecessor_run_card_bytes,
            selection=base.selection,
            case_relevance=base.case_relevance,
            manifest=base.download_manifest,
            clearance=base.disclosure_clearance,
            restriction=base.restriction_evidence,
            core_filter=base.core_filter_results,
            source_commitments=base.source_commitments,
        )
    ):
        raise Exact100SuccessorReplacementV3Error(
            "v3 predecessor base was not produced by authenticated replay"
        )


def mint_verified_exact100_v3_terminal_exclusions(
    *,
    selection_bytes: bytes,
    exclusions: Sequence[Mapping[str, Any]],
) -> VerifiedExact100V3TerminalExclusions:
    """Close N verified terminal facts into exact predecessor selection order.

    Each entry must already carry its authenticated ground.  Detector-derived
    grounds arrive with the eligibility-audit replay commitments that produced
    them; the owner-judgment ground arrives with the recorded owner disposition
    that is its only possible source.  Either way an exclusion without a
    citation refuses.
    """

    selected = _selection_index(selection_bytes)
    by_candidate: dict[str, JsonRecord] = {}
    for entry in exclusions:
        candidate_id = _text(entry, "candidate_id")
        if candidate_id not in selected:
            raise Exact100SuccessorReplacementV3Error(
                "terminal exclusion candidate is outside the exact selection"
            )
        if candidate_id in by_candidate:
            raise Exact100SuccessorReplacementV3Error(
                f"duplicate terminal exclusion candidate: {candidate_id}"
            )
        ground = _ground(entry)
        evidence_commitments = _commitment_map(
            entry.get("evidence_commitments"), label="terminal exclusion evidence"
        )
        owner_commitments = _commitment_map(
            entry.get("owner_authorization_commitments"),
            label="terminal exclusion owner authorization",
        )
        if not owner_commitments:
            raise Exact100SuccessorReplacementV3Error(
                "terminal exclusion lacks its owner authorization citation"
            )
        detector_derived = ground is not (
            TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
        )
        if detector_derived:
            if evidence_commitments.get("selection") != _sha(selection_bytes):
                raise Exact100SuccessorReplacementV3Error(
                    "terminal evidence binds a different exact selection"
                )
        elif evidence_commitments:
            raise Exact100SuccessorReplacementV3Error(
                "an owner-judgment exclusion must not claim detector evidence"
            )
        by_candidate[candidate_id] = {
            "schema_version": EXCLUSION_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_document_id": _text(entry, "source_document_id"),
            "ground": ground.value,
            "evidence_class": (
                "authenticated_stage_a_target_eligibility_replay"
                if detector_derived
                else "recorded_owner_adjudication"
            ),
            "evidence_commitments": dict(sorted(evidence_commitments.items())),
            "owner_authorization_commitments": dict(sorted(owner_commitments.items())),
        }
    if not by_candidate:
        raise Exact100SuccessorReplacementV3Error(
            "v3 successor replacement requires at least one terminal exclusion"
        )
    records = tuple(
        by_candidate[candidate_id]
        for candidate_id in selected
        if candidate_id in by_candidate
    )
    records_bytes = _jsonl_bytes(records)
    value = object.__new__(VerifiedExact100V3TerminalExclusions)
    for name, item in (
        ("records", records),
        ("records_bytes", records_bytes),
        ("selection_sha256", _sha(selection_bytes)),
        ("commitment_sha256", _sha(records_bytes)),
        ("_verification_seal", _EXCLUSION_SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


def require_verified_exact100_v3_terminal_exclusions(
    authority: VerifiedExact100V3TerminalExclusions,
) -> None:
    """Reject a changed or caller-constructed terminal subset."""

    if (
        type(authority) is not VerifiedExact100V3TerminalExclusions
        or getattr(authority, "_verification_seal", None) is not _EXCLUSION_SEAL
        or authority.records_bytes != _jsonl_bytes(authority.records)
        or authority.commitment_sha256 != _sha(authority.records_bytes)
    ):
        raise Exact100SuccessorReplacementV3Error(
            "v3 terminal exclusions were not produced by verified replay"
        )


def project_exact100_successor_replacement_v3(
    *,
    base: VerifiedExact100V3Base,
    terminal_exclusions: VerifiedExact100V3TerminalExclusions,
    replacements: Sequence[VerifiedOwnerAdjudicatedReplacement],
) -> Exact100SuccessorReplacementV3:
    """Derive the successor cohort from sealed exclusions and replacements."""

    require_verified_exact100_v3_base(base)
    require_verified_exact100_v3_terminal_exclusions(terminal_exclusions)
    for replacement in replacements:
        require_verified_owner_adjudicated_replacement(replacement)
    if terminal_exclusions.selection_sha256 != _sha(base.selection_bytes):
        raise Exact100SuccessorReplacementV3Error(
            "terminal exclusions bind a different predecessor selection"
        )

    terminal_ids = terminal_exclusions.candidate_ids
    by_slot: dict[str, VerifiedOwnerAdjudicatedReplacement] = {}
    for replacement in replacements:
        if replacement.replaces_candidate_id in by_slot:
            raise Exact100SuccessorReplacementV3Error(
                "two replacements claim the same excluded slot"
            )
        by_slot[replacement.replaces_candidate_id] = replacement
    # Pairing is the invariant that keeps the cohort at exactly 100: one
    # exclusion removes a row, one promotion restores it, and neither is
    # permitted alone.
    if set(by_slot) != set(terminal_ids):
        raise Exact100SuccessorReplacementV3Error(
            "every terminal exclusion needs exactly one paired replacement"
        )
    promoted_ids = [replacement.candidate_id for replacement in replacements]
    if len(set(promoted_ids)) != len(promoted_ids):
        raise Exact100SuccessorReplacementV3Error(
            "a replacement candidate was promoted into two slots"
        )
    selected_ids = {_candidate_id(row) for row in base.selection}
    if any(promoted_id in selected_ids for promoted_id in promoted_ids):
        raise Exact100SuccessorReplacementV3Error(
            "a promoted candidate is already inside the predecessor cohort"
        )

    ordered = tuple(by_slot[candidate_id] for candidate_id in terminal_ids)
    retained = tuple(
        dict(row)
        for row in base.selection
        if _candidate_id(row) not in set(terminal_ids)
    )
    selection = (*retained, *(dict(item.selection_row) for item in ordered))
    final_ids = tuple(_candidate_id(row) for row in selection)
    if len(selection) != _TARGET_COUNT or len(set(final_ids)) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementV3Error(
            "v3 successor is not exactly 100 unique candidates"
        )

    case_relevance = _replace_candidate_rows(
        base.case_relevance,
        tuple(dict(item.case_relevance_row) for item in ordered),
        terminal_ids=terminal_ids,
    )
    download_manifest = _replace_candidate_rows(
        base.download_manifest,
        tuple(row for item in ordered for row in item.download_manifest),
        terminal_ids=terminal_ids,
    )
    disclosure_clearance = _replace_candidate_rows(
        base.disclosure_clearance,
        tuple(row for item in ordered for row in item.disclosure_clearance),
        terminal_ids=terminal_ids,
    )
    restriction_evidence = _replace_candidate_rows(
        base.restriction_evidence,
        tuple(row for item in ordered for row in item.restriction_evidence),
        terminal_ids=terminal_ids,
    )
    core_results = tuple(
        result.to_record() for result in filter_core_documents(case_relevance)
    )
    for replacement in ordered:
        _require_clean_core_result(core_results, promoted_id=replacement.candidate_id)
    _require_evidence_coverage(
        download_manifest,
        clearance=disclosure_clearance,
        restriction=restriction_evidence,
        allowed_candidate_ids=set(final_ids),
        label="successor",
    )

    exclusion_by_candidate = {
        cast(str, record["candidate_id"]): record
        for record in terminal_exclusions.records
    }
    promotions = tuple(
        {
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "candidate_id": replacement.candidate_id,
            "replaces_candidate_id": replacement.replaces_candidate_id,
            "provenance_class": PromotionProvenanceClass.OWNER_ADJUDICATED.value,
            "wider_rank": None,
            "exclusion_ground": exclusion_by_candidate[
                replacement.replaces_candidate_id
            ]["ground"],
            "replacement_evidence_sha256": replacement.commitment_sha256,
            "final_selection_row_sha256": _sha(
                _canonical_bytes(dict(replacement.selection_row))
            ),
            "required_document_sha256": dict(replacement.required_document_sha256),
            "identity_field_provenance": dict(replacement.field_provenance),
            "source_commitments": dict(replacement.source_commitments),
        }
        for replacement in ordered
    )

    outputs = {
        "target-cohort-selection.jsonl": _jsonl_bytes(selection),
        "case-relevance.jsonl": _jsonl_bytes(case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(download_manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(disclosure_clearance),
        "restriction-evidence.jsonl": _jsonl_bytes(restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(core_results),
        "successor-terminal-exclusions.jsonl": terminal_exclusions.records_bytes,
        "successor-promotions.jsonl": _jsonl_bytes(promotions),
    }
    source_commitments = dict(
        sorted(
            {
                **base.source_commitments,
                "terminal_exclusions": terminal_exclusions.commitment_sha256,
                **{
                    f"replacement_{replacement.candidate_id}": (
                        replacement.commitment_sha256
                    )
                    for replacement in ordered
                },
            }.items()
        )
    )
    config: JsonRecord = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "target_case_count": _TARGET_COUNT,
        "predecessor_schema_version": base.predecessor_schema_version,
        "predecessor_stage": base.predecessor_stage,
        "terminal_exclusion_count": len(terminal_ids),
        "terminal_candidate_ids": list(terminal_ids),
        "promoted_candidate_ids": [item.candidate_id for item in ordered],
        "promotion_provenance_classes": sorted(
            {PromotionProvenanceClass.OWNER_ADJUDICATED.value}
        ),
        "source_commitments": source_commitments,
        "output_commitments": {
            name: _sha(payload) for name, payload in outputs.items()
        },
        "provider_activity_permitted": False,
        "courtlistener_activity_permitted": False,
        "pacer_activity_permitted": False,
        "recap_fetch_activity_permitted": False,
        "paid_activity_permitted": False,
        "model_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    state: JsonRecord = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "completed",
        "target_case_count": _TARGET_COUNT,
        "predecessor_case_count": _TARGET_COUNT,
        "retained_case_count": _TARGET_COUNT - len(terminal_ids),
        "terminal_exclusion_count": len(terminal_ids),
        "promotion_count": len(ordered),
        "selected_case_count": _TARGET_COUNT,
        "terminal_candidate_ids": list(terminal_ids),
        "promoted_candidate_ids": [item.candidate_id for item in ordered],
        "config_sha256": _sha(_canonical_bytes(config)),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "courtlistener_activity_requested": False,
        "courtlistener_activity_executed": False,
        "pacer_activity_requested": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_requested": False,
        "recap_fetch_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "model_activity_requested": False,
        "model_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    return Exact100SuccessorReplacementV3(
        selection=selection,
        case_relevance=case_relevance,
        download_manifest=download_manifest,
        disclosure_clearance=disclosure_clearance,
        restriction_evidence=restriction_evidence,
        core_filter_results=core_results,
        terminal_exclusions=terminal_exclusions.records,
        promotions=promotions,
        config=config,
        state=state,
    )


def methods_disclosure_text(result: Exact100SuccessorReplacementV3) -> str:
    """Derive the Cycle 1 methods sentence from the emitted promotions.

    The disclosure is generated from the artifacts rather than written by hand
    so the report can never claim a promotion source the cohort does not carry.
    """

    owner_adjudicated = tuple(
        record
        for record in result.promotions
        if record.get("provenance_class")
        == PromotionProvenanceClass.OWNER_ADJUDICATED.value
    )
    if not owner_adjudicated:
        return (
            "Every exact-100 replacement in this cohort was derived from the "
            "sealed wider-rank reserve horizon."
        )
    pairs = ", ".join(
        f"{cast(str, record['candidate_id'])} for "
        f"{cast(str, record['replaces_candidate_id'])}"
        for record in owner_adjudicated
    )
    count = len(owner_adjudicated)
    noun = "replacement" if count == 1 else "replacements"
    return (
        f"{count} exact-100 {noun} entered the cohort by owner adjudication "
        "rather than by derivation from the sealed wider-rank reserve horizon, "
        "the reserve having been exhausted. Each carries a recorded owner "
        "disposition, complete packet evidence, and byte-role validated "
        f"documents ({pairs}). All remaining cohort members were selected and "
        "replaced by the sealed ranking procedure described above."
    )


def _base_integrity_sha256(
    *,
    predecessor_run_card_bytes: bytes,
    selection: Sequence[Mapping[str, Any]],
    case_relevance: Sequence[Mapping[str, Any]],
    manifest: Sequence[Mapping[str, Any]],
    clearance: Sequence[Mapping[str, Any]],
    restriction: Sequence[Mapping[str, Any]],
    core_filter: Sequence[Mapping[str, Any]],
    source_commitments: Mapping[str, str],
) -> str:
    return _sha(
        _canonical_bytes(
            {
                "predecessor_run_card": _sha(predecessor_run_card_bytes),
                "selection": _sha(_jsonl_bytes(selection)),
                "case_relevance": _sha(_jsonl_bytes(case_relevance)),
                "download_manifest": _sha(_jsonl_bytes(manifest)),
                "disclosure_clearance": _sha(_jsonl_bytes(clearance)),
                "restriction_evidence": _sha(_jsonl_bytes(restriction)),
                "core_filter_results": _sha(_jsonl_bytes(core_filter)),
                "source_commitments": dict(source_commitments),
            }
        )
    )


def _ground(entry: Mapping[str, Any]) -> TerminalExclusionGroundV2:
    value = entry.get("ground")
    try:
        return TerminalExclusionGroundV2(value)
    except ValueError as exc:
        raise Exact100SuccessorReplacementV3Error(
            "terminal exclusion ground is outside the v3 vocabulary"
        ) from exc


def _replace_candidate_rows(
    base: Sequence[Mapping[str, Any]],
    promoted: Sequence[Mapping[str, Any]],
    *,
    terminal_ids: Sequence[str],
) -> tuple[JsonRecord, ...]:
    excluded = set(terminal_ids)
    return (
        *(dict(row) for row in base if _candidate_id(row) not in excluded),
        *(dict(row) for row in promoted),
    )


def _require_evidence_coverage(
    manifest: Sequence[Mapping[str, Any]],
    *,
    clearance: Sequence[Mapping[str, Any]],
    restriction: Sequence[Mapping[str, Any]],
    allowed_candidate_ids: set[str],
    label: str,
) -> None:
    manifest_by_key = _unique_documents(manifest, label=f"{label} manifest")
    clearance_by_key = _unique_documents(clearance, label=f"{label} clearance")
    restriction_by_key = _unique_documents(restriction, label=f"{label} restriction")
    if (
        not manifest_by_key
        or set(manifest_by_key) != set(clearance_by_key)
        or set(manifest_by_key) != set(restriction_by_key)
    ):
        raise Exact100SuccessorReplacementV3Error(
            f"{label} materialized evidence coverage differs"
        )
    if {candidate_id for candidate_id, _ in manifest_by_key} - allowed_candidate_ids:
        raise Exact100SuccessorReplacementV3Error(
            f"{label} materialized evidence contains an unselected candidate"
        )
    for key, document in manifest_by_key.items():
        clear = clearance_by_key[key]
        restricted = restriction_by_key[key]
        if (
            clear.get("status") != "cleared"
            or restricted.get("is_sealed") is True
            or restricted.get("is_private") is True
            or _hex(clear, "sha256") != _hex(document, "sha256")
            or clear.get("byte_count") != document.get("byte_count")
        ):
            raise Exact100SuccessorReplacementV3Error(
                f"{label} document is not cleared and public: {key[0]}/{key[1]}"
            )


def _require_clean_core_result(
    rows: Sequence[Mapping[str, Any]], *, promoted_id: str
) -> None:
    matches = [row for row in rows if _candidate_id(row) == promoted_id]
    if len(matches) != 1:
        raise Exact100SuccessorReplacementV3Error(
            f"promoted candidate lacks one core-filter result: {promoted_id}"
        )
    row = matches[0]
    if (
        row.get("excluded") is not False
        or row.get("missing_operative_complaint") is not False
        or row.get("missing_core_roles") not in ([], ())
    ):
        raise Exact100SuccessorReplacementV3Error(
            f"promoted candidate packet is incomplete: {promoted_id}"
        )


def _require_unique_candidate_rows(
    rows: Sequence[Mapping[str, Any]], *, label: str
) -> None:
    ids = [_candidate_id(row) for row in rows]
    if len(ids) != len(set(ids)):
        raise Exact100SuccessorReplacementV3Error(f"{label} repeats a candidate")


def _require_candidate_coverage(
    rows: Sequence[Mapping[str, Any]], candidate_ids: set[str], *, label: str
) -> None:
    _require_unique_candidate_rows(rows, label=label)
    if {_candidate_id(row) for row in rows} != candidate_ids:
        raise Exact100SuccessorReplacementV3Error(
            f"{label} does not exactly cover the predecessor"
        )


def _unique_documents(
    rows: Sequence[Mapping[str, Any]], *, label: str
) -> dict[DocumentKey, Mapping[str, Any]]:
    result: dict[DocumentKey, Mapping[str, Any]] = {}
    for row in rows:
        key = (_candidate_id(row), _text(row, "source_document_id"))
        if key in result:
            raise Exact100SuccessorReplacementV3Error(f"{label} repeats a document")
        result[key] = row
    return result


def _selection_index(selection_bytes: bytes) -> dict[str, JsonRecord]:
    records = _jsonl_records(selection_bytes)
    result: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _text(record, "candidate_id")
        if candidate_id in result:
            raise Exact100SuccessorReplacementV3Error(
                "exact selection contains a duplicate candidate"
            )
        result[candidate_id] = record
    if len(result) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementV3Error(
            "terminal exclusions require the exact 100-case selection"
        )
    return result


def _jsonl_records(payload: bytes) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for raw_line in payload.splitlines():
        if not raw_line.strip():
            raise Exact100SuccessorReplacementV3Error("selection has a blank line")
        try:
            record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Exact100SuccessorReplacementV3Error(
                "selection line is invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise Exact100SuccessorReplacementV3Error("selection line is not an object")
        records.append(cast(JsonRecord, record))
    if _jsonl_bytes(records) != payload:
        raise Exact100SuccessorReplacementV3Error("selection is not canonical JSONL")
    return records


def _commitment_map(value: object, *, label: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise Exact100SuccessorReplacementV3Error(f"{label} commitments are malformed")
    result: dict[str, str] = {}
    for name, item in cast(Mapping[object, object], value).items():
        if not isinstance(name, str) or not name or not isinstance(item, str):
            raise Exact100SuccessorReplacementV3Error(
                f"{label} commitments are malformed"
            )
        raw = item.removeprefix("sha256:")
        if len(raw) != 64 or any(ch not in "0123456789abcdef" for ch in raw):
            raise Exact100SuccessorReplacementV3Error(f"{label} commitment is invalid")
        result[name] = "sha256:" + raw
    return result


def _validated_commitments(values: Mapping[str, str]) -> dict[str, str]:
    if not values:
        raise Exact100SuccessorReplacementV3Error("v3 source commitments are required")
    result: dict[str, str] = {}
    for name, value in values.items():
        raw = value.removeprefix("sha256:")
        if (
            not name
            or len(raw) != 64
            or any(ch not in "0123456789abcdef" for ch in raw)
        ):
            raise Exact100SuccessorReplacementV3Error("v3 source commitment is invalid")
        result[name] = "sha256:" + raw
    return dict(sorted(result.items()))


def _candidate_id(row: Mapping[str, Any]) -> str:
    return _text(row, "candidate_id")


def _text(row: Mapping[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value:
        raise Exact100SuccessorReplacementV3Error(f"record lacks {field_name}")
    return value


def _hex(row: Mapping[str, Any], field_name: str) -> str:
    value = _text(row, field_name).removeprefix("sha256:")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise Exact100SuccessorReplacementV3Error(f"record has invalid {field_name}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementV3Error,
        error_message="v3 successor serialization failed",
    )


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(row)) for row in rows)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

"""Versioned provider-free exact-100 replacement over a wider rank horizon.

The v1 successor remains frozen.  This module consumes only verifier-owned
capabilities: a complete current materialization of the exact predecessor, the
sealed terminal exclusion, byte-derived semantic repairs, and the complete
wider-rank result.  It has no path, provider, or candidate-selection API.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_PROMOTION_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2,
    ZERO_COST_SUCCESSOR_CONFIG_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.exact100_successor_semantic_repair import (
    VerifiedExact100SuccessorSemanticRepairs,
    require_verified_exact100_successor_semantic_repairs,
)
from legalforecast.ingestion.exact100_successor_wider_rank import (
    VerifiedExact100SuccessorWiderRank,
    require_verified_exact100_successor_wider_rank,
    required_packet_roles,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    VerifiedPostSelectionTerminalExclusions,
    require_verified_post_selection_terminal_exclusions,
)

JsonRecord = dict[str, Any]
DocumentKey = tuple[str, str]

CONFIG_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V2)
STATE_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2)
PROMOTION_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_PROMOTION_V2)

_TARGET_COUNT = 100
_BASE_SEAL = object()
_PUBLIC_UNKNOWN_RESTRICTION_EVIDENCE = frozenset(
    {
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    }
)


class Exact100SuccessorReplacementV2Error(ValueError):
    """Raised when v2 successor evidence does not reconcile exactly."""


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100V2Base:
    """Complete predecessor surface sealed after root-30/root-32 replay."""

    predecessor_projection_bytes: bytes
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


@dataclass(frozen=True, slots=True)
class Exact100SuccessorReplacementV2:
    """Closed v2 projection and its complete replay surface."""

    selection: tuple[JsonRecord, ...]
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    terminal_exclusions: tuple[JsonRecord, ...]
    semantic_repairs: tuple[JsonRecord, ...]
    wider_rank_ledger: tuple[JsonRecord, ...]
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
    def semantic_repairs_bytes(self) -> bytes:
        return _jsonl_bytes(self.semantic_repairs)

    @property
    def wider_rank_ledger_bytes(self) -> bytes:
        return _jsonl_bytes(self.wider_rank_ledger)

    @property
    def promotions_bytes(self) -> bytes:
        return _jsonl_bytes(self.promotions)

    @property
    def config_bytes(self) -> bytes:
        return _canonical_bytes(self.config)


def _mint_verified_exact100_v2_base(  # pyright: ignore[reportUnusedFunction]
    *,
    predecessor_projection_bytes: bytes,
    selection_rows: Sequence[Mapping[str, Any]],
    case_relevance_rows: Sequence[Mapping[str, Any]],
    download_manifest_rows: Sequence[Mapping[str, Any]],
    disclosure_rows: Sequence[Mapping[str, Any]],
    restriction_rows: Sequence[Mapping[str, Any]],
    core_filter_rows: Sequence[Mapping[str, Any]],
    source_commitments: Mapping[str, str],
) -> VerifiedExact100V2Base:
    """Mint the v2 base only after the CLI replays both predecessor surfaces."""

    selection = tuple(dict(row) for row in selection_rows)
    case_relevance = tuple(dict(row) for row in case_relevance_rows)
    manifest = tuple(dict(row) for row in download_manifest_rows)
    clearance = tuple(dict(row) for row in disclosure_rows)
    restriction = tuple(dict(row) for row in restriction_rows)
    core_filter = tuple(dict(row) for row in core_filter_rows)
    commitments = _validated_commitments(source_commitments)
    _require_unique_candidate_rows(selection, label="predecessor selection")
    if len(selection) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementV2Error(
            "v2 predecessor is not exactly 100 candidates"
        )
    selected_ids = {_candidate_id(row) for row in selection}
    _require_candidate_coverage(
        case_relevance, selected_ids, label="predecessor case relevance"
    )
    _require_candidate_coverage(
        core_filter, selected_ids, label="predecessor core filter"
    )
    _require_materialized_evidence(
        manifest,
        clearance=clearance,
        restriction=restriction,
        allowed_candidate_ids=selected_ids,
        label="predecessor",
    )
    integrity_sha256 = _base_integrity_sha256(
        predecessor_projection_bytes=predecessor_projection_bytes,
        selection=selection,
        case_relevance=case_relevance,
        manifest=manifest,
        clearance=clearance,
        restriction=restriction,
        core_filter=core_filter,
        source_commitments=commitments,
    )
    value = object.__new__(VerifiedExact100V2Base)
    for name, item in (
        ("predecessor_projection_bytes", bytes(predecessor_projection_bytes)),
        ("selection", selection),
        ("selection_bytes", _jsonl_bytes(selection)),
        ("case_relevance", case_relevance),
        ("download_manifest", manifest),
        ("disclosure_clearance", clearance),
        ("restriction_evidence", restriction),
        ("core_filter_results", core_filter),
        ("source_commitments", MappingProxyType(commitments)),
        ("integrity_sha256", integrity_sha256),
        ("_verification_seal", _BASE_SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


def require_verified_exact100_v2_base(base: VerifiedExact100V2Base) -> None:
    """Reject caller-created or changed complete-materialization capabilities."""

    if (
        type(base) is not VerifiedExact100V2Base
        or getattr(base, "_verification_seal", None) is not _BASE_SEAL
    ):
        raise Exact100SuccessorReplacementV2Error(
            "v2 predecessor base was not produced by authenticated replay"
        )
    replay = _mint_verified_exact100_v2_base(
        predecessor_projection_bytes=base.predecessor_projection_bytes,
        selection_rows=base.selection,
        case_relevance_rows=base.case_relevance,
        download_manifest_rows=base.download_manifest,
        disclosure_rows=base.disclosure_clearance,
        restriction_rows=base.restriction_evidence,
        core_filter_rows=base.core_filter_results,
        source_commitments=base.source_commitments,
    )
    if (
        base.integrity_sha256
        != _base_integrity_sha256(
            predecessor_projection_bytes=base.predecessor_projection_bytes,
            selection=base.selection,
            case_relevance=base.case_relevance,
            manifest=base.download_manifest,
            clearance=base.disclosure_clearance,
            restriction=base.restriction_evidence,
            core_filter=base.core_filter_results,
            source_commitments=base.source_commitments,
        )
        or base.integrity_sha256 != replay.integrity_sha256
        or base.predecessor_projection_bytes != replay.predecessor_projection_bytes
        or base.selection != replay.selection
        or base.selection_bytes != replay.selection_bytes
        or base.case_relevance != replay.case_relevance
        or base.download_manifest != replay.download_manifest
        or base.disclosure_clearance != replay.disclosure_clearance
        or base.restriction_evidence != replay.restriction_evidence
        or base.core_filter_results != replay.core_filter_results
        or base.source_commitments != replay.source_commitments
    ):
        raise Exact100SuccessorReplacementV2Error(
            "v2 predecessor base changed after authenticated replay"
        )


def _base_integrity_sha256(
    *,
    predecessor_projection_bytes: bytes,
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
                "predecessor_projection": _sha(predecessor_projection_bytes),
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


def project_exact100_successor_replacement_v2(
    *,
    base: VerifiedExact100V2Base,
    terminal_exclusions: VerifiedPostSelectionTerminalExclusions,
    semantic_repairs: VerifiedExact100SuccessorSemanticRepairs,
    wider_rank: VerifiedExact100SuccessorWiderRank,
) -> Exact100SuccessorReplacementV2:
    """Derive the sole v2 replacement from sealed evidence and ranking."""

    require_verified_exact100_v2_base(base)
    require_verified_post_selection_terminal_exclusions(terminal_exclusions)
    require_verified_exact100_successor_semantic_repairs(semantic_repairs)
    require_verified_exact100_successor_wider_rank(wider_rank)
    if terminal_exclusions.selection_sha256 != _sha(base.selection_bytes):
        raise Exact100SuccessorReplacementV2Error(
            "terminal exclusion binds a different predecessor selection"
        )
    terminal_ids = terminal_exclusions.candidate_ids
    if len(terminal_ids) != 1:
        raise Exact100SuccessorReplacementV2Error(
            "v2 requires exactly one sealed terminal candidate"
        )
    selected_ids = {_candidate_id(row) for row in base.selection}
    terminal_id = terminal_ids[0]
    promoted_id = wider_rank.selected_candidate_id
    if terminal_id not in selected_ids or promoted_id in selected_ids:
        raise Exact100SuccessorReplacementV2Error(
            "terminal or promoted candidate lies outside the required partition"
        )
    required_promotion_roles = required_packet_roles(
        wider_rank.selected_selection_row,
        materialized_documents=wider_rank.selected_evidence.download_manifest,
    )
    promotion_row, promoted_relevance, promoted_manifest = _promoted_surfaces(
        wider_rank=wider_rank,
        repairs=semantic_repairs,
        required_roles=required_promotion_roles,
    )
    retained = tuple(
        dict(row) for row in base.selection if _candidate_id(row) != terminal_id
    )
    selection = (*retained, promotion_row)
    final_ids = tuple(_candidate_id(row) for row in selection)
    if len(selection) != _TARGET_COUNT or len(set(final_ids)) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementV2Error(
            "v2 successor is not exactly 100 unique candidates"
        )
    case_relevance = _replace_candidate_rows(
        base.case_relevance,
        (promoted_relevance,),
        terminal_id=terminal_id,
        promoted_id=promoted_id,
    )
    download_manifest = _replace_candidate_rows(
        base.download_manifest,
        promoted_manifest,
        terminal_id=terminal_id,
        promoted_id=promoted_id,
    )
    evidence = wider_rank.selected_evidence
    disclosure_clearance = _replace_candidate_rows(
        base.disclosure_clearance,
        evidence.disclosure_clearance,
        terminal_id=terminal_id,
        promoted_id=promoted_id,
    )
    restriction_evidence = _replace_candidate_rows(
        base.restriction_evidence,
        evidence.restriction_evidence,
        terminal_id=terminal_id,
        promoted_id=promoted_id,
    )
    core_results = tuple(
        result.to_record() for result in filter_core_documents(case_relevance)
    )
    _require_clean_core_result(core_results, promoted_id=promoted_id)
    _require_materialized_evidence(
        download_manifest,
        clearance=disclosure_clearance,
        restriction=restriction_evidence,
        allowed_candidate_ids=set(final_ids),
        label="successor",
    )
    selected_rank = _selected_promotion_rank(wider_rank)
    promotion = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "candidate_id": promoted_id,
        "wider_rank": selected_rank,
        "source_selection_row_sha256": _sha(
            _canonical_bytes(wider_rank.selected_selection_row)
        ),
        "final_selection_row_sha256": _sha(_canonical_bytes(promotion_row)),
        "semantic_repairs_sha256": semantic_repairs.commitment_sha256,
        "earlier_rank_horizon_sha256": _sha(
            _jsonl_bytes(
                tuple(
                    row
                    for row in wider_rank.ordered_ledger
                    if cast(int, row["rank"]) <= selected_rank
                )
            )
        ),
        "required_document_sha256": {
            _required_text(row, "source_document_id"): _raw_sha(row, "sha256")
            for row in promoted_manifest
            if _required_role(_semantic_role(row, semantic_repairs))
            in required_promotion_roles
        },
        "disposition_class": "moot_non_merits_disposition",
    }
    outputs = {
        "target-cohort-selection.jsonl": _jsonl_bytes(selection),
        "case-relevance.jsonl": _jsonl_bytes(case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(download_manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(disclosure_clearance),
        "restriction-evidence.jsonl": _jsonl_bytes(restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(core_results),
        "successor-terminal-exclusions.jsonl": terminal_exclusions.records_bytes,
        "successor-semantic-repairs.jsonl": semantic_repairs.records_bytes,
        "successor-wider-rank-ledger.jsonl": _jsonl_bytes(wider_rank.ordered_ledger),
        "successor-promotions.jsonl": _jsonl_bytes((promotion,)),
    }
    source_commitments = dict(
        sorted(
            {
                **base.source_commitments,
                **{
                    f"wider_{name}": value
                    for name, value in wider_rank.source_commitments.items()
                },
                "terminal_exclusions": terminal_exclusions.commitment_sha256,
                "semantic_repairs": semantic_repairs.commitment_sha256,
                **{
                    f"semantic_{name}": value
                    for name, value in semantic_repairs.source_commitments.items()
                },
            }.items()
        )
    )
    config: JsonRecord = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "target_case_count": _TARGET_COUNT,
        "predecessor_schema_version": str(ZERO_COST_SUCCESSOR_CONFIG_V1),
        "terminal_exclusion_count": 1,
        "promoted_candidate_ids": [promoted_id],
        "ranking_policy": [
            "missing_required_document_count",
            "projected_paid_cost_usd",
            "candidate_id_casefold",
            "candidate_id",
        ],
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
    config_bytes = _canonical_bytes(config)
    state: JsonRecord = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "completed",
        "target_case_count": _TARGET_COUNT,
        "predecessor_case_count": _TARGET_COUNT,
        "retained_case_count": _TARGET_COUNT - 1,
        "terminal_exclusion_count": 1,
        "promotion_count": 1,
        "selected_case_count": _TARGET_COUNT,
        "terminal_candidate_ids": [terminal_id],
        "promoted_candidate_ids": [promoted_id],
        "config_sha256": _sha(config_bytes),
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
    return Exact100SuccessorReplacementV2(
        selection=selection,
        case_relevance=case_relevance,
        download_manifest=download_manifest,
        disclosure_clearance=disclosure_clearance,
        restriction_evidence=restriction_evidence,
        core_filter_results=core_results,
        terminal_exclusions=terminal_exclusions.records,
        semantic_repairs=semantic_repairs.records,
        wider_rank_ledger=wider_rank.ordered_ledger,
        promotions=(promotion,),
        config=config,
        state=state,
    )


def _promoted_surfaces(
    *,
    wider_rank: VerifiedExact100SuccessorWiderRank,
    repairs: VerifiedExact100SuccessorSemanticRepairs,
    required_roles: frozenset[str],
) -> tuple[JsonRecord, JsonRecord, tuple[JsonRecord, ...]]:
    candidate_id = wider_rank.selected_candidate_id
    evidence = wider_rank.selected_evidence
    manifest = tuple(dict(row) for row in evidence.download_manifest)
    if not manifest:
        raise Exact100SuccessorReplacementV2Error(
            "promoted candidate lacks its authenticated document manifest"
        )
    clearance_by_id = _rows_by_document(evidence.disclosure_clearance)
    restriction_by_id = _rows_by_document(evidence.restriction_evidence)
    documents: list[JsonRecord] = []
    present_required_roles: set[str] = set()
    for row in sorted(
        manifest,
        key=lambda item: (
            item.get("docket_entry_number") is None,
            item.get("docket_entry_number") or 0,
            _required_text(item, "source_document_id"),
        ),
    ):
        source_document_id = _required_text(row, "source_document_id")
        role = _semantic_role(row, repairs)
        if role == "amended_complaint":
            model_role = "amended_complaint"
            present_required_roles.add("complaint")
        else:
            model_role = role
            if role in required_roles:
                present_required_roles.add(role)
        restrictions = restriction_by_id.get(source_document_id, ())
        clearances = clearance_by_id.get(source_document_id, ())
        if len(restrictions) != 1 or len(clearances) != 1:
            raise Exact100SuccessorReplacementV2Error(
                "promoted document lacks exact clearance/restriction coverage"
            )
        restriction = restrictions[0]
        documents.append(
            {
                "candidate_id": candidate_id,
                "contains_target_outcome": model_role == "decision",
                "description": _document_description(model_role),
                "docket_entry_number": row.get("docket_entry_number"),
                "document_role": model_role,
                "is_private": restriction.get("is_private"),
                "is_sealed": restriction.get("is_sealed"),
                "model_visible": model_role != "decision",
                "redaction_or_seal_status": "public",
                "restriction_evidence": list(
                    cast(Sequence[str], restriction.get("restriction_evidence", ()))
                ),
                "setup_runner_label": (
                    "core_mtd" if model_role != "decision" else "other_substantive"
                ),
                "source_document_id": source_document_id,
                "source_url": row.get("source_url"),
            }
        )
    if present_required_roles != set(required_roles):
        raise Exact100SuccessorReplacementV2Error(
            "promoted packet does not contain every required semantic role"
        )
    base = dict(wider_rank.selected_selection_row)
    base.update(
        {
            "candidate_id": candidate_id,
            "case_id": candidate_id,
            "cost_rank": _selected_promotion_rank(wider_rank),
            "documents": documents,
            "exclusion_reasons": [],
            "free_required_document_count": len(required_roles),
            "missing_required_document_count": 0,
            "paid_gap_reasons": [],
            "paid_recovery_required": False,
            "planning_status": "provider_free_packet_complete",
            "projected_paid_cost_usd": "0.00",
            "required_document_count": len(required_roles),
            "selected": True,
        }
    )
    for stale in ("resolved_paid_gap_reasons", "document_recovery_status"):
        base.pop(stale, None)
    return base, dict(base), manifest


def _semantic_role(
    document: Mapping[str, Any], repairs: VerifiedExact100SuccessorSemanticRepairs
) -> str:
    candidate_id = _candidate_id(document)
    source_document_id = _required_text(document, "source_document_id")
    matching = tuple(
        record
        for record in repairs.records
        if record.get("candidate_id") == candidate_id
        and record.get("source_document_id") == source_document_id
    )
    if len(matching) > 1:
        raise Exact100SuccessorReplacementV2Error(
            "one promoted document has multiple derived roles"
        )
    if not matching:
        return _required_text(document, "document_role")
    repair = matching[0]
    if (
        _raw_sha(repair, "source_sha256") != _raw_sha(document, "sha256")
        or repair.get("source_byte_count") != document.get("byte_count")
        or _raw_sha(repair, "source_metadata_sha256")
        != hashlib.sha256(_canonical_bytes(dict(document))).hexdigest()
    ):
        raise Exact100SuccessorReplacementV2Error(
            "semantic repair source does not bind promoted document"
        )
    return _required_text(repair, "derived_document_role")


def _selected_promotion_rank(
    wider_rank: VerifiedExact100SuccessorWiderRank,
) -> int:
    rank = next(
        (
            row.get("rank")
            for row in wider_rank.ordered_ledger
            if row.get("selected_for_promotion") is True
        ),
        None,
    )
    if type(rank) is not int:
        raise Exact100SuccessorReplacementV2Error(
            "wider rank lacks its selected promotion rank"
        )
    return rank


def _required_role(role: str) -> str:
    return "complaint" if role == "amended_complaint" else role


def _replace_candidate_rows(
    base: Sequence[Mapping[str, Any]],
    promoted: Sequence[Mapping[str, Any]],
    *,
    terminal_id: str,
    promoted_id: str,
) -> tuple[JsonRecord, ...]:
    if any(_candidate_id(row) != promoted_id for row in promoted):
        raise Exact100SuccessorReplacementV2Error(
            "promoted evidence contains another candidate"
        )
    return (
        *(dict(row) for row in base if _candidate_id(row) != terminal_id),
        *(dict(row) for row in promoted),
    )


def _require_materialized_evidence(
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
        raise Exact100SuccessorReplacementV2Error(
            f"{label} materialized evidence coverage differs"
        )
    if {candidate_id for candidate_id, _ in manifest_by_key} - allowed_candidate_ids:
        raise Exact100SuccessorReplacementV2Error(
            f"{label} materialized evidence contains an unselected candidate"
        )
    for key, document in manifest_by_key.items():
        clear = clearance_by_key[key]
        restricted = restriction_by_key[key]
        if (
            clear.get("status") != "cleared"
            or not _restriction_is_publicly_usable(restricted)
            or _raw_sha(clear, "sha256") != _raw_sha(document, "sha256")
            or clear.get("byte_count") != document.get("byte_count")
        ):
            raise Exact100SuccessorReplacementV2Error(
                f"{label} document is not cleared and public: {key[0]}/{key[1]}"
            )


def _restriction_is_publicly_usable(record: Mapping[str, Any]) -> bool:
    status = record.get("restriction_status")
    if status == "public":
        return True
    raw_evidence = record.get("restriction_evidence")
    if not isinstance(raw_evidence, (list, tuple)):
        return False
    evidence = cast(Sequence[object], raw_evidence)
    if status != "unknown" or not all(isinstance(value, str) for value in evidence):
        return False
    return _PUBLIC_UNKNOWN_RESTRICTION_EVIDENCE <= set(cast(Sequence[str], evidence))


def _require_clean_core_result(
    rows: Sequence[Mapping[str, Any]], *, promoted_id: str
) -> None:
    matches = [row for row in rows if _candidate_id(row) == promoted_id]
    if len(matches) != 1:
        raise Exact100SuccessorReplacementV2Error(
            "promoted candidate lacks one core-filter result"
        )
    row = matches[0]
    if (
        row.get("excluded") is not False
        or row.get("missing_operative_complaint") is not False
        or row.get("missing_core_roles") not in ([], ())
    ):
        raise Exact100SuccessorReplacementV2Error(
            "promoted candidate remains incomplete after semantic repair"
        )


def _require_unique_candidate_rows(
    rows: Sequence[Mapping[str, Any]], *, label: str
) -> None:
    ids = [_candidate_id(row) for row in rows]
    if len(ids) != len(set(ids)):
        raise Exact100SuccessorReplacementV2Error(f"{label} repeats a candidate")


def _require_candidate_coverage(
    rows: Sequence[Mapping[str, Any]], candidate_ids: set[str], *, label: str
) -> None:
    _require_unique_candidate_rows(rows, label=label)
    if {_candidate_id(row) for row in rows} != candidate_ids:
        raise Exact100SuccessorReplacementV2Error(
            f"{label} does not exactly cover the predecessor"
        )


def _unique_documents(
    rows: Sequence[Mapping[str, Any]], *, label: str
) -> dict[DocumentKey, Mapping[str, Any]]:
    result: dict[DocumentKey, Mapping[str, Any]] = {}
    for row in rows:
        key = (_candidate_id(row), _required_text(row, "source_document_id"))
        if key in result:
            raise Exact100SuccessorReplacementV2Error(f"{label} repeats a document")
        result[key] = row
    return result


def _rows_by_document(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        result.setdefault(_required_text(row, "source_document_id"), []).append(row)
    return {key: tuple(value) for key, value in result.items()}


def _document_description(role: str) -> str:
    return {
        "amended_complaint": "Verified First Amended Complaint",
        "motion_to_dismiss_memorandum": "Motion to Dismiss and Memorandum",
        "opposition": "Opposition to Motion to Dismiss",
        "reply": "Reply in Support of Motion to Dismiss",
        "decision": "Written MTD Disposition",
    }.get(role, role.replace("_", " ").title())


def _validated_commitments(values: Mapping[str, str]) -> dict[str, str]:
    if not values:
        raise Exact100SuccessorReplacementV2Error("v2 source commitments are required")
    result: dict[str, str] = {}
    for name, value in values.items():
        raw = value.removeprefix("sha256:")
        if (
            not name
            or len(raw) != 64
            or any(ch not in "0123456789abcdef" for ch in raw)
        ):
            raise Exact100SuccessorReplacementV2Error("v2 source commitment is invalid")
        result[name] = "sha256:" + raw
    return dict(sorted(result.items()))


def _candidate_id(row: Mapping[str, Any]) -> str:
    return _required_text(row, "candidate_id")


def _required_text(row: Mapping[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value:
        raise Exact100SuccessorReplacementV2Error(f"record lacks {field_name}")
    return value


def _raw_sha(row: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(row, field_name).removeprefix("sha256:")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise Exact100SuccessorReplacementV2Error(f"record has invalid {field_name}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementV2Error,
        error_message="v2 successor serialization failed",
    )


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(row)) for row in rows)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

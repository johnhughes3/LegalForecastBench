"""Pure deterministic wider-universe ranking for an exact-100 successor."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_SEMANTIC_REPAIR_V1,
    EXACT100_SUCCESSOR_WIDER_RANK_LEDGER_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes

JsonRecord = dict[str, Any]
LEDGER_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_WIDER_RANK_LEDGER_V1)
SEMANTIC_REPAIR_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_SEMANTIC_REPAIR_V1)
_COUNTS = (153, 100, 53)
_SHA256 = re.compile(r"(?:sha256:)?([0-9a-f]{64})")
_SEAL = object()
_EVIDENCE_FIELDS = (
    "case_relevance",
    "download_manifest",
    "disclosure_clearance",
    "restriction_evidence",
    "core_filter_results",
)
_REQUIRED_ROLES = (
    "complaint",
    "motion_to_dismiss_memorandum",
    "opposition",
    "decision",
)
_REPAIR_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "docket_entry_number",
        "original_document_role",
        "derived_document_role",
        "repair_kind",
        "source_sha256",
        "source_byte_count",
        "source_metadata_sha256",
        "evidence_cues",
    }
)


class Exact100SuccessorWiderRankError(ValueError):
    """Raised when wider-rank evidence does not reconcile exactly."""


@dataclass(frozen=True, slots=True)
class SelectedCandidateEvidence:
    """Exact materialized rows carried with the selected replacement."""

    selection_row: JsonRecord
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100SuccessorWiderRank:
    """Sealed result minted only after authenticated inputs reconcile."""

    ordered_ledger: tuple[JsonRecord, ...]
    selected_candidate_id: str
    selected_selection_row: JsonRecord
    selected_evidence: SelectedCandidateEvidence
    source_commitments: Mapping[str, str]
    _integrity_sha256: str = field(repr=False, compare=False)
    _verification_seal: object = field(repr=False, compare=False)


def require_verified_exact100_successor_wider_rank(
    value: VerifiedExact100SuccessorWiderRank,
) -> VerifiedExact100SuccessorWiderRank:
    """Reject forged, subclassed, or mutated capabilities."""

    if (
        type(value) is not VerifiedExact100SuccessorWiderRank
        or getattr(value, "_verification_seal", None) is not _SEAL
    ):
        raise Exact100SuccessorWiderRankError("wider-rank capability was not minted")
    if getattr(value, "_integrity_sha256", None) != _integrity(value):
        raise Exact100SuccessorWiderRankError("wider-rank capability changed")
    selected = [
        r for r in value.ordered_ledger if r.get("selected_for_promotion") is True
    ]
    if (
        len(value.ordered_ledger) != _COUNTS[2]
        or len(selected) != 1
        or selected[0].get("candidate_id") != value.selected_candidate_id
    ):
        raise Exact100SuccessorWiderRankError("wider-rank ledger is incomplete")
    return value


def _mint_verified_exact100_successor_wider_rank(  # pyright: ignore[reportUnusedFunction]
    *,
    final153_rows: Sequence[Mapping[str, Any]],
    exact100_rows: Sequence[Mapping[str, Any]],
    exclusion_rows: Sequence[Mapping[str, Any]],
    materialized_selection_rows: Sequence[Mapping[str, Any]],
    case_relevance_rows: Sequence[Mapping[str, Any]],
    download_manifest_rows: Sequence[Mapping[str, Any]],
    disclosure_rows: Sequence[Mapping[str, Any]],
    restriction_rows: Sequence[Mapping[str, Any]],
    core_filter_rows: Sequence[Mapping[str, Any]],
    identity_mapping_rows: Sequence[Mapping[str, Any]],
    semantic_repair_rows: Sequence[Mapping[str, Any]],
    source_commitments: Mapping[str, str],
) -> VerifiedExact100SuccessorWiderRank:
    """Mint from records already byte-authenticated by the integration layer."""

    commitments = _commitments(source_commitments)
    final_ids = _mapped_final_ids(final153_rows, identity_mapping_rows)
    selected = _unique(exact100_rows, "exact-100 selection")
    exclusions = _unique(exclusion_rows, "exclusion ledger")
    if (len(final_ids), len(selected), len(exclusions)) != _COUNTS:
        raise Exact100SuccessorWiderRankError(
            "expected exactly 153 final, 100 selected, and 53 nonselected candidates"
        )
    selected_ids, excluded_ids = set(selected), set(exclusions)
    if selected_ids & excluded_ids or set(final_ids) != selected_ids | excluded_ids:
        raise Exact100SuccessorWiderRankError("selected/nonselected partition mismatch")

    materialized = _unique(materialized_selection_rows, "materialized selection")
    if set(materialized) != excluded_ids:
        raise Exact100SuccessorWiderRankError(
            "materialized selection must cover all 53 nonselected candidates"
        )
    evidence = {
        "case_relevance": _group(case_relevance_rows),
        "download_manifest": _group(download_manifest_rows),
        "disclosure_clearance": _group(disclosure_rows),
        "restriction_evidence": _group(restriction_rows),
        "core_filter_results": _group(core_filter_rows),
    }
    for name, groups in evidence.items():
        if not set(groups) <= excluded_ids:
            raise Exact100SuccessorWiderRankError(
                f"{name} contains a candidate outside the wider partition"
            )
    repairs = _repairs(
        semantic_repair_rows, download_by_id=evidence["download_manifest"]
    )
    rows: dict[str, JsonRecord] = {}
    bundles: dict[str, dict[str, tuple[JsonRecord, ...]]] = {}
    for candidate_id in excluded_ids:
        bundles[candidate_id] = {
            name: tuple(dict(r) for r in groups.get(candidate_id, ()))
            for name, groups in evidence.items()
        }
        rows[candidate_id] = _derive_selection_row(
            base=materialized[candidate_id],
            exclusion=exclusions[candidate_id],
            evidence=bundles[candidate_id],
            repairs=repairs.get(candidate_id, {}),
        )

    ordered = sorted(excluded_ids, key=lambda cid: _rank_key(rows[cid]))
    eligible = [cid for cid in ordered if _eligible(rows[cid], bundles[cid])]
    if not eligible:
        raise Exact100SuccessorWiderRankError(
            "no fully eligible zero-cost complete candidate"
        )
    chosen = eligible[0]
    ledger: list[JsonRecord] = []
    for rank, candidate_id in enumerate(ordered, 1):
        missing, cost, folded, exact = _rank_key(rows[candidate_id])
        ledger.append(
            {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "rank": rank,
                "ranking_key": {
                    "missing_required_document_count": missing,
                    "projected_paid_cost_usd": f"{cost:.2f}",
                    "candidate_id_casefold": folded,
                    "candidate_id": exact,
                },
                "base_exclusion_row_sha256": _sha_record(exclusions[candidate_id]),
                "effective_selection_row_sha256": _sha_record(rows[candidate_id]),
                "semantic_repair_applied": bool(repairs.get(candidate_id)),
                "remaining_exclusion_reasons": list(
                    rows[candidate_id].get("exclusion_reasons", [])
                ),
                "evidence_row_counts": {
                    name: len(bundles[candidate_id][name]) for name in _EVIDENCE_FIELDS
                },
                "fully_eligible_zero_cost_complete": candidate_id in eligible,
                "selected_for_promotion": candidate_id == chosen,
            }
        )
    chosen_bundle = bundles[chosen]
    chosen_row = dict(rows[chosen])
    evidence_bundle = SelectedCandidateEvidence(
        selection_row=dict(chosen_row),
        case_relevance=chosen_bundle["case_relevance"],
        download_manifest=chosen_bundle["download_manifest"],
        disclosure_clearance=chosen_bundle["disclosure_clearance"],
        restriction_evidence=chosen_bundle["restriction_evidence"],
        core_filter_results=chosen_bundle["core_filter_results"],
    )
    value = object.__new__(VerifiedExact100SuccessorWiderRank)
    object.__setattr__(value, "ordered_ledger", tuple(ledger))
    object.__setattr__(value, "selected_candidate_id", chosen)
    object.__setattr__(value, "selected_selection_row", chosen_row)
    object.__setattr__(value, "selected_evidence", evidence_bundle)
    object.__setattr__(value, "source_commitments", commitments)
    object.__setattr__(value, "_verification_seal", _SEAL)
    object.__setattr__(value, "_integrity_sha256", _integrity(value))
    return require_verified_exact100_successor_wider_rank(value)


def _mapped_final_ids(
    final_rows: Sequence[Mapping[str, Any]], mappings: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    by_snapshot: dict[str, tuple[str, str]] = {}
    canonical: set[str] = set()
    for mapping in mappings:
        source = _required_str(mapping, "snapshot_candidate_id")
        target = _required_str(mapping, "canonical_candidate_id")
        digest = _digest(mapping, "snapshot_row_sha256")
        if source in by_snapshot or target in canonical:
            raise Exact100SuccessorWiderRankError("duplicate identity mapping")
        by_snapshot[source] = target, digest
        canonical.add(target)
    if len(by_snapshot) != len(final_rows):
        raise Exact100SuccessorWiderRankError(
            "identity mapping must cover every final row"
        )
    result: list[str] = []
    seen: set[str] = set()
    for row in final_rows:
        source = _candidate_id(row)
        if source in seen or source not in by_snapshot:
            raise Exact100SuccessorWiderRankError(
                "missing or duplicate mapped identity"
            )
        seen.add(source)
        target, digest = by_snapshot[source]
        if _sha_record(row) != digest:
            raise Exact100SuccessorWiderRankError("identity mapping row hash mismatch")
        result.append(target)
    if len(set(result)) != len(result):
        raise Exact100SuccessorWiderRankError("mapped identities are not unique")
    return tuple(result)


def _repairs(
    rows: Sequence[Mapping[str, Any]],
    *,
    download_by_id: Mapping[str, tuple[JsonRecord, ...]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    seen_documents: set[tuple[str, str]] = set()
    for row in rows:
        if sorted(row) != sorted(_REPAIR_FIELDS):
            raise Exact100SuccessorWiderRankError(
                "semantic repair fields are not closed"
            )
        if row.get("schema_version") != SEMANTIC_REPAIR_SCHEMA_VERSION:
            raise Exact100SuccessorWiderRankError("unsupported semantic repair schema")
        candidate_id = _candidate_id(row)
        source_document_id = _required_str(row, "source_document_id")
        key = candidate_id, source_document_id
        if key in seen_documents:
            raise Exact100SuccessorWiderRankError("duplicate semantic document repair")
        seen_documents.add(key)
        matches = [
            document
            for document in download_by_id.get(candidate_id, ())
            if document.get("source_document_id") == source_document_id
        ]
        if len(matches) != 1:
            raise Exact100SuccessorWiderRankError(
                "semantic repair source document is absent or duplicate"
            )
        document = matches[0]
        original = _required_str(row, "original_document_role")
        derived = _required_str(row, "derived_document_role")
        repair_kind = _required_str(row, "repair_kind")
        expected = {
            "embedded_operative_amended_complaint": "amended_complaint",
            "combined_mtd_memorandum": "motion_to_dismiss_memorandum",
        }.get(repair_kind)
        if expected != derived or document.get("document_role") != original:
            raise Exact100SuccessorWiderRankError("semantic repair role mismatch")
        if (
            _digest(row, "source_sha256") != _digest(document, "sha256")
            or row.get("source_byte_count") != document.get("byte_count")
            or _digest(row, "source_metadata_sha256") != _sha_record(document)
        ):
            raise Exact100SuccessorWiderRankError(
                "semantic repair source binding mismatch"
            )
        cues = row.get("evidence_cues")
        if not isinstance(cues, list) or not cues:
            raise Exact100SuccessorWiderRankError("semantic repair lacks evidence cues")
        result.setdefault(candidate_id, {})[source_document_id] = derived
    return result


def _derive_selection_row(
    *,
    base: Mapping[str, Any],
    exclusion: Mapping[str, Any],
    evidence: Mapping[str, tuple[JsonRecord, ...]],
    repairs: Mapping[str, str],
) -> JsonRecord:
    candidate_id = _candidate_id(base)
    clearance = _documents_by_id(evidence["disclosure_clearance"])
    restrictions = _documents_by_id(evidence["restriction_evidence"])
    roles: dict[str, list[JsonRecord]] = {role: [] for role in _REQUIRED_ROLES}
    for document in evidence["download_manifest"]:
        source_document_id = _required_str(document, "source_document_id")
        role = repairs.get(source_document_id, document.get("document_role"))
        if role == "amended_complaint":
            role = "complaint"
        if role in roles and _document_is_usable(
            document,
            clearance=clearance.get(source_document_id, ()),
            restrictions=restrictions.get(source_document_id, ()),
        ):
            roles[cast(str, role)].append(document)
    missing_roles = [role for role, documents in roles.items() if not documents]
    reasons = _exclusion_reasons(base, exclusion)
    if roles["complaint"]:
        reasons -= {"operative_complaint_not_found", "no_free_operative_complaint"}
    if roles["motion_to_dismiss_memorandum"]:
        reasons -= {"no_free_mtd_memorandum", "no_free_target_mtd_document"}
    result = dict(base)
    result.update(
        {
            "candidate_id": candidate_id,
            "missing_required_document_count": len(missing_roles),
            "projected_paid_cost_usd": (
                "0.00" if not missing_roles else _base_cost(base)
            ),
            "exclusion_reasons": sorted(reasons),
        }
    )
    return result


def _documents_by_id(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_required_str(row, "source_document_id"), []).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _document_is_usable(
    document: Mapping[str, Any],
    *,
    clearance: Sequence[Mapping[str, Any]],
    restrictions: Sequence[Mapping[str, Any]],
) -> bool:
    if document.get("free_or_purchased") != "free":
        return False
    digest = _digest(document, "sha256")
    byte_count = document.get("byte_count")
    return (
        len(clearance) == 1
        and clearance[0].get("status") == "cleared"
        and clearance[0].get("free_or_purchased") == "free"
        and _digest(clearance[0], "sha256") == digest
        and clearance[0].get("byte_count") == byte_count
        and len(restrictions) == 1
        and restrictions[0].get("restriction_status") == "public"
    )


def _exclusion_reasons(
    base: Mapping[str, Any], exclusion: Mapping[str, Any]
) -> set[str]:
    result: set[str] = set()
    base_reasons = base.get("exclusion_reasons")
    if isinstance(base_reasons, (list, tuple)):
        result.update(
            _string_items(cast(list[object] | tuple[object, ...], base_reasons))
        )
    for field_name in ("primary_exclusion_reason", "reason"):
        value = exclusion.get(field_name)
        if isinstance(value, str) and value:
            result.add(value)
    secondary = exclusion.get("secondary_exclusion_reasons")
    if isinstance(secondary, (list, tuple)):
        result.update(_string_items(cast(list[object] | tuple[object, ...], secondary)))
    return result


def _string_items(value: list[object] | tuple[object, ...]) -> tuple[str, ...]:
    return tuple(item for item in value if isinstance(item, str))


def _base_cost(row: Mapping[str, Any]) -> str:
    _, cost, _, _ = _rank_key(row)
    return f"{cost:.2f}"


def _rank_key(row: Mapping[str, Any]) -> tuple[int, Decimal, str, str]:
    candidate_id = _candidate_id(row)
    missing = row.get("missing_required_document_count")
    if not isinstance(missing, int) or isinstance(missing, bool) or missing < 0:
        raise Exact100SuccessorWiderRankError("invalid missing-document count")
    raw_cost = row.get("projected_paid_cost_usd")
    if not isinstance(raw_cost, (str, int)) or isinstance(raw_cost, bool):
        raise Exact100SuccessorWiderRankError("invalid projected paid cost")
    try:
        cost = Decimal(str(raw_cost))
    except InvalidOperation as exc:
        raise Exact100SuccessorWiderRankError("invalid projected paid cost") from exc
    if not cost.is_finite() or cost < 0:
        raise Exact100SuccessorWiderRankError("invalid projected paid cost")
    # This is the live disclosure_clearance.ranked_replacement tuple.
    return missing, cost, candidate_id.casefold(), candidate_id


def _eligible(
    row: Mapping[str, Any], evidence: Mapping[str, tuple[JsonRecord, ...]]
) -> bool:
    missing, cost, _, _ = _rank_key(row)
    return (
        missing == 0
        and cost == 0
        and row.get("exclusion_reasons") in (None, [], ())
        and all(evidence.get(name) for name in _EVIDENCE_FIELDS)
    )


def _unique(
    rows: Sequence[Mapping[str, Any]], label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        candidate_id = _candidate_id(row)
        if candidate_id in result:
            raise Exact100SuccessorWiderRankError(f"duplicate {label} candidate")
        result[candidate_id] = row
    return result


def _group(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[JsonRecord, ...]]:
    result: dict[str, list[JsonRecord]] = {}
    for row in rows:
        result.setdefault(_candidate_id(row), []).append(dict(row))
    return {candidate_id: tuple(group) for candidate_id, group in result.items()}


def _commitments(values: Mapping[str, str]) -> dict[str, str]:
    if not values:
        raise Exact100SuccessorWiderRankError("source commitments are required")
    result: dict[str, str] = {}
    for name, value in values.items():
        match = _SHA256.fullmatch(value)
        if not name or match is None:
            raise Exact100SuccessorWiderRankError("invalid source commitment")
        result[name] = match.group(1)
    return dict(sorted(result.items()))


def _integrity(value: VerifiedExact100SuccessorWiderRank) -> str:
    evidence = value.selected_evidence
    return hashlib.sha256(
        _canonical(
            {
                "ordered_ledger": list(value.ordered_ledger),
                "selected_candidate_id": value.selected_candidate_id,
                "selected_selection_row": value.selected_selection_row,
                "selected_evidence": {
                    "selection_row": evidence.selection_row,
                    **{
                        name: list(getattr(evidence, name)) for name in _EVIDENCE_FIELDS
                    },
                },
                "source_commitments": dict(value.source_commitments),
            }
        )
    ).hexdigest()


def _canonical(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorWiderRankError,
        error_message="wider-rank serialization failed",
    )


def _sha_record(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(dict(row))).hexdigest()


def _candidate_id(row: Mapping[str, Any]) -> str:
    return _required_str(row, "candidate_id")


def _required_str(row: Mapping[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise Exact100SuccessorWiderRankError(f"missing {field_name}")
    return value


def _digest(row: Mapping[str, Any], field_name: str) -> str:
    match = _SHA256.fullmatch(_required_str(row, field_name))
    if match is None:
        raise Exact100SuccessorWiderRankError(f"invalid {field_name}")
    return match.group(1)

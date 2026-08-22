"""Provider-free replacement of terminal cases in an authenticated exact 100."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_PROMOTION_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1,
    ZERO_COST_SUCCESSOR_CONFIG_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    VerifiedPostSelectionTerminalExclusions,
    require_verified_post_selection_terminal_exclusions,
)

JsonRecord = dict[str, Any]

CONFIG_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1)
STATE_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1)
PROMOTION_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_PROMOTION_V1)

_TARGET_COUNT = 100
_PREDECESSOR_SCHEMA_VERSION = str(ZERO_COST_SUCCESSOR_CONFIG_V1)
_VERIFICATION_SEAL = object()

# ``zero_cost_successor_config.v1`` is frozen.  Its full output surface, not
# merely the selection which this projector consumes, is the predecessor that
# an input replay must authenticate.
PREDECESSOR_OUTPUT_NAMES = frozenset(
    {
        "target-cohort-selection.jsonl",
        "case-relevance.jsonl",
        "document-downloads-merged.jsonl",
        "free-document-downloads.jsonl",
        "purchased-document-downloads.jsonl",
        "disclosure-clearance.jsonl",
        "restriction-evidence.jsonl",
        "core-filter-results.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-exclusions.jsonl",
        "target-cohort-ranked-reserve.jsonl",
    }
)


class Exact100SuccessorReplacementError(ValueError):
    """Raised when successor replacement evidence does not reconcile exactly."""


@dataclass(frozen=True, slots=True, init=False)
class VerifiedExact100Predecessor:
    """Exact predecessor surface minted after producer/materializer replay."""

    projection: JsonRecord
    projection_bytes: bytes
    selection: tuple[JsonRecord, ...]
    selection_bytes: bytes
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    all_output_bytes: Mapping[str, bytes]
    source_commitments: Mapping[str, str]
    _verification_seal: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True, init=False)
class VerifiedSuccessorPromotionPool:
    """Frozen-rank candidates with current complete, cleared public artifacts."""

    ranked_reserve: tuple[JsonRecord, ...]
    promotable_candidate_ids: tuple[str, ...]
    nonpromotable: tuple[JsonRecord, ...]
    selection_by_candidate: Mapping[str, JsonRecord]
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    producer_config_bytes: bytes
    producer_run_card_bytes: bytes
    producer_root_bytes: bytes
    source_commitments: Mapping[str, str]
    _verification_seal: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Exact100SuccessorReplacement:
    """Closed successor selection and standard materialization surface."""

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

    @property
    def state_bytes(self) -> bytes:
        return _canonical_bytes(self.state)


def project_exact100_successor_replacement(
    *,
    predecessor: VerifiedExact100Predecessor,
    terminal_exclusions: VerifiedPostSelectionTerminalExclusions,
    promotion_pool: VerifiedSuccessorPromotionPool,
) -> Exact100SuccessorReplacement:
    """Replace the terminal subset with the first replay-verified clean reserves."""

    require_verified_exact100_predecessor(predecessor)
    require_verified_post_selection_terminal_exclusions(terminal_exclusions)
    require_verified_successor_promotion_pool(promotion_pool)
    if terminal_exclusions.selection_sha256 != _sha(predecessor.selection_bytes):
        raise Exact100SuccessorReplacementError(
            "terminal exclusions bind a different predecessor selection"
        )
    terminal_ids = terminal_exclusions.candidate_ids
    terminal_set = set(terminal_ids)
    selected_ids = tuple(_candidate_id(row) for row in predecessor.selection)
    if not terminal_set <= set(selected_ids):
        raise Exact100SuccessorReplacementError(
            "terminal exclusions are outside the predecessor selection"
        )
    required_count = len(terminal_ids)
    promoted_ids = tuple(
        candidate_id
        for candidate_id in promotion_pool.promotable_candidate_ids
        if candidate_id not in set(selected_ids)
    )[:required_count]
    if len(promoted_ids) != required_count:
        raise Exact100SuccessorReplacementError(
            "insufficient replay-verified clean reserve candidates"
        )
    if set(promoted_ids) & (set(selected_ids) | terminal_set):
        raise Exact100SuccessorReplacementError(
            "promoted candidate overlaps the predecessor or terminal subset"
        )
    retained = tuple(
        dict(row)
        for row in predecessor.selection
        if _candidate_id(row) not in terminal_set
    )
    promoted_rows = tuple(
        dict(promotion_pool.selection_by_candidate[candidate_id])
        for candidate_id in promoted_ids
    )
    selection = (*retained, *promoted_rows)
    successor_ids = tuple(_candidate_id(row) for row in selection)
    if len(selection) != _TARGET_COUNT or len(set(successor_ids)) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementError(
            "successor selection is not exactly 100 unique candidates"
        )

    promotions = tuple(
        {
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "reserve_rank": _reserve_rank(
                promotion_pool.ranked_reserve, candidate_id=candidate_id
            ),
            "source_selection_row_sha256": _sha(
                _canonical_bytes(promotion_pool.selection_by_candidate[candidate_id])
            ),
        }
        for candidate_id in promoted_ids
    )
    case_relevance = _replace_candidate_rows(
        predecessor.case_relevance,
        promotion_pool.case_relevance,
        terminal_ids=terminal_set,
        promoted_ids=promoted_ids,
    )
    download_manifest = _replace_candidate_rows(
        predecessor.download_manifest,
        promotion_pool.download_manifest,
        terminal_ids=terminal_set,
        promoted_ids=promoted_ids,
    )
    disclosure_clearance = _replace_candidate_rows(
        predecessor.disclosure_clearance,
        promotion_pool.disclosure_clearance,
        terminal_ids=terminal_set,
        promoted_ids=promoted_ids,
    )
    restriction_evidence = _replace_candidate_rows(
        predecessor.restriction_evidence,
        promotion_pool.restriction_evidence,
        terminal_ids=terminal_set,
        promoted_ids=promoted_ids,
    )
    core_filter_results = _replace_candidate_rows(
        predecessor.core_filter_results,
        promotion_pool.core_filter_results,
        terminal_ids=terminal_set,
        promoted_ids=promoted_ids,
    )

    output_bytes = {
        "target-cohort-selection.jsonl": _jsonl_bytes(selection),
        "case-relevance.jsonl": _jsonl_bytes(case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(download_manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(disclosure_clearance),
        "restriction-evidence.jsonl": _jsonl_bytes(restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(core_filter_results),
        "successor-terminal-exclusions.jsonl": terminal_exclusions.records_bytes,
        "successor-promotions.jsonl": _jsonl_bytes(promotions),
    }
    config: JsonRecord = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "target_case_count": _TARGET_COUNT,
        "predecessor_schema_version": predecessor.projection["schema_version"],
        "terminal_exclusion_count": required_count,
        "promoted_candidate_ids": list(promoted_ids),
        "source_commitments": dict(
            sorted(
                {
                    **predecessor.source_commitments,
                    "terminal_exclusions": terminal_exclusions.commitment_sha256,
                    **promotion_pool.source_commitments,
                }.items()
            )
        ),
        "output_commitments": {
            name: _sha(payload) for name, payload in output_bytes.items()
        },
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    config_bytes = _canonical_bytes(config)
    state: JsonRecord = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "completed",
        "target_case_count": _TARGET_COUNT,
        "predecessor_case_count": len(predecessor.selection),
        "retained_case_count": len(retained),
        "terminal_exclusion_count": required_count,
        "promotion_count": len(promoted_ids),
        "selected_case_count": len(selection),
        "terminal_candidate_ids": list(terminal_ids),
        "promoted_candidate_ids": list(promoted_ids),
        "config_sha256": _sha(config_bytes),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    return Exact100SuccessorReplacement(
        selection=selection,
        case_relevance=case_relevance,
        download_manifest=download_manifest,
        disclosure_clearance=disclosure_clearance,
        restriction_evidence=restriction_evidence,
        core_filter_results=core_filter_results,
        terminal_exclusions=terminal_exclusions.records,
        promotions=promotions,
        config=config,
        state=state,
    )


def _mint_verified_exact100_predecessor(  # pyright: ignore[reportUnusedFunction]
    *,
    projection: Mapping[str, Any],
    projection_bytes: bytes,
    selection_bytes: bytes,
    case_relevance_bytes: bytes,
    download_manifest_bytes: bytes,
    disclosure_clearance_bytes: bytes,
    restriction_evidence_bytes: bytes,
    core_filter_results_bytes: bytes,
    all_output_bytes: Mapping[str, bytes],
) -> VerifiedExact100Predecessor:
    """Authenticate the predecessor surface from replayed producer bytes.

    This is intentionally module-private.  The CLI's authenticated zero-cost
    predecessor replay is the only production issuer.  Keeping the
    byte-to-capability step private prevents artifact callers from minting
    authority over arbitrary self-consistent bytes.
    """

    if _canonical_bytes(dict(projection)) != projection_bytes:
        raise Exact100SuccessorReplacementError(
            "predecessor projection differs from canonical supplied bytes"
        )
    if (
        projection.get("schema_version") != _PREDECESSOR_SCHEMA_VERSION
        or projection.get("target_case_count") != _TARGET_COUNT
        or projection.get("provider_activity_permitted") is not False
        or projection.get("paid_activity_permitted") is not False
        or projection.get("evaluation_authorized") is not False
        or projection.get("freeze_authorized") is not False
        or projection.get("dispatch_authorized") is not False
    ):
        raise Exact100SuccessorReplacementError(
            "predecessor is not the closed exact-100 successor contract"
        )
    raw_outputs = projection.get("output_commitments")
    if not isinstance(raw_outputs, Mapping):
        raise Exact100SuccessorReplacementError(
            "predecessor does not bind every configured output"
        )
    outputs = cast(Mapping[str, object], raw_outputs)
    if (
        frozenset(outputs) != PREDECESSOR_OUTPUT_NAMES
        or frozenset(all_output_bytes) != PREDECESSOR_OUTPUT_NAMES
        or any(
            outputs.get(name) != _sha(payload)
            for name, payload in all_output_bytes.items()
        )
        or all_output_bytes["target-cohort-selection.jsonl"] != selection_bytes
        or all_output_bytes["case-relevance.jsonl"] != case_relevance_bytes
        or all_output_bytes["document-downloads-merged.jsonl"]
        != download_manifest_bytes
        or all_output_bytes["disclosure-clearance.jsonl"] != disclosure_clearance_bytes
        or all_output_bytes["restriction-evidence.jsonl"] != restriction_evidence_bytes
        or all_output_bytes["core-filter-results.jsonl"] != core_filter_results_bytes
    ):
        raise Exact100SuccessorReplacementError(
            "predecessor does not bind every configured output"
        )
    selection = tuple(_jsonl_records(selection_bytes, "predecessor selection"))
    ids = tuple(_candidate_id(row) for row in selection)
    if len(ids) != _TARGET_COUNT or len(set(ids)) != _TARGET_COUNT:
        raise Exact100SuccessorReplacementError(
            "predecessor selection is not exactly 100 unique candidates"
        )
    artifact_bytes = {
        "case_relevance": case_relevance_bytes,
        "download_manifest": download_manifest_bytes,
        "disclosure_clearance": disclosure_clearance_bytes,
        "restriction_evidence": restriction_evidence_bytes,
        "core_filter_results": core_filter_results_bytes,
    }
    artifacts = {
        name: tuple(_jsonl_records(payload, f"predecessor {name}"))
        for name, payload in artifact_bytes.items()
    }
    _require_exact_predecessor_artifact_coverage(selection, **artifacts)
    value = object.__new__(VerifiedExact100Predecessor)
    for name, item in (
        ("projection", dict(projection)),
        ("projection_bytes", projection_bytes),
        ("selection", selection),
        ("selection_bytes", selection_bytes),
        *artifacts.items(),
        ("all_output_bytes", dict(all_output_bytes)),
        (
            "source_commitments",
            {
                "predecessor_projection": _sha(projection_bytes),
                "predecessor_selection": _sha(selection_bytes),
                **{
                    f"predecessor_{name}": _sha(payload)
                    for name, payload in artifact_bytes.items()
                },
            },
        ),
        ("_verification_seal", _VERIFICATION_SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


def _mint_verified_successor_promotion_pool(  # pyright: ignore[reportUnusedFunction]
    *,
    ranked_reserve_bytes: bytes,
    source_selection_bytes: bytes,
    case_relevance_bytes: bytes,
    download_manifest_bytes: bytes,
    disclosure_clearance_bytes: bytes,
    restriction_evidence_bytes: bytes,
    core_filter_results_bytes: bytes,
    producer_config_bytes: bytes,
    producer_run_card_bytes: bytes,
    producer_root_bytes: bytes,
) -> VerifiedSuccessorPromotionPool:
    """Authenticate the reserve order from replayed current-artifact bytes.

    This is intentionally module-private.  The public replay helper validates
    its producer config, completed run card, and immutable root before it can
    mint the sealed pool below.
    """

    reserve = tuple(_jsonl_records(ranked_reserve_bytes, "ranked reserve"))
    source_rows = _jsonl_records(source_selection_bytes, "reserve source selection")
    source = {_candidate_id(row): dict(row) for row in source_rows}
    if len(source) != len(source_rows):
        raise Exact100SuccessorReplacementError(
            "reserve source selection contains a duplicate candidate"
        )
    ranks: list[int] = []
    reserve_ids: list[str] = []
    for row in reserve:
        candidate_id = _candidate_id(row)
        rank = row.get("reserve_rank")
        if type(rank) is not int or rank <= 0:
            raise Exact100SuccessorReplacementError("reserve rank is invalid")
        ranks.append(rank)
        reserve_ids.append(candidate_id)
        if candidate_id not in source:
            raise Exact100SuccessorReplacementError(
                "reserve candidate is absent from authenticated source selection"
            )
    if ranks != list(range(1, len(reserve) + 1)) or len(set(reserve_ids)) != len(
        reserve_ids
    ):
        raise Exact100SuccessorReplacementError(
            "reserve order is not a unique contiguous frozen ranking"
        )
    artifact_bytes = {
        "case_relevance": case_relevance_bytes,
        "download_manifest": download_manifest_bytes,
        "disclosure_clearance": disclosure_clearance_bytes,
        "restriction_evidence": restriction_evidence_bytes,
        "core_filter_results": core_filter_results_bytes,
    }
    artifacts = {
        name: tuple(_jsonl_records(payload, f"reserve {name}"))
        for name, payload in artifact_bytes.items()
    }
    promotable: list[str] = []
    nonpromotable: list[JsonRecord] = []
    for candidate_id in reserve_ids:
        reason = _nonpromotable_reason(
            candidate_id, selection=source[candidate_id], **artifacts
        )
        if reason is None:
            promotable.append(candidate_id)
        else:
            nonpromotable.append(
                {
                    "candidate_id": candidate_id,
                    "reserve_rank": _reserve_rank(reserve, candidate_id=candidate_id),
                    "reason": reason,
                }
            )
    value = object.__new__(VerifiedSuccessorPromotionPool)
    for name, item in (
        ("ranked_reserve", reserve),
        ("promotable_candidate_ids", tuple(promotable)),
        ("nonpromotable", tuple(nonpromotable)),
        ("selection_by_candidate", source),
        ("case_relevance", artifacts["case_relevance"]),
        ("download_manifest", artifacts["download_manifest"]),
        ("disclosure_clearance", artifacts["disclosure_clearance"]),
        ("restriction_evidence", artifacts["restriction_evidence"]),
        ("core_filter_results", artifacts["core_filter_results"]),
        ("producer_config_bytes", producer_config_bytes),
        ("producer_run_card_bytes", producer_run_card_bytes),
        ("producer_root_bytes", producer_root_bytes),
        (
            "source_commitments",
            {
                "reserve_ranked_reserve": _sha(ranked_reserve_bytes),
                "reserve_source_selection": _sha(source_selection_bytes),
                **{
                    f"reserve_{name}": _sha(payload)
                    for name, payload in artifact_bytes.items()
                },
                "reserve_producer_config": _sha(producer_config_bytes),
                "reserve_producer_run_card": _sha(producer_run_card_bytes),
                "reserve_producer_root": _sha(producer_root_bytes),
            },
        ),
        ("_verification_seal", _VERIFICATION_SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


def verify_exact100_predecessor(**_unattested: Any) -> VerifiedExact100Predecessor:
    """Refuse the former raw-byte issuer; authenticated CLI replay is required."""

    raise Exact100SuccessorReplacementError(
        "direct predecessor verification is disabled; replay the authenticated "
        "zero-cost predecessor"
    )


def verify_successor_promotion_pool(
    **_unattested: Any,
) -> VerifiedSuccessorPromotionPool:
    """Refuse the former raw-byte issuer; see ``verify_exact100_predecessor``."""

    raise Exact100SuccessorReplacementError(
        "direct promotion verification is disabled; derive the pool from the "
        "authenticated original target projection"
    )


def require_verified_exact100_predecessor(
    predecessor: VerifiedExact100Predecessor,
) -> None:
    if (
        type(predecessor) is not VerifiedExact100Predecessor
        or getattr(predecessor, "_verification_seal", None) is not _VERIFICATION_SEAL
        or predecessor.selection_bytes != _jsonl_bytes(predecessor.selection)
        or _canonical_bytes(predecessor.projection) != predecessor.projection_bytes
        or frozenset(predecessor.all_output_bytes) != PREDECESSOR_OUTPUT_NAMES
        or predecessor.projection.get("output_commitments")
        != {
            name: _sha(payload)
            for name, payload in predecessor.all_output_bytes.items()
        }
        or predecessor.all_output_bytes["target-cohort-selection.jsonl"]
        != predecessor.selection_bytes
        or predecessor.all_output_bytes["case-relevance.jsonl"]
        != _jsonl_bytes(predecessor.case_relevance)
        or predecessor.all_output_bytes["document-downloads-merged.jsonl"]
        != _jsonl_bytes(predecessor.download_manifest)
        or predecessor.all_output_bytes["disclosure-clearance.jsonl"]
        != _jsonl_bytes(predecessor.disclosure_clearance)
        or predecessor.all_output_bytes["restriction-evidence.jsonl"]
        != _jsonl_bytes(predecessor.restriction_evidence)
        or predecessor.all_output_bytes["core-filter-results.jsonl"]
        != _jsonl_bytes(predecessor.core_filter_results)
        or predecessor.source_commitments
        != {
            "predecessor_projection": _sha(predecessor.projection_bytes),
            "predecessor_selection": _sha(predecessor.selection_bytes),
            "predecessor_case_relevance": _sha(
                _jsonl_bytes(predecessor.case_relevance)
            ),
            "predecessor_download_manifest": _sha(
                _jsonl_bytes(predecessor.download_manifest)
            ),
            "predecessor_disclosure_clearance": _sha(
                _jsonl_bytes(predecessor.disclosure_clearance)
            ),
            "predecessor_restriction_evidence": _sha(
                _jsonl_bytes(predecessor.restriction_evidence)
            ),
            "predecessor_core_filter_results": _sha(
                _jsonl_bytes(predecessor.core_filter_results)
            ),
        }
    ):
        raise Exact100SuccessorReplacementError(
            "predecessor was not produced by exact producer replay"
        )
    _require_exact_predecessor_artifact_coverage(
        predecessor.selection,
        case_relevance=predecessor.case_relevance,
        download_manifest=predecessor.download_manifest,
        disclosure_clearance=predecessor.disclosure_clearance,
        restriction_evidence=predecessor.restriction_evidence,
        core_filter_results=predecessor.core_filter_results,
    )


def require_verified_successor_promotion_pool(
    promotion_pool: VerifiedSuccessorPromotionPool,
) -> None:
    if (
        type(promotion_pool) is not VerifiedSuccessorPromotionPool
        or getattr(promotion_pool, "_verification_seal", None) is not _VERIFICATION_SEAL
    ):
        raise Exact100SuccessorReplacementError(
            "promotion pool was not produced by authenticated replay"
        )
    expected: list[str] = []
    for row in promotion_pool.ranked_reserve:
        candidate_id = _candidate_id(row)
        selection = promotion_pool.selection_by_candidate.get(candidate_id)
        if not isinstance(selection, Mapping):
            raise Exact100SuccessorReplacementError(
                "reserve candidate is absent from authenticated source selection"
            )
        reason = _nonpromotable_reason(
            candidate_id,
            selection=selection,
            case_relevance=promotion_pool.case_relevance,
            download_manifest=promotion_pool.download_manifest,
            disclosure_clearance=promotion_pool.disclosure_clearance,
            restriction_evidence=promotion_pool.restriction_evidence,
            core_filter_results=promotion_pool.core_filter_results,
        )
        if reason is None:
            expected.append(candidate_id)
    if tuple(expected) != promotion_pool.promotable_candidate_ids:
        raise Exact100SuccessorReplacementError(
            "replay-verified promotion eligibility changed"
        )
    expected_commitments = {
        "reserve_ranked_reserve": _sha(_jsonl_bytes(promotion_pool.ranked_reserve)),
        "reserve_source_selection": _sha(
            _jsonl_bytes(tuple(promotion_pool.selection_by_candidate.values()))
        ),
        "reserve_case_relevance": _sha(_jsonl_bytes(promotion_pool.case_relevance)),
        "reserve_download_manifest": _sha(
            _jsonl_bytes(promotion_pool.download_manifest)
        ),
        "reserve_disclosure_clearance": _sha(
            _jsonl_bytes(promotion_pool.disclosure_clearance)
        ),
        "reserve_restriction_evidence": _sha(
            _jsonl_bytes(promotion_pool.restriction_evidence)
        ),
        "reserve_core_filter_results": _sha(
            _jsonl_bytes(promotion_pool.core_filter_results)
        ),
        "reserve_producer_config": _sha(promotion_pool.producer_config_bytes),
        "reserve_producer_run_card": _sha(promotion_pool.producer_run_card_bytes),
        "reserve_producer_root": _sha(promotion_pool.producer_root_bytes),
    }
    if set(promotion_pool.source_commitments) != set(expected_commitments) or any(
        promotion_pool.source_commitments.get(name) != digest
        for name, digest in expected_commitments.items()
    ):
        raise Exact100SuccessorReplacementError(
            "promotion pool artifacts changed after authenticated replay"
        )


def _require_exact_predecessor_artifact_coverage(
    selection: Sequence[Mapping[str, Any]],
    *,
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    disclosure_clearance: Sequence[Mapping[str, Any]],
    restriction_evidence: Sequence[Mapping[str, Any]],
    core_filter_results: Sequence[Mapping[str, Any]],
) -> None:
    """Require exact selected-candidate/document coverage on consumed evidence.

    The zero-cost predecessor may keep unacquired selected documents as
    authenticated paid-recovery gaps (``requires_paid_recovery is True`` and
    ``availability_status == "unavailable"``). Those identities must remain on
    selection and case relevance, but they are absent from the pre-recovery
    download manifest, clearance, and restriction surfaces. Acquired documents
    still require exact one-row coverage on those three artifacts.
    """

    selected_by_candidate = {_candidate_id(row): row for row in selection}
    selected_ids = set(selected_by_candidate)
    if len(selected_by_candidate) != len(selection):
        raise Exact100SuccessorReplacementError(
            "predecessor selection is not exactly unique candidates"
        )
    _require_exact_candidate_coverage(
        case_relevance, selected_ids, label="case relevance"
    )
    _require_exact_candidate_coverage(
        core_filter_results, selected_ids, label="core filter results"
    )
    for label, records in (
        ("download manifest", download_manifest),
        ("disclosure clearance", disclosure_clearance),
        ("restriction evidence", restriction_evidence),
    ):
        if not {_candidate_id(row) for row in records} <= selected_ids:
            raise Exact100SuccessorReplacementError(
                f"predecessor {label} includes an unselected candidate"
            )
    for candidate_id, selection_row in selected_by_candidate.items():
        document_ids = _document_ids_from_selection(selection_row, "selection")
        acquired_ids = document_ids - _paid_recovery_gap_ids(selection_row, "selection")
        relevance_rows = _candidate_rows(case_relevance, candidate_id)
        if (
            _document_ids_from_selection(relevance_rows[0], "case relevance")
            != document_ids
        ):
            raise Exact100SuccessorReplacementError(
                "predecessor case relevance document coverage is incomplete"
            )
        for label, records in (
            ("download manifest", download_manifest),
            ("disclosure clearance", disclosure_clearance),
            ("restriction evidence", restriction_evidence),
        ):
            if not _has_exact_document_coverage(
                _candidate_rows(records, candidate_id), acquired_ids
            ):
                raise Exact100SuccessorReplacementError(
                    f"predecessor {label} document coverage is incomplete"
                )


def _require_exact_candidate_coverage(
    rows: Sequence[Mapping[str, Any]], candidate_ids: set[str], *, label: str
) -> None:
    observed_ids = {_candidate_id(row) for row in rows}
    if len(rows) != len(candidate_ids) or observed_ids != candidate_ids:
        raise Exact100SuccessorReplacementError(
            f"predecessor {label} does not exactly cover selected candidates"
        )


def _document_ids_from_selection(record: Mapping[str, Any], label: str) -> set[str]:
    documents = record.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise Exact100SuccessorReplacementError(
            f"predecessor {label} documents are invalid"
        )
    document_sequence = cast(Sequence[object], documents)
    document_ids: set[str] = set()
    for document in document_sequence:
        if not isinstance(document, Mapping):
            raise Exact100SuccessorReplacementError(
                f"predecessor {label} documents are invalid"
            )
        document_ids.add(
            _required_text(cast(Mapping[str, object], document), "source_document_id")
        )
    if not document_ids or len(document_ids) != len(document_sequence):
        raise Exact100SuccessorReplacementError(
            f"predecessor {label} documents are invalid"
        )
    return document_ids


def _paid_recovery_gap_ids(record: Mapping[str, Any], label: str) -> set[str]:
    """Return selected document ids that are authenticated unpaid recovery gaps."""

    documents = record.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise Exact100SuccessorReplacementError(
            f"predecessor {label} documents are invalid"
        )
    gaps: set[str] = set()
    for document in cast(Sequence[object], documents):
        if not isinstance(document, Mapping):
            raise Exact100SuccessorReplacementError(
                f"predecessor {label} documents are invalid"
            )
        typed = cast(Mapping[str, object], document)
        requires_paid = typed.get("requires_paid_recovery")
        availability = typed.get("availability_status")
        is_gap = requires_paid is True and availability == "unavailable"
        if (requires_paid is True or availability == "unavailable") is not is_gap:
            raise Exact100SuccessorReplacementError(
                "predecessor selection has inconsistent paid-recovery gap markers"
            )
        if is_gap:
            gaps.add(_required_text(typed, "source_document_id"))
    return gaps


def _nonpromotable_reason(
    candidate_id: str,
    *,
    selection: Mapping[str, Any],
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    disclosure_clearance: Sequence[Mapping[str, Any]],
    restriction_evidence: Sequence[Mapping[str, Any]],
    core_filter_results: Sequence[Mapping[str, Any]],
) -> str | None:
    documents = selection.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        return "selection_documents_missing"
    document_sequence = cast(Sequence[object], documents)
    document_ids = {
        _required_text(cast(Mapping[str, object], document), "source_document_id")
        for document in document_sequence
        if isinstance(document, Mapping)
    }
    if not document_ids or len(document_ids) != len(document_sequence):
        return "selection_documents_invalid"
    relevance = _candidate_rows(case_relevance, candidate_id)
    if len(relevance) != 1:
        return "case_relevance_incomplete"
    try:
        relevance_document_ids = _document_ids_from_selection(
            relevance[0], "case relevance"
        )
    except Exact100SuccessorReplacementError:
        return "case_relevance_incomplete"
    if relevance_document_ids != document_ids:
        return "case_relevance_incomplete"
    manifest = _candidate_rows(download_manifest, candidate_id)
    clearance = _candidate_rows(disclosure_clearance, candidate_id)
    restrictions = _candidate_rows(restriction_evidence, candidate_id)
    core = _candidate_rows(core_filter_results, candidate_id)
    if not _has_exact_document_coverage(manifest, document_ids):
        return "download_manifest_incomplete"
    if any(_nonzero_cost_or_unavailable_manifest_row(row) for row in manifest):
        return "nonzero_cost_or_unavailable_document"
    if not _has_exact_document_coverage(clearance, document_ids) or any(
        row.get("status") != "cleared" for row in clearance
    ):
        return "disclosure_clearance_incomplete"
    if not _has_exact_document_coverage(restrictions, document_ids) or any(
        row.get("restriction_status") not in {"public", "redacted"}
        or bool(row.get("restriction_markers"))
        for row in restrictions
    ):
        return "restriction_evidence_incomplete"
    if len(core) != 1 or any(_core_documents_incomplete(row) for row in core):
        return "core_documents_incomplete"
    return None


def _has_exact_document_coverage(
    rows: Sequence[Mapping[str, Any]], document_ids: set[str]
) -> bool:
    """Require exactly one artifact row for every selected document."""

    return len(rows) == len(document_ids) and _document_ids(rows) == document_ids


def _nonzero_cost_or_unavailable_manifest_row(row: Mapping[str, Any]) -> bool:
    """True when a manifest row is purchased, unpaid, or explicitly unavailable."""

    if row.get("free_or_purchased") == "purchased":
        return True
    if row.get("requires_paid_recovery") is True:
        return True
    if row.get("free_or_purchased") == "free":
        return row.get("availability_status") not in {None, "available"}
    return row.get("availability_status") != "available"


def _core_documents_incomplete(row: Mapping[str, Any]) -> bool:
    """True when core-filter evidence does not prove complete core documents.

    Hand-built fixtures stamp ``core_documents_complete``. Live
    ``filter_core_documents`` records instead stamp ``core_missing_documents``
    and ``excluded``.
    """

    complete = row.get("core_documents_complete")
    if complete is True:
        return row.get("missing_core_document_count", 0) != 0
    if complete is False:
        return True
    if "core_missing_documents" in row or "purchase_document_ids" in row:
        return (
            bool(row.get("core_missing_documents"))
            or row.get("excluded") is True
            or row.get("missing_operative_complaint") is True
        )
    return True


def _replace_candidate_rows(
    predecessor: Sequence[Mapping[str, Any]],
    pool: Sequence[Mapping[str, Any]],
    *,
    terminal_ids: set[str],
    promoted_ids: Sequence[str],
) -> tuple[JsonRecord, ...]:
    retained = [
        dict(row) for row in predecessor if _candidate_id(row) not in terminal_ids
    ]
    promoted_by_candidate: dict[str, list[JsonRecord]] = {
        candidate_id: [] for candidate_id in promoted_ids
    }
    for row in pool:
        candidate_id = _candidate_id(row)
        if candidate_id in promoted_by_candidate:
            promoted_by_candidate[candidate_id].append(dict(row))
    if len(promoted_by_candidate) != len(promoted_ids) or any(
        not rows for rows in promoted_by_candidate.values()
    ):
        raise Exact100SuccessorReplacementError(
            "promoted candidate artifacts are incomplete"
        )
    return tuple(
        (
            *retained,
            *(
                row
                for candidate_id in promoted_ids
                for row in promoted_by_candidate[candidate_id]
            ),
        )
    )


def _candidate_rows(
    records: Sequence[Mapping[str, Any]], candidate_id: str
) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in records if _candidate_id(row) == candidate_id)


def _document_ids(records: Sequence[Mapping[str, Any]]) -> set[str]:
    return {_required_text(row, "source_document_id") for row in records}


def _reserve_rank(
    ranked_reserve: Sequence[Mapping[str, Any]], *, candidate_id: str
) -> int:
    matches = [
        row.get("reserve_rank")
        for row in ranked_reserve
        if _candidate_id(row) == candidate_id
    ]
    if len(matches) != 1 or type(matches[0]) is not int:
        raise Exact100SuccessorReplacementError("reserve candidate rank is ambiguous")
    return matches[0]


def _candidate_id(record: Mapping[str, Any]) -> str:
    return _required_text(record, "candidate_id")


def _required_text(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise Exact100SuccessorReplacementError(f"record lacks required {field_name}")
    return value.strip()


def _jsonl_records(payload: bytes, label: str) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        try:
            record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is not an object"
            )
        records.append(cast(JsonRecord, record))
    if _jsonl_bytes(records) != payload:
        raise Exact100SuccessorReplacementError(f"{label} is not canonical JSONL")
    return records


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementError,
        error_message="successor replacement serialization failed",
    )


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical_bytes(dict(record)) for record in records)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

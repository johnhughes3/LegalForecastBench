"""Provider-free reserve extension for an authenticated exact-100 successor.

The planner is deliberately pure: callers supply already-read artifact bytes and
the replay-authenticated exact successor.  It neither reads paths nor contacts a
provider, and every output explicitly denies paid and downstream authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)

JsonRecord = dict[str, Any]

SUMMARY_SCHEMA_VERSION = "legalforecast.exact100_reserve_extension.v1"
RESERVE_SCHEMA_VERSION = "legalforecast.exact100_extended_reserve.v1"
EXCLUSION_SCHEMA_VERSION = "legalforecast.exact100_reserve_exclusion.v1"
FREE_REFRESH_SCHEMA_VERSION = "legalforecast.exact100_free_refresh_request.v1"
COST_SCHEMA_VERSION = "legalforecast.exact100_reserve_cost_plan.v1"

_CLEARANCE_RUN_CARD_SCHEMA = "legalforecast.provenance_model_clearance_run_card.v1"
_CLEARANCE_RUN_CARD_STAGE = "finalize-provenance-quarantine"
_QUARANTINE_RUN_CARD_SCHEMA = "legalforecast.disclosure_quarantine_run_card.v1"
_QUARANTINE_RUN_CARD_STAGE = "finalize-disclosure-quarantine"
_EXACT_SUCCESSOR_SCHEMA = "legalforecast.zero_cost_successor_config.v1"
_ORIGINAL_PROJECTION_SCHEMA = "legalforecast.target_cohort_projection.v1"
_FRONTIER_SCHEMA = "legalforecast.target_cohort_candidate_frontier.v1"
_ORIGINAL_RESERVE_SCHEMA = "legalforecast.target_cohort_ranked_reserve.v1"
_TARGET_COUNT = 100
_SOURCE_COUNT = 115
_ORIGINAL_RESERVE_COUNT = 5
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_RANKING_ATTRIBUTES = (
    "missing_core_document_count",
    "estimated_cost_usd",
    "candidate_id",
)
_FRONTIER_SOURCE_COMMITMENTS = frozenset(
    {
        "snapshot_manifest_sha256",
        "preparation_config_sha256",
        "preparation_summary_sha256",
        "preparation_success_run_card_sha256",
        "reconciled_selection_sha256",
        "case_relevance_sha256",
        "download_manifest_sha256",
        "core_filter_results_sha256",
        "provisional_budget_plan_sha256",
        "restriction_evidence_sha256",
        "disclosure_review_requests_sha256",
    }
)
_FRONTIER_CARD_SOURCE_COMMITMENTS = frozenset(
    {
        "preparation_summary",
        "preparation_config",
        "snapshot_manifest",
        "preparation_success_run_card",
    }
)


class Exact100ReserveExtensionError(ValueError):
    """Raised when reserve capacity cannot be derived from authenticated inputs."""


@dataclass(frozen=True, slots=True)
class Exact100ReserveExtension:
    """Closed provider-free reserve extension artifacts."""

    selected_cohort_bytes: bytes
    ranked_reserve: tuple[JsonRecord, ...]
    exclusions: tuple[JsonRecord, ...]
    cost_plan: JsonRecord
    free_refresh_inputs: tuple[JsonRecord, ...]
    summary: JsonRecord

    @property
    def ranked_reserve_bytes(self) -> bytes:
        return _jsonl_bytes(self.ranked_reserve)

    @property
    def exclusions_bytes(self) -> bytes:
        return _jsonl_bytes(self.exclusions)

    @property
    def cost_plan_bytes(self) -> bytes:
        return _canonical_bytes(self.cost_plan)

    @property
    def free_refresh_inputs_bytes(self) -> bytes:
        return _jsonl_bytes(self.free_refresh_inputs)

    @property
    def summary_bytes(self) -> bytes:
        return _canonical_bytes(self.summary)


def extension_summary_digest(summary: Mapping[str, object]) -> str:
    """Return the canonical `extension_sha256` preimage digest for *summary*.

    The digest is self-excluded: it commits every summary field except
    `extension_sha256` itself, because that field cannot contain its own
    digest.  A consumer reading a persisted summary artifact must therefore
    drop `extension_sha256` before rehashing, which this helper does, rather
    than hashing the artifact bytes directly.
    """

    preimage = {
        key: value for key, value in summary.items() if key != "extension_sha256"
    }
    return _sha(original=_canonical_bytes(preimage))


def verify_extension_summary(summary: Mapping[str, object]) -> None:
    """Raise unless *summary* carries its own correct self-excluded digest."""

    recorded = summary.get("extension_sha256")
    expected = extension_summary_digest(summary)
    if recorded != expected:
        raise Exact100ReserveExtensionError(
            "extension summary digest does not match its self-excluded preimage"
        )


def extend_exact100_reserve(
    *,
    authenticated_exact_successor: Mapping[str, object],
    exact_successor_projection: Mapping[str, object],
    exact_successor_projection_bytes: bytes,
    exact_selection_bytes: bytes,
    authenticated_full_frontier: Mapping[str, object],
    full_frontier: Mapping[str, object],
    full_frontier_bytes: bytes,
    frontier_run_card: Mapping[str, object],
    frontier_run_card_bytes: bytes,
    source_pool_bytes: bytes,
    original_projection: Mapping[str, object],
    original_projection_bytes: bytes,
    original_selection_bytes: bytes,
    original_reserve_bytes: bytes,
    original_exclusions_bytes: bytes,
    final_clearance_bytes: bytes,
    final_clearance_run_card: Mapping[str, object],
    final_clearance_run_card_bytes: bytes,
    current_quarantine_bytes: bytes,
    authenticated_current_quarantine_run_card: Mapping[str, object],
    current_quarantine_run_card: Mapping[str, object],
    current_quarantine_run_card_bytes: bytes,
    required_replacement_count: int,
) -> Exact100ReserveExtension:
    """Derive additional reserve capacity without provider or paid authority.

    Candidate IDs are intentionally not an input.  The result follows only from
    the authenticated full frontier, clearance, current quarantine, and frozen
    selection/reserve state.
    """

    if required_replacement_count < 1:
        raise Exact100ReserveExtensionError(
            "required_replacement_count must be positive"
        )
    # Authenticate the mapping against the caller's artifact bytes.  Deriving
    # the payload from the mapping itself would compare a value with a
    # serialization of that same value, which can never fail.
    _verify_object_bytes(
        exact_successor_projection,
        exact_successor_projection_bytes,
        label="exact successor projection",
    )
    if dict(authenticated_exact_successor) != dict(exact_successor_projection):
        raise Exact100ReserveExtensionError(
            "exact successor replay differs from supplied projection"
        )
    exact_ids = _verify_exact_successor(
        exact_successor_projection, selection_bytes=exact_selection_bytes
    )

    _verify_object_bytes(full_frontier, full_frontier_bytes, label="full frontier")
    if dict(authenticated_full_frontier) != dict(full_frontier):
        raise Exact100ReserveExtensionError(
            "full frontier replay differs from supplied artifact"
        )
    frontier_rows, frontier_policy = _verify_frontier(
        full_frontier,
        frontier_bytes=full_frontier_bytes,
        run_card=frontier_run_card,
        run_card_bytes=frontier_run_card_bytes,
        source_pool_bytes=source_pool_bytes,
    )
    source_rows = _jsonl_records(source_pool_bytes, "source pool")
    source_by_id = _candidate_index(source_rows, "source pool")
    if set(source_by_id) != {row["candidate_id"] for row in frontier_rows}:
        raise Exact100ReserveExtensionError(
            "full frontier and source pool candidate sets differ"
        )

    _verify_object_bytes(
        original_projection,
        original_projection_bytes,
        label="original projection",
    )
    original_reserve = _verify_original_projection(
        original_projection,
        projection_bytes=original_projection_bytes,
        exact_successor_projection=exact_successor_projection,
        selection_bytes=original_selection_bytes,
        reserve_bytes=original_reserve_bytes,
        exclusions_bytes=original_exclusions_bytes,
        source_pool_bytes=source_pool_bytes,
        frontier_by_id={cast(str, row["candidate_id"]): row for row in frontier_rows},
    )

    final_clearance = _verify_clearance_authority(
        clearance_bytes=final_clearance_bytes,
        run_card=final_clearance_run_card,
        run_card_bytes=final_clearance_run_card_bytes,
        commitment_name="disclosure_clearance",
        label="clearance",
        allowed_candidate_ids=set(source_by_id),
        run_card_schema=_CLEARANCE_RUN_CARD_SCHEMA,
        run_card_stage=_CLEARANCE_RUN_CARD_STAGE,
    )
    exact_sources = _mapping(
        exact_successor_projection.get("source_commitments"),
        "exact successor sources",
    )
    if exact_sources.get("disclosure_clearance") != _sha(
        original=final_clearance_bytes
    ) or exact_sources.get("disclosure_clearance_run_card") != _sha(
        original=final_clearance_run_card_bytes
    ):
        raise Exact100ReserveExtensionError(
            "exact successor does not bind final clearance authority"
        )
    final_quarantined = {
        candidate_id
        for candidate_id, records in _records_by_candidate(final_clearance).items()
        if any(record.get("status") != "cleared" for record in records)
    }
    cleared_candidate_ids = {
        candidate_id
        for candidate_id, records in _records_by_candidate(final_clearance).items()
        if records and all(record.get("status") == "cleared" for record in records)
    }
    current_quarantine = _verify_clearance_authority(
        clearance_bytes=current_quarantine_bytes,
        run_card=current_quarantine_run_card,
        run_card_bytes=current_quarantine_run_card_bytes,
        commitment_name="disclosure_quarantine",
        label="current quarantine",
        allowed_candidate_ids=set(exact_ids),
        run_card_schema=_QUARANTINE_RUN_CARD_SCHEMA,
        run_card_stage=_QUARANTINE_RUN_CARD_STAGE,
        require_status=False,
    )
    if dict(authenticated_current_quarantine_run_card) != dict(
        current_quarantine_run_card
    ):
        raise Exact100ReserveExtensionError(
            "current quarantine replay differs from supplied run card"
        )
    current_quarantined = set(_records_by_candidate(current_quarantine))
    if len(current_quarantined) != required_replacement_count:
        raise Exact100ReserveExtensionError(
            "current quarantine count differs from required replacement count"
        )

    original_reserve_ids = set(original_reserve)
    eligible_rows: list[JsonRecord] = []
    exclusion_reasons: dict[str, str] = {}
    for frontier_row in frontier_rows:
        candidate_id = cast(str, frontier_row["candidate_id"])
        if candidate_id in exact_ids:
            exclusion_reasons[candidate_id] = "already_selected"
            continue
        if candidate_id in final_quarantined:
            exclusion_reasons[candidate_id] = "final_disclosure_quarantined"
            continue
        raw_reasons = cast(Sequence[object], frontier_row["exclusion_reasons"])
        if raw_reasons:
            exclusion_reasons[candidate_id] = "frozen_frontier_excluded"
            continue
        is_unused_original_reserve = candidate_id in original_reserve_ids
        is_later_cleared_absent = candidate_id in cleared_candidate_ids
        if not is_unused_original_reserve and not is_later_cleared_absent:
            exclusion_reasons[candidate_id] = "authenticated_clearance_absent"
            continue
        eligible_rows.append(frontier_row)

    eligible_rows.sort(key=_ranking_key)
    if len(eligible_rows) < required_replacement_count:
        raise Exact100ReserveExtensionError(
            "insufficient authenticated reserve capacity for current quarantine"
        )
    ranked_reserve = tuple(
        _extended_reserve_record(
            row,
            source_row=source_by_id[cast(str, row["candidate_id"])],
            reserve_rank=reserve_rank,
            origin=(
                "unused_original_ranked_reserve"
                if row["candidate_id"] in original_reserve_ids
                else "later_authenticated_clearance"
            ),
        )
        for reserve_rank, row in enumerate(eligible_rows, start=1)
    )
    exclusions = tuple(
        {
            "schema_version": EXCLUSION_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "reason": exclusion_reasons[candidate_id],
            "source_frontier_rank": _frontier_rank_by_id(frontier_rows, candidate_id),
        }
        for candidate_id in sorted(
            exclusion_reasons,
            key=lambda item: _frontier_rank_by_id(frontier_rows, item),
        )
    )
    required_rows = ranked_reserve[:required_replacement_count]
    required_max_cost = sum(
        (_money(row["estimated_cost_usd"]) for row in required_rows), Decimal("0")
    )
    total_max_cost = sum(
        (_money(row["estimated_cost_usd"]) for row in ranked_reserve), Decimal("0")
    )
    cost_plan: JsonRecord = {
        "schema_version": COST_SCHEMA_VERSION,
        "required_replacement_count": required_replacement_count,
        "available_reserve_count": len(ranked_reserve),
        "required_replacement_candidate_ids": [
            row["candidate_id"] for row in required_rows
        ],
        "required_replacement_max_cost_usd": _money_text(required_max_cost),
        "total_reserve_max_cost_usd": _money_text(total_max_cost),
        "paid_permitted": False,
        "provider_activity_permitted": False,
    }
    free_refresh_inputs = tuple(
        {
            "schema_version": FREE_REFRESH_SCHEMA_VERSION,
            "candidate_id": row["candidate_id"],
            "reserve_rank": row["reserve_rank"],
            "court": row["court"],
            "purchase_document_ids": list(
                cast(Sequence[object], row["purchase_document_ids"])
            ),
            "missing_core_document_count": row["missing_core_document_count"],
            "estimated_cost_usd": row["estimated_cost_usd"],
            "paid_permitted": False,
            "refresh_mode": "courtlistener_rest_noncharging_only",
        }
        for row in ranked_reserve
    )

    reserve_bytes = _jsonl_bytes(ranked_reserve)
    exclusion_bytes = _jsonl_bytes(exclusions)
    cost_bytes = _canonical_bytes(cost_plan)
    refresh_bytes = _jsonl_bytes(free_refresh_inputs)
    source_commitments = {
        "exact_successor_projection": _sha(original=exact_successor_projection_bytes),
        "exact_selection": _sha(original=exact_selection_bytes),
        "full_frontier": _sha(original=full_frontier_bytes),
        "frontier_run_card": _sha(original=frontier_run_card_bytes),
        "source_pool": _sha(original=source_pool_bytes),
        "original_projection": _sha(original=original_projection_bytes),
        "original_selection": _sha(original=original_selection_bytes),
        "original_reserve": _sha(original=original_reserve_bytes),
        "original_exclusions": _sha(original=original_exclusions_bytes),
        "final_clearance": _sha(original=final_clearance_bytes),
        "final_clearance_run_card": _sha(original=final_clearance_run_card_bytes),
        "current_quarantine": _sha(original=current_quarantine_bytes),
        "current_quarantine_run_card": _sha(original=current_quarantine_run_card_bytes),
    }
    output_commitments = {
        "target-cohort-selection.jsonl": _sha(original=exact_selection_bytes),
        "target-cohort-ranked-reserve.jsonl": _sha(original=reserve_bytes),
        "target-cohort-reserve-exclusions.jsonl": _sha(original=exclusion_bytes),
        "target-cohort-reserve-cost-plan.json": _sha(original=cost_bytes),
        "target-cohort-free-refresh-inputs.jsonl": _sha(original=refresh_bytes),
    }
    summary: JsonRecord = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "target_case_count": _TARGET_COUNT,
        "selected_case_count": len(exact_ids),
        "current_quarantine_case_count": len(current_quarantined),
        "required_replacement_count": required_replacement_count,
        "ranked_reserve_case_count": len(ranked_reserve),
        "ranking_policy": dict(frontier_policy),
        "source_commitments": source_commitments,
        "output_commitments": output_commitments,
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    # Self-excluded digest: computed over the summary *without* this key, then
    # inserted.  sha256(summary_bytes) therefore does not equal
    # extension_sha256; verifiers must use extension_summary_digest below.
    summary["extension_sha256"] = extension_summary_digest(summary)
    return Exact100ReserveExtension(
        selected_cohort_bytes=exact_selection_bytes,
        ranked_reserve=ranked_reserve,
        exclusions=exclusions,
        cost_plan=cost_plan,
        free_refresh_inputs=free_refresh_inputs,
        summary=summary,
    )


def _verify_exact_successor(
    projection: Mapping[str, object], *, selection_bytes: bytes
) -> tuple[str, ...]:
    if (
        projection.get("schema_version") != _EXACT_SUCCESSOR_SCHEMA
        or projection.get("target_case_count") != _TARGET_COUNT
        or projection.get("paid_activity_permitted") is not False
        or projection.get("provider_activity_permitted") is not False
        or projection.get("evaluation_authorized") is not False
        or projection.get("freeze_authorized") is not False
        or projection.get("dispatch_authorized") is not False
    ):
        raise Exact100ReserveExtensionError("exact successor contract mismatch")
    selection_sha = _sha(original=selection_bytes)
    commitments = _mapping(
        projection.get("output_commitments"), "exact successor outputs"
    )
    if (
        projection.get("selection_sha256") != selection_sha
        or commitments.get("target-cohort-selection.jsonl") != selection_sha
    ):
        raise Exact100ReserveExtensionError(
            "exact successor selection commitment mismatch"
        )
    selection = _jsonl_records(selection_bytes, "exact selection")
    ids = tuple(_candidate_id(row, "exact selection") for row in selection)
    if len(ids) != _TARGET_COUNT or len(set(ids)) != _TARGET_COUNT:
        raise Exact100ReserveExtensionError(
            "exact successor selection is not 100 unique cases"
        )
    return ids


def _verify_frontier(
    frontier: Mapping[str, object],
    *,
    frontier_bytes: bytes,
    run_card: Mapping[str, object],
    run_card_bytes: bytes,
    source_pool_bytes: bytes,
) -> tuple[list[JsonRecord], Mapping[str, object]]:
    if frontier.get("schema_version") != _FRONTIER_SCHEMA:
        raise Exact100ReserveExtensionError("unsupported full frontier schema")
    policy = _mapping(frontier.get("policy"), "frontier policy")
    if frontier.get("policy_sha256") != _sha(original=_canonical_value_bytes(policy)):
        raise Exact100ReserveExtensionError("full frontier policy self-hash mismatch")
    if (
        policy.get("frontier_truncated") is not False
        or policy.get("candidate_count") != _SOURCE_COUNT
        or policy.get("target_case_count") != _TARGET_COUNT
    ):
        raise Exact100ReserveExtensionError(
            "full frontier is not the untruncated 115-row authority"
        )
    source_commitments = _mapping(
        policy.get("source_commitments"), "frontier source commitments"
    )
    if frozenset(source_commitments) != _FRONTIER_SOURCE_COMMITMENTS or any(
        not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
        for digest in source_commitments.values()
    ):
        raise Exact100ReserveExtensionError(
            "frontier source commitments are incomplete or malformed"
        )
    if source_commitments.get("reconciled_selection_sha256") != _sha(
        original=source_pool_bytes
    ):
        raise Exact100ReserveExtensionError("frontier source-pool commitment mismatch")
    raw_rows = policy.get("candidates")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise Exact100ReserveExtensionError("full frontier candidates are malformed")
    rows = [
        dict(_mapping(row, "frontier candidate"))
        for row in cast(Sequence[object], raw_rows)
    ]
    if len(rows) != _SOURCE_COUNT:
        raise Exact100ReserveExtensionError(
            "full frontier does not contain 115 candidates"
        )
    ids: set[str] = set()
    prior_key: tuple[int, Decimal, str] | None = None
    for expected_rank, row in enumerate(rows, start=1):
        candidate_id = _candidate_id(row, "frontier candidate")
        if candidate_id in ids:
            raise Exact100ReserveExtensionError("full frontier has duplicate candidate")
        ids.add(candidate_id)
        if row.get("rank") != expected_rank:
            raise Exact100ReserveExtensionError(
                "full frontier rank sequence is inconsistent"
            )
        key = _ranking_key(row)
        if prior_key is not None and key < prior_key:
            raise Exact100ReserveExtensionError(
                "full frontier rank order violates frozen ranking"
            )
        prior_key = key
        _validate_frontier_row(row)
    _verify_completed_card(
        run_card,
        run_card_bytes=run_card_bytes,
        artifact_bytes=frontier_bytes,
        commitment_name="full_candidate_frontier",
        label="frontier run card",
        expected_stage="materialize-target-cohort-frontier",
        expected_count=_SOURCE_COUNT,
    )
    ranking_policy = {
        "attributes": list(_RANKING_ATTRIBUTES),
        "output_blind": True,
        "tie_breaker": "candidate_id",
    }
    return rows, ranking_policy


def _verify_original_projection(
    projection: Mapping[str, object],
    *,
    projection_bytes: bytes,
    exact_successor_projection: Mapping[str, object],
    selection_bytes: bytes,
    reserve_bytes: bytes,
    exclusions_bytes: bytes,
    source_pool_bytes: bytes,
    frontier_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, JsonRecord]:
    if (
        projection.get("schema_version") != _ORIGINAL_PROJECTION_SCHEMA
        or projection.get("target_case_count") != _TARGET_COUNT
        or projection.get("selected_case_count") != _TARGET_COUNT
        or projection.get("ranked_reserve_case_count") != _ORIGINAL_RESERVE_COUNT
        or projection.get("resolved_pool_case_count") != _SOURCE_COUNT
    ):
        raise Exact100ReserveExtensionError(
            f"original target projection contract mismatch: expected "
            f"{_ORIGINAL_PROJECTION_SCHEMA} with {_TARGET_COUNT} selected cases, "
            f"{_ORIGINAL_RESERVE_COUNT} reserve rows, and a {_SOURCE_COUNT}-row pool"
        )
    expected_policy = {
        "attributes": list(_RANKING_ATTRIBUTES),
        "output_blind": True,
        "tie_breaker": "candidate_id",
    }
    if projection.get("ranking_policy") != expected_policy:
        raise Exact100ReserveExtensionError(
            "original projection ranking policy mismatch"
        )
    successor_sources = _mapping(
        exact_successor_projection.get("source_commitments"), "exact successor sources"
    )
    if successor_sources.get("target_projection") != _sha(original=projection_bytes):
        raise Exact100ReserveExtensionError(
            "exact successor does not bind original projection"
        )
    outputs = _mapping(
        projection.get("output_commitments"), "original projection outputs"
    )
    expected_outputs = {
        "target-cohort-selection.jsonl": _sha(original=selection_bytes),
        "target-cohort-ranked-reserve.jsonl": _sha(original=reserve_bytes),
        "target-cohort-exclusions.jsonl": _sha(original=exclusions_bytes),
    }
    for name, digest in expected_outputs.items():
        if outputs.get(name) != digest:
            raise Exact100ReserveExtensionError(
                f"original projection {name} commitment mismatch"
            )
    inputs = _mapping(projection.get("input_commitments"), "original projection inputs")
    source_matches = [
        digest
        for name, digest in inputs.items()
        if str(name).endswith("/public-packet-selection-reconciled.jsonl")
    ]
    if source_matches != [_sha(original=source_pool_bytes)]:
        raise Exact100ReserveExtensionError(
            "original projection source-pool commitment mismatch"
        )
    selected = _candidate_index(
        _jsonl_records(selection_bytes, "original selection"), "original selection"
    )
    reserve_rows = _jsonl_records(reserve_bytes, "original reserve")
    reserve = _candidate_index(reserve_rows, "original reserve")
    exclusions = _candidate_index(
        _jsonl_records(exclusions_bytes, "original exclusions"), "original exclusions"
    )
    source = _candidate_index(
        _jsonl_records(source_pool_bytes, "source pool"), "source pool"
    )
    if len(selected) != _TARGET_COUNT or len(reserve) != _ORIGINAL_RESERVE_COUNT:
        raise Exact100ReserveExtensionError(
            "original projection is not the frozen 100+5 cohort"
        )
    if set(selected) & set(reserve) or not set(reserve) <= set(exclusions):
        raise Exact100ReserveExtensionError(
            "original reserve does not reconcile exclusions"
        )
    if set(selected) | set(exclusions) != set(source):
        raise Exact100ReserveExtensionError(
            "original selection and exclusions do not reconcile source pool"
        )
    ranked_reserve: dict[str, JsonRecord] = {}
    for expected_rank, row in enumerate(reserve_rows, start=1):
        candidate_id = _candidate_id(row, "original reserve")
        if (
            row.get("schema_version") != _ORIGINAL_RESERVE_SCHEMA
            or row.get("reserve_rank") != expected_rank
        ):
            raise Exact100ReserveExtensionError(
                "original reserve rank or schema mismatch"
            )
        frontier = frontier_by_id.get(candidate_id)
        if frontier is None:
            raise Exact100ReserveExtensionError(
                "original reserve candidate is absent from frontier"
            )
        expected_key = [
            frontier["missing_core_document_count"],
            frontier["estimated_cost_usd"],
            candidate_id,
        ]
        if (
            row.get("ranking_key") != expected_key
            or row.get("missing_core_document_count")
            != frontier["missing_core_document_count"]
            or row.get("estimated_cost_usd") != frontier["estimated_cost_usd"]
            or row.get("purchase_document_ids") != frontier["purchase_document_ids"]
            or row.get("missing_core_roles") != frontier["missing_core_roles"]
        ):
            raise Exact100ReserveExtensionError(
                "original reserve differs from authenticated frontier"
            )
        ranked_reserve[candidate_id] = row
    return ranked_reserve


def _verify_clearance_authority(
    *,
    clearance_bytes: bytes,
    run_card: Mapping[str, object],
    run_card_bytes: bytes,
    commitment_name: str,
    label: str,
    allowed_candidate_ids: set[str],
    run_card_schema: str,
    run_card_stage: str,
    require_status: bool = True,
) -> list[JsonRecord]:
    _verify_object_bytes(run_card, run_card_bytes, label=f"{label} run card")
    # Pin the run card's identity before trusting its commitments.  Without
    # this, any completed provider-free card whose output commitment happens to
    # match these bytes would be accepted as clearance or quarantine authority.
    if (
        run_card.get("schema_version") != run_card_schema
        or run_card.get("stage") != run_card_stage
    ):
        raise Exact100ReserveExtensionError(f"{label} run card identity mismatch")
    if (
        run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("provider_activity_requested") is not False
        or run_card.get("provider_activity_executed") is not False
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or not isinstance(run_card.get("source_commitments"), Mapping)
        or not cast(Mapping[str, object], run_card["source_commitments"])
    ):
        raise Exact100ReserveExtensionError(f"{label} run card contract mismatch")
    outputs = _mapping(run_card.get("output_commitments"), f"{label} outputs")
    commitment = outputs.get(commitment_name)
    if isinstance(commitment, Mapping):
        committed_sha = cast(Mapping[str, object], commitment).get("sha256")
    else:
        committed_sha = commitment
    if committed_sha != _sha(original=clearance_bytes):
        raise Exact100ReserveExtensionError(
            f"{label} run card output commitment mismatch"
        )
    records = _jsonl_records(clearance_bytes, label)
    seen_keys: set[tuple[str, str]] = set()
    for record in records:
        candidate_id = _candidate_id(record, label)
        if candidate_id not in allowed_candidate_ids:
            raise Exact100ReserveExtensionError(
                f"{label} candidate is outside exact selection"
                if label == "current quarantine"
                else f"{label} candidate is outside source pool"
            )
        source_document_id = record.get("source_document_id")
        key = (
            candidate_id,
            str(source_document_id)
            if source_document_id is not None
            else "row:" + json.dumps(record, sort_keys=True, separators=(",", ":")),
        )
        if key in seen_keys:
            raise Exact100ReserveExtensionError(f"duplicate {label} record")
        seen_keys.add(key)
        if require_status and record.get("status") not in {"cleared", "quarantined"}:
            raise Exact100ReserveExtensionError(f"{label} status is invalid")
    return records


def _verify_completed_card(
    card: Mapping[str, object],
    *,
    run_card_bytes: bytes,
    artifact_bytes: bytes,
    commitment_name: str,
    label: str,
    expected_stage: str,
    expected_count: int,
) -> None:
    _verify_object_bytes(card, run_card_bytes, label=label)
    digest = _sha(original=artifact_bytes)
    if (
        card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != expected_stage
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or card.get("record_count") != expected_count
        or card.get("target_case_count") != _TARGET_COUNT
        or card.get("frontier_sha256") != digest
        or card.get("output_commitments") != {commitment_name: digest}
        or card.get("zero_provider_activity_evidence") is not True
    ):
        raise Exact100ReserveExtensionError(f"{label} contract mismatch")
    sources = card.get("source_commitments")
    typed_sources = (
        cast(Mapping[object, object], sources) if isinstance(sources, Mapping) else None
    )
    if (
        typed_sources is None
        or frozenset(typed_sources) != _FRONTIER_CARD_SOURCE_COMMITMENTS
        or any(
            not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
            for digest in typed_sources.values()
        )
    ):
        raise Exact100ReserveExtensionError(
            f"{label} source commitments are incomplete or malformed"
        )


def _validate_frontier_row(row: Mapping[str, Any]) -> None:
    candidate_id = _candidate_id(row, "frontier candidate")
    missing_count = _nonnegative_int(
        row.get("missing_core_document_count"), "missing count"
    )
    purchase_count = _nonnegative_int(
        row.get("estimated_purchase_count"), "purchase count"
    )
    documents = _string_sequence(row.get("purchase_document_ids"), "purchase documents")
    _string_sequence(row.get("missing_core_roles"), "missing roles")
    reasons = row.get("exclusion_reasons")
    if not isinstance(reasons, Sequence) or isinstance(reasons, (str, bytes)):
        raise Exact100ReserveExtensionError("frontier exclusion reasons are malformed")
    if missing_count != purchase_count or missing_count != len(documents):
        raise Exact100ReserveExtensionError(
            f"frontier document counts differ: {candidate_id}"
        )
    cost = _money(row.get("estimated_cost_usd"))
    if cost != Decimal("3.05") * missing_count:
        raise Exact100ReserveExtensionError(
            f"frontier cost differs from frozen policy: {candidate_id}"
        )


def _extended_reserve_record(
    frontier: Mapping[str, Any],
    *,
    source_row: Mapping[str, Any],
    reserve_rank: int,
    origin: str,
) -> JsonRecord:
    candidate_id = _candidate_id(frontier, "frontier candidate")
    return {
        "schema_version": RESERVE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "case_id": source_row.get("case_id", candidate_id),
        "case_name": source_row.get("case_name"),
        "court": frontier.get("court"),
        "decision_date": source_row.get("decision_date"),
        "source_frontier_rank": frontier["rank"],
        "reserve_rank": reserve_rank,
        "reserve_origin": origin,
        "missing_core_document_count": frontier["missing_core_document_count"],
        "estimated_cost_usd": frontier["estimated_cost_usd"],
        "missing_core_roles": list(
            cast(Sequence[object], frontier["missing_core_roles"])
        ),
        "purchase_document_ids": list(
            cast(Sequence[object], frontier["purchase_document_ids"])
        ),
        "ranking_key": [
            frontier["missing_core_document_count"],
            frontier["estimated_cost_usd"],
            candidate_id,
        ],
    }


def _verify_object_bytes(
    value: Mapping[str, object], payload: bytes, *, label: str
) -> None:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100ReserveExtensionError(f"{label} is not valid JSON") from exc
    if not isinstance(decoded, Mapping) or dict(
        cast(Mapping[str, object], decoded)
    ) != dict(value):
        raise Exact100ReserveExtensionError(f"{label} differs from supplied bytes")


def _jsonl_records(payload: bytes, label: str) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line.strip():
            raise Exact100ReserveExtensionError(f"{label} has blank JSONL line")
        try:
            record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Exact100ReserveExtensionError(
                f"{label} line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise Exact100ReserveExtensionError(
                f"{label} line {line_number} is not an object"
            )
        records.append(cast(JsonRecord, record))
    return records


def _candidate_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[str, JsonRecord]:
    output: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _candidate_id(record, label)
        if candidate_id in output:
            raise Exact100ReserveExtensionError(
                f"duplicate {label} candidate: {candidate_id}"
            )
        output[candidate_id] = dict(record)
    return output


def _records_by_candidate(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    output: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        output.setdefault(_candidate_id(record, "clearance"), []).append(record)
    return output


def _candidate_id(record: Mapping[str, Any], label: str) -> str:
    value = record.get("candidate_id")
    if not isinstance(value, str) or not value:
        raise Exact100ReserveExtensionError(f"{label} lacks candidate_id")
    return value


def _ranking_key(record: Mapping[str, Any]) -> tuple[int, Decimal, str]:
    return (
        _nonnegative_int(record.get("missing_core_document_count"), "missing count"),
        _money(record.get("estimated_cost_usd")),
        _candidate_id(record, "frontier candidate"),
    )


def _frontier_rank_by_id(rows: Sequence[Mapping[str, Any]], candidate_id: str) -> int:
    for row in rows:
        if row.get("candidate_id") == candidate_id:
            return cast(int, row["rank"])
    raise Exact100ReserveExtensionError("candidate is absent from frontier")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Exact100ReserveExtensionError(f"{label} is not an object")
    return cast(Mapping[str, Any], value)


def _string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise Exact100ReserveExtensionError(f"{label} is malformed")
    values = tuple(cast(Sequence[object], value))
    if any(not isinstance(item, str) or not item for item in values):
        raise Exact100ReserveExtensionError(f"{label} is malformed")
    return cast(tuple[str, ...], values)


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Exact100ReserveExtensionError(f"{label} is invalid")
    return value


def _money(value: object) -> Decimal:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", value) is None
    ):
        raise Exact100ReserveExtensionError("money value is invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise Exact100ReserveExtensionError("money value is invalid") from exc
    if amount < 0:
        raise Exact100ReserveExtensionError("money value is invalid")
    return amount


def _money_text(value: Decimal) -> str:
    return f"{value:.2f}"


def _sha(*, original: bytes) -> str:
    return "sha256:" + hashlib.sha256(original).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100ReserveExtensionError,
        error_message="reserve extension artifact is not canonicalizable",
    )


def _canonical_value_bytes(value: object) -> bytes:
    return canonical_json_value_bytes(
        value,
        error_type=Exact100ReserveExtensionError,
        error_message="reserve extension value is not canonicalizable",
    )


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(record) for record in records)

"""Provider-free exact-100 successor after ranked-reserve terminal recovery."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.decision_text_artifact import CYCLE_1_ELIGIBILITY_ANCHOR
from legalforecast.ingestion.disclosure_clearance import (
    DisclosureClearanceError,
    require_clearance_policy,
)
from legalforecast.ingestion.docket_decision_text_source import (
    DocketDecisionTextSourceError,
    validate_terminal_purchase_disposition_record,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.ranked_reserve_replacement import (
    CURRENT_REPLAY_RESULT_SCHEMA_VERSION,
    POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION,
    VerifiedRankedReservePostPurchaseReplay,
    ranked_reserve_canonical_sha256,
    ranked_reserve_result_bytes,
    require_verified_post_purchase_replay,
    validate_authenticated_legacy_replay,
    validate_authenticated_post_purchase_replay,
)

JsonRecord = dict[str, Any]

FROZEN_ZERO_COST_CANDIDATE_IDS = ("70525291", "71279774", "71677178")
RESULT_SCHEMA_VERSION = "legalforecast.ranked_reserve_replacement_result.v2"
SELECTION_SCHEMA_VERSION = "legalforecast.zero_cost_successor_selection.v1"
CONFIG_SCHEMA_VERSION = "legalforecast.zero_cost_successor_config.v1"
STATE_SCHEMA_VERSION = "legalforecast.zero_cost_successor_state.v1"

_TARGET_COUNT = 100
_PRECURSOR_COUNT = 99
_ORIGINAL_RETAINED_COUNT = 97
_RESERVE_PROMOTION_COUNT = 2
_REQUIRED_COUNTER_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT.value,
        DocumentRole.AMENDED_COMPLAINT.value,
        DocumentRole.MTD_MEMORANDUM.value,
        DocumentRole.OPPOSITION.value,
        DocumentRole.REPLY.value,
        DocumentRole.DECISION.value,
    }
)
_OPTIONAL_COUNTER_ROLES = frozenset(
    {
        DocumentRole.MTD_NOTICE.value,
    }
)
_DIGEST_FIELDS = (
    "projection_sha256",
    "purchase_policy_sha256",
    "purchase_journal_state_sha256",
    "terminal_exclusions_sha256",
    "active_selection_sha256",
    "replacement_selection_sha256",
    "successor_exclusions_sha256",
    "replacement_budget_plan_sha256",
)
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "projection_sha256",
        "cycle_id",
        "purchase_policy_sha256",
        "purchase_journal_state_sha256",
        "hard_cap_usd",
        "terminal_exclusions_sha256",
        "terminal_disposition",
        "terminal_disposition_sha256",
        "active_selection_sha256",
        "replacement_selection_sha256",
        "successor_exclusions_sha256",
        "replacement_budget_plan_sha256",
        "active_case_count",
        "replacement_case_count",
        "committed_spend_usd",
        "reserved_replacement_spend_usd",
        "remaining_headroom_usd",
        "successor_approval_required",
        "replacement_event_record_sha256s",
        "tranche_event_record_sha256s",
        "provider_activity_requested",
        "paid_activity_requested",
        "paid_activity_executed",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    }
)
_CURRENT_RESULT_FIELDS = _RESULT_FIELDS | {"authenticated_legacy_replay"}
_POST_PURCHASE_RESULT_FIELDS = _CURRENT_RESULT_FIELDS | {
    "authenticated_post_purchase_replay"
}


class ZeroCostSuccessorError(ValueError):
    """Raised when the exact-100 successor cannot be authenticated."""


_VERIFIED_POST_PURCHASE_RANKED_RESULT_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class VerifiedPostPurchaseRankedResult:
    """Opaque fully replayed v4 ranked-result capability."""

    ranked_result_bytes: bytes
    transition: VerifiedRankedReservePostPurchaseReplay
    _token: object

    def __init__(self, **_values: object) -> None:
        raise TypeError(
            "VerifiedPostPurchaseRankedResult is created only by full ranked replay"
        )

    def is_replay_minted(self) -> bool:
        """Return whether full producer replay minted this result."""

        return self._token is _VERIFIED_POST_PURCHASE_RANKED_RESULT_TOKEN


def _mint_verified_post_purchase_ranked_result(  # pyright: ignore[reportUnusedFunction]
    ranked_result: Mapping[str, object],
    transition: VerifiedRankedReservePostPurchaseReplay,
) -> VerifiedPostPurchaseRankedResult:
    """Mint a v4 result capability after exact full-result reconstruction."""

    require_verified_post_purchase_replay(ranked_result, transition)
    verified = object.__new__(VerifiedPostPurchaseRankedResult)
    object.__setattr__(
        verified, "ranked_result_bytes", ranked_reserve_result_bytes(ranked_result)
    )
    object.__setattr__(verified, "transition", transition)
    object.__setattr__(verified, "_token", _VERIFIED_POST_PURCHASE_RANKED_RESULT_TOKEN)
    return verified


@dataclass(frozen=True, slots=True)
class ZeroCostSuccessor:
    """Closed exact-100 selection, config, and terminal state."""

    selection: tuple[JsonRecord, ...]
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[JsonRecord, ...]
    config: JsonRecord
    state: JsonRecord


@dataclass(frozen=True, slots=True)
class SuccessorCounterTotals:
    """Role-aware required-document totals for one successor selection."""

    required_document_count: int
    free_required_document_count: int
    missing_required_document_count: int
    selected_document_count: int
    manifest_document_count: int
    free_manifest_document_count: int


def project_zero_cost_successor(
    *,
    target_projection: Mapping[str, object],
    original_selection: Sequence[Mapping[str, Any]],
    ranked_reserve: Sequence[Mapping[str, Any]],
    source_pool: Sequence[Mapping[str, Any]],
    ranked_result: Mapping[str, object],
    ranked_result_bytes: bytes,
    authenticated_ranked_result: (
        Mapping[str, object] | VerifiedPostPurchaseRankedResult
    ),
    active_selection: Sequence[Mapping[str, Any]],
    active_selection_bytes: bytes,
    replacement_selection: Sequence[Mapping[str, Any]],
    replacement_selection_bytes: bytes,
    successor_exclusions_bytes: bytes,
    replacement_budget_plan_bytes: bytes,
    disclosure_clearance: Sequence[Mapping[str, Any]],
    disclosure_clearance_bytes: bytes,
    disclosure_clearance_run_card_bytes: bytes,
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    restriction_evidence: Sequence[Mapping[str, Any]],
) -> ZeroCostSuccessor:
    """Authenticate the exact 99-case precursor and add one cleared free case."""

    _require_target_projection(target_projection)
    original = _candidate_index(original_selection, "original selection")
    reserves = _candidate_index(ranked_reserve, "ranked reserve")
    pool = _candidate_index(source_pool, "source pool")
    active = _candidate_index(active_selection, "active selection")
    replacements = _candidate_index(replacement_selection, "replacement selection")
    if len(original) != _TARGET_COUNT or len(reserves) != 5:
        raise ZeroCostSuccessorError("successor requires the exact frozen 100+5 pool")
    if not set(original) | set(reserves) <= set(pool):
        raise ZeroCostSuccessorError("frozen selection is absent from the source pool")

    is_post_purchase_v4 = (
        ranked_result.get("schema_version")
        == POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION
    )
    verified_post_purchase_transition: (
        VerifiedRankedReservePostPurchaseReplay | None
    ) = (
        authenticated_ranked_result.transition
        if type(authenticated_ranked_result) is VerifiedPostPurchaseRankedResult
        and authenticated_ranked_result.is_replay_minted()
        else None
    )

    disposition = _verify_ranked_result(
        target_projection=target_projection,
        ranked_result=ranked_result,
        ranked_result_bytes=ranked_result_bytes,
        active_selection_bytes=active_selection_bytes,
        replacement_selection_bytes=replacement_selection_bytes,
        successor_exclusions_bytes=successor_exclusions_bytes,
        replacement_budget_plan_bytes=replacement_budget_plan_bytes,
        verified_post_purchase_transition=verified_post_purchase_transition,
    )
    if is_post_purchase_v4:
        if (
            type(authenticated_ranked_result) is not VerifiedPostPurchaseRankedResult
            or not authenticated_ranked_result.is_replay_minted()
        ):
            raise ZeroCostSuccessorError(
                "post-purchase v4 result lacks full authenticated producer replay"
            )
        try:
            require_verified_post_purchase_replay(
                ranked_result, authenticated_ranked_result.transition
            )
        except ValueError as exc:
            raise ZeroCostSuccessorError(str(exc)) from exc
        if ranked_result_bytes != authenticated_ranked_result.ranked_result_bytes:
            raise ZeroCostSuccessorError(
                "ranked result differs from authenticated ranked-reserve replay"
            )
    else:
        if not isinstance(authenticated_ranked_result, Mapping):
            raise ZeroCostSuccessorError(
                "verified post-purchase result cannot authenticate a legacy result"
            )
        authenticated_result = authenticated_ranked_result
        if ranked_result != authenticated_result:
            raise ZeroCostSuccessorError(
                "ranked result differs from authenticated ranked-reserve replay"
            )

    residual_ids = {
        _required_text(pair, "candidate_id")
        for pair in _mapping_sequence(
            disposition.get("residual_failure_pairs"), "residual failure pairs"
        )
    }
    promoted_ids = tuple(replacements)
    expected_promoted_ids = tuple(
        item[0]
        for item in sorted(
            reserves.items(), key=lambda item: _positive_int(item[1], "reserve_rank")
        )[:_RESERVE_PROMOTION_COUNT]
    )
    if promoted_ids != expected_promoted_ids:
        raise ZeroCostSuccessorError(
            "replacement selection is not frozen reserve ranks 1/2"
        )
    if any(
        replacements[candidate_id] != pool[candidate_id]
        for candidate_id in promoted_ids
    ):
        raise ZeroCostSuccessorError("replacement row differs from frozen source pool")
    expected_active_ids = (set(original) - residual_ids) | set(promoted_ids)
    if (
        len(residual_ids) != 3
        or len(set(original) - residual_ids) != _ORIGINAL_RETAINED_COUNT
        or len(active) != _PRECURSOR_COUNT
        or set(active) != expected_active_ids
    ):
        raise ZeroCostSuccessorError(
            "ranked successor is not 97 retained plus two reserves"
        )
    for candidate_id, row in active.items():
        if row != pool[candidate_id]:
            raise ZeroCostSuccessorError(
                "active selection row differs from frozen source pool"
            )

    relevance = _candidate_index(case_relevance, "case relevance")
    manifest = _document_index(download_manifest, "download manifest")
    clearance = _document_index(disclosure_clearance, "disclosure clearance")
    restrictions = _document_index(restriction_evidence, "restriction evidence")
    chosen: str | None = None
    for candidate_id in FROZEN_ZERO_COST_CANDIDATE_IDS:
        if candidate_id not in pool or candidate_id not in relevance:
            raise ZeroCostSuccessorError(
                f"frozen zero-cost candidate is absent: {candidate_id}"
            )
        if _candidate_is_fully_cleared(
            candidate_id,
            selection=pool[candidate_id],
            relevance=relevance[candidate_id],
            manifest=manifest,
            clearance=clearance,
            restrictions=restrictions,
        ):
            chosen = candidate_id
            break
    if chosen is None:
        raise ZeroCostSuccessorError("no frozen zero-cost candidate is fully cleared")

    selection = (*tuple(dict(row) for row in active_selection), dict(pool[chosen]))
    if (
        len(selection) != _TARGET_COUNT
        or len({row["candidate_id"] for row in selection}) != _TARGET_COUNT
    ):
        raise ZeroCostSuccessorError(
            "successor selection is not exactly 100 unique cases"
        )
    selected_ids = tuple(_required_text(row, "candidate_id") for row in selection)
    missing_relevance = [
        candidate_id for candidate_id in selected_ids if candidate_id not in relevance
    ]
    if missing_relevance:
        raise ZeroCostSuccessorError(
            "successor case relevance is incomplete: " + ", ".join(missing_relevance)
        )
    selected_id_set = set(selected_ids)
    selected_relevance = tuple(
        dict(relevance[candidate_id]) for candidate_id in selected_ids
    )
    selected_manifest = tuple(
        dict(row)
        for row in download_manifest
        if _required_text(row, "candidate_id") in selected_id_set
    )
    selected_clearance = tuple(
        dict(row)
        for row in disclosure_clearance
        if _required_text(row, "candidate_id") in selected_id_set
    )
    selected_restrictions = tuple(
        dict(row)
        for row in restriction_evidence
        if _required_text(row, "candidate_id") in selected_id_set
    )
    _require_union_document_coverage(
        selection=selection,
        case_relevance=selected_relevance,
        download_manifest=selected_manifest,
        disclosure_clearance=selected_clearance,
        restriction_evidence=selected_restrictions,
    )
    selection, _counter_totals = normalize_successor_selection_counters(
        selection,
        selected_manifest,
        validate_stored=False,
    )
    try:
        selected_filter_results = tuple(
            result.to_record() for result in filter_core_documents(selected_relevance)
        )
    except (TypeError, ValueError) as exc:
        raise ZeroCostSuccessorError(str(exc)) from exc
    if len(selected_filter_results) != _TARGET_COUNT or any(
        row.get("excluded") is True for row in selected_filter_results
    ):
        raise ZeroCostSuccessorError(
            "successor core-document eligibility does not cover exactly 100 cases"
        )
    for row in selected_manifest:
        if row.get("free_or_purchased") not in {"free", "purchased"}:
            raise ZeroCostSuccessorError(
                "download manifest row has an unsupported free_or_purchased value: "
                f"{row.get('candidate_id')}/{row.get('source_document_id')}"
            )
    selection_bytes = _jsonl_bytes(selection)
    relevance_bytes = _jsonl_bytes(selected_relevance)
    manifest_bytes = _jsonl_bytes(selected_manifest)
    free_manifest_bytes = _jsonl_bytes(
        tuple(
            row for row in selected_manifest if row.get("free_or_purchased") == "free"
        )
    )
    purchased_manifest_bytes = _jsonl_bytes(
        tuple(
            row
            for row in selected_manifest
            if row.get("free_or_purchased") == "purchased"
        )
    )
    clearance_output_bytes = _jsonl_bytes(selected_clearance)
    restriction_output_bytes = _jsonl_bytes(selected_restrictions)
    filter_bytes = _jsonl_bytes(selected_filter_results)
    source_commitments = {
        "target_projection": _canonical_sha256(target_projection),
        "ranked_result": _bytes_sha256(ranked_result_bytes),
        "ranked_active_selection": _bytes_sha256(active_selection_bytes),
        "ranked_replacement_selection": _bytes_sha256(replacement_selection_bytes),
        "ranked_successor_exclusions": _bytes_sha256(successor_exclusions_bytes),
        "ranked_replacement_budget_plan": _bytes_sha256(replacement_budget_plan_bytes),
        "disclosure_clearance": _bytes_sha256(disclosure_clearance_bytes),
        "disclosure_clearance_run_card": _bytes_sha256(
            disclosure_clearance_run_card_bytes
        ),
        "purchase_policy": _digest(
            ranked_result.get("purchase_policy_sha256"), "purchase policy"
        ),
        "purchase_journal_state": _digest(
            ranked_result.get("purchase_journal_state_sha256"),
            "purchase journal state",
        ),
        "purchase_result": _prefixed_sha256(
            disposition.get("purchase_result_sha256"), "purchase result"
        ),
        "purchase_run_card": _prefixed_sha256(
            disposition.get("purchase_run_card_sha256"), "purchase run card"
        ),
        "screening_snapshot_manifest": _prefixed_sha256(
            disposition.get("snapshot_manifest_sha256"),
            "screening snapshot manifest",
        ),
    }
    config: JsonRecord = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "cycle_id": _required_text(ranked_result, "cycle_id"),
        "target_case_count": _TARGET_COUNT,
        "eligibility_anchor": CYCLE_1_ELIGIBILITY_ANCHOR.isoformat(),
        "hard_cap_usd": _money(ranked_result.get("hard_cap_usd"), "hard cap"),
        "frozen_zero_cost_candidate_ids": list(FROZEN_ZERO_COST_CANDIDATE_IDS),
        "selected_zero_cost_candidate_id": chosen,
        "selection_schema_version": SELECTION_SCHEMA_VERSION,
        "source_commitments": source_commitments,
        "output_commitments": {
            "target-cohort-selection.jsonl": _bytes_sha256(selection_bytes),
            "case-relevance.jsonl": _bytes_sha256(relevance_bytes),
            "document-downloads-merged.jsonl": _bytes_sha256(manifest_bytes),
            "free-document-downloads.jsonl": _bytes_sha256(free_manifest_bytes),
            "purchased-document-downloads.jsonl": _bytes_sha256(
                purchased_manifest_bytes
            ),
            "disclosure-clearance.jsonl": _bytes_sha256(clearance_output_bytes),
            "restriction-evidence.jsonl": _bytes_sha256(restriction_output_bytes),
            "core-filter-results.jsonl": _bytes_sha256(filter_bytes),
            "missing-core-budget-plan.json": _bytes_sha256(
                replacement_budget_plan_bytes
            ),
            "target-cohort-exclusions.jsonl": _bytes_sha256(successor_exclusions_bytes),
            "target-cohort-ranked-reserve.jsonl": _bytes_sha256(b""),
        },
        "selection_sha256": _bytes_sha256(selection_bytes),
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    config_bytes = canonical_json_bytes(
        config,
        error_type=ZeroCostSuccessorError,
        error_message="successor config is not canonical JSON",
    )
    state: JsonRecord = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "completed",
        "cycle_id": config["cycle_id"],
        "original_selected_case_count": _TARGET_COUNT,
        "terminal_residual_case_count": len(residual_ids),
        "retained_original_case_count": _ORIGINAL_RETAINED_COUNT,
        "promoted_reserve_case_count": _RESERVE_PROMOTION_COUNT,
        "zero_cost_successor_case_count": 1,
        "selected_case_count": len(selection),
        "selected_zero_cost_candidate_id": chosen,
        "hard_cap_usd": config["hard_cap_usd"],
        "committed_spend_usd": _money(
            ranked_result.get("committed_spend_usd"), "committed spend"
        ),
        "reserved_replacement_spend_usd": _money(
            ranked_result.get("reserved_replacement_spend_usd"),
            "reserved replacement spend",
        ),
        "remaining_headroom_usd": _money(
            ranked_result.get("remaining_headroom_usd"), "remaining headroom"
        ),
        "selection_sha256": config["selection_sha256"],
        "config_sha256": _bytes_sha256(config_bytes),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    return ZeroCostSuccessor(
        selection=selection,
        case_relevance=selected_relevance,
        download_manifest=selected_manifest,
        disclosure_clearance=selected_clearance,
        restriction_evidence=selected_restrictions,
        core_filter_results=selected_filter_results,
        config=config,
        state=state,
    )


def _require_target_projection(projection: Mapping[str, object]) -> None:
    if (
        projection.get("schema_version") != "legalforecast.target_cohort_projection.v1"
        or projection.get("selected_case_count") != _TARGET_COUNT
        or projection.get("ranked_reserve_case_count") != 5
        or projection.get("eligibility_anchor")
        != CYCLE_1_ELIGIBILITY_ANCHOR.isoformat()
    ):
        raise ZeroCostSuccessorError("unsupported frozen target projection")


def _verify_ranked_result(
    *,
    target_projection: Mapping[str, object],
    ranked_result: Mapping[str, object],
    ranked_result_bytes: bytes,
    active_selection_bytes: bytes,
    replacement_selection_bytes: bytes,
    successor_exclusions_bytes: bytes,
    replacement_budget_plan_bytes: bytes,
    verified_post_purchase_transition: (
        VerifiedRankedReservePostPurchaseReplay | None
    ) = None,
) -> Mapping[str, object]:
    schema_version = ranked_result.get("schema_version")
    expected_fields = (
        _POST_PURCHASE_RESULT_FIELDS
        if schema_version == POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION
        else _CURRENT_RESULT_FIELDS
        if schema_version == CURRENT_REPLAY_RESULT_SCHEMA_VERSION
        else _RESULT_FIELDS
    )
    if frozenset(ranked_result) != expected_fields or schema_version not in {
        RESULT_SCHEMA_VERSION,
        CURRENT_REPLAY_RESULT_SCHEMA_VERSION,
        POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION,
    }:
        raise ZeroCostSuccessorError("unsupported ranked successor result")
    try:
        canonical = ranked_reserve_result_bytes(ranked_result)
    except ValueError as exc:
        raise ZeroCostSuccessorError(
            "ranked successor result is not canonical JSON"
        ) from exc
    if ranked_result_bytes != canonical:
        raise ZeroCostSuccessorError("ranked successor result is not canonical JSON")
    if ranked_result.get("projection_sha256") != target_projection.get(
        "projection_sha256"
    ):
        raise ZeroCostSuccessorError("ranked successor targets another projection")
    commitments = {
        "active_selection_sha256": active_selection_bytes,
        "replacement_selection_sha256": replacement_selection_bytes,
        "successor_exclusions_sha256": successor_exclusions_bytes,
        "replacement_budget_plan_sha256": replacement_budget_plan_bytes,
    }
    if any(
        ranked_result.get(field) != _bytes_sha256(payload)
        for field, payload in commitments.items()
    ):
        raise ZeroCostSuccessorError("ranked successor artifact commitment mismatch")
    for field in _DIGEST_FIELDS:
        _digest(ranked_result.get(field), field)
    for field in (
        "provider_activity_requested",
        "paid_activity_requested",
        "paid_activity_executed",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    ):
        if ranked_result.get(field) is not False:
            raise ZeroCostSuccessorError("ranked successor grants prohibited activity")
    if (
        ranked_result.get("active_case_count") != _PRECURSOR_COUNT
        or ranked_result.get("replacement_case_count") != _RESERVE_PROMOTION_COUNT
        or ranked_result.get("successor_approval_required") is not True
    ):
        raise ZeroCostSuccessorError(
            "ranked successor is not the exact 99-case precursor"
        )
    hard_cap = _money(ranked_result.get("hard_cap_usd"), "hard cap")
    projection_cap = _money(
        target_projection.get("max_projected_budget_usd"), "projection cap"
    )
    if hard_cap != projection_cap:
        raise ZeroCostSuccessorError("ranked successor changed the frozen hard cap")
    try:
        disposition = validate_terminal_purchase_disposition_record(
            ranked_result.get("terminal_disposition")
        )
    except DocketDecisionTextSourceError as exc:
        raise ZeroCostSuccessorError(str(exc)) from exc
    expected_disposition_state = ranked_result.get("purchase_journal_state_sha256")
    if (
        schema_version == POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION
        and verified_post_purchase_transition is not None
    ):
        expected_disposition_state = (
            "sha256:"
            + verified_post_purchase_transition.live_snapshot.purchase_state_sha256
        )
    if (
        ranked_result.get("terminal_disposition_sha256")
        != ranked_reserve_canonical_sha256(disposition)
        or _sha256_hex(
            disposition.get("residual_terminal_exclusions_sha256"),
            "terminal disposition residual exclusions",
        )
        != _sha256_hex(
            ranked_result.get("terminal_exclusions_sha256"),
            "ranked successor terminal exclusions",
        )
        or disposition.get("purchase_journal_state_sha256")
        != expected_disposition_state
        or disposition.get("partition_disjoint") is not True
        or disposition.get("partition_exhaustive") is not True
    ):
        raise ZeroCostSuccessorError("terminal disposition commitment mismatch")
    if schema_version in {
        CURRENT_REPLAY_RESULT_SCHEMA_VERSION,
        POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION,
    }:
        try:
            replay = validate_authenticated_legacy_replay(
                ranked_result.get("authenticated_legacy_replay")
            )
        except ValueError as exc:
            raise ZeroCostSuccessorError(str(exc)) from exc
        companion_fields = {
            "precursor_active_selection_sha256": "active_selection_sha256",
            "precursor_replacement_selection_sha256": ("replacement_selection_sha256"),
            "precursor_successor_exclusions_sha256": "successor_exclusions_sha256",
            "precursor_replacement_budget_plan_sha256": (
                "replacement_budget_plan_sha256"
            ),
        }
        authenticated_events = replay.get("authenticated_event_record_sha256s")
        if (
            any(
                replay.get(proof_field) != ranked_result.get(result_field)
                for proof_field, result_field in companion_fields.items()
            )
            or authenticated_events
            != ranked_result.get("replacement_event_record_sha256s")
            or authenticated_events != ranked_result.get("tranche_event_record_sha256s")
        ):
            raise ZeroCostSuccessorError(
                "authenticated legacy replay differs from current output commitments"
            )
    if schema_version == POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION:
        try:
            post_purchase = validate_authenticated_post_purchase_replay(
                ranked_result.get("authenticated_post_purchase_replay")
            )
        except ValueError as exc:
            raise ZeroCostSuccessorError(str(exc)) from exc
        prior_result = post_purchase["prior_result"]
        if (
            post_purchase.get("current_purchase_journal_state_sha256")
            != ranked_result.get("purchase_journal_state_sha256")
            or post_purchase.get("current_committed_spend_usd")
            != ranked_result.get("committed_spend_usd")
            or prior_result.get("authenticated_legacy_replay")
            != ranked_result.get("authenticated_legacy_replay")
            or any(
                prior_result.get(field) != ranked_result.get(field)
                for field in (
                    "projection_sha256",
                    "cycle_id",
                    "purchase_policy_sha256",
                    "hard_cap_usd",
                    "active_selection_sha256",
                    "replacement_selection_sha256",
                    "successor_exclusions_sha256",
                    "replacement_budget_plan_sha256",
                    "replacement_event_record_sha256s",
                    "tranche_event_record_sha256s",
                )
            )
        ):
            raise ZeroCostSuccessorError(
                "authenticated post-purchase replay differs from current output "
                "commitments"
            )
    return disposition


def _candidate_is_fully_cleared(
    candidate_id: str,
    *,
    selection: Mapping[str, Any],
    relevance: Mapping[str, Any],
    manifest: Mapping[tuple[str, str], Mapping[str, Any]],
    clearance: Mapping[tuple[str, str], Mapping[str, Any]],
    restrictions: Mapping[tuple[str, str], Mapping[str, Any]],
) -> bool:
    _require_eligible_selection(selection, candidate_id=candidate_id)
    selection_documents = _documents(selection, "selection")
    relevance_documents = _documents(relevance, "case relevance")
    selected_ids = {
        _required_text(row, "source_document_id") for row in selection_documents
    }
    relevant_ids = {
        _required_text(row, "source_document_id") for row in relevance_documents
    }
    keys = {(candidate_id, document_id) for document_id in selected_ids}
    if selected_ids != relevant_ids or keys != {
        key for key in manifest if key[0] == candidate_id
    }:
        raise ZeroCostSuccessorError(
            "candidate document coverage differs across frozen artifacts: "
            f"{candidate_id}"
        )
    if keys != {key for key in clearance if key[0] == candidate_id} or keys != {
        key for key in restrictions if key[0] == candidate_id
    }:
        raise ZeroCostSuccessorError(
            f"candidate clearance/restriction coverage is incomplete: {candidate_id}"
        )
    for document in selection_documents:
        model_visible = document.get("model_visible")
        contains_outcome = document.get("contains_target_outcome")
        if model_visible is True and (
            contains_outcome is not False
            or document.get("is_predecision_material") is not True
        ):
            raise ZeroCostSuccessorError(
                f"model-visible outcome leakage is unproven: {candidate_id}"
            )
        if contains_outcome is True and model_visible is not False:
            raise ZeroCostSuccessorError(
                f"decision material is model-visible: {candidate_id}"
            )
        _reject_positive_restriction(document, candidate_id=candidate_id)
    try:
        filter_result = filter_core_documents((relevance,))
    except (TypeError, ValueError) as exc:
        raise ZeroCostSuccessorError(str(exc)) from exc
    if (
        len(filter_result) != 1
        or filter_result[0].candidate_id != candidate_id
        or filter_result[0].excluded
        or filter_result[0].core_missing_documents
    ):
        raise ZeroCostSuccessorError(
            f"candidate core documents are incomplete: {candidate_id}"
        )
    for key in sorted(keys):
        source = manifest[key]
        decision = clearance[key]
        restriction = restrictions[key]
        if decision.get("status") != "cleared":
            return False
        for field in ("sha256", "byte_count", "free_or_purchased"):
            if decision.get(field) != source.get(field):
                raise ZeroCostSuccessorError(
                    f"clearance differs from manifest for {key}"
                )
        if source.get("free_or_purchased") != "free":
            raise ZeroCostSuccessorError(
                f"zero-cost successor document is not free: {key}"
            )
        _require_zero_cost_clearance_policy(decision, key=key)
        _reject_positive_restriction(decision, candidate_id=candidate_id)
        _reject_positive_restriction(restriction, candidate_id=candidate_id)
    return True


def _require_union_document_coverage(
    *,
    selection: Sequence[Mapping[str, Any]],
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    disclosure_clearance: Sequence[Mapping[str, Any]],
    restriction_evidence: Sequence[Mapping[str, Any]],
) -> None:
    """Require one exact document-key universe across the emitted 100 cases."""

    selection_documents: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in selection:
        candidate_id = _required_text(record, "candidate_id")
        for document in _documents(record, f"selection {candidate_id}"):
            _require_parent_scoped_document_candidate(
                document,
                candidate_id=candidate_id,
                label="selection",
            )
            key = (candidate_id, _required_text(document, "source_document_id"))
            if key in selection_documents:
                raise ZeroCostSuccessorError(
                    f"selection repeats document coverage: {key}"
                )
            selection_documents[key] = document
    selection_keys = set(selection_documents)

    relevance_documents: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in case_relevance:
        candidate_id = _required_text(record, "candidate_id")
        for document in _documents(record, f"case relevance {candidate_id}"):
            _require_parent_scoped_document_candidate(
                document,
                candidate_id=candidate_id,
                label="relevance",
            )
            key = (candidate_id, _required_text(document, "source_document_id"))
            if key in relevance_documents:
                raise ZeroCostSuccessorError(
                    f"case relevance repeats document coverage: {key}"
                )
            relevance_documents[key] = document
    relevance_keys = set(relevance_documents)

    manifest_keys = set(_document_index(download_manifest, "download manifest"))
    clearance_keys = set(_document_index(disclosure_clearance, "disclosure clearance"))
    restriction_keys = set(
        _document_index(restriction_evidence, "restriction evidence")
    )
    if selection_keys != relevance_keys or not (
        manifest_keys == clearance_keys == restriction_keys
    ):
        raise ZeroCostSuccessorError(
            "exact-100 selection document coverage differs across standard surfaces"
        )
    if not manifest_keys <= selection_keys:
        raise ZeroCostSuccessorError(
            "exact-100 acquired documents are absent from the selection"
        )
    for key in selection_keys - manifest_keys:
        for document in (selection_documents[key], relevance_documents[key]):
            if (
                document.get("requires_paid_recovery") is not True
                or document.get("availability_status") != "unavailable"
            ):
                raise ZeroCostSuccessorError(
                    f"unacquired successor document is not a paid-recovery gap: {key}"
                )


def normalize_successor_selection_counters(
    selection: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    *,
    validate_stored: bool,
) -> tuple[tuple[JsonRecord, ...], SuccessorCounterTotals]:
    """Derive or verify role-aware free/missing counters from authenticated rows."""

    manifest = _document_index(download_manifest, "successor counter manifest")
    for key, record in manifest.items():
        phase = record.get("free_or_purchased")
        if phase not in {"free", "purchased"}:
            raise ZeroCostSuccessorError(
                "download manifest row has an unsupported free_or_purchased value: "
                f"{key[0]}/{key[1]}"
            )

    normalized: list[JsonRecord] = []
    selected_keys: set[tuple[str, str]] = set()
    total_required = 0
    total_free_required = 0
    total_missing_required = 0
    for record in selection:
        candidate_id = _required_text(record, "candidate_id")
        required_count = 0
        free_required_count = 0
        missing_required_count = 0
        for document in _documents(record, f"selection {candidate_id}"):
            _require_parent_scoped_document_candidate(
                document,
                candidate_id=candidate_id,
                label="selection counter",
            )
            key = (candidate_id, _required_text(document, "source_document_id"))
            if key in selected_keys:
                raise ZeroCostSuccessorError(
                    f"selection repeats successor counter document: {key}"
                )
            selected_keys.add(key)
            role = _required_text(document, "document_role")
            manifest_record = manifest.get(key)
            is_free = (
                manifest_record is not None
                and manifest_record.get("free_or_purchased") == "free"
            )
            if manifest_record is None:
                if (
                    document.get("requires_paid_recovery") is not True
                    or document.get("availability_status") != "unavailable"
                ):
                    raise ZeroCostSuccessorError(
                        "unacquired successor counter document is not an authenticated "
                        f"paid-recovery gap: {key}"
                    )
            elif is_free and (
                document.get("requires_paid_recovery") is True
                or document.get("availability_status") == "unavailable"
            ):
                raise ZeroCostSuccessorError(
                    f"free successor counter document is marked unavailable: {key}"
                )
            if role in _OPTIONAL_COUNTER_ROLES:
                continue
            if role not in _REQUIRED_COUNTER_ROLES:
                raise ZeroCostSuccessorError(
                    f"unsupported successor counter document role: {role}"
                )
            required_count += 1
            if is_free:
                free_required_count += 1
            else:
                missing_required_count += 1
        if required_count != free_required_count + missing_required_count:
            raise ZeroCostSuccessorError(
                "successor document counters do not partition required rows: "
                f"{candidate_id}"
            )
        derived = {
            "required_document_count": required_count,
            "free_required_document_count": free_required_count,
            "missing_required_document_count": missing_required_count,
        }
        if validate_stored and any(
            record.get(field) != value for field, value in derived.items()
        ):
            raise ZeroCostSuccessorError(
                f"successor selection document counters differ: {candidate_id}"
            )
        normalized.append({**record, **derived})
        total_required += required_count
        total_free_required += free_required_count
        total_missing_required += missing_required_count

    extra_manifest_keys = set(manifest) - selected_keys
    if extra_manifest_keys:
        first = min(extra_manifest_keys)
        raise ZeroCostSuccessorError(
            f"successor counter manifest document is absent from selection: {first}"
        )
    if total_required != total_free_required + total_missing_required:
        raise ZeroCostSuccessorError(
            "successor aggregate document counters do not partition required rows"
        )
    return (
        tuple(normalized),
        SuccessorCounterTotals(
            required_document_count=total_required,
            free_required_document_count=total_free_required,
            missing_required_document_count=total_missing_required,
            selected_document_count=len(selected_keys),
            manifest_document_count=len(manifest),
            free_manifest_document_count=sum(
                record.get("free_or_purchased") == "free"
                for record in manifest.values()
            ),
        ),
    )


def _require_parent_scoped_document_candidate(
    document: Mapping[str, Any],
    *,
    candidate_id: str,
    label: str,
) -> None:
    if "candidate_id" not in document:
        return
    if _required_text(document, "candidate_id") != candidate_id:
        raise ZeroCostSuccessorError(
            f"{label} document candidate differs: {candidate_id}"
        )


def _require_zero_cost_clearance_policy(
    row: Mapping[str, Any], *, key: tuple[str, str]
) -> None:
    """Accept canonical clearance or finalizer-authenticated model clearance."""

    if row.get("clearance_basis") != "authenticated_model_exception_review":
        try:
            require_clearance_policy(row, key=key, label="zero-cost successor")
        except DisclosureClearanceError as exc:
            raise ZeroCostSuccessorError(str(exc)) from exc
        return
    reviewer_id = row.get("reviewer_id")
    routing_plan_sha256 = row.get("routing_plan_sha256")
    evidence = row.get("restriction_evidence")
    if (
        not isinstance(reviewer_id, str)
        or not reviewer_id
        or row.get("controlled_store_provenance")
        != "private-store://disclosure/model-review"
        or row.get("reviewed_at") is not None
        or not isinstance(routing_plan_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", routing_plan_sha256) is None
        or not isinstance(evidence, list)
        or not evidence
        or any(
            not isinstance(item, str) or not item
            for item in cast(list[object], evidence)
        )
    ):
        raise ZeroCostSuccessorError(
            f"authenticated model clearance provenance is invalid: {key}"
        )


def _require_eligible_selection(
    selection: Mapping[str, Any], *, candidate_id: str
) -> None:
    if (
        selection.get("selected") is not True
        or selection.get("exclusion_reasons") != []
    ):
        raise ZeroCostSuccessorError(
            f"candidate is not screen-eligible: {candidate_id}"
        )
    raw_date = _required_text(selection, "decision_date")
    try:
        decision_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ZeroCostSuccessorError(f"invalid decision date: {candidate_id}") from exc
    if (
        decision_date.isoformat() != raw_date
        or decision_date < CYCLE_1_ELIGIBILITY_ANCHOR
    ):
        raise ZeroCostSuccessorError(
            f"candidate predates eligibility anchor: {candidate_id}"
        )


def _reject_positive_restriction(
    record: Mapping[str, Any], *, candidate_id: str
) -> None:
    if (
        record.get("is_sealed") is True
        or record.get("is_private") is True
        or record.get("restriction_status")
        in {"sealed", "private", "restricted", "under_seal"}
        or record.get("redaction_or_seal_status")
        in {"sealed", "private", "restricted", "under_seal"}
    ):
        raise ZeroCostSuccessorError(
            f"candidate has positive restriction evidence: {candidate_id}"
        )


def _candidate_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[str, JsonRecord]:
    output: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _required_text(record, "candidate_id")
        if candidate_id in output:
            raise ZeroCostSuccessorError(f"duplicate {label} candidate: {candidate_id}")
        output[candidate_id] = dict(record)
    return output


def _document_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], JsonRecord]:
    output: dict[tuple[str, str], JsonRecord] = {}
    for record in records:
        key = (
            _required_text(record, "candidate_id"),
            _required_text(record, "source_document_id"),
        )
        if key in output:
            raise ZeroCostSuccessorError(f"duplicate {label} document: {key}")
        output[key] = dict(record)
    return output


def _documents(record: Mapping[str, Any], label: str) -> tuple[Mapping[str, Any], ...]:
    raw = record.get("documents")
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(item, Mapping) for item in cast(list[object], raw))
    ):
        raise ZeroCostSuccessorError(f"{label} documents are missing")
    return tuple(cast(list[Mapping[str, Any]], raw))


def _mapping_sequence(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in cast(list[object], value)
    ):
        raise ZeroCostSuccessorError(f"{label} must be a JSON list")
    return tuple(cast(list[Mapping[str, object]], value))


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ZeroCostSuccessorError(f"{field} must be a non-empty string")
    return value


def _positive_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if type(value) is not int or value < 1:
        raise ZeroCostSuccessorError(f"{field} must be a positive integer")
    return value


def _digest(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
    ):
        raise ZeroCostSuccessorError(f"{field} must be a sha256 digest")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ZeroCostSuccessorError(f"{field} must be a sha256 digest")
    return value


def _sha256_hex(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ZeroCostSuccessorError(f"{field} must be a sha256 digest")
    normalized = value.removeprefix("sha256:")
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ZeroCostSuccessorError(f"{field} must be a sha256 digest")
    return normalized


def _prefixed_sha256(value: object, field: str) -> str:
    return "sha256:" + _sha256_hex(value, field)


def _money(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ZeroCostSuccessorError(f"{label} must be canonical USD")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ZeroCostSuccessorError(f"{label} must be canonical USD") from exc
    if parsed < 0 or f"{parsed:.2f}" != value:
        raise ZeroCostSuccessorError(f"{label} must be canonical USD")
    return value


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        canonical_json_bytes(
            record,
            error_type=ZeroCostSuccessorError,
            error_message="successor artifact is not canonical JSON",
        )
        for record in records
    )


def _canonical_sha256(value: object) -> str:
    return _bytes_sha256(
        canonical_json_bytes(
            value,
            error_type=ZeroCostSuccessorError,
            error_message="successor source is not canonical JSON",
        )
    )


def _bytes_sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()

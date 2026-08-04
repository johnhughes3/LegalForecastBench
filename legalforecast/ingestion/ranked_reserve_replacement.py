"""Provider-free continuation from a frozen target cohort's ranked reserve.

The planner consumes only caller-authenticated bytes and a verified purchase
journal.  It does not read files, contact a provider, purchase documents, or
authorize evaluation, freeze, or dispatch.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseJournal
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.selection.exclusion_ledger import ExclusionStage

JsonRecord = dict[str, Any]

TERMINAL_EXCLUSION_SCHEMA_VERSION = "legalforecast.ranked_reserve_terminal_exclusion.v1"
REPLACEMENT_EVENT_SCHEMA_VERSION = "legalforecast.ranked_reserve_replacement_event.v1"
RESULT_SCHEMA_VERSION = "legalforecast.ranked_reserve_replacement_result.v1"
_PROJECTION_SCHEMA_VERSION = "legalforecast.target_cohort_projection.v1"
_RESERVE_SCHEMA_VERSION = "legalforecast.target_cohort_ranked_reserve.v1"
_FROZEN_SELECTED_COUNT = 100
_FROZEN_RESERVE_COUNT = 5
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_TERMINAL_SOURCE_STAGE_TO_EXCLUSION_STAGE = {
    "parse-documents": ExclusionStage.EXTRACTION,
    "llm-unitize": ExclusionStage.UNITIZATION,
    "llm-review-stage-a": ExclusionStage.UNITIZATION,
    "apply-unitization-review": ExclusionStage.UNITIZATION,
    "llm-label": ExclusionStage.LABELING,
    "apply-lawyer-review": ExclusionStage.LABELING,
}
_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "reason",
        "source_stage",
        "source_artifact_sha256",
        "source_record_sha256",
        "terminal",
        "retryable",
    }
)


class RankedReserveReplacementError(ValueError):
    """Raised when frozen lineage, terminality, or budget cannot be proven."""


@dataclass(frozen=True, slots=True)
class RankedReserveReplacementPlan:
    """Authenticated successor projection with no execution authority."""

    projection_sha256: str
    cycle_id: str
    purchase_policy_sha256: str
    purchase_journal_state_sha256: str
    hard_cap: Decimal
    terminal_exclusions_sha256: str
    active_selection: tuple[JsonRecord, ...]
    replacement_selection: tuple[JsonRecord, ...]
    successor_exclusions: tuple[JsonRecord, ...]
    replacement_plan: MissingCoreBudgetPlan
    committed_spend: Decimal
    reserved_replacement_spend: Decimal
    remaining_headroom: Decimal
    successor_approval_required: bool
    replacement_event_record_sha256s: tuple[str, ...]
    tranche_event_record_sha256s: tuple[str, ...]

    @property
    def active_candidate_ids(self) -> tuple[str, ...]:
        return tuple(
            _candidate_id(row, "active selection") for row in self.active_selection
        )

    @property
    def committed_spend_usd(self) -> str:
        return _money(self.committed_spend)

    @property
    def reserved_replacement_spend_usd(self) -> str:
        return _money(self.reserved_replacement_spend)

    @property
    def remaining_headroom_usd(self) -> str:
        return _money(self.remaining_headroom)

    @property
    def paid_activity_requested(self) -> bool:
        return False

    @property
    def paid_activity_executed(self) -> bool:
        return False


def plan_ranked_reserve_replacements(
    *,
    projection: Mapping[str, object],
    selected_bytes: bytes,
    reserve_bytes: bytes,
    source_pool_bytes: bytes,
    original_exclusions_bytes: bytes,
    terminal_exclusions_bytes: bytes,
    expected_terminal_exclusions_sha256: str,
    purchase_journal: CaseDevPurchaseJournal,
) -> RankedReserveReplacementPlan:
    """Plan deterministic reserve promotions from explicit terminal evidence.

    ``projection`` and its artifact bytes must first have passed the complete
    target-cohort projection replay at the caller boundary.  This function
    independently binds the exact bytes it uses and fails before journal
    mutation when any invariant is unproven.
    """

    projection_sha256 = _digest(
        projection.get("projection_sha256"), "projection_sha256"
    )
    if projection.get("schema_version") != _PROJECTION_SCHEMA_VERSION:
        raise RankedReserveReplacementError("unsupported target projection schema")
    commitments = _mapping(projection.get("output_commitments"), "output commitments")
    _require_byte_commitment(
        commitments, "target-cohort-selection.jsonl", selected_bytes, "selection bytes"
    )
    _require_byte_commitment(
        commitments,
        "target-cohort-ranked-reserve.jsonl",
        reserve_bytes,
        "reserve bytes",
    )
    _require_byte_commitment(
        commitments,
        "target-cohort-exclusions.jsonl",
        original_exclusions_bytes,
        "original exclusion bytes",
    )
    input_commitments = _mapping(
        projection.get("input_commitments"), "input commitments"
    )
    source_commitments = [
        value
        for name, value in input_commitments.items()
        if str(name).endswith("/public-packet-selection-reconciled.jsonl")
    ]
    if len(source_commitments) != 1 or source_commitments[0] != _bytes_sha256(
        source_pool_bytes
    ):
        raise RankedReserveReplacementError(
            "source-pool bytes do not match the unique frozen input commitment"
        )

    selected = _jsonl_records(selected_bytes, "selected cohort")
    reserve = _jsonl_records(reserve_bytes, "ranked reserve")
    source_pool = _jsonl_records(source_pool_bytes, "source pool")
    original_exclusions = _jsonl_records(
        original_exclusions_bytes, "original exclusions"
    )
    selected_ids = _unique_ids(selected, "selected cohort")
    reserve_ids = _unique_ids(reserve, "ranked reserve")
    source_ids = _unique_ids(source_pool, "source pool")
    excluded_ids = _unique_ids(original_exclusions, "original exclusions")
    if (
        len(selected_ids) != _FROZEN_SELECTED_COUNT
        or len(reserve_ids) != _FROZEN_RESERVE_COUNT
    ):
        raise RankedReserveReplacementError(
            "continuation requires the exact frozen 100+5 candidate pool"
        )
    if set(selected_ids) & set(reserve_ids):
        raise RankedReserveReplacementError("selected cohort and reserve overlap")
    if not set(selected_ids) | set(reserve_ids) <= set(source_ids):
        raise RankedReserveReplacementError(
            "selected cohort or reserve is absent from the frozen source pool"
        )
    if set(selected_ids) & set(excluded_ids):
        raise RankedReserveReplacementError(
            "selected cohort overlaps original exclusions"
        )
    if set(selected_ids) | set(excluded_ids) != set(source_ids):
        raise RankedReserveReplacementError(
            "selected cohort and original exclusions do not reconcile the resolved pool"
        )
    _require_count(projection, "selected_case_count", len(selected))
    _require_count(projection, "ranked_reserve_case_count", len(reserve))
    _require_count(projection, "resolved_pool_case_count", len(source_pool))
    _require_count(
        projection, "post_clearance_case_count", len(selected) + len(reserve)
    )
    if projection.get("selected_candidate_ids_sha256") != _canonical_sha256(
        list(selected_ids)
    ):
        raise RankedReserveReplacementError("selected candidate commitment mismatch")
    if projection.get("ranked_reserve_candidate_ids_sha256") != _canonical_sha256(
        list(reserve_ids)
    ):
        raise RankedReserveReplacementError("reserve candidate commitment mismatch")
    if projection.get("ranked_reserve_sha256") != _canonical_sha256(reserve):
        raise RankedReserveReplacementError("reserve record commitment mismatch")
    reserve_by_id = _verify_reserve(reserve, selected_count=len(selected))
    source_by_id = dict(zip(source_ids, source_pool, strict=True))

    terminal_digest = _digest(
        expected_terminal_exclusions_sha256,
        "expected_terminal_exclusions_sha256",
    )
    if _bytes_sha256(terminal_exclusions_bytes) != terminal_digest:
        raise RankedReserveReplacementError(
            "terminal exclusion bytes do not match the external commitment"
        )
    terminal_records = _jsonl_records(terminal_exclusions_bytes, "terminal exclusions")

    policy = purchase_journal.policy
    for candidate_id, reserve_record in reserve_by_id.items():
        document_count = cast(int, reserve_record["missing_core_document_count"])
        estimated_cost = _money_decimal(
            reserve_record["estimated_cost_usd"], "reserve cost"
        )
        if (
            estimated_cost != policy.per_document_reservation_usd * document_count
            or estimated_cost > policy.max_per_case_usd
        ):
            raise RankedReserveReplacementError(
                f"frozen reserve cost conflicts with purchase policy: {candidate_id}"
            )
    committed = _money_decimal(
        purchase_journal.committed_amount_usd, "committed purchase spend"
    )
    operation_by_document: dict[str, Mapping[str, Any]] = {}
    for operation in purchase_journal.operation_records():
        document_id = _required_string(operation, "source_document_id", "operation")
        if document_id in operation_by_document:
            raise RankedReserveReplacementError(
                "purchase journal repeats a document operation"
            )
        operation_by_document[document_id] = operation
    purchase_journal_state_sha256 = "sha256:" + purchase_journal.purchase_state_sha256()
    prior_events = _replacement_events(
        purchase_journal.replacement_events(),
        projection_sha256=projection_sha256,
        reserve_by_id=reserve_by_id,
    )
    active = [dict(row) for row in selected]
    promoted_by_displaced: dict[str, str] = {}
    all_terminal_by_id: dict[str, JsonRecord] = {}
    used_reserves: set[str] = set()
    event_hashes: list[str] = []
    reserved = Decimal("0.00")
    for event in prior_events:
        displaced_id = cast(str, event["displaced_candidate_id"])
        promoted_id = cast(str, event["promoted_candidate_id"])
        _apply_promotion(
            active,
            displaced_id=displaced_id,
            promoted_record=source_by_id[promoted_id],
        )
        promoted_by_displaced[displaced_id] = promoted_id
        all_terminal_by_id[displaced_id] = {
            "candidate_id": displaced_id,
            "reason": event["terminal_reason"],
            "source_stage": event["terminal_source_stage"],
            "source_artifact_sha256": event["terminal_source_artifact_sha256"],
            "source_record_sha256": event["terminal_source_record_sha256"],
        }
        used_reserves.add(promoted_id)
        event_documents = cast(list[str], event["purchase_document_ids"])
        for document_id in event_documents:
            operation = operation_by_document.get(document_id)
            if operation is None or not _operation_commits_spend(operation):
                reserved += policy.per_document_reservation_usd
        event_hashes.append(_digest(event.get("record_sha256"), "event record hash"))

    available_before_new = policy.hard_cap_usd - committed - reserved
    if available_before_new < 0:
        raise RankedReserveReplacementError(
            "durable replacement reservations exceed the purchase-policy hard cap"
        )
    terminal_by_id = _verify_terminal_records(
        terminal_records,
        {
            *(_candidate_id(record, "active selection") for record in active),
            *promoted_by_displaced,
        },
    )
    for displaced_id in terminal_by_id.keys() & promoted_by_displaced.keys():
        terminal = terminal_by_id[displaced_id]
        prior = all_terminal_by_id[displaced_id]
        if any(
            terminal[field] != prior[field]
            for field in (
                "reason",
                "source_stage",
                "source_artifact_sha256",
                "source_record_sha256",
            )
        ):
            raise RankedReserveReplacementError(
                "terminal exclusion replay conflicts with the durable event"
            )
    remaining = [
        candidate_id
        for candidate_id in reserve_ids
        if candidate_id not in used_reserves
    ]
    new_events: list[tuple[str, JsonRecord]] = []
    newly_promoted_ids: list[str] = []
    for displaced_id in sorted(terminal_by_id):
        if displaced_id in promoted_by_displaced:
            continue
        terminal = terminal_by_id[displaced_id]
        if not remaining:
            raise RankedReserveReplacementError(
                "ranked reserve is exhausted before all terminal exclusions "
                "are replaced"
            )
        promoted_id = remaining.pop(0)
        reserve_record = reserve_by_id[promoted_id]
        purchase_document_ids = cast(list[str], reserve_record["purchase_document_ids"])
        if any(
            document_id in operation_by_document
            for document_id in purchase_document_ids
        ):
            raise RankedReserveReplacementError(
                "unselected reserve already has a purchase-journal operation"
            )
        cost = _money_decimal(reserve_record["estimated_cost_usd"], "reserve cost")
        projected_total = committed + reserved + cost
        if projected_total > policy.hard_cap_usd:
            raise RankedReserveReplacementError(
                "next ranked reserve exceeds remaining purchase-policy headroom"
            )
        payload: JsonRecord = {
            "schema_version": REPLACEMENT_EVENT_SCHEMA_VERSION,
            "projection_sha256": projection_sha256,
            "displaced_candidate_id": displaced_id,
            "promoted_candidate_id": promoted_id,
            "reserve_rank": reserve_record["reserve_rank"],
            "estimated_cost_usd": _money(cost),
            "purchase_document_ids": list(purchase_document_ids),
            "terminal_reason": terminal["reason"],
            "terminal_source_stage": terminal["source_stage"],
            "terminal_source_artifact_sha256": terminal["source_artifact_sha256"],
            "terminal_source_record_sha256": terminal["source_record_sha256"],
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
        event_key = _canonical_sha256([projection_sha256, displaced_id])
        new_events.append((event_key, payload))
        _apply_promotion(
            active,
            displaced_id=displaced_id,
            promoted_record=source_by_id[promoted_id],
        )
        promoted_by_displaced[displaced_id] = promoted_id
        all_terminal_by_id[displaced_id] = terminal
        used_reserves.add(promoted_id)
        newly_promoted_ids.append(promoted_id)
        reserved += cost

    replacement_selection = tuple(
        dict(source_by_id[candidate_id]) for candidate_id in newly_promoted_ids
    )
    successor_exclusions = _successor_exclusions(
        original_exclusions,
        terminal_by_id=all_terminal_by_id,
        promoted_ids=used_reserves,
        source_by_id=source_by_id,
    )
    _require_successor_partition(
        active,
        successor_exclusions,
        expected_source_ids=set(source_ids),
        expected_selected_count=len(selected),
    )
    case_plans = tuple(
        _case_plan(reserve_by_id[candidate_id]) for candidate_id in newly_promoted_ids
    )
    max_documents = max(
        (plan.missing_core_document_count for plan in case_plans), default=1
    )
    replacement_plan = MissingCoreBudgetPlan(
        case_plans=case_plans,
        cost_per_document=policy.per_document_reservation_usd,
        max_projected_budget=available_before_new,
        max_missing_core_documents_per_case=max_documents,
        dry_run=False,
        target_case_count=len(case_plans),
    )
    remaining_headroom = policy.hard_cap_usd - committed - reserved
    if remaining_headroom < 0:
        raise RankedReserveReplacementError("replacement reservations exceed hard cap")

    # All validation and budget decisions precede the first journal mutation.
    tranche_event_hashes: list[str] = []
    for event_key, payload in new_events:
        stored = purchase_journal.append_replacement_event(event_key, payload)
        event_hash = _digest(stored.get("record_sha256"), "event record hash")
        event_hashes.append(event_hash)
        tranche_event_hashes.append(event_hash)

    return RankedReserveReplacementPlan(
        projection_sha256=projection_sha256,
        cycle_id=policy.cycle_id,
        purchase_policy_sha256="sha256:" + policy.policy_sha256,
        purchase_journal_state_sha256=purchase_journal_state_sha256,
        hard_cap=policy.hard_cap_usd,
        terminal_exclusions_sha256=terminal_digest,
        active_selection=tuple(active),
        replacement_selection=replacement_selection,
        successor_exclusions=successor_exclusions,
        replacement_plan=replacement_plan,
        committed_spend=committed,
        reserved_replacement_spend=reserved,
        remaining_headroom=remaining_headroom,
        successor_approval_required=any(
            plan.purchase_document_ids for plan in case_plans
        ),
        replacement_event_record_sha256s=tuple(event_hashes),
        tranche_event_record_sha256s=tuple(tranche_event_hashes),
    )


def bind_ranked_reserve_outputs(
    plan: RankedReserveReplacementPlan,
    *,
    active_selection_bytes: bytes,
    replacement_selection_bytes: bytes,
    successor_exclusions_bytes: bytes,
    replacement_budget_plan_bytes: bytes,
) -> JsonRecord:
    """Bind exact serialized outputs while granting no downstream authority."""

    if _jsonl_records(active_selection_bytes, "active selection output") != list(
        plan.active_selection
    ):
        raise RankedReserveReplacementError(
            "active selection output differs from the planned records"
        )
    if _jsonl_records(
        replacement_selection_bytes, "replacement selection output"
    ) != list(plan.replacement_selection):
        raise RankedReserveReplacementError(
            "replacement selection output differs from the planned records"
        )
    if _jsonl_records(
        successor_exclusions_bytes, "successor exclusions output"
    ) != list(plan.successor_exclusions):
        raise RankedReserveReplacementError(
            "successor exclusions output differs from the planned records"
        )
    try:
        budget_value: object = json.loads(replacement_budget_plan_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RankedReserveReplacementError(
            "replacement budget-plan output is invalid JSON"
        ) from exc
    if budget_value != plan.replacement_plan.to_record():
        raise RankedReserveReplacementError(
            "replacement budget-plan output differs from the planned record"
        )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "projection_sha256": plan.projection_sha256,
        "cycle_id": plan.cycle_id,
        "purchase_policy_sha256": plan.purchase_policy_sha256,
        "purchase_journal_state_sha256": plan.purchase_journal_state_sha256,
        "hard_cap_usd": _money(plan.hard_cap),
        "terminal_exclusions_sha256": plan.terminal_exclusions_sha256,
        "active_selection_sha256": _bytes_sha256(active_selection_bytes),
        "replacement_selection_sha256": _bytes_sha256(replacement_selection_bytes),
        "successor_exclusions_sha256": _bytes_sha256(successor_exclusions_bytes),
        "replacement_budget_plan_sha256": _bytes_sha256(replacement_budget_plan_bytes),
        "active_case_count": len(plan.active_selection),
        "replacement_case_count": len(plan.replacement_selection),
        "committed_spend_usd": plan.committed_spend_usd,
        "reserved_replacement_spend_usd": plan.reserved_replacement_spend_usd,
        "remaining_headroom_usd": plan.remaining_headroom_usd,
        "successor_approval_required": plan.successor_approval_required,
        "replacement_event_record_sha256s": list(plan.replacement_event_record_sha256s),
        "tranche_event_record_sha256s": list(plan.tranche_event_record_sha256s),
        "provider_activity_requested": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }


def _replacement_events(
    records: Sequence[Mapping[str, Any]],
    *,
    projection_sha256: str,
    reserve_by_id: Mapping[str, JsonRecord],
) -> tuple[Mapping[str, Any], ...]:
    relevant: list[Mapping[str, Any]] = []
    displaced: set[str] = set()
    promoted: set[str] = set()
    for record in records:
        if record.get("schema_version") != REPLACEMENT_EVENT_SCHEMA_VERSION:
            raise RankedReserveReplacementError(
                "purchase journal contains incompatible replacement history"
            )
        if record.get("projection_sha256") != projection_sha256:
            raise RankedReserveReplacementError(
                "purchase journal replacement history targets another projection"
            )
        displaced_id = _required_string(record, "displaced_candidate_id", "event")
        promoted_id = _required_string(record, "promoted_candidate_id", "event")
        if (
            promoted_id not in reserve_by_id
            or displaced_id in displaced
            or promoted_id in promoted
        ):
            raise RankedReserveReplacementError(
                "durable replacement event conflicts with the frozen pool"
            )
        reserve_record = reserve_by_id[promoted_id]
        if (
            record.get("reserve_rank") != reserve_record["reserve_rank"]
            or record.get("estimated_cost_usd") != reserve_record["estimated_cost_usd"]
            or record.get("purchase_document_ids")
            != reserve_record["purchase_document_ids"]
            or record.get("paid_activity_requested") is not False
            or record.get("paid_activity_executed") is not False
        ):
            raise RankedReserveReplacementError(
                "durable replacement event differs from the frozen reserve"
            )
        displaced.add(displaced_id)
        promoted.add(promoted_id)
        relevant.append(record)
    ordered_reserve_ids = list(reserve_by_id)
    if [record["promoted_candidate_id"] for record in relevant] != ordered_reserve_ids[
        : len(relevant)
    ]:
        raise RankedReserveReplacementError(
            "durable replacement events did not consume the reserve in rank order"
        )
    return tuple(relevant)


def _verify_terminal_records(
    records: Sequence[JsonRecord], selected_ids: set[str]
) -> dict[str, JsonRecord]:
    result: dict[str, JsonRecord] = {}
    for record in records:
        if sorted(record) != sorted(_TERMINAL_FIELDS):
            raise RankedReserveReplacementError(
                "terminal exclusion record has an open or incomplete schema"
            )
        candidate_id = _candidate_id(record, "terminal exclusion")
        if (
            record.get("schema_version") != TERMINAL_EXCLUSION_SCHEMA_VERSION
            or record.get("terminal") is not True
            or record.get("retryable") is not False
        ):
            raise RankedReserveReplacementError(
                "reserve use requires explicit terminal nonretryable evidence"
            )
        if candidate_id not in selected_ids:
            raise RankedReserveReplacementError(
                "terminal exclusion candidate is not in the frozen selected cohort"
            )
        for name in ("reason", "source_stage"):
            _required_string(record, name, "terminal exclusion")
        for name in ("source_artifact_sha256", "source_record_sha256"):
            _digest(record.get(name), f"terminal exclusion {name}")
        if candidate_id in result:
            raise RankedReserveReplacementError(
                "terminal exclusion candidate is duplicated"
            )
        result[candidate_id] = record
    if not result:
        raise RankedReserveReplacementError("terminal exclusion evidence is empty")
    return result


def _verify_reserve(
    records: Sequence[JsonRecord], *, selected_count: int
) -> dict[str, JsonRecord]:
    result: dict[str, JsonRecord] = {}
    for index, record in enumerate(records, start=1):
        candidate_id = _candidate_id(record, "ranked reserve")
        if (
            record.get("schema_version") != _RESERVE_SCHEMA_VERSION
            or record.get("reserve_rank") != index
            or record.get("frontier_rank") != selected_count + index
        ):
            raise RankedReserveReplacementError(
                "ranked reserve order or schema is inconsistent"
            )
        document_ids = record.get("purchase_document_ids")
        roles = record.get("missing_core_roles")
        count = record.get("missing_core_document_count")
        if (
            not isinstance(document_ids, list)
            or not isinstance(roles, list)
            or not isinstance(count, int)
            or isinstance(count, bool)
        ):
            raise RankedReserveReplacementError(
                "ranked reserve document obligations are inconsistent"
            )
        raw_document_ids = cast(list[object], document_ids)
        raw_roles = cast(list[object], roles)
        if (
            not all(isinstance(value, str) and value for value in raw_document_ids)
            or len(raw_document_ids) != len(set(raw_document_ids))
            or not all(isinstance(value, str) and value for value in raw_roles)
            or count != len(raw_document_ids)
        ):
            raise RankedReserveReplacementError(
                "ranked reserve document obligations are inconsistent"
            )
        cost = _money_decimal(record.get("estimated_cost_usd"), "reserve cost")
        if cost < 0:
            raise RankedReserveReplacementError("reserve cost must be nonnegative")
        result[candidate_id] = record
    return result


def _case_plan(record: Mapping[str, Any]) -> CaseMissingCorePurchasePlan:
    document_ids = cast(list[str], record["purchase_document_ids"])
    roles = cast(list[str], record["missing_core_roles"])
    return CaseMissingCorePurchasePlan(
        candidate_id=cast(str, record["candidate_id"]),
        purchase_document_ids=tuple(document_ids),
        missing_core_document_count=cast(int, record["missing_core_document_count"]),
        estimated_cost=_money_decimal(record["estimated_cost_usd"], "reserve cost"),
        audit_only_document_count=0,
        dry_run=False,
        missing_core_roles=tuple(roles),
    )


def _successor_exclusions(
    original: Sequence[JsonRecord],
    *,
    terminal_by_id: Mapping[str, JsonRecord],
    promoted_ids: set[str],
    source_by_id: Mapping[str, JsonRecord],
) -> tuple[JsonRecord, ...]:
    records = [
        dict(record)
        for record in original
        if _candidate_id(record, "original exclusion") not in promoted_ids
    ]
    for candidate_id, terminal in terminal_by_id.items():
        source = source_by_id[candidate_id]
        source_stage = cast(str, terminal["source_stage"])
        try:
            exclusion_stage = _TERMINAL_SOURCE_STAGE_TO_EXCLUSION_STAGE[source_stage]
        except KeyError as exc:
            raise RankedReserveReplacementError(
                f"terminal exclusion source stage is unsupported: {source_stage}"
            ) from exc
        raw_documents = source.get("documents")
        documents = (
            cast(list[object], raw_documents) if isinstance(raw_documents, list) else []
        )
        source_document_ids = sorted(
            {
                cast(str, document["source_document_id"])
                for value in documents
                if isinstance(value, Mapping)
                for document in (cast(Mapping[str, object], value),)
                if isinstance(document.get("source_document_id"), str)
                and cast(str, document["source_document_id"])
            }
        )
        raw_entry_ids = source.get("source_entry_ids")
        source_entry_ids = (
            [
                value
                for value in cast(list[object], raw_entry_ids)
                if isinstance(value, str) and value
            ]
            if isinstance(raw_entry_ids, list)
            else []
        )
        records.append(
            {
                "candidate_id": candidate_id,
                "case_id": source.get("case_id", candidate_id),
                "court": source.get("court"),
                "decision_date": source.get("decision_date"),
                "notes": (
                    "Explicit terminal downstream exclusion consumed one frozen "
                    "ranked reserve candidate."
                ),
                "primary_exclusion_reason": terminal["reason"],
                "reason": terminal["reason"],
                "related_family_id": source.get("related_family_id"),
                "secondary_exclusion_reasons": [],
                "source_document_ids": source_document_ids,
                "source_entry_ids": source_entry_ids,
                "stage": exclusion_stage.value,
                "source_stage": source_stage,
                "terminal_evidence_sha256": terminal["source_record_sha256"],
            }
        )
    return tuple(records)


def _require_successor_partition(
    selection: Sequence[JsonRecord],
    exclusions: Sequence[JsonRecord],
    *,
    expected_source_ids: set[str],
    expected_selected_count: int,
) -> None:
    selected_ids = _unique_ids(selection, "successor selection")
    excluded_ids = _unique_ids(exclusions, "successor exclusions")
    if (
        len(selected_ids) != expected_selected_count
        or set(selected_ids) & set(excluded_ids)
        or set(selected_ids) | set(excluded_ids) != expected_source_ids
    ):
        raise RankedReserveReplacementError(
            "successor records do not provide selected XOR excluded resolution"
        )


def _apply_promotion(
    selection: list[JsonRecord],
    *,
    displaced_id: str,
    promoted_record: Mapping[str, Any],
) -> None:
    positions = [
        index
        for index, record in enumerate(selection)
        if _candidate_id(record, "active selection") == displaced_id
    ]
    if len(positions) != 1:
        raise RankedReserveReplacementError(
            "displaced candidate is not uniquely active in the selected cohort"
        )
    selection[positions[0]] = dict(promoted_record)


def _jsonl_records(payload: bytes, source: str) -> list[JsonRecord]:
    if payload and not payload.endswith(b"\n"):
        raise RankedReserveReplacementError(f"{source} lacks a terminal newline")
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RankedReserveReplacementError(
                f"{source} line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise RankedReserveReplacementError(
                f"{source} line {line_number} must be an object"
            )
        records.append(cast(JsonRecord, value))
    return records


def _unique_ids(records: Sequence[JsonRecord], source: str) -> tuple[str, ...]:
    result = tuple(_candidate_id(record, source) for record in records)
    if len(set(result)) != len(result):
        raise RankedReserveReplacementError(f"{source} contains duplicate candidates")
    return result


def _candidate_id(record: Mapping[str, Any], source: str) -> str:
    return _required_string(record, "candidate_id", source)


def _required_string(record: Mapping[str, Any], name: str, source: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RankedReserveReplacementError(
            f"{source} {name} must be a canonical non-empty string"
        )
    return value


def _mapping(value: object, source: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RankedReserveReplacementError(f"{source} must be an object")
    return cast(Mapping[str, object], value)


def _require_count(projection: Mapping[str, object], name: str, actual: int) -> None:
    if projection.get(name) != actual:
        raise RankedReserveReplacementError(f"projection {name} is inconsistent")


def _require_byte_commitment(
    commitments: Mapping[str, object],
    name: str,
    payload: bytes,
    source: str,
) -> None:
    if commitments.get(name) != _bytes_sha256(payload):
        raise RankedReserveReplacementError(
            f"{source} do not match the frozen projection commitment"
        )


def _money_decimal(value: object, source: str) -> Decimal:
    if isinstance(value, bool):
        raise RankedReserveReplacementError(f"{source} must be decimal money")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RankedReserveReplacementError(f"{source} must be decimal money") from exc
    try:
        uses_finite_cents = amount.is_finite() and amount == amount.quantize(
            Decimal("0.01")
        )
    except InvalidOperation as exc:
        raise RankedReserveReplacementError(
            f"{source} must use finite cents"
        ) from exc
    if not uses_finite_cents:
        raise RankedReserveReplacementError(f"{source} must use finite cents")
    return amount


def _operation_commits_spend(operation: Mapping[str, Any]) -> bool:
    """Mirror the canonical journal's committed-amount status treatment."""

    status = operation.get("status")
    return (
        status == "confirmed"
        or status in {"submitted", "queued", "unknown"}
        or (
            status == "failed"
            and operation.get("response") is not None
            and operation.get("reconciliation") is None
        )
    )


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _digest(value: object, source: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RankedReserveReplacementError(f"{source} must be a sha256 digest")
    return value


def _bytes_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return _bytes_sha256(payload)

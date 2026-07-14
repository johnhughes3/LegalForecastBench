"""Provider-free extension of a frozen target-100 cohort to target 150.

The extension is deliberately artifact-oriented. It verifies the bytes emitted by
the original projection, retains those bytes as exact prefixes, and ranks only
the eligible candidates omitted from that projection. No function in this module
performs I/O or has a provider client dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
    plan_missing_core_document_budget,
)
from legalforecast.ingestion.target_cohort_projection import (
    TargetCohortProjectionError,
    project_target_cohort,
    restriction_evidence_from_case_relevance,
)

JsonRecord = dict[str, Any]

BASE_CASE_COUNT = 100
TARGET_CASE_COUNT = 150
SCHEMA_VERSION = "legalforecast.retained_cohort_extension.v1"
BASE_PROJECTION_ARTIFACT_NAMES = (
    "target-cohort-selection.jsonl",
    "case-relevance.jsonl",
    "document-downloads-merged.jsonl",
    "disclosure-clearance.jsonl",
    "restriction-evidence.jsonl",
    "core-filter-results.jsonl",
    "target-cohort-exclusions.jsonl",
    "free-document-downloads.jsonl",
    "purchased-document-downloads.jsonl",
    "missing-core-budget-plan.json",
    "target-cohort-projection.json",
)

_BASE_JSONL_NAMES = (
    "target-cohort-selection.jsonl",
    "case-relevance.jsonl",
    "document-downloads-merged.jsonl",
    "disclosure-clearance.jsonl",
    "restriction-evidence.jsonl",
    "core-filter-results.jsonl",
    "free-document-downloads.jsonl",
    "purchased-document-downloads.jsonl",
)
_BASE_REQUIRED_NAMES = frozenset(BASE_PROJECTION_ARTIFACT_NAMES)
_FULL_REQUIRED_NAMES = frozenset(
    {
        "selection.jsonl",
        "case-relevance.jsonl",
        "document-downloads-merged.jsonl",
        "disclosure-clearance.jsonl",
    }
)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class RetainedCohortExtensionError(ValueError):
    """Raised when retained-cohort lineage or budget safety cannot be proven."""


@dataclass(frozen=True, slots=True)
class PurchaseObligationSnapshot:
    """Fail-closed accounting derived from one verified canonical journal."""

    purchase_policy_sha256: str
    purchase_journal_state_sha256: str
    canonical_ledger_path: str
    opening_obligation: Decimal
    confirmed_obligation: Decimal
    reserved_obligation: Decimal
    unknown_obligation: Decimal
    write_off_obligation: Decimal

    @property
    def total(self) -> Decimal:
        return sum(
            (
                self.opening_obligation,
                self.confirmed_obligation,
                self.reserved_obligation,
                self.unknown_obligation,
                self.write_off_obligation,
            ),
            Decimal("0.00"),
        )

    def budget_record(self) -> JsonRecord:
        return {
            "opening_obligation_usd": _format_money(self.opening_obligation),
            "confirmed_obligation_usd": _format_money(self.confirmed_obligation),
            "reserved_obligation_usd": _format_money(self.reserved_obligation),
            "unknown_obligation_usd": _format_money(self.unknown_obligation),
            "write_off_obligation_usd": _format_money(self.write_off_obligation),
        }


@dataclass(frozen=True, slots=True)
class AuthenticatedPoolLineage:
    """Verified preparation, frontier, and clearance identities for the pool."""

    preparation_summary_sha256: str
    preparation_config_sha256: str
    snapshot_manifest_sha256: str
    full_candidate_frontier_sha256: str
    frontier_policy_sha256: str
    frontier_run_card_sha256: str
    clearance_run_card_sha256: str
    clearance_reviews_sha256: str
    clearance_review_receipt_sha256: str
    restriction_evidence_sha256: str

    def source_record(self) -> JsonRecord:
        record = {
            "preparation_summary_sha256": self.preparation_summary_sha256,
            "preparation_config_sha256": self.preparation_config_sha256,
            "snapshot_manifest_sha256": self.snapshot_manifest_sha256,
            "full_candidate_frontier_sha256": self.full_candidate_frontier_sha256,
            "frontier_policy_sha256": self.frontier_policy_sha256,
            "frontier_run_card_sha256": self.frontier_run_card_sha256,
            "clearance_run_card_sha256": self.clearance_run_card_sha256,
            "clearance_reviews_sha256": self.clearance_reviews_sha256,
            "clearance_review_receipt_sha256": (self.clearance_review_receipt_sha256),
            "restriction_evidence_sha256": self.restriction_evidence_sha256,
        }
        for name, digest in record.items():
            _sha(digest, name)
        return record


def purchase_obligation_snapshot(
    *,
    policy: CaseDevPurchasePolicy,
    journal: CaseDevPurchaseJournal,
    cohort_policy_artifact: Mapping[str, Any],
) -> PurchaseObligationSnapshot:
    """Derive every committed category from canonical policy and journal state."""

    try:
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort_policy_artifact)
    except (CaseDevPurchasePolicyError, ValueError) as exc:
        raise RetainedCohortExtensionError(str(exc)) from exc
    if journal.policy.policy_sha256 != policy.policy_sha256:
        raise RetainedCohortExtensionError(
            "purchase journal is bound to a different purchase policy"
        )
    categories = {
        "confirmed": Decimal("0.00"),
        "reserved": Decimal("0.00"),
        "unknown": Decimal("0.00"),
        "write_off": Decimal("0.00"),
    }
    for row in journal.operation_records():
        status = row.get("status")
        reservation = _money(str(row.get("reservation_usd")), "reservation_usd")
        actual_raw = row.get("actual_usd")
        actual = (
            Decimal("0.00")
            if actual_raw is None
            else _money(str(actual_raw), "actual_usd")
        )
        committed = max(reservation, actual)
        reconciliation = row.get("reconciliation")
        typed_reconciliation = (
            cast(Mapping[str, object], reconciliation)
            if isinstance(reconciliation, Mapping)
            else None
        )
        disposition = (
            typed_reconciliation.get("disposition")
            if typed_reconciliation is not None
            else None
        )
        if disposition == "write_off":
            categories["write_off"] += committed
        elif status == "confirmed":
            categories["confirmed"] += actual if actual_raw is not None else reservation
        elif status in {"submitted", "queued"}:
            categories["reserved"] += committed
        elif status == "unknown":
            categories["unknown"] += committed
        elif status == "failed":
            if row.get("response") is not None and reconciliation is None:
                categories["reserved"] += committed
        elif status != "planned":
            raise RetainedCohortExtensionError(
                f"purchase journal contains unsupported status: {status!r}"
            )
    snapshot = PurchaseObligationSnapshot(
        purchase_policy_sha256="sha256:" + policy.policy_sha256,
        purchase_journal_state_sha256="sha256:" + journal.purchase_state_sha256(),
        canonical_ledger_path=str(policy.canonical_ledger_path),
        opening_obligation=policy.opening_committed_spend_usd,
        confirmed_obligation=categories["confirmed"],
        reserved_obligation=categories["reserved"],
        unknown_obligation=categories["unknown"],
        write_off_obligation=categories["write_off"],
    )
    if _format_money(snapshot.total) != journal.committed_amount_usd:
        raise RetainedCohortExtensionError(
            "purchase journal obligation categories do not reconcile to committed state"
        )
    return snapshot


@dataclass(frozen=True, slots=True)
class RetainedCohortExtension:
    """Deterministic provider-free outputs for the retained extension."""

    base_candidate_ids: tuple[str, ...]
    incremental_candidate_ids: tuple[str, ...]
    combined_candidate_ids: tuple[str, ...]
    incremental_artifacts: Mapping[str, bytes]
    combined_artifacts: Mapping[str, bytes]
    combined_budget: JsonRecord
    extension_record: JsonRecord


def extend_target_cohort(
    *,
    base_projection_artifacts: Mapping[str, bytes],
    full_pool_artifacts: Mapping[str, bytes],
    cohort_policy_artifact: Mapping[str, Any],
    snapshot_manifest_sha256: str,
    snapshot_cycle_hash: str,
    snapshot_batch_digest: str,
    cost_per_document_usd: str,
    max_projected_budget_usd: str,
    max_missing_core_documents_per_case: int,
    purchase_obligations: PurchaseObligationSnapshot,
    authenticated_lineage: AuthenticatedPoolLineage,
) -> RetainedCohortExtension:
    """Retain an exact target-100 prefix and select 50 omitted candidates.

    Existing obligations must be derived from the verified canonical purchase
    policy and journal. They are additive and never released by this projection.
    """

    _require_exact_names(
        base_projection_artifacts, _BASE_REQUIRED_NAMES, "base projection"
    )
    _require_exact_names(full_pool_artifacts, _FULL_REQUIRED_NAMES, "full pool")
    policy_sha256, _ = _verified_policy(
        cohort_policy_artifact,
        snapshot_cycle_hash=snapshot_cycle_hash,
        max_projected_budget_usd=max_projected_budget_usd,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        cost_per_document_usd=cost_per_document_usd,
    )
    snapshot_hash = _sha(snapshot_manifest_sha256, "snapshot_manifest_sha256")
    cycle_hash = _bare_sha(snapshot_cycle_hash, "snapshot_cycle_hash")
    batch_digest = _bare_sha(snapshot_batch_digest, "snapshot_batch_digest")
    money = _money(cost_per_document_usd, "cost_per_document_usd", positive=True)
    cap = _money(max_projected_budget_usd, "max_projected_budget_usd", positive=True)
    obligations = purchase_obligations.budget_record()
    obligation_values = {
        name: _money(value, name) for name, value in obligations.items()
    }

    base = _verify_base_projection(
        base_projection_artifacts,
        cost_per_document_usd=money,
        max_projected_budget_usd=cap,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
    )
    base_summary = cast(Mapping[str, Any], base["summary"])
    if (
        base_summary.get("snapshot_manifest_sha256") != snapshot_hash
        or base_summary.get("snapshot_cycle_hash") != cycle_hash
        or base_summary.get("snapshot_batch_digest") != batch_digest
    ):
        raise RetainedCohortExtensionError(
            "base projection snapshot lineage differs from the extension inputs"
        )
    authenticated_sources = authenticated_lineage.source_record()
    for summary_field, lineage_field in (
        ("preparation_summary_sha256", "preparation_summary_sha256"),
        ("preparation_config_sha256", "preparation_config_sha256"),
        ("snapshot_manifest_sha256", "snapshot_manifest_sha256"),
        ("clearance_run_card_sha256", "clearance_run_card_sha256"),
    ):
        if base_summary.get(summary_field) != authenticated_sources[lineage_field]:
            raise RetainedCohortExtensionError(
                f"base projection {summary_field} differs from authenticated lineage"
            )
    raw_base_inputs = base_summary.get("input_commitments")
    if not isinstance(raw_base_inputs, Mapping):
        raise RetainedCohortExtensionError(
            "base projection lacks authenticated input commitments"
        )
    base_input_hashes = set(cast(Mapping[object, object], raw_base_inputs).values())
    required_base_hashes = {
        authenticated_sources["preparation_summary_sha256"],
        authenticated_sources["preparation_config_sha256"],
        authenticated_sources["snapshot_manifest_sha256"],
        authenticated_sources["clearance_run_card_sha256"],
        authenticated_sources["restriction_evidence_sha256"],
    }
    if not required_base_hashes.issubset(base_input_hashes):
        raise RetainedCohortExtensionError(
            "base projection input commitments differ from authenticated lineage"
        )
    full = {
        name: _jsonl_records(payload, source=f"full pool {name}")
        for name, payload in full_pool_artifacts.items()
    }
    full_selection = _candidate_index(full["selection.jsonl"], "full selection")
    full_relevance = _candidate_index(
        full["case-relevance.jsonl"], "full case relevance"
    )
    if set(full_selection) != set(full_relevance):
        raise RetainedCohortExtensionError(
            "full selection and relevance candidate sets differ"
        )
    _verify_base_is_exact_full_pool_subset(base, full)
    base_ids = cast(tuple[str, ...], base["candidate_ids"])
    omitted_ids = tuple(sorted(set(full_selection) - set(base_ids)))
    omitted_set = set(omitted_ids)
    if len(omitted_ids) < TARGET_CASE_COUNT - BASE_CASE_COUNT:
        raise RetainedCohortExtensionError(
            "full eligible omitted frontier is smaller than the required extension"
        )

    full_manifest = full["document-downloads-merged.jsonl"]
    full_clearance = full["disclosure-clearance.jsonl"]
    try:
        incremental = project_target_cohort(
            selections=[full_selection[candidate_id] for candidate_id in omitted_ids],
            case_relevance=[
                full_relevance[candidate_id] for candidate_id in omitted_ids
            ],
            download_manifest=[
                record
                for record in full_manifest
                if _required_str(record, "candidate_id") in omitted_set
            ],
            clearance_records=[
                record
                for record in full_clearance
                if _required_str(record, "candidate_id") in omitted_set
            ],
            target_case_count=TARGET_CASE_COUNT - BASE_CASE_COUNT,
            cost_per_document_usd=_format_money(money),
            max_projected_budget_usd=_format_money(
                _remaining_incremental_cap(
                    cap=cap,
                    base_cost=cast(Decimal, base["cost"]),
                    obligations=obligation_values,
                )
            ),
            max_missing_core_documents_per_case=(max_missing_core_documents_per_case),
        )
    except TargetCohortProjectionError as exc:
        raise RetainedCohortExtensionError(str(exc)) from exc

    incremental_ids = incremental.selected_candidate_ids
    combined_ids = (*base_ids, *incremental_ids)
    if len(combined_ids) != TARGET_CASE_COUNT or len(set(combined_ids)) != len(
        combined_ids
    ):
        raise RetainedCohortExtensionError(
            "combined cohort does not contain exactly 150 unique candidates"
        )
    if set(base_ids) & set(incremental_ids):
        raise RetainedCohortExtensionError(
            "incremental cohort overlaps the retained base cohort"
        )
    if not set(incremental_ids).issubset(omitted_ids):
        raise RetainedCohortExtensionError(
            "incremental cohort contains a candidate outside the omitted frontier"
        )
    _verify_combined_identities(
        [full_selection[candidate_id] for candidate_id in combined_ids]
    )

    base_plans = cast(tuple[CaseMissingCorePurchasePlan, ...], base["case_plans"])
    combined_filter_results = filter_core_documents(
        [full_relevance[candidate_id] for candidate_id in combined_ids]
    )
    recomputed_combined = plan_missing_core_document_budget(
        combined_filter_results,
        dry_run=False,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        cost_per_document_usd=money,
        max_projected_budget_usd=cap - purchase_obligations.total,
        truncate_to_budget=True,
        target_case_count=TARGET_CASE_COUNT,
    )
    combined_plan = MissingCoreBudgetPlan(
        case_plans=(*base_plans, *incremental.budget_plan.case_plans),
        cost_per_document=money,
        max_projected_budget=cap,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        dry_run=False,
        frontier_rows=recomputed_combined.frontier_rows,
        omitted_candidate_ids=recomputed_combined.omitted_candidate_ids,
        excluded_case_plans=recomputed_combined.excluded_case_plans,
        target_case_count=TARGET_CASE_COUNT,
    )
    incremental_cost = incremental.budget_plan.total_estimated_cost
    base_cost = cast(Decimal, base["cost"])
    cumulative = base_cost + incremental_cost + purchase_obligations.total
    if cumulative > cap:
        raise RetainedCohortExtensionError(
            "combined cumulative obligation exceeds the immutable budget cap"
        )
    combined_budget = {
        "schema_version": "legalforecast.retained_cohort_budget.v1",
        "target_case_count": TARGET_CASE_COUNT,
        "base_case_count": BASE_CASE_COUNT,
        "incremental_case_count": TARGET_CASE_COUNT - BASE_CASE_COUNT,
        "cost_per_document_usd": _format_money(money),
        "max_projected_budget_usd": _format_money(cap),
        "max_missing_core_documents_per_case": (max_missing_core_documents_per_case),
        "base_projected_usd": _format_money(base_cost),
        "incremental_projected_usd": _format_money(incremental_cost),
        **obligations,
        "cumulative_obligation_usd": _format_money(cumulative),
        "remaining_headroom_usd": _format_money(cap - cumulative),
        "base_budget_plan_sha256": _bytes_sha256(
            base_projection_artifacts["missing-core-budget-plan.json"]
        ),
        "incremental_budget_plan_sha256": _canonical_sha256(
            incremental.budget_plan.to_record()
        ),
        "combined_budget_plan_sha256": _canonical_sha256(combined_plan.to_record()),
    }
    combined_budget["budget_sha256"] = _canonical_sha256(combined_budget)

    incremental_payloads = _projection_payloads(incremental)
    combined_payloads = {
        name: base_projection_artifacts[name] + incremental_payloads[name]
        for name in _BASE_JSONL_NAMES
    }
    # Exclusions are intentionally rederived for the new 150-case boundary;
    # target-100 omissions may become selected and therefore cannot be prefixes.
    combined_payloads["target-cohort-exclusions.jsonl"] = incremental_payloads[
        "target-cohort-exclusions.jsonl"
    ]
    combined_payloads["missing-core-budget-plan.json"] = _json_bytes(
        combined_plan.to_record()
    )
    combined_payloads["retained-cohort-budget.json"] = _json_bytes(combined_budget)

    exclusions = _jsonl_records(
        combined_payloads["target-cohort-exclusions.jsonl"],
        source="combined exclusions",
    )
    excluded_ids = {_required_str(row, "candidate_id") for row in exclusions}
    expected_excluded = set(full_selection) - set(combined_ids)
    if excluded_ids != expected_excluded or len(exclusions) != len(excluded_ids):
        raise RetainedCohortExtensionError(
            "combined exclusions do not reconcile the full resolved pool"
        )

    source_commitments = {
        "base_projection": {
            name: _bytes_sha256(payload)
            for name, payload in sorted(base_projection_artifacts.items())
        },
        "full_pool": {
            name: _bytes_sha256(payload)
            for name, payload in sorted(full_pool_artifacts.items())
        },
        "cohort_policy_sha256": "sha256:" + policy_sha256,
        "snapshot_manifest_sha256": snapshot_hash,
        "snapshot_cycle_hash": cycle_hash,
        "snapshot_batch_digest": batch_digest,
        "purchase_policy_sha256": purchase_obligations.purchase_policy_sha256,
        "purchase_journal_state_sha256": (
            purchase_obligations.purchase_journal_state_sha256
        ),
        "canonical_purchase_ledger_path": (purchase_obligations.canonical_ledger_path),
        "authenticated_pool_lineage": authenticated_lineage.source_record(),
    }
    extension_record: JsonRecord = {
        "schema_version": SCHEMA_VERSION,
        "base_case_count": BASE_CASE_COUNT,
        "incremental_case_count": TARGET_CASE_COUNT - BASE_CASE_COUNT,
        "combined_case_count": len(combined_ids),
        "full_pool_case_count": len(full_selection),
        "base_candidate_ids": list(base_ids),
        "incremental_candidate_ids": list(incremental_ids),
        "combined_candidate_ids": list(combined_ids),
        "base_candidate_ids_sha256": _canonical_sha256(list(base_ids)),
        "incremental_candidate_ids_sha256": _canonical_sha256(list(incremental_ids)),
        "combined_candidate_ids_sha256": _canonical_sha256(list(combined_ids)),
        "source_commitments": source_commitments,
        "budget": combined_budget,
        "incremental_projection_sha256": incremental.summary["projection_sha256"],
        "output_commitments": {
            name: _bytes_sha256(payload)
            for name, payload in sorted(combined_payloads.items())
        },
        "prefix_preservation": {
            name: {
                "base_byte_count": len(base_projection_artifacts[name]),
                "base_sha256": _bytes_sha256(base_projection_artifacts[name]),
            }
            for name in _BASE_JSONL_NAMES
        },
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    extension_record["extension_sha256"] = _canonical_sha256(extension_record)
    combined_payloads["retained-cohort-extension.json"] = _json_bytes(extension_record)
    return RetainedCohortExtension(
        base_candidate_ids=base_ids,
        incremental_candidate_ids=incremental_ids,
        combined_candidate_ids=combined_ids,
        incremental_artifacts=dict(incremental_payloads),
        combined_artifacts=dict(combined_payloads),
        combined_budget=combined_budget,
        extension_record=extension_record,
    )


def _verified_policy(
    artifact: Mapping[str, Any],
    *,
    snapshot_cycle_hash: str,
    max_projected_budget_usd: str,
    max_missing_core_documents_per_case: int,
    cost_per_document_usd: str,
) -> tuple[str, Mapping[str, Any]]:
    try:
        digest = verify_cohort_policy(artifact)
    except CohortPolicyError as exc:
        raise RetainedCohortExtensionError(str(exc)) from exc
    policy = cast(Mapping[str, Any], artifact["policy"])
    stop = cast(Mapping[str, Any], policy["stop_rule"])
    if stop.get("target_clean_cases") != TARGET_CASE_COUNT:
        raise RetainedCohortExtensionError(
            "cohort policy target_clean_cases must be exactly 150"
        )
    if policy.get("cycle_acquisition_hash") != _bare_sha(
        snapshot_cycle_hash, "snapshot_cycle_hash"
    ):
        raise RetainedCohortExtensionError(
            "snapshot cycle hash differs from the cohort policy"
        )
    purchase = cast(Mapping[str, Any], policy["purchase_policy"])
    cycle_cap = _money(
        str(purchase.get("cycle_budget_usd")), "policy cycle_budget_usd", positive=True
    )
    requested_cap = _money(
        max_projected_budget_usd, "max_projected_budget_usd", positive=True
    )
    if requested_cap > cycle_cap:
        raise RetainedCohortExtensionError(
            "projected budget exceeds the immutable cohort-policy cycle cap"
        )
    if isinstance(max_missing_core_documents_per_case, bool) or (
        max_missing_core_documents_per_case < 1
    ):
        raise RetainedCohortExtensionError(
            "max_missing_core_documents_per_case must be positive"
        )
    per_case = _money(
        str(purchase.get("max_per_case_usd")),
        "policy max_per_case_usd",
        positive=True,
    )
    cost = _money(cost_per_document_usd, "cost_per_document_usd", positive=True)
    if cost * max_missing_core_documents_per_case > per_case:
        raise RetainedCohortExtensionError(
            "configured missing-document threshold exceeds the immutable per-case cap"
        )
    return digest, policy


def _verify_base_projection(
    artifacts: Mapping[str, bytes],
    *,
    cost_per_document_usd: Decimal,
    max_projected_budget_usd: Decimal,
    max_missing_core_documents_per_case: int,
) -> dict[str, Any]:
    summary = _json_object(
        artifacts["target-cohort-projection.json"], source="base projection summary"
    )
    if summary.get("schema_version") != "legalforecast.target_cohort_projection.v1":
        raise RetainedCohortExtensionError("unsupported base projection schema")
    projection_sha256 = summary.get("projection_sha256")
    if (
        not isinstance(projection_sha256, str)
        or _SHA256.fullmatch(projection_sha256) is None
    ):
        raise RetainedCohortExtensionError(
            "base projection lacks a valid projection_sha256"
        )
    if (
        summary.get("target_case_count") != BASE_CASE_COUNT
        or summary.get("selected_case_count") != BASE_CASE_COUNT
        or summary.get("paid_activity_requested") is not False
        or summary.get("paid_activity_executed") is not False
    ):
        raise RetainedCohortExtensionError(
            "base projection is not an exact noncharging target-100 projection"
        )
    raw_commitments = summary.get("output_commitments")
    if not isinstance(raw_commitments, Mapping):
        raise RetainedCohortExtensionError("base projection lacks output commitments")
    commitments = cast(Mapping[str, object], raw_commitments)
    for name in _BASE_REQUIRED_NAMES - {"target-cohort-projection.json"}:
        if commitments.get(name) != _bytes_sha256(artifacts[name]):
            raise RetainedCohortExtensionError(
                f"base projection output commitment mismatch: {name}"
            )
    selection = _jsonl_records(
        artifacts["target-cohort-selection.jsonl"], source="base selection"
    )
    candidate_ids = tuple(_required_str(row, "candidate_id") for row in selection)
    if len(candidate_ids) != BASE_CASE_COUNT or len(set(candidate_ids)) != len(
        candidate_ids
    ):
        raise RetainedCohortExtensionError(
            "base selection does not contain exactly 100 unique candidates"
        )
    if summary.get("selected_candidate_ids_sha256") != _canonical_sha256(
        list(candidate_ids)
    ):
        raise RetainedCohortExtensionError(
            "base selected-candidate commitment mismatch"
        )
    budget = _json_object(
        artifacts["missing-core-budget-plan.json"], source="base budget"
    )
    if (
        budget.get("target_case_count") != BASE_CASE_COUNT
        or budget.get("target_case_count_met") is not True
        or budget.get("dry_run") is not False
        or _money(str(budget.get("cost_per_document_usd")), "base cost")
        != cost_per_document_usd
        or _money(str(budget.get("max_projected_budget_usd")), "base cap")
        != max_projected_budget_usd
        or budget.get("max_missing_core_documents_per_case")
        != max_missing_core_documents_per_case
    ):
        raise RetainedCohortExtensionError(
            "base budget semantics differ from the extension contract"
        )
    raw_plans = budget.get("case_plans")
    if not isinstance(raw_plans, Sequence) or isinstance(raw_plans, (str, bytes)):
        raise RetainedCohortExtensionError("base budget lacks case plans")
    plans = tuple(_case_plan(record) for record in cast(Sequence[object], raw_plans))
    if tuple(plan.candidate_id for plan in plans) != candidate_ids:
        raise RetainedCohortExtensionError(
            "base budget plan order differs from the retained selection"
        )
    base_cost = sum((plan.estimated_cost for plan in plans), Decimal("0.00"))
    if _format_money(base_cost) != budget.get("total_estimated_cost_usd"):
        raise RetainedCohortExtensionError("base budget total is inconsistent")
    parsed = {
        name: _jsonl_records(artifacts[name], source=f"base {name}")
        for name in _BASE_JSONL_NAMES
    }
    parsed["target-cohort-exclusions.jsonl"] = _jsonl_records(
        artifacts["target-cohort-exclusions.jsonl"], source="base exclusions"
    )
    for name in (
        "case-relevance.jsonl",
        "core-filter-results.jsonl",
    ):
        ids = tuple(_required_str(row, "candidate_id") for row in parsed[name])
        if ids != candidate_ids:
            raise RetainedCohortExtensionError(
                f"base {name} order differs from retained selection"
            )
    return {
        "summary": summary,
        "candidate_ids": candidate_ids,
        "parsed": parsed,
        "case_plans": plans,
        "cost": base_cost,
        "cost_per_document": cost_per_document_usd,
        "max_projected_budget": max_projected_budget_usd,
        "max_missing_core_documents_per_case": (max_missing_core_documents_per_case),
    }


def _verify_base_is_exact_full_pool_subset(
    base: Mapping[str, Any], full: Mapping[str, list[JsonRecord]]
) -> None:
    summary = cast(Mapping[str, Any], base["summary"])
    base_ids = cast(tuple[str, ...], base["candidate_ids"])
    parsed = cast(Mapping[str, list[JsonRecord]], base["parsed"])
    full_selection = _candidate_index(full["selection.jsonl"], "full selection")
    full_relevance = _candidate_index(
        full["case-relevance.jsonl"], "full case relevance"
    )
    for name, index in (
        ("target-cohort-selection.jsonl", full_selection),
        ("case-relevance.jsonl", full_relevance),
    ):
        base_index = _candidate_index(parsed[name], f"base {name}")
        if set(base_index) != set(base_ids) or any(
            candidate_id not in index or index[candidate_id] != base_index[candidate_id]
            for candidate_id in base_ids
        ):
            raise RetainedCohortExtensionError(
                f"base {name} is not an exact subset of the full pool"
            )
    merged_index = _document_index(
        parsed["document-downloads-merged.jsonl"], "base merged manifest"
    )
    for name, expected_kind in (
        ("free-document-downloads.jsonl", "free"),
        ("purchased-document-downloads.jsonl", "purchased"),
    ):
        category_index = _document_index(parsed[name], f"base {name}")
        expected_index = {
            key: record
            for key, record in merged_index.items()
            if record.get("free_or_purchased") == expected_kind
        }
        if category_index != expected_index:
            raise RetainedCohortExtensionError(
                f"base {name} does not exactly partition the merged manifest"
            )
    for base_name, full_name in (
        ("document-downloads-merged.jsonl", "document-downloads-merged.jsonl"),
        ("disclosure-clearance.jsonl", "disclosure-clearance.jsonl"),
    ):
        expected = _document_index(
            (
                record
                for record in full[full_name]
                if _required_str(record, "candidate_id") in set(base_ids)
            ),
            f"full {full_name} base subset",
        )
        actual = _document_index(parsed[base_name], f"base {base_name}")
        if expected != actual:
            raise RetainedCohortExtensionError(
                f"base {base_name} is not an exact subset of the full pool"
            )

    base_relevance = [full_relevance[candidate_id] for candidate_id in base_ids]
    try:
        restrictions = restriction_evidence_from_case_relevance(base_relevance)
    except TargetCohortProjectionError as exc:
        raise RetainedCohortExtensionError(str(exc)) from exc
    if list(restrictions) != parsed["restriction-evidence.jsonl"]:
        raise RetainedCohortExtensionError(
            "base restriction evidence does not derive from the full pool"
        )
    filter_results = filter_core_documents(base_relevance)
    if [row.to_record() for row in filter_results] != parsed[
        "core-filter-results.jsonl"
    ]:
        raise RetainedCohortExtensionError(
            "base core-filter results do not derive from the full pool"
        )
    base_plans = cast(tuple[CaseMissingCorePurchasePlan, ...], base["case_plans"])
    recomputed = plan_missing_core_document_budget(
        filter_results,
        dry_run=False,
        max_missing_core_documents_per_case=cast(
            int, base["max_missing_core_documents_per_case"]
        ),
        cost_per_document_usd=cast(Decimal, base["cost_per_document"]),
        max_projected_budget_usd=cast(Decimal, base["max_projected_budget"]),
        truncate_to_budget=True,
        target_case_count=BASE_CASE_COUNT,
    )
    if recomputed.case_plans != base_plans:
        raise RetainedCohortExtensionError(
            "base budget plans do not derive from the full pool"
        )
    try:
        validated = project_target_cohort(
            selections=full["selection.jsonl"],
            case_relevance=full["case-relevance.jsonl"],
            download_manifest=full["document-downloads-merged.jsonl"],
            clearance_records=full["disclosure-clearance.jsonl"],
            target_case_count=BASE_CASE_COUNT,
            cost_per_document_usd=_format_money(
                cast(Decimal, base["cost_per_document"])
            ),
            max_projected_budget_usd=_format_money(
                cast(Decimal, base["max_projected_budget"])
            ),
            max_missing_core_documents_per_case=cast(
                int, base["max_missing_core_documents_per_case"]
            ),
        )
    except TargetCohortProjectionError as exc:
        raise RetainedCohortExtensionError(
            f"base projection does not revalidate: {exc}"
        ) from exc
    if (
        validated.selected_candidate_ids != base_ids
        or validated.budget_plan.case_plans != base_plans
        or list(validated.restriction_evidence) != parsed["restriction-evidence.jsonl"]
        or [row.to_record() for row in validated.core_filter_results]
        != parsed["core-filter-results.jsonl"]
        or list(validated.exclusions) != parsed["target-cohort-exclusions.jsonl"]
    ):
        raise RetainedCohortExtensionError(
            "base projection artifacts do not reproduce from the frozen inputs"
        )
    if summary.get("budget_plan_sha256") != _canonical_sha256(
        validated.budget_plan.to_record()
    ):
        raise RetainedCohortExtensionError(
            "base budget-plan digest does not match reproduced content"
        )
    if summary.get("projection_sha256") != validated.summary.get("projection_sha256"):
        raise RetainedCohortExtensionError(
            "base projection digest does not match reproduced content"
        )


def _verify_combined_identities(selections: Sequence[Mapping[str, Any]]) -> None:
    docket_seen: set[tuple[str, str]] = set()
    motion_seen: set[tuple[str, str]] = set()
    for record in selections:
        candidate_id = _required_str(record, "candidate_id")
        court = _required_str(record, "court")
        docket_number = _required_str(record, "docket_number")
        docket = (court, docket_number)
        if docket in docket_seen:
            raise RetainedCohortExtensionError(
                f"duplicate docket identity in combined cohort: {docket}"
            )
        docket_seen.add(docket)
        case_id = _required_str(record, "case_id")
        raw_entries = record.get("target_motion_entry_numbers")
        if not isinstance(raw_entries, Sequence) or isinstance(
            raw_entries, (str, bytes)
        ):
            raise RetainedCohortExtensionError(
                f"candidate {candidate_id} lacks exactly one target motion identity"
            )
        entries = tuple(cast(Sequence[object], raw_entries))
        if (
            len(entries) != 1
            or isinstance(entries[0], bool)
            or not isinstance(entries[0], (str, int))
        ):
            raise RetainedCohortExtensionError(
                f"candidate {candidate_id} lacks exactly one target motion identity"
            )
        motion = (case_id, str(entries[0]))
        if motion in motion_seen:
            raise RetainedCohortExtensionError(
                f"duplicate motion identity in combined cohort: {motion}"
            )
        motion_seen.add(motion)


def _projection_payloads(projection: Any) -> dict[str, bytes]:
    merged = tuple(projection.download_manifest)
    return {
        "target-cohort-selection.jsonl": _jsonl_bytes(projection.selections),
        "case-relevance.jsonl": _jsonl_bytes(projection.case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(projection.download_manifest),
        "free-document-downloads.jsonl": _jsonl_bytes(
            record for record in merged if record.get("free_or_purchased") == "free"
        ),
        "purchased-document-downloads.jsonl": _jsonl_bytes(
            record
            for record in merged
            if record.get("free_or_purchased") == "purchased"
        ),
        "disclosure-clearance.jsonl": _jsonl_bytes(projection.clearance_records),
        "restriction-evidence.jsonl": _jsonl_bytes(projection.restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(
            row.to_record() for row in projection.core_filter_results
        ),
        "target-cohort-exclusions.jsonl": _jsonl_bytes(projection.exclusions),
        "missing-core-budget-plan.json": _json_bytes(
            projection.budget_plan.to_record()
        ),
        "target-cohort-projection.json": _json_bytes(projection.summary),
    }


def _case_plan(raw: object) -> CaseMissingCorePurchasePlan:
    if not isinstance(raw, Mapping):
        raise RetainedCohortExtensionError("base case plan must be an object")
    record = cast(Mapping[str, Any], raw)
    documents = _string_tuple(record.get("purchase_document_ids"), "purchase documents")
    roles = _string_tuple(record.get("missing_core_roles"), "missing core roles")
    exclusions = _string_tuple(record.get("exclusion_reasons"), "exclusion reasons")
    count = record.get("missing_core_document_count")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count != len(documents)
        or record.get("estimated_purchase_count") != count
    ):
        raise RetainedCohortExtensionError("base case plan count is inconsistent")
    audit_count = record.get("audit_only_document_count")
    if (
        not isinstance(audit_count, int)
        or isinstance(audit_count, bool)
        or audit_count < 0
    ):
        raise RetainedCohortExtensionError("base audit-only count is invalid")
    if record.get("dry_run") is not False:
        raise RetainedCohortExtensionError("base case plan must be executable")
    return CaseMissingCorePurchasePlan(
        candidate_id=_required_str(record, "candidate_id"),
        purchase_document_ids=documents,
        missing_core_document_count=count,
        estimated_cost=_money(str(record.get("estimated_cost_usd")), "case cost"),
        audit_only_document_count=audit_count,
        dry_run=False,
        exclusion_reasons=exclusions,
        missing_core_roles=roles,
    )


def _remaining_incremental_cap(
    *, cap: Decimal, base_cost: Decimal, obligations: Mapping[str, Decimal]
) -> Decimal:
    remaining = cap - base_cost - sum(obligations.values(), Decimal("0.00"))
    if remaining < 0:
        raise RetainedCohortExtensionError(
            "base and existing obligations already exceed the immutable budget cap"
        )
    return remaining


def _candidate_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[str, JsonRecord]:
    output: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in output:
            raise RetainedCohortExtensionError(
                f"duplicate candidate in {label}: {candidate_id}"
            )
        output[candidate_id] = dict(record)
    if not output:
        raise RetainedCohortExtensionError(f"{label} is empty")
    return output


def _document_index(
    records: Iterable[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], JsonRecord]:
    output: dict[tuple[str, str], JsonRecord] = {}
    for record in records:
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        if key in output:
            raise RetainedCohortExtensionError(f"duplicate document in {label}: {key}")
        output[key] = dict(record)
    return output


def _require_exact_names(
    artifacts: Mapping[str, bytes], expected: frozenset[str], label: str
) -> None:
    actual = set(artifacts)
    if actual != set(expected):
        raise RetainedCohortExtensionError(
            f"{label} artifact set mismatch; missing={sorted(expected - actual)}; "
            f"extra={sorted(actual - expected)}"
        )


def _jsonl_records(payload: bytes, *, source: str) -> list[JsonRecord]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RetainedCohortExtensionError(f"{source} is not UTF-8") from exc
    output: list[JsonRecord] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (ValueError, TypeError) as exc:
            raise RetainedCohortExtensionError(
                f"{source} has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(record, Mapping):
            raise RetainedCohortExtensionError(
                f"{source} line {line_number} is not an object"
            )
        output.append(dict(cast(Mapping[str, Any], record)))
    return output


def _json_object(payload: bytes, *, source: str) -> JsonRecord:
    try:
        record = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise RetainedCohortExtensionError(f"{source} is not valid JSON") from exc
    if not isinstance(record, Mapping):
        raise RetainedCohortExtensionError(f"{source} is not an object")
    return dict(cast(Mapping[str, Any], record))


def _jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    ).encode("utf-8")


def _json_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(record), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise RetainedCohortExtensionError(f"{field} must be a non-empty string")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RetainedCohortExtensionError(f"{label} must be an array")
    output = tuple(cast(Sequence[object], value))
    if not all(isinstance(item, str) and item for item in output):
        raise RetainedCohortExtensionError(f"{label} contains an invalid value")
    return cast(tuple[str, ...], output)


def _money(value: str, label: str, *, positive: bool = False) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise RetainedCohortExtensionError(f"{label} is invalid") from exc
    if (
        not amount.is_finite()
        or amount < 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise RetainedCohortExtensionError(f"{label} must be nonnegative USD cents")
    if positive and amount <= 0:
        raise RetainedCohortExtensionError(f"{label} must be positive")
    return amount


def _format_money(value: Decimal) -> str:
    return f"{value:.2f}"


def _sha(value: str, label: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise RetainedCohortExtensionError(f"{label} must be a prefixed SHA-256")
    return value


def _bare_sha(value: str, label: str) -> str:
    raw = value.removeprefix("sha256:")
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise RetainedCohortExtensionError(f"{label} must be a SHA-256")
    return raw


def _bytes_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()

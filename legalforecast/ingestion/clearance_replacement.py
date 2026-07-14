"""Frozen, idempotent replacement planning after purchased-document clearance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicyError,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)

FRONTIER_SCHEMA_VERSION = "legalforecast.clearance_replacement_frontier.v1"
EVENT_SCHEMA_VERSION = "legalforecast.clearance_replacement_event.v1"
RESULT_SCHEMA_VERSION = "legalforecast.clearance_replacement_plan.v1"
_SHA256 = re.compile(r"(?:sha256:)?[0-9a-f]{64}")
_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")
_CASE_MIX_DIMENSIONS = (
    "court",
    "nos_macro_category",
    "related_family_id",
    "mdl_family_id",
)


class ClearanceReplacementError(ValueError):
    """Raised when replacement evidence is incomplete, mutable, or unsafe."""


@dataclass(frozen=True, slots=True)
class ClearanceReplacementPlan:
    """One replay-safe view of the active cohort and next purchase iteration."""

    active_candidate_ids: tuple[str, ...]
    replacement_plan: MissingCoreBudgetPlan
    broker_allowlist_plan: MissingCoreBudgetPlan
    ledger_records: tuple[Mapping[str, Any], ...]
    derived_exclusions: tuple[Mapping[str, Any], ...]
    stop_reason: str
    frontier_sha256: str
    purchase_journal_state_sha256: str

    def to_record(self) -> dict[str, Any]:
        """Return the hash-bound offline orchestration artifact."""

        record: dict[str, Any] = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "active_candidate_ids": list(self.active_candidate_ids),
            "replacement_plan": self.replacement_plan.to_record(),
            "broker_allowlist_plan": self.broker_allowlist_plan.to_record(),
            "ledger_records": [dict(row) for row in self.ledger_records],
            "derived_exclusions": [dict(row) for row in self.derived_exclusions],
            "stop_reason": self.stop_reason,
            "frontier_sha256": self.frontier_sha256,
            "purchase_journal_state_sha256": self.purchase_journal_state_sha256,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
        record["plan_sha256"] = _prefixed_hash(record)
        return record


def build_replacement_frontier(
    *,
    cohort_policy_artifact: Mapping[str, Any],
    purchase_policy_artifact: Mapping[str, object],
    projection_sha256: str,
    initial_selected_candidate_ids: Sequence[str],
    candidate_rows: Sequence[Mapping[str, object]],
    case_mix_max_per_bucket: int | None,
    source_commitments: Mapping[str, str],
) -> dict[str, Any]:
    """Freeze the complete canonical candidate order and replacement constraints.

    ``candidate_rows`` is already the canonical ranked frontier produced by the
    acquisition projection. This function never re-sorts it. Its source hashes
    and explicit ``frontier_truncated=False`` assertion make omission detectable
    by the upstream projection commitment rather than silently changing rank.
    """

    try:
        cohort_sha256 = verify_cohort_policy(cohort_policy_artifact)
        purchase_policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy, cohort_policy_artifact
        )
    except (CohortPolicyError, CaseDevPurchasePolicyError) as exc:
        raise ClearanceReplacementError(str(exc)) from exc
    projection = _sha(projection_sha256, "projection_sha256")
    initial = _canonical_unique_strings(
        initial_selected_candidate_ids, "initial_selected_candidate_ids"
    )
    cohort_policy = cast(Mapping[str, Any], cohort_policy_artifact["policy"])
    target = _target_clean_cases(cohort_policy)
    if len(initial) != target:
        raise ClearanceReplacementError(
            "initial selected candidate count must equal the frozen target"
        )
    if case_mix_max_per_bucket is not None and (
        isinstance(case_mix_max_per_bucket, bool) or case_mix_max_per_bucket < 1
    ):
        raise ClearanceReplacementError(
            "case_mix_max_per_bucket must be a positive integer or null"
        )
    if not source_commitments:
        raise ClearanceReplacementError(
            "replacement frontier requires source commitments"
        )
    commitments = {
        _canonical_text(name, "source commitment name"): _sha(
            digest, f"source commitment {name}"
        )
        for name, digest in sorted(source_commitments.items())
    }
    candidates = [
        _frontier_candidate(row, rank=rank)
        for rank, row in enumerate(candidate_rows, start=1)
    ]
    candidate_ids = [cast(str, row["candidate_id"]) for row in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ClearanceReplacementError(
            "replacement frontier candidate IDs must be unique"
        )
    _verify_candidate_costs(candidates, purchase_policy=purchase_policy)
    policy: dict[str, Any] = {
        "cycle_id": purchase_policy.cycle_id,
        "cohort_policy_sha256": "sha256:" + cohort_sha256,
        "purchase_policy_sha256": "sha256:" + purchase_policy.policy_sha256,
        "projection_sha256": projection,
        "source_commitments": commitments,
        "target_clean_cases": target,
        "initial_selected_candidate_ids": list(initial),
        "frontier_truncated": False,
        "candidate_count": len(candidates),
        "case_mix_dimensions": list(_CASE_MIX_DIMENSIONS),
        "case_mix_max_per_bucket": case_mix_max_per_bucket,
        "candidates": candidates,
    }
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "policy": policy,
        "policy_sha256": _prefixed_hash(policy),
    }


def verify_replacement_frontier(
    artifact: Mapping[str, Any],
    *,
    cohort_policy_artifact: Mapping[str, Any] | None = None,
    purchase_policy_artifact: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Verify the full frontier, its hash, and optional source policy bindings."""

    _exact_keys(
        artifact,
        {"schema_version", "policy", "policy_sha256"},
        "replacement frontier artifact",
    )
    if artifact.get("schema_version") != FRONTIER_SCHEMA_VERSION:
        raise ClearanceReplacementError("unsupported replacement frontier schema")
    raw_policy = artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise ClearanceReplacementError("replacement frontier policy must be an object")
    policy = cast(Mapping[str, Any], raw_policy)
    _exact_keys(
        policy,
        {
            "cycle_id",
            "cohort_policy_sha256",
            "purchase_policy_sha256",
            "projection_sha256",
            "source_commitments",
            "target_clean_cases",
            "initial_selected_candidate_ids",
            "frontier_truncated",
            "candidate_count",
            "case_mix_dimensions",
            "case_mix_max_per_bucket",
            "candidates",
        },
        "replacement frontier policy",
    )
    if _sha(artifact.get("policy_sha256"), "policy_sha256") != _prefixed_hash(policy):
        raise ClearanceReplacementError(
            "replacement frontier hash does not match content"
        )
    _canonical_text(policy.get("cycle_id"), "cycle_id")
    _sha(policy.get("cohort_policy_sha256"), "cohort_policy_sha256")
    _sha(policy.get("purchase_policy_sha256"), "purchase_policy_sha256")
    _sha(policy.get("projection_sha256"), "projection_sha256")
    if policy.get("frontier_truncated") is not False:
        raise ClearanceReplacementError(
            "replacement frontier must be the full untruncated canonical frontier"
        )
    if policy.get("case_mix_dimensions") != list(_CASE_MIX_DIMENSIONS):
        raise ClearanceReplacementError(
            "replacement frontier case-mix dimensions changed"
        )
    max_per_bucket = policy.get("case_mix_max_per_bucket")
    if max_per_bucket is not None and (
        not isinstance(max_per_bucket, int)
        or isinstance(max_per_bucket, bool)
        or max_per_bucket < 1
    ):
        raise ClearanceReplacementError("invalid case_mix_max_per_bucket")
    target = _positive_int(policy.get("target_clean_cases"), "target_clean_cases")
    initial = _canonical_unique_strings(
        _sequence(policy.get("initial_selected_candidate_ids"), "initial selected"),
        "initial_selected_candidate_ids",
    )
    if len(initial) != target:
        raise ClearanceReplacementError(
            "initial selected candidate count must equal target_clean_cases"
        )
    raw_candidates = _sequence(policy.get("candidates"), "candidates")
    candidates: list[dict[str, Any]] = []
    for rank, raw in enumerate(raw_candidates, start=1):
        if not isinstance(raw, Mapping):
            raise ClearanceReplacementError(
                "replacement frontier candidate must be an object"
            )
        candidate = _frontier_candidate(
            cast(Mapping[str, object], raw), rank=rank, require_rank=True
        )
        candidates.append(candidate)
    if policy.get("candidate_count") != len(candidates):
        raise ClearanceReplacementError("replacement frontier candidate_count mismatch")
    candidate_ids = [cast(str, row["candidate_id"]) for row in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ClearanceReplacementError("replacement frontier candidates repeat")
    if not set(initial).issubset(candidate_ids):
        raise ClearanceReplacementError(
            "initial selected candidates are absent from the replacement frontier"
        )
    commitments = policy.get("source_commitments")
    if not isinstance(commitments, Mapping) or not commitments:
        raise ClearanceReplacementError("replacement frontier lacks source commitments")
    typed_commitments = cast(Mapping[object, object], commitments)
    for name, digest in typed_commitments.items():
        _canonical_text(name, "source commitment name")
        _sha(digest, f"source commitment {name}")

    if cohort_policy_artifact is not None:
        try:
            cohort_hash = verify_cohort_policy(cohort_policy_artifact)
        except CohortPolicyError as exc:
            raise ClearanceReplacementError(str(exc)) from exc
        if policy.get("cohort_policy_sha256") != "sha256:" + cohort_hash:
            raise ClearanceReplacementError("frontier cohort-policy hash mismatch")
        cohort = cast(Mapping[str, Any], cohort_policy_artifact["policy"])
        if policy.get("cycle_id") != cohort.get("cycle_id"):
            raise ClearanceReplacementError("frontier cycle_id mismatch")
        if target != _target_clean_cases(cohort):
            raise ClearanceReplacementError(
                "frontier target differs from cohort policy"
            )
    if purchase_policy_artifact is not None:
        try:
            purchase = verify_case_dev_purchase_policy(purchase_policy_artifact)
            if cohort_policy_artifact is not None:
                verify_case_dev_purchase_policy_cohort_binding(
                    purchase, cohort_policy_artifact
                )
        except CaseDevPurchasePolicyError as exc:
            raise ClearanceReplacementError(str(exc)) from exc
        if policy.get("purchase_policy_sha256") != "sha256:" + purchase.policy_sha256:
            raise ClearanceReplacementError("frontier purchase-policy hash mismatch")
        if policy.get("cycle_id") != purchase.cycle_id:
            raise ClearanceReplacementError("frontier purchase-policy cycle mismatch")
        _verify_candidate_costs(candidates, purchase_policy=purchase)
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "policy": dict(policy),
        "policy_sha256": artifact["policy_sha256"],
    }


def write_replacement_frontier(path: str | Path, artifact: Mapping[str, Any]) -> Path:
    """Atomically publish a verified immutable replacement frontier."""

    verify_replacement_frontier(artifact)
    target = Path(path)
    payload = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != payload:
            raise ClearanceReplacementError(
                "refusing to overwrite a different replacement frontier"
            )
        return target
    fd, name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ClearanceReplacementError(
                "replacement frontier was concurrently created with different content"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def build_broad_broker_allowlist_plan(
    *,
    cohort_policy_artifact: Mapping[str, Any],
    purchase_policy_artifact: Mapping[str, object],
    frontier_artifact: Mapping[str, Any],
) -> MissingCoreBudgetPlan:
    """Derive the broad broker scope before any purchase or clearance result."""

    frontier = verify_replacement_frontier(
        frontier_artifact,
        cohort_policy_artifact=cohort_policy_artifact,
        purchase_policy_artifact=purchase_policy_artifact,
    )
    try:
        purchase = verify_case_dev_purchase_policy(purchase_policy_artifact)
    except CaseDevPurchasePolicyError as exc:
        raise ClearanceReplacementError(str(exc)) from exc
    policy = cast(Mapping[str, Any], frontier["policy"])
    candidates = cast(Sequence[Mapping[str, Any]], policy["candidates"])
    return _broad_allowlist_plan(candidates, purchase=purchase)


def plan_clearance_replacements(
    *,
    cohort_policy_artifact: Mapping[str, Any],
    purchase_policy_artifact: Mapping[str, object],
    frontier_artifact: Mapping[str, Any],
    purchase_journal: CaseDevPurchaseJournal,
    purchased_clearance_records: Sequence[Mapping[str, object]],
    clearance_run_card_sha256: str,
) -> ClearanceReplacementPlan:
    """Plan replacements without provider calls or purchase-state mutation."""

    try:
        frontier = verify_replacement_frontier(
            frontier_artifact,
            cohort_policy_artifact=cohort_policy_artifact,
            purchase_policy_artifact=purchase_policy_artifact,
        )
        purchase = verify_case_dev_purchase_policy(purchase_policy_artifact)
        purchase_journal.require_reconciled()
    except (CaseDevPurchasePolicyError, CaseDevPurchaseLedgerError) as exc:
        message = str(exc)
        if "paid outcome" in message:
            message = "unresolved purchase state: " + message
        raise ClearanceReplacementError(message) from exc
    if purchase_journal.policy.policy_sha256 != purchase.policy_sha256:
        raise ClearanceReplacementError(
            "purchase journal is bound to a different purchase policy"
        )
    clearance_run_card = _sha(clearance_run_card_sha256, "clearance_run_card_sha256")
    policy = cast(Mapping[str, Any], frontier["policy"])
    frontier_hash = cast(str, frontier["policy_sha256"])
    candidates = cast(Sequence[Mapping[str, Any]], policy["candidates"])
    candidate_index = {
        cast(str, candidate["candidate_id"]): candidate for candidate in candidates
    }
    initial = tuple(cast(Sequence[str], policy["initial_selected_candidate_ids"]))
    target = cast(int, policy["target_clean_cases"])
    max_per_bucket = cast(int | None, policy["case_mix_max_per_bucket"])

    operations = purchase_journal.operation_records()
    confirmed = {
        (
            cast(str, operation["candidate_id"]),
            cast(str, operation["source_document_id"]),
        ): operation
        for operation in operations
        if operation["status"] == "confirmed"
    }
    clearance = _purchased_clearance_index(purchased_clearance_records)
    if set(clearance) != set(confirmed):
        missing = sorted(set(confirmed) - set(clearance))
        extra = sorted(set(clearance) - set(confirmed))
        raise ClearanceReplacementError(
            "purchased clearance coverage does not match confirmed journal rows; "
            f"missing={missing}; extra={extra}"
        )
    for candidate_id, _ in confirmed:
        if candidate_id not in candidate_index:
            raise ClearanceReplacementError(
                f"purchased candidate is outside the frozen frontier: {candidate_id}"
            )

    quarantine_documents: dict[str, list[str]] = {}
    for (candidate_id, document_id), record in clearance.items():
        if record["status"] == "quarantined":
            quarantine_documents.setdefault(candidate_id, []).append(document_id)

    existing = purchase_journal.replacement_events()
    _verify_existing_events(
        existing,
        cycle_id=purchase.cycle_id,
        cohort_policy_sha256="sha256:" + purchase.cohort_policy_sha256,
        purchase_policy_sha256="sha256:" + purchase.policy_sha256,
        frontier_sha256=frontier_hash,
        projection_sha256=cast(str, policy["projection_sha256"]),
        candidate_index=candidate_index,
        source_commitments=cast(Mapping[str, str], policy["source_commitments"]),
        hard_cap_usd=purchase.hard_cap_usd,
        quarantine_documents=quarantine_documents,
    )
    active = list(initial)
    attempted = set(initial)
    for event in existing:
        quarantined_id = cast(str, event["quarantined_candidate_id"])
        replacement_id = cast(str | None, event["replacement_candidate_id"])
        if quarantined_id not in active:
            raise ClearanceReplacementError(
                "replacement ledger quarantines a candidate outside active cohort"
            )
        active.remove(quarantined_id)
        if replacement_id is not None:
            active.append(replacement_id)
            attempted.add(replacement_id)

    pending_quarantines = [
        candidate_id for candidate_id in active if candidate_id in quarantine_documents
    ]
    derived_exclusions: list[Mapping[str, Any]] = []
    provisional_reservations = Decimal("0.00")
    current_journal_state = "sha256:" + purchase_journal.purchase_state_sha256()

    for quarantined_id in pending_quarantines:
        if quarantined_id not in active:
            continue
        write_off = Decimal(
            purchase_journal.candidate_committed_amount_usd(quarantined_id)
        )
        if write_off <= 0:
            raise ClearanceReplacementError(
                "quarantined purchased candidate lacks journal-derived committed spend"
            )
        active.remove(quarantined_id)
        committed_before = Decimal(purchase_journal.committed_amount_usd)
        headroom_before = (
            purchase.hard_cap_usd - committed_before - provisional_reservations
        )
        counts_before = _case_mix_counts(active, candidate_index=candidate_index)
        replacement: Mapping[str, Any] | None = None
        budget_blocked = False
        event_exclusions: list[Mapping[str, Any]] = []
        for candidate in candidates:
            candidate_id = cast(str, candidate["candidate_id"])
            if candidate_id in attempted or candidate_id in active:
                exclusion = _derived_exclusion(
                    candidate_id,
                    quarantined_id,
                    "already_selected_or_attempted",
                    cast(int, candidate["rank"]),
                )
                derived_exclusions.append(exclusion)
                event_exclusions.append(exclusion)
                continue
            reasons = cast(Sequence[str], candidate["exclusion_reasons"])
            if reasons:
                exclusion = _derived_exclusion(
                    candidate_id,
                    quarantined_id,
                    "frontier_ineligible:" + ",".join(reasons),
                    cast(int, candidate["rank"]),
                )
                derived_exclusions.append(exclusion)
                event_exclusions.append(exclusion)
                continue
            binding = _binding_case_mix_bucket(
                candidate,
                counts=counts_before,
                max_per_bucket=max_per_bucket,
            )
            if binding is not None:
                dimension, bucket = binding
                exclusion = _derived_exclusion(
                    candidate_id,
                    quarantined_id,
                    f"case_mix_cap_reached:{dimension}:{bucket}",
                    cast(int, candidate["rank"]),
                )
                derived_exclusions.append(exclusion)
                event_exclusions.append(exclusion)
                continue
            estimated = Decimal(cast(str, candidate["estimated_cost_usd"]))
            if estimated > headroom_before:
                budget_blocked = True
                exclusion = _derived_exclusion(
                    candidate_id,
                    quarantined_id,
                    "budget_headroom_exhausted",
                    cast(int, candidate["rank"]),
                )
                derived_exclusions.append(exclusion)
                event_exclusions.append(exclusion)
                continue
            replacement = candidate
            break

        replacement_id = (
            None if replacement is None else cast(str, replacement["candidate_id"])
        )
        replacement_cost = (
            None
            if replacement is None
            else Decimal(cast(str, replacement["estimated_cost_usd"]))
        )
        if replacement is not None:
            assert replacement_id is not None and replacement_cost is not None
            active.append(replacement_id)
            attempted.add(replacement_id)
            provisional_reservations += replacement_cost
        stop_reason = (
            "target_reached"
            if len(active) == target
            else "budget_headroom_exhausted"
            if budget_blocked
            else "frontier_exhausted"
        )
        counts_after = _case_mix_counts(active, candidate_index=candidate_index)
        event_payload: dict[str, Any] = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "cycle_id": purchase.cycle_id,
            "cohort_policy_sha256": "sha256:" + purchase.cohort_policy_sha256,
            "purchase_policy_sha256": "sha256:" + purchase.policy_sha256,
            "frontier_sha256": frontier_hash,
            "projection_sha256": policy["projection_sha256"],
            "source_commitments": policy["source_commitments"],
            "clearance_run_card_sha256": clearance_run_card,
            "purchase_journal_state_sha256": current_journal_state,
            "quarantined_candidate_id": quarantined_id,
            "quarantined_document_ids": sorted(quarantine_documents[quarantined_id]),
            "replacement_candidate_id": replacement_id,
            "replacement_rank": (None if replacement is None else replacement["rank"]),
            "write_off_cost_usd": _money(write_off),
            "replacement_cost_usd": (
                None if replacement_cost is None else _money(replacement_cost)
            ),
            "committed_spend_before_usd": _money(committed_before),
            "headroom_before_usd": _money(headroom_before),
            "headroom_after_usd": _money(
                headroom_before
                - (replacement_cost if replacement_cost is not None else Decimal("0"))
            ),
            "attempted_candidate_ids": sorted(attempted),
            "case_mix_counts_before": counts_before,
            "case_mix_counts_after": counts_after,
            "stop_reason": stop_reason,
            "derived_exclusions": [dict(row) for row in event_exclusions],
        }
        event_key = _prefixed_hash(
            {
                "cycle_id": purchase.cycle_id,
                "frontier_sha256": frontier_hash,
                "clearance_run_card_sha256": clearance_run_card,
                "quarantined_candidate_id": quarantined_id,
                "quarantined_document_ids": sorted(
                    quarantine_documents[quarantined_id]
                ),
            }
        )
        try:
            purchase_journal.append_replacement_event(event_key, event_payload)
        except CaseDevPurchaseLedgerError as exc:
            raise ClearanceReplacementError(str(exc)) from exc

    ledger_records = purchase_journal.replacement_events()
    if len(active) == target:
        final_stop_reason = "target_reached"
    elif ledger_records:
        final_stop_reason = cast(str, ledger_records[-1]["stop_reason"])
    else:
        final_stop_reason = "target_reached"
    recorded_replacement_ids = tuple(
        cast(str, event["replacement_candidate_id"])
        for event in ledger_records
        if event.get("replacement_candidate_id") is not None
    )
    operation_status = {
        cast(str, operation["source_document_id"]): cast(str, operation["status"])
        for operation in operations
    }
    recorded_plans = tuple(
        _candidate_plan(candidate_index[candidate_id])
        for candidate_id in recorded_replacement_ids
        if any(
            operation_status.get(document_id) in {None, "planned"}
            for document_id in cast(
                Sequence[str], candidate_index[candidate_id]["purchase_document_ids"]
            )
        )
    )
    recorded_exclusions = tuple(
        cast(Mapping[str, Any], exclusion)
        for event in ledger_records
        for exclusion in _sequence(
            event.get("derived_exclusions", []), "derived_exclusions"
        )
        if isinstance(exclusion, Mapping)
    )
    replacement_plan = MissingCoreBudgetPlan(
        case_plans=recorded_plans,
        cost_per_document=purchase.per_document_reservation_usd,
        max_projected_budget=purchase.hard_cap_usd,
        max_missing_core_documents_per_case=_max_documents_per_case(purchase),
        dry_run=False,
        target_case_count=len(recorded_plans) if recorded_plans else None,
    )
    broker_allowlist_plan = build_broad_broker_allowlist_plan(
        cohort_policy_artifact=cohort_policy_artifact,
        purchase_policy_artifact=purchase_policy_artifact,
        frontier_artifact=frontier_artifact,
    )
    return ClearanceReplacementPlan(
        active_candidate_ids=tuple(active),
        replacement_plan=replacement_plan,
        broker_allowlist_plan=broker_allowlist_plan,
        ledger_records=ledger_records,
        derived_exclusions=recorded_exclusions,
        stop_reason=final_stop_reason,
        frontier_sha256=frontier_hash,
        purchase_journal_state_sha256=(
            "sha256:" + purchase_journal.purchase_state_sha256()
        ),
    )


def _frontier_candidate(
    row: Mapping[str, object], *, rank: int, require_rank: bool = False
) -> dict[str, Any]:
    allowed = {
        "rank",
        "candidate_id",
        "purchase_document_ids",
        "missing_core_document_count",
        "estimated_purchase_count",
        "missing_core_roles",
        "estimated_cost_usd",
        "exclusion_reasons",
        *_CASE_MIX_DIMENSIONS,
    }
    unknown = set(row) - allowed
    if unknown:
        raise ClearanceReplacementError(
            "replacement candidate has unexpected fields: " + ", ".join(sorted(unknown))
        )
    if require_rank and row.get("rank") != rank:
        raise ClearanceReplacementError(
            "replacement frontier rank sequence is not canonical"
        )
    candidate_id = _canonical_text(row.get("candidate_id"), "candidate_id")
    documents = _canonical_unique_strings(
        _sequence(row.get("purchase_document_ids"), "purchase_document_ids"),
        "purchase_document_ids",
    )
    count = _nonnegative_int(
        row.get("missing_core_document_count"), "missing_core_document_count"
    )
    estimated_count = _nonnegative_int(
        row.get("estimated_purchase_count"), "estimated_purchase_count"
    )
    if count != len(documents) or estimated_count != count:
        raise ClearanceReplacementError(
            f"candidate {candidate_id} purchase document count is inconsistent"
        )
    roles = _canonical_unique_strings(
        _sequence(row.get("missing_core_roles"), "missing_core_roles"),
        "missing_core_roles",
    )
    exclusions = _canonical_unique_strings(
        _sequence(row.get("exclusion_reasons"), "exclusion_reasons"),
        "exclusion_reasons",
    )
    estimated_cost = _usd(row.get("estimated_cost_usd"), "estimated_cost_usd")
    output: dict[str, Any] = {
        "rank": rank,
        "candidate_id": candidate_id,
        "purchase_document_ids": list(documents),
        "missing_core_document_count": count,
        "estimated_purchase_count": estimated_count,
        "missing_core_roles": list(roles),
        "estimated_cost_usd": _money(estimated_cost),
        "exclusion_reasons": list(exclusions),
    }
    for dimension in _CASE_MIX_DIMENSIONS:
        value = row.get(dimension)
        output[dimension] = None if value is None else _canonical_text(value, dimension)
    return output


def _purchased_clearance_index(
    records: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    output: dict[tuple[str, str], Mapping[str, object]] = {}
    for record in records:
        if record.get("schema_version") != "legalforecast.disclosure_clearance.v1":
            raise ClearanceReplacementError("unsupported purchased clearance schema")
        if record.get("free_or_purchased") != "purchased":
            raise ClearanceReplacementError(
                "replacement loop accepts purchased clearance rows only"
            )
        candidate_id = _canonical_text(record.get("candidate_id"), "candidate_id")
        document_id = _canonical_text(
            record.get("source_document_id"), "source_document_id"
        )
        status = record.get("status")
        if status not in {"cleared", "quarantined"}:
            raise ClearanceReplacementError("purchased clearance status is invalid")
        _sha(record.get("sha256"), "clearance sha256")
        if (
            not isinstance(record.get("byte_count"), int)
            or isinstance(record.get("byte_count"), bool)
            or cast(int, record["byte_count"]) <= 0
        ):
            raise ClearanceReplacementError("clearance byte_count must be positive")
        key = (candidate_id, document_id)
        if key in output:
            raise ClearanceReplacementError("duplicate purchased clearance row")
        output[key] = record
    return output


def _verify_existing_events(
    events: Sequence[Mapping[str, Any]],
    *,
    cycle_id: str,
    cohort_policy_sha256: str,
    purchase_policy_sha256: str,
    frontier_sha256: str,
    projection_sha256: str,
    candidate_index: Mapping[str, Mapping[str, Any]],
    source_commitments: Mapping[str, str],
    hard_cap_usd: Decimal,
    quarantine_documents: Mapping[str, Sequence[str]],
) -> None:
    expected_fields = {
        "schema_version",
        "cycle_id",
        "cohort_policy_sha256",
        "purchase_policy_sha256",
        "frontier_sha256",
        "projection_sha256",
        "source_commitments",
        "clearance_run_card_sha256",
        "purchase_journal_state_sha256",
        "quarantined_candidate_id",
        "quarantined_document_ids",
        "replacement_candidate_id",
        "replacement_rank",
        "write_off_cost_usd",
        "replacement_cost_usd",
        "committed_spend_before_usd",
        "headroom_before_usd",
        "headroom_after_usd",
        "attempted_candidate_ids",
        "case_mix_counts_before",
        "case_mix_counts_after",
        "stop_reason",
        "derived_exclusions",
        "event_key",
        "sequence",
        "previous_record_sha256",
        "record_sha256",
    }
    for event in events:
        _exact_keys(event, expected_fields, "replacement ledger event")
        expected = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "cycle_id": cycle_id,
            "cohort_policy_sha256": cohort_policy_sha256,
            "purchase_policy_sha256": purchase_policy_sha256,
            "frontier_sha256": frontier_sha256,
            "projection_sha256": projection_sha256,
        }
        if any(event.get(key) != value for key, value in expected.items()):
            raise ClearanceReplacementError(
                "replacement ledger hash binding conflicts with supplied artifacts"
            )
        if event.get("source_commitments") != source_commitments:
            raise ClearanceReplacementError(
                "replacement ledger source commitments conflict with frontier"
            )
        _sha(
            event.get("purchase_journal_state_sha256"),
            "purchase_journal_state_sha256",
        )
        event_clearance_run_card = _sha(
            event.get("clearance_run_card_sha256"),
            "clearance_run_card_sha256",
        )
        for field in ("quarantined_candidate_id", "replacement_candidate_id"):
            value = event.get(field)
            if value is not None and value not in candidate_index:
                raise ClearanceReplacementError(
                    f"replacement ledger {field} is outside frozen frontier"
                )
        quarantined_id = _canonical_text(
            event.get("quarantined_candidate_id"), "quarantined_candidate_id"
        )
        event_documents = _canonical_unique_strings(
            _sequence(
                event.get("quarantined_document_ids"), "quarantined_document_ids"
            ),
            "quarantined_document_ids",
        )
        expected_documents = tuple(sorted(quarantine_documents.get(quarantined_id, ())))
        if tuple(sorted(event_documents)) != expected_documents:
            raise ClearanceReplacementError(
                "replacement ledger quarantine documents conflict with clearance"
            )
        replacement_id = cast(str | None, event.get("replacement_candidate_id"))
        replacement_cost_value = event.get("replacement_cost_usd")
        replacement_rank = event.get("replacement_rank")
        if replacement_id is None:
            if replacement_cost_value is not None or replacement_rank is not None:
                raise ClearanceReplacementError(
                    "replacement ledger absent candidate has cost or rank"
                )
            replacement_cost = Decimal("0.00")
        else:
            candidate = candidate_index[replacement_id]
            if replacement_rank != candidate["rank"]:
                raise ClearanceReplacementError(
                    "replacement ledger candidate rank conflicts with frontier"
                )
            replacement_cost = _usd(replacement_cost_value, "replacement_cost_usd")
            if replacement_cost != Decimal(cast(str, candidate["estimated_cost_usd"])):
                raise ClearanceReplacementError(
                    "replacement ledger candidate cost conflicts with frontier"
                )
        write_off = _usd(event.get("write_off_cost_usd"), "write_off_cost_usd")
        committed = _usd(
            event.get("committed_spend_before_usd"),
            "committed_spend_before_usd",
        )
        headroom_before = _usd(event.get("headroom_before_usd"), "headroom_before_usd")
        headroom_after = _usd(event.get("headroom_after_usd"), "headroom_after_usd")
        if write_off <= 0 or committed > hard_cap_usd:
            raise ClearanceReplacementError(
                "replacement ledger write-off or committed spend is invalid"
            )
        if headroom_after != headroom_before - replacement_cost:
            raise ClearanceReplacementError(
                "replacement ledger headroom arithmetic is inconsistent"
            )
        attempted = _canonical_unique_strings(
            _sequence(event.get("attempted_candidate_ids"), "attempted_candidate_ids"),
            "attempted_candidate_ids",
        )
        if quarantined_id not in attempted or (
            replacement_id is not None and replacement_id not in attempted
        ):
            raise ClearanceReplacementError(
                "replacement ledger attempted candidates are incomplete"
            )
        if event.get("stop_reason") not in {
            "target_reached",
            "frontier_exhausted",
            "budget_headroom_exhausted",
        }:
            raise ClearanceReplacementError("replacement ledger stop_reason is invalid")
        raw_exclusions = _sequence(
            event.get("derived_exclusions"), "derived_exclusions"
        )
        if any(not isinstance(item, Mapping) for item in raw_exclusions):
            raise ClearanceReplacementError(
                "replacement ledger derived exclusions are invalid"
            )
        expected_event_key = _prefixed_hash(
            {
                "cycle_id": cycle_id,
                "frontier_sha256": frontier_sha256,
                "clearance_run_card_sha256": event_clearance_run_card,
                "quarantined_candidate_id": quarantined_id,
                "quarantined_document_ids": sorted(event_documents),
            }
        )
        if event.get("event_key") != expected_event_key:
            raise ClearanceReplacementError(
                "replacement ledger event identity conflicts with bound inputs"
            )


def _case_mix_counts(
    candidate_ids: Sequence[str],
    *,
    candidate_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {
        dimension: {} for dimension in _CASE_MIX_DIMENSIONS
    }
    for candidate_id in candidate_ids:
        candidate = candidate_index[candidate_id]
        for dimension in _CASE_MIX_DIMENSIONS:
            bucket = candidate.get(dimension)
            if isinstance(bucket, str):
                output[dimension][bucket] = output[dimension].get(bucket, 0) + 1
    return output


def _binding_case_mix_bucket(
    candidate: Mapping[str, Any],
    *,
    counts: Mapping[str, Mapping[str, int]],
    max_per_bucket: int | None,
) -> tuple[str, str] | None:
    if max_per_bucket is None:
        return None
    for dimension in _CASE_MIX_DIMENSIONS:
        bucket = candidate.get(dimension)
        if (
            isinstance(bucket, str)
            and counts.get(dimension, {}).get(bucket, 0) >= max_per_bucket
        ):
            return dimension, bucket
    return None


def _candidate_plan(
    candidate: Mapping[str, Any], *, dry_run: bool = False
) -> CaseMissingCorePurchasePlan:
    return CaseMissingCorePurchasePlan(
        candidate_id=cast(str, candidate["candidate_id"]),
        purchase_document_ids=tuple(
            cast(Sequence[str], candidate["purchase_document_ids"])
        ),
        missing_core_document_count=cast(int, candidate["missing_core_document_count"]),
        estimated_cost=Decimal(cast(str, candidate["estimated_cost_usd"])),
        audit_only_document_count=0,
        dry_run=dry_run,
        exclusion_reasons=tuple(cast(Sequence[str], candidate["exclusion_reasons"])),
        missing_core_roles=tuple(cast(Sequence[str], candidate["missing_core_roles"])),
    )


def _broad_allowlist_plan(
    candidates: Sequence[Mapping[str, Any]], *, purchase: Any
) -> MissingCoreBudgetPlan:
    plans = tuple(
        _candidate_plan(candidate, dry_run=True)
        for candidate in candidates
        if not candidate["exclusion_reasons"] and candidate["purchase_document_ids"]
    )
    # The broker's dynamic journal enforces the immutable Cycle cap. The broad
    # allowlist is intentionally not an executable iteration and may contain a
    # frontier whose aggregate hypothetical cost exceeds that cap.
    return MissingCoreBudgetPlan(
        case_plans=plans,
        cost_per_document=purchase.per_document_reservation_usd,
        max_projected_budget=purchase.hard_cap_usd,
        max_missing_core_documents_per_case=_max_documents_per_case(purchase),
        dry_run=True,
    )


def _max_documents_per_case(purchase: Any) -> int:
    return max(
        1, int(purchase.max_per_case_usd / purchase.per_document_reservation_usd)
    )


def _verify_candidate_costs(
    candidates: Sequence[Mapping[str, Any]], *, purchase_policy: Any
) -> None:
    max_documents = _max_documents_per_case(purchase_policy)
    for candidate in candidates:
        count = cast(int, candidate["missing_core_document_count"])
        expected = purchase_policy.per_document_reservation_usd * count
        actual = Decimal(cast(str, candidate["estimated_cost_usd"]))
        if actual != expected:
            raise ClearanceReplacementError(
                f"candidate {candidate['candidate_id']} estimated cost does not "
                "equal the frozen per-document reservation"
            )
        if count > max_documents:
            raise ClearanceReplacementError(
                f"candidate {candidate['candidate_id']} exceeds the frozen per-case cap"
            )


def _derived_exclusion(
    candidate_id: str, replaced_candidate_id: str, reason: str, rank: int
) -> Mapping[str, Any]:
    return {
        "schema_version": "legalforecast.clearance_replacement_exclusion.v1",
        "candidate_id": candidate_id,
        "stage": "disclosure_clearance_replacement",
        "reason": reason,
        "replacement_for_candidate_id": replaced_candidate_id,
        "frontier_rank": rank,
    }


def _target_clean_cases(policy: Mapping[str, Any]) -> int:
    stop = policy.get("stop_rule")
    if not isinstance(stop, Mapping):
        raise ClearanceReplacementError("cohort stop_rule must be an object")
    typed_stop = cast(Mapping[str, Any], stop)
    return _positive_int(typed_stop.get("target_clean_cases"), "target_clean_cases")


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise ClearanceReplacementError(
            f"{label} fields differ; missing={missing}; extra={extra}"
        )


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ClearanceReplacementError(f"{field} must be a list")
    return cast(Sequence[object], value)


def _canonical_unique_strings(values: Sequence[object], field: str) -> tuple[str, ...]:
    output = tuple(_canonical_text(value, field) for value in values)
    if len(output) != len(set(output)):
        raise ClearanceReplacementError(f"{field} values must be unique")
    return output


def _canonical_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ClearanceReplacementError(f"{field} must be a canonical non-empty string")
    return value


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ClearanceReplacementError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ClearanceReplacementError(f"{field} must be a nonnegative integer")
    return value


def _usd(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or _USD.fullmatch(value) is None:
        raise ClearanceReplacementError(
            f"{field} must be canonical nonnegative two-decimal USD"
        )
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ClearanceReplacementError(f"{field} is invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise ClearanceReplacementError(f"{field} is invalid")
    return amount


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ClearanceReplacementError(f"{field} must be a SHA-256 commitment")
    return "sha256:" + value.removeprefix("sha256:")


def _prefixed_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

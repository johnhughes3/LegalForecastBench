"""Provider-free approval for one exact clearance-replacement purchase tranche."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    require_approved_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.clearance_replacement import (
    RESULT_SCHEMA_VERSION as CLEARANCE_RESULT_SCHEMA_VERSION,
)
from legalforecast.ingestion.clearance_replacement import (
    ClearanceReplacementError,
    verify_replacement_frontier,
)
from legalforecast.ingestion.cohort_policy import CohortPolicyError
from legalforecast.ingestion.disclosure_review_bundle import read_unique_regular_file
from legalforecast.ingestion.docket_decision_text_source import (
    DocketDecisionTextSourceError,
    validate_terminal_purchase_disposition_record,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    AUTHENTICATED_RESULT_SCHEMA_VERSION as _AUTHENTICATED_RANKED_RESERVE_RESULT_SCHEMA,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    REPLACEMENT_EVENT_SCHEMA_VERSION as _RANKED_RESERVE_EVENT_SCHEMA,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    RESULT_SCHEMA_VERSION as _RANKED_RESERVE_RESULT_SCHEMA,
)

REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA = (
    "legalforecast.replacement_purchase_approval_checkpoint.v1"
)
REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA = (
    "legalforecast.replacement_purchase_approval_run_card.v1"
)
REPLACEMENT_APPROVAL_SCHEMA = "legalforecast.replacement_purchase_approval.v1"
REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA_V2 = (
    "legalforecast.replacement_purchase_approval_checkpoint.v2"
)
REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA_V2 = (
    "legalforecast.replacement_purchase_approval_run_card.v2"
)
REPLACEMENT_APPROVAL_SCHEMA_V2 = "legalforecast.replacement_purchase_approval.v2"

_SOURCE_AUTHORITY_KINDS = frozenset({"clearance_frontier", "ranked_reserve_projection"})
_RANKED_RESERVE_BUDGET_FIELDS = frozenset(
    {
        "dry_run",
        "cost_per_document_usd",
        "max_projected_budget_usd",
        "max_missing_core_documents_per_case",
        "total_missing_core_documents",
        "total_estimated_cost_usd",
        "frontier_truncated",
        "omitted_candidate_ids",
        "frontier_rows",
        "case_plans",
        "excluded_case_plans",
        "target_case_count",
        "target_case_count_met",
    }
)
_RANKED_RESERVE_CASE_PLAN_FIELDS = frozenset(
    {
        "candidate_id",
        "purchase_document_ids",
        "missing_core_document_count",
        "estimated_purchase_count",
        "missing_core_roles",
        "estimated_cost_usd",
        "audit_only_document_count",
        "dry_run",
        "exclusion_reasons",
    }
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")
_DECISIONS = frozenset({"approve", "reject"})


class ReplacementPurchaseApprovalError(ValueError):
    """Raised when an exact replacement tranche lacks valid successor authority."""


@dataclass(frozen=True, slots=True)
class ReplacementPurchaseApprovalRequest:
    """Exact provider-free facts requiring a new human decision."""

    cycle_id: str
    cohort_policy_sha256: str
    initial_purchase_policy_sha256: str
    initial_approval_sha256: str
    frontier_sha256: str
    replacement_result_sha256: str
    replacement_budget_plan_sha256: str
    replacement_selection_sha256: str
    purchase_journal_state_sha256: str
    purchase_ledger_path: str
    purchase_ledger_initialization_receipt_path: str
    purchase_ledger_initialization_receipt_sha256: str
    committed_spend_usd: str
    hard_cap_usd: str
    max_per_case_usd: str
    remaining_headroom_before_usd: str
    tranche_projected_cost_usd: str
    remaining_headroom_after_usd: str
    candidate_headroom: tuple[tuple[str, str, str, str, str], ...]
    replacement_candidate_ids: tuple[str, ...]
    purchase_document_ids: tuple[str, ...]
    replacement_event_record_sha256s: tuple[str, ...]
    baseline_operation_record_sha256s: tuple[str, ...] = ()
    session_scope: str = "exact_replacement_tranche_one_global_session"
    fallback: str = "stop_without_replacement_purchase"
    source_authority_kind: str | None = None
    source_authority_sha256: str | None = None

    def to_record(self) -> dict[str, object]:
        """Return canonical request bytes committed by the private checkpoint."""

        if self.source_authority_kind is None:
            if self.source_authority_sha256 is not None:
                raise ReplacementPurchaseApprovalError(
                    "legacy authority cannot be mixed with a v2 source commitment"
                )
            authority_kind: str | None = None
            authority_sha256: str | None = None
        else:
            authority_kind = _source_authority_kind(self.source_authority_kind)
            if self.source_authority_sha256 is None:
                raise ReplacementPurchaseApprovalError(
                    "replacement source authority requires a SHA-256"
                )
            authority_sha256 = _sha(
                self.source_authority_sha256, "source_authority_sha256"
            )
            if (
                authority_sha256 != self.source_authority_sha256
                or authority_sha256 != self.frontier_sha256
            ):
                raise ReplacementPurchaseApprovalError(
                    "replacement source authority SHA-256 is not canonical"
                )
        record: dict[str, object] = {
            "cycle_id": self.cycle_id,
            "cohort_policy_sha256": self.cohort_policy_sha256,
            "initial_purchase_policy_sha256": self.initial_purchase_policy_sha256,
            "initial_approval_sha256": self.initial_approval_sha256,
            "replacement_result_sha256": self.replacement_result_sha256,
            "replacement_budget_plan_sha256": (self.replacement_budget_plan_sha256),
            "replacement_selection_sha256": self.replacement_selection_sha256,
            "purchase_journal_state_sha256": self.purchase_journal_state_sha256,
            "purchase_ledger_path": self.purchase_ledger_path,
            "purchase_ledger_initialization_receipt_path": (
                self.purchase_ledger_initialization_receipt_path
            ),
            "purchase_ledger_initialization_receipt_sha256": (
                self.purchase_ledger_initialization_receipt_sha256
            ),
            "committed_spend_usd": self.committed_spend_usd,
            "hard_cap_usd": self.hard_cap_usd,
            "max_per_case_usd": self.max_per_case_usd,
            "remaining_headroom_before_usd": self.remaining_headroom_before_usd,
            "tranche_projected_cost_usd": self.tranche_projected_cost_usd,
            "remaining_headroom_after_usd": self.remaining_headroom_after_usd,
            "candidate_headroom": [
                {
                    "candidate_id": candidate_id,
                    "committed_spend_usd": committed,
                    "remaining_headroom_before_usd": before,
                    "approved_tranche_cost_usd": approved,
                    "remaining_headroom_after_usd": after,
                }
                for candidate_id, committed, before, approved, after in (
                    self.candidate_headroom
                )
            ],
            "replacement_candidate_ids": list(self.replacement_candidate_ids),
            "purchase_document_ids": list(self.purchase_document_ids),
            "replacement_event_record_sha256s": list(
                self.replacement_event_record_sha256s
            ),
            "baseline_operation_record_sha256s": list(
                self.baseline_operation_record_sha256s
            ),
            "session_scope": self.session_scope,
            "fallback": self.fallback,
        }
        if authority_kind is None:
            record["frontier_sha256"] = self.frontier_sha256
        else:
            record["source_authority_kind"] = authority_kind
            record["source_authority_sha256"] = authority_sha256
        return record

    @property
    def evidence_schema_version(self) -> int:
        """Return the closed private/public evidence schema generation."""

        return 1 if self.source_authority_kind is None else 2

    @property
    def request_sha256(self) -> str:
        return _canonical_sha256(self.to_record())

    def required_confirmation(self, decision: str) -> str:
        normalized = _decision(decision)
        return (
            f"{normalized.upper()} REPLACEMENT {self.cycle_id} "
            f"{self.request_sha256} {self.tranche_projected_cost_usd} "
            f"CAP {self.hard_cap_usd} EXACT_TRANCHE STOP_ON_MISMATCH"
        )


_VERIFIED_REPLACEMENT_APPROVAL_MINT = object()


@dataclass(frozen=True, slots=True, init=False)
class VerifiedReplacementPurchaseApproval:
    """Replay-verified successor approval safe to publish as a public sidecar."""

    request: ReplacementPurchaseApprovalRequest
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise ReplacementPurchaseApprovalError(
            "VerifiedReplacementPurchaseApproval can be created only by evidence replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint_token is _VERIFIED_REPLACEMENT_APPROVAL_MINT


def _mint_verified_replacement_purchase_approval(
    *,
    request: ReplacementPurchaseApprovalRequest,
    reviewer_id: str,
    recorded_at_utc: str,
    typed_confirmation_sha256: str,
    checkpoint_sha256: str,
    run_card_sha256: str,
) -> VerifiedReplacementPurchaseApproval:
    instance = object.__new__(VerifiedReplacementPurchaseApproval)
    object.__setattr__(instance, "request", request)
    object.__setattr__(instance, "reviewer_id", reviewer_id)
    object.__setattr__(instance, "recorded_at_utc", recorded_at_utc)
    object.__setattr__(instance, "typed_confirmation_sha256", typed_confirmation_sha256)
    object.__setattr__(instance, "checkpoint_sha256", checkpoint_sha256)
    object.__setattr__(instance, "run_card_sha256", run_card_sha256)
    object.__setattr__(instance, "_mint_token", _VERIFIED_REPLACEMENT_APPROVAL_MINT)
    return instance


def build_replacement_purchase_approval_request(
    *,
    cohort_policy_path: Path,
    initial_purchase_policy_path: Path,
    initial_controlled_private_root: Path,
    frontier_path: Path | None,
    replacement_result_path: Path,
    replacement_budget_plan_path: Path,
    replacement_selection_path: Path,
    purchase_ledger_path: Path,
    purchase_ledger_initialization_receipt_path: Path,
    source_authority_kind: str | None = None,
    source_authority_sha256: str | None = None,
) -> ReplacementPurchaseApprovalRequest:
    """Reproduce one exact ranked tranche against the existing Cycle ledger.

    This function performs no provider call, fee acknowledgement, or purchase.
    The initial approval authenticates only the common policy/cap identity; it
    is deliberately not treated as authority for the replacement tranche.
    Ranked-reserve callers must supply the projection digest returned by their
    full authenticated projection replay.  This function then binds that digest
    directly to the ranked result and canonical replacement-event journal.
    """

    authority_kind = _optional_source_authority_kind(source_authority_kind)
    if authority_kind is None and source_authority_sha256 is not None:
        raise ReplacementPurchaseApprovalError(
            "legacy authority cannot be mixed with a v2 source commitment"
        )
    if authority_kind == "ranked_reserve_projection" and frontier_path is not None:
        raise ReplacementPurchaseApprovalError(
            "ranked-reserve authority cannot be mixed with a clearance frontier"
        )
    if authority_kind != "ranked_reserve_projection" and frontier_path is None:
        raise ReplacementPurchaseApprovalError(
            "clearance-frontier authority requires the exact frontier artifact"
        )
    if (
        authority_kind == "ranked_reserve_projection"
        and source_authority_sha256 is None
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked-reserve authority requires the replayed projection SHA-256"
        )

    cohort_bytes = read_unique_regular_file(cohort_policy_path)
    policy_bytes = read_unique_regular_file(initial_purchase_policy_path)
    result_bytes = read_unique_regular_file(replacement_result_path)
    budget_bytes = read_unique_regular_file(replacement_budget_plan_path)
    selection_bytes = read_unique_regular_file(replacement_selection_path)
    initialization_receipt = purchase_ledger_initialization_receipt_path.resolve()
    initialization_receipt_bytes = read_unique_regular_file(initialization_receipt)
    cohort = _json_object(cohort_bytes, "cohort policy")
    policy_artifact = _json_object(policy_bytes, "initial purchase policy")
    result = _json_object(result_bytes, "replacement result")
    budget = _json_object(budget_bytes, "replacement budget plan")
    try:
        policy = verify_case_dev_purchase_policy(policy_artifact)
        require_approved_case_dev_purchase_policy(
            policy,
            controlled_private_root=initial_controlled_private_root,
        )
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort)
    except (
        CaseDevPurchasePolicyError,
        ClearanceReplacementError,
        CohortPolicyError,
        OSError,
        ValueError,
    ) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    ledger = purchase_ledger_path.resolve()
    if ledger != policy.canonical_ledger_path:
        raise ReplacementPurchaseApprovalError(
            "replacement approval ledger differs from the initial v2 policy"
        )
    if authority_kind == "ranked_reserve_projection":
        return _build_ranked_reserve_purchase_approval_request(
            policy=policy,
            result=result,
            result_bytes=result_bytes,
            budget=budget,
            budget_bytes=budget_bytes,
            selection_bytes=selection_bytes,
            ledger=ledger,
            initialization_receipt=initialization_receipt,
            initialization_receipt_bytes=initialization_receipt_bytes,
            initial_controlled_private_root=initial_controlled_private_root,
            expected_source_authority_sha256=_sha(
                source_authority_sha256, "source_authority_sha256"
            ),
        )

    assert frontier_path is not None
    frontier_bytes = read_unique_regular_file(frontier_path)
    frontier_artifact = _json_object(frontier_bytes, "replacement frontier")
    try:
        frontier = verify_replacement_frontier(
            frontier_artifact,
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            controlled_private_root=initial_controlled_private_root,
        )
    except (ClearanceReplacementError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    frontier_sha256 = _sha(frontier["policy_sha256"], "frontier_sha256")
    if (
        authority_kind is not None
        and source_authority_sha256 is not None
        and _sha(source_authority_sha256, "source_authority_sha256") != frontier_sha256
    ):
        raise ReplacementPurchaseApprovalError(
            "clearance replacement frontier differs from the source commitment"
        )
    _verify_result_identity(result)
    if result.get("replacement_plan") != budget:
        raise ReplacementPurchaseApprovalError(
            "replacement budget-plan bytes differ from the planned result"
        )
    if result.get("frontier_sha256") != frontier.get("policy_sha256"):
        raise ReplacementPurchaseApprovalError(
            "replacement result is bound to a different frozen frontier"
        )
    if (
        result.get("paid_activity_requested") is not False
        or result.get("paid_activity_executed") is not False
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement planning must have zero paid activity"
        )
    if result.get("replacement_selection_sha256") != (
        "sha256:" + _sha256(selection_bytes)
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement selection differs from the planned result"
        )

    try:
        with CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            read_only=True,
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            state_sha256 = "sha256:" + journal.purchase_state_sha256()
            if result.get("purchase_journal_state_sha256") != state_sha256:
                raise ReplacementPurchaseApprovalError(
                    "replacement result purchase-journal state is stale"
                )
            events = tuple(journal.replacement_events())
            committed = _usd(journal.committed_amount_usd, "committed spend")
            operations = tuple(journal.operation_records())
    except (CaseDevPurchaseLedgerError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    if result.get("ledger_records") != [dict(event) for event in events]:
        raise ReplacementPurchaseApprovalError(
            "replacement result ledger records differ from the canonical journal"
        )

    frontier_policy = cast(Mapping[str, Any], frontier["policy"])
    raw_candidates = cast(Sequence[Mapping[str, Any]], frontier_policy["candidates"])
    candidates = {
        cast(str, candidate["candidate_id"]): candidate for candidate in raw_candidates
    }
    initial = set(
        cast(Sequence[str], frontier_policy["initial_selected_candidate_ids"])
    )
    existing_documents = {
        cast(str, operation["source_document_id"]) for operation in operations
    }
    case_plans = _sequence(budget.get("case_plans"), "replacement case plans")
    if result.get("replacement_selection_count") != len(case_plans):
        raise ReplacementPurchaseApprovalError(
            "replacement selection count differs from the planned result"
        )
    candidate_ids: list[str] = []
    document_ids: list[str] = []
    ranks: list[int] = []
    total_cost = Decimal("0.00")
    for raw_plan in case_plans:
        if not isinstance(raw_plan, Mapping):
            raise ReplacementPurchaseApprovalError(
                "replacement case plan must be an object"
            )
        plan = cast(Mapping[str, object], raw_plan)
        candidate_id = _text(plan.get("candidate_id"), "replacement candidate_id")
        if candidate_id in initial:
            raise ReplacementPurchaseApprovalError(
                "initially approved candidate cannot appear in a successor tranche"
            )
        candidate = candidates.get(candidate_id)
        if candidate is None or candidate.get("exclusion_reasons") != []:
            raise ReplacementPurchaseApprovalError(
                "successor candidate is not eligible in the frozen frontier"
            )
        if plan.get("dry_run") is not False or plan.get("exclusion_reasons") != []:
            raise ReplacementPurchaseApprovalError(
                "replacement tranche must contain executable unexcluded plans"
            )
        documents = _unique_texts(
            _sequence(plan.get("purchase_document_ids"), "purchase document IDs"),
            "purchase document IDs",
        )
        if list(documents) != candidate.get("purchase_document_ids"):
            raise ReplacementPurchaseApprovalError(
                "replacement documents differ from the frozen frontier"
            )
        if any(document_id in existing_documents for document_id in documents):
            raise ReplacementPurchaseApprovalError(
                "replacement tranche repeats an existing purchase operation"
            )
        estimated = _usd(plan.get("estimated_cost_usd"), "replacement cost")
        expected = policy.per_document_reservation_usd * len(documents)
        if estimated != expected or plan.get("missing_core_document_count") != len(
            documents
        ):
            raise ReplacementPurchaseApprovalError(
                "replacement tranche cost or document count is inconsistent"
            )
        candidate_ids.append(candidate_id)
        document_ids.extend(documents)
        ranks.append(cast(int, candidate["rank"]))
        total_cost += estimated
    if not case_plans:
        raise ReplacementPurchaseApprovalError(
            "replacement approval requires a nonempty exact tranche"
        )
    if len(candidate_ids) != len(set(candidate_ids)) or len(document_ids) != len(
        set(document_ids)
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement candidates and documents must be unique"
        )
    if ranks != sorted(ranks):
        raise ReplacementPurchaseApprovalError(
            "replacement tranche is not in deterministic frozen-frontier order"
        )
    event_replacements = [
        cast(str, event["replacement_candidate_id"])
        for event in events
        if event.get("replacement_candidate_id") is not None
    ]
    if candidate_ids != event_replacements[-len(candidate_ids) :]:
        raise ReplacementPurchaseApprovalError(
            "replacement tranche differs from the durable ranked replacement events"
        )
    hard_cap = policy.hard_cap_usd
    headroom_before = hard_cap - committed
    if headroom_before < 0 or total_cost > headroom_before:
        raise ReplacementPurchaseApprovalError(
            "replacement tranche exceeds remaining Cycle headroom"
        )
    raw_approval = policy.approval
    if raw_approval is None:
        raise ReplacementPurchaseApprovalError("initial v2 approval is missing")
    event_hashes = tuple(
        _sha(event.get("record_sha256"), "replacement event record_sha256")
        for event in events
        if event.get("replacement_candidate_id") in set(candidate_ids)
    )
    if len(event_hashes) != len(candidate_ids):
        raise ReplacementPurchaseApprovalError(
            "replacement event coverage differs from the exact tranche"
        )
    approved_costs_by_candidate = {
        candidate_id: _usd(
            cast(Mapping[str, object], raw_plan).get("estimated_cost_usd"),
            "replacement cost",
        )
        for candidate_id, raw_plan in zip(candidate_ids, case_plans, strict=True)
    }
    baseline_candidate_ids = sorted(
        set(candidate_ids)
        | set(policy.opening_case_committed_spend_usd)
        | {cast(str, operation["candidate_id"]) for operation in operations}
    )
    try:
        with CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            read_only=True,
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            if "sha256:" + journal.purchase_state_sha256() != state_sha256:
                raise ReplacementPurchaseApprovalError(
                    "purchase journal changed while snapshotting per-case headroom"
                )
            candidate_headroom = tuple(
                _candidate_headroom_record(
                    candidate_id=candidate_id,
                    committed=_usd(
                        journal.candidate_committed_amount_usd(candidate_id),
                        f"{candidate_id} committed spend",
                    ),
                    approved_cost=approved_costs_by_candidate.get(
                        candidate_id, Decimal("0.00")
                    ),
                    max_per_case=policy.max_per_case_usd,
                )
                for candidate_id in baseline_candidate_ids
            )
    except (CaseDevPurchaseLedgerError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    request = ReplacementPurchaseApprovalRequest(
        cycle_id=policy.cycle_id,
        cohort_policy_sha256=policy.cohort_policy_sha256,
        initial_purchase_policy_sha256=policy.policy_sha256,
        initial_approval_sha256=_canonical_sha256(dict(raw_approval)),
        frontier_sha256=frontier_sha256,
        replacement_result_sha256=_sha256(result_bytes),
        replacement_budget_plan_sha256=_sha256(budget_bytes),
        replacement_selection_sha256=_sha256(selection_bytes),
        purchase_journal_state_sha256=state_sha256,
        purchase_ledger_path=str(ledger),
        purchase_ledger_initialization_receipt_path=str(initialization_receipt),
        purchase_ledger_initialization_receipt_sha256=_sha256(
            initialization_receipt_bytes
        ),
        committed_spend_usd=_money(committed),
        hard_cap_usd=_money(hard_cap),
        max_per_case_usd=_money(policy.max_per_case_usd),
        remaining_headroom_before_usd=_money(headroom_before),
        tranche_projected_cost_usd=_money(total_cost),
        remaining_headroom_after_usd=_money(headroom_before - total_cost),
        candidate_headroom=candidate_headroom,
        replacement_candidate_ids=tuple(candidate_ids),
        purchase_document_ids=tuple(document_ids),
        replacement_event_record_sha256s=event_hashes,
        baseline_operation_record_sha256s=tuple(
            _canonical_sha256(dict(operation)) for operation in operations
        ),
        source_authority_kind=authority_kind,
        source_authority_sha256=(
            frontier_sha256 if authority_kind is not None else None
        ),
    )
    _verify_runtime_budget_plan(request, budget_bytes)
    _verify_runtime_selection(request, selection_bytes, budget_bytes)
    return request


def _build_ranked_reserve_purchase_approval_request(
    *,
    policy: CaseDevPurchasePolicy,
    result: Mapping[str, object],
    result_bytes: bytes,
    budget: Mapping[str, object],
    budget_bytes: bytes,
    selection_bytes: bytes,
    ledger: Path,
    initialization_receipt: Path,
    initialization_receipt_bytes: bytes,
    initial_controlled_private_root: Path,
    expected_source_authority_sha256: str,
) -> ReplacementPurchaseApprovalRequest:
    """Replay ranked-reserve evidence directly against the canonical journal."""

    _verify_ranked_result_identity(result)
    source_sha256 = _sha(
        result.get("projection_sha256"), "ranked source authority SHA-256"
    )
    if source_sha256 != expected_source_authority_sha256:
        raise ReplacementPurchaseApprovalError(
            "ranked replacement result differs from the replayed source authority"
        )
    if (
        result.get("cycle_id") != policy.cycle_id
        or result.get("purchase_policy_sha256") != "sha256:" + policy.policy_sha256
        or result.get("hard_cap_usd") != _money(policy.hard_cap_usd)
        or result.get("replacement_budget_plan_sha256")
        != "sha256:" + _sha256(budget_bytes)
        or result.get("replacement_selection_sha256")
        != "sha256:" + _sha256(selection_bytes)
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement result differs from its policy, budget, or selection"
        )
    case_plans = _sequence(budget.get("case_plans"), "replacement case plans")
    if (
        not case_plans
        or result.get("replacement_case_count") != len(case_plans)
        or result.get("successor_approval_required") is not True
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement result lacks a nonempty exact successor tranche"
        )

    try:
        with CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            read_only=True,
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            state_sha256 = "sha256:" + journal.purchase_state_sha256()
            committed = _usd(journal.committed_amount_usd, "committed spend")
            events = tuple(journal.replacement_events())
            operations = tuple(journal.operation_records())
            if result.get("purchase_journal_state_sha256") != state_sha256:
                raise ReplacementPurchaseApprovalError(
                    "ranked replacement result purchase-journal state is stale"
                )
            event_by_hash = {
                _sha(
                    event.get("record_sha256"), "replacement event record SHA-256"
                ): event
                for event in events
            }
            # The producer rejects every incompatible or cross-projection event
            # before planning. Preserve that Cycle-journal invariant here; the
            # exact successor tranche is scoped separately by its committed hashes.
            if len(event_by_hash) != len(events) or any(
                event.get("schema_version") != _RANKED_RESERVE_EVENT_SCHEMA
                or event.get("projection_sha256") != source_sha256
                for event in events
            ):
                raise ReplacementPurchaseApprovalError(
                    "ranked replacement journal is not bound to one source projection"
                )
            all_event_hashes = tuple(event_by_hash)
            result_event_hashes = tuple(
                _sha(value, "replacement event record SHA-256")
                for value in _sequence(
                    result.get("replacement_event_record_sha256s"),
                    "replacement event record SHA-256s",
                )
            )
            tranche_event_hashes = tuple(
                _sha(value, "tranche event record SHA-256")
                for value in _sequence(
                    result.get("tranche_event_record_sha256s"),
                    "tranche event record SHA-256s",
                )
            )
            if (
                result_event_hashes != all_event_hashes
                or not tranche_event_hashes
                or len(tranche_event_hashes) != len(set(tranche_event_hashes))
                or any(value not in event_by_hash for value in tranche_event_hashes)
            ):
                raise ReplacementPurchaseApprovalError(
                    "ranked replacement event commitments differ from the "
                    "canonical journal"
                )
            tranche_events = tuple(
                event_by_hash[value] for value in tranche_event_hashes
            )
            if "sha256:" + journal.purchase_state_sha256() != state_sha256:
                raise ReplacementPurchaseApprovalError(
                    "purchase journal changed while replaying ranked authority"
                )
    except (CaseDevPurchaseLedgerError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc

    existing_documents = {
        cast(str, operation["source_document_id"]) for operation in operations
    }
    operation_by_document = {
        cast(str, operation["source_document_id"]): operation
        for operation in operations
    }
    canonical_reserved = Decimal("0.00")
    for event in events:
        event_documents = _unique_texts(
            _sequence(
                event.get("purchase_document_ids"),
                "ranked event purchase document IDs",
            ),
            "ranked event purchase document IDs",
        )
        event_cost = _usd(
            event.get("estimated_cost_usd"), "ranked event estimated cost"
        )
        if (
            event_cost != policy.per_document_reservation_usd * len(event_documents)
            or event.get("paid_activity_requested") is not False
            or event.get("paid_activity_executed") is not False
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement journal differs from canonical reservation costs"
            )
        canonical_reserved += sum(
            (
                policy.per_document_reservation_usd
                for document_id in event_documents
                if (
                    (operation := operation_by_document.get(document_id)) is None
                    or not _operation_commits_spend(operation)
                )
            ),
            Decimal("0.00"),
        )
    candidate_ids: list[str] = []
    document_ids: list[str] = []
    document_counts: list[int] = []
    total_cost = Decimal("0.00")
    if len(case_plans) != len(tranche_events):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement event coverage or tranche identity differs"
        )
    for raw_plan, event in zip(case_plans, tranche_events, strict=True):
        plan = _mapping(raw_plan, "replacement case plan")
        if frozenset(plan) != _RANKED_RESERVE_CASE_PLAN_FIELDS:
            raise ReplacementPurchaseApprovalError(
                "ranked replacement case plan fields differ from the canonical producer"
            )
        candidate_id = _text(plan.get("candidate_id"), "replacement candidate_id")
        documents = _unique_texts(
            _sequence(plan.get("purchase_document_ids"), "purchase document IDs"),
            "purchase document IDs",
        )
        _unique_texts(
            _sequence(plan.get("missing_core_roles"), "missing core roles"),
            "missing core roles",
        )
        estimated = _usd(plan.get("estimated_cost_usd"), "replacement cost")
        expected = policy.per_document_reservation_usd * len(documents)
        if (
            event.get("schema_version") != _RANKED_RESERVE_EVENT_SCHEMA
            or event.get("projection_sha256") != source_sha256
            or event.get("promoted_candidate_id") != candidate_id
            or event.get("purchase_document_ids") != list(documents)
            or event.get("estimated_cost_usd") != _money(estimated)
            or event.get("paid_activity_requested") is not False
            or event.get("paid_activity_executed") is not False
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement tranche differs from its durable event"
            )
        if (
            plan.get("dry_run") is not False
            or plan.get("exclusion_reasons") != []
            or plan.get("missing_core_document_count") != len(documents)
            or plan.get("estimated_purchase_count") != len(documents)
            or plan.get("audit_only_document_count") != 0
            or estimated != expected
            or any(document_id in existing_documents for document_id in documents)
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement tranche is not an executable unpurchased plan"
            )
        candidate_ids.append(candidate_id)
        document_ids.extend(documents)
        document_counts.append(len(documents))
        total_cost += estimated
    if len(candidate_ids) != len(set(candidate_ids)) or len(document_ids) != len(
        set(document_ids)
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement event coverage or tranche identity differs"
        )
    if (
        frozenset(budget) != _RANKED_RESERVE_BUDGET_FIELDS
        or budget.get("dry_run") is not False
        or budget.get("cost_per_document_usd")
        != _money(policy.per_document_reservation_usd)
        or budget.get("max_missing_core_documents_per_case") != max(document_counts)
        or budget.get("total_missing_core_documents") != len(document_ids)
        or budget.get("total_estimated_cost_usd") != _money(total_cost)
        or budget.get("frontier_truncated") is not False
        or budget.get("omitted_candidate_ids") != []
        or budget.get("frontier_rows") != []
        or budget.get("excluded_case_plans") != []
        or budget.get("target_case_count") != len(case_plans)
        or budget.get("target_case_count_met") is not True
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement budget totals differ from the exact tranche"
        )
    hard_cap = policy.hard_cap_usd
    prior_reserved = canonical_reserved - total_cost
    if prior_reserved < 0:
        raise ReplacementPurchaseApprovalError(
            "ranked replacement journal omits the exact tranche reservation"
        )
    headroom_before = hard_cap - committed - prior_reserved
    budget_cap = _usd(
        budget.get("max_projected_budget_usd"),
        "replacement maximum projected budget",
    )
    reported_reserved = _usd(
        result.get("reserved_replacement_spend_usd"),
        "ranked reserved replacement spend",
    )
    if reported_reserved != canonical_reserved:
        raise ReplacementPurchaseApprovalError(
            "ranked reserved spend differs from the canonical journal"
        )
    if (
        headroom_before < 0
        or total_cost > headroom_before
        or budget_cap != headroom_before
        or result.get("committed_spend_usd") != _money(committed)
        or result.get("remaining_headroom_usd")
        != _money(hard_cap - committed - canonical_reserved)
    ):
        raise ReplacementPurchaseApprovalError(
            "ranked replacement tranche exceeds or differs from Cycle headroom"
        )
    raw_approval = policy.approval
    if raw_approval is None:
        raise ReplacementPurchaseApprovalError("initial v2 approval is missing")
    approved_costs_by_candidate = {
        candidate_id: _usd(
            _mapping(raw_plan, "replacement case plan").get("estimated_cost_usd"),
            "replacement cost",
        )
        for candidate_id, raw_plan in zip(candidate_ids, case_plans, strict=True)
    }
    baseline_candidate_ids = sorted(
        set(candidate_ids)
        | set(policy.opening_case_committed_spend_usd)
        | {cast(str, operation["candidate_id"]) for operation in operations}
    )
    try:
        with CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            read_only=True,
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            if "sha256:" + journal.purchase_state_sha256() != state_sha256:
                raise ReplacementPurchaseApprovalError(
                    "purchase journal changed while snapshotting per-case headroom"
                )
            candidate_headroom = tuple(
                _candidate_headroom_record(
                    candidate_id=candidate_id,
                    committed=_usd(
                        journal.candidate_committed_amount_usd(candidate_id),
                        f"{candidate_id} committed spend",
                    ),
                    approved_cost=approved_costs_by_candidate.get(
                        candidate_id, Decimal("0.00")
                    ),
                    max_per_case=policy.max_per_case_usd,
                )
                for candidate_id in baseline_candidate_ids
            )
    except (CaseDevPurchaseLedgerError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc

    request = ReplacementPurchaseApprovalRequest(
        cycle_id=policy.cycle_id,
        cohort_policy_sha256=policy.cohort_policy_sha256,
        initial_purchase_policy_sha256=policy.policy_sha256,
        initial_approval_sha256=_canonical_sha256(dict(raw_approval)),
        frontier_sha256=source_sha256,
        replacement_result_sha256=_sha256(result_bytes),
        replacement_budget_plan_sha256=_sha256(budget_bytes),
        replacement_selection_sha256=_sha256(selection_bytes),
        purchase_journal_state_sha256=state_sha256,
        purchase_ledger_path=str(ledger),
        purchase_ledger_initialization_receipt_path=str(initialization_receipt),
        purchase_ledger_initialization_receipt_sha256=_sha256(
            initialization_receipt_bytes
        ),
        committed_spend_usd=_money(committed),
        hard_cap_usd=_money(hard_cap),
        max_per_case_usd=_money(policy.max_per_case_usd),
        remaining_headroom_before_usd=_money(headroom_before),
        tranche_projected_cost_usd=_money(total_cost),
        remaining_headroom_after_usd=_money(headroom_before - total_cost),
        candidate_headroom=candidate_headroom,
        replacement_candidate_ids=tuple(candidate_ids),
        purchase_document_ids=tuple(document_ids),
        replacement_event_record_sha256s=tranche_event_hashes,
        baseline_operation_record_sha256s=tuple(
            _canonical_sha256(dict(operation)) for operation in operations
        ),
        source_authority_kind="ranked_reserve_projection",
        source_authority_sha256=source_sha256,
    )
    _verify_runtime_budget_plan(request, budget_bytes)
    _verify_runtime_selection(request, selection_bytes, budget_bytes)
    if _selection_candidate_ids(selection_bytes) != request.replacement_candidate_ids:
        raise ReplacementPurchaseApprovalError(
            "ranked replacement selection differs from the exact tranche"
        )
    return request


def record_replacement_purchase_approval(
    *,
    request: ReplacementPurchaseApprovalRequest,
    controlled_private_root: Path,
    decision: str,
    typed_confirmation: str,
    reviewer_id: str,
    recorded_at_utc: str,
) -> tuple[Path, Path]:
    """Record a new exact successor decision without provider or paid activity."""

    if _request_from_record(request.to_record()) != request:
        raise ReplacementPurchaseApprovalError(
            "replacement approval request does not canonically replay"
        )
    root = _absolute_root(controlled_private_root)
    normalized_decision = _decision(decision)
    if reviewer_id != "John Hughes":
        raise ReplacementPurchaseApprovalError(
            "official replacement reviewer must be John Hughes"
        )
    recorded = _utc_timestamp(recorded_at_utc)
    if typed_confirmation != request.required_confirmation(normalized_decision):
        raise ReplacementPurchaseApprovalError(
            "typed confirmation does not match the exact replacement request"
        )
    checkpoint_body: dict[str, object] = {
        "request": request.to_record(),
        "decision": normalized_decision,
        "reviewer_id": reviewer_id,
        "recorded_at_utc": recorded,
        "typed_confirmation": typed_confirmation,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    checkpoint = {
        "schema_version": _checkpoint_schema(request),
        "checkpoint": checkpoint_body,
        "checkpoint_sha256": _canonical_sha256(checkpoint_body),
    }
    checkpoint_bytes = _pretty_json(checkpoint)
    checkpoint_path = root / "replacement-purchase-approval-checkpoint.json"
    run_card_body: dict[str, object] = {
        "stage": "record-replacement-purchase-approval",
        "status": "completed",
        "decision": normalized_decision,
        "request_sha256": request.request_sha256,
        "checkpoint_sha256": _sha256(checkpoint_bytes),
        "reviewer_id": reviewer_id,
        "recorded_at_utc": recorded,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    run_card = {
        "schema_version": _run_card_schema(request),
        "run_card": run_card_body,
        "run_card_sha256": _canonical_sha256(run_card_body),
    }
    run_card_path = root / "run-cards" / "record-replacement-purchase-approval.json"
    run_card_bytes = _pretty_json(run_card)
    for path in (checkpoint_path, run_card_path):
        _preflight_private_once(path)
    _write_private_once(checkpoint_path, checkpoint_bytes)
    _write_private_once(run_card_path, run_card_bytes)
    return checkpoint_path, run_card_path


def verify_replacement_purchase_approval(
    *,
    request: ReplacementPurchaseApprovalRequest,
    controlled_private_root: Path,
    checkpoint_path: Path,
    run_card_path: Path,
) -> VerifiedReplacementPurchaseApproval:
    """Replay the exact private successor decision before public publication."""

    root = _absolute_root(controlled_private_root)
    expected_checkpoint = root / "replacement-purchase-approval-checkpoint.json"
    expected_run_card = root / "run-cards" / "record-replacement-purchase-approval.json"
    if checkpoint_path != expected_checkpoint or run_card_path != expected_run_card:
        raise ReplacementPurchaseApprovalError(
            "replacement approval evidence must use exact controlled-store locations"
        )
    checkpoint_bytes = read_unique_regular_file(checkpoint_path)
    run_card_bytes = read_unique_regular_file(run_card_path)
    checkpoint_artifact = _json_object(checkpoint_bytes, "replacement checkpoint")
    run_card_artifact = _json_object(run_card_bytes, "replacement run card")
    if checkpoint_artifact.get("schema_version") != _checkpoint_schema(
        request
    ) or run_card_artifact.get("schema_version") != _run_card_schema(request):
        raise ReplacementPurchaseApprovalError(
            "unsupported replacement approval evidence schema"
        )
    checkpoint = _mapping(checkpoint_artifact.get("checkpoint"), "checkpoint")
    run_card = _mapping(run_card_artifact.get("run_card"), "run card")
    if checkpoint_artifact.get("checkpoint_sha256") != _canonical_sha256(checkpoint):
        raise ReplacementPurchaseApprovalError("replacement checkpoint hash differs")
    if run_card_artifact.get("run_card_sha256") != _canonical_sha256(run_card):
        raise ReplacementPurchaseApprovalError("replacement run-card hash differs")
    if checkpoint.get("request") != request.to_record():
        raise ReplacementPurchaseApprovalError(
            "replacement approval request or current journal state changed"
        )
    decision = _decision(checkpoint.get("decision"))
    if decision != "approve":
        raise ReplacementPurchaseApprovalError(
            f"{decision} does not authorize replacement purchases"
        )
    reviewer = _text(checkpoint.get("reviewer_id"), "reviewer_id")
    if reviewer != "John Hughes":
        raise ReplacementPurchaseApprovalError(
            "official replacement reviewer must be John Hughes"
        )
    recorded = _utc_timestamp(checkpoint.get("recorded_at_utc"))
    confirmation = _text(checkpoint.get("typed_confirmation"), "typed confirmation")
    if confirmation != request.required_confirmation(decision):
        raise ReplacementPurchaseApprovalError(
            "replacement approval confirmation differs"
        )
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if checkpoint.get(field) is not False or run_card.get(field) is not False:
            raise ReplacementPurchaseApprovalError(
                "replacement approval activity flags are invalid"
            )
    if run_card != {
        "stage": "record-replacement-purchase-approval",
        "status": "completed",
        "decision": decision,
        "request_sha256": request.request_sha256,
        "checkpoint_sha256": _sha256(checkpoint_bytes),
        "reviewer_id": reviewer,
        "recorded_at_utc": recorded,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }:
        raise ReplacementPurchaseApprovalError(
            "replacement approval run card does not replay"
        )
    return _mint_verified_replacement_purchase_approval(
        request=request,
        reviewer_id=reviewer,
        recorded_at_utc=recorded,
        typed_confirmation_sha256=_sha256(confirmation.encode()),
        checkpoint_sha256=_sha256(checkpoint_bytes),
        run_card_sha256=_sha256(run_card_bytes),
    )


def generate_replacement_purchase_authority(
    approval: VerifiedReplacementPurchaseApproval,
) -> dict[str, object]:
    """Publish exact successor authority without changing the initial v2 policy."""

    if (
        type(approval) is not VerifiedReplacementPurchaseApproval
        or not approval.is_replay_minted()
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement authority can be minted only from private evidence replay"
        )
    schema = _authority_schema(approval.request)
    body = {
        "schema_version": schema,
        "decision": "approve",
        "reviewer_id": approval.reviewer_id,
        "recorded_at_utc": approval.recorded_at_utc,
        "typed_confirmation_sha256": approval.typed_confirmation_sha256,
        "private_checkpoint_sha256": approval.checkpoint_sha256,
        "private_run_card_sha256": approval.run_card_sha256,
        "request": approval.request.to_record(),
    }
    return {
        "schema_version": schema,
        "authority": body,
        "authority_sha256": _canonical_sha256(body),
    }


def verify_replacement_purchase_authority(
    *,
    authority_artifact: Mapping[str, object],
    controlled_private_root: Path,
    initial_purchase_policy_artifact: Mapping[str, object],
    initial_controlled_private_root: Path,
    cohort_policy_artifact: Mapping[str, object],
    budget_plan_bytes: bytes,
    selection_bytes: bytes,
    purchase_ledger_path: Path,
    purchase_ledger_initialization_receipt_path: Path,
    allowed_additional_operation_pairs: set[tuple[str, str]] | None = None,
) -> ReplacementPurchaseApprovalRequest:
    """Authorize only the exact successor tranche, including safe resume state."""

    if set(authority_artifact) != {
        "schema_version",
        "authority",
        "authority_sha256",
    } or authority_artifact.get("schema_version") not in {
        REPLACEMENT_APPROVAL_SCHEMA,
        REPLACEMENT_APPROVAL_SCHEMA_V2,
    }:
        raise ReplacementPurchaseApprovalError(
            "unsupported replacement purchase authority artifact"
        )
    body = _mapping(authority_artifact.get("authority"), "replacement authority")
    if authority_artifact.get("authority_sha256") != _canonical_sha256(body):
        raise ReplacementPurchaseApprovalError(
            "replacement purchase authority hash differs"
        )
    expected_body_fields = {
        "schema_version",
        "decision",
        "reviewer_id",
        "recorded_at_utc",
        "typed_confirmation_sha256",
        "private_checkpoint_sha256",
        "private_run_card_sha256",
        "request",
    }
    if set(body) != expected_body_fields:
        raise ReplacementPurchaseApprovalError(
            "replacement purchase authority fields differ"
        )
    artifact_schema = authority_artifact.get("schema_version")
    if (
        body.get("schema_version") != artifact_schema
        or body.get("decision") != "approve"
        or body.get("reviewer_id") != "John Hughes"
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement purchase authority decision is invalid"
        )
    request = _request_from_record(
        _mapping(body.get("request"), "replacement authority request")
    )
    if artifact_schema != _authority_schema(request):
        raise ReplacementPurchaseApprovalError(
            "replacement purchase authority schema differs from its request"
        )
    checkpoint_path = (
        controlled_private_root / "replacement-purchase-approval-checkpoint.json"
    )
    run_card_path = (
        controlled_private_root
        / "run-cards"
        / "record-replacement-purchase-approval.json"
    )
    verified = verify_replacement_purchase_approval(
        request=request,
        controlled_private_root=controlled_private_root,
        checkpoint_path=checkpoint_path,
        run_card_path=run_card_path,
    )
    if authority_artifact != generate_replacement_purchase_authority(verified):
        raise ReplacementPurchaseApprovalError(
            "replacement authority differs from private successor evidence"
        )
    try:
        policy = verify_case_dev_purchase_policy(initial_purchase_policy_artifact)
        require_approved_case_dev_purchase_policy(
            policy,
            controlled_private_root=initial_controlled_private_root,
        )
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort_policy_artifact)
    except (CaseDevPurchasePolicyError, CohortPolicyError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    ledger = purchase_ledger_path.resolve()
    initialization_receipt = purchase_ledger_initialization_receipt_path.resolve()
    initialization_receipt_bytes = read_unique_regular_file(initialization_receipt)
    if (
        request.initial_purchase_policy_sha256 != policy.policy_sha256
        or request.cohort_policy_sha256 != policy.cohort_policy_sha256
        or request.purchase_ledger_path != str(ledger)
        or request.purchase_ledger_initialization_receipt_path
        != str(initialization_receipt)
        or request.purchase_ledger_initialization_receipt_sha256
        != _sha256(initialization_receipt_bytes)
        or ledger != policy.canonical_ledger_path
        or request.hard_cap_usd != _money(policy.hard_cap_usd)
        or request.max_per_case_usd != _money(policy.max_per_case_usd)
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement authority differs from the initial v2 policy or ledger"
        )
    if request.replacement_budget_plan_sha256 != _sha256(budget_plan_bytes):
        raise ReplacementPurchaseApprovalError(
            "replacement budget plan differs from exact successor approval"
        )
    if request.replacement_selection_sha256 != _sha256(selection_bytes):
        raise ReplacementPurchaseApprovalError(
            "replacement selection differs from exact successor approval"
        )
    _verify_runtime_budget_plan(request, budget_plan_bytes)
    _verify_runtime_selection(request, selection_bytes, budget_plan_bytes)
    try:
        with CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            read_only=True,
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            current_committed = _usd(
                journal.committed_amount_usd, "current committed spend"
            )
            operations = tuple(journal.operation_records())
            current_candidate_totals = {
                candidate_id: _usd(
                    journal.candidate_committed_amount_usd(candidate_id),
                    f"{candidate_id} current committed spend",
                )
                for candidate_id in sorted(
                    set(policy.opening_case_committed_spend_usd)
                    | {cast(str, operation["candidate_id"]) for operation in operations}
                )
            }
    except (CaseDevPurchaseLedgerError, OSError, ValueError) as exc:
        raise ReplacementPurchaseApprovalError(str(exc)) from exc
    base_committed = _usd(request.committed_spend_usd, "approved committed spend")
    tranche_cost = _usd(
        request.tranche_projected_cost_usd, "approved tranche projected cost"
    )
    approved_ceiling = base_committed + tranche_cost
    if current_committed < base_committed or (
        allowed_additional_operation_pairs is None
        and current_committed > approved_ceiling
    ):
        raise ReplacementPurchaseApprovalError(
            "current committed spend is outside the approved successor envelope"
        )
    if allowed_additional_operation_pairs is not None and current_committed > _usd(
        request.hard_cap_usd, "approved hard cap"
    ):
        raise ReplacementPurchaseApprovalError(
            "current committed spend exceeds the unchanged approved hard cap"
        )
    approved_by_candidate = _approved_documents_by_candidate(request, budget_plan_bytes)
    current_operations = tuple(
        (_canonical_sha256(dict(operation)), operation) for operation in operations
    )
    current_operation_hashes = tuple(digest for digest, _ in current_operations)
    baseline_hashes = request.baseline_operation_record_sha256s
    if len(set(baseline_hashes)) != len(baseline_hashes):
        raise ReplacementPurchaseApprovalError(
            "successor approval contains duplicate baseline purchase operations"
        )
    if len(set(current_operation_hashes)) != len(current_operation_hashes):
        raise ReplacementPurchaseApprovalError(
            "purchase journal contains duplicate canonical operation records"
        )
    current_hash_set = set(current_operation_hashes)
    if any(digest not in current_hash_set for digest in baseline_hashes):
        raise ReplacementPurchaseApprovalError(
            "purchase journal lost or changed baseline operations after "
            "successor approval"
        )
    baseline_hash_set = set(baseline_hashes)
    approved_pairs = {
        (candidate_id, document_id)
        for candidate_id, document_ids in approved_by_candidate.items()
        for document_id in document_ids
    }
    permitted_pairs = approved_pairs | (allowed_additional_operation_pairs or set())
    observed_successor_pairs: set[tuple[str, str]] = set()
    for digest, operation in current_operations:
        if digest in baseline_hash_set:
            continue
        candidate_id = cast(str, operation["candidate_id"])
        document_id = cast(str, operation["source_document_id"])
        pair = (candidate_id, document_id)
        if pair not in permitted_pairs:
            raise ReplacementPurchaseApprovalError(
                "purchase journal contains an operation outside the approved "
                "successor tranche"
            )
        if pair in observed_successor_pairs:
            raise ReplacementPurchaseApprovalError(
                "purchase journal repeats an approved successor operation"
            )
        if operation.get("reservation_usd") != _money(
            policy.per_document_reservation_usd
        ):
            raise ReplacementPurchaseApprovalError(
                "successor operation reservation differs from the unchanged policy"
            )
        observed_successor_pairs.add(pair)
    baseline_candidate_headroom = {
        candidate_id: _usd(committed, f"{candidate_id} approved committed spend")
        for candidate_id, committed, _before, _approved, _after in (
            request.candidate_headroom
        )
    }
    if set(request.replacement_candidate_ids) - set(baseline_candidate_headroom):
        raise ReplacementPurchaseApprovalError(
            "successor approval lacks replacement candidate headroom"
        )
    max_per_case = _usd(request.max_per_case_usd, "approved per-case cap")
    for candidate_id, current_total in current_candidate_totals.items():
        baseline_total = baseline_candidate_headroom.get(candidate_id, Decimal("0.00"))
        if current_total < baseline_total or current_total > max_per_case:
            raise ReplacementPurchaseApprovalError(
                "current per-case committed spend is outside the approved "
                "successor envelope"
            )
    return request


def _request_from_record(
    record: Mapping[str, object],
) -> ReplacementPurchaseApprovalRequest:
    common_fields = {
        "cycle_id",
        "cohort_policy_sha256",
        "initial_purchase_policy_sha256",
        "initial_approval_sha256",
        "replacement_result_sha256",
        "replacement_budget_plan_sha256",
        "replacement_selection_sha256",
        "purchase_journal_state_sha256",
        "purchase_ledger_path",
        "purchase_ledger_initialization_receipt_path",
        "purchase_ledger_initialization_receipt_sha256",
        "committed_spend_usd",
        "hard_cap_usd",
        "max_per_case_usd",
        "remaining_headroom_before_usd",
        "tranche_projected_cost_usd",
        "remaining_headroom_after_usd",
        "candidate_headroom",
        "replacement_candidate_ids",
        "purchase_document_ids",
        "replacement_event_record_sha256s",
        "baseline_operation_record_sha256s",
        "session_scope",
        "fallback",
    }
    v1_fields = common_fields | {"frontier_sha256"}
    v2_fields = common_fields | {
        "source_authority_kind",
        "source_authority_sha256",
    }
    if set(record) == v1_fields:
        source_authority_kind: str | None = None
        source_authority_sha256: str | None = None
        frontier_sha256 = _sha(record.get("frontier_sha256"), "frontier_sha256")
    elif set(record) == v2_fields:
        source_authority_kind = _source_authority_kind(
            record.get("source_authority_kind")
        )
        source_authority_sha256 = _sha(
            record.get("source_authority_sha256"), "source_authority_sha256"
        )
        frontier_sha256 = source_authority_sha256
    else:
        raise ReplacementPurchaseApprovalError(
            "replacement approval request fields differ"
        )
    request = ReplacementPurchaseApprovalRequest(
        cycle_id=_text(record.get("cycle_id"), "cycle_id"),
        cohort_policy_sha256=_sha(
            record.get("cohort_policy_sha256"), "cohort_policy_sha256"
        ).removeprefix("sha256:"),
        initial_purchase_policy_sha256=_sha(
            record.get("initial_purchase_policy_sha256"),
            "initial_purchase_policy_sha256",
        ).removeprefix("sha256:"),
        initial_approval_sha256=_sha(
            record.get("initial_approval_sha256"), "initial_approval_sha256"
        ).removeprefix("sha256:"),
        frontier_sha256=frontier_sha256,
        replacement_result_sha256=_sha(
            record.get("replacement_result_sha256"), "replacement_result_sha256"
        ).removeprefix("sha256:"),
        replacement_budget_plan_sha256=_sha(
            record.get("replacement_budget_plan_sha256"),
            "replacement_budget_plan_sha256",
        ).removeprefix("sha256:"),
        replacement_selection_sha256=_sha(
            record.get("replacement_selection_sha256"),
            "replacement_selection_sha256",
        ).removeprefix("sha256:"),
        purchase_journal_state_sha256=_sha(
            record.get("purchase_journal_state_sha256"),
            "purchase_journal_state_sha256",
        ),
        purchase_ledger_path=_text(
            record.get("purchase_ledger_path"), "purchase_ledger_path"
        ),
        purchase_ledger_initialization_receipt_path=_text(
            record.get("purchase_ledger_initialization_receipt_path"),
            "purchase_ledger_initialization_receipt_path",
        ),
        purchase_ledger_initialization_receipt_sha256=_sha(
            record.get("purchase_ledger_initialization_receipt_sha256"),
            "purchase_ledger_initialization_receipt_sha256",
        ).removeprefix("sha256:"),
        committed_spend_usd=_money(
            _usd(record.get("committed_spend_usd"), "committed_spend_usd")
        ),
        hard_cap_usd=_money(_usd(record.get("hard_cap_usd"), "hard_cap_usd")),
        max_per_case_usd=_money(
            _usd(record.get("max_per_case_usd"), "max_per_case_usd")
        ),
        remaining_headroom_before_usd=_money(
            _usd(
                record.get("remaining_headroom_before_usd"),
                "remaining_headroom_before_usd",
            )
        ),
        tranche_projected_cost_usd=_money(
            _usd(
                record.get("tranche_projected_cost_usd"),
                "tranche_projected_cost_usd",
            )
        ),
        remaining_headroom_after_usd=_money(
            _usd(
                record.get("remaining_headroom_after_usd"),
                "remaining_headroom_after_usd",
            )
        ),
        candidate_headroom=_candidate_headroom_from_record(
            record.get("candidate_headroom")
        ),
        replacement_candidate_ids=_unique_texts(
            _sequence(
                record.get("replacement_candidate_ids"),
                "replacement_candidate_ids",
            ),
            "replacement_candidate_ids",
        ),
        purchase_document_ids=_unique_texts(
            _sequence(record.get("purchase_document_ids"), "purchase_document_ids"),
            "purchase_document_ids",
        ),
        replacement_event_record_sha256s=tuple(
            _sha(value, "replacement_event_record_sha256")
            for value in _sequence(
                record.get("replacement_event_record_sha256s"),
                "replacement_event_record_sha256s",
            )
        ),
        baseline_operation_record_sha256s=tuple(
            _sha(value, "baseline_operation_record_sha256").removeprefix("sha256:")
            for value in _sequence(
                record.get("baseline_operation_record_sha256s"),
                "baseline operation record SHA-256s",
            )
        ),
        session_scope=_text(record.get("session_scope"), "session_scope"),
        fallback=_text(record.get("fallback"), "fallback"),
        source_authority_kind=source_authority_kind,
        source_authority_sha256=source_authority_sha256,
    )
    if (
        request.session_scope != "exact_replacement_tranche_one_global_session"
        or request.fallback != "stop_without_replacement_purchase"
        or (
            request.source_authority_kind is None
            and request.source_authority_sha256 is not None
        )
        or (
            request.source_authority_kind is not None
            and request.source_authority_sha256 != request.frontier_sha256
        )
        or tuple(entry[0] for entry in request.candidate_headroom)
        != tuple(sorted(entry[0] for entry in request.candidate_headroom))
        or len({entry[0] for entry in request.candidate_headroom})
        != len(request.candidate_headroom)
        or any(
            _usd(committed, "candidate committed spend")
            + _usd(before, "candidate remaining headroom before")
            != _usd(request.max_per_case_usd, "max_per_case_usd")
            for _candidate_id, committed, before, _approved, _after in (
                request.candidate_headroom
            )
        )
        or request.remaining_headroom_after_usd
        != _money(
            _usd(
                request.remaining_headroom_before_usd,
                "remaining_headroom_before_usd",
            )
            - _usd(
                request.tranche_projected_cost_usd,
                "tranche_projected_cost_usd",
            )
        )
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement request scope or headroom arithmetic is invalid"
        )
    return request


def _candidate_headroom_record(
    *,
    candidate_id: str,
    committed: Decimal,
    approved_cost: Decimal,
    max_per_case: Decimal,
) -> tuple[str, str, str, str, str]:
    before = max_per_case - committed
    after = before - approved_cost
    if before < 0 or after < 0:
        raise ReplacementPurchaseApprovalError(
            f"replacement tranche exceeds per-case headroom: {candidate_id}"
        )
    return (
        candidate_id,
        _money(committed),
        _money(before),
        _money(approved_cost),
        _money(after),
    )


def _candidate_headroom_from_record(
    value: object,
) -> tuple[tuple[str, str, str, str, str], ...]:
    output: list[tuple[str, str, str, str, str]] = []
    for raw in _sequence(value, "candidate_headroom"):
        entry = _mapping(raw, "candidate headroom")
        if set(entry) != {
            "candidate_id",
            "committed_spend_usd",
            "remaining_headroom_before_usd",
            "approved_tranche_cost_usd",
            "remaining_headroom_after_usd",
        }:
            raise ReplacementPurchaseApprovalError("candidate headroom fields differ")
        candidate_id = _text(entry.get("candidate_id"), "candidate headroom ID")
        committed = _usd(entry.get("committed_spend_usd"), "candidate committed spend")
        before = _usd(
            entry.get("remaining_headroom_before_usd"),
            "candidate remaining headroom before",
        )
        approved = _usd(
            entry.get("approved_tranche_cost_usd"),
            "candidate approved tranche cost",
        )
        after = _usd(
            entry.get("remaining_headroom_after_usd"),
            "candidate remaining headroom after",
        )
        if after != before - approved or after < 0:
            raise ReplacementPurchaseApprovalError(
                "candidate headroom arithmetic is invalid"
            )
        output.append(
            (
                candidate_id,
                _money(committed),
                _money(before),
                _money(approved),
                _money(after),
            )
        )
    return tuple(output)


def _approved_documents_by_candidate(
    request: ReplacementPurchaseApprovalRequest, budget_plan_bytes: bytes
) -> dict[str, set[str]]:
    budget = _json_object(budget_plan_bytes, "replacement budget plan")
    output: dict[str, set[str]] = {}
    for raw_plan in _sequence(budget.get("case_plans"), "replacement case plans"):
        plan = _mapping(raw_plan, "replacement case plan")
        candidate_id = _text(plan.get("candidate_id"), "candidate_id")
        output[candidate_id] = set(
            _unique_texts(
                _sequence(plan.get("purchase_document_ids"), "purchase_document_ids"),
                "purchase_document_ids",
            )
        )
    if tuple(output) != request.replacement_candidate_ids:
        raise ReplacementPurchaseApprovalError(
            "replacement budget candidates differ from exact successor approval"
        )
    return output


def _verify_runtime_budget_plan(
    request: ReplacementPurchaseApprovalRequest, budget_plan_bytes: bytes
) -> None:
    budget = _json_object(budget_plan_bytes, "replacement budget plan")
    if (
        budget.get("dry_run") is not False
        or budget.get("total_estimated_cost_usd") != request.tranche_projected_cost_usd
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement budget plan is not the approved executable tranche"
        )
    approved_by_candidate = _approved_documents_by_candidate(request, budget_plan_bytes)
    documents = tuple(
        document_id
        for candidate_documents in approved_by_candidate.values()
        for document_id in candidate_documents
    )
    if set(documents) != set(request.purchase_document_ids) or len(documents) != len(
        request.purchase_document_ids
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement budget documents differ from exact successor approval"
        )
    planned_costs = {
        _text(
            _mapping(raw_plan, "replacement case plan").get("candidate_id"),
            "candidate_id",
        ): _money(
            _usd(
                _mapping(raw_plan, "replacement case plan").get("estimated_cost_usd"),
                "replacement cost",
            )
        )
        for raw_plan in _sequence(budget.get("case_plans"), "replacement case plans")
    }
    if {
        candidate_id: approved
        for candidate_id, _committed, _before, approved, _after in (
            request.candidate_headroom
        )
        if approved != "0.00"
    } != planned_costs:
        raise ReplacementPurchaseApprovalError(
            "replacement candidate headroom differs from exact successor plan"
        )


def _verify_runtime_selection(
    request: ReplacementPurchaseApprovalRequest,
    selection_bytes: bytes,
    budget_plan_bytes: bytes,
) -> None:
    try:
        rows = tuple(
            json.loads(line)
            for line in selection_bytes.decode().splitlines()
            if line.strip()
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplacementPurchaseApprovalError(
            "replacement selection is invalid JSONL"
        ) from exc
    by_candidate: dict[str, set[str]] = {}
    for raw in rows:
        row = _mapping(raw, "replacement selection row")
        candidate_id = _text(row.get("candidate_id"), "selection candidate_id")
        if candidate_id not in request.replacement_candidate_ids:
            continue
        raw_documents = _sequence(row.get("documents"), "selection documents")
        by_candidate[candidate_id] = {
            _text(
                _mapping(document, "selection document").get("source_document_id"),
                "source_document_id",
            )
            for document in raw_documents
        }
    if set(by_candidate) != set(request.replacement_candidate_ids):
        raise ReplacementPurchaseApprovalError(
            "replacement selection lacks an approved successor candidate"
        )
    # Candidate/document association is part of the exact approved plan, not
    # merely set membership somewhere in a broader selection artifact.
    approved = _approved_documents_by_candidate(request, budget_plan_bytes)
    for candidate_id, document_ids in approved.items():
        if not document_ids.issubset(by_candidate[candidate_id]):
            raise ReplacementPurchaseApprovalError(
                "replacement selection lacks an approved successor candidate/document"
            )


def _selection_candidate_ids(selection_bytes: bytes) -> tuple[str, ...]:
    try:
        rows = tuple(
            json.loads(line)
            for line in selection_bytes.decode().splitlines()
            if line.strip()
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplacementPurchaseApprovalError(
            "replacement selection is invalid JSONL"
        ) from exc
    return tuple(
        _text(
            _mapping(row, "replacement selection row").get("candidate_id"),
            "candidate_id",
        )
        for row in rows
    )


def _operation_commits_spend(operation: Mapping[str, object]) -> bool:
    """Mirror the ranked planner's canonical committed-spend treatment."""

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


def _verify_result_identity(result: Mapping[str, object]) -> None:
    expected = {
        "schema_version",
        "active_candidate_ids",
        "replacement_plan",
        "broker_allowlist_plan",
        "ledger_records",
        "derived_exclusions",
        "stop_reason",
        "frontier_sha256",
        "purchase_journal_state_sha256",
        "active_selection_sha256",
        "active_selection_count",
        "replacement_selection_sha256",
        "replacement_selection_count",
        "paid_activity_requested",
        "paid_activity_executed",
        "plan_sha256",
    }
    if (
        set(result) != expected
        or result.get("schema_version") != CLEARANCE_RESULT_SCHEMA_VERSION
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement result has unsupported or incomplete fields"
        )
    body = {key: value for key, value in result.items() if key != "plan_sha256"}
    if result.get("plan_sha256") != _replacement_plan_sha256(body):
        raise ReplacementPurchaseApprovalError(
            "replacement result plan_sha256 does not match content"
        )


def _verify_ranked_result_identity(result: Mapping[str, object]) -> None:
    expected = {
        "schema_version",
        "projection_sha256",
        "cycle_id",
        "purchase_policy_sha256",
        "purchase_journal_state_sha256",
        "hard_cap_usd",
        "terminal_exclusions_sha256",
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
    schema_version = result.get("schema_version")
    if schema_version == _AUTHENTICATED_RANKED_RESERVE_RESULT_SCHEMA:
        expected |= {"terminal_disposition", "terminal_disposition_sha256"}
    if set(result) != expected or schema_version not in {
        _RANKED_RESERVE_RESULT_SCHEMA,
        _AUTHENTICATED_RANKED_RESERVE_RESULT_SCHEMA,
    }:
        raise ReplacementPurchaseApprovalError(
            "ranked replacement result has unsupported or incomplete fields"
        )
    if schema_version == _AUTHENTICATED_RANKED_RESERVE_RESULT_SCHEMA:
        try:
            disposition = validate_terminal_purchase_disposition_record(
                result.get("terminal_disposition")
            )
        except DocketDecisionTextSourceError as exc:
            raise ReplacementPurchaseApprovalError(str(exc)) from exc
        if result.get("terminal_disposition_sha256") != (
            "sha256:"
            + hashlib.sha256(
                canonical_json_value_bytes(
                    disposition,
                    error_type=ReplacementPurchaseApprovalError,
                    error_message="terminal disposition is not canonical JSON",
                )
            ).hexdigest()
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement terminal disposition commitment mismatch"
            )
        if disposition.get("residual_terminal_exclusions_sha256") != result.get(
            "terminal_exclusions_sha256"
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement residual exclusion commitment mismatch"
            )
        if disposition.get("purchase_journal_state_sha256") != result.get(
            "purchase_journal_state_sha256"
        ):
            raise ReplacementPurchaseApprovalError(
                "ranked replacement terminal disposition targets another journal state"
            )
    for field in (
        "provider_activity_requested",
        "paid_activity_requested",
        "paid_activity_executed",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    ):
        if result.get(field) is not False:
            raise ReplacementPurchaseApprovalError(
                "ranked replacement result grants activity or downstream authority"
            )
    for field in (
        "projection_sha256",
        "purchase_policy_sha256",
        "purchase_journal_state_sha256",
        "terminal_exclusions_sha256",
        "active_selection_sha256",
        "replacement_selection_sha256",
        "successor_exclusions_sha256",
        "replacement_budget_plan_sha256",
    ):
        _sha(result.get(field), field)
    for field, positive in (
        ("active_case_count", True),
        ("replacement_case_count", True),
    ):
        value = result.get(field)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or (positive and value <= 0)
        ):
            raise ReplacementPurchaseApprovalError(
                f"ranked replacement result {field} is invalid"
            )
    for field in (
        "hard_cap_usd",
        "committed_spend_usd",
        "reserved_replacement_spend_usd",
        "remaining_headroom_usd",
    ):
        _usd(result.get(field), field)


def _optional_source_authority_kind(value: str | None) -> str | None:
    if value is None:
        return None
    return _source_authority_kind(value)


def _source_authority_kind(value: object) -> str:
    kind = _text(value, "source_authority_kind")
    if kind not in _SOURCE_AUTHORITY_KINDS:
        raise ReplacementPurchaseApprovalError(
            "replacement source authority kind is unsupported"
        )
    return kind


def _checkpoint_schema(request: ReplacementPurchaseApprovalRequest) -> str:
    return (
        REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA
        if request.evidence_schema_version == 1
        else REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA_V2
    )


def _run_card_schema(request: ReplacementPurchaseApprovalRequest) -> str:
    return (
        REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA
        if request.evidence_schema_version == 1
        else REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA_V2
    )


def _authority_schema(request: ReplacementPurchaseApprovalRequest) -> str:
    return (
        REPLACEMENT_APPROVAL_SCHEMA
        if request.evidence_schema_version == 1
        else REPLACEMENT_APPROVAL_SCHEMA_V2
    )


def _write_private_once(path: Path, payload: bytes) -> None:
    """Publish through an anchored no-follow directory descriptor."""

    try:
        directory_fd = _open_or_create_private_directory(path.parent)
    except OSError as exc:
        raise ReplacementPurchaseApprovalError(
            f"replacement approval output cannot be safely published: {path}"
        ) from exc
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    temporary_created = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open(temporary_name, flags, 0o600, dir_fd=directory_fd)
        temporary_created = True
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.link(
                temporary_name,
                path.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ReplacementPurchaseApprovalError(
                f"replacement approval output already exists: {path}"
            ) from exc
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_created = False
        os.fsync(directory_fd)
        if _read_unique_regular_at(directory_fd, path.name) != payload:
            raise ReplacementPurchaseApprovalError(
                "replacement approval output changed during publication"
            )
    except OSError as exc:
        raise ReplacementPurchaseApprovalError(
            f"replacement approval output cannot be safely published: {path}"
        ) from exc
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                # Publication may already have removed the staging entry.
                pass
        os.close(directory_fd)


def _preflight_private_once(path: Path) -> None:
    """Reject any existing output before either approval artifact is written."""

    try:
        directory_fd = _open_or_create_private_directory(path.parent)
    except OSError as exc:
        raise ReplacementPurchaseApprovalError(
            f"replacement approval output cannot be safely preflighted: {path}"
        ) from exc
    try:
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ReplacementPurchaseApprovalError(
                f"replacement approval output cannot be safely preflighted: {path}"
            ) from exc
        else:
            os.close(descriptor)
            raise ReplacementPurchaseApprovalError(
                f"replacement approval output already exists: {path}"
            )
    finally:
        os.close(directory_fd)


def _open_or_create_private_directory(path: Path) -> int:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise ReplacementPurchaseApprovalError(
            "replacement approval directory must be an absolute normalized path"
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parts = path.parts
    directory_fd = os.open(parts[0], flags)
    try:
        for component in parts[1:]:
            try:
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=directory_fd)
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd
    except BaseException:
        os.close(directory_fd)
        raise


def _read_unique_regular_at(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ReplacementPurchaseApprovalError(
                "replacement approval output is not a unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ReplacementPurchaseApprovalError(
                "replacement approval output changed while reading"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise ReplacementPurchaseApprovalError(
                "replacement approval output changed while reading"
            )
        return payload
    finally:
        os.close(descriptor)


def _absolute_root(path: Path) -> Path:
    if not path.is_absolute():
        raise ReplacementPurchaseApprovalError(
            "controlled private root must be absolute"
        )
    return path


def _json_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplacementPurchaseApprovalError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReplacementPurchaseApprovalError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReplacementPurchaseApprovalError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReplacementPurchaseApprovalError(f"{label} must be a list")
    return cast(Sequence[object], value)


def _unique_texts(values: Sequence[object], label: str) -> tuple[str, ...]:
    output = tuple(_text(value, label) for value in values)
    if len(output) != len(set(output)):
        raise ReplacementPurchaseApprovalError(f"{label} must be unique")
    return output


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ReplacementPurchaseApprovalError(
            f"{label} must be a canonical nonempty string"
        )
    return value


def _decision(value: object) -> str:
    decision = _text(value, "decision")
    if decision not in _DECISIONS:
        raise ReplacementPurchaseApprovalError(
            "replacement decision must be approve or reject"
        )
    return decision


def _usd(value: object, label: str) -> Decimal:
    if not isinstance(value, str) or _USD.fullmatch(value) is None:
        raise ReplacementPurchaseApprovalError(
            f"{label} must be canonical nonnegative USD"
        )
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ReplacementPurchaseApprovalError(f"{label} is invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise ReplacementPurchaseApprovalError(f"{label} is invalid")
    return amount


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ReplacementPurchaseApprovalError(f"{label} must be SHA-256")
    raw = value.removeprefix("sha256:")
    if _SHA256.fullmatch(raw) is None:
        raise ReplacementPurchaseApprovalError(f"{label} must be SHA-256")
    return "sha256:" + raw


def _utc_timestamp(value: object) -> str:
    text = _text(value, "recorded_at_utc")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplacementPurchaseApprovalError(
            "recorded_at_utc must be ISO-8601"
        ) from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ReplacementPurchaseApprovalError("recorded_at_utc must be UTC")
    return text


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _replacement_plan_sha256(value: object) -> str:
    """Match the clearance-replacement producer's canonical hash exactly."""

    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

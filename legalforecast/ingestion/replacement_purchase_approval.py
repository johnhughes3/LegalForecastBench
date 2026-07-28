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

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicyError,
    require_approved_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.clearance_replacement import (
    RESULT_SCHEMA_VERSION,
    ClearanceReplacementError,
    verify_replacement_frontier,
)
from legalforecast.ingestion.cohort_policy import CohortPolicyError
from legalforecast.ingestion.disclosure_review_bundle import read_unique_regular_file

REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA = (
    "legalforecast.replacement_purchase_approval_checkpoint.v1"
)
REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA = (
    "legalforecast.replacement_purchase_approval_run_card.v1"
)
REPLACEMENT_APPROVAL_SCHEMA = "legalforecast.replacement_purchase_approval.v1"

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
    remaining_headroom_before_usd: str
    tranche_projected_cost_usd: str
    remaining_headroom_after_usd: str
    replacement_candidate_ids: tuple[str, ...]
    purchase_document_ids: tuple[str, ...]
    replacement_event_record_sha256s: tuple[str, ...]
    baseline_operation_record_sha256s: tuple[str, ...] = ()
    session_scope: str = "exact_replacement_tranche_one_global_session"
    fallback: str = "stop_without_replacement_purchase"

    def to_record(self) -> dict[str, object]:
        """Return canonical request bytes committed by the private checkpoint."""

        return {
            "cycle_id": self.cycle_id,
            "cohort_policy_sha256": self.cohort_policy_sha256,
            "initial_purchase_policy_sha256": self.initial_purchase_policy_sha256,
            "initial_approval_sha256": self.initial_approval_sha256,
            "frontier_sha256": self.frontier_sha256,
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
            "remaining_headroom_before_usd": self.remaining_headroom_before_usd,
            "tranche_projected_cost_usd": self.tranche_projected_cost_usd,
            "remaining_headroom_after_usd": self.remaining_headroom_after_usd,
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
    frontier_path: Path,
    replacement_result_path: Path,
    replacement_budget_plan_path: Path,
    replacement_selection_path: Path,
    purchase_ledger_path: Path,
    purchase_ledger_initialization_receipt_path: Path,
) -> ReplacementPurchaseApprovalRequest:
    """Reproduce one exact ranked tranche against the existing Cycle ledger.

    This function performs no provider call, fee acknowledgement, or purchase.
    The initial approval authenticates only the common policy/cap identity; it
    is deliberately not treated as authority for the replacement tranche.
    """

    cohort_bytes = read_unique_regular_file(cohort_policy_path)
    policy_bytes = read_unique_regular_file(initial_purchase_policy_path)
    frontier_bytes = read_unique_regular_file(frontier_path)
    result_bytes = read_unique_regular_file(replacement_result_path)
    budget_bytes = read_unique_regular_file(replacement_budget_plan_path)
    selection_bytes = read_unique_regular_file(replacement_selection_path)
    initialization_receipt = purchase_ledger_initialization_receipt_path.resolve()
    initialization_receipt_bytes = read_unique_regular_file(initialization_receipt)
    cohort = _json_object(cohort_bytes, "cohort policy")
    policy_artifact = _json_object(policy_bytes, "initial purchase policy")
    frontier_artifact = _json_object(frontier_bytes, "replacement frontier")
    result = _json_object(result_bytes, "replacement result")
    budget = _json_object(budget_bytes, "replacement budget plan")
    try:
        policy = verify_case_dev_purchase_policy(policy_artifact)
        require_approved_case_dev_purchase_policy(
            policy,
            controlled_private_root=initial_controlled_private_root,
        )
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort)
        frontier = verify_replacement_frontier(
            frontier_artifact,
            cohort_policy_artifact=cohort,
            purchase_policy_artifact=policy_artifact,
            controlled_private_root=initial_controlled_private_root,
        )
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
    request = ReplacementPurchaseApprovalRequest(
        cycle_id=policy.cycle_id,
        cohort_policy_sha256=policy.cohort_policy_sha256,
        initial_purchase_policy_sha256=policy.policy_sha256,
        initial_approval_sha256=_canonical_sha256(dict(raw_approval)),
        frontier_sha256=_sha(frontier["policy_sha256"], "frontier_sha256"),
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
        remaining_headroom_before_usd=_money(headroom_before),
        tranche_projected_cost_usd=_money(total_cost),
        remaining_headroom_after_usd=_money(headroom_before - total_cost),
        replacement_candidate_ids=tuple(candidate_ids),
        purchase_document_ids=tuple(document_ids),
        replacement_event_record_sha256s=event_hashes,
        baseline_operation_record_sha256s=tuple(
            _canonical_sha256(dict(operation)) for operation in operations
        ),
    )
    _verify_runtime_budget_plan(request, budget_bytes)
    _verify_runtime_selection(request, selection_bytes, budget_bytes)
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
        "schema_version": REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA,
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
        "schema_version": REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA,
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
    if (
        checkpoint_artifact.get("schema_version")
        != REPLACEMENT_APPROVAL_CHECKPOINT_SCHEMA
        or run_card_artifact.get("schema_version")
        != REPLACEMENT_APPROVAL_RUN_CARD_SCHEMA
    ):
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
    body = {
        "schema_version": REPLACEMENT_APPROVAL_SCHEMA,
        "decision": "approve",
        "reviewer_id": approval.reviewer_id,
        "recorded_at_utc": approval.recorded_at_utc,
        "typed_confirmation_sha256": approval.typed_confirmation_sha256,
        "private_checkpoint_sha256": approval.checkpoint_sha256,
        "private_run_card_sha256": approval.run_card_sha256,
        "request": approval.request.to_record(),
    }
    return {
        "schema_version": REPLACEMENT_APPROVAL_SCHEMA,
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

    if (
        set(authority_artifact)
        != {
            "schema_version",
            "authority",
            "authority_sha256",
        }
        or authority_artifact.get("schema_version") != REPLACEMENT_APPROVAL_SCHEMA
    ):
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
    if (
        body.get("schema_version") != REPLACEMENT_APPROVAL_SCHEMA
        or body.get("decision") != "approve"
        or body.get("reviewer_id") != "John Hughes"
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement purchase authority decision is invalid"
        )
    request = _request_from_record(
        _mapping(body.get("request"), "replacement authority request")
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
            controlled_private_root=initial_controlled_private_root,
            initialization_receipt_path=initialization_receipt,
        ) as journal:
            journal.require_reconciled()
            current_committed = _usd(
                journal.committed_amount_usd, "current committed spend"
            )
            operations = tuple(journal.operation_records())
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
    return request


def _request_from_record(
    record: Mapping[str, object],
) -> ReplacementPurchaseApprovalRequest:
    expected = {
        "cycle_id",
        "cohort_policy_sha256",
        "initial_purchase_policy_sha256",
        "initial_approval_sha256",
        "frontier_sha256",
        "replacement_result_sha256",
        "replacement_budget_plan_sha256",
        "replacement_selection_sha256",
        "purchase_journal_state_sha256",
        "purchase_ledger_path",
        "purchase_ledger_initialization_receipt_path",
        "purchase_ledger_initialization_receipt_sha256",
        "committed_spend_usd",
        "hard_cap_usd",
        "remaining_headroom_before_usd",
        "tranche_projected_cost_usd",
        "remaining_headroom_after_usd",
        "replacement_candidate_ids",
        "purchase_document_ids",
        "replacement_event_record_sha256s",
        "baseline_operation_record_sha256s",
        "session_scope",
        "fallback",
    }
    if set(record) != expected:
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
        frontier_sha256=_sha(record.get("frontier_sha256"), "frontier_sha256"),
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
    )
    if (
        request.session_scope != "exact_replacement_tranche_one_global_session"
        or request.fallback != "stop_without_replacement_purchase"
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
    documents = tuple(
        document_id
        for candidate_documents in _approved_documents_by_candidate(
            request, budget_plan_bytes
        ).values()
        for document_id in candidate_documents
    )
    if set(documents) != set(request.purchase_document_ids) or len(documents) != len(
        request.purchase_document_ids
    ):
        raise ReplacementPurchaseApprovalError(
            "replacement budget documents differ from exact successor approval"
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
    if set(result) != expected or result.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise ReplacementPurchaseApprovalError(
            "replacement result has unsupported or incomplete fields"
        )
    body = {key: value for key, value in result.items() if key != "plan_sha256"}
    if result.get("plan_sha256") != _replacement_plan_sha256(body):
        raise ReplacementPurchaseApprovalError(
            "replacement result plan_sha256 does not match content"
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

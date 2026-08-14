"""Provider-free human approval for one exact post-clearance purchase plan."""

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

from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.target_cohort_projection import (
    TargetCohortProjectionError,
    project_target_cohort,
)

PURCHASE_APPROVAL_CHECKPOINT_SCHEMA = "legalforecast.purchase_approval_checkpoint.v1"
PURCHASE_APPROVAL_RUN_CARD_SCHEMA = "legalforecast.purchase_approval_run_card.v1"
PURCHASE_APPROVAL_SCHEMA = "legalforecast.purchase_approval.v1"
PURCHASE_POLICY_V2_SCHEMA = "legalforecast.case_dev_purchase_policy.v2"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")
_DECISIONS = frozenset({"approve", "reject", "free_only"})
_CHECKPOINT_BODY_FIELDS = frozenset(
    {
        "request",
        "verification_inputs",
        "decision",
        "reviewer_id",
        "recorded_at_utc",
        "typed_confirmation",
        "rule_decision",
        "target_decision",
        "session_decision",
        "fallback_decision",
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    }
)
_RUN_CARD_BODY_FIELDS = frozenset(
    {
        "stage",
        "status",
        "decision",
        "request_sha256",
        "checkpoint_sha256",
        "reviewer_id",
        "recorded_at_utc",
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    }
)
_REQUIRED_OUTPUT_NAMES = frozenset(
    {
        "target-cohort-selection.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-projection.json",
    }
)
_PROJECTION_OUTPUT_NAMES = frozenset(
    {
        "target-cohort-selection.jsonl",
        "target-cohort-ranked-reserve.jsonl",
        "case-relevance.jsonl",
        "free-document-downloads.jsonl",
        "purchased-document-downloads.jsonl",
        "document-downloads-merged.jsonl",
        "disclosure-clearance.jsonl",
        "restriction-evidence.jsonl",
        "core-filter-results.jsonl",
        "target-cohort-exclusions.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-projection.json",
    }
)
_PROJECTION_INPUT_NAMES = (
    "selection",
    "case_relevance",
    "download_manifest",
    "disclosure_clearance",
    "clearance_run_card",
    "restriction_evidence",
    "preparation_summary",
    "preparation_config",
    "snapshot_manifest",
)


class PurchaseApprovalError(ValueError):
    """Raised when exact human purchase authority cannot be proven."""


@dataclass(frozen=True, slots=True)
class PurchaseApprovalRequest:
    """Immutable facts shown to the reviewer before one purchase decision."""

    cycle_id: str
    cohort_policy_sha256: str
    cohort_policy_file_sha256: str
    fee_schedule_file_sha256: str
    fee_schedule: Mapping[str, object]
    cohort_policy_path: str
    fee_schedule_path: str
    canonical_ledger_path: str
    ledger_initial_state: str
    target_cohort_root: str
    target_cohort_run_card_sha256: str
    projection_sha256: str
    selection_sha256: str
    budget_plan_sha256: str
    target_case_count: int
    selected_case_count: int
    purchase_document_count: int
    projected_cost_usd: str
    hard_cap_usd: str
    max_per_case_usd: str
    per_document_reservation_usd: str
    opening_committed_spend_usd: str
    opening_case_committed_spend_usd: Mapping[str, str]
    remaining_headroom_usd: str
    rule: str
    session_scope: str
    fallback: str
    selected_candidate_ids_sha256: str
    purchase_document_ids_sha256: str
    output_commitments: Mapping[str, str]

    def to_record(self) -> dict[str, object]:
        """Return the canonical record committed by the private checkpoint."""

        return {
            "cycle_id": self.cycle_id,
            "cohort_policy_sha256": self.cohort_policy_sha256,
            "cohort_policy_file_sha256": self.cohort_policy_file_sha256,
            "fee_schedule_file_sha256": self.fee_schedule_file_sha256,
            "fee_schedule": dict(self.fee_schedule),
            "canonical_ledger_path": self.canonical_ledger_path,
            "ledger_initial_state": self.ledger_initial_state,
            "target_cohort_root": self.target_cohort_root,
            "target_cohort_run_card_sha256": self.target_cohort_run_card_sha256,
            "projection_sha256": self.projection_sha256,
            "selection_sha256": self.selection_sha256,
            "budget_plan_sha256": self.budget_plan_sha256,
            "target_case_count": self.target_case_count,
            "selected_case_count": self.selected_case_count,
            "purchase_document_count": self.purchase_document_count,
            "projected_cost_usd": self.projected_cost_usd,
            "hard_cap_usd": self.hard_cap_usd,
            "max_per_case_usd": self.max_per_case_usd,
            "per_document_reservation_usd": self.per_document_reservation_usd,
            "opening_committed_spend_usd": self.opening_committed_spend_usd,
            "opening_case_committed_spend_usd": dict(
                self.opening_case_committed_spend_usd
            ),
            "remaining_headroom_usd": self.remaining_headroom_usd,
            "rule": self.rule,
            "session_scope": self.session_scope,
            "fallback": self.fallback,
            "selected_candidate_ids_sha256": self.selected_candidate_ids_sha256,
            "purchase_document_ids_sha256": self.purchase_document_ids_sha256,
            "output_commitments": dict(self.output_commitments),
        }

    @property
    def request_sha256(self) -> str:
        return _canonical_sha256(self.to_record())

    def required_confirmation(self, decision: str) -> str:
        """Return the exact typed phrase for a decision over this request.

        Cycle 1 live phrase. Post-Cycle-1 knobs live in legalforecast.config.
        """

        normalized = _decision(decision)
        return (
            f"{normalized.upper()} {self.cycle_id} {self.request_sha256} "
            f"{self.projected_cost_usd} RULE {self.rule} "
            f"TARGET {self.target_case_count} ONE_GLOBAL_SESSION FREE_ONLY"
        )


_VERIFIED_APPROVAL_MINT = object()
_VERIFIED_FREE_ONLY_MINT = object()


@dataclass(frozen=True, slots=True, init=False)
class VerifiedPurchaseApproval:
    """Replay-verified private approval and its exact public commitments."""

    request: PurchaseApprovalRequest
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise PurchaseApprovalError(
            "VerifiedPurchaseApproval can be created only by evidence replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint_token is _VERIFIED_APPROVAL_MINT


@dataclass(frozen=True, slots=True, init=False)
class VerifiedFreeOnlyPurchaseApproval:
    """Replay-verified authority to use only already-free cohort documents."""

    request: PurchaseApprovalRequest
    decision: str
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise PurchaseApprovalError(
            "VerifiedFreeOnlyPurchaseApproval can be created only by evidence replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint_token is _VERIFIED_FREE_ONLY_MINT


def _mint_verified_purchase_approval(
    evidence: _VerifiedPurchaseApprovalEvidence,
) -> VerifiedPurchaseApproval:
    approval = object.__new__(VerifiedPurchaseApproval)
    for name, value in (
        ("request", evidence.request),
        ("reviewer_id", evidence.reviewer_id),
        ("recorded_at_utc", evidence.recorded_at_utc),
        ("typed_confirmation_sha256", evidence.typed_confirmation_sha256),
        ("checkpoint_sha256", evidence.checkpoint_sha256),
        ("run_card_sha256", evidence.run_card_sha256),
        ("_mint_token", _VERIFIED_APPROVAL_MINT),
    ):
        object.__setattr__(approval, name, value)
    return approval


def _mint_verified_free_only_purchase_approval(
    evidence: _VerifiedPurchaseApprovalEvidence,
) -> VerifiedFreeOnlyPurchaseApproval:
    approval = object.__new__(VerifiedFreeOnlyPurchaseApproval)
    for name, value in (
        ("request", evidence.request),
        ("decision", evidence.decision),
        ("reviewer_id", evidence.reviewer_id),
        ("recorded_at_utc", evidence.recorded_at_utc),
        ("typed_confirmation_sha256", evidence.typed_confirmation_sha256),
        ("checkpoint_sha256", evidence.checkpoint_sha256),
        ("run_card_sha256", evidence.run_card_sha256),
        ("_mint_token", _VERIFIED_FREE_ONLY_MINT),
    ):
        object.__setattr__(approval, name, value)
    return approval


@dataclass(frozen=True, slots=True)
class _VerifiedPurchaseApprovalEvidence:
    """Common verified evidence that is not itself minting authority."""

    request: PurchaseApprovalRequest
    decision: str
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str


@dataclass(frozen=True, slots=True)
class ReplayedPurchaseApproval:
    """Non-minting proof that an existing public policy replays privately."""

    policy_sha256: str
    request_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str


def build_purchase_approval_request(
    *,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
) -> PurchaseApprovalRequest:
    """Replay and bind one completed exact target projection without providers."""

    return _build_purchase_approval_request(
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy_path,
        fee_schedule_path=fee_schedule_path,
        canonical_ledger_path=canonical_ledger_path,
        require_fresh_ledger_namespace=True,
    )


def _build_purchase_approval_request(
    *,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
    require_fresh_ledger_namespace: bool,
) -> PurchaseApprovalRequest:
    """Internal replay primitive; only downstream comparison may waive freshness."""

    root = _normalized_absolute(target_cohort_root, "target cohort root")
    ledger = _normalized_absolute(canonical_ledger_path, "canonical ledger path")
    cohort_policy_path = _normalized_absolute(cohort_policy_path, "cohort policy path")
    fee_schedule_path = _normalized_absolute(fee_schedule_path, "fee schedule path")
    if require_fresh_ledger_namespace:
        _require_fresh_ledger_namespace(ledger)
    if root.is_symlink() or not root.is_dir():
        raise PurchaseApprovalError("target cohort root must be a real directory")
    # Import lazily to avoid a module-import cycle: the CLI owns the established
    # full projection/materializer verifier and imports this recorder module.
    # Approval must reuse that verifier instead of maintaining a weaker fork.
    try:
        from legalforecast.cli import (
            verify_completed_target_cohort_projection_for_purchase_approval,
        )

        verified_projection = (
            verify_completed_target_cohort_projection_for_purchase_approval(root)
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise PurchaseApprovalError(
            f"authenticated target projection verification failed: {exc}"
        ) from exc
    raw_verified_bytes = verified_projection.get("verified_artifact_bytes")
    if not isinstance(raw_verified_bytes, Mapping):
        raise PurchaseApprovalError(
            "authenticated target projection verifier omitted authoritative bytes"
        )
    verified_bytes = cast(Mapping[str, object], raw_verified_bytes)

    def projection_bytes(path: Path, label: str) -> bytes:
        payload = verified_bytes.get(os.path.abspath(path))
        if not isinstance(payload, bytes):
            raise PurchaseApprovalError(
                f"authenticated target projection verifier omitted {label}"
            )
        return payload

    cohort_bytes = _read_file(cohort_policy_path, "cohort policy")
    cohort = _json_object(cohort_bytes, "cohort policy")
    fee_schedule_bytes = _read_file(fee_schedule_path, "fee schedule")
    fee_schedule = _validated_fee_schedule(
        _json_object(fee_schedule_bytes, "fee schedule")
    )
    try:
        cohort_hash = verify_cohort_policy(cohort)
    except (CohortPolicyError, ValueError) as exc:
        raise PurchaseApprovalError(f"invalid cohort policy: {exc}") from exc
    raw_cohort = cohort.get("policy")
    if not isinstance(raw_cohort, Mapping):
        raise PurchaseApprovalError("cohort policy content must be an object")
    cohort_body = cast(Mapping[str, object], raw_cohort)
    purchase = _mapping(cohort_body.get("purchase_policy"), "cohort purchase policy")
    reduced_n = _mapping(cohort_body.get("reduced_n"), "cohort reduced_n")

    run_card_path = root / "run-cards/project-target-cohort.json"
    run_card_bytes = projection_bytes(run_card_path, "target projection run card")
    run_card = _json_object(run_card_bytes, "target projection run card")
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "project-target-cohort"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
    ):
        raise PurchaseApprovalError(
            "target projection run card is not a completed provider-free execution"
        )

    raw_outputs = run_card.get("output_paths")
    raw_commitments = run_card.get("output_commitments")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise PurchaseApprovalError("target projection run card lacks output paths")
    if not isinstance(raw_commitments, Mapping):
        raise PurchaseApprovalError("target projection run card lacks commitments")
    output_paths = tuple(
        Path(str(value)) for value in cast(Sequence[object], raw_outputs)
    )
    if len(output_paths) != len(set(output_paths)):
        raise PurchaseApprovalError("target projection output paths are duplicated")
    outputs: dict[str, bytes] = {}
    commitments: dict[str, str] = {}
    for output_path in output_paths:
        absolute = _normalized_absolute(output_path, "target projection output")
        if root not in absolute.parents:
            raise PurchaseApprovalError("target projection output escapes its root")
        payload = projection_bytes(
            absolute, f"target projection output {absolute.name}"
        )
        expected = cast(Mapping[object, object], raw_commitments).get(str(output_path))
        digest = _sha256(payload)
        if expected not in {digest, "sha256:" + digest}:
            raise PurchaseApprovalError(
                f"target projection output commitment differs: {absolute.name}"
            )
        if absolute.name in outputs:
            raise PurchaseApprovalError(
                f"target projection output filename is duplicated: {absolute.name}"
            )
        outputs[absolute.name] = payload
        commitments[absolute.name] = "sha256:" + digest
    if set(outputs) != set(_PROJECTION_OUTPUT_NAMES):
        raise PurchaseApprovalError(
            "target projection output set is incomplete or expanded"
        )

    selection_bytes = outputs["target-cohort-selection.jsonl"]
    selection = _jsonl(selection_bytes, "target cohort selection")
    candidate_ids = tuple(
        _text(row.get("candidate_id"), "candidate_id") for row in selection
    )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise PurchaseApprovalError("target cohort selection has duplicate candidates")

    budget_bytes = outputs["missing-core-budget-plan.json"]
    budget = _json_object(budget_bytes, "missing core budget plan")
    summary_bytes = outputs["target-cohort-projection.json"]
    summary = _json_object(summary_bytes, "target cohort projection")
    target_count = _positive_int(summary.get("target_case_count"), "target_case_count")
    selected_count = _positive_int(
        summary.get("selected_case_count"), "selected_case_count"
    )
    if target_count != selected_count or selected_count != len(candidate_ids):
        raise PurchaseApprovalError("projection target and selection counts differ")
    if run_card.get("record_count") != selected_count:
        raise PurchaseApprovalError("projection run-card record count differs")
    if reduced_n.get("target_clean_cases") != target_count:
        raise PurchaseApprovalError("cohort target differs from projection target")
    if budget.get("target_case_count") != target_count or (
        budget.get("target_case_count_met") is not True
    ):
        raise PurchaseApprovalError("budget plan does not meet the exact target")
    if budget.get("dry_run") is not False:
        raise PurchaseApprovalError("purchase budget must be executable")
    omitted = budget.get("omitted_candidate_ids")
    if not isinstance(omitted, Sequence) or isinstance(omitted, (str, bytes)):
        raise PurchaseApprovalError("budget omitted candidate IDs must be a list")
    omitted_ids = tuple(
        _text(value, "omitted candidate ID")
        for value in cast(Sequence[object], omitted)
    )
    if len(omitted_ids) != len(set(omitted_ids)) or set(omitted_ids) & set(
        candidate_ids
    ):
        raise PurchaseApprovalError("budget omitted candidate IDs are invalid")
    if budget.get("frontier_truncated") is not bool(omitted_ids):
        raise PurchaseApprovalError("budget frontier truncation commitment differs")

    case_plans_raw = budget.get("case_plans")
    if not isinstance(case_plans_raw, Sequence) or isinstance(
        case_plans_raw, (str, bytes)
    ):
        raise PurchaseApprovalError("budget case plans must be a list")
    case_plans = tuple(
        _mapping(item, "budget case plan")
        for item in cast(Sequence[object], case_plans_raw)
    )
    planned_ids = tuple(
        _text(plan.get("candidate_id"), "budget candidate_id") for plan in case_plans
    )
    if planned_ids != candidate_ids:
        raise PurchaseApprovalError("budget plan selection differs from projection")
    reservation = _usd(
        budget.get("cost_per_document_usd"), "cost_per_document_usd", positive=True
    )
    purchase_ids: list[str] = []
    computed_cost = Decimal("0")
    max_per_case = _usd(
        purchase.get("max_per_case_usd"), "max_per_case_usd", positive=True
    )
    for plan in case_plans:
        raw_ids = plan.get("purchase_document_ids")
        if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes)):
            raise PurchaseApprovalError("purchase document IDs must be a list")
        ids = [
            _text(value, "purchase document ID")
            for value in cast(Sequence[object], raw_ids)
        ]
        if len(ids) != len(set(ids)):
            raise PurchaseApprovalError(
                "purchase document IDs are duplicated within a case"
            )
        count = len(ids)
        if (
            plan.get("missing_core_document_count") != count
            or plan.get("estimated_purchase_count") != count
        ):
            raise PurchaseApprovalError(
                "purchase document count differs from case plan"
            )
        estimated = _usd(plan.get("estimated_cost_usd"), "estimated_cost_usd")
        if estimated != reservation * count:
            raise PurchaseApprovalError(
                "case estimated cost does not equal reservations"
            )
        if estimated > max_per_case:
            raise PurchaseApprovalError("case estimated cost exceeds per-case cap")
        purchase_ids.extend(ids)
        computed_cost += estimated
    if len(purchase_ids) != len(set(purchase_ids)):
        raise PurchaseApprovalError("purchase document IDs are duplicated across cases")
    if budget.get("total_missing_core_documents") != len(purchase_ids):
        raise PurchaseApprovalError("budget purchase-document count differs")
    projected_cost = _usd(
        budget.get("total_estimated_cost_usd"), "total_estimated_cost_usd"
    )
    if projected_cost != computed_cost:
        raise PurchaseApprovalError("budget total cost does not reproduce")
    hard_cap = _usd(purchase.get("cycle_budget_usd"), "cycle_budget_usd", positive=True)
    budget_cap = _usd(
        budget.get("max_projected_budget_usd"),
        "max_projected_budget_usd",
        positive=True,
    )
    if hard_cap != budget_cap or projected_cost > hard_cap:
        raise PurchaseApprovalError("projection budget differs from frozen cohort cap")
    if reservation > max_per_case:
        raise PurchaseApprovalError("document reservation exceeds per-case cap")
    if (
        summary.get("total_missing_core_documents") != len(purchase_ids)
        or _usd(
            summary.get("total_estimated_cost_usd"), "summary total_estimated_cost_usd"
        )
        != projected_cost
    ):
        raise PurchaseApprovalError("projection summary differs from budget plan")
    if (
        _usd(
            summary.get("max_projected_budget_usd"),
            "summary max_projected_budget_usd",
            positive=True,
        )
        != hard_cap
    ):
        raise PurchaseApprovalError("projection summary cap differs")
    if (
        summary.get("paid_activity_requested") is not False
        or summary.get("paid_activity_executed") is not False
    ):
        raise PurchaseApprovalError("projection includes paid activity")
    selected_hash = _canonical_sha256(list(candidate_ids))
    if summary.get("selected_candidate_ids_sha256") not in {
        selected_hash,
        "sha256:" + selected_hash,
    }:
        raise PurchaseApprovalError("selected candidate commitment differs")
    if summary.get("budget_plan_sha256") not in {
        _canonical_sha256(budget),
        "sha256:" + _canonical_sha256(budget),
    }:
        raise PurchaseApprovalError("budget plan semantic commitment differs")

    _replay_projection_semantics(
        run_card=run_card,
        outputs=outputs,
        summary=summary,
        verified_artifact_bytes=verified_bytes,
    )

    # Detect source/output replacement between the first read and authority return.
    snapshots = {
        cohort_policy_path: cohort_bytes,
        fee_schedule_path: fee_schedule_bytes,
    }
    for path, payload in snapshots.items():
        if _read_file(path, f"stable approval source {path.name}") != payload:
            raise PurchaseApprovalError(
                f"approval source changed while reading: {path}"
            )
    if require_fresh_ledger_namespace:
        _require_fresh_ledger_namespace(ledger)

    return PurchaseApprovalRequest(
        cycle_id=_text(cohort_body.get("cycle_id"), "cycle_id"),
        cohort_policy_sha256=cohort_hash,
        cohort_policy_file_sha256=_sha256(cohort_bytes),
        fee_schedule_file_sha256=_sha256(fee_schedule_bytes),
        fee_schedule=fee_schedule,
        cohort_policy_path=str(cohort_policy_path),
        fee_schedule_path=str(fee_schedule_path),
        canonical_ledger_path=str(ledger),
        ledger_initial_state="absent_fresh_initialization_required",
        target_cohort_root=str(root),
        target_cohort_run_card_sha256=_sha256(run_card_bytes),
        projection_sha256=_sha256(summary_bytes),
        selection_sha256=_sha256(selection_bytes),
        budget_plan_sha256=_sha256(budget_bytes),
        target_case_count=target_count,
        selected_case_count=selected_count,
        purchase_document_count=len(purchase_ids),
        projected_cost_usd=_money(projected_cost),
        hard_cap_usd=_money(hard_cap),
        max_per_case_usd=_money(max_per_case),
        per_document_reservation_usd=_money(reservation),
        opening_committed_spend_usd="0.00",
        opening_case_committed_spend_usd={},
        remaining_headroom_usd=_money(hard_cap - projected_cost),
        rule=_text(purchase.get("rule"), "purchase rule"),
        session_scope="exact_initial_selection_one_global_session",
        fallback="free_only",
        selected_candidate_ids_sha256=selected_hash,
        purchase_document_ids_sha256=_canonical_sha256(purchase_ids),
        output_commitments=dict(sorted(commitments.items())),
    )


def _replay_projection_semantics(
    *,
    run_card: Mapping[str, object],
    outputs: Mapping[str, bytes],
    summary: Mapping[str, object],
    verified_artifact_bytes: Mapping[str, object],
) -> dict[Path, bytes]:
    """Recompute every deterministic projection output from its nine inputs."""

    raw_inputs = run_card.get("input_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise PurchaseApprovalError("target projection run card lacks exact inputs")
    input_paths = tuple(
        Path(str(value)) for value in cast(Sequence[object], raw_inputs)
    )
    if len(input_paths) != len(_PROJECTION_INPUT_NAMES) or len(input_paths) != len(
        set(input_paths)
    ):
        raise PurchaseApprovalError("target projection input paths differ")
    sources: dict[str, bytes] = {}
    for name, path in zip(_PROJECTION_INPUT_NAMES, input_paths, strict=True):
        payload = verified_artifact_bytes.get(os.path.abspath(path))
        if not isinstance(payload, bytes):
            raise PurchaseApprovalError(
                f"authenticated target projection verifier omitted input {name}"
            )
        sources[name] = payload
    config = _json_object(sources["preparation_config"], "preparation config")
    try:
        reproduced = project_target_cohort(
            selections=_jsonl(sources["selection"], "projection selection input"),
            case_relevance=_jsonl(
                sources["case_relevance"], "projection case-relevance input"
            ),
            download_manifest=_jsonl(
                sources["download_manifest"], "projection manifest input"
            ),
            clearance_records=_jsonl(
                sources["disclosure_clearance"], "projection clearance input"
            ),
            target_case_count=_positive_int(
                config.get("target_case_count"), "preparation target_case_count"
            ),
            cost_per_document_usd=_money(
                _usd(
                    config.get("cost_per_document_usd"),
                    "preparation cost_per_document_usd",
                    positive=True,
                )
            ),
            max_projected_budget_usd=_money(
                _usd(
                    config.get("max_projected_budget_usd"),
                    "preparation max_projected_budget_usd",
                    positive=True,
                )
            ),
            max_missing_core_documents_per_case=_positive_int(
                config.get("max_missing_core_documents_per_case"),
                "preparation max_missing_core_documents_per_case",
            ),
        )
    except TargetCohortProjectionError as exc:
        raise PurchaseApprovalError(
            f"target projection does not reproduce: {exc}"
        ) from exc
    manifest = tuple(reproduced.download_manifest)
    expected = {
        "target-cohort-selection.jsonl": _jsonl_bytes(reproduced.selections),
        "target-cohort-ranked-reserve.jsonl": _jsonl_bytes(reproduced.ranked_reserve),
        "case-relevance.jsonl": _jsonl_bytes(reproduced.case_relevance),
        "free-document-downloads.jsonl": _jsonl_bytes(
            row for row in manifest if row.get("free_or_purchased") == "free"
        ),
        "purchased-document-downloads.jsonl": _jsonl_bytes(
            row for row in manifest if row.get("free_or_purchased") == "purchased"
        ),
        "document-downloads-merged.jsonl": _jsonl_bytes(manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(reproduced.clearance_records),
        "restriction-evidence.jsonl": _jsonl_bytes(reproduced.restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(
            row.to_record() for row in reproduced.core_filter_results
        ),
        "target-cohort-exclusions.jsonl": _jsonl_bytes(reproduced.exclusions),
        "missing-core-budget-plan.json": _pretty_json(
            reproduced.budget_plan.to_record()
        ),
    }
    for name, payload in expected.items():
        if outputs.get(name) != payload:
            raise PurchaseApprovalError(f"target projection does not reproduce: {name}")
    if summary.get("projection_sha256") != reproduced.summary.get("projection_sha256"):
        raise PurchaseApprovalError(
            "target projection semantic digest does not reproduce"
        )
    return dict(zip(input_paths, sources.values(), strict=True))


def record_purchase_approval(
    *,
    request: PurchaseApprovalRequest,
    controlled_private_root: Path,
    decision: str,
    typed_confirmation: str,
    reviewer_id: str,
    recorded_at_utc: str,
    resume: bool = False,
) -> tuple[Path, Path]:
    """Write one private checkpoint and run card; never contact a provider."""

    root = _normalized_absolute(controlled_private_root, "controlled private root")
    normalized_decision = _decision(decision)
    reviewer = _text(reviewer_id, "reviewer_id")
    if reviewer != "John Hughes":
        raise PurchaseApprovalError("official purchase reviewer must be John Hughes")
    recorded = _utc_timestamp(recorded_at_utc)
    required = request.required_confirmation(normalized_decision)
    if typed_confirmation != required:
        raise PurchaseApprovalError("typed confirmation does not match exact request")
    checkpoint_path = root / "purchase-approval-checkpoint.json"
    run_card_path = root / "run-cards/record-purchase-approval.json"
    checkpoint_body: dict[str, object] = {
        "request": request.to_record(),
        "verification_inputs": {
            "target_cohort_root": request.target_cohort_root,
            "cohort_policy_path": request.cohort_policy_path,
            "fee_schedule_path": request.fee_schedule_path,
            "canonical_ledger_path": request.canonical_ledger_path,
        },
        "decision": normalized_decision,
        "reviewer_id": reviewer,
        "recorded_at_utc": recorded,
        "typed_confirmation": typed_confirmation,
        "rule_decision": request.rule,
        "target_decision": request.target_case_count,
        "session_decision": request.session_scope,
        "fallback_decision": request.fallback,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    checkpoint = {
        "schema_version": PURCHASE_APPROVAL_CHECKPOINT_SCHEMA,
        "checkpoint": checkpoint_body,
        "checkpoint_sha256": _canonical_sha256(checkpoint_body),
    }
    checkpoint_bytes = _pretty_json(checkpoint)
    run_card_body = {
        "stage": "record-purchase-approval",
        "status": "completed",
        "decision": normalized_decision,
        "request_sha256": request.request_sha256,
        "checkpoint_sha256": _sha256(checkpoint_bytes),
        "reviewer_id": reviewer,
        "recorded_at_utc": recorded,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    run_card = {
        "schema_version": PURCHASE_APPROVAL_RUN_CARD_SCHEMA,
        "run_card": run_card_body,
        "run_card_sha256": _canonical_sha256(run_card_body),
    }
    run_card_bytes = _pretty_json(run_card)
    _preflight_private_immutable(checkpoint_path, checkpoint_bytes, resume=resume)
    _preflight_private_immutable(run_card_path, run_card_bytes, resume=resume)
    _write_private_immutable(checkpoint_path, checkpoint_bytes, resume=resume)
    _write_private_immutable(run_card_path, run_card_bytes, resume=resume)
    return checkpoint_path, run_card_path


def resume_purchase_approval_recording(
    *,
    request: PurchaseApprovalRequest,
    controlled_private_root: Path,
) -> tuple[Path, Path]:
    """Repair only a missing exact run card from one durable checkpoint."""

    root = _normalized_absolute(controlled_private_root, "controlled private root")
    checkpoint_path = root / "purchase-approval-checkpoint.json"
    run_card_path = root / "run-cards/record-purchase-approval.json"
    checkpoint_bytes = _read_file(checkpoint_path, "purchase approval checkpoint")
    checkpoint_artifact = _json_object(checkpoint_bytes, "purchase approval checkpoint")
    if checkpoint_artifact.get("schema_version") != PURCHASE_APPROVAL_CHECKPOINT_SCHEMA:
        raise PurchaseApprovalError("unsupported purchase approval checkpoint")
    checkpoint = _mapping(checkpoint_artifact.get("checkpoint"), "approval checkpoint")
    _require_exact_keys(
        checkpoint_artifact,
        {"schema_version", "checkpoint", "checkpoint_sha256"},
        "purchase approval checkpoint artifact",
    )
    _require_exact_keys(checkpoint, _CHECKPOINT_BODY_FIELDS, "approval checkpoint")
    if checkpoint_artifact.get("checkpoint_sha256") != _canonical_sha256(checkpoint):
        raise PurchaseApprovalError("purchase approval checkpoint hash differs")
    if checkpoint.get("request") != request.to_record():
        raise PurchaseApprovalError("purchase approval checkpoint request differs")
    decision = _decision(checkpoint.get("decision"))
    confirmation = _text(checkpoint.get("typed_confirmation"), "typed confirmation")
    if confirmation != request.required_confirmation(decision):
        raise PurchaseApprovalError("purchase approval confirmation differs")
    reviewer = _text(checkpoint.get("reviewer_id"), "reviewer_id")
    if reviewer != "John Hughes":
        raise PurchaseApprovalError("official purchase reviewer must be John Hughes")
    recorded = _utc_timestamp(checkpoint.get("recorded_at_utc"))
    _verify_checkpoint_companions(checkpoint, request=request)
    run_card_body = {
        "stage": "record-purchase-approval",
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
    }
    run_card = {
        "schema_version": PURCHASE_APPROVAL_RUN_CARD_SCHEMA,
        "run_card": run_card_body,
        "run_card_sha256": _canonical_sha256(run_card_body),
    }
    _write_private_immutable(run_card_path, _pretty_json(run_card), resume=True)
    return checkpoint_path, run_card_path


def verify_purchase_approval(
    *,
    controlled_private_root: Path,
    checkpoint_path: Path,
    run_card_path: Path,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
) -> VerifiedPurchaseApproval:
    """Replay fresh-ledger evidence and return the sole purchase-minting type."""

    evidence = _verify_purchase_approval_evidence(
        controlled_private_root=controlled_private_root,
        checkpoint_path=checkpoint_path,
        run_card_path=run_card_path,
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy_path,
        fee_schedule_path=fee_schedule_path,
        canonical_ledger_path=canonical_ledger_path,
        require_fresh_ledger_namespace=True,
        required_decision="approve",
    )
    return _mint_verified_purchase_approval(evidence)


def verify_free_only_purchase_approval(
    *,
    controlled_private_root: Path,
    checkpoint_path: Path,
    run_card_path: Path,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
) -> VerifiedFreeOnlyPurchaseApproval:
    """Replay exact ``free_only`` authority without minting purchase authority."""

    evidence = _verify_purchase_approval_evidence(
        controlled_private_root=controlled_private_root,
        checkpoint_path=checkpoint_path,
        run_card_path=run_card_path,
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy_path,
        fee_schedule_path=fee_schedule_path,
        canonical_ledger_path=canonical_ledger_path,
        require_fresh_ledger_namespace=True,
        required_decision="free_only",
    )
    return _mint_verified_free_only_purchase_approval(evidence)


def _verify_purchase_approval_evidence(
    *,
    controlled_private_root: Path,
    checkpoint_path: Path,
    run_card_path: Path,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
    require_fresh_ledger_namespace: bool,
    required_decision: str = "approve",
) -> _VerifiedPurchaseApprovalEvidence:
    """Verify common evidence for minting or existing-policy comparison."""

    private_root = _normalized_absolute(
        controlled_private_root, "controlled private root"
    )
    target_cohort_root = _normalized_absolute(target_cohort_root, "target cohort root")
    cohort_policy_path = _normalized_absolute(cohort_policy_path, "cohort policy path")
    fee_schedule_path = _normalized_absolute(fee_schedule_path, "fee schedule path")
    canonical_ledger_path = _normalized_absolute(
        canonical_ledger_path, "canonical ledger path"
    )
    if checkpoint_path != private_root / "purchase-approval-checkpoint.json" or (
        run_card_path != private_root / "run-cards/record-purchase-approval.json"
    ):
        raise PurchaseApprovalError(
            "purchase approval evidence must use exact controlled-store locations"
        )
    checkpoint_bytes = _read_file(checkpoint_path, "purchase approval checkpoint")
    run_card_bytes = _read_file(run_card_path, "purchase approval run card")
    checkpoint_artifact = _json_object(checkpoint_bytes, "purchase approval checkpoint")
    run_card_artifact = _json_object(run_card_bytes, "purchase approval run card")
    if checkpoint_artifact.get("schema_version") != PURCHASE_APPROVAL_CHECKPOINT_SCHEMA:
        raise PurchaseApprovalError("unsupported purchase approval checkpoint")
    if run_card_artifact.get("schema_version") != PURCHASE_APPROVAL_RUN_CARD_SCHEMA:
        raise PurchaseApprovalError("unsupported purchase approval run card")
    checkpoint = _mapping(checkpoint_artifact.get("checkpoint"), "approval checkpoint")
    run_card = _mapping(run_card_artifact.get("run_card"), "approval run card")
    _require_exact_keys(
        checkpoint_artifact,
        {"schema_version", "checkpoint", "checkpoint_sha256"},
        "purchase approval checkpoint artifact",
    )
    _require_exact_keys(
        run_card_artifact,
        {"schema_version", "run_card", "run_card_sha256"},
        "purchase approval run-card artifact",
    )
    _require_exact_keys(checkpoint, _CHECKPOINT_BODY_FIELDS, "approval checkpoint")
    _require_exact_keys(run_card, _RUN_CARD_BODY_FIELDS, "approval run card")
    if checkpoint_artifact.get("checkpoint_sha256") != _canonical_sha256(checkpoint):
        raise PurchaseApprovalError("purchase approval checkpoint hash differs")
    if run_card_artifact.get("run_card_sha256") != _canonical_sha256(run_card):
        raise PurchaseApprovalError("purchase approval run-card hash differs")
    request = _build_purchase_approval_request(
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy_path,
        fee_schedule_path=fee_schedule_path,
        canonical_ledger_path=canonical_ledger_path,
        require_fresh_ledger_namespace=require_fresh_ledger_namespace,
    )
    if checkpoint.get("request") != request.to_record():
        raise PurchaseApprovalError("purchase approval request bytes or paths changed")
    if checkpoint.get("verification_inputs") != {
        "target_cohort_root": request.target_cohort_root,
        "cohort_policy_path": request.cohort_policy_path,
        "fee_schedule_path": request.fee_schedule_path,
        "canonical_ledger_path": request.canonical_ledger_path,
    }:
        raise PurchaseApprovalError("private approval verification inputs changed")
    decision = _decision(checkpoint.get("decision"))
    expected_decision = _decision(required_decision)
    if decision != expected_decision:
        if expected_decision == "approve":
            raise PurchaseApprovalError(f"{decision} does not authorize purchases")
        raise PurchaseApprovalError(
            f"{decision} does not authorize free-only materialization"
        )
    confirmation = _text(checkpoint.get("typed_confirmation"), "typed confirmation")
    if confirmation != request.required_confirmation(decision):
        raise PurchaseApprovalError("typed confirmation does not bind exact request")
    reviewer = _text(checkpoint.get("reviewer_id"), "reviewer_id")
    if reviewer != "John Hughes":
        raise PurchaseApprovalError("official purchase reviewer must be John Hughes")
    recorded = _utc_timestamp(checkpoint.get("recorded_at_utc"))
    _verify_checkpoint_companions(checkpoint, request=request)
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if checkpoint.get(field) is not False or run_card.get(field) is not False:
            raise PurchaseApprovalError("approval recorder activity flags are invalid")
    if (
        run_card.get("stage") != "record-purchase-approval"
        or run_card.get("status") != "completed"
        or run_card.get("decision") != decision
        or run_card.get("request_sha256") != request.request_sha256
        or run_card.get("checkpoint_sha256") != _sha256(checkpoint_bytes)
        or run_card.get("reviewer_id") != reviewer
        or run_card.get("recorded_at_utc") != recorded
    ):
        raise PurchaseApprovalError("purchase approval run card does not replay")
    if (
        _read_file(checkpoint_path, "stable approval checkpoint") != checkpoint_bytes
        or _read_file(run_card_path, "stable approval run card") != run_card_bytes
    ):
        raise PurchaseApprovalError(
            "purchase approval evidence changed while verifying"
        )
    return _VerifiedPurchaseApprovalEvidence(
        request=request,
        decision=decision,
        reviewer_id=reviewer,
        recorded_at_utc=recorded,
        typed_confirmation_sha256=_sha256(confirmation.encode()),
        checkpoint_sha256=_sha256(checkpoint_bytes),
        run_card_sha256=_sha256(run_card_bytes),
    )


def generate_approved_purchase_policy(
    approval: VerifiedPurchaseApproval,
) -> dict[str, object]:
    """Derive the sole public v2 purchase authority from verified private proof."""

    if (
        type(approval) is not VerifiedPurchaseApproval
        or not approval.is_replay_minted()
    ):
        raise PurchaseApprovalError(
            "purchase authority can be minted only from fresh-ledger verification"
        )
    return _approved_purchase_policy(
        request=approval.request,
        reviewer_id=approval.reviewer_id,
        recorded_at_utc=approval.recorded_at_utc,
        typed_confirmation_sha256=approval.typed_confirmation_sha256,
        checkpoint_sha256=approval.checkpoint_sha256,
        run_card_sha256=approval.run_card_sha256,
    )


def _approved_purchase_policy(
    *,
    request: PurchaseApprovalRequest,
    reviewer_id: str,
    recorded_at_utc: str,
    typed_confirmation_sha256: str,
    checkpoint_sha256: str,
    run_card_sha256: str,
) -> dict[str, object]:
    """Build public bytes from already verified evidence."""

    public_approval = {
        "schema_version": PURCHASE_APPROVAL_SCHEMA,
        "decision": "approve",
        "reviewer_id": reviewer_id,
        "recorded_at_utc": recorded_at_utc,
        "typed_confirmation_sha256": typed_confirmation_sha256,
        "private_checkpoint_sha256": checkpoint_sha256,
        "private_run_card_sha256": run_card_sha256,
        **request.to_record(),
    }
    policy = {
        "cycle_id": request.cycle_id,
        "cohort_policy_sha256": request.cohort_policy_sha256,
        "canonical_ledger_path": request.canonical_ledger_path,
        "hard_cap_usd": request.hard_cap_usd,
        "opening_committed_spend_usd": request.opening_committed_spend_usd,
        "opening_case_committed_spend_usd": dict(
            request.opening_case_committed_spend_usd
        ),
        "max_per_case_usd": request.max_per_case_usd,
        "per_document_reservation_usd": request.per_document_reservation_usd,
        "fee_schedule": dict(request.fee_schedule),
        "approval": public_approval,
    }
    return {
        "schema_version": PURCHASE_POLICY_V2_SCHEMA,
        "policy": policy,
        "policy_sha256": _canonical_sha256(policy),
    }


def replay_approved_purchase_policy(
    *,
    purchase_policy_artifact: Mapping[str, object],
    controlled_private_root: Path,
) -> ReplayedPurchaseApproval:
    """Compare an existing policy to private evidence without minting.

    Ledger absence is an issuance-time fact. This path intentionally does not
    re-probe it, and its distinct return type is rejected by the minting API.
    """

    private_root = _normalized_absolute(
        controlled_private_root, "controlled private root"
    )
    checkpoint_path = private_root / "purchase-approval-checkpoint.json"
    run_card_path = private_root / "run-cards/record-purchase-approval.json"
    checkpoint_artifact = _json_object(
        _read_file(checkpoint_path, "purchase approval checkpoint"),
        "purchase approval checkpoint",
    )
    checkpoint = _mapping(checkpoint_artifact.get("checkpoint"), "approval checkpoint")
    inputs = _mapping(
        checkpoint.get("verification_inputs"), "private approval verification inputs"
    )
    _require_exact_keys(
        inputs,
        {
            "target_cohort_root",
            "cohort_policy_path",
            "fee_schedule_path",
            "canonical_ledger_path",
        },
        "private approval verification inputs",
    )
    evidence = _verify_purchase_approval_evidence(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint_path,
        run_card_path=run_card_path,
        target_cohort_root=Path(
            _text(inputs.get("target_cohort_root"), "target cohort root")
        ),
        cohort_policy_path=Path(
            _text(inputs.get("cohort_policy_path"), "cohort policy path")
        ),
        fee_schedule_path=Path(
            _text(inputs.get("fee_schedule_path"), "fee schedule path")
        ),
        canonical_ledger_path=Path(
            _text(inputs.get("canonical_ledger_path"), "canonical ledger path")
        ),
        require_fresh_ledger_namespace=False,
    )
    expected = _approved_purchase_policy(
        request=evidence.request,
        reviewer_id=evidence.reviewer_id,
        recorded_at_utc=evidence.recorded_at_utc,
        typed_confirmation_sha256=evidence.typed_confirmation_sha256,
        checkpoint_sha256=evidence.checkpoint_sha256,
        run_card_sha256=evidence.run_card_sha256,
    )
    if dict(purchase_policy_artifact) != expected:
        raise PurchaseApprovalError(
            "existing approved v2 policy differs from private authority replay"
        )
    return ReplayedPurchaseApproval(
        policy_sha256=_text(expected.get("policy_sha256"), "purchase policy hash"),
        request_sha256=evidence.request.request_sha256,
        checkpoint_sha256=evidence.checkpoint_sha256,
        run_card_sha256=evidence.run_card_sha256,
    )


def _write_private_immutable(path: Path, payload: bytes, *, resume: bool) -> None:
    """Publish through a no-follow directory fd so parents cannot redirect writes."""

    directory_fd = _open_or_create_private_directory(path.parent)
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    temporary_created = False
    try:
        try:
            existing = _read_unique_regular_at(directory_fd, path.name)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if not resume or existing != payload:
                raise PurchaseApprovalError(
                    "private approval output already exists with incompatible state"
                )
            return
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
            raise PurchaseApprovalError(
                "private approval output was concurrently created"
            ) from exc
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_created = False
        os.fsync(directory_fd)
        if _read_unique_regular_at(directory_fd, path.name) != payload:
            raise PurchaseApprovalError(
                "private approval output changed during publication"
            )
    except OSError as exc:
        raise PurchaseApprovalError(
            f"private approval output cannot be safely published: {path}"
        ) from exc
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        os.close(directory_fd)


def _preflight_private_immutable(path: Path, payload: bytes, *, resume: bool) -> None:
    try:
        directory_fd = _open_or_create_private_directory(path.parent)
    except OSError as exc:
        raise PurchaseApprovalError(
            f"private approval output cannot be safely preflighted: {path}"
        ) from exc
    try:
        try:
            existing = _read_unique_regular_at(directory_fd, path.name)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise PurchaseApprovalError(
                f"private approval output cannot be safely preflighted: {path}"
            ) from exc
        if not resume or existing != payload:
            raise PurchaseApprovalError(
                "private approval output already exists with incompatible state"
            )
    finally:
        os.close(directory_fd)


def _open_or_create_private_directory(path: Path) -> int:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise PurchaseApprovalError(
            "private approval directory must be an absolute normalized path"
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
            raise PurchaseApprovalError(
                "private approval output must be a unique regular file"
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
            raise PurchaseApprovalError("private approval output changed while reading")
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise PurchaseApprovalError("private approval output changed while reading")
        return payload
    finally:
        os.close(descriptor)


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], label: str
) -> None:
    if set(value) != set(expected):
        missing = sorted(set(expected) - set(value))
        unexpected = sorted(set(value) - set(expected))
        raise PurchaseApprovalError(
            f"{label} keys mismatch; missing={missing}, unexpected={unexpected}"
        )


def _verify_checkpoint_companions(
    checkpoint: Mapping[str, object], *, request: PurchaseApprovalRequest
) -> None:
    if (
        checkpoint.get("rule_decision") != request.rule
        or checkpoint.get("target_decision") != request.target_case_count
        or checkpoint.get("session_decision") != request.session_scope
        or checkpoint.get("fallback_decision") != request.fallback
    ):
        raise PurchaseApprovalError(
            "purchase approval companion decisions differ from the request"
        )
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if checkpoint.get(field) is not False:
            raise PurchaseApprovalError("approval recorder activity flags are invalid")


def _require_fresh_ledger_namespace(path: Path) -> None:
    """Prove this approval starts from a not-yet-initialized purchase journal."""

    reserved = (
        path,
        Path(f"{path}.lock"),
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    )
    for candidate in reserved:
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        raise PurchaseApprovalError(
            f"purchase approval requires an absent fresh ledger namespace: {candidate}"
        )
    current = Path(path.anchor)
    for component in path.parent.parts[1:]:
        current /= component
        try:
            current.lstat()
        except FileNotFoundError:
            break
        if current.is_symlink() or not current.is_dir():
            raise PurchaseApprovalError(
                "canonical ledger parent must not traverse a symlink or non-directory"
            )


def require_fresh_purchase_ledger_namespace(path: Path) -> None:
    """Public pre-init gate for a policy's canonical SQLite namespace."""

    _require_fresh_ledger_namespace(_normalized_absolute(path, "canonical ledger path"))


def _validated_fee_schedule(
    schedule: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "source_citation",
        "verified_at_utc",
        "includes_pacer_fees",
        "includes_service_fees",
        "includes_rounding",
    }
    if set(schedule) != expected:
        raise PurchaseApprovalError("fee schedule fields differ from v1 authority")
    source = _text(schedule.get("source_citation"), "fee source citation")
    verified = _utc_timestamp(schedule.get("verified_at_utc"))
    for field in (
        "includes_pacer_fees",
        "includes_service_fees",
        "includes_rounding",
    ):
        if schedule.get(field) is not True:
            raise PurchaseApprovalError(f"fee schedule {field} must be true")
    return {
        "source_citation": source,
        "verified_at_utc": verified,
        "includes_pacer_fees": True,
        "includes_service_fees": True,
        "includes_rounding": True,
    }


def _read_file(path: Path, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError, ValueError) as exc:
        raise PurchaseApprovalError(f"{label} must be a unique regular file") from exc


def _normalized_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise PurchaseApprovalError(f"{label} must be an absolute normalized path")
    return path


def _json_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PurchaseApprovalError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PurchaseApprovalError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _jsonl(payload: bytes, label: str) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    try:
        lines = payload.decode().splitlines()
    except UnicodeError as exc:
        raise PurchaseApprovalError(f"{label} is not UTF-8") from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PurchaseApprovalError(f"{label} is not valid JSONL") from exc
        if not isinstance(value, dict):
            raise PurchaseApprovalError(f"{label} rows must be objects")
        rows.append(cast(dict[str, object], value))
    return tuple(rows)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PurchaseApprovalError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise PurchaseApprovalError(f"{label} must be a nonempty canonical string")
    return value


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise PurchaseApprovalError(f"{label} must be a positive integer")
    return value


def _decision(value: object) -> str:
    if not isinstance(value, str) or value not in _DECISIONS:
        raise PurchaseApprovalError("decision must be approve, reject, or free_only")
    return value


def _usd(value: object, label: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, str) or _USD.fullmatch(value) is None:
        raise PurchaseApprovalError(f"{label} must be canonical nonnegative USD")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise PurchaseApprovalError(f"{label} is invalid") from exc
    if positive and amount <= 0:
        raise PurchaseApprovalError(f"{label} must be positive")
    return amount


def _utc_timestamp(value: object) -> str:
    text = _text(value, "recorded_at_utc")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PurchaseApprovalError("recorded_at_utc must be ISO-8601") from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise PurchaseApprovalError("recorded_at_utc must be UTC")
    return text


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return _sha256(_canonical_bytes(value))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _jsonl_bytes(values: Sequence[Mapping[str, object]] | Any) -> bytes:
    return b"".join(
        (json.dumps(dict(value), sort_keys=True, allow_nan=False) + "\n").encode()
        for value in values
    )

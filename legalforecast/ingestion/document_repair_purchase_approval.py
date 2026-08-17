"""Supported TTY issuance of purchase authority for one document-repair tranche.

``legalforecast.ingestion.document_repair_executor`` already enforces paid
access fail-closed:

* ``build_document_repair_purchase_authority`` refuses anything but a
  replay-minted execution bound to an independently approved
  ``legalforecast.case_dev_purchase_policy.v2`` artifact.
* ``verify_document_repair_purchase_runtime`` refuses until that policy's
  canonical ledger has been initialized and its receipt authenticates against
  the policy and cohort file digests.

Nothing issued either artifact for a repair tranche. The 147-document tranche
shipped through a private script that synthesized the checkpoint from a
confirmation string pasted into chat; its own checkpoint recorded
``typed_confirmation_normalized_from_wrapped_chat: true``. That satisfied the
enforcement checks while defeating what the TTY requirement exists to prove.
This module is the supported issuance half, and it changes none of the
enforcement above: it builds *to* those contracts.

**The displayed string is the only signing material.** The recorder derives
every fact it shows -- cost, document count, case count, ceiling, headroom,
ledger path, execution digest -- from authenticated bytes it read itself, then
prints the exact confirmation phrase at the TTY. A phrase circulated in chat is
not authoritative and cannot be made authoritative by pasting it back.

Private evidence reuses the established
``legalforecast.purchase_approval_checkpoint.v1`` recorder rather than forking a
second immutable-write spine, so no new schema identifier is introduced. The
approval body a repair tranche must publish is fixed by the frozen validator
``_validated_public_purchase_approval``, which admits *exactly* the
project-target-cohort field names and no others. Repair lineage therefore lives
in ``output_commitments``, the one free-form member, under this mapping:

======================================  =====================================
frozen field                            document-repair meaning
======================================  =====================================
``target_cohort_root``                  repair tranche root holding every input
``target_cohort_run_card_sha256``       approved repair-plan approval record
``projection_sha256``                   ``execution.execution_sha256``
``selection_sha256``                    ``execution.full_plan_sha256``
``budget_plan_sha256``                  canonical repair purchase-budget record
``target_case_count``/``selected_``     paid cases in the tranche
``rule``                                ``buy_exact_approved_document_repairs``
======================================  =====================================

A cohort checkpoint cannot verify here and a repair checkpoint cannot verify in
the cohort recorder: each verifier recomputes its own request from its own
inputs and compares the whole record, so a cross-fed checkpoint fails closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from legalforecast.contracts import ARTIFACT_JSON_VALUE_V1
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.document_repair_errors import DocumentRepairExecutorError
from legalforecast.ingestion.document_repair_executor import (
    DocumentRepairExecution,
    DocumentRepairPurchaseAuthority,
    DocumentRepairPurchaseRuntime,
    build_document_repair_purchase_authority,
    build_full_document_repair_execution,
    replay_docket_snapshot_authority,
    verify_document_repair_purchase_runtime,
    verify_purchase_policy_compatibility,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentSuccessorError,
    build_missing_document_acquisition_plan,
    verify_repair_plan_approval,
)

# These four are the shared identity of the checkpoint/run-card schema this
# module writes through ``record_purchase_approval`` and of the public approval
# body the frozen v2 validator accepts. Re-declaring them here would let the
# writer and the verifier drift apart silently, which is the one failure this
# module exists to prevent, so they are imported rather than copied.
from legalforecast.ingestion.purchase_approval import (
    _CHECKPOINT_BODY_FIELDS,  # pyright: ignore[reportPrivateUsage]
    _RUN_CARD_BODY_FIELDS,  # pyright: ignore[reportPrivateUsage]
    PURCHASE_APPROVAL_CHECKPOINT_SCHEMA,
    PURCHASE_APPROVAL_RUN_CARD_SCHEMA,
    PurchaseApprovalError,
    PurchaseApprovalRequest,
    _approved_purchase_policy,  # pyright: ignore[reportPrivateUsage]
    _validated_fee_schedule,  # pyright: ignore[reportPrivateUsage]
    _verify_checkpoint_companions,  # pyright: ignore[reportPrivateUsage]
    require_fresh_purchase_ledger_namespace,
)

#: The rule recorded and typed for a repair tranche. It is deliberately not the
#: cohort's own selection rule: a repair tranche buys an already-approved exact
#: document set rather than selecting one, and the distinct phrase gives the
#: reviewer a visible separation from a cohort purchase at the TTY.
DOCUMENT_REPAIR_PURCHASE_RULE = "buy_exact_approved_document_repairs"

_SHA256 = re.compile(r"[0-9a-f]{64}")

#: Fixed by the frozen v2 approval validator.
_SESSION_SCOPE = "exact_initial_selection_one_global_session"
_FALLBACK = "free_only"
_LEDGER_INITIAL_STATE = "absent_fresh_initialization_required"

_CHECKPOINT_NAME = "purchase-approval-checkpoint.json"
_RUN_CARD_NAME = "run-cards/record-purchase-approval.json"

_VERIFIED_REPAIR_APPROVAL_MINT = object()


class DocumentRepairPurchaseApprovalError(ValueError):
    """Raised when repair-tranche purchase authority cannot be issued or proven."""


@dataclass(frozen=True, slots=True)
class DocumentRepairPurchaseInputs:
    """Exact authenticated inputs that mint one repair tranche's execution.

    Every path must resolve inside ``repair_execution_root`` so the root
    recorded in the checkpoint is a complete pointer to what was signed.
    ``source_lineage_sha256`` is the operator-supplied external pin the
    snapshot authority replays against; it is an argument rather than a file in
    the root because a pin read from the material it pins proves nothing.
    """

    repair_execution_root: Path
    repair_manifest_path: Path
    repair_plan_approval_path: Path
    docket_snapshot_manifest_path: Path
    source_lineage_path: Path
    source_lineage_sha256: str
    docket_snapshot_dir: Path

    def to_record(self) -> dict[str, str]:
        """Return the operator-facing echo of these inputs."""

        return {
            "repair_execution_root": str(self.repair_execution_root),
            "repair_manifest_path": str(self.repair_manifest_path),
            "repair_plan_approval_path": str(self.repair_plan_approval_path),
            "docket_snapshot_manifest_path": str(self.docket_snapshot_manifest_path),
            "source_lineage_path": str(self.source_lineage_path),
            "source_lineage_sha256": self.source_lineage_sha256,
            "docket_snapshot_dir": str(self.docket_snapshot_dir),
        }


@dataclass(frozen=True, slots=True)
class DocumentRepairPurchaseProjection:
    """One repair tranche's replay-minted execution and its approval request."""

    request: PurchaseApprovalRequest
    execution: DocumentRepairExecution

    def display_lines(self) -> tuple[str, ...]:
        """Return the recorder-derived facts shown before any typed phrase."""

        request = self.request
        return (
            f"cycle:                 {request.cycle_id}",
            f"rule:                  {request.rule}",
            f"repair execution:      sha256:{self.execution.execution_sha256}",
            f"repair scope:          {self.execution.scope}",
            f"paid cases:            {request.selected_case_count}",
            f"paid documents:        {request.purchase_document_count}",
            f"per document:          USD {request.per_document_reservation_usd}",
            f"projected cost:        USD {request.projected_cost_usd}",
            f"cycle ceiling:         USD {request.hard_cap_usd}",
            f"per-case ceiling:      USD {request.max_per_case_usd}",
            f"remaining headroom:    USD {request.remaining_headroom_usd}",
            f"canonical ledger:      {request.canonical_ledger_path}",
            f"ledger initial state:  {request.ledger_initial_state}",
            f"request:               sha256:{request.request_sha256}",
        )


@dataclass(frozen=True, slots=True, init=False)
class VerifiedDocumentRepairPurchaseApproval:
    """Replay-verified private repair approval; the sole policy-minting type."""

    request: PurchaseApprovalRequest
    execution_sha256: str
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation_sha256: str
    checkpoint_sha256: str
    run_card_sha256: str
    _mint_token: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise DocumentRepairPurchaseApprovalError(
            "VerifiedDocumentRepairPurchaseApproval requires evidence replay"
        )

    def is_replay_minted(self) -> bool:
        """Whether this instance came from :func:`verify_...approval`."""

        return self._mint_token is _VERIFIED_REPAIR_APPROVAL_MINT


@dataclass(frozen=True, slots=True)
class DocumentRepairPurchaseIssuance:
    """Authority, initialized ledger receipt, and runtime for one execution."""

    authority: DocumentRepairPurchaseAuthority
    runtime: DocumentRepairPurchaseRuntime
    initialization_receipt: Mapping[str, object]
    initialization_receipt_path: Path


def build_document_repair_purchase_approval_request(
    *,
    inputs: DocumentRepairPurchaseInputs,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
) -> DocumentRepairPurchaseProjection:
    """Replay one repair tranche into the exact facts a reviewer must sign.

    The execution is minted here, from bytes this function read and digested,
    so no caller-supplied cost, count, or digest reaches the typed phrase.
    """

    root = _normalized(inputs.repair_execution_root, "repair execution root")
    if root.is_symlink() or not root.is_dir():
        raise DocumentRepairPurchaseApprovalError(
            "repair execution root must be a real directory"
        )
    ledger = _normalized(canonical_ledger_path, "canonical ledger path")
    cohort_path = _normalized(cohort_policy_path, "cohort policy path")
    fee_path = _normalized(fee_schedule_path, "fee schedule path")
    contained = {
        "repair manifest": _normalized(inputs.repair_manifest_path, "repair manifest"),
        "repair plan approval": _normalized(
            inputs.repair_plan_approval_path, "repair plan approval"
        ),
        "docket snapshot manifest": _normalized(
            inputs.docket_snapshot_manifest_path, "docket snapshot manifest"
        ),
        "source lineage": _normalized(inputs.source_lineage_path, "source lineage"),
        "docket snapshot directory": _normalized(
            inputs.docket_snapshot_dir, "docket snapshot directory"
        ),
    }
    for label, path in contained.items():
        if root not in path.parents:
            raise DocumentRepairPurchaseApprovalError(
                f"{label} escapes the repair execution root: {path}"
            )
    _require_fresh_ledger(ledger)

    manifest_bytes = _read(contained["repair manifest"], "repair manifest")
    plan_approval_bytes = _read(
        contained["repair plan approval"], "repair plan approval"
    )
    snapshot_manifest_bytes = _read(
        contained["docket snapshot manifest"], "docket snapshot manifest"
    )
    lineage_bytes = _read(contained["source lineage"], "source lineage")
    cohort_bytes = _read(cohort_path, "cohort policy")
    fee_bytes = _read(fee_path, "fee schedule")

    cohort_artifact = _json_object(cohort_bytes, "cohort policy")
    try:
        cohort_policy_sha256 = verify_cohort_policy(cohort_artifact)
    except (CohortPolicyError, ValueError) as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"invalid cohort policy: {exc}"
        ) from exc
    cohort_body = _mapping(cohort_artifact.get("policy"), "cohort policy content")
    purchase_policy = _mapping(
        cohort_body.get("purchase_policy"), "cohort purchase policy"
    )
    fee_schedule = _validated_fee_schedule(_json_object(fee_bytes, "fee schedule"))

    try:
        plan = build_missing_document_acquisition_plan(
            manifest_bytes=manifest_bytes,
            approval=verify_repair_plan_approval(
                manifest_bytes,
                _json_object(plan_approval_bytes, "repair plan approval"),
            ),
        )
    except (MissingDocumentSuccessorError, ValueError) as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"approved repair plan does not replay: {exc}"
        ) from exc

    try:
        snapshot_authority = replay_docket_snapshot_authority(
            manifest_bytes=snapshot_manifest_bytes,
            source_lineage_bytes=lineage_bytes,
            expected_source_lineage_sha256=_digest(
                inputs.source_lineage_sha256, "source lineage pin"
            ),
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"docket snapshot authority does not replay: {exc}"
        ) from exc
    # The tranche's own lineage pins a cohort policy digest. Requiring it to
    # equal the digest of the separately supplied cohort policy file is what
    # stops a tranche root from certifying itself against a policy nobody read.
    if snapshot_authority.cohort_policy_sha256 != cohort_policy_sha256:
        raise DocumentRepairPurchaseApprovalError(
            "repair source lineage is bound to a different cohort policy"
        )

    candidate_ids = tuple(dict.fromkeys(item.candidate_id for item in plan.items))
    snapshot_bytes: dict[str, bytes] = {}
    for candidate_id in candidate_ids:
        snapshot_path = _snapshot_path(
            contained["docket snapshot directory"], candidate_id
        )
        snapshot_bytes[candidate_id] = _read(
            snapshot_path, f"docket snapshot {candidate_id}"
        )
    try:
        execution = build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshot_bytes,
            docket_snapshot_sha256={
                candidate_id: hashlib.sha256(payload).hexdigest()
                for candidate_id, payload in snapshot_bytes.items()
            },
            snapshot_authority=snapshot_authority,
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"repair execution does not replay: {exc}"
        ) from exc

    budget = execution.purchase_budget
    if not budget.case_plans:
        raise DocumentRepairPurchaseApprovalError(
            "repair tranche has no paid operations; no purchase approval is required"
        )
    paid_candidate_ids = tuple(plan.candidate_id for plan in budget.case_plans)
    document_ids = tuple(
        document_id
        for case_plan in budget.case_plans
        for document_id in case_plan.purchase_document_ids
    )
    projected_cost = budget.total_estimated_cost
    reservation = budget.cost_per_document
    hard_cap = _usd(purchase_policy.get("cycle_budget_usd"), "cycle_budget_usd")
    max_per_case = _usd(purchase_policy.get("max_per_case_usd"), "max_per_case_usd")
    # Refuse here rather than at execution: a projection the executor would
    # reject must never reach the reviewer's screen as signable.
    if projected_cost != reservation * len(document_ids):
        raise DocumentRepairPurchaseApprovalError(
            "repair budget total does not equal its per-document reservations"
        )
    if projected_cost > hard_cap:
        raise DocumentRepairPurchaseApprovalError(
            "repair tranche projected cost exceeds the frozen cycle ceiling"
        )
    for case_plan in budget.case_plans:
        if case_plan.estimated_cost > max_per_case:
            raise DocumentRepairPurchaseApprovalError(
                "repair tranche case cost exceeds the per-case ceiling: "
                f"{case_plan.candidate_id}"
            )

    request = PurchaseApprovalRequest(
        cycle_id=_text(cohort_body.get("cycle_id"), "cycle_id"),
        cohort_policy_sha256=cohort_policy_sha256,
        cohort_policy_file_sha256=hashlib.sha256(cohort_bytes).hexdigest(),
        fee_schedule_file_sha256=hashlib.sha256(fee_bytes).hexdigest(),
        fee_schedule=fee_schedule,
        cohort_policy_path=str(cohort_path),
        fee_schedule_path=str(fee_path),
        canonical_ledger_path=str(ledger),
        ledger_initial_state=_LEDGER_INITIAL_STATE,
        target_cohort_root=str(root),
        target_cohort_run_card_sha256=plan.approval_sha256,
        projection_sha256=execution.execution_sha256,
        selection_sha256=execution.full_plan_sha256,
        budget_plan_sha256=_value_sha256(budget.to_record()),
        target_case_count=len(paid_candidate_ids),
        selected_case_count=len(paid_candidate_ids),
        purchase_document_count=len(document_ids),
        projected_cost_usd=_money(projected_cost),
        hard_cap_usd=_money(hard_cap),
        max_per_case_usd=_money(max_per_case),
        per_document_reservation_usd=_money(reservation),
        opening_committed_spend_usd="0.00",
        opening_case_committed_spend_usd={},
        remaining_headroom_usd=_money(hard_cap - projected_cost),
        rule=DOCUMENT_REPAIR_PURCHASE_RULE,
        session_scope=_SESSION_SCOPE,
        fallback=_FALLBACK,
        # The executor recomputes both with its own encoder; use that encoder
        # here rather than a locally reimplemented canonical form.
        selected_candidate_ids_sha256=_value_sha256(list(paid_candidate_ids)),
        purchase_document_ids_sha256=_value_sha256(list(document_ids)),
        output_commitments={
            "repair_execution": "sha256:" + execution.execution_sha256,
            "repair_full_plan": "sha256:" + execution.full_plan_sha256,
            "repair_manifest": "sha256:" + execution.manifest_sha256,
            "repair_plan_approval": "sha256:" + plan.approval_sha256,
            "repair_purchase_budget": "sha256:" + _value_sha256(budget.to_record()),
            "docket_snapshot_manifest": "sha256:" + snapshot_authority.manifest_sha256,
            "source_lineage": "sha256:" + execution.source_lineage_sha256,
            "cohort_policy": "sha256:" + cohort_policy_sha256,
        },
    )

    # Detect source replacement between the first read and authority return.
    for label, path, payload in (
        ("repair manifest", contained["repair manifest"], manifest_bytes),
        (
            "repair plan approval",
            contained["repair plan approval"],
            plan_approval_bytes,
        ),
        (
            "docket snapshot manifest",
            contained["docket snapshot manifest"],
            snapshot_manifest_bytes,
        ),
        ("source lineage", contained["source lineage"], lineage_bytes),
        ("cohort policy", cohort_path, cohort_bytes),
        ("fee schedule", fee_path, fee_bytes),
    ):
        if _read(path, f"stable {label}") != payload:
            raise DocumentRepairPurchaseApprovalError(
                f"repair approval source changed while reading: {label}"
            )
    for candidate_id, payload in snapshot_bytes.items():
        snapshot_path = _snapshot_path(
            contained["docket snapshot directory"], candidate_id
        )
        if _read(snapshot_path, f"stable docket snapshot {candidate_id}") != payload:
            raise DocumentRepairPurchaseApprovalError(
                f"repair approval source changed while reading: snapshot {candidate_id}"
            )
    _require_fresh_ledger(ledger)
    return DocumentRepairPurchaseProjection(request=request, execution=execution)


def verify_document_repair_purchase_approval(
    *,
    controlled_private_root: Path,
    checkpoint_path: Path,
    run_card_path: Path,
    inputs: DocumentRepairPurchaseInputs,
    cohort_policy_path: Path,
    fee_schedule_path: Path,
    canonical_ledger_path: Path,
) -> VerifiedDocumentRepairPurchaseApproval:
    """Replay private repair-approval evidence and mint the policy authority."""

    private_root = _normalized(controlled_private_root, "controlled private root")
    if (
        _normalized(checkpoint_path, "checkpoint path")
        != private_root / _CHECKPOINT_NAME
        or _normalized(run_card_path, "approval run card")
        != private_root / _RUN_CARD_NAME
    ):
        raise DocumentRepairPurchaseApprovalError(
            "repair approval evidence must use exact controlled-store locations"
        )
    checkpoint_bytes = _read(
        private_root / _CHECKPOINT_NAME, "repair approval checkpoint"
    )
    run_card_bytes = _read(private_root / _RUN_CARD_NAME, "repair approval run card")
    checkpoint_artifact = _json_object(checkpoint_bytes, "repair approval checkpoint")
    run_card_artifact = _json_object(run_card_bytes, "repair approval run card")
    if checkpoint_artifact.get("schema_version") != PURCHASE_APPROVAL_CHECKPOINT_SCHEMA:
        raise DocumentRepairPurchaseApprovalError(
            "unsupported repair approval checkpoint"
        )
    if run_card_artifact.get("schema_version") != PURCHASE_APPROVAL_RUN_CARD_SCHEMA:
        raise DocumentRepairPurchaseApprovalError(
            "unsupported repair approval run card"
        )
    checkpoint = _mapping(
        checkpoint_artifact.get("checkpoint"), "repair approval checkpoint"
    )
    run_card = _mapping(run_card_artifact.get("run_card"), "repair approval run card")
    _exact_keys(
        checkpoint_artifact,
        {"schema_version", "checkpoint", "checkpoint_sha256"},
        "repair approval checkpoint artifact",
    )
    _exact_keys(
        run_card_artifact,
        {"schema_version", "run_card", "run_card_sha256"},
        "repair approval run-card artifact",
    )
    _exact_keys(checkpoint, _CHECKPOINT_BODY_FIELDS, "repair approval checkpoint")
    _exact_keys(run_card, _RUN_CARD_BODY_FIELDS, "repair approval run card")
    if checkpoint_artifact.get("checkpoint_sha256") != _value_sha256(checkpoint):
        raise DocumentRepairPurchaseApprovalError(
            "repair approval checkpoint hash differs"
        )
    if run_card_artifact.get("run_card_sha256") != _value_sha256(run_card):
        raise DocumentRepairPurchaseApprovalError(
            "repair approval run-card hash differs"
        )

    projection = build_document_repair_purchase_approval_request(
        inputs=inputs,
        cohort_policy_path=cohort_policy_path,
        fee_schedule_path=fee_schedule_path,
        canonical_ledger_path=canonical_ledger_path,
    )
    request = projection.request
    if checkpoint.get("request") != request.to_record():
        raise DocumentRepairPurchaseApprovalError(
            "repair approval request bytes or paths changed"
        )
    if checkpoint.get("verification_inputs") != {
        "target_cohort_root": request.target_cohort_root,
        "cohort_policy_path": request.cohort_policy_path,
        "fee_schedule_path": request.fee_schedule_path,
        "canonical_ledger_path": request.canonical_ledger_path,
    }:
        raise DocumentRepairPurchaseApprovalError(
            "private repair approval verification inputs changed"
        )
    decision = _text(checkpoint.get("decision"), "decision")
    if decision != "approve":
        raise DocumentRepairPurchaseApprovalError(
            f"{decision} does not authorize repair purchases"
        )
    confirmation = _text(checkpoint.get("typed_confirmation"), "typed confirmation")
    if confirmation != request.required_confirmation(decision):
        raise DocumentRepairPurchaseApprovalError(
            "typed confirmation does not bind the exact repair request"
        )
    reviewer = _text(checkpoint.get("reviewer_id"), "reviewer_id")
    if reviewer != "John Hughes":
        raise DocumentRepairPurchaseApprovalError(
            "official purchase reviewer must be John Hughes"
        )
    recorded = _text(checkpoint.get("recorded_at_utc"), "recorded_at_utc")
    try:
        _verify_checkpoint_companions(checkpoint, request=request)
    except PurchaseApprovalError as exc:
        raise DocumentRepairPurchaseApprovalError(str(exc)) from exc
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "pacer_fee_acknowledged",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if checkpoint.get(field) is not False or run_card.get(field) is not False:
            raise DocumentRepairPurchaseApprovalError(
                "repair approval recorder activity flags are invalid"
            )
    if (
        run_card.get("stage") != "record-purchase-approval"
        or run_card.get("status") != "completed"
        or run_card.get("decision") != decision
        or run_card.get("request_sha256") != request.request_sha256
        or run_card.get("checkpoint_sha256")
        != hashlib.sha256(checkpoint_bytes).hexdigest()
        or run_card.get("reviewer_id") != reviewer
        or run_card.get("recorded_at_utc") != recorded
    ):
        raise DocumentRepairPurchaseApprovalError(
            "repair approval run card does not replay"
        )
    if (
        _read(private_root / _CHECKPOINT_NAME, "stable repair checkpoint")
        != checkpoint_bytes
        or _read(private_root / _RUN_CARD_NAME, "stable repair run card")
        != run_card_bytes
    ):
        raise DocumentRepairPurchaseApprovalError(
            "repair approval evidence changed while verifying"
        )
    approval = object.__new__(VerifiedDocumentRepairPurchaseApproval)
    for name, value in (
        ("request", request),
        ("execution_sha256", projection.execution.execution_sha256),
        ("reviewer_id", reviewer),
        ("recorded_at_utc", recorded),
        (
            "typed_confirmation_sha256",
            hashlib.sha256(confirmation.encode()).hexdigest(),
        ),
        ("checkpoint_sha256", hashlib.sha256(checkpoint_bytes).hexdigest()),
        ("run_card_sha256", hashlib.sha256(run_card_bytes).hexdigest()),
        ("_mint_token", _VERIFIED_REPAIR_APPROVAL_MINT),
    ):
        object.__setattr__(approval, name, value)
    return approval


def generate_approved_document_repair_purchase_policy(
    approval: VerifiedDocumentRepairPurchaseApproval,
) -> dict[str, object]:
    """Derive the public v2 purchase authority from verified private proof."""

    if (
        type(approval) is not VerifiedDocumentRepairPurchaseApproval
        or not approval.is_replay_minted()
    ):
        raise DocumentRepairPurchaseApprovalError(
            "repair purchase authority can be minted only from fresh-ledger "
            "verification"
        )
    return _approved_purchase_policy(
        request=approval.request,
        reviewer_id=approval.reviewer_id,
        recorded_at_utc=approval.recorded_at_utc,
        typed_confirmation_sha256=approval.typed_confirmation_sha256,
        checkpoint_sha256=approval.checkpoint_sha256,
        run_card_sha256=approval.run_card_sha256,
    )


def verify_document_repair_purchase_policy_binds(
    *,
    execution: DocumentRepairExecution,
    purchase_policy_artifact: Mapping[str, object],
) -> CaseDevPurchasePolicy:
    """Prove an issued policy will bind, consuming nothing and minting nothing.

    This is the repeatable issuance-time preflight. It runs the executor's own
    compatibility check, so a pass here means the paid entrypoint will accept
    the policy; it neither creates the ledger nor mints authority, so it can be
    run as often as needed before the execution sitting.
    """

    try:
        return verify_purchase_policy_compatibility(
            execution=execution,
            purchase_policy_artifact=purchase_policy_artifact,
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"issued repair purchase policy does not bind this execution: {exc}"
        ) from exc


def initialize_document_repair_purchase_runtime(
    *,
    execution: DocumentRepairExecution,
    purchase_policy_path: Path,
    cohort_policy_path: Path,
    initialization_receipt_path: Path,
    initialized_at: str,
) -> DocumentRepairPurchaseIssuance:
    """Mint authority, initialize the ledger, and verify the paid runtime.

    The order here is the whole point and is not a matter of taste.
    ``build_document_repair_purchase_authority`` refuses once the canonical
    ledger exists, while ``verify_document_repair_purchase_runtime`` refuses
    until it does. Authority must therefore be minted *before* initialization,
    in the same process that will execute -- neither object can be serialized
    and rebuilt later. Initializing the ledger from a separate step would leave
    the tranche permanently unable to mint authority, which is why no CLI
    subcommand exposes initialization on its own.
    """

    policy_path = _normalized(purchase_policy_path, "purchase policy path")
    cohort_path = _normalized(cohort_policy_path, "cohort policy path")
    receipt_path = _normalized(
        initialization_receipt_path, "initialization receipt path"
    )
    policy_bytes = _read(policy_path, "approved purchase policy")
    cohort_bytes = _read(cohort_path, "cohort policy")
    artifact = _json_object(policy_bytes, "approved purchase policy")
    try:
        authority = build_document_repair_purchase_authority(
            execution=execution,
            approved_purchase_policy_artifact=artifact,
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"repair purchase authority does not bind this execution: {exc}"
        ) from exc
    policy_commitment = "sha256:" + hashlib.sha256(policy_bytes).hexdigest()
    cohort_commitment = "sha256:" + hashlib.sha256(cohort_bytes).hexdigest()
    try:
        receipt = initialize_case_dev_purchase_journal(
            authority.purchase_policy.canonical_ledger_path,
            policy=authority.purchase_policy,
            receipt_path=receipt_path,
            purchase_policy_file_sha256=policy_commitment,
            cohort_policy_file_sha256=cohort_commitment,
            initialized_at=initialized_at,
        )
    except (CaseDevPurchaseLedgerError, CaseDevPurchasePolicyError) as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"repair purchase ledger cannot be initialized: {exc}"
        ) from exc
    try:
        runtime = verify_document_repair_purchase_runtime(
            execution=execution,
            purchase_authority=authority,
            initialization_receipt_path=receipt_path,
            purchase_policy_file_sha256=policy_commitment,
            cohort_policy_file_sha256=cohort_commitment,
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"repair purchase runtime does not verify: {exc}"
        ) from exc
    return DocumentRepairPurchaseIssuance(
        authority=authority,
        runtime=runtime,
        initialization_receipt=receipt,
        initialization_receipt_path=receipt_path,
    )


def read_approved_document_repair_purchase_policy(
    path: Path,
) -> tuple[dict[str, object], CaseDevPurchasePolicy]:
    """Read and type one issued v2 policy artifact without minting authority."""

    artifact = _json_object(
        _read(_normalized(path, "purchase policy path"), "approved purchase policy"),
        "approved purchase policy",
    )
    try:
        return artifact, verify_case_dev_purchase_policy(artifact)
    except CaseDevPurchasePolicyError as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"issued repair purchase policy is invalid: {exc}"
        ) from exc


def _snapshot_path(root: Path, candidate_id: str) -> Path:
    if (
        not candidate_id
        or candidate_id in {".", ".."}
        or "/" in candidate_id
        or "\\" in candidate_id
    ):
        raise DocumentRepairPurchaseApprovalError(
            "docket snapshot candidate_id is unsafe"
        )
    path = root / f"{candidate_id}.json"
    if path.parent != root:
        raise DocumentRepairPurchaseApprovalError(
            "docket snapshot escapes its verified root"
        )
    return path


def _require_fresh_ledger(path: Path) -> None:
    try:
        require_fresh_purchase_ledger_namespace(path)
    except PurchaseApprovalError as exc:
        raise DocumentRepairPurchaseApprovalError(str(exc)) from exc


def _read(path: Path, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"{label} is unreadable: {exc}"
        ) from exc


def _normalized(path: Path, label: str) -> Path:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise DocumentRepairPurchaseApprovalError(
            f"{label} must be an absolute normalized path"
        )
    return path


def _json_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentRepairPurchaseApprovalError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise DocumentRepairPurchaseApprovalError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DocumentRepairPurchaseApprovalError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str] | set[str], label: str
) -> None:
    if set(value) != set(expected):
        missing = sorted(set(expected) - set(value))
        unexpected = sorted(set(value) - set(expected))
        raise DocumentRepairPurchaseApprovalError(
            f"{label} keys mismatch; missing={missing}, unexpected={unexpected}"
        )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentRepairPurchaseApprovalError(f"{label} must be a nonempty string")
    return value


def _digest(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise DocumentRepairPurchaseApprovalError(
            f"{label} must be a lowercase SHA-256"
        )
    return text


def _usd(value: object, label: str) -> Decimal:
    try:
        amount = Decimal(_text(value, label))
    except InvalidOperation as exc:
        raise DocumentRepairPurchaseApprovalError(
            f"{label} must be decimal money"
        ) from exc
    if (
        not amount.is_finite()
        or amount <= 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise DocumentRepairPurchaseApprovalError(
            f"{label} must be positive money with at most two decimals"
        )
    return amount


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _value_sha256(value: object) -> str:
    return hashlib.sha256(ARTIFACT_JSON_VALUE_V1.encode(value)).hexdigest()

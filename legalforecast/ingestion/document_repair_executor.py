"""Authenticated identity and execution bridge for exact-100 document repairs.

This module remains provider-neutral: it resolves authenticated CourtListener
snapshots into the existing free-download and paid-budget types, then records
the outcomes returned by those established executors. It never performs a
network request or submits a purchase itself.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_JSON_VALUE_V1,
    ARTIFACT_RAW_SHA256_V1,
    EXACT100_DOCUMENT_REPAIR_EXECUTION_V1,
    EXACT100_DOCUMENT_REPAIR_PILOT_V2,
    EXACT100_DOCUMENT_REPAIR_PURCHASE_AUTHORITY_V1,
    EXACT100_DOCUMENT_REPAIR_RECEIPT_V1,
    EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
)
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    require_approved_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.document_repair_pilot import DocumentRepairPilot
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentAcquisitionItem,
    MissingDocumentAcquisitionPlan,
    SealedMissingDocumentSuccessor,
    seal_missing_document_successor,
)
from legalforecast.ingestion.recap_api_discovery import public_recap_download_url
from legalforecast.ingestion.restricted_material import restricted_material_markers

SCHEMA_VERSION = str(EXACT100_DOCUMENT_REPAIR_EXECUTION_V1)
RECEIPT_SCHEMA_VERSION = str(EXACT100_DOCUMENT_REPAIR_RECEIPT_V1)
_SHA256 = re.compile(r"[0-9a-f]{64}")


class DocumentRepairExecutorError(ValueError):
    """Raised when repair execution is not exactly authorized and replayable."""


_SNAPSHOT_AUTHORITY = object()
_EXECUTION_AUTHORITY = object()
_PURCHASE_AUTHORITY = object()


@dataclass(frozen=True, slots=True, init=False)
class DocketSnapshotAuthority:
    """Replay-minted docket-byte commitments from one pinned lineage manifest."""

    source_lineage_sha256: str
    cohort_policy_sha256: str
    manifest_sha256: str
    candidate_sha256: Mapping[str, str]
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise DocumentRepairExecutorError(
            "docket snapshot authority can be created only by manifest replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _SNAPSHOT_AUTHORITY


@dataclass(frozen=True, slots=True)
class ResolvedRepairOperation:
    """One manifest obligation resolved to one exact RECAP document."""

    candidate_id: str
    docket_entry_number: int
    document_selector: str
    document_role: str
    route: str
    recap_document_id: str
    docket_entry_id: str
    source_url: str | None
    projected_cost_usd: Decimal
    docket_snapshot_sha256: str

    @property
    def key(self) -> tuple[str, int, str]:
        return self.candidate_id, self.docket_entry_number, self.document_selector

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "docket_entry_number": self.docket_entry_number,
            "document_selector": self.document_selector,
            "document_role": self.document_role,
            "route": self.route,
            "recap_document_id": self.recap_document_id,
            "docket_entry_id": self.docket_entry_id,
            "source_url": self.source_url,
            "projected_cost_usd": _money(self.projected_cost_usd),
            "docket_snapshot_sha256": self.docket_snapshot_sha256,
        }


@dataclass(frozen=True, slots=True, init=False)
class DocumentRepairExecution:
    """Exact provider inputs derived from an approved plan and pilot scope."""

    full_plan_sha256: str
    manifest_sha256: str
    source_lineage_sha256: str
    cohort_policy_sha256: str
    scope: str
    scope_sha256: str
    pilot_sha256: str | None
    operations: tuple[ResolvedRepairOperation, ...]
    purchase_budget: MissingCoreBudgetPlan
    execution_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise DocumentRepairExecutorError(
            "document repair execution can be created only by authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _EXECUTION_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "full_plan_sha256": self.full_plan_sha256,
            "manifest_sha256": self.manifest_sha256,
            "source_lineage_sha256": self.source_lineage_sha256,
            "cohort_policy_sha256": self.cohort_policy_sha256,
            "scope": self.scope,
            "scope_sha256": self.scope_sha256,
            "pilot_sha256": self.pilot_sha256,
            "operations": [operation.to_record() for operation in self.operations],
            "purchase_budget": self.purchase_budget.to_record(),
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "execution_sha256": self.execution_sha256}


@dataclass(frozen=True, slots=True)
class RepairOperationOutcome:
    """Measured terminal result from one established acquisition executor."""

    candidate_id: str
    docket_entry_number: int
    disposition: str
    retry_count: int
    duration_seconds: str
    committed_cost_usd: str
    document_selector: str = "main_document"


@dataclass(frozen=True, slots=True)
class DocumentRepairReceipt:
    """Immutable ordered outcome ledger for one repair execution."""

    execution_sha256: str
    full_plan_sha256: str
    scope: str
    scope_sha256: str
    pilot_sha256: str | None
    operation_ledger: tuple[Mapping[str, object], ...]
    receipt_sha256: str

    @property
    def committed_cost_usd(self) -> str:
        total = sum(
            (Decimal(str(row["committed_cost_usd"])) for row in self.operation_ledger),
            Decimal("0.00"),
        )
        return _money(total)

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "execution_sha256": self.execution_sha256,
            "full_plan_sha256": self.full_plan_sha256,
            "scope": self.scope,
            "scope_sha256": self.scope_sha256,
            "pilot_sha256": self.pilot_sha256,
            "committed_cost_usd": self.committed_cost_usd,
            "operation_ledger": [dict(row) for row in self.operation_ledger],
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class AcquiredRepairDocument:
    """One dependency-injected acquisition result before successor sealing."""

    disposition: str
    source_document_id: str
    document_bytes: bytes | None
    committed_cost_usd: str
    retry_count: int
    reason: str | None = None
    document_selector: str = "main_document"


@dataclass(frozen=True, slots=True)
class DocumentRepairRunResult:
    """Measured acquisition result ready for semantic successor validation."""

    receipt: DocumentRepairReceipt
    acquired_documents: tuple[Mapping[str, object], ...]
    exclusions: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True, init=False)
class DocumentRepairPurchaseAuthority:
    """Execution-bound approved-v2 policy for one fresh repair ledger."""

    execution_sha256: str
    scope: str
    scope_sha256: str
    purchase_policy: CaseDevPurchasePolicy
    authority_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise DocumentRepairExecutorError(
            "purchase authority can be created only by authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _PURCHASE_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": str(EXACT100_DOCUMENT_REPAIR_PURCHASE_AUTHORITY_V1),
            "execution_sha256": self.execution_sha256,
            "scope": self.scope,
            "scope_sha256": self.scope_sha256,
            "purchase_policy": dict(self.purchase_policy.artifact),
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "authority_sha256": self.authority_sha256}


def build_document_repair_execution(
    *,
    full_plan: MissingDocumentAcquisitionPlan,
    pilot: DocumentRepairPilot,
    docket_snapshot_bytes: Mapping[str, bytes],
    docket_snapshot_sha256: Mapping[str, str],
    snapshot_authority: DocketSnapshotAuthority,
) -> DocumentRepairExecution:
    """Resolve the exact pilot obligations from authenticated docket snapshots."""

    _require_scope_binding(full_plan, pilot)
    _require_snapshot_authority(snapshot_authority, docket_snapshot_sha256)
    expected_candidates = set(pilot.candidate_ids)
    if (
        set(docket_snapshot_bytes) != expected_candidates
        or set(docket_snapshot_sha256) != expected_candidates
    ):
        raise DocumentRepairExecutorError(
            "docket snapshots must exactly cover the pilot candidates"
        )
    snapshots: dict[str, Mapping[str, object]] = {}
    verified_digests: dict[str, str] = {}
    for candidate_id in pilot.candidate_ids:
        payload = docket_snapshot_bytes[candidate_id]
        expected_digest = _digest(
            docket_snapshot_sha256[candidate_id], "docket snapshot digest"
        )
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise DocumentRepairExecutorError(
                f"docket snapshot digest mismatch: {candidate_id}"
            )
        snapshots[candidate_id] = _snapshot(payload, candidate_id)
        verified_digests[candidate_id] = expected_digest

    operations = tuple(
        _resolve_operation(
            item,
            snapshot=snapshots[item.candidate_id],
            snapshot_sha256=verified_digests[item.candidate_id],
        )
        for item in pilot.items
    )
    purchase_budget = _purchase_budget(operations, pilot)
    provisional = _mint_execution(
        full_plan_sha256=full_plan.plan_sha256,
        manifest_sha256=full_plan.manifest_sha256,
        source_lineage_sha256=snapshot_authority.source_lineage_sha256,
        cohort_policy_sha256=snapshot_authority.cohort_policy_sha256,
        scope="pilot",
        scope_sha256=pilot.pilot_sha256,
        pilot_sha256=pilot.pilot_sha256,
        operations=operations,
        purchase_budget=purchase_budget,
        execution_sha256="",
    )
    return _mint_execution(
        full_plan_sha256=provisional.full_plan_sha256,
        manifest_sha256=provisional.manifest_sha256,
        source_lineage_sha256=provisional.source_lineage_sha256,
        cohort_policy_sha256=provisional.cohort_policy_sha256,
        scope=provisional.scope,
        scope_sha256=provisional.scope_sha256,
        pilot_sha256=provisional.pilot_sha256,
        operations=provisional.operations,
        purchase_budget=provisional.purchase_budget,
        execution_sha256=_commit_execution(provisional.content_record()),
    )


def build_full_document_repair_execution(
    *,
    full_plan: MissingDocumentAcquisitionPlan,
    docket_snapshot_bytes: Mapping[str, bytes],
    docket_snapshot_sha256: Mapping[str, str],
    snapshot_authority: DocketSnapshotAuthority,
) -> DocumentRepairExecution:
    """Resolve every approved full-plan obligation without a pilot sub-scope."""

    _require_valid_full_plan(full_plan)
    _require_snapshot_authority(snapshot_authority, docket_snapshot_sha256)
    candidate_ids = tuple(dict.fromkeys(item.candidate_id for item in full_plan.items))
    expected_candidates = set(candidate_ids)
    if (
        set(docket_snapshot_bytes) != expected_candidates
        or set(docket_snapshot_sha256) != expected_candidates
    ):
        raise DocumentRepairExecutorError(
            "docket snapshots must exactly cover the full-plan candidates"
        )
    snapshots: dict[str, Mapping[str, object]] = {}
    verified_digests: dict[str, str] = {}
    for candidate_id in candidate_ids:
        payload = docket_snapshot_bytes[candidate_id]
        expected_digest = _digest(
            docket_snapshot_sha256[candidate_id], "docket snapshot digest"
        )
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise DocumentRepairExecutorError(
                f"docket snapshot digest mismatch: {candidate_id}"
            )
        snapshots[candidate_id] = _snapshot(payload, candidate_id)
        verified_digests[candidate_id] = expected_digest
    operations = tuple(
        _resolve_operation(
            item,
            snapshot=snapshots[item.candidate_id],
            snapshot_sha256=verified_digests[item.candidate_id],
        )
        for item in full_plan.items
    )
    purchase_budget = _purchase_budget_for_scope(
        operations,
        candidate_ids=candidate_ids,
        maximum=full_plan.approved_maximum_usd,
    )
    provisional = _mint_execution(
        full_plan_sha256=full_plan.plan_sha256,
        manifest_sha256=full_plan.manifest_sha256,
        source_lineage_sha256=snapshot_authority.source_lineage_sha256,
        cohort_policy_sha256=snapshot_authority.cohort_policy_sha256,
        scope="full_plan",
        scope_sha256=full_plan.plan_sha256,
        pilot_sha256=None,
        operations=operations,
        purchase_budget=purchase_budget,
        execution_sha256="",
    )
    return _mint_execution(
        full_plan_sha256=provisional.full_plan_sha256,
        manifest_sha256=provisional.manifest_sha256,
        source_lineage_sha256=provisional.source_lineage_sha256,
        cohort_policy_sha256=provisional.cohort_policy_sha256,
        scope=provisional.scope,
        scope_sha256=provisional.scope_sha256,
        pilot_sha256=None,
        operations=provisional.operations,
        purchase_budget=provisional.purchase_budget,
        execution_sha256=_commit_execution(provisional.content_record()),
    )


def replay_docket_snapshot_authority(
    *,
    manifest_bytes: bytes,
    source_lineage_bytes: bytes,
    expected_source_lineage_sha256: str,
) -> DocketSnapshotAuthority:
    """Mint exact candidate-byte commitments from an externally pinned manifest."""

    lineage_digest = _digest(expected_source_lineage_sha256, "source lineage digest")
    if hashlib.sha256(source_lineage_bytes).hexdigest() != lineage_digest:
        raise DocumentRepairExecutorError("source lineage differs from its pin")
    try:
        lineage_value = json.loads(source_lineage_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentRepairExecutorError("source lineage is invalid JSON") from exc
    if not isinstance(lineage_value, Mapping):
        raise DocumentRepairExecutorError("source lineage must be an object")
    lineage = cast(Mapping[str, object], lineage_value)
    raw_manifest_digest = lineage.get("docket_snapshot_manifest_sha256")
    if not isinstance(raw_manifest_digest, str):
        raise DocumentRepairExecutorError("source lineage omits snapshot manifest pin")
    manifest_digest = _digest(raw_manifest_digest, "snapshot manifest digest")
    raw_cohort_policy_digest = lineage.get("cohort_policy_sha256")
    if not isinstance(raw_cohort_policy_digest, str):
        raise DocumentRepairExecutorError("source lineage omits cohort policy pin")
    cohort_policy_digest = _digest(raw_cohort_policy_digest, "cohort policy digest")
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_digest:
        raise DocumentRepairExecutorError("snapshot manifest differs from lineage pin")
    try:
        value = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentRepairExecutorError("snapshot manifest is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise DocumentRepairExecutorError("snapshot manifest must be an object")
    manifest = cast(Mapping[str, object], value)
    raw_candidates = manifest.get("candidate_sha256")
    if not isinstance(raw_candidates, Mapping):
        raise DocumentRepairExecutorError(
            "snapshot manifest candidate commitments are missing"
        )
    candidate_sha256: dict[str, str] = {}
    for candidate_id, digest in cast(Mapping[object, object], raw_candidates).items():
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise DocumentRepairExecutorError("snapshot manifest candidate is invalid")
        if not isinstance(digest, str):
            raise DocumentRepairExecutorError("snapshot manifest digest is invalid")
        candidate_sha256[candidate_id] = _digest(digest, "snapshot candidate digest")
    authority = object.__new__(DocketSnapshotAuthority)
    for name, field_value in (
        ("source_lineage_sha256", lineage_digest),
        ("cohort_policy_sha256", cohort_policy_digest),
        ("manifest_sha256", manifest_digest),
        ("candidate_sha256", MappingProxyType(candidate_sha256)),
        ("_mint", _SNAPSHOT_AUTHORITY),
    ):
        object.__setattr__(authority, name, field_value)
    return authority


def record_document_repair_outcomes(
    *,
    execution: DocumentRepairExecution,
    outcomes: tuple[RepairOperationOutcome, ...],
) -> DocumentRepairReceipt:
    """Record an exact ordered result prefix, stopping permanently on unknown."""

    _require_replay_minted_execution(execution)
    if len(outcomes) > len(execution.operations):
        raise DocumentRepairExecutorError("outcomes exceed planned operations")
    ledger: list[Mapping[str, object]] = []
    unknown_index: int | None = None
    for index, outcome in enumerate(outcomes):
        operation = execution.operations[index]
        if (
            outcome.candidate_id,
            outcome.docket_entry_number,
            outcome.document_selector,
        ) != operation.key:
            raise DocumentRepairExecutorError("outcome operation order is invalid")
        if unknown_index is not None:
            raise DocumentRepairExecutorError(
                "an unknown paid outcome is already terminal for this execution"
            )
        ledger.append(_outcome_record(operation, outcome))
        if outcome.disposition == "unknown":
            unknown_index = index
    if unknown_index is None and len(outcomes) != len(execution.operations):
        raise DocumentRepairExecutorError(
            "complete outcomes are required unless an unknown paid outcome stops work"
        )
    if unknown_index is not None:
        for operation in execution.operations[unknown_index + 1 :]:
            ledger.append(
                {
                    **operation.to_record(),
                    "disposition": "not_attempted_after_unknown",
                    "retry_count": 0,
                    "duration_seconds": "0.000000",
                    "committed_cost_usd": "0.00",
                    "retry_permitted": False,
                }
            )
    provisional = DocumentRepairReceipt(
        execution_sha256=execution.execution_sha256,
        full_plan_sha256=execution.full_plan_sha256,
        scope=execution.scope,
        scope_sha256=execution.scope_sha256,
        pilot_sha256=execution.pilot_sha256,
        operation_ledger=tuple(ledger),
        receipt_sha256="",
    )
    if (
        Decimal(provisional.committed_cost_usd)
        > execution.purchase_budget.max_projected_budget
    ):
        raise DocumentRepairExecutorError(
            "committed cost exceeds approved pilot maximum"
        )
    return DocumentRepairReceipt(
        execution_sha256=provisional.execution_sha256,
        full_plan_sha256=provisional.full_plan_sha256,
        scope=provisional.scope,
        scope_sha256=provisional.scope_sha256,
        pilot_sha256=provisional.pilot_sha256,
        operation_ledger=provisional.operation_ledger,
        receipt_sha256=_commit_receipt(provisional.content_record()),
    )


def run_document_repair_execution(
    *,
    execution: DocumentRepairExecution,
    purchase_authority: DocumentRepairPurchaseAuthority | None,
    acquire: Callable[[ResolvedRepairOperation], AcquiredRepairDocument],
    monotonic: Callable[[], float],
) -> DocumentRepairRunResult:
    """Run exact operations in free-first order with measured terminal stopping."""

    _require_replay_minted_execution(execution)
    _require_purchase_authority(execution, purchase_authority)
    outcomes: list[RepairOperationOutcome] = []
    acquired_documents: list[Mapping[str, object]] = []
    exclusions: list[Mapping[str, object]] = []
    for operation in execution.operations:
        started = monotonic()
        result = acquire(operation)
        finished = monotonic()
        duration = Decimal(str(finished)) - Decimal(str(started))
        if duration < 0:
            raise DocumentRepairExecutorError("monotonic clock moved backwards")
        _validate_acquired_result(operation, result)
        outcome = RepairOperationOutcome(
            candidate_id=operation.candidate_id,
            docket_entry_number=operation.docket_entry_number,
            disposition=result.disposition,
            retry_count=result.retry_count,
            duration_seconds=str(duration),
            committed_cost_usd=result.committed_cost_usd,
            document_selector=operation.document_selector,
        )
        # Validate cost, retry, duration, and terminal semantics before any
        # later provider callback can run.
        _outcome_record(operation, outcome)
        outcomes.append(outcome)
        if result.disposition == "included":
            assert result.document_bytes is not None
            acquired_documents.append(
                {
                    "candidate_id": operation.candidate_id,
                    "docket_entry_number": operation.docket_entry_number,
                    "document_selector": operation.document_selector,
                    "document_role": operation.document_role,
                    "source_document_id": operation.recap_document_id,
                    "source": operation.route,
                    "sha256": hashlib.sha256(result.document_bytes).hexdigest(),
                    "byte_count": len(result.document_bytes),
                    "document_bytes": result.document_bytes,
                }
            )
        elif result.disposition in {"excluded", "provider_error"}:
            exclusions.append(
                {
                    "candidate_id": operation.candidate_id,
                    "docket_entry_number": operation.docket_entry_number,
                    "document_selector": operation.document_selector,
                    "document_role": operation.document_role,
                    "reason": cast(str, result.reason),
                }
            )
        elif result.disposition == "unknown":
            break
    return DocumentRepairRunResult(
        receipt=record_document_repair_outcomes(
            execution=execution, outcomes=tuple(outcomes)
        ),
        acquired_documents=tuple(acquired_documents),
        exclusions=tuple(exclusions),
    )


def build_document_repair_purchase_authority(
    *,
    execution: DocumentRepairExecution,
    approved_purchase_policy_artifact: Mapping[str, object],
) -> DocumentRepairPurchaseAuthority:
    """Bind independently approved v2 purchase authority to one execution."""

    _require_replay_minted_execution(execution)
    budget = execution.purchase_budget
    if not budget.case_plans:
        raise DocumentRepairExecutorError(
            "purchase authority requires at least one paid operation"
        )
    policy = verify_purchase_policy_compatibility(
        execution=execution,
        purchase_policy_artifact=approved_purchase_policy_artifact,
    )
    provisional = _mint_purchase_authority(
        execution_sha256=execution.execution_sha256,
        scope=execution.scope,
        scope_sha256=execution.scope_sha256,
        purchase_policy=policy,
        authority_sha256="",
    )
    return _mint_purchase_authority(
        execution_sha256=provisional.execution_sha256,
        scope=provisional.scope,
        scope_sha256=provisional.scope_sha256,
        purchase_policy=provisional.purchase_policy,
        authority_sha256=_commit_purchase_authority(provisional.content_record()),
    )


def verify_purchase_policy_compatibility(
    *,
    execution: DocumentRepairExecution,
    purchase_policy_artifact: Mapping[str, object],
) -> CaseDevPurchasePolicy:
    """Require an existing typed purchase policy to fit this exact execution."""

    _require_replay_minted_execution(execution)
    try:
        policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        require_approved_case_dev_purchase_policy(policy)
    except CaseDevPurchasePolicyError as exc:
        raise DocumentRepairExecutorError(f"purchase policy is invalid: {exc}") from exc
    budget = execution.purchase_budget
    if policy.per_document_reservation_usd != budget.cost_per_document:
        raise DocumentRepairExecutorError(
            "purchase-policy per-document reservation differs from repair approval"
        )
    if policy.cohort_policy_sha256 != execution.cohort_policy_sha256:
        raise DocumentRepairExecutorError(
            "purchase-policy cohort lineage differs from repair execution"
        )
    if policy.canonical_ledger_path.exists():
        raise DocumentRepairExecutorError(
            "purchase authority requires a fresh canonical ledger"
        )
    approval = policy.approval
    assert approval is not None
    paid_operations = tuple(
        operation
        for operation in execution.operations
        if operation.route == "pacer_purchase"
    )
    candidate_ids = tuple(plan.candidate_id for plan in budget.case_plans)
    document_ids = tuple(operation.recap_document_id for operation in paid_operations)
    if (
        approval.get("selected_candidate_ids_sha256")
        != hashlib.sha256(
            ARTIFACT_JSON_VALUE_V1.encode(list(candidate_ids))
        ).hexdigest()
        or approval.get("purchase_document_ids_sha256")
        != hashlib.sha256(ARTIFACT_JSON_VALUE_V1.encode(list(document_ids))).hexdigest()
        or approval.get("selected_case_count") != len(candidate_ids)
        or approval.get("purchase_document_count") != len(document_ids)
        or approval.get("projected_cost_usd") != _money(budget.total_estimated_cost)
    ):
        raise DocumentRepairExecutorError(
            "purchase-policy approval differs from the repair execution"
        )
    global_headroom = policy.hard_cap_usd - policy.opening_committed_spend_usd
    if global_headroom < budget.total_estimated_cost:
        raise DocumentRepairExecutorError(
            "purchase-policy global headroom is below the repair budget"
        )
    for case_plan in budget.case_plans:
        opening = policy.opening_case_committed_spend_usd.get(
            case_plan.candidate_id, Decimal("0.00")
        )
        if policy.max_per_case_usd - opening < case_plan.estimated_cost:
            raise DocumentRepairExecutorError(
                "purchase-policy per-case headroom is below the repair budget: "
                f"{case_plan.candidate_id}"
            )
    return policy


def seal_document_repair_execution(
    *,
    full_plan: MissingDocumentAcquisitionPlan,
    execution: DocumentRepairExecution,
    receipt: DocumentRepairReceipt,
    acquired_documents: Sequence[Mapping[str, object]],
    exclusions: Sequence[Mapping[str, object]],
    role_bytes_match: Callable[[str, bytes], bool],
) -> SealedMissingDocumentSuccessor:
    """Seal only a complete resolved execution with exact RECAP identities."""

    _require_scope_binding_from_execution(full_plan, execution)
    if execution.scope != "full_plan":
        raise DocumentRepairExecutorError(
            "only a complete full-plan execution may seal the exact-100 successor"
        )
    if _commit_receipt(receipt.content_record()) != receipt.receipt_sha256:
        raise DocumentRepairExecutorError("repair receipt changed after execution")
    if (
        receipt.execution_sha256 != execution.execution_sha256
        or receipt.full_plan_sha256 != full_plan.plan_sha256
        or receipt.scope != execution.scope
        or receipt.scope_sha256 != execution.scope_sha256
        or receipt.pilot_sha256 != execution.pilot_sha256
    ):
        raise DocumentRepairExecutorError("repair receipt binding is invalid")
    if len(receipt.operation_ledger) != len(execution.operations):
        raise DocumentRepairExecutorError("repair receipt ledger is incomplete")
    dispositions = [str(row.get("disposition")) for row in receipt.operation_ledger]
    if any(disposition not in {"included", "excluded"} for disposition in dispositions):
        raise DocumentRepairExecutorError(
            "repair execution has nonterminal outcomes and cannot seal"
        )
    operation_by_key = {operation.key: operation for operation in execution.operations}
    if len(operation_by_key) != len(execution.operations):
        raise DocumentRepairExecutorError("repair execution repeats an operation")
    evidence_dispositions: dict[tuple[str, int, str], str] = {}
    for document in acquired_documents:
        key = _evidence_key(document)
        operation = operation_by_key.get(key)
        if operation is None:
            raise DocumentRepairExecutorError("acquired document is outside execution")
        if document.get("source_document_id") != operation.recap_document_id:
            raise DocumentRepairExecutorError(
                "acquired document differs from resolved RECAP identity"
            )
        evidence_dispositions[key] = "included"
    for exclusion in exclusions:
        key = _evidence_key(exclusion)
        if key not in operation_by_key:
            raise DocumentRepairExecutorError("exclusion is outside execution")
        if key in evidence_dispositions:
            raise DocumentRepairExecutorError("duplicate sealing disposition")
        evidence_dispositions[key] = "excluded"
    for operation, row in zip(
        execution.operations, receipt.operation_ledger, strict=True
    ):
        operation_record = operation.to_record()
        if any(row.get(field) != value for field, value in operation_record.items()):
            raise DocumentRepairExecutorError(
                "repair receipt operation differs from execution"
            )
        retry_count = row.get("retry_count")
        if not isinstance(retry_count, int) or isinstance(retry_count, bool):
            raise DocumentRepairExecutorError("repair receipt retry count is invalid")
        canonical_outcome = _outcome_record(
            operation,
            RepairOperationOutcome(
                candidate_id=operation.candidate_id,
                docket_entry_number=operation.docket_entry_number,
                disposition=str(row.get("disposition")),
                retry_count=retry_count,
                duration_seconds=str(row.get("duration_seconds")),
                committed_cost_usd=str(row.get("committed_cost_usd")),
                document_selector=operation.document_selector,
            ),
        )
        if row.get("retry_permitted") != canonical_outcome["retry_permitted"]:
            raise DocumentRepairExecutorError(
                "repair receipt retry permission differs from outcome"
            )
        expected = "included" if row.get("disposition") == "included" else "excluded"
        if evidence_dispositions.get(operation.key) != expected:
            raise DocumentRepairExecutorError(
                "sealing evidence contradicts repair receipt disposition"
            )
    try:
        return seal_missing_document_successor(
            plan=full_plan,
            acquired_documents=acquired_documents,
            exclusions=exclusions,
            role_bytes_match=role_bytes_match,
        )
    except ValueError as exc:
        raise DocumentRepairExecutorError(str(exc)) from exc


def _require_scope_binding(
    full_plan: MissingDocumentAcquisitionPlan, pilot: DocumentRepairPilot
) -> None:
    _require_valid_full_plan(full_plan)
    verified_pilot_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            pilot.content_record(), domain=EXACT100_DOCUMENT_REPAIR_PILOT_V2
        ).digest
    )
    if verified_pilot_sha256 != pilot.pilot_sha256:
        raise DocumentRepairExecutorError("pilot changed after projection")
    if pilot.full_plan_sha256 != full_plan.plan_sha256:
        raise DocumentRepairExecutorError("pilot is not bound to the full plan")
    if pilot.manifest_sha256 != full_plan.manifest_sha256:
        raise DocumentRepairExecutorError("pilot manifest binding is invalid")
    selected = set(pilot.candidate_ids)
    expected_items = tuple(
        item for item in full_plan.items if item.candidate_id in selected
    )
    if pilot.items != expected_items:
        raise DocumentRepairExecutorError(
            "pilot items differ from the exact full-plan projection"
        )


def _require_valid_full_plan(full_plan: MissingDocumentAcquisitionPlan) -> None:
    verified = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            full_plan.content_record(),
            domain=EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
        ).digest
    )
    if verified != full_plan.plan_sha256:
        raise DocumentRepairExecutorError("full plan changed after approval")
    if full_plan.max_per_document_usd != Decimal("3.00") or any(
        item.projected_cost_usd not in {Decimal("0.00"), Decimal("3.00")}
        for item in full_plan.items
    ):
        raise DocumentRepairExecutorError(
            "repair execution requires the approved $3.00 per-document price"
        )


def _require_snapshot_authority(
    authority: DocketSnapshotAuthority,
    supplied_digests: Mapping[str, str],
) -> None:
    if (
        type(authority) is not DocketSnapshotAuthority
        or not authority.is_replay_minted()
    ):
        raise DocumentRepairExecutorError("docket snapshots lack replayed authority")
    normalized = {
        candidate_id: _digest(digest, "docket snapshot digest")
        for candidate_id, digest in supplied_digests.items()
    }
    if any(
        authority.candidate_sha256.get(candidate_id) != digest
        for candidate_id, digest in normalized.items()
    ):
        raise DocumentRepairExecutorError(
            "docket snapshot digests differ from committed authority"
        )


def _require_scope_binding_from_execution(
    full_plan: MissingDocumentAcquisitionPlan, execution: DocumentRepairExecution
) -> None:
    _require_replay_minted_execution(execution)
    verified_full_plan_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            full_plan.content_record(),
            domain=EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
        ).digest
    )
    if verified_full_plan_sha256 != full_plan.plan_sha256:
        raise DocumentRepairExecutorError("full plan changed after approval")
    if execution.full_plan_sha256 != full_plan.plan_sha256:
        raise DocumentRepairExecutorError("execution is not bound to the full plan")
    if execution.scope == "pilot":
        if execution.scope_sha256 != execution.pilot_sha256:
            raise DocumentRepairExecutorError("execution pilot scope is invalid")
    elif execution.scope == "full_plan":
        if (
            execution.scope_sha256 != full_plan.plan_sha256
            or execution.pilot_sha256 is not None
        ):
            raise DocumentRepairExecutorError("execution full-plan scope is invalid")
    else:
        raise DocumentRepairExecutorError("execution scope is invalid")
    if _commit_execution(execution.content_record()) != execution.execution_sha256:
        raise DocumentRepairExecutorError("execution changed after resolution")
    planned = {item.key: item.to_record() for item in full_plan.items}
    for operation in execution.operations:
        plan_record = planned.get(operation.key)
        if plan_record is None:
            raise DocumentRepairExecutorError(
                "execution operation is outside full plan"
            )
        if (
            plan_record["document_role"] != operation.document_role
            or plan_record["acquisition_method"] != operation.route
            or plan_record["projected_cost_usd"] != _money(operation.projected_cost_usd)
        ):
            raise DocumentRepairExecutorError("execution operation alters full plan")


def _evidence_key(record: Mapping[str, object]) -> tuple[str, int, str]:
    candidate_id = record.get("candidate_id")
    entry = record.get("docket_entry_number")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise DocumentRepairExecutorError("document candidate identity is invalid")
    resolved_entry = _positive_int(entry)
    if resolved_entry is None:
        raise DocumentRepairExecutorError("document docket entry is invalid")
    selector = record.get("document_selector", "main_document")
    if not isinstance(selector, str):
        raise DocumentRepairExecutorError("document selector is invalid")
    return candidate_id, resolved_entry, selector


def _snapshot(payload: bytes, candidate_id: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentRepairExecutorError("docket snapshot is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise DocumentRepairExecutorError("docket snapshot must be an object")
    record = cast(Mapping[str, object], value)
    if record.get("candidate_id") != candidate_id:
        raise DocumentRepairExecutorError(
            "docket snapshot candidate binding is invalid"
        )
    if not isinstance(record.get("docket_id"), int) or isinstance(
        record.get("docket_id"), bool
    ):
        raise DocumentRepairExecutorError("docket snapshot docket identity is invalid")
    expected_docket_id = _candidate_docket_id(candidate_id)
    if (
        expected_docket_id is not None
        and str(record["docket_id"]) != expected_docket_id
    ):
        raise DocumentRepairExecutorError(
            "docket snapshot docket identity differs from candidate"
        )
    return record


def _resolve_operation(
    item: MissingDocumentAcquisitionItem,
    *,
    snapshot: Mapping[str, object],
    snapshot_sha256: str,
) -> ResolvedRepairOperation:
    entries = _mapping_list(snapshot.get("entries"), "docket snapshot entries")
    matches = [
        entry
        for entry in entries
        if _positive_int(entry.get("entry_number"), allow_invalid=True)
        == item.docket_entry_number
    ]
    if len(matches) != 1:
        raise DocumentRepairExecutorError(
            "docket entry resolution is not exact: "
            f"{item.candidate_id}/{item.docket_entry_number}"
        )
    entry = matches[0]
    if _docket_identifier(entry.get("docket")) != str(snapshot["docket_id"]):
        raise DocumentRepairExecutorError("docket entry belongs to a different docket")
    documents = _mapping_list(entry.get("recap_documents"), "RECAP documents")
    selected_documents = [
        document
        for document in documents
        if _document_selector(document) == item.document_selector
    ]
    if len(selected_documents) != 1:
        raise DocumentRepairExecutorError(
            "ambiguous selected document: "
            f"{item.candidate_id}/{item.docket_entry_number}/{item.document_selector}"
        )
    document = selected_documents[0]
    document_id = _positive_identifier(document.get("id"), "RECAP document id")
    docket_entry_id = _positive_identifier(entry.get("id"), "docket entry id")
    linked_entry_id = document.get("docket_entry_id")
    if linked_entry_id is not None and str(linked_entry_id) != docket_entry_id:
        raise DocumentRepairExecutorError("RECAP document belongs to another entry")
    free_url = None
    filepath = document.get("filepath_local")
    if (
        document.get("is_available") is True
        and document.get("is_sealed") is False
        and not restricted_material_markers(
            records=(document,),
            text_fields=(str(document.get("description") or ""),),
        )
        and isinstance(filepath, str)
    ):
        free_url = public_recap_download_url(filepath)
    if item.acquisition_method == "courtlistener_free" and free_url is None:
        raise DocumentRepairExecutorError(
            "approved free route is unavailable: "
            f"{item.candidate_id}/{item.docket_entry_number}"
        )
    if item.acquisition_method == "pacer_purchase" and free_url is not None:
        raise DocumentRepairExecutorError(
            "approved paid route has become free and requires a new plan: "
            f"{item.candidate_id}/{item.docket_entry_number}"
        )
    return ResolvedRepairOperation(
        candidate_id=item.candidate_id,
        docket_entry_number=item.docket_entry_number,
        document_selector=item.document_selector,
        document_role=item.document_role,
        route=item.acquisition_method,
        recap_document_id=document_id,
        docket_entry_id=docket_entry_id,
        source_url=free_url,
        projected_cost_usd=item.projected_cost_usd,
        docket_snapshot_sha256=snapshot_sha256,
    )


def _purchase_budget(
    operations: tuple[ResolvedRepairOperation, ...], pilot: DocumentRepairPilot
) -> MissingCoreBudgetPlan:
    return _purchase_budget_for_scope(
        operations,
        candidate_ids=pilot.candidate_ids,
        maximum=pilot.pilot_maximum_usd,
    )


def _purchase_budget_for_scope(
    operations: tuple[ResolvedRepairOperation, ...],
    *,
    candidate_ids: tuple[str, ...],
    maximum: Decimal,
) -> MissingCoreBudgetPlan:
    paid_by_candidate: dict[str, list[ResolvedRepairOperation]] = {}
    for operation in operations:
        if operation.route == "pacer_purchase":
            paid_by_candidate.setdefault(operation.candidate_id, []).append(operation)
    case_plans = tuple(
        CaseMissingCorePurchasePlan(
            candidate_id=candidate_id,
            purchase_document_ids=tuple(
                operation.recap_document_id for operation in candidate_operations
            ),
            missing_core_document_count=len(candidate_operations),
            estimated_cost=Decimal("3.00") * len(candidate_operations),
            audit_only_document_count=0,
            dry_run=False,
            missing_core_roles=tuple(
                operation.document_role for operation in candidate_operations
            ),
        )
        for candidate_id in candidate_ids
        if (candidate_operations := paid_by_candidate.get(candidate_id))
    )
    return MissingCoreBudgetPlan(
        case_plans=case_plans,
        cost_per_document=Decimal("3.00"),
        max_projected_budget=maximum,
        max_missing_core_documents_per_case=max(
            (len(plan.purchase_document_ids) for plan in case_plans), default=1
        ),
        dry_run=False,
        target_case_count=None,
    )


def _outcome_record(
    operation: ResolvedRepairOperation, outcome: RepairOperationOutcome
) -> Mapping[str, object]:
    allowed = {"included", "excluded", "provider_error", "unknown"}
    if outcome.disposition not in allowed:
        raise DocumentRepairExecutorError("unsupported operation disposition")
    if outcome.disposition == "unknown" and operation.route != "pacer_purchase":
        raise DocumentRepairExecutorError("only a paid operation may be unknown")
    if isinstance(outcome.retry_count, bool) or outcome.retry_count < 0:
        raise DocumentRepairExecutorError("retry count is invalid")
    duration = _decimal(outcome.duration_seconds, "duration")
    if duration < 0:
        raise DocumentRepairExecutorError("duration must be nonnegative")
    cost = _money_value(outcome.committed_cost_usd, "committed cost")
    maximum = operation.projected_cost_usd
    if cost > maximum:
        raise DocumentRepairExecutorError("operation cost exceeds approved amount")
    if operation.route == "courtlistener_free" and cost != 0:
        raise DocumentRepairExecutorError("free operation recorded paid cost")
    if outcome.disposition == "unknown" and cost != maximum:
        raise DocumentRepairExecutorError(
            "unknown paid outcome must retain its full approved reservation"
        )
    return {
        **operation.to_record(),
        "disposition": outcome.disposition,
        "retry_count": outcome.retry_count,
        "duration_seconds": f"{duration:.6f}",
        "committed_cost_usd": _money(cost),
        "retry_permitted": outcome.disposition == "provider_error",
    }


def _validate_acquired_result(
    operation: ResolvedRepairOperation, result: AcquiredRepairDocument
) -> None:
    if result.document_selector != operation.document_selector:
        raise DocumentRepairExecutorError(
            "acquisition result differs from resolved document selector"
        )
    if result.source_document_id != operation.recap_document_id:
        raise DocumentRepairExecutorError(
            "acquisition result differs from resolved RECAP identity"
        )
    if result.disposition not in {
        "included",
        "excluded",
        "provider_error",
        "unknown",
    }:
        raise DocumentRepairExecutorError("unsupported acquisition disposition")
    if result.disposition == "included" and result.document_bytes is None:
        raise DocumentRepairExecutorError("included acquisition has no document bytes")
    if result.disposition != "included" and result.document_bytes is not None:
        raise DocumentRepairExecutorError(
            "non-included acquisition unexpectedly returned bytes"
        )
    if result.disposition in {"excluded", "provider_error", "unknown"} and (
        result.reason is None or not result.reason.strip()
    ):
        raise DocumentRepairExecutorError(
            "non-included acquisition requires a specific reason"
        )


def _require_purchase_authority(
    execution: DocumentRepairExecution,
    authority: DocumentRepairPurchaseAuthority | None,
) -> None:
    has_paid_operations = any(
        operation.route == "pacer_purchase" for operation in execution.operations
    )
    if not has_paid_operations:
        if authority is not None:
            raise DocumentRepairExecutorError(
                "purchase authority was supplied for a free-only execution"
            )
        return
    if authority is None:
        raise DocumentRepairExecutorError(
            "paid execution requires exact generated purchase authority"
        )
    if (
        type(authority) is not DocumentRepairPurchaseAuthority
        or not authority.is_replay_minted()
        or authority.execution_sha256 != execution.execution_sha256
        or authority.scope != execution.scope
        or authority.scope_sha256 != execution.scope_sha256
        or _commit_purchase_authority(authority.content_record())
        != authority.authority_sha256
    ):
        raise DocumentRepairExecutorError("purchase authority binding is invalid")
    verified = verify_purchase_policy_compatibility(
        execution=execution,
        purchase_policy_artifact=authority.purchase_policy.artifact,
    )
    if verified.policy_sha256 != authority.purchase_policy.policy_sha256:
        raise DocumentRepairExecutorError("purchase authority policy changed")


def _mapping_list(value: object, label: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise DocumentRepairExecutorError(f"{label} must be an object array")
    raw_items = cast(list[object], value)
    if any(not isinstance(item, Mapping) for item in raw_items):
        raise DocumentRepairExecutorError(f"{label} must be an object array")
    return [cast(Mapping[str, object], item) for item in raw_items]


def _positive_int(value: object, *, allow_invalid: bool = False) -> int | None:
    if isinstance(value, bool):
        return None if allow_invalid else _raise("positive integer is required")
    try:
        result = int(str(value))
    except ValueError:
        return None if allow_invalid else _raise("positive integer is required")
    if result <= 0:
        return None if allow_invalid else _raise("positive integer is required")
    return result


def _positive_identifier(value: object, label: str) -> str:
    result = _positive_int(value)
    if result is None:
        raise DocumentRepairExecutorError(f"{label} is invalid")
    return str(result)


def _docket_identifier(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    stripped = value.rstrip("/")
    candidate = stripped.rsplit("/", 1)[-1]
    resolved = _positive_int(candidate, allow_invalid=True)
    return str(resolved) if resolved is not None else None


def _document_selector(document: Mapping[str, object]) -> str | None:
    attachment = document.get("attachment_number")
    if attachment in {None, "", 0, "0"}:
        return "main_document"
    resolved = _positive_int(attachment, allow_invalid=True)
    return f"attachment_{resolved}" if resolved is not None else None


def _candidate_docket_id(candidate_id: str) -> str | None:
    if candidate_id.isdigit():
        return candidate_id
    prefix = "courtlistener-docket-"
    suffix = candidate_id.removeprefix(prefix)
    if suffix != candidate_id and suffix.isdigit() and int(suffix) > 0:
        return suffix
    return None


def _raise(message: str) -> None:
    raise DocumentRepairExecutorError(message)


def _digest(value: str, label: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise DocumentRepairExecutorError(f"{label} is invalid")
    return value


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DocumentRepairExecutorError(f"{label} is invalid") from exc
    if not result.is_finite():
        raise DocumentRepairExecutorError(f"{label} is invalid")
    return result


def _money_value(value: object, label: str) -> Decimal:
    result = _decimal(value, label)
    if result < 0 or result != result.quantize(Decimal("0.01")):
        raise DocumentRepairExecutorError(f"{label} is invalid")
    return result


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _commit_execution(record: Mapping[str, object]) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            record, domain=EXACT100_DOCUMENT_REPAIR_EXECUTION_V1
        ).digest
    )


def _require_replay_minted_execution(execution: DocumentRepairExecution) -> None:
    if (
        type(execution) is not DocumentRepairExecution
        or not execution.is_replay_minted()
    ):
        raise DocumentRepairExecutorError("execution lacks replay-minted authority")
    if _commit_execution(execution.content_record()) != execution.execution_sha256:
        raise DocumentRepairExecutorError("execution changed after resolution")


def _mint_execution(**fields: object) -> DocumentRepairExecution:
    execution = object.__new__(DocumentRepairExecution)
    for name, value in (*fields.items(), ("_mint", _EXECUTION_AUTHORITY)):
        object.__setattr__(execution, name, value)
    return execution


def _mint_purchase_authority(**fields: object) -> DocumentRepairPurchaseAuthority:
    authority = object.__new__(DocumentRepairPurchaseAuthority)
    for name, value in (*fields.items(), ("_mint", _PURCHASE_AUTHORITY)):
        object.__setattr__(authority, name, value)
    return authority


def _commit_receipt(record: Mapping[str, object]) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            record, domain=EXACT100_DOCUMENT_REPAIR_RECEIPT_V1
        ).digest
    )


def _commit_purchase_authority(record: Mapping[str, object]) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            record, domain=EXACT100_DOCUMENT_REPAIR_PURCHASE_AUTHORITY_V1
        ).digest
    )

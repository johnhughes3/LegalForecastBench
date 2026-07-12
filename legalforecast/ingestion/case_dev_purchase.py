"""Guarded case.dev PACER purchase orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, cast

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevClientError,
    CaseDevPurchaseOutcomeUnknownError,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseDocumentCapExceededError,
    MissingCoreBudgetPlan,
    PurchaseBudgetExceededError,
)


class CaseDevPacerCapability(StrEnum):
    """Known case.dev PACER recovery behavior for selected packet documents."""

    DOCUMENT_LEVEL_PURCHASE = "document_level_purchase"
    DOCKET_LEVEL_LIVE_FETCH_ONLY = "docket_level_live_fetch_only"
    UNKNOWN = "unknown"


class CaseDevPacerPurchaseStatus(StrEnum):
    """Machine-readable status for one intended paid document recovery."""

    PLANNED_DRY_RUN = "planned_dry_run"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    CAPABILITY_BLOCKED = "capability_blocked"
    PURCHASED = "purchased"
    UNKNOWN = "unknown"
    PROVIDER_ERROR = "provider_error"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseAttempt:
    """Recorded intent and outcome for one missing core-document purchase."""

    candidate_id: str
    source_document_id: str
    status: CaseDevPacerPurchaseStatus
    reason: str | None = None
    fee_acknowledged: bool | None = None
    pacer_fees: Mapping[str, str] | None = None
    download_url: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "reason": self.reason,
            "fee_acknowledged": self.fee_acknowledged,
            "pacer_fees": dict(self.pacer_fees) if self.pacer_fees else None,
            "download_url": self.download_url,
        }


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseResult:
    """Run-level result for a guarded case.dev PACER purchase plan."""

    live: bool
    acknowledge_pacer_fees: bool
    capability: CaseDevPacerCapability
    dry_run: bool
    projected_cost_usd: str
    max_projected_budget_usd: str
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...]

    @property
    def intended_purchase_count(self) -> int:
        return len(self.attempts)

    @property
    def executed_purchase_count(self) -> int:
        return sum(
            1
            for attempt in self.attempts
            if attempt.status is CaseDevPacerPurchaseStatus.PURCHASED
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "live": self.live,
            "acknowledge_pacer_fees": self.acknowledge_pacer_fees,
            "capability": self.capability.value,
            "dry_run": self.dry_run,
            "projected_cost_usd": self.projected_cost_usd,
            "max_projected_budget_usd": self.max_projected_budget_usd,
            "intended_purchase_count": self.intended_purchase_count,
            "executed_purchase_count": self.executed_purchase_count,
            "attempts": [attempt.to_record() for attempt in self.attempts],
        }


class CaseDevPacerPurchaseClient:
    """Execute missing-core purchase plans only after explicit safety gates."""

    def __init__(
        self,
        client: CaseDevClient,
        *,
        capability: CaseDevPacerCapability = CaseDevPacerCapability.UNKNOWN,
    ) -> None:
        self.client = client
        self.capability = capability

    def execute_purchase_plan(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        """Execute or block a missing-core document purchase plan."""

        _validate_plan_budget(plan)
        if plan.dry_run:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.PLANNED_DRY_RUN,
                reason="dry_run_no_paid_request",
            )
        if not live:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="live_flag_required",
            )
        if not acknowledge_pacer_fees:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="acknowledge_pacer_fees_required",
            )
        if self.capability is not CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE:
            reason = (
                "document_level_purchase_unavailable"
                if self.capability
                is CaseDevPacerCapability.DOCKET_LEVEL_LIVE_FETCH_ONLY
                else "document_level_purchase_capability_unknown"
            )
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.CAPABILITY_BLOCKED,
                reason=reason,
            )

        return self._execute_document_purchases(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
        )

    def _blocked_result(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
        status: CaseDevPacerPurchaseStatus,
        reason: str,
    ) -> CaseDevPacerPurchaseResult:
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(
                CaseDevPacerPurchaseAttempt(
                    candidate_id=case_plan.candidate_id,
                    source_document_id=document_id,
                    status=status,
                    reason=reason,
                )
                for case_plan in plan.case_plans
                for document_id in case_plan.purchase_document_ids
            ),
        )

    def _execute_document_purchases(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        intended = tuple(
            (case_plan.candidate_id, document_id)
            for case_plan in plan.case_plans
            for document_id in case_plan.purchase_document_ids
        )
        attempts: list[CaseDevPacerPurchaseAttempt] = []
        for index, (candidate_id, document_id) in enumerate(intended):
            try:
                payload = self.client.purchase_pacer_document(
                    document_id,
                    acknowledge_pacer_fees=True,
                )
            except CaseDevPurchaseOutcomeUnknownError:
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.UNKNOWN,
                        reason="purchase_redirect_outcome_unknown",
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            except CaseDevClientError as exc:
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                        reason=str(exc),
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="provider_error_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            attempts.append(_successful_attempt(candidate_id, document_id, payload))
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(attempts),
        )


def _validate_plan_budget(plan: MissingCoreBudgetPlan) -> None:
    for case_plan in plan.case_plans:
        if (
            case_plan.missing_core_document_count
            > plan.max_missing_core_documents_per_case
        ):
            raise CaseDocumentCapExceededError(
                f"{case_plan.candidate_id} has "
                f"{case_plan.missing_core_document_count} missing core documents; "
                f"cap is {plan.max_missing_core_documents_per_case}"
            )
    if plan.total_estimated_cost > plan.max_projected_budget:
        raise PurchaseBudgetExceededError(
            "projected total "
            f"${plan.total_estimated_cost_usd} exceeds budget "
            f"${plan.max_projected_budget_usd}"
        )


def _successful_attempt(
    candidate_id: str,
    document_id: str,
    payload: Mapping[str, Any],
) -> CaseDevPacerPurchaseAttempt:
    return CaseDevPacerPurchaseAttempt(
        candidate_id=candidate_id,
        source_document_id=document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        fee_acknowledged=_optional_bool(
            payload,
            "acknowledgePacerFees",
            "feeAcknowledged",
        ),
        pacer_fees=_pacer_fees(payload.get("pacerFees", payload.get("pacer_fees"))),
        download_url=_optional_string(payload, "downloadUrl", "download_url", "url"),
    )


def _result(
    plan: MissingCoreBudgetPlan,
    *,
    live: bool,
    acknowledge_pacer_fees: bool,
    capability: CaseDevPacerCapability,
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...],
) -> CaseDevPacerPurchaseResult:
    return CaseDevPacerPurchaseResult(
        live=live,
        acknowledge_pacer_fees=acknowledge_pacer_fees,
        capability=capability,
        dry_run=plan.dry_run,
        projected_cost_usd=plan.total_estimated_cost_usd,
        max_projected_budget_usd=plan.max_projected_budget_usd,
        attempts=attempts,
    )


def _pacer_fees(value: object) -> Mapping[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None
    fees = cast(Mapping[object, object], value)
    return {
        "pacer_fee_usd": _money_field(fees, "pacerFee", "pacer_fee"),
        "service_fee_usd": _money_field(fees, "serviceFee", "service_fee"),
        "total_usd": _money_field(fees, "total", "totalFee", "total_fee"),
    }


def _money_field(record: Mapping[object, object], *field_names: str) -> str:
    for field_name in field_names:
        value = record.get(field_name)
        if value is not None:
            return _money(value)
    return "0.00"


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("PACER fee values must be decimal dollar amounts") from exc
    if amount < 0:
        raise ValueError("PACER fee values cannot be negative")
    return f"{amount.quantize(Decimal('0.01')):.2f}"


def _optional_bool(record: Mapping[str, Any], *field_names: str) -> bool | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, bool):
            return value
    return None


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None

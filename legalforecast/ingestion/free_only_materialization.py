"""Authenticated authority for materializing an entirely free target cohort."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast.ingestion.purchase_approval import (
    PurchaseApprovalError,
    VerifiedFreeOnlyPurchaseApproval,
    verify_free_only_purchase_approval,
)


class FreeOnlyMaterializationError(ValueError):
    """Raised when a target cohort cannot use the provider-free path."""


@dataclass(frozen=True, slots=True)
class FreeOnlyMaterializationInputs:
    """Exact evidence paths for one authenticated free-only decision."""

    checkpoint_path: Path
    run_card_path: Path
    fee_schedule_path: Path
    canonical_ledger_path: Path


def verify_free_only_materialization_authority(
    *,
    inputs: FreeOnlyMaterializationInputs,
    controlled_private_root: Path,
    target_cohort_root: Path,
    cohort_policy_path: Path,
    projected_purchased_manifest: Sequence[Mapping[str, Any]],
    free_manifest: Sequence[Mapping[str, Any]],
    selected_document_keys: set[tuple[str, str]],
) -> VerifiedFreeOnlyPurchaseApproval:
    """Replay free-only authority and prove the selection is entirely free."""

    if projected_purchased_manifest:
        raise FreeOnlyMaterializationError(
            "free-only materialization rejects projected purchased documents"
        )
    free_keys = {
        (
            _required_string(record, "candidate_id"),
            _required_string(record, "source_document_id"),
        )
        for record in free_manifest
    }
    if free_keys != selected_document_keys:
        raise FreeOnlyMaterializationError(
            "free-only materialization requires exact free-document coverage"
        )
    try:
        approval = verify_free_only_purchase_approval(
            controlled_private_root=controlled_private_root,
            checkpoint_path=inputs.checkpoint_path,
            run_card_path=inputs.run_card_path,
            target_cohort_root=target_cohort_root,
            cohort_policy_path=cohort_policy_path,
            fee_schedule_path=inputs.fee_schedule_path,
            canonical_ledger_path=inputs.canonical_ledger_path,
        )
    except (OSError, PurchaseApprovalError, UnicodeError, ValueError) as exc:
        raise FreeOnlyMaterializationError(str(exc)) from exc
    if (
        approval.decision != "free_only"
        or approval.request.purchase_document_count != 0
        or approval.request.projected_cost_usd != "0.00"
    ):
        raise FreeOnlyMaterializationError(
            "free-only authority must bind zero purchases and zero cost"
        )
    if (
        Path(approval.request.canonical_ledger_path).resolve()
        != inputs.canonical_ledger_path.resolve()
    ):
        raise FreeOnlyMaterializationError("free-only approval ledger locator changed")
    return approval


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise FreeOnlyMaterializationError(f"{key} must be a non-empty string")
    return value

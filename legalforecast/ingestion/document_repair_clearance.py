"""Small, provider-neutral clearance decisions for document-repair execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from legalforecast.ingestion.document_repair_errors import DocumentRepairExecutorError

PAID_DELIVERY_CLEARANCE_BASIS = "paid_delivery"


def post_delivery_restrictions(document: Mapping[str, object]) -> dict[str, object]:
    """Capture provider restriction fields in a non-authoritative sidecar."""

    return {
        "is_private": document.get("is_private"),
        "is_sealed": document.get("is_sealed"),
    }


def paid_clearance_pending(document: Mapping[str, object], *, route: str) -> bool:
    """Recognize explicit PACER nulls that require post-delivery evidence."""

    return (
        route == "pacer_purchase"
        and document.get("is_private") is None
        and document.get("is_sealed") is None
        and "is_private" in document
        and "is_sealed" in document
    )


def resolve_acquired_clearance(
    operation: _Operation,
    result: _Result,
) -> tuple[str, bool, bool, str]:
    """Resolve inclusion clearance while keeping every non-paid route closed."""

    if operation.public_clearance is not None:
        status, is_private, is_sealed = operation.public_clearance
        return status, is_private, is_sealed, "snapshot"
    if not operation.paid_clearance_pending or operation.route != "pacer_purchase":
        raise DocumentRepairExecutorError(
            "snapshot does not establish public clearance"
        )
    if result.paid_clearance != ("cleared", False, False):
        raise DocumentRepairExecutorError(
            "paid acquisition lacks explicit post-delivery public clearance"
        )
    if result.paid_clearance_basis != PAID_DELIVERY_CLEARANCE_BASIS:
        raise DocumentRepairExecutorError(
            "paid acquisition clearance lacks a paid-delivery basis"
        )
    return "cleared", False, False, PAID_DELIVERY_CLEARANCE_BASIS


class _Operation(Protocol):
    @property
    def public_clearance(self) -> tuple[str, bool, bool] | None: ...

    @property
    def route(self) -> str: ...

    @property
    def paid_clearance_pending(self) -> bool: ...


class _Result(Protocol):
    @property
    def paid_clearance(self) -> tuple[str, bool, bool] | None: ...

    @property
    def paid_clearance_basis(self) -> str | None: ...

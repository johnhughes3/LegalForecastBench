# pyright: reportPrivateUsage=false

"""Versioned execution bytes and the external receipt pin.

``…document_repair_execution.v2`` moves the derived snapshot clearance inside
the committed execution digest; v1 bytes stay reproducible so already-acquired
pilot receipts still replay. Sealing additionally requires an independently
supplied receipt digest, because a receipt that authenticates only against
itself is not evidence.
"""

from __future__ import annotations

import hashlib

import pytest
from legalforecast.ingestion.document_repair_executor import (
    EXECUTION_SCHEMA_VERSION_V1,
    EXECUTION_SCHEMA_VERSION_V2,
    DocumentRepairExecutorError,
    RepairOperationOutcome,
    _commit_receipt,
    record_document_repair_outcomes,
    seal_document_repair_execution,
)
from legalforecast.ingestion.missing_document_successor import (
    build_missing_document_acquisition_plan,
)
from tests.test_document_repair_executor import (
    _manifest_bytes,
    _plan_approval,
    _row,
    _snapshot,
    build_full_document_repair_execution,
)


def _full_plan_execution(schema_version: str | None = None):  # type: ignore[no-untyped-def]
    manifest = _manifest_bytes(_row("a", 1, free=True))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=_plan_approval(manifest),
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=True)}
    digests = {
        candidate: hashlib.sha256(payload).hexdigest()
        for candidate, payload in snapshots.items()
    }
    extra = {} if schema_version is None else {"schema_version": schema_version}
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256=digests,
        **extra,
    )
    return plan, execution


def _sealing_evidence(execution):  # type: ignore[no-untyped-def]
    receipt = record_document_repair_outcomes(
        execution=execution,
        outcomes=tuple(
            RepairOperationOutcome(
                operation.candidate_id,
                operation.docket_entry_number,
                "included",
                0,
                "0.10",
                "0.00" if operation.route == "courtlistener_free" else "3.00",
            )
            for operation in execution.operations
        ),
    )
    acquired = tuple(
        {
            "candidate_id": operation.candidate_id,
            "docket_entry_number": operation.docket_entry_number,
            "document_role": operation.document_role,
            "source_document_id": operation.recap_document_id,
            "source": operation.route,
            "sha256": hashlib.sha256(
                f"{operation.document_role} bytes".encode()
            ).hexdigest(),
            "byte_count": len(f"{operation.document_role} bytes".encode()),
            "document_bytes": f"{operation.document_role} bytes".encode(),
            "clearance_status": "cleared",
            "is_private": False,
            "is_sealed": False,
            "cost_usd": "0.00" if operation.route == "courtlistener_free" else "3.00",
        }
        for operation in execution.operations
    )
    return receipt, acquired


def test_execution_defaults_to_v2_and_authenticates_public_clearance() -> None:
    _, execution = _full_plan_execution()

    assert execution.schema_version == EXECUTION_SCHEMA_VERSION_V2
    record = execution.content_record()
    operations = record["operations"]
    assert isinstance(operations, list)
    assert operations[0]["public_clearance"] == {
        "status": "cleared",
        "is_private": False,
        "is_sealed": False,
    }
    assert operations[0]["paid_clearance_pending"] is False


def test_v1_execution_bytes_stay_frozen_and_omit_clearance() -> None:
    _, v1_execution = _full_plan_execution(EXECUTION_SCHEMA_VERSION_V1)
    _, v2_execution = _full_plan_execution()

    v1_operations = v1_execution.content_record()["operations"]
    assert isinstance(v1_operations, list)
    assert "public_clearance" not in v1_operations[0]
    assert v1_execution.execution_sha256 != v2_execution.execution_sha256
    # The frozen v1 record is still what receipt ledger rows carry, in both
    # versions, so receipt bytes are untouched by the migration.
    assert "public_clearance" not in v2_execution.operations[0].to_record()


def test_unknown_execution_schema_version_is_refused() -> None:
    manifest = _manifest_bytes(_row("a", 1, free=True))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=_plan_approval(manifest),
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=True)}
    with pytest.raises(DocumentRepairExecutorError, match="schema version"):
        build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                "a": hashlib.sha256(snapshots["a"]).hexdigest(),
            },
            schema_version="legalforecast.exact100_document_repair_execution.v9",
        )


def test_mutated_v2_clearance_invalidates_the_execution_digest() -> None:
    plan, execution = _full_plan_execution()
    receipt, acquired = _sealing_evidence(execution)

    object.__setattr__(execution.operations[0], "public_clearance", None)

    with pytest.raises(DocumentRepairExecutorError, match="changed after resolution"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            expected_receipt_sha256=receipt.receipt_sha256,
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )


def test_mutated_v1_clearance_still_seals_which_is_why_v2_exists() -> None:
    """Name the v1 hole explicitly so the migration is not silently reverted."""

    plan, execution = _full_plan_execution(EXECUTION_SCHEMA_VERSION_V1)
    receipt, acquired = _sealing_evidence(execution)

    object.__setattr__(execution.operations[0], "public_clearance", None)

    successor = seal_document_repair_execution(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        expected_receipt_sha256=receipt.receipt_sha256,
        acquired_documents=acquired,
        exclusions=(),
        role_bytes_match=lambda _role, _body: True,
    )
    assert successor.status == "sealed"


def test_seal_refuses_a_mutated_receipt_against_its_external_pin() -> None:
    plan, execution = _full_plan_execution()
    receipt, acquired = _sealing_evidence(execution)
    pinned = receipt.receipt_sha256

    forged_ledger = tuple(
        {**dict(row), "committed_cost_usd": "0.01"} for row in receipt.operation_ledger
    )
    object.__setattr__(receipt, "operation_ledger", forged_ledger)
    object.__setattr__(
        receipt,
        "receipt_sha256",
        _commit_receipt(receipt.content_record()),
    )

    assert receipt.receipt_sha256 != pinned
    with pytest.raises(DocumentRepairExecutorError, match="differs from its pin"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            expected_receipt_sha256=pinned,
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )


def test_seal_refuses_a_receipt_pin_that_is_not_a_digest() -> None:
    plan, execution = _full_plan_execution()
    receipt, acquired = _sealing_evidence(execution)

    with pytest.raises(DocumentRepairExecutorError, match="repair receipt digest"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            expected_receipt_sha256="not-a-digest",
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecution,
    DocumentRepairExecutorError,
    RepairOperationOutcome,
    record_document_repair_outcomes,
    run_document_repair_execution,
)
from legalforecast.ingestion.document_repair_verify_only import (
    DocumentRepairVerifyOnlyError,
    verify_document_repair_pilot_bytes,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentAcquisitionPlan,
    build_missing_document_acquisition_plan,
)
from tests.test_document_repair_executor import (
    _bound,
    _canonical_bytes,
    _manifest_bytes,
    _plan_approval,
    _purchase_runtime,
    _row,
    _snapshot,
    build_full_document_repair_execution,
)


def _null_clearance_execution() -> tuple[
    DocumentRepairExecution, MissingDocumentAcquisitionPlan
]:
    snapshots = {"a": _snapshot("a", 1, 9001, free=False)}
    payload = json.loads(snapshots["a"])
    payload["entries"][0]["recap_documents"][0]["is_private"] = None
    payload["entries"][0]["recap_documents"][0]["is_sealed"] = None
    snapshots["a"] = _canonical_bytes(payload)
    manifest = _manifest_bytes(_row("a", 1, free=False))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=_plan_approval(manifest),
    )
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
    )
    return execution, plan


def _included_outcomes(
    execution: DocumentRepairExecution,
) -> tuple[RepairOperationOutcome, ...]:
    return tuple(
        RepairOperationOutcome(
            operation.candidate_id,
            operation.docket_entry_number,
            "included",
            0,
            "0.10",
            "3.00",
        )
        for operation in execution.operations
    )


def test_paid_null_clearance_is_admitted_only_with_post_delivery_sidecar(
    tmp_path: Path,
) -> None:
    execution, _plan = _null_clearance_execution()
    assert execution.operations[0].public_clearance is None
    assert execution.operations[0].paid_clearance_pending is True
    execution_bytes = execution.to_record()
    runtime = _purchase_runtime(execution, tmp_path)
    result = run_document_repair_execution(
        execution=execution,
        purchase_runtime=runtime,
        acquire=_bound(
            runtime,
            lambda operation: AcquiredRepairDocument(
                disposition="included",
                source_document_id=operation.recap_document_id,
                document_bytes=b"reply bytes",
                committed_cost_usd="3.00",
                retry_count=0,
                paid_clearance=("cleared", False, False),
                paid_clearance_basis="paid_delivery",
            ),
        ),
        monotonic=lambda: 1.0,
    )

    assert result.acquired_documents[0]["clearance_basis"] == "paid_delivery"
    assert result.acquired_documents[0]["is_private"] is False
    assert result.acquired_documents[0]["is_sealed"] is False
    assert execution.to_record() == execution_bytes


def test_paid_null_clearance_without_sidecar_fails_after_acquisition(
    tmp_path: Path,
) -> None:
    execution, _plan = _null_clearance_execution()
    runtime = _purchase_runtime(execution, tmp_path)

    with pytest.raises(DocumentRepairExecutorError, match="post-delivery"):
        run_document_repair_execution(
            execution=execution,
            purchase_runtime=runtime,
            acquire=_bound(
                runtime,
                lambda operation: AcquiredRepairDocument(
                    disposition="included",
                    source_document_id=operation.recap_document_id,
                    document_bytes=b"reply bytes",
                    committed_cost_usd="3.00",
                    retry_count=0,
                ),
            ),
            monotonic=lambda: 1.0,
        )


def test_verify_only_accepts_paid_delivery_clearance_for_null_snapshot() -> None:
    execution, plan = _null_clearance_execution()
    receipt = record_document_repair_outcomes(
        execution=execution, outcomes=_included_outcomes(execution)
    )
    body = b"reply bytes"
    acquired = [
        {
            "candidate_id": "a",
            "docket_entry_number": 1,
            "document_selector": "main_document",
            "document_role": "reply",
            "source_document_id": "9001",
            "source": "pacer_purchase",
            "sha256": hashlib.sha256(body).hexdigest(),
            "byte_count": len(body),
            "document_bytes": body,
            "clearance_status": "cleared",
            "is_private": False,
            "is_sealed": False,
            "clearance_basis": "paid_delivery",
            "cost_usd": "3.00",
        }
    ]

    verify_document_repair_pilot_bytes(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        acquired_documents=acquired,
        exclusions=(),
        role_bytes_match=lambda role, value: role.encode() in value,
    )

    without_basis = [{**acquired[0], "clearance_basis": "snapshot"}]
    with pytest.raises(DocumentRepairVerifyOnlyError, match="paid-delivery"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=without_basis,
            exclusions=(),
            role_bytes_match=lambda role, value: role.encode() in value,
        )

"""Verify-only revalidation of already-acquired repair bytes."""

from __future__ import annotations

import hashlib

import pytest
from legalforecast.ingestion.document_repair_executor import (
    DocumentRepairExecution,
    RepairOperationOutcome,
    record_document_repair_outcomes,
)
from legalforecast.ingestion.document_repair_verify_only import (
    DocumentRepairVerifyOnlyError,
    verify_document_repair_pilot_bytes,
)
from legalforecast.ingestion.missing_document_successor import (
    build_missing_document_acquisition_plan,
)
from tests.test_document_repair_executor import (
    _manifest_bytes,
    _plan_approval,
    _row,
    _scope,
    _snapshots,
    build_document_repair_execution,
    build_full_document_repair_execution,
)


def _included_documents(
    execution: DocumentRepairExecution,
) -> list[dict[str, object]]:
    acquired: list[dict[str, object]] = []
    for operation in execution.operations:
        body = f"{operation.document_role} bytes {operation.recap_document_id}".encode()
        acquired.append(
            {
                "candidate_id": operation.candidate_id,
                "docket_entry_number": operation.docket_entry_number,
                "document_role": operation.document_role,
                "source_document_id": operation.recap_document_id,
                "source": operation.route,
                "sha256": hashlib.sha256(body).hexdigest(),
                "byte_count": len(body),
                "document_bytes": body,
                "clearance_status": "cleared",
                "is_private": False,
                "is_sealed": False,
                "cost_usd": (
                    "0.00" if operation.route == "courtlistener_free" else "3.00"
                ),
            }
        )
    return acquired


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
            "0.00" if operation.route == "courtlistener_free" else "3.00",
        )
        for operation in execution.operations
    )


def test_verify_only_accepts_pilot_bytes_and_refuses_tampered_sha256() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    execution = build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )
    receipt = record_document_repair_outcomes(
        execution=execution, outcomes=_included_outcomes(execution)
    )
    acquired = _included_documents(execution)

    verify_document_repair_pilot_bytes(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        acquired_documents=acquired,
        exclusions=(),
        role_bytes_match=lambda role, body: role.encode() in body,
    )

    tampered = [{**acquired[0], "sha256": "0" * 64}, *acquired[1:]]
    with pytest.raises(DocumentRepairVerifyOnlyError, match="sha256"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=tampered,
            exclusions=(),
            role_bytes_match=lambda role, body: role.encode() in body,
        )

    missing = [{**acquired[0], "document_bytes": b""}, *acquired[1:]]
    with pytest.raises(DocumentRepairVerifyOnlyError, match="purchase"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=missing,
            exclusions=(),
            role_bytes_match=lambda role, body: role.encode() in body,
        )


def test_verify_only_full_plan_revalidates_without_purchasing() -> None:
    manifest = _manifest_bytes(
        *(
            _row(candidate, index, free=index == 1)
            for index, candidate in enumerate("abcde", start=1)
        )
    )
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=_plan_approval(manifest),
    )
    snapshots = _snapshots()
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )
    receipt = record_document_repair_outcomes(
        execution=execution, outcomes=_included_outcomes(execution)
    )

    verify_document_repair_pilot_bytes(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        acquired_documents=_included_documents(execution),
        exclusions=(),
        role_bytes_match=lambda role, body: role.encode() in body,
    )


def test_verify_only_binds_included_bytes_to_resolved_operation() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    execution = build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )
    receipt = record_document_repair_outcomes(
        execution=execution, outcomes=_included_outcomes(execution)
    )
    acquired = _included_documents(execution)
    acquired[0] = {**acquired[0], "document_role": "complaint"}

    with pytest.raises(DocumentRepairVerifyOnlyError, match="document_role"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )

    acquired = _included_documents(execution)
    acquired[0] = {**acquired[0], "source_document_id": "9999"}
    with pytest.raises(DocumentRepairVerifyOnlyError, match="source_document_id"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )

    extra = [
        *_included_documents(execution),
        {
            **_included_documents(execution)[0],
            "candidate_id": "zzz",
            "docket_entry_number": 99,
        },
    ]
    with pytest.raises(DocumentRepairVerifyOnlyError, match="unapproved"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=extra,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )


def test_verify_only_requires_exclusion_evidence_for_excluded_operations() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    execution = build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )
    outcomes = list(_included_outcomes(execution))
    last = execution.operations[-1]
    outcomes[-1] = RepairOperationOutcome(
        last.candidate_id,
        last.docket_entry_number,
        "excluded",
        0,
        "0.10",
        "0.00",
        last.document_selector,
    )
    receipt = record_document_repair_outcomes(
        execution=execution, outcomes=tuple(outcomes)
    )
    acquired = _included_documents(execution)[:-1]

    with pytest.raises(DocumentRepairVerifyOnlyError, match="exclusion evidence"):
        verify_document_repair_pilot_bytes(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=acquired,
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )

    verify_document_repair_pilot_bytes(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        acquired_documents=acquired,
        exclusions=(
            {
                "candidate_id": last.candidate_id,
                "docket_entry_number": last.docket_entry_number,
                "document_selector": last.document_selector,
                "document_role": last.document_role,
                "reason": "terminal exclusion",
            },
        ),
        role_bytes_match=lambda role, body: role.encode() in body,
    )

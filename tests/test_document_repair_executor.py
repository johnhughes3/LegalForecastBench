"""Authenticated execution bridge tests for exact-100 document repair."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    EXACT100_DOCUMENT_REPAIR_PILOT_V2,
)
from legalforecast.ingestion.case_dev_purchase import generate_case_dev_purchase_policy
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecution,
    DocumentRepairExecutorError,
    DocumentRepairPurchaseAuthority,
    RepairOperationOutcome,
    build_document_repair_purchase_authority,
    record_document_repair_outcomes,
    replay_docket_snapshot_authority,
    run_document_repair_execution,
    seal_document_repair_execution,
    verify_purchase_policy_compatibility,
)
from legalforecast.ingestion.document_repair_executor import (
    build_document_repair_execution as _build_document_repair_execution,
)
from legalforecast.ingestion.document_repair_executor import (
    build_full_document_repair_execution as _build_full_document_repair_execution,
)
from legalforecast.ingestion.document_repair_pilot import build_document_repair_pilot
from legalforecast.ingestion.missing_document_successor import (
    build_missing_document_acquisition_plan,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _manifest_bytes(*records: Mapping[str, object]) -> bytes:
    return b"".join(_canonical_bytes(record) for record in records)


def _row(candidate_id: str, entry: int, *, free: bool) -> dict[str, object]:
    cost = 0.0 if free else 3.0
    return {
        "candidate_id": candidate_id,
        "recommendation": "repair",
        "cost_usd": cost,
        "missing_docs": [
            {
                "entry": entry,
                "role": "reply",
                "cost_usd": cost,
                "free_document_count": int(free),
                "pacer_only_document_count": int(not free),
                "evidence": "synthetic executor fixture",
                "source": "pass1",
                "opinion_derived": False,
            }
        ],
        "byte_mismatches": [],
        "current_selection": [],
        "required_entries": [],
        "extra_selected": [],
    }


def _scope() -> tuple[object, object]:
    manifest = _manifest_bytes(
        _row("a", 1, free=True),
        _row("b", 2, free=False),
        _row("c", 3, free=False),
        _row("d", 4, free=False),
        _row("e", 5, free=False),
    )
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
        max_per_document_usd="3.00",
    )
    pilot = build_document_repair_pilot(
        full_plan=plan,
        candidate_ids=("a", "b", "c", "d", "e"),
        pilot_maximum_usd="33.00",
    )
    return plan, pilot


def _snapshot(candidate_id: str, entry: int, document_id: int, *, free: bool) -> bytes:
    docket_id = (
        int(candidate_id) if candidate_id.isdigit() else int(candidate_id, 36) + 100
    )
    return _canonical_bytes(
        {
            "candidate_id": candidate_id,
            "docket_id": docket_id,
            "entries": [
                {
                    "id": entry + 1000,
                    "docket": docket_id,
                    "entry_number": entry,
                    "recap_documents": [
                        {
                            "id": document_id,
                            "docket_entry_id": entry + 1000,
                            "document_number": str(entry),
                            "attachment_number": None,
                            "is_available": free,
                            "is_sealed": False,
                            "filepath_local": (
                                f"recap/example/{document_id}.pdf" if free else None
                            ),
                        }
                    ],
                }
            ],
        }
    )


def _snapshots() -> dict[str, bytes]:
    return {
        candidate: _snapshot(candidate, index, 9000 + index, free=index == 1)
        for index, candidate in enumerate("abcde", start=1)
    }


def _snapshot_authority(snapshots: Mapping[str, bytes]):
    candidate_sha256 = {
        candidate: hashlib.sha256(payload).hexdigest()
        for candidate, payload in snapshots.items()
    }
    manifest = _canonical_bytes({"candidate_sha256": candidate_sha256})
    lineage = _canonical_bytes(
        {
            "docket_snapshot_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "cohort_policy_sha256": "1" * 64,
        }
    )
    return replay_docket_snapshot_authority(
        manifest_bytes=manifest,
        source_lineage_bytes=lineage,
        expected_source_lineage_sha256=hashlib.sha256(lineage).hexdigest(),
    )


def build_document_repair_execution(**kwargs):  # type: ignore[no-untyped-def]
    snapshots = kwargs["docket_snapshot_bytes"]
    return _build_document_repair_execution(
        **kwargs, snapshot_authority=_snapshot_authority(snapshots)
    )


def build_full_document_repair_execution(**kwargs):  # type: ignore[no-untyped-def]
    snapshots = kwargs["docket_snapshot_bytes"]
    return _build_full_document_repair_execution(
        **kwargs, snapshot_authority=_snapshot_authority(snapshots)
    )


def test_execution_resolves_exact_recap_id_and_builds_three_dollar_budget() -> None:
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

    assert execution.full_plan_sha256 == plan.plan_sha256
    assert execution.pilot_sha256 == pilot.pilot_sha256
    assert execution.operations[0].route == "courtlistener_free"
    assert execution.operations[0].recap_document_id == "9001"
    assert execution.operations[0].source_url == (
        "https://storage.courtlistener.com/recap/example/9001.pdf"
    )
    assert execution.operations[1].route == "pacer_purchase"
    assert execution.operations[1].recap_document_id == "9002"
    assert execution.purchase_budget.cost_per_document_usd == "3.00"
    assert execution.purchase_budget.max_projected_budget_usd == "33.00"
    assert execution.purchase_budget.total_estimated_cost_usd == "12.00"
    assert execution.purchase_budget.dry_run is False


def test_execution_rejects_tampered_full_plan_and_pilot_objects() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    object.__setattr__(plan, "plan_sha256", "0" * 64)
    object.__setattr__(pilot, "full_plan_sha256", "0" * 64)

    with pytest.raises(DocumentRepairExecutorError, match="full plan"):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_execution_requires_exact_ordered_pilot_projection() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    object.__setattr__(pilot, "items", pilot.items[:-1])
    object.__setattr__(
        pilot,
        "pilot_sha256",
        str(
            ARTIFACT_RAW_SHA256_V1.commit(
                pilot.content_record(), domain=EXACT100_DOCUMENT_REPAIR_PILOT_V2
            ).digest
        ),
    )

    with pytest.raises(DocumentRepairExecutorError, match="exact full-plan projection"):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_execution_rejects_tampered_or_ambiguous_resolution() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    digests = {
        candidate: hashlib.sha256(payload).hexdigest()
        for candidate, payload in snapshots.items()
    }
    digests["a"] = "0" * 64
    with pytest.raises(DocumentRepairExecutorError, match="snapshot digest"):
        _build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256=digests,
            snapshot_authority=_snapshot_authority(snapshots),
        )

    changed = dict(snapshots)
    changed["a"] = changed["a"] + b" "
    changed_digests = {
        candidate: hashlib.sha256(payload).hexdigest()
        for candidate, payload in changed.items()
    }
    with pytest.raises(DocumentRepairExecutorError, match="committed authority"):
        _build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=changed,
            docket_snapshot_sha256=changed_digests,
            snapshot_authority=_snapshot_authority(snapshots),
        )

    ambiguous = json.loads(snapshots["a"])
    ambiguous["entries"][0]["recap_documents"].append(
        {
            "id": 9999,
            "docket_entry_id": 1001,
            "document_number": None,
            "attachment_number": None,
            "is_available": True,
            "is_sealed": False,
            "filepath_local": "recap/example/9999.pdf",
        }
    )
    snapshots["a"] = _canonical_bytes(ambiguous)
    with pytest.raises(
        DocumentRepairExecutorError, match="ambiguous selected document"
    ):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_execution_rejects_free_paid_route_substitution() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    unavailable = json.loads(snapshots["a"])
    unavailable["entries"][0]["recap_documents"][0]["is_available"] = False
    unavailable["entries"][0]["recap_documents"][0]["filepath_local"] = None
    snapshots["a"] = _canonical_bytes(unavailable)

    with pytest.raises(DocumentRepairExecutorError, match="approved free route"):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_execution_rejects_private_recap_record_as_free_route() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    private = json.loads(snapshots["a"])
    private["entries"][0]["recap_documents"][0]["is_private"] = True
    snapshots["a"] = _canonical_bytes(private)

    with pytest.raises(DocumentRepairExecutorError, match="approved free route"):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_execution_rejects_snapshot_docket_id_from_another_candidate() -> None:
    row = _row("70754103", 1, free=True)
    manifest = _manifest_bytes(row)
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshot = json.loads(_snapshot("70754103", 1, 9001, free=True))
    snapshot["docket_id"] = 71212565
    snapshot["entries"][0]["docket"] = 71212565
    snapshots = {"70754103": _canonical_bytes(snapshot)}

    with pytest.raises(DocumentRepairExecutorError, match="differs from candidate"):
        build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                "70754103": hashlib.sha256(snapshots["70754103"]).hexdigest()
            },
        )


def test_execution_rejects_namespaced_candidate_bound_to_another_docket() -> None:
    candidate = "courtlistener-docket-70754103"
    row = _row(candidate, 1, free=True)
    manifest = _manifest_bytes(row)
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshot = json.loads(_snapshot("70754103", 1, 9001, free=True))
    snapshot["candidate_id"] = candidate
    snapshot["docket_id"] = 71212565
    snapshot["entries"][0]["docket"] = 71212565
    snapshots = {candidate: _canonical_bytes(snapshot)}

    with pytest.raises(DocumentRepairExecutorError, match="differs from candidate"):
        build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(snapshots[candidate]).hexdigest()
            },
        )


def _purchase_policy(*, reservation: str, hard_cap: str) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1-document-repair",
            "cohort_policy_sha256": "1" * 64,
            "canonical_ledger_path": "/controlled/purchase-ledger.sqlite3",
            "hard_cap_usd": hard_cap,
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": hard_cap,
            "per_document_reservation_usd": reservation,
            "fee_schedule": {
                "source_citation": "https://example.test/public-fee-schedule",
                "verified_at_utc": "2026-08-13T00:00:00Z",
                "includes_service_fees": True,
                "includes_pacer_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _purchase_authority(execution):  # type: ignore[no-untyped-def]
    return build_document_repair_purchase_authority(
        execution=execution,
        canonical_ledger_path="/controlled/document-repair-ledger.sqlite3",
        fee_schedule={
            "source_citation": "https://example.test/public-fee-schedule",
            "verified_at_utc": "2026-08-13T00:00:00Z",
            "includes_service_fees": True,
            "includes_pacer_fees": True,
            "includes_rounding": True,
        },
    )


def test_purchase_policy_must_fit_exact_repair_ceiling() -> None:
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

    policy = verify_purchase_policy_compatibility(
        execution=execution,
        purchase_policy_artifact=_purchase_policy(reservation="3.00", hard_cap="33.00"),
    )
    assert (
        policy.per_document_reservation_usd
        == execution.purchase_budget.cost_per_document
    )

    with pytest.raises(DocumentRepairExecutorError, match="per-document"):
        verify_purchase_policy_compatibility(
            execution=execution,
            purchase_policy_artifact=_purchase_policy(
                reservation="3.05", hard_cap="33.00"
            ),
        )
    with pytest.raises(DocumentRepairExecutorError, match="global headroom"):
        verify_purchase_policy_compatibility(
            execution=execution,
            purchase_policy_artifact=_purchase_policy(
                reservation="3.00", hard_cap="10.00"
            ),
        )


def test_unknown_paid_outcome_stops_later_operations_and_is_not_retryable() -> None:
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
        execution=execution,
        outcomes=(
            RepairOperationOutcome("a", 1, "included", 0, "0.20", "0.00"),
            RepairOperationOutcome("b", 2, "unknown", 0, "1.50", "3.00"),
        ),
    )

    assert [row["disposition"] for row in receipt.operation_ledger] == [
        "included",
        "unknown",
        "not_attempted_after_unknown",
        "not_attempted_after_unknown",
        "not_attempted_after_unknown",
    ]
    assert receipt.operation_ledger[1]["retry_permitted"] is False
    assert receipt.committed_cost_usd == "3.00"
    with pytest.raises(DocumentRepairExecutorError, match="already terminal"):
        record_document_repair_outcomes(
            execution=execution,
            outcomes=(
                RepairOperationOutcome("a", 1, "included", 0, "0.20", "0.00"),
                RepairOperationOutcome("b", 2, "unknown", 0, "1.50", "3.00"),
                RepairOperationOutcome("c", 3, "included", 0, "1.00", "3.00"),
            ),
        )
    with pytest.raises(DocumentRepairExecutorError, match="full approved reservation"):
        record_document_repair_outcomes(
            execution=execution,
            outcomes=(
                RepairOperationOutcome("a", 1, "included", 0, "0.20", "0.00"),
                RepairOperationOutcome("b", 2, "unknown", 0, "1.50", "0.00"),
            ),
        )


def test_receipt_requires_monotonic_duration_and_exact_operation_prefix() -> None:
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

    with pytest.raises(DocumentRepairExecutorError, match="duration"):
        record_document_repair_outcomes(
            execution=execution,
            outcomes=(RepairOperationOutcome("a", 1, "included", 0, "-0.01", "0.00"),),
        )
    with pytest.raises(DocumentRepairExecutorError, match="operation order"):
        record_document_repair_outcomes(
            execution=execution,
            outcomes=(RepairOperationOutcome("b", 2, "included", 0, "0.10", "3.00"),),
        )

    tampered = object.__new__(DocumentRepairExecution)
    for name in (
        "full_plan_sha256",
        "manifest_sha256",
        "source_lineage_sha256",
        "cohort_policy_sha256",
        "scope",
        "scope_sha256",
        "pilot_sha256",
        "operations",
        "purchase_budget",
        "_mint",
    ):
        object.__setattr__(tampered, name, getattr(execution, name))
    object.__setattr__(tampered, "execution_sha256", "0" * 64)
    with pytest.raises(DocumentRepairExecutorError, match="changed"):
        record_document_repair_outcomes(execution=tampered, outcomes=())


def test_purchase_authority_rejects_forged_execution_capability() -> None:
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
    forged = object.__new__(DocumentRepairExecution)
    for name in (
        "full_plan_sha256",
        "manifest_sha256",
        "source_lineage_sha256",
        "cohort_policy_sha256",
        "scope",
        "scope_sha256",
        "pilot_sha256",
        "operations",
        "purchase_budget",
        "execution_sha256",
    ):
        object.__setattr__(forged, name, getattr(execution, name))
    object.__setattr__(forged, "_mint", object())

    with pytest.raises(DocumentRepairExecutorError, match="replay-minted"):
        build_document_repair_purchase_authority(
            execution=forged,
            canonical_ledger_path="/controlled/document-repair-ledger.sqlite3",
            fee_schedule={
                "source_citation": "https://example.test/public-fee-schedule",
                "verified_at_utc": "2026-08-13T00:00:00Z",
                "includes_service_fees": True,
                "includes_pacer_fees": True,
                "includes_rounding": True,
            },
        )

    with pytest.raises(DocumentRepairExecutorError, match="replay-minted"):
        run_document_repair_execution(
            execution=forged,
            purchase_authority=None,
            acquire=lambda _operation: pytest.fail("must not invoke acquisition"),
            monotonic=lambda: 0.0,
        )


def test_purchase_authority_rejects_existing_ledger_path(tmp_path: Path) -> None:
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
    ledger_path = tmp_path / "existing-ledger.sqlite3"
    ledger_path.touch()

    with pytest.raises(DocumentRepairExecutorError, match="fresh canonical ledger"):
        build_document_repair_purchase_authority(
            execution=execution,
            canonical_ledger_path=str(ledger_path),
            fee_schedule={
                "source_citation": "https://example.test/public-fee-schedule",
                "verified_at_utc": "2026-08-13T00:00:00Z",
                "includes_service_fees": True,
                "includes_pacer_fees": True,
                "includes_rounding": True,
            },
        )


def test_paid_runner_rejects_forged_purchase_authority() -> None:
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
    valid = _purchase_authority(execution)
    forged = object.__new__(DocumentRepairPurchaseAuthority)
    for name in (
        "execution_sha256",
        "scope",
        "scope_sha256",
        "purchase_policy",
        "authority_sha256",
    ):
        object.__setattr__(forged, name, getattr(valid, name))
    object.__setattr__(forged, "_mint", object())

    with pytest.raises(DocumentRepairExecutorError, match="purchase authority"):
        run_document_repair_execution(
            execution=execution,
            purchase_authority=forged,
            acquire=lambda _operation: pytest.fail("must not invoke acquisition"),
            monotonic=lambda: 0.0,
        )


def test_execution_seals_complete_successor_only_from_exact_resolved_documents() -> (
    None
):
    manifest = _manifest_bytes(
        *(
            _row(candidate, index, free=index == 1)
            for index, candidate in enumerate("abcde", start=1)
        )
    )
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
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
    acquired = []
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
            }
        )

    successor = seal_document_repair_execution(
        full_plan=plan,
        execution=execution,
        receipt=receipt,
        acquired_documents=tuple(acquired),
        exclusions=(),
        role_bytes_match=lambda role, body: role.encode() in body,
    )

    assert successor.status == "sealed"
    assert len(successor.included_document_keys) == 5

    acquired[0]["source_document_id"] = "9999"
    with pytest.raises(DocumentRepairExecutorError, match="resolved RECAP identity"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=tuple(acquired),
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )

    acquired[0]["source_document_id"] = "9001"
    with pytest.raises(DocumentRepairExecutorError, match="contradicts"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=tuple(acquired[1:]),
            exclusions=(
                {
                    "candidate_id": "a",
                    "docket_entry_number": 1,
                    "document_role": "reply",
                    "reason": "contradictory exclusion",
                },
            ),
            role_bytes_match=lambda _role, _body: True,
        )


def test_unknown_receipt_cannot_seal_successor() -> None:
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
        execution=execution,
        outcomes=(
            RepairOperationOutcome("a", 1, "included", 0, "0.10", "0.00"),
            RepairOperationOutcome("b", 2, "unknown", 0, "0.10", "3.00"),
        ),
    )

    with pytest.raises(DocumentRepairExecutorError, match="full-plan"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=(),
            exclusions=(),
            role_bytes_match=lambda _role, _body: True,
        )


def test_retryable_provider_error_cannot_seal_successor() -> None:
    manifest = _manifest_bytes(_row("a", 1, free=False))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=False)}
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
    )
    receipt = record_document_repair_outcomes(
        execution=execution,
        outcomes=(RepairOperationOutcome("a", 1, "provider_error", 0, "0.10", "0.00"),),
    )

    with pytest.raises(DocumentRepairExecutorError, match="nonterminal outcomes"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=receipt,
            acquired_documents=(),
            exclusions=(
                {
                    "candidate_id": "a",
                    "docket_entry_number": 1,
                    "document_role": "complaint",
                    "reason": "temporary provider failure",
                },
            ),
            role_bytes_match=lambda _role, _body: True,
        )


def test_retry_permitted_terminal_receipt_cannot_seal_successor() -> None:
    manifest = _manifest_bytes(_row("a", 1, free=False))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=False)}
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
    )
    receipt = record_document_repair_outcomes(
        execution=execution,
        outcomes=(RepairOperationOutcome("a", 1, "included", 0, "0.10", "3.00"),),
    )
    row = {**receipt.operation_ledger[0], "retry_permitted": True}
    tampered = replace(receipt, operation_ledger=(row,), receipt_sha256="")
    tampered = replace(
        tampered,
        receipt_sha256=str(
            ARTIFACT_RAW_SHA256_V1.commit(
                tampered.content_record(),
                domain="legalforecast.exact100_document_repair_receipt.v1",
            ).digest
        ),
    )
    body = b"reply"

    with pytest.raises(DocumentRepairExecutorError, match="retry permission"):
        seal_document_repair_execution(
            full_plan=plan,
            execution=execution,
            receipt=tampered,
            acquired_documents=(
                {
                    "candidate_id": "a",
                    "docket_entry_number": 1,
                    "document_role": "reply",
                    "source_document_id": "9001",
                    "source": "pacer_purchase",
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "byte_count": len(body),
                    "document_bytes": body,
                },
            ),
            exclusions=(),
            role_bytes_match=lambda role, value: role.encode() == value,
        )


def test_terminal_exclusion_is_not_retryable() -> None:
    manifest = _manifest_bytes(_row("a", 1, free=False))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=False)}
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
    )

    receipt = record_document_repair_outcomes(
        execution=execution,
        outcomes=(RepairOperationOutcome("a", 1, "excluded", 0, "0.10", "0.00"),),
    )

    assert receipt.operation_ledger[0]["retry_permitted"] is False


def test_runner_invokes_free_first_and_stops_after_unknown_paid_outcome() -> None:
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
    invoked: list[str] = []
    ticks = iter((1.0, 1.2, 2.0, 3.5))

    def acquire(operation):  # type: ignore[no-untyped-def]
        invoked.append(operation.recap_document_id)
        if operation.route == "courtlistener_free":
            return AcquiredRepairDocument(
                disposition="included",
                source_document_id=operation.recap_document_id,
                document_bytes=b"reply free bytes",
                committed_cost_usd="0.00",
                retry_count=1,
            )
        return AcquiredRepairDocument(
            disposition="unknown",
            source_document_id=operation.recap_document_id,
            document_bytes=None,
            committed_cost_usd="3.00",
            retry_count=0,
            reason="purchase_outcome_unknown",
        )

    result = run_document_repair_execution(
        execution=execution,
        purchase_authority=_purchase_authority(execution),
        acquire=acquire,
        monotonic=lambda: next(ticks),
    )

    assert invoked == ["9001", "9002"]
    assert [row["duration_seconds"] for row in result.receipt.operation_ledger[:2]] == [
        "0.200000",
        "1.500000",
    ]
    assert len(result.acquired_documents) == 1
    assert result.exclusions == ()
    assert result.receipt.operation_ledger[2]["disposition"] == (
        "not_attempted_after_unknown"
    )


def test_runner_materializes_complete_evidence_for_successor_seal() -> None:
    manifest = _manifest_bytes(
        *(
            _row(candidate, index, free=index == 1)
            for index, candidate in enumerate("abcde", start=1)
        )
    )
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
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
    tick = iter(float(value) for value in range(11))

    result = run_document_repair_execution(
        execution=execution,
        purchase_authority=_purchase_authority(execution),
        acquire=lambda operation: AcquiredRepairDocument(
            disposition="included",
            source_document_id=operation.recap_document_id,
            document_bytes=f"{operation.document_role} bytes".encode(),
            committed_cost_usd=(
                "0.00" if operation.route == "courtlistener_free" else "3.00"
            ),
            retry_count=0,
        ),
        monotonic=lambda: next(tick),
    )
    successor = seal_document_repair_execution(
        full_plan=plan,
        execution=execution,
        receipt=result.receipt,
        acquired_documents=result.acquired_documents,
        exclusions=result.exclusions,
        role_bytes_match=lambda role, body: role.encode() in body,
    )

    assert successor.status == "sealed"
    assert result.receipt.committed_cost_usd == "12.00"


def test_paid_runner_requires_exact_generated_purchase_authority() -> None:
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

    with pytest.raises(DocumentRepairExecutorError, match="purchase authority"):
        run_document_repair_execution(
            execution=execution,
            purchase_authority=None,
            acquire=lambda _operation: pytest.fail("must not invoke acquisition"),
            monotonic=lambda: 0.0,
        )

    authority = _purchase_authority(execution)
    assert authority.execution_sha256 == execution.execution_sha256
    assert authority.purchase_policy.per_document_reservation_usd == 3
    assert authority.purchase_policy.hard_cap_usd == 33
    assert authority.authority_sha256


def test_full_execution_covers_every_plan_item_under_full_approval() -> None:
    manifest = _manifest_bytes(
        *(
            _row(candidate, index, free=index == 1)
            for index, candidate in enumerate("abcdef", start=1)
        )
    )
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
        max_per_document_usd="3.00",
    )
    snapshots = {
        candidate: _snapshot(candidate, index, 9000 + index, free=index == 1)
        for index, candidate in enumerate("abcdef", start=1)
    }

    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )

    assert execution.scope == "full_plan"
    assert execution.scope_sha256 == plan.plan_sha256
    assert execution.pilot_sha256 is None
    assert len(execution.operations) == len(plan.items) == 6
    assert execution.purchase_budget.max_projected_budget_usd == "453.00"
    assert execution.purchase_budget.total_estimated_cost_usd == "15.00"


def test_full_execution_requires_exact_snapshot_candidate_set() -> None:
    manifest = _manifest_bytes(_row("a", 1, free=True), _row("b", 2, free=False))
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=True)}

    with pytest.raises(DocumentRepairExecutorError, match="exactly cover"):
        build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
        )


def test_execution_rejects_nonapproved_per_document_price() -> None:
    row = _row("a", 1, free=False)
    row["cost_usd"] = 4.0
    missing = row["missing_docs"]
    assert isinstance(missing, list)
    missing[0]["cost_usd"] = 4.0
    manifest = _manifest_bytes(row)
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
        max_per_document_usd="4.00",
    )
    snapshots = {"a": _snapshot("a", 1, 9001, free=False)}

    with pytest.raises(DocumentRepairExecutorError, match=r"approved \$3\.00"):
        build_full_document_repair_execution(
            full_plan=plan,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={"a": hashlib.sha256(snapshots["a"]).hexdigest()},
        )


def test_pilot_execution_rejects_nonapproved_per_document_price() -> None:
    rows = []
    for index, candidate in enumerate("abcde", start=1):
        row = _row(candidate, index, free=False)
        row["cost_usd"] = 4.0
        missing = row["missing_docs"]
        assert isinstance(missing, list)
        missing[0]["cost_usd"] = 4.0
        rows.append(row)
    manifest = _manifest_bytes(*rows)
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
        max_per_document_usd="4.00",
    )
    pilot = build_document_repair_pilot(
        full_plan=plan,
        candidate_ids=tuple("abcde"),
        pilot_maximum_usd="33.00",
    )
    snapshots = {
        candidate: _snapshot(candidate, index, 9000 + index, free=False)
        for index, candidate in enumerate("abcde", start=1)
    }

    with pytest.raises(DocumentRepairExecutorError, match=r"approved \$3\.00"):
        build_document_repair_execution(
            full_plan=plan,
            pilot=pilot,
            docket_snapshot_bytes=snapshots,
            docket_snapshot_sha256={
                candidate: hashlib.sha256(payload).hexdigest()
                for candidate, payload in snapshots.items()
            },
        )


def test_pilot_accepts_authenticated_subset_of_snapshot_manifest() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    authority_snapshots = {
        **snapshots,
        "unaffected": _snapshot("unaffected", 99, 9999, free=True),
    }

    execution = _build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
        snapshot_authority=_snapshot_authority(authority_snapshots),
    )

    assert tuple(operation.candidate_id for operation in execution.operations) == tuple(
        "abcde"
    )


def test_snapshot_authority_candidate_commitments_are_immutable() -> None:
    authority = _snapshot_authority(_snapshots())

    with pytest.raises(TypeError):
        authority.candidate_sha256["a"] = "0" * 64  # type: ignore[index]


def test_execution_accepts_v4_docket_resource_url() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    snapshot = json.loads(snapshots["a"])
    docket_id = snapshot["docket_id"]
    snapshot["entries"][0]["docket"] = (
        f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
    )
    snapshots["a"] = _canonical_bytes(snapshot)

    execution = build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )

    assert execution.operations[0].docket_entry_id == "1001"


def test_execution_treats_string_zero_attachment_as_main_document() -> None:
    plan, pilot = _scope()
    snapshots = _snapshots()
    snapshot = json.loads(snapshots["a"])
    snapshot["entries"][0]["recap_documents"][0]["attachment_number"] = "0"
    snapshots["a"] = _canonical_bytes(snapshot)

    execution = build_document_repair_execution(
        full_plan=plan,
        pilot=pilot,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            candidate: hashlib.sha256(payload).hexdigest()
            for candidate, payload in snapshots.items()
        },
    )

    assert execution.operations[0].document_selector == "main_document"


def test_execution_resolves_same_entry_attachment_selector() -> None:
    row = _row("73569789", 5, free=False)
    missing = row["missing_docs"]
    assert isinstance(missing, list)
    missing[0]["role"] = "motion"
    missing.append(
        {
            **missing[0],
            "role": "supporting_memorandum",
            "document_selector": "attachment_1",
        }
    )
    row["cost_usd"] = 6.0
    manifest = _manifest_bytes(row)
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )
    snapshot = json.loads(_snapshot("73569789", 5, 9005, free=False))
    snapshot["entries"][0]["recap_documents"].append(
        {
            "id": 9105,
            "docket_entry_id": 1005,
            "document_number": "5-1",
            "attachment_number": 1,
            "is_available": False,
            "is_sealed": False,
            "filepath_local": None,
        }
    )
    snapshots = {"73569789": _canonical_bytes(snapshot)}

    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            "73569789": hashlib.sha256(snapshots["73569789"]).hexdigest()
        },
    )

    assert [operation.document_selector for operation in execution.operations] == [
        "attachment_1",
        "main_document",
    ]
    assert [operation.recap_document_id for operation in execution.operations] == [
        "9105",
        "9005",
    ]

    ticks = iter((1.0, 1.2, 2.0, 2.3))
    result = run_document_repair_execution(
        execution=execution,
        purchase_authority=_purchase_authority(execution),
        acquire=lambda resolved: AcquiredRepairDocument(
            disposition="included",
            source_document_id=resolved.recap_document_id,
            document_bytes=resolved.document_role.encode(),
            committed_cost_usd="3.00",
            retry_count=0,
            document_selector=resolved.document_selector,
        ),
        monotonic=lambda: next(ticks),
    )

    successor = seal_document_repair_execution(
        full_plan=plan,
        execution=execution,
        receipt=result.receipt,
        acquired_documents=result.acquired_documents,
        exclusions=result.exclusions,
        role_bytes_match=lambda role, body: role.encode() == body,
    )

    assert [row["document_selector"] for row in result.receipt.operation_ledger] == [
        "attachment_1",
        "main_document",
    ]
    assert [row["document_selector"] for row in result.acquired_documents] == [
        "attachment_1",
        "main_document",
    ]
    assert successor.included_document_keys == frozenset(
        {
            ("73569789", 5, "main_document"),
            ("73569789", 5, "attachment_1"),
        }
    )

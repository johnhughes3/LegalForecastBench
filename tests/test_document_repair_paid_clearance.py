from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.document_repair_acquire import DocumentRepairAcquirer
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
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentFetch,
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
        expected_receipt_sha256=receipt.receipt_sha256,
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
            expected_receipt_sha256=receipt.receipt_sha256,
            acquired_documents=without_basis,
            exclusions=(),
            role_bytes_match=lambda role, value: role.encode() in value,
        )


# --- Live CourtListener v4 shape (legalforecastbench-n3y7) -------------------
#
# CourtListener REST v4 no longer serializes is_private on any RECAP-document
# serializer, so the executor's paid-clearance gate could not be satisfied by
# any live response and refused every document-repair purchase. The fixture
# below is captured v4 bytes with no hand-added keys: these tests fail if the
# gate ever regresses to demanding a field the provider does not send, and the
# canary fails if the provider starts sending it again.

_CAPTURED_ENTRY_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "courtlistener"
    / "docket-entry-attachments-no-is-private-v4.json"
)
_CAPTURED_CANDIDATE_ID = "68966872"
_CAPTURED_ENTRY_NUMBER = 19
_CAPTURED_PAID_DOCUMENT_ID = "490298006"
_PURCHASED_BYTES = b"motion_memorandum purchased bytes"
_DOWNLOAD_URL = "https://storage.courtlistener.com/recap/example/490298006.pdf"


def _captured_entry() -> dict[str, Any]:
    return cast(
        "dict[str, Any]", json.loads(_CAPTURED_ENTRY_PATH.read_text(encoding="utf-8"))
    )


def _captured_paid_document(entry: dict[str, Any]) -> dict[str, Any]:
    for document in cast("list[dict[str, Any]]", entry["recap_documents"]):
        if str(document["id"]) == _CAPTURED_PAID_DOCUMENT_ID:
            return document
    raise AssertionError("captured fixture lost its PACER-only attachment row")


def _captured_snapshot(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> bytes:
    entry = _captured_entry()
    if mutate is not None:
        mutate(entry)
    return _canonical_bytes(
        {
            "candidate_id": _CAPTURED_CANDIDATE_ID,
            "docket_id": int(_CAPTURED_CANDIDATE_ID),
            "entries": [entry],
        }
    )


def _captured_manifest() -> bytes:
    return _manifest_bytes(
        {
            "candidate_id": _CAPTURED_CANDIDATE_ID,
            "recommendation": "repair",
            "cost_usd": 3.0,
            "missing_docs": [
                {
                    "entry": _CAPTURED_ENTRY_NUMBER,
                    "document_selector": "attachment_1",
                    "role": "motion_memorandum",
                    "cost_usd": 3.0,
                    "free_document_count": 0,
                    "pacer_only_document_count": 1,
                    "evidence": "captured CourtListener v4 docket entry 451158527",
                    "source": "pass1",
                    "opinion_derived": False,
                }
            ],
            "byte_mismatches": [],
            "current_selection": [],
            "required_entries": [],
            "extra_selected": [],
        }
    )


def _captured_execution(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[DocumentRepairExecution, MissingDocumentAcquisitionPlan]:
    snapshots = {_CAPTURED_CANDIDATE_ID: _captured_snapshot(mutate)}
    manifest = _captured_manifest()
    plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=_plan_approval(manifest),
    )
    execution = build_full_document_repair_execution(
        full_plan=plan,
        docket_snapshot_bytes=snapshots,
        docket_snapshot_sha256={
            _CAPTURED_CANDIDATE_ID: hashlib.sha256(
                snapshots[_CAPTURED_CANDIDATE_ID]
            ).hexdigest()
        },
    )
    return execution, plan


_OMIT_RESTRICTIONS = object()


class _DeliveringRecapClient:
    """RECAP Fetch stub that journals one post-delivery provider document."""

    def __init__(self, journal: object, restrictions: object) -> None:
        self.journal = journal
        self._restrictions = restrictions

    def execute_one_document(
        self, candidate_id: str, document_id: str
    ) -> CaseDevPacerPurchaseAttempt:
        journal = cast(Any, self.journal)
        journal.submit(document_id)
        response: dict[str, object] = {"status": "confirmed"}
        if self._restrictions is not _OMIT_RESTRICTIONS:
            response["post_delivery_restrictions"] = self._restrictions
        journal.confirm(document_id, response=response, fees={"total_usd": "3.00"})
        return CaseDevPacerPurchaseAttempt(
            candidate_id=candidate_id,
            source_document_id=document_id,
            status=CaseDevPacerPurchaseStatus.PURCHASED,
            download_url=_DOWNLOAD_URL,
            pacer_fees={"total_usd": "3.00"},
        )


def _run_captured_purchase(
    tmp_path: Path,
    *,
    restrictions: object,
) -> tuple[DocumentRepairExecution, Any]:
    """Execute the captured paid row through the production acquire adapter."""

    execution, _plan = _captured_execution()
    runtime = _purchase_runtime(execution, tmp_path)
    acquirer = DocumentRepairAcquirer(
        journal=runtime.journal,
        free_source=FixtureFreeDocumentSource({}),
        recap_client=cast(Any, _DeliveringRecapClient(runtime.journal, restrictions)),
        fetch_purchased=lambda _url: FreeDocumentFetch(content=_PURCHASED_BYTES),
    )
    result = run_document_repair_execution(
        execution=execution,
        purchase_runtime=runtime,
        acquire=acquirer,
        monotonic=lambda: 1.0,
    )
    return execution, result


def test_captured_v4_fixture_omits_is_private_on_every_row() -> None:
    entry = _captured_entry()
    documents = cast("list[dict[str, Any]]", entry["recap_documents"])

    assert documents, "captured fixture must carry RECAP document rows"
    for document in documents:
        assert "is_private" not in document
        assert "is_sealed" in document
        assert document["is_sealed"] is None


def test_live_v4_paid_row_pends_clearance_instead_of_refusing() -> None:
    execution, _plan = _captured_execution()
    operation = execution.operations[0]

    assert operation.route == "pacer_purchase"
    assert operation.recap_document_id == _CAPTURED_PAID_DOCUMENT_ID
    # The snapshot cannot mint clearance for a paid row from live bytes, so the
    # hand-set ("cleared", False, False) shortcut is unreachable here.
    assert operation.public_clearance is None
    assert operation.paid_clearance_pending is True


def test_live_v4_paid_row_clears_through_post_delivery_evidence(
    tmp_path: Path,
) -> None:
    delivered = _captured_paid_document(_captured_entry())

    execution, result = _run_captured_purchase(tmp_path, restrictions=delivered)

    acquired = result.acquired_documents[0]
    assert acquired["clearance_status"] == "cleared"
    assert acquired["clearance_basis"] == "paid_delivery"
    assert acquired["is_private"] is False
    assert acquired["is_sealed"] is False
    assert acquired["document_bytes"] == _PURCHASED_BYTES
    assert result.exclusions == ()
    assert result.receipt.operation_ledger[0]["disposition"] == "included"
    assert execution.operations[0].public_clearance is None


@pytest.mark.parametrize(
    ("label", "restrictions"),
    [
        ("missing_evidence", _OMIT_RESTRICTIONS),
        ("empty_evidence", {}),
        ("not_a_mapping", "cleared"),
        ("asserted_private", {"is_private": True, "is_sealed": None}),
        ("asserted_sealed", {"is_private": None, "is_sealed": True}),
        ("sealed_field_dropped", {"is_private": None}),
        # A restriction asserted as a non-boolean must refuse too. Reading these
        # fields as an "is True" blacklist rather than an identity whitelist
        # would clear every one of the five cases below.
        ("truthy_int_sealed", {"is_private": None, "is_sealed": 1}),
        ("truthy_string_private", {"is_private": "true", "is_sealed": None}),
        ("falsey_string_sealed", {"is_private": None, "is_sealed": "false"}),
        ("zero_int_sealed", {"is_private": None, "is_sealed": 0}),
        ("list_private", {"is_private": [1], "is_sealed": None}),
    ],
)
def test_live_v4_paid_row_refuses_unproven_delivery_evidence(
    tmp_path: Path,
    label: str,
    restrictions: object,
) -> None:
    _execution, result = _run_captured_purchase(tmp_path, restrictions=restrictions)

    assert result.acquired_documents == (), label
    assert result.receipt.operation_ledger[0]["disposition"] == "excluded", label
    assert result.exclusions[0]["reason"] == "paid_delivery_clearance_unproven", label


@pytest.mark.parametrize("field", ["is_private", "is_sealed"])
def test_live_v4_snapshot_asserting_a_restriction_never_reaches_purchase(
    field: str,
) -> None:
    def assert_restriction(entry: dict[str, Any]) -> None:
        _captured_paid_document(entry)[field] = True

    with pytest.raises(DocumentRepairExecutorError, match="restricted material"):
        _captured_execution(assert_restriction)

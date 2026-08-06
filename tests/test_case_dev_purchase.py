from __future__ import annotations

import fcntl
import os
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.ingestion import (
    CaseDevClient,
    CaseDevFixtureTransport,
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
    PurchaseBudgetExceededError,
)
from legalforecast.ingestion import case_dev_purchase as purchase_module
from legalforecast.ingestion.case_dev_client import RecordedCaseDevResponse
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseClient,
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
    read_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    plan_missing_core_document_budget,
)
from tests.purchase_approval_fixtures import (
    allow_historical_v1_algorithm_fixtures,
)


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_purchase_client_blocks_without_live_flag_or_acknowledgment() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )
    plan = _budget_plan("case-1", ("doc-1",), dry_run=False)

    result = client.execute_purchase_plan(
        plan,
        live=False,
        acknowledge_pacer_fees=True,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED
    assert result.attempts[0].reason == "live_flag_required"

    result = client.execute_purchase_plan(
        plan,
        live=True,
        acknowledge_pacer_fees=False,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED
    assert result.attempts[0].reason == "acknowledge_pacer_fees_required"


def test_purchase_snapshot_is_strictly_read_only(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    journal.plan(_budget_plan("case-1", ("doc-1",), dry_run=False))
    journal.close()
    reserved_paths = (
        journal.path,
        Path(f"{journal.path}.lock"),
        Path(f"{journal.path}-wal"),
        Path(f"{journal.path}-shm"),
        Path(f"{journal.path}-journal"),
    )
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in reserved_paths
        if path.exists()
    }

    snapshot = read_case_dev_purchase_snapshot(journal.path, policy=policy)

    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in reserved_paths
        if path.exists()
    }
    assert before == after
    assert set(before) == set(after)
    assert snapshot.operations[0]["source_document_id"] == "doc-1"
    assert len(snapshot.purchase_state_sha256) == 64


def test_purchase_snapshot_replays_wal_without_changing_sqlite_files(
    tmp_path: Path,
) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    anchor = sqlite3.connect(journal.path, isolation_level=None)
    try:
        anchor.execute("PRAGMA wal_autocheckpoint=0")
        anchor.execute("BEGIN")
        anchor.execute("SELECT COUNT(*) FROM purchase_operations").fetchone()
        journal._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "PRAGMA wal_autocheckpoint=0"
        )
        journal.plan(_budget_plan("case-1", ("doc-1",), dry_run=False))
        journal.submit("doc-1")
        journal.fail_before_dispatch("doc-1", "terminal fixture failure")
        expected_digest = journal.purchase_state_sha256()
        journal.close()

        reserved_paths = (
            journal.path,
            Path(f"{journal.path}.lock"),
            Path(f"{journal.path}-wal"),
            Path(f"{journal.path}-shm"),
            Path(f"{journal.path}-journal"),
        )
        assert Path(f"{journal.path}-wal").exists()
        assert Path(f"{journal.path}-shm").exists()
        with sqlite3.connect(
            f"file:{journal.path}?mode=ro&immutable=1", uri=True
        ) as main_file_only:
            with pytest.raises(sqlite3.OperationalError, match="no such table"):
                main_file_only.execute(
                    "SELECT COUNT(*) FROM purchase_operations"
                ).fetchone()
        old_atime_ns = 946_684_800_000_000_000
        for path in reserved_paths:
            if path.exists():
                metadata = path.stat()
                os.utime(path, ns=(old_atime_ns, metadata.st_mtime_ns))
        before = purchase_module._purchase_snapshot_filesystem_identity(  # pyright: ignore[reportPrivateUsage]
            reserved_paths
        )
        assert all(identity[4] == old_atime_ns for identity in before)

        with CaseDevPurchaseJournal(
            journal.path, policy=policy, read_only=True
        ) as read_only_journal:
            assert read_only_journal.purchase_state_sha256() == expected_digest
            assert tuple(
                row["status"] for row in read_only_journal.operation_records()
            ) == ("failed",)
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                read_only_journal.plan(
                    _budget_plan("case-2", ("doc-2",), dry_run=False)
                )

        snapshot = read_case_dev_purchase_snapshot(journal.path, policy=policy)

        after = purchase_module._purchase_snapshot_filesystem_identity(  # pyright: ignore[reportPrivateUsage]
            reserved_paths
        )
        assert before == after
        assert snapshot.purchase_state_sha256 == expected_digest
        assert tuple(row["status"] for row in snapshot.operations) == ("failed",)
    finally:
        anchor.close()


def test_purchase_snapshot_recovers_hot_rollback_journal_only_in_private_copy(
    tmp_path: Path,
) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    journal.plan(_budget_plan("case-1", ("doc-1",), dry_run=False))
    journal.close()
    writer = sqlite3.connect(journal.path, isolation_level=None)
    try:
        assert writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE purchase_operations SET status='submitted' "
            "WHERE source_document_id='doc-1'"
        )
        rollback_journal_path = Path(f"{journal.path}-journal")
        assert rollback_journal_path.stat().st_size > 0
        reserved_paths = (
            journal.path,
            Path(f"{journal.path}.lock"),
            Path(f"{journal.path}-wal"),
            Path(f"{journal.path}-shm"),
            rollback_journal_path,
        )
        before = purchase_module._purchase_snapshot_filesystem_identity(  # pyright: ignore[reportPrivateUsage]
            reserved_paths
        )

        snapshot = read_case_dev_purchase_snapshot(journal.path, policy=policy)

        after = purchase_module._purchase_snapshot_filesystem_identity(  # pyright: ignore[reportPrivateUsage]
            reserved_paths
        )
        assert before == after
        assert tuple(row["status"] for row in snapshot.operations) == ("planned",)
    finally:
        writer.rollback()
        writer.close()


def test_purchase_snapshot_closes_lock_when_descriptor_inspection_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    journal.close()
    original_fstat = purchase_module.os.fstat
    original_close = purchase_module.os.close
    inspected_descriptors: list[int] = []
    closed_descriptors: list[int] = []

    def fail_first_fstat(descriptor: int) -> object:
        inspected_descriptors.append(descriptor)
        if len(inspected_descriptors) == 1:
            raise OSError("injected descriptor inspection failure")
        return original_fstat(descriptor)

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(purchase_module.os, "fstat", fail_first_fstat)
    monkeypatch.setattr(purchase_module.os, "close", record_close)

    with pytest.raises(
        RuntimeError,
        match="purchase ledger lock path changed while opening read-only",
    ):
        read_case_dev_purchase_snapshot(journal.path, policy=policy)

    assert closed_descriptors == inspected_descriptors


def test_read_only_lock_rejects_path_swap_at_flock_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal(tmp_path)
    journal.close()
    lock_path = Path(f"{journal.path}.lock")
    displaced_lock_path = Path(f"{lock_path}.displaced")
    original_flock = purchase_module.fcntl.flock
    original_close = purchase_module.os.close
    shared_lock_fd: int | None = None
    closed_descriptors: list[int] = []
    swapped = False

    def swap_path_after_lock(descriptor: int, operation: int) -> None:
        nonlocal shared_lock_fd, swapped
        original_flock(descriptor, operation)
        if not swapped and operation & fcntl.LOCK_SH:
            shared_lock_fd = descriptor
            os.replace(lock_path, displaced_lock_path)
            lock_path.touch(mode=0o600)
            swapped = True

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(purchase_module.fcntl, "flock", swap_path_after_lock)
    monkeypatch.setattr(purchase_module.os, "close", record_close)

    with pytest.raises(
        RuntimeError,
        match="purchase ledger lock path changed while acquiring read-only lock",
    ):
        purchase_module._acquire_existing_purchase_ledger_lock(  # pyright: ignore[reportPrivateUsage]
            journal.path
        )

    assert shared_lock_fd is not None
    assert shared_lock_fd in closed_descriptors
    new_lock_fd = os.open(lock_path, os.O_RDONLY)
    try:
        original_flock(new_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        original_flock(new_lock_fd, fcntl.LOCK_UN)
        os.close(new_lock_fd)


def test_read_only_open_preserves_primary_error_and_releases_lock_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    journal.close()
    snapshot_directory = tmp_path / "failing-snapshot-cleanup"
    snapshot_directory.mkdir()
    original_acquire = purchase_module._acquire_existing_purchase_ledger_lock  # pyright: ignore[reportPrivateUsage]
    original_close = purchase_module.os.close
    acquired_descriptors: list[int] = []
    closed_descriptors: list[int] = []

    class PrimaryCopyError(RuntimeError):
        pass

    class CleanupError(RuntimeError):
        pass

    class FailingTemporaryDirectory:
        def __init__(self, *, prefix: str) -> None:
            assert prefix == "legalforecast-purchase-audit-"
            self.name = str(snapshot_directory)

        def cleanup(self) -> None:
            raise CleanupError("injected temporary-directory cleanup failure")

    def record_acquire(path: Path) -> int:
        descriptor = original_acquire(path)
        acquired_descriptors.append(descriptor)
        return descriptor

    def fail_copy(source: Path, destination: Path) -> None:
        raise PrimaryCopyError(f"injected copy failure: {source} -> {destination}")

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(
        purchase_module, "_acquire_existing_purchase_ledger_lock", record_acquire
    )
    monkeypatch.setattr(purchase_module, "_copy_purchase_snapshot_namespace", fail_copy)
    monkeypatch.setattr(
        purchase_module.tempfile, "TemporaryDirectory", FailingTemporaryDirectory
    )
    monkeypatch.setattr(purchase_module.os, "close", record_close)

    with pytest.raises(PrimaryCopyError) as caught:
        CaseDevPurchaseJournal(journal.path, policy=policy, read_only=True)

    assert isinstance(caught.value.__cause__, ExceptionGroup)
    assert any(
        isinstance(error, CleanupError) for error in caught.value.__cause__.exceptions
    )
    assert len(acquired_descriptors) == 1
    assert acquired_descriptors[0] in closed_descriptors


def test_read_only_identity_rejects_path_swap_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal(tmp_path)
    journal.close()
    displaced_path = Path(f"{journal.path}.displaced")
    replacement_bytes = journal.path.read_bytes()
    original_read = purchase_module.os.read
    original_close = purchase_module.os.close
    read_descriptor: int | None = None
    closed_descriptors: list[int] = []
    swapped = False

    def swap_path_during_read(descriptor: int, count: int) -> bytes:
        nonlocal read_descriptor, swapped
        payload = original_read(descriptor, count)
        if not swapped:
            read_descriptor = descriptor
            os.replace(journal.path, displaced_path)
            journal.path.write_bytes(replacement_bytes)
            swapped = True
        return payload

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(purchase_module.os, "read", swap_path_during_read)
    monkeypatch.setattr(purchase_module.os, "close", record_close)

    with pytest.raises(
        RuntimeError,
        match="purchase ledger path changed during read-only audit",
    ):
        purchase_module._purchase_snapshot_filesystem_identity(  # pyright: ignore[reportPrivateUsage]
            (journal.path,)
        )

    assert read_descriptor is not None
    assert read_descriptor in closed_descriptors


def test_purchase_snapshot_rejects_semantically_corrupt_material_state(
    tmp_path: Path,
) -> None:
    journal = _journal(tmp_path)
    policy = journal.policy
    journal.plan(_budget_plan("case-1", ("doc-1",), dry_run=False))
    journal.close()
    with sqlite3.connect(journal.path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            """UPDATE purchase_material_state
            SET authority='unknown_status_attempt'
            WHERE source_document_id='doc-1'"""
        )

    with pytest.raises(
        RuntimeError,
        match="unknown-status material lacks attempt authority",
    ):
        read_case_dev_purchase_snapshot(journal.path, policy=policy)


def test_purchase_client_records_capability_blocked_for_docket_level_only() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCKET_LEVEL_LIVE_FETCH_ONLY,
    )

    result = client.execute_purchase_plan(
        _budget_plan("case-1", ("doc-1",), dry_run=False),
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.CAPABILITY_BLOCKED
    assert result.attempts[0].reason == "document_level_purchase_unavailable"


def test_purchase_client_posts_acknowledged_document_purchase_and_records_fees(
    tmp_path: Path,
) -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload={
                    "documentId": "doc-1",
                    "acknowledgePacerFees": True,
                    "pacerFees": {
                        "serviceFee": 3.05,
                        "pacerFee": 0.0,
                        "total": 3.05,
                    },
                    "downloadUrl": "https://case.dev/download/doc-1.pdf",
                },
            )
        ]
    )
    with _journal(tmp_path) as journal:
        client = CaseDevPacerPurchaseClient(
            _case_dev_client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        )
        result = client.execute_purchase_plan(
            _budget_plan("case-1", ("doc-1",), dry_run=False),
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert transport.requests == [
        (
            "POST",
            "/legal/v1/documents/doc-1/pacer",
            {"live": True, "acknowledgePacerFees": True},
        )
    ]
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.PURCHASED
    assert result.attempts[0].fee_acknowledged is True
    assert result.attempts[0].pacer_fees == {
        "pacer_fee_usd": "0.00",
        "service_fee_usd": "3.05",
        "total_usd": "3.05",
    }


def test_purchase_client_records_case_dev_errors_without_continuing_blindly(
    tmp_path: Path,
) -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=402,
                payload={"error": "pacer fee cap exceeded"},
            )
        ]
    )
    with _journal(tmp_path) as journal:
        client = CaseDevPacerPurchaseClient(
            _case_dev_client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        )
        result = client.execute_purchase_plan(
            _budget_plan("case-1", ("doc-1",), dry_run=False),
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.PROVIDER_ERROR
    assert result.attempts[0].reason == "pacer fee cap exceeded"


def test_purchase_redirect_records_unknown_and_retains_full_plan_reservation(
    tmp_path: Path,
) -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=302,
                payload={"error": "redirected purchase"},
            )
        ]
    )
    case_dev_client = _case_dev_client(transport)
    with _journal(tmp_path) as journal:
        client = CaseDevPacerPurchaseClient(
            case_dev_client,
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        )
        result = client.execute_purchase_plan(
            _budget_plan("case-1", ("doc-1", "doc-2"), dry_run=False),
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert [attempt.status for attempt in result.attempts] == [
        CaseDevPacerPurchaseStatus.UNKNOWN,
        CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
    ]
    assert result.attempts[0].reason == "purchase_outcome_unknown"
    assert result.attempts[1].reason == "unknown_outcome_before_attempt"
    assert result.projected_cost_usd == "6.10"
    assert result.executed_purchase_count == 0
    assert case_dev_client.request_count == 1
    assert len(transport.requests) == 1


def test_purchase_client_rechecks_spend_cap_before_any_request() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )
    bad_plan = MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=("doc-1", "doc-2"),
                missing_core_document_count=2,
                estimated_cost=Decimal("6.10"),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("6.09"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )

    with pytest.raises(
        PurchaseBudgetExceededError,
        match=r"projected total \$6\.10 exceeds budget \$6\.09",
    ):
        client.execute_purchase_plan(
            bad_plan,
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert transport.requests == []


def _budget_plan(
    candidate_id: str,
    document_ids: tuple[str, ...],
    *,
    dry_run: bool,
) -> MissingCoreBudgetPlan:
    filter_result = _filter_result(candidate_id, document_ids)
    return plan_missing_core_document_budget([filter_result], dry_run=dry_run)


def _filter_result(candidate_id: str, document_ids: tuple[str, ...]):
    from legalforecast.ingestion import CoreDocumentFilterResult

    return CoreDocumentFilterResult(
        candidate_id=candidate_id,
        purchase_document_ids=document_ids,
        core_mtd_documents=document_ids,
        core_exhibit_documents=(),
        model_visible_document_ids=document_ids,
        operative_complaint_document_id=document_ids[0] if document_ids else None,
        operative_complaint_documents=document_ids[:1],
        audit_only_document_ids=(),
        core_missing_documents=document_ids,
        exclusion_reasons=(),
    )


def _case_dev_client(transport: CaseDevFixtureTransport) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=transport,
    )


def _journal(tmp_path: Path) -> CaseDevPurchaseJournal:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "2250.00",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "73.20",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "case.dev docs",
                "verified_at_utc": "2026-07-13T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    return CaseDevPurchaseJournal(
        ledger,
        policy=verify_case_dev_purchase_policy(artifact),
        allow_create=True,
    )

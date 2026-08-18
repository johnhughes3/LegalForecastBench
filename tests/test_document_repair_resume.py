"""Resume tests for an interrupted document-repair purchase tranche.

The scenario reproduced here is the one that stranded the s3a combined tranche:
a paid run confirms its first document, then dies on the *free* verification GET
that precedes the second document's submission. The ledger is left with one
confirmed row and the rest still planned -- and until this module's verb
existed, that state had no supported way forward, because purchase authority is
mintable only while the canonical ledger is absent.

Every fixture here is hand-authored (``synthetic: true``) and offline. The
tranche factories are imported from ``test_document_repair_purchase_approval``
so both suites exercise one manifest and cohort contract rather than two
drifting ones; only the docket snapshots are local, because a resumed tranche's
paid documents must carry the CourtListener REST v4 shape (``is_sealed`` present
and null, ``is_private`` absent) that makes clearance a post-delivery question.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion import document_repair_resume_cli as resume_cli
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    initialize_case_dev_purchase_journal,
    read_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
)
from legalforecast.ingestion.document_repair_acquire import (
    DocumentRepairAcquirer,
    paid_delivery_clearance_from_journal,
)
from legalforecast.ingestion.document_repair_clearance import (
    PAID_DELIVERY_CLEARANCE_BASIS,
)
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecutorError,
    ResolvedRepairOperation,
    build_document_repair_purchase_resume_authority,
    run_document_repair_execution,
    verify_document_repair_purchase_resume_runtime,
)
from legalforecast.ingestion.document_repair_purchase_approval import (
    DocumentRepairPurchaseApprovalError,
    DocumentRepairPurchaseInputs,
    DocumentRepairPurchaseProjection,
    build_document_repair_purchase_approval_request,
    build_document_repair_purchase_resume_request,
    generate_approved_document_repair_purchase_policy,
    initialize_document_repair_purchase_runtime,
    resume_document_repair_purchase_runtime,
    verify_document_repair_purchase_approval,
    verify_document_repair_purchase_resume_approval,
)
from legalforecast.ingestion.document_repair_resume import (
    DocumentRepairResumeError,
    ResumingDocumentRepairAcquirer,
    plan_document_repair_resume,
    purchase_statuses,
    read_prior_acquired_documents,
)
from legalforecast.ingestion.free_document_downloader import FreeDocumentFetch
from legalforecast.ingestion.purchase_approval import record_purchase_approval
from tests.test_document_repair_purchase_approval import (
    _canonical,
    _cohort_policy_artifact,
    _fee_schedule,
    _manifest_row,
)

_REVIEWER = "John Hughes"
_RECORDED_AT = "2026-08-19T09:00:00Z"
_INITIALIZED_AT = "2026-08-19T09:05:00Z"
_FIRST = "9002"
_SECOND = "9003"


def _paid_snapshot_bytes(candidate_id: str, entry: int, document_id: int) -> bytes:
    """Return one PACER-only docket snapshot in the provider's live v4 shape.

    ``is_sealed`` is serialized as null and ``is_private`` is not serialized at
    all, which is what CourtListener actually sends. That combination is what
    makes ``paid_clearance_pending`` true, so the resumed documents here take
    the same post-delivery clearance path the real tranche does.
    """

    docket_id = int(candidate_id, 36) + 100
    return _canonical(
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
                            "is_available": False,
                            "is_sealed": None,
                            "filepath_local": None,
                        }
                    ],
                }
            ],
        }
    )


@pytest.fixture
def tranche(tmp_path: Path) -> dict[str, Any]:
    """Materialize one two-paid-document tranche root plus its approval sources."""

    root = tmp_path / "repair-tranche"
    snapshots = root / "docket-snapshots"
    snapshots.mkdir(parents=True)
    (root / "acquired").mkdir()

    manifest = b"".join(
        _canonical(row)
        for row in (
            _manifest_row("b", 2, free=False),
            _manifest_row("c", 3, free=False),
        )
    )
    manifest_path = root / "repair-manifest.jsonl"
    manifest_path.write_bytes(manifest)

    rows = [json.loads(line) for line in manifest.splitlines()]
    approval_path = root / "repair-plan-approval.json"
    approval_path.write_bytes(
        _canonical(
            {
                "schema_version": "legalforecast.repair_manifest_approval.v2",
                "decision": "approve",
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "maximum_cost_usd": "6.00",
                "max_per_document_usd": "3.00",
                "candidate_count": len(rows),
                "repair_count": len(rows),
                "keep_count": 0,
                "replace_count": 0,
                "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
            }
        )
    )

    payloads = {
        "b": _paid_snapshot_bytes("b", 2, int(_FIRST)),
        "c": _paid_snapshot_bytes("c", 3, int(_SECOND)),
    }
    for candidate_id, payload in payloads.items():
        (snapshots / f"{candidate_id}.json").write_bytes(payload)

    cohort_artifact = _cohort_policy_artifact()
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_bytes(_canonical(cohort_artifact))

    snapshot_manifest = _canonical(
        {
            "candidate_sha256": {
                candidate_id: hashlib.sha256(payload).hexdigest()
                for candidate_id, payload in payloads.items()
            }
        }
    )
    snapshot_manifest_path = root / "docket-snapshot-manifest.json"
    snapshot_manifest_path.write_bytes(snapshot_manifest)

    lineage = _canonical(
        {
            "docket_snapshot_manifest_sha256": hashlib.sha256(
                snapshot_manifest
            ).hexdigest(),
            "cohort_policy_sha256": cast(str, cohort_artifact["policy_sha256"]),
        }
    )
    lineage_path = root / "source-lineage.json"
    lineage_path.write_bytes(lineage)

    fee_path = tmp_path / "fee-schedule.json"
    fee_path.write_bytes(_canonical(_fee_schedule()))

    return {
        "inputs": DocumentRepairPurchaseInputs(
            repair_execution_root=root,
            repair_manifest_path=manifest_path,
            repair_plan_approval_path=approval_path,
            docket_snapshot_manifest_path=snapshot_manifest_path,
            source_lineage_path=lineage_path,
            source_lineage_sha256=hashlib.sha256(lineage).hexdigest(),
            docket_snapshot_dir=snapshots,
        ),
        "cohort_policy_path": cohort_path,
        "fee_schedule_path": fee_path,
        "canonical_ledger_path": tmp_path / "purchase/repair-ledger.sqlite3",
        "private_root": tmp_path / "private-repair-approval",
        "root": root,
        "acquired_dir": root / "acquired",
        "policy_path": root / "approved-purchase-policy.json",
        "receipt_path": tmp_path / "purchase/purchase-ledger-initialization.json",
    }


def _projection(
    tranche: Mapping[str, Any], *, resume: bool = False
) -> DocumentRepairPurchaseProjection:
    build = (
        build_document_repair_purchase_resume_request
        if resume
        else build_document_repair_purchase_approval_request
    )
    return build(
        inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
        canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
    )


def _issue(tranche: Mapping[str, Any]) -> DocumentRepairPurchaseProjection:
    """Record the owner approval, publish the policy, and initialize the ledger."""

    projection = _projection(tranche)
    private_root = cast(Path, tranche["private_root"])
    checkpoint, run_card = record_purchase_approval(
        request=projection.request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=projection.request.required_confirmation("approve"),
        reviewer_id=_REVIEWER,
        recorded_at_utc=_RECORDED_AT,
    )
    approval = verify_document_repair_purchase_approval(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
        inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
        canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
    )
    artifact = generate_approved_document_repair_purchase_policy(approval)
    cast(Path, tranche["policy_path"]).write_bytes(
        json.dumps(artifact, indent=2, sort_keys=True).encode() + b"\n"
    )
    initialize_document_repair_purchase_runtime(
        execution=projection.execution,
        purchase_policy_path=cast(Path, tranche["policy_path"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        initialization_receipt_path=cast(Path, tranche["receipt_path"]),
        initialized_at=_INITIALIZED_AT,
    ).runtime.journal.close()
    return projection


class _InterruptedFirstRun:
    """Confirm the first paid document, then die before the second is submitted.

    The failure is raised where the real one occurred: inside the acquire
    callback for the next operation, *before* ``purchase_broker
    .prepare_submission`` and ``journal.submit``. The second row therefore
    stays ``planned`` and nothing was charged for it.
    """

    def __init__(self, journal: CaseDevPurchaseJournal, acquired_dir: Path) -> None:
        self.journal = journal
        self.acquired_dir = acquired_dir

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        if operation.recap_document_id != _FIRST:
            raise ConnectionError("CourtListener verification GET outcome is unknown")
        return _confirm_and_persist(self.journal, operation, self.acquired_dir)


def _confirm_and_persist(
    journal: CaseDevPurchaseJournal,
    operation: ResolvedRepairOperation,
    acquired_dir: Path,
) -> AcquiredRepairDocument:
    """Drive one document through the journal states a real delivery walks."""

    document_id = operation.recap_document_id
    journal.submit(document_id, context={"reservation_usd": "3.00"})
    journal.queue(document_id, response={"queue_id": "77", "reservation_id": "r-77"})
    journal.confirm_reserved(
        document_id,
        response={
            "queue_id": "77",
            "reservation_id": "r-77",
            "reservation_usd": "3.00",
            "download_url": f"https://storage.courtlistener.com/recap/{document_id}.pdf",
            "post_delivery_restrictions": {"is_sealed": None, "id": document_id},
        },
    )
    payload = f"{operation.document_role} bytes for {document_id}".encode()
    path = acquired_dir / (
        f"{operation.candidate_id}-{operation.docket_entry_number}-"
        f"{operation.document_role}-{document_id}.pdf"
    )
    path.write_bytes(payload)
    with (acquired_dir / "progress.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "candidate_id": operation.candidate_id,
                    "docket_entry_number": operation.docket_entry_number,
                    "document_role": operation.document_role,
                    "document_selector": operation.document_selector,
                    "source_document_id": document_id,
                    "source": operation.route,
                    "disposition": "included",
                    "committed_cost_usd": "3.00",
                    "reason": None,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "byte_count": len(payload),
                    "path": str(path),
                },
                sort_keys=True,
            )
            + "\n"
        )
    return AcquiredRepairDocument(
        disposition="included",
        source_document_id=document_id,
        document_bytes=payload,
        committed_cost_usd="3.00",
        retry_count=0,
        document_selector=operation.document_selector,
        paid_clearance=paid_delivery_clearance_from_journal(journal, document_id),
        paid_clearance_basis=PAID_DELIVERY_CLEARANCE_BASIS,
    )


def _policy(tranche: Mapping[str, Any]) -> CaseDevPurchasePolicy:
    return verify_case_dev_purchase_policy(
        json.loads(cast(Path, tranche["policy_path"]).read_text(encoding="utf-8"))
    )


def _purchase_state(tranche: Mapping[str, Any]) -> str:
    """Read the ledger's current authenticated purchase-state digest."""

    return read_case_dev_purchase_snapshot(
        cast(Path, tranche["canonical_ledger_path"]),
        policy=_policy(tranche),
        initialization_receipt_path=cast(Path, tranche["receipt_path"]),
    ).purchase_state_sha256


def _resumption(
    tranche: Mapping[str, Any], *, expected_purchase_state_sha256: str | None = None
) -> Any:
    return resume_document_repair_purchase_runtime(
        execution=_projection(tranche, resume=True).execution,
        purchase_policy_path=cast(Path, tranche["policy_path"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        initialization_receipt_path=cast(Path, tranche["receipt_path"]),
        expected_purchase_state_sha256=(
            _purchase_state(tranche)
            if expected_purchase_state_sha256 is None
            else expected_purchase_state_sha256
        ),
    )


@pytest.fixture
def interrupted(tranche: dict[str, Any]) -> dict[str, Any]:
    """Leave the tranche exactly as the halted s3a run left its own: 1 of 2."""

    projection = _issue(tranche)
    issuance = resume_document_repair_purchase_runtime(
        execution=projection.execution,
        purchase_policy_path=cast(Path, tranche["policy_path"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        initialization_receipt_path=cast(Path, tranche["receipt_path"]),
        expected_purchase_state_sha256=_purchase_state(tranche),
    )
    ticks = iter(float(value) for value in range(12))
    with pytest.raises(ConnectionError):
        run_document_repair_execution(
            execution=projection.execution,
            purchase_runtime=issuance.runtime,
            acquire=_InterruptedFirstRun(
                issuance.runtime.journal, cast(Path, tranche["acquired_dir"])
            ),
            monotonic=lambda: next(ticks),
        )
    return {**tranche, "projection": projection}


class _RecordingDispatch:
    """Stand in for the live acquirer, recording exactly what was dispatched."""

    def __init__(self, journal: CaseDevPurchaseJournal, acquired_dir: Path) -> None:
        self.journal = journal
        self.acquired_dir = acquired_dir
        self.dispatched: list[str] = []

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        self.dispatched.append(operation.recap_document_id)
        return _confirm_and_persist(self.journal, operation, self.acquired_dir)


def _resume(
    tranche: Mapping[str, Any],
) -> tuple[Any, _RecordingDispatch, dict[str, Any]]:
    """Run the supported resume against the interrupted tranche."""

    projection = _projection(tranche, resume=True)
    execution = projection.execution
    carried = read_prior_acquired_documents(
        progress_path=cast(Path, tranche["acquired_dir"]) / "progress.jsonl",
        acquired_dir=cast(Path, tranche["acquired_dir"]),
        execution=execution,
    )
    issuance = resume_document_repair_purchase_runtime(
        execution=execution,
        purchase_policy_path=cast(Path, tranche["policy_path"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        initialization_receipt_path=cast(Path, tranche["receipt_path"]),
        expected_purchase_state_sha256=_purchase_state(tranche),
    )
    journal = issuance.runtime.journal
    plan = plan_document_repair_resume(
        execution=execution,
        policy=journal.policy,
        statuses=journal.statuses(),
        committed_amount_usd=journal.committed_amount_usd,
        carried_documents=carried,
    )
    dispatch = _RecordingDispatch(journal, cast(Path, tranche["acquired_dir"]))
    ticks = iter(float(value) for value in range(12))
    result = run_document_repair_execution(
        execution=execution,
        purchase_runtime=issuance.runtime,
        acquire=ResumingDocumentRepairAcquirer(
            journal=journal,
            dispatch=dispatch,
            carried_documents=carried,
        ),
        monotonic=lambda: next(ticks),
    )
    return result, dispatch, {"plan": plan, "carried": carried, "issuance": issuance}


def test_resume_dispatches_only_planned_rows_and_carries_the_confirmed_one(
    interrupted: dict[str, Any],
) -> None:
    """The property the whole verb exists for: a paid row is bought once."""

    prior_bytes = (
        cast(Path, interrupted["acquired_dir"]) / f"b-2-reply-{_FIRST}.pdf"
    ).read_bytes()

    result, dispatch, context = _resume(interrupted)

    # Only the row the journal still called planned reached a dispatcher.
    assert dispatch.dispatched == [_SECOND]
    plan = context["plan"]
    assert plan.dispatch_document_ids == (_SECOND,)
    assert plan.carried_document_ids == (_FIRST,)
    assert plan.committed_spend_usd == Decimal("3.00")
    assert plan.remaining_ceiling_usd == Decimal("3.00")
    assert plan.projected_dispatch_cost_usd == Decimal("3.00")

    # Both documents are present, and the carried one is the original bytes.
    acquired = {
        str(row["source_document_id"]): row for row in result.acquired_documents
    }
    assert sorted(acquired) == [_FIRST, _SECOND]
    assert acquired[_FIRST]["sha256"] == hashlib.sha256(prior_bytes).hexdigest()
    assert acquired[_FIRST]["clearance_basis"] == PAID_DELIVERY_CLEARANCE_BASIS

    # The receipt covers the whole tranche at exactly the approved maximum.
    assert len(result.receipt.operation_ledger) == 2
    assert result.receipt.committed_cost_usd == "6.00"


def test_resume_refuses_a_ledger_rolled_back_after_its_state_was_pinned(
    interrupted: dict[str, Any],
) -> None:
    """The gap the initialization receipt cannot close: a rewritten history.

    The receipt testifies to the ledger's *initial* state, so a ledger restored
    from an older copy of the same lineage -- or edited to put a spent row back
    to ``planned`` -- passes receipt lineage, initialization identity, policy
    binding and document-set equality while offering an already-bought document
    as buyable. Only a pin taken from outside that ledger can see it.
    """

    pinned = _purchase_state(interrupted)
    connection = sqlite3.connect(cast(Path, interrupted["canonical_ledger_path"]))
    try:
        connection.execute(
            """UPDATE purchase_operations
            SET status='planned', operation_key=NULL, response_json=NULL
            WHERE source_document_id=?""",
            (_FIRST,),
        )
        connection.commit()
    finally:
        connection.close()

    # Every other gate is still satisfied: the rollback preserved policy,
    # lineage and initialization identity, and the document set is unchanged.
    assert _purchase_state(interrupted) != pinned
    with pytest.raises(DocumentRepairPurchaseApprovalError, match="rolled back"):
        _resumption(interrupted, expected_purchase_state_sha256=pinned)


class _RefusingFreeSource:
    """Any download at all would falsify the property under test."""

    def fetch(self, source_url: str) -> FreeDocumentFetch:
        raise AssertionError(f"a resumed confirmed row must not download: {source_url}")


def test_a_confirmed_row_reaches_no_paid_call_through_the_real_client(
    interrupted: dict[str, Any],
) -> None:
    """Zero provider contact when every row is already bought.

    This runs the real ``CourtListenerRecapFetchClient`` rather than a
    stand-in, against a transport and a broker that would record any request
    made. A tranche whose purchases all completed before the run died must
    reach the end of a resume without a single one.
    """

    # Finish the interrupted tranche's remaining document, then resume again:
    # the second resume has nothing planned left and must contact nobody.
    _first, dispatch, _context = _resume(interrupted)
    assert dispatch.dispatched == [_SECOND]

    execution = _projection(interrupted, resume=True).execution
    carried = read_prior_acquired_documents(
        progress_path=cast(Path, interrupted["acquired_dir"]) / "progress.jsonl",
        acquired_dir=cast(Path, interrupted["acquired_dir"]),
        execution=execution,
    )
    issuance = _resumption(interrupted)
    journal = issuance.runtime.journal
    transport = FixtureRecapFetchTransport(())
    broker = FixtureRecapFetchPurchaseBroker(())
    client = CourtListenerRecapFetchClient(
        CourtListenerRecapFetchConfig(api_token="offline-fixture-token"),
        journal=journal,
        transport=transport,
        purchase_broker=broker,
    )
    ticks = iter(float(value) for value in range(12))
    result = run_document_repair_execution(
        execution=execution,
        purchase_runtime=issuance.runtime,
        acquire=ResumingDocumentRepairAcquirer(
            journal=journal,
            dispatch=DocumentRepairAcquirer(
                journal=journal,
                free_source=_RefusingFreeSource(),
                recap_client=client,
            ),
            carried_documents=carried,
        ),
        monotonic=lambda: next(ticks),
    )

    assert transport.requests == []
    assert broker.requests == []
    assert client.paid_request_count == 0
    assert client.courtlistener_request_count == 0
    assert len(result.acquired_documents) == 2
    assert result.receipt.committed_cost_usd == "6.00"


def test_resume_refuses_a_row_whose_outcome_is_still_ambiguous(
    interrupted: dict[str, Any],
) -> None:
    """An unknown row is recovered before a resume, never dispatched again."""

    projection = _projection(interrupted, resume=True)
    carried = read_prior_acquired_documents(
        progress_path=cast(Path, interrupted["acquired_dir"]) / "progress.jsonl",
        acquired_dir=cast(Path, interrupted["acquired_dir"]),
        execution=projection.execution,
    )
    issuance = resume_document_repair_purchase_runtime(
        execution=projection.execution,
        purchase_policy_path=cast(Path, interrupted["policy_path"]),
        cohort_policy_path=cast(Path, interrupted["cohort_policy_path"]),
        initialization_receipt_path=cast(Path, interrupted["receipt_path"]),
        expected_purchase_state_sha256=_purchase_state(interrupted),
    )
    journal = issuance.runtime.journal
    try:
        journal.submit(_SECOND, context={"reservation_usd": "3.00"})
        journal.mark_unknown(_SECOND, "provider outcome unknown")
        with pytest.raises(DocumentRepairResumeError, match="dispatches only planned"):
            plan_document_repair_resume(
                execution=projection.execution,
                policy=journal.policy,
                statuses=journal.statuses(),
                committed_amount_usd=journal.committed_amount_usd,
                carried_documents=carried,
            )
    finally:
        journal.close()


def test_resume_refuses_a_ledger_carrying_a_foreign_row(
    interrupted: dict[str, Any],
) -> None:
    """A ledger must hold this execution's documents and no others.

    ``journal.plan`` inserts what is missing but ignores what is extra, so a
    row belonging to another tranche would otherwise ride along invisibly.
    """

    projection = _projection(interrupted, resume=True)
    connection = sqlite3.connect(cast(Path, interrupted["canonical_ledger_path"]))
    try:
        connection.execute(
            """INSERT INTO purchase_operations(
            source_document_id, candidate_id, reservation_usd, status)
            VALUES ('4242', 'b', '3.00', 'planned')"""
        )
        connection.execute(
            """INSERT INTO purchase_material_state(
            source_document_id, authority, status)
            VALUES ('4242', 'ordinary_public', 'not_recovered')"""
        )
        connection.commit()
    finally:
        connection.close()

    snapshot = read_case_dev_purchase_snapshot(
        cast(Path, interrupted["canonical_ledger_path"]),
        policy=verify_case_dev_purchase_policy(
            json.loads(cast(Path, interrupted["policy_path"]).read_text())
        ),
        initialization_receipt_path=cast(Path, interrupted["receipt_path"]),
    )
    statuses = purchase_statuses(snapshot.operations)
    assert "4242" in statuses

    with pytest.raises(DocumentRepairResumeError, match="do not match this execution"):
        plan_document_repair_resume(
            execution=projection.execution,
            policy=verify_case_dev_purchase_policy(
                json.loads(cast(Path, interrupted["policy_path"]).read_text())
            ),
            statuses=statuses,
            committed_amount_usd=snapshot.committed_amount_usd,
            carried_documents={},
        )
    assert main(_cli_arguments(interrupted)) == 2


def test_resume_ceiling_accounts_for_the_interrupted_run_s_spend(
    interrupted: dict[str, Any],
) -> None:
    """Remaining headroom is the approved maximum minus what was already spent."""

    projection = _projection(interrupted, resume=True)
    carried = read_prior_acquired_documents(
        progress_path=cast(Path, interrupted["acquired_dir"]) / "progress.jsonl",
        acquired_dir=cast(Path, interrupted["acquired_dir"]),
        execution=projection.execution,
    )
    policy = verify_case_dev_purchase_policy(
        json.loads(cast(Path, interrupted["policy_path"]).read_text())
    )
    statuses = {_FIRST: "confirmed", _SECOND: "planned"}

    # A reconciled charge above the reservation leaves too little for the rest.
    with pytest.raises(DocumentRepairResumeError, match="remaining of the approved"):
        plan_document_repair_resume(
            execution=projection.execution,
            policy=policy,
            statuses=statuses,
            committed_amount_usd="4.00",
            carried_documents=carried,
        )

    # A repair tranche always opens at zero, so the opening-balance subtraction
    # is a no-op in production and would go unproven without saying it here:
    # the journal reports spend inclusive of any opening cycle balance, and
    # only the tranche's own share may count against the tranche's maximum.
    opened = replace(policy, opening_committed_spend_usd=Decimal("2.00"))
    plan = plan_document_repair_resume(
        execution=projection.execution,
        policy=opened,
        statuses=statuses,
        committed_amount_usd="5.00",
        carried_documents=carried,
    )
    assert plan.committed_spend_usd == Decimal("3.00")
    assert plan.remaining_ceiling_usd == Decimal("3.00")


def test_resume_refuses_carried_bytes_that_lost_their_recorded_digest(
    interrupted: dict[str, Any],
) -> None:
    """Carried-forward evidence is re-proved from bytes, not taken on trust."""

    projection = _projection(interrupted, resume=True)
    document = cast(Path, interrupted["acquired_dir"]) / f"b-2-reply-{_FIRST}.pdf"
    document.write_bytes(document.read_bytes() + b" tampered")

    with pytest.raises(DocumentRepairResumeError, match="recorded digest"):
        read_prior_acquired_documents(
            progress_path=cast(Path, interrupted["acquired_dir"]) / "progress.jsonl",
            acquired_dir=cast(Path, interrupted["acquired_dir"]),
            execution=projection.execution,
        )


def test_resume_refuses_a_tampered_approval_checkpoint(
    interrupted: dict[str, Any],
) -> None:
    """The resume replays the recorded approval in full, not just its digest."""

    private_root = cast(Path, interrupted["private_root"])
    checkpoint = private_root / "purchase-approval-checkpoint.json"
    artifact = json.loads(checkpoint.read_text(encoding="utf-8"))
    artifact["checkpoint"]["reviewer_id"] = "Someone Else"
    checkpoint.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")

    with pytest.raises(DocumentRepairPurchaseApprovalError):
        verify_document_repair_purchase_resume_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=private_root / "run-cards/record-purchase-approval.json",
            inputs=cast(DocumentRepairPurchaseInputs, interrupted["inputs"]),
            cohort_policy_path=cast(Path, interrupted["cohort_policy_path"]),
            fee_schedule_path=cast(Path, interrupted["fee_schedule_path"]),
            canonical_ledger_path=cast(Path, interrupted["canonical_ledger_path"]),
        )


def test_resume_runtime_refuses_an_initialization_receipt_bound_elsewhere(
    interrupted: dict[str, Any],
) -> None:
    """The receipt must commit to the policy bytes this resume actually read."""

    projection = _projection(interrupted, resume=True)
    authority = build_document_repair_purchase_resume_authority(
        execution=projection.execution,
        approved_purchase_policy_artifact=json.loads(
            cast(Path, interrupted["policy_path"]).read_text()
        ),
    )
    with pytest.raises(
        DocumentRepairExecutorError, match="purchase_policy_file_sha256"
    ):
        verify_document_repair_purchase_resume_runtime(
            execution=projection.execution,
            purchase_authority=authority,
            initialization_receipt_path=cast(Path, interrupted["receipt_path"]),
            purchase_policy_file_sha256="sha256:" + "e" * 64,
            cohort_policy_file_sha256="sha256:" + "f" * 64,
            expected_purchase_state_sha256=_purchase_state(interrupted),
        )


def test_resume_authority_requires_the_ledger_the_first_mint_forbade(
    tranche: dict[str, Any],
) -> None:
    """The two authority mints are exact complements, and both stay closed.

    ``build_document_repair_purchase_authority`` refuses once the ledger
    exists; the resume mint refuses until it does. Neither can stand in for the
    other, which is what stops a resume verb from becoming a way to re-run an
    un-started tranche outside its issuance gate.
    """

    projection = _projection(tranche)
    private_root = cast(Path, tranche["private_root"])
    checkpoint, run_card = record_purchase_approval(
        request=projection.request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=projection.request.required_confirmation("approve"),
        reviewer_id=_REVIEWER,
        recorded_at_utc=_RECORDED_AT,
    )
    artifact = generate_approved_document_repair_purchase_policy(
        verify_document_repair_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
            inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
            cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
            fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
            canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
        )
    )

    with pytest.raises(DocumentRepairExecutorError, match="initialized canonical"):
        build_document_repair_purchase_resume_authority(
            execution=projection.execution,
            approved_purchase_policy_artifact=artifact,
        )

    initialize_case_dev_purchase_journal(
        cast(Path, tranche["canonical_ledger_path"]),
        policy=verify_case_dev_purchase_policy(artifact),
        receipt_path=cast(Path, tranche["receipt_path"]),
        purchase_policy_file_sha256="sha256:" + "c" * 64,
        cohort_policy_file_sha256="sha256:" + "d" * 64,
        initialized_at=_INITIALIZED_AT,
    )
    assert (
        build_document_repair_purchase_resume_authority(
            execution=projection.execution,
            approved_purchase_policy_artifact=artifact,
        ).execution_sha256
        == projection.execution.execution_sha256
    )


def test_resume_projection_and_issuance_projection_hold_the_same_request(
    interrupted: dict[str, Any],
) -> None:
    """The signed request does not move when the ledger appears.

    This is the fact a resume rests on. ``ledger_initial_state`` records the
    boundary at issuance rather than reading the ledger now, so the re-minted
    request still reproduces the digest the reviewer typed against -- which is
    why the resume can replay the original checkpoint instead of asking for a
    second sitting against new bytes.
    """

    resumed = _projection(interrupted, resume=True)
    recorded = json.loads(
        (
            cast(Path, interrupted["private_root"])
            / "purchase-approval-checkpoint.json"
        ).read_text(encoding="utf-8")
    )
    assert recorded["checkpoint"]["request"] == resumed.request.to_record()
    assert (
        resumed.request.ledger_initial_state == "absent_fresh_initialization_required"
    )
    assert cast(Path, interrupted["canonical_ledger_path"]).exists()


def _cli_arguments(tranche: Mapping[str, Any]) -> list[str]:
    inputs = cast(DocumentRepairPurchaseInputs, tranche["inputs"])
    private_root = cast(Path, tranche["private_root"])
    projection = cast(DocumentRepairPurchaseProjection, tranche["projection"])
    return [
        "acquisition",
        "resume-document-repair-purchase",
        "--repair-execution-root",
        str(inputs.repair_execution_root),
        "--repair-manifest",
        str(inputs.repair_manifest_path),
        "--repair-plan-approval",
        str(inputs.repair_plan_approval_path),
        "--docket-snapshot-manifest",
        str(inputs.docket_snapshot_manifest_path),
        "--source-lineage",
        str(inputs.source_lineage_path),
        "--source-lineage-sha256",
        inputs.source_lineage_sha256,
        "--docket-snapshot-dir",
        str(inputs.docket_snapshot_dir),
        "--cohort-policy",
        str(tranche["cohort_policy_path"]),
        "--fee-schedule",
        str(tranche["fee_schedule_path"]),
        "--canonical-ledger-path",
        str(tranche["canonical_ledger_path"]),
        "--controlled-private-root",
        str(private_root),
        "--checkpoint",
        str(private_root / "purchase-approval-checkpoint.json"),
        "--approval-run-card",
        str(private_root / "run-cards/record-purchase-approval.json"),
        "--purchase-policy",
        str(tranche["policy_path"]),
        "--acquired-dir",
        str(tranche["acquired_dir"]),
        "--expected-request-sha256",
        projection.request.request_sha256,
        "--expected-execution-sha256",
        projection.execution.execution_sha256,
    ]


def _ledger_namespace(tranche: Mapping[str, Any]) -> dict[str, bytes | None]:
    ledger = cast(Path, tranche["canonical_ledger_path"])
    paths = (ledger, *(Path(f"{ledger}{suffix}") for suffix in ("-wal", "-shm")))
    return {str(path): path.read_bytes() if path.exists() else None for path in paths}


def test_cli_preflight_reports_the_plan_and_changes_no_ledger_bytes(
    interrupted: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """The default mode is the safe one: authenticate, report, touch nothing."""

    before = _ledger_namespace(interrupted)
    assert main(_cli_arguments(interrupted)) == 0
    report = json.loads(capsys.readouterr().out.splitlines()[0])

    assert report["executed"] is False
    assert report["paid_activity_executed"] is False
    assert report["dispatch_document_ids"] == [_SECOND]
    assert report["carried_document_ids"] == [_FIRST]
    assert report["committed_spend_usd"] == "3.00"
    assert report["remaining_ceiling_usd"] == "3.00"
    assert _ledger_namespace(interrupted) == before


def test_cli_refuses_a_policy_file_edited_after_issuance(
    interrupted: dict[str, Any],
) -> None:
    """A policy edited after publication cannot authorize the resume."""

    policy_path = cast(Path, interrupted["policy_path"])
    artifact = json.loads(policy_path.read_text(encoding="utf-8"))
    artifact["policy"]["approval"]["reviewer_id"] = "Someone Else"
    policy_path.write_bytes(json.dumps(artifact, indent=2, sort_keys=True).encode())

    assert main(_cli_arguments(interrupted)) == 2


def test_a_valid_policy_from_another_sitting_does_not_reproduce(
    interrupted: dict[str, Any],
) -> None:
    """The published policy is welded to this checkpoint, not merely valid.

    The on-disk artifact here is untouched and passes the frozen v2 validator;
    what it fails is the comparison against the artifact re-derived from the
    verified approval. Without that comparison a resume would accept any
    approved policy that happened to bind the same execution -- including one
    minted from a different recorded sitting.
    """

    approval_artifact = json.loads(
        cast(Path, interrupted["policy_path"]).read_text(encoding="utf-8")
    )
    approval_artifact["policy"]["approval"]["recorded_at_utc"] = "2026-01-01T00:00:00Z"

    with pytest.raises(DocumentRepairResumeError, match="does not reproduce"):
        resume_cli._require_policy_from_approval(  # pyright: ignore[reportPrivateUsage]
            approval_artifact=approval_artifact,
            purchase_policy_path=cast(Path, interrupted["policy_path"]),
        )


def test_cli_execute_carries_everything_and_contacts_nobody(
    interrupted: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Drive the whole --execute path, including the glue the preflight skips.

    The tranche is finished first, so every row is already confirmed and the
    execute path has nothing to dispatch. That is what makes it runnable
    offline: the provider seams are replaced with fixtures that would record
    any request, and the run must still produce the complete artifact set.
    """

    _first, dispatch, _context = _resume(interrupted)
    assert dispatch.dispatched == [_SECOND]

    transport = FixtureRecapFetchTransport(())
    broker = FixtureRecapFetchPurchaseBroker(())
    monkeypatch.setattr(
        resume_cli,
        "DirectCourtListenerRecapFetchConfig",
        _FixtureDirectConfig,
    )
    monkeypatch.setattr(
        resume_cli, "UrlLibRecapFetchTransport", lambda _base_url: transport
    )
    monkeypatch.setattr(
        resume_cli,
        "DirectCourtListenerRecapFetchPurchaseBroker",
        lambda *_args, **_kwargs: broker,
    )
    monkeypatch.setattr(resume_cli, "UrlLibFreeDocumentSource", _RefusingFreeSource)

    acquired_dir = cast(Path, interrupted["acquired_dir"])
    assert (
        main(
            [
                *_cli_arguments(interrupted),
                "--execute",
                "--expected-purchase-state-sha256",
                _purchase_state(interrupted),
                "--expected-confirmed-document-ids",
                _FIRST,
                _SECOND,
                "--request-ledger",
                str(
                    cast(Path, interrupted["canonical_ledger_path"]).parent / "rate.db"
                ),
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert summary["executed"] is True
    assert summary["dispatched_document_ids"] == []
    assert summary["paid_dispatch_count"] == 0
    assert summary["included_count"] == 2
    assert summary["committed_cost_usd"] == "6.00"
    assert transport.requests == []
    assert broker.requests == []

    rows = json.loads((acquired_dir / "acquired-documents.json").read_text())
    assert sorted(str(row["source_document_id"]) for row in rows) == [_FIRST, _SECOND]
    # The gate builder reads exactly these fields off each row.
    for row in rows:
        assert set(row) >= {
            "candidate_id",
            "docket_entry_number",
            "document_role",
            "source_document_id",
            "sha256",
            "byte_count",
            "path",
            "committed_cost_usd",
            "document_selector",
        }
        assert Path(str(row["path"])).exists()
    assert (acquired_dir / "repair-receipt.json").exists()
    assert (acquired_dir / "resume-run-summary.json").exists()
    assert json.loads((acquired_dir / "exclusions.json").read_text()) == []


class _FixtureDirectConfig:
    """Stand-in for the credentialed provider config, with no credentials."""

    base_url = "https://www.courtlistener.com/api/rest/v4"

    @classmethod
    def from_env(cls) -> _FixtureDirectConfig:
        return cls()

    def public_config(self) -> CourtListenerRecapFetchConfig:
        return CourtListenerRecapFetchConfig(api_token="offline-fixture-token")


def test_resume_refuses_a_confirmed_set_that_lost_a_bought_document(
    interrupted: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The human-checkable half of the rollback guard.

    The operator states which documents the halted run bought. A ledger whose
    confirmed set no longer contains one of them has lost history, and saying
    so in document ids rather than in an opaque digest is what lets a reviewer
    catch it by reading the halt record.

    Asserted on the message, not merely on a nonzero exit: without provider
    credentials this CLI path would refuse a step later for an unrelated
    reason, and a test that accepted that would pass with the pin removed.
    """

    projection = _projection(interrupted, resume=True)
    carried = read_prior_acquired_documents(
        progress_path=cast(Path, interrupted["acquired_dir"]) / "progress.jsonl",
        acquired_dir=cast(Path, interrupted["acquired_dir"]),
        execution=projection.execution,
    )
    # The interrupted tranche confirmed only _FIRST; claiming both must refuse.
    with pytest.raises(DocumentRepairResumeError, match="differ from the set"):
        plan_document_repair_resume(
            execution=projection.execution,
            policy=_policy(interrupted),
            statuses={_FIRST: "confirmed", _SECOND: "planned"},
            committed_amount_usd="3.00",
            carried_documents=carried,
            expected_confirmed_document_ids=frozenset({_FIRST, _SECOND}),
        )

    # And the same claim through the CLI surfaces that reason, not another.
    assert (
        main(
            [
                *_cli_arguments(interrupted),
                "--execute",
                "--expected-purchase-state-sha256",
                _purchase_state(interrupted),
                "--expected-confirmed-document-ids",
                _FIRST,
                _SECOND,
                "--request-ledger",
                str(
                    cast(Path, interrupted["canonical_ledger_path"]).parent / "rate.db"
                ),
            ]
        )
        == 2
    )
    assert "differ from the set" in capsys.readouterr().err


def test_cli_preflight_does_not_hand_back_a_paste_ready_pin(
    interrupted: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """A pin copied out of the ledger it authenticates proves nothing.

    The preflight must report what the ledger reads now without offering it as
    the value to feed straight back into --execute; that suggestion would make
    the one control that detects a rolled-back ledger self-satisfying.
    """

    assert main(_cli_arguments(interrupted)) == 0
    output = capsys.readouterr().out
    guidance = output.splitlines()[-1]

    assert "--execute --expected-purchase-state-sha256" not in output
    assert _purchase_state(interrupted) not in guidance
    assert "halt record" in guidance


def test_cli_refuses_an_expected_execution_pin_that_drifted(
    interrupted: dict[str, Any],
) -> None:
    """The external pins are what tie the run to the recorded sitting."""

    arguments = _cli_arguments(interrupted)
    arguments[arguments.index("--expected-execution-sha256") + 1] = "0" * 64
    assert main(arguments) == 2

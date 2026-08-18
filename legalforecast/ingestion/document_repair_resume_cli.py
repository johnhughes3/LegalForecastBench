"""Operator command that resumes one interrupted document-repair tranche.

``resume-document-repair-purchase`` is the continuation half of the issuance
flow in :mod:`legalforecast.ingestion.document_repair_purchase_cli`. It exists
because an interrupted paid run previously had no supported forward path: the
canonical ledger it left behind is the record of what was already bought, and
every way of getting past it -- deleting it, re-initializing it, re-approving
the tranche -- either destroys that record or pays for the same documents
twice.

The command has two modes and the safe one is the default. Without
``--execute`` it authenticates everything and reports the resume plan, reading
the ledger through the read-only snapshot path so no filesystem state changes
and no credential is required. With ``--execute`` it dispatches exactly the
rows the journal still calls ``planned``.

Nothing here relaxes what a purchase must prove. The recorded approval is
replayed in full by the same verifier the issuance path uses, the published
policy artifact must reproduce byte for byte from that verified approval, the
initialization receipt must still authenticate against the policy, and
``run_document_repair_execution`` still owns ordering, stop-on-unknown, and the
approved ceiling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    read_case_dev_purchase_snapshot,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchError,
    DirectCourtListenerRecapFetchConfig,
    DirectCourtListenerRecapFetchPurchaseBroker,
    UrlLibRecapFetchTransport,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudget,
    CourtListenerRequestLimits,
)
from legalforecast.ingestion.document_repair_acquire import DocumentRepairAcquirer
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecution,
    ResolvedRepairOperation,
    run_document_repair_execution,
)
from legalforecast.ingestion.document_repair_purchase_approval import (
    DocumentRepairPurchaseApprovalError,
    DocumentRepairPurchaseInputs,
    build_document_repair_purchase_resume_request,
    generate_approved_document_repair_purchase_policy,
    read_approved_document_repair_purchase_policy,
    resume_document_repair_purchase_runtime,
    verify_document_repair_purchase_resume_approval,
)
from legalforecast.ingestion.document_repair_purchase_cli import (
    add_repair_source_arguments,
)
from legalforecast.ingestion.document_repair_resume import (
    CarriedForwardDocument,
    DocumentRepairResumeError,
    DocumentRepairResumePlan,
    ResumingDocumentRepairAcquirer,
    plan_document_repair_resume,
    purchase_statuses,
    read_prior_acquired_documents,
)
from legalforecast.ingestion.free_document_downloader import UrlLibFreeDocumentSource

#: Cycle 1 live request ceiling, matching the tranche runner that produced the
#: interrupted run. A resume must not widen it.
_LIMITS = CourtListenerRequestLimits(per_minute=24, per_hour=290, per_day=1_350)

_INITIALIZATION_RECEIPT_NAME = "purchase-ledger-initialization.json"
_PROGRESS_NAME = "progress.jsonl"


def add_parsers(subparsers: Any) -> None:
    """Register the interrupted-tranche resume command."""

    resume = subparsers.add_parser(
        "resume-document-repair-purchase",
        help=(
            "Resume one interrupted document-repair tranche, dispatching only "
            "the rows its purchase journal still records as planned."
        ),
        description=(
            "Replays the owner's recorded approval in full against a tranche "
            "whose canonical ledger already exists, re-binds authority and "
            "runtime to that ledger, and continues the execution. Confirmed "
            "rows are carried forward from the bytes the interrupted run "
            "persisted and are never dispatched again; a row in any other "
            "state refuses until its outcome is recovered. Without --execute "
            "the command authenticates everything, reports the plan, and "
            "touches neither the ledger's filesystem state nor a provider."
        ),
    )
    add_repair_source_arguments(
        resume,
        canonical_ledger_help=(
            "The tranche's existing canonical ledger, holding the record of "
            "what the interrupted run already bought. It must already exist."
        ),
    )
    resume.add_argument("--controlled-private-root", type=Path, required=True)
    resume.add_argument("--checkpoint", type=Path, required=True)
    resume.add_argument("--approval-run-card", type=Path, required=True)
    resume.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help=(
            "Published v2 policy artifact. Its bytes must reproduce exactly "
            "from the verified checkpoint, so a policy swapped after issuance "
            "cannot authorize the resume."
        ),
    )
    resume.add_argument(
        "--initialization-receipt",
        type=Path,
        default=None,
        help=(
            "Immutable ledger initialization receipt. Defaults to "
            f"<canonical ledger directory>/{_INITIALIZATION_RECEIPT_NAME}."
        ),
    )
    resume.add_argument(
        "--acquired-dir",
        type=Path,
        required=True,
        help=(
            "Directory holding the interrupted run's documents and receiving "
            "any new ones."
        ),
    )
    resume.add_argument(
        "--prior-progress",
        type=Path,
        default=None,
        help=(
            "The interrupted run's append-only per-row log. Defaults to "
            f"<acquired dir>/{_PROGRESS_NAME}."
        ),
    )
    resume.add_argument(
        "--expected-request-sha256",
        required=True,
        help="External pin for the approval request the owner typed against.",
    )
    resume.add_argument(
        "--expected-execution-sha256",
        required=True,
        help="External pin for the repair execution that approval committed to.",
    )
    resume.add_argument(
        "--expected-purchase-state-sha256",
        default=None,
        help=(
            "External pin for the interrupted ledger's purchase state, as "
            "recorded when the run halted. Required with --execute. Take it "
            "from the halt record; a value read out of the ledger you are "
            "about to act on cannot detect a rollback of that same ledger."
        ),
    )
    resume.add_argument(
        "--expected-confirmed-document-ids",
        nargs="*",
        default=None,
        help=(
            "The RECAP document ids the interrupted run already bought, as "
            "named in its halt record. Required with --execute, and the "
            "ledger's confirmed set must equal it exactly. This is the "
            "purchase-state pin in a form a human can verify: a digest cannot "
            "be eyeballed against a halt record, a list of document ids can. "
            "Pass an empty list only for a run that bought nothing."
        ),
    )
    resume.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Dispatch the planned rows. Omitted, the command authenticates and "
            "reports only, and needs no provider credentials."
        ),
    )
    resume.add_argument(
        "--request-ledger",
        type=Path,
        default=None,
        help=(
            "CourtListener request-rate budget database. Required with "
            "--execute; reuse the tranche's existing one."
        ),
    )
    resume.add_argument(
        "--request-budget-max-wait-seconds",
        type=float,
        default=600.0,
    )
    resume.add_argument(
        "--poll-attempts",
        type=int,
        default=90,
        help="Queue polls per dispatched document before it is left not_attempted.",
    )
    resume.add_argument(
        "--poll-backoff-seconds",
        type=float,
        default=8.0,
    )
    resume.set_defaults(handler=run_resume)


def run_resume(args: argparse.Namespace) -> int:
    """Authenticate an interrupted tranche and, with --execute, continue it."""

    ledger_path = cast(Path, args.canonical_ledger_path)
    acquired_dir = cast(Path, args.acquired_dir)
    receipt_path = cast(Path | None, args.initialization_receipt) or (
        ledger_path.parent / _INITIALIZATION_RECEIPT_NAME
    )
    progress_path = cast(Path | None, args.prior_progress) or (
        acquired_dir / _PROGRESS_NAME
    )
    inputs = DocumentRepairPurchaseInputs(
        repair_execution_root=cast(Path, args.repair_execution_root),
        repair_manifest_path=cast(Path, args.repair_manifest),
        repair_plan_approval_path=cast(Path, args.repair_plan_approval),
        docket_snapshot_manifest_path=cast(Path, args.docket_snapshot_manifest),
        source_lineage_path=cast(Path, args.source_lineage),
        source_lineage_sha256=cast(str, args.source_lineage_sha256),
        docket_snapshot_dir=cast(Path, args.docket_snapshot_dir),
    )

    projection = build_document_repair_purchase_resume_request(
        inputs=inputs,
        cohort_policy_path=cast(Path, args.cohort_policy),
        fee_schedule_path=cast(Path, args.fee_schedule),
        canonical_ledger_path=ledger_path,
    )
    approval = verify_document_repair_purchase_resume_approval(
        controlled_private_root=cast(Path, args.controlled_private_root),
        checkpoint_path=cast(Path, args.checkpoint),
        run_card_path=cast(Path, args.approval_run_card),
        inputs=inputs,
        cohort_policy_path=cast(Path, args.cohort_policy),
        fee_schedule_path=cast(Path, args.fee_schedule),
        canonical_ledger_path=ledger_path,
    )
    execution = projection.execution
    _require_pinned_identities(
        projection_request_sha256=projection.request.request_sha256,
        approval_request_sha256=approval.request.request_sha256,
        execution_sha256=execution.execution_sha256,
        approval_execution_sha256=approval.execution_sha256,
        expected_request_sha256=cast(str, args.expected_request_sha256),
        expected_execution_sha256=cast(str, args.expected_execution_sha256),
    )
    policy = _require_policy_from_approval(
        approval_artifact=generate_approved_document_repair_purchase_policy(approval),
        purchase_policy_path=cast(Path, args.purchase_policy),
    )

    carried = read_prior_acquired_documents(
        progress_path=progress_path,
        acquired_dir=acquired_dir,
        execution=execution,
    )
    try:
        snapshot = read_case_dev_purchase_snapshot(
            ledger_path,
            policy=policy,
            initialization_receipt_path=receipt_path,
        )
    except (CaseDevPurchaseLedgerError, CaseDevPurchasePolicyError) as exc:
        raise DocumentRepairResumeError(
            f"interrupted tranche ledger does not authenticate: {exc}"
        ) from exc
    raw_confirmed = cast(list[str] | None, args.expected_confirmed_document_ids)
    expected_confirmed = None if raw_confirmed is None else frozenset(raw_confirmed)
    plan = plan_document_repair_resume(
        execution=execution,
        policy=policy,
        statuses=purchase_statuses(snapshot.operations),
        committed_amount_usd=snapshot.committed_amount_usd,
        carried_documents=carried,
        expected_confirmed_document_ids=expected_confirmed,
    )
    expected_state = cast(str | None, args.expected_purchase_state_sha256)
    if expected_state is not None and expected_state != snapshot.purchase_state_sha256:
        raise DocumentRepairResumeError(
            "purchase state differs from the pinned interrupted state; observed "
            f"{snapshot.purchase_state_sha256}"
        )
    bound = {
        "request_sha256": approval.request.request_sha256,
        "execution_sha256": execution.execution_sha256,
        "purchase_policy_sha256": policy.policy_sha256,
        "canonical_ledger_path": str(ledger_path),
        "purchase_state_sha256": snapshot.purchase_state_sha256,
        **plan.to_record(),
    }
    if not cast(bool, args.execute):
        print(
            json.dumps(
                {
                    **bound,
                    "phase": "preflight",
                    "executed": False,
                    "paid_activity_requested": False,
                    "paid_activity_executed": False,
                },
                sort_keys=True,
            )
        )
        # Deliberately not a ready-to-paste --execute line. Printing the pin
        # this preflight just derived, next to the flag that consumes it, would
        # turn the one control that detects a rolled-back ledger into a value
        # copied out of that same ledger. The digest above is labelled as what
        # it is -- observed now -- and the operator supplies the pin from the
        # halt record instead.
        print(
            "Preflight only: ledger unchanged, no provider contacted. The "
            "purchase_state_sha256 above is what this ledger reads NOW; check "
            "it, and the carried document ids, against the interrupted run's "
            "halt record before supplying them to --execute."
        )
        return 0
    if expected_state is None or expected_confirmed is None:
        raise DocumentRepairResumeError(
            "--expected-purchase-state-sha256 and --expected-confirmed-document-"
            "ids are both required with --execute. Take both from the "
            "interrupted run's halt record: a pin read out of the ledger you "
            "are about to act on cannot detect a rollback of that same ledger"
        )
    return _execute(
        args,
        execution=execution,
        plan=plan,
        carried=carried,
        bound=bound,
        expected_purchase_state_sha256=expected_state,
        expected_confirmed_document_ids=expected_confirmed,
        ledger_path=ledger_path,
        acquired_dir=acquired_dir,
        receipt_path=receipt_path,
        progress_path=progress_path,
        policy=policy,
    )


def _execute(
    args: argparse.Namespace,
    *,
    execution: DocumentRepairExecution,
    plan: DocumentRepairResumePlan,
    carried: Mapping[str, CarriedForwardDocument],
    bound: Mapping[str, object],
    expected_purchase_state_sha256: str,
    expected_confirmed_document_ids: frozenset[str],
    ledger_path: Path,
    acquired_dir: Path,
    receipt_path: Path,
    progress_path: Path,
    policy: CaseDevPurchasePolicy,
) -> int:
    """Dispatch the planned rows under the already-authenticated plan."""

    request_ledger = cast(Path | None, args.request_ledger)
    if request_ledger is None:
        raise DocumentRepairResumeError("--request-ledger is required with --execute")
    max_wait = cast(float, args.request_budget_max_wait_seconds)
    if max_wait < 0:
        raise DocumentRepairResumeError(
            "--request-budget-max-wait-seconds cannot be negative"
        )
    # Everything that can fail without touching the journal is built first, so
    # a missing credential or an exhausted request budget cannot surface after
    # the ledger lock is held. Their errors are translated here because the CLI
    # boundary does not catch bare runtime errors, and an operator one
    # environment variable short should read that rather than a traceback.
    try:
        config = DirectCourtListenerRecapFetchConfig.from_env()
        transport = UrlLibRecapFetchTransport(config.base_url)
        request_budget = CourtListenerRequestBudget(
            request_ledger,
            limits=_LIMITS,
            max_wait_seconds=max_wait,
        )
        broker = DirectCourtListenerRecapFetchPurchaseBroker(
            config,
            transport=transport,
            before_request=request_budget.reserve_cancellable,
        )
    except (CourtListenerRecapFetchError, OSError, ValueError) as exc:
        raise DocumentRepairResumeError(
            f"provider configuration or request budget is unusable: {exc}"
        ) from exc
    free_source = UrlLibFreeDocumentSource()

    resumption = resume_document_repair_purchase_runtime(
        execution=execution,
        purchase_policy_path=cast(Path, args.purchase_policy),
        cohort_policy_path=cast(Path, args.cohort_policy),
        initialization_receipt_path=receipt_path,
        expected_purchase_state_sha256=expected_purchase_state_sha256,
    )
    runtime = resumption.runtime
    journal = runtime.journal
    # Re-derive the plan from the write journal that now holds the ledger lock.
    # The plan above was read through the read-only snapshot, so anything that
    # changed between the two -- another writer, a restore, a direct edit --
    # must refuse here rather than be dispatched against a stale reading.
    locked_plan = plan_document_repair_resume(
        execution=execution,
        policy=policy,
        statuses=journal.statuses(),
        committed_amount_usd=journal.committed_amount_usd,
        carried_documents=carried,
        expected_confirmed_document_ids=expected_confirmed_document_ids,
    )
    if locked_plan != plan:
        journal.close()
        raise DocumentRepairResumeError(
            "purchase state changed between preflight and the locked journal; "
            f"preflight {plan.to_record()} now {locked_plan.to_record()}"
        )
    print(
        json.dumps(
            {**dict(bound), "phase": "bound", "executed": False}, sort_keys=True
        ),
        flush=True,
    )
    client = CourtListenerRecapFetchClient(
        config.public_config(),
        journal=journal,
        transport=transport,
        purchase_broker=broker,
        before_request=request_budget.before_request,
        poll_attempts=cast(int, args.poll_attempts),
        poll_backoff_seconds=cast(float, args.poll_backoff_seconds),
    )
    dispatch = _PersistingDispatch(
        DocumentRepairAcquirer(
            journal=journal,
            free_source=free_source,
            recap_client=client,
        ),
        acquired_dir=acquired_dir,
        progress_path=progress_path,
    )
    result = run_document_repair_execution(
        execution=execution,
        purchase_runtime=runtime,
        acquire=ResumingDocumentRepairAcquirer(
            journal=journal,
            dispatch=dispatch,
            carried_documents=carried,
        ),
        monotonic=time.monotonic,
    )
    paths = {
        **{
            document_id: str(document.path) for document_id, document in carried.items()
        },
        **dispatch.paths,
    }
    acquired_rows = [_acquired_row(row, paths) for row in result.acquired_documents]
    _write(acquired_dir / "repair-receipt.json", result.receipt.to_record())
    _write(acquired_dir / "acquired-documents.json", acquired_rows)
    _write(acquired_dir / "exclusions.json", [dict(row) for row in result.exclusions])
    summary = {
        **dict(bound),
        "executed": True,
        "authority_sha256": resumption.authority.authority_sha256,
        "initialization_id": resumption.initialization_receipt.get("initialization_id"),
        "receipt_sha256": result.receipt.receipt_sha256,
        "committed_cost_usd": result.receipt.committed_cost_usd,
        "paid_dispatch_count": broker.paid_dispatch_count,
        "dispatched_document_ids": list(dispatch.dispatched),
        "included_count": len(result.acquired_documents),
        "exclusion_count": len(result.exclusions),
        "canonical_ledger_path": str(ledger_path),
    }
    _write(acquired_dir / "resume-run-summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


class _PersistingDispatch:
    """Persist every dispatched document and outcome row as it terminates.

    The bytes must reach disk as each operation finishes rather than at the end
    of the run: an interrupted run's value survives only in what it already
    wrote, which is precisely how the document this resume carries forward was
    preserved.
    """

    def __init__(
        self,
        inner: DocumentRepairAcquirer,
        *,
        acquired_dir: Path,
        progress_path: Path,
    ) -> None:
        self.inner = inner
        self.journal = inner.journal
        self.acquired_dir = acquired_dir
        self.progress_path = progress_path
        self.paths: dict[str, str] = {}
        self.dispatched: list[str] = []

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        self.dispatched.append(operation.recap_document_id)
        result = self.inner(operation)
        row: dict[str, object] = {
            "candidate_id": operation.candidate_id,
            "docket_entry_number": operation.docket_entry_number,
            "document_role": operation.document_role,
            "document_selector": operation.document_selector,
            "source_document_id": operation.recap_document_id,
            "source": operation.route,
            "disposition": result.disposition,
            "committed_cost_usd": result.committed_cost_usd,
            "reason": result.reason,
        }
        if result.disposition == "included" and result.document_bytes is not None:
            payload = bytes(result.document_bytes)
            path = self.acquired_dir / (
                f"{operation.candidate_id}-{operation.docket_entry_number}-"
                f"{operation.document_role}-{operation.recap_document_id}.pdf"
            )
            if path.exists() and path.read_bytes() != payload:
                raise DocumentRepairResumeError(
                    f"acquired document conflicts with existing bytes: {path}"
                )
            path.write_bytes(payload)
            self.paths[operation.recap_document_id] = str(path)
            row.update(
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_count=len(payload),
                path=str(path),
            )
        with self.progress_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        return result


def _acquired_row(
    row: Mapping[str, object], paths: Mapping[str, str]
) -> dict[str, object]:
    """Project one executor-authenticated acquisition into the gate's shape."""

    document_id = str(row["source_document_id"])
    path = paths.get(document_id)
    if path is None:
        raise DocumentRepairResumeError(
            f"acquired document has no persisted path: {document_id}"
        )
    return {
        "candidate_id": row["candidate_id"],
        "docket_entry_number": row["docket_entry_number"],
        "document_role": row["document_role"],
        "document_selector": row["document_selector"],
        "source_document_id": document_id,
        "source": row["source"],
        "sha256": row["sha256"],
        "byte_count": row["byte_count"],
        "path": path,
        "committed_cost_usd": row["cost_usd"],
        "clearance_status": row["clearance_status"],
        "is_private": row["is_private"],
        "is_sealed": row["is_sealed"],
        "clearance_basis": row["clearance_basis"],
    }


def _require_pinned_identities(
    *,
    projection_request_sha256: str,
    approval_request_sha256: str,
    execution_sha256: str,
    approval_execution_sha256: str,
    expected_request_sha256: str,
    expected_execution_sha256: str,
) -> None:
    """Require the re-minted tranche to be the one the owner actually signed.

    The external pins are supplied on the command line rather than read from
    the tranche, for the same reason the source-lineage pin is: a commitment
    read from the material it commits to proves nothing.
    """

    if projection_request_sha256 != approval_request_sha256:
        raise DocumentRepairResumeError(
            "resume projection and verified approval disagree on the request"
        )
    if execution_sha256 != approval_execution_sha256:
        raise DocumentRepairResumeError(
            "resume projection and verified approval disagree on the execution"
        )
    if approval_request_sha256 != expected_request_sha256:
        raise DocumentRepairResumeError(
            "approval request digest drifted from the recorded owner approval: "
            f"{approval_request_sha256}"
        )
    if execution_sha256 != expected_execution_sha256:
        raise DocumentRepairResumeError(
            f"repair execution identity drifted: {execution_sha256}"
        )


def _require_policy_from_approval(
    *,
    approval_artifact: Mapping[str, object],
    purchase_policy_path: Path,
) -> CaseDevPurchasePolicy:
    """Require the published policy to reproduce from the verified approval.

    Re-deriving the artifact and comparing *bytes* is what welds the policy file
    to the checkpoint. Without it a resume would accept any structurally valid
    approved policy that happened to bind the execution, including one issued
    from a different recorded sitting.

    The comparison is on bytes rather than decoded mappings because the digest
    the initialization receipt commits to is a digest of file bytes. Comparing
    mappings would let a reformatted file pass this check and then fail the
    receipt comparison later, after the operator had been told the preflight
    was clean.
    """

    _artifact, policy = read_approved_document_repair_purchase_policy(
        purchase_policy_path
    )
    expected = (
        json.dumps(dict(approval_artifact), indent=2, sort_keys=True) + "\n"
    ).encode()
    if purchase_policy_path.read_bytes() != expected:
        raise DocumentRepairResumeError(
            "published purchase policy does not reproduce from the verified "
            "approval checkpoint"
        )
    return policy


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")


__all__ = [
    "DocumentRepairPurchaseApprovalError",
    "add_parsers",
    "run_resume",
]

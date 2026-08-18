"""Resume one interrupted document-repair purchase tranche exactly once.

The type-2 purchase journal was always designed to survive an interrupted run:
every intent is durably ``planned`` before anything is submitted, a dispatch is
a single ``planned -> submitted`` transition under the ledger lock, and an
ambiguous outcome blocks the next dispatch until it is reconciled. What it
never had was a verb that reads that state back and continues.

Without one, an interrupted tranche has only bad options. Its ledger cannot be
re-created, because authority is mintable only while the canonical ledger is
absent -- so "just run it again" means deleting the record of what was already
bought, which is the double-charge path. Re-approving the whole tranche spends
a scarce owner-authorization window and re-buys the rows already paid for.

This module is the third option. It changes nothing about how a purchase is
authorized or executed: :func:`run_document_repair_execution` still owns
ordering, stop-on-unknown, receipt minting and the approved ceiling. The only
new behaviour is the acquire wrapper here, which reads each paid row's journal
status before doing anything with it:

``planned``
    dispatch, through the ordinary acquirer.
``confirmed``
    carry forward the bytes the interrupted run already persisted, with no
    provider call of any kind.
anything else
    refuse, naming the recovery step. A ``submitted`` or ``unknown`` row is an
    ambiguous paid outcome; it is recovered by broker receipt or status GET
    before a resume, never by dispatching it again.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.document_repair_acquire import (
    paid_delivery_clearance_from_journal,
)
from legalforecast.ingestion.document_repair_clearance import (
    PAID_DELIVERY_CLEARANCE_BASIS,
)
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecution,
    ResolvedRepairOperation,
)

#: The only two journal statuses a resume may act on. Every other status is a
#: state a resume must not silently interpret: ``submitted`` and ``unknown``
#: are ambiguous paid outcomes, ``queued`` is a live provider operation, and
#: ``failed`` is terminal evidence that belongs in the run that produced it.
RESUMABLE_STATUSES = frozenset({"planned", "confirmed"})

_PAID_ROUTE = "pacer_purchase"


class DocumentRepairResumeError(ValueError):
    """Raised when an interrupted tranche cannot be resumed exactly once."""


@dataclass(frozen=True, slots=True)
class CarriedForwardDocument:
    """One document a previous run already bought, re-proved from its bytes."""

    source_document_id: str
    candidate_id: str
    docket_entry_number: int
    document_role: str
    document_selector: str
    path: Path
    sha256: str
    byte_count: int
    document_bytes: bytes


@dataclass(frozen=True, slots=True)
class DocumentRepairResumePlan:
    """What a resume will and will not do, derived before anything is spent."""

    dispatch_document_ids: tuple[str, ...]
    carried_document_ids: tuple[str, ...]
    committed_spend_usd: Decimal
    remaining_ceiling_usd: Decimal
    projected_dispatch_cost_usd: Decimal

    def to_record(self) -> dict[str, object]:
        """Return the operator-facing, non-authoritative resume summary."""

        return {
            "dispatch_document_ids": list(self.dispatch_document_ids),
            "carried_document_ids": list(self.carried_document_ids),
            "dispatch_document_count": len(self.dispatch_document_ids),
            "carried_document_count": len(self.carried_document_ids),
            "committed_spend_usd": _money(self.committed_spend_usd),
            "remaining_ceiling_usd": _money(self.remaining_ceiling_usd),
            "projected_dispatch_cost_usd": _money(self.projected_dispatch_cost_usd),
        }


def read_prior_acquired_documents(
    *,
    progress_path: Path,
    acquired_dir: Path,
    execution: DocumentRepairExecution,
) -> dict[str, CarriedForwardDocument]:
    """Re-prove every document an interrupted run persisted, from its bytes.

    ``progress_path`` is the interrupted run's own append-only per-row record,
    written as each operation terminated -- the one durable statement of what
    reached disk when the run died before it could write a receipt. Nothing in
    it is trusted on its own: each row must name an operation of this
    authenticated execution and agree with it on candidate, entry, role and
    selector, its file must resolve inside ``acquired_dir``, and the bytes read
    back must reproduce the digest and length the row recorded.
    """

    operations = {
        operation.recap_document_id: operation
        for operation in execution.operations
        if operation.route == _PAID_ROUTE
    }
    directory = _normalized(acquired_dir, "acquired directory")
    if directory.is_symlink() or not directory.is_dir():
        raise DocumentRepairResumeError(
            "prior acquired directory must be a real directory"
        )
    try:
        payload = read_unique_regular_file(_normalized(progress_path, "progress log"))
    except (OSError, ReviewBundleError) as exc:
        raise DocumentRepairResumeError(
            f"prior progress log is unreadable: {exc}"
        ) from exc
    carried: dict[str, CarriedForwardDocument] = {}
    for number, line in enumerate(payload.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = _row(line, number)
        if row.get("disposition") != "included":
            continue
        document_id = _text(row.get("source_document_id"), f"row {number} document id")
        operation = operations.get(document_id)
        if operation is None:
            raise DocumentRepairResumeError(
                f"prior progress row {number} is outside this execution: {document_id}"
            )
        if document_id in carried:
            raise DocumentRepairResumeError(
                f"prior progress records {document_id} as included more than once"
            )
        carried[document_id] = _carried_document(row, operation, directory, number)
    return carried


def purchase_statuses(records: Sequence[Mapping[str, object]]) -> dict[str, str]:
    """Index journal-status rows the same way for a snapshot and a live journal."""

    return {
        str(record["source_document_id"]): str(record["status"]) for record in records
    }


def plan_document_repair_resume(
    *,
    execution: DocumentRepairExecution,
    policy: CaseDevPurchasePolicy,
    statuses: Mapping[str, str],
    committed_amount_usd: str,
    carried_documents: Mapping[str, CarriedForwardDocument],
) -> DocumentRepairResumePlan:
    """Derive what a resume may dispatch, refusing anything it cannot prove.

    Journal state arrives as plain values rather than as an open journal so the
    identical derivation serves both callers: the read-only preflight, which
    reads an authenticated snapshot and must leave the ledger's filesystem
    state untouched, and the run itself, which holds the write journal.

    The ceiling is stated here rather than left to the receipt check at the end
    of the run. Both hold, but only this one can refuse *before* a provider is
    contacted, and only this one says the thing an operator needs to read: what
    the interrupted run already committed, and what is left of the approved
    maximum after it.
    """

    operations = tuple(
        operation
        for operation in execution.operations
        if operation.route == _PAID_ROUTE
    )
    if not operations:
        raise DocumentRepairResumeError(
            "resume requires a tranche with paid operations"
        )
    document_ids = tuple(operation.recap_document_id for operation in operations)
    unexpected = sorted(set(statuses) - set(document_ids))
    absent = sorted(set(document_ids) - set(statuses))
    if unexpected or absent:
        raise DocumentRepairResumeError(
            "purchase ledger rows do not match this execution exactly; "
            f"unexpected={unexpected} missing={absent}"
        )
    dispatch: list[str] = []
    carried: list[str] = []
    for document_id in document_ids:
        status = statuses[document_id]
        if status == "planned":
            dispatch.append(document_id)
        elif status == "confirmed":
            carried.append(document_id)
        else:
            raise DocumentRepairResumeError(
                f"document {document_id} is {status}; a resume dispatches only "
                "planned rows. Recover the outcome first through broker receipt "
                "or provider status, then resume"
            )
    missing_bytes = sorted(set(carried) - set(carried_documents))
    surplus_bytes = sorted(set(carried_documents) - set(carried))
    if missing_bytes or surplus_bytes:
        raise DocumentRepairResumeError(
            "carried-forward evidence does not match the confirmed ledger rows; "
            f"missing={missing_bytes} unexpected={surplus_bytes}"
        )
    budget = execution.purchase_budget
    # The journal reports spend inclusive of any opening cycle balance, while
    # the approved maximum covers this tranche alone. Subtracting the opening
    # balance is what makes the remainder comparable to it.
    committed = Decimal(committed_amount_usd) - policy.opening_committed_spend_usd
    remaining = budget.max_projected_budget - committed
    projected = budget.cost_per_document * len(dispatch)
    if projected > remaining:
        raise DocumentRepairResumeError(
            f"resume would dispatch USD {_money(projected)} against USD "
            f"{_money(remaining)} remaining of the approved maximum"
        )
    return DocumentRepairResumePlan(
        dispatch_document_ids=tuple(dispatch),
        carried_document_ids=tuple(carried),
        committed_spend_usd=committed,
        remaining_ceiling_usd=remaining,
        projected_dispatch_cost_usd=projected,
    )


@dataclass(frozen=True, slots=True)
class ResumingDocumentRepairAcquirer:
    """Dispatch planned rows; carry confirmed rows forward without a provider.

    ``journal`` is the attribute :func:`run_document_repair_execution` requires
    to be the very journal its runtime authenticated, so this wrapper cannot be
    substituted for one bound to a different ledger.
    """

    journal: CaseDevPurchaseJournal
    dispatch: Callable[[ResolvedRepairOperation], AcquiredRepairDocument]
    carried_documents: Mapping[str, CarriedForwardDocument]

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        if operation.route != _PAID_ROUTE:
            return self.dispatch(operation)
        # Read the status again here rather than trusting the plan: the plan
        # was derived before this run started, and the only statement that can
        # authorize a dispatch is the ledger's state at the moment of it.
        status = self.journal.statuses().get(operation.recap_document_id)
        if status == "planned":
            return self.dispatch(operation)
        if status == "confirmed":
            return self._carry_forward(operation)
        raise DocumentRepairResumeError(
            f"document {operation.recap_document_id} is {status}; a resume "
            "dispatches only planned rows"
        )

    def _carry_forward(
        self, operation: ResolvedRepairOperation
    ) -> AcquiredRepairDocument:
        document = self.carried_documents.get(operation.recap_document_id)
        if document is None:
            raise DocumentRepairResumeError(
                "confirmed document has no carried-forward bytes: "
                f"{operation.recap_document_id}"
            )
        evidence = self.journal.operation_evidence(operation.recap_document_id)
        if evidence is None or evidence.get("candidate_id") != operation.candidate_id:
            raise DocumentRepairResumeError(
                "confirmed document lacks exact journal operation evidence: "
                f"{operation.recap_document_id}"
            )
        clearance: tuple[str, bool, bool] | None = None
        basis: str | None = None
        if operation.paid_clearance_pending:
            clearance = paid_delivery_clearance_from_journal(
                self.journal, operation.recap_document_id
            )
            if clearance is None:
                raise DocumentRepairResumeError(
                    "confirmed document lacks post-delivery public clearance: "
                    f"{operation.recap_document_id}"
                )
            basis = PAID_DELIVERY_CLEARANCE_BASIS
        cost = evidence.get("actual_usd") or evidence.get("reservation_usd")
        return AcquiredRepairDocument(
            disposition="included",
            source_document_id=operation.recap_document_id,
            document_bytes=document.document_bytes,
            committed_cost_usd=str(cost),
            retry_count=0,
            document_selector=operation.document_selector,
            paid_clearance=clearance,
            paid_clearance_basis=basis,
        )


def _carried_document(
    row: Mapping[str, object],
    operation: ResolvedRepairOperation,
    acquired_dir: Path,
    number: int,
) -> CarriedForwardDocument:
    label = f"prior progress row {number}"
    for field, expected in (
        ("candidate_id", operation.candidate_id),
        ("docket_entry_number", operation.docket_entry_number),
        ("document_role", operation.document_role),
        ("document_selector", operation.document_selector),
        ("source", operation.route),
    ):
        if row.get(field) != expected:
            raise DocumentRepairResumeError(
                f"{label} {field} differs from the authenticated execution"
            )
    path = _normalized(Path(_text(row.get("path"), f"{label} path")), f"{label} path")
    if path.parent != acquired_dir:
        raise DocumentRepairResumeError(
            f"{label} path escapes the prior acquired directory: {path}"
        )
    digest = _digest(row.get("sha256"), f"{label} sha256")
    byte_count = row.get("byte_count")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool):
        raise DocumentRepairResumeError(f"{label} byte_count is invalid")
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise DocumentRepairResumeError(
            f"{label} document is unreadable: {exc}"
        ) from exc
    if hashlib.sha256(payload).hexdigest() != digest:
        raise DocumentRepairResumeError(
            f"{label} document differs from its recorded digest: {path}"
        )
    if len(payload) != byte_count:
        raise DocumentRepairResumeError(
            f"{label} document differs from its recorded byte count: {path}"
        )
    return CarriedForwardDocument(
        source_document_id=operation.recap_document_id,
        candidate_id=operation.candidate_id,
        docket_entry_number=operation.docket_entry_number,
        document_role=operation.document_role,
        document_selector=operation.document_selector,
        path=path,
        sha256=digest,
        byte_count=byte_count,
        document_bytes=payload,
    )


def _row(line: str, number: int) -> Mapping[str, object]:
    try:
        value: object = json.loads(line)
    except json.JSONDecodeError as exc:
        raise DocumentRepairResumeError(
            f"prior progress row {number} is not valid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise DocumentRepairResumeError(
            f"prior progress row {number} must be an object"
        )
    return cast(Mapping[str, object], value)


def _normalized(path: Path, label: str) -> Path:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise DocumentRepairResumeError(f"{label} must be an absolute normalized path")
    return path


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentRepairResumeError(f"{label} must be a nonempty string")
    return value


def _digest(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise DocumentRepairResumeError(f"{label} must be a lowercase SHA-256")
    return text


def _money(value: Decimal) -> str:
    return f"{value:.2f}"

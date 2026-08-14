"""Re-validate already-acquired repair bytes without purchasing.

The five-case pilot (`legalforecastbench-3ak.11`) executes against the pre-
hardening executor. `3ak.9` must carry that evidence onto the hardened path by
replaying byte, role, and clearance checks against stored documents. This
module never opens a journal, never calls acquire, and never contacts a
provider.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence

from legalforecast.ingestion.document_repair_executor import (
    DocumentRepairExecution,
    DocumentRepairExecutorError,
    DocumentRepairReceipt,
    require_authenticated_repair_receipt,
    require_repair_execution_binding,
    stamp_successor_acquired_documents,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentAcquisitionPlan,
    MissingDocumentSuccessorError,
    seal_missing_document_successor,
)


class DocumentRepairVerifyOnlyError(ValueError):
    """Raised when already-acquired repair bytes cannot be revalidated offline."""


def verify_document_repair_pilot_bytes(
    *,
    full_plan: MissingDocumentAcquisitionPlan,
    execution: DocumentRepairExecution,
    receipt: DocumentRepairReceipt,
    acquired_documents: Sequence[Mapping[str, object]],
    exclusions: Sequence[Mapping[str, object]],
    role_bytes_match: Callable[[str, bytes], bool],
) -> None:
    """Refuse unless stored bytes still match the hardened repair contracts.

    Missing bytes are a verify-only refusal, not a purchase trigger.
    """

    try:
        require_repair_execution_binding(full_plan, execution)
        require_authenticated_repair_receipt(
            full_plan=full_plan, execution=execution, receipt=receipt
        )
    except DocumentRepairExecutorError as exc:
        raise DocumentRepairVerifyOnlyError(str(exc)) from exc
    for document in acquired_documents:
        body = document.get("document_bytes")
        if not isinstance(body, bytes) or not body:
            raise DocumentRepairVerifyOnlyError(
                "verify-only refuses missing document_bytes; a purchase would "
                "be required"
            )
        digest = document.get("sha256")
        if not isinstance(digest, str) or hashlib.sha256(body).hexdigest() != digest:
            raise DocumentRepairVerifyOnlyError("document sha256 differs from bytes")
    try:
        if execution.scope == "full_plan":
            seal_missing_document_successor(
                plan=full_plan,
                acquired_documents=stamp_successor_acquired_documents(
                    acquired_documents, receipt
                ),
                exclusions=exclusions,
                role_bytes_match=role_bytes_match,
            )
            return
        _verify_pilot_operation_bytes(
            execution=execution,
            receipt=receipt,
            acquired_documents=acquired_documents,
            exclusions=exclusions,
            role_bytes_match=role_bytes_match,
        )
    except (DocumentRepairExecutorError, MissingDocumentSuccessorError) as exc:
        raise DocumentRepairVerifyOnlyError(str(exc)) from exc


def _verify_pilot_operation_bytes(
    *,
    execution: DocumentRepairExecution,
    receipt: DocumentRepairReceipt,
    acquired_documents: Sequence[Mapping[str, object]],
    exclusions: Sequence[Mapping[str, object]],
    role_bytes_match: Callable[[str, bytes], bool],
) -> None:
    included = {
        (
            document.get("candidate_id"),
            document.get("docket_entry_number"),
            document.get("document_selector", "main_document"),
        ): document
        for document in acquired_documents
    }
    excluded = {
        (
            record.get("candidate_id"),
            record.get("docket_entry_number"),
            record.get("document_selector", "main_document"),
        )
        for record in exclusions
    }
    if len(receipt.operation_ledger) != len(execution.operations):
        raise DocumentRepairVerifyOnlyError("repair receipt ledger is incomplete")
    for operation, row in zip(
        execution.operations, receipt.operation_ledger, strict=True
    ):
        key = operation.key
        disposition = row.get("disposition")
        if disposition == "included":
            document = included.get(key)
            if document is None:
                raise DocumentRepairVerifyOnlyError(
                    "verify-only refuses missing document_bytes; a purchase "
                    "would be required"
                )
            role = document.get("document_role")
            body = document.get("document_bytes")
            if not isinstance(role, str) or not isinstance(body, bytes):
                raise DocumentRepairVerifyOnlyError(
                    "verify-only refuses missing document_bytes; a purchase "
                    "would be required"
                )
            if not role_bytes_match(role, body):
                raise DocumentRepairVerifyOnlyError(
                    f"role-byte mismatch: {operation.candidate_id}/"
                    f"{operation.docket_entry_number} as {role}"
                )
            if document.get("clearance_status") != "cleared":
                raise DocumentRepairVerifyOnlyError(
                    "acquired document clearance_status is not cleared"
                )
            if document.get("is_private") is not False:
                raise DocumentRepairVerifyOnlyError(
                    "acquired document is_private must be false"
                )
            if document.get("is_sealed") is not False:
                raise DocumentRepairVerifyOnlyError(
                    "acquired document is_sealed must be false"
                )
        elif disposition in {"excluded", "provider_error", "unknown"}:
            if key not in excluded and key in included:
                raise DocumentRepairVerifyOnlyError(
                    "sealing evidence contradicts repair receipt disposition"
                )
            if disposition != "excluded":
                raise DocumentRepairVerifyOnlyError(
                    "repair execution has nonterminal outcomes and cannot "
                    "verify-only seal"
                )
        else:
            raise DocumentRepairVerifyOnlyError(
                "verify-only refuses missing document_bytes; a purchase would "
                "be required"
            )

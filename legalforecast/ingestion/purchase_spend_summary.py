"""Provider-free, immutable reporting for authenticated PACER billing state.

The purchase journal's reservation is an enforceable cap commitment, not a
statement of what PACER ultimately billed.  This sidecar binds the current
authenticated ledger to the two exact Cycle 1 purchase-result roots and keeps
that distinction visible in a machine-readable final summary.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    PURCHASE_SPEND_SUMMARY_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicyError,
    CaseDevPurchaseSnapshot,
    read_case_dev_purchase_snapshot,
    require_approved_case_dev_purchase_policy,
    summarize_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
    verify_purchase_ledger_initialization_lineage,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

_PURCHASE_RESULT_FIELDS = frozenset(
    {
        "acknowledge_pacer_fees",
        "attempts",
        "capability",
        "completed_purchase_count",
        "dry_run",
        "executed_purchase_count",
        "intended_purchase_count",
        "live",
        "max_projected_budget_usd",
        "projected_cost_usd",
        "quarantined_material_count",
    }
)
_PURCHASE_ATTEMPT_FIELDS = frozenset(
    {
        "candidate_id",
        "download_url",
        "fee_acknowledged",
        "pacer_fees",
        "reason",
        "source_document_id",
        "source_provider",
        "status",
    }
)


class PurchaseSpendSummaryError(ValueError):
    """Raised when a provider-free purchase-spend sidecar cannot be trusted."""


def build_purchase_spend_summary(
    *,
    purchase_policy: Path,
    cohort_policy: Path,
    purchase_ledger: Path,
    purchase_ledger_initialization_receipt: Path,
    initial_purchase_result: Path,
    replacement_purchase_result: Path,
    controlled_private_root: Path | None = None,
) -> dict[str, object]:
    """Bind current ledger billing uncertainty to both exact purchase roots.

    This never contacts CourtListener, RECAP, PACER, or any broker and never
    opens the ledger for mutation.  A non-null fee in a result root is not
    silently summarized: it must already be reconciled in the journal.  The
    published v2 policy authenticates its approved authority without a private
    replay; callers may opt into the additional private-provenance replay.
    """

    policy_bytes = _read_bytes(purchase_policy, "purchase policy")
    cohort_bytes = _read_bytes(cohort_policy, "cohort policy")
    initialization_bytes = _read_bytes(
        purchase_ledger_initialization_receipt,
        "purchase ledger initialization receipt",
    )
    try:
        policy_value = _json_object(policy_bytes, "purchase policy")
        cohort_value = _json_object(cohort_bytes, "cohort policy")
        policy = verify_case_dev_purchase_policy(policy_value)
        require_approved_case_dev_purchase_policy(
            policy, controlled_private_root=controlled_private_root
        )
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort_value)
        verify_purchase_ledger_initialization_lineage(
            purchase_ledger_initialization_receipt,
            policy=policy,
        )
        _validate_initialization_receipt_file_hashes(
            initialization_bytes,
            purchase_policy_bytes=policy_bytes,
            cohort_policy_bytes=cohort_bytes,
        )
        snapshot = read_case_dev_purchase_snapshot(
            purchase_ledger,
            policy=policy,
            controlled_private_root=controlled_private_root,
            initialization_receipt_path=purchase_ledger_initialization_receipt,
        )
        spend = summarize_case_dev_purchase_snapshot(policy=policy, snapshot=snapshot)
    except (CaseDevPurchaseLedgerError, CaseDevPurchasePolicyError, OSError) as exc:
        raise PurchaseSpendSummaryError(str(exc)) from exc

    initial = _read_purchase_result(initial_purchase_result, "initial purchase result")
    replacement = _read_purchase_result(
        replacement_purchase_result, "replacement purchase result"
    )
    result_attempts = (*initial.attempts, *replacement.attempts)
    _require_exact_attempt_coverage(snapshot, result_attempts)

    unresolved_ids = set(spend.unresolved_billing_document_ids)
    ledger_actual_ids = {
        str(operation["source_document_id"])
        for operation in snapshot.operations
        if operation.get("actual_usd") is not None
    }
    nonnull_fee_ids = {
        str(attempt["source_document_id"])
        for attempt in result_attempts
        if attempt["pacer_fees"] is not None
    }
    missing_ledger_reconciliation = nonnull_fee_ids & unresolved_ids
    if missing_ledger_reconciliation:
        raise PurchaseSpendSummaryError(
            "provider billing evidence is present in a purchase result root but "
            "the ledger has no matching authoritative reconciliation: "
            + ", ".join(sorted(missing_ledger_reconciliation))
        )

    has_billing_evidence = bool(nonnull_fee_ids | ledger_actual_ids)
    classification = (
        "actual_charge_reconciled"
        if not unresolved_ids
        else (
            "actual_charge_unavailable"
            if not has_billing_evidence
            else "actual_charge_partially_unavailable"
        )
    )
    reconciliation: dict[str, object] = {
        "classification": classification,
        "unavailable_operation_count": len(unresolved_ids),
        "unavailable_source_document_ids": sorted(unresolved_ids),
    }
    if unresolved_ids:
        reconciliation["reason"] = (
            "no authenticated provider billing evidence is present in the bound "
            "purchase result roots or purchase ledger"
            if classification == "actual_charge_unavailable"
            else (
                "authenticated provider billing evidence is present only for "
                "reconciled operations; the listed operations remain unresolved"
            )
        )

    source_commitments = {
        "purchase_policy": _file_commitment(policy_bytes),
        "cohort_policy": _file_commitment(cohort_bytes),
        "purchase_ledger_initialization_receipt": _file_commitment(
            initialization_bytes
        ),
        "purchase_ledger": _ledger_commitment(snapshot),
        "initial_purchase_result": initial.commitment,
        "replacement_purchase_result": replacement.commitment,
    }
    result: dict[str, object] = {
        "schema_version": str(PURCHASE_SPEND_SUMMARY_V1),
        "cycle_id": policy.cycle_id,
        "purchase_policy_sha256": policy.policy_sha256,
        "cohort_policy_sha256": policy.cohort_policy_sha256,
        "source_commitments": source_commitments,
        "actual_charge_reconciliation": reconciliation,
        "spend_summary": spend.to_record(),
    }
    result["summary_sha256"] = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            result,
            domain=PURCHASE_SPEND_SUMMARY_V1,
        ).digest
    )
    return result


def purchase_spend_summary_bytes(summary: Mapping[str, object]) -> bytes:
    """Return exact canonical bytes for a verified purchase-spend summary."""

    _verify_summary(summary)
    return canonical_json_bytes(
        dict(summary),
        error_type=PurchaseSpendSummaryError,
        error_message="purchase-spend summary is not canonical JSON",
    )


def write_purchase_spend_summary(path: Path, summary: Mapping[str, object]) -> str:
    """Create-once write or exact-byte resume a provider-free sidecar."""

    payload = purchase_spend_summary_bytes(summary)
    parent_fd = _open_existing_directory(path.parent, "purchase-spend output")
    try:
        try:
            existing = _read_unique_regular_at(
                parent_fd,
                path.name,
                "purchase-spend summary output",
            )
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing != payload:
                raise PurchaseSpendSummaryError(
                    "purchase-spend summary output already exists with different bytes"
                )
            return str(summary["summary_sha256"])

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise PurchaseSpendSummaryError(
                "immutable purchase-spend writes require O_NOFOLLOW"
            )
        try:
            descriptor = os.open(path.name, flags | nofollow, 0o600, dir_fd=parent_fd)
        except OSError:
            raise PurchaseSpendSummaryError(
                "unable to create purchase-spend output"
            ) from None
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.unlink(path.name, dir_fd=parent_fd)
            except OSError:
                # Preserve the primary failure; a later caller rejects residue.
                pass
            raise
        return str(summary["summary_sha256"])
    finally:
        os.close(parent_fd)


class _PurchaseResult:
    def __init__(
        self,
        *,
        attempts: tuple[Mapping[str, object], ...],
        commitment: dict[str, object],
    ) -> None:
        self.attempts = attempts
        self.commitment = commitment


def _read_purchase_result(path: Path, label: str) -> _PurchaseResult:
    payload = _read_bytes(path, label)
    record = _json_object(payload, label)
    if frozenset(record) != _PURCHASE_RESULT_FIELDS:
        raise PurchaseSpendSummaryError(f"{label} schema is unsupported")
    if (
        record["acknowledge_pacer_fees"] is not True
        or record["dry_run"] is not False
        or record["live"] is not True
        or record["capability"] != "document_level_purchase"
    ):
        raise PurchaseSpendSummaryError(
            f"{label} is not a live document-level purchase root"
        )
    attempts_value = record["attempts"]
    if not isinstance(attempts_value, list):
        raise PurchaseSpendSummaryError(f"{label} attempts must be a list")
    typed_attempts = cast(list[object], attempts_value)
    intended_purchase_count = _required_count(
        record["intended_purchase_count"], f"{label} intended purchase count"
    )
    if intended_purchase_count != len(typed_attempts):
        raise PurchaseSpendSummaryError(
            f"{label} intended purchase count is inconsistent"
        )
    attempts: list[Mapping[str, object]] = []
    ids: list[str] = []
    for raw in typed_attempts:
        if not isinstance(raw, Mapping):
            raise PurchaseSpendSummaryError(f"{label} attempt schema is unsupported")
        attempt = cast(Mapping[str, object], raw)
        if frozenset(attempt) != _PURCHASE_ATTEMPT_FIELDS:
            raise PurchaseSpendSummaryError(f"{label} attempt schema is unsupported")
        document_id = _required_text(
            attempt["source_document_id"], f"{label} document ID"
        )
        _required_text(attempt["candidate_id"], f"{label} candidate ID")
        if attempt["source_provider"] != "courtlistener.recap-fetch+pacer":
            raise PurchaseSpendSummaryError(f"{label} attempt provider is invalid")
        status = _required_text(attempt["status"], f"{label} attempt status")
        if status not in {member.value for member in CaseDevPacerPurchaseStatus}:
            raise PurchaseSpendSummaryError(f"{label} attempt status is invalid")
        if attempt["reason"] is not None and not isinstance(attempt["reason"], str):
            raise PurchaseSpendSummaryError(f"{label} attempt reason is invalid")
        if attempt["fee_acknowledged"] is not None and not isinstance(
            attempt["fee_acknowledged"], bool
        ):
            raise PurchaseSpendSummaryError(f"{label} fee acknowledgment is invalid")
        if attempt["download_url"] is not None and not isinstance(
            attempt["download_url"], str
        ):
            raise PurchaseSpendSummaryError(f"{label} download URL is invalid")
        fees = _validated_pacer_fees(attempt["pacer_fees"], label)
        if fees is not None and (
            status != CaseDevPacerPurchaseStatus.PURCHASED.value
            or attempt["fee_acknowledged"] is not True
        ):
            raise PurchaseSpendSummaryError(
                f"{label} PACER fees require an acknowledged purchased attempt"
            )
        if document_id in ids:
            raise PurchaseSpendSummaryError(f"{label} repeats a source document ID")
        ids.append(document_id)
        attempts.append(dict(attempt))
    _validate_purchase_result_summary(record, attempts, label)
    return _PurchaseResult(
        attempts=tuple(attempts),
        commitment={
            **_file_commitment(payload),
            "attempt_count": len(attempts),
            "source_document_ids_sha256": str(
                ARTIFACT_RAW_SHA256_V1.commit(
                    sorted(ids),
                    domain=PURCHASE_SPEND_SUMMARY_V1,
                ).digest
            ),
        },
    )


def _require_exact_attempt_coverage(
    snapshot: CaseDevPurchaseSnapshot,
    attempts: Sequence[Mapping[str, object]],
) -> None:
    ledger_by_id = {
        str(operation["source_document_id"]): operation
        for operation in snapshot.operations
    }
    attempts_by_id: dict[str, Mapping[str, object]] = {}
    for attempt in attempts:
        document_id = str(attempt["source_document_id"])
        if document_id in attempts_by_id:
            raise PurchaseSpendSummaryError(
                "purchase result roots overlap a source document"
            )
        attempts_by_id[document_id] = attempt
    if set(attempts_by_id) != set(ledger_by_id):
        raise PurchaseSpendSummaryError(
            "purchase result roots do not exactly cover authenticated ledger operations"
        )
    for document_id, operation in ledger_by_id.items():
        attempt = attempts_by_id[document_id]
        if attempt["candidate_id"] != operation["candidate_id"]:
            raise PurchaseSpendSummaryError(
                "purchase result candidate differs from ledger operation: "
                f"{document_id}"
            )


def _ledger_commitment(snapshot: CaseDevPurchaseSnapshot) -> dict[str, object]:
    return {
        "purchase_state_sha256": snapshot.purchase_state_sha256,
        "operations_sha256": str(
            ARTIFACT_RAW_SHA256_V1.commit(
                [dict(operation) for operation in snapshot.operations],
                domain=PURCHASE_SPEND_SUMMARY_V1,
            ).digest
        ),
        "committed_amount_usd": snapshot.committed_amount_usd,
        "operation_count": len(snapshot.operations),
    }


def _file_commitment(payload: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def _validate_initialization_receipt_file_hashes(
    receipt_payload: bytes,
    *,
    purchase_policy_bytes: bytes,
    cohort_policy_bytes: bytes,
) -> None:
    receipt = _json_object(receipt_payload, "purchase ledger initialization receipt")
    for field, source_bytes in (
        ("purchase_policy_file_sha256", purchase_policy_bytes),
        ("cohort_policy_file_sha256", cohort_policy_bytes),
    ):
        expected = f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"
        if receipt.get(field) != expected:
            raise PurchaseSpendSummaryError(
                f"initialization receipt {field} differs from current bytes"
            )


def _validate_purchase_result_summary(
    record: Mapping[str, object],
    attempts: Sequence[Mapping[str, object]],
    label: str,
) -> None:
    maximum = _money(record["max_projected_budget_usd"], f"{label} maximum budget")
    projected = _money(record["projected_cost_usd"], f"{label} projected cost")
    if projected > maximum:
        raise PurchaseSpendSummaryError(f"{label} projected cost exceeds its budget")
    executed = _required_count(
        record["executed_purchase_count"], f"{label} executed purchase count"
    )
    quarantined = _required_count(
        record["quarantined_material_count"], f"{label} quarantined material count"
    )
    completed = _required_count(
        record["completed_purchase_count"], f"{label} completed purchase count"
    )
    purchased_count = sum(
        attempt["status"] == CaseDevPacerPurchaseStatus.PURCHASED.value
        for attempt in attempts
    )
    quarantined_count = sum(
        attempt["status"] == CaseDevPacerPurchaseStatus.QUARANTINED.value
        for attempt in attempts
    )
    if (
        executed != purchased_count
        or quarantined != quarantined_count
        or completed != purchased_count + quarantined_count
    ):
        raise PurchaseSpendSummaryError(
            f"{label} completion counts are inconsistent with its attempts"
        )


def _validated_pacer_fees(value: object, label: str) -> Mapping[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PurchaseSpendSummaryError(f"{label} PACER fees must be an object")
    raw_fees = cast(Mapping[str, object], value)
    fields = {"pacer_fee_usd", "service_fee_usd", "total_usd"}
    if set(raw_fees) != fields:
        raise PurchaseSpendSummaryError(f"{label} PACER fees schema is unsupported")
    amounts = {
        field: _money(raw_fees[field], f"{label} PACER fees {field}")
        for field in fields
    }
    if amounts["pacer_fee_usd"] + amounts["service_fee_usd"] != amounts["total_usd"]:
        raise PurchaseSpendSummaryError(f"{label} PACER fee total is inconsistent")
    return {field: f"{amount:.2f}" for field, amount in amounts.items()}


def _required_count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PurchaseSpendSummaryError(f"{label} must be a non-negative integer")
    return value


def _money(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PurchaseSpendSummaryError(f"{label} must be finite decimal money")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise PurchaseSpendSummaryError(
            f"{label} must be finite decimal money"
        ) from exc
    if (
        not amount.is_finite()
        or amount < 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise PurchaseSpendSummaryError(f"{label} must be finite decimal money")
    return amount


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise PurchaseSpendSummaryError(
            f"{label} is not a unique regular file"
        ) from exc


def _open_existing_directory(path: Path, label: str) -> int:
    """Open an existing directory through no-follow components only."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise PurchaseSpendSummaryError(
            "immutable purchase-spend writes require O_NOFOLLOW and O_DIRECTORY"
        )
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    flags = os.O_RDONLY | directory | nofollow | os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(parts[0], flags)
        for component in parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise PurchaseSpendSummaryError(
            f"{label} directory must already exist without symlinks"
        ) from exc


def _read_unique_regular_at(parent_fd: int, name: str, label: str) -> bytes:
    """Read an existing immutable output from an authenticated parent fd."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise PurchaseSpendSummaryError("safe purchase-spend reads require O_NOFOLLOW")
    flags = os.O_RDONLY | os.O_NONBLOCK | nofollow | os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise PurchaseSpendSummaryError(f"{label} is not a unique regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(getattr(before, field) != getattr(after, field) for field in fields):
            raise PurchaseSpendSummaryError(f"{label} changed while read")
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise PurchaseSpendSummaryError(f"{label} changed while read")
        return payload
    except PurchaseSpendSummaryError:
        raise
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PurchaseSpendSummaryError(f"{label} cannot be safely read") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _json_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PurchaseSpendSummaryError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise PurchaseSpendSummaryError(f"{label} must be a JSON object")
    return dict(cast(Mapping[str, object], value))


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip() != value:
        raise PurchaseSpendSummaryError(f"{label} is invalid")
    return value


def _verify_summary(summary: Mapping[str, object]) -> None:
    if summary.get("schema_version") != str(PURCHASE_SPEND_SUMMARY_V1):
        raise PurchaseSpendSummaryError("purchase-spend summary schema is invalid")
    expected = summary.get("summary_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise PurchaseSpendSummaryError("purchase-spend summary hash is invalid")
    body = {key: value for key, value in summary.items() if key != "summary_sha256"}
    actual = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            body,
            domain=PURCHASE_SPEND_SUMMARY_V1,
        ).digest
    )
    if actual != expected:
        raise PurchaseSpendSummaryError("purchase-spend summary hash differs")

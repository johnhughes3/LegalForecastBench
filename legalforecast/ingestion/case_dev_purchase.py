"""Guarded case.dev PACER purchase orchestration."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Any, cast

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevClientError,
    CaseDevPurchaseOutcomeUnknownError,
    CaseDevResponseError,
    CaseDevServerError,
)
from legalforecast.ingestion.cohort_policy import verify_cohort_policy
from legalforecast.ingestion.missing_core_budget import (
    CaseDocumentCapExceededError,
    MissingCoreBudgetPlan,
    PurchaseBudgetExceededError,
)

CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION = "legalforecast.case_dev_purchase_policy.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CANONICAL_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")


class CaseDevPurchasePolicyError(ValueError):
    """Raised when the immutable cycle purchase policy is invalid or conflicts."""


class CaseDevPurchaseLedgerError(RuntimeError):
    """Raised when a purchase journal cannot make a safe state transition."""


class CaseDevPurchaseLedgerBusyError(CaseDevPurchaseLedgerError):
    """Raised when another process owns the cycle purchase journal."""


class CaseDevPurchaseReconciliationRequired(CaseDevPurchaseLedgerError):
    """Raised when an ambiguous paid request needs provider-side evidence."""


@dataclass(frozen=True, slots=True)
class CaseDevPurchasePolicy:
    """Verified immutable policy controlling one cycle's document purchases."""

    cycle_id: str
    cohort_policy_sha256: str
    canonical_ledger_path: Path
    hard_cap_usd: Decimal
    opening_committed_spend_usd: Decimal
    opening_case_committed_spend_usd: Mapping[str, Decimal]
    max_per_case_usd: Decimal
    per_document_reservation_usd: Decimal
    policy_sha256: str
    fee_schedule: Mapping[str, Any]


def generate_case_dev_purchase_policy(
    decisions: Mapping[str, object],
) -> dict[str, object]:
    """Validate and hash a pre-committed cycle document-purchase policy."""

    policy = _validated_purchase_policy(decisions)
    return {
        "schema_version": CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION,
        "policy": policy,
        "policy_sha256": _hash(policy),
    }


def verify_case_dev_purchase_policy(
    artifact: Mapping[str, object],
) -> CaseDevPurchasePolicy:
    """Verify a purchase policy artifact and return its typed immutable identity."""

    _exact_keys(
        artifact,
        {"schema_version", "policy", "policy_sha256"},
        "purchase policy artifact",
    )
    if artifact.get("schema_version") != CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION:
        raise CaseDevPurchasePolicyError("unsupported purchase policy schema")
    raw_policy = artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise CaseDevPurchasePolicyError("purchase policy must be an object")
    policy = _validated_purchase_policy(cast(Mapping[str, object], raw_policy))
    committed = _required_sha(artifact.get("policy_sha256"), "policy_sha256")
    if _hash(policy) != committed:
        raise CaseDevPurchasePolicyError("purchase policy hash does not match content")
    fee_schedule = cast(Mapping[str, Any], policy["fee_schedule"])
    return CaseDevPurchasePolicy(
        cycle_id=cast(str, policy["cycle_id"]),
        cohort_policy_sha256=cast(str, policy["cohort_policy_sha256"]),
        canonical_ledger_path=Path(cast(str, policy["canonical_ledger_path"])),
        hard_cap_usd=Decimal(cast(str, policy["hard_cap_usd"])),
        opening_committed_spend_usd=Decimal(
            cast(str, policy["opening_committed_spend_usd"])
        ),
        opening_case_committed_spend_usd={
            case_id: Decimal(amount)
            for case_id, amount in cast(
                Mapping[str, str], policy["opening_case_committed_spend_usd"]
            ).items()
        },
        max_per_case_usd=Decimal(cast(str, policy["max_per_case_usd"])),
        per_document_reservation_usd=Decimal(
            cast(str, policy["per_document_reservation_usd"])
        ),
        policy_sha256=committed,
        fee_schedule=fee_schedule,
    )


def write_case_dev_purchase_policy(
    path: str | Path,
    artifact: Mapping[str, object],
) -> Path:
    """Atomically publish an immutable verified purchase policy artifact."""

    verify_case_dev_purchase_policy(artifact)
    target = Path(path)
    payload = f"{json.dumps(artifact, indent=2, sort_keys=True)}\n".encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != payload:
            raise CaseDevPurchasePolicyError(
                "refusing to overwrite a different purchase policy artifact"
            )
        return target
    fd, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise CaseDevPurchasePolicyError(
                "purchase policy was concurrently created with different content"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def verify_case_dev_purchase_policy_cohort_binding(
    policy: CaseDevPurchasePolicy,
    cohort_artifact: Mapping[str, Any],
) -> None:
    """Require the purchase envelope to consume the frozen cohort policy caps."""

    cohort_hash = verify_cohort_policy(cohort_artifact)
    if policy.cohort_policy_sha256 != cohort_hash:
        raise CaseDevPurchasePolicyError(
            "purchase policy is bound to a different cohort policy hash"
        )
    raw_policy = cohort_artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise CaseDevPurchasePolicyError("cohort policy content must be an object")
    typed_policy = cast(Mapping[str, object], raw_policy)
    raw_purchase = typed_policy.get("purchase_policy")
    if not isinstance(raw_purchase, Mapping):
        raise CaseDevPurchasePolicyError(
            "cohort purchase policy content must be an object"
        )
    typed_purchase = cast(Mapping[str, object], raw_purchase)
    cohort_cap = _policy_money(
        typed_purchase.get("cycle_budget_usd"), "cohort cycle_budget_usd"
    )
    cohort_per_case = _policy_money(
        typed_purchase.get("max_per_case_usd"), "cohort max_per_case_usd"
    )
    if policy.hard_cap_usd != cohort_cap:
        raise CaseDevPurchasePolicyError(
            "purchase hard cap must equal the frozen cohort cycle budget"
        )
    if policy.max_per_case_usd != cohort_per_case:
        raise CaseDevPurchasePolicyError(
            "purchase per-case cap must equal the frozen cohort per-case cap"
        )


class CaseDevPurchaseJournal:
    """Single-writer durable state machine for non-idempotent paid POSTs."""

    def __init__(self, path: str | Path, *, policy: CaseDevPurchasePolicy) -> None:
        self.path = Path(path).resolve()
        if self.path != policy.canonical_ledger_path:
            raise CaseDevPurchasePolicyError(
                "purchase ledger path conflicts with canonical policy locator"
            )
        self.policy = policy
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = Path(f"{self.path}.lock")
        self._lock_fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._lock_fd)
            raise CaseDevPurchaseLedgerBusyError(
                f"cycle purchase journal is already locked: {self.path}"
            ) from exc
        try:
            if not self.path.exists():
                fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            self._connection: sqlite3.Connection = sqlite3.connect(
                self.path, isolation_level=None
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._create_schema()
            self._bind_policy()
        except BaseException:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            raise

    def __enter__(self) -> CaseDevPurchaseJournal:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._closed = True

    def plan(self, plan: MissingCoreBudgetPlan) -> None:
        """Persist every intent as planned before any submission can occur."""

        reservation = self.policy.per_document_reservation_usd
        with self._connection:
            for case_plan in plan.case_plans:
                existing_ids = {
                    str(row["source_document_id"])
                    for row in self._connection.execute(
                        """SELECT source_document_id FROM purchase_operations
                        WHERE candidate_id=?""",
                        (case_plan.candidate_id,),
                    ).fetchall()
                }
                new_ids = set(case_plan.purchase_document_ids) - existing_ids
                cumulative_reservation = self._candidate_cap_amount(
                    case_plan.candidate_id
                ) + reservation * len(new_ids)
                if cumulative_reservation > self.policy.max_per_case_usd:
                    raise CaseDevPurchaseLedgerError(
                        f"{case_plan.candidate_id} cumulative reservation exceeds "
                        "per-case cap"
                    )
                for document_id in case_plan.purchase_document_ids:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO purchase_operations(
                        source_document_id, candidate_id, reservation_usd, status)
                        VALUES (?, ?, ?, 'planned')""",
                        (document_id, case_plan.candidate_id, _money(reservation)),
                    )
                    row = self._operation(document_id)
                    assert row is not None
                    if str(row["candidate_id"]) != case_plan.candidate_id or str(
                        row["reservation_usd"]
                    ) != _money(reservation):
                        raise CaseDevPurchaseLedgerError(
                            f"purchase intent conflicts for document {document_id}"
                        )

    def require_reconciled(self) -> None:
        row = self._connection.execute(
            """SELECT source_document_id, status FROM purchase_operations
            WHERE status='submitted' OR
              (status='unknown' AND reconciliation_json IS NULL)
            ORDER BY source_document_id LIMIT 1"""
        ).fetchone()
        if row is not None:
            identity = row["source_document_id"]
            status = row["status"]
            raise CaseDevPurchaseReconciliationRequired(
                f"document {identity} has {status} paid outcome; "
                "billing receipt, statement export, support confirmation, or a "
                "counted write-off is required before any reissue"
            )

    def submit(
        self,
        document_id: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Reserve cap and durably commit submitted immediately before one POST."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._operation(document_id)
            if row is None:
                raise CaseDevPurchaseLedgerError("purchase intent was not planned")
            status = str(row["status"])
            if status == "confirmed":
                self._connection.commit()
                return False
            if status != "planned":
                raise CaseDevPurchaseReconciliationRequired(
                    f"document {document_id} has {status} paid outcome"
                )
            reservation = Decimal(str(row["reservation_usd"]))
            candidate_id = str(row["candidate_id"])
            if self._candidate_cap_amount(candidate_id) > self.policy.max_per_case_usd:
                raise CaseDevPurchaseLedgerError(
                    f"{candidate_id} cumulative reservation exceeds per-case cap"
                )
            if (
                Decimal(self.committed_amount_usd) + reservation
                > self.policy.hard_cap_usd
            ):
                raise CaseDevPurchaseLedgerError(
                    f"document {document_id} reservation would exceed cycle cap"
                )
            operation_key = str(uuid.uuid4())
            cursor = self._connection.execute(
                """UPDATE purchase_operations
                SET status='submitted', operation_key=?, response_json=?
                WHERE source_document_id=? AND status='planned'""",
                (
                    operation_key,
                    None if context is None else _canonical(context),
                    document_id,
                ),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("purchase submit transition failed")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        return True

    def confirm(
        self,
        document_id: str,
        *,
        response: Mapping[str, Any],
        fees: Mapping[str, str],
    ) -> None:
        actual = Decimal(fees["total_usd"])
        row = self._operation(document_id)
        if row is None:
            raise CaseDevPurchaseLedgerError("purchase operation is missing")
        if actual > Decimal(str(row["reservation_usd"])):
            with self._connection:
                self._connection.execute(
                    """UPDATE purchase_operations SET status='unknown',
                    actual_usd=?, response_json=?, error=?
                    WHERE source_document_id=? AND status='submitted'""",
                    (
                        _money(actual),
                        _canonical(response),
                        "provider fee exceeded verified worst-case reservation",
                        document_id,
                    ),
                )
            raise CaseDevPurchaseLedgerError(
                "provider fee exceeds the verified worst-case reservation"
            )
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='confirmed',
                actual_usd=?, response_json=?, error=NULL
                WHERE source_document_id=? AND status='submitted'""",
                (_money(actual), _canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot confirm unsubmitted purchase")

    def queue(self, document_id: str, *, response: Mapping[str, Any]) -> None:
        """Durably record the provider queue identity after the one paid POST."""

        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='queued', response_json=?,
                error=NULL WHERE source_document_id=? AND status='submitted'""",
                (_canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot queue unsubmitted purchase")

    def confirm_reserved(
        self,
        document_id: str,
        *,
        response: Mapping[str, Any],
    ) -> None:
        """Confirm delivery while retaining the worst-case reservation as spend."""

        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='confirmed',
                actual_usd=NULL, response_json=?, error=NULL
                WHERE source_document_id=? AND status='queued'""",
                (_canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot confirm unqueued purchase")

    def queued_response(self, document_id: str) -> Mapping[str, Any] | None:
        """Return durable asynchronous provider state without mutating the ledger."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) != "queued":
            return None
        response_json = row["response_json"]
        if response_json is None:
            raise CaseDevPurchaseLedgerError("queued purchase lacks provider evidence")
        return cast(Mapping[str, Any], json.loads(str(response_json)))

    def operation_evidence(self, document_id: str) -> Mapping[str, Any] | None:
        """Return the durable row needed by provider-specific resume logic."""

        row = self._operation(document_id)
        if row is None:
            return None
        response = (
            None
            if row["response_json"] is None
            else cast(Mapping[str, Any], json.loads(str(row["response_json"])))
        )
        return {
            "candidate_id": str(row["candidate_id"]),
            "status": str(row["status"]),
            "operation_key": (
                None if row["operation_key"] is None else str(row["operation_key"])
            ),
            "reservation_usd": str(row["reservation_usd"]),
            "actual_usd": (
                None if row["actual_usd"] is None else str(row["actual_usd"])
            ),
            "response": response,
            "error": None if row["error"] is None else str(row["error"]),
        }

    def fail(self, document_id: str, error: BaseException) -> None:
        with self._connection:
            self._connection.execute(
                """UPDATE purchase_operations SET status='failed', error=?
                WHERE source_document_id=? AND status IN ('submitted','queued')""",
                (f"{type(error).__name__}: {error}", document_id),
            )

    def mark_unknown(self, document_id: str, error: object) -> None:
        with self._connection:
            self._connection.execute(
                """UPDATE purchase_operations SET status='unknown', error=?
                WHERE source_document_id=? AND status IN ('submitted','queued')""",
                (str(error), document_id),
            )

    def reconcile(self, evidence: Mapping[str, object]) -> None:
        """Resolve or write off an ambiguous row using recorded provider evidence."""

        _exact_keys(
            evidence,
            {
                "source_document_id",
                "disposition",
                "source_type",
                "source_reference",
                "pacer_fees",
                "download_url",
            },
            "purchase reconciliation evidence",
        )
        document_id = _required_text(
            evidence.get("source_document_id"), "source_document_id"
        )
        disposition = _required_text(evidence.get("disposition"), "disposition")
        source_type = _required_text(evidence.get("source_type"), "source_type")
        if source_type not in {
            "billing_receipt",
            "statement_export",
            "support_confirmation",
        }:
            raise CaseDevPurchasePolicyError(
                "reconciliation source must be provider-side billing evidence"
            )
        _required_text(evidence.get("source_reference"), "source_reference")
        row = self._operation(document_id)
        reconcilable_statuses = {
            "submitted",
            "queued",
            "confirmed",
            "failed",
            "unknown",
        }
        if row is None or str(row["status"]) not in reconcilable_statuses:
            raise CaseDevPurchaseLedgerError(
                "reconciliation requires a paid or reserved operation"
            )
        reconciliation = _canonical(evidence)
        if disposition == "confirmed":
            fees = _pacer_fees(evidence.get("pacer_fees"))
            download_url = _required_text(evidence.get("download_url"), "download_url")
            actual = Decimal(fees["total_usd"])
            if actual > Decimal(str(row["reservation_usd"])):
                raise CaseDevPurchaseLedgerError(
                    "reconciled fee exceeds verified worst-case reservation"
                )
            with self._connection:
                prior_response: Mapping[str, Any] = (
                    cast(Mapping[str, Any], {})
                    if row["response_json"] is None
                    else cast(Mapping[str, Any], json.loads(str(row["response_json"])))
                )
                if prior_response.get("source_provider") == (
                    "courtlistener.recap-fetch+pacer"
                ):
                    response = {
                        **prior_response,
                        "actual_fees": dict(fees),
                        "download_url": download_url,
                    }
                else:
                    response = {
                        "acknowledgePacerFees": True,
                        "pacerFees": evidence["pacer_fees"],
                        "downloadUrl": download_url,
                    }
                self._connection.execute(
                    """UPDATE purchase_operations SET status='confirmed',
                    actual_usd=?, response_json=?, reconciliation_json=?, error=NULL
                    WHERE source_document_id=?""",
                    (
                        _money(actual),
                        _canonical(response),
                        reconciliation,
                        document_id,
                    ),
                )
            return
        if (
            evidence.get("pacer_fees") is not None
            or evidence.get("download_url") is not None
        ):
            raise CaseDevPurchasePolicyError(
                "failed or written-off reconciliation cannot assert fees or a URL"
            )
        if disposition == "failed":
            with self._connection:
                self._connection.execute(
                    """UPDATE purchase_operations SET status='failed',
                    reconciliation_json=?
                    WHERE source_document_id=? AND status IN
                    ('submitted','queued','failed','unknown')""",
                    (reconciliation, document_id),
                )
            return
        if disposition == "write_off":
            with self._connection:
                self._connection.execute(
                    """UPDATE purchase_operations SET status='unknown',
                    reconciliation_json=?
                    WHERE source_document_id=? AND status IN
                    ('submitted','queued','confirmed','failed','unknown')""",
                    (reconciliation, document_id),
                )
            return
        raise CaseDevPurchasePolicyError(
            "reconciliation disposition must be confirmed, failed, or write_off"
        )

    def statuses(self) -> dict[str, str]:
        rows = self._connection.execute(
            """SELECT source_document_id, status FROM purchase_operations
            ORDER BY source_document_id"""
        ).fetchall()
        return {str(row["source_document_id"]): str(row["status"]) for row in rows}

    def replay_attempt(
        self,
        candidate_id: str,
        document_id: str,
    ) -> CaseDevPacerPurchaseAttempt | None:
        """Reconstruct a terminal result without another provider call."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) == "planned":
            return None
        status = str(row["status"])
        if status == "confirmed":
            response_json = row["response_json"]
            if response_json is not None:
                response = cast(Mapping[str, Any], json.loads(str(response_json)))
                return _successful_attempt(candidate_id, document_id, response)
            reconciliation_json = row["reconciliation_json"]
            if reconciliation_json is None:
                raise CaseDevPurchaseLedgerError(
                    "confirmed purchase lacks durable provider evidence"
                )
            evidence = cast(Mapping[str, Any], json.loads(str(reconciliation_json)))
            fees = _pacer_fees(evidence.get("pacer_fees"))
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.PURCHASED,
                reason="confirmed_purchase_replayed_from_provider_evidence",
                pacer_fees=fees,
            )
        if status == "failed":
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                reason=str(row["error"] or "provider_evidence_confirmed_failure"),
            )
        if status == "unknown" and row["reconciliation_json"] is not None:
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.UNKNOWN,
                reason="purchase_written_off_and_counted_against_cycle_cap",
            )
        return None

    @property
    def committed_amount_usd(self) -> str:
        rows = self._connection.execute(
            """SELECT status, reservation_usd, actual_usd, response_json,
            reconciliation_json
            FROM purchase_operations"""
        ).fetchall()
        amount = Decimal("0")
        for row in rows:
            status = str(row["status"])
            if status == "confirmed":
                amount += (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal(str(row["reservation_usd"]))
                )
            elif status in {"submitted", "queued", "unknown"} or (
                status == "failed"
                and row["response_json"] is not None
                and row["reconciliation_json"] is None
            ):
                reservation = Decimal(str(row["reservation_usd"]))
                actual = (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal("0")
                )
                amount += max(reservation, actual)
        return _money(self.policy.opening_committed_spend_usd + amount)

    def _operation(self, document_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """SELECT * FROM purchase_operations WHERE source_document_id=?""",
            (document_id,),
        ).fetchone()

    def _candidate_cap_amount(self, candidate_id: str) -> Decimal:
        rows = self._connection.execute(
            """SELECT status, reservation_usd, actual_usd, response_json,
            reconciliation_json
            FROM purchase_operations WHERE candidate_id=?""",
            (candidate_id,),
        ).fetchall()
        amount = self.policy.opening_case_committed_spend_usd.get(
            candidate_id, Decimal("0")
        )
        for row in rows:
            status = str(row["status"])
            reservation = Decimal(str(row["reservation_usd"]))
            if status == "confirmed":
                amount += (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else reservation
                )
            elif status in {"planned", "submitted", "queued", "unknown"} or (
                status == "failed"
                and row["response_json"] is not None
                and row["reconciliation_json"] is None
            ):
                actual = (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal("0")
                )
                amount += max(reservation, actual)
        return amount

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS purchase_ledger (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                cycle_id TEXT NOT NULL,
                cohort_policy_sha256 TEXT NOT NULL,
                purchase_policy_sha256 TEXT NOT NULL,
                canonical_ledger_path TEXT NOT NULL,
                hard_cap_usd TEXT NOT NULL,
                opening_committed_spend_usd TEXT NOT NULL,
                max_per_case_usd TEXT NOT NULL,
                per_document_reservation_usd TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchase_operations (
                source_document_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                reservation_usd TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('planned','submitted','queued','confirmed','failed','unknown')),
                operation_key TEXT UNIQUE,
                actual_usd TEXT,
                response_json TEXT,
                error TEXT,
                reconciliation_json TEXT
            );
            """
        )
        schema_row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='purchase_operations'"
        ).fetchone()
        if schema_row is not None and "'queued'" not in str(schema_row["sql"]):
            self._migrate_purchase_operations_for_queued_state()

    def _migrate_purchase_operations_for_queued_state(self) -> None:
        """Add the asynchronous state without losing an existing cycle ledger."""

        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            ALTER TABLE purchase_operations RENAME TO purchase_operations_legacy;
            CREATE TABLE purchase_operations (
                source_document_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                reservation_usd TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('planned','submitted','queued','confirmed','failed','unknown')),
                operation_key TEXT UNIQUE,
                actual_usd TEXT,
                response_json TEXT,
                error TEXT,
                reconciliation_json TEXT
            );
            INSERT INTO purchase_operations SELECT * FROM purchase_operations_legacy;
            DROP TABLE purchase_operations_legacy;
            COMMIT;
            """
        )

    def _bind_policy(self) -> None:
        expected = (
            self.policy.cycle_id,
            self.policy.cohort_policy_sha256,
            self.policy.policy_sha256,
            str(self.policy.canonical_ledger_path),
            _money(self.policy.hard_cap_usd),
            _money(self.policy.opening_committed_spend_usd),
            _money(self.policy.max_per_case_usd),
            _money(self.policy.per_document_reservation_usd),
        )
        with self._connection:
            self._connection.execute(
                """INSERT OR IGNORE INTO purchase_ledger(
                singleton, cycle_id, cohort_policy_sha256, purchase_policy_sha256,
                canonical_ledger_path, hard_cap_usd, opening_committed_spend_usd,
                max_per_case_usd, per_document_reservation_usd)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                expected,
            )
        row = self._connection.execute(
            "SELECT * FROM purchase_ledger WHERE singleton=1"
        ).fetchone()
        assert row is not None
        actual = tuple(
            str(row[field])
            for field in (
                "cycle_id",
                "cohort_policy_sha256",
                "purchase_policy_sha256",
                "canonical_ledger_path",
                "hard_cap_usd",
                "opening_committed_spend_usd",
                "max_per_case_usd",
                "per_document_reservation_usd",
            )
        )
        if actual != expected:
            raise CaseDevPurchasePolicyError(
                "purchase journal identity conflicts with immutable cycle policy"
            )


class CaseDevPacerCapability(StrEnum):
    """Known case.dev PACER recovery behavior for selected packet documents."""

    DOCUMENT_LEVEL_PURCHASE = "document_level_purchase"
    DOCKET_LEVEL_LIVE_FETCH_ONLY = "docket_level_live_fetch_only"
    UNKNOWN = "unknown"


class CaseDevPacerPurchaseStatus(StrEnum):
    """Machine-readable status for one intended paid document recovery."""

    PLANNED_DRY_RUN = "planned_dry_run"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    CAPABILITY_BLOCKED = "capability_blocked"
    PURCHASED = "purchased"
    UNKNOWN = "unknown"
    PROVIDER_ERROR = "provider_error"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseAttempt:
    """Recorded intent and outcome for one missing core-document purchase."""

    candidate_id: str
    source_document_id: str
    status: CaseDevPacerPurchaseStatus
    reason: str | None = None
    fee_acknowledged: bool | None = None
    pacer_fees: Mapping[str, str] | None = None
    download_url: str | None = None
    source_provider: str = "case.dev+pacer"

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "reason": self.reason,
            "fee_acknowledged": self.fee_acknowledged,
            "pacer_fees": dict(self.pacer_fees) if self.pacer_fees else None,
            "download_url": self.download_url,
            "source_provider": self.source_provider,
        }


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseResult:
    """Run-level result for a guarded case.dev PACER purchase plan."""

    live: bool
    acknowledge_pacer_fees: bool
    capability: CaseDevPacerCapability
    dry_run: bool
    projected_cost_usd: str
    max_projected_budget_usd: str
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...]

    @property
    def intended_purchase_count(self) -> int:
        return len(self.attempts)

    @property
    def executed_purchase_count(self) -> int:
        return sum(
            1
            for attempt in self.attempts
            if attempt.status is CaseDevPacerPurchaseStatus.PURCHASED
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "live": self.live,
            "acknowledge_pacer_fees": self.acknowledge_pacer_fees,
            "capability": self.capability.value,
            "dry_run": self.dry_run,
            "projected_cost_usd": self.projected_cost_usd,
            "max_projected_budget_usd": self.max_projected_budget_usd,
            "intended_purchase_count": self.intended_purchase_count,
            "executed_purchase_count": self.executed_purchase_count,
            "attempts": [attempt.to_record() for attempt in self.attempts],
        }


class CaseDevPacerPurchaseClient:
    """Execute missing-core purchase plans only after explicit safety gates."""

    def __init__(
        self,
        client: CaseDevClient,
        *,
        capability: CaseDevPacerCapability = CaseDevPacerCapability.UNKNOWN,
        journal: CaseDevPurchaseJournal | None = None,
    ) -> None:
        self.client = client
        self.capability = capability
        self.journal = journal

    def execute_purchase_plan(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        """Execute or block a missing-core document purchase plan."""

        _validate_plan_budget(plan)
        if plan.dry_run:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.PLANNED_DRY_RUN,
                reason="dry_run_no_paid_request",
            )
        if not live:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="live_flag_required",
            )
        if not acknowledge_pacer_fees:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="acknowledge_pacer_fees_required",
            )
        if self.capability is not CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE:
            reason = (
                "document_level_purchase_unavailable"
                if self.capability
                is CaseDevPacerCapability.DOCKET_LEVEL_LIVE_FETCH_ONLY
                else "document_level_purchase_capability_unknown"
            )
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.CAPABILITY_BLOCKED,
                reason=reason,
            )

        if self.journal is None:
            raise CaseDevPurchaseLedgerError(
                "live document purchase requires the canonical cycle journal"
            )

        return self._execute_document_purchases(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
        )

    def _blocked_result(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
        status: CaseDevPacerPurchaseStatus,
        reason: str,
    ) -> CaseDevPacerPurchaseResult:
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(
                CaseDevPacerPurchaseAttempt(
                    candidate_id=case_plan.candidate_id,
                    source_document_id=document_id,
                    status=status,
                    reason=reason,
                )
                for case_plan in plan.case_plans
                for document_id in case_plan.purchase_document_ids
            ),
        )

    def _execute_document_purchases(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        assert self.journal is not None
        intended = tuple(
            (case_plan.candidate_id, document_id)
            for case_plan in plan.case_plans
            for document_id in case_plan.purchase_document_ids
        )
        self.journal.plan(plan)
        self.journal.require_reconciled()
        attempts: list[CaseDevPacerPurchaseAttempt] = []
        for index, (candidate_id, document_id) in enumerate(intended):
            replayed = self.journal.replay_attempt(candidate_id, document_id)
            if replayed is not None:
                attempts.append(replayed)
                continue
            if not self.journal.submit(document_id):
                replayed = self.journal.replay_attempt(candidate_id, document_id)
                if replayed is None:
                    raise CaseDevPurchaseLedgerError(
                        "purchase submit was skipped without a replayable result"
                    )
                attempts.append(replayed)
                continue
            try:
                payload = self.client.purchase_pacer_document(
                    document_id,
                    acknowledge_pacer_fees=acknowledge_pacer_fees,
                )
            except (
                CaseDevPurchaseOutcomeUnknownError,
                CaseDevServerError,
                CaseDevResponseError,
                ValueError,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                self.journal.mark_unknown(document_id, exc)
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.UNKNOWN,
                        reason="purchase_outcome_unknown",
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            except CaseDevClientError as exc:
                self.journal.fail(document_id, exc)
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                        reason=str(exc),
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="provider_error_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            try:
                attempt = _successful_attempt(candidate_id, document_id, payload)
                if attempt.pacer_fees is None:
                    raise ValueError("successful purchase is missing validated fees")
                self.journal.confirm(
                    document_id,
                    response=payload,
                    fees=attempt.pacer_fees,
                )
            except (ValueError, CaseDevPurchaseLedgerError) as exc:
                self.journal.mark_unknown(document_id, exc)
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.UNKNOWN,
                        reason="unparseable_provider_fees",
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            attempts.append(attempt)
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(attempts),
        )


def _validate_plan_budget(plan: MissingCoreBudgetPlan) -> None:
    for case_plan in plan.case_plans:
        if (
            case_plan.missing_core_document_count
            > plan.max_missing_core_documents_per_case
        ):
            raise CaseDocumentCapExceededError(
                f"{case_plan.candidate_id} has "
                f"{case_plan.missing_core_document_count} missing core documents; "
                f"cap is {plan.max_missing_core_documents_per_case}"
            )
    if plan.total_estimated_cost > plan.max_projected_budget:
        raise PurchaseBudgetExceededError(
            "projected total "
            f"${plan.total_estimated_cost_usd} exceeds budget "
            f"${plan.max_projected_budget_usd}"
        )


def _successful_attempt(
    candidate_id: str,
    document_id: str,
    payload: Mapping[str, Any],
) -> CaseDevPacerPurchaseAttempt:
    fee_acknowledged = _optional_bool(
        payload,
        "acknowledgePacerFees",
        "feeAcknowledged",
    )
    if fee_acknowledged is not True:
        raise ValueError("purchase response must confirm PACER fee acknowledgment")
    return CaseDevPacerPurchaseAttempt(
        candidate_id=candidate_id,
        source_document_id=document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        fee_acknowledged=fee_acknowledged,
        pacer_fees=_pacer_fees(payload.get("pacerFees", payload.get("pacer_fees"))),
        download_url=_optional_string(payload, "downloadUrl", "download_url", "url"),
    )


def _result(
    plan: MissingCoreBudgetPlan,
    *,
    live: bool,
    acknowledge_pacer_fees: bool,
    capability: CaseDevPacerCapability,
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...],
) -> CaseDevPacerPurchaseResult:
    return CaseDevPacerPurchaseResult(
        live=live,
        acknowledge_pacer_fees=acknowledge_pacer_fees,
        capability=capability,
        dry_run=plan.dry_run,
        projected_cost_usd=plan.total_estimated_cost_usd,
        max_projected_budget_usd=plan.max_projected_budget_usd,
        attempts=attempts,
    )


def _pacer_fees(value: object) -> Mapping[str, str]:
    if value is None:
        raise ValueError("purchase response must include PACER fees")
    if not isinstance(value, Mapping):
        raise ValueError("purchase response PACER fees must be an object")
    fees = cast(Mapping[object, object], value)
    parsed = {
        "pacer_fee_usd": _money_field(fees, "pacerFee", "pacer_fee"),
        "service_fee_usd": _money_field(fees, "serviceFee", "service_fee"),
        "total_usd": _money_field(fees, "total", "totalFee", "total_fee"),
    }
    if Decimal(parsed["pacer_fee_usd"]) + Decimal(parsed["service_fee_usd"]) != Decimal(
        parsed["total_usd"]
    ):
        raise ValueError("PACER fee total must equal PACER plus service fees")
    return parsed


def _money_field(record: Mapping[object, object], *field_names: str) -> str:
    for field_name in field_names:
        value = record.get(field_name)
        if value is not None:
            return _money(value)
    raise ValueError(f"PACER fee response is missing {field_names[0]}")


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("PACER fee values must be decimal dollar amounts") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("PACER fee values cannot be negative")
    quantized = amount.quantize(Decimal("0.01"))
    if amount != quantized:
        raise ValueError("PACER fee values cannot use sub-cent precision")
    return f"{quantized:.2f}"


def _validated_purchase_policy(
    decisions: Mapping[str, object],
) -> dict[str, object]:
    _exact_keys(
        decisions,
        {
            "cycle_id",
            "cohort_policy_sha256",
            "canonical_ledger_path",
            "hard_cap_usd",
            "opening_committed_spend_usd",
            "opening_case_committed_spend_usd",
            "max_per_case_usd",
            "per_document_reservation_usd",
            "fee_schedule",
        },
        "purchase policy",
    )
    cycle_id = _required_text(decisions.get("cycle_id"), "cycle_id")
    cohort_hash = _required_sha(
        decisions.get("cohort_policy_sha256"), "cohort_policy_sha256"
    )
    ledger_text = _required_text(
        decisions.get("canonical_ledger_path"), "canonical_ledger_path"
    )
    ledger_path = Path(ledger_text)
    if not ledger_path.is_absolute() or ledger_path != ledger_path.resolve():
        raise CaseDevPurchasePolicyError(
            "canonical_ledger_path must be an absolute normalized path"
        )
    hard_cap = _policy_money(decisions.get("hard_cap_usd"), "hard_cap_usd")
    opening_committed = _policy_money(
        decisions.get("opening_committed_spend_usd"),
        "opening_committed_spend_usd",
    )
    max_per_case = _policy_money(decisions.get("max_per_case_usd"), "max_per_case_usd")
    reservation = _policy_money(
        decisions.get("per_document_reservation_usd"),
        "per_document_reservation_usd",
    )
    if hard_cap <= 0 or max_per_case <= 0 or reservation <= 0:
        raise CaseDevPurchasePolicyError("purchase policy amounts must be positive")
    if opening_committed < 0 or opening_committed > hard_cap:
        raise CaseDevPurchasePolicyError(
            "opening committed spend must be within the cycle hard cap"
        )
    if max_per_case > hard_cap:
        raise CaseDevPurchasePolicyError("max per-case cap exceeds cycle hard cap")
    if reservation > max_per_case:
        raise CaseDevPurchasePolicyError("document reservation exceeds per-case cap")
    raw_opening_cases = decisions.get("opening_case_committed_spend_usd")
    if not isinstance(raw_opening_cases, Mapping):
        raise CaseDevPurchasePolicyError(
            "opening_case_committed_spend_usd must be an object"
        )
    typed_opening_cases = cast(Mapping[object, object], raw_opening_cases)
    opening_cases: dict[str, str] = {}
    opening_case_total = Decimal("0")
    for raw_case_id in sorted(typed_opening_cases, key=str):
        if (
            not isinstance(raw_case_id, str)
            or not raw_case_id
            or raw_case_id.strip() != raw_case_id
        ):
            raise CaseDevPurchasePolicyError(
                "opening commitment case ID must be a non-empty canonical string"
            )
        raw_amount = typed_opening_cases[raw_case_id]
        if (
            not isinstance(raw_amount, str)
            or _CANONICAL_USD.fullmatch(raw_amount) is None
        ):
            raise CaseDevPurchasePolicyError(
                "opening case commitment must be canonical nonnegative USD"
            )
        amount = Decimal(raw_amount)
        if amount > max_per_case:
            raise CaseDevPurchasePolicyError(
                "opening case commitment exceeds per-case cap"
            )
        opening_cases[raw_case_id] = raw_amount
        opening_case_total += amount
    if opening_case_total > opening_committed:
        raise CaseDevPurchasePolicyError(
            "opening case commitments exceed opening committed spend"
        )
    raw_schedule = decisions.get("fee_schedule")
    if not isinstance(raw_schedule, Mapping):
        raise CaseDevPurchasePolicyError("fee_schedule must be an object")
    schedule = cast(Mapping[str, object], raw_schedule)
    _exact_keys(
        schedule,
        {
            "source_citation",
            "verified_at_utc",
            "includes_pacer_fees",
            "includes_service_fees",
            "includes_rounding",
        },
        "fee_schedule",
    )
    source = _required_text(schedule.get("source_citation"), "source_citation")
    verified_at = _required_text(schedule.get("verified_at_utc"), "verified_at_utc")
    try:
        parsed_verified_at = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaseDevPurchasePolicyError("verified_at_utc must be ISO-8601") from exc
    if parsed_verified_at.tzinfo is None:
        raise CaseDevPurchasePolicyError("verified_at_utc must include a timezone")
    for field in (
        "includes_pacer_fees",
        "includes_service_fees",
        "includes_rounding",
    ):
        if schedule.get(field) is not True:
            raise CaseDevPurchasePolicyError(f"fee_schedule {field} must be true")
    return {
        "cycle_id": cycle_id,
        "cohort_policy_sha256": cohort_hash,
        "canonical_ledger_path": str(ledger_path),
        "hard_cap_usd": _money(hard_cap),
        "opening_committed_spend_usd": _money(opening_committed),
        "opening_case_committed_spend_usd": opening_cases,
        "max_per_case_usd": _money(max_per_case),
        "per_document_reservation_usd": _money(reservation),
        "fee_schedule": {
            "source_citation": source,
            "verified_at_utc": verified_at,
            "includes_pacer_fees": True,
            "includes_service_fees": True,
            "includes_rounding": True,
        },
    }


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise CaseDevPurchasePolicyError(
            f"{label} keys mismatch; missing={missing}, unexpected={unexpected}"
        )


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseDevPurchasePolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _required_sha(value: object, label: str) -> str:
    text = _required_text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise CaseDevPurchasePolicyError(f"{label} must be a lowercase SHA-256")
    return text


def _policy_money(value: object, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise CaseDevPurchasePolicyError(f"{label} must be decimal money") from exc
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise CaseDevPurchasePolicyError(f"{label} must have at most two decimals")
    return amount


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _optional_bool(record: Mapping[str, Any], *field_names: str) -> bool | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, bool):
            return value
    return None


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None

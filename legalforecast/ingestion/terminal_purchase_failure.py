"""Closed verifier for cap-counted terminal CourtListener purchase failures."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseJournal
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

JsonRecord = dict[str, Any]

TERMINAL_EXCLUSION_SCHEMA_VERSION = "legalforecast.ranked_reserve_terminal_exclusion.v1"
TERMINAL_RETRIEVAL_EVIDENCE_SCHEMA_VERSION = (
    "legalforecast.terminal_recap_fetch_failure_evidence.v1"
)
_COURTLISTENER_PROVIDER = "courtlistener.recap-fetch+pacer"
_TERMINAL_QUEUE_STATUSES = frozenset({3, 6, 7})
_AMBIGUOUS_LEDGER_STATUSES = frozenset({"submitted", "queued", "unknown"})
_PURCHASE_RESULT_FIELDS = frozenset(
    {
        "live",
        "acknowledge_pacer_fees",
        "capability",
        "dry_run",
        "projected_cost_usd",
        "max_projected_budget_usd",
        "intended_purchase_count",
        "executed_purchase_count",
        "quarantined_material_count",
        "completed_purchase_count",
        "attempts",
    }
)
_PURCHASE_ATTEMPT_FIELDS = frozenset(
    {
        "candidate_id",
        "source_document_id",
        "status",
        "reason",
        "fee_acknowledged",
        "pacer_fees",
        "download_url",
        "source_provider",
    }
)
_PURCHASE_RUN_CARD_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "resume",
        "record_count",
        "input_paths",
        "output_paths",
        "paid_activity_requested",
        "paid_activity_executed",
        "generated_at",
        "executed_purchase_count",
        "quarantined_material_count",
        "completed_purchase_count",
        "courtlistener_live",
        "courtlistener_physical_requests",
        "courtlistener_rate_profile",
        "courtlistener_request_budget_max_wait_seconds",
        "courtlistener_request_ledger",
        "courtlistener_reservations_this_phase",
        "courtlistener_reservations_total",
        "courtlistener_limits",
    }
)
_BUDGET_CASE_PLAN_FIELDS = frozenset(
    {
        "candidate_id",
        "purchase_document_ids",
        "missing_core_document_count",
        "estimated_purchase_count",
        "missing_core_roles",
        "estimated_cost_usd",
        "audit_only_document_count",
        "dry_run",
        "exclusion_reasons",
    }
)
_ISSUER = object()


class TerminalPurchaseFailureError(ValueError):
    """Raised when terminal paid-retrieval evidence is not fully authenticated."""


class VerifiedTerminalPurchaseFailureAuthority:
    """Opaque proof that terminal retrieval failures match the purchase journal."""

    __slots__ = (
        "_evidence_bytes",
        "_issuer",
        "_purchase_budget_plan_bytes",
        "_purchase_budget_plan_path",
        "_purchase_result_bytes",
        "_purchase_result_locator",
        "_purchase_result_path",
        "_purchase_run_card_bytes",
        "_purchase_run_card_path",
        "_terminal_exclusions_bytes",
        "purchase_journal_state_sha256",
        "purchase_result_sha256",
        "purchase_run_card_sha256",
    )

    def __init__(self) -> None:
        raise TypeError(
            "terminal purchase-failure authority is issued only by its verifier"
        )

    @property
    def evidence_records(self) -> tuple[JsonRecord, ...]:
        """Return independent copies of the closed evidence records."""

        return tuple(
            _jsonl_records(self._evidence_bytes, "terminal retrieval evidence")
        )

    @property
    def terminal_exclusions(self) -> tuple[JsonRecord, ...]:
        """Return independent copies of planner-compatible terminal records."""

        return tuple(
            _jsonl_records(
                self._terminal_exclusions_bytes,
                "verified terminal retrieval exclusions",
            )
        )

    @property
    def serialized_terminal_exclusions(self) -> bytes:
        """Return immutable planner input bytes issued by the verifier."""

        return self._terminal_exclusions_bytes


def verify_terminal_purchase_failure_authority(
    *,
    purchase_result_path: Path,
    purchase_run_card_path: Path,
    purchase_journal: CaseDevPurchaseJournal,
) -> VerifiedTerminalPurchaseFailureAuthority:
    """Safely capture and authenticate terminal statuses 3/6/7."""

    result_locator = str(purchase_result_path)
    result_path = _absolute_lexical_path(purchase_result_path)
    run_card_path = _absolute_lexical_path(purchase_run_card_path)
    try:
        purchase_result_bytes = read_unique_regular_file(result_path)
        purchase_run_card_bytes = read_unique_regular_file(run_card_path)
    except ReviewBundleError as exc:
        raise TerminalPurchaseFailureError(
            "purchase result or run card cannot be safely captured"
        ) from exc
    purchase_result = _canonical_artifact_mapping(
        purchase_result_bytes, "purchase result"
    )
    purchase_run_card = _canonical_artifact_mapping(
        purchase_run_card_bytes, "purchase run card"
    )
    input_paths = _string_list(
        purchase_run_card.get("input_paths"),
        "completed purchase run-card input paths",
    )
    budget_plan_path = _absolute_lexical_path(Path(input_paths[0]))
    try:
        purchase_budget_plan_bytes = read_unique_regular_file(budget_plan_path)
    except ReviewBundleError as exc:
        raise TerminalPurchaseFailureError(
            "purchase budget plan cannot be safely captured"
        ) from exc
    purchase_budget_plan = _canonical_artifact_mapping(
        purchase_budget_plan_bytes, "purchase budget plan"
    )
    return _verify_artifact_records(
        purchase_budget_plan=purchase_budget_plan,
        purchase_budget_plan_bytes=purchase_budget_plan_bytes,
        purchase_budget_plan_path=budget_plan_path,
        purchase_result=purchase_result,
        purchase_result_bytes=purchase_result_bytes,
        purchase_result_path=result_path,
        purchase_result_locator=result_locator,
        purchase_run_card=purchase_run_card,
        purchase_run_card_bytes=purchase_run_card_bytes,
        purchase_run_card_path=run_card_path,
        purchase_journal=purchase_journal,
    )


def _verify_artifact_records(
    *,
    purchase_budget_plan: Mapping[str, object],
    purchase_budget_plan_bytes: bytes,
    purchase_budget_plan_path: Path,
    purchase_result: Mapping[str, object],
    purchase_result_bytes: bytes,
    purchase_result_path: Path,
    purchase_result_locator: str,
    purchase_run_card: Mapping[str, object],
    purchase_run_card_bytes: bytes,
    purchase_run_card_path: Path,
    purchase_journal: CaseDevPurchaseJournal,
) -> VerifiedTerminalPurchaseFailureAuthority:
    """Verify already captured canonical source records."""

    if not _has_exact_keys(purchase_result, _PURCHASE_RESULT_FIELDS):
        raise TerminalPurchaseFailureError(
            "purchase result has an open or incomplete schema"
        )
    if not _has_exact_keys(purchase_run_card, _PURCHASE_RUN_CARD_FIELDS):
        raise TerminalPurchaseFailureError(
            "purchase run card has an open or incomplete schema"
        )
    _verify_completed_run_card(
        purchase_run_card,
        purchase_journal,
        purchase_result_locator=purchase_result_locator,
        purchase_budget_plan_path=purchase_budget_plan_path,
    )
    attempts = _attempt_records(purchase_result)
    _verify_result_summary(purchase_result, attempts, purchase_journal)
    tranche_pairs = _verify_purchase_tranche(
        purchase_budget_plan,
        attempts=attempts,
        purchase_result=purchase_result,
    )
    if purchase_run_card.get("record_count") != len(attempts):
        raise TerminalPurchaseFailureError(
            "completed purchase run-card record count differs from the result"
        )
    for name in (
        "executed_purchase_count",
        "quarantined_material_count",
        "completed_purchase_count",
    ):
        if purchase_run_card.get(name) != purchase_result.get(name):
            raise TerminalPurchaseFailureError(
                f"completed purchase run card {name} differs from the result"
            )
    if any(
        attempt.get("status") not in {"purchased", "quarantined", "provider_error"}
        for attempt in attempts
    ):
        raise TerminalPurchaseFailureError(
            "retryable or unresolved purchase attempt cannot issue terminal authority"
        )

    operations = purchase_journal.operation_records()
    ambiguous = sorted(
        _required_string(operation, "source_document_id", "purchase operation")
        for operation in operations
        if operation.get("status") in _AMBIGUOUS_LEDGER_STATUSES
    )
    if ambiguous:
        raise TerminalPurchaseFailureError(
            "terminal authority cannot be issued while the canonical ledger has "
            "submitted, queued, or unknown operations: " + ", ".join(ambiguous)
        )
    operation_by_document = _operations_by_document(operations)
    terminal_ledger_pairs = {
        (
            _required_string(operation, "candidate_id", "purchase operation"),
            document_id,
        )
        for document_id, operation in operation_by_document.items()
        if _terminal_operation_status(operation) is not None
        and (
            _required_string(operation, "candidate_id", "purchase operation"),
            document_id,
        )
        in tranche_pairs
    }
    result_provider_error_pairs = {
        (
            _required_string(attempt, "candidate_id", "purchase attempt"),
            _required_string(attempt, "source_document_id", "purchase attempt"),
        )
        for attempt in attempts
        if attempt.get("status") == "provider_error"
    }
    if result_provider_error_pairs != terminal_ledger_pairs:
        raise TerminalPurchaseFailureError(
            "purchase result statuses differ from terminal operations in its "
            "committed budget-plan tranche"
        )
    failures_by_candidate: dict[str, list[JsonRecord]] = {}
    seen_documents: set[str] = set()
    for attempt in attempts:
        candidate_id = _required_string(attempt, "candidate_id", "purchase attempt")
        document_id = _required_string(
            attempt, "source_document_id", "purchase attempt"
        )
        if document_id in seen_documents:
            raise TerminalPurchaseFailureError(
                "purchase result repeats a document attempt"
            )
        seen_documents.add(document_id)
        if attempt.get("status") != "provider_error":
            continue
        queue_status = _terminal_queue_status(attempt.get("reason"))
        operation = operation_by_document.get(document_id)
        if operation is None:
            raise TerminalPurchaseFailureError(
                f"terminal purchase document is absent from the ledger: {document_id}"
            )
        failures_by_candidate.setdefault(candidate_id, []).append(
            _verified_terminal_operation(
                attempt=attempt,
                operation=operation,
                candidate_id=candidate_id,
                document_id=document_id,
                queue_status=queue_status,
                purchase_journal=purchase_journal,
            )
        )
    if not failures_by_candidate:
        raise TerminalPurchaseFailureError(
            "purchase result contains no verified terminal CourtListener failure"
        )

    result_sha256 = _bytes_sha256(purchase_result_bytes)
    run_card_sha256 = _bytes_sha256(purchase_run_card_bytes)
    journal_sha256 = "sha256:" + purchase_journal.purchase_state_sha256()
    evidence_records = [
        {
            "schema_version": TERMINAL_RETRIEVAL_EVIDENCE_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_provider": _COURTLISTENER_PROVIDER,
            "source_stage": "purchase-missing-recap-fetch",
            "terminal": True,
            "retryable": False,
            "purchase_result_sha256": result_sha256,
            "purchase_run_card_sha256": run_card_sha256,
            "purchase_journal_state_sha256": journal_sha256,
            "failures": sorted(
                failures,
                key=lambda record: cast(str, record["source_document_id"]),
            ),
        }
        for candidate_id, failures in sorted(failures_by_candidate.items())
    ]
    evidence_bytes = _canonical_jsonl(evidence_records)
    evidence_sha256 = _bytes_sha256(evidence_bytes)
    terminal_records = [
        {
            "schema_version": TERMINAL_EXCLUSION_SCHEMA_VERSION,
            "candidate_id": cast(str, record["candidate_id"]),
            "reason": "terminal_courtlistener_recap_fetch_provider_error",
            "source_stage": "purchase-missing-recap-fetch",
            "source_artifact_sha256": evidence_sha256,
            "source_record_sha256": _canonical_sha256(record),
            "terminal": True,
            "retryable": False,
        }
        for record in evidence_records
    ]
    return _issue(
        evidence_bytes=evidence_bytes,
        terminal_exclusions_bytes=_canonical_jsonl(terminal_records),
        purchase_result_sha256=result_sha256,
        purchase_run_card_sha256=run_card_sha256,
        purchase_journal_state_sha256=journal_sha256,
        purchase_budget_plan_bytes=purchase_budget_plan_bytes,
        purchase_budget_plan_path=_result_path_text(purchase_budget_plan_path),
        purchase_result_bytes=purchase_result_bytes,
        purchase_result_locator=purchase_result_locator,
        purchase_result_path=_result_path_text(purchase_result_path),
        purchase_run_card_bytes=purchase_run_card_bytes,
        purchase_run_card_path=_result_path_text(purchase_run_card_path),
    )


def terminal_retrieval_exclusions_bytes(
    authority: VerifiedTerminalPurchaseFailureAuthority,
) -> bytes:
    """Return exact planner input emitted by the closed verifier."""

    _require_issued(authority)
    return authority.serialized_terminal_exclusions


def verified_terminal_retrieval_records(
    authority: VerifiedTerminalPurchaseFailureAuthority | None,
    *,
    purchase_journal: CaseDevPurchaseJournal,
) -> dict[str, JsonRecord]:
    """Validate authority freshness and return its exact terminal records."""

    if authority is None:
        return {}
    _require_issued(authority)
    if authority.purchase_journal_state_sha256 != (
        "sha256:" + purchase_journal.purchase_state_sha256()
    ):
        raise TerminalPurchaseFailureError(
            "terminal purchase-failure authority targets another journal state"
        )
    replayed = _verify_artifact_records(
        purchase_budget_plan=_canonical_artifact_mapping(
            authority._purchase_budget_plan_bytes,  # pyright: ignore[reportPrivateUsage]
            "captured purchase budget plan",
        ),
        purchase_budget_plan_bytes=authority._purchase_budget_plan_bytes,  # pyright: ignore[reportPrivateUsage]
        purchase_budget_plan_path=Path(authority._purchase_budget_plan_path),  # pyright: ignore[reportPrivateUsage]
        purchase_result=_canonical_artifact_mapping(
            authority._purchase_result_bytes,  # pyright: ignore[reportPrivateUsage]
            "captured purchase result",
        ),
        purchase_result_bytes=authority._purchase_result_bytes,  # pyright: ignore[reportPrivateUsage]
        purchase_result_path=Path(authority._purchase_result_path),  # pyright: ignore[reportPrivateUsage]
        purchase_result_locator=authority._purchase_result_locator,  # pyright: ignore[reportPrivateUsage]
        purchase_run_card=_canonical_artifact_mapping(
            authority._purchase_run_card_bytes,  # pyright: ignore[reportPrivateUsage]
            "captured purchase run card",
        ),
        purchase_run_card_bytes=authority._purchase_run_card_bytes,  # pyright: ignore[reportPrivateUsage]
        purchase_run_card_path=Path(authority._purchase_run_card_path),  # pyright: ignore[reportPrivateUsage]
        purchase_journal=purchase_journal,
    )
    if (
        authority._evidence_bytes != replayed._evidence_bytes  # pyright: ignore[reportPrivateUsage]
        or authority._terminal_exclusions_bytes  # pyright: ignore[reportPrivateUsage]
        != replayed._terminal_exclusions_bytes  # pyright: ignore[reportPrivateUsage]
    ):
        raise TerminalPurchaseFailureError(
            "terminal purchase-failure authority differs from verified source evidence"
        )
    records = _jsonl_records(
        authority.serialized_terminal_exclusions,
        "verified terminal retrieval exclusions",
    )
    identifiers = tuple(
        _required_string(record, "candidate_id", "verified terminal retrieval")
        for record in records
    )
    if len(identifiers) != len(set(identifiers)):
        raise TerminalPurchaseFailureError(
            "verified terminal retrieval exclusions repeat a candidate"
        )
    return dict(zip(identifiers, records, strict=True))


def _issue(
    *,
    evidence_bytes: bytes,
    terminal_exclusions_bytes: bytes,
    purchase_result_sha256: str,
    purchase_run_card_sha256: str,
    purchase_journal_state_sha256: str,
    purchase_budget_plan_bytes: bytes,
    purchase_budget_plan_path: str,
    purchase_result_bytes: bytes,
    purchase_result_locator: str,
    purchase_result_path: str,
    purchase_run_card_bytes: bytes,
    purchase_run_card_path: str,
) -> VerifiedTerminalPurchaseFailureAuthority:
    authority = object.__new__(VerifiedTerminalPurchaseFailureAuthority)
    authority._issuer = _ISSUER  # pyright: ignore[reportPrivateUsage]
    authority._evidence_bytes = evidence_bytes  # pyright: ignore[reportPrivateUsage]
    authority._terminal_exclusions_bytes = (  # pyright: ignore[reportPrivateUsage]
        terminal_exclusions_bytes
    )
    authority.purchase_result_sha256 = purchase_result_sha256
    authority.purchase_run_card_sha256 = purchase_run_card_sha256
    authority.purchase_journal_state_sha256 = purchase_journal_state_sha256
    authority._purchase_budget_plan_bytes = purchase_budget_plan_bytes  # pyright: ignore[reportPrivateUsage]
    authority._purchase_budget_plan_path = purchase_budget_plan_path  # pyright: ignore[reportPrivateUsage]
    authority._purchase_result_bytes = purchase_result_bytes  # pyright: ignore[reportPrivateUsage]
    authority._purchase_result_path = purchase_result_path  # pyright: ignore[reportPrivateUsage]
    authority._purchase_result_locator = purchase_result_locator  # pyright: ignore[reportPrivateUsage]
    authority._purchase_run_card_bytes = purchase_run_card_bytes  # pyright: ignore[reportPrivateUsage]
    authority._purchase_run_card_path = purchase_run_card_path  # pyright: ignore[reportPrivateUsage]
    return authority


def _require_issued(authority: VerifiedTerminalPurchaseFailureAuthority) -> None:
    if getattr(authority, "_issuer", None) is not _ISSUER:
        raise TerminalPurchaseFailureError(
            "terminal purchase-failure authority is not verifier-issued"
        )


def _verify_completed_run_card(
    card: Mapping[str, object],
    journal: CaseDevPurchaseJournal,
    *,
    purchase_result_locator: str,
    purchase_budget_plan_path: Path,
) -> None:
    required = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "purchase-missing-recap-fetch",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": True,
        "paid_activity_executed": True,
        "courtlistener_live": True,
    }
    if any(
        not _required_value_matches(card.get(name), value)
        for name, value in required.items()
    ):
        raise TerminalPurchaseFailureError(
            "terminal authority requires a completed purchase run card"
        )
    if not isinstance(card.get("resume"), bool):
        raise TerminalPurchaseFailureError("purchase run-card resume must be boolean")
    _count(card.get("record_count"), "purchase run-card record count")
    _count(
        card.get("courtlistener_physical_requests"),
        "CourtListener physical request count",
        positive=True,
    )
    phase = _count(
        card.get("courtlistener_reservations_this_phase"),
        "CourtListener phase reservation count",
        positive=True,
    )
    total = _count(
        card.get("courtlistener_reservations_total"),
        "CourtListener total reservation count",
        positive=True,
    )
    if phase > total:
        raise TerminalPurchaseFailureError(
            "CourtListener phase reservations exceed the durable total"
        )
    inputs = _string_list(
        card.get("input_paths"), "completed purchase run-card input paths"
    )
    outputs = _string_list(
        card.get("output_paths"), "completed purchase run-card output paths"
    )
    if (
        len(outputs) != 2
        or outputs[0] == outputs[1]
        or outputs[0] != purchase_result_locator
        or outputs[1] != str(journal.policy.canonical_ledger_path)
    ):
        raise TerminalPurchaseFailureError(
            "completed purchase run card does not bind the result and canonical ledger"
        )
    if _absolute_lexical_path(Path(inputs[0])) != purchase_budget_plan_path:
        raise TerminalPurchaseFailureError(
            "completed purchase run card does not bind the purchase budget plan"
        )
    for name in (
        "generated_at",
        "courtlistener_rate_profile",
        "courtlistener_request_ledger",
    ):
        _required_string(card, name, "completed purchase run card")
    wait = card.get("courtlistener_request_budget_max_wait_seconds")
    if (
        isinstance(wait, bool)
        or not isinstance(wait, (int, float))
        or not Decimal(str(wait)).is_finite()
        or wait < 0
    ):
        raise TerminalPurchaseFailureError(
            "CourtListener request-budget wait is invalid"
        )
    limits_value = card.get("courtlistener_limits")
    if not isinstance(limits_value, Mapping):
        raise TerminalPurchaseFailureError("CourtListener limits are invalid")
    limits = cast(Mapping[str, object], limits_value)
    if not _has_exact_keys(limits, frozenset({"per_minute", "per_hour", "per_day"})):
        raise TerminalPurchaseFailureError("CourtListener limits are invalid")
    for name, value in limits.items():
        _count(value, f"CourtListener {name} limit", positive=True)


def _attempt_records(result: Mapping[str, object]) -> tuple[JsonRecord, ...]:
    values = result.get("attempts")
    if not isinstance(values, list) or not values:
        raise TerminalPurchaseFailureError("purchase result attempts are empty")
    attempts: list[JsonRecord] = []
    for value in cast(list[object], values):
        if not isinstance(value, Mapping):
            raise TerminalPurchaseFailureError(
                "purchase attempt has an open or incomplete schema"
            )
        attempt = cast(Mapping[str, object], value)
        if not _has_exact_keys(attempt, _PURCHASE_ATTEMPT_FIELDS):
            raise TerminalPurchaseFailureError(
                "purchase attempt has an open or incomplete schema"
            )
        if attempt.get("source_provider") != _COURTLISTENER_PROVIDER:
            raise TerminalPurchaseFailureError(
                "purchase attempt is not a CourtListener RECAP Fetch attempt"
            )
        attempts.append(dict(cast(Mapping[str, Any], attempt)))
    return tuple(attempts)


def _verify_result_summary(
    result: Mapping[str, object],
    attempts: Sequence[JsonRecord],
    journal: CaseDevPurchaseJournal,
) -> None:
    required = {
        "live": True,
        "acknowledge_pacer_fees": True,
        "capability": "document_level_purchase",
        "dry_run": False,
    }
    if any(
        not _required_value_matches(result.get(name), value)
        for name, value in required.items()
    ):
        raise TerminalPurchaseFailureError(
            "terminal authority requires an executed document-level purchase result"
        )
    projected = _money(result.get("projected_cost_usd"), "projected cost")
    maximum = _money(result.get("max_projected_budget_usd"), "maximum projected budget")
    if projected < 0 or maximum < 0 or projected > maximum:
        raise TerminalPurchaseFailureError(
            "purchase result projected cost exceeds its maximum budget"
        )
    if maximum > journal.policy.hard_cap_usd:
        raise TerminalPurchaseFailureError(
            "purchase result maximum budget exceeds the canonical hard cap"
        )
    intended = _count(result.get("intended_purchase_count"), "intended purchase count")
    executed = _count(result.get("executed_purchase_count"), "executed purchase count")
    quarantined = _count(
        result.get("quarantined_material_count"), "quarantined material count"
    )
    completed = _count(
        result.get("completed_purchase_count"), "completed purchase count"
    )
    purchased_count = sum(attempt.get("status") == "purchased" for attempt in attempts)
    quarantine_count = sum(
        attempt.get("status") == "quarantined" for attempt in attempts
    )
    if intended != len(attempts):
        raise TerminalPurchaseFailureError(
            "purchase result intended count differs from its attempts"
        )
    if (
        executed != purchased_count
        or quarantined != quarantine_count
        or completed != purchased_count + quarantine_count
    ):
        raise TerminalPurchaseFailureError(
            "purchase result completion counts differ from its attempts"
        )


def _verify_purchase_tranche(
    budget_plan: Mapping[str, object],
    *,
    attempts: Sequence[JsonRecord],
    purchase_result: Mapping[str, object],
) -> set[tuple[str, str]]:
    """Bind every result attempt to the budget plan named by the run card."""

    if budget_plan.get("dry_run") is not False:
        raise TerminalPurchaseFailureError(
            "terminal authority requires a non-dry-run purchase budget plan"
        )
    case_plans_value = budget_plan.get("case_plans")
    if not isinstance(case_plans_value, list) or not case_plans_value:
        raise TerminalPurchaseFailureError(
            "purchase budget plan contains no closed case tranche"
        )
    planned_pairs: set[tuple[str, str]] = set()
    total_cost = Decimal("0.00")
    for raw_case_plan in cast(list[object], case_plans_value):
        if not isinstance(raw_case_plan, Mapping):
            raise TerminalPurchaseFailureError(
                "purchase budget plan case tranche is invalid"
            )
        case_plan = cast(Mapping[str, object], raw_case_plan)
        if not _has_exact_keys(case_plan, _BUDGET_CASE_PLAN_FIELDS):
            raise TerminalPurchaseFailureError(
                "purchase budget plan case tranche has an open or incomplete schema"
            )
        candidate_id = _required_string(
            case_plan, "candidate_id", "purchase budget case plan"
        )
        documents = _string_list(
            case_plan.get("purchase_document_ids"),
            "purchase budget case-plan document IDs",
        )
        count = _count(
            case_plan.get("missing_core_document_count"),
            "purchase budget case-plan document count",
            positive=True,
        )
        estimated_count = _count(
            case_plan.get("estimated_purchase_count"),
            "purchase budget case-plan estimated count",
            positive=True,
        )
        if count != len(documents) or estimated_count != len(documents):
            raise TerminalPurchaseFailureError(
                "purchase budget case-plan counts differ from its documents"
            )
        if (
            case_plan.get("dry_run") is not False
            or case_plan.get("exclusion_reasons") != []
        ):
            raise TerminalPurchaseFailureError(
                "purchase budget case plan is dry-run or excluded"
            )
        total_cost += _money(
            case_plan.get("estimated_cost_usd"),
            "purchase budget case-plan estimated cost",
        )
        for document_id in documents:
            pair = (candidate_id, document_id)
            if pair in planned_pairs:
                raise TerminalPurchaseFailureError(
                    "purchase budget plan repeats a candidate/document operation"
                )
            planned_pairs.add(pair)
    attempted_pairs = {
        (
            _required_string(attempt, "candidate_id", "purchase attempt"),
            _required_string(attempt, "source_document_id", "purchase attempt"),
        )
        for attempt in attempts
    }
    if attempted_pairs != planned_pairs or len(attempted_pairs) != len(attempts):
        raise TerminalPurchaseFailureError(
            "purchase result must cover its committed budget-plan tranche exactly once"
        )
    if (
        _money(
            budget_plan.get("total_estimated_cost_usd"),
            "purchase budget total estimated cost",
        )
        != total_cost
        or _money(
            purchase_result.get("projected_cost_usd"), "purchase result projected cost"
        )
        != total_cost
    ):
        raise TerminalPurchaseFailureError(
            "purchase result cost differs from its committed budget-plan tranche"
        )
    if _money(
        budget_plan.get("max_projected_budget_usd"),
        "purchase budget maximum projected budget",
    ) != _money(
        purchase_result.get("max_projected_budget_usd"),
        "purchase result maximum projected budget",
    ):
        raise TerminalPurchaseFailureError(
            "purchase result maximum differs from its committed budget plan"
        )
    return planned_pairs


def _operations_by_document(
    operations: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for operation in operations:
        document_id = _required_string(
            operation, "source_document_id", "purchase operation"
        )
        if document_id in result:
            raise TerminalPurchaseFailureError(
                "canonical purchase ledger repeats a document operation"
            )
        result[document_id] = operation
    return result


def _terminal_queue_status(reason: object) -> int:
    if not isinstance(reason, str):
        raise TerminalPurchaseFailureError(
            "provider error lacks a nonretryable CourtListener queue status"
        )
    patterns = (
        r"recap_fetch_status_([0-9]{1,3})",
        r"CourtListenerRecapFetchError: RECAP Fetch terminal queue status "
        r"([0-9]{1,3})",
    )
    match = next(
        (
            candidate
            for pattern in patterns
            if (candidate := re.fullmatch(pattern, reason))
        ),
        None,
    )
    if match is None:
        raise TerminalPurchaseFailureError(
            "provider error lacks a nonretryable CourtListener queue status"
        )
    status = int(match.group(1))
    if status not in _TERMINAL_QUEUE_STATUSES:
        raise TerminalPurchaseFailureError(
            "provider error is not a nonretryable CourtListener queue status 3, 6, or 7"
        )
    return status


def _verified_terminal_operation(
    *,
    attempt: Mapping[str, Any],
    operation: Mapping[str, Any],
    candidate_id: str,
    document_id: str,
    queue_status: int,
    purchase_journal: CaseDevPurchaseJournal,
) -> JsonRecord:
    if operation.get("candidate_id") != candidate_id:
        raise TerminalPurchaseFailureError(
            "terminal attempt candidate differs from the canonical ledger"
        )
    if operation.get("source_document_id") != document_id:
        raise TerminalPurchaseFailureError(
            "terminal attempt document differs from the canonical ledger"
        )
    if operation.get("status") != "failed":
        raise TerminalPurchaseFailureError(
            "terminal attempt does not bind a failed canonical ledger operation"
        )
    expected_error = (
        "CourtListenerRecapFetchError: RECAP Fetch terminal queue status "
        f"{queue_status}"
    )
    if operation.get("error") != expected_error:
        raise TerminalPurchaseFailureError(
            "terminal attempt status differs from the canonical ledger failure"
        )
    if any(
        attempt.get(name) is not None
        for name in ("fee_acknowledged", "pacer_fees", "download_url")
    ):
        raise TerminalPurchaseFailureError(
            "terminal provider error unexpectedly claims purchase material"
        )
    reservation = _money(
        operation.get("reservation_usd"), "terminal operation reservation"
    )
    if reservation != purchase_journal.policy.per_document_reservation_usd:
        raise TerminalPurchaseFailureError(
            "terminal operation reservation differs from the purchase policy"
        )
    operation_key = _uuid(operation.get("operation_key"), "terminal operation key")
    response_value = operation.get("response")
    if not isinstance(response_value, Mapping):
        raise TerminalPurchaseFailureError(
            "terminal operation lacks a durable provider response"
        )
    response = cast(Mapping[str, Any], response_value)
    if response.get("source_provider") != _COURTLISTENER_PROVIDER or response.get(
        "reservation_usd"
    ) != _money_text(reservation):
        raise TerminalPurchaseFailureError(
            "terminal operation response differs from its provider reservation"
        )
    queue_id = _positive_decimal(
        response.get("queue_id"), "terminal operation queue ID"
    )
    reservation_id = _required_string(
        response, "reservation_id", "terminal operation response"
    )
    if operation.get("reconciliation") is not None or not _operation_counts(operation):
        raise TerminalPurchaseFailureError(
            "terminal operation is not retained as cap-counted state"
        )
    if (
        _money(
            purchase_journal.candidate_committed_amount_usd(candidate_id),
            "candidate committed amount",
        )
        < reservation
    ):
        raise TerminalPurchaseFailureError(
            "terminal operation reservation is absent from the candidate cap"
        )
    return {
        "source_document_id": document_id,
        "queue_status": queue_status,
        "failure_reason": f"recap_fetch_status_{queue_status}",
        "ledger_status": "failed",
        "operation_key": operation_key,
        "reservation_id": reservation_id,
        "queue_id": queue_id,
        "reservation_usd": _money_text(reservation),
        "cap_counted": True,
        "cap_counted_usd": _money_text(reservation),
        "ledger_operation_sha256": _canonical_sha256(dict(operation)),
    }


def _operation_counts(operation: Mapping[str, Any]) -> bool:
    return (
        operation.get("status") == "failed"
        and operation.get("response") is not None
        and operation.get("reconciliation") is None
    )


def _terminal_operation_status(operation: Mapping[str, Any]) -> int | None:
    if not _operation_counts(operation):
        return None
    response = operation.get("response")
    if not isinstance(response, Mapping):
        return None
    response_record = cast(Mapping[str, Any], response)
    if response_record.get("source_provider") != _COURTLISTENER_PROVIDER:
        return None
    error = operation.get("error")
    if not isinstance(error, str):
        return None
    for status in _TERMINAL_QUEUE_STATUSES:
        if error == (
            f"CourtListenerRecapFetchError: RECAP Fetch terminal queue status {status}"
        ):
            return status
    return None


def _canonical_artifact_mapping(
    artifact_bytes: bytes, source: str
) -> Mapping[str, object]:
    try:
        decoded: object = json.loads(
            artifact_bytes,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"unsupported JSON numeric constant {value}")
            ),
        )
        if not isinstance(decoded, dict):
            raise ValueError("artifact root is not an object")
        record = cast(dict[str, object], decoded)
        canonical = (
            json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise TerminalPurchaseFailureError(f"{source} is not canonical JSON") from exc
    if artifact_bytes != canonical:
        raise TerminalPurchaseFailureError(f"{source} is not exact canonical JSON")
    return record


def _result_path_text(path: Path) -> str:
    """Return the absolute lexical path format emitted by acquisition run cards."""

    return str(_absolute_lexical_path(path))


def _absolute_lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _has_exact_keys(record: Mapping[str, object], expected: frozenset[str]) -> bool:
    return len(record) == len(expected) and all(name in expected for name in record)


def _required_value_matches(actual: object, expected: object) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    return actual == expected


def _string_list(value: object, source: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TerminalPurchaseFailureError(f"{source} are invalid")
    raw = cast(list[object], value)
    if not all(isinstance(item, str) and item for item in raw) or len(raw) != len(
        set(cast(list[str], raw))
    ):
        raise TerminalPurchaseFailureError(f"{source} are invalid")
    return tuple(cast(list[str], raw))


def _required_string(record: Mapping[str, Any], name: str, source: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value or value.strip() != value:
        raise TerminalPurchaseFailureError(
            f"{source} {name} must be a canonical non-empty string"
        )
    return value


def _count(value: object, source: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        qualifier = "positive" if positive else "nonnegative"
        raise TerminalPurchaseFailureError(f"{source} must be a {qualifier} integer")
    return value


def _money(value: object, source: str) -> Decimal:
    if isinstance(value, bool):
        raise TerminalPurchaseFailureError(f"{source} must be decimal money")
    try:
        amount = Decimal(str(value))
        valid = amount.is_finite() and amount == amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise TerminalPurchaseFailureError(f"{source} must use finite cents") from exc
    if not valid:
        raise TerminalPurchaseFailureError(f"{source} must use finite cents")
    return amount


def _money_text(value: Decimal) -> str:
    return f"{value:.2f}"


def _uuid(value: object, source: str) -> str:
    if not isinstance(value, str):
        raise TerminalPurchaseFailureError(f"{source} must be a canonical UUID")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError) as exc:
        raise TerminalPurchaseFailureError(
            f"{source} must be a canonical UUID"
        ) from exc
    if str(parsed) != value:
        raise TerminalPurchaseFailureError(f"{source} must be a canonical UUID")
    return value


def _positive_decimal(value: object, source: str) -> str:
    if not isinstance(value, str) or not value.isdigit() or value.startswith("0"):
        raise TerminalPurchaseFailureError(
            f"{source} must be a canonical positive decimal"
        )
    return value


def _jsonl_records(payload: bytes, source: str) -> list[JsonRecord]:
    if payload and not payload.endswith(b"\n"):
        raise TerminalPurchaseFailureError(f"{source} lacks a terminal newline")
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TerminalPurchaseFailureError(
                f"{source} line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise TerminalPurchaseFailureError(
                f"{source} line {line_number} must be an object"
            )
        records.append(cast(JsonRecord, value))
    return records


def _canonical_jsonl(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(
        json.dumps(
            dict(record),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
        for record in records
    )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode()
    return _bytes_sha256(payload)


def _bytes_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

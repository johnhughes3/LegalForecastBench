"""Verify provider-free inputs for a direct CourtListener discovery snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    FirecrawlAttempt,
)


class CourtListenerSnapshotMaterializationError(ValueError):
    """Raised when discovery evidence cannot support an immutable snapshot."""


@dataclass(frozen=True, slots=True)
class VerifiedRawArtifact:
    candidate_id: str
    path: Path
    content: bytes
    sha256: str
    byte_count: int
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class VerifiedCourtListenerDiscovery:
    run_card_sha256: str
    cycle_hash: str
    batch_digest: str
    eligibility_anchor: date
    query_terms: tuple[str, ...]
    screened_cases: tuple[Mapping[str, Any], ...]
    exclusions: tuple[Mapping[str, Any], ...]
    search_pages: tuple[Mapping[str, Any], ...]
    raw_artifacts: tuple[VerifiedRawArtifact, ...]
    stage_commitment: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _HybridFirecrawlEvidence:
    batch_id: str
    run_id: str
    receipt_count: int
    run_reserved_credits: int
    run_reported_credits: int
    successful_attempts: Mapping[int, FirecrawlAttempt]
    terminal_unsuccessful_attempts: Mapping[str, FirecrawlAttempt]


_SHA256 = re.compile(r"[0-9a-f]{64}")
_OUTPUT_NAMES = (
    "screened_cases",
    "exclusions",
    "raw_html_directory",
    "summary",
    "search_pages",
    "raw_artifacts",
)
_FIRECRAWL_AUDIT_SCHEMA = "legalforecast.budgeted_courtlistener_html_audit.v1"
_FIRECRAWL_RECEIPT_SCHEMA = "legalforecast.firecrawl_docket_html_source_receipt.v1"
_FIRECRAWL_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "docket_html_source",
        "batch_digest",
        "firecrawl_run_id",
        "firecrawl_target_id",
        "firecrawl_attempt_id",
        "request_url",
        "reserved_credits",
        "reported_credits",
        "proxy_used",
        "target_http_status",
        "artifact_sha256",
        "artifact_byte_count",
        "authorized_at",
        "completed_at",
    }
)
_FIRECRAWL_COMMON_AUDIT_KEYS = (
    "abandoned_docket_count",
    "attempt_status_counts",
    "batch_id",
    "config_digest",
    "credit_cap",
    "docket_html_source",
    "failure_code_counts",
    "firecrawl_audit_schema_version",
    "firecrawl_cycle_credit_cap",
    "firecrawl_max_credits_per_new_candidate",
    "firecrawl_metered_activity_executed",
    "firecrawl_metered_activity_requested",
    "firecrawl_run_status",
    "firecrawl_source_receipt_count",
    "max_attempts_per_target",
    "pacer_paid_activity_executed",
    "pacer_paid_activity_requested",
    "provider_unavailable_docket_count",
    "proxy",
    "remaining_authorization",
    "reported_credits",
    "reserved_credits",
    "reserved_credits_per_attempt",
    "run_id",
    "run_reported_credits",
    "run_reserved_credits",
    "source",
    "successful_docket_count",
    "target_count",
    "unavailable_docket_count",
)


def verify_courtlistener_discovery(
    *,
    run_card_path: Path,
    expected_run_card_sha256: str,
    expected_cycle_hash: str,
    expected_batch_id: str,
    expected_batch_digest: str,
    cycle_policy: Mapping[str, object],
    batch_config: Mapping[str, object],
    firecrawl_attempts: Sequence[FirecrawlAttempt],
    firecrawl_run_summary: Mapping[str, object] | None,
    durable_candidate_observations: Sequence[CandidateObservation] = (),
) -> VerifiedCourtListenerDiscovery:
    """Verify one completed, saturated, hash-bound direct discovery run."""

    if _SHA256.fullmatch(expected_run_card_sha256) is None:
        raise CourtListenerSnapshotMaterializationError(
            "expected discovery run-card SHA-256 must be 64 lowercase hex characters"
        )
    run_card_bytes = _read_regular_file(run_card_path, "discovery run card")
    actual_run_card_sha256 = hashlib.sha256(run_card_bytes).hexdigest()
    if actual_run_card_sha256 != expected_run_card_sha256:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card SHA-256 mismatch"
        )
    run_card = _json_object(run_card_bytes, "discovery run card")
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "discover-courtlistener"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card is not a completed execution"
        )
    if run_card.get("cycle_hash") != expected_cycle_hash:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card cycle hash mismatch"
        )
    if run_card.get("batch_digest") != expected_batch_digest:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card batch digest mismatch"
        )
    output_paths_value = run_card.get("output_paths")
    if not isinstance(output_paths_value, list):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks the required transcript and artifact outputs"
        )
    output_path_items = cast(list[object], output_paths_value)
    if len(output_path_items) != 6:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks the required transcript and artifact outputs"
        )
    output_paths = tuple(
        _absolute_path(value, f"discovery output {index}")
        for index, value in enumerate(output_path_items, start=1)
    )
    paths = dict(zip(_OUTPUT_NAMES, output_paths, strict=True))
    commitments_value = run_card.get("output_commitments")
    if not isinstance(commitments_value, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks output commitments"
        )
    commitments = cast(Mapping[str, object], commitments_value)
    committed_files = {
        name: paths[name]
        for name in (
            "screened_cases",
            "exclusions",
            "summary",
            "search_pages",
            "raw_artifacts",
        )
    }
    if set(commitments) != set(committed_files):
        raise CourtListenerSnapshotMaterializationError(
            "discovery output commitment set is incomplete"
        )
    for name, path in committed_files.items():
        _verify_file_commitment(path, commitments[name], name)

    screened_cases = tuple(_jsonl(paths["screened_cases"], "screened cases"))
    exclusions = tuple(_jsonl(paths["exclusions"], "discovery exclusions"))
    search_pages = tuple(_jsonl(paths["search_pages"], "search-page transcript"))
    raw_manifest = tuple(_jsonl(paths["raw_artifacts"], "raw-artifact manifest"))
    summary = _json_object(
        _read_regular_file(paths["summary"], "discovery summary"),
        "discovery summary",
    )
    firecrawl_evidence = _validate_discovery_activity(
        run_card=run_card,
        summary=summary,
        expected_batch_id=expected_batch_id,
        batch_config=batch_config,
        firecrawl_attempts=firecrawl_attempts,
        firecrawl_run_summary=firecrawl_run_summary,
    )

    anchor = _validate_frozen_identity(
        run_card=run_card,
        summary=summary,
        cycle_policy=cycle_policy,
        batch_config=batch_config,
    )
    accepted_ids = _accepted_ids(screened_cases, anchor=anchor)
    excluded_ids = _excluded_ids(
        exclusions,
        firecrawl_evidence=firecrawl_evidence,
        durable_candidate_observations=durable_candidate_observations,
    )
    if accepted_ids & excluded_ids:
        raise CourtListenerSnapshotMaterializationError(
            "a candidate appears in both screened cases and exclusions"
        )
    outcome_ids = accepted_ids | excluded_ids
    query_terms = _string_list(summary.get("query_terms"), "summary query_terms")
    transcript_ids = _validate_transcript(
        search_pages,
        summary=summary,
        query_terms=query_terms,
    )
    if transcript_ids != outcome_ids:
        raise CourtListenerSnapshotMaterializationError(
            "discovery transcript candidates do not exactly match terminal outcomes"
        )
    _validate_summary_counts(
        run_card=run_card,
        summary=summary,
        accepted_count=len(accepted_ids),
        excluded_count=len(excluded_ids),
        transcript_count=len(transcript_ids),
    )
    artifacts = _verify_raw_artifacts(
        raw_html_directory=paths["raw_html_directory"],
        manifest=raw_manifest,
        retrieved_at=_string(run_card.get("generated_at"), "run-card generated_at"),
        accepted_ids=accepted_ids,
        exclusions=exclusions,
        outcome_ids=outcome_ids,
        expected_batch_digest=expected_batch_digest,
        firecrawl_evidence=firecrawl_evidence,
    )
    stage_commitment = {
        "schema_version": ("legalforecast.courtlistener_discovery_snapshot_inputs.v1"),
        "discovery_run_card_sha256": actual_run_card_sha256,
        "cycle_hash": expected_cycle_hash,
        "batch_digest": expected_batch_digest,
        "batch_id": expected_batch_id,
        "eligibility_anchor": anchor.isoformat(),
        "source_saturated": True,
        "accepted_case_count": len(accepted_ids),
        "excluded_case_count": len(excluded_ids),
        "candidate_count": len(outcome_ids),
        "output_commitments": json.loads(_canonical_json(commitments)),
    }
    if firecrawl_evidence is not None:
        stage_commitment.update(
            {
                "docket_html_source": "firecrawl",
                "firecrawl_batch_id": firecrawl_evidence.batch_id,
                "firecrawl_run_id": firecrawl_evidence.run_id,
                "firecrawl_source_receipt_count": (firecrawl_evidence.receipt_count),
                "firecrawl_run_reserved_credits": (
                    firecrawl_evidence.run_reserved_credits
                ),
                "firecrawl_run_reported_credits": (
                    firecrawl_evidence.run_reported_credits
                ),
                "pacer_paid_activity_requested": False,
                "pacer_paid_activity_executed": False,
            }
        )
    return VerifiedCourtListenerDiscovery(
        run_card_sha256=actual_run_card_sha256,
        cycle_hash=expected_cycle_hash,
        batch_digest=expected_batch_digest,
        eligibility_anchor=anchor,
        query_terms=query_terms,
        screened_cases=screened_cases,
        exclusions=exclusions,
        search_pages=search_pages,
        raw_artifacts=artifacts,
        stage_commitment=stage_commitment,
    )


def _validate_discovery_activity(
    *,
    run_card: Mapping[str, Any],
    summary: Mapping[str, Any],
    expected_batch_id: str,
    batch_config: Mapping[str, object],
    firecrawl_attempts: Sequence[FirecrawlAttempt],
    firecrawl_run_summary: Mapping[str, object] | None,
) -> _HybridFirecrawlEvidence | None:
    hybrid = any(
        record.get("docket_html_source") == "firecrawl"
        or "firecrawl_metered_activity_requested" in record
        for record in (run_card, summary, batch_config)
    )
    if not hybrid:
        if (
            run_card.get("paid_activity_requested") is not False
            or run_card.get("paid_activity_executed") is not False
        ):
            raise CourtListenerSnapshotMaterializationError(
                "discovery run card is not a completed noncharging execution"
            )
        if firecrawl_attempts or firecrawl_run_summary is not None:
            raise CourtListenerSnapshotMaterializationError(
                "legacy discovery unexpectedly supplied Firecrawl ledger evidence"
            )
        return None

    if (
        run_card.get("docket_html_source") != "firecrawl"
        or summary.get("docket_html_source") != "firecrawl"
        or batch_config.get("docket_html_source") != "firecrawl"
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery source identity is incomplete"
        )
    if run_card.get("paid_activity_requested") is not True:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery must record metered activity as requested"
        )
    for record in (run_card, summary):
        if (
            record.get("pacer_paid_activity_requested") is not False
            or record.get("pacer_paid_activity_executed") is not False
        ):
            raise CourtListenerSnapshotMaterializationError(
                "PACER paid activity is forbidden in a Firecrawl discovery snapshot"
            )
    for key in _FIRECRAWL_COMMON_AUDIT_KEYS:
        if key not in run_card or run_card.get(key) != summary.get(key):
            raise CourtListenerSnapshotMaterializationError(
                f"Firecrawl discovery audit mismatch: {key}"
            )
    if run_card.get("firecrawl_audit_schema_version") != _FIRECRAWL_AUDIT_SCHEMA:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery audit schema mismatch"
        )
    if (
        run_card.get("source") != "courtlistener-rest-firecrawl-html"
        or run_card.get("proxy") != "basic"
        or run_card.get("max_attempts_per_target") != 3
        or run_card.get("firecrawl_max_credits_per_new_candidate") != 3
        or run_card.get("reserved_credits_per_attempt") != 1
        or run_card.get("firecrawl_metered_activity_requested") is not True
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery authority is not the bounded basic-proxy profile"
        )

    run_id = _string(summary.get("firecrawl_run_id"), "Firecrawl run ID")
    if (
        run_card.get("run_id") != run_id
        or summary.get("run_id") != run_id
        or batch_config.get("firecrawl_run_id") != run_id
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery run identity mismatch"
        )
    if firecrawl_run_summary is None:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery lacks durable run-ledger evidence"
        )
    ledger_summary = dict(firecrawl_run_summary)
    expected_ledger_keys = {
        "run_id",
        "batch_id",
        "status",
        "config_digest",
        "credit_cap",
        "reserved_credits_per_attempt",
        "reserved_credits",
        "reported_credits",
        "run_reserved_credits",
        "run_reported_credits",
        "remaining_authorization",
        "attempt_status_counts",
        "failure_code_counts",
    }
    if set(ledger_summary) != expected_ledger_keys:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable run-ledger schema mismatch"
        )
    if ledger_summary.get("batch_id") != expected_batch_id:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable run belongs to a different batch"
        )
    ledger_to_audit = {
        "run_id": "run_id",
        "status": "firecrawl_run_status",
        "config_digest": "config_digest",
        "credit_cap": "credit_cap",
        "reserved_credits_per_attempt": "reserved_credits_per_attempt",
        "reserved_credits": "reserved_credits",
        "reported_credits": "reported_credits",
        "run_reserved_credits": "run_reserved_credits",
        "run_reported_credits": "run_reported_credits",
        "remaining_authorization": "remaining_authorization",
        "attempt_status_counts": "attempt_status_counts",
        "failure_code_counts": "failure_code_counts",
    }
    for ledger_key, audit_key in ledger_to_audit.items():
        if ledger_summary.get(ledger_key) != run_card.get(audit_key):
            raise CourtListenerSnapshotMaterializationError(
                f"Firecrawl durable run-ledger mismatch: {ledger_key}"
            )
    config_digest = _string(
        run_card.get("config_digest"), "Firecrawl run config digest"
    )
    if _SHA256.fullmatch(config_digest) is None:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl run config digest is invalid"
        )
    cap = _positive_int(summary.get("firecrawl_credit_cap"), "Firecrawl credit cap")
    if cap > 45_000 or any(
        value != cap
        for value in (
            batch_config.get("firecrawl_credit_cap"),
            run_card.get("firecrawl_cycle_credit_cap"),
            run_card.get("credit_cap"),
        )
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery credit cap does not match the frozen <=45000 cap"
        )

    target_count = _nonnegative_int(
        run_card.get("target_count"), "Firecrawl target count"
    )
    successful_count = _nonnegative_int(
        run_card.get("successful_docket_count"), "Firecrawl successful docket count"
    )
    unavailable_count = _nonnegative_int(
        run_card.get("unavailable_docket_count"), "Firecrawl unavailable docket count"
    )
    provider_unavailable_count = _nonnegative_int(
        run_card.get("provider_unavailable_docket_count"),
        "Firecrawl provider-unavailable docket count",
    )
    abandoned_count = _nonnegative_int(
        run_card.get("abandoned_docket_count"), "Firecrawl abandoned docket count"
    )
    receipt_count = _nonnegative_int(
        run_card.get("firecrawl_source_receipt_count"),
        "Firecrawl source receipt count",
    )
    run_reserved = _nonnegative_int(
        run_card.get("run_reserved_credits"), "Firecrawl run reserved credits"
    )
    run_reported = _nonnegative_int(
        run_card.get("run_reported_credits"), "Firecrawl run reported credits"
    )
    cycle_reserved = _nonnegative_int(
        run_card.get("reserved_credits"), "Firecrawl cycle reserved credits"
    )
    cycle_reported = _nonnegative_int(
        run_card.get("reported_credits"), "Firecrawl cycle reported credits"
    )
    remaining = _nonnegative_int(
        run_card.get("remaining_authorization"),
        "Firecrawl remaining authorization",
    )
    executed = run_reserved > 0
    if (
        run_card.get("firecrawl_metered_activity_executed") is not executed
        or run_card.get("paid_activity_executed") is not executed
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl metered-execution evidence does not match reserved credits"
        )
    if (
        successful_count != receipt_count
        or unavailable_count != provider_unavailable_count + abandoned_count
        or target_count != successful_count + unavailable_count
        or run_reserved < target_count
        or run_reserved > target_count * 3
        or run_reported > run_reserved
        or cycle_reserved < run_reserved
        or cycle_reported < run_reported
        or cycle_reported > cycle_reserved
        or remaining != cap - cycle_reserved
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery credit and target accounting does not reconcile"
        )

    attempt_counts = _count_mapping(
        run_card.get("attempt_status_counts"), "Firecrawl attempt status counts"
    )
    if set(attempt_counts) - {
        "succeeded",
        "target_error",
        "interrupted",
        "provider_error",
        "transport_error",
    }:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery contains a nonterminal attempt status"
        )
    if (
        sum(attempt_counts.values()) != run_reserved
        or attempt_counts.get("succeeded", 0) != successful_count
        or attempt_counts.get("target_error", 0) != provider_unavailable_count
        or attempt_counts.get("interrupted", 0) != abandoned_count
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl attempt statuses do not reconcile with terminal targets"
        )
    failure_counts = _count_mapping(
        run_card.get("failure_code_counts"), "Firecrawl failure code counts"
    )
    if run_card.get("firecrawl_run_status") not in {"active", "completed"}:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl discovery run status is not materializable"
        )
    attempts_by_id: dict[int, FirecrawlAttempt] = {}
    attempts_by_target: dict[str, list[FirecrawlAttempt]] = {}
    for attempt in firecrawl_attempts:
        if attempt.run_id != run_id or attempt.attempt_id in attempts_by_id:
            raise CourtListenerSnapshotMaterializationError(
                "Firecrawl durable attempt lineage is invalid"
            )
        attempts_by_id[attempt.attempt_id] = attempt
        attempts_by_target.setdefault(attempt.target_id, []).append(attempt)
    if len(attempts_by_id) != run_reserved or len(attempts_by_target) != target_count:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable attempts do not reconcile with credit and target counts"
        )
    durable_status_counts: dict[str, int] = {}
    durable_failure_counts: dict[str, int] = {}
    for attempt in attempts_by_id.values():
        durable_status_counts[attempt.status] = (
            durable_status_counts.get(attempt.status, 0) + 1
        )
        if attempt.failure_code is not None:
            durable_failure_counts[attempt.failure_code] = (
                durable_failure_counts.get(attempt.failure_code, 0) + 1
            )
    if (
        durable_status_counts != attempt_counts
        or durable_failure_counts != failure_counts
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable attempt audit counts do not reconcile"
        )

    successful_attempts: dict[int, FirecrawlAttempt] = {}
    terminal_unsuccessful_attempts: dict[str, FirecrawlAttempt] = {}
    for target_id, target_attempts in attempts_by_target.items():
        ordered_attempts = sorted(
            target_attempts,
            key=lambda attempt: attempt.attempt_number,
        )
        if (
            not 1 <= len(ordered_attempts) <= 3
            or [attempt.attempt_number for attempt in ordered_attempts]
            != list(range(1, len(ordered_attempts) + 1))
            or any(
                attempt.target_id != target_id or attempt.page_number != 1
                for attempt in ordered_attempts
            )
        ):
            raise CourtListenerSnapshotMaterializationError(
                "Firecrawl per-target retry lineage is invalid"
            )
        for prior_attempt in ordered_attempts[:-1]:
            _validate_transient_firecrawl_attempt(
                prior_attempt,
                expected_run_id=run_id,
            )
        final_attempt = ordered_attempts[-1]
        if final_attempt.status == "succeeded":
            _validate_successful_firecrawl_attempt(
                final_attempt,
                expected_run_id=run_id,
            )
            successful_attempts[final_attempt.attempt_id] = final_attempt
            continue
        candidate_id = _validate_terminal_firecrawl_attempt(
            final_attempt,
            expected_run_id=run_id,
        )
        if candidate_id in terminal_unsuccessful_attempts:
            raise CourtListenerSnapshotMaterializationError(
                "duplicate terminal Firecrawl candidate lineage"
            )
        terminal_unsuccessful_attempts[candidate_id] = final_attempt
    if len(successful_attempts) != successful_count:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable successful attempts do not reconcile"
        )
    if len(terminal_unsuccessful_attempts) != unavailable_count:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable terminal attempts do not reconcile"
        )
    durable_reported_credits = sum(
        attempt.reported_credits
        for attempt in attempts_by_id.values()
        if attempt.reported_credits is not None
    )
    if durable_reported_credits != run_reported:
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl durable reported credits do not reconcile with the run ledger"
        )
    return _HybridFirecrawlEvidence(
        batch_id=expected_batch_id,
        run_id=run_id,
        receipt_count=receipt_count,
        run_reserved_credits=run_reserved,
        run_reported_credits=run_reported,
        successful_attempts=successful_attempts,
        terminal_unsuccessful_attempts=terminal_unsuccessful_attempts,
    )


def _validate_frozen_identity(
    *,
    run_card: Mapping[str, Any],
    summary: Mapping[str, Any],
    cycle_policy: Mapping[str, object],
    batch_config: Mapping[str, object],
) -> date:
    if (
        summary.get("schema_version")
        != "legalforecast.courtlistener_discovery_summary.v1"
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary schema mismatch"
        )
    if summary.get("dry_run") is not False:
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary is not an executed result"
        )
    anchor_text = _string(summary.get("anchor_date"), "summary anchor_date")
    try:
        anchor = date.fromisoformat(anchor_text)
    except ValueError as error:
        raise CourtListenerSnapshotMaterializationError(
            "summary anchor_date is not an ISO date"
        ) from error
    if cycle_policy.get("eligibility_anchor") != anchor_text:
        raise CourtListenerSnapshotMaterializationError(
            "discovery anchor does not match the frozen cycle policy"
        )
    if run_card.get("anchor_date") != anchor_text:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card anchor does not match its summary"
        )
    expected_batch = {
        "provider": "courtlistener",
        "search_window_start": summary.get("search_window_start"),
        "search_window_end": summary.get("search_window_end"),
        "query_terms": summary.get("query_terms"),
        "target_clean_cases": summary.get("target_clean_cases"),
        "max_candidates": summary.get("max_candidates"),
        "search_page_size": summary.get("search_page_size"),
    }
    for optional_key in (
        "docket_html_source",
        "firecrawl_run_id",
        "firecrawl_credit_cap",
    ):
        if optional_key in summary:
            expected_batch[optional_key] = summary[optional_key]
    if dict(batch_config) != expected_batch:
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not match the frozen batch configuration"
        )
    per_term = summary.get("per_term")
    query_terms = _string_list(summary.get("query_terms"), "summary query_terms")
    if not isinstance(per_term, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not include every frozen query term"
        )
    per_term_records = cast(Mapping[str, object], per_term)
    if set(per_term_records) != set(query_terms):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not include every frozen query term"
        )
    for term in query_terms:
        record_value = per_term_records[term]
        if not isinstance(record_value, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"discovery diagnostic is invalid for query term {term!r}"
            )
        record = cast(Mapping[str, object], record_value)
        if (
            record.get("terminal_status") != "exhausted"
            or record.get("limit_bound") is not False
        ):
            raise CourtListenerSnapshotMaterializationError(
                f"discovery is not saturated: query term {term!r} was not exhausted"
            )
    if (
        summary.get("target_met") is not False
        or summary.get("candidate_limit_reached") is not False
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery is not saturated: a target or candidate limit bound the run"
        )
    return anchor


def _accepted_ids(records: tuple[Mapping[str, Any], ...], *, anchor: date) -> set[str]:
    ids: set[str] = set()
    for row_number, record in enumerate(records, start=1):
        candidate = record.get("candidate")
        if not isinstance(candidate, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"screened case row {row_number} lacks candidate metadata"
            )
        candidate_record = cast(Mapping[str, object], candidate)
        candidate_id = _string(
            candidate_record.get("docket_id"),
            f"screened case row {row_number} docket_id",
        )
        if candidate_id in ids:
            raise CourtListenerSnapshotMaterializationError(
                f"duplicate screened candidate {candidate_id}"
            )
        metadata = candidate_record.get("metadata")
        if not isinstance(metadata, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate identity mismatch for {candidate_id}"
            )
        metadata_record = cast(Mapping[str, object], metadata)
        if metadata_record.get("case_id") != candidate_id:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate identity mismatch for {candidate_id}"
            )
        if record.get("eligibility_anchor_date") != anchor.isoformat():
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} has different anchor lineage"
            )
        disposition = _string(
            record.get("first_written_mtd_disposition_date"),
            f"screened candidate {candidate_id} disposition date",
        )
        try:
            disposition_date = date.fromisoformat(disposition)
        except ValueError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} disposition date is invalid"
            ) from error
        if disposition_date < anchor:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} predates the eligibility anchor"
            )
        ids.add(candidate_id)
    return ids


def _excluded_ids(
    records: tuple[Mapping[str, Any], ...],
    *,
    firecrawl_evidence: _HybridFirecrawlEvidence | None,
    durable_candidate_observations: Sequence[CandidateObservation],
) -> set[str]:
    ids: set[str] = set()
    terminal_retrieval_ids: set[str] = set()
    durable_by_candidate: dict[str, CandidateObservation] = {}
    for observation in durable_candidate_observations:
        if observation.candidate_id in durable_by_candidate:
            raise CourtListenerSnapshotMaterializationError(
                "duplicate durable candidate checkpoint evidence"
            )
        durable_by_candidate[observation.candidate_id] = observation
    for row_number, record in enumerate(records, start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"exclusion row {row_number} candidate_id"
        )
        if candidate_id in ids:
            raise CourtListenerSnapshotMaterializationError(
                f"duplicate excluded candidate {candidate_id}"
            )
        if record.get("stage") == "retrieval":
            reason = record.get("reason")
            if reason == "courtlistener_docket_unavailable":
                observation = durable_by_candidate.get(candidate_id)
                if (
                    observation is None
                    or observation.state != "excluded"
                    or observation.reason_code != "strict_clean_screen_failed"
                    or _canonical_json(observation.evidence) != _canonical_json(record)
                ):
                    raise CourtListenerSnapshotMaterializationError(
                        "CourtListener REST docket-unavailable outcome lacks exact "
                        f"durable candidate evidence: {candidate_id}"
                    )
            elif (
                reason != "courtlistener_docket_html_unavailable"
                or firecrawl_evidence is None
                or candidate_id not in firecrawl_evidence.terminal_unsuccessful_attempts
            ):
                raise CourtListenerSnapshotMaterializationError(
                    "CourtListener retrieval outcome lacks exact terminal "
                    f"Firecrawl evidence: {candidate_id}"
                )
            else:
                terminal_retrieval_ids.add(candidate_id)
        ids.add(candidate_id)
    if firecrawl_evidence is not None and terminal_retrieval_ids != set(
        firecrawl_evidence.terminal_unsuccessful_attempts
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl terminal attempts do not reconcile one-to-one with "
            "retrieval exclusions"
        )
    return ids


def _validate_terminal_firecrawl_attempt(
    attempt: FirecrawlAttempt,
    *,
    expected_run_id: str,
) -> str:
    prefix = "courtlistener-docket:"
    if not attempt.target_id.startswith(prefix):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl terminal attempt target identity is invalid"
        )
    candidate_id = attempt.target_id.removeprefix(prefix)
    if (
        not candidate_id.isascii()
        or not candidate_id.isdigit()
        or attempt.run_id != expected_run_id
        or attempt.page_number != 1
        or not 1 <= attempt.attempt_number <= 3
        or attempt.request_url
        != f"https://www.courtlistener.com/docket/{candidate_id}/"
        or attempt.reserved_credits != 1
        or attempt.artifact_path is not None
        or attempt.artifact_sha256 is not None
        or attempt.artifact_byte_count is not None
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl terminal attempt lineage is invalid"
        )
    authorized_at = _canonical_utc_datetime(
        attempt.authorized_at,
        f"Firecrawl terminal authorization time for {candidate_id}",
    )
    completed_at = _canonical_utc_datetime(
        attempt.completed_at,
        f"Firecrawl terminal completion time for {candidate_id}",
    )
    if completed_at < authorized_at:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl terminal attempt timestamps are invalid for {candidate_id}"
        )
    target_unavailable = (
        attempt.status == "target_error"
        and attempt.failure_code == "target_http_status_invalid"
        and attempt.failure_transient is False
        and attempt.provider_http_status == 200
        and attempt.target_http_status in {404, 410}
        and attempt.reported_credits in {0, 1}
        and attempt.proxy_used == "basic"
        and isinstance(attempt.failure_message, str)
        and bool(attempt.failure_message.strip())
        and isinstance(attempt.failure_response_sha256, str)
        and _SHA256.fullmatch(attempt.failure_response_sha256) is not None
    )
    abandoned = (
        attempt.status == "interrupted"
        and attempt.failure_code
        in {"authorization_abandoned", "authorization_abandoned_with_orphan"}
        and attempt.failure_transient is False
        and attempt.provider_http_status is None
        and attempt.target_http_status is None
        and attempt.reported_credits is None
        and attempt.proxy_used is None
        and isinstance(attempt.failure_message, str)
        and bool(attempt.failure_message.strip())
        and attempt.failure_response_sha256 is None
    )
    if not target_unavailable and not abandoned:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl terminal attempt is not an admitted outcome: {candidate_id}"
        )
    return candidate_id


def _validate_transient_firecrawl_attempt(
    attempt: FirecrawlAttempt,
    *,
    expected_run_id: str,
) -> None:
    prefix = "courtlistener-docket:"
    candidate_id = attempt.target_id.removeprefix(prefix)
    if (
        not attempt.target_id.startswith(prefix)
        or not candidate_id.isascii()
        or not candidate_id.isdigit()
        or attempt.run_id != expected_run_id
        or attempt.page_number != 1
        or not 1 <= attempt.attempt_number < 3
        or attempt.request_url
        != f"https://www.courtlistener.com/docket/{candidate_id}/"
        or attempt.reserved_credits != 1
        or attempt.status not in {"provider_error", "transport_error"}
        or attempt.failure_transient is not True
        or attempt.failure_code
        not in {
            "firecrawl_error",
            "provider_auth_error",
            "provider_payment_required",
            "provider_rate_limit",
            "provider_server_error",
        }
        or not isinstance(attempt.failure_message, str)
        or not attempt.failure_message.strip()
        or attempt.reported_credits is not None
        or attempt.proxy_used is not None
        or attempt.target_http_status is not None
        or attempt.artifact_path is not None
        or attempt.artifact_sha256 is not None
        or attempt.artifact_byte_count is not None
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl transient attempt lineage is invalid for {candidate_id}"
        )
    if (
        attempt.failure_response_sha256 is not None
        and _SHA256.fullmatch(attempt.failure_response_sha256) is None
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl transient response hash is invalid for {candidate_id}"
        )
    authorized_at = _canonical_utc_datetime(
        attempt.authorized_at,
        f"Firecrawl transient authorization time for {candidate_id}",
    )
    completed_at = _canonical_utc_datetime(
        attempt.completed_at,
        f"Firecrawl transient completion time for {candidate_id}",
    )
    if completed_at < authorized_at:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl transient attempt timestamps are invalid for {candidate_id}"
        )


def _validate_successful_firecrawl_attempt(
    attempt: FirecrawlAttempt,
    *,
    expected_run_id: str,
) -> None:
    prefix = "courtlistener-docket:"
    candidate_id = attempt.target_id.removeprefix(prefix)
    if (
        not attempt.target_id.startswith(prefix)
        or not candidate_id.isascii()
        or not candidate_id.isdigit()
        or attempt.run_id != expected_run_id
        or attempt.page_number != 1
        or not 1 <= attempt.attempt_number <= 3
        or attempt.request_url
        != f"https://www.courtlistener.com/docket/{candidate_id}/"
        or attempt.reserved_credits != 1
        or attempt.status != "succeeded"
        or attempt.reported_credits not in {0, 1}
        or attempt.proxy_used != "basic"
        or attempt.target_http_status != 200
        or attempt.failure_code is not None
        or attempt.failure_message is not None
        or attempt.failure_transient is not None
        or attempt.failure_response_sha256 is not None
        or attempt.artifact_path is None
        or attempt.artifact_sha256 is None
        or _SHA256.fullmatch(attempt.artifact_sha256) is None
        or attempt.artifact_byte_count is None
        or attempt.artifact_byte_count <= 0
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl successful attempt lineage is invalid for {candidate_id}"
        )
    authorized_at = _canonical_utc_datetime(
        attempt.authorized_at,
        f"Firecrawl successful authorization time for {candidate_id}",
    )
    completed_at = _canonical_utc_datetime(
        attempt.completed_at,
        f"Firecrawl successful completion time for {candidate_id}",
    )
    if completed_at < authorized_at:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl successful attempt timestamps are invalid for {candidate_id}"
        )


def _validate_transcript(
    pages: tuple[Mapping[str, Any], ...],
    *,
    summary: Mapping[str, Any],
    query_terms: tuple[str, ...],
) -> set[str]:
    pages_by_term: dict[str, list[Mapping[str, Any]]] = {
        term: [] for term in query_terms
    }
    all_ids: set[str] = set()
    total_hits = 0
    seen_hits: dict[tuple[str, str], str] = {}
    for row_number, page in enumerate(pages, start=1):
        if page.get("schema_version") != (
            "legalforecast.courtlistener_search_page_transcript.v1"
        ):
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript row {row_number} has wrong schema"
            )
        term = _string(page.get("term"), f"search transcript row {row_number} term")
        if term not in pages_by_term:
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript contains unknown query term {term!r}"
            )
        hits = page.get("hits")
        if not isinstance(hits, list):
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript row {row_number} hits must be a list"
            )
        page_provider_ids: set[str] = set()
        for raw_hit in cast(list[object], hits):
            if not isinstance(raw_hit, Mapping):
                raise CourtListenerSnapshotMaterializationError(
                    f"search transcript row {row_number} contains a non-object hit"
                )
            hit = cast(Mapping[str, object], raw_hit)
            provider_hit_id = _string(hit.get("provider_hit_id"), "provider_hit_id")
            candidate_id = _string(hit.get("candidate_id"), "candidate_id")
            payload = hit.get("payload")
            if not isinstance(payload, Mapping):
                raise CourtListenerSnapshotMaterializationError(
                    f"search hit {provider_hit_id} payload is not an object"
                )
            if provider_hit_id in page_provider_ids:
                raise CourtListenerSnapshotMaterializationError(
                    f"duplicate provider hit within transcript page: {provider_hit_id}"
                )
            page_provider_ids.add(provider_hit_id)
            payload_record = cast(Mapping[str, object], payload)
            identity = _canonical_json(
                {"candidate_id": candidate_id, "payload": payload_record}
            )
            prior = seen_hits.get((term, provider_hit_id))
            if prior is not None and prior != identity:
                raise CourtListenerSnapshotMaterializationError(
                    f"provider hit identity changed for {provider_hit_id}"
                )
            seen_hits[(term, provider_hit_id)] = identity
            all_ids.add(candidate_id)
            total_hits += 1
        pages_by_term[term].append(page)

    per_term = cast(Mapping[str, object], summary["per_term"])
    for term in query_terms:
        term_pages = pages_by_term[term]
        if not term_pages:
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript is missing query term {term!r}"
            )
        expected_cursor: str | None = None
        term_ids: set[str] = set()
        for index, page in enumerate(term_pages):
            if page.get("request_cursor") != expected_cursor:
                raise CourtListenerSnapshotMaterializationError(
                    f"search transcript cursor chain is broken for {term!r}"
                )
            terminal = page.get("terminal_status")
            is_last = index == len(term_pages) - 1
            if is_last:
                if terminal != "exhausted" or page.get("next_cursor") is not None:
                    raise CourtListenerSnapshotMaterializationError(
                        f"search transcript is not exhausted for {term!r}"
                    )
            else:
                next_cursor = page.get("next_cursor")
                if (
                    terminal is not None
                    or not isinstance(next_cursor, str)
                    or not next_cursor
                ):
                    raise CourtListenerSnapshotMaterializationError(
                        f"search transcript has an incomplete page for {term!r}"
                    )
                expected_cursor = next_cursor
            for raw_hit in cast(list[object], page["hits"]):
                hit = cast(Mapping[str, object], raw_hit)
                term_ids.add(cast(str, hit["candidate_id"]))
        diagnostic = per_term[term]
        if not isinstance(diagnostic, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"summary diagnostic for {term!r} is invalid"
            )
        diagnostic_record = cast(Mapping[str, object], diagnostic)
        if diagnostic_record.get("request_count") != len(
            term_pages
        ) or diagnostic_record.get("candidate_count") != len(term_ids):
            raise CourtListenerSnapshotMaterializationError(
                f"summary diagnostic count mismatch for {term!r}"
            )
    if summary.get("search_hit_count") != total_hits:
        raise CourtListenerSnapshotMaterializationError(
            "summary search-hit count does not match the transcript"
        )
    if summary.get("duplicate_search_hit_count") != total_hits - len(all_ids):
        raise CourtListenerSnapshotMaterializationError(
            "summary duplicate-hit count does not match the transcript"
        )
    return all_ids


def _validate_summary_counts(
    *,
    run_card: Mapping[str, Any],
    summary: Mapping[str, Any],
    accepted_count: int,
    excluded_count: int,
    transcript_count: int,
) -> None:
    processed = accepted_count + excluded_count
    expected = {
        "accepted_case_count": accepted_count,
        "excluded_case_count": excluded_count,
        "processed_candidate_count": processed,
        "unique_candidate_count": transcript_count,
    }
    for name, value in expected.items():
        if summary.get(name) != value:
            raise CourtListenerSnapshotMaterializationError(
                f"discovery summary count mismatch: {name}"
            )
    if run_card.get("record_count") != accepted_count:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card record count mismatch"
        )
    if (
        run_card.get("accepted_case_count") != accepted_count
        or run_card.get("excluded_case_count") != excluded_count
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card outcome counts do not reconcile"
        )


def _verify_raw_artifacts(
    *,
    raw_html_directory: Path,
    manifest: tuple[Mapping[str, Any], ...],
    retrieved_at: str,
    accepted_ids: set[str],
    exclusions: tuple[Mapping[str, Any], ...],
    outcome_ids: set[str],
    expected_batch_digest: str,
    firecrawl_evidence: _HybridFirecrawlEvidence | None,
) -> tuple[VerifiedRawArtifact, ...]:
    if raw_html_directory.is_symlink() or not raw_html_directory.is_dir():
        raise CourtListenerSnapshotMaterializationError(
            "raw CourtListener HTML output is not a regular directory"
        )
    artifacts: list[VerifiedRawArtifact] = []
    manifest_ids: set[str] = set()
    manifest_names: set[str] = set()
    receipt_attempt_ids: set[int] = set()
    for row_number, record in enumerate(manifest, start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"raw manifest row {row_number} candidate_id"
        )
        if candidate_id not in outcome_ids or candidate_id in manifest_ids:
            raise CourtListenerSnapshotMaterializationError(
                f"raw manifest candidate identity is invalid: {candidate_id}"
            )
        relative = _string(
            record.get("relative_path"), f"raw manifest row {row_number} path"
        )
        if relative != f"{candidate_id}.html" or Path(relative).name != relative:
            raise CourtListenerSnapshotMaterializationError(
                f"raw manifest path is unsafe for {candidate_id}"
            )
        path = raw_html_directory / relative
        content = _read_regular_file(path, f"raw HTML for {candidate_id}")
        digest = hashlib.sha256(content).hexdigest()
        if record.get("sha256") != digest or record.get("byte_count") != len(content):
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML commitment mismatch for {candidate_id}"
            )
        if not content.strip():
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML is empty for {candidate_id}"
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML is not UTF-8 for {candidate_id}"
            ) from error
        receipt_value = record.get("source_receipt")
        if firecrawl_evidence is None:
            if receipt_value is not None:
                raise CourtListenerSnapshotMaterializationError(
                    "legacy discovery raw artifact contains unexpected source receipt"
                )
        else:
            attempt_id = _verify_firecrawl_source_receipt(
                receipt_value,
                candidate_id=candidate_id,
                digest=digest,
                byte_count=len(content),
                expected_batch_digest=expected_batch_digest,
                expected_run_id=firecrawl_evidence.run_id,
                artifact_path=path,
                successful_attempts=firecrawl_evidence.successful_attempts,
            )
            if attempt_id in receipt_attempt_ids:
                raise CourtListenerSnapshotMaterializationError(
                    "Firecrawl source receipt attempt identity is duplicated"
                )
            receipt_attempt_ids.add(attempt_id)
        manifest_ids.add(candidate_id)
        manifest_names.add(relative)
        artifacts.append(
            VerifiedRawArtifact(
                candidate_id=candidate_id,
                path=path,
                content=content,
                sha256=digest,
                byte_count=len(content),
                retrieved_at=retrieved_at,
            )
        )
    actual_names: set[str] = set()
    for path in raw_html_directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise CourtListenerSnapshotMaterializationError(
                f"unexpected non-regular raw HTML artifact: {path}"
            )
        actual_names.add(path.name)
    if actual_names != manifest_names:
        raise CourtListenerSnapshotMaterializationError(
            "raw HTML directory does not exactly match its committed manifest"
        )
    required_ids = set(accepted_ids)
    for exclusion in exclusions:
        notes = exclusion.get("notes")
        if exclusion.get("stage") not in {"discovery", "retrieval"} or (
            isinstance(notes, str)
            and "failed the strict MTD acquisition screen" in notes
        ):
            required_ids.add(cast(str, exclusion["candidate_id"]))
    missing = sorted(required_ids - manifest_ids)
    if missing:
        raise CourtListenerSnapshotMaterializationError(
            "discovery outcomes are missing required raw HTML: " + ", ".join(missing)
        )
    if (
        firecrawl_evidence is not None
        and len(receipt_attempt_ids) != firecrawl_evidence.receipt_count
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl source receipts do not exactly reconcile with raw artifacts"
        )
    return tuple(artifacts)


def _verify_firecrawl_source_receipt(
    value: object,
    *,
    candidate_id: str,
    digest: str,
    byte_count: int,
    expected_batch_digest: str,
    expected_run_id: str,
    artifact_path: Path,
    successful_attempts: Mapping[int, FirecrawlAttempt],
) -> int:
    if not isinstance(value, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt is required for {candidate_id}"
        )
    receipt = cast(Mapping[str, object], value)
    if frozenset(receipt) != _FIRECRAWL_RECEIPT_KEYS:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt schema is incomplete for {candidate_id}"
        )
    if (
        receipt.get("schema_version") != _FIRECRAWL_RECEIPT_SCHEMA
        or receipt.get("docket_html_source") != "firecrawl"
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt schema mismatch for {candidate_id}"
        )
    if receipt.get("batch_digest") != expected_batch_digest:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt batch mismatch for {candidate_id}"
        )
    if receipt.get("firecrawl_run_id") != expected_run_id:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt run mismatch for {candidate_id}"
        )
    if (
        not candidate_id.isascii()
        or not candidate_id.isdigit()
        or receipt.get("firecrawl_target_id") != f"courtlistener-docket:{candidate_id}"
        or receipt.get("request_url")
        != f"https://www.courtlistener.com/docket/{candidate_id}/"
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt target mismatch for {candidate_id}"
        )
    attempt_id = _positive_int(
        receipt.get("firecrawl_attempt_id"),
        f"Firecrawl source receipt attempt ID for {candidate_id}",
    )
    reported_credits = receipt.get("reported_credits")
    if (
        receipt.get("reserved_credits") != 1
        or isinstance(reported_credits, bool)
        or not isinstance(reported_credits, int)
        or reported_credits not in {0, 1}
        or receipt.get("proxy_used") != "basic"
        or receipt.get("target_http_status") != 200
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt authority mismatch for {candidate_id}"
        )
    if (
        receipt.get("artifact_sha256") != digest
        or receipt.get("artifact_byte_count") != byte_count
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt artifact mismatch for {candidate_id}"
        )
    authorized_at = _canonical_utc_datetime(
        receipt.get("authorized_at"),
        f"Firecrawl source receipt authorization time for {candidate_id}",
    )
    completed_at = _canonical_utc_datetime(
        receipt.get("completed_at"),
        f"Firecrawl source receipt completion time for {candidate_id}",
    )
    if completed_at < authorized_at:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt timestamps are invalid for {candidate_id}"
        )
    attempt = successful_attempts.get(attempt_id)
    if attempt is None:
        raise CourtListenerSnapshotMaterializationError(
            f"Firecrawl source receipt lacks a durable attempt for {candidate_id}"
        )
    durable_authorized_at = _canonical_utc_datetime(
        attempt.authorized_at,
        f"Firecrawl durable authorization time for {candidate_id}",
    )
    durable_completed_at = _canonical_utc_datetime(
        attempt.completed_at,
        f"Firecrawl durable completion time for {candidate_id}",
    )
    if (
        attempt.run_id != expected_run_id
        or attempt.target_id != f"courtlistener-docket:{candidate_id}"
        or attempt.page_number != 1
        or not 1 <= attempt.attempt_number <= 3
        or attempt.request_url != receipt.get("request_url")
        or attempt.status != "succeeded"
        or attempt.reserved_credits != receipt.get("reserved_credits")
        or attempt.reported_credits != receipt.get("reported_credits")
        or attempt.proxy_used != receipt.get("proxy_used")
        or attempt.provider_http_status is not None
        or attempt.target_http_status != receipt.get("target_http_status")
        or attempt.failure_code is not None
        or attempt.failure_message is not None
        or attempt.failure_transient is not None
        or attempt.failure_response_sha256 is not None
        or attempt.artifact_path != artifact_path.resolve()
        or attempt.artifact_sha256 != digest
        or attempt.artifact_byte_count != byte_count
        or attempt.authorized_at != receipt.get("authorized_at")
        or attempt.completed_at != receipt.get("completed_at")
        or durable_authorized_at != authorized_at
        or durable_completed_at != completed_at
    ):
        raise CourtListenerSnapshotMaterializationError(
            "Firecrawl source receipt does not match durable attempt for "
            f"{candidate_id}"
        )
    return attempt_id


def _verify_file_commitment(path: Path, value: object, name: str) -> None:
    if not isinstance(value, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            f"discovery commitment for {name} is invalid"
        )
    payload = _read_regular_file(path, f"discovery output {name}")
    commitment = cast(Mapping[str, object], value)
    if (
        commitment.get("sha256") != hashlib.sha256(payload).hexdigest()
        or commitment.get("byte_count") != len(payload)
        or commitment.get("row_count") != payload.count(b"\n")
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"discovery output commitment mismatch: {name}"
        )


def _read_regular_file(path: Path, label: str) -> bytes:
    if not path.is_absolute():
        path = path.resolve()
    if path.is_symlink() or not path.is_file():
        raise CourtListenerSnapshotMaterializationError(
            f"{label} is not a regular file: {path}"
        )
    return path.read_bytes()


def _jsonl(path: Path, label: str) -> list[Mapping[str, Any]]:
    payload = _read_regular_file(path, label)
    records: list[Mapping[str, Any]] = []
    for row_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"{label} row {row_number} is invalid JSON"
            ) from error
        if not isinstance(value, dict):
            raise CourtListenerSnapshotMaterializationError(
                f"{label} row {row_number} is not an object"
            )
        records.append(cast(dict[str, Any], value))
    return records


def _json_object(payload: bytes, label: str) -> Mapping[str, Any]:
    try:
        value: object = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} is invalid JSON"
        ) from error
    if not isinstance(value, dict):
        raise CourtListenerSnapshotMaterializationError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CourtListenerSnapshotMaterializationError(f"{label} is invalid")
    path = Path(value)
    if not path.is_absolute():
        raise CourtListenerSnapshotMaterializationError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be an existing canonical absolute path without symlinks"
        ) from error
    if path != resolved:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be an existing canonical absolute path without symlinks"
        )
    return path


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourtListenerSnapshotMaterializationError(f"{label} is required")
    return value.strip()


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be a positive integer"
        )
    return value


def _canonical_utc_datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be a canonical UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be a canonical UTC timestamp"
        ) from error
    if parsed.tzinfo != UTC or parsed.isoformat().replace("+00:00", "Z") != text:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be a canonical UTC timestamp"
        )
    return parsed


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be a nonnegative integer"
        )
    return value


def _count_mapping(value: object, label: str) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise CourtListenerSnapshotMaterializationError(f"{label} must be an object")
    counts = cast(Mapping[object, object], value)
    result: dict[str, int] = {}
    for raw_key, raw_count in counts.items():
        if not isinstance(raw_key, str) or not raw_key:
            raise CourtListenerSnapshotMaterializationError(
                f"{label} contains an invalid key"
            )
        result[raw_key] = _positive_int(raw_count, f"{label} count")
    return result


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CourtListenerSnapshotMaterializationError(f"{label} must be a list")
    result = tuple(_string(item, label) for item in cast(list[object], value))
    if not result or len(set(result)) != len(result):
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must contain unique values"
        )
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

"""Authenticated provisional Firecrawl frontier from partial Case.dev progress."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_ranked_selection import (
    RankedCaseDevCandidate,
    case_dev_projection_by_docket,
    case_dev_source_authority_commitments,
    project_case_dev_opinion_source,
    verify_case_dev_ranked_record,
)
from legalforecast.ingestion.case_dev_recap_enrichment import (
    CASE_DEV_RANKING_POLICY_VERSION,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.decision_text_artifact import CYCLE_1_ELIGIBILITY_ANCHOR
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, TermTerminalStatus
from legalforecast.ingestion.recap_api_batch_driver import (
    DirectSearchLead,
    DirectSearchSeedSource,
    RecapApiBatchDriverError,
)
from legalforecast.ingestion.recap_api_discovery import (
    RECAP_API_PROVIDER,
    build_recap_api_batch_config,
    prescreen_recap_candidate,
)

CASE_DEV_PROVISIONAL_FRONTIER_TERM = "case-dev-provisional-frontier-transfer-v1"
CASE_DEV_PROVISIONAL_FRONTIER_SCHEMA = (
    "legalforecast.case_dev_provisional_frontier_transfer.v1"
)
CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA = (
    "legalforecast.case_dev_provisional_frontier_selection_run.v1"
)
CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS = "authenticated_case_dev_provisional_frontier"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DOCKET_ID = re.compile(r"[1-9][0-9]*")
_AUTHORIZED_TERMINAL_REASONS = frozenset(
    {
        "case_dev_continuation_cycle",
        "case_dev_page_limit_reached",
        "case_dev_pagination_exhaustion_unproven",
        "case_dev_server_error_retries_exhausted",
    }
)
_RETRYABLE_FAILURE_REASONS = frozenset(
    {
        "case_dev_duplicate_entry_conflict",
        "case_dev_duplicate_entry_semantic_conflict",
    }
)


@dataclass(frozen=True, slots=True)
class VerifiedCaseDevProvisionalFrontier:
    """Exact authenticated partition of one partial Case.dev enrichment."""

    source: DirectSearchSeedSource
    source_store_path: Path
    source_projection_path: Path
    progress_config_path: Path
    progress_path: Path
    source_projection_sha256: str
    progress_config_sha256: str
    progress_sha256: str
    success_candidate_set_sha256: str
    terminal_excluded_candidate_set_sha256: str
    pending_candidate_set_sha256: str
    terminal_exclusion_reason_counts: tuple[tuple[str, int], ...]
    selected: tuple[RankedCaseDevCandidate, ...]
    ranked_records: tuple[dict[str, object], ...]
    terminal_exclusions: tuple[dict[str, object], ...]
    pending: tuple[dict[str, object], ...]

    @property
    def source_candidate_count(self) -> int:
        return len(self.source.leads)

    def commitment_record(self) -> dict[str, object]:
        selected = [candidate.commitment_record() for candidate in self.selected]
        return {
            "provisional_frontier": True,
            "final_cohort_eligible": False,
            "full_source_terminal": False,
            "source_store_path": str(self.source_store_path),
            **case_dev_source_authority_commitments(self.source),
            "source_projection_path": str(self.source_projection_path),
            "source_projection_sha256": self.source_projection_sha256,
            "progress_config_path": str(self.progress_config_path),
            "progress_config_sha256": self.progress_config_sha256,
            "progress_path": str(self.progress_path),
            "progress_sha256": self.progress_sha256,
            "source_candidate_count": self.source_candidate_count,
            "ranked_candidate_count": len(self.selected),
            "success_count": len(self.selected),
            "terminal_exclusion_count": len(self.terminal_exclusions),
            "pending_count": len(self.pending),
            "success_candidate_set_sha256": self.success_candidate_set_sha256,
            "terminal_excluded_candidate_set_sha256": (
                self.terminal_excluded_candidate_set_sha256
            ),
            "pending_candidate_set_sha256": self.pending_candidate_set_sha256,
            "terminal_exclusion_reason_counts": dict(
                self.terminal_exclusion_reason_counts
            ),
            "terminal_exclusions": list(self.terminal_exclusions),
            "pending": list(self.pending),
            "selected_candidate_set_sha256": self.success_candidate_set_sha256,
            "selected": selected,
        }

    def compact_commitment_record(self) -> dict[str, object]:
        """Project constant-size source/progress/partition authentication."""

        source = case_dev_source_authority_commitments(self.source)
        return {
            "provisional_frontier": True,
            "final_cohort_eligible": False,
            "full_source_terminal": False,
            "source_batch_id": source["source_batch_id"],
            "source_batch_digest": source["source_batch_digest"],
            "source_cycle_hash": source["source_cycle_hash"],
            "source_query_commitment_sha256": source["source_query_commitment_sha256"],
            "source_candidate_set_sha256": source["source_candidate_set_sha256"],
            "source_hit_set_sha256": source["source_hit_set_sha256"],
            "source_projection_sha256": self.source_projection_sha256,
            "progress_config_sha256": self.progress_config_sha256,
            "progress_sha256": self.progress_sha256,
            "source_candidate_count": self.source_candidate_count,
            "ranked_candidate_count": len(self.selected),
            "success_count": len(self.selected),
            "terminal_exclusion_count": len(self.terminal_exclusions),
            "pending_count": len(self.pending),
            "success_candidate_set_sha256": self.success_candidate_set_sha256,
            "terminal_excluded_candidate_set_sha256": (
                self.terminal_excluded_candidate_set_sha256
            ),
            "pending_candidate_set_sha256": self.pending_candidate_set_sha256,
            "selected_candidate_set_sha256": self.success_candidate_set_sha256,
        }


@dataclass(frozen=True, slots=True)
class CaseDevProvisionalFrontierResult:
    """Replay result for one materialized provisional public frontier."""

    batch_id: str
    target_cycle_hash: str
    target_batch_digest: str
    leads_seeded: int
    already_seeded: bool
    frontier: VerifiedCaseDevProvisionalFrontier

    def run_card_record(self) -> dict[str, object]:
        return provisional_frontier_run_card_record(
            frontier=self.frontier,
            batch_id=self.batch_id,
            target_cycle_hash=self.target_cycle_hash,
            target_batch_digest=self.target_batch_digest,
        )

    def to_record(self) -> dict[str, object]:
        record = self.run_card_record()
        # The run card retains the exact identity arrays. Console/summary output
        # stays bounded even when thousands of source rows remain pending.
        record.pop("selected")
        record.pop("terminal_exclusions")
        record.pop("pending")
        record.update(
            {
                "leads_seeded": self.leads_seeded,
                "already_seeded": self.already_seeded,
            }
        )
        return record


def verify_case_dev_provisional_frontier(
    *,
    source: DirectSearchSeedSource,
    source_store_path: Path,
    source_projection_path: Path,
    progress_config_path: Path,
    progress_path: Path,
    expected_progress_config_sha256: str,
    expected_progress_sha256: str,
) -> VerifiedCaseDevProvisionalFrontier:
    """Authenticate partial progress and reconcile every source row exactly once."""

    for label, digest in (
        ("progress-config", expected_progress_config_sha256),
        ("progress", expected_progress_sha256),
    ):
        if _SHA256.fullmatch(digest) is None:
            raise RecapApiBatchDriverError(
                f"expected {label} SHA-256 must be 64 lowercase hex digits"
            )
    progress_config_bytes = _read_regular_bytes(
        progress_config_path, "Case.dev progress config"
    )
    progress_config_sha256 = hashlib.sha256(progress_config_bytes).hexdigest()
    if progress_config_sha256 != expected_progress_config_sha256:
        raise RecapApiBatchDriverError(
            "Case.dev progress-config SHA-256 does not match the external commitment"
        )
    progress_bytes = _read_regular_bytes(progress_path, "Case.dev progress")
    progress_sha256 = hashlib.sha256(progress_bytes).hexdigest()
    if progress_sha256 != expected_progress_sha256:
        raise RecapApiBatchDriverError(
            "Case.dev progress SHA-256 does not match the external commitment"
        )
    expected_projection = list(project_case_dev_opinion_source(source))
    projection_records = _read_jsonl(source_projection_path)
    if projection_records != expected_projection:
        raise RecapApiBatchDriverError(
            "Case.dev source projection does not match the verified source"
        )
    projection_by_docket = case_dev_projection_by_docket(projection_records)
    source_commitments = case_dev_source_authority_commitments(source)
    config = _json_object_from_bytes(progress_config_bytes, "Case.dev progress config")
    projection_sha256 = _file_sha256(source_projection_path)
    expected_config: dict[str, object] = {
        "schema_version": "legalforecast.case_dev_recap_progress.v1",
        "ranking_policy_version": CASE_DEV_RANKING_POLICY_VERSION,
        "dockets_sha256": "sha256:" + projection_sha256,
        "input_record_count": len(projection_records),
        "page_size": config.get("page_size"),
        "max_pages_per_docket": config.get("max_pages_per_docket"),
        "free_lookup_only": True,
        **source_commitments,
        "source_projection_sha256": projection_sha256,
        "eligibility_anchor": CYCLE_1_ELIGIBILITY_ANCHOR.isoformat(),
    }
    if (
        config != expected_config
        or type(config.get("page_size")) is not int
        or not 1 <= cast(int, config["page_size"]) <= 100
        or type(config.get("max_pages_per_docket")) is not int
        or cast(int, config["max_pages_per_docket"]) <= 0
    ):
        raise RecapApiBatchDriverError(
            "Case.dev progress config does not authenticate the source projection"
        )

    progress_records = _jsonl_from_bytes(progress_bytes, "Case.dev progress")
    latest: dict[int, Mapping[str, object]] = {}
    for record in progress_records:
        input_index = record.get("input_index")
        outcome = record.get("outcome")
        payload = record.get("payload")
        if (
            type(input_index) is not int
            or input_index < 0
            or input_index >= len(projection_records)
            or outcome not in {"success", "failure", "transient"}
            or not isinstance(payload, Mapping)
        ):
            raise RecapApiBatchDriverError("Case.dev progress record is invalid")
        prior = latest.get(input_index)
        if prior is not None and not _progress_is_retryable(prior):
            raise RecapApiBatchDriverError(
                "Case.dev progress repeats a terminal source index"
            )
        latest[input_index] = record

    successes: list[tuple[int, RankedCaseDevCandidate, dict[str, object]]] = []
    exclusions: list[dict[str, object]] = []
    pending: list[dict[str, object]] = []
    exclusion_reasons: Counter[str] = Counter()
    for input_index, projection in enumerate(projection_records):
        candidate_id = _required_projection_text(projection, "candidate_id")
        docket_id = _required_projection_text(projection, "docket_id")
        progress = latest.get(input_index)
        if progress is None:
            pending.append(
                {
                    "input_index": input_index,
                    "candidate_id": candidate_id,
                    "docket_id": docket_id,
                    "pending_state": "unprocessed",
                    "latest_progress_record_sha256": None,
                }
            )
            continue
        outcome = progress["outcome"]
        payload = cast(Mapping[str, object], progress["payload"])
        if outcome == "success":
            candidate = verify_case_dev_ranked_record(
                payload,
                rank=1,
                projection_by_docket=projection_by_docket,
            )
            if candidate.docket_id != docket_id:
                raise RecapApiBatchDriverError(
                    "Case.dev success does not match its source index"
                )
            successes.append((input_index, candidate, dict(payload)))
            continue
        if _progress_is_retryable(progress):
            pending.append(
                {
                    "input_index": input_index,
                    "candidate_id": candidate_id,
                    "docket_id": docket_id,
                    "pending_state": (
                        "retryable_transient"
                        if outcome == "transient"
                        else "retryable_integrity_conflict"
                    ),
                    "latest_progress_record_sha256": _canonical_sha256(progress),
                }
            )
            continue
        reason = payload.get("reason")
        detail = payload.get("detail")
        if (
            outcome != "failure"
            or not isinstance(reason, str)
            or reason not in _AUTHORIZED_TERMINAL_REASONS
            or not isinstance(detail, str)
            or not detail
            or detail != detail.strip()
        ):
            raise RecapApiBatchDriverError(
                "Case.dev progress contains an unauthorized terminal failure"
            )
        for field, expected in (
            ("input_index", input_index),
            ("candidate_id", candidate_id),
            ("docket_id", docket_id),
        ):
            present = payload.get(field)
            if present is not None and present != expected:
                raise RecapApiBatchDriverError(
                    "Case.dev terminal failure contradicts its source identity"
                )
        exclusion: dict[str, object] = {
            "input_index": input_index,
            "candidate_id": candidate_id,
            "docket_id": docket_id,
            "reason": reason,
            "progress_record_sha256": _canonical_sha256(progress),
        }
        exclusions.append(exclusion)
        exclusion_reasons[reason] += 1

    successes.sort(key=lambda item: item[1].ranking_key)
    selected = tuple(
        RankedCaseDevCandidate(
            docket_id=candidate.docket_id,
            rank=rank,
            ranking_key=candidate.ranking_key,
            returned_courtlistener_url=candidate.returned_courtlistener_url,
            ranked_record_sha256=candidate.ranked_record_sha256,
            bankruptcy_adversary_entry_evidence=(
                candidate.bankruptcy_adversary_entry_evidence
            ),
        )
        for rank, (_, candidate, _) in enumerate(successes, start=1)
    )
    if not selected:
        raise RecapApiBatchDriverError(
            "Case.dev provisional frontier has no authenticated successes"
        )
    success_indices = {index for index, _, _ in successes}
    exclusion_indices = {cast(int, item["input_index"]) for item in exclusions}
    pending_indices = {cast(int, item["input_index"]) for item in pending}
    expected_indices = set(range(len(projection_records)))
    if (
        success_indices & exclusion_indices
        or success_indices & pending_indices
        or exclusion_indices & pending_indices
        or success_indices | exclusion_indices | pending_indices != expected_indices
    ):
        raise RecapApiBatchDriverError(
            "Case.dev provisional partitions do not exactly reconcile the source"
        )
    selected_commitments = [candidate.commitment_record() for candidate in selected]
    return VerifiedCaseDevProvisionalFrontier(
        source=source,
        source_store_path=source_store_path,
        source_projection_path=source_projection_path,
        progress_config_path=progress_config_path,
        progress_path=progress_path,
        source_projection_sha256=projection_sha256,
        progress_config_sha256=progress_config_sha256,
        progress_sha256=progress_sha256,
        success_candidate_set_sha256=_canonical_sha256(selected_commitments),
        terminal_excluded_candidate_set_sha256=_canonical_sha256(exclusions),
        pending_candidate_set_sha256=_canonical_sha256(pending),
        terminal_exclusion_reason_counts=tuple(sorted(exclusion_reasons.items())),
        selected=selected,
        ranked_records=tuple(record for _, _, record in successes),
        terminal_exclusions=tuple(exclusions),
        pending=tuple(pending),
    )


def materialize_case_dev_provisional_frontier(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    frontier: VerifiedCaseDevProvisionalFrontier,
    page_size: int = 100,
) -> CaseDevProvisionalFrontierResult:
    """Materialize all and only authenticated successes as a provisional batch."""

    if batch_id == frontier.source.source_batch_id:
        raise RecapApiBatchDriverError(
            "provisional target batch must differ from its source batch"
        )
    source = frontier.source
    config = provisional_frontier_batch_config(
        frontier=frontier,
        page_size=page_size,
    )
    digest = store.ensure_batch(batch_id, config)
    if digest != provisional_frontier_batch_digest(
        frontier=frontier,
        page_size=page_size,
    ):
        raise RecapApiBatchDriverError(
            "provisional batch digest differs from its pre-mutation plan"
        )
    store.ensure_terms(batch_id, (CASE_DEV_PROVISIONAL_FRONTIER_TERM,))
    initial = store.term_progress(batch_id, CASE_DEV_PROVISIONAL_FRONTIER_TERM)
    if initial.hit_count > len(frontier.selected):
        raise RecapApiBatchDriverError(
            "provisional frontier progress exceeds authenticated successes"
        )
    lead_by_docket = {lead.docket_id: lead for lead in source.leads}
    compact_commitment = frontier.compact_commitment_record()
    hits = tuple(
        _provisional_hit(
            candidate,
            lead=lead_by_docket[candidate.docket_id],
            frontier=frontier,
            compact_commitment=compact_commitment,
            target_cycle_hash=store.cycle_hash,
        )
        for candidate in frontier.selected
    )
    offset = 0
    cursor: str | None = None
    while offset < len(hits):
        next_offset = min(offset + page_size, len(hits))
        next_cursor = str(next_offset) if next_offset < len(hits) else None
        store.commit_search_page(
            batch_id,
            CASE_DEV_PROVISIONAL_FRONTIER_TERM,
            cursor,
            hits[offset:next_offset],
            next_cursor=next_cursor,
            terminal_status=(
                None if next_cursor is not None else TermTerminalStatus.EXHAUSTED
            ),
        )
        offset = next_offset
        cursor = next_cursor
    final = store.term_progress(batch_id, CASE_DEV_PROVISIONAL_FRONTIER_TERM)
    if (
        final.hit_count != len(hits)
        or final.terminal_status != TermTerminalStatus.EXHAUSTED
        or store.candidate_discovery_hits(batch_id)
        != tuple(sorted(hits, key=lambda hit: hit.candidate_id))
    ):
        raise RecapApiBatchDriverError(
            "materialized provisional frontier does not reconcile"
        )
    already_seeded = (
        initial.terminal_status == TermTerminalStatus.EXHAUSTED
        and initial.hit_count == len(hits)
    )
    return CaseDevProvisionalFrontierResult(
        batch_id=batch_id,
        target_cycle_hash=store.cycle_hash,
        target_batch_digest=digest,
        leads_seeded=0 if already_seeded else len(hits) - initial.hit_count,
        already_seeded=already_seeded,
        frontier=frontier,
    )


def ranked_records_for_provisional_frontier(
    frontier: VerifiedCaseDevProvisionalFrontier,
) -> tuple[dict[str, object], ...]:
    """Return authenticated success payloads in canonical ranking order."""

    return frontier.ranked_records


def provisional_frontier_batch_config(
    *,
    frontier: VerifiedCaseDevProvisionalFrontier,
    page_size: int,
) -> dict[str, object]:
    """Build the exact immutable target-batch config without mutating a store."""

    if not 1 <= page_size <= 100:
        raise RecapApiBatchDriverError("page_size must be from 1 through 100")
    source = frontier.source
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(CASE_DEV_PROVISIONAL_FRONTIER_TERM,),
        page_size=page_size,
        top_k_per_term=len(frontier.selected),
    )
    config.update(
        {
            "discovery_mode": CASE_DEV_PROVISIONAL_FRONTIER_SCHEMA,
            "selection_semantics": CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS,
            "selected_candidate_count": len(frontier.selected),
            **frontier.commitment_record(),
        }
    )
    return config


def provisional_frontier_batch_digest(
    *,
    frontier: VerifiedCaseDevProvisionalFrontier,
    page_size: int,
) -> str:
    """Derive the store's exact config digest before target-batch mutation."""

    config = provisional_frontier_batch_config(
        frontier=frontier,
        page_size=page_size,
    )
    return hashlib.sha256(
        json.dumps(
            config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def provisional_frontier_run_card_record(
    *,
    frontier: VerifiedCaseDevProvisionalFrontier,
    batch_id: str,
    target_cycle_hash: str,
    target_batch_digest: str,
) -> dict[str, object]:
    """Build the exact immutable run-card body from pre-mutation commitments."""

    return {
        "schema_version": CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_fee_acknowledgment_allowed": False,
        "batch_id": batch_id,
        "target_cycle_hash": target_cycle_hash,
        "target_batch_digest": target_batch_digest,
        "leads_selected": len(frontier.selected),
        **frontier.commitment_record(),
    }


def _provisional_hit(
    candidate: RankedCaseDevCandidate,
    *,
    lead: DirectSearchLead,
    frontier: VerifiedCaseDevProvisionalFrontier,
    compact_commitment: Mapping[str, object],
    target_cycle_hash: str,
) -> DiscoveryHit:
    prescreen_reason = prescreen_recap_candidate(
        court_id=lead.court_id,
        docket_number=lead.docket_number,
        case_name=lead.case_name,
        defer_bankruptcy_to_authoritative_docket=True,
    )
    payload: dict[str, Any] = {
        "candidate_id": lead.candidate_id,
        "docket_id": lead.docket_id,
        "courtlistener_docket_id": lead.docket_id,
        "court_id": lead.court_id,
        "docket_number": lead.docket_number,
        "case_name": lead.case_name,
        "provider": RECAP_API_PROVIDER,
        "prescreen_exclusion_reason": prescreen_reason,
        "query_term": CASE_DEV_PROVISIONAL_FRONTIER_TERM,
        "case_dev_provisional_frontier_provenance": (
            provisional_frontier_hit_provenance(
                candidate=candidate,
                compact_commitment=compact_commitment,
                target_cycle_hash=target_cycle_hash,
            )
        ),
    }
    if lead.decision_entry_evidence is not None:
        payload["decision_entry_evidence"] = dict(lead.decision_entry_evidence)
    if lead.opinion_resolution_evidence is not None:
        payload["opinion_resolution_evidence"] = dict(lead.opinion_resolution_evidence)
    return DiscoveryHit(
        provider_hit_id=(
            f"{CASE_DEV_PROVISIONAL_FRONTIER_TERM}:"
            f"{frontier.success_candidate_set_sha256}:{lead.docket_id}"
        ),
        candidate_id=lead.candidate_id,
        payload=payload,
    )


def provisional_frontier_hit_provenance(
    *,
    candidate: RankedCaseDevCandidate,
    compact_commitment: Mapping[str, object],
    target_cycle_hash: str,
) -> dict[str, object]:
    """Bind one success to the constant-size authenticated partition projection."""

    return {
        "schema_version": CASE_DEV_PROVISIONAL_FRONTIER_SCHEMA,
        "docket_id": candidate.docket_id,
        "rank": candidate.rank,
        "ranking_key": list(candidate.ranking_key),
        "ranked_record_sha256": candidate.ranked_record_sha256,
        "case_dev_returned_courtlistener_url": candidate.returned_courtlistener_url,
        "target_cycle_hash": target_cycle_hash,
        **compact_commitment,
    }


def _progress_is_retryable(record: Mapping[str, object]) -> bool:
    if record.get("outcome") == "transient":
        return True
    payload = record.get("payload")
    typed_payload = (
        cast(Mapping[str, object], payload) if isinstance(payload, Mapping) else None
    )
    return (
        record.get("outcome") == "failure"
        and typed_payload is not None
        and typed_payload.get("reason") in _RETRYABLE_FAILURE_REASONS
    )


def _required_projection_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value or value != value.strip():
        raise RecapApiBatchDriverError(
            f"Case.dev source projection has invalid {field}"
        )
    if field == "docket_id" and _DOCKET_ID.fullmatch(value) is None:
        raise RecapApiBatchDriverError(
            "Case.dev source projection has invalid docket_id"
        )
    return value


def _read_regular_bytes(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RecapApiBatchDriverError(f"{label} must be a regular non-symlink file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RecapApiBatchDriverError(f"cannot read {label}: {exc}") from exc


def _json_object_from_bytes(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise RecapApiBatchDriverError(f"invalid JSON object {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecapApiBatchDriverError(f"JSON artifact is not an object: {label}")
    return cast(dict[str, object], value)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return _jsonl_from_bytes(_read_regular_bytes(path, str(path)), str(path))


def _jsonl_from_bytes(payload: bytes, label: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        for line in payload.splitlines():
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RecapApiBatchDriverError(
                    f"JSONL artifact contains a non-object: {label}"
                )
            records.append(cast(dict[str, object], value))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise RecapApiBatchDriverError(
            f"invalid JSONL artifact {label}: {exc}"
        ) from exc
    return records


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(_read_regular_bytes(path, str(path))).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

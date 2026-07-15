"""Source-bound Case.dev ranking projection and REST-batch selection."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.ingestion.case_dev_recap_enrichment import (
    CASE_DEV_RANKING_POLICY_VERSION,
    CaseDevRecapEnrichmentError,
    reconstruct_case_dev_recap_enrichment,
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

CASE_DEV_SOURCE_DOCKET_SCHEMA = "legalforecast.case_dev_recap_source_docket.v1"
CASE_DEV_RANKED_TRANSFER_TERM = "case-dev-ranked-opinion-transfer-v1"
CASE_DEV_RANKED_TRANSFER_SCHEMA = "legalforecast.case_dev_ranked_opinion_transfer.v1"
CASE_DEV_RANKED_SELECTION_RUN_SCHEMA = (
    "legalforecast.case_dev_ranked_rest_selection_run.v1"
)
_DOCKET_ID = re.compile(r"[1-9][0-9]*")
_API_DOCKET_PATH = re.compile(r"^/api/rest/v[1-9][0-9]*/dockets/([1-9][0-9]*)/$")
_PUBLIC_DOCKET_PATH = re.compile(r"^/docket/([1-9][0-9]*)/[^/]+/$")
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class RankedCaseDevCandidate:
    """One verified ranked enrichment selected for REST observation."""

    docket_id: str
    rank: int
    ranking_key: tuple[int, int, int, int, str]
    returned_courtlistener_url: str
    ranked_record_sha256: str

    def commitment_record(self) -> dict[str, object]:
        return {
            "docket_id": self.docket_id,
            "rank": self.rank,
            "ranking_key": list(self.ranking_key),
            "returned_courtlistener_url": self.returned_courtlistener_url,
            "ranked_record_sha256": self.ranked_record_sha256,
        }


@dataclass(frozen=True, slots=True)
class VerifiedCaseDevRankedSelection:
    """Authenticated top-N prefix of one completed free enrichment run."""

    source: DirectSearchSeedSource
    source_store_path: Path
    source_projection_path: Path
    ranked_path: Path
    enrichment_run_card_path: Path
    source_projection_sha256: str
    ranked_output_sha256: str
    enrichment_run_card_sha256: str
    ranked_candidate_count: int
    top_n: int
    selected_candidate_set_sha256: str
    selected: tuple[RankedCaseDevCandidate, ...]

    def commitment_record(self) -> dict[str, object]:
        return {
            "source_store_path": str(self.source_store_path),
            "source_batch_id": self.source.source_batch_id,
            "source_batch_digest": self.source.source_batch_digest,
            "source_cycle_hash": self.source.source_cycle_hash,
            "source_candidate_set_sha256": (self.source.source_candidate_set_sha256),
            "source_projection_path": str(self.source_projection_path),
            "source_projection_sha256": self.source_projection_sha256,
            "ranked_path": str(self.ranked_path),
            "ranked_output_sha256": self.ranked_output_sha256,
            "enrichment_run_card_path": str(self.enrichment_run_card_path),
            "enrichment_run_card_sha256": self.enrichment_run_card_sha256,
            "ranked_candidate_count": self.ranked_candidate_count,
            "top_n": self.top_n,
            "selected_candidate_set_sha256": self.selected_candidate_set_sha256,
            "selected": [candidate.commitment_record() for candidate in self.selected],
        }


@dataclass(frozen=True, slots=True)
class CaseDevRankedTargetPlan:
    """Pure commitment for materializing one ranked REST-observation batch."""

    batch_id: str
    target_cycle_hash: str
    target_batch_config: Mapping[str, object]
    target_batch_digest: str
    selection: VerifiedCaseDevRankedSelection

    def run_card_record(self) -> dict[str, object]:
        """Return the complete commitment required before target writes."""

        return _ranked_selection_run_card_record(
            batch_id=self.batch_id,
            target_cycle_hash=self.target_cycle_hash,
            target_batch_digest=self.target_batch_digest,
            leads_selected=len(self.selection.selected),
            selection=self.selection,
        )


@dataclass(frozen=True, slots=True)
class CaseDevRankedSeedResult:
    """Deterministic result of materializing the selected REST batch."""

    batch_id: str
    target_cycle_hash: str
    target_batch_digest: str
    leads_selected: int
    leads_seeded: int
    already_seeded: bool
    selection: VerifiedCaseDevRankedSelection

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": CASE_DEV_RANKED_SELECTION_RUN_SCHEMA,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "batch_id": self.batch_id,
            "target_cycle_hash": self.target_cycle_hash,
            "target_batch_digest": self.target_batch_digest,
            "leads_selected": self.leads_selected,
            "leads_seeded": self.leads_seeded,
            "already_seeded": self.already_seeded,
            **self.selection.commitment_record(),
        }

    def run_card_record(self) -> dict[str, object]:
        """Return a replay-stable commitment independent of resume state."""

        return _ranked_selection_run_card_record(
            batch_id=self.batch_id,
            target_cycle_hash=self.target_cycle_hash,
            target_batch_digest=self.target_batch_digest,
            leads_selected=self.leads_selected,
            selection=self.selection,
        )


def project_case_dev_opinion_source(
    source: DirectSearchSeedSource,
) -> tuple[dict[str, object], ...]:
    """Project an exhausted opinion batch into exact-ID lookup records."""

    if source.source_search_type != "o":
        raise RecapApiBatchDriverError(
            "Case.dev source ranking requires a CourtListener search_type=o batch"
        )
    projected: list[dict[str, object]] = []
    for lead in source.leads:
        raw_docket_id = cast(object, lead.docket_id)
        if (
            not isinstance(raw_docket_id, str)
            or _DOCKET_ID.fullmatch(raw_docket_id) is None
        ):
            raise RecapApiBatchDriverError(
                "opinion source lead has invalid docket identity"
            )
        source_hits = [hit.to_record() for hit in lead.source_hits]
        entry_keys = sorted({hit.provider_hit_id for hit in lead.source_hits})
        matched_terms = sorted({hit.query_term for hit in lead.source_hits})
        if not entry_keys or not matched_terms:
            raise RecapApiBatchDriverError(
                f"opinion source lead lacks frozen hit provenance: {lead.docket_id}"
            )
        projected.append(
            {
                "schema_version": CASE_DEV_SOURCE_DOCKET_SCHEMA,
                "candidate_id": lead.candidate_id,
                "docket_id": lead.docket_id,
                "entry_keys": entry_keys,
                "matched_terms": matched_terms,
                "eligibility_status": "potential_unverified",
                "source_lineage": {
                    "source_batch_id": source.source_batch_id,
                    "source_batch_digest": source.source_batch_digest,
                    "source_cycle_hash": source.source_cycle_hash,
                    "source_search_type": source.source_search_type,
                    "source_candidate_set_sha256": (source.source_candidate_set_sha256),
                    "docket_id": lead.docket_id,
                    "lead_commitment": lead.commitment_record(),
                    "source_hits": source_hits,
                },
            }
        )
    return tuple(projected)


def verify_case_dev_ranked_selection(
    *,
    source: DirectSearchSeedSource,
    source_store_path: Path,
    source_projection_path: Path,
    ranked_path: Path,
    enrichment_run_card_path: Path,
    expected_enrichment_run_card_sha256: str,
    top_n: int,
) -> VerifiedCaseDevRankedSelection:
    """Verify the complete enrichment lineage and return its exact top-N prefix."""

    if top_n <= 0:
        raise RecapApiBatchDriverError("top_n must be a positive integer")
    if _SHA256.fullmatch(expected_enrichment_run_card_sha256) is None:
        raise RecapApiBatchDriverError(
            "expected enrichment run-card SHA-256 must be 64 lowercase hex digits"
        )
    # Authenticate the exact bytes against the caller's out-of-band receipt before
    # parsing the card or trusting any of its internally self-reported commitments.
    run_card_sha256 = _file_sha256(enrichment_run_card_path)
    if run_card_sha256 != expected_enrichment_run_card_sha256:
        raise RecapApiBatchDriverError(
            "enrichment run-card SHA-256 does not match the external commitment"
        )
    run_card = _read_json_object(enrichment_run_card_path)
    expected_projection = list(project_case_dev_opinion_source(source))
    projection_records = _read_jsonl(source_projection_path)
    if projection_records != expected_projection:
        raise RecapApiBatchDriverError(
            "Case.dev source projection does not match the verified opinion source"
        )
    projection_sha256 = _file_sha256(source_projection_path)
    ranked_records = _read_jsonl(ranked_path)
    ranked_sha256 = _file_sha256(ranked_path)
    expected_commitments = {
        "ranking_policy_version": CASE_DEV_RANKING_POLICY_VERSION,
        "eligibility_anchor": CYCLE_1_ELIGIBILITY_ANCHOR.isoformat(),
        "source_batch_id": source.source_batch_id,
        "source_batch_digest": source.source_batch_digest,
        "source_cycle_hash": source.source_cycle_hash,
        "source_search_type": "o",
        "source_candidate_set_sha256": source.source_candidate_set_sha256,
        "source_projection_sha256": projection_sha256,
        "ranked_output_sha256": ranked_sha256,
    }
    if (
        run_card.get("schema_version")
        != "legalforecast.case_dev_recap_batch_summary.v1"
        or run_card.get("stage") != "enrich-recap-case-dev"
        or run_card.get("status") != "completed"
        or run_card.get("execute") is not True
        or run_card.get("dry_run") is not False
        or run_card.get("free_lookup_only") is not True
        or run_card.get("pacer_fee_acknowledgment_allowed") is not False
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or run_card.get("reconciled") is not True
        or run_card.get("failure_count") != 0
        or run_card.get("conversion_failure_count") != 0
        or run_card.get("enrichment_failure_count") != 0
        or run_card.get("input_record_count") != len(projection_records)
        or run_card.get("converted_docket_count") != len(projection_records)
        or run_card.get("enrichment_attempt_count") != len(projection_records)
        or run_card.get("successful_docket_count") != len(projection_records)
        or any(
            run_card.get(key) != value for key, value in expected_commitments.items()
        )
    ):
        raise RecapApiBatchDriverError(
            "Case.dev enrichment run card does not authenticate the ranked source"
        )
    if run_card.get("record_count") != len(ranked_records):
        raise RecapApiBatchDriverError(
            "Case.dev enrichment run card record count does not match ranked output"
        )
    _require_committed_path(run_card, "input_paths", source_store_path)
    _require_committed_path(run_card, "output_paths", source_projection_path)
    _require_committed_path(run_card, "output_paths", ranked_path)
    if top_n > len(ranked_records):
        raise RecapApiBatchDriverError(
            f"top_n={top_n} exceeds verified ranked candidates={len(ranked_records)}"
        )
    projection_by_docket = _projection_by_docket(projection_records)
    verified_ranked: list[RankedCaseDevCandidate] = []
    seen_dockets: set[str] = set()
    previous_key: tuple[int, int, int, int, str] | None = None
    for rank, record in enumerate(ranked_records, start=1):
        candidate = _verify_ranked_record(
            record,
            rank=rank,
            projection_by_docket=projection_by_docket,
        )
        if candidate.docket_id in seen_dockets:
            raise RecapApiBatchDriverError(
                f"ranked output repeats docket {candidate.docket_id}"
            )
        if previous_key is not None and candidate.ranking_key < previous_key:
            raise RecapApiBatchDriverError("ranked output is not in canonical order")
        seen_dockets.add(candidate.docket_id)
        previous_key = candidate.ranking_key
        verified_ranked.append(candidate)
    if seen_dockets != set(projection_by_docket):
        raise RecapApiBatchDriverError(
            "ranked successes do not exactly cover the verified source projection"
        )
    selected = tuple(verified_ranked[:top_n])
    selected_sha256 = _canonical_sha256(
        [candidate.commitment_record() for candidate in selected]
    )
    return VerifiedCaseDevRankedSelection(
        source=source,
        source_store_path=source_store_path,
        source_projection_path=source_projection_path,
        ranked_path=ranked_path,
        enrichment_run_card_path=enrichment_run_card_path,
        source_projection_sha256=projection_sha256,
        ranked_output_sha256=ranked_sha256,
        enrichment_run_card_sha256=run_card_sha256,
        ranked_candidate_count=len(verified_ranked),
        top_n=top_n,
        selected_candidate_set_sha256=selected_sha256,
        selected=selected,
    )


def build_case_dev_ranked_target_plan(
    *,
    batch_id: str,
    target_cycle_hash: str,
    selection: VerifiedCaseDevRankedSelection,
    page_size: int = 100,
) -> CaseDevRankedTargetPlan:
    """Build the exact target commitment without mutating its cycle store."""

    if not 1 <= page_size <= 100:
        raise RecapApiBatchDriverError("page_size must be from 1 through 100")
    source = selection.source
    if batch_id == source.source_batch_id:
        raise RecapApiBatchDriverError(
            "ranked selection target batch must differ from its source batch"
        )
    if _SHA256.fullmatch(target_cycle_hash) is None:
        raise RecapApiBatchDriverError(
            "target cycle hash must be 64 lowercase hex digits"
        )
    config = build_recap_api_batch_config(
        decision_window_start=source.search_window_start,
        decision_window_end=source.search_window_end,
        auth_mode="authenticated",
        query_terms=(CASE_DEV_RANKED_TRANSFER_TERM,),
        page_size=page_size,
        top_k_per_term=selection.top_n,
    )
    config.update(
        {
            "discovery_mode": CASE_DEV_RANKED_TRANSFER_SCHEMA,
            "selection_semantics": "exact_case_dev_ranked_prefix",
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_cycle_hash": source.source_cycle_hash,
            "target_cycle_hash": target_cycle_hash,
            "source_candidate_count": len(source.leads),
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "source_projection_sha256": selection.source_projection_sha256,
            "ranked_output_sha256": selection.ranked_output_sha256,
            "enrichment_run_card_sha256": selection.enrichment_run_card_sha256,
            "ranked_candidate_count": selection.ranked_candidate_count,
            "selected_candidate_count": len(selection.selected),
            "selected_candidate_set_sha256": selection.selected_candidate_set_sha256,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
    )
    return CaseDevRankedTargetPlan(
        batch_id=batch_id,
        target_cycle_hash=target_cycle_hash,
        target_batch_config=config,
        target_batch_digest=_canonical_json_sha256(config),
        selection=selection,
    )


def seed_case_dev_ranked_selection(
    store: CycleAcquisitionStore,
    *,
    plan: CaseDevRankedTargetPlan,
    page_size: int = 100,
) -> CaseDevRankedSeedResult:
    """Materialize a source-bound top-N batch for the existing REST observer."""

    if not 1 <= page_size <= 100:
        raise RecapApiBatchDriverError("page_size must be from 1 through 100")
    if plan.target_batch_config.get("page_size") != page_size:
        raise RecapApiBatchDriverError(
            "ranked selection replay page size differs from its frozen plan"
        )
    batch_id = plan.batch_id
    selection = plan.selection
    source = selection.source
    target_cycle_hash = store.cycle_hash
    if target_cycle_hash != plan.target_cycle_hash:
        raise RecapApiBatchDriverError(
            "target cycle hash changed after ranked-selection planning"
        )
    target_batch_digest = store.ensure_batch(batch_id, plan.target_batch_config)
    if target_batch_digest != plan.target_batch_digest:
        raise RecapApiBatchDriverError(
            "target batch digest differs from ranked-selection plan"
        )
    store.ensure_terms(batch_id, (CASE_DEV_RANKED_TRANSFER_TERM,))
    initial_progress = store.term_progress(batch_id, CASE_DEV_RANKED_TRANSFER_TERM)
    if initial_progress.hit_count > len(selection.selected):
        raise RecapApiBatchDriverError(
            "ranked selection progress exceeds the frozen top-N prefix"
        )
    lead_by_docket = {lead.docket_id: lead for lead in source.leads}
    expected_hits = tuple(
        _ranked_candidate_hit(
            candidate,
            lead=lead_by_docket[candidate.docket_id],
            selection=selection,
            target_cycle_hash=target_cycle_hash,
        )
        for candidate in selection.selected
    )
    offset = 0
    request_cursor: str | None = None
    while offset < len(selection.selected):
        next_offset = min(offset + page_size, len(selection.selected))
        next_cursor = (
            str(next_offset) if next_offset < len(selection.selected) else None
        )
        terminal = None if next_cursor is not None else TermTerminalStatus.EXHAUSTED
        store.commit_search_page(
            batch_id,
            CASE_DEV_RANKED_TRANSFER_TERM,
            request_cursor,
            expected_hits[offset:next_offset],
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
        offset = next_offset
        request_cursor = next_cursor
    final_progress = store.term_progress(batch_id, CASE_DEV_RANKED_TRANSFER_TERM)
    expected_stored_hits = tuple(
        sorted(expected_hits, key=lambda hit: hit.candidate_id)
    )
    if (
        final_progress.hit_count != len(selection.selected)
        or final_progress.terminal_status != TermTerminalStatus.EXHAUSTED
        or store.candidate_discovery_hits(batch_id) != expected_stored_hits
    ):
        raise RecapApiBatchDriverError(
            "materialized ranked selection does not match its deterministic pages"
        )
    already_seeded = (
        initial_progress.terminal_status == TermTerminalStatus.EXHAUSTED
        and initial_progress.hit_count == len(selection.selected)
    )
    return CaseDevRankedSeedResult(
        batch_id=batch_id,
        target_cycle_hash=target_cycle_hash,
        target_batch_digest=target_batch_digest,
        leads_selected=len(selection.selected),
        leads_seeded=(
            0
            if already_seeded
            else len(selection.selected) - initial_progress.hit_count
        ),
        already_seeded=already_seeded,
        selection=selection,
    )


def _projection_by_docket(
    records: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    projected: dict[str, Mapping[str, object]] = {}
    for record in records:
        docket_id = record.get("docket_id")
        if not isinstance(docket_id, str) or _DOCKET_ID.fullmatch(docket_id) is None:
            raise RecapApiBatchDriverError(
                "Case.dev source projection has invalid docket_id"
            )
        if docket_id in projected:
            raise RecapApiBatchDriverError(
                f"Case.dev source projection repeats docket {docket_id}"
            )
        projected[docket_id] = record
    return projected


def _ranked_selection_run_card_record(
    *,
    batch_id: str,
    target_cycle_hash: str,
    target_batch_digest: str,
    leads_selected: int,
    selection: VerifiedCaseDevRankedSelection,
) -> dict[str, object]:
    return {
        "schema_version": CASE_DEV_RANKED_SELECTION_RUN_SCHEMA,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "batch_id": batch_id,
        "target_cycle_hash": target_cycle_hash,
        "target_batch_digest": target_batch_digest,
        "leads_selected": leads_selected,
        **selection.commitment_record(),
    }


def _ranked_candidate_hit(
    candidate: RankedCaseDevCandidate,
    *,
    lead: DirectSearchLead,
    selection: VerifiedCaseDevRankedSelection,
    target_cycle_hash: str,
) -> DiscoveryHit:
    source = selection.source
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
        "query_term": CASE_DEV_RANKED_TRANSFER_TERM,
        "case_dev_ranked_selection_provenance": {
            "schema_version": CASE_DEV_RANKED_TRANSFER_SCHEMA,
            "rank": candidate.rank,
            "ranking_key": list(candidate.ranking_key),
            "ranked_record_sha256": candidate.ranked_record_sha256,
            "case_dev_returned_courtlistener_url": (
                candidate.returned_courtlistener_url
            ),
            "source_batch_id": source.source_batch_id,
            "source_batch_digest": source.source_batch_digest,
            "source_cycle_hash": source.source_cycle_hash,
            "target_cycle_hash": target_cycle_hash,
            "source_candidate_set_sha256": source.source_candidate_set_sha256,
            "source_projection_sha256": selection.source_projection_sha256,
            "ranked_output_sha256": selection.ranked_output_sha256,
            "enrichment_run_card_sha256": selection.enrichment_run_card_sha256,
            "selected_candidate_set_sha256": (selection.selected_candidate_set_sha256),
        },
    }
    if lead.decision_entry_evidence is not None:
        payload["decision_entry_evidence"] = dict(lead.decision_entry_evidence)
    if lead.opinion_resolution_evidence is not None:
        payload["opinion_resolution_evidence"] = dict(lead.opinion_resolution_evidence)
    return DiscoveryHit(
        provider_hit_id=(
            f"{CASE_DEV_RANKED_TRANSFER_TERM}:"
            f"{selection.selected_candidate_set_sha256}:{lead.docket_id}"
        ),
        candidate_id=lead.candidate_id,
        payload=payload,
    )


def _verify_ranked_record(
    record: Mapping[str, object],
    *,
    rank: int,
    projection_by_docket: Mapping[str, Mapping[str, object]],
) -> RankedCaseDevCandidate:
    try:
        enrichment = reconstruct_case_dev_recap_enrichment(record)
    except CaseDevRecapEnrichmentError as exc:
        raise RecapApiBatchDriverError(
            f"ranked record semantics are invalid at rank {rank}: {exc}"
        ) from exc
    if enrichment.eligibility_anchor != CYCLE_1_ELIGIBILITY_ANCHOR:
        raise RecapApiBatchDriverError(
            "ranked record does not use the frozen cycle-1 eligibility anchor"
        )
    if record.get("ranking_policy_version") != CASE_DEV_RANKING_POLICY_VERSION:
        raise RecapApiBatchDriverError(
            "ranked record lacks the current eligibility-aware ranking policy"
        )
    identity = record.get("identity")
    if not isinstance(identity, Mapping):
        raise RecapApiBatchDriverError("ranked record lacks identity")
    typed_identity = cast(Mapping[str, object], identity)
    docket_id = typed_identity.get("courtlistener_docket_id")
    if not isinstance(docket_id, str) or _DOCKET_ID.fullmatch(docket_id) is None:
        raise RecapApiBatchDriverError("ranked record has invalid docket identity")
    if typed_identity.get("case_dev_id") != docket_id:
        raise RecapApiBatchDriverError("ranked record Case.dev ID does not match")
    case_dev_url = typed_identity.get("case_dev_url")
    courtlistener_url = typed_identity.get("courtlistener_url")
    if (
        not isinstance(case_dev_url, str)
        or courtlistener_url != case_dev_url
        or _courtlistener_url_docket_id(case_dev_url) != docket_id
    ):
        raise RecapApiBatchDriverError(
            "ranked record lacks a verified Case.dev-returned CourtListener URL"
        )
    projection = projection_by_docket.get(docket_id)
    if projection is None or record.get("source_lineage") != projection.get(
        "source_lineage"
    ):
        raise RecapApiBatchDriverError(
            f"ranked record source lineage mismatch for docket {docket_id}"
        )
    integer_fields = (
        "structural_priority_tier",
        "decision_signal_priority_tier",
        "missing_required_document_count",
        "required_document_count",
    )
    integers: list[int] = []
    for field_name in integer_fields:
        value = record.get(field_name)
        if type(value) is not int or value < 0:
            raise RecapApiBatchDriverError(
                f"ranked record has invalid {field_name} for docket {docket_id}"
            )
        integers.append(value)
    expected_key = (*integers, docket_id)
    raw_key = record.get("ranking_key")
    if (
        not isinstance(raw_key, list)
        or tuple(cast(list[object], raw_key)) != expected_key
    ):
        raise RecapApiBatchDriverError(
            f"ranked record ranking key mismatch for docket {docket_id}"
        )
    return RankedCaseDevCandidate(
        docket_id=docket_id,
        rank=rank,
        ranking_key=cast(tuple[int, int, int, int, str], expected_key),
        returned_courtlistener_url=case_dev_url,
        ranked_record_sha256=_canonical_sha256(record),
    )


def _courtlistener_url_docket_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.courtlistener.com"
        or parsed.query
        or parsed.fragment
    ):
        return None
    for pattern in (_API_DOCKET_PATH, _PUBLIC_DOCKET_PATH):
        match = pattern.fullmatch(parsed.path)
        if match is not None:
            return match.group(1)
    return None


def _require_committed_path(
    run_card: Mapping[str, object], field_name: str, expected: Path
) -> None:
    raw_paths = run_card.get(field_name)
    if not isinstance(raw_paths, list):
        raise RecapApiBatchDriverError(f"run card lacks valid {field_name}")
    typed_paths = cast(list[object], raw_paths)
    if not all(isinstance(path, str) for path in typed_paths):
        raise RecapApiBatchDriverError(f"run card lacks valid {field_name}")
    expected_resolved = expected.resolve()
    if expected_resolved not in {
        Path(cast(str, path)).resolve() for path in typed_paths
    }:
        raise RecapApiBatchDriverError(
            f"run card does not commit expected {field_name}: {expected}"
        )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        records = [json.loads(line) for line in path.read_text().splitlines() if line]
    except (OSError, json.JSONDecodeError) as exc:
        raise RecapApiBatchDriverError(f"invalid JSONL artifact {path}: {exc}") from exc
    if not all(isinstance(record, dict) for record in records):
        raise RecapApiBatchDriverError(f"JSONL artifact contains non-objects: {path}")
    return [cast(dict[str, object], record) for record in records]


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RecapApiBatchDriverError(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecapApiBatchDriverError(f"JSON artifact is not an object: {path}")
    return cast(dict[str, object], value)


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RecapApiBatchDriverError(f"cannot hash artifact {path}: {exc}") from exc


def _canonical_sha256(value: Mapping[str, object] | Sequence[object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    """Match ``CycleAcquisitionStore.ensure_batch`` canonicalization exactly."""

    try:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RecapApiBatchDriverError(
            f"target batch config is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(canonical.encode()).hexdigest()

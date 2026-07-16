"""Acquire ranked CourtListener dockets through the canonical Firecrawl ledger."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.case_dev_provisional_frontier import (
    CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA,
    CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS,
    CASE_DEV_PROVISIONAL_FRONTIER_TERM,
    provisional_frontier_hit_provenance,
    ranked_records_for_provisional_frontier,
    verify_case_dev_provisional_frontier,
)
from legalforecast.ingestion.case_dev_ranked_selection import (
    CASE_DEV_RANKED_SELECTION_RUN_SCHEMA,
    CASE_DEV_RANKED_SUBSET_SELECTION_RUN_SCHEMA,
)
from legalforecast.ingestion.courtlistener_opinion_discovery import (
    OPINION_API_POLICY_SCHEMA,
)
from legalforecast.ingestion.courtlistener_unrestricted_recap_discovery import (
    UNRESTRICTED_RECAP_POLICY_SCHEMA,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketBundle,
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
    may_stop_at_anchor_boundary,
    paginate_courtlistener_docket,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    courtlistener_public_docket_url_from_case_dev,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    RecapApiBatchDriverError,
    read_saturated_direct_search_leads,
)
from legalforecast.ingestion.recap_api_discovery import RECAP_API_PROVIDER


class BudgetedDocketAcquisitionError(ValueError):
    """Raised when ranked input cannot produce a complete screening artifact."""


_SHA256 = re.compile(r"[0-9a-f]{64}")
_RANKED_PREFIX_TERM = "case-dev-ranked-opinion-transfer-v1"
_RANKED_SUBSET_TERM = "case-dev-ranked-opinion-subset-transfer-v1"
_AUTHENTICATED_HANDOFF_COMMITMENTS = (
    "source_batch_id",
    "source_batch_digest",
    "source_cycle_hash",
    "source_schema_version",
    "source_search_type",
    "source_available_only",
    "source_query_expression",
    "source_query_terms",
    "source_search_window_start",
    "source_search_window_end",
    "source_query_commitment_sha256",
    "source_candidate_set_sha256",
    "source_hit_set_sha256",
    "source_projection_sha256",
    "ranked_output_sha256",
    "enrichment_run_card_sha256",
    "selected_candidate_set_sha256",
)
_AUTHENTICATED_SELECTION_SEMANTICS = frozenset(
    {
        "exact_case_dev_ranked_prefix",
        "exact_case_dev_ranked_subset",
        CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS,
    }
)
_PROVISIONAL_HANDOFF_COMMITMENTS = (
    "source_batch_id",
    "source_batch_digest",
    "source_cycle_hash",
    "source_schema_version",
    "source_search_type",
    "source_available_only",
    "source_query_expression",
    "source_query_terms",
    "source_search_window_start",
    "source_search_window_end",
    "source_query_commitment_sha256",
    "source_candidate_set_sha256",
    "source_hit_set_sha256",
    "source_projection_sha256",
    "progress_config_sha256",
    "progress_sha256",
    "success_candidate_set_sha256",
    "terminal_excluded_candidate_set_sha256",
    "pending_candidate_set_sha256",
    "selected_candidate_set_sha256",
)
_PROVISIONAL_LINEAGE = {
    "provisional_frontier": True,
    "final_cohort_eligible": False,
    "full_source_terminal": False,
}
_PROVISIONAL_PROPAGATED_FIELDS = (
    "source_candidate_count",
    "source_candidate_set_sha256",
    "source_projection_sha256",
    "progress_config_sha256",
    "progress_sha256",
    "success_count",
    "terminal_exclusion_count",
    "pending_count",
    "success_candidate_set_sha256",
    "terminal_excluded_candidate_set_sha256",
    "pending_candidate_set_sha256",
)


@dataclass(frozen=True, slots=True)
class RankedDocketTarget:
    """Validated selective acquisition target from free Case.dev ranking."""

    candidate_id: str
    docket_id: str
    docket_url: str
    rank: int


@dataclass(frozen=True, slots=True)
class BudgetedDocketAcquisitionResult:
    """Only complete-for-window bundles, in Case.dev cost order."""

    bundles: tuple[CourtListenerDocketBundle, ...]
    failures: tuple[DocketAcquisitionFailure, ...]
    credit_summary: Mapping[str, object]

    @property
    def failed_docket_ids(self) -> tuple[str, ...]:
        """Return failed docket IDs in deterministic Case.dev rank order."""

        return tuple(failure.docket_id for failure in self.failures)


@dataclass(frozen=True, slots=True)
class DocketAcquisitionFailure:
    """Candidate-local terminal failure safe for the public exclusion ledger."""

    candidate_id: str
    docket_id: str
    reason: str
    failure_stage: str
    failure_reason: str

    def as_record(self) -> dict[str, str]:
        """Render the deterministic acquisition failure/exclusion record."""

        return {
            "case_id": self.candidate_id,
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "reason": self.reason,
            "failure_stage": self.failure_stage,
            "failure_reason": self.failure_reason,
        }


def ranked_parent_requires_authenticated_handoff(
    store: CycleAcquisitionStore,
    parent_batch_id: str,
) -> bool:
    """Derive source-bound authentication from one frozen parent batch."""

    try:
        parent_config = store.batch_config(parent_batch_id)
    except KeyError as exc:
        raise BudgetedDocketAcquisitionError("ranked parent batch is missing") from exc
    return parent_config.get(
        "selection_semantics"
    ) in _AUTHENTICATED_SELECTION_SEMANTICS or any(
        field in parent_config for field in _AUTHENTICATED_HANDOFF_COMMITMENTS
    )


def verify_authenticated_ranked_firecrawl_handoff(
    *,
    store: CycleAcquisitionStore,
    parent_batch_id: str,
    ranked_path: Path,
    selection_run_card_path: Path,
    expected_selection_run_card_sha256: str,
    max_candidates: int,
) -> tuple[dict[str, Any], ...]:
    """Return the exact authenticated prefix/subset authorized for Firecrawl."""

    if _SHA256.fullmatch(expected_selection_run_card_sha256) is None:
        raise BudgetedDocketAcquisitionError(
            "expected ranked-selection run-card SHA-256 is invalid"
        )
    try:
        run_card_bytes = selection_run_card_path.read_bytes()
        ranked_bytes = ranked_path.read_bytes()
        run_card_value = json.loads(run_card_bytes)
        ranked_values = [json.loads(line) for line in ranked_bytes.splitlines() if line]
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise BudgetedDocketAcquisitionError(
            f"authenticated ranked handoff artifact is unreadable: {exc}"
        ) from exc
    run_card_sha256 = hashlib.sha256(run_card_bytes).hexdigest()
    if run_card_sha256 != expected_selection_run_card_sha256:
        raise BudgetedDocketAcquisitionError(
            "ranked-selection run card does not match its external SHA-256"
        )
    if not isinstance(run_card_value, dict) or not all(
        isinstance(record, dict) for record in ranked_values
    ):
        raise BudgetedDocketAcquisitionError(
            "authenticated ranked handoff artifacts must contain JSON objects"
        )
    run_card = cast(dict[str, object], run_card_value)
    ranked = [cast(dict[str, Any], record) for record in ranked_values]
    schema = run_card.get("schema_version")
    if schema == CASE_DEV_RANKED_SELECTION_RUN_SCHEMA:
        selection_semantics = "exact_case_dev_ranked_prefix"
        transfer_term = _RANKED_PREFIX_TERM
        provisional = False
    elif schema == CASE_DEV_RANKED_SUBSET_SELECTION_RUN_SCHEMA:
        selection_semantics = "exact_case_dev_ranked_subset"
        transfer_term = _RANKED_SUBSET_TERM
        provisional = False
    elif schema == CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA:
        selection_semantics = CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS
        transfer_term = CASE_DEV_PROVISIONAL_FRONTIER_TERM
        provisional = True
    else:
        raise BudgetedDocketAcquisitionError(
            "ranked-selection run card uses an unsupported schema"
        )
    source_search_type = run_card.get("source_search_type")
    source_schema = run_card.get("source_schema_version")
    source_available_only = run_card.get("source_available_only")
    source_query_expression = run_card.get("source_query_expression")
    if source_search_type == "o":
        source_supported = (
            source_schema == OPINION_API_POLICY_SCHEMA
            and source_available_only == "absent"
            and source_query_expression is None
        )
    elif source_search_type == "r":
        source_supported = (
            source_schema == UNRESTRICTED_RECAP_POLICY_SCHEMA
            and source_available_only == "omitted"
            and source_query_expression
            == "{term} AND entry_date_filed:[{start} TO {end}]"
        )
    else:
        source_supported = False
    if not source_supported:
        raise BudgetedDocketAcquisitionError(
            "ranked-selection source schema/type substitution is not permitted"
        )
    raw_source_query_terms = run_card.get("source_query_terms")
    if not isinstance(raw_source_query_terms, list):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection source query terms are invalid"
        )
    source_query_term_values = cast(list[object], raw_source_query_terms)
    if not all(
        isinstance(term, str) and bool(term) and term == term.strip()
        for term in source_query_term_values
    ):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection source query terms are invalid"
        )
    source_query_terms = cast(list[str], source_query_term_values)
    query_commitment: dict[str, object] = {
        "source_schema_version": source_schema,
        "source_search_type": source_search_type,
        "source_available_only": source_available_only,
        "source_query_expression": source_query_expression,
        "source_query_terms": source_query_terms,
        "source_search_window_start": run_card.get("source_search_window_start"),
        "source_search_window_end": run_card.get("source_search_window_end"),
    }
    if run_card.get("source_query_commitment_sha256") != _canonical_record_sha256(
        query_commitment
    ):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection source query commitment does not reconcile"
        )
    required_hash_fields = (
        "source_batch_digest",
        "source_cycle_hash",
        "source_query_commitment_sha256",
        "source_candidate_set_sha256",
        "source_hit_set_sha256",
        "source_projection_sha256",
        "ranked_output_sha256",
        "selected_candidate_set_sha256",
        *(
            (
                "progress_config_sha256",
                "progress_sha256",
                "success_candidate_set_sha256",
                "terminal_excluded_candidate_set_sha256",
                "pending_candidate_set_sha256",
            )
            if provisional
            else ("enrichment_run_card_sha256",)
        ),
    )
    for field in required_hash_fields:
        value = run_card.get(field)
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise BudgetedDocketAcquisitionError(
                f"ranked-selection run card has invalid {field}"
            )
    if (
        run_card.get("provider_activity_requested") is not False
        or run_card.get("provider_activity_executed") is not False
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or (
            provisional
            and (
                run_card.get("pacer_fee_acknowledgment_allowed") is not False
                or run_card.get("provisional_frontier") is not True
                or run_card.get("final_cohort_eligible") is not False
                or run_card.get("full_source_terminal") is not False
            )
        )
        or run_card.get("batch_id") != parent_batch_id
        or run_card.get("target_cycle_hash") != store.cycle_hash
        or run_card.get("ranked_output_sha256")
        != hashlib.sha256(ranked_bytes).hexdigest()
        or run_card.get("ranked_candidate_count") != len(ranked)
    ):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection run card does not authenticate the Firecrawl input"
        )
    try:
        parent_config = store.batch_config(parent_batch_id)
        parent_digest = store.batch_digest(parent_batch_id)
        parent_progress = store.term_progress(parent_batch_id, transfer_term)
    except KeyError as exc:
        raise BudgetedDocketAcquisitionError(
            "ranked-selection parent batch is missing"
        ) from exc
    if (
        run_card.get("target_batch_digest") != parent_digest
        or parent_config.get("selection_semantics") != selection_semantics
        or parent_config.get("query_terms") != [transfer_term]
        or parent_progress.terminal_status != TermTerminalStatus.EXHAUSTED
        or any(
            field not in run_card or parent_config.get(field) != run_card.get(field)
            for field in (
                _PROVISIONAL_HANDOFF_COMMITMENTS
                if provisional
                else _AUTHENTICATED_HANDOFF_COMMITMENTS
            )
        )
    ):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection parent batch does not match the authenticated run card"
        )
    raw_selected = run_card.get("selected")
    leads_selected = run_card.get("leads_selected")
    if not isinstance(raw_selected, list):
        raise BudgetedDocketAcquisitionError(
            "ranked-selection selected commitments must be an array"
        )
    selected = cast(list[object], raw_selected)
    if (
        type(leads_selected) is not int
        or leads_selected <= 0
        or leads_selected != len(selected)
        or max_candidates != leads_selected
        or parent_config.get("selected_candidate_count") != leads_selected
        or parent_progress.hit_count != leads_selected
    ):
        raise BudgetedDocketAcquisitionError(
            "Firecrawl max-candidates must equal the complete authenticated selection"
        )
    selected_objects: list[Mapping[str, object]] = []
    selected_records: list[dict[str, Any]] = []
    seen_dockets: set[str] = set()
    seen_ranks: set[int] = set()
    for raw_commitment in selected:
        if not isinstance(raw_commitment, Mapping):
            raise BudgetedDocketAcquisitionError(
                "ranked-selection selected commitment is invalid"
            )
        commitment = cast(Mapping[str, object], raw_commitment)
        if set(commitment) != {
            "docket_id",
            "rank",
            "ranking_key",
            "returned_courtlistener_url",
            "ranked_record_sha256",
        }:
            raise BudgetedDocketAcquisitionError(
                "ranked-selection selected commitment has unexpected fields"
            )
        docket_id = commitment.get("docket_id")
        rank = commitment.get("rank")
        if (
            not isinstance(docket_id, str)
            or not docket_id.isascii()
            or not re.fullmatch(r"[1-9][0-9]*", docket_id)
            or type(rank) is not int
            or rank <= 0
            or rank > len(ranked)
            or docket_id in seen_dockets
            or rank in seen_ranks
        ):
            raise BudgetedDocketAcquisitionError(
                "ranked-selection selected identity/rank is invalid"
            )
        record = ranked[rank - 1]
        identity = record.get("identity")
        if not isinstance(identity, Mapping):
            raise BudgetedDocketAcquisitionError(
                "authenticated ranked record lacks identity"
            )
        typed_identity = cast(Mapping[str, object], identity)
        if (
            typed_identity.get("courtlistener_docket_id") != docket_id
            or typed_identity.get("courtlistener_url")
            != commitment.get("returned_courtlistener_url")
            or record.get("ranking_key") != commitment.get("ranking_key")
            or _canonical_record_sha256(record)
            != commitment.get("ranked_record_sha256")
        ):
            raise BudgetedDocketAcquisitionError(
                f"authenticated ranked record mismatch for docket {docket_id}"
            )
        seen_dockets.add(docket_id)
        seen_ranks.add(rank)
        screening_metadata = record.get("screening_metadata")
        if not isinstance(screening_metadata, Mapping):
            raise BudgetedDocketAcquisitionError(
                f"authenticated ranked record lacks screening metadata for {docket_id}"
            )
        case_name = cast(Mapping[str, object], screening_metadata).get("case_name")
        if (
            not isinstance(case_name, str)
            or not case_name
            or case_name != case_name.strip()
        ):
            raise BudgetedDocketAcquisitionError(
                "authenticated ranked record lacks a canonical case name for "
                f"{docket_id}"
            )
        public_url = courtlistener_public_docket_url_from_case_dev(
            {"docket_id": docket_id, "case_name": case_name}
        )
        if public_url is None:
            raise BudgetedDocketAcquisitionError(
                f"authenticated public docket URL cannot be derived for {docket_id}"
            )
        handoff_identity = dict(typed_identity)
        handoff_identity["courtlistener_url"] = public_url
        handoff_record = dict(record)
        handoff_record["identity"] = handoff_identity
        selected_objects.append(commitment)
        selected_records.append(handoff_record)
    selected_ranks = [cast(int, item["rank"]) for item in selected_objects]
    if selected_ranks != sorted(selected_ranks):
        raise BudgetedDocketAcquisitionError(
            "authenticated selected ranks are not in canonical order"
        )
    if selection_semantics == "exact_case_dev_ranked_prefix":
        if (
            selected_ranks != list(range(1, leads_selected + 1))
            or run_card.get("top_n") != leads_selected
        ):
            raise BudgetedDocketAcquisitionError(
                "authenticated prefix is not the exact ranked prefix"
            )
    elif selection_semantics == "exact_case_dev_ranked_subset" and run_card.get(
        "selected_docket_ids"
    ) != [cast(str, item["docket_id"]) for item in selected_objects]:
        raise BudgetedDocketAcquisitionError(
            "authenticated subset docket list does not reconcile"
        )
    if run_card.get("selected_candidate_set_sha256") != _canonical_record_sha256(
        selected_objects
    ):
        raise BudgetedDocketAcquisitionError(
            "authenticated selected candidate-set commitment does not reconcile"
        )
    expected_parent_ids = tuple(
        sorted(f"courtlistener-docket-{docket_id}" for docket_id in seen_dockets)
    )
    if store.candidate_ids(parent_batch_id) != expected_parent_ids:
        raise BudgetedDocketAcquisitionError(
            "ranked-selection parent candidates do not exactly reconcile"
        )
    if provisional:
        _verify_provisional_firecrawl_partition(
            store=store,
            parent_batch_id=parent_batch_id,
            run_card=run_card,
            parent_config=parent_config,
            ranked_path=ranked_path,
        )
    return tuple(selected_records)


def _verify_provisional_firecrawl_partition(
    *,
    store: CycleAcquisitionStore,
    parent_batch_id: str,
    run_card: Mapping[str, object],
    parent_config: Mapping[str, object],
    ranked_path: Path,
) -> None:
    """Re-derive the provisional source partition before Firecrawl authorization."""

    if (
        parent_config.get("provisional_frontier") is not True
        or parent_config.get("final_cohort_eligible") is not False
        or parent_config.get("full_source_terminal") is not False
    ):
        raise BudgetedDocketAcquisitionError(
            "provisional parent batch lacks fail-closed cohort flags"
        )
    required_paths: dict[str, Path] = {}
    for field in (
        "source_store_path",
        "source_projection_path",
        "progress_config_path",
        "progress_path",
    ):
        value = run_card.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            raise BudgetedDocketAcquisitionError(
                f"provisional run card has invalid {field}"
            )
        required_paths[field] = Path(value)
    source_batch_id = run_card.get("source_batch_id")
    progress_sha256 = run_card.get("progress_sha256")
    if not isinstance(source_batch_id, str) or not isinstance(progress_sha256, str):
        raise BudgetedDocketAcquisitionError(
            "provisional run card lacks source/progress identity"
        )
    try:
        source = read_saturated_direct_search_leads(
            required_paths["source_store_path"],
            source_batch_id=source_batch_id,
        )
        frontier = verify_case_dev_provisional_frontier(
            source=source,
            source_store_path=required_paths["source_store_path"],
            source_projection_path=required_paths["source_projection_path"],
            progress_config_path=required_paths["progress_config_path"],
            progress_path=required_paths["progress_path"],
            expected_progress_config_sha256=cast(
                str, run_card["progress_config_sha256"]
            ),
            expected_progress_sha256=progress_sha256,
        )
    except (OSError, RecapApiBatchDriverError, ValueError) as exc:
        raise BudgetedDocketAcquisitionError(
            f"provisional source partition cannot be authenticated: {exc}"
        ) from exc
    commitments = frontier.commitment_record()
    if any(
        run_card.get(field) != value or parent_config.get(field) != value
        for field, value in commitments.items()
    ):
        raise BudgetedDocketAcquisitionError(
            "provisional success/exclusion/pending partition does not reconcile"
        )
    compact_commitment = frontier.compact_commitment_record()
    candidate_by_docket = {
        candidate.docket_id: candidate for candidate in frontier.selected
    }
    lead_by_docket = {lead.docket_id: lead for lead in frontier.source.leads}
    persisted_hits = store.candidate_discovery_hits(parent_batch_id)
    if len(persisted_hits) != len(candidate_by_docket):
        raise BudgetedDocketAcquisitionError(
            "provisional parent lacks exact compact provisional provenance"
        )
    for hit in persisted_hits:
        payload = hit.payload
        docket_id = payload.get("docket_id")
        candidate = (
            candidate_by_docket.get(docket_id) if isinstance(docket_id, str) else None
        )
        lead = lead_by_docket.get(docket_id) if isinstance(docket_id, str) else None
        expected_provenance = (
            provisional_frontier_hit_provenance(
                candidate=candidate,
                compact_commitment=compact_commitment,
                target_cycle_hash=store.cycle_hash,
            )
            if candidate is not None
            else None
        )
        if (
            candidate is None
            or lead is None
            or hit.candidate_id != lead.candidate_id
            or payload.get("candidate_id") != lead.candidate_id
            or payload.get("courtlistener_docket_id") != docket_id
            or payload.get("query_term") != CASE_DEV_PROVISIONAL_FRONTIER_TERM
            or payload.get("provider") != RECAP_API_PROVIDER
            or hit.provider_hit_id
            != (
                f"{CASE_DEV_PROVISIONAL_FRONTIER_TERM}:"
                f"{frontier.success_candidate_set_sha256}:{docket_id}"
            )
            or payload.get("case_dev_provisional_frontier_provenance")
            != expected_provenance
        ):
            raise BudgetedDocketAcquisitionError(
                "provisional parent changed compact provisional provenance"
            )
    ranked_bytes = b"".join(
        json.dumps(record, sort_keys=True).encode() + b"\n"
        for record in ranked_records_for_provisional_frontier(frontier)
    )
    if (
        ranked_path.read_bytes() != ranked_bytes
        or run_card.get("ranked_output_sha256")
        != hashlib.sha256(ranked_bytes).hexdigest()
        or run_card.get("success_count") != len(frontier.selected)
        or run_card.get("terminal_exclusion_count") != len(frontier.terminal_exclusions)
        or run_card.get("pending_count") != len(frontier.pending)
        or len(frontier.selected)
        + len(frontier.terminal_exclusions)
        + len(frontier.pending)
        != frontier.source_candidate_count
    ):
        raise BudgetedDocketAcquisitionError(
            "provisional ranked bytes or partition counts do not reconcile"
        )


def _canonical_record_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def materialize_selected_slice_batch(
    *,
    store: CycleAcquisitionStore,
    parent_batch_id: str,
    selected_batch_id: str,
    records: Iterable[Mapping[str, Any]],
    limit: int,
) -> tuple[RankedDocketTarget, ...]:
    """Create an honest terminal batch containing only ranked selected dockets.

    This does not claim that the parent discovery is saturated. The child batch
    binds its immutable configuration to the parent digest and exact ranked
    selection, so completeness and snapshot publication are scoped to the
    selected acquisition slice while the original partial pool remains partial.
    """

    materialized = tuple(records)
    targets = ranked_docket_targets(materialized, limit=limit)
    parent_ids = set(store.candidate_ids(parent_batch_id))
    missing = [
        target.candidate_id
        for target in targets
        if target.candidate_id not in parent_ids
    ]
    if missing:
        raise BudgetedDocketAcquisitionError(
            "selected docket was not discovered in parent batch: " + ",".join(missing)
        )
    selection_payload = [
        {
            "candidate_id": target.candidate_id,
            "courtlistener_url": target.docket_url,
            "cost_rank": target.rank,
        }
        for target in targets
    ]
    selection_hash = hashlib.sha256(
        json.dumps(selection_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    parent_config = store.batch_config(parent_batch_id)
    provisional_lineage = provisional_lineage_flags(parent_config)
    store.ensure_batch(
        selected_batch_id,
        {
            "schema_version": "legalforecast.selected_acquisition_slice.v1",
            "parent_batch_id": parent_batch_id,
            "parent_batch_digest": store.batch_digest(parent_batch_id),
            "selection_hash": selection_hash,
            "selection_count": len(targets),
            "parent_discovery_saturation_claimed": False,
            **provisional_lineage,
        },
    )
    term = "selected-ranked-slice"
    store.ensure_terms(selected_batch_id, (term,))
    store.commit_search_page(
        selected_batch_id,
        term,
        None,
        (
            DiscoveryHit(
                provider_hit_id=f"selected-{target.docket_id}",
                candidate_id=target.candidate_id,
                payload=selection_payload[index],
            )
            for index, target in enumerate(targets)
        ),
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )
    return targets


def provisional_lineage_flags(
    batch_config: Mapping[str, object],
) -> dict[str, object]:
    """Return exact provisional lineage or reject partial/contradictory markers."""

    present = any(field in batch_config for field in _PROVISIONAL_LINEAGE)
    if not present:
        return {}
    if any(
        batch_config.get(field) != value
        for field, value in _PROVISIONAL_LINEAGE.items()
    ):
        raise BudgetedDocketAcquisitionError(
            "provisional batch has incomplete or contradictory cohort-safety flags"
        )
    lineage: dict[str, object] = dict(_PROVISIONAL_LINEAGE)
    for field in _PROVISIONAL_PROPAGATED_FIELDS:
        value = batch_config.get(field)
        if value is None:
            raise BudgetedDocketAcquisitionError(
                f"provisional batch lacks required lineage field: {field}"
            )
        lineage[field] = value
    source_count = lineage["source_candidate_count"]
    counts = tuple(
        lineage[field]
        for field in ("success_count", "terminal_exclusion_count", "pending_count")
    )
    if (
        type(source_count) is not int
        or source_count <= 0
        or any(type(value) is not int or value < 0 for value in counts)
        or sum(cast(tuple[int, int, int], counts)) != source_count
    ):
        raise BudgetedDocketAcquisitionError(
            "provisional batch partition counts do not reconcile"
        )
    for field in _PROVISIONAL_PROPAGATED_FIELDS:
        if field.endswith("sha256"):
            value = lineage[field]
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise BudgetedDocketAcquisitionError(
                    f"provisional batch has invalid lineage hash: {field}"
                )
    return lineage


def ranked_docket_targets(
    records: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[RankedDocketTarget, ...]:
    """Validate and preserve the free Case.dev cost order."""

    if limit <= 0:
        raise BudgetedDocketAcquisitionError("limit must be positive")
    targets: list[RankedDocketTarget] = []
    seen: set[str] = set()
    for rank, record in enumerate(records):
        identity = record.get("identity")
        if not isinstance(identity, Mapping):
            raise BudgetedDocketAcquisitionError("ranked record identity is missing")
        typed_identity = cast(Mapping[str, object], identity)
        docket_id = typed_identity.get("courtlistener_docket_id")
        docket_url = typed_identity.get("courtlistener_url")
        if not isinstance(docket_id, str) or not docket_id.isdigit():
            raise BudgetedDocketAcquisitionError("ranked docket id is invalid")
        if not isinstance(docket_url, str):
            raise BudgetedDocketAcquisitionError("ranked docket URL is missing")
        if docket_id in seen:
            raise BudgetedDocketAcquisitionError(
                f"duplicate ranked docket: {docket_id}"
            )
        # Canonical construction is also the strict same-host/same-docket validator.
        try:
            canonical_courtlistener_docket_page_url(docket_url, page_number=1)
        except CourtListenerDocketPaginationError as exc:
            raise BudgetedDocketAcquisitionError(str(exc)) from exc
        seen.add(docket_id)
        targets.append(
            RankedDocketTarget(
                candidate_id=f"courtlistener-docket-{docket_id}",
                docket_id=docket_id,
                docket_url=docket_url,
                rank=rank,
            )
        )
        if len(targets) == limit:
            break
    return tuple(targets)


def acquire_ranked_dockets(
    *,
    records: Iterable[Mapping[str, Any]],
    scheduler: BudgetedFirecrawlScheduler,
    limit: int,
    max_pages_per_docket: int,
    decision_anchor: date,
) -> BudgetedDocketAcquisitionResult:
    """Acquire docket pages in waves and expose no incomplete bundle.

    Each page wave is submitted as one scheduler batch, retaining its widest-first
    retry behavior across dockets. A failed target is isolated; auth, budget,
    billing, rate, challenge, and circuit errors still propagate from the scheduler.
    """

    if max_pages_per_docket <= 0:
        raise BudgetedDocketAcquisitionError("max_pages_per_docket must be positive")
    ranked = ranked_docket_targets(records, limit=limit)
    active = {target.docket_id: target for target in ranked}
    pages: dict[str, dict[str, str]] = {target.docket_id: {} for target in ranked}
    failures_by_docket: dict[str, DocketAcquisitionFailure] = {}
    summary: Mapping[str, object] = {}

    for page_number in range(1, max_pages_per_docket + 1):
        if not active:
            break
        specs: list[FirecrawlTargetSpec] = []
        urls: dict[str, str] = {}
        for target in active.values():
            url = canonical_courtlistener_docket_page_url(
                target.docket_url, page_number=page_number
            )
            target_id = _target_id(target.docket_id, page_number)
            urls[target.docket_id] = url
            specs.append(
                FirecrawlTargetSpec(
                    target_id=target_id,
                    target_kind="docket",
                    source_url=url,
                    page_number=page_number,
                    ordinal=(page_number - 1) * len(ranked) + target.rank,
                )
            )
        run = scheduler.run(specs)
        summary = run.summary
        acquired = {page.target_id: page for page in run.pages}
        for docket_id, _target in tuple(active.items()):
            target_id = _target_id(docket_id, page_number)
            page = acquired.get(target_id)
            if page is None:
                failures_by_docket[docket_id] = _failure(
                    target=_target,
                    reason="fetch_failed",
                    stage="docket_page_acquisition",
                    detail=f"page_{page_number}_not_acquired",
                )
                del active[docket_id]
                continue
            pages[docket_id][page.source_url] = page.raw_html
            try:
                parsed = parse_courtlistener_docket_html(
                    page.raw_html, source_url=page.source_url, docket_id=docket_id
                )
                observed = [
                    parse_courtlistener_docket_html(
                        html, source_url=url, docket_id=docket_id
                    )
                    for url, html in pages[docket_id].items()
                ]
            except CourtListenerWebParseError as exc:
                failures_by_docket[docket_id] = _failure(
                    target=_target,
                    reason="docket_reconstruction_failed",
                    stage="complete_docket_reconstruction",
                    detail=f"invalid_docket_page_artifact:{exc}",
                )
                del active[docket_id]
                continue
            if not parsed.has_next_page or may_stop_at_anchor_boundary(
                observed, anchor=decision_anchor
            ):
                del active[docket_id]
    for docket_id, target in active.items():
        failures_by_docket[docket_id] = _failure(
            target=target,
            reason="fetch_failed",
            stage="docket_page_acquisition",
            detail="pagination_page_limit_reached",
        )

    bundles: list[CourtListenerDocketBundle] = []
    for target in ranked:
        if target.docket_id in failures_by_docket:
            continue
        cached = pages[target.docket_id]
        try:
            bundle = paginate_courtlistener_docket(
                target.docket_url,
                fetch=lambda url, cached=cached: cached[url],
                max_pages=max_pages_per_docket,
                decision_anchor=decision_anchor,
            )
        except KeyError:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail="cached_page_missing",
            )
            continue
        except CourtListenerDocketPaginationError as exc:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail=str(exc),
            )
            continue
        except CourtListenerWebParseError as exc:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail=f"invalid_docket_page_artifact:{exc}",
            )
            continue
        if not bundle.complete_for_anchor_window:
            failures_by_docket[target.docket_id] = _failure(
                target=target,
                reason="docket_reconstruction_failed",
                stage="complete_docket_reconstruction",
                detail="incomplete_anchor_window",
            )
            continue
        bundles.append(bundle)
    return BudgetedDocketAcquisitionResult(
        bundles=tuple(bundles),
        failures=tuple(
            failures_by_docket[target.docket_id]
            for target in ranked
            if target.docket_id in failures_by_docket
        ),
        credit_summary=summary,
    )


def render_complete_docket_html(bundle: CourtListenerDocketBundle) -> str:
    """Render a deterministic single-page screening view of a proven bundle."""

    if not bundle.complete_for_anchor_window:
        raise BudgetedDocketAcquisitionError("cannot render incomplete docket")
    rows: list[str] = []
    for entry in bundle.entries:
        document_rows: list[str] = []
        for document in entry.documents:
            link_class = "open_buy_pacer_modal" if document.pacer_only else ""
            action_label = document.action_label or (
                "Buy on PACER" if document.pacer_only else "Download PDF"
            )
            link = ""
            if document.href is not None:
                link = (
                    f'<a class="{link_class}" href="{escape(document.href)}">'
                    f"{escape(action_label)}</a>"
                )
            document_rows.append(
                '<div class="row recap-documents">'
                f"<div>{escape(document.kind)}</div>"
                f"<div>{escape(document.description)}"
                + (" Document is sealed." if document.restriction_markers else "")
                + f"</div>{link}</div>"
            )
        restriction_notice = (
            '<span class="restriction-notice">Document is sealed.</span>'
            if entry.restriction_markers
            else ""
        )
        rows.append(
            f'<div id="{escape(entry.row_id)}" class="row">'
            f'<div class="col-xs-1">{escape(entry.entry_number or "")}</div>'
            '<div class="col-xs-3">'
            f'<span title="{escape(entry.filed_at or "")}">'
            f"{escape(entry.filed_at or '')}</span></div>"
            f'<div class="col-xs-8">{escape(entry.text)}{restriction_notice}'
            f"{''.join(document_rows)}</div></div>"
        )
    return (
        "<html><head><title>"
        + escape(bundle.title or f"CourtListener docket {bundle.docket_id}")
        + '</title></head><body><div id="docket-entry-table">'
        + "".join(rows)
        + "</div></body></html>"
    )


def _target_id(docket_id: str, page_number: int) -> str:
    value = f"{docket_id}:{page_number}"
    return "docket-" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _failure(
    *, target: RankedDocketTarget, reason: str, stage: str, detail: str
) -> DocketAcquisitionFailure:
    return DocketAcquisitionFailure(
        candidate_id=target.candidate_id,
        docket_id=target.docket_id,
        reason=reason,
        failure_stage=stage,
        failure_reason=detail,
    )

"""Provider-free promotion of one terminal CourtListener REST priority tranche.

The priority-tranche scheduler deliberately emits a provisional snapshot because
most candidates in its authenticated parent source remain unscreened.  This
module provides the narrow bridge approved for an acquisition-shaped benchmark
cohort: it authenticates the first frozen tranche, proves every selected
candidate terminal, revalidates every acceptance under the exact release anchor,
and publishes only that exact selected set as a nonprovisional source.

The parent source is never represented as fully screened.  Its deferred
candidates remain an explicit, hash-bound ``unscreened_not_excluded`` omission
inventory in the promotion commitment and never enter the exclusion ledger.
No provider, purchase, model, evaluation, freeze, or dispatch capability is
accepted by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    REST_PRIORITY_DEFERRED_OMISSION_SCHEMA,
    REST_PRIORITY_SELECTION_POLICY_SCHEMA,
    REST_TERMINAL_SUBSET_PROMOTION_SCHEMA,
    REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY,
    FirecrawlScreeningIdentityError,
    canonical_rest_commitment_json_bytes,
    rest_priority_deferred_omission_jsonl_bytes,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    validate_rest_terminal_subset_promotion_commitment as _validate_identity_commitment,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    DIRECT_SEARCH_DEFERRED_FRONTIER_SCHEMA,
    DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
    DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
    DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,
    direct_search_frontier_sha256,
    direct_search_record_sha256,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)

REST_TERMINAL_SUBSET_SOURCE_SCHEMA = "legalforecast.rest_terminal_subset_source.v1"
REST_TERMINAL_SUBSET_TERM = "courtlistener-rest-terminal-subset-promotion-v1"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SELECTION_POLICY_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "approval_reference",
        "approved_by",
        "approved",
        "cohort_shape",
        "benchmark_claim_scope",
        "selection_purpose",
        "representative_sample_claimed",
        "acquisition_only",
        "model_visible",
        "outcome_polarity_blind",
        "outcome_polarity_used",
        "stage_b_labels_used",
        "model_outputs_used",
        "strict_screen_is_sole_eligibility_and_exclusion_authority",
        "ranking_metadata_visibility",
        "eligibility_anchor_date",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
    }
)


class RestPrioritySubsetPromotionError(ValueError):
    """Raised when an exact REST priority-subset proof fails closed."""


def validate_rest_terminal_subset_promotion_commitment(
    commitment: object,
    *,
    snapshot_candidate_ids: Sequence[str],
    snapshot_accepted_ids: Sequence[str],
    snapshot_excluded_ids: Sequence[str],
) -> dict[str, object]:
    """Delegate source identity validation with promotion-specific errors.

    The authoritative field and semantics validation lives in
    :mod:`firecrawl_screening_identity`, where recursive union identity checks
    can use it without importing this orchestration module.
    """

    try:
        return _validate_identity_commitment(
            commitment,
            snapshot_candidate_ids=tuple(sorted(snapshot_candidate_ids)),
            snapshot_accepted_ids=tuple(sorted(snapshot_accepted_ids)),
            snapshot_excluded_ids=tuple(sorted(snapshot_excluded_ids)),
        )
    except FirecrawlScreeningIdentityError as exc:
        raise RestPrioritySubsetPromotionError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class RestPrioritySubsetPromotionResult:
    """One verified nonprovisional exact-subset snapshot publication."""

    batch_id: str
    batch_digest: str
    snapshot_id: str
    snapshot_path: Path
    snapshot_manifest_sha256: str
    cycle_hash: str
    priority_batch_id: str
    priority_batch_digest: str
    source_batch_id: str
    source_batch_digest: str
    selected_candidate_ids: tuple[str, ...]
    accepted_candidate_ids: tuple[str, ...]
    excluded_candidate_ids: tuple[str, ...]
    deferred_candidate_ids: tuple[str, ...]
    commitment: Mapping[str, object]

    @property
    def selected_count(self) -> int:
        """Return the promoted exact-source size."""

        return len(self.selected_candidate_ids)

    @property
    def accepted_count(self) -> int:
        """Return the number of strict-screen acceptances."""

        return len(self.accepted_candidate_ids)

    @property
    def excluded_count(self) -> int:
        """Return the number of selected strict-screen exclusions."""

        return len(self.excluded_candidate_ids)

    @property
    def deferred_count(self) -> int:
        """Return the explicitly omitted parent-source size."""

        return len(self.deferred_candidate_ids)

    def to_record(self) -> dict[str, object]:
        """Return a JSON-serializable operator result."""

        return {
            "schema_version": "legalforecast.rest_priority_subset_promotion_result.v1",
            "batch_id": self.batch_id,
            "batch_digest": self.batch_digest,
            "snapshot_id": self.snapshot_id,
            "snapshot_path": str(self.snapshot_path),
            "snapshot_manifest_sha256": self.snapshot_manifest_sha256,
            "cycle_hash": self.cycle_hash,
            "priority_batch_id": self.priority_batch_id,
            "priority_batch_digest": self.priority_batch_digest,
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "selected_candidate_count": self.selected_count,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "accepted_candidate_count": self.accepted_count,
            "accepted_candidate_ids": list(self.accepted_candidate_ids),
            "excluded_candidate_count": self.excluded_count,
            "excluded_candidate_ids": list(self.excluded_candidate_ids),
            "deferred_candidate_count": self.deferred_count,
            "deferred_disposition": "unscreened_not_excluded",
            "verified": True,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "model_activity_requested": False,
            "model_activity_executed": False,
            "evaluation_activity_executed": False,
            "freeze_activity_executed": False,
            "dispatch_activity_executed": False,
        }


def promote_terminal_rest_priority_tranche(
    store: CycleAcquisitionStore,
    *,
    priority_batch_id: str,
    expected_priority_batch_digest: str,
    priority_snapshot: Path,
    expected_priority_snapshot_manifest_sha256: str,
    priority_frontier: Path,
    expected_priority_frontier_file_sha256: str,
    selection_policy: Path,
    expected_selection_policy_sha256: str,
    expected_source_batch_digest: str,
    expected_cycle_hash: str,
    decision_filed_on_or_after: date,
    target_batch_id: str,
    snapshot_root: Path,
    snapshot_id: str,
) -> RestPrioritySubsetPromotionResult:
    """Authenticate, materialize, and publish one exact terminal REST tranche.

    Every input artifact is externally pinned.  All verification that can fail
    without mutation runs before the target batch is created.  Target writes are
    deterministic and resumable; the exported snapshot reads only target-batch
    terminal observations so later canonical candidate transitions cannot alter
    the publication.
    """

    _require_date(decision_filed_on_or_after)
    anchor = decision_filed_on_or_after.isoformat()
    for label, digest in (
        ("priority batch", expected_priority_batch_digest),
        ("priority snapshot manifest", expected_priority_snapshot_manifest_sha256),
        ("priority frontier file", expected_priority_frontier_file_sha256),
        ("selection policy", expected_selection_policy_sha256),
        ("source batch", expected_source_batch_digest),
        ("cycle", expected_cycle_hash),
    ):
        _require_sha256(digest, label)
    if store.read_only:
        raise RestPrioritySubsetPromotionError(
            "REST priority-subset promotion requires a writable cycle store"
        )
    if store.cycle_hash != expected_cycle_hash:
        raise RestPrioritySubsetPromotionError("cycle hash mismatch")
    frozen_cycle_anchor = _required_text(
        store.cycle_policy,
        "eligibility_anchor",
    )
    if anchor != frozen_cycle_anchor:
        raise RestPrioritySubsetPromotionError(
            "requested eligibility anchor does not match the frozen cycle policy: "
            f"{anchor} != {frozen_cycle_anchor}"
        )
    if priority_batch_id == target_batch_id:
        raise RestPrioritySubsetPromotionError(
            "priority and target batch IDs must differ"
        )

    priority_batch_digest = store.batch_digest(priority_batch_id)
    if priority_batch_digest != expected_priority_batch_digest:
        raise RestPrioritySubsetPromotionError("priority batch digest mismatch")
    priority_config = dict(store.batch_config(priority_batch_id))
    _validate_priority_batch_config(priority_config)

    frontier_path = _regular_file(priority_frontier, "priority frontier")
    if _sha256_file(frontier_path) != expected_priority_frontier_file_sha256:
        raise RestPrioritySubsetPromotionError(
            "priority frontier file SHA-256 mismatch"
        )
    frontier = _json_object(frontier_path, "priority frontier")
    _validate_frontier_self_hash(frontier)

    source_batch_id = _required_text(frontier, "source_batch_id")
    if source_batch_id in {priority_batch_id, target_batch_id}:
        raise RestPrioritySubsetPromotionError(
            "parent source, priority, and target batch IDs must be distinct"
        )
    source_batch_digest = store.batch_digest(source_batch_id)
    if source_batch_digest != expected_source_batch_digest:
        raise RestPrioritySubsetPromotionError("source batch digest mismatch")

    selected_ids, deferred_ids, ranked_ids = _validate_exact_first_frontier(
        frontier=frontier,
        priority_config=priority_config,
        source_batch_digest=source_batch_digest,
        source_candidate_ids=store.candidate_ids(source_batch_id),
        cycle_hash=expected_cycle_hash,
    )
    if store.candidate_ids(priority_batch_id) != tuple(sorted(selected_ids)):
        raise RestPrioritySubsetPromotionError(
            "priority batch candidates do not exactly equal the frozen tranche"
        )

    policy_path = _regular_file(selection_policy, "selection policy")
    if _sha256_file(policy_path) != expected_selection_policy_sha256:
        raise RestPrioritySubsetPromotionError("selection policy SHA-256 mismatch")
    policy = _json_object(policy_path, "selection policy")
    _validate_selection_policy(policy, eligibility_anchor=anchor)
    canonical_selection_policy_sha256 = _canonical_sha256(policy)

    priority_manifest_path = _regular_file(
        priority_snapshot / "manifest.json",
        "priority snapshot manifest",
    )
    if _sha256_file(priority_manifest_path) != (
        expected_priority_snapshot_manifest_sha256
    ):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot manifest SHA-256 mismatch"
        )
    try:
        priority_manifest = verify_snapshot(
            priority_snapshot,
            expected_cycle_hash=expected_cycle_hash,
            expected_batch_digest=expected_priority_batch_digest,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        raise RestPrioritySubsetPromotionError(str(exc)) from exc
    _validate_priority_snapshot_manifest(
        priority_manifest,
        priority_batch_id=priority_batch_id,
        priority_config=priority_config,
        frontier=frontier,
    )

    source_terminals = _validate_selected_terminals(
        store.batch_terminal_observations(priority_batch_id),
        selected_ids=selected_ids,
        eligibility_anchor=anchor,
    )
    accepted_ids = tuple(
        observation.candidate_id
        for observation in source_terminals
        if observation.state == "accepted"
    )
    excluded_ids = tuple(
        observation.candidate_id
        for observation in source_terminals
        if observation.state == "excluded"
    )
    _validate_priority_snapshot_outcomes(
        priority_snapshot,
        source_terminals=source_terminals,
        selected_ids=selected_ids,
        accepted_ids=accepted_ids,
        excluded_ids=excluded_ids,
    )
    current_sources = _current_terminal_sources(
        store,
        source_terminals=source_terminals,
    )

    omission_inventory: dict[str, object] = {
        "schema_version": REST_PRIORITY_DEFERRED_OMISSION_SCHEMA,
        "disposition": "unscreened_not_excluded",
        "candidate_count": len(deferred_ids),
        "candidate_ids": list(deferred_ids),
        "candidate_id_set_sha256": _candidate_id_set_sha256(deferred_ids),
        "jsonl_sha256": hashlib.sha256(
            rest_priority_deferred_omission_jsonl_bytes(deferred_ids)
        ).hexdigest(),
        "parent_source_candidate_count": len(ranked_ids),
        "selected_plus_deferred_partition_sha256": _canonical_sha256(
            {
                "selected_candidate_ids": list(selected_ids),
                "deferred_candidate_ids": list(deferred_ids),
            }
        ),
    }
    commitment: dict[str, object] = {
        "schema_version": REST_TERMINAL_SUBSET_PROMOTION_SCHEMA,
        "selection_semantics": "exact_frozen_priority_tranche",
        "eligibility_anchor_date": anchor,
        "cycle_hash": expected_cycle_hash,
        "priority_batch_id": priority_batch_id,
        "priority_batch_digest": expected_priority_batch_digest,
        "priority_snapshot_manifest_sha256": (
            expected_priority_snapshot_manifest_sha256
        ),
        "priority_screened_cases_sha256": _snapshot_file_sha256(
            priority_manifest, "screened-cases.jsonl"
        ),
        "priority_exclusions_sha256": _snapshot_file_sha256(
            priority_manifest, "exclusions.jsonl"
        ),
        "priority_frontier_file_sha256": (expected_priority_frontier_file_sha256),
        "priority_frontier_sha256": _required_sha256(frontier, "frontier_sha256"),
        "source_batch_id": source_batch_id,
        "source_batch_digest": source_batch_digest,
        "source_candidate_count": len(ranked_ids),
        "source_candidate_set_sha256": _required_sha256(
            frontier, "source_candidate_set_sha256"
        ),
        "source_candidate_id_set_sha256": _candidate_id_set_sha256(ranked_ids),
        "source_lineage_commitment_sha256": _required_sha256(
            frontier, "source_lineage_commitment_sha256"
        ),
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "selection_policy_sha256": canonical_selection_policy_sha256,
        "selection_policy": dict(policy),
        "tranche_ordinal": 1,
        "selected_candidate_count": len(selected_ids),
        "selected_candidate_ids": list(selected_ids),
        "selected_candidate_id_set_sha256": _candidate_id_set_sha256(selected_ids),
        "selected_candidate_set_sha256": _required_sha256(
            frontier, "selected_candidate_set_sha256"
        ),
        "selected_terminal_observations_sha256": _canonical_sha256(
            [_terminal_projection(observation) for observation in source_terminals]
        ),
        "accepted_candidate_count": len(accepted_ids),
        "accepted_candidate_ids": list(accepted_ids),
        "accepted_candidate_id_set_sha256": _candidate_id_set_sha256(accepted_ids),
        "excluded_candidate_count": len(excluded_ids),
        "excluded_candidate_ids": list(excluded_ids),
        "excluded_candidate_id_set_sha256": _candidate_id_set_sha256(excluded_ids),
        "deferred_omission_inventory": omission_inventory,
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
        "cohort_sampling_claim": (
            "convenience_acquisition_shaped_nonrepresentative_"
            "relative_model_comparison_only"
        ),
        "parent_source_fully_screened": False,
        "terminality_scope": "promoted_exact_selected_source",
        "final_cohort_eligible": True,
        "full_source_terminal": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "model_activity_requested": False,
        "model_activity_executed": False,
        "evaluation_activity_executed": False,
        "freeze_activity_executed": False,
        "dispatch_activity_executed": False,
    }
    validate_rest_terminal_subset_promotion_commitment(
        commitment,
        snapshot_candidate_ids=selected_ids,
        snapshot_accepted_ids=accepted_ids,
        snapshot_excluded_ids=excluded_ids,
    )

    target_config: dict[str, object] = {
        "schema_version": REST_TERMINAL_SUBSET_SOURCE_SCHEMA,
        "provider": "none",
        "query_terms": [REST_TERMINAL_SUBSET_TERM],
        "discovery_mode": REST_TERMINAL_SUBSET_SOURCE_SCHEMA,
        "selection_semantics": "exact_frozen_priority_tranche",
        "source_cycle_hash": expected_cycle_hash,
        "priority_batch_id": priority_batch_id,
        "priority_batch_digest": expected_priority_batch_digest,
        "priority_frontier_sha256": _required_sha256(frontier, "frontier_sha256"),
        "selection_policy_sha256": canonical_selection_policy_sha256,
        "selected_candidate_count": len(selected_ids),
        "selected_candidate_id_set_sha256": _candidate_id_set_sha256(selected_ids),
        "rest_terminal_subset_promotion_sha256": _canonical_sha256(commitment),
        "provider_activity_requested": False,
        "paid_activity_requested": False,
        "model_activity_requested": False,
    }
    batch_digest = store.ensure_batch(target_batch_id, target_config)
    store.ensure_terms(target_batch_id, (REST_TERMINAL_SUBSET_TERM,))
    hits = tuple(
        _promotion_hit(
            candidate_id,
            priority_batch_id=priority_batch_id,
            priority_frontier_sha256=_required_sha256(frontier, "frontier_sha256"),
        )
        for candidate_id in selected_ids
    )
    store.commit_search_page(
        target_batch_id,
        REST_TERMINAL_SUBSET_TERM,
        None,
        hits,
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )
    if store.candidate_ids(target_batch_id) != tuple(sorted(selected_ids)):
        raise RestPrioritySubsetPromotionError(
            "target batch candidates do not exactly equal the promoted subset"
        )
    for candidate_id in selected_ids:
        store.reuse_current_terminal_observation(
            candidate_id,
            batch_id=target_batch_id,
            source_observation=current_sources[candidate_id],
        )
    if not store.snapshot_is_saturated(
        target_batch_id,
        use_batch_terminal_observations=True,
    ):
        raise RestPrioritySubsetPromotionError(
            "promoted exact-subset target is not saturated"
        )
    try:
        existing_snapshot = store.existing_complete_snapshot_evidence(
            snapshot_root,
            snapshot_id=snapshot_id,
            batch_id=target_batch_id,
        )
    except (FileExistsError, SnapshotVerificationError, ValueError) as exc:
        raise RestPrioritySubsetPromotionError(str(exc)) from exc
    if existing_snapshot is None:
        snapshot_path = store.export_snapshot(
            snapshot_root,
            snapshot_id=snapshot_id,
            batch_id=target_batch_id,
            complete=True,
            stage_commitments={
                REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY: commitment,
            },
            use_batch_terminal_observations=True,
        )
        try:
            target_manifest = verify_snapshot(
                snapshot_path,
                expected_cycle_hash=expected_cycle_hash,
                expected_batch_digest=batch_digest,
                require_complete=True,
                require_saturated=True,
            )
        except SnapshotVerificationError as exc:
            raise RestPrioritySubsetPromotionError(str(exc)) from exc
        target_candidate_ids, target_accepted_ids, target_excluded_ids = (
            _snapshot_identity_sets(snapshot_path)
        )
        target_manifest_sha256 = _sha256_file(snapshot_path / "manifest.json")
    else:
        snapshot_path = existing_snapshot.path
        target_manifest = dict(existing_snapshot.manifest)
        if target_manifest.get("saturated") is not True:
            raise RestPrioritySubsetPromotionError(
                "committed target snapshot is not saturated"
            )
        target_candidate_ids, target_accepted_ids, target_excluded_ids = (
            _snapshot_identity_sets_from_payloads(existing_snapshot.payloads)
        )
        target_manifest_sha256 = hashlib.sha256(
            f"{_canonical_json(target_manifest)}\n".encode()
        ).hexdigest()
    if any(
        marker in target_manifest
        for marker in (
            "provisional_frontier",
            "final_cohort_eligible",
            "full_source_terminal",
        )
    ):
        raise RestPrioritySubsetPromotionError(
            "promoted target snapshot retained provisional manifest markers"
        )
    validate_rest_terminal_subset_promotion_commitment(
        commitment,
        snapshot_candidate_ids=target_candidate_ids,
        snapshot_accepted_ids=target_accepted_ids,
        snapshot_excluded_ids=target_excluded_ids,
    )
    target_stage_commitments = _mapping(
        target_manifest.get("stage_commitments"),
        "target snapshot stage_commitments",
    )
    if (
        target_stage_commitments.get(REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY)
        != commitment
    ):
        raise RestPrioritySubsetPromotionError(
            "target snapshot promotion commitment changed during publication"
        )
    return RestPrioritySubsetPromotionResult(
        batch_id=target_batch_id,
        batch_digest=batch_digest,
        snapshot_id=snapshot_id,
        snapshot_path=snapshot_path,
        snapshot_manifest_sha256=target_manifest_sha256,
        cycle_hash=expected_cycle_hash,
        priority_batch_id=priority_batch_id,
        priority_batch_digest=expected_priority_batch_digest,
        source_batch_id=source_batch_id,
        source_batch_digest=source_batch_digest,
        selected_candidate_ids=selected_ids,
        accepted_candidate_ids=accepted_ids,
        excluded_candidate_ids=excluded_ids,
        deferred_candidate_ids=deferred_ids,
        commitment=commitment,
    )


def _validate_priority_batch_config(config: Mapping[str, object]) -> None:
    if (
        config.get("discovery_mode") != DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA
        or config.get("selection_semantics") != "rank_only_no_membership_exclusion"
        or config.get("deferred_disposition") != "unscreened_not_excluded"
        or config.get("provisional_frontier") is not True
        or config.get("final_cohort_eligible") is not False
        or config.get("full_source_terminal") is not False
        or config.get("strict_screen_is_sole_eligibility_and_exclusion_authority")
        is not True
        or config.get("ranking_metadata_visibility")
        != "acquisition_only_never_packet_visible"
        or config.get("provider_activity_requested") is not False
        or config.get("paid_activity_requested") is not False
        or config.get("ranking_policy_sha256") != DIRECT_SEARCH_PRIORITY_POLICY_SHA256
        or config.get("query_terms") != [DIRECT_SEARCH_PRIORITY_TRANCHE_TERM]
    ):
        raise RestPrioritySubsetPromotionError(
            "priority batch is not the expected provider-free provisional tranche"
        )


def _validate_frontier_self_hash(frontier: Mapping[str, object]) -> None:
    supplied = dict(frontier)
    claimed = supplied.pop("frontier_sha256", None)
    if (
        not isinstance(claimed, str)
        or _SHA256.fullmatch(claimed) is None
        or direct_search_frontier_sha256(supplied) != claimed
    ):
        raise RestPrioritySubsetPromotionError("priority frontier self-hash is invalid")


def _validate_exact_first_frontier(
    *,
    frontier: Mapping[str, object],
    priority_config: Mapping[str, object],
    source_batch_digest: str,
    source_candidate_ids: Sequence[str],
    cycle_hash: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if (
        frontier.get("schema_version") != DIRECT_SEARCH_DEFERRED_FRONTIER_SCHEMA
        or frontier.get("selection_semantics") != "rank_only_no_membership_exclusion"
        or frontier.get("deferred_disposition") != "unscreened_not_excluded"
        or frontier.get("tranche_ordinal") != 1
        or frontier.get("predecessor_frontier_sha256") is not None
        or frontier.get("source_batch_digest") != source_batch_digest
        or frontier.get("source_cycle_hash") != cycle_hash
        or frontier.get("ranking_policy_sha256") != DIRECT_SEARCH_PRIORITY_POLICY_SHA256
        or frontier.get("strict_screen_is_sole_eligibility_and_exclusion_authority")
        is not True
        or frontier.get("ranking_metadata_visibility")
        != "acquisition_only_never_packet_visible"
        or frontier.get("provider_activity_executed") is not False
        or frontier.get("paid_activity_executed") is not False
        or frontier.get("global_source_saturated") is not False
    ):
        raise RestPrioritySubsetPromotionError(
            "priority frontier is not the expected first provider-free tranche"
        )
    selected = _unique_text_list(frontier, "selected_candidate_ids")
    deferred = _unique_text_list(frontier, "deferred_candidate_ids")
    ranked = _unique_text_list(frontier, "ranked_candidate_ids")
    cumulative = _unique_text_list(frontier, "cumulative_selected_candidate_ids")
    if not selected:
        raise RestPrioritySubsetPromotionError(
            "priority frontier selected set is empty"
        )
    if cumulative != selected or selected + deferred != ranked:
        raise RestPrioritySubsetPromotionError(
            "first priority tranche does not exactly partition its ranked parent"
        )
    if set(source_candidate_ids) != set(ranked):
        raise RestPrioritySubsetPromotionError(
            "priority frontier ranked IDs do not equal the parent source batch"
        )
    if frontier.get("source_candidate_count") != len(ranked):
        raise RestPrioritySubsetPromotionError(
            "priority frontier source candidate count does not reconcile"
        )
    if frontier.get("source_candidate_id_set_sha256") != (
        _candidate_id_set_sha256(ranked)
    ):
        raise RestPrioritySubsetPromotionError(
            "priority frontier source candidate-ID commitment is invalid"
        )
    if frontier.get("selected_candidate_set_sha256") != priority_config.get(
        "selected_candidate_set_sha256"
    ):
        raise RestPrioritySubsetPromotionError(
            "priority selected candidate-set commitment changed"
        )
    expected_config_fields: dict[str, object] = {
        "source_batch_id": frontier.get("source_batch_id"),
        "source_batch_digest": source_batch_digest,
        "source_cycle_hash": cycle_hash,
        "source_candidate_count": len(ranked),
        "source_candidate_set_sha256": frontier.get("source_candidate_set_sha256"),
        "source_candidate_id_set_sha256": frontier.get(
            "source_candidate_id_set_sha256"
        ),
        "source_lineage_commitment_sha256": frontier.get(
            "source_lineage_commitment_sha256"
        ),
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "tranche_ordinal": 1,
        "predecessor_frontier_sha256": None,
        "selected_candidate_count": len(selected),
        "selected_candidate_set_sha256": frontier.get("selected_candidate_set_sha256"),
        "cumulative_selected_count": len(selected),
        "deferred_candidate_count": len(deferred),
        "deferred_candidate_set_sha256": frontier.get("deferred_candidate_set_sha256"),
        "deferred_frontier_sha256": frontier.get("frontier_sha256"),
    }
    for field, expected in expected_config_fields.items():
        if priority_config.get(field) != expected:
            raise RestPrioritySubsetPromotionError(
                f"priority batch/frontier commitment mismatch: {field}"
            )
    source_lineage = _mapping(
        frontier.get("source_lineage_commitments"),
        "source_lineage_commitments",
    )
    if direct_search_record_sha256(source_lineage) != frontier.get(
        "source_lineage_commitment_sha256"
    ):
        raise RestPrioritySubsetPromotionError(
            "priority source-lineage commitment is invalid"
        )
    ranking_policy = _mapping(frontier.get("ranking_policy"), "ranking_policy")
    if (
        direct_search_record_sha256(ranking_policy)
        != DIRECT_SEARCH_PRIORITY_POLICY_SHA256
    ):
        raise RestPrioritySubsetPromotionError(
            "priority frontier ranking-policy content is invalid"
        )
    ranking_records = _mapping_list(frontier, "ranking_records")
    if tuple(_required_text(record, "candidate_id") for record in ranking_records) != (
        ranked
    ):
        raise RestPrioritySubsetPromotionError(
            "priority ranking records do not exactly follow ranked candidate IDs"
        )
    if tuple(record.get("rank") for record in ranking_records) != tuple(
        range(1, len(ranked) + 1)
    ):
        raise RestPrioritySubsetPromotionError(
            "priority ranking record ordinals are invalid"
        )
    selected_commitments = _mapping(
        frontier.get("selected_ranking_record_commitments"),
        "selected_ranking_record_commitments",
    )
    records_by_id = {
        _required_text(record, "candidate_id"): record for record in ranking_records
    }
    if set(selected_commitments) != set(selected):
        raise RestPrioritySubsetPromotionError(
            "selected ranking-record commitments do not cover the exact tranche"
        )
    for candidate_id in selected:
        if selected_commitments[candidate_id] != direct_search_record_sha256(
            records_by_id[candidate_id]
        ):
            raise RestPrioritySubsetPromotionError(
                f"selected ranking record changed for {candidate_id}"
            )
    if frontier.get("selected_ranking_record_commitment_sha256") != (
        direct_search_record_sha256(
            {"selected_ranking_record_commitments": dict(selected_commitments)}
        )
    ):
        raise RestPrioritySubsetPromotionError(
            "selected ranking-record aggregate commitment is invalid"
        )
    return tuple(sorted(selected)), tuple(sorted(deferred)), tuple(sorted(ranked))


def _validate_selection_policy(
    policy: Mapping[str, object],
    *,
    eligibility_anchor: str,
) -> None:
    if frozenset(policy.keys()) != _SELECTION_POLICY_FIELDS:
        raise RestPrioritySubsetPromotionError(
            "selection policy fields do not match the approved schema"
        )
    expected: dict[str, object] = {
        "schema_version": REST_PRIORITY_SELECTION_POLICY_SCHEMA,
        "approved": True,
        "cohort_shape": "convenience_acquisition_shaped_nonrepresentative",
        "benchmark_claim_scope": "relative_model_performance_only",
        "selection_purpose": "cheapest_clean_cases_for_timely_cycle",
        "representative_sample_claimed": False,
        "acquisition_only": True,
        "model_visible": False,
        "outcome_polarity_blind": True,
        "outcome_polarity_used": False,
        "stage_b_labels_used": False,
        "model_outputs_used": False,
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
        "eligibility_anchor_date": eligibility_anchor,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "model_activity_requested": False,
        "model_activity_executed": False,
    }
    for field, expected_value in expected.items():
        if policy.get(field) != expected_value:
            raise RestPrioritySubsetPromotionError(
                f"selection policy has unsafe or invalid {field}"
            )
    for field in ("approval_reference", "approved_by"):
        _required_text(policy, field)


def _validate_priority_snapshot_manifest(
    manifest: Mapping[str, object],
    *,
    priority_batch_id: str,
    priority_config: Mapping[str, object],
    frontier: Mapping[str, object],
) -> None:
    if (
        manifest.get("batch_id") != priority_batch_id
        or manifest.get("provisional_frontier") is not True
        or manifest.get("final_cohort_eligible") is not False
        or manifest.get("full_source_terminal") is not False
    ):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot is not the authenticated provisional tranche"
        )
    commitments = _mapping(
        manifest.get("stage_commitments"),
        "priority snapshot stage_commitments",
    )
    priority = _mapping(
        commitments.get("direct_search_priority_tranche"),
        "direct_search_priority_tranche",
    )
    expected_fields = (
        "source_batch_id",
        "source_batch_digest",
        "source_cycle_hash",
        "source_candidate_count",
        "source_candidate_set_sha256",
        "source_candidate_id_set_sha256",
        "source_lineage_commitment_sha256",
        "ranking_policy_sha256",
        "tranche_ordinal",
        "requested_tranche_size",
        "predecessor_frontier_sha256",
        "selected_candidate_count",
        "selected_candidate_set_sha256",
        "cumulative_selected_count",
        "deferred_candidate_count",
        "deferred_candidate_set_sha256",
        "deferred_frontier_sha256",
        "chain_terminal",
        "ranking_frontier_exhausted",
        "global_source_saturated",
        "strict_screen_is_sole_eligibility_and_exclusion_authority",
        "ranking_metadata_visibility",
    )
    expected = {
        "schema_version": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
        **{field: priority_config[field] for field in expected_fields},
    }
    if priority != expected:
        raise RestPrioritySubsetPromotionError(
            "priority snapshot stage commitment does not match its batch"
        )
    if priority.get("deferred_frontier_sha256") != frontier.get("frontier_sha256"):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot does not commit the authenticated frontier"
        )


def _validate_selected_terminals(
    observations: Sequence[CandidateObservation],
    *,
    selected_ids: tuple[str, ...],
    eligibility_anchor: str,
) -> tuple[CandidateObservation, ...]:
    by_id = {observation.candidate_id: observation for observation in observations}
    if len(by_id) != len(observations) or set(by_id) != set(selected_ids):
        raise RestPrioritySubsetPromotionError(
            "every selected candidate must have exactly one batch terminal"
        )
    ordered = tuple(by_id[candidate_id] for candidate_id in selected_ids)
    for observation in ordered:
        if observation.state not in {"accepted", "excluded"}:
            raise RestPrioritySubsetPromotionError(
                f"selected candidate is not accepted or excluded: "
                f"{observation.candidate_id}"
            )
        if observation.state == "accepted":
            if observation.reason_code != "strict_clean_screen_passed":
                raise RestPrioritySubsetPromotionError(
                    "selected acceptance is not a strict clean-screen terminal: "
                    f"{observation.candidate_id}"
                )
            try:
                validate_strict_screen_evidence(
                    observation.evidence,
                    expected_candidate_id=observation.candidate_id,
                )
            except StrictScreenEvidenceError as exc:
                raise RestPrioritySubsetPromotionError(str(exc)) from exc
            if observation.evidence.get("eligibility_anchor_date") != (
                eligibility_anchor
            ):
                raise RestPrioritySubsetPromotionError(
                    "selected acceptance does not use the required eligibility "
                    f"anchor: {observation.candidate_id}"
                )
    return ordered


def _validate_priority_snapshot_outcomes(
    snapshot: Path,
    *,
    source_terminals: tuple[CandidateObservation, ...],
    selected_ids: tuple[str, ...],
    accepted_ids: tuple[str, ...],
    excluded_ids: tuple[str, ...],
) -> None:
    candidates = _jsonl_objects(snapshot / "candidates.jsonl", "candidates")
    by_id = {_required_text(record, "candidate_id"): record for record in candidates}
    if len(by_id) != len(candidates) or set(by_id) != set(selected_ids):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot candidates do not equal the frozen selected set"
        )
    terminals_by_id = {
        observation.candidate_id: observation for observation in source_terminals
    }
    for candidate_id in selected_ids:
        record = by_id[candidate_id]
        observation = terminals_by_id[candidate_id]
        expected = _terminal_projection(observation)
        actual = {
            "candidate_id": candidate_id,
            "state": record.get("state"),
            "reason_code": record.get("reason_code"),
            "evidence": record.get("evidence"),
            "observed_at": record.get("observed_at"),
        }
        if actual != expected:
            raise RestPrioritySubsetPromotionError(
                f"priority snapshot terminal changed for {candidate_id}"
            )
    screened = _jsonl_objects(snapshot / "screened-cases.jsonl", "screened cases")
    exclusions = _jsonl_objects(snapshot / "exclusions.jsonl", "exclusions")
    if tuple(sorted(_required_text(row, "candidate_id") for row in screened)) != (
        tuple(sorted(accepted_ids))
    ):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot accepted IDs do not reconcile"
        )
    if tuple(sorted(_required_text(row, "candidate_id") for row in exclusions)) != (
        tuple(sorted(excluded_ids))
    ):
        raise RestPrioritySubsetPromotionError(
            "priority snapshot exclusion IDs do not reconcile"
        )
    expected_screened = tuple(
        _snapshot_outcome_record(terminals_by_id[candidate_id])
        for candidate_id in sorted(accepted_ids)
    )
    expected_exclusions = tuple(
        _snapshot_outcome_record(terminals_by_id[candidate_id])
        for candidate_id in sorted(excluded_ids)
    )
    if tuple(sorted(screened, key=_record_candidate_id)) != expected_screened:
        raise RestPrioritySubsetPromotionError(
            "priority snapshot changed accepted evidence"
        )
    if tuple(sorted(exclusions, key=_record_candidate_id)) != expected_exclusions:
        raise RestPrioritySubsetPromotionError(
            "priority snapshot changed selected exclusion evidence"
        )


def _current_terminal_sources(
    store: CycleAcquisitionStore,
    *,
    source_terminals: tuple[CandidateObservation, ...],
) -> dict[str, CandidateObservation]:
    current_sources: dict[str, CandidateObservation] = {}
    for terminal in source_terminals:
        current = store.current_observation(terminal.candidate_id)
        if current is None or current.state not in {"accepted", "excluded"}:
            raise RestPrioritySubsetPromotionError(
                "selected terminal no longer has a reusable canonical source: "
                f"{terminal.candidate_id}"
            )
        if _terminal_projection(current) != _terminal_projection(terminal):
            raise RestPrioritySubsetPromotionError(
                "selected terminal drifted after the priority snapshot: "
                f"{terminal.candidate_id}"
            )
        current_sources[terminal.candidate_id] = current
    return current_sources


def _promotion_hit(
    candidate_id: str,
    *,
    priority_batch_id: str,
    priority_frontier_sha256: str,
) -> DiscoveryHit:
    docket_id = candidate_id.removeprefix("courtlistener-docket-")
    if not docket_id.isdigit() or candidate_id != (f"courtlistener-docket-{docket_id}"):
        raise RestPrioritySubsetPromotionError(
            f"invalid CourtListener candidate identity: {candidate_id}"
        )
    return DiscoveryHit(
        provider_hit_id=f"{REST_TERMINAL_SUBSET_TERM}:{docket_id}",
        candidate_id=candidate_id,
        payload={
            "candidate_id": candidate_id,
            "docket_id": docket_id,
            "courtlistener_docket_id": docket_id,
            "provider": "courtlistener-rest-v4",
            "rest_terminal_subset_promotion": {
                "schema_version": REST_TERMINAL_SUBSET_SOURCE_SCHEMA,
                "priority_batch_id": priority_batch_id,
                "priority_frontier_sha256": priority_frontier_sha256,
                "provider_activity_executed": False,
                "paid_activity_executed": False,
            },
        },
    )


def _snapshot_identity_sets(
    snapshot: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    candidates = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_objects(
                snapshot / "candidates.jsonl", "target candidates"
            )
        )
    )
    accepted = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_objects(
                snapshot / "screened-cases.jsonl", "target screened cases"
            )
        )
    )
    excluded = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_objects(
                snapshot / "exclusions.jsonl", "target exclusions"
            )
        )
    )
    return candidates, accepted, excluded


def _snapshot_identity_sets_from_payloads(
    payloads: Mapping[str, bytes],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    candidates = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_payload_objects(
                payloads.get("candidates.jsonl"),
                "target candidates",
            )
        )
    )
    accepted = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_payload_objects(
                payloads.get("screened-cases.jsonl"),
                "target screened cases",
            )
        )
    )
    excluded = tuple(
        sorted(
            _required_text(record, "candidate_id")
            for record in _jsonl_payload_objects(
                payloads.get("exclusions.jsonl"),
                "target exclusions",
            )
        )
    )
    return candidates, accepted, excluded


def _snapshot_outcome_record(
    observation: CandidateObservation,
) -> dict[str, object]:
    record = dict(observation.evidence)
    existing_candidate_id = record.get("candidate_id")
    if existing_candidate_id is not None and (
        existing_candidate_id != observation.candidate_id
    ):
        raise RestPrioritySubsetPromotionError(
            f"candidate evidence identity mismatch for {observation.candidate_id}"
        )
    record["candidate_id"] = observation.candidate_id
    if observation.state == "excluded":
        record.setdefault("reason", observation.reason_code)
        record.setdefault("primary_exclusion_reason", observation.reason_code)
    return record


def _terminal_projection(
    observation: CandidateObservation,
) -> dict[str, object]:
    return {
        "candidate_id": observation.candidate_id,
        "state": observation.state,
        "reason_code": observation.reason_code,
        "evidence": dict(observation.evidence),
        "observed_at": observation.observed_at,
    }


def _snapshot_file_sha256(
    manifest: Mapping[str, object],
    filename: str,
) -> str:
    files = _mapping(manifest.get("files"), "snapshot files")
    commitment = _mapping(files.get(filename), f"snapshot file {filename}")
    digest = commitment.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise RestPrioritySubsetPromotionError(
            f"snapshot file has invalid SHA-256: {filename}"
        )
    return digest


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RestPrioritySubsetPromotionError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RestPrioritySubsetPromotionError(f"{label} must be a JSON object")
    typed = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in typed):
        raise RestPrioritySubsetPromotionError(f"{label} must be a JSON object")
    return cast(dict[str, object], typed)


def _jsonl_objects(path: Path, label: str) -> tuple[dict[str, object], ...]:
    regular = _regular_file(path, label)
    try:
        payload = regular.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise RestPrioritySubsetPromotionError(f"{label} is unreadable") from exc
    return _jsonl_payload_objects(payload, label)


def _jsonl_payload_objects(
    payload: bytes | None,
    label: str,
) -> tuple[dict[str, object], ...]:
    if payload is None:
        raise RestPrioritySubsetPromotionError(f"{label} payload is missing")
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise RestPrioritySubsetPromotionError(f"{label} is unreadable") from exc
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise RestPrioritySubsetPromotionError(
                f"{label} contains a blank JSONL row at line {line_number}"
            )
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RestPrioritySubsetPromotionError(
                f"{label} has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(value, dict) or not all(
            isinstance(key, str) for key in cast(dict[object, object], value)
        ):
            raise RestPrioritySubsetPromotionError(
                f"{label} line {line_number} must be a JSON object"
            )
        records.append(cast(dict[str, object], value))
    return tuple(records)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RestPrioritySubsetPromotionError(f"{label} must be an object")
    result = dict(cast(Mapping[object, object], value))
    if not all(isinstance(key, str) for key in result):
        raise RestPrioritySubsetPromotionError(f"{label} must be an object")
    return cast(dict[str, object], result)


def _mapping_list(
    record: Mapping[str, object],
    field: str,
) -> tuple[dict[str, object], ...]:
    value = record.get(field)
    if not isinstance(value, list):
        raise RestPrioritySubsetPromotionError(f"{field} must be a list")
    return tuple(_mapping(item, field) for item in cast(list[object], value))


def _unique_text_list(
    record: Mapping[str, object],
    field: str,
) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list):
        raise RestPrioritySubsetPromotionError(f"{field} must be a list")
    raw = cast(list[object], value)
    if any(not isinstance(item, str) or not item for item in raw):
        raise RestPrioritySubsetPromotionError(f"{field} must contain nonempty strings")
    result = tuple(cast(list[str], raw))
    if len(set(result)) != len(result):
        raise RestPrioritySubsetPromotionError(f"{field} contains duplicates")
    return result


def _record_candidate_id(record: Mapping[str, object]) -> str:
    return _required_text(record, "candidate_id")


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RestPrioritySubsetPromotionError(
            f"record lacks required nonempty {field}"
        )
    return value.strip()


def _required_sha256(record: Mapping[str, object], field: str) -> str:
    value = _required_text(record, field)
    _require_sha256(value, field)
    return value


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise RestPrioritySubsetPromotionError(
            f"expected {label} SHA-256 must be 64 lowercase hex digits"
        )


def _require_date(value: object) -> None:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError("decision_filed_on_or_after must be a date")


def _regular_file(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RestPrioritySubsetPromotionError(
            f"{label} is unavailable: {path}"
        ) from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or not resolved.is_file()
    ):
        raise RestPrioritySubsetPromotionError(
            f"{label} must be a regular file: {path}"
        )
    return resolved


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RestPrioritySubsetPromotionError(
            f"cannot read file for SHA-256: {path}"
        ) from exc


def _candidate_id_set_sha256(candidate_ids: Sequence[str]) -> str:
    return _canonical_sha256(sorted(candidate_ids))


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _canonical_json(value: object) -> str:
    try:
        return canonical_rest_commitment_json_bytes(value).decode()
    except (FirecrawlScreeningIdentityError, UnicodeDecodeError) as exc:
        raise RestPrioritySubsetPromotionError(
            "commitment input is not canonical JSON"
        ) from exc


__all__ = [
    "REST_PRIORITY_DEFERRED_OMISSION_SCHEMA",
    "REST_PRIORITY_SELECTION_POLICY_SCHEMA",
    "REST_TERMINAL_SUBSET_PROMOTION_SCHEMA",
    "REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY",
    "REST_TERMINAL_SUBSET_SOURCE_SCHEMA",
    "REST_TERMINAL_SUBSET_TERM",
    "RestPrioritySubsetPromotionError",
    "RestPrioritySubsetPromotionResult",
    "promote_terminal_rest_priority_tranche",
    "rest_priority_deferred_omission_jsonl_bytes",
    "validate_rest_terminal_subset_promotion_commitment",
]

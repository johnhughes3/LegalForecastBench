"""Conformance tests for provider-free REST priority-tranche promotion.

These tests encode the narrow exception approved for the first, frozen,
acquisition-ranked tranche.  They deliberately exercise the public promotion
API instead of reaching into its implementation helpers.
"""

from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_screening_identity import (
    snapshot_firecrawl_screening_source_count,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
    materialize_direct_search_priority_tranche,
    read_saturated_direct_search_leads,
    read_verified_priority_dedupe_snapshots,
    seed_novel_direct_search_leads,
)
from legalforecast.ingestion.rest_priority_subset_promotion import (
    REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY,
    RestPrioritySubsetPromotionError,
    promote_terminal_rest_priority_tranche,
    validate_rest_terminal_subset_promotion_commitment,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)

_ANCHOR = date(2026, 6, 30)
_ANCHOR_TEXT = _ANCHOR.isoformat()
_SOURCE_BATCH_ID = "novel-direct-search"
_PRIORITY_BATCH_ID = "priority-tranche-1"


@dataclass(frozen=True, slots=True)
class _PromotionFixture:
    store_path: Path
    source_batch_digest: str
    priority_batch_digest: str
    cycle_hash: str
    frontier_path: Path
    frontier_file_sha256: str
    source_snapshot: Path
    source_snapshot_manifest_sha256: str
    policy_path: Path
    policy_sha256: str
    accepted_id: str
    excluded_id: str
    deferred_id: str
    source_exclusion: Mapping[str, Any]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _write_json(path: Path, value: Mapping[str, object]) -> str:
    path.write_text(json.dumps(dict(value), sort_keys=True, separators=(",", ":")))
    return _sha256_file(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text().splitlines()
        if line
    ]


def _snapshot_manifest_sha256(snapshot: Path) -> str:
    return _sha256_file(snapshot / "manifest.json")


def _decision_evidence(docket_id: str, *, entry_number: int) -> dict[str, object]:
    return {
        "id": 8_000 + int(docket_id),
        "docket_entry_id": 7_000 + int(docket_id),
        "entry_number": entry_number,
        "document_number": str(entry_number),
        "description": "ORDER granting motion to dismiss",
        "entry_date_filed": "2026-07-20",
        "absolute_url": f"/api/rest/v4/recap-documents/{8_000 + int(docket_id)}/",
        "is_available": True,
    }


def _build_direct_search_source(store_path: Path) -> None:
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "test-cycle",
                "eligibility_anchor": _ANCHOR_TEXT,
            }
        )
        term = "motion to dismiss"
        store.ensure_batch(
            "direct-search",
            {
                "provider": "courtlistener",
                "search_window_start": _ANCHOR_TEXT,
                "search_window_end": "2026-07-23",
                "query_terms": [term],
                "search_page_size": 100,
            },
        )
        store.ensure_terms("direct-search", (term,))
        store.commit_search_page(
            "direct-search",
            term,
            None,
            tuple(
                {
                    "provider_hit_id": f"hit-{docket_id}",
                    "candidate_id": docket_id,
                    "payload": {
                        "docket_id": docket_id,
                        "court_id": "nysd",
                        "docket_number": f"1:26-cv-{docket_id.zfill(5)}",
                        "case_name": f"Fixture {docket_id} v. Example",
                        "recap_documents": [
                            _decision_evidence(
                                docket_id,
                                entry_number=10 + index,
                            )
                        ],
                    },
                }
                for index, docket_id in enumerate(("101", "102", "103"), start=1)
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )


def _build_prior_snapshot(tmp_path: Path) -> tuple[Path, str]:
    store_path = tmp_path / "prior.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "test-cycle",
                "eligibility_anchor": _ANCHOR_TEXT,
            }
        )
        store.ensure_batch("prior", {"provider": "courtlistener"})
        store.ensure_terms("prior", ("screen",))
        store.commit_search_page(
            "prior",
            "screen",
            None,
            (
                {
                    "provider_hit_id": "prior-999",
                    "candidate_id": "courtlistener-docket-999",
                    "payload": {"candidate_id": "courtlistener-docket-999"},
                },
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "courtlistener-docket-999",
            batch_id="prior",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={
                "candidate_id": "courtlistener-docket-999",
                "decision_date": "2026-06-29",
            },
        )
        snapshot = store.export_snapshot(
            tmp_path / "prior-snapshots",
            snapshot_id="prior-terminal",
            batch_id="prior",
            complete=True,
        )
    return snapshot, _snapshot_manifest_sha256(snapshot)


def _embedded_entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    role: str,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": _ANCHOR_TEXT,
        "text": text,
        "role": role,
        "restriction_markers": [],
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
                "freely_available": not pacer_only,
                "restriction_markers": [],
            }
        ],
    }


def _strict_screen_evidence(
    candidate_id: str,
    *,
    anchor: str = _ANCHOR_TEXT,
) -> dict[str, Any]:
    docket_id = candidate_id.removeprefix("courtlistener-docket-")
    entries = [
        _embedded_entry(
            5,
            "MOTION to Dismiss filed by Defendant.",
            "Motion to Dismiss",
            "https://ecf.nysd.uscourts.gov/doc1/12345",
            role="mtd_notice",
            pacer_only=True,
        ),
        _embedded_entry(
            12,
            "ORDER on Motion to Dismiss.",
            "Order on Motion to Dismiss",
            "https://storage.courtlistener.com/decision.pdf",
            role="decision",
            pacer_only=False,
        ),
    ]
    return {
        "candidate_id": candidate_id,
        "candidate": {
            "docket_id": docket_id,
            "candidate_key": docket_id,
            "metadata": {
                "case_id": candidate_id,
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": f"https://www.courtlistener.com/docket/{docket_id}/fixture/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["12"],
        },
        "first_written_mtd_disposition_date": _ANCHOR_TEXT,
        "eligibility_anchor_date": anchor,
        "selected_entries": entries,
        "mtd_decision_screen": {
            "status": "accepted_strict_civil_mtd_decision",
            "exclusion_reasons": [],
            "actual_mtd_decision_entry_count": 1,
            "decision_entries": [
                {
                    "row_id": "entry-12",
                    "entry_number": "12",
                    "filed_at": _ANCHOR_TEXT,
                    "actual_mtd_decision": True,
                    "exclusion_reasons": [],
                }
            ],
        },
        "motion_linkage": {
            "candidate_id": docket_id,
            "case_id": candidate_id,
            "is_clean": True,
            "links": [
                {
                    "candidate_id": docket_id,
                    "case_id": candidate_id,
                    "motion_entry_ids": ["entry-5"],
                    "disposition_entry_ids": ["entry-12"],
                    "linkage_basis": ["fixture"],
                }
            ],
            "exclusion_entries": [],
        },
    }


def _selection_policy() -> dict[str, object]:
    return {
        "schema_version": "legalforecast.rest_priority_subset_selection_policy.v1",
        "approval_reference": "John approved acquisition-shaped sampling",
        "approved_by": "John Hughes",
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
        "eligibility_anchor_date": _ANCHOR_TEXT,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "model_activity_requested": False,
        "model_activity_executed": False,
    }


def _priority_stage_commitment(config: Mapping[str, Any]) -> dict[str, object]:
    fields = (
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
    return {
        "schema_version": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
        **{field: config[field] for field in fields},
    }


def _build_promotion_fixture(
    tmp_path: Path,
    *,
    accepted_anchor: str = _ANCHOR_TEXT,
    omit_excluded_terminal: bool = False,
) -> _PromotionFixture:
    store_path = tmp_path / "cycle.sqlite3"
    _build_direct_search_source(store_path)
    prior_snapshot, prior_manifest_sha256 = _build_prior_snapshot(tmp_path)

    source = read_saturated_direct_search_leads(
        store_path,
        source_batch_id="direct-search",
    )
    prior = read_verified_priority_dedupe_snapshots(
        (prior_snapshot,),
        expected_manifest_sha256=(prior_manifest_sha256,),
    )
    with CycleAcquisitionStore(store_path) as store:
        seed_novel_direct_search_leads(
            store,
            batch_id=_SOURCE_BATCH_ID,
            source=source,
            prior_snapshots=prior,
        )
    novel_source = read_saturated_direct_search_leads(
        store_path,
        source_batch_id=_SOURCE_BATCH_ID,
    )
    with CycleAcquisitionStore(store_path) as store:
        tranche = materialize_direct_search_priority_tranche(
            store,
            batch_id=_PRIORITY_BATCH_ID,
            source=novel_source,
            tranche_size=2,
        )
        accepted_id, excluded_id = tranche.selected_candidate_ids
        [deferred_id] = tranche.deferred_candidate_ids
        store.record_observation(
            accepted_id,
            batch_id=_PRIORITY_BATCH_ID,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence=_strict_screen_evidence(
                accepted_id,
                anchor=accepted_anchor,
            ),
            observed_at="2026-07-24T12:00:00+00:00",
        )
        exclusion_evidence: dict[str, Any] = {
            "candidate_id": excluded_id,
            "exclusion_reason": "strict_clean_screen_failed",
            "source": "strict_rest_screen",
        }
        if not omit_excluded_terminal:
            store.record_observation(
                excluded_id,
                batch_id=_PRIORITY_BATCH_ID,
                state="excluded",
                reason_code="strict_clean_screen_failed",
                evidence=exclusion_evidence,
                observed_at="2026-07-24T12:01:00+00:00",
            )
        config = store.batch_config(_PRIORITY_BATCH_ID)
        priority_batch_digest = store.batch_digest(_PRIORITY_BATCH_ID)
        source_batch_digest = store.batch_digest(_SOURCE_BATCH_ID)
        cycle_hash = store.cycle_hash
        source_snapshot = store.export_snapshot(
            tmp_path / "priority-snapshots",
            snapshot_id="priority-terminal",
            batch_id=_PRIORITY_BATCH_ID,
            complete=not omit_excluded_terminal,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                },
                "direct_search_priority_tranche": _priority_stage_commitment(config),
            },
        )

    frontier_path = tmp_path / "priority-frontier.json"
    frontier_file_sha256 = _write_json(
        frontier_path,
        tranche.frontier,
    )
    policy_path = tmp_path / "selection-policy.json"
    policy_sha256 = _write_json(policy_path, _selection_policy())
    source_exclusion = (
        {
            "candidate_id": excluded_id,
            "reason": "strict_clean_screen_failed",
            "primary_exclusion_reason": "strict_clean_screen_failed",
            **exclusion_evidence,
        }
        if omit_excluded_terminal
        else next(
            row
            for row in _read_jsonl(source_snapshot / "exclusions.jsonl")
            if row["candidate_id"] == excluded_id
        )
    )
    return _PromotionFixture(
        store_path=store_path,
        source_batch_digest=source_batch_digest,
        priority_batch_digest=priority_batch_digest,
        cycle_hash=cycle_hash,
        frontier_path=frontier_path,
        frontier_file_sha256=frontier_file_sha256,
        source_snapshot=source_snapshot,
        source_snapshot_manifest_sha256=_snapshot_manifest_sha256(source_snapshot),
        policy_path=policy_path,
        policy_sha256=policy_sha256,
        accepted_id=accepted_id,
        excluded_id=excluded_id,
        deferred_id=deferred_id,
        source_exclusion=source_exclusion,
    )


def _promote(
    fixture: _PromotionFixture,
    tmp_path: Path,
    *,
    target_batch_id: str = "promoted-priority-terminal-subset",
    decision_filed_on_or_after: date = _ANCHOR,
) -> object:
    with CycleAcquisitionStore(fixture.store_path) as store:
        return promote_terminal_rest_priority_tranche(
            store,
            priority_batch_id=_PRIORITY_BATCH_ID,
            expected_priority_batch_digest=fixture.priority_batch_digest,
            priority_snapshot=fixture.source_snapshot,
            expected_priority_snapshot_manifest_sha256=(
                fixture.source_snapshot_manifest_sha256
            ),
            priority_frontier=fixture.frontier_path,
            expected_priority_frontier_file_sha256=fixture.frontier_file_sha256,
            selection_policy=fixture.policy_path,
            expected_selection_policy_sha256=fixture.policy_sha256,
            expected_source_batch_digest=fixture.source_batch_digest,
            expected_cycle_hash=fixture.cycle_hash,
            decision_filed_on_or_after=decision_filed_on_or_after,
            target_batch_id=target_batch_id,
            snapshot_root=tmp_path / "promoted-snapshots",
            snapshot_id=f"{target_batch_id}-snapshot",
        )


def _promoted_snapshot_path(tmp_path: Path) -> Path:
    return (
        tmp_path / "promoted-snapshots" / "promoted-priority-terminal-subset-snapshot"
    )


def _build_disjoint_ordinary_rest_snapshot(
    fixture: _PromotionFixture,
    tmp_path: Path,
) -> Path:
    candidate_id = "courtlistener-docket-999"
    with CycleAcquisitionStore(fixture.store_path) as store:
        store.ensure_batch(
            "ordinary-rest-screen",
            {
                "provider": "courtlistener",
                "query_terms": ["ordinary-rest-screen"],
                "provider_activity_requested": False,
                "paid_activity_requested": False,
            },
        )
        store.ensure_terms("ordinary-rest-screen", ("ordinary-rest-screen",))
        store.commit_search_page(
            "ordinary-rest-screen",
            "ordinary-rest-screen",
            None,
            (
                {
                    "provider_hit_id": "ordinary-rest-999",
                    "candidate_id": candidate_id,
                    "payload": {
                        "candidate_id": candidate_id,
                        "docket_id": "999",
                        "provider": "courtlistener-rest-v4",
                    },
                },
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            candidate_id,
            batch_id="ordinary-rest-screen",
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={
                "candidate_id": candidate_id,
                "exclusion_reason": "strict_clean_screen_failed",
                "source": "ordinary_rest_screen",
            },
            observed_at="2026-07-24T12:02:00+00:00",
        )
        return store.export_snapshot(
            tmp_path / "ordinary-rest-snapshots",
            snapshot_id="ordinary-rest-terminal",
            batch_id="ordinary-rest-screen",
            complete=True,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )


def test_promotes_mixed_terminal_subset_and_preserves_exclusion(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)

    _promote(fixture, tmp_path)

    target = _promoted_snapshot_path(tmp_path)
    manifest = cast(dict[str, Any], json.loads((target / "manifest.json").read_text()))
    stage = cast(
        dict[str, Any],
        manifest["stage_commitments"][REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY],
    )
    assert manifest["complete"] is True
    assert manifest["saturated"] is True
    assert "direct_search_priority_tranche" not in manifest["stage_commitments"]
    assert stage["final_cohort_eligible"] is True
    assert stage["full_source_terminal"] is True
    assert stage["selection_semantics"] == "exact_frozen_priority_tranche"
    assert stage["terminality_scope"] == "promoted_exact_selected_source"
    assert stage["parent_source_fully_screened"] is False

    candidates = _read_jsonl(target / "candidates.jsonl")
    assert {row["candidate_id"] for row in candidates} == {
        fixture.accepted_id,
        fixture.excluded_id,
    }
    [target_exclusion] = _read_jsonl(target / "exclusions.jsonl")
    assert target_exclusion == fixture.source_exclusion


def test_omission_inventory_is_exact_and_never_an_exclusion(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    target = _promoted_snapshot_path(tmp_path)
    manifest = cast(dict[str, Any], json.loads((target / "manifest.json").read_text()))
    commitment = cast(
        dict[str, Any],
        manifest["stage_commitments"][REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY],
    )

    inventory = cast(dict[str, Any], commitment["deferred_omission_inventory"])
    assert inventory["disposition"] == "unscreened_not_excluded"
    assert inventory["candidate_ids"] == [fixture.deferred_id]
    assert inventory["candidate_count"] == 1
    assert inventory["candidate_id_set_sha256"] == _canonical_sha256(
        [fixture.deferred_id]
    )
    assert fixture.deferred_id not in {
        row["candidate_id"] for row in _read_jsonl(target / "exclusions.jsonl")
    }
    with CycleAcquisitionStore(fixture.store_path) as store:
        assert (
            store.batch_terminal_observation(
                "promoted-priority-terminal-subset",
                fixture.deferred_id,
            )
            is None
        )


def test_promoted_rest_snapshot_has_zero_firecrawl_screening_sources(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    manifest = cast(
        dict[str, Any],
        json.loads((_promoted_snapshot_path(tmp_path) / "manifest.json").read_text()),
    )

    assert (
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )
        == 0
    )


def test_union_accepts_disjoint_ordinary_rest_and_promoted_mixed_subset(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    ordinary = _build_disjoint_ordinary_rest_snapshot(fixture, tmp_path)

    union = load_screening_snapshot_union(
        (ordinary, promoted),
        expected_manifest_sha256=(
            _snapshot_manifest_sha256(ordinary),
            _snapshot_manifest_sha256(promoted),
        ),
        expected_cycle_hash=fixture.cycle_hash,
    )

    assert {candidate.candidate_id for candidate in union.candidates} == {
        fixture.accepted_id,
        fixture.excluded_id,
        "courtlistener-docket-999",
    }
    assert "provisional_frontier" not in union.stage_commitment
    assert "full_source_terminal" not in union.stage_commitment
    assert union.stage_commitment["candidate_count"] == 3


def test_union_rejects_repinned_promotion_commitment_tamper(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    ordinary = _build_disjoint_ordinary_rest_snapshot(fixture, tmp_path)
    manifest_path = promoted / "manifest.json"
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    commitment = cast(
        dict[str, Any],
        manifest["stage_commitments"][REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY],
    )
    commitment["provider_activity_executed"] = True
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match=r"(activity flags|provider|promotion)",
    ):
        load_screening_snapshot_union(
            (ordinary, promoted),
            expected_manifest_sha256=(
                _snapshot_manifest_sha256(ordinary),
                _snapshot_manifest_sha256(promoted),
            ),
            expected_cycle_hash=fixture.cycle_hash,
        )


def test_raw_incomplete_priority_tranche_still_rejects_mixed_union(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    ordinary = _build_disjoint_ordinary_rest_snapshot(fixture, tmp_path)

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match=r"(priority-tranche|provisional|complete|chain)",
    ):
        load_screening_snapshot_union(
            (ordinary, fixture.source_snapshot),
            expected_manifest_sha256=(
                _snapshot_manifest_sha256(ordinary),
                fixture.source_snapshot_manifest_sha256,
            ),
            expected_cycle_hash=fixture.cycle_hash,
        )


def test_rejects_strict_acceptance_with_self_declared_anchor_drift(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(
        tmp_path,
        accepted_anchor="2026-07-01",
    )

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(eligibility anchor|2026-06-30)",
    ):
        _promote(fixture, tmp_path)


def test_rejects_anchor_that_differs_from_frozen_cycle_policy(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"frozen cycle policy",
    ):
        _promote(
            fixture,
            tmp_path,
            decision_filed_on_or_after=date(2026, 7, 1),
        )


def test_rejects_unpinned_frontier_bytes(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    fixture.frontier_path.write_text(fixture.frontier_path.read_text() + " ")

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"frontier.*SHA-256",
    ):
        _promote(fixture, tmp_path)


@pytest.mark.parametrize(
    "mutation",
    (
        "frontier_self_hash",
        "selected_deferred_overlap",
        "selected_partition_drift",
    ),
)
def test_rejects_authenticated_frontier_tampering(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    frontier = cast(dict[str, Any], json.loads(fixture.frontier_path.read_text()))
    if mutation == "frontier_self_hash":
        frontier["frontier_sha256"] = "0" * 64
    elif mutation == "selected_deferred_overlap":
        frontier["deferred_candidate_ids"] = [
            fixture.accepted_id,
            fixture.deferred_id,
        ]
    else:
        frontier["selected_candidate_ids"] = [fixture.accepted_id]
    if mutation != "frontier_self_hash":
        without_self_hash = dict(frontier)
        without_self_hash.pop("frontier_sha256")
        frontier["frontier_sha256"] = _canonical_sha256(without_self_hash)
    fixture.frontier_path.write_text(
        json.dumps(frontier, sort_keys=True, separators=(",", ":")) + "\n"
    )
    tampered_file_hash = _sha256_file(fixture.frontier_path)
    tampered = replace(
        fixture,
        frontier_file_sha256=tampered_file_hash,
    )

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(frontier|partition|selected|deferred)",
    ):
        _promote(tampered, tmp_path)


def test_rejects_priority_snapshot_with_missing_terminal(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path, omit_excluded_terminal=True)

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(complete|terminal|selected)",
    ):
        _promote(fixture, tmp_path)


def test_rejects_altered_exclusion_even_under_a_rehashed_manifest(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    exclusions_path = fixture.source_snapshot / "exclusions.jsonl"
    [exclusion] = _read_jsonl(exclusions_path)
    exclusion["reason"] = "altered_after_screen"
    exclusions_path.write_text(json.dumps(exclusion, sort_keys=True) + "\n")
    manifest_path = fixture.source_snapshot / "manifest.json"
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    payload = exclusions_path.read_bytes()
    manifest["files"]["exclusions.jsonl"] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": payload.count(b"\n"),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )
    altered = replace(
        fixture,
        source_snapshot_manifest_sha256=_sha256_file(manifest_path),
    )

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(exclusion|snapshot|observation|reconcile)",
    ):
        _promote(altered, tmp_path)


@pytest.mark.parametrize(
    "field",
    (
        "outcome_polarity_used",
        "stage_b_labels_used",
        "model_outputs_used",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
    ),
)
def test_rejects_policy_forbidden_inputs_or_activity(
    tmp_path: Path,
    field: str,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    policy = cast(dict[str, object], json.loads(fixture.policy_path.read_text()))
    policy[field] = True
    policy_sha256 = _write_json(fixture.policy_path, policy)
    altered = replace(
        fixture,
        policy_sha256=policy_sha256,
    )

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(selection policy|activity|model|outcome|label)",
    ):
        _promote(altered, tmp_path)


def test_rejects_selection_policy_hash_tampering(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    fixture.policy_path.write_text(fixture.policy_path.read_text() + " ")

    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"selection policy.*SHA-256",
    ):
        _promote(fixture, tmp_path)


def test_commitment_validator_rejects_omission_overlap_and_terminal_drift(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    target = _promoted_snapshot_path(tmp_path)
    manifest = cast(dict[str, Any], json.loads((target / "manifest.json").read_text()))
    commitment = cast(
        dict[str, Any],
        manifest["stage_commitments"][REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY],
    )
    accepted = (fixture.accepted_id,)
    excluded = (fixture.excluded_id,)
    selected = tuple(sorted((*accepted, *excluded)))

    validate_rest_terminal_subset_promotion_commitment(
        commitment,
        snapshot_candidate_ids=selected,
        snapshot_accepted_ids=accepted,
        snapshot_excluded_ids=excluded,
    )
    overlap = deepcopy(commitment)
    overlap_inventory = cast(
        dict[str, Any],
        overlap["deferred_omission_inventory"],
    )
    overlap_inventory["candidate_ids"] = [
        fixture.accepted_id,
        fixture.deferred_id,
    ]
    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(overlap|partition|deferred)",
    ):
        validate_rest_terminal_subset_promotion_commitment(
            overlap,
            snapshot_candidate_ids=selected,
            snapshot_accepted_ids=accepted,
            snapshot_excluded_ids=excluded,
        )
    with pytest.raises(
        RestPrioritySubsetPromotionError,
        match=r"(accepted|excluded|terminal|candidate)",
    ):
        validate_rest_terminal_subset_promotion_commitment(
            commitment,
            snapshot_candidate_ids=selected,
            snapshot_accepted_ids=(),
            snapshot_excluded_ids=excluded,
        )


def test_promotion_has_no_network_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)

    def forbid_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("REST priority promotion attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    _promote(fixture, tmp_path)


def test_cli_help_documents_narrow_provider_free_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            ["acquisition", "promote-terminal-rest-priority-subset", "--help"]
        )
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "acquisition-shaped" in output
    assert "nonrepresentative" in output
    assert "unscreened_not_excluded" in output
    assert "no network" in output.lower()
    assert "provider" in output.lower()
    for forbidden_option in (
        "--acknowledge-pacer-fees",
        "--purchase",
        "--provider-token",
        "--model",
        "--evaluate",
        "--freeze",
        "--dispatch",
    ):
        assert forbidden_option not in output

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    export_observation_manifest,
    generate_cohort_policy,
    read_observation_manifest,
    verify_cohort_policy,
    verify_observation_manifest,
    write_cohort_policy,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
    cohort_reason_policy_taxonomy,
)


def test_policy_generation_is_stable_and_tampering_fails() -> None:
    decisions = _decisions("a" * 64)
    first = generate_cohort_policy(decisions)
    second = generate_cohort_policy(json.loads(json.dumps(decisions)))

    assert first == second
    assert verify_cohort_policy(first) == first["policy_sha256"]
    tampered = json.loads(json.dumps(first))
    tampered["policy"]["window_policy"]["overlap_days"] = 8
    with pytest.raises(CohortPolicyError, match="hash does not match"):
        verify_cohort_policy(tampered)


def test_policy_rejects_forbidden_restatement_and_inconsistent_values() -> None:
    decisions = _decisions("a" * 64)
    decisions["cycle_series"] = "official"
    with pytest.raises(CohortPolicyError, match=r"extra=\['cycle_series'\]"):
        generate_cohort_policy(decisions)

    decisions = _decisions("a" * 64)
    decisions["reduced_n"]["target_clean_cases"] = 149
    with pytest.raises(CohortPolicyError, match="target must match"):
        generate_cohort_policy(decisions)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("overlap", "ordered, contiguous, and non-overlapping"),
        ("gap", "ordered, contiguous, and non-overlapping"),
        ("reordered", "ordered, contiguous, and non-overlapping"),
        ("wrong_end", "terminate exactly"),
        ("threshold_without_action", "requires minimum_prediction_units"),
        ("non_downgrade", "must be a lower claim class"),
        ("non_monotone_claim", "strictly increase"),
        ("terminal_not_target", "must use claim_class target"),
        ("bad_below_minimum", "below_minimum_action is unsupported"),
    ],
)
def test_policy_rejects_invalid_reduced_n_tiers(mutation: str, message: str) -> None:
    decisions = _decisions("a" * 64)
    reduced = decisions["reduced_n"]
    assert isinstance(reduced, dict)
    tiers = reduced["claim_tiers"]
    assert isinstance(tiers, list)
    if mutation == "overlap":
        tiers[1]["minimum_clean_cases"] = 99
    elif mutation == "gap":
        tiers[1]["minimum_clean_cases"] = 101
    elif mutation == "reordered":
        tiers[0], tiers[1] = tiers[1], tiers[0]
    elif mutation == "wrong_end":
        tiers[-1]["maximum_clean_cases"] = 151
    elif mutation == "threshold_without_action":
        tiers[0]["insufficient_units_action"] = "pilot_only_no_official_cycle"
    elif mutation == "non_downgrade":
        tiers[1]["insufficient_units_action"] = "target"
    elif mutation == "non_monotone_claim":
        tiers[1]["claim_class"] = "provisional_feasibility"
    elif mutation == "terminal_not_target":
        tiers.pop()
        tiers[-1]["maximum_clean_cases"] = 150
    else:
        reduced["below_minimum_action"] = "official_descriptive"
    with pytest.raises(CohortPolicyError, match=message):
        generate_cohort_policy(decisions)

    decisions = _decisions("a" * 64)
    decisions["refresh_policy"]["evidence_precedence"]["accepted"] = 5
    with pytest.raises(CohortPolicyError, match="must increase"):
        generate_cohort_policy(decisions)


@pytest.mark.parametrize("mutation", ["omission", "extra", "misclassification"])
def test_policy_rejects_reason_taxonomy_drift(mutation: str) -> None:
    decisions = _decisions("a" * 64)
    refresh = decisions["refresh_policy"]
    assert isinstance(refresh, dict)
    if mutation == "omission":
        refresh["immutable_reason_codes"] = refresh["immutable_reason_codes"][1:]
    elif mutation == "extra":
        refresh["transient_reason_codes"] = [
            *refresh["transient_reason_codes"],
            "invented_reason",
        ]
    else:
        moved = refresh["immutable_reason_codes"][0]
        refresh["immutable_reason_codes"] = refresh["immutable_reason_codes"][1:]
        refresh["refreshable_reason_codes"] = [
            *refresh["refreshable_reason_codes"],
            moved,
        ]
    with pytest.raises(CohortPolicyError, match="cycle-store reason taxonomy"):
        generate_cohort_policy(decisions)


def test_policy_taxonomy_classifies_new_exclusion_reasons() -> None:
    taxonomy = cohort_reason_policy_taxonomy()

    assert "procedural_or_standing_order" in taxonomy["immutable_reason_codes"]
    assert "oversized_docket_soft_skip" in taxonomy["refreshable_reason_codes"]


def test_policy_file_is_immutable(tmp_path: Path) -> None:
    path = tmp_path / "cohort-policy.json"
    artifact = generate_cohort_policy(_decisions("a" * 64))
    write_cohort_policy(path, artifact)
    write_cohort_policy(path, artifact)

    changed = generate_cohort_policy(
        {**_decisions("a" * 64), "cycle_id": "another-cycle"}
    )
    with pytest.raises(CohortPolicyError, match="different immutable content"):
        write_cohort_policy(path, changed)


def test_observation_export_appends_verified_snapshots_only(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    snapshot_root = tmp_path / "snapshots"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
        store.ensure_batch("batch-001", {"window": "one"})
        store.ensure_terms("batch-001", ["term"])
        store.commit_search_page(
            "batch-001", "term", None, [], next_cursor=None, terminal_status="exhausted"
        )
        store.export_snapshot(
            snapshot_root,
            snapshot_id="batch-001-snapshot",
            batch_id="batch-001",
            complete=True,
        )
        policy = generate_cohort_policy(_decisions(cycle_hash))
        manifest_path = tmp_path / "cohort-observations.jsonl"
        first = export_observation_manifest(
            store=store, policy_artifact=policy, destination=manifest_path
        )
        first_bytes = manifest_path.read_bytes()
        store.ensure_batch("batch-002", {"window": "two"})
        store.ensure_terms("batch-002", ["term"])
        store.commit_search_page(
            "batch-002",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.export_snapshot(
            snapshot_root,
            snapshot_id="batch-002-snapshot",
            batch_id="batch-002",
            complete=True,
        )
        second = export_observation_manifest(
            store=store, policy_artifact=policy, destination=manifest_path
        )
        second_bytes = manifest_path.read_bytes()
        third = export_observation_manifest(
            store=store, policy_artifact=policy, destination=manifest_path
        )

    assert second == third
    assert manifest_path.read_bytes() == second_bytes
    assert second_bytes.startswith(first_bytes)
    assert len(second_bytes) > len(first_bytes)
    assert [record["record_type"] for record in first] == ["header", "snapshot"]
    assert [record["record_type"] for record in second] == [
        "header",
        "snapshot",
        "snapshot",
    ]
    assert (
        verify_observation_manifest(second, policy_artifact=policy)
        == second[-1]["record_sha256"]
    )

    tampered = [dict(record) for record in second]
    tampered[1]["batch_id"] = "batch-999"
    with pytest.raises(CohortPolicyError, match="hash does not match"):
        verify_observation_manifest(tampered, policy_artifact=policy)


def test_provisional_snapshot_coexists_with_later_publishable_snapshot(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    snapshot_root = tmp_path / "snapshots"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
        store.ensure_batch(
            "provisional",
            {
                "provisional_frontier": True,
                "final_cohort_eligible": False,
                "full_source_terminal": False,
            },
        )
        store.ensure_terms("provisional", ["term"])
        store.commit_search_page(
            "provisional",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="limit_bound",
        )
        provisional_path = store.export_snapshot(
            snapshot_root,
            snapshot_id="provisional-snapshot",
            batch_id="provisional",
            complete=True,
        )
        store.ensure_batch("final", {"window": "final"})
        store.ensure_terms("final", ["term"])
        store.commit_search_page(
            "final",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="exhausted",
        )
        final_path = store.export_snapshot(
            snapshot_root,
            snapshot_id="final-snapshot",
            batch_id="final",
            complete=True,
        )

        published = store.published_snapshots()
        observations = export_observation_manifest(
            store=store,
            policy_artifact=generate_cohort_policy(_decisions(cycle_hash)),
            destination=tmp_path / "observations.jsonl",
        )

    assert [snapshot.snapshot_id for snapshot in published] == ["final-snapshot"]
    assert [record.get("snapshot_id") for record in observations[1:]] == [
        "final-snapshot"
    ]
    assert provisional_path.is_dir()
    assert final_path.is_dir()


@pytest.mark.parametrize(
    "malformed_config",
    [
        {"provisional_frontier": True},
        {
            "provisional_frontier": True,
            "final_cohort_eligible": True,
            "full_source_terminal": False,
        },
        {"final_cohort_eligible": False, "full_source_terminal": False},
    ],
)
def test_export_snapshot_rejects_malformed_provisional_markers(
    tmp_path: Path,
    malformed_config: dict[str, object],
) -> None:
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
        store.ensure_batch("malformed", malformed_config)
        store.ensure_terms("malformed", ["term"])
        store.commit_search_page(
            "malformed",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="exhausted",
        )
        with pytest.raises(
            SnapshotVerificationError,
            match="contradictory cohort-safety flags",
        ):
            store.export_snapshot(
                tmp_path / "snapshots",
                snapshot_id="malformed-snapshot",
                batch_id="malformed",
                complete=True,
            )


def test_observation_export_rejects_unsaturated_snapshot(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
        store.ensure_batch("batch-001", {"window": "one"})
        store.ensure_terms("batch-001", ["term"])
        store.commit_search_page(
            "batch-001",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="limit_bound",
        )
        store.export_snapshot(
            tmp_path / "snapshots",
            snapshot_id="unsaturated",
            batch_id="batch-001",
            complete=True,
        )
        with pytest.raises(CycleAcquisitionStoreError, match="require saturated"):
            export_observation_manifest(
                store=store,
                policy_artifact=generate_cohort_policy(_decisions(cycle_hash)),
                destination=tmp_path / "observations.jsonl",
            )


def test_observation_export_reverifies_existing_same_id_snapshot(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    snapshot_root = tmp_path / "snapshots"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
        store.ensure_batch("batch-001", {"window": "one"})
        store.ensure_terms("batch-001", ["term"])
        store.commit_search_page(
            "batch-001", "term", None, [], next_cursor=None, terminal_status="exhausted"
        )
        snapshot = store.export_snapshot(
            snapshot_root,
            snapshot_id="same-id",
            batch_id="batch-001",
            complete=True,
        )
        policy = generate_cohort_policy(_decisions(cycle_hash))
        destination = tmp_path / "observations.jsonl"
        export_observation_manifest(
            store=store, policy_artifact=policy, destination=destination
        )
        manifest_path = snapshot / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = "2099-01-01T00:00:00Z"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(CohortPolicyError, match="snapshot manifest"):
            export_observation_manifest(
                store=store, policy_artifact=policy, destination=destination
            )


def test_cohort_policy_and_observation_cli_round_trip(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"schema": "test", "anchor": "2026-06-30"})
    decisions_path = tmp_path / "decisions.json"
    policy_path = tmp_path / "cohort-policy.json"
    manifest_path = tmp_path / "cohort-observations.jsonl"
    decisions_path.write_text(json.dumps(_decisions(cycle_hash)), encoding="utf-8")

    assert (
        main(
            [
                "acquisition",
                "generate-cohort-policy",
                "--decisions",
                str(decisions_path),
                "--output",
                str(policy_path),
            ]
        )
        == 0
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert (
        main(
            [
                "acquisition",
                "verify-cohort-policy",
                "--policy",
                str(policy_path),
                "--expected-sha256",
                policy["policy_sha256"],
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "export-cohort-observations",
                "--cycle-store",
                str(store_path),
                "--policy",
                str(policy_path),
                "--output",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "verify-cohort-observations",
                "--manifest",
                str(manifest_path),
                "--policy",
                str(policy_path),
            ]
        )
        == 0
    )
    assert len(read_observation_manifest(manifest_path)) == 1


def _decisions(cycle_hash: str) -> dict[str, object]:
    taxonomy = cohort_reason_policy_taxonomy()
    return {
        "cycle_id": "cycle-1",
        "cycle_acquisition_hash": cycle_hash,
        "eligibility_anchor": "2026-06-30",
        "stop_rule": {
            "mode": "target_or_deadline",
            "target_clean_cases": 150,
            "search_window_end": "2026-08-15",
            "stop_on_frontier_exhaustion": True,
            "stop_on_budget_headroom_exhaustion": True,
        },
        "window_policy": {
            "overlap_days": 7,
            "backfill_late_indexed": True,
            "refresh_before_purchase": True,
        },
        "refresh_policy": {
            **{field: list(reason_codes) for field, reason_codes in taxonomy.items()},
            "evidence_precedence": {
                "transient": 0,
                "excluded_refreshable": 10,
                "accepted": 20,
                "newly_free": 30,
                "excluded_immutable": 100,
            },
            "transition_semantics": {
                "immutable_reconsideration": "never",
                "transient_supersedes_evidenced": False,
                "higher_rank_supersedes_lower_rank": True,
                "latest_wins_equal_rank": True,
            },
        },
        "packet_completeness": {
            "motion_or_combined_memorandum_required": True,
            "opposition_required_if_docketed": True,
            "reply_required": False,
        },
        "target_motion": {
            "selector": "earliest_eligible_mtd_then_lowest_entry_number",
            "exactly_one_per_candidate": True,
        },
        "purchase_policy": {
            "rule": "buy_cheapest_complete",
            "cycle_budget_usd": "100.00",
            "max_per_case_usd": "3.00",
            "reservation_headroom_required": True,
        },
        "disclosure_clearance": {
            "all_documents_require_clearance": True,
            "unknown_or_unscannable": "quarantine",
            "replacement_rule": "next_cheapest_eligible_under_same_cap",
        },
        "reduced_n": {
            "target_clean_cases": 150,
            "claim_tiers": [
                {
                    "minimum_clean_cases": 40,
                    "maximum_clean_cases": 99,
                    "claim_class": "provisional_feasibility",
                    "minimum_prediction_units": None,
                    "insufficient_units_action": None,
                },
                {
                    "minimum_clean_cases": 100,
                    "maximum_clean_cases": 149,
                    "claim_class": "official_descriptive",
                    "minimum_prediction_units": 200,
                    "insufficient_units_action": "provisional_feasibility",
                },
                {
                    "minimum_clean_cases": 150,
                    "maximum_clean_cases": 150,
                    "claim_class": "target",
                    "minimum_prediction_units": None,
                    "insufficient_units_action": None,
                },
            ],
            "below_minimum_action": "pilot_only_no_official_cycle",
        },
    }

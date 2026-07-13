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
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore


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

    decisions = _decisions("a" * 64)
    decisions["refresh_policy"]["evidence_precedence"]["accepted"] = 5
    with pytest.raises(CohortPolicyError, match="must increase"):
        generate_cohort_policy(decisions)


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
            "immutable_reason_codes": ["not_federal_district_court"],
            "refreshable_reason_codes": ["strict_clean_screen_failed"],
            "transient_reason_codes": ["fetch_error"],
            "evidence_precedence": {
                "transient": 0,
                "excluded_refreshable": 10,
                "accepted": 20,
                "newly_free": 30,
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
            "minimum_clean_cases": 100,
            "target_clean_cases": 150,
            "claim_class": "official_descriptive",
        },
    }

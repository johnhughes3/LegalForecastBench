from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
    verify_snapshot,
)
from legalforecast.ingestion.rest_observation_policy_rebind import (
    RestObservationPolicyRebindError,
    RestObservationRebindContract,
    load_official_rest_observation_rebind_contract,
    rebind_terminal_rest_observations,
    verify_official_rest_observation_rebind_semantics,
)
from legalforecast.ingestion.screening_snapshot_union import (
    load_screening_snapshot_union,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy(courtlistener_sha256: str) -> dict[str, object]:
    return {
        "eligibility_anchor": "2026-06-30",
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "screening_source_sha256": {
            "contamination_filters": "a" * 64,
            "courtlistener_acquisition": courtlistener_sha256,
            "motion_linkage": "b" * 64,
            "mtd_acquisition_screen": "c" * 64,
            "restricted_material": "d" * 64,
        },
    }


def _commit_batch(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    candidate_ids: tuple[str, ...],
) -> None:
    store.ensure_batch(batch_id, {"kind": "test", "batch_id": batch_id})
    store.ensure_terms(batch_id, ("fixture",))
    store.commit_search_page(
        batch_id,
        "fixture",
        None,
        tuple(
            DiscoveryHit(
                provider_hit_id=f"hit-{candidate_id}",
                candidate_id=candidate_id,
                payload={
                    "docket_id": candidate_id.removeprefix("courtlistener-docket-")
                },
            )
            for candidate_id in candidate_ids
        ),
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )


def _record(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    candidate_id: str,
    state: str,
    reason_code: str,
    evidence: dict[str, object],
) -> None:
    store.record_observation(
        candidate_id,
        batch_id=batch_id,
        state=state,
        reason_code=reason_code,
        evidence={**evidence, "candidate_id": candidate_id},
        observed_at="2026-07-16T12:00:00Z",
        audit_immutable_skip=False,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _fixture(tmp_path: Path) -> dict[str, object]:
    old_sha = "1" * 64
    new_sha = "2" * 64
    source_policy = _policy(old_sha)
    target_policy = _policy(new_sha)
    source_store_path = tmp_path / "source.sqlite3"
    target_store_path = tmp_path / "target.sqlite3"
    source_batch_id = "opinions-prefix"
    target_batch_id = "current-prefix"
    overlap = "courtlistener-docket-100"
    novel_excluded = "courtlistener-docket-200"
    novel_accepted = "courtlistener-docket-300"
    selected_ids = (overlap, novel_excluded, novel_accepted)

    with CycleAcquisitionStore(source_store_path) as source:
        source_cycle_hash = source.ensure_cycle(source_policy)
        _commit_batch(source, batch_id=source_batch_id, candidate_ids=selected_ids)
        _record(
            source,
            batch_id=source_batch_id,
            candidate_id=overlap,
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={"provider": "courtlistener-recap-rest-v4", "overlap": True},
        )
        _record(
            source,
            batch_id=source_batch_id,
            candidate_id=novel_excluded,
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={"provider": "courtlistener-recap-rest-v4", "novel": True},
        )
        _record(
            source,
            batch_id=source_batch_id,
            candidate_id=novel_accepted,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                "provider": "courtlistener-recap-rest-v4",
                "novel": True,
                "canonical_rest_screen_complete": True,
                "selected_entries": [{"row_id": "entry-4", "role": "mtd_notice"}],
                "ai": {
                    "target_motion_entry_numbers": ["4"],
                    "decision_entry_numbers": ["9"],
                },
                "mtd_decision_screen": {
                    "actual_mtd_decision_entry_count": 1,
                    "anchor_disposition_entries": [{"row_id": "entry-9"}],
                },
                "motion_linkage": {
                    "links": [
                        {
                            "motion_entry_ids": ["entry-4"],
                            "disposition_entry_ids": ["entry-9"],
                        }
                    ]
                },
            },
        )
        source_snapshot = source.export_snapshot(
            tmp_path / "source-snapshots",
            snapshot_id="source-complete",
            batch_id=source_batch_id,
            complete=True,
        )

    selection = {
        "schema_version": "legalforecast.case_dev_ranked_rest_selection_run.v1",
        "batch_id": source_batch_id,
        "leads_selected": len(selected_ids),
        "selected_candidate_set_sha256": "3" * 64,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "selected": [
            {
                "docket_id": candidate_id.removeprefix("courtlistener-docket-"),
                "rank": rank,
            }
            for rank, candidate_id in enumerate(selected_ids, start=1)
        ],
    }
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(json.dumps(selection, sort_keys=True) + "\n")

    source_observations = {
        row["candidate_id"]: row
        for row in _read_jsonl(source_snapshot / "observations.jsonl")
    }
    outcomes = tuple(
        {
            "candidate_id": candidate_id,
            "state": source_observations[candidate_id]["state"],
            "reason_code": source_observations[candidate_id]["reason_code"],
            "source_observation_sha256": _canonical_sha256(
                source_observations[candidate_id]
            ),
        }
        for candidate_id in sorted((novel_excluded, novel_accepted))
    )
    with CycleAcquisitionStore(target_store_path) as target:
        target_cycle_hash = target.ensure_cycle(target_policy)
        prior_batch_id = "legacy-current"
        _commit_batch(target, batch_id=prior_batch_id, candidate_ids=(overlap,))
        _record(
            target,
            batch_id=prior_batch_id,
            candidate_id=overlap,
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={"provider": "courtlistener-recap-rest-v4", "overlap": True},
        )
        prior_snapshot = target.export_snapshot(
            tmp_path / "target-source-snapshots",
            snapshot_id="target-prior-complete",
            batch_id=prior_batch_id,
            complete=True,
        )
        supplemental_batch_id = "supplemental-current"
        supplemental_candidate = "courtlistener-docket-400"
        _commit_batch(
            target,
            batch_id=supplemental_batch_id,
            candidate_ids=(supplemental_candidate,),
        )
        _record(
            target,
            batch_id=supplemental_batch_id,
            candidate_id=supplemental_candidate,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                "provider": "courtlistener-recap-rest-v4",
                "supplemental": True,
                "canonical_rest_screen_complete": True,
                "selected_entries": [{"row_id": "entry-14", "role": "mtd_notice"}],
                "ai": {
                    "target_motion_entry_numbers": ["14"],
                    "decision_entry_numbers": ["19"],
                },
                "mtd_decision_screen": {
                    "actual_mtd_decision_entry_count": 1,
                    "anchor_disposition_entries": [{"row_id": "entry-19"}],
                },
                "motion_linkage": {
                    "links": [
                        {
                            "motion_entry_ids": ["entry-14"],
                            "disposition_entry_ids": ["entry-19"],
                        }
                    ]
                },
            },
        )
        supplemental_snapshot = target.export_snapshot(
            tmp_path / "target-source-snapshots",
            snapshot_id="target-supplemental-complete",
            batch_id=supplemental_batch_id,
            complete=True,
        )
        _commit_batch(target, batch_id=target_batch_id, candidate_ids=selected_ids)

    contract = RestObservationRebindContract.from_mapping(
        {
            "schema_version": (
                "legalforecast.rest_observation_policy_rebind_contract.v1"
            ),
            "source_cycle_hash": source_cycle_hash,
            "target_cycle_hash": target_cycle_hash,
            "source_batch_id": source_batch_id,
            "source_snapshot_manifest_sha256": _file_sha256(
                source_snapshot / "manifest.json"
            ),
            "selection_run_card_sha256": _file_sha256(selection_path),
            "selected_candidate_set_sha256": "3" * 64,
            "selected_candidate_count": len(selected_ids),
            "novel_candidate_count": len(outcomes),
            "novel_candidate_ids_sha256": _canonical_sha256(
                sorted((novel_excluded, novel_accepted))
            ),
            "novel_outcomes_sha256": _canonical_sha256(list(outcomes)),
            "source_policy": source_policy,
            "target_policy": target_policy,
            "allowed_policy_delta": {
                "source_key": "courtlistener_acquisition",
                "old_sha256": old_sha,
                "new_sha256": new_sha,
            },
            "semantic_noop_proof": {
                "commit": "6ffbbdbc915a8a8bda7a40b474e656fd6425e6cf",
                "screening_source_path": (
                    "legalforecast/ingestion/courtlistener_acquisition.py"
                ),
                "old_to_current_diff_shape": (
                    "candidate_text_override_optional_default_none"
                ),
                "rest_observation_mode": "candidate_text_override_none",
                "excluded_evidence_markers": [
                    "source_bound_bankruptcy_adversary",
                    "bankruptcy_adversary",
                ],
            },
            "novel_outcomes": list(outcomes),
        }
    )

    return {
        "contract": contract,
        "source_store": source_store_path,
        "source_snapshot": source_snapshot,
        "selection": selection_path,
        "target_store": target_store_path,
        "target_batch_id": target_batch_id,
        "novel_ids": {novel_excluded, novel_accepted},
        "prior_snapshot": prior_snapshot,
        "supplemental_snapshot": supplemental_snapshot,
    }


def test_rebind_terminal_rest_observations_emits_current_snapshot_and_card(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_store_stat = fixture["source_store"].stat()
    source_store_sha256 = _file_sha256(fixture["source_store"])
    result = rebind_terminal_rest_observations(
        source_store_path=fixture["source_store"],
        source_snapshot_path=fixture["source_snapshot"],
        selection_run_card_path=fixture["selection"],
        target_store_path=fixture["target_store"],
        target_batch_id=fixture["target_batch_id"],
        snapshot_output_root=tmp_path / "current-snapshots",
        snapshot_id="current-complete",
        run_card_path=tmp_path / "run-card.json",
        contract=fixture["contract"],
        verify_git_semantics=False,
    )

    assert result.rebound_count == 2
    assert result.provider_activity_executed is False
    assert result.paid_activity_executed is False
    manifest = verify_snapshot(
        result.snapshot_path,
        expected_cycle_hash=fixture["contract"].target_cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    assert manifest["stage_commitments"]["novel_candidate_count"] == 2
    run_card = json.loads(result.run_card_path.read_text())
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False
    assert set(run_card["novel_candidate_ids"]) == fixture["novel_ids"]
    union = load_screening_snapshot_union(
        (
            fixture["prior_snapshot"],
            fixture["supplemental_snapshot"],
            result.snapshot_path,
        ),
        expected_manifest_sha256=(
            _file_sha256(fixture["prior_snapshot"] / "manifest.json"),
            _file_sha256(fixture["supplemental_snapshot"] / "manifest.json"),
            result.snapshot_manifest_sha256,
        ),
        expected_cycle_hash=fixture["contract"].target_cycle_hash,
    )
    assert union.stage_commitment["source_count"] == 3
    assert len(union.candidates) == 4
    with CycleAcquisitionStore(fixture["target_store"]) as target:
        for candidate_id in fixture["novel_ids"]:
            assert target.current_observation(candidate_id) is not None

    resumed = rebind_terminal_rest_observations(
        source_store_path=fixture["source_store"],
        source_snapshot_path=fixture["source_snapshot"],
        selection_run_card_path=fixture["selection"],
        target_store_path=fixture["target_store"],
        target_batch_id=fixture["target_batch_id"],
        snapshot_output_root=tmp_path / "current-snapshots",
        snapshot_id="current-complete",
        run_card_path=tmp_path / "resumed-run-card.json",
        contract=fixture["contract"],
        verify_git_semantics=False,
    )
    assert resumed.snapshot_manifest_sha256 == result.snapshot_manifest_sha256
    with CycleAcquisitionStore(fixture["target_store"]) as target:
        assert all(
            len(target.observations(candidate_id)) == 1
            for candidate_id in fixture["novel_ids"]
        )
    assert fixture["source_store"].stat().st_mtime_ns == source_store_stat.st_mtime_ns
    assert _file_sha256(fixture["source_store"]) == source_store_sha256


def test_rebind_refuses_any_additional_policy_drift(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    target_policy = dict(fixture["contract"].target_policy)
    sources = dict(target_policy["screening_source_sha256"])
    sources["motion_linkage"] = "9" * 64
    target_policy["screening_source_sha256"] = sources
    fixture["contract"] = fixture["contract"].replace(target_policy=target_policy)

    with pytest.raises(RestObservationPolicyRebindError, match="exactly one"):
        rebind_terminal_rest_observations(
            source_store_path=fixture["source_store"],
            source_snapshot_path=fixture["source_snapshot"],
            selection_run_card_path=fixture["selection"],
            target_store_path=fixture["target_store"],
            target_batch_id=fixture["target_batch_id"],
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run-card.json",
            contract=fixture["contract"],
            verify_git_semantics=False,
        )


def test_rebind_refuses_tampered_source_snapshot(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with (fixture["source_snapshot"] / "observations.jsonl").open("a") as handle:
        handle.write("{}\n")

    with pytest.raises(RestObservationPolicyRebindError, match="snapshot"):
        rebind_terminal_rest_observations(
            source_store_path=fixture["source_store"],
            source_snapshot_path=fixture["source_snapshot"],
            selection_run_card_path=fixture["selection"],
            target_store_path=fixture["target_store"],
            target_batch_id=fixture["target_batch_id"],
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run-card.json",
            contract=fixture["contract"],
            verify_git_semantics=False,
        )


def test_rebind_refuses_unpinned_source_outcome(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outcomes = list(fixture["contract"].novel_outcomes)
    outcomes[0] = {**outcomes[0], "source_observation_sha256": "f" * 64}
    fixture["contract"] = fixture["contract"].replace(novel_outcomes=tuple(outcomes))

    with pytest.raises(RestObservationPolicyRebindError, match="outcome"):
        rebind_terminal_rest_observations(
            source_store_path=fixture["source_store"],
            source_snapshot_path=fixture["source_snapshot"],
            selection_run_card_path=fixture["selection"],
            target_store_path=fixture["target_store"],
            target_batch_id=fixture["target_batch_id"],
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run-card.json",
            contract=fixture["contract"],
            verify_git_semantics=False,
        )


def test_rebind_refuses_target_with_unexpected_unresolved_candidate(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    target_store_path = tmp_path / "wrong-target.sqlite3"
    with CycleAcquisitionStore(target_store_path) as target:
        target.ensure_cycle(dict(fixture["contract"].target_policy))
        _commit_batch(
            target,
            batch_id=fixture["target_batch_id"],
            candidate_ids=(
                "courtlistener-docket-100",
                "courtlistener-docket-200",
                "courtlistener-docket-300",
            ),
        )

    with pytest.raises(RestObservationPolicyRebindError, match="unresolved"):
        rebind_terminal_rest_observations(
            source_store_path=fixture["source_store"],
            source_snapshot_path=fixture["source_snapshot"],
            selection_run_card_path=fixture["selection"],
            target_store_path=target_store_path,
            target_batch_id=fixture["target_batch_id"],
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run-card.json",
            contract=fixture["contract"],
            verify_git_semantics=False,
        )


def test_rebind_refuses_non_default_override_evidence(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    snapshot = fixture["source_snapshot"]
    observations = _read_jsonl(snapshot / "observations.jsonl")
    for row in observations:
        if row["candidate_id"] in fixture["novel_ids"]:
            row["evidence"]["source_bound_bankruptcy_adversary"] = {"matched": True}
            row["source_observation_sha256"] = _canonical_sha256(row)
            break
    # The manifest tamper gate is intentionally stronger than the semantic gate.
    (snapshot / "observations.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in observations)
    )
    with pytest.raises(RestObservationPolicyRebindError, match="snapshot"):
        rebind_terminal_rest_observations(
            source_store_path=fixture["source_store"],
            source_snapshot_path=snapshot,
            selection_run_card_path=fixture["selection"],
            target_store_path=fixture["target_store"],
            target_batch_id=fixture["target_batch_id"],
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run-card.json",
            contract=fixture["contract"],
            verify_git_semantics=False,
        )


def test_official_contract_pins_exact_100_outcomes() -> None:
    contract = load_official_rest_observation_rebind_contract()

    assert contract.novel_candidate_count == 100
    assert len(contract.novel_outcomes) == 100
    assert sum(row["state"] == "accepted" for row in contract.novel_outcomes) == 1
    assert sum(row["state"] == "excluded" for row in contract.novel_outcomes) == 99
    assert {
        row["candidate_id"]
        for row in contract.novel_outcomes
        if row["state"] == "accepted"
    } == {"courtlistener-docket-71843630"}
    assert (
        contract.source_snapshot_manifest_sha256
        == "8272689426926946fa3e32102e8f0caa2e8188d84e7889e129011fd86206b492"
    )
    assert (
        contract.selected_candidate_set_sha256
        == "f2d20b979710e7e78027dea6a85c09359399fb116d970a4f21a882fc1887bedb"
    )
    proof = verify_official_rest_observation_rebind_semantics()
    assert proof["commit"] == "6ffbbdbc915a8a8bda7a40b474e656fd6425e6cf"
    assert proof["rest_observation_mode"] == "candidate_text_override_none"


def test_terminal_rest_rebind_help_is_explicitly_provider_free(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch-002", "rebind-terminal-rest-observations", "--help"])

    assert exc_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "exact 100 novel terminal outcomes" in help_text
    assert "candidate_text_override=None" in help_text
    assert "no network, provider, PACER, RECAP Fetch" in help_text
    assert "fee acknowledgment" in help_text

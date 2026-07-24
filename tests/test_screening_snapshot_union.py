from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli_module
import legalforecast.ingestion.screening_snapshot_union as union_module
import pytest
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    firecrawl_screening_implementation,
    snapshot_firecrawl_screening_source_count,
    source_manifest_sha256,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)
from legalforecast.ingestion.screening_union_policy_rebind import (
    SOURCE_RESTRICTED_MATERIAL_SHA256,
    ScreeningUnionPolicyRebindError,
    rebind_screening_union_policy,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)


def test_complete_priority_tranche_chain_clears_only_at_zero_deferred() -> None:
    candidate_ids = frozenset({"courtlistener-docket-1", "courtlistener-docket-2"})
    candidate_hash = hashlib.sha256(
        json.dumps(
            sorted(candidate_ids), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    common: dict[str, object] = {
        "schema_version": "legalforecast.direct_search_priority_tranche.v1",
        "source_batch_id": "novel-source",
        "source_batch_digest": "a" * 64,
        "source_cycle_hash": "b" * 64,
        "source_candidate_count": 2,
        "source_candidate_set_sha256": "c" * 64,
        "source_candidate_id_set_sha256": candidate_hash,
        "source_lineage_commitment_sha256": "d" * 64,
        "ranking_policy_sha256": "e" * 64,
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
        "requested_tranche_size": 1,
    }
    first = {
        **common,
        "tranche_ordinal": 1,
        "predecessor_frontier_sha256": None,
        "deferred_frontier_sha256": "1" * 64,
        "selected_candidate_count": 1,
        "cumulative_selected_count": 1,
        "deferred_candidate_count": 1,
        "chain_terminal": False,
        "ranking_frontier_exhausted": False,
        "global_source_saturated": False,
    }
    second = {
        **common,
        "tranche_ordinal": 2,
        "predecessor_frontier_sha256": "1" * 64,
        "deferred_frontier_sha256": "2" * 64,
        "selected_candidate_count": 1,
        "cumulative_selected_count": 2,
        "deferred_candidate_count": 0,
        "chain_terminal": True,
        "ranking_frontier_exhausted": True,
        "global_source_saturated": False,
    }

    result = union_module._priority_tranche_chain_commitment(
        (
            (first, frozenset({"courtlistener-docket-1"})),
            (second, frozenset({"courtlistener-docket-2"})),
        ),
        union_candidate_ids=candidate_ids,
    )

    assert result is not None
    assert result["full_source_terminal"] is True
    assert result["accepted_plus_excluded_count"] == 2

    with pytest.raises(
        ScreeningSnapshotUnionError, match="cumulative/deferred reconciliation"
    ):
        union_module._priority_tranche_chain_commitment(
            ((first, frozenset({"courtlistener-docket-1"})),),
            union_candidate_ids=frozenset({"courtlistener-docket-1"}),
        )


_CYCLE_POLICY = {"eligibility_anchor": "2026-06-30", "fixture": True}


def test_union_help_documents_raw_observation_policy(capsys: Any) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["acquisition", "union-screening-snapshots", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "candidate/source-manifest correction pin" in output
    assert "never infer authority from order or time" in output
    assert "unique active proof" in output
    assert "source-local raw bytes" in output
    assert "earliest UTC capture is the packet input" in output


def test_rebind_union_help_is_explicitly_provider_and_purchase_free(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["acquisition", "rebind-screening-union-policy", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "Any other policy drift fails closed" in output
    assert "This command has no provider" in output
    assert "PACER, fee acknowledgment" in output


def test_exact_union_policy_rebind_preserves_every_terminal_and_raw_record(
    tmp_path: Path,
) -> None:
    source_policy, target_policy = _policy_rebind_fixture_policies()
    accepted_id = "courtlistener-docket-73330394"
    excluded_id = "courtlistener-docket-73330395"
    accepted_evidence = _strict_screen_evidence(accepted_id)
    accepted_evidence["policy_rebind"] = {
        "strategy": "authenticated_strict_evidence_reproof_v1",
        "current_policy_proof_available": True,
        "raw_artifact_count": 0,
        "source_cycle_hash": "a" * 64,
        "source_batch_id": "exact310-source",
        "source_snapshot_manifest_sha256": "b" * 64,
        "source_observation_sha256": "c" * 64,
        "source_state": "accepted",
        "source_reason_code": "strict_clean_screen_passed",
        "target_cycle_hash": "d" * 64,
    }
    first_root = tmp_path / "first"
    first = _snapshot(
        first_root,
        batch_id="accepted",
        observations=[
            (
                accepted_id,
                "accepted",
                "strict_clean_screen_passed",
                accepted_evidence,
                b"<html><body>accepted raw docket</body></html>",
            )
        ],
        cycle_policy=source_policy,
    )
    _set_firecrawl_screening_implementation(first)
    second = _snapshot(
        tmp_path / "second",
        batch_id="excluded",
        observations=[
            (
                excluded_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": excluded_id,
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>excluded raw docket</body></html>",
            )
        ],
        cycle_policy=source_policy,
    )
    union_output = tmp_path / "union-output"
    union_snapshot_root = tmp_path / "union-snapshots"
    source_cycle_hash = _cycle_hash(first_root)
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(union_output),
                "--cycle-store",
                str(first_root / "cycle.sqlite3"),
                "--batch-id",
                "source-union",
                "--expected-cycle-hash",
                source_cycle_hash,
                "--source-snapshot",
                str(first),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(first),
                "--source-snapshot",
                str(second),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(second),
                "--snapshot-root",
                str(union_snapshot_root),
                "--snapshot-id",
                "source-union-complete",
                "--execute",
            ]
        )
        == 0
    )
    source_union = union_snapshot_root / "source-union-complete"
    source_union_manifest_path = source_union / "manifest.json"
    source_union_manifest = json.loads(source_union_manifest_path.read_text())
    source_implementation = source_union_manifest["stage_commitments"][
        "firecrawl_screening_implementation"
    ]
    source_sha256 = source_implementation["source_sha256"]
    source_sha256["legalforecast/ingestion/courtlistener_dates.py"] = (
        "c414deb237d62fe6fbdd43863cdd4acf0387a5de54ecb21f0cd7c0ec88417f3d"
    )
    source_implementation["manifest_sha256"] = source_manifest_sha256(source_sha256)
    source_union_manifest_path.write_text(
        json.dumps(source_union_manifest, sort_keys=True, separators=(",", ":"))
    )
    source_union_card = union_output / "run-cards" / "union-screening-snapshots.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(target_policy)

    result = rebind_screening_union_policy(
        source_snapshot_path=source_union,
        expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
        source_union_run_card_path=source_union_card,
        expected_source_union_run_card_sha256=hashlib.sha256(
            source_union_card.read_bytes()
        ).hexdigest(),
        source_cycle_store_path=first_root / "cycle.sqlite3",
        expected_source_cycle_hash=source_cycle_hash,
        target_cycle_store_path=target_store,
        expected_target_cycle_hash=target_cycle_hash,
        target_batch_id="current-policy-union",
        snapshot_output_root=tmp_path / "target-snapshots",
        snapshot_id="current-policy-union-complete",
        raw_artifact_output_root=tmp_path / "rebound-raw",
        run_card_path=tmp_path / "rebind-run-card.json",
    )

    assert result.candidate_count == 2
    assert result.accepted_count == 1
    assert result.excluded_count == 1
    assert result.raw_artifact_count == 2
    assert result.provider_activity_executed is False
    assert result.paid_activity_executed is False
    manifest = verify_snapshot(
        result.snapshot_path,
        expected_cycle_hash=target_cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    commitment = manifest["stage_commitments"]["screening_union_policy_rebind"]
    assert commitment["source_candidate_count"] == 2
    assert commitment["provider_activity_requested"] is False
    assert commitment["paid_activity_requested"] is False
    assert (
        manifest["stage_commitments"]["screening_snapshot_union_inputs"]
        == (
            json.loads((source_union / "manifest.json").read_text())[
                "stage_commitments"
            ]["screening_snapshot_union_inputs"]
        )
    )
    assert (
        manifest["stage_commitments"]["firecrawl_screening_implementation"]
        == firecrawl_screening_implementation()
    )
    assert (
        snapshot_firecrawl_screening_source_count(manifest, require_current=True) == 1
    )
    run_card = json.loads(result.run_card_path.read_text())
    assert run_card["reconciled"] is True
    with CycleAcquisitionStore(target_store, read_only=True) as store:
        accepted = store.current_observation(accepted_id)
        excluded = store.current_observation(excluded_id)
    assert accepted is not None and accepted.state == "accepted"
    assert excluded is not None and excluded.state == "excluded"
    source_rows = {
        row["candidate_id"]: row for row in _jsonl(source_union / "candidates.jsonl")
    }
    assert accepted.observed_at == source_rows[accepted_id]["observed_at"]
    assert excluded.observed_at == source_rows[excluded_id]["observed_at"]
    assert accepted.evidence["policy_rebind"] == accepted_evidence["policy_rebind"]
    assert accepted.evidence["screening_union_policy_rebind"]["source_terminal_sha256"]

    resumed = rebind_screening_union_policy(
        source_snapshot_path=source_union,
        expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
        source_union_run_card_path=source_union_card,
        expected_source_union_run_card_sha256=hashlib.sha256(
            source_union_card.read_bytes()
        ).hexdigest(),
        source_cycle_store_path=first_root / "cycle.sqlite3",
        expected_source_cycle_hash=source_cycle_hash,
        target_cycle_store_path=target_store,
        expected_target_cycle_hash=target_cycle_hash,
        target_batch_id="current-policy-union",
        snapshot_output_root=tmp_path / "target-snapshots",
        snapshot_id="current-policy-union-complete",
        raw_artifact_output_root=tmp_path / "rebound-raw",
        run_card_path=tmp_path / "rebind-run-card.json",
    )
    assert resumed.snapshot_manifest_sha256 == result.snapshot_manifest_sha256
    assert resumed.run_card_sha256 == result.run_card_sha256
    with CycleAcquisitionStore(target_store, read_only=True) as store:
        assert len(store.observations(accepted_id)) == 1
        assert len(store.observations(excluded_id)) == 1
    with sqlite3.connect(target_store) as connection:
        connection.execute(
            """
            UPDATE candidate_observations
            SET observed_at = ?
            WHERE candidate_id = ?
            """,
            ("2026-07-31T00:00:00Z", accepted_id),
        )
    with pytest.raises(
        ScreeningUnionPolicyRebindError,
        match="conflicting replay evidence",
    ):
        rebind_screening_union_policy(
            source_snapshot_path=source_union,
            expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
            source_union_run_card_path=source_union_card,
            expected_source_union_run_card_sha256=hashlib.sha256(
                source_union_card.read_bytes()
            ).hexdigest(),
            source_cycle_store_path=first_root / "cycle.sqlite3",
            expected_source_cycle_hash=source_cycle_hash,
            target_cycle_store_path=target_store,
            expected_target_cycle_hash=target_cycle_hash,
            target_batch_id="current-policy-union",
            snapshot_output_root=tmp_path / "target-snapshots",
            snapshot_id="current-policy-union-complete",
            raw_artifact_output_root=tmp_path / "rebound-raw",
            run_card_path=tmp_path / "rebind-run-card.json",
        )

    novel_id = "courtlistener-docket-73330396"
    novel_snapshot = _snapshot(
        tmp_path / "novel-current-cycle",
        batch_id="novel-current-policy",
        observations=[
            (
                novel_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": novel_id,
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>novel current-cycle raw docket</body></html>",
            )
        ],
        cycle_policy=target_policy,
    )
    combined = load_screening_snapshot_union(
        [result.snapshot_path, novel_snapshot],
        expected_manifest_sha256=[
            result.snapshot_manifest_sha256,
            _manifest_sha256(novel_snapshot),
        ],
        expected_cycle_hash=target_cycle_hash,
    )
    assert {candidate.candidate_id for candidate in combined.candidates} == {
        accepted_id,
        excluded_id,
        novel_id,
    }
    assert combined.stage_commitment["firecrawl_screening_source_count"] == 1

    tampered_snapshot = tmp_path / "tampered-rebind-snapshot"
    shutil.copytree(result.snapshot_path, tampered_snapshot)
    tampered_manifest_path = tampered_snapshot / "manifest.json"
    tampered_manifest = json.loads(tampered_manifest_path.read_text())
    implementation = tampered_manifest["stage_commitments"][
        "screening_union_policy_rebind"
    ]["implementation"]
    implementation["source_sha256"][
        "legalforecast/ingestion/screening_union_policy_rebind.py"
    ] = "0" * 64
    tampered_manifest_path.write_text(
        json.dumps(tampered_manifest, sort_keys=True, separators=(",", ":"))
    )
    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="policy-rebind source manifest commitment mismatch",
    ):
        load_screening_snapshot_union(
            [tampered_snapshot, novel_snapshot],
            expected_manifest_sha256=[
                _manifest_sha256(tampered_snapshot),
                _manifest_sha256(novel_snapshot),
            ],
            expected_cycle_hash=target_cycle_hash,
        )

    overlap_target = tmp_path / "overlap-target.sqlite3"
    with CycleAcquisitionStore(overlap_target) as store:
        assert store.ensure_cycle(target_policy) == target_cycle_hash
    overlap_target_sha256 = hashlib.sha256(overlap_target.read_bytes()).hexdigest()
    with pytest.raises(
        ScreeningUnionPolicyRebindError,
        match="owned output overlaps a source or cycle store",
    ):
        rebind_screening_union_policy(
            source_snapshot_path=source_union,
            expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
            source_union_run_card_path=source_union_card,
            expected_source_union_run_card_sha256=hashlib.sha256(
                source_union_card.read_bytes()
            ).hexdigest(),
            source_cycle_store_path=first_root / "cycle.sqlite3",
            expected_source_cycle_hash=source_cycle_hash,
            target_cycle_store_path=overlap_target,
            expected_target_cycle_hash=target_cycle_hash,
            target_batch_id="overlap-refused",
            snapshot_output_root=tmp_path / "overlap-snapshots",
            snapshot_id="overlap-refused",
            raw_artifact_output_root=source_union / "forbidden-owned-raw",
            run_card_path=tmp_path / "overlap-run-card.json",
        )
    assert hashlib.sha256(overlap_target.read_bytes()).hexdigest() == (
        overlap_target_sha256
    )
    assert not (source_union / "forbidden-owned-raw").exists()

    symlink_target = tmp_path / "symlink-target.sqlite3"
    with CycleAcquisitionStore(symlink_target) as store:
        assert store.ensure_cycle(target_policy) == target_cycle_hash
    symlink_target_sha256 = hashlib.sha256(symlink_target.read_bytes()).hexdigest()
    actual_raw_root = tmp_path / "actual-symlink-raw"
    actual_raw_root.mkdir()
    symlink_raw_root = tmp_path / "symlink-raw"
    symlink_raw_root.symlink_to(actual_raw_root, target_is_directory=True)
    with pytest.raises(
        ScreeningUnionPolicyRebindError,
        match="must not traverse symlinks",
    ):
        rebind_screening_union_policy(
            source_snapshot_path=source_union,
            expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
            source_union_run_card_path=source_union_card,
            expected_source_union_run_card_sha256=hashlib.sha256(
                source_union_card.read_bytes()
            ).hexdigest(),
            source_cycle_store_path=first_root / "cycle.sqlite3",
            expected_source_cycle_hash=source_cycle_hash,
            target_cycle_store_path=symlink_target,
            expected_target_cycle_hash=target_cycle_hash,
            target_batch_id="symlink-refused",
            snapshot_output_root=tmp_path / "symlink-snapshots",
            snapshot_id="symlink-refused",
            raw_artifact_output_root=symlink_raw_root,
            run_card_path=tmp_path / "symlink-run-card.json",
        )
    assert hashlib.sha256(symlink_target.read_bytes()).hexdigest() == (
        symlink_target_sha256
    )
    assert not any(actual_raw_root.iterdir())


def test_exact_union_policy_rebind_rejects_unrelated_policy_drift(
    tmp_path: Path,
) -> None:
    source_policy, target_policy = _policy_rebind_fixture_policies()
    target_hashes = dict(cast(dict[str, str], target_policy["screening_source_sha256"]))
    target_hashes["motion_linkage"] = "9" * 64
    target_policy["screening_source_sha256"] = target_hashes
    source_root = tmp_path / "source"
    first = _snapshot(
        source_root,
        batch_id="first",
        observations=[],
        cycle_policy=source_policy,
    )
    _set_firecrawl_screening_implementation(first)
    second = _snapshot(
        tmp_path / "second",
        batch_id="second",
        observations=[],
        cycle_policy=source_policy,
    )
    union_output = tmp_path / "union-output"
    union_snapshot_root = tmp_path / "union-snapshots"
    source_cycle_hash = _cycle_hash(source_root)
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(union_output),
                "--cycle-store",
                str(source_root / "cycle.sqlite3"),
                "--batch-id",
                "source-union",
                "--expected-cycle-hash",
                source_cycle_hash,
                "--source-snapshot",
                str(first),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(first),
                "--source-snapshot",
                str(second),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(second),
                "--snapshot-root",
                str(union_snapshot_root),
                "--snapshot-id",
                "source-union-complete",
                "--execute",
            ]
        )
        == 0
    )
    source_union = union_snapshot_root / "source-union-complete"
    source_union_card = union_output / "run-cards" / "union-screening-snapshots.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(target_policy)

    with pytest.raises(
        ScreeningUnionPolicyRebindError,
        match="differs outside the one audited",
    ):
        rebind_screening_union_policy(
            source_snapshot_path=source_union,
            expected_source_snapshot_manifest_sha256=_manifest_sha256(source_union),
            source_union_run_card_path=source_union_card,
            expected_source_union_run_card_sha256=hashlib.sha256(
                source_union_card.read_bytes()
            ).hexdigest(),
            source_cycle_store_path=source_root / "cycle.sqlite3",
            expected_source_cycle_hash=source_cycle_hash,
            target_cycle_store_path=target_store,
            expected_target_cycle_hash=target_cycle_hash,
            target_batch_id="refused-current-policy-union",
            snapshot_output_root=tmp_path / "target-snapshots",
            snapshot_id="refused",
            raw_artifact_output_root=tmp_path / "rebound-raw",
            run_card_path=tmp_path / "rebind-run-card.json",
        )
    assert not (tmp_path / "rebound-raw").exists()


def test_strict_evidence_accepts_exact_unnumbered_text_only_placeholder() -> None:
    candidate_id = "courtlistener-docket-73330394"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-1",
            "entry_number": None,
            "filed_at": "2026-06-30",
            "text": "Set/Reset Deadlines: response due July 7.",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "",
                    "description": "",
                    "href": None,
                    "action_label": None,
                    "pacer_only": False,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id=candidate_id,
    )


def test_strict_evidence_allows_unselected_unnumbered_text_decision() -> None:
    candidate_id = "courtlistener-docket-73330394"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-2",
            "entry_number": None,
            "filed_at": "2026-07-01",
            "text": "Text Order terminating the motion to dismiss.",
            "role": "decision",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "",
                    "description": "",
                    "href": None,
                    "action_label": None,
                    "pacer_only": False,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )
    evidence["mtd_decision_screen"]["decision_entries"].append(
        {
            "row_id": "minute-entry-2",
            "entry_number": None,
            "filed_at": "2026-07-01",
            "actual_mtd_decision": True,
            "exclusion_reasons": [],
        }
    )
    evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = 2
    evidence["motion_linkage"]["links"][0]["disposition_entry_ids"].append(
        "minute-entry-2"
    )

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id=candidate_id,
    )


def test_strict_evidence_rejects_unnumbered_decision_without_selected_row_id() -> None:
    candidate_id = "courtlistener-docket-73330394"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["mtd_decision_screen"]["decision_entries"].append(
        {
            "entry_number": None,
            "filed_at": "2026-07-01",
            "actual_mtd_decision": True,
            "exclusion_reasons": [],
        }
    )
    evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = 2

    with pytest.raises(
        StrictScreenEvidenceError,
        match="unnumbered MTD decision screen entry lacks its selected row ID",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("href", "https://storage.courtlistener.com/hidden.pdf"),
        ("action_label", "Download PDF"),
        ("freely_available", True),
        ("restriction_markers", ["text_documentissealed"]),
    ),
)
def test_strict_evidence_rejects_blank_kind_download_or_restriction_shape(
    field: str,
    value: object,
) -> None:
    candidate_id = "courtlistener-docket-73330394"
    evidence = _strict_screen_evidence(candidate_id)
    placeholder: dict[str, object] = {
        "kind": "",
        "description": "",
        "href": None,
        "action_label": None,
        "pacer_only": False,
        "freely_available": False,
        "restriction_markers": [],
    }
    placeholder[field] = value
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-1",
            "entry_number": None,
            "filed_at": "2026-06-30",
            "text": "Set/Reset Deadlines: response due July 7.",
            "role": "other",
            "restriction_markers": [],
            "documents": [placeholder],
        }
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"\.kind must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_regular_file_reader_sets_close_on_exec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "payload.json"
    path.write_bytes(b"{}")
    original_open = os.open
    observed_flags: list[int] = []

    def recording_open(open_path: Path, flags: int) -> int:
        observed_flags.append(flags)
        return original_open(open_path, flags)

    monkeypatch.setattr(union_module.os, "open", recording_open)

    assert union_module._read_regular_file(path, "fixture") == b"{}"
    assert observed_flags
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    if close_on_exec:
        assert observed_flags[0] & close_on_exec


def test_union_rejects_source_without_stage_commitments(tmp_path: Path) -> None:
    first = _snapshot(
        tmp_path / "first",
        batch_id="first",
        observations=[],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="second",
        observations=[],
    )
    manifest_path = first / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("stage_commitments")
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="lacks affirmative stage commitments",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_preserves_updated_raw_observations_for_identical_terminal_evidence(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {
        "candidate_id": candidate_id,
        "reason": "no_mtd_or_rule_12_reference",
        "primary_exclusion_reason": "no_mtd_or_rule_12_reference",
    }
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(_manifest_sha256(first), _manifest_sha256(second)),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert [candidate.candidate_id for candidate in union.candidates] == [candidate_id]
    assert len(union.raw_artifacts) == 2
    assert {artifact.content for artifact in union.raw_artifacts} == {
        b"<html><body>earlier docket observation</body></html>",
        b"<html><body>later docket observation</body></html>",
    }
    assert [artifact.sha256 for artifact in union.raw_artifacts] == sorted(
        artifact.sha256 for artifact in union.raw_artifacts
    )
    [canonical] = union.canonical_raw_artifacts
    assert canonical.content == b"<html><body>earlier docket observation</body></html>"

    reversed_union = load_screening_snapshot_union(
        (second, first),
        expected_manifest_sha256=(_manifest_sha256(second), _manifest_sha256(first)),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )
    assert reversed_union.canonical_raw_artifacts[0].sha256 == canonical.sha256


def test_union_archives_excluded_versions_but_projects_earliest_for_packets(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {
        "candidate_id": candidate_id,
        "reason": "no_mtd_or_rule_12_reference",
    }
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = _snapshot(
        first_root,
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    _set_firecrawl_screening_implementation(first)
    second = _snapshot(
        second_root,
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )
    cycle_hash = _cycle_hash(first_root)
    output_root = tmp_path / "union-output"
    snapshot_root = tmp_path / "union-snapshots"
    command = [
        "acquisition",
        "union-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(first_root / "cycle.sqlite3"),
        "--batch-id",
        "raw-observation-union",
        "--expected-cycle-hash",
        cycle_hash,
        "--source-snapshot",
        str(first),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(first),
        "--source-snapshot",
        str(second),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(second),
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "complete-union",
        "--execute",
    ]

    assert cli_module.main(command) == 0
    union_snapshot = snapshot_root / "complete-union"
    assert len(_jsonl(union_snapshot / "raw-artifacts.jsonl")) == 2
    canonical_records = _jsonl(output_root / "union-raw-artifacts.jsonl")
    observation_records = _jsonl(output_root / "union-raw-observations.jsonl")
    assert len(canonical_records) == 1
    assert len(observation_records) == 2
    assert canonical_records[0]["retrieved_at"] == "2026-07-16T12:00:00Z"
    assert (
        canonical_records[0]["sha256"]
        == hashlib.sha256(
            b"<html><body>earlier docket observation</body></html>"
        ).hexdigest()
    )

    (output_root / "union-raw-artifacts.jsonl").unlink()
    (output_root / "union-raw-observations.jsonl").write_text("")
    assert cli_module.main(command) == 0
    assert _jsonl(output_root / "union-raw-artifacts.jsonl") == canonical_records
    assert _jsonl(output_root / "union-raw-observations.jsonl") == observation_records

    shutil.rmtree(first_root / "snapshots")
    shutil.rmtree(second_root)
    verify_snapshot(
        union_snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    cli_module._verify_packet_raw_artifacts_snapshot_binding(
        raw_html_dir=output_root / "union-raw-artifacts",
        raw_artifacts_manifest_path=output_root / "union-raw-artifacts.jsonl",
        screening_snapshot_manifest_path=union_snapshot / "manifest.json",
    )

    manifest_path = union_snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["stage_commitments"]["firecrawl_screening_implementation"] == (
        firecrawl_screening_implementation()
    )
    assert (
        manifest["stage_commitments"]["screening_snapshot_union_inputs"][
            "firecrawl_screening_source_count"
        ]
        == 1
    )
    assert (
        json.loads((output_root / "screening-snapshot-union-summary.json").read_text())[
            "firecrawl_screening_source_count"
        ]
        == 1
    )
    mapping = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "canonical_raw_artifacts"
    ]
    mapping[0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="does not select the earliest authenticated observation",
    ):
        cli_module._owned_raw_records_from_snapshot(union_snapshot)


def test_union_of_union_uses_nested_terminal_raw_authority(tmp_path: Path) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / "stale",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>stale excluded proof</body></html>",
            )
        ],
    )
    corrected_evidence = _strict_screen_evidence(candidate_id)
    corrected = _snapshot(
        tmp_path / "corrected",
        batch_id="corrected-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>corrected active proof</body></html>",
            )
        ],
    )
    _set_firecrawl_screening_implementation(corrected)
    cycle_hash = _cycle_hash(tmp_path / "stale")
    nested_output = tmp_path / "nested-output"
    nested_snapshot_root = tmp_path / "nested-snapshots"
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(nested_output),
                "--cycle-store",
                str(tmp_path / "stale" / "cycle.sqlite3"),
                "--batch-id",
                "nested-corrected-union",
                "--expected-cycle-hash",
                cycle_hash,
                "--source-snapshot",
                str(stale),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(stale),
                "--source-snapshot",
                str(corrected),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(corrected),
                "--expected-terminal-correction-candidate-id",
                candidate_id,
                "--expected-terminal-correction-source-manifest-sha256",
                _manifest_sha256(corrected),
                "--snapshot-root",
                str(nested_snapshot_root),
                "--snapshot-id",
                "nested-complete",
                "--execute",
            ]
        )
        == 0
    )
    nested = nested_snapshot_root / "nested-complete"
    disjoint = _snapshot(
        tmp_path / "disjoint",
        batch_id="disjoint-screen",
        observations=[
            (
                "courtlistener-docket-79999999",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-79999999",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>disjoint excluded proof</body></html>",
            )
        ],
    )

    outer = load_screening_snapshot_union(
        (nested, disjoint),
        expected_manifest_sha256=(
            _manifest_sha256(nested),
            _manifest_sha256(disjoint),
        ),
        expected_cycle_hash=cycle_hash,
    )

    assert len(outer.raw_artifacts) == 3
    active_raw = next(
        artifact
        for artifact in outer.canonical_raw_artifacts
        if artifact.candidate_id == candidate_id
    )
    assert active_raw.content == b"<html><body>corrected active proof</body></html>"
    outer_output = tmp_path / "outer-output"
    outer_snapshot_root = tmp_path / "outer-snapshots"
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(outer_output),
                "--cycle-store",
                str(tmp_path / "stale" / "cycle.sqlite3"),
                "--batch-id",
                "outer-nested-union",
                "--expected-cycle-hash",
                cycle_hash,
                "--source-snapshot",
                str(nested),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(nested),
                "--source-snapshot",
                str(disjoint),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(disjoint),
                "--snapshot-root",
                str(outer_snapshot_root),
                "--snapshot-id",
                "outer-complete",
                "--execute",
            ]
        )
        == 0
    )
    outer_snapshot = outer_snapshot_root / "outer-complete"
    owned_records = cli_module._owned_raw_records_from_snapshot(outer_snapshot)
    active_record = next(
        record for record in owned_records if record["candidate_id"] == candidate_id
    )
    assert active_record["sha256"] == active_raw.sha256
    outer_manifest_path = outer_snapshot / "manifest.json"
    outer_manifest = json.loads(outer_manifest_path.read_text())
    nested_source = next(
        source
        for source in outer_manifest["stage_commitments"][
            "screening_snapshot_union_inputs"
        ]["sources"]
        if "screening_snapshot_union_inputs" in source["stage_commitments"]
    )
    nested_authority = next(
        row
        for row in nested_source["stage_commitments"][
            "screening_snapshot_union_inputs"
        ]["canonical_raw_artifacts"]
        if row["candidate_id"] == candidate_id
    )
    nested_authority["sha256"] = "0" * 64
    outer_manifest_path.write_text(json.dumps(outer_manifest))
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="without one authenticated correction source",
    ):
        cli_module._owned_raw_records_from_snapshot(outer_snapshot)


def test_union_rejects_active_candidate_with_divergent_raw_observations(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {"candidate_id": candidate_id, "selected_entries": [16]}
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active candidate has non-identical raw-artifact commitments",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_updated_raw_observations_with_conflicting_terminal_evidence(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {"candidate_id": candidate_id, "selected_entries": [16]},
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="terminal evidence conflict requires an explicit authenticated",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_promotes_only_explicit_unique_active_correction_and_binds_its_raw(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / "stale",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "procedural_or_standing_order",
                },
                b"<html><body>stale screen over docket with entry 12</body></html>",
            )
        ],
    )
    corrected_evidence = _strict_screen_evidence(candidate_id)
    # CourtListener REST strict screens can retain the numeric docket identity
    # in metadata.case_id while the owning store candidate is provider-qualified.
    corrected_evidence["candidate"]["metadata"]["case_id"] = "73330395"
    corrected = _snapshot(
        tmp_path / "corrected",
        batch_id="current-policy-rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>corrected screen over docket with entry 12</body></html>",
            )
        ],
    )
    correction_hash = _manifest_sha256(corrected)
    kwargs = {
        "expected_terminal_correction_candidate_id": (candidate_id,),
        "expected_terminal_correction_source_manifest_sha256": (correction_hash,),
    }

    union = load_screening_snapshot_union(
        (stale, corrected),
        expected_manifest_sha256=(
            _manifest_sha256(stale),
            correction_hash,
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale"),
        **kwargs,
    )

    [candidate] = union.candidates
    assert candidate.state == "accepted"
    assert candidate.reason_code == "strict_clean_screen_passed"
    assert candidate.evidence == corrected_evidence
    assert len(union.raw_artifacts) == 2
    [canonical] = union.canonical_raw_artifacts
    assert canonical.content == (
        b"<html><body>corrected screen over docket with entry 12</body></html>"
    )
    correction = union.stage_commitment["longitudinal_corrections"][0]
    assert correction["candidate_id"] == candidate_id
    assert correction["canonical_source_manifest_sha256"] == correction_hash
    assert {row["state"] for row in correction["observations"]} == {
        "accepted",
        "excluded",
    }

    reversed_union = load_screening_snapshot_union(
        (corrected, stale),
        expected_manifest_sha256=(
            correction_hash,
            _manifest_sha256(stale),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale"),
        **kwargs,
    )
    assert reversed_union.candidates == union.candidates
    assert (
        reversed_union.canonical_raw_artifacts[0].sha256
        == union.canonical_raw_artifacts[0].sha256
    )
    assert (
        reversed_union.stage_commitment["longitudinal_corrections"]
        == union.stage_commitment["longitudinal_corrections"]
    )


@pytest.mark.parametrize(
    "malformed_field",
    (
        "disposition_date",
        "selected_entries",
        "motion_linkage",
        "decision_count",
    ),
)
def test_union_rejects_malformed_active_correction_evidence(
    tmp_path: Path,
    malformed_field: str,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / f"stale-{malformed_field}",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    corrected_evidence = _strict_screen_evidence(candidate_id)
    if malformed_field == "disposition_date":
        corrected_evidence["first_written_mtd_disposition_date"] = "not-a-date"
    elif malformed_field == "selected_entries":
        corrected_evidence["selected_entries"] = [12]
    elif malformed_field == "motion_linkage":
        corrected_evidence["motion_linkage"] = {}
    else:
        corrected_evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = (
            True
        )
    corrected = _snapshot(
        tmp_path / f"corrected-{malformed_field}",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>same docket</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks an independently qualifying strict screen",
    ):
        load_screening_snapshot_union(
            (stale, corrected),
            expected_manifest_sha256=(
                _manifest_sha256(stale),
                _manifest_sha256(corrected),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / f"stale-{malformed_field}"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(corrected),
            ),
        )


@pytest.mark.parametrize("terminal_state", ("accepted", "newly_free"))
def test_union_rejects_cross_candidate_strict_screen_substitution(
    tmp_path: Path,
    terminal_state: str,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    other_candidate_id = "courtlistener-docket-73330396"
    stale = _snapshot(
        tmp_path / f"stale-cross-candidate-{terminal_state}",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    substituted_evidence = _strict_screen_evidence(other_candidate_id)
    # The store already binds this top-level field. The union must also bind the
    # internally self-consistent embedded docket identity to the outer owner.
    substituted_evidence["candidate_id"] = candidate_id
    source_observations = [
        (
            candidate_id,
            "accepted",
            "strict_clean_screen_passed",
            substituted_evidence,
            b"<html><body>same docket</body></html>",
        )
    ]
    if terminal_state == "newly_free":
        source_observations.append(
            (
                candidate_id,
                "newly_free",
                "required_documents_newly_free",
                {"candidate_id": candidate_id, "document_id": "44"},
                b"<html><body>same docket</body></html>",
            )
        )
    substituted = _snapshot(
        tmp_path / f"cross-candidate-{terminal_state}",
        batch_id="rescreen",
        observations=source_observations,
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="strict-screen docket ID does not match its candidate",
    ):
        load_screening_snapshot_union(
            (stale, substituted),
            expected_manifest_sha256=(
                _manifest_sha256(stale),
                _manifest_sha256(substituted),
            ),
            expected_cycle_hash=_cycle_hash(
                tmp_path / f"stale-cross-candidate-{terminal_state}"
            ),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(substituted),
            ),
        )


def test_strict_screen_validator_rejects_outer_candidate_substitution() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence("courtlistener-docket-73330396")

    with pytest.raises(
        StrictScreenEvidenceError,
        match="strict-screen evidence belongs to a different candidate",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_cross_case_linkage() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["motion_linkage"]["links"][0]["case_id"] = "courtlistener-docket-73330396"

    with pytest.raises(
        StrictScreenEvidenceError,
        match="motion_linkage link case ID does not match its candidate",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


@pytest.mark.parametrize(
    "auxiliary_entry",
    (
        {
            "row_id": "entry-64",
            "entry_number": "64",
            "filed_at": "July 23, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Judgment (Clerk's Office Only)",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "minute-entry-405945218",
            "entry_number": None,
            "filed_at": "October 23, 2024",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Case Referred to Magistrate Judge",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "entry-1",
            "entry_number": "1",
            "filed_at": "October 22, 2025",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Complaint",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "minute-entry-453283793",
            "entry_number": None,
            "filed_at": "February 9, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Motion for Leave to File Sealed Document",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": ["text_sealeddocument"],
                }
            ],
        },
    ),
)
def test_strict_screen_validator_accepts_described_blank_auxiliary_rest_rows(
    auxiliary_entry: dict[str, object],
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(auxiliary_entry)

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id=candidate_id,
    )


def test_strict_screen_validator_rejects_blank_target_motion_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"][0]["text"] = ""
    evidence["selected_entries"][0]["role"] = "other"

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[1\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_blank_substantive_role_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "entry-8",
            "entry_number": "8",
            "filed_at": "February 10, 2026",
            "text": "",
            "role": "opposition",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Opposition to Motion to Dismiss",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[3\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_blank_decision_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"][1]["text"] = ""
    evidence["selected_entries"][1]["role"] = "other"

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[2\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_undescribed_blank_auxiliary_row() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-405945218",
            "entry_number": None,
            "filed_at": "October 23, 2024",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[3\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_linked_blank_auxiliary_row() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "entry-64",
            "entry_number": "64",
            "filed_at": "July 23, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Judgment (Clerk's Office Only)",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )
    evidence["motion_linkage"]["links"][0]["motion_entry_ids"].append("entry-64")

    with pytest.raises(
        StrictScreenEvidenceError,
        match="motion_linkage references a blank auxiliary row",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_union_authenticates_newly_free_correction_from_prior_strict_screen(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / "stale-newly-free",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    newly_free = _snapshot(
        tmp_path / "newly-free",
        batch_id="availability-refresh",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                _strict_screen_evidence(candidate_id),
                b"<html><body>same docket</body></html>",
            ),
            (
                candidate_id,
                "newly_free",
                "required_documents_newly_free",
                {"candidate_id": candidate_id, "document_id": "44"},
                b"<html><body>same docket</body></html>",
            ),
        ],
    )

    union = load_screening_snapshot_union(
        (stale, newly_free),
        expected_manifest_sha256=(
            _manifest_sha256(stale),
            _manifest_sha256(newly_free),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale-newly-free"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(newly_free),
        ),
    )

    [candidate] = union.candidates
    assert candidate.state == "newly_free"
    assert candidate.reason_code == "required_documents_newly_free"


def test_union_command_archives_and_resumes_authenticated_terminal_correction(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale_root = tmp_path / "stale"
    corrected_root = tmp_path / "corrected"
    selected_entries = [
        _embedded_entry(
            1,
            "COMPLAINT filed by Plaintiff.",
            "Complaint",
            "https://storage.courtlistener.com/complaint.pdf",
            role="other",
            pacer_only=False,
        ),
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
    docket_html = _raw_docket_html(selected_entries)
    stale = _snapshot(
        stale_root,
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                docket_html,
            )
        ],
    )
    corrected = _snapshot(
        corrected_root,
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                _strict_screen_evidence(
                    candidate_id,
                    selected_entries=selected_entries,
                ),
                docket_html,
            )
        ],
    )
    output_root = tmp_path / "union-output"
    snapshot_root = tmp_path / "union-snapshots"
    command = [
        "acquisition",
        "union-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(stale_root / "cycle.sqlite3"),
        "--batch-id",
        "longitudinal-union",
        "--expected-cycle-hash",
        _cycle_hash(stale_root),
        "--source-snapshot",
        str(stale),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(stale),
        "--source-snapshot",
        str(corrected),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(corrected),
        "--expected-terminal-correction-candidate-id",
        candidate_id,
        "--expected-terminal-correction-source-manifest-sha256",
        _manifest_sha256(corrected),
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "complete-union",
        "--execute",
    ]

    assert cli_module.main(command) == 0
    snapshot = snapshot_root / "complete-union"
    [screened] = _jsonl(snapshot / "screened-cases.jsonl")
    assert screened["candidate_id"] == candidate_id
    archived = _jsonl(output_root / "union-terminal-observations.jsonl")
    assert len(archived) == 2
    assert sum(row["canonical_terminal_observation"] for row in archived) == 1
    raw_bindings = [row["raw_artifacts"][0] for row in archived]
    assert {binding["retrieved_at"] for binding in raw_bindings} == {
        "2026-07-16T12:00:00Z"
    }
    assert {binding["source_retrieved_at"] for binding in raw_bindings} == {
        "2026-07-16T12:00:00Z",
        "2026-07-16T13:00:00Z",
    }
    [packet_raw] = _jsonl(output_root / "union-raw-artifacts.jsonl")
    assert packet_raw["sha256"] == hashlib.sha256(docket_html).hexdigest()
    cli_module._verify_packet_raw_artifacts_snapshot_binding(
        raw_html_dir=output_root / "union-raw-artifacts",
        raw_artifacts_manifest_path=output_root / "union-raw-artifacts.jsonl",
        screening_snapshot_manifest_path=snapshot / "manifest.json",
    )
    raw_directory, raw_paths = cli_module._verified_snapshot_raw_html_sources(
        snapshot,
        requested=output_root / "union-raw-artifacts",
        use_embedded_entries=True,
    )
    assert raw_directory is None
    assert raw_paths is not None
    assert raw_paths["73330395"].read_bytes() == docket_html

    (output_root / "union-terminal-observations.jsonl").write_text("")
    assert cli_module.main(command) == 0
    assert _jsonl(output_root / "union-terminal-observations.jsonl") == archived

    assert (
        cli_module.main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(tmp_path / "public-plan"),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                _cycle_hash(stale_root),
                "--raw-html-dir",
                str(output_root / "union-raw-artifacts"),
                "--use-embedded-entries",
                "--target-clean-cases",
                "1",
                "--cost-per-missing-document-usd",
                "0.10",
                "--execute",
            ]
        )
        == 0
    )

    shutil.rmtree(stale_root / "snapshots")
    shutil.rmtree(corrected_root / "snapshots")
    verify_snapshot(
        snapshot,
        expected_cycle_hash=_cycle_hash(stale_root),
        require_complete=True,
        require_saturated=True,
    )
    assert cli_module._owned_raw_records_from_snapshot(snapshot) == [packet_raw]

    manifest_path = snapshot / "manifest.json"
    original_manifest = manifest_path.read_text()
    manifest = json.loads(original_manifest)
    correction = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "longitudinal_corrections"
    ][0]
    forged_source_hash = "f" * 64
    authoritative_source_hash = correction["canonical_source_manifest_sha256"]
    correction["canonical_source_manifest_sha256"] = forged_source_hash
    authoritative_observation = next(
        observation
        for observation in correction["observations"]
        if observation["source_manifest_sha256"] == authoritative_source_hash
    )
    authoritative_observation["source_manifest_sha256"] = forged_source_hash
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CycleAcquisitionStoreError, match="unauthenticated authority"):
        cli_module._owned_raw_records_from_snapshot(snapshot)

    manifest = json.loads(original_manifest)
    correction = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "longitudinal_corrections"
    ][0]
    correction["observations"][0]["terminal_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CycleAcquisitionStoreError, match="terminal hash drift"):
        cli_module._owned_raw_records_from_snapshot(snapshot)


def test_union_preserves_excluded_evidence_drift_under_explicit_source_authority(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-69879510"
    failed_fetch = _snapshot(
        tmp_path / "failed-fetch",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "fetch_failed",
                    "page_1_acquired": False,
                },
                b"<html><body>partial fetch</body></html>",
            )
        ],
    )
    substantive_evidence = {
        "candidate_id": candidate_id,
        "reason": "not_civil_cv_docket",
        "primary_exclusion_reason": "not_civil_cv_docket",
    }
    substantive = _snapshot(
        tmp_path / "substantive",
        batch_id="current-policy-rescreen",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                substantive_evidence,
                b"<html><body>substantive screen</body></html>",
            )
        ],
    )

    union = load_screening_snapshot_union(
        (failed_fetch, substantive),
        expected_manifest_sha256=(
            _manifest_sha256(failed_fetch),
            _manifest_sha256(substantive),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "failed-fetch"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(substantive),
        ),
    )

    [candidate] = union.candidates
    assert candidate.state == "excluded"
    assert candidate.evidence == substantive_evidence
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert {row["evidence"]["reason"] for row in correction["observations"]} == {
        "fetch_failed",
        "not_civil_cv_docket",
    }


def test_union_rejects_unpinned_or_extra_longitudinal_corrections(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>first</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_disposition"},
                b"<html><body>second</body></html>",
            )
        ],
    )
    common = {
        "source_snapshots": (first, second),
        "expected_manifest_sha256": (
            _manifest_sha256(first),
            _manifest_sha256(second),
        ),
        "expected_cycle_hash": _cycle_hash(tmp_path / "first"),
    }

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="requires an explicit authenticated correction source",
    ):
        load_screening_snapshot_union(**common)

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="correction pins do not exactly match terminal conflicts",
    ):
        load_screening_snapshot_union(
            **common,
            expected_terminal_correction_candidate_id=(candidate_id, "extra"),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
                _manifest_sha256(first),
            ),
        )


def test_union_rejects_multiple_distinct_active_proofs_even_when_one_is_pinned(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="first-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                _strict_screen_evidence(candidate_id),
                b"<html><body>first active proof</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="second-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {
                    "candidate_id": candidate_id,
                    "first_written_mtd_disposition_date": "2026-07-01",
                    "selected_entries": [{"entry_number": 13}],
                },
                b"<html><body>second active proof</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
            ),
        )


def test_union_allows_raw_backed_active_authority_over_exact310_rawless_reproof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-72615251"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="terminal-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>authenticated docket proof</body></html>",
            )
        ],
    )
    reproof_evidence = deepcopy(raw_backed_evidence)
    reproof_evidence["policy_rebind"] = {
        "strategy": "authenticated_strict_evidence_reproof_v1",
        "current_policy_proof_available": True,
        "raw_artifact_count": 0,
        "source_cycle_hash": "a" * 64,
        "source_batch_id": "exact310-source",
        "source_snapshot_manifest_sha256": "b" * 64,
        "source_observation_sha256": "c" * 64,
        "source_state": "accepted",
        "source_reason_code": "strict_clean_screen_passed",
        "target_cycle_hash": _cycle_hash(tmp_path / "raw-backed"),
    }
    rawless_reproof = _snapshot(
        tmp_path / "rawless-reproof",
        batch_id="exact310-rebind",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                reproof_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(rawless_reproof, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, rawless_reproof),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(rawless_reproof),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )

    _set_exact310_stage_commitments(
        rawless_reproof,
        policy_rebind=reproof_evidence["policy_rebind"],
    )
    union = load_screening_snapshot_union(
        (raw_backed, rawless_reproof),
        expected_manifest_sha256=(
            _manifest_sha256(raw_backed),
            _manifest_sha256(rawless_reproof),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(raw_backed),
        ),
    )

    [candidate] = union.candidates
    assert candidate.evidence == raw_backed_evidence
    [canonical_raw] = union.canonical_raw_artifacts
    assert canonical_raw.content == (
        b"<html><body>authenticated docket proof</body></html>"
    )
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert correction["active_reproof_reconciliation"] == {
        "policy": (
            "unique_raw_backed_authority_over_authenticated_rawless_exact310_reproof_v1"
        ),
        "rawless_source_manifest_sha256": [
            _manifest_sha256(rawless_reproof),
        ],
    }
    assert cli_module._snapshot_longitudinal_active_raw_mapping(
        union.stage_commitment,
        candidate_records=[
            {
                "candidate_id": candidate.candidate_id,
                "state": candidate.state,
                "reason_code": candidate.reason_code,
                "evidence": candidate.evidence,
            }
        ],
        archived_records=[
            {
                "candidate_id": artifact.candidate_id,
                "sha256": artifact.sha256,
                "byte_count": artifact.byte_count,
                "retrieved_at": artifact.retrieved_at,
            }
            for artifact in union.raw_artifacts
        ],
    ) == {
        candidate_id: (
            canonical_raw.sha256,
            canonical_raw.byte_count,
            canonical_raw.retrieved_at,
        )
    }
    tampered_commitment = deepcopy(union.stage_commitment)
    del tampered_commitment["longitudinal_corrections"][0][
        "active_reproof_reconciliation"
    ]
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="not uniquely reconcilable",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=[
                {
                    "candidate_id": candidate.candidate_id,
                    "state": candidate.state,
                    "reason_code": candidate.reason_code,
                    "evidence": candidate.evidence,
                }
            ],
            archived_records=[
                {
                    "candidate_id": artifact.candidate_id,
                    "sha256": artifact.sha256,
                    "byte_count": artifact.byte_count,
                    "retrieved_at": artifact.retrieved_at,
                }
                for artifact in union.raw_artifacts
            ],
        )

    tampered_commitment = deepcopy(union.stage_commitment)
    rawless_source = next(
        source
        for source in tampered_commitment["sources"]
        if source["manifest_sha256"] == _manifest_sha256(rawless_reproof)
    )
    rawless_source["stage_commitments"]["target_cycle_hash"] = "d" * 64
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="invalid rawless active reproof",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=[
                {
                    "candidate_id": candidate.candidate_id,
                    "state": candidate.state,
                    "reason_code": candidate.reason_code,
                    "evidence": candidate.evidence,
                }
            ],
            archived_records=[
                {
                    "candidate_id": artifact.candidate_id,
                    "sha256": artifact.sha256,
                    "byte_count": artifact.byte_count,
                    "retrieved_at": artifact.retrieved_at,
                }
                for artifact in union.raw_artifacts
            ],
        )

    newly_free_reproof = _snapshot(
        tmp_path / "newly-free-reproof",
        batch_id="exact310-newly-free",
        observations=[
            (
                candidate_id,
                "newly_free",
                "newly_free",
                reproof_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(newly_free_reproof, "raw-artifacts.jsonl", [])
    _set_exact310_stage_commitments(
        newly_free_reproof,
        policy_rebind=reproof_evidence["policy_rebind"],
    )
    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, newly_free_reproof),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(newly_free_reproof),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )


def test_union_rejects_generic_rawless_distinct_active_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-72615251"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="terminal-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>authenticated docket proof</body></html>",
            )
        ],
    )
    rawless_evidence = deepcopy(raw_backed_evidence)
    rawless_evidence["candidate"]["url"] = (
        "https://www.courtlistener.com/docket/72615251/other-proof/"
    )
    rawless = _snapshot(
        tmp_path / "rawless",
        batch_id="unbound-rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                rawless_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(rawless, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, rawless),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(rawless),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )


def test_union_allows_raw_backed_authority_over_authenticated_direct_rest_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="firecrawl-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>current public docket proof</body></html>",
            )
        ],
    )
    _set_firecrawl_screening_implementation(raw_backed)

    direct_rest_evidence = deepcopy(raw_backed_evidence)
    direct_rest_evidence["candidate"]["url"] = (
        "https://www.courtlistener.com/docket/61568804/rest-observation/"
    )
    direct_rest = _snapshot(
        tmp_path / "direct-rest",
        batch_id="direct-rest-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                direct_rest_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(direct_rest, "raw-artifacts.jsonl", [])

    union = load_screening_snapshot_union(
        (raw_backed, direct_rest),
        expected_manifest_sha256=(
            _manifest_sha256(raw_backed),
            _manifest_sha256(direct_rest),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(raw_backed),
        ),
    )

    [candidate] = union.candidates
    assert candidate.evidence == raw_backed_evidence
    [canonical_raw] = union.canonical_raw_artifacts
    assert canonical_raw.content == (
        b"<html><body>current public docket proof</body></html>"
    )
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert correction["active_reproof_reconciliation"] == {
        "policy": (
            "unique_raw_backed_authority_over_authenticated_rawless_"
            "direct_rest_proof_v1"
        ),
        "rawless_source_manifest_sha256": [
            _manifest_sha256(direct_rest),
        ],
    }
    candidate_records = [
        {
            "candidate_id": candidate.candidate_id,
            "state": candidate.state,
            "reason_code": candidate.reason_code,
            "evidence": candidate.evidence,
        }
    ]
    archived_records = [
        {
            "candidate_id": artifact.candidate_id,
            "sha256": artifact.sha256,
            "byte_count": artifact.byte_count,
            "retrieved_at": artifact.retrieved_at,
        }
        for artifact in union.raw_artifacts
    ]
    assert cli_module._snapshot_longitudinal_active_raw_mapping(
        union.stage_commitment,
        candidate_records=candidate_records,
        archived_records=archived_records,
    ) == {
        candidate_id: (
            canonical_raw.sha256,
            canonical_raw.byte_count,
            canonical_raw.retrieved_at,
        )
    }

    tampered_commitment = deepcopy(union.stage_commitment)
    rawless_source = next(
        source
        for source in tampered_commitment["sources"]
        if source["manifest_sha256"] == _manifest_sha256(direct_rest)
    )
    rawless_source["stage_commitments"]["unbound"] = True
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="invalid rawless active reproof",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=candidate_records,
            archived_records=archived_records,
        )


def test_union_rejects_active_correction_without_source_bound_raw(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>first</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                _strict_screen_evidence(candidate_id),
                b"<html><body>second</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(second, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks exactly one source-bound raw artifact",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
            ),
        )


def test_union_rejects_source_raw_drift_within_unique_active_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    active_evidence = _strict_screen_evidence(candidate_id)
    first_active = _snapshot(
        tmp_path / "first-active",
        batch_id="first-active",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                active_evidence,
                b"<html><body>active raw version one</body></html>",
            )
        ],
    )
    second_active = _snapshot(
        tmp_path / "second-active",
        batch_id="second-active",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                active_evidence,
                b"<html><body>active raw version two</body></html>",
            )
        ],
    )
    excluded = _snapshot(
        tmp_path / "excluded",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>excluded raw</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks exactly one source-bound raw artifact",
    ):
        load_screening_snapshot_union(
            (first_active, second_active, excluded),
            expected_manifest_sha256=(
                _manifest_sha256(first_active),
                _manifest_sha256(second_active),
                _manifest_sha256(excluded),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first-active"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(first_active),
            ),
        )


def test_union_rejects_cross_candidate_raw_path_substitution(tmp_path: Path) -> None:
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                "courtlistener-docket-61568804",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568804",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568804</body></html>",
            ),
            (
                "courtlistener-docket-61568805",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568805",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568805</body></html>",
            ),
        ],
    )
    raw_records = _jsonl(first / "raw-artifacts.jsonl")
    raw_records[0]["candidate_id"], raw_records[1]["candidate_id"] = (
        raw_records[1]["candidate_id"],
        raw_records[0]["candidate_id"],
    )
    _rewrite_snapshot_jsonl(first, "raw-artifacts.jsonl", raw_records)
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                "courtlistener-docket-61568806",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568806",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568806</body></html>",
            )
        ],
    )

    with pytest.raises(ScreeningSnapshotUnionError, match="ownership mismatch"):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_cross_source_raw_owner_substitution(tmp_path: Path) -> None:
    first_id = "courtlistener-docket-61568804"
    second_id = "courtlistener-docket-61568805"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                first_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": first_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568804</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                second_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": second_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568805</body></html>",
            )
        ],
    )
    [raw_record] = _jsonl(first / "raw-artifacts.jsonl")
    old_path = Path(raw_record["path"])
    substituted_path = old_path.with_name("61568805.html")
    old_path.rename(substituted_path)
    raw_record["candidate_id"] = second_id
    raw_record["path"] = str(substituted_path)
    _rewrite_snapshot_jsonl(first, "raw-artifacts.jsonl", [raw_record])

    with pytest.raises(
        SnapshotVerificationError,
        match=r"raw-artifacts\.jsonl references unknown candidate_id.*61568805",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_uncommitted_raw_path_before_reading_referenced_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id = "courtlistener-docket-61568804"
    second_id = "courtlistener-docket-61568805"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                first_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": first_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568804</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                second_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": second_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568805</body></html>",
            )
        ],
    )
    sentinel = (tmp_path / "must-not-be-read.html").resolve()
    sentinel.write_bytes(b"<html><body>uncommitted local file</body></html>")
    [raw_record] = _jsonl(first / "raw-artifacts.jsonl")
    raw_record["path"] = str(sentinel)
    # Deliberately do not update manifest.json: the metadata is unauthenticated.
    (first / "raw-artifacts.jsonl").write_text(json.dumps(raw_record) + "\n")

    original_read_bytes = Path.read_bytes
    referenced_file_reads: list[Path] = []

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve() == sentinel:
            referenced_file_reads.append(path)
            raise AssertionError("unauthenticated raw path was read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    with pytest.raises(
        SnapshotVerificationError,
        match=r"snapshot file commitment mismatch: raw-artifacts\.jsonl",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )
    assert referenced_file_reads == []


def test_union_consumes_pinned_manifest_buffer_when_path_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>baseline docket</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>terminal docket</body></html>",
            )
        ],
    )
    first_manifest_sha256 = _manifest_sha256(first)
    first_manifest_path = first / "manifest.json"
    replacement = json.loads(first_manifest_path.read_text())
    replacement["batch_id"] = "replacement-must-not-propagate"
    replacement_payload = json.dumps(replacement).encode()
    original_read = union_module._read_regular_file
    replaced = False

    def replace_after_buffer(path: Path, label: str) -> bytes:
        nonlocal replaced
        payload = original_read(path, label)
        if path == first_manifest_path and not replaced:
            first_manifest_path.write_bytes(replacement_payload)
            replaced = True
        return payload

    monkeypatch.setattr(union_module, "_read_regular_file", replace_after_buffer)

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(
            first_manifest_sha256,
            _manifest_sha256(second),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert replaced is True
    assert union.stage_commitment["sources"][0]["batch_id"] == "baseline"


def test_union_consumes_authenticated_payload_buffer_when_path_mutates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>baseline docket</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>terminal docket</body></html>",
            )
        ],
    )
    candidates_path = first / "candidates.jsonl"
    [replacement] = _jsonl(candidates_path)
    replacement["reason_code"] = "tampered_after_authentication"
    replacement["evidence"] = {
        "candidate_id": candidate_id,
        "reason": "tampered_after_authentication",
    }
    replacement_payload = (json.dumps(replacement) + "\n").encode()
    original_read = union_module._read_regular_file
    mutated = False

    def mutate_after_buffer(path: Path, label: str) -> bytes:
        nonlocal mutated
        payload = original_read(path, label)
        if path == candidates_path and not mutated:
            candidates_path.write_bytes(replacement_payload)
            mutated = True
        return payload

    monkeypatch.setattr(union_module, "_read_regular_file", mutate_after_buffer)

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(
            _manifest_sha256(first),
            _manifest_sha256(second),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert mutated is True
    assert union.candidates[0].reason_code == "strict_clean_screen_failed"


def _snapshot(
    root: Path,
    *,
    batch_id: str,
    observations: list[tuple[str, str, str, dict[str, Any], bytes]],
    cycle_policy: dict[str, object] | None = None,
) -> Path:
    store_path = root / "cycle.sqlite3"
    term = "fixture-term"
    raw_root = root / "raw"
    raw_root.mkdir(parents=True)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(_CYCLE_POLICY if cycle_policy is None else cycle_policy)
        store.ensure_batch(batch_id, {"source": batch_id})
        store.ensure_terms(batch_id, (term,))
        store.commit_search_page(
            batch_id,
            term,
            None,
            tuple(
                DiscoveryHit(
                    provider_hit_id=f"{batch_id}:{candidate_id}",
                    candidate_id=candidate_id,
                    payload={"candidate_id": candidate_id},
                )
                for candidate_id in dict.fromkeys(
                    candidate_id
                    for (
                        candidate_id,
                        _state,
                        _reason,
                        _evidence,
                        _content,
                    ) in observations
                )
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        for index, (candidate_id, state, reason, evidence, content) in enumerate(
            observations
        ):
            store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state=state,
                reason_code=reason,
                evidence=evidence,
                observed_at="2026-07-16T12:00:00Z",
            )
            docket_id = candidate_id.removeprefix("courtlistener-docket-")
            raw_path = raw_root / f"{docket_id}.html"
            store.write_raw_artifact(
                candidate_id,
                raw_path,
                content,
                retrieved_at=(
                    f"2026-07-16T12:00:0{index}Z"
                    if batch_id == "baseline"
                    else f"2026-07-16T13:00:0{index}Z"
                ),
            )
        return store.export_snapshot(
            root / "snapshots",
            snapshot_id=f"{batch_id}-complete",
            batch_id=batch_id,
            complete=True,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )


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
        "filed_at": "2026-06-30",
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
    selected_entries: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    docket_id = candidate_id.removeprefix("courtlistener-docket-")
    entries = selected_entries or [
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
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": entries,
        "mtd_decision_screen": {
            "status": "accepted_strict_civil_mtd_decision",
            "exclusion_reasons": [],
            "actual_mtd_decision_entry_count": 1,
            "decision_entries": [
                {
                    "row_id": "entry-12",
                    "entry_number": "12",
                    "filed_at": "2026-06-30",
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


def _raw_docket_html(entries: list[dict[str, object]]) -> bytes:
    rows: list[str] = []
    for entry in entries:
        [document] = entry["documents"]  # type: ignore[misc]
        rows.append(
            '<div class="row" id="{row_id}">'
            '<div class="col-xs-1">{entry_number}</div>'
            '<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span>'
            "</div>"
            '<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>{kind}</div>'
            "<div>{description}</div>"
            '<a href="{href}">{action_label}</a>'
            "</div></div></div>".format(
                row_id=entry["row_id"],
                entry_number=entry["entry_number"],
                filed_at=entry["filed_at"],
                text=entry["text"],
                kind=document["kind"],
                description=document["description"],
                href=document["href"],
                action_label=document["action_label"],
            )
        )
    return (
        "<html><head><title>Fixture docket</title></head><body>"
        '<div id="docket-entry-table">' + "".join(rows) + "</div></body></html>"
    ).encode()


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _policy_rebind_fixture_policies() -> tuple[dict[str, object], dict[str, object]]:
    package_root = Path(cli_module.__file__).resolve().parent
    target_hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in {
            "mtd_acquisition_screen": (
                package_root / "ingestion" / "mtd_acquisition_screen.py"
            ),
            "courtlistener_acquisition": (
                package_root / "ingestion" / "courtlistener_acquisition.py"
            ),
            "restricted_material": (
                package_root / "ingestion" / "restricted_material.py"
            ),
            "contamination_filters": (
                package_root / "selection" / "contamination_filters.py"
            ),
            "motion_linkage": package_root / "selection" / "motion_linkage.py",
        }.items()
    }
    source_hashes = dict(target_hashes)
    source_hashes["restricted_material"] = SOURCE_RESTRICTED_MATERIAL_SHA256
    source_policy: dict[str, object] = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "screening_source_sha256": source_hashes,
    }
    target_policy: dict[str, object] = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "screening_source_sha256": target_hashes,
    }
    return source_policy, target_policy


def _set_firecrawl_screening_implementation(snapshot: Path) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    stage_commitments = manifest.setdefault("stage_commitments", {})
    stage_commitments["firecrawl_screen_inputs"] = {
        "schema_version": "legalforecast.firecrawl_screen_input_commitment.v1"
    }
    stage_commitments["firecrawl_screening_implementation"] = (
        firecrawl_screening_implementation()
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )


def _set_exact310_stage_commitments(
    snapshot: Path,
    *,
    policy_rebind: dict[str, Any],
) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    candidate_count = manifest["files"]["candidates.jsonl"]["row_count"]
    manifest["stage_commitments"] = {
        "stage": "exact310-terminal-rest-policy-rebind",
        "contract_sha256": "d" * 64,
        "source_cycle_hash": policy_rebind["source_cycle_hash"],
        "source_batch_id": policy_rebind["source_batch_id"],
        "source_snapshot_manifest_sha256": policy_rebind[
            "source_snapshot_manifest_sha256"
        ],
        "source_candidate_set_sha256": "e" * 64,
        "transfer_receipt_sha256": "f" * 64,
        "target_seed_summary_sha256": "1" * 64,
        "source_observations_sha256": "2" * 64,
        "target_cycle_hash": policy_rebind["target_cycle_hash"],
        "target_batch_id": manifest["batch_id"],
        "target_batch_digest": manifest["batch_digest"],
        "target_outcomes_sha256": "3" * 64,
        "preserve_current_count": 0,
        "reprove_current_count": candidate_count,
        "reprove_exclusion_count": 0,
        "fail_closed_count": 0,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )


def _cycle_hash(root: Path) -> str:
    with CycleAcquisitionStore(root / "cycle.sqlite3") as store:
        return store.cycle_hash


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _rewrite_snapshot_jsonl(
    snapshot: Path,
    filename: str,
    records: list[dict[str, Any]],
) -> None:
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    (snapshot / filename).write_bytes(payload)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": len(records),
    }
    manifest_path.write_text(json.dumps(manifest))

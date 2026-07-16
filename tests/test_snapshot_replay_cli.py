from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.snapshot_replay import (
    ReplaySourceSnapshot,
    SnapshotReplayBundle,
    SnapshotReplayError,
    _AssemblyExpansion,
    _expand_assembly_closure,
    _read_hashed_json_object,
    _verified_success,
    _verify_entry_transport_enrichment,
    _verify_screen_input_commitment,
    firecrawl_screen_input_commitments,
    source_replay_commitment,
)
from legalforecast.protocol.freeze import sha256_file

ANCHOR = "2026-06-30"


def test_replay_screening_snapshots_is_provider_free_and_globally_plannable(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("101",),
        fetch_exclusions=("102",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("101", "103"),
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"

    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    output_root = tmp_path / "replay"
    snapshot_id = "global-replay"
    normalized_assembly_path = (
        assembly_root / "unused" / ".." / "run-cards/assemble-cycle-acquisition.json"
    )
    command = _replay_command(
        output_root=output_root,
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=normalized_assembly_path,
        snapshot_id=snapshot_id,
        expected_assembly_sha256=sha256_file(assembly_run_card),
    )

    assert main(command) == 0

    snapshot = output_root / "snapshots" / snapshot_id
    manifest = verify_snapshot(
        snapshot,
        expected_cycle_hash=target_cycle_hash,
        require_saturated=True,
    )
    assert (
        manifest["stage_commitments"]["source_bound_replay"]["source_candidate_count"]
        == 3
    )
    replay_commitment = manifest["stage_commitments"]["source_bound_replay"]
    assert replay_commitment["source_closure_sha256"] == (
        _fixture_source_closure_sha256(assembly_run_card)
    )
    assert replay_commitment["source_assembly_run_card_count"] == 1
    assert str(tmp_path) not in json.dumps(replay_commitment, sort_keys=True)
    assert "source_assembly_run_card" not in replay_commitment
    assert all("path" not in source for source in replay_commitment["source_snapshots"])
    summary = _read_json(snapshot / "summary.json")
    assert summary == {
        "accepted_count": 2,
        "batch_id": "superseding-replay",
        "excluded_count": 1,
        "processed_count": 3,
        "reconciliation_complete": True,
    }
    assert {
        row["candidate_id"] for row in _read_jsonl(snapshot / "screened-cases.jsonl")
    } == {"case-dev-101", "case-dev-103"}
    [excluded] = _read_jsonl(snapshot / "exclusions.jsonl")
    assert excluded["candidate_id"] == "case-dev-102"
    assert excluded["primary_exclusion_reason"] == "decision_before_release_anchor"
    run_card = _read_json(output_root / "run-cards/replay-screening-snapshots.json")
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False

    public_plan = tmp_path / "public-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(public_plan),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                target_cycle_hash,
                "--target-clean-cases",
                "2",
                "--execute",
            ]
        )
        == 0
    )
    assert (
        _read_json(public_plan / "public-packet-plan-summary.json")[
            "screened_case_count"
        ]
        == 2
    )


def test_replay_screening_snapshots_rejects_provisional_source_laundering(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=_cycle_policy(extra={"fixture_generation": "provisional"}),
        batch_id="provisional-source",
        successes=("101",),
        provisional=True,
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    assembly = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly,
                snapshot_id="must-not-exist",
                expected_assembly_sha256=sha256_file(assembly),
            )
        )
        == 2
    )
    assert not (tmp_path / "replay/snapshots/must-not-exist").exists()


def test_replay_screening_snapshots_combines_cross_cycle_supplemental_snapshots(
    tmp_path: Path,
) -> None:
    old_policy = _cycle_policy(extra={"fixture_generation": "old"})
    old_snapshot = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "old.sqlite3",
        policy=old_policy,
        batch_id="old-source",
        successes=("151",),
    )
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                str(verify_snapshot(old_snapshot)["cycle_hash"]),
                "--batch-root",
                str(old_snapshot),
                "--execute",
            ]
        )
        == 0
    )
    first_supplemental_policy = _cycle_policy(extra={"fixture_generation": "jop"})
    first_bundle_root = tmp_path / "jop-bundle"
    first_supplemental = _source_snapshot(
        first_bundle_root,
        store_path=first_bundle_root / "cycle.sqlite3",
        policy=first_supplemental_policy,
        batch_id="jop-source",
        successes=("152",),
    )
    second_supplemental_policy = _cycle_policy(
        extra={"fixture_generation": "adversary"}
    )
    second_bundle_root = tmp_path / "adversary-bundle"
    second_supplemental = _source_snapshot(
        second_bundle_root,
        store_path=second_bundle_root / "cycle.sqlite3",
        policy=second_supplemental_policy,
        batch_id="adversary-source",
        successes=("153",),
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=str(verify_snapshot(old_snapshot)["cycle_hash"]),
        assembly_run_card=assembly_run_card,
        snapshot_id="combined-replay",
        supplemental_snapshots=(first_supplemental, second_supplemental),
    )
    command.extend(
        (
            "--source-snapshot",
            str(first_supplemental),
            "--expected-source-snapshot-cycle-hash",
            str(verify_snapshot(first_supplemental)["cycle_hash"]),
            "--source-snapshot-screen-run-card",
            str(
                first_supplemental.parent.parent
                / "run-cards/screen-firecrawl-dockets.json"
            ),
            "--expected-source-snapshot-screen-run-card-sha256",
            sha256_file(
                first_supplemental.parent.parent
                / "run-cards/screen-firecrawl-dockets.json"
            ),
            "--source-snapshot-bundle-root",
            str(first_bundle_root),
            "--source-snapshot",
            str(second_supplemental),
            "--expected-source-snapshot-cycle-hash",
            str(verify_snapshot(second_supplemental)["cycle_hash"]),
            "--source-snapshot-screen-run-card",
            str(
                second_supplemental.parent.parent
                / "run-cards/screen-firecrawl-dockets.json"
            ),
            "--expected-source-snapshot-screen-run-card-sha256",
            sha256_file(
                second_supplemental.parent.parent
                / "run-cards/screen-firecrawl-dockets.json"
            ),
            "--source-snapshot-bundle-root",
            str(second_bundle_root),
        )
    )

    assert main(command) == 0

    manifest = verify_snapshot(
        tmp_path / "replay/snapshots/combined-replay",
        expected_cycle_hash=target_cycle_hash,
        require_saturated=True,
    )
    stage_commitments = cast(dict[str, Any], manifest["stage_commitments"])
    replay_commitment = cast(dict[str, Any], stage_commitments["source_bound_replay"])
    assert replay_commitment["source_snapshot_count"] == 3
    assert {
        source["cycle_hash"] for source in replay_commitment["source_snapshots"]
    } == {
        str(verify_snapshot(old_snapshot)["cycle_hash"]),
        str(verify_snapshot(first_supplemental)["cycle_hash"]),
        str(verify_snapshot(second_supplemental)["cycle_hash"]),
    }


@pytest.mark.parametrize("hash_count", (0, 2))
def test_replay_screening_snapshots_requires_one_cycle_hash_per_supplement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    hash_count: int,
) -> None:
    old_policy = _cycle_policy(extra={"fixture_generation": "old"})
    old_snapshot = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "old.sqlite3",
        policy=old_policy,
        batch_id="old-source",
        successes=("171",),
    )
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                str(verify_snapshot(old_snapshot)["cycle_hash"]),
                "--batch-root",
                str(old_snapshot),
                "--execute",
            ]
        )
        == 0
    )
    supplemental = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "supplemental.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "supplemental"}),
        batch_id="supplemental",
        successes=("172",),
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=str(verify_snapshot(old_snapshot)["cycle_hash"]),
        assembly_run_card=assembly_root / "run-cards/assemble-cycle-acquisition.json",
        snapshot_id="rejected-replay",
    )
    command.extend(("--source-snapshot", str(supplemental)))
    for _ in range(hash_count):
        command.extend(
            (
                "--expected-source-snapshot-cycle-hash",
                str(verify_snapshot(supplemental)["cycle_hash"]),
            )
        )

    assert main(command) == 2
    assert "each --source-snapshot requires exactly one" in capsys.readouterr().err
    assert not (tmp_path / "replay/snapshots/rejected-replay").exists()


@pytest.mark.parametrize(
    "escape_kind", (None, "raw_symlink", "snapshot_symlink", "traversal")
)
def test_replay_screening_snapshots_reads_relocated_self_contained_supplement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    escape_kind: str | None,
) -> None:
    old_snapshot = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "old.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="old-source",
        successes=("175",),
    )
    assembly_root = tmp_path / "source-assembly"
    old_cycle_hash = str(verify_snapshot(old_snapshot)["cycle_hash"])
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                old_cycle_hash,
                "--batch-root",
                str(old_snapshot),
                "--execute",
            ]
        )
        == 0
    )

    original_root = tmp_path / "volatile-source"
    supplemental = _source_snapshot(
        original_root,
        store_path=original_root / "cycle.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "supplemental"}),
        batch_id="actual-layout",
        successes=("176",),
    )
    original_run_card = (
        supplemental.parent.parent / "run-cards/screen-firecrawl-dockets.json"
    )
    supplemental_cycle_hash = str(verify_snapshot(supplemental)["cycle_hash"])
    archive_root = tmp_path / "durable-archive"
    shutil.copytree(original_root, archive_root)
    shutil.rmtree(original_root)
    archived_snapshot = archive_root / supplemental.relative_to(original_root)
    archived_run_card = archive_root / original_run_card.relative_to(original_root)
    if escape_kind == "raw_symlink":
        archived_raw = archive_root / "actual-layout/raw-docket-html/176.html"
        outside_raw = tmp_path / "outside-raw.html"
        shutil.copyfile(archived_raw, outside_raw)
        archived_raw.unlink()
        archived_raw.symlink_to(outside_raw)
    elif escape_kind == "snapshot_symlink":
        outside_snapshot = tmp_path / "outside-snapshot"
        shutil.copytree(archived_snapshot, outside_snapshot)
        shutil.rmtree(archived_snapshot)
        archived_snapshot.symlink_to(outside_snapshot, target_is_directory=True)
    elif escape_kind == "traversal":
        archived_card = _read_json(archived_run_card)
        successes_path = Path(archived_card["input_paths"][1])
        outside_successes = tmp_path / "outside-successes.jsonl"
        shutil.copyfile(
            archive_root / successes_path.relative_to(original_root),
            outside_successes,
        )
        archived_card["input_paths"][1] = str(
            original_root / "actual-layout/../../outside-successes.jsonl"
        )
        archived_run_card.write_text(
            json.dumps(archived_card, sort_keys=True) + "\n", encoding="utf-8"
        )
    expected_run_card_sha256 = sha256_file(archived_run_card)

    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=old_cycle_hash,
        assembly_run_card=assembly_root / "run-cards/assemble-cycle-acquisition.json",
        snapshot_id="relocated-replay",
        supplemental_snapshots=(archived_snapshot,),
    )
    command.extend(
        (
            "--source-snapshot",
            str(archived_snapshot),
            "--expected-source-snapshot-cycle-hash",
            supplemental_cycle_hash,
            "--source-snapshot-screen-run-card",
            str(archived_run_card),
            "--expected-source-snapshot-screen-run-card-sha256",
            expected_run_card_sha256,
            "--source-snapshot-bundle-root",
            str(archive_root),
        )
    )

    result = main(command)
    if escape_kind is not None:
        assert result == 2
        expected_error = (
            "contains a symlink"
            if escape_kind in {"raw_symlink", "snapshot_symlink"}
            else "cannot access supplemental relocated output"
        )
        assert expected_error in capsys.readouterr().err
        return
    assert result == 0
    summary = _read_json(tmp_path / "replay/replay-screening-summary.json")
    assert summary["source_candidate_count"] == 2
    assert summary["provider_activity_executed"] is False


def test_replay_screening_snapshots_reconciles_volatile_refresh_metadata(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("70652482",),
        retrieved_at="2026-07-14T03:23:36.761146+00:00",
        raw_html_path="/tmp/adversary/70652482.html",
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("70652482",),
        retrieved_at="2026-07-14T04:13:10.918677+00:00",
        raw_html_path="/durable/jop/70652482.html",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="volatile-refresh-replay",
            )
        )
        == 0
    )
    summary = _read_json(tmp_path / "replay/replay-screening-summary.json")
    assert summary["source_candidate_count"] == 1


def test_replay_screening_snapshots_accepts_strictly_appended_docket_refresh(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("71221919",),
        retrieved_at="2026-07-13T05:30:46.705629+00:00",
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("71221919",),
        retrieved_at="2026-07-14T04:13:10.918677+00:00",
        appended_entry_text="NOTICE of supplemental authority filed",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="appended-refresh-replay",
            )
        )
        == 0
    )
    commitment = _read_json(
        tmp_path / "replay/snapshots/appended-refresh-replay/manifest.json"
    )["stage_commitments"]["source_bound_replay"]
    assert commitment["refresh_supersession_count"] == 1
    [supersession] = commitment["refresh_supersessions"]
    assert supersession["candidate_id"] == "case-dev-71221919"
    assert supersession["older_retrieved_at"].startswith("2026-07-13")
    assert supersession["newer_retrieved_at"].startswith("2026-07-14")
    assert (
        supersession["selection_reason"]
        == "strict_monotonic_append_only_docket_refresh"
    )


@pytest.mark.parametrize("mutated_source", ("older", "newer"))
def test_replay_refresh_rechecks_raw_commitments_before_reconciliation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    mutated_source: str,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("71221919",),
        retrieved_at="2026-07-13T05:30:46.705629+00:00",
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("71221919",),
        retrieved_at="2026-07-14T04:13:10.918677+00:00",
        appended_entry_text="NOTICE of supplemental authority filed",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    original_verified_success = _verified_success
    verified_paths: list[Path] = []

    def mutating_verified_success(*args: Any, **kwargs: Any) -> Any:
        success = original_verified_success(*args, **kwargs)
        verified_paths.append(success.raw_path)
        if len(verified_paths) == 2:
            target = verified_paths[0 if mutated_source == "older" else 1]
            target.write_text("tampered after initial verification", encoding="utf-8")
        return success

    monkeypatch.setattr(
        "legalforecast.ingestion.snapshot_replay._verified_success",
        mutating_verified_success,
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="toctou-replay",
            )
        )
        == 2
    )
    assert "raw artifact" in capsys.readouterr().err


def test_replay_rechecks_screen_run_card_after_atomic_parse_and_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("71221920",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    original_reader = _read_hashed_json_object
    mutated = False

    def mutating_reader(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
        nonlocal mutated
        record, digest = original_reader(path, label=label)
        if label == "screen run card" and not mutated:
            mutated = True
            path.write_bytes(path.read_bytes() + b" ")
        return record, digest

    monkeypatch.setattr(
        "legalforecast.ingestion.snapshot_replay._read_hashed_json_object",
        mutating_reader,
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="screen-card-toctou-replay",
            )
        )
        == 2
    )
    assert "source closure evidence changed" in capsys.readouterr().err
    assert not (tmp_path / "replay").exists()


def test_replay_rechecks_top_assembly_card_between_pin_and_expansion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("71221920",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    assembly_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    original_expander = _expand_assembly_closure
    mutated = False

    def mutating_expander(path: Path) -> _AssemblyExpansion:
        nonlocal mutated
        if not mutated:
            mutated = True
            path.write_bytes(path.read_bytes() + b" ")
        return original_expander(path)

    monkeypatch.setattr(
        "legalforecast.ingestion.snapshot_replay._expand_assembly_closure",
        mutating_expander,
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_card,
                snapshot_id="assembly-card-toctou-replay",
            )
        )
        == 2
    )
    assert "source assembly evidence changed" in capsys.readouterr().err
    assert not (tmp_path / "replay").exists()


def test_replay_screening_snapshots_accepts_caption_and_slug_identity_refinement(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("73603887",),
        retrieved_at="2026-07-13T07:49:31.198822+00:00",
        case_name="Leslie Klein - Adversary Proceeding",
        source_slug="leslie-klein-adversary-proceeding",
        court_id="cacb",
        docket_number="2:26-ap-01186",
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("73603887",),
        retrieved_at="2026-07-14T03:23:36.761146+00:00",
        case_name="Sharp, Liquidation Trustee v. Klein",
        source_slug="sharp-liquidation-trustee-v-klein",
        court_id="cacb",
        docket_number="2:26-ap-01186",
        appended_entry_text="NOTICE of supplemental authority filed",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="identity-refinement-replay",
            )
        )
        == 0
    )
    [supersession] = _read_json(
        tmp_path / "replay/snapshots/identity-refinement-replay/manifest.json"
    )["stage_commitments"]["source_bound_replay"]["refresh_supersessions"]
    assert supersession["older_case_name"] == "Leslie Klein - Adversary Proceeding"
    assert supersession["newer_case_name"] == "Sharp, Liquidation Trustee v. Klein"


@pytest.mark.parametrize("stable_field", ("court_id", "docket_number", "pacer_case_id"))
def test_replay_screening_snapshots_rejects_stable_identity_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stable_field: str,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    common = {
        "court_id": "cacb",
        "docket_number": "2:26-ap-01186",
        "pacer_case_id": "12345",
    }
    changed = dict(common)
    changed[stable_field] = {
        "court_id": "nysd",
        "docket_number": "1:26-cv-99999",
        "pacer_case_id": "99999",
    }[stable_field]
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("73603887",),
        retrieved_at="2026-07-13T07:49:31.198822+00:00",
        **common,
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("73603887",),
        retrieved_at="2026-07-14T03:23:36.761146+00:00",
        appended_entry_text="NOTICE of supplemental authority filed",
        **changed,
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="stable-conflict-replay",
            )
        )
        == 2
    )
    assert "conflicting raw artifacts" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mutation",
    ("changed_entry", "deleted_entry", "equal_timestamp", "invalid_timestamp"),
)
def test_replay_screening_snapshots_rejects_nonmonotonic_docket_refresh(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first_has_append = mutation == "deleted_entry"
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("71221919",),
        retrieved_at="2026-07-13T05:30:46.705629+00:00",
        appended_entry_text=(
            "NOTICE of supplemental authority filed" if first_has_append else None
        ),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("71221919",),
        retrieved_at=(
            "2026-07-13T05:30:46.705629+00:00"
            if mutation == "equal_timestamp"
            else "2026-07-14T04:13:10.918677+00:00"
        ),
        decision_text=(
            "ORDER denying Motion to Dismiss"
            if mutation == "changed_entry"
            else "ORDER granting Motion to Dismiss"
        ),
        appended_entry_text=(
            "NOTICE of supplemental authority filed"
            if mutation in {"equal_timestamp", "invalid_timestamp"}
            else None
        ),
    )
    if mutation == "invalid_timestamp":
        successes_path = (
            second.parent.parent.parent / "firecrawl-docket-successes.jsonl"
        )
        success_records = _read_jsonl(successes_path)
        success_records[0]["retrieved_at"] = "not-a-timestamp"
        _write_jsonl(successes_path, success_records)
        manifest_path = second / "manifest.json"
        manifest = _read_json(manifest_path)
        manifest["stage_commitments"]["firecrawl_screen_inputs"] = (
            firecrawl_screen_input_commitments(
                success_records=success_records,
                fetch_exclusion_records=[],
            )
        )
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="rejected-refresh-replay",
            )
        )
        == 2
    )
    assert "conflicting raw artifacts" in capsys.readouterr().err


def test_replay_screening_snapshots_binds_legacy_screen_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "legacy"}),
        batch_id="legacy-source",
        successes=("701",),
    )
    manifest_path = source / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest.pop("stage_commitments")
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    source_cycle_hash = str(manifest["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=assembly_root / "run-cards/assemble-cycle-acquisition.json",
        snapshot_id="legacy-replay",
    )

    assert main(command) == 2
    error = capsys.readouterr().err
    match = re.search(r"computed ([0-9a-f]{64})", error)
    assert match is not None
    wrong_hash_command = [
        *command,
        "--expected-legacy-screen-inputs-sha256",
        "0" * 64,
    ]
    assert main(wrong_hash_command) == 2
    assert "legacy screen-input aggregate SHA-256 mismatch" in capsys.readouterr().err
    command.extend(("--expected-legacy-screen-inputs-sha256", match.group(1)))

    assert main(command) == 0
    commitment = _read_json(tmp_path / "replay/snapshots/legacy-replay/manifest.json")[
        "stage_commitments"
    ]["source_bound_replay"]
    assert commitment["legacy_screen_input_count"] == 1
    assert commitment["legacy_screen_inputs_sha256"] == match.group(1)


def test_source_closure_rejects_mutated_nested_assembly_card(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "nested"}),
        batch_id="nested-source",
        successes=("702",),
    )
    child_card = tmp_path / "child-assembly/run-cards/assemble-cycle-acquisition.json"
    child_card.parent.mkdir(parents=True)
    child_card.write_text(
        json.dumps(
            {
                "stage": "assemble-cycle-acquisition",
                "input_paths": [str(source)],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    top_card = tmp_path / "top-assembly/run-cards/assemble-cycle-acquisition.json"
    top_card.parent.mkdir(parents=True)
    top_card.write_text(
        json.dumps(
            {
                "stage": "assemble-cycle-acquisition",
                "input_paths": [str(child_card.parent.parent)],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=str(verify_snapshot(source)["cycle_hash"]),
        assembly_run_card=top_card,
        snapshot_id="nested-closure-replay",
    )
    child_record = _read_json(child_card)
    child_record["uncommitted_mutation"] = True
    child_card.write_text(
        json.dumps(child_record, sort_keys=True) + "\n", encoding="utf-8"
    )

    assert main(command) == 2
    assert "source closure SHA-256 mismatch" in capsys.readouterr().err
    assert not (tmp_path / "replay").exists()


@pytest.mark.parametrize("stage_commitments", (None, "invalid", [], 17))
def test_legacy_screen_inputs_rejects_malformed_stage_commitments(
    tmp_path: Path,
    stage_commitments: object,
) -> None:
    with pytest.raises(
        SnapshotReplayError, match="stage commitments have an invalid shape"
    ):
        _verify_screen_input_commitment(
            manifest={"stage_commitments": stage_commitments},
            successes=(),
            exclusions=(),
            snapshot=tmp_path / "snapshot",
        )


@pytest.mark.parametrize("committed", (None, "invalid", [], 17))
def test_legacy_screen_inputs_rejects_malformed_present_commitment(
    tmp_path: Path,
    committed: object,
) -> None:
    with pytest.raises(
        SnapshotReplayError, match="screen input commitment has an invalid shape"
    ):
        _verify_screen_input_commitment(
            manifest={"stage_commitments": {"firecrawl_screen_inputs": committed}},
            successes=(),
            exclusions=(),
            snapshot=tmp_path / "snapshot",
        )


def test_legacy_screen_inputs_accepts_only_absent_commitment_fields(
    tmp_path: Path,
) -> None:
    assert _verify_screen_input_commitment(
        manifest={},
        successes=(),
        exclusions=(),
        snapshot=tmp_path / "snapshot",
    ) == firecrawl_screen_input_commitments(
        success_records=(), fetch_exclusion_records=()
    )


def test_legacy_screen_inputs_rejects_present_empty_stage_commitments(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SnapshotReplayError, match="lacks firecrawl_screen_inputs commitment"
    ):
        _verify_screen_input_commitment(
            manifest={"stage_commitments": {}},
            successes=(),
            exclusions=(),
            snapshot=tmp_path / "snapshot",
        )


def test_replay_screening_snapshots_rejects_substantive_refresh_metadata_conflict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("72337445",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("72337445",),
        case_name="Substantively Different v. Identity",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_root
                / "run-cards/assemble-cycle-acquisition.json",
                snapshot_id="conflicting-refresh-replay",
            )
        )
        == 2
    )
    assert "conflicting raw artifacts" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("duplicate_cycle_hash", "error_pattern"),
    (("0" * 64, "conflicting expected cycle hashes"), (None, "duplicate source")),
)
def test_replay_screening_snapshots_rejects_duplicate_source_bindings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    duplicate_cycle_hash: str | None,
    error_pattern: str,
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("181",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=assembly_root / "run-cards/assemble-cycle-acquisition.json",
        snapshot_id="rejected-replay",
    )
    command.extend(
        (
            "--source-snapshot",
            str(source),
            "--expected-source-snapshot-cycle-hash",
            duplicate_cycle_hash or source_cycle_hash,
            "--source-snapshot-screen-run-card",
            str(source.parent.parent / "run-cards/screen-firecrawl-dockets.json"),
            "--expected-source-snapshot-screen-run-card-sha256",
            sha256_file(
                source.parent.parent / "run-cards/screen-firecrawl-dockets.json"
            ),
            "--source-snapshot-bundle-root",
            str(tmp_path),
        )
    )

    assert main(command) == 2
    assert error_pattern in capsys.readouterr().err
    assert not (tmp_path / "replay/snapshots/rejected-replay").exists()


@pytest.mark.parametrize(
    ("mutation", "error_pattern"),
    (
        ("assembly_hash", "source assembly SHA-256 mismatch"),
        ("source_cycle", "source snapshot cycle hash mismatch"),
        ("target_cycle", "target cycle hash mismatch"),
        ("raw_html", "raw artifact"),
        ("missing_raw", "raw artifact"),
        ("symlink_raw", "symlink"),
        ("success_record", "source screen input commitment mismatch"),
        ("relative_run_card_path", "relative input_paths"),
        ("unused_legacy_hash", "supplied but no legacy source snapshots"),
    ),
)
def test_replay_screening_snapshots_rejects_unbound_or_unsafe_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    error_pattern: str,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    source = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source",
        successes=("201",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=(
            "0" * 64 if mutation == "target_cycle" else target_cycle_hash
        ),
        source_cycle_hash=(
            "1" * 64 if mutation == "source_cycle" else source_cycle_hash
        ),
        assembly_run_card=assembly_run_card,
        snapshot_id="rejected-replay",
        expected_assembly_sha256=(
            "2" * 64 if mutation == "assembly_hash" else sha256_file(assembly_run_card)
        ),
    )
    if mutation == "unused_legacy_hash":
        command.extend(("--expected-legacy-screen-inputs-sha256", "3" * 64))
    if mutation == "raw_html":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        raw_path.write_text("tampered", encoding="utf-8")
    elif mutation == "missing_raw":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        raw_path.unlink()
    elif mutation == "symlink_raw":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        original = raw_path.with_suffix(".original")
        raw_path.rename(original)
        raw_path.symlink_to(original)
    elif mutation in {"success_record", "relative_run_card_path"}:
        screen_run_card = (
            source.parent.parent / "run-cards/screen-firecrawl-dockets.json"
        )
        run_card = _read_json(screen_run_card)
        if mutation == "success_record":
            successes_path = Path(run_card["input_paths"][1])
            [success] = _read_jsonl(successes_path)
            success["case_metadata"]["case_name"] = "Tampered v. Metadata"
            _write_jsonl(successes_path, [success])
        else:
            run_card["input_paths"][1] = "relative/successes.jsonl"
            screen_run_card.write_text(
                json.dumps(run_card, sort_keys=True) + "\n", encoding="utf-8"
            )

    assert main(command) == 2
    assert error_pattern in capsys.readouterr().err
    assert not (tmp_path / "replay/snapshots/rejected-replay").exists()


def test_replay_screening_snapshots_rejects_conflicting_overlap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("301",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("301",),
        decision_text="ORDER denying Motion to Dismiss",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_run_card,
                snapshot_id="conflicting-replay",
            )
        )
        == 2
    )
    assert (
        "conflicting raw artifacts for candidate case-dev-301"
        in capsys.readouterr().err
    )


def test_replay_screening_snapshots_rejects_docket_identity_collision(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("401",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("401",),
        candidate_ids={"401": "case-dev-collision"},
    )
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                str(verify_snapshot(first)["cycle_hash"]),
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=str(verify_snapshot(first)["cycle_hash"]),
                assembly_run_card=(
                    assembly_root / "run-cards/assemble-cycle-acquisition.json"
                ),
                snapshot_id="colliding-replay",
            )
        )
        == 2
    )
    assert "docket ID collision" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    (
        "--screened-cases-output",
        "--exclusions-output",
        "--summary-output",
        "--run-card-output",
        "--log-output",
    ),
)
def test_replay_screening_snapshots_rejects_side_outputs_inside_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    flag: str,
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("451",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    output_root = tmp_path / "replay"
    snapshot = output_root / "snapshots/rejected-output"
    command = _replay_command(
        output_root=output_root,
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=(assembly_root / "run-cards/assemble-cycle-acquisition.json"),
        snapshot_id="rejected-output",
    )
    command.extend((flag, str(snapshot / f"{flag[2:]}.json")))

    assert main(command) == 2

    assert "must be outside the committed snapshot tree" in capsys.readouterr().err
    assert not snapshot.exists()


@pytest.mark.parametrize(
    "collision",
    (
        "screened_exclusions",
        "run_card_log",
        "summary_cycle_store",
        "summary_cycle_store_wal",
        "summary_cycle_store_shm",
        "summary_cycle_store_journal",
        "cycle_store_sidecar_alias",
        "hardlink_outputs",
        "hardlink_target_store",
        "summary_under_raw_tree",
        "summary_under_snapshot_staging_tree",
        "tree_under_snapshot_staging_tree",
    ),
)
def test_replay_preflight_rejects_writable_output_overlaps_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    collision: str,
) -> None:
    source = _source_snapshot(
        tmp_path / "source-root",
        store_path=tmp_path / "source-root/source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("4515",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    target_digest = sha256_file(target_store)
    if collision == "cycle_store_sidecar_alias":
        Path(f"{target_store}-wal").symlink_to(target_store)
    hardlink_first = tmp_path / "hardlink-first.jsonl"
    hardlink_second = tmp_path / "hardlink-second.jsonl"
    if collision == "hardlink_outputs":
        hardlink_first.write_text("sentinel", encoding="utf-8")
        os.link(hardlink_first, hardlink_second)
    elif collision == "hardlink_target_store":
        os.link(target_store, hardlink_second)
    output_root = tmp_path / "replay"
    snapshot_id = "rejected-overlap"
    command = _replay_command(
        output_root=output_root,
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=assembly_root / "run-cards/assemble-cycle-acquisition.json",
        snapshot_id=snapshot_id,
    )
    shared_file = tmp_path / "shared-output.jsonl"
    collision_flags: dict[str, tuple[str, ...]] = {
        "screened_exclusions": (
            "--screened-cases-output",
            str(shared_file),
            "--exclusions-output",
            str(shared_file),
        ),
        "run_card_log": (
            "--run-card-output",
            str(shared_file),
            "--log-output",
            str(shared_file),
        ),
        "summary_cycle_store": ("--summary-output", str(target_store)),
        "summary_cycle_store_wal": (
            "--summary-output",
            f"{target_store}-wal",
        ),
        "summary_cycle_store_shm": (
            "--summary-output",
            f"{target_store}-shm",
        ),
        "summary_cycle_store_journal": (
            "--summary-output",
            f"{target_store}-journal",
        ),
        "cycle_store_sidecar_alias": (),
        "hardlink_outputs": (
            "--screened-cases-output",
            str(hardlink_first),
            "--exclusions-output",
            str(hardlink_second),
        ),
        "hardlink_target_store": ("--summary-output", str(hardlink_second)),
        "summary_under_raw_tree": (
            "--summary-output",
            str(output_root / "raw-docket-html" / snapshot_id / "summary.json"),
        ),
        "summary_under_snapshot_staging_tree": (
            "--summary-output",
            str(output_root / "snapshots" / "summary.json"),
        ),
        "tree_under_snapshot_staging_tree": (
            "--snapshot-root",
            str(output_root),
        ),
    }
    command.extend(collision_flags[collision])

    assert main(command) == 2
    assert "overlap" in capsys.readouterr().err
    assert sha256_file(target_store) == target_digest
    assert not output_root.exists()
    assert not shared_file.exists()
    if collision == "hardlink_outputs":
        assert hardlink_first.read_text(encoding="utf-8") == "sentinel"


@pytest.mark.parametrize(
    "collision",
    (
        "manifest",
        "screen_run_card",
        "top_assembly_card",
        "raw_html",
        "successes",
        "bundle_root",
        "cycle_store",
        "cycle_store_wal",
        "cycle_store_shm",
        "cycle_store_journal",
        "source_manifest_hardlink",
        "source_raw_hardlink",
    ),
)
def test_replay_preflight_rejects_every_source_output_collision_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    collision: str,
) -> None:
    assembly_source_root = tmp_path / "assembly-source-root"
    source_store = assembly_source_root / "source.sqlite3"
    source = _source_snapshot(
        assembly_source_root,
        store_path=source_store,
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("452",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    supplemental_root = tmp_path / "supplemental-root"
    supplemental = _source_snapshot(
        supplemental_root,
        store_path=supplemental_root / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "supplemental"}),
        batch_id="supplemental",
        successes=("453",),
    )
    supplemental_card = (
        supplemental.parent.parent / "run-cards/screen-firecrawl-dockets.json"
    )
    top_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=top_card,
        snapshot_id="collision-replay",
        supplemental_snapshots=(supplemental,),
    )
    command.extend(
        (
            "--source-snapshot",
            str(supplemental),
            "--expected-source-snapshot-cycle-hash",
            str(verify_snapshot(supplemental)["cycle_hash"]),
            "--source-snapshot-screen-run-card",
            str(supplemental_card),
            "--expected-source-snapshot-screen-run-card-sha256",
            sha256_file(supplemental_card),
            "--source-snapshot-bundle-root",
            str(supplemental_root),
        )
    )
    source_screen_card = (
        source.parent.parent / "run-cards/screen-firecrawl-dockets.json"
    )
    source_card_record = _read_json(source_screen_card)
    raw_html = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
    source_manifest_hardlink = tmp_path / "source-manifest-hardlink.json"
    if collision == "source_manifest_hardlink":
        os.link(source / "manifest.json", source_manifest_hardlink)
    source_raw_hardlink = tmp_path / "source-raw-hardlink.html"
    if collision == "source_raw_hardlink":
        os.link(raw_html, source_raw_hardlink)
    collision_flag, collision_path = {
        "manifest": ("--summary-output", source / "manifest.json"),
        "screen_run_card": ("--run-card-output", source_screen_card),
        "top_assembly_card": ("--log-output", top_card),
        "raw_html": ("--screened-cases-output", raw_html),
        "successes": (
            "--exclusions-output",
            Path(source_card_record["input_paths"][1]),
        ),
        "bundle_root": ("--summary-output", supplemental_root),
        "cycle_store": ("--cycle-store", source_store),
        "cycle_store_wal": ("--cycle-store", Path(f"{source_store}-wal")),
        "cycle_store_shm": ("--cycle-store", Path(f"{source_store}-shm")),
        "cycle_store_journal": (
            "--cycle-store",
            Path(f"{source_store}-journal"),
        ),
        "source_manifest_hardlink": (
            "--summary-output",
            source_manifest_hardlink,
        ),
        "source_raw_hardlink": ("--summary-output", source_raw_hardlink),
    }[collision]
    command.extend((collision_flag, str(collision_path)))
    before_source_digest = _fixture_tree_digest(
        (assembly_source_root, assembly_root, supplemental_root)
    )
    target_store_before = target_store.read_bytes()

    assert main(command) == 2
    assert "overlap" in capsys.readouterr().err
    assert (
        _fixture_tree_digest((assembly_source_root, assembly_root, supplemental_root))
        == before_source_digest
    )
    assert target_store.read_bytes() == target_store_before
    assert not (tmp_path / "replay").exists()


def test_replay_screening_snapshots_audits_kernel_runtime_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "source.sqlite3",
        policy=_cycle_policy(extra={"fixture_generation": "old"}),
        batch_id="source",
        successes=("475",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    def invariant_failure(**_: object) -> None:
        raise RuntimeError("fixture screening reconciliation invariant")

    monkeypatch.setattr(
        cli_module,
        "screen_case_dev_firecrawl_successes",
        invariant_failure,
    )
    output_root = tmp_path / "replay"
    assert (
        main(
            _replay_command(
                output_root=output_root,
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=(
                    assembly_root / "run-cards/assemble-cycle-acquisition.json"
                ),
                snapshot_id="runtime-error-replay",
            )
        )
        == 2
    )
    assert "fixture screening reconciliation invariant" in capsys.readouterr().err
    run_card = _read_json(output_root / "run-cards/replay-screening-snapshots.json")
    assert run_card["status"] == "failed"
    assert run_card["failure_reason"] == ("fixture screening reconciliation invariant")


def test_replay_screening_snapshots_help_states_no_provider_semantics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "replay-screening-snapshots", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "never contacts a provider" in output
    assert "--expected-source-assembly-sha256" in output
    assert "--expected-source-closure-sha256" in output
    assert "--expected-target-cycle-hash" in output
    assert "--source-snapshot" in output
    assert "--expected-source-snapshot-cycle-hash" in output
    assert "--source-snapshot-screen-run-card" in output
    assert "--expected-source-snapshot-screen-run-card-sha256" in output
    assert "--source-snapshot-bundle-root" in output
    assert "--expected-legacy-screen-inputs-sha256" in output


def test_transport_enrichment_accepts_recap_upgrade_and_ui_only_text_changes() -> None:
    old_document = CourtListenerWebDocument(
        kind="Main Document",
        description="Motion to Dismiss",
        href="https://ecf.nysd.uscourts.gov/doc1/12719999999",
        action_label="Buy on PACER",
        pacer_only=True,
    )
    new_document = CourtListenerWebDocument(
        kind="Main Document",
        description="Motion to Dismiss",
        href="https://storage.courtlistener.com/recap/gov.uscourts.nysd.999999.5.0.pdf",
        action_label="Download PDF",
        pacer_only=False,
    )
    newly_surfaced_attachment = CourtListenerWebDocument(
        kind="Attachment 1",
        description="Exhibit A",
        href="https://storage.courtlistener.com/recap/gov.uscourts.nysd.999999.5.1.pdf",
        action_label="Download PDF",
        pacer_only=False,
    )
    older = CourtListenerWebDocketEntry(
        row_id="entry-5",
        entry_number="5",
        filed_at="February 2, 2026",
        text="MOTION to Dismiss (Attachments: (1) Exhibit A) Main Document",
        documents=(old_document,),
        narrative_text="MOTION to Dismiss (Attachments: (1) Exhibit A)",
    )
    newer = CourtListenerWebDocketEntry(
        row_id="entry-5",
        entry_number="5",
        filed_at="February 2, 2026",
        text=(
            "MOTION to Dismiss (Entered: 02/02/2026) "
            "(Attachments: # 1 Exhibit A) Main Document Attachment 1"
        ),
        documents=(new_document, newly_surfaced_attachment),
        narrative_text=(
            "MOTION to Dismiss (Entered: 02/02/2026) (Attachments: # 1 Exhibit A)"
        ),
    )

    enrichment = _verify_entry_transport_enrichment(older, newer)

    assert enrichment is not None
    assert enrichment["row_id"] == "entry-5"
    [transport_change] = enrichment["document_transport_changes"]
    assert transport_change["old_transport"]["pacer_only"] is True
    assert transport_change["new_transport"]["freely_available"] is True


def test_source_replay_commitment_is_independent_of_source_argument_order(
    tmp_path: Path,
) -> None:
    def source(snapshot_id: str, digest_character: str) -> ReplaySourceSnapshot:
        return ReplaySourceSnapshot(
            path=tmp_path / snapshot_id,
            manifest={
                "snapshot_id": snapshot_id,
                "cycle_hash": digest_character * 64,
                "batch_digest": digest_character * 64,
            },
            manifest_sha256=digest_character * 64,
            screen_run_card=tmp_path / snapshot_id / "screen.json",
            screen_run_card_sha256=digest_character * 64,
            input_paths=(),
            bundle_root=None,
        )

    first = source("z-source", "b")
    second = source("a-source", "a")

    def bundle(sources: tuple[ReplaySourceSnapshot, ...]) -> SnapshotReplayBundle:
        return SnapshotReplayBundle(
            successes=(),
            exclusions=(),
            sources=sources,
            source_assembly_run_card=tmp_path / "assembly.json",
            source_assembly_sha256="c" * 64,
            source_assembly_run_cards=(tmp_path / "assembly.json",),
            source_closure_sha256="d" * 64,
            legacy_screen_input_count=0,
            legacy_screen_inputs_sha256=None,
            refresh_supersessions=(),
        )

    forward = source_replay_commitment(bundle((first, second)))
    reverse = source_replay_commitment(bundle((second, first)))

    assert forward == reverse
    assert [
        source_record["snapshot_id"] for source_record in forward["source_snapshots"]
    ] == ["a-source", "z-source"]


@pytest.mark.parametrize(
    "mutation",
    (
        "narrative",
        "filed_at",
        "description",
        "removed_document",
        "document_kind_literal",
        "count_number",
    ),
)
def test_transport_enrichment_rejects_substantive_or_destructive_changes(
    mutation: str,
) -> None:
    old_document = CourtListenerWebDocument(
        kind="Main Document",
        description="Motion to Dismiss",
        href="https://ecf.nysd.uscourts.gov/doc1/12719999999",
        action_label="Buy on PACER",
        pacer_only=True,
    )
    new_document = CourtListenerWebDocument(
        kind="Main Document",
        description=(
            "Amended Motion to Dismiss"
            if mutation == "description"
            else "Motion to Dismiss"
        ),
        href="https://storage.courtlistener.com/recap/gov.uscourts.nysd.999999.5.0.pdf",
        action_label="Download PDF",
        pacer_only=False,
    )
    older = CourtListenerWebDocketEntry(
        row_id="entry-5",
        entry_number="5",
        filed_at="February 2, 2026",
        text=(
            "MOTION to Dismiss Main Document reason A"
            if mutation == "document_kind_literal"
            else (
                "ORDER dismissing Count # 1 Main Document"
                if mutation == "count_number"
                else "MOTION to Dismiss Main Document"
            )
        ),
        documents=(old_document,),
        narrative_text=(
            None
            if mutation in {"document_kind_literal", "count_number"}
            else "MOTION to Dismiss"
        ),
    )
    newer = CourtListenerWebDocketEntry(
        row_id="entry-5",
        entry_number="5",
        filed_at=("February 3, 2026" if mutation == "filed_at" else "February 2, 2026"),
        text=(
            "MOTION to Dismiss Main Document reason B"
            if mutation == "document_kind_literal"
            else (
                "ORDER dismissing Count (1) Main Document"
                if mutation == "count_number"
                else (
                    "MOTION to Dismiss amended Main Document"
                    if mutation == "narrative"
                    else "MOTION to Dismiss Main Document"
                )
            )
        ),
        documents=() if mutation == "removed_document" else (new_document,),
        narrative_text=(
            None
            if mutation in {"document_kind_literal", "count_number"}
            else (
                "MOTION to Dismiss amended"
                if mutation == "narrative"
                else "MOTION to Dismiss"
            )
        ),
    )

    with pytest.raises(SnapshotReplayError):
        _verify_entry_transport_enrichment(older, newer)


def _source_snapshot(
    tmp_path: Path,
    *,
    store_path: Path,
    policy: dict[str, object],
    batch_id: str,
    successes: tuple[str, ...],
    fetch_exclusions: tuple[str, ...] = (),
    decision_text: str = "ORDER granting Motion to Dismiss",
    candidate_ids: dict[str, str] | None = None,
    retrieved_at: str = "2026-07-14T12:00:00+00:00",
    raw_html_path: str = "ignored",
    case_name: str | None = None,
    appended_entry_text: str | None = None,
    source_slug: str = "fixture",
    court_id: str = "nysd",
    docket_number: str | None = None,
    pacer_case_id: str | None = None,
    provisional: bool = False,
) -> Path:
    batch_root = tmp_path / batch_id
    raw_dir = batch_root / "raw-docket-html"
    raw_dir.mkdir(parents=True)
    success_records: list[dict[str, object]] = []
    hits: list[DiscoveryHit] = []
    for docket_id in successes:
        case_id = (candidate_ids or {}).get(docket_id, f"case-dev-{docket_id}")
        raw_html = _docket_html(
            docket_id=docket_id,
            decision_text=decision_text,
            appended_entry_text=appended_entry_text,
        )
        raw_path = raw_dir / f"{docket_id}.html"
        raw_path.write_text(raw_html, encoding="utf-8")
        record = _success_record(
            docket_id,
            raw_html,
            case_id=case_id,
            retrieved_at=retrieved_at,
            raw_html_path=raw_html_path,
            case_name=case_name,
            source_slug=source_slug,
            court_id=court_id,
            docket_number=docket_number,
            pacer_case_id=pacer_case_id,
        )
        success_records.append(record)
        hits.append(
            DiscoveryHit(
                provider_hit_id=f"success-{docket_id}",
                candidate_id=case_id,
                payload={"case_id": case_id},
            )
        )
    exclusion_records: list[dict[str, object]] = []
    for docket_id in fetch_exclusions:
        case_id = f"case-dev-{docket_id}"
        hits.append(
            DiscoveryHit(
                provider_hit_id=f"excluded-{docket_id}",
                candidate_id=case_id,
                payload={"case_id": case_id},
            )
        )
        exclusion_records.append(
            {
                "case_id": case_id,
                "candidate_id": case_id,
                "reason": "decision_before_release_anchor",
                "primary_exclusion_reason": "decision_before_release_anchor",
                "stage": "eligibility",
            }
        )
    successes_path = batch_root / "firecrawl-docket-successes.jsonl"
    exclusions_path = batch_root / "firecrawl-docket-exclusions.jsonl"
    _write_jsonl(successes_path, success_records)
    _write_jsonl(exclusions_path, exclusion_records)
    batch_config: dict[str, object] = {"fixture_batch": batch_id}
    if provisional:
        source_count = len(success_records) + len(exclusion_records) + 1
        batch_config.update(
            {
                "provisional_frontier": True,
                "final_cohort_eligible": False,
                "full_source_terminal": False,
                "source_candidate_count": source_count,
                "source_candidate_set_sha256": "1" * 64,
                "source_projection_sha256": "2" * 64,
                "progress_config_sha256": "3" * 64,
                "progress_sha256": "4" * 64,
                "success_count": len(success_records),
                "terminal_exclusion_count": len(exclusion_records),
                "pending_count": 1,
                "success_candidate_set_sha256": "5" * 64,
                "terminal_excluded_candidate_set_sha256": "6" * 64,
                "pending_candidate_set_sha256": "7" * 64,
            }
        )
        from legalforecast.ingestion.budgeted_docket_acquisition import (
            provisional_lineage_flags,
        )

        lineage = provisional_lineage_flags(batch_config)
        success_records = [{**record, **lineage} for record in success_records]
        exclusion_records = [{**record, **lineage} for record in exclusion_records]
        _write_jsonl(successes_path, success_records)
        _write_jsonl(exclusions_path, exclusion_records)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(policy)
        store.ensure_batch(batch_id, batch_config)
        store.ensure_terms(batch_id, ("fixture",))
        store.commit_search_page(
            batch_id,
            "fixture",
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    snapshot_id = f"{batch_id}-complete"
    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--output-root",
                str(batch_root / "screening"),
                "--cycle-store",
                str(store_path),
                "--batch-id",
                batch_id,
                "--successes",
                str(successes_path),
                "--fetch-exclusions",
                str(exclusions_path),
                "--raw-html-dir",
                str(raw_dir),
                "--decision-filed-on-or-after",
                ANCHOR,
                "--snapshot-id",
                snapshot_id,
                "--execute",
            ]
        )
        == 0
    )
    return batch_root / "screening/snapshots" / snapshot_id


def _replay_command(
    *,
    output_root: Path,
    target_store: Path,
    target_cycle_hash: str,
    source_cycle_hash: str,
    assembly_run_card: Path,
    snapshot_id: str,
    expected_assembly_sha256: str | None = None,
    supplemental_snapshots: tuple[Path, ...] = (),
) -> list[str]:
    return [
        "acquisition",
        "replay-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "superseding-replay",
        "--source-assembly-run-card",
        str(assembly_run_card),
        "--expected-source-assembly-sha256",
        expected_assembly_sha256 or sha256_file(assembly_run_card),
        "--expected-source-closure-sha256",
        _fixture_source_closure_sha256(
            assembly_run_card,
            supplemental_snapshots=supplemental_snapshots,
        ),
        "--expected-source-cycle-hash",
        source_cycle_hash,
        "--expected-target-cycle-hash",
        target_cycle_hash,
        "--decision-filed-on-or-after",
        ANCHOR,
        "--snapshot-id",
        snapshot_id,
        "--execute",
    ]


def _fixture_source_closure_sha256(
    assembly_run_card: Path, *, supplemental_snapshots: tuple[Path, ...] = ()
) -> str:
    run_card_hashes: list[str] = []
    manifest_hashes: list[str] = []
    seen_cards: set[Path] = set()
    seen_roots: set[Path] = set()

    def visit(card_path: Path) -> None:
        card_path = card_path.resolve()
        if card_path in seen_cards:
            return
        seen_cards.add(card_path)
        run_card_hashes.append(sha256_file(card_path))
        card = _read_json(card_path)
        for raw_root in card["input_paths"]:
            root = Path(raw_root).resolve()
            if root in seen_roots:
                continue
            seen_roots.add(root)
            nested = root / "run-cards/assemble-cycle-acquisition.json"
            manifest = root / "manifest.json"
            if nested.is_file():
                visit(nested)
            elif manifest.is_file():
                manifest_hashes.append(sha256_file(manifest))

    visit(assembly_run_card)
    for snapshot in supplemental_snapshots:
        resolved = snapshot.resolve()
        if resolved not in seen_roots:
            seen_roots.add(resolved)
            manifest_hashes.append(sha256_file(resolved / "manifest.json"))
    payload = {
        "schema_version": "legalforecast.replay_source_closure.v1",
        "assembly_run_card_sha256": sorted(run_card_hashes),
        "source_snapshot_manifest_sha256": sorted(manifest_hashes),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _cycle_policy(*, extra: dict[str, object] | None = None) -> dict[str, object]:
    package_root = Path(__file__).parents[1] / "legalforecast"
    sources = {
        "mtd_acquisition_screen": package_root / "ingestion/mtd_acquisition_screen.py",
        "courtlistener_acquisition": package_root
        / "ingestion/courtlistener_acquisition.py",
        "restricted_material": package_root / "ingestion/restricted_material.py",
        "contamination_filters": package_root / "selection/contamination_filters.py",
        "motion_linkage": package_root / "selection/motion_linkage.py",
    }
    policy: dict[str, object] = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": date(2026, 6, 30).isoformat(),
        "screening_source_sha256": {
            name: sha256_file(path) for name, path in sorted(sources.items())
        },
    }
    if extra:
        policy.update(extra)
    return policy


def _success_record(
    docket_id: str,
    raw_html: str,
    *,
    case_id: str | None = None,
    retrieved_at: str = "2026-07-14T12:00:00+00:00",
    raw_html_path: str = "ignored",
    case_name: str | None = None,
    source_slug: str = "fixture",
    court_id: str = "nysd",
    docket_number: str | None = None,
    pacer_case_id: str | None = None,
) -> dict[str, object]:
    raw_bytes = raw_html.encode()
    case_id = case_id or f"case-dev-{docket_id}"
    return {
        "case_id": case_id,
        "source_url": f"https://www.courtlistener.com/docket/{docket_id}/{source_slug}/",
        "docket_id": docket_id,
        "raw_html_path": raw_html_path,
        "raw_html_sha256": f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
        "raw_html_bytes": len(raw_bytes),
        "retrieved_at": retrieved_at,
        "pagination_complete_for_anchor_window": True,
        "case_metadata": {
            "case_id": case_id,
            "court_id": court_id,
            "docket_number": docket_number or f"1:26-cv-{int(docket_id):05d}",
            "case_name": case_name or f"Fixture {docket_id} v. Example",
            "source_url": f"https://www.courtlistener.com/docket/{docket_id}/{source_slug}/",
            "pacer_case_id": pacer_case_id,
        },
    }


def _docket_html(
    *, docket_id: str, decision_text: str, appended_entry_text: str | None = None
) -> str:
    def entry(number: int, filed_at: str, text: str, description: str) -> str:
        return (
            f'<div class="row" id="entry-{number}">'
            f'<div class="col-xs-1">{number}</div>'
            f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
            f'<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>Main Document</div>'
            f"<div>{description}</div>"
            f'<a href="https://storage.courtlistener.com/{docket_id}-{number}.pdf">'
            f"Download PDF</a></div></div></div>"
        )

    appended_entry = (
        entry(17, "July 2, 2026", appended_entry_text, "Notice")
        if appended_entry_text is not None
        else ""
    )
    return (
        f"<html><head><title>Fixture {docket_id} v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + entry(1, "January 2, 2026", "COMPLAINT filed", "Complaint")
        + entry(5, "February 2, 2026", "MOTION to Dismiss", "Motion to Dismiss")
        + entry(16, "July 1, 2026", decision_text, "Order on Motion to Dismiss")
        + appended_entry
        + "</div></body></html>"
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _fixture_tree_digest(roots: tuple[Path, ...]) -> str:
    rows: list[tuple[str, str]] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rows.append(
                (
                    str(path.relative_to(root)),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cohort_snapshot_recovery import (
    PublishedSnapshotRecoveryError,
    prepare_disposable_store_for_recovered_snapshot,
    recover_published_snapshot_from_store_commitment,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)

_POLICY = {
    "anchor": "2026-06-30T00:00:00Z",
    "query_terms": ["motion to dismiss"],
    "screen_hash": "screen-v1",
    "schema": 1,
}
_SNAPSHOT_ID = "published-terminal-snapshot-v1"


@dataclass(frozen=True, slots=True)
class _Fixture:
    store: Path
    snapshot_id: str
    manifest_sha256: str
    cycle_hash: str
    original_files: dict[str, bytes]


def _hit(candidate_id: str) -> dict[str, object]:
    return {
        "provider_hit_id": f"hit-{candidate_id}",
        "candidate_id": candidate_id,
        "payload": {"candidate_id": candidate_id},
    }


def _fixture(tmp_path: Path) -> _Fixture:
    store_path = tmp_path / "store" / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle(_POLICY)
        store.ensure_batch("batch-001", {"page_size": 50})
        store.ensure_terms("batch-001", ["term"])
        store.commit_search_page(
            "batch-001",
            "term",
            None,
            [_hit("candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"entry_id": "1"},
        )
        snapshot = store.export_snapshot(
            tmp_path / "historical",
            snapshot_id=_SNAPSHOT_ID,
            batch_id="batch-001",
            complete=True,
            use_batch_terminal_observations=True,
        )
        original_files = {path.name: path.read_bytes() for path in snapshot.iterdir()}
        manifest_sha256 = hashlib.sha256(original_files["manifest.json"]).hexdigest()

        # A later append-only observation for the same candidate extends the
        # current projection without changing batch-001 terminal payloads.
        store.ensure_batch("batch-002", {"page_size": 50})
        store.ensure_terms("batch-002", ["later-term"])
        store.commit_search_page(
            "batch-002",
            "later-term",
            None,
            [_hit("candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-002",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"entry_id": "later"},
        )

    shutil.rmtree(snapshot)
    return _Fixture(
        store=store_path,
        snapshot_id=_SNAPSHOT_ID,
        manifest_sha256=manifest_sha256,
        cycle_hash=cycle_hash,
        original_files=original_files,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recover(fixture: _Fixture, output: Path) -> Path:
    return recover_published_snapshot_from_store_commitment(
        cycle_store=fixture.store,
        expected_store_sha256=_sha256(fixture.store),
        snapshot_id=fixture.snapshot_id,
        expected_manifest_sha256=fixture.manifest_sha256,
        output_root=output,
    ).path


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir()}


def _mutate_manifest(
    fixture: _Fixture,
    mutation: Callable[[dict[str, object]], None],
) -> str:
    connection = sqlite3.connect(fixture.store)
    try:
        row = connection.execute(
            "SELECT manifest_json FROM snapshots WHERE snapshot_id = ?",
            (fixture.snapshot_id,),
        ).fetchone()
        assert row is not None
        manifest = json.loads(str(row[0]))
        mutation(manifest)
        manifest_json = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        connection.execute(
            "UPDATE snapshots SET manifest_json = ? WHERE snapshot_id = ?",
            (manifest_json, fixture.snapshot_id),
        )
        connection.commit()
    finally:
        connection.close()
    return hashlib.sha256(f"{manifest_json}\n".encode()).hexdigest()


def test_recovery_republishes_exact_committed_bytes_without_new_timestamp(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = fixture.store.read_bytes()
    output = tmp_path / "private" / "recovered-snapshot"
    output.parent.mkdir()

    result = recover_published_snapshot_from_store_commitment(
        cycle_store=fixture.store,
        expected_store_sha256=hashlib.sha256(source_before).hexdigest(),
        snapshot_id=fixture.snapshot_id,
        expected_manifest_sha256=fixture.manifest_sha256,
        output_root=output,
    )

    assert result.path == output
    assert result.snapshot_id == fixture.snapshot_id
    assert result.manifest_sha256 == fixture.manifest_sha256
    assert result.store_sha256 == hashlib.sha256(source_before).hexdigest()
    assert result.recovered_observation_row_count == 1
    assert _snapshot_files(output) == fixture.original_files
    manifest = verify_snapshot(
        output,
        expected_cycle_hash=fixture.cycle_hash,
        require_complete=True,
    )
    assert (
        manifest["created_at"]
        == json.loads(fixture.original_files["manifest.json"])["created_at"]
    )
    assert fixture.store.read_bytes() == source_before


def test_recovery_cli_publishes_and_reports_exact_commitments(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "private" / "recovered-snapshot"
    output.parent.mkdir()

    assert (
        main(
            [
                "acquisition",
                "recover-published-snapshot-from-store-commitment",
                "--cycle-store",
                str(fixture.store),
                "--expected-store-sha256",
                _sha256(fixture.store),
                "--snapshot-id",
                fixture.snapshot_id,
                "--expected-manifest-sha256",
                fixture.manifest_sha256,
                "--output-root",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["output_root"] == str(output)
    assert report["snapshot_id"] == fixture.snapshot_id
    assert report["manifest_sha256"] == fixture.manifest_sha256
    assert report["recovered_observation_row_count"] == 1
    assert _snapshot_files(output) == fixture.original_files


def test_disposable_store_copy_rebinds_only_copy_and_is_export_ready(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    source_before = fixture.store.read_bytes()
    recovered = tmp_path / "private" / "recovered"
    recovered.parent.mkdir()
    _recover(fixture, recovered)
    copy_root = tmp_path / "private" / "store-copy"

    assert (
        main(
            [
                "acquisition",
                "prepare-disposable-snapshot-recovery-store",
                "--cycle-store",
                str(fixture.store),
                "--expected-store-sha256",
                hashlib.sha256(source_before).hexdigest(),
                "--snapshot-id",
                fixture.snapshot_id,
                "--recovered-snapshot-root",
                str(recovered),
                "--expected-manifest-sha256",
                fixture.manifest_sha256,
                "--output-root",
                str(copy_root),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    copy_store = Path(report["cycle_store"])
    assert copy_store == copy_root / "cycle-acquisition.sqlite3"
    assert set(path.name for path in copy_root.iterdir()) == {
        "cycle-acquisition.sqlite3",
        "cycle-acquisition.sqlite3.lock",
    }
    assert fixture.store.read_bytes() == source_before
    assert (
        hashlib.sha256(copy_store.read_bytes()).hexdigest()
        == report["disposable_store_sha256"]
    )
    with CycleAcquisitionStore(copy_store, read_only=True) as store:
        snapshots = store.published_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0].snapshot_id == fixture.snapshot_id
        assert snapshots[0].path == recovered
        verify_snapshot(snapshots[0].path)


def test_disposable_store_copy_is_create_only_and_preserves_source(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = fixture.store.read_bytes()
    recovered = tmp_path / "private" / "recovered"
    recovered.parent.mkdir()
    _recover(fixture, recovered)
    output = tmp_path / "private" / "occupied"
    output.mkdir()
    marker = output / "marker"
    marker.write_bytes(b"unchanged")

    with pytest.raises(PublishedSnapshotRecoveryError, match="already exists"):
        prepare_disposable_store_for_recovered_snapshot(
            cycle_store=fixture.store,
            expected_store_sha256=hashlib.sha256(source_before).hexdigest(),
            snapshot_id=fixture.snapshot_id,
            recovered_snapshot_root=recovered,
            expected_manifest_sha256=fixture.manifest_sha256,
            output_root=output,
        )

    assert marker.read_bytes() == b"unchanged"
    assert fixture.store.read_bytes() == source_before


def test_recovery_rejects_wrong_external_manifest_hash_before_output(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "output"

    with pytest.raises(PublishedSnapshotRecoveryError, match="manifest SHA-256"):
        recover_published_snapshot_from_store_commitment(
            cycle_store=fixture.store,
            expected_store_sha256=_sha256(fixture.store),
            snapshot_id=fixture.snapshot_id,
            expected_manifest_sha256="0" * 64,
            output_root=output,
        )

    assert not output.exists()


@pytest.mark.parametrize("field", ["row_count", "sha256", "byte_count"])
def test_recovery_rejects_wrong_committed_observation_prefix(
    tmp_path: Path,
    field: str,
) -> None:
    fixture = _fixture(tmp_path)

    def mutate(manifest: dict[str, object]) -> None:
        files = cast(dict[str, object], manifest["files"])
        commitment = cast(dict[str, object], files["observations.jsonl"])
        if field == "sha256":
            commitment[field] = "0" * 64
        else:
            current = commitment[field]
            assert isinstance(current, int)
            commitment[field] = current + 1

    expected_manifest_sha256 = _mutate_manifest(fixture, mutate)
    output = tmp_path / "output"

    with pytest.raises(
        PublishedSnapshotRecoveryError,
        match=r"committed payload|observation prefix",
    ):
        recover_published_snapshot_from_store_commitment(
            cycle_store=fixture.store,
            expected_store_sha256=_sha256(fixture.store),
            snapshot_id=fixture.snapshot_id,
            expected_manifest_sha256=expected_manifest_sha256,
            output_root=output,
        )

    assert not output.exists()


def test_recovery_rejects_manifest_cycle_mismatch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    manifest_sha256 = _mutate_manifest(
        fixture, lambda manifest: manifest.__setitem__("cycle_hash", "0" * 64)
    )

    with pytest.raises(PublishedSnapshotRecoveryError, match="cycle hash"):
        recover_published_snapshot_from_store_commitment(
            cycle_store=fixture.store,
            expected_store_sha256=_sha256(fixture.store),
            snapshot_id=fixture.snapshot_id,
            expected_manifest_sha256=manifest_sha256,
            output_root=tmp_path / "output",
        )


def test_recovery_rejects_store_policy_hash_mismatch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    connection = sqlite3.connect(fixture.store)
    try:
        connection.execute(
            "UPDATE cycle_identity SET policy_json = ? WHERE singleton = 1",
            ('{"tampered":true}',),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(PublishedSnapshotRecoveryError, match="policy hash"):
        recover_published_snapshot_from_store_commitment(
            cycle_store=fixture.store,
            expected_store_sha256=_sha256(fixture.store),
            snapshot_id=fixture.snapshot_id,
            expected_manifest_sha256=fixture.manifest_sha256,
            output_root=tmp_path / "output",
        )


def test_recovery_rejects_invalid_registered_snapshot_path(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    connection = sqlite3.connect(fixture.store)
    try:
        connection.execute(
            "UPDATE snapshots SET path = ? WHERE snapshot_id = ?",
            ("relative/wrong-name", fixture.snapshot_id),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(PublishedSnapshotRecoveryError, match="registered path"):
        recover_published_snapshot_from_store_commitment(
            cycle_store=fixture.store,
            expected_store_sha256=_sha256(fixture.store),
            snapshot_id=fixture.snapshot_id,
            expected_manifest_sha256=fixture.manifest_sha256,
            output_root=tmp_path / "output",
        )


def test_recovery_is_create_only(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "marker"
    marker.write_bytes(b"unchanged")

    with pytest.raises(PublishedSnapshotRecoveryError, match="already exists"):
        _recover(fixture, output)

    assert marker.read_bytes() == b"unchanged"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_recovery_rejects_non_unique_or_nonregular_store_input(
    tmp_path: Path,
    kind: str,
) -> None:
    fixture = _fixture(tmp_path)
    alias = tmp_path / "cycle-alias.sqlite3"
    if kind == "symlink":
        alias.symlink_to(fixture.store)
    elif kind == "hardlink":
        os.link(fixture.store, alias)
    else:
        os.mkfifo(alias)

    try:
        with pytest.raises(
            PublishedSnapshotRecoveryError,
            match=r"singly linked regular non-symlink|cycle store",
        ):
            recover_published_snapshot_from_store_commitment(
                cycle_store=alias,
                expected_store_sha256=_sha256(fixture.store),
                snapshot_id=fixture.snapshot_id,
                expected_manifest_sha256=fixture.manifest_sha256,
                output_root=tmp_path / "output",
            )
    finally:
        alias.unlink(missing_ok=True)


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_recovery_rejects_occupied_special_output(
    tmp_path: Path,
    kind: str,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "output"
    if kind == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        output.symlink_to(outside, target_is_directory=True)
    else:
        os.mkfifo(output)

    with pytest.raises(PublishedSnapshotRecoveryError, match="already exists"):
        _recover(fixture, output)


def test_recovery_rejects_symlinked_output_ancestor(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublishedSnapshotRecoveryError, match="without symlinks"):
        _recover(fixture, linked_parent / "output")

    assert list(outside.iterdir()) == []


def test_recovery_detects_output_ancestor_swap_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    parent = tmp_path / "private"
    parent.mkdir()
    output = parent / "output"
    moved_parent = tmp_path / "private-moved"

    from legalforecast.ingestion import cohort_snapshot_recovery as recovery_module

    original_rename = recovery_module._rename_noreplace_at  # pyright: ignore[reportPrivateUsage]

    def swap_then_rename(
        parent_fd: int,
        source_name: str,
        destination_name: str,
    ) -> None:
        os.rename(parent, moved_parent)
        parent.mkdir()
        original_rename(parent_fd, source_name, destination_name)

    monkeypatch.setattr(recovery_module, "_rename_noreplace_at", swap_then_rename)

    with pytest.raises(PublishedSnapshotRecoveryError, match="ancestor changed"):
        _recover(fixture, output)

    assert not output.exists()
    assert list(parent.iterdir()) == []
    assert not (moved_parent / "output").exists()


def test_recovery_rejects_output_overlapping_store_or_registered_path(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    for output in (fixture.store, fixture.store.parent):
        with pytest.raises(PublishedSnapshotRecoveryError, match="overlaps"):
            recover_published_snapshot_from_store_commitment(
                cycle_store=fixture.store,
                expected_store_sha256=_sha256(fixture.store),
                snapshot_id=fixture.snapshot_id,
                expected_manifest_sha256=fixture.manifest_sha256,
                output_root=output,
            )

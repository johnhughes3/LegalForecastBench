from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.snapshot_quarantine import (
    SnapshotQuarantineError,
    quarantine_orphan_snapshot,
)


@dataclass(frozen=True, slots=True)
class _Fixture:
    store: Path
    canonical: Path
    orphan: Path
    quarantine: Path
    receipt: Path
    snapshot_id: str
    canonical_manifest_sha256: str
    orphan_manifest_sha256: str


def test_quarantine_dry_run_then_execute_preserves_store_and_canonical_snapshot(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    database_before = fixture.store.read_bytes()
    canonical_before = _snapshot_files(fixture.canonical)
    with CycleAcquisitionStore(fixture.store) as store:
        observation_ids_before = tuple(
            row.observation_id for row in store.observations("candidate-1")
        )

    dry_run = _quarantine(fixture, execute=False)

    assert dry_run["status"] == "dry_run_verified"
    assert fixture.orphan.is_dir()
    assert not Path(str(dry_run["quarantine_target_path"])).exists()
    assert fixture.store.read_bytes() == database_before
    assert _snapshot_files(fixture.canonical) == canonical_before

    completed = _quarantine(fixture, execute=True)

    target = Path(str(completed["quarantine_target_path"]))
    assert completed["status"] == "quarantined"
    assert completed["database_mutated"] is False
    assert completed["observations_preserved"] is True
    assert not fixture.orphan.exists()
    assert target.is_dir()
    assert verify_snapshot(target)["snapshot_id"] == fixture.snapshot_id
    assert fixture.store.read_bytes() == database_before
    assert _snapshot_files(fixture.canonical) == canonical_before
    with CycleAcquisitionStore(fixture.store) as store:
        assert (
            tuple(row.observation_id for row in store.observations("candidate-1"))
            == observation_ids_before
        )
    receipt = json.loads(fixture.receipt.read_text())
    assert receipt["status"] == "quarantined"
    assert receipt["orphan_snapshots_path_reference_count"] == 0


def test_quarantine_rejects_registered_path_without_receipt_or_move(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(SnapshotQuarantineError, match="registered"):
        quarantine_orphan_snapshot(
            cycle_store=fixture.store,
            orphan_snapshot=fixture.canonical,
            quarantine_root=fixture.quarantine,
            receipt_output=fixture.receipt,
            expected_snapshot_id=fixture.snapshot_id,
            expected_orphan_manifest_sha256=fixture.canonical_manifest_sha256,
            expected_canonical_manifest_sha256=fixture.canonical_manifest_sha256,
            execute=True,
        )

    assert fixture.canonical.is_dir()
    assert not fixture.receipt.exists()
    assert list(fixture.quarantine.iterdir()) == []


def test_quarantine_rejects_wrong_or_corrupt_orphan_commitment(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(SnapshotQuarantineError, match="does not match"):
        quarantine_orphan_snapshot(
            cycle_store=fixture.store,
            orphan_snapshot=fixture.orphan,
            quarantine_root=fixture.quarantine,
            receipt_output=fixture.receipt,
            expected_snapshot_id=fixture.snapshot_id,
            expected_orphan_manifest_sha256="0" * 64,
            expected_canonical_manifest_sha256=fixture.canonical_manifest_sha256,
            execute=True,
        )

    assert fixture.orphan.is_dir()
    assert not fixture.receipt.exists()


def test_quarantine_rejects_orphan_file_corruption_with_pinned_manifest(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    (fixture.orphan / "candidates.jsonl").write_text("corrupt\n", encoding="utf-8")

    with pytest.raises(SnapshotQuarantineError, match="commitment mismatch"):
        _quarantine(fixture, execute=True)

    assert fixture.orphan.is_dir()
    assert not fixture.receipt.exists()
    assert list(fixture.quarantine.iterdir()) == []


def test_quarantine_rejects_canonical_disk_manifest_that_differs_from_database(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    manifest_path = fixture.canonical / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["created_at"] = "2026-07-13T23:59:59Z"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotQuarantineError, match="database manifest"):
        quarantine_orphan_snapshot(
            cycle_store=fixture.store,
            orphan_snapshot=fixture.orphan,
            quarantine_root=fixture.quarantine,
            receipt_output=fixture.receipt,
            expected_snapshot_id=fixture.snapshot_id,
            expected_orphan_manifest_sha256=fixture.orphan_manifest_sha256,
            expected_canonical_manifest_sha256=_sha256(manifest_path),
            execute=True,
        )

    assert fixture.orphan.is_dir()
    assert not fixture.receipt.exists()
    assert list(fixture.quarantine.iterdir()) == []


def test_quarantine_rejects_active_cycle_store_writer(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    with CycleAcquisitionStore(fixture.store):
        with pytest.raises(SnapshotQuarantineError, match="active"):
            _quarantine(fixture, execute=True)

    assert fixture.orphan.is_dir()
    assert not fixture.receipt.exists()


def test_quarantine_rejects_receipt_or_quarantine_inside_store_root(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    inside_quarantine = fixture.store.parent / "inside-quarantine"
    inside_quarantine.mkdir()

    with pytest.raises(SnapshotQuarantineError, match="outside"):
        quarantine_orphan_snapshot(
            cycle_store=fixture.store,
            orphan_snapshot=fixture.orphan,
            quarantine_root=inside_quarantine,
            receipt_output=fixture.receipt,
            expected_snapshot_id=fixture.snapshot_id,
            expected_orphan_manifest_sha256=fixture.orphan_manifest_sha256,
            expected_canonical_manifest_sha256=fixture.canonical_manifest_sha256,
            execute=False,
        )

    inside_receipt = fixture.store.parent / "receipt.json"
    with pytest.raises(SnapshotQuarantineError, match="outside"):
        quarantine_orphan_snapshot(
            cycle_store=fixture.store,
            orphan_snapshot=fixture.orphan,
            quarantine_root=fixture.quarantine,
            receipt_output=inside_receipt,
            expected_snapshot_id=fixture.snapshot_id,
            expected_orphan_manifest_sha256=fixture.orphan_manifest_sha256,
            expected_canonical_manifest_sha256=fixture.canonical_manifest_sha256,
            execute=False,
        )

    assert fixture.orphan.is_dir()
    assert not fixture.receipt.exists()


def test_quarantine_cli_defaults_to_receipt_only_and_help_documents_execute(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    command = [
        "acquisition",
        "quarantine-orphan-snapshot",
        "--cycle-store",
        str(fixture.store),
        "--orphan-snapshot",
        str(fixture.orphan),
        "--quarantine-root",
        str(fixture.quarantine),
        "--receipt-output",
        str(fixture.receipt),
        "--expected-snapshot-id",
        fixture.snapshot_id,
        "--expected-orphan-manifest-sha256",
        fixture.orphan_manifest_sha256,
        "--expected-canonical-manifest-sha256",
        fixture.canonical_manifest_sha256,
    ]

    assert main(command) == 0
    assert fixture.orphan.is_dir()
    assert json.loads(fixture.receipt.read_text())["status"] == "dry_run_verified"
    with pytest.raises(SystemExit) as raised:
        main(["acquisition", "quarantine-orphan-snapshot", "--help"])
    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert "--execute" in help_text
    assert "Dry runs write" in help_text


def _quarantine(fixture: _Fixture, *, execute: bool) -> dict[str, object]:
    return quarantine_orphan_snapshot(
        cycle_store=fixture.store,
        orphan_snapshot=fixture.orphan,
        quarantine_root=fixture.quarantine,
        receipt_output=fixture.receipt,
        expected_snapshot_id=fixture.snapshot_id,
        expected_orphan_manifest_sha256=fixture.orphan_manifest_sha256,
        expected_canonical_manifest_sha256=fixture.canonical_manifest_sha256,
        execute=execute,
    )


def _fixture(tmp_path: Path) -> _Fixture:
    official = tmp_path / "official"
    store_path = official / "cycle.sqlite3"
    snapshot_id = "snapshot-1"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "legalforecast.cycle_acquisition_policy.v1",
                "eligibility_anchor": "2026-06-30",
                "screening_source_sha256": {"screen": "abc123"},
            }
        )
        store.ensure_batch("batch-1", {"source": "fixture"})
        store.ensure_terms("batch-1", ["motion to dismiss"])
        store.commit_search_page(
            "batch-1",
            "motion to dismiss",
            None,
            [
                {
                    "provider_hit_id": "hit-1",
                    "candidate_id": "candidate-1",
                    "payload": {"id": "candidate-1"},
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-1",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"entry_id": "10"},
        )
        canonical = store.export_snapshot(
            official / "snapshots",
            snapshot_id=snapshot_id,
            batch_id="batch-1",
            complete=True,
        )
    orphan = official / "other-stage" / "snapshots" / snapshot_id
    orphan.parent.mkdir(parents=True)
    shutil.copytree(canonical, orphan)
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    return _Fixture(
        store=store_path,
        canonical=canonical,
        orphan=orphan,
        quarantine=quarantine,
        receipt=receipts / "snapshot-quarantine.json",
        snapshot_id=snapshot_id,
        canonical_manifest_sha256=_sha256(canonical / "manifest.json"),
        orphan_manifest_sha256=_sha256(orphan / "manifest.json"),
    )


def _snapshot_files(path: Path) -> dict[str, bytes]:
    return {
        child.name: child.read_bytes() for child in path.iterdir() if child.is_file()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.snapshot_reconciliation import (
    SnapshotReconciliationError,
    verify_saturated_snapshot_reconciliation,
)
from legalforecast.protocol import sha256_file


def test_verify_saturated_snapshot_reconciliation_accepts_current_snapshot_shape(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)

    result = verify_saturated_snapshot_reconciliation(**paths)

    assert result.accepted_count == 1
    assert result.excluded_count == 1
    assert result.processed_count == 2
    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    assert result.cycle_hash == manifest["cycle_hash"]
    assert result.batch_id == "batch-1"
    assert result.batch_digest == manifest["batch_digest"]
    assert result.snapshot_id == "snapshot-1"
    assert result.manifest_sha256 == sha256_file(paths["manifest_path"])
    assert result.cycle_store_path == str(paths["cycle_store_path"].resolve())
    assert result.to_record()["snapshot_id"] == "snapshot-1"


def test_reconciliation_rejects_partial_hand_authored_manifest(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)
    manifest_path = paths["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        name: manifest["files"][name]
        for name in ("screened-cases.jsonl", "exclusions.jsonl", "summary.json")
    }
    _write_json(manifest_path, manifest)

    with pytest.raises(
        SnapshotReconciliationError,
        match="canonical screening snapshot verification failed: snapshot file "
        "manifest is incomplete",
    ):
        verify_saturated_snapshot_reconciliation(**paths)


def test_reconciliation_rejects_complete_snapshot_not_registered_at_path(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path / "source")
    forged = tmp_path / "forged" / "snapshot-1"
    forged.parent.mkdir()
    shutil.copytree(paths["expected_snapshot_path"], forged)
    forged_paths = {
        **paths,
        "manifest_path": forged / "manifest.json",
        "summary_path": forged / "summary.json",
        "screened_cases_path": forged / "screened-cases.jsonl",
        "exclusions_path": forged / "exclusions.jsonl",
        "expected_snapshot_path": forged,
    }

    with pytest.raises(
        SnapshotReconciliationError,
        match="store registration verification failed",
    ):
        verify_saturated_snapshot_reconciliation(**forged_paths)


def test_reconciliation_rejects_snapshot_not_pinned_by_target_cohort(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)
    paths["expected_manifest_sha256"] = "f" * 64

    with pytest.raises(
        SnapshotReconciliationError,
        match="manifest differs from the authenticated target cohort",
    ):
        verify_saturated_snapshot_reconciliation(**paths)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("complete", "snapshot is not complete"),
        ("saturated", "snapshot discovery is not saturated"),
    ],
)
def test_verify_saturated_snapshot_reconciliation_rejects_nonterminal_snapshot(
    tmp_path: Path,
    field: str,
    message: str,
) -> None:
    paths = _write_snapshot(tmp_path)
    manifest_path = paths["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = False
    _write_json(manifest_path, manifest)

    with pytest.raises(SnapshotReconciliationError, match=message):
        verify_saturated_snapshot_reconciliation(**paths)


def test_verify_saturated_snapshot_reconciliation_rejects_replay_summary_aliases(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)
    summary_path = paths["summary_path"]
    _write_json(
        summary_path,
        {
            "accepted_case_count": 1,
            "batch_id": "batch-1",
            "excluded_case_count": 1,
            "reconciled": True,
            "schema_version": "legalforecast.snapshot_replay_summary.v1",
            "source_candidate_count": 2,
        },
    )
    _rebind_member(paths["manifest_path"], "summary.json", summary_path)

    with pytest.raises(
        SnapshotReconciliationError,
        match="snapshot summary counts do not reconcile",
    ):
        verify_saturated_snapshot_reconciliation(**paths)


def test_verify_saturated_snapshot_reconciliation_rejects_manifest_count_drift(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)
    manifest_path = paths["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["screened-cases.jsonl"]["row_count"] = 2
    _write_json(manifest_path, manifest)

    with pytest.raises(
        SnapshotReconciliationError,
        match=r"snapshot file commitment mismatch: screened-cases\.jsonl",
    ):
        verify_saturated_snapshot_reconciliation(**paths)


def test_verify_saturated_snapshot_reconciliation_rejects_summary_batch_drift(
    tmp_path: Path,
) -> None:
    paths = _write_snapshot(tmp_path)
    summary_path = paths["summary_path"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["batch_id"] = "batch-2"
    _write_json(summary_path, summary)
    _rebind_member(paths["manifest_path"], "summary.json", summary_path)
    paths["expected_manifest_sha256"] = sha256_file(paths["manifest_path"])

    with pytest.raises(
        SnapshotReconciliationError,
        match="summary batch_id does not match manifest",
    ):
        verify_saturated_snapshot_reconciliation(**paths)


def _write_snapshot(tmp_path: Path) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store_path = tmp_path / "store" / "cycle-acquisition.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "anchor": "2026-06-30T00:00:00Z",
                "query_terms": ["motion to dismiss"],
                "screen_hash": "screen-v1",
                "schema": 1,
            }
        )
        store.ensure_batch("batch-1", {"page_size": 2})
        store.ensure_terms("batch-1", ["motion to dismiss"])
        store.commit_search_page(
            "batch-1",
            "motion to dismiss",
            None,
            [
                {
                    "provider_hit_id": "hit-1",
                    "candidate_id": "cand-1",
                    "payload": {"id": "hit-1"},
                },
                {
                    "provider_hit_id": "hit-2",
                    "candidate_id": "cand-2",
                    "payload": {"id": "hit-2"},
                },
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "cand-1",
            batch_id="batch-1",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"candidate": {"docket_id": "cand-1"}},
        )
        store.record_observation(
            "cand-2",
            batch_id="batch-1",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={"reason": "decision_before_release_anchor"},
        )
        snapshot = store.export_snapshot(
            tmp_path / "snapshots",
            snapshot_id="snapshot-1",
            batch_id="batch-1",
            complete=True,
            stage_commitments={"test_source": {"schema_version": "test.v1"}},
        )
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    return {
        "manifest_path": snapshot / "manifest.json",
        "summary_path": snapshot / "summary.json",
        "screened_cases_path": snapshot / "screened-cases.jsonl",
        "exclusions_path": snapshot / "exclusions.jsonl",
        "cycle_store_path": store_path,
        "expected_snapshot_path": snapshot,
        "expected_manifest_sha256": sha256_file(snapshot / "manifest.json"),
        "expected_cycle_hash": str(manifest["cycle_hash"]),
        "expected_batch_digest": str(manifest["batch_digest"]),
    }


def _rebind_member(manifest_path: Path, name: str, path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][name] = _member(path, jsonl=name.endswith(".jsonl"))
    _write_json(manifest_path, manifest)


def _member(path: Path, *, jsonl: bool) -> dict[str, object]:
    return {
        "byte_count": path.stat().st_size,
        "row_count": (
            len(path.read_text(encoding="utf-8").splitlines()) if jsonl else 1
        ),
        "sha256": sha256_file(path),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True) + "\n",
        encoding="utf-8",
    )

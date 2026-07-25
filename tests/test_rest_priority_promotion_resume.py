"""Crash-boundary and drift tests for REST priority-subset promotion resume."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast

import legalforecast.ingestion.rest_priority_subset_promotion as promotion_module
import pytest
from legalforecast.ingestion.cycle_acquisition_store import ConfigMismatchError
from tests.test_rest_priority_subset_promotion import (
    _build_promotion_fixture,
    _promote,
    _promoted_snapshot_path,
)


def test_exact_published_snapshot_is_reused_on_resume(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    first = cast(
        promotion_module.RestPrioritySubsetPromotionResult,
        _promote(fixture, tmp_path),
    )
    manifest_before = (first.snapshot_path / "manifest.json").read_bytes()

    resumed = cast(
        promotion_module.RestPrioritySubsetPromotionResult,
        _promote(fixture, tmp_path),
    )

    assert resumed == first
    assert (first.snapshot_path / "manifest.json").read_bytes() == manifest_before
    with closing(sqlite3.connect(fixture.store_path)) as connection, connection:
        [snapshot_count] = connection.execute(
            "SELECT COUNT(*) FROM snapshots WHERE snapshot_id = ?",
            (first.snapshot_id,),
        ).fetchone()
    assert snapshot_count == 1


def test_resume_after_crash_immediately_after_snapshot_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    original_identity_reader = promotion_module._snapshot_identity_sets

    def crash_after_publication(
        snapshot: Path,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        original_identity_reader(snapshot)
        raise RuntimeError("simulated process crash after snapshot publication")

    monkeypatch.setattr(
        promotion_module,
        "_snapshot_identity_sets",
        crash_after_publication,
    )
    with pytest.raises(RuntimeError, match="simulated process crash"):
        _promote(fixture, tmp_path)
    assert _promoted_snapshot_path(tmp_path).is_dir()

    monkeypatch.setattr(
        promotion_module,
        "_snapshot_identity_sets",
        original_identity_reader,
    )
    resumed = cast(
        promotion_module.RestPrioritySubsetPromotionResult,
        _promote(fixture, tmp_path),
    )

    assert resumed.snapshot_path == _promoted_snapshot_path(tmp_path)
    assert resumed.selected_candidate_ids == (
        fixture.accepted_id,
        fixture.excluded_id,
    )


def test_resume_rejects_tampered_published_snapshot_payload(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    result = cast(
        promotion_module.RestPrioritySubsetPromotionResult,
        _promote(fixture, tmp_path),
    )
    candidates = result.snapshot_path / "candidates.jsonl"
    candidates.write_bytes(candidates.read_bytes() + b"\n")

    with pytest.raises(
        promotion_module.RestPrioritySubsetPromotionError,
        match="snapshot",
    ):
        _promote(fixture, tmp_path)


def test_resume_rejects_target_batch_config_drift(tmp_path: Path) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    result = cast(
        promotion_module.RestPrioritySubsetPromotionResult,
        _promote(fixture, tmp_path),
    )
    with closing(sqlite3.connect(fixture.store_path)) as connection, connection:
        [raw_config] = connection.execute(
            "SELECT config_json FROM batches WHERE batch_id = ?",
            (result.batch_id,),
        ).fetchone()
        config = json.loads(raw_config)
        config["selected_candidate_count"] = 999
        drifted_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
        drifted_digest = hashlib.sha256(drifted_json.encode()).hexdigest()
        connection.execute(
            """
            UPDATE batches SET config_json = ?, config_digest = ?
            WHERE batch_id = ?
            """,
            (drifted_json, drifted_digest, result.batch_id),
        )

    with pytest.raises(ConfigMismatchError, match="config mismatch"):
        _promote(fixture, tmp_path)


def test_resume_rejects_untracked_snapshot_directory_collision(
    tmp_path: Path,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    collision = _promoted_snapshot_path(tmp_path)
    collision.mkdir(parents=True)

    with pytest.raises(
        promotion_module.RestPrioritySubsetPromotionError,
        match="untracked snapshot target",
    ):
        _promote(fixture, tmp_path)

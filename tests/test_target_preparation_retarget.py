from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.target_preparation_retarget import (
    RETARGET_IMPORT_RECEIPT_FILENAME,
    FailedSourcePreparation,
    RetargetImportError,
    SemanticReplayPlan,
    SnapshotCommitment,
    SourceTreeCommitment,
    StageCommitment,
    build_stage_commitment,
    compute_source_tree_commitment,
    inspect_failed_source_preparation,
    verify_retarget_import_receipt,
    write_retarget_import_receipt,
)


@dataclass(frozen=True, slots=True)
class _ValidInputs:
    source: Path
    target: Path
    source_evidence: FailedSourcePreparation
    snapshot: SnapshotCommitment
    source_stages: tuple[StageCommitment, ...]
    target_stages: tuple[StageCommitment, ...]
    before: SourceTreeCommitment
    after: SourceTreeCommitment
    replay: SemanticReplayPlan


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _source_root(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    snapshot_manifest_sha256 = "sha256:" + "1" * 64
    config: dict[str, Any] = {
        "schema_version": "legalforecast.target_cohort_config.v1",
        "driver_execute": True,
        "target_case_count": 148,
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
        "snapshot_cycle_hash": "2" * 64,
        "snapshot_batch_digest": "3" * 64,
        "stage_commands": [{"stage": "bridge-pacer-gaps", "argv": ["x"]}],
    }
    config["config_sha256"] = _canonical_sha(config)
    _write_json(source / "target-cohort-config.json", config)
    attempt_id = "20260725T050022.328074Z-4c53353201a64063899742560d50a059"
    _write_json(
        source / f"attempts/prepare-target-cohort/{attempt_id}/run-card.json",
        {
            "schema_version": "legalforecast.target_cohort_attempt.v1",
            "attempt_id": attempt_id,
            "stage": "prepare-target-cohort",
            "status": "failed",
            "failure_reason": "restricted document",
            "dry_run": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "requested_output_root": str(source.resolve()),
            "config_sha256": config["config_sha256"],
        },
    )
    (source / "00-authenticated-snapshot").mkdir()
    (source / "00-authenticated-snapshot/screened-cases.jsonl").write_text(
        '{"candidate_id":"a"}\n', encoding="utf-8"
    )
    (source / "03-gap-bridge/checkpoints").mkdir(parents=True)
    (source / "03-gap-bridge/checkpoints/a.json").write_text(
        '{"outcome":"failure"}\n', encoding="utf-8"
    )
    (source / "03-gap-bridge/progress-config.json").write_text(
        '{"source_commitment_count":2}\n', encoding="utf-8"
    )
    return source


def _valid_inputs(tmp_path: Path) -> _ValidInputs:
    source = _source_root(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (target / "imported").mkdir()
    (target / "imported/checkpoint.json").write_text(
        '{"outcome":"failure"}\n', encoding="utf-8"
    )
    source_evidence = inspect_failed_source_preparation(source)
    snapshot = SnapshotCommitment(
        manifest_sha256="sha256:" + "1" * 64,
        cycle_hash="2" * 64,
        batch_digest="3" * 64,
    )
    source_stages = (
        build_stage_commitment(
            source,
            stage="authenticated-snapshot",
            relative_paths=("00-authenticated-snapshot/screened-cases.jsonl",),
        ),
        build_stage_commitment(
            source,
            stage="gap-bridge-checkpoints",
            relative_paths=(
                "03-gap-bridge/checkpoints/a.json",
                "03-gap-bridge/progress-config.json",
            ),
        ),
    )
    target_stages = (
        build_stage_commitment(
            target,
            stage="imported-gap-bridge-checkpoints",
            relative_paths=("imported/checkpoint.json",),
        ),
    )
    before = compute_source_tree_commitment(source)
    after = compute_source_tree_commitment(source)
    replay = SemanticReplayPlan(
        source_semantic_revision="courtlistener-rest-recap-storage-host-2026-07-16-v4",
        target_semantic_revision=(
            "courtlistener-rest-described-embedded-rows-2026-07-25-v5"
        ),
        reason_code="text_missing",
        candidate_ids=("candidate-a", "candidate-b"),
    )
    return _ValidInputs(
        source=source,
        target=target,
        source_evidence=source_evidence,
        snapshot=snapshot,
        source_stages=source_stages,
        target_stages=target_stages,
        before=before,
        after=after,
        replay=replay,
    )


def test_write_and_verify_provider_free_retarget_import_receipt(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path)
    receipt_path = write_retarget_import_receipt(
        source=values.source_evidence,
        target_root=values.target,
        snapshot=values.snapshot,
        source_stage_commitments=values.source_stages,
        target_stage_commitments=values.target_stages,
        semantic_replay=values.replay,
        source_before=values.before,
        source_after=values.after,
    )

    assert receipt_path == values.target / RETARGET_IMPORT_RECEIPT_FILENAME
    record = json.loads(receipt_path.read_text())
    assert record["schema_version"] == (
        "legalforecast.target_cohort_retarget_import.v1"
    )
    assert record["provider_request_count"] == 0
    assert record["provider_activity_requested"] is False
    assert record["provider_activity_executed"] is False
    assert record["paid_activity_requested"] is False
    assert record["paid_activity_executed"] is False
    assert record["canonical_prepare_success_record_written"] is False
    assert record["source_unchanged"] is True
    assert record["semantic_replay"]["candidate_ids"] == [
        "candidate-a",
        "candidate-b",
    ]
    assert all(
        not artifact["relative_path"].startswith("/")
        for stage in record["source_stage_commitments"]
        for artifact in stage["artifacts"]
    )

    verified = verify_retarget_import_receipt(
        receipt_path,
        source_root=values.source,
        target_root=values.target,
        expected_receipt_file_sha256=(
            "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        ),
    )
    assert verified.semantic_replay.candidate_ids == (
        "candidate-a",
        "candidate-b",
    )

    # Exact resume is immutable and idempotent.
    before = receipt_path.read_bytes()
    assert (
        write_retarget_import_receipt(
            source=values.source_evidence,
            target_root=values.target,
            snapshot=values.snapshot,
            source_stage_commitments=values.source_stages,
            target_stage_commitments=values.target_stages,
            semantic_replay=values.replay,
            source_before=values.before,
            source_after=values.after,
        )
        == receipt_path
    )
    assert receipt_path.read_bytes() == before


def test_failed_source_authentication_rejects_config_and_attempt_drift(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path)
    config_path = source / "target-cohort-config.json"
    config = json.loads(config_path.read_text())
    config["target_case_count"] = 100
    _write_json(config_path, config)
    with pytest.raises(RetargetImportError, match="config self-hash mismatch"):
        inspect_failed_source_preparation(source)

    source = _source_root(tmp_path / "other")
    original = next(source.glob("attempts/prepare-target-cohort/*/run-card.json"))
    duplicate = source / "attempts/prepare-target-cohort/second/run-card.json"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(original.read_bytes())
    with pytest.raises(RetargetImportError, match="exactly one failed attempt"):
        inspect_failed_source_preparation(source)


def test_failed_source_rejects_success_evidence_and_nonfailed_attempt(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path)
    success = source / "run-cards/prepare-target-cohort.json"
    _write_json(success, {"status": "completed"})
    with pytest.raises(RetargetImportError, match="canonical success"):
        inspect_failed_source_preparation(source)

    success.unlink()
    attempt_path = next(source.glob("attempts/prepare-target-cohort/*/run-card.json"))
    attempt = json.loads(attempt_path.read_text())
    attempt["status"] = "completed"
    _write_json(attempt_path, attempt)
    with pytest.raises(RetargetImportError, match="not an authenticated failure"):
        inspect_failed_source_preparation(source)


def test_stage_commitment_recomputes_bytes_and_rejects_path_aliases(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path)
    stage = build_stage_commitment(
        source,
        stage="gap-bridge-checkpoints",
        relative_paths=("03-gap-bridge/checkpoints/a.json",),
    )
    (source / "03-gap-bridge/checkpoints/a.json").write_text(
        '{"tampered":true}\n', encoding="utf-8"
    )
    target = tmp_path / "target"
    target.mkdir()
    evidence = inspect_failed_source_preparation(source)
    tree = compute_source_tree_commitment(source)
    with pytest.raises(RetargetImportError, match="artifact SHA-256 mismatch"):
        write_retarget_import_receipt(
            source=evidence,
            target_root=target,
            snapshot=SnapshotCommitment(
                manifest_sha256="sha256:" + "1" * 64,
                cycle_hash="2" * 64,
                batch_digest="3" * 64,
            ),
            source_stage_commitments=(stage,),
            target_stage_commitments=(),
            semantic_replay=SemanticReplayPlan(
                source_semantic_revision="v4",
                target_semantic_revision="v5",
                reason_code="text_missing",
                candidate_ids=("a",),
            ),
            source_before=tree,
            source_after=tree,
        )

    with pytest.raises(RetargetImportError, match="canonical root-relative"):
        build_stage_commitment(
            source,
            stage="escape",
            relative_paths=("../outside",),
        )
    with pytest.raises(RetargetImportError, match="duplicate logical artifact"):
        build_stage_commitment(
            source,
            stage="duplicate",
            relative_paths=(
                "03-gap-bridge/progress-config.json",
                "03-gap-bridge/progress-config.json",
            ),
        )


def test_stage_commitment_accepts_historical_source_superset(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path)
    (source / "03-gap-bridge/orphan-source.json").write_text(
        '{"candidate_id":"70965642"}\n', encoding="utf-8"
    )

    stage = build_stage_commitment(
        source,
        stage="gap-bridge-source-commitments",
        relative_paths=(
            "03-gap-bridge/checkpoints/a.json",
            "03-gap-bridge/orphan-source.json",
            "03-gap-bridge/progress-config.json",
        ),
    )

    assert stage.artifact_count == 3


def test_write_rejects_overlap_source_mutation_and_target_success(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path)
    with pytest.raises(RetargetImportError, match="must be disjoint"):
        write_retarget_import_receipt(
            source=values.source_evidence,
            target_root=values.source,
            snapshot=values.snapshot,
            source_stage_commitments=values.source_stages,
            target_stage_commitments=(),
            semantic_replay=values.replay,
            source_before=values.before,
            source_after=values.after,
        )

    changed = replace(values.after, byte_count=values.after.byte_count + 1)
    with pytest.raises(RetargetImportError, match="source changed during import"):
        write_retarget_import_receipt(
            source=values.source_evidence,
            target_root=values.target,
            snapshot=values.snapshot,
            source_stage_commitments=values.source_stages,
            target_stage_commitments=values.target_stages,
            semantic_replay=values.replay,
            source_before=values.before,
            source_after=changed,
        )

    _write_json(
        values.target / "run-cards/prepare-target-cohort.json",
        {"status": "completed"},
    )
    with pytest.raises(RetargetImportError, match="canonical success"):
        write_retarget_import_receipt(
            source=values.source_evidence,
            target_root=values.target,
            snapshot=values.snapshot,
            source_stage_commitments=values.source_stages,
            target_stage_commitments=values.target_stages,
            semantic_replay=values.replay,
            source_before=values.before,
            source_after=values.after,
        )


def test_semantic_replay_ids_must_be_exact_sorted_and_unique() -> None:
    for candidate_ids in (("b", "a"), ("a", "a"), (), ("",)):
        with pytest.raises(RetargetImportError, match="candidate IDs"):
            SemanticReplayPlan(
                source_semantic_revision="v4",
                target_semantic_revision="v5",
                reason_code="text_missing",
                candidate_ids=candidate_ids,
            ).validate()


def test_verify_rejects_receipt_tampering_and_wrong_expected_file_hash(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path)
    receipt_path = write_retarget_import_receipt(
        source=values.source_evidence,
        target_root=values.target,
        snapshot=values.snapshot,
        source_stage_commitments=values.source_stages,
        target_stage_commitments=values.target_stages,
        semantic_replay=values.replay,
        source_before=values.before,
        source_after=values.after,
    )
    with pytest.raises(RetargetImportError, match="receipt file SHA-256 mismatch"):
        verify_retarget_import_receipt(
            receipt_path,
            source_root=values.source,
            target_root=values.target,
            expected_receipt_file_sha256="sha256:" + "0" * 64,
        )

    record = json.loads(receipt_path.read_text())
    record["provider_request_count"] = 1
    _write_json(receipt_path, record)
    with pytest.raises(RetargetImportError, match="receipt self-hash mismatch"):
        verify_retarget_import_receipt(
            receipt_path,
            source_root=values.source,
            target_root=values.target,
        )


def test_receipt_remains_verifiable_after_normal_resume_writes_success(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path)
    receipt_path = write_retarget_import_receipt(
        source=values.source_evidence,
        target_root=values.target,
        snapshot=values.snapshot,
        source_stage_commitments=values.source_stages,
        target_stage_commitments=values.target_stages,
        semantic_replay=values.replay,
        source_before=values.before,
        source_after=values.after,
    )
    _write_json(
        values.target / "run-cards/prepare-target-cohort.json",
        {"stage": "prepare-target-cohort", "status": "completed"},
    )
    _write_json(
        values.target / "target-cohort-preparation-summary.json",
        {"schema_version": "legalforecast.target_cohort_preparation.v1"},
    )

    verified = verify_retarget_import_receipt(
        receipt_path,
        source_root=values.source,
        target_root=values.target,
    )

    assert verified.receipt_file_sha256.startswith("sha256:")


def test_receipt_commits_immutable_baseline_but_allows_progressed_live_state(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path)
    receipt_path = write_retarget_import_receipt(
        source=values.source_evidence,
        target_root=values.target,
        snapshot=values.snapshot,
        source_stage_commitments=values.source_stages,
        target_stage_commitments=values.target_stages,
        semantic_replay=values.replay,
        source_before=values.before,
        source_after=values.after,
    )
    progressed_live_checkpoint = (
        values.target
        / "03-gap-bridge/checkpoints/pacer-gap-bridge/000002-progressed.json"
    )
    _write_json(
        progressed_live_checkpoint,
        {"candidate_id": "candidate-c", "outcome": "success"},
    )

    verified = verify_retarget_import_receipt(
        receipt_path,
        source_root=values.source,
        target_root=values.target,
    )
    assert verified.receipt_file_sha256.startswith("sha256:")

    immutable_baseline = values.target / "imported/checkpoint.json"
    immutable_baseline.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(RetargetImportError, match="artifact SHA-256 mismatch"):
        verify_retarget_import_receipt(
            receipt_path,
            source_root=values.source,
            target_root=values.target,
        )


def test_rejects_symlink_and_hardlink_artifacts(tmp_path: Path) -> None:
    source = _source_root(tmp_path)
    original = source / "03-gap-bridge/checkpoints/a.json"
    symlink = source / "03-gap-bridge/checkpoints/symlink.json"
    symlink.symlink_to(original)
    with pytest.raises(RetargetImportError, match="symlink"):
        build_stage_commitment(
            source,
            stage="bad-symlink",
            relative_paths=("03-gap-bridge/checkpoints/symlink.json",),
        )

    symlink.unlink()
    hardlink = source / "03-gap-bridge/checkpoints/hardlink.json"
    os.link(original, hardlink)
    with pytest.raises(RetargetImportError, match="singly linked"):
        build_stage_commitment(
            source,
            stage="bad-hardlink",
            relative_paths=("03-gap-bridge/checkpoints/a.json",),
        )


def test_rejects_source_and_target_roots_through_symlinked_ancestors(
    tmp_path: Path,
) -> None:
    values = _valid_inputs(tmp_path / "real")
    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(tmp_path / "real", target_is_directory=True)
    aliased_source = alias_parent / "source"
    with pytest.raises(RetargetImportError, match="path contains a symlink"):
        inspect_failed_source_preparation(aliased_source)

    aliased_target = alias_parent / "target"
    with pytest.raises(RetargetImportError, match="path contains a symlink"):
        write_retarget_import_receipt(
            source=values.source_evidence,
            target_root=aliased_target,
            snapshot=values.snapshot,
            source_stage_commitments=values.source_stages,
            target_stage_commitments=values.target_stages,
            semantic_replay=values.replay,
            source_before=values.before,
            source_after=values.after,
        )

    with pytest.raises(RetargetImportError, match="canonical path"):
        inspect_failed_source_preparation(alias_parent / "ignored" / ".." / "source")

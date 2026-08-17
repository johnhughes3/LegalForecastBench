"""Independent document-repair receipt replay for Stage A preflight."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.ingestion.stage_a_replay_executor.spec import (
    StageAReplayExecutorError,
)


def verify_repair_receipt(record: Mapping[str, object]) -> dict[str, object]:
    """Rebuild the repair plan/execution before accepting the receipt pin."""

    from legalforecast.ingestion.document_repair_executor import (
        build_full_document_repair_execution,
        replay_docket_snapshot_authority,
        replay_document_repair_receipt,
    )
    from legalforecast.ingestion.missing_document_successor import (
        build_missing_document_acquisition_plan,
        verify_repair_plan_approval,
    )

    manifest_path = _path(record, "manifest_path")
    approval_path = _path(record, "approval_path")
    snapshot_manifest_path = _path(record, "snapshot_manifest_path")
    source_lineage_path = _path(record, "source_lineage_path")
    snapshots_root = _path(record, "snapshots_root")
    execution_path = _path(record, "execution_path")
    receipt_path = _path(record, "receipt_path")

    manifest_bytes = _read_regular(manifest_path, "document repair manifest")
    approval = verify_repair_plan_approval(
        manifest_bytes,
        _json_object(
            _read_regular(approval_path, "repair approval"), "repair approval"
        ),
    )
    full_plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest_bytes,
        approval=approval,
    )
    snapshot_manifest_bytes = _read_regular(
        snapshot_manifest_path, "docket snapshot manifest"
    )
    source_lineage_bytes = _read_regular(source_lineage_path, "repair source lineage")
    source_lineage_sha256 = _digest(record, "source_lineage_sha256")
    snapshot_authority = replay_docket_snapshot_authority(
        manifest_bytes=snapshot_manifest_bytes,
        source_lineage_bytes=source_lineage_bytes,
        expected_source_lineage_sha256=source_lineage_sha256,
    )
    snapshot_bytes = {
        candidate_id: _read_regular(
            _snapshot_path(snapshots_root, candidate_id),
            f"docket snapshot {candidate_id}",
        )
        for candidate_id in snapshot_authority.candidate_sha256
    }
    execution_bytes = _read_regular(execution_path, "document repair execution")
    execution_raw_sha256 = hashlib.sha256(execution_bytes).hexdigest()
    if execution_raw_sha256 != _digest(record, "execution_artifact_sha256"):
        raise StageAReplayExecutorError(
            "document repair execution artifact pin differs"
        )
    execution_record = _json_object(execution_bytes, "document repair execution")
    execution = build_full_document_repair_execution(
        full_plan=full_plan,
        docket_snapshot_bytes=snapshot_bytes,
        docket_snapshot_sha256=dict(snapshot_authority.candidate_sha256),
        snapshot_authority=snapshot_authority,
        schema_version=_text(execution_record, "schema_version"),
    )
    if execution.to_record() != dict(execution_record):
        raise StageAReplayExecutorError(
            "document repair execution does not reproduce from verifier inputs"
        )

    receipt_bytes = _read_regular(receipt_path, "document repair receipt")
    receipt_raw_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_raw_sha256 != _digest(record, "receipt_artifact_sha256"):
        raise StageAReplayExecutorError("document repair receipt artifact pin differs")
    replayed = replay_document_repair_receipt(
        full_plan=full_plan,
        execution=execution,
        receipt_record=_json_object(receipt_bytes, "document repair receipt"),
        expected_receipt_sha256=_digest(record, "expected_receipt_sha256"),
    )
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_lineage_sha256": source_lineage_sha256,
        "execution_path": str(execution_path),
        "execution_sha256": execution.execution_sha256,
        "execution_artifact_sha256": execution_raw_sha256,
        "receipt_path": str(receipt_path),
        "receipt_sha256": replayed.receipt_sha256,
        "receipt_artifact_sha256": receipt_raw_sha256,
    }


def _snapshot_path(root: Path, candidate_id: str) -> Path:
    if (
        not candidate_id
        or candidate_id in {".", ".."}
        or "/" in candidate_id
        or "\\" in candidate_id
    ):
        raise StageAReplayExecutorError("docket snapshot candidate_id is unsafe")
    path = root / f"{candidate_id}.json"
    if path.parent != root:
        raise StageAReplayExecutorError("docket snapshot escapes its verified root")
    return path


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        loaded: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(f"{label} is not valid JSON") from exc
    if not isinstance(loaded, Mapping):
        raise StageAReplayExecutorError(f"{label} must be an object")
    return cast(Mapping[str, object], loaded)


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def _path(record: Mapping[str, object], field: str) -> Path:
    return Path(_text(record, field))


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value

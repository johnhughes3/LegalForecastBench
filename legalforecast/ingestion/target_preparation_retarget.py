"""Authenticated, provider-free import boundary for target-cohort retargeting.

This module deliberately does not construct providers, execute acquisition stages, or
write a canonical ``prepare-target-cohort`` success summary/run card.  The integrating
orchestrator must first use the existing stage-specific verifiers to establish the
*semantic* meaning of every artifact it imports.  It then passes root-relative paths
to :func:`build_stage_commitment`; this module independently reopens the bytes,
rejects aliases, and binds them into the import receipt.

Integration contract:

* call :func:`inspect_failed_source_preparation` before copying anything;
* call :func:`compute_source_tree_commitment` before and after the import;
* include the authenticated snapshot identity from the existing snapshot verifier;
* include every imported source and target artifact in one named stage commitment;
* list exactly the stale terminal candidate IDs that the normal resume must replay;
* call :func:`write_retarget_import_receipt` only after materialization is complete;
* stop after the receipt.  A later normal resume owns provider construction and the
  canonical preparation success record.

Stage commitments intentionally do not require checkpoint counts to equal source
commitment counts.  Historical progress configurations may authenticate a strict
superset (including an orphan source commitment) as long as every listed artifact is
independently authenticated and the higher-level stage verifier accepts its meaning.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Self, cast

RETARGET_IMPORT_RECEIPT_FILENAME = "target-cohort-retarget-import.json"
RETARGET_IMPORT_RECEIPT_SCHEMA = "legalforecast.target_cohort_retarget_import.v1"

_SOURCE_CONFIG_FILENAME = "target-cohort-config.json"
_SOURCE_CONFIG_SCHEMA = "legalforecast.target_cohort_config.v1"
_SOURCE_ATTEMPT_SCHEMA = "legalforecast.target_cohort_attempt.v1"
_SOURCE_STAGE = "prepare-target-cohort"
_SOURCE_SUCCESS_PATHS = (
    "target-cohort-preparation-summary.json",
    "run-cards/prepare-target-cohort.json",
)
_SHA256 = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_TEXT = re.compile(r"\S")


class RetargetImportError(ValueError):
    """Raised when retarget-import evidence is incomplete or changes."""


@dataclass(frozen=True, slots=True)
class ArtifactCommitment:
    """Commitment to one canonical root-relative, singly linked regular file."""

    relative_path: str
    sha256: str
    byte_count: int

    def validate(self) -> None:
        _canonical_relative_path(self.relative_path)
        _require_sha256(self.sha256, "artifact")
        if self.byte_count < 0:
            raise RetargetImportError("artifact byte count must be nonnegative")

    def to_record(self) -> dict[str, object]:
        self.validate()
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }

    @classmethod
    def from_record(cls, value: Mapping[str, object]) -> Self:
        _require_exact_keys(
            value, {"relative_path", "sha256", "byte_count"}, "artifact"
        )
        commitment = cls(
            relative_path=_required_text(value, "relative_path"),
            sha256=_required_text(value, "sha256"),
            byte_count=_required_int(value, "byte_count"),
        )
        commitment.validate()
        return commitment


@dataclass(frozen=True, slots=True)
class StageCommitment:
    """Canonical aggregate of byte commitments accepted by one stage verifier."""

    stage: str
    artifacts: tuple[ArtifactCommitment, ...]
    commitment_sha256: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def validate(self) -> None:
        _require_plain_text(self.stage, "stage")
        if not self.artifacts:
            raise RetargetImportError("stage commitment must contain artifacts")
        paths = [artifact.relative_path for artifact in self.artifacts]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise RetargetImportError(
                "stage artifacts must be canonical, unique, and sorted"
            )
        for artifact in self.artifacts:
            artifact.validate()
        _require_sha256(self.commitment_sha256, "stage commitment")
        if self.commitment_sha256 != _stage_commitment_sha256(
            self.stage, self.artifacts
        ):
            raise RetargetImportError("stage commitment SHA-256 mismatch")

    def to_record(self) -> dict[str, object]:
        self.validate()
        return {
            "stage": self.stage,
            "artifact_count": self.artifact_count,
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "commitment_sha256": self.commitment_sha256,
        }

    @classmethod
    def from_record(cls, value: Mapping[str, object]) -> Self:
        _require_exact_keys(
            value,
            {"stage", "artifact_count", "artifacts", "commitment_sha256"},
            "stage commitment",
        )
        raw_artifacts = value.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise RetargetImportError("stage artifacts must be a list")
        artifacts = tuple(
            ArtifactCommitment.from_record(_required_mapping(row, "artifact"))
            for row in cast(list[object], raw_artifacts)
        )
        commitment = cls(
            stage=_required_text(value, "stage"),
            artifacts=artifacts,
            commitment_sha256=_required_text(value, "commitment_sha256"),
        )
        if _required_int(value, "artifact_count") != commitment.artifact_count:
            raise RetargetImportError("stage artifact count mismatch")
        commitment.validate()
        return commitment


@dataclass(frozen=True, slots=True)
class SnapshotCommitment:
    """Authenticated snapshot identity already established by its verifier."""

    manifest_sha256: str
    cycle_hash: str
    batch_digest: str

    def validate(self) -> None:
        _require_sha256(self.manifest_sha256, "snapshot manifest")
        _require_sha256(self.cycle_hash, "snapshot cycle")
        _require_sha256(self.batch_digest, "snapshot batch")

    def to_record(self) -> dict[str, str]:
        self.validate()
        return {
            "manifest_sha256": _prefixed_sha256(self.manifest_sha256),
            "cycle_hash": _bare_sha256(self.cycle_hash),
            "batch_digest": _bare_sha256(self.batch_digest),
        }

    @classmethod
    def from_record(cls, value: Mapping[str, object]) -> Self:
        _require_exact_keys(
            value,
            {"manifest_sha256", "cycle_hash", "batch_digest"},
            "snapshot commitment",
        )
        commitment = cls(
            manifest_sha256=_required_text(value, "manifest_sha256"),
            cycle_hash=_required_text(value, "cycle_hash"),
            batch_digest=_required_text(value, "batch_digest"),
        )
        commitment.validate()
        return commitment


@dataclass(frozen=True, slots=True)
class SourceTreeCommitment:
    """Aggregate commitment over every filesystem entry below the source root."""

    sha256: str
    file_count: int
    byte_count: int

    def validate(self) -> None:
        _require_sha256(self.sha256, "source tree")
        if self.file_count < 1 or self.byte_count < 1:
            raise RetargetImportError(
                "source tree commitment requires positive file and byte counts"
            )

    def to_record(self) -> dict[str, object]:
        self.validate()
        return {
            "sha256": self.sha256,
            "file_count": self.file_count,
            "byte_count": self.byte_count,
        }

    @classmethod
    def from_record(cls, value: Mapping[str, object]) -> Self:
        _require_exact_keys(
            value, {"sha256", "file_count", "byte_count"}, "source tree"
        )
        commitment = cls(
            sha256=_required_text(value, "sha256"),
            file_count=_required_int(value, "file_count"),
            byte_count=_required_int(value, "byte_count"),
        )
        commitment.validate()
        return commitment


@dataclass(frozen=True, slots=True)
class SemanticReplayPlan:
    """Exact stale-terminal set admitted for one semantic-revision replay."""

    source_semantic_revision: str
    target_semantic_revision: str
    reason_code: str
    candidate_ids: tuple[str, ...]

    def validate(self) -> None:
        _require_plain_text(self.source_semantic_revision, "source semantic revision")
        _require_plain_text(self.target_semantic_revision, "target semantic revision")
        _require_plain_text(self.reason_code, "semantic replay reason code")
        if self.source_semantic_revision == self.target_semantic_revision:
            raise RetargetImportError("semantic replay revisions must differ")
        if (
            not self.candidate_ids
            or list(self.candidate_ids) != sorted(self.candidate_ids)
            or len(self.candidate_ids) != len(set(self.candidate_ids))
            or any(_TEXT.search(value) is None for value in self.candidate_ids)
        ):
            raise RetargetImportError(
                "semantic replay candidate IDs must be nonempty, unique, and sorted"
            )

    def to_record(self) -> dict[str, object]:
        self.validate()
        return {
            "source_semantic_revision": self.source_semantic_revision,
            "target_semantic_revision": self.target_semantic_revision,
            "reason_code": self.reason_code,
            "candidate_count": len(self.candidate_ids),
            "candidate_ids": list(self.candidate_ids),
            "candidate_ids_sha256": _canonical_sha256(list(self.candidate_ids)),
        }

    @classmethod
    def from_record(cls, value: Mapping[str, object]) -> Self:
        _require_exact_keys(
            value,
            {
                "source_semantic_revision",
                "target_semantic_revision",
                "reason_code",
                "candidate_count",
                "candidate_ids",
                "candidate_ids_sha256",
            },
            "semantic replay",
        )
        raw_ids = value.get("candidate_ids")
        if not isinstance(raw_ids, list):
            raise RetargetImportError("semantic replay candidate IDs are invalid")
        candidate_ids: list[str] = []
        for item in cast(list[object], raw_ids):
            if not isinstance(item, str):
                raise RetargetImportError("semantic replay candidate IDs are invalid")
            candidate_ids.append(item)
        plan = cls(
            source_semantic_revision=_required_text(value, "source_semantic_revision"),
            target_semantic_revision=_required_text(value, "target_semantic_revision"),
            reason_code=_required_text(value, "reason_code"),
            candidate_ids=tuple(candidate_ids),
        )
        plan.validate()
        if _required_int(value, "candidate_count") != len(plan.candidate_ids):
            raise RetargetImportError("semantic replay candidate count mismatch")
        if _required_text(value, "candidate_ids_sha256") != _canonical_sha256(
            list(plan.candidate_ids)
        ):
            raise RetargetImportError("semantic replay candidate IDs SHA-256 mismatch")
        return plan


@dataclass(frozen=True, slots=True)
class FailedSourcePreparation:
    """Directly authenticated failed source wrapper evidence."""

    root: Path
    config_relative_path: str
    config_file_sha256: str
    config_byte_count: int
    config_self_hash: str
    snapshot: SnapshotCommitment
    attempt_relative_path: str
    attempt_file_sha256: str
    attempt_byte_count: int
    attempt_id: str
    failure_reason: str
    config_record: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RetargetImportReceipt:
    """Verified immutable provider-free retarget-import receipt."""

    source_root: Path
    target_root: Path
    source: FailedSourcePreparation
    snapshot: SnapshotCommitment
    source_stage_commitments: tuple[StageCommitment, ...]
    target_stage_commitments: tuple[StageCommitment, ...]
    semantic_replay: SemanticReplayPlan
    source_before: SourceTreeCommitment
    source_after: SourceTreeCommitment
    receipt_sha256: str
    receipt_file_sha256: str


def inspect_failed_source_preparation(source_root: Path) -> FailedSourcePreparation:
    """Authenticate one executed, failed generic target preparation in place."""

    root = _canonical_existing_root(source_root, "source preparation root")
    _reject_canonical_success(root, label="source preparation")
    config_artifact, config_payload = _read_artifact(
        root, _SOURCE_CONFIG_FILENAME, label="source preparation config"
    )
    config = _json_object(config_payload, "source preparation config")
    if config.get("schema_version") != _SOURCE_CONFIG_SCHEMA:
        raise RetargetImportError("source preparation config schema mismatch")
    claimed_self_hash = _required_text(config, "config_sha256")
    config_without_hash = dict(config)
    config_without_hash.pop("config_sha256", None)
    if claimed_self_hash != _canonical_sha256(config_without_hash):
        raise RetargetImportError("source preparation config self-hash mismatch")
    if config.get("driver_execute") is not True:
        raise RetargetImportError("source preparation config was not executable")
    target_count = config.get("target_case_count")
    if (
        isinstance(target_count, bool)
        or not isinstance(target_count, int)
        or target_count < 1
    ):
        raise RetargetImportError("source preparation target count is invalid")
    snapshot = SnapshotCommitment(
        manifest_sha256=_required_text(config, "snapshot_manifest_sha256"),
        cycle_hash=_required_text(config, "snapshot_cycle_hash"),
        batch_digest=_required_text(config, "snapshot_batch_digest"),
    )
    snapshot.validate()

    attempts_root = root / "attempts" / _SOURCE_STAGE
    attempt_paths = (
        sorted(attempts_root.glob("*/run-card.json"))
        if attempts_root.is_dir() and not attempts_root.is_symlink()
        else []
    )
    if len(attempt_paths) != 1:
        raise RetargetImportError(
            "source preparation must contain exactly one failed attempt"
        )
    attempt_relative = attempt_paths[0].relative_to(root).as_posix()
    attempt_artifact, attempt_payload = _read_artifact(
        root, attempt_relative, label="source failed attempt"
    )
    attempt = _json_object(attempt_payload, "source failed attempt")
    attempt_id = attempt_paths[0].parent.name
    requested_root = _required_text(attempt, "requested_output_root")
    try:
        requested_root_path = Path(requested_root).resolve(strict=True)
    except OSError as exc:
        raise RetargetImportError(
            "source failed attempt requested output root is unavailable"
        ) from exc
    if (
        attempt.get("schema_version") != _SOURCE_ATTEMPT_SCHEMA
        or attempt.get("stage") != _SOURCE_STAGE
        or attempt.get("status") != "failed"
        or attempt.get("dry_run") is not False
        or attempt.get("paid_activity_requested") is not False
        or attempt.get("paid_activity_executed") is not False
        or attempt.get("attempt_id") != attempt_id
        or attempt.get("config_sha256") != claimed_self_hash
        or requested_root_path != root
    ):
        raise RetargetImportError(
            "source preparation attempt is not an authenticated failure"
        )
    failure_reason = _required_text(attempt, "failure_reason")
    return FailedSourcePreparation(
        root=root,
        config_relative_path=config_artifact.relative_path,
        config_file_sha256=config_artifact.sha256,
        config_byte_count=config_artifact.byte_count,
        config_self_hash=claimed_self_hash,
        snapshot=snapshot,
        attempt_relative_path=attempt_artifact.relative_path,
        attempt_file_sha256=attempt_artifact.sha256,
        attempt_byte_count=attempt_artifact.byte_count,
        attempt_id=attempt_id,
        failure_reason=failure_reason,
        config_record=MappingProxyType(dict(config)),
    )


def build_stage_commitment(
    root: Path,
    *,
    stage: str,
    relative_paths: Sequence[str],
) -> StageCommitment:
    """Reopen and commit every stage artifact from canonical relative paths."""

    canonical_root = _canonical_existing_root(root, "stage artifact root")
    _require_plain_text(stage, "stage")
    if not relative_paths:
        raise RetargetImportError("stage commitment must contain artifacts")
    if len(relative_paths) != len(set(relative_paths)):
        raise RetargetImportError("stage contains a duplicate logical artifact")
    artifacts = tuple(
        sorted(
            (
                _read_artifact(canonical_root, path, label=f"{stage} artifact")[0]
                for path in relative_paths
            ),
            key=lambda artifact: artifact.relative_path,
        )
    )
    commitment = StageCommitment(
        stage=stage,
        artifacts=artifacts,
        commitment_sha256=_stage_commitment_sha256(stage, artifacts),
    )
    commitment.validate()
    return commitment


def compute_source_tree_commitment(source_root: Path) -> SourceTreeCommitment:
    """Hash every source entry, rejecting aliases and non-regular leaf nodes."""

    root = _canonical_existing_root(source_root, "source preparation root")
    relative_paths: list[str] = []
    for candidate in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        relative = candidate.relative_to(root).as_posix()
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise RetargetImportError(f"source tree contains a symlink: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise RetargetImportError(
                f"source tree contains a non-regular entry: {relative}"
            )
        relative_paths.append(relative)
    artifacts = tuple(
        _read_artifact(root, relative, label="source tree artifact")[0]
        for relative in relative_paths
    )
    if not artifacts:
        raise RetargetImportError("source tree contains no regular files")
    aggregate = {
        "artifacts": [artifact.to_record() for artifact in artifacts],
    }
    commitment = SourceTreeCommitment(
        sha256=_canonical_sha256(aggregate),
        file_count=len(artifacts),
        byte_count=sum(artifact.byte_count for artifact in artifacts),
    )
    commitment.validate()
    return commitment


def write_retarget_import_receipt(
    *,
    source: FailedSourcePreparation,
    target_root: Path,
    snapshot: SnapshotCommitment,
    source_stage_commitments: Sequence[StageCommitment],
    target_stage_commitments: Sequence[StageCommitment],
    semantic_replay: SemanticReplayPlan,
    source_before: SourceTreeCommitment,
    source_after: SourceTreeCommitment,
) -> Path:
    """Write or verify one immutable zero-provider retarget-import receipt."""

    current_source = inspect_failed_source_preparation(source.root)
    _require_same_source(source, current_source)
    target = _canonical_existing_root(target_root, "target preparation root")
    _require_disjoint_roots(current_source.root, target)
    _reject_canonical_success(target, label="target preparation")
    snapshot.validate()
    if snapshot.to_record() != current_source.snapshot.to_record():
        raise RetargetImportError("snapshot commitment differs from source config")
    semantic_replay.validate()
    source_before.validate()
    source_after.validate()
    if source_before != source_after:
        raise RetargetImportError("source changed during import")
    if compute_source_tree_commitment(current_source.root) != source_after:
        raise RetargetImportError(
            "source after commitment does not match current bytes"
        )

    verified_source_stages = _verify_stage_commitments(
        current_source.root,
        source_stage_commitments,
        label="source",
    )
    verified_target_stages = _verify_stage_commitments(
        target,
        target_stage_commitments,
        label="target",
    )
    record = _receipt_record(
        source=current_source,
        target=target,
        snapshot=snapshot,
        source_stages=verified_source_stages,
        target_stages=verified_target_stages,
        semantic_replay=semantic_replay,
        source_before=source_before,
        source_after=source_after,
    )
    payload = _json_bytes(record)
    path = target / RETARGET_IMPORT_RECEIPT_FILENAME
    if path.exists() or path.is_symlink():
        existing = _read_artifact(
            target,
            RETARGET_IMPORT_RECEIPT_FILENAME,
            label="retarget import receipt",
        )[1]
        if existing != payload:
            raise RetargetImportError(
                "retarget import receipt already exists with different bytes"
            )
        verify_retarget_import_receipt(
            path,
            source_root=current_source.root,
            target_root=target,
            expected_receipt_file_sha256=_sha256(payload),
        )
        return path
    _write_exclusive_regular(path, payload)
    verify_retarget_import_receipt(
        path,
        source_root=current_source.root,
        target_root=target,
        expected_receipt_file_sha256=_sha256(payload),
    )
    return path


def verify_retarget_import_receipt(
    receipt_path: Path,
    *,
    source_root: Path,
    target_root: Path,
    expected_receipt_file_sha256: str | None = None,
) -> RetargetImportReceipt:
    """Recompute every receipt commitment from current authenticated bytes."""

    source_path = _canonical_existing_root(source_root, "source preparation root")
    target = _canonical_existing_root(target_root, "target preparation root")
    _require_disjoint_roots(source_path, target)
    expected_path = target / RETARGET_IMPORT_RECEIPT_FILENAME
    try:
        if receipt_path.absolute() != expected_path.absolute():
            raise RetargetImportError(
                "retarget import receipt path is not the canonical target path"
            )
    except OSError as exc:
        raise RetargetImportError("retarget import receipt path is invalid") from exc
    receipt_artifact, payload = _read_artifact(
        target,
        RETARGET_IMPORT_RECEIPT_FILENAME,
        label="retarget import receipt",
    )
    if expected_receipt_file_sha256 is not None:
        _require_sha256(expected_receipt_file_sha256, "receipt file")
        if receipt_artifact.sha256 != _prefixed_sha256(expected_receipt_file_sha256):
            raise RetargetImportError("receipt file SHA-256 mismatch")
    record = _json_object(payload, "retarget import receipt")
    _require_exact_keys(
        record,
        {
            "schema_version",
            "operation",
            "status",
            "source_preparation_root",
            "target_preparation_root",
            "source_config",
            "failed_attempt",
            "snapshot_commitment",
            "source_stage_commitments",
            "target_stage_commitments",
            "semantic_replay",
            "source_before_commitment",
            "source_after_commitment",
            "source_unchanged",
            "provider_request_count",
            "provider_activity_requested",
            "provider_activity_executed",
            "paid_activity_requested",
            "paid_activity_executed",
            "canonical_prepare_success_record_written",
            "receipt_sha256",
        },
        "retarget import receipt",
    )
    claimed_receipt_sha256 = _required_text(record, "receipt_sha256")
    unhashed = dict(record)
    unhashed.pop("receipt_sha256", None)
    if claimed_receipt_sha256 != _canonical_sha256(unhashed):
        raise RetargetImportError("receipt self-hash mismatch")
    if (
        record.get("schema_version") != RETARGET_IMPORT_RECEIPT_SCHEMA
        or record.get("operation") != "target_cohort_retarget_import"
        or record.get("status") != "completed"
        or record.get("source_preparation_root") != str(source_path)
        or record.get("target_preparation_root") != str(target)
        or record.get("source_unchanged") is not True
        or record.get("provider_request_count") != 0
        or record.get("provider_activity_requested") is not False
        or record.get("provider_activity_executed") is not False
        or record.get("paid_activity_requested") is not False
        or record.get("paid_activity_executed") is not False
        or record.get("canonical_prepare_success_record_written") is not False
    ):
        raise RetargetImportError("retarget import receipt safety fields are invalid")
    source = inspect_failed_source_preparation(source_path)
    _verify_source_receipt_fields(source, record)
    snapshot = SnapshotCommitment.from_record(
        _required_mapping(record.get("snapshot_commitment"), "snapshot commitment")
    )
    if snapshot.to_record() != source.snapshot.to_record():
        raise RetargetImportError("receipt snapshot differs from source config")
    source_stages = _stage_commitments_from_record(
        record.get("source_stage_commitments"), label="source"
    )
    target_stages = _stage_commitments_from_record(
        record.get("target_stage_commitments"), label="target"
    )
    source_stages = _verify_stage_commitments(
        source_path, source_stages, label="source"
    )
    target_stages = _verify_stage_commitments(target, target_stages, label="target")
    semantic_replay = SemanticReplayPlan.from_record(
        _required_mapping(record.get("semantic_replay"), "semantic replay")
    )
    source_before = SourceTreeCommitment.from_record(
        _required_mapping(
            record.get("source_before_commitment"), "source before commitment"
        )
    )
    source_after = SourceTreeCommitment.from_record(
        _required_mapping(
            record.get("source_after_commitment"), "source after commitment"
        )
    )
    if source_before != source_after:
        raise RetargetImportError("receipt source changed during import")
    if compute_source_tree_commitment(source_path) != source_after:
        raise RetargetImportError(
            "receipt source commitment differs from current bytes"
        )
    return RetargetImportReceipt(
        source_root=source_path,
        target_root=target,
        source=source,
        snapshot=snapshot,
        source_stage_commitments=source_stages,
        target_stage_commitments=target_stages,
        semantic_replay=semantic_replay,
        source_before=source_before,
        source_after=source_after,
        receipt_sha256=claimed_receipt_sha256,
        receipt_file_sha256=receipt_artifact.sha256,
    )


def _receipt_record(
    *,
    source: FailedSourcePreparation,
    target: Path,
    snapshot: SnapshotCommitment,
    source_stages: tuple[StageCommitment, ...],
    target_stages: tuple[StageCommitment, ...],
    semantic_replay: SemanticReplayPlan,
    source_before: SourceTreeCommitment,
    source_after: SourceTreeCommitment,
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": RETARGET_IMPORT_RECEIPT_SCHEMA,
        "operation": "target_cohort_retarget_import",
        "status": "completed",
        "source_preparation_root": str(source.root),
        "target_preparation_root": str(target),
        "source_config": {
            "relative_path": source.config_relative_path,
            "file_sha256": source.config_file_sha256,
            "byte_count": source.config_byte_count,
            "config_self_hash": source.config_self_hash,
        },
        "failed_attempt": {
            "relative_path": source.attempt_relative_path,
            "file_sha256": source.attempt_file_sha256,
            "byte_count": source.attempt_byte_count,
            "attempt_id": source.attempt_id,
            "failure_reason": source.failure_reason,
        },
        "snapshot_commitment": snapshot.to_record(),
        "source_stage_commitments": [stage.to_record() for stage in source_stages],
        "target_stage_commitments": [stage.to_record() for stage in target_stages],
        "semantic_replay": semantic_replay.to_record(),
        "source_before_commitment": source_before.to_record(),
        "source_after_commitment": source_after.to_record(),
        "source_unchanged": True,
        "provider_request_count": 0,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "canonical_prepare_success_record_written": False,
    }
    record["receipt_sha256"] = _canonical_sha256(record)
    return record


def _verify_stage_commitments(
    root: Path,
    stages: Sequence[StageCommitment],
    *,
    label: str,
) -> tuple[StageCommitment, ...]:
    if not stages:
        raise RetargetImportError(f"{label} stage commitments must not be empty")
    ordered = tuple(sorted(stages, key=lambda stage: stage.stage))
    names = [stage.stage for stage in ordered]
    if len(names) != len(set(names)):
        raise RetargetImportError(f"{label} stage names are duplicated")
    logical_paths: set[str] = set()
    for stage in ordered:
        stage.validate()
        for artifact in stage.artifacts:
            if artifact.relative_path in logical_paths:
                raise RetargetImportError(
                    f"{label} stage commitments contain a duplicate logical artifact"
                )
            logical_paths.add(artifact.relative_path)
            actual = _read_artifact(
                root,
                artifact.relative_path,
                label=f"{label} stage artifact",
            )[0]
            if actual.sha256 != artifact.sha256:
                raise RetargetImportError(
                    f"{label} stage artifact SHA-256 mismatch: {artifact.relative_path}"
                )
            if actual.byte_count != artifact.byte_count:
                raise RetargetImportError(
                    f"{label} stage artifact byte count mismatch: "
                    f"{artifact.relative_path}"
                )
    return ordered


def _stage_commitments_from_record(
    value: object, *, label: str
) -> tuple[StageCommitment, ...]:
    if not isinstance(value, list):
        raise RetargetImportError(f"{label} stage commitments must be a list")
    stages = tuple(
        StageCommitment.from_record(_required_mapping(row, "stage commitment"))
        for row in cast(list[object], value)
    )
    if list(stages) != sorted(stages, key=lambda stage: stage.stage):
        raise RetargetImportError(f"{label} stage commitments are not sorted")
    return stages


def _verify_source_receipt_fields(
    source: FailedSourcePreparation, record: Mapping[str, object]
) -> None:
    config = _required_mapping(record.get("source_config"), "source config")
    _require_exact_keys(
        config,
        {"relative_path", "file_sha256", "byte_count", "config_self_hash"},
        "source config",
    )
    if dict(config) != {
        "relative_path": source.config_relative_path,
        "file_sha256": source.config_file_sha256,
        "byte_count": source.config_byte_count,
        "config_self_hash": source.config_self_hash,
    }:
        raise RetargetImportError("receipt source config commitment mismatch")
    attempt = _required_mapping(record.get("failed_attempt"), "failed attempt")
    _require_exact_keys(
        attempt,
        {
            "relative_path",
            "file_sha256",
            "byte_count",
            "attempt_id",
            "failure_reason",
        },
        "failed attempt",
    )
    if dict(attempt) != {
        "relative_path": source.attempt_relative_path,
        "file_sha256": source.attempt_file_sha256,
        "byte_count": source.attempt_byte_count,
        "attempt_id": source.attempt_id,
        "failure_reason": source.failure_reason,
    }:
        raise RetargetImportError("receipt failed-attempt commitment mismatch")


def _require_same_source(
    expected: FailedSourcePreparation, actual: FailedSourcePreparation
) -> None:
    comparable_expected = (
        expected.root,
        expected.config_relative_path,
        expected.config_file_sha256,
        expected.config_byte_count,
        expected.config_self_hash,
        expected.snapshot,
        expected.attempt_relative_path,
        expected.attempt_file_sha256,
        expected.attempt_byte_count,
        expected.attempt_id,
        expected.failure_reason,
        dict(expected.config_record),
    )
    comparable_actual = (
        actual.root,
        actual.config_relative_path,
        actual.config_file_sha256,
        actual.config_byte_count,
        actual.config_self_hash,
        actual.snapshot,
        actual.attempt_relative_path,
        actual.attempt_file_sha256,
        actual.attempt_byte_count,
        actual.attempt_id,
        actual.failure_reason,
        dict(actual.config_record),
    )
    if comparable_expected != comparable_actual:
        raise RetargetImportError("failed source preparation changed after inspection")


def _reject_canonical_success(root: Path, *, label: str) -> None:
    for relative in _SOURCE_SUCCESS_PATHS:
        path = root / relative
        if path.exists() or path.is_symlink():
            raise RetargetImportError(
                f"{label} already contains canonical success evidence: {relative}"
            )


def _require_disjoint_roots(source: Path, target: Path) -> None:
    if (
        source == target
        or source.is_relative_to(target)
        or target.is_relative_to(source)
    ):
        raise RetargetImportError(
            "source and target preparation roots must be disjoint"
        )


def _canonical_existing_root(path: Path, label: str) -> Path:
    lexical = path if path.is_absolute() else Path.cwd() / path
    if any(part in {".", ".."} for part in lexical.parts):
        raise RetargetImportError(f"{label} must be a canonical path")
    current = Path(lexical.anchor)
    for component in lexical.parts[1:]:
        current = current / component
        try:
            ancestor = current.lstat()
        except OSError as exc:
            raise RetargetImportError(f"{label} does not exist: {lexical}") from exc
        if stat.S_ISLNK(ancestor.st_mode):
            raise RetargetImportError(f"{label} path contains a symlink")
    configured = lexical
    try:
        metadata = configured.lstat()
    except OSError as exc:
        raise RetargetImportError(f"{label} does not exist: {configured}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RetargetImportError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise RetargetImportError(f"{label} must be a directory")
    try:
        resolved = configured.resolve(strict=True)
    except OSError as exc:
        raise RetargetImportError(f"{label} cannot be resolved") from exc
    return resolved


def _read_artifact(
    root: Path, relative_path: str, *, label: str
) -> tuple[ArtifactCommitment, bytes]:
    canonical = _canonical_relative_path(relative_path)
    path = root.joinpath(*PurePosixPath(canonical).parts)
    current = root
    for component in PurePosixPath(canonical).parts[:-1]:
        current = current / component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise RetargetImportError(
                f"{label} parent is unavailable: {canonical}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise RetargetImportError(f"{label} path contains a symlink: {canonical}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise RetargetImportError(f"{label} parent is not a directory: {canonical}")
    try:
        before = path.lstat()
    except OSError as exc:
        raise RetargetImportError(f"{label} is unavailable: {canonical}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise RetargetImportError(f"{label} must not be a symlink: {canonical}")
    if not stat.S_ISREG(before.st_mode):
        raise RetargetImportError(f"{label} must be a regular file: {canonical}")
    if before.st_nlink != 1:
        raise RetargetImportError(f"{label} must be singly linked: {canonical}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RetargetImportError(
            f"{label} could not be opened safely: {canonical}"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise RetargetImportError(
                f"{label} identity changed before read: {canonical}"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        payload = b"".join(chunks)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except OSError as exc:
        raise RetargetImportError(
            f"{label} disappeared during read: {canonical}"
        ) from exc
    stable = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_nlink,
    )
    if stable != (
        after_open.st_dev,
        after_open.st_ino,
        after_open.st_size,
        after_open.st_mtime_ns,
        after_open.st_nlink,
    ) or stable != (
        after_path.st_dev,
        after_path.st_ino,
        after_path.st_size,
        after_path.st_mtime_ns,
        after_path.st_nlink,
    ):
        raise RetargetImportError(f"{label} changed during read: {canonical}")
    artifact = ArtifactCommitment(
        relative_path=canonical,
        sha256=_sha256(payload),
        byte_count=len(payload),
    )
    artifact.validate()
    return artifact, payload


def _canonical_relative_path(value: str) -> str:
    if not value or "\\" in value:
        raise RetargetImportError("artifact path must be canonical root-relative")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != value
    ):
        raise RetargetImportError("artifact path must be canonical root-relative")
    return value


def _write_exclusive_regular(path: Path, payload: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RetargetImportError(f"cannot create immutable receipt: {path}") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        directory = os.open(path.parent, directory_flags)
    except OSError as exc:
        raise RetargetImportError(
            f"cannot open immutable receipt directory: {path.parent}"
        ) from exc
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _stage_commitment_sha256(
    stage: str, artifacts: Sequence[ArtifactCommitment]
) -> str:
    return _canonical_sha256(
        {
            "stage": stage,
            "artifacts": [artifact.to_record() for artifact in artifacts],
        }
    )


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetargetImportError(f"{label} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise RetargetImportError(f"{label} must contain a JSON object")
    return cast(Mapping[str, object], value)


def _json_bytes(value: object) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise RetargetImportError("receipt is not canonical JSON data") from exc


def _canonical_sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RetargetImportError(
            "commitment payload is not canonical JSON data"
        ) from exc
    return _sha256(payload)


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise RetargetImportError(f"{label} SHA-256 is invalid")


def _prefixed_sha256(value: str) -> str:
    _require_sha256(value, "commitment")
    return value if value.startswith("sha256:") else "sha256:" + value


def _bare_sha256(value: str) -> str:
    _require_sha256(value, "commitment")
    return value.removeprefix("sha256:")


def _required_text(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or _TEXT.search(result) is None:
        raise RetargetImportError(f"{key} must be a nonempty string")
    return result


def _require_plain_text(value: str, label: str) -> None:
    if _TEXT.search(value) is None:
        raise RetargetImportError(f"{label} must be a nonempty string")


def _required_int(value: Mapping[str, object], key: str) -> int:
    result = value.get(key)
    if isinstance(result, bool) or not isinstance(result, int):
        raise RetargetImportError(f"{key} must be an integer")
    return result


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RetargetImportError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], label: str
) -> None:
    if set(value) != expected:
        raise RetargetImportError(f"{label} field set is not exact")

"""Provider-free union of complete saturated screening snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import verify_snapshot


class ScreeningSnapshotUnionError(ValueError):
    """Raised when source snapshots cannot form an exact terminal union."""


@dataclass(frozen=True, slots=True)
class UnionCandidate:
    candidate_id: str
    state: str
    reason_code: str
    evidence: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class UnionRawArtifact:
    candidate_id: str
    path: Path
    content: bytes
    sha256: str
    byte_count: int
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class ScreeningSnapshotUnion:
    candidates: tuple[UnionCandidate, ...]
    raw_artifacts: tuple[UnionRawArtifact, ...]
    stage_commitment: Mapping[str, Any]


def load_screening_snapshot_union(
    source_snapshots: Sequence[Path],
    *,
    expected_manifest_sha256: Sequence[str],
    expected_cycle_hash: str,
) -> ScreeningSnapshotUnion:
    """Verify and normalize at least two same-cycle saturated snapshots."""

    resolved = tuple(path.resolve() for path in source_snapshots)
    if len(resolved) < 2 or len(set(resolved)) != len(resolved):
        raise ScreeningSnapshotUnionError(
            "snapshot union requires at least two distinct source manifests"
        )
    if len(expected_manifest_sha256) != len(resolved):
        raise ScreeningSnapshotUnionError(
            "each source snapshot requires one ordered expected manifest SHA-256"
        )
    candidate_by_id: dict[str, UnionCandidate] = {}
    candidate_commitments: dict[str, str] = {}
    raw_sets_by_candidate: dict[str, set[tuple[str, int]]] = {}
    raw_by_commitment: dict[tuple[str, str, int], UnionRawArtifact] = {}
    source_commitments: list[dict[str, object]] = []
    seen_manifest_sha256: set[str] = set()
    seen_batch_digests: set[str] = set()
    for snapshot, expected_manifest_hash in zip(
        resolved, expected_manifest_sha256, strict=True
    ):
        if snapshot.is_symlink() or not snapshot.is_dir():
            raise ScreeningSnapshotUnionError(
                f"source snapshot is not a regular directory: {snapshot}"
            )
        manifest = verify_snapshot(
            snapshot,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        manifest_path = snapshot / "manifest.json"
        manifest_sha256 = hashlib.sha256(
            _read_regular_file(manifest_path, "source manifest")
        ).hexdigest()
        if manifest_sha256 != expected_manifest_hash:
            raise ScreeningSnapshotUnionError(
                f"source snapshot manifest SHA-256 mismatch: {manifest_path}"
            )
        batch_digest = _string(manifest.get("batch_digest"), "source batch digest")
        if manifest_sha256 in seen_manifest_sha256:
            raise ScreeningSnapshotUnionError(
                "snapshot union contains duplicate source manifest content"
            )
        if batch_digest in seen_batch_digests:
            raise ScreeningSnapshotUnionError(
                "snapshot union contains duplicate source batch digest"
            )
        seen_manifest_sha256.add(manifest_sha256)
        seen_batch_digests.add(batch_digest)
        source_commitments.append(
            {
                "manifest_path": str(manifest_path),
                "manifest_sha256": manifest_sha256,
                "snapshot_id": manifest["snapshot_id"],
                "batch_id": manifest["batch_id"],
                "batch_digest": batch_digest,
            }
        )
        source_candidates = _candidate_records(snapshot / "candidates.jsonl")
        source_raw = _raw_records(snapshot / "raw-artifacts.jsonl")
        source_raw_sets: dict[str, set[tuple[str, int]]] = {}
        for artifact in source_raw:
            source_raw_sets.setdefault(artifact.candidate_id, set()).add(
                (artifact.sha256, artifact.byte_count)
            )
            key = (artifact.candidate_id, artifact.sha256, artifact.byte_count)
            raw_by_commitment.setdefault(key, artifact)
        for candidate in source_candidates:
            commitment = _canonical_json(
                {
                    "state": candidate.state,
                    "reason_code": candidate.reason_code,
                    "evidence": candidate.evidence,
                }
            )
            prior = candidate_commitments.get(candidate.candidate_id)
            if prior is not None and prior != commitment:
                raise ScreeningSnapshotUnionError(
                    "duplicate candidate has non-identical terminal evidence: "
                    f"{candidate.candidate_id}"
                )
            raw_set = source_raw_sets.get(candidate.candidate_id, set())
            prior_raw_set = raw_sets_by_candidate.get(candidate.candidate_id)
            if prior_raw_set is not None and prior_raw_set != raw_set:
                raise ScreeningSnapshotUnionError(
                    "duplicate candidate has non-identical raw-artifact commitments: "
                    f"{candidate.candidate_id}"
                )
            candidate_commitments[candidate.candidate_id] = commitment
            candidate_by_id.setdefault(candidate.candidate_id, candidate)
            raw_sets_by_candidate.setdefault(candidate.candidate_id, raw_set)
    stage_commitment = {
        "schema_version": "legalforecast.screening_snapshot_union_inputs.v1",
        "expected_cycle_hash": expected_cycle_hash,
        "source_count": len(source_commitments),
        "sources": source_commitments,
        "candidate_count": len(candidate_by_id),
    }
    return ScreeningSnapshotUnion(
        candidates=tuple(candidate_by_id[key] for key in sorted(candidate_by_id)),
        raw_artifacts=tuple(
            raw_by_commitment[key] for key in sorted(raw_by_commitment)
        ),
        stage_commitment=stage_commitment,
    )


def _candidate_records(path: Path) -> tuple[UnionCandidate, ...]:
    candidates: list[UnionCandidate] = []
    for row_number, record in enumerate(_jsonl(path), start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"candidate row {row_number} candidate_id"
        )
        state = _string(record.get("state"), f"candidate {candidate_id} state")
        reason_code = _string(
            record.get("reason_code"), f"candidate {candidate_id} reason_code"
        )
        evidence = record.get("evidence")
        if state not in {"accepted", "excluded", "newly_free"} or not isinstance(
            evidence, Mapping
        ):
            raise ScreeningSnapshotUnionError(
                f"candidate {candidate_id} lacks terminal evidence"
            )
        evidence_record = cast(Mapping[str, Any], evidence)
        if evidence_record.get("candidate_id") != candidate_id:
            raise ScreeningSnapshotUnionError(
                f"candidate {candidate_id} evidence identity mismatch"
            )
        candidates.append(
            UnionCandidate(
                candidate_id=candidate_id,
                state=state,
                reason_code=reason_code,
                evidence=evidence_record,
            )
        )
    return tuple(candidates)


def _raw_records(path: Path) -> tuple[UnionRawArtifact, ...]:
    artifacts: list[UnionRawArtifact] = []
    for row_number, record in enumerate(_jsonl(path), start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"raw row {row_number} candidate_id"
        )
        raw_path = Path(_string(record.get("path"), f"raw row {row_number} path"))
        if (
            not raw_path.is_absolute()
            or raw_path.is_symlink()
            or not raw_path.is_file()
        ):
            raise ScreeningSnapshotUnionError(
                f"raw artifact is not a regular file for {candidate_id}"
            )
        content = _read_regular_file(raw_path, f"raw artifact for {candidate_id}")
        digest = hashlib.sha256(content).hexdigest()
        byte_count = record.get("byte_count")
        if (
            record.get("sha256") != digest
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count != len(content)
        ):
            raise ScreeningSnapshotUnionError(
                f"raw artifact commitment mismatch for {candidate_id}"
            )
        artifacts.append(
            UnionRawArtifact(
                candidate_id=candidate_id,
                path=raw_path,
                content=content,
                sha256=digest,
                byte_count=byte_count,
                retrieved_at=_string(
                    record.get("retrieved_at"),
                    f"raw row {row_number} retrieved_at",
                ),
            )
        )
    return tuple(artifacts)


def _jsonl(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    payload = _read_regular_file(path, f"snapshot metadata {path.name}")
    for row_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as error:
            raise ScreeningSnapshotUnionError(
                f"invalid JSON in {path} row {row_number}"
            ) from error
        if not isinstance(value, dict):
            raise ScreeningSnapshotUnionError(
                f"non-object JSON in {path} row {row_number}"
            )
        records.append(cast(dict[str, Any], value))
    return records


def _read_regular_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ScreeningSnapshotUnionError(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScreeningSnapshotUnionError(f"{label} is required")
    return value.strip()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

"""Provider-free union of complete saturated screening snapshots."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import verify_snapshot
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)


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
class _SourceTerminalObservation:
    candidate: UnionCandidate
    source_manifest_sha256: str
    source_snapshot_id: str
    source_batch_id: str
    raw_artifacts: tuple[UnionRawArtifact, ...]
    strict_screen_history: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ScreeningSnapshotUnion:
    candidates: tuple[UnionCandidate, ...]
    raw_artifacts: tuple[UnionRawArtifact, ...]
    canonical_raw_artifacts: tuple[UnionRawArtifact, ...]
    longitudinal_observations: tuple[Mapping[str, Any], ...]
    stage_commitment: Mapping[str, Any]


def load_screening_snapshot_union(
    source_snapshots: Sequence[Path],
    *,
    expected_manifest_sha256: Sequence[str],
    expected_cycle_hash: str,
    expected_terminal_correction_candidate_id: Sequence[str] = (),
    expected_terminal_correction_source_manifest_sha256: Sequence[str] = (),
) -> ScreeningSnapshotUnion:
    """Verify and normalize at least two same-cycle saturated snapshots."""

    snapshots = tuple(
        _canonical_snapshot_directory(path, f"source snapshot {index}")
        for index, path in enumerate(source_snapshots, start=1)
    )
    if len(snapshots) < 2 or len(set(snapshots)) != len(snapshots):
        raise ScreeningSnapshotUnionError(
            "snapshot union requires at least two distinct source manifests"
        )
    if len(expected_manifest_sha256) != len(snapshots):
        raise ScreeningSnapshotUnionError(
            "each source snapshot requires one ordered expected manifest SHA-256"
        )
    correction_pins = _terminal_correction_pins(
        expected_terminal_correction_candidate_id,
        expected_terminal_correction_source_manifest_sha256,
    )
    observations_by_candidate: dict[str, list[_SourceTerminalObservation]] = {}
    raw_by_commitment: dict[tuple[str, str, int], UnionRawArtifact] = {}
    source_commitments: list[dict[str, object]] = []
    seen_manifest_sha256: set[str] = set()
    seen_batch_digests: set[str] = set()
    provisional_union = False
    for snapshot, expected_manifest_hash in zip(
        snapshots, expected_manifest_sha256, strict=True
    ):
        manifest_path = snapshot / "manifest.json"
        manifest_sha256 = hashlib.sha256(
            _read_regular_file(manifest_path, "source manifest")
        ).hexdigest()
        if manifest_sha256 != expected_manifest_hash:
            raise ScreeningSnapshotUnionError(
                f"source snapshot manifest SHA-256 mismatch: {manifest_path}"
            )
        manifest = verify_snapshot(
            snapshot,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        _read_regular_file(snapshot / "candidates.jsonl", "source candidates")
        _preflight_raw_paths(snapshot / "raw-artifacts.jsonl")
        source_candidates = _candidate_records(snapshot / "candidates.jsonl")
        strict_screen_history = _strict_screen_history(snapshot / "observations.jsonl")
        source_raw = _raw_records(snapshot / "raw-artifacts.jsonl")
        source_candidate_ids = {
            candidate.candidate_id for candidate in source_candidates
        }
        source_raw_candidate_ids = {artifact.candidate_id for artifact in source_raw}
        if not source_raw_candidate_ids <= source_candidate_ids:
            orphan_ids = sorted(source_raw_candidate_ids - source_candidate_ids)
            raise ScreeningSnapshotUnionError(
                "source snapshot raw artifacts lack source-local candidate owners: "
                + ", ".join(orphan_ids)
            )
        marker_present = any(
            field in manifest
            for field in (
                "provisional_frontier",
                "final_cohort_eligible",
                "full_source_terminal",
            )
        )
        if marker_present:
            if (
                manifest.get("provisional_frontier") is not True
                or manifest.get("final_cohort_eligible") is not False
                or manifest.get("full_source_terminal") is not False
            ):
                raise ScreeningSnapshotUnionError(
                    "source snapshot has contradictory provisional lineage"
                )
            provisional_union = True
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
                "stage_commitments": manifest.get("stage_commitments", {}),
            }
        )
        source_raw_by_candidate: dict[str, list[UnionRawArtifact]] = {}
        for artifact in source_raw:
            source_raw_by_candidate.setdefault(artifact.candidate_id, []).append(
                artifact
            )
            key = (artifact.candidate_id, artifact.sha256, artifact.byte_count)
            prior_artifact = raw_by_commitment.get(key)
            if prior_artifact is None or _retrieved_at(artifact) < _retrieved_at(
                prior_artifact
            ):
                raw_by_commitment[key] = artifact
        for candidate in source_candidates:
            observations_by_candidate.setdefault(candidate.candidate_id, []).append(
                _SourceTerminalObservation(
                    candidate=candidate,
                    source_manifest_sha256=manifest_sha256,
                    source_snapshot_id=_string(
                        manifest.get("snapshot_id"), "source snapshot ID"
                    ),
                    source_batch_id=_string(
                        manifest.get("batch_id"), "source batch ID"
                    ),
                    raw_artifacts=tuple(
                        sorted(
                            source_raw_by_candidate.get(candidate.candidate_id, ()),
                            key=lambda artifact: (
                                artifact.sha256,
                                artifact.byte_count,
                                artifact.retrieved_at,
                            ),
                        )
                    ),
                    strict_screen_history=strict_screen_history.get(
                        candidate.candidate_id, ()
                    ),
                )
            )
    candidate_by_id, active_raw_overrides, longitudinal_corrections = (
        _reconcile_terminal_observations(
            observations_by_candidate,
            correction_pins=correction_pins,
            archived_raw_by_commitment=raw_by_commitment,
        )
    )
    raw_artifacts = tuple(raw_by_commitment[key] for key in sorted(raw_by_commitment))
    canonical_raw_artifacts = _canonical_raw_observations(
        raw_artifacts,
        candidates=candidate_by_id,
        active_raw_overrides=active_raw_overrides,
    )
    stage_commitment = {
        "schema_version": "legalforecast.screening_snapshot_union_inputs.v2",
        "expected_cycle_hash": expected_cycle_hash,
        "source_count": len(source_commitments),
        "sources": source_commitments,
        "candidate_count": len(candidate_by_id),
        "raw_artifact_count": len(raw_by_commitment),
        "canonical_raw_artifact_count": len(canonical_raw_artifacts),
        "canonical_raw_selection_policy": "terminal_authority_bound_raw_v2",
        "canonical_raw_artifacts": [
            {
                "candidate_id": artifact.candidate_id,
                "sha256": artifact.sha256,
                "byte_count": artifact.byte_count,
                "retrieved_at": artifact.retrieved_at,
            }
            for artifact in canonical_raw_artifacts
        ],
        "longitudinal_correction_policy": (
            "explicit_candidate_source_manifest_unique_active_v1"
        ),
        "longitudinal_correction_count": len(longitudinal_corrections),
        "longitudinal_corrections": list(longitudinal_corrections),
    }
    if provisional_union:
        stage_commitment.update(
            {
                "provisional_frontier": True,
                "final_cohort_eligible": False,
                "full_source_terminal": False,
            }
        )
    return ScreeningSnapshotUnion(
        candidates=tuple(candidate_by_id[key] for key in sorted(candidate_by_id)),
        raw_artifacts=raw_artifacts,
        canonical_raw_artifacts=canonical_raw_artifacts,
        longitudinal_observations=tuple(
            observation
            for correction in longitudinal_corrections
            for observation in cast(list[Mapping[str, Any]], correction["observations"])
        ),
        stage_commitment=stage_commitment,
    )


def _terminal_correction_pins(
    candidate_ids: Sequence[str], source_manifest_sha256: Sequence[str]
) -> Mapping[str, str]:
    if len(candidate_ids) != len(source_manifest_sha256):
        raise ScreeningSnapshotUnionError(
            "terminal correction candidate and source-manifest pins must be paired"
        )
    pins: dict[str, str] = {}
    for candidate_id, manifest_sha256 in zip(
        candidate_ids, source_manifest_sha256, strict=True
    ):
        normalized_candidate_id = _string(
            candidate_id, "terminal correction candidate ID"
        )
        normalized_manifest_sha256 = _string(
            manifest_sha256, "terminal correction source manifest SHA-256"
        )
        if re.fullmatch(r"[0-9a-f]{64}", normalized_manifest_sha256) is None:
            raise ScreeningSnapshotUnionError(
                "terminal correction source manifest SHA-256 must be lowercase hex"
            )
        if normalized_candidate_id in pins:
            raise ScreeningSnapshotUnionError(
                f"duplicate terminal correction pin: {normalized_candidate_id}"
            )
        pins[normalized_candidate_id] = normalized_manifest_sha256
    return pins


def _reconcile_terminal_observations(
    observations_by_candidate: Mapping[str, Sequence[_SourceTerminalObservation]],
    *,
    correction_pins: Mapping[str, str],
    archived_raw_by_commitment: Mapping[tuple[str, str, int], UnionRawArtifact],
) -> tuple[
    dict[str, UnionCandidate],
    dict[str, UnionRawArtifact],
    tuple[Mapping[str, Any], ...],
]:
    conflicts = {
        candidate_id
        for candidate_id, observations in observations_by_candidate.items()
        if len({_terminal_commitment(item.candidate) for item in observations}) > 1
    }
    missing_pins = conflicts - set(correction_pins)
    if missing_pins:
        raise ScreeningSnapshotUnionError(
            "terminal evidence conflict requires an explicit authenticated "
            "correction source: " + ", ".join(sorted(missing_pins))
        )
    if set(correction_pins) != conflicts:
        raise ScreeningSnapshotUnionError(
            "terminal correction pins do not exactly match terminal conflicts"
        )

    candidates: dict[str, UnionCandidate] = {}
    active_raw_overrides: dict[str, UnionRawArtifact] = {}
    corrections: list[Mapping[str, Any]] = []
    for candidate_id in sorted(observations_by_candidate):
        observations = tuple(observations_by_candidate[candidate_id])
        commitment_groups: dict[str, list[_SourceTerminalObservation]] = {}
        for observation in observations:
            commitment_groups.setdefault(
                _terminal_commitment(observation.candidate), []
            ).append(observation)
        if len(commitment_groups) == 1:
            canonical = min(observations, key=lambda item: item.source_manifest_sha256)
            candidates[candidate_id] = canonical.candidate
            if canonical.candidate.state != "excluded":
                raw_commitment_sets = {
                    _raw_commitment_set(item.raw_artifacts) for item in observations
                }
                if len(raw_commitment_sets) != 1:
                    raise ScreeningSnapshotUnionError(
                        "active candidate has non-identical raw-artifact commitments: "
                        f"{candidate_id}"
                    )
            continue

        authoritative_manifest = correction_pins[candidate_id]
        authoritative = [
            item
            for item in observations
            if item.source_manifest_sha256 == authoritative_manifest
        ]
        if len(authoritative) != 1:
            raise ScreeningSnapshotUnionError(
                "terminal correction source does not uniquely own candidate: "
                f"{candidate_id}"
            )
        canonical = authoritative[0]
        active_groups = {
            commitment: tuple(items)
            for commitment, items in commitment_groups.items()
            if items[0].candidate.state in {"accepted", "newly_free"}
        }
        if len(active_groups) > 1:
            raise ScreeningSnapshotUnionError(
                "multiple non-identical active terminal proofs: " + candidate_id
            )
        if active_groups:
            active_commitment, active_observations = next(iter(active_groups.items()))
            if _terminal_commitment(canonical.candidate) != active_commitment:
                raise ScreeningSnapshotUnionError(
                    "terminal correction cannot select an exclusion over a unique "
                    f"active proof: {candidate_id}"
                )
            _validate_active_correction(canonical)
            active_raw_sets = {
                _raw_commitment_set(item.raw_artifacts) for item in active_observations
            }
            if len(active_raw_sets) != 1 or len(canonical.raw_artifacts) != 1:
                raise ScreeningSnapshotUnionError(
                    "active correction lacks exactly one source-bound raw artifact: "
                    f"{candidate_id}"
                )
            active_raw_overrides[candidate_id] = _archived_raw_artifact(
                canonical.raw_artifacts[0],
                archived_raw_by_commitment=archived_raw_by_commitment,
            )
        candidates[candidate_id] = canonical.candidate
        corrections.append(
            {
                "candidate_id": candidate_id,
                "canonical_source_manifest_sha256": authoritative_manifest,
                "canonical_terminal_sha256": hashlib.sha256(
                    _terminal_commitment(canonical.candidate).encode()
                ).hexdigest(),
                "observations": [
                    _source_observation_record(
                        item,
                        canonical=(
                            item.source_manifest_sha256 == authoritative_manifest
                        ),
                        archived_raw_by_commitment=archived_raw_by_commitment,
                    )
                    for item in sorted(
                        observations,
                        key=lambda item: item.source_manifest_sha256,
                    )
                ],
            }
        )
    return candidates, active_raw_overrides, tuple(corrections)


def _terminal_commitment(candidate: UnionCandidate) -> str:
    return _canonical_json(
        {
            "state": candidate.state,
            "reason_code": candidate.reason_code,
            "evidence": candidate.evidence,
        }
    )


def _raw_commitment_set(
    artifacts: Sequence[UnionRawArtifact],
) -> frozenset[tuple[str, int]]:
    return frozenset((artifact.sha256, artifact.byte_count) for artifact in artifacts)


def _validate_active_correction(observation: _SourceTerminalObservation) -> None:
    candidate = observation.candidate
    allowed = (
        candidate.state == "accepted"
        and candidate.reason_code == "strict_clean_screen_passed"
    ) or (
        candidate.state == "newly_free"
        and candidate.reason_code in {"newly_free", "required_documents_newly_free"}
    )
    if not allowed:
        raise ScreeningSnapshotUnionError(
            "active correction lacks an independently qualifying strict screen: "
            f"{candidate.candidate_id}"
        )
    evidence_records = (
        (candidate.evidence,)
        if candidate.state == "accepted"
        else observation.strict_screen_history
    )
    errors: list[str] = []
    for evidence in evidence_records:
        try:
            validate_strict_screen_evidence(evidence)
        except StrictScreenEvidenceError as error:
            errors.append(str(error))
        else:
            return
    detail = errors[-1] if errors else "no prior strict-screen evidence"
    raise ScreeningSnapshotUnionError(
        "active correction lacks an independently qualifying strict screen: "
        f"{candidate.candidate_id}: {detail}"
    )


def _source_observation_record(
    observation: _SourceTerminalObservation,
    *,
    canonical: bool,
    archived_raw_by_commitment: Mapping[tuple[str, str, int], UnionRawArtifact],
) -> Mapping[str, Any]:
    candidate = observation.candidate
    return {
        "candidate_id": candidate.candidate_id,
        "source_manifest_sha256": observation.source_manifest_sha256,
        "source_snapshot_id": observation.source_snapshot_id,
        "source_batch_id": observation.source_batch_id,
        "canonical_terminal_observation": canonical,
        "state": candidate.state,
        "reason_code": candidate.reason_code,
        "evidence": dict(candidate.evidence),
        "terminal_sha256": hashlib.sha256(
            _terminal_commitment(candidate).encode()
        ).hexdigest(),
        "raw_artifacts": [
            {
                "sha256": archived.sha256,
                "byte_count": archived.byte_count,
                "retrieved_at": archived.retrieved_at,
                "source_retrieved_at": artifact.retrieved_at,
            }
            for artifact in observation.raw_artifacts
            for archived in (
                _archived_raw_artifact(
                    artifact,
                    archived_raw_by_commitment=archived_raw_by_commitment,
                ),
            )
        ],
    }


def _archived_raw_artifact(
    artifact: UnionRawArtifact,
    *,
    archived_raw_by_commitment: Mapping[tuple[str, str, int], UnionRawArtifact],
) -> UnionRawArtifact:
    try:
        return archived_raw_by_commitment[
            (artifact.candidate_id, artifact.sha256, artifact.byte_count)
        ]
    except KeyError as error:
        raise ScreeningSnapshotUnionError(
            "source raw observation is absent from the authenticated archive: "
            f"{artifact.candidate_id}"
        ) from error


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


def _strict_screen_history(
    path: Path,
) -> Mapping[str, tuple[Mapping[str, Any], ...]]:
    history: dict[str, list[Mapping[str, Any]]] = {}
    for row_number, record in enumerate(_jsonl(path), start=1):
        if (
            record.get("state") != "accepted"
            or record.get("reason_code") != "strict_clean_screen_passed"
        ):
            continue
        candidate_id = _string(
            record.get("candidate_id"),
            f"observation row {row_number} candidate_id",
        )
        evidence = record.get("evidence")
        if not isinstance(evidence, Mapping):
            raise ScreeningSnapshotUnionError(
                f"strict-screen observation for {candidate_id} lacks evidence"
            )
        history.setdefault(candidate_id, []).append(cast(Mapping[str, Any], evidence))
    return {candidate_id: tuple(records) for candidate_id, records in history.items()}


def _raw_records(path: Path) -> tuple[UnionRawArtifact, ...]:
    artifacts: list[UnionRawArtifact] = []
    for row_number, record in enumerate(_jsonl(path), start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"raw row {row_number} candidate_id"
        )
        raw_path = _canonical_absolute_path(
            record.get("path"), f"raw row {row_number} path"
        )
        try:
            is_regular = stat.S_ISREG(raw_path.lstat().st_mode)
        except OSError as error:
            raise ScreeningSnapshotUnionError(
                f"raw artifact is not a canonical regular file for {candidate_id}"
            ) from error
        if not is_regular:
            raise ScreeningSnapshotUnionError(
                f"raw artifact is not a canonical regular file for {candidate_id}"
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
        _validate_raw_artifact_ownership(
            candidate_id=candidate_id,
            raw_path=raw_path,
            sha256=digest,
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


def _validate_raw_artifact_ownership(
    *, candidate_id: str, raw_path: Path, sha256: str
) -> None:
    """Bind direct and union-owned docket HTML paths to their candidate."""

    direct_stems = {candidate_id}
    namespaced = re.fullmatch(
        r"courtlistener-docket-(?P<docket_id>[0-9]+)", candidate_id
    )
    if namespaced is not None:
        direct_stems.add(namespaced.group("docket_id"))
    direct_layout = raw_path.suffix == ".html" and raw_path.stem in direct_stems
    union_layout = (
        raw_path.name == f"{sha256}.html" and raw_path.parent.name == candidate_id
    )
    if not direct_layout and not union_layout:
        raise ScreeningSnapshotUnionError(
            "raw artifact candidate/path ownership mismatch for "
            f"{candidate_id}: {raw_path}"
        )


def _canonical_raw_observations(
    artifacts: Sequence[UnionRawArtifact],
    *,
    candidates: Mapping[str, UnionCandidate],
    active_raw_overrides: Mapping[str, UnionRawArtifact],
) -> tuple[UnionRawArtifact, ...]:
    by_candidate: dict[str, list[UnionRawArtifact]] = {}
    for artifact in artifacts:
        by_candidate.setdefault(artifact.candidate_id, []).append(artifact)
    canonical: list[UnionRawArtifact] = []
    for candidate_id in sorted(by_candidate):
        versions = sorted(
            by_candidate[candidate_id],
            key=lambda artifact: (_retrieved_at(artifact), artifact.sha256),
        )
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise ScreeningSnapshotUnionError(
                f"raw artifact has no terminal candidate owner: {candidate_id}"
            )
        for earlier, later in pairwise(versions):
            if _retrieved_at(earlier) == _retrieved_at(later):
                raise ScreeningSnapshotUnionError(
                    "distinct raw observations have an ambiguous equal retrieval "
                    f"timestamp for {candidate_id}"
                )
        if candidate.state != "excluded":
            override = active_raw_overrides.get(candidate_id)
            if override is not None:
                if not any(
                    artifact.sha256 == override.sha256
                    and artifact.byte_count == override.byte_count
                    for artifact in versions
                ):
                    raise ScreeningSnapshotUnionError(
                        "active correction raw artifact is absent from archive: "
                        f"{candidate_id}"
                    )
                canonical.append(override)
                continue
            if len(versions) > 1:
                raise ScreeningSnapshotUnionError(
                    "active candidate has non-identical raw-artifact commitments: "
                    f"{candidate_id}"
                )
        canonical.append(versions[0])
    return tuple(canonical)


def _retrieved_at(artifact: UnionRawArtifact) -> datetime:
    try:
        parsed = datetime.fromisoformat(artifact.retrieved_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ScreeningSnapshotUnionError(
            f"raw artifact retrieved_at is invalid for {artifact.candidate_id}"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ScreeningSnapshotUnionError(
            f"raw artifact retrieved_at must be UTC for {artifact.candidate_id}"
        )
    return parsed


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


def _preflight_raw_paths(path: Path) -> None:
    for row_number, record in enumerate(_jsonl(path), start=1):
        _canonical_absolute_path(record.get("path"), f"raw row {row_number} path")


def _canonical_absolute_path(value: object, label: str) -> Path:
    path = Path(_string(value, label))
    if not path.is_absolute():
        raise ScreeningSnapshotUnionError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ScreeningSnapshotUnionError(
            f"{label} must be an existing canonical absolute path without symlinks"
        ) from error
    if path != resolved:
        raise ScreeningSnapshotUnionError(
            f"{label} must be an existing canonical absolute path without symlinks"
        )
    return path


def _canonical_snapshot_directory(path: Path, label: str) -> Path:
    lexical = path if path.is_absolute() else Path.cwd() / path
    try:
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ScreeningSnapshotUnionError(
            f"{label} must be an existing canonical directory without symlinks"
        ) from error
    if lexical != resolved or lexical.is_symlink() or not lexical.is_dir():
        raise ScreeningSnapshotUnionError(
            f"{label} must be an existing canonical directory without symlinks"
        )
    return lexical


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScreeningSnapshotUnionError(f"{label} is required")
    return value.strip()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

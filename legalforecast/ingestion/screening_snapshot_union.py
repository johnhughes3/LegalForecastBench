"""Provider-free union of complete saturated screening snapshots."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    SCHEMA_VERSION,
    SnapshotVerificationError,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    FirecrawlScreeningIdentityError,
    snapshot_firecrawl_screening_source_count,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)


class ScreeningSnapshotUnionError(ValueError):
    """Raised when source snapshots cannot form an exact terminal union."""


_SNAPSHOT_FILES = (
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
)
LONGITUDINAL_CORRECTION_POLICY_V1 = (
    "explicit_candidate_source_manifest_unique_active_v1"
)
LONGITUDINAL_CORRECTION_POLICY_V2 = (
    "explicit_candidate_source_manifest_unique_raw_backed_active_v2"
)
RAWLESS_ACTIVE_REPROOF_POLICY = (
    "unique_raw_backed_authority_over_authenticated_rawless_exact310_reproof_v1"
)
RAWLESS_DIRECT_REST_ACTIVE_PROOF_POLICY = (
    "unique_raw_backed_authority_over_authenticated_rawless_direct_rest_proof_v1"
)


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
    source_batch_digest: str
    source_candidate_count: int
    source_stage_commitments: Mapping[str, Any]
    raw_artifacts: tuple[UnionRawArtifact, ...]
    strict_screen_history: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ScreeningSnapshotUnion:
    candidates: tuple[UnionCandidate, ...]
    raw_artifacts: tuple[UnionRawArtifact, ...]
    canonical_raw_artifacts: tuple[UnionRawArtifact, ...]
    longitudinal_observations: tuple[Mapping[str, Any], ...]
    stage_commitment: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _VerifiedSourceSnapshot:
    manifest: Mapping[str, Any]
    manifest_sha256: str
    candidates: tuple[UnionCandidate, ...]
    strict_screen_history: Mapping[str, tuple[Mapping[str, Any], ...]]
    raw_artifacts: tuple[UnionRawArtifact, ...]


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
    firecrawl_screening_source_count = 0
    for snapshot, expected_manifest_hash in zip(
        snapshots, expected_manifest_sha256, strict=True
    ):
        verified_source = _load_verified_source_snapshot(
            snapshot,
            expected_manifest_sha256=expected_manifest_hash,
            expected_cycle_hash=expected_cycle_hash,
        )
        manifest_path = snapshot / "manifest.json"
        manifest = verified_source.manifest
        manifest_sha256 = verified_source.manifest_sha256
        try:
            firecrawl_screening_source_count += (
                snapshot_firecrawl_screening_source_count(
                    cast(Mapping[str, object], manifest),
                    require_current=True,
                )
            )
        except FirecrawlScreeningIdentityError as exc:
            raise ScreeningSnapshotUnionError(str(exc)) from exc
        source_candidates = verified_source.candidates
        strict_screen_history = verified_source.strict_screen_history
        source_raw = verified_source.raw_artifacts
        source_terminal_raw = _source_terminal_raw_artifacts(
            manifest,
            candidates=source_candidates,
            raw_artifacts=source_raw,
        )
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
                "candidate_count": len(source_candidates),
                "raw_artifact_count": len(source_raw),
                "stage_commitments": manifest.get("stage_commitments", {}),
            }
        )
        source_stage_commitments = manifest.get("stage_commitments")
        if not isinstance(source_stage_commitments, Mapping):
            raise ScreeningSnapshotUnionError(
                f"source snapshot stage commitments are invalid: {snapshot}"
            )
        source_terminal_raw_by_candidate: dict[str, list[UnionRawArtifact]] = {}
        for artifact in source_terminal_raw:
            source_terminal_raw_by_candidate.setdefault(
                artifact.candidate_id, []
            ).append(artifact)
        for artifact in source_raw:
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
                    source_batch_digest=batch_digest,
                    source_candidate_count=len(source_candidates),
                    source_stage_commitments=cast(
                        Mapping[str, Any], source_stage_commitments
                    ),
                    raw_artifacts=tuple(
                        sorted(
                            source_terminal_raw_by_candidate.get(
                                candidate.candidate_id, ()
                            ),
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
            expected_cycle_hash=expected_cycle_hash,
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
        "firecrawl_screening_source_count": firecrawl_screening_source_count,
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
        "longitudinal_correction_policy": LONGITUDINAL_CORRECTION_POLICY_V2,
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


def _source_terminal_raw_artifacts(
    manifest: Mapping[str, Any],
    *,
    candidates: Sequence[UnionCandidate],
    raw_artifacts: Sequence[UnionRawArtifact],
) -> tuple[UnionRawArtifact, ...]:
    """Project a nested union's archived raw history to its terminal authority."""

    stage_commitments_value = manifest.get("stage_commitments")
    if not isinstance(stage_commitments_value, Mapping):
        raise ScreeningSnapshotUnionError(
            "source snapshot stage commitments are invalid"
        )
    stage_commitments = cast(Mapping[str, Any], stage_commitments_value)
    union_value = stage_commitments.get("screening_snapshot_union_inputs")
    if union_value is None:
        return tuple(raw_artifacts)
    if not isinstance(union_value, Mapping):
        raise ScreeningSnapshotUnionError(
            "nested screening union commitment is invalid"
        )
    union = cast(Mapping[str, Any], union_value)
    canonical_value = union.get("canonical_raw_artifacts")
    if not isinstance(canonical_value, list):
        raise ScreeningSnapshotUnionError(
            "nested screening union raw authority is invalid"
        )
    canonical_rows = cast(list[object], canonical_value)
    if (
        union.get("schema_version")
        != "legalforecast.screening_snapshot_union_inputs.v2"
        or union.get("candidate_count") != len(candidates)
        or union.get("raw_artifact_count") != len(raw_artifacts)
        or union.get("canonical_raw_selection_policy")
        != "terminal_authority_bound_raw_v2"
        or union.get("canonical_raw_artifact_count") != len(canonical_rows)
    ):
        raise ScreeningSnapshotUnionError(
            "nested screening union raw authority is invalid"
        )
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    raw_by_commitment = {
        (
            artifact.candidate_id,
            artifact.sha256,
            artifact.byte_count,
            artifact.retrieved_at,
        ): artifact
        for artifact in raw_artifacts
    }
    raw_candidate_ids = {artifact.candidate_id for artifact in raw_artifacts}
    canonical_by_candidate: dict[str, UnionRawArtifact] = {}
    for index, value in enumerate(canonical_rows, start=1):
        if not isinstance(value, Mapping):
            raise ScreeningSnapshotUnionError(
                f"nested screening union canonical raw row {index} is invalid"
            )
        row = cast(Mapping[str, object], value)
        if set(row) != {"candidate_id", "sha256", "byte_count", "retrieved_at"}:
            raise ScreeningSnapshotUnionError(
                f"nested screening union canonical raw row {index} is invalid"
            )
        candidate_id = row.get("candidate_id")
        sha256 = row.get("sha256")
        byte_count = row.get("byte_count")
        retrieved_at = row.get("retrieved_at")
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in candidates_by_id
            or candidate_id in canonical_by_candidate
            or not isinstance(sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or not isinstance(retrieved_at, str)
        ):
            raise ScreeningSnapshotUnionError(
                f"nested screening union canonical raw row {index} is invalid"
            )
        artifact = raw_by_commitment.get(
            (candidate_id, sha256, byte_count, retrieved_at)
        )
        if artifact is None:
            raise ScreeningSnapshotUnionError(
                f"nested screening union canonical raw row {index} is unbound"
            )
        canonical_by_candidate[candidate_id] = artifact
    if set(canonical_by_candidate) != raw_candidate_ids:
        raise ScreeningSnapshotUnionError(
            "nested screening union canonical raw ownership is incomplete"
        )
    return tuple(
        artifact
        for candidate_id in sorted(candidates_by_id)
        for artifact in (
            (canonical_by_candidate[candidate_id],)
            if (
                candidates_by_id[candidate_id].state != "excluded"
                and candidate_id in canonical_by_candidate
            )
            else tuple(
                sorted(
                    (
                        item
                        for item in raw_artifacts
                        if item.candidate_id == candidate_id
                    ),
                    key=lambda item: (
                        _retrieved_at(item),
                        item.sha256,
                    ),
                )
            )
        )
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
    expected_cycle_hash: str,
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
                if len(raw_commitment_sets) != 1 or len(canonical.raw_artifacts) > 1:
                    raise ScreeningSnapshotUnionError(
                        "active candidate has non-identical raw-artifact commitments: "
                        f"{candidate_id}"
                    )
                if canonical.raw_artifacts:
                    active_raw_overrides[candidate_id] = _archived_raw_artifact(
                        canonical.raw_artifacts[0],
                        archived_raw_by_commitment=archived_raw_by_commitment,
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
        rawless_active_reproofs: tuple[_SourceTerminalObservation, ...] = ()
        rawless_active_reproof_policy: str | None = None
        if len(active_groups) > 1:
            (
                rawless_active_reproofs,
                rawless_active_reproof_policy,
            ) = _authenticated_rawless_active_reproofs(
                canonical,
                active_groups=active_groups,
                expected_cycle_hash=expected_cycle_hash,
            )
            if not rawless_active_reproofs:
                raise ScreeningSnapshotUnionError(
                    "multiple non-identical active terminal proofs: " + candidate_id
                )
            canonical_commitment = _terminal_commitment(canonical.candidate)
            active_groups = {
                canonical_commitment: active_groups[canonical_commitment],
            }
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
        correction: dict[str, Any] = {
            "candidate_id": candidate_id,
            "canonical_source_manifest_sha256": authoritative_manifest,
            "canonical_terminal_sha256": hashlib.sha256(
                _terminal_commitment(canonical.candidate).encode()
            ).hexdigest(),
            "observations": [
                _source_observation_record(
                    item,
                    canonical=(item.source_manifest_sha256 == authoritative_manifest),
                    archived_raw_by_commitment=archived_raw_by_commitment,
                )
                for item in sorted(
                    observations,
                    key=lambda item: item.source_manifest_sha256,
                )
            ],
        }
        if rawless_active_reproofs:
            correction["active_reproof_reconciliation"] = {
                "policy": rawless_active_reproof_policy,
                "rawless_source_manifest_sha256": sorted(
                    item.source_manifest_sha256 for item in rawless_active_reproofs
                ),
            }
        corrections.append(correction)
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
            validate_strict_screen_evidence(
                evidence,
                expected_candidate_id=candidate.candidate_id,
            )
        except StrictScreenEvidenceError as error:
            errors.append(str(error))
        else:
            return
    detail = errors[-1] if errors else "no prior strict-screen evidence"
    raise ScreeningSnapshotUnionError(
        "active correction lacks an independently qualifying strict screen: "
        f"{candidate.candidate_id}: {detail}"
    )


def _authenticated_rawless_active_reproofs(
    canonical: _SourceTerminalObservation,
    *,
    active_groups: Mapping[str, Sequence[_SourceTerminalObservation]],
    expected_cycle_hash: str,
) -> tuple[tuple[_SourceTerminalObservation, ...], str | None]:
    """Return authenticated rawless same-disposition proofs and their policy."""

    if (
        canonical.candidate.state != "accepted"
        or canonical.candidate.reason_code != "strict_clean_screen_passed"
        or len(canonical.raw_artifacts) != 1
    ):
        return (), None
    canonical_commitment = _terminal_commitment(canonical.candidate)
    canonical_group = active_groups.get(canonical_commitment)
    if canonical_group is None:
        return (), None
    canonical_raw_set = _raw_commitment_set(canonical.raw_artifacts)
    if len(canonical_raw_set) != 1 or any(
        _raw_commitment_set(item.raw_artifacts) != canonical_raw_set
        for item in canonical_group
    ):
        return (), None
    rawless: list[_SourceTerminalObservation] = []
    policies: set[str] = set()
    for commitment, observations in active_groups.items():
        if commitment == canonical_commitment:
            continue
        for observation in observations:
            base_matches = (
                observation.candidate.state != "accepted"
                or observation.candidate.reason_code != "strict_clean_screen_passed"
                or observation.raw_artifacts
            )
            if base_matches:
                return (), None
            exact310_matches = authenticated_rawless_active_reproof_matches(
                canonical.candidate.evidence,
                observation.candidate.evidence,
                expected_candidate_id=canonical.candidate.candidate_id,
                expected_cycle_hash=expected_cycle_hash,
                reproof_source_manifest_sha256=(observation.source_manifest_sha256),
                reproof_source_batch_id=observation.source_batch_id,
                reproof_source_batch_digest=observation.source_batch_digest,
                reproof_source_candidate_count=(observation.source_candidate_count),
                reproof_source_stage_commitments=(observation.source_stage_commitments),
            )
            direct_rest_matches = _canonical_current_firecrawl_stage_matches(
                canonical
            ) and authenticated_rawless_direct_rest_active_proof_matches(
                canonical.candidate.evidence,
                observation.candidate.evidence,
                expected_candidate_id=canonical.candidate.candidate_id,
                reproof_source_manifest_sha256=(observation.source_manifest_sha256),
                reproof_source_batch_id=observation.source_batch_id,
                reproof_source_batch_digest=observation.source_batch_digest,
                reproof_source_candidate_count=(observation.source_candidate_count),
                reproof_source_stage_commitments=(observation.source_stage_commitments),
            )
            if exact310_matches == direct_rest_matches:
                return (), None
            try:
                _validate_active_correction(observation)
            except ScreeningSnapshotUnionError:
                return (), None
            policies.add(
                RAWLESS_ACTIVE_REPROOF_POLICY
                if exact310_matches
                else RAWLESS_DIRECT_REST_ACTIVE_PROOF_POLICY
            )
            rawless.append(observation)
    if len(policies) != 1:
        return (), None
    return tuple(rawless), policies.pop()


def _canonical_current_firecrawl_stage_matches(
    canonical: _SourceTerminalObservation,
) -> bool:
    implementation_value = canonical.source_stage_commitments.get(
        "firecrawl_screening_implementation"
    )
    if not isinstance(implementation_value, Mapping):
        return False
    implementation = cast(Mapping[str, Any], implementation_value)
    return (
        implementation.get("schema_version")
        == "legalforecast.firecrawl_screening_implementation.v1"
    )


def authenticated_rawless_active_reproof_matches(
    canonical_evidence: Mapping[str, Any],
    reproof_evidence: Mapping[str, Any],
    *,
    expected_candidate_id: str,
    expected_cycle_hash: str,
    reproof_source_manifest_sha256: str,
    reproof_source_batch_id: str,
    reproof_source_batch_digest: str,
    reproof_source_candidate_count: int,
    reproof_source_stage_commitments: Mapping[str, Any],
) -> bool:
    """Recognize one rawless exact310 reproof of the same strict disposition."""

    policy_rebind_value = reproof_evidence.get("policy_rebind")
    if not isinstance(policy_rebind_value, Mapping):
        return False
    policy_rebind = cast(Mapping[str, Any], policy_rebind_value)
    required_rebind_fields = {
        "strategy": "authenticated_strict_evidence_reproof_v1",
        "current_policy_proof_available": True,
        "raw_artifact_count": 0,
        "source_state": "accepted",
        "source_reason_code": "strict_clean_screen_passed",
    }
    if any(
        policy_rebind.get(field) != expected
        for field, expected in required_rebind_fields.items()
    ):
        return False
    for field in (
        "source_cycle_hash",
        "source_snapshot_manifest_sha256",
        "source_observation_sha256",
        "target_cycle_hash",
    ):
        value = policy_rebind.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            return False
    source_batch_id = policy_rebind.get("source_batch_id")
    if not isinstance(source_batch_id, str) or not source_batch_id:
        return False
    if not _authenticated_exact310_reproof_stage_matches(
        policy_rebind,
        expected_cycle_hash=expected_cycle_hash,
        reproof_source_manifest_sha256=reproof_source_manifest_sha256,
        reproof_source_batch_id=reproof_source_batch_id,
        reproof_source_batch_digest=reproof_source_batch_digest,
        reproof_source_candidate_count=reproof_source_candidate_count,
        reproof_source_stage_commitments=reproof_source_stage_commitments,
    ):
        return False
    try:
        validate_strict_screen_evidence(
            canonical_evidence,
            expected_candidate_id=expected_candidate_id,
        )
        validate_strict_screen_evidence(
            reproof_evidence,
            expected_candidate_id=expected_candidate_id,
        )
    except StrictScreenEvidenceError:
        return False
    return _strict_disposition_fingerprint(
        canonical_evidence,
        expected_candidate_id=expected_candidate_id,
    ) == _strict_disposition_fingerprint(
        reproof_evidence,
        expected_candidate_id=expected_candidate_id,
    )


def authenticated_rawless_direct_rest_active_proof_matches(
    canonical_evidence: Mapping[str, Any],
    reproof_evidence: Mapping[str, Any],
    *,
    expected_candidate_id: str,
    reproof_source_manifest_sha256: str,
    reproof_source_batch_id: str,
    reproof_source_batch_digest: str,
    reproof_source_candidate_count: int,
    reproof_source_stage_commitments: Mapping[str, Any],
) -> bool:
    """Recognize one rawless direct-REST proof of the same strict disposition."""

    if not _authenticated_direct_rest_stage_matches(
        reproof_source_manifest_sha256=reproof_source_manifest_sha256,
        reproof_source_batch_id=reproof_source_batch_id,
        reproof_source_batch_digest=reproof_source_batch_digest,
        reproof_source_candidate_count=reproof_source_candidate_count,
        reproof_source_stage_commitments=reproof_source_stage_commitments,
    ):
        return False
    try:
        validate_strict_screen_evidence(
            canonical_evidence,
            expected_candidate_id=expected_candidate_id,
        )
        validate_strict_screen_evidence(
            reproof_evidence,
            expected_candidate_id=expected_candidate_id,
        )
    except StrictScreenEvidenceError:
        return False
    return _strict_disposition_fingerprint(
        canonical_evidence,
        expected_candidate_id=expected_candidate_id,
    ) == _strict_disposition_fingerprint(
        reproof_evidence,
        expected_candidate_id=expected_candidate_id,
    )


def _authenticated_direct_rest_stage_matches(
    *,
    reproof_source_manifest_sha256: str,
    reproof_source_batch_id: str,
    reproof_source_batch_digest: str,
    reproof_source_candidate_count: int,
    reproof_source_stage_commitments: Mapping[str, Any],
) -> bool:
    """Bind a rawless proof to one complete source-neutral REST snapshot."""

    return (
        re.fullmatch(r"[0-9a-f]{64}", reproof_source_manifest_sha256) is not None
        and bool(reproof_source_batch_id)
        and re.fullmatch(r"[0-9a-f]{64}", reproof_source_batch_digest) is not None
        and reproof_source_candidate_count > 0
        and reproof_source_stage_commitments
        == {
            "courtlistener_rest_screen_inputs": {
                "schema_version": "legalforecast.courtlistener_rest_screen_inputs.v1"
            }
        }
    )


def _authenticated_exact310_reproof_stage_matches(
    policy_rebind: Mapping[str, Any],
    *,
    expected_cycle_hash: str,
    reproof_source_manifest_sha256: str,
    reproof_source_batch_id: str,
    reproof_source_batch_digest: str,
    reproof_source_candidate_count: int,
    reproof_source_stage_commitments: Mapping[str, Any],
) -> bool:
    """Bind a rawless policy proof to one authenticated exact310 snapshot."""

    if (
        re.fullmatch(r"[0-9a-f]{64}", reproof_source_manifest_sha256) is None
        or re.fullmatch(r"[0-9a-f]{64}", reproof_source_batch_digest) is None
        or reproof_source_candidate_count <= 0
    ):
        return False
    expected_fields = {
        "stage": "exact310-terminal-rest-policy-rebind",
        "source_cycle_hash": policy_rebind.get("source_cycle_hash"),
        "source_batch_id": policy_rebind.get("source_batch_id"),
        "source_snapshot_manifest_sha256": policy_rebind.get(
            "source_snapshot_manifest_sha256"
        ),
        "target_cycle_hash": expected_cycle_hash,
        "target_batch_id": reproof_source_batch_id,
        "target_batch_digest": reproof_source_batch_digest,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    if any(
        reproof_source_stage_commitments.get(field) != expected
        for field, expected in expected_fields.items()
    ):
        return False
    if policy_rebind.get("target_cycle_hash") != expected_cycle_hash:
        return False
    for field in (
        "contract_sha256",
        "source_candidate_set_sha256",
        "source_observations_sha256",
        "target_outcomes_sha256",
        "target_seed_summary_sha256",
        "transfer_receipt_sha256",
    ):
        value = reproof_source_stage_commitments.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            return False
    counts: list[int] = []
    for field in (
        "preserve_current_count",
        "reprove_current_count",
        "reprove_exclusion_count",
        "fail_closed_count",
    ):
        value = reproof_source_stage_commitments.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return False
        counts.append(value)
    return (
        reproof_source_stage_commitments.get("reprove_current_count", 0) > 0
        and sum(counts) == reproof_source_candidate_count
    )


def _strict_disposition_fingerprint(
    evidence: Mapping[str, Any],
    *,
    expected_candidate_id: str,
) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    if evidence.get("candidate_id") != expected_candidate_id:
        return None
    disposition_date = evidence.get("first_written_mtd_disposition_date")
    ai_value = evidence.get("ai")
    if not isinstance(disposition_date, str) or not isinstance(ai_value, Mapping):
        return None
    ai = cast(Mapping[str, Any], ai_value)
    motion_entries = ai.get("target_motion_entry_numbers")
    decision_entries = ai.get("decision_entry_numbers")
    if not isinstance(motion_entries, list) or not isinstance(decision_entries, list):
        return None
    typed_motion_entries = cast(list[object], motion_entries)
    typed_decision_entries = cast(list[object], decision_entries)
    if not typed_motion_entries or not typed_decision_entries:
        return None
    if not all(isinstance(value, (str, int)) for value in typed_motion_entries):
        return None
    if not all(isinstance(value, (str, int)) for value in typed_decision_entries):
        return None
    return (
        disposition_date,
        tuple(sorted(str(value) for value in typed_motion_entries)),
        tuple(sorted(str(value) for value in typed_decision_entries)),
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


def _load_verified_source_snapshot(
    snapshot: Path,
    *,
    expected_manifest_sha256: str,
    expected_cycle_hash: str,
) -> _VerifiedSourceSnapshot:
    """Authenticate one immutable byte set and consume only those buffers."""

    manifest_path = snapshot / "manifest.json"
    manifest_payload = _read_regular_file(manifest_path, "source manifest")
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise ScreeningSnapshotUnionError(
            f"source snapshot manifest SHA-256 mismatch: {manifest_path}"
        )
    manifest = _json_object_payload(manifest_payload, "source manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotVerificationError("snapshot schema version mismatch")
    if manifest.get("complete") is not True:
        raise SnapshotVerificationError("snapshot is not complete")
    if manifest.get("saturated") is not True:
        raise SnapshotVerificationError("snapshot discovery is not saturated")
    if manifest.get("cycle_hash") != expected_cycle_hash:
        raise SnapshotVerificationError("snapshot cycle hash mismatch")
    parsed_files = manifest.get("files")
    if not isinstance(parsed_files, Mapping):
        raise SnapshotVerificationError("snapshot file manifest is incomplete")
    file_commitments = cast(Mapping[str, object], parsed_files)
    if set(file_commitments) != set(_SNAPSHOT_FILES):
        raise SnapshotVerificationError("snapshot file manifest is incomplete")
    payloads: dict[str, bytes] = {}
    for filename in _SNAPSHOT_FILES:
        parsed_commitment = file_commitments[filename]
        if not isinstance(parsed_commitment, Mapping):
            raise SnapshotVerificationError(f"invalid commitment for {filename}")
        commitment = cast(Mapping[str, object], parsed_commitment)
        try:
            payload = _read_regular_file(
                snapshot / filename,
                f"snapshot file {filename}",
            )
        except ScreeningSnapshotUnionError as error:
            cause = error.__cause__
            if not isinstance(cause, OSError) or cause.errno != errno.ENOENT:
                raise
            raise SnapshotVerificationError(
                f"missing snapshot file {filename}"
            ) from error
        if (
            commitment.get("sha256") != hashlib.sha256(payload).hexdigest()
            or commitment.get("byte_count") != len(payload)
            or commitment.get("row_count") != payload.count(b"\n")
        ):
            raise SnapshotVerificationError(
                f"snapshot file commitment mismatch: {filename}"
            )
        payloads[filename] = payload

    screened = _jsonl_payload(payloads["screened-cases.jsonl"], "screened-cases.jsonl")
    exclusions = _jsonl_payload(payloads["exclusions.jsonl"], "exclusions.jsonl")
    candidate_rows = _jsonl_payload(payloads["candidates.jsonl"], "candidates.jsonl")
    observation_rows = _jsonl_payload(
        payloads["observations.jsonl"], "observations.jsonl"
    )
    raw_rows = _jsonl_payload(payloads["raw-artifacts.jsonl"], "raw-artifacts.jsonl")
    summary = _json_object_payload(payloads["summary.json"], "snapshot summary")
    _verify_buffered_snapshot_reconciliation(
        screened=screened,
        exclusions=exclusions,
        candidates=candidate_rows,
        observations=observation_rows,
        raw_artifacts=raw_rows,
        summary=summary,
    )
    return _VerifiedSourceSnapshot(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        candidates=_candidate_records(candidate_rows),
        strict_screen_history=_strict_screen_history(observation_rows),
        raw_artifacts=_raw_records(raw_rows),
    )


def _verify_buffered_snapshot_reconciliation(
    *,
    screened: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    raw_artifacts: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    screened_ids = _snapshot_candidate_ids(screened, "screened-cases.jsonl")
    exclusion_ids = _snapshot_candidate_ids(exclusions, "exclusions.jsonl")
    candidate_ids = _snapshot_candidate_ids(candidates, "candidates.jsonl")
    overlap = screened_ids & exclusion_ids
    if overlap:
        raise SnapshotVerificationError(
            "accepted and excluded candidate IDs overlap: " + ", ".join(sorted(overlap))
        )
    accepted_candidate_ids: set[str] = set()
    excluded_candidate_ids: set[str] = set()
    for candidate in candidates:
        candidate_id = cast(str, candidate["candidate_id"])
        state = candidate.get("state")
        if state in {"accepted", "newly_free"}:
            accepted_candidate_ids.add(candidate_id)
        elif state == "excluded":
            excluded_candidate_ids.add(candidate_id)
        else:
            raise SnapshotVerificationError(
                f"candidates.jsonl contains invalid canonical state for {candidate_id}"
            )
    if (
        candidate_ids != screened_ids | exclusion_ids
        or accepted_candidate_ids != screened_ids
        or excluded_candidate_ids != exclusion_ids
    ):
        raise SnapshotVerificationError(
            "candidate IDs and states do not reconcile with screened cases and "
            "exclusions"
        )
    _require_snapshot_links(observations, "observations.jsonl", candidate_ids)
    _require_snapshot_links(raw_artifacts, "raw-artifacts.jsonl", candidate_ids)
    accepted_count = len(screened_ids)
    excluded_count = len(exclusion_ids)
    if (
        summary.get("accepted_count") != accepted_count
        or summary.get("excluded_count") != excluded_count
        or summary.get("processed_count") != accepted_count + excluded_count
        or summary.get("reconciliation_complete") is not True
    ):
        raise SnapshotVerificationError("snapshot summary counts do not reconcile")


def _snapshot_candidate_ids(
    records: Sequence[Mapping[str, Any]], filename: str
) -> set[str]:
    candidate_ids: set[str] = set()
    for record in records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise SnapshotVerificationError(
                f"{filename} contains a missing candidate_id"
            )
        if candidate_id in candidate_ids:
            raise SnapshotVerificationError(
                f"{filename} contains duplicate candidate_id {candidate_id}"
            )
        candidate_ids.add(candidate_id)
    return candidate_ids


def _require_snapshot_links(
    records: Sequence[Mapping[str, Any]],
    filename: str,
    candidate_ids: set[str],
) -> None:
    for record in records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise SnapshotVerificationError(
                f"{filename} contains a missing candidate_id"
            )
        if candidate_id not in candidate_ids:
            raise SnapshotVerificationError(
                f"{filename} references unknown candidate_id {candidate_id}"
            )


def _candidate_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[UnionCandidate, ...]:
    candidates: list[UnionCandidate] = []
    for row_number, record in enumerate(records, start=1):
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
    records: Sequence[Mapping[str, Any]],
) -> Mapping[str, tuple[Mapping[str, Any], ...]]:
    history: dict[str, list[Mapping[str, Any]]] = {}
    for row_number, record in enumerate(records, start=1):
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


def _raw_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[UnionRawArtifact, ...]:
    artifacts: list[UnionRawArtifact] = []
    for row_number, record in enumerate(records, start=1):
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


def _jsonl_payload(payload: bytes, label: str) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for row_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ScreeningSnapshotUnionError(
                f"invalid JSON in {label} row {row_number}"
            ) from error
        if not isinstance(value, dict):
            raise ScreeningSnapshotUnionError(
                f"non-object JSON in {label} row {row_number}"
            )
        records.append(cast(dict[str, Any], value))
    return records


def _json_object_payload(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SnapshotVerificationError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise SnapshotVerificationError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _read_regular_file(path: Path, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        detail = (
            f"errno {error.errno}: {error.strerror}"
            if error.errno is not None
            else str(error)
        )
        raise ScreeningSnapshotUnionError(
            f"{label} is not a regular file: {path} ({detail})"
        ) from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ScreeningSnapshotUnionError(f"{label} is not a regular file: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


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

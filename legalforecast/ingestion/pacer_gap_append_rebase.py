"""Authenticate append-only screening-snapshot growth for bridge checkpoint reuse."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import verify_snapshot
from legalforecast.ingestion.screening_snapshot_union import (
    LONGITUDINAL_CORRECTION_POLICY_V1,
    LONGITUDINAL_CORRECTION_POLICY_V2,
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_UNION_COMMITMENT = "screening_snapshot_union_inputs"


class AppendOnlyPacerGapRebaseError(ValueError):
    """Raised when snapshot growth cannot authorize checkpoint reuse."""


@dataclass(frozen=True, slots=True)
class AppendOnlySnapshotProof:
    """Verified relationship between an earlier snapshot and a later union."""

    cycle_hash: str
    previous_manifest_sha256: str
    current_manifest_sha256: str
    previous_candidate_count: int
    current_candidate_count: int
    added_candidate_ids: tuple[str, ...]
    invalidated_candidate_ids: tuple[str, ...]
    retained_candidate_count: int
    previous_manifest_in_current_ancestry: bool
    union_source_manifest_sha256: tuple[str, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": ("legalforecast.pacer_gap_append_only_snapshot_proof.v1"),
            "cycle_hash": self.cycle_hash,
            "previous_manifest_sha256": self.previous_manifest_sha256,
            "current_manifest_sha256": self.current_manifest_sha256,
            "previous_candidate_count": self.previous_candidate_count,
            "current_candidate_count": self.current_candidate_count,
            "added_candidate_count": len(self.added_candidate_ids),
            "added_candidate_ids": list(self.added_candidate_ids),
            "invalidated_candidate_count": len(self.invalidated_candidate_ids),
            "invalidated_candidate_ids": list(self.invalidated_candidate_ids),
            "retained_candidate_count": self.retained_candidate_count,
            "previous_manifest_in_current_ancestry": (
                self.previous_manifest_in_current_ancestry
            ),
            "union_source_manifest_sha256": list(self.union_source_manifest_sha256),
        }


def verify_append_only_snapshot_union(
    *,
    previous_snapshot: Path,
    expected_previous_manifest_sha256: str,
    current_snapshot: Path,
    expected_current_manifest_sha256: str,
    expected_added_candidate_ids: Sequence[str],
    expected_invalidated_candidate_ids: Sequence[str] = (),
) -> AppendOnlySnapshotProof:
    """Verify exact candidate/raw preservation through a same-cycle union.

    The current snapshot must be an actual ``union-screening-snapshots`` output,
    and its recursively authenticated union ancestry must contain the exact
    previous manifest unless the caller explicitly pins policy-replay
    invalidations. Every retained prior candidate terminal record and raw-byte
    commitment must survive unchanged. The caller pins the complete added and
    invalidated ID sets externally so a larger-than-reviewed change cannot
    silently gain reuse authority.
    """

    previous = _snapshot_directory(previous_snapshot, "previous snapshot")
    current = _snapshot_directory(current_snapshot, "current snapshot")
    if previous == current:
        raise AppendOnlyPacerGapRebaseError(
            "append-only proof requires distinct previous and current snapshots"
        )
    previous_hash = _manifest_hash(
        previous, expected_previous_manifest_sha256, "previous snapshot"
    )
    current_hash = _manifest_hash(
        current, expected_current_manifest_sha256, "current snapshot"
    )
    previous_manifest = _verified_manifest(previous)
    current_manifest = _verified_manifest(current)
    previous_cycle = _required_sha256(
        previous_manifest.get("cycle_hash"), "previous snapshot cycle hash"
    )
    current_cycle = _required_sha256(
        current_manifest.get("cycle_hash"), "current snapshot cycle hash"
    )
    if previous_cycle != current_cycle:
        raise AppendOnlyPacerGapRebaseError(
            "append-only snapshots do not share one cycle hash"
        )
    _reject_provisional(previous_manifest, "previous snapshot")
    _reject_provisional(current_manifest, "current snapshot")

    current_union = _union_commitment(current_manifest, "current snapshot")
    direct_sources = _union_sources(current_union, "current snapshot")
    correction_candidate_ids, correction_source_hashes = _union_correction_pins(
        current_union,
        "current snapshot",
    )
    direct_paths = tuple(
        _manifest_parent(source, label="current union source")
        for source in direct_sources
    )
    direct_hashes = tuple(
        _required_sha256(
            source.get("manifest_sha256"), "current union source manifest SHA-256"
        )
        for source in direct_sources
    )
    try:
        reconstructed = load_screening_snapshot_union(
            direct_paths,
            expected_manifest_sha256=direct_hashes,
            expected_cycle_hash=current_cycle,
            expected_terminal_correction_candidate_id=correction_candidate_ids,
            expected_terminal_correction_source_manifest_sha256=(
                correction_source_hashes
            ),
        )
    except ScreeningSnapshotUnionError as exc:
        raise AppendOnlyPacerGapRebaseError(
            f"current snapshot union inputs are invalid: {exc}"
        ) from exc
    reconstructed_commitment = _commitment_for_schema(
        reconstructed.stage_commitment,
        schema_version=_required_text(
            current_union.get("schema_version"),
            "current snapshot union schema version",
        ),
    )
    if _canonical_json(reconstructed_commitment) != _canonical_json(current_union):
        raise AppendOnlyPacerGapRebaseError(
            "current snapshot union commitment does not reconstruct exactly"
        )

    ancestry_hashes = _verified_union_ancestry(
        current,
        expected_cycle_hash=current_cycle,
        active=set(),
        verified=set(),
    )
    expected_added = _expected_ids(
        expected_added_candidate_ids,
        label="added candidate ID",
        require_nonempty=True,
    )
    expected_invalidated = _expected_ids(
        expected_invalidated_candidate_ids,
        label="invalidated candidate ID",
        require_nonempty=False,
    )
    overlap = set(expected_added) & set(expected_invalidated)
    if overlap:
        raise AppendOnlyPacerGapRebaseError(
            "added and invalidated candidate pins overlap: "
            + ", ".join(sorted(overlap))
        )
    previous_in_ancestry = previous_hash in ancestry_hashes
    if not previous_in_ancestry and not expected_invalidated:
        raise AppendOnlyPacerGapRebaseError(
            "previous snapshot manifest is not in current union ancestry"
        )

    previous_candidates = _records_by_id(
        previous / "candidates.jsonl", source="previous snapshot candidates"
    )
    current_candidates = _records_by_id(
        current / "candidates.jsonl", source="current snapshot candidates"
    )
    invalidated = set(previous_candidates) - set(current_candidates)
    previous_raw = _raw_commitments(previous / "raw-artifacts.jsonl")
    current_raw = _raw_commitments(current / "raw-artifacts.jsonl")
    for candidate_id, previous_record in previous_candidates.items():
        current_record = current_candidates.get(candidate_id)
        if current_record is None:
            continue
        previous_terminal = {
            field: previous_record.get(field)
            for field in ("state", "reason_code", "evidence")
        }
        current_terminal = {
            field: current_record.get(field)
            for field in ("state", "reason_code", "evidence")
        }
        if _canonical_json(previous_terminal) != _canonical_json(
            current_terminal
        ) or previous_raw.get(candidate_id, ()) != current_raw.get(candidate_id, ()):
            invalidated.add(candidate_id)
    actual_invalidated = tuple(sorted(invalidated))
    if actual_invalidated != expected_invalidated:
        raise AppendOnlyPacerGapRebaseError(
            "current snapshot invalidated candidate IDs do not match the external "
            f"pin: expected {list(expected_invalidated)}, got "
            f"{list(actual_invalidated)}"
        )
    actual_added = tuple(sorted(set(current_candidates) - set(previous_candidates)))
    if actual_added != expected_added:
        raise AppendOnlyPacerGapRebaseError(
            "current snapshot added candidate IDs do not match the external pin: "
            f"expected {list(expected_added)}, got {list(actual_added)}"
        )
    return AppendOnlySnapshotProof(
        cycle_hash=current_cycle,
        previous_manifest_sha256=previous_hash,
        current_manifest_sha256=current_hash,
        previous_candidate_count=len(previous_candidates),
        current_candidate_count=len(current_candidates),
        added_candidate_ids=actual_added,
        invalidated_candidate_ids=actual_invalidated,
        retained_candidate_count=len(previous_candidates) - len(actual_invalidated),
        previous_manifest_in_current_ancestry=previous_in_ancestry,
        union_source_manifest_sha256=direct_hashes,
    )


def verify_screened_case_projection(
    *, snapshot: Path, screened_records: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    """Prove that bridge-visible screened records exactly project accepted evidence."""

    snapshot_path = _snapshot_directory(snapshot, "screening snapshot")
    _verified_manifest(snapshot_path)
    terminal_records = _records_by_id(
        snapshot_path / "candidates.jsonl", source="screening snapshot candidates"
    )
    accepted_evidence: dict[str, Mapping[str, Any]] = {}
    for candidate_id, record in terminal_records.items():
        if record.get("state") != "accepted":
            continue
        evidence = record.get("evidence")
        if not isinstance(evidence, Mapping):
            raise AppendOnlyPacerGapRebaseError(
                f"accepted snapshot candidate lacks evidence: {candidate_id}"
            )
        accepted_evidence[candidate_id] = cast(Mapping[str, Any], evidence)
    screened_by_id: dict[str, Mapping[str, Any]] = {}
    for record in screened_records:
        candidate_id = _screened_candidate_id(record)
        if candidate_id in screened_by_id:
            raise AppendOnlyPacerGapRebaseError(
                f"screened cases repeat candidate {candidate_id}"
            )
        screened_by_id[candidate_id] = record
    if set(screened_by_id) != set(accepted_evidence):
        raise AppendOnlyPacerGapRebaseError(
            "screened cases do not exactly project accepted snapshot candidates"
        )
    for candidate_id, evidence in accepted_evidence.items():
        if _canonical_json(screened_by_id[candidate_id]) != _canonical_json(evidence):
            raise AppendOnlyPacerGapRebaseError(
                f"screened evidence differs from snapshot for {candidate_id}"
            )
    return tuple(sorted(screened_by_id))


def _snapshot_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise AppendOnlyPacerGapRebaseError(f"{label} must be absolute")
    if path.is_symlink() or not path.is_dir():
        raise AppendOnlyPacerGapRebaseError(f"{label} is not a real directory: {path}")
    return path.resolve()


def _manifest_hash(snapshot: Path, expected: str, label: str) -> str:
    expected_hash = _required_sha256(expected, f"{label} expected manifest SHA-256")
    path = snapshot / "manifest.json"
    if path.is_symlink() or not path.is_file():
        raise AppendOnlyPacerGapRebaseError(f"{label} manifest is not regular")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_hash:
        raise AppendOnlyPacerGapRebaseError(f"{label} manifest SHA-256 mismatch")
    return actual


def _verified_manifest(snapshot: Path) -> Mapping[str, Any]:
    try:
        manifest = verify_snapshot(
            snapshot,
            require_complete=True,
            require_saturated=True,
        )
    except Exception as exc:
        raise AppendOnlyPacerGapRebaseError(
            f"snapshot verification failed for {snapshot}: {exc}"
        ) from exc
    return manifest


def _reject_provisional(manifest: Mapping[str, Any], label: str) -> None:
    if (
        manifest.get("provisional_frontier") is True
        or manifest.get("final_cohort_eligible") is False
        or manifest.get("full_source_terminal") is False
    ):
        raise AppendOnlyPacerGapRebaseError(f"{label} is provisional")


def _union_commitment(manifest: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    stage = manifest.get("stage_commitments")
    if not isinstance(stage, Mapping):
        raise AppendOnlyPacerGapRebaseError(f"{label} lacks stage commitments")
    union = cast(Mapping[str, Any], stage).get(_UNION_COMMITMENT)
    if not isinstance(union, Mapping):
        raise AppendOnlyPacerGapRebaseError(
            f"{label} is not a screening snapshot union"
        )
    return cast(Mapping[str, Any], union)


def _union_sources(
    commitment: Mapping[str, Any], label: str
) -> tuple[Mapping[str, Any], ...]:
    if commitment.get("schema_version") not in {
        "legalforecast.screening_snapshot_union_inputs.v1",
        "legalforecast.screening_snapshot_union_inputs.v2",
    }:
        raise AppendOnlyPacerGapRebaseError(f"{label} union schema is unsupported")
    sources = commitment.get("sources")
    if not isinstance(sources, list):
        raise AppendOnlyPacerGapRebaseError(f"{label} union sources are invalid")
    source_values = cast(list[object], sources)
    if len(source_values) < 2:
        raise AppendOnlyPacerGapRebaseError(f"{label} union sources are invalid")
    records: list[Mapping[str, Any]] = []
    for source in source_values:
        if not isinstance(source, Mapping):
            raise AppendOnlyPacerGapRebaseError(
                f"{label} union source is not an object"
            )
        records.append(cast(Mapping[str, Any], source))
    if commitment.get("source_count") != len(records):
        raise AppendOnlyPacerGapRebaseError(f"{label} union source count mismatches")
    return tuple(records)


def _union_correction_pins(
    commitment: Mapping[str, Any], label: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if (
        commitment.get("schema_version")
        == "legalforecast.screening_snapshot_union_inputs.v1"
    ):
        return (), ()
    if commitment.get("longitudinal_correction_policy") not in {
        LONGITUDINAL_CORRECTION_POLICY_V1,
        LONGITUDINAL_CORRECTION_POLICY_V2,
    }:
        raise AppendOnlyPacerGapRebaseError(
            f"{label} union correction policy is unsupported"
        )
    corrections_value = commitment.get("longitudinal_corrections")
    if not isinstance(corrections_value, list):
        raise AppendOnlyPacerGapRebaseError(f"{label} union corrections are invalid")
    corrections = cast(list[object], corrections_value)
    if commitment.get("longitudinal_correction_count") != len(corrections):
        raise AppendOnlyPacerGapRebaseError(
            f"{label} union correction count mismatches"
        )
    pins: dict[str, str] = {}
    for correction in corrections:
        if not isinstance(correction, Mapping):
            raise AppendOnlyPacerGapRebaseError(
                f"{label} union correction is not an object"
            )
        typed_correction = cast(Mapping[str, Any], correction)
        candidate_id = _required_text(
            typed_correction.get("candidate_id"),
            f"{label} union correction candidate ID",
        )
        source_hash = _required_sha256(
            typed_correction.get("canonical_source_manifest_sha256"),
            f"{label} union correction source manifest SHA-256",
        )
        if candidate_id in pins:
            raise AppendOnlyPacerGapRebaseError(
                f"{label} union corrections repeat candidate {candidate_id}"
            )
        pins[candidate_id] = source_hash
    ordered = tuple(sorted(pins.items()))
    return (
        tuple(candidate_id for candidate_id, _source_hash in ordered),
        tuple(source_hash for _candidate_id, source_hash in ordered),
    )


def _commitment_for_schema(
    reconstructed: Mapping[str, Any], *, schema_version: str
) -> Mapping[str, Any]:
    if schema_version == "legalforecast.screening_snapshot_union_inputs.v2":
        return reconstructed
    if schema_version != "legalforecast.screening_snapshot_union_inputs.v1":
        raise AppendOnlyPacerGapRebaseError(
            "current snapshot union schema is unsupported"
        )
    legacy = dict(reconstructed)
    sources_value = legacy.get("sources")
    if not isinstance(sources_value, list):
        raise AppendOnlyPacerGapRebaseError("reconstructed union sources are invalid")
    legacy["schema_version"] = schema_version
    legacy_sources: list[dict[str, Any]] = []
    for source_value in cast(list[object], sources_value):
        if not isinstance(source_value, Mapping):
            raise AppendOnlyPacerGapRebaseError(
                "reconstructed union source is not an object"
            )
        source = cast(Mapping[str, Any], source_value)
        legacy_sources.append(
            {key: value for key, value in source.items() if key != "stage_commitments"}
        )
    legacy["sources"] = legacy_sources
    legacy["canonical_raw_selection_policy"] = (
        "excluded_earliest_authenticated_utc_sha_v1"
    )
    legacy.pop("longitudinal_correction_policy", None)
    legacy.pop("longitudinal_correction_count", None)
    legacy.pop("longitudinal_corrections", None)
    return legacy


def _manifest_parent(source: Mapping[str, Any], *, label: str) -> Path:
    value = source.get("manifest_path")
    if not isinstance(value, str) or not value:
        raise AppendOnlyPacerGapRebaseError(f"{label} path is invalid")
    path = Path(value)
    if not path.is_absolute() or path.name != "manifest.json":
        raise AppendOnlyPacerGapRebaseError(
            f"{label} path is not an absolute manifest path"
        )
    return _snapshot_directory(path.parent, label)


def _verified_union_ancestry(
    snapshot: Path,
    *,
    expected_cycle_hash: str,
    active: set[str],
    verified: set[str],
) -> set[str]:
    manifest = _verified_manifest(snapshot)
    cycle_hash = _required_sha256(
        manifest.get("cycle_hash"), "union ancestry cycle hash"
    )
    if cycle_hash != expected_cycle_hash:
        raise AppendOnlyPacerGapRebaseError("union ancestry crosses cycle identities")
    manifest_hash = hashlib.sha256(
        (snapshot / "manifest.json").read_bytes()
    ).hexdigest()
    if manifest_hash in active:
        raise AppendOnlyPacerGapRebaseError("union ancestry contains a cycle")
    if manifest_hash in verified:
        return {manifest_hash}
    active.add(manifest_hash)
    hashes = {manifest_hash}
    stage = manifest.get("stage_commitments")
    union_value = (
        cast(Mapping[str, Any], stage).get(_UNION_COMMITMENT)
        if isinstance(stage, Mapping)
        else None
    )
    if union_value is None:
        active.remove(manifest_hash)
        verified.add(manifest_hash)
        return hashes
    if not isinstance(union_value, Mapping):
        raise AppendOnlyPacerGapRebaseError("union ancestry commitment is invalid")
    for source in _union_sources(
        cast(Mapping[str, Any], union_value), "union ancestry"
    ):
        source_snapshot = _manifest_parent(source, label="union ancestry source")
        expected_hash = _required_sha256(
            source.get("manifest_sha256"), "union ancestry source manifest SHA-256"
        )
        actual_hash = _manifest_hash(
            source_snapshot, expected_hash, "union ancestry source"
        )
        hashes.add(actual_hash)
        hashes.update(
            _verified_union_ancestry(
                source_snapshot,
                expected_cycle_hash=expected_cycle_hash,
                active=active,
                verified=verified,
            )
        )
    active.remove(manifest_hash)
    verified.add(manifest_hash)
    return hashes


def _records_by_id(path: Path, *, source: str) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for row_number, record in enumerate(_jsonl(path, source=source), start=1):
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AppendOnlyPacerGapRebaseError(
                f"{source} row {row_number} lacks candidate_id"
            )
        if candidate_id in records:
            raise AppendOnlyPacerGapRebaseError(
                f"{source} repeats candidate {candidate_id}"
            )
        records[candidate_id] = record
    return records


def _screened_candidate_id(record: Mapping[str, Any]) -> str:
    candidate = record.get("candidate")
    if not isinstance(candidate, Mapping):
        raise AppendOnlyPacerGapRebaseError("screened case lacks candidate record")
    for field_name in ("docket_id", "candidate_key"):
        value = cast(Mapping[str, Any], candidate).get(field_name)
        if isinstance(value, str) and value:
            return value
    raise AppendOnlyPacerGapRebaseError(
        "screened case lacks candidate docket_id or candidate_key"
    )


def _raw_commitments(path: Path) -> dict[str, tuple[tuple[str, int], ...]]:
    grouped: dict[str, set[tuple[str, int]]] = {}
    for row_number, record in enumerate(
        _jsonl(path, source="snapshot raw artifacts"), start=1
    ):
        candidate_id = record.get("candidate_id")
        sha256 = record.get("sha256")
        byte_count = record.get("byte_count")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(sha256, str)
            or _SHA256_RE.fullmatch(sha256) is None
            or type(byte_count) is not int
            or byte_count < 1
        ):
            raise AppendOnlyPacerGapRebaseError(
                f"snapshot raw artifact row {row_number} is invalid"
            )
        commitment = (sha256, byte_count)
        values = grouped.setdefault(candidate_id, set())
        if commitment in values:
            raise AppendOnlyPacerGapRebaseError(
                f"snapshot repeats raw commitment for {candidate_id}"
            )
        values.add(commitment)
    return {
        candidate_id: tuple(sorted(commitments))
        for candidate_id, commitments in grouped.items()
    }


def _expected_ids(
    values: Sequence[str], *, label: str, require_nonempty: bool
) -> tuple[str, ...]:
    if require_nonempty and not values:
        raise AppendOnlyPacerGapRebaseError(
            f"append-only proof requires externally pinned {label}s"
        )
    if any(not value for value in values):
        raise AppendOnlyPacerGapRebaseError(f"{label} pin is invalid")
    if len(set(values)) != len(values):
        raise AppendOnlyPacerGapRebaseError(f"{label} pins repeat")
    return tuple(sorted(values))


def _jsonl(path: Path, *, source: str) -> tuple[Mapping[str, Any], ...]:
    if path.is_symlink() or not path.is_file():
        raise AppendOnlyPacerGapRebaseError(f"{source} is not a regular file")
    records: list[Mapping[str, Any]] = []
    for row_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AppendOnlyPacerGapRebaseError(
                f"{source} row {row_number} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise AppendOnlyPacerGapRebaseError(
                f"{source} row {row_number} is not an object"
            )
        records.append(cast(Mapping[str, Any], value))
    return tuple(records)


def _required_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise AppendOnlyPacerGapRebaseError(f"{label} is invalid")
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppendOnlyPacerGapRebaseError(f"{label} is invalid")
    return value.strip()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

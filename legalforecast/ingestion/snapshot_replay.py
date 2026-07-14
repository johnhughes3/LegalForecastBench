"""Provider-free, source-bound inputs for superseding-cycle rescreening."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    SnapshotVerificationError,
    verify_snapshot,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SCREEN_RUN_CARD = Path("run-cards/screen-firecrawl-dockets.json")
_ASSEMBLY_RUN_CARD = Path("run-cards/assemble-cycle-acquisition.json")
_FIRECRAWL_SCREEN_INPUT_COMMITMENT_SCHEMA = (
    "legalforecast.firecrawl_screen_input_commitment.v1"
)


class SnapshotReplayError(ValueError):
    """Raised when replay evidence is incomplete, unsafe, or contradictory."""


@dataclass(frozen=True, slots=True)
class ReplaySuccess:
    """One verified successful docket fetch and its immutable raw commitment."""

    candidate_id: str
    docket_id: str
    record: Mapping[str, Any]
    raw_path: Path
    raw_sha256: str
    raw_byte_count: int


@dataclass(frozen=True, slots=True)
class ReplayExclusion:
    """One verified fetch exclusion without a raw docket artifact."""

    candidate_id: str
    record: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ReplaySourceSnapshot:
    """Verified source snapshot and the screen inputs that created it."""

    path: Path
    manifest: Mapping[str, Any]
    manifest_sha256: str
    screen_run_card: Path
    screen_run_card_sha256: str


@dataclass(frozen=True, slots=True)
class SnapshotReplayBundle:
    """Deduplicated inputs ready for one provider-free strict rescreen."""

    successes: tuple[ReplaySuccess, ...]
    exclusions: tuple[ReplayExclusion, ...]
    sources: tuple[ReplaySourceSnapshot, ...]
    source_assembly_run_card: Path
    source_assembly_sha256: str

    @property
    def candidate_count(self) -> int:
        return len(self.successes) + len(self.exclusions)


def collect_snapshot_replay_bundle(
    *,
    source_assembly_run_card: Path,
    expected_source_assembly_sha256: str,
    expected_source_cycle_hash: str,
    additional_source_snapshots: Sequence[Path],
    expected_additional_cycle_hash: str,
) -> SnapshotReplayBundle:
    """Verify and combine historical assembly snapshots without provider access."""

    _require_sha256(expected_source_assembly_sha256, "source assembly SHA-256")
    _require_sha256(expected_source_cycle_hash, "source cycle hash")
    _require_sha256(expected_additional_cycle_hash, "target cycle hash")
    assembly_path = _safe_regular_file(
        source_assembly_run_card, label="source assembly run card"
    )
    assembly_sha256 = _sha256_file(assembly_path)
    if assembly_sha256 != expected_source_assembly_sha256:
        raise SnapshotReplayError(
            "source assembly SHA-256 mismatch: "
            f"expected {expected_source_assembly_sha256}, got {assembly_sha256}"
        )
    assembly_snapshots = _expand_assembly_snapshots(assembly_path)
    if not assembly_snapshots:
        raise SnapshotReplayError("source assembly contains no screening snapshots")
    source_paths: list[tuple[Path, str]] = [
        (path, expected_source_cycle_hash) for path in assembly_snapshots
    ]
    source_paths.extend(
        (path, expected_additional_cycle_hash) for path in additional_source_snapshots
    )

    verified_sources: list[ReplaySourceSnapshot] = []
    ordered_outcomes: list[ReplaySuccess | ReplayExclusion] = []
    seen_snapshots: set[Path] = set()
    for source_path, expected_cycle_hash in source_paths:
        snapshot = _safe_directory(source_path, label="source snapshot")
        if snapshot in seen_snapshots:
            continue
        seen_snapshots.add(snapshot)
        try:
            manifest = verify_snapshot(
                snapshot,
                expected_cycle_hash=expected_cycle_hash,
                require_complete=True,
                require_saturated=True,
            )
        except SnapshotVerificationError as exc:
            message = str(exc)
            if "cycle hash mismatch" in message:
                message = "source snapshot cycle hash mismatch"
            raise SnapshotReplayError(f"{snapshot}: {message}") from exc
        manifest_path = _safe_regular_file(
            snapshot / "manifest.json", label="source snapshot manifest"
        )
        screen_run_card = _source_screen_run_card(snapshot)
        run_card = _read_json_object(screen_run_card, label="screen run card")
        if run_card.get("stage") != "screen-firecrawl-dockets":
            raise SnapshotReplayError(
                f"source screen run card has the wrong stage: {screen_run_card}"
            )
        output_paths = _absolute_run_card_paths(
            run_card.get("output_paths"), "output_paths"
        )
        if snapshot not in {_normalized_resolved_path(value) for value in output_paths}:
            raise SnapshotReplayError(
                "source screen run card does not commit the supplied snapshot: "
                f"{snapshot}"
            )
        input_paths = _absolute_run_card_paths(
            run_card.get("input_paths"), "input_paths"
        )
        if len(input_paths) < 4:
            raise SnapshotReplayError(
                f"source screen run card has incomplete inputs: {screen_run_card}"
            )
        successes_path = _safe_regular_file(
            Path(input_paths[1]), label="source successes JSONL"
        )
        exclusions_path = _safe_regular_file(
            Path(input_paths[2]), label="source fetch exclusions JSONL"
        )
        raw_dir = _safe_directory(Path(input_paths[3]), label="source raw HTML")
        successes = _read_jsonl(successes_path, label="source successes JSONL")
        exclusions = _read_jsonl(exclusions_path, label="source fetch exclusions JSONL")
        _verify_screen_input_commitment(
            manifest=manifest,
            successes=successes,
            exclusions=exclusions,
            snapshot=snapshot,
        )
        snapshot_candidate_ids = {
            _required_text(row, "candidate_id")
            for row in _read_jsonl(
                snapshot / "candidates.jsonl", label="snapshot candidates"
            )
        }
        outcome_ids: set[str] = set()
        for record in successes:
            success = _verified_success(record, raw_dir=raw_dir)
            if success.candidate_id in outcome_ids:
                raise SnapshotReplayError(
                    f"duplicate source outcome for {success.candidate_id} in {snapshot}"
                )
            outcome_ids.add(success.candidate_id)
            ordered_outcomes.append(success)
        for record in exclusions:
            exclusion = ReplayExclusion(
                candidate_id=_required_text(record, "case_id"),
                record=dict(record),
            )
            if exclusion.candidate_id in outcome_ids:
                raise SnapshotReplayError(
                    "duplicate source outcome for "
                    f"{exclusion.candidate_id} in {snapshot}"
                )
            outcome_ids.add(exclusion.candidate_id)
            ordered_outcomes.append(exclusion)
        if outcome_ids != snapshot_candidate_ids:
            missing = sorted(snapshot_candidate_ids - outcome_ids)
            unexpected = sorted(outcome_ids - snapshot_candidate_ids)
            raise SnapshotReplayError(
                "source screen inputs do not reconcile with snapshot candidates: "
                f"missing={missing}, unexpected={unexpected}"
            )
        verified_sources.append(
            ReplaySourceSnapshot(
                path=snapshot,
                manifest=dict(manifest),
                manifest_sha256=_sha256_file(manifest_path),
                screen_run_card=screen_run_card,
                screen_run_card_sha256=_sha256_file(screen_run_card),
            )
        )

    successes_by_candidate: dict[str, ReplaySuccess] = {}
    exclusions_by_candidate: dict[str, ReplayExclusion] = {}
    candidate_by_docket: dict[str, str] = {}
    for outcome in ordered_outcomes:
        if isinstance(outcome, ReplaySuccess):
            prior_docket_candidate = candidate_by_docket.get(outcome.docket_id)
            if (
                prior_docket_candidate is not None
                and prior_docket_candidate != outcome.candidate_id
            ):
                raise SnapshotReplayError(
                    "CourtListener docket ID collision between candidates "
                    f"{prior_docket_candidate} and {outcome.candidate_id}"
                )
            candidate_by_docket[outcome.docket_id] = outcome.candidate_id
            prior = successes_by_candidate.get(outcome.candidate_id)
            if prior is not None and (
                prior.docket_id != outcome.docket_id
                or prior.raw_sha256 != outcome.raw_sha256
                or _canonical_json(prior.record) != _canonical_json(outcome.record)
            ):
                raise SnapshotReplayError(
                    f"conflicting raw artifacts for candidate {outcome.candidate_id}"
                )
            successes_by_candidate[outcome.candidate_id] = prior or outcome
            exclusions_by_candidate.pop(outcome.candidate_id, None)
            continue
        if outcome.candidate_id in successes_by_candidate:
            continue
        prior_exclusion = exclusions_by_candidate.get(outcome.candidate_id)
        if prior_exclusion is not None and (
            _canonical_json(prior_exclusion.record) != _canonical_json(outcome.record)
        ):
            raise SnapshotReplayError(
                f"conflicting fetch exclusions for candidate {outcome.candidate_id}"
            )
        exclusions_by_candidate[outcome.candidate_id] = prior_exclusion or outcome

    return SnapshotReplayBundle(
        successes=tuple(
            successes_by_candidate[candidate_id]
            for candidate_id in sorted(successes_by_candidate)
        ),
        exclusions=tuple(
            exclusions_by_candidate[candidate_id]
            for candidate_id in sorted(exclusions_by_candidate)
        ),
        sources=tuple(verified_sources),
        source_assembly_run_card=assembly_path,
        source_assembly_sha256=assembly_sha256,
    )


def source_replay_commitment(bundle: SnapshotReplayBundle) -> dict[str, object]:
    """Return the ordered cryptographic provenance committed by the target."""

    source_snapshots = [
        {
            "snapshot_id": source.manifest["snapshot_id"],
            "manifest_sha256": source.manifest_sha256,
            "screen_run_card_sha256": source.screen_run_card_sha256,
            "cycle_hash": source.manifest["cycle_hash"],
            "batch_digest": source.manifest["batch_digest"],
        }
        for source in bundle.sources
    ]
    outcomes = [
        {
            "candidate_id": success.candidate_id,
            "outcome_class": "success",
            "record_sha256": hashlib.sha256(
                _canonical_json(success.record).encode()
            ).hexdigest(),
            "raw_sha256": success.raw_sha256,
        }
        for success in bundle.successes
    ]
    outcomes.extend(
        {
            "candidate_id": exclusion.candidate_id,
            "outcome_class": "fetch_exclusion",
            "record_sha256": hashlib.sha256(
                _canonical_json(exclusion.record).encode()
            ).hexdigest(),
        }
        for exclusion in bundle.exclusions
    )
    return {
        "schema_version": "legalforecast.source_bound_snapshot_replay.v1",
        "source_assembly_sha256": bundle.source_assembly_sha256,
        "source_snapshot_count": len(bundle.sources),
        "source_candidate_count": bundle.candidate_count,
        "source_success_count": len(bundle.successes),
        "source_fetch_exclusion_count": len(bundle.exclusions),
        "source_snapshots": source_snapshots,
        "per_candidate_outcome_sha256": hashlib.sha256(
            _canonical_json(outcomes).encode()
        ).hexdigest(),
    }


def _expand_assembly_snapshots(run_card_path: Path) -> tuple[Path, ...]:
    snapshots: list[Path] = []
    seen_run_cards: set[Path] = set()
    seen_roots: set[Path] = set()

    def visit_run_card(path: Path) -> None:
        safe_path = _safe_regular_file(path, label="assembly run card")
        if safe_path in seen_run_cards:
            return
        seen_run_cards.add(safe_path)
        record = _read_json_object(safe_path, label="assembly run card")
        if record.get("stage") != "assemble-cycle-acquisition":
            raise SnapshotReplayError(
                f"source assembly run card has the wrong stage: {safe_path}"
            )
        for raw_input in _absolute_run_card_paths(
            record.get("input_paths"), "input_paths"
        ):
            root = _safe_directory(raw_input, label="assembly input root")
            if root in seen_roots:
                continue
            seen_roots.add(root)
            nested = root / _ASSEMBLY_RUN_CARD
            manifest = root / "manifest.json"
            if nested.is_file():
                visit_run_card(nested)
            elif manifest.is_file():
                snapshots.append(root)
            # Downstream-only component roots intentionally contain neither.

    visit_run_card(run_card_path)
    return tuple(snapshots)


def _source_screen_run_card(snapshot: Path) -> Path:
    candidates = (
        snapshot.parent.parent / _SCREEN_RUN_CARD,
        snapshot.parent.parent.parent / _SCREEN_RUN_CARD,
    )
    for candidate in candidates:
        if candidate.is_file():
            return _safe_regular_file(candidate, label="source screen run card")
    raise SnapshotReplayError(
        f"cannot locate source screen run card for snapshot: {snapshot}"
    )


def _verified_success(record: Mapping[str, Any], *, raw_dir: Path) -> ReplaySuccess:
    candidate_id = _required_text(record, "case_id")
    docket_id = _required_text(record, "docket_id")
    if not docket_id.isdigit():
        raise SnapshotReplayError(f"invalid docket ID for {candidate_id}: {docket_id}")
    if record.get("pagination_complete_for_anchor_window") is not True:
        raise SnapshotReplayError(
            f"source success lacks pagination completeness for {candidate_id}"
        )
    expected_sha256 = _required_text(record, "raw_html_sha256")
    if (
        not expected_sha256.startswith("sha256:")
        or _SHA256.fullmatch(expected_sha256[7:]) is None
    ):
        raise SnapshotReplayError(f"invalid raw SHA-256 for {candidate_id}")
    expected_bytes = record.get("raw_html_bytes")
    if (
        not isinstance(expected_bytes, int)
        or isinstance(expected_bytes, bool)
        or expected_bytes < 0
    ):
        raise SnapshotReplayError(f"invalid raw byte count for {candidate_id}")
    raw_path = _safe_regular_file(
        raw_dir / f"{docket_id}.html", label="source raw HTML"
    )
    if raw_path.parent != raw_dir:
        raise SnapshotReplayError(f"source raw HTML escaped its directory: {raw_path}")
    raw_bytes = raw_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha256 != expected_sha256[7:]:
        raise SnapshotReplayError(
            f"raw artifact sha256 mismatch for candidate {candidate_id}"
        )
    if len(raw_bytes) != expected_bytes:
        raise SnapshotReplayError(
            f"raw artifact byte_count mismatch for candidate {candidate_id}"
        )
    return ReplaySuccess(
        candidate_id=candidate_id,
        docket_id=docket_id,
        record=dict(record),
        raw_path=raw_path,
        raw_sha256=actual_sha256,
        raw_byte_count=expected_bytes,
    )


def read_verified_replay_raw(success: ReplaySuccess) -> bytes:
    """Read one replay artifact and recheck it immediately before publication."""

    raw_path = _safe_regular_file(success.raw_path, label="source raw HTML")
    raw_bytes = raw_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha256 != success.raw_sha256:
        raise SnapshotReplayError(
            f"raw artifact sha256 changed for candidate {success.candidate_id}"
        )
    if len(raw_bytes) != success.raw_byte_count:
        raise SnapshotReplayError(
            f"raw artifact byte_count changed for candidate {success.candidate_id}"
        )
    return raw_bytes


def firecrawl_screen_input_commitments(
    *,
    success_records: Sequence[Mapping[str, Any]],
    fetch_exclusion_records: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Commit normalized screen inputs in the same order as the screening stage."""

    per_record_commitments: list[dict[str, object]] = []
    input_ordinal = 0
    for outcome_class, records in (
        ("success", success_records),
        ("fetch_exclusion", fetch_exclusion_records),
    ):
        for record in records:
            input_ordinal += 1
            candidate_id = _required_text(record, "case_id")
            normalized_record = _canonical_json(dict(record))
            per_record_commitments.append(
                {
                    "candidate_id": candidate_id,
                    "input_ordinal": input_ordinal,
                    "outcome_class": outcome_class,
                    "normalized_record_sha256": hashlib.sha256(
                        normalized_record.encode()
                    ).hexdigest(),
                }
            )
    return {
        "schema_version": _FIRECRAWL_SCREEN_INPUT_COMMITMENT_SCHEMA,
        "input_record_count": len(per_record_commitments),
        "per_candidate_outcome_record_sha256": hashlib.sha256(
            _canonical_json(per_record_commitments).encode()
        ).hexdigest(),
    }


def _verify_screen_input_commitment(
    *,
    manifest: Mapping[str, Any],
    successes: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
    snapshot: Path,
) -> None:
    stage_commitments = manifest.get("stage_commitments")
    if not isinstance(stage_commitments, Mapping):
        raise SnapshotReplayError(
            f"source snapshot lacks screening stage commitments: {snapshot}"
        )
    committed = cast(Mapping[str, object], stage_commitments).get(
        "firecrawl_screen_inputs"
    )
    if not isinstance(committed, Mapping):
        raise SnapshotReplayError(
            f"source snapshot lacks firecrawl_screen_inputs commitment: {snapshot}"
        )
    recomputed = firecrawl_screen_input_commitments(
        success_records=successes,
        fetch_exclusion_records=exclusions,
    )
    if dict(cast(Mapping[str, object], committed)) != recomputed:
        raise SnapshotReplayError(
            f"source screen input commitment mismatch: {snapshot}"
        )


def _safe_regular_file(path: Path, *, label: str) -> Path:
    resolved = _safe_existing_path(path, label=label)
    mode = resolved.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise SnapshotReplayError(f"{label} is not a regular file: {path}")
    return resolved


def _safe_directory(path: Path, *, label: str) -> Path:
    resolved = _safe_existing_path(path, label=label)
    mode = resolved.lstat().st_mode
    if not stat.S_ISDIR(mode):
        raise SnapshotReplayError(f"{label} is not a directory: {path}")
    return resolved


def _safe_existing_path(path: Path, *, label: str) -> Path:
    normalized = Path(os.path.abspath(os.fspath(path)))
    current = Path(normalized.anchor)
    for component in normalized.parts[1:]:
        current /= component
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise SnapshotReplayError(f"cannot access {label}: {path}: {exc}") from exc
        if stat.S_ISLNK(mode) and not _allowed_macos_system_alias(current):
            raise SnapshotReplayError(f"{label} contains a symlink: {path}")
    try:
        return normalized.resolve(strict=True)
    except OSError as exc:
        raise SnapshotReplayError(f"cannot resolve {label}: {path}: {exc}") from exc


def _allowed_macos_system_alias(path: Path) -> bool:
    return sys.platform == "darwin" and path in {
        Path("/etc"),
        Path("/tmp"),
        Path("/var"),
    }


def _normalized_resolved_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path))).resolve()


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        parsed = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotReplayError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SnapshotReplayError(f"{label} must contain a JSON object: {path}")
    return cast(dict[str, Any], parsed)


def _read_jsonl(path: Path, *, label: str) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise SnapshotReplayError(f"cannot read {label}: {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            parsed = cast(object, json.loads(line))
        except json.JSONDecodeError as exc:
            raise SnapshotReplayError(
                f"invalid {label} JSON at line {line_number}: {path}"
            ) from exc
        if not isinstance(parsed, dict):
            raise SnapshotReplayError(
                f"{label} line {line_number} is not an object: {path}"
            )
        records.append(cast(dict[str, Any], parsed))
    return tuple(records)


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SnapshotReplayError(f"missing required replay field {field}")
    return value.strip()


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SnapshotReplayError(f"invalid {field} in source run card")
    items = cast(list[object], value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise SnapshotReplayError(f"invalid {field} in source run card")
    return tuple(cast(list[str], items))


def _absolute_run_card_paths(value: object, field: str) -> tuple[Path, ...]:
    paths = tuple(Path(item) for item in _string_list(value, field))
    relative = tuple(str(path) for path in paths if not path.is_absolute())
    if relative:
        raise SnapshotReplayError(
            f"relative {field} in source run card are not replay-safe: {relative}"
        )
    return paths


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise SnapshotReplayError(f"{label} must be 64 lowercase hexadecimal digits")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

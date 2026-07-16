"""Provider-free, source-bound inputs for superseding-cycle rescreening."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
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
_SNAPSHOT_PAYLOAD_FILES = (
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
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
    raw_bytes: bytes
    source_snapshot_id: str
    source_manifest_sha256: str


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
    input_paths: tuple[Path, ...]
    bundle_root: Path | None


@dataclass(frozen=True, slots=True)
class SupplementalReplaySource:
    """Explicit, hash-bound evidence for one portable supplemental snapshot."""

    snapshot: Path
    expected_cycle_hash: str
    screen_run_card: Path
    expected_screen_run_card_sha256: str
    bundle_root: Path


@dataclass(frozen=True, slots=True)
class VerifiedSupplementalReplaySourceEvidence:
    """One externally hash-bound portable snapshot and all screen inputs."""

    snapshot: Path
    manifest: Mapping[str, Any]
    manifest_bytes: bytes
    snapshot_file_payloads: Mapping[str, bytes]
    manifest_sha256: str
    screen_run_card: Path
    screen_run_card_record: Mapping[str, Any]
    screen_run_card_sha256: str
    success_records: tuple[Mapping[str, Any], ...]
    exclusion_records: tuple[Mapping[str, Any], ...]
    screened_records: tuple[Mapping[str, Any], ...]
    successes: tuple[ReplaySuccess, ...]
    screen_input_commitment: Mapping[str, object]


def verify_supplemental_replay_source_evidence(
    source: SupplementalReplaySource,
    *,
    expected_manifest_sha256: str,
) -> VerifiedSupplementalReplaySourceEvidence:
    """Verify one portable snapshot without combining or replaying its outcomes."""

    _require_sha256(expected_manifest_sha256, "source snapshot manifest SHA-256")
    _require_sha256(source.expected_cycle_hash, "supplemental source cycle hash")
    _require_sha256(
        source.expected_screen_run_card_sha256,
        "supplemental screen run-card SHA-256",
    )
    snapshot = _verified_supplemental_snapshot_path(source)
    screen_run_card = _verified_supplemental_screen_run_card(source)
    manifest_bytes, snapshot_file_payloads = _read_snapshot_payloads(snapshot)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise SnapshotReplayError("source snapshot manifest SHA-256 mismatch")
    run_card, run_card_sha256 = _read_hashed_json_object(
        screen_run_card, label="source screen run card"
    )
    if run_card_sha256 != source.expected_screen_run_card_sha256:
        raise SnapshotReplayError("supplemental screen run-card SHA-256 mismatch")
    if run_card.get("stage") != "screen-firecrawl-dockets":
        raise SnapshotReplayError("source screen run card has the wrong stage")
    input_paths = _absolute_run_card_paths(run_card.get("input_paths"), "input_paths")
    output_paths = _absolute_run_card_paths(
        run_card.get("output_paths"), "output_paths"
    )
    relocated = _relocated_source_paths(
        snapshot=snapshot,
        screen_run_card=screen_run_card,
        input_paths=input_paths,
        output_paths=output_paths,
        supplemental=source,
    )
    manifest = _verify_buffered_snapshot(
        manifest_bytes=manifest_bytes,
        file_payloads=snapshot_file_payloads,
        expected_cycle_hash=source.expected_cycle_hash,
        raw_artifact_relocation=relocated.raw_artifact_relocation,
    )
    if len(relocated.input_paths) < 4:
        raise SnapshotReplayError("source screen run card has incomplete inputs")
    successes_path = _safe_regular_file(
        relocated.input_paths[1], label="source successes JSONL"
    )
    exclusions_path = _safe_regular_file(
        relocated.input_paths[2], label="source fetch exclusions JSONL"
    )
    raw_dir = _safe_directory(relocated.input_paths[3], label="source raw HTML")
    success_records = tuple(_read_jsonl(successes_path, label="source successes JSONL"))
    exclusion_records = tuple(
        _read_jsonl(exclusions_path, label="source fetch exclusions JSONL")
    )
    _verify_screen_input_commitment(
        manifest=manifest,
        successes=success_records,
        exclusions=exclusion_records,
        snapshot=snapshot,
    )
    stage_commitments = manifest.get("stage_commitments")
    if not isinstance(stage_commitments, Mapping):
        raise SnapshotReplayError("source snapshot lacks stage commitments")
    typed_stage_commitments = cast(Mapping[str, object], stage_commitments)
    screen_inputs = typed_stage_commitments.get("firecrawl_screen_inputs")
    if not isinstance(screen_inputs, Mapping):
        raise SnapshotReplayError(
            "source snapshot lacks firecrawl_screen_inputs commitment"
        )
    snapshot_id = _required_text(manifest, "snapshot_id")
    successes: list[ReplaySuccess] = []
    outcome_ids: set[str] = set()
    for record in success_records:
        success = _verified_success(
            record,
            raw_dir=raw_dir,
            source_snapshot_id=snapshot_id,
            source_manifest_sha256=manifest_sha256,
        )
        if success.candidate_id in outcome_ids:
            raise SnapshotReplayError(
                f"duplicate source outcome for {success.candidate_id}"
            )
        outcome_ids.add(success.candidate_id)
        successes.append(success)
    for record in exclusion_records:
        candidate_id = _required_text(record, "case_id")
        if candidate_id in outcome_ids:
            raise SnapshotReplayError(f"duplicate source outcome for {candidate_id}")
        outcome_ids.add(candidate_id)
    snapshot_candidate_ids = {
        _required_text(row, "candidate_id")
        for row in _read_jsonl_payload(
            snapshot_file_payloads["candidates.jsonl"],
            label="source snapshot candidates",
        )
    }
    if outcome_ids != snapshot_candidate_ids:
        raise SnapshotReplayError(
            "source screen inputs do not reconcile with snapshot candidates"
        )
    screened_records = _read_jsonl_payload(
        snapshot_file_payloads["screened-cases.jsonl"],
        label="source screened cases",
    )
    return VerifiedSupplementalReplaySourceEvidence(
        snapshot=snapshot,
        manifest=MappingProxyType(dict(manifest)),
        manifest_bytes=manifest_bytes,
        snapshot_file_payloads=MappingProxyType(dict(snapshot_file_payloads)),
        manifest_sha256=manifest_sha256,
        screen_run_card=screen_run_card,
        screen_run_card_record=dict(run_card),
        screen_run_card_sha256=run_card_sha256,
        success_records=success_records,
        exclusion_records=exclusion_records,
        screened_records=screened_records,
        successes=tuple(successes),
        screen_input_commitment=dict(cast(Mapping[str, object], screen_inputs)),
    )


@dataclass(frozen=True, slots=True)
class SnapshotReplayBundle:
    """Deduplicated inputs ready for one provider-free strict rescreen."""

    successes: tuple[ReplaySuccess, ...]
    exclusions: tuple[ReplayExclusion, ...]
    sources: tuple[ReplaySourceSnapshot, ...]
    source_assembly_run_card: Path
    source_assembly_sha256: str
    source_assembly_run_cards: tuple[Path, ...]
    source_closure_sha256: str
    legacy_screen_input_count: int
    legacy_screen_inputs_sha256: str | None
    refresh_supersessions: tuple[Mapping[str, object], ...]

    @property
    def candidate_count(self) -> int:
        return len(self.successes) + len(self.exclusions)


def collect_snapshot_replay_bundle(
    *,
    source_assembly_run_card: Path,
    expected_source_assembly_sha256: str,
    expected_source_closure_sha256: str,
    expected_source_cycle_hash: str,
    expected_legacy_screen_inputs_sha256: str | None,
    additional_source_snapshots: Sequence[SupplementalReplaySource],
) -> SnapshotReplayBundle:
    """Verify and combine historical assembly snapshots without provider access."""

    _require_sha256(expected_source_assembly_sha256, "source assembly SHA-256")
    _require_sha256(expected_source_closure_sha256, "source closure SHA-256")
    _require_sha256(expected_source_cycle_hash, "source cycle hash")
    if expected_legacy_screen_inputs_sha256 is not None:
        _require_sha256(
            expected_legacy_screen_inputs_sha256,
            "legacy screen-input aggregate SHA-256",
        )
    for source in additional_source_snapshots:
        _require_sha256(source.expected_cycle_hash, "supplemental source cycle hash")
        _require_sha256(
            source.expected_screen_run_card_sha256,
            "supplemental screen run-card SHA-256",
        )
    assembly_path = _safe_regular_file(
        source_assembly_run_card, label="source assembly run card"
    )
    assembly_sha256 = _sha256_file(assembly_path)
    if assembly_sha256 != expected_source_assembly_sha256:
        raise SnapshotReplayError(
            "source assembly SHA-256 mismatch: "
            f"expected {expected_source_assembly_sha256}, got {assembly_sha256}"
        )
    assembly_expansion = _expand_assembly_closure(assembly_path)
    if not assembly_expansion.run_cards or assembly_expansion.run_cards[0] != (
        assembly_path,
        assembly_sha256,
    ):
        raise SnapshotReplayError(
            f"source assembly evidence changed during verification: {assembly_path}"
        )
    assembly_snapshots = assembly_expansion.snapshots
    if not assembly_snapshots:
        raise SnapshotReplayError("source assembly contains no screening snapshots")
    source_paths: list[tuple[Path, str, SupplementalReplaySource | None]] = [
        (path, expected_source_cycle_hash, None) for path in assembly_snapshots
    ]
    source_paths.extend(
        (source.snapshot, source.expected_cycle_hash, source)
        for source in additional_source_snapshots
    )

    prepared_sources: list[
        tuple[Path, str, SupplementalReplaySource | None, Path, str]
    ] = []
    seen_snapshot_cycle_hashes: dict[Path, str] = {}
    for source_path, expected_cycle_hash, supplemental in source_paths:
        snapshot = (
            _verified_supplemental_snapshot_path(supplemental)
            if supplemental is not None
            else _safe_directory(source_path, label="source snapshot")
        )
        prior_expected_cycle_hash = seen_snapshot_cycle_hashes.get(snapshot)
        if (
            prior_expected_cycle_hash is not None
            and prior_expected_cycle_hash != expected_cycle_hash
        ):
            raise SnapshotReplayError(
                "conflicting expected cycle hashes for duplicate source snapshot: "
                f"{snapshot}"
            )
        if prior_expected_cycle_hash is not None:
            raise SnapshotReplayError(
                f"duplicate source snapshot binding is not allowed: {snapshot}"
            )
        seen_snapshot_cycle_hashes[snapshot] = expected_cycle_hash
        manifest_path = _safe_regular_file(
            snapshot / "manifest.json", label="source snapshot manifest"
        )
        prepared_sources.append(
            (
                snapshot,
                expected_cycle_hash,
                supplemental,
                manifest_path,
                _sha256_file(manifest_path),
            )
        )
    source_closure_sha256 = _source_closure_sha256(
        assembly_run_card_sha256=tuple(
            digest for _, digest in assembly_expansion.run_cards
        ),
        source_snapshot_manifest_sha256=tuple(
            manifest_sha256 for *_, manifest_sha256 in prepared_sources
        ),
    )
    if source_closure_sha256 != expected_source_closure_sha256:
        raise SnapshotReplayError(
            "source closure SHA-256 mismatch: expected "
            f"{expected_source_closure_sha256}, got {source_closure_sha256}"
        )

    verified_sources: list[ReplaySourceSnapshot] = []
    ordered_outcomes: list[ReplaySuccess | ReplayExclusion] = []
    legacy_screen_inputs: list[dict[str, object]] = []
    for (
        snapshot,
        expected_cycle_hash,
        supplemental,
        _manifest_path,
        manifest_sha256,
    ) in prepared_sources:
        screen_run_card = (
            _source_screen_run_card(snapshot)
            if supplemental is None
            else _verified_supplemental_screen_run_card(supplemental)
        )
        run_card, screen_run_card_sha256 = _read_hashed_json_object(
            screen_run_card, label="screen run card"
        )
        if (
            supplemental is not None
            and screen_run_card_sha256 != supplemental.expected_screen_run_card_sha256
        ):
            raise SnapshotReplayError(
                "supplemental screen run-card SHA-256 mismatch: expected "
                f"{supplemental.expected_screen_run_card_sha256}, got "
                f"{screen_run_card_sha256}"
            )
        if run_card.get("stage") != "screen-firecrawl-dockets":
            raise SnapshotReplayError(
                f"source screen run card has the wrong stage: {screen_run_card}"
            )
        output_paths = _absolute_run_card_paths(
            run_card.get("output_paths"), "output_paths"
        )
        input_paths = _absolute_run_card_paths(
            run_card.get("input_paths"), "input_paths"
        )
        relocated_paths = _relocated_source_paths(
            snapshot=snapshot,
            screen_run_card=screen_run_card,
            input_paths=input_paths,
            output_paths=output_paths,
            supplemental=supplemental,
        )
        try:
            manifest_bytes, snapshot_file_payloads = _read_snapshot_payloads(snapshot)
            if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
                raise SnapshotReplayError(
                    f"source snapshot manifest changed before verification: {snapshot}"
                )
            manifest = _verify_buffered_snapshot(
                manifest_bytes=manifest_bytes,
                file_payloads=snapshot_file_payloads,
                expected_cycle_hash=expected_cycle_hash,
                raw_artifact_relocation=relocated_paths.raw_artifact_relocation,
            )
        except (SnapshotReplayError, SnapshotVerificationError) as exc:
            message = str(exc)
            if "cycle hash mismatch" in message:
                message = "source snapshot cycle hash mismatch"
            raise SnapshotReplayError(f"{snapshot}: {message}") from exc
        if any(
            field in manifest
            for field in (
                "provisional_frontier",
                "final_cohort_eligible",
                "full_source_terminal",
            )
        ):
            raise SnapshotReplayError(
                "generic snapshot replay rejects provisional sources; use the "
                "terminal exact-subset promotion command with authenticated "
                f"terminal selection evidence: {snapshot}"
            )
        if len(input_paths) < 4:
            raise SnapshotReplayError(
                f"source screen run card has incomplete inputs: {screen_run_card}"
            )
        successes_path = _safe_regular_file(
            relocated_paths.input_paths[1], label="source successes JSONL"
        )
        exclusions_path = _safe_regular_file(
            relocated_paths.input_paths[2], label="source fetch exclusions JSONL"
        )
        raw_dir = _safe_directory(
            relocated_paths.input_paths[3], label="source raw HTML"
        )
        successes = _read_jsonl(successes_path, label="source successes JSONL")
        exclusions = _read_jsonl(exclusions_path, label="source fetch exclusions JSONL")
        input_commitment = _verify_screen_input_commitment(
            manifest=manifest,
            successes=successes,
            exclusions=exclusions,
            snapshot=snapshot,
        )
        if input_commitment is not None:
            legacy_screen_inputs.append(
                {
                    "snapshot_manifest_sha256": manifest_sha256,
                    "screen_run_card_sha256": screen_run_card_sha256,
                    "screen_inputs": input_commitment,
                }
            )
        snapshot_candidate_ids = {
            _required_text(row, "candidate_id")
            for row in _read_jsonl(
                snapshot / "candidates.jsonl", label="snapshot candidates"
            )
        }
        outcome_ids: set[str] = set()
        for record in successes:
            success = _verified_success(
                record,
                raw_dir=raw_dir,
                source_snapshot_id=_required_text(manifest, "snapshot_id"),
                source_manifest_sha256=manifest_sha256,
            )
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
                manifest_sha256=manifest_sha256,
                screen_run_card=screen_run_card,
                screen_run_card_sha256=screen_run_card_sha256,
                input_paths=relocated_paths.input_paths,
                bundle_root=(
                    _declared_bundle_root(supplemental.bundle_root)
                    if supplemental is not None
                    else None
                ),
            )
        )

    successes_by_candidate: dict[str, ReplaySuccess] = {}
    exclusions_by_candidate: dict[str, ReplayExclusion] = {}
    candidate_by_docket: dict[str, str] = {}
    refresh_supersessions: list[Mapping[str, object]] = []
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
            if prior is None:
                successes_by_candidate[outcome.candidate_id] = outcome
            else:
                selected, supersession = _reconcile_success_refresh(prior, outcome)
                successes_by_candidate[outcome.candidate_id] = selected
                if supersession is not None:
                    refresh_supersessions.append(supersession)
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

    legacy_screen_inputs_sha256 = (
        hashlib.sha256(
            _canonical_json(sorted(legacy_screen_inputs, key=_canonical_json)).encode()
        ).hexdigest()
        if legacy_screen_inputs
        else None
    )
    if legacy_screen_inputs_sha256 is not None:
        if expected_legacy_screen_inputs_sha256 is None:
            raise SnapshotReplayError(
                "legacy source snapshots require "
                "--expected-legacy-screen-inputs-sha256; computed "
                f"{legacy_screen_inputs_sha256}"
            )
        if legacy_screen_inputs_sha256 != expected_legacy_screen_inputs_sha256:
            raise SnapshotReplayError(
                "legacy screen-input aggregate SHA-256 mismatch: expected "
                f"{expected_legacy_screen_inputs_sha256}, got "
                f"{legacy_screen_inputs_sha256}"
            )
    elif expected_legacy_screen_inputs_sha256 is not None:
        raise SnapshotReplayError(
            "legacy screen-input aggregate SHA-256 was supplied but no legacy "
            "source snapshots were encountered"
        )
    _recheck_source_closure(
        assembly_run_cards=assembly_expansion.run_cards,
        source_manifests=tuple(
            (manifest_path, manifest_sha256)
            for *_, manifest_path, manifest_sha256 in prepared_sources
        ),
        screen_run_cards=tuple(
            (source.screen_run_card, source.screen_run_card_sha256)
            for source in verified_sources
        ),
    )
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
        source_assembly_run_cards=tuple(
            path for path, _ in assembly_expansion.run_cards
        ),
        source_closure_sha256=source_closure_sha256,
        legacy_screen_input_count=len(legacy_screen_inputs),
        legacy_screen_inputs_sha256=legacy_screen_inputs_sha256,
        refresh_supersessions=tuple(sorted(refresh_supersessions, key=_canonical_json)),
    )


@dataclass(frozen=True, slots=True)
class _RelocatedSourcePaths:
    input_paths: tuple[Path, ...]
    raw_artifact_relocation: tuple[Path, Path] | None


def _verified_supplemental_screen_run_card(
    source: SupplementalReplaySource,
) -> Path:
    return _safe_declared_bundle_member(
        source.screen_run_card,
        label="supplemental screen run card",
        declared_root=source.bundle_root,
        require_directory=False,
    )


def _verified_supplemental_snapshot_path(
    source: SupplementalReplaySource,
) -> Path:
    return _safe_declared_bundle_member(
        source.snapshot,
        label="supplemental snapshot",
        declared_root=source.bundle_root,
        require_directory=True,
    )


def _relocated_source_paths(
    *,
    snapshot: Path,
    screen_run_card: Path,
    input_paths: tuple[Path, ...],
    output_paths: tuple[Path, ...],
    supplemental: SupplementalReplaySource | None,
) -> _RelocatedSourcePaths:
    if supplemental is None:
        if snapshot not in {_normalized_resolved_path(value) for value in output_paths}:
            raise SnapshotReplayError(
                "source screen run card does not commit the supplied snapshot: "
                f"{snapshot}"
            )
        return _RelocatedSourcePaths(
            input_paths=input_paths, raw_artifact_relocation=None
        )

    bundle_root = _declared_bundle_root(supplemental.bundle_root)
    all_committed_paths = tuple(
        Path(os.path.abspath(os.fspath(path))) for path in (*input_paths, *output_paths)
    )
    try:
        original_root = Path(os.path.commonpath(all_committed_paths))
    except ValueError as exc:
        raise SnapshotReplayError(
            "supplemental run-card paths do not share one source root"
        ) from exc
    if original_root == Path(original_root.anchor):
        raise SnapshotReplayError(
            "supplemental run-card paths have an unsafe filesystem-root boundary"
        )

    def relocate(path: Path) -> Path:
        normalized_path = Path(os.path.abspath(os.fspath(path)))
        try:
            relative = normalized_path.relative_to(original_root)
        except ValueError as exc:  # pragma: no cover - guarded by commonpath
            raise SnapshotReplayError(
                f"supplemental run-card path escapes its source root: {path}"
            ) from exc
        relocated = Path(os.path.abspath(os.fspath(bundle_root / relative)))
        if not relocated.is_relative_to(bundle_root):
            raise SnapshotReplayError(
                f"supplemental run-card path escapes its bundle root: {path}"
            )
        return relocated

    relocated_outputs = tuple(
        _safe_bundle_relative_existing_path(
            relocate(path),
            root=bundle_root,
            label="supplemental relocated output",
        )
        for path in output_paths
    )
    if snapshot not in relocated_outputs:
        raise SnapshotReplayError(
            "supplemental screen run card does not commit the supplied snapshot "
            "under its bundle root"
        )
    if not screen_run_card.is_relative_to(bundle_root):
        raise SnapshotReplayError(
            "supplemental screen run card escaped its bundle root"
        )
    return _RelocatedSourcePaths(
        input_paths=tuple(relocate(path) for path in input_paths),
        raw_artifact_relocation=(original_root, bundle_root),
    )


def _reconcile_success_refresh(
    first: ReplaySuccess,
    second: ReplaySuccess,
) -> tuple[ReplaySuccess, Mapping[str, object] | None]:
    volatile_fields = {"raw_html_path", "retrieved_at"}
    refresh_fields = {*volatile_fields, "raw_html_sha256", "raw_html_bytes"}
    if first.docket_id != second.docket_id:
        raise _conflicting_success_error(first.candidate_id)
    if _records_without(first.record, volatile_fields) == _records_without(
        second.record, volatile_fields
    ):
        selected = min((first, second), key=lambda item: _canonical_json(item.record))
        return selected, None
    if not _stable_refresh_identity(first.record, second.record, refresh_fields):
        raise _conflicting_success_error(first.candidate_id)

    first_retrieved_at = _strict_retrieved_at(first)
    second_retrieved_at = _strict_retrieved_at(second)
    if first_retrieved_at == second_retrieved_at:
        raise _conflicting_success_error(first.candidate_id)
    older, newer = (
        (first, second) if first_retrieved_at < second_retrieved_at else (second, first)
    )
    try:
        enriched_rows = _require_monotonic_docket_refresh(older=older, newer=newer)
    except SnapshotReplayError as exc:
        raise _conflicting_success_error(older.candidate_id) from exc
    return newer, {
        "candidate_id": newer.candidate_id,
        "selection_reason": "strict_monotonic_append_only_docket_refresh",
        "older_raw_sha256": older.raw_sha256,
        "older_retrieved_at": _required_text(older.record, "retrieved_at"),
        "older_snapshot_id": older.source_snapshot_id,
        "older_snapshot_manifest_sha256": older.source_manifest_sha256,
        "newer_raw_sha256": newer.raw_sha256,
        "newer_retrieved_at": _required_text(newer.record, "retrieved_at"),
        "newer_snapshot_id": newer.source_snapshot_id,
        "newer_snapshot_manifest_sha256": newer.source_manifest_sha256,
        "older_case_name": _case_metadata_text(older.record, "case_name"),
        "newer_case_name": _case_metadata_text(newer.record, "case_name"),
        "older_source_url": _required_text(older.record, "source_url"),
        "newer_source_url": _required_text(newer.record, "source_url"),
        "enriched_existing_rows": list(enriched_rows),
    }


def _records_without(record: Mapping[str, Any], fields: set[str]) -> Mapping[str, Any]:
    return {key: value for key, value in record.items() if key not in fields}


def _stable_refresh_identity(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    refresh_fields: set[str],
) -> bool:
    presentation_fields = {"source_url", "case_metadata"}
    if _records_without(
        first, refresh_fields | presentation_fields
    ) != _records_without(second, refresh_fields | presentation_fields):
        return False
    first_metadata = first.get("case_metadata")
    second_metadata = second.get("case_metadata")
    if not isinstance(first_metadata, Mapping) or not isinstance(
        second_metadata, Mapping
    ):
        return False
    typed_first_metadata = cast(Mapping[str, Any], first_metadata)
    typed_second_metadata = cast(Mapping[str, Any], second_metadata)
    mutable_metadata_fields = {"case_name", "source_url", "pacer_case_id"}
    if _records_without(
        typed_first_metadata, mutable_metadata_fields
    ) != _records_without(typed_second_metadata, mutable_metadata_fields):
        return False
    for field in ("case_id", "court_id", "docket_number"):
        if _required_text(typed_first_metadata, field) != _required_text(
            typed_second_metadata, field
        ):
            return False
    first_pacer_case_id: object = typed_first_metadata.get("pacer_case_id")
    second_pacer_case_id: object = typed_second_metadata.get("pacer_case_id")
    return not (
        first_pacer_case_id is not None
        and second_pacer_case_id is not None
        and first_pacer_case_id != second_pacer_case_id
    )


def _case_metadata_text(record: Mapping[str, Any], field: str) -> str | None:
    metadata = record.get("case_metadata")
    if not isinstance(metadata, Mapping):
        return None
    typed_metadata = cast(Mapping[str, object], metadata)
    value = typed_metadata.get(field)
    return value if isinstance(value, str) else None


def _strict_retrieved_at(success: ReplaySuccess) -> datetime:
    raw_value = _required_text(success.record, "retrieved_at")
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise _conflicting_success_error(success.candidate_id) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _conflicting_success_error(success.candidate_id)
    return parsed


def _require_monotonic_docket_refresh(
    *, older: ReplaySuccess, newer: ReplaySuccess
) -> tuple[Mapping[str, object], ...]:
    try:
        older_page = parse_courtlistener_docket_html(
            read_verified_replay_raw(older).decode("utf-8"),
            source_url=_required_text(older.record, "source_url"),
            docket_id=older.docket_id,
        )
        newer_page = parse_courtlistener_docket_html(
            read_verified_replay_raw(newer).decode("utf-8"),
            source_url=_required_text(newer.record, "source_url"),
            docket_id=newer.docket_id,
        )
    except (OSError, UnicodeError, CourtListenerWebParseError) as exc:
        raise _conflicting_success_error(older.candidate_id) from exc
    older_entries = {entry.row_id: entry.to_record() for entry in older_page.entries}
    newer_entries = {entry.row_id: entry.to_record() for entry in newer_page.entries}
    if (
        len(older_entries) != len(older_page.entries)
        or len(newer_entries) != len(newer_page.entries)
        or older_page.docket_id != newer_page.docket_id
        or older_page.has_next_page != newer_page.has_next_page
    ):
        raise _conflicting_success_error(older.candidate_id)
    enriched_rows: list[Mapping[str, object]] = []
    newer_entries_by_id = {entry.row_id: entry for entry in newer_page.entries}
    for older_entry in older_page.entries:
        newer_entry = newer_entries_by_id.get(older_entry.row_id)
        if newer_entry is None:
            raise _conflicting_success_error(older.candidate_id)
        enrichment = _verify_entry_transport_enrichment(older_entry, newer_entry)
        if enrichment is not None:
            enriched_rows.append(enrichment)
    return tuple(enriched_rows)


def _verify_entry_transport_enrichment(
    older: CourtListenerWebDocketEntry,
    newer: CourtListenerWebDocketEntry,
) -> Mapping[str, object] | None:
    if older.to_record() == newer.to_record():
        return None
    if (
        older.entry_number != newer.entry_number
        or older.filed_at != newer.filed_at
        or older.restriction_markers != newer.restriction_markers
        or _semantic_entry_narrative(older) != _semantic_entry_narrative(newer)
    ):
        raise SnapshotReplayError("existing docket entry narrative changed")

    newer_documents: dict[tuple[str, str], list[CourtListenerWebDocument]] = {}
    for document in newer.documents:
        newer_documents.setdefault((document.kind, document.description), []).append(
            document
        )
    transport_changes: list[Mapping[str, object]] = []
    for old_document in older.documents:
        identity = (old_document.kind, old_document.description)
        matches = newer_documents.get(identity)
        if not matches:
            raise SnapshotReplayError("existing docket document was removed or renamed")
        new_document = matches.pop(0)
        change = _verified_document_transport_enrichment(old_document, new_document)
        if change is not None:
            transport_changes.append(change)
    return {
        "row_id": older.row_id,
        "old_entry_sha256": hashlib.sha256(
            _canonical_json(older.to_record()).encode()
        ).hexdigest(),
        "new_entry_sha256": hashlib.sha256(
            _canonical_json(newer.to_record()).encode()
        ).hexdigest(),
        "document_transport_changes": transport_changes,
    }


def _verified_document_transport_enrichment(
    older: CourtListenerWebDocument,
    newer: CourtListenerWebDocument,
) -> Mapping[str, object] | None:
    if older.to_record() == newer.to_record():
        return None
    if older.restriction_markers != newer.restriction_markers:
        raise SnapshotReplayError("existing docket document restriction changed")
    if older.pacer_only:
        allowed_href_change = (
            older.href is not None
            and "ecf." in older.href
            and newer.href is not None
            and newer.href.startswith("https://storage.courtlistener.com/recap/")
            and not newer.pacer_only
        )
    else:
        allowed_href_change = older.href == newer.href and not newer.pacer_only
    if not allowed_href_change:
        raise SnapshotReplayError("existing docket document transport did not enrich")
    return {
        "kind": older.kind,
        "description": older.description,
        "old_transport": _document_transport_record(older),
        "new_transport": _document_transport_record(newer),
    }


def _document_transport_record(
    document: CourtListenerWebDocument,
) -> Mapping[str, object]:
    return {
        "href": document.href,
        "action_label": document.action_label,
        "pacer_only": document.pacer_only,
        "freely_available": document.freely_available,
    }


def _semantic_entry_narrative(entry: CourtListenerWebDocketEntry) -> str:
    text = entry.narrative_text if entry.narrative_text is not None else entry.text
    document_tail_start = _document_ui_tail_start(entry, text=text)
    if document_tail_start is not None:
        text = text[:document_tail_start]
    text = re.sub(r"\s*\(Entered:\s*\d{2}/\d{2}/\d{4}\)", "", text)
    attachment_start = text.casefold().find("(attachments:")
    if attachment_start >= 0:
        prefix = text[:attachment_start]
        attachment_suffix = re.sub(r"#\s*(\d+)", r"(\1)", text[attachment_start:])
        text = prefix + attachment_suffix
    text = re.sub(r"\bre\s+\[(\d+)\]", r"re \1", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _document_ui_tail_start(
    entry: CourtListenerWebDocketEntry, *, text: str
) -> int | None:
    """Find a rendered document-card tail only from its full transport signature."""

    if not entry.documents:
        return None
    first_document = entry.documents[0]
    if not first_document.action_label:
        return None
    signature = " ".join(
        value
        for value in (
            first_document.kind,
            first_document.description,
            first_document.action_label,
        )
        if value
    )
    offset = text.find(signature)
    return offset if offset > 0 else None


def _conflicting_success_error(candidate_id: str) -> SnapshotReplayError:
    return SnapshotReplayError(
        f"conflicting raw artifacts for candidate {candidate_id}"
    )


def source_replay_commitment(bundle: SnapshotReplayBundle) -> dict[str, object]:
    """Return the ordered cryptographic provenance committed by the target."""

    source_snapshots = sorted(
        (
            {
                "snapshot_id": source.manifest["snapshot_id"],
                "manifest_sha256": source.manifest_sha256,
                "screen_run_card_sha256": source.screen_run_card_sha256,
                "cycle_hash": source.manifest["cycle_hash"],
                "batch_digest": source.manifest["batch_digest"],
            }
            for source in bundle.sources
        ),
        key=_canonical_json,
    )
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
        "source_closure_sha256": bundle.source_closure_sha256,
        "source_assembly_run_card_count": len(bundle.source_assembly_run_cards),
        "source_snapshot_count": len(bundle.sources),
        "source_candidate_count": bundle.candidate_count,
        "source_success_count": len(bundle.successes),
        "source_fetch_exclusion_count": len(bundle.exclusions),
        "legacy_screen_input_count": bundle.legacy_screen_input_count,
        "legacy_screen_inputs_sha256": bundle.legacy_screen_inputs_sha256,
        "refresh_supersession_count": len(bundle.refresh_supersessions),
        "refresh_supersessions": list(bundle.refresh_supersessions),
        "source_snapshots": source_snapshots,
        "per_candidate_outcome_sha256": hashlib.sha256(
            _canonical_json(outcomes).encode()
        ).hexdigest(),
    }


@dataclass(frozen=True, slots=True)
class _AssemblyExpansion:
    snapshots: tuple[Path, ...]
    run_cards: tuple[tuple[Path, str], ...]


def _expand_assembly_closure(run_card_path: Path) -> _AssemblyExpansion:
    snapshots: list[Path] = []
    seen_run_cards: set[Path] = set()
    run_cards: list[tuple[Path, str]] = []
    seen_roots: set[Path] = set()

    def visit_run_card(path: Path) -> None:
        safe_path = _safe_regular_file(path, label="assembly run card")
        if safe_path in seen_run_cards:
            return
        seen_run_cards.add(safe_path)
        record, run_card_sha256 = _read_hashed_json_object(
            safe_path, label="assembly run card"
        )
        run_cards.append((safe_path, run_card_sha256))
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
    return _AssemblyExpansion(snapshots=tuple(snapshots), run_cards=tuple(run_cards))


def _source_closure_sha256(
    *,
    assembly_run_card_sha256: Sequence[str],
    source_snapshot_manifest_sha256: Sequence[str],
) -> str:
    payload = {
        "schema_version": "legalforecast.replay_source_closure.v1",
        "assembly_run_card_sha256": sorted(assembly_run_card_sha256),
        "source_snapshot_manifest_sha256": sorted(source_snapshot_manifest_sha256),
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _recheck_source_closure(
    *,
    assembly_run_cards: Sequence[tuple[Path, str]],
    source_manifests: Sequence[tuple[Path, str]],
    screen_run_cards: Sequence[tuple[Path, str]],
) -> None:
    for path, expected_sha256 in (
        *assembly_run_cards,
        *source_manifests,
        *screen_run_cards,
    ):
        if _sha256_file(path) != expected_sha256:
            raise SnapshotReplayError(
                f"source closure evidence changed during verification: {path}"
            )


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


def _verified_success(
    record: Mapping[str, Any],
    *,
    raw_dir: Path,
    source_snapshot_id: str,
    source_manifest_sha256: str,
) -> ReplaySuccess:
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
        raw_bytes=raw_bytes,
        source_snapshot_id=source_snapshot_id,
        source_manifest_sha256=source_manifest_sha256,
    )


def read_verified_replay_raw(success: ReplaySuccess) -> bytes:
    """Return the immutable raw buffer authenticated during source verification."""

    actual_sha256 = hashlib.sha256(success.raw_bytes).hexdigest()
    if actual_sha256 != success.raw_sha256:
        raise SnapshotReplayError(
            f"buffered raw artifact sha256 changed for candidate {success.candidate_id}"
        )
    if len(success.raw_bytes) != success.raw_byte_count:
        raise SnapshotReplayError(
            "buffered raw artifact byte_count changed for candidate "
            f"{success.candidate_id}"
        )
    return success.raw_bytes


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
) -> dict[str, object] | None:
    recomputed = firecrawl_screen_input_commitments(
        success_records=successes,
        fetch_exclusion_records=exclusions,
    )
    if "stage_commitments" not in manifest:
        return recomputed
    stage_commitments = manifest["stage_commitments"]
    if not isinstance(stage_commitments, Mapping):
        raise SnapshotReplayError(
            f"source stage commitments have an invalid shape: {snapshot}"
        )
    typed_stage_commitments = cast(Mapping[str, object], stage_commitments)
    if "firecrawl_screen_inputs" not in typed_stage_commitments:
        raise SnapshotReplayError(
            f"source snapshot lacks firecrawl_screen_inputs commitment: {snapshot}"
        )
    committed = typed_stage_commitments["firecrawl_screen_inputs"]
    if not isinstance(committed, Mapping):
        raise SnapshotReplayError(
            f"source screen input commitment has an invalid shape: {snapshot}"
        )
    if dict(cast(Mapping[str, object], committed)) != recomputed:
        raise SnapshotReplayError(
            f"source screen input commitment mismatch: {snapshot}"
        )
    return None


def _read_snapshot_payloads(snapshot: Path) -> tuple[bytes, Mapping[str, bytes]]:
    """Read each committed snapshot payload exactly once into immutable bytes."""

    manifest_path = _safe_regular_file(
        snapshot / "manifest.json", label="source snapshot manifest"
    )
    try:
        manifest_bytes = manifest_path.read_bytes()
        file_payloads = {
            filename: _safe_regular_file(
                snapshot / filename,
                label=f"source snapshot {filename}",
            ).read_bytes()
            for filename in _SNAPSHOT_PAYLOAD_FILES
        }
    except OSError as exc:
        raise SnapshotReplayError(
            f"cannot buffer source snapshot payloads: {snapshot}: {exc}"
        ) from exc
    return manifest_bytes, MappingProxyType(file_payloads)


def _verify_buffered_snapshot(
    *,
    manifest_bytes: bytes,
    file_payloads: Mapping[str, bytes],
    expected_cycle_hash: str,
    raw_artifact_relocation: tuple[Path, Path] | None,
) -> Mapping[str, Any]:
    """Verify one private materialization of the exact buffered snapshot bytes."""

    try:
        parsed: object = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotReplayError("source snapshot manifest is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise SnapshotReplayError("source snapshot manifest must be a JSON object")
    exact_manifest = cast(dict[str, Any], parsed)
    if set(file_payloads) != set(_SNAPSHOT_PAYLOAD_FILES):
        raise SnapshotReplayError("source snapshot payload set is incomplete")
    try:
        with tempfile.TemporaryDirectory(
            prefix="legalforecast-buffered-snapshot-"
        ) as temporary_root:
            private_snapshot = Path(temporary_root) / "snapshot"
            private_snapshot.mkdir()
            (private_snapshot / "manifest.json").write_bytes(manifest_bytes)
            for filename, payload in file_payloads.items():
                (private_snapshot / filename).write_bytes(payload)
            verified_manifest = verify_snapshot(
                private_snapshot,
                expected_cycle_hash=expected_cycle_hash,
                require_complete=True,
                require_saturated=True,
                raw_artifact_relocation=raw_artifact_relocation,
            )
    except SnapshotVerificationError as exc:
        raise SnapshotReplayError(str(exc)) from exc
    if dict(verified_manifest) != exact_manifest:
        raise SnapshotReplayError(
            "private snapshot verification changed the authenticated manifest"
        )
    return exact_manifest


def _read_jsonl_payload(payload: bytes, *, label: str) -> tuple[dict[str, Any], ...]:
    """Parse one already-buffered JSONL payload without touching the filesystem."""

    records: list[dict[str, Any]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise SnapshotReplayError(f"cannot decode {label}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            parsed: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SnapshotReplayError(
                f"invalid {label} JSON at line {line_number}"
            ) from exc
        if not isinstance(parsed, dict):
            raise SnapshotReplayError(f"{label} line {line_number} is not an object")
        records.append(cast(dict[str, Any], parsed))
    return tuple(records)


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


def _declared_bundle_root(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        mode = resolved.lstat().st_mode
    except OSError as exc:
        raise SnapshotReplayError(
            f"cannot access supplemental bundle root: {path}: {exc}"
        ) from exc
    if not stat.S_ISDIR(mode):
        raise SnapshotReplayError(
            f"supplemental bundle root is not a directory: {path}"
        )
    return resolved


def _safe_declared_bundle_member(
    path: Path,
    *,
    label: str,
    declared_root: Path,
    require_directory: bool,
) -> Path:
    raw_root = Path(os.path.abspath(os.fspath(declared_root)))
    raw_path = Path(os.path.abspath(os.fspath(path)))
    try:
        relative = raw_path.relative_to(raw_root)
    except ValueError as exc:
        raise SnapshotReplayError(f"{label} must be inside its bundle root") from exc
    resolved_root = _declared_bundle_root(declared_root)
    member = _safe_bundle_relative_existing_path(
        resolved_root / relative,
        root=resolved_root,
        label=label,
    )
    mode = member.lstat().st_mode
    expected = stat.S_ISDIR(mode) if require_directory else stat.S_ISREG(mode)
    if not expected:
        expected_kind = "directory" if require_directory else "regular file"
        raise SnapshotReplayError(f"{label} is not a {expected_kind}: {path}")
    return member


def _safe_bundle_relative_existing_path(path: Path, *, root: Path, label: str) -> Path:
    normalized_root = Path(os.path.abspath(os.fspath(root)))
    normalized_path = Path(os.path.abspath(os.fspath(path)))
    try:
        relative = normalized_path.relative_to(normalized_root)
    except ValueError as exc:
        raise SnapshotReplayError(f"{label} escapes its bundle root: {path}") from exc
    current = normalized_root
    for component in relative.parts:
        current /= component
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise SnapshotReplayError(f"cannot access {label}: {path}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise SnapshotReplayError(f"{label} contains a symlink: {path}")
    return normalized_path


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


def _read_hashed_json_object(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    try:
        payload = path.read_bytes()
        parsed: object = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotReplayError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SnapshotReplayError(f"{label} must be a JSON object: {path}")
    return cast(dict[str, Any], parsed), hashlib.sha256(payload).hexdigest()


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

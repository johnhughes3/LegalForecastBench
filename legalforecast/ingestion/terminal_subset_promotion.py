"""Authenticated provider-free promotion of one terminal exact subset."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_ranked_selection import (
    VerifiedCaseDevRankedSelection,
)
from legalforecast.ingestion.snapshot_replay import (
    ReplaySuccess,
    SnapshotReplayError,
    SupplementalReplaySource,
    read_verified_replay_raw,
    verify_supplemental_replay_source_evidence,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROVISIONAL_MARKERS: Mapping[str, object] = {
    "provisional_frontier": True,
    "final_cohort_eligible": False,
    "full_source_terminal": False,
}


class TerminalSubsetPromotionError(ValueError):
    """Raised when exact-subset promotion evidence does not reconcile."""


@dataclass(frozen=True, slots=True)
class TerminalSubsetPromotionBundle:
    """Verified selected raw bytes and their nonprovisional input records."""

    successes: tuple[ReplaySuccess, ...]
    promoted_success_records: tuple[Mapping[str, Any], ...]
    commitment: Mapping[str, object]


def read_pinned_terminal_selection_docket_ids(
    selection_run_card: Path,
    *,
    expected_selection_run_card_sha256: str,
) -> tuple[str, ...]:
    """Read exact docket IDs only after authenticating the terminal card bytes."""

    _require_sha256(expected_selection_run_card_sha256, "selection run-card")
    path = _regular_file(selection_run_card, "terminal selection run card")
    if _sha256_file(path) != expected_selection_run_card_sha256:
        raise TerminalSubsetPromotionError(
            "terminal selection run-card SHA-256 mismatch"
        )
    card = _json_object(path, "terminal selection run card")
    docket_ids_value = card.get("selected_docket_ids")
    docket_ids = (
        cast(list[object], docket_ids_value)
        if isinstance(docket_ids_value, list)
        else []
    )
    if (
        card.get("schema_version")
        != "legalforecast.case_dev_ranked_rest_subset_selection_run.v1"
        or card.get("selection_semantics") != "exact_case_dev_ranked_subset"
        or card.get("provider_activity_requested") is not False
        or card.get("provider_activity_executed") is not False
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or not docket_ids
        or any(
            not isinstance(value, str) or not value.isdigit() for value in docket_ids
        )
        or len({cast(str, value) for value in docket_ids}) != len(docket_ids)
    ):
        raise TerminalSubsetPromotionError(
            "terminal selection run card is not a zero-provider exact subset"
        )
    return tuple(cast(str, value) for value in docket_ids)


def verify_terminal_subset_promotion_source(
    *,
    selection: VerifiedCaseDevRankedSelection,
    expected_selection_run_card_record: Mapping[str, object],
    selection_run_card: Path,
    expected_selection_run_card_sha256: str,
    source_snapshot: Path,
    expected_source_snapshot_manifest_sha256: str,
    source_screen_run_card: Path,
    expected_source_screen_run_card_sha256: str,
    source_bundle_root: Path,
    expected_source_cycle_hash: str,
) -> TerminalSubsetPromotionBundle:
    """Verify a provisional source whose accepted set is the terminal subset."""

    for label, digest in (
        ("selection run-card", expected_selection_run_card_sha256),
        ("source snapshot manifest", expected_source_snapshot_manifest_sha256),
        ("source screen run-card", expected_source_screen_run_card_sha256),
        ("source cycle", expected_source_cycle_hash),
    ):
        _require_sha256(digest, label)
    if selection.top_n is not None:
        raise TerminalSubsetPromotionError(
            "terminal subset promotion requires exact docket-ID selection semantics"
        )

    selection_card_path = _regular_file(
        selection_run_card, "terminal selection run card"
    )
    selection_card_sha256 = _sha256_file(selection_card_path)
    if selection_card_sha256 != expected_selection_run_card_sha256:
        raise TerminalSubsetPromotionError(
            "terminal selection run-card SHA-256 mismatch"
        )
    selection_card = _json_object(selection_card_path, "terminal selection run card")
    if selection_card != dict(expected_selection_run_card_record):
        raise TerminalSubsetPromotionError(
            "terminal selection run card does not match the reconstructed exact subset"
        )

    supplemental = SupplementalReplaySource(
        snapshot=source_snapshot,
        expected_cycle_hash=expected_source_cycle_hash,
        screen_run_card=source_screen_run_card,
        expected_screen_run_card_sha256=(expected_source_screen_run_card_sha256),
        bundle_root=source_bundle_root,
    )
    try:
        evidence = verify_supplemental_replay_source_evidence(
            supplemental,
            expected_manifest_sha256=expected_source_snapshot_manifest_sha256,
        )
    except SnapshotReplayError as exc:
        raise TerminalSubsetPromotionError(str(exc)) from exc
    manifest = evidence.manifest
    manifest_sha256 = evidence.manifest_sha256
    screen_card = evidence.screen_run_card_record
    screen_card_sha256 = evidence.screen_run_card_sha256
    _verify_screen_run_card_shape(screen_card)
    lineage = _verify_provisional_lineage(
        manifest=manifest,
        screen_card=screen_card,
        selection=selection,
    )
    committed_inputs = dict(evidence.screen_input_commitment)
    outcomes: dict[str, ReplaySuccess | Mapping[str, Any]] = {}
    successes_by_docket: dict[str, ReplaySuccess] = {}
    for success in evidence.successes:
        if success.candidate_id in outcomes or success.docket_id in successes_by_docket:
            raise TerminalSubsetPromotionError("source success outcomes are duplicated")
        _require_record_lineage(success.record, lineage)
        outcomes[success.candidate_id] = success
        successes_by_docket[success.docket_id] = success
    for record in evidence.exclusion_records:
        candidate_id = _required_text(record, "case_id")
        if candidate_id in outcomes:
            raise TerminalSubsetPromotionError(
                f"duplicate source outcome for {candidate_id}"
            )
        _require_record_lineage(record, lineage)
        outcomes[candidate_id] = dict(record)
    if lineage.get("success_count") != len(outcomes):
        raise TerminalSubsetPromotionError(
            "source provisional success count does not match verified snapshot outcomes"
        )

    accepted_ids = {
        _required_text(row, "candidate_id") for row in evidence.screened_records
    }
    lead_by_docket = {lead.docket_id: lead for lead in selection.source.leads}
    missing_dockets = sorted(
        candidate.docket_id
        for candidate in selection.selected
        if candidate.docket_id not in lead_by_docket
    )
    if missing_dockets:
        raise TerminalSubsetPromotionError(
            "terminal selection references dockets missing from its source: "
            + ", ".join(missing_dockets)
        )
    expected_candidate_ids = {
        lead_by_docket[candidate.docket_id].candidate_id
        for candidate in selection.selected
    }
    selected_dockets = {candidate.docket_id for candidate in selection.selected}
    if accepted_ids != expected_candidate_ids:
        raise TerminalSubsetPromotionError(
            "source accepted candidate set does not exactly equal terminal selection"
        )
    if set(successes_by_docket).issuperset(selected_dockets) is False:
        raise TerminalSubsetPromotionError(
            "terminal selection is missing from source successful fetches"
        )
    selected_successes = tuple(
        successes_by_docket[candidate.docket_id] for candidate in selection.selected
    )
    if {
        success.candidate_id for success in selected_successes
    } != expected_candidate_ids:
        raise TerminalSubsetPromotionError(
            "terminal selection candidate identities changed in source successes"
        )

    promoted_records: list[Mapping[str, Any]] = []
    raw_commitments: list[dict[str, object]] = []
    for success in selected_successes:
        original_record_sha256 = _canonical_sha256(dict(success.record))
        promoted = {
            key: value for key, value in success.record.items() if key not in lineage
        }
        promoted["terminal_subset_promotion"] = {
            "schema_version": "legalforecast.terminal_subset_source_record.v1",
            "original_record_sha256": original_record_sha256,
            "source_snapshot_manifest_sha256": manifest_sha256,
            "selection_run_card_sha256": selection_card_sha256,
        }
        if any(field in promoted for field in _PROVISIONAL_MARKERS):
            raise TerminalSubsetPromotionError(
                "promoted success retained provisional cohort-safety fields"
            )
        promoted_records.append(promoted)
        raw_commitments.append(
            {
                "candidate_id": success.candidate_id,
                "docket_id": success.docket_id,
                "raw_html_sha256": success.raw_sha256,
                "raw_html_bytes": success.raw_byte_count,
                "original_record_sha256": original_record_sha256,
            }
        )

    commitment: dict[str, object] = {
        "schema_version": "legalforecast.terminal_subset_promotion.v1",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "final_cohort_eligible": True,
        "full_source_terminal": True,
        "selected_candidate_count": len(selected_successes),
        "selected_candidate_set_sha256": selection.selected_candidate_set_sha256,
        "promoted_candidate_id_set_sha256": _canonical_sha256(
            sorted(expected_candidate_ids)
        ),
        "terminal_source_candidate_count": len(selection.source.leads),
        "terminal_ranked_candidate_count": selection.ranked_candidate_count,
        "terminal_exclusion_count": selection.terminal_exclusion_count,
        "terminal_excluded_candidate_set_sha256": (
            selection.terminal_excluded_candidate_set_sha256
        ),
        "selection_run_card_sha256": selection_card_sha256,
        "source_snapshot_manifest_sha256": manifest_sha256,
        "source_screen_run_card_sha256": screen_card_sha256,
        "source_screen_inputs": dict(committed_inputs),
        "source_provisional_lineage_sha256": _canonical_sha256(lineage),
        "raw_artifacts": raw_commitments,
    }
    return TerminalSubsetPromotionBundle(
        successes=selected_successes,
        promoted_success_records=tuple(promoted_records),
        commitment=commitment,
    )


def read_verified_promotion_raw(success: ReplaySuccess) -> bytes:
    """Recheck selected source bytes immediately before target publication."""

    try:
        return read_verified_replay_raw(success)
    except SnapshotReplayError as exc:
        raise TerminalSubsetPromotionError(str(exc)) from exc


def _verify_screen_run_card_shape(card: Mapping[str, Any]) -> None:
    if (
        card.get("stage") != "screen-firecrawl-dockets"
        or card.get("status") != "completed"
        or card.get("execute") is not True
        or card.get("dry_run") is not False
        or card.get("reconciled") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or card.get("snapshot_complete") is not True
        or card.get("snapshot_saturated") is not True
    ):
        raise TerminalSubsetPromotionError(
            "source screen run card is not one completed zero-paid strict screen"
        )


def _verify_provisional_lineage(
    *,
    manifest: Mapping[str, Any],
    screen_card: Mapping[str, Any],
    selection: VerifiedCaseDevRankedSelection,
) -> dict[str, object]:
    if any(
        manifest.get(field) != value for field, value in _PROVISIONAL_MARKERS.items()
    ):
        raise TerminalSubsetPromotionError(
            "source snapshot is not explicitly provisional and ineligible"
        )
    stage_commitments_value = manifest.get("stage_commitments")
    if not isinstance(stage_commitments_value, Mapping):
        raise TerminalSubsetPromotionError("source snapshot lacks stage commitments")
    stage_commitments = cast(Mapping[str, object], stage_commitments_value)
    lineage_value = stage_commitments.get("provisional_lineage")
    if not isinstance(lineage_value, Mapping):
        raise TerminalSubsetPromotionError(
            "source snapshot lacks authenticated provisional lineage"
        )
    lineage = dict(cast(Mapping[str, object], lineage_value))
    if any(
        lineage.get(field) != value for field, value in _PROVISIONAL_MARKERS.items()
    ):
        raise TerminalSubsetPromotionError(
            "source snapshot provisional lineage changed cohort-safety flags"
        )
    if any(screen_card.get(field) != value for field, value in lineage.items()):
        raise TerminalSubsetPromotionError(
            "source screen run card does not match snapshot provisional lineage"
        )
    expected = selection.commitment_record()
    for field in (
        "source_candidate_count",
        "source_candidate_set_sha256",
        "source_projection_sha256",
    ):
        if lineage.get(field) != expected.get(field):
            raise TerminalSubsetPromotionError(
                f"source provisional lineage does not match terminal source: {field}"
            )
    source_count = lineage.get("source_candidate_count")
    partition = tuple(
        lineage.get(field)
        for field in ("success_count", "terminal_exclusion_count", "pending_count")
    )
    if (
        type(source_count) is not int
        or any(type(value) is not int for value in partition)
        or source_count <= 0
        or any(cast(int, value) < 0 for value in partition)
        or sum(cast(tuple[int, int, int], partition)) != source_count
    ):
        raise TerminalSubsetPromotionError(
            "source provisional partition counts do not reconcile"
        )
    return lineage


def _require_record_lineage(
    record: Mapping[str, Any], lineage: Mapping[str, object]
) -> None:
    if any(record.get(field) != value for field, value in lineage.items()):
        raise TerminalSubsetPromotionError("source outcome changed provisional lineage")


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSubsetPromotionError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TerminalSubsetPromotionError(f"{label} must be a JSON object")
    typed_value = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in typed_value):
        raise TerminalSubsetPromotionError(f"{label} must be a JSON object")
    return cast(dict[str, object], typed_value)


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise TerminalSubsetPromotionError(f"record lacks required {field}")
    return value.strip()


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise TerminalSubsetPromotionError(
            f"expected {label} SHA-256 must be 64 lowercase hex digits"
        )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regular_file(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise TerminalSubsetPromotionError(f"{label} is unavailable: {path}") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or not resolved.is_file()
    ):
        raise TerminalSubsetPromotionError(f"{label} must be a regular file: {path}")
    return resolved


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()

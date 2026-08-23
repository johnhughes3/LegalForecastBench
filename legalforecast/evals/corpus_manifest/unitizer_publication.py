# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Immutable Stage 5.1 r2 sidecar and completion-marker publication."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object, write_jsonl_objects
from legalforecast.contracts import CYCLE1_MANIFEST_UNITIZER_R2_AUTHORITY_V1

from .stage51_r2 import (
    _file_commitment,
    _verify_file_commitments,
    _write_json_output,
    _write_jsonl_output,
)
from .unitizer_shared import (
    _R2_AUTHORITY_MODE,
    AuthenticatedFinalizedOverlay,
    JsonRecord,
    ManifestUnitizerCommandError,
    PreparedManifestUnitizerInputs,
)


def _write_stage_card(
    args: argparse.Namespace,
    *,
    output_root: Path,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    record_count: int,
    paid: bool,
    extra: Mapping[str, Any],
    dry_run: bool,
    immutable: bool = False,
    authority_overlay: AuthenticatedFinalizedOverlay | None = None,
    prepared: PreparedManifestUnitizerInputs | None = None,
    replay_audits: Sequence[Mapping[str, Any]] = (),
) -> None:
    run_card = (
        Path(args.run_card_output)
        if args.run_card_output
        else (output_root / "run-cards" / "llm-unitize-manifest.json")
    )
    log_path = (
        Path(args.log_output)
        if args.log_output
        else (output_root / "logs" / "llm-unitize-manifest.jsonl")
    )
    metadata_path = output_root / "run-cards" / "llm-unitize-manifest.metadata.json"
    authority_path = (
        output_root / "run-cards" / "llm-unitize-manifest.r2-authority.json"
    )
    metadata = {
        "authoritative": False,
        "stage": "llm-unitize-manifest",
        "run_card_path": str(run_card),
        **dict(extra),
    }
    if immutable:
        metadata["authority_sidecar_path"] = str(authority_path)
        metadata["authority_mode"] = _R2_AUTHORITY_MODE
        metadata["authority_authenticated"] = True
    card_output_paths = [*output_paths, metadata_path]
    if immutable:
        card_output_paths.extend((log_path, authority_path))
    card: dict[str, Any] = {
        # contract-ratchet: allow additive manifest-mode run-card adapter
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "llm-unitize-manifest",
        "status": "completed",
        "dry_run": dry_run,
        "execute": not dry_run,
        "resume": bool(args.resume),
        "record_count": record_count,
        "input_paths": [str(path) for path in input_paths],
        "output_paths": [str(path) for path in card_output_paths],
        "paid_activity_requested": paid,
        "paid_activity_executed": paid,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    log_record = {
        # contract-ratchet: allow additive manifest-mode stage-log adapter
        "schema_version": "legalforecast.acquisition_stage_log.v1",
        "event": "stage_completed",
        "stage": "llm-unitize-manifest",
        "status": "completed",
        "dry_run": dry_run,
        "run_card_path": str(run_card),
        "record_count": record_count,
        "paid_activity_requested": paid,
        "paid_activity_executed": paid,
    }
    if not immutable:
        write_json_object(metadata_path, metadata)
        write_json_object(run_card, card)
        write_jsonl_objects(log_path, [log_record])
        return
    if authority_overlay is None or prepared is None:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 publication requires its authenticated authority inputs"
        )
    _verify_file_commitments(authority_overlay.authority_input_commitments)
    _write_json_output(metadata_path, metadata, immutable=True)
    _write_jsonl_output(log_path, [log_record], immutable=True)
    authority_record = _stage51_r2_authority_record(
        args,
        run_card=run_card,
        metadata_path=metadata_path,
        log_path=log_path,
        input_paths=input_paths,
        output_paths=output_paths,
        overlay=authority_overlay,
        prepared=prepared,
        replay_audits=replay_audits,
        dry_run=dry_run,
    )
    _write_json_output(authority_path, authority_record, immutable=True)
    # The ordinary frozen-shape run card is the completion marker and is
    # deliberately published only after every output it names exists.
    _write_json_output(run_card, card, immutable=True)


def _stage51_r2_authority_record(
    args: argparse.Namespace,
    *,
    run_card: Path,
    metadata_path: Path,
    log_path: Path,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    overlay: AuthenticatedFinalizedOverlay,
    prepared: PreparedManifestUnitizerInputs,
    replay_audits: Sequence[Mapping[str, Any]],
    dry_run: bool,
) -> JsonRecord:
    approval_observation = next(
        (
            dict(commitment)
            for commitment in overlay.authority_input_commitments
            if commitment.get("label") == "owner_approval_observation"
        ),
        None,
    )
    if approval_observation is None:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 authority lacks its approval observation commitment"
        )
    replay_commitments: list[JsonRecord] = []
    for audit in replay_audits:
        metadata = audit.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ManifestUnitizerCommandError(
                f"{audit.get('candidate_id')}: replay audit metadata is missing"
            )
        replay_metadata = cast(Mapping[str, object], metadata)
        replay_commitments.append(
            {
                "candidate_id": audit.get("candidate_id"),
                "case_id": audit.get("case_id"),
                "provider_prompt_sha256": audit.get("provider_prompt_sha256"),
                "raw_output_sha256": audit.get("raw_output_sha256"),
                "provider_response_sha256": replay_metadata.get(
                    "provider_response_sha256"
                ),
                "normalized_response_sha256": replay_metadata.get(
                    "normalized_response_sha256"
                ),
                "historical_provider_attempt_ordinal": audit.get(
                    "historical_provider_attempt_ordinal"
                ),
                "input_tokens": audit.get("input_tokens"),
                "output_tokens": audit.get("output_tokens"),
                "estimated_cost": audit.get("estimated_cost"),
                "unit_count": audit.get("unit_count"),
                "scorable_unit_count": audit.get("scorable_unit_count"),
            }
        )
    if (
        tuple(str(record.get("candidate_id")) for record in replay_commitments)
        != overlay.fresh_candidate_ids
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 replay commitments differ from the exact fresh-five order"
        )
    published_paths = (*output_paths, metadata_path, log_path)
    return {
        # contract-ratchet: new disjoint r2 authority sidecar
        "schema_version": str(CYCLE1_MANIFEST_UNITIZER_R2_AUTHORITY_V1),
        "stage": "llm-unitize-manifest",
        "authority_mode": overlay.authority_mode,
        "authoritative": not dry_run,
        "dry_run": dry_run,
        "completion_marker_path": str(run_card),
        "owner_approval": {
            "reference": str(args.owner_approval_reference),
            "packet_line": str(args.stage51_packet_approval),
            "spend_line": str(args.units_spend_approval),
            "observation": approval_observation,
            "observation_role": (
                "hash-pinned observational evidence; not identity authentication"
            ),
        },
        "input_paths": [str(path) for path in input_paths],
        "input_commitments": [
            dict(commitment) for commitment in overlay.authority_input_commitments
        ],
        "selection": {
            "sha256": prepared.selection_sha256,
            "candidate_order": [
                str(record["candidate_id"]) for record in prepared.selection_records
            ],
            "candidate_count": len(prepared.selection_records),
            "retained_count": len(overlay.retained_records),
            "reprocessed_count": len(overlay.reprocessed_records),
            "reprocessed_candidate_ids": list(overlay.reprocessed_candidate_ids),
            "fresh_count": len(overlay.fresh_selection_records),
            "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
            "unit_count": sum(
                len(cast(list[object], record["prediction_units"]))
                for record in (
                    *overlay.retained_records,
                    *overlay.reprocessed_records,
                    *overlay.expected_fresh_records,
                )
            ),
        },
        "document_commitments": {
            document_id: dict(commitment)
            for document_id, commitment in prepared.document_commitments.items()
        },
        "journal_reconstruction": {
            "journal_path": str(Path(args.provider_journal).resolve()),
            "snapshot_mode": "query_only",
            "journal_mutated": False,
            "candidates": replay_commitments,
        },
        "output_commitments": [
            _file_commitment(path, f"published_output_{index}")
            for index, path in enumerate(published_paths, start=1)
        ],
        "provider_called": False,
        "historical_replay_only": True,
        "new_paid_activity": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "journal_mutated": False,
    }

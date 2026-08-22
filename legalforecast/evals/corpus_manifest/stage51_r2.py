# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Authentication and create-only primitives for Stage 5.1 r2 authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object, write_jsonl_objects
from legalforecast.contracts import (
    ACQUISITION_RUN_CARD_V1,
    ARTIFACT_CANONICAL_JSON_V1,
    CYCLE1_STAGE51_FINALIZED_UNITS_INTEGRATION_PROPOSAL_V1,
    CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_DIFF_V1,
    CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_SHA_INVENTORY_V1,
    CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_VALIDATION_V1,
)
from legalforecast.ingestion.cohort_document_materializer import (
    CohortDocumentMaterializationError,
    prepare_non_symlink_directory,
    require_non_symlink_components,
)
from legalforecast.unitization.schemas import prediction_unit_from_record

from .unitizer_shared import (
    _CYCLE1_REPROCESSED_CANDIDATE_IDS,
    _LABELING_MODEL_KEY,
    _R2_AUTHORITY_MODE,
    _R2_FILES,
    _R2_FRESH_CANDIDATE_IDS,
    _R2_PACKET_CANDIDATE_IDS,
    _R2_UNITS_SPEND_APPROVAL,
    AuthenticatedFinalizedOverlay,
    JsonRecord,
    ManifestUnitizerCommandError,
    PreparedManifestUnitizerInputs,
    _command_required_string,
    _jsonl_records_from_bytes,
    _normalized_approval,
    _packet_replacement_units,
    _read_regular_input,
    _records_by_candidate,
    _validate_retained_record,
)


def _jsonl_output_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(record), sort_keys=True, allow_nan=False) + "\n"
        for record in records
    ).encode("utf-8")


def _json_output_bytes(record: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(record), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_jsonl_output(
    path: Path, records: Sequence[Mapping[str, Any]], *, immutable: bool
) -> None:
    if not immutable:
        write_jsonl_objects(path, records)
        return
    _write_immutable_bytes(path, _jsonl_output_bytes(records))


def _write_json_output(
    path: Path, record: Mapping[str, Any], *, immutable: bool
) -> None:
    if not immutable:
        write_json_object(path, record)
        return
    _write_immutable_bytes(path, _json_output_bytes(record))


def _write_immutable_bytes(path: Path, payload: bytes) -> None:
    try:
        parent = prepare_non_symlink_directory(path.parent)
    except CohortDocumentMaterializationError as exc:
        raise ManifestUnitizerCommandError(str(exc)) from exc
    if path.exists() or path.is_symlink():
        raise ManifestUnitizerCommandError(f"immutable output already exists: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            raise ManifestUnitizerCommandError(
                f"immutable output appeared concurrently: {path}"
            ) from None
        temporary.unlink()
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _stage_card_paths(args: argparse.Namespace, output_root: Path) -> tuple[Path, ...]:
    run_card = (
        Path(args.run_card_output)
        if args.run_card_output
        else output_root / "run-cards" / "llm-unitize-manifest.json"
    )
    log_path = (
        Path(args.log_output)
        if args.log_output
        else output_root / "logs" / "llm-unitize-manifest.jsonl"
    )
    return (
        run_card,
        log_path,
        output_root / "run-cards" / "llm-unitize-manifest.metadata.json",
        output_root / "run-cards" / "llm-unitize-manifest.r2-authority.json",
    )


def _preflight_r2_outputs(
    args: argparse.Namespace,
    *,
    output_root: Path,
    input_paths: Sequence[Path],
    primary_outputs: Sequence[Path],
) -> None:
    output_paths = (*primary_outputs, *_stage_card_paths(args, output_root))
    lexical = [path.absolute() for path in output_paths]
    resolved = [path.resolve(strict=False) for path in output_paths]
    if len(set(lexical)) != len(lexical) or len(set(resolved)) != len(resolved):
        raise ManifestUnitizerCommandError("Stage-51 r2 output paths alias each other")
    input_resolved = {path.resolve(strict=False) for path in input_paths}
    for path, resolved_path in zip(output_paths, resolved, strict=True):
        if resolved_path in input_resolved:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 output aliases an authenticated input: {path}"
            )
        if path.exists() or path.is_symlink():
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 immutable output already exists: {path}"
            )
        try:
            prepare_non_symlink_directory(path.parent)
        except CohortDocumentMaterializationError as exc:
            raise ManifestUnitizerCommandError(str(exc)) from exc


def _required_path_argument(args: argparse.Namespace, name: str) -> Path:
    value = getattr(args, name, None)
    if value is None:
        raise ManifestUnitizerCommandError(f"--{name.replace('_', '-')} is required")
    return Path(value)


def _required_digest_argument(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name, None)
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ManifestUnitizerCommandError(
            f"--{name.replace('_', '-')} must be a bare lowercase SHA-256"
        )
    return value


def _file_commitment(
    path: Path, label: str, payload: bytes | None = None
) -> JsonRecord:
    captured = _read_regular_input(path, label) if payload is None else payload
    return {
        "label": label,
        "path": str(path),
        "sha256": hashlib.sha256(captured).hexdigest(),
        "byte_count": len(captured),
    }


def _verify_file_commitments(commitments: Sequence[Mapping[str, Any]]) -> None:
    for commitment in commitments:
        label = _command_required_string(commitment, "label")
        path = Path(_command_required_string(commitment, "path"))
        expected_sha256 = _command_required_string(commitment, "sha256")
        expected_byte_count = commitment.get("byte_count")
        payload = _read_regular_input(path, label)
        if (
            hashlib.sha256(payload).hexdigest() != expected_sha256
            or len(payload) != expected_byte_count
        ):
            raise ManifestUnitizerCommandError(
                f"authenticated input changed before publication: {label}"
            )


def authenticate_stage51_r2_proposal(
    args: argparse.Namespace,
    *,
    prepared: PreparedManifestUnitizerInputs,
) -> AuthenticatedFinalizedOverlay:
    """Promote the exact r2 proposal only after independent replay and approval."""

    root = _required_path_argument(args, "stage51_proposal_root")
    try:
        require_non_symlink_components(root)
    except CohortDocumentMaterializationError as exc:
        raise ManifestUnitizerCommandError(str(exc)) from exc
    if root.is_symlink() or not root.is_dir():
        raise ManifestUnitizerCommandError(
            f"Stage-51 proposal root is not a regular directory: {root}"
        )
    expected_fields = {
        "selection": "expected_stage51_selection_sha256",
        "overlay": "expected_stage51_overlay_sha256",
        "packet": "expected_stage51_packet_sha256",
        "validation": "expected_stage51_validation_sha256",
        "semantic_diff": "expected_stage51_semantic_diff_sha256",
        "inventory": "expected_stage51_inventory_sha256",
        "checksums": "expected_stage51_checksums_sha256",
        "integration_proposal": "expected_stage51_integration_proposal_sha256",
    }
    paths = {label: root / name for label, name in _R2_FILES.items()}
    payloads: dict[str, bytes] = {}
    commitments: list[JsonRecord] = []
    for label, path in paths.items():
        payload = _read_regular_input(path, f"Stage-51 r2 {label}")
        expected = _required_digest_argument(args, expected_fields[label])
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 {label} differs from its expected SHA-256"
            )
        payloads[label] = payload
        commitments.append(_file_commitment(path, f"stage51_r2_{label}", payload))

    expected_selection = _required_digest_argument(args, "expected_selection_sha256")
    if expected_selection != prepared.selection_sha256:
        raise ManifestUnitizerCommandError(
            "corrected selection digest differs from the approved digest"
        )
    if hashlib.sha256(payloads["selection"]).hexdigest() != prepared.selection_sha256:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 selection differs from the unitizer selection"
        )
    if not str(args.owner_approval_reference).strip():
        raise ManifestUnitizerCommandError("owner approval reference is required")
    packet_sha256 = hashlib.sha256(payloads["packet"]).hexdigest()
    packet_approval = f"stage51-terminal-units: approved — packet {packet_sha256}"
    if _normalized_approval(str(args.stage51_packet_approval)) != packet_approval:
        raise ManifestUnitizerCommandError(
            "Stage-51 packet approval does not name the authenticated r2 packet"
        )
    if _normalized_approval(str(args.units_spend_approval)) != _R2_UNITS_SPEND_APPROVAL:
        raise ManifestUnitizerCommandError(
            "units spend approval does not match the owner-approved USD 5 line"
        )
    approval_path = _required_path_argument(args, "owner_approval_source")
    approval_payload = _read_regular_input(approval_path, "owner approval source")
    approval_sha256 = _required_digest_argument(
        args, "expected_owner_approval_source_sha256"
    )
    if hashlib.sha256(approval_payload).hexdigest() != approval_sha256:
        raise ManifestUnitizerCommandError(
            "owner approval source differs from its expected SHA-256"
        )
    _verify_durable_approval_observation(
        approval_payload,
        owner_approval_reference=str(args.owner_approval_reference),
        packet_approval=packet_approval,
        spend_approval=_R2_UNITS_SPEND_APPROVAL,
    )
    commitments.append(
        _file_commitment(approval_path, "owner_approval_observation", approval_payload)
    )

    records = _authenticate_r2_semantics(
        root=root,
        paths=paths,
        payloads=payloads,
        prepared=prepared,
        packet_sha256=packet_sha256,
        commitments=commitments,
    )
    fresh_records, fresh_audits = _authenticate_fresh_five_evidence(
        args,
        prepared=prepared,
        commitments=commitments,
    )
    overlay_by_candidate = _records_by_candidate(records, label="Stage-51 r2 overlay")
    selection_ids = {str(row["candidate_id"]) for row in prepared.selection_records}
    overlay_ids = set(overlay_by_candidate)
    intersection = selection_ids & overlay_ids
    fresh_set = selection_ids - overlay_ids
    if (
        len(selection_ids) != 100
        or len(overlay_ids) != 100
        or len(intersection) != 95
        or fresh_set != set(_R2_FRESH_CANDIDATE_IDS)
        or len(overlay_ids - selection_ids) != 5
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 overlay does not form the exact prior-100/current-95 partition"
        )

    retained: list[JsonRecord] = []
    reprocessed: list[JsonRecord] = []
    fresh_selection: list[JsonRecord] = []
    for selection in prepared.selection_records:
        candidate_id = str(selection["candidate_id"])
        if candidate_id in fresh_set:
            fresh_selection.append(dict(selection))
            continue
        record = overlay_by_candidate[candidate_id]
        _validate_retained_record(record, selection=selection, prepared=prepared)
        if candidate_id in _CYCLE1_REPROCESSED_CANDIDATE_IDS:
            reprocessed.append(record)
        else:
            retained.append(record)
    if len(retained) != 94 or len(reprocessed) != 1:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 authority must retain 94 and reprocess exactly 72288139"
        )
    fresh_ids = tuple(str(row["candidate_id"]) for row in fresh_selection)
    if tuple(str(row["candidate_id"]) for row in fresh_records) != fresh_ids:
        raise ManifestUnitizerCommandError(
            "fresh-five evidence order differs from corrected selection order"
        )
    return AuthenticatedFinalizedOverlay(
        retained_records=tuple(retained),
        fresh_selection_records=tuple(fresh_selection),
        overlay_sha256=hashlib.sha256(payloads["overlay"]).hexdigest(),
        integration_manifest_sha256=hashlib.sha256(
            payloads["integration_proposal"]
        ).hexdigest(),
        fresh_candidate_ids=fresh_ids,
        reprocessed_records=tuple(reprocessed),
        reprocessed_candidate_ids=("72288139",),
        authority_mode=_R2_AUTHORITY_MODE,
        authority_input_commitments=tuple(commitments),
        expected_fresh_records=fresh_records,
        expected_fresh_audits=fresh_audits,
    )


def _verify_durable_approval_observation(
    payload: bytes,
    *,
    owner_approval_reference: str,
    packet_approval: str,
    spend_approval: str,
) -> None:
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestUnitizerCommandError(
            "owner approval source is not valid UTF-8 JSON"
        ) from exc
    observed: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            observed.extend(line.strip() for line in value.splitlines() if line.strip())
        elif isinstance(value, list):
            for item in cast(list[object], value):
                collect(item)
        elif isinstance(value, Mapping):
            for item in cast(Mapping[object, object], value).values():
                collect(item)

    collect(loaded)
    for required in (owner_approval_reference, packet_approval, spend_approval):
        if required not in observed:
            raise ManifestUnitizerCommandError(
                f"owner approval observation does not contain exact line: {required}"
            )


def _json_object_from_bytes(payload: bytes, label: str) -> JsonRecord:
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestUnitizerCommandError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(loaded, dict):
        raise ManifestUnitizerCommandError(f"{label} must be a JSON object")
    return cast(JsonRecord, loaded)


def _authenticate_r2_semantics(
    *,
    root: Path,
    paths: Mapping[str, Path],
    payloads: Mapping[str, bytes],
    prepared: PreparedManifestUnitizerInputs,
    packet_sha256: str,
    commitments: list[JsonRecord],
) -> tuple[JsonRecord, ...]:
    selection_records = _jsonl_records_from_bytes(
        payloads["selection"],
        label="Stage-51 r2 selection",
        error_factory=ManifestUnitizerCommandError,
    )
    if selection_records != prepared.selection_records:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 selection records differ from the prepared selection"
        )
    overlay_records = _jsonl_records_from_bytes(
        payloads["overlay"],
        label="Stage-51 r2 prediction-units overlay",
        error_factory=ManifestUnitizerCommandError,
    )
    overlay_by_candidate = _records_by_candidate(
        overlay_records, label="Stage-51 r2 prediction-units overlay"
    )
    if len(overlay_records) != 100:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 prediction-units overlay must contain 100 candidates"
        )
    unit_count = 0
    scorable_count = 0
    for record in overlay_records:
        raw_units = record.get("prediction_units")
        if not isinstance(raw_units, list) or not raw_units:
            raise ManifestUnitizerCommandError(
                f"{record.get('candidate_id')}: r2 overlay requires prediction units"
            )
        for raw_unit in cast(list[object], raw_units):
            unit = prediction_unit_from_record(raw_unit)
            unit_count += 1
            scorable_count += unit.should_score
    if unit_count != 437 or scorable_count != 437:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 overlay must contain exactly 437 scorable units"
        )

    packet = _json_object_from_bytes(payloads["packet"], "Stage-51 r2 packet")
    if ARTIFACT_CANONICAL_JSON_V1.encode(packet) != payloads["packet"]:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 packet is not artifact-canonical JSON"
        )
    if packet.get("authoritative") is not False:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 packet must remain non-authoritative before owner promotion"
        )
    if packet.get("candidate_order") != list(_R2_PACKET_CANDIDATE_IDS):
        raise ManifestUnitizerCommandError("Stage-51 r2 packet candidate order differs")
    packet_units = _packet_replacement_units(payloads["packet"])
    if tuple(packet_units) != _R2_PACKET_CANDIDATE_IDS:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 packet candidates differ from the exact reviewed five"
        )
    if sum(len(units) for units in packet_units.values()) != 19:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 packet must contain exactly 19 proposed units"
        )
    for candidate_id, units in packet_units.items():
        overlay_units = overlay_by_candidate.get(candidate_id, {}).get(
            "prediction_units"
        )
        if overlay_units != units:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: r2 overlay units differ from the approved packet"
            )

    integration = _json_object_from_bytes(
        payloads["integration_proposal"], "Stage-51 r2 integration proposal"
    )
    _verify_r2_integration_record(
        integration,
        root=root,
        paths=paths,
        payloads=payloads,
        packet_sha256=packet_sha256,
    )
    validation = _json_object_from_bytes(
        payloads["validation"], "Stage-51 r2 validation report"
    )
    semantic_diff = _json_object_from_bytes(
        payloads["semantic_diff"], "Stage-51 r2 semantic diff"
    )
    inventory = _json_object_from_bytes(
        payloads["inventory"], "Stage-51 r2 byte inventory"
    )
    _verify_r2_validation_record(validation, packet_sha256=packet_sha256)
    _verify_r2_semantic_diff(
        semantic_diff,
        packet_sha256=packet_sha256,
        overlay_by_candidate=overlay_by_candidate,
    )
    inventory_paths = _verify_r2_inventory(
        inventory,
        root=root,
        paths=paths,
        payloads=payloads,
        packet_sha256=packet_sha256,
        commitments=commitments,
    )
    _verify_r2_checksums(
        payloads["checksums"],
        required_paths=inventory_paths | (set(paths.values()) - {paths["checksums"]}),
    )
    return overlay_records


def _verify_r2_integration_record(
    record: Mapping[str, Any],
    *,
    root: Path,
    paths: Mapping[str, Path],
    payloads: Mapping[str, bytes],
    packet_sha256: str,
) -> None:
    expected_scalars: dict[str, object] = {
        "artifact": (str(CYCLE1_STAGE51_FINALIZED_UNITS_INTEGRATION_PROPOSAL_V1)),
        "authoritative": False,
        "integration_ready": False,
        "owner_digest_approval_status": "PENDING",
        "owner_substantive_approval_status": "PENDING",
        "provider_activity": False,
        "pacer_activity": False,
        "provider_spend_usd": "0.00",
        "candidate_count": 100,
        "selection_document_count": 339,
        "unit_count": 437,
        "scorable_unit_count": 437,
        "packet_candidate_count": 5,
        "packet_proposed_unit_count": 19,
        "packet_candidates": list(_R2_PACKET_CANDIDATE_IDS),
        "changed_candidate_ids": ["72288139"],
        "packet_sha256": packet_sha256,
        "output_selection_proposal": str(paths["selection"]),
        "output_prediction_units_overlay": str(paths["overlay"]),
        "packet": str(paths["packet"]),
        "validation_report": str(paths["validation"]),
        "semantic_diff": str(paths["semantic_diff"]),
    }
    for field, expected in expected_scalars.items():
        if record.get(field) != expected:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 integration proposal has invalid {field}"
            )
    expected_hashes = {
        "output_selection_proposal_sha256": "selection",
        "output_prediction_units_overlay_sha256": "overlay",
        "validation_report_sha256": "validation",
        "semantic_diff_sha256": "semantic_diff",
    }
    for field, label in expected_hashes.items():
        if record.get(field) != hashlib.sha256(payloads[label]).hexdigest():
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 integration proposal has invalid {field}"
            )
    approval = f"stage51-terminal-units: approved — packet {packet_sha256}"
    if record.get("approval_template_pending") != approval:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 integration proposal approval template differs"
        )
    if Path(str(record.get("output_selection_proposal"))).parent != root:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 integration proposal escapes its proposal root"
        )


def _verify_r2_validation_record(
    record: Mapping[str, Any], *, packet_sha256: str
) -> None:
    expected = {
        "artifact": (str(CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_VALIDATION_V1)),
        "authoritative": False,
        "status": "PASS; provider-free validation only",
        "canonical_packet_sha256": packet_sha256,
        "changed_candidate_ids": ["72288139"],
        "owner_digest_approval_status": "PENDING",
        "owner_substantive_approval_status": "PENDING",
        "provider_activity": False,
        "pacer_activity": False,
        "provider_spend_usd": "0.00",
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 validation report has invalid {field}"
            )
    counts = record.get("counts")
    if counts != {
        "candidate_count": 100,
        "selection_document_count": 339,
        "unit_count": 437,
        "scorable_unit_count": 437,
        "packet_candidate_count": 5,
        "packet_proposed_unit_count": 19,
    }:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 validation report counts differ"
        )
    checks = record.get("checks")
    required_checks = {
        "only candidate 72288139 selection and prediction-unit rows changed "
        "relative to r1",
        "all 437 units passed prediction_unit_from_record and are scorable",
        "no selected decision/order or contains_target_outcome document is "
        "model-visible",
        "no prediction unit cites a selected decision/outcome document",
    }
    if not isinstance(checks, list) or not required_checks <= set(
        cast(list[object], checks)
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 validation report lacks required semantic checks"
        )


def _verify_r2_semantic_diff(
    record: Mapping[str, Any],
    *,
    packet_sha256: str,
    overlay_by_candidate: Mapping[str, JsonRecord],
) -> None:
    if (
        record.get("artifact") != str(CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_DIFF_V1)
        or record.get("authoritative") is not False
        or record.get("status")
        != "PASS; provider-free semantic and byte-preservation comparison"
        or record.get("provider_spend_usd") != "0.00"
    ):
        raise ManifestUnitizerCommandError("Stage-51 r2 semantic diff header differs")
    packet = record.get("packet")
    if not isinstance(packet, Mapping) or dict(cast(Mapping[str, object], packet)) != {
        "added_candidate": "72288139",
        "authoritative": False,
        "candidate_count": 5,
        "candidate_order": list(_R2_PACKET_CANDIDATE_IDS),
        "canonical_packet_sha256": packet_sha256,
        "prior_four_candidate_objects_semantically_preserved": True,
        "proposed_unit_count": 19,
    }:
        raise ManifestUnitizerCommandError("Stage-51 r2 semantic packet diff differs")
    prediction = record.get("prediction_units")
    selection = record.get("selection")
    if not isinstance(prediction, Mapping) or not isinstance(selection, Mapping):
        raise ManifestUnitizerCommandError("Stage-51 r2 semantic diff is incomplete")
    prediction_record = cast(Mapping[str, object], prediction)
    selection_record = cast(Mapping[str, object], selection)
    if (
        prediction_record.get("candidate_count_before") != 100
        or prediction_record.get("candidate_count_after") != 100
        or prediction_record.get("changed_candidate_ids") != ["72288139"]
        or prediction_record.get("non_72288139_rows_byte_unchanged") is not True
        or prediction_record.get("unit_count_after") != 437
        or prediction_record.get("scorable_unit_count_after") != 437
        or prediction_record.get("stale_document_id_469045191_absent") is not True
        or selection_record.get("candidate_count_before") != 100
        or selection_record.get("candidate_count_after") != 100
        or selection_record.get("changed_candidate_ids") != ["72288139"]
        or selection_record.get("non_72288139_rows_byte_unchanged") is not True
        or selection_record.get("document_count_after") != 339
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 semantic selection/unit diff differs"
        )
    serialized_722 = json.dumps(overlay_by_candidate["72288139"], sort_keys=True)
    if "469045191" in serialized_722:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 corrected 72288139 row retains stale document 469045191"
        )


def _verify_r2_inventory(
    record: Mapping[str, Any],
    *,
    root: Path,
    paths: Mapping[str, Path],
    payloads: Mapping[str, bytes],
    packet_sha256: str,
    commitments: list[JsonRecord],
) -> set[Path]:
    if (
        record.get("artifact")
        != str(CYCLE1_STAGE51_FINALIZED_UNITS_PROPOSAL_SHA_INVENTORY_V1)
        or record.get("status")
        != "provider-free exact-byte inventory; non-authoritative"
        or record.get("canonical_packet_sha256") != packet_sha256
    ):
        raise ManifestUnitizerCommandError("Stage-51 r2 byte inventory header differs")
    inventory_paths: set[Path] = set()
    for section_name in ("inputs", "outputs"):
        section = record.get(section_name)
        if not isinstance(section, Mapping) or not section:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 byte inventory lacks {section_name}"
            )
        section_record = cast(Mapping[object, object], section)
        for raw_label, raw_entry in section_record.items():
            label = str(raw_label)
            if not isinstance(raw_entry, Mapping):
                raise ManifestUnitizerCommandError(
                    f"Stage-51 r2 inventory entry is invalid: {label}"
                )
            entry = cast(Mapping[str, object], raw_entry)
            path_value = entry.get("path")
            digest = entry.get("sha256")
            byte_count = entry.get("byte_count")
            if (
                not isinstance(path_value, str)
                or not Path(path_value).is_absolute()
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or type(byte_count) is not int
                or byte_count < 0
            ):
                raise ManifestUnitizerCommandError(
                    f"Stage-51 r2 inventory entry fields are invalid: {label}"
                )
            path = Path(path_value)
            payload = _read_regular_input(path, f"Stage-51 r2 inventory {label}")
            if (
                hashlib.sha256(payload).hexdigest() != digest
                or len(payload) != byte_count
            ):
                raise ManifestUnitizerCommandError(
                    f"Stage-51 r2 inventory bytes changed: {label}"
                )
            if path in inventory_paths:
                raise ManifestUnitizerCommandError(
                    f"Stage-51 r2 inventory repeats path: {path}"
                )
            inventory_paths.add(path)
            if path not in paths.values():
                commitments.append(
                    _file_commitment(path, f"stage51_r2_inventory_{label}", payload)
                )
    expected_outputs = {
        "selection_proposal": paths["selection"],
        "prediction_units_overlay": paths["overlay"],
        "owner_packet_json": paths["packet"],
        "validation_report": paths["validation"],
        "semantic_diff": paths["semantic_diff"],
        "integration_proposal": paths["integration_proposal"],
    }
    outputs = cast(Mapping[str, object], record["outputs"])
    for label, path in expected_outputs.items():
        raw = outputs.get(label)
        if not isinstance(raw, Mapping) or cast(Mapping[str, object], raw).get(
            "path"
        ) != str(path):
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 inventory output binding differs: {label}"
            )
    if any(path.parent != root for path in expected_outputs.values()):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 inventory output escapes proposal root"
        )
    return inventory_paths


def _verify_r2_checksums(payload: bytes, *, required_paths: set[Path]) -> None:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 sha256s manifest is not UTF-8"
        ) from exc
    if len(lines) != 17:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 sha256s manifest must contain exactly 17 entries"
        )
    observed: set[Path] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (/.+)", line)
        if match is None:
            raise ManifestUnitizerCommandError(
                "Stage-51 r2 sha256s manifest has an invalid entry"
            )
        digest, raw_path = match.groups()
        path = Path(raw_path)
        if path in observed:
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 sha256s manifest repeats path: {path}"
            )
        observed.add(path)
        if (
            hashlib.sha256(
                _read_regular_input(path, "Stage-51 r2 checksum target")
            ).hexdigest()
            != digest
        ):
            raise ManifestUnitizerCommandError(
                f"Stage-51 r2 checksum target changed: {path}"
            )
    missing = required_paths - observed
    if missing:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 sha256s manifest omits required paths: "
            + ", ".join(str(path) for path in sorted(missing))
        )


def _authenticate_fresh_five_evidence(
    args: argparse.Namespace,
    *,
    prepared: PreparedManifestUnitizerInputs,
    commitments: list[JsonRecord],
) -> tuple[tuple[JsonRecord, ...], tuple[JsonRecord, ...]]:
    fields = {
        "selection": (
            "fresh_five_selection",
            "expected_fresh_five_selection_sha256",
        ),
        "units": ("fresh_five_units", "expected_fresh_five_units_sha256"),
        "audit": ("fresh_five_audit", "expected_fresh_five_audit_sha256"),
        "run_card": (
            "fresh_five_run_card",
            "expected_fresh_five_run_card_sha256",
        ),
        "review_queue": (
            "fresh_five_review_queue",
            "expected_fresh_five_review_queue_sha256",
        ),
        "terminal_queue": (
            "fresh_five_terminal_review_queue",
            "expected_fresh_five_terminal_review_queue_sha256",
        ),
    }
    paths: dict[str, Path] = {}
    payloads: dict[str, bytes] = {}
    for label, (path_field, digest_field) in fields.items():
        path = _required_path_argument(args, path_field)
        payload = _read_regular_input(path, f"fresh-five {label}")
        if hashlib.sha256(payload).hexdigest() != _required_digest_argument(
            args, digest_field
        ):
            raise ManifestUnitizerCommandError(
                f"fresh-five {label} differs from its expected SHA-256"
            )
        paths[label] = path
        payloads[label] = payload
        commitments.append(_file_commitment(path, f"fresh_five_{label}", payload))
    if payloads["review_queue"] or payloads["terminal_queue"]:
        raise ManifestUnitizerCommandError(
            "fresh-five replay evidence must have empty review queues"
        )
    selection_records = _jsonl_records_from_bytes(
        payloads["selection"],
        label="fresh-five selection",
        error_factory=ManifestUnitizerCommandError,
    )
    expected_selection = tuple(
        dict(record)
        for record in prepared.selection_records
        if str(record["candidate_id"]) in _R2_FRESH_CANDIDATE_IDS
    )
    if selection_records != expected_selection:
        raise ManifestUnitizerCommandError(
            "fresh-five selection differs from the corrected selection subset"
        )
    unit_records = _jsonl_records_from_bytes(
        payloads["units"],
        label="fresh-five units",
        error_factory=ManifestUnitizerCommandError,
    )
    audit_records = _jsonl_records_from_bytes(
        payloads["audit"],
        label="fresh-five audit",
        error_factory=ManifestUnitizerCommandError,
    )
    if len(unit_records) != 5 or len(audit_records) != 5:
        raise ManifestUnitizerCommandError(
            "fresh-five evidence must contain exactly five unit and audit rows"
        )
    units_by_candidate = _records_by_candidate(unit_records, label="fresh-five units")
    unit_count = 0
    for selection in expected_selection:
        candidate_id = str(selection["candidate_id"])
        record = units_by_candidate.get(candidate_id)
        if record is None:
            raise ManifestUnitizerCommandError(
                f"fresh-five units omit candidate {candidate_id}"
            )
        _validate_retained_record(record, selection=selection, prepared=prepared)
        unit_count += len(cast(list[object], record["prediction_units"]))
    if unit_count != 21:
        raise ManifestUnitizerCommandError(
            "fresh-five evidence must contain exactly 21 scorable units"
        )
    audit_ids = tuple(str(record.get("candidate_id")) for record in audit_records)
    expected_ids = tuple(str(record["candidate_id"]) for record in expected_selection)
    if audit_ids != expected_ids:
        raise ManifestUnitizerCommandError(
            "fresh-five audit order differs from corrected selection order"
        )
    for audit in audit_records:
        metadata = audit.get("metadata")
        provider_attempt_count = (
            cast(Mapping[str, object], metadata).get("provider_attempt_count")
            if isinstance(metadata, Mapping)
            else None
        )
        if (
            audit.get("stage") != "llm-unitize"
            or audit.get("status") != "succeeded"
            or audit.get("model_key") != _LABELING_MODEL_KEY
            or not isinstance(metadata, Mapping)
            or provider_attempt_count != "0"
            or audit.get("review_items") != []
            or audit.get("unitization_review_queue") != []
        ):
            raise ManifestUnitizerCommandError(
                f"{audit.get('candidate_id')}: fresh-five audit is not a settled replay"
            )
    card = _json_object_from_bytes(payloads["run_card"], "fresh-five run card")
    if (
        card.get("schema_version") != str(ACQUISITION_RUN_CARD_V1)
        or card.get("stage") != "llm-unitize-manifest"
        or card.get("status") != "completed"
        or card.get("record_count") != 5
        or card.get("selection_count") != 5
        or card.get("selection_sha256")
        != hashlib.sha256(payloads["selection"]).hexdigest()
        or card.get("terminal_escalation_count") != 0
    ):
        raise ManifestUnitizerCommandError("fresh-five run card semantics differ")
    return unit_records, audit_records

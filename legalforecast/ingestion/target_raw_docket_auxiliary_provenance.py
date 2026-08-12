"""Provider-free bridge for recovered target docket HTML.

The final153 screening snapshot remains the sole authority for eligibility and
selection.  This module only joins its already accepted selected candidates to
the nine raw docket pages recovered under the separately authenticated Stage33
receipt.  It deliberately does not screen, rank, select, call a provider, or
materialize a replacement screening snapshot.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_V1,
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cohort_document_materializer import (
    prepare_non_symlink_directory,
    require_non_symlink_components,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_verified_screening_snapshot,
)
from legalforecast.ingestion.target_raw_docket_recovery import (
    TargetRawDocketRecoveryError,
    load_target_raw_docket_recovery_provider_contract_retry_plan,
    resolve_target_raw_docket_recovery_provider_contract_retry,
    verify_target_raw_docket_recovery_receipt,
)

TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_SCHEMA = str(
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_V1
)
TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_SCHEMA = str(
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_V1
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE = re.compile(r"courtlistener-docket-[1-9][0-9]*\Z")


class TargetRawDocketAuxiliaryProvenanceError(ValueError):
    """Raised when the provider-free auxiliary raw bridge is not authentic."""


@dataclass(frozen=True, slots=True)
class VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    """Authenticated bridge plus the selected raw bytes needed by packet planning."""

    bridge_path: Path
    bridge_sha256: str
    raw_artifacts_manifest_path: Path
    raw_artifacts_manifest_sha256: str
    run_card_path: Path
    run_card_sha256: str
    source_snapshot_path: Path
    source_snapshot_manifest_sha256: str
    source_raw_html_dir: Path
    selected_candidate_ids: tuple[str, ...]
    raw_artifact_bytes_by_candidate: Mapping[str, bytes]
    raw_artifact_bytes_by_path: Mapping[str, bytes]
    verified_artifact_bytes: Mapping[str, bytes] = field(
        default_factory=lambda: cast(Mapping[str, bytes], {})
    )
    verified_artifact_absences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _BridgeInputs:
    selection_path: Path
    expected_selection_sha256: str
    source_snapshot_path: Path
    expected_source_snapshot_manifest_sha256: str
    expected_cycle_hash: str
    source_union_run_card_path: Path
    expected_source_union_run_card_sha256: str
    source_cycle_store_path: Path
    source_raw_artifacts_manifest_path: Path
    expected_source_raw_artifacts_manifest_sha256: str
    source_raw_html_dir: Path
    recovery_plan_path: Path
    expected_recovery_plan_sha256: str
    recovery_receipt_path: Path
    expected_recovery_receipt_sha256: str
    recovery_successes_path: Path
    recovery_exclusions_path: Path
    recovery_summary_path: Path
    recovery_raw_html_dir: Path
    raw_artifacts_manifest_path: Path
    bridge_path: Path
    run_card_path: Path


@dataclass(frozen=True, slots=True)
class _BridgeMaterial:
    raw_artifacts_manifest: bytes
    bridge_body: Mapping[str, object]
    run_card_body: Mapping[str, object]
    selected_candidate_ids: tuple[str, ...]
    raw_artifact_bytes_by_candidate: Mapping[str, bytes]
    verified_input_bytes: Mapping[str, bytes]
    verified_input_absences: tuple[str, ...]


def build_target_raw_docket_auxiliary_provenance_bridge(
    *,
    selection_path: Path,
    expected_selection_sha256: str,
    source_snapshot_path: Path,
    expected_source_snapshot_manifest_sha256: str,
    expected_cycle_hash: str,
    source_union_run_card_path: Path,
    expected_source_union_run_card_sha256: str,
    source_cycle_store_path: Path,
    source_raw_artifacts_manifest_path: Path,
    expected_source_raw_artifacts_manifest_sha256: str,
    source_raw_html_dir: Path,
    recovery_plan_path: Path,
    expected_recovery_plan_sha256: str,
    recovery_receipt_path: Path,
    expected_recovery_receipt_sha256: str,
    recovery_successes_path: Path,
    recovery_exclusions_path: Path,
    recovery_summary_path: Path,
    recovery_raw_html_dir: Path,
    raw_artifacts_manifest_path: Path,
    bridge_path: Path,
    run_card_path: Path,
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    """Build a deterministic provider-free bridge and its derived raw manifest."""

    inputs = _BridgeInputs(
        selection_path=selection_path,
        expected_selection_sha256=expected_selection_sha256,
        source_snapshot_path=source_snapshot_path,
        expected_source_snapshot_manifest_sha256=expected_source_snapshot_manifest_sha256,
        expected_cycle_hash=expected_cycle_hash,
        source_union_run_card_path=source_union_run_card_path,
        expected_source_union_run_card_sha256=expected_source_union_run_card_sha256,
        source_cycle_store_path=source_cycle_store_path,
        source_raw_artifacts_manifest_path=source_raw_artifacts_manifest_path,
        expected_source_raw_artifacts_manifest_sha256=(
            expected_source_raw_artifacts_manifest_sha256
        ),
        source_raw_html_dir=source_raw_html_dir,
        recovery_plan_path=recovery_plan_path,
        expected_recovery_plan_sha256=expected_recovery_plan_sha256,
        recovery_receipt_path=recovery_receipt_path,
        expected_recovery_receipt_sha256=expected_recovery_receipt_sha256,
        recovery_successes_path=recovery_successes_path,
        recovery_exclusions_path=recovery_exclusions_path,
        recovery_summary_path=recovery_summary_path,
        recovery_raw_html_dir=recovery_raw_html_dir,
        raw_artifacts_manifest_path=raw_artifacts_manifest_path,
        bridge_path=bridge_path,
        run_card_path=run_card_path,
    )
    material = _assemble(inputs)
    bridge_payload = _bridge_payload(material.bridge_body)
    run_card_payload = _run_card_payload(material.run_card_body)
    _write_immutable(raw_artifacts_manifest_path, material.raw_artifacts_manifest)
    _write_immutable(bridge_path, bridge_payload)
    _write_immutable(run_card_path, run_card_payload)
    return _verified_result(
        inputs=inputs,
        material=material,
        bridge_payload=bridge_payload,
        run_card_payload=run_card_payload,
    )


def verify_target_raw_docket_auxiliary_provenance_bridge(
    *,
    selection_path: Path,
    expected_selection_sha256: str,
    source_snapshot_path: Path,
    expected_source_snapshot_manifest_sha256: str,
    expected_cycle_hash: str,
    source_union_run_card_path: Path,
    expected_source_union_run_card_sha256: str,
    source_cycle_store_path: Path,
    source_raw_artifacts_manifest_path: Path,
    expected_source_raw_artifacts_manifest_sha256: str,
    source_raw_html_dir: Path,
    recovery_plan_path: Path,
    expected_recovery_plan_sha256: str,
    recovery_receipt_path: Path,
    expected_recovery_receipt_sha256: str,
    recovery_successes_path: Path,
    recovery_exclusions_path: Path,
    recovery_summary_path: Path,
    recovery_raw_html_dir: Path,
    raw_artifacts_manifest_path: Path,
    bridge_path: Path,
    run_card_path: Path,
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    """Reauthenticate a bridge from every pinned source without side effects."""

    inputs = _BridgeInputs(
        selection_path=selection_path,
        expected_selection_sha256=expected_selection_sha256,
        source_snapshot_path=source_snapshot_path,
        expected_source_snapshot_manifest_sha256=expected_source_snapshot_manifest_sha256,
        expected_cycle_hash=expected_cycle_hash,
        source_union_run_card_path=source_union_run_card_path,
        expected_source_union_run_card_sha256=expected_source_union_run_card_sha256,
        source_cycle_store_path=source_cycle_store_path,
        source_raw_artifacts_manifest_path=source_raw_artifacts_manifest_path,
        expected_source_raw_artifacts_manifest_sha256=(
            expected_source_raw_artifacts_manifest_sha256
        ),
        source_raw_html_dir=source_raw_html_dir,
        recovery_plan_path=recovery_plan_path,
        expected_recovery_plan_sha256=expected_recovery_plan_sha256,
        recovery_receipt_path=recovery_receipt_path,
        expected_recovery_receipt_sha256=expected_recovery_receipt_sha256,
        recovery_successes_path=recovery_successes_path,
        recovery_exclusions_path=recovery_exclusions_path,
        recovery_summary_path=recovery_summary_path,
        recovery_raw_html_dir=recovery_raw_html_dir,
        raw_artifacts_manifest_path=raw_artifacts_manifest_path,
        bridge_path=bridge_path,
        run_card_path=run_card_path,
    )
    material = _assemble(inputs)
    bridge_payload = _pinned_file(bridge_path, _sha256_file(bridge_path), "bridge")
    run_card_payload = _pinned_file(
        run_card_path, _sha256_file(run_card_path), "bridge run card"
    )
    if bridge_payload != _bridge_payload(material.bridge_body):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary raw bridge does not canonically replay"
        )
    if run_card_payload != _run_card_payload(material.run_card_body):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary raw bridge run card does not canonically replay"
        )
    if _safe_read(raw_artifacts_manifest_path, "augmented raw-artifact manifest") != (
        material.raw_artifacts_manifest
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "augmented raw-artifact manifest does not replay"
        )
    return _verified_result(
        inputs=inputs,
        material=material,
        bridge_payload=bridge_payload,
        run_card_payload=run_card_payload,
    )


def load_verified_target_raw_docket_auxiliary_provenance_bridge(
    bridge_path: Path,
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    """Load a bridge descriptor and reauthenticate each committed dependency."""

    envelope_payload = _safe_read(bridge_path, "auxiliary raw bridge")
    envelope = _json_object(envelope_payload, "auxiliary raw bridge")
    if set(envelope) != {"schema_version", "bridge", "bridge_sha256"}:
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary raw bridge is malformed"
        )
    if (
        envelope.get("schema_version")
        != TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_SCHEMA
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary raw bridge schema differs"
        )
    body = _mapping(envelope.get("bridge"), "auxiliary raw bridge body")
    if envelope.get("bridge_sha256") != _canonical_sha256(body, "auxiliary raw bridge"):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary raw bridge body commitment differs"
        )
    source = _mapping(body.get("source"), "auxiliary raw bridge source")
    selection = _mapping(body.get("selection"), "auxiliary raw bridge selection")
    recovery = _mapping(body.get("recovery"), "auxiliary raw bridge recovery")
    output = _mapping(body.get("output"), "auxiliary raw bridge output")
    return verify_target_raw_docket_auxiliary_provenance_bridge(
        selection_path=_path(selection, "path", "selection"),
        expected_selection_sha256=_sha(selection, "sha256", "selection"),
        source_snapshot_path=_path(source, "screening_snapshot_path", "source"),
        expected_source_snapshot_manifest_sha256=_sha(
            source, "screening_snapshot_manifest_sha256", "source"
        ),
        expected_cycle_hash=_sha(source, "cycle_hash", "source"),
        source_union_run_card_path=_path(source, "union_run_card_path", "source"),
        expected_source_union_run_card_sha256=_sha(
            source, "union_run_card_sha256", "source"
        ),
        source_cycle_store_path=_path(source, "cycle_store_path", "source"),
        source_raw_artifacts_manifest_path=_path(
            source, "raw_artifacts_manifest_path", "source"
        ),
        expected_source_raw_artifacts_manifest_sha256=_sha(
            source, "raw_artifacts_manifest_sha256", "source"
        ),
        source_raw_html_dir=_path(source, "raw_html_dir", "source"),
        recovery_plan_path=_path(recovery, "plan_path", "recovery"),
        expected_recovery_plan_sha256=_sha(recovery, "plan_sha256", "recovery"),
        recovery_receipt_path=_path(recovery, "receipt_path", "recovery"),
        expected_recovery_receipt_sha256=_sha(recovery, "receipt_sha256", "recovery"),
        recovery_successes_path=_path(recovery, "successes_path", "recovery"),
        recovery_exclusions_path=_path(recovery, "exclusions_path", "recovery"),
        recovery_summary_path=_path(recovery, "summary_path", "recovery"),
        recovery_raw_html_dir=_path(recovery, "raw_html_dir", "recovery"),
        raw_artifacts_manifest_path=_path(
            output, "raw_artifacts_manifest_path", "output"
        ),
        bridge_path=bridge_path,
        run_card_path=_path(output, "run_card_path", "output"),
    )


def _assemble(inputs: _BridgeInputs) -> _BridgeMaterial:
    _validate_sha256(inputs.expected_selection_sha256, "selection")
    _validate_sha256(
        inputs.expected_source_snapshot_manifest_sha256, "source snapshot manifest"
    )
    _validate_sha256(inputs.expected_cycle_hash, "cycle")
    _validate_sha256(inputs.expected_source_union_run_card_sha256, "source union card")
    _validate_sha256(
        inputs.expected_source_raw_artifacts_manifest_sha256,
        "source raw-artifact manifest",
    )
    _validate_sha256(inputs.expected_recovery_plan_sha256, "recovery plan")
    _validate_sha256(inputs.expected_recovery_receipt_sha256, "recovery receipt")

    selection_payload = _pinned_file(
        inputs.selection_path, inputs.expected_selection_sha256, "selection"
    )
    selected_candidate_ids = _selected_candidate_ids(selection_payload)
    source_card_payload = _pinned_file(
        inputs.source_union_run_card_path,
        inputs.expected_source_union_run_card_sha256,
        "source union run card",
    )
    source_card = _json_object(source_card_payload, "source union run card")
    _validate_source_union_card(source_card, inputs)
    try:
        snapshot = load_verified_screening_snapshot(
            inputs.source_snapshot_path,
            expected_manifest_sha256=inputs.expected_source_snapshot_manifest_sha256,
            expected_cycle_hash=inputs.expected_cycle_hash,
        )
    except (ScreeningSnapshotUnionError, ValueError) as exc:
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"source final screening snapshot is not authenticated: {exc}"
        ) from exc
    accepted_ids = {candidate.candidate_id for candidate in snapshot.candidates}
    if not set(selected_candidate_ids) <= accepted_ids:
        missing = sorted(set(selected_candidate_ids) - accepted_ids)
        raise TargetRawDocketAuxiliaryProvenanceError(
            "selected candidates are not accepted by the final screening snapshot: "
            + ", ".join(missing)
        )

    base_payload = _pinned_file(
        inputs.source_raw_artifacts_manifest_path,
        inputs.expected_source_raw_artifacts_manifest_sha256,
        "source raw-artifact manifest",
    )
    base_records = _raw_artifact_records(
        base_payload,
        raw_root=inputs.source_raw_html_dir,
        label="source raw-artifact manifest",
    )
    expected_output = _mapping(source_card.get("output_commitments"), "source output")
    expected_raw = _mapping(expected_output.get("owned_raw_artifacts"), "source raw")
    if (
        expected_raw.get("sha256")
        != inputs.expected_source_raw_artifacts_manifest_sha256
        or expected_raw.get("byte_count") != len(base_payload)
        or expected_raw.get("row_count") != len(base_records)
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "source union run card does not bind the raw-artifact manifest"
        )

    try:
        retry_plan = load_target_raw_docket_recovery_provider_contract_retry_plan(
            inputs.recovery_plan_path, inputs.expected_recovery_plan_sha256
        )
        recovery_authority_bytes: dict[str, bytes] = {}
        recovery_authority_absences: set[str] = set()
        _root, recovered_plan, _successor = (
            resolve_target_raw_docket_recovery_provider_contract_retry(
                retry_plan,
                _verified_byte_closure=recovery_authority_bytes,
                _verified_absence_closure=recovery_authority_absences,
            )
        )
        receipt = verify_target_raw_docket_recovery_receipt(
            receipt_path=inputs.recovery_receipt_path,
            expected_receipt_sha256=inputs.expected_recovery_receipt_sha256,
            expected_plan_sha256=inputs.expected_recovery_plan_sha256,
            successes_path=inputs.recovery_successes_path,
            exclusions_path=inputs.recovery_exclusions_path,
            summary_path=inputs.recovery_summary_path,
            raw_html_dir=inputs.recovery_raw_html_dir,
        )
    except TargetRawDocketRecoveryError as exc:
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"target raw-docket recovery is not authenticated: {exc}"
        ) from exc
    _validate_recovery_lineage(
        receipt=receipt,
        recovered_plan=recovered_plan,
        inputs=inputs,
    )
    recovery_records = _recovery_raw_artifact_records(
        receipt, inputs.recovery_raw_html_dir
    )
    if _read_jsonl(inputs.recovery_exclusions_path, "recovery exclusions"):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "auxiliary bridge requires a complete recovery with no exclusions"
        )

    by_candidate: dict[str, dict[str, object]] = {
        cast(str, record["candidate_id"]): record for record in base_records
    }
    recovered_by_candidate: dict[str, dict[str, object]] = {
        cast(str, record["candidate_id"]): record for record in recovery_records
    }
    overlap = set(by_candidate) & set(recovered_by_candidate)
    if overlap:
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery repeats canonical source raw artifacts: "
            + ", ".join(sorted(overlap))
        )
    augmented_by_candidate = {**by_candidate, **recovered_by_candidate}
    if set(selected_candidate_ids) != set(selected_candidate_ids) & set(
        augmented_by_candidate
    ):
        missing = sorted(set(selected_candidate_ids) - set(augmented_by_candidate))
        raise TargetRawDocketAuxiliaryProvenanceError(
            "selected candidates lack one raw docket identity after recovery: "
            + ", ".join(missing)
        )
    recovered_selected = set(selected_candidate_ids) & set(recovered_by_candidate)
    expected_recovered = set(selected_candidate_ids) - set(by_candidate)
    if (
        recovered_selected != expected_recovered
        or set(recovered_by_candidate) != expected_recovered
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery candidates are not exactly selected-minus-source-raw"
        )

    selected_bytes: dict[str, bytes] = {}
    for candidate_id in selected_candidate_ids:
        record = augmented_by_candidate[candidate_id]
        payload = _pinned_file(
            Path(cast(str, record["path"])),
            cast(str, record["sha256"]),
            f"raw docket HTML {candidate_id}",
        )
        if len(payload) != record["byte_count"]:
            raise TargetRawDocketAuxiliaryProvenanceError(
                f"raw docket HTML byte count differs: {candidate_id}"
            )
        selected_bytes[candidate_id] = payload

    verified_input_bytes: dict[str, bytes] = {}
    _merge_verified_byte_pairs(
        verified_input_bytes,
        (
            (os.path.abspath(inputs.selection_path), selection_payload),
            (os.path.abspath(inputs.source_union_run_card_path), source_card_payload),
            (os.path.abspath(inputs.source_raw_artifacts_manifest_path), base_payload),
            (
                os.path.abspath(inputs.recovery_plan_path),
                _pinned_file(
                    inputs.recovery_plan_path,
                    inputs.expected_recovery_plan_sha256,
                    "recovery plan",
                ),
            ),
            (
                os.path.abspath(inputs.recovery_receipt_path),
                _pinned_file(
                    inputs.recovery_receipt_path,
                    inputs.expected_recovery_receipt_sha256,
                    "recovery receipt",
                ),
            ),
            (
                os.path.abspath(inputs.recovery_successes_path),
                _pinned_file(
                    inputs.recovery_successes_path,
                    _sha(receipt, "successes_sha256", "recovery receipt"),
                    "recovery successes",
                ),
            ),
            (
                os.path.abspath(inputs.recovery_exclusions_path),
                _pinned_file(
                    inputs.recovery_exclusions_path,
                    _sha(receipt, "exclusions_sha256", "recovery receipt"),
                    "recovery exclusions",
                ),
            ),
            (
                os.path.abspath(inputs.recovery_summary_path),
                _pinned_file(
                    inputs.recovery_summary_path,
                    _sha(receipt, "summary_sha256", "recovery receipt"),
                    "recovery summary",
                ),
            ),
        ),
    )
    _merge_verified_bytes(verified_input_bytes, recovery_authority_bytes)
    verified_input_absences: set[str] = set(recovery_authority_absences)
    recovery_authority_paths = (
        (retry_plan.root_plan_path, retry_plan.root_plan_sha256),
        (
            retry_plan.root_failure_run_card_path,
            retry_plan.root_failure_run_card_sha256,
        ),
        (
            retry_plan.direct_successor_plan_path,
            retry_plan.direct_successor_plan_sha256,
        ),
        (
            retry_plan.direct_successor_failure_run_card_path,
            retry_plan.direct_successor_failure_run_card_sha256,
        ),
        (
            retry_plan.provider_contract_defect_authorization_path,
            retry_plan.provider_contract_defect_authorization_sha256,
        ),
        (
            recovered_plan.source_snapshot_run_card_path,
            recovered_plan.source_snapshot_run_card_sha256,
        ),
        (
            recovered_plan.source_raw_manifest_path,
            recovered_plan.source_raw_manifest_sha256,
        ),
    )
    for path, digest in recovery_authority_paths:
        authority_path = Path(path)
        _merge_verified_bytes(
            verified_input_bytes,
            {
                os.path.abspath(authority_path): _pinned_file(
                    authority_path, digest, "recovery authority"
                )
            },
        )
    for filename, payload in snapshot.payloads.items():
        _merge_verified_bytes(
            verified_input_bytes,
            {os.path.abspath(inputs.source_snapshot_path / filename): payload},
        )
    for artifact in snapshot.raw_artifacts:
        if artifact.content is None or not artifact.content_authenticated:
            raise TargetRawDocketAuxiliaryProvenanceError(
                "source screening snapshot raw-docket closure is incomplete"
            )
        _merge_verified_bytes(
            verified_input_bytes,
            {os.path.abspath(artifact.path): artifact.content},
        )
    for path, payload in {
        cast(str, record["path"]): selected_bytes[cast(str, record["candidate_id"])]
        for record in (*base_records, *recovery_records)
        if cast(str, record["candidate_id"]) in selected_bytes
    }.items():
        _merge_verified_bytes(verified_input_bytes, {os.path.abspath(path): payload})

    # Preserve the canonical union's manifest bytes exactly.  The bridge adds
    # only the independently authenticated recovery rows, so replay can prove
    # it did not normalize, reorder, or otherwise rewrite the frozen baseline.
    recovery_payload = _jsonl_bytes(
        [
            recovered_by_candidate[candidate]
            for candidate in sorted(recovered_by_candidate)
        ]
    )
    manifest_payload = base_payload + recovery_payload
    augmented_record_count = len(base_records) + len(recovery_records)
    bridge_body: dict[str, object] = {
        "stage": "target-raw-docket-auxiliary-provenance-bridge",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source": {
            "screening_snapshot_path": str(inputs.source_snapshot_path.resolve()),
            "screening_snapshot_manifest_sha256": (
                inputs.expected_source_snapshot_manifest_sha256
            ),
            "union_run_card_path": str(inputs.source_union_run_card_path.resolve()),
            "union_run_card_sha256": inputs.expected_source_union_run_card_sha256,
            "cycle_store_path": str(inputs.source_cycle_store_path.resolve()),
            "cycle_hash": inputs.expected_cycle_hash,
            "raw_artifacts_manifest_path": str(
                inputs.source_raw_artifacts_manifest_path.resolve()
            ),
            "raw_artifacts_manifest_sha256": (
                inputs.expected_source_raw_artifacts_manifest_sha256
            ),
            "raw_html_dir": str(inputs.source_raw_html_dir.resolve()),
            "raw_artifact_count": len(base_records),
        },
        "selection": {
            "path": str(inputs.selection_path.resolve()),
            "sha256": inputs.expected_selection_sha256,
            "candidate_count": len(selected_candidate_ids),
            "candidate_id_set_sha256": _candidate_set_sha256(selected_candidate_ids),
        },
        "recovery": {
            "plan_path": str(inputs.recovery_plan_path.resolve()),
            "plan_sha256": inputs.expected_recovery_plan_sha256,
            "receipt_path": str(inputs.recovery_receipt_path.resolve()),
            "receipt_sha256": inputs.expected_recovery_receipt_sha256,
            "successes_path": str(inputs.recovery_successes_path.resolve()),
            "successes_sha256": _sha256_file(inputs.recovery_successes_path),
            "exclusions_path": str(inputs.recovery_exclusions_path.resolve()),
            "exclusions_sha256": _sha256_file(inputs.recovery_exclusions_path),
            "summary_path": str(inputs.recovery_summary_path.resolve()),
            "summary_sha256": _sha256_file(inputs.recovery_summary_path),
            "raw_html_dir": str(inputs.recovery_raw_html_dir.resolve()),
            "raw_artifact_count": len(recovery_records),
        },
        "output": {
            "raw_artifacts_manifest_path": str(
                inputs.raw_artifacts_manifest_path.resolve()
            ),
            "raw_artifacts_manifest_sha256": hashlib.sha256(
                manifest_payload
            ).hexdigest(),
            "raw_artifact_count": augmented_record_count,
            "selected_raw_coverage_count": len(selected_candidate_ids),
            "run_card_path": str(inputs.run_card_path.resolve()),
        },
    }
    run_card_body: dict[str, object] = {
        "stage": "build-target-raw-docket-auxiliary-provenance-bridge",
        "status": "completed",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "bridge_sha256": hashlib.sha256(_bridge_payload(bridge_body)).hexdigest(),
        "raw_artifacts_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "selected_raw_coverage_count": len(selected_candidate_ids),
    }
    return _BridgeMaterial(
        raw_artifacts_manifest=manifest_payload,
        bridge_body=bridge_body,
        run_card_body=run_card_body,
        selected_candidate_ids=selected_candidate_ids,
        raw_artifact_bytes_by_candidate=selected_bytes,
        verified_input_bytes=verified_input_bytes,
        verified_input_absences=tuple(sorted(verified_input_absences)),
    )


def _validate_source_union_card(
    card: Mapping[str, object], inputs: _BridgeInputs
) -> None:
    if (
        card.get("schema_version")
        # contract-ratchet: allow frozen source schema is authenticated by its run card.
        != "legalforecast.screening_snapshot_union_summary.v1"
        or card.get("status") != "completed"
        or card.get("snapshot_path") != str(inputs.source_snapshot_path.resolve())
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "source union run card does not bind the final screening snapshot"
        )
    input_paths = card.get("input_paths")
    if not isinstance(input_paths, list) or not input_paths:
        raise TargetRawDocketAuxiliaryProvenanceError(
            "source union run card inputs are invalid"
        )
    typed_input_paths = cast(Sequence[object], input_paths)
    if (
        Path(str(typed_input_paths[0])).resolve()
        != inputs.source_cycle_store_path.resolve()
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "source union run card does not bind the expected cycle store"
        )


def _validate_recovery_lineage(
    *,
    receipt: Mapping[str, object],
    recovered_plan: Any,
    inputs: _BridgeInputs,
) -> None:
    expected = {
        "cycle_hash": inputs.expected_cycle_hash,
        "source_snapshot_manifest_sha256": (
            inputs.expected_source_snapshot_manifest_sha256
        ),
        "cycle_store_path": str(inputs.source_cycle_store_path.resolve()),
        "selection_path": str(inputs.selection_path.resolve()),
        "selection_sha256": inputs.expected_selection_sha256,
    }
    if any(
        receipt.get(name) != value
        for name, value in expected.items()
        if name in receipt
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery receipt does not bind the final153 source authority"
        )
    if (
        receipt.get("cycle_hash") != inputs.expected_cycle_hash
        or receipt.get("source_snapshot_manifest_sha256")
        != inputs.expected_source_snapshot_manifest_sha256
        or receipt.get("source_batch_id") is None
        or receipt.get("source_batch_digest") is None
        or receipt.get("dry_run") is not False
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery receipt does not bind completed final153 authority"
        )
    if (
        Path(recovered_plan.selection_path).resolve() != inputs.selection_path.resolve()
        or recovered_plan.selection_sha256 != inputs.expected_selection_sha256
        or Path(recovered_plan.source_snapshot_path).resolve()
        != inputs.source_snapshot_path.resolve()
        or recovered_plan.source_snapshot_manifest_sha256
        != inputs.expected_source_snapshot_manifest_sha256
        or recovered_plan.cycle_hash != inputs.expected_cycle_hash
        or Path(recovered_plan.cycle_store_path).resolve()
        != inputs.source_cycle_store_path.resolve()
        or Path(recovered_plan.source_raw_manifest_path).resolve()
        != (inputs.source_snapshot_path / "raw-artifacts.jsonl").resolve()
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery plan does not reconstruct the final153 source authority"
        )


def _recovery_raw_artifact_records(
    receipt: Mapping[str, object], raw_root: Path
) -> list[dict[str, object]]:
    require_non_symlink_components(raw_root)
    raw_artifacts = receipt.get("raw_artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery receipt has no raw artifacts"
        )
    result: list[dict[str, object]] = []
    for record in cast(Sequence[object], raw_artifacts):
        typed = _mapping(record, "recovery raw artifact")
        candidate_id = _candidate_id(typed.get("candidate_id"), "recovery raw artifact")
        sha256 = _raw_sha256(typed.get("sha256"), "recovery raw artifact")
        byte_count = _byte_count(typed.get("byte_count"), "recovery raw artifact")
        retrieved_at = typed.get("retrieved_at")
        if not isinstance(retrieved_at, str) or not retrieved_at:
            raise TargetRawDocketAuxiliaryProvenanceError(
                "recovery raw artifact retrieved_at is invalid"
            )
        docket_id = candidate_id.removeprefix("courtlistener-docket-")
        path = raw_root / f"{docket_id}.html"
        result.append(
            {
                "candidate_id": candidate_id,
                "path": str(_absolute_path(path)),
                "sha256": sha256,
                "byte_count": byte_count,
                "retrieved_at": retrieved_at,
            }
        )
    if len({record["candidate_id"] for record in result}) != len(result):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "recovery receipt repeats a candidate"
        )
    return result


def _raw_artifact_records(
    payload: bytes, *, raw_root: Path, label: str
) -> list[dict[str, object]]:
    require_non_symlink_components(raw_root)
    records: list[dict[str, object]] = []
    for raw in _read_jsonl_bytes(payload, label):
        candidate_id = _candidate_id(raw.get("candidate_id"), label)
        sha256 = _raw_sha256(raw.get("sha256"), label)
        byte_count = _byte_count(raw.get("byte_count"), label)
        retrieved_at = raw.get("retrieved_at")
        path = raw.get("path")
        if (
            not isinstance(retrieved_at, str)
            or not retrieved_at
            or not isinstance(path, str)
        ):
            raise TargetRawDocketAuxiliaryProvenanceError(
                f"{label} record is malformed"
            )
        expected_path = raw_root / candidate_id / f"{sha256}.html"
        if _absolute_path(Path(path)) != _absolute_path(expected_path):
            raise TargetRawDocketAuxiliaryProvenanceError(
                f"{label} record path is outside the canonical raw root"
            )
        records.append(
            {
                "candidate_id": candidate_id,
                "path": str(_absolute_path(expected_path)),
                "sha256": sha256,
                "byte_count": byte_count,
                "retrieved_at": retrieved_at,
            }
        )
    if not records or len({record["candidate_id"] for record in records}) != len(
        records
    ):
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"{label} must have exactly one raw identity per candidate"
        )
    return records


def _selected_candidate_ids(payload: bytes) -> tuple[str, ...]:
    selected: list[str] = []
    for row in _read_jsonl_bytes(payload, "selection"):
        if row.get("selected") is not True:
            continue
        raw_id = row.get("candidate_id")
        if not isinstance(raw_id, str):
            raise TargetRawDocketAuxiliaryProvenanceError(
                "selected candidate ID is invalid"
            )
        candidate_id = (
            raw_id
            if raw_id.startswith("courtlistener-docket-")
            else f"courtlistener-docket-{raw_id}"
        )
        _candidate_id(candidate_id, "selection")
        selected.append(candidate_id)
    if not selected or len(set(selected)) != len(selected):
        raise TargetRawDocketAuxiliaryProvenanceError(
            "selection must contain distinct selected candidate IDs"
        )
    return tuple(sorted(selected))


def _verified_result(
    *,
    inputs: _BridgeInputs,
    material: _BridgeMaterial,
    bridge_payload: bytes,
    run_card_payload: bytes,
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    verified_artifact_bytes = dict(material.verified_input_bytes)
    _merge_verified_bytes(
        verified_artifact_bytes,
        {
            os.path.abspath(inputs.raw_artifacts_manifest_path): (
                material.raw_artifacts_manifest
            ),
            os.path.abspath(inputs.bridge_path): bridge_payload,
            os.path.abspath(inputs.run_card_path): run_card_payload,
        },
    )
    return VerifiedTargetRawDocketAuxiliaryProvenanceBridge(
        bridge_path=inputs.bridge_path.resolve(),
        bridge_sha256=hashlib.sha256(bridge_payload).hexdigest(),
        raw_artifacts_manifest_path=inputs.raw_artifacts_manifest_path.resolve(),
        raw_artifacts_manifest_sha256=hashlib.sha256(
            material.raw_artifacts_manifest
        ).hexdigest(),
        run_card_path=inputs.run_card_path.resolve(),
        run_card_sha256=hashlib.sha256(run_card_payload).hexdigest(),
        source_snapshot_path=inputs.source_snapshot_path.resolve(),
        source_snapshot_manifest_sha256=(
            inputs.expected_source_snapshot_manifest_sha256
        ),
        source_raw_html_dir=inputs.source_raw_html_dir.resolve(),
        selected_candidate_ids=material.selected_candidate_ids,
        raw_artifact_bytes_by_candidate=material.raw_artifact_bytes_by_candidate,
        raw_artifact_bytes_by_path={
            str(record["path"]): material.raw_artifact_bytes_by_candidate[
                cast(str, record["candidate_id"])
            ]
            for record in _read_jsonl_bytes(
                material.raw_artifacts_manifest, "augmented raw-artifact manifest"
            )
            if cast(str, record["candidate_id"])
            in material.raw_artifact_bytes_by_candidate
        },
        verified_artifact_bytes=verified_artifact_bytes,
        verified_artifact_absences=material.verified_input_absences,
    )


def _merge_verified_bytes(
    target: dict[str, bytes], incoming: Mapping[str, bytes]
) -> None:
    """Merge verifier-owned lexical path evidence without hiding aliases."""

    for path, payload in incoming.items():
        key = os.path.abspath(path)
        existing = target.get(key)
        if existing is not None and existing != payload:
            raise TargetRawDocketAuxiliaryProvenanceError(
                "verified auxiliary bridge byte closure conflicts"
            )
        target[key] = payload


def _merge_verified_byte_pairs(
    target: dict[str, bytes], incoming: Sequence[tuple[str, bytes]]
) -> None:
    """Merge ordered evidence without pre-collapsing duplicate lexical keys."""

    for path, payload in incoming:
        _merge_verified_bytes(target, {path: payload})


def _bridge_payload(body: Mapping[str, object]) -> bytes:
    envelope = {
        "schema_version": TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_SCHEMA,
        "bridge": dict(body),
        # contract-ratchet: allow self-hash binds the descriptor envelope body.
        "bridge_sha256": hashlib.sha256(
            canonical_json_bytes(
                body,
                error_type=TargetRawDocketAuxiliaryProvenanceError,
                error_message="bridge is not canonical JSON",
            )
        ).hexdigest(),
    }
    return canonical_json_bytes(
        envelope,
        error_type=TargetRawDocketAuxiliaryProvenanceError,
        error_message="bridge is not canonical JSON",
    )


def _run_card_payload(body: Mapping[str, object]) -> bytes:
    envelope = {
        "schema_version": TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_SCHEMA,
        "run_card": dict(body),
        # contract-ratchet: allow self-hash binds the descriptor run-card body.
        "run_card_sha256": hashlib.sha256(
            canonical_json_bytes(
                body,
                error_type=TargetRawDocketAuxiliaryProvenanceError,
                error_message="bridge run card is not canonical JSON",
            )
        ).hexdigest(),
    }
    return canonical_json_bytes(
        envelope,
        error_type=TargetRawDocketAuxiliaryProvenanceError,
        error_message="bridge run card is not canonical JSON",
    )


def _write_immutable(path: Path, payload: bytes) -> None:
    parent = prepare_non_symlink_directory(path.parent)
    destination = parent / path.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError:
        if _safe_read(destination, "bridge output") != payload:
            raise TargetRawDocketAuxiliaryProvenanceError(
                f"bridge output already exists with different bytes: {destination}"
            ) from None
        return
    except OSError as exc:
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"cannot publish bridge output: {destination}"
        ) from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:  # pragma: no cover - defensive OS invariant
                raise TargetRawDocketAuxiliaryProvenanceError(
                    "short bridge output write"
                )
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if _safe_read(destination, "published bridge output") != payload:
        raise TargetRawDocketAuxiliaryProvenanceError(
            "bridge output changed while publishing"
        )


def _pinned_file(path: Path, expected_sha256: str, label: str) -> bytes:
    _validate_sha256(expected_sha256, label)
    payload = _safe_read(path, label)
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} SHA-256 mismatch")
    return payload


def _safe_read(path: Path, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except ReviewBundleError as exc:
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"{label} is not a unique regular file"
        ) from exc


# contract-ratchet: allow raw digest binds immutable source bytes.
def _sha256_file(path: Path) -> str:
    return hashlib.sha256(_safe_read(path, str(path))).hexdigest()


def _absolute_path(path: Path) -> Path:
    """Normalize a path without dereferencing a possible terminal symlink."""

    return Path(os.path.abspath(os.fspath(path)))


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(
            payload,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} is not JSON") from exc
    return _mapping(value, label)


def _read_jsonl(path: Path, label: str) -> list[Mapping[str, object]]:
    return _read_jsonl_bytes(_safe_read(path, label), label)


def _read_jsonl_bytes(payload: bytes, label: str) -> list[Mapping[str, object]]:
    if payload and not payload.endswith(b"\n"):
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} lacks final newline")
    records: list[Mapping[str, object]] = []
    for line in payload.splitlines():
        records.append(_json_object(line, label))
    return records


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(
        canonical_json_bytes(
            record,
            error_type=TargetRawDocketAuxiliaryProvenanceError,
            error_message="raw-artifact record is not canonical JSON",
        )
        for record in records
    )


# contract-ratchet: allow candidate-set identity is a descriptor field.
def _candidate_set_sha256(candidate_ids: Sequence[str]) -> str:
    # contract-ratchet: allow candidate-set digest binds its canonical identity list.
    return hashlib.sha256(
        canonical_json_bytes(
            list(candidate_ids),
            error_type=TargetRawDocketAuxiliaryProvenanceError,
            error_message="candidate set is not canonical JSON",
        )
    ).hexdigest()


# contract-ratchet: allow descriptor body self-hash verifies the immutable envelope.
def _canonical_sha256(value: Mapping[str, object], label: str) -> str:
    # contract-ratchet: allow descriptor body self-hash verifies the immutable envelope.
    return hashlib.sha256(
        canonical_json_bytes(
            value,
            error_type=TargetRawDocketAuxiliaryProvenanceError,
            error_message=f"{label} is not canonical JSON",
        )
    ).hexdigest()


def _path(record: Mapping[str, object], name: str, label: str) -> Path:
    value = record.get(name)
    if not isinstance(value, str) or not value:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} {name} is invalid")
    return Path(value)


def _sha(record: Mapping[str, object], name: str, label: str) -> str:
    value = record.get(name)
    if not isinstance(value, str):
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} {name} is invalid")
    _validate_sha256(value, f"{label} {name}")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _candidate_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _CANDIDATE.fullmatch(value) is None:
        raise TargetRawDocketAuxiliaryProvenanceError(
            f"{label} candidate ID is invalid"
        )
    return value


def _raw_sha256(value: object, label: str) -> str:
    normalized = value.removeprefix("sha256:") if isinstance(value, str) else ""
    if _SHA256.fullmatch(normalized) is None:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} SHA-256 is invalid")
    return normalized


def _byte_count(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} byte count is invalid")
    return value


def _validate_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise TargetRawDocketAuxiliaryProvenanceError(f"{label} SHA-256 is invalid")

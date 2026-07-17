"""Select immutable shard receipts and fan them into one verified aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from legalforecast.protocol.freeze import (
    FrozenArtifactName,
    sha256_file,
    verify_freeze_bundle,
)
from legalforecast.protocol.manifest import hash_payload
from legalforecast.protocol.policy_artifacts import (
    execution_policy_content,
    load_json_object,
    policy_content_sha256,
)
from legalforecast.publication.official_aggregate import (
    OfficialAggregationConfig,
    OfficialAggregationResult,
    aggregate_official_results,
)
from legalforecast.publication.shard_receipt import (
    ShardReceiptError,
    verify_committed_payload,
    verify_shard_receipt,
)
from legalforecast.reporting.cadence import CycleSeries
from legalforecast.unitization.review import (
    UnitizationReviewError,
    require_finalized_envelopes,
)

JsonRecord = dict[str, Any]
ShardKey = tuple[str, str]
ACCEPTED_ATTEMPT_MAP_SCHEMA_VERSION = "legalforecast.accepted_attempt_map.v1"
FAN_IN_REPORT_SCHEMA_VERSION = "legalforecast.shard_fan_in_report.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CYCLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_RESULT_NAMES = ("accounting", "metrics", "runs")


class FanInError(ValueError):
    """Raised when shard evidence cannot form one safe aggregate."""


@dataclass(frozen=True, slots=True)
class FrozenFanInContext:
    """Hashes every accepted receipt must reproduce from frozen bytes."""

    cycle_id: str
    freeze_bundle_sha256: str
    execution_policy_sha256: str
    execution_policy_artifact_sha256: str
    repeat_policy_sha256: str
    attempt_policy_sha256: str
    receipt_policy_sha256: str
    frozen_manifest_sha256: str
    run_input_manifest_sha256: str
    labels_sha256: str
    model_registry_sha256: str


@dataclass(frozen=True, slots=True)
class ReceiptSelection:
    """Exactly one accepted receipt for every frozen shard."""

    receipts: tuple[Mapping[str, Any], ...]
    accepted_attempt_map_sha256: str | None
    accepted_attempt_map: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class CadenceCounts:
    """Cadence inputs derived from immutable corpus artifacts."""

    clean_motion_count: int
    prediction_unit_count: int


@dataclass(frozen=True, slots=True)
class FanInConfig:
    """Inputs for one receipt-bound fan-in verification."""

    freeze_bundle_path: Path
    run_input_manifest_path: Path
    receipt_root: str
    output_dir: Path
    amendment_bundle_paths: tuple[Path, ...] = ()
    source_dispatch_run_id: str | None = None
    labels_path: Path | None = None
    model_registry_path: Path | None = None
    accepted_attempt_map_path: Path | None = None
    operator_clean_motion_count: int | None = None
    operator_prediction_unit_count: int | None = None
    baseline_training_examples_path: Path | None = None
    elapsed_days: int | None = None
    official_window_days: int | None = None
    deferred_ablations: tuple[str, ...] = ("judge_removed",)
    verify_only: bool = False


@dataclass(frozen=True, slots=True)
class FanInReport:
    """Auditable result of receipt selection and aggregate validation."""

    cycle_id: str
    mode: str
    freeze_bundle_sha256: str
    accepted_attempt_map_sha256: str | None
    accepted_attempt_map: Mapping[str, Any] | None
    accepted_receipts: tuple[Mapping[str, Any], ...]
    receipt_inventory_sha256: str
    union_inventory_sha256: str
    union_commitment_sha256: str
    frozen_artifact_sha256: Mapping[str, str]
    clean_motion_count: int
    prediction_unit_count: int
    aggregate_output_dir: Path
    aggregate_result: Mapping[str, int] | None = None
    accepted_attempt_map_path: str | None = None

    def to_record(self) -> JsonRecord:
        """Return the canonical private fan-in report."""

        return {
            "schema_version": FAN_IN_REPORT_SCHEMA_VERSION,
            "cycle_id": self.cycle_id,
            "mode": self.mode,
            "freeze_bundle_sha256": self.freeze_bundle_sha256,
            "accepted_attempt_map": (
                None
                if self.accepted_attempt_map is None
                else {
                    "source_path": self.accepted_attempt_map_path,
                    "sha256": self.accepted_attempt_map_sha256,
                    "record": dict(self.accepted_attempt_map),
                }
            ),
            "accepted_receipts": [dict(value) for value in self.accepted_receipts],
            "receipt_inventory_sha256": self.receipt_inventory_sha256,
            "union_inventory_sha256": self.union_inventory_sha256,
            "union_commitment_sha256": self.union_commitment_sha256,
            "frozen_artifact_sha256": dict(self.frozen_artifact_sha256),
            "cadence_counts": {
                "clean_motion_count": self.clean_motion_count,
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count": self.prediction_unit_count,
                "prediction_unit_count_source": "frozen_units",
            },
            "aggregate_validation": (
                dict(self.aggregate_result)
                if self.aggregate_result is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class _FrozenInputs:
    context: FrozenFanInContext
    execution_policy: Mapping[str, Any]
    manifest_path: Path
    units_path: Path
    labels_path: Path
    model_registry_path: Path
    baselines_path: Path


@dataclass(frozen=True, slots=True)
class ReceiptArtifact:
    """One discovered receipt together with its actual immutable object key."""

    actual_key: str
    raw_sha256: str
    record: Mapping[str, Any]


def select_accepted_receipts(
    receipts: Sequence[Mapping[str, Any]],
    *,
    declared_shards: Sequence[ShardKey],
    cycle_id: str,
    freeze_bundle_sha256: str,
    execution_policy_sha256: str,
    shard_schedule_sha256: str,
    accepted_attempt_map: Mapping[str, Any] | None = None,
) -> ReceiptSelection:
    """Resolve one receipt per shard, requiring a map for every ambiguity."""

    declared = tuple(sorted(set(declared_shards)))
    if len(declared) != len(declared_shards):
        raise FanInError("declared shard schedule contains duplicates")
    grouped: dict[ShardKey, list[Mapping[str, Any]]] = {}
    for receipt in receipts:
        key = (_required_str(receipt, "model_key"), _required_str(receipt, "ablation"))
        grouped.setdefault(key, []).append(receipt)
    missing = sorted(set(declared) - set(grouped))
    extra = sorted(set(grouped) - set(declared))
    if missing:
        raise FanInError(f"missing shard receipts: {missing}")
    if extra:
        raise FanInError(f"undeclared shard receipts: {extra}")
    ambiguous = {key for key, values in grouped.items() if len(values) > 1}
    if ambiguous and accepted_attempt_map is None:
        labels = ", ".join(
            f"{model_key}/{ablation}" for model_key, ablation in sorted(ambiguous)
        )
        raise FanInError(
            f"multiple receipts require a committed accepted-attempt map for: {labels}"
        )
    selections: dict[ShardKey, Mapping[str, Any]] = {}
    map_sha256: str | None = None
    if accepted_attempt_map is not None:
        if not ambiguous:
            raise FanInError(
                "accepted-attempt map is allowed only when a shard is ambiguous"
            )
        selections, map_sha256 = _validate_accepted_attempt_map(
            accepted_attempt_map,
            ambiguous_shards=ambiguous,
            cycle_id=cycle_id,
            freeze_bundle_sha256=freeze_bundle_sha256,
            execution_policy_sha256=execution_policy_sha256,
            shard_schedule_sha256=shard_schedule_sha256,
        )
    accepted: list[Mapping[str, Any]] = []
    for key in declared:
        candidates = grouped[key]
        if len(candidates) == 1:
            accepted.append(candidates[0])
            continue
        selection = selections[key]
        matches = [
            receipt
            for receipt in candidates
            if _receipt_matches_selection(receipt, selection)
        ]
        if len(matches) != 1:
            raise FanInError(
                "accepted-attempt selection does not identify exactly one receipt "
                f"for {key[0]}/{key[1]}"
            )
        accepted.append(matches[0])
    return ReceiptSelection(tuple(accepted), map_sha256, accepted_attempt_map)


def validate_receipt_against_freeze(
    receipt: Mapping[str, Any],
    *,
    context: FrozenFanInContext,
    run_input_manifest: Mapping[str, Any],
    repeat_policy: Mapping[str, Any],
    actual_receipt_key: str | None = None,
) -> Mapping[str, Any]:
    """Delegate complete receipt validation to the canonical strict verifier."""

    if _required_str(receipt, "cycle_id") != context.cycle_id:
        raise FanInError("receipt cycle_id does not match freeze")
    expected_hashes = {
        "freeze_bundle_sha256": context.freeze_bundle_sha256,
        "execution_policy_sha256": context.execution_policy_sha256,
        "execution_policy_artifact_sha256": (context.execution_policy_artifact_sha256),
        "repeat_policy_sha256": context.repeat_policy_sha256,
        "attempt_policy_sha256": context.attempt_policy_sha256,
        "receipt_policy_sha256": context.receipt_policy_sha256,
        "frozen_manifest_sha256": context.frozen_manifest_sha256,
        "run_input_manifest_sha256": context.run_input_manifest_sha256,
        "labels_sha256": context.labels_sha256,
        "model_registry_sha256": context.model_registry_sha256,
    }
    try:
        return verify_shard_receipt(
            receipt,
            manifest=run_input_manifest,
            repeat_policy=repeat_policy,
            expected_identity=expected_hashes,
            expected_shard=(
                _required_str(receipt, "model_key"),
                _required_str(receipt, "ablation"),
            ),
            actual_receipt_key=actual_receipt_key,
        )
    except ShardReceiptError as exc:
        raise FanInError(f"invalid shard receipt: {exc}") from exc


def select_and_validate_receipts(
    artifacts: Sequence[ReceiptArtifact],
    *,
    declared_shards: Sequence[ShardKey],
    context: FrozenFanInContext,
    run_input_manifest: Mapping[str, Any],
    repeat_policy: Mapping[str, Any],
    shard_schedule_sha256: str,
    accepted_attempt_map: Mapping[str, Any] | None = None,
) -> ReceiptSelection:
    """Select attempts first, then strictly verify only the accepted receipts."""

    selection = select_accepted_receipts(
        [artifact.record for artifact in artifacts],
        declared_shards=declared_shards,
        cycle_id=context.cycle_id,
        freeze_bundle_sha256=context.freeze_bundle_sha256,
        execution_policy_sha256=context.execution_policy_sha256,
        shard_schedule_sha256=shard_schedule_sha256,
        accepted_attempt_map=accepted_attempt_map,
    )
    verified: list[Mapping[str, Any]] = []
    for selected in selection.receipts:
        matches = [artifact for artifact in artifacts if artifact.record is selected]
        if len(matches) != 1:
            raise FanInError("selected receipt does not map to one discovered artifact")
        artifact = matches[0]
        verified.append(
            validate_receipt_against_freeze(
                selected,
                context=context,
                run_input_manifest=run_input_manifest,
                repeat_policy=repeat_policy,
                actual_receipt_key=artifact.actual_key,
            )
        )
    return ReceiptSelection(
        tuple(verified),
        selection.accepted_attempt_map_sha256,
        selection.accepted_attempt_map,
    )


def verify_and_materialize_union(
    receipts: Sequence[Mapping[str, Any]],
    *,
    result_store_root: str,
    output_dir: Path,
) -> str:
    """Verify the current union equals accepted versions and materialize only them."""

    commitments: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    cells: set[tuple[str, str, str]] = set()
    destinations: set[Path] = set()
    cycle_ids = {_required_str(receipt, "cycle_id") for receipt in receipts}
    if len(cycle_ids) != 1:
        raise FanInError("accepted receipts must have one cycle_id")
    cycle_id = next(iter(cycle_ids))
    for receipt in receipts:
        raw_cells = receipt.get("cells")
        if not isinstance(raw_cells, list):
            raise FanInError("receipt cells must be an array")
        for raw_cell in cast(list[object], raw_cells):
            cell = _mapping(raw_cell, "receipt cell")
            cell_key = (
                _required_str(cell, "case_id"),
                _required_str(cell, "ablation"),
                _required_str(cell, "model_key"),
            )
            if cell_key in cells:
                raise FanInError(f"duplicate accepted cell: {cell_key}")
            cells.add(cell_key)
            raw_objects = cell.get("objects")
            if not isinstance(raw_objects, list):
                raise FanInError("receipt cell objects must be an array")
            objects = [
                _mapping(value, "receipt object")
                for value in cast(list[object], raw_objects)
            ]
            names = tuple(sorted(_required_str(value, "name") for value in objects))
            if names != _RESULT_NAMES:
                raise FanInError("accepted cell must commit runs/accounting/metrics")
            for commitment in objects:
                uri = _normalize_uri(_required_str(commitment, "uri"))
                _require_union_uri(
                    uri, result_store_root=result_store_root, cycle_id=cycle_id
                )
                if uri in commitments:
                    raise FanInError(f"accepted receipts reuse union object: {uri}")
                commitments[uri] = (commitment, cell)
    current = _discover_current_union_objects(result_store_root, cycle_id)
    inventory_sha256 = _union_inventory_sha256(current)
    extra = sorted(set(current) - set(commitments))
    missing = sorted(set(commitments) - set(current))
    if extra:
        raise FanInError(f"uncommitted union objects: {extra}")
    if missing:
        raise FanInError(f"accepted receipt objects missing from union: {missing}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FanInError(f"materialization output must be empty: {output_dir}")
    for uri, (commitment, cell) in sorted(commitments.items()):
        expected_version = _required_str(commitment, "version_id")
        if current[uri] != expected_version:
            raise FanInError(f"union object version is stale or superseded: {uri}")
        payload = _read_exact_object(uri, expected_version)
        try:
            verify_committed_payload(commitment, cell=cell, payload=payload)
        except ShardReceiptError as exc:
            raise FanInError(
                f"union object commitment mismatch for {uri}: {exc}"
            ) from exc
        model_slug = _slug(_required_str(cell, "model_key"))
        target = (
            output_dir
            / _path_component(_required_str(cell, "case_id"), "case_id")
            / _path_component(_required_str(cell, "ablation"), "ablation")
            / model_slug
            / _output_filename(_required_str(commitment, "name"))
        )
        if target in destinations:
            raise FanInError(f"accepted objects collide at aggregate path: {target}")
        destinations.add(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return inventory_sha256


def derive_cadence_counts(
    frozen_manifest_path: Path,
    frozen_units_path: Path,
    run_input_manifest_path: Path,
    *,
    operator_clean_motion_count: int | None = None,
    operator_prediction_unit_count: int | None = None,
) -> CadenceCounts:
    """Derive immutable cadence counts and reject mutable-input mismatches."""

    manifest_records = _read_jsonl(frozen_manifest_path, "frozen manifest")
    included_candidates: dict[str, str] = {}
    included_cases: set[str] = set()
    expected_units_by_case: dict[str, int] = {}
    for record in manifest_records:
        eligibility = _required_str(record, "eligibility_status")
        exclusion = _required_str(record, "exclusion_status")
        if eligibility != "eligible" or exclusion != "included":
            continue
        case_id = _required_str(record, "case_id")
        if case_id in included_cases:
            raise FanInError(
                f"duplicate included case_id in frozen manifest: {case_id}"
            )
        included_cases.add(case_id)
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in included_candidates:
            raise FanInError(
                f"duplicate included candidate_id in frozen manifest: {candidate_id}"
            )
        included_candidates[candidate_id] = case_id
        case_mix_fields = _mapping(record.get("case_mix_fields"), "case_mix_fields")
        expected_units_by_case[case_id] = _nonnegative_int(
            case_mix_fields, "prediction_unit_count"
        )
    if not included_cases:
        raise FanInError("frozen manifest contains no eligible included motions")

    run_input = _read_json_object(run_input_manifest_path, "run-input manifest")
    raw_packets = run_input.get("model_packets")
    if not isinstance(raw_packets, list) or not raw_packets:
        raise FanInError("run-input manifest model_packets must be a non-empty array")
    packet_rows: set[tuple[str, str]] = set()
    run_input_cases: set[str] = set()
    for raw_packet in cast(list[object], raw_packets):
        packet = _mapping(raw_packet, "run-input model packet")
        case_id = _required_str(packet, "case_id")
        ablation = packet.get("ablation") or "full_packet"
        if not isinstance(ablation, str) or not ablation.strip():
            raise FanInError("run-input packet ablation must be a non-empty string")
        row = (case_id, ablation)
        if row in packet_rows:
            raise FanInError(f"duplicate run-input packet row: {row}")
        packet_rows.add(row)
        run_input_cases.add(case_id)
    if run_input_cases != included_cases:
        raise FanInError(
            "run-input cases do not match the frozen included manifest: "
            f"missing={sorted(included_cases - run_input_cases)}, "
            f"extra={sorted(run_input_cases - included_cases)}"
        )

    raw_units = _read_jsonl(frozen_units_path, "frozen units")
    try:
        envelopes = require_finalized_envelopes(raw_units)
    except UnitizationReviewError as exc:
        raise FanInError(f"invalid frozen finalized units: {exc}") from exc
    active_candidates: dict[str, str] = {}
    actual_units_by_case: dict[str, int] = {}
    unit_ids: set[str] = set()
    prediction_unit_count = 0
    for envelope in envelopes:
        if envelope.get("status") == "candidate_excluded":
            continue
        candidate_id = _required_str(envelope, "candidate_id")
        case_id = _required_str(envelope, "case_id")
        active_candidates[candidate_id] = case_id
        raw_prediction_units = envelope.get("prediction_units")
        if not isinstance(raw_prediction_units, list):
            raise FanInError("finalized prediction_units must be an array")
        scoreable_for_case = 0
        for raw_unit in cast(list[object], raw_prediction_units):
            unit = _mapping(raw_unit, "finalized prediction unit")
            unit_id = _required_str(unit, "unit_id")
            if unit_id in unit_ids:
                raise FanInError(f"duplicate frozen unit_id: {unit_id}")
            unit_ids.add(unit_id)
            should_score = unit.get("should_score")
            if not isinstance(should_score, bool):
                raise FanInError("frozen unit should_score must be a Boolean")
            scoreable_for_case += int(should_score)
        actual_units_by_case[case_id] = scoreable_for_case
        prediction_unit_count += scoreable_for_case
    if active_candidates != included_candidates:
        raise FanInError(
            "finalized-unit candidate/case coverage does not match frozen manifest"
        )
    if actual_units_by_case != expected_units_by_case:
        mismatches = {
            case_id: {
                "manifest": expected_units_by_case.get(case_id),
                "finalized_units": actual_units_by_case.get(case_id),
            }
            for case_id in sorted(
                set(expected_units_by_case) | set(actual_units_by_case)
            )
            if expected_units_by_case.get(case_id) != actual_units_by_case.get(case_id)
        }
        raise FanInError(
            "frozen manifest prediction-unit counts do not match finalized units: "
            f"{mismatches}"
        )
    if prediction_unit_count == 0:
        raise FanInError("frozen units contain no scorable prediction units")
    counts = CadenceCounts(len(included_cases), prediction_unit_count)
    if (
        operator_clean_motion_count is not None
        and operator_clean_motion_count != counts.clean_motion_count
    ):
        raise FanInError(
            "clean_motion_count mismatch: operator supplied "
            f"{operator_clean_motion_count}, frozen manifest derives "
            f"{counts.clean_motion_count}"
        )
    if (
        operator_prediction_unit_count is not None
        and operator_prediction_unit_count != counts.prediction_unit_count
    ):
        raise FanInError(
            "prediction_unit_count mismatch: operator supplied "
            f"{operator_prediction_unit_count}, frozen units derive "
            f"{counts.prediction_unit_count}"
        )
    return counts


def require_publishable_cycle(*, cycle_id: str, cycle_series: str) -> None:
    """Refuse canonical publication unless the frozen policy is official."""

    smoke_identity = re.search(
        r"(?:^|[-_.])smoke(?:$|[-_.])", cycle_id, flags=re.IGNORECASE
    )
    if cycle_series != "official" or smoke_identity is not None:
        raise FanInError(
            "full fan-in publication requires a non-smoke official cycle identity"
        )


def current_receipt_inventory_sha256(root: str, cycle_id: str) -> str:
    """Hash the complete current receipt inventory for a publication race check."""

    return _receipt_inventory_sha256(_discover_receipts(root, cycle_id))


def current_union_inventory_sha256(root: str, cycle_id: str) -> str:
    """Hash every current union URI and VersionId for a publication race check."""

    return _union_inventory_sha256(_discover_current_union_objects(root, cycle_id))


def verify_fan_in(config: FanInConfig) -> FanInReport:
    """Run receipt selection, exact object checks, completeness, and aggregation."""

    frozen = _load_frozen_inputs(config)
    if _CYCLE_ID.fullmatch(frozen.context.cycle_id) is None:
        raise FanInError("cycle_id must use only safe identifier characters")
    cycle_series = _required_str(frozen.execution_policy, "cycle_series")
    if not config.verify_only:
        require_publishable_cycle(
            cycle_id=frozen.context.cycle_id, cycle_series=cycle_series
        )
    run_input_manifest = _read_json_object(
        config.run_input_manifest_path, "frozen run-input manifest"
    )
    if _required_str(run_input_manifest, "cycle_id") != frozen.context.cycle_id:
        raise FanInError("run-input manifest cycle_id does not match freeze")
    receipt_artifacts = _discover_receipts(config.receipt_root, frozen.context.cycle_id)
    accepted_map = (
        None
        if config.accepted_attempt_map_path is None
        else _read_json_object(config.accepted_attempt_map_path, "accepted-attempt map")
    )
    schedule = _declared_shards(frozen.execution_policy)
    schedule_sha256 = _shard_schedule_sha256(schedule)
    repeat_policy = _mapping(
        frozen.execution_policy.get("repeat_policy"), "repeat_policy"
    )
    selection = select_and_validate_receipts(
        receipt_artifacts,
        declared_shards=schedule,
        context=frozen.context,
        run_input_manifest=run_input_manifest,
        repeat_policy=repeat_policy,
        shard_schedule_sha256=schedule_sha256,
        accepted_attempt_map=accepted_map,
    )
    if (
        config.source_dispatch_run_id is not None
        and re.fullmatch(r"[1-9][0-9]*", config.source_dispatch_run_id) is None
    ):
        raise FanInError("source dispatch run ID must be a positive integer")
    if config.source_dispatch_run_id is not None and not any(
        _required_str(receipt, "workflow_run_id") == config.source_dispatch_run_id
        for receipt in selection.receipts
    ):
        raise FanInError(
            "source dispatch run must match at least one accepted shard receipt"
        )
    counts = derive_cadence_counts(
        frozen.manifest_path,
        frozen.units_path,
        config.run_input_manifest_path,
        operator_clean_motion_count=config.operator_clean_motion_count,
        operator_prediction_unit_count=config.operator_prediction_unit_count,
    )
    accepted_receipt_records = tuple(
        {
            "model_key": _required_str(receipt, "model_key"),
            "ablation": _required_str(receipt, "ablation"),
            "workflow_run_id": _required_str(receipt, "workflow_run_id"),
            "workflow_run_attempt": _positive_int(receipt, "workflow_run_attempt"),
            "receipt_key": _required_str(receipt, "receipt_key"),
            "receipt_sha256": _required_sha256(receipt, "receipt_sha256"),
        }
        for receipt in selection.receipts
    )
    receipt_inventory_sha256 = _receipt_inventory_sha256(receipt_artifacts)
    union_commitment_sha256 = _union_commitment_sha256(selection.receipts)
    frozen_artifact_sha256 = {
        "manifest": frozen.context.frozen_manifest_sha256,
        "run_input_manifest": frozen.context.run_input_manifest_sha256,
        "units": sha256_file(frozen.units_path),
        "labels": frozen.context.labels_sha256,
        "model_registry": frozen.context.model_registry_sha256,
        "baselines": sha256_file(frozen.baselines_path),
        "execution_policy": frozen.context.execution_policy_artifact_sha256,
    }
    public_evidence = {
        "schema_version": FAN_IN_REPORT_SCHEMA_VERSION,
        "cycle_id": frozen.context.cycle_id,
        "mode": "verify_only" if config.verify_only else "publish",
        "freeze_bundle_sha256": frozen.context.freeze_bundle_sha256,
        "accepted_attempt_map": (
            None
            if selection.accepted_attempt_map is None
            else dict(selection.accepted_attempt_map)
        ),
        "accepted_receipts": list(accepted_receipt_records),
        "receipt_inventory_sha256": receipt_inventory_sha256,
        "union_commitment_sha256": union_commitment_sha256,
        "frozen_artifact_sha256": frozen_artifact_sha256,
        "cadence_counts": {
            "clean_motion_count": counts.clean_motion_count,
            "prediction_unit_count": counts.prediction_unit_count,
        },
    }
    if config.verify_only:
        with tempfile.TemporaryDirectory(prefix="lfb-fan-in-verify-") as temporary:
            temporary_root = Path(temporary)
            aggregate, union_inventory_sha256 = _validate_aggregate(
                config,
                frozen=frozen,
                receipts=selection.receipts,
                counts=counts,
                materialized_dir=temporary_root / "per-case",
                aggregate_dir=temporary_root / "aggregate",
                cycle_series=cycle_series,
                public_fan_in_record=public_evidence,
            )
        aggregate_dir = Path("ephemeral-verify-only-aggregate")
    else:
        aggregate_dir = config.output_dir / "aggregate"
        aggregate, union_inventory_sha256 = _validate_aggregate(
            config,
            frozen=frozen,
            receipts=selection.receipts,
            counts=counts,
            materialized_dir=config.output_dir / "per-case",
            aggregate_dir=aggregate_dir,
            cycle_series=cycle_series,
            public_fan_in_record=public_evidence,
        )
    report = FanInReport(
        cycle_id=frozen.context.cycle_id,
        mode="verify_only" if config.verify_only else "publish",
        freeze_bundle_sha256=frozen.context.freeze_bundle_sha256,
        accepted_attempt_map_sha256=selection.accepted_attempt_map_sha256,
        accepted_attempt_map=selection.accepted_attempt_map,
        accepted_attempt_map_path=(
            str(config.accepted_attempt_map_path)
            if config.accepted_attempt_map_path is not None
            else None
        ),
        accepted_receipts=accepted_receipt_records,
        receipt_inventory_sha256=receipt_inventory_sha256,
        union_inventory_sha256=union_inventory_sha256,
        union_commitment_sha256=union_commitment_sha256,
        frozen_artifact_sha256=frozen_artifact_sha256,
        clean_motion_count=counts.clean_motion_count,
        prediction_unit_count=counts.prediction_unit_count,
        aggregate_output_dir=aggregate_dir,
        aggregate_result=_aggregate_result_record(aggregate),
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(config.output_dir / "fan-in-report.json", report.to_record())
    return report


def verify_only_main(argv: Sequence[str] | None = None) -> int:
    """Execute verification through an entry point with no publication call."""

    args = build_parser().parse_args(argv)
    if not cast(bool, args.verify_only):
        raise FanInError("verify_only_main requires --verify-only")
    config = config_from_args(args, verify_only=True)
    report = verify_fan_in(config)
    print(json.dumps(report.to_record(), sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the structurally nonpublishing fan-in verification CLI."""

    return verify_only_main(argv)


def _load_frozen_inputs(config: FanInConfig) -> _FrozenInputs:
    overrides: dict[FrozenArtifactName, Path] = {}
    if config.labels_path is not None:
        overrides[FrozenArtifactName.LABELS] = config.labels_path
    if config.model_registry_path is not None:
        overrides[FrozenArtifactName.MODEL_REGISTRY] = config.model_registry_path
    if config.baseline_training_examples_path is not None:
        overrides[FrozenArtifactName.BASELINES] = config.baseline_training_examples_path
    try:
        bundle = verify_freeze_bundle(
            config.freeze_bundle_path,
            root_path=Path.cwd(),
            artifact_path_overrides=overrides,
            amendment_bundle_paths=config.amendment_bundle_paths,
        )
    except ValueError as exc:
        raise FanInError(f"freeze verification failed: {exc}") from exc
    execution_artifact_record = load_json_object(
        bundle.artifact(FrozenArtifactName.EXECUTION_POLICY).path,
        "execution policy",
    )
    execution = execution_policy_content(execution_artifact_record)
    repeat = _mapping(execution.get("repeat_policy"), "repeat_policy")
    attempts = _mapping(execution.get("attempt_policy"), "attempt_policy")
    receipts = _mapping(execution.get("receipt_policy"), "receipt_policy")
    context = FrozenFanInContext(
        cycle_id=bundle.cycle_id,
        freeze_bundle_sha256=bundle.bundle_sha256,
        execution_policy_sha256=policy_content_sha256(execution),
        execution_policy_artifact_sha256=bundle.artifact(
            FrozenArtifactName.EXECUTION_POLICY
        ).sha256,
        repeat_policy_sha256=policy_content_sha256(repeat),
        attempt_policy_sha256=policy_content_sha256(attempts),
        receipt_policy_sha256=policy_content_sha256(receipts),
        frozen_manifest_sha256=bundle.artifact(FrozenArtifactName.MANIFEST).sha256,
        run_input_manifest_sha256=sha256_file(config.run_input_manifest_path),
        labels_sha256=bundle.artifact(FrozenArtifactName.LABELS).sha256,
        model_registry_sha256=bundle.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256,
    )
    return _FrozenInputs(
        context=context,
        execution_policy=execution,
        manifest_path=bundle.artifact(FrozenArtifactName.MANIFEST).path,
        units_path=bundle.artifact(FrozenArtifactName.UNITS).path,
        labels_path=bundle.artifact(FrozenArtifactName.LABELS).path,
        model_registry_path=bundle.artifact(FrozenArtifactName.MODEL_REGISTRY).path,
        baselines_path=bundle.artifact(FrozenArtifactName.BASELINES).path,
    )


def _validate_aggregate(
    config: FanInConfig,
    *,
    frozen: _FrozenInputs,
    receipts: Sequence[Mapping[str, Any]],
    counts: CadenceCounts,
    materialized_dir: Path,
    aggregate_dir: Path,
    cycle_series: str,
    public_fan_in_record: Mapping[str, Any],
) -> tuple[OfficialAggregationResult, str]:
    union_inventory_sha256 = verify_and_materialize_union(
        receipts,
        result_store_root=config.receipt_root,
        output_dir=materialized_dir,
    )
    _write_json(
        aggregate_dir / "public" / "run-cards" / "fan-in-report.json",
        {**public_fan_in_record, "union_inventory_sha256": union_inventory_sha256},
    )
    allow_no_baselines = _required_bool(frozen.execution_policy, "allow_no_baselines")
    baseline_training_examples_path = (
        None
        if config.baseline_training_examples_path is None and allow_no_baselines
        else frozen.baselines_path
    )
    result = aggregate_official_results(
        OfficialAggregationConfig(
            per_case_dir=materialized_dir,
            run_input_manifest_path=config.run_input_manifest_path,
            labels_path=frozen.labels_path,
            output_dir=aggregate_dir,
            cycle_id=frozen.context.cycle_id,
            cycle_series=CycleSeries(cycle_series),
            clean_motion_count=counts.clean_motion_count,
            prediction_unit_count=counts.prediction_unit_count,
            model_registry_path=frozen.model_registry_path,
            baseline_training_examples_path=baseline_training_examples_path,
            allow_no_baselines=allow_no_baselines,
            deferred_ablations=config.deferred_ablations,
            elapsed_days=config.elapsed_days,
            official_window_days=config.official_window_days,
        )
    )
    return result, union_inventory_sha256


def _aggregate_result_record(result: OfficialAggregationResult) -> JsonRecord:
    return {
        "expected_matrix_row_count": result.expected_matrix_row_count,
        "aggregated_matrix_row_count": result.aggregated_matrix_row_count,
        "expected_case_count": result.expected_case_count,
        "aggregated_case_count": result.aggregated_case_count,
        "model_count": result.model_count,
    }


def _validate_accepted_attempt_map(
    record: Mapping[str, Any],
    *,
    ambiguous_shards: set[ShardKey],
    cycle_id: str,
    freeze_bundle_sha256: str,
    execution_policy_sha256: str,
    shard_schedule_sha256: str,
) -> tuple[dict[ShardKey, Mapping[str, Any]], str]:
    _exact_keys(
        record,
        {
            "schema_version",
            "cycle_id",
            "parent_freeze_bundle_sha256",
            "execution_policy_sha256",
            "shard_schedule_sha256",
            "selections",
            "accepted_attempt_map_sha256",
        },
        "accepted-attempt map",
    )
    if record.get("schema_version") != ACCEPTED_ATTEMPT_MAP_SCHEMA_VERSION:
        raise FanInError("unsupported accepted-attempt map schema")
    if _required_str(record, "cycle_id") != cycle_id:
        raise FanInError("accepted-attempt map cycle_id does not match fan-in")
    if _required_sha256(record, "parent_freeze_bundle_sha256") != freeze_bundle_sha256:
        raise FanInError(
            "accepted-attempt map parent_freeze_bundle_sha256 does not match fan-in"
        )
    if _required_sha256(record, "execution_policy_sha256") != execution_policy_sha256:
        raise FanInError("accepted-attempt map execution_policy_sha256 mismatch")
    if _required_sha256(record, "shard_schedule_sha256") != shard_schedule_sha256:
        raise FanInError("accepted-attempt map shard_schedule_sha256 mismatch")
    without_hash = dict(record)
    supplied_hash = _required_sha256(without_hash, "accepted_attempt_map_sha256")
    without_hash.pop("accepted_attempt_map_sha256")
    if hash_payload(without_hash) != supplied_hash:
        raise FanInError("accepted-attempt map hash does not match its content")
    raw_selections = record.get("selections")
    if not isinstance(raw_selections, list):
        raise FanInError("accepted-attempt map selections must be an array")
    selections: dict[ShardKey, Mapping[str, Any]] = {}
    selection_order: list[ShardKey] = []
    for raw in cast(list[object], raw_selections):
        selection = _mapping(raw, "accepted-attempt selection")
        _exact_keys(
            selection,
            {
                "model_key",
                "ablation",
                "workflow_run_id",
                "workflow_run_attempt",
                "receipt_key",
                "receipt_sha256",
            },
            "accepted-attempt selection",
        )
        key = (
            _required_str(selection, "model_key"),
            _required_str(selection, "ablation"),
        )
        _required_str(selection, "workflow_run_id")
        _positive_int(selection, "workflow_run_attempt")
        _required_str(selection, "receipt_key")
        _required_sha256(selection, "receipt_sha256")
        if key in selections:
            raise FanInError(f"duplicate accepted-attempt selection: {key}")
        selections[key] = selection
        selection_order.append(key)
    if selection_order != sorted(selection_order):
        raise FanInError("accepted-attempt selections must be sorted by shard")
    if set(selections) != ambiguous_shards:
        extra = sorted(set(selections) - ambiguous_shards)
        missing = sorted(ambiguous_shards - set(selections))
        if extra:
            raise FanInError(
                f"accepted-attempt map may select only ambiguous shards: {extra}"
            )
        raise FanInError(f"accepted-attempt map is missing ambiguous shards: {missing}")
    return selections, supplied_hash


def _receipt_matches_selection(
    receipt: Mapping[str, Any], selection: Mapping[str, Any]
) -> bool:
    return all(
        receipt.get(field) == selection.get(field)
        for field in (
            "model_key",
            "ablation",
            "workflow_run_id",
            "workflow_run_attempt",
            "receipt_key",
            "receipt_sha256",
        )
    )


def _declared_shards(policy: Mapping[str, Any]) -> tuple[ShardKey, ...]:
    schedule = _mapping(policy.get("shard_schedule"), "shard_schedule")
    raw_shards = schedule.get("shards")
    if not isinstance(raw_shards, list):
        raise FanInError("execution policy shard schedule must be an array")
    return tuple(
        (
            _required_str(_mapping(raw, "declared shard"), "model_key"),
            _required_str(_mapping(raw, "declared shard"), "ablation"),
        )
        for raw in cast(list[object], raw_shards)
    )


def _shard_schedule_sha256(shards: Sequence[ShardKey]) -> str:
    return hash_payload(
        {
            "shards": [
                {"model_key": model_key, "ablation": ablation}
                for model_key, ablation in sorted(shards)
            ]
        }
    )


def _receipt_inventory_sha256(artifacts: Sequence[ReceiptArtifact]) -> str:
    return hash_payload(
        {
            "receipts": [
                {
                    "actual_key": artifact.actual_key,
                    "raw_sha256": artifact.raw_sha256,
                }
                for artifact in sorted(artifacts, key=lambda value: value.actual_key)
            ]
        }
    )


def _union_inventory_sha256(inventory: Mapping[str, str]) -> str:
    return hash_payload(
        {
            "objects": [
                {"uri": uri, "version_id": version_id}
                for uri, version_id in sorted(inventory.items())
            ]
        }
    )


def _union_commitment_sha256(
    receipts: Sequence[Mapping[str, Any]],
) -> str:
    objects: list[Mapping[str, Any]] = []
    for receipt in receipts:
        raw_cells = receipt.get("cells")
        if not isinstance(raw_cells, list):
            raise FanInError("receipt cells must be an array")
        for raw_cell in cast(list[object], raw_cells):
            cell = _mapping(raw_cell, "receipt cell")
            raw_objects = cell.get("objects")
            if not isinstance(raw_objects, list):
                raise FanInError("receipt cell objects must be an array")
            objects.extend(
                _mapping(raw_object, "receipt object")
                for raw_object in cast(list[object], raw_objects)
            )
    return hash_payload(
        {
            "objects": sorted(
                objects,
                key=lambda value: (
                    _required_str(value, "uri"),
                    _required_str(value, "version_id"),
                ),
            )
        }
    )


def _discover_receipts(root: str, cycle_id: str) -> tuple[ReceiptArtifact, ...]:
    prefix = f"shard-receipts/{cycle_id}/"
    artifacts: list[ReceiptArtifact] = []
    if root.startswith("s3://"):
        keys = _list_s3_keys(root, prefix)
        for key in keys:
            payload = _read_s3_bytes(root, key, "shard receipt")
            artifacts.append(
                ReceiptArtifact(
                    actual_key=key,
                    raw_sha256=hashlib.sha256(payload).hexdigest(),
                    record=_decode_json_object(payload, "shard receipt"),
                )
            )
    else:
        directory = Path(root) / prefix
        for path in sorted(directory.rglob("*.json")):
            payload = path.read_bytes()
            artifacts.append(
                ReceiptArtifact(
                    actual_key=path.relative_to(Path(root)).as_posix(),
                    raw_sha256=hashlib.sha256(payload).hexdigest(),
                    record=_decode_json_object(payload, "shard receipt"),
                )
            )
    if not artifacts:
        raise FanInError(f"no shard receipts found for cycle {cycle_id}")
    keys = [artifact.actual_key for artifact in artifacts]
    if len(keys) != len(set(keys)):
        raise FanInError("receipt inventory contains duplicate object keys")
    return tuple(artifacts)


def _discover_current_union_objects(root: str, cycle_id: str) -> dict[str, str]:
    prefix = f"per-case/{cycle_id}/"
    if root.startswith("s3://"):
        return {
            _normalize_uri(_join_root(root, key)): _head_s3_version(
                _join_root(root, key)
            )
            for key in _list_s3_keys(root, prefix)
        }
    directory = Path(root) / prefix
    if not directory.is_dir():
        return {}
    return {
        _normalize_uri(str(path)): sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _list_s3_keys(root: str, prefix: str) -> tuple[str, ...]:
    parsed = urlparse(root.rstrip("/"))
    if parsed.scheme != "s3" or not parsed.netloc:
        raise FanInError(f"invalid S3 root: {root}")
    root_prefix = unquote(parsed.path.lstrip("/"))
    full_prefix = "/".join(value for value in (root_prefix, prefix) if value)
    keys: list[str] = []
    token: str | None = None
    while True:
        command = [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            parsed.netloc,
            "--prefix",
            full_prefix,
            "--output",
            "json",
        ]
        if token is not None:
            command.extend(("--continuation-token", token))
        payload = _run_aws_json(command, "S3 object discovery")
        contents = payload.get("Contents", [])
        if not isinstance(contents, list):
            raise FanInError("S3 list response Contents must be an array")
        for raw in cast(list[object], contents):
            item = _mapping(raw, "S3 object")
            key = _required_str(item, "Key")
            if root_prefix:
                expected = root_prefix.rstrip("/") + "/"
                if not key.startswith(expected):
                    raise FanInError("S3 listing escaped configured root")
                key = key[len(expected) :]
            keys.append(key)
        truncated = payload.get("IsTruncated", False)
        if truncated is False:
            break
        if truncated is not True:
            raise FanInError("S3 list response IsTruncated must be Boolean")
        token = _required_str(payload, "NextContinuationToken")
    return tuple(sorted(keys))


def _head_s3_version(uri: str) -> str:
    parsed = urlparse(uri)
    payload = _run_aws_json(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            parsed.netloc,
            "--key",
            unquote(parsed.path.lstrip("/")),
            "--output",
            "json",
        ],
        "S3 object version verification",
    )
    version = _required_str(payload, "VersionId")
    if version == "null":
        raise FanInError(f"S3 object has no durable VersionId: {uri}")
    return version


def _read_exact_object(uri: str, version_id: str) -> bytes:
    if not uri.startswith("s3://"):
        path = Path(uri)
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != version_id:
            raise FanInError(f"local object version commitment mismatch: {uri}")
        return payload
    parsed = urlparse(uri)
    with tempfile.NamedTemporaryFile() as handle:
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                parsed.netloc,
                "--key",
                unquote(parsed.path.lstrip("/")),
                "--version-id",
                version_id,
                handle.name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FanInError(f"exact S3 object read failed: {result.stderr.strip()}")
        return Path(handle.name).read_bytes()


def _read_s3_bytes(root: str, key: str, description: str) -> bytes:
    uri = _join_root(root, key)
    parsed = urlparse(uri)
    with tempfile.NamedTemporaryFile() as handle:
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                parsed.netloc,
                "--key",
                unquote(parsed.path.lstrip("/")),
                handle.name,
            ],
            check=False,
            capture_output=True,
        )
        payload = Path(handle.name).read_bytes()
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise FanInError(f"{description} read failed: {message}")
    return payload


def _decode_json_object(payload: bytes, description: str) -> Mapping[str, Any]:
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FanInError(f"{description} is invalid JSON") from exc
    return _mapping(value, description)


def _run_aws_json(command: list[str], description: str) -> Mapping[str, Any]:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise FanInError(f"{description} failed: {result.stderr.strip()}")
    try:
        value: object = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FanInError(f"{description} returned invalid JSON") from exc
    return _mapping(value, description)


def _require_union_uri(uri: str, *, result_store_root: str, cycle_id: str) -> None:
    expected_prefix = (
        _normalize_uri(_join_root(result_store_root, f"per-case/{cycle_id}/")).rstrip(
            "/"
        )
        + "/"
    )
    if not uri.startswith(expected_prefix):
        raise FanInError(
            f"receipt object is outside the frozen cycle union prefix: {uri}"
        )


def _normalize_uri(uri: str) -> str:
    if uri.startswith("s3://"):
        parsed = urlparse(uri)
        return f"s3://{parsed.netloc}/{unquote(parsed.path.lstrip('/'))}"
    return str(Path(uri).resolve())


def _join_root(root: str, key: str) -> str:
    if root.startswith("s3://"):
        return root.rstrip("/") + "/" + key.lstrip("/")
    return str(Path(root) / key)


def _output_filename(name: str) -> str:
    if name == "metrics":
        return "metrics.json"
    if name in {"runs", "accounting"}:
        return f"{name}.jsonl"
    raise FanInError(f"unsupported result object name: {name}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return _path_component(slug, "model_key")


def _path_component(value: str, field: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise FanInError(f"unsafe {field} path component")
    return value


def _read_json_object(path: Path, description: str) -> Mapping[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FanInError(f"{description} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FanInError(f"{description} is invalid JSON: {path}") from exc
    return _mapping(value, description)


def _read_jsonl(path: Path, description: str) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise FanInError(f"{description} is missing: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FanInError(
                f"{description} line {line_number} is invalid JSON"
            ) from exc
        records.append(_mapping(value, f"{description} line {line_number}"))
    if not records:
        raise FanInError(f"{description} must not be empty")
    return tuple(records)


def _write_json(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify immutable shard receipts and aggregate accepted objects."
    )
    parser.add_argument("--freeze-bundle", type=Path, required=True)
    parser.add_argument(
        "--amendment-bundle",
        type=Path,
        action="append",
        default=[],
        help="Committed ancestor freeze bundle; repeat for the full amendment chain.",
    )
    parser.add_argument("--run-input-manifest", type=Path, required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--model-registry", type=Path)
    parser.add_argument("--accepted-attempt-map", type=Path)
    parser.add_argument("--source-dispatch-run-id")
    parser.add_argument("--clean-motion-count", type=int)
    parser.add_argument("--prediction-unit-count", type=int)
    parser.add_argument("--baseline-training-examples", type=Path)
    parser.add_argument("--elapsed-days", type=int)
    parser.add_argument("--official-window-days", type=int)
    parser.add_argument("--deferred-ablation", action="append", default=[])
    parser.add_argument("--verify-only", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace, *, verify_only: bool) -> FanInConfig:
    deferred = tuple(cast(Sequence[str], args.deferred_ablation))
    return FanInConfig(
        freeze_bundle_path=cast(Path, args.freeze_bundle),
        amendment_bundle_paths=tuple(cast(Sequence[Path], args.amendment_bundle)),
        run_input_manifest_path=cast(Path, args.run_input_manifest),
        receipt_root=cast(str, args.receipt_root),
        output_dir=cast(Path, args.output_dir),
        labels_path=cast(Path | None, args.labels),
        model_registry_path=cast(Path | None, args.model_registry),
        accepted_attempt_map_path=cast(Path | None, args.accepted_attempt_map),
        source_dispatch_run_id=cast(str | None, args.source_dispatch_run_id),
        operator_clean_motion_count=cast(int | None, args.clean_motion_count),
        operator_prediction_unit_count=cast(int | None, args.prediction_unit_count),
        baseline_training_examples_path=cast(
            Path | None, args.baseline_training_examples
        ),
        elapsed_days=cast(int | None, args.elapsed_days),
        official_window_days=cast(int | None, args.official_window_days),
        deferred_ablations=deferred or ("judge_removed",),
        verify_only=verify_only,
    )


def _mapping(value: object, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FanInError(f"{description} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FanInError(f"{field} must be a non-empty string")
    return value


def _required_sha256(record: Mapping[str, Any], field: str) -> str:
    value = _required_str(record, field)
    if _SHA256.fullmatch(value) is None:
        raise FanInError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _required_bool(record: Mapping[str, Any], field: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise FanInError(f"{field} must be a Boolean")
    return value


def _nonnegative_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FanInError(f"{field} must be a non-negative integer")
    return value


def _positive_int(record: Mapping[str, Any], field: str) -> int:
    value = _nonnegative_int(record, field)
    if value < 1:
        raise FanInError(f"{field} must be a positive integer")
    return value


def _exact_keys(
    record: Mapping[str, Any], expected: set[str], description: str
) -> None:
    actual = set(record)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    raise FanInError(
        f"{description} fields do not match schema; missing={missing}, extra={extra}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

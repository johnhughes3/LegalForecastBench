"""Authenticated, labels-deferred manifest forecast bundles.

This module is deliberately additive.  It does not alter the ordinary freeze,
shard-receipt, fan-in, or scoring contracts.  A bundle is an immutable bridge
around the timing gap between a blinded forecast and authenticated Stage B
labels.  Provider evidence can be recorded against a bundle, but those
receipts are explicitly non-scoreable until :func:`attach_labels` derives a
new record from an authenticated label lineage.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import (
    MANIFEST_FORECAST_BOUND_RECEIPT_V1,
    MANIFEST_FORECAST_BUNDLE_V1,
    MANIFEST_FORECAST_DEFERRED_RECEIPT_V1,
    MANIFEST_FORECAST_LABEL_ATTACHMENT_V1,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.labeling.provider_journal import load_provider_cycle_caps_bytes
from legalforecast.protocol.policy_artifacts import (
    OFFICIAL_SHARD_ABLATIONS,
    verify_execution_policy,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_BUNDLE_NAME: Final = "bundle.json"
_RUN_CARD_NAME: Final = "run-cards/manifest-forecast-bundle.json"
_ATTACHMENT_NAME: Final = "label-attachment.json"
_BOUND_RECEIPTS_NAME: Final = "bound-receipts.jsonl"
_DEFERRED_RECEIPTS_NAME: Final = "deferred-receipts.jsonl"
_OFFICIAL_CASE_COUNT: Final = 100
_OFFICIAL_MODEL_COUNT: Final = 4
_OWNER_APPROVAL_TEMPLATE: Final = (
    "I approve corpus manifest {digest} as the frozen Cycle 1 forecast corpus."
)


class ManifestForecastBundleError(ValueError):
    """Raised when an authenticated bundle or label attachment is invalid."""


class DeferredReceiptError(ManifestForecastBundleError):
    """Raised when a deferred receipt is not bound to the bundle."""


@dataclass(frozen=True, slots=True)
class ManifestForecastBundleBuild:
    """Bytes and the canonical bundle record produced before publication."""

    bundle: Mapping[str, Any]
    payloads: Mapping[str, bytes]
    input_snapshots: Mapping[Path, bytes]


@dataclass(frozen=True, slots=True)
class LabelAttachmentBuild:
    """Create-only label attachment and newly derived receipt records."""

    attachment: Mapping[str, Any]
    bound_receipts: tuple[Mapping[str, Any], ...]


def issue_bundle(
    *,
    cycle_id: str,
    freeze_inputs_root: Path,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    execution_policy: Path,
    repeat_policy: Mapping[str, Any],
    shard_schedule: Sequence[Mapping[str, Any]],
    journal_namespace: str,
    output_root: Path,
    generated_at: datetime | None = None,
) -> ManifestForecastBundleBuild:
    """Issue one create-only bundle from authenticated provider-free inputs."""

    if output_root.exists():
        raise ManifestForecastBundleError(
            f"bundle output already exists; refusing overwrite: {output_root}"
        )
    if not cycle_id.strip() or not journal_namespace.strip():
        raise ManifestForecastBundleError("cycle_id and journal_namespace are required")
    snapshots: dict[Path, bytes] = {}
    freeze = _read_freeze_inputs(
        freeze_inputs_root, snapshots, expected_cycle_id=cycle_id
    )
    owner_bytes = _snapshot(owner_manifest, snapshots, "owner manifest")
    forecast_record_path = forecast_output_dir / "manifest-mode-run-record.json"
    run_inputs_path = forecast_output_dir / "run-inputs.json"
    forecast_record_bytes = _snapshot(
        forecast_record_path, snapshots, "manifest forecast run record"
    )
    run_inputs_bytes = _snapshot(run_inputs_path, snapshots, "manifest run inputs")
    registry_bytes = _snapshot(model_registry, snapshots, "successor model registry")
    caps_bytes = _snapshot(provider_cycle_caps, snapshots, "provider cycle caps")
    policy_bytes = _snapshot(execution_policy, snapshots, "execution policy")
    owner = _json_object(owner_bytes, "owner manifest")
    manifest_sha = _required_sha(owner, "manifest_sha256")
    manifest = _load_manifest(owner_bytes, manifest_sha)
    run_record = _json_object(forecast_record_bytes, "manifest forecast run record")
    run_inputs = _json_object(run_inputs_bytes, "manifest run inputs")
    _require_cycle(owner, cycle_id, "owner manifest")
    _require_cycle(run_record, cycle_id, "manifest forecast run record")
    _require_cycle(run_inputs, cycle_id, "manifest run inputs")
    if run_record.get("manifest_sha256") != manifest_sha:
        raise ManifestForecastBundleError("run record manifest digest differs")
    _require_official_forecast_record(
        run_record,
        run_inputs,
        manifest=manifest,
        manifest_sha=manifest_sha,
    )
    packets = _records(run_inputs.get("model_packets"), "model_packets")
    packet_commitments, prompt_commitments = _forecast_commitments(
        run_inputs, forecast_output_dir, snapshots
    )
    registry_entries, policy = _authenticate_runtime_inputs(
        registry_bytes,
        caps_bytes,
        policy_bytes,
        cycle_id=cycle_id,
    )
    _require_policy_bindings(
        policy,
        repeat_policy=repeat_policy,
        shard_schedule=shard_schedule,
    )
    units_source = run_record.get("prediction_units_source")
    _require_prediction_units_source(
        units_source,
        manifest.prediction_units_source.to_record(),
    )
    unit_identities = _prediction_unit_identities(units_source, snapshots)
    generated = generated_at or datetime.now(UTC)
    if generated.tzinfo is None:
        raise ManifestForecastBundleError("generated_at must be timezone-aware")
    core: dict[str, Any] = {
        "schema_version": str(MANIFEST_FORECAST_BUNDLE_V1),
        "cycle_id": cycle_id,
        "generated_at": generated.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "labels_state": "deferred",
        "labels_sha256": None,
        "scoreable": False,
        "publishable": False,
        "provider_calls_made": 0,
        "owner_manifest": {
            "path": str(owner_manifest),
            "sha256": _sha(owner_bytes),
            "manifest_sha256": manifest_sha,
        },
        "forecast_inputs": {
            "run_record_path": str(forecast_record_path),
            "run_record_sha256": _sha(forecast_record_bytes),
            "run_inputs_path": str(run_inputs_path),
            "run_inputs_sha256": _sha(run_inputs_bytes),
            "packet_count": len(packets),
            "packet_sha256": dict(sorted(packet_commitments.items())),
            "prompt_sha256": dict(sorted(prompt_commitments.items())),
        },
        "generic_freeze_inputs": freeze,
        "model_registry": {
            "path": str(model_registry),
            "sha256": _sha(registry_bytes),
            "entries": registry_entries,
        },
        "provider_cycle_caps": {
            "path": str(provider_cycle_caps),
            "sha256": _sha(caps_bytes),
        },
        "execution_policy": {
            "path": str(execution_policy),
            "sha256": _sha(policy_bytes),
        },
        "execution_constraints": {
            "docket_tool": False,
            "search": False,
            "tools": [],
            "outcome_labels_visible": False,
        },
        "repeat_policy": _canonical_value(repeat_policy, "repeat_policy"),
        "shard_schedule": [
            _canonical_value(row, "shard_schedule row") for row in shard_schedule
        ],
        "journal_namespace": journal_namespace,
        "prediction_unit_identities": sorted(unit_identities),
    }
    core["bundle_sha256"] = _sha(_canonical(core))
    payloads = {
        _BUNDLE_NAME: _canonical(core),
        _RUN_CARD_NAME: _canonical(
            {
                "schema_version": str(MANIFEST_FORECAST_BUNDLE_V1),
                "stage": "issue-manifest-forecast-bundle",
                "status": "completed",
                "cycle_id": cycle_id,
                "provider_calls_made": 0,
                "paid_activity_executed": False,
                "bundle_sha256": core["bundle_sha256"],
                "input_commitments": {
                    str(path): _sha(payload)
                    for path, payload in sorted(
                        snapshots.items(), key=lambda item: str(item[0])
                    )
                },
            }
        ),
    }
    _require_snapshots_unchanged(snapshots)
    _publish_create_only(output_root, payloads)
    _require_snapshots_unchanged(snapshots)
    return ManifestForecastBundleBuild(core, payloads, snapshots)


def verify_bundle(output_root: Path) -> Mapping[str, Any]:
    """Verify a previously issued bundle and every bound input byte."""

    bundle_path = output_root / _BUNDLE_NAME
    card_path = output_root / _RUN_CARD_NAME
    bundle_bytes = _read_regular(bundle_path, "manifest forecast bundle")
    bundle = _json_object(bundle_bytes, "manifest forecast bundle")
    if bundle.get("schema_version") != str(MANIFEST_FORECAST_BUNDLE_V1):
        raise ManifestForecastBundleError("unsupported manifest forecast bundle schema")
    claimed = _required_sha(bundle, "bundle_sha256")
    without = dict(bundle)
    del without["bundle_sha256"]
    if _sha(_canonical(without)) != claimed:
        raise ManifestForecastBundleError("bundle digest does not match content")
    card_bytes = _read_regular(card_path, "bundle run card")
    card = _json_object(card_bytes, "bundle run card")
    if card.get("status") != "completed" or card.get("provider_calls_made") != 0:
        raise ManifestForecastBundleError(
            "bundle run card is not a completed provider-free issuance"
        )
    if card.get("bundle_sha256") != claimed:
        raise ManifestForecastBundleError("bundle run card digest differs")
    snapshots: dict[Path, bytes] = {}
    cycle_id = _required_text(bundle, "cycle_id")
    freeze_record = _mapping(
        bundle.get("generic_freeze_inputs"), "generic_freeze_inputs"
    )
    freeze_root = Path(_required_text(freeze_record, "root"))
    freeze = _read_freeze_inputs(freeze_root, snapshots, expected_cycle_id=cycle_id)
    for section in (
        "owner_manifest",
        "model_registry",
        "provider_cycle_caps",
        "execution_policy",
    ):
        value = _mapping(bundle.get(section), section)
        path = Path(_required_text(value, "path"))
        payload = _snapshot(path, snapshots, section)
        if _sha(payload) != _required_sha(value, "sha256"):
            raise ManifestForecastBundleError(f"{section} bytes changed")
        snapshots[path] = payload
    forecast = _mapping(bundle.get("forecast_inputs"), "forecast_inputs")
    run_record_path = Path(_required_text(forecast, "run_record_path"))
    run_inputs_path = Path(_required_text(forecast, "run_inputs_path"))
    run_record_bytes = _snapshot(run_record_path, snapshots, "run record")
    run_inputs_bytes = _snapshot(run_inputs_path, snapshots, "run inputs")
    for key, label, payload in (
        ("run_record_path", "run record", run_record_bytes),
        ("run_inputs_path", "run inputs", run_inputs_bytes),
    ):
        path = Path(_required_text(forecast, key))
        if _sha(payload) != _required_sha(forecast, key.replace("_path", "_sha256")):
            raise ManifestForecastBundleError(f"{label} bytes changed")
    run_record = _json_object(run_record_bytes, "run record")
    run_inputs = _json_object(run_inputs_bytes, "run inputs")
    _require_cycle(run_record, cycle_id, "manifest forecast run record")
    _require_cycle(run_inputs, cycle_id, "manifest run inputs")
    owner_value = _mapping(bundle["owner_manifest"], "owner_manifest")
    owner_bytes = snapshots[Path(_required_text(owner_value, "path"))]
    manifest_sha = _required_sha(owner_value, "manifest_sha256")
    manifest = _load_manifest(owner_bytes, manifest_sha)
    _require_official_forecast_record(
        run_record,
        run_inputs,
        manifest=manifest,
        manifest_sha=manifest_sha,
    )
    registry_value = _mapping(bundle["model_registry"], "model_registry")
    registry_bytes = snapshots[Path(_required_text(registry_value, "path"))]
    caps_value = _mapping(bundle["provider_cycle_caps"], "provider_cycle_caps")
    policy_value = _mapping(bundle["execution_policy"], "execution_policy")
    registry_entries, policy = _authenticate_runtime_inputs(
        registry_bytes,
        snapshots[Path(_required_text(caps_value, "path"))],
        snapshots[Path(_required_text(policy_value, "path"))],
        cycle_id=cycle_id,
    )
    if registry_entries != registry_value.get("entries"):
        raise ManifestForecastBundleError("model registry entries changed")
    _require_prediction_units_source(
        run_record.get("prediction_units_source"),
        manifest.prediction_units_source.to_record(),
    )
    _require_policy_bindings(
        policy,
        repeat_policy=bundle.get("repeat_policy"),
        shard_schedule=bundle.get("shard_schedule"),
    )
    packet_sha256, prompt_sha256 = _forecast_commitments(
        run_inputs, run_record_path.parent, snapshots
    )
    if packet_sha256 != forecast.get("packet_sha256"):
        raise ManifestForecastBundleError("packet commitments changed")
    if prompt_sha256 != forecast.get("prompt_sha256"):
        raise ManifestForecastBundleError("prompt commitments changed")
    source = _mapping(
        run_record.get("prediction_units_source"), "prediction_units_source"
    )
    source_path = Path(_required_text(source, "path"))
    unit_identities = _prediction_unit_identities(source, snapshots)
    if sorted(unit_identities) != bundle.get("prediction_unit_identities"):
        raise ManifestForecastBundleError("prediction-unit commitments changed")
    expected_input_commitments = {
        str(path): _sha(payload)
        for path, payload in sorted(snapshots.items(), key=lambda item: str(item[0]))
    }
    if card.get("input_commitments") != expected_input_commitments:
        raise ManifestForecastBundleError("bundle input commitments changed")
    replayed_freeze = freeze
    if dict(replayed_freeze) != dict(freeze_record):
        raise ManifestForecastBundleError("generic freeze input commitments changed")
    del source_path
    if (
        bundle.get("labels_state") != "deferred"
        or bundle.get("labels_sha256") is not None
    ):
        raise ManifestForecastBundleError("issued bundle must remain labels-deferred")
    return bundle


def write_deferred_receipts(
    *,
    bundle: Mapping[str, Any] | Path,
    receipts: Sequence[Mapping[str, Any]],
    output: Path,
) -> tuple[Mapping[str, Any], ...]:
    """Validate and create-only write private, non-scoreable receipts."""

    if not isinstance(bundle, Path):
        raise DeferredReceiptError(
            "deferred receipts require a bundle path so all authenticated "
            "inputs can be replayed"
        )
    bundle_record = verify_bundle(bundle)
    if output.exists():
        raise DeferredReceiptError(f"deferred receipt output already exists: {output}")
    bound = _validate_deferred_rows(bundle_record, receipts)
    _write_jsonl_create_only(output, bound)
    return bound


def _validate_deferred_rows(
    bundle_record: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], ...]:
    """Validate deferred rows against a fully replayed bundle."""

    bundle_sha = _required_sha(bundle_record, "bundle_sha256")
    prompt_map = _mapping(
        _mapping(bundle_record["forecast_inputs"], "forecast_inputs").get(
            "prompt_sha256"
        ),
        "prompt_sha256",
    )
    packet_map = _mapping(
        _mapping(bundle_record["forecast_inputs"], "forecast_inputs").get(
            "packet_sha256"
        ),
        "packet_sha256",
    )
    bound: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    expected = _expected_receipt_keys(bundle_record)
    for raw in receipts:
        row = dict(raw)
        if row.get("labels_state") != "deferred":
            raise DeferredReceiptError("receipt labels_state must be deferred")
        if row.get("scoreable") is not False or row.get("publishable") is not False:
            raise DeferredReceiptError(
                "deferred receipt must be non-scoreable and non-publishable"
            )
        if row.get("bundle_sha256") != bundle_sha:
            raise DeferredReceiptError("receipt bundle digest differs")
        identity = (
            f"{_required_text(row, 'candidate_id')}:{_required_text(row, 'ablation')}"
        )
        prompt_sha = _required_sha(row, "actual_provider_prompt_sha256")
        packet_sha = _required_sha(row, "packet_sha256")
        if (
            prompt_map.get(identity) != prompt_sha
            or packet_map.get(identity) != packet_sha
        ):
            raise DeferredReceiptError(f"receipt identity is not in bundle: {identity}")
        _reject_label_lineage(row)
        key = (identity, prompt_sha, _nonnegative_int(row, "repeat_index"))
        if key in seen:
            raise DeferredReceiptError(f"duplicate deferred receipt: {identity}")
        seen.add(key)
        row["schema_version"] = str(MANIFEST_FORECAST_DEFERRED_RECEIPT_V1)
        expected_resume = _resume_identity(
            bundle_record,
            packet_sha=packet_sha,
            prompt_sha=prompt_sha,
            repeat_index=key[2],
        )
        supplied_resume = row.get("resume_identity_sha256")
        if supplied_resume is not None and supplied_resume != expected_resume:
            raise DeferredReceiptError("receipt resume identity differs")
        row["resume_identity_sha256"] = expected_resume
        bound.append(row)
    if seen != expected:
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        raise DeferredReceiptError(
            f"deferred receipt coverage differs (missing={missing}, extra={extra})"
        )
    return tuple(bound)


def attach_labels(
    *,
    bundle: Path,
    deferred_receipts: Path,
    labels: Path,
    decision_texts: Path,
    finalized_units: Path,
    label_run_card: Path,
    output_root: Path,
) -> LabelAttachmentBuild:
    """Authenticate Stage B lineage and derive fresh label-bound receipts."""

    if output_root.exists():
        raise ManifestForecastBundleError(
            f"label attachment output already exists: {output_root}"
        )
    bundle_record = verify_bundle(bundle)
    snapshots = {
        path: _read_regular(path, path.name)
        for path in (
            deferred_receipts,
            labels,
            decision_texts,
            finalized_units,
            label_run_card,
        )
    }
    receipts = _jsonl(snapshots[deferred_receipts], deferred_receipts)
    receipts = list(_validate_deferred_rows(bundle_record, receipts))
    label_rows = _jsonl(snapshots[labels], labels)
    decision_rows = _jsonl(snapshots[decision_texts], decision_texts)
    unit_rows = _jsonl(snapshots[finalized_units], finalized_units)
    card = _json_object(snapshots[label_run_card], "label run card")
    if (
        card.get("stage") not in ("llm-label", "label")
        or card.get("status") != "completed"
    ):
        raise ManifestForecastBundleError(
            "labels must come from a completed authenticated label run"
        )
    _require_card_commitment(card, "labels", _sha(snapshots[labels]))
    expected_units = set(bundle_record.get("prediction_unit_identities", []))
    final_units = _unit_identities(unit_rows)
    label_units = _unique_label_identities(label_rows)
    if final_units != expected_units or label_units != expected_units:
        raise ManifestForecastBundleError(
            "finalized units and labels do not exactly cover bundle units"
        )
    _validate_decision_evidence(label_rows, decision_rows)
    _validate_label_lineage(label_rows, unit_rows, decision_rows)
    attachment_core: dict[str, Any] = {
        "schema_version": str(MANIFEST_FORECAST_LABEL_ATTACHMENT_V1),
        "cycle_id": bundle_record["cycle_id"],
        "bundle_sha256": bundle_record["bundle_sha256"],
        "deferred_receipts_sha256": _sha(snapshots[deferred_receipts]),
        "labels_sha256": _sha(snapshots[labels]),
        "decision_texts_sha256": _sha(snapshots[decision_texts]),
        "finalized_units_sha256": _sha(snapshots[finalized_units]),
        "label_run_card_sha256": _sha(snapshots[label_run_card]),
        "coverage": sorted(expected_units),
        "status": "completed",
    }
    attachment_core["attachment_sha256"] = _sha(_canonical(attachment_core))
    bound_receipts = tuple(
        _derive_bound_receipt(row, attachment_core) for row in receipts
    )
    payloads = {
        _ATTACHMENT_NAME: _canonical(attachment_core),
        _BOUND_RECEIPTS_NAME: _jsonl_bytes(bound_receipts),
    }
    _publish_create_only(output_root, payloads)
    return LabelAttachmentBuild(attachment_core, bound_receipts)


def _derive_bound_receipt(
    deferred: Mapping[str, Any], attachment: Mapping[str, Any]
) -> Mapping[str, Any]:
    provider_evidence = dict(deferred)
    for key in (
        "labels_state",
        "scoreable",
        "publishable",
        "schema_version",
        "resume_identity_sha256",
    ):
        provider_evidence.pop(key, None)
    result = {
        "schema_version": str(MANIFEST_FORECAST_BOUND_RECEIPT_V1),
        "labels_state": "bound",
        "scoreable": True,
        "publishable": False,
        "bundle_sha256": attachment["bundle_sha256"],
        "label_attachment_sha256": attachment["attachment_sha256"],
        "labels_sha256": attachment["labels_sha256"],
        "provider_evidence": provider_evidence,
    }
    result["receipt_sha256"] = _sha(_canonical(result))
    return result


def _read_freeze_inputs(
    root: Path,
    snapshots: dict[Path, bytes],
    *,
    expected_cycle_id: str | None = None,
) -> Mapping[str, Any]:
    card_path = root / "run-cards/issue-manifest-freeze-inputs.json"
    card_bytes = _snapshot(card_path, snapshots, "generic freeze run card")
    card = _json_object(card_bytes, "generic freeze run card")
    if card.get("status") != "completed" or card.get("provider_calls_made") != 0:
        raise ManifestForecastBundleError(
            "generic freeze inputs are not completed/provider-free"
        )
    if expected_cycle_id is not None and card.get("cycle_id") != expected_cycle_id:
        raise ManifestForecastBundleError("generic freeze run card cycle_id differs")
    output_commitments = _mapping(
        card.get("output_commitments"), "generic freeze output commitments"
    )
    outputs: dict[str, str] = {}
    saw_no_baselines = False
    for name, claimed in output_commitments.items():
        path = (root / str(name)).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ManifestForecastBundleError(
                "generic freeze input escapes its output root"
            ) from exc
        payload = _snapshot(path, snapshots, f"generic freeze input {name}")
        if _sha(payload) != str(claimed):
            raise ManifestForecastBundleError(f"generic freeze input changed: {name}")
        if name == "no-baselines.json":
            no_baselines = _json_object(payload, "no-baselines sentinel")
            if (
                no_baselines.get("schema_version") != "legalforecast.no_baselines.v1"
                or no_baselines.get("status") != "unavailable"
                or (
                    expected_cycle_id is not None
                    and no_baselines.get("cycle_id") != expected_cycle_id
                )
            ):
                raise ManifestForecastBundleError(
                    "generic freeze no-baselines sentinel is not authenticated"
                )
            saw_no_baselines = True

        outputs[str(name)] = _sha(payload)
    if not saw_no_baselines:
        raise ManifestForecastBundleError(
            "generic freeze inputs lack the authenticated no-baselines sentinel"
        )
    return {
        "root": str(root),
        "run_card_sha256": _sha(card_bytes),
        "outputs": outputs,
    }


def _load_manifest(payload: bytes, manifest_sha: str) -> Any:
    """Authenticate the owner-signed manifest from the captured bytes."""

    try:
        manifest = load_signed_manifest_bytes(payload, expected_digest=manifest_sha)
    except (ValueError, TypeError) as exc:
        raise ManifestForecastBundleError(
            "owner manifest is not an authenticated signed manifest"
        ) from exc
    if len(manifest.cases) != _OFFICIAL_CASE_COUNT:
        raise ManifestForecastBundleError(
            "official manifest forecast requires exactly 100 cases"
        )
    return manifest


def _require_official_forecast_record(
    run_record: Mapping[str, Any],
    run_inputs: Mapping[str, Any],
    *,
    manifest: Any,
    manifest_sha: str,
) -> None:
    """Require the exact 100-case, two-ablation, no-tool forecast matrix."""

    if (
        run_record.get("manifest_sha256") != manifest_sha
        or run_record.get("cycle_id") != manifest.cycle_id
        or run_inputs.get("cycle_id") != manifest.cycle_id
        or run_record.get("schema_version")
        != "legalforecast.manifest_mode_forecast_run_record.v1"
        or run_record.get("entry_mode") != "owner_signed_manifest"
        or run_record.get("case_count") != _OFFICIAL_CASE_COUNT
        or run_record.get("packet_count")
        != _OFFICIAL_CASE_COUNT * len(OFFICIAL_SHARD_ABLATIONS)
        or run_record.get("packet_ablations") != list(OFFICIAL_SHARD_ABLATIONS)
        or run_record.get("provider_calls_made") != 0
        or run_record.get("docket_tool_enabled") is not False
        or run_record.get("required_eval_run_case_flags") != ["--no-docket-tool"]
    ):
        raise ManifestForecastBundleError(
            "manifest forecast is not the authenticated 100x2 no-tool input"
        )
    signature = _mapping(
        run_record.get("owner_signature_reference"), "owner_signature_reference"
    )
    _required_text(signature, "bead_id")
    approval_line = _required_text(signature, "approval_line")
    expected_approval = _OWNER_APPROVAL_TEMPLATE.format(digest=manifest_sha)
    if approval_line != expected_approval:
        raise ManifestForecastBundleError(
            "owner manifest approval line is not verbatim"
        )
    if run_record.get("prediction_units_source") != (
        manifest.prediction_units_source.to_record()
    ):
        raise ManifestForecastBundleError(
            "forecast prediction-unit source is not manifest-bound"
        )
    packets = _records(run_inputs.get("model_packets"), "model_packets")
    expected = {
        (case.candidate_id, ablation)
        for case in manifest.cases
        for ablation in OFFICIAL_SHARD_ABLATIONS
    }
    seen: set[tuple[str, str]] = set()
    for packet in packets:
        identity = (
            _required_text(packet, "candidate_id"),
            _required_text(packet, "ablation"),
        )
        if identity in seen or identity not in expected:
            raise ManifestForecastBundleError(
                "forecast packets do not exactly cover the 100x2 matrix"
            )
        seen.add(identity)
    if seen != expected:
        raise ManifestForecastBundleError(
            "forecast packets do not exactly cover the 100x2 matrix"
        )


def _authenticate_runtime_inputs(
    registry_bytes: bytes,
    caps_bytes: bytes,
    policy_bytes: bytes,
    *,
    cycle_id: str,
) -> tuple[list[dict[str, str]], Mapping[str, Any]]:
    """Validate official registry, authority-enabled caps, and policy bytes."""

    try:
        registry = load_model_registry_bytes(registry_bytes)
        entries = require_official_registry_entries(registry.entries)
    except (ValueError, TypeError) as exc:
        raise ManifestForecastBundleError(
            "model registry is not an authenticated official registry"
        ) from exc
    if len(entries) != _OFFICIAL_MODEL_COUNT:
        raise ManifestForecastBundleError(
            "official manifest forecast requires exactly four registry entries"
        )
    registry_entries = registry_record(entries)
    try:
        caps = load_provider_cycle_caps_bytes(caps_bytes, source="provider-cycle-caps")
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ManifestForecastBundleError(
            "provider cycle caps are not an authenticated authority-enabled artifact"
        ) from exc
    if caps.cycle_id != cycle_id:
        raise ManifestForecastBundleError("provider cycle caps cycle_id differs")
    try:
        expected_attempt_policy = caps.execution_attempt_policy(_sha(caps_bytes))
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ManifestForecastBundleError(
            "provider cycle caps lack an authenticated execution authority"
        ) from exc
    policy = _json_object(policy_bytes, "execution policy")
    try:
        verify_execution_policy(policy, expected_cycle_id=cycle_id)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ManifestForecastBundleError(
            "execution policy is not a verified policy artifact"
        ) from exc
    policy_content = _mapping(policy.get("policy"), "execution policy policy")
    if policy_content.get("attempt_policy") != expected_attempt_policy:
        raise ManifestForecastBundleError(
            "execution policy does not bind the provider caps authority"
        )
    return registry_entries, policy_content


def _require_policy_bindings(
    policy: Mapping[str, Any],
    *,
    repeat_policy: object,
    shard_schedule: object,
) -> None:
    """Reject operator schedule inputs that differ from the verified policy."""

    expected_repeat = policy.get("repeat_policy")
    expected_shards = _mapping(policy.get("shard_schedule"), "shard_schedule").get(
        "shards"
    )
    if _canonical_value(repeat_policy, "repeat_policy") != expected_repeat:
        raise ManifestForecastBundleError(
            "repeat policy does not match the verified execution policy"
        )
    if _canonical_value(shard_schedule, "shard_schedule") != expected_shards:
        raise ManifestForecastBundleError(
            "shard schedule does not match the verified execution policy"
        )


def _require_prediction_units_source(
    source: object,
    expected: Mapping[str, Any],
) -> None:
    source_map = _mapping(source, "prediction_units_source")
    if dict(source_map) != dict(expected):
        raise ManifestForecastBundleError(
            "prediction-unit source does not match the signed manifest"
        )


def _prediction_unit_identities(
    source: object, snapshots: dict[Path, bytes]
) -> tuple[str, ...]:
    source_map = _mapping(source, "prediction_units_source")
    path = Path(_required_text(source_map, "path"))
    payload = _snapshot(path, snapshots, "prediction units")
    if _sha(payload) != _required_sha(source_map, "sha256"):
        raise ManifestForecastBundleError("prediction-unit source bytes changed")
    identities = _unit_identities(_jsonl(payload, path))
    return tuple(sorted(identities))


def _forecast_commitments(
    run_inputs: Mapping[str, Any],
    forecast_root: Path,
    snapshots: dict[Path, bytes],
) -> tuple[dict[str, str], dict[str, str]]:
    """Recompute packet and prompt commitments from the captured run inputs."""

    packets = _records(run_inputs.get("model_packets"), "model_packets")
    packet_commitments: dict[str, str] = {}
    prompt_commitments: dict[str, str] = {}
    for packet in packets:
        identity = (
            f"{_required_text(packet, 'candidate_id')}:"
            f"{_required_text(packet, 'ablation')}"
        )
        if identity in packet_commitments:
            raise ManifestForecastBundleError(f"duplicate packet identity: {identity}")
        key = _required_text(packet, "packet_object_key")
        if not key.startswith("model-packets/"):
            raise ManifestForecastBundleError(
                "packet object key is outside model-packets"
            )
        path = (forecast_root / key).resolve()
        try:
            path.relative_to(forecast_root.resolve())
        except ValueError as exc:
            raise ManifestForecastBundleError(
                "packet object escapes forecast root"
            ) from exc
        packet_payload = _snapshot(path, snapshots, f"packet {key}")
        packet_sha = _required_sha(packet, "packet_sha256")
        if _sha(packet_payload) != packet_sha:
            raise ManifestForecastBundleError(f"packet commitment mismatch: {key}")
        prompt_sha = _required_sha(packet, "prompt_sha256")
        embedded_prompt = packet.get(
            "actual_provider_prompt_sha256", packet.get("prompt_sha256")
        )
        if embedded_prompt is not None and embedded_prompt != prompt_sha:
            raise ManifestForecastBundleError(f"prompt commitment mismatch: {identity}")
        packet_commitments[identity] = packet_sha
        prompt_commitments[identity] = prompt_sha
    return dict(sorted(packet_commitments.items())), dict(
        sorted(prompt_commitments.items())
    )


def _expected_receipt_keys(bundle: Mapping[str, Any]) -> set[tuple[str, str, int]]:
    forecast = _mapping(bundle.get("forecast_inputs"), "forecast_inputs")
    prompt_map = _mapping(forecast.get("prompt_sha256"), "prompt_sha256")
    repeat_policy = _mapping(bundle.get("repeat_policy"), "repeat_policy")
    raw_count = repeat_policy.get("count", repeat_policy.get("repeat_count", 1))
    if not isinstance(raw_count, int) or isinstance(raw_count, bool) or raw_count < 1:
        raise DeferredReceiptError("repeat policy count must be a positive integer")
    return {
        (str(identity), str(prompt_sha), repeat_index)
        for identity, prompt_sha in prompt_map.items()
        for repeat_index in range(raw_count)
    }


def _resume_identity(
    bundle: Mapping[str, Any],
    *,
    packet_sha: str,
    prompt_sha: str,
    repeat_index: int,
) -> str:
    return _sha(
        _canonical(
            {
                "bundle_sha256": _required_sha(bundle, "bundle_sha256"),
                "packet_sha256": packet_sha,
                "actual_provider_prompt_sha256": prompt_sha,
                "model_registry_sha256": _required_sha(
                    _mapping(bundle["model_registry"], "model_registry"), "sha256"
                ),
                "provider_cycle_caps_sha256": _required_sha(
                    _mapping(bundle["provider_cycle_caps"], "provider_cycle_caps"),
                    "sha256",
                ),
                "execution_policy_sha256": _required_sha(
                    _mapping(bundle["execution_policy"], "execution_policy"),
                    "sha256",
                ),
                "repeat_policy": bundle["repeat_policy"],
                "journal_namespace": bundle["journal_namespace"],
                "repeat_index": repeat_index,
            }
        )
    )


_LABEL_LINEAGE_KEYS = frozenset(
    {
        "label",
        "labels",
        "outcome",
        "disposition",
        "gold_label",
        "ground_truth",
        "human_label",
        "label_source",
        "label_lineage",
    }
)


def _reject_label_lineage(row: Mapping[str, Any]) -> None:
    """Reject outcome-bearing fields anywhere in a deferred provider receipt."""

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            mapping_value = cast(Mapping[str, object], value)
            for key, child in mapping_value.items():
                if key.lower() in _LABEL_LINEAGE_KEYS:
                    raise DeferredReceiptError(
                        "deferred receipt contains outcome or label bytes"
                    )
                visit(child)
        elif isinstance(value, list):
            for child in cast(list[object], value):
                visit(child)

    visit(row)


def _unique_label_identities(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    identities: set[str] = set()
    for row in rows:
        identity = _label_identity(row)
        if identity in identities:
            raise ManifestForecastBundleError(f"duplicate label identity: {identity}")
        identities.add(identity)
    return identities


def _validate_label_lineage(
    labels: Sequence[Mapping[str, Any]],
    finalized_units: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> None:
    """Require Stage B artifacts to remain outcome-hidden from the model path."""

    for collection, name in (
        (labels, "label"),
        (finalized_units, "finalized unit"),
        (decisions, "decision text"),
    ):
        for row in collection:
            if row.get("model_visible") is True:
                raise ManifestForecastBundleError(f"{name} is model-visible")
            source = row.get("source")
            if isinstance(source, str) and source.lower() in {
                "model",
                "llm",
                "hand-authored",
                "hand_authored",
                "manual",
            }:
                raise ManifestForecastBundleError(f"{name} has unauthenticated lineage")
            if (
                row.get("hand_authored") is True
                or row.get("generated_by_model") is True
            ):
                raise ManifestForecastBundleError(f"{name} has unauthenticated lineage")
    for row in decisions:
        if (
            "is_first_written_disposition" in row
            and row.get("is_first_written_disposition") is not True
        ):
            raise ManifestForecastBundleError(
                "decision text is not first-written disposition evidence"
            )


def _unit_identities(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    identities: set[str] = set()
    for row in rows:
        candidate = _required_text(row, "candidate_id")
        units = row.get("prediction_units", row.get("finalized_units"))
        if not isinstance(units, list):
            if "unit_id" in row:
                units = [row]
            else:
                raise ManifestForecastBundleError(
                    "prediction-unit row lacks prediction_units"
                )
        for unit in cast(list[object], units):
            mapping = _mapping(unit, "prediction unit")
            unit_id = _required_text(mapping, "unit_id")
            identity = f"{candidate}:{unit_id}"
            if identity in identities:
                raise ManifestForecastBundleError(
                    f"duplicate prediction unit: {identity}"
                )
            identities.add(identity)
    return identities


def _label_identity(row: Mapping[str, Any]) -> str:
    return f"{_required_text(row, 'candidate_id')}:{_required_text(row, 'unit_id')}"


def _validate_decision_evidence(
    labels: Sequence[Mapping[str, Any]], decisions: Sequence[Mapping[str, Any]]
) -> None:
    texts: dict[str, list[str]] = {}
    for row in decisions:
        candidate = _required_text(row, "candidate_id")
        text = _required_text(row, "text")
        if row.get("is_first_written_disposition") is not True:
            raise ManifestForecastBundleError(
                "decision text is not first-written disposition evidence"
            )
        texts.setdefault(candidate, []).append(text)
    for label in labels:
        candidate = _required_text(label, "candidate_id")
        evidence = label.get("disposition_evidence", label)
        evidence_map = _mapping(evidence, "label disposition evidence")
        excerpt = evidence_map.get("disposition_excerpt", evidence_map.get("excerpt"))
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ManifestForecastBundleError(
                "label lacks verbatim disposition excerpt"
            )
        if not any(excerpt in text for text in texts.get(candidate, [])):
            raise ManifestForecastBundleError(
                f"disposition excerpt is not verbatim evidence: {candidate}"
            )


def _require_card_commitment(card: Mapping[str, Any], name: str, digest: str) -> None:
    output = card.get("output_commitments")
    if not isinstance(output, Mapping) or name not in output:
        raise ManifestForecastBundleError(f"label run card lacks {name} commitment")
    output_map = cast(Mapping[str, Any], output)
    claimed: object = output_map[name]
    if isinstance(claimed, Mapping):
        claimed = cast(Mapping[str, object], claimed).get("sha256")
    if claimed != digest:
        raise ManifestForecastBundleError(f"label run card {name} commitment differs")


def _publish_create_only(root: Path, payloads: Mapping[str, bytes]) -> None:
    if root.exists():
        raise ManifestForecastBundleError(f"output already exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{root.name}.", dir=str(root.parent)))
    try:
        for name, payload in payloads.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
            except BaseException:
                os.close(fd)
                raise
        os.replace(temporary, root)
    except BaseException:
        if temporary.exists():
            for path in sorted(temporary.rglob("*"), reverse=True):
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            temporary.rmdir()
        raise


def _write_jsonl_create_only(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if path.exists():
        raise DeferredReceiptError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(_jsonl_bytes(rows))


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    payload = _read_regular(path, label)
    snapshots[path] = payload
    return payload


def _require_snapshots_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if _read_regular(path, path.name) != expected:
            raise ManifestForecastBundleError(f"input changed during issuance: {path}")


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManifestForecastBundleError(f"{label} must be a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestForecastBundleError(f"cannot read {label}: {path}") from exc


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ManifestForecastBundleError(f"{label} is not JSON") from exc
    if not isinstance(value, dict):
        raise ManifestForecastBundleError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonl(payload: bytes, path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(payload.splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestForecastBundleError(f"{path}:{number} is not JSON") from exc
        rows.append(dict(_mapping(value, f"{path}:{number}")))
    return rows


def _records(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManifestForecastBundleError(f"{label} must be an array")
    return [dict(_mapping(item, label)) for item in cast(list[object], value)]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestForecastBundleError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value:
        raise ManifestForecastBundleError(f"{name} must be a non-empty string")
    return value


def _required_sha(record: Mapping[str, Any], name: str) -> str:
    value = _required_text(record, name)
    if _SHA256.fullmatch(value) is None:
        raise ManifestForecastBundleError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _nonnegative_int(record: Mapping[str, Any], name: str) -> int:
    value = record.get(name, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DeferredReceiptError(f"{name} must be a non-negative integer")
    return value


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return canonical_json_bytes(
            value,
            error_type=ManifestForecastBundleError,
            error_message="value is not canonical JSON",
        )
    except TypeError as exc:
        raise ManifestForecastBundleError("value is not canonical JSON") from exc


def _canonical_value(value: object, label: str) -> object:
    _canonical(value)
    return json.loads(_canonical(value))


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical(row) for row in rows)


def _require_cycle(record: Mapping[str, Any], cycle_id: str, label: str) -> None:
    if record.get("cycle_id") != cycle_id:
        raise ManifestForecastBundleError(f"{label} cycle_id differs")

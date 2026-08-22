"""Authenticated, labels-deferred manifest forecast bundles.

This module is deliberately additive.  It does not alter the ordinary freeze,
shard-receipt, fan-in, or scoring contracts. The output is issuance groundwork
only: it is not a dispatch artifact, provider receipt, scoring input, or
publication input. Those bridges remain separate until their production
producers and authentic verifiers ship together.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import (
    MANIFEST_FORECAST_BUNDLE_RUN_CARD_V2,
    MANIFEST_FORECAST_BUNDLE_V2,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
    NO_BASELINES_V1,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.immutable_io import (
    ImmutableIOError,
    publish_tree_create_only,
    read_single_link_file,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.labeling.provider_journal import load_provider_cycle_caps_bytes
from legalforecast.protocol.policy_artifacts import (
    EXECUTION_POLICY_V2_SCHEMA_VERSION,
    OFFICIAL_SHARD_ABLATIONS,
    verify_execution_policy_v2,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_BUNDLE_NAME: Final = "bundle-v2.json"
_RUN_CARD_NAME: Final = "run-cards/manifest-forecast-bundle-v2.json"
_OFFICIAL_CASE_COUNT: Final = 100
_OFFICIAL_MODEL_COUNT: Final = 4
_OWNER_APPROVAL_TEMPLATE: Final = (
    "I approve corpus manifest {digest} as the frozen Cycle 1 forecast corpus."
)
_BUNDLE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "cycle_id",
        "generated_at",
        "labels_state",
        "labels_sha256",
        "scoreable",
        "publishable",
        "provider_calls_made",
        "owner_manifest",
        "forecast_inputs",
        "generic_freeze_inputs",
        "model_registry",
        "provider_cycle_caps",
        "execution_policy",
        "execution_constraints",
        "repeat_policy",
        "shard_schedule",
        "provider_attempt_policy",
        "prediction_unit_identities",
        "bundle_sha256",
    }
)
_RUN_CARD_FIELDS: Final = frozenset(
    {
        "schema_version",
        "stage",
        "status",
        "cycle_id",
        "provider_calls_made",
        "paid_activity_executed",
        "bundle_sha256",
        "input_commitments",
    }
)


class ManifestForecastBundleError(ValueError):
    """Raised when an authenticated deferred bundle is invalid."""


@dataclass(frozen=True, slots=True)
class ManifestForecastBundleBuild:
    """Bytes and the canonical bundle record produced before publication."""

    bundle: Mapping[str, Any]
    payloads: Mapping[str, bytes]
    input_snapshots: Mapping[Path, bytes]


def issue_bundle(
    *,
    cycle_id: str,
    freeze_inputs_root: Path,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    execution_policy: Path,
    output_root: Path,
    verify_freeze_inputs: Callable[[Path], Any],
) -> ManifestForecastBundleBuild:
    """Issue one create-only bundle from authenticated provider-free inputs."""

    if not cycle_id.strip():
        raise ManifestForecastBundleError("cycle_id is required")
    snapshots: dict[Path, bytes] = {}
    freeze = _read_freeze_inputs(
        freeze_inputs_root,
        snapshots,
        expected_cycle_id=cycle_id,
        verifier=verify_freeze_inputs,
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
    _require_freeze_cross_binding(
        freeze,
        owner_manifest=owner_manifest,
        model_registry=model_registry,
        forecast_output_dir=forecast_output_dir,
        owner_manifest_sha256=_sha(owner_bytes),
        model_registry_sha256=_sha(registry_bytes),
        run_record_sha256=_sha(forecast_record_bytes),
        run_inputs_sha256=_sha(run_inputs_bytes),
        prompt_commitments=prompt_commitments,
    )
    registry_entries, policy = _authenticate_runtime_inputs(
        registry_bytes,
        caps_bytes,
        policy_bytes,
        cycle_id=cycle_id,
    )
    repeat_policy, shard_schedule = _official_policy_bindings(
        policy, registry_entries=registry_entries
    )
    units_source = run_record.get("prediction_units_source")
    _require_prediction_units_source(
        units_source,
        manifest.prediction_units_source.to_record(),
    )
    unit_identities = _prediction_unit_identities(units_source, snapshots)
    generated_at = _required_text(run_record, "generated_at")
    _parse_timestamp(generated_at, "generated_at")
    if run_inputs.get("generated_at") != generated_at:
        raise ManifestForecastBundleError("run-inputs generated_at differs")
    core: dict[str, Any] = {
        "schema_version": str(MANIFEST_FORECAST_BUNDLE_V2),
        "cycle_id": cycle_id,
        "generated_at": generated_at,
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
        "repeat_policy": repeat_policy,
        "shard_schedule": shard_schedule,
        "provider_attempt_policy": _canonical_value(
            policy["attempt_policy"], "attempt_policy"
        ),
        "prediction_unit_identities": sorted(unit_identities),
    }
    core["bundle_sha256"] = _sha(_canonical(core))
    payloads = {
        _BUNDLE_NAME: _canonical(core),
        _RUN_CARD_NAME: _canonical(
            {
                "schema_version": str(MANIFEST_FORECAST_BUNDLE_RUN_CARD_V2),
                "stage": "issue-manifest-forecast-bundle-v2",
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


def verify_bundle(
    output_root: Path, *, verify_freeze_inputs: Callable[[Path], Any]
) -> Mapping[str, Any]:
    """Verify a previously issued bundle and every bound input byte."""

    bundle_path = output_root / _BUNDLE_NAME
    card_path = output_root / _RUN_CARD_NAME
    bundle_bytes = _read_regular(bundle_path, "manifest forecast bundle")
    bundle = _json_object(bundle_bytes, "manifest forecast bundle")
    if frozenset(bundle) != _BUNDLE_FIELDS:
        raise ManifestForecastBundleError(
            "manifest forecast bundle fields are not exact"
        )
    if bundle.get("schema_version") != str(MANIFEST_FORECAST_BUNDLE_V2):
        raise ManifestForecastBundleError("unsupported manifest forecast bundle schema")
    if bundle_bytes != _canonical(bundle):
        raise ManifestForecastBundleError("manifest forecast bundle is not canonical")
    claimed = _required_sha(bundle, "bundle_sha256")
    without = dict(bundle)
    del without["bundle_sha256"]
    if _sha(_canonical(without)) != claimed:
        raise ManifestForecastBundleError("bundle digest does not match content")
    card_bytes = _read_regular(card_path, "bundle run card")
    card = _json_object(card_bytes, "bundle run card")
    if frozenset(card) != _RUN_CARD_FIELDS:
        raise ManifestForecastBundleError("bundle run card fields are not exact")
    cycle_id = _required_text(bundle, "cycle_id")
    _parse_timestamp(_required_text(bundle, "generated_at"), "generated_at")
    if (
        bundle.get("labels_state") != "deferred"
        or bundle.get("labels_sha256") is not None
        or bundle.get("scoreable") is not False
        or bundle.get("publishable") is not False
        or bundle.get("provider_calls_made") != 0
        or bundle.get("execution_constraints")
        != {
            "docket_tool": False,
            "search": False,
            "tools": [],
            "outcome_labels_visible": False,
        }
    ):
        raise ManifestForecastBundleError(
            "issued bundle must remain private, provider-free, and labels-deferred"
        )
    if card_bytes != _canonical(card):
        raise ManifestForecastBundleError("bundle run card is not canonical")
    if (
        card.get("schema_version") != str(MANIFEST_FORECAST_BUNDLE_RUN_CARD_V2)
        or card.get("stage") != "issue-manifest-forecast-bundle-v2"
        or card.get("status") != "completed"
        or card.get("cycle_id") != cycle_id
        or card.get("provider_calls_made") != 0
        or card.get("paid_activity_executed") is not False
    ):
        raise ManifestForecastBundleError(
            "bundle run card is not a completed provider-free issuance"
        )
    if card.get("bundle_sha256") != claimed:
        raise ManifestForecastBundleError("bundle run card digest differs")
    snapshots: dict[Path, bytes] = {}
    freeze_record = _mapping(
        bundle.get("generic_freeze_inputs"), "generic_freeze_inputs"
    )
    freeze_root = Path(_required_text(freeze_record, "root"))
    freeze = _read_freeze_inputs(
        freeze_root,
        snapshots,
        expected_cycle_id=cycle_id,
        verifier=verify_freeze_inputs,
    )
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
        if _sha(payload) != _required_sha(forecast, key.replace("_path", "_sha256")):
            raise ManifestForecastBundleError(f"{label} bytes changed")
    run_record = _json_object(run_record_bytes, "run record")
    run_inputs = _json_object(run_inputs_bytes, "run inputs")
    _require_cycle(run_record, cycle_id, "manifest forecast run record")
    _require_cycle(run_inputs, cycle_id, "manifest run inputs")
    if run_record.get("generated_at") != bundle.get("generated_at") or run_inputs.get(
        "generated_at"
    ) != bundle.get("generated_at"):
        raise ManifestForecastBundleError("bundle timestamp is not forecast-bound")
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
    repeat_policy, shard_schedule = _official_policy_bindings(
        policy, registry_entries=registry_entries
    )
    if bundle.get("repeat_policy") != repeat_policy:
        raise ManifestForecastBundleError("bundle repeat policy changed")
    if bundle.get("shard_schedule") != shard_schedule:
        raise ManifestForecastBundleError("bundle shard schedule changed")
    if bundle.get("provider_attempt_policy") != policy.get("attempt_policy"):
        raise ManifestForecastBundleError("bundle provider attempt policy changed")
    packet_sha256, prompt_sha256 = _forecast_commitments(
        run_inputs, run_record_path.parent, snapshots
    )
    _require_freeze_cross_binding(
        freeze,
        owner_manifest=Path(_required_text(owner_value, "path")),
        model_registry=Path(_required_text(registry_value, "path")),
        forecast_output_dir=run_record_path.parent,
        owner_manifest_sha256=_sha(owner_bytes),
        model_registry_sha256=_sha(registry_bytes),
        run_record_sha256=_sha(run_record_bytes),
        run_inputs_sha256=_sha(run_inputs_bytes),
        prompt_commitments=prompt_sha256,
    )
    if packet_sha256 != forecast.get("packet_sha256"):
        raise ManifestForecastBundleError("packet commitments changed")
    if prompt_sha256 != forecast.get("prompt_sha256"):
        raise ManifestForecastBundleError("prompt commitments changed")
    source = _mapping(
        run_record.get("prediction_units_source"), "prediction_units_source"
    )
    _required_text(source, "path")
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
    _require_snapshots_unchanged(snapshots)
    return bundle


def _read_freeze_inputs(
    root: Path,
    snapshots: dict[Path, bytes],
    *,
    expected_cycle_id: str | None = None,
    verifier: Callable[[Path], Any],
) -> Mapping[str, Any]:
    try:
        build = verifier(root)
    except Exception as exc:
        raise ManifestForecastBundleError(
            "generic freeze inputs fail complete replay verification"
        ) from exc
    payloads = getattr(build, "payloads", None)
    run_card = getattr(build, "run_card", None)
    if not isinstance(payloads, Mapping) or not isinstance(run_card, Mapping):
        raise ManifestForecastBundleError(
            "generic freeze verifier returned an incomplete result"
        )
    payload_map = cast(Mapping[str, object], payloads)
    run_card_map = cast(Mapping[str, Any], run_card)
    expected_names = {
        "prompt-contract.json",
        "scorer-contract.json",
        "harness-contract.json",
        "no-baselines.json",
        "complete-exclusion-ledger.jsonl",
        "run-cards/issue-manifest-freeze-inputs.json",
    }
    if set(payload_map) != expected_names:
        raise ManifestForecastBundleError(
            "generic freeze verifier output inventory is not exact"
        )
    if (
        expected_cycle_id is not None
        and run_card_map.get("cycle_id") != expected_cycle_id
    ):
        raise ManifestForecastBundleError("generic freeze run card cycle_id differs")
    outputs: dict[str, str] = {}
    for name in sorted(expected_names):
        path = (root / name).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ManifestForecastBundleError(
                "generic freeze input escapes its output root"
            ) from exc
        payload = _snapshot(path, snapshots, f"generic freeze input {name}")
        expected = payload_map[name]
        if not isinstance(expected, bytes) or payload != expected:
            raise ManifestForecastBundleError(
                f"generic freeze verifier bytes differ: {name}"
            )
        outputs[name] = _sha(payload)
    no_baselines = _json_object(
        snapshots[(root / "no-baselines.json").resolve()], "no-baselines sentinel"
    )
    if (
        no_baselines.get("schema_version") != str(NO_BASELINES_V1)
        or no_baselines.get("status") != "unavailable"
        or (
            expected_cycle_id is not None
            and no_baselines.get("cycle_id") != expected_cycle_id
        )
    ):
        raise ManifestForecastBundleError(
            "generic freeze no-baselines sentinel is not authenticated"
        )
    input_paths = _mapping(run_card_map.get("input_paths"), "freeze input_paths")
    prompt_contract = _json_object(
        snapshots[(root / "prompt-contract.json").resolve()], "prompt contract"
    )
    prompt_replay = _mapping(
        prompt_contract.get("prompt_replay"), "freeze prompt_replay"
    )
    return {
        "root": str(root),
        "run_card_sha256": outputs["run-cards/issue-manifest-freeze-inputs.json"],
        "outputs": outputs,
        "input_paths": {
            name: _required_text(input_paths, name)
            for name in ("owner_manifest", "model_registry", "forecast_output_dir")
        },
        "prompt_replay": dict(prompt_replay),
    }


def _require_freeze_cross_binding(
    freeze: Mapping[str, Any],
    *,
    owner_manifest: Path,
    model_registry: Path,
    forecast_output_dir: Path,
    owner_manifest_sha256: str,
    model_registry_sha256: str,
    run_record_sha256: str,
    run_inputs_sha256: str,
    prompt_commitments: Mapping[str, str],
) -> None:
    paths = _mapping(freeze.get("input_paths"), "freeze input_paths")
    for name, expected in (
        ("owner_manifest", owner_manifest),
        ("model_registry", model_registry),
        ("forecast_output_dir", forecast_output_dir),
    ):
        if Path(_required_text(paths, name)).resolve() != expected.resolve():
            raise ManifestForecastBundleError(
                f"generic freeze {name} is not bundle-bound"
            )
    replay = _mapping(freeze.get("prompt_replay"), "freeze prompt_replay")
    expected_values: dict[str, object] = {
        "owner_manifest_bytes_sha256": owner_manifest_sha256,
        "model_registry_sha256": model_registry_sha256,
        "run_record_sha256": run_record_sha256,
        "run_inputs_sha256": run_inputs_sha256,
        "packet_count": _OFFICIAL_CASE_COUNT * len(OFFICIAL_SHARD_ABLATIONS),
        "candidate_count": _OFFICIAL_CASE_COUNT,
        "prompt_commitments": dict(sorted(prompt_commitments.items())),
    }
    for name, expected in expected_values.items():
        if replay.get(name) != expected:
            raise ManifestForecastBundleError(
                f"generic freeze prompt replay {name} is not bundle-bound"
            )


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
        or run_inputs.get("generated_at") != run_record.get("generated_at")
        or run_record.get("schema_version") != str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1)
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
    _parse_timestamp(_required_text(run_record, "generated_at"), "generated_at")
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
        verify_execution_policy_v2(policy, expected_cycle_id=cycle_id)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ManifestForecastBundleError(
            "execution policy is not a verified policy artifact"
        ) from exc
    if policy.get("schema_version") != EXECUTION_POLICY_V2_SCHEMA_VERSION:
        raise ManifestForecastBundleError(
            "deferred bundle requires execution policy v2"
        )
    policy_content = _mapping(policy.get("policy"), "execution policy policy")
    if policy_content.get("attempt_policy") != expected_attempt_policy:
        raise ManifestForecastBundleError(
            "execution policy does not bind the provider caps authority"
        )
    from legalforecast.evals.corpus_manifest.beads_observation import (
        SUCCESSOR_REGISTRY_KEYS,
    )

    if frozenset(entry.registry_key for entry in entries) != SUCCESSOR_REGISTRY_KEYS:
        raise ManifestForecastBundleError(
            "model registry does not contain the successor set"
        )
    if any(
        entry.network_disabled is not True
        or entry.search_disabled is not True
        or entry.temperature != 0.0
        or entry.top_p != 1.0
        or entry.tool_policy.value != "controlled_docket_tool_only"
        for entry in entries
    ):
        raise ManifestForecastBundleError("model registry execution safety differs")
    caps_providers = {
        _required_text(cap, "provider").lower()
        for cap in _records(
            expected_attempt_policy.get("provider_account_caps"),
            "provider_account_caps",
        )
    }
    if caps_providers != {entry.provider.lower() for entry in entries}:
        raise ManifestForecastBundleError(
            "provider caps do not exactly cover successor providers"
        )
    return registry_entries, policy_content


def _official_policy_bindings(
    policy: Mapping[str, Any], *, registry_entries: Sequence[Mapping[str, str]]
) -> tuple[Mapping[str, Any], list[Mapping[str, str]]]:
    """Derive the exact 800-cell official schedule from verified policy bytes."""

    if policy.get("cycle_series") != "official":
        raise ManifestForecastBundleError(
            "execution policy cycle_series must be official"
        )
    if policy.get("allow_no_baselines") is not True:
        raise ManifestForecastBundleError(
            "execution policy must allow the authenticated no-baselines sentinel"
        )
    repeat = _mapping(policy.get("repeat_policy"), "repeat_policy")
    if dict(repeat) != {"case_ids": [], "count": 1}:
        raise ManifestForecastBundleError(
            "official manifest forecast repeat policy must be empty/count=1"
        )
    schedule = _mapping(policy.get("shard_schedule"), "shard_schedule")
    raw_shards = schedule.get("shards")
    if not isinstance(raw_shards, list):
        raise ManifestForecastBundleError("shard schedule must contain shards")
    shards = [
        dict(_mapping(row, "shard schedule row"))
        for row in cast(list[object], raw_shards)
    ]
    registry_keys = {
        f"{_required_text(row, 'provider')}:{_required_text(row, 'model_id')}"
        for row in registry_entries
    }
    expected = {
        (key, ablation)
        for key in registry_keys
        for ablation in OFFICIAL_SHARD_ABLATIONS
    }
    observed = {
        (_required_text(row, "model_key"), _required_text(row, "ablation"))
        for row in shards
    }
    if (
        len(registry_keys) != _OFFICIAL_MODEL_COUNT
        or observed != expected
        or len(shards) != len(expected)
        or schedule.get("shard_count") != len(expected)
        or schedule.get("dispatch_unit") != "model_key_ablation"
    ):
        raise ManifestForecastBundleError(
            "execution policy must bind the exact four-model by two-ablation schedule"
        )
    return dict(repeat), [
        {"model_key": key, "ablation": ablation} for key, ablation in sorted(observed)
    ]


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
        _reject_outcome_leakage(_json_object(packet_payload, f"packet {key}"))
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


def _publish_create_only(root: Path, payloads: Mapping[str, bytes]) -> None:
    try:
        publish_tree_create_only(root, payloads)
    except ImmutableIOError as exc:
        raise ManifestForecastBundleError(str(exc)) from exc


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    payload = _read_regular(path, label)
    snapshots[path] = payload
    return payload


def _require_snapshots_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if _read_regular(path, path.name) != expected:
            raise ManifestForecastBundleError(f"input changed during issuance: {path}")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        return read_single_link_file(path, label=label)
    except ImmutableIOError as exc:
        raise ManifestForecastBundleError(str(exc)) from exc


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


def _require_cycle(record: Mapping[str, Any], cycle_id: str, label: str) -> None:
    if record.get("cycle_id") != cycle_id:
        raise ManifestForecastBundleError(f"{label} cycle_id differs")


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestForecastBundleError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestForecastBundleError(f"{label} must be timezone-aware")
    return parsed


def _reject_outcome_leakage(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in cast(Mapping[object, object], value).items():
            lowered = str(key).lower()
            if lowered in {"outcome", "outcome_label", "labels", "disposition"}:
                raise ManifestForecastBundleError(
                    f"forecast packet contains outcome field: {key}"
                )
            if lowered == "contains_target_outcome" and child is True:
                raise ManifestForecastBundleError(
                    "forecast packet contains target outcome material"
                )
            _reject_outcome_leakage(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            _reject_outcome_leakage(child)

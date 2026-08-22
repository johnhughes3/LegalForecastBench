"""Provider-free issuer for the authenticated Cycle 1 execution decisions.

The execution-policy generator already validates the policy shape.  This module
owns the missing upstream step: derive the decisions from authenticated
manifest, forecast, registry, caps, labeling/cohort, observation, and Beads
evidence, then create-only publish both the decisions and the generated policy.
No policy value is accepted from an operator on the command line.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import (
    MANIFEST_EXECUTION_DECISIONS_V1,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
    NO_BASELINES_V1,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cohort_policy import (
    verify_cohort_policy,
    verify_observation_manifest,
)
from legalforecast.labeling.provider_journal import load_provider_cycle_caps_bytes
from legalforecast.protocol.policy_artifacts import (
    OFFICIAL_SHARD_ABLATIONS,
    generate_execution_policy,
    verify_execution_policy,
    verify_labeling_policy,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_DECISIONS_NAME: Final = "execution-decisions.json"
_POLICY_NAME: Final = "execution-policy.json"
_RUN_CARD_NAME: Final = "run-cards/issue-manifest-execution-decisions.json"
_NO_BASELINES_NAME: Final = "no-baselines.json"
_BEADS_SCHEMA: Final = "legalforecast.execution_decisions_beads_observation.v1"
_OFFICIAL_CASE_COUNT: Final = 100
_ABLATIONS: Final = tuple(OFFICIAL_SHARD_ABLATIONS)
_POLICY_FIELDS: Final = frozenset(
    {
        "cycle_id",
        "cycle_series",
        "allow_no_baselines",
        "labeling_policy_sha256",
        "cohort_policy_sha256",
        "cohort_observation_manifest_sha256",
        "lifecycle",
        "shard_schedule",
        "concurrency_policy",
        "receipt_policy",
        "attempt_policy",
        "repeat_policy",
        "cadence_counts",
    }
)


class ExecutionDecisionsError(ValueError):
    """Raised when an authenticated execution-decision input is invalid."""


@dataclass(frozen=True, slots=True)
class ExecutionDecisionsBuild:
    """Canonical decisions, generated policy, and publication payloads."""

    decisions: Mapping[str, Any]
    execution_policy: Mapping[str, Any]
    run_card: Mapping[str, Any]
    payloads: Mapping[str, bytes]
    input_snapshots: Mapping[Path, bytes]


def issue_beads_observation(
    *,
    raw_observation: Path,
    raw_sha256: str,
    cycle_id: str,
    manifest_digest: str,
    model_registry: Path,
    bead_id: str,
    required_lines: Mapping[str, str],
    lifecycle: Mapping[str, str],
    ceiling_usd: float,
    estimate_usd: float,
    output: Path,
) -> Mapping[str, Any]:
    """Issue a Beads observation wrapper from hash-pinned raw ``bd`` JSON."""

    if output.exists():
        raise ExecutionDecisionsError(f"output already exists: {output}")
    payload = _read_regular(raw_observation, "raw Beads observation")
    if _sha(payload) != _required_digest(raw_sha256, "raw_sha256"):
        raise ExecutionDecisionsError("raw Beads observation hash differs")
    if not bead_id.strip():
        raise ExecutionDecisionsError("bead_id must be non-empty")
    if set(required_lines) != {"manifest", "contamination", "final_provider_spend"}:
        raise ExecutionDecisionsError("required Beads lines are not exact")
    observed_lines = _collect_lines(payload)
    line_records: dict[str, dict[str, str]] = {}
    for name, expected in required_lines.items():
        if expected not in observed_lines:
            raise ExecutionDecisionsError(
                f"raw Beads observation lacks exact {name} line"
            )
        line_records[name] = {"text": expected, "sha256": _sha(expected.encode())}
    if set(lifecycle) != {
        "production_labeling_started_at",
        "cohort_policy_published_at",
        "batch_002_started_at",
    }:
        raise ExecutionDecisionsError("Beads lifecycle fields are not exact")
    for name, value in lifecycle.items():
        _timestamp(value, name)
    wrapper = {
        "schema_version": _BEADS_SCHEMA,
        "cycle_id": cycle_id,
        "observed_at": datetime.now().astimezone().isoformat(),
        "bead_id": bead_id,
        "manifest_sha256": manifest_digest,
        "model_registry_path": str(model_registry),
        "spend": {"ceiling_usd": ceiling_usd, "estimate_usd": estimate_usd},
        "lines": line_records,
        "lifecycle": dict(lifecycle),
        "raw_observation_sha256": _sha(payload),
    }
    _verify_beads_observation(
        canonical_json_bytes(
            wrapper,
            error_type=ExecutionDecisionsError,
            error_message="Beads observation is not canonical JSON",
        ),
        cycle_id=cycle_id,
        manifest_digest=manifest_digest,
        model_registry=model_registry,
    )
    encoded = canonical_json_bytes(
        wrapper,
        error_type=ExecutionDecisionsError,
        error_message="Beads observation is not canonical JSON",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
    return wrapper


def issue_execution_decisions(
    *,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    labeling_policy: Path,
    cohort_policy: Path,
    cohort_observation_manifest: Path,
    beads_observation: Path,
    freeze_inputs_root: Path,
    output_root: Path,
) -> ExecutionDecisionsBuild:
    """Derive and create-only publish the official Cycle 1 decisions/policy."""

    if output_root.exists():
        raise ExecutionDecisionsError(f"output already exists: {output_root}")
    build = _build(
        owner_manifest=owner_manifest,
        forecast_output_dir=forecast_output_dir,
        model_registry=model_registry,
        provider_cycle_caps=provider_cycle_caps,
        labeling_policy=labeling_policy,
        cohort_policy=cohort_policy,
        cohort_observation_manifest=cohort_observation_manifest,
        beads_observation=beads_observation,
        freeze_inputs_root=freeze_inputs_root,
    )
    _require_unchanged(build.input_snapshots)
    _publish_create_only(output_root, build.payloads)
    _require_unchanged(build.input_snapshots)
    return build


def verify_execution_decisions(output_root: Path) -> ExecutionDecisionsBuild:
    """Rebuild and verify a previously issued decisions/policy tree."""

    card_path = output_root / _RUN_CARD_NAME
    card_bytes = _read_regular(card_path, "execution-decision run card")
    card = _json_object(card_bytes, "execution-decision run card")
    if card.get("status") != "completed" or card.get("provider_calls_made") != 0:
        raise ExecutionDecisionsError(
            "execution-decision run card is not provider-free"
        )
    inputs = _mapping(card.get("input_paths"), "run-card input_paths")
    build = _build(
        owner_manifest=Path(_required_text(inputs, "owner_manifest")),
        forecast_output_dir=Path(_required_text(inputs, "forecast_output_dir")),
        model_registry=Path(_required_text(inputs, "model_registry")),
        provider_cycle_caps=Path(_required_text(inputs, "provider_cycle_caps")),
        labeling_policy=Path(_required_text(inputs, "labeling_policy")),
        cohort_policy=Path(_required_text(inputs, "cohort_policy")),
        cohort_observation_manifest=Path(
            _required_text(inputs, "cohort_observation_manifest")
        ),
        beads_observation=Path(_required_text(inputs, "beads_observation")),
        freeze_inputs_root=Path(_required_text(inputs, "freeze_inputs_root")),
    )
    if card_bytes != build.payloads[_RUN_CARD_NAME]:
        raise ExecutionDecisionsError("execution-decision run card does not reproduce")
    decisions = _json_object(
        _read_regular(output_root / _DECISIONS_NAME, "execution decisions"),
        "execution decisions",
    )
    policy = _json_object(
        _read_regular(output_root / _POLICY_NAME, "execution policy"),
        "execution policy",
    )
    expected_output_commitments = {
        name: _sha(payload)
        for name, payload in build.payloads.items()
        if name != _RUN_CARD_NAME
    }
    if card.get("output_commitments") != expected_output_commitments:
        raise ExecutionDecisionsError(
            "execution-decision output commitments do not reproduce"
        )
    if decisions != dict(build.decisions):
        raise ExecutionDecisionsError("execution decisions do not reproduce")
    if policy != dict(build.execution_policy):
        raise ExecutionDecisionsError("execution policy does not reproduce")
    verify_execution_policy(policy, expected_cycle_id=decisions["cycle_id"])
    _require_unchanged(build.input_snapshots)
    return build


def _build(
    *,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    labeling_policy: Path,
    cohort_policy: Path,
    cohort_observation_manifest: Path,
    beads_observation: Path,
    freeze_inputs_root: Path,
) -> ExecutionDecisionsBuild:
    snapshots: dict[Path, bytes] = {}
    owner_bytes = _snapshot(owner_manifest, snapshots, "owner manifest")
    owner_record = _json_object(owner_bytes, "owner manifest")
    cycle_id = _required_sha(owner_record, "manifest_sha256")
    manifest = load_signed_manifest_bytes(owner_bytes, expected_digest=cycle_id)
    if len(manifest.cases) != _OFFICIAL_CASE_COUNT:
        raise ExecutionDecisionsError(
            "official execution requires exactly 100 manifest cases"
        )

    registry_bytes = _snapshot(model_registry, snapshots, "model registry")
    registry = load_model_registry_bytes(registry_bytes)
    entries = require_official_registry_entries(registry.entries)
    if len(entries) != 4:
        raise ExecutionDecisionsError(
            "official execution requires exactly four registry entries"
        )
    registry_keys = tuple(sorted(entry.registry_key for entry in entries))

    forecast = _verify_forecast(
        forecast_output_dir,
        snapshots,
        cycle_id=manifest.cycle_id,
        manifest_digest=cycle_id,
        expected_case_ids=tuple(case.candidate_id for case in manifest.cases),
        registry_keys=registry_keys,
        registry_entries=entries,
        prediction_units_source=manifest.prediction_units_source.to_record(),
    )
    if manifest.cycle_id != _required_text(owner_record, "cycle_id"):
        raise ExecutionDecisionsError("owner manifest cycle_id is invalid")
    cycle_id_text = manifest.cycle_id

    caps_bytes = _snapshot(provider_cycle_caps, snapshots, "provider cycle caps")
    caps = load_provider_cycle_caps_bytes(caps_bytes, source=provider_cycle_caps)
    if caps.cycle_id != cycle_id_text:
        raise ExecutionDecisionsError("provider cycle caps cycle_id differs")
    caps_sha = _sha(caps_bytes)
    attempt_policy = dict(caps.execution_attempt_policy(caps_sha))

    labeling_bytes = _snapshot(labeling_policy, snapshots, "labeling policy")
    labeling = _json_object(labeling_bytes, "labeling policy")
    verify_labeling_policy(labeling, expected_cycle_id=cycle_id_text)
    labeling_content = _mapping(labeling.get("policy"), "labeling policy")
    labeling_published = _required_text(labeling_content, "published_at")

    cohort_bytes = _snapshot(cohort_policy, snapshots, "cohort policy")
    cohort = _json_object(cohort_bytes, "cohort policy")
    verify_cohort_policy(cohort)
    cohort_content = _mapping(cohort.get("policy"), "cohort policy")
    if cohort_content.get("cycle_id") != cycle_id_text:
        raise ExecutionDecisionsError("cohort policy cycle_id differs")

    observation_bytes = _snapshot(
        cohort_observation_manifest, snapshots, "cohort observation manifest"
    )
    observation = _observation_records(observation_bytes)
    verify_observation_manifest(observation, policy_artifact=cohort)
    observation_sha = _sha(observation_bytes)

    beads_bytes = _snapshot(beads_observation, snapshots, "Beads observation")
    beads = _verify_beads_observation(
        beads_bytes,
        cycle_id=cycle_id_text,
        manifest_digest=cycle_id,
        model_registry=model_registry,
    )
    labeling_time = _parse_timestamp(labeling_published, "labeling policy published_at")
    labeling_started_time = _parse_timestamp(
        _required_text(beads["lifecycle"], "production_labeling_started_at"),
        "production_labeling_started_at",
    )
    if labeling_time > labeling_started_time:
        raise ExecutionDecisionsError(
            "labeling policy was not published before labeling started"
        )

    no_baselines_path = freeze_inputs_root / _NO_BASELINES_NAME
    no_baselines_bytes = _snapshot(
        no_baselines_path, snapshots, "no-baselines sentinel"
    )
    no_baselines = _json_object(no_baselines_bytes, "no-baselines sentinel")
    if (
        no_baselines.get("schema_version") != str(NO_BASELINES_V1)
        or no_baselines.get("cycle_id") != cycle_id_text
        or no_baselines.get("status") != "unavailable"
    ):
        raise ExecutionDecisionsError("no-baselines sentinel is not authenticated")
    freeze_card_path = (
        freeze_inputs_root / "run-cards/issue-manifest-freeze-inputs.json"
    )
    freeze_card_bytes = _snapshot(
        freeze_card_path, snapshots, "generic freeze-input run card"
    )
    freeze_card = _json_object(freeze_card_bytes, "generic freeze-input run card")
    freeze_outputs = _mapping(
        freeze_card.get("output_commitments"),
        "generic freeze-input output commitments",
    )
    if (
        freeze_card.get("status") != "completed"
        or freeze_card.get("cycle_id") != cycle_id_text
        or freeze_card.get("provider_calls_made") != 0
        or freeze_outputs.get(_NO_BASELINES_NAME) != _sha(no_baselines_bytes)
    ):
        raise ExecutionDecisionsError("generic freeze inputs are not authenticated")

    decisions: dict[str, Any] = {
        "cycle_id": cycle_id_text,
        "cycle_series": "official",
        "allow_no_baselines": True,
        # Policy links are raw bytes, matching FrozenArtifact.sha256 and the
        # cross-artifact checks in protocol.freeze.
        "labeling_policy_sha256": _sha(labeling_bytes),
        "cohort_policy_sha256": _sha(cohort_bytes),
        "cohort_observation_manifest_sha256": observation_sha,
        "lifecycle": {
            "labeling_policy_published_at": labeling_published,
            **beads["lifecycle"],
        },
        "shard_schedule": {
            "shard_count": len(registry_keys) * len(_ABLATIONS),
            "dispatch_unit": "model_key_ablation",
            "shards": [
                {"model_key": key, "ablation": ablation}
                for key in registry_keys
                for ablation in _ABLATIONS
            ],
        },
        "concurrency_policy": {
            "mode": "shard_identity",
            "identity_fields": ["cycle_id", "model_key", "ablation"],
        },
        "receipt_policy": {
            "write_once_per_attempt": True,
            "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
            "result_commitment_required": True,
        },
        "attempt_policy": attempt_policy,
        "repeat_policy": {"case_ids": [], "count": 1},
        "cadence_counts": {
            "clean_motion_count_source": "frozen_manifest",
            "prediction_unit_count_source": "frozen_units",
            "reject_operator_mismatch": True,
        },
        "authenticated_inputs": {
            "manifest_sha256": cycle_id,
            "run_inputs_sha256": forecast["run_inputs_sha256"],
            "model_registry_sha256": _sha(registry_bytes),
            "provider_cycle_caps_sha256": caps_sha,
            "labeling_policy_sha256": _sha(labeling_bytes),
            "cohort_policy_sha256": _sha(cohort_bytes),
            "cohort_observation_manifest_sha256": observation_sha,
            "beads_observation_sha256": _sha(beads_bytes),
            "beads_raw_observation_sha256": beads["raw_observation_sha256"],
            "beads_bead_id": beads["bead_id"],
            "beads_spend": {
                "ceiling_usd": beads["ceiling_usd"],
                "estimate_usd": beads["estimate_usd"],
            },
            "beads_line_sha256": beads["line_sha256"],
            "no_baselines_sha256": _sha(no_baselines_bytes),
            "request_count": len(manifest.cases) * len(registry_keys) * len(_ABLATIONS),
        },
    }
    policy_decisions = {
        key: value for key, value in decisions.items() if key in _POLICY_FIELDS
    }
    execution_policy = generate_execution_policy(policy_decisions)
    payloads = {
        _DECISIONS_NAME: canonical_json_bytes(
            {"schema_version": str(MANIFEST_EXECUTION_DECISIONS_V1), **decisions},
            error_type=ExecutionDecisionsError,
            error_message="execution decisions are not canonical JSON",
        ),
        _POLICY_NAME: _policy_bytes(execution_policy),
    }
    run_card = {
        "schema_version": str(MANIFEST_EXECUTION_DECISIONS_V1),
        "stage": "issue-manifest-execution-decisions",
        "status": "completed",
        "cycle_id": cycle_id_text,
        "provider_calls_made": 0,
        "paid_activity_executed": False,
        "input_paths": {
            "owner_manifest": str(owner_manifest),
            "forecast_output_dir": str(forecast_output_dir),
            "model_registry": str(model_registry),
            "provider_cycle_caps": str(provider_cycle_caps),
            "labeling_policy": str(labeling_policy),
            "cohort_policy": str(cohort_policy),
            "cohort_observation_manifest": str(cohort_observation_manifest),
            "beads_observation": str(beads_observation),
            "freeze_inputs_root": str(freeze_inputs_root),
        },
        "input_commitments": {
            str(path): _sha(payload)
            for path, payload in sorted(
                snapshots.items(), key=lambda item: str(item[0])
            )
        },
        "output_commitments": {
            name: _sha(payload) for name, payload in payloads.items()
        },
    }
    payloads[_RUN_CARD_NAME] = canonical_json_bytes(
        run_card,
        error_type=ExecutionDecisionsError,
        error_message="execution-decision run card is not canonical JSON",
    )
    return ExecutionDecisionsBuild(
        decisions={"schema_version": str(MANIFEST_EXECUTION_DECISIONS_V1), **decisions},
        execution_policy=execution_policy,
        run_card=run_card,
        payloads=payloads,
        input_snapshots=snapshots,
    )


def _verify_forecast(
    root: Path,
    snapshots: dict[Path, bytes],
    *,
    cycle_id: str,
    manifest_digest: str,
    expected_case_ids: tuple[str, ...],
    registry_keys: tuple[str, ...],
    registry_entries: tuple[Any, ...],
    prediction_units_source: Mapping[str, Any],
) -> dict[str, str]:
    record_path = root / "manifest-mode-run-record.json"
    inputs_path = root / "run-inputs.json"
    record_bytes = _snapshot(record_path, snapshots, "manifest forecast run record")
    inputs_bytes = _snapshot(inputs_path, snapshots, "manifest forecast run inputs")
    record = _json_object(record_bytes, "manifest forecast run record")
    inputs = _json_object(inputs_bytes, "manifest forecast run inputs")
    if (
        record.get("schema_version") != str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1)
        or record.get("manifest_sha256") != manifest_digest
        or record.get("cycle_id") != cycle_id
        or inputs.get("cycle_id") != cycle_id
        or record.get("entry_mode") != "owner_signed_manifest"
        or record.get("case_count") != len(expected_case_ids)
        or record.get("packet_count") != len(expected_case_ids) * len(_ABLATIONS)
        or record.get("packet_ablations") != list(_ABLATIONS)
        or record.get("provider_calls_made") != 0
        or record.get("docket_tool_enabled") is not False
        or record.get("required_eval_run_case_flags") != ["--no-docket-tool"]
    ):
        raise ExecutionDecisionsError(
            "manifest forecast is not authenticated no-docket input"
        )
    models = _mapping_list(record.get("evaluation_models"), "evaluation_models")
    if models != registry_record(registry_entries):
        raise ExecutionDecisionsError("forecast run record registry differs")
    actual_keys = tuple(
        sorted(
            f"{_required_text(row, 'provider')}:{_required_text(row, 'model_id')}"
            for row in models
        )
    )
    if actual_keys != registry_keys:
        raise ExecutionDecisionsError("forecast run record registry differs")
    signature = _mapping(
        record.get("owner_signature_reference"), "owner_signature_reference"
    )
    _required_text(signature, "bead_id")
    expected_approval = (
        f"I approve corpus manifest {manifest_digest} as the frozen Cycle 1 "
        "forecast corpus."
    )
    if _required_text(signature, "approval_line") != expected_approval:
        raise ExecutionDecisionsError("owner manifest approval line is not verbatim")
    if record.get("prediction_units_source") != dict(prediction_units_source):
        raise ExecutionDecisionsError(
            "forecast prediction-unit source is not manifest-bound"
        )
    packets = _mapping_list(inputs.get("model_packets"), "model_packets")
    if len(packets) != len(expected_case_ids) * len(_ABLATIONS):
        raise ExecutionDecisionsError("forecast packet count differs from manifest")
    expected_candidates = set(expected_case_ids)
    if len(expected_candidates) != len(expected_case_ids):
        raise ExecutionDecisionsError("manifest case IDs are not unique")
    prompt_commitments = _mapping(
        record.get("prompt_commitments"), "forecast prompt_commitments"
    )
    seen: set[tuple[str, str]] = set()
    for packet in packets:
        candidate = _required_text(packet, "candidate_id")
        if candidate not in expected_candidates:
            raise ExecutionDecisionsError(
                "forecast packet candidate is absent from signed manifest"
            )
        ablation = _required_text(packet, "ablation")
        pair = (candidate, ablation)
        if ablation not in _ABLATIONS or pair in seen:
            raise ExecutionDecisionsError(
                "forecast packet ablation coverage is invalid"
            )
        seen.add(pair)
        key = _required_text(packet, "packet_object_key")
        if not key.startswith("model-packets/"):
            raise ExecutionDecisionsError("forecast packet path is unsafe")
        packet_path = (root / key).resolve()
        try:
            packet_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ExecutionDecisionsError(
                "forecast packet escapes output root"
            ) from exc
        packet_bytes = _snapshot(packet_path, snapshots, f"forecast packet {key}")
        if _sha(packet_bytes) != _required_sha(packet, "packet_sha256"):
            raise ExecutionDecisionsError(f"forecast packet changed: {key}")
        prompt_sha = _required_sha(packet, "prompt_sha256")
        prompt_key = f"{candidate}:{ablation}"
        if prompt_commitments.get(prompt_key) != prompt_sha:
            raise ExecutionDecisionsError("forecast prompt commitment differs")
    expected = {
        (candidate, ablation)
        for candidate in expected_candidates
        for ablation in _ABLATIONS
    }
    if seen != expected:
        raise ExecutionDecisionsError("forecast packet ablations are incomplete")
    return {
        "run_inputs_sha256": _sha(inputs_bytes),
        "run_record_sha256": _sha(record_bytes),
    }


def _observation_records(payload: bytes) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            raise ExecutionDecisionsError(
                f"cohort observation manifest has a blank line at {line_number}"
            )
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExecutionDecisionsError(
                f"cohort observation manifest line {line_number} is not JSON"
            ) from exc
        if not isinstance(value, dict):
            raise ExecutionDecisionsError(
                f"cohort observation manifest line {line_number} is not an object"
            )
        records.append(cast(dict[str, Any], value))
    return tuple(records)


def _verify_beads_observation(
    payload: bytes,
    *,
    cycle_id: str,
    manifest_digest: str,
    model_registry: Path,
) -> dict[str, Any]:
    record = _json_object(payload, "Beads observation")
    if set(record) != {
        "schema_version",
        "cycle_id",
        "observed_at",
        "bead_id",
        "manifest_sha256",
        "model_registry_path",
        "raw_observation_sha256",
        "spend",
        "lines",
        "lifecycle",
    }:
        raise ExecutionDecisionsError("Beads observation fields are not exact")
    if (
        record.get("schema_version") != _BEADS_SCHEMA
        or record.get("cycle_id") != cycle_id
        or record.get("manifest_sha256") != manifest_digest
        or record.get("model_registry_path") != str(model_registry)
    ):
        raise ExecutionDecisionsError("Beads observation schema or cycle differs")
    _required_sha(record, "raw_observation_sha256")
    _required_text(record, "bead_id")
    observed_at = _required_text(record, "observed_at")
    _timestamp(observed_at, "observed_at")
    spend = _mapping(record.get("spend"), "Beads spend")
    if set(spend) != {"ceiling_usd", "estimate_usd"}:
        raise ExecutionDecisionsError("Beads spend fields are not exact")
    ceiling = _required_number(spend, "ceiling_usd")
    estimate = _required_number(spend, "estimate_usd")
    if ceiling < 0 or estimate < 0 or estimate > ceiling:
        raise ExecutionDecisionsError("Beads spend estimate exceeds ceiling")
    lines = _mapping(record.get("lines"), "Beads observation lines")
    if set(lines) != {"manifest", "contamination", "final_provider_spend"}:
        raise ExecutionDecisionsError("Beads observation lines are not exact")
    line_hashes: dict[str, str] = {}
    for name in ("manifest", "contamination", "final_provider_spend"):
        line = _mapping(lines.get(name), f"Beads {name} line")
        text = _required_text(line, "text")
        digest = _required_sha(line, "sha256")
        if _sha(text.encode()) != digest:
            raise ExecutionDecisionsError(f"Beads {name} line hash differs")
        line_hashes[name] = digest
    lifecycle = _mapping(record.get("lifecycle"), "Beads lifecycle")
    if set(lifecycle) != {
        "production_labeling_started_at",
        "cohort_policy_published_at",
        "batch_002_started_at",
    }:
        raise ExecutionDecisionsError("Beads lifecycle fields are not exact")
    lifecycle_times: dict[str, datetime] = {}
    for name in (
        "production_labeling_started_at",
        "cohort_policy_published_at",
        "batch_002_started_at",
    ):
        value = _required_text(lifecycle, name)
        _timestamp(value, name)
        lifecycle_times[name] = _parse_timestamp(value, name)
    if (
        lifecycle_times["cohort_policy_published_at"]
        > lifecycle_times["batch_002_started_at"]
    ):
        raise ExecutionDecisionsError(
            "cohort policy was not published before Batch 002"
        )
    return {
        "line_sha256": line_hashes,
        "lifecycle": dict(lifecycle),
        "bead_id": _required_text(record, "bead_id"),
        "raw_observation_sha256": _required_sha(record, "raw_observation_sha256"),
        "ceiling_usd": ceiling,
        "estimate_usd": estimate,
    }


def _policy_bytes(policy: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _publish_create_only(root: Path, payloads: Mapping[str, bytes]) -> None:
    if root.exists():
        raise ExecutionDecisionsError(f"output already exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{root.name}.", dir=str(root.parent)))
    try:
        for name, payload in payloads.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
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


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    payload = _read_regular(path, label)
    snapshots[path] = payload
    return payload


def _require_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if _read_regular(path, path.name) != expected:
            raise ExecutionDecisionsError(f"input changed during issuance: {path}")


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ExecutionDecisionsError(f"{label} must be a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ExecutionDecisionsError(f"cannot read {label}: {path}") from exc


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ExecutionDecisionsError(f"{label} is not JSON") from exc
    if not isinstance(value, dict):
        raise ExecutionDecisionsError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExecutionDecisionsError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _mapping_list(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ExecutionDecisionsError(f"{label} must be an array")
    return [_mapping(item, label) for item in cast(list[object], value)]


def _required_text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionDecisionsError(f"{name} must be a non-empty string")
    return value


def _required_sha(record: Mapping[str, Any], name: str) -> str:
    value = _required_text(record, name)
    if _SHA256.fullmatch(value) is None:
        raise ExecutionDecisionsError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _required_digest(value: str, name: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ExecutionDecisionsError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _required_number(record: Mapping[str, Any], name: str) -> float:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionDecisionsError(f"{name} must be a number")
    return float(value)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _collect_lines(payload: bytes) -> frozenset[str]:
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutionDecisionsError("raw Beads observation is not JSON") from exc
    lines: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            lines.extend(line.strip() for line in value.splitlines() if line.strip())
        elif isinstance(value, list):
            for item in cast(list[object], value):
                collect(item)
        elif isinstance(value, Mapping):
            for item in cast(Mapping[object, object], value).values():
                collect(item)

    collect(loaded)
    return frozenset(lines)


def _timestamp(value: str, name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionDecisionsError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionDecisionsError(f"{name} must be timezone-aware")


def _parse_timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionDecisionsError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionDecisionsError(f"{name} must be timezone-aware")
    return parsed

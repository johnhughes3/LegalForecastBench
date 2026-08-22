"""Authentication of frozen manifest cost projection inputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.schemas import (
    MANIFEST_FREEZE_RUNTIME_CONTRACT_V1,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
)
from legalforecast.evals.corpus_manifest.cost_projector_contract import (
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    packet_object_key_from_row,
    packet_sha256_from_row,
    required_nonnegative_int,
)
from legalforecast.evals.corpus_manifest.cost_projector_io import normalized_absolute
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.ingestion.cohort_document_materializer import (
    CohortDocumentMaterializationError,
    require_materializer_artifact,
)
from legalforecast.protocol.freeze import (
    FreezeProtocolError,
    FrozenArtifactName,
    verify_freeze_bundle,
)

_EXPECTED_PACKET_COUNT = 200
_EXPECTED_CASE_COUNT = 100


@dataclass(frozen=True, slots=True)
class AuthenticatedManifestCostInputs:
    """Exact bytes accepted through the issued manifest freeze chain."""

    run_inputs: Mapping[str, Any]
    registry_records: Sequence[Mapping[str, Any]]
    run_input_bytes: bytes
    registry_bytes: bytes
    packet_payloads: Mapping[str, bytes]
    snapshots: Mapping[Path, bytes]
    input_commitments: Mapping[str, Any]


def authenticate_manifest_cost_inputs(
    request: ManifestCostProjectionRequest,
) -> AuthenticatedManifestCostInputs:
    """Authenticate the complete issued freeze and every manifest packet byte."""

    snapshots: dict[Path, bytes] = {}
    freeze_root = normalized_absolute(request.freeze_root)
    manifest_run_root = normalized_absolute(request.manifest_run_root)
    freeze_bundle = _bounded_path(
        request.freeze_bundle, root=freeze_root, label="freeze bundle"
    )
    amendment_bundles = tuple(
        _bounded_path(path, root=freeze_root, label="freeze amendment bundle")
        for path in request.amendment_bundles
    )
    freeze_bytes = _snapshot(freeze_bundle, snapshots, "freeze bundle")
    amendment_bytes = [
        _snapshot(path, snapshots, "freeze amendment bundle")
        for path in amendment_bundles
    ]
    try:
        bundle = verify_freeze_bundle(
            freeze_bundle,
            cycle_id=request.cycle_id,
            root_path=freeze_root,
            amendment_bundle_paths=amendment_bundles,
        )
    except (FreezeProtocolError, OSError, ValueError) as exc:
        raise ManifestCostProjectionError(
            f"manifest freeze is not valid: {exc}"
        ) from exc
    if _snapshot(freeze_bundle, snapshots, "freeze bundle recheck") != freeze_bytes:
        raise ManifestCostProjectionError("freeze bundle changed during authentication")
    for path, expected in zip(amendment_bundles, amendment_bytes, strict=True):
        if _snapshot(path, snapshots, "freeze amendment recheck") != expected:
            raise ManifestCostProjectionError(
                "freeze amendment bundle changed during authentication"
            )

    frozen_payloads: dict[FrozenArtifactName, bytes] = {}
    for artifact in bundle.artifacts:
        path = _bounded_path(
            artifact.path, root=freeze_root, label=f"frozen {artifact.name.value}"
        )
        payload = _snapshot(path, snapshots, f"frozen {artifact.name.value}")
        if (
            hashlib.sha256(payload).hexdigest() != artifact.sha256
            or len(payload) != artifact.size_bytes
        ):
            raise ManifestCostProjectionError(
                f"frozen {artifact.name.value} bytes differ from freeze commitment"
            )
        frozen_payloads[artifact.name] = payload

    try:
        manifest_bytes = frozen_payloads[FrozenArtifactName.MANIFEST]
        registry_bytes = frozen_payloads[FrozenArtifactName.MODEL_REGISTRY]
        prompt_bytes = frozen_payloads[FrozenArtifactName.PROMPT]
    except KeyError as exc:  # Defensive for mocked or future freeze implementations.
        raise ManifestCostProjectionError(
            f"manifest freeze is missing required artifact: {exc.args[0]}"
        ) from exc
    run_input_path = _bounded_path(
        manifest_run_root / "run-inputs.json",
        root=manifest_run_root,
        label="manifest run-inputs",
    )
    run_record_path = _bounded_path(
        manifest_run_root / "manifest-mode-run-record.json",
        root=manifest_run_root,
        label="manifest run record",
    )
    run_input_bytes = _snapshot(run_input_path, snapshots, "manifest run-inputs")
    run_record_bytes = _snapshot(run_record_path, snapshots, "manifest run record")
    prompt = _json_object(prompt_bytes, "frozen prompt contract")
    run_inputs = _json_object(run_input_bytes, "manifest run-inputs")
    run_record = _json_object(run_record_bytes, "manifest run record")
    prompt_replay = _mapping(prompt.get("prompt_replay"), "prompt contract replay")
    _verify_manifest_chain(
        request=request,
        prompt=prompt,
        prompt_replay=prompt_replay,
        manifest_bytes=manifest_bytes,
        registry_bytes=registry_bytes,
        run_input_bytes=run_input_bytes,
        run_record_bytes=run_record_bytes,
        run_inputs=run_inputs,
        run_record=run_record,
    )

    try:
        registry = load_model_registry_bytes(registry_bytes)
        entries = require_official_registry_entries(registry.entries)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManifestCostProjectionError(
            f"frozen model registry is not valid: {exc}"
        ) from exc
    raw_registry_records = _json_array(registry_bytes, "model registry")
    expected_registry_record = registry_record(entries)
    if (
        run_record.get("evaluation_models") != expected_registry_record
        or prompt_replay.get("evaluation_models") != expected_registry_record
        or run_record.get("evaluation_release_anchor")
        != earliest_eligible_decision_date(entries).isoformat()
        or prompt_replay.get("evaluation_release_anchor")
        != earliest_eligible_decision_date(entries).isoformat()
    ):
        raise ManifestCostProjectionError(
            "manifest run registry identity differs from frozen successor registry"
        )

    raw_packets = run_inputs.get("model_packets")
    if not isinstance(raw_packets, list):
        raise ManifestCostProjectionError(
            "run-input manifest must contain exactly 200 model_packets"
        )
    packets = cast(list[object], raw_packets)
    if len(packets) != _EXPECTED_PACKET_COUNT:
        raise ManifestCostProjectionError(
            "run-input manifest must contain exactly 200 model_packets"
        )
    packet_payloads: dict[str, bytes] = {}
    packet_commitments: list[dict[str, int | str]] = []
    seen_keys: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_cases: set[str] = set()
    for raw_packet in packets:
        if not isinstance(raw_packet, Mapping):
            raise ManifestCostProjectionError("model_packets entries must be objects")
        packet = cast(Mapping[str, Any], raw_packet)
        key = packet_object_key_from_row(packet)
        if key in seen_keys:
            raise ManifestCostProjectionError(f"duplicate packet_object_key: {key}")
        seen_keys.add(key)
        packet_path = _bounded_packet_path(manifest_run_root, key)
        payload = _snapshot(packet_path, snapshots, f"packet {key}")
        expected_sha256 = packet_sha256_from_row(packet)
        expected_size = required_nonnegative_int(
            packet, "packet_size_bytes", label="matrix row"
        )
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ManifestCostProjectionError(
                f"packet bytes differ from run-inputs: {key}"
            )
        if len(payload) != expected_size:
            raise ManifestCostProjectionError(
                f"packet size differs from run-inputs: {key}"
            )
        packet_record = _json_object(payload, f"packet {key}")
        for field_name in ("candidate_id", "case_id", "ablation"):
            if packet_record.get(field_name) != packet.get(field_name):
                raise ManifestCostProjectionError(
                    f"packet {field_name} differs from run-inputs: {key}"
                )
        candidate_id = _required_string(packet, "candidate_id", "matrix row")
        ablation = _required_string(packet, "ablation", "matrix row")
        pair = (candidate_id, ablation)
        if pair in seen_pairs:
            raise ManifestCostProjectionError(
                f"duplicate candidate/ablation packet: {pair}"
            )
        seen_pairs.add(pair)
        seen_cases.add(candidate_id)
        packet_payloads[key] = payload
        packet_commitments.append(
            {
                "packet_object_key": key,
                "sha256": expected_sha256,
                "size_bytes": expected_size,
            }
        )
    if (
        prompt_replay.get("packet_count") != _EXPECTED_PACKET_COUNT
        or prompt_replay.get("candidate_count") != _EXPECTED_CASE_COUNT
        or len(seen_cases) != _EXPECTED_CASE_COUNT
    ):
        raise ManifestCostProjectionError(
            "frozen prompt contract packet matrix differs from manifest run"
        )

    input_commitments: dict[str, Any] = {
        "freeze_bundle": _raw_commitment(freeze_bytes),
        "freeze_amendment_bundles": [
            _raw_commitment(payload) for payload in amendment_bytes
        ],
        "owner_manifest": _raw_commitment(manifest_bytes),
        "manifest_run_record": _raw_commitment(run_record_bytes),
        "run_input_manifest": _raw_commitment(run_input_bytes),
        "model_registry": _raw_commitment(registry_bytes),
        "prompt_contract": _raw_commitment(prompt_bytes),
        "packets": packet_commitments,
    }
    return AuthenticatedManifestCostInputs(
        run_inputs=run_inputs,
        registry_records=raw_registry_records,
        run_input_bytes=run_input_bytes,
        registry_bytes=registry_bytes,
        packet_payloads=packet_payloads,
        snapshots=snapshots,
        input_commitments=input_commitments,
    )


def require_inputs_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    """Re-read every authenticated input and reject any pre-commit drift."""

    for path, expected in snapshots.items():
        if _read_regular(path, "cost projection source recheck") != expected:
            raise ManifestCostProjectionError(f"input changed during issuance: {path}")


def _raw_commitment(payload: bytes) -> dict[str, int | str]:
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _json_value(payload: bytes, label: str) -> object:
    try:
        return json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestCostProjectionError(f"{label} must be valid UTF-8 JSON") from exc


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = _json_value(payload, label)
    if not isinstance(value, Mapping):
        raise ManifestCostProjectionError(f"{label} must be a JSON object")
    return dict(cast(Mapping[str, Any], value))


def _json_array(payload: bytes, label: str) -> list[Mapping[str, Any]]:
    value = _json_value(payload, label)
    if not isinstance(value, list):
        raise ManifestCostProjectionError(f"{label} must be a JSON array")
    records: list[Mapping[str, Any]] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, Mapping):
            raise ManifestCostProjectionError(f"{label} entries must be objects")
        records.append(cast(Mapping[str, Any], raw))
    return records


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestCostProjectionError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_string(record: Mapping[str, Any], field_name: str, label: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManifestCostProjectionError(f"{label} requires {field_name}")
    return value


def _required_sha256(record: Mapping[str, Any], field_name: str, label: str) -> str:
    value = _required_string(record, field_name, label)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ManifestCostProjectionError(
            f"{label} {field_name} must be a lowercase SHA-256"
        )
    return value


def _verify_manifest_chain(
    *,
    request: ManifestCostProjectionRequest,
    prompt: Mapping[str, Any],
    prompt_replay: Mapping[str, Any],
    manifest_bytes: bytes,
    registry_bytes: bytes,
    run_input_bytes: bytes,
    run_record_bytes: bytes,
    run_inputs: Mapping[str, Any],
    run_record: Mapping[str, Any],
) -> None:
    if (
        prompt.get("schema_version") != str(MANIFEST_FREEZE_RUNTIME_CONTRACT_V1)
        or prompt.get("artifact_role") != "prompt"
        or prompt.get("cycle_id") != request.cycle_id
        or prompt.get("required_eval_run_case_flags") != ["--no-docket-tool"]
        or prompt.get("use_docket_tool") is not False
    ):
        raise ManifestCostProjectionError(
            "freeze prompt artifact is not the manifest runtime contract"
        )
    digest = _required_sha256(prompt_replay, "manifest_sha256", "prompt replay")
    commitments = (
        (manifest_bytes, "owner_manifest_bytes_sha256", "owner manifest"),
        (registry_bytes, "model_registry_sha256", "model registry"),
        (run_input_bytes, "run_inputs_sha256", "run-input manifest"),
        (run_record_bytes, "run_record_sha256", "manifest run record"),
    )
    for payload, field_name, label in commitments:
        if hashlib.sha256(payload).hexdigest() != _required_sha256(
            prompt_replay, field_name, "prompt replay"
        ):
            raise ManifestCostProjectionError(
                f"{label} differs from frozen prompt replay commitment"
            )
    try:
        manifest = load_signed_manifest_bytes(manifest_bytes, expected_digest=digest)
    except ValueError as exc:
        raise ManifestCostProjectionError(
            f"owner manifest is not valid: {exc}"
        ) from exc
    if manifest.cycle_id != request.cycle_id:
        raise ManifestCostProjectionError(
            "owner manifest cycle_id does not match dispatch input"
        )
    signature = _mapping(
        run_record.get("owner_signature_reference"),
        "manifest run owner_signature_reference",
    )
    frozen_signature = _mapping(
        prompt_replay.get("owner_signature_reference"),
        "prompt replay owner_signature_reference",
    )
    approval_line = _required_string(signature, "approval_line", "owner signature")
    expected_approval = (
        f"I approve corpus manifest {digest} as the frozen Cycle 1 forecast corpus."
    )
    if (
        signature != frozen_signature
        or approval_line != expected_approval
        or not _required_string(signature, "bead_id", "owner signature")
    ):
        raise ManifestCostProjectionError(
            "manifest run does not carry the exact frozen owner approval"
        )
    if (
        run_record.get("schema_version") != str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1)
        or run_record.get("entry_mode") != "owner_signed_manifest"
        or run_record.get("cycle_id") != request.cycle_id
        or run_record.get("manifest_sha256") != digest
        or run_record.get("packet_ablations") != ["full_packet", "metadata_only"]
        or run_record.get("case_count") != _EXPECTED_CASE_COUNT
        or run_record.get("packet_count") != _EXPECTED_PACKET_COUNT
        or run_record.get("provider_calls_made") != 0
        or run_record.get("docket_tool_enabled") is not False
        or run_record.get("required_eval_run_case_flags") != ["--no-docket-tool"]
    ):
        raise ManifestCostProjectionError(
            "manifest run record is not the authenticated 100x2 no-tool build"
        )
    if (
        run_inputs.get("cycle_id") != request.cycle_id
        or run_inputs.get("generated_at") != run_record.get("generated_at")
        or run_record.get("prompt_commitments")
        != prompt_replay.get("prompt_commitments")
    ):
        raise ManifestCostProjectionError(
            "manifest run inputs differ from the frozen manifest run record"
        )


def _bounded_path(path: Path, *, root: Path, label: str) -> Path:
    normalized = normalized_absolute(path)
    try:
        normalized.relative_to(root)
    except ValueError as exc:
        raise ManifestCostProjectionError(
            f"{label} escapes its authenticated root"
        ) from exc
    return normalized


def _bounded_packet_path(manifest_run_root: Path, key: str) -> Path:
    path = _bounded_path(
        manifest_run_root / key,
        root=manifest_run_root,
        label="packet path",
    )
    packet_root = manifest_run_root / "model-packets"
    try:
        path.relative_to(packet_root)
    except ValueError as exc:
        raise ManifestCostProjectionError(
            "packet path escapes model-packets root"
        ) from exc
    return path


def _read_regular(path: Path, label: str) -> bytes:
    try:
        return require_materializer_artifact(path, label=label)
    except CohortDocumentMaterializationError as exc:
        raise ManifestCostProjectionError(str(exc)) from exc


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    normalized = normalized_absolute(path)
    payload = _read_regular(normalized, label)
    previous = snapshots.get(normalized)
    if previous is not None and previous != payload:
        raise ManifestCostProjectionError(
            f"input changed during authentication: {path}"
        )
    snapshots[normalized] = payload
    return payload

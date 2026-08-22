"""Provider-free official manifest cost projection and receipt issuance."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import MANIFEST_COST_PROJECTION_RECEIPT_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    require_repeat_case_coverage,
)

PRICE_UNITS_PER_TOKEN: Final = Decimal(1_000_000)
LONG_CONTEXT_SURCHARGE_THRESHOLD_TOKENS: Final = 272_000
SUPPORTED_ABLATIONS: Final = frozenset(
    {
        "full_packet",
        "metadata_only",
        "briefs_only_redacted",
        "judge_removed",
        "no_briefs",
    }
)
PROVIDER_LANES: Final = ("openai", "anthropic", "gemini")
_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_SIX_PLACES: Final = Decimal("0.000001")


class ManifestCostProjectionError(ValueError):
    """Raised when cost inputs or issuance fail closed."""


@dataclass(frozen=True, slots=True)
class ManifestCostProjectionRequest:
    """Inputs to one deterministic provider-free cost projection."""

    run_input_manifest: Path
    model_registry: Path
    cycle_id: str
    model_keys: tuple[str, ...]
    ablations: tuple[str, ...]
    repeat_count: int
    repeat_sample_case_ids: tuple[str, ...]
    max_projected_model_cost_usd: str | None
    matrix_limit: int
    output: Path

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ManifestCostProjectionError("cycle_id is required")
        if not 1 <= self.repeat_count <= 10:
            raise ManifestCostProjectionError(
                "repeat_count must be an integer from 1 through 10"
            )
        if self.matrix_limit < 1:
            raise ManifestCostProjectionError("matrix_limit must be positive")


def issue_manifest_cost_projection(
    request: ManifestCostProjectionRequest,
) -> dict[str, Any]:
    """Project exact workflow costs and create-only publish a canonical receipt."""

    if request.output.exists() or request.output.is_symlink():
        raise ManifestCostProjectionError(
            f"output already exists; refusing create-only issuance: {request.output}"
        )
    manifest_bytes = _read_regular(request.run_input_manifest, "run-input manifest")
    registry_bytes = _read_regular(request.model_registry, "model registry")
    receipt = build_manifest_cost_projection(
        request,
        manifest_bytes=manifest_bytes,
        registry_bytes=registry_bytes,
    )
    payload = canonical_json_bytes(
        receipt,
        error_type=ManifestCostProjectionError,
        error_message="manifest cost projection receipt is not canonical JSON",
    )
    snapshots = {
        request.run_input_manifest: manifest_bytes,
        request.model_registry: registry_bytes,
    }
    _require_inputs_unchanged(snapshots)
    _write_create_only(request.output, payload)
    _require_inputs_unchanged(snapshots)
    return receipt


def build_manifest_cost_projection(
    request: ManifestCostProjectionRequest,
    *,
    manifest_bytes: bytes,
    registry_bytes: bytes,
) -> dict[str, Any]:
    """Build one receipt from already-snapshotted raw input bytes."""

    manifest = _json_value(manifest_bytes, "run-input manifest")
    registry_records = _json_value(registry_bytes, "model registry")
    if not isinstance(manifest, dict):
        raise ManifestCostProjectionError("run-input manifest must be a JSON object")
    manifest_record = cast(dict[str, object], manifest)
    if manifest_record.get("cycle_id") != request.cycle_id:
        raise ManifestCostProjectionError(
            "run-input manifest cycle_id does not match dispatch input"
        )
    raw_packets = manifest_record.get("model_packets")
    if not isinstance(raw_packets, list):
        raise ManifestCostProjectionError(
            "run-input manifest must contain model_packets list"
        )
    packets = cast(list[object], raw_packets)
    registry_by_key = _registry_by_key(registry_records)
    requested_model_keys = _requested_values(request.model_keys, "model_keys")
    missing_model_keys = [
        key for key in requested_model_keys if key not in registry_by_key
    ]
    if missing_model_keys:
        raise ManifestCostProjectionError(
            f"model_keys missing from registry: {missing_model_keys}"
        )
    requested_ablations = _requested_values(request.ablations, "ablations")
    unsupported_ablations = sorted(set(requested_ablations) - SUPPORTED_ABLATIONS)
    if unsupported_ablations:
        raise ManifestCostProjectionError(
            f"unsupported ablations: {unsupported_ablations}"
        )
    repeat_sample_case_ids = sorted(
        {
            case_id.strip()
            for case_id in request.repeat_sample_case_ids
            if case_id.strip()
        }
    )
    try:
        require_repeat_case_coverage(
            packets,
            repeat_case_ids=repeat_sample_case_ids,
            requested_ablations=requested_ablations,
        )
    except PolicyArtifactError as exc:
        raise ManifestCostProjectionError(str(exc)) from exc
    if (
        request.repeat_count > 1
        and repeat_sample_case_ids
        and any(
            provider_lane(model_key) == "openai" for model_key in requested_model_keys
        )
    ):
        raise ManifestCostProjectionError(
            "OpenAI repeat samples are not supported in one provider-cell shard; "
            "use repeat_count=1 until repeat fan-out and AWS-session coordination "
            "land."
        )

    include: list[dict[str, Any]] = []
    long_context_packets: list[dict[str, Any]] = []
    projected_cost = Decimal(0)
    seen_packet_rows: set[tuple[str, str]] = set()
    case_ids: list[str] = []
    seen_case_ids: set[str] = set()
    requested_ablation_set = set(requested_ablations)
    repeat_case_set = set(repeat_sample_case_ids)
    for raw_packet in packets:
        if not isinstance(raw_packet, dict):
            raise ManifestCostProjectionError("model_packets entries must be objects")
        packet = cast(dict[str, Any], raw_packet)
        ablation = packet.get("ablation", "full_packet")
        if ablation not in requested_ablation_set:
            continue
        if not isinstance(ablation, str):
            raise ManifestCostProjectionError("each matrix row requires ablation")
        case_id = packet.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ManifestCostProjectionError("each matrix row requires case_id")
        packet_row_key = (case_id, ablation)
        if packet_row_key in seen_packet_rows:
            raise ManifestCostProjectionError(
                f"duplicate packet row for ablation: {case_id}"
            )
        packet_object_key = (
            packet.get("packet_object_key")
            or packet.get("object_key")
            or packet.get("key")
        )
        if not isinstance(packet_object_key, str) or not packet_object_key.startswith(
            "model-packets/"
        ):
            raise ManifestCostProjectionError(
                "each matrix row requires model-packets/ packet_object_key"
            )
        packet_sha256 = _packet_sha256(packet)
        input_tokens = packet_input_tokens(packet)
        if input_tokens > LONG_CONTEXT_SURCHARGE_THRESHOLD_TOKENS:
            long_context_packets.append(
                {
                    "case_id": case_id,
                    "ablation": ablation,
                    "packet_object_key": packet_object_key,
                    "packet_sha256": packet_sha256,
                    "estimated_input_tokens": input_tokens,
                }
            )
        seen_packet_rows.add(packet_row_key)
        if case_id not in seen_case_ids:
            seen_case_ids.add(case_id)
            case_ids.append(case_id)
        row_repeat_count = request.repeat_count if case_id in repeat_case_set else 1
        for model_key in requested_model_keys:
            projected_cost += row_repeat_count * projected_cost_for_row(
                input_tokens=input_tokens,
                registry_record=registry_by_key[model_key],
            )
            include.append(
                {
                    "case_id": case_id,
                    "case_id_slug": safe_case_id_slug(case_id),
                    "ablation": ablation,
                    "packet_object_key": packet_object_key,
                    "packet_sha256": packet_sha256,
                    "model_key": model_key,
                    "model_key_slug": re.sub(r"[^A-Za-z0-9._-]+", "-", model_key).strip(
                        "-"
                    ),
                    "repeat_count": row_repeat_count,
                }
            )

    if not include:
        raise ManifestCostProjectionError("run-input manifest produced an empty matrix")
    if len(include) > request.matrix_limit:
        raise ManifestCostProjectionError(
            f"matrix has {len(include)} rows; GitHub limit is {request.matrix_limit}"
        )
    recommended_ceiling = projected_cost * 2
    requested_ceiling = _optional_ceiling(request.max_projected_model_cost_usd)
    if requested_ceiling is not None:
        if projected_cost > requested_ceiling:
            raise ManifestCostProjectionError(
                f"projected model cost ${projected_cost:.2f} exceeds budget "
                f"${requested_ceiling:.2f}"
            )
        if requested_ceiling > recommended_ceiling:
            raise ManifestCostProjectionError(
                f"budget ${requested_ceiling:.2f} exceeds the 2x projected "
                f"early-warning ceiling ${recommended_ceiling:.2f}"
            )

    provider_matrices: dict[str, dict[str, list[dict[str, Any]]]] = {}
    provider_counts: dict[str, int] = {}
    for provider in PROVIDER_LANES:
        rows = [
            row
            for row in include
            if provider_lane(cast(str, row["model_key"])) == provider
        ]
        provider_counts[provider] = len(rows)
        provider_matrices[provider] = {"include": rows}
    long_context_json = json.dumps(
        long_context_packets, ensure_ascii=False, separators=(",", ":")
    )
    receipt: dict[str, Any] = {
        "schema_version": str(MANIFEST_COST_PROJECTION_RECEIPT_V1),
        "cycle_id": request.cycle_id,
        "input_commitments": {
            "run_input_manifest": _raw_commitment(manifest_bytes),
            "model_registry": _raw_commitment(registry_bytes),
        },
        "requested_model_keys": requested_model_keys,
        "requested_ablations": requested_ablations,
        "case_ids": case_ids,
        "repeat_sample_case_ids": repeat_sample_case_ids,
        "repeat_count": request.repeat_count,
        "matrix_limit": request.matrix_limit,
        "max_projected_model_cost_usd": (
            request.max_projected_model_cost_usd.strip()
            if requested_ceiling is not None
            and request.max_projected_model_cost_usd is not None
            else None
        ),
        "matrix": {"include": include},
        "provider_counts": provider_counts,
        "provider_matrices": provider_matrices,
        "case_count": len(seen_packet_rows),
        "model_count": len(requested_model_keys),
        "long_context_surcharge_packet_count": len(long_context_packets),
        "long_context_surcharge_packets": long_context_packets,
        "long_context_surcharge_packets_json": long_context_json,
        "projected_model_cost_usd": _format_usd(projected_cost),
        "recommended_max_projected_model_cost_usd": _format_usd(recommended_ceiling),
        "provider_calls_made": 0,
        "aws_activity_executed": False,
        "packet_mutations_made": 0,
    }
    for provider in PROVIDER_LANES:
        receipt[f"{provider}_count"] = provider_counts[provider]
        receipt[f"{provider}_matrix"] = provider_matrices[provider]
    return receipt


def packet_input_tokens(packet: Mapping[str, Any]) -> int:
    """Return tokens using the frozen workflow field fallback order."""

    for field_name in (
        "estimated_input_tokens",
        "input_tokens",
        "prompt_tokens",
        "estimated_prompt_tokens",
        "packet_token_count",
        "token_count",
    ):
        value = packet.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    packet_size_bytes = packet.get("packet_size_bytes")
    if isinstance(packet_size_bytes, int) and packet_size_bytes >= 0:
        return math.ceil(packet_size_bytes / 4)
    raise ManifestCostProjectionError(
        "each matrix row requires packet token counts or packet_size_bytes "
        "for cost projection"
    )


def projected_cost_for_row(
    *, input_tokens: int, registry_record: Mapping[str, Any]
) -> Decimal:
    """Apply the frozen 1,000,000-token input-plus-max-output formula."""

    input_price = _required_nonnegative_decimal(registry_record, "input_token_price")
    output_price = _required_nonnegative_decimal(registry_record, "output_token_price")
    max_output_tokens = _required_nonnegative_int(registry_record, "max_output_tokens")
    return (
        Decimal(input_tokens) * input_price + Decimal(max_output_tokens) * output_price
    ) / PRICE_UNITS_PER_TOKEN


def provider_lane(model_key: str) -> str:
    """Map a registry key to the workflow provider lane."""

    provider = model_key.split(":", 1)[0]
    if provider in {"google", "gemini"}:
        return "gemini"
    if provider in {"openai", "anthropic"}:
        return provider
    raise ManifestCostProjectionError(f"unsupported model provider: {provider}")


def safe_case_id_slug(case_id: str) -> str:
    """Preserve the workflow case slug and collision-resistant suffix."""

    prefix = re.sub(r"[^A-Za-z0-9]+", "-", case_id).strip("-").lower()
    prefix = prefix[:48].rstrip("-") or "case"
    digest = hashlib.sha256(case_id.encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _registry_by_key(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ManifestCostProjectionError("model registry must contain a JSON array")
    registry_by_key: dict[str, dict[str, Any]] = {}
    for raw_record in cast(list[object], value):
        if not isinstance(raw_record, dict):
            raise ManifestCostProjectionError("model registry entries must be objects")
        record = cast(dict[str, Any], raw_record)
        provider = record.get("provider")
        model_id = record.get("model_id")
        if not isinstance(provider, str) or not isinstance(model_id, str):
            raise ManifestCostProjectionError(
                "model registry entries require provider and model_id"
            )
        registry_by_key[f"{provider}:{model_id}"] = record
    return registry_by_key


def _requested_values(
    values: tuple[str, ...], label: str, *, allow_empty: bool = False
) -> list[str]:
    normalized = [value.strip() for value in values if value.strip()]
    if not normalized and not allow_empty:
        noun = "provider:model_id key" if label == "model_keys" else "packet ablation"
        raise ManifestCostProjectionError(f"{label} must include at least one {noun}")
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise ManifestCostProjectionError(f"duplicate {label}: {duplicates}")
    return normalized


def _packet_sha256(packet: Mapping[str, Any]) -> str:
    sha256_value = packet.get("sha256")
    packet_sha256_value = packet.get("packet_sha256")
    for field_name, value in (
        ("sha256", sha256_value),
        ("packet_sha256", packet_sha256_value),
    ):
        if value is not None and (
            not isinstance(value, str) or _SHA256.fullmatch(value) is None
        ):
            raise ManifestCostProjectionError(
                f"each matrix row {field_name} must be a lowercase SHA-256"
            )
    if sha256_value is None and packet_sha256_value is None:
        raise ManifestCostProjectionError(
            "each matrix row requires sha256 or packet_sha256"
        )
    if (
        sha256_value is not None
        and packet_sha256_value is not None
        and sha256_value != packet_sha256_value
    ):
        raise ManifestCostProjectionError(
            "matrix row has conflicting sha256 and packet_sha256"
        )
    return cast(str, sha256_value or packet_sha256_value)


def _required_nonnegative_decimal(
    record: Mapping[str, Any], field_name: str
) -> Decimal:
    value = record.get(field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ManifestCostProjectionError(
            f"model registry {field_name} must be non-negative"
        )
    decimal = Decimal(str(value))
    if not decimal.is_finite() or decimal < 0:
        raise ManifestCostProjectionError(
            f"model registry {field_name} must be non-negative"
        )
    return decimal


def _required_nonnegative_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ManifestCostProjectionError(
            f"model registry {field_name} must be a non-negative integer"
        )
    return value


def _optional_ceiling(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    text = raw.strip()
    if _USD.fullmatch(text) is None:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        )
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        ) from exc
    if not value.is_finite() or value < 0:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        )
    return value


def _format_usd(value: Decimal) -> str:
    return format(value.quantize(_SIX_PLACES), "f")


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


def _read_regular(path: Path, label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ManifestCostProjectionError(f"{label} is unreadable: {path}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ManifestCostProjectionError(f"{label} is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _require_inputs_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if _read_regular(path, "cost projection source recheck") != expected:
            raise ManifestCostProjectionError(f"input changed during issuance: {path}")


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise ManifestCostProjectionError(
            f"cannot create cost projection receipt: {path}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)

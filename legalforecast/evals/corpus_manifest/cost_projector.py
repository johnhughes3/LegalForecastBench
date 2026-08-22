"""Provider-free official manifest cost projection and receipt issuance."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, cast

from legalforecast.contracts.schemas import MANIFEST_COST_PROJECTION_RECEIPT_V1
from legalforecast.evals.corpus_manifest.cost_projector_contract import (
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    packet_object_key_from_row,
    packet_sha256_from_row,
    required_nonnegative_int,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.protocol.manifest import hash_payload
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    require_repeat_case_coverage,
)

if TYPE_CHECKING:
    from legalforecast.evals.corpus_manifest.cost_projector_auth import (
        AuthenticatedManifestCostInputs,
    )

PRICE_UNITS_PER_TOKEN: Final = 1_000_000
LONG_CONTEXT_SURCHARGE_THRESHOLD_TOKENS: Final = 272_000
SUPPORTED_ABLATIONS: Final = frozenset(
    "full_packet metadata_only briefs_only_redacted judge_removed no_briefs".split()
)
PROVIDER_LANES: Final = ("openai", "anthropic", "gemini")
_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")


def issue_manifest_cost_projection(
    request: ManifestCostProjectionRequest,
) -> dict[str, Any]:
    """Project exact workflow costs and create-only publish a canonical receipt."""

    from legalforecast.evals.corpus_manifest.cost_projector_auth import (
        require_inputs_unchanged,
    )
    from legalforecast.evals.corpus_manifest.cost_projector_io import (
        verify_receipt_self_hash,
        write_create_only,
    )

    authenticated = authenticate_manifest_cost_inputs(request)
    receipt = build_manifest_cost_projection(request, authenticated=authenticated)
    verify_receipt_self_hash(receipt, error_type=ManifestCostProjectionError)
    payload = canonical_json_bytes(
        receipt,
        error_type=ManifestCostProjectionError,
        error_message="manifest cost projection receipt is not canonical JSON",
    )
    require_inputs_unchanged(authenticated.snapshots)
    write_create_only(request.output, payload, error_type=ManifestCostProjectionError)
    return receipt


def authenticate_manifest_cost_inputs(
    request: ManifestCostProjectionRequest,
) -> AuthenticatedManifestCostInputs:
    """Authenticate the complete issued freeze and every manifest packet byte."""

    from legalforecast.evals.corpus_manifest.cost_projector_auth import (
        authenticate_manifest_cost_inputs as authenticate,
    )

    return authenticate(request)


def build_manifest_cost_projection(
    request: ManifestCostProjectionRequest,
    *,
    authenticated: AuthenticatedManifestCostInputs,
) -> dict[str, Any]:
    """Build one receipt from a fully authenticated manifest forecast."""

    manifest_record = authenticated.run_inputs
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
    registry_by_key = _registry_by_key(authenticated.registry_records)
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
    projected_cost = 0.0
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
        packet_object_key = packet_object_key_from_row(packet)
        packet_sha256 = packet_sha256_from_row(packet)
        packet_payload = authenticated.packet_payloads.get(packet_object_key)
        if packet_payload is None:
            raise ManifestCostProjectionError(
                f"authenticated packet bytes are missing: {packet_object_key}"
            )
        input_tokens = packet_input_tokens(
            packet, authenticated_packet_size=len(packet_payload)
        )
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
        "input_commitments": dict(authenticated.input_commitments),
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
    receipt["receipt_sha256"] = hash_payload(receipt)
    return receipt


def packet_input_tokens(
    packet: Mapping[str, Any], *, authenticated_packet_size: int | None = None
) -> int:
    """Return tokens using the frozen workflow field fallback order."""

    token_fields = (
        "estimated_input_tokens input_tokens prompt_tokens "
        "estimated_prompt_tokens packet_token_count token_count"
    )
    for field_name in token_fields.split():
        value = packet.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    packet_size_bytes = packet.get("packet_size_bytes")
    if isinstance(packet_size_bytes, int) and packet_size_bytes >= 0:
        if (
            authenticated_packet_size is not None
            and packet_size_bytes != authenticated_packet_size
        ):
            raise ManifestCostProjectionError(
                "packet_size_bytes differs from authenticated packet bytes"
            )
        return math.ceil(packet_size_bytes / 4)
    if authenticated_packet_size is not None:
        return math.ceil(authenticated_packet_size / 4)
    raise ManifestCostProjectionError(
        "each matrix row requires packet token counts or packet_size_bytes "
        "for cost projection"
    )


def projected_cost_for_row(
    *, input_tokens: int, registry_record: Mapping[str, Any]
) -> float:
    """Apply the frozen 1,000,000-token input-plus-max-output formula."""

    input_price = _required_nonnegative_float(registry_record, "input_token_price")
    output_price = _required_nonnegative_float(registry_record, "output_token_price")
    max_output_tokens = required_nonnegative_int(registry_record, "max_output_tokens")
    return (
        input_tokens * input_price + max_output_tokens * output_price
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


def _required_nonnegative_float(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ManifestCostProjectionError(
            f"model registry {field_name} must be non-negative"
        )
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ManifestCostProjectionError(
            f"model registry {field_name} must be non-negative"
        )
    return number


def _optional_ceiling(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if _USD.fullmatch(text) is None:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        )
    try:
        value = float(text)
    except ValueError as exc:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        ) from exc
    if not math.isfinite(value) or value < 0:
        raise ManifestCostProjectionError(
            "max_projected_model_cost_usd must be a non-negative decimal amount"
        )
    return value


def _format_usd(value: float) -> str:
    return f"{value:.6f}"

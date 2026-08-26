"""Provider-free official manifest cost projection and receipt issuance."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Set
from decimal import Decimal, InvalidOperation
from pathlib import Path
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
AUTHENTICATED_MANIFEST_ABLATIONS: Final = frozenset({"full_packet", "metadata_only"})
_OFFICIAL_ABLATIONS: Final = ("full_packet", "metadata_only")
PROVIDER_LANES: Final = ("openai", "anthropic", "gemini")
OFFICIAL_CASE_COUNT: Final = 100
OFFICIAL_CALL_COUNT: Final = 200
_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_USD_SIX: Final = re.compile(r"[0-9]+\.[0-9]{6}\Z")
_COST_RECEIPT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "cycle_id",
        "input_commitments",
        "requested_model_keys",
        "requested_ablations",
        "case_ids",
        "repeat_sample_case_ids",
        "repeat_count",
        "matrix_limit",
        "shard_only",
        "max_projected_model_cost_usd",
        "matrix",
        "provider_counts",
        "provider_matrices",
        "case_count",
        "packet_count",
        "cell_count",
        "matrix_row_count",
        "shard_matrix_row_count",
        "request_count",
        "attempt_count",
        "model_count",
        "long_context_surcharge_packet_count",
        "long_context_surcharge_packets",
        "long_context_surcharge_packets_json",
        "projected_model_cost_usd",
        "recommended_max_projected_model_cost_usd",
        "provider_calls_made",
        "aws_activity_executed",
        "packet_mutations_made",
        "openai_count",
        "openai_matrix",
        "anthropic_count",
        "anthropic_matrix",
        "gemini_count",
        "gemini_matrix",
        "receipt_sha256",
    }
)
_COST_MATRIX_ROW_FIELDS: Final = frozenset(
    {
        "case_id",
        "case_id_slug",
        "ablation",
        "packet_object_key",
        "packet_sha256",
        "model_key",
        "model_key_slug",
        "repeat_count",
    }
)
_COST_INPUT_COMMITMENT_FIELDS: Final = frozenset(
    {
        "freeze_bundle",
        "freeze_amendment_bundles",
        "owner_manifest",
        "manifest_run_record",
        "run_input_manifest",
        "model_registry",
        "prompt_contract",
        "packets",
    }
)
_COST_RAW_COMMITMENT_FIELDS: Final = frozenset({"sha256", "size_bytes"})
_COST_PACKET_COMMITMENT_FIELDS: Final = frozenset(
    {"packet_object_key", "sha256", "size_bytes", "input_tokens"}
)
_LEGACY_COST_PACKET_COMMITMENT_FIELDS: Final = frozenset(
    {"packet_object_key", "sha256", "size_bytes"}
)
_COST_WARNING_FIELDS: Final = frozenset(
    {
        "case_id",
        "ablation",
        "packet_object_key",
        "packet_sha256",
        "estimated_input_tokens",
    }
)


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

    def verify_sources() -> None:
        require_inputs_unchanged(authenticated.snapshots)

    write_create_only(
        request.output,
        payload,
        error_type=ManifestCostProjectionError,
        before_commit=verify_sources,
        after_commit=verify_sources,
    )
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
    unsupported_ablations = sorted(
        set(requested_ablations) - AUTHENTICATED_MANIFEST_ABLATIONS
    )
    if unsupported_ablations:
        raise ManifestCostProjectionError(
            f"unsupported ablations: {unsupported_ablations}"
        )
    if request.shard_only and (
        len(requested_model_keys) != 1 or len(requested_ablations) != 1
    ):
        raise ManifestCostProjectionError(
            "shard-only projection requires exactly one model-key/ablation pair"
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
    attempt_count = 0
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
        if not isinstance(ablation, str):
            raise ManifestCostProjectionError("each matrix row requires ablation")
        if ablation not in AUTHENTICATED_MANIFEST_ABLATIONS:
            raise ManifestCostProjectionError(
                f"authenticated packet row has unexpected ablation: {ablation}"
            )
        case_id = packet.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ManifestCostProjectionError("each matrix row requires case_id")
        if case_id not in seen_case_ids:
            seen_case_ids.add(case_id)
            case_ids.append(case_id)
        if ablation not in requested_ablation_set:
            continue
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
        row_repeat_count = request.repeat_count if case_id in repeat_case_set else 1
        for model_key in requested_model_keys:
            attempt_count += row_repeat_count
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
    expected_packet_rows = len(seen_case_ids) * len(requested_ablations)
    if len(seen_packet_rows) != expected_packet_rows:
        raise ManifestCostProjectionError(
            "requested packet matrix is incomplete for the authenticated case set"
        )
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
        long_context_packets, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    cell_count = len(requested_model_keys) * len(requested_ablations)
    shard_matrix_row_count = max(
        sum(
            row["model_key"] == model_key and row["ablation"] == ablation
            for row in include
        )
        for model_key in requested_model_keys
        for ablation in requested_ablations
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
        "shard_only": request.shard_only,
        "max_projected_model_cost_usd": (
            request.max_projected_model_cost_usd.strip()
            if requested_ceiling is not None
            and request.max_projected_model_cost_usd is not None
            else None
        ),
        "matrix": {"include": include},
        "provider_counts": provider_counts,
        "provider_matrices": provider_matrices,
        "case_count": len(seen_case_ids),
        "packet_count": len(packets),
        "cell_count": cell_count,
        "matrix_row_count": len(include),
        "shard_matrix_row_count": shard_matrix_row_count,
        "request_count": len(include),
        "attempt_count": attempt_count,
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


def verify_manifest_cost_projection_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_cycle_id: str,
    expected_model_key: str,
    expected_common_frozen_inputs: Mapping[str, Any],
    expected_registry_entry: Mapping[str, Any],
    run_input_manifest: Path | bytes | None = None,
) -> str:
    """Verify one exact-model receipt emitted by the canonical cost projector.

    When ``run_input_manifest`` is supplied, the verifier is in strict scope
    mode: it authenticates the exact frozen run-input bytes and derives every
    packet's token basis from its ``packet_size_bytes`` row.  Omitting the
    source retains the standalone compatibility path for callers that cannot
    reach execution-scope authority.
    """

    record = dict(receipt)
    _cost_exact_keys(record, _COST_RECEIPT_FIELDS, "cost projection receipt")
    if record.get("schema_version") != str(MANIFEST_COST_PROJECTION_RECEIPT_V1):
        raise ManifestCostProjectionError(
            "unsupported manifest cost projection receipt schema"
        )
    supplied = _cost_sha(record.get("receipt_sha256"), "receipt_sha256")
    without_hash = dict(record)
    without_hash.pop("receipt_sha256")
    if hash_payload(without_hash) != supplied:
        raise ManifestCostProjectionError(
            "cost projection receipt hash does not match bytes"
        )
    cycle_id = _cost_text(expected_cycle_id, "expected cycle_id")
    if record.get("cycle_id") != cycle_id:
        raise ManifestCostProjectionError(
            "cost projection receipt cycle_id does not match common plan"
        )
    model_key = _cost_text(expected_model_key, "expected model_key")
    if record.get("requested_model_keys") != [model_key]:
        raise ManifestCostProjectionError(
            "cost receipt is not the exact selected-model projection"
        )
    if record.get("requested_ablations") != list(_OFFICIAL_ABLATIONS):
        raise ManifestCostProjectionError(
            "cost receipt is not the exact two-ablation projection"
        )
    if record.get("repeat_sample_case_ids") != [] or record.get("repeat_count") != 1:
        raise ManifestCostProjectionError(
            "cost receipt repeat policy must be the unexpanded official matrix"
        )
    if record.get("shard_only") is not False:
        raise ManifestCostProjectionError(
            "scope cost receipt must be the two-cell aggregate projection"
        )

    case_ids = _cost_string_list(record.get("case_ids"), "case_ids")
    if len(case_ids) != OFFICIAL_CASE_COUNT or len(set(case_ids)) != len(case_ids):
        raise ManifestCostProjectionError(
            "cost receipt must contain exactly 100 unique case IDs"
        )
    if (
        record.get("case_count") != OFFICIAL_CASE_COUNT
        or record.get("packet_count") != OFFICIAL_CALL_COUNT
        or record.get("request_count") != OFFICIAL_CALL_COUNT
        or record.get("attempt_count") != OFFICIAL_CALL_COUNT
        or record.get("cell_count") != 2
        or record.get("matrix_row_count") != OFFICIAL_CALL_COUNT
        or record.get("shard_matrix_row_count") != OFFICIAL_CASE_COUNT
        or record.get("model_count") != 1
    ):
        raise ManifestCostProjectionError(
            "cost receipt must cover exactly 100 cases, 200 calls, and two cells"
        )
    matrix_limit = _cost_nonnegative_int(record.get("matrix_limit"), "matrix_limit")
    if matrix_limit < OFFICIAL_CALL_COUNT:
        raise ManifestCostProjectionError(
            "cost receipt matrix_limit is below the two-cell matrix"
        )

    input_commitments = _cost_mapping(
        record.get("input_commitments"), "input_commitments"
    )
    _cost_exact_keys(
        input_commitments, _COST_INPUT_COMMITMENT_FIELDS, "input_commitments"
    )
    common_commitment_fields = {
        "freeze_bundle": "freeze_bundle_sha256",
        "owner_manifest": "manifest_sha256",
        "run_input_manifest": "run_input_manifest_sha256",
        "model_registry": "model_registry_sha256",
    }
    for commitment_name, common_name in common_commitment_fields.items():
        commitment = _cost_raw_commitment(
            input_commitments.get(commitment_name),
            f"input_commitments.{commitment_name}",
        )
        expected = _cost_sha(
            expected_common_frozen_inputs.get(common_name),
            f"common_frozen_inputs.{common_name}",
        )
        if commitment["sha256"] != expected:
            raise ManifestCostProjectionError(
                f"input_commitments.{commitment_name} does not match common plan"
            )
    amendment_bundles = input_commitments.get("freeze_amendment_bundles")
    if not isinstance(amendment_bundles, list):
        raise ManifestCostProjectionError(
            "input_commitments.freeze_amendment_bundles must be an array"
        )
    for index, commitment in enumerate(cast(list[object], amendment_bundles)):
        _cost_raw_commitment(
            commitment, f"input_commitments.freeze_amendment_bundles[{index}]"
        )
    for name in ("manifest_run_record", "prompt_contract"):
        _cost_raw_commitment(input_commitments.get(name), f"input_commitments.{name}")

    authenticated_packet_rows = None
    if run_input_manifest is not None:
        authenticated_packet_rows = _authenticated_run_input_packet_rows(
            run_input_manifest,
            expected_cycle_id=cycle_id,
            expected_sha256=expected_common_frozen_inputs.get(
                "run_input_manifest_sha256"
            ),
        )

    raw_packet_commitments = input_commitments.get("packets")
    if not isinstance(raw_packet_commitments, list):
        raise ManifestCostProjectionError("input_commitments.packets must be an array")
    packet_commitments: dict[str, Mapping[str, Any]] = {}
    authenticated_token_basis: bool | None = None
    for index, raw_commitment in enumerate(cast(list[object], raw_packet_commitments)):
        commitment = _cost_mapping(
            raw_commitment, f"input_commitments.packets[{index}]"
        )
        commitment_fields = set(commitment)
        if authenticated_packet_rows is not None:
            _cost_exact_keys(
                commitment,
                _COST_PACKET_COMMITMENT_FIELDS,
                f"input_commitments.packets[{index}]",
            )
            has_token_basis = True
        elif commitment_fields == set(_LEGACY_COST_PACKET_COMMITMENT_FIELDS):
            # Keep receipts issued before the token-basis extension readable
            # for standalone consumers.  Scope authority always supplies the
            # run-input source and takes the strict path above.
            has_token_basis = False
        elif commitment_fields != set(_COST_PACKET_COMMITMENT_FIELDS):
            _cost_exact_keys(
                commitment,
                _COST_PACKET_COMMITMENT_FIELDS,
                f"input_commitments.packets[{index}]",
            )
            has_token_basis = True
        else:
            has_token_basis = True
        if (
            authenticated_token_basis is not None
            and authenticated_token_basis != has_token_basis
        ):
            raise ManifestCostProjectionError(
                "input_commitments.packets must use one token-basis format"
            )
        authenticated_token_basis = has_token_basis
        key = _cost_packet_key(
            commitment.get("packet_object_key"),
            f"input_commitments.packets[{index}].packet_object_key",
        )
        if key in packet_commitments:
            raise ManifestCostProjectionError(
                f"input_commitments.packets contains duplicate key: {key}"
            )
        _cost_sha(
            commitment.get("sha256"), f"input_commitments.packets[{index}].sha256"
        )
        _cost_nonnegative_int(
            commitment.get("size_bytes"),
            f"input_commitments.packets[{index}].size_bytes",
        )
        if authenticated_token_basis:
            _cost_nonnegative_int(
                commitment.get("input_tokens"),
                f"input_commitments.packets[{index}].input_tokens",
            )
        if authenticated_packet_rows is not None:
            authenticated_row = authenticated_packet_rows.get(key)
            if authenticated_row is None:
                raise ManifestCostProjectionError(
                    "cost receipt packet commitment is not present in the "
                    f"authenticated run-input manifest: {key}"
                )
            if (
                commitment.get("sha256") != authenticated_row["packet_sha256"]
                or commitment.get("size_bytes")
                != authenticated_row["packet_size_bytes"]
                or commitment.get("input_tokens") != authenticated_row["input_tokens"]
            ):
                raise ManifestCostProjectionError(
                    "cost receipt packet commitment differs from authenticated "
                    f"run-input row: {key}"
                )
        packet_commitments[key] = commitment
    if len(packet_commitments) != OFFICIAL_CALL_COUNT:
        raise ManifestCostProjectionError(
            "input_commitments.packets must contain exactly 200 packets"
        )
    if authenticated_packet_rows is not None and set(packet_commitments) != set(
        authenticated_packet_rows
    ):
        raise ManifestCostProjectionError(
            "cost receipt packets do not cover the authenticated run-input matrix"
        )

    matrix = _cost_mapping(record.get("matrix"), "matrix")
    _cost_exact_keys(matrix, {"include"}, "matrix")
    raw_rows = matrix.get("include")
    if not isinstance(raw_rows, list):
        raise ManifestCostProjectionError("matrix.include must be an array")
    rows = cast(list[object], raw_rows)
    if len(rows) != OFFICIAL_CALL_COUNT:
        raise ManifestCostProjectionError(
            "cost receipt matrix must contain exactly 200 rows"
        )
    expected_pairs = {
        (case_id, ablation) for case_id in case_ids for ablation in _OFFICIAL_ABLATIONS
    }
    matrix_rows: list[Mapping[str, Any]] = []
    observed_pairs: set[tuple[str, str]] = set()
    observed_packet_keys: set[str] = set()
    recomputed_cost = 0.0
    for index, raw_row in enumerate(rows):
        row = _cost_mapping(raw_row, f"matrix.include[{index}]")
        _cost_exact_keys(row, _COST_MATRIX_ROW_FIELDS, f"matrix.include[{index}]")
        row_case_id = _cost_text(row.get("case_id"), "matrix row case_id")
        row_ablation = _cost_text(row.get("ablation"), "matrix row ablation")
        pair = (row_case_id, row_ablation)
        if pair in observed_pairs:
            raise ManifestCostProjectionError(
                f"cost receipt matrix contains duplicate row: {pair}"
            )
        if pair not in expected_pairs:
            raise ManifestCostProjectionError(
                f"cost receipt matrix contains undeclared row: {pair}"
            )
        observed_pairs.add(pair)
        if row.get("model_key") != model_key:
            raise ManifestCostProjectionError(
                "cost receipt matrix row model_key differs from selected model"
            )
        if row.get("case_id_slug") != safe_case_id_slug(row_case_id):
            raise ManifestCostProjectionError(
                "cost receipt matrix case_id_slug does not match case_id"
            )
        expected_model_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", model_key).strip("-")
        if row.get("model_key_slug") != expected_model_slug:
            raise ManifestCostProjectionError(
                "cost receipt matrix model_key_slug does not match model_key"
            )
        packet_key = _cost_packet_key(row.get("packet_object_key"), "matrix packet key")
        if packet_key in observed_packet_keys:
            raise ManifestCostProjectionError(
                f"cost receipt matrix reuses packet: {packet_key}"
            )
        observed_packet_keys.add(packet_key)
        packet_sha = _cost_sha(row.get("packet_sha256"), "matrix packet_sha256")
        commitment = packet_commitments.get(packet_key)
        if commitment is None or commitment.get("sha256") != packet_sha:
            raise ManifestCostProjectionError(
                "cost receipt matrix packet commitment is not authenticated: "
                f"{packet_key}"
            )
        if authenticated_packet_rows is not None:
            authenticated_row = authenticated_packet_rows[packet_key]
            if (
                row_case_id != authenticated_row["case_id"]
                or row_ablation != authenticated_row["ablation"]
                or packet_sha != authenticated_row["packet_sha256"]
                or commitment.get("size_bytes")
                != authenticated_row["packet_size_bytes"]
            ):
                raise ManifestCostProjectionError(
                    "cost receipt matrix packet differs from authenticated "
                    f"run-input row: {packet_key}"
                )
        if row.get("repeat_count") != 1:
            raise ManifestCostProjectionError(
                "cost receipt matrix repeat_count must be one"
            )
        if authenticated_packet_rows is not None:
            input_tokens = authenticated_packet_rows[packet_key]["input_tokens"]
            recomputed_cost += projected_cost_for_row(
                input_tokens=input_tokens,
                registry_record=expected_registry_entry,
            )
        elif authenticated_token_basis:
            input_tokens = _cost_nonnegative_int(
                packet_commitments[packet_key].get("input_tokens"),
                f"input_commitments.packets[{packet_key}].input_tokens",
            )
            recomputed_cost += projected_cost_for_row(
                input_tokens=input_tokens,
                registry_record=expected_registry_entry,
            )
        matrix_rows.append(row)
    if observed_pairs != expected_pairs or observed_packet_keys != set(
        packet_commitments
    ):
        raise ManifestCostProjectionError(
            "cost receipt matrix does not cover the authenticated packet matrix"
        )

    registry_provider = _cost_text(
        expected_registry_entry.get("provider"), "selected registry provider"
    )
    registry_model_id = _cost_text(
        expected_registry_entry.get("model_id"), "selected registry model_id"
    )
    if model_key != f"{registry_provider}:{registry_model_id}":
        raise ManifestCostProjectionError(
            "cost receipt selected model differs from registry entry"
        )
    selected_provider = provider_lane(model_key)
    provider_counts = _cost_mapping(record.get("provider_counts"), "provider_counts")
    _cost_exact_keys(provider_counts, set(PROVIDER_LANES), "provider_counts")
    provider_matrices = _cost_mapping(
        record.get("provider_matrices"), "provider_matrices"
    )
    _cost_exact_keys(provider_matrices, set(PROVIDER_LANES), "provider_matrices")
    for provider in PROVIDER_LANES:
        expected_rows = matrix_rows if provider == selected_provider else []
        if record.get(f"{provider}_count") != len(expected_rows):
            raise ManifestCostProjectionError(
                f"{provider} count does not match selected model matrix"
            )
        if provider_counts.get(provider) != len(expected_rows):
            raise ManifestCostProjectionError(
                f"provider_counts.{provider} does not match selected model matrix"
            )
        provider_matrix = _cost_mapping(
            provider_matrices.get(provider), f"provider_matrices.{provider}"
        )
        _cost_exact_keys(provider_matrix, {"include"}, f"provider_matrices.{provider}")
        if provider_matrix.get("include") != expected_rows:
            raise ManifestCostProjectionError(
                f"provider_matrices.{provider} differs from the full matrix"
            )
        if record.get(f"{provider}_matrix") != provider_matrix:
            raise ManifestCostProjectionError(
                f"{provider}_matrix differs from provider_matrices.{provider}"
            )

    warnings = record.get("long_context_surcharge_packets")
    if not isinstance(warnings, list):
        raise ManifestCostProjectionError(
            "long_context_surcharge_packets must be an array"
        )
    warning_rows = cast(list[object], warnings)
    if record.get("long_context_surcharge_packet_count") != len(warning_rows):
        raise ManifestCostProjectionError(
            "long_context_surcharge_packet_count does not match warning rows"
        )
    if record.get("long_context_surcharge_packets_json") != json.dumps(
        warnings, ensure_ascii=False, separators=(",", ":")
    ):
        raise ManifestCostProjectionError(
            "long_context_surcharge_packets_json does not match warning rows"
        )
    for index, raw_warning in enumerate(warning_rows):
        warning = _cost_mapping(raw_warning, f"long_context warning[{index}]")
        _cost_exact_keys(
            warning, _COST_WARNING_FIELDS, f"long_context warning[{index}]"
        )
        warning_pair = (
            _cost_text(warning.get("case_id"), "long_context warning case_id"),
            _cost_text(warning.get("ablation"), "long_context warning ablation"),
        )
        warning_key = _cost_packet_key(
            warning.get("packet_object_key"), "long_context warning packet key"
        )
        if (
            warning_pair not in observed_pairs
            or warning_key not in observed_packet_keys
        ):
            raise ManifestCostProjectionError(
                "long_context warning is not part of the authenticated matrix"
            )
        if _cost_sha(
            warning.get("packet_sha256"), "long_context warning packet_sha256"
        ) != packet_commitments[warning_key].get("sha256"):
            raise ManifestCostProjectionError(
                "long_context warning packet commitment differs from matrix"
            )
        warning_tokens = _cost_nonnegative_int(
            warning.get("estimated_input_tokens"),
            "long_context warning estimated_input_tokens",
        )
        expected_warning_tokens = (
            authenticated_packet_rows[warning_key]["input_tokens"]
            if authenticated_packet_rows is not None
            else packet_commitments[warning_key].get("input_tokens")
        )
        if authenticated_token_basis and warning_tokens != expected_warning_tokens:
            raise ManifestCostProjectionError(
                "long_context warning token basis differs from packet commitment"
            )
    if authenticated_token_basis:
        expected_warning_keys = {
            (cast(str, row["case_id"]), cast(str, row["ablation"]))
            for row in matrix_rows
            if (
                authenticated_packet_rows[cast(str, row["packet_object_key"])][
                    "input_tokens"
                ]
                if authenticated_packet_rows is not None
                else _cost_nonnegative_int(
                    packet_commitments[cast(str, row["packet_object_key"])].get(
                        "input_tokens"
                    ),
                    "matrix packet input_tokens",
                )
            )
            > LONG_CONTEXT_SURCHARGE_THRESHOLD_TOKENS
        }
        observed_warning_keys = {
            (
                _cost_text(
                    _cost_mapping(raw, "long_context warning").get("case_id"),
                    "long_context warning case_id",
                ),
                _cost_text(
                    _cost_mapping(raw, "long_context warning").get("ablation"),
                    "long_context warning ablation",
                ),
            )
            for raw in warning_rows
        }
        if observed_warning_keys != expected_warning_keys:
            raise ManifestCostProjectionError(
                "long_context warning rows do not match authenticated token basis"
            )

    expected_projected = _format_usd(recomputed_cost)
    expected_recommended = _format_usd(recomputed_cost * 2)

    projected = _cost_money(
        record.get("projected_model_cost_usd"), "projected_model_cost_usd"
    )
    recommended = _cost_money(
        record.get("recommended_max_projected_model_cost_usd"),
        "recommended_max_projected_model_cost_usd",
    )
    if recommended < projected:
        raise ManifestCostProjectionError(
            "recommended cost ceiling is below projected model cost"
        )
    if (
        authenticated_token_basis
        and record.get("projected_model_cost_usd") != expected_projected
    ):
        raise ManifestCostProjectionError(
            "projected_model_cost_usd does not match authenticated pricing projection"
        )
    if (
        authenticated_token_basis
        and record.get("recommended_max_projected_model_cost_usd")
        != expected_recommended
    ):
        raise ManifestCostProjectionError(
            "recommended_max_projected_model_cost_usd does not match the 2x "
            "authenticated pricing projection"
        )
    requested_ceiling = record.get("max_projected_model_cost_usd")
    if requested_ceiling is not None:
        ceiling = _cost_money(requested_ceiling, "max_projected_model_cost_usd")
        if ceiling < projected:
            raise ManifestCostProjectionError(
                "requested cost ceiling is below projected model cost"
            )
    if record.get("provider_calls_made") != 0:
        raise ManifestCostProjectionError("cost receipt records provider activity")
    if record.get("aws_activity_executed") is not False:
        raise ManifestCostProjectionError("cost receipt records AWS activity")
    if record.get("packet_mutations_made") != 0:
        raise ManifestCostProjectionError("cost receipt records packet mutation")
    return supplied


def _authenticated_run_input_packet_rows(
    source: object,
    *,
    expected_cycle_id: str,
    expected_sha256: object,
) -> dict[str, dict[str, Any]]:
    """Load packet identities and token bases from one frozen run-input source."""

    if isinstance(source, Path):
        try:
            payload = source.read_bytes()
        except OSError as exc:
            raise ManifestCostProjectionError(
                f"cannot read run-input manifest: {source}"
            ) from exc
    elif isinstance(source, bytes):
        payload = source
    else:
        raise ManifestCostProjectionError(
            "run-input manifest must be a path or exact bytes"
        )
    expected = _cost_sha(
        expected_sha256, "common_frozen_inputs.run_input_manifest_sha256"
    )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ManifestCostProjectionError(
            "run-input manifest bytes do not match common frozen input hash"
        )
    try:
        decoded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestCostProjectionError(
            "authenticated run-input manifest is not valid JSON"
        ) from exc
    manifest = _cost_mapping(decoded, "authenticated run-input manifest")
    if manifest.get("cycle_id") != expected_cycle_id:
        raise ManifestCostProjectionError(
            "authenticated run-input manifest cycle_id does not match scope"
        )
    raw_packets = manifest.get("model_packets")
    if not isinstance(raw_packets, list):
        raise ManifestCostProjectionError(
            "authenticated run-input manifest must contain exactly 200 model_packets"
        )
    packets = cast(list[object], raw_packets)
    if len(packets) != OFFICIAL_CALL_COUNT:
        raise ManifestCostProjectionError(
            "authenticated run-input manifest must contain exactly 200 model_packets"
        )
    packet_rows: dict[str, dict[str, Any]] = {}
    for index, raw_packet in enumerate(packets):
        packet = _cost_mapping(raw_packet, f"authenticated model_packets[{index}]")
        key = _cost_packet_key(
            packet.get("packet_object_key"),
            f"authenticated model_packets[{index}].packet_object_key",
        )
        if key in packet_rows:
            raise ManifestCostProjectionError(
                f"authenticated run-input manifest contains duplicate packet: {key}"
            )
        packet_sha = packet_sha256_from_row(packet)
        packet_size = _cost_nonnegative_int(
            packet.get("packet_size_bytes"),
            f"authenticated model_packets[{index}].packet_size_bytes",
        )
        packet_rows[key] = {
            "packet_object_key": key,
            "packet_sha256": packet_sha,
            "packet_size_bytes": packet_size,
            "input_tokens": math.ceil(packet_size / 4),
            "case_id": _cost_text(
                packet.get("case_id"),
                f"authenticated model_packets[{index}].case_id",
            ),
            "ablation": _cost_text(
                packet.get("ablation"),
                f"authenticated model_packets[{index}].ablation",
            ),
        }
    return packet_rows


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
    """Apply frozen pricing, including any registry long-context surcharge."""

    input_price = _required_nonnegative_float(registry_record, "input_token_price")
    output_price = _required_nonnegative_float(registry_record, "output_token_price")
    max_output_tokens = required_nonnegative_int(registry_record, "max_output_tokens")
    surcharge = registry_record.get("long_context_surcharge")
    if surcharge is not None:
        if not isinstance(surcharge, Mapping):
            raise ManifestCostProjectionError(
                "model registry long_context_surcharge must be an object"
            )
        surcharge_record = cast(Mapping[str, Any], surcharge)
        threshold = required_nonnegative_int(
            surcharge_record,
            "threshold_input_tokens",
            label="model registry long_context_surcharge",
        )
        input_multiplier = _required_nonnegative_float(
            surcharge_record, "input_price_multiplier"
        )
        output_multiplier = _required_nonnegative_float(
            surcharge_record, "output_price_multiplier"
        )
        if threshold < 1 or input_multiplier < 1 or output_multiplier < 1:
            raise ManifestCostProjectionError(
                "model registry long_context_surcharge fields must be positive"
            )
        if input_tokens > threshold:
            input_price *= input_multiplier
            output_price *= output_multiplier
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


def _cost_exact_keys(value: Mapping[str, Any], expected: Set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ManifestCostProjectionError(
            f"{label} fields mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _cost_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestCostProjectionError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _cost_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestCostProjectionError(f"{label} must be a non-empty string")
    return value.strip()


def _cost_sha(value: object, label: str) -> str:
    text = _cost_text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ManifestCostProjectionError(f"{label} must be a lowercase SHA-256")
    return text


def _cost_nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ManifestCostProjectionError(f"{label} must be a non-negative integer")
    return value


def _cost_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ManifestCostProjectionError(f"{label} must be an array")
    result: list[str] = []
    for index, item in enumerate(cast(list[object], value)):
        result.append(_cost_text(item, f"{label}[{index}]"))
    return result


def _cost_raw_commitment(value: object, label: str) -> Mapping[str, Any]:
    commitment = _cost_mapping(value, label)
    _cost_exact_keys(commitment, _COST_RAW_COMMITMENT_FIELDS, label)
    _cost_sha(commitment.get("sha256"), f"{label}.sha256")
    _cost_nonnegative_int(commitment.get("size_bytes"), f"{label}.size_bytes")
    return commitment


def _cost_packet_key(value: object, label: str) -> str:
    key = _cost_text(value, label)
    if not key.startswith("model-packets/"):
        raise ManifestCostProjectionError(f"{label} must use the model-packets/ prefix")
    parts = Path(key).parts
    if Path(key).is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ManifestCostProjectionError(f"{label} is not a safe relative path")
    return key


def _cost_money(value: object, label: str) -> Decimal:
    if not isinstance(value, str) or _USD_SIX.fullmatch(value) is None:
        raise ManifestCostProjectionError(
            f"{label} must be a six-decimal non-negative USD amount"
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ManifestCostProjectionError(f"{label} must be decimal USD") from exc
    if not parsed.is_finite():
        raise ManifestCostProjectionError(f"{label} must be finite USD")
    return parsed

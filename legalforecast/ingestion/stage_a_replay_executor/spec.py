"""Closed, self-hashed input contract for the canonical Stage A executor.

The spec is an execution sidecar, not a new authenticated benchmark schema.  A
production spec names verifier-owned artifacts; only explicitly synthetic test
specs may carry packet records inline.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.ingestion.stage_a_replay_executor.contract import (
    ReplaySpendCeilingError,
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    candidate_ids_value as _candidate_ids,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    canonical as _canonical,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    digest as _digest,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    mapping_value as _mapping,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    optional_path as _optional_path,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    path_value as _path,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    read_regular as _read_regular,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    sha256_bytes as _sha256_bytes,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    text_value as _text,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    validate_authorization as _validate_authorization,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    validate_spend as _validate_spend,
)

REPLAY_SPEC_SCHEMA_VERSION = "legalforecast.candidate_scoped_stage_a_executor_spec.v1"
UNITIZER_CONFIG_NAMESPACE = "claim-ontology-v5"
REVIEWER_CONFIG_NAMESPACE = "claim-ontology-v4"

__all__ = (
    "ReplaySpec",
    "ReplaySpendCeilingError",
    "StageAReplayExecutorError",
    "configuration_digest",
    "load_replay_spec",
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")
_PRODUCTION_LINEAGE_FIELDS = {
    "mode",
    "cycle_id",
    "index_path",
    "active_root_identity_sha256",
    "predecessor",
    "successor",
    "repair_receipt",
}
_PREDECESSOR_FIELDS = {
    "raw_prediction_units_path",
    "unitization_audit_path",
    "unitization_run_card_path",
    "original_review_path",
    "structural_flags_path",
    "structural_review_audit_path",
    "structural_review_run_card_path",
    "structural_review_registry_path",
    "structural_review_model_key",
    "merged_review_path",
    "finalized_prediction_units_path",
    "adjudications_path",
    "apply_unitization_run_card_path",
    "controlled_private_root",
    "initialization_receipt_path",
}
_SUCCESSOR_FIELDS = {
    "selection_path",
    "selection_run_card_path",
    "download_manifest_path",
    "disclosure_clearance_path",
    "materialization_run_card_path",
    "document_root",
    "parse_requests_path",
    "parser_manifest_path",
    "parser_run_card_path",
    "markdown_root",
    "controlled_private_root",
    "initialization_receipt_path",
}
_REPAIR_EVIDENCE_FIELDS = {
    "manifest_path",
    "approval_path",
    "snapshot_manifest_path",
    "source_lineage_path",
    "source_lineage_sha256",
    "snapshots_root",
    "execution_path",
    "execution_artifact_sha256",
    "receipt_path",
    "receipt_artifact_sha256",
    "expected_receipt_sha256",
}
_FIXTURE_LINEAGE_FIELDS = {
    "mode",
    "synthetic",
    "cycle_id",
    "predecessor",
    "successor",
    "predecessor_selection_sha256",
    "predecessor_materialization_sha256",
    "predecessor_parser_sha256",
    "successor_selection_sha256",
    "successor_materialization_sha256",
    "successor_parser_sha256",
}
_OUTPUT_FIELDS = {
    "plan_path",
    "execution_path",
    "stage_a_receipt_path",
    "invocation_journal_path",
    "executor_receipt_path",
    "terminal_evidence_root",
}


@dataclass(frozen=True, slots=True)
class ReplaySpec:
    """Immutable, validated view over one replay-spec sidecar."""

    path: Path
    spec_sha256: str
    record: Mapping[str, object]
    candidate_ids: tuple[str, ...]
    per_candidate_ceiling_usd: Mapping[str, Decimal]
    aggregate_ceiling_usd: Decimal
    invocation_reservations_usd: Mapping[str, Decimal]
    code_commit: str
    config_hashes: Mapping[str, str]
    model_ids: Mapping[str, str]
    provider_journal_path: Path
    provider_caps_sha256: str
    model_registry_sha256: str
    cycle_id: str
    output_paths: Mapping[str, Path]
    input_paths: tuple[Path, ...]
    synthetic_fixture: bool


def load_replay_spec(path: str | Path, *, now: datetime | None = None) -> ReplaySpec:
    """Authenticate the spec before opening any referenced artifact or journal."""

    source = Path(path).resolve()
    payload = _read_regular(source, "replay-spec")
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(
            f"replay-spec hash {hashlib.sha256(payload).hexdigest()} is not valid JSON"
        ) from exc
    if not isinstance(loaded, dict):
        raise StageAReplayExecutorError("replay-spec must be a JSON object")
    raw = cast(dict[str, object], loaded)
    claimed = _digest(raw, "replay_spec_sha256")
    unsigned = dict(raw)
    del unsigned["replay_spec_sha256"]
    actual = _sha256_bytes(_canonical(unsigned))
    if actual != claimed:
        raise StageAReplayExecutorError(
            "replay-spec hash mismatch: "
            f"claimed {claimed}, computed {actual} (replay-spec hash)"
        )
    required = {
        "schema_version",
        "replay_spec_sha256",
        "authorization",
        "candidate_ids",
        "lineage",
        "configuration",
        "spend",
        "provider",
        "outputs",
        "code_commit",
    }
    if set(raw) != required or raw.get("schema_version") != REPLAY_SPEC_SCHEMA_VERSION:
        raise StageAReplayExecutorError("replay-spec fields or schema_version differ")

    candidate_ids = _candidate_ids(raw.get("candidate_ids"), "replay-spec")
    authorization = _mapping(raw, "authorization")
    request_artifact_path = _validate_authorization(
        authorization, candidate_ids, now=now
    )
    lineage = _mapping(raw, "lineage")
    synthetic = _validate_lineage(lineage, authorization)
    cycle_id = _text(lineage, "cycle_id")
    provider = _mapping(raw, "provider")
    provider_paths, caps_sha, registry_sha = _validate_provider(provider)
    config_hashes, model_ids = _validate_configuration(
        _mapping(raw, "configuration"),
        provider_caps_sha256=caps_sha,
        model_registry_sha256=registry_sha,
    )
    aggregate, per_candidate, reservations = _validate_spend(
        _mapping(raw, "spend"), authorization, candidate_ids
    )
    output_paths = _validate_outputs(_mapping(raw, "outputs"))
    code_commit = _text(raw, "code_commit")
    if _COMMIT.fullmatch(code_commit) is None:
        raise StageAReplayExecutorError("code_commit must be a hexadecimal commit id")

    lineage_inputs = _lineage_input_paths(lineage)
    input_paths = (
        source,
        request_artifact_path,
        *provider_paths,
        *lineage_inputs,
    )
    _require_output_isolation(output_paths, input_paths)
    return ReplaySpec(
        path=source,
        spec_sha256=claimed,
        record=MappingProxyType(raw),
        candidate_ids=candidate_ids,
        per_candidate_ceiling_usd=MappingProxyType(per_candidate),
        aggregate_ceiling_usd=aggregate,
        invocation_reservations_usd=MappingProxyType(reservations),
        code_commit=code_commit,
        config_hashes=MappingProxyType(config_hashes),
        model_ids=MappingProxyType(model_ids),
        provider_journal_path=provider_paths[2],
        provider_caps_sha256=caps_sha,
        model_registry_sha256=registry_sha,
        cycle_id=cycle_id,
        output_paths=MappingProxyType(output_paths),
        input_paths=tuple(dict.fromkeys(input_paths)),
        synthetic_fixture=synthetic,
    )


def configuration_digest(record: Mapping[str, object]) -> str:
    """Return the closed executor configuration commitment."""

    return _sha256_bytes(_canonical(record))


def _validate_lineage(
    lineage: Mapping[str, object], authorization: Mapping[str, object]
) -> bool:
    mode = _text(lineage, "mode")
    if mode == "synthetic_fixture":
        if (
            set(lineage) != _FIXTURE_LINEAGE_FIELDS
            or lineage.get("synthetic") is not True
        ):
            raise StageAReplayExecutorError("synthetic fixture lineage fields differ")
        if _text(authorization, "signature") != "synthetic:true":
            raise StageAReplayExecutorError(
                "inline packet authority is permitted only for synthetic fixtures"
            )
        for name in _FIXTURE_LINEAGE_FIELDS - {
            "mode",
            "synthetic",
            "cycle_id",
            "predecessor",
            "successor",
        }:
            _digest(lineage, name)
        if not isinstance(lineage.get("predecessor"), list) or not isinstance(
            lineage.get("successor"), list
        ):
            raise StageAReplayExecutorError("synthetic fixture packets must be arrays")
        return True
    if mode != "verified_artifacts" or set(lineage) != _PRODUCTION_LINEAGE_FIELDS:
        raise StageAReplayExecutorError("production lineage descriptor fields differ")
    if _text(authorization, "signature") == "synthetic:true":
        raise StageAReplayExecutorError(
            "production lineage requires owner authorization"
        )
    _path(lineage, "index_path")
    _digest(lineage, "active_root_identity_sha256")
    predecessor = _mapping(lineage, "predecessor")
    successor = _mapping(lineage, "successor")
    repair = _mapping(lineage, "repair_receipt")
    if set(predecessor) != _PREDECESSOR_FIELDS:
        raise StageAReplayExecutorError("predecessor verifier inputs differ")
    if set(successor) != _SUCCESSOR_FIELDS:
        raise StageAReplayExecutorError("successor verifier inputs differ")
    for record, fields in (
        (predecessor, _PREDECESSOR_FIELDS),
        (successor, _SUCCESSOR_FIELDS),
    ):
        for field in fields:
            if field.endswith("_path") or field.endswith("_root"):
                _optional_path(record, field)
            else:
                _text(record, field)
    if set(repair) != _REPAIR_EVIDENCE_FIELDS:
        raise StageAReplayExecutorError("repair verifier inputs differ")
    for field in _REPAIR_EVIDENCE_FIELDS:
        if field.endswith("_path") or field.endswith("_root"):
            _path(repair, field)
        else:
            _digest(repair, field)
    return False


def _validate_provider(
    provider: Mapping[str, object],
) -> tuple[tuple[Path, Path, Path], str, str]:
    required = {
        "model_registry_path",
        "model_registry_sha256",
        "provider_cycle_caps_path",
        "provider_caps_sha256",
        "journal_path",
        "provider_accounts",
    }
    if set(provider) != required:
        raise StageAReplayExecutorError("provider descriptor fields differ")
    accounts = _mapping(provider, "provider_accounts")
    if not accounts or any(
        not isinstance(value, str) or not value for value in accounts.values()
    ):
        raise StageAReplayExecutorError("provider accounts must be non-empty text")
    return (
        (
            _path(provider, "model_registry_path"),
            _path(provider, "provider_cycle_caps_path"),
            _path(provider, "journal_path"),
        ),
        _digest(provider, "provider_caps_sha256"),
        _digest(provider, "model_registry_sha256"),
    )


def _validate_configuration(
    configuration: Mapping[str, object],
    *,
    provider_caps_sha256: str,
    model_registry_sha256: str,
) -> tuple[dict[str, str], dict[str, str]]:
    if set(configuration) != {"unitizer", "reviewer"}:
        raise StageAReplayExecutorError(
            "frozen Stage A configuration must name unitizer and reviewer"
        )
    hashes: dict[str, str] = {}
    models: dict[str, str] = {}
    for stage, namespace in (
        ("unitizer", UNITIZER_CONFIG_NAMESPACE),
        ("reviewer", REVIEWER_CONFIG_NAMESPACE),
    ):
        value = _mapping(configuration, stage)
        content_fields = {
            "namespace",
            "prompt_contract",
            "model_id",
            "model_registry_sha256",
            "model_entry_sha256",
            "provider_caps_sha256",
        }
        if set(value) != content_fields | {"config_sha256"}:
            raise StageAReplayExecutorError(
                f"{stage} frozen configuration fields differ"
            )
        if (
            _text(value, "namespace") != namespace
            or _text(value, "prompt_contract") != namespace
        ):
            raise StageAReplayExecutorError(
                f"{stage} must use frozen {namespace} contract"
            )
        if _digest(value, "model_registry_sha256") != model_registry_sha256:
            raise StageAReplayExecutorError(f"{stage} model registry pin differs")
        if _digest(value, "provider_caps_sha256") != provider_caps_sha256:
            raise StageAReplayExecutorError(f"{stage} provider caps pin differs")
        _digest(value, "model_entry_sha256")
        models[stage] = _text(value, "model_id")
        content = {name: value[name] for name in sorted(content_fields)}
        hashes[stage] = _digest(value, "config_sha256")
        if configuration_digest(content) != hashes[stage]:
            raise StageAReplayExecutorError(
                f"{stage} frozen configuration hash differs"
            )
    return hashes, models


def _validate_outputs(outputs: Mapping[str, object]) -> dict[str, Path]:
    if set(outputs) != _OUTPUT_FIELDS:
        raise StageAReplayExecutorError("executor output fields differ")
    paths = {name: _path(outputs, name) for name in _OUTPUT_FIELDS}
    values = tuple(paths.values())
    if len(set(values)) != len(values):
        raise StageAReplayExecutorError("executor output paths must be distinct")
    for index, path in enumerate(values):
        for other in values[index + 1 :]:
            if path in other.parents or other in path.parents:
                raise StageAReplayExecutorError(
                    "executor output paths must not overlap each other"
                )
    if any(path.exists() or path.is_symlink() for path in values):
        raise StageAReplayExecutorError("executor outputs must not already exist")
    return paths


def _lineage_input_paths(lineage: Mapping[str, object]) -> tuple[Path, ...]:
    if lineage.get("mode") == "synthetic_fixture":
        return ()
    paths = [_path(lineage, "index_path")]
    for section in ("predecessor", "successor"):
        record = _mapping(lineage, section)
        paths.extend(
            path
            for name in record
            if name != "controlled_private_root"
            if (name.endswith("_path") or name.endswith("_root"))
            and (path := _optional_path(record, name)) is not None
        )
    repair = _mapping(lineage, "repair_receipt")
    paths.extend(
        _path(repair, field)
        for field in _REPAIR_EVIDENCE_FIELDS
        if field.endswith("_path") or field.endswith("_root")
    )
    return tuple(paths)


def _require_output_isolation(
    outputs: Mapping[str, Path], inputs: Sequence[Path]
) -> None:
    for output in outputs.values():
        for source in inputs:
            if output == source or output in source.parents or source in output.parents:
                raise StageAReplayExecutorError(
                    "executor output overlaps authenticated input: "
                    f"{output} vs {source}"
                )

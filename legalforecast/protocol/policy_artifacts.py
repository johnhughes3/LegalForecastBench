"""Canonical precommitment and execution policy artifacts."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._datetime import format_utc_iso_z

LABELING_POLICY_SCHEMA_VERSION = "legalforecast.labeling_policy.v1"
EXECUTION_POLICY_SCHEMA_VERSION = "legalforecast.execution_policy.v1"
LABEL_AUDIT_SAMPLE_FRACTION = 0.05
LABEL_AUDIT_MINIMUM_SAMPLE_SIZE = 20
LABEL_AUDIT_MINIMUM_PER_STRATUM = 5
LABEL_AUDIT_MAX_ERROR_RATE = 0.05
LABEL_AUDIT_STRATA = (
    "unanimous_grant",
    "unanimous_deny",
    "partial",
)
OFFICIAL_SHARD_ABLATIONS = ("full_packet", "metadata_only")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class PolicyArtifactError(ValueError):
    """Raised when a policy artifact is incomplete or inconsistent."""


def generate_labeling_policy(
    *,
    cycle_id: str,
    judge_registry_path: str | Path,
    published_at: datetime,
    threshold_source: str,
) -> dict[str, Any]:
    """Generate the fixed Cycle 1 labeling precommitment."""

    registry_path = Path(judge_registry_path)
    _validate_judge_registry(registry_path)
    policy = {
        "cycle_id": _text(cycle_id, "cycle_id"),
        "published_at": _timestamp(published_at, "published_at"),
        "judge_registry_sha256": _sha256_file(registry_path),
        "label_audit": {
            "population": "auto_labeled_units",
            "sample_fraction": LABEL_AUDIT_SAMPLE_FRACTION,
            "minimum_sample_size": LABEL_AUDIT_MINIMUM_SAMPLE_SIZE,
            "strata": list(LABEL_AUDIT_STRATA),
            "minimum_per_stratum": LABEL_AUDIT_MINIMUM_PER_STRATUM,
            "allocation": "largest_remainder_with_minimums_exhaustive_below_minimum",
            "seed_components": [
                "cycle_id",
                "pre_adjudication_ensemble_corpus_sha256",
                "labeling_policy_sha256",
            ],
            "max_llm_error_rate": LABEL_AUDIT_MAX_ERROR_RATE,
            "max_human_disagreement_rate": LABEL_AUDIT_MAX_ERROR_RATE,
            "threshold_operator": "greater_than",
            "threshold_source": _text(threshold_source, "threshold_source"),
        },
    }
    return _artifact(LABELING_POLICY_SCHEMA_VERSION, policy)


def verify_labeling_policy(
    artifact: Mapping[str, Any],
    *,
    judge_registry_path: str | Path | None = None,
    expected_cycle_id: str | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Verify labeling-policy schema, commitment, and optional registry bytes."""

    policy, actual = _verify_artifact(
        artifact, schema_version=LABELING_POLICY_SCHEMA_VERSION
    )
    _exact_keys(
        policy,
        {"cycle_id", "published_at", "judge_registry_sha256", "label_audit"},
        "labeling policy",
    )
    cycle_id = _text(policy.get("cycle_id"), "cycle_id")
    _parse_timestamp(policy.get("published_at"), "published_at")
    registry_sha256 = _sha(policy.get("judge_registry_sha256"), "judge_registry_sha256")
    _verify_label_audit(_object(policy.get("label_audit"), "label_audit"))
    if expected_cycle_id is not None and cycle_id != expected_cycle_id:
        raise PolicyArtifactError("labeling policy cycle_id must match expected cycle")
    if expected_sha256 is not None and actual != _sha(
        expected_sha256, "expected_sha256"
    ):
        raise PolicyArtifactError("labeling policy hash does not match expected hash")
    if judge_registry_path is not None:
        path = Path(judge_registry_path)
        _validate_judge_registry(path)
        if _sha256_file(path) != registry_sha256:
            raise PolicyArtifactError(
                "judge registry bytes do not match labeling policy commitment"
            )
    return actual


def write_labeling_policy(path: str | Path, artifact: Mapping[str, Any]) -> None:
    """Publish a verified policy once; changed content may not overwrite it."""

    verify_labeling_policy(artifact)
    _write_immutable(Path(path), artifact, "labeling policy")


def labeling_policy_content(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return labeling-policy content only after complete validation."""

    verify_labeling_policy(artifact)
    return cast(Mapping[str, Any], artifact["policy"])


def generate_execution_policy(decisions: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and commit the at-freeze execution decisions."""

    policy = _validated_execution_policy(decisions)
    return _artifact(EXECUTION_POLICY_SCHEMA_VERSION, policy)


def verify_execution_policy(
    artifact: Mapping[str, Any],
    *,
    expected_cycle_id: str | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Verify the at-freeze execution policy and its content commitment."""

    policy, actual = _verify_artifact(
        artifact, schema_version=EXECUTION_POLICY_SCHEMA_VERSION
    )
    validated = _validated_execution_policy(policy)
    if expected_cycle_id is not None and validated["cycle_id"] != expected_cycle_id:
        raise PolicyArtifactError("execution policy cycle_id must match expected cycle")
    if expected_sha256 is not None and actual != _sha(
        expected_sha256, "expected_sha256"
    ):
        raise PolicyArtifactError("execution policy hash does not match expected hash")
    return actual


def write_execution_policy(path: str | Path, artifact: Mapping[str, Any]) -> None:
    """Write a verified canonical execution policy."""

    verify_execution_policy(artifact)
    _write_immutable(Path(path), artifact, "execution policy")


def execution_policy_content(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return validated execution-policy content for cross-artifact checks."""

    verify_execution_policy(artifact)
    return cast(Mapping[str, Any], artifact["policy"])


def require_dispatch_policy_match(
    artifact: Mapping[str, Any],
    *,
    cycle_series: str,
    allow_no_baselines: bool,
) -> None:
    """Fail closed when mutable dispatch inputs differ from frozen choices."""

    policy = execution_policy_content(artifact)
    if cycle_series != policy["cycle_series"]:
        raise PolicyArtifactError(
            "dispatch cycle_series does not match frozen execution policy"
        )
    if allow_no_baselines != policy["allow_no_baselines"]:
        raise PolicyArtifactError(
            "dispatch allow_no_baselines does not match frozen execution policy"
        )


def load_json_object(path: str | Path, description: str) -> Mapping[str, Any]:
    """Load one strict JSON object for policy verification."""

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyArtifactError(f"invalid {description}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PolicyArtifactError(f"{description} must be a JSON object")
    return cast(Mapping[str, Any], value)


def find_values(value: Any, field_name: str) -> tuple[Any, ...]:
    """Find every recursively restated JSON field."""

    found: list[Any] = []
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        for key, child in mapping.items():
            if key == field_name:
                found.append(child)
            found.extend(find_values(child, field_name))
    elif isinstance(value, list):
        for child in cast(list[Any], value):
            found.extend(find_values(child, field_name))
    return tuple(found)


def _validated_execution_policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    policy = cast(dict[str, Any], json.loads(_canonical(raw)))
    _exact_keys(
        policy,
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
        },
        "execution policy",
    )
    _text(policy.get("cycle_id"), "cycle_id")
    if policy.get("cycle_series") not in {"rapid", "official"}:
        raise PolicyArtifactError("cycle_series must be rapid or official")
    _boolean(policy.get("allow_no_baselines"), "allow_no_baselines")
    for field in (
        "labeling_policy_sha256",
        "cohort_policy_sha256",
        "cohort_observation_manifest_sha256",
    ):
        _sha(policy.get(field), field)

    lifecycle = _object(policy.get("lifecycle"), "lifecycle")
    _exact_keys(
        lifecycle,
        {
            "labeling_policy_published_at",
            "production_labeling_started_at",
            "cohort_policy_published_at",
            "batch_002_started_at",
        },
        "lifecycle",
    )
    labeling_published = _parse_timestamp(
        lifecycle.get("labeling_policy_published_at"),
        "labeling_policy_published_at",
    )
    labeling_started = _parse_timestamp(
        lifecycle.get("production_labeling_started_at"),
        "production_labeling_started_at",
    )
    cohort_published = _parse_timestamp(
        lifecycle.get("cohort_policy_published_at"), "cohort_policy_published_at"
    )
    batch_started = _parse_timestamp(
        lifecycle.get("batch_002_started_at"), "batch_002_started_at"
    )
    if labeling_published > labeling_started:
        raise PolicyArtifactError("labeling policy was not published before labeling")
    if cohort_published > batch_started:
        raise PolicyArtifactError("cohort policy was not published before Batch 002")

    shards = _object(policy.get("shard_schedule"), "shard_schedule")
    _exact_keys(
        shards,
        {"shard_count", "dispatch_unit", "shards"},
        "shard_schedule",
    )
    _positive_int(shards.get("shard_count"), "shard_schedule.shard_count")
    if shards.get("dispatch_unit") != "model_key_ablation":
        raise PolicyArtifactError(
            "shard_schedule.dispatch_unit must be model_key_ablation"
        )
    shard_records = _object_list(shards.get("shards"), "shard_schedule.shards")
    normalized_shards: list[dict[str, str]] = []
    for index, shard in enumerate(shard_records):
        name = f"shard_schedule.shards[{index}]"
        _exact_keys(shard, {"model_key", "ablation"}, name)
        model_key = _text(shard.get("model_key"), f"{name}.model_key")
        if ":" not in model_key:
            raise PolicyArtifactError(f"{name}.model_key must be provider:model_id")
        ablation = _text(shard.get("ablation"), f"{name}.ablation")
        if ablation not in OFFICIAL_SHARD_ABLATIONS:
            raise PolicyArtifactError(
                f"{name}.ablation must be one of {list(OFFICIAL_SHARD_ABLATIONS)}"
            )
        normalized_shards.append({"model_key": model_key, "ablation": ablation})
    unique_shards = {
        (shard["model_key"], shard["ablation"]) for shard in normalized_shards
    }
    if len(unique_shards) != len(normalized_shards):
        raise PolicyArtifactError("shard_schedule.shards contains duplicates")
    if len(normalized_shards) != shards["shard_count"]:
        raise PolicyArtifactError(
            "shard_schedule.shard_count must equal the number of declared shards"
        )
    models = {model_key for model_key, _ in unique_shards}
    expected_shards = {
        (model_key, ablation)
        for model_key in models
        for ablation in OFFICIAL_SHARD_ABLATIONS
    }
    if unique_shards != expected_shards:
        raise PolicyArtifactError(
            "shard_schedule.shards must declare both required ablations for every model"
        )
    cast(dict[str, Any], shards)["shards"] = sorted(
        normalized_shards,
        key=lambda shard: (shard["model_key"], shard["ablation"]),
    )

    concurrency = _object(policy.get("concurrency_policy"), "concurrency_policy")
    _exact_keys(concurrency, {"mode", "identity_fields"}, "concurrency_policy")
    if concurrency.get("mode") != "shard_identity":
        raise PolicyArtifactError(
            "concurrency_policy.mode must be shard_identity for the official "
            "shard dispatcher"
        )
    identity_fields = _string_list(
        concurrency.get("identity_fields"), "concurrency_policy.identity_fields"
    )
    required_identity_fields = ("cycle_id", "model_key", "ablation")
    if identity_fields != required_identity_fields:
        raise PolicyArtifactError(
            "concurrency_policy.identity_fields must match the selected mode: "
            f"expected {list(required_identity_fields)}"
        )

    receipts = _object(policy.get("receipt_policy"), "receipt_policy")
    _exact_keys(
        receipts,
        {"write_once_per_attempt", "identity_fields", "result_commitment_required"},
        "receipt_policy",
    )
    _true(receipts.get("write_once_per_attempt"), "write_once_per_attempt")
    _string_list(receipts.get("identity_fields"), "receipt_policy.identity_fields")
    _true(receipts.get("result_commitment_required"), "result_commitment_required")

    attempts = _object(policy.get("attempt_policy"), "attempt_policy")
    _exact_keys(
        attempts,
        {"reservation_ledger_sha256", "max_billable_attempts"},
        "attempt_policy",
    )
    _sha(attempts.get("reservation_ledger_sha256"), "reservation_ledger_sha256")
    _positive_int(attempts.get("max_billable_attempts"), "max_billable_attempts")

    repeat = _object(policy.get("repeat_policy"), "repeat_policy")
    _exact_keys(repeat, {"case_ids", "count"}, "repeat_policy")
    case_ids = _string_list(repeat.get("case_ids"), "repeat_policy.case_ids")
    if len(case_ids) != len(set(case_ids)):
        raise PolicyArtifactError("repeat_policy.case_ids contains duplicates")
    if repeat.get("count") != len(case_ids):
        raise PolicyArtifactError("repeat_policy.count must equal case_ids length")

    cadence = _object(policy.get("cadence_counts"), "cadence_counts")
    _exact_keys(
        cadence,
        {
            "clean_motion_count_source",
            "prediction_unit_count_source",
            "reject_operator_mismatch",
        },
        "cadence_counts",
    )
    if cadence.get("clean_motion_count_source") != "frozen_manifest":
        raise PolicyArtifactError("clean motion count must derive from frozen_manifest")
    if cadence.get("prediction_unit_count_source") != "frozen_units":
        raise PolicyArtifactError("prediction unit count must derive from frozen_units")
    _true(cadence.get("reject_operator_mismatch"), "reject_operator_mismatch")
    return policy


def _verify_label_audit(audit: Mapping[str, Any]) -> None:
    _exact_keys(
        audit,
        {
            "population",
            "sample_fraction",
            "minimum_sample_size",
            "strata",
            "minimum_per_stratum",
            "allocation",
            "seed_components",
            "max_llm_error_rate",
            "max_human_disagreement_rate",
            "threshold_operator",
            "threshold_source",
        },
        "label_audit",
    )
    expected: dict[str, Any] = {
        "population": "auto_labeled_units",
        "sample_fraction": LABEL_AUDIT_SAMPLE_FRACTION,
        "minimum_sample_size": LABEL_AUDIT_MINIMUM_SAMPLE_SIZE,
        "strata": list(LABEL_AUDIT_STRATA),
        "minimum_per_stratum": LABEL_AUDIT_MINIMUM_PER_STRATUM,
        "allocation": "largest_remainder_with_minimums_exhaustive_below_minimum",
        "seed_components": [
            "cycle_id",
            "pre_adjudication_ensemble_corpus_sha256",
            "labeling_policy_sha256",
        ],
        "max_llm_error_rate": LABEL_AUDIT_MAX_ERROR_RATE,
        "max_human_disagreement_rate": LABEL_AUDIT_MAX_ERROR_RATE,
        "threshold_operator": "greater_than",
    }
    for field, value in expected.items():
        if audit.get(field) != value:
            raise PolicyArtifactError(f"label_audit.{field} is not precommitted")
    _text(audit.get("threshold_source"), "threshold_source")


def _validate_judge_registry(path: Path) -> None:
    try:
        from legalforecast.evals.model_registry import load_model_registry

        registry = load_model_registry(path)
    except (OSError, ValueError) as exc:
        raise PolicyArtifactError(f"invalid judge registry: {exc}") from exc
    if not registry.entries:
        raise PolicyArtifactError("judge registry must contain at least one entry")


def _artifact(schema_version: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    normalized = cast(dict[str, Any], json.loads(_canonical(policy)))
    return {
        "schema_version": schema_version,
        "policy": normalized,
        "policy_sha256": _hash(normalized),
    }


def _verify_artifact(
    artifact: Mapping[str, Any], *, schema_version: str
) -> tuple[Mapping[str, Any], str]:
    _exact_keys(
        artifact, {"schema_version", "policy", "policy_sha256"}, "policy artifact"
    )
    if artifact.get("schema_version") != schema_version:
        raise PolicyArtifactError("unsupported policy artifact schema version")
    policy = _object(artifact.get("policy"), "policy")
    actual = _hash(policy)
    if _sha(artifact.get("policy_sha256"), "policy_sha256") != actual:
        raise PolicyArtifactError("policy hash does not match its content")
    return policy, actual


def _write_immutable(path: Path, artifact: Mapping[str, Any], description: str) -> None:
    payload = f"{_canonical(artifact)}\n".encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(f"{path}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if path.exists():
            if path.read_bytes() != payload:
                raise PolicyArtifactError(
                    f"{description} already exists with different immutable content"
                )
            return
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    finally:
        os.close(lock_fd)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise PolicyArtifactError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PolicyArtifactError(
            f"{name} fields mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PolicyArtifactError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _object_list(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise PolicyArtifactError(f"{name} must be an object list")
    return tuple(
        _object(item, f"{name}[{index}]")
        for index, item in enumerate(cast(Sequence[Any], value))
    )


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyArtifactError(f"{name} must be a non-empty string")
    return value.strip()


def _sha(value: Any, name: str) -> str:
    text = _text(value, name)
    if _SHA256.fullmatch(text) is None:
        raise PolicyArtifactError(f"{name} must be a lowercase SHA-256 hash")
    return text


def _timestamp(value: datetime, name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PolicyArtifactError(f"{name} must be timezone-aware")
    return format_utc_iso_z(value)


def _parse_timestamp(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyArtifactError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PolicyArtifactError(f"{name} must be timezone-aware")
    return parsed


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise PolicyArtifactError(f"{name} must be a boolean")
    return value


def _true(value: Any, name: str) -> None:
    if _boolean(value, name) is not True:
        raise PolicyArtifactError(f"{name} must be true")


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PolicyArtifactError(f"{name} must be a positive integer")
    return value


def _string_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise PolicyArtifactError(f"{name} must be a string list")
    result = tuple(_text(item, name) for item in cast(Sequence[Any], value))
    return result

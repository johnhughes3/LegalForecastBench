"""Run-card construction and validation helpers for published benchmark runs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import ModelRegistryEntry

RUN_CARD_SCHEMA_VERSION = "legalforecast.run_card.v1"
RUN_CARD_PRICE_UNIT = "usd_per_1m_tokens"
RUN_CARD_TYPES = frozenset(
    {"official", "rapid", "pilot", "descriptive", "annual_aggregate"}
)


@dataclass(frozen=True, slots=True)
class RunCardArtifacts:
    """Frozen artifacts and run condition facts attached to a run card."""

    cycle_id: str
    evaluation_timestamp: datetime
    harness_version: str
    prompt_sha256: str
    scorer_sha256: str
    model_registry_sha256: str
    manifest_sha256: str
    prediction_unit_sha256: str
    label_sha256: str
    tool_call_cap: int
    run_label: str = "full_packet"

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_aware_datetime(self.evaluation_timestamp, "evaluation_timestamp")
        _require_non_empty(self.harness_version, "harness_version")
        for field_name in (
            "prompt_sha256",
            "scorer_sha256",
            "model_registry_sha256",
            "manifest_sha256",
            "prediction_unit_sha256",
            "label_sha256",
        ):
            _require_prefixed_sha256(getattr(self, field_name), field_name)
        _require_non_negative_int(self.tool_call_cap, "tool_call_cap")
        _require_non_empty(self.run_label, "run_label")


@dataclass(frozen=True, slots=True)
class RunCardValidationIssue:
    """One validation issue for a run-card field."""

    path: str
    message: str

    def __post_init__(self) -> None:
        _require_non_empty(self.path, "path")
        _require_non_empty(self.message, "message")

    def to_record(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True, slots=True)
class RunCardValidationResult:
    """Validation result for a run-card record."""

    issues: tuple[RunCardValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_records(self) -> list[dict[str, str]]:
        return [issue.to_record() for issue in self.issues]

    def require_ok(self) -> None:
        if self.ok:
            return
        formatted = "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        raise ValueError(f"run card validation failed: {formatted}")


def build_run_card_record(
    *,
    run_id: str,
    run_type: str,
    generated_at: datetime,
    registry_entry: ModelRegistryEntry,
    artifacts: RunCardArtifacts,
    accounting_summary: Mapping[str, Any],
    limitations: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """Build and validate a complete run-card JSON record."""

    _require_non_empty(run_id, "run_id")
    _require_run_type(run_type, "run_type")
    _require_aware_datetime(generated_at, "generated_at")
    accounting = _validated_accounting_summary(accounting_summary)
    record: dict[str, Any] = {
        "schema_version": RUN_CARD_SCHEMA_VERSION,
        "run": {
            "run_id": run_id,
            "cycle_id": artifacts.cycle_id,
            "run_type": run_type,
            "generated_at": _iso_datetime(generated_at),
            "evaluation_timestamp": _iso_datetime(artifacts.evaluation_timestamp),
            "harness_version": artifacts.harness_version,
            "run_label": artifacts.run_label,
            "limitations": _string_list(limitations, "limitations"),
        },
        "model": _model_record(registry_entry),
        "sampling": {
            "temperature": registry_entry.temperature,
            "top_p": registry_entry.top_p,
            "max_output_tokens": registry_entry.max_output_tokens,
        },
        "policy": {
            "network_disabled": registry_entry.network_disabled,
            "search_disabled": registry_entry.search_disabled,
            "tool_policy": registry_entry.tool_policy.value,
            "tool_call_cap": artifacts.tool_call_cap,
        },
        "pricing": {
            "pricing_source": registry_entry.pricing_source,
            "input_token_price": registry_entry.input_token_price,
            "output_token_price": registry_entry.output_token_price,
            "price_unit": RUN_CARD_PRICE_UNIT,
        },
        "hashes": {
            "prompt_sha256": artifacts.prompt_sha256,
            "scorer_sha256": artifacts.scorer_sha256,
            "model_registry_sha256": artifacts.model_registry_sha256,
            "manifest_sha256": artifacts.manifest_sha256,
            "prediction_unit_sha256": artifacts.prediction_unit_sha256,
            "label_sha256": artifacts.label_sha256,
        },
        "accounting_summary": accounting,
        "notes": _string_list(notes, "notes"),
    }
    validate_run_card_record(record).require_ok()
    return record


def validate_run_card_record(record: Mapping[str, Any]) -> RunCardValidationResult:
    """Validate the required LegalForecast-MTD run-card schema fields."""

    issues: list[RunCardValidationIssue] = []
    _require_equal(
        _required_str(record, "schema_version", issues),
        RUN_CARD_SCHEMA_VERSION,
        "schema_version",
        issues,
    )

    run = _required_mapping(record, "run", issues)
    model = _required_mapping(record, "model", issues)
    sampling = _required_mapping(record, "sampling", issues)
    policy = _required_mapping(record, "policy", issues)
    pricing = _required_mapping(record, "pricing", issues)
    hashes = _required_mapping(record, "hashes", issues)
    accounting = _required_mapping(record, "accounting_summary", issues)
    _required_string_sequence(record, "notes", issues)

    if run is not None:
        _required_str(run, "run_id", issues, prefix="run")
        _required_str(run, "cycle_id", issues, prefix="run")
        _require_run_type(
            _required_str(run, "run_type", issues, prefix="run"),
            "run.run_type",
            issues,
        )
        _required_iso_datetime(run, "generated_at", issues, prefix="run")
        _required_iso_datetime(run, "evaluation_timestamp", issues, prefix="run")
        _required_str(run, "harness_version", issues, prefix="run")
        _required_str(run, "run_label", issues, prefix="run")
        _required_string_sequence(run, "limitations", issues, prefix="run")

    if model is not None:
        _required_str(model, "provider", issues, prefix="model")
        _required_str(model, "model_id", issues, prefix="model")
        _required_str(model, "display_name", issues, prefix="model")
        _required_str(model, "model_version_or_snapshot", issues, prefix="model")
        _optional_iso_datetime(model, "release_timestamp", issues, prefix="model")
        cutoff_status = _required_str(
            model,
            "provider_training_cutoff_status",
            issues,
            prefix="model",
        )
        _validate_cutoff(model, cutoff_status, issues)
        _required_true(model, "network_disabled", issues, prefix="model")
        _required_true(model, "search_disabled", issues, prefix="model")
        model_tool_policy = _required_str(model, "tool_policy", issues, prefix="model")
        _require_tool_policy(model_tool_policy, "model.tool_policy", issues)
        _required_int(model, "context_limit", issues, prefix="model", minimum=1)
        _required_string_sequence(
            model,
            "known_cutoff_publicity_caveats",
            issues,
            prefix="model",
        )

    if sampling is not None:
        _required_number(sampling, "temperature", issues, prefix="sampling")
        _required_number(sampling, "top_p", issues, prefix="sampling", maximum=1)
        _required_int(
            sampling,
            "max_output_tokens",
            issues,
            prefix="sampling",
            minimum=1,
        )

    if policy is not None:
        _required_true(policy, "network_disabled", issues, prefix="policy")
        _required_true(policy, "search_disabled", issues, prefix="policy")
        policy_tool_policy = _required_str(
            policy,
            "tool_policy",
            issues,
            prefix="policy",
        )
        _require_tool_policy(policy_tool_policy, "policy.tool_policy", issues)
        _required_int(policy, "tool_call_cap", issues, prefix="policy")
        if model is not None:
            model_tool_policy = _optional_str(model, "tool_policy")
            if (
                model_tool_policy is not None
                and policy_tool_policy is not None
                and model_tool_policy != policy_tool_policy
            ):
                issues.append(
                    RunCardValidationIssue(
                        path="policy.tool_policy",
                        message="must match model.tool_policy",
                    )
                )

    if pricing is not None:
        _required_str(pricing, "pricing_source", issues, prefix="pricing")
        _required_number(pricing, "input_token_price", issues, prefix="pricing")
        _required_number(pricing, "output_token_price", issues, prefix="pricing")
        _require_equal(
            _required_str(pricing, "price_unit", issues, prefix="pricing"),
            RUN_CARD_PRICE_UNIT,
            "pricing.price_unit",
            issues,
        )

    if hashes is not None:
        for field_name in (
            "prompt_sha256",
            "scorer_sha256",
            "model_registry_sha256",
            "manifest_sha256",
            "prediction_unit_sha256",
            "label_sha256",
        ):
            _required_prefixed_sha256(hashes, field_name, issues, prefix="hashes")

    if accounting is not None:
        _validate_accounting_summary(accounting, issues)

    return RunCardValidationResult(issues=tuple(issues))


def write_run_card(record: Mapping[str, Any], path: str | Path) -> Path:
    """Validate and write a run card as stable JSON."""

    validate_run_card_record(record).require_ok()
    output_path = Path(path)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _model_record(entry: ModelRegistryEntry) -> dict[str, Any]:
    return {
        "provider": entry.provider,
        "model_id": entry.model_id,
        "display_name": entry.display_name,
        "model_version_or_snapshot": entry.model_version_or_snapshot,
        "release_timestamp": (
            _iso_datetime(entry.release_timestamp)
            if entry.release_timestamp is not None
            else None
        ),
        "provider_training_cutoff_status": (
            entry.provider_training_cutoff_status.value
        ),
        "provider_training_cutoff": (
            entry.provider_training_cutoff.isoformat()
            if entry.provider_training_cutoff is not None
            else None
        ),
        "network_disabled": entry.network_disabled,
        "search_disabled": entry.search_disabled,
        "tool_policy": entry.tool_policy.value,
        "context_limit": entry.context_limit,
        "known_cutoff_publicity_caveats": list(entry.known_cutoff_publicity_caveats),
    }


def _validated_accounting_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(summary)
    issues: list[RunCardValidationIssue] = []
    _validate_accounting_summary(record, issues)
    RunCardValidationResult(issues=tuple(issues)).require_ok()
    return record


def _validate_accounting_summary(
    record: Mapping[str, Any],
    issues: list[RunCardValidationIssue],
) -> None:
    _required_int(record, "case_count", issues, prefix="accounting_summary", minimum=1)
    _required_int(
        record,
        "prediction_unit_count",
        issues,
        prefix="accounting_summary",
        minimum=1,
    )
    _required_int(record, "request_count", issues, prefix="accounting_summary")
    prompt_tokens = _required_int(
        record,
        "prompt_tokens",
        issues,
        prefix="accounting_summary",
    )
    completion_tokens = _required_int(
        record,
        "completion_tokens",
        issues,
        prefix="accounting_summary",
    )
    total_tokens = _required_int(
        record,
        "total_tokens",
        issues,
        prefix="accounting_summary",
    )
    if (
        prompt_tokens is not None
        and completion_tokens is not None
        and total_tokens is not None
        and total_tokens != prompt_tokens + completion_tokens
    ):
        issues.append(
            RunCardValidationIssue(
                path="accounting_summary.total_tokens",
                message="must equal prompt_tokens + completion_tokens",
            )
        )
    for field_name in (
        "mean_tool_calls_per_case",
        "median_tool_calls_per_case",
        "p95_tool_calls_per_case",
        "cost_per_case",
        "cost_per_prediction_unit",
        "mean_latency_ms",
        "p95_latency_ms",
    ):
        _required_number(record, field_name, issues, prefix="accounting_summary")
    for field_name in ("invalid_output_rate", "refusal_rate", "content_filter_rate"):
        _required_number(
            record,
            field_name,
            issues,
            prefix="accounting_summary",
            maximum=1,
        )


def _validate_cutoff(
    model: Mapping[str, Any],
    cutoff_status: str | None,
    issues: list[RunCardValidationIssue],
) -> None:
    if cutoff_status not in {"known", "unknown", "not_disclosed"}:
        issues.append(
            RunCardValidationIssue(
                path="model.provider_training_cutoff_status",
                message="must be known, unknown, or not_disclosed",
            )
        )
        return
    cutoff = model.get("provider_training_cutoff")
    if cutoff_status == "known":
        if not isinstance(cutoff, str) or not cutoff.strip():
            issues.append(
                RunCardValidationIssue(
                    path="model.provider_training_cutoff",
                    message="is required when cutoff status is known",
                )
            )
            return
        _validate_iso_date(cutoff, "model.provider_training_cutoff", issues)
    elif cutoff is not None:
        issues.append(
            RunCardValidationIssue(
                path="model.provider_training_cutoff",
                message="must be null unless cutoff status is known",
            )
        )


def _required_mapping(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> Mapping[str, Any] | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if not isinstance(value, Mapping):
        issues.append(RunCardValidationIssue(path=path, message="must be an object"))
        return None
    return cast(Mapping[str, Any], value)


def _required_str(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> str | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        issues.append(
            RunCardValidationIssue(path=path, message="must be a non-empty string")
        )
        return None
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _required_string_sequence(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> tuple[str, ...] | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        issues.append(RunCardValidationIssue(path=path, message="must be an array"))
        return None
    items = cast(Sequence[object], value)
    output: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            issues.append(
                RunCardValidationIssue(
                    path=f"{path}[{index}]",
                    message="must be a non-empty string",
                )
            )
            continue
        output.append(item)
    return tuple(output)


def _required_true(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> bool | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if value is not True:
        issues.append(RunCardValidationIssue(path=path, message="must be true"))
        return None
    return True


def _required_int(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
    minimum: int = 0,
) -> int | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        issues.append(RunCardValidationIssue(path=path, message="must be an integer"))
        return None
    if value < minimum:
        issues.append(
            RunCardValidationIssue(path=path, message=f"must be at least {minimum}")
        )
        return None
    return value


def _required_number(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
    maximum: float | None = None,
) -> float | None:
    path = _path(prefix, field_name)
    value = record.get(field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        issues.append(RunCardValidationIssue(path=path, message="must be a number"))
        return None
    number = float(value)
    if number < 0:
        issues.append(RunCardValidationIssue(path=path, message="cannot be negative"))
        return None
    if maximum is not None and number > maximum:
        issues.append(
            RunCardValidationIssue(path=path, message=f"must be at most {maximum:g}")
        )
        return None
    return number


def _required_iso_datetime(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> None:
    path = _path(prefix, field_name)
    value = _required_str(record, field_name, issues, prefix=prefix)
    if value is not None:
        _validate_iso_datetime(value, path, issues)


def _optional_iso_datetime(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> None:
    value = record.get(field_name)
    if value is None:
        return
    path = _path(prefix, field_name)
    if not isinstance(value, str) or not value.strip():
        issues.append(
            RunCardValidationIssue(
                path=path,
                message="must be an ISO timestamp or null",
            )
        )
        return
    _validate_iso_datetime(value, path, issues)


def _required_prefixed_sha256(
    record: Mapping[str, Any],
    field_name: str,
    issues: list[RunCardValidationIssue],
    *,
    prefix: str | None = None,
) -> None:
    path = _path(prefix, field_name)
    value = _required_str(record, field_name, issues, prefix=prefix)
    if value is not None and not _is_prefixed_sha256(value):
        issues.append(
            RunCardValidationIssue(
                path=path,
                message="must match sha256:<64 lowercase hex characters>",
            )
        )


def _require_equal(
    value: str | None,
    expected: str,
    path: str,
    issues: list[RunCardValidationIssue],
) -> None:
    if value is not None and value != expected:
        issues.append(
            RunCardValidationIssue(path=path, message=f"must equal {expected}")
        )


def _require_run_type(
    value: str | None,
    path: str,
    issues: list[RunCardValidationIssue] | None = None,
) -> None:
    if value is None:
        return
    if value in RUN_CARD_TYPES:
        return
    if issues is None:
        raise ValueError(f"{path} must be one of {sorted(RUN_CARD_TYPES)}")
    issues.append(
        RunCardValidationIssue(
            path=path,
            message=f"must be one of {sorted(RUN_CARD_TYPES)}",
        )
    )


def _require_tool_policy(
    value: str | None,
    path: str,
    issues: list[RunCardValidationIssue],
) -> None:
    if value is None:
        return
    if value in {"no_tools", "controlled_docket_tool_only"}:
        return
    issues.append(
        RunCardValidationIssue(
            path=path,
            message="must be no_tools or controlled_docket_tool_only",
        )
    )


def _string_list(values: Sequence[str], field_name: str) -> list[str]:
    output: list[str] = []
    for index, value in enumerate(values):
        if not value.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        output.append(value)
    return output


def _validate_iso_datetime(
    value: str,
    path: str,
    issues: list[RunCardValidationIssue],
) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(
            RunCardValidationIssue(path=path, message="must be an ISO timestamp")
        )


def _validate_iso_date(
    value: str,
    path: str,
    issues: list[RunCardValidationIssue],
) -> None:
    try:
        date.fromisoformat(value)
    except ValueError:
        issues.append(RunCardValidationIssue(path=path, message="must be an ISO date"))


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_prefixed_sha256(value: str, field_name: str) -> None:
    if not _is_prefixed_sha256(value):
        raise ValueError(f"{field_name} must match sha256:<64 lowercase hex>")


def _is_prefixed_sha256(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    hex_value = value.removeprefix("sha256:")
    return len(hex_value) == 64 and all(
        character in "0123456789abcdef" for character in hex_value
    )


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _path(prefix: str | None, field_name: str) -> str:
    return field_name if prefix is None else f"{prefix}.{field_name}"

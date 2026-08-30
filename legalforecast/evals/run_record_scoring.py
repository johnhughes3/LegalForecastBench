"""Score persisted evaluation-run records against locked outcome labels."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PUBLIC_RUN_RECEIPT_V1
from legalforecast.evals.model_registry import (
    ModelRegistry,
    model_registry_entry_sha256,
    require_official_registry_entries,
)
from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParsedPrediction,
    ParserStatus,
    parse_model_output,
    parsed_output_from_public_record,
)
from legalforecast.evals.scorers import (
    ScoreLabel,
    ScoreSummary,
    ScoringCase,
    score_cases,
)
from legalforecast.release import (
    BenchmarkRunManifest,
    ForecastPredictionUnit,
    ForecastRelease,
    LabelsRelease,
    validate_manifest_against_forecast,
)


@dataclass(frozen=True, slots=True)
class ReleaseOutcomeLabel:
    """Minimal score-label view for the public labels-release contract."""

    unit_id: str
    primary_outcome: int
    label_confidence: float | None = None


def score_run_records_against_labels_release(
    run_records: Sequence[Mapping[str, Any]],
    labels_release: LabelsRelease,
    *,
    base_rate: float | None,
    include_ablation_in_model_id: bool = False,
    forecast_release: ForecastRelease | None = None,
    manifest: BenchmarkRunManifest | None = None,
    expected_run_identity_sha256: str | None = None,
    model_registry: ModelRegistry | None = None,
    expected_model_registry_sha256: str | None = None,
) -> tuple[ScoreSummary, ...]:
    """Score run records using only the validated public labels release.

    The labels release intentionally contains no private review metadata.  The
    scorer consumes its binary outcomes through the same small label protocol
    as legacy community records, without manufacturing citations or loading a
    private label artifact.
    """

    if (forecast_release is None) != (manifest is None):
        raise ValueError(
            "forecast_release and manifest must be supplied together for strict scoring"
        )
    if forecast_release is not None and manifest is not None:
        _require_locked_provenance_inputs(
            expected_run_identity_sha256=expected_run_identity_sha256,
            model_registry=model_registry,
            expected_model_registry_sha256=expected_model_registry_sha256,
        )
        validate_manifest_against_forecast(manifest, forecast_release)
        return _score_locked_run_records(
            run_records,
            labels_release,
            forecast_release=forecast_release,
            base_rate=base_rate,
            include_ablation_in_model_id=include_ablation_in_model_id,
            expected_run_identity_sha256=expected_run_identity_sha256,
            model_registry=model_registry,
            expected_model_registry_sha256=expected_model_registry_sha256,
        )

    labels: tuple[ScoreLabel, ...] = tuple(
        ReleaseOutcomeLabel(unit_id=outcome.unit_id, primary_outcome=outcome.outcome)
        for outcome in labels_release.unit_outcomes
    )
    return score_run_records(
        run_records,
        labels,
        base_rate=base_rate,
        include_ablation_in_model_id=include_ablation_in_model_id,
    )


def _score_locked_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels_release: LabelsRelease,
    *,
    forecast_release: ForecastRelease,
    base_rate: float | None,
    include_ablation_in_model_id: bool,
    expected_run_identity_sha256: str | None,
    model_registry: ModelRegistry | None,
    expected_model_registry_sha256: str | None,
) -> tuple[ScoreSummary, ...]:
    """Score only a complete, identity-consistent locked forecast run."""

    expected_units = tuple(forecast_release.prediction_units)
    expected_unit_ids = tuple(unit.unit_id for unit in expected_units)
    expected_unit_id_set = set(expected_unit_ids)
    units_by_id = {unit.unit_id: unit for unit in expected_units}
    expected_case_by_unit = {unit.unit_id: unit.case_id for unit in expected_units}
    expected_scoreable = {unit.unit_id for unit in expected_units if unit.should_score}
    label_unit_ids = tuple(outcome.unit_id for outcome in labels_release.unit_outcomes)
    if set(label_unit_ids) != expected_scoreable:
        raise ValueError("labels release does not match forecast scoreable unit set")
    if labels_release.release_id != forecast_release.release_id:
        raise ValueError("labels release identity differs from forecast release")
    if labels_release.forecast_release_digest != forecast_release.release_digest:
        raise ValueError("labels release binds a different forecast release")
    if not run_records:
        raise ValueError("at least one locked run receipt is required")

    labels_by_unit_id = {
        outcome.unit_id: ReleaseOutcomeLabel(
            unit_id=outcome.unit_id,
            primary_outcome=outcome.outcome,
        )
        for outcome in labels_release.unit_outcomes
    }
    records_by_model: dict[str, list[tuple[str, ParsedModelOutput]]] = defaultdict(list)
    model_run_ids: dict[str, str] = {}
    model_bindings: dict[str, tuple[str, str, str, str]] = {}
    model_units: dict[str, set[str]] = defaultdict(set)
    for record in run_records:
        required_unit_ids = _required_str_tuple(record, "required_unit_ids")
        unknown_units = sorted(set(required_unit_ids) - expected_unit_id_set)
        if unknown_units:
            raise ValueError(
                f"run records contain units outside forecast release: {unknown_units}"
            )
        case_id = _required_str(record, "case_id")
        expected_cases = {
            expected_case_by_unit[unit_id] for unit_id in required_unit_ids
        }
        if expected_cases != {case_id}:
            raise ValueError(
                "run record case_id does not match forecast unit mapping: "
                f"case_id={case_id!r}, units={list(required_unit_ids)!r}"
            )
        receipt_unit_id = _optional_str(record, "unit_id")
        if len(required_unit_ids) != 1 or receipt_unit_id != required_unit_ids[0]:
            raise ValueError("run receipt must identify exactly one forecast unit")
        unit = units_by_id[required_unit_ids[0]]
        _validate_locked_receipt_identity(
            record,
            forecast_release=forecast_release,
            unit=unit,
            expected_run_identity_sha256=expected_run_identity_sha256,
            model_registry=model_registry,
            expected_model_registry_sha256=expected_model_registry_sha256,
        )
        parsed = _record_parsed_output(record, required_unit_ids)
        model_key = _required_str(record, "model_key")
        model_id = _optional_str(record, "model_id") or model_key
        if model_key != model_id:
            raise ValueError("run receipt model identity differs from model_id")
        model_binding = (
            model_key,
            _required_sha256(record, "model_registry_sha256"),
            _required_sha256(record, "model_registry_entry_sha256"),
            _required_str(record, "served_model_version"),
        )
        prior_model_binding = model_bindings.setdefault(model_id, model_binding)
        if prior_model_binding != model_binding:
            raise ValueError("run records mix multiple model identities")
        run_identity = _required_sha256(record, "run_identity_sha256")
        prior_run_identity = model_run_ids.setdefault(model_id, run_identity)
        if prior_run_identity != run_identity:
            raise ValueError("run records mix multiple run identities for one model")
        duplicate_units = model_units[model_id].intersection(required_unit_ids)
        if duplicate_units:
            raise ValueError(
                "run records contain duplicate receipt units: "
                f"{sorted(duplicate_units)}"
            )
        model_units[model_id].update(required_unit_ids)
        records_by_model[model_id].append((case_id, parsed))

    missing_by_model = {
        model_id: sorted(expected_unit_id_set - unit_ids)
        for model_id, unit_ids in model_units.items()
        if unit_ids != expected_unit_id_set
    }
    if missing_by_model:
        raise ValueError(
            "run records are incomplete for forecast release: "
            f"missing_units={missing_by_model}"
        )

    cases_by_model: dict[str, list[ScoringCase]] = defaultdict(list)
    for model_id, records in records_by_model.items():
        parsed_by_unit: dict[str, ParsedModelOutput] = {}
        case_units: dict[str, list[str]] = defaultdict(list)
        for case_id, parsed in records:
            case_units[case_id].extend(parsed.required_unit_ids)
            for unit_id in parsed.required_unit_ids:
                if unit_id in parsed_by_unit:
                    raise ValueError(
                        f"run records contain duplicate receipt unit: {unit_id}"
                    )
                parsed_by_unit[unit_id] = parsed
        for case_id in sorted(case_units):
            scoreable_ids = tuple(
                unit.unit_id
                for unit in expected_units
                if unit.case_id == case_id and unit.should_score
            )
            if not scoreable_ids:
                continue
            aggregate = _merge_parsed_outputs(
                tuple(parsed_by_unit[unit_id] for unit_id in case_units[case_id]),
                required_unit_ids=scoreable_ids,
            )
            cases_by_model[model_id].append(
                ScoringCase(
                    case_id=case_id,
                    model_id=(
                        _display_model_id(
                            model_id,
                            "none",
                            include_ablation=True,
                        )
                        if include_ablation_in_model_id
                        else model_id
                    ),
                    parsed_output=aggregate,
                    outcome_labels=tuple(
                        labels_by_unit_id[unit_id] for unit_id in scoreable_ids
                    ),
                )
            )

    effective_base_rate = (
        _computed_base_rate(labels_by_unit_id.values())
        if base_rate is None
        else base_rate
    )
    summaries = tuple(
        score_cases(tuple(cases), base_rate=effective_base_rate)
        for _model_id, cases in sorted(cases_by_model.items())
    )
    if not summaries:
        raise ValueError("no scoreable units remain after locked receipt validation")
    return summaries


def _validate_locked_receipt_identity(
    record: Mapping[str, Any],
    *,
    forecast_release: ForecastRelease,
    unit: ForecastPredictionUnit,
    expected_run_identity_sha256: str | None,
    model_registry: ModelRegistry | None,
    expected_model_registry_sha256: str | None,
) -> None:
    """Validate receipt identity before any parser output reaches scoring."""

    if expected_run_identity_sha256 is None:
        raise ValueError("locked scoring requires the expected run identity")
    if model_registry is None:
        raise ValueError("locked scoring requires the frozen model registry")
    if expected_model_registry_sha256 is None:
        raise ValueError("locked scoring requires the expected model registry")
    if model_registry.source_sha256 != expected_model_registry_sha256:
        raise ValueError("frozen model registry bytes differ from expected registry")
    if _required_str(record, "schema_version") != str(PUBLIC_RUN_RECEIPT_V1):
        raise ValueError("run receipt schema differs from public receipt contract")
    if _required_str(record, "release_id") != forecast_release.release_id:
        raise ValueError("run receipt release_id differs from forecast release")
    if _required_sha256(record, "forecast_release_digest") != (
        forecast_release.release_digest
    ):
        raise ValueError("run receipt forecast release digest differs")
    run_identity = _required_sha256(record, "run_identity_sha256")
    if run_identity != expected_run_identity_sha256:
        raise ValueError("run receipt run identity differs from expected run")
    registry_sha256 = _required_sha256(record, "model_registry_sha256")
    if registry_sha256 != expected_model_registry_sha256:
        raise ValueError("run receipt model registry differs from frozen registry")
    model_key = _required_str(record, "model_key")
    provider, separator, model_id = model_key.partition(":")
    if not separator or not provider or not model_id:
        raise ValueError("run receipt model_key must be provider:model_id")
    try:
        entry = model_registry.get(provider, model_id)
    except KeyError as exc:
        raise ValueError(
            f"run receipt model_key is absent from frozen registry: {model_key}"
        ) from exc
    try:
        require_official_registry_entries((entry,))
    except ValueError as exc:
        raise ValueError(f"frozen model registry entry is not official: {exc}") from exc
    if _required_sha256(record, "model_registry_entry_sha256") != (
        model_registry_entry_sha256(entry)
    ):
        raise ValueError(
            "run receipt model registry entry differs from frozen registry"
        )
    if _required_str(record, "served_model_version") != entry.model_version_or_snapshot:
        raise ValueError("run receipt served model differs from frozen registry")
    repeat_index = record.get("repeat_index")
    if type(repeat_index) is not int or repeat_index != 1:
        raise ValueError("run receipt repeat_index must be exactly 1")
    expected_cell_id = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "case_id": unit.case_id,
                "repeat_index": repeat_index,
                "run_identity_sha256": run_identity,
                "unit_id": unit.unit_id,
            },
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    if _required_str(record, "cell_id") != expected_cell_id:
        raise ValueError("run receipt cell identity differs from unit identity")
    if _required_sha256(record, "prompt_sha256") != unit.prompt_sha256:
        raise ValueError("run receipt prompt identity differs from forecast release")
    _required_sha256(record, "request_body_sha256")
    if _required_str(record, "ablation") != "none":
        raise ValueError("run receipt ablation differs from forecast execution")
    if _required_str(record, "harness") != "native":
        raise ValueError("run receipt harness differs from forecast execution")


def _required_sha256(record: Mapping[str, Any], field_name: str) -> str:
    value = _required_str(record, field_name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256")
    return value


def _require_locked_provenance_inputs(
    *,
    expected_run_identity_sha256: str | None,
    model_registry: ModelRegistry | None,
    expected_model_registry_sha256: str | None,
) -> None:
    """Reject self-consistent receipt sets without frozen authority inputs."""

    if expected_run_identity_sha256 is None:
        raise ValueError("locked scoring requires the expected run identity")
    _validate_sha256_value(expected_run_identity_sha256, "expected run identity")
    if model_registry is None or expected_model_registry_sha256 is None:
        raise ValueError("locked scoring requires the frozen model registry")
    _validate_sha256_value(
        expected_model_registry_sha256,
        "expected model registry",
    )
    if model_registry.source_sha256 != expected_model_registry_sha256:
        raise ValueError("frozen model registry bytes differ from expected registry")


def _validate_sha256_value(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")


def _merge_parsed_outputs(
    outputs: Sequence[ParsedModelOutput],
    *,
    required_unit_ids: tuple[str, ...],
) -> ParsedModelOutput:
    """Combine per-receipt unit projections into one case-level output."""

    by_unit = {
        unit_id: output.prediction_for(unit_id)
        for output in outputs
        for unit_id in output.required_unit_ids
    }
    predictions: tuple[ParsedPrediction, ...] = tuple(
        by_unit[unit_id] for unit_id in required_unit_ids
    )
    raw_hash = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                [output.raw_output_sha256 for output in outputs],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    return ParsedModelOutput(
        status=_merged_parser_status(outputs),
        raw_output_sha256=raw_hash,
        required_unit_ids=required_unit_ids,
        predictions=predictions,
        issues=tuple(issue for output in outputs for issue in output.issues),
        extra_predictions=tuple(
            extra for output in outputs for extra in output.extra_predictions
        ),
        repair_attempted=any(output.repair_attempted for output in outputs),
        repair_applied=any(output.repair_applied for output in outputs),
    )


def _merged_parser_status(outputs: Sequence[ParsedModelOutput]) -> ParserStatus:
    if all(output.is_valid for output in outputs):
        if any(output.status is ParserStatus.REPAIRED_VALID for output in outputs):
            return ParserStatus.REPAIRED_VALID
        return ParserStatus.VALID
    priority = (
        ParserStatus.DUPLICATE_UNIT,
        ParserStatus.MISSING_UNIT,
        ParserStatus.INVALID_PROBABILITY,
        ParserStatus.EXTRA_UNIT,
        ParserStatus.INVALID_JSON,
        ParserStatus.REFUSAL,
        ParserStatus.INVALID_SCHEMA,
    )
    statuses = {output.status for output in outputs}
    return next(status for status in priority if status in statuses)


def score_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels: Sequence[ScoreLabel],
    *,
    base_rate: float | None,
    include_ablation_in_model_id: bool = False,
) -> tuple[ScoreSummary, ...]:
    """Group evaluation records by model and score them against locked labels."""

    if not run_records:
        raise ValueError("at least one run record is required")
    label_unit_ids = tuple(label.unit_id for label in labels)
    duplicate_unit_ids = sorted(
        unit_id for unit_id, count in Counter(label_unit_ids).items() if count > 1
    )
    if duplicate_unit_ids:
        raise ValueError(f"duplicate outcome labels for units: {duplicate_unit_ids}")
    labels_by_unit_id = {label.unit_id: label for label in labels}
    if not labels_by_unit_id:
        raise ValueError("at least one outcome label is required")
    label_unit_id_set = set(labels_by_unit_id)
    effective_base_rate = (
        _computed_base_rate(labels) if base_rate is None else base_rate
    )

    cases_by_model: dict[str, list[ScoringCase]] = defaultdict(list)
    for record in run_records:
        required_unit_ids = _required_str_tuple(record, "required_unit_ids")
        missing_labels = sorted(set(required_unit_ids) - label_unit_id_set)
        if missing_labels:
            raise ValueError(f"labels missing for required units: {missing_labels}")
        base_model_id = _record_model_id(record)
        model_id = (
            _display_model_id(
                base_model_id,
                _record_ablation(record),
                include_ablation=True,
            )
            if include_ablation_in_model_id
            else base_model_id
        )
        parsed = _record_parsed_output(record, required_unit_ids)
        cases_by_model[model_id].append(
            ScoringCase(
                case_id=_required_str(record, "case_id"),
                candidate_id=_optional_str(record, "candidate_id"),
                model_id=model_id,
                related_family_id=_optional_str(record, "related_family_id"),
                mdl_family_id=_optional_str(record, "mdl_family_id"),
                parsed_output=parsed,
                outcome_labels=tuple(
                    labels_by_unit_id[unit_id] for unit_id in required_unit_ids
                ),
            )
        )

    return tuple(
        score_cases(tuple(cases), base_rate=effective_base_rate)
        for _model_id, cases in sorted(cases_by_model.items())
    )


def _record_ablation(record: Mapping[str, Any]) -> str:
    return (
        _optional_str(record, "ablation")
        or _optional_str(record, "run_label")
        or "full_packet"
    )


def _display_model_id(model_id: str, ablation: str, *, include_ablation: bool) -> str:
    return f"{model_id}::{ablation}" if include_ablation else model_id


def _computed_base_rate(labels: Iterable[ScoreLabel]) -> float:
    outcomes = tuple(label.primary_outcome for label in labels)
    scored = tuple(outcome for outcome in outcomes if outcome is not None)
    if not scored:
        raise ValueError("cannot compute base rate without scored labels")
    return sum(scored) / len(scored)


def _record_model_id(record: Mapping[str, Any]) -> str:
    model_id = _optional_str(record, "model_id")
    if model_id is not None:
        return model_id
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        metadata_mapping = cast(Mapping[object, object], metadata)
        metadata_model = metadata_mapping.get("model_id")
        if isinstance(metadata_model, str) and metadata_model.strip():
            return metadata_model
    solver_id = _required_str(record, "solver_id")
    if ":" in solver_id:
        model_id = solver_id.split(":", maxsplit=1)[1]
        if not model_id.strip():
            raise ValueError("solver_id must include a non-empty model ID")
        return model_id
    return solver_id


def _record_parsed_output(
    record: Mapping[str, Any],
    required_unit_ids: tuple[str, ...],
) -> ParsedModelOutput:
    projection = record.get("parser_output")
    if projection is None:
        return parse_model_output(
            _required_str(record, "raw_output"),
            required_unit_ids=required_unit_ids,
        )
    if not isinstance(projection, Mapping):
        raise ValueError("parser_output must be an object")
    parsed = parsed_output_from_public_record(cast(Mapping[str, Any], projection))
    if parsed.required_unit_ids != required_unit_ids:
        raise ValueError("parser_output required_unit_ids does not match run record")
    return parsed


def _required(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in record:
        raise ValueError(f"{field_name} is required")
    return record[field_name]


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _required(record, field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_str_tuple(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    value = _required(record, field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list of strings")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        strings.append(item)
    return tuple(strings)

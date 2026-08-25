"""Score persisted evaluation-run records against locked outcome labels."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    parse_model_output,
    parsed_output_from_public_record,
)
from legalforecast.evals.scorers import ScoreSummary, ScoringCase, score_cases
from legalforecast.labeling.label_outcomes import OutcomeLabel


def score_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
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


def _computed_base_rate(labels: Iterable[OutcomeLabel]) -> float:
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

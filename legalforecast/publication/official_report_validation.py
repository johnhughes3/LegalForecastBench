"""Fail-closed validation for canonical official publication bundles."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object, read_jsonl_objects
from legalforecast.evals.baselines import BaselineTrainingExample
from legalforecast.evals.bootstrap import (
    ModelScoreInput,
    PairwiseDelta,
    paired_clustered_bootstrap,
)
from legalforecast.evals.output_parser import ParserIssueCode, ParserStatus
from legalforecast.evals.scorers import DEFAULT_LOG_LOSS_EPSILON, UnitScore

OFFICIAL_AGGREGATE_SCHEMA_VERSION = "legalforecast-official-aggregate-v1"
_REQUIRED_ARTIFACTS = frozenset(
    {
        "artifact-index.json",
        "artifact-manifest.json",
        "cycle-power.json",
        "report/leaderboard.html",
        "report/leaderboard.json",
        "run-cards/aggregate-run-card.json",
        "scores.json",
        "unit-scores.jsonl",
    }
)


@dataclass(frozen=True, slots=True)
class OfficialBundle:
    """Canonical public artifacts accepted for official rendering."""

    report: Mapping[str, Any]
    scores: Mapping[str, Any]
    run_card: Mapping[str, Any]
    cycle_power: Mapping[str, Any]
    unit_scores: tuple[Mapping[str, Any], ...]
    artifact_paths: tuple[str, ...]


def load_official_bundle(root: Path) -> OfficialBundle:
    missing = sorted(
        path for path in _REQUIRED_ARTIFACTS if not (root / path).is_file()
    )
    if missing:
        raise ValueError(
            "canonical official artifact is missing: " + ", ".join(missing)
        )
    report = _read_json(root / "report" / "leaderboard.json", "leaderboard")
    scores = _read_json(root / "scores.json", "score summary")
    run_card = _read_json(
        root / "run-cards" / "aggregate-run-card.json",
        "aggregate run card",
    )
    cycle_power = _read_json(root / "cycle-power.json", "cycle power")
    manifest = _read_json(root / "artifact-manifest.json", "artifact manifest")
    index = _read_json(root / "artifact-index.json", "artifact index")
    records = tuple(
        read_jsonl_objects(
            root / "unit-scores.jsonl",
            error_factory=ValueError,
            missing_message=lambda path: f"public unit scores do not exist: {path}",
            non_object_message=lambda path, line: (
                f"public unit score line {line} must be an object: {path}"
            ),
        )
    )
    _validate_bundle_provenance(
        root,
        report=report,
        scores=scores,
        run_card=run_card,
        cycle_power=cycle_power,
        manifest=manifest,
        index=index,
    )
    return OfficialBundle(
        report=report,
        scores=scores,
        run_card=run_card,
        cycle_power=cycle_power,
        unit_scores=records,
        artifact_paths=(
            *_string_sequence(manifest.get("artifacts"), "artifact manifest"),
            "artifact-index.json",
            "artifact-manifest.json",
        ),
    )


def _validate_bundle_provenance(
    root: Path,
    *,
    report: Mapping[str, Any],
    scores: Mapping[str, Any],
    run_card: Mapping[str, Any],
    cycle_power: Mapping[str, Any],
    manifest: Mapping[str, Any],
    index: Mapping[str, Any],
) -> None:
    for label, record in (
        ("leaderboard", report),
        ("scores", scores),
        ("aggregate run card", run_card),
        ("cycle power", cycle_power),
        ("artifact manifest", manifest),
        ("artifact index", index),
    ):
        if record.get("schema_version") != OFFICIAL_AGGREGATE_SCHEMA_VERSION:
            raise ValueError(
                f"{label} requires schema_version={OFFICIAL_AGGREGATE_SCHEMA_VERSION}"
            )

    cycle_ids = {
        _required_text(record, "cycle_id", label=label)
        for label, record in (
            ("leaderboard", report),
            ("scores", scores),
            ("aggregate run card", run_card),
            ("cycle power", cycle_power),
        )
    }
    if len(cycle_ids) != 1:
        raise ValueError(f"official artifact cycle_id mismatch: {sorted(cycle_ids)}")
    cycle_id = next(iter(cycle_ids))
    if run_card.get("run_type") != "official":
        raise ValueError("aggregate run card must declare run_type=official")
    if run_card.get("allow_incomplete_model_set") is not False:
        raise ValueError("official publication refuses incomplete model sets")

    manifest_paths = _string_sequence(manifest.get("artifacts"), "artifact manifest")
    required_payloads = _REQUIRED_ARTIFACTS - {
        "artifact-index.json",
        "artifact-manifest.json",
    }
    if not manifest_paths or not required_payloads.issubset(set(manifest_paths)):
        raise ValueError("artifact manifest is empty or missing canonical artifacts")
    index_rows = _mapping_rows(index.get("artifacts", ()))
    if not index_rows:
        raise ValueError("artifact index must contain canonical artifact records")
    indexed_paths: set[str] = set()
    for record in index_rows:
        relative = _required_text(record, "path", label="artifact index row")
        if relative in indexed_paths:
            raise ValueError(f"artifact index contains duplicate path={relative}")
        indexed_paths.add(relative)
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"artifact index path is missing or unsafe: {relative}")
        expected_hash = _required_text(record, "sha256", label="artifact index row")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_hash.removeprefix("sha256:") != actual_hash:
            raise ValueError(f"artifact hash mismatch: {relative}")
        expected_size = _required_int(record, "size_bytes", label="artifact index row")
        if expected_size != path.stat().st_size:
            raise ValueError(f"artifact size mismatch: {relative}")
    if indexed_paths != set(manifest_paths):
        raise ValueError("artifact index and artifact manifest path sets differ")

    expected_model_keys = _string_sequence(
        run_card.get("expected_model_keys"), "expected_model_keys"
    )
    registry_model_keys = _string_sequence(
        run_card.get("registry_model_keys"), "registry_model_keys"
    )
    expected_models = set(expected_model_keys)
    registry_models = set(registry_model_keys)
    if (
        not expected_models
        or len(expected_models) != len(expected_model_keys)
        or len(registry_models) != len(registry_model_keys)
        or expected_models != registry_models
    ):
        raise ValueError("official expected and registry model sets must match")
    case_count = _required_int(run_card, "case_count", label="aggregate run card")
    ablation_count = _required_int(
        run_card,
        "ablation_count",
        label="aggregate run card",
    )
    expected_rows = _required_int(
        run_card,
        "expected_matrix_rows",
        label="aggregate run card",
    )
    if expected_rows != case_count * ablation_count * len(expected_models):
        raise ValueError("aggregate run card has an incomplete expected model matrix")
    is_cycle_one = cycle_id == "cycle-1" or cycle_id.startswith("cycle-1-")
    if is_cycle_one and case_count != 100:
        raise ValueError("Cycle 1 official publication requires exactly 100 cases")

    cycle_record = _required_mapping(cycle_power, "cycle_power", "cycle power")
    if _required_text(cycle_record, "cycle_id", label="cycle power") != cycle_id:
        raise ValueError("nested cycle-power cycle_id differs from official cycle")
    if _required_text(cycle_record, "series", label="cycle power") != "official":
        raise ValueError("official publication requires cycle-power series=official")
    if (
        _required_int(cycle_record, "clean_motion_count", label="cycle power")
        != case_count
    ):
        raise ValueError(
            "cycle-power clean motion count differs from run-card case count"
        )
    report_cycle_power = _required_mapping(report, "cycle_power", "leaderboard")
    run_card_cycle_power = _required_mapping(
        run_card,
        "cycle_power",
        "aggregate run card",
    )
    if cycle_record != report_cycle_power or cycle_record != run_card_cycle_power:
        raise ValueError("cycle-power records differ across official artifacts")

    report_rows = _mapping_rows(report.get("rows", ()))
    score_rows = _mapping_rows(scores.get("summaries", ()))
    report_models = {
        _required_text(row, "model_id", label="leaderboard row") for row in report_rows
    }
    score_models = {
        _required_text(row, "model_id", label="score summary") for row in score_rows
    }
    if (
        not report_rows
        or report_models != score_models
        or len(report_models) != len(report_rows)
        or len(score_models) != len(score_rows)
    ):
        raise ValueError("leaderboard and score-summary model sets must match exactly")
    report_types = _row_types_by_model(report_rows, label="leaderboard")
    score_types = _row_types_by_model(score_rows, label="score summary")
    if report_types != score_types:
        raise ValueError("leaderboard and score-summary row types must match")
    evaluated_solvers = {
        _required_text(row, "solver_id", label="evaluated score summary")
        for row in score_rows
        if score_types[_required_text(row, "model_id", label="score summary")]
        == "model"
    }
    if evaluated_solvers != expected_models:
        raise ValueError(
            "frozen expected model keys must match evaluated score-summary solvers"
        )
    if _required_int(run_card, "model_count", label="aggregate run card") != len(
        score_rows
    ):
        raise ValueError("aggregate run-card model_count differs from score summaries")
    accounting_count = _required_int(
        run_card,
        "accounting_record_count",
        label="aggregate run card",
    )
    if accounting_count != sum(
        _required_int(row, "run_count", label="score summary") for row in score_rows
    ):
        raise ValueError(
            "aggregate accounting_record_count differs from score summaries"
        )
    _validate_baseline_provenance(root, run_card, report_rows, manifest_paths)


def _row_types_by_model(
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[str, str]:
    types: dict[str, str] = {}
    for row in rows:
        model_id = _required_text(row, "model_id", label=f"{label} row")
        row_type = _required_text(row, "row_type", label=f"{label} row")
        if row_type not in {"model", "baseline"}:
            raise ValueError(f"unsupported official row_type={row_type}")
        types[model_id] = row_type
    return types


def _validate_baseline_provenance(
    root: Path,
    run_card: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    manifest_paths: Sequence[str],
) -> None:
    baseline_ids = set(
        _string_sequence(run_card.get("baseline_model_ids"), "baseline_model_ids")
    )
    row_ids = {
        _required_text(row, "model_id", label="baseline row")
        for row in rows
        if _required_text(row, "row_type", label="leaderboard row") == "baseline"
    }
    allow_none = run_card.get("allow_no_baselines") is True
    reference = run_card.get("brier_skill_score_reference_model_id")
    if allow_none:
        if baseline_ids or row_ids or reference is not None:
            raise ValueError(
                "allow_no_baselines bundle must not invent baseline evidence"
            )
        return
    if not baseline_ids or baseline_ids != row_ids:
        raise ValueError("frozen baseline rows must match baseline_model_ids")
    if not isinstance(reference, str) or reference not in baseline_ids:
        raise ValueError("baseline reference must name a frozen baseline row")
    raw_period = run_card.get("baseline_training_period")
    if not isinstance(raw_period, Mapping):
        raise ValueError("frozen baselines require a baseline training period")
    period = cast(Mapping[str, Any], raw_period)
    period_start = _required_date(
        period,
        "training_period_start",
        label="baseline training period",
    )
    period_end = _required_date(
        period,
        "training_period_end",
        label="baseline training period",
    )
    if period_end < period_start:
        raise ValueError("baseline training period end precedes start")
    usage = _required_text(
        period, "judge_history_usage", label="baseline training period"
    )
    try:
        if not isinstance(json.loads(usage), Mapping):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(
            "baseline judge-history usage must be a JSON object"
        ) from error
    training_count = _required_int(
        run_card,
        "cycle_baseline_training_example_count",
        label="aggregate run card",
    )
    if training_count <= 0 or "baseline-training-examples.jsonl" not in manifest_paths:
        raise ValueError("frozen baselines require public training evidence")
    examples = tuple(
        BaselineTrainingExample.from_record(record)
        for record in read_jsonl_objects(
            root / "baseline-training-examples.jsonl",
            error_factory=ValueError,
            missing_message=lambda path: (
                f"baseline training evidence is missing: {path}"
            ),
            non_object_message=lambda path, line: (
                f"baseline training evidence line {line} must be an object: {path}"
            ),
        )
    )
    if len(examples) != training_count:
        raise ValueError(
            "declared baseline training count differs from public evidence"
        )
    example_keys = {(item.features.case_id, item.features.unit_id) for item in examples}
    if len(example_keys) != len(examples):
        raise ValueError("baseline training evidence contains duplicate case/unit rows")
    if any(item.decision_date <= period_end for item in examples):
        raise ValueError(
            "cycle baseline examples must postdate the frozen historical "
            "training period"
        )


def _summary_prevalence(score_summary: Mapping[str, Any]) -> float | None:
    summaries = _mapping_rows(
        score_summary.get("summaries", score_summary.get("rows", ()))
    )
    values = {
        value
        for row in summaries
        if (value := _optional_number(row, "base_rate")) is not None
    }
    return next(iter(values)) if len(values) == 1 else None


def validate_official_arithmetic(
    rows: Sequence[Mapping[str, Any]],
    *,
    report: Mapping[str, Any],
    score_summary: Mapping[str, Any],
    unit_scores: Sequence[Mapping[str, Any]],
    run_card: Mapping[str, Any],
    cycle_power: Mapping[str, Any],
) -> float | None:
    report_scores = _micro_briers_by_model(rows, label="leaderboard")
    score_rows = _mapping_rows(
        score_summary.get("summaries", score_summary.get("rows", ()))
    )
    summary_scores = _micro_briers_by_model(score_rows, label="score summary")
    for model_id in sorted(report_scores.keys() & summary_scores.keys()):
        if not math.isclose(
            report_scores[model_id],
            summary_scores[model_id],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"micro-Brier mismatch for {model_id}: leaderboard="
                f"{report_scores[model_id]} scores={summary_scores[model_id]}"
            )
    _validate_report_summary_alignment(rows, score_rows)

    if not unit_scores:
        raise ValueError("canonical official unit scores must not be empty")
    summary_by_model = {
        _required_text(row, "model_id", label="score summary"): row
        for row in score_rows
    }
    reconstructed: dict[str, list[UnitScore]] = {}
    unit_keys_by_model: dict[str, set[tuple[str, str]]] = {}
    outcomes: dict[tuple[str, str], float] = {}
    for record in unit_scores:
        score = _unit_score(record)
        model_id = score.model_id
        expected_brier = (score.probability_fully_dismissed - score.outcome) ** 2
        if not _close(score.brier, expected_brier):
            raise ValueError(
                f"reconstructed Brier mismatch for {model_id}/{score.case_id}/"
                f"{score.unit_id}: published={score.brier} reconstructed="
                f"{expected_brier}"
            )
        expected_log_loss = _binary_log_loss(
            score.probability_fully_dismissed,
            score.outcome,
        )
        if not _close(score.log_loss, expected_log_loss):
            raise ValueError(
                f"reconstructed log-loss mismatch for {model_id}/{score.case_id}/"
                f"{score.unit_id}"
            )
        reconstructed.setdefault(model_id, []).append(score)
        model_unit_keys = unit_keys_by_model.setdefault(model_id, set())
        model_unit_key = (score.case_id, score.unit_id)
        if model_unit_key in model_unit_keys:
            raise ValueError(
                f"duplicate public unit score for {model_id}/{score.case_id}/"
                f"{score.unit_id}"
            )
        model_unit_keys.add(model_unit_key)
        case_id = score.case_id
        unit_id = score.unit_id
        outcome = float(score.outcome)
        key = (case_id, unit_id)
        prior = outcomes.setdefault(key, outcome)
        if not _close(prior, outcome):
            raise ValueError(f"conflicting public outcomes for case/unit {key}")

    if set(reconstructed) != set(summary_by_model):
        raise ValueError("unit-score and score-summary model sets must match exactly")
    observed_prevalence = sum(outcomes.values()) / len(outcomes)
    expected_case_count = _required_int(
        run_card,
        "case_count",
        label="aggregate run card",
    )
    cycle_record = _required_mapping(cycle_power, "cycle_power", "cycle power")
    expected_unit_count = _required_int(
        cycle_record,
        "prediction_unit_count",
        label="cycle power",
    )
    for model_id, summary in summary_by_model.items():
        model_scores = reconstructed.get(model_id)
        if model_scores is None:
            raise ValueError(f"public unit scores missing model_id={model_id}")
        _validate_model_summary(
            model_id,
            summary,
            model_scores,
            prevalence=observed_prevalence,
            expected_case_count=expected_case_count,
            expected_unit_count=expected_unit_count,
        )
        _validate_public_accounting(summary)

    summary_prevalence = _summary_prevalence(score_summary)
    if summary_prevalence is None or not _close(
        summary_prevalence,
        observed_prevalence,
    ):
        raise ValueError(
            "realized prevalence mismatch: "
            f"scores={summary_prevalence} unit_scores={observed_prevalence}"
        )
    _validate_calibration_report(report, summary_by_model)
    _validate_bootstrap_intervals(report, rows, reconstructed)
    return observed_prevalence


def _validate_report_summary_alignment(
    report_rows: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
) -> None:
    summaries = {
        _required_text(row, "model_id", label="score summary"): row
        for row in score_rows
    }
    for row in report_rows:
        model_id = _required_text(row, "model_id", label="leaderboard row")
        summary = summaries[model_id]
        if row.get("row_type") != summary.get("row_type"):
            raise ValueError(f"row_type mismatch for {model_id}")
        for field in (
            "micro_brier",
            "macro_brier",
            "brier_skill_score",
            "log_loss",
            "ece",
            "invalid_output_rate",
            "refusal_rate",
            "defaulted_prediction_rate",
            "cost_per_case",
            "cost_per_prediction_unit",
            "mean_tool_calls_per_case",
            "p95_tool_calls_per_case",
            "mean_latency_ms",
            "p95_latency_ms",
        ):
            report_value = _required_number(row, field, label="leaderboard row")
            summary_value = _required_number(summary, field, label="score summary")
            if not _close(report_value, summary_value):
                raise ValueError(f"{field} mismatch for {model_id}")


def _unit_score(record: Mapping[str, Any]) -> UnitScore:
    outcome_value = _required_number(record, "outcome", label="unit score")
    if outcome_value not in {0.0, 1.0}:
        raise ValueError("unit score outcome must be binary")
    invalid_reason = record.get("invalid_reason")
    try:
        return UnitScore(
            case_id=_required_text(record, "case_id", label="unit score"),
            candidate_id=_optional_text(record.get("candidate_id")),
            related_family_id=_optional_text(record.get("related_family_id")),
            mdl_family_id=_optional_text(record.get("mdl_family_id")),
            model_id=_required_text(record, "model_id", label="unit score"),
            unit_id=_required_text(record, "unit_id", label="unit score"),
            probability_fully_dismissed=_required_number(
                record,
                "probability_fully_dismissed",
                label="unit score",
            ),
            outcome=int(outcome_value),
            brier=_required_number(record, "brier", label="unit score"),
            log_loss=_required_number(record, "log_loss", label="unit score"),
            parser_status=ParserStatus(
                _required_text(record, "parser_status", label="unit score")
            ),
            raw_output_sha256=_required_text(
                record,
                "raw_output_sha256",
                label="unit score",
            ),
            defaulted_prediction=_required_bool(
                record,
                "defaulted_prediction",
                label="unit score",
            ),
            invalid_reason=(
                ParserIssueCode(invalid_reason)
                if isinstance(invalid_reason, str)
                else None
            ),
            label_confidence=_optional_number(record, "label_confidence"),
        )
    except ValueError as error:
        raise ValueError(f"invalid canonical unit score: {error}") from error


def _validate_model_summary(
    model_id: str,
    summary: Mapping[str, Any],
    scores: Sequence[UnitScore],
    *,
    prevalence: float,
    expected_case_count: int,
    expected_unit_count: int,
) -> None:
    case_ids = {score.case_id for score in scores}
    if _required_int(summary, "case_count", label="score summary") != len(case_ids):
        raise ValueError(f"case_count mismatch for {model_id}")
    if len(case_ids) != expected_case_count:
        raise ValueError(
            f"scored case set does not match run-card count for {model_id}"
        )
    if _required_int(summary, "unit_count", label="score summary") != len(scores):
        raise ValueError(f"unit_count mismatch for {model_id}")
    if len(scores) != expected_unit_count:
        raise ValueError(
            f"scored unit set does not match cycle-power count for {model_id}"
        )
    briers = [score.brier for score in scores]
    micro_brier = sum(briers) / len(briers)
    by_case: dict[str, list[float]] = {}
    for score in scores:
        by_case.setdefault(score.case_id, []).append(score.brier)
    macro_brier = sum(sum(values) / len(values) for values in by_case.values()) / len(
        by_case
    )
    base_rate_brier = sum((prevalence - score.outcome) ** 2 for score in scores) / len(
        scores
    )
    expected = {
        "micro_brier": micro_brier,
        "macro_brier": macro_brier,
        "log_loss": sum(score.log_loss for score in scores) / len(scores),
        "base_rate": prevalence,
        "base_rate_brier": base_rate_brier,
        "brier_skill_score": (
            0.0 if base_rate_brier == 0 else 1 - (micro_brier / base_rate_brier)
        ),
        "invalid_output_rate": _case_status_rate(scores, refusal_only=False),
        "refusal_rate": _case_status_rate(scores, refusal_only=True),
        "defaulted_prediction_rate": (
            sum(score.defaulted_prediction for score in scores) / len(scores)
        ),
    }
    for field, reconstructed in expected.items():
        published = _required_number(summary, field, label="score summary")
        if not _close(published, reconstructed):
            raise ValueError(
                f"reconstructed {field} mismatch for {model_id}: "
                f"published={published} reconstructed={reconstructed}"
            )
    ece = _validate_ece_bins(model_id, summary, scores)
    if not _close(_required_number(summary, "ece", label="score summary"), ece):
        raise ValueError(f"reconstructed ece mismatch for {model_id}")


def _case_status_rate(scores: Sequence[UnitScore], *, refusal_only: bool) -> float:
    status_by_case: dict[str, ParserStatus] = {}
    for score in scores:
        prior = status_by_case.setdefault(score.case_id, score.parser_status)
        if prior is not score.parser_status:
            raise ValueError(f"conflicting parser status for case={score.case_id}")
    if refusal_only:
        count = sum(
            status is ParserStatus.REFUSAL for status in status_by_case.values()
        )
    else:
        count = sum(
            status not in {ParserStatus.VALID, ParserStatus.REPAIRED_VALID}
            for status in status_by_case.values()
        )
    return count / len(status_by_case)


def _validate_ece_bins(
    model_id: str,
    summary: Mapping[str, Any],
    scores: Sequence[UnitScore],
) -> float:
    bins = _mapping_rows(summary.get("ece_bins", ()))
    if not bins:
        raise ValueError(f"score summary has no calibration bins for {model_id}")
    bin_count = len(bins)
    weighted_error = 0.0
    for index, published in enumerate(bins):
        if _required_int(published, "bin_index", label="calibration bin") != index:
            raise ValueError(f"calibration bin index mismatch for {model_id}")
        lower = index / bin_count
        upper = (index + 1) / bin_count
        members = [
            score
            for score in scores
            if min(int(score.probability_fully_dismissed * bin_count), bin_count - 1)
            == index
        ]
        _assert_number(published, "lower", lower, label=f"calibration bin {model_id}")
        _assert_number(published, "upper", upper, label=f"calibration bin {model_id}")
        if _required_int(published, "unit_count", label="calibration bin") != len(
            members
        ):
            raise ValueError(f"calibration bin count mismatch for {model_id}")
        if not members:
            for field in (
                "mean_probability",
                "observed_rate",
                "absolute_calibration_error",
            ):
                if published.get(field) is not None:
                    raise ValueError(f"empty calibration bin {field} must be null")
            continue
        mean_probability = sum(
            score.probability_fully_dismissed for score in members
        ) / len(members)
        observed_rate = sum(score.outcome for score in members) / len(members)
        absolute_error = abs(mean_probability - observed_rate)
        _assert_number(
            published,
            "mean_probability",
            mean_probability,
            label=f"calibration bin {model_id}",
        )
        _assert_number(
            published,
            "observed_rate",
            observed_rate,
            label=f"calibration bin {model_id}",
        )
        _assert_number(
            published,
            "absolute_calibration_error",
            absolute_error,
            label=f"calibration bin {model_id}",
        )
        weighted_error += (len(members) / len(scores)) * absolute_error
    return weighted_error


def _validate_public_accounting(summary: Mapping[str, Any]) -> None:
    model_id = _required_text(summary, "model_id", label="score summary")
    for field in ("solver_id", "provider", "model_version_or_snapshot", "run_label"):
        _required_text(summary, field, label=f"score summary {model_id}")
    integers = {
        field: _required_int(summary, field, label=f"score summary {model_id}")
        for field in (
            "run_count",
            "request_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "tool_call_count",
            "allowed_tool_call_count",
            "denied_tool_call_count",
        )
    }
    if any(value < 0 for value in integers.values()):
        raise ValueError(f"public accounting values cannot be negative for {model_id}")
    if integers["run_count"] <= 0:
        raise ValueError(f"public accounting run_count must be positive for {model_id}")
    if integers["total_tokens"] != (
        integers["prompt_tokens"] + integers["completion_tokens"]
    ):
        raise ValueError(f"token accounting mismatch for {model_id}")
    if integers["tool_call_count"] != (
        integers["allowed_tool_call_count"] + integers["denied_tool_call_count"]
    ):
        raise ValueError(f"tool-call accounting mismatch for {model_id}")
    for field in (
        "mean_latency_ms",
        "p95_latency_ms",
        "total_estimated_cost",
        "cost_per_case",
        "cost_per_prediction_unit",
    ):
        value = _required_number(summary, field, label=f"score summary {model_id}")
        if value < 0:
            raise ValueError(f"{field} cannot be negative for {model_id}")
    total_cost = _required_number(
        summary,
        "total_estimated_cost",
        label=f"score summary {model_id}",
    )
    case_count = _required_int(summary, "case_count", label="score summary")
    _assert_number(
        summary,
        "cost_per_case",
        total_cost / case_count,
        label=f"score summary {model_id}",
    )
    if integers["run_count"] == case_count:
        unit_count = _required_int(summary, "unit_count", label="score summary")
        _assert_number(
            summary,
            "cost_per_prediction_unit",
            total_cost / unit_count,
            label=f"score summary {model_id}",
        )
    _assert_number(
        summary,
        "mean_tool_calls_per_case",
        integers["tool_call_count"] / integers["run_count"],
        label=f"score summary {model_id}",
    )


def _validate_calibration_report(
    report: Mapping[str, Any],
    summaries: Mapping[str, Mapping[str, Any]],
) -> None:
    tables = _mapping_rows(report.get("calibration_tables", ()))
    by_model = {
        _required_text(table, "model_id", label="calibration table"): table
        for table in tables
    }
    if len(tables) != len(by_model):
        raise ValueError("calibration tables contain duplicate model records")
    if set(by_model) != set(summaries):
        raise ValueError("calibration-table model set differs from score summaries")
    for model_id, table in by_model.items():
        summary = summaries[model_id]
        _assert_number(
            table,
            "ece",
            _required_number(summary, "ece", label="score summary"),
            label=f"calibration table {model_id}",
        )
        if table.get("bins") != summary.get("ece_bins"):
            raise ValueError(f"calibration bins differ for {model_id}")


def _validate_bootstrap_intervals(
    report: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    scores: Mapping[str, Sequence[UnitScore]],
) -> None:
    inference = paired_clustered_bootstrap(
        tuple(
            ModelScoreInput(model_id=model_id, unit_scores=tuple(model_scores))
            for model_id, model_scores in sorted(scores.items())
        )
    )
    published = _mapping_rows(report.get("pairwise_deltas", ()))
    by_pair = {
        frozenset(
            {
                _required_text(item, "model_a", label="pairwise delta"),
                _required_text(item, "model_b", label="pairwise delta"),
            }
        ): item
        for item in published
    }
    if len(published) != len(by_pair):
        raise ValueError("pairwise bootstrap intervals contain duplicate model pairs")
    if len(by_pair) != len(inference.pairwise_deltas):
        raise ValueError("pairwise bootstrap interval set is incomplete")
    for expected in inference.pairwise_deltas:
        item = by_pair.get(frozenset({expected.model_a, expected.model_b}))
        if item is None:
            raise ValueError("pairwise bootstrap interval set is incomplete")
        direction = 1.0 if item.get("model_a") == expected.model_a else -1.0
        values = (
            ("observed_delta", direction * expected.observed_delta),
            (
                "ci_low",
                expected.ci_low if direction > 0 else -expected.ci_high,
            ),
            (
                "ci_high",
                expected.ci_high if direction > 0 else -expected.ci_low,
            ),
        )
        for field, value in values:
            if not _close(_required_number(item, field, label="pairwise delta"), value):
                raise ValueError(
                    f"bootstrap interval mismatch for {expected.model_a}/"
                    f"{expected.model_b} field={field}"
                )
    _validate_row_intervals(rows, inference.pairwise_deltas)


def _validate_row_intervals(
    rows: Sequence[Mapping[str, Any]],
    deltas: Sequence[PairwiseDelta],
) -> None:
    model_rows = [row for row in rows if row.get("row_type") == "model"]
    interval_fields = (
        "delta_vs_best",
        "delta_vs_best_ci_low",
        "delta_vs_best_ci_high",
    )
    for row in rows:
        if row.get("row_type") == "baseline" and any(
            row.get(field) is not None for field in interval_fields
        ):
            raise ValueError("baseline rows cannot carry ranked intervals")
    best = min(
        model_rows,
        key=lambda row: _required_number(row, "micro_brier", label="leaderboard row"),
    )
    best_id = _required_text(best, "model_id", label="leaderboard row")
    for row in model_rows:
        model_id = _required_text(row, "model_id", label="leaderboard row")
        if model_id == best_id:
            if any(row.get(field) is not None for field in interval_fields):
                raise ValueError(
                    "best model row must not carry a delta-vs-best interval"
                )
            continue
        delta = next(
            (
                item
                for item in deltas
                if {item.model_a, item.model_b} == {model_id, best_id}
            ),
            None,
        )
        if delta is None:
            raise ValueError(f"missing row interval for {model_id}")
        direction = 1.0 if delta.model_a == model_id else -1.0
        expected = {
            "delta_vs_best": direction * delta.observed_delta,
            "delta_vs_best_ci_low": delta.ci_low if direction > 0 else -delta.ci_high,
            "delta_vs_best_ci_high": delta.ci_high if direction > 0 else -delta.ci_low,
        }
        for field, value in expected.items():
            if not _close(_required_number(row, field, label="leaderboard row"), value):
                raise ValueError(f"row bootstrap interval mismatch for {model_id}")


def _binary_log_loss(probability: float, outcome: int) -> float:
    bounded = min(
        max(probability, DEFAULT_LOG_LOSS_EPSILON),
        1 - DEFAULT_LOG_LOSS_EPSILON,
    )
    return -(outcome * math.log(bounded) + (1 - outcome) * math.log(1 - bounded))


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def _micro_briers_by_model(
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in rows:
        model_id = _first_str(row, ("model_id", "model_key", "solver_id"))
        score = _optional_number(row, "micro_brier")
        if model_id == "unknown" or score is None:
            continue
        if model_id in scores:
            raise ValueError(f"duplicate {label} model_id={model_id}")
        scores[model_id] = score
    return scores


def _required_text(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} requires non-empty {key}")
    return value


def _required_number(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> float:
    value = _optional_number(record, key)
    if value is None:
        raise ValueError(f"{label} requires numeric {key}")
    return value


def _required_int(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} requires integer {key}")
    return value


def _required_bool(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label} requires boolean {key}")
    return value


def _required_mapping(
    record: Mapping[str, Any],
    key: str,
    label: str,
) -> Mapping[str, Any]:
    value = record.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} requires object {key}")
    return cast(Mapping[str, Any], value)


def _required_date(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> date:
    value = _required_text(record, key, label=label)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} requires ISO date {key}") from error


def _string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{label} must be a list of strings")
    strings = tuple(cast(Sequence[object], value))
    if any(not isinstance(item, str) or not item.strip() for item in strings):
        raise ValueError(f"{label} must contain non-empty strings")
    return cast(tuple[str, ...], strings)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("optional text fields must be non-empty strings or null")
    return value


def _assert_number(
    record: Mapping[str, Any],
    field: str,
    expected: float,
    *,
    label: str,
) -> None:
    published = _required_number(record, field, label=label)
    if not _close(published, expected):
        raise ValueError(
            f"{label} {field} mismatch: published={published} reconstructed={expected}"
        )


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, Mapping):
            records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _first_str(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _optional_number(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)

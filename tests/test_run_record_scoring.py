from __future__ import annotations

import json

import pytest
from legalforecast.evals.output_parser import ParserStatus
from legalforecast.evals.run_record_scoring import score_run_records
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel


def test_score_run_records_groups_models_and_preserves_identity_precedence() -> None:
    labels = (_label("unit-a", True), _label("unit-b", False))
    summaries = score_run_records(
        (
            _run_record(
                model_id="model-z",
                metadata_model_id="ignored-metadata",
                solver_id="offline:ignored-solver",
                case_id="case-z",
            ),
            _run_record(
                metadata_model_id="model-a",
                solver_id="offline:ignored-solver",
                case_id="case-a",
            ),
            _run_record(solver_id="offline:model-a", case_id="case-b"),
        ),
        labels,
        base_rate=0.25,
    )

    assert tuple(summary.model_id for summary in summaries) == ("model-a", "model-z")
    assert tuple(summary.case_count for summary in summaries) == (2, 1)
    assert all(summary.base_rate == 0.25 for summary in summaries)


def test_score_run_records_computes_base_rate_from_scored_labels() -> None:
    summaries = score_run_records(
        (_run_record(model_id="model-a"),),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=None,
    )

    assert summaries[0].base_rate == 0.5


def test_score_run_records_excludes_ambiguous_units_and_all_ambiguous_cases() -> None:
    summaries = score_run_records(
        (
            _run_record(case_id="all-ambiguous", required_unit_ids=("unit-a",)),
            _run_record(case_id="mixed"),
        ),
        (_ambiguous_label("unit-a"), _label("unit-b", False)),
        base_rate=0.0,
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.case_count == 1
    assert summary.unit_count == 1
    assert tuple(score.unit_id for score in summary.unit_scores) == ("unit-b",)


def test_score_run_records_preserves_parser_accounting_for_ambiguous_units() -> None:
    raw_output = json.dumps(
        {
            "case_assessment": "Partial prediction.",
            "predictions": [
                {
                    "unit_id": "unit-a",
                    "probability_fully_dismissed": 0.8,
                }
            ],
        }
    )
    summaries = score_run_records(
        (_run_record(raw_output=raw_output),),
        (_label("unit-a", True), _ambiguous_label("unit-b")),
        base_rate=1.0,
    )

    summary = summaries[0]
    assert summary.unit_count == 1
    assert summary.invalid_output_rate == 1.0
    assert summary.unit_scores[0].parser_status is ParserStatus.MISSING_UNIT


def test_score_run_records_rejects_duplicate_outcome_label_unit_ids() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate outcome labels for units: \\['unit-a'\\]",
    ):
        score_run_records(
            (_run_record(),),
            (
                _label("unit-a", True),
                _label("unit-a", False),
                _label("unit-b", False),
            ),
            base_rate=None,
        )


def test_score_run_records_rejects_empty_solver_model_suffix() -> None:
    with pytest.raises(
        ValueError,
        match="solver_id must include a non-empty model ID",
    ):
        score_run_records(
            (_run_record(solver_id="offline:"),),
            (_label("unit-a", True), _label("unit-b", False)),
            base_rate=0.5,
        )


def test_score_run_records_can_include_ablation_in_model_identity() -> None:
    summaries = score_run_records(
        (
            _run_record(
                model_id="model-a",
                case_id="case-full",
                ablation="full_packet",
            ),
            _run_record(
                model_id="model-a",
                case_id="case-metadata",
                ablation="metadata_only",
            ),
        ),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=0.5,
        include_ablation_in_model_id=True,
    )

    assert tuple(summary.model_id for summary in summaries) == (
        "model-a::full_packet",
        "model-a::metadata_only",
    )


def test_score_run_records_rejects_computed_base_rate_without_scored_labels() -> None:
    with pytest.raises(
        ValueError,
        match="cannot compute base rate without scored labels",
    ):
        score_run_records(
            (_run_record(),),
            (_ambiguous_label("unit-a"), _ambiguous_label("unit-b")),
            base_rate=None,
        )


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("empty-runs", "at least one run record is required"),
        ("empty-labels", "at least one outcome label is required"),
        (
            "missing-label",
            "labels missing for required units: \\['unit-b'\\]",
        ),
    ],
)
def test_score_run_records_preserves_boundary_errors(
    scenario: str,
    message: str,
) -> None:
    run_records = () if scenario == "empty-runs" else (_run_record(),)
    labels = () if scenario == "empty-labels" else (_label("unit-a", True),)
    with pytest.raises(ValueError, match=message):
        score_run_records(run_records, labels, base_rate=0.5)


def _run_record(
    *,
    model_id: str | None = None,
    metadata_model_id: str | None = None,
    solver_id: str = "offline:model-fallback",
    case_id: str = "case-1",
    required_unit_ids: tuple[str, ...] = ("unit-a", "unit-b"),
    raw_output: str | None = None,
    ablation: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "case_id": case_id,
        "solver_id": solver_id,
        "required_unit_ids": list(required_unit_ids),
        "raw_output": raw_output
        if raw_output is not None
        else json.dumps(
            {
                "case_assessment": "Mixed outcome.",
                "predictions": [
                    {
                        "unit_id": unit_id,
                        "probability_fully_dismissed": (0.8 if index == 0 else 0.2),
                    }
                    for index, unit_id in enumerate(required_unit_ids)
                ],
            }
        ),
    }
    if model_id is not None:
        record["model_id"] = model_id
    if metadata_model_id is not None:
        record["metadata"] = {"model_id": metadata_model_id}
    if ablation is not None:
        record["ablation"] = ablation
    return record


def _label(unit_id: str, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.97,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )


def _ambiguous_label(unit_id: str) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=None,
        amendment_class=AmendmentClass.AMBIGUOUS,
        ambiguous=True,
        label_confidence=0.4,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )

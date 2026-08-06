from __future__ import annotations

import json

import pytest
from legalforecast.evals.run_record_scoring import score_run_records
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel


def test_score_run_records_groups_models_and_preserves_identity_precedence() -> None:
    labels = (_label("unit-a", True), _label("unit-b", False))
    summaries = score_run_records(
        (
            _run_record(model_id="model-z", case_id="case-z"),
            _run_record(metadata_model_id="model-a", case_id="case-a"),
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
) -> dict[str, object]:
    record: dict[str, object] = {
        "case_id": case_id,
        "solver_id": solver_id,
        "required_unit_ids": ["unit-a", "unit-b"],
        "raw_output": json.dumps(
            {
                "case_assessment": "Mixed outcome.",
                "predictions": [
                    {
                        "unit_id": "unit-a",
                        "probability_fully_dismissed": 0.8,
                    },
                    {
                        "unit_id": "unit-b",
                        "probability_fully_dismissed": 0.2,
                    },
                ],
            }
        ),
    }
    if model_id is not None:
        record["model_id"] = model_id
    if metadata_model_id is not None:
        record["metadata"] = {"model_id": metadata_model_id}
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

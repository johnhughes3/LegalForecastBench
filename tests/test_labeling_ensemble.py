from __future__ import annotations

import json

import pytest
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.labeling.ensemble import (
    EnsembleDecisionStatus,
    EnsembleRouteReason,
    LabelAuditSummary,
    LabelingModel,
    audit_ensemble_labels,
    enforce_label_audit_acceptance,
    evaluate_labeling_ensemble,
    run_labeling_models,
    sample_unanimous_labels_for_audit,
)


class _FixtureLabelingModel:
    def __init__(self, model_id: str, labels: tuple[OutcomeLabel, ...]) -> None:
        self.model_id = model_id
        self._labels = labels

    def label_units(self, labeling_inputs: object) -> tuple[OutcomeLabel, ...]:
        del labeling_inputs
        return self._labels


def test_unanimous_high_confidence_labels_auto_label_and_sample_audit() -> None:
    votes = tuple(
        vote
        for model_id in ("cheap-a", "cheap-b", "cheap-c")
        for vote in (
            _vote(model_id, _label("unit-1", dismissed=True, confidence=0.93)),
            _vote(model_id, _label("unit-2", dismissed=False, confidence=0.91)),
        )
    )

    result = evaluate_labeling_ensemble(votes, high_confidence_threshold=0.9)
    record = result.to_record()

    assert [label.unit_id for label in result.auto_labels] == ["unit-1", "unit-2"]
    assert result.lawyer_adjudicated_share == 0
    assert record["auto_label_count"] == 2
    assert json.dumps(record)

    sample = sample_unanimous_labels_for_audit(
        result,
        sample_size=2,
        strata_by_unit_id={"unit-1": "securities", "unit-2": "employment"},
        seed=20260514,
    )

    assert {decision.unit_id for decision in sample} == {"unit-1", "unit-2"}


def test_disagreement_low_confidence_and_ambiguous_labels_route_to_review() -> None:
    result = evaluate_labeling_ensemble(
        (
            _vote("cheap-a", _label("unit-disagreement", dismissed=True)),
            _vote("cheap-b", _label("unit-disagreement", dismissed=False)),
            _vote("cheap-c", _label("unit-disagreement", dismissed=True)),
            _vote("cheap-a", _label("unit-low", dismissed=True, confidence=0.7)),
            _vote("cheap-b", _label("unit-low", dismissed=True, confidence=0.92)),
            _vote("cheap-c", _label("unit-low", dismissed=True, confidence=0.91)),
            _vote("cheap-a", _ambiguous_label("unit-ambiguous")),
            _vote("cheap-b", _ambiguous_label("unit-ambiguous")),
            _vote("cheap-c", _ambiguous_label("unit-ambiguous")),
        ),
        high_confidence_threshold=0.9,
    )

    decisions_by_unit = {decision.unit_id: decision for decision in result.decisions}

    assert decisions_by_unit["unit-disagreement"].status is (
        EnsembleDecisionStatus.LAWYER_ADJUDICATION
    )
    assert decisions_by_unit["unit-disagreement"].route_reason is (
        EnsembleRouteReason.DISAGREEMENT
    )
    assert decisions_by_unit["unit-low"].route_reason is (
        EnsembleRouteReason.LOW_CONFIDENCE
    )
    assert decisions_by_unit["unit-ambiguous"].route_reason is (
        EnsembleRouteReason.AMBIGUOUS
    )
    assert result.lawyer_adjudicated_share == 1
    assert result.ambiguous_unit_count == 1


def test_ambiguous_labels_can_be_excluded_and_reported() -> None:
    result = evaluate_labeling_ensemble(
        (
            _vote("cheap-a", _ambiguous_label("unit-ambiguous")),
            _vote("cheap-b", _ambiguous_label("unit-ambiguous")),
            _vote("cheap-c", _ambiguous_label("unit-ambiguous")),
        ),
        exclude_ambiguous=True,
    )

    assert result.decisions[0].status is EnsembleDecisionStatus.EXCLUDED_AMBIGUOUS
    assert result.ambiguous_exclusion_count == 1
    assert result.lawyer_adjudicated_share == 0


def test_audit_acceptance_reports_rates_and_fails_closed() -> None:
    result = evaluate_labeling_ensemble(
        tuple(
            vote
            for model_id in ("cheap-a", "cheap-b", "cheap-c")
            for vote in (
                _vote(model_id, _label("unit-good", dismissed=True)),
                _vote(model_id, _label("unit-bad", dismissed=False)),
            )
        )
    )

    summary = audit_ensemble_labels(
        result,
        adjudicated_labels_by_unit_id={
            "unit-good": _label("unit-good", dismissed=True),
            "unit-bad": _label("unit-bad", dismissed=True),
        },
        human_blind_disagreement_rate=0.2,
    )

    assert isinstance(summary, LabelAuditSummary)
    assert summary.audited_unit_count == 2
    assert summary.llm_audited_error_rate == 0.5
    assert summary.human_blind_disagreement_rate == 0.2
    assert summary.passes_acceptance is False
    assert summary.to_record()["absolute_error_ceiling"] == 0.1

    with pytest.raises(ValueError, match="LLM label audit failed closed"):
        enforce_label_audit_acceptance(summary)

    passing = audit_ensemble_labels(
        result,
        adjudicated_labels_by_unit_id={
            "unit-good": _label("unit-good", dismissed=True),
            "unit-bad": _label("unit-bad", dismissed=False),
        },
        human_blind_disagreement_rate=0.2,
    )
    enforce_label_audit_acceptance(passing)


def test_audit_acceptance_fails_closed_on_absolute_error_ceiling() -> None:
    result = evaluate_labeling_ensemble(
        tuple(
            vote
            for model_id in ("cheap-a", "cheap-b", "cheap-c")
            for vote in (
                _vote(model_id, _label("unit-good", dismissed=True)),
                _vote(model_id, _label("unit-bad", dismissed=False)),
            )
        )
    )

    summary = audit_ensemble_labels(
        result,
        adjudicated_labels_by_unit_id={
            "unit-good": _label("unit-good", dismissed=True),
            "unit-bad": _label("unit-bad", dismissed=True),
        },
        human_blind_disagreement_rate=0.75,
    )

    assert summary.llm_audited_error_rate == 0.5
    assert summary.llm_audited_error_rate <= summary.human_blind_disagreement_rate
    assert summary.passes_acceptance is False
    with pytest.raises(ValueError, match="absolute ceiling"):
        enforce_label_audit_acceptance(summary)


def test_run_labeling_models_wraps_model_outputs_as_votes() -> None:
    models: tuple[LabelingModel, ...] = (
        _FixtureLabelingModel("cheap-a", (_label("unit-1", dismissed=True),)),
        _FixtureLabelingModel("cheap-b", (_label("unit-1", dismissed=True),)),
        _FixtureLabelingModel("cheap-c", (_label("unit-1", dismissed=True),)),
    )

    result = run_labeling_models(models, labeling_inputs=object())

    assert result.auto_labels[0].unit_id == "unit-1"
    assert result.decisions[0].model_ids == ("cheap-a", "cheap-b", "cheap-c")


def _vote(model_id: str, label: OutcomeLabel):
    from legalforecast.labeling.ensemble import EnsembleLabelVote

    return EnsembleLabelVote(
        model_id=model_id,
        unit_id=label.unit_id,
        label=label,
        confidence=label.label_confidence,
        rationale="Fixture label rationale.",
    )


def _label(
    unit_id: str,
    *,
    dismissed: bool,
    confidence: float = 0.95,
) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=confidence,
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
        supporting_citations=(
            OutcomeCitation(
                document_id="decision-1",
                excerpt="The order is unclear.",
            ),
        ),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )

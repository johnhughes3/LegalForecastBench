from __future__ import annotations

import json

import pytest
from legalforecast.labeling import (
    AmendmentClass,
    LaterProceduralChange,
    OutcomeCitation,
    OutcomeLabel,
)


def _citation() -> OutcomeCitation:
    return OutcomeCitation(
        document_id="decision-42",
        page=8,
        paragraph=2,
        excerpt="Count I is dismissed with leave to amend.",
    )


def _label(
    *,
    fully_dismissed: bool | None,
    amendment_class: AmendmentClass,
    ambiguous: bool = False,
) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id="count_i_issuer",
        fully_dismissed=fully_dismissed,
        amendment_class=amendment_class,
        ambiguous=ambiguous,
        label_confidence=0.94,
        supporting_citations=(_citation(),),
        first_written_disposition_id="decision-42",
        first_written_disposition_date="2026-05-18",
    )


def test_full_dismissal_with_leave_to_amend_sets_primary_and_secondary_labels() -> None:
    label = _label(
        fully_dismissed=True,
        amendment_class=(AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY),
    )

    assert label.primary_outcome == 1
    assert label.amendment_target_applicable is True
    assert label.conditional_amendment_target is True
    assert label.to_record()["amendment_class"] == (
        "dismissed_with_express_amendment_opportunity"
    )
    json.dumps(label.to_record())


def test_survival_in_any_material_respect_is_not_fully_dismissed() -> None:
    label = _label(
        fully_dismissed=False,
        amendment_class=AmendmentClass.NOT_FULLY_DISMISSED,
    )

    assert label.primary_outcome == 0
    assert label.amendment_target_applicable is False
    assert label.conditional_amendment_target is None


def test_mixed_defendant_outcomes_are_labeled_per_unit() -> None:
    issuer_label = _label(
        fully_dismissed=True,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
        ),
    )
    officer_label = OutcomeLabel(
        unit_id="count_i_officer",
        fully_dismissed=False,
        amendment_class=AmendmentClass.NOT_FULLY_DISMISSED,
        ambiguous=False,
        label_confidence=0.91,
        supporting_citations=(_citation(),),
        first_written_disposition_id="decision-42",
        first_written_disposition_date="2026-05-18",
    )

    assert issuer_label.primary_outcome == 1
    assert officer_label.primary_outcome == 0


def test_partial_theory_dismissal_does_not_count_as_full_dismissal() -> None:
    label = OutcomeLabel(
        unit_id="count_iv_contract",
        fully_dismissed=False,
        amendment_class=AmendmentClass.NOT_FULLY_DISMISSED,
        ambiguous=False,
        label_confidence=0.89,
        supporting_citations=(
            OutcomeCitation(
                document_id="decision-42",
                excerpt="The notice theory is dismissed, but Count IV survives.",
            ),
        ),
        first_written_disposition_id="decision-42",
        first_written_disposition_date="2026-05-18",
        notes="Dismissal of one theory did not dispose of the claim unit.",
    )

    assert label.primary_outcome == 0
    assert label.to_record()["fully_dismissed"] is False


def test_silence_on_leave_is_distinct_from_express_leave() -> None:
    label = _label(
        fully_dismissed=True,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
        ),
    )

    assert label.amendment_target_applicable is True
    assert label.conditional_amendment_target is False
    assert label.amendment_class == (
        AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
    )


def test_ambiguous_label_has_no_primary_scoring_outcome() -> None:
    label = _label(
        fully_dismissed=None,
        amendment_class=AmendmentClass.AMBIGUOUS,
        ambiguous=True,
    )

    assert label.primary_outcome is None
    assert label.amendment_target_applicable is False
    assert label.conditional_amendment_target is None


def test_later_procedural_changes_do_not_change_locked_primary_label() -> None:
    label = _label(
        fully_dismissed=True,
        amendment_class=(AmendmentClass.DISMISSED_WITH_EXPRESS_DENIAL_OF_LEAVE),
    )

    reconsidered = (
        label.with_later_procedural_change(LaterProceduralChange.RECONSIDERATION)
        .with_later_procedural_change(LaterProceduralChange.APPEAL)
        .with_later_procedural_change(LaterProceduralChange.AMENDED_COMPLAINT)
    )

    assert reconsidered.primary_outcome == 1
    assert reconsidered.first_written_disposition_id == "decision-42"
    assert reconsidered.later_procedural_changes == (
        LaterProceduralChange.RECONSIDERATION,
        LaterProceduralChange.APPEAL,
        LaterProceduralChange.AMENDED_COMPLAINT,
    )


def test_non_first_written_disposition_cannot_lock_label() -> None:
    with pytest.raises(ValueError, match="first written disposition"):
        OutcomeLabel(
            unit_id="count_i_issuer",
            fully_dismissed=True,
            amendment_class=(
                AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            ),
            ambiguous=False,
            label_confidence=0.9,
            supporting_citations=(_citation(),),
            first_written_disposition_id="reconsideration-99",
            first_written_disposition_date="2026-06-01",
            first_written_disposition_locked=False,
        )


def test_invalid_amendment_combinations_are_rejected() -> None:
    with pytest.raises(ValueError, match="dismissal amendment class"):
        _label(
            fully_dismissed=True,
            amendment_class=AmendmentClass.NOT_FULLY_DISMISSED,
        )

    with pytest.raises(ValueError, match="not_fully_dismissed"):
        _label(
            fully_dismissed=False,
            amendment_class=(
                AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY
            ),
        )

    with pytest.raises(ValueError, match="omit fully_dismissed"):
        _label(
            fully_dismissed=True,
            amendment_class=AmendmentClass.AMBIGUOUS,
            ambiguous=True,
        )

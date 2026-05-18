from __future__ import annotations

import json

import pytest
from legalforecast.labeling import (
    AmendmentClass,
    AmendmentSignal,
    StageBDecisionText,
    StageBLabelingInput,
    StageBMissingUnitFlag,
    StageBUnitFinding,
    UnitResolution,
    label_stage_b_outcomes,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation


def test_stage_b_labels_clean_grant_with_express_leave_to_amend() -> None:
    excerpt = "Count I is dismissed with leave to amend within 21 days."
    result = label_stage_b_outcomes(
        StageBLabelingInput(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=(_unit("count_i_issuer"),),
            decision_text=_decision(excerpt),
            unit_findings=(
                StageBUnitFinding(
                    unit_id="count_i_issuer",
                    resolution=UnitResolution.FULLY_DISMISSED,
                    amendment_signal=AmendmentSignal.EXPRESS_LEAVE_TO_AMEND,
                    supporting_excerpt=excerpt,
                    labeler_confidence=0.96,
                    page=12,
                ),
            ),
        )
    )

    label = result.labels_by_unit_id["count_i_issuer"]

    assert label.fully_dismissed is True
    assert label.primary_outcome == 1
    assert label.amendment_class == (
        AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY
    )
    assert label.conditional_amendment_target is True
    assert label.label_confidence == pytest.approx(0.96)
    assert label.supporting_citations[0].document_id == "decision-1"
    json.dumps(result.to_record())


def test_stage_b_labels_clean_denial_and_grant_in_part_as_survival() -> None:
    denial = "The motion to dismiss Count I against Issuer is denied."
    partial = "The damages theory is dismissed, but Count II survives."
    result = label_stage_b_outcomes(
        StageBLabelingInput(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=(
                _unit("count_i_issuer", count="I", claim_name="Fraud"),
                _unit("count_ii_issuer", count="II", claim_name="Contract"),
            ),
            decision_text=_decision(denial, partial),
            unit_findings=(
                StageBUnitFinding(
                    unit_id="count_i_issuer",
                    resolution=UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
                    amendment_signal=AmendmentSignal.NOT_APPLICABLE,
                    supporting_excerpt=denial,
                    labeler_confidence=0.94,
                ),
                StageBUnitFinding(
                    unit_id="count_ii_issuer",
                    resolution=UnitResolution.PARTIAL_DISMISSAL_ONLY,
                    amendment_signal=AmendmentSignal.NOT_APPLICABLE,
                    supporting_excerpt=partial,
                    labeler_confidence=0.88,
                ),
            ),
        )
    )

    assert result.labels_by_unit_id["count_i_issuer"].fully_dismissed is False
    assert result.labels_by_unit_id["count_ii_issuer"].fully_dismissed is False
    assert result.labels_by_unit_id["count_ii_issuer"].primary_outcome == 0


def test_stage_b_preserves_unit_specific_defendant_outcomes() -> None:
    issuer_excerpt = "Count I is dismissed as to the Issuer defendant."
    officer_excerpt = "The motion is denied as to the Officer defendants."
    result = label_stage_b_outcomes(
        StageBLabelingInput(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=(
                _unit("count_i_issuer", defendant_group="Issuer defendant"),
                _unit("count_i_officers", defendant_group="Officer defendants"),
            ),
            decision_text=_decision(issuer_excerpt, officer_excerpt),
            unit_findings=(
                StageBUnitFinding(
                    unit_id="count_i_issuer",
                    resolution=UnitResolution.FULLY_DISMISSED,
                    amendment_signal=AmendmentSignal.SILENT,
                    supporting_excerpt=issuer_excerpt,
                    labeler_confidence=0.93,
                ),
                StageBUnitFinding(
                    unit_id="count_i_officers",
                    resolution=UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
                    amendment_signal=AmendmentSignal.NOT_APPLICABLE,
                    supporting_excerpt=officer_excerpt,
                    labeler_confidence=0.9,
                ),
            ),
        )
    )

    assert result.labels_by_unit_id["count_i_issuer"].primary_outcome == 1
    assert result.labels_by_unit_id["count_i_officers"].primary_outcome == 0


def test_stage_b_maps_amendment_invitation_and_silence_on_leave() -> None:
    invitation = "Plaintiff may move for leave to amend Count III."
    silent = "Count IV is dismissed."
    result = label_stage_b_outcomes(
        StageBLabelingInput(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=(
                _unit("count_iii_issuer", count="III"),
                _unit("count_iv_issuer", count="IV"),
            ),
            decision_text=_decision(invitation, silent),
            unit_findings=(
                StageBUnitFinding(
                    unit_id="count_iii_issuer",
                    resolution=UnitResolution.FULLY_DISMISSED,
                    amendment_signal=AmendmentSignal.EXPRESS_INVITATION_TO_SEEK_LEAVE,
                    supporting_excerpt=invitation,
                    labeler_confidence=0.91,
                ),
                StageBUnitFinding(
                    unit_id="count_iv_issuer",
                    resolution=UnitResolution.FULLY_DISMISSED,
                    amendment_signal=AmendmentSignal.SILENT,
                    supporting_excerpt=silent,
                    labeler_confidence=0.89,
                ),
            ),
        )
    )

    invited = result.labels_by_unit_id["count_iii_issuer"]
    silent_label = result.labels_by_unit_id["count_iv_issuer"]

    assert invited.amendment_class == (
        AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY
    )
    assert invited.conditional_amendment_target is True
    assert silent_label.amendment_class == (
        AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
    )
    assert silent_label.conditional_amendment_target is False


def test_missing_unit_flag_routes_to_frozen_unit_workflow_without_creating_label() -> (
    None
):
    labeled_excerpt = "Count I is dismissed with prejudice."
    missing_excerpt = "The court also dismisses Count II against Issuer."
    result = label_stage_b_outcomes(
        StageBLabelingInput(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=(_unit("count_i_issuer"),),
            decision_text=_decision(labeled_excerpt, missing_excerpt),
            unit_findings=(
                StageBUnitFinding(
                    unit_id="count_i_issuer",
                    resolution=UnitResolution.FULLY_DISMISSED,
                    amendment_signal=AmendmentSignal.EXPRESS_DENIAL_OF_LEAVE,
                    supporting_excerpt=labeled_excerpt,
                    labeler_confidence=0.95,
                ),
            ),
            missing_unit_flags=(
                StageBMissingUnitFlag(
                    missing_unit_description=(
                        "Decision resolved Count II, which is absent from frozen units."
                    ),
                    supporting_excerpt=missing_excerpt,
                    notes="Route to blinded repair or exclusion.",
                ),
            ),
        )
    )

    record = result.to_record()

    assert len(result.labels) == 1
    assert result.requires_frozen_unit_workflow is True
    assert record["missing_unit_flags"][0]["route"] == (
        "frozen_unit_repair_or_exclusion"
    )
    assert record["missing_unit_flags"][0]["routed_to_frozen_unit_workflow"] is True


def test_stage_b_rejects_unknown_unit_findings_instead_of_creating_units() -> None:
    excerpt = "Count II is dismissed."

    with pytest.raises(ValueError, match="may not create prediction units"):
        label_stage_b_outcomes(
            StageBLabelingInput(
                candidate_id="cand-1",
                case_id="case-1",
                frozen_units=(_unit("count_i_issuer"),),
                decision_text=_decision(excerpt),
                unit_findings=(
                    StageBUnitFinding(
                        unit_id="count_ii_issuer",
                        resolution=UnitResolution.FULLY_DISMISSED,
                        amendment_signal=AmendmentSignal.SILENT,
                        supporting_excerpt=excerpt,
                        labeler_confidence=0.9,
                    ),
                ),
            )
        )


def test_stage_b_requires_supporting_excerpt_from_decision_text() -> None:
    with pytest.raises(ValueError, match="supporting_excerpt"):
        label_stage_b_outcomes(
            StageBLabelingInput(
                candidate_id="cand-1",
                case_id="case-1",
                frozen_units=(_unit("count_i_issuer"),),
                decision_text=_decision("The motion is denied."),
                unit_findings=(
                    StageBUnitFinding(
                        unit_id="count_i_issuer",
                        resolution=UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
                        amendment_signal=AmendmentSignal.NOT_APPLICABLE,
                        supporting_excerpt="Count I is dismissed.",
                        labeler_confidence=0.8,
                    ),
                ),
            )
        )


def _decision(*excerpts: str) -> StageBDecisionText:
    return StageBDecisionText(
        document_id="decision-1",
        entered_date="2026-05-18",
        text="\n".join(excerpts),
    )


def _unit(
    unit_id: str,
    *,
    count: str = "I",
    claim_name: str = "Section 10(b)",
    defendant_group: str = "Issuer",
) -> PredictionUnit:
    return PredictionUnit(
        unit_id=unit_id,
        count=count,
        claim_name=claim_name,
        defendant_group=defendant_group,
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.9,
        source_citations=(
            SourceCitation(
                document_id="mtd",
                docket_entry_number=12,
                excerpt="Motion challenges this unit.",
            ),
        ),
    )

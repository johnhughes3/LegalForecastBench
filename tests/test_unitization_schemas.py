from __future__ import annotations

import json

import pytest
from legalforecast.unitization import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)


def _citation() -> SourceCitation:
    return SourceCitation(
        document_id="034_motion_to_dismiss",
        docket_entry_number=34,
        page=12,
        paragraph=3,
        excerpt="Defendants move to dismiss Count I.",
    )


def test_prediction_unit_serializes_claim_defendant_unit() -> None:
    unit = PredictionUnit(
        unit_id="count_1_section_10b_issuer",
        count="I",
        claim_name="Section 10(b) / Rule 10b-5",
        defendant_group="Issuer defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.93,
        source_citations=(_citation(),),
    )

    record = unit.to_record()

    assert record["unit_id"] == "count_1_section_10b_issuer"
    assert record["challenge_scope"] == "entire_claim"
    assert record["grouping"] == "individual"
    assert record["should_score"] is True
    assert record["source_citations"][0]["document_id"] == "034_motion_to_dismiss"
    json.dumps(record)


def test_grouped_defendants_require_grouping_rationale() -> None:
    with pytest.raises(ValueError, match="grouping_rationale is required"):
        PredictionUnit(
            unit_id="count_2_section_20a_officers",
            count="II",
            claim_name="Section 20(a)",
            defendant_group="Officer defendants",
            challenged_by_motion=True,
            challenge_scope=ChallengeScope.ENTIRE_CLAIM,
            unit_confidence=0.8,
            source_citations=(_citation(),),
            grouping=DefendantGrouping.GROUPED,
        )


def test_grouped_defendants_can_share_common_motion_arguments() -> None:
    unit = PredictionUnit(
        unit_id="count_2_section_20a_officers",
        count="II",
        claim_name="Section 20(a)",
        defendant_group="Officer defendants",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.8,
        source_citations=(_citation(),),
        grouping=DefendantGrouping.GROUPED,
        grouping_rationale="The motion challenges all officer defendants together.",
    )

    assert unit.grouping is DefendantGrouping.GROUPED
    assert unit.to_record()["grouping_rationale"].startswith("The motion")


def test_separable_subclaim_requires_subclaim_description() -> None:
    with pytest.raises(ValueError, match="separable_subclaim is required"):
        PredictionUnit(
            unit_id="count_3_contract_notice_subclaim",
            count="III",
            claim_name="Breach of contract",
            defendant_group="Contract defendant",
            challenged_by_motion=True,
            challenge_scope=ChallengeScope.SEPARABLE_SUBCLAIM,
            unit_confidence=0.72,
            source_citations=(_citation(),),
        )


def test_partial_theory_challenge_remains_claim_level_unit() -> None:
    unit = PredictionUnit(
        unit_id="count_1_section_10b_issuer",
        count="I",
        claim_name="Section 10(b) / Rule 10b-5",
        defendant_group="Issuer defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.PARTIAL_THEORY_ONLY,
        unit_confidence=0.66,
        source_citations=(_citation(),),
        uncertainty_notes=(
            "Motion attacks falsity and scienter theories, not a separate claim."
        ),
    )

    assert unit.should_score is True
    assert unit.to_record()["challenge_scope"] == "partial_theory_only"


def test_unclear_units_are_explicitly_not_scored_without_repair() -> None:
    unit = PredictionUnit(
        unit_id="count_unknown_grouping",
        count="unknown",
        claim_name="Unclear statutory claim",
        defendant_group="Unclear defendant grouping",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.UNCLEAR,
        unit_confidence=0.2,
        source_citations=(_citation(),),
        uncertainty_notes="Complaint and motion use inconsistent count numbering.",
    )

    assert unit.should_score is False
    assert unit.to_record()["uncertainty_notes"].startswith("Complaint")


def test_confidence_and_citation_validation() -> None:
    with pytest.raises(ValueError, match="unit_confidence"):
        PredictionUnit(
            unit_id="count_1",
            count="I",
            claim_name="Example claim",
            defendant_group="Example defendant",
            challenged_by_motion=True,
            challenge_scope=ChallengeScope.ENTIRE_CLAIM,
            unit_confidence=1.1,
            source_citations=(_citation(),),
        )

    with pytest.raises(ValueError, match="source_citations"):
        PredictionUnit(
            unit_id="count_1",
            count="I",
            claim_name="Example claim",
            defendant_group="Example defendant",
            challenged_by_motion=True,
            challenge_scope=ChallengeScope.ENTIRE_CLAIM,
            unit_confidence=0.5,
            source_citations=(),
        )

    with pytest.raises(ValueError, match="docket_entry_number must be positive"):
        SourceCitation(document_id="bad", docket_entry_number=0)

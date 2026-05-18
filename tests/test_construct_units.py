from __future__ import annotations

import json

import pytest
from legalforecast.unitization import (
    ChallengeScope,
    DefendantGrouping,
    StageAConstructionInput,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    UnitizationReviewReason,
    construct_stage_a_units,
)


def _sources() -> tuple[StageASourceDocument, ...]:
    return (
        StageASourceDocument(
            document_id="complaint",
            role=StageADocumentRole.COMPLAINT,
            docket_entry_number=1,
        ),
        StageASourceDocument(
            document_id="mtd_memo",
            role=StageADocumentRole.MTD_MEMORANDUM,
            docket_entry_number=34,
        ),
        StageASourceDocument(
            document_id="opposition",
            role=StageADocumentRole.OPPOSITION,
            docket_entry_number=41,
        ),
    )


def _input(*seeds: StageAUnitSeed) -> StageAConstructionInput:
    return StageAConstructionInput(
        candidate_id="cand-2026-05-001",
        case_id="case-1",
        source_documents=_sources(),
        unit_seeds=seeds,
    )


def test_constructs_securities_issuer_and_officer_units() -> None:
    result = construct_stage_a_units(
        _input(
            StageAUnitSeed(
                count="I",
                claim_name="Section 10(b) / Rule 10b-5",
                defendant_names=("Acme Corp.",),
                source_document_ids=("mtd_memo",),
                citation_page=12,
                citation_excerpt="Issuer moves to dismiss Count I.",
            ),
            StageAUnitSeed(
                count="II",
                claim_name="Section 20(a)",
                defendant_names=("Jane Doe", "John Roe"),
                source_document_ids=("mtd_memo",),
                grouping=DefendantGrouping.GROUPED,
                group_label="Officer defendants",
                grouping_rationale=(
                    "The motion challenges the officer defendants together."
                ),
            ),
        )
    )

    assert result.is_clean is True
    assert [unit.claim_name for unit in result.units] == [
        "Section 10(b) / Rule 10b-5",
        "Section 20(a)",
    ]
    assert result.units[0].defendant_group == "Acme Corp."
    assert result.units[1].grouping is DefendantGrouping.GROUPED
    assert result.units[1].defendant_group == "Officer defendants"
    assert result.units[0].source_citations[0].docket_entry_number == 34
    json.dumps(result.to_record())


def test_grouped_underwriters_produce_one_grouped_unit_with_rationale() -> None:
    result = construct_stage_a_units(
        _input(
            StageAUnitSeed(
                count="III",
                claim_name="Securities Act Section 11",
                defendant_names=("Bank A", "Bank B", "Bank C"),
                source_document_ids=("mtd_memo",),
                grouping=DefendantGrouping.GROUPED,
                group_label="Underwriter defendants",
                grouping_rationale="The motion presents common arguments for all.",
            )
        )
    )

    assert len(result.units) == 1
    unit = result.units[0]
    assert unit.defendant_group == "Underwriter defendants"
    assert unit.grouping_rationale == "The motion presents common arguments for all."
    assert unit.should_score is True


def test_separate_defendants_with_distinct_arguments_remain_separate_units() -> None:
    result = construct_stage_a_units(
        _input(
            StageAUnitSeed(
                count="I",
                claim_name="Fraud",
                defendant_names=("Issuer",),
                source_document_ids=("mtd_memo",),
                citation_excerpt="Issuer argues no actionable misstatement.",
            ),
            StageAUnitSeed(
                count="I",
                claim_name="Fraud",
                defendant_names=("Auditor",),
                source_document_ids=("mtd_memo",),
                citation_excerpt="Auditor argues no duty or scienter.",
            ),
        )
    )

    assert [unit.defendant_group for unit in result.units] == ["Issuer", "Auditor"]
    assert result.units[0].unit_id != result.units[1].unit_id
    assert all(unit.grouping is DefendantGrouping.INDIVIDUAL for unit in result.units)


def test_partial_theory_challenge_remains_one_claim_level_unit() -> None:
    result = construct_stage_a_units(
        _input(
            StageAUnitSeed(
                count="IV",
                claim_name="Breach of contract",
                defendant_names=("Contract counterparty",),
                source_document_ids=("mtd_memo",),
                challenge_scope=ChallengeScope.PARTIAL_THEORY_ONLY,
                uncertainty_notes=(
                    "Motion attacks the notice theory but not a separate subclaim."
                ),
            )
        )
    )

    assert len(result.units) == 1
    assert result.units[0].challenge_scope is ChallengeScope.PARTIAL_THEORY_ONLY
    assert result.units[0].should_score is True
    assert result.review_items == ()


def test_unresolved_ambiguity_routes_unit_to_blinded_review() -> None:
    result = construct_stage_a_units(
        _input(
            StageAUnitSeed(
                count="unclear",
                claim_name="Unclear statutory claim",
                defendant_names=("Unclear defendants",),
                source_document_ids=("complaint", "mtd_memo"),
                challenge_scope=ChallengeScope.UNCLEAR,
                unit_confidence=0.35,
                uncertainty_notes=(
                    "Complaint and motion use inconsistent count numbering."
                ),
            )
        )
    )

    assert result.is_clean is False
    assert result.units[0].should_score is False
    assert result.review_items[0].reason == (
        UnitizationReviewReason.UNCLEAR_CLAIM_OR_DEFENDANT
    )
    assert result.review_items[0].source_document_ids == ("complaint", "mtd_memo")


def test_stage_a_rejects_decision_or_outcome_material() -> None:
    with pytest.raises(ValueError, match="exclude decisions/orders"):
        construct_stage_a_units(
            StageAConstructionInput(
                candidate_id="cand-1",
                case_id="case-1",
                source_documents=(
                    *_sources(),
                    StageASourceDocument(
                        document_id="decision",
                        role=StageADocumentRole.DECISION,
                    ),
                ),
                unit_seeds=(
                    StageAUnitSeed(
                        count="I",
                        claim_name="Fraud",
                        defendant_names=("Issuer",),
                        source_document_ids=("mtd_memo",),
                    ),
                ),
            )
        )


def test_multiple_defendants_require_grouping_or_separate_seeds() -> None:
    with pytest.raises(ValueError, match="exactly one defendant"):
        StageAUnitSeed(
            count="I",
            claim_name="Fraud",
            defendant_names=("Issuer", "Auditor"),
            source_document_ids=("mtd_memo",),
        )

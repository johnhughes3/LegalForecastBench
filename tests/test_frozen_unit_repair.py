from __future__ import annotations

from datetime import date

import pytest
from legalforecast.selection import ExclusionReason
from legalforecast.unitization import (
    BlindedUnitRepairRequest,
    ChallengeScope,
    FrozenUnitStatus,
    StageAConstructionInput,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    UnitRepairMethod,
    UnitRepairReason,
    construct_stage_a_units,
    exclude_for_missing_stage_a_unit,
    freeze_stage_a_units,
    repair_frozen_units,
)


def test_freeze_stage_a_units_marks_clean_units_before_labeling() -> None:
    frozen = freeze_stage_a_units(_stage_a_result())

    assert frozen.status is FrozenUnitStatus.FROZEN_CLEAN
    assert frozen.unit_missing_from_stage_a is False
    assert frozen.unitization_repaired is False
    assert frozen.to_manifest_fields()["unit_ids"] == ["count_i_issuer"]


def test_decision_informed_unit_creation_is_blocked() -> None:
    with pytest.raises(ValueError, match="decision materials"):
        BlindedUnitRepairRequest(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=_stage_a_result().units,
            predecision_source_documents=_predecision_sources(),
            repair_unit_seeds=(_repair_seed(),),
            missing_unit_description="Decision labeler spotted Count II.",
            decision_source_ids=("decision-99",),
        )


def test_blinded_repair_receives_only_predecision_materials_and_flags_manifest() -> (
    None
):
    request = BlindedUnitRepairRequest(
        candidate_id="cand-1",
        case_id="case-1",
        frozen_units=_stage_a_result().units,
        predecision_source_documents=_predecision_sources(),
        repair_unit_seeds=(_repair_seed(),),
        missing_unit_description="Count II was challenged but missing from Stage A.",
        notes="Repair adjudicator reviewed only complaint and MTD memo.",
    )

    repaired = repair_frozen_units(request)
    manifest = repaired.to_manifest_fields()

    assert repaired.status is FrozenUnitStatus.REPAIRED
    assert [unit.unit_id for unit in repaired.units] == [
        "count_i_issuer",
        "count_ii_issuer",
    ]
    assert manifest["unit_missing_from_stage_a"] is True
    assert manifest["unitization_repaired"] is True
    assert manifest["repair_method"] == UnitRepairMethod.BLINDED_PREDECISION_ADJUDICATOR
    assert (
        manifest["repair_reason"] == UnitRepairReason.MATERIAL_UNIT_MISSING_FROM_STAGE_A
    )
    assert manifest["is_scored"] is True


def test_blinded_repair_rejects_outcome_materials_even_without_source_ids() -> None:
    decision_document = StageASourceDocument(
        document_id="doc-decision",
        role=StageADocumentRole.DECISION,
        is_predecision_material=False,
        contains_target_outcome=True,
    )

    with pytest.raises(ValueError, match="pre-decision materials"):
        BlindedUnitRepairRequest(
            candidate_id="cand-1",
            case_id="case-1",
            frozen_units=_stage_a_result().units,
            predecision_source_documents=(*_predecision_sources(), decision_document),
            repair_unit_seeds=(_repair_seed(),),
            missing_unit_description="Count II was missing.",
        )


def test_unrepaired_missing_unit_enters_exclusion_ledger() -> None:
    excluded = exclude_for_missing_stage_a_unit(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        decision_date=date(2026, 5, 14),
        frozen_units=_stage_a_result().units,
        source_entry_ids=("entry-35",),
        source_document_ids=("doc-decision",),
        notes="Decision-stage labeler found a material missing unit; no blind repair.",
    )

    assert excluded.status is FrozenUnitStatus.EXCLUDED
    assert excluded.is_scored is False
    assert excluded.unit_missing_from_stage_a is True
    assert excluded.exclusion_entry is not None
    assert excluded.exclusion_entry.reason == (
        ExclusionReason.UNIT_MISSING_FROM_STAGE_A.value
    )
    assert excluded.to_manifest_fields()["exclusion"]["stage"] == "unitization"


def _stage_a_result():
    return construct_stage_a_units(
        StageAConstructionInput(
            candidate_id="cand-1",
            case_id="case-1",
            source_documents=_predecision_sources(),
            unit_seeds=(
                StageAUnitSeed(
                    unit_id="count_i_issuer",
                    count="I",
                    claim_name="Section 10(b)",
                    defendant_names=("Issuer",),
                    source_document_ids=("doc-complaint", "doc-motion"),
                    challenged_by_motion=True,
                    challenge_scope=ChallengeScope.ENTIRE_CLAIM,
                    unit_confidence=0.9,
                ),
            ),
        )
    )


def _repair_seed() -> StageAUnitSeed:
    return StageAUnitSeed(
        unit_id="count_ii_issuer",
        count="II",
        claim_name="Section 20(a)",
        defendant_names=("Issuer",),
        source_document_ids=("doc-complaint", "doc-motion"),
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.82,
    )


def _predecision_sources() -> tuple[StageASourceDocument, ...]:
    return (
        StageASourceDocument(
            document_id="doc-complaint",
            role=StageADocumentRole.COMPLAINT,
            docket_entry_number=1,
        ),
        StageASourceDocument(
            document_id="doc-motion",
            role=StageADocumentRole.MTD_MEMORANDUM,
            docket_entry_number=12,
        ),
    )

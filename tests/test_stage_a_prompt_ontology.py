from __future__ import annotations

import json

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.llm_pipeline import (
    _LlmDocument,
    _stage_a_seed,
    _stage_a_structural_review_prompt,
    _unitization_prompt,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation


def _selection() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Plaintiff v. Defendant",
        "court": "Example District Court",
        "docket_number": "1:26-cv-1",
        "target_motion_entry_numbers": [4],
        "decision_entry_numbers": [9],
    }


def _documents() -> list[_LlmDocument]:
    return [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="complaint",
            document_role=DocumentRole.COMPLAINT,
            docket_entry_number=1,
            description="Complaint",
            markdown="Count I asserts retaliation against Defendant.",
        ),
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown="Defendant moves to dismiss Count I as untimely.",
        ),
    ]


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Retaliation",
        defendant_group="Defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint"),),
    )


def _rules(prompt: str) -> str:
    return " ".join(json.loads(prompt)["rules"])


def test_unitizer_prompt_defines_claim_ground_boundary() -> None:
    rules = _rules(_unitization_prompt(_selection(), _documents()))

    assert "independently enforceable legal right" in rules
    assert "never itself a prediction unit" in rules
    assert "Section 230" in rules
    assert "SLUSA" in rules
    assert "partial_theory_only" in rules
    assert "actual moving defendant" in rules
    assert "nonmoving defendant" in rules
    assert "remedy" in rules


def test_structural_reviewer_prompt_uses_same_claim_ground_boundary() -> None:
    rules = _rules(
        _stage_a_structural_review_prompt(_selection(), _documents(), [_unit()])
    )

    assert "claim-defendant ledger" in rules
    assert "motion-scope matrix" in rules
    assert "never itself a prediction unit" in rules
    assert "independently enforceable legal right" in rules
    assert "nonmoving defendant" in rules


def test_provider_seed_routes_individual_label_and_unchallenged_unit_to_review() -> (
    None
):
    seed = _stage_a_seed(
        {
            "count": "Count I",
            "claim_name": "Retaliation",
            "defendant_names": ["Acme Corp."],
            "source_document_ids": ["complaint", "motion"],
            "challenged_by_motion": False,
            "challenge_scope": "entire_claim",
            "unit_confidence": 0.9,
            "grouping": "individual",
            "grouping_rationale": None,
            "group_label": "Corporate defendants",
            "separable_subclaim": None,
            "uncertainty_notes": None,
        }
    )

    assert seed.group_label is None
    assert seed.challenged_by_motion is False
    assert seed.challenge_scope is ChallengeScope.UNCLEAR
    assert seed.review_reason is not None
    assert "not challenged by the target motion" in (seed.uncertainty_notes or "")

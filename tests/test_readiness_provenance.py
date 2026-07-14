from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.ingestion.readiness_provenance import (
    ReadinessProvenanceError,
    verify_stage_a_readiness_provenance,
    verify_stage_b_readiness_provenance,
)
from legalforecast.labeling.llm_pipeline import merge_structural_flags_into_review_queue
from legalforecast.protocol import sha256_file
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    UnitizationReviewError,
    apply_unitization_reviews,
    canonical_records_sha256,
    canonical_sha256,
)

ROOT = Path(__file__).parents[1]
LABELING_REGISTRY = ROOT / "model_registries/cycle-1-labeling-2026-07-12.json"
JUDGE_REGISTRY = ROOT / "model_registries/cycle-1-stage-b-judges-2026-07-12.json"
GEMINI_KEY = "google:gemini-3.5-flash"


def test_stage_a_readiness_requires_complete_verified_structural_merge() -> None:
    fixture = _stage_a_fixture()
    verify_stage_a_readiness_provenance(**fixture)

    missing_audit = {**fixture, "structural_review_audit_records": []}
    with pytest.raises(ReadinessProvenanceError, match="cover every candidate"):
        verify_stage_a_readiness_provenance(**missing_audit)

    substituted_queue = {
        **fixture,
        "merged_review_records": [
            {
                "candidate_id": "cand-1",
                "review_id": "invented",
            }
        ],
    }
    with pytest.raises(ReadinessProvenanceError, match="verified original-plus"):
        verify_stage_a_readiness_provenance(**substituted_queue)

    broken_units = deepcopy(fixture["finalized_prediction_unit_records"])
    broken_units[0]["unitization_review_queue_sha256"] = "0" * 64
    with pytest.raises(UnitizationReviewError, match="review-queue hash link"):
        verify_stage_a_readiness_provenance(
            **{**fixture, "finalized_prediction_unit_records": broken_units}
        )


def test_stage_a_readiness_rejects_served_version_and_output_tampering() -> None:
    fixture = _stage_a_fixture()
    audits = deepcopy(fixture["structural_review_audit_records"])
    audits[0]["served_model_version"] = "gemini-flash-latest"
    with pytest.raises(ReadinessProvenanceError, match="served model version"):
        verify_stage_a_readiness_provenance(
            **{**fixture, "structural_review_audit_records": audits}
        )

    audits = deepcopy(fixture["structural_review_audit_records"])
    audits[0]["structural_flags_sha256"] = "0" * 64
    with pytest.raises(ReadinessProvenanceError, match="structural flags hash"):
        verify_stage_a_readiness_provenance(
            **{**fixture, "structural_review_audit_records": audits}
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda audit: audit.update(consensus_policy="majority"), "not unanimous"),
        (
            lambda audit: audit["model_outputs"].pop(),
            "model-output panel mismatch",
        ),
        (
            lambda audit: audit["model_outputs"][0]["metadata"].update(
                served_model_version="alias"
            ),
            "served model version",
        ),
        (
            lambda audit: audit["model_outputs"][0]["labels"][0][
                "supporting_citations"
            ][0].update(excerpt="not in the disposition"),
            "not verbatim",
        ),
        (
            lambda audit: audit["model_outputs"][0]["labels"].clear(),
            "cover every scorable unit",
        ),
    ],
)
def test_stage_b_readiness_rejects_policy_panel_and_voter_evidence_tampering(
    mutation,
    message: str,
) -> None:
    fixture = _stage_b_fixture()
    verify_stage_b_readiness_provenance(**fixture)
    audits = deepcopy(fixture["label_audit_records"])
    mutation(audits[0])

    with pytest.raises(ReadinessProvenanceError, match=message):
        verify_stage_b_readiness_provenance(
            **{**fixture, "label_audit_records": audits}
        )


def _stage_a_fixture() -> dict[str, object]:
    raw = [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "prediction_units": [
                {"unit_id": "unit-1", "should_score": True, "text": "Count I"}
            ],
        }
    ]
    registry = load_model_registry(LABELING_REGISTRY)
    gemini = next(
        entry for entry in registry.entries if entry.registry_key == GEMINI_KEY
    )
    registry_sha = sha256_file(LABELING_REGISTRY)
    flag_content = {
        "flag_type": "combined",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion-1"],
        "citation_excerpt": "Count I contains two theories.",
        "explanation": "The frozen unit may combine separately challenged theories.",
    }
    structural_flags = [
        {
            "schema_version": "legalforecast.stage_a_structural_flag.v1",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "reviewer_model_key": GEMINI_KEY,
            "model_registry_sha256": registry_sha,
            "raw_prediction_units_sha256": canonical_sha256(raw[0]),
            # The producer hashes the validated flag payload, before envelope fields
            # such as candidate_id are attached.
            "flag_sha256": canonical_sha256(flag_content),
            **flag_content,
        }
    ]
    merged_reviews = list(
        merge_structural_flags_into_review_queue([], structural_flags)
    )
    adjudications = [
        {
            "schema_version": ADJUDICATION_SCHEMA_VERSION,
            "adjudication_id": "adj-cand-1",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "review_ids": [merged_reviews[0]["review_id"]],
            "source_unit_ids": ["unit-1"],
            "disposition": "ACCEPT",
            "finalized_units": [],
            "adjudicator_id": "lawyer-1",
            "adjudication_notes": "Reviewed against blinded predecision materials.",
        }
    ]
    finalized = list(
        apply_unitization_reviews(
            prediction_unit_records=raw,
            review_records=merged_reviews,
            adjudication_records=adjudications,
        )
    )
    return {
        "selection_records": [{"candidate_id": "cand-1", "case_id": "case-1"}],
        "raw_prediction_unit_records": raw,
        "original_review_records": [],
        "structural_flag_records": structural_flags,
        "structural_review_audit_records": [
            {
                "stage": "llm-review-stage-a",
                "status": "flags_pending",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "model_key": GEMINI_KEY,
                "model_registry_sha256": registry_sha,
                "served_model_version": gemini.model_version_or_snapshot,
                "raw_prediction_units_sha256": canonical_sha256(raw[0]),
                "prompt_sha256": "1" * 64,
                "raw_output_sha256": "2" * 64,
                "structural_flags_sha256": canonical_records_sha256(structural_flags),
                "flag_count": 1,
                "metadata": {"served_model_version": gemini.model_version_or_snapshot},
            }
        ],
        "merged_review_records": merged_reviews,
        "finalized_prediction_unit_records": finalized,
        "adjudication_records": adjudications,
        "reviewer_registry_entries": registry.entries,
        "reviewer_registry_sha256": registry_sha,
        "reviewer_model_key": GEMINI_KEY,
    }


def _stage_b_fixture() -> dict[str, object]:
    stage_a = _stage_a_fixture()
    finalized = stage_a["finalized_prediction_unit_records"]
    registry = load_model_registry(JUDGE_REGISTRY)
    registry_sha = sha256_file(JUDGE_REGISTRY)
    model_keys = [entry.registry_key for entry in registry.entries]
    label = {
        "unit_id": "unit-1",
        "supporting_citations": [
            {"document_id": "decision-1", "excerpt": "Count I is dismissed."}
        ],
    }
    audit = {
        "stage": "llm-label",
        "status": "succeeded",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "consensus_policy": "unanimous",
        "model_keys": model_keys,
        "model_registry_sha256": registry_sha,
        "consensus_policy_sha256": canonical_sha256(
            {
                "consensus_policy": "unanimous",
                "model_keys": model_keys,
                "model_registry_sha256": registry_sha,
            }
        ),
        "model_outputs": [
            {
                "model_key": entry.registry_key,
                "raw_output_sha256": str(index) * 64,
                "metadata": {"served_model_version": entry.model_version_or_snapshot},
                "labels": [deepcopy(label)],
            }
            for index, entry in enumerate(registry.entries, start=1)
        ],
    }
    return {
        "finalized_prediction_unit_records": finalized,
        "label_audit_records": [audit],
        "judge_registry_entries": registry.entries,
        "judge_registry_sha256": registry_sha,
        "decision_text_by_candidate_and_document": {
            ("cand-1", "decision-1"): "The Court rules. Count I is dismissed."
        },
    }

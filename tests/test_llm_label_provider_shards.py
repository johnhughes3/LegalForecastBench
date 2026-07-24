from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.ingestion.decision_text_artifact import (
    VerifiedDecisionTextArtifact,
)
from legalforecast.labeling import llm_pipeline
from legalforecast.unitization.review import apply_unitization_reviews
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]


def _inputs() -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    VerifiedDecisionTextArtifact,
]:
    selection = [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "case_name": "Example v. Issuer",
            "court": "S.D.N.Y.",
            "docket_number": "1:26-cv-1",
            "decision_date": "2026-06-30",
            "target_motion_entry_numbers": [5],
            "decision_entry_numbers": [16],
        }
    ]
    finalized = apply_unitization_reviews(
        prediction_unit_records=[
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_group": "Issuer",
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.95,
                        "source_citations": [
                            {
                                "document_id": "mtd",
                                "docket_entry_number": 5,
                                "excerpt": "Defendants move to dismiss Count I.",
                            }
                        ],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
        review_records=(),
        adjudication_records=(),
    )
    text = "Count I is dismissed without leave to amend."
    artifact = VerifiedDecisionTextArtifact(
        records=(
            {
                "schema_version": "legalforecast.decision_text.v1",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "document_id": "decision",
                "entered_date": "2026-06-30",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "is_first_written_disposition": True,
                "contains_target_outcome": True,
                "model_visible": False,
            },
        ),
        decision_texts_sha256="sha256:" + "a" * 64,
        manifest_sha256="sha256:" + "b" * 64,
        run_card_sha256="sha256:" + "c" * 64,
        finalized_prediction_units_sha256="sha256:" + "d" * 64,
        finalized_unit_envelope_sha256s={"cand-1": "sha256:" + "e" * 64},
        input_commitments={},
    )
    return selection, finalized, artifact


def _response(entry: Any) -> SolverResponse:
    return SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "unit-1",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": (
                            "Count I is dismissed without leave to amend."
                        ),
                        "labeler_confidence": 0.97,
                    }
                ],
                "missing_unit_flags": [],
            }
        ),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": entry.provider, "model_id": entry.model_id},
    )


def test_provider_shards_call_only_selected_provider_and_merge_without_call(
    monkeypatch: MonkeyPatch,
) -> None:
    selection, finalized, artifact = _inputs()
    registry_path = ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
    entries = load_model_registry(registry_path).entries
    registry_sha = "sha256:" + hashlib.sha256(registry_path.read_bytes()).hexdigest()
    calls: list[str] = []

    def completion(entry: Any, *args: Any, **kwargs: Any) -> SolverResponse:
        del args, kwargs
        calls.append(entry.provider)
        return _response(entry)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    shard_audits: list[dict[str, Any]] = []
    for provider in ("google", "openai"):
        result = llm_pipeline.llm_label_cases(
            selection_records=selection,
            prediction_unit_records=finalized,
            decision_text_artifact=artifact,
            registry_entries=entries,
            model_registry_sha256=registry_sha,
            execution_provider=provider,
            defer_consensus=True,
        )
        assert result.records == ()
        assert len(result.audit_records) == 1
        audit = result.audit_records[0]
        assert audit["stage"] == "llm-label-provider-shard"
        assert audit["execution_provider"] == provider
        assert {output["model_key"] for output in audit["model_outputs"]} == {
            entry.registry_key for entry in entries if entry.provider == provider
        }
        shard_audits.append(audit)
    assert calls == ["google", "openai"]

    def forbidden_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args, kwargs
        raise AssertionError("provider-free merge must not call a provider")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", forbidden_completion)
    merged = llm_pipeline.merge_llm_label_provider_shards(
        selection_records=selection,
        prediction_unit_records=finalized,
        decision_text_artifact=artifact,
        registry_entries=entries,
        provider_shard_audit_records=shard_audits,
        model_registry_sha256=registry_sha,
    )

    assert len(merged.records) == 1
    assert merged.records[0]["unit_id"] == "unit-1"
    assert merged.records[0]["fully_dismissed"] is True
    assert merged.audit_records[0]["status"] == "succeeded"
    assert len(merged.audit_records[0]["model_outputs"]) == 2


def test_provider_shard_merge_fails_closed_on_missing_or_mutated_shard(
    monkeypatch: MonkeyPatch,
) -> None:
    selection, finalized, artifact = _inputs()
    registry_path = ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
    entries = load_model_registry(registry_path).entries
    registry_sha = "sha256:" + hashlib.sha256(registry_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda entry, *args, **kwargs: _response(entry),
    )
    google = llm_pipeline.llm_label_cases(
        selection_records=selection,
        prediction_unit_records=finalized,
        decision_text_artifact=artifact,
        registry_entries=entries,
        model_registry_sha256=registry_sha,
        execution_provider="google",
        defer_consensus=True,
    ).audit_records[0]
    openai = llm_pipeline.llm_label_cases(
        selection_records=selection,
        prediction_unit_records=finalized,
        decision_text_artifact=artifact,
        registry_entries=entries,
        model_registry_sha256=registry_sha,
        execution_provider="openai",
        defer_consensus=True,
    ).audit_records[0]

    with pytest.raises(llm_pipeline.LlmPipelineError, match="coverage differs"):
        llm_pipeline.merge_llm_label_provider_shards(
            selection_records=selection,
            prediction_unit_records=finalized,
            decision_text_artifact=artifact,
            registry_entries=entries,
            provider_shard_audit_records=[google],
            model_registry_sha256=registry_sha,
        )

    mutated = json.loads(json.dumps(openai))
    mutated["model_outputs"][0]["provider_prompt_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(llm_pipeline.LlmPipelineError, match="prompt differs"):
        llm_pipeline.merge_llm_label_provider_shards(
            selection_records=selection,
            prediction_unit_records=finalized,
            decision_text_artifact=artifact,
            registry_entries=entries,
            provider_shard_audit_records=[google, mutated],
            model_registry_sha256=registry_sha,
        )


def test_provider_shard_mode_requires_deferred_consensus() -> None:
    selection, finalized, artifact = _inputs()
    entries = load_model_registry(
        ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
    ).entries

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="requires both execution_provider and defer_consensus",
    ):
        llm_pipeline.llm_label_cases(
            selection_records=selection,
            prediction_unit_records=finalized,
            decision_text_artifact=artifact,
            registry_entries=entries,
            execution_provider="openai",
        )

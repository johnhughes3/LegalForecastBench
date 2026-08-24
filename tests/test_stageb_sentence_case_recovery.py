from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation
from pytest import MonkeyPatch

JsonRecord = dict[str, Any]


def _selection(candidate_id: str = "synthetic-candidate") -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": "synthetic-case",
        "decision_date": "2026-06-30",
        "case_name": "Synthetic v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "synthetic-docket",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "selected": True,
    }


def _unit_with_id(unit_id: str, count: str) -> PredictionUnit:
    return PredictionUnit(
        unit_id=unit_id,
        count=count,
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.9,
        source_citations=(
            SourceCitation(
                document_id="synthetic-motion",
                docket_entry_number=5,
                excerpt="Defendants move to dismiss Count I.",
            ),
        ),
    )


def _registry() -> llm_pipeline.ModelRegistryEntry:
    return llm_pipeline.ModelRegistryEntry.from_record(
        {
            "provider": "openai",
            "model_id": "synthetic-model",
            "display_name": "Synthetic model",
            "model_version_or_snapshot": "synthetic-model",
            "release_timestamp": "2026-05-18T00:00:00Z",
            "release_timestamp_source": "synthetic fixture",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-04-01",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "synthetic fixture",
            "input_token_price": 1.0,
            "output_token_price": 2.0,
            "known_cutoff_publicity_caveats": [],
        }
    )


_SOURCE_EXCERPT = (
    "Concluding that plaintiffs' claims are not federally preempted but that they "
    "have failed to plausibly plead causation, and that other grounds support "
    "dismissal of specific claims, the court grants defendants' motion to dismiss "
    "and also grants plaintiffs leave to replead."
)
_MODEL_EXCERPT = _SOURCE_EXCERPT[0].lower() + _SOURCE_EXCERPT[1:]
_UNIT_IDS = (
    "72025962_count_one_negligence_manufacturers_manufacturing_defendants",
    "72025962_count_two_negligence_distributor_mouser_electronics_inc",
    "72025962_count_three_negligence_per_se_all_defendants",
    "72025962_count_four_gross_negligence_all_defendants",
    "72025962_count_nine_wrongful_death_all_defendants",
    "72025962_count_ten_survival_action_all_defendants",
)


def test_stage_b_72025962_retained_replay_recovers_six_case_initial_excerpts(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Replay the retained v7 response without a provider call or source rewrite."""

    units = tuple(
        _unit_with_id(unit_id, f"Count {index}")
        for index, unit_id in enumerate(_UNIT_IDS, start=1)
    )
    raw_response = json.dumps(
        {
            "unit_findings": [
                {
                    "unit_id": unit.unit_id,
                    "resolution": "fully_dismissed",
                    "amendment_signal": "express_leave_to_amend",
                    "supporting_excerpt": _MODEL_EXCERPT,
                    "labeler_confidence": 0.95,
                }
                for unit in units
            ],
            "missing_unit_flags": [],
        }
    )
    response = SolverResponse(
        raw_output=raw_response,
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
    )
    provider_calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"output_text": response.raw_output}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    original_coerce = cast(Any, llm_pipeline)._coerced_excerpt

    def legacy_coerce(text: str, excerpt: str) -> str:
        if excerpt.strip() == _MODEL_EXCERPT:
            raise llm_pipeline.LlmPipelineError("retained v7 citation reconstruction")
        return original_coerce(text, excerpt)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    monkeypatch.setattr(llm_pipeline, "_coerced_excerpt", legacy_coerce)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    kwargs: dict[str, Any] = {
        "selection": {**_selection("72025962"), "case_id": "72025962"},
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="72025962-entry-85-decision",
            entered_date="2026-07-01",
            text=_SOURCE_EXCERPT,
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": units,
        "prompt": "retained v7 frozen label prompt",
        "registry_entry": _registry(),
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "retained-v7-cycle",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
        "max_provider_attempts": 1,
    }

    with pytest.raises(llm_pipeline.LlmResponseValidationError):
        cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    with sqlite3.connect(journal_path) as connection:
        failed = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json "
            "FROM provider_attempts"
        ).fetchone()
    assert failed is not None
    assert failed[0] == "reconstruction_failed"
    raw_response_json, normalized_response_json = failed[1:]

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail("retained replay must not call provider"),
    )
    monkeypatch.setattr(llm_pipeline, "_coerced_excerpt", original_coerce)
    kwargs["replay_only"] = True
    labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    assert len(labels) == len(_UNIT_IDS)
    assert all(
        label.supporting_citations[0].excerpt == _SOURCE_EXCERPT for label in labels
    )
    assert provider_calls == 1
    with sqlite3.connect(journal_path) as connection:
        row = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "normalized_response_json FROM provider_attempts"
        ).fetchall()
    assert row == [(1, "settled", raw_response_json, normalized_response_json)]


def test_stage_b_sentence_initial_case_recovery_returns_exact_source_slice() -> None:
    source = "The court reached its conclusion. " + _SOURCE_EXCERPT

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt(source, _MODEL_EXCERPT)
        == _SOURCE_EXCERPT
    )


def test_stage_b_sentence_initial_case_recovery_defers_to_normalized_exact_match() -> None:
    source = (
        _SOURCE_EXCERPT
        + " The court reached another conclusion.\n"
        + _MODEL_EXCERPT.replace(" ", "  ", 1)
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt(source, _MODEL_EXCERPT)
        == _MODEL_EXCERPT.replace(" ", "  ", 1)
    )


@pytest.mark.parametrize(
    "source, excerpt",
    [
        pytest.param(
            "The court is " + _SOURCE_EXCERPT, _MODEL_EXCERPT, id="mid-sentence"
        ),
        pytest.param(
            _SOURCE_EXCERPT.replace("Concluding that", "Concluding That", 1),
            _MODEL_EXCERPT,
            id="multiple-case-differences",
        ),
        pytest.param(
            _SOURCE_EXCERPT + " " + _SOURCE_EXCERPT,
            _MODEL_EXCERPT,
            id="ambiguous-authenticated-matches",
        ),
        pytest.param("X" + _SOURCE_EXCERPT, _MODEL_EXCERPT, id="word-boundary"),
    ],
)
def test_stage_b_sentence_initial_case_recovery_fails_closed(
    source: str,
    excerpt: str,
) -> None:
    with pytest.raises(llm_pipeline.LlmPipelineError):
        cast(Any, llm_pipeline)._coerced_excerpt(source, excerpt)

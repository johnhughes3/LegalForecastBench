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


def _selection() -> JsonRecord:
    return {
        "candidate_id": "synthetic-candidate",
        "case_id": "synthetic-case",
        "decision_date": "2026-06-30",
        "case_name": "Synthetic v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "synthetic-docket",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "selected": True,
    }


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="synthetic-unit",
        count="Count I",
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


def _unit_with_id(unit_id: str, count: str) -> PredictionUnit:
    unit = _unit()
    return PredictionUnit(
        unit_id=unit_id,
        count=count,
        claim_name=unit.claim_name,
        defendant_group=unit.defendant_group,
        challenged_by_motion=unit.challenged_by_motion,
        challenge_scope=unit.challenge_scope,
        unit_confidence=unit.unit_confidence,
        source_citations=unit.source_citations,
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


@pytest.mark.parametrize(
    ("decision_text", "response_excerpt", "expected_excerpt"),
    [
        pytest.param(
            "The court stated that defendants' request to dismiss Count I is denied.",
            "Accordingly, The court stated that defendants' request to dismiss "
            "Count I is denied.",
            "The court stated that defendants' request to dismiss Count I is denied.",
            id="allowlisted-leading-marker",
        ),
        pytest.param(
            "21 Because none of these allegations are a basis for\n"
            "22 Plaintiff\u2019s claims are futile.\n"
            "23 Plaintiff\u2019s causes of action under R2P are\n"
            "24 therefore dismissed with prejudice.",
            "Because none of these allegations are a basis for Plaintiff\u2019s claims "
            "are futile. Plaintiff\u2019s causes of action under R2P are therefore "
            "dismissed with prejudice.",
            "21 Because none of these allegations are a basis for\n"
            "22 Plaintiff\u2019s claims are futile.\n"
            "23 Plaintiff\u2019s causes of action under R2P are\n"
            "24 therefore dismissed with prejudice.",
            id="pdf-line-number-prefixes",
        ),
        pytest.param(
            "For the following reasons, the Court GRANTS Defendant\u2019s motion to "
            "dismiss Plaintiff\u2019s FAC.\n\n"
            "### I. Plaintiff Fails to State a Derivative-Work Copyright Claim",
            "Accordingly, the Court grants Defendant\u2019s motion to dismiss "
            "Plaintiff\u2019s FAC.\n\n"
            "### I. Plaintiff Fails to State a Derivative-Work Copyright Claim",
            "For the following reasons, the Court GRANTS Defendant\u2019s motion to "
            "dismiss Plaintiff\u2019s FAC.\n\n"
            "### I. Plaintiff Fails to State a Derivative-Work Copyright Claim",
            id="allowlisted-lead-in-with-ascii-case-drift",
        ),
        pytest.param(
            "Accordingly, the Court **GRANTED** the motion, and the parties must "
            "respond **within five days**. The request was **DENIED**.",
            "Accordingly, the Court GRANTED the motion, and the parties must "
            "respond within five days. The request was DENIED.",
            "Accordingly, the Court **GRANTED** the motion, and the parties must "
            "respond **within five days**. The request was **DENIED**.",
            id="omitted-markdown-emphasis-delimiters",
        ),
        pytest.param(
            "7 Thus, like in *Sound N*\n"
            "8 *Light*, Plaintiffs do not allege non-conclusory facts. See Compl.; "
            "2016 WL 7635950, at \\*4. The motion is **GRANTED.**",
            "Thus, like in Sound N Light, Plaintiffs do not allege non-conclusory "
            "facts. See Compl.; 2016 WL 7635950, at *4. The motion is GRANTED.",
            "7 Thus, like in *Sound N*\n"
            "8 *Light*, Plaintiffs do not allege non-conclusory facts. See Compl.; "
            "2016 WL 7635950, at \\*4. The motion is **GRANTED.**",
            id="rendered-markdown-line-map",
        ),
        pytest.param(
            "The court explained that the constitutional violation was established\n\n"
            "11\n\n\n\n---\n\n##### Page 12\n\n"
            "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
            "and the claim therefore survived.",
            "The court explained that the constitutional violation was established "
            "and the claim therefore survived.",
            "The court explained that the constitutional violation was established\n\n"
            "11\n\n\n\n---\n\n##### Page 12\n\n"
            "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
            "and the claim therefore survived.",
            id="parser-page-boundary",
        ),
    ],
)
def test_stage_b_reconstruction_recovers_citation_provider_free(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    decision_text: str,
    response_excerpt: str,
    expected_excerpt: str,
) -> None:
    """Recover citation-only drift without making a second provider call."""

    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "synthetic-unit",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": response_excerpt,
                        "labeler_confidence": 0.95,
                    }
                ],
                "missing_unit_flags": [],
            }
        ),
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
    )
    provider_calls = 0
    completion_calls = 0

    def provider_call() -> JsonRecord:
        nonlocal provider_calls
        provider_calls += 1
        return {"fixture": "provider-response"}

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        nonlocal completion_calls
        completion_calls += 1
        handler = kwargs["attempt_handler"]
        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    kwargs: dict[str, Any] = {
        "selection": _selection(),
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="synthetic-decision",
            entered_date="2026-07-01",
            text=decision_text,
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": (_unit(),),
        "prompt": "synthetic frozen label prompt",
        "registry_entry": _registry(),
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "synthetic-cycle",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
    }

    original_coerce = cast(Any, llm_pipeline)._coerced_excerpt

    def legacy_coerce(text: str, excerpt: str) -> str:
        if excerpt.strip() == response_excerpt:
            raise llm_pipeline.LlmPipelineError("legacy citation reconstruction")
        return original_coerce(text, excerpt)

    # Seed the exact retained failed response under the old reconstruction
    # behavior, then replay it through the new provider-free recovery path.
    monkeypatch.setattr(llm_pipeline, "_coerced_excerpt", legacy_coerce)
    with pytest.raises(llm_pipeline.LlmResponseValidationError):
        cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
    monkeypatch.setattr(llm_pipeline, "_coerced_excerpt", original_coerce)

    with sqlite3.connect(journal_path) as connection:
        failed = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json "
            "FROM provider_attempts"
        ).fetchone()
    assert failed is not None
    assert failed[0] == "reconstruction_failed"
    raw_response_json, normalized_response_json = failed[1:]

    labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    assert labels[0].supporting_citations[0].excerpt == expected_excerpt
    assert provider_calls == 1
    assert completion_calls == 2
    with sqlite3.connect(journal_path) as connection:
        row = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "normalized_response_json FROM provider_attempts"
        ).fetchall()
    assert row == [(1, "settled", raw_response_json, normalized_response_json)]


def test_stage_b_page_boundary_recovery_returns_exact_source_slice() -> None:
    decision_text = (
        "The court explained that the constitutional violation was established\n\n"
        "11\n\n\n\n---\n\n##### Page 12\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "and the claim therefore survived."
    )
    excerpt = (
        "The court explained that the constitutional violation was established "
        "and the claim therefore survived."
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)
        == decision_text
    )


@pytest.mark.parametrize(
    "invalid_boundary",
    [
        "##### Page 13",
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 13 of 13",
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12",
    ],
)
def test_stage_b_page_boundary_recovery_rejects_unqualified_markers(
    invalid_boundary: str,
) -> None:
    decision_text = (
        "The court explained that the constitutional violation was established\n\n"
        "11\n\n\n\n---\n\n"
        f"{invalid_boundary}\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "and the claim therefore survived."
    )
    excerpt = (
        "The court explained that the constitutional violation was established "
        "and the claim therefore survived."
    )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)


def test_stage_b_one_attempt_replay_normalizes_structurally_inapplicable_amendment(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Recover one retained response without a second provider call or byte rewrite."""

    decision_text = "The motion is denied as to Counts I, II, III, IV, and V."
    units = tuple(
        _unit_with_id(f"synthetic-unit-{index}", f"Count {count}")
        for index, count in enumerate(("I", "II", "III", "IV", "V"), start=1)
    )
    raw_response = json.dumps(
        {
            "unit_findings": [
                {
                    "unit_id": unit.unit_id,
                    "resolution": "survives_in_material_respect",
                    "amendment_signal": "silent",
                    "supporting_excerpt": decision_text,
                    "labeler_confidence": 0.91,
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
    completion_calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        nonlocal completion_calls, provider_calls
        completion_calls += 1
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {
                "output_text": response.raw_output,
                "model": "synthetic-model",
                "usage": {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
            }

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    original_completion = llm_pipeline.complete_live_prompt
    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    kwargs: dict[str, Any] = {
        "selection": _selection(),
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="synthetic-decision",
            entered_date="2026-07-01",
            text=decision_text,
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": units,
        "prompt": "synthetic frozen label prompt",
        "registry_entry": _registry(),
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "synthetic-cycle",
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

    def provider_must_not_run(request: object, timeout_seconds: float) -> JsonRecord:
        del request, timeout_seconds
        raise AssertionError("retained response replay must not call provider")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", original_completion)
    kwargs["transport"] = provider_must_not_run
    kwargs["environ"] = {"OPENAI_API_KEY": "synthetic-key"}
    labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    assert len(labels) == 5
    assert all(
        label.unit_resolution.value == "survives_in_material_respect"
        for label in labels
    )
    assert all(label.amendment_class.value == "not_fully_dismissed" for label in labels)
    assert provider_calls == 1
    assert completion_calls == 1
    with sqlite3.connect(journal_path) as connection:
        row = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "normalized_response_json FROM provider_attempts"
        ).fetchall()
    assert row == [(1, "settled", raw_response_json, normalized_response_json)]

    # Simulate a stop after journal settlement but before the caller persists
    # its create-only outer receipt. A fresh invocation must replay the same
    # settled response provider-free with the compatibility repair intact.
    replayed_labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
    assert [label.to_record() for label in replayed_labels] == [
        label.to_record() for label in labels
    ]
    assert provider_calls == 1
    assert completion_calls == 1


@pytest.mark.parametrize(
    ("resolution", "amendment_signal"),
    [
        ("fully_dismissed", "silent"),
        ("not_addressed_by_this_disposition", "silent"),
        ("ambiguous", "silent"),
        ("survives_in_material_respect", "express_leave_to_amend"),
    ],
)
def test_structural_amendment_normalization_has_negative_boundaries(
    resolution: str,
    amendment_signal: str,
) -> None:
    record = {
        "unit_id": "synthetic-unit",
        "resolution": resolution,
        "amendment_signal": amendment_signal,
    }
    normalized = cast(
        Any, llm_pipeline
    )._normalize_structurally_inapplicable_amendment_signal(record)
    assert normalized is record
    assert normalized["amendment_signal"] == amendment_signal


@pytest.mark.parametrize(
    "resolution",
    [
        "survives_in_material_respect",
        "partial_dismissal_only",
    ],
)
def test_structural_amendment_normalization_copies_only_inapplicable_silent(
    resolution: str,
) -> None:
    record = {
        "unit_id": "synthetic-unit",
        "resolution": resolution,
        "amendment_signal": "silent",
    }
    normalized = cast(
        Any, llm_pipeline
    )._normalize_structurally_inapplicable_amendment_signal(record)
    assert normalized is not record
    assert record["amendment_signal"] == "silent"
    assert normalized["amendment_signal"] == "not_applicable"


@pytest.mark.parametrize(
    ("decision_text", "response_excerpt"),
    [
        (
            "The court stated that defendants' request to dismiss Count I is denied.",
            "Accordingly, The court stated that defendants' request to dismiss "
            "Count I is granted.",
        ),
        (
            "21 The motion is denied because the claim survives.\n"
            "22 The court therefore permits discovery to proceed.",
            "The motion is denied because the claim survives. The court therefore "
            "permits discovery to continue.",
        ),
        (
            "21 The motion is denied because the claim survives.",
            "The motion is denied because the claim   survives.",
        ),
        (
            "For the following reasons, the Court GRANTS Defendant's motion.",
            "Accordingly, the Court grants Defendant's motion denied.",
        ),
        (
            "Accordingly, the Court **GRANTED** the motion.",
            "Accordingly, the Court granted the motion.",
        ),
        (
            "Accordingly, the Court **GRANTED** the motion.",
            "Accordingly, the Court GRANTED the request.",
        ),
    ],
)
def test_stage_b_excerpt_recovery_rejects_non_exact_remainder(
    decision_text: str, response_excerpt: str
) -> None:
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, response_excerpt)


def test_stage_b_excerpt_recovery_falls_back_after_unrelated_numbered_lines() -> None:
    decision_text = (
        "21 This numbered paragraph is unrelated to the requested citation.\n"
        "22 This consecutive numbered paragraph is also unrelated.\n"
        "The authenticated decision explains that jurisdiction remains proper "
        "because the complaint invokes federal law."
    )
    response_excerpt = (
        "The authenticated decision explains that jurisdiction remains proper "
        "because the complaint invokes federal statute."
    )

    assert cast(Any, llm_pipeline)._coerced_excerpt(
        decision_text, response_excerpt
    ) == (
        "The authenticated decision explains that jurisdiction remains proper "
        "because the complaint invokes federal law."
    )


def test_stage_b_rendered_markdown_recovery_rejects_word_drift() -> None:
    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_from_rendered_markdown(
            "7 The Court **GRANTED** the motion because the complaint is deficient.",
            "The Court GRANTED the motion because the complaint is insufficient.",
        )
        is None
    )


def test_stage_b_rendered_markdown_recovery_rejects_unbalanced_markup() -> None:
    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_from_rendered_markdown(
            "7 The Court *GRANTED the motion because the complaint is deficient.",
            "The Court GRANTED the motion because the complaint is deficient.",
        )
        is None
    )

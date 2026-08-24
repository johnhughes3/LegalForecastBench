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


def _selection(candidate_id: str = "synthetic-candidate") -> JsonRecord:
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


_CANDIDATE_71985792_DECISION_TEXT = (
    " 6 So, because Epidemic has not plausibly alleged any works on Meta's platform "
    "are  \n"
    " 7 substantially similar to or exact copies of its 1,000 copyright-protected "
    "Works, Epidemic fails to  \n"
    " 8 state a direct infringement claim.\n"
    " 18 any of its Works are substantially similar to any infringing work. So, "
    "Epidemic has not plausibly  \n"
    " 19 alleged any direct infringement, and the Court grants Meta's motion to "
    "dismiss Epidemic's  \n"
    " 20 inducement of infringement and contributory infringement causes of action."
)
_CANDIDATE_71985792_FIRST_EXCERPT = (
    "So, because Epidemic has not plausibly alleged any works on Meta's platform are "
    "substantially similar to or exact copies of its 1,000 copyright-protected Works, "
    "Epidemic fails to state a direct infringement claim."
)
_CANDIDATE_71985792_SECOND_EXCERPT = (
    "So, Epidemic has not plausibly alleged any direct infringement, and the Court "
    "grants Meta's motion to dismiss Epidemic's inducement of infringement and "
    "contributory infringement causes of action."
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
        pytest.param(
            _CANDIDATE_71985792_DECISION_TEXT,
            _CANDIDATE_71985792_FIRST_EXCERPT,
            "6 So, because Epidemic has not plausibly alleged any works on Meta's "
            "platform "
            "are  \n"
            " 7 substantially similar to or exact copies of its 1,000 "
            "copyright-protected "
            "Works, Epidemic fails to  \n"
            " 8 state a direct infringement claim.",
            id="candidate-71985792-indented-pdf-lines-7-8",
        ),
        pytest.param(
            _CANDIDATE_71985792_DECISION_TEXT,
            _CANDIDATE_71985792_SECOND_EXCERPT,
            "So, Epidemic has not plausibly  \n"
            " 19 alleged any direct infringement, and the Court grants Meta's "
            "motion to "
            "dismiss Epidemic's  \n"
            " 20 inducement of infringement and contributory infringement causes of "
            "action.",
            id="candidate-71985792-indented-pdf-lines-19-20",
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

    kwargs["replay_only"] = True
    labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    assert labels[0].supporting_citations[0].excerpt == expected_excerpt
    assert provider_calls == 1
    assert completion_calls == 1
    with sqlite3.connect(journal_path) as connection:
        row = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "normalized_response_json FROM provider_attempts"
        ).fetchall()
    assert row == [(1, "settled", raw_response_json, normalized_response_json)]


def test_stage_b_indented_pdf_line_recovery_requires_a_unique_numbered_match() -> None:
    decision_text = (
        " 7 repeated citation text appears here.\n"
        " 8 and continues on this line.\n"
        " 19 repeated citation text appears here.\n"
        " 20 and continues on this line."
    )
    excerpt = "repeated citation text appears here. and continues on this line."

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="ambiguous PDF line-number matches",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt_without_pdf_line_numbers(
            decision_text, excerpt
        )


def test_stage_b_pdf_line_recovery_rejects_ambiguous_unindented_matches() -> None:
    decision_text = (
        "7 repeated citation text appears here.\n"
        "8 and continues on this line.\n"
        "19 repeated citation text appears here.\n"
        "20 and continues on this line."
    )
    excerpt = "repeated citation text appears here. and continues on this line."

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="ambiguous PDF line-number matches",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)


def test_stage_b_pdf_line_recovery_prefers_exact_unindented_occurrence() -> None:
    decision_text = (
        " 7 repeated citation text\n 8 continues\n\nrepeated citation text continues"
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt(
            decision_text, "repeated citation text continues"
        )
        == "repeated citation text continues"
    )


def test_stage_b_pdf_line_recovery_rejects_first_line_isolated_prefix() -> None:
    decision_text = " 7 citation text\n 6 unrelated line"

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, "citation text")


def test_stage_b_indented_pdf_line_recovery_uses_rendered_mapping() -> None:
    decision_text = " 7 first line\n 8 second line"

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_from_rendered_markdown(
            decision_text, "first line second line"
        )
        == "7 first line\n 8 second line"
    )


@pytest.mark.parametrize(
    "decision_text",
    [
        " 7 isolated citation text.",
        "    7 over-indented citation text.\n    8 continues here.",
    ],
)
def test_stage_b_indented_pdf_line_recovery_rejects_unqualified_prefixes(
    decision_text: str,
) -> None:
    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_pdf_line_numbers(
            decision_text,
            "isolated citation text."
            if "isolated" in decision_text
            else "over-indented citation text. continues here.",
        )
        is None
    )


def test_stage_b_replay_only_rejects_unrelated_settled_journal(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    class UnrelatedSettledJournal:
        has_settled_attempt = True
        has_reconstruction_failure = False
        has_validated_response = False

        def latest_reconstruction_recovery_evidence(self) -> object:
            raise llm_pipeline.ProviderJournalError(
                "provider journal has no failed reconstruction to recover"
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        llm_pipeline,
        "_provider_attempt_journal",
        lambda **_: UnrelatedSettledJournal(),
    )
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail(
            "provider-free replay must reject before live completion"
        ),
    )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="provider-free Stage B replay has no retained response to settle",
    ):
        cast(Any, llm_pipeline)._llm_label_one_model(
            selection=_selection(),
            decision_text=llm_pipeline.StageBDecisionText(
                document_id="synthetic-decision",
                entered_date="2026-07-01",
                text="The motion is denied.",
            ),
            decision_text_commitment={"decision_texts_sha256": "sha256:" + "a" * 64},
            frozen_units=(_unit(),),
            prompt="synthetic frozen label prompt",
            registry_entry=_registry(),
            model_registry_sha256="b" * 64,
            transport=None,
            environ=None,
            timeout_seconds=1.0,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="synthetic-cycle",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_spend_authorities=None,
            provider_accounts=None,
            replay_only=True,
        )


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


def test_stage_b_page_boundary_recovery_does_not_prefix_post_boundary_excerpt() -> None:
    decision_text = (
        "The preceding page explains the issue.\n\n"
        "11\n\n\n\n---\n\n##### Page 12\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "and the claim\ntherefore survived."
    )
    excerpt = "and the claim therefore survived."

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)
        == "and the claim\ntherefore survived."
    )


def test_stage_b_page_boundary_recovery_rejects_unrelated_isolated_line_number() -> (
    None
):
    decision_text = (
        "7 The motion\nis denied.\n\n"
        "11\n\n\n\n---\n\n##### Page 12\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "The later page is unrelated."
    )
    excerpt = "The motion is denied."

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_page_boundary(
            decision_text, excerpt
        )
        is None
    )
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)


def test_stage_b_page_boundary_recovery_rejects_duplicate_matches() -> None:
    decision_text = (
        "The claim survives because the record is complete.\n\n"
        "11\n\n\n\n---\n\n##### Page 12\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "That conclusion follows.\n\n"
        "The claim survives because the record is complete.\n\n"
        "13\n\n\n\n---\n\n##### Page 14\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 14 of 14\n\n"
        "That conclusion follows."
    )
    excerpt = (
        "The claim survives because the record is complete. That conclusion follows."
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_page_boundary(
            decision_text, excerpt
        )
        is None
    )
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)


def test_stage_b_page_boundary_recovery_rejects_multi_boundary_match() -> None:
    decision_text = (
        "The first conclusion is established.\n\n"
        "11\n\n\n\n---\n\n##### Page 12\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 12 of 12\n\n"
        "The second conclusion is established.\n\n"
        "13\n\n\n\n---\n\n##### Page 14\n\n"
        "CASE SYNTHETIC-1 Doc. 80 Filed 07/08/26 Page 14 of 14\n\n"
        "The third conclusion is established."
    )
    excerpt = (
        "The first conclusion is established. The second conclusion is "
        "established. The third conclusion is established."
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_page_boundary(
            decision_text, excerpt
        )
        is None
    )
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)


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


def test_stage_b_local_markdown_recovery_ignores_unrelated_malformed_text() -> None:
    decision_text = (
        "An unrelated malformed marker * appears before the sentence.\n"
        "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim."
    )
    excerpt = "Therefore, Plaintiff fails to state a First Amendment Bivens claim."

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_single_markdown_emphasis(
            decision_text, excerpt
        )
        == "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim."
    )

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_single_markdown_emphasis(
            decision_text + " *",
            excerpt,
        )
        == "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim."
    )


@pytest.mark.parametrize(
    "decision_text",
    [
        "Therefore, Plaintiff fails to state a First Amendment *Bivens claim.",
        "Therefore, Plaintiff fails to state a First Amendment *Bivens*claim.",
        "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim. "
        + "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim.",
    ],
)
def test_stage_b_local_markdown_emphasis_recovery_fails_closed(
    decision_text: str,
) -> None:
    excerpt = "Therefore, Plaintiff fails to state a First Amendment Bivens claim."

    assert (
        cast(Any, llm_pipeline)._coerced_excerpt_without_single_markdown_emphasis(
            decision_text, excerpt
        )
        is None
    )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="supporting_excerpt does not appear in decision text",
    ):
        cast(Any, llm_pipeline)._coerced_excerpt(decision_text, excerpt)

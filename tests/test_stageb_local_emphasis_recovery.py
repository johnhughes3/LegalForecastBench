from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast.evals.inspect_task import SolverResponse
from pytest import MonkeyPatch
from tests.test_stageb_excerpt_recovery import _registry, _selection, _unit


def test_stage_b_72449171_retained_google_v7_replay_recovers_local_emphasis(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Replay the retained Google v7 response without a provider call."""

    decision_text = (
        "An unrelated malformed marker * appears before the sentence.\n"
        "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim."
    )
    response_excerpt = (
        "Therefore, Plaintiff fails to state a First Amendment Bivens claim."
    )
    source_excerpt = (
        "Therefore, Plaintiff fails to state a First Amendment *Bivens* claim."
    )
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

    def provider_call() -> dict[str, str]:
        nonlocal provider_calls
        provider_calls += 1
        return {"fixture": "retained-google-v7-response"}

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
        "selection": {**_selection("72449171"), "case_id": "72449171"},
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="72449171-decision",
            entered_date="2026-07-01",
            text=decision_text,
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": (_unit(),),
        "prompt": "retained Google v7 frozen label prompt",
        "registry_entry": llm_pipeline.ModelRegistryEntry.from_record(
            {
                **_registry().to_record(),
                "provider": "Google",
                "model_id": "gemini-3.5-flash",
                "model_version_or_snapshot": "gemini-3.5-flash",
            }
        ),
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "retained-google-v7-cycle",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
        "max_provider_attempts": 1,
    }

    original_coerce = cast(Any, llm_pipeline)._coerced_excerpt

    def legacy_coerce(text: str, excerpt: str) -> str:
        if excerpt.strip() == response_excerpt:
            raise llm_pipeline.LlmPipelineError("legacy citation reconstruction")
        return original_coerce(text, excerpt)

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

    assert labels[0].supporting_citations[0].excerpt == source_excerpt
    assert provider_calls == 1
    assert completion_calls == 1
    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "normalized_response_json FROM provider_attempts"
        ).fetchall()
    assert rows == [(1, "settled", raw_response_json, normalized_response_json)]

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.model_registry import load_model_registry
from pytest import MonkeyPatch
from tests.test_stageb_excerpt_recovery import _registry, _selection, _unit

JsonRecord = dict[str, Any]


@pytest.mark.parametrize(
    ("candidate_id", "provider"),
    [("73183894", "google"), ("72261437", "openai")],
)
def test_retained_stage_b_excerpt_failure_recovers_advisory_provider_free(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    candidate_id: str,
    provider: str,
) -> None:
    decision_text = llm_pipeline.StageBDecisionText(
        document_id=f"{candidate_id}-decision",
        entered_date="2026-07-01",
        text="The court dismisses Count I.",
    )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "synthetic-unit",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": "The provider's unmatched excerpt.",
                        "labeler_confidence": 0.95,
                    }
                ],
                "missing_unit_flags": [],
            }
        ),
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
        metadata={"provider": provider},
    )
    calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        nonlocal calls
        calls += 1
        handler = kwargs["attempt_handler"]
        handler.run_attempt(1, lambda: {"output_text": response.raw_output})
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    registry = _registry()
    if provider == "google":
        registry = llm_pipeline.ModelRegistryEntry.from_record(
            {**registry.to_record(), "provider": "google", "model_id": "gemini"}
        )
    journal_path = tmp_path / f"provider-attempts-{provider}.sqlite3"
    kwargs: JsonRecord = {
        "selection": {**_selection(candidate_id), "case_id": candidate_id},
        "decision_text": decision_text,
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": (_unit(),),
        "prompt": f"retained {provider} Stage B prompt",
        "registry_entry": registry,
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": f"retained-{candidate_id}",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
        "max_provider_attempts": 1,
    }

    with pytest.raises(llm_pipeline.LlmResponseValidationError):
        cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
    with sqlite3.connect(journal_path) as connection:
        before = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json, "
            "reconstructed_result_json FROM provider_attempts"
        ).fetchall()
    assert before[0][0] == "reconstruction_failed"

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail("advisory replay must not call provider"),
    )
    evidence_audit: JsonRecord = {}
    kwargs.update(
        replay_only=True,
        supporting_evidence_audit=evidence_audit,
    )
    labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)

    assert labels[0].supporting_citations[0].excerpt is None
    assert evidence_audit == {
        "supporting_evidence_status": "unresolved_advisory",
        "supporting_evidence_affected_unit_ids": ["synthetic-unit"],
    }
    assert calls == 1
    with sqlite3.connect(journal_path) as connection:
        after = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json, "
            "reconstructed_result_json FROM provider_attempts"
        ).fetchall()
    assert after == before


@pytest.mark.parametrize(
    "mutation",
    [
        {"unit_id": "not-frozen"},
        {"resolution": "not-an-enum"},
        {"drop_finding": True},
        {
            "resolution": "fully_dismissed",
            "amendment_signal": "not_applicable",
        },
    ],
)
def test_advisory_replay_rejects_structural_label_failures(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    mutation: JsonRecord,
) -> None:
    finding: JsonRecord = {
        "unit_id": "synthetic-unit",
        "resolution": "fully_dismissed",
        "amendment_signal": "express_denial_of_leave",
        "supporting_excerpt": "The provider's unmatched excerpt.",
        "labeler_confidence": 0.95,
    }
    finding.update(
        {key: value for key, value in mutation.items() if key != "drop_finding"}
    )
    raw_output = {
        "unit_findings": [] if mutation.get("drop_finding") else [finding],
        "missing_unit_flags": [],
    }
    response = SolverResponse(
        raw_output=json.dumps(raw_output),
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.01,
    )

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]
        handler.run_attempt(1, lambda: {"output_text": response.raw_output})
        handler.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    kwargs: JsonRecord = {
        "selection": _selection("negative"),
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-07-01",
            text="The court dismisses Count I.",
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": (_unit(),),
        "prompt": "negative advisory replay prompt",
        "registry_entry": _registry(),
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "negative-cycle",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
        "max_provider_attempts": 1,
    }
    with pytest.raises(llm_pipeline.LlmResponseValidationError):
        cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail(
            "invalid advisory replay must not call provider"
        ),
    )
    with pytest.raises((llm_pipeline.LlmPipelineError, ValueError)):
        cast(Any, llm_pipeline)._llm_label_one_model(
            **kwargs,
            replay_only=True,
            supporting_evidence_audit={},
        )


def test_provider_shard_merge_routes_union_of_advisory_units(
    monkeypatch: MonkeyPatch,
) -> None:
    from tests.test_llm_label_provider_shards import _inputs

    selection, finalized, artifact = _inputs()
    registry_path = Path(__file__).parents[1] / (
        "model_registries/cycle-1-stage-b-judges-2026-07-12.json"
    )
    entries = load_model_registry(registry_path).entries
    registry_sha = "sha256:" + hashlib.sha256(registry_path.read_bytes()).hexdigest()

    def completion(entry: Any, *args: Any, **kwargs: Any) -> SolverResponse:
        del args, kwargs
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
            input_tokens=1,
            output_tokens=1,
            estimated_cost=0.0,
            metadata={"provider": entry.provider, "model_id": entry.model_id},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    shard_audits: list[JsonRecord] = []
    for provider in ("google", "openai"):
        audit = llm_pipeline.llm_label_cases(
            selection_records=selection,
            prediction_unit_records=finalized,
            decision_text_artifact=artifact,
            registry_entries=entries,
            model_registry_sha256=registry_sha,
            execution_provider=provider,
            defer_consensus=True,
        ).audit_records[0]
        for output in audit["model_outputs"]:
            output["supporting_evidence_status"] = "unresolved_advisory"
            output["supporting_evidence_affected_unit_ids"] = ["unit-1"]
            output["labels"][0]["supporting_citations"][0]["excerpt"] = None
        shard_audits.append(audit)

    merged = llm_pipeline.merge_llm_label_provider_shards(
        selection_records=selection,
        prediction_unit_records=finalized,
        decision_text_artifact=artifact,
        registry_entries=entries,
        provider_shard_audit_records=shard_audits,
        model_registry_sha256=registry_sha,
    )

    audit = merged.audit_records[0]
    assert audit["status"] == "adjudication_pending"
    assert audit["human_verified"] is False
    assert audit["supporting_evidence_status"] == "unresolved_advisory"
    assert audit["supporting_evidence_affected_unit_ids"] == ["unit-1"]
    assert audit["pending_adjudication_unit_ids"] == ["unit-1"]
    assert audit["pending_adjudication_count"] == 1
    queue = audit["lawyer_review_queue"]
    assert len(queue) == 1
    assert queue[0]["route_reason"] == "unresolved_supporting_evidence"

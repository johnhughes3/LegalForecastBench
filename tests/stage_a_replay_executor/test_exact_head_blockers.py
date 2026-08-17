# pyright: reportPrivateUsage=false

"""Regressions for exact-head Stage A replay review blockers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.ingestion.stage_a_replay_executor import executor as executor_module
from legalforecast.ingestion.stage_a_replay_executor import journal as journal_module
from legalforecast.ingestion.stage_a_replay_executor import lineage as lineage_module
from legalforecast.ingestion.stage_a_replay_executor import (
    predecessor as predecessor_module,
)
from legalforecast.ingestion.stage_a_replay_executor import provider as provider_module
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    StageAReplayExecutorError,
    execute_stage_a_replay,
    load_replay_spec,
)
from legalforecast.labeling import llm_pipeline
from legalforecast.labeling.provider_journal import (
    ProviderCallIdentity,
    provider_prompt_logical_call_scope,
)
from tests.stage_a_replay_executor.fixtures import (
    FakeSpendMeter,
    settled_reviewer,
    settled_unitizer,
    write_spec,
)


def test_prompt_scoped_identity_separates_changed_successor_prompt() -> None:
    common = {
        "stage": "llm-unitize",
        "candidate_id": "cand-a",
        "model_key": "fixture:unitizer",
        "model_registry_sha256": "a" * 64,
        "account": "fixture-account",
        "prompt_contract": "claim-ontology-v5",
    }
    predecessor = ProviderCallIdentity(prompt="predecessor prompt", **common)
    successor = ProviderCallIdentity(
        prompt="successor prompt",
        logical_call_scope=provider_prompt_logical_call_scope("successor prompt"),
        **common,
    )
    same_successor = ProviderCallIdentity(
        prompt="successor prompt",
        logical_call_scope=provider_prompt_logical_call_scope("successor prompt"),
        **common,
    )

    assert successor.logical_call_key != predecessor.logical_call_key
    assert successor.logical_call_key == same_successor.logical_call_key


def test_runtime_and_llm_adapter_derive_the_same_prompt_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = "successor prompt"
    entry = SimpleNamespace(registry_key="fixture:unitizer", provider="fixture")
    runtime = object.__new__(provider_module.CanonicalProviderRuntime)
    runtime.unitizer_entry = entry
    runtime.accounts = {"fixture": "fixture-account"}
    runtime.spec = SimpleNamespace(model_registry_sha256="a" * 64)
    runtime.lineage = SimpleNamespace(
        successor_parser_records=(),
        successor_markdown_root=Path("/synthetic"),
        successor_markdown_bytes={},
    )
    monkeypatch.setattr(
        llm_pipeline,
        "stage_a_unitization_prompt_records",
        lambda **_kwargs: ({"prompt": prompt},),
    )
    request = SimpleNamespace(
        candidate_id="cand-a",
        packet=SimpleNamespace(selection_record={}),
    )

    identity, _entry, _account, _stage = runtime.call_identity(
        request,
        stage="unitizer",
        unitize=None,
    )

    expected_scope = provider_prompt_logical_call_scope(prompt)
    assert identity.logical_call_scope == expected_scope
    assert (
        llm_pipeline._provider_attempt_journal(
            path=None,
            stage="llm-unitize",
            candidate_id="cand-a",
            prompt=prompt,
            registry_entry=entry,
            account="fixture-account",
            model_registry_sha256="a" * 64,
            cycle_cap_usd=1.0,
            cycle_id=None,
            provider_cycle_caps_sha256=None,
            provider_attempt_namespace="claim-ontology-v5",
            provider_logical_call_scope=identity.logical_call_scope,
        )
        is None
    )
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="logical-call scope differs from the exact prompt",
    ):
        llm_pipeline._provider_attempt_journal(
            path=None,
            stage="llm-unitize",
            candidate_id="cand-a",
            prompt=prompt,
            registry_entry=entry,
            account="fixture-account",
            model_registry_sha256="a" * 64,
            cycle_cap_usd=1.0,
            cycle_id=None,
            provider_cycle_caps_sha256=None,
            provider_attempt_namespace="claim-ontology-v5",
            provider_logical_call_scope=provider_prompt_logical_call_scope(
                "different prompt"
            ),
        )


def test_non_reconstruction_journal_failure_reserves_three_fresh_attempts() -> None:
    rows = (
        {
            "attempt_ordinal": 1,
            "status": "failed",
        },
    )

    assert journal_module._maximum_new_attempts(rows, stage="unitizer") == 3


def test_predecessor_namespace_mismatch_halts_before_binder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsed = load_replay_spec(write_spec(tmp_path, candidate_ids=("cand-a",)))
    verified = lineage_module.verify_replay_lineage(parsed)
    mismatched = replace(
        verified,
        unitizer_namespace="claim-ontology-v4",
    )
    binder_called = False

    def forbidden_binder(**_kwargs: object) -> object:
        nonlocal binder_called
        binder_called = True
        raise AssertionError("binder opened on unverified predecessor namespaces")

    monkeypatch.setattr(
        executor_module, "verify_replay_lineage", lambda _spec: mismatched
    )
    monkeypatch.setattr(
        executor_module,
        "bind_predecessor_stage_a_lineage",
        forbidden_binder,
    )

    result = execute_stage_a_replay(
        parsed,
        unitizer=settled_unitizer,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert binder_called is False
    assert result.to_record()["halt_evidence"] == {
        "status": "halted_on_preflight_failure",
        "reason": "predecessor Stage A unitizer namespace is not frozen v5",
        "failure_type": "StageAReplayExecutorError",
        "provider_accessed": False,
    }


def test_authenticated_run_card_namespaces_must_be_frozen_pair() -> None:
    unitizer = b'{"model_execution":{"provider_attempt_namespace":"claim-ontology-v5"}}'
    reviewer = b'{"model_execution":{"provider_attempt_namespace":"claim-ontology-v4"}}'
    assert predecessor_module.require_frozen_predecessor_namespaces(
        unitizer,
        reviewer,
    ) == ("claim-ontology-v5", "claim-ontology-v4")

    with pytest.raises(
        StageAReplayExecutorError,
        match="unitizer namespace is not frozen v5",
    ):
        predecessor_module.require_frozen_predecessor_namespaces(
            reviewer,
            reviewer,
        )


def test_predecessor_run_cards_use_one_authenticated_byte_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # synthetic: true — minimal card bytes exercise verifier wiring only.
    unitizer = tmp_path / "unitizer.json"
    reviewer = tmp_path / "reviewer.json"
    unitizer_bytes = (
        b'{"model_execution":{"provider_attempt_namespace":"claim-ontology-v5"}}'
    )
    reviewer_bytes = (
        b'{"model_execution":{"provider_attempt_namespace":"claim-ontology-v4"}}'
    )
    unitizer.write_bytes(unitizer_bytes)
    reviewer.write_bytes(reviewer_bytes)
    record = {
        "unitization_run_card_path": str(unitizer),
        "raw_prediction_units_path": str(tmp_path / "raw.jsonl"),
        "unitization_audit_path": str(tmp_path / "unit-audit.jsonl"),
        "original_review_path": str(tmp_path / "original-review.jsonl"),
        "structural_flags_path": str(tmp_path / "flags.jsonl"),
        "structural_review_audit_path": str(tmp_path / "review-audit.jsonl"),
        "structural_review_run_card_path": str(reviewer),
        "structural_review_registry_path": str(tmp_path / "registry.json"),
        "structural_review_model_key": "fixture:reviewer",
        "merged_review_path": str(tmp_path / "merged-review.jsonl"),
    }
    authenticated_lineage = object()
    calls: list[str] = []

    def verify_unitizer(_path: Path, **kwargs: object) -> object:
        captured = kwargs["captured_input_bytes"]
        assert isinstance(captured, dict)
        assert captured[str(unitizer.resolve())] == unitizer_bytes
        assert captured[str(reviewer.resolve())] == reviewer_bytes
        calls.append("unitizer")
        return authenticated_lineage

    def verify_reviewer(_path: Path, **kwargs: object) -> None:
        assert kwargs["lineage"] is authenticated_lineage
        captured = kwargs["captured_input_bytes"]
        assert isinstance(captured, dict)
        assert captured[str(unitizer.resolve())] == unitizer_bytes
        assert captured[str(reviewer.resolve())] == reviewer_bytes
        calls.append("reviewer")

    monkeypatch.setattr(
        predecessor_module,
        "verify_stage_a_unitization_run_card",
        verify_unitizer,
    )
    monkeypatch.setattr(
        predecessor_module,
        "verify_stage_a_review_run_card",
        verify_reviewer,
    )

    verified = predecessor_module.verify_predecessor_run_cards(
        record=record,
        controlled_private_root=None,
        initialization_receipt_path=None,
    )

    assert calls == ["unitizer", "reviewer"]
    assert verified.unitizer_namespace == "claim-ontology-v5"
    assert verified.reviewer_namespace == "claim-ontology-v4"
    unitizer.write_bytes(reviewer_bytes)
    with pytest.raises(
        StageAReplayExecutorError,
        match="unitizer run card changed after verification",
    ):
        verified.require_unchanged()

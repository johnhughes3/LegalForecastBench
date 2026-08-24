from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.contracts.schemas import LOCAL_MODEL_PLAN_V1, LOCAL_MODEL_RESULT_V1
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.response_verification import (
    output_statuses_from_run_records,
    response_verification_summary_from_run_records,
)
from scripts.run_cycle1_luna import GEMINI_CONFIG
from scripts.validate_flatten_local import LocalModelResultError, flatten_results

REGISTRY_PATH = Path(__file__).parents[1] / (
    "model_registries/cycle-1-supplementary-gemini-3.7-flash-2026-08-24.json"
)
REGISTRY_SHA = "a" * 64
PROMPT_SHA = "c" * 64


def test_supplementary_registry_freezes_gemini_safety_and_accounting_fields() -> None:
    registry = load_model_registry(REGISTRY_PATH)
    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.registry_key == GEMINI_CONFIG.model_key
    assert entry.model_version_or_snapshot == "gemini-3.7-flash"
    assert entry.context_limit == 1_048_576
    assert entry.max_output_tokens == 16_000
    assert entry.input_token_price == 0.75
    assert entry.output_token_price == 3.75
    assert entry.network_disabled is True
    assert entry.search_disabled is True
    assert entry.tool_policy.value == "no_tools"
    assert any(
        "postdates the frozen Cycle 1 model registry" in caveat
        for caveat in entry.known_cutoff_publicity_caveats
    )


def test_gemini_config_binds_owner_ceiling_and_exact_registry() -> None:
    assert GEMINI_CONFIG.cap_microusd == 15_000_000
    assert GEMINI_CONFIG.approval_bead == "legalforecastbench-rkjw"
    assert GEMINI_CONFIG.manifest_approval_bead == "legalforecastbench-3ak.38"
    assert (
        GEMINI_CONFIG.spend_approval_comment_id
        == "9dc0ad0a-de38-5eb8-ae76-a935a3a8f311"
    )
    assert (
        GEMINI_CONFIG.manifest_approval_comment_id
        == "36e31a09-588e-591c-8898-510f1ccb9d06"
    )
    assert GEMINI_CONFIG.spend_approval == (
        "I approve up to USD 15 for the Gemini 3.7 Flash 200-call Cycle 1 comparison."
    )
    assert GEMINI_CONFIG.plan_schema_version == str(LOCAL_MODEL_PLAN_V1)
    assert GEMINI_CONFIG.result_schema_version == str(LOCAL_MODEL_RESULT_V1)
    assert (
        GEMINI_CONFIG.expected_registry_sha256
        == hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    )


def test_generic_flatten_authenticates_gemini_model_registry_and_prompt(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write_result(
        results,
        "courtlistener-docket-case-1",
        "full_packet",
        "unit-1",
        candidate_id="case-1",
    )

    output = tmp_path / "runs.jsonl"
    assert (
        flatten_results(
            results,
            output,
            expected_count=1,
            expected_model_key=GEMINI_CONFIG.model_key,
            expected_registry_sha256=REGISTRY_SHA,
            expected_prompt_commitments={"case-1:full_packet": PROMPT_SHA},
        )
        == 1
    )
    row = json.loads(output.read_text())
    assert row["solver_id"] == GEMINI_CONFIG.model_key


def test_generic_flatten_rejects_prompt_identity_drift_without_output(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write_result(results, "case-1", "full_packet", "unit-1")

    with pytest.raises(LocalModelResultError, match="prompt commitment"):
        flatten_results(
            results,
            tmp_path / "runs.jsonl",
            expected_model_key=GEMINI_CONFIG.model_key,
            expected_registry_sha256=REGISTRY_SHA,
            expected_prompt_commitments={"case-1:full_packet": "d" * 64},
        )
    assert not (tmp_path / "runs.jsonl").exists()


def _write_result(
    results: Path,
    case_id: str,
    ablation: str,
    unit_id: str,
    *,
    candidate_id: str | None = None,
) -> None:
    raw_output = json.dumps(
        {
            "case_assessment": "Assessment.",
            "predictions": [{"unit_id": unit_id, "probability_fully_dismissed": 0.5}],
        }
    )
    run = {
        "case_id": case_id,
        "ablation": ablation,
        "solver_id": GEMINI_CONFIG.model_key,
        "execution_backend": "inspect_ai",
        "required_unit_ids": [unit_id],
        "raw_output": raw_output,
        "raw_output_sha256": "sha256:"
        + hashlib.sha256(raw_output.encode()).hexdigest(),
        "tool_call_logs": [],
        "metadata": {
            "provider": "google",
            "provider_sampling_policy": "provider_default",
            "model_registry_sha256": REGISTRY_SHA,
        },
    }
    envelope = {
        "schema_version": str(LOCAL_MODEL_RESULT_V1),
        "identity": f"{case_id}:{ablation}",
        "model_key": GEMINI_CONFIG.model_key,
        "registry_sha256": REGISTRY_SHA,
        "packet_sha256": "b" * 64,
        "prompt_sha256": PROMPT_SHA,
        "plan_identity_sha256": "d" * 64,
        "prompt_commitment_identity": f"{candidate_id or case_id}:{ablation}",
        "provider": "google",
        "tools": [],
        "runs": [run],
        "response_verification": response_verification_summary_from_run_records([run]),
        "output_statuses": {
            digest: status.to_record()
            for digest, status in output_statuses_from_run_records([run]).items()
        },
    }
    (results / f"{case_id}--{ablation}.json").write_text(json.dumps(envelope))

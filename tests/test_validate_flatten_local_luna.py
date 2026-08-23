from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.evals.response_verification import (
    output_statuses_from_run_records,
    response_verification_summary_from_run_records,
)
from scripts.validate_flatten_local_luna import LocalLunaResultError, flatten_results

REGISTRY_SHA = "a" * 64


def test_flatten_validates_and_preserves_nested_run(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write_result(results, "case-2", "metadata_only", "unit-2")
    _write_result(results, "case-1", "full_packet", "unit-1")

    output = tmp_path / "runs.jsonl"
    assert (
        flatten_results(
            results,
            output,
            expected_count=2,
            expected_registry_sha256=REGISTRY_SHA,
        )
        == 2
    )
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["case_id"] for row in rows] == ["case-1", "case-2"]
    assert rows[0]["solver_id"] == "openai:gpt-5.6-luna"
    assert rows[0]["raw_output"] == _raw_output("unit-1")


def test_flatten_rejects_custom_sampling_and_does_not_write(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    path = _write_result(results, "case-1", "full_packet", "unit-1")
    payload = json.loads(path.read_text())
    payload["runs"][0]["metadata"]["temperature"] = "0"
    path.write_text(json.dumps(payload))

    with pytest.raises(LocalLunaResultError, match="custom sampling"):
        flatten_results(results, tmp_path / "runs.jsonl")
    assert not (tmp_path / "runs.jsonl").exists()


def test_flatten_requires_explicit_identity_for_legacy_missing_statuses(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    path = _write_result(results, "case-1", "full_packet", "unit-1")
    payload = json.loads(path.read_text())
    payload["output_statuses"] = None
    path.write_text(json.dumps(payload))

    with pytest.raises(LocalLunaResultError, match="status summary is missing"):
        flatten_results(results, tmp_path / "runs.jsonl")
    assert (
        flatten_results(
            results,
            tmp_path / "runs-legacy.jsonl",
            derive_missing_output_statuses=frozenset({"case-1:full_packet"}),
        )
        == 1
    )


def test_flatten_rejects_nested_run_tampering(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    path = _write_result(results, "case-1", "full_packet", "unit-1")
    payload = json.loads(path.read_text())
    payload["runs"][0]["raw_output"] = _raw_output("other-unit")
    path.write_text(json.dumps(payload))

    with pytest.raises(LocalLunaResultError, match="raw output hash mismatch"):
        flatten_results(results, tmp_path / "runs.jsonl")


def _write_result(results: Path, case_id: str, ablation: str, unit_id: str) -> Path:
    raw_output = _raw_output(unit_id)
    run = {
        "case_id": case_id,
        "ablation": ablation,
        "solver_id": "openai:gpt-5.6-luna",
        "execution_backend": "inspect_ai",
        "required_unit_ids": [unit_id],
        "raw_output": raw_output,
        "raw_output_sha256": "sha256:"
        + hashlib.sha256(raw_output.encode()).hexdigest(),
        "tool_call_logs": [],
        "metadata": {
            "provider": "openai",
            "provider_sampling_policy": "provider_default",
            "model_registry_sha256": REGISTRY_SHA,
        },
    }
    envelope = {
        "schema_version": "legalforecast.local_luna_result.v1",
        "identity": f"{case_id}:{ablation}",
        "packet_sha256": "b" * 64,
        "prompt_sha256": "c" * 64,
        "plan_identity_sha256": "d" * 64,
        "runs": [run],
        "response_verification": response_verification_summary_from_run_records([run]),
        "output_statuses": {
            digest: status.to_record()
            for digest, status in output_statuses_from_run_records([run]).items()
        },
    }
    path = results / f"{case_id}--{ablation}.json"
    path.write_text(json.dumps(envelope))
    return path


def _raw_output(unit_id: str) -> str:
    return json.dumps(
        {
            "case_assessment": "Assessment.",
            "predictions": [{"unit_id": unit_id, "probability_fully_dismissed": 0.5}],
        }
    )

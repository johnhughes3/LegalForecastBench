from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.jev.execution import build_jev_case_input
from legalforecast.jev.summaries import (
    SHORT_SUMMARY_PROMPT_VERSION,
    SUMMARY_PROMPT_VERSION,
)
from legalforecast.runner import execute_release_run

from test_jev_execution import NativeProbabilityTransport, setup_run


def test_short_summary_cache_is_accepted_for_inference_and_labeled(tmp_path):
    config, execution = setup_run(
        tmp_path,
        summaries=True,
        summary_prompt_version=SHORT_SUMMARY_PROMPT_VERSION,
    )
    entry = load_model_registry(config.model_registry_path).entries[0]
    assert entry.display_name == "Jev (Luna shorter summaries; one shot)"

    units = tuple(
        unit
        for unit in execution.release.prediction_units
        if unit.case_id == execution.release.cases[0].case_id
    )
    case = build_jev_case_input(entry, execution, units, config.jev_summaries_path)

    assert case.unit_ids == tuple(unit.unit_id for unit in units)
    assert case.request["state"]["record_representation"] == "luna_summaries"
    assert all(
        document["text"] == "Faithful source summary."
        for document in case.request["state"]["documents"]
    )


@pytest.mark.parametrize(
    "replacement_version",
    (SUMMARY_PROMPT_VERSION, "jev-document-summary-unknown-v1"),
    ids=("mixed-prompts", "unknown-prompt"),
)
def test_registry_rejects_mixed_or_unknown_summary_prompts(
    tmp_path: Path,
    replacement_version: str,
) -> None:
    config, _ = setup_run(
        tmp_path,
        summaries=True,
        summary_prompt_version=SHORT_SUMMARY_PROMPT_VERSION,
    )
    payload = json.loads(config.jev_summaries_path.read_text())
    first_case = next(iter(payload["records"].values()))
    first_summary = next(iter(first_case.values()))
    first_summary["prompt_version"] = replacement_version
    config.jev_summaries_path.write_text(json.dumps(payload))

    registry_path = tmp_path / "invalid-registry.json"
    assert (
        main(
            [
                "jev",
                "registry",
                "--provider",
                "vercel_ai_gateway",
                "--summaries",
                str(config.jev_summaries_path),
                "--output",
                str(registry_path),
            ]
        )
        == 2
    )
    assert not registry_path.exists()


def test_summary_cache_tampering_refused_before_any_call(tmp_path):
    config, _ = setup_run(tmp_path, summaries=True)
    config.jev_summaries_path.write_text(config.jev_summaries_path.read_text() + " ")
    transport = NativeProbabilityTransport()
    with pytest.raises(ValueError, match="frozen registry"):
        execute_release_run(config, transport=transport, environ={})
    assert transport.calls == []

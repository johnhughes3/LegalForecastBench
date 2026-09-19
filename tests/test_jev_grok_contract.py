from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.provider_spend_attempt_handler import (
    conservative_reservation_microusd,
)
from legalforecast.jev.execution import build_jev_case_input
from legalforecast.jev.packets import case_documents
from legalforecast.jev.summaries import (
    SUMMARY_PROMPT_VERSION,
    DocumentSummary,
    SummaryCache,
)
from legalforecast.release import ForecastExecution, load_forecast_execution
from legalforecast.runner import issue_runner_fixture

_GROK_MODEL = "spacexai/grok-4.6"


def _execution(tmp_path: Path) -> ForecastExecution:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    return load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )


def _grok_cache(tmp_path: Path, execution: ForecastExecution) -> Path:
    path = tmp_path / "grok-summaries.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = SummaryCache(path, execution.release.release_digest)
    for case in execution.release.cases:
        units = tuple(
            unit
            for unit in execution.release.prediction_units
            if unit.case_id == case.case_id
        )
        for document in case_documents(execution, units):
            cache.put(
                case.case_id,
                DocumentSummary(
                    document_id=document.document_id,
                    source_sha256=document.source_sha256,
                    text="Faithful Grok summary.",
                    model=_GROK_MODEL,
                    prompt_version=SUMMARY_PROMPT_VERSION,
                    input_tokens=10,
                    output_tokens=5,
                    estimated_cost_usd=0.001,
                ),
            )
    return path


def _freeze_registry(
    tmp_path: Path, cache: Path, *, summary_model: str = "grok"
) -> Path:
    output = tmp_path / f"registry-{summary_model}.json"
    assert (
        main(
            [
                "jev",
                "registry",
                "--summary-model",
                summary_model,
                "--summaries",
                str(cache),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    return output


def test_registry_freezes_grok_mode_and_display(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    cache = _grok_cache(tmp_path, execution)

    registry_path = _freeze_registry(tmp_path, cache)
    entry = load_model_registry(registry_path).entries[0]

    assert entry.jev_input_mode == "grok_summaries"
    assert entry.context_limit == 64_000
    reservation = conservative_reservation_microusd(
        context_limit=entry.context_limit,
        max_output_tokens=entry.max_output_tokens,
        input_token_price=entry.input_token_price,
        output_token_price=entry.output_token_price,
    )
    # A full 64,000-token request costs 2,688 microusd at the frozen rate.
    assert reservation >= 2688
    assert entry.display_name == "Jev (Grok 4.6 summaries; one shot)"
    assert entry.jev_summaries_sha256 is not None


def test_registry_rejects_wrong_or_mixed_summary_models(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    execution = _execution(tmp_path)
    cache = _grok_cache(tmp_path, execution)
    payload = json.loads(cache.read_text(encoding="utf-8"))
    records = payload["records"]
    for case_records in records.values():
        for summary in case_records.values():
            summary["model"] = "gpt-5.6-luna"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        main(
            [
                "jev",
                "registry",
                "--summary-model",
                "grok",
                "--summaries",
                str(cache),
                "--output",
                str(tmp_path / "wrong.json"),
            ]
        )
        == 2
    )
    assert "does not match" in capsys.readouterr().err

    cache = _grok_cache(tmp_path / "mixed", execution)
    payload = json.loads(cache.read_text(encoding="utf-8"))
    records = payload["records"]
    first_case = next(iter(records.values()))
    first_summary = next(iter(first_case.values()))
    first_summary["model"] = "gpt-5.6-luna"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        main(
            [
                "jev",
                "registry",
                "--summary-model",
                "grok",
                "--summaries",
                str(cache),
                "--output",
                str(tmp_path / "mixed.json"),
            ]
        )
        == 2
    )
    assert "does not match" in capsys.readouterr().err


def test_execution_reads_grok_cache_and_marks_request_representation(
    tmp_path: Path,
) -> None:
    execution = _execution(tmp_path)
    cache = _grok_cache(tmp_path, execution)
    registry_path = _freeze_registry(tmp_path, cache)
    entry = load_model_registry(registry_path).entries[0]
    units = tuple(
        unit
        for unit in execution.release.prediction_units
        if unit.case_id == execution.release.cases[0].case_id
    )

    request = build_jev_case_input(entry, execution, units, cache).request

    assert request["model"] == "jev-1.13.0"
    state = request["state"]
    assert isinstance(state, dict)
    assert state["record_representation"] == "grok_summaries"
    assert state["documents"][0]["text"] == "Faithful Grok summary."

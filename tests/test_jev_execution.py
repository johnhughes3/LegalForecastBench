from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from urllib.request import Request

import legalforecast.jev.execution as jev_execution
import pytest
from legalforecast.cli import main
from legalforecast.evals.live_model_solver import LiveModelProviderError
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.jev.execution import build_jev_case_input
from legalforecast.jev.packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    require_request_fits,
)
from legalforecast.jev.summaries import (
    SUMMARY_PROMPT_VERSION,
    DocumentSummary,
    SummaryCache,
)
from legalforecast.release import load_forecast_execution
from legalforecast.runner import RunConfig, execute_release_run, issue_runner_fixture


def setup_run(tmp_path: Path, *, summaries: bool = False):
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    execution = load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )
    cache_path = tmp_path / "summaries.json"
    if summaries:
        cache = SummaryCache(cache_path, execution.release.release_digest)
        for case in execution.release.cases:
            units = tuple(
                u
                for u in execution.release.prediction_units
                if u.case_id == case.case_id
            )
            for doc in case_documents(execution, units):
                cache.put(
                    case.case_id,
                    DocumentSummary(
                        document_id=doc.document_id,
                        source_sha256=doc.source_sha256,
                        text="Faithful source summary.",
                        model="gpt-5.6-luna",
                        prompt_version=SUMMARY_PROMPT_VERSION,
                        input_tokens=10,
                        output_tokens=5,
                        estimated_cost_usd=0.001,
                    ),
                )
    registry = tmp_path / "registry.json"
    args = ["jev", "registry", "--output", str(registry)]
    if summaries:
        args += ["--summaries", str(cache_path)]
    assert main(args) == 0
    config = RunConfig(
        forecast_path=fixture / "release/forecast-release.json",
        artifact_root=fixture / "release",
        model_registry_path=registry,
        model_key="vercel_ai_gateway:typesafe-ai/jev",
        ledger_path=tmp_path / "ledger.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=1_000_000,
        approval_reference="fixture",
        jev_summaries_path=cache_path if summaries else None,
    )
    return config, execution


class NativeProbabilityTransport:
    def __init__(self, invalid: object = None):
        self.calls: list[dict] = []
        self.invalid = invalid

    def __call__(self, request: Request, timeout_seconds: float):
        body = json.loads(request.data)
        self.calls.append(body)
        return {
            "answers": {
                unit: {
                    "type": "boolean",
                    "probability": self.invalid if self.invalid is not None else 0.37,
                }
                for unit in body["questions"]
            },
            "usage": {"inputTokens": 100, "outputTokens": 4},
            "providerMetadata": {},
        }


@pytest.mark.parametrize("summaries", [False, True])
def test_native_probabilities_reach_normal_receipts_and_resume_without_calls(
    tmp_path, summaries
):
    config, execution = setup_run(tmp_path, summaries=summaries)
    transport = NativeProbabilityTransport()
    first = execute_release_run(
        config, transport=transport, environ={"AI_GATEWAY_API_KEY": "fixture"}
    )
    assert first.executed_cells == execution.release.case_count
    assert len(transport.calls) == execution.release.case_count
    assert {key for call in transport.calls for key in call["questions"]} == {
        u.unit_id for u in execution.release.prediction_units
    }
    for call in transport.calls:
        assert "tools" not in call
        assert all(q["type"] == "boolean" for q in call["questions"].values())
        assert "Leave to amend" in call["state"]["forecast_event_definition"]
        assert "partial" in call["state"]["forecast_event_definition"]
    receipts = [json.loads(p.read_text()) for p in config.receipts_dir.glob("*.json")]
    assert len(receipts) == execution.release.case_count
    assert {r["execution_condition"] for r in receipts} == {
        "jev_luna_summaries" if summaries else "jev_full_text"
    }
    assert all(r["served_model_version"] == "unreported" for r in receipts)
    second = execute_release_run(config, transport=transport, environ={})
    assert second.executed_cells == 0
    assert len(transport.calls) == execution.release.case_count


@pytest.mark.parametrize("probability", [True, -0.1, 1.1, float("nan")])
def test_rejects_invalid_native_probabilities_without_repair_calls(
    tmp_path, probability
):
    config, _ = setup_run(tmp_path)
    transport = NativeProbabilityTransport(probability)
    with pytest.raises(ValueError, match=r"probability|non-finite"):
        execute_release_run(
            config, transport=transport, environ={"AI_GATEWAY_API_KEY": "fixture"}
        )
    assert len(transport.calls) == 1
    assert not list(config.receipts_dir.glob("*.json"))


def test_summary_cache_tampering_refused_before_any_call(tmp_path):
    config, _ = setup_run(tmp_path, summaries=True)
    config.jev_summaries_path.write_text(config.jev_summaries_path.read_text() + " ")
    transport = NativeProbabilityTransport()
    with pytest.raises(ValueError, match="frozen registry"):
        execute_release_run(config, transport=transport, environ={})
    assert transport.calls == []


def test_whole_request_budget_includes_questions_and_never_truncates(tmp_path):
    config, execution = setup_run(tmp_path)
    units = (execution.release.prediction_units[0],)
    documents = case_documents(execution, units)
    oversized = replace(documents[0], text="x" * JEV_REQUEST_BYTE_BUDGET)
    request = case_request(units, (oversized, *documents[1:]))
    with pytest.raises(ValueError, match="above conservative"):
        require_request_fits(request)
    assert request["state"]["documents"][0]["text"] == oversized.text
    entry = load_model_registry(config.model_registry_path).entries[0]
    case = build_jev_case_input(entry, execution, units, None)
    assert case.unit_ids == (units[0].unit_id,)


def test_one_shared_record_carries_all_units_and_their_meaning(tmp_path):
    _, execution = setup_run(tmp_path)
    first = execution.release.prediction_units[0]
    second = first.model_copy(
        update={
            "unit_id": "another-unit",
            "claim_name": "different claim",
            "defendant_group": "different defendants",
        }
    )
    documents = case_documents(execution, (first, second))
    request = case_request((first, second), documents)
    assert set(request["questions"]) == {first.unit_id, second.unit_id}
    assert "different claim" in request["questions"][second.unit_id]["instructions"]
    assert (
        "different defendants" in request["questions"][second.unit_id]["instructions"]
    )
    assert len(request["state"]["documents"]) == len(documents)


@pytest.mark.parametrize("empty_text", ["", " \n\t"])
def test_empty_summary_cannot_silently_omit_a_document(tmp_path, empty_text):
    _, execution = setup_run(tmp_path)
    units = (execution.release.prediction_units[0],)
    documents = case_documents(execution, units)
    summaries = {
        document.document_id: "A substantive summary" for document in documents
    }
    summaries[documents[0].document_id] = empty_text
    with pytest.raises(ValueError, match="empty document summary"):
        case_request(units, documents, summaries=summaries)


@pytest.mark.parametrize(
    "status,retryable,expected",
    [(429, True, True), (429, False, False), (500, True, False)],
)
def test_sdk_preserves_only_confirmed_nonbillable_rate_limits(
    monkeypatch, status, retryable, expected
):
    monkeypatch.setattr(jev_execution.shutil, "which", lambda _: "/fixture/node")
    monkeypatch.setattr(
        jev_execution.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout=b"",
            stderr=json.dumps(
                {
                    "error_name": "AI_APICallError",
                    "error_message": "gateway response unavailable",
                    "generation_id": "gen_fixture_123",
                    "status_code": status,
                    "retryable": retryable,
                }
            ).encode(),
        ),
    )
    with pytest.raises(LiveModelProviderError) as failure:
        jev_execution._sdk_call(b"{}", {"AI_GATEWAY_API_KEY": "fixture"})
    assert failure.value.status_code == status
    assert failure.value.retryable is expected


def test_sdk_error_propagates_bounded_diagnostic_without_secret_or_control_chars(
    monkeypatch,
):
    secret = "fixture-gateway-key"
    monkeypatch.setattr(jev_execution.shutil, "which", lambda _: "/fixture/node")
    monkeypatch.setattr(
        jev_execution.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout=b"",
            stderr=json.dumps(
                {
                    "error_name": "GatewayInternalServerError",
                    "error_message": (
                        f"backend failed\nAuthorization: Bearer {secret}; "
                        f"apiKey={secret}\x00"
                    ),
                    "status_code": 500,
                    "generation_id": "gen_fixture_456",
                    "retryable": True,
                }
            ).encode(),
        ),
    )
    with pytest.raises(LiveModelProviderError) as failure:
        jev_execution._sdk_call(
            b"{}", {"AI_GATEWAY_API_KEY": secret, "PATH": "/fixture"}
        )
    rendered = str(failure.value)
    assert "backend failed" in rendered
    assert "status_code=500" in rendered
    assert "gen_fixture_456" in rendered
    assert secret not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "apiKey=" not in rendered
    assert "\x00" not in rendered
    assert failure.value.status_code == 500
    assert failure.value.retryable is False

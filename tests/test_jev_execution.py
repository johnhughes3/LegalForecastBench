from __future__ import annotations

import json
import sqlite3
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


def setup_run(
    tmp_path: Path, *, summaries: bool = False, provider: str = "vercel_ai_gateway"
):
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
    args = [
        "jev",
        "registry",
        "--provider",
        provider,
        "--output",
        str(registry),
    ]
    if summaries:
        args += ["--summaries", str(cache_path)]
    assert main(args) == 0
    config = RunConfig(
        forecast_path=fixture / "release/forecast-release.json",
        artifact_root=fixture / "release",
        model_registry_path=registry,
        model_key=(
            "typesafe:jev-1.13.0"
            if provider == "typesafe"
            else "vercel_ai_gateway:typesafe-ai/jev"
        ),
        ledger_path=tmp_path / "ledger.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=1_000_000,
        approval_reference="fixture",
        jev_summaries_path=cache_path if summaries else None,
    )
    return config, execution


class NativeProbabilityTransport:
    def __init__(self, invalid: object = None, *, provider: str = "gateway"):
        self.calls: list[dict] = []
        self.invalid = invalid
        self.provider = provider

    def __call__(self, request: Request, timeout_seconds: float):
        body = json.loads(request.data)
        self.calls.append(body)
        answer_type = "noul" if self.provider == "typesafe" else "boolean"
        probability_key = "noul" if self.provider == "typesafe" else "probability"
        usage = (
            {"input_tokens": 100, "output_tokens": 4}
            if self.provider == "typesafe"
            else {"inputTokens": 100, "outputTokens": 4}
        )
        payload = {
            "answers": {
                unit: {
                    "type": answer_type,
                    probability_key: self.invalid if self.invalid is not None else 0.37,
                }
                for unit in body["questions"]
            },
            "usage": usage,
            "providerMetadata": {},
        }
        if self.provider == "typesafe":
            payload["model"] = "jev-1.13.0"
        return payload


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


def test_first_party_typesafe_route_uses_native_nouls_and_records_model_metadata(
    tmp_path,
):
    config, execution = setup_run(tmp_path, provider="typesafe")
    transport = NativeProbabilityTransport(provider="typesafe")

    result = execute_release_run(
        config, transport=transport, environ={"TYPESAFE_API_KEY": "fixture"}
    )

    assert result.executed_cells == execution.release.case_count
    assert len(transport.calls) == execution.release.case_count
    for call in transport.calls:
        assert call["model"] == "jev-1.13.0"
        assert "providerOptions" not in call
        assert all(q["type"] == "noul" for q in call["questions"].values())
    receipts = [
        json.loads(path.read_text()) for path in config.receipts_dir.glob("*.json")
    ]
    assert {receipt["model_key"] for receipt in receipts} == {"typesafe:jev-1.13.0"}
    assert {receipt["served_model_version"] for receipt in receipts} == {"jev-1.13.0"}
    assert all(receipt["jev_provider_metadata"] == {} for receipt in receipts)


def test_first_party_typesafe_route_requires_its_own_credential(tmp_path):
    config, _ = setup_run(tmp_path, provider="typesafe")
    transport = NativeProbabilityTransport(provider="typesafe")
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        execute_release_run(config, transport=transport, environ={})
    assert transport.calls == []


@pytest.mark.parametrize("probability", [True, -0.1, 1.1, float("nan")])
def test_first_party_typesafe_route_rejects_malformed_nouls(tmp_path, probability):
    config, _ = setup_run(tmp_path, provider="typesafe")
    transport = NativeProbabilityTransport(probability, provider="typesafe")
    with pytest.raises(ValueError, match=r"probability|non-finite"):
        execute_release_run(
            config, transport=transport, environ={"TYPESAFE_API_KEY": "fixture"}
        )
    assert len(transport.calls) == 1
    assert not list(config.receipts_dir.glob("*.json"))


def test_typesafe_sdk_call_preserves_native_response_and_records_sdk_metadata(
    monkeypatch,
):
    import httpx2
    import typesafe_sdk

    raw_payload = {
        "model": "jev-1.13.0",
        "answers": {"unit": {"type": "noul", "noul": 0.62}},
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }

    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        sent = json.loads(request.content)
        assert sent["model"] == "jev-1.13.0"
        assert sent["state"] == {"case_id": "case"}
        assert sent["questions"]["unit"]["type"] == "noul"
        return httpx2.Response(
            200,
            json=raw_payload,
            headers={"x-typesafe-request-id": "request_fixture_123"},
            request=request,
        )

    real_client = typesafe_sdk.TypeSafeClient
    transport = httpx2.MockTransport(handler)

    def client_factory(**kwargs):
        assert kwargs["api_key"] == "fixture-typesafe-key"
        assert kwargs["model"] == "jev-1.13.0"
        assert kwargs["retry"].max_retries == 0
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", client_factory)
    metadata: dict[str, object] = {}
    body = json.dumps(
        {
            "model": "jev-1.13.0",
            "state": {"case_id": "case"},
            "questions": {"unit": {"type": "noul", "instructions": "Does it?"}},
        }
    ).encode()

    payload = jev_execution._typesafe_sdk_call(
        body,
        {"TYPESAFE_API_KEY": "fixture-typesafe-key"},
        provider_metadata=metadata,
    )

    assert payload == raw_payload
    assert metadata == {
        "sdk": f"typesafe-sdk/{typesafe_sdk.__version__}",
        "request_id": "request_fixture_123",
    }
    assert len(requests) == 1


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
    [(429, True, True), (429, False, True), (429, None, True), (500, True, False)],
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


@pytest.mark.parametrize("provider", ["vercel_ai_gateway", "typesafe"])
def test_429_backoff_preserves_request_and_successful_resume(
    tmp_path, monkeypatch, provider
):
    from legalforecast.jev import rate_limits

    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    config, execution = setup_run(tmp_path, provider=provider)
    good = NativeProbabilityTransport(provider=provider)
    requests = []

    def transport(request, timeout):
        requests.append(request.data)
        if len(requests) <= 7:
            raise LiveModelProviderError("capacity", status_code=429, retryable=False)
        return good(request, timeout)

    env = {"AI_GATEWAY_API_KEY": "fixture", "TYPESAFE_API_KEY": "fixture"}
    result = execute_release_run(config, transport=transport, environ=env)
    assert result.executed_cells == execution.release.case_count
    assert sleeps == [30, 60, 120, 240, 300, 300, 300]
    assert len(requests) == execution.release.case_count + 7
    assert len(set(requests[:8])) == 1
    assert len(good.calls) == execution.release.case_count
    receipts = [json.loads(p.read_text()) for p in config.receipts_dir.glob("*.json")]
    assert sorted(r["jev_request_count"] for r in receipts) == [
        *([1] * (execution.release.case_count - 1)),
        8,
    ]
    count = len(requests)
    resumed = execute_release_run(config, transport=transport, environ={})
    assert resumed.executed_cells == 0
    assert len(requests) == count


@pytest.mark.parametrize("retryable", [True, False, None])
def test_every_429_exhausts_after_eight_requests(tmp_path, monkeypatch, retryable):
    from legalforecast.jev import rate_limits

    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    config, _ = setup_run(tmp_path)
    calls = []

    def transport(request, timeout):
        calls.append(request.data)
        raise LiveModelProviderError("quota", status_code=429, retryable=retryable)

    with pytest.raises(LiveModelProviderError) as failure:
        execute_release_run(
            config, transport=transport, environ={"AI_GATEWAY_API_KEY": "fixture"}
        )
    assert failure.value.status_code == 429
    assert failure.value.retryable is True
    assert len(calls) == 8
    assert len(set(calls)) == 1
    assert sleeps == [30, 60, 120, 240, 300, 300, 300]
    assert not list(config.receipts_dir.glob("*.json"))
    with sqlite3.connect(config.ledger_path) as connection:
        statuses = connection.execute("SELECT status FROM provider_attempts").fetchall()
    # The runner's local shadow calls nonbillable failures "blocked"; the
    # remote spend authority retains its separate failed_nonbillable state.
    assert statuses == [("blocked",)]


def test_429_then_uncertain_failure_preserves_reservation(tmp_path, monkeypatch):
    from legalforecast.jev import rate_limits

    sleeps = []
    monkeypatch.setattr(rate_limits.time, "sleep", sleeps.append)
    config, _ = setup_run(tmp_path)
    calls = []

    def transport(request, timeout):
        calls.append(request.data)
        if len(calls) == 1:
            raise LiveModelProviderError("quota", status_code=429, retryable=False)
        raise LiveModelProviderError("server failed", status_code=500, retryable=True)

    with pytest.raises(LiveModelProviderError, match="server failed"):
        execute_release_run(
            config, transport=transport, environ={"AI_GATEWAY_API_KEY": "fixture"}
        )
    assert len(calls) == 2
    assert sleeps == [30]
    with sqlite3.connect(config.ledger_path) as connection:
        statuses = connection.execute("SELECT status FROM provider_attempts").fetchall()
    assert statuses == [("ambiguous",)]

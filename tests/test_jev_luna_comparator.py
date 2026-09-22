from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.request import Request

import httpx2
import legalforecast.jev.luna as luna
import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.jev.execution import build_jev_case_input
from legalforecast.jev.packets import case_documents
from legalforecast.jev.summaries import (
    SUMMARY_PROMPT_VERSION,
    DocumentSummary,
    SummaryCache,
)
from legalforecast.release import load_forecast_execution
from legalforecast.runner import RunConfig, execute_release_run, issue_runner_fixture
from openai import AsyncOpenAI as RealAsyncOpenAI


class _ComparatorTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, request: Request, timeout_seconds: float) -> dict[str, object]:
        del timeout_seconds
        body = cast(dict[str, object], json.loads(cast(bytes, request.data)))
        self.calls.append(body)
        questions = cast(dict[str, object], body["questions"])
        return {
            "model": "gpt-5.6-luna",
            "predictions": [
                {
                    "unit_id": unit_id,
                    "probability_fully_dismissed": 0.37,
                }
                for unit_id in questions
            ],
            "usage": {"input_tokens": 100, "output_tokens": 8},
            "providerMetadata": {},
        }


def _fixture_with_luna_cache(tmp_path: Path) -> tuple[Path, Path, Path]:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    execution = load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )
    cache_path = tmp_path / "jev-summaries.json"
    cache = SummaryCache(cache_path, execution.release.release_digest)
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
                    text="Faithful Luna summary.",
                    model="gpt-5.6-luna",
                    prompt_version=SUMMARY_PROMPT_VERSION,
                    input_tokens=10,
                    output_tokens=5,
                    estimated_cost_usd=0.001,
                ),
            )
    return fixture, cache_path, tmp_path / "base-registry.json"


def _freeze(
    cache_path: Path,
    output: Path,
    *,
    predictor: str = "jev",
    reasoning_effort: str | None = None,
    provider: str = "typesafe",
) -> None:
    args = [
        "jev",
        "registry",
        "--summaries",
        str(cache_path),
        "--output",
        str(output),
        "--provider",
        provider,
    ]
    if predictor == "luna":
        args += [
            "--predictor",
            "luna",
            "--reasoning-effort",
            reasoning_effort or "none",
        ]
    assert main(args) == 0


def test_luna_registry_freezes_a_reasoning_condition_from_the_base_entry(
    tmp_path: Path,
) -> None:
    _, cache_path, _ = _fixture_with_luna_cache(tmp_path)
    output = tmp_path / "luna-none.json"
    _freeze(cache_path, output, predictor="luna", reasoning_effort="none")
    entry = load_model_registry(output).entries[0]
    assert entry.registry_key == "openai:gpt-5.6-luna"
    assert entry.jev_input_mode == "luna_summaries"
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "none"
    assert entry.tool_policy.value == "no_tools"
    assert entry.input_token_price == 1.0
    assert entry.output_token_price == 6.0
    assert entry.display_name == "Luna (Luna summaries; one shot; reasoning none)"


def test_luna_packet_matches_gateway_jev_state_and_questions(
    tmp_path: Path,
) -> None:
    fixture, cache_path, _ = _fixture_with_luna_cache(tmp_path)
    luna_registry_path = tmp_path / "luna.json"
    jev_registry_path = tmp_path / "jev.json"
    _freeze(cache_path, luna_registry_path, predictor="luna", reasoning_effort="high")
    _freeze(cache_path, jev_registry_path, provider="vercel_ai_gateway")
    execution = load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )
    units = tuple(execution.release.prediction_units[:1])
    luna_entry = load_model_registry(luna_registry_path).entries[0]
    jev_entry = load_model_registry(jev_registry_path).entries[0]
    luna_request = build_jev_case_input(
        luna_entry, execution, units, cache_path
    ).request
    jev_request = build_jev_case_input(jev_entry, execution, units, cache_path).request
    assert luna_request["state"] == jev_request["state"]
    assert luna_request["questions"] == jev_request["questions"]
    questions = cast(dict[str, object], luna_request["questions"])
    assert all(
        cast(dict[str, object], question)["type"] == "boolean"
        for question in questions.values()
    )


def test_luna_comparator_makes_one_request_and_preserves_original_units(
    tmp_path: Path,
) -> None:
    fixture, cache_path, _ = _fixture_with_luna_cache(tmp_path)
    registry_path = tmp_path / "luna.json"
    _freeze(cache_path, registry_path, predictor="luna", reasoning_effort="high")
    execution = load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )
    transport = _ComparatorTransport()
    config = RunConfig(
        forecast_path=fixture / "release/forecast-release.json",
        artifact_root=fixture / "release",
        model_registry_path=registry_path,
        model_key="openai:gpt-5.6-luna",
        ledger_path=tmp_path / "ledger.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=1_000_000,
        approval_reference="fixture",
        jev_summaries_path=cache_path,
    )
    result = execute_release_run(config, transport=transport, environ={})
    assert result.executed_cells == execution.release.case_count
    assert len(transport.calls) == execution.release.case_count
    assert {
        unit_id
        for call in transport.calls
        for unit_id in cast(dict[str, object], call["questions"])
    } == {unit.unit_id for unit in execution.release.prediction_units}
    receipts = [
        json.loads(path.read_text()) for path in config.receipts_dir.glob("*.json")
    ]
    assert {receipt["execution_condition"] for receipt in receipts} == {
        "luna_summary_comparator_reasoning_high"
    }
    assert all(receipt["jev_request_count"] == 1 for receipt in receipts)


@pytest.mark.parametrize("reasoning_effort", ("none", "high"))
def test_luna_sdk_adapter_posts_one_native_no_tool_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reasoning_effort: str,
) -> None:
    _, cache_path, _ = _fixture_with_luna_cache(tmp_path)
    registry_path = tmp_path / "luna.json"
    _freeze(
        cache_path,
        registry_path,
        predictor="luna",
        reasoning_effort=reasoning_effort,
    )
    entry = load_model_registry(registry_path).entries[0]
    requests: list[dict[str, object]] = []

    async def response_handler(request: httpx2.Request) -> httpx2.Response:
        body = cast(dict[str, object], json.loads(await request.aread()))
        requests.append(body)
        return httpx2.Response(
            200,
            json={
                "id": "resp_luna_fixture",
                "object": "response",
                "created_at": 1_725_000_000,
                "model": "gpt-5.6-luna",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_luna_fixture",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "predictions": [
                                            {
                                                "unit_id": "unit-a",
                                                "probability_fully_dismissed": 0.25,
                                            }
                                        ]
                                    }
                                ),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 8,
                    "total_tokens": 108,
                },
            },
            request=request,
        )

    http_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(response_handler),
        base_url="https://api.openai.com/v1",
    )
    client_kwargs: dict[str, object] = {}

    def client_factory(**kwargs: Any) -> RealAsyncOpenAI:
        client_kwargs.update(kwargs)
        return RealAsyncOpenAI(http_client=http_client, **kwargs)

    monkeypatch.setattr(luna, "AsyncOpenAI", client_factory)
    payload = luna._sdk_call(  # pyright: ignore[reportPrivateUsage]
        json.dumps(
            {
                "state": {"case_id": "case-1"},
                "questions": {"unit-a": {"type": "boolean", "question": "Dismiss?"}},
            }
        ).encode(),
        {"OPENAI_API_KEY": "fixture-key"},
        entry,
    )

    assert client_kwargs["max_retries"] == 0
    assert len(requests) == 1
    request = requests[0]
    assert request["model"] == "gpt-5.6-luna"
    assert request["reasoning"] == {
        "effort": reasoning_effort,
        "context": "all_turns",
    }
    assert "tools" not in request
    text_format = cast(dict[str, object], request["text"])["format"]
    assert cast(dict[str, object], text_format)["type"] == "json_schema"
    assert payload["model"] == "gpt-5.6-luna"
    provider_metadata = payload["providerMetadata"]
    assert isinstance(provider_metadata, dict)
    assert provider_metadata["provider_response_id"] == "resp_luna_fixture"


def test_luna_sdk_adapter_rejects_unexpected_served_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cache_path, _ = _fixture_with_luna_cache(tmp_path)
    registry_path = tmp_path / "luna.json"
    _freeze(cache_path, registry_path, predictor="luna", reasoning_effort="none")
    entry = load_model_registry(registry_path).entries[0]

    class _UnexpectedModelAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run_sync(self, *_args: object, **_kwargs: object) -> object:
            return SimpleNamespace(
                output=luna._LunaEnvelope(  # pyright: ignore[reportPrivateUsage]
                    predictions=(
                        luna._LunaPrediction(  # pyright: ignore[reportPrivateUsage]
                            unit_id="unit-a", probability_fully_dismissed=0.25
                        ),
                    )
                ),
                usage=SimpleNamespace(
                    requests=1,
                    input_tokens=10,
                    output_tokens=5,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                    input_audio_tokens=0,
                    output_audio_tokens=0,
                    tool_calls=0,
                    cost=None,
                ),
                response=SimpleNamespace(model_name="gpt-5.6-luna-wrong"),
            )

    monkeypatch.setattr(luna, "Agent", _UnexpectedModelAgent)
    with pytest.raises(ValueError, match="differs from the frozen registry"):
        luna._sdk_call(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "state": {},
                    "questions": {
                        "unit-a": {"type": "boolean", "question": "Dismiss?"}
                    },
                }
            ).encode(),
            {"OPENAI_API_KEY": "fixture-key"},
            entry,
        )


@pytest.mark.parametrize(
    ("predictor", "provider", "model_id", "effort"),
    [
        ("sol-6", "openai", "gpt-6-sol", "none"),
        ("sol-6", "openai", "gpt-6-sol", "high"),
        ("luna-6", "openai", "gpt-6-luna", "none"),
        ("luna-6", "openai", "gpt-6-luna", "high"),
        ("opus-5.5", "anthropic", "claude-opus-5-5", "low"),
        ("opus-5.5", "anthropic", "claude-opus-5-5", "high"),
    ],
)
def test_new_predictor_registry_keeps_summary_identity(
    tmp_path: Path, predictor: str, provider: str, model_id: str, effort: str
) -> None:
    _, cache, _ = _fixture_with_luna_cache(tmp_path)
    output = tmp_path / "registry.json"
    assert (
        main(
            [
                "jev",
                "registry",
                "--predictor",
                predictor,
                "--reasoning-effort",
                effort,
                "--summaries",
                str(cache),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    entry = load_model_registry(output).get(provider, model_id)
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == effort
    assert entry.jev_input_mode == "luna_summaries"
    assert entry.jev_summaries_sha256
    assert entry.tool_policy.value == "no_tools"
    assert entry.max_output_tokens == 16000
    assert model_id == entry.model_version_or_snapshot


def test_opus_rejects_reasoning_off_before_registry_creation(tmp_path: Path) -> None:
    _, cache, _ = _fixture_with_luna_cache(tmp_path)
    output = tmp_path / "registry.json"
    result = main(
        [
            "jev",
            "registry",
            "--predictor",
            "opus-5.5",
            "--reasoning-effort",
            "none",
            "--summaries",
            str(cache),
            "--output",
            str(output),
        ]
    )
    assert result != 0
    assert not output.exists()

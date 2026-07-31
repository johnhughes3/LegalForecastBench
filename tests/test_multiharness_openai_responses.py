from __future__ import annotations

import json
import math
import traceback
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.multiharness.openai_responses import (
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_RESPONSES_ADAPTER_ID,
    OPENAI_RESPONSES_ADAPTER_VERSION,
    OPENAI_SDK_MAX_RETRIES,
    OPENAI_SDK_VERSION,
    OpenAIResponsesAdapterError,
    adapter_bundle_sha256,
    build_capabilities,
    run_offline_protocol_fixture,
    run_openai_responses,
)
from legalforecast.multiharness.openai_responses_cli import (
    build_openai_client,
)
from legalforecast.multiharness.openai_responses_cli import (
    main as adapter_main,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse


@dataclass(frozen=True)
class _FunctionCall:
    call_id: str
    name: str = "read_canonical_task"
    arguments: str = "{}"
    type: str = "function_call"


class _FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("unexpected Responses API request")
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = _FakeResponses(responses)


class _ToolTransport:
    def __init__(self) -> None:
        self.requests: list[ToolRequest] = []

    def execute(self, request: ToolRequest) -> ToolResponse:
        self.requests.append(request)
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={"text": '{"task":"public canonical metadata"}\n'},
        )


def test_capabilities_are_real_lfb_only_and_advertise_live_tools() -> None:
    capabilities = build_capabilities()

    assert capabilities.adapter_id == OPENAI_RESPONSES_ADAPTER_ID
    assert capabilities.adapter_version == OPENAI_RESPONSES_ADAPTER_VERSION
    assert capabilities.supported_families == ("legalforecast_mtd",)
    assert capabilities.supported_scoring_modes == ("lfb_brier",)
    assert (
        capabilities.tool_protocol_version
        == "legalforecast.multiharness.tool_request.v1"
    )


def test_offline_protocol_fixture_is_credential_free_and_explicit(
    tmp_path: Path,
) -> None:
    request = _request(
        allowed_provider_env_vars=(),
        fixture="adapter-conformance",
        model_key="conformance-fixture-model",
    )

    result = run_offline_protocol_fixture(request, tmp_path)

    assert result.status == "succeeded"
    assert result.public_summary["offline_protocol_fixture"] is True
    assert result.public_summary["provider_request_count"] == 0
    assert result.public_summary["requested_model"] == "conformance-fixture-model"
    assert result.public_summary["sdk_name"] == "openai"
    assert result.public_summary["sdk_version"] == OPENAI_SDK_VERSION
    assert result.public_summary["sandbox_policy_id"] == "provider-runtime"


def test_offline_protocol_fixture_rejects_non_conformance_runs(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        OpenAIResponsesAdapterError,
        match="restricted to the adapter conformance fixture",
    ):
        run_offline_protocol_fixture(_request(), tmp_path)


def test_installed_sdk_matches_exact_baseline_pin() -> None:
    assert version("openai") == OPENAI_SDK_VERSION


def test_live_client_disables_transparent_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> object:
        observed.update(kwargs)
        return object()

    monkeypatch.setattr("openai.OpenAI", fake_openai)

    build_openai_client("sk-test")

    assert observed == {
        "api_key": "sk-test",
        "max_retries": OPENAI_SDK_MAX_RETRIES,
    }


def test_cli_missing_key_fails_with_constant_public_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request().to_record()), encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = adapter_main(
        [
            "run-with-tools",
            "--request",
            str(request_path),
            "--output",
            str(tmp_path / "result.json"),
            "--workspace",
            str(tmp_path / "workspace"),
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert captured.err == "OpenAI Responses adapter failed closed\n"
    assert not (tmp_path / "result.json").exists()


def test_live_responses_tool_loop_maps_request_and_records_safe_provenance(
    tmp_path: Path,
) -> None:
    reasoning = SimpleNamespace(
        type="reasoning",
        encrypted_content="opaque-provider-reasoning",
    )
    first = _response(
        response_id="resp-private-1",
        model="gpt-served-snapshot",
        output=[reasoning, _FunctionCall(call_id="call-1")],
        input_tokens=12,
        output_tokens=3,
    )
    forecast = {
        "predictions": [
            {
                "unit_id": "count_i",
                "probability_fully_dismissed": 0.7,
            }
        ]
    }
    second = _response(
        response_id="resp-private-2",
        model="gpt-served-snapshot",
        output=[],
        output_text=json.dumps(forecast),
        input_tokens=20,
        output_tokens=7,
    )
    client = _FakeClient([first, second])
    tools = _ToolTransport()

    result = run_openai_responses(
        _request(),
        tmp_path,
        tool_transport=tools,
        client=client,
    )

    assert len(client.responses.calls) == 2
    initial = client.responses.calls[0]
    assert initial["model"] == "gpt-test"
    assert initial["store"] is False
    assert initial["include"] == ["reasoning.encrypted_content"]
    assert initial["max_output_tokens"] == OPENAI_MAX_OUTPUT_TOKENS
    assert initial["timeout"] == 30.0
    assert initial["tool_choice"] == "required"
    assert initial["tools"] == [
        {
            "type": "function",
            "name": "read_canonical_task",
            "description": (
                "Read the public canonical task record staged by the host-owned "
                "tool container."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    continuation = client.responses.calls[1]
    assert "previous_response_id" not in continuation
    assert continuation["instructions"] == initial["instructions"]
    assert continuation["input"] == [
        *initial["input"],
        reasoning,
        first.output[1],
        {
            "type": "function_call_output",
            "call_id": "call-1",
            "output": '{"text":"{\\"task\\":\\"public canonical metadata\\"}\\n"}',
        },
    ]
    assert tools.requests == [
        ToolRequest(
            request_id=f"{_request().request_id}:openai-tool:1",
            operation="read_text",
            arguments={"encoding": "utf-8"},
            input_paths=("task.json",),
        )
    ]
    assert result.public_summary == {
        "adapter_id": OPENAI_RESPONSES_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": OPENAI_RESPONSES_ADAPTER_VERSION,
        "auth_mode": "api-key-by-user-environment",
        "forecast_sha256": result.public_summary["forecast_sha256"],
        "input_tokens": 32,
        "model_key": "openai:gpt-test",
        "max_output_tokens_per_request": OPENAI_MAX_OUTPUT_TOKENS,
        "output_tokens": 10,
        "provider": "openai",
        "provider_request_count": 2,
        "python_version": result.public_summary["python_version"],
        "requested_model": "gpt-test",
        "sdk_name": "openai",
        "sdk_max_retries": OPENAI_SDK_MAX_RETRIES,
        "sdk_version": OPENAI_SDK_VERSION,
        "sandbox_policy_id": "provider-runtime",
        "provider_request_timeout_seconds": 30,
        "served_model": "gpt-served-snapshot",
        "subscription_login_claimed": False,
        "task_id": "lfb:case-1:full_packet",
        "tool_call_count": 1,
        "total_tokens": 42,
    }
    assert "response_id" not in result.public_summary
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.artifact_id == "openai-forecast-private"
    assert artifact.path == "private-logs/openai-forecast.json"
    assert artifact.sha256 == result.public_summary["forecast_sha256"]
    assert artifact.public is False
    assert artifact.size_bytes is not None
    private_forecast = json.loads(
        (tmp_path / "private-logs" / "openai-forecast.json").read_text()
    )
    assert private_forecast == forecast


@pytest.mark.parametrize(
    "allowed",
    [
        (),
        ("ANTHROPIC_API_KEY",),
        ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    ],
)
def test_live_run_requires_exact_openai_provider_grant(
    tmp_path: Path,
    allowed: tuple[str, ...],
) -> None:
    with pytest.raises(
        OpenAIResponsesAdapterError,
        match="exactly OPENAI_API_KEY",
    ):
        run_openai_responses(
            _request(allowed_provider_env_vars=allowed),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=_FakeClient([]),
        )


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (_FunctionCall(call_id="call-1", name="shell"), "unsupported tool"),
        (
            _FunctionCall(call_id="call-1", arguments='{"path":"task.json"}'),
            "arguments",
        ),
    ],
)
def test_live_run_rejects_unknown_or_malformed_tool_calls(
    tmp_path: Path,
    call: _FunctionCall,
    message: str,
) -> None:
    client = _FakeClient(
        [
            _response(
                response_id="resp-private",
                model="gpt-test",
                output=[call],
            )
        ]
    )

    with pytest.raises(OpenAIResponsesAdapterError, match=message):
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=client,
        )


@pytest.mark.parametrize("arguments", ["", " \t\n", "{}"])
def test_live_run_accepts_empty_arguments_for_zero_parameter_tool(
    tmp_path: Path,
    arguments: str,
) -> None:
    forecast = {
        "predictions": [
            {
                "unit_id": "count_i",
                "probability_fully_dismissed": 0.5,
            }
        ]
    }
    client = _FakeClient(
        [
            _response(
                response_id="resp-private-1",
                model="gpt-test",
                output=[
                    _FunctionCall(call_id="call-1", arguments=arguments),
                ],
            ),
            _response(
                response_id="resp-private-2",
                model="gpt-test",
                output=[],
                output_text=json.dumps(forecast),
            ),
        ]
    )

    result = run_openai_responses(
        _request(),
        tmp_path,
        tool_transport=_ToolTransport(),
        client=client,
    )

    assert result.status == "succeeded"


def test_live_run_rejects_duplicate_function_call_ids(tmp_path: Path) -> None:
    client = _FakeClient(
        [
            _response(
                response_id="resp-private-1",
                model="gpt-test",
                output=[_FunctionCall(call_id="call-1")],
            ),
            _response(
                response_id="resp-private-2",
                model="gpt-test",
                output=[_FunctionCall(call_id="call-1")],
            ),
        ]
    )

    with pytest.raises(OpenAIResponsesAdapterError, match="duplicate"):
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=client,
        )


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled", None])
def test_live_run_rejects_non_completed_responses(
    tmp_path: Path,
    status: str | None,
) -> None:
    response = _response(
        response_id="resp-private",
        model="gpt-test",
        output=[],
        output_text=json.dumps(
            {
                "predictions": [
                    {
                        "unit_id": "count_i",
                        "probability_fully_dismissed": 0.5,
                    }
                ]
            }
        ),
        status=status,
    )

    with pytest.raises(OpenAIResponsesAdapterError, match="did not complete"):
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=_FakeClient([response]),
        )


def test_live_run_enforces_tool_exchange_cap(tmp_path: Path) -> None:
    client = _FakeClient(
        [
            _response(
                response_id=f"resp-private-{index}",
                model="gpt-test",
                output=[_FunctionCall(call_id=f"call-{index}")],
            )
            for index in range(1, 4)
        ]
    )

    with pytest.raises(OpenAIResponsesAdapterError, match="tool call limit"):
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=client,
            max_tool_calls=2,
        )


@pytest.mark.parametrize(
    "forecast",
    [
        {"predictions": []},
        {
            "predictions": [
                {
                    "unit_id": "wrong",
                    "probability_fully_dismissed": 0.5,
                }
            ]
        },
        {
            "predictions": [
                {
                    "unit_id": "count_i",
                    "probability_fully_dismissed": 1.1,
                }
            ]
        },
        {
            "predictions": [
                {
                    "unit_id": "count_i",
                    "probability_fully_dismissed": math.nan,
                }
            ]
        },
    ],
)
def test_live_run_rejects_invalid_forecast(
    tmp_path: Path,
    forecast: dict[str, object],
) -> None:
    client = _FakeClient(
        [
            _response(
                response_id="resp-private",
                model="gpt-test",
                output=[],
                output_text=json.dumps(forecast),
            )
        ]
    )

    with pytest.raises(OpenAIResponsesAdapterError, match="forecast"):
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=client,
        )


def test_provider_exception_is_normalized_without_secret_or_account_details(
    tmp_path: Path,
) -> None:
    secret = "sk-test-secret-value"

    class _FailingResponses:
        def create(self, **kwargs: Any) -> object:
            del kwargs
            raise RuntimeError(
                f"Authorization: Bearer {secret}; organization_id=org-private"
            )

    client = SimpleNamespace(responses=_FailingResponses())

    with pytest.raises(
        OpenAIResponsesAdapterError,
        match=r"^OpenAI Responses request failed$",
    ) as captured:
        run_openai_responses(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            client=client,
        )

    assert secret not in str(captured.value)
    assert "org-private" not in str(captured.value)
    assert captured.value.__cause__ is None
    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert secret not in rendered
    assert "org-private" not in rendered


def _request(
    *,
    allowed_provider_env_vars: tuple[str, ...] = ("OPENAI_API_KEY",),
    fixture: str | None = None,
    model_key: str = "openai:gpt-test",
) -> RunRequest:
    metadata: dict[str, object] = {
        "required_unit_ids": ["count_i"],
        "candidate_id": "case-1",
    }
    if fixture is not None:
        metadata["fixture"] = fixture
    task = CanonicalTask(
        task_id="lfb:case-1:full_packet",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="legalforecast-mtd-v1",
        source_id="case-1",
        task_sha256="sha256:" + "1" * 64,
        metadata=metadata,
    )
    manifest = AdapterManifest(
        adapter_id=OPENAI_RESPONSES_ADAPTER_ID,
        display_name="OpenAI Responses Baseline",
        adapter_version=OPENAI_RESPONSES_ADAPTER_VERSION,
        command=("adapter.py",),
    )
    policy = SandboxPolicy(
        policy_id="provider-runtime",
        backend="podman",
        image="worker@sha256:" + "2" * 64,
        network_policy="provider-egress-host-only",
        timeout_seconds=30,
        allowed_provider_env_vars=allowed_provider_env_vars,
    )
    return RunRequest(
        request_id="request-1",
        task=task,
        adapter=manifest,
        model_key=model_key,
        sandbox_policy=policy,
        request_sha256="sha256:" + "3" * 64,
    )


def _response(
    *,
    response_id: str,
    model: str,
    output: list[object],
    output_text: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    status: str | None = "completed",
) -> object:
    return SimpleNamespace(
        id=response_id,
        model=model,
        output=output,
        output_text=output_text,
        status=status,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )

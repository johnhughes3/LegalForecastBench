from __future__ import annotations

import json
import tomllib
import traceback
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.multiharness.claude_agent_sdk import (
    CLAUDE_AGENT_SDK_ADAPTER_ID,
    CLAUDE_AGENT_SDK_ADAPTER_VERSION,
    CLAUDE_AGENT_SDK_VERSION,
    CLAUDE_BUNDLED_CLI_SHA256_BY_PLATFORM,
    CLAUDE_BUNDLED_CLI_VERSION,
    CLAUDE_MAX_BUDGET_USD,
    CLAUDE_MAX_TURNS,
    ClaudeAgentSDKAdapterError,
    ClaudeSDKExecution,
    ClaudeSDKRunConfig,
    build_capabilities,
    claude_bundled_runtime_pin,
    run_claude_agent_sdk,
    run_offline_protocol_fixture,
    validate_process_auth_environment,
)
from legalforecast.multiharness.claude_agent_sdk_cli import (
    PinnedClaudeSDKExecutor,
    _failure_stage,  # pyright: ignore[reportPrivateUsage]
    _runtime_identity,  # pyright: ignore[reportPrivateUsage]
    build_claude_agent_options,
)
from legalforecast.multiharness.claude_agent_sdk_cli import (
    main as adapter_main,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse

ROOT = Path(__file__).resolve().parents[1]


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


class _FakeExecutor:
    def __init__(
        self,
        execution: ClaudeSDKExecution | None = None,
        *,
        failure: Exception | None = None,
    ) -> None:
        self.configs: list[ClaudeSDKRunConfig] = []
        self.failure = failure
        self.execution = execution or _execution()

    def execute(
        self,
        config: ClaudeSDKRunConfig,
        *,
        tool_transport: _ToolTransport,
    ) -> ClaudeSDKExecution:
        self.configs.append(config)
        if self.failure is not None:
            raise self.failure
        response = tool_transport.execute(
            ToolRequest(
                request_id=f"{config.request_id}:claude-tool:1",
                operation="read_text",
                arguments={"encoding": "utf-8"},
                input_paths=("task.json",),
            )
        )
        assert response.status == "succeeded"
        return self.execution


def test_capabilities_are_real_lfb_only_and_advertise_live_tools() -> None:
    capabilities = build_capabilities()

    assert capabilities.adapter_id == CLAUDE_AGENT_SDK_ADAPTER_ID
    assert capabilities.adapter_version == CLAUDE_AGENT_SDK_ADAPTER_VERSION
    assert capabilities.supported_families == ("legalforecast_mtd",)
    assert capabilities.supported_scoring_modes == ("lfb_brier",)
    assert (
        capabilities.tool_protocol_version
        == "legalforecast.multiharness.tool_request.v1"
    )


def test_sdk_is_an_exact_optional_runtime_pin() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["optional-dependencies"]["claude-agent-sdk-adapter"] == [
        f"claude-agent-sdk=={CLAUDE_AGENT_SDK_VERSION}"
    ]
    assert CLAUDE_AGENT_SDK_VERSION == "0.2.128"
    assert CLAUDE_BUNDLED_CLI_VERSION == "2.1.220"
    assert CLAUDE_BUNDLED_CLI_SHA256_BY_PLATFORM["linux-x86_64"] == (
        "sha256:674f61f20ff306f3100cf9200e4c36c4b70278b5bef2884549819b942a89c863"
    )


def test_offline_protocol_fixture_is_credential_free_and_explicit(
    tmp_path: Path,
) -> None:
    result = run_offline_protocol_fixture(
        _request(
            allowed_provider_env_vars=(),
            fixture="adapter-conformance",
            model_key="conformance-fixture-model",
        ),
        tmp_path,
    )

    assert result.status == "succeeded"
    assert result.public_summary["offline_protocol_fixture"] is True
    assert result.public_summary["provider_request_count"] == 0
    assert result.public_summary["sdk_version"] == CLAUDE_AGENT_SDK_VERSION
    assert result.public_summary["bundled_cli_version"] == CLAUDE_BUNDLED_CLI_VERSION


def test_offline_protocol_fixture_rejects_non_conformance_runs(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="restricted to the adapter conformance fixture",
    ):
        run_offline_protocol_fixture(_request(), tmp_path)


def test_live_run_maps_isolated_config_and_records_safe_provenance(
    tmp_path: Path,
) -> None:
    executor = _FakeExecutor()
    tools = _ToolTransport()

    result = run_claude_agent_sdk(
        _request(),
        tmp_path,
        tool_transport=tools,
        executor=executor,
    )

    assert len(executor.configs) == 1
    config = executor.configs[0]
    assert config.requested_model == "claude-test"
    assert config.max_turns == CLAUDE_MAX_TURNS
    assert config.max_budget_usd == CLAUDE_MAX_BUDGET_USD
    assert config.working_directory == tmp_path / "private-logs" / "claude-workdir"
    assert config.config_directory == tmp_path / "private-logs" / "claude-config"
    assert str(uuid.UUID(config.session_id)) == config.session_id
    assert config.session_id == str(
        uuid.uuid5(uuid.NAMESPACE_URL, "legalforecast:request-1")
    )
    assert "count_i" in config.prompt
    assert config.output_schema["additionalProperties"] is False
    assert tools.requests == [
        ToolRequest(
            request_id="request-1:claude-tool:1",
            operation="read_text",
            arguments={"encoding": "utf-8"},
            input_paths=("task.json",),
        )
    ]
    summary = result.public_summary
    assert summary["auth_mode"] == "anthropic-api-key"
    assert summary["subscription_login_claimed"] is False
    assert summary["requested_model"] == "claude-test"
    assert summary["served_model"] == "claude-served-snapshot"
    assert summary["sdk_version"] == CLAUDE_AGENT_SDK_VERSION
    assert summary["bundled_cli_version"] == CLAUDE_BUNDLED_CLI_VERSION
    assert summary["bundled_cli_sha256"] == claude_bundled_runtime_pin()[1]
    assert "provider_request_count" not in summary
    assert summary["tool_call_count"] == 1
    assert summary["input_tokens"] == 12
    assert summary["output_tokens"] == 7
    assert summary["total_cost_usd"] == 0.03
    assert "session_id" not in summary
    assert "ANTHROPIC_API_KEY" not in json.dumps(summary)
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.public is False
    assert artifact.path == "private-logs/claude-structured-output.json"
    assert artifact.sha256 == summary["structured_output_sha256"]
    assert json.loads((tmp_path / artifact.path).read_text()) == _forecast()


@pytest.mark.parametrize(
    "allowed",
    [
        (),
        ("OPENAI_API_KEY",),
        ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
    ],
)
def test_live_run_requires_exact_anthropic_provider_grant(
    tmp_path: Path,
    allowed: tuple[str, ...],
) -> None:
    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="exactly ANTHROPIC_API_KEY",
    ):
        run_claude_agent_sdk(
            _request(allowed_provider_env_vars=allowed),
            tmp_path,
            tool_transport=_ToolTransport(),
            executor=_FakeExecutor(),
        )


@pytest.mark.parametrize(
    "name",
    ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"],
)
def test_subscription_credentials_are_rejected(name: str) -> None:
    with pytest.raises(ClaudeAgentSDKAdapterError, match="API-key"):
        validate_process_auth_environment({name: "subscription-secret"})


def test_provider_exception_is_normalized_without_secret_or_account_details(
    tmp_path: Path,
) -> None:
    secret = "sk-ant-test-secret"
    executor = _FakeExecutor(
        failure=RuntimeError(
            f"Authorization: Bearer {secret}; organization_id=org-private"
        )
    )

    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match=r"^Claude Agent SDK request failed$",
    ) as captured:
        run_claude_agent_sdk(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            executor=executor,
        )

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


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("tool_call_count", 0),
        ("tool_call_count", 2),
        ("sdk_version", "0.2.127"),
        ("bundled_cli_version", "2.1.219"),
        ("bundled_cli_sha256", "sha256:" + "4" * 64),
        ("served_model", ""),
        ("usage", {}),
        (
            "usage",
            {
                "input_tokens": 1,
                "output_tokens": 1,
                "cache_creation_input_tokens": 0,
            },
        ),
        ("usage", {"input_tokens": "secret"}),
        ("structured_output", {"predictions": []}),
        (
            "structured_output",
            {
                "case_assessment": "Assessment.",
                "predictions": [
                    {
                        "unit_id": "count_i",
                        "probability_fully_dismissed": 0.5,
                    }
                ],
                "provider_secret": "must-not-be-accepted",
            },
        ),
        (
            "structured_output",
            {
                "case_assessment": "Assessment.",
                "predictions": [
                    {
                        "unit_id": "count_i",
                        "probability_fully_dismissed": 0.5,
                        "provider_secret": "must-not-be-accepted",
                    }
                ],
            },
        ),
    ],
)
def test_live_run_rejects_invalid_sdk_execution(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    execution = replace(_execution(), **{field_name: value})

    with pytest.raises(ClaudeAgentSDKAdapterError):
        run_claude_agent_sdk(
            _request(),
            tmp_path,
            tool_transport=_ToolTransport(),
            executor=_FakeExecutor(execution),
        )


def test_sdk_options_disable_native_state_and_subscription_paths(
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    class _FakeSDK:
        @staticmethod
        def ClaudeAgentOptions(**kwargs: object) -> object:
            observed.update(kwargs)
            return object()

    config = ClaudeSDKRunConfig(
        request_id="request-1",
        requested_model="claude-test",
        prompt="prompt",
        output_schema={"type": "object"},
        working_directory=tmp_path / "workdir",
        config_directory=tmp_path / "config",
        session_id="lfb-session",
    )

    build_claude_agent_options(
        _FakeSDK,
        config,
        api_key="sk-ant-test",
        bundled_cli_path=tmp_path / "bundled" / "claude",
        mcp_server={"type": "sdk"},
    )

    assert observed["tools"] == []
    assert observed["allowed_tools"] == ["mcp__legalforecast__read_canonical_task"]
    assert observed["strict_mcp_config"] is True
    assert observed["permission_mode"] == "dontAsk"
    assert observed["setting_sources"] == []
    assert observed["skills"] == []
    assert observed["plugins"] == []
    assert observed["agents"] is None
    assert observed["hooks"] is None
    assert observed["fallback_model"] is None
    assert observed["resume"] is None
    assert observed["continue_conversation"] is False
    assert observed["fork_session"] is False
    assert observed["session_store"] is None
    assert observed["add_dirs"] == []
    assert observed["env"] == {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "CLAUDE_CONFIG_DIR": str(tmp_path / "config"),
    }
    assert observed["cwd"] == tmp_path / "workdir"
    assert observed["cli_path"] == tmp_path / "bundled" / "claude"
    assert observed["output_format"] == {
        "type": "json_schema",
        "schema": {"type": "object"},
    }


def test_runtime_identity_rejects_unpinned_bundled_cli_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "claude_agent_sdk"
    executable_name, _ = claude_bundled_runtime_pin()
    bundled_cli = package_root / "_bundled" / executable_name
    bundled_cli.parent.mkdir(parents=True)
    bundled_cli.write_bytes(b"unexpected bundled runtime")
    sdk = SimpleNamespace(__file__=str(package_root / "__init__.py"))
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli.importlib.metadata.version",
        lambda _name: CLAUDE_AGENT_SDK_VERSION,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli.importlib.import_module",
        lambda _name: SimpleNamespace(__cli_version__=CLAUDE_BUNDLED_CLI_VERSION),
    )

    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="bundled Claude Code digest does not match",
    ):
        _runtime_identity(sdk)


@pytest.mark.parametrize(
    ("sys_platform", "machine", "executable_name", "platform_key"),
    (
        ("darwin", "arm64", "claude", "darwin-arm64"),
        ("darwin", "x86_64", "claude", "darwin-x86_64"),
        ("linux", "aarch64", "claude", "linux-aarch64"),
        ("linux", "AMD64", "claude", "linux-x86_64"),
        ("win32", "AMD64", "claude.exe", "win32-x86_64"),
    ),
)
def test_runtime_pin_covers_every_locked_platform_wheel(
    sys_platform: str,
    machine: str,
    executable_name: str,
    platform_key: str,
) -> None:
    assert claude_bundled_runtime_pin(
        sys_platform=sys_platform,
        machine=machine,
    ) == (
        executable_name,
        CLAUDE_BUNDLED_CLI_SHA256_BY_PLATFORM[platform_key],
    )


def test_runtime_pin_rejects_unlocked_platform() -> None:
    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="Claude Agent SDK platform is not pinned",
    ):
        claude_bundled_runtime_pin(sys_platform="freebsd", machine="x86_64")


def test_pinned_executor_drives_fake_sdk_mcp_tool_and_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, observed = _fake_sdk(
        [
            _FakeAssistantMessage("claude-served-snapshot"),
            _FakeResultMessage(),
        ]
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._import_sdk",
        lambda: sdk,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._runtime_identity",
        lambda _sdk: {
            "sdk_version": CLAUDE_AGENT_SDK_VERSION,
            "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
            "bundled_cli_path": tmp_path / "bundled" / "claude",
            "bundled_cli_sha256": claude_bundled_runtime_pin()[1],
        },
    )
    tools = _ToolTransport()

    execution = PinnedClaudeSDKExecutor("sk-ant-test").execute(
        _sdk_config(tmp_path),
        tool_transport=tools,
    )

    assert execution.served_model == "claude-served-snapshot"
    assert execution.tool_call_count == 1
    assert tools.requests[0].input_paths == ("prompt.txt",)
    assert observed["query"] == ("prompt", "lfb-session")
    assert observed["tool_result"] == {
        "content": [
            {
                "type": "text",
                "text": '{"text":"{\\"task\\":\\"public canonical metadata\\"}\\n"}',
            }
        ]
    }
    options = observed["options"]
    assert isinstance(options, SimpleNamespace)
    assert options.model == "claude-test"
    assert options.env["ANTHROPIC_API_KEY"] == "sk-ant-test"


def test_pinned_executor_counts_malformed_mcp_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, _ = _fake_sdk(
        [
            _FakeAssistantMessage("claude-served-snapshot"),
            _FakeResultMessage(),
        ],
        tool_arguments=[{"unexpected": "argument"}, {}],
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._import_sdk",
        lambda: sdk,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._runtime_identity",
        lambda _sdk: {
            "sdk_version": CLAUDE_AGENT_SDK_VERSION,
            "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
            "bundled_cli_path": tmp_path / "bundled" / "claude",
            "bundled_cli_sha256": claude_bundled_runtime_pin()[1],
        },
    )

    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="exactly one solver prompt read",
    ):
        PinnedClaudeSDKExecutor("sk-ant-test").execute(
            _sdk_config(tmp_path),
            tool_transport=_ToolTransport(),
        )


def test_pinned_executor_rejects_malformed_only_mcp_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, _ = _fake_sdk(
        [
            _FakeAssistantMessage("claude-served-snapshot"),
            _FakeResultMessage(),
        ],
        tool_arguments=[{"unexpected": "argument"}],
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._import_sdk",
        lambda: sdk,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._runtime_identity",
        lambda _sdk: {
            "sdk_version": CLAUDE_AGENT_SDK_VERSION,
            "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
            "bundled_cli_path": tmp_path / "bundled" / "claude",
            "bundled_cli_sha256": claude_bundled_runtime_pin()[1],
        },
    )

    with pytest.raises(
        ClaudeAgentSDKAdapterError,
        match="exactly one solver prompt read",
    ):
        PinnedClaudeSDKExecutor("sk-ant-test").execute(
            _sdk_config(tmp_path),
            tool_transport=_ToolTransport(),
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no-terminal", "no terminal"),
        ("model-drift", "changed"),
        ("terminal-error", "not successful"),
        ("missing-model-usage", "model usage"),
        ("incomplete-model-usage", "model usage"),
        ("conflicting-model-usage", "aggregate usage"),
        ("missing-usage", "usage"),
    ],
)
def test_pinned_executor_fails_closed_on_invalid_sdk_message_sequences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    message: str,
) -> None:
    messages: list[object]
    if case == "no-terminal":
        messages = [_FakeAssistantMessage("claude-test")]
    elif case == "model-drift":
        messages = [
            _FakeAssistantMessage("claude-one"),
            _FakeAssistantMessage("claude-two"),
            _FakeResultMessage(),
        ]
    else:
        messages = [
            _FakeAssistantMessage("claude-test"),
            _FakeResultMessage(is_error=True, subtype="error"),
        ]
    if case == "missing-model-usage":
        terminal = _FakeResultMessage()
        terminal.model_usage = None
        messages = [_FakeAssistantMessage("claude-served-snapshot"), terminal]
    elif case == "incomplete-model-usage":
        terminal = _FakeResultMessage()
        terminal.model_usage = {"claude-served-snapshot": {}}
        messages = [_FakeAssistantMessage("claude-served-snapshot"), terminal]
    elif case == "conflicting-model-usage":
        terminal = _FakeResultMessage()
        terminal.model_usage["claude-served-snapshot"]["inputTokens"] = 13
        messages = [_FakeAssistantMessage("claude-served-snapshot"), terminal]
    elif case == "missing-usage":
        terminal = _FakeResultMessage()
        terminal.usage = None
        messages = [_FakeAssistantMessage("claude-served-snapshot"), terminal]
    sdk, _ = _fake_sdk(messages)
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._import_sdk",
        lambda: sdk,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli._runtime_identity",
        lambda _sdk: {
            "sdk_version": CLAUDE_AGENT_SDK_VERSION,
            "bundled_cli_version": CLAUDE_BUNDLED_CLI_VERSION,
            "bundled_cli_path": tmp_path / "bundled" / "claude",
            "bundled_cli_sha256": claude_bundled_runtime_pin()[1],
        },
    )

    with pytest.raises(ClaudeAgentSDKAdapterError, match=message):
        PinnedClaudeSDKExecutor("sk-ant-test").execute(
            _sdk_config(tmp_path),
            tool_transport=_ToolTransport(),
        )


def test_cli_missing_key_fails_with_constant_public_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request().to_record()), encoding="utf-8")
    stale_receipt_path = (
        tmp_path
        / "workspace"
        / "private-logs"
        / "claude-adapter-failure-00000000000000000000000000000000.json"
    )
    stale_receipt_path.parent.mkdir(parents=True)
    stale_receipt_path.write_text("stale receipt", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

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
    assert captured.err == "Claude Agent SDK adapter failed closed\n"
    assert not (tmp_path / "result.json").exists()
    receipt_paths = tuple(
        path
        for path in stale_receipt_path.parent.glob("claude-adapter-failure-*.json")
        if path != stale_receipt_path
    )
    assert len(receipt_paths) == 1
    receipt_path = receipt_paths[0]
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == {
        "attempt_id": receipt_path.stem.removeprefix("claude-adapter-failure-"),
        "schema_version": "legalforecast.claude_adapter_failure.v1",
        "stage": "provider_auth",
    }
    assert stale_receipt_path.read_text(encoding="utf-8") == "stale receipt"
    assert receipt_path.stat().st_mode & 0o777 == 0o600


def test_cli_does_not_mutate_symlinked_private_log_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request().to_record()), encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    external_receipt = external / "claude-adapter-failure-sentinel.json"
    external_receipt.write_text("external sentinel", encoding="utf-8")
    (workspace / "private-logs").symlink_to(external, target_is_directory=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("provider executor must not run for an unsafe workspace")

    monkeypatch.setattr(
        "legalforecast.multiharness.claude_agent_sdk_cli.run_claude_agent_sdk",
        fail_if_called,
    )

    status = adapter_main(
        [
            "run-with-tools",
            "--request",
            str(request_path),
            "--output",
            str(tmp_path / "result.json"),
            "--workspace",
            str(workspace),
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert captured.err == "Claude Agent SDK adapter failed closed\n"
    assert external_receipt.read_text(encoding="utf-8") == "external sentinel"
    assert {path.name for path in external.iterdir()} == {
        "claude-adapter-failure-sentinel.json"
    }


@pytest.mark.parametrize(
    ("message", "stage"),
    (
        ("Claude Agent SDK terminal result was not successful", "sdk_terminal"),
        ("Claude Agent SDK returned no terminal result", "sdk_request"),
        ("Claude Agent SDK returned multiple terminal results", "sdk_request"),
        ("Claude Agent SDK usage is invalid", "usage_accounting"),
        (
            "Claude Agent SDK served model identity changed within one run",
            "model_identity",
        ),
        (
            "Claude Agent SDK must complete exactly one solver prompt read",
            "tool_contract",
        ),
        ("Claude Agent SDK structured output is invalid", "structured_output"),
        ("unexpected adapter failure", "adapter_validation"),
    ),
)
def test_failure_stage_is_bounded_and_content_free(message: str, stage: str) -> None:
    assert _failure_stage(ClaudeAgentSDKAdapterError(message)) == stage


def _request(
    *,
    allowed_provider_env_vars: tuple[str, ...] = ("ANTHROPIC_API_KEY",),
    fixture: str | None = None,
    model_key: str = "anthropic:claude-test",
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
        adapter_id=CLAUDE_AGENT_SDK_ADAPTER_ID,
        display_name="Claude Agent SDK Baseline",
        adapter_version=CLAUDE_AGENT_SDK_ADAPTER_VERSION,
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


def _forecast() -> dict[str, object]:
    return {
        "case_assessment": "The public fixture supports a balanced forecast.",
        "predictions": [
            {
                "unit_id": "count_i",
                "probability_fully_dismissed": 0.7,
                "rationale": "Fixture rationale.",
            }
        ],
    }


def _execution() -> ClaudeSDKExecution:
    return ClaudeSDKExecution(
        structured_output=_forecast(),
        served_model="claude-served-snapshot",
        sdk_version=CLAUDE_AGENT_SDK_VERSION,
        bundled_cli_version=CLAUDE_BUNDLED_CLI_VERSION,
        bundled_cli_sha256=claude_bundled_runtime_pin()[1],
        tool_call_count=1,
        num_turns=2,
        duration_ms=1200,
        duration_api_ms=900,
        total_cost_usd=0.03,
        usage={
            "input_tokens": 12,
            "output_tokens": 7,
            "cache_creation_input_tokens": 2,
            "cache_read_input_tokens": 3,
        },
    )


class _FakeAssistantMessage:
    def __init__(self, model: str, error: str | None = None) -> None:
        self.model = model
        self.error = error


class _FakeResultMessage:
    def __init__(
        self,
        *,
        is_error: bool = False,
        subtype: str = "success",
    ) -> None:
        self.is_error = is_error
        self.subtype = subtype
        self.structured_output = _forecast()
        self.model_usage = {
            "claude-served-snapshot": {
                "inputTokens": 12,
                "outputTokens": 7,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "webSearchRequests": 0,
                "costUSD": 0.03,
                "contextWindow": 200_000,
                "maxOutputTokens": 64_000,
            }
        }
        self.num_turns = 2
        self.duration_ms = 1200
        self.duration_api_ms = 900
        self.total_cost_usd = 0.03
        self.usage = {
            "input_tokens": 12,
            "output_tokens": 7,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }


def _fake_sdk(
    messages: list[object],
    *,
    tool_arguments: list[dict[str, object]] | None = None,
) -> tuple[SimpleNamespace, dict[str, object]]:
    observed: dict[str, object] = {}

    def tool(
        name: str,
        description: str,
        input_schema: dict[str, object],
    ) -> object:
        observed["tool_contract"] = (name, description, input_schema)

        def decorate(handler: object) -> object:
            return handler

        return decorate

    def create_sdk_mcp_server(
        name: str,
        version: str,
        tools: list[object],
    ) -> dict[str, object]:
        return {"name": name, "version": version, "tools": tools}

    def options_factory(**kwargs: object) -> SimpleNamespace:
        options = SimpleNamespace(**kwargs)
        observed["options"] = options
        return options

    class Client:
        def __init__(self, options: SimpleNamespace) -> None:
            self.options = options

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc_value: object,
            traceback_value: object,
        ) -> bool:
            del exc_type, exc_value, traceback_value
            return False

        async def query(self, prompt: str, session_id: str) -> None:
            observed["query"] = (prompt, session_id)
            server = self.options.mcp_servers["legalforecast"]
            handler = server["tools"][0]
            arguments = tool_arguments if tool_arguments is not None else [{}]
            for item in arguments:
                observed["tool_result"] = await handler(item)

        async def receive_response(self) -> object:
            for message in messages:
                yield message

    return (
        SimpleNamespace(
            AssistantMessage=_FakeAssistantMessage,
            ResultMessage=_FakeResultMessage,
            ClaudeSDKClient=Client,
            ClaudeAgentOptions=options_factory,
            create_sdk_mcp_server=create_sdk_mcp_server,
            tool=tool,
        ),
        observed,
    )


def _sdk_config(tmp_path: Path) -> ClaudeSDKRunConfig:
    return ClaudeSDKRunConfig(
        request_id="request-1",
        requested_model="claude-test",
        prompt="prompt",
        output_schema={"type": "object"},
        working_directory=tmp_path / "workdir",
        config_directory=tmp_path / "config",
        session_id="lfb-session",
    )

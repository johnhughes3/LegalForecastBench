"""Command adapter entry point for the pinned Claude Agent SDK baseline."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.claude_agent_sdk import (
    CLAUDE_AGENT_SDK_VERSION,
    CLAUDE_BUNDLED_CLI_VERSION,
    CLAUDE_PROVIDER_ENV_VAR,
    ClaudeAgentSDKAdapterError,
    ClaudeSDKExecution,
    ClaudeSDKExecutor,
    ClaudeSDKRunConfig,
    ToolTransport,
    build_capabilities,
    claude_bundled_runtime_pin,
    current_process_environment,
    run_async,
    run_claude_agent_sdk,
    run_offline_protocol_fixture,
    validate_process_auth_environment,
    validate_provider_grant,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolRequest,
    ToolResponse,
    decode_tool_response,
    encode_tool_message,
)

_TOOL_CALL_TIMEOUT_SECONDS = 60.0
_FAILURE_RECEIPT_SCHEMA_VERSION = "legalforecast.claude_adapter_failure.v1"


class StdioToolTransport:
    """Exchange one request and response at a time over the host JSONL channel."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Send one bounded request and decode its matching response."""

        sys.stdout.buffer.write(encode_tool_message(request))
        sys.stdout.buffer.flush()
        response = sys.stdin.buffer.readline(MAX_TOOL_MESSAGE_BYTES + 2)
        if not response:
            raise ClaudeAgentSDKAdapterError("host tool channel closed")
        return decode_tool_response(response)


class PinnedClaudeSDKExecutor(ClaudeSDKExecutor):
    """Execute one session with the exact installed SDK and bundled CLI."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def execute(
        self,
        config: ClaudeSDKRunConfig,
        *,
        tool_transport: ToolTransport,
    ) -> ClaudeSDKExecution:
        """Run the asynchronous SDK session from the synchronous adapter."""

        return cast(
            ClaudeSDKExecution,
            run_async(
                self._execute_async(
                    config,
                    tool_transport=tool_transport,
                )
            ),
        )

    async def _execute_async(
        self,
        config: ClaudeSDKRunConfig,
        *,
        tool_transport: ToolTransport,
    ) -> ClaudeSDKExecution:
        sdk = _import_sdk()
        identity = _runtime_identity(sdk)
        tool_call_count = [0]
        successful_tool_reads: list[int] = [0]

        @sdk.tool(
            "read_canonical_task",
            "Read the complete solver prompt staged by the host.",
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )
        async def read_canonical_task(
            arguments: Mapping[str, object],
        ) -> dict[str, Any]:
            tool_call_count[0] += 1
            if arguments:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "canonical task tool accepts no arguments",
                        }
                    ],
                    "is_error": True,
                }
            tool_request = ToolRequest(
                request_id=f"{config.request_id}:claude-tool:{tool_call_count[0]}",
                operation="read_text",
                arguments={"encoding": "utf-8"},
                input_paths=(SOLVER_INPUT_ENTRY_PATH,),
            )
            response = await asyncio.wait_for(
                asyncio.to_thread(tool_transport.execute, tool_request),
                timeout=_TOOL_CALL_TIMEOUT_SECONDS,
            )
            if response.request_id != tool_request.request_id:
                raise ClaudeAgentSDKAdapterError(
                    "host tool response request id does not match"
                )
            if response.status != "succeeded":
                raise ClaudeAgentSDKAdapterError("host tool request failed")
            successful_tool_reads[0] += 1
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            response.to_record()["output"],
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                ]
            }

        server = sdk.create_sdk_mcp_server(
            name="legalforecast",
            version="1.0.0",
            tools=[read_canonical_task],
        )
        options = build_claude_agent_options(
            sdk,
            config,
            api_key=self._api_key,
            bundled_cli_path=identity["bundled_cli_path"],
            mcp_server=server,
        )
        assistant_models: set[str] = set()
        terminal: Any | None = None
        try:
            async with sdk.ClaudeSDKClient(options) as client:
                await client.query(config.prompt, session_id=config.session_id)
                async for message in client.receive_response():
                    if isinstance(message, sdk.AssistantMessage):
                        if message.error is not None:
                            raise ClaudeAgentSDKAdapterError(
                                "Claude Agent SDK assistant response failed"
                            )
                        if (
                            not isinstance(message.model, str)
                            or not message.model.strip()
                        ):
                            raise ClaudeAgentSDKAdapterError(
                                "Claude Agent SDK served model is missing"
                            )
                        assistant_models.add(message.model)
                    elif isinstance(message, sdk.ResultMessage):
                        if terminal is not None:
                            raise ClaudeAgentSDKAdapterError(
                                "Claude Agent SDK returned multiple terminal results"
                            )
                        terminal = message
        except ClaudeAgentSDKAdapterError:
            raise
        except Exception:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK request failed"
            ) from None
        if terminal is None:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK returned no terminal result"
            )
        if terminal.is_error or terminal.subtype != "success":
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK terminal result was not successful"
            )
        if len(assistant_models) != 1:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK served model identity changed within one run"
            )
        served_model = next(iter(assistant_models))
        usage = _usage_record(terminal.usage)
        total_cost_usd = _non_negative_number(
            terminal.total_cost_usd,
            "total_cost_usd",
        )
        _validate_model_usage(
            terminal.model_usage,
            served_model,
            aggregate_usage=usage,
            total_cost_usd=total_cost_usd,
        )
        if tool_call_count[0] != 1 or successful_tool_reads[0] != 1:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK must complete exactly one solver prompt read"
            )
        return ClaudeSDKExecution(
            structured_output=terminal.structured_output,
            served_model=served_model,
            sdk_version=identity["sdk_version"],
            bundled_cli_version=identity["bundled_cli_version"],
            bundled_cli_sha256=identity["bundled_cli_sha256"],
            tool_call_count=tool_call_count[0],
            num_turns=_non_negative_int(terminal.num_turns, "num_turns"),
            duration_ms=_non_negative_int(terminal.duration_ms, "duration_ms"),
            duration_api_ms=_non_negative_int(
                terminal.duration_api_ms,
                "duration_api_ms",
            ),
            total_cost_usd=total_cost_usd,
            usage=usage,
        )


def build_claude_agent_options(
    sdk: Any,
    config: ClaudeSDKRunConfig,
    *,
    api_key: str,
    bundled_cli_path: Path,
    mcp_server: object,
) -> Any:
    """Build the exact isolated options passed to the pinned SDK client."""

    return sdk.ClaudeAgentOptions(
        tools=[],
        allowed_tools=["mcp__legalforecast__read_canonical_task"],
        system_prompt=(
            "You are a bounded LegalForecastBench forecasting adapter. "
            "Use only the host-owned solver prompt tool and return only the "
            "required structured output."
        ),
        mcp_servers={"legalforecast": mcp_server},
        strict_mcp_config=True,
        permission_mode="dontAsk",
        continue_conversation=False,
        resume=None,
        session_id=config.session_id,
        max_turns=config.max_turns,
        max_budget_usd=config.max_budget_usd,
        disallowed_tools=[],
        model=config.requested_model,
        fallback_model=None,
        cwd=config.working_directory,
        cli_path=bundled_cli_path,
        settings=None,
        add_dirs=[],
        env={
            CLAUDE_PROVIDER_ENV_VAR: api_key,
            "CLAUDE_CONFIG_DIR": str(config.config_directory),
        },
        extra_args={},
        can_use_tool=None,
        hooks=None,
        include_partial_messages=False,
        include_hook_events=False,
        fork_session=False,
        agents=None,
        setting_sources=[],
        skills=[],
        sandbox=None,
        plugins=[],
        output_format={
            "type": "json_schema",
            "schema": dict(config.output_schema),
        },
        enable_file_checkpointing=False,
        session_store=None,
    )


def main(argv: list[str] | None = None) -> int:
    """Run one adapter protocol command."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)
    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--output", type=Path, required=True)
    for phase in ("run", "run-with-tools"):
        command = subparsers.add_parser(phase)
        command.add_argument("--request", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args(argv)
    failure_attempt_id = (
        secrets.token_hex(16) if args.phase == "run-with-tools" else None
    )
    failure_receipt_path = (
        _safe_failure_receipt_path(args.workspace, failure_attempt_id)
        if failure_attempt_id is not None
        else None
    )
    if args.phase == "run-with-tools" and failure_receipt_path is None:
        print("Claude Agent SDK adapter failed closed", file=sys.stderr)
        return 1
    try:
        if args.phase == "capabilities":
            write_json_object(args.output, build_capabilities().to_record())
            return 0
        request = RunRequest.from_record(_read_json_object(args.request))
        if args.phase == "run":
            result = run_offline_protocol_fixture(request, args.workspace)
        else:
            validate_provider_grant(request)
            validate_process_auth_environment(current_process_environment())
            api_key = os.environ.get(CLAUDE_PROVIDER_ENV_VAR)
            if api_key is None or not api_key.strip():
                raise ClaudeAgentSDKAdapterError(
                    "ANTHROPIC_API_KEY must be set and non-empty"
                )
            result = run_claude_agent_sdk(
                request,
                args.workspace,
                tool_transport=StdioToolTransport(),
                executor=PinnedClaudeSDKExecutor(api_key),
            )
        write_json_object(args.output, result.to_record())
        return 0
    except Exception as exc:
        if failure_receipt_path is not None and failure_attempt_id is not None:
            _write_failure_receipt(failure_receipt_path, failure_attempt_id, exc)
        print("Claude Agent SDK adapter failed closed", file=sys.stderr)
        return 1


def _write_failure_receipt(path: Path, attempt_id: str, error: Exception) -> None:
    """Persist only a bounded failure stage beneath the private log tree."""

    try:
        safe_path = _safe_failure_receipt_path(path.parent.parent, attempt_id)
        if safe_path != path:
            return
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        write_json_object(
            path,
            {
                "attempt_id": attempt_id,
                "schema_version": _FAILURE_RECEIPT_SCHEMA_VERSION,
                "stage": _failure_stage(error),
            },
        )
        path.chmod(0o600)
    except OSError:
        return


def _safe_failure_receipt_path(workspace: Path, attempt_id: str) -> Path | None:
    """Resolve a receipt target without following workspace-local symlinks."""

    try:
        if workspace.is_symlink() or (workspace.exists() and not workspace.is_dir()):
            return None
        workspace_root = workspace.resolve(strict=False)
        private_logs = workspace / "private-logs"
        if private_logs.is_symlink() or (
            private_logs.exists() and not private_logs.is_dir()
        ):
            return None
        private_logs_root = private_logs.resolve(strict=False)
        if private_logs_root != workspace_root / "private-logs":
            return None
        if len(attempt_id) != 32 or any(
            char not in "0123456789abcdef" for char in attempt_id
        ):
            return None
        path = private_logs / f"claude-adapter-failure-{attempt_id}.json"
        if path.exists() or path.is_symlink():
            return None
        return path
    except OSError:
        return None


def _failure_stage(error: Exception) -> str:
    """Map internal failures onto a content-free diagnostic vocabulary."""

    if not isinstance(error, ClaudeAgentSDKAdapterError):
        return "adapter_validation"
    message = str(error)
    if "structured output" in message or "case assessment" in message:
        return "structured_output"
    if "usage" in message or "cost" in message:
        return "usage_accounting"
    if "no terminal result" in message or "multiple terminal result" in message:
        return "sdk_request"
    if "terminal result" in message:
        return "sdk_terminal"
    if "served model" in message or "model identity" in message:
        return "model_identity"
    if (
        "host tool" in message
        or "canonical task tool" in message
        or "solver prompt read" in message
    ):
        return "tool_contract"
    if "SDK request" in message or "assistant response" in message:
        return "sdk_request"
    if (
        "provider environment" in message
        or "API-key" in message
        or "ANTHROPIC_API_KEY" in message
    ):
        return "provider_auth"
    return "adapter_validation"


def _import_sdk() -> Any:
    try:
        import claude_agent_sdk
    except ImportError:
        raise ClaudeAgentSDKAdapterError(
            "claude-agent-sdk-adapter optional dependency is required"
        ) from None
    return cast(Any, claude_agent_sdk)


def _runtime_identity(sdk: Any) -> dict[str, Any]:
    observed_sdk = importlib.metadata.version("claude-agent-sdk")
    if observed_sdk != CLAUDE_AGENT_SDK_VERSION:
        raise ClaudeAgentSDKAdapterError(
            "installed Claude Agent SDK version does not match"
        )
    try:
        cli_version_module = importlib.import_module("claude_agent_sdk._cli_version")
        observed_cli_version = cast(str, cli_version_module.__cli_version__)
    except (AttributeError, ImportError):
        raise ClaudeAgentSDKAdapterError(
            "bundled Claude Code version is unavailable"
        ) from None
    if observed_cli_version != CLAUDE_BUNDLED_CLI_VERSION:
        raise ClaudeAgentSDKAdapterError("bundled Claude Code version does not match")
    executable_name, expected_sha256 = claude_bundled_runtime_pin()
    package_path = Path(cast(str, sdk.__file__)).resolve().parent
    bundled_cli_path = package_path / "_bundled" / executable_name
    try:
        with bundled_cli_path.open("rb") as stream:
            bundled_cli_sha256 = (
                f"sha256:{hashlib.file_digest(stream, 'sha256').hexdigest()}"
            )
    except OSError:
        raise ClaudeAgentSDKAdapterError(
            "bundled Claude Code executable is unavailable"
        ) from None
    if bundled_cli_sha256 != expected_sha256:
        raise ClaudeAgentSDKAdapterError("bundled Claude Code digest does not match")
    return {
        "sdk_version": observed_sdk,
        "bundled_cli_version": observed_cli_version,
        "bundled_cli_path": bundled_cli_path,
        "bundled_cli_sha256": bundled_cli_sha256,
    }


def _validate_model_usage(
    model_usage: object,
    served_model: str,
    *,
    aggregate_usage: Mapping[str, object],
    total_cost_usd: float,
) -> None:
    if not isinstance(model_usage, Mapping) or not model_usage:
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK model usage is invalid")
    record = cast(Mapping[object, object], model_usage)
    keys = tuple(record)
    if len(keys) != 1 or not isinstance(keys[0], str) or keys[0] != served_model:
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK model usage conflicts with served model"
        )
    value = record[keys[0]]
    if not isinstance(value, Mapping):
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK model usage is invalid")
    details = cast(Mapping[object, object], value)
    integer_fields = (
        "inputTokens",
        "outputTokens",
        "cacheReadInputTokens",
        "cacheCreationInputTokens",
        "webSearchRequests",
        "contextWindow",
        "maxOutputTokens",
    )
    for field_name in integer_fields:
        if field_name not in details:
            raise ClaudeAgentSDKAdapterError(
                "Claude Agent SDK model usage is incomplete"
            )
        _non_negative_int(details[field_name], field_name)
    if "costUSD" not in details:
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK model usage is incomplete")
    model_cost_usd = _non_negative_number(details["costUSD"], "costUSD")
    expected_tokens = {
        "inputTokens": aggregate_usage["input_tokens"],
        "outputTokens": aggregate_usage["output_tokens"],
        "cacheReadInputTokens": aggregate_usage["cache_read_input_tokens"],
        "cacheCreationInputTokens": aggregate_usage["cache_creation_input_tokens"],
    }
    if any(details[name] != expected for name, expected in expected_tokens.items()):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK model usage conflicts with aggregate usage"
        )
    if not math.isclose(model_cost_usd, total_cost_usd, rel_tol=0, abs_tol=1e-9):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK model cost conflicts with terminal cost"
        )


def _usage_record(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ClaudeAgentSDKAdapterError("Claude Agent SDK usage is invalid")
    record = cast(Mapping[object, object], value)
    allowed = (
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "input_tokens",
        "output_tokens",
    )
    if any(name not in record for name in allowed):
        raise ClaudeAgentSDKAdapterError(
            "Claude Agent SDK usage is missing required token dimensions"
        )
    return {name: record[name] for name in allowed}


def _non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ClaudeAgentSDKAdapterError(f"Claude Agent SDK {field_name} is invalid")
    return value


def _non_negative_number(value: object, field_name: str) -> float:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ClaudeAgentSDKAdapterError(f"Claude Agent SDK {field_name} is invalid")
    return float(value)


def _read_json_object(path: Path) -> dict[str, Any]:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise ClaudeAgentSDKAdapterError("request must be a JSON object")
    return cast(dict[str, Any], decoded)


if __name__ == "__main__":
    raise SystemExit(main())

"""Invoke OpenClaw's managed embedded runner with an isolated host tool socket."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.host_environment import (
    build_host_subprocess_environment,
)
from legalforecast.multiharness.openclaw import (
    OPENCLAW_COMMIT,
    OPENCLAW_VERSION,
    TOOL_NAME,
    OpenClawError,
    ToolTransport,
    normalize_result,
    unit_ids,
    validate_request,
)
from legalforecast.multiharness.openclaw_tool import PromptDelivery, bridge_read
from legalforecast.multiharness.sandbox import PROVIDER_EGRESS_HOST_ONLY
from legalforecast.multiharness.spec import RunRequest, RunResult

GATEWAY_BASE_URL = "http://lfb-model-gateway:8080"


@dataclass(frozen=True, slots=True)
class GatewayRuntimeConfig:
    """Non-provider capability and frozen model limits for the contained worker."""

    capability: str
    context_limit: int
    max_output_tokens: int
    reasoning_effort: str = "high"

    def __post_init__(self) -> None:
        if not self.capability or any(c in self.capability for c in "\r\n"):
            raise OpenClawError("gateway capability must be a nonempty header value")
        if self.context_limit <= 0 or self.max_output_tokens <= 0:
            raise OpenClawError("gateway model limits must be positive")
        if self.reasoning_effort != "high":
            raise OpenClawError("OpenClaw gateway supports only pinned high reasoning")


def runtime_root() -> Path:
    """Locate the separately installed, source-checkout community runtime."""
    return (
        Path(__file__).resolve().parents[2]
        / "examples/adapters/openclaw-pinned/node_modules/openclaw"
    )


def verify_runtime(root: Path) -> Path:
    """Check both the distribution version and its recorded upstream revision."""
    try:
        package = json.loads((root / "package.json").read_text())
        build = json.loads((root / "dist/build-info.json").read_text())
    except (OSError, ValueError):
        raise OpenClawError(
            "Pinned OpenClaw runtime is unavailable; install its locked package"
        ) from None
    if (
        package.get("version") != OPENCLAW_VERSION
        or build.get("version") != OPENCLAW_VERSION
    ):
        raise OpenClawError("OpenClaw runtime version mismatch")
    if build.get("commit") != OPENCLAW_COMMIT:
        raise OpenClawError("OpenClaw runtime commit mismatch")
    entry = root / "openclaw.mjs"
    if not entry.is_file():
        raise OpenClawError("OpenClaw runtime entrypoint unavailable")
    return entry.resolve()


def build_config(
    model: str, descriptor: int, *, gateway: GatewayRuntimeConfig | None = None
) -> dict[str, Any]:
    """Select the built-in managed runtime and only the host-owned read tool."""
    provider = "openai" if gateway is None else "anthropic"
    config: dict[str, Any] = {
        "agents": {
            "defaults": {
                "models": {f"{provider}/{model}": {"agentRuntime": {"id": "openclaw"}}},
                "model": {"primary": f"{provider}/{model}", "fallbacks": []},
            }
        },
        "tools": {
            "profile": "minimal",
            "alsoAllow": [TOOL_NAME],
            "deny": ["session_status", "gateway"],
            "codeMode": {"enabled": False},
            "toolSearch": False,
        },
        "plugins": {
            "allow": [provider, "lfb-container-tool"],
            "load": {"paths": [str(Path(__file__).with_name("openclaw_plugin"))]},
            "entries": {
                "lfb-container-tool": {
                    "enabled": True,
                    "config": {"descriptor": descriptor},
                }
            },
        },
        "env": {"shellEnv": {"enabled": False}},
    }
    if gateway is not None:
        config["agents"]["defaults"]["thinkingDefault"] = gateway.reasoning_effort
        config["models"] = {
            "providers": {
                "anthropic": {
                    "baseUrl": GATEWAY_BASE_URL,
                    "api": "anthropic-messages",
                    "apiKey": gateway.capability,
                    "models": [
                        {
                            "id": model,
                            "name": model,
                            "input": ["text"],
                            "reasoning": True,
                            "contextWindow": gateway.context_limit,
                            "maxTokens": gateway.max_output_tokens,
                        }
                    ],
                }
            }
        }
    return config


def run_openclaw(
    request: RunRequest,
    workspace: Path,
    transport: ToolTransport,
    *,
    gateway: GatewayRuntimeConfig | None = None,
) -> RunResult:
    """Run one managed OpenClaw turn; model tools never receive provider keys."""
    validate_request(request)
    expected_grant = ("OPENAI_API_KEY",) if gateway is None else ()
    if request.sandbox_policy.allowed_provider_env_vars != expected_grant:
        raise OpenClawError(
            "OpenClaw provider grant must be exactly OPENAI_API_KEY"
            if gateway is None
            else "contained OpenClaw must not receive a provider credential grant"
        )
    if request.sandbox_policy.network_policy != PROVIDER_EGRESS_HOST_ONLY:
        raise OpenClawError(f"OpenClaw requires {PROVIDER_EGRESS_HOST_ONLY} policy")
    provider, separator, model = request.model_key.partition(":")
    expected_provider = "openai" if gateway is None else "anthropic"
    if provider != expected_provider or not separator or not model.strip():
        raise OpenClawError(f"OpenClaw model must use {expected_provider}:<model>")
    required = unit_ids(request)
    entry = verify_runtime(runtime_root())
    node = shutil.which("node")
    if node is None:
        raise OpenClawError("OpenClaw requires Node 24.16+ or 26.1+")
    # The shared environment helper drops ambient auth, endpoint overrides,
    # NODE_OPTIONS, proxies, and home/config state before the child starts.
    private = workspace / "private-logs"
    build_host_subprocess_environment(private)
    private = private.resolve()
    with tempfile.TemporaryDirectory(prefix="openclaw-", dir=private) as temporary:
        root = Path(temporary)
        environment = build_host_subprocess_environment(root, expected_grant)
        work = root / "work"
        work.mkdir(mode=0o700)
        state = root / "state"
        state.mkdir(mode=0o700)
        environment.update(
            {
                "OPENCLAW_HOME": str(root),
                "OPENCLAW_STATE_DIR": str(state),
                "OPENCLAW_CONFIG_PATH": str(root / "config.json"),
                "OPENCLAW_LOAD_SHELL_ENV": "0",
                "OPENCLAW_NO_RESPAWN": "1",
                "NODE_DISABLE_COMPILE_CACHE": "1",
            }
        )
        host, child = socket.socketpair()
        host.settimeout(60)
        delivery = PromptDelivery()
        failures: list[BaseException] = []
        worker = threading.Thread(
            target=bridge_read,
            args=(host, transport, request.request_id, delivery, failures),
            daemon=True,
        )
        try:
            config_path = root / "config.json"
            write_json_object(
                config_path,
                build_config(model, child.fileno())
                if gateway is None
                else build_config(model, child.fileno(), gateway=gateway),
            )
            config_path.chmod(0o600)
            prompt_path = root / "prompt.txt"
            prompt_path.write_text(
                f"Read the complete solver prompt with {TOOL_NAME}, starting with "
                'page 0 and receipt "". Each result supplies next_page and a receipt: '
                "pass both back to the same tool until it confirms complete=true. "
                "Do not forecast before acknowledging the final page. "
                "Use only that prompt. Return only a JSON object with a nonempty "
                "case_assessment and predictions array. Each prediction has unit_id "
                "and probability_fully_dismissed between 0 and 1. Include exactly "
                "these unit IDs: " + json.dumps(required),
                encoding="utf-8",
            )
            prompt_path.chmod(0o600)
            worker.start()
            # Inherit the public CommandAdapter's containment/process group so
            # its timeout and signal cleanup also owns this runtime's descendants.
            with (
                (private / "openclaw-stdout.json").open("wb") as stdout,
                (private / "openclaw-stderr.log").open("wb") as stderr,
            ):
                os.chmod(stdout.name, 0o600)
                os.chmod(stderr.name, 0o600)
                completed = subprocess.run(
                    [
                        node,
                        str(entry),
                        "agent",
                        "exec",
                        "--config",
                        str(config_path),
                        "--message-file",
                        str(prompt_path),
                        "--cwd",
                        str(work),
                        "--model",
                        f"{provider}/{model}",
                        "--json",
                        "--timeout",
                        str(
                            max(1, min(120, request.sandbox_policy.timeout_seconds - 5))
                        ),
                    ],
                    env=environment,
                    cwd=work,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    pass_fds=(child.fileno(),),
                    timeout=min(130, request.sandbox_policy.timeout_seconds),
                    check=False,
                )
            child.close()
            worker.join(timeout=1)
            if completed.returncode != 0 or failures or worker.is_alive():
                raise OpenClawError("OpenClaw managed run or host tool channel failed")
            payload = (private / "openclaw-stdout.json").read_bytes()
            if len(payload) > 1_048_576:
                raise OpenClawError("OpenClaw result exceeds size limit")
            envelope: object = json.loads(payload)
            if not isinstance(envelope, Mapping):
                raise OpenClawError("OpenClaw result must be an object")
            return normalize_result(
                request,
                workspace,
                cast(Mapping[str, Any], envelope),
                tool_reads=delivery.tool_calls,
                prompt_complete=delivery.complete,
                gateway_auth=gateway is not None,
            )
        except subprocess.TimeoutExpired:
            raise OpenClawError("OpenClaw managed run timed out") from None
        finally:
            child.close()
            host.close()

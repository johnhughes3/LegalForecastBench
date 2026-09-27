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
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import RunRequest, RunResult
from legalforecast.multiharness.tool_protocol import ToolRequest, encode_tool_message


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


def build_config(model: str, descriptor: int) -> dict[str, Any]:
    """Select the built-in managed runtime and only the host-owned read tool."""
    return {
        "agents": {
            "defaults": {
                "models": {f"openai/{model}": {"agentRuntime": {"id": "openclaw"}}},
                "model": {"primary": f"openai/{model}", "fallbacks": []},
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
            "allow": ["openai", "lfb-container-tool"],
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


def bridge_read(
    channel: socket.socket,
    transport: ToolTransport,
    request_id: str,
    reads: list[int],
    failures: list[BaseException],
) -> None:
    """Translate the plugin's sole operation into the existing container protocol."""
    try:
        with channel.makefile("rb") as reader:
            message = reader.readline(256)
            if message != b'{"operation":"read_solver_prompt"}\n':
                raise OpenClawError("OpenClaw tool sent an unsupported operation")
            request = ToolRequest(
                request_id=f"{request_id}:openclaw:read",
                operation="read_text",
                arguments={"encoding": "utf-8"},
                input_paths=(SOLVER_INPUT_ENTRY_PATH,),
            )
            response = transport.execute(request)
            if (
                response.request_id != request.request_id
                or response.status != "succeeded"
            ):
                raise OpenClawError("OpenClaw host tool response failed or mismatched")
            channel.sendall(encode_tool_message(response))
            reads.append(1)
    except (OSError, ValueError, RuntimeError) as exc:
        failures.append(exc)
    finally:
        channel.close()


def run_openclaw(
    request: RunRequest,
    workspace: Path,
    transport: ToolTransport,
) -> RunResult:
    """Run one managed OpenClaw turn; model tools never receive provider keys."""
    validate_request(request)
    if request.sandbox_policy.allowed_provider_env_vars != ("OPENAI_API_KEY",):
        raise OpenClawError("OpenClaw provider grant must be exactly OPENAI_API_KEY")
    if request.sandbox_policy.network_policy != "provider-egress-host-only":
        raise OpenClawError("OpenClaw requires provider-egress-host-only policy")
    if not request.model_key.startswith("openai:") or not request.model_key[7:].strip():
        raise OpenClawError("OpenClaw model must use openai:<model>")
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
        environment = build_host_subprocess_environment(root, ("OPENAI_API_KEY",))
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
        reads: list[int] = []
        failures: list[BaseException] = []
        worker = threading.Thread(
            target=bridge_read,
            args=(host, transport, request.request_id, reads, failures),
            daemon=True,
        )
        try:
            config_path = root / "config.json"
            write_json_object(
                config_path, build_config(request.model_key[7:], child.fileno())
            )
            config_path.chmod(0o600)
            prompt_path = root / "prompt.txt"
            prompt_path.write_text(
                f"Call {TOOL_NAME} exactly once to read the complete solver prompt. "
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
                        f"openai/{request.model_key[7:]}",
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
                tool_reads=len(reads),
            )
        except subprocess.TimeoutExpired:
            raise OpenClawError("OpenClaw managed run timed out") from None
        finally:
            child.close()
            host.close()

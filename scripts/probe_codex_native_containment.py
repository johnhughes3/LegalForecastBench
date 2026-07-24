#!/usr/bin/env python3
"""Characterize the installed Codex native loop without provider spend.

The probe uses a loopback-only deterministic Responses API stub. It first tries
Codex's requested ``workspace-write`` sandbox. If the host cannot initialize
that sandbox, it records the failure and runs the same native-loop probes under
an explicitly non-claimable ``danger-full-access`` diagnostic profile. The
fallback proves only CLI/tool behavior; it can never authorize the clean-native
containment claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "legalforecast.codex_native_containment_probe.v1"
DEFAULT_EXPECTED_SHA256 = (
    "058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600"
)
EXPECTED_VERSION = "codex-cli 0.144.5"
EXPECTED_EXECUTABLE = "codex-x86_64-unknown-linux-musl"
DELIVERABLE_CONTENT = "FINAL NATIVE_BOUNDARY_OK\n"
CREDENTIAL_CANARY = "LFB_CREDENTIAL_CHILD_CANARY_DO_NOT_INHERIT"
AMBIENT_MARKERS = {
    "config": "LFB_AMBIENT_CONFIG_CANARY",
    "mcp": "LFB_AMBIENT_MCP_CANARY",
    "project_instructions": "LFB_AMBIENT_PROJECT_INSTRUCTIONS_CANARY",
    "rules": "LFB_AMBIENT_RULES_CANARY",
    "skills": "LFB_AMBIENT_SKILLS_CANARY",
}
DISABLED_STOCK_CAPABILITIES = [
    "apps and connectors",
    "browser and computer use",
    "hooks",
    "image generation",
    "live web search",
    "memories",
    "plugins",
    "remote control",
]
FEATURE_DISABLE_KEYS = [
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "hooks",
    "image_generation",
    "in_app_browser",
    "memories",
    "network_proxy",
    "remote_control",
    "remote_plugin",
    "standalone_web_search",
]
DELEGATION_TOOL_NAMES = {
    "close_agent",
    "multi_agent_v1",
    "send_input",
    "spawn_agent",
    "wait",
}


type JsonObject = dict[str, object]


def _empty_requests() -> list[JsonObject]:
    return []


@dataclass
class StubState:
    """Mutable request/response state for one deterministic native-loop run."""

    canary_paths: dict[str, Path]
    requests: list[JsonObject] = field(default_factory=_empty_requests)
    response_count: int = 0


_stub_state: StubState | None = None


def _json_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return cast(JsonObject, value)


def _tool_name(tool: object) -> str | None:
    if not isinstance(tool, dict):
        return None
    mapping = cast(dict[str, object], tool)
    direct = mapping.get("name")
    if isinstance(direct, str):
        return direct
    function = mapping.get("function")
    if isinstance(function, dict):
        nested = cast(dict[str, object], function).get("name")
        if isinstance(nested, str):
            return nested
    return None


def _tool_names(request: JsonObject) -> list[str]:
    tools = request.get("tools")
    if not isinstance(tools, list):
        return []
    tool_values = cast(list[object], tools)
    return sorted(
        name for tool in tool_values if (name := _tool_name(tool)) is not None
    )


def _sse(events: list[JsonObject]) -> bytes:
    chunks: list[str] = []
    for event in events:
        kind = event["type"]
        chunks.append(f"event: {kind}\n")
        chunks.append(f"data: {json.dumps(event, separators=(',', ':'))}\n\n")
    return "".join(chunks).encode("utf-8")


def _created(response_id: str) -> JsonObject:
    return {"type": "response.created", "response": {"id": response_id}}


def _completed(response_id: str) -> JsonObject:
    return {
        "type": "response.completed",
        "response": {
            "id": response_id,
            "usage": {
                "input_tokens": 0,
                "input_tokens_details": None,
                "output_tokens": 0,
                "output_tokens_details": None,
                "total_tokens": 0,
            },
        },
    }


def _function_call(
    response_id: str, call_id: str, name: str, arguments: JsonObject
) -> bytes:
    return _sse(
        [
            _created(response_id),
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": json.dumps(arguments, separators=(",", ":")),
                },
            },
            _completed(response_id),
        ]
    )


def _custom_call(response_id: str, call_id: str, name: str, payload: str) -> bytes:
    return _sse(
        [
            _created(response_id),
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "custom_tool_call",
                    "call_id": call_id,
                    "name": name,
                    "input": payload,
                },
            },
            _completed(response_id),
        ]
    )


def _assistant_completion(response_id: str) -> bytes:
    return _sse(
        [
            _created(response_id),
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "id": f"message-{response_id}",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Local deterministic probe complete.",
                        }
                    ],
                },
            },
            _completed(response_id),
        ]
    )


def _shell_arguments(tool_name: str, command: str) -> JsonObject:
    if tool_name == "exec_command":
        return {"cmd": command, "yield_time_ms": 10_000, "max_output_tokens": 4_000}
    return {"command": command}


def _preferred_shell_tool(names: list[str]) -> str:
    for candidate in ("exec_command", "shell_command"):
        if candidate in names:
            return candidate
    raise RuntimeError(f"Codex did not advertise a supported shell tool: {names}")


def _workspace_probe_command() -> str:
    return (
        "set -eu; "
        'test "$(cat input.txt)" = "NATIVE_INPUT"; '
        "grep -n '^NATIVE_INPUT$' input.txt > search.txt; "
        "printf 'NATIVE_WRITE_OK\\n' > created.txt"
    )


def _edit_patch() -> str:
    return """*** Begin Patch
*** Update File: input.txt
@@
-NATIVE_INPUT
+NATIVE_EDITED
*** Add File: deliverable.txt
+FINAL NATIVE_BOUNDARY_OK
*** End Patch"""


def _edit_shell_command() -> str:
    return (
        "set -eu; "
        "printf 'NATIVE_EDITED\\n' > input.txt; "
        "printf 'FINAL NATIVE_BOUNDARY_OK\\n' > deliverable.txt"
    )


def _canary_command(paths: dict[str, Path]) -> str:
    quoted = {name: str(path) for name, path in paths.items()}
    return (
        "set -eu; "
        'test "$(cat input.txt)" = "NATIVE_EDITED"; '
        'test "$(cat deliverable.txt)" = "FINAL NATIVE_BOUNDARY_OK"; '
        f"if cat '{quoted['host_home']}' >/dev/null 2>&1; then echo visible; "
        "else echo denied; fi > canary_host_home.status; "
        f"if cat '{quoted['host_auth']}' >/dev/null 2>&1; then echo visible; "
        "else echo denied; fi > canary_host_auth.status; "
        f"if cat '{quoted['host_repository']}' >/dev/null 2>&1; then echo visible; "
        "else echo denied; fi > canary_host_repository.status; "
        f"if cat '{quoted['evaluator_private']}' >/dev/null 2>&1; then echo visible; "
        "else echo denied; fi > canary_evaluator_private.status; "
        "if env | grep -E 'OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|"
        f"{CREDENTIAL_CANARY}' >/dev/null 2>&1; then echo inherited; "
        "else echo absent; fi > canary_credential.status; "
        "env | cut -d= -f1 | sort > child_environment_names.txt; "
        "if curl --max-time 2 --silent --fail --output /dev/null "
        "https://example.com; then echo reachable; else echo denied; "
        "fi > canary_network.status; "
        "sleep 60 >/dev/null 2>&1 & echo $! > child.pid"
    )


def _response_for(request: JsonObject, response_index: int, state: StubState) -> bytes:
    names = _tool_names(request)
    shell_tool = _preferred_shell_tool(names)
    response_id = f"local-{response_index + 1}"
    if response_index == 0:
        return _function_call(
            response_id,
            "call-workspace",
            shell_tool,
            _shell_arguments(shell_tool, _workspace_probe_command()),
        )
    if response_index == 1:
        if "apply_patch" in names:
            return _custom_call(response_id, "call-edit", "apply_patch", _edit_patch())
        return _function_call(
            response_id,
            "call-edit",
            shell_tool,
            _shell_arguments(shell_tool, _edit_shell_command()),
        )
    if response_index == 2:
        return _function_call(
            response_id,
            "call-canaries",
            shell_tool,
            _shell_arguments(shell_tool, _canary_command(state.canary_paths)),
        )
    return _assistant_completion(response_id)


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        body = json.dumps(
            {"object": "list", "data": [{"id": "gpt-5.1", "object": "model"}]}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        global _stub_state
        state = _stub_state
        if state is None:
            self.send_error(500, "stub state unavailable")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw_request: object = json.loads(self.rfile.read(length))
        request = _json_object(raw_request)
        state.requests.append(request)
        response_index = state.response_count
        state.response_count += 1
        try:
            body = _response_for(request, response_index, state)
        except RuntimeError as exc:
            self.send_error(500, str(exc))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


@dataclass(frozen=True)
class AttemptResult:
    """Sanitized result from one real Codex local-stub invocation."""

    returncode: int
    stdout: str
    stderr: str
    requests: list[JsonObject]
    workspace: Path
    child_probe_started: bool
    child_alive_after_codex_exit: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    argv: list[str], *, env: dict[str, str], cwd: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _clean_control_env(home: Path, codex_home: Path, path: str) -> dict[str, str]:
    return {
        "ANTHROPIC_API_KEY": CREDENTIAL_CANARY,
        "AWS_SECRET_ACCESS_KEY": CREDENTIAL_CANARY,
        "CODEX_HOME": str(codex_home),
        "HOME": str(home),
        "OPENAI_API_KEY": CREDENTIAL_CANARY,
        "PATH": path,
    }


def _feature_overrides() -> list[str]:
    result: list[str] = []
    for feature in FEATURE_DISABLE_KEYS:
        result.extend(["-c", f"features.{feature}=false"])
    result.extend(["-c", "features.multi_agent=true"])
    return result


def _codex_argv(
    codex_binary: Path,
    workspace: Path,
    home: Path,
    port: int,
    sandbox: str,
) -> list[str]:
    provider = (
        'model_providers.lfb_stub={name="lfb-loopback-stub",'
        f'base_url="http://127.0.0.1:{port}/v1",wire_api="responses",'
        "requires_openai_auth=false,supports_websockets=false,"
        "request_max_retries=0,stream_max_retries=0}"
    )
    return [
        str(codex_binary),
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--skip-git-repo-check",
        "--sandbox",
        sandbox,
        "--model",
        "gpt-5.1",
        "-C",
        str(workspace),
        "-c",
        provider,
        "-c",
        'model_provider="lfb_stub"',
        "-c",
        'web_search="disabled"',
        "-c",
        'shell_environment_policy.inherit="none"',
        "-c",
        (f'shell_environment_policy.set={{PATH="/usr/bin:/bin",HOME="{home}"}}'),
        *_feature_overrides(),
        (
            "Run the deterministic local capability probe exactly as scripted by "
            "the loopback fixture. Do not add or substitute tools."
        ),
    ]


def _prepare_workspace(root: Path, name: str) -> Path:
    workspace = root / name / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "home").mkdir()
    (workspace / "input.txt").write_text("NATIVE_INPUT\n", encoding="utf-8")
    return workspace


def _child_probe_result(workspace: Path) -> tuple[bool, bool]:
    pid_path = workspace / "child.pid"
    if not pid_path.is_file():
        return False, False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return True, False
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass  # The probe cleanup is best-effort after the child-state check.
    return True, True


def _run_attempt(
    *,
    codex_binary: Path,
    root: Path,
    clean_home: Path,
    codex_home: Path,
    canary_paths: dict[str, Path],
    sandbox: str,
    path: str,
) -> AttemptResult:
    global _stub_state
    workspace = _prepare_workspace(root, sandbox)
    state = StubState(canary_paths=canary_paths)
    _stub_state = state
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    address = cast(tuple[str, int], server.server_address)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run(
            _codex_argv(
                codex_binary, workspace, workspace / "home", address[1], sandbox
            ),
            env=_clean_control_env(clean_home, codex_home, path),
            cwd=workspace,
            timeout=45,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        _stub_state = None
    child_probe_started, child_alive = _child_probe_result(workspace)
    return AttemptResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        requests=state.requests,
        workspace=workspace,
        child_probe_started=child_probe_started,
        child_alive_after_codex_exit=child_alive,
    )


def _write_ambient_canaries(root: Path) -> dict[str, Path]:
    ambient_home = root / "ambient-home"
    ambient_codex = ambient_home / ".codex"
    ambient_codex.mkdir(parents=True)
    (ambient_codex / "config.toml").write_text(
        (
            f"# {AMBIENT_MARKERS['config']}\n"
            "[mcp_servers.ambient]\n"
            'command = "ambient-mcp-must-not-run"\n'
            f"# {AMBIENT_MARKERS['mcp']}\n"
        ),
        encoding="utf-8",
    )
    skill_dir = ambient_codex / "skills" / "ambient"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"# {AMBIENT_MARKERS['skills']}\n", encoding="utf-8"
    )
    rules_dir = ambient_codex / "rules"
    rules_dir.mkdir()
    (rules_dir / "default.rules").write_text(
        f"# {AMBIENT_MARKERS['rules']}\n", encoding="utf-8"
    )
    ambient_repo = root / "ambient-repository"
    ambient_repo.mkdir()
    (ambient_repo / "AGENTS.md").write_text(
        f"# {AMBIENT_MARKERS['project_instructions']}\n", encoding="utf-8"
    )

    host_home = root / "host-home-private.txt"
    host_auth = root / "host-auth.json"
    host_repository = root / "host-repository-private.txt"
    evaluator_private = root / "evaluator-private.txt"
    host_home.write_text("HOST_HOME_PRIVATE_CANARY\n", encoding="utf-8")
    host_auth.write_text('{"token":"HOST_AUTH_CANARY"}\n', encoding="utf-8")
    host_repository.write_text("HOST_REPOSITORY_PRIVATE_CANARY\n", encoding="utf-8")
    evaluator_private.write_text("EVALUATOR_PRIVATE_CANARY\n", encoding="utf-8")
    return {
        "evaluator_private": evaluator_private,
        "host_auth": host_auth,
        "host_home": host_home,
        "host_repository": host_repository,
    }


def _parse_capability_inventory(
    help_text: str,
    exec_help: str,
    features: str,
) -> JsonObject:
    subcommands: list[str] = []
    in_commands = False
    for line in help_text.splitlines():
        if line == "Commands:":
            in_commands = True
            continue
        if in_commands and not line.strip():
            break
        if in_commands and line.startswith("  ") and not line.startswith("    "):
            subcommands.append(line.strip().split(maxsplit=1)[0])

    exec_flags = sorted(
        {
            token.rstrip(",")
            for line in exec_help.splitlines()
            for token in line.strip().split()
            if token.startswith("--")
        }
    )
    feature_rows: list[JsonObject] = []
    for line in features.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[-1] not in {"false", "true"}:
            continue
        feature_rows.append(
            {
                "enabled_by_default": parts[-1] == "true",
                "name": parts[0],
                "stage": " ".join(parts[1:-1]),
            }
        )
    return {
        "exec_flags": exec_flags,
        "feature_flags": feature_rows,
        "subcommands": subcommands,
    }


def _read_status(workspace: Path, name: str, expected: str) -> bool:
    path = workspace / name
    return path.is_file() and path.read_text(encoding="utf-8").strip() == expected


def _ambient_canaries(requests: list[JsonObject]) -> dict[str, bool]:
    serialized = json.dumps(requests, sort_keys=True)
    return {
        f"ambient_{name}_loaded": marker in serialized
        for name, marker in AMBIENT_MARKERS.items()
    }


def _sanitize_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    relevant = [line for line in lines if "bwrap:" in line or "Error:" in line]
    chosen = relevant[-1] if relevant else (lines[-1] if lines else "no stderr")
    return chosen.replace(str(Path(tempfile.gettempdir())), "/tmp")


def _native_sandbox_preflight(
    codex_binary: Path, clean_home: Path, codex_home: Path, path: str
) -> subprocess.CompletedProcess[str]:
    return _run(
        [str(codex_binary), "sandbox", "/usr/bin/true"],
        env=_clean_control_env(clean_home, codex_home, path),
        cwd=clean_home,
        timeout=15,
    )


def systemd_preflight_is_effective(preflight: Mapping[str, object]) -> bool:
    return (
        preflight.get("command_exit_code") == 0
        and preflight.get("service_exit_status") == "0/SUCCESS"
        and preflight.get("mount_namespace_effective") is True
        and preflight.get("network_namespace_different_from_host") is True
        and preflight.get("fallback_warnings") == []
    )


def normalize_systemd_preflight(
    *,
    command_exit_code: int,
    command_output: str,
    journal_output: str | None,
    host_network_namespace: str,
) -> JsonObject:
    """Reduce volatile systemd diagnostics to a stable, fail-closed receipt."""
    if command_exit_code != 0:
        return {
            "command_exit_code": command_exit_code,
            "service_exit_status": (
                "226/NAMESPACE"
                if command_exit_code == 226
                else f"{command_exit_code}/NONZERO"
            ),
            "failure_class": (
                "namespace-setup-failed"
                if command_exit_code == 226
                else "systemd-preflight-failed"
            ),
            "mount_namespace_effective": False,
            "network_namespace_different_from_host": False,
            "fallback_warnings": ["nonzero systemd boundary preflight"],
        }

    if journal_output is None:
        return {
            "command_exit_code": command_exit_code,
            "service_exit_status": "0/SUCCESS",
            "failure_class": "journal-evidence-unavailable",
            "mount_namespace_effective": False,
            "network_namespace_different_from_host": False,
            "fallback_warnings": ["systemd journal evidence unavailable"],
        }

    evidence_text = "\n".join((command_output, journal_output))
    fallback_markers = (
        "proceeding without",
        "Failed to set up mount namespacing",
        "Operation not supported",
    )
    if any(marker in evidence_text for marker in fallback_markers):
        return {
            "command_exit_code": command_exit_code,
            "service_exit_status": "0/SUCCESS",
            "failure_class": "journal-reported-namespace-fallback",
            "mount_namespace_effective": False,
            "network_namespace_different_from_host": False,
            "fallback_warnings": ["journal reported namespace fallback"],
        }

    inner_namespaces = re.findall(r"net:\[\d+\]", command_output)
    if not inner_namespaces:
        return {
            "command_exit_code": command_exit_code,
            "service_exit_status": "0/SUCCESS",
            "failure_class": "network-namespace-evidence-unavailable",
            "mount_namespace_effective": True,
            "network_namespace_different_from_host": False,
            "fallback_warnings": ["network namespace evidence unavailable"],
        }

    network_namespace_different = inner_namespaces[-1] != host_network_namespace
    return {
        "command_exit_code": command_exit_code,
        "service_exit_status": "0/SUCCESS",
        "failure_class": (
            "none" if network_namespace_different else "host-network-namespace-reused"
        ),
        "mount_namespace_effective": True,
        "network_namespace_different_from_host": network_namespace_different,
        "fallback_warnings": (
            [] if network_namespace_different else ["host network namespace reused"]
        ),
    }


def _systemd_outer_boundary_preflight(root: Path, path: str) -> JsonObject:
    root_directory = root / "systemd-root"
    for relative in (
        "bin",
        "home",
        "lib",
        "lib64",
        "proc",
        "tmp",
        "usr",
        "workspace",
    ):
        (root_directory / relative).mkdir(parents=True, exist_ok=True)

    systemd_run = shutil.which("systemd-run")
    journalctl = shutil.which("journalctl")
    if systemd_run is None or journalctl is None:
        return {
            "available": False,
            "command_exit_code": None,
            "service_exit_status": "not-run",
            "failure_class": "systemd-tools-unavailable",
            "mount_namespace_effective": False,
            "network_namespace_different_from_host": False,
            "fallback_warnings": ["systemd-run or journalctl unavailable"],
            "effective": False,
        }

    environment = {"HOME": str(Path.home()), "PATH": path}
    for name in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
        if value := os.environ.get(name):
            environment[name] = value
    unit_name = f"lfb-codex-native-{os.getpid()}"
    result = _run(
        [
            systemd_run,
            "--user",
            "--wait",
            "--pipe",
            f"--unit={unit_name}",
            f"--property=RootDirectory={root_directory}",
            "--property=PrivateNetwork=yes",
            "--property=BindReadOnlyPaths=/usr:/usr",
            "--property=BindReadOnlyPaths=/bin:/bin",
            "--property=BindReadOnlyPaths=/lib:/lib",
            "--property=BindReadOnlyPaths=/lib64:/lib64",
            "/usr/bin/readlink",
            "/proc/self/ns/net",
        ],
        env=environment,
        cwd=root,
        timeout=20,
    )
    combined = "\n".join((result.stdout, result.stderr))
    journal: str | None = None
    if result.returncode == 0:
        journal_result = _run(
            [
                journalctl,
                "--user",
                "--unit",
                unit_name,
                "--output=cat",
                "--no-pager",
                "--lines=30",
            ],
            env=environment,
            cwd=root,
            timeout=10,
        )
        if journal_result.returncode == 0:
            journal = "\n".join((journal_result.stdout, journal_result.stderr))

    normalized = normalize_systemd_preflight(
        command_exit_code=result.returncode,
        command_output=combined,
        journal_output=journal,
        host_network_namespace=os.readlink("/proc/self/ns/net"),
    )
    preflight: JsonObject = {
        "available": True,
        **normalized,
        "requested_properties": [
            "BindReadOnlyPaths=/usr,/bin,/lib,/lib64",
            "PrivateNetwork=yes",
            "RootDirectory=disposable",
        ],
    }
    preflight["effective"] = systemd_preflight_is_effective(preflight)

    systemctl = shutil.which("systemctl")
    if systemctl is not None:
        _run(
            [systemctl, "--user", "reset-failed", unit_name],
            env=environment,
            cwd=root,
            timeout=10,
        )
    return preflight


def containment_blocking_gaps(
    *,
    native_sandbox_active: bool,
    whole_process_boundary_applied: bool,
    host_filesystem_isolated: bool,
    external_network_isolated: bool,
    credential_child_inherited: bool,
    foreign_mcp_tool_names: list[str],
    ambient_surface_loaded: bool,
) -> list[str]:
    """Return every condition that forbids the clean-native claim."""
    gaps: list[str] = []
    if not native_sandbox_active:
        gaps.append("native workspace-write sandbox unavailable")
    if not whole_process_boundary_applied or not host_filesystem_isolated:
        gaps.append("no enforced whole-process filesystem boundary")
    if not whole_process_boundary_applied or not external_network_isolated:
        gaps.append("no enforced whole-process network boundary")
    if credential_child_inherited:
        gaps.append("credential canary inherited by child command")
    if foreign_mcp_tool_names:
        gaps.append("foreign MCP tool present in primary loop")
    if ambient_surface_loaded:
        gaps.append("ambient configuration surface entered model context")
    return gaps


def build_evidence(codex_binary: Path, expected_sha256: str, path: str) -> JsonObject:
    resolved = codex_binary.resolve(strict=True)
    observed_sha256 = _sha256(resolved)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"Codex hash drift: expected {expected_sha256}, observed {observed_sha256}"
        )
    codex_binary = resolved
    version_result = _run(
        [str(codex_binary), "--version"],
        env={"PATH": path},
        cwd=Path.cwd(),
    )
    version = version_result.stdout.strip()
    if version != EXPECTED_VERSION:
        raise RuntimeError(
            f"Codex version drift: expected {EXPECTED_VERSION!r}, observed {version!r}"
        )

    with tempfile.TemporaryDirectory(prefix="lfb-codex-native-") as directory:
        root = Path(directory)
        clean_home = root / "clean-home"
        codex_home = root / "clean-codex-home"
        clean_home.mkdir()
        codex_home.mkdir()
        canary_paths = _write_ambient_canaries(root)
        control_env = _clean_control_env(clean_home, codex_home, path)

        help_result = _run(
            [str(codex_binary), "--help"], env=control_env, cwd=clean_home
        )
        exec_help_result = _run(
            [str(codex_binary), "exec", "--help"],
            env=control_env,
            cwd=clean_home,
        )
        features_result = _run(
            [str(codex_binary), "features", "list"],
            env=control_env,
            cwd=clean_home,
        )
        mcp_result = _run(
            [str(codex_binary), "mcp", "list", "--json"],
            env=control_env,
            cwd=clean_home,
        )
        if any(
            result.returncode != 0
            for result in (
                help_result,
                exec_help_result,
                features_result,
                mcp_result,
            )
        ):
            raise RuntimeError("credential-free Codex capability/config probe failed")
        if json.loads(mcp_result.stdout) != []:
            raise RuntimeError("isolated CODEX_HOME unexpectedly loaded an MCP server")

        sandbox_preflight = _native_sandbox_preflight(
            codex_binary, clean_home, codex_home, path
        )
        systemd_preflight = _systemd_outer_boundary_preflight(root, path)
        candidate = _run_attempt(
            codex_binary=codex_binary,
            root=root,
            clean_home=clean_home,
            codex_home=codex_home,
            canary_paths=canary_paths,
            sandbox="workspace-write",
            path=path,
        )
        candidate_deliverable = candidate.workspace / "deliverable.txt"
        candidate_succeeded = (
            sandbox_preflight.returncode == 0
            and candidate.returncode == 0
            and candidate_deliverable.is_file()
            and candidate_deliverable.read_text(encoding="utf-8") == DELIVERABLE_CONTENT
        )

        if candidate_succeeded:
            diagnostic = candidate
            effective_profile = "codex-cli-clean-native-candidate"
        else:
            diagnostic = _run_attempt(
                codex_binary=codex_binary,
                root=root,
                clean_home=clean_home,
                codex_home=codex_home,
                canary_paths=canary_paths,
                sandbox="danger-full-access",
                path=path,
            )
            effective_profile = "codex-cli-local-stub-native-loop-only"

        if diagnostic.returncode != 0 or len(diagnostic.requests) < 4:
            raise RuntimeError(
                "Codex diagnostic native loop did not complete against the local stub: "
                f"exit={diagnostic.returncode}, requests={len(diagnostic.requests)}, "
                f"stderr={_sanitize_error(diagnostic.stderr)}"
            )
        if not diagnostic.child_probe_started:
            raise RuntimeError("native diagnostic process-cleanup canary did not start")
        first_request = diagnostic.requests[0]
        advertised_names = _tool_names(first_request)
        shell_tool = _preferred_shell_tool(advertised_names)
        edit_tool = "apply_patch" if "apply_patch" in advertised_names else shell_tool
        delegation = sorted(DELEGATION_TOOL_NAMES & set(advertised_names))
        foreign_mcp = sorted(
            name
            for name in advertised_names
            if name.startswith("mcp__") or name.startswith("mcp_")
        )

        workspace = diagnostic.workspace
        deliverable_path = workspace / "deliverable.txt"
        deliverable = (
            deliverable_path.read_text(encoding="utf-8")
            if deliverable_path.is_file()
            else ""
        )
        tool_probes = {
            "edit": (workspace / "input.txt").read_text(encoding="utf-8")
            == "NATIVE_EDITED\n",
            "filesystem_read": (workspace / "search.txt").is_file(),
            "filesystem_write": _read_status(
                workspace, "created.txt", "NATIVE_WRITE_OK"
            ),
            "search": _read_status(workspace, "search.txt", "1:NATIVE_INPUT"),
            "shell": len(diagnostic.requests) >= 4,
        }
        if not all(tool_probes.values()) or deliverable != DELIVERABLE_CONTENT:
            raise RuntimeError("native diagnostic tool/output probe did not complete")

        canaries: dict[str, bool] = {
            **_ambient_canaries(diagnostic.requests),
            "credential_child_inherited": _read_status(
                workspace, "canary_credential.status", "inherited"
            ),
            "evaluator_private_bytes_visible": _read_status(
                workspace, "canary_evaluator_private.status", "visible"
            ),
            "external_network_reachable": _read_status(
                workspace, "canary_network.status", "reachable"
            ),
            "host_auth_visible": _read_status(
                workspace, "canary_host_auth.status", "visible"
            ),
            "host_home_visible": _read_status(
                workspace, "canary_host_home.status", "visible"
            ),
            "host_repository_visible": _read_status(
                workspace, "canary_host_repository.status", "visible"
            ),
        }

        whole_process_boundary_applied = False
        host_filesystem_isolated = False
        external_network_isolated = False
        ambient_surface_loaded = any(
            canaries[name]
            for name in (
                "ambient_config_loaded",
                "ambient_mcp_loaded",
                "ambient_project_instructions_loaded",
                "ambient_rules_loaded",
                "ambient_skills_loaded",
            )
        )
        blocking_gaps = containment_blocking_gaps(
            native_sandbox_active=candidate_succeeded,
            whole_process_boundary_applied=whole_process_boundary_applied,
            host_filesystem_isolated=host_filesystem_isolated,
            external_network_isolated=external_network_isolated,
            credential_child_inherited=canaries["credential_child_inherited"],
            foreign_mcp_tool_names=foreign_mcp,
            ambient_surface_loaded=ambient_surface_loaded,
        )
        if diagnostic.child_alive_after_codex_exit:
            blocking_gaps.append("background descendant survived Codex exit")

        clean_native_allowed = whole_process_boundary_applied and not blocking_gaps
        status = "accepted" if clean_native_allowed else "rejected"
        if clean_native_allowed:
            effective_profile = "codex-cli-clean-native"
        if _sha256(resolved) != observed_sha256:
            raise RuntimeError("Codex executable changed while the probe was running")

        return {
            "schema_version": SCHEMA_VERSION,
            "binary": {
                "executable": resolved.name,
                "sha256": observed_sha256,
                "version": version,
            },
            "spend": {
                "benchmark_task_bytes": 0,
                "local_stub_requests": len(candidate.requests)
                + (0 if diagnostic is candidate else len(diagnostic.requests)),
                "provider_requests": 0,
            },
            "profile": {
                "candidate_profile": "codex-cli-clean-native",
                "effective_profile": effective_profile,
                "literal_out_of_box_claim_allowed": False,
                "task_mcp_servers": [],
                "foreign_mcp_primary_loop": False,
                "disabled_stock_capabilities": DISABLED_STOCK_CAPABILITIES,
                "feature_disable_keys": FEATURE_DISABLE_KEYS,
                "codex_argv": {
                    "approval_policy": "never",
                    "ephemeral": True,
                    "ignore_rules": True,
                    "ignore_user_config": True,
                    "model": "gpt-5.1",
                    "provider": "loopback deterministic Responses API stub",
                    "requested_sandbox": "workspace-write",
                    "strict_config": True,
                    "web_search": "disabled",
                },
            },
            "cli_capability_inventory": _parse_capability_inventory(
                help_result.stdout, exec_help_result.stdout, features_result.stdout
            ),
            "native_tool_inventory": {
                "advertised_tool_names": advertised_names,
                "edit_tool": edit_tool,
                "foreign_mcp_tool_names": foreign_mcp,
                "native_delegation": {
                    "status": "present" if delegation else "absent",
                    "tool_names": delegation,
                },
                "required_capabilities": sorted(tool_probes),
                "shell_tool": shell_tool,
            },
            "tool_probes": tool_probes,
            "deliverable": {
                "content": deliverable,
                "path": "/workspace/deliverable.txt",
                "sealed_sha256": hashlib.sha256(
                    deliverable.encode("utf-8")
                ).hexdigest(),
            },
            "canaries": canaries,
            "child_environment_names": (
                (workspace / "child_environment_names.txt")
                .read_text(encoding="utf-8")
                .splitlines()
            ),
            "native_sandbox": {
                "requested": "workspace-write",
                "implementation": "bubblewrap",
                "active_for_required_tool_probe": candidate_succeeded,
                "probe_exit_code": sandbox_preflight.returncode,
                "probe_error": _sanitize_error(sandbox_preflight.stderr),
                "candidate_codex_exit_code": candidate.returncode,
            },
            "outer_boundary": {
                "kind": "none-applied-to-codex-parent",
                "whole_process_boundary_applied": whole_process_boundary_applied,
                "workspace_disposable": True,
                "provider_endpoint_loopback_only": True,
                "host_filesystem_isolated": host_filesystem_isolated,
                "external_network_isolated": external_network_isolated,
                "process_cleanup_probe_started": diagnostic.child_probe_started,
                "process_cleanup_verified": not diagnostic.child_alive_after_codex_exit,
                "systemd_user_preflight": systemd_preflight,
            },
            "claim_decision": {
                "status": status,
                "clean_native_claim_allowed": clean_native_allowed,
                "effective_profile": effective_profile,
                "blocking_gaps": blocking_gaps,
                "narrow_claim": (
                    "The pinned Codex binary's native local tool loop and output "
                    "contract work against a deterministic loopback model stub with "
                    "isolated ambient configuration. This host does not establish "
                    "native or whole-process containment; child credential filtering "
                    "must also be fixed before any clean-native claim."
                ),
            },
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the zero-provider-spend Codex native-loop and containment probe. "
            "The command fails on binary drift or incomplete local tool evidence."
        )
    )
    parser.add_argument(
        "--codex-binary",
        type=Path,
        default=Path(shutil.which("codex") or "codex"),
        help="Codex executable to characterize (default: codex from PATH).",
    )
    parser.add_argument(
        "--expected-sha256",
        default=DEFAULT_EXPECTED_SHA256,
        help="Required SHA-256 for the resolved executable.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write canonical JSON evidence here; stdout is used when omitted.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    path = os.environ.get("PATH")
    if not path:
        raise SystemExit("PATH is required to locate the CLI and probe utilities")
    evidence = build_evidence(args.codex_binary, args.expected_sha256, path)
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

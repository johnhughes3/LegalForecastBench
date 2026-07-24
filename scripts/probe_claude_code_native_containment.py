#!/usr/bin/env python3
"""Probe the real Claude Code native loop without benchmark bytes or provider calls."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.server
import json
import os
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn, cast
from urllib.parse import urlsplit

EXPECTED_VERSION = "2.1.218 (Claude Code)"
EXPECTED_SHA256 = "e12071751a9336b8af1012c103358ff04ac18f9aaff4a738cff7ba5cdfaf63f2"
MODEL = "claude-sonnet-4-6"
LOCAL_API_KEY = "local-stub-no-provider-credential"
PROBE_PROMPT = "Synthetic native capability probe. No benchmark task bytes are present."
REQUIRED_TOOLS = ("Read", "Glob", "Grep", "Bash", "Write", "Edit")
DRAFT_DELIVERABLE = "DRAFT NATIVE_BOUNDARY_OK\n"
DELIVERABLE = "FINAL NATIVE_BOUNDARY_OK\n"
CANARY = "LFB_AMBIENT_CUSTOMIZATION_CANARY_7e03"
CANARY_KEYS = (
    "ambient_agents_loaded",
    "ambient_config_loaded",
    "ambient_hooks_loaded",
    "ambient_mcp_loaded",
    "ambient_project_instructions_loaded",
    "ambient_skills_loaded",
    "evaluator_private_bytes_visible",
    "external_network_reachable",
    "host_home_visible",
    "host_repository_visible",
)
BOUNDARY_ATTESTATION = Path("/opt/boundary-attestation.json")
DISABLED_STOCK_CAPABILITIES = (
    "Chrome integration",
    "WebFetch",
    "WebSearch",
    "ambient agents",
    "ambient hooks",
    "ambient MCP servers",
    "ambient project instructions",
    "ambient settings",
    "ambient skills and slash commands",
)
UNVERIFIED_SAFE_MODE_SURFACES = ("ambient plugins",)
BASH_NATIVE_SENTINEL = "BASH_NATIVE_OK"
GREP_RESULT_SENTINEL = "required.txt:BOUNDARY_PROBE_INPUT GREP_RESULT_ONLY_7D4C2A"
BASH_DNS_GUARD = (
    "if timeout 2 getent hosts example.com >/dev/null 2>&1; then exit 98; fi"
)
TOOL_RESULT_SENTINELS = {
    "Read": "BOUNDARY_PROBE_INPUT",
    "Glob": "/input/required.txt",
    "Grep": GREP_RESULT_SENTINEL,
    "Bash": BASH_NATIVE_SENTINEL,
    "Write": "File created successfully at: /workspace/deliverable.txt",
    "Edit": ("The file /workspace/deliverable.txt has been updated successfully."),
}
DELIVERABLE_STATES = {
    "Write": DRAFT_DELIVERABLE.encode(),
    "Edit": DELIVERABLE.encode(),
}
SYSTEMD_PROPERTIES = (
    "Type=exec",
    "DynamicUser=yes",
    "PrivateNetwork=yes",
    "PrivateDevices=yes",
    "PrivateIPC=yes",
    "PrivateTmp=yes",
    "NoNewPrivileges=yes",
    "ProtectSystem=strict",
    "ProtectClock=yes",
    "ProtectControlGroups=yes",
    "ProtectHostname=yes",
    "ProtectKernelLogs=yes",
    "ProtectKernelModules=yes",
    "ProtectKernelTunables=yes",
    "ProtectProc=invisible",
    "ProcSubset=pid",
    "RestrictNamespaces=yes",
    "RestrictRealtime=yes",
    "LockPersonality=yes",
    "RemoveIPC=yes",
    "UMask=0077",
    "CapabilityBoundingSet=",
    "AmbientCapabilities=",
    "RuntimeMaxSec=120s",
    "TasksMax=64",
    "MemoryMax=1G",
    "KillMode=control-group",
    "TimeoutStopSec=10s",
    "ReadWritePaths=/home/claude /workspace",
    "BindReadOnlyPaths=/bin /lib /lib64 /usr",
)
FAIL_CLOSED_CONDITIONS = (
    "binary hash drift",
    "missing required native tool",
    "outer boundary unavailable",
    "provider endpoint not local",
    "unexpected task MCP server",
    "unsupported Claude stream event or content-block schema",
)


class ProbeError(RuntimeError):
    """Raised when evidence cannot satisfy the fail-closed probe contract."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pinned Claude Code binary against a loopback-only fake provider "
            "inside a disposable systemd RootDirectory boundary. Must run as root; "
            "use the repository's documented sudo-gate command."
        )
    )
    parser.add_argument(
        "--claude-binary",
        type=Path,
        default=Path("/work/.local/share/claude/versions/2.1.218"),
        help="pinned Claude Code executable to copy into the disposable root",
    )
    parser.add_argument(
        "--expected-sha256",
        default=EXPECTED_SHA256,
        help="required executable SHA-256; drift fails before launch",
    )
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--self-test-positive-canary",
        choices=CANARY_KEYS,
        help=argparse.SUPPRESS,
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_probe_source(path: Path, expected_sha256: str) -> str:
    observed_sha256 = _sha256(path.resolve(strict=True))
    if observed_sha256 != expected_sha256:
        _fail(
            "probe source hash drift: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    return observed_sha256


def _fail(message: str) -> NoReturn:
    raise ProbeError(message)


def _require_clear_canaries(canaries: Mapping[str, bool]) -> None:
    missing = sorted(set(CANARY_KEYS) - set(canaries))
    if missing:
        _fail(f"containment canary result missing: {', '.join(missing)}")
    unexpected = sorted(set(canaries) - set(CANARY_KEYS))
    if unexpected:
        _fail(f"unsupported containment canary result: {', '.join(unexpected)}")
    failed = sorted(name for name in CANARY_KEYS if canaries[name])
    if failed:
        _fail(f"containment canary failed: {', '.join(failed)}")


def _require_hidden_evaluator_private_path(path_value: str) -> None:
    path = Path(path_value)
    if not path.is_absolute():
        _fail("outer-boundary evaluator-private host path is not absolute")
    if path.exists():
        _fail("evaluator-private host path is visible inside the outer boundary")


def _disabled_surface_tools(tool_names: Sequence[str]) -> list[str]:
    return sorted(
        name
        for name in tool_names
        if name in {"WebFetch", "WebSearch"} or "chrome" in name.casefold()
    )


def _require_disabled_tools_absent(tool_names: Sequence[str]) -> None:
    violations = _disabled_surface_tools(tool_names)
    if violations:
        _fail(f"disabled tool surface advertised: {', '.join(violations)}")


def _advertised_tool_names(body: Mapping[str, Any]) -> list[str]:
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        _fail("Claude request omitted the native tool inventory")
    names: list[str] = []
    for raw_item in cast(list[object], tools):
        if not isinstance(raw_item, dict):
            _fail("Claude request contains a malformed native tool entry")
        item = cast(dict[str, object], raw_item)
        name = item.get("name")
        if not isinstance(name, str) or not name:
            _fail("Claude request contains an unnamed native tool")
        names.append(name)
    if len(set(names)) != len(names):
        _fail("Claude request contains duplicate native tool names")
    return names


def stable_evidence_projection(evidence: Mapping[str, Any]) -> dict[str, Any]:
    try:
        projected_raw = json.loads(json.dumps(evidence))
    except (TypeError, ValueError) as exc:
        raise ProbeError("containment evidence is not JSON-serializable") from exc
    if not isinstance(projected_raw, dict):
        _fail("containment evidence is not a JSON object")
    projected = cast(dict[str, Any], projected_raw)
    outer_boundary = projected.get("outer_boundary")
    if not isinstance(outer_boundary, dict):
        _fail("containment evidence omitted outer_boundary")
    network_namespace = cast(dict[str, Any], outer_boundary).get("network_namespace")
    if not isinstance(network_namespace, dict):
        _fail("containment evidence omitted network_namespace")
    typed_namespace = cast(dict[str, Any], network_namespace)
    namespace_values: dict[str, str] = {}
    for key in ("host", "inner"):
        value = typed_namespace.get(key)
        if not isinstance(value, str) or re.fullmatch(r"net:\[\d+\]", value) is None:
            _fail(f"containment evidence omitted network namespace {key}")
        namespace_values[key] = value
        typed_namespace[key] = "<runtime-network-namespace>"
    if namespace_values["host"] == namespace_values["inner"]:
        _fail("containment evidence network namespaces are not distinct")

    typed_boundary = cast(dict[str, Any], outer_boundary)
    runtime = typed_boundary.get("observed_runtime")
    if not isinstance(runtime, dict):
        _fail("containment evidence omitted observed_runtime")
    typed_runtime = cast(dict[str, Any], runtime)
    identity = typed_runtime.get("process_identity")
    if not isinstance(identity, dict):
        _fail("containment evidence omitted process_identity")
    typed_identity = cast(dict[str, Any], identity)
    external = typed_runtime.get("external_process")
    if not isinstance(external, dict):
        _fail("containment evidence omitted external_process")
    attested = cast(dict[str, Any], external).get("attested")
    if not isinstance(attested, dict):
        _fail("containment evidence omitted external process attestation")
    typed_attested = cast(dict[str, Any], attested)
    host_ids: dict[str, int] = {}
    for key in ("host_uid", "host_gid"):
        value = typed_attested.get(key)
        if type(value) is not int or value <= 0:
            _fail(f"containment evidence has invalid external process {key}")
        host_ids[key] = value
    for key in ("uids", "gids"):
        values = typed_identity.get(key)
        if not isinstance(values, list):
            _fail(f"containment evidence omitted dynamic {key}")
        typed_values = cast(list[object], values)
        if len(typed_values) != 4:
            _fail(f"containment evidence omitted dynamic {key}")
        if not all(type(value) is int and value > 0 for value in typed_values):
            _fail(f"containment evidence has invalid dynamic {key}")
        if len(set(typed_values)) != 1:
            _fail(f"containment evidence has nonuniform dynamic {key}")
        host_key = "host_uid" if key == "uids" else "host_gid"
        if host_ids[host_key] in typed_values:
            _fail("containment evidence retained the host user identity")
        typed_identity[key] = ["<runtime-dynamic-id>"] * 4

    service_cgroup = typed_runtime.get("service_cgroup")
    if (
        not isinstance(service_cgroup, str)
        or re.fullmatch(
            r"/system\.slice/lfb-claude-native-probe-[0-9a-f]{12}\.service",
            service_cgroup,
        )
        is None
    ):
        _fail("containment evidence omitted service cgroup")
    typed_runtime["service_cgroup"] = "<runtime-service-cgroup>"
    external_pid = typed_attested.get("pid")
    external_cwd = typed_attested.get("cwd")
    sentinel_path = typed_attested.get("sentinel_file_path")
    sentinel_inode = typed_attested.get("sentinel_file_inode")
    sentinel_fd = typed_attested.get("sentinel_fd")
    token_hash = typed_attested.get("environment_token_sha256")
    if type(external_pid) is not int or external_pid <= 0:
        _fail("containment evidence has invalid external process pid")
    if (
        not isinstance(external_cwd, str)
        or re.fullmatch(
            r"/tmp/lfb-johnhughes-process-canary-[a-z0-9_]{8}/canary",
            external_cwd,
        )
        is None
    ):
        _fail("containment evidence has invalid external process cwd")
    if sentinel_path != f"{external_cwd}/sentinel":
        _fail("containment evidence external sentinel path does not match cwd")
    if type(sentinel_inode) is not int or sentinel_inode <= 0:
        _fail("containment evidence has invalid external sentinel inode")
    if type(sentinel_fd) is not int or sentinel_fd < 0:
        _fail("containment evidence has invalid external sentinel fd")
    if (
        not isinstance(token_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", token_hash) is None
    ):
        _fail("containment evidence has invalid external token hash")
    volatile_external = {
        "pid": "<runtime-external-pid>",
        "cwd": "<runtime-external-path>",
        "sentinel_file_path": "<runtime-external-path>",
        "sentinel_file_inode": "<runtime-external-inode>",
        "sentinel_fd": "<runtime-external-fd>",
        "environment_token_sha256": "<runtime-external-token>",
    }
    for key, placeholder in volatile_external.items():
        if key not in typed_attested:
            _fail(f"containment evidence omitted external process {key}")
        typed_attested[key] = placeholder
    access = cast(dict[str, Any], external).get("access")
    if not isinstance(access, dict):
        _fail("containment evidence omitted external process access")
    typed_access = cast(dict[str, Any], access)
    for key in ("cwd", "environ", "fd", "root", "signal"):
        value = typed_access.get(key)
        if value in {"permission-denied", "not-visible"}:
            typed_access[key] = "<runtime-access-denied>"

    cleanup = typed_boundary.get("transient_unit_cleanup")
    if not isinstance(cleanup, dict):
        _fail("containment evidence omitted transient_unit_cleanup")
    typed_cleanup = cast(dict[str, Any], cleanup)
    manager_state = typed_cleanup.get("manager_state")
    if manager_state in {"inactive", "failed"}:
        typed_cleanup["manager_state"] = "<manager-confirmed-inactive>"
    load_state = typed_cleanup.get("load_state")
    if load_state in {"loaded", "masked", "not-found"}:
        typed_cleanup["load_state"] = "<manager-confirmed-load-state>"
    status_poll_count = typed_cleanup.get("status_poll_count")
    if (
        type(status_poll_count) is not int
        or status_poll_count < 1
        or status_poll_count > 5
    ):
        _fail("containment evidence has invalid cleanup status poll count")
    typed_cleanup["status_poll_count"] = "<runtime-status-polls>"
    return projected


def _outer_binary_preflight(path: Path, expected_sha256: str) -> dict[str, str]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        _fail(f"Claude binary is not an executable file: {resolved}")
    observed_hash = _sha256(resolved)
    if observed_hash != expected_sha256:
        _fail(
            "Claude binary hash drift: "
            f"expected {expected_sha256}, observed {observed_hash}"
        )
    return {"path": str(resolved), "sha256": observed_hash}


def _inner_binary_preflight(path: Path, expected_sha256: str) -> str:
    preflight = _outer_binary_preflight(path, expected_sha256)
    version = subprocess.run(
        [preflight["path"], "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin"},
    ).stdout.strip()
    if version != EXPECTED_VERSION:
        _fail(
            f"Claude version drift: expected {EXPECTED_VERSION!r}, observed {version!r}"
        )
    return version


def _write_text(path: Path, content: str, mode: int = 0o444) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def _require_exact_file_bytes(path: Path, expected: bytes, description: str) -> None:
    try:
        observed = path.read_bytes()
    except FileNotFoundError:
        _fail(f"{description} did not complete")
    if observed != expected:
        _fail(f"{description} did not produce expected bytes")


def _prepare_root(
    root: Path,
    binary: Path,
    boundary_attestation: Mapping[str, Any],
) -> None:
    for relative in (
        "bin",
        "lib",
        "lib64",
        "usr",
        "opt",
        "input",
        "workspace",
        "home/claude/.claude/agents",
        "home/claude/.claude/skills/ambient-canary",
        "tmp",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    shutil.copy2(binary, root / "opt/claude")
    (root / "opt/claude").chmod(0o555)
    shutil.copy2(Path(__file__).resolve(), root / "opt/probe.py")
    (root / "opt/probe.py").chmod(0o444)
    _write_text(
        root / BOUNDARY_ATTESTATION.relative_to("/"),
        json.dumps(boundary_attestation, sort_keys=True) + "\n",
    )

    _write_text(
        root / "input/required.txt",
        "BOUNDARY_PROBE_INPUT GREP_RESULT_ONLY_7D4C2A\n",
    )
    _write_text(root / "workspace/CLAUDE.md", f"{CANARY}_PROJECT\n")
    _write_text(
        root / "workspace/.mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "ambient-canary": {
                        "command": "/bin/sh",
                        "args": ["-c", "printf mcp > /workspace/ambient-mcp-fired"],
                    }
                }
            }
        )
        + "\n",
    )
    _write_text(
        root / "home/claude/.claude/settings.json",
        json.dumps(
            {
                "env": {"LFB_AMBIENT_SETTINGS_CANARY": f"{CANARY}_SETTINGS"},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "printf hook > /workspace/ambient-hook-fired"
                                    ),
                                }
                            ],
                        }
                    ]
                },
            }
        )
        + "\n",
    )
    _write_text(
        root / "home/claude/.claude/agents/ambient-canary.md",
        (
            "---\n"
            "name: ambient-canary\n"
            "description: Ambient agent that must be excluded by safe mode.\n"
            "---\n"
            f"{CANARY}_AGENT\n"
        ),
    )
    _write_text(
        root / "home/claude/.claude/skills/ambient-canary/SKILL.md",
        f"---\nname: ambient-canary\n---\n{CANARY}_SKILL\n",
    )

    root.chmod(0o755)
    # These broad modes exist only inside a root-owned, disposable RootDirectory.
    # They let systemd's unpredictable DynamicUser write its isolated home/workspace
    # without granting access to any persistent host path.
    for writable in (root / "workspace", root / "home/claude"):
        for path in (writable, *writable.parents):
            if path == root.parent:
                break
            path.chmod(0o755)
        writable.chmod(0o777)


def _systemd_command(
    root: Path,
    expected_sha256: str,
    boundary_nonce: str,
    unit: str,
) -> list[str]:
    command = [
        "/usr/bin/systemd-run",
        "--wait",
        "--collect",
        "--pipe",
        "--quiet",
        "--unit",
        unit,
        "--property",
        f"RootDirectory={root}",
        "--property",
        "WorkingDirectory=/workspace",
        "--property",
        "MountAPIVFS=yes",
        "--property",
        f"Environment=LFB_BOUNDARY_NONCE={boundary_nonce}",
        "--property",
        f"Environment=LFB_TRANSIENT_UNIT={unit}",
    ]
    for item in SYSTEMD_PROPERTIES:
        command.extend(("--property", item))
    command.extend(
        (
            "/usr/bin/python3",
            "/opt/probe.py",
            "--inner",
            "--claude-binary",
            "/opt/claude",
            "--expected-sha256",
            expected_sha256,
        )
    )
    return command


def _parse_unit_stdout(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    stripped = stdout.strip()
    try:
        value, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        raise ProbeError("unit stdout is not a JSON object") from exc
    if not isinstance(value, dict):
        _fail("unit stdout is not a JSON object")
    if stripped[end:].strip():
        _fail("unit stdout did not contain exactly one JSON object")
    return cast(dict[str, Any], value)


def _journal_for_unit(unit: str) -> str:
    result = subprocess.run(
        [
            "/usr/bin/journalctl",
            "--unit",
            unit,
            "--no-pager",
            "--output",
            "cat",
            "--lines",
            "200",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        _fail(f"could not inspect transient-unit journal: {result.stderr.strip()}")
    return result.stdout


def _journal_reports_namespace_fallback(journal: str) -> bool:
    lowered = journal.lower()
    return any(
        marker in lowered
        for marker in (
            "failed at step namespace",
            "failed to set up mount namespacing",
            "failed to set up network namespacing",
            "lacks the necessary privileges",
            "operation not permitted",
            "proceeding without namespacing",
            "proceeding without private network",
        )
    )


def _cleanup_transient_unit(unit: str) -> dict[str, Any]:
    def attempt(argv: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    attempt(["/usr/bin/systemctl", "stop", unit])
    attempt(
        [
            "/usr/bin/systemctl",
            "kill",
            "--kill-who=all",
            "--signal=SIGKILL",
            unit,
        ]
    )

    for poll_count in range(1, 6):
        status = attempt(
            [
                "/usr/bin/systemctl",
                "show",
                unit,
                "--property=ActiveState",
                "--property=LoadState",
            ]
        )
        if status is None:
            break
        if status.returncode != 0 or status.stderr.strip():
            break
        fields: dict[str, str] = {}
        malformed = False
        for line in status.stdout.splitlines():
            key, separator, value = line.partition("=")
            if (
                not separator
                or key not in {"ActiveState", "LoadState"}
                or not value
                or key in fields
            ):
                malformed = True
                break
            fields[key] = value
        if malformed or set(fields) != {"ActiveState", "LoadState"}:
            break
        active_state = fields["ActiveState"]
        load_state = fields["LoadState"]
        manager_confirmed = (
            active_state in {"inactive", "failed"}
            and load_state in {"loaded", "masked", "not-found"}
            and not (load_state == "not-found" and active_state != "inactive")
        )
        if manager_confirmed:
            return {
                "inactive_verified": True,
                "kill_attempted": True,
                "load_state": load_state,
                "manager_state": active_state,
                "status_poll_count": poll_count,
                "stop_attempted": True,
            }
        if active_state not in {"active", "activating", "deactivating", "reloading"}:
            break
        time.sleep(0.05)
    _fail(f"transient unit inactivity was not proven by systemd manager: {unit}")


def _read_status_fields(pid: int) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition(":")
        if separator:
            fields[name] = value.strip()
    return fields


def _create_external_canary_directory(
    user: pwd.struct_passwd,
) -> tuple[Path, Path]:
    canary_parent = Path(
        tempfile.mkdtemp(prefix="lfb-johnhughes-process-canary-", dir="/tmp")
    )
    try:
        canary_parent.chmod(0o711)
        canary_leaf = canary_parent / "canary"
        canary_leaf.mkdir(mode=0o700)
        os.chown(canary_leaf, user.pw_uid, user.pw_gid)
        return canary_parent, canary_leaf
    except Exception:
        _remove_external_canary_directory(canary_parent)
        raise


def _remove_external_canary_directory(canary_dir: Path) -> None:
    try:
        shutil.rmtree(canary_dir)
    except FileNotFoundError:
        pass


def _launch_external_process_canary() -> tuple[
    subprocess.Popen[str], dict[str, Any], Path
]:
    user = pwd.getpwnam("johnhughes")
    setpriv = Path("/usr/bin/setpriv")
    python = Path("/usr/bin/python3")
    if not setpriv.is_file() or not python.is_file():
        _fail("pinned setpriv/Python external-process canary helper is unavailable")

    canary_cleanup_dir, canary_dir = _create_external_canary_directory(user)
    sentinel = canary_dir / "sentinel"
    token = uuid.uuid4().hex
    helper = (
        "import os,sys,threading;"
        "os.chdir(sys.argv[1]);"
        "fd=os.open(sys.argv[2],os.O_CREAT|os.O_RDWR,0o600);"
        "os.write(fd,b'johnhughes external process canary\\n');"
        "threading.Event().wait()"
    )
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [
                str(setpriv),
                f"--reuid={user.pw_uid}",
                f"--regid={user.pw_gid}",
                "--clear-groups",
                str(python),
                "-c",
                helper,
                str(canary_dir),
                str(sentinel),
            ],
            env={
                "LFB_EXTERNAL_PROCESS_TOKEN": token,
                "LFB_EXTERNAL_SENTINEL_PATH": str(sentinel),
                "PATH": "/usr/bin:/bin",
            },
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _fail("external johnhughes process canary exited before attestation")
            try:
                status = _read_status_fields(process.pid)
                root_link = os.readlink(f"/proc/{process.pid}/root")
                cwd = os.readlink(f"/proc/{process.pid}/cwd")
                environ = Path(f"/proc/{process.pid}/environ").read_bytes()
                fd_targets = {
                    int(entry.name): os.readlink(entry)
                    for entry in Path(f"/proc/{process.pid}/fd").iterdir()
                }
            except (FileNotFoundError, PermissionError):
                time.sleep(0.02)
                continue
            uids = [int(value) for value in status.get("Uid", "").split()]
            gids = [int(value) for value in status.get("Gid", "").split()]
            sentinel_fds = [
                fd for fd, target in fd_targets.items() if target == str(sentinel)
            ]
            ready = (
                len(uids) == 4
                and all(value == user.pw_uid for value in uids)
                and len(gids) == 4
                and all(value == user.pw_gid for value in gids)
                and root_link == "/"
                and cwd == str(canary_dir)
                and f"LFB_EXTERNAL_PROCESS_TOKEN={token}".encode()
                in environ.split(b"\0")
                and len(sentinel_fds) == 1
            )
            if ready:
                sentinel_stat = sentinel.stat()
                return (
                    process,
                    {
                        "pid": process.pid,
                        "host_uid": user.pw_uid,
                        "host_gid": user.pw_gid,
                        "root": root_link,
                        "cwd": str(canary_dir),
                        "sentinel_file_path": str(sentinel),
                        "sentinel_file_owner_uid": sentinel_stat.st_uid,
                        "sentinel_file_inode": sentinel_stat.st_ino,
                        "sentinel_file_sha256": _sha256(sentinel),
                        "sentinel_fd": sentinel_fds[0],
                        "environment_token_sha256": hashlib.sha256(
                            token.encode()
                        ).hexdigest(),
                    },
                    canary_cleanup_dir,
                )
            time.sleep(0.02)
        _fail("external johnhughes process canary did not become ready")
    except Exception:
        if process is None:
            _remove_external_canary_directory(canary_cleanup_dir)
        else:
            _reap_external_process_canary(process, canary_cleanup_dir)
        raise


def _reap_external_process_canary(
    process: subprocess.Popen[str], canary_dir: Path
) -> None:
    reaped = False
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired as exc:
                    raise ProbeError(
                        f"external canary PID {process.pid} was not reaped; "
                        f"preserved {canary_dir}"
                    ) from exc
        else:
            process.wait(timeout=5)
        if process.poll() is None:
            _fail(
                f"external canary PID {process.pid} was not reaped; "
                f"preserved {canary_dir}"
            )
        reaped = True
    finally:
        if reaped:
            _remove_external_canary_directory(canary_dir)


def _observe_external_process_canary(pid: int) -> dict[str, Any]:
    status = _read_status_fields(pid)
    uids = [int(value) for value in status.get("Uid", "").split()]
    gids = [int(value) for value in status.get("Gid", "").split()]
    environ_entries = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    environment: dict[str, str] = {}
    for entry in environ_entries:
        if not entry:
            continue
        key, separator, value = entry.partition(b"=")
        if separator:
            environment[key.decode()] = value.decode()
    token = environment.get("LFB_EXTERNAL_PROCESS_TOKEN")
    sentinel_value = environment.get("LFB_EXTERNAL_SENTINEL_PATH")
    if token is None or sentinel_value is None:
        _fail(f"external canary PID {pid} omitted its identity environment")
    sentinel = Path(sentinel_value)
    sentinel_stat = sentinel.stat()
    fd_targets = {
        int(entry.name): os.readlink(entry)
        for entry in Path(f"/proc/{pid}/fd").iterdir()
    }
    sentinel_fds = [fd for fd, target in fd_targets.items() if target == str(sentinel)]
    if len(sentinel_fds) != 1:
        _fail(f"external canary PID {pid} sentinel fd identity drift")
    return {
        "pid": pid,
        "host_uid": uids[0] if len(set(uids)) == 1 and uids else None,
        "host_gid": gids[0] if len(set(gids)) == 1 and gids else None,
        "root": os.readlink(f"/proc/{pid}/root"),
        "cwd": os.readlink(f"/proc/{pid}/cwd"),
        "sentinel_file_path": str(sentinel),
        "sentinel_file_owner_uid": sentinel_stat.st_uid,
        "sentinel_file_inode": sentinel_stat.st_ino,
        "sentinel_file_sha256": _sha256(sentinel),
        "sentinel_fd": sentinel_fds[0],
        "environment_token_sha256": hashlib.sha256(token.encode()).hexdigest(),
    }


def _verify_external_process_canary(
    process: subprocess.Popen[str], attestation: Mapping[str, Any]
) -> dict[str, bool]:
    expected_pid = attestation.get("pid")
    if process.pid != expected_pid or process.poll() is not None:
        _fail(f"external canary PID {expected_pid} is not alive after unit run")
    try:
        observed = _observe_external_process_canary(process.pid)
    except (OSError, ValueError) as exc:
        raise ProbeError(
            f"external canary PID {process.pid} could not be reverified"
        ) from exc
    if observed != dict(attestation):
        _fail(f"external canary PID {process.pid} identity drift after unit run")
    return {
        "alive_same_process": True,
        "identity_reverified": True,
    }


def _require_sealed_root_parent(parent: Path, root: Path) -> None:
    parent_stat = parent.stat()
    if (
        parent_stat.st_uid != 0
        or stat.S_IMODE(parent_stat.st_mode) != 0o700
        or root.parent != parent
    ):
        _fail(
            "disposable RootDirectory parent is not a root-owned mode-0700 "
            "traversal barrier"
        )


def _finalize_outer_resources(
    parent: Path,
    unit: str,
    external_process: subprocess.Popen[str] | None,
    external_canary_dir: Path | None,
) -> dict[str, Any]:
    cleanup_proof: dict[str, Any] | None = None
    cleanup_error: Exception | None = None
    reap_error: Exception | None = None
    try:
        cleanup_proof = _cleanup_transient_unit(unit)
    except Exception as exc:
        cleanup_error = exc
    if external_process is not None and external_canary_dir is not None:
        try:
            _reap_external_process_canary(external_process, external_canary_dir)
        except Exception as exc:
            reap_error = exc
    if cleanup_error is not None or cleanup_proof is None:
        raise ProbeError(
            f"{cleanup_error}; preserved RootDirectory parent {parent}"
        ) from cleanup_error
    shutil.rmtree(parent)
    if reap_error is not None:
        raise reap_error
    return cleanup_proof


def _outer_probe(binary: Path, expected_sha256: str) -> dict[str, Any]:
    if os.geteuid() != 0:
        _fail(
            "the outer containment probe requires root to create the transient "
            "systemd RootDirectory boundary"
        )
    if shutil.which("systemd-run") != "/usr/bin/systemd-run":
        _fail("the pinned /usr/bin/systemd-run boundary is unavailable")
    binary_preflight = _outer_binary_preflight(binary, expected_sha256)

    parent = Path(tempfile.mkdtemp(prefix="lfb-claude-native-"))
    root = parent / "root"
    root.mkdir()
    _require_sealed_root_parent(parent, root)
    evaluator_private = parent / "evaluator-private-canary"
    evaluator_private.write_text(
        "EVALUATOR_PRIVATE_SENTINEL_NOT_FOR_SOLVER\n",
        encoding="utf-8",
    )
    evaluator_private.chmod(0o600)
    boundary_nonce = uuid.uuid4().hex
    root_stat = root.stat()
    unit = f"lfb-claude-native-probe-{uuid.uuid4().hex[:12]}.service"
    external_process: subprocess.Popen[str] | None = None
    external_canary_dir: Path | None = None
    typed: dict[str, Any]
    cleanup_proof: dict[str, Any]
    try:
        external_process, external_attestation, external_canary_dir = (
            _launch_external_process_canary()
        )
        boundary_attestation = {
            "boundary_nonce": boundary_nonce,
            "evaluator_private_path": str(evaluator_private),
            "evaluator_private_sha256": _sha256(evaluator_private),
            "external_process": external_attestation,
            "host_gid": external_attestation["host_gid"],
            "host_network_namespace": os.readlink("/proc/self/ns/net"),
            "host_uid": external_attestation["host_uid"],
            "probe_source_sha256": _sha256(Path(__file__).resolve()),
            "root_device": root_stat.st_dev,
            "root_inode": root_stat.st_ino,
            "schema_version": "legalforecast.claude_outer_boundary_attestation.v2",
            "transient_unit": unit,
        }
        _prepare_root(root, Path(binary_preflight["path"]), boundary_attestation)
        _require_sealed_root_parent(parent, root)
        result = subprocess.run(
            _systemd_command(root, expected_sha256, boundary_nonce, unit),
            check=False,
            capture_output=True,
            text=True,
            timeout=130,
        )
        post_run = _verify_external_process_canary(
            external_process, external_attestation
        )
        if result.returncode != 0:
            _fail(
                "outer boundary failed closed: "
                f"systemd-run exited {result.returncode}: {result.stderr.strip()}"
            )
        journal = _journal_for_unit(unit)
        namespace_fallback = _journal_reports_namespace_fallback(journal)
        if namespace_fallback:
            _fail("transient-unit journal reports a namespace fallback")
        typed = _parse_unit_stdout(result.stdout)
        outer_boundary = typed.get("outer_boundary")
        if not isinstance(outer_boundary, dict):
            _fail("inner evidence omitted outer_boundary")
        typed_boundary = cast(dict[str, Any], outer_boundary)
        observed_runtime = typed_boundary.get("observed_runtime")
        if not isinstance(observed_runtime, dict):
            _fail("inner evidence omitted observed_runtime")
        external_runtime = cast(dict[str, Any], observed_runtime).get(
            "external_process"
        )
        if not isinstance(external_runtime, dict):
            _fail("inner evidence omitted external process evidence")
        cast(dict[str, Any], external_runtime)["post_run"] = post_run
        typed_boundary["journal_namespace_fallback_detected"] = namespace_fallback
        typed["evaluator_private_sentinel"] = {
            "planted_outside_root": evaluator_private.is_file(),
            "exact_host_path_checked": True,
            "sha256": boundary_attestation["evaluator_private_sha256"],
            "visible_from_inner": False,
        }
    finally:
        cleanup_proof = _finalize_outer_resources(
            parent, unit, external_process, external_canary_dir
        )
    cast(dict[str, Any], typed["outer_boundary"])["transient_unit_cleanup"] = (
        cleanup_proof
    )
    return typed


def _event_stream(events: Sequence[tuple[str, Mapping[str, Any]]]) -> bytes:
    chunks: list[str] = []
    for event_name, payload in events:
        chunks.append(f"event: {event_name}\ndata: {json.dumps(payload)}\n\n")
    return "".join(chunks).encode()


def _message_start(message_id: str) -> tuple[str, dict[str, Any]]:
    return (
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": MODEL,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 1,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 0,
                },
            },
        },
    )


def _tool_response(name: str, tool_input: Mapping[str, Any], index: int) -> bytes:
    tool_id = f"toolu_local_{index:04d}"
    partial = json.dumps(tool_input, separators=(",", ":"))
    return _event_stream(
        (
            _message_start(f"msg_local_{index:04d}"),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": name,
                        "input": {},
                    },
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": partial},
                },
            ),
            (
                "content_block_stop",
                {"type": "content_block_stop", "index": 0},
            ),
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {"output_tokens": 8},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        )
    )


def _final_response(index: int) -> bytes:
    return _event_stream(
        (
            _message_start(f"msg_local_{index:04d}"),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": "NATIVE_LOOP_COMPLETE",
                    },
                },
            ),
            (
                "content_block_stop",
                {"type": "content_block_stop", "index": 0},
            ),
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 4},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        )
    )


def _tool_input(name: str) -> dict[str, Any]:
    inputs: dict[str, dict[str, Any]] = {
        "Read": {"file_path": "/input/required.txt"},
        "Glob": {"path": "/input", "pattern": "*.txt"},
        "Grep": {
            "path": "/input",
            "pattern": "BOUNDARY_PROBE_INPUT",
            "output_mode": "content",
        },
        "Bash": {
            "command": (
                "set -eu; "
                'if test -n "${LFB_AMBIENT_SETTINGS_CANARY+x}"; then '
                "printf settings > /workspace/ambient-settings-fired; exit 97; fi; "
                "test ! -e /home/johnhughes; "
                "test ! -e /work/Development; "
                "test ! -e /workspace/ambient-mcp-fired; "
                f"{BASH_DNS_GUARD}; "
                f"printf '{BASH_NATIVE_SENTINEL}\\n' > /workspace/bash-ok.txt; "
                f"printf '{BASH_NATIVE_SENTINEL}\\n'"
            )
        },
        "Write": {
            "file_path": "/workspace/deliverable.txt",
            "content": DRAFT_DELIVERABLE,
        },
        "Edit": {
            "file_path": "/workspace/deliverable.txt",
            "old_string": "DRAFT",
            "new_string": "FINAL",
        },
    }
    return inputs[name]


class _ProbeState:
    def __init__(
        self,
        *,
        deliverable_path: Path = Path("/workspace/deliverable.txt"),
    ) -> None:
        self.lock = threading.Lock()
        self.deliverable_path = deliverable_path
        self.requests: list[dict[str, Any]] = []
        self.accepted_bodies: list[dict[str, Any]] = []
        self.advertised_tools: list[str] = []
        self.tool_results: dict[str, bool] = {name: False for name in REQUIRED_TOOLS}
        self.accepted_http_calls = 0
        self.count_token_calls = 0
        self.message_round_trips = 0
        self.step = 0
        self.failure_message: str | None = None

    def _latch_failure_locked(self, error: BaseException) -> None:
        if self.failure_message is None:
            self.failure_message = str(error) or type(error).__name__

    def latch_failure(self, error: BaseException) -> None:
        with self.lock:
            self._latch_failure_locked(error)

    def _raise_if_failed_locked(self) -> None:
        if self.failure_message is not None:
            _fail(self.failure_message)

    def raise_if_failed(self) -> None:
        with self.lock:
            self._raise_if_failed_locked()

    def _observe_tool_inventory(self, body: Mapping[str, Any]) -> None:
        observed_tools = _advertised_tool_names(body)
        _require_disabled_tools_absent(observed_tools)
        if not self.advertised_tools:
            self.advertised_tools.extend(observed_tools)
            missing = sorted(set(REQUIRED_TOOLS) - set(self.advertised_tools))
            if missing:
                _fail(f"missing required native tools: {', '.join(missing)}")
        elif observed_tools != self.advertised_tools:
            _fail("Claude native tool inventory drifted between requests")

    def observe_tool_inventory(self, body: Mapping[str, Any]) -> None:
        with self.lock:
            self._raise_if_failed_locked()
            try:
                self._observe_tool_inventory(body)
            except Exception as exc:
                self._latch_failure_locked(exc)
                raise

    def accept_count_token_request(self, body: Mapping[str, Any]) -> None:
        with self.lock:
            self._raise_if_failed_locked()
            try:
                if self.step >= len(REQUIRED_TOOLS) + 1:
                    _fail("Claude sent a request after terminal local-stub response")
                self._observe_tool_inventory(body)
                accepted = dict(body)
                self.accepted_bodies.append(accepted)
                self.accepted_http_calls += 1
                self.count_token_calls += 1
            except Exception as exc:
                self._latch_failure_locked(exc)
                raise

    def next_response(self, body: dict[str, Any]) -> bytes:
        with self.lock:
            self._raise_if_failed_locked()
            try:
                if self.step >= len(REQUIRED_TOOLS) + 1:
                    _fail("Claude sent a request after terminal local-stub response")
                self._observe_tool_inventory(body)
                accepted = dict(body)
                self.requests.append(accepted)
                self.accepted_bodies.append(accepted)
                self.accepted_http_calls += 1
                self.message_round_trips += 1
                if 0 < self.step <= len(REQUIRED_TOOLS):
                    previous = REQUIRED_TOOLS[self.step - 1]
                    expected_id = f"toolu_local_{self.step:04d}"
                    successful = _has_successful_tool_result(
                        body, expected_id, previous
                    )
                    expected_state = DELIVERABLE_STATES.get(previous)
                    if successful and expected_state is not None:
                        _require_exact_file_bytes(
                            self.deliverable_path,
                            expected_state,
                            f"native {previous} immediate deliverable state",
                        )
                    self.tool_results[previous] = successful

                self.step += 1
                if self.step <= len(REQUIRED_TOOLS):
                    name = REQUIRED_TOOLS[self.step - 1]
                    return _tool_response(name, _tool_input(name), self.step)
                return _final_response(self.step)
            except Exception as exc:
                self._latch_failure_locked(exc)
                raise


def _require_no_ambient_canary(bodies: Sequence[Mapping[str, Any]]) -> None:
    if CANARY in json.dumps(list(bodies), sort_keys=True):
        _fail("ambient customization canary reached an accepted local-stub body")


def _validate_completed_probe_state(state: _ProbeState) -> None:
    state.raise_if_failed()
    expected = len(REQUIRED_TOOLS) + 1
    if state.message_round_trips != expected or state.step != expected:
        _fail(
            "Claude native loop did not complete the exact required message round trips"
        )


def _tool_result_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for raw_block in cast(list[object], content):
        if not isinstance(raw_block, dict):
            return None
        block = cast(dict[str, object], raw_block)
        if block.get("type") != "text" or not isinstance(block.get("text"), str):
            return None
        parts.append(cast(str, block["text"]))
    return "\n".join(parts) if parts else None


def _has_successful_tool_result(
    body: Mapping[str, Any], tool_use_id: str, tool_name: str
) -> bool:
    """Accept exactly one successful tool_result object for the requested tool use."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return False
    matches: list[dict[str, Any]] = []
    for raw_message in cast(list[object], messages):
        if not isinstance(raw_message, dict):
            continue
        message = cast(dict[str, object], raw_message)
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for raw_block in cast(list[object], content):
            if not isinstance(raw_block, dict):
                continue
            block = cast(dict[str, Any], raw_block)
            if (
                block.get("type") == "tool_result"
                and block.get("tool_use_id") == tool_use_id
            ):
                matches.append(block)
    if len(matches) != 1:
        return False
    match = matches[0]
    if match.get("is_error", False) is not False:
        return False
    result_text = _tool_result_text(match.get("content"))
    if result_text is None or result_text == "":
        return False
    expected = TOOL_RESULT_SENTINELS.get(tool_name)
    return expected is None or expected in result_text


def _user_text_messages(body: Mapping[str, Any]) -> list[str] | None:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return None
    texts: list[str] = []
    for raw_message in cast(list[object], messages):
        if not isinstance(raw_message, dict):
            return None
        message = cast(dict[str, object], raw_message)
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
            continue
        if not isinstance(content, list):
            return None
        for raw_block in cast(list[object], content):
            if not isinstance(raw_block, dict):
                return None
            block = cast(dict[str, object], raw_block)
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if not isinstance(text, str):
                    return None
                texts.append(text)
            elif block_type == "tool_result":
                if not isinstance(block.get("tool_use_id"), str):
                    return None
                if _tool_result_text(block.get("content")) is None:
                    return None
                if "is_error" in block and not isinstance(block["is_error"], bool):
                    return None
            else:
                _fail("unsupported user content block")
    return texts


def _validate_stub_request(
    request_path: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
) -> str:
    parsed = urlsplit(request_path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        _fail("unsupported local-stub path")
    if parsed.query not in ("", "beta=true"):
        _fail("unsupported local-stub query")
    path_kinds = {
        "/v1/messages": "messages",
        "/v1/messages/count_tokens": "count_tokens",
    }
    kind = path_kinds.get(parsed.path)
    if kind is None:
        _fail("unsupported local-stub path")

    lowered_headers = {name.lower(): value for name, value in headers.items()}
    if lowered_headers.get("x-api-key") != LOCAL_API_KEY:
        _fail("local-stub authentication marker missing or incorrect")
    if body.get("model") != MODEL:
        _fail("local-stub model drift")
    if _user_text_messages(body) != [PROBE_PROMPT]:
        _fail("local-stub synthetic prompt contract failed")
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        _fail("local-stub native tool request contract failed")
    if kind == "messages" and body.get("stream") is not True:
        _fail("local-stub streaming contract failed")
    return kind


def _handler(state: _ProbeState) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            try:
                self._handle_post()
            except Exception as exc:
                state.latch_failure(exc)
                try:
                    self._json_response(
                        {"error": {"type": "invalid_request", "message": str(exc)}},
                        status=400,
                    )
                except Exception as response_exc:
                    state.latch_failure(response_exc)

        def _handle_post(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProbeError("Claude sent malformed JSON to local stub") from exc
            if not isinstance(body, dict):
                _fail("Claude local-stub request is not a JSON object")
            typed_body = cast(dict[str, Any], body)
            headers = {name: value for name, value in self.headers.items()}
            kind = _validate_stub_request(self.path, headers, typed_body)
            if kind == "count_tokens":
                state.accept_count_token_request(typed_body)
                self._json_response({"input_tokens": 1})
                return
            payload = state.next_response(typed_body)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            del format, args
            return

        def _json_response(
            self, payload: Mapping[str, Any], *, status: int = 200
        ) -> None:
            encoded = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _claude_argv(binary: Path) -> list[str]:
    return [
        str(binary),
        "--safe-mode",
        "--no-chrome",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disallowed-tools",
        "WebFetch",
        "WebSearch",
        "--print",
        PROBE_PROMPT,
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--model",
        MODEL,
        "--dangerously-skip-permissions",
    ]


def _validate_cli_content_blocks(content: object, *, role: str) -> None:
    if not isinstance(content, list):
        _fail(f"Claude {role} content is not a block list")
    for raw_block in cast(list[object], content):
        if not isinstance(raw_block, dict):
            _fail(f"Claude {role} content block is malformed")
        block = cast(dict[str, object], raw_block)
        block_type = block.get("type")
        if role == "assistant":
            if block_type == "text" and isinstance(block.get("text"), str):
                continue
            if (
                block_type == "tool_use"
                and isinstance(block.get("id"), str)
                and isinstance(block.get("name"), str)
                and isinstance(block.get("input"), dict)
            ):
                continue
            if block_type == "thinking" and isinstance(block.get("thinking"), str):
                continue
            if block_type == "redacted_thinking" and isinstance(block.get("data"), str):
                continue
            _fail("unsupported Claude assistant content block")
        if role == "user":
            if (
                block_type == "tool_result"
                and isinstance(block.get("tool_use_id"), str)
                and _tool_result_text(block.get("content")) is not None
                and ("is_error" not in block or isinstance(block.get("is_error"), bool))
            ):
                continue
            _fail("unsupported Claude user content block")
        _fail("unsupported Claude stream message role")


def _validate_cli_events(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not events:
        _fail("Claude stream omitted all events")
    result_events = 0
    for index, event in enumerate(events):
        event_type = event.get("type")
        if event_type == "system":
            tools = event.get("tools")
            if (
                event.get("subtype") != "init"
                or not isinstance(event.get("session_id"), str)
                or not isinstance(event.get("model"), str)
                or not isinstance(event.get("claude_code_version"), str)
                or not isinstance(tools, list)
                or not all(isinstance(tool, str) for tool in cast(list[object], tools))
            ):
                _fail("malformed Claude system init event")
            continue
        if event_type in {"assistant", "user"}:
            if not isinstance(event.get("session_id"), str):
                _fail(f"malformed Claude {event_type} stream event")
            message = event.get("message")
            if not isinstance(message, dict):
                _fail(f"malformed Claude {event_type} stream message")
            typed_message = cast(dict[str, object], message)
            if typed_message.get("role") != event_type:
                _fail(f"malformed Claude {event_type} stream role")
            _validate_cli_content_blocks(
                typed_message.get("content"), role=cast(str, event_type)
            )
            continue
        if event_type == "result":
            result_events += 1
            if (
                index != len(events) - 1
                or event.get("is_error") is not False
                or not isinstance(event.get("subtype"), str)
                or not isinstance(event.get("session_id"), str)
            ):
                _fail("malformed Claude terminal result event")
            continue
        _fail("unsupported Claude stream event")
    if result_events != 1:
        _fail("Claude stream omitted the unique terminal result event")
    return events[-1]


def _external_network_reachable() -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=0.5):
            return True
    except OSError:
        return False


def _status_mapping(status: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in status.splitlines():
        name, separator, value = line.partition(":")
        if separator:
            fields[name] = value.strip()
    return fields


def _validate_process_identity(
    status: str, *, host_uid: int, host_gid: int
) -> dict[str, Any]:
    fields = _status_mapping(status)
    try:
        uids = [int(value) for value in fields["Uid"].split()]
        gids = [int(value) for value in fields["Gid"].split()]
        no_new_privileges = int(fields["NoNewPrivs"])
        capability_masks = {
            name: int(fields[name], 16)
            for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
        }
    except (KeyError, ValueError) as exc:
        raise ProbeError("process identity status is malformed") from exc
    if len(uids) != 4 or len(gids) != 4:
        _fail("process identity status omitted real/effective/saved/fs IDs")
    if len(set(uids)) != 1 or len(set(gids)) != 1:
        _fail("dynamic service UID/GID identities are not uniform")
    if any(value == 0 for value in (*uids, *gids)):
        _fail("dynamic service retained a root user/group identity")
    if host_uid in uids or host_gid in gids:
        _fail("dynamic service retained the host user identity")
    if no_new_privileges != 1:
        _fail("dynamic service did not enforce NoNewPrivs")
    if any(capability_masks.values()):
        _fail("dynamic service retained a Linux capability")
    return {
        "uids": uids,
        "gids": gids,
        "no_new_privileges": True,
        "capability_masks": capability_masks,
    }


def _validate_service_cgroup(cgroup: str, unit: str) -> str:
    unified = next(
        (
            line.split("::", 1)[1]
            for line in cgroup.splitlines()
            if line.startswith("0::")
        ),
        None,
    )
    if unified is None or unit not in Path(unified).parts:
        _fail("process is not in the attested transient service cgroup")
    return unified


def _observe_read_only_mount(path: Path, mountinfo: str) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    candidates: list[tuple[Path, set[str]]] = []
    for line in mountinfo.splitlines():
        before, separator, after = line.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        filesystem = after.split()
        if len(fields) < 6 or len(filesystem) < 3:
            continue
        mount_point = Path(fields[4].replace("\\040", " "))
        try:
            resolved.relative_to(mount_point)
        except ValueError:
            continue
        options = set(fields[5].split(",")) | set(filesystem[2].split(","))
        candidates.append((mount_point, options))
    if not candidates:
        _fail(f"no mountinfo entry covers required OS path: {path}")
    mount_point, options = max(candidates, key=lambda item: len(item[0].parts))
    statvfs_read_only = bool(os.statvfs(resolved).f_flag & os.ST_RDONLY)
    mountinfo_read_only = "ro" in options
    if not statvfs_read_only or not mountinfo_read_only:
        _fail(f"required OS path is not observably read-only: {path}")
    return {
        "mount_point": str(mount_point),
        "mountinfo_read_only": mountinfo_read_only,
        "statvfs_read_only": statvfs_read_only,
    }


def _read_proc_link(path: Path) -> str:
    return os.readlink(path)


def _read_proc_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _list_proc_fd(path: Path) -> list[str]:
    return [entry.name for entry in path.iterdir()]


def _denied_proc_access(operation: Callable[[], object]) -> str:
    try:
        operation()
    except PermissionError:
        return "permission-denied"
    except (FileNotFoundError, ProcessLookupError):
        return "not-visible"
    _fail("external host process surface was accessible inside containment")


def _probe_external_process_access(pid: int) -> dict[str, str]:
    process_root = Path(f"/proc/{pid}")
    return {
        "cwd": _denied_proc_access(lambda: _read_proc_link(process_root / "cwd")),
        "environ": _denied_proc_access(
            lambda: _read_proc_bytes(process_root / "environ")
        ),
        "fd": _denied_proc_access(lambda: _list_proc_fd(process_root / "fd")),
        "root": _denied_proc_access(lambda: _read_proc_link(process_root / "root")),
        "signal": _denied_proc_access(lambda: os.kill(pid, 0)),
    }


def _disable_process_dumpability() -> None:
    pr_set_dumpable = 4
    pr_get_dumpable = 3
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(pr_set_dumpable, 0, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if libc.prctl(pr_get_dumpable, 0, 0, 0, 0) != 0:
        _fail("trusted supervisor remained dumpable")


def _establish_same_uid_supervisor_boundary() -> dict[str, bool]:
    _disable_process_dumpability()
    supervisor_pid = os.getpid()
    stdout_fd = sys.stdout.fileno()
    child_source = """
import json
import os
import signal
import sys

pid = int(sys.argv[1])
stdout_fd = int(sys.argv[2])

def denied(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return True
    else:
        os.close(fd)
        return False

result = {
    "child_stdout_fd_denied": denied(f"/proc/{pid}/fd/{stdout_fd}"),
    "child_environ_denied": denied(f"/proc/{pid}/environ"),
    "child_mem_denied": denied(f"/proc/{pid}/mem"),
}
try:
    os.kill(pid, signal.SIGCONT)
except OSError:
    result["same_uid_signal_availability_only"] = False
else:
    result["same_uid_signal_availability_only"] = True
print(json.dumps(result, sort_keys=True))
"""
    child = subprocess.run(
        ["/usr/bin/python3", "-c", child_source, str(supervisor_pid), str(stdout_fd)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env={"PATH": "/usr/bin:/bin"},
    )
    if child.returncode != 0:
        _fail(f"same-UID supervisor negative control failed: {child.stderr.strip()}")
    try:
        observed = json.loads(child.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(
            "same-UID supervisor negative control emitted malformed evidence"
        ) from exc
    required = {
        "child_stdout_fd_denied",
        "child_environ_denied",
        "child_mem_denied",
        "same_uid_signal_availability_only",
    }
    if not isinstance(observed, dict):
        _fail("same-UID supervisor negative control evidence is malformed")
    typed = cast(dict[str, object], observed)
    if set(typed) != required:
        _fail("same-UID supervisor negative control evidence is malformed")
    if not all(typed.get(key) is True for key in required):
        _fail("same-UID child crossed the trusted supervisor process boundary")
    return {
        "child_environ_denied": True,
        "child_mem_denied": True,
        "child_stdout_fd_denied": True,
        "dumpable_disabled": True,
        "same_uid_signal_availability_only": True,
        "supervisor_survived_signal": os.getpid() == supervisor_pid,
    }


def _read_boundary_attestation() -> dict[str, Any]:
    try:
        raw = json.loads(BOUNDARY_ATTESTATION.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProbeError("missing outer-boundary attestation") from exc
    if not isinstance(raw, dict):
        _fail("outer-boundary attestation is not a JSON object")
    attestation = cast(dict[str, Any], raw)
    required = {
        "boundary_nonce",
        "evaluator_private_path",
        "evaluator_private_sha256",
        "external_process",
        "host_gid",
        "host_network_namespace",
        "host_uid",
        "probe_source_sha256",
        "root_device",
        "root_inode",
        "schema_version",
        "transient_unit",
    }
    if set(attestation) != required:
        _fail("outer-boundary attestation has an unsupported schema")
    if attestation["schema_version"] != (
        "legalforecast.claude_outer_boundary_attestation.v2"
    ):
        _fail("outer-boundary attestation version is unsupported")
    if os.environ.get("LFB_BOUNDARY_NONCE") != attestation["boundary_nonce"]:
        _fail("outer-boundary attestation nonce mismatch")
    probe_source_sha256 = attestation["probe_source_sha256"]
    if not isinstance(probe_source_sha256, str):
        _fail("outer-boundary probe source hash is invalid")
    _verify_probe_source(Path(__file__), probe_source_sha256)
    evaluator_private_path = attestation["evaluator_private_path"]
    if not isinstance(evaluator_private_path, str):
        _fail("outer-boundary evaluator-private path is invalid")
    _require_hidden_evaluator_private_path(evaluator_private_path)
    root_stat = Path("/").stat()
    if (root_stat.st_dev, root_stat.st_ino) != (
        attestation["root_device"],
        attestation["root_inode"],
    ):
        _fail("process is not running in the attested disposable RootDirectory")
    inner_network_namespace = os.readlink("/proc/self/ns/net")
    if inner_network_namespace == attestation["host_network_namespace"]:
        _fail("process did not enter a network namespace distinct from the host")
    host_uid = attestation["host_uid"]
    host_gid = attestation["host_gid"]
    transient_unit = attestation["transient_unit"]
    external_process = attestation["external_process"]
    if (
        not isinstance(host_uid, int)
        or not isinstance(host_gid, int)
        or not isinstance(transient_unit, str)
        or not transient_unit.endswith(".service")
        or not isinstance(external_process, dict)
    ):
        _fail("outer-boundary runtime attestation is malformed")
    typed_external = cast(dict[str, Any], external_process)
    if set(typed_external) != {
        "pid",
        "host_uid",
        "host_gid",
        "root",
        "cwd",
        "sentinel_file_path",
        "sentinel_file_owner_uid",
        "sentinel_file_inode",
        "sentinel_file_sha256",
        "sentinel_fd",
        "environment_token_sha256",
    }:
        _fail("outer-boundary external process attestation is malformed")
    external_pid = typed_external["pid"]
    if (
        not isinstance(external_pid, int)
        or typed_external["host_uid"] != host_uid
        or typed_external["host_gid"] != host_gid
        or typed_external["sentinel_file_owner_uid"] != host_uid
        or typed_external["root"] != "/"
        or not isinstance(typed_external["sentinel_fd"], int)
        or not isinstance(typed_external["sentinel_file_sha256"], str)
        or len(typed_external["sentinel_file_sha256"]) != 64
        or not isinstance(typed_external["environment_token_sha256"], str)
        or len(typed_external["environment_token_sha256"]) != 64
    ):
        _fail("outer-boundary external process identity is invalid")

    status = Path("/proc/self/status").read_text(encoding="utf-8")
    cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    observed_runtime = {
        "process_identity": _validate_process_identity(
            status, host_uid=host_uid, host_gid=host_gid
        ),
        "service_cgroup": _validate_service_cgroup(cgroup, transient_unit),
        "read_only_os_binds": {
            str(path): _observe_read_only_mount(Path(path), mountinfo)
            for path in ("/bin", "/lib", "/lib64", "/usr")
        },
        "external_process": {
            "attested": typed_external,
            "access": _probe_external_process_access(external_pid),
        },
    }
    attestation["inner_network_namespace"] = inner_network_namespace
    attestation["evaluator_private_path_visible"] = False
    attestation["observed_runtime"] = observed_runtime
    return attestation


def _inner_probe(binary: Path, expected_sha256: str) -> dict[str, Any]:
    attestation = _read_boundary_attestation()
    supervisor_boundary = _establish_same_uid_supervisor_boundary()
    cast(dict[str, Any], attestation["observed_runtime"])["supervisor_boundary"] = (
        supervisor_boundary
    )
    version = _inner_binary_preflight(binary, expected_sha256)
    state = _ProbeState()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    argv = _claude_argv(binary)
    environment = {
        "ANTHROPIC_API_KEY": "local-stub-no-provider-credential",
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CONFIG_DIR": "/home/claude/.claude",
        "HOME": "/home/claude",
        "LANG": "C.UTF-8",
        "NO_PROXY": "127.0.0.1,localhost",
        "PATH": "/usr/bin:/bin",
        "SHELL": "/bin/sh",
        "TMPDIR": "/tmp",
        "XDG_CACHE_HOME": "/home/claude/.cache",
        "XDG_CONFIG_HOME": "/home/claude/.config",
        "XDG_DATA_HOME": "/home/claude/.local/share",
        "XDG_STATE_HOME": "/home/claude/.local/state",
    }
    try:
        result = subprocess.run(
            argv,
            cwd="/workspace",
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    _validate_completed_probe_state(state)
    if result.returncode != 0:
        _fail(
            f"Claude native loop failed with exit {result.returncode}: "
            f"{result.stderr[-2000:]}"
        )
    if not all(state.tool_results.values()):
        failed = sorted(
            name for name, passed in state.tool_results.items() if not passed
        )
        _fail(f"native tool results failed or were absent: {', '.join(failed)}")
    deliverable = Path("/workspace/deliverable.txt")
    if deliverable.read_text(encoding="utf-8") != DELIVERABLE:
        _fail("native Write/Edit deliverable probe did not produce expected bytes")
    _require_exact_file_bytes(
        Path("/workspace/bash-ok.txt"),
        f"{BASH_NATIVE_SENTINEL}\n".encode(),
        "native Bash canary probe",
    )

    _require_no_ambient_canary(state.accepted_bodies)
    serialized_requests = json.dumps(state.accepted_bodies, sort_keys=True)
    advertised = state.advertised_tools
    subagent_name = next(
        (name for name in ("Agent", "Task") if name in advertised), None
    )
    claude_events: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProbeError(
                "Claude emitted non-JSON stdout in stream-json mode"
            ) from exc
        if not isinstance(event, dict):
            _fail("Claude emitted a non-object stream event")
        claude_events.append(cast(dict[str, Any], event))
    terminal_event = _validate_cli_events(claude_events)

    canaries = {
        "ambient_agents_loaded": f"{CANARY}_AGENT" in serialized_requests,
        "ambient_config_loaded": Path("/workspace/ambient-settings-fired").exists(),
        "ambient_hooks_loaded": Path("/workspace/ambient-hook-fired").exists(),
        "ambient_mcp_loaded": (
            Path("/workspace/ambient-mcp-fired").exists()
            or any(name.startswith("mcp__") for name in advertised)
        ),
        "ambient_project_instructions_loaded": (
            f"{CANARY}_PROJECT" in serialized_requests
        ),
        "ambient_skills_loaded": f"{CANARY}_SKILL" in serialized_requests,
        "evaluator_private_bytes_visible": bool(
            attestation["evaluator_private_path_visible"]
        ),
        "external_network_reachable": _external_network_reachable(),
        "host_home_visible": Path("/home/johnhughes").exists(),
        "host_repository_visible": Path("/work/Development").exists(),
    }
    _require_clear_canaries(canaries)

    return {
        "binary": {"sha256": expected_sha256, "version": version},
        "canaries": canaries,
        "deliverable": {
            "content": DELIVERABLE,
            "path": "/workspace/deliverable.txt",
            "sealed_sha256": _sha256(deliverable),
        },
        "native_loop": {
            "context_round_trips": state.message_round_trips,
            "message_round_trips": state.message_round_trips,
            "stream_terminal_subtype": terminal_event.get("subtype"),
            "used_local_stub": True,
        },
        "native_tool_inventory": {
            "advertised": advertised,
            "disabled_surface_tools_present": _disabled_surface_tools(advertised),
            "native_subagent": {
                "status": "present" if subagent_name else "absent",
                "tool_name": subagent_name,
            },
            "required_local_tools": sorted(REQUIRED_TOOLS),
        },
        "outer_boundary": {
            "fail_closed_conditions": list(FAIL_CLOSED_CONDITIONS),
            "kind": "systemd-transient-root-directory",
            "network_namespace": {
                "distinct_from_host": (
                    attestation["inner_network_namespace"]
                    != attestation["host_network_namespace"]
                ),
                "host": attestation["host_network_namespace"],
                "inner": attestation["inner_network_namespace"],
            },
            "private_network": (
                attestation["inner_network_namespace"]
                != attestation["host_network_namespace"]
            ),
            "read_only_os_binds": ["/bin", "/lib", "/lib64", "/usr"],
            "observed_runtime": attestation["observed_runtime"],
            "requested_systemd_properties": list(SYSTEMD_PROPERTIES),
            "root_directory": "disposable",
            "sensitive_private_host_paths_bound": [],
            "writable_paths": ["/home/claude", "/tmp", "/workspace"],
        },
        "profile": {
            "claude_argv": argv[1:],
            "description": "clean-install native",
            "disabled_stock_capabilities": list(DISABLED_STOCK_CAPABILITIES),
            "literal_out_of_box_claim_allowed": False,
            "task_mcp_servers": [],
            "unverified_safe_mode_surfaces": list(UNVERIFIED_SAFE_MODE_SURFACES),
        },
        "probe": {"source_sha256": attestation["probe_source_sha256"]},
        "schema_version": "legalforecast.claude_code_native_containment_probe.v2",
        "spend": {
            "benchmark_task_bytes": 0,
            "count_token_requests": state.count_token_calls,
            "local_stub_requests": state.accepted_http_calls,
            "message_round_trips": state.message_round_trips,
            "provider_requests": 0,
        },
        "tool_probes": {
            name: state.tool_results[name] for name in sorted(REQUIRED_TOOLS)
        },
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.self_test_positive_canary is not None:
            canaries = {name: False for name in CANARY_KEYS}
            canaries[args.self_test_positive_canary] = True
            _require_clear_canaries(canaries)
            _fail("positive-canary self-test unexpectedly passed")
        if args.inner:
            evidence = _inner_probe(args.claude_binary, args.expected_sha256)
        else:
            evidence = _outer_probe(args.claude_binary, args.expected_sha256)
        encoded = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
        sys.stdout.write(encoded)
    except (
        OSError,
        ProbeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"claude native containment probe: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

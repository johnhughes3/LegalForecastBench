from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "claude_native_containment"
    / "claude-code-native-containment-2.1.218.json"
)
PROBE = ROOT / "scripts" / "probe_claude_code_native_containment.py"
EXPECTED_SHA256 = "e12071751a9336b8af1012c103358ff04ac18f9aaff4a738cff7ba5cdfaf63f2"
REQUIRED_LOCAL_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}
CANARY_KEYS = {
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
}
FIXTURE_REQUIRED = pytest.mark.skipif(
    not FIXTURE.is_file(),
    reason="privileged Claude containment evidence has not been captured",
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _probe_module() -> Any:
    spec = importlib.util.spec_from_file_location("claude_native_probe", PROBE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pre_capture_profile_pins_exact_218_binary_and_one_permission_mode() -> None:
    module = _probe_module()

    assert module.EXPECTED_VERSION == "2.1.218 (Claude Code)"
    assert module.EXPECTED_SHA256 == EXPECTED_SHA256
    assert module._parser().parse_args([]).claude_binary == Path(
        "/work/.local/share/claude/versions/2.1.218"
    )
    argv = module._claude_argv(Path("/opt/claude"))
    assert argv.count("--dangerously-skip-permissions") == 1
    assert "--permission-mode" not in argv
    assert module.UNVERIFIED_SAFE_MODE_SURFACES == ("ambient plugins",)
    assert "ambient plugins" not in module.DISABLED_STOCK_CAPABILITIES


def test_outer_binary_preflight_hashes_without_executing_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _probe_module()
    binary = tmp_path / "claude"
    binary.write_bytes(b"reviewed claude candidate")
    binary.chmod(0o755)
    expected = hashlib.sha256(binary.read_bytes()).hexdigest()

    def forbidden_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("outer binary preflight executed the candidate")

    monkeypatch.setattr(module.subprocess, "run", forbidden_run)

    assert module._outer_binary_preflight(binary, expected) == {
        "path": str(binary.resolve()),
        "sha256": expected,
    }


def test_external_canary_never_opens_the_disposable_root_parent(
    tmp_path: Path,
) -> None:
    module = _probe_module()
    disposable_parent = tmp_path / "sealed-root-parent"
    disposable_parent.mkdir(mode=0o700)
    root = disposable_parent / "root"
    root.mkdir()
    binary = tmp_path / "claude"
    binary.write_bytes(b"reviewed candidate")
    binary.chmod(0o755)
    module._prepare_root(root, binary, {})

    current_user = module.pwd.getpwuid(os.getuid())
    canary_parent, canary_dir = module._create_external_canary_directory(current_user)
    try:
        assert stat.S_IMODE(disposable_parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(root.stat().st_mode) == 0o755
        assert stat.S_IMODE((root / "workspace").stat().st_mode) == 0o777
        assert not (root / "workspace/evidence.json").exists()
        assert canary_parent.parent == Path("/tmp")
        assert canary_dir.parent == canary_parent
        assert stat.S_IMODE(canary_parent.stat().st_mode) == 0o711
        assert stat.S_IMODE(canary_dir.stat().st_mode) == 0o700
        assert not canary_dir.is_relative_to(disposable_parent)
    finally:
        module._remove_external_canary_directory(canary_parent)

    assert not canary_parent.exists()


def test_external_canary_directory_is_removed_after_process_reap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    events: list[str] = []

    class FakeProcess:
        pid = 4242
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            events.append("terminate")

        def wait(self, *, timeout: int) -> int:
            events.append(f"wait:{timeout}")
            self.returncode = 0
            return 0

    def record_removal(_path: Path) -> None:
        events.append("remove")

    monkeypatch.setattr(
        module,
        "_remove_external_canary_directory",
        record_removal,
    )

    module._reap_external_process_canary(FakeProcess(), Path("/tmp/random-canary"))

    assert events == ["terminate", "wait:5", "remove"]


def test_external_canary_reap_failure_preserves_directory_and_names_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    events: list[str] = []

    class StuckProcess:
        pid = 4242

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            events.append("terminate")

        def kill(self) -> None:
            events.append("kill")

        def wait(self, *, timeout: int) -> int:
            events.append(f"wait:{timeout}")
            raise subprocess.TimeoutExpired(["canary"], timeout)

    def forbidden_removal(_path: Path) -> None:
        raise AssertionError("unreaped canary directory was removed")

    monkeypatch.setattr(module, "_remove_external_canary_directory", forbidden_removal)

    with pytest.raises(module.ProbeError, match="PID 4242"):
        module._reap_external_process_canary(StuckProcess(), Path("/tmp/random-canary"))
    assert events == ["terminate", "wait:5", "kill", "wait:5"]


def test_external_canary_post_run_rejects_dead_or_reused_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    attestation = {
        "pid": 4242,
        "host_uid": 1000,
        "host_gid": 1000,
        "root": "/",
        "cwd": "/tmp/canary",
        "sentinel_file_path": "/tmp/canary/sentinel",
        "sentinel_file_owner_uid": 1000,
        "sentinel_file_inode": 12345,
        "sentinel_file_sha256": "a" * 64,
        "sentinel_fd": 3,
        "environment_token_sha256": "b" * 64,
    }

    class Process:
        pid = 4242

        def __init__(self, returncode: int | None) -> None:
            self.returncode = returncode

        def poll(self) -> int | None:
            return self.returncode

    with pytest.raises(module.ProbeError, match="PID 4242 is not alive"):
        module._verify_external_process_canary(Process(0), attestation)

    reused: dict[str, Any] = dict(attestation)
    reused["sentinel_file_inode"] = 99999

    def observe_reused(_pid: int) -> dict[str, object]:
        return reused

    monkeypatch.setattr(
        module,
        "_observe_external_process_canary",
        observe_reused,
    )
    with pytest.raises(module.ProbeError, match="identity drift"):
        module._verify_external_process_canary(Process(None), attestation)


def test_same_uid_supervisor_boundary_is_dumpability_hardened_in_subprocess() -> None:
    code = f"""
import importlib.util, json
spec = importlib.util.spec_from_file_location("probe", {str(PROBE)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps(module._establish_same_uid_supervisor_boundary(), sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    observed = json.loads(result.stdout)
    assert observed == {
        "child_environ_denied": True,
        "child_mem_denied": True,
        "child_stdout_fd_denied": True,
        "dumpable_disabled": True,
        "same_uid_signal_availability_only": True,
        "supervisor_survived_signal": True,
    }


def test_systemd_command_uses_dynamic_identity_and_bounded_lifecycle(
    tmp_path: Path,
) -> None:
    module = _probe_module()
    unit = "lfb-claude-native-a1b2c3d4.service"
    command = module._systemd_command(
        tmp_path,
        "a" * 64,
        "boundary-nonce",
        unit,
    )
    properties = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--property"
    }

    assert "DynamicUser=yes" in properties
    assert "User=johnhughes" not in properties
    assert "Group=johnhughes" not in properties
    assert "PrivatePIDs=yes" not in properties
    assert "RuntimeMaxSec=120s" in properties
    assert "TasksMax=64" in properties
    assert "MemoryMax=1G" in properties
    assert "KillMode=control-group" in properties
    assert "TimeoutStopSec=10s" in properties
    assert f"Environment=LFB_TRANSIENT_UNIT={unit}" in properties
    assert "--inner-evidence-path" not in command
    assert "--output" not in command


def test_unit_stdout_contains_exactly_one_json_receipt() -> None:
    module = _probe_module()

    assert module._parse_unit_stdout('{"receipt": true}\n') == {"receipt": True}
    with pytest.raises(module.ProbeError, match="exactly one JSON object"):
        module._parse_unit_stdout('{"receipt": true}\n{"forged": true}\n')
    with pytest.raises(module.ProbeError, match="JSON object"):
        module._parse_unit_stdout("not-json")


def test_transient_unit_cleanup_stops_kills_and_proves_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    calls: list[list[str]] = []
    results = iter(
        [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess(
                [], 0, "ActiveState=inactive\nLoadState=loaded\n", ""
            ),
        ]
    )

    def fake_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return next(results)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    proof = module._cleanup_transient_unit("lfb-claude-native-test.service")

    assert [call[1] for call in calls] == ["stop", "kill", "show"]
    assert proof == {
        "inactive_verified": True,
        "kill_attempted": True,
        "load_state": "loaded",
        "manager_state": "inactive",
        "status_poll_count": 1,
        "stop_attempted": True,
    }


def test_transient_unit_cleanup_still_kills_and_checks_after_stop_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    calls: list[str] = []

    def fake_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv[1])
        if argv[1] == "stop":
            raise subprocess.TimeoutExpired(argv, 20)
        if argv[1] == "kill":
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(
            argv, 0, "ActiveState=failed\nLoadState=loaded\n", ""
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    proof = module._cleanup_transient_unit("lfb-claude-native-test.service")
    assert calls == ["stop", "kill", "show"]
    assert proof["inactive_verified"] is True
    assert proof["manager_state"] == "failed"


def test_transient_unit_cleanup_rejects_total_dbus_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()
    calls: list[str] = []

    def unavailable(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv[1])
        raise subprocess.CalledProcessError(1, argv, stderr="D-Bus unavailable")

    monkeypatch.setattr(module.subprocess, "run", unavailable)

    with pytest.raises(module.ProbeError, match="inactivity was not proven"):
        module._cleanup_transient_unit("lfb-claude-native-test.service")
    assert calls == ["stop", "kill", "show"]


@pytest.mark.parametrize(
    "status_stdout",
    [
        "",
        "ActiveState=deactivating\nLoadState=loaded\n",
        "ActiveState=unknown\nLoadState=loaded\n",
        "ActiveState=inactive\nLoadState=unknown\n",
    ],
)
def test_transient_unit_cleanup_rejects_ambiguous_manager_status(
    status_stdout: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _probe_module()

    def fake_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv[1] in {"stop", "kill"}:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, status_stdout, "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.ProbeError, match="inactivity was not proven"):
        module._cleanup_transient_unit("lfb-claude-native-test.service")


def test_unproven_unit_cleanup_preserves_root_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _probe_module()
    parent = tmp_path / "sealed-root-parent"
    parent.mkdir()

    def cleanup_failure(_unit: str) -> dict[str, Any]:
        raise module.ProbeError("D-Bus unavailable")

    monkeypatch.setattr(module, "_cleanup_transient_unit", cleanup_failure)

    with pytest.raises(module.ProbeError, match=str(parent)):
        module._finalize_outer_resources(
            parent,
            "lfb-claude-native-test.service",
            None,
            None,
        )
    assert parent.is_dir()


def test_dynamic_runtime_identity_status_and_cgroup_are_fail_closed() -> None:
    module = _probe_module()
    status = "\n".join(
        (
            "Uid:\t61123\t61123\t61123\t61123",
            "Gid:\t61124\t61124\t61124\t61124",
            "CapInh:\t0000000000000000",
            "CapPrm:\t0000000000000000",
            "CapEff:\t0000000000000000",
            "CapBnd:\t0000000000000000",
            "CapAmb:\t0000000000000000",
            "NoNewPrivs:\t1",
        )
    )
    unit = "lfb-claude-native-a1b2c3d4.service"

    observed = module._validate_process_identity(status, host_uid=1000, host_gid=1000)
    assert observed["uids"] == [61123, 61123, 61123, 61123]
    assert observed["gids"] == [61124, 61124, 61124, 61124]
    assert observed["no_new_privileges"] is True
    assert all(value == 0 for value in observed["capability_masks"].values())
    assert (
        module._validate_service_cgroup(f"0::/system.slice/{unit}\n", unit)
        == f"/system.slice/{unit}"
    )

    with pytest.raises(module.ProbeError, match="host user identity"):
        module._validate_process_identity(
            status.replace("61123", "1000"), host_uid=1000, host_gid=1000
        )
    with pytest.raises(module.ProbeError, match="NoNewPrivs"):
        module._validate_process_identity(
            status.replace("NoNewPrivs:\t1", "NoNewPrivs:\t0"),
            host_uid=1000,
            host_gid=1000,
        )
    with pytest.raises(module.ProbeError, match="uniform"):
        module._validate_process_identity(
            status.replace(
                "Uid:\t61123\t61123\t61123\t61123",
                "Uid:\t61123\t61125\t61123\t61123",
            ),
            host_uid=1000,
            host_gid=1000,
        )
    with pytest.raises(module.ProbeError, match="uniform"):
        module._validate_process_identity(
            status.replace(
                "Gid:\t61124\t61124\t61124\t61124",
                "Gid:\t61124\t61126\t61124\t61124",
            ),
            host_uid=1000,
            host_gid=1000,
        )


def test_read_only_mount_observation_uses_statvfs_and_mountinfo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()

    def read_only_statvfs(_path: os.PathLike[str] | str) -> SimpleNamespace:
        return SimpleNamespace(f_flag=module.os.ST_RDONLY)

    monkeypatch.setattr(
        module.os,
        "statvfs",
        read_only_statvfs,
    )
    mountinfo = "36 25 0:31 / /usr ro,relatime - ext4 /dev/root ro\n"

    assert module._observe_read_only_mount(Path("/usr"), mountinfo) == {
        "mount_point": "/usr",
        "mountinfo_read_only": True,
        "statvfs_read_only": True,
    }


def test_external_process_canary_requires_every_access_surface_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _probe_module()

    def denied(*_args: object, **_kwargs: object) -> Any:
        raise PermissionError("denied")

    monkeypatch.setattr(module, "_read_proc_link", denied)
    monkeypatch.setattr(module, "_read_proc_bytes", denied)
    monkeypatch.setattr(module, "_list_proc_fd", denied)
    monkeypatch.setattr(module.os, "kill", denied)

    observed = module._probe_external_process_access(4242)
    assert observed == {
        "cwd": "permission-denied",
        "environ": "permission-denied",
        "fd": "permission-denied",
        "root": "permission-denied",
        "signal": "permission-denied",
    }


@FIXTURE_REQUIRED
def test_committed_probe_records_exact_binary_and_zero_provider_spend() -> None:
    evidence = _fixture()

    assert evidence["schema_version"] == (
        "legalforecast.claude_code_native_containment_probe.v2"
    )
    assert evidence["binary"] == {
        "sha256": EXPECTED_SHA256,
        "version": "2.1.218 (Claude Code)",
    }
    assert evidence["probe"] == {
        "source_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest()
    }
    assert evidence["spend"] == {
        "benchmark_task_bytes": 0,
        "count_token_requests": evidence["spend"]["count_token_requests"],
        "local_stub_requests": evidence["spend"]["local_stub_requests"],
        "message_round_trips": evidence["spend"]["message_round_trips"],
        "provider_requests": 0,
    }
    assert evidence["spend"]["local_stub_requests"] > 0
    assert evidence["spend"]["local_stub_requests"] == (
        evidence["spend"]["count_token_requests"]
        + evidence["spend"]["message_round_trips"]
    )


@FIXTURE_REQUIRED
def test_committed_probe_preserves_native_tools_and_records_disabled_stock() -> None:
    evidence = _fixture()
    profile = evidence["profile"]

    argv = profile["claude_argv"]
    assert "--safe-mode" in argv
    assert "--no-chrome" in argv
    assert "--strict-mcp-config" in argv
    assert "--no-session-persistence" in argv
    assert "--dangerously-skip-permissions" in argv
    assert "--permission-mode" not in argv
    assert "--bare" not in argv
    assert profile["task_mcp_servers"] == []
    assert profile["description"] == "clean-install native"
    assert profile["literal_out_of_box_claim_allowed"] is False
    assert profile["unverified_safe_mode_surfaces"] == ["ambient plugins"]

    inventory = evidence["native_tool_inventory"]
    assert REQUIRED_LOCAL_TOOLS <= set(inventory["advertised"])
    assert set(inventory["required_local_tools"]) == REQUIRED_LOCAL_TOOLS
    assert inventory["disabled_surface_tools_present"] == []
    assert inventory["native_subagent"]["status"] in {"present", "absent"}
    if inventory["native_subagent"]["status"] == "present":
        assert inventory["native_subagent"]["tool_name"] in {"Agent", "Task"}

    assert set(profile["disabled_stock_capabilities"]) == {
        "Chrome integration",
        "WebFetch",
        "WebSearch",
        "ambient agents",
        "ambient hooks",
        "ambient MCP servers",
        "ambient project instructions",
        "ambient settings",
        "ambient skills and slash commands",
    }


@FIXTURE_REQUIRED
def test_committed_probe_passes_required_tools_deliverable_and_canaries() -> None:
    evidence = _fixture()

    assert set(evidence["tool_probes"]) == REQUIRED_LOCAL_TOOLS
    assert all(evidence["tool_probes"].values())
    assert evidence["deliverable"] == {
        "content": "FINAL NATIVE_BOUNDARY_OK\n",
        "path": "/workspace/deliverable.txt",
        "sealed_sha256": hashlib.sha256(b"FINAL NATIVE_BOUNDARY_OK\n").hexdigest(),
    }
    assert set(evidence["canaries"]) == CANARY_KEYS
    assert not any(evidence["canaries"].values())
    sentinel = evidence["evaluator_private_sentinel"]
    assert sentinel["planted_outside_root"] is True
    assert sentinel["exact_host_path_checked"] is True
    assert sentinel["visible_from_inner"] is False
    assert len(sentinel["sha256"]) == 64


@FIXTURE_REQUIRED
def test_committed_probe_uses_a_disposable_fail_closed_outer_boundary() -> None:
    boundary = _fixture()["outer_boundary"]

    assert boundary["kind"] == "systemd-transient-root-directory"
    assert boundary["private_network"] is True
    assert boundary["network_namespace"]["distinct_from_host"] is True
    assert boundary["journal_namespace_fallback_detected"] is False
    assert boundary["root_directory"] == "disposable"
    assert boundary["sensitive_private_host_paths_bound"] == []
    assert boundary["read_only_os_binds"] == ["/bin", "/lib", "/lib64", "/usr"]
    assert boundary["writable_paths"] == ["/home/claude", "/tmp", "/workspace"]
    assert "DynamicUser=yes" in boundary["requested_systemd_properties"]
    assert "User=johnhughes" not in boundary["requested_systemd_properties"]
    assert "PrivatePIDs=yes" not in boundary["requested_systemd_properties"]
    runtime = boundary["observed_runtime"]
    assert runtime["process_identity"]["no_new_privileges"] is True
    assert not any(runtime["process_identity"]["capability_masks"].values())
    assert all(
        fact["mountinfo_read_only"] and fact["statvfs_read_only"]
        for fact in runtime["read_only_os_binds"].values()
    )
    external_access = runtime["external_process"]["access"]
    assert set(external_access) == {"cwd", "environ", "fd", "root", "signal"}
    assert set(external_access.values()) <= {
        "permission-denied",
        "not-visible",
    }
    assert runtime["external_process"]["post_run"] == {
        "alive_same_process": True,
        "identity_reverified": True,
    }
    assert runtime["supervisor_boundary"] == {
        "child_environ_denied": True,
        "child_mem_denied": True,
        "child_stdout_fd_denied": True,
        "dumpable_disabled": True,
        "same_uid_signal_availability_only": True,
        "supervisor_survived_signal": True,
    }
    assert boundary["transient_unit_cleanup"]["inactive_verified"] is True
    assert set(boundary["fail_closed_conditions"]) >= {
        "binary hash drift",
        "missing required native tool",
        "outer boundary unavailable",
        "provider endpoint not local",
        "unexpected task MCP server",
        "unsupported Claude stream event or content-block schema",
    }


def test_fail_closed_claims_do_not_overstate_tool_input_validation() -> None:
    module = _probe_module()

    assert (
        "unsupported Claude stream event or content-block schema"
        in module.FAIL_CLOSED_CONDITIONS
    )
    assert "unsupported Claude event or tool schema" not in (
        module.FAIL_CLOSED_CONDITIONS
    )


def test_probe_cli_help_is_credential_free() -> None:
    result = subprocess.run(
        [sys.executable, str(PROBE), "--help"],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert "--claude-binary" in result.stdout
    assert "--expected-sha256" in result.stdout
    assert "--output" not in result.stdout
    assert "--inner" not in result.stdout


def test_direct_inner_mode_fails_without_outer_attestation() -> None:
    result = subprocess.run(
        [sys.executable, str(PROBE), "--inner"],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "outer-boundary attestation" in result.stderr


def test_removed_inner_evidence_path_is_rejected_by_cli(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--inner",
            "--inner-evidence-path",
            str(tmp_path / "untrusted.json"),
        ],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --inner-evidence-path" in result.stderr


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_local_0001",
                    "content": "BASH_NATIVE_OK",
                }
            ],
            True,
        ),
        (
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_local_0001",
                    "content": "failed",
                    "is_error": True,
                }
            ],
            False,
        ),
        ([{"type": "text", "text": "toolu_local_0001"}], False),
        (
            [{"type": "tool_result", "tool_use_id": "toolu_local_0001"}],
            False,
        ),
        (
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_local_0001",
                    "content": "ok",
                },
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_local_0001",
                    "content": "duplicate",
                },
            ],
            False,
        ),
    ],
)
def test_tool_result_contract_is_structural_and_exact(
    content: list[dict[str, Any]], expected: bool
) -> None:
    module = _probe_module()
    body = {"messages": [{"role": "user", "content": content}]}

    assert (
        module._has_successful_tool_result(body, "toolu_local_0001", "Bash") is expected
    )


@pytest.mark.parametrize(
    ("tool_name", "content"),
    [
        ("Read", "unrelated but nonempty"),
        ("Glob", "/input/unrelated.bin"),
        ("Grep", "no matching sentinel here"),
        ("Grep", "BOUNDARY_PROBE_INPUT"),
        ("Bash", "arbitrary nonempty result"),
        ("Write", "arbitrary nonempty result"),
        ("Edit", "arbitrary nonempty result"),
    ],
)
def test_capability_specific_tool_results_reject_wrong_nonempty_content(
    tool_name: str, content: str
) -> None:
    module = _probe_module()
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_local_0001",
                        "content": content,
                    }
                ],
            }
        ]
    }

    assert (
        module._has_successful_tool_result(body, "toolu_local_0001", tool_name) is False
    )


@pytest.mark.parametrize(
    ("tool_name", "content"),
    [
        ("Read", "1→BOUNDARY_PROBE_INPUT"),
        ("Glob", "/input/required.txt"),
        (
            "Grep",
            [
                {
                    "type": "text",
                    "text": (
                        "required.txt:BOUNDARY_PROBE_INPUT GREP_RESULT_ONLY_7D4C2A"
                    ),
                }
            ],
        ),
        ("Bash", "BASH_NATIVE_OK"),
        ("Write", "File created successfully at: /workspace/deliverable.txt"),
        (
            "Edit",
            ("The file /workspace/deliverable.txt has been updated successfully."),
        ),
    ],
)
def test_capability_specific_tool_results_accept_expected_content(
    tool_name: str, content: object
) -> None:
    module = _probe_module()
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_local_0001",
                        "content": content,
                    }
                ],
            }
        ]
    }

    assert (
        module._has_successful_tool_result(body, "toolu_local_0001", tool_name) is True
    )


def test_bash_probe_binds_file_and_stdout_to_the_same_exact_sentinel() -> None:
    module = _probe_module()
    command = module._tool_input("Bash")["command"]

    assert module.TOOL_RESULT_SENTINELS["Bash"] == module.BASH_NATIVE_SENTINEL
    assert "! timeout" not in command
    assert f"{module.BASH_DNS_GUARD};" in command
    assert command.endswith(
        "printf 'BASH_NATIVE_OK\\n' > /workspace/bash-ok.txt; "
        "printf 'BASH_NATIVE_OK\\n'"
    )


@pytest.mark.parametrize(("getent_exit", "expected_exit"), [(0, 98), (1, 0)])
def test_bash_dns_guard_explicitly_fails_only_when_dns_succeeds(
    tmp_path: Path, getent_exit: int, expected_exit: int
) -> None:
    module = _probe_module()
    tools = tmp_path / "bin"
    tools.mkdir()
    timeout = tools / "timeout"
    timeout.write_text('#!/bin/sh\nshift\nexec "$@"\n', encoding="utf-8")
    timeout.chmod(0o755)
    getent = tools / "getent"
    getent.write_text(f"#!/bin/sh\nexit {getent_exit}\n", encoding="utf-8")
    getent.chmod(0o755)

    result = subprocess.run(
        ["/bin/sh", "-c", f"set -eu; {module.BASH_DNS_GUARD}; exit 0"],
        env={"PATH": str(tools)},
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == expected_exit


def test_grep_result_sentinel_is_file_match_evidence_absent_from_request() -> None:
    module = _probe_module()
    grep_input = module._tool_input("Grep")
    sentinel = module.TOOL_RESULT_SENTINELS["Grep"]

    assert sentinel == ("required.txt:BOUNDARY_PROBE_INPUT GREP_RESULT_ONLY_7D4C2A")
    assert sentinel not in json.dumps(grep_input, sort_keys=True)


def _successful_tool_result_body(
    module: Any, tool_name: str, step: int
) -> dict[str, Any]:
    return {
        "tools": [{"name": name} for name in module.REQUIRED_TOOLS],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"toolu_local_{step:04d}",
                        "content": module.TOOL_RESULT_SENTINELS[tool_name],
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ("tool_name", "observed", "expected"),
    [
        ("Write", b"FINAL NATIVE_BOUNDARY_OK\n", b"DRAFT NATIVE_BOUNDARY_OK\n"),
        ("Edit", b"DRAFT NATIVE_BOUNDARY_OK\n", b"FINAL NATIVE_BOUNDARY_OK\n"),
    ],
)
def test_write_edit_success_rejects_wrong_immediate_deliverable_state(
    tmp_path: Path, tool_name: str, observed: bytes, expected: bytes
) -> None:
    module = _probe_module()
    deliverable = tmp_path / "deliverable.txt"
    deliverable.write_bytes(observed)
    state = module._ProbeState(deliverable_path=deliverable)
    step = module.REQUIRED_TOOLS.index(tool_name) + 1
    state.step = step

    with pytest.raises(module.ProbeError, match="expected bytes"):
        state.next_response(_successful_tool_result_body(module, tool_name, step))

    assert deliverable.read_bytes() != expected


@pytest.mark.parametrize("tool_name", ["Write", "Edit"])
def test_write_edit_success_rejects_missing_immediate_deliverable_state(
    tmp_path: Path, tool_name: str
) -> None:
    module = _probe_module()
    state = module._ProbeState(deliverable_path=tmp_path / "missing.txt")
    step = module.REQUIRED_TOOLS.index(tool_name) + 1
    state.step = step

    with pytest.raises(module.ProbeError, match="did not complete"):
        state.next_response(_successful_tool_result_body(module, tool_name, step))


@pytest.mark.parametrize(
    ("tool_name", "expected"),
    [
        ("Write", b"DRAFT NATIVE_BOUNDARY_OK\n"),
        ("Edit", b"FINAL NATIVE_BOUNDARY_OK\n"),
    ],
)
def test_write_edit_success_accepts_exact_immediate_deliverable_state(
    tmp_path: Path, tool_name: str, expected: bytes
) -> None:
    module = _probe_module()
    deliverable = tmp_path / "deliverable.txt"
    deliverable.write_bytes(expected)
    state = module._ProbeState(deliverable_path=deliverable)
    step = module.REQUIRED_TOOLS.index(tool_name) + 1
    state.step = step

    state.next_response(_successful_tool_result_body(module, tool_name, step))
    assert state.tool_results[tool_name] is True


def test_tool_result_contract_rejects_non_user_message() -> None:
    module = _probe_module()
    body = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_local_0001",
                        "content": "ok",
                    }
                ],
            }
        ]
    }

    assert module._has_successful_tool_result(body, "toolu_local_0001", "Bash") is False


@pytest.mark.parametrize(
    "content",
    [b"", b"arbitrary nonempty result\n", b"BASH_NATIVE_OK\nextra"],
)
def test_exact_bash_canary_rejects_wrong_file_bytes(
    tmp_path: Path, content: bytes
) -> None:
    module = _probe_module()
    canary = tmp_path / "bash-ok.txt"
    canary.write_bytes(content)

    with pytest.raises(module.ProbeError, match="expected bytes"):
        module._require_exact_file_bytes(
            canary, b"BASH_NATIVE_OK\n", "native Bash canary probe"
        )


def test_exact_bash_canary_accepts_expected_file_bytes(tmp_path: Path) -> None:
    module = _probe_module()
    canary = tmp_path / "bash-ok.txt"
    canary.write_bytes(b"BASH_NATIVE_OK\n")

    module._require_exact_file_bytes(
        canary, b"BASH_NATIVE_OK\n", "native Bash canary probe"
    )


def test_exact_bash_canary_rejects_missing_file(tmp_path: Path) -> None:
    module = _probe_module()

    with pytest.raises(module.ProbeError, match="did not complete"):
        module._require_exact_file_bytes(
            tmp_path / "missing-bash-ok.txt",
            b"BASH_NATIVE_OK\n",
            "native Bash canary probe",
        )


def test_actual_evaluator_private_host_path_must_be_hidden(
    tmp_path: Path,
) -> None:
    module = _probe_module()
    planted = tmp_path / "evaluator-private-canary"
    planted.write_text("private\n", encoding="utf-8")

    with pytest.raises(module.ProbeError, match="evaluator-private host path"):
        module._require_hidden_evaluator_private_path(str(planted))

    planted.unlink()
    module._require_hidden_evaluator_private_path(str(planted))


def test_probe_source_attestation_fails_closed_on_mismatch(tmp_path: Path) -> None:
    module = _probe_module()
    source = tmp_path / "probe.py"
    source.write_text("print('reviewed')\n", encoding="utf-8")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()

    assert module._verify_probe_source(source, expected) == expected
    with pytest.raises(module.ProbeError, match="probe source hash drift"):
        module._verify_probe_source(source, "0" * 64)


def _realistic_runtime_receipt() -> dict[str, Any]:
    return {
        "binary": {"version": "2.1.218 (Claude Code)"},
        "outer_boundary": {
            "network_namespace": {
                "distinct_from_host": True,
                "host": "net:[100]",
                "inner": "net:[200]",
            },
            "private_network": True,
            "observed_runtime": {
                "process_identity": {
                    "uids": [61123, 61123, 61123, 61123],
                    "gids": [61124, 61124, 61124, 61124],
                    "no_new_privileges": True,
                    "capability_masks": {"CapEff": 0},
                },
                "service_cgroup": (
                    "/system.slice/lfb-claude-native-probe-a1b2c3d4e5f6.service"
                ),
                "external_process": {
                    "attested": {
                        "pid": 4001,
                        "host_uid": 1000,
                        "host_gid": 1000,
                        "root": "/",
                        "cwd": ("/tmp/lfb-johnhughes-process-canary-abc123_x/canary"),
                        "sentinel_file_path": (
                            "/tmp/lfb-johnhughes-process-canary-abc123_x/"
                            "canary/sentinel"
                        ),
                        "sentinel_file_owner_uid": 1000,
                        "sentinel_file_inode": 7001,
                        "sentinel_file_sha256": "a" * 64,
                        "sentinel_fd": 3,
                        "environment_token_sha256": "b" * 64,
                    },
                    "access": {
                        "cwd": "not-visible",
                        "environ": "permission-denied",
                        "fd": "permission-denied",
                        "root": "not-visible",
                        "signal": "permission-denied",
                    },
                    "post_run": {
                        "alive_same_process": True,
                        "identity_reverified": True,
                    },
                },
                "supervisor_boundary": {
                    "dumpable_disabled": True,
                    "child_environ_denied": True,
                    "child_mem_denied": True,
                    "child_stdout_fd_denied": True,
                    "same_uid_signal_availability_only": True,
                    "supervisor_survived_signal": True,
                },
            },
            "transient_unit_cleanup": {
                "inactive_verified": True,
                "kill_attempted": True,
                "load_state": "loaded",
                "manager_state": "inactive",
                "status_poll_count": 1,
                "stop_attempted": True,
            },
        },
    }


def test_stable_evidence_projection_normalizes_only_explicit_runtime_ids() -> None:
    module = _probe_module()
    first = _realistic_runtime_receipt()
    second = json.loads(json.dumps(first))
    boundary = second["outer_boundary"]
    boundary["network_namespace"].update({"host": "net:[300]", "inner": "net:[400]"})
    runtime = boundary["observed_runtime"]
    runtime["process_identity"]["uids"] = [62123] * 4
    runtime["process_identity"]["gids"] = [62124] * 4
    runtime["service_cgroup"] = (
        "/system.slice/lfb-claude-native-probe-0f1e2d3c4b5a.service"
    )
    attested = runtime["external_process"]["attested"]
    attested.update(
        {
            "pid": 5002,
            "cwd": "/tmp/lfb-johnhughes-process-canary-def456_y/canary",
            "sentinel_file_path": (
                "/tmp/lfb-johnhughes-process-canary-def456_y/canary/sentinel"
            ),
            "sentinel_file_inode": 8002,
            "sentinel_fd": 7,
            "environment_token_sha256": "c" * 64,
        }
    )
    runtime["external_process"]["access"].update(
        {
            "cwd": "permission-denied",
            "environ": "not-visible",
            "fd": "not-visible",
            "root": "permission-denied",
            "signal": "not-visible",
        }
    )
    boundary["transient_unit_cleanup"].update(
        {
            "load_state": "not-found",
            "manager_state": "failed",
            "status_poll_count": 4,
        }
    )

    assert module.stable_evidence_projection(first) == (
        module.stable_evidence_projection(second)
    )
    assert first["outer_boundary"]["network_namespace"]["host"] == "net:[100]"

    second["binary"]["version"] = "unexpected"
    assert module.stable_evidence_projection(first) != (
        module.stable_evidence_projection(second)
    )


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("outer_boundary", "private_network"), False),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "process_identity",
                "no_new_privileges",
            ),
            False,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "access",
                "root",
            ),
            "accessible",
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "supervisor_boundary",
                "dumpable_disabled",
            ),
            False,
        ),
        (
            (
                "outer_boundary",
                "transient_unit_cleanup",
                "inactive_verified",
            ),
            False,
        ),
    ],
)
def test_stable_projection_preserves_security_fact_drift(
    path: tuple[str, ...], replacement: object
) -> None:
    module = _probe_module()
    first = _realistic_runtime_receipt()
    drifted = json.loads(json.dumps(first))
    cursor: dict[str, Any] = drifted
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement

    assert module.stable_evidence_projection(first) != (
        module.stable_evidence_projection(drifted)
    )


@pytest.mark.parametrize(
    ("identity_key", "host_key"),
    [("uids", "host_uid"), ("gids", "host_gid")],
)
def test_stable_projection_rejects_dynamic_identity_equal_to_attested_host(
    identity_key: str, host_key: str
) -> None:
    module = _probe_module()
    tampered = _realistic_runtime_receipt()
    runtime = tampered["outer_boundary"]["observed_runtime"]
    host_id = runtime["external_process"]["attested"][host_key]
    runtime["process_identity"][identity_key] = [host_id] * 4

    with pytest.raises(module.ProbeError, match="host user identity"):
        module.stable_evidence_projection(tampered)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("outer_boundary", "network_namespace", "host"), "net:[not-digits]"),
        (("outer_boundary", "network_namespace", "inner"), "net:[100]"),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "process_identity",
                "uids",
            ),
            [61123, 61123, 0, 61123],
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "process_identity",
                "uids",
            ),
            [61123, 61123, "61123", 61123],
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "process_identity",
                "gids",
            ),
            [61124, 61125, 61124, 61124],
        ),
        (
            ("outer_boundary", "observed_runtime", "service_cgroup"),
            "/system.slice/not-the-attested-unit.service",
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "host_uid",
            ),
            True,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "host_gid",
            ),
            "1000",
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "host_uid",
            ),
            0,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "host_gid",
            ),
            0,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "pid",
            ),
            0,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "cwd",
            ),
            "/tmp/attacker-controlled/canary",
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "sentinel_file_path",
            ),
            "/tmp/different/sentinel",
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "sentinel_file_inode",
            ),
            0,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "sentinel_fd",
            ),
            -1,
        ),
        (
            (
                "outer_boundary",
                "observed_runtime",
                "external_process",
                "attested",
                "environment_token_sha256",
            ),
            "A" * 64,
        ),
        (
            (
                "outer_boundary",
                "transient_unit_cleanup",
                "status_poll_count",
            ),
            0,
        ),
        (
            (
                "outer_boundary",
                "transient_unit_cleanup",
                "status_poll_count",
            ),
            6,
        ),
    ],
)
def test_stable_projection_rejects_tampered_volatile_leaf_before_normalizing(
    path: tuple[str, ...], replacement: object
) -> None:
    module = _probe_module()
    tampered = _realistic_runtime_receipt()
    cursor: dict[str, Any] = tampered
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement

    with pytest.raises(module.ProbeError):
        module.stable_evidence_projection(tampered)


def test_stub_request_contract_accepts_only_the_local_probe_shape() -> None:
    module = _probe_module()
    body = {
        "model": module.MODEL,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": module.PROBE_PROMPT},
                ],
            }
        ],
        "tools": [{"name": "Read"}],
    }

    assert (
        module._validate_stub_request(
            "/v1/messages?beta=true",
            {"x-api-key": module.LOCAL_API_KEY},
            body,
        )
        == "messages"
    )
    count_body = dict(body)
    count_body.pop("stream")
    assert (
        module._validate_stub_request(
            "/v1/messages/count_tokens",
            {"X-API-Key": module.LOCAL_API_KEY},
            count_body,
        )
        == "count_tokens"
    )


@pytest.mark.parametrize(
    ("path", "headers", "body_update", "match"),
    [
        (
            "/unexpected/messages",
            {"x-api-key": "local-stub-no-provider-credential"},
            {},
            "unsupported local-stub path",
        ),
        (
            "/v1/messages",
            {"x-api-key": "wrong"},
            {},
            "authentication marker",
        ),
        (
            "/v1/messages",
            {"x-api-key": "local-stub-no-provider-credential"},
            {"model": "wrong-model"},
            "model drift",
        ),
        (
            "/v1/messages",
            {"x-api-key": "local-stub-no-provider-credential"},
            {"messages": [{"role": "user", "content": "unexpected task bytes"}]},
            "synthetic prompt contract",
        ),
        (
            "/v1/messages",
            {"x-api-key": "local-stub-no-provider-credential"},
            {"stream": False},
            "streaming contract",
        ),
        (
            "/v1/messages?unexpected=true",
            {"x-api-key": "local-stub-no-provider-credential"},
            {},
            "unsupported local-stub query",
        ),
        (
            "/v1/messages",
            {"x-api-key": "local-stub-no-provider-credential"},
            {"tools": []},
            "native tool request contract",
        ),
    ],
)
def test_stub_request_contract_fails_closed(
    path: str,
    headers: dict[str, str],
    body_update: dict[str, object],
    match: str,
) -> None:
    module = _probe_module()
    body = {
        "model": module.MODEL,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": module.PROBE_PROMPT},
                ],
            }
        ],
        "tools": [{"name": "Read"}],
    }
    body.update(body_update)

    with pytest.raises(module.ProbeError, match=match):
        module._validate_stub_request(path, headers, body)


@pytest.mark.parametrize(
    "tool_name",
    ["WebFetch", "WebSearch", "Chrome", "mcp__claude-in-chrome__navigate"],
)
def test_disabled_web_and_chrome_inventory_fails_closed(tool_name: str) -> None:
    module = _probe_module()

    with pytest.raises(module.ProbeError, match="disabled tool surface"):
        module._require_disabled_tools_absent(["Read", tool_name])

    module._require_disabled_tools_absent(["Read", "Glob"])


def test_native_tool_inventory_must_remain_stable_between_requests() -> None:
    module = _probe_module()
    state = module._ProbeState()
    first_tools = [{"name": name} for name in module.REQUIRED_TOOLS]
    state.observe_tool_inventory({"tools": first_tools})
    state.next_response({"tools": first_tools, "messages": []})

    drifted_tools = list(reversed(first_tools))
    with pytest.raises(module.ProbeError, match="inventory drifted"):
        state.next_response({"tools": drifted_tools, "messages": []})


def test_unknown_user_content_blocks_fail_closed() -> None:
    module = _probe_module()
    body = {
        "model": module.MODEL,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "image", "source": "unexpected"}],
            }
        ],
        "tools": [{"name": "Read"}],
    }

    with pytest.raises(module.ProbeError, match="unsupported user content block"):
        module._validate_stub_request(
            "/v1/messages",
            {"x-api-key": module.LOCAL_API_KEY},
            body,
        )


def test_cli_event_contract_allows_known_shapes_and_rejects_unknown() -> None:
    module = _probe_module()
    valid = [
        {
            "type": "system",
            "subtype": "init",
            "session_id": "session",
            "model": module.MODEL,
            "claude_code_version": "2.1.218",
            "tools": list(module.REQUIRED_TOOLS),
        },
        {
            "type": "assistant",
            "session_id": "session",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "done"}],
            },
        },
        {
            "type": "user",
            "session_id": "session",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_local_0001",
                        "content": "ok",
                    }
                ],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "session_id": "session",
        },
    ]

    assert module._validate_cli_events(valid) is valid[-1]
    with pytest.raises(module.ProbeError, match="unsupported Claude stream event"):
        module._validate_cli_events([*valid[:-1], {"type": "future_event"}, valid[-1]])
    malformed = [*valid]
    malformed[1] = {
        "type": "assistant",
        "session_id": "session",
        "message": {
            "role": "assistant",
            "content": [{"type": "unknown"}],
        },
    }
    with pytest.raises(module.ProbeError, match="assistant content block"):
        module._validate_cli_events(malformed)


def test_stub_accounting_counts_all_accepted_http_calls() -> None:
    module = _probe_module()
    state = module._ProbeState()
    tools = [{"name": name} for name in module.REQUIRED_TOOLS]

    state.accept_count_token_request({"tools": tools})
    state.next_response({"tools": tools, "messages": []})

    assert state.accepted_http_calls == 2
    assert state.count_token_calls == 1
    assert state.message_round_trips == 1
    assert len(state.requests) == 1


def test_count_token_body_is_preserved_and_scanned_for_ambient_canary() -> None:
    module = _probe_module()
    state = module._ProbeState()
    tools = [{"name": name} for name in module.REQUIRED_TOOLS]
    body = {
        "tools": tools,
        "metadata": {"untrusted": module.CANARY},
    }

    state.accept_count_token_request(body)

    assert state.accepted_bodies == [body]
    with pytest.raises(module.ProbeError, match="ambient customization canary"):
        module._require_no_ambient_canary(state.accepted_bodies)


def test_request_after_terminal_latches_without_index_error() -> None:
    module = _probe_module()
    state = module._ProbeState()
    tools = [{"name": name} for name in module.REQUIRED_TOOLS]
    body = {"tools": tools, "messages": []}

    for _ in range(len(module.REQUIRED_TOOLS) + 1):
        state.next_response(body)
    with pytest.raises(module.ProbeError, match="after terminal"):
        state.next_response(body)
    with pytest.raises(module.ProbeError, match="after terminal"):
        state.next_response(body)

    count_state = module._ProbeState()
    for _ in range(len(module.REQUIRED_TOOLS) + 1):
        count_state.next_response(body)
    with pytest.raises(module.ProbeError, match="after terminal"):
        count_state.accept_count_token_request({"tools": tools})


def test_http_handler_latches_invalid_request_and_rejects_valid_retry() -> None:
    module = _probe_module()
    state = module._ProbeState()
    server = module.http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), module._handler(state)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    tools = [{"name": name} for name in module.REQUIRED_TOOLS]
    valid = {
        "model": module.MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": module.PROBE_PROMPT}],
        "tools": tools,
    }

    def post(body: dict[str, Any]) -> int:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": module.LOCAL_API_KEY,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        assert post({**valid, "model": "invalid"}) >= 400
        assert post(valid) >= 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    with pytest.raises(module.ProbeError, match="model drift"):
        state.raise_if_failed()
    assert state.accepted_http_calls == 0


def test_completed_probe_requires_exact_message_round_trip_count() -> None:
    module = _probe_module()
    state = module._ProbeState()
    state.message_round_trips = len(module.REQUIRED_TOOLS)

    with pytest.raises(module.ProbeError, match="message round trips"):
        module._validate_completed_probe_state(state)


@pytest.mark.parametrize("canary", sorted(CANARY_KEYS))
def test_every_positive_canary_fails_closed(canary: str) -> None:
    result = subprocess.run(
        [sys.executable, str(PROBE), "--self-test-positive-canary", canary],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert f"containment canary failed: {canary}" in result.stderr


def test_opt_in_probe_matches_committed_evidence() -> None:
    result_path = os.environ.get("CLAUDE_NATIVE_CONTAINMENT_PROBE_RESULT")
    if result_path is None:
        pytest.skip(
            "set CLAUDE_NATIVE_CONTAINMENT_PROBE_RESULT to replay fresh evidence"
        )

    observed = json.loads(Path(result_path).read_text(encoding="utf-8"))
    assert _probe_module().stable_evidence_projection(observed) == (
        _probe_module().stable_evidence_projection(_fixture())
    )

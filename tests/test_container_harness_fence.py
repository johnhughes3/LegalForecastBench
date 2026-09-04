"""Agent-proof web/search fence: nested CLI invocation still has tools off.

Disable flags on the initial docker argv are not a fence.  These tests exec the
wrapper the same way a tools-on agent would: by name, on PATH, without those
flags, and with a rewritten HOME.  The vendor binary is a fake that only dumps
argv, so the assertion is about the fence, not about a live provider.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.container_harness.cli_fence import (
    FENCED_CLIS,
    CliFenceError,
    fenced_argv,
    install_cli_fence,
    materialize_runtime_home,
    seed_agy_web_fence,
)
from legalforecast.multiharness.container_harness.plan import (
    CREDENTIALS_TARGET,
    DEFAULT_CONTAINER_HOME,
    FENCE_BIN_DIR,
    FENCE_WRAPPER_TARGET,
    ContainerHarnessError,
    ContainerHarnessSpec,
    HarnessCredential,
    build_harness_environment,
    build_harness_run_argv,
    build_run_names,
    stage_cli_fence,
    stage_credential_home,
)

_IMAGE = "lfb-harness@sha256:" + "a" * 64
_TOKEN = "0123456789abcdef"
_BACKEND = Path("/usr/bin/docker")


def _spec(tmp_path: Path, **overrides: object) -> ContainerHarnessSpec:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    defaults: dict[str, object] = {
        "run_id": "cycle1-claude-code",
        "image": _IMAGE,
        "harness_argv": ("claude", "-p", "forecast"),
        "workspace": workspace,
        "log_root": tmp_path / "logs",
        "allow_hosts": ("api.anthropic.com",),
    }
    defaults.update(overrides)
    return ContainerHarnessSpec(**defaults)  # pyright: ignore[reportArgumentType]


def _flag_values(argv: tuple[str, ...], flag: str) -> list[str]:
    return [argv[index + 1] for index, item in enumerate(argv) if item == flag]


def _write_fake_cli(path: Path, dump: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(dump)!r}, 'w', encoding='utf-8').write(json.dumps(sys.argv))\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _install_fenced_fake(
    tmp_path: Path, *, cli: str = "claude"
) -> tuple[Path, Path, Path]:
    dump = tmp_path / "argv.json"
    vendor = tmp_path / "vendor" / cli
    _write_fake_cli(vendor, dump)
    bin_dir = tmp_path / "layout" / "bin"
    libexec = tmp_path / "layout" / "libexec"
    install_cli_fence(bin_dir=bin_dir, libexec_dir=libexec, cli=cli, real_binary=vendor)
    return bin_dir, libexec, dump


def test_kimi_is_not_a_fenced_cli() -> None:
    assert "kimi" not in FENCED_CLIS
    with pytest.raises(CliFenceError, match="not a fenced"):
        fenced_argv("kimi", ["-p", "forecast"])
    names = builtin_adapter_registry().known_names()
    assert not any("kimi" in name.lower() for name in names)


def test_fenced_argv_injects_disable_flags_when_the_agent_omits_them() -> None:
    claude = fenced_argv("claude", ["-p", "forecast"])
    assert claude[:3] == ["--disallowedTools", "WebSearch", "WebFetch"]
    assert "-p" in claude and "forecast" in claude

    grok = fenced_argv("grok", ["-p", "forecast"])
    assert grok[0] == "--disable-web-search"

    codex = fenced_argv("codex", ["exec", "--json", "forecast"])
    assert codex[0] == "exec"
    assert 'web_search="disabled"' in codex
    assert "--ignore-user-config" in codex


def test_fenced_argv_strips_flags_that_would_re_enable_web_tools() -> None:
    claude = fenced_argv(
        "claude",
        ["--allowedTools", "WebSearch", "WebFetch", "-p", "forecast"],
    )
    assert "WebSearch" in claude
    assert claude.count("--allowedTools") == 0
    assert claude[0] == "--disallowedTools"

    grok = fenced_argv("grok", ["--enable-web-search", "-p", "forecast"])
    assert "--enable-web-search" not in grok
    assert grok.count("--disable-web-search") == 1

    codex = fenced_argv(
        "codex",
        ["exec", "-c", "web_search=enabled", "--json"],
    )
    assert "web_search=enabled" not in codex
    assert 'web_search="disabled"' in codex


def test_nested_invocation_without_disable_flags_still_has_tools_off(
    tmp_path: Path,
) -> None:
    bin_dir, _libexec, dump = _install_fenced_fake(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "/usr/bin"),
        "HOME": str(home),
        "LFB_CREDENTIALS_ROOT": str(tmp_path / "missing-creds"),
    }

    completed = subprocess.run(
        ["claude", "-p", "forecast"],
        env=env,
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(dump.read_text(encoding="utf-8"))
    assert Path(recorded[0]).name == "claude"
    assert recorded[1:4] == ["--disallowedTools", "WebSearch", "WebFetch"]
    assert "-p" in recorded and "forecast" in recorded


def test_nested_invocation_cannot_reenable_tools_via_argv_or_home_config(
    tmp_path: Path,
) -> None:
    bin_dir, _libexec, dump = _install_fenced_fake(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / "settings.json").write_text(
        '{"allowedTools": ["WebSearch", "WebFetch"]}\n', encoding="utf-8"
    )
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "/usr/bin"),
        "HOME": str(home),
    }

    completed = subprocess.run(
        ["claude", "--allowedTools", "WebSearch", "-p", "forecast"],
        env=env,
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(dump.read_text(encoding="utf-8"))
    assert "--allowedTools" not in recorded
    assert recorded[1:4] == ["--disallowedTools", "WebSearch", "WebFetch"]


def test_the_only_path_name_for_the_cli_is_the_wrapper(tmp_path: Path) -> None:
    bin_dir, libexec, _dump = _install_fenced_fake(tmp_path)
    wrapper = (bin_dir / "claude").read_bytes()
    real = (libexec / "claude").read_bytes()

    assert wrapper != real
    assert b"--disallowedTools" in wrapper
    assert stat.S_IMODE((bin_dir / "claude").stat().st_mode) == 0o755
    assert stat.S_IMODE((libexec / "claude").stat().st_mode) == 0o755
    assert (bin_dir / "lfb-cli-fence").read_bytes() == wrapper


def test_credential_files_are_copied_into_home_but_not_clobbered(
    tmp_path: Path,
) -> None:
    creds = tmp_path / "creds"
    (creds / ".claude").mkdir(parents=True)
    (creds / ".claude.json").write_text('{"token": "original"}', encoding="utf-8")
    (creds / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    home = tmp_path / "home"

    materialize_runtime_home(home, creds)
    assert (home / ".claude.json").read_text(
        encoding="utf-8"
    ) == '{"token": "original"}'
    (home / ".claude.json").write_text('{"token": "refreshed"}', encoding="utf-8")
    materialize_runtime_home(home, creds)
    assert (home / ".claude.json").read_text(
        encoding="utf-8"
    ) == '{"token": "refreshed"}'


def test_agy_nested_invocation_reseeds_hooks_the_agent_rewrote(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    planted = home / ".gemini" / "config" / "hooks.json"
    planted.parent.mkdir(parents=True)
    planted.write_text('{"enabled": false}\n', encoding="utf-8")

    seed_agy_web_fence(home)

    rewritten = planted.read_text(encoding="utf-8")
    assert "search_web" in rewritten
    assert "deny-web-tools" in rewritten
    deny = home / ".lfb-fence" / "deny-web-tools"
    assert stat.S_IMODE(deny.stat().st_mode) == 0o755


def test_plan_mounts_credentials_read_only_and_home_as_tmpfs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text('{"token": "secret"}', encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )
    names = build_run_names(spec.run_id, _TOKEN)
    home = stage_credential_home(tmp_path / "staging", spec)
    fence = stage_cli_fence(tmp_path / "staging")

    argv = build_harness_run_argv(
        _BACKEND,
        spec,
        names,
        credential_home=home,
        cidfile=tmp_path / "harness.cid",
        fence_binary=fence,
    )
    mounts = _flag_values(argv, "--mount")
    tmpfs = _flag_values(argv, "--tmpfs")

    assert any(
        item == f"type=bind,src={home},dst={CREDENTIALS_TARGET},readonly"
        for item in mounts
    )
    assert not any(
        f"dst={spec.container_home}" in item and "readonly" not in item
        for item in mounts
        if "type=bind" in item
    )
    assert any(item.startswith(f"{DEFAULT_CONTAINER_HOME}:") for item in tmpfs)
    assert _flag_values(argv, "--entrypoint") == [FENCE_WRAPPER_TARGET]
    assert f"type=bind,src={fence},dst={FENCE_WRAPPER_TARGET},readonly" in mounts
    assert f"type=bind,src={fence},dst={FENCE_BIN_DIR}/claude,readonly" in mounts


def test_child_path_puts_the_wrapper_first(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    names = build_run_names(spec.run_id, _TOKEN)

    environment = build_harness_environment(spec, names)

    assert environment["PATH"].startswith(f"{FENCE_BIN_DIR}:")
    assert environment["LFB_HARNESS_CLI"] == "claude"
    assert environment["LFB_HARNESS_REAL_BIN"].endswith("/libexec/claude")
    assert environment["LFB_CREDENTIALS_ROOT"] == CREDENTIALS_TARGET
    assert environment["HOME"] == spec.container_home


def test_unknown_cli_is_refused_before_the_container_starts(tmp_path: Path) -> None:
    with pytest.raises(ContainerHarnessError, match="not a fenced"):
        _spec(tmp_path, harness_argv=("kimi", "-p", "forecast"))


def test_staged_fence_binary_is_executable(tmp_path: Path) -> None:
    staged = stage_cli_fence(tmp_path / "staging")

    assert staged.is_file()
    assert stat.S_IMODE(staged.stat().st_mode) == 0o755
    assert b"FENCED_CLIS" in staged.read_bytes()

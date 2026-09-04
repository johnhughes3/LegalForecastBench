"""The containerized harness plan, asserted as data without spawning a backend.

Every test here builds argv, environment or staged files and inspects them
directly.  Nothing calls Docker, so the plan is checkable in CI on a machine
with no container backend at all -- which is exactly the property that makes
these assertions about the *fence* trustworthy rather than environment-shaped.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    require_digest_pinned_image,
)
from legalforecast.multiharness.container_harness.plan import (
    PROXY_EVIDENCE_TARGET,
    PROXY_SOURCE_TARGET,
    WORKSPACE_TARGET,
    ContainerHarnessError,
    ContainerHarnessResult,
    ContainerHarnessSpec,
    HarnessCredential,
    build_egress_network_create_argv,
    build_harness_environment,
    build_harness_run_argv,
    build_network_connect_argv,
    build_network_create_argv,
    build_proxy_run_argv,
    build_run_names,
    egress_network_name,
    egress_proxy_source_path,
    stage_credential_home,
)

_IMAGE = "lfb-harness@sha256:" + "a" * 64
_PROXY_IMAGE = "lfb-proxy@sha256:" + "b" * 64
_TOKEN = "0123456789abcdef"
_BACKEND = Path("/usr/bin/docker")
_SECRET = "sk-ant-api03-MUST-NOT-APPEAR-ON-ARGV"


def _spec(tmp_path: Path, **overrides: object) -> ContainerHarnessSpec:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    logs = tmp_path / "logs"
    defaults: dict[str, object] = {
        "run_id": "cycle1-claude-code",
        "image": _IMAGE,
        "harness_argv": ("claude", "-p", "forecast"),
        "workspace": workspace,
        "log_root": logs,
        "allow_hosts": ("api.anthropic.com", "console.anthropic.com"),
    }
    defaults.update(overrides)
    return ContainerHarnessSpec(**defaults)  # pyright: ignore[reportArgumentType]


def _flag_values(argv: tuple[str, ...], flag: str) -> list[str]:
    return [argv[index + 1] for index, item in enumerate(argv) if item == flag]


def test_image_must_be_digest_pinned(tmp_path: Path) -> None:
    with pytest.raises(ContainerImageError, match="digest-pinned"):
        require_digest_pinned_image("lfb-harness:latest", "image")
    with pytest.raises(ContainerImageError, match="digest-pinned"):
        _spec(tmp_path, image="lfb-harness:latest")
    with pytest.raises(ContainerImageError, match="digest-pinned"):
        _spec(tmp_path, proxy_image="python:3-alpine")

    assert require_digest_pinned_image(_IMAGE, "image") == _IMAGE
    assert require_digest_pinned_image("sha256:" + "c" * 64, "image").endswith("c" * 8)


def test_spec_requires_an_explicit_argv_and_a_usable_run_id(tmp_path: Path) -> None:
    with pytest.raises(ContainerHarnessError, match="flag-explicit"):
        _spec(tmp_path, harness_argv=())
    with pytest.raises(ContainerHarnessError, match="run_id must be"):
        _spec(tmp_path, run_id="Cycle 1")


def test_proxy_image_defaults_to_the_harness_image(tmp_path: Path) -> None:
    assert _spec(tmp_path).resolved_proxy_image() == _IMAGE
    assert _spec(tmp_path, proxy_image=_PROXY_IMAGE).resolved_proxy_image() == (
        _PROXY_IMAGE
    )


def test_run_names_are_unique_per_token_and_docker_safe(tmp_path: Path) -> None:
    names = build_run_names(_spec(tmp_path).run_id, _TOKEN)

    assert names.network == f"lfb-cycle1-claude-code-{_TOKEN}-net"
    assert names.egress_network == f"lfb-cycle1-claude-code-{_TOKEN}-out"
    assert names.proxy_container == f"lfb-cycle1-claude-code-{_TOKEN}-egress"
    assert names.harness_container == f"lfb-cycle1-claude-code-{_TOKEN}-harness"
    assert (
        len(
            {
                names.network,
                names.egress_network,
                names.proxy_container,
                names.harness_container,
            }
        )
        == 4
    )
    with pytest.raises(ContainerHarnessError, match="hex characters"):
        build_run_names("cycle1", "not-hex!")


def test_the_run_network_has_no_external_route(tmp_path: Path) -> None:
    names = build_run_names(_spec(tmp_path).run_id, _TOKEN)

    argv = build_network_create_argv(_BACKEND, names)

    assert argv == (str(_BACKEND), "network", "create", "--internal", names.network)


def test_only_the_sidecar_is_joined_to_the_egress_network(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    names = build_run_names(spec.run_id, _TOKEN)

    argv = build_network_connect_argv(_BACKEND, spec, names)

    assert argv[1:] == (
        "network",
        "connect",
        names.egress_network,
        names.proxy_container,
    )
    assert names.harness_container not in argv


def test_the_egress_network_is_per_run_unless_a_host_network_is_named(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    names = build_run_names(spec.run_id, _TOKEN)

    # Default: a fresh routable network nothing else is attached to, so no other
    # local container can relay through the sidecar for the life of the run.
    assert egress_network_name(spec, names) == f"lfb-cycle1-claude-code-{_TOKEN}-out"
    assert build_egress_network_create_argv(_BACKEND, names) == (
        str(_BACKEND),
        "network",
        "create",
        names.egress_network,
    )
    assert "--internal" not in build_egress_network_create_argv(_BACKEND, names)

    named = _spec(tmp_path, egress_network="corp-egress")
    assert egress_network_name(named, names) == "corp-egress"
    assert build_network_connect_argv(_BACKEND, named, names)[3] == "corp-egress"


def test_proxy_argv_carries_the_allowlist_and_bind_mounts_the_single_file(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path, allow_subdomains=("anthropic.com",), allow_ports=(443,))
    names = build_run_names(spec.run_id, _TOKEN)
    evidence = tmp_path / "egress"

    argv = build_proxy_run_argv(
        _BACKEND,
        spec,
        names,
        proxy_source=Path("/srv/egress_proxy.py"),
        evidence_directory=evidence,
    )

    assert _flag_values(argv, "--allow-host") == [
        "api.anthropic.com",
        "console.anthropic.com",
    ]
    assert _flag_values(argv, "--allow-subdomains") == ["anthropic.com"]
    assert _flag_values(argv, "--allow-port") == ["443"]
    assert _flag_values(argv, "--network") == [names.network]
    assert "--pull=never" in argv
    assert "--read-only" in argv
    assert _flag_values(argv, "--cap-drop") == ["ALL"]
    assert _flag_values(argv, "--security-opt") == ["no-new-privileges"]
    assert f"type=bind,src=/srv/egress_proxy.py,dst={PROXY_SOURCE_TARGET},readonly" in (
        argv
    )
    assert f"type=bind,src={evidence},dst=/var/legalforecast-egress" in argv
    assert _flag_values(argv, "--evidence-file") == [PROXY_EVIDENCE_TARGET]


def test_harness_argv_never_disables_the_network_and_keeps_the_isolation_flags(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    names = build_run_names(spec.run_id, _TOKEN)
    credential_home = tmp_path / "home"

    argv = build_harness_run_argv(
        _BACKEND,
        spec,
        names,
        credential_home=credential_home,
        cidfile=tmp_path / "harness.cid",
    )

    assert "--network=none" not in argv
    assert _flag_values(argv, "--network") == [names.network]
    assert names.egress_network not in argv
    assert "--pull=never" in argv
    assert "--read-only" in argv
    assert _flag_values(argv, "--security-opt") == ["no-new-privileges"]
    assert _flag_values(argv, "--cap-drop") == ["ALL"]
    assert _flag_values(argv, "--pids-limit") == ["512"]
    assert _flag_values(argv, "--memory") == ["4g"]
    assert "--cpus=2" in argv
    assert _flag_values(argv, "--workdir") == [WORKSPACE_TARGET]
    assert argv[-len(spec.harness_argv) :] == spec.harness_argv
    assert argv[-len(spec.harness_argv) - 1] == _IMAGE


def test_the_harness_entrypoint_is_always_the_fence_wrapper(tmp_path: Path) -> None:
    spec = _spec(tmp_path, harness_entrypoint="claude")
    names = build_run_names(spec.run_id, _TOKEN)

    argv = build_harness_run_argv(
        _BACKEND,
        spec,
        names,
        credential_home=tmp_path / "home",
        cidfile=tmp_path / "harness.cid",
    )

    assert _flag_values(argv, "--entrypoint") == [
        "/opt/legalforecast/bin/lfb-cli-fence"
    ]
    assert _flag_values(
        build_harness_run_argv(
            _BACKEND,
            _spec(tmp_path),
            names,
            credential_home=tmp_path / "home",
            cidfile=tmp_path / "harness.cid",
        ),
        "--entrypoint",
    ) == ["/opt/legalforecast/bin/lfb-cli-fence"]


def test_workspace_credentials_and_fence_are_the_only_bind_mounts(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    names = build_run_names(spec.run_id, _TOKEN)
    credential_home = tmp_path / "home"

    mounts = _flag_values(
        build_harness_run_argv(
            _BACKEND,
            spec,
            names,
            credential_home=credential_home,
            cidfile=tmp_path / "harness.cid",
        ),
        "--mount",
    )

    assert mounts[0] == f"type=bind,src={spec.workspace},dst={WORKSPACE_TARGET}"
    assert (
        f"type=bind,src={credential_home},dst=/run/legalforecast/credentials,readonly"
        in mounts
    )
    assert any(item.endswith("/lfb-cli-fence,readonly") for item in mounts)
    assert any(item.endswith("/bin/claude,readonly") for item in mounts)
    assert not any(
        "dst=/home/harness" in item and "readonly" not in item for item in mounts
    )


def test_child_environment_is_clean_and_points_at_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "must-not-leak")
    spec = _spec(tmp_path, environment={"CODEX_HOME": "/home/harness/.codex"})
    names = build_run_names(spec.run_id, _TOKEN)

    environment = build_harness_environment(spec, names)

    proxy_url = f"http://{names.proxy_container}:3128"
    assert environment["HOME"] == "/home/harness"
    assert environment["CODEX_HOME"] == "/home/harness/.codex"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        assert environment[name] == proxy_url
    assert environment["NO_PROXY"] == "localhost,127.0.0.1,::1"
    assert "ANTHROPIC_API_KEY" not in environment
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in environment
    assert environment["PATH"].startswith("/opt/legalforecast/bin:")
    assert environment["LFB_HARNESS_CLI"] == "claude"
    assert "LFB_HARNESS_REAL_BIN" not in environment


def test_environment_reaches_the_container_only_through_explicit_env_flags(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path, environment={"CODEX_HOME": "/home/harness/.codex"})
    names = build_run_names(spec.run_id, _TOKEN)

    argv = build_harness_run_argv(
        _BACKEND,
        spec,
        names,
        credential_home=tmp_path / "home",
        cidfile=tmp_path / "harness.cid",
    )

    assert sorted(_flag_values(argv, "--env")) == sorted(
        f"{name}={value}"
        for name, value in build_harness_environment(spec, names).items()
    )


def test_credentials_are_copied_into_a_fresh_0700_home(tmp_path: Path) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text('{"token": "original"}', encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude/.creds"),
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )

    home = stage_credential_home(tmp_path / "staging", spec)

    copied = home / ".claude/.creds"
    assert copied.read_text(encoding="utf-8") == '{"token": "original"}'
    assert not copied.is_symlink()
    assert stat.S_IMODE(copied.stat().st_mode) == 0o600
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert (home / ".claude.json").is_file()

    copied.write_text('{"token": "refreshed"}', encoding="utf-8")
    assert source.read_text(encoding="utf-8") == '{"token": "original"}'


def test_credential_bytes_never_appear_on_the_docker_command_line(
    tmp_path: Path,
) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text(_SECRET, encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )
    names = build_run_names(spec.run_id, _TOKEN)
    home = stage_credential_home(tmp_path / "staging", spec)

    argv = build_harness_run_argv(
        _BACKEND,
        spec,
        names,
        credential_home=home,
        cidfile=tmp_path / "harness.cid",
    )
    joined = "\0".join(argv)

    assert _SECRET not in joined
    assert str(source) not in joined
    assert "--env" not in argv or all(
        _SECRET not in value for value in _flag_values(argv, "--env")
    )


def test_credential_paths_must_stay_inside_the_container_home(tmp_path: Path) -> None:
    source = tmp_path / "creds.json"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ContainerHarnessError, match="traversal"):
        HarnessCredential(host_path=source, home_relative_path="../escape")
    with pytest.raises(ContainerHarnessError, match="relative to the container HOME"):
        HarnessCredential(host_path=source, home_relative_path="/etc/shadow")
    with pytest.raises(ContainerHarnessError, match="absolute"):
        HarnessCredential(host_path=Path("creds.json"), home_relative_path="a")


def test_a_missing_credential_fails_before_the_container_starts(
    tmp_path: Path,
) -> None:
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(
                host_path=tmp_path / "absent.json", home_relative_path=".creds"
            ),
        ),
    )

    with pytest.raises(ContainerHarnessError, match="not a regular file"):
        stage_credential_home(tmp_path / "staging", spec)


def test_the_bind_mounted_proxy_source_is_a_real_single_file() -> None:
    source = egress_proxy_source_path()

    assert source.is_file()
    assert source.name == "egress_proxy.py"
    assert "import legalforecast" not in source.read_text(encoding="utf-8")


def test_result_record_carries_counts_but_no_attacker_controlled_hosts(
    tmp_path: Path,
) -> None:
    result = ContainerHarnessResult(
        run_id="cycle1-claude-code",
        exit_code=0,
        timed_out=False,
        duration_seconds=12.3456,
        stdout_path=tmp_path / "run.stdout",
        stderr_path=tmp_path / "run.stderr",
        image_id="sha256:" + "a" * 64,
        proxy_image_id="sha256:" + "a" * 64,
        allowed_hosts=("api.anthropic.com",),
        refused=({"host": "courtlistener.com", "port": 443, "reason": "x"},),
        allowlist={"hosts": ["api.anthropic.com"], "ports": [443]},
    )

    record = result.to_record()

    assert record["egress_allowed_host_count"] == 1
    assert record["egress_refused_count"] == 1
    assert "courtlistener.com" not in repr(record)
    assert record["duration_seconds"] == 12.346
    assert record["stdout_file"] == "run.stdout"
    assert str(tmp_path) not in repr(record)

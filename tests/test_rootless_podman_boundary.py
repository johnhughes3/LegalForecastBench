# pyright: reportPrivateUsage=false
"""Rootless Podman boundary for the community native Codex solver."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness import rootless_podman_boundary as podman_boundary
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    SubscriptionRuntimeAccess,
)
from legalforecast.multiharness.community_subscription_sandbox import (
    CODEX_COMMUNITY_PERMISSION_PROFILE,
    codex_permissions_override,
)
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    CommunitySubscriptionOperatorRequest,
    _run_codex_native_sandbox_canary,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

_EXPECTED_CODEX_SHA256 = (
    "cdcb45aaa01d0f14e298985e09465aebccd47f64ecd298aea44814af7b62bbda"
)


def _roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    executable = tmp_path / "bin" / "codex"
    executable.parent.mkdir()
    executable.write_bytes(b"fixture")
    executable.chmod(0o700)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    projection = tmp_path / "projection"
    for directory in (workspace, auth, projection):
        directory.mkdir()
    return executable, workspace, auth, projection


def _backend_double(_backend: str) -> tuple[Path, dict[str, str]]:
    return Path("/usr/bin/podman"), {"PATH": "/usr/bin"}


def test_plan_uses_exact_mounts_rootless_network_and_truthful_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)
    monkeypatch.setattr(
        podman_boundary,
        "resolve_rootless_backend",
        _backend_double,
    )

    launch = podman_boundary.prepare_rootless_podman_boundary(
        (str(executable), "exec", "--help"),
        execution_cwd=workspace,
        executable=executable,
        read_paths=(projection,),
        write_paths=(workspace, auth),
        container_environment={
            "CODEX_HOME": str(auth),
            "HOME": str(workspace),
            "PATH": "/host/private/bin:/usr/bin",
            "OPENAI_API_KEY": "must-not-pass",
        },
    )
    try:
        argv = launch.argv
        assert argv[:5] == (
            "/usr/bin/podman",
            "run",
            "--interactive",
            "--rm",
            "--cidfile",
        )
        assert "--rootfs" in argv
        assert "--read-only" in argv
        assert "--network" not in argv
        assert "--userns=keep-id" in argv
        assert "--cap-drop=ALL" in argv
        assert "/tmp:rw,nosuid,nodev,mode=1777" in argv
        mounts = [
            argv[index + 1] for index, token in enumerate(argv) if token == "--mount"
        ]
        assert (
            f"type=bind,source={executable},destination={executable},ro=true" in mounts
        )
        assert f"type=bind,source={workspace},destination={workspace},rw=true" in mounts
        assert f"type=bind,source={auth},destination={auth},rw=true" in mounts
        assert (
            f"type=bind,source={projection},destination={projection},ro=true" in mounts
        )
        ca_bundle = Path("/etc/ssl/certs/ca-certificates.crt")
        assert f"type=bind,source={ca_bundle},destination={ca_bundle},ro=true" in mounts
        assert not any("/proc" in mount for mount in mounts)
        assert not any(
            mount.startswith("type=bind,source=/tmp,destination=/tmp")
            for mount in mounts
        )
        assert "--privileged" not in argv
        assert "security-opt=unconfined" not in " ".join(argv)
        assert not any(
            "podman.sock" in token or "docker.sock" in token for token in argv
        )
        assert "OPENAI_API_KEY=must-not-pass" not in argv
        assert "PATH=/host/private/bin:/usr/bin" not in argv
        assert launch.environment == {"PATH": "/usr/bin"}
        assert launch.boundary_identity == {
            "policy_id": podman_boundary.CONTRIBUTOR_ROOTLESS_PODMAN_BOUNDARY,
            "filesystem_scope": podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
            "backend": "podman",
            "host_process_containment": "posix_process_group.v1",
            "isolated_environment": True,
            "transcript_redaction": True,
            "root_filesystem": "read_only",
            "network": "rootless_default",
            "user_namespace": "keep-id",
            "cap_drop": ["ALL"],
        }
        launch.revalidate()
    finally:
        control_root = launch.control_root
        launch.close()
    assert not control_root.exists()


def test_plan_rejects_ancestor_symlink_and_mount_option_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)
    monkeypatch.setattr(
        podman_boundary,
        "resolve_rootless_backend",
        _backend_double,
    )
    alias = tmp_path / "workspace-alias"
    alias.symlink_to(workspace, target_is_directory=True)

    with pytest.raises(
        podman_boundary.RootlessPodmanBoundaryError,
        match="symlink components",
    ):
        podman_boundary.prepare_rootless_podman_boundary(
            (str(executable),),
            execution_cwd=alias,
            executable=executable,
            read_paths=(projection,),
            write_paths=(workspace, auth),
            container_environment={"CODEX_HOME": str(auth)},
        )

    with pytest.raises(
        podman_boundary.RootlessPodmanBoundaryError,
        match="ancestor of the Codex auth root",
    ):
        podman_boundary.prepare_rootless_podman_boundary(
            (str(executable),),
            execution_cwd=workspace,
            executable=executable,
            read_paths=(tmp_path,),
            write_paths=(workspace, auth),
            container_environment={"CODEX_HOME": str(auth)},
        )

    comma_path = tmp_path / "projection,escaped"
    comma_path.mkdir()
    with pytest.raises(
        podman_boundary.RootlessPodmanBoundaryError,
        match="unsafe mount-option",
    ):
        podman_boundary.prepare_rootless_podman_boundary(
            (str(executable),),
            execution_cwd=workspace,
            executable=executable,
            read_paths=(comma_path,),
            write_paths=(workspace, auth),
            container_environment={"CODEX_HOME": str(auth)},
        )


def test_revalidation_rejects_source_inode_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)
    monkeypatch.setattr(
        podman_boundary,
        "resolve_rootless_backend",
        _backend_double,
    )
    launch = podman_boundary.prepare_rootless_podman_boundary(
        (str(executable),),
        execution_cwd=workspace,
        executable=executable,
        read_paths=(projection,),
        write_paths=(workspace, auth),
        container_environment={"CODEX_HOME": str(auth)},
    )
    moved = tmp_path / "projection-original"
    projection.rename(moved)
    projection.mkdir()
    try:
        with pytest.raises(
            podman_boundary.RootlessPodmanBoundaryError,
            match="changed before launch",
        ):
            launch.revalidate()
    finally:
        launch.close()


def test_backend_absence_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)

    def unavailable(_backend: str) -> tuple[Path, dict[str, str]]:
        raise RuntimeError("missing")

    monkeypatch.setattr(podman_boundary, "resolve_rootless_backend", unavailable)
    with pytest.raises(
        podman_boundary.RootlessPodmanBoundaryError,
        match="rootless Podman backend is unavailable",
    ):
        podman_boundary.prepare_rootless_podman_boundary(
            (str(executable),),
            execution_cwd=workspace,
            executable=executable,
            read_paths=(projection,),
            write_paths=(workspace, auth),
            container_environment={"CODEX_HOME": str(auth)},
        )


def test_scope_validation_is_exact() -> None:
    assert (
        podman_boundary.require_rootless_podman_scope(
            podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE
        )
        == podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE
    )
    with pytest.raises(
        podman_boundary.RootlessPodmanBoundaryError,
        match="filesystem_scope",
    ):
        podman_boundary.require_rootless_podman_scope("linux_landlock_fs.v1")


def test_system_mount_sources_are_resolved_without_host_proc() -> None:
    mounts = podman_boundary.system_read_mounts()
    assert [target for _source, target in mounts] == [
        Path("/usr"),
        Path("/bin"),
        Path("/lib"),
        Path("/lib64"),
    ]
    assert all(source.is_absolute() for source, _target in mounts)
    assert all("/proc" not in str(source) for source, _target in mounts)
    if os.path.islink("/bin"):
        assert mounts[1][0] == Path("/bin").resolve(strict=True)


@pytest.mark.skipif(
    os.environ.get("LFB_CODEX_PODMAN_E2E") != "1",
    reason="set LFB_CODEX_PODMAN_E2E=1 for the rootless Codex boundary test",
)
def test_actual_shared_executor_preserves_parent_and_native_boundaries(
    tmp_path: Path,
) -> None:
    located = shutil.which("codex")
    if located is None:
        pytest.fail("the explicitly enabled test requires Codex")
    executable = Path(located).resolve(strict=True)
    pin = executable_pin_for(
        executable,
        version="codex-cli 0.167.0",
        distribution_kind="standalone-cli",
    )
    assert pin.sha256 == _EXPECTED_CODEX_SHA256

    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    evaluator_private = tmp_path / "evaluator-private"
    for directory in (workspace, auth, evaluator_private):
        directory.mkdir(mode=0o700)
    auth_canary = auth / "auth.json"
    private_canary = evaluator_private / "rubric"
    auth_canary.write_text("synthetic-auth-canary", encoding="utf-8")
    private_canary.write_text("synthetic-private-canary", encoding="utf-8")
    auth_canary.chmod(0o600)
    private_canary.chmod(0o600)
    auth_before = auth_canary.read_bytes()
    private_before = private_canary.read_bytes()
    (workspace / "auth-link").symlink_to(auth, target_is_directory=True)
    (workspace / "private-link").symlink_to(
        evaluator_private,
        target_is_directory=True,
    )

    class SyntheticPresence:
        def prove(self, parent_env: object) -> SubscriptionRuntimeAccess:
            del parent_env
            return SubscriptionRuntimeAccess(
                environment=(("CODEX_HOME", str(auth)),),
                read_paths=(auth,),
                write_paths=(auth,),
            )

    permissions = codex_permissions_override(auth, executable)
    probe = (
        "printf ok > output; "
        'if cat "$1"; then exit 91; fi; '
        'if printf bad > "$1"; then exit 92; fi; '
        "if cat auth-link/auth.json; then exit 93; fi; "
        "if printf bad > auth-link/auth.json; then exit 94; fi; "
        'if cat "$2"; then exit 95; fi; '
        'if printf bad > "$2"; then exit 96; fi; '
        "if cat private-link/rubric; then exit 97; fi; "
        "if printf bad > private-link/rubric; then exit 98; fi; "
        'if cat "/proc/self/root$1"; then exit 99; fi; '
        'if printf bad > "/proc/self/root$1"; then exit 100; fi; '
        'if cat "/proc/1/root$2"; then exit 101; fi; '
        'if printf bad > "/proc/1/root$2"; then exit 102; fi; '
        'test "$(cat output)" = ok'
    )
    service = LocalCliExecutionService(
        adapter_id="codex-podman-e2e",
        display_name="Codex Podman E2E",
        adapter_version="0.167.0",
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
        executable_pin=pin,
        parent_env={"PATH": f"{executable.parent}:/usr/bin:/bin"},
        filesystem_scope=podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
        subscription_presence=SyntheticPresence(),
        filesystem_write_paths=(workspace,),
        run_in_working_directory=True,
    )
    receipt = service.execute(
        RunSpec(
            spec_id="codex-podman-native-boundary",
            argv=(
                "codex",
                "--cd",
                str(workspace),
                "-c",
                f'default_permissions="{CODEX_COMMUNITY_PERMISSION_PROFILE}"',
                "-c",
                permissions,
                "sandbox",
                "/bin/sh",
                "-c",
                probe,
                "probe",
                str(auth_canary),
                str(private_canary),
            ),
            working_directory=workspace,
            environment={},
            timeout_seconds=30,
        )
    )

    assert receipt.status == "succeeded", receipt.stderr
    assert (workspace / "output").read_text(encoding="utf-8") == "ok"
    assert auth_canary.read_bytes() == auth_before
    assert private_canary.read_bytes() == private_before
    assert receipt.returncode == 0
    _run_codex_native_sandbox_canary(
        CommunitySubscriptionOperatorRequest(
            source_root=tmp_path / "source",
            projection_root=tmp_path / "projection",
            evaluator_private_root=evaluator_private,
            run_root=tmp_path / "run",
            evaluator_bin_dir=executable.parent,
            solver_config_dir=auth,
            judge_config_dir=tmp_path / "judge-auth",
            claude_version="unused",
            claude_sha256="0" * 64,
            solver_model="unused",
            judge_model="unused",
            harness="codex",
            codex_version="codex-cli 0.167.0",
            codex_sha256=_EXPECTED_CODEX_SHA256,
        ),
        service,
    )


@pytest.mark.skipif(
    os.environ.get("LFB_CODEX_PODMAN_E2E") != "1",
    reason="set LFB_CODEX_PODMAN_E2E=1 for the rootless Podman boundary test",
)
def test_actual_outer_parent_sees_only_auth_and_workspace(tmp_path: Path) -> None:
    shell = Path("/bin/sh").resolve(strict=True)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    evaluator_private = tmp_path / "evaluator-private"
    for directory in (workspace, auth, evaluator_private):
        directory.mkdir(mode=0o700)
    auth_canary = auth / "auth.json"
    private_canary = evaluator_private / "rubric"
    auth_canary.write_text("auth", encoding="utf-8")
    private_canary.write_text("private", encoding="utf-8")
    private_before = private_canary.read_bytes()
    (workspace / "private-link").symlink_to(
        evaluator_private,
        target_is_directory=True,
    )
    command = (
        str(shell),
        "-c",
        'cat "$1" >/dev/null; printf parent-ok > "$2"; '
        "printf workspace-ok > workspace-output; "
        'if cat "$3"; then exit 91; fi; '
        'if printf bad > "$3"; then exit 92; fi; '
        "if cat private-link/rubric; then exit 93; fi; "
        'if cat "/proc/self/root$3"; then exit 94; fi; '
        'if printf bad > "/proc/self/root$3"; then exit 95; fi; '
        'if cat "/proc/1/root$3"; then exit 96; fi; '
        'if printf bad > "/proc/1/root$3"; then exit 97; fi; '
        "mkdir escape; "
        'if mount --bind "$1" escape; then exit 98; fi; '
        "if unshare --mount /bin/true; then exit 99; fi; "
        "test ! -e /run/podman/podman.sock; "
        "test ! -e /run/docker.sock; test ! -e /dev/fuse",
        "probe",
        str(auth_canary),
        str(auth / "parent-output"),
        str(private_canary),
    )
    launch = podman_boundary.prepare_rootless_podman_boundary(
        command,
        execution_cwd=workspace,
        executable=shell,
        read_paths=(auth,),
        write_paths=(workspace, auth),
        container_environment={"CODEX_HOME": str(auth)},
    )
    try:
        launch.revalidate()
        completed = subprocess.run(
            launch.argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=30,
            env=launch.environment,
        )
    finally:
        launch.close()
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert (auth / "parent-output").read_text(encoding="utf-8") == "parent-ok"
    assert (workspace / "workspace-output").read_text(encoding="utf-8") == (
        "workspace-ok"
    )
    assert private_canary.read_bytes() == private_before

# pyright: reportPrivateUsage=false
"""Lifecycle enforcement for the rootless Podman filesystem boundary."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from legalforecast.multiharness import local_cli_runtime as local_runtime
from legalforecast.multiharness import rootless_podman_boundary as podman_boundary
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    SubscriptionRuntimeAccess,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService


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


class _LaunchDouble:
    def __init__(self, argv: tuple[str, ...], *, cleanup_fails: bool = False) -> None:
        self.argv = argv
        self.environment = {"PATH": "/usr/bin:/bin"}
        self.boundary_identity = {"backend": "podman"}
        self.events: list[str] = []
        self.cleanup_fails = cleanup_fails

    def revalidate(self) -> None:
        self.events.append("revalidate")

    def mark_spawn_attempted(self) -> None:
        self.events.append("spawn-attempted")

    def require_container_revalidation(self) -> None:
        self.events.append("require-container-revalidation")

    def terminate_container(self) -> None:
        self.events.append("terminate-container")
        if self.cleanup_fails:
            raise podman_boundary.RootlessPodmanBoundaryError(
                "rootless Podman container cleanup failed"
            )

    def close(self) -> None:
        self.events.append("close")


class _SyntheticPresence:
    def __init__(self, auth: Path) -> None:
        self.auth = auth

    def prove(self, parent_env: object) -> SubscriptionRuntimeAccess:
        del parent_env
        return SubscriptionRuntimeAccess(
            environment=(("CODEX_HOME", str(self.auth)),),
            read_paths=(self.auth,),
            write_paths=(self.auth,),
        )


def test_container_termination_uses_zero_grace_and_verifies_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)
    monkeypatch.setattr(podman_boundary, "resolve_rootless_backend", _backend_double)
    launch = podman_boundary.prepare_rootless_podman_boundary(
        (str(executable),),
        execution_cwd=workspace,
        executable=executable,
        read_paths=(projection,),
        write_paths=(workspace, auth),
        container_environment={"CODEX_HOME": str(auth)},
    )
    calls: list[tuple[str, ...]] = []

    def completed(
        command: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1 if command[1:3] == ("container", "exists") else 0,
            b"",
            b"",
        )

    monkeypatch.setattr(podman_boundary.subprocess, "run", completed)
    try:
        launch.mark_spawn_attempted()
        launch.terminate_container()
        name = launch.argv[launch.argv.index("--name") + 1]
        assert calls == [
            ("/usr/bin/podman", "stop", "--time=0", "--ignore", name),
            ("/usr/bin/podman", "rm", "--force", "--ignore", name),
            ("/usr/bin/podman", "container", "exists", name),
        ]
    finally:
        launch._spawn_attempted = False
        launch.close()


def test_container_cleanup_failure_is_fail_closed_and_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, workspace, auth, projection = _roots(tmp_path)
    monkeypatch.setattr(podman_boundary, "resolve_rootless_backend", _backend_double)
    launch = podman_boundary.prepare_rootless_podman_boundary(
        (str(executable),),
        execution_cwd=workspace,
        executable=executable,
        read_paths=(projection,),
        write_paths=(workspace, auth),
        container_environment={"CODEX_HOME": str(auth)},
    )

    def failed_stop(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        if command[1] == "stop":
            return subprocess.CompletedProcess(command, 125, b"", b"failed")
        return subprocess.CompletedProcess(
            command,
            1 if command[1:3] == ("container", "exists") else 0,
            b"",
            b"",
        )

    monkeypatch.setattr(podman_boundary.subprocess, "run", failed_stop)
    try:
        launch.mark_spawn_attempted()
        with pytest.raises(
            podman_boundary.RootlessPodmanBoundaryError,
            match="container cleanup failed",
        ):
            launch.terminate_container()
    finally:
        launch._spawn_attempted = False
        launch.close()


def test_shared_executor_surfaces_container_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    located = shutil.which("true")
    assert located is not None
    executable = Path(located).resolve(strict=True)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    workspace.mkdir(mode=0o700)
    auth.mkdir(mode=0o700)
    launch = _LaunchDouble((str(executable),), cleanup_fails=True)

    def prepared_launch(_argv: tuple[str, ...], **_kwargs: object) -> _LaunchDouble:
        return launch

    monkeypatch.setattr(
        podman_boundary,
        "prepare_rootless_podman_boundary",
        prepared_launch,
    )
    receipt = LocalCliExecutionService(
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
        executable_pin=executable_pin_for(executable, version="fixture"),
        parent_env={"PATH": f"{executable.parent}:/usr/bin:/bin"},
        filesystem_scope=podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
        subscription_presence=_SyntheticPresence(auth),
        filesystem_write_paths=(workspace,),
        run_in_working_directory=True,
    ).execute(
        RunSpec(
            spec_id="podman-cleanup-failure",
            argv=(executable.name,),
            working_directory=workspace,
            timeout_seconds=5,
        )
    )

    assert receipt.status == "failed"
    assert receipt.stderr == "rootless Podman container cleanup failed"
    assert launch.events.count("terminate-container") == 2
    assert launch.events[-1] == "close"


def test_shared_executor_interrupt_terminates_and_rechecks_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    located = shutil.which("sleep")
    assert located is not None
    executable = Path(located).resolve(strict=True)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    workspace.mkdir(mode=0o700)
    auth.mkdir(mode=0o700)
    launch = _LaunchDouble((str(executable), "30"))

    def prepared_launch(_argv: tuple[str, ...], **_kwargs: object) -> _LaunchDouble:
        return launch

    monkeypatch.setattr(
        podman_boundary,
        "prepare_rootless_podman_boundary",
        prepared_launch,
    )

    def interrupt_wait(*_args: object, **_kwargs: object) -> tuple[int, bool, bool]:
        raise KeyboardInterrupt

    monkeypatch.setattr(local_runtime, "_wait_for_contained_process", interrupt_wait)
    service = LocalCliExecutionService(
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
        executable_pin=executable_pin_for(executable, version="fixture"),
        parent_env={"PATH": f"{executable.parent}:/usr/bin:/bin"},
        termination_grace_seconds=0.1,
        filesystem_scope=podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
        subscription_presence=_SyntheticPresence(auth),
        filesystem_write_paths=(workspace,),
        run_in_working_directory=True,
    )
    with pytest.raises(KeyboardInterrupt):
        service.execute(
            RunSpec(
                spec_id="podman-interrupted",
                argv=(executable.name, "30"),
                working_directory=workspace,
                timeout_seconds=5,
            )
        )

    assert launch.events == [
        "revalidate",
        "spawn-attempted",
        "terminate-container",
        "require-container-revalidation",
        "terminate-container",
        "close",
    ]


@pytest.mark.skipif(
    os.environ.get("LFB_CODEX_PODMAN_E2E") != "1",
    reason="set LFB_CODEX_PODMAN_E2E=1 for the rootless Podman boundary test",
)
def test_actual_shared_executor_stops_oci_workload_at_timeout(
    tmp_path: Path,
) -> None:
    located = shutil.which("dash")
    if located is None:
        pytest.fail("the explicitly enabled test requires dash")
    executable = Path(located).resolve(strict=True)
    workspace = tmp_path / "workspace"
    auth = tmp_path / "auth"
    workspace.mkdir(mode=0o700)
    auth.mkdir(mode=0o700)
    workspace_after_deadline = workspace / "post-deadline"
    auth_after_deadline = auth / "post-deadline"
    service = LocalCliExecutionService(
        adapter_id="podman-timeout-e2e",
        display_name="Podman timeout E2E",
        adapter_version="fixture",
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
        executable_pin=executable_pin_for(executable, version="fixture"),
        parent_env={"PATH": f"{executable.parent}:/usr/bin:/bin"},
        termination_grace_seconds=0.2,
        filesystem_scope=podman_boundary.ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
        subscription_presence=_SyntheticPresence(auth),
        filesystem_write_paths=(workspace,),
        run_in_working_directory=True,
    )
    started = time.monotonic()
    receipt = service.execute(
        RunSpec(
            spec_id="podman-timeout-no-post-deadline-writes",
            argv=(
                executable.name,
                "-c",
                'sleep 2; printf bad > "$1"; printf bad > "$2"; sleep 30',
                "probe",
                str(workspace_after_deadline),
                str(auth_after_deadline),
            ),
            working_directory=workspace,
            timeout_seconds=0.2,
        )
    )
    elapsed = time.monotonic() - started

    assert receipt.status == "timeout", receipt.stderr
    assert elapsed < 1.5
    time.sleep(2)
    assert not workspace_after_deadline.exists()
    assert not auth_after_deadline.exists()

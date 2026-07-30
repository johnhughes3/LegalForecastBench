from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import legalforecast.multiharness.host_environment as host_environment_module
import pytest


def test_container_backend_environment_omits_provider_and_home_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_directory = tmp_path / "runtime"
    runtime_directory.mkdir(mode=0o700)
    socket_path = runtime_directory / "docker.sock"
    backend_socket = socket.socket(socket.AF_UNIX)
    backend_socket.bind(str(socket_path))
    try:
        monkeypatch.setenv("PATH", "/usr/bin")
        monkeypatch.setenv("LC_CTYPE", "C.UTF-8")
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_directory))
        monkeypatch.setenv("DOCKER_HOST", f"unix://{socket_path}")
        monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-backend")
        monkeypatch.setenv("HOME", "/private/operator-home")

        environment = host_environment_module.build_container_backend_environment()
    finally:
        backend_socket.close()

    assert environment == {
        "PATH": "/usr/bin",
        "LC_CTYPE": "C.UTF-8",
        "XDG_RUNTIME_DIR": str(runtime_directory),
        "DOCKER_HOST": f"unix://{socket_path}",
    }


def test_container_backend_environment_rejects_remote_docker_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_directory = tmp_path / "runtime"
    runtime_directory.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_directory))
    monkeypatch.setenv("DOCKER_HOST", "tcp://container-host.example:2376")

    with pytest.raises(
        host_environment_module.HostEnvironmentError,
        match="local Unix socket",
    ):
        host_environment_module.build_container_backend_environment()


def test_container_backend_environment_rejects_symlinked_runtime_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(linked))
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    with pytest.raises(
        host_environment_module.HostEnvironmentError, match="non-symlink"
    ):
        host_environment_module.build_container_backend_environment()


def test_container_backend_environment_rejects_writable_runtime_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_directory = tmp_path / "runtime"
    runtime_directory.mkdir(mode=0o777)
    runtime_directory.chmod(0o777)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_directory))
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    with pytest.raises(
        host_environment_module.HostEnvironmentError,
        match="group or world writable",
    ):
        host_environment_module.build_container_backend_environment()


@pytest.mark.parametrize(
    ("backend", "stdout"),
    (
        ("docker", b'["name=seccomp","name=rootless"]\n'),
        ("podman", b"true\n"),
    ),
)
def test_rootless_backend_preflight_is_value_free(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    stdout: bytes,
) -> None:
    calls: list[tuple[str, ...]] = []

    def _run(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=b"")

    monkeypatch.setattr(host_environment_module.subprocess, "run", _run)

    host_environment_module.require_rootless_container_daemon(
        Path("/usr/bin/true"),
        backend,
        {"PATH": ""},
    )

    assert calls
    assert all("secret" not in argument.lower() for argument in calls[0])


def test_rootless_backend_preflight_rejects_rootful_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        host_environment_module.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout=b'["name=seccomp"]\n',
            stderr=b"",
        ),
    )

    with pytest.raises(host_environment_module.HostEnvironmentError, match="rootless"):
        host_environment_module.require_rootless_container_daemon(
            Path("/usr/bin/true"),
            "docker",
            {"PATH": ""},
        )


def test_local_pinned_image_preflight_checks_exact_image_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = "sha256:" + "a" * 64
    monkeypatch.setattr(
        host_environment_module.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout=(expected + "\n").encode(),
            stderr=b"",
        ),
    )

    host_environment_module.require_local_pinned_container_image(
        Path("/usr/bin/true"),
        expected,
        {"PATH": ""},
    )

    with pytest.raises(
        host_environment_module.HostEnvironmentError,
        match="does not match",
    ):
        host_environment_module.require_local_pinned_container_image(
            Path("/usr/bin/true"),
            "sha256:" + "b" * 64,
            {"PATH": ""},
        )

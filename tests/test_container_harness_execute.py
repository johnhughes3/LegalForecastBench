"""Execute-path proofs for the fenced container platform, without a live backend.

A fake ``subprocess.run`` stands in for Docker so CI can still assert that
credentials are deleted in ``finally``, never appear on the docker command line,
and that the harness container is not joined to the egress network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.multiharness import container_harness, container_runtime
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessSpec,
    HarnessCredential,
)
from legalforecast.multiharness.container_harness.runtime import (
    STAGING_ROOT_NAME,
    run_container_harness,
)

_IMAGE = "lfb-harness@sha256:" + "a" * 64
_SECRET = "sk-ant-api03-MUST-NOT-APPEAR-ON-ARGV"


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


def test_platform_is_a_new_subpackage_not_the_tool_protocol_runtime() -> None:
    assert Path(container_harness.__file__).parent.name == "container_harness"
    assert Path(container_runtime.__file__).name == "container_runtime.py"
    assert container_harness.__file__ != container_runtime.__file__


def test_no_kimi_harness_is_registered() -> None:
    names = builtin_adapter_registry().known_names()
    assert not any("kimi" in name.lower() for name in names)
    package = Path(container_runtime.__file__).resolve().parent
    kimi_hits = [
        path.as_posix()
        for path in package.rglob("*.py")
        if "kimi" in path.read_text(encoding="utf-8").lower()
    ]
    assert kimi_hits == []


def _install_fake_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fail_on: tuple[str, ...] | None = None,
) -> list[tuple[str, ...]]:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    environment = {"XDG_RUNTIME_DIR": str(runtime_dir), "PATH": "/usr/bin"}
    calls: list[tuple[str, ...]] = []

    def resolve_backend(_backend: str) -> tuple[Path, dict[str, str]]:
        return Path("/usr/bin/docker"), environment

    def resolve_image(_path: Path, _image: str, _env: object) -> str:
        return "sha256:" + "a" * 64

    def fake_run(
        argv: object,
        stdin: object = None,
        stdout: object = None,
        stderr: object = None,
        timeout: object = None,
        check: object = None,
        env: object = None,
    ) -> SimpleNamespace:
        argv_t = tuple(str(item) for item in argv)  # type: ignore[arg-type]
        calls.append(argv_t)
        if fail_on is not None and fail_on == argv_t[1:3]:
            raise OSError("injected backend failure")
        if len(argv_t) >= 2 and argv_t[1] == "logs":
            return SimpleNamespace(returncode=0, stdout=b"3128\n", stderr=b"")
        if "--detach" in argv_t:
            for item in argv_t:
                if item.startswith("type=bind,src=") and item.endswith(
                    ",dst=/var/legalforecast-egress"
                ):
                    source = item.removeprefix("type=bind,src=").split(",", 1)[0]
                    Path(source).mkdir(parents=True, exist_ok=True)
                    (Path(source) / "egress-evidence.json").write_text(
                        json.dumps(
                            {
                                "allowed_hosts": [],
                                "refused": [],
                                "decision_count": 0,
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        "legalforecast.multiharness.container_harness.runtime.resolve_rootless_backend",
        resolve_backend,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_harness.runtime.resolve_local_image_id",
        resolve_image,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.container_harness.runtime.subprocess.run",
        fake_run,
    )
    return calls


def test_failed_setup_deletes_the_credential_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text(_SECRET, encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )
    _install_fake_backend(monkeypatch, tmp_path, fail_on=("network", "create"))

    with pytest.raises(ContainerHarnessError):
        run_container_harness(spec)

    runtime_dir = tmp_path / "runtime"
    leftover = [
        path
        for path in runtime_dir.rglob("*")
        if path.is_file() and _SECRET.encode() in path.read_bytes()
    ]
    assert leftover == []
    assert source.read_text(encoding="utf-8") == _SECRET
    staging = runtime_dir / STAGING_ROOT_NAME
    if staging.exists():
        assert list(staging.iterdir()) == []


def test_mocked_run_puts_the_harness_only_on_the_internal_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text(_SECRET, encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )
    calls = _install_fake_backend(monkeypatch, tmp_path)

    result = run_container_harness(spec)

    assert result.exit_code == 0
    assert result.timed_out is False
    joined = "\n".join(" ".join(call) for call in calls)
    assert _SECRET not in joined
    assert any(call[1:4] == ("network", "create", "--internal") for call in calls)
    harness_runs = [
        call for call in calls if call[1] == "run" and "--detach" not in call
    ]
    assert harness_runs, calls
    harness = harness_runs[0]
    assert "--cap-drop" in harness and "ALL" in harness
    assert "no-new-privileges" in harness
    assert "--read-only" in harness
    connect_calls = [call for call in calls if call[1:3] == ("network", "connect")]
    assert connect_calls
    assert all("-harness" not in " ".join(call) for call in connect_calls)
    staging = tmp_path / "runtime" / STAGING_ROOT_NAME
    if staging.exists():
        assert list(staging.iterdir()) == []
    assert source.read_text(encoding="utf-8") == _SECRET


def test_cleanup_deletes_credentials_when_docker_rm_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "real-credentials.json"
    source.write_text(_SECRET, encoding="utf-8")
    spec = _spec(
        tmp_path,
        credentials=(
            HarnessCredential(host_path=source, home_relative_path=".claude.json"),
        ),
    )
    calls = _install_fake_backend(monkeypatch, tmp_path, fail_on=("rm", "--force"))

    with pytest.raises(ContainerHarnessError):
        run_container_harness(spec)

    rm_calls = [call for call in calls if call[1:3] == ("rm", "--force")]
    network_rms = [call for call in calls if call[1:3] == ("network", "rm")]
    assert len(rm_calls) >= 2
    assert network_rms
    runtime_dir = tmp_path / "runtime"
    leftover = [
        path
        for path in runtime_dir.rglob("*")
        if path.is_file() and _SECRET.encode() in path.read_bytes()
    ]
    assert leftover == []
    staging = runtime_dir / STAGING_ROOT_NAME
    if staging.exists():
        assert list(staging.iterdir()) == []
    assert source.read_text(encoding="utf-8") == _SECRET

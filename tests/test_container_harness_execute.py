"""Execute-path proofs for the fenced container platform, without a live backend.

A fake ``subprocess.run`` stands in for Docker so CI can still assert that
credentials are deleted in ``finally``, never appear on the docker command line,
and that the harness container is not joined to the egress network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import IO, cast

import pytest
from legalforecast.multiharness import container_harness, container_runtime
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    ModelGatewayRequest,
)
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessSpec,
    HarnessCredential,
)
from legalforecast.multiharness.container_harness.publication import (
    DENIED_HOST_PLACEHOLDER,
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
    evidence_payload: dict[str, object] | None = None,
    harness_stdout: bytes = b"",
    gateway_ready: bool = False,
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
            marker = "3128"
            return SimpleNamespace(
                returncode=0, stdout=f"{marker}\n".encode(), stderr=b""
            )
        if len(argv_t) >= 2 and argv_t[1] == "exec":
            return SimpleNamespace(
                returncode=0 if gateway_ready else 1, stdout=b"", stderr=b""
            )
        if "--detach" in argv_t:
            for item in argv_t:
                if item.startswith("type=bind,src=") and item.endswith(
                    ",dst=/var/legalforecast-egress"
                ):
                    source = item.removeprefix("type=bind,src=").split(",", 1)[0]
                    Path(source).mkdir(parents=True, exist_ok=True)
                    payload = evidence_payload or {
                        "allowed_hosts": [],
                        "refused": [],
                        "decision_count": 0,
                    }
                    (Path(source) / "egress-evidence.json").write_text(
                        json.dumps(payload) + "\n",
                        encoding="utf-8",
                    )
                    if "--env-file" in argv_t:
                        gateway_payload = {
                            "schema_version": 1,
                            "request_count": 1,
                            "rejected_count": 0,
                            "accounted_input_tokens": 1,
                            "accounted_output_tokens": 1,
                            "reserved_input_tokens": 0,
                            "reserved_output_tokens": 0,
                            "observed_input_tokens": 1,
                            "observed_output_tokens": 1,
                        }
                        (Path(source) / "gateway-usage.json").write_text(
                            json.dumps(gateway_payload) + "\n",
                            encoding="utf-8",
                        )
        elif len(argv_t) >= 2 and argv_t[1] == "run" and stdout is not None:
            writer = cast(IO[bytes], stdout)
            writer.write(harness_stdout)
            writer.flush()
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


def test_mocked_gateway_run_uses_sidecar_network_and_no_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = ModelGatewayRequest(
        upstream_base_url="http://fixture-upstream:8081",
        model_key="anthropic:claude-sonnet-4",
        run_capability="run-capability",
        upstream_api_key="fixture-upstream-dummy-key",
    )
    spec = _spec(
        tmp_path,
        allow_hosts=("fixture-upstream",),
        allow_ports=(8081,),
        model_gateway=request,
        environment={"ANTHROPIC_API_KEY": "run-capability"},
    )
    transcript = (
        b'{"type":"system","subtype":"init","tools":["Bash"]}\n'
        b'{"type":"result","subtype":"success","is_error":false,}'
        b'"result":"{}"}\n'
    )
    calls = _install_fake_backend(
        monkeypatch,
        tmp_path,
        gateway_ready=True,
        evidence_payload={
            "allowed_hosts": ["fixture-upstream"],
            "refused": [],
            "decision_count": 1,
        },
        harness_stdout=transcript,
    )

    result = run_container_harness(
        spec,
        publication_directory=tmp_path / "published",
    )

    assert result.exit_code == 0
    assert result.gateway_usage is not None
    assert result.gateway_usage["request_count"] == 1
    public_result = json.loads(
        (tmp_path / "published" / "result.json").read_text(encoding="utf-8")
    )
    assert public_result["gateway_usage"]["request_count"] == 1
    detached = [call for call in calls if call[1] == "run" and "--detach" in call]
    assert len(detached) == 1
    gateway = detached[0]
    assert "lfb-model-gateway-ready" not in gateway
    assert "--env-file" in gateway
    assert "egress_proxy.py" not in " ".join(gateway)
    assert any(call[1:3] == ("network", "connect") for call in calls)
    connect = next(call for call in calls if call[1:3] == ("network", "connect"))
    assert "-harness" not in " ".join(connect)
    harness = next(
        call for call in calls if call[1] == "run" and "--detach" not in call
    )
    assert "HTTP_PROXY" not in " ".join(harness)
    assert "HTTPS_PROXY" not in " ".join(harness)
    assert "run-capability" in " ".join(harness)


def test_gateway_usage_is_preserved_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = ModelGatewayRequest(
        upstream_base_url="http://fixture-upstream:8081",
        model_key="anthropic:claude-sonnet-4",
        run_capability="run-capability",
        upstream_api_key="fixture-upstream-dummy-key",
    )
    spec = _spec(
        tmp_path,
        allow_hosts=("fixture-upstream",),
        allow_ports=(8081,),
        model_gateway=request,
        environment={"ANTHROPIC_API_KEY": "run-capability"},
    )
    _install_fake_backend(
        monkeypatch,
        tmp_path,
        fail_on=("rm", "--force"),
        gateway_ready=True,
    )

    with pytest.raises(ContainerHarnessError):
        run_container_harness(spec, publication_directory=tmp_path / "published")

    usage_files = list(spec.log_root.glob("*.gateway-usage.json"))
    assert len(usage_files) == 1
    assert json.loads(usage_files[0].read_text(encoding="utf-8"))["request_count"] == 1
    assert usage_files[0].stat().st_mode & 0o777 == 0o600


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
        run_container_harness(spec, publication_directory=tmp_path / "published")

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
    attacker_host = "attacker-choice.not-allowlisted.test"
    transcript = (
        b'{"type":"system","subtype":"init","tools":["Bash","Read"]}\n'
        b'{"type":"result","usage":{"server_tool_use":'
        b'{"web_search_requests":0,"web_fetch_requests":0}}}\n'
    )
    calls = _install_fake_backend(
        monkeypatch,
        tmp_path,
        evidence_payload={
            "allowed_hosts": ["api.anthropic.com"],
            "refused": [
                {
                    "host": attacker_host,
                    "port": 443,
                    "reason": "host_not_allowlisted",
                }
            ],
            "decision_count": 2,
        },
        harness_stdout=transcript,
    )

    published = tmp_path / "published"
    result = run_container_harness(spec, publication_directory=published)

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
    assert any(
        item.endswith("/run/legalforecast/credentials,readonly") for item in harness
    )
    assert "--entrypoint" in harness
    assert "/opt/legalforecast/bin/lfb-cli-fence" in harness
    connect_calls = [call for call in calls if call[1:3] == ("network", "connect")]
    assert connect_calls
    assert all("-harness" not in " ".join(call) for call in connect_calls)
    staging = tmp_path / "runtime" / STAGING_ROOT_NAME
    if staging.exists():
        assert list(staging.iterdir()) == []
    assert source.read_text(encoding="utf-8") == _SECRET
    public_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(published.iterdir())
    )
    assert attacker_host not in public_text
    proxy = json.loads((published / "proxy-logs.json").read_text(encoding="utf-8"))
    assert proxy["refused"][0]["host"] == DENIED_HOST_PLACEHOLDER
    fence = json.loads((published / "fence.json").read_text(encoding="utf-8"))
    assert fence["server_side_web_tools_disabled"] is True
    assert fence["native_tools_enabled"] is True
    assert fence["parser_fields"]["tools_available"] == ["Bash", "Read"]


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
        run_container_harness(spec, publication_directory=tmp_path / "published")

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

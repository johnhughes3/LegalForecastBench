"""Generic named-adapter registry and CLI discovery (dm0g.4.4.8)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    CODEX_CLI_REGISTRY_NAME,
    HARVEY_LAB_REGISTRY_NAME,
    LFB_NATIVE_REGISTRY_NAME,
    AdapterRegistry,
    AdapterRegistryError,
    builtin_adapter_registry,
)
from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
from legalforecast.multiharness.codex_cli import CodexCliAdapter
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.container_harness.images import ContainerImageError
from legalforecast.multiharness.harness_lane.adapter import (
    ContainerCliAdapter,
    ContainerCliAdapterError,
)
from legalforecast.multiharness.harness_lane.harnesses import (
    CONTAINER_HARNESS_IDENTITIES,
    CONTAINER_TOOLS_ON_REGISTRY_NAMES,
    identity_for_registry_name,
)
from legalforecast.multiharness.harness_lane.preflight import (
    PreflightReport,
    run_preflight,
)
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.spec import (
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SOURCE = ROOT / "legalforecast" / "multiharness" / "adapter_registry.py"
CLI_SOURCE = ROOT / "legalforecast" / "multiharness" / "cli.py"


def test_fixture_adapters_register_and_discover_in_sorted_name_order() -> None:
    registry = AdapterRegistry()
    registry.register("zeta-fixture", LfbNativeAdapter)
    registry.register("alpha-fixture", LfbNativeAdapter)

    assert registry.known_names() == ("alpha-fixture", "zeta-fixture")
    assert isinstance(registry.get("alpha-fixture"), LfbNativeAdapter)
    assert isinstance(registry.get("zeta-fixture"), LfbNativeAdapter)


def test_duplicate_adapter_name_is_refused() -> None:
    registry = AdapterRegistry()
    registry.register("lfb-native", LfbNativeAdapter)

    with pytest.raises(AdapterRegistryError, match="duplicate adapter name"):
        registry.register("lfb-native", LfbNativeAdapter)


def test_unknown_adapter_name_lists_known_names() -> None:
    registry = AdapterRegistry()
    registry.register("zeta-fixture", LfbNativeAdapter)
    registry.register("alpha-fixture", LfbNativeAdapter)

    with pytest.raises(AdapterRegistryError, match="unknown adapter 'no-such'") as exc:
        registry.require_known("no-such")

    message = str(exc.value)
    assert "alpha-fixture" in message
    assert "zeta-fixture" in message
    assert message.index("alpha-fixture") < message.index("zeta-fixture")
    with pytest.raises(AdapterRegistryError, match="unknown adapter 'no-such'"):
        registry.get("no-such")


def test_empty_or_blank_names_are_refused() -> None:
    registry = AdapterRegistry()
    with pytest.raises(AdapterRegistryError, match="adapter name"):
        registry.register("", LfbNativeAdapter)
    with pytest.raises(AdapterRegistryError, match="adapter name"):
        registry.register(" padded ", LfbNativeAdapter)


def test_builtin_registry_is_deterministic_and_includes_local_cli_adapters() -> None:
    first = builtin_adapter_registry()
    second = builtin_adapter_registry()

    assert first.known_names() == second.known_names()
    assert first.known_names() == tuple(sorted(first.known_names()))
    assert first.known_names() == (
        "antigravity-cli-container-tools-on",
        CLAUDE_CODE_REGISTRY_NAME,
        "claude-code-container-tools-on",
        "codex-cli-container-tools-on",
        CODEX_CLI_REGISTRY_NAME,
        "grok-cli-container-tools-on",
        HARVEY_LAB_REGISTRY_NAME,
        "kimi-cli-container-tools-on",
        LFB_NATIVE_REGISTRY_NAME,
    )
    assert isinstance(first.get(LFB_NATIVE_REGISTRY_NAME), LfbNativeAdapter)
    assert isinstance(
        first.get(CLAUDE_CODE_REGISTRY_NAME),
        ClaudeCodeCliAdapter,
    )
    assert isinstance(first.get(CODEX_CLI_REGISTRY_NAME), CodexCliAdapter)


def test_builtin_harvey_lab_requires_lab_command() -> None:
    registry = builtin_adapter_registry()
    with pytest.raises(AdapterRegistryError, match="lab-command"):
        registry.get(HARVEY_LAB_REGISTRY_NAME)


def test_registry_module_has_no_import_time_side_effects() -> None:
    tree = ast.parse(REGISTRY_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    blocked = {
        "legalforecast.multiharness.claude_code",
        "legalforecast.multiharness.codex_cli",
        "legalforecast.multiharness.harness_lane",
        "legalforecast.multiharness.harvey_lab_adapter",
        "legalforecast.multiharness.lfb_native",
        "legalforecast.multiharness.local_cli_runtime",
        "legalforecast.cli",
    }
    assert not any(
        name in blocked or any(name.startswith(f"{prefix}.") for prefix in blocked)
        for name in imported
    )

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            pytest.fail("adapter_registry must not call functions at import time")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "REGISTRY",
                    "DEFAULT_REGISTRY",
                    "_REGISTRY",
                }:
                    pytest.fail("adapter_registry must not populate a module registry")


def test_cli_inspect_uses_registry_instead_of_adapter_name_conditionals() -> None:
    source = CLI_SOURCE.read_text(encoding="utf-8")
    assert "builtin_adapter_registry" in source
    assert 'adapter_name == "lfb-native"' not in source
    assert 'adapter_name == "harvey-lab"' not in source


CONTAINER_IMAGE_DIGEST = "sha256:" + "3b" * 32
SCHEMA_DOC = ROOT / "docs" / "schemas" / "local-cli-adapter-manifest-v1.md"
DOCUMENTED_CONTAINER_EXAMPLE = "example-containerized-tools-on"


def _documented_container_example() -> dict[str, Any]:
    """Return the schema doc's worked containerized manifest.

    Derived from the documentation rather than retyped: ``capability_digest``
    is order-sensitive and already kept in lockstep across four committed
    places, and this lane has no business adding a fifth copy that can drift
    from the example operators are told to start from.
    """

    blocks = re.findall(
        r"```json\n(.*?)```",
        SCHEMA_DOC.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    for block in blocks:
        record = cast(dict[str, Any], json.loads(block))
        if record.get("manifest_id") == DOCUMENTED_CONTAINER_EXAMPLE:
            return record
    raise AssertionError(
        f"the schema doc no longer documents {DOCUMENTED_CONTAINER_EXAMPLE}"
    )


def container_manifest_record(
    *,
    basename: str = "claude",
    manifest_id: str = "claude-code-container-tools-on",
    capabilities: tuple[str, ...] | None = None,
    image: str | None = CONTAINER_IMAGE_DIGEST,
    executable_sha256: str | None = None,
    invocation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind the documented example to one harness, with test-only overrides."""

    record = _documented_container_example()
    record["manifest_id"] = manifest_id
    record["display_name"] = f"{basename} (containerized, native tools on)"
    record["harness_binding"]["adapter_id"] = manifest_id
    record["executable"]["basename"] = basename
    record["executable"].pop("container_image_digest", None)
    if image is not None:
        record["executable"]["container_image_digest"] = image
    if executable_sha256 is not None:
        record["executable"]["sha256"] = executable_sha256
    if capabilities is not None:
        record["capabilities"] = list(capabilities)
    if invocation is not None:
        record["invocation"].update(invocation)
    record["auth_profile_name"] = "contributor-subscription"
    record["supported_auth_profiles"] = ["contributor-subscription", "fixture-none"]
    record["auth_environment_variables"] = [
        {"names": [], "profile": "contributor-subscription"},
        {"names": [], "profile": "fixture-none"},
    ]
    record["capability_digest"] = capability_digest_for(record)
    return record


def container_manifest(**kwargs: Any) -> LocalCliAdapterManifest:
    """Parse the containerized tools-on manifest record used by these tests."""

    return LocalCliAdapterManifest.from_record(container_manifest_record(**kwargs))


def test_every_declared_container_harness_is_registered_under_its_own_name() -> None:
    known = set(builtin_adapter_registry().known_names())

    assert set(CONTAINER_TOOLS_ON_REGISTRY_NAMES) <= known
    assert CONTAINER_TOOLS_ON_REGISTRY_NAMES == tuple(
        sorted(CONTAINER_HARNESS_IDENTITIES)
    )
    assert {
        identity.executable_basename
        for identity in CONTAINER_HARNESS_IDENTITIES.values()
    } == {"agy", "claude", "codex", "grok", "kimi"}


def test_container_factory_requires_a_parsed_local_cli_manifest() -> None:
    registry = builtin_adapter_registry()

    with pytest.raises(AdapterRegistryError, match="local_cli_manifest"):
        registry.get("claude-code-container-tools-on")
    with pytest.raises(AdapterRegistryError, match="local_cli_manifest"):
        registry.get("claude-code-container-tools-on", local_cli_manifest="a-path")


def test_container_factory_builds_the_adapter_with_its_run_posture() -> None:
    adapter = builtin_adapter_registry().get(
        "claude-code-container-tools-on",
        local_cli_manifest=container_manifest(),
        auth_profile="fixture-none",
        allow_hosts=("api.example.test",),
        allow_subdomains=("example.test",),
        allow_ports=(443, 8443),
        backend="podman",
        parent_env={"HOME": "/nonexistent"},
    )

    assert isinstance(adapter, ContainerCliAdapter)
    assert adapter.identity.executable_basename == "claude"
    assert adapter.auth_profile == "fixture-none"
    assert adapter.allow_hosts == ("api.example.test",)
    assert adapter.allow_subdomains == ("example.test",)
    assert adapter.allow_ports == (443, 8443)
    assert adapter.backend == "podman"
    assert adapter.image == CONTAINER_IMAGE_DIGEST
    assert adapter.manifest.adapter_id == "claude-code-container-tools-on"
    assert adapter.environment() == {"HOME": "/nonexistent"}


def test_container_factory_defaults_to_the_contributor_subscription_posture() -> None:
    adapter = builtin_adapter_registry().get(
        "codex-cli-container-tools-on",
        local_cli_manifest=container_manifest(
            basename="codex", manifest_id="codex-cli-container-tools-on"
        ),
    )

    assert isinstance(adapter, ContainerCliAdapter)
    assert adapter.auth_profile == "contributor-subscription"
    assert adapter.allow_ports == (443,)
    assert adapter.backend == "docker"


def test_container_factory_refuses_a_manifest_for_a_different_harness() -> None:
    registry = builtin_adapter_registry()

    with pytest.raises(ContainerCliAdapterError, match="runs 'codex'"):
        registry.get(
            "codex-cli-container-tools-on",
            local_cli_manifest=container_manifest(),
        )


def test_container_factory_refuses_a_manifest_without_the_tools_on_posture() -> None:
    registry = builtin_adapter_registry()
    host_manifest = container_manifest(
        capabilities=(
            "empty_tools",
            "headless_print",
            "isolated_setting_sources",
            "json_output",
            "model_selection",
            "working_directory_isolation",
        ),
        image=None,
        executable_sha256="a" * 64,
    )

    with pytest.raises(ContainerCliAdapterError, match="missing capabilities") as exc:
        registry.get("claude-code-container-tools-on", local_cli_manifest=host_manifest)

    message = str(exc.value)
    assert "container_execution" in message
    assert "native_tools_enabled" in message
    assert "restricted_egress" in message
    assert "server_side_web_tools_disabled" in message


def test_container_factory_refuses_a_schema_enforced_invocation() -> None:
    registry = builtin_adapter_registry()

    with pytest.raises(ContainerCliAdapterError, match="schema_enforcement"):
        registry.get(
            "claude-code-container-tools-on",
            local_cli_manifest=container_manifest(
                invocation={
                    "schema_enforcement": "output_schema_file",
                    "argv_template": [
                        "-p",
                        "{prompt}",
                        "--output-schema",
                        "{output_schema_path}",
                        "--cwd",
                        "{workspace}",
                        "--model",
                        "{model}",
                    ],
                },
            ),
        )


def _container_run_request(adapter: ContainerCliAdapter) -> RunRequest:
    task = CanonicalTask(
        task_id="lfb.case-1",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture",
        source_id="case-1",
        task_sha256="sha256:" + "b" * 64,
        metadata={"solver_prompt": "Forecast the motion to dismiss."},
    )
    return RunRequest(
        request_id="row-1",
        task=task,
        adapter=adapter.manifest,
        model_key="fixture/model",
        sandbox_policy=SandboxPolicy(
            policy_id="fixture-sandbox",
            backend="dry-run",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=60,
            policy_sha256="sha256:" + "c" * 64,
        ),
        request_sha256="sha256:" + "d" * 64,
    )


def _fake_container_result(
    spec: ContainerHarnessSpec,
    *,
    stdout: str,
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> ContainerHarnessResult:
    spec.log_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stdout_path = spec.log_root / "harness.stdout"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path = spec.log_root / "harness.stderr"
    stderr_path.write_text("", encoding="utf-8")
    return ContainerHarnessResult(
        run_id=spec.run_id,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=1.5,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        image_id=spec.image,
        proxy_image_id=spec.image,
        allowed_hosts=("api.example.test",),
        refused=(),
        allowlist=spec.allowlist().to_record(),
    )


def test_container_adapter_runs_a_row_and_projects_the_manifest_deliverable(
    tmp_path: Path,
) -> None:
    seen: list[ContainerHarnessSpec] = []

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        seen.append(spec)
        return _fake_container_result(
            spec, stdout=json.dumps({"text": "dismissal denied, p=0.4"})
        )

    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name("claude-code-container-tools-on"),
        local_manifest=container_manifest(),
        auth_profile="fixture-none",
        allow_hosts=("api.example.test",),
        parent_env={"HOME": str(tmp_path / "home")},
        runner=runner,
    )
    request = _container_run_request(adapter)

    result = adapter.run(request, tmp_path / "workspace")

    assert result.status == "succeeded"
    assert result.public_summary["harness"] == "claude-code-container-tools-on"
    assert result.public_summary["native_tools_enabled"] is True
    assert result.public_summary["server_side_web_tools_disabled"] is True
    assert result.public_summary["auth_mode"] == "none-offline"
    assert result.public_summary["container_image_digest"] == CONTAINER_IMAGE_DIGEST
    assert result.public_summary["failure_class"] is None
    assert result.public_summary["egress_allowed_hosts"] == ["api.example.test"]

    (spec,) = seen
    assert spec.image == CONTAINER_IMAGE_DIGEST
    assert spec.harness_argv == (
        "-p",
        "Forecast the motion to dismiss.",
        "--output-format",
        "json",
        "--cwd",
        "/workspace",
        "--model",
        "fixture/model",
        "--effort",
        "high",
        "--max-turns",
        "40",
        "--no-web-search",
    )
    assert spec.credentials == ()
    assert spec.run_id.startswith("claude-")
    assert spec.timeout_seconds == 3600


def test_container_adapter_marks_a_timeout_and_an_unprojectable_answer(
    tmp_path: Path,
) -> None:
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name("claude-code-container-tools-on"),
        local_manifest=container_manifest(),
        auth_profile="fixture-none",
        allow_hosts=("api.example.test",),
        parent_env={"HOME": str(tmp_path / "home")},
        runner=lambda spec: _fake_container_result(
            spec, stdout="", exit_code=None, timed_out=True
        ),
    )
    request = _container_run_request(adapter)

    timed_out = adapter.run(request, tmp_path / "timeout")

    assert timed_out.status == "failed"
    assert timed_out.public_summary["failure_class"] == "timeout"

    garbled = ContainerCliAdapter(
        identity=identity_for_registry_name("claude-code-container-tools-on"),
        local_manifest=container_manifest(),
        auth_profile="fixture-none",
        allow_hosts=("api.example.test",),
        parent_env={"HOME": str(tmp_path / "home")},
        runner=lambda spec: _fake_container_result(spec, stdout="not json at all"),
    ).run(request, tmp_path / "garbled")

    assert garbled.status == "failed"
    assert garbled.public_summary["failure_class"] == "schema_violation"


def test_container_adapter_stages_a_contributor_login_into_the_container_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    home = tmp_path / "home"
    config_dir = home / ".claude"
    config_dir.mkdir(parents=True)
    (config_dir / ".credentials.json").write_text("{}", encoding="utf-8")

    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name("claude-code-container-tools-on"),
        local_manifest=container_manifest(),
        auth_profile="contributor-subscription",
        allow_hosts=("api.example.test",),
        parent_env={"HOME": str(home)},
        runner=lambda spec: _fake_container_result(
            spec, stdout=json.dumps({"text": "ok"})
        ),
    )
    spec = adapter.container_spec(
        _container_run_request(adapter), tmp_path / "workspace"
    )

    assert [credential.home_relative_path for credential in spec.credentials] == [
        ".claude/.credentials.json"
    ]
    assert spec.credentials[0].host_path == config_dir / ".credentials.json"
    assert str(home) not in str(spec.credentials[0].home_relative_path)


def test_container_adapter_refuses_a_run_without_the_contributor_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name("grok-cli-container-tools-on"),
        local_manifest=container_manifest(
            basename="grok", manifest_id="grok-cli-container-tools-on"
        ),
        auth_profile="contributor-subscription",
        allow_hosts=("api.example.test",),
        parent_env={"HOME": str(tmp_path / "empty-home")},
        runner=lambda spec: _fake_container_result(spec, stdout="{}"),
    )

    with pytest.raises(AuthProfileError, match="run 'grok login'") as exc:
        adapter.run(_container_run_request(adapter), tmp_path / "workspace")

    assert str(tmp_path) not in str(exc.value)


def _preflight_adapter(tmp_path: Path, *, auth_profile: str) -> ContainerCliAdapter:
    return ContainerCliAdapter(
        identity=identity_for_registry_name("claude-code-container-tools-on"),
        local_manifest=container_manifest(),
        auth_profile=auth_profile,
        allow_subdomains=("example.test",),
        parent_env={"HOME": str(tmp_path / "home")},
    )


def _checks(report: PreflightReport) -> dict[str, bool]:
    return {check.name: check.ok for check in report.checks}


def test_preflight_passes_on_a_present_contributor_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    config_dir = tmp_path / "home" / ".claude"
    config_dir.mkdir(parents=True)
    (config_dir / ".credentials.json").write_text("{}", encoding="utf-8")

    report = run_preflight(
        _preflight_adapter(tmp_path, auth_profile="contributor-subscription"),
        selected_task_ids=("lfb.case-1",),
        image_resolver=lambda _backend, image: image,
    )

    assert report.ok is True
    assert _checks(report)["local_login"] is True
    assert report.to_record()["auth_profile"] == "contributor-subscription"


def test_preflight_reports_a_pinned_image_that_is_not_on_the_host(
    tmp_path: Path,
) -> None:
    def refuse(_backend: str, image: str) -> str:
        raise ContainerImageError(f"pinned image is not present locally: {image}")

    report = run_preflight(
        _preflight_adapter(tmp_path, auth_profile="fixture-none"),
        selected_task_ids=("lfb.case-1",),
        image_resolver=refuse,
    )

    assert report.ok is False
    image = next(check for check in report.checks if check.name == "container_image")
    assert "not present locally" in image.detail


def test_preflight_reports_a_local_image_that_drifted_from_the_pin(
    tmp_path: Path,
) -> None:
    report = run_preflight(
        _preflight_adapter(tmp_path, auth_profile="fixture-none"),
        selected_task_ids=("lfb.case-1",),
        image_resolver=lambda _backend, _image: "sha256:" + "9c" * 32,
    )

    assert _checks(report)["container_image"] is False


def test_preflight_refuses_an_empty_egress_allowlist(tmp_path: Path) -> None:
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name("kimi-cli-container-tools-on"),
        local_manifest=container_manifest(
            basename="kimi", manifest_id="kimi-cli-container-tools-on"
        ),
        auth_profile="fixture-none",
        parent_env={"HOME": str(tmp_path / "home")},
    )

    report = run_preflight(
        adapter,
        selected_task_ids=("lfb.case-1",),
        image_resolver=lambda _backend, image: image,
    )

    checks = _checks(report)
    assert checks["egress_allowlist"] is False
    assert checks["egress_proxy"] is False
    assert report.to_record()["egress_allowlist"] == {}


def test_preflight_starts_and_releases_a_real_allowlist_sidecar(
    tmp_path: Path,
) -> None:
    report = run_preflight(
        _preflight_adapter(tmp_path, auth_profile="fixture-none"),
        selected_task_ids=("lfb.case-1",),
        image_resolver=lambda _backend, image: image,
    )

    assert report.ok is True
    proxy = next(check for check in report.checks if check.name == "egress_proxy")
    assert "bound and released port" in proxy.detail


def test_container_manifest_refusal_reaches_the_cli_as_an_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = tmp_path / "wrong-harness.json"
    manifest.write_text(
        json.dumps(
            container_manifest_record(
                basename="codex", manifest_id="codex-cli-container-tools-on"
            )
        ),
        encoding="utf-8",
    )
    index = tmp_path / "index.json"
    index.write_text("{}", encoding="utf-8")

    assert (
        main(
            [
                "multiharness",
                "harness",
                "preflight",
                "--harness",
                "claude-code-container-tools-on",
                "--adapter-manifest",
                str(manifest),
                "--task-index",
                str(index),
                "--output-dir",
                str(tmp_path / "out"),
                "--allow-host",
                "api.example.test",
            ]
        )
        == 2
    )

    assert "runs 'claude'" in capsys.readouterr().err

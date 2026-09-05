"""Generic named-adapter registry and CLI discovery (dm0g.4.4.8)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    CODEX_CLI_REGISTRY_NAME,
    HARVEY_LAB_REGISTRY_NAME,
    LFB_NATIVE_REGISTRY_NAME,
    AdapterRegistry,
    AdapterRegistryError,
    adapter_from_manifest_file,
    builtin_adapter_registry,
)
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
    AuthProfileError,
)
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapter,
    claude_code_local_manifest,
)
from legalforecast.multiharness.codex_cli import CodexCliAdapter
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.runner import ModelConfig, MultiHarnessRunConfig
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex

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
        CLAUDE_CODE_REGISTRY_NAME,
        CODEX_CLI_REGISTRY_NAME,
        HARVEY_LAB_REGISTRY_NAME,
        LFB_NATIVE_REGISTRY_NAME,
    )
    assert isinstance(first.get(LFB_NATIVE_REGISTRY_NAME), LfbNativeAdapter)
    claude = first.get(CLAUDE_CODE_REGISTRY_NAME)
    assert isinstance(claude, ClaudeCodeCliAdapter)
    assert claude.auth_profile == FIXTURE_NONE
    assert isinstance(first.get(CODEX_CLI_REGISTRY_NAME), CodexCliAdapter)


def test_builtin_harvey_lab_requires_lab_command() -> None:
    registry = builtin_adapter_registry()
    with pytest.raises(AdapterRegistryError, match="lab-command"):
        registry.get(HARVEY_LAB_REGISTRY_NAME)


def test_local_cli_registry_adapter_binds_requested_auth_profile() -> None:
    adapter = builtin_adapter_registry().get(
        CLAUDE_CODE_REGISTRY_NAME,
        auth_profile=PUBLISHED_API_KEY,
        dry_run=True,
    )

    assert isinstance(adapter, ClaudeCodeCliAdapter)
    assert adapter.auth_profile == PUBLISHED_API_KEY
    assert adapter.execution_service.auth_profile == PUBLISHED_API_KEY


def test_manifest_loader_refuses_paid_execution_before_adapter_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory_called = False

    class _Registry:
        def get(self, name: str, **kwargs: object) -> object:
            del name, kwargs
            nonlocal factory_called
            factory_called = True
            raise AssertionError("adapter factory must not run")

    monkeypatch.setattr(
        "legalforecast.multiharness.adapter_registry.builtin_adapter_registry",
        lambda: _Registry(),
    )

    with pytest.raises(AdapterRegistryError, match="guarded Tier-0"):
        adapter_from_manifest_file(
            ROOT
            / "examples"
            / "adapters"
            / "claude-code"
            / "local-cli-adapter-manifest.json",
            auth_profile=PUBLISHED_API_KEY,
            dry_run=False,
        )
    assert not factory_called


def test_manifest_loader_refuses_subscription_without_production_presence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory_called = False

    class _Registry:
        def get(self, name: str, **kwargs: object) -> object:
            del name, kwargs
            nonlocal factory_called
            factory_called = True
            raise AssertionError("adapter factory must not run")

    monkeypatch.setattr(
        "legalforecast.multiharness.adapter_registry.builtin_adapter_registry",
        lambda: _Registry(),
    )

    with pytest.raises(AdapterRegistryError, match="presence probe"):
        adapter_from_manifest_file(
            ROOT
            / "examples"
            / "adapters"
            / "claude-code"
            / "local-cli-adapter-manifest.json",
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
            dry_run=True,
        )
    assert not factory_called


def test_run_config_identity_records_selected_auth_profile(tmp_path: Path) -> None:
    adapter = builtin_adapter_registry().get(
        CLAUDE_CODE_REGISTRY_NAME,
        auth_profile=PUBLISHED_API_KEY,
        dry_run=True,
    )
    task = CanonicalTask(
        task_id="fixture-task",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-suite",
        source_id="fixture-task",
        task_sha256="a" * 64,
    )
    config = MultiHarnessRunConfig(
        task_index=TaskIndex(
            index_id="fixture-index",
            selection_namespace="fixture",
            tasks=(task,),
            index_sha256="sha256:" + "b" * 64,
        ),
        adapters=(adapter,),
        model_configs=(ModelConfig(model_key="anthropic:claude-sonnet-4-6"),),
        sandbox_policy=sandbox_policy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        output_dir=tmp_path / "run",
    )

    assert config.to_record()["adapter_auth_profiles"] == {
        CLAUDE_CODE_REGISTRY_NAME: PUBLISHED_API_KEY
    }


def test_local_cli_registry_adapter_refuses_profile_missing_from_manifest() -> None:
    record = claude_code_local_manifest().to_record()
    record["supported_auth_profiles"] = [
        profile
        for profile in record["supported_auth_profiles"]
        if profile != CONTRIBUTOR_SUBSCRIPTION
    ]
    record["auth_environment_variables"] = [
        entry
        for entry in record["auth_environment_variables"]
        if entry["profile"] != CONTRIBUTOR_SUBSCRIPTION
    ]
    record["capability_digest"] = capability_digest_for(record)
    restricted = LocalCliAdapterManifest.from_record(record)

    with pytest.raises(AuthProfileError, match="not supported by this adapter"):
        builtin_adapter_registry().get(
            CLAUDE_CODE_REGISTRY_NAME,
            local_cli_manifest=restricted,
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        )


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

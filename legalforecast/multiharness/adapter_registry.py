"""Named adapter registry for multi-harness CLI and acceptance tests.

Adapters register by an explicit call. Importing this module does not bind
any adapter. The CLI and fake-binary acceptance tests share
``builtin_adapter_registry`` so discovery cannot drift from invocation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final, cast

from legalforecast.multiharness.adapters import HarnessAdapter

LFB_NATIVE_REGISTRY_NAME: Final = "lfb-native"
HARVEY_LAB_REGISTRY_NAME: Final = "harvey-lab"
CLAUDE_CODE_REGISTRY_NAME: Final = "claude-code-clean-native"
CODEX_CLI_REGISTRY_NAME: Final = "codex-cli-offline"

AdapterFactory = Callable[..., HarnessAdapter]


class AdapterRegistryError(ValueError):
    """Raised when an adapter cannot be registered or resolved."""


class AdapterRegistry:
    """Deterministic name → factory map. Duplicate names are refused."""

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, name: str, factory: AdapterFactory) -> None:
        """Bind one adapter name. A second bind of the same name fails."""

        canonical = _require_adapter_name(name)
        if canonical in self._factories:
            raise AdapterRegistryError(f"duplicate adapter name: {canonical}")
        self._factories[canonical] = factory

    def known_names(self) -> tuple[str, ...]:
        """Return registered names in sorted order."""

        return tuple(sorted(self._factories))

    def get(self, name: str, **kwargs: object) -> HarnessAdapter:
        """Construct the named adapter or refuse with the known-name list."""

        canonical = _require_adapter_name(name, field_name="adapter")
        factory = self._factories.get(canonical)
        if factory is None:
            known = ", ".join(self.known_names()) or "(none)"
            raise AdapterRegistryError(
                f"unknown adapter {canonical!r}; known adapters: {known}"
            )
        return factory(**kwargs)


def builtin_adapter_registry() -> AdapterRegistry:
    """Return a fresh registry of built-in adapters. Call explicitly."""

    registry = AdapterRegistry()
    _register_builtin_adapters(registry)
    return registry


def _require_adapter_name(name: object, *, field_name: str = "adapter name") -> str:
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise AdapterRegistryError(f"{field_name} must be a non-empty canonical name")
    if "/" in name or "\\" in name:
        raise AdapterRegistryError(f"{field_name} must not contain a path")
    return name


def _register_builtin_adapters(registry: AdapterRegistry) -> None:
    registry.register(LFB_NATIVE_REGISTRY_NAME, _lfb_native_factory)
    registry.register(HARVEY_LAB_REGISTRY_NAME, _harvey_lab_factory)
    registry.register(CLAUDE_CODE_REGISTRY_NAME, _claude_code_factory)
    registry.register(CODEX_CLI_REGISTRY_NAME, _codex_cli_factory)


def _lfb_native_factory(**_kwargs: object) -> HarnessAdapter:
    from legalforecast.multiharness.lfb_native import LfbNativeAdapter

    return LfbNativeAdapter()


def _harvey_lab_factory(**kwargs: object) -> HarnessAdapter:
    from legalforecast.multiharness.harvey_lab_adapter import HarveyLabCliAdapter

    lab_command = _optional_str_tuple(kwargs.get("lab_command"))
    if not lab_command:
        raise AdapterRegistryError("--lab-command is required for --adapter harvey-lab")
    lab_root = kwargs.get("lab_root")
    timeout = kwargs.get("timeout_seconds", 300.0)
    timeout_seconds = (
        float(timeout)
        if isinstance(timeout, int | float) and not isinstance(timeout, bool)
        else 300.0
    )
    return HarveyLabCliAdapter(
        lab_command=lab_command,
        lab_root=lab_root if isinstance(lab_root, Path) else None,
        timeout_seconds=timeout_seconds,
    )


def _claude_code_factory(**kwargs: object) -> HarnessAdapter:
    from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
    from legalforecast.multiharness.local_cli_runtime import (
        LocalCliExecutionService as RuntimeService,
    )

    return ClaudeCodeCliAdapter(
        execution_service=cast(RuntimeService, _execution_service(kwargs))
    )


def _codex_cli_factory(**kwargs: object) -> HarnessAdapter:
    from legalforecast.multiharness.codex_cli import CodexCliAdapter
    from legalforecast.multiharness.local_cli_contracts import LocalCliExecutionService

    return CodexCliAdapter(
        execution_service=cast(LocalCliExecutionService, _execution_service(kwargs))
    )


def _execution_service(kwargs: Mapping[str, object]) -> object:
    from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
    from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

    service = kwargs.get("execution_service")
    if service is not None:
        return service
    parent_env = kwargs.get("parent_env")
    environment: Mapping[str, str] | None = None
    if isinstance(parent_env, Mapping):
        typed_parent = cast(Mapping[object, object], parent_env)
        environment = {str(key): str(value) for key, value in typed_parent.items()}
    return LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=environment,
    )


def _optional_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if not isinstance(value, Sequence) or isinstance(value, bytes):
        return ()
    names: list[str] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, str) and item.strip():
            names.append(item)
    return tuple(names)

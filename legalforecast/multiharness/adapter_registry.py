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

    def require_known(self, name: str) -> str:
        """Return the canonical name, or refuse with the known-name list."""

        canonical = _require_adapter_name(name, field_name="adapter")
        if canonical not in self._factories:
            known = ", ".join(self.known_names()) or "(none)"
            raise AdapterRegistryError(
                f"unknown adapter {canonical!r}; known adapters: {known}"
            )
        return canonical

    def get(self, name: str, **kwargs: object) -> HarnessAdapter:
        """Construct the named adapter or refuse with the known-name list."""

        return self._factories[self.require_known(name)](**kwargs)


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
    from legalforecast.multiharness.harness_lane.harnesses import (
        CONTAINER_TOOLS_ON_REGISTRY_NAMES,
    )

    registry.register(LFB_NATIVE_REGISTRY_NAME, _lfb_native_factory)
    registry.register(HARVEY_LAB_REGISTRY_NAME, _harvey_lab_factory)
    registry.register(CLAUDE_CODE_REGISTRY_NAME, _claude_code_factory)
    registry.register(CODEX_CLI_REGISTRY_NAME, _codex_cli_factory)
    for name in CONTAINER_TOOLS_ON_REGISTRY_NAMES:
        registry.register(name, _container_tools_on_factory(name))


def _container_tools_on_factory(registry_name: str) -> AdapterFactory:
    """Bind one containerized harness name to its manifest-driven adapter.

    The manifest is a required keyword rather than a default because this
    family has no built-in manifest: the image digest, the argv template and
    the tool posture all come from the operator's own manifest file, and a
    factory that invented one would run a different program than the run
    record claims.
    """

    def factory(**kwargs: object) -> HarnessAdapter:
        from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
        from legalforecast.multiharness.harness_lane.adapter import (
            DEFAULT_ALLOWED_PORTS,
            ContainerCliAdapter,
        )
        from legalforecast.multiharness.harness_lane.harnesses import (
            identity_for_registry_name,
        )
        from legalforecast.multiharness.local_cli_manifest import (
            LocalCliAdapterManifest,
        )

        manifest = kwargs.get("local_cli_manifest")
        if not isinstance(manifest, LocalCliAdapterManifest):
            raise AdapterRegistryError(
                "local_cli_manifest (a parsed LocalCliAdapterManifest) is required "
                f"for --adapter {registry_name}"
            )
        auth_profile = kwargs.get("auth_profile")
        backend = kwargs.get("backend")
        parent_env = kwargs.get("parent_env")
        lab_projection_root = kwargs.get("lab_projection_root")
        return ContainerCliAdapter(
            identity=identity_for_registry_name(registry_name),
            local_manifest=manifest,
            auth_profile=(
                auth_profile
                if isinstance(auth_profile, str)
                else CONTRIBUTOR_SUBSCRIPTION
            ),
            allow_hosts=_optional_str_tuple(kwargs.get("allow_hosts")),
            allow_subdomains=_optional_str_tuple(kwargs.get("allow_subdomains")),
            allow_ports=_optional_port_tuple(
                kwargs.get("allow_ports"), DEFAULT_ALLOWED_PORTS
            ),
            parent_env=_optional_env(parent_env),
            lab_projection_root=(
                lab_projection_root if isinstance(lab_projection_root, Path) else None
            ),
            backend=backend if isinstance(backend, str) and backend else "docker",
        )

    return factory


def _optional_port_tuple(value: object, default: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return default
    ports = tuple(
        item
        for item in cast(Sequence[object], value)
        if isinstance(item, int) and not isinstance(item, bool)
    )
    return ports or default


def _optional_env(value: object) -> Mapping[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    typed = cast(Mapping[object, object], value)
    return {str(key): str(item) for key, item in typed.items()}


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

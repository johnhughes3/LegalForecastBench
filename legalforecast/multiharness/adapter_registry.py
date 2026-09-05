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


def adapter_from_manifest_file(
    path: Path,
    *,
    auth_profile: str | None = None,
    dry_run: bool = False,
    timeout_seconds: float = 300.0,
) -> HarnessAdapter:
    """Load a command or built-in local-CLI adapter from its manifest."""

    from legalforecast._json_io import read_json_object
    from legalforecast.multiharness.command_adapter import CommandAdapter
    from legalforecast.multiharness.local_cli_manifest import (
        LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION,
        LocalCliAdapterManifest,
    )

    record = read_json_object(
        path,
        error_factory=AdapterRegistryError,
        missing_message=lambda item: f"adapter manifest does not exist: {item}",
        non_object_message=lambda item: f"adapter manifest must be an object: {item}",
    )
    if record.get("schema_version") != LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION:
        if auth_profile is not None:
            raise AdapterRegistryError(
                "--auth-profile requires a local-CLI adapter manifest"
            )
        return CommandAdapter.from_manifest_file(path, timeout_seconds=timeout_seconds)
    manifest = LocalCliAdapterManifest.from_record(record)
    selected_profile = (
        manifest.auth_profile_name if auth_profile is None else auth_profile
    )
    _require_cli_profile_execution_boundary(selected_profile, dry_run=dry_run)
    kwargs: dict[str, object] = {
        "auth_profile": selected_profile,
        "dry_run": dry_run,
        "local_cli_manifest": manifest,
    }
    return builtin_adapter_registry().get(manifest.manifest_id, **kwargs)


def adapter_auth_profile_record(
    adapters: Sequence[HarnessAdapter],
) -> dict[str, object]:
    """Return the selected non-secret profiles for run-plan identity."""

    profiles = {
        adapter.manifest.adapter_id: profile
        for adapter in adapters
        if isinstance((profile := getattr(adapter, "auth_profile", None)), str)
    }
    return {"adapter_auth_profiles": profiles} if profiles else {}


def _require_cli_profile_execution_boundary(
    profile_id: str,
    *,
    dry_run: bool,
) -> None:
    from legalforecast.multiharness.auth_profiles import (
        CONTRIBUTOR_SUBSCRIPTION,
        PUBLISHED_API_KEY,
    )

    if profile_id == CONTRIBUTOR_SUBSCRIPTION:
        raise AdapterRegistryError(
            "contributor-subscription has no production local-login presence probe"
        )
    if profile_id == PUBLISHED_API_KEY and not dry_run:
        raise AdapterRegistryError(
            "published-api-key execution requires the guarded Tier-0 spend-control path"
        )


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
    from legalforecast.multiharness.claude_code import (
        ClaudeCodeCliAdapter,
        claude_code_local_manifest,
    )
    from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
    from legalforecast.multiharness.local_cli_runtime import (
        LocalCliExecutionService as RuntimeService,
    )

    manifest, auth_profile, service = _local_cli_inputs(
        kwargs,
        default_manifest=claude_code_local_manifest,
    )
    return ClaudeCodeCliAdapter(
        execution_service=cast(RuntimeService, service),
        local_manifest=cast(LocalCliAdapterManifest, manifest),
        auth_profile=auth_profile,
    )


def _codex_cli_factory(**kwargs: object) -> HarnessAdapter:
    from legalforecast.multiharness.codex_cli import (
        CodexCliAdapter,
        load_codex_local_cli_manifest,
    )
    from legalforecast.multiharness.local_cli_contracts import LocalCliExecutionService
    from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest

    manifest, auth_profile, service = _local_cli_inputs(
        kwargs,
        default_manifest=load_codex_local_cli_manifest,
    )
    return CodexCliAdapter(
        execution_service=cast(LocalCliExecutionService, service),
        local_cli_manifest=cast(LocalCliAdapterManifest, manifest),
        auth_profile=auth_profile,
    )


def _local_cli_inputs(
    kwargs: Mapping[str, object],
    *,
    default_manifest: Callable[[], object],
) -> tuple[object, str, object]:
    from legalforecast.multiharness.auth_binding import (
        bind_adapter_auth_profile,
        contained_execution_service,
    )
    from legalforecast.multiharness.local_cli_identity import ExecutableIdentityPin
    from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest

    manifest = kwargs.get("local_cli_manifest")
    if manifest is None:
        manifest = default_manifest()
    if not isinstance(manifest, LocalCliAdapterManifest):
        raise AdapterRegistryError("local_cli_manifest has the wrong type")
    requested = kwargs.get("auth_profile", manifest.auth_profile_name)
    bound = bind_adapter_auth_profile(manifest, requested)
    _require_cli_profile_execution_boundary(
        bound.profile_id,
        dry_run=kwargs.get("dry_run") is True,
    )
    service = kwargs.get("execution_service")
    if service is not None:
        return manifest, bound.profile_id, service
    environment = _parent_environment(kwargs.get("parent_env"))
    return (
        manifest,
        bound.profile_id,
        contained_execution_service(
            bound,
            parent_env=environment,
            executable_pin=ExecutableIdentityPin(
                basename=manifest.executable.basename,
                version=manifest.executable.version,
                sha256=manifest.executable.sha256,
                distribution_kind=manifest.executable.distribution_kind,
            ),
        ),
    )


def _parent_environment(value: object) -> Mapping[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    typed = cast(Mapping[object, object], value)
    return {str(key): str(item) for key, item in typed.items()}


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

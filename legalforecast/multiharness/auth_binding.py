"""Bind a declared auth profile to a local-CLI adapter invocation plan.

Adapters resolve profile identity and projected *names* here. Credential
values stay with the contained execution service and Infisical wrapper.
``fixture-none`` projects nothing. ``published-api-key`` uses the 4.2.13
layout. ``contributor-subscription`` is not yet bound.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeGuard

from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
    AuthProfileError,
    ResolvedAuthProfile,
    published_api_key_env_vars_for_executable,
    require_auth_profile_id,
    resolve_auth_profile,
)
from legalforecast.multiharness.local_cli_environment import (
    CredentialSource,
    InfisicalSandboxCredentialSource,
    build_local_cli_environment,
    expected_child_environment_names,
    project_profile_credentials,
)
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.sandbox import PROVIDER_EGRESS_HOST_ONLY

ADAPTER_BOUND_AUTH_PROFILES: Final[frozenset[str]] = frozenset(
    {FIXTURE_NONE, PUBLISHED_API_KEY}
)


@dataclass(frozen=True, slots=True)
class BoundAdapterAuth:
    """Non-secret profile binding used to plan an adapter invocation."""

    profile: ResolvedAuthProfile
    supported_profiles: tuple[str, ...]
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def profile_id(self) -> str:
        """Return the canonical bound profile ID."""

        return self.profile.profile_id

    def public_provenance(self) -> dict[str, str]:
        """Return the only profile fields allowed in public records."""

        return self.profile.public_provenance()


def bind_adapter_auth_profile(
    manifest: LocalCliAdapterManifest,
    requested: object,
    *,
    infisical_env: str = "dev",
) -> BoundAdapterAuth:
    """Bind one requested profile to this adapter's manifest at plan time."""

    profile_id = require_auth_profile_id(requested)
    if profile_id not in ADAPTER_BOUND_AUTH_PROFILES:
        raise AuthProfileError(
            f"{profile_id} is not yet bound for adapter invocation; "
            "declare exactly one of: "
            f"{', '.join(sorted(ADAPTER_BOUND_AUTH_PROFILES))}"
        )
    if profile_id not in manifest.supported_auth_profiles:
        raise AuthProfileError("declared auth_profile is not supported by this adapter")
    env_names = manifest.env_vars_for_profile(profile_id)
    if profile_id == PUBLISHED_API_KEY:
        expected = published_api_key_env_vars_for_executable(
            manifest.executable.basename
        )
        if tuple(env_names) != expected:
            raise AuthProfileError(
                "published-api-key projected names do not match the Infisical layout"
            )
        require_credentialed_network_policy(
            profile_id, manifest.containment.network_policy
        )
    profile = resolve_auth_profile(
        profile_id,
        supported_profiles=manifest.supported_auth_profiles,
        projected_env_vars=env_names,
        infisical_env=infisical_env,
    )
    return BoundAdapterAuth(
        profile=profile,
        supported_profiles=manifest.supported_auth_profiles,
        profile_env_vars=manifest.auth_environment_variables,
    )


def public_auth_mode(profile_id: str, *, fixture_mode: str) -> str:
    """Return public auth_mode, preserving fixture-none adapter strings."""

    canonical = require_auth_profile_id(profile_id)
    if canonical == FIXTURE_NONE:
        return fixture_mode
    return canonical


def require_credentialed_network_policy(profile_id: str, network_policy: str) -> None:
    """Refuse published-api-key unless the request opted into provider egress."""

    canonical = require_auth_profile_id(profile_id)
    if canonical != PUBLISHED_API_KEY:
        return
    if network_policy != PROVIDER_EGRESS_HOST_ONLY:
        raise AuthProfileError(
            "published-api-key requires provider_egress_host_only network policy"
        )


def require_execution_service_profile(
    service: object,
    profile_id: str,
    *,
    projected_env_vars: Sequence[str] | None = None,
) -> None:
    """Refuse a live profile unless the contained service is bound to it."""

    canonical = require_auth_profile_id(profile_id)
    declared = getattr(service, "auth_profile", None)
    if declared is None:
        if canonical != FIXTURE_NONE:
            raise AuthProfileError(
                "published-api-key requires a contained execution service "
                "configured with that profile"
            )
        return
    if declared != canonical:
        raise AuthProfileError(
            "execution service auth_profile does not match the bound profile"
        )
    if projected_env_vars is None:
        return
    service_names = _service_projected_env_vars(service, canonical)
    if tuple(service_names) != tuple(projected_env_vars):
        raise AuthProfileError(
            "execution service projected names do not match the bound profile"
        )


def _service_projected_env_vars(service: object, profile_id: str) -> tuple[str, ...]:
    lookup = getattr(service, "env_vars_for_profile", None)
    if callable(lookup):
        return _string_tuple(lookup(profile_id))
    return _profile_env_var_lookup(getattr(service, "profile_env_vars", ()), profile_id)


def _profile_env_var_lookup(mapping: object, profile_id: str) -> tuple[str, ...]:
    if not _is_sequence(mapping):
        return ()
    for item in mapping:
        parsed = _profile_env_var_entry(item)
        if parsed is None:
            continue
        declared_id, env_names = parsed
        if declared_id == profile_id:
            return env_names
    return ()


def _profile_env_var_entry(item: object) -> tuple[str, tuple[str, ...]] | None:
    if not _is_sequence(item) or len(item) != 2:
        return None
    declared_id = item[0]
    if not isinstance(declared_id, str):
        return None
    return declared_id, _string_tuple(item[1])


def _string_tuple(value: object) -> tuple[str, ...]:
    if not _is_sequence(value):
        return ()
    names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return ()
        names.append(item)
    return tuple(names)


def _is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def project_bound_child_environment(
    bound: BoundAdapterAuth,
    scratch_root: Path,
    *,
    credential_source: CredentialSource | None,
    parent_env: Mapping[str, str],
    extra_allowlist: Sequence[str] = (),
) -> dict[str, str]:
    """Project the bound profile into an allowlisted child environment."""

    projected = project_profile_credentials(
        bound.profile,
        credential_source=credential_source,
        parent_env=parent_env,
    )
    return build_local_cli_environment(
        bound.profile,
        scratch_root,
        projected_credentials=projected,
        parent_env=parent_env,
        extra_allowlist=extra_allowlist,
    )


def expected_bound_child_environment_names(
    bound: BoundAdapterAuth,
    *,
    parent_env: Mapping[str, str],
    extra_allowlist: Sequence[str] = (),
) -> frozenset[str]:
    """Return the exact child env names this binding may emit."""

    return expected_child_environment_names(
        parent_env=parent_env,
        projected_names=bound.profile.projected_env_vars,
        extra_allowlist=extra_allowlist,
    )


def contained_execution_service(
    bound: BoundAdapterAuth,
    *,
    credential_source: CredentialSource | None = None,
    parent_env: Mapping[str, str] | None = None,
    adapter_id: str = "contained-local-cli",
    display_name: str = "Contained local CLI",
    adapter_version: str = "1.0.0",
) -> LocalCliExecutionService:
    """Return a contained service whose auth_profile matches this binding."""

    if bound.profile_id == FIXTURE_NONE:
        if credential_source is not None:
            raise AuthProfileError("fixture-none never reads credentials")
        source: CredentialSource | None = None
    elif credential_source is not None:
        source = credential_source
    else:
        source = InfisicalSandboxCredentialSource(parent_env=parent_env)
    return LocalCliExecutionService(
        adapter_id=adapter_id,
        display_name=display_name,
        adapter_version=adapter_version,
        auth_profile=bound.profile_id,
        supported_auth_profiles=bound.supported_profiles,
        profile_env_vars=bound.profile_env_vars,
        credential_source=source,
        infisical_env=bound.profile.infisical_env,
        parent_env=parent_env,
    )

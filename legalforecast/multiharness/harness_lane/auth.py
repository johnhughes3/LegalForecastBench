"""Bridge a contributor's own harness login into a containerized run.

``contributor-subscription`` means the harness runs under the contributor's
existing interactive login.  :mod:`legalforecast.multiharness.subscription`
proves that login is present without reading it; this module turns the same
descriptor into the two things a container needs: the credential files to copy
into the run's throwaway HOME, and the per-harness environment settings that
keep an autoupdater or a memory feature from writing outside it.

The copy is deliberately keyed to the harness's *default* home-relative
config directory rather than to wherever the login lives on the host.  A
contributor who redirected ``CODEX_HOME`` still gets a container whose
``$HOME/.codex`` holds the login, so no host path crosses the boundary and no
config-dir override has to be smuggled into the child environment.
"""

from __future__ import annotations

from collections.abc import Mapping

from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    AuthProfileError,
    require_auth_profile_id,
)
from legalforecast.multiharness.container_harness import HarnessCredential
from legalforecast.multiharness.harness_lane.harnesses import ContainerHarnessIdentity
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.subscription import (
    descriptor_for_executable,
    local_login_presence_for,
)


def resolve_lane_auth_profile(
    profile_id: str, manifest: LocalCliAdapterManifest
) -> str:
    """Return the canonical profile, or refuse one the manifest does not support."""

    canonical = require_auth_profile_id(profile_id)
    if canonical not in manifest.supported_auth_profiles:
        supported = ", ".join(sorted(manifest.supported_auth_profiles))
        raise AuthProfileError(
            f"{manifest.manifest_id} does not support auth profile {canonical!r}; "
            f"supported profiles: {supported}"
        )
    return canonical


def prove_local_login(
    identity: ContainerHarnessIdentity,
    profile_id: str,
    parent_env: Mapping[str, str],
) -> None:
    """Prove the contributor's own login for this harness, or fail closed.

    Any other profile is a no-op here: ``fixture-none`` projects nothing, and
    ``published-api-key`` is the official lane's posture, whose credential
    projection is owned by ``auth_profiles`` rather than by this lane.
    """

    if require_auth_profile_id(profile_id) != CONTRIBUTOR_SUBSCRIPTION:
        return
    local_login_presence_for(identity.executable_basename).prove(parent_env)


def container_credentials(
    identity: ContainerHarnessIdentity,
    profile_id: str,
    parent_env: Mapping[str, str],
) -> tuple[HarnessCredential, ...]:
    """Return the login files to copy into the run's throwaway container HOME."""

    if require_auth_profile_id(profile_id) != CONTRIBUTOR_SUBSCRIPTION:
        return ()
    basename = identity.executable_basename
    presence = local_login_presence_for(basename)
    presence.prove(parent_env)
    descriptor = descriptor_for_executable(basename)
    config_dir = presence.config_dir(parent_env)
    return tuple(
        HarnessCredential(
            host_path=config_dir / relative,
            home_relative_path=f"{descriptor.home_relative_config_dir}/{relative}",
        )
        for relative in descriptor.credential_relative_paths
    )


def container_child_env(
    identity: ContainerHarnessIdentity, profile_id: str
) -> dict[str, str]:
    """Return per-harness child settings for a subscription run.

    ``HOME`` and the proxy variables are set by the container plan, and the
    credential copy lands at the harness's default home-relative config
    directory, so nothing here needs to name a path.
    """

    if require_auth_profile_id(profile_id) != CONTRIBUTOR_SUBSCRIPTION:
        return {}
    descriptor = descriptor_for_executable(identity.executable_basename)
    return dict(descriptor.extra_child_env)

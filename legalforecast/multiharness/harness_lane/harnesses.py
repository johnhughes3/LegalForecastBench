"""Registry identities for the containerized, tools-on harness family.

This lane asks one question the main benchmark cannot: does an agentic CLI
beat the bare provider API on the same forecast?  Answering it means running
each CLI *with its own local tools live* -- read, write, bash, grep,
subagents -- inside a digest-pinned container whose egress is confined to the
provider's own endpoints.  Strip the tools and the run is an expensive API
wrapper measuring nothing.

Each identity below binds one registry name to the executable basename the
rest of the stack already keys on: the contributor-subscription login layout
in :mod:`legalforecast.multiharness.subscription`, and the ``executable``
block of the local-CLI adapter manifest.  Binding them here is what lets the
adapter refuse a manifest for a *different* harness than the registry name
asked for, which is otherwise an easy and silent way to mislabel a result
row.

Nothing here declares an egress allowlist.  The provider API and token-refresh
domains are a per-run operator input precisely because guessing them wrong
fails open (an over-broad allowlist) rather than closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


class ContainerHarnessIdentityError(ValueError):
    """Raised when a name is not part of the containerized tools-on family."""


@dataclass(frozen=True, slots=True)
class ContainerHarnessIdentity:
    """One harness CLI's registry name, executable, and human label."""

    registry_name: str
    executable_basename: str
    display_name: str


# Sourced from the 2026-08-31 live harness characterization.  The basenames are
# the same keys ``subscription.local_login`` declares, so a harness that gains
# an identity here without a login layout there fails loudly at preflight
# rather than silently running unauthenticated.
_IDENTITIES: Final[tuple[ContainerHarnessIdentity, ...]] = (
    ContainerHarnessIdentity(
        registry_name="antigravity-cli-container-tools-on",
        executable_basename="agy",
        display_name="Antigravity CLI (containerized, native tools on)",
    ),
    ContainerHarnessIdentity(
        registry_name="claude-code-container-tools-on",
        executable_basename="claude",
        display_name="Claude Code (containerized, native tools on)",
    ),
    ContainerHarnessIdentity(
        registry_name="codex-cli-container-tools-on",
        executable_basename="codex",
        display_name="Codex CLI (containerized, native tools on)",
    ),
    ContainerHarnessIdentity(
        registry_name="grok-cli-container-tools-on",
        executable_basename="grok",
        display_name="Grok CLI (containerized, native tools on)",
    ),
    ContainerHarnessIdentity(
        registry_name="kimi-cli-container-tools-on",
        executable_basename="kimi",
        display_name="Kimi Code (containerized, native tools on)",
    ),
)

CONTAINER_HARNESS_IDENTITIES: Final[Mapping[str, ContainerHarnessIdentity]] = (
    MappingProxyType({identity.registry_name: identity for identity in _IDENTITIES})
)
CONTAINER_TOOLS_ON_REGISTRY_NAMES: Final[tuple[str, ...]] = tuple(
    sorted(CONTAINER_HARNESS_IDENTITIES)
)


def identity_for_registry_name(name: str) -> ContainerHarnessIdentity:
    """Return one containerized harness identity, or refuse with the family."""

    identity = CONTAINER_HARNESS_IDENTITIES.get(name)
    if identity is None:
        declared = ", ".join(CONTAINER_TOOLS_ON_REGISTRY_NAMES)
        raise ContainerHarnessIdentityError(
            f"{name!r} is not a containerized tools-on harness; "
            f"declared harnesses: {declared}"
        )
    return identity

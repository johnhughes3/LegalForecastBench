"""Explicit local-CLI authentication profiles with a strict no-fallback policy.

A run declares exactly one profile. Missing, ambiguous, or unknown values fail
before credential fetch or process spawn. Profiles never substitute for each
other, and ``fixture-none`` never reads credentials.

Canonical IDs are consumed by B1 adapter manifests (``dm0g.4.4.1``). Do not add
provider-specific aliases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    validate_env_var_names,
    validate_public_record,
)

FIXTURE_NONE: Final = "fixture-none"
PUBLISHED_API_KEY: Final = "published-api-key"
CONTRIBUTOR_SUBSCRIPTION: Final = "contributor-subscription"

AUTH_PROFILE_IDS: Final[frozenset[str]] = frozenset(
    {FIXTURE_NONE, PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION}
)

LEGALFORECASTBENCH_SANDBOX_ROOT: Final = "/agents/sandbox/legalforecastbench"
LABELING_INFISICAL_PATH: Final = f"{LEGALFORECASTBENCH_SANDBOX_ROOT}/labeling"
HARNESS_RUNTIME_INFISICAL_ROOT: Final = (
    f"{LEGALFORECASTBENCH_SANDBOX_ROOT}/harness-runtime"
)

# published-api-key reuses the existing labeling stage view rather than a
# duplicate harness-runtime folder. The labeling inventory also has
# GEMINI_API_KEY; adapters never project it. contributor-subscription stays
# on its own harness-runtime folder and is not bound yet.
_PROFILE_INFISICAL_PATH: Final[Mapping[str, str]] = {
    PUBLISHED_API_KEY: LABELING_INFISICAL_PATH,
    CONTRIBUTOR_SUBSCRIPTION: (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/contributor-subscription"
    ),
}

# Infisical secret names this profile may project. Each adapter takes a
# subset. See docs/adapters/published-api-key-profile.md.
PUBLISHED_API_KEY_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    }
)

INFISICAL_WRAPPER_NAME: Final = "infisical-agent-sandbox"

PUBLISHED_API_KEY_ENV_BY_EXECUTABLE: Final[Mapping[str, tuple[str, ...]]] = {
    "claude": ("ANTHROPIC_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
}

_REFUSED_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "fixture_none",
        "explicit_api_key",
        "explicit-api-key",
        "local_cli_subscription",
        "local-cli-subscription",
        "published_api_key",
        "contributor_subscription",
    }
)

ALLOWED_INFISICAL_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"dev", "staging", "sandbox"}
)


class AuthProfileError(ValueError):
    """Raised when a run's authentication profile cannot be used."""


@dataclass(frozen=True, slots=True)
class ResolvedAuthProfile:
    """Non-secret profile identity used to project credentials and provenance."""

    profile_id: str
    projected_env_vars: tuple[str, ...]
    infisical_path: str | None
    infisical_env: str

    def public_provenance(self) -> dict[str, str]:
        """Return the only profile fields allowed in public records."""

        record = {"auth_profile": self.profile_id}
        validate_public_record(record, "auth profile provenance")
        return record


def require_auth_profile_id(value: object, field_name: str = "auth_profile") -> str:
    """Return a canonical profile ID or fail closed without substituting aliases."""

    if value is None:
        raise AuthProfileError(f"{field_name} is required")
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AuthProfileError(f"{field_name} must be a single canonical profile ID")
    if value in _REFUSED_ALIASES:
        raise AuthProfileError(
            f"{field_name} {value!r} is a refused alias; declare exactly one of: "
            f"{', '.join(sorted(AUTH_PROFILE_IDS))}"
        )
    if value not in AUTH_PROFILE_IDS:
        raise AuthProfileError(
            f"{field_name} {value!r} is unknown; declare exactly one of: "
            f"{', '.join(sorted(AUTH_PROFILE_IDS))}"
        )
    return value


def published_api_key_env_vars_for_executable(basename: str) -> tuple[str, ...]:
    """Return the Infisical key names this executable may project."""

    names = PUBLISHED_API_KEY_ENV_BY_EXECUTABLE.get(basename)
    if names is None:
        raise AuthProfileError(
            "published-api-key has no Infisical layout for this executable"
        )
    return names


def published_api_key_layout() -> dict[str, object]:
    """Return the operator Infisical layout. Never includes secret values."""

    record: dict[str, object] = {
        "wrapper": INFISICAL_WRAPPER_NAME,
        "infisical_path": infisical_path_for_profile(PUBLISHED_API_KEY),
        "canonical_environment": "dev",
        "allowed_environments": list(sorted(ALLOWED_INFISICAL_ENVIRONMENTS)),
        "infisical_keys": [
            {"executable": basename, "name": name}
            for basename, names in PUBLISHED_API_KEY_ENV_BY_EXECUTABLE.items()
            for name in names
        ],
        "fail_closed_when_empty": True,
        "host_environment_fallback": False,
    }
    validate_public_record(record, "published-api-key Infisical layout")
    listed = frozenset(
        name for names in PUBLISHED_API_KEY_ENV_BY_EXECUTABLE.values() for name in names
    )
    if listed != PUBLISHED_API_KEY_SECRET_KEYS:
        raise AuthProfileError("published-api-key layout keys drifted")
    return record


def infisical_path_for_profile(profile_id: str) -> str:
    """Return the Infisical sandbox path for a credentialed profile."""

    canonical = require_auth_profile_id(profile_id)
    if canonical == FIXTURE_NONE:
        raise AuthProfileError("fixture-none never reads credentials")
    path = _PROFILE_INFISICAL_PATH[canonical]
    _require_declared_profile_infisical_path(path)
    return path


def require_infisical_environment(value: str) -> str:
    """Return a non-production Infisical environment name."""

    if value == "prod":
        raise AuthProfileError("Infisical production environment is refused")
    if value not in ALLOWED_INFISICAL_ENVIRONMENTS:
        raise AuthProfileError("Infisical environment is not an allowed sandbox stage")
    return value


def resolve_auth_profile(
    declared: object,
    *,
    supported_profiles: Sequence[str],
    projected_env_vars: Sequence[str] | None = None,
    infisical_env: str = "dev",
) -> ResolvedAuthProfile:
    """Bind exactly one declared profile to non-secret projection metadata."""

    profile_id = require_auth_profile_id(declared)
    supported = tuple(
        require_auth_profile_id(item, "supported_auth_profiles")
        for item in supported_profiles
    )
    if not supported:
        raise AuthProfileError("supported_auth_profiles must not be empty")
    if profile_id not in supported:
        raise AuthProfileError("declared auth_profile is not supported by this adapter")
    stage = require_infisical_environment(infisical_env)
    env_names = _validated_projected_env_vars(profile_id, projected_env_vars)
    path = (
        None if profile_id == FIXTURE_NONE else infisical_path_for_profile(profile_id)
    )
    return ResolvedAuthProfile(
        profile_id=profile_id,
        projected_env_vars=env_names,
        infisical_path=path,
        infisical_env=stage,
    )


def _validated_projected_env_vars(
    profile_id: str,
    projected_env_vars: Sequence[str] | None,
) -> tuple[str, ...]:
    names = tuple(projected_env_vars or ())
    if profile_id == FIXTURE_NONE:
        if names:
            raise AuthProfileError(
                "fixture-none never reads credentials and must not declare "
                "projected credential environment names"
            )
        return ()
    if not names:
        raise AuthProfileError(
            "credentialed auth_profile must declare projected environment names"
        )
    try:
        validated = validate_env_var_names(names, "projected_env_vars")
    except MultiHarnessValidationError as exc:
        raise AuthProfileError(str(exc)) from exc
    if len(set(validated)) != len(validated):
        raise AuthProfileError("projected_env_vars must not contain duplicates")
    return validated


def _require_declared_profile_infisical_path(path: str) -> None:
    if ".." in path or path.endswith("/") or "//" in path:
        raise AuthProfileError("Infisical path is invalid")
    prefix = f"{LEGALFORECASTBENCH_SANDBOX_ROOT}/"
    if path != LEGALFORECASTBENCH_SANDBOX_ROOT and not path.startswith(prefix):
        raise AuthProfileError(
            "Infisical path must be a legalforecastbench sandbox subdirectory"
        )
    if path not in _PROFILE_INFISICAL_PATH.values():
        raise AuthProfileError(
            "CLI auth credentials must use a declared profile Infisical path"
        )

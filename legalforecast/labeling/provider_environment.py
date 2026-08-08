"""Run provider-bearing children with one exact provider key name."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import Final

from legalforecast.evals.live_model_solver import (
    ANTHROPIC_API_KEY_ENV,
    GEMINI_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
)

GENERIC_PROVIDER_API_KEY_ENV: Final = "LFB_PROVIDER_API_KEY"
PROVIDER_KEY_ENV_BY_PROVIDER: Final = {
    "anthropic": ANTHROPIC_API_KEY_ENV,
    "google": GEMINI_API_KEY_ENV,
    "openai": OPENAI_API_KEY_ENV,
}
PROVIDER_KEY_ENV_NAMES: Final = frozenset(PROVIDER_KEY_ENV_BY_PROVIDER.values())
_CROSS_STAGE_SECRET_ENV_NAMES: Final = frozenset(
    {
        "CASE_DEV_API_KEY",
        "COURTLISTENER_API_TOKEN",
        "FIRECRAWL_API_KEY",
        "MISTRAL_API_KEY",
        "PACER_PASSWORD",
        "PACER_USERNAME",
        "RECAP_API_TOKEN",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
        "RECAP_FETCH_BROKER_MACHINE_ID",
        "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
        "RECAP_FETCH_BROKER_URL",
    }
)


class ProviderEnvironmentError(ValueError):
    """Raised when a provider-bearing child would start with the wrong secrets."""


def canonical_provider_environment_name(provider: str) -> str:
    """Return the exact provider key name for one reviewed provider."""

    normalized = provider.strip().lower()
    try:
        return PROVIDER_KEY_ENV_BY_PROVIDER[normalized]
    except KeyError as exc:
        raise ProviderEnvironmentError(
            "provider is outside the reviewed allowlist"
        ) from exc


def reduce_provider_child_environment(
    *,
    provider: str,
    parent_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a child environment with exactly one provider key name."""

    source_env = os.environ if parent_env is None else parent_env
    child_env = dict(source_env)
    selected_name = canonical_provider_environment_name(provider)
    offending_names = sorted(
        name for name in _CROSS_STAGE_SECRET_ENV_NAMES if name in source_env
    )
    if offending_names:
        names = ", ".join(offending_names)
        raise ProviderEnvironmentError(
            "cross-stage secret environment names are not allowed: " + names
        )
    generic_value = source_env.get(GENERIC_PROVIDER_API_KEY_ENV)
    if generic_value is not None:
        if not generic_value.strip():
            raise ProviderEnvironmentError(
                f"{GENERIC_PROVIDER_API_KEY_ENV} must be present and nonempty"
            )
        present_canonical = sorted(
            name for name in PROVIDER_KEY_ENV_NAMES if name in source_env
        )
        if present_canonical:
            names = ", ".join(present_canonical)
            raise ProviderEnvironmentError(
                "generic protected provider key must not be combined with "
                "canonical labeling-stage provider names: " + names
            )
        selected_value = generic_value
    else:
        selected_value = source_env.get(selected_name, "")
        if not selected_value.strip():
            raise ProviderEnvironmentError(
                f"{selected_name} must be present and nonempty"
            )
    for name in PROVIDER_KEY_ENV_NAMES | {GENERIC_PROVIDER_API_KEY_ENV}:
        child_env.pop(name, None)
    child_env[selected_name] = selected_value
    return child_env


def run_provider_isolated_command(
    *,
    provider: str,
    command: Sequence[str],
    parent_env: Mapping[str, str] | None = None,
) -> int:
    """Run one command under the reduced child environment."""

    if not command:
        raise ProviderEnvironmentError("provider child command is required")
    child_env = reduce_provider_child_environment(
        provider=provider,
        parent_env=parent_env,
    )
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            env=child_env,
        )
    except FileNotFoundError:
        return 127
    except PermissionError:
        return 126
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Select one provider key name and run the child command under it."""

    parser = argparse.ArgumentParser(
        description=(
            "Run a child command with exactly one reviewed labeling provider key "
            "name. The parent may expose either the local labeling stage view "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY) or the "
            "protected workflow's single LFB_PROVIDER_API_KEY source."
        )
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    command = list(arguments.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        return run_provider_isolated_command(
            provider=arguments.provider,
            command=command,
        )
    except ProviderEnvironmentError as exc:
        parser.exit(status=2, message=f"{parser.prog}: error: {exc}\n")
    return 2  # pragma: no cover

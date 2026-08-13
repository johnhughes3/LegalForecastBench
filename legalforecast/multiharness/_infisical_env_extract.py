"""Emit selected environment names as JSON for Infisical-wrapper children.

Invoked only as ``python -m legalforecast.multiharness._infisical_env_extract``.
It never prints Infisical broker identity variables.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

_BROKER_ENV_NAMES = frozenset(
    {
        "INFISICAL_TOKEN",
        "INFISICAL_DOMAIN",
        "INFISICAL_AGENT_SANDBOX_ENV_FILE",
        "INFISICAL_AGENT_SANDBOX_PROJECT_ID",
        "INFISICAL_AGENT_SANDBOX_ENV",
        "INFISICAL_AGENT_SANDBOX_PATH",
        "INFISICAL_AGENT_SANDBOX_DOMAIN",
        "INFISICAL_AGENT_SANDBOX_TOKEN",
        "INFISICAL_AGENT_SANDBOX_MACHINE_CLIENT_ID",
        "INFISICAL_AGENT_SANDBOX_MACHINE_CLIENT_SECRET",
        "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID",
        "INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET",
    }
)


class ExtractError(ValueError):
    """Raised when requested environment names cannot be emitted safely."""


def projected_env_payload(
    names: Sequence[str],
    source: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return requested values, refusing broker identity names."""

    if not names:
        raise ExtractError("projected environment names must not be empty")
    environment = os.environ if source is None else source
    payload: dict[str, str] = {}
    for name in names:
        if not name or name in _BROKER_ENV_NAMES:
            raise ExtractError("refusing to emit Infisical broker identity")
        value = environment.get(name)
        if value:
            payload[name] = value
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """Write requested environment values as compact JSON to stdout."""

    parser = argparse.ArgumentParser(
        prog="legalforecast.multiharness._infisical_env_extract"
    )
    parser.add_argument(
        "--names", required=True, help="comma-separated environment names"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    names = tuple(part for part in args.names.split(",") if part)
    try:
        payload = projected_env_payload(names)
    except ExtractError:
        return 65
    json.dump(payload, sys.stdout, separators=(",", ":"), sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

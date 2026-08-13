"""Command adapter entry point for the offline Codex CLI adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapterError,
    build_capabilities,
    run_offline_protocol_fixture,
)
from legalforecast.multiharness.spec import RunRequest


def main(argv: list[str] | None = None) -> int:
    """Run one adapter protocol command without spawning Codex."""

    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)

    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--output", type=Path, required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--workspace", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.phase == "capabilities":
            write_json_object(args.output, build_capabilities().to_record())
            return 0

        request = RunRequest.from_record(_read_json_object(args.request))
        result = run_offline_protocol_fixture(request, args.workspace)
        write_json_object(args.output, result.to_record())
        return 0
    except Exception:
        print("Codex CLI adapter failed closed", file=sys.stderr)
        return 1


def _read_json_object(path: Path) -> dict[str, Any]:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise CodexCliAdapterError("request must be a JSON object")
    return cast(dict[str, Any], decoded)


if __name__ == "__main__":
    raise SystemExit(main())

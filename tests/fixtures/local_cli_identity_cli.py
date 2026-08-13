#!/usr/bin/env python3
"""Versioned identity-probe fixture for fail-closed local CLI binding.

synthetic: true

Invoked as a real subprocess. Default identity document is
``legalforecast.multiharness.local_cli_identity_probe.v1``. Report overrides
are argv flags so tests can mutate version, events, flags, and models without
rewriting the hashed file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

IDENTITY_SCHEMA_VERSION = "legalforecast.multiharness.local_cli_identity_probe.v1"
DEFAULT_VERSION = "1.0.0"
DEFAULT_FLAGS = ("--mode", "--model")
DEFAULT_CAPABILITIES = ("json_output", "headless_print")
DEFAULT_EVENTS = ("result",)
DEFAULT_MODELS = ("fixture-haiku",)


def _identity_payload(args: argparse.Namespace) -> dict[str, object]:
    flags = tuple(item for item in args.report_flags.split(",") if item)
    capabilities = tuple(item for item in args.report_capabilities.split(",") if item)
    events = tuple(item for item in args.report_events.split(",") if item)
    models = tuple(item for item in args.report_models.split(",") if item)
    return {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "basename": Path(__file__).name,
        "version": args.report_version,
        "flags": list(flags),
        "capabilities": list(capabilities),
        "events": list(events),
        "models": list(models),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local_cli_identity_cli")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("identity", "succeed-json", "would-run"),
    )
    parser.add_argument("--model", default="fixture-haiku")
    parser.add_argument("--report-version", default=DEFAULT_VERSION)
    parser.add_argument("--report-flags", default=",".join(DEFAULT_FLAGS))
    parser.add_argument(
        "--report-capabilities",
        default=",".join(DEFAULT_CAPABILITIES),
    )
    parser.add_argument("--report-events", default=",".join(DEFAULT_EVENTS))
    parser.add_argument("--report-models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--sentinel")
    args = parser.parse_args(argv)
    if args.mode == "identity":
        json.dump(_identity_payload(args), sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    if args.sentinel:
        Path(args.sentinel).write_text("ran\n", encoding="utf-8")
    if args.mode == "would-run":
        print("should-not-run")
        return 0
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "total_cost_usd": 0.0,
                "model": args.model,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

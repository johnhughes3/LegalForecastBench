"""Public CLI for the pinned native lab-core bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legalforecast.multiharness.harvey_lab.core_bridge import (
    LabCoreRequest,
    run_lab_core,
)
from legalforecast.multiharness.harvey_lab.core_runtime import LabCoreRuntime


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register credential-free probing and explicit contributor-funded runs."""
    group = subparsers.add_parser(
        "harvey-lab", help="Use the pinned lab-core 1.1.0 native CLI bridge."
    )
    commands = group.add_subparsers(dest="lab_command")
    for name in ("probe", "run"):
        command = commands.add_parser(
            name,
            help=(
                "Inspect installed CLI/source without credentials."
                if name == "probe"
                else "Run a native solver and explicit judge using provider credit."
            ),
        )
        command.add_argument(
            "--source-root",
            type=Path,
            required=True,
            help="Clean harveyai/harvey-labs checkout at the documented v1.1.0 commit.",
        )
        command.add_argument(
            "--python",
            type=Path,
            required=True,
            help="Python 3.12/3.13 environment containing the pinned lab-core package.",
        )
        command.add_argument(
            "--output-dir",
            type=Path,
            required=True,
            help="Private scratch directory; run requires a fresh path.",
        )
        if name == "probe":
            command.set_defaults(handler=_probe)
            continue
        command.add_argument(
            "--task-id",
            required=True,
            help="Canonical harvey_lab:category/task or upstream category/task ID.",
        )
        command.add_argument(
            "--model",
            required=True,
            help="Upstream provider/model ID; no model alias is guessed.",
        )
        command.add_argument(
            "--judge-model",
            required=True,
            help="Explicit single judge ID; does not default to the paid judge pair.",
        )
        command.add_argument(
            "--run-id",
            required=True,
            help="Measurement identity, mapped to a deterministic upstream run ID.",
        )
        command.add_argument(
            "--max-turns",
            type=int,
            required=True,
            help="Native runtime turn ceiling. This is not a dollar spending cap.",
        )
        command.add_argument(
            "--sandbox-image",
            required=True,
            help="Immutable sha256:... ID of a local native LAB Podman image.",
        )
        command.add_argument(
            "--provider-env",
            action="append",
            default=[],
            help="Provider variable name; repeat for solver/judge credentials.",
        )
        command.add_argument("--reasoning-effort")
        command.add_argument("--timeout-seconds", type=float, default=3600)
        command.set_defaults(handler=_run)


def _probe(args: argparse.Namespace) -> int:
    runtime = LabCoreRuntime(args.source_root, args.python)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(json.dumps(runtime.probe(args.output_dir), sort_keys=True))
    return 0


def _run(args: argparse.Namespace) -> int:
    request = LabCoreRequest(
        task_id=args.task_id,
        model=args.model,
        judge_model=args.judge_model,
        run_id=args.run_id,
        max_turns=args.max_turns,
        sandbox_image=args.sandbox_image,
        provider_env=tuple(args.provider_env),
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.timeout_seconds,
    )
    result = run_lab_core(
        LabCoreRuntime(args.source_root, args.python), request, args.output_dir
    )
    print(json.dumps(result, sort_keys=True))
    return 0

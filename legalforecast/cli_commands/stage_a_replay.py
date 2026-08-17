# pyright: reportPrivateUsage=false

"""Cycle-neutral adapter for the canonical Stage A replay executor."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast


class _ReplayResult(Protocol):
    halted: bool

    def to_record(self) -> dict[str, object]: ...


_EXECUTOR = importlib.metadata.EntryPoint(
    name="candidate-scoped-stage-a-executor",
    value=(
        "legalforecast.ingestion.stage_a_replay_executor.executor:"
        "execute_canonical_stage_a_replay"
    ),
    group="legalforecast.internal",
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the sole production Stage A replay command."""

    replay = subparsers.add_parser(
        "replay-stage-a",
        help="Execute one authenticated candidate-scoped Stage A replay spec.",
        description=(
            "Execute the signed, hashed candidate-scoped Stage A replay spec "
            "through the frozen claim-ontology-v5 unitizer and v4 reviewer. "
            "All candidates, artifacts, models, ceilings, journal identity, "
            "and output paths come from --replay-spec; no ad-hoc execution "
            "flags are accepted."
        ),
    )
    replay.add_argument(
        "--replay-spec",
        type=Path,
        required=True,
        help=(
            "Self-hashed replay-spec artifact containing signed authorization, "
            "candidate set, frozen v5/v4 configuration, ceilings, lineage, "
            "canonical journal identity, and output paths."
        ),
    )
    replay.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Load the heavy verifier stack only after command selection."""

    execute = cast(Callable[[Path], _ReplayResult], _EXECUTOR.load())
    result = execute(cast(Path, args.replay_spec))
    print(json.dumps(result.to_record(), sort_keys=True))
    return 2 if result.halted else 0

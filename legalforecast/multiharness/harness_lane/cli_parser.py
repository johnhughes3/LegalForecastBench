"""``legalforecast multiharness harness`` -- the containerized tools-on lane.

One live run per invocation, by design.  ``multiharness run`` schedules a
matrix, and this lane cannot use it yet, but the shape would be wrong anyway:
each harness needs its own image, its own login, and its own egress
allowlist, so five harnesses are five invocations with five output
directories, joined at report time rather than in one process.

``preflight`` is the only command here that touches a run before it starts,
because only ``preflight`` is honest today -- it answers "would this run
start?" without buying a token.  The flags it takes are the run's full control
surface (harness, manifest, auth profile, task selection, output directory,
egress rules) so that wiring an executing sibling later is a handler, not a
redesign.

``submit`` and ``check-submission`` come from :mod:`.community_submit` and act
on a run that already finished, so a contributor has one place to look for the
whole lane rather than a subcommand here and a module entry point elsewhere.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast._json_io import read_json_object, write_json_object_safe
from legalforecast.immutable_io import ImmutableIOError, ensure_private_directory
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.harness_lane.adapter import ContainerCliAdapter
from legalforecast.multiharness.harness_lane.harnesses import (
    CONTAINER_TOOLS_ON_REGISTRY_NAMES,
)
from legalforecast.multiharness.harness_lane.preflight import (
    default_image_resolver,
    default_proxy_probe,
    run_preflight,
)
from legalforecast.multiharness.harness_vocab import AUTH_PROFILE_NAMES
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.sandbox import BACKEND_DOCKER, BACKEND_PODMAN
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import TaskIndex

PREFLIGHT_REPORT_NAME = "harness-preflight.json"


class _ParserRegistration(Protocol):
    def __call__(self, harness_commands: Any) -> None: ...


# Reached through an entry point rather than an import.  ``community_submit``
# pulls in ``community_intake`` and the publication guardrails, and a static
# edge from this parser would close an import cycle back through
# ``legalforecast.protocol`` -- the same reason ``cli_commands`` reaches its
# verifiers this way.  The subcommands still register eagerly, at parser
# construction, so ``--help`` lists them.
_COMMUNITY_SUBMISSION_PARSERS = importlib.metadata.EntryPoint(
    name="harness-lane-community-submission-parsers",
    value=(
        "legalforecast.multiharness.harness_lane.community_submit:"
        "add_community_submission_parsers"
    ),
    group="legalforecast.internal",
)


def add_harness_parser(commands: Any) -> None:
    """Register the containerized tools-on lane under ``multiharness``."""

    harness = commands.add_parser(
        "harness",
        help="Containerized, tools-on agentic CLI harness lane.",
        description=(
            "Run one agentic CLI per invocation inside a digest-pinned image "
            "with its own local tools live and egress confined to an "
            "allowlist. Results are a separate lane and never merge into the "
            "official benchmark numbers."
        ),
    )
    harness_commands = harness.add_subparsers(dest="harness_command", metavar="COMMAND")
    preflight = harness_commands.add_parser(
        "preflight",
        help="Report whether one harness run would start. Spends nothing.",
        description=(
            "Check the contributor login, the pinned image, the egress sidecar "
            "and the task selection for one harness. No provider call is made "
            "and no container is started."
        ),
    )
    preflight.add_argument(
        "--harness",
        required=True,
        choices=CONTAINER_TOOLS_ON_REGISTRY_NAMES,
        help="Containerized harness registry name.",
    )
    preflight.add_argument(
        "--adapter-manifest",
        type=Path,
        required=True,
        help="Local-CLI adapter manifest JSON for this harness.",
    )
    preflight.add_argument(
        "--auth-profile",
        choices=tuple(sorted(AUTH_PROFILE_NAMES)),
        default="contributor-subscription",
        help="Auth profile for the run. Default runs under your own login.",
    )
    preflight.add_argument("--task-index", type=Path, required=True)
    preflight.add_argument(
        "--selection",
        type=Path,
        help="Selection manifest from 'multiharness tasks select'.",
    )
    preflight.add_argument(
        "--task-id",
        action="append",
        default=[],
        help="Task id to select. Repeatable; ignored with --selection.",
    )
    preflight.add_argument("--output-dir", type=Path, required=True)
    preflight.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="Exact host the harness may reach. Repeatable.",
    )
    preflight.add_argument(
        "--allow-subdomains",
        action="append",
        default=[],
        help="Parent domain whose subdomains the harness may reach. Repeatable.",
    )
    preflight.add_argument(
        "--allow-port",
        action="append",
        type=int,
        default=[],
        help="Allowed egress port. Repeatable. Defaults to 443.",
    )
    preflight.add_argument(
        "--container-backend",
        choices=(BACKEND_DOCKER, BACKEND_PODMAN),
        default=BACKEND_DOCKER,
    )
    preflight.set_defaults(handler=cmd_harness_preflight)
    cast(_ParserRegistration, _COMMUNITY_SUBMISSION_PARSERS.load())(harness_commands)


def cmd_harness_preflight(args: argparse.Namespace) -> int:
    """Write one harness readiness report; exit non-zero if it would not start."""

    output_dir = cast(Path, args.output_dir)
    try:
        ensure_private_directory(output_dir)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc
    adapter = adapter_from_args(args)
    # Named explicitly rather than left to the defaults so a test can replace
    # the one probe that needs a container daemon without faking the report.
    report = run_preflight(
        adapter,
        selected_task_ids=selected_task_ids(args),
        image_resolver=default_image_resolver,
        proxy_probe=default_proxy_probe,
    )
    write_json_object_safe(output_dir / PREFLIGHT_REPORT_NAME, report.to_record())
    for check in report.checks:
        status = "ok" if check.ok else "FAILED"
        print(f"{check.name}: {status} - {check.detail}")
    return 0 if report.ok else 1


def adapter_from_args(args: argparse.Namespace) -> ContainerCliAdapter:
    """Build the lane adapter through the shared registry, never directly."""

    ports = tuple(cast(list[int], args.allow_port))
    adapter = builtin_adapter_registry().get(
        cast(str, args.harness),
        local_cli_manifest=load_lane_manifest(cast(Path, args.adapter_manifest)),
        auth_profile=cast(str, args.auth_profile),
        allow_hosts=tuple(cast(list[str], args.allow_host)),
        allow_subdomains=tuple(cast(list[str], args.allow_subdomains)),
        allow_ports=ports,
        backend=cast(str, args.container_backend),
    )
    if not isinstance(adapter, ContainerCliAdapter):  # pragma: no cover - registry pin
        raise ValueError(f"{args.harness} did not build a containerized adapter")
    return adapter


def load_lane_manifest(path: Path) -> LocalCliAdapterManifest:
    """Load one local-CLI adapter manifest, refusing anything but an object."""

    record = read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"adapter manifest does not exist: {item}",
        non_object_message=lambda item: f"adapter manifest must be an object: {item}",
    )
    return LocalCliAdapterManifest.from_record(record)


def selected_task_ids(args: argparse.Namespace) -> tuple[str, ...]:
    """Resolve the task selection the run would execute, without running it."""

    index = TaskIndex.from_record(
        read_json_object(
            cast(Path, args.task_index),
            error_factory=ValueError,
            missing_message=lambda item: f"task index does not exist: {item}",
            non_object_message=lambda item: f"task index must be an object: {item}",
        )
    )
    selection_path = cast(Path | None, args.selection)
    if selection_path is None:
        task_ids = tuple(cast(list[str], args.task_id))
    else:
        task_ids = _selection_manifest_task_ids(selection_path)
    selection = TaskSelection(task_ids=task_ids, allow_empty=True)
    return tuple(task.task_id for task in selection.select(index).tasks)


def _selection_manifest_task_ids(path: Path) -> tuple[str, ...]:
    record: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    value = record.get("task_ids")
    if not isinstance(value, list):
        raise ValueError("selection manifest task_ids must be a list of strings")
    task_ids: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError("selection manifest task_ids must be non-empty strings")
        task_ids.append(item)
    return tuple(task_ids)

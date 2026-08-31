"""Reach the containerized tools-on lane from ``multiharness run``.

Before this module the run matrix could only schedule ``CommandAdapter``
manifests, so a registered container harness could be *listed* but never
*run*, and the only corpus a run could name was a pre-built task index.  Both
gaps are closed here rather than in ``multiharness/cli.py``, which is a frozen
oversized facade: the parser gains one call, each handler line becomes one
call, and every decision lives in this package beside the adapter it serves.

Two shapes of run are supported and they compose:

* ``--adapter <registry name> --local-cli-manifest <manifest>`` schedules a
  container harness through the same matrix as any command adapter.
* ``--task-source lfb|harvey-lab`` resolves a corpus in place instead of
  requiring ``--task-index``; ``--task-index`` still works unchanged.

One live run stays one provider per invocation --
``validate_provider_environment_scope`` refuses a multi-provider scope by
design -- so five harnesses are five runs with five ``--output-dir`` values,
joined at report time.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.folder_selection import (
    FolderSelection,
    narrow_selection_to_folder,
)
from legalforecast.multiharness.harness_lane.task_sources import (
    TASK_SOURCES,
    ResolvedTaskSource,
    TaskSourceError,
    resolve_task_source,
)
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import SolverInputStore
from legalforecast.multiharness.spec import AdapterManifest, TaskIndex


class HarnessRunArgumentError(ValueError):
    """Raised when the run arguments do not describe a runnable matrix."""


@dataclass(frozen=True, slots=True)
class ResolvedRunInputs:
    """What one ``multiharness run`` invocation will actually iterate over."""

    task_index: TaskIndex
    selection: TaskSelection
    solver_inputs: SolverInputStore | None
    task_source: ResolvedTaskSource | None = None
    folder: FolderSelection | None = None

    def plan_fields(self) -> dict[str, Any]:
        """Return the public corpus record for a dry-run plan, if any."""

        record: dict[str, Any] = {}
        if self.task_source is not None:
            record["task_source"] = self.task_source.to_public_record()
        if self.folder is not None:
            record["folder"] = self.folder.to_public_record()
        return record


def add_harness_lane_run_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the container-harness and task-source options to ``run``."""

    parser.add_argument(
        "--adapter",
        help=(
            "Built-in adapter name from the generic registry, such as a "
            "containerized tools-on harness. Requires --local-cli-manifest."
        ),
    )
    parser.add_argument(
        "--local-cli-manifest",
        type=Path,
        help=(
            "Local-CLI adapter manifest for --adapter. It pins the container "
            "image digest, the argv template, and the tool posture, so there "
            "is deliberately no built-in default."
        ),
    )
    parser.add_argument(
        "--auth-profile",
        help="Auth profile for --adapter. Default is contributor-subscription.",
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="Exact host the harness container may reach. Repeatable.",
    )
    parser.add_argument(
        "--allow-subdomain",
        action="append",
        default=[],
        help="Domain suffix the harness container may reach. Repeatable.",
    )
    parser.add_argument(
        "--allow-port",
        action="append",
        type=int,
        default=[],
        help="TCP port the egress proxy may connect to. Default is 443.",
    )
    parser.add_argument(
        "--container-backend",
        default="docker",
        help="Rootless container backend for --adapter. Default is docker.",
    )
    parser.add_argument(
        "--task-source",
        choices=TASK_SOURCES,
        help=(
            "Resolve the corpus in place instead of passing --task-index: "
            "'lfb' needs --packets, 'harvey-lab' needs --projected-root or "
            "--task-folder."
        ),
    )
    parser.add_argument(
        "--packets",
        type=Path,
        help="Model-packet JSONL for --task-source lfb.",
    )
    parser.add_argument(
        "--projected-root",
        type=Path,
        help=(
            "Projected Harvey LAB layout. Names the corpus for --task-source "
            "harvey-lab and supplies the documents a container harness stages."
        ),
    )


def resolve_run_inputs(args: argparse.Namespace) -> ResolvedRunInputs:
    """Resolve the corpus, the selection, and the private solver-input store."""

    task_index_path = cast(Path | None, getattr(args, "task_index", None))
    source = cast(str | None, getattr(args, "task_source", None))
    solver_input_root = cast(Path | None, args.solver_input_root)
    if (task_index_path is None) == (source is None):
        raise HarnessRunArgumentError(
            "pass exactly one of --task-index or --task-source "
            f"({', '.join(TASK_SOURCES)})"
        )
    if source is not None:
        resolved = _resolved_source(args, source, solver_input_root)
        return ResolvedRunInputs(
            task_index=resolved.task_index,
            selection=resolved.selection,
            solver_inputs=_store(solver_input_root),
            task_source=resolved,
            folder=resolved.folder,
        )
    task_index = TaskIndex.from_record(
        _read_object(cast(Path, task_index_path), "task index")
    )
    selection, folder = narrow_selection_to_folder(
        _selection_from_args(args),
        task_index,
        cast(Path | None, getattr(args, "task_folder", None)),
    )
    return ResolvedRunInputs(
        task_index=task_index,
        selection=selection,
        solver_inputs=_store(solver_input_root),
        folder=folder,
    )


def _selection_from_args(args: argparse.Namespace) -> TaskSelection:
    """Build the selection from an explicit manifest or from the run's flags."""

    selection_path = cast(Path | None, getattr(args, "selection", None))
    if selection_path is not None:
        record = _read_object(selection_path, "selection manifest")
        label = record.get("selection_label")
        if label is not None and not isinstance(label, str):
            raise HarnessRunArgumentError("selection_label must be a string")
        return TaskSelection(
            task_ids=_strings_from(record.get("task_ids"), "task_ids"),
            label=label,
        )
    return TaskSelection(
        families=_strings(args, "family"),
        task_ids=_strings(args, "task_id"),
        case_ids=_strings(args, "case_id"),
        candidate_ids=_strings(args, "candidate_id"),
        ablations=_strings(args, "ablation"),
        modules=_strings(args, "module") + _strings(args, "category"),
        practice_areas=_strings(args, "practice_area"),
        tags=_strings(args, "tag"),
        limit=cast(int | None, args.limit),
        seed=cast(str | None, args.seed),
        allow_empty=cast(bool, args.allow_empty),
        label=cast(str | None, args.label),
    )


def _resolved_source(
    args: argparse.Namespace,
    source: str,
    solver_input_root: Path | None,
) -> ResolvedTaskSource:
    try:
        return resolve_task_source(
            source=source,
            packets=cast(Path | None, getattr(args, "packets", None)),
            projected_root=cast(Path | None, getattr(args, "projected_root", None)),
            task_folder=cast(Path | None, getattr(args, "task_folder", None)),
            task_ids=_strings(args, "task_id"),
            categories=_strings(args, "category") + _strings(args, "module"),
            limit=cast(int | None, args.limit),
            seed=cast(str | None, args.seed),
            label=cast(str | None, args.label),
            solver_input_root=solver_input_root,
        )
    except TaskSourceError as exc:
        raise HarnessRunArgumentError(str(exc)) from exc


def _store(solver_input_root: Path | None) -> SolverInputStore | None:
    if solver_input_root is None:
        return None
    return SolverInputStore.load(solver_input_root)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def build_run_adapters(
    args: argparse.Namespace, *, timeout_seconds: float
) -> tuple[HarnessAdapter, ...]:
    """Return every adapter this run schedules, command and registry alike."""

    from legalforecast.multiharness.command_adapter import CommandAdapter

    command_adapters = tuple(
        CommandAdapter.from_manifest_file(path, timeout_seconds=timeout_seconds)
        for path in _manifest_paths(args)
    )
    name = _registry_adapter_name(args, bool(command_adapters))
    if name is None:
        return command_adapters
    return (*command_adapters, _registry_adapter(args, name))


def run_adapter_manifests(args: argparse.Namespace) -> tuple[AdapterManifest, ...]:
    """Return the public adapter identities without launching anything."""

    manifests = tuple(
        AdapterManifest.from_record(_read_object(path, "adapter manifest"))
        for path in _manifest_paths(args)
    )
    name = _registry_adapter_name(args, bool(manifests))
    if name is None:
        return manifests
    return (*manifests, _registry_adapter(args, name).manifest)


def _manifest_paths(args: argparse.Namespace) -> tuple[Path, ...]:
    value: object = getattr(args, "adapter_manifest", None) or ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise HarnessRunArgumentError("adapter_manifest must be a list of paths")
    return tuple(
        item for item in cast(Sequence[object], value) if isinstance(item, Path)
    )


def _registry_adapter_name(
    args: argparse.Namespace, has_command_adapters: bool
) -> str | None:
    name = cast(str | None, getattr(args, "adapter", None))
    manifest_path = cast(Path | None, getattr(args, "local_cli_manifest", None))
    if name is None:
        if manifest_path is not None:
            raise HarnessRunArgumentError(
                "--local-cli-manifest names the manifest for --adapter; pass "
                "--adapter <registry name> as well"
            )
        if not has_command_adapters:
            raise HarnessRunArgumentError(
                "pass at least one --adapter-manifest or one --adapter"
            )
        return None
    if manifest_path is None:
        raise HarnessRunArgumentError(
            f"--adapter {name} needs --local-cli-manifest: the image digest, "
            "argv template and tool posture come from the manifest, and a "
            "default would run a different program than the record claims"
        )
    return name


def _registry_adapter(args: argparse.Namespace, name: str) -> HarnessAdapter:
    from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest

    manifest_path = cast(Path, args.local_cli_manifest)
    kwargs: dict[str, object] = {
        "local_cli_manifest": LocalCliAdapterManifest.from_record(
            _read_object(manifest_path, "local-CLI adapter manifest")
        ),
        "allow_hosts": _strings(args, "allow_host"),
        "allow_subdomains": _strings(args, "allow_subdomain"),
        "allow_ports": tuple(cast(list[int], getattr(args, "allow_port", []) or [])),
        "backend": cast(str, getattr(args, "container_backend", "docker")),
        "lab_projection_root": cast(Path | None, getattr(args, "projected_root", None)),
    }
    auth_profile = cast(str | None, getattr(args, "auth_profile", None))
    if auth_profile is not None:
        kwargs["auth_profile"] = auth_profile
    return builtin_adapter_registry().get(name, **kwargs)


def _strings_from(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise HarnessRunArgumentError(f"{name} must be a list of strings")
    return tuple(
        item for item in cast(Sequence[object], value) if isinstance(item, str) and item
    )


def _strings(args: argparse.Namespace, name: str) -> tuple[str, ...]:
    return _strings_from(getattr(args, name, None), name)

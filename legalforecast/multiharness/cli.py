"""Argparse command group for the multi-harness benchmark package."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
    write_json_object_safe,
)
from legalforecast.immutable_io import ImmutableIOError, ensure_private_directory
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterCancelled,
)
from legalforecast.multiharness.community import (
    REQUIRED_ATTESTATIONS,
    CommunityPackageConfig,
    package_community_submission,
    validate_submission_file,
)
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.folder_selection import (
    FolderSelectionError,
    select_tasks_from_folder,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EvaluatorRunner,
)
from legalforecast.multiharness.harvey_lab_projected_tasks import (
    DEFAULT_PROJECTED_SUITE_VERSION,
    HarveyLabProjectionTaskLoader,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ROOT_MANIFEST_NAME as PROJECTION_MANIFEST_NAME,
)
from legalforecast.multiharness.harvey_lab_projection import (
    project_harvey_lab_suite,
    remove_projected_tree,
)
from legalforecast.multiharness.release_harness_cli import (
    add_lfb_task_index_arguments,
    lfb_task_index_from_args,
    release_task_index_plan_fields,
)
from legalforecast.multiharness.runner import (
    INCOMPLETE_RUN_POLICIES,
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
    signal_boundary,
    validate_provider_environment_scope,
)
from legalforecast.multiharness.sandbox import (
    BACKEND_DOCKER,
    BACKEND_PODMAN,
    NETWORK_NONE,
    PROVIDER_EGRESS_HOST_ONLY,
    sandbox_policy,
    validate_live_container_policy,
)
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import SolverInputStore
from legalforecast.multiharness.spec import (
    HOST_PROCESS_CONTAINMENT_MODES,
    POSIX_PROCESS_GROUP_CONTAINMENT,
    AdapterManifest,
    ContributorCredit,
    TaskIndex,
)
from legalforecast.multiharness.spend import PricingSnapshot, SpendPolicy
from legalforecast.multiharness.task_loaders import (
    DEFAULT_LAB_SUITE_VERSION,
    HarveyLabTaskLoader,
)
from legalforecast.multiharness.tier0_operator_contract import (
    caller_tier0_roots,
    infisical_evaluator_issuer_secret_loader,
)
from legalforecast.multiharness.tier0_runner import (
    Tier0EvaluatorProvenanceProvider,
    Tier0ExecutableSpec,
    load_approved_issuer_authority,
    load_approved_tier0_approval_authority,
    load_detached_approval,
    load_executable_spec,
    load_spend_artifacts,
    run_tier0,
)
from legalforecast.publication.community_aggregate import (
    CommunityAggregateConfig,
    build_community_aggregate,
)

_CLI_PLAN_SCHEMA_VERSION = "legalforecast.multiharness.cli_plan.v1"
_SELECTION_MANIFEST_SCHEMA_VERSION = "legalforecast.multiharness.selection_manifest.v1"
_REPORT_SCHEMA_VERSION = "legalforecast.multiharness.report.v1"

Tier0ProductionEvaluatorFactory = Callable[
    [Tier0ExecutableSpec, Path, Path, SpendPolicy, PricingSnapshot],
    tuple[EvaluatorRunner, Tier0EvaluatorProvenanceProvider],
]
_tier0_production_evaluator_factory: Tier0ProductionEvaluatorFactory | None = None


def install_tier0_production_evaluator_factory(
    factory: Tier0ProductionEvaluatorFactory,
) -> None:
    """Inject the reviewed paid evaluator/provider seam for an embedded CLI."""

    global _tier0_production_evaluator_factory
    if not callable(factory):
        raise TypeError("Tier-0 production evaluator factory must be callable")
    _tier0_production_evaluator_factory = factory


def add_multiharness_parser(subparsers: Any) -> None:
    """Register the multi-harness command group on the top-level parser."""

    parser = subparsers.add_parser(
        "multiharness",
        help="Run community multi-harness benchmark tasks and adapter checks.",
    )
    commands = parser.add_subparsers(
        dest="multiharness_command",
        metavar="COMMAND",
    )

    tasks = commands.add_parser("tasks", help="Task index and selection commands.")
    task_commands = tasks.add_subparsers(dest="tasks_command", metavar="COMMAND")
    task_index = task_commands.add_parser(
        "index",
        help="Build a canonical task index from LFB packets or Harvey LAB tasks.",
    )
    task_index.add_argument(
        "--suite",
        choices=("lfb", "harvey-lab"),
        required=True,
        help="Source suite to index.",
    )
    add_lfb_task_index_arguments(task_index)
    task_index.add_argument(
        "--lab-root",
        type=Path,
        help=(
            "Raw pinned Harvey LAB checkout for --suite harvey-lab. Maintainer "
            "path: it reads the evaluator-private task.json. Contributors use "
            "--projected-root."
        ),
    )
    task_index.add_argument(
        "--projected-root",
        type=Path,
        help=(
            "Projected Harvey LAB layout from 'tasks project' for --suite "
            "harvey-lab. Every listed file is re-hashed before indexing."
        ),
    )
    task_index.add_argument("--output", type=Path, required=True)
    task_index.add_argument(
        "--solver-input-root",
        type=Path,
        help=(
            "Fresh private directory for exact solver-visible LFB prompts. "
            "Required before live provider execution and never publishable."
        ),
    )
    task_index.add_argument("--suite-version")
    task_index.add_argument("--index-id")
    task_index.add_argument("--selection-namespace")
    task_index.add_argument("--dry-run", action="store_true")
    task_index.set_defaults(handler=_cmd_tasks_index)

    task_project = task_commands.add_parser(
        "project",
        help="Project solver-visible Harvey LAB bytes into a contributor layout.",
        description=(
            "Split a pinned Harvey LAB checkout into a solver-visible projected "
            "layout and a private evaluator root. The projected root is the only "
            "contributor input the harness accepts; the private root holds the "
            "gold criteria and is never solver input and never published."
        ),
    )
    task_project.add_argument(
        "--lab-root",
        type=Path,
        required=True,
        help="Your Harvey LAB checkout at the recorded pin.",
    )
    task_project.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Solver-visible projected root to create.",
    )
    task_project.add_argument(
        "--evaluator-private-dir",
        type=Path,
        required=True,
        help="Private evaluator root to create. Never solver input, never published.",
    )
    task_project.add_argument(
        "--category",
        action="append",
        dest="categories",
        metavar="CATEGORY",
        help="Project one Harvey LAB category. Repeatable.",
    )
    task_project.add_argument(
        "--task-id",
        action="append",
        dest="task_ids",
        metavar="LAB_TASK_ID",
        help="Project one task by its path under tasks/. Repeatable.",
    )
    task_project.add_argument(
        "--refuse-unsupported-tasks",
        action="store_true",
        help=(
            "Fail instead of skipping tasks whose upstream shape this projection "
            "cannot carry yet. Default reports them and projects the rest."
        ),
    )
    task_project.add_argument("--dry-run", action="store_true")
    task_project.set_defaults(handler=_cmd_tasks_project)

    task_select = task_commands.add_parser(
        "select",
        help="Select a deterministic task shard from a canonical task index.",
    )
    task_select.add_argument("--index", type=Path, required=True)
    task_select.add_argument("--output", type=Path, required=True)
    _add_selection_arguments(task_select)
    task_select.add_argument("--dry-run", action="store_true")
    task_select.set_defaults(handler=_cmd_tasks_select)

    adapters = commands.add_parser("adapters", help="Adapter inspection commands.")
    adapter_commands = adapters.add_subparsers(
        dest="adapters_command",
        metavar="COMMAND",
    )
    listed = adapter_commands.add_parser(
        "list",
        help="List built-in adapter names from the generic registry.",
    )
    listed.add_argument("--output", type=Path, required=True)
    listed.add_argument("--dry-run", action="store_true")
    listed.set_defaults(handler=_cmd_adapters_list)

    inspect = adapter_commands.add_parser(
        "inspect",
        help="Inspect a built-in or command-manifest adapter.",
    )
    adapter_source = inspect.add_mutually_exclusive_group(required=True)
    adapter_source.add_argument(
        "--adapter",
        help="Built-in adapter name from the generic registry.",
    )
    adapter_source.add_argument(
        "--adapter-manifest",
        type=Path,
        help="Command adapter manifest JSON to inspect.",
    )
    inspect.add_argument("--output-dir", type=Path, required=True)
    inspect.add_argument(
        "--lab-command",
        nargs="+",
        help="Harvey LAB command argv for --adapter harvey-lab.",
    )
    inspect.add_argument("--lab-root", type=Path)
    inspect.add_argument("--timeout-seconds", type=float, default=300.0)
    inspect.add_argument("--dry-run", action="store_true")
    inspect.set_defaults(handler=_cmd_adapters_inspect)

    conformance = commands.add_parser(
        "conformance",
        help="Run the no-provider adapter conformance suite.",
    )
    conformance.add_argument("--adapter-manifest", type=Path, required=True)
    conformance.add_argument("--output-dir", type=Path, required=True)
    conformance.add_argument("--resume", action="store_true")
    conformance.add_argument("--timeout-seconds", type=float, default=300.0)
    conformance.add_argument("--dry-run", action="store_true")
    conformance.set_defaults(handler=_cmd_conformance)

    run = commands.add_parser(
        "run",
        help="Run or dry-run a selected task matrix through command adapters.",
    )
    run.add_argument("--task-index", type=Path, required=True)
    run.add_argument(
        "--solver-input-root",
        type=Path,
        help=(
            "Private solver-input store produced by tasks index. Required with "
            "--live-tool-container."
        ),
    )
    run.add_argument(
        "--adapter-manifest",
        type=Path,
        action="append",
        required=True,
        help="Command adapter manifest. Repeat for multiple adapters.",
    )
    run.add_argument(
        "--model-key",
        action="append",
        required=True,
        help="Model/provider key to schedule. Repeat for multiple models.",
    )
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--run-id", default="multiharness-run")
    run.add_argument("--selection", type=Path)
    _add_selection_arguments(run)
    run.add_argument(
        "--sandbox-backend",
        choices=(BACKEND_DOCKER, BACKEND_PODMAN),
        default=BACKEND_DOCKER,
    )
    run.add_argument("--sandbox-image", default="python:3.12-slim")
    run.add_argument("--sandbox-policy-id", default="multiharness-cli")
    run.add_argument("--sandbox-timeout-seconds", type=int, default=300)
    run.add_argument(
        "--host-process-containment",
        choices=tuple(sorted(HOST_PROCESS_CONTAINMENT_MODES)),
        default=POSIX_PROCESS_GROUP_CONTAINMENT,
        help=(
            "Containment mode for the host command adapter. Default is posix "
            "process-group. The systemd scope/cgroup-v2 mode fails closed when "
            "unavailable."
        ),
    )
    run.add_argument(
        "--live-tool-container",
        action="store_true",
        help=(
            "Execute adapter tool calls in a local network-disabled container. "
            "Requires a digest-pinned image and an adapter that advertises the "
            "versioned tool protocol; provider credentials remain host-only."
        ),
    )
    run.add_argument(
        "--provider-env-var",
        action="append",
        default=[],
        help="Provider env var to allow into the host adapter process.",
    )
    run.add_argument(
        "--allow-provider-egress",
        action="store_true",
        help="Record provider API egress as allowed for host adapter processes.",
    )
    run.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue a previous run in this output directory. Completed tasks "
            "are skipped; a changed solver, config, or policy is refused."
        ),
    )
    run.add_argument(
        "--incomplete-run-policy",
        choices=tuple(sorted(INCOMPLETE_RUN_POLICIES)),
        default="record_failure",
    )
    run.add_argument("--timeout-seconds", type=float, default=300.0)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=_cmd_run)

    tier0 = commands.add_parser(
        "tier0",
        help="Execute the hash-bound paired Harvey LAB Tier-0 smoke.",
        description=(
            "Run the committed executable-spec artifact in its frozen opaque "
            "order. Model, adapter, command, timeout, and settings are loaded "
            "from the spec; no run-varying execution flags are accepted."
        ),
    )
    tier0_commands = tier0.add_subparsers(dest="tier0_command", metavar="COMMAND")
    tier0_run = tier0_commands.add_parser(
        "run",
        help="Run both frozen Tier-0 arms and emit a private/public archive.",
    )
    tier0_run.add_argument("--spec", type=Path, required=True)
    tier0_run.add_argument("--spec-sha256", required=True)
    tier0_run.add_argument("--approval", type=Path, required=True)
    tier0_run.set_defaults(handler=_cmd_tier0_run)
    tier0_validate = tier0_commands.add_parser(
        "validate",
        help="Validate the frozen executable spec and its deterministic sidecars.",
    )
    tier0_validate.add_argument("--spec", type=Path, required=True)
    tier0_validate.add_argument("--spec-sha256", required=True)
    tier0_validate.add_argument("--approval", type=Path, required=True)
    tier0_validate.set_defaults(handler=_cmd_tier0_validate)
    tier0_install = tier0_commands.add_parser(
        "install-evaluator-wrapper",
        help="Install the pinned harvey-lab-eval entrypoint and probe it.",
        description=(
            "Copy the committed evaluator wrapper byte-for-byte into an "
            "operator-supplied directory on PATH, then run the credential-free "
            "capability probe against the installed bytes. The printed digest "
            "is the value a Tier-0 executable spec must pin."
        ),
    )
    tier0_install.add_argument("--bin-dir", type=Path, required=True)
    tier0_install.add_argument("--scratch-root", type=Path, required=True)
    tier0_install.add_argument("--output", type=Path, required=True)
    tier0_install.add_argument("--overwrite", action="store_true")
    tier0_install.set_defaults(handler=_cmd_tier0_install_evaluator_wrapper)
    tier0_mint = tier0_commands.add_parser(
        "mint",
        help="Deterministically mint the Tier-0 spec and its spend sidecars.",
        description=(
            "Regenerate the executable spec, dated pricing snapshot, and "
            "spend policy from committed inputs. The same inputs always "
            "produce the same bytes, so a reviewer can recompute every hash "
            "the freeze names."
        ),
    )
    tier0_mint.add_argument("--output-dir", type=Path, required=True)
    tier0_mint.add_argument(
        "--private-task-json",
        type=Path,
        required=True,
        help=(
            "Pinned upstream task.json. Hash-verified before use; supplies the "
            "evaluator-private criterion IDs the judge ceilings must carry."
        ),
    )
    tier0_mint.add_argument(
        "--native-thin-manifest",
        type=Path,
        required=True,
        help=(
            "JSON identity of the pinned native-thin solver, including the "
            "budget argument its command genuinely enforces."
        ),
    )
    tier0_mint.add_argument(
        "--evaluator-wrapper-sha256",
        help=(
            "Digest of the installed harvey-lab-eval. Defaults to the "
            "committed wrapper bytes, which install-evaluator-wrapper copies "
            "verbatim."
        ),
    )
    tier0_mint.set_defaults(handler=_cmd_tier0_mint)

    report = commands.add_parser(
        "report",
        help="Summarize a multi-harness run directory as public JSON.",
    )
    report.add_argument("--run-dir", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.set_defaults(handler=_cmd_report)

    community = commands.add_parser(
        "community",
        help="Community submission packaging and aggregation commands.",
    )
    community_commands = community.add_subparsers(
        dest="community_command",
        metavar="COMMAND",
    )
    package = community_commands.add_parser(
        "package",
        help="Plan a PR-ready community submission package.",
    )
    package.add_argument("--run-dir", type=Path, required=True)
    package.add_argument("--output-dir", type=Path, required=True)
    package.add_argument("--submission-id")
    package.add_argument("--conformance-report", type=Path)
    package.add_argument("--submitter-name")
    package.add_argument("--submitter-github")
    package.add_argument("--run-operator-name")
    package.add_argument("--adapter-author-name")
    package.add_argument("--task-source-credit-name")
    package.add_argument("--benchmark-credit-name")
    package.add_argument("--compute-sponsor-name")
    package.add_argument("--attestation", action="append", default=[])
    package.add_argument(
        "--acknowledge-required-attestations",
        action="store_true",
        help=(
            "Include all required non-official/private-material/rights/terms "
            "attestations."
        ),
    )
    package.add_argument("--hf-upload-plan", action="store_true")
    package.add_argument("--dry-run", action="store_true")
    package.set_defaults(handler=_cmd_community_package)

    validate = community_commands.add_parser(
        "validate-submission",
        help="Plan validation for a community submission manifest.",
    )
    validate.add_argument("--submission", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    validate.add_argument("--dry-run", action="store_true")
    validate.set_defaults(handler=_cmd_community_validate_submission)

    aggregate = community_commands.add_parser(
        "aggregate",
        help="Plan aggregation of reviewed community submissions.",
    )
    aggregate.add_argument("--submissions-dir", type=Path, required=True)
    aggregate.add_argument("--output-dir", type=Path, required=True)
    aggregate.add_argument("--dry-run", action="store_true")
    aggregate.set_defaults(handler=_cmd_community_aggregate)


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Harvey LAB category (same selector as --module).",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--candidate-id", action="append", default=[])
    parser.add_argument("--ablation", action="append", default=[])
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--practice-area", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument(
        "--task-folder",
        type=Path,
        help=(
            "Projected task folder with projection-manifest.json. "
            "Unrecognized or tampered bytes are refused."
        ),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--label")


def _cmd_tasks_index(args: argparse.Namespace) -> int:
    output = cast(Path, args.output)
    suite = _required_str_arg(args, "suite")
    if cast(bool, args.dry_run):
        write_json_object(
            output,
            {
                "schema_version": _CLI_PLAN_SCHEMA_VERSION,
                "command": "tasks index",
                "dry_run": True,
                "suite": suite,
                "input": _optional_path_record(cast(Path | None, args.input)),
                **release_task_index_plan_fields(args),
                "lab_root": _optional_path_record(cast(Path | None, args.lab_root)),
                "projected_root": _optional_path_record(
                    cast(Path | None, args.projected_root)
                ),
                "suite_version": cast(str | None, args.suite_version),
                "index_id": cast(str | None, args.index_id),
                "selection_namespace": cast(str | None, args.selection_namespace),
                "solver_input_store_requested": args.solver_input_root is not None,
            },
        )
        return 0

    task_index = _task_index_from_args(args)
    write_json_object(output, task_index.to_record())
    _cli_note(f"Wrote {output} ({len(task_index.tasks)} task(s)).")
    return 0


def _cmd_tasks_project(args: argparse.Namespace) -> int:
    lab_root = cast(Path, args.lab_root)
    categories = _str_tuple_arg(args, "categories")
    task_ids = _str_tuple_arg(args, "task_ids")
    selected = _discover_lab_task_ids(
        lab_root, categories=categories, task_ids=task_ids
    )
    if cast(bool, args.dry_run):
        _cli_note(
            f"Dry run: {len(selected)} Harvey LAB task(s) matched; nothing written."
        )
        for lab_task_id in selected:
            _cli_note(f"  {lab_task_id}")
        return 0

    output_dir = cast(Path, args.output_dir)
    private_dir = cast(Path, args.evaluator_private_dir)
    for label, path in (
        ("--output-dir", output_dir),
        ("--evaluator-private-dir", private_dir),
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(
                f"{label} {path} already exists and a projection writes a fresh "
                "tree. Projected files are sealed read-only, so remove it with: "
                f"chmod -R u+w {path} && rm -rf {path}"
            )
    try:
        result = project_harvey_lab_suite(
            source_root=lab_root,
            solver_root=output_dir,
            evaluator_private_root=private_dir,
            lab_task_ids=selected,
            skip_unsupported_tasks=not cast(bool, args.refuse_unsupported_tasks),
        )
    except BaseException:
        # A partial projection is sealed read-only too. Leaving it behind would
        # make the obvious retry fail on "must be a fresh, absent path".
        remove_projected_tree(output_dir)
        remove_projected_tree(private_dir)
        raise
    _cli_note(
        f"Projected {len(result.tasks)} of {len(selected)} matched Harvey LAB task(s)."
    )
    if result.skipped:
        _cli_note(
            f"Skipped {len(result.skipped)} task(s) whose upstream shape this "
            "projection cannot carry yet (GitHub #842):"
        )
        for item in result.skipped:
            _cli_note(f"  {item.lab_task_id}: {item.reason}")
    _cli_note(f"Wrote {result.solver_root / PROJECTION_MANIFEST_NAME}.")
    _cli_note(
        f"Evaluator-private bytes are in {result.evaluator_private_root}. "
        "Do not publish them and do not pass them to a solver."
    )
    return 0


def _discover_lab_task_ids(
    lab_root: Path,
    *,
    categories: tuple[str, ...],
    task_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Resolve --category / --task-id against the checkout, naming what missed."""

    tasks_root = lab_root / "tasks"
    if not tasks_root.is_dir():
        raise ValueError(f"Harvey LAB root is missing tasks/: {tasks_root}")
    discovered = tuple(
        sorted(
            path.parent.relative_to(tasks_root).as_posix()
            for path in tasks_root.rglob("task.json")
            if path.is_file() and not path.is_symlink()
        )
    )
    if not discovered:
        raise ValueError(
            f"Harvey LAB tasks directory has no task.json files: {tasks_root}"
        )
    if not categories and not task_ids:
        return discovered

    known = set(discovered)
    missing_ids = sorted(set(task_ids) - known)
    if missing_ids:
        raise ValueError(
            f"Harvey LAB task id(s) were not found: {', '.join(missing_ids)}"
        )
    available = sorted({item.split("/", 1)[0] for item in discovered})
    missing_categories = sorted(set(categories) - set(available))
    if missing_categories:
        raise ValueError(
            f"Harvey LAB category/categories were not found: "
            f"{', '.join(missing_categories)}. Available: {', '.join(available)}"
        )
    wanted = set(task_ids)
    wanted.update(
        item for item in discovered if item.split("/", 1)[0] in set(categories)
    )
    return tuple(sorted(wanted))


def _cmd_tasks_select(args: argparse.Namespace) -> int:
    task_index = _load_task_index(cast(Path, args.index))
    selection = _apply_folder_selection(
        _selection_from_args(args),
        task_index,
        cast(Path | None, args.task_folder),
    )
    output = cast(Path, args.output)
    write_json_object(
        output,
        _selection_manifest(
            task_index=task_index,
            selection=selection,
            dry_run=cast(bool, args.dry_run),
        ),
    )
    _cli_note(f"Wrote {output}.")
    return 0


def _ensure_cli_private_directory(path: Path) -> Path:
    try:
        return ensure_private_directory(path)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc


def _cmd_adapters_list(args: argparse.Namespace) -> int:
    output = cast(Path, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_object(
        output,
        {
            "schema_version": _CLI_PLAN_SCHEMA_VERSION,
            "command": "adapters list",
            "dry_run": cast(bool, args.dry_run),
            "adapters": list(builtin_adapter_registry().known_names()),
        },
    )
    return 0


def _cmd_adapters_inspect(args: argparse.Namespace) -> int:
    adapter_name = cast(str | None, args.adapter)
    if adapter_name is not None:
        builtin_adapter_registry().require_known(adapter_name)
    output_dir = cast(Path, args.output_dir)
    _ensure_cli_private_directory(output_dir)
    if cast(bool, args.dry_run):
        write_json_object_safe(
            output_dir / "adapter-inspect-plan.json",
            {
                "schema_version": _CLI_PLAN_SCHEMA_VERSION,
                "command": "adapters inspect",
                "dry_run": True,
                "adapter_source": _adapter_source_record(args),
                "output_dir": output_dir.as_posix(),
            },
        )
        return 0

    adapter = _load_adapter(args)
    write_json_object_safe(
        output_dir / "adapter-manifest.json", adapter.manifest.to_record()
    )
    capabilities_dir = _ensure_cli_private_directory(output_dir / "capabilities")
    capabilities = adapter.capabilities(capabilities_dir)
    write_json_object_safe(
        output_dir / "adapter-capabilities.json",
        capabilities.to_record(),
    )
    _cli_note(f"Wrote {output_dir / 'adapter-capabilities.json'}.")
    return 0


def _cmd_conformance(args: argparse.Namespace) -> int:
    adapter_manifest = cast(Path, args.adapter_manifest)
    output_dir = cast(Path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if cast(bool, args.dry_run):
        write_json_object(
            output_dir / "conformance-plan.json",
            {
                "schema_version": _CLI_PLAN_SCHEMA_VERSION,
                "command": "conformance",
                "dry_run": True,
                "adapter_manifest": adapter_manifest.as_posix(),
                "resume": cast(bool, args.resume),
                "timeout_seconds": cast(float, args.timeout_seconds),
            },
        )
        return 0

    run_adapter_conformance(
        adapter_manifest_path=adapter_manifest,
        output_dir=output_dir,
        resume=cast(bool, args.resume),
        timeout_seconds=cast(float, args.timeout_seconds),
    )
    _cli_note(f"Wrote {output_dir / 'conformance-report.json'}.")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        with signal_boundary():
            return _cmd_run_guarded(args)
    except (CommandAdapterCancelled, KeyboardInterrupt):
        print(
            "Interrupted before any task started. This is a partial run, not a crash. "
            "Resume with the same command plus --resume.",
            file=sys.stderr,
        )
        return 130


def _cmd_run_guarded(args: argparse.Namespace) -> int:
    task_index = _load_task_index(cast(Path, args.task_index))
    solver_input_root = cast(Path | None, args.solver_input_root)
    solver_inputs = (
        SolverInputStore.load(solver_input_root)
        if solver_input_root is not None
        else None
    )
    selection = _selection_from_run_args(args)
    selection = _apply_folder_selection(
        selection,
        task_index,
        cast(Path | None, args.task_folder),
    )
    output_dir = cast(Path, args.output_dir)
    _ensure_cli_private_directory(output_dir)
    manifests = _adapter_manifests_from_paths(_path_tuple_arg(args, "adapter_manifest"))
    policy = _sandbox_policy_from_args(args)
    if cast(bool, args.live_tool_container):
        if solver_inputs is None:
            raise ValueError(
                "--solver-input-root is required with --live-tool-container"
            )
        validate_live_container_policy(policy)
    validate_provider_environment_scope(
        sandbox_policy=policy,
        adapter_count=len(manifests),
        model_count=len(_str_tuple_arg(args, "model_key")),
    )
    if cast(bool, args.dry_run):
        write_json_object_safe(
            output_dir / "run-plan.json",
            _run_plan_record(
                args=args,
                task_index=task_index,
                selection=selection,
                manifests=manifests,
                policy_record=policy.to_record(),
                solver_inputs=solver_inputs,
            ),
        )
        return 0
    adapters = tuple(
        CommandAdapter.from_manifest_file(
            path,
            timeout_seconds=cast(float, args.timeout_seconds),
        )
        for path in _path_tuple_arg(args, "adapter_manifest")
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=adapters,
            model_configs=tuple(
                ModelConfig(model_key=model_key)
                for model_key in _str_tuple_arg(args, "model_key")
            ),
            sandbox_policy=policy,
            output_dir=output_dir,
            selection=selection,
            run_id=_required_str_arg(args, "run_id"),
            resume=cast(bool, args.resume),
            incomplete_run_policy=_required_str_arg(args, "incomplete_run_policy"),
            container_execution=(
                "live_tools" if cast(bool, args.live_tool_container) else "plan_only"
            ),
            solver_inputs=solver_inputs,
        )
    )
    if run.interrupted:
        completed = sum(1 for row in run.rows if row.result.status == "succeeded")
        print(
            f"Interrupted after {completed} completed task(s). "
            "This is a partial run, not a crash. Resume with the same command "
            "plus --resume.",
            file=sys.stderr,
        )
        return 130
    succeeded = sum(1 for row in run.rows if row.result.status == "succeeded")
    _cli_note(
        f"Run completed ({succeeded}/{len(run.rows)} succeeded). "
        f"Wrote {output_dir / 'run-progress.json'}."
    )
    return 0


def _cmd_tier0_run(args: argparse.Namespace) -> int:
    """Execute only the immutable Tier-0 spec/approval pair."""

    spec, spec_sha256 = load_executable_spec(
        cast(Path, args.spec),
        cast(str, args.spec_sha256),
    )
    approval_authority = load_approved_tier0_approval_authority()
    evaluator_authority = load_approved_issuer_authority(
        secret_loader=infisical_evaluator_issuer_secret_loader
    )
    approval = load_detached_approval(
        cast(Path, args.approval),
        spec_sha256=spec_sha256,
        authority=approval_authority,
    )
    if spec.pricing_snapshot_sha256 is None and approval.status == "provider_free":
        spend_policy = None
        pricing_snapshot = None
    else:
        spend_policy, pricing_snapshot = load_spend_artifacts(
            cast(Path, args.spec), spec
        )
    source_root, private_root, archive_root = caller_tier0_roots()
    if spend_policy is None or pricing_snapshot is None:
        evaluator_runner = None
        evaluator_provenance_provider = None
    else:
        factory = _tier0_production_evaluator_factory
        if factory is None:
            # Install the single supported production adapter rather than
            # refusing outright. An embedding runtime that already installed a
            # reviewed factory keeps it; nothing here selects between adapters,
            # so no run-varying input escapes the frozen spec hash.
            from legalforecast.multiharness.tier0_production_factory import (
                install_supported_production_factory,
            )

            install_supported_production_factory()
            factory = _tier0_production_evaluator_factory
        if factory is None:
            raise ValueError(
                "paid Tier-0 execution requires an injected reviewed production "
                "evaluator/provider adapter"
            )
        evaluator_runner, evaluator_provenance_provider = factory(
            spec,
            cast(Path, args.spec).resolve(),
            private_root,
            spend_policy,
            pricing_snapshot,
        )
    result = run_tier0(
        spec=spec,
        spec_sha256=spec_sha256,
        approval=approval,
        source_root=source_root,
        private_root=private_root,
        archive_root=archive_root,
        approval_authority=approval_authority,
        evaluator_authority=evaluator_authority,
        spend_policy=spend_policy,
        pricing_snapshot=pricing_snapshot,
        evaluator_runner=evaluator_runner,
        evaluator_provenance_provider=evaluator_provenance_provider,
    )
    _cli_note(
        f"Tier-0 run completed ({'matched' if result.matched else 'system-bundle'}); "
        f"wrote {result.archive_manifest}."
    )
    return 0


def _cmd_tier0_install_evaluator_wrapper(args: argparse.Namespace) -> int:
    """Install the pinned evaluator wrapper and record its probed identity."""

    from legalforecast.multiharness.tier0_evaluator_wrapper import (
        install_evaluator_wrapper,
    )

    installed = install_evaluator_wrapper(
        cast(Path, args.bin_dir),
        scratch_root=cast(Path, args.scratch_root),
        overwrite=cast(bool, args.overwrite),
    )
    write_json_object(cast(Path, args.output), installed.to_record())
    _cli_note(
        f"Installed {installed.install_path.name} "
        f"({installed.wrapper_version}); pin evaluator_wrapper_sha256 to "
        f"{installed.wrapper_sha256}."
    )
    return 0


def _cmd_tier0_mint(args: argparse.Namespace) -> int:
    """Mint the executable spec and its deterministic spend sidecars."""

    from legalforecast.multiharness.tier0_mint import (
        NativeThinArmInput,
        criterion_ids_from_private_task,
        mint_tier0_artifacts,
    )

    manifest = _read_json(cast(Path, args.native_thin_manifest), "native-thin manifest")
    native_thin = NativeThinArmInput(
        executable=_required_record_str(manifest, "executable"),
        executable_sha256=_required_record_str(manifest, "executable_sha256"),
        executable_version=_required_record_str(manifest, "executable_version"),
        version_probe_args=_record_str_tuple(manifest, "version_probe_args"),
        command=_record_str_tuple(manifest, "command"),
        budget_argument=_required_record_str(manifest, "budget_argument"),
    )
    minted = mint_tier0_artifacts(
        cast(Path, args.output_dir),
        criterion_ids=criterion_ids_from_private_task(
            cast(Path, args.private_task_json)
        ),
        native_thin=native_thin,
        evaluator_wrapper_sha256=cast(str | None, args.evaluator_wrapper_sha256),
    )
    _cli_note(
        f"Minted {minted.spec_path.name} and its sidecars. "
        f"Spec SHA-256 {minted.spec_sha256}; pricing "
        f"{minted.pricing_snapshot_sha256}; policy {minted.spend_policy_sha256}. "
        "These artifacts contain evaluator-private criterion IDs and must stay "
        "outside the public repository."
    )
    return 0


def _cmd_tier0_validate(args: argparse.Namespace) -> int:
    spec, spec_sha256 = load_executable_spec(
        cast(Path, args.spec), cast(str, args.spec_sha256)
    )
    approval_authority = load_approved_tier0_approval_authority()
    load_detached_approval(
        cast(Path, args.approval),
        spec_sha256=spec_sha256,
        authority=approval_authority,
    )
    load_spend_artifacts(cast(Path, args.spec), spec)
    _cli_note(f"Tier-0 executable spec and sidecars validated ({spec_sha256}).")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    run_dir = cast(Path, args.run_dir)
    rows = read_jsonl_objects(
        run_dir / "row-results.jsonl",
        error_factory=ValueError,
        missing_message=lambda path: f"row results do not exist: {path}",
        non_object_message=lambda path, line: (
            f"row results row {line} in {path} must be an object"
        ),
    )
    manifest = _read_json(run_dir / "run-manifest.json", "run manifest")
    status_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    adapter_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    for row in rows:
        status_counts[_required_record_str(row, "status")] += 1
        family_counts[_required_record_str(row, "family")] += 1
        adapter_counts[_required_record_str(row, "adapter_id")] += 1
        model_counts[_required_record_str(row, "model_key")] += 1
    write_json_object(
        cast(Path, args.output),
        {
            "schema_version": _REPORT_SCHEMA_VERSION,
            "run_id": _required_record_str(manifest, "run_id"),
            "selection_sha256": _required_record_str(manifest, "selection_sha256"),
            "row_count": len(rows),
            "status_counts": _counter_record(status_counts),
            "family_counts": _counter_record(family_counts),
            "adapter_counts": _counter_record(adapter_counts),
            "model_counts": _counter_record(model_counts),
        },
    )
    return 0


def _cmd_community_package(args: argparse.Namespace) -> int:
    output_dir = cast(Path, args.output_dir)
    if cast(bool, args.dry_run):
        _ensure_cli_private_directory(output_dir)
        write_json_object(
            output_dir / "community-package-plan.json",
            {
                "schema_version": _CLI_PLAN_SCHEMA_VERSION,
                "command": "community package",
                "dry_run": True,
                "run_dir": cast(Path, args.run_dir).as_posix(),
                "submission_id": cast(str | None, args.submission_id),
                "hf_upload_plan": cast(bool, args.hf_upload_plan),
                "required_attestations": sorted(REQUIRED_ATTESTATIONS),
                "expected_outputs": [
                    "submission.json",
                    "public-summary.json",
                    "conformance-report.json",
                    "selection-manifest.json",
                    "artifact-manifest.json",
                ],
            },
        )
        return 0
    package_community_submission(_community_package_config_from_args(args))
    _cli_note(f"Wrote {output_dir / 'submission.json'}.")
    return 0


def _cmd_community_validate_submission(args: argparse.Namespace) -> int:
    submission = cast(Path, args.submission)
    write_json_object(
        cast(Path, args.output),
        {
            "schema_version": _CLI_PLAN_SCHEMA_VERSION,
            "command": "community validate-submission",
            "dry_run": cast(bool, args.dry_run),
            "submission": submission.as_posix(),
            "status": "planned" if cast(bool, args.dry_run) else "passed",
            "checks": _community_validation_checks(),
        },
    )
    if not cast(bool, args.dry_run):
        validate_submission_file(submission)
    _cli_note(f"Wrote {cast(Path, args.output)}.")
    return 0


def _cmd_community_aggregate(args: argparse.Namespace) -> int:
    output_dir = cast(Path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not cast(bool, args.dry_run):
        build_community_aggregate(
            CommunityAggregateConfig(
                submissions_dir=cast(Path, args.submissions_dir),
                output_dir=output_dir,
            )
        )
        return 0
    write_json_object(
        output_dir / "community-aggregate-plan.json",
        {
            "schema_version": _CLI_PLAN_SCHEMA_VERSION,
            "command": "community aggregate",
            "dry_run": True,
            "submissions_dir": cast(Path, args.submissions_dir).as_posix(),
            "expected_outputs": [
                "community/registry/submissions.jsonl",
                "community/registry/task-coverage.jsonl",
                "community/registry/contributors.json",
                "community/registry/site-summary.json",
            ],
        },
    )
    return 0


def _community_package_config_from_args(
    args: argparse.Namespace,
) -> CommunityPackageConfig:
    submitter_name = _required_optional_str_arg(args, "submitter_name")
    benchmark_name = _required_optional_str_arg(args, "benchmark_credit_name")
    contributors = [
        ContributorCredit(
            role="run_operator",
            name=_required_optional_str_arg(args, "run_operator_name"),
        ),
        ContributorCredit(
            role="adapter_author",
            name=_required_optional_str_arg(args, "adapter_author_name"),
        ),
        ContributorCredit(
            role="task_source",
            name=_required_optional_str_arg(args, "task_source_credit_name"),
        ),
        ContributorCredit(
            role="benchmark_infrastructure",
            name=benchmark_name,
        ),
    ]
    compute_sponsor = cast(str | None, args.compute_sponsor_name)
    if compute_sponsor is not None and compute_sponsor.strip():
        contributors.append(
            ContributorCredit(role="compute_sponsor", name=compute_sponsor)
        )
    attestations = set(_str_tuple_arg(args, "attestation"))
    if cast(bool, args.acknowledge_required_attestations):
        attestations.update(REQUIRED_ATTESTATIONS)
    return CommunityPackageConfig(
        run_dir=cast(Path, args.run_dir),
        output_dir=cast(Path, args.output_dir),
        submission_id=_community_submission_id(args),
        submitter=ContributorCredit(
            role="submitter",
            name=submitter_name,
            identifiers=_submitter_identifiers(args),
        ),
        contributors=tuple(contributors),
        benchmark_credit=(
            ContributorCredit(role="benchmark_infrastructure", name=benchmark_name),
        ),
        attestations=tuple(sorted(attestations)),
        conformance_report_path=cast(Path | None, args.conformance_report),
        hf_upload_plan=cast(bool, args.hf_upload_plan),
    )


def _community_submission_id(args: argparse.Namespace) -> str:
    value = cast(str | None, args.submission_id)
    if value is not None and value.strip():
        return value
    operator_slug = (
        _required_optional_str_arg(
            args,
            "run_operator_name",
        )
        .lower()
        .replace(" ", "-")
    )
    return f"{operator_slug}-submission"


def _submitter_identifiers(args: argparse.Namespace) -> dict[str, str]:
    github = cast(str | None, args.submitter_github)
    if github is None or not github.strip():
        return {}
    return {"github": github}


def _required_optional_str_arg(args: argparse.Namespace, name: str) -> str:
    value = cast(str | None, getattr(args, name))
    if value is None or not value.strip():
        raise ValueError(f"--{name.replace('_', '-')} is required")
    return value


def _community_validation_checks() -> list[str]:
    return [
        "required attestations",
        "artifact hashes",
        "safe public paths",
        "publication guardrails",
        "deprecated taxonomy",
        "shard compatibility",
        "contributor credits",
    ]


def _task_index_from_args(args: argparse.Namespace) -> TaskIndex:
    suite = _required_str_arg(args, "suite")
    suite_version = cast(str | None, args.suite_version)
    index_id = cast(str | None, args.index_id)
    namespace = cast(str | None, args.selection_namespace)
    if suite == "lfb":
        return lfb_task_index_from_args(
            args,
            suite_version=suite_version,
            index_id=index_id,
            selection_namespace=namespace,
        )
    if suite == "harvey-lab":
        if args.solver_input_root is not None:
            raise ValueError("--solver-input-root is only supported for lfb")
        projected_root = cast(Path | None, getattr(args, "projected_root", None))
        lab_root = cast(Path | None, args.lab_root)
        if projected_root is not None and lab_root is not None:
            raise ValueError("pass either --projected-root or --lab-root, not both")
        if projected_root is not None:
            return HarveyLabProjectionTaskLoader(
                projected_root,
                suite_version=suite_version or DEFAULT_PROJECTED_SUITE_VERSION,
            ).load_task_index(
                index_id=index_id or "harvey-lab",
                selection_namespace=namespace or "harvey_lab",
            )
        if lab_root is None:
            raise ValueError(
                "--projected-root or --lab-root is required for harvey-lab"
            )
        if (lab_root / PROJECTION_MANIFEST_NAME).is_file():
            raise ValueError(
                f"{lab_root} is a projected layout, not a raw Harvey LAB "
                "checkout; pass it as --projected-root"
            )
        return HarveyLabTaskLoader(
            lab_root,
            suite_version=suite_version or DEFAULT_LAB_SUITE_VERSION,
        ).load_task_index(
            index_id=index_id or "harvey-lab",
            selection_namespace=namespace or "harvey_lab",
        )
    raise ValueError(f"unsupported suite: {suite}")


def _selection_manifest(
    *,
    task_index: TaskIndex,
    selection: TaskSelection,
    dry_run: bool,
) -> dict[str, Any]:
    result = selection.select(task_index)
    return {
        "schema_version": _SELECTION_MANIFEST_SCHEMA_VERSION,
        "dry_run": dry_run,
        "task_index": {
            "index_id": task_index.index_id,
            "index_sha256": task_index.index_sha256,
            "selection_namespace": task_index.selection_namespace,
        },
        "selection": selection.normalized().to_record(),
        "selection_result": result.to_record(),
        "tasks": [task.to_record() for task in result.tasks],
        "task_ids": [task.task_id for task in result.tasks],
        "selection_label": result.selection_label,
        "selection_sha256": result.selection_sha256,
    }


def _selection_from_run_args(args: argparse.Namespace) -> TaskSelection:
    selection_path = cast(Path | None, args.selection)
    if selection_path is None:
        return _selection_from_args(args)
    record = _read_json(selection_path, "selection manifest")
    task_ids = _record_str_tuple(record, "task_ids")
    label = record.get("selection_label")
    if label is not None and not isinstance(label, str):
        raise ValueError("selection_label must be a string")
    return TaskSelection(task_ids=task_ids, label=label)


def _selection_from_args(args: argparse.Namespace) -> TaskSelection:
    modules = _str_tuple_arg(args, "module") + _str_tuple_arg(args, "category")
    return TaskSelection(
        families=_str_tuple_arg(args, "family"),
        task_ids=_str_tuple_arg(args, "task_id"),
        case_ids=_str_tuple_arg(args, "case_id"),
        candidate_ids=_str_tuple_arg(args, "candidate_id"),
        ablations=_str_tuple_arg(args, "ablation"),
        modules=modules,
        practice_areas=_str_tuple_arg(args, "practice_area"),
        tags=_str_tuple_arg(args, "tag"),
        limit=cast(int | None, args.limit),
        seed=cast(str | None, args.seed),
        allow_empty=cast(bool, args.allow_empty),
        label=cast(str | None, args.label),
    )


def _apply_folder_selection(
    selection: TaskSelection,
    task_index: TaskIndex,
    folder: Path | None,
) -> TaskSelection:
    if folder is None:
        return selection
    resolved = select_tasks_from_folder(folder, task_index)
    task_ids = resolved.task_ids
    if selection.task_ids:
        allowed = set(selection.task_ids)
        task_ids = tuple(task_id for task_id in task_ids if task_id in allowed)
    if not task_ids:
        raise FolderSelectionError(
            "folder mode matched no tasks after applying --task-id filters"
        )
    return replace(
        selection,
        task_ids=task_ids,
        label=selection.label or "folder",
    )


def _load_adapter(args: argparse.Namespace) -> HarnessAdapter:
    manifest_path = cast(Path | None, args.adapter_manifest)
    if manifest_path is not None:
        return CommandAdapter.from_manifest_file(
            manifest_path,
            timeout_seconds=cast(float, args.timeout_seconds),
        )
    adapter_name = _required_str_arg(args, "adapter")
    return builtin_adapter_registry().get(
        adapter_name,
        lab_command=_str_tuple_arg(args, "lab_command"),
        lab_root=cast(Path | None, args.lab_root),
        timeout_seconds=cast(float, args.timeout_seconds),
    )


def _adapter_source_record(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "adapter": cast(str | None, args.adapter),
        "adapter_manifest": _optional_path_record(
            cast(Path | None, args.adapter_manifest)
        ),
        "lab_command": list(_str_tuple_arg(args, "lab_command")),
        "lab_root": _optional_path_record(cast(Path | None, args.lab_root)),
        "timeout_seconds": cast(float, args.timeout_seconds),
    }


def _run_plan_record(
    *,
    args: argparse.Namespace,
    task_index: TaskIndex,
    selection: TaskSelection,
    manifests: Sequence[AdapterManifest],
    policy_record: Mapping[str, Any],
    solver_inputs: SolverInputStore | None,
) -> dict[str, Any]:
    selected = selection.select(task_index)
    record: dict[str, Any] = {
        "schema_version": _CLI_PLAN_SCHEMA_VERSION,
        "command": "run",
        "dry_run": True,
        "run_id": _required_str_arg(args, "run_id"),
        "task_index": {
            "index_id": task_index.index_id,
            "index_sha256": task_index.index_sha256,
            "selection_namespace": task_index.selection_namespace,
        },
        "selection": selection.normalized().to_record(),
        "selection_result": selected.to_record(),
        "adapter_manifests": [manifest.to_record() for manifest in manifests],
        "model_keys": list(_str_tuple_arg(args, "model_key")),
        "sandbox_policy": dict(policy_record),
        "incomplete_run_policy": _required_str_arg(args, "incomplete_run_policy"),
        "resume": cast(bool, args.resume),
        "adapter_invocation": "skipped",
        "container_invocation": (
            "required" if cast(bool, args.live_tool_container) else "skipped"
        ),
    }
    if solver_inputs is not None:
        record["solver_input_index_sha256"] = solver_inputs.index.index_sha256
    return record


def _sandbox_policy_from_args(args: argparse.Namespace):
    provider_env_vars = _str_tuple_arg(args, "provider_env_var")
    network_policy = (
        PROVIDER_EGRESS_HOST_ONLY
        if cast(bool, args.allow_provider_egress)
        else NETWORK_NONE
    )
    return sandbox_policy(
        policy_id=_required_str_arg(args, "sandbox_policy_id"),
        backend=_required_str_arg(args, "sandbox_backend"),
        image=_required_str_arg(args, "sandbox_image"),
        mounts=(),
        timeout_seconds=cast(int, args.sandbox_timeout_seconds),
        network_policy=network_policy,
        uid_gid="65532:65532" if cast(bool, args.live_tool_container) else None,
        allowed_provider_env_vars=provider_env_vars,
        host_process_containment=_required_str_arg(
            args,
            "host_process_containment",
        ),
    )


def _adapter_manifests_from_paths(paths: Sequence[Path]) -> tuple[AdapterManifest, ...]:
    return tuple(
        AdapterManifest.from_record(_read_json(path, "adapter manifest"))
        for path in paths
    )


def _load_task_index(path: Path) -> TaskIndex:
    return TaskIndex.from_record(_read_json(path, "task index"))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _path_tuple_arg(args: argparse.Namespace, name: str) -> tuple[Path, ...]:
    value = getattr(args, name)
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{name} must be a list of paths")
    paths: list[Path] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Path):
            raise ValueError(f"{name} must contain paths")
        paths.append(item)
    return tuple(paths)


def _cli_note(message: str) -> None:
    """Print a one-line success path so silent commands are not a mystery."""

    print(message, file=sys.stderr)


def _str_tuple_arg(args: argparse.Namespace, name: str) -> tuple[str, ...]:
    value = getattr(args, name)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, bytes):
        raise ValueError(f"{name} must be a list of strings")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name} must contain non-empty strings")
        strings.append(item)
    return tuple(strings)


def _required_str_arg(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_record_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _record_str_tuple(record: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{field_name} must be a list of strings")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        strings.append(item)
    return tuple(strings)


def _optional_path_record(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()


def _counter_record(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))

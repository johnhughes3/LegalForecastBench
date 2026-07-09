"""Argparse command group for the multi-harness benchmark package."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
)
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.community import (
    REQUIRED_ATTESTATIONS,
    CommunityPackageConfig,
    package_community_submission,
    validate_submission_file,
)
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.harvey_lab_adapter import HarveyLabCliAdapter
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.runner import (
    INCOMPLETE_RUN_POLICIES,
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import (
    BACKEND_DOCKER,
    BACKEND_PODMAN,
    NETWORK_NONE,
    PROVIDER_EGRESS_HOST_ONLY,
    sandbox_policy,
)
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import (
    AdapterManifest,
    ContributorCredit,
    TaskIndex,
)
from legalforecast.multiharness.task_loaders import (
    DEFAULT_LAB_SUITE_VERSION,
    DEFAULT_LFB_SUITE_VERSION,
    HarveyLabTaskLoader,
    LfbTaskLoader,
)
from legalforecast.publication.community_aggregate import (
    CommunityAggregateConfig,
    build_community_aggregate,
)

_CLI_PLAN_SCHEMA_VERSION = "legalforecast.multiharness.cli_plan.v1"
_SELECTION_MANIFEST_SCHEMA_VERSION = "legalforecast.multiharness.selection_manifest.v1"
_REPORT_SCHEMA_VERSION = "legalforecast.multiharness.report.v1"


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
    task_index.add_argument(
        "--input",
        type=Path,
        help="LFB packet JSONL input for --suite lfb.",
    )
    task_index.add_argument(
        "--lab-root",
        type=Path,
        help="Harvey LAB checkout/root for --suite harvey-lab.",
    )
    task_index.add_argument("--output", type=Path, required=True)
    task_index.add_argument("--suite-version")
    task_index.add_argument("--index-id")
    task_index.add_argument("--selection-namespace")
    task_index.add_argument("--dry-run", action="store_true")
    task_index.set_defaults(handler=_cmd_tasks_index)

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
    inspect = adapter_commands.add_parser(
        "inspect",
        help="Inspect a built-in or command-manifest adapter.",
    )
    adapter_source = inspect.add_mutually_exclusive_group(required=True)
    adapter_source.add_argument(
        "--adapter",
        choices=("lfb-native", "harvey-lab"),
        help="Built-in adapter to inspect.",
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
        "--provider-env-var",
        action="append",
        default=[],
        help="Provider credential env var name to record for host adapter use.",
    )
    run.add_argument(
        "--allow-provider-egress",
        action="store_true",
        help="Record provider API egress as allowed for host adapter processes.",
    )
    run.add_argument("--resume", action="store_true")
    run.add_argument(
        "--incomplete-run-policy",
        choices=tuple(sorted(INCOMPLETE_RUN_POLICIES)),
        default="record_failure",
    )
    run.add_argument("--timeout-seconds", type=float, default=300.0)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=_cmd_run)

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
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--candidate-id", action="append", default=[])
    parser.add_argument("--ablation", action="append", default=[])
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--practice-area", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
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
                "lab_root": _optional_path_record(cast(Path | None, args.lab_root)),
                "suite_version": cast(str | None, args.suite_version),
                "index_id": cast(str | None, args.index_id),
                "selection_namespace": cast(str | None, args.selection_namespace),
            },
        )
        return 0

    task_index = _task_index_from_args(args)
    write_json_object(output, task_index.to_record())
    return 0


def _cmd_tasks_select(args: argparse.Namespace) -> int:
    task_index = _load_task_index(cast(Path, args.index))
    selection = _selection_from_args(args)
    output = cast(Path, args.output)
    write_json_object(
        output,
        _selection_manifest(
            task_index=task_index,
            selection=selection,
            dry_run=cast(bool, args.dry_run),
        ),
    )
    return 0


def _cmd_adapters_inspect(args: argparse.Namespace) -> int:
    output_dir = cast(Path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if cast(bool, args.dry_run):
        write_json_object(
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
    write_json_object(
        output_dir / "adapter-manifest.json", adapter.manifest.to_record()
    )
    capabilities = adapter.capabilities(output_dir / "capabilities")
    write_json_object(
        output_dir / "adapter-capabilities.json",
        capabilities.to_record(),
    )
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
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    task_index = _load_task_index(cast(Path, args.task_index))
    selection = _selection_from_run_args(args)
    output_dir = cast(Path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = _adapter_manifests_from_paths(_path_tuple_arg(args, "adapter_manifest"))
    policy = _sandbox_policy_from_args(args)
    if cast(bool, args.dry_run):
        write_json_object(
            output_dir / "run-plan.json",
            _run_plan_record(
                args=args,
                task_index=task_index,
                selection=selection,
                manifests=manifests,
                policy_record=policy.to_record(),
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
    run_multi_harness(
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
        )
    )
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
    output_dir.mkdir(parents=True, exist_ok=True)
    if cast(bool, args.dry_run):
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
        input_path = _required_path_arg(args, "input", "--input is required for lfb")
        return LfbTaskLoader(
            suite_version=suite_version or DEFAULT_LFB_SUITE_VERSION,
        ).load_packet_jsonl(
            input_path,
            index_id=index_id or "legalforecast-mtd",
            selection_namespace=namespace or "legalforecast_mtd",
        )
    if suite == "harvey-lab":
        lab_root = _required_path_arg(
            args,
            "lab_root",
            "--lab-root is required for harvey-lab",
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
    return TaskSelection(
        families=_str_tuple_arg(args, "family"),
        task_ids=_str_tuple_arg(args, "task_id"),
        case_ids=_str_tuple_arg(args, "case_id"),
        candidate_ids=_str_tuple_arg(args, "candidate_id"),
        ablations=_str_tuple_arg(args, "ablation"),
        modules=_str_tuple_arg(args, "module"),
        practice_areas=_str_tuple_arg(args, "practice_area"),
        tags=_str_tuple_arg(args, "tag"),
        limit=cast(int | None, args.limit),
        seed=cast(str | None, args.seed),
        allow_empty=cast(bool, args.allow_empty),
        label=cast(str | None, args.label),
    )


def _load_adapter(args: argparse.Namespace) -> HarnessAdapter:
    manifest_path = cast(Path | None, args.adapter_manifest)
    if manifest_path is not None:
        return CommandAdapter.from_manifest_file(
            manifest_path,
            timeout_seconds=cast(float, args.timeout_seconds),
        )
    adapter_name = _required_str_arg(args, "adapter")
    if adapter_name == "lfb-native":
        return LfbNativeAdapter()
    if adapter_name == "harvey-lab":
        lab_command = _str_tuple_arg(args, "lab_command")
        if not lab_command:
            raise ValueError("--lab-command is required for --adapter harvey-lab")
        return HarveyLabCliAdapter(
            lab_command=lab_command,
            lab_root=cast(Path | None, args.lab_root),
            timeout_seconds=cast(float, args.timeout_seconds),
        )
    raise ValueError(f"unsupported adapter: {adapter_name}")


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
) -> dict[str, Any]:
    selected = selection.select(task_index)
    return {
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
        "container_invocation": "skipped",
    }


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
        allowed_provider_env_vars=provider_env_vars,
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


def _required_path_arg(args: argparse.Namespace, name: str, message: str) -> Path:
    value = cast(Path | None, getattr(args, name))
    if value is None:
        raise ValueError(message)
    return value


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

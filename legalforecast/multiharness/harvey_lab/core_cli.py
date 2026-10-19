"""Public CLI for the pinned native lab-core bridge."""

from __future__ import annotations

import argparse
import json
from importlib import import_module
from pathlib import Path

from legalforecast.multiharness.harvey_lab.core_bridge import (
    LabCoreRequest,
    run_lab_core,
)
from legalforecast.multiharness.harvey_lab.core_runtime import LabCoreRuntime
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    ROOT_MANIFEST_NAME,
    harvey_lab_v1_1_pin,
    project_harvey_lab_suite,
    remove_projected_tree,
)

_PROTECTED_OPERATOR_MODULE = ".".join(
    ("legalforecast", "multiharness", "harvey_lab_protected_operator")
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register credential-free probing and explicit contributor-funded runs."""
    group = subparsers.add_parser(
        "harvey-lab", help="Use the pinned lab-core 1.1.0 native CLI bridge."
    )
    commands = group.add_subparsers(dest="lab_command")
    prepare = commands.add_parser(
        "prepare-clean-native",
        help="Produce the pinned task split for the Claude Code clean-native baseline.",
    )
    prepare.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Clean harveyai/harvey-labs checkout at the v1.1.0 commit.",
    )
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--evaluator-private-dir", type=Path, required=True)
    prepare.set_defaults(handler=_prepare_clean_native)
    protected = commands.add_parser(
        "run-clean-native",
        help=(
            "Run the prepared Claude Code LAB arm with the protected solver "
            "gateway and a separately metered production judge."
        ),
    )
    protected.add_argument("--source-root", type=Path, required=True)
    protected.add_argument("--projection-dir", type=Path, required=True)
    protected.add_argument("--evaluator-private-dir", type=Path, required=True)
    protected.add_argument("--run-dir", type=Path, required=True)
    protected.add_argument("--evaluator-bin-dir", type=Path, required=True)
    protected.add_argument("--paid-config", type=Path, required=True)
    protected.add_argument("--model-registry", type=Path, required=True)
    protected.add_argument("--solver-image", required=True)
    protected.add_argument("--gateway-image", required=True)
    protected.add_argument("--model-key", required=True)
    protected.add_argument("--timeout-seconds", type=int, default=900)
    protected.set_defaults(handler=_run_clean_native)
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


def _prepare_clean_native(args: argparse.Namespace) -> int:
    """Produce the exact solver/private split consumed by the baseline join."""

    for label, path in (
        ("--output-dir", args.output_dir),
        ("--evaluator-private-dir", args.evaluator_private_dir),
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(f"{label} must name a fresh, absent path: {path}")
    try:
        result = project_harvey_lab_suite(
            source_root=args.source_root,
            solver_root=args.output_dir,
            evaluator_private_root=args.evaluator_private_dir,
            pin=harvey_lab_v1_1_pin(),
            lab_task_ids=(ISSUE_196_LAB_TASK_ID,),
        )
    except BaseException:
        remove_projected_tree(args.output_dir)
        remove_projected_tree(args.evaluator_private_dir)
        raise
    print(
        json.dumps(
            {
                "projection_manifest": str(result.solver_root / ROOT_MANIFEST_NAME),
                "provider_requests": 0,
                "task_id": ISSUE_196_LAB_TASK_ID,
            },
            sort_keys=True,
        )
    )
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


def _run_clean_native(args: argparse.Namespace) -> int:
    # The provider adapter is an optional paid-runtime dependency. Load it only
    # when this protected command is selected, after CLI registration completes.
    operator = import_module(_PROTECTED_OPERATOR_MODULE)
    request_type = operator.ProtectedHarveyLabOperatorRequest
    run_operator = operator.run_protected_harvey_lab_operator
    result = run_operator(
        request_type(
            source_root=args.source_root,
            projection_root=args.projection_dir,
            evaluator_private_root=args.evaluator_private_dir,
            run_root=args.run_dir,
            evaluator_bin_dir=args.evaluator_bin_dir,
            paid_config_path=args.paid_config,
            model_registry_path=args.model_registry,
            solver_image_digest=args.solver_image,
            gateway_image_digest=args.gateway_image,
            model_key=args.model_key,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(
        json.dumps(
            {
                "execution_mode": result.execution_mode,
                "n_criteria": result.score.n_criteria,
                "n_passed": result.score.n_passed,
                "score": result.baseline_score_value,
                "task_id": result.task.lab_task_id,
            },
            sort_keys=True,
        )
    )
    return 0

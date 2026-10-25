"""Native Codex invocation policy and solver prompt for Harvey LAB."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapterError,
    CodexCliInvocationPlan,
)
from legalforecast.multiharness.contributor_boundary import (
    LINUX_LANDLOCK_FS_SCOPE,
    preflight_contributor_boundary,
)
from legalforecast.multiharness.harvey_lab_projection import HarveyLabProjectedTask
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService


def externally_contained_plan(
    plan: CodexCliInvocationPlan, service: LocalCliExecutionService
) -> CodexCliInvocationPlan:
    """Use native external containment only behind the subscription boundary.

    Nested bubblewrap cannot create user namespaces on some contributor hosts.
    Landlock still restricts the entire Codex process and every descendant.
    The execution service establishes it before exec and fails closed on error.
    """

    if (
        plan.auth_profile != CONTRIBUTOR_SUBSCRIPTION
        or service.auth_profile != CONTRIBUTOR_SUBSCRIPTION
        or service.filesystem_scope != LINUX_LANDLOCK_FS_SCOPE
    ):
        raise CodexCliAdapterError(
            "external Codex containment requires subscription execution with Landlock"
        )
    preflight_contributor_boundary()
    argv = list(plan.argv)
    argv[argv.index("--sandbox") + 1] = "danger-full-access"
    return replace(plan, argv=tuple(argv))


def lab_solver_prompt(
    *,
    instructions: Path,
    task: HarveyLabProjectedTask,
    externally_contained: bool = False,
) -> str:
    """Describe the task and the actual containment mode to the native solver."""

    if not instructions.is_file():
        raise CodexCliAdapterError(
            "projected Harvey LAB task is missing instructions.txt"
        )
    body = instructions.read_text(encoding="utf-8").strip()
    if not body:
        raise CodexCliAdapterError(
            "projected Harvey LAB instructions must be non-empty"
        )
    declaration = (
        "Write the expected deliverables " + ", ".join(task.expected_deliverables)
        if task.expected_deliverables
        else "Write every deliverable requested by the task"
    )
    containment = (
        "The entire process and native tools are restricted by the external Landlock "
        "filesystem boundary; use native tools in this working directory. "
        if externally_contained
        else "Use only the native Codex workspace-write sandbox. "
    )
    return (
        f"{body}\n\n"
        "Read solver-visible materials under task/ in the working directory. "
        f"{declaration} into the output directory under the "
        f"working directory. {containment}"
        "Do not use MCP tools."
    )

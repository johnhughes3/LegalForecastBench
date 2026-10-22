"""Pre-transport production and completion guards for the Claude LAB join."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType

from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapterError,
    classify_claude_completion_execution,
)
from legalforecast.multiharness.harvey_lab.evaluation_contract import (
    HarveyLabEvaluationError,
    directory_snapshot,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EvaluatorProvenanceProvider,
    EvaluatorRunner,
    HarveyLabEvaluatorProvenance,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    project_harvey_lab_suite,
    remove_projected_tree,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
    is_local_cli_sandbox_denial,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

_LAB_FAILURE_MESSAGES: Mapping[LocalCliFailureClass, str] = MappingProxyType(
    {
        LocalCliFailureClass.TIMEOUT: (
            "clean-native Claude Code Harvey LAB run timed out"
        ),
        LocalCliFailureClass.CANCELLED: (
            "clean-native Claude Code Harvey LAB run was cancelled"
        ),
        LocalCliFailureClass.SANDBOX_DENIAL: (
            "clean-native Claude Code Harvey LAB run hit a sandbox denial"
        ),
        LocalCliFailureClass.IDENTITY_DRIFT: (
            "clean-native Claude Code Harvey LAB run was served a different model"
        ),
    }
)


def require_complete_production_evaluator(
    *,
    solver_service: LocalCliExecutionService,
    evaluator_execution_service: LocalCliExecutionService | None,
    judge_request_boundary: HarveyLabJudgeRequestBoundary | None,
    evaluator_runner: EvaluatorRunner | None,
    evaluator_provenance: HarveyLabEvaluatorProvenance | None,
    evaluator_provenance_provider: EvaluatorProvenanceProvider | None,
    require_production_provenance: bool,
) -> None:
    """Refuse an incomplete production path before any solver transport."""

    if not require_production_provenance:
        return
    if evaluator_execution_service is None:
        raise ClaudeCodeCliAdapterError(
            "production LAB requires an explicit evaluator execution service"
        )
    if evaluator_execution_service is solver_service:
        raise ClaudeCodeCliAdapterError(
            "production LAB requires distinct solver and evaluator services"
        )
    if judge_request_boundary is None or evaluator_runner is None:
        raise ClaudeCodeCliAdapterError(
            "production LAB requires a per-criterion judge runner and spend boundary"
        )
    if (evaluator_provenance is None) == (evaluator_provenance_provider is None):
        raise ClaudeCodeCliAdapterError(
            "production LAB requires exactly one evaluator provenance source"
        )


def require_authentic_prepared_private_material(
    *,
    source_root: Path,
    evaluator_private_root: Path,
    pin: HarveyLabPin,
    lab_task_id: str,
) -> None:
    """Bind prepared evaluator-private bytes to a fresh pinned projection."""

    with TemporaryDirectory(prefix="lfb-lab-private-compare-") as temporary:
        comparison_root = Path(temporary)
        expected_solver = comparison_root / "solver"
        expected_private = comparison_root / "private"
        try:
            expected = project_harvey_lab_suite(
                source_root=source_root,
                solver_root=expected_solver,
                evaluator_private_root=expected_private,
                pin=pin,
                lab_task_ids=(lab_task_id,),
            )
            try:
                _, expected_files = directory_snapshot(
                    expected.evaluator_private_root,
                    "authenticated evaluator-private material",
                )
                _, prepared_files = directory_snapshot(
                    evaluator_private_root,
                    "prepared evaluator-private material",
                )
            except HarveyLabEvaluationError as exc:
                raise ClaudeCodeCliAdapterError(str(exc)) from exc
            expected_paths = set(expected_files)
            prepared_paths = set(prepared_files)
            if expected_paths != prepared_paths:
                missing = ", ".join(sorted(expected_paths - prepared_paths)) or "none"
                extra = ", ".join(sorted(prepared_paths - expected_paths)) or "none"
                raise ClaudeCodeCliAdapterError(
                    "prepared Harvey LAB evaluator-private file census does not "
                    "match the authenticated checkout "
                    f"(missing: {missing}; extra: {extra})"
                )
            for relative in sorted(expected_paths):
                if prepared_files[relative] != expected_files[relative]:
                    raise ClaudeCodeCliAdapterError(
                        "prepared Harvey LAB evaluator-private bytes do not match "
                        f"the authenticated checkout: {relative}"
                    )
        finally:
            remove_projected_tree(expected_solver)
            remove_projected_tree(expected_private)


def require_solver_success(
    spec: RunSpec,
    execution: ExecutionReceipt,
    *,
    requested_model: str,
    allow_model_alias: bool = False,
) -> None:
    """Require a clean completion served by the selected Claude model."""

    if execution.spec_sha256 != spec.spec_sha256:
        raise ClaudeCodeCliAdapterError("execution receipt does not bind the RunSpec")
    failure_class = classify_claude_completion_execution(
        execution,
        requested_model=requested_model,
        allow_model_alias=allow_model_alias,
    )
    if failure_class is None and is_local_cli_sandbox_denial(
        "\n".join((execution.stdout, execution.stderr))
    ):
        failure_class = LocalCliFailureClass.SANDBOX_DENIAL
    if failure_class is None:
        if execution.status != "succeeded" or execution.returncode not in {0, None}:
            detail = execution.stderr.strip() or execution.stdout.strip() or "crash"
            raise ClaudeCodeCliAdapterError(
                f"clean-native Claude Code Harvey LAB run failed: {detail}",
                failure_class=LocalCliFailureClass.CRASH,
            )
        return
    named = _LAB_FAILURE_MESSAGES.get(failure_class)
    if named is not None:
        raise ClaudeCodeCliAdapterError(named, failure_class=failure_class)
    detail = execution.stderr.strip() or execution.stdout.strip() or "crash"
    raise ClaudeCodeCliAdapterError(
        f"clean-native Claude Code Harvey LAB run failed: {detail}",
        failure_class=failure_class,
    )


__all__ = [
    "require_authentic_prepared_private_material",
    "require_complete_production_evaluator",
    "require_solver_success",
]

"""Clean-native Codex CLI → Harvey LAB composition.
Wires landed modules: projection → contained ``codex exec`` with native
sandbox → sandbox output discovery → isolated evaluator → authorized
scoring. Does not invent a second RunSpec, ExecutionReceipt, or
failure-class family.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast.multiharness import community_subscription_sandbox as _native
from legalforecast.multiharness.auth_binding import (
    bind_adapter_auth_profile,
    require_execution_service_profile,
)
from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.claude_code_harvey_lab_guards import (
    require_authentic_prepared_private_material,
    require_complete_production_evaluator,
)
from legalforecast.multiharness.codex_cli import (
    CODEX_CLI_EXECUTABLE,
    CODEX_DEFAULT_REASONING_EFFORT,
    CodexCliAdapter,
    CodexCliAdapterError,
    classify_codex_execution,
    plan_contained_codex_exec,
)
from legalforecast.multiharness.codex_cli_harvey_lab_guards import (
    require_solver_success,
)
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    harvey_lab_issuer_policy_sha256,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATOR_COMMAND_NAME,
    EvaluatorProvenanceProvider,
    EvaluatorRunner,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabEvaluatorExecution,
    HarveyLabEvaluatorProvenance,
    HarveyLabIsolatedEvaluation,
    HarveyLabJudgeRequestBoundary,
    execute_isolated_harvey_lab_evaluator,
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_observed_score import (
    HarveyLabObservedScore,
    observed_harvey_lab_score,
)
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryResult,
    discover_harvey_lab_outputs,
    require_harvey_lab_sandbox_hosts,
)
from legalforecast.multiharness.harvey_lab_projection import (
    INSTRUCTIONS_NAME,
    ISSUE_196_LAB_TASK_ID,
    HarveyLabPin,
    HarveyLabProjectedTask,
    HarveyLabProjectionResult,
    harvey_lab_v1_1_pin,
    project_harvey_lab_suite,
    verify_harvey_lab_projection,
    verify_harvey_lab_source_pin,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    sha256_file,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import (
    ScoreArtifact,
    build_harvey_lab_metric_definition,
)

CODEX_LAB_DEFAULT_MODEL = "gpt-5.1"


@dataclass(frozen=True, slots=True)
class CodexCliHarveyLabPipelineResult:
    """Receipts chain for one clean-native Codex CLI Harvey LAB run."""

    projection: HarveyLabProjectionResult
    task: HarveyLabProjectedTask
    solver_spec: RunSpec
    solver_execution: ExecutionReceipt
    discovery: HarveyLabOutputDiscoveryResult
    evaluation: HarveyLabIsolatedEvaluation
    score: ScoreArtifact


@dataclass(frozen=True, slots=True)
class CodexCliHarveyLabMeasurementResult:
    """Observed standalone Codex result without issuer/signing requirements."""

    projection: HarveyLabProjectionResult
    task: HarveyLabProjectedTask
    solver_spec: RunSpec
    solver_execution: ExecutionReceipt
    discovery: HarveyLabOutputDiscoveryResult
    evaluation: HarveyLabEvaluatorExecution
    score: HarveyLabObservedScore
    execution_mode: Literal["fixture", "production"]
    baseline_score_value: int | None


def run_codex_cli_clean_native_harvey_lab(
    *,
    adapter: CodexCliAdapter,
    source_root: Path,
    solver_root: Path,
    evaluator_private_root: Path,
    sandbox_root: Path,
    sealed_root: Path,
    quarantine_root: Path,
    overlay_root: Path,
    evaluator_working_directory: Path,
    signer: Callable[[bytes], bytes] | None = None,
    issuer_public_key: Ed25519PublicKey | None = None,
    lab_task_id: str = ISSUE_196_LAB_TASK_ID,
    pin: HarveyLabPin | None = None,
    model: str = CODEX_LAB_DEFAULT_MODEL,
    timeout_seconds: float | None = None,
    output_root: Path | None = None,
    escape_watch_roots: Sequence[Path] = (),
    evaluator_command: str = EVALUATOR_COMMAND_NAME,
    measurement_id: str | None = None,
    evaluation_attempt_id: str | None = None,
    attempt_nonce: str | None = None,
    reasoning_effort: str = CODEX_DEFAULT_REASONING_EFFORT,
    solver_executable_pin: ExecutableIdentityPin | None = None,
    before_solver: Callable[[RunSpec], None] | None = None,
    after_solver: Callable[[RunSpec, ExecutionReceipt], ExecutionReceipt] | None = None,
    judge_request_boundary: HarveyLabJudgeRequestBoundary | None = None,
    evaluator_runner: EvaluatorRunner | None = None,
    evaluator_provenance: HarveyLabEvaluatorProvenance | None = None,
    evaluator_provenance_provider: EvaluatorProvenanceProvider | None = None,
    evaluator_execution_service: LocalCliExecutionService | None = None,
    require_production_provenance: bool = False,
    use_prepared_projection: bool = False,
    community_subscription_auth_root: Path | None = None,
) -> CodexCliHarveyLabPipelineResult | CodexCliHarveyLabMeasurementResult:
    """Project a LAB task, run contained Codex CLI, discover, and score."""

    service = adapter.execution_service
    if not isinstance(service, LocalCliExecutionService):
        raise CodexCliAdapterError(
            "clean-native Harvey LAB runs require the contained execution service"
        )
    try:
        bound = bind_adapter_auth_profile(
            adapter.local_cli_manifest, adapter.auth_profile
        )
        require_execution_service_profile(
            service,
            bound.profile_id,
            projected_env_vars=bound.profile.projected_env_vars,
        )
    except AuthProfileError as exc:
        raise CodexCliAdapterError(str(exc)) from exc
    require_complete_production_evaluator(
        solver_service=service,
        evaluator_execution_service=evaluator_execution_service,
        judge_request_boundary=judge_request_boundary,
        evaluator_runner=evaluator_runner,
        evaluator_provenance=evaluator_provenance,
        evaluator_provenance_provider=evaluator_provenance_provider,
        require_production_provenance=require_production_provenance,
    )
    if (signer is None) != (issuer_public_key is None):
        raise CodexCliAdapterError(
            "signer and issuer_public_key must be supplied together"
        )
    applied_pin = pin or harvey_lab_v1_1_pin()
    if use_prepared_projection:
        verify_harvey_lab_source_pin(source_root, applied_pin)
        manifest = verify_harvey_lab_projection(solver_root)
        if manifest.pin != applied_pin:
            raise CodexCliAdapterError(
                "prepared Harvey LAB projection does not match the selected pin"
            )
        require_authentic_prepared_private_material(
            source_root=source_root,
            evaluator_private_root=evaluator_private_root,
            pin=applied_pin,
            lab_task_id=lab_task_id,
        )
        projection = HarveyLabProjectionResult(
            solver_root=solver_root.resolve(),
            evaluator_private_root=evaluator_private_root.resolve(),
            manifest=manifest,
            tasks=(),
        )
    else:
        projection = project_harvey_lab_suite(
            source_root=source_root,
            solver_root=solver_root,
            evaluator_private_root=evaluator_private_root,
            pin=applied_pin,
            lab_task_ids=(lab_task_id,),
        )
    if (
        len(projection.manifest.tasks) != 1
        or projection.manifest.tasks[0].lab_task_id != lab_task_id
    ):
        raise CodexCliAdapterError(
            "Harvey LAB projection did not produce exactly the selected task"
        )
    task = projection.manifest.tasks[0]
    task_dir = projection.solver_root / task.relative_path
    prompt = _lab_solver_prompt(instructions=task_dir / INSTRUCTIONS_NAME, task=task)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    _stage_solver_visible_task(task_dir, sandbox_root)
    resolved_output = require_harvey_lab_sandbox_hosts(
        sandbox_root=sandbox_root,
        output_root=output_root or (sandbox_root / "output"),
    )
    local_cli_manifest = adapter.local_cli_manifest
    declared_timeout = float(local_cli_manifest.timeout_retry.timeout_seconds)
    applied_timeout = (
        declared_timeout
        if timeout_seconds is None
        else min(float(timeout_seconds), declared_timeout)
    )
    plan = plan_contained_codex_exec(
        prompt=prompt,
        model=model,
        workspace=sandbox_root,
        timeout_seconds=applied_timeout,
        reasoning_effort=reasoning_effort,
        local_cli_manifest=local_cli_manifest,
        auth_profile=adapter.auth_profile,
    )
    if community_subscription_auth_root is not None:
        plan = _native.codex_service_plan(
            plan, community_subscription_auth_root, service, solver_executable_pin
        )
    if "--approve-for-me" in plan.argv or "--ask-for-approval" in plan.argv:
        raise CodexCliAdapterError(
            "clean-native Codex Harvey LAB invocation must stay non-interactive"
        )
    _require_on_path(
        CODEX_CLI_EXECUTABLE,
        service.parent_env,
        label="clean-native Codex CLI executable",
        missing="local CLI executable could not be launched",
    )
    spec = RunSpec(
        spec_id=task.task_id,
        argv=plan.argv,
        working_directory=sandbox_root,
        environment={},
        timeout_seconds=applied_timeout,
        output_format="json",
        stdin_bytes=plan.stdin.encode("utf-8"),
    )
    if before_solver is not None:
        before_solver(spec)
    # Pin only the solver launch; the evaluator has its own executable identity.
    solver_service = (
        service
        if solver_executable_pin is None
        else replace(service, executable_pin=solver_executable_pin)
    )
    execution = solver_service.execute(spec)
    if after_solver is not None:
        execution = after_solver(spec, execution)
    require_solver_success(
        spec,
        execution,
        requested_model=plan.requested_model,
    )
    execution = replace(
        execution,
        served_model=classify_codex_execution(
            execution, requested_model_name=model
        ).served_model,
    )
    task_digest = _prefixed_digest_text(task.task_sha256)
    run_digest = spec.spec_sha256
    config_digest = spec.spec_sha256
    discovery = discover_harvey_lab_outputs(
        sandbox_root=sandbox_root,
        output_root=resolved_output,
        quarantine_root=quarantine_root,
        sealed_root=sealed_root,
        task=task,
        task_sha256=task_digest,
        run_sha256=run_digest,
        config_sha256=config_digest,
        layout="native",
        escape_watch_roots=escape_watch_roots,
        evaluator_private_root=evaluator_private_root,
        projection_root=projection.solver_root,
    )
    if discovery.quarantined:
        raise CodexCliAdapterError("quarantined extras must not be scored")
    evaluator_service = evaluator_execution_service or service
    wrapper_sha256 = "sha256:" + sha256_file(
        Path(
            _require_on_path(
                evaluator_command,
                evaluator_service.parent_env,
                label="evaluator wrapper",
            )
        )
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=evaluator_private_root,
        overlay_root=overlay_root,
        working_directory=evaluator_working_directory,
        solver_projection_root=projection.solver_root,
        evaluator_source_root=source_root,
    )
    identity = HarveyLabEvaluationIdentity(
        lab_task_id=task.lab_task_id,
        task_sha256=task_digest,
        expected_deliverable_basenames=task.expected_deliverables,
        projection_manifest_sha256=projection.manifest.manifest_sha256,
        wrapper_sha256=wrapper_sha256,
        run_sha256=run_digest,
        config_sha256=config_digest,
        pin=projection.manifest.pin,
    )
    if signer is None:
        evaluation = execute_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=discovery.sealed,
            identity=identity,
            execution_service=evaluator_service,
            evaluator_command=evaluator_command,
            timeout_seconds=applied_timeout,
            judge_request_boundary=judge_request_boundary,
            evaluator_runner=evaluator_runner,
            evaluator_provenance=evaluator_provenance,
            evaluator_provenance_provider=evaluator_provenance_provider,
            require_production_provenance=require_production_provenance,
        )
    else:
        assert issuer_public_key is not None
        evaluation = invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=discovery.sealed,
            identity=identity,
            execution_service=evaluator_service,
            signer=signer,
            issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
            issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
            evaluator_command=evaluator_command,
            timeout_seconds=applied_timeout,
            measurement_id=measurement_id,
            evaluation_attempt_id=evaluation_attempt_id,
            attempt_nonce=attempt_nonce,
            judge_request_boundary=judge_request_boundary,
            evaluator_runner=evaluator_runner,
            evaluator_provenance=evaluator_provenance,
            evaluator_provenance_provider=evaluator_provenance_provider,
            require_production_provenance=require_production_provenance,
        )
    if isinstance(evaluation, HarveyLabIsolatedEvaluation):
        metric = build_harvey_lab_metric_definition(
            rubric_sha256=evaluation.spec.rubric_sha256,
            criteria_sha256=evaluation.spec.criteria_sha256,
            aggregation_sha256=evaluation.spec.aggregation_sha256,
            output_schema_sha256=evaluation.spec.judge_output_schema_sha256,
            criterion_count=evaluation.criterion_count,
        )
        assert issuer_public_key is not None
        score: ScoreArtifact | HarveyLabObservedScore = (
            verify_authorized_harvey_lab_receipt(
                evaluation.receipt.to_record(),
                raw_result=evaluation.raw_result,
                spec=evaluation.spec,
                metric=metric,
                issuer_public_key=issuer_public_key,
                expected_measurement_id=evaluation.receipt.measurement_id,
                expected_evaluation_attempt_id=(
                    evaluation.receipt.evaluation_attempt_id
                ),
                expected_attempt_nonce=evaluation.receipt.attempt_nonce,
                expected_repeat_index=evaluation.receipt.repeat_index,
                expected_deliverable_manifest_sha256=(discovery.sealed.manifest_sha256),
                expected_runtime_policy_sha256=evaluation.spec.runtime_policy_sha256,
            )
        )
    else:
        score = observed_harvey_lab_score(evaluation)
    if isinstance(evaluation, HarveyLabIsolatedEvaluation):
        assert isinstance(score, ScoreArtifact)
        return CodexCliHarveyLabPipelineResult(
            projection=projection,
            task=task,
            solver_spec=spec,
            solver_execution=execution,
            discovery=discovery,
            evaluation=evaluation,
            score=score,
        )
    assert isinstance(score, HarveyLabObservedScore)
    return CodexCliHarveyLabMeasurementResult(
        projection=projection,
        task=task,
        solver_spec=spec,
        solver_execution=execution,
        discovery=discovery,
        evaluation=evaluation,
        score=score,
        execution_mode=("production" if require_production_provenance else "fixture"),
        baseline_score_value=(
            score.score_value if require_production_provenance else None
        ),
    )


def _lab_solver_prompt(*, instructions: Path, task: HarveyLabProjectedTask) -> str:
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
    return (
        f"{body}\n\n"
        "Read solver-visible materials under task/ in the working directory. "
        f"{declaration} into the output directory under the "
        "working directory. Use only the native Codex workspace-write sandbox. "
        "Do not use MCP tools."
    )


def _stage_solver_visible_task(task_dir: Path, sandbox_root: Path) -> Path:
    """Copy projected solver-visible files into the sandbox.
    Codex exec forbids ``--add-dir``. The copy keeps the projection root
    disjoint from the sandbox while still giving native tools a local tree.
    """

    if not task_dir.is_dir() or task_dir.is_symlink():
        raise CodexCliAdapterError("projected Harvey LAB task must be a real directory")
    destination = sandbox_root / "task"
    if destination.exists() or destination.is_symlink():
        raise CodexCliAdapterError("sandbox task staging path already exists")
    destination.mkdir(parents=True)
    for source in task_dir.rglob("*"):
        relative = source.relative_to(task_dir)
        target = destination / relative
        if source.is_symlink():
            raise CodexCliAdapterError("projected LAB task must not contain symlinks")
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not source.is_file():
            raise CodexCliAdapterError("projected LAB task contains a non-regular file")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=False)
    return destination


def _require_on_path(
    command: str,
    parent_env: Mapping[str, str] | None,
    *,
    label: str,
    missing: str | None = None,
) -> str:
    if "/" in command or "\\" in command or command in {".", ".."}:
        raise CodexCliAdapterError(f"{label} must be a basename on PATH")
    search_path = parent_env.get("PATH", "/usr/bin") if parent_env else "/usr/bin"
    located = shutil.which(command, path=search_path)
    if located is None:
        raise CodexCliAdapterError(missing or f"{label} is not on PATH")
    return located


def _prefixed_digest_text(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"

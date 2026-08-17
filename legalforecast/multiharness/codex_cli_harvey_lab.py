"""Clean-native Codex CLI → Harvey LAB composition.

Wires landed modules: projection → contained ``codex exec`` with native
sandbox → sandbox output discovery → isolated evaluator → authorized
scoring. Does not invent a second RunSpec, ExecutionReceipt, or
failure-class family.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast.multiharness.codex_cli import (
    CODEX_CLI_EXECUTABLE,
    CODEX_DEFAULT_REASONING_EFFORT,
    CodexCliAdapter,
    CodexCliAdapterError,
    classify_codex_execution,
    plan_contained_codex_exec,
)
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    harvey_lab_issuer_policy_sha256,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATOR_COMMAND_NAME,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabIsolatedEvaluation,
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryResult,
    discover_harvey_lab_outputs,
)
from legalforecast.multiharness.harvey_lab_projection import (
    INSTRUCTIONS_NAME,
    ISSUE_196_LAB_TASK_ID,
    HarveyLabPin,
    HarveyLabProjectedTask,
    HarveyLabProjectionResult,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
    coerce_local_cli_failure_class,
    is_local_cli_sandbox_denial,
)
from legalforecast.multiharness.local_cli_identity import sha256_file
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
    signer: Callable[[bytes], bytes],
    issuer_public_key: Ed25519PublicKey,
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
) -> CodexCliHarveyLabPipelineResult:
    """Project a LAB task, run contained Codex CLI, discover, and score."""

    service = adapter.execution_service
    if not isinstance(service, LocalCliExecutionService):
        raise CodexCliAdapterError(
            "clean-native Harvey LAB runs require the contained execution service"
        )
    projection = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=solver_root,
        evaluator_private_root=evaluator_private_root,
        pin=pin,
        lab_task_ids=(ISSUE_196_LAB_TASK_ID,),
    )
    if (
        len(projection.manifest.tasks) != 1
        or projection.manifest.tasks[0].lab_task_id != ISSUE_196_LAB_TASK_ID
    ):
        raise CodexCliAdapterError(
            "Harvey LAB projection did not produce exactly the frozen issue-196 task"
        )
    task = projection.manifest.tasks[0]
    task_dir = projection.solver_root / task.relative_path
    prompt = _lab_solver_prompt(instructions=task_dir / INSTRUCTIONS_NAME, task=task)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    _stage_solver_visible_task(task_dir, sandbox_root)
    resolved_output = output_root or (sandbox_root / "output")
    resolved_output.mkdir(parents=True, exist_ok=True)
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
    execution = service.execute(spec)
    _require_solver_success(
        spec,
        execution,
        requested_model=plan.requested_model,
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
    wrapper_sha256 = "sha256:" + sha256_file(
        Path(
            _require_on_path(
                evaluator_command,
                service.parent_env,
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
    )
    identity = HarveyLabEvaluationIdentity(
        lab_task_id=task.lab_task_id,
        task_sha256=task_digest,
        expected_deliverable_basename=task.expected_deliverable,
        projection_manifest_sha256=projection.manifest.manifest_sha256,
        wrapper_sha256=wrapper_sha256,
        run_sha256=run_digest,
        config_sha256=config_digest,
        pin=projection.manifest.pin,
    )
    evaluation = invoke_isolated_harvey_lab_evaluator(
        hosts=hosts,
        sealed_manifest=discovery.sealed,
        identity=identity,
        execution_service=service,
        signer=signer,
        issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        evaluator_command=evaluator_command,
        timeout_seconds=applied_timeout,
        measurement_id=measurement_id,
        evaluation_attempt_id=evaluation_attempt_id,
        attempt_nonce=attempt_nonce,
    )
    metric = build_harvey_lab_metric_definition(
        rubric_sha256=evaluation.spec.rubric_sha256,
        criteria_sha256=evaluation.spec.criteria_sha256,
        aggregation_sha256=evaluation.spec.aggregation_sha256,
        output_schema_sha256=evaluation.spec.judge_output_schema_sha256,
    )
    score = verify_authorized_harvey_lab_receipt(
        evaluation.receipt.to_record(),
        raw_result=evaluation.raw_result,
        spec=evaluation.spec,
        metric=metric,
        issuer_public_key=issuer_public_key,
        expected_measurement_id=evaluation.receipt.measurement_id,
        expected_evaluation_attempt_id=evaluation.receipt.evaluation_attempt_id,
        expected_attempt_nonce=evaluation.receipt.attempt_nonce,
        expected_repeat_index=evaluation.receipt.repeat_index,
        expected_deliverable_manifest_sha256=discovery.sealed.manifest_sha256,
        expected_runtime_policy_sha256=evaluation.spec.runtime_policy_sha256,
    )
    return CodexCliHarveyLabPipelineResult(
        projection=projection,
        task=task,
        solver_spec=spec,
        solver_execution=execution,
        discovery=discovery,
        evaluation=evaluation,
        score=score,
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
    return (
        f"{body}\n\n"
        "Read solver-visible materials under task/ in the working directory. "
        "Write the expected deliverable "
        f"{task.expected_deliverable} into the output directory under the "
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


def _require_solver_success(
    spec: RunSpec,
    execution: ExecutionReceipt,
    *,
    requested_model: str,
) -> None:
    if execution.spec_sha256 != spec.spec_sha256:
        raise CodexCliAdapterError("execution receipt does not bind the RunSpec")
    envelope = classify_codex_execution(
        execution,
        requested_model_name=requested_model,
    )
    failure_text = "\n".join((execution.stdout, execution.stderr))
    if execution.status == "timeout" or envelope.failure_class == (
        LocalCliFailureClass.TIMEOUT.value
    ):
        raise CodexCliAdapterError(
            "clean-native Codex CLI Harvey LAB run timed out",
            failure_class=LocalCliFailureClass.TIMEOUT,
        )
    if envelope.failure_class == LocalCliFailureClass.SANDBOX_DENIAL.value or (
        is_local_cli_sandbox_denial(failure_text)
    ):
        raise CodexCliAdapterError(
            "clean-native Codex CLI Harvey LAB run hit a sandbox denial",
            failure_class=LocalCliFailureClass.SANDBOX_DENIAL,
        )
    if envelope.failure_class is not None:
        detail = (
            execution.stderr.strip()
            or execution.stdout.strip()
            or envelope.failure_class
        )
        raise CodexCliAdapterError(
            f"clean-native Codex CLI Harvey LAB run failed: {detail}",
            failure_class=coerce_local_cli_failure_class(envelope.failure_class),
        )
    if execution.status != "succeeded" or execution.returncode not in {0, None}:
        detail = execution.stderr.strip() or execution.stdout.strip() or "crash"
        raise CodexCliAdapterError(
            f"clean-native Codex CLI Harvey LAB run failed: {detail}",
            failure_class=LocalCliFailureClass.CRASH,
        )


def _require_on_path(
    command: str,
    parent_env: Mapping[str, str] | None,
    *,
    label: str,
    missing: str | None = None,
) -> str:
    if "/" in command or "\\" in command or command in {".", ".."}:
        raise CodexCliAdapterError(f"{label} must be a basename on PATH")
    search_path = (
        "/usr/bin" if parent_env is None else parent_env.get("PATH", "/usr/bin")
    )
    located = shutil.which(command, path=search_path)
    if located is None:
        raise CodexCliAdapterError(missing or f"{label} is not on PATH")
    return located


def _prefixed_digest_text(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"

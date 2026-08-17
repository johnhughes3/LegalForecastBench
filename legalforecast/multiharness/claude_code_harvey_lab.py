"""Clean-native Claude Code → Harvey LAB composition.

Wires landed modules: projection → contained ``claude -p`` with native tools
→ sandbox output discovery → isolated evaluator → authorized scoring.
Does not invent a second RunSpec, ExecutionReceipt, or failure-class family.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_CLEAN_NATIVE_TOOLS,
    CLAUDE_CODE_EXECUTABLE_NAME,
    CLAUDE_CODE_OUTPUT_SCHEMA_NAME,
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
    build_claude_invocation_plan,
    classify_claude_completion_execution,
    encode_claude_code_tools_argv_token,
)
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    harvey_lab_issuer_policy_sha256,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATOR_COMMAND_NAME,
    EvaluatorRunner,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabEvaluatorProvenance,
    HarveyLabIsolatedEvaluation,
    HarveyLabJudgeRequestBoundary,
    invoke_isolated_harvey_lab_evaluator,
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
    project_harvey_lab_suite,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
    is_local_cli_sandbox_denial,
)
from legalforecast.multiharness.local_cli_identity import sha256_file
from legalforecast.multiharness.scoring import (
    ScoreArtifact,
    build_harvey_lab_metric_definition,
)

HARVEY_LAB_COMPLETION_SCHEMA: dict[str, Any] = {
    "additionalProperties": False,
    "properties": {
        "deliverable": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["deliverable", "status"],
    "type": "object",
}


@dataclass(frozen=True, slots=True)
class ClaudeCodeHarveyLabPipelineResult:
    """Receipts chain for one clean-native Claude Code Harvey LAB run."""

    projection: HarveyLabProjectionResult
    task: HarveyLabProjectedTask
    solver_spec: RunSpec
    solver_execution: ExecutionReceipt
    discovery: HarveyLabOutputDiscoveryResult
    evaluation: HarveyLabIsolatedEvaluation
    score: ScoreArtifact


def run_claude_code_clean_native_harvey_lab(
    *,
    adapter: ClaudeCodeCliAdapter,
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
    model: str = "claude-sonnet-4-6",
    timeout_seconds: float | None = None,
    output_root: Path | None = None,
    allowed_tools: Sequence[str] | None = None,
    escape_watch_roots: Sequence[Path] = (),
    evaluator_command: str = EVALUATOR_COMMAND_NAME,
    measurement_id: str | None = None,
    evaluation_attempt_id: str | None = None,
    attempt_nonce: str | None = None,
    max_budget_usd: str | None = None,
    before_solver: Callable[[RunSpec], None] | None = None,
    after_solver: Callable[[RunSpec, ExecutionReceipt], ExecutionReceipt] | None = None,
    before_evaluator: Callable[[], None] | None = None,
    after_evaluator: Callable[[HarveyLabIsolatedEvaluation], None] | None = None,
    judge_request_boundary: HarveyLabJudgeRequestBoundary | None = None,
    evaluator_runner: EvaluatorRunner | None = None,
    evaluator_provenance: HarveyLabEvaluatorProvenance | None = None,
    require_production_provenance: bool = False,
) -> ClaudeCodeHarveyLabPipelineResult:
    """Project a LAB task, run contained Claude Code, discover, and score."""

    service = adapter.execution_service
    tools = tuple(
        CLAUDE_CODE_CLEAN_NATIVE_TOOLS if allowed_tools is None else allowed_tools
    )
    if not tools:
        raise ClaudeCodeCliAdapterError(
            "clean-native Harvey LAB runs must enable native --tools"
        )
    tools_token = encode_claude_code_tools_argv_token(tools)
    if tools_token == "":
        raise ClaudeCodeCliAdapterError(
            "clean-native Harvey LAB runs must not keep the empty --tools pin"
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
        raise ClaudeCodeCliAdapterError(
            "Harvey LAB projection did not produce exactly the frozen issue-196 task"
        )
    task = projection.manifest.tasks[0]
    task_dir = projection.solver_root / task.relative_path
    instructions = task_dir / INSTRUCTIONS_NAME
    prompt = _lab_solver_prompt(instructions, task.expected_deliverable)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    resolved_output = require_harvey_lab_sandbox_hosts(
        sandbox_root=sandbox_root,
        output_root=output_root or (sandbox_root / "output"),
    )
    schema_path = sandbox_root / CLAUDE_CODE_OUTPUT_SCHEMA_NAME
    schema_path.write_text(
        json.dumps(
            HARVEY_LAB_COMPLETION_SCHEMA,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    declared_timeout = float(adapter.local_manifest.timeout_retry.timeout_seconds)
    applied_timeout = (
        declared_timeout
        if timeout_seconds is None
        else min(float(timeout_seconds), declared_timeout)
    )
    plan = build_claude_invocation_plan(
        prompt=prompt,
        model=model,
        required_unit_ids=(),
        workspace=sandbox_root,
        output_schema_path=schema_path,
        allowed_tools=tools,
        manifest=adapter.local_manifest,
        auth_profile=adapter.auth_profile,
        json_schema=HARVEY_LAB_COMPLETION_SCHEMA,
        extra_add_dirs=(task_dir,),
        max_budget_usd=max_budget_usd,
    )
    if plan.argv[plan.argv.index("--tools") + 1] != tools_token:
        raise ClaudeCodeCliAdapterError(
            "clean-native --tools argv token drifted from the frozen encoding"
        )
    _require_on_path(
        CLAUDE_CODE_EXECUTABLE_NAME,
        service.parent_env,
        label="clean-native Claude Code executable",
        missing="local CLI executable could not be launched",
    )
    spec = RunSpec(
        spec_id=task.task_id,
        argv=plan.argv,
        working_directory=sandbox_root,
        environment={},
        timeout_seconds=applied_timeout,
        json_schema=plan.json_schema,
        max_budget_usd=(None if max_budget_usd is None else float(max_budget_usd)),
    )
    if before_solver is not None:
        before_solver(spec)
    execution = service.execute(spec)
    if after_solver is not None:
        execution = after_solver(spec, execution)
    _require_solver_success(spec, execution, requested_model=model)
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
        raise ClaudeCodeCliAdapterError(
            "discovered outputs include quarantined files; scoring refused"
        )
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
    if before_evaluator is not None:
        before_evaluator()
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
        judge_request_boundary=judge_request_boundary,
        evaluator_runner=evaluator_runner,
        evaluator_provenance=evaluator_provenance,
        require_production_provenance=require_production_provenance,
    )
    if after_evaluator is not None:
        after_evaluator(evaluation)
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
    return ClaudeCodeHarveyLabPipelineResult(
        projection=projection,
        task=task,
        solver_spec=spec,
        solver_execution=execution,
        discovery=discovery,
        evaluation=evaluation,
        score=score,
    )


def _lab_solver_prompt(instructions: Path, expected_deliverable: str) -> str:
    if not instructions.is_file():
        raise ClaudeCodeCliAdapterError(
            "projected Harvey LAB task is missing instructions.txt"
        )
    body = instructions.read_text(encoding="utf-8").strip()
    if not body:
        raise ClaudeCodeCliAdapterError(
            "projected Harvey LAB instructions must be non-empty"
        )
    return (
        f"{body}\n\n"
        "Write the expected deliverable "
        f"{expected_deliverable} into the output directory under the working "
        "directory. Use only in-sandbox native tools."
    )


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


def _require_solver_success(
    spec: RunSpec,
    execution: ExecutionReceipt,
    *,
    requested_model: str,
) -> None:
    """Refuse to score a LAB run that is not a clean, correctly served success.

    The classification order is the shared adapter-core taxonomy rather than a
    LAB-local copy: ``cancelled`` is a lifecycle abort, not a crash, and a
    served-model mismatch is ``identity_drift`` even when the CLI exits zero.
    """

    if execution.spec_sha256 != spec.spec_sha256:
        raise ClaudeCodeCliAdapterError("execution receipt does not bind the RunSpec")
    failure_class = classify_claude_completion_execution(
        execution,
        requested_model=requested_model,
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


def _require_on_path(
    command: str,
    parent_env: Mapping[str, str] | None,
    *,
    label: str,
    missing: str | None = None,
) -> str:
    if "/" in command or "\\" in command or command in {".", ".."}:
        raise ClaudeCodeCliAdapterError(f"{label} must be a basename on PATH")
    search_path = (
        "/usr/bin" if parent_env is None else parent_env.get("PATH", "/usr/bin")
    )
    located = shutil.which(command, path=search_path)
    if located is None:
        raise ClaudeCodeCliAdapterError(missing or f"{label} is not on PATH")
    return located


def _prefixed_digest_text(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"

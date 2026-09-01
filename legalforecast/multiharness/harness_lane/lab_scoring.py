"""Score the harness lane's Harvey LAB leg with LAB's own native evaluator.

A LAB row is *not* an MTD forecast.  It has no probability, no outcome label
and no Brier score, and ``legalforecast score`` -- which reads
``lfb/runs.jsonl`` over ``lfb_brier`` -- can never apply to one.  LAB is scored
by the pinned 23-criterion all-pass rubric its own evaluator owns, and that
evaluator must never be reachable from a solver: its gold ``criteria`` live in
the evaluator-private half of the projection, which this module reads *after*
the harness has finished and never stages into a workspace.

So the two legs stay disjoint by construction rather than by convention:

* LFB rows land in ``lfb/runs.jsonl`` and carry probabilities.
* LAB rows land in ``lab/scores.jsonl`` and carry ``score_value`` in
  ``{0, 1}`` under ``metric_id: harvey-lab-binary-all-pass-v1``.

Nothing in either file is an official benchmark number: every record here
names the container adapter that produced it and the
``container_cli_tools_on`` backend, which is the whole point of the lane --
these are harness-vs-API measurements, run with an agentic CLI's own tools
live, and they answer a different question than the benchmark does.

This is a composition, not a new mechanism.  It wires modules that already
exist and are already tested -- ``verify_harvey_lab_projection`` →
``discover_harvey_lab_outputs`` → ``invoke_isolated_harvey_lab_evaluator`` →
``verify_authorized_harvey_lab_receipt`` -- in the same order
``codex_cli_harvey_lab`` and ``claude_code_harvey_lab`` wire them for the
clean-native lane.  The judge identity, the signer and the issuer key are
parameters for the same reason they are there: this module has no authority to
mint any of them, and a fixture judge must never be able to masquerade as a
production one.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast._json_io import read_jsonl_objects, write_jsonl_objects_safe
from legalforecast.multiharness.harness_lane.lab_workspace import LAB_OUTPUT_DIRECTORY
from legalforecast.multiharness.harness_lane.release_evidence import (
    CONTAINER_EXECUTION_BACKEND,
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
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryResult,
    discover_harvey_lab_outputs,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabProjectedTask,
    HarveyLabProjectionError,
    HarveyLabProjectionManifest,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.local_cli_identity import sha256_file
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import (
    ScoreArtifact,
    build_harvey_lab_metric_definition,
)
from legalforecast.multiharness.validation import validate_public_record

LAB_DIRECTORY: Final = "lab"
LAB_RESULTS_NAME: Final = "task-results.jsonl"
LAB_SCORES_NAME: Final = "scores.jsonl"
CONTAINER_WORKSPACE_DIRECTORY: Final = "container-workspace"
ROWS_DIRECTORY: Final = "rows"
LAB_SCORING_MODE: Final = "lab_native"
LAB_METRIC_ID: Final = "harvey-lab-binary-all-pass-v1"
DEFAULT_EVALUATOR_TIMEOUT_SECONDS: Final = 300.0


class LabScoringError(ValueError):
    """Raised when a harness-lane LAB row cannot be scored fail-closed."""


@dataclass(frozen=True, slots=True)
class LabRowScore:
    """One LAB row's outcome: an authorized score, or why there is none."""

    row_id: str
    task_id: str
    record: Mapping[str, Any]
    score: ScoreArtifact | None
    discovery: HarveyLabOutputDiscoveryResult | None = None

    @property
    def scored(self) -> bool:
        return self.score is not None


def score_harness_lane_lab_run(
    *,
    run_dir: Path,
    projection_root: Path,
    evaluator_private_root: Path,
    work_root: Path,
    signer: Callable[[bytes], bytes],
    issuer_public_key: Ed25519PublicKey,
    execution_service: LocalCliExecutionService,
    evaluator_command: str = EVALUATOR_COMMAND_NAME,
    timeout_seconds: float = DEFAULT_EVALUATOR_TIMEOUT_SECONDS,
) -> tuple[LabRowScore, ...]:
    """Score every LAB row of one run directory and write ``lab/scores.jsonl``.

    ``work_root`` holds the sealed, quarantined and overlay trees one row at a
    time.  It must be outside ``run_dir/rows`` -- the sandbox, the sealed
    deliverable and the evaluator-private material are required to be pairwise
    disjoint, and discovery refuses the layout rather than trusting the caller.
    """

    rows = _lab_rows(run_dir)
    manifest = _projection_manifest(projection_root)
    projected = {task.task_id: task for task in manifest.tasks}
    wrapper_sha256 = _wrapper_sha256(evaluator_command, execution_service)
    scores = tuple(
        _score_row(
            row,
            run_dir=run_dir,
            projection_root=projection_root,
            evaluator_private_root=evaluator_private_root,
            work_root=work_root,
            projected=projected,
            manifest=manifest,
            wrapper_sha256=wrapper_sha256,
            signer=signer,
            issuer_public_key=issuer_public_key,
            execution_service=execution_service,
            evaluator_command=evaluator_command,
            timeout_seconds=timeout_seconds,
        )
        for row in rows
    )
    write_jsonl_objects_safe(
        run_dir / LAB_DIRECTORY / LAB_SCORES_NAME,
        [dict(item.record) for item in scores],
    )
    return scores


def _score_row(
    row: Mapping[str, Any],
    *,
    run_dir: Path,
    projection_root: Path,
    evaluator_private_root: Path,
    work_root: Path,
    projected: Mapping[str, HarveyLabProjectedTask],
    manifest: HarveyLabProjectionManifest,
    wrapper_sha256: str,
    signer: Callable[[bytes], bytes],
    issuer_public_key: Ed25519PublicKey,
    execution_service: LocalCliExecutionService,
    evaluator_command: str,
    timeout_seconds: float,
) -> LabRowScore:
    identity = _row_identity(row)
    task = projected.get(identity["task_id"])
    if task is None:
        raise LabScoringError(
            f"run row {identity['row_id']} names LAB task {identity['task_id']}, "
            "which this projection does not contain; score the run against the "
            "projected root it was run over"
        )
    status = _row_status(row)
    if status != "succeeded":
        return LabRowScore(
            row_id=identity["row_id"],
            task_id=identity["task_id"],
            record=_record(identity, task, score=None, unscored_reason=status),
            score=None,
        )
    sandbox_root = (
        run_dir / ROWS_DIRECTORY / identity["row_id"] / CONTAINER_WORKSPACE_DIRECTORY
    )
    if not sandbox_root.is_dir():
        raise LabScoringError(
            f"run row {identity['row_id']} has no {CONTAINER_WORKSPACE_DIRECTORY}/ "
            "to score; the harness workspace is the only place a LAB deliverable "
            "can come from"
        )
    row_work = _row_work_root(work_root, identity["row_id"])
    discovery = discover_harvey_lab_outputs(
        sandbox_root=sandbox_root,
        output_root=sandbox_root / LAB_OUTPUT_DIRECTORY,
        quarantine_root=row_work / "quarantine",
        sealed_root=row_work / "sealed",
        task=task,
        task_sha256=task.task_sha256,
        run_sha256=identity["request_sha256"],
        config_sha256=identity["request_sha256"],
        layout="native",
        evaluator_private_root=evaluator_private_root,
        projection_root=projection_root,
    )
    if discovery.quarantined:
        raise LabScoringError(
            f"run row {identity['row_id']} left unrecognized files in "
            f"{LAB_OUTPUT_DIRECTORY}/; quarantined extras are never scored"
        )
    evaluation = invoke_isolated_harvey_lab_evaluator(
        hosts=HarveyLabEvaluationHosts(
            sealed_deliverable_root=row_work / "sealed",
            evaluator_private_root=evaluator_private_root,
            overlay_root=row_work / "overlay",
            working_directory=row_work / "eval-cwd",
            solver_projection_root=projection_root,
        ),
        sealed_manifest=discovery.sealed,
        identity=HarveyLabEvaluationIdentity(
            lab_task_id=task.lab_task_id,
            task_sha256=_prefixed(task.task_sha256),
            expected_deliverable_basename=task.expected_deliverable,
            projection_manifest_sha256=manifest.manifest_sha256,
            wrapper_sha256=wrapper_sha256,
            run_sha256=_prefixed(identity["request_sha256"]),
            config_sha256=_prefixed(identity["request_sha256"]),
            pin=manifest.pin,
        ),
        execution_service=execution_service,
        signer=signer,
        issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        evaluator_command=evaluator_command,
        timeout_seconds=timeout_seconds,
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
    return LabRowScore(
        row_id=identity["row_id"],
        task_id=identity["task_id"],
        record=_record(
            identity,
            task,
            score=score,
            unscored_reason=None,
            deliverable_manifest_sha256=discovery.sealed.manifest_sha256,
            measurement_id=evaluation.receipt.measurement_id,
        ),
        score=score,
        discovery=discovery,
    )


def _record(
    identity: Mapping[str, str],
    task: HarveyLabProjectedTask,
    *,
    score: ScoreArtifact | None,
    unscored_reason: str | None,
    deliverable_manifest_sha256: str | None = None,
    measurement_id: str | None = None,
) -> dict[str, Any]:
    """Return one public LAB score row, shaped so it cannot read as a forecast.

    There is deliberately no probability, no unit_id and no ``raw_output``
    here: the fields an LFB Brier row is made of are absent, so a LAB record
    that wandered into an LFB reader would be refused for missing them rather
    than silently averaged into a forecast score.
    """

    record: dict[str, Any] = {
        "row_id": identity["row_id"],
        "task_id": identity["task_id"],
        "lab_task_id": task.lab_task_id,
        "category": task.category,
        "expected_deliverable": task.expected_deliverable,
        "adapter_id": identity["adapter_id"],
        "adapter_version": identity["adapter_version"],
        "model_key": identity["model_key"],
        "solver_id": f"{identity['adapter_id']}:{identity['model_key']}",
        "request_sha256": identity["request_sha256"],
        "scoring_mode": LAB_SCORING_MODE,
        "execution_backend": CONTAINER_EXECUTION_BACKEND,
        "metric_id": LAB_METRIC_ID,
        "deliverable_manifest_sha256": deliverable_manifest_sha256,
        "measurement_id": measurement_id,
        "unscored_reason": unscored_reason,
        "score": None if score is None else dict(score.to_record()),
    }
    validate_public_record(record, "harness lane LAB score")
    return record


def _row_identity(row: Mapping[str, Any]) -> dict[str, str]:
    fields = (
        "row_id",
        "task_id",
        "adapter_id",
        "adapter_version",
        "model_key",
        "request_sha256",
    )
    identity: dict[str, str] = {}
    for name in fields:
        value = row.get(name)
        if not isinstance(value, str) or not value.strip():
            raise LabScoringError(
                f"{LAB_DIRECTORY}/{LAB_RESULTS_NAME} row is missing {name}"
            )
        identity[name] = value
    return identity


def _row_status(row: Mapping[str, Any]) -> str:
    result = row.get("result")
    if not isinstance(result, Mapping):
        raise LabScoringError(
            f"{LAB_DIRECTORY}/{LAB_RESULTS_NAME} row carries no result object"
        )
    status = _optional_str(cast(Mapping[str, Any], result).get("status"))
    if status is None:
        raise LabScoringError(
            f"{LAB_DIRECTORY}/{LAB_RESULTS_NAME} row result carries no status"
        )
    return status


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _lab_rows(run_dir: Path) -> tuple[Mapping[str, Any], ...]:
    path = run_dir / LAB_DIRECTORY / LAB_RESULTS_NAME
    rows = tuple(
        read_jsonl_objects(
            path,
            error_factory=LabScoringError,
            missing_message=lambda item: (
                f"no Harvey LAB rows to score at {item}; run the lane over "
                "--task-source harvey-lab first"
            ),
            non_object_message=lambda item, line: (
                f"LAB result row {line} in {item} must be an object"
            ),
        )
    )
    if not rows:
        raise LabScoringError(
            f"{LAB_DIRECTORY}/{LAB_RESULTS_NAME} is empty; there is nothing to score"
        )
    return rows


def _projection_manifest(projection_root: Path) -> HarveyLabProjectionManifest:
    """Re-authenticate the projection before any of its bytes are trusted."""

    try:
        return verify_harvey_lab_projection(projection_root)
    except HarveyLabProjectionError as exc:
        raise LabScoringError(
            f"projected Harvey LAB root did not verify: {exc}"
        ) from exc


def _row_work_root(work_root: Path, row_id: str) -> Path:
    row_work = work_root / row_id
    if row_work.exists() or row_work.is_symlink():
        raise LabScoringError(
            f"LAB scoring work directory for row {row_id} already exists; sealed "
            "and quarantined trees are created fresh so a stale deliverable can "
            "never be scored twice"
        )
    row_work.mkdir(mode=0o700, parents=True)
    return row_work


def _wrapper_sha256(
    evaluator_command: str, execution_service: LocalCliExecutionService
) -> str:
    if "/" in evaluator_command or evaluator_command in {".", ".."}:
        raise LabScoringError("evaluator command must be a basename on PATH")
    parent_env = execution_service.parent_env
    search_path = (
        "/usr/bin" if parent_env is None else parent_env.get("PATH", "/usr/bin")
    )
    located = shutil.which(evaluator_command, path=search_path)
    if located is None:
        raise LabScoringError(
            f"Harvey LAB evaluator {evaluator_command!r} is not on PATH; install "
            "the pinned wrapper before scoring"
        )
    return _prefixed(sha256_file(Path(located)))


def _prefixed(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"

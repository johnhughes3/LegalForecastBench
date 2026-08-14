"""Isolated Harvey LAB evaluator invocation.

Evaluate a sealed external deliverable without rerunning the solver. The
contained process sees only overlay paths listed in an explicit stdin
manifest, under the #685 POSIX process-group runtime (fixture-none, fresh
HOME/XDG, no ambient credentials). Overlay, solver projection, and
evaluator-private roots are pairwise disjoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.deliverables import (
    DeliverableManifest,
    validate_sealed_deliverable,
)
from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationReceipt,
    EvaluationSpec,
    EvaluationTokenUsage,
    MonotonicTiming,
    TokenCount,
    build_evaluation_receipt,
    build_evaluation_spec,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    issue_196_pin,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.validation import (
    validate_safe_relative_path,
    validate_sha256,
)

EVALUATION_INPUT_SCHEMA_VERSION = "legalforecast.harvey_lab_evaluation_input.v1"
EVALUATION_OUTPUT_SCHEMA_VERSION = "legalforecast.harvey_lab_evaluation_output.v1"
FIXTURE_JUDGE_IDENTITY = "fixture/stub@local"
EVALUATOR_COMMAND_NAME = "harvey-lab-eval"
_OVERLAY_DELIVERABLE = "output"
_OVERLAY_PRIVATE = "private"
_OVERLAY_RAW = "raw"


class HarveyLabEvaluationError(ValueError):
    """Raised when isolated LAB evaluation cannot proceed fail-closed."""


@dataclass(frozen=True, slots=True)
class HarveyLabEvaluationHosts:
    """Disjoint host directories for one isolated evaluation."""

    sealed_deliverable_root: Path
    evaluator_private_root: Path
    overlay_root: Path
    working_directory: Path
    solver_projection_root: Path | None = None
    evaluator_source_root: Path | None = None


@dataclass(frozen=True, slots=True)
class HarveyLabEvaluationIdentity:
    """Path-free bindings for one isolated evaluation."""

    lab_task_id: str
    task_sha256: str
    expected_deliverable_basename: str
    projection_manifest_sha256: str
    wrapper_sha256: str
    run_sha256: str
    config_sha256: str
    pin: HarveyLabPin = field(default_factory=issue_196_pin)


@dataclass(frozen=True, slots=True)
class HarveyLabIsolatedEvaluation:
    """Result of one contained evaluator invocation."""

    spec: EvaluationSpec
    receipt: EvaluationReceipt
    execution: ExecutionReceipt
    raw_result: bytes
    overlay_root: Path
    input_manifest: Mapping[str, object]


def build_contained_evaluator_run_spec(
    *,
    hosts: HarveyLabEvaluationHosts,
    sealed_manifest: DeliverableManifest,
    identity: HarveyLabEvaluationIdentity,
    evaluator_command: str = EVALUATOR_COMMAND_NAME,
    timeout_seconds: float = 30.0,
    mode: str = "succeed",
    spec_id: str | None = None,
) -> tuple[RunSpec, dict[str, object]]:
    """Prepare overlay bytes and a path-validated stdin manifest.

    The contained process cwd is the runtime scratch directory, so overlay
    locations are passed as validated absolute paths on stdin only.
    """

    overlay = _prepare_evaluation_overlay(
        hosts,
        sealed_manifest=sealed_manifest,
        identity=identity,
    )
    stdin_record = evaluation_input_record(
        hosts=hosts,
        overlay=overlay,
        sealed_manifest=sealed_manifest,
        identity=identity,
        mode=mode,
    )
    spec = RunSpec(
        spec_id=spec_id or f"harvey-lab-eval-{uuid4().hex[:12]}",
        argv=(evaluator_command,),
        working_directory=hosts.working_directory.resolve(),
        stdin_bytes=_canonical_json(stdin_record),
        timeout_seconds=timeout_seconds,
    )
    return spec, stdin_record


def invoke_isolated_harvey_lab_evaluator(
    *,
    hosts: HarveyLabEvaluationHosts,
    sealed_manifest: DeliverableManifest,
    identity: HarveyLabEvaluationIdentity,
    execution_service: LocalCliExecutionService,
    signer: Callable[[bytes], bytes],
    issuer_key_id: str,
    issuer_policy_sha256: str,
    evaluator_command: str = EVALUATOR_COMMAND_NAME,
    timeout_seconds: float = 30.0,
    measurement_id: str | None = None,
    evaluation_attempt_id: str | None = None,
    attempt_nonce: str | None = None,
) -> HarveyLabIsolatedEvaluation:
    """Run the common LAB evaluator in a contained boundary and bind a receipt."""

    _reject_checkout_env(hosts.evaluator_source_root)
    spec, stdin_record = build_contained_evaluator_run_spec(
        hosts=hosts,
        sealed_manifest=sealed_manifest,
        identity=identity,
        evaluator_command=evaluator_command,
        timeout_seconds=timeout_seconds,
    )
    started_monotonic = time.monotonic_ns()
    started_at = datetime.now(UTC)
    execution = execution_service.execute(spec)
    ended_monotonic = time.monotonic_ns()
    ended_at = datetime.now(UTC)
    if execution.status != "succeeded" or execution.returncode not in {0, None}:
        raise HarveyLabEvaluationError(
            "contained LAB evaluator failed; evaluation never reruns the solver"
        )
    scores_path = Path(str(stdin_record["scores_output_path"]))
    try:
        raw_result = scores_path.read_bytes()
    except OSError as exc:
        raise HarveyLabEvaluationError(
            "evaluator did not write the scores path listed in the input manifest"
        ) from exc
    evaluation_spec = _evaluation_spec(
        sealed_manifest=sealed_manifest,
        identity=identity,
        hosts=hosts,
        raw_result=raw_result,
    )
    receipt = build_evaluation_receipt(
        spec=evaluation_spec,
        signer=signer,
        measurement_id=measurement_id or f"measurement-{uuid4().hex[:12]}",
        evaluation_attempt_id=evaluation_attempt_id
        or f"eval-attempt-{uuid4().hex[:12]}",
        attempt_nonce=attempt_nonce or f"nonce-{uuid4().hex[:12]}",
        repeat_index=1,
        judge_resolved_identity=FIXTURE_JUDGE_IDENTITY,
        raw_result_sha256=_prefixed_digest(raw_result),
        raw_result_size_bytes=len(raw_result),
        raw_result_media_type="application/json",
        status="succeeded",
        token_usage=_fixture_token_usage(),
        cost=_fixture_cost(),
        timing=_timing(started_at, ended_at, started_monotonic, ended_monotonic),
        issuer_policy_sha256=_require_prefixed(
            issuer_policy_sha256, "issuer_policy_sha256"
        ),
        issuer_key_id=issuer_key_id,
    )
    write_json_object(
        hosts.overlay_root / "evaluation-output.json",
        {
            "schema_version": EVALUATION_OUTPUT_SCHEMA_VERSION,
            "evaluation_spec_sha256": evaluation_spec.spec_sha256,
            "receipt_sha256": receipt.receipt_sha256,
            "raw_result_sha256": _prefixed_digest(raw_result),
        },
    )
    return HarveyLabIsolatedEvaluation(
        spec=evaluation_spec,
        receipt=receipt,
        execution=execution,
        raw_result=raw_result,
        overlay_root=hosts.overlay_root.resolve(),
        input_manifest=stdin_record,
    )


def evaluation_input_record(
    *,
    hosts: HarveyLabEvaluationHosts,
    overlay: Mapping[str, Path],
    sealed_manifest: DeliverableManifest,
    identity: HarveyLabEvaluationIdentity,
    mode: str,
) -> dict[str, object]:
    """Return the explicit stdin manifest. Every path must stay in the overlay."""

    overlay_root = hosts.overlay_root.resolve()
    record: dict[str, object] = {
        "schema_version": EVALUATION_INPUT_SCHEMA_VERSION,
        "mode": mode,
        "lab_task_id": identity.lab_task_id,
        "expected_deliverable_basename": identity.expected_deliverable_basename,
        "deliverable_manifest_sha256": sealed_manifest.manifest_sha256,
        "deliverable_tree_sha256": sealed_manifest.tree_sha256,
        "task_sha256": _require_prefixed(identity.task_sha256, "task_sha256"),
        "projection_manifest_sha256": identity.projection_manifest_sha256,
        "private_material_sha256": _directory_digest(
            hosts.evaluator_private_root,
            "private_material_sha256",
        ),
        "deliverable_path": str(overlay["deliverable"]),
        "private_task_json_path": str(overlay["private_task_json"]),
        "scores_output_path": str(overlay["scores"]),
    }
    for field_name in (
        "deliverable_path",
        "private_task_json_path",
        "scores_output_path",
    ):
        _require_overlay_path(overlay_root, Path(str(record[field_name])), field_name)
    if hosts.solver_projection_root is not None:
        solver = hosts.solver_projection_root.resolve()
        encoded = json.dumps(record, sort_keys=True)
        if str(solver) in encoded:
            raise HarveyLabEvaluationError(
                "evaluation input must not name the solver projection root"
            )
    return record


def _prepare_evaluation_overlay(
    hosts: HarveyLabEvaluationHosts,
    *,
    sealed_manifest: DeliverableManifest,
    identity: HarveyLabEvaluationIdentity,
) -> dict[str, Path]:
    overlay = _fresh_root(hosts.overlay_root, "evaluation overlay")
    working = hosts.working_directory
    working.mkdir(parents=True, exist_ok=True)
    if working.is_symlink() or not working.is_dir():
        raise HarveyLabEvaluationError("working directory must be a real directory")
    private_root = hosts.evaluator_private_root.resolve()
    sealed_root = hosts.sealed_deliverable_root.resolve()
    roots = [overlay, private_root, sealed_root, working.resolve()]
    if hosts.solver_projection_root is not None:
        roots.append(hosts.solver_projection_root.resolve())
    _require_pairwise_disjoint(*roots)
    try:
        validate_sealed_deliverable(sealed_root, sealed_manifest)
    except (OSError, ValueError) as exc:
        raise HarveyLabEvaluationError(str(exc)) from exc
    basename = identity.expected_deliverable_basename
    if basename != Path(basename).name or basename in {".", ".."}:
        raise HarveyLabEvaluationError(
            "expected_deliverable_basename must be a single filename"
        )
    validate_safe_relative_path(basename, "expected_deliverable_basename")
    source = _deliverable_source(sealed_root, sealed_manifest, basename)
    deliverable_dest = overlay / _OVERLAY_DELIVERABLE / basename
    private_dest = overlay / _OVERLAY_PRIVATE / "task.json"
    scores_dest = overlay / _OVERLAY_RAW / "scores.json"
    _copy_regular_file(source, deliverable_dest)
    _copy_regular_file(
        _private_task_json(private_root, identity.lab_task_id), private_dest
    )
    scores_dest.parent.mkdir(parents=True, exist_ok=True)
    _seal_file(deliverable_dest)
    _seal_file(private_dest)
    return {
        "deliverable": deliverable_dest,
        "private_task_json": private_dest,
        "scores": scores_dest,
    }


def _deliverable_source(
    sealed_root: Path,
    manifest: DeliverableManifest,
    basename: str,
) -> Path:
    matches = [
        artifact
        for artifact in manifest.artifacts
        if Path(artifact.path).name == basename
    ]
    if len(matches) != 1:
        raise HarveyLabEvaluationError(
            f"sealed deliverable must contain exactly one file matching {basename}"
        )
    source = sealed_root / matches[0].path
    if source.is_symlink() or not source.is_file():
        raise HarveyLabEvaluationError(
            f"sealed deliverable file is missing: {basename}"
        )
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = matches[0].sha256.removeprefix("sha256:")
    if actual != expected:
        raise HarveyLabEvaluationError(f"sealed deliverable hash mismatch: {basename}")
    return source


def _private_task_json(private_root: Path, lab_task_id: str) -> Path:
    candidate = private_root / "tasks" / lab_task_id / "task.json"
    if candidate.is_file() and not candidate.is_symlink():
        return candidate
    fallback = private_root / "task.json"
    if fallback.is_file() and not fallback.is_symlink():
        return fallback
    raise HarveyLabEvaluationError(
        f"evaluator-private task.json is missing for {lab_task_id}"
    )


def _evaluation_spec(
    *,
    sealed_manifest: DeliverableManifest,
    identity: HarveyLabEvaluationIdentity,
    hosts: HarveyLabEvaluationHosts,
    raw_result: bytes,
) -> EvaluationSpec:
    pin = identity.pin
    private_digest = _directory_digest(
        hosts.evaluator_private_root,
        "private_material_sha256",
    )
    policy = _prefixed_json(
        {
            "containment": "posix_process_group.v1",
            "network": "none",
            "auth_profile": "fixture-none",
        }
    )
    del raw_result
    return build_evaluation_spec(
        evaluation_id="harvey-lab-employment-v1",
        deliverable_manifest_sha256=sealed_manifest.manifest_sha256,
        deliverable_tree_sha256=sealed_manifest.tree_sha256,
        task_sha256=_require_prefixed(identity.task_sha256, "task_sha256"),
        run_sha256=_require_prefixed(identity.run_sha256, "run_sha256"),
        config_sha256=_require_prefixed(identity.config_sha256, "config_sha256"),
        evaluator_repository=pin.repository,
        evaluator_commit=pin.commit,
        evaluator_tree=pin.tree,
        evaluator_file_manifest_sha256=_prefixed_json(
            {"pin": pin.to_record(), "wrapper_sha256": identity.wrapper_sha256}
        ),
        evaluator_image_digest=_prefixed_json({"kind": "fixture-cli"}),
        wrapper_sha256=_require_prefixed(identity.wrapper_sha256, "wrapper_sha256"),
        private_material_sha256=private_digest,
        rubric_sha256=private_digest,
        criteria_sha256=private_digest,
        aggregation_sha256=_prefixed_json({"aggregation_rule": "all_pass"}),
        judge_requested_identity=FIXTURE_JUDGE_IDENTITY,
        judge_settings_sha256=_prefixed_json({"judge": FIXTURE_JUDGE_IDENTITY}),
        judge_prompt_sha256=_prefixed_json({"entrypoint": "evaluate_run"}),
        judge_output_schema_sha256=_prefixed_json({"media_type": "application/json"}),
        runtime_policy_sha256=policy,
        egress_policy_sha256=policy,
        resource_policy_sha256=policy,
        token_accounting_policy_sha256=policy,
    )


def _reject_checkout_env(source_root: Path | None) -> None:
    if source_root is None:
        return
    if not source_root.is_dir():
        raise HarveyLabEvaluationError("evaluator source root does not exist")
    ambient = sorted(path.name for path in source_root.glob(".env*"))
    if ambient:
        names = ", ".join(ambient)
        raise HarveyLabEvaluationError(
            f"evaluator source root contains ambient env files: {names}"
        )


def _require_overlay_path(overlay_root: Path, path: Path, field_name: str) -> None:
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(overlay_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HarveyLabEvaluationError(
            f"evaluation input path escapes the overlay: {field_name}"
        ) from exc
    if resolved == overlay_root:
        raise HarveyLabEvaluationError(
            f"evaluation input path escapes the overlay: {field_name}"
        )


def _require_pairwise_disjoint(*roots: Path) -> None:
    normalized = tuple(root.resolve(strict=False) for root in roots)
    for index, first in enumerate(normalized):
        for second in normalized[index + 1 :]:
            if (
                first == second
                or first.is_relative_to(second)
                or second.is_relative_to(first)
            ):
                raise HarveyLabEvaluationError(
                    "evaluation hosts must be physically disjoint and non-nested"
                )


def _fresh_root(path: Path, label: str) -> Path:
    if path.exists() or path.is_symlink():
        raise HarveyLabEvaluationError(f"{label} must be a fresh, absent path")
    path.mkdir(parents=True)
    return path.resolve()


def _copy_regular_file(source: Path, destination: Path) -> None:
    source_stat = source.lstat()
    if source.is_symlink() or not stat.S_ISREG(source_stat.st_mode):
        raise HarveyLabEvaluationError(
            f"evaluation source must be a regular file: {source.name}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _seal_file(path: Path) -> None:
    os.chmod(path, 0o444)


def _directory_digest(root: Path, field_name: str) -> str:
    if root.is_symlink() or not root.is_dir():
        raise HarveyLabEvaluationError(f"{field_name} root must be a real directory")
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    return _prefixed_json({"files": entries})


def _fixture_token_usage() -> EvaluationTokenUsage:
    unknown = TokenCount(value=None, unknown_reason="not_reported")
    return EvaluationTokenUsage(
        source="evaluator_wrapper",
        input_tokens=unknown,
        output_tokens=unknown,
        cache_read_tokens=unknown,
        cache_write_tokens=unknown,
        reasoning_tokens=unknown,
        total_tokens=unknown,
    )


def _fixture_cost() -> CostMeasurement:
    return CostMeasurement(
        amount_microusd=None,
        currency=None,
        basis="unknown",
        pricing_snapshot_sha256=None,
        unknown_reason="not_applicable",
    )


def _timing(
    started_at: datetime,
    ended_at: datetime,
    started_monotonic: int,
    ended_monotonic: int,
) -> MonotonicTiming:
    if ended_monotonic < started_monotonic:
        ended_monotonic = started_monotonic
    return MonotonicTiming(
        clock_id="linux-clock-monotonic-raw",
        started_at_utc=_utc_z(started_at),
        ended_at_utc=_utc_z(ended_at),
        started_monotonic_ns=started_monotonic,
        ended_monotonic_ns=ended_monotonic,
        wall_elapsed_ns=ended_monotonic - started_monotonic,
        queue_elapsed_ns=0,
        summed_call_elapsed_ns=ended_monotonic - started_monotonic,
    )


def _utc_z(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_prefixed(value: str, field_name: str) -> str:
    canonical = value if value.startswith("sha256:") else f"sha256:{value}"
    validate_sha256(canonical, field_name)
    return canonical


def _prefixed_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _prefixed_json(record: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(record)).hexdigest()


def _canonical_json(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")

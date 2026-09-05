# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import os
import stat
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.deliverables import (
    DeliverableArtifactProjection,
    DeliverableManifest,
    seal_deliverable,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATOR_COMMAND_NAME,
    HarveyLabEvaluationError,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
    _directory_digest,
    _pin_wrapper_executable,
    build_contained_evaluator_run_spec,
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    HarveyLabProjectionResult,
    issue_196_pin,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from tests.test_harvey_lab_projection import (
    FIXTURE_PIN,
    GOLD_MARKER,
    _issue_196_source,
)

FAKE_EVALUATOR = (
    Path(__file__).resolve().parent / "fixtures" / "harvey_lab" / "fake_evaluator.py"
)
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"k" * 32)
ISSUER_POLICY = "sha256:" + "8" * 64
RUN_DIGEST = "sha256:" + "4" * 64
CONFIG_DIGEST = "sha256:" + "5" * 64


class _RecordingJudgeBoundary(HarveyLabJudgeRequestBoundary):
    def __init__(self) -> None:
        self.events: list[tuple[str, int, str, int]] = []

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        self.events.append(
            ("before", request.ordinal, request.criterion_id, request.attempt_index)
        )
        return request

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        assert reservation is request
        self.events.append(
            ("after", request.ordinal, request.criterion_id, request.attempt_index)
        )


def _fake_per_criterion_runner(
    service: LocalCliExecutionService,
    spec: RunSpec,
    boundary: HarveyLabJudgeRequestBoundary,
) -> ExecutionReceipt:
    for ordinal in range(1, 24):
        request = HarveyLabJudgeRequest(ordinal, f"criterion-{ordinal}")
        reservation = boundary.before_judge_call(request)
        boundary.after_judge_call(request, reservation, object())
    return service.execute(spec)


def test_isolated_evaluator_binds_receipt_without_solver_or_network(
    tmp_path: Path,
) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = _identity(projected, tmp_path)
    service = LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=env,
    )
    result = invoke_isolated_harvey_lab_evaluator(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=identity,
        execution_service=service,
        signer=PRIVATE_KEY.sign,
        issuer_key_id="evaluation-key-fixture",
        issuer_policy_sha256=ISSUER_POLICY,
        measurement_id="measurement-lab1",
        evaluation_attempt_id="eval-attempt-lab1",
        attempt_nonce="nonce-lab1",
    )
    assert result.receipt.status == "succeeded"
    assert result.criterion_count == 23
    assert result.spec.judge_requested_identity == "fixture/stub@local"
    assert result.receipt.judge_resolved_identity == "fixture/stub@local"
    assert result.spec.evaluator_commit == projected.manifest.pin.commit
    scores = json.loads(result.raw_result.decode("utf-8"))
    assert scores["n_criteria"] == 23
    assert scores["entrypoint"] == "evaluation.run_eval.evaluate_run"
    assert GOLD_MARKER not in result.raw_result.decode("utf-8")
    assert not list(projected.solver_root.rglob("scores.json"))
    stdin = json.dumps(dict(result.input_manifest), sort_keys=True)
    assert str(projected.solver_root.resolve()) not in stdin
    assert "harness.run" not in stdin
    if hasattr(time, "CLOCK_MONOTONIC_RAW"):
        assert result.receipt.timing.clock_id == "linux-clock-monotonic-raw"


def test_isolated_evaluator_runner_receives_each_23_criterion_boundary_callback(
    tmp_path: Path,
) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    boundary = _RecordingJudgeBoundary()
    result = invoke_isolated_harvey_lab_evaluator(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=_identity(projected, tmp_path),
        execution_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=env,
        ),
        signer=PRIVATE_KEY.sign,
        issuer_key_id="evaluation-key-fixture",
        issuer_policy_sha256=ISSUER_POLICY,
        judge_request_boundary=boundary,
        evaluator_runner=_fake_per_criterion_runner,
    )
    assert result.receipt.status == "succeeded"
    assert len(boundary.events) == 46
    assert boundary.events[::2] == [
        ("before", ordinal, f"criterion-{ordinal}", 0) for ordinal in range(1, 24)
    ]
    assert boundary.events[1::2] == [
        ("after", ordinal, f"criterion-{ordinal}", 0) for ordinal in range(1, 24)
    ]


def test_paid_evaluator_boundary_without_runner_fails_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    service = LocalCliExecutionService(auth_profile=FIXTURE_NONE, parent_env=env)

    def unexpected_execution(
        _service: LocalCliExecutionService, _spec: RunSpec
    ) -> ExecutionReceipt:
        raise AssertionError("paid evaluator launched without its runner")

    monkeypatch.setattr(LocalCliExecutionService, "execute", unexpected_execution)
    with pytest.raises(HarveyLabEvaluationError, match="per-criterion judge runner"):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            execution_service=service,
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
            judge_request_boundary=_RecordingJudgeBoundary(),
        )


def test_receipt_binds_to_copied_private_inputs_not_live_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = _identity(projected, tmp_path)
    private_json = (
        projected.evaluator_private_root / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
    )
    original = private_json.read_bytes()
    service = LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=env,
    )

    original_execute = LocalCliExecutionService.execute

    def mutate_then_execute(
        self: LocalCliExecutionService, spec: RunSpec
    ) -> ExecutionReceipt:
        os.chmod(private_json, stat.S_IWUSR | stat.S_IRUSR)
        private_json.write_bytes(original + b"\nMUTATED_AFTER_COPY\n")
        return original_execute(self, spec)

    monkeypatch.setattr(LocalCliExecutionService, "execute", mutate_then_execute)
    result = invoke_isolated_harvey_lab_evaluator(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=identity,
        execution_service=service,
        signer=PRIVATE_KEY.sign,
        issuer_key_id="evaluation-key-fixture",
        issuer_policy_sha256=ISSUER_POLICY,
        measurement_id="measurement-overlay-private",
        evaluation_attempt_id="eval-attempt-overlay-private",
        attempt_nonce="nonce-overlay-private",
    )
    overlay_private = Path(str(result.input_manifest["private_task_json_path"]))
    assert overlay_private.read_bytes() == original
    assert private_json.read_bytes() != original
    assert (
        result.spec.private_material_sha256
        == result.input_manifest["private_material_sha256"]
    )
    assert result.spec.private_material_sha256 == _directory_digest(
        overlay_private.parent,
        "private_material_sha256",
    )
    assert result.spec.private_material_sha256 != _directory_digest(
        private_json.parent,
        "private_material_sha256",
    )


def test_evaluator_env_has_no_ambient_credentials_or_solver_path(
    tmp_path: Path,
) -> None:
    env = _install_evaluator(tmp_path)
    env["ANTHROPIC_API_KEY"] = "ambient-anthropic-canary"
    env["OPENAI_API_KEY"] = "ambient-openai-canary"
    env["CANARY_SECRET"] = "must-not-leak"
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    spec, _stdin = build_contained_evaluator_run_spec(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=_identity(projected, tmp_path),
        mode="dump-env",
    )
    receipt = LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=env,
    ).execute(spec)
    assert receipt.status == "succeeded"
    child_env = json.loads(receipt.stdout)
    assert "ANTHROPIC_API_KEY" not in child_env
    assert "OPENAI_API_KEY" not in child_env
    assert "CANARY_SECRET" not in child_env
    dumped = json.dumps(child_env, sort_keys=True)
    assert str(projected.solver_root.resolve()) not in dumped
    assert "ambient-anthropic-canary" not in dumped


def test_solver_path_in_evaluation_input_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    spec, stdin_record = build_contained_evaluator_run_spec(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=_identity(projected, tmp_path),
    )
    malicious = dict(stdin_record)
    malicious["deliverable_root"] = str(
        projected.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "instructions.txt"
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="evaluation input path escapes the overlay: deliverable_root",
    ):
        from legalforecast.multiharness.harvey_lab_evaluator import (
            evaluation_input_record,
        )

        evaluation_input_record(
            hosts=hosts,
            overlay={
                "deliverable_root": Path(str(malicious["deliverable_root"])),
                "private_task_json": Path(str(stdin_record["private_task_json_path"])),
                "scores": Path(str(stdin_record["scores_output_path"])),
            },
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            mode="succeed",
        )
    del spec
    del env


def test_checkout_dotenv_is_rejected_before_spawn(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    source = tmp_path / "lab-checkout"
    source.mkdir()
    (source / ".env").write_text(
        "ANTHROPIC_API_KEY=should-not-load\n", encoding="utf-8"
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
        evaluator_source_root=source,
    )
    with pytest.raises(HarveyLabEvaluationError, match="ambient env files"):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def test_nested_solver_and_overlay_roots_fail_closed(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=projected.solver_root / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    with pytest.raises(HarveyLabEvaluationError, match="disjoint"):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def test_malicious_document_bytes_are_not_followed_as_paths(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    # Solver tree is sealed; the canary lives beside the sealed deliverable source.
    payload = b"../../solver-canary.txt\nSOLVER_CANARY=do-not-follow\n"
    source_root = tmp_path / "deliverable-source"
    source_root.mkdir()
    (source_root / "issue-identification-memo.docx").write_bytes(payload)
    sealed_root = tmp_path / "sealed"
    sealed = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=_task_digest(projected),
        run_sha256=RUN_DIGEST,
        config_sha256=CONFIG_DIGEST,
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="memo",
                source_path="issue-identification-memo.docx",
                path="issue-identification-memo.docx",
                media_type="application/octet-stream",
                max_size_bytes=4096,
            ),
        ),
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    spec, _stdin = build_contained_evaluator_run_spec(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=_identity(projected, tmp_path),
        mode="parser-bomb",
    )
    receipt = LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=env,
    ).execute(spec)
    assert receipt.status == "succeeded"
    scores_path = Path(str(_stdin["scores_output_path"]))
    assert scores_path.is_file()
    assert b"SOLVER_CANARY" not in scores_path.read_bytes()


def test_sibling_overlay_name_is_not_treated_as_solver_path(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "solver-overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    spec, stdin_record = build_contained_evaluator_run_spec(
        hosts=hosts,
        sealed_manifest=sealed,
        identity=_identity(projected, tmp_path),
    )
    assert Path(str(stdin_record["deliverable_paths"][0])).is_relative_to(
        (tmp_path / "solver-overlay").resolve()
    )
    del spec
    del env


def test_extra_sealed_artifact_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    source_root = tmp_path / "deliverable-source"
    source_root.mkdir()
    (source_root / "issue-identification-memo.docx").write_bytes(b"PK-fake-docx")
    (source_root / "extra.txt").write_text("nope", encoding="utf-8")
    sealed_root = tmp_path / "sealed"
    sealed = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=_task_digest(projected),
        run_sha256=RUN_DIGEST,
        config_sha256=CONFIG_DIGEST,
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="memo",
                source_path="issue-identification-memo.docx",
                path="issue-identification-memo.docx",
                media_type="application/octet-stream",
                max_size_bytes=4096,
            ),
            DeliverableArtifactProjection(
                artifact_id="extra",
                source_path="extra.txt",
                path="extra.txt",
                media_type="text/plain",
                max_size_bytes=4096,
            ),
        ),
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="exactly the expected basename",
    ):
        build_contained_evaluator_run_spec(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
        )
    del env


def test_absolute_evaluator_command_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    with pytest.raises(HarveyLabEvaluationError, match="must be a basename"):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
            evaluator_command=str(tmp_path / "bin" / EVALUATOR_COMMAND_NAME),
        )


def test_wrapper_pin_directories_are_unique_per_call(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    work = tmp_path / "work"
    first_digest, first_dir = _pin_wrapper_executable(EVALUATOR_COMMAND_NAME, env, work)
    second_digest, second_dir = _pin_wrapper_executable(
        EVALUATOR_COMMAND_NAME, env, work
    )
    assert first_digest == second_digest
    assert first_dir != second_dir
    assert first_dir.is_absolute()
    assert second_dir.is_absolute()
    assert first_dir.is_dir()
    assert second_dir.is_dir()
    assert (first_dir / EVALUATOR_COMMAND_NAME).is_file()
    assert (second_dir / EVALUATOR_COMMAND_NAME).is_file()


def test_wrapper_pin_from_relative_workdir_is_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_evaluator(tmp_path)
    monkeypatch.chdir(tmp_path)
    _digest, wrapper_dir = _pin_wrapper_executable(
        EVALUATOR_COMMAND_NAME, env, Path("work")
    )
    assert wrapper_dir.is_absolute()
    assert (wrapper_dir / EVALUATOR_COMMAND_NAME).is_file()
    assert wrapper_dir.parent == (tmp_path / "work").resolve()


def test_wrapper_hash_mismatch_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = replace(
        _identity(projected, tmp_path),
        wrapper_sha256="sha256:" + "c" * 64,
    )
    with pytest.raises(HarveyLabEvaluationError, match="wrapper_sha256 does not match"):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=identity,
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def test_sealed_identity_mismatch_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    source_root = tmp_path / "deliverable-source"
    source_root.mkdir()
    (source_root / "issue-identification-memo.docx").write_bytes(b"PK-fake-docx")
    sealed_root = tmp_path / "sealed"
    sealed = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256="sha256:" + "1" * 64,
        run_sha256=RUN_DIGEST,
        config_sha256=CONFIG_DIGEST,
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="memo",
                source_path="issue-identification-memo.docx",
                path="issue-identification-memo.docx",
                media_type="application/octet-stream",
                max_size_bytes=4096,
            ),
        ),
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="does not match evaluation identity",
    ):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def test_lab_task_id_path_escape_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = replace(
        _identity(projected, tmp_path),
        lab_task_id="../secret-task",
    )
    with pytest.raises(HarveyLabEvaluationError, match="parent segments"):
        build_contained_evaluator_run_spec(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=identity,
        )
    del env


def test_mutated_projection_bytes_fail_identity_bind(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    instructions = (
        projected.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "instructions.txt"
    )
    instructions.chmod(instructions.stat().st_mode | stat.S_IWUSR)
    instructions.write_text("mutated after projection", encoding="utf-8")
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="could not be bound to the solver projection",
    ):
        build_contained_evaluator_run_spec(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=_identity(projected, tmp_path),
        )
    del env


def test_official_pin_requires_evaluator_source_root(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = replace(_identity(projected, tmp_path), pin=issue_196_pin())
    with pytest.raises(
        HarveyLabEvaluationError,
        match="evaluator source root is required",
    ):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=identity,
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def test_projected_task_identity_mismatch_is_refused(tmp_path: Path) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path, projected)
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=tmp_path / "overlay",
        working_directory=tmp_path / "work",
        solver_projection_root=projected.solver_root,
    )
    identity = replace(
        _identity(projected, tmp_path),
        expected_deliverable_basenames=("other-memo.docx",),
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="expected_deliverable_basenames do not match",
    ):
        invoke_isolated_harvey_lab_evaluator(
            hosts=hosts,
            sealed_manifest=sealed,
            identity=identity,
            execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            signer=PRIVATE_KEY.sign,
            issuer_key_id="evaluation-key-fixture",
            issuer_policy_sha256=ISSUER_POLICY,
        )


def _project(tmp_path: Path) -> HarveyLabProjectionResult:
    source = _issue_196_source(tmp_path / "lab")
    return project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )


def _seal_deliverable(
    tmp_path: Path,
    projected: HarveyLabProjectionResult,
    payload: bytes = b"PK-fake-docx",
) -> tuple[Path, DeliverableManifest]:
    source_root = tmp_path / "deliverable-source"
    source_root.mkdir()
    (source_root / "issue-identification-memo.docx").write_bytes(payload)
    sealed_root = tmp_path / "sealed"
    manifest = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=_task_digest(projected),
        run_sha256=RUN_DIGEST,
        config_sha256=CONFIG_DIGEST,
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="memo",
                source_path="issue-identification-memo.docx",
                path="issue-identification-memo.docx",
                media_type="application/octet-stream",
                max_size_bytes=4096,
            ),
        ),
    )
    return sealed_root, manifest


def _task_digest(projected: HarveyLabProjectionResult) -> str:
    digest = projected.manifest.tasks[0].task_sha256
    return digest if digest.startswith("sha256:") else f"sha256:{digest}"


def _identity(
    projected: HarveyLabProjectionResult, tmp_path: Path
) -> HarveyLabEvaluationIdentity:
    wrapper = tmp_path / "bin" / EVALUATOR_COMMAND_NAME
    digest = (
        "sha256:" + __import__("hashlib").sha256(wrapper.read_bytes()).hexdigest()
        if wrapper.is_file()
        else "sha256:" + "c" * 64
    )
    return HarveyLabEvaluationIdentity(
        lab_task_id=ISSUE_196_LAB_TASK_ID,
        task_sha256=projected.manifest.tasks[0].task_sha256,
        expected_deliverable_basenames=("issue-identification-memo.docx",),
        projection_manifest_sha256=projected.manifest.manifest_sha256,
        wrapper_sha256=digest,
        run_sha256=RUN_DIGEST,
        config_sha256=CONFIG_DIGEST,
        pin=projected.manifest.pin,
    )


def _install_evaluator(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / EVALUATOR_COMMAND_NAME
    body = FAKE_EVALUATOR.read_text(encoding="utf-8")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]
    target.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
        "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
        "OPENAI_API_KEY": "ambient-openai-canary",
    }

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.deliverables import (
    DeliverableArtifactProjection,
    seal_deliverable,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATOR_COMMAND_NAME,
    HarveyLabEvaluationError,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    build_contained_evaluator_run_spec,
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from tests.test_harvey_lab_projection import GOLD_MARKER, _issue_196_source

FAKE_EVALUATOR = (
    Path(__file__).resolve().parent / "fixtures" / "harvey_lab" / "fake_evaluator.py"
)
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"k" * 32)
ISSUER_POLICY = "sha256:" + "8" * 64
RUN_DIGEST = "sha256:" + "4" * 64
CONFIG_DIGEST = "sha256:" + "5" * 64


def test_isolated_evaluator_binds_receipt_without_solver_or_network(
    tmp_path: Path,
) -> None:
    env = _install_evaluator(tmp_path)
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path)
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


def test_evaluator_env_has_no_ambient_credentials_or_solver_path(
    tmp_path: Path,
) -> None:
    env = _install_evaluator(tmp_path)
    env["ANTHROPIC_API_KEY"] = "ambient-anthropic-canary"
    env["OPENAI_API_KEY"] = "ambient-openai-canary"
    env["CANARY_SECRET"] = "must-not-leak"
    projected = _project(tmp_path)
    sealed_root, sealed = _seal_deliverable(tmp_path)
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
    sealed_root, sealed = _seal_deliverable(tmp_path)
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
    malicious["deliverable_path"] = str(
        projected.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "instructions.txt"
    )
    with pytest.raises(
        HarveyLabEvaluationError,
        match="evaluation input path escapes the overlay: deliverable_path",
    ):
        from legalforecast.multiharness.harvey_lab_evaluator import (
            evaluation_input_record,
        )

        evaluation_input_record(
            hosts=hosts,
            overlay={
                "deliverable": Path(str(malicious["deliverable_path"])),
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
    sealed_root, sealed = _seal_deliverable(tmp_path)
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
    sealed_root, sealed = _seal_deliverable(tmp_path)
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


def _project(tmp_path: Path):
    source = _issue_196_source(tmp_path / "lab")
    return project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
    )


def _seal_deliverable(tmp_path: Path):
    source_root = tmp_path / "deliverable-source"
    source_root.mkdir()
    (source_root / "issue-identification-memo.docx").write_bytes(b"PK-fake-docx")
    sealed_root = tmp_path / "sealed"
    manifest = seal_deliverable(
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
    return sealed_root, manifest


def _identity(projected, tmp_path: Path) -> HarveyLabEvaluationIdentity:
    wrapper = tmp_path / "bin" / EVALUATOR_COMMAND_NAME
    digest = (
        "sha256:" + __import__("hashlib").sha256(wrapper.read_bytes()).hexdigest()
        if wrapper.is_file()
        else "sha256:" + "c" * 64
    )
    return HarveyLabEvaluationIdentity(
        lab_task_id=ISSUE_196_LAB_TASK_ID,
        task_sha256=projected.manifest.tasks[0].task_sha256,
        expected_deliverable_basename="issue-identification-memo.docx",
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

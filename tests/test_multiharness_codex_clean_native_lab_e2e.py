"""Offline clean-native Codex CLI Harvey LAB composition.

Fake CLI plays the solver over a real projected fixture task. Zero live LAB
runs and zero provider spend. Required fail-closed mutations are named.
"""

from __future__ import annotations

import io
import os
import stat
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import legalforecast.multiharness.codex_cli_harvey_lab as codex_lab_composition
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapter,
    CodexCliAdapterError,
)
from legalforecast.multiharness.codex_cli_harvey_lab import (
    run_codex_cli_clean_native_harvey_lab,
)
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HarveyLabReceiptError,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.harvey_lab_evaluator import EVALUATOR_COMMAND_NAME
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryError,
    HarveyLabOutputErrorCode,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    HarveyLabProjectionResult,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import build_harvey_lab_metric_definition
from tests.test_harvey_lab_projection import (
    FIXTURE_PIN,
    _add_unselected_task,
    _issue_196_source,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE_CLI = ROOT / "tests" / "fixtures" / "local_cli_fake_cli.py"
FAKE_EVALUATOR = (
    ROOT / "tests" / "fixtures" / "codex_cli" / "fake_harvey_lab_evaluator.py"
)
LAB_BASENAME = "issue-identification-memo.docx"
KEY = Ed25519PrivateKey.from_private_bytes(b"L" * 32)


def test_fake_cli_lab_pipeline_binds_projection_receipt_discovery_and_score(
    tmp_path: Path,
) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    try:
        result = run_codex_cli_clean_native_harvey_lab(
            adapter=_adapter(env),
            pin=FIXTURE_PIN,
            signer=KEY.sign,
            issuer_public_key=KEY.public_key(),
            measurement_id="measurement-g1b",
            evaluation_attempt_id="eval-attempt-g1b",
            attempt_nonce="nonce-g1b",
            **hosts,
        )
    finally:
        _make_writable(tmp_path)

    argv = result.solver_spec.argv
    assert argv[0] == "codex"
    assert argv[1] == "exec"
    assert "--sandbox" in argv
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "--approve-for-me" not in argv
    assert "--ask-for-approval" not in argv
    assert argv[-1] == "-"
    assert result.solver_spec.stdin_bytes
    assert result.solver_execution.spec_sha256 == result.solver_spec.spec_sha256
    assert result.solver_execution.status == "succeeded"
    assert result.task.lab_task_id == ISSUE_196_LAB_TASK_ID
    assert result.discovery.expected_deliverable == LAB_BASENAME
    assert result.discovery.quarantined == ()
    assert result.discovery.sealed.manifest_sha256.startswith("sha256:")
    assert (
        result.evaluation.receipt.deliverable_manifest_sha256
        == result.discovery.sealed.manifest_sha256
    )
    assert result.evaluation.spec.task_sha256 == result.discovery.sealed.task_sha256
    assert (
        result.score.evaluation_receipt_sha256
        == result.evaluation.receipt.receipt_sha256
    )
    assert result.score.score_value == 1
    assert result.score.n_passed == result.score.n_criteria == 23
    assert (tmp_path / "sealed" / LAB_BASENAME).is_file()
    assert not list((tmp_path / "solver").rglob("gold-answers.json"))


def test_pipeline_selects_only_the_frozen_issue_196_task(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    _add_unselected_task(hosts["source_root"])
    try:
        result = run_codex_cli_clean_native_harvey_lab(
            adapter=_adapter(env),
            pin=FIXTURE_PIN,
            signer=KEY.sign,
            issuer_public_key=KEY.public_key(),
            **hosts,
        )
    finally:
        _make_writable(tmp_path)

    assert result.task.lab_task_id == ISSUE_196_LAB_TASK_ID
    assert tuple(task.lab_task_id for task in result.projection.manifest.tasks) == (
        ISSUE_196_LAB_TASK_ID,
    )


def test_pipeline_refuses_an_invalid_projection_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    real_project = codex_lab_composition.project_harvey_lab_suite

    def project_without_tasks(
        *args: object, **kwargs: object
    ) -> HarveyLabProjectionResult:
        projection = real_project(*args, **kwargs)
        return replace(
            projection,
            manifest=replace(projection.manifest, tasks=()),
        )

    monkeypatch.setattr(
        codex_lab_composition,
        "project_harvey_lab_suite",
        project_without_tasks,
    )
    try:
        with pytest.raises(
            CodexCliAdapterError,
            match=(
                "Harvey LAB projection did not produce exactly "
                "the frozen issue-196 task"
            ),
        ):
            run_codex_cli_clean_native_harvey_lab(
                adapter=_adapter(env),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                **hosts,
            )
    finally:
        _make_writable(tmp_path)

    assert not (tmp_path / "sealed").exists()


def test_sandbox_denial_classifies_at_top_of_stack(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path, outcome="sandbox_denial")
    hosts = _hosts(tmp_path)
    try:
        with pytest.raises(CodexCliAdapterError) as caught:
            run_codex_cli_clean_native_harvey_lab(
                adapter=_adapter(env),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert caught.value.failure_class is LocalCliFailureClass.SANDBOX_DENIAL
    assert caught.value.failure_class is not LocalCliFailureClass.CRASH
    assert "sandbox denial" in str(caught.value)
    assert not (tmp_path / "sealed").exists()
    assert not list((tmp_path / "sandbox" / "output").glob("*.docx"))


def test_broken_wrapper_path_fails_closed(tmp_path: Path) -> None:
    _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    broken = {
        "PATH": str(tmp_path / "empty-bin"),
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
    }
    (tmp_path / "empty-bin").mkdir()
    try:
        with pytest.raises(CodexCliAdapterError, match="could not be launched"):
            run_codex_cli_clean_native_harvey_lab(
                adapter=_adapter(broken),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert not (tmp_path / "sealed").exists()


def test_out_of_sandbox_output_file_is_not_scored(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    outside = tmp_path / "outside-sandbox"
    outside.mkdir()
    (outside / "planted-output.docx").write_bytes(_docx_bytes())
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            run_codex_cli_clean_native_harvey_lab(
                adapter=_adapter(env),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                escape_watch_roots=(outside,),
                measurement_id="measurement-escape",
                evaluation_attempt_id="eval-attempt-escape",
                attempt_nonce="nonce-escape",
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert caught.value.code == HarveyLabOutputErrorCode.SANDBOX_ESCAPE
    assert not (tmp_path / "sealed").exists()


def test_quarantined_extra_is_not_scored(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    extra = tmp_path / "sandbox" / "output"
    extra.mkdir(parents=True, exist_ok=True)
    (extra / "scratch-notes.txt").write_text("not scored", encoding="utf-8")
    try:
        with pytest.raises(
            CodexCliAdapterError, match="quarantined extras must not be scored"
        ):
            run_codex_cli_clean_native_harvey_lab(
                adapter=_adapter(env),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert (tmp_path / "quarantine" / "scratch-notes.txt").read_text(
        encoding="utf-8"
    ) == "not scored"
    assert not (tmp_path / "score.json").exists()


def test_swapped_scoring_input_digest_is_named(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path, outcome="success")
    hosts = _hosts(tmp_path)
    try:
        result = run_codex_cli_clean_native_harvey_lab(
            adapter=_adapter(env),
            pin=FIXTURE_PIN,
            signer=KEY.sign,
            issuer_public_key=KEY.public_key(),
            measurement_id="measurement-digest",
            evaluation_attempt_id="eval-attempt-digest",
            attempt_nonce="nonce-digest",
            **hosts,
        )
        swapped = "sha256:" + "9" * 64
        assert swapped != result.discovery.sealed.manifest_sha256
        metric = build_harvey_lab_metric_definition(
            rubric_sha256=result.evaluation.spec.rubric_sha256,
            criteria_sha256=result.evaluation.spec.criteria_sha256,
            aggregation_sha256=result.evaluation.spec.aggregation_sha256,
            output_schema_sha256=result.evaluation.spec.judge_output_schema_sha256,
        )
        with pytest.raises(HarveyLabReceiptError, match="deliverable_manifest_sha256"):
            verify_authorized_harvey_lab_receipt(
                result.evaluation.receipt.to_record(),
                raw_result=result.evaluation.raw_result,
                spec=result.evaluation.spec,
                metric=metric,
                issuer_public_key=KEY.public_key(),
                expected_measurement_id=result.evaluation.receipt.measurement_id,
                expected_evaluation_attempt_id=(
                    result.evaluation.receipt.evaluation_attempt_id
                ),
                expected_attempt_nonce=result.evaluation.receipt.attempt_nonce,
                expected_repeat_index=result.evaluation.receipt.repeat_index,
                expected_deliverable_manifest_sha256=swapped,
            )
    finally:
        _make_writable(tmp_path)


def _adapter(parent_env: dict[str, str]) -> CodexCliAdapter:
    return CodexCliAdapter(
        execution_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=parent_env,
        )
    )


def _hosts(tmp_path: Path) -> dict[str, Path]:
    return {
        "source_root": _issue_196_source(tmp_path / "lab"),
        "solver_root": tmp_path / "solver",
        "evaluator_private_root": tmp_path / "private",
        "sandbox_root": tmp_path / "sandbox",
        "sealed_root": tmp_path / "sealed",
        "quarantine_root": tmp_path / "quarantine",
        "overlay_root": tmp_path / "overlay",
        "evaluator_working_directory": tmp_path / "eval-work",
    }


def _install_binaries(tmp_path: Path, *, outcome: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_codex_wrapper(bin_dir / "codex", outcome=outcome)
    evaluator_body = FAKE_EVALUATOR.read_text(encoding="utf-8")
    if evaluator_body.startswith("#!"):
        evaluator_body = evaluator_body.split("\n", 1)[1]
    evaluator = bin_dir / EVALUATOR_COMMAND_NAME
    evaluator.write_text(
        "#!" + sys.executable + "\n" + evaluator_body, encoding="utf-8"
    )
    evaluator.chmod(
        evaluator.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
        "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
        "OPENAI_API_KEY": "ambient-openai-canary",
    }


def _install_codex_wrapper(path: Path, *, outcome: str) -> None:
    write_lab = ""
    if outcome == "success":
        write_lab = (
            "import io\n"
            "import sys\n"
            "import zipfile\n"
            "from pathlib import Path\n"
            "argv = sys.argv\n"
            "workspace = Path.cwd()\n"
            "if '--cd' in argv:\n"
            "    workspace = Path(argv[argv.index('--cd') + 1])\n"
            "output = workspace / 'output'\n"
            "output.mkdir(parents=True, exist_ok=True)\n"
            "destination = output / " + repr(LAB_BASENAME) + "\n"
            "buffer = io.BytesIO()\n"
            "with zipfile.ZipFile(buffer, 'w') as archive:\n"
            "    archive.writestr('[Content_Types].xml', '<Types></Types>')\n"
            "    archive.writestr('word/document.xml', '<w:document></w:document>')\n"
            "destination.write_bytes(buffer.getvalue())\n"
        )
    path.write_text(
        "#!"
        + sys.executable
        + "\n"
        + write_lab
        + "import os\n"
        + "import sys\n"
        + "os.execv(sys.executable, [sys.executable, "
        + repr(str(FAKE_CLI))
        + ", '--adapter', 'codex', '--outcome', "
        + repr(outcome)
        + ", *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        try:
            item.chmod(item.stat().st_mode | 0o200)
        except OSError:
            continue

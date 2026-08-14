# pyright: reportPrivateUsage=false

"""Offline clean-native Claude Code Harvey LAB composition.

Fake CLI plays the solver over a real projected fixture task. Zero live LAB
runs and zero provider spend. Required fail-closed mutations are named.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import TypedDict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_CLEAN_NATIVE_TOOLS,
    CLAUDE_CODE_TOOLS_ARGV_EXAMPLE,
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
    encode_claude_code_tools_argv_token,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    run_claude_code_clean_native_harvey_lab,
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
from legalforecast.multiharness.harvey_lab_projection import ISSUE_196_LAB_TASK_ID
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import build_harvey_lab_metric_definition
from tests.test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source

ROOT = Path(__file__).resolve().parents[1]
FAKE_CLI = ROOT / "tests" / "fixtures" / "local_cli_fake_cli.py"
FAKE_LAB_CLI = ROOT / "tests" / "fixtures" / "claude_code" / "fake_claude_lab_cli.py"
FAKE_EVALUATOR = (
    ROOT
    / "tests"
    / "fixtures"
    / "claude_code"
    / "fake_harvey_lab_authorized_evaluator.py"
)
LAB_BASENAME = "issue-identification-memo.docx"
KEY = Ed25519PrivateKey.from_private_bytes(b"L" * 32)


def test_fake_cli_lab_pipeline_binds_projection_receipt_discovery_and_score(
    tmp_path: Path,
) -> None:
    env = _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    try:
        result = run_claude_code_clean_native_harvey_lab(
            adapter=_adapter(env),
            pin=FIXTURE_PIN,
            signer=KEY.sign,
            issuer_public_key=KEY.public_key(),
            measurement_id="measurement-g1a",
            evaluation_attempt_id="eval-attempt-g1a",
            attempt_nonce="nonce-g1a",
            **hosts,
        )
    finally:
        _make_writable(tmp_path)

    tools_token = encode_claude_code_tools_argv_token(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert tools_token != ""
    assert "," in tools_token
    assert result.solver_spec.argv[result.solver_spec.argv.index("--tools") + 1] == (
        tools_token
    )
    assert result.solver_spec.argv.count("--tools") == 1
    next_token = result.solver_spec.argv[result.solver_spec.argv.index("--tools") + 2]
    assert next_token.startswith("--")
    assert "WebFetch" not in tools_token
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
    assert FAKE_CLI.is_file()


def test_broken_wrapper_path_fails_closed(tmp_path: Path) -> None:
    _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    broken = {
        "PATH": str(tmp_path / "empty-bin"),
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
    }
    (tmp_path / "empty-bin").mkdir()
    try:
        with pytest.raises(ClaudeCodeCliAdapterError, match="could not be launched"):
            run_claude_code_clean_native_harvey_lab(
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
    env = _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    outside = tmp_path / "outside-sandbox"
    outside.mkdir()
    (outside / "planted-output.docx").write_bytes(b"PK\x03\x04escaped")
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            run_claude_code_clean_native_harvey_lab(
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


def test_swapped_scoring_input_digest_is_named(tmp_path: Path) -> None:
    env = _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    try:
        result = run_claude_code_clean_native_harvey_lab(
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


def test_clean_native_tools_token_is_comma_joined_single_slot() -> None:
    token = encode_claude_code_tools_argv_token(("Read", "Glob"))
    assert token == CLAUDE_CODE_TOOLS_ARGV_EXAMPLE
    assert token == "Read,Glob"
    assert " " not in token
    native = encode_claude_code_tools_argv_token(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert native == ",".join(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert encode_claude_code_tools_argv_token(()) == ""


def _adapter(parent_env: dict[str, str]) -> ClaudeCodeCliAdapter:
    return ClaudeCodeCliAdapter(
        execution_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=parent_env,
        )
    )


class _LabHosts(TypedDict):
    source_root: Path
    solver_root: Path
    evaluator_private_root: Path
    sandbox_root: Path
    sealed_root: Path
    quarantine_root: Path
    overlay_root: Path
    evaluator_working_directory: Path


def _hosts(tmp_path: Path) -> _LabHosts:
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


def _install_binaries(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_trampoline(bin_dir / "claude", FAKE_LAB_CLI)
    _install_script(bin_dir / EVALUATOR_COMMAND_NAME, FAKE_EVALUATOR)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
        "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
        "OPENAI_API_KEY": "ambient-openai-canary",
    }


def _install_trampoline(path: Path, source: Path) -> None:
    path.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os\n"
        + "import sys\n"
        + "os.execv(sys.executable, [sys.executable, "
        + repr(str(source))
        + ", *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_script(path: Path, source: Path) -> None:
    body = source.read_text(encoding="utf-8")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]
    path.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        try:
            item.chmod(item.stat().st_mode | 0o200)
        except OSError:
            continue

# pyright: reportPrivateUsage=false

"""Pre-spawn host containment and completion classification for Harvey LAB.

Both guards run before scoring can happen: the host check refuses a bad
``output_root`` before the solver is launched at all, and the completion
classifier refuses a receipt that is cancelled or served by a different model
even when the CLI exits zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapterError
from legalforecast.multiharness.claude_code_harvey_lab import (
    _require_solver_success,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.codex_cli import CodexCliAdapter
from legalforecast.multiharness.codex_cli_harvey_lab import (
    run_codex_cli_clean_native_harvey_lab,
)
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryError,
    HarveyLabOutputErrorCode,
    require_harvey_lab_sandbox_hosts,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from tests.test_harvey_lab_projection import FIXTURE_PIN
from tests.test_multiharness_claude_clean_native_lab_e2e import (
    _adapter,
    _hosts,
    _make_writable,
)
from tests.test_multiharness_codex_clean_native_lab_e2e import (
    _hosts as _codex_lab_hosts,
)

KEY = Ed25519PrivateKey.from_private_bytes(b"G" * 32)
LAB_MODEL = "claude-sonnet-4-6"


def _empty_path_env(tmp_path: Path) -> dict[str, str]:
    """Return a parent env whose PATH holds no solver and no evaluator.

    A run that reaches the spawn preflight fails with "could not be launched".
    Any host-layout failure raised against this env therefore proves the check
    ran before the solver was reachable.
    """

    empty = tmp_path / "no-binaries"
    empty.mkdir()
    return {
        "PATH": str(empty),
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
    }


def test_require_hosts_accepts_a_real_directory_inside_the_sandbox(
    tmp_path: Path,
) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    resolved = require_harvey_lab_sandbox_hosts(
        sandbox_root=sandbox,
        output_root=sandbox / "output",
    )
    assert resolved == (sandbox / "output").resolve()
    assert resolved.is_dir()


def test_require_hosts_refuses_output_equal_to_the_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        require_harvey_lab_sandbox_hosts(sandbox_root=sandbox, output_root=sandbox)
    assert caught.value.code is HarveyLabOutputErrorCode.LAYOUT


def test_require_hosts_refuses_an_outside_output_without_creating_it(
    tmp_path: Path,
) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside" / "output"
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        require_harvey_lab_sandbox_hosts(sandbox_root=sandbox, output_root=outside)
    assert caught.value.code is HarveyLabOutputErrorCode.LAYOUT
    assert not outside.exists()
    assert not outside.parent.exists()


def test_require_hosts_refuses_an_output_symlink_into_the_sandbox(
    tmp_path: Path,
) -> None:
    sandbox = tmp_path / "sandbox"
    (sandbox / "real-output").mkdir(parents=True)
    link = sandbox / "output"
    link.symlink_to(sandbox / "real-output", target_is_directory=True)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        require_harvey_lab_sandbox_hosts(sandbox_root=sandbox, output_root=link)
    assert caught.value.code is HarveyLabOutputErrorCode.SYMLINK


def test_require_hosts_refuses_an_output_file(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    occupied = sandbox / "output"
    occupied.write_text("not a directory", encoding="utf-8")
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        require_harvey_lab_sandbox_hosts(sandbox_root=sandbox, output_root=occupied)
    assert caught.value.code is HarveyLabOutputErrorCode.LAYOUT


def test_claude_lab_refuses_an_out_of_sandbox_output_before_spawn(
    tmp_path: Path,
) -> None:
    hosts = _hosts(tmp_path)
    outside = tmp_path / "outside-sandbox" / "output"
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            run_claude_code_clean_native_harvey_lab(
                adapter=_adapter(_empty_path_env(tmp_path)),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                output_root=outside,
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert caught.value.code is HarveyLabOutputErrorCode.LAYOUT
    assert not outside.exists()
    assert not (tmp_path / "sandbox" / "claude-output-schema.json").exists()
    assert not (tmp_path / "sealed").exists()


def test_codex_lab_refuses_an_out_of_sandbox_output_before_spawn(
    tmp_path: Path,
) -> None:
    hosts = _codex_lab_hosts(tmp_path)
    outside = tmp_path / "outside-sandbox" / "output"
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            run_codex_cli_clean_native_harvey_lab(
                adapter=_codex_adapter(_empty_path_env(tmp_path)),
                pin=FIXTURE_PIN,
                signer=KEY.sign,
                issuer_public_key=KEY.public_key(),
                output_root=outside,
                **hosts,
            )
    finally:
        _make_writable(tmp_path)
    assert caught.value.code is HarveyLabOutputErrorCode.LAYOUT
    assert not outside.exists()
    assert not (tmp_path / "sealed").exists()


def _codex_adapter(parent_env: dict[str, str]) -> CodexCliAdapter:
    return CodexCliAdapter(
        execution_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=parent_env,
        )
    )


def _lab_spec(tmp_path: Path) -> RunSpec:
    workspace = tmp_path / "sandbox"
    workspace.mkdir(exist_ok=True)
    return RunSpec(
        spec_id="lab-task",
        argv=("claude", "-p", "--model", LAB_MODEL),
        working_directory=workspace,
        environment={},
        timeout_seconds=30.0,
    )


def _envelope(**fields: object) -> str:
    return json.dumps({"type": "result", **fields}, sort_keys=True)


def test_lab_cancelled_subtype_is_not_a_crash(tmp_path: Path) -> None:
    spec = _lab_spec(tmp_path)
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout=_envelope(subtype="cancelled", is_error=True, result="aborted"),
        returncode=1,
        status="failed",
    )
    with pytest.raises(ClaudeCodeCliAdapterError) as caught:
        _require_solver_success(spec, receipt, requested_model=LAB_MODEL)
    assert caught.value.failure_class is LocalCliFailureClass.CANCELLED


def test_lab_served_model_drift_is_identity_drift(tmp_path: Path) -> None:
    spec = _lab_spec(tmp_path)
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout=_envelope(
            subtype="success",
            is_error=False,
            model="claude-haiku-4-5",
            result={"deliverable": "memo.docx", "status": "done"},
        ),
    )
    with pytest.raises(ClaudeCodeCliAdapterError) as caught:
        _require_solver_success(spec, receipt, requested_model=LAB_MODEL)
    assert caught.value.failure_class is LocalCliFailureClass.IDENTITY_DRIFT


def test_lab_receipt_served_model_drift_is_identity_drift(tmp_path: Path) -> None:
    spec = _lab_spec(tmp_path)
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout=_envelope(
            subtype="success",
            is_error=False,
            model=LAB_MODEL,
            result={"deliverable": "memo.docx", "status": "done"},
        ),
        served_model="claude-opus-4-1",
    )
    with pytest.raises(ClaudeCodeCliAdapterError) as caught:
        _require_solver_success(spec, receipt, requested_model=LAB_MODEL)
    assert caught.value.failure_class is LocalCliFailureClass.IDENTITY_DRIFT


def test_lab_timeout_and_sandbox_denial_keep_their_classes(tmp_path: Path) -> None:
    spec = _lab_spec(tmp_path)
    timed_out = ExecutionReceipt.from_transcript(
        spec,
        stdout="",
        returncode=None,
        status="timeout",
        failure_class=LocalCliFailureClass.TIMEOUT.value,
    )
    with pytest.raises(ClaudeCodeCliAdapterError) as timeout_caught:
        _require_solver_success(spec, timed_out, requested_model=LAB_MODEL)
    assert timeout_caught.value.failure_class is LocalCliFailureClass.TIMEOUT
    denied = ExecutionReceipt.from_transcript(
        spec,
        stdout=_envelope(
            subtype="error_during_execution",
            is_error=True,
            result="sandbox denied write under landlock",
        ),
        returncode=1,
        status="failed",
    )
    with pytest.raises(ClaudeCodeCliAdapterError) as denial_caught:
        _require_solver_success(spec, denied, requested_model=LAB_MODEL)
    assert denial_caught.value.failure_class is LocalCliFailureClass.SANDBOX_DENIAL


def test_lab_matching_model_success_is_accepted(tmp_path: Path) -> None:
    spec = _lab_spec(tmp_path)
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout=_envelope(
            subtype="success",
            is_error=False,
            model=LAB_MODEL,
            result={"deliverable": "memo.docx", "status": "done"},
        ),
        served_model=LAB_MODEL,
    )
    _require_solver_success(spec, receipt, requested_model=LAB_MODEL)

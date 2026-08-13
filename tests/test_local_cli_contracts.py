from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.multiharness.claude_code import (
    declared_failure_classes as claude_failure_classes,
)
from legalforecast.multiharness.codex_cli import (
    declared_failure_classes as codex_failure_classes,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliContractError,
    LocalCliFailureClass,
    RunSpec,
    coerce_local_cli_failure_class,
    declared_local_cli_failure_classes,
    is_local_cli_sandbox_denial,
)

CONTRACTS_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "legalforecast"
    / "multiharness"
    / "local_cli_contracts.py"
)


def test_failure_taxonomy_is_identical_for_claude_and_codex() -> None:
    expected = (
        "timeout",
        "refusal",
        "schema_violation",
        "crash",
        "sandbox_denial",
    )
    assert declared_local_cli_failure_classes() == expected
    assert claude_failure_classes() == expected
    assert codex_failure_classes() == expected
    assert tuple(item.value for item in LocalCliFailureClass) == expected


def test_unknown_failure_class_coerces_to_schema_violation() -> None:
    assert (
        coerce_local_cli_failure_class("not-a-class")
        is LocalCliFailureClass.SCHEMA_VIOLATION
    )
    assert coerce_local_cli_failure_class("crash") is LocalCliFailureClass.CRASH


def test_receipt_unknown_failure_class_coerces_to_schema_violation() -> None:
    spec = _spec()
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout="denied",
        status="failed",
        returncode=1,
        failure_class="not-a-class",
    )
    assert receipt.failure_class == LocalCliFailureClass.SCHEMA_VIOLATION.value


def test_sandbox_denial_markers_are_error_path_substrings() -> None:
    assert is_local_cli_sandbox_denial("sandbox denied write under landlock")
    assert is_local_cli_sandbox_denial("seccomp filter refused the syscall")
    assert not is_local_cli_sandbox_denial("I cannot provide a forecast")
    assert is_local_cli_sandbox_denial("landlocked")


def test_run_spec_allows_codex_config_dash_c() -> None:
    spec = RunSpec(
        spec_id="spec-1",
        argv=(
            "codex",
            "exec",
            "-c",
            'approval_policy="never"',
        ),
        working_directory=Path("workspace"),
        stdin_bytes=b"solve fixture",
    )
    assert spec.argv[2] == "-c"
    assert spec.stdin_bytes == b"solve fixture"


def test_run_spec_rejects_shell_invocation() -> None:
    with pytest.raises(LocalCliContractError, match="shell"):
        RunSpec(
            spec_id="spec-1",
            argv=("sh", "-c", "codex exec"),
            working_directory=Path("workspace"),
        )
    with pytest.raises(LocalCliContractError, match="shell"):
        RunSpec(
            spec_id="spec-1",
            argv=("codex", "bash"),
            working_directory=Path("workspace"),
        )


def test_stdin_bytes_change_spec_identity_without_leaking_payload() -> None:
    empty = _spec()
    with_stdin = RunSpec(
        spec_id="spec-1",
        argv=("claude", "-p", "prompt"),
        working_directory=Path("workspace"),
        stdin_bytes=b"solve fixture",
    )
    assert empty.stdin_bytes == b""
    assert "stdin_sha256" not in empty.to_record()
    assert with_stdin.spec_sha256 != empty.spec_sha256
    assert "solve fixture" not in str(with_stdin.to_record())
    assert with_stdin.to_record()["stdin_sha256"].startswith("sha256:")
    restored = RunSpec.from_record(with_stdin.to_record())
    assert restored.spec_sha256 == with_stdin.spec_sha256
    assert restored.stdin_bytes == b""
    assert restored.stdin_sha256 == with_stdin.to_record()["stdin_sha256"]


def test_contracts_module_does_not_spawn_or_read_credentials() -> None:
    source = CONTRACTS_SOURCE.read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "Popen" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source


def _spec() -> RunSpec:
    return RunSpec(
        spec_id="spec-1",
        argv=("claude", "-p", "prompt"),
        working_directory=Path("workspace"),
    )

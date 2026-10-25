"""Terminal-success guard shared by the Codex LAB execution routes."""

from __future__ import annotations

from legalforecast.multiharness.codex_cli import (
    CodexCliAdapterError,
    classify_codex_execution,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
    coerce_local_cli_failure_class,
    is_local_cli_sandbox_denial,
)


def require_solver_success(
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

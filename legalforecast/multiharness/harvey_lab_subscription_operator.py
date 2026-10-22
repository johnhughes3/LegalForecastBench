"""Local subscription-backed community operator for the Claude Harvey LAB arm."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from legalforecast.multiharness.auth_binding import (
    bind_adapter_auth_profile,
    contained_execution_service,
)
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapter,
    claude_code_local_manifest,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    ClaudeCodeHarveyLabMeasurementResult,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EvaluatorProvenanceProvider,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionHarveyLabEvaluatorRunner,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    harvey_lab_v1_1_pin,
)
from legalforecast.multiharness.harvey_lab_subscription_judge import (
    build_subscription_judge,
    observed_model_from_receipt,
)
from legalforecast.multiharness.local_cli_identity import ExecutableIdentityPin
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.native_cli_subscription import (
    NativeCliSubscriptionPresence,
)


class CommunitySubscriptionOperatorError(RuntimeError):
    """The local community subscription route is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class CommunitySubscriptionOperatorRequest:
    """Prepared paths plus explicit native CLI and model pins."""

    source_root: Path
    projection_root: Path
    evaluator_private_root: Path
    run_root: Path
    evaluator_bin_dir: Path
    claude_version: str
    claude_sha256: str
    solver_model: str
    judge_model: str
    timeout_seconds: int = 900
    pin: HarveyLabPin = field(default_factory=harvey_lab_v1_1_pin)


@dataclass(frozen=True, slots=True)
class CommunitySubscriptionRuntime:
    """Distinct solver and judge services using one verified local login."""

    adapter: ClaudeCodeCliAdapter
    judge_service: LocalCliExecutionService
    evaluator_runner: ProductionHarveyLabEvaluatorRunner
    judge_boundary: HarveyLabJudgeRequestBoundary
    evaluator_provenance_provider: EvaluatorProvenanceProvider


def build_community_subscription_runtime(
    request: CommunitySubscriptionOperatorRequest,
) -> CommunitySubscriptionRuntime:
    """Build the local subscription solver and separate native CLI judge."""

    executable_pin = ExecutableIdentityPin(
        basename="claude",
        version=request.claude_version,
        sha256=request.claude_sha256,
        distribution_kind="standalone-cli",
    )
    manifest = claude_code_local_manifest()
    bound = bind_adapter_auth_profile(manifest, CONTRIBUTOR_SUBSCRIPTION)
    presence = NativeCliSubscriptionPresence(
        "claude",
        expected_version=request.claude_version,
    )
    parent_env = dict(os.environ)
    parent_env["PATH"] = (
        f"{request.evaluator_bin_dir}{os.pathsep}{parent_env.get('PATH', '/usr/bin')}"
    )
    solver_service = contained_execution_service(
        bound,
        parent_env=parent_env,
        adapter_id="claude-code-community-subscription-solver",
        display_name="Claude Code community subscription solver",
        executable_pin=executable_pin,
        subscription_presence=presence,
        filesystem_read_paths=(request.projection_root,),
        filesystem_write_paths=(request.run_root / "solver-workspace",),
    )
    judge_service = contained_execution_service(
        bound,
        parent_env=parent_env,
        adapter_id="claude-code-community-subscription-judge",
        display_name="Claude Code community subscription judge",
        executable_pin=executable_pin,
        subscription_presence=presence,
    )
    runner, boundary, provenance = build_subscription_judge(
        service=judge_service,
        model=request.judge_model,
        run_root=request.run_root,
        timeout_seconds=request.timeout_seconds,
        pin=request.pin,
        claude_sha256=request.claude_sha256,
    )
    return CommunitySubscriptionRuntime(
        adapter=ClaudeCodeCliAdapter(
            execution_service=solver_service,
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        ),
        judge_service=judge_service,
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance,
    )


def run_community_subscription_harvey_lab(
    request: CommunitySubscriptionOperatorRequest,
    *,
    runtime: CommunitySubscriptionRuntime | None = None,
) -> ClaudeCodeHarveyLabMeasurementResult:
    """Run the prepared community arm without API keys or hosted authority."""

    if request.run_root.exists() or request.run_root.is_symlink():
        raise CommunitySubscriptionOperatorError(
            "--run-dir must be a fresh, absent path"
        )
    selected = runtime or build_community_subscription_runtime(request)
    request.run_root.mkdir(parents=True)
    result = run_claude_code_clean_native_harvey_lab(
        adapter=selected.adapter,
        source_root=request.source_root,
        solver_root=request.projection_root,
        evaluator_private_root=request.evaluator_private_root,
        sandbox_root=request.run_root / "solver-workspace",
        sealed_root=request.run_root / "sealed",
        quarantine_root=request.run_root / "quarantine",
        overlay_root=request.run_root / "evaluator-overlay",
        evaluator_working_directory=request.run_root / "evaluator-work",
        pin=request.pin,
        model=request.solver_model,
        timeout_seconds=request.timeout_seconds,
        judge_request_boundary=selected.judge_boundary,
        evaluator_runner=selected.evaluator_runner,
        evaluator_provenance_provider=selected.evaluator_provenance_provider,
        require_production_provenance=True,
        evaluator_execution_service=selected.judge_service,
        container_workspace=False,
        use_prepared_projection=True,
        allow_model_alias=True,
    )
    if not isinstance(result, ClaudeCodeHarveyLabMeasurementResult):
        raise CommunitySubscriptionOperatorError(
            "community LAB operator unexpectedly produced an issuer result"
        )
    return result


__all__ = [
    "CommunitySubscriptionOperatorError",
    "CommunitySubscriptionOperatorRequest",
    "CommunitySubscriptionRuntime",
    "build_community_subscription_runtime",
    "observed_model_from_receipt",
    "run_community_subscription_harvey_lab",
]

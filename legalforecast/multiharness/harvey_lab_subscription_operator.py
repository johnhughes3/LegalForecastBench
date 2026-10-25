"""Local subscription-backed community operator for the Claude Harvey LAB arm."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

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
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapter,
    load_codex_local_cli_manifest,
)
from legalforecast.multiharness.codex_cli_harvey_lab import (
    CodexCliHarveyLabMeasurementResult,
    run_codex_cli_clean_native_harvey_lab,
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
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    LocalCliIdentityError,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.local_cli_probe import LocalCliProbeError
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.native_cli_preflight import preflight_native_cli
from legalforecast.multiharness.native_cli_subscription import (
    NativeCliSubscriptionPresence,
    validate_role_config_separation,
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
    solver_config_dir: Path
    judge_config_dir: Path
    claude_version: str
    claude_sha256: str
    solver_model: str
    judge_model: str
    harness: Literal["claude-code", "codex"] = "claude-code"
    codex_version: str | None = None
    codex_sha256: str | None = None
    reasoning_effort: str = "medium"
    timeout_seconds: int = 900
    pin: HarveyLabPin = field(default_factory=harvey_lab_v1_1_pin)


@dataclass(frozen=True, slots=True)
class CommunitySubscriptionRuntime:
    """Distinct solver and judge services using separate local logins."""

    adapter: ClaudeCodeCliAdapter | CodexCliAdapter
    judge_service: LocalCliExecutionService
    evaluator_runner: ProductionHarveyLabEvaluatorRunner
    judge_boundary: HarveyLabJudgeRequestBoundary
    evaluator_provenance_provider: EvaluatorProvenanceProvider


def _with_community_timeout(
    manifest: LocalCliAdapterManifest, timeout_seconds: int
) -> LocalCliAdapterManifest:
    """Bind the selected local limit without changing shared adapter defaults."""

    record = manifest.to_record()
    record["timeout_retry"] = replace(
        manifest.timeout_retry, timeout_seconds=timeout_seconds
    ).to_record()
    record["capability_digest"] = capability_digest_for(record)
    return LocalCliAdapterManifest.from_record(record)


def build_community_subscription_runtime(
    request: CommunitySubscriptionOperatorRequest,
) -> CommunitySubscriptionRuntime:
    """Build the local subscription solver and separate native CLI judge."""

    executable_pin = ExecutableIdentityPin(
        basename="claude",
        version=request.claude_version,
        sha256=request.claude_sha256,
        distribution_kind="standalone-cli",
        required_flags=(
            "--add-dir",
            "--json-schema",
            "--no-session-persistence",
            "--safe-mode",
            "--setting-sources",
            "--strict-mcp-config",
            "--tools",
        ),
    )
    manifest = _with_community_timeout(
        claude_code_local_manifest(), request.timeout_seconds
    )
    bound = bind_adapter_auth_profile(manifest, CONTRIBUTOR_SUBSCRIPTION)
    if request.harness not in {"claude-code", "codex"}:
        raise CommunitySubscriptionOperatorError("unsupported community solver harness")
    solver_executable = "codex" if request.harness == "codex" else "claude"
    solver_pin = executable_pin
    solver_manifest = manifest
    if request.harness == "codex":
        if not request.codex_version or not request.codex_sha256:
            raise CommunitySubscriptionOperatorError(
                "Codex requires explicit --codex-version and --codex-sha256"
            )
        solver_manifest = _with_community_timeout(
            load_codex_local_cli_manifest(), request.timeout_seconds
        )
        solver_pin = ExecutableIdentityPin(
            basename="codex",
            version=request.codex_version,
            sha256=request.codex_sha256,
            distribution_kind="standalone-cli",
            required_flags=(
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--strict-config",
            ),
        )
    solver_bound = bind_adapter_auth_profile(solver_manifest, CONTRIBUTOR_SUBSCRIPTION)
    parent_env = dict(os.environ)
    parent_env["PATH"] = (
        f"{request.evaluator_bin_dir}{os.pathsep}{parent_env.get('PATH', '/usr/bin')}"
    )
    solver_config, judge_config = validate_role_config_separation(
        request.solver_config_dir,
        request.judge_config_dir,
        solver_executable=solver_executable,
        codex_pin=solver_pin if solver_executable == "codex" else None,
        codex_search_path=parent_env["PATH"],
        forbidden_paths=(
            request.source_root,
            request.projection_root,
            request.evaluator_private_root,
            request.run_root,
            request.evaluator_bin_dir,
        ),
    )
    solver_presence = NativeCliSubscriptionPresence(
        solver_executable,
        config_root=solver_config,
        role="solver",
        executable_pin=solver_pin,
    )
    judge_presence = NativeCliSubscriptionPresence(
        "claude", config_root=judge_config, role="judge"
    )
    solver_service = contained_execution_service(
        solver_bound,
        parent_env=parent_env,
        adapter_id=f"{request.harness}-community-subscription-solver",
        display_name=f"{request.harness} community subscription solver",
        executable_pin=solver_pin,
        subscription_presence=solver_presence,
        filesystem_read_paths=(request.projection_root,),
        filesystem_write_paths=(request.run_root / "solver-workspace",),
        run_in_working_directory=True,
    )
    judge_service = contained_execution_service(
        bound,
        parent_env=parent_env,
        adapter_id="claude-code-community-subscription-judge",
        display_name="Claude Code community subscription judge",
        executable_pin=executable_pin,
        subscription_presence=judge_presence,
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
        adapter=(
            CodexCliAdapter(
                execution_service=solver_service,
                local_cli_manifest=solver_manifest,
                auth_profile=CONTRIBUTOR_SUBSCRIPTION,
            )
            if request.harness == "codex"
            else ClaudeCodeCliAdapter(
                execution_service=solver_service,
                local_manifest=solver_manifest,
                auth_profile=CONTRIBUTOR_SUBSCRIPTION,
            )
        ),
        judge_service=judge_service,
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance,
    )


def preflight_community_subscription_runtime(
    request: CommunitySubscriptionOperatorRequest,
    runtime: CommunitySubscriptionRuntime,
) -> CommunitySubscriptionRuntime:
    """Check vendor capabilities, then retain byte identity for actual launches.

    Native vendor help/version is the capability interface. The contained
    executor's generic JSON identity probe is a different protocol; after
    preflight, its launch pins retain version/digest without probe framing.
    """

    for service in (runtime.adapter.execution_service, runtime.judge_service):
        if not isinstance(service, LocalCliExecutionService):
            raise CommunitySubscriptionOperatorError("native runtime must be contained")
        pin = service.executable_pin
        if pin is None:
            raise CommunitySubscriptionOperatorError(
                "community subscription runtime has no executable pin"
            )
        try:
            with tempfile.TemporaryDirectory(
                prefix="lfb-community-native-preflight-"
            ) as scratch:
                preflight_native_cli(
                    pin,
                    scratch_root=Path(scratch),
                    parent_env=service.parent_env,
                )
        except (LocalCliIdentityError, LocalCliProbeError) as exc:
            raise CommunitySubscriptionOperatorError(
                f"native {pin.basename} capability preflight failed before execution"
            ) from exc
    solver_service = runtime.adapter.execution_service
    assert isinstance(solver_service, LocalCliExecutionService)
    assert solver_service.executable_pin is not None
    assert runtime.judge_service.executable_pin is not None
    solver_service = replace(
        solver_service,
        executable_pin=replace(solver_service.executable_pin, required_flags=()),
    )
    judge_service = replace(
        runtime.judge_service,
        executable_pin=replace(runtime.judge_service.executable_pin, required_flags=()),
    )
    runner, boundary, provenance = build_subscription_judge(
        service=judge_service,
        model=request.judge_model,
        run_root=request.run_root,
        timeout_seconds=request.timeout_seconds,
        pin=request.pin,
        claude_sha256=request.claude_sha256,
    )
    return replace(
        runtime,
        adapter=replace(runtime.adapter, execution_service=solver_service),
        judge_service=judge_service,
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance,
    )


def run_community_subscription_harvey_lab(
    request: CommunitySubscriptionOperatorRequest,
    *,
    runtime: CommunitySubscriptionRuntime | None = None,
) -> ClaudeCodeHarveyLabMeasurementResult | CodexCliHarveyLabMeasurementResult:
    """Run the prepared community arm without API keys or hosted authority."""

    if request.run_root.exists() or request.run_root.is_symlink():
        raise CommunitySubscriptionOperatorError(
            "--run-dir must be a fresh, absent path"
        )
    # Native --cd and process cwd must use the same absolute workspace.
    request = replace(request, run_root=request.run_root.resolve())
    selected = runtime or build_community_subscription_runtime(request)
    if runtime is None:
        selected = preflight_community_subscription_runtime(request, selected)
    request.run_root.mkdir(parents=True)
    if isinstance(selected.adapter, CodexCliAdapter):
        result = run_codex_cli_clean_native_harvey_lab(
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
            reasoning_effort=request.reasoning_effort,
            timeout_seconds=request.timeout_seconds,
            judge_request_boundary=selected.judge_boundary,
            evaluator_runner=selected.evaluator_runner,
            evaluator_provenance_provider=selected.evaluator_provenance_provider,
            require_production_provenance=True,
            evaluator_execution_service=selected.judge_service,
            use_prepared_projection=True,
        )
        if not isinstance(result, CodexCliHarveyLabMeasurementResult):
            raise CommunitySubscriptionOperatorError(
                "community LAB operator unexpectedly produced an issuer result"
            )
        return result
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
    "preflight_community_subscription_runtime",
    "run_community_subscription_harvey_lab",
]

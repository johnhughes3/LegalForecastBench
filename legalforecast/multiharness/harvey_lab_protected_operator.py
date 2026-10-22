"""Protected standalone operator runtime for the Claude Code Harvey LAB arm."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from legalforecast.multiharness.auth_profiles import FIXTURE_NONE, PUBLISHED_API_KEY
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
from legalforecast.multiharness.claude_code_container import (
    CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
    build_claude_code_container_adapter,
)
from legalforecast.multiharness.claude_code_container_runtime import (
    MODEL_GATEWAY_HOST,
    MODEL_GATEWAY_PORT,
    OUTER_CONTAINER_ONLY_MODE,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    ClaudeCodeHarveyLabMeasurementResult,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    HARVEY_LAB_MAX_BILLABLE_ATTEMPTS,
    ProtectedPaidGatewayConfig,
    load_paid_gateway_config,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EvaluatorProvenanceProvider,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_paid_gateway_descriptor import (
    authenticate_harvey_lab_paid_inputs,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionHarveyLabEvaluatorRunner,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    harvey_lab_v1_1_pin,
)
from legalforecast.multiharness.harvey_lab_protected_spend import (
    ProtectedHarveyLabJudgeBoundary,
    registry_cost_microusd,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.protected_terminal_paid import (
    PROTECTED_ANTHROPIC_ENV,
    UPSTREAM_API_KEY_ENV,
    GitHubEnvironmentGatewayCredentialSource,
    ProtectedTerminalPaidError,
    build_dynamodb_spend_authority,
)
from legalforecast.multiharness.tier0_evaluator_wrapper import wrapper_source_sha256
from legalforecast.multiharness.tier0_production_factory import (
    EGRESS_POLICY,
    JUDGE_OUTPUT_SCHEMA,
    JUDGE_PROMPT_FRAMING_TOKEN_RESERVE,
    JUDGE_SETTINGS,
    JUDGE_SYSTEM_PROMPT,
    RESOURCE_POLICY,
    RUNTIME_POLICY,
    TOKEN_ACCOUNTING_POLICY,
    AnthropicMessagesJudgeAdapter,
    JudgeAttemptWriter,
    anthropic_messages_transport,
    policy_digest,
    text_digest,
)
from legalforecast.multiharness.tier0_runner import Tier0EvaluatorConfiguration


class ProtectedHarveyLabOperatorError(RuntimeError):
    """The standalone protected LAB operator is not executable as configured."""


@dataclass(frozen=True, slots=True)
class ProtectedHarveyLabRuntime:
    """Complete solver/evaluator runtime assembled from one paid descriptor."""

    adapter: ClaudeCodeCliAdapter
    evaluator_service: LocalCliExecutionService
    evaluator_runner: ProductionHarveyLabEvaluatorRunner
    judge_boundary: HarveyLabJudgeRequestBoundary
    evaluator_provenance_provider: EvaluatorProvenanceProvider
    model: str
    ceiling_microusd: int


@dataclass(frozen=True, slots=True)
class ProtectedHarveyLabOperatorRequest:
    """Prepared paths and immutable runtime pins for one standalone run."""

    source_root: Path
    projection_root: Path
    evaluator_private_root: Path
    run_root: Path
    evaluator_bin_dir: Path
    paid_config_path: Path
    model_registry_path: Path
    solver_image_digest: str
    gateway_image_digest: str
    model_key: str
    timeout_seconds: int = 900
    pin: HarveyLabPin = field(default_factory=harvey_lab_v1_1_pin)


def build_protected_harvey_lab_runtime(
    request: ProtectedHarveyLabOperatorRequest,
) -> ProtectedHarveyLabRuntime:
    """Build the real protected solver and per-criterion judge boundaries."""

    config = load_paid_gateway_config(
        request.paid_config_path,
        model_registry_path=request.model_registry_path,
        environment=os.environ,
    )
    if config.harness_id != CLAUDE_CODE_HARVEY_LAB_HARNESS_ID:
        raise ProtectedHarveyLabOperatorError(
            "paid descriptor is not bound to the Claude Code Harvey LAB harness"
        )
    if config.forecast_release_digest is not None:
        raise ProtectedHarveyLabOperatorError(
            "Harvey LAB cannot consume a forecast-release paid descriptor"
        )
    if config.model_key != request.model_key:
        raise ProtectedHarveyLabOperatorError(
            "operator model key does not match the paid descriptor"
        )
    _require_descriptor_inputs(config, request)
    ceiling_usd = Decimal(config.spend.ceiling_microusd) / Decimal(1_000_000)
    container = build_claude_code_container_adapter(
        image_digest=request.solver_image_digest,
        auth_profile=PUBLISHED_API_KEY,
        model_key=request.model_key,
        max_budget_usd=float(ceiling_usd),
        approval_reference=None,
        output_root=(request.run_root / "container-results").resolve(),
        timeout_seconds=request.timeout_seconds,
        case_count=1,
        execution_mode=OUTER_CONTAINER_ONLY_MODE,
        gateway_base_url=f"http://{MODEL_GATEWAY_HOST}:{MODEL_GATEWAY_PORT}",
        gateway_upstream_base_url=MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
        gateway_image_digest=request.gateway_image_digest,
        paid_config_path=request.paid_config_path.resolve(),
        model_registry_path=request.model_registry_path.resolve(),
        harness_id=CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
    )
    authority = build_dynamodb_spend_authority(
        config.spend,
        max_billable_attempts=HARVEY_LAB_MAX_BILLABLE_ATTEMPTS,
    )
    boundary = ProtectedHarveyLabJudgeBoundary(authority=authority, config=config)
    pricing_sha256 = "sha256:" + config.model_registry_sha256
    judge_adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=None,
        usage_pricing_sha256=pricing_sha256,
        cost_microusd=lambda input_tokens, output_tokens: registry_cost_microusd(
            config.registry_entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        secret_loader=_protected_judge_secret,
        transport=anthropic_messages_transport,
        max_prompt_bytes=max(
            1,
            config.registry_entry.context_limit - JUDGE_PROMPT_FRAMING_TOKEN_RESERVE,
        ),
        requested_model=config.registry_entry.model_id,
        before_transport=lambda call: boundary.mark_transport_started(call.request),
    )
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=judge_adapter,
        attempt_writer=JudgeAttemptWriter(request.run_root / "judge-attempts"),
        max_attempts=HARVEY_LAB_MAX_BILLABLE_ATTEMPTS,
        expected_judge_identity=config.registry_entry.model_id,
        evaluator_executable_version="harvey-lab-eval@" + wrapper_source_sha256(),
    )
    evaluator_env = {
        "PATH": f"{request.evaluator_bin_dir}{os.pathsep}/usr/bin",
        "LC_CTYPE": "C.UTF-8",
    }
    evaluator_service = LocalCliExecutionService(
        auth_profile=FIXTURE_NONE,
        parent_env=evaluator_env,
    )
    provenance = _evaluator_configuration(
        request.pin,
        model_id=config.registry_entry.model_id,
        pricing_sha256=pricing_sha256,
    )
    return ProtectedHarveyLabRuntime(
        adapter=container.delegate,
        evaluator_service=evaluator_service,
        evaluator_runner=runner,
        judge_boundary=boundary,
        evaluator_provenance_provider=provenance.provenance_for_execution,
        model=config.registry_entry.model_id,
        ceiling_microusd=config.spend.ceiling_microusd,
    )


def run_protected_harvey_lab_operator(
    request: ProtectedHarveyLabOperatorRequest,
    *,
    runtime: ProtectedHarveyLabRuntime | None = None,
) -> ClaudeCodeHarveyLabMeasurementResult:
    """Consume prepared inputs and run the production standalone join."""

    if request.run_root.exists() or request.run_root.is_symlink():
        raise ProtectedHarveyLabOperatorError("--run-dir must be a fresh, absent path")
    selected = runtime or build_protected_harvey_lab_runtime(request)
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
        model=selected.model,
        timeout_seconds=request.timeout_seconds,
        max_budget_usd=format(
            Decimal(selected.ceiling_microusd) / Decimal(1_000_000),
            "f",
        ),
        judge_request_boundary=selected.judge_boundary,
        evaluator_runner=selected.evaluator_runner,
        evaluator_provenance_provider=selected.evaluator_provenance_provider,
        require_production_provenance=True,
        evaluator_execution_service=selected.evaluator_service,
        container_workspace=True,
        use_prepared_projection=True,
    )
    if not isinstance(result, ClaudeCodeHarveyLabMeasurementResult):
        raise ProtectedHarveyLabOperatorError(
            "standalone LAB operator unexpectedly produced an issuer result"
        )
    if result.execution_mode != "production" or result.baseline_score_value is None:
        raise ProtectedHarveyLabOperatorError(
            "standalone LAB operator did not produce a production measurement"
        )
    return result


def _protected_judge_secret(_environment: str, _path: str, _name: str) -> str:
    values = GitHubEnvironmentGatewayCredentialSource().upstream_environment()
    return values[UPSTREAM_API_KEY_ENV]


def _require_descriptor_inputs(
    config: ProtectedPaidGatewayConfig,
    request: ProtectedHarveyLabOperatorRequest,
) -> None:
    """Authenticate the prepared LAB roots before authority or credential use."""

    try:
        identity = authenticate_harvey_lab_paid_inputs(
            source_root=request.source_root,
            projection_root=request.projection_root,
            evaluator_private_root=request.evaluator_private_root,
            pin=request.pin,
        )
    except (OSError, ProtectedTerminalPaidError, ValueError) as exc:
        raise ProtectedHarveyLabOperatorError(
            f"prepared Harvey LAB inputs are invalid: {exc}"
        ) from exc
    observed = (
        identity.projection_manifest_sha256,
        identity.private_material_sha256,
        identity.task_id,
        identity.source_commit,
        identity.source_tree,
    )
    expected = (
        config.harvey_lab_projection_manifest_sha256,
        config.harvey_lab_private_material_sha256,
        config.harvey_lab_task_id,
        config.harvey_lab_source_commit,
        config.harvey_lab_source_tree,
    )
    if observed != expected:
        raise ProtectedHarveyLabOperatorError(
            "prepared Harvey LAB inputs do not match the paid descriptor"
        )


def _evaluator_configuration(
    pin: HarveyLabPin,
    *,
    model_id: str,
    pricing_sha256: str,
) -> Tier0EvaluatorConfiguration:
    wrapper_sha256 = wrapper_source_sha256()
    judge_settings, runtime_policy = _protected_evaluator_policy_inputs(model_id)
    return Tier0EvaluatorConfiguration(
        evaluator_repository=pin.repository,
        evaluator_commit=pin.commit,
        evaluator_tree=pin.tree,
        evaluator_file_manifest_sha256=wrapper_sha256,
        evaluator_image_digest=wrapper_sha256,
        judge_requested_identity=f"anthropic/{model_id}",
        judge_settings_sha256=policy_digest(judge_settings),
        judge_prompt_sha256=text_digest(JUDGE_SYSTEM_PROMPT),
        judge_output_schema_sha256=policy_digest(JUDGE_OUTPUT_SCHEMA),
        runtime_policy_sha256=policy_digest(runtime_policy),
        egress_policy_sha256=policy_digest(EGRESS_POLICY),
        resource_policy_sha256=policy_digest(RESOURCE_POLICY),
        token_accounting_policy_sha256=policy_digest(TOKEN_ACCOUNTING_POLICY),
        cost_basis="estimated_from_pricing_snapshot",
        pricing_snapshot_sha256=pricing_sha256,
        is_fixture=False,
    )


def _protected_evaluator_policy_inputs(
    model_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the actual protected judge request and credential policies."""

    judge_settings = {**JUDGE_SETTINGS, "model": model_id}
    runtime_policy = {
        **RUNTIME_POLICY,
        "credential_backend": "github-environment",
        "credential_environment": "legalforecastbench-official-eval",
        "credential_path": "secrets",
        "credential_name": PROTECTED_ANTHROPIC_ENV,
    }
    return judge_settings, runtime_policy


__all__ = [
    "ProtectedHarveyLabJudgeBoundary",
    "ProtectedHarveyLabOperatorError",
    "ProtectedHarveyLabOperatorRequest",
    "ProtectedHarveyLabRuntime",
    "build_protected_harvey_lab_runtime",
    "run_protected_harvey_lab_operator",
]

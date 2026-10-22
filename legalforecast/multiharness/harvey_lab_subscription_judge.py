"""Native Claude subscription judge for the community Harvey LAB route."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.claude_code import (
    build_claude_invocation_plan,
    claude_code_local_manifest,
)
from legalforecast.multiharness.claude_code_stream import served_model, usage
from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationTokenUsage,
    TokenCount,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    EvaluatorProvenanceProvider,
    HarveyLabEvaluatorProvenance,
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    JudgeDeliverable,
    ProductionEvaluatorRunnerError,
    ProductionHarveyLabEvaluatorRunner,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.harvey_lab_projection import HarveyLabPin
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import UsageObservation
from legalforecast.multiharness.tier0_evaluator_wrapper import wrapper_source_sha256

_JUDGE_SCHEMA: Mapping[str, object] = {
    "additionalProperties": False,
    "properties": {"verdict": {"enum": ["pass", "fail"], "type": "string"}},
    "required": ["verdict"],
    "type": "object",
}
_JUDGE_PROMPT = (
    "Grade one binary criterion for a legal drafting task. Use the candidate "
    "deliverable and private criterion below. Return only the required JSON verdict."
)
_RUNTIME_POLICY: Mapping[str, object] = {
    "auth": CONTRIBUTOR_SUBSCRIPTION,
    "runtime": "vendor_native_claude_cli",
    "solver_judge_isolation": "separate_execution_services",
    "provider_api_key": False,
}
_EGRESS_POLICY: Mapping[str, object] = {"runtime": "vendor_managed_subscription_egress"}
_RESOURCE_POLICY: Mapping[str, object] = {
    "judge_calls_per_criterion": 1,
    "parallelism": 1,
}
_ACCOUNTING_POLICY: Mapping[str, object] = {
    "cost": "subscription_unallocable",
    "tokens": "provider_response_when_reported",
}
_SAFE_ID = re.compile(r"[^a-z0-9._+-]+")


class SubscriptionJudgeError(RuntimeError):
    """A native subscription judge invocation or record was invalid."""


class SubscriptionJudgeBoundary(HarveyLabJudgeRequestBoundary):
    """Require truthful subscription accounting without a paid-call authority."""

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        return request

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        if reservation is not request:
            raise SubscriptionJudgeError(
                "subscription judge boundary lost criterion identity"
            )
        if (
            not isinstance(observation, UsageObservation)
            or observation.basis != "subscription_unallocable"
        ):
            raise SubscriptionJudgeError(
                "subscription judge cost must remain unallocable"
            )


class SubscriptionProvenanceProvider:
    """Build evaluator provenance from actual native CLI execution evidence."""

    def __init__(
        self,
        *,
        pin: HarveyLabPin,
        requested_model: str,
        claude_sha256: str,
    ) -> None:
        self._pin = pin
        self._requested_model = requested_model
        self._claude_sha256 = claude_sha256

    def __call__(self, execution: ExecutionReceipt) -> HarveyLabEvaluatorProvenance:
        if execution.status != "succeeded" or not execution.served_model:
            raise SubscriptionJudgeError(
                "subscription evaluator did not record judge identity"
            )
        input_tokens = _token_count(execution.usage.get("input_tokens"))
        output_tokens = _token_count(execution.usage.get("output_tokens"))
        total = (
            TokenCount(input_tokens.value + output_tokens.value, None)
            if input_tokens.value is not None and output_tokens.value is not None
            else TokenCount(None, "not_reported")
        )
        return HarveyLabEvaluatorProvenance(
            evaluator_repository=self._pin.repository,
            evaluator_commit=self._pin.commit,
            evaluator_tree=self._pin.tree,
            evaluator_file_manifest_sha256=wrapper_source_sha256(),
            evaluator_image_digest="sha256:" + self._claude_sha256,
            judge_requested_identity=_requested_identity(self._requested_model),
            judge_resolved_identity=execution.served_model,
            judge_settings_sha256=_digest(
                {"model_alias": self._requested_model, "tools": []}
            ),
            judge_prompt_sha256=_text_digest(_JUDGE_PROMPT),
            judge_output_schema_sha256=_digest(_JUDGE_SCHEMA),
            runtime_policy_sha256=_digest(_RUNTIME_POLICY),
            egress_policy_sha256=_digest(_EGRESS_POLICY),
            resource_policy_sha256=_digest(_RESOURCE_POLICY),
            token_accounting_policy_sha256=_digest(_ACCOUNTING_POLICY),
            token_usage=EvaluationTokenUsage(
                source="provider_response",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=TokenCount(None, "not_reported"),
                cache_write_tokens=TokenCount(None, "not_reported"),
                reasoning_tokens=TokenCount(None, "not_reported"),
                total_tokens=total,
            ),
            cost=CostMeasurement(
                amount_microusd=None,
                currency=None,
                basis="subscription_unallocable",
                pricing_snapshot_sha256=None,
                unknown_reason="flat_subscription_has_no_per_call_allocation",
            ),
        )


def build_subscription_judge(
    *,
    service: LocalCliExecutionService,
    model: str,
    run_root: Path,
    timeout_seconds: int,
    pin: HarveyLabPin,
    claude_sha256: str,
) -> tuple[
    ProductionHarveyLabEvaluatorRunner,
    HarveyLabJudgeRequestBoundary,
    EvaluatorProvenanceProvider,
]:
    """Return the one-shot native judge, boundary, and provenance provider."""

    judge = _ClaudeSubscriptionJudge(
        service=service,
        model=model,
        run_root=run_root,
        timeout_seconds=timeout_seconds,
    )
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=judge,
        attempt_writer=_attempt_writer(run_root / "judge-attempts"),
        max_attempts=1,
        allow_subscription_unallocable=True,
        evaluator_executable_version="harvey-lab-eval@" + wrapper_source_sha256(),
    )
    provenance = SubscriptionProvenanceProvider(
        pin=pin,
        requested_model=model,
        claude_sha256=claude_sha256,
    )
    return runner, SubscriptionJudgeBoundary(), provenance


def observed_model_from_receipt(receipt: ExecutionReceipt) -> str | None:
    """Return the actual model named by Claude, without guessing from an alias."""

    return served_model(_json_object(receipt.stdout))


class _ClaudeSubscriptionJudge:
    def __init__(
        self,
        *,
        service: LocalCliExecutionService,
        model: str,
        run_root: Path,
        timeout_seconds: int,
    ) -> None:
        self._service = service
        self._model = model
        self._run_root = run_root
        self._timeout_seconds = timeout_seconds
        self._manifest = claude_code_local_manifest()

    def __call__(self, call: ProductionJudgeCall) -> ProductionJudgeResponse:
        working = (
            self._run_root
            / "judge-work"
            / f"criterion-{call.request.ordinal:03d}"
            / f"attempt-{call.request.attempt_index:02d}"
        )
        if working.exists() or working.is_symlink():
            raise SubscriptionJudgeError("judge working directory must be fresh")
        working.mkdir(parents=True)
        plan = build_claude_invocation_plan(
            prompt=_judge_prompt(call.criterion, call.deliverable),
            model=self._model,
            required_unit_ids=(),
            workspace=working,
            output_schema_path=working / "judge-schema.json",
            manifest=self._manifest,
            auth_profile=CONTRIBUTOR_SUBSCRIPTION,
            json_schema=_JUDGE_SCHEMA,
            allowed_tools=(),
        )
        spec = RunSpec(
            spec_id=(
                f"harvey-lab-judge-{call.request.ordinal:03d}-"
                f"{call.request.attempt_index:02d}"
            ),
            argv=plan.argv,
            working_directory=working,
            environment={},
            timeout_seconds=self._timeout_seconds,
            json_schema=plan.json_schema,
            output_format=plan.output_format,
        )
        receipt = self._service.execute(spec)
        if receipt.status != "succeeded" or receipt.returncode not in {0, None}:
            raise SubscriptionJudgeError(
                "native Claude subscription judge invocation failed"
            )
        envelope = _json_object(receipt.stdout)
        verdict = _judge_verdict(envelope)
        if verdict is None:
            raise SubscriptionJudgeError(
                "native Claude subscription judge returned no valid verdict"
            )
        token_usage = usage(envelope)
        return ProductionJudgeResponse(
            verdict=verdict,
            judge_resolved_identity=_resolved_identity(
                served_model(envelope), requested_alias=self._model
            ),
            usage=UsageObservation(
                basis="subscription_unallocable",
                input_tokens=token_usage.get("input_tokens"),
                output_tokens=token_usage.get("output_tokens"),
                unknown_reason="flat_subscription_has_no_per_call_allocation",
            ),
            raw_response=receipt.stdout.encode("utf-8"),
        )


def _judge_prompt(
    criterion: Mapping[str, object], deliverable: JudgeDeliverable
) -> str:
    match = criterion.get("match_criteria")
    if not isinstance(match, str) or not match.strip():
        raise SubscriptionJudgeError("judge criterion is missing private match text")
    title = criterion.get("title")
    heading = title if isinstance(title, str) and title.strip() else "criterion"
    return (
        f"{_JUDGE_PROMPT}\n\nCandidate deliverables "
        f"({', '.join(deliverable.artifact_paths)}):\n<deliverable>\n"
        f"{deliverable.text}\n</deliverable>\n\nCriterion: {heading}\n\n"
        f"Requirement:\n{match}"
    )


def _attempt_writer(root: Path):
    def write(call: ProductionJudgeCall, response: ProductionJudgeResponse) -> None:
        directory = root / f"criterion-{call.request.ordinal:03d}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"attempt-{call.request.attempt_index:02d}.json"
        record = {
            "criterion_id": call.request.criterion_id,
            "deliverable_sha256": call.deliverable.sha256,
            "judge_resolved_identity": response.judge_resolved_identity,
            "usage": response.usage.to_record(),
            "verdict": response.verdict,
        }
        try:
            with path.open("xb") as handle:
                handle.write(_canonical(record) + b"\n")
            raw_path = directory / f"attempt-{call.request.attempt_index:02d}.raw"
            with raw_path.open("xb") as handle:
                handle.write(response.raw_response)
        except OSError as exc:
            raise ProductionEvaluatorRunnerError(
                "judge attempt retention failed"
            ) from exc

    return write


def _judge_verdict(envelope: dict[str, object] | None) -> str | None:
    if envelope is None:
        return None
    value = envelope.get("structured_output", envelope.get("result"))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None
    verdict = cast(dict[str, object], value).get("verdict")
    return verdict if isinstance(verdict, str) and verdict in {"pass", "fail"} else None


def _json_object(text: str) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _requested_identity(alias: str) -> str:
    return "claude-cli/" + _safe_identity_component(alias)


def _resolved_identity(observed: str | None, *, requested_alias: str) -> str:
    if observed:
        return "anthropic/" + _safe_identity_component(observed)
    return "claude-cli/unreported@requested-" + _safe_identity_component(
        requested_alias
    )


def _safe_identity_component(value: str) -> str:
    normalized = _SAFE_ID.sub("-", value.strip().lower()).strip("-.")
    if not normalized:
        raise SubscriptionJudgeError("model identity is not public-safe")
    return normalized[:120]


def _token_count(value: object) -> TokenCount:
    return (
        TokenCount(value, None)
        if type(value) is int and value >= 0
        else TokenCount(None, "not_reported")
    )


def _digest(record: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(record)).hexdigest()


def _text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


__all__ = [
    "SubscriptionJudgeBoundary",
    "SubscriptionJudgeError",
    "SubscriptionProvenanceProvider",
    "build_subscription_judge",
    "observed_model_from_receipt",
]

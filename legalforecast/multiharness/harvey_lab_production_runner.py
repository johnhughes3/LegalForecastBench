"""Injected production Harvey LAB judge runner.

The pinned LAB evaluator makes one provider request per criterion, but its
upstream command exposes only an aggregate CLI.  Calling that command once
after reserving an aggregate amount cannot prove per-criterion spend.  This
module therefore defines the narrow seam used by a reviewed production
provider adapter: the adapter supplies one real provider response at a time,
while this runner owns the reserve/request/settle ordering and the final
score serialization.

No credential lookup or provider SDK is allowed here.  The injected provider
callback is the authority for those concerns and must return the provider's
actual token and cost observation.  A callback that is absent, returns
fixture identities, or omits accounting is not a production runner.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from legalforecast.multiharness.deliverable_text import (
    DeliverableTextError,
    docx_visible_text,
)
from legalforecast.multiharness.deliverables import artifact_tree_sha256
from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
    harvey_lab_private_material_snapshot,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import PricingSnapshot, UsageObservation

# Compatibility export for the retained issue-196 task. Runtime cardinality is
# now authenticated from the selected task rather than fixed to this value.
HARVEY_LAB_JUDGE_CRITERION_COUNT = 23


class ProductionEvaluatorRunnerError(ValueError):
    """Raised when the injected production evaluator seam is incomplete."""


@dataclass(frozen=True, slots=True)
class JudgeDeliverable:
    """The authenticated candidate work product shown to the judge.

    ``text`` is what actually reaches the provider; ``sha256`` is the sealed
    tree digest, so a retained attempt names every artifact used for a verdict.
    """

    artifact_paths: tuple[str, ...]
    text: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.artifact_paths or any(
            not path.strip() for path in self.artifact_paths
        ):
            raise ProductionEvaluatorRunnerError(
                "judge deliverable must name its artifacts"
            )
        if not self.text.strip():
            raise ProductionEvaluatorRunnerError(
                "judge deliverable text must not be blank"
            )
        if not self.sha256.startswith("sha256:"):
            raise ProductionEvaluatorRunnerError(
                "judge deliverable digest must use the sha256:<hex> form"
            )


@dataclass(frozen=True, slots=True)
class ProductionJudgeCall:
    """The private, criterion-scoped input supplied to the provider adapter."""

    request: HarveyLabJudgeRequest
    run_spec: RunSpec
    criterion: Mapping[str, object]
    deliverable: JudgeDeliverable


@dataclass(frozen=True, slots=True)
class ProductionJudgeResponse:
    """One provider response with all accounting needed for settlement."""

    verdict: str | None
    judge_resolved_identity: str
    usage: UsageObservation
    raw_response: bytes
    retryable: bool = False

    def __post_init__(self) -> None:
        if self.verdict not in {None, "pass", "fail"}:
            raise ProductionEvaluatorRunnerError(
                "production judge verdict must be pass, fail, or null"
            )
        if not self.judge_resolved_identity.strip():
            raise ProductionEvaluatorRunnerError(
                "production judge response must identify the resolved model"
            )
        if self.judge_resolved_identity == "fixture/stub@local":
            raise ProductionEvaluatorRunnerError(
                "fixture judge identity cannot authorize a production response"
            )
        if type(self.raw_response) is not bytes or not self.raw_response:
            raise ProductionEvaluatorRunnerError(
                "production judge response must retain non-empty provider bytes"
            )
        if type(self.retryable) is not bool:
            raise ProductionEvaluatorRunnerError("retryable must be a boolean")
        if self.retryable and self.verdict is not None:
            raise ProductionEvaluatorRunnerError(
                "a retryable judge response cannot contain a final verdict"
            )
        if self.usage.basis in {"unknown", "subscription_unallocable"}:
            raise ProductionEvaluatorRunnerError(
                "production judge response must carry allocable usage"
            )


ProviderJudgeCall = Callable[[ProductionJudgeCall], ProductionJudgeResponse]
JudgeAttemptWriter = Callable[[ProductionJudgeCall, ProductionJudgeResponse], None]


class ProductionHarveyLabEvaluatorRunner:
    """Run one real, criterion-scoped provider request at a time.

    ``provider_call`` is intentionally injected.  It is the reviewed runtime
    adapter that owns credentials and the provider SDK; it must not be a
    fixture callback in a paid run.  ``attempt_writer`` is mandatory so every
    response, including retry attempts, can be retained in the private archive.
    """

    def __init__(
        self,
        *,
        provider_call: ProviderJudgeCall,
        attempt_writer: JudgeAttemptWriter,
        pricing_snapshot: PricingSnapshot | None = None,
        pricing_provider: str | None = None,
        pricing_model: str | None = None,
        max_attempts: int = 3,
        expected_judge_identity: str | None = None,
        evaluator_executable_version: str = "production",
    ) -> None:
        if not callable(provider_call):
            raise ProductionEvaluatorRunnerError(
                "production evaluator requires an injected provider adapter"
            )
        if not callable(attempt_writer):
            raise ProductionEvaluatorRunnerError(
                "production evaluator requires a private attempt-retention sink"
            )
        if type(max_attempts) is not int or max_attempts <= 0:
            raise ProductionEvaluatorRunnerError(
                "production evaluator max_attempts must be positive"
            )
        if expected_judge_identity is not None and not expected_judge_identity.strip():
            raise ProductionEvaluatorRunnerError(
                "expected judge identity must not be blank"
            )
        if (pricing_provider is None) != (pricing_model is None):
            raise ProductionEvaluatorRunnerError(
                "pricing provider and model must be supplied together"
            )
        if pricing_snapshot is not None and (
            pricing_provider is None or pricing_model is None
        ):
            raise ProductionEvaluatorRunnerError(
                "a pricing snapshot requires its provider and model identity"
            )
        if not evaluator_executable_version.strip():
            raise ProductionEvaluatorRunnerError(
                "evaluator executable version must not be blank"
            )
        self._provider_call = provider_call
        self._attempt_writer = attempt_writer
        self._pricing_snapshot = pricing_snapshot
        self._pricing_provider = pricing_provider
        self._pricing_model = pricing_model
        self._max_attempts = max_attempts
        self._expected_judge_identity = expected_judge_identity
        self._evaluator_executable_version = evaluator_executable_version

    def __call__(
        self,
        service: LocalCliExecutionService,
        spec: RunSpec,
        boundary: HarveyLabJudgeRequestBoundary,
    ) -> ExecutionReceipt:
        """Execute all criterion calls through the injected provider seam.

        ``service`` is deliberately unused: invoking the aggregate LAB CLI
        here would create an unaccounted provider call.  The provider callback
        is the actual request boundary for each criterion.
        """

        del service
        if not callable(getattr(boundary, "before_judge_call", None)) or not callable(
            getattr(boundary, "after_judge_call", None)
        ):
            raise ProductionEvaluatorRunnerError(
                "production evaluator requires a judge request boundary"
            )
        criteria = _authenticated_criteria(spec)
        # Resolved before the loop: a deliverable that cannot be authenticated
        # must refuse the run before any reservation, credential fetch, or
        # billable request, not after the first criterion has been paid for.
        deliverable = _authenticated_deliverable(spec)
        started = time.monotonic_ns()
        final_responses: list[ProductionJudgeResponse] = []
        all_responses: list[ProductionJudgeResponse] = []
        resolved_identity: str | None = None
        for ordinal, criterion in enumerate(criteria, start=1):
            criterion_id = str(criterion["id"])
            final: ProductionJudgeResponse | None = None
            for attempt_index in range(self._max_attempts):
                request = HarveyLabJudgeRequest(
                    ordinal=ordinal,
                    criterion_id=criterion_id,
                    attempt_index=attempt_index,
                )
                reservation = boundary.before_judge_call(request)
                response = self._provider_call(
                    ProductionJudgeCall(
                        request=request,
                        run_spec=spec,
                        criterion=criterion,
                        deliverable=deliverable,
                    )
                )
                if type(response) is not ProductionJudgeResponse:
                    raise ProductionEvaluatorRunnerError(
                        "provider adapter returned an invalid judge response"
                    )
                # Retain the billed response before settlement removes the
                # reservation. If retention fails, the outer boundary can
                # still terminalize the outstanding reservation fail-closed.
                self._attempt_writer(
                    ProductionJudgeCall(
                        request=request,
                        run_spec=spec,
                        criterion=criterion,
                        deliverable=deliverable,
                    ),
                    response,
                )
                observation = response.usage
                boundary.after_judge_call(request, reservation, observation)
                all_responses.append(response)
                if resolved_identity is None:
                    resolved_identity = response.judge_resolved_identity
                elif resolved_identity != response.judge_resolved_identity:
                    raise ProductionEvaluatorRunnerError(
                        "production judge resolved identity changed between calls"
                    )
                if (
                    self._expected_judge_identity is not None
                    and response.judge_resolved_identity
                    != self._expected_judge_identity
                ):
                    raise ProductionEvaluatorRunnerError(
                        "production judge resolved identity differs from the "
                        "pinned model"
                    )
                if not response.retryable:
                    final = response
                    break
            if final is None or final.verdict is None:
                raise ProductionEvaluatorRunnerError(
                    f"criterion {criterion_id} exhausted without a final verdict"
                )
            final_responses.append(final)

        if len(final_responses) != len(criteria):
            raise ProductionEvaluatorRunnerError(
                "production evaluator did not produce all criterion verdicts"
            )
        scores = _scores_record(final_responses)
        scores_path = _scores_path(spec)
        _write_new_json(scores_path, scores)
        stdout = _canonical_json(scores).decode("utf-8")
        usage = _aggregate_usage(all_responses)
        cost_microusd = _aggregate_cost_microusd(
            all_responses,
            pricing=self._pricing_snapshot,
            pricing_provider=self._pricing_provider,
            pricing_model=self._pricing_model,
        )
        ended = time.monotonic_ns()
        duration_ms = max(0, (ended - started) // 1_000_000)
        return ExecutionReceipt.from_transcript(
            spec,
            stdout=stdout,
            duration_ms=duration_ms,
            served_model=resolved_identity,
            executable_version=self._evaluator_executable_version,
            usage=usage,
            cost_usd=float(Decimal(cost_microusd) / Decimal(1_000_000)),
        )


def _scores_record(
    responses: Sequence[ProductionJudgeResponse],
) -> dict[str, object]:
    verdicts = [response.verdict for response in responses]
    if any(verdict not in {"pass", "fail"} for verdict in verdicts):
        raise ProductionEvaluatorRunnerError("all final judge responses need verdicts")
    passed = sum(verdict == "pass" for verdict in verdicts)
    return {
        "score": 1.0 if passed == len(verdicts) else 0.0,
        "n_passed": passed,
        "n_criteria": len(verdicts),
        "verdicts": list(verdicts),
        "entrypoint": "evaluation.run_eval.evaluate_run",
    }


def _evaluator_input_record(spec: RunSpec) -> Mapping[str, object]:
    try:
        record = json.loads(spec.stdin_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionEvaluatorRunnerError(
            "evaluator RunSpec stdin is not valid JSON"
        ) from exc
    if not isinstance(record, Mapping):
        raise ProductionEvaluatorRunnerError(
            "evaluator RunSpec stdin must be an object"
        )
    return cast(Mapping[str, object], record)


def _authenticated_criteria(spec: RunSpec) -> tuple[Mapping[str, object], ...]:
    record = _evaluator_input_record(spec)
    private_value = record.get("private_task_json_path")
    expected_digest = record.get("private_material_sha256")
    if not isinstance(private_value, str) or not private_value:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind private task material"
        )
    if not isinstance(expected_digest, str) or not expected_digest:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind the private material digest"
        )
    private_path = Path(private_value)
    if not private_path.is_absolute() or private_path.is_symlink():
        raise ProductionEvaluatorRunnerError(
            "private task material must be an absolute regular file"
        )
    try:
        actual_digest, private_files = harvey_lab_private_material_snapshot(
            private_path.parent
        )
        task = json.loads(private_files[private_path.name])
    except (KeyError, OSError, json.JSONDecodeError, ValueError) as exc:
        raise ProductionEvaluatorRunnerError(
            "private task material is not readable authenticated JSON"
        ) from exc
    if actual_digest != expected_digest:
        raise ProductionEvaluatorRunnerError(
            "private task material does not match the pinned digest"
        )
    if not isinstance(task, Mapping):
        raise ProductionEvaluatorRunnerError("private task material must be an object")
    typed_task = cast(Mapping[str, object], task)
    raw_criteria = typed_task.get("criteria")
    if not isinstance(raw_criteria, Sequence) or isinstance(raw_criteria, str | bytes):
        raise ProductionEvaluatorRunnerError(
            "private task material must contain a criteria array"
        )
    criterion_values = cast(Sequence[object], raw_criteria)
    if not criterion_values:
        raise ProductionEvaluatorRunnerError(
            "production evaluator requires at least one criterion record"
        )
    normalized: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for ordinal, criterion in enumerate(criterion_values, start=1):
        if not isinstance(criterion, Mapping):
            raise ProductionEvaluatorRunnerError(
                f"criterion {ordinal} must be an object"
            )
        criterion_record = cast(Mapping[str, object], criterion)
        criterion_id = criterion_record.get("id")
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise ProductionEvaluatorRunnerError(
                f"criterion {ordinal} must have a non-empty id"
            )
        if criterion_id in seen:
            raise ProductionEvaluatorRunnerError(
                "production evaluator criterion IDs must be unique"
            )
        seen.add(criterion_id)
        normalized.append(dict(criterion_record))
    return tuple(normalized)


def _authenticated_deliverable(spec: RunSpec) -> JudgeDeliverable:
    """Return the candidate deliverable text, bound to its sealed commitment.

    The evaluation-input record carries ``deliverable_tree_sha256``, the
    commitment produced when the output set was sealed. The evaluator can
    recompute it from the overlay bytes before any provider request, proving
    the text handed to the judge is the candidate's authenticated work product.
    """

    record = _evaluator_input_record(spec)
    paths_value = record.get("deliverable_paths")
    root_value = record.get("deliverable_root")
    expected_basenames = record.get("expected_deliverable_basenames")
    expected_tree = record.get("deliverable_tree_sha256")
    if not isinstance(paths_value, list) or not paths_value:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind deliverable paths"
        )
    if not isinstance(root_value, str) or not root_value:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind the deliverable root"
        )
    path_values = cast(list[object], paths_value)
    if not isinstance(expected_basenames, list) or any(
        not isinstance(item, str) for item in cast(list[object], expected_basenames)
    ):
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind expected deliverable basenames"
        )
    if not isinstance(expected_tree, str) or not expected_tree:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind the deliverable tree digest"
        )
    root = Path(root_value)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ProductionEvaluatorRunnerError(
            "candidate deliverable root must be an absolute real directory"
        )
    paths: list[Path] = []
    relative_paths: list[str] = []
    for path_value in path_values:
        if not isinstance(path_value, str) or not path_value:
            raise ProductionEvaluatorRunnerError(
                "evaluator input contains an invalid deliverable path"
            )
        path = Path(path_value)
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ProductionEvaluatorRunnerError(
                "candidate deliverable escapes the deliverable root"
            ) from exc
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ProductionEvaluatorRunnerError(
                "candidate deliverable must be an absolute regular file"
            )
        paths.append(path)
        relative_paths.append(relative)
    if relative_paths != sorted(relative_paths) or len(set(relative_paths)) != len(
        relative_paths
    ):
        raise ProductionEvaluatorRunnerError(
            "candidate deliverable paths must be sorted and unique"
        )
    if expected_basenames and relative_paths != expected_basenames:
        raise ProductionEvaluatorRunnerError(
            "candidate deliverables do not match the expected basenames"
        )
    payloads: dict[str, bytes] = {}
    try:
        for relative, path in zip(relative_paths, paths, strict=True):
            payloads[relative] = path.read_bytes()
        actual_tree = artifact_tree_sha256(payloads)
    except (OSError, ValueError) as exc:
        raise ProductionEvaluatorRunnerError(
            "candidate deliverable tree commitment is not recomputable"
        ) from exc
    if actual_tree != expected_tree:
        raise ProductionEvaluatorRunnerError(
            "candidate deliverable does not match the sealed tree digest"
        )
    sections: list[str] = []
    for relative in relative_paths:
        try:
            text = docx_visible_text(payloads[relative])
        except (OSError, DeliverableTextError) as exc:
            raise ProductionEvaluatorRunnerError(
                f"candidate deliverable text is not extractable: {relative}"
            ) from exc
        sections.append(f"## Agent Output: {relative}\n{text}")
    return JudgeDeliverable(
        artifact_paths=tuple(relative_paths),
        text="\n\n".join(sections),
        sha256=expected_tree,
    )


def _scores_path(spec: RunSpec) -> Path:
    record = _evaluator_input_record(spec)
    value = record.get("scores_output_path")
    if not isinstance(value, str) or not value:
        raise ProductionEvaluatorRunnerError(
            "evaluator input does not bind a scores output path"
        )
    path = Path(value)
    if not path.is_absolute() or path == path.parent:
        raise ProductionEvaluatorRunnerError(
            "evaluator scores output path must be an absolute file path"
        )
    return path


def _write_new_json(path: Path, record: Mapping[str, object]) -> None:
    payload = _canonical_json(record) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fd = os.open(path, flags, 0o444)
    except OSError as exc:
        raise ProductionEvaluatorRunnerError(
            "evaluator scores output must be a new regular file"
        ) from exc
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(payload)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)


def _aggregate_usage(
    responses: Sequence[ProductionJudgeResponse],
) -> dict[str, int]:
    input_tokens = [response.usage.input_tokens for response in responses]
    output_tokens = [response.usage.output_tokens for response in responses]
    if any(value is None for value in (*input_tokens, *output_tokens)):
        raise ProductionEvaluatorRunnerError(
            "production judge responses must report input and output tokens"
        )
    return {
        "input_tokens": sum(value for value in input_tokens if value is not None),
        "output_tokens": sum(value for value in output_tokens if value is not None),
    }


def _aggregate_cost_microusd(
    responses: Sequence[ProductionJudgeResponse],
    *,
    pricing: PricingSnapshot | None,
    pricing_provider: str | None,
    pricing_model: str | None,
) -> int:
    amounts: list[int] = []
    for response in responses:
        usage = response.usage
        if usage.reported_cost_usd is not None:
            try:
                amount = int(Decimal(usage.reported_cost_usd) * Decimal(1_000_000))
            except (InvalidOperation, ValueError) as exc:
                raise ProductionEvaluatorRunnerError(
                    "provider-reported judge cost is not numeric"
                ) from exc
            amounts.append(amount)
            continue
        if pricing is None:
            raise ProductionEvaluatorRunnerError(
                "estimated judge usage requires the bound pricing snapshot"
            )
        if usage.input_tokens is None or usage.output_tokens is None:
            raise ProductionEvaluatorRunnerError(
                "estimated judge usage requires input and output tokens"
            )
        if pricing_provider is None or pricing_model is None:
            raise ProductionEvaluatorRunnerError(
                "estimated judge usage has no provider/model pricing identity"
            )
        rate = pricing.rate_for(pricing_provider, pricing_model)
        amounts.append(
            rate.worst_case_microusd(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        )
    return sum(amounts)


def _canonical_json(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

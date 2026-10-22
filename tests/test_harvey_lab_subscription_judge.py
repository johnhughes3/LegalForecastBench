from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.harvey_lab_evaluator import HarveyLabJudgeRequest
from legalforecast.multiharness.harvey_lab_production_runner import (
    JudgeDeliverable,
    ProductionJudgeCall,
)
from legalforecast.multiharness.harvey_lab_subscription_judge import (
    ClaudeSubscriptionJudge,
    SubscriptionJudgeBoundary,
    SubscriptionJudgeError,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.spend import UsageObservation


def test_subscription_judge_boundary_accepts_only_unallocable_usage() -> None:
    boundary = SubscriptionJudgeBoundary()
    request = HarveyLabJudgeRequest(ordinal=1, criterion_id="c01")
    reservation = boundary.before_judge_call(request)
    observation = UsageObservation(
        basis="subscription_unallocable",
        input_tokens=10,
        output_tokens=1,
        unknown_reason="flat_subscription_has_no_per_call_allocation",
    )
    boundary.after_judge_call(request, reservation, observation)


class _JudgeServiceDouble:
    def __init__(self, envelope: object) -> None:
        self.envelope = envelope
        self.scopes: list[Path] = []

    def scoped_to_working_directory(self, path: Path) -> _JudgeServiceDouble:
        self.scopes.append(path)
        return self

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        return ExecutionReceipt.from_transcript(
            spec,
            stdout=json.dumps(self.envelope),
        )


@pytest.mark.parametrize(
    "envelope",
    [
        {
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "structured_output": {"verdict": "pass"},
        },
        {
            "type": "result",
            "subtype": "cancelled",
            "is_error": True,
            "result": '{"verdict":"pass"}',
        },
        {
            "type": "result",
            "subtype": "error_max_turns",
            "is_error": True,
            "result": {"verdict": "pass"},
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": {"verdict": "maybe"},
        },
    ],
)
def test_real_subscription_judge_rejects_nonterminal_or_malformed_verdict(
    tmp_path: Path, envelope: object
) -> None:
    service = _JudgeServiceDouble(envelope)
    judge = ClaudeSubscriptionJudge(
        service=service,  # type: ignore[arg-type]
        model="sonnet",
        run_root=tmp_path / "run",
        timeout_seconds=30,
    )

    with pytest.raises(SubscriptionJudgeError):
        judge(_production_judge_call(tmp_path))

    assert service.scopes == [
        tmp_path / "run" / "judge-work" / "criterion-001" / "attempt-00"
    ]


def test_real_subscription_judge_accepts_only_terminal_success(tmp_path: Path) -> None:
    service = _JudgeServiceDouble(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "modelUsage": {"claude-sonnet-4-6": {"inputTokens": 2}},
            "structured_output": {"verdict": "pass"},
            "usage": {"input_tokens": 2, "output_tokens": 1},
        }
    )
    response = ClaudeSubscriptionJudge(
        service=service,  # type: ignore[arg-type]
        model="sonnet",
        run_root=tmp_path / "run",
        timeout_seconds=30,
    )(_production_judge_call(tmp_path))

    assert response.verdict == "pass"
    assert response.judge_resolved_identity == "anthropic/claude-sonnet-4-6"


def _production_judge_call(tmp_path: Path) -> ProductionJudgeCall:
    return ProductionJudgeCall(
        request=HarveyLabJudgeRequest(1, "criterion-1", 0),
        run_spec=RunSpec(
            spec_id="evaluator",
            argv=("harvey-lab-evaluator",),
            working_directory=tmp_path / "evaluator",
            environment={},
            timeout_seconds=30,
        ),
        criterion={"title": "Criterion", "match_criteria": "Do the thing."},
        deliverable=JudgeDeliverable(
            artifact_paths=("memo.docx",),
            text="Candidate memorandum.",
            sha256="sha256:" + "a" * 64,
        ),
    )

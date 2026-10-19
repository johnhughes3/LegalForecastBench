"""Source-grounded scoring for an operator-run Harvey LAB evaluation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabEvaluatorExecution,
)
from legalforecast.multiharness.scoring import (
    ScoreNormalizationError,
    normalize_harvey_lab_verdicts,
)


class HarveyLabObservedScoreError(ValueError):
    """The evaluator output does not satisfy the pinned all-pass rule."""


@dataclass(frozen=True, slots=True)
class HarveyLabObservedScore:
    """All-pass score observed from an isolated evaluator, without an issuer."""

    score_value: int
    n_passed: int
    n_criteria: int
    evaluation_spec_sha256: str
    raw_result_sha256: str


def observed_harvey_lab_score(
    evaluation: HarveyLabEvaluatorExecution,
) -> HarveyLabObservedScore:
    """Validate and normalize the authenticated evaluator's raw score bytes."""

    try:
        summary = normalize_harvey_lab_verdicts(
            evaluation.raw_result,
            expected_criterion_count=evaluation.criterion_count,
        )
    except ScoreNormalizationError as exc:
        raise HarveyLabObservedScoreError(str(exc)) from exc
    return HarveyLabObservedScore(
        score_value=summary.score_value,
        n_passed=summary.n_passed,
        n_criteria=summary.n_criteria,
        evaluation_spec_sha256=evaluation.spec.spec_sha256,
        raw_result_sha256="sha256:" + hashlib.sha256(evaluation.raw_result).hexdigest(),
    )

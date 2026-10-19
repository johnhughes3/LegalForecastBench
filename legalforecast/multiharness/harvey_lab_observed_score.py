"""Source-grounded scoring for an operator-run Harvey LAB evaluation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabEvaluatorExecution,
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
        record = json.loads(evaluation.raw_result)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarveyLabObservedScoreError("evaluator result is not valid JSON") from exc
    if not isinstance(record, Mapping):
        raise HarveyLabObservedScoreError("evaluator result must be a JSON object")
    typed_record = cast(Mapping[str, object], record)
    n_passed = typed_record.get("n_passed")
    n_criteria = typed_record.get("n_criteria")
    score = typed_record.get("score")
    if (
        type(n_passed) is not int
        or type(n_criteria) is not int
        or n_criteria != evaluation.criterion_count
        or not 0 <= n_passed <= n_criteria
    ):
        raise HarveyLabObservedScoreError(
            "evaluator result has invalid criterion counts"
        )
    expected = 1 if n_passed == n_criteria else 0
    if type(score) not in {int, float} or float(cast(int | float, score)) != expected:
        raise HarveyLabObservedScoreError("evaluator result violates all-pass scoring")
    return HarveyLabObservedScore(
        score_value=expected,
        n_passed=n_passed,
        n_criteria=n_criteria,
        evaluation_spec_sha256=evaluation.spec.spec_sha256,
        raw_result_sha256="sha256:" + hashlib.sha256(evaluation.raw_result).hexdigest(),
    )

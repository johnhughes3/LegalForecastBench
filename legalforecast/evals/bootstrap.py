"""Paired clustered bootstrap inference for model score comparisons."""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from legalforecast.evals.scorers import UnitScore

DEFAULT_BOOTSTRAP_REPLICATES = 5000
DEFAULT_CI_LEVEL = 0.95


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    """Configuration for paired clustered bootstrap inference."""

    replicates: int = DEFAULT_BOOTSTRAP_REPLICATES
    seed: int = 20260514
    ci_level: float = DEFAULT_CI_LEVEL

    def __post_init__(self) -> None:
        if self.replicates <= 0:
            raise ValueError("replicates must be positive")
        if not 0 < self.ci_level < 1:
            raise ValueError("ci_level must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ModelScoreInput:
    """Unit-level scores for one model over the same benchmark slice."""

    model_id: str
    unit_scores: tuple[UnitScore, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.model_id, "model_id")
        if not self.unit_scores:
            raise ValueError("unit_scores must not be empty")


@dataclass(frozen=True, slots=True)
class BootstrapReplicate:
    """One paired cluster-resampled replicate."""

    replicate_index: int
    sampled_case_ids: tuple[str, ...]
    micro_briers: dict[str, float]

    def to_record(self) -> dict[str, Any]:
        return {
            "replicate_index": self.replicate_index,
            "sampled_case_ids": list(self.sampled_case_ids),
            "micro_briers": dict(self.micro_briers),
        }


@dataclass(frozen=True, slots=True)
class PairwiseDelta:
    """Bootstrap confidence interval for model_a minus model_b micro-Brier."""

    model_a: str
    model_b: str
    observed_delta: float
    ci_low: float
    ci_high: float
    probability_a_better: float

    def to_record(self) -> dict[str, Any]:
        return {
            "model_a": self.model_a,
            "model_b": self.model_b,
            "observed_delta": self.observed_delta,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "probability_a_better": self.probability_a_better,
        }


@dataclass(frozen=True, slots=True)
class ModelRank:
    """Observed rank and uncertainty tier for one model."""

    model_id: str
    observed_micro_brier: float
    rank: int
    tier: int

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "observed_micro_brier": self.observed_micro_brier,
            "rank": self.rank,
            "tier": self.tier,
        }


@dataclass(frozen=True, slots=True)
class BootstrapInferenceResult:
    """Complete paired clustered bootstrap result."""

    config: BootstrapConfig
    case_ids: tuple[str, ...]
    observed_micro_briers: dict[str, float]
    pairwise_deltas: tuple[PairwiseDelta, ...]
    ranks: tuple[ModelRank, ...]
    replicates: tuple[BootstrapReplicate, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "config": {
                "replicates": self.config.replicates,
                "seed": self.config.seed,
                "ci_level": self.config.ci_level,
            },
            "case_ids": list(self.case_ids),
            "observed_micro_briers": dict(self.observed_micro_briers),
            "pairwise_deltas": [delta.to_record() for delta in self.pairwise_deltas],
            "ranks": [rank.to_record() for rank in self.ranks],
            "replicates": [replicate.to_record() for replicate in self.replicates],
        }


def paired_clustered_bootstrap(
    model_scores: tuple[ModelScoreInput, ...],
    *,
    config: BootstrapConfig | None = None,
) -> BootstrapInferenceResult:
    """Run paired clustered bootstrap over case/motion clusters.

    Every replicate samples case IDs with replacement and includes all unit
    scores for each sampled case. The same sampled cases are used for every
    model, so pairwise deltas are paired by construction.
    """

    effective_config = config or BootstrapConfig()
    case_ids = _validate_model_score_inputs(model_scores)
    observed = {
        model.model_id: _mean(score.brier for score in model.unit_scores)
        for model in model_scores
    }
    scores_by_model_case = {
        model.model_id: _scores_by_case(model.unit_scores) for model in model_scores
    }

    sampled_case_sets = draw_cluster_samples(
        case_ids,
        replicates=effective_config.replicates,
        seed=effective_config.seed,
    )
    replicates = tuple(
        BootstrapReplicate(
            replicate_index=index,
            sampled_case_ids=sampled_case_ids,
            micro_briers={
                model.model_id: _resampled_micro_brier(
                    scores_by_model_case[model.model_id],
                    sampled_case_ids,
                )
                for model in model_scores
            },
        )
        for index, sampled_case_ids in enumerate(sampled_case_sets)
    )
    pairwise_deltas = _pairwise_deltas(
        model_scores,
        observed_micro_briers=observed,
        replicates=replicates,
        ci_level=effective_config.ci_level,
    )
    return BootstrapInferenceResult(
        config=effective_config,
        case_ids=case_ids,
        observed_micro_briers=observed,
        pairwise_deltas=pairwise_deltas,
        ranks=_rank_tiers(observed, pairwise_deltas),
        replicates=replicates,
    )


def draw_cluster_samples(
    case_ids: tuple[str, ...],
    *,
    replicates: int,
    seed: int,
) -> tuple[tuple[str, ...], ...]:
    """Draw deterministic bootstrap samples of case IDs with replacement."""

    if not case_ids:
        raise ValueError("case_ids must not be empty")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    rng = random.Random(seed)
    return tuple(
        tuple(rng.choice(case_ids) for _ in case_ids)
        for _replicate in range(replicates)
    )


def _pairwise_deltas(
    model_scores: tuple[ModelScoreInput, ...],
    *,
    observed_micro_briers: dict[str, float],
    replicates: tuple[BootstrapReplicate, ...],
    ci_level: float,
) -> tuple[PairwiseDelta, ...]:
    alpha = 1 - ci_level
    deltas: list[PairwiseDelta] = []
    for model_a, model_b in itertools.combinations(model_scores, 2):
        replicate_deltas = tuple(
            replicate.micro_briers[model_a.model_id]
            - replicate.micro_briers[model_b.model_id]
            for replicate in replicates
        )
        deltas.append(
            PairwiseDelta(
                model_a=model_a.model_id,
                model_b=model_b.model_id,
                observed_delta=(
                    observed_micro_briers[model_a.model_id]
                    - observed_micro_briers[model_b.model_id]
                ),
                ci_low=_quantile(replicate_deltas, alpha / 2),
                ci_high=_quantile(replicate_deltas, 1 - (alpha / 2)),
                probability_a_better=(
                    sum(1 for delta in replicate_deltas if delta < 0)
                    / len(replicate_deltas)
                ),
            )
        )
    return tuple(deltas)


def _rank_tiers(
    observed_micro_briers: dict[str, float],
    pairwise_deltas: tuple[PairwiseDelta, ...],
) -> tuple[ModelRank, ...]:
    sorted_models = sorted(observed_micro_briers, key=observed_micro_briers.__getitem__)
    rank_by_model = {
        model_id: index + 1 for index, model_id in enumerate(sorted_models)
    }
    remaining = list(sorted_models)
    tier_by_model: dict[str, int] = {}
    tier = 1
    while remaining:
        best = remaining[0]
        current_tier = [best]
        for model_id in remaining[1:]:
            ci_low, _ci_high = _delta_ci(
                model_id,
                best,
                pairwise_deltas,
            )
            if ci_low <= 0:
                current_tier.append(model_id)
        for model_id in current_tier:
            tier_by_model[model_id] = tier
        remaining = [model_id for model_id in remaining if model_id not in current_tier]
        tier += 1
    return tuple(
        ModelRank(
            model_id=model_id,
            observed_micro_brier=observed_micro_briers[model_id],
            rank=rank_by_model[model_id],
            tier=tier_by_model[model_id],
        )
        for model_id in sorted_models
    )


def _delta_ci(
    model_a: str,
    model_b: str,
    pairwise_deltas: tuple[PairwiseDelta, ...],
) -> tuple[float, float]:
    for delta in pairwise_deltas:
        if delta.model_a == model_a and delta.model_b == model_b:
            return (delta.ci_low, delta.ci_high)
        if delta.model_a == model_b and delta.model_b == model_a:
            return (-delta.ci_high, -delta.ci_low)
    raise KeyError(f"missing pairwise delta for {model_a} and {model_b}")


def _validate_model_score_inputs(
    model_scores: tuple[ModelScoreInput, ...],
) -> tuple[str, ...]:
    if len(model_scores) < 2:
        raise ValueError("paired bootstrap requires at least two models")
    model_ids = [model.model_id for model in model_scores]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("model_id values must be unique")

    reference_keys: tuple[tuple[str, str], ...] | None = None
    case_ids: tuple[str, ...] | None = None
    for model in model_scores:
        keys = tuple(
            sorted((score.case_id, score.unit_id) for score in model.unit_scores)
        )
        if reference_keys is None:
            reference_keys = keys
            case_ids = tuple(sorted({case_id for case_id, _unit_id in keys}))
            continue
        if keys != reference_keys:
            raise ValueError("paired bootstrap requires matching case/unit keys")
    if case_ids is None or not case_ids:
        raise ValueError("model_scores must include at least one case")
    return case_ids


def _scores_by_case(
    unit_scores: tuple[UnitScore, ...],
) -> dict[str, tuple[UnitScore, ...]]:
    grouped: dict[str, list[UnitScore]] = {}
    for unit_score in unit_scores:
        grouped.setdefault(unit_score.case_id, []).append(unit_score)
    return {
        case_id: tuple(scores)
        for case_id, scores in sorted(grouped.items(), key=lambda item: item[0])
    }


def _resampled_micro_brier(
    scores_by_case: dict[str, tuple[UnitScore, ...]],
    sampled_case_ids: tuple[str, ...],
) -> float:
    return _mean(
        unit_score.brier
        for case_id in sampled_case_ids
        for unit_score in scores_by_case[case_id]
    )


def _quantile(values: tuple[float, ...], q: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = q * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + (
        (sorted_values[upper_index] - sorted_values[lower_index]) * fraction
    )


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    if not materialized:
        raise ValueError("cannot take mean of empty values")
    return sum(materialized) / len(materialized)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")

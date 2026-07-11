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
BONFERRONI_RANK_TIER_METHOD = "bonferroni_pairwise_bootstrap_confidence_intervals"
UNADJUSTED_RANK_TIER_METHOD = "unadjusted_pairwise_bootstrap_confidence_intervals"
BONFERRONI_RANK_TIER_CAVEAT = (
    "Rank tiers use Bonferroni-adjusted pairwise bootstrap confidence intervals "
    "when there are multiple model comparisons; they are descriptive tiers, not "
    "a full simultaneous ranking model."
)
UNADJUSTED_RANK_TIER_CAVEAT = (
    "Rank tiers use unadjusted pairwise bootstrap confidence intervals; they are "
    "descriptive and not simultaneous multiple-comparison-adjusted intervals."
)


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    """Configuration for paired clustered bootstrap inference."""

    replicates: int = DEFAULT_BOOTSTRAP_REPLICATES
    seed: int = 20260514
    ci_level: float = DEFAULT_CI_LEVEL
    rank_tier_correction: str = "bonferroni"
    small_cluster_threshold: int = 30

    def __post_init__(self) -> None:
        if self.replicates <= 0:
            raise ValueError("replicates must be positive")
        if not 0 < self.ci_level < 1:
            raise ValueError("ci_level must be between 0 and 1")
        if self.rank_tier_correction not in {"bonferroni", "none"}:
            raise ValueError("rank_tier_correction must be 'bonferroni' or 'none'")
        if self.small_cluster_threshold <= 0:
            raise ValueError("small_cluster_threshold must be positive")


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
class _BootstrapSamplingFrame:
    """Validated paired units and the independence clusters to resample."""

    case_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    case_ids_by_cluster: dict[str, tuple[str, ...]]
    cluster_id_by_unit_key: dict[tuple[str, str], str]


@dataclass(frozen=True, slots=True)
class BootstrapReplicate:
    """One paired cluster-resampled replicate."""

    replicate_index: int
    sampled_case_ids: tuple[str, ...]
    micro_briers: dict[str, float]
    sampled_cluster_ids: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "replicate_index": self.replicate_index,
            "sampled_case_ids": list(self.sampled_case_ids),
            "sampled_cluster_ids": list(self.sampled_cluster_ids),
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
    tier: int | None

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
    cluster_ids: tuple[str, ...] = ()
    cluster_dimension: str = "case"
    small_cluster_warning: str | None = None
    rank_tier_ci_level: float = DEFAULT_CI_LEVEL

    @property
    def rank_tier_method(self) -> str:
        return _rank_tier_method(self.config.rank_tier_correction)

    @property
    def rank_tier_caveat(self) -> str:
        return _rank_tier_caveat(self.config.rank_tier_correction)

    def to_record(self) -> dict[str, Any]:
        return {
            "config": {
                "replicates": self.config.replicates,
                "seed": self.config.seed,
                "ci_level": self.config.ci_level,
                "rank_tier_correction": self.config.rank_tier_correction,
                "small_cluster_threshold": self.config.small_cluster_threshold,
            },
            "case_ids": list(self.case_ids),
            "cluster_ids": list(self.cluster_ids),
            "cluster_dimension": self.cluster_dimension,
            "small_cluster_warning": self.small_cluster_warning,
            "rank_tier_ci_level": self.rank_tier_ci_level,
            "rank_tier_method": self.rank_tier_method,
            "rank_tier_caveat": self.rank_tier_caveat,
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
    """Run paired clustered bootstrap over case, related-family, or MDL clusters.

    Every replicate samples the coarsest declared independence unit with
    replacement: MDL family when present, otherwise related-case family when
    present, otherwise case ID. It includes all unit scores for each sampled
    cluster. The same sampled clusters are used for every model, so pairwise
    deltas are paired by construction.
    """

    effective_config = config or BootstrapConfig()
    frame = _validate_model_score_inputs(model_scores)
    observed = {
        model.model_id: _mean(score.brier for score in model.unit_scores)
        for model in model_scores
    }
    scores_by_model_cluster = {
        model.model_id: _scores_by_cluster(
            model.unit_scores,
            frame.cluster_id_by_unit_key,
        )
        for model in model_scores
    }

    sampled_cluster_sets = draw_cluster_samples(
        frame.cluster_ids,
        replicates=effective_config.replicates,
        seed=effective_config.seed,
    )
    replicates = tuple(
        BootstrapReplicate(
            replicate_index=index,
            sampled_case_ids=_sampled_case_ids(
                frame.case_ids_by_cluster,
                sampled_cluster_ids,
            ),
            sampled_cluster_ids=sampled_cluster_ids,
            micro_briers={
                model.model_id: _resampled_micro_brier(
                    scores_by_model_cluster[model.model_id],
                    sampled_cluster_ids,
                )
                for model in model_scores
            },
        )
        for index, sampled_cluster_ids in enumerate(sampled_cluster_sets)
    )
    pairwise_deltas = _pairwise_deltas(
        model_scores,
        observed_micro_briers=observed,
        replicates=replicates,
        ci_level=effective_config.ci_level,
    )
    rank_tier_ci_level = _rank_tier_ci_level(
        ci_level=effective_config.ci_level,
        model_count=len(model_scores),
        correction=effective_config.rank_tier_correction,
    )
    rank_tier_deltas = (
        pairwise_deltas
        if rank_tier_ci_level == effective_config.ci_level
        else _pairwise_deltas(
            model_scores,
            observed_micro_briers=observed,
            replicates=replicates,
            ci_level=rank_tier_ci_level,
        )
    )
    cluster_dimension = _cluster_dimension(frame.cluster_ids)
    small_cluster_warning = _small_cluster_warning(
        cluster_count=len(frame.cluster_ids),
        threshold=effective_config.small_cluster_threshold,
        cluster_dimension=cluster_dimension,
    )
    return BootstrapInferenceResult(
        config=effective_config,
        case_ids=frame.case_ids,
        cluster_ids=frame.cluster_ids,
        cluster_dimension=cluster_dimension,
        small_cluster_warning=small_cluster_warning,
        rank_tier_ci_level=rank_tier_ci_level,
        observed_micro_briers=observed,
        pairwise_deltas=pairwise_deltas,
        ranks=_rank_tiers(
            observed,
            rank_tier_deltas,
            assign_tiers=small_cluster_warning is None,
        ),
        replicates=replicates,
    )


def draw_cluster_samples(
    case_ids: tuple[str, ...],
    *,
    replicates: int,
    seed: int,
) -> tuple[tuple[str, ...], ...]:
    """Draw deterministic bootstrap samples of cluster IDs with replacement."""

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
                probability_a_better=_probability_lower_brier_better(replicate_deltas),
            )
        )
    return tuple(deltas)


def _rank_tiers(
    observed_micro_briers: dict[str, float],
    pairwise_deltas: tuple[PairwiseDelta, ...],
    *,
    assign_tiers: bool = True,
) -> tuple[ModelRank, ...]:
    sorted_models = sorted(observed_micro_briers, key=observed_micro_briers.__getitem__)
    rank_by_model = {
        model_id: index + 1 for index, model_id in enumerate(sorted_models)
    }
    if not assign_tiers:
        return tuple(
            ModelRank(
                model_id=model_id,
                observed_micro_brier=observed_micro_briers[model_id],
                rank=rank_by_model[model_id],
                tier=None,
            )
            for model_id in sorted_models
        )
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


def _probability_lower_brier_better(deltas: tuple[float, ...]) -> float:
    if not deltas:
        raise ValueError("deltas must not be empty")
    strict_wins = sum(1 for delta in deltas if delta < 0)
    ties = sum(1 for delta in deltas if delta == 0)
    return (strict_wins + (0.5 * ties)) / len(deltas)


def _cluster_dimension(cluster_ids: tuple[str, ...]) -> str:
    if any(cluster_id.startswith("mdl_family:") for cluster_id in cluster_ids):
        return "mdl_family"
    if any(cluster_id.startswith("related_family:") for cluster_id in cluster_ids):
        return "related_family"
    return "case"


def _small_cluster_warning(
    *, cluster_count: int, threshold: int, cluster_dimension: str
) -> str | None:
    if cluster_count >= threshold:
        return None
    return (
        f"Only {cluster_count} independent {cluster_dimension} clusters are "
        f"available, below the configured small-cluster threshold of {threshold}; "
        "confidence intervals are unstable and uncertainty tiers are suppressed."
    )


def _rank_tier_ci_level(
    *,
    ci_level: float,
    model_count: int,
    correction: str,
) -> float:
    if correction == "none" or model_count < 3:
        return ci_level
    pair_count = model_count * (model_count - 1) // 2
    familywise_alpha = 1 - ci_level
    return 1 - (familywise_alpha / pair_count)


def _rank_tier_method(correction: str) -> str:
    if correction == "bonferroni":
        return BONFERRONI_RANK_TIER_METHOD
    return UNADJUSTED_RANK_TIER_METHOD


def _rank_tier_caveat(correction: str) -> str:
    if correction == "bonferroni":
        return BONFERRONI_RANK_TIER_CAVEAT
    return UNADJUSTED_RANK_TIER_CAVEAT


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
) -> _BootstrapSamplingFrame:
    if len(model_scores) < 2:
        raise ValueError("paired bootstrap requires at least two models")
    model_ids = [model.model_id for model in model_scores]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("model_id values must be unique")

    reference_keys: tuple[tuple[str, str], ...] | None = None
    reference_clusters: dict[tuple[str, str], str] | None = None
    case_ids_by_cluster: dict[str, tuple[str, ...]] | None = None
    for model in model_scores:
        keys = tuple(
            sorted((score.case_id, score.unit_id) for score in model.unit_scores)
        )
        clusters = _cluster_id_by_unit_key(model.unit_scores)
        if reference_keys is None:
            reference_keys = keys
            reference_clusters = clusters
            case_ids_by_cluster = _case_ids_by_cluster(
                model.unit_scores,
                clusters,
            )
            continue
        if keys != reference_keys:
            raise ValueError("paired bootstrap requires matching case/unit keys")
        if clusters != reference_clusters:
            raise ValueError(
                "paired bootstrap requires matching bootstrap cluster metadata"
            )
    if (
        reference_keys is None
        or reference_clusters is None
        or case_ids_by_cluster is None
    ):
        raise ValueError("model_scores must include at least one case")
    case_ids = tuple(sorted({case_id for case_id, _unit_id in reference_keys}))
    if not case_ids:
        raise ValueError("model_scores must include at least one case")
    return _BootstrapSamplingFrame(
        case_ids=case_ids,
        cluster_ids=tuple(sorted(case_ids_by_cluster)),
        case_ids_by_cluster=case_ids_by_cluster,
        cluster_id_by_unit_key=reference_clusters,
    )


def _cluster_id_by_unit_key(
    unit_scores: tuple[UnitScore, ...],
) -> dict[tuple[str, str], str]:
    cluster_by_unit_key: dict[tuple[str, str], str] = {}
    cluster_by_case_id: dict[str, str] = {}
    for unit_score in unit_scores:
        cluster_id = _bootstrap_cluster_id(unit_score)
        existing_case_cluster = cluster_by_case_id.setdefault(
            unit_score.case_id,
            cluster_id,
        )
        if existing_case_cluster != cluster_id:
            raise ValueError(
                "paired bootstrap requires one cluster per case_id; "
                f"{unit_score.case_id} has conflicting metadata"
            )
        cluster_by_unit_key[(unit_score.case_id, unit_score.unit_id)] = cluster_id
    return cluster_by_unit_key


def _case_ids_by_cluster(
    unit_scores: tuple[UnitScore, ...],
    cluster_id_by_unit_key: dict[tuple[str, str], str],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for unit_score in unit_scores:
        cluster_id = cluster_id_by_unit_key[(unit_score.case_id, unit_score.unit_id)]
        grouped.setdefault(cluster_id, set()).add(unit_score.case_id)
    return {
        cluster_id: tuple(sorted(case_ids))
        for cluster_id, case_ids in sorted(grouped.items(), key=lambda item: item[0])
    }


def _bootstrap_cluster_id(unit_score: UnitScore) -> str:
    if unit_score.mdl_family_id is not None:
        return f"mdl_family:{unit_score.mdl_family_id}"
    if unit_score.related_family_id is not None:
        return f"related_family:{unit_score.related_family_id}"
    return f"case:{unit_score.case_id}"


def _scores_by_cluster(
    unit_scores: tuple[UnitScore, ...],
    cluster_id_by_unit_key: dict[tuple[str, str], str],
) -> dict[str, tuple[UnitScore, ...]]:
    grouped: dict[str, list[UnitScore]] = {}
    for unit_score in unit_scores:
        cluster_id = cluster_id_by_unit_key[(unit_score.case_id, unit_score.unit_id)]
        grouped.setdefault(cluster_id, []).append(unit_score)
    return {
        cluster_id: tuple(scores)
        for cluster_id, scores in sorted(grouped.items(), key=lambda item: item[0])
    }


def _sampled_case_ids(
    case_ids_by_cluster: dict[str, tuple[str, ...]],
    sampled_cluster_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        case_id
        for cluster_id in sampled_cluster_ids
        for case_id in case_ids_by_cluster[cluster_id]
    )


def _resampled_micro_brier(
    scores_by_cluster: dict[str, tuple[UnitScore, ...]],
    sampled_cluster_ids: tuple[str, ...],
) -> float:
    return _mean(
        unit_score.brier
        for cluster_id in sampled_cluster_ids
        for unit_score in scores_by_cluster[cluster_id]
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

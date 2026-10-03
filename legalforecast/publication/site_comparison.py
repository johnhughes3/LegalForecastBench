"""Paired public-unit comparisons with the existing case-cluster bootstrap."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

METRICS = ("micro_brier", "equal_case_brier", "accuracy")


def compare(
    models: dict[str, list[dict[str, Any]]],
    *,
    replicates: int = 1_000_000,
    seed: int = 20260514,
    family_model_count: int | None = None,
) -> dict[str, Any]:
    """Resample the same cases for every model, retaining every unit per case."""
    ids = sorted(models)
    family_size = family_model_count or len(ids)
    if len(ids) < 2 or family_size < len(ids) or replicates <= 0:
        raise ValueError(
            "Need at least two models, a sufficient family, and replicates"
        )
    reference: dict[tuple[str, str], int] | None = None
    predictions: dict[str, dict[tuple[str, str], float]] = {}
    for model, rows in models.items():
        labels: dict[tuple[str, str], int] = {}
        probabilities: dict[tuple[str, str], float] = {}
        for row in rows:
            key = (row["case_id"], row["unit_id"])
            probability = row["probability_fully_dismissed"]
            if key in labels or row["outcome"] not in (0, 1):
                raise ValueError("Duplicate unit or invalid outcome")
            if not np.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("Invalid probability")
            if (
                row.get("defaulted_prediction")
                or row.get("invalid_reason")
                or row.get("parser_status", "valid") != "valid"
            ):
                raise ValueError("Invalid or defaulted prediction")
            if row.get("mdl_family_id") or row.get("related_family_id"):
                raise ValueError("Declared families require family-cluster analysis")
            labels[key] = row["outcome"]
            probabilities[key] = probability
        if not labels or (reference is not None and labels != reference):
            raise ValueError("Models must have identical case/unit/outcome keys")
        reference = labels
        predictions[model] = probabilities
    assert reference is not None
    cases = sorted({key[0] for key in reference})
    case_keys = [[key for key in sorted(reference) if key[0] == c] for c in cases]
    counts = np.array([len(keys) for keys in case_keys])
    loss = np.array(
        [
            [sum((predictions[m][k] - reference[k]) ** 2 for k in keys) for m in ids]
            for keys in case_keys
        ]
    )
    correct = np.array(
        [
            [
                sum((predictions[m][k] >= 0.5) == bool(reference[k]) for k in keys)
                for m in ids
            ]
            for keys in case_keys
        ]
    )
    means = loss / counts[:, None]
    observed = np.stack(
        [
            loss.sum(axis=0) / counts.sum(),
            means.mean(axis=0),
            correct.sum(axis=0) / counts.sum(),
        ]
    )
    rng = np.random.default_rng(seed)
    bootstrap = np.empty((replicates, 3, len(ids)))
    for start in range(0, replicates, 10000):
        weights = rng.multinomial(
            len(cases),
            np.full(len(cases), 1 / len(cases)),
            size=min(10000, replicates - start),
        )
        denominator = weights @ counts
        target = bootstrap[start : start + len(weights)]
        target[:, 0, :] = (weights @ loss) / denominator[:, None]
        target[:, 1, :] = (weights @ means) / len(cases)
        target[:, 2, :] = (weights @ correct) / denominator[:, None]
    family_pairs = family_size * (family_size - 1) // 2
    alpha = 0.05 / (family_pairs * len(METRICS))
    pairs: list[dict[str, Any]] = []
    significant: list[dict[str, str]] = []
    for a, b in combinations(range(len(ids)), 2):
        for j, metric in enumerate(METRICS):
            low, high = np.quantile(
                bootstrap[:, j, a] - bootstrap[:, j, b],
                [alpha / 2, 1 - alpha / 2],
                method="linear",
            )
            is_significant = bool(low > 0 or high < 0)
            pairs.append(
                dict(
                    model_a=ids[a],
                    model_b=ids[b],
                    metric=metric,
                    delta=float(observed[j, a] - observed[j, b]),
                    ci_low=float(low),
                    ci_high=float(high),
                    significant=is_significant,
                )
            )
            if is_significant:
                a_better = high < 0 if j < 2 else low > 0
                significant.append(
                    dict(
                        better=ids[a] if a_better else ids[b],
                        worse=ids[b] if a_better else ids[a],
                        metric=metric,
                    )
                )
    return dict(
        method="Paired case-cluster percentile bootstrap",
        replicates=replicates,
        seed=seed,
        rng="NumPy PCG64 multinomial case multiplicities",
        numpy_version=np.__version__,
        family_model_count=family_size,
        available_models=ids,
        case_count=len(cases),
        unit_count=len(reference),
        familywise_alpha=0.05,
        interval_confidence=1 - alpha,
        correction=f"Bonferroni across {family_pairs} model pairs and three metrics",
        metrics={
            m: {metric: float(observed[j, i]) for j, metric in enumerate(METRICS)}
            for i, m in enumerate(ids)
        },
        pairs=pairs,
        significant_pairs=significant,
        caveat=(
            "Exploratory. Cross-case dependence has not been verified. "
            "Unavailable pairs are not tested."
        ),
    )

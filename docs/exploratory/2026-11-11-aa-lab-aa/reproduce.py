"""Reproduce only the numerical claims in the November 11 exploratory comparison.

Run from the repository root with the pinned, analysis-only SciPy dependency::

    uv run --locked --with scipy==1.18.1 python \
        docs/exploratory/2026-11-11-aa-lab-aa/reproduce.py --check

Without --check, print the calculated JSON to stdout. Inputs resolve relative
to this script; execution requires no network, provider calls, or credentials.
"""

# pyright: basic
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.stats import rankdata

DIRECTORY = Path(__file__).resolve().parent
SEED = 20261111
PERMUTATIONS = 100_000
BATCH_SIZE = 1_000


def normalized_ranks(values: list[float]) -> NDArray[np.float64]:
    """Use average ranks for ties, centered and scaled to unit length."""
    ranks = np.asarray(rankdata(values), dtype=np.float64)
    ranks -= ranks.mean()
    norm = np.linalg.norm(ranks)
    if norm == 0:
        raise ValueError("Correlation is undefined for a constant score vector")
    return ranks / norm


def spearman(x: list[float], y: list[float]) -> float:
    """Correlate ranks; positive means better AA accompanies better performance."""
    return round(float(normalized_ranks(x) @ normalized_ranks(y)), 12)


def permutation_p(x: list[float], y: list[float]) -> float:
    """Reproduce the original two-sided random-pairing test with add-one correction."""
    rng = np.random.default_rng(SEED)
    x_rank, y_rank = normalized_ranks(x), normalized_ranks(y)
    observed = float(x_rank @ y_rank)
    extreme = 0
    for _ in range(PERMUTATIONS // BATCH_SIZE):
        permutations = np.argsort(rng.random((BATCH_SIZE, len(y))), axis=1)
        null = y_rank[permutations] @ x_rank
        extreme += int(np.sum(np.abs(null) >= abs(observed) - 1e-12))
    return round((extreme + 1) / (PERMUTATIONS + 1), 12)


def calculate() -> dict[str, object]:
    """Calculate the tweet's comparisons and references from the saved source rows."""
    with (DIRECTORY / "inputs.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cohort = json.loads((DIRECTORY / "cohort.json").read_text(encoding="utf-8"))
    ranked = [row for row in rows if row["ranked"] == "True"]
    (reference,) = [row for row in rows if row["ranked"] == "False"]
    worst = max(ranked, key=lambda row: float(row["micro_brier"]))
    same_effort = [row for row in ranked if row["aa_same_effort_score"]]
    shared = [row for row in ranked if row["aa_shared_model_score"]]
    if (len(ranked), len(same_effort), len(shared)) != (21, 10, 12):
        raise ValueError(
            "The saved analysis requires 21 ranked, 10 effort, 12 shared models"
        )

    aa_effort = [float(row["aa_same_effort_score"]) for row in same_effort]
    lfb_effort = [-float(row["micro_brier"]) for row in same_effort]
    aa_shared = [float(row["aa_shared_model_score"]) for row in shared]
    lfb_shared = [-float(row["micro_brier"]) for row in shared]
    lab_shared = [float(row["lab_aa_gated_all_pass"]) for row in shared]
    rate = cohort["dismissed_units"] / cohort["prediction_units"]
    constant_brier = rate * (1 - rate)

    return {
        "older_model_comparison": {
            "reference_model": "gpt-4.1-2025-04-14",
            "reference_micro_brier": float(reference["micro_brier"]),
            "worst_ranked_model": worst["model"],
            "worst_ranked_micro_brier": float(worst["micro_brier"]),
        },
        "same_effort_aa_comparison": {
            "models": len(same_effort),
            "spearman": spearman(aa_effort, lfb_effort),
            "two_sided_permutation_p": permutation_p(aa_effort, lfb_effort),
            "permutations": PERMUTATIONS,
            "seed": SEED,
        },
        "shared_model_aa_comparison": {
            "models": len(shared),
            "lfb_spearman": spearman(aa_shared, lfb_shared),
            "lab_aa_spearman": spearman(aa_shared, lab_shared),
        },
        "brier_baselines": {
            "constant_half": 0.5**2,
            "retrospectively_fitted_constant": round(constant_brier, 12),
            "ranked_models": len(ranked),
            "ranked_models_beating_both": sum(
                float(row["micro_brier"]) < min(0.25, constant_brier) for row in ranked
            ),
            "reference_beats_either": float(reference["micro_brier"])
            < max(0.25, constant_brier),
        },
        "cohort": {
            "cases": cohort["cases"],
            "prediction_units_per_model": cohort["prediction_units"],
        },
    }


def main() -> None:
    """Print the results, or verify the committed output without writing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify results.json without changing it."
    )
    args = parser.parse_args()
    result = calculate()
    if args.check:
        expected = json.loads((DIRECTORY / "results.json").read_text(encoding="utf-8"))
        if result != expected:
            parser.exit(1, "Calculated results differ from results.json\n")
        print("All cited numerical results reproduce from the saved inputs.")
    else:
        print(json.dumps(result, indent=2) + "\n", end="")


if __name__ == "__main__":
    main()

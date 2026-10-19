"""Confidence coverage for the citation review's two possible analyses."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path


def test_two_look_bounds_control_noncoverage() -> None:
    """Enumerate the actual stopping procedure, including the reviewer's example."""
    path = Path(__file__).resolve().parents[1] / "scripts/harvey_citation_sample.py"
    spec = importlib.util.spec_from_file_location("citation_sample", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    population = 436
    early_bound = module.lower_bound(population, 10, 10)
    late_bounds = [module.lower_bound(population, 20, k) for k in range(20)]
    # Given k successes among 20, the first ten are all successes with
    # probability comb(k, 10) / comb(20, 10). Exclude those early stops.
    for errors in range(population + 1):
        noncoverage = 0.0
        for k in range(21):
            probability = (
                math.comb(errors, k)
                * math.comb(population - errors, 20 - k)
                / math.comb(population, 20)
            )
            early = math.comb(k, 10) / math.comb(20, 10)
            if early_bound > errors:
                noncoverage += probability * early
            if k < 20 and late_bounds[k] > errors:
                noncoverage += probability * (1 - early)
        assert noncoverage <= 0.05 + 1e-12, (errors, noncoverage)

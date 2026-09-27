"""Case-cluster inference preserves paired units and different weighting rules."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "compare_site_results",
    Path(__file__).parents[1] / "scripts/compare_site_results.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def rows(probabilities: list[float]) -> list[dict[str, object]]:
    return [
        dict(
            case_id="one" if i < 2 else "two",
            unit_id=str(i),
            outcome=1,
            probability_fully_dismissed=p,
        )
        for i, p in enumerate(probabilities)
    ]


def test_pairing_weighting_and_bonferroni_family() -> None:
    result = MODULE.compare(
        {"perfect": rows([1, 1, 1]), "unequal": rows([1, 1, 0])},
        replicates=500,
        family_model_count=16,
    )
    assert result["metrics"]["unequal"]["micro_brier"] == pytest.approx(1 / 3)
    assert result["metrics"]["unequal"]["equal_case_brier"] == 0.5
    assert result["metrics"]["unequal"]["accuracy"] == pytest.approx(2 / 3)
    assert result["interval_confidence"] == pytest.approx(1 - 0.05 / 360)
    assert result == MODULE.compare(
        {"perfect": rows([1, 1, 1]), "unequal": rows([1, 1, 0])},
        replicates=500,
        family_model_count=16,
    )


def test_identical_predictions_have_zero_interval() -> None:
    result = MODULE.compare(
        {"a": rows([0.2, 0.7, 0.5]), "b": rows([0.2, 0.7, 0.5])}, replicates=100
    )
    assert not result["significant_pairs"]
    assert all(p["ci_low"] == p["ci_high"] == 0 for p in result["pairs"])


@pytest.mark.parametrize(
    "change", ["outcome", "duplicate", "family", "default", "nan", "parser"]
)
def test_refuse_unpaired_or_invalid_evidence(change: str) -> None:
    altered = rows([0.2, 0.7, 0.5])
    if change == "outcome":
        altered[0]["outcome"] = 0
    if change == "duplicate":
        altered.append(altered[0])
    if change == "family":
        altered[0]["mdl_family_id"] = "shared"
    if change == "default":
        altered[0]["defaulted_prediction"] = True
    if change == "nan":
        altered[0]["probability_fully_dismissed"] = float("nan")
    if change == "parser":
        altered[0]["parser_status"] = "invalid"
    with pytest.raises(ValueError):
        MODULE.compare({"a": rows([0.2, 0.7, 0.5]), "b": altered}, replicates=100)


@pytest.mark.parametrize("better", ["a", "b"])
def test_dominance_direction_for_loss_and_accuracy(better: str) -> None:
    worse = "b" if better == "a" else "a"
    result = MODULE.compare(
        {better: rows([1, 1, 1]), worse: rows([0, 0, 0])}, replicates=100
    )
    assert result["significant_pairs"] == [
        {"better": better, "worse": worse, "metric": metric}
        for metric in ("micro_brier", "equal_case_brier", "accuracy")
    ]

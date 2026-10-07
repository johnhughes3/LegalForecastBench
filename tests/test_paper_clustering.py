"""Focused tests for the reusable case-clustering analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docs.papers.legalforecastbench.analysis import clustering


def _write_fixture(
    root: Path,
    *,
    other_outcomes: list[int] | None = None,
    other_probabilities: list[float] | None = None,
    outcomes: list[int] | None = None,
) -> Path:
    cases = ["case-a", "case-a", "case-a", "case-b", "case-b", "case-c", "case-c"]
    default_outcomes = [0, 0, 0, 1, 1, 0, 1]
    labels = outcomes or default_outcomes
    sol_probabilities = [0.05, 0.15, 0.1, 0.85, 0.9, 0.2, 0.8]
    other_values = other_probabilities or [0.1, 0.2, 0.15, 0.8, 0.85, 0.3, 0.7]
    ids = [f"unit-{index}" for index in range(len(cases))]

    def rows(probabilities: list[float], row_outcomes: list[int]) -> str:
        return "".join(
            json.dumps(
                {
                    "case_id": case_id,
                    "outcome": outcome,
                    "probability_fully_dismissed": probability,
                    "unit_id": unit_id,
                }
            )
            + "\n"
            for case_id, outcome, probability, unit_id in zip(
                cases, row_outcomes, probabilities, ids, strict=True
            )
        )

    root.mkdir(parents=True, exist_ok=True)
    (root / "sol.jsonl").write_text(rows(sol_probabilities, labels), encoding="utf-8")
    (root / "other.jsonl").write_text(
        rows(other_values, other_outcomes or labels), encoding="utf-8"
    )
    manifest = {
        "models": {"gpt-6-sol": "sol.jsonl", "other": "other.jsonl"},
        "family_model_count": 3,
        "missing_models": ["unavailable"],
    }
    inputs = root / "inputs.json"
    inputs.write_text(json.dumps(manifest), encoding="utf-8")
    return inputs


def test_known_clustering_has_pair_counts_and_shared_coverage(tmp_path: Path) -> None:
    inputs = _write_fixture(tmp_path / "relocated" / "significance")
    results = clustering.analyze(inputs, bootstrap=400, permutations=200, seed=17)

    assert results["cases"] == 3
    assert results["units"] == 7
    assert results["outcome"]["icc_anova"] == pytest.approx(0.627906976744)
    assert results["pair_counts"]["within_case_pairs"] == 5
    assert results["pair_counts"]["within_case_agree"] == 4
    assert results["pair_counts"]["within_case_equal_case_count"] == 3
    assert results["coverage"]["available_models"] == ["gpt-6-sol", "other"]
    assert results["coverage"]["missing_models"] == ["unavailable"]
    assert results["models"]["gpt-6-sol"]["brier_loss"]["icc_anova"] is not None


def test_model_label_drift_is_rejected(tmp_path: Path) -> None:
    inputs = _write_fixture(
        tmp_path / "significance", other_outcomes=[0, 0, 0, 0, 1, 0, 1]
    )
    with pytest.raises(ValueError, match="case/outcome label drift"):
        clustering.analyze(inputs, bootstrap=10, permutations=10)


def test_probability_validation_is_rejected(tmp_path: Path) -> None:
    inputs = _write_fixture(
        tmp_path / "significance",
        other_probabilities=[0.1, 0.2, 0.15, 0.8, 1.2, 0.3, 0.7],
    )
    with pytest.raises(ValueError, match=r"finite in \[0, 1\]"):
        clustering.analyze(inputs, bootstrap=10, permutations=10)


def test_constant_outcome_has_null_icc_and_reason(tmp_path: Path) -> None:
    inputs = _write_fixture(tmp_path / "significance", outcomes=[0] * 7)
    results = clustering.analyze(inputs, bootstrap=100, permutations=20)
    outcome = results["outcome"]

    assert outcome["icc_anova"] is None
    assert "constant" in outcome["undefined_reason"]
    assert outcome["case_bootstrap_ci95"] is None
    assert outcome["permutation_exceedances"] is None


def test_cli_check_detects_output_and_manuscript_drift(tmp_path: Path) -> None:
    inputs = _write_fixture(tmp_path / "significance")
    output_dir = tmp_path / "analysis"
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(
        "before\n\n"
        f"{clustering.BEGIN_MARKER}\nold generated text\n"
        f"{clustering.END_MARKER}\n"
        "\nafter\n",
        encoding="utf-8",
    )
    args = [
        "--inputs",
        str(inputs),
        "--output-dir",
        str(output_dir),
        "--bootstrap",
        "100",
        "--permutations",
        "100",
        "--manuscript",
        str(manuscript),
        "--write-manuscript",
    ]
    assert clustering.main(args) == 0
    written = manuscript.read_text(encoding="utf-8")
    assert written.startswith("before\n\n")
    assert written.endswith("\nafter\n")
    assert "old generated text" not in written
    assert "denied on procedural grounds" in written
    assert clustering.main([*args[:-1], "--check"]) == 0

    summary_path = output_dir / "summary.tex"
    summary_path.write_text(
        summary_path.read_text(encoding="utf-8") + "drift\n", encoding="utf-8"
    )
    assert clustering.main([*args[:-1], "--check"]) == 1

    summary_path.write_text(
        clustering.render_summary(
            clustering.analyze(inputs, bootstrap=100, permutations=100)
        ),
        encoding="utf-8",
    )
    manuscript.write_text(written.replace("Across", "Drifted"), encoding="utf-8")
    assert clustering.main([*args[:-1], "--check"]) == 1


def test_cli_is_portable_when_called_from_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _write_fixture(tmp_path / "inputs" / "significance")
    output_dir = tmp_path / "outputs"
    monkeypatch.chdir(tmp_path)
    assert (
        clustering.main(
            [
                "--inputs",
                str(inputs),
                "--output-dir",
                str(output_dir),
                "--bootstrap",
                "20",
                "--permutations",
                "20",
            ]
        )
        == 0
    )
    result = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert not result["source"].startswith("/")

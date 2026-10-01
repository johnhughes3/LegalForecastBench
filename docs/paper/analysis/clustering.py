"""Reproduce the case-clustering analysis used by the working paper.

The command reads the public significance manifest and its unit-level JSONL
files.  It writes a machine-readable ``results.json`` and a short paragraph
in ``summary.tex``.  No private corpus files are needed.

The default paths are resolved from this file's repository checkout, so the
command may be run from any working directory::

    python docs/paper/analysis/clustering.py

Use ``--check`` in CI to detect drift without changing generated artifacts.
``--write-manuscript`` updates only a manuscript block between the two
``% BEGIN GENERATED CLUSTERING`` and ``% END GENERATED CLUSTERING`` markers.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

BOOTSTRAP_DEFAULT = 20_000
PERMUTATIONS_DEFAULT = 20_000
SEED_DEFAULT = 2_026_0930
BEGIN_MARKER = "% BEGIN GENERATED CLUSTERING"
END_MARKER = "% END GENERATED CLUSTERING"
MARKER_BLOCK = re.compile(
    rf"(?ms)^{re.escape(BEGIN_MARKER)}[ \t]*$.*?^{re.escape(END_MARKER)}[ \t]*$"
)


def repository_root() -> Path:
    """Return the checkout root inferred from this module or the cwd."""

    starts = [Path(__file__).resolve(), Path.cwd().resolve()]
    for start in starts:
        current = start if start.is_dir() else start.parent
        for candidate in (current, *current.parents):
            if (candidate / "site" / "src" / "data" / "significance").is_dir():
                return candidate
    # This fallback keeps the module useful when copied into a fixture tree.
    return Path(__file__).resolve().parents[3]


REPOSITORY_ROOT = repository_root()
DEFAULT_INPUTS = REPOSITORY_ROOT / "site/src/data/significance/inputs.json"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Unit:
    """The fields required from one public unit-level prediction row."""

    case_id: str
    unit_id: str
    outcome: int
    probability: float


@dataclass(frozen=True)
class Dataset:
    """Canonical labels and all model predictions aligned to those labels."""

    manifest_path: Path
    units: tuple[Unit, ...]
    case_ids: tuple[str, ...]
    case_units: tuple[tuple[Unit, ...], ...]
    model_probabilities: dict[str, FloatArray]
    available_models: tuple[str, ...]
    missing_models: tuple[str, ...]
    family_model_count: int


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"input file is missing: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return cast(dict[str, Any], value)


def _read_units(path: Path) -> list[Unit]:
    units: list[Unit] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"listed model file is missing: {path}") from exc
    for row_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{row_number}: invalid JSONL") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{row_number}: expected a JSON object")
        row = cast(dict[str, Any], value)
        case_id = row.get("case_id")
        unit_id = row.get("unit_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{row_number}: case_id must be a non-empty string")
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError(f"{path}:{row_number}: unit_id must be a non-empty string")
        if unit_id in seen:
            raise ValueError(f"{path}:{row_number}: duplicate unit_id {unit_id!r}")
        seen.add(unit_id)
        outcome_value = row.get("outcome")
        if type(outcome_value) is not int or outcome_value not in (0, 1):
            raise ValueError(f"{path}:{row_number}: outcome must be exactly 0 or 1")
        probability_value = row.get("probability_fully_dismissed")
        if isinstance(probability_value, bool) or not isinstance(
            probability_value, (int, float)
        ):
            raise ValueError(f"{path}:{row_number}: probability must be numeric")
        probability = float(probability_value)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(
                f"{path}:{row_number}: probability must be finite in [0, 1]"
            )
        outcome = cast(int, outcome_value)
        units.append(Unit(case_id, unit_id, outcome, probability))
    if not units:
        raise ValueError(f"{path}: model file contains no units")
    return units


def load_dataset(inputs_path: Path) -> Dataset:
    """Load and validate a manifest and its listed model files."""

    manifest_path = inputs_path.expanduser().resolve()
    manifest = _json_object(manifest_path)
    raw_models = manifest.get("models")
    if not isinstance(raw_models, dict) or not raw_models:
        raise ValueError(f"{manifest_path}: models must be a non-empty object")
    model_files: dict[str, str] = {}
    for model_name, model_path in cast(dict[Any, Any], raw_models).items():
        if not isinstance(model_name, str) or not model_name:
            raise ValueError(f"{manifest_path}: model names must be non-empty strings")
        if not isinstance(model_path, str) or not model_path:
            raise ValueError(f"{manifest_path}: invalid path for {model_name!r}")
        model_files[model_name] = model_path
    raw_missing = manifest.get("missing_models", [])
    if not isinstance(raw_missing, list):
        raise ValueError(f"{manifest_path}: missing_models must be a list of strings")
    raw_missing_items = cast(list[Any], raw_missing)
    missing_models = tuple(
        item for item in raw_missing_items if isinstance(item, str) and item
    )
    if len(missing_models) != len(raw_missing_items) or len(set(missing_models)) != len(
        missing_models
    ):
        raise ValueError(f"{manifest_path}: invalid or duplicate missing_models")
    overlap = set(model_files) & set(missing_models)
    if overlap:
        raise ValueError(
            f"manifest lists models as both available and missing: {overlap}"
        )

    family_count_value = manifest.get(
        "family_model_count", len(model_files) + len(missing_models)
    )
    if type(family_count_value) is not int or family_count_value < len(model_files):
        raise ValueError(f"{manifest_path}: invalid family_model_count")
    family_model_count = int(family_count_value)

    loaded: dict[str, list[Unit]] = {}
    for model_name, relative_path in model_files.items():
        model_path = Path(relative_path)
        if not model_path.is_absolute():
            model_path = manifest_path.parent / model_path
        loaded[model_name] = _read_units(model_path.resolve())

    baseline_name = next(iter(model_files))
    baseline = loaded[baseline_name]
    baseline_keys = {unit.unit_id: (unit.case_id, unit.outcome) for unit in baseline}

    for model_name, units in loaded.items():
        keys = {unit.unit_id: (unit.case_id, unit.outcome) for unit in units}
        if set(keys) != set(baseline_keys):
            missing = sorted(set(baseline_keys) - set(keys))
            extra = sorted(set(keys) - set(baseline_keys))
            raise ValueError(
                f"model {model_name!r} does not have the canonical unit set "
                f"(missing={missing[:3]}, extra={extra[:3]})"
            )
        mismatches = [
            unit_id
            for unit_id in baseline_keys
            if keys[unit_id] != baseline_keys[unit_id]
        ]
        if mismatches:
            raise ValueError(
                f"model {model_name!r} has case/outcome label drift for "
                f"{mismatches[:3]}"
            )

    groups: dict[str, list[Unit]] = {}
    for unit in baseline:
        groups.setdefault(unit.case_id, []).append(unit)
    case_ids = tuple(sorted(groups))
    if len(case_ids) < 2:
        raise ValueError("clustering analysis requires at least two cases")
    case_units = tuple(tuple(groups[case_id]) for case_id in case_ids)
    if sum(len(group) * (len(group) - 1) // 2 for group in case_units) < 1:
        raise ValueError("clustering analysis requires at least one within-case pair")

    ordered_units = tuple(unit for group in case_units for unit in group)
    by_model: dict[str, FloatArray] = {}
    for model_name, units in loaded.items():
        probabilities = {unit.unit_id: unit.probability for unit in units}
        by_model[model_name] = np.asarray(
            [probabilities[unit.unit_id] for unit in ordered_units], dtype=np.float64
        )
    return Dataset(
        manifest_path=manifest_path,
        units=ordered_units,
        case_ids=case_ids,
        case_units=case_units,
        model_probabilities=by_model,
        available_models=tuple(sorted(model_files)),
        missing_models=missing_models,
        family_model_count=family_model_count,
    )


def _icc_scalar(
    ns: FloatArray, sums: FloatArray, squares: FloatArray
) -> tuple[float | None, str | None]:
    """Calculate unbalanced one-way ANOVA method-of-moments ICC."""

    clusters = len(ns)
    total = float(ns.sum())
    if clusters < 2:
        return None, "fewer than two cases"
    if total <= clusters:
        return None, "no within-case residual degrees of freedom"
    if not np.all(np.isfinite(sums)) or not np.all(np.isfinite(squares)):
        return None, "non-finite cluster moments"
    weighted_squares = (sums * sums / ns).sum()
    overall = float(sums.sum() / total)
    between = float((weighted_squares - total * overall * overall) / (clusters - 1))
    within = float((squares.sum() - weighted_squares) / (total - clusters))
    n0 = float((total - (ns * ns).sum() / total) / (clusters - 1))
    denominator = between + (n0 - 1.0) * within
    if math.isclose(
        float(squares.sum() - total * overall * overall), 0.0, abs_tol=1e-14
    ):
        return None, "constant variable has zero total variance"
    if not math.isfinite(denominator) or math.isclose(denominator, 0.0, abs_tol=1e-14):
        return None, "ICC denominator is zero or non-finite"
    value = (between - within) / denominator
    if not math.isfinite(value):
        return None, "ICC is non-finite"
    return float(value), None


def _icc_bootstrap(
    ns: FloatArray, sums: FloatArray, squares: FloatArray, draws: IntArray
) -> tuple[FloatArray, int]:
    selected_n = ns[draws]
    selected_sums = sums[draws]
    selected_squares = squares[draws]
    total = selected_n.sum(axis=1)
    clusters = selected_n.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        weighted_squares = (selected_sums * selected_sums / selected_n).sum(axis=1)
        overall = selected_sums.sum(axis=1) / total
        between = (weighted_squares - total * overall * overall) / (clusters - 1)
        within = (selected_squares.sum(axis=1) - weighted_squares) / (total - clusters)
        n0 = (total - (selected_n * selected_n).sum(axis=1) / total) / (clusters - 1)
        denominator = between + (n0 - 1.0) * within
    values = np.full(draws.shape[0], np.nan, dtype=np.float64)
    valid = np.isfinite(denominator) & ~np.isclose(denominator, 0.0, atol=1e-14)
    values[valid] = (between[valid] - within[valid]) / denominator[valid]
    valid &= np.isfinite(values)
    values[~valid] = np.nan
    return values, int((~valid).sum())


def _moments(values: FloatArray, starts: IntArray) -> tuple[FloatArray, FloatArray]:
    return np.add.reduceat(values, starts), np.add.reduceat(values * values, starts)


def _metric_summary(
    values: FloatArray,
    ns: FloatArray,
    starts: IntArray,
    draws: IntArray,
) -> dict[str, Any]:
    sums, squares = _moments(values, starts)
    point, reason = _icc_scalar(ns, sums, squares)
    bootstrap_values, undefined = _icc_bootstrap(ns, sums, squares, draws)
    finite = bootstrap_values[np.isfinite(bootstrap_values)]
    result: dict[str, Any] = {
        "icc_anova": None if point is None else round(point, 12),
        "case_bootstrap_ci95": (
            None
            if finite.size == 0
            else [
                round(float(item), 12) for item in np.quantile(finite, [0.025, 0.975])
            ]
        ),
        "case_bootstrap_ci95_condition": (
            "percentile among finite bootstrap replicates; "
            "undefined replicates excluded"
        ),
        "bootstrap_replicates": int(draws.shape[0]),
        "bootstrap_valid_replicates": int(finite.size),
        "bootstrap_undefined_replicates": undefined,
    }
    if reason is not None:
        result["undefined_reason"] = reason
    elif undefined:
        result["bootstrap_undefined_reason"] = "degenerate case resample"
    return result


def _pair_counts(outcomes: FloatArray, ns: FloatArray) -> dict[str, Any]:
    starts = np.r_[0, np.cumsum(ns, dtype=np.int64)[:-1]]
    case_sums = np.add.reduceat(outcomes, starts).astype(np.int64)
    within_pairs = int(np.sum(ns * (ns - 1) / 2))
    within_agree = int(
        np.sum(
            case_sums * (case_sums - 1) / 2
            + (ns - case_sums) * (ns - case_sums - 1) / 2
        )
    )
    total_pairs = int(len(outcomes) * (len(outcomes) - 1) // 2)
    positives = int(outcomes.sum())
    negatives = len(outcomes) - positives
    total_agree = positives * (positives - 1) // 2 + negatives * (negatives - 1) // 2
    across_pairs = total_pairs - within_pairs
    across_agree = total_agree - within_agree
    case_agreements = [
        float(
            (int(case_sum) * (int(case_sum) - 1) / 2)
            + (int(case_size - case_sum) * (int(case_size - case_sum) - 1) / 2)
        )
        / (int(case_size) * (int(case_size) - 1) / 2)
        for case_size, case_sum in zip(ns, case_sums, strict=True)
        if case_size > 1
    ]

    def fraction(count: int, total: int) -> float | None:
        return None if total == 0 else round(count / total, 12)

    return {
        "within_case_pairs": within_pairs,
        "within_case_agree": within_agree,
        "within_case_agreement": fraction(within_agree, within_pairs),
        "within_case_agreement_percent": (
            None if within_pairs == 0 else round(100 * within_agree / within_pairs, 12)
        ),
        "between_case_pairs": across_pairs,
        "between_case_agree": across_agree,
        "between_case_agreement": fraction(across_agree, across_pairs),
        "between_case_agreement_percent": (
            None if across_pairs == 0 else round(100 * across_agree / across_pairs, 12)
        ),
        "across_case_pairs": across_pairs,
        "across_case_agree": across_agree,
        "across_case_agreement": fraction(across_agree, across_pairs),
        "across_case_agreement_percent": (
            None if across_pairs == 0 else round(100 * across_agree / across_pairs, 12)
        ),
        "within_case_equal_case_count": len(case_agreements),
        "within_case_equal_case_agreement": (
            None
            if not case_agreements
            else round(sum(case_agreements) / len(case_agreements), 12)
        ),
        "within_case_equal_case_agreement_percent": (
            None
            if not case_agreements
            else round(100 * sum(case_agreements) / len(case_agreements), 12)
        ),
    }


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def analyze(
    inputs_path: Path = DEFAULT_INPUTS,
    *,
    bootstrap: int = BOOTSTRAP_DEFAULT,
    permutations: int = PERMUTATIONS_DEFAULT,
    seed: int = SEED_DEFAULT,
) -> dict[str, Any]:
    """Run the deterministic clustering analysis and return JSON-ready data."""

    if bootstrap < 1 or permutations < 1:
        raise ValueError("bootstrap and permutations must both be positive")
    dataset = load_dataset(inputs_path)
    ns = np.asarray([len(group) for group in dataset.case_units], dtype=np.float64)
    starts = np.r_[0, np.cumsum(ns, dtype=np.int64)[:-1]]
    outcomes = np.asarray([unit.outcome for unit in dataset.units], dtype=np.float64)

    # Keep this draw and operation order identical to the exploratory script:
    # all case-bootstrap indices are drawn before the permutation null.
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ns), size=(bootstrap, len(ns)), dtype=np.int64)
    outcome_summary = _metric_summary(outcomes, ns, starts, draws)
    pair_counts = _pair_counts(outcomes, ns)
    case_sums = cast(FloatArray, np.add.reduceat(outcomes, starts))
    homogeneous_multiunit_cases = sum(
        1
        for size, case_sum in zip(ns, case_sums, strict=True)
        if size > 1 and (case_sum == 0 or case_sum == size)
    )
    mixed_multiunit_cases = sum(
        1
        for size, case_sum in zip(ns, case_sums, strict=True)
        if size > 1 and 0 < case_sum < size
    )

    permutation_exceedances = 0
    permutation_undefined = 0
    observed_sums, observed_squares = _moments(outcomes, starts)
    observed_float, _ = _icc_scalar(ns, observed_sums, observed_squares)
    if observed_float is not None:
        for _ in range(permutations):
            shuffled = rng.permutation(outcomes)
            shuffled_sums, shuffled_squares = _moments(shuffled, starts)
            value, _ = _icc_scalar(ns, shuffled_sums, shuffled_squares)
            if value is None:
                permutation_undefined += 1
            elif value >= observed_float:
                permutation_exceedances += 1
    else:
        permutation_undefined = permutations

    outcome_summary["permutation_exceedances"] = (
        None if observed_float is None else permutation_exceedances
    )
    outcome_summary["permutation_p_plus_one"] = (
        None
        if observed_float is None
        else round((permutation_exceedances + 1) / (permutations + 1), 12)
    )
    outcome_summary["permutation_undefined_replicates"] = permutation_undefined

    model_results: dict[str, Any] = {}
    for model_name in dataset.available_models:
        probabilities = dataset.model_probabilities[model_name]
        signed_error = probabilities - outcomes
        brier_loss = signed_error * signed_error
        model_results[model_name] = {
            "signed_error": _metric_summary(signed_error, ns, starts, draws),
            "brier_loss": _metric_summary(brier_loss, ns, starts, draws),
        }

    model_count = len(dataset.available_models)
    return {
        "source": _portable_path(dataset.manifest_path),
        "seed": seed,
        "bootstrap_replicates": bootstrap,
        "permutations": permutations,
        "cases": len(dataset.case_ids),
        "units": len(dataset.units),
        "case_size_range": [int(ns.min()), int(ns.max())],
        "singleton_cases": sum(1 for size in ns if size == 1),
        "multiunit_cases": sum(1 for size in ns if size > 1),
        "homogeneous_multiunit_cases": homogeneous_multiunit_cases,
        "mixed_multiunit_cases": mixed_multiunit_cases,
        "outcome_dismissed": int(outcomes.sum()),
        "outcome": outcome_summary,
        "models": model_results,
        "pair_counts": pair_counts,
        # Retain the flat names used by the exploratory JSON for convenient
        # downstream readers while grouping the complete count set above.
        **pair_counts,
        "coverage": {
            "family_model_count": dataset.family_model_count,
            "available_model_count": model_count,
            "missing_model_count": len(dataset.missing_models),
            "available_models": list(dataset.available_models),
            "missing_models": list(dataset.missing_models),
            "cases": len(dataset.case_ids),
            "units": len(dataset.units),
        },
        "method_assumptions": {
            "estimator": "unbalanced one-way ANOVA method-of-moments ICC",
            "bootstrap": "percentile interval from whole-case resampling",
            "permutation_null": (
                "unit-label exchangeability across fixed case-size slots"
            ),
            "independence": (
                "Independence between cases is assumed for intervals; related-case "
                "family dependence is not assessed"
            ),
            "pair_agreement": (
                "descriptive pair counts; pairs are not independent sample sizes"
            ),
            "model_intervals": "pointwise intervals, not simultaneous comparisons",
        },
        "method_notes": [
            "Binary outcomes are analyzed on the observed 0/1 scale, not a logistic "
            "latent scale.",
            "Case bootstrap treats cases as the sampling clusters; independence "
            "between cases is assumed for intervals.",
            "The permutation null preserves total outcomes and fixed case sizes by "
            "shuffling unit labels.",
        ],
    }


def render_summary(results: dict[str, Any]) -> str:
    """Render the self-contained paragraph written to ``summary.tex``."""

    def fmt(value: Any, digits: int = 2) -> str:
        if value is None:
            return "undefined"
        return f"{float(value):.{digits}f}"

    def interval(value: list[Any] | None) -> str:
        if value is None:
            return "undefined"
        return f"{fmt(value[0])}--{fmt(value[1])}"

    outcome = cast(dict[str, Any], results["outcome"])
    ci = cast(list[Any] | None, outcome["case_bootstrap_ci95"])
    paragraph = (
        f"Across the {results['units']:,} scored units in "
        f"{results['cases']:,} cases, "
        f"the observed-scale outcome ICC was {fmt(outcome['icc_anova'])} "
        f"(95\\% CI: {interval(ci)})."
    )
    sol = cast(dict[str, Any] | None, results["models"].get("gpt-6-sol"))
    if sol is not None:
        brier = cast(dict[str, Any], sol["brier_loss"])
        brier_ci = cast(list[Any] | None, brier["case_bootstrap_ci95"])
        paragraph += (
            " Prediction losses also clustered within case because if a model "
            "failed to account, for example, for the possibility that a given "
            "motion might be denied on procedural grounds, all of the claims in "
            "a case that it expected to be dismissed could survive: "
            f"GPT-6 Sol's Brier-loss ICC was {fmt(brier['icc_anova'])} "
            f"(95\\% CI: {interval(brier_ci)})."
        )
    paragraph += (
        f" These intervals use {results['bootstrap_replicates']:,} whole-case "
        "bootstrap resamples, and assume independent between cases."
    )
    return paragraph + "\n"


def _manuscript_block(text: str) -> str:
    matches = list(MARKER_BLOCK.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"manuscript must contain exactly one {BEGIN_MARKER} / {END_MARKER} block"
        )
    return matches[0].group(0)


def replace_manuscript_block(manuscript: Path, summary: str) -> None:
    """Replace only the marked generated paragraph in a manuscript."""

    text = manuscript.read_text(encoding="utf-8")
    matches = list(MARKER_BLOCK.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"manuscript must contain exactly one {BEGIN_MARKER} / {END_MARKER} block"
        )
    replacement = f"{BEGIN_MARKER}\n{summary.rstrip()}\n{END_MARKER}"
    manuscript.write_text(
        text[: matches[0].start()] + replacement + text[matches[0].end() :],
        encoding="utf-8",
    )


def _check_manuscript(manuscript: Path, summary: str) -> bool:
    text = manuscript.read_text(encoding="utf-8")
    block = _manuscript_block(text)
    expected = f"{BEGIN_MARKER}\n{summary.rstrip()}\n{END_MARKER}"
    return block == expected


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_DEFAULT)
    parser.add_argument("--permutations", type=int, default=PERMUTATIONS_DEFAULT)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument(
        "--check", action="store_true", help="check outputs without writing"
    )
    parser.add_argument(
        "--manuscript", type=Path, help="check or update a marked manuscript block"
    )
    parser.add_argument(
        "--write-manuscript",
        action="store_true",
        help="replace only the marked clustering block in --manuscript",
    )
    args = parser.parse_args(argv)
    if args.write_manuscript and args.manuscript is None:
        parser.error("--write-manuscript requires --manuscript")
    if args.write_manuscript and args.check:
        parser.error("--write-manuscript cannot be combined with --check")
    try:
        results = analyze(
            args.inputs,
            bootstrap=args.bootstrap,
            permutations=args.permutations,
            seed=args.seed,
        )
        summary = render_summary(results)
        results_path = args.output_dir / "results.json"
        summary_path = args.output_dir / "summary.tex"
        mismatches: list[str] = []
        if args.check:
            expected_json = (
                json.dumps(
                    results,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )
            if (
                not results_path.exists()
                or results_path.read_text(encoding="utf-8") != expected_json
            ):
                mismatches.append(str(results_path))
            if (
                not summary_path.exists()
                or summary_path.read_text(encoding="utf-8") != summary
            ):
                mismatches.append(str(summary_path))
        else:
            _write_json(results_path, results)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary, encoding="utf-8")
        if args.manuscript is not None:
            if args.write_manuscript:
                replace_manuscript_block(args.manuscript, summary)
            elif not _check_manuscript(args.manuscript, summary):
                mismatches.append(f"{args.manuscript} (generated clustering block)")
        if mismatches:
            print("clustering artifacts differ:", file=sys.stderr)
            for mismatch in mismatches:
                print(f"- {mismatch}", file=sys.stderr)
            return 1
        print("clustering analysis is reproducible")
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"clustering analysis failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

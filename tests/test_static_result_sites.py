from __future__ import annotations

import hashlib
import json
import math
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.evals.bootstrap import ModelScoreInput, paired_clustered_bootstrap
from legalforecast.evals.output_parser import ParserStatus
from legalforecast.evals.scorers import UnitScore
from legalforecast.publication.official_report_validation import (
    _validate_model_summary,
)
from legalforecast.publication.publication_guardrails import PublicationGuardrailError
from legalforecast.publication.static_sites import (
    render_community_results_site,
    render_official_results_site,
)

JsonRecord = dict[str, Any]


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value is not None:
                self.hrefs.append(value)


def test_official_results_site_fails_closed_without_canonical_bundle(
    tmp_path: Path,
) -> None:
    official_dir = tmp_path / "official"
    _write_json(
        official_dir / "scores.json",
        {
            "rows": [
                {
                    "model_id": "official-model",
                    "micro_brier": 0.123,
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="canonical official artifact is missing"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "official-site",
        )


def test_official_results_site_renders_the_cycle_one_reader_contract(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    output_dir = tmp_path / "official-site"

    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=output_dir,
    )

    rendered = result.index_path.read_text(encoding="utf-8")
    css = (output_dir / "assets" / "site.css").read_text(encoding="utf-8")
    run_card = _read_json(official_dir / "run-cards" / "aggregate-run-card.json")
    scores = _read_json(official_dir / "scores.json")
    score_rows = cast(list[JsonRecord], scores["summaries"])
    evaluated_rows = [row for row in score_rows if row["row_type"] == "model"]
    assert {row["solver_id"] for row in evaluated_rows} == set(
        cast(list[str], run_card["expected_model_keys"])
    )
    assert {row["model_id"] for row in evaluated_rows} != set(
        cast(list[str], run_card["expected_model_keys"])
    )
    assert "<html lang='en'>" in rendered
    assert "<title>Cycle 1 fixture report | LegalForecastBench</title>" in rendered
    assert "href='#main-content'" in rendered
    assert "<main id='main-content'>" in rendered
    assert "Official evidence tier" in rendered
    assert "Official and community results are published separately" in rendered
    assert "model-a" in rendered
    assert "0.0880" in rendered
    assert "Paired micro-Brier difference intervals" in rendered
    assert "Delta vs best (95% CI)" in rendered
    assert "N cases" in rendered
    assert "N units" in rendered
    assert "Provider / snapshot" in rendered
    assert "Expected calibration error" in rendered
    assert "Calibration bins for model-a" in rendered
    assert "Mean forecast" in rendered
    assert "Observed rate" in rendered
    assert "0.0400" in rendered
    assert "Invalid outputs" in rendered
    assert "0.00%" in rendered
    assert "Refusals" in rendered
    assert "Realized prevalence" in rendered
    assert "40.00%" in rendered
    assert "global_base_rate" in rendered
    assert "Cost per case" in rendered
    assert "$0.0500" in rendered
    assert "Tokens" in rendered
    assert "Latency" in rendered
    assert "Official" in rendered
    assert "reduces temporal contamination risk; it does not prove immunity" in rendered
    assert "Limitations" in rendered
    assert "Descriptive fixture result only." in rendered
    assert "LegalForecastBench is an independent project" in rendered
    assert "<caption>Evaluated model results</caption>" in rendered
    assert "<caption>Frozen empirical baseline context</caption>" in rendered
    assert "scope='col'" in rendered
    assert "aria-label='Report navigation'" in rendered
    assert "role='region' tabindex='0'" in rendered
    assert "Scroll horizontally to inspect all columns." in rendered
    assert "@media (max-width: 720px)" in css
    assert "overflow-x: auto" in css
    assert ":focus-visible" in css

    links = _LinkCollector()
    links.feed(rendered)
    assert "../official/report/leaderboard.html" in links.hrefs
    assert "../official/run-cards/aggregate-run-card.json" in links.hrefs
    assert "../official/unit-scores.jsonl" in links.hrefs
    assert "../official/artifact-index.json" in links.hrefs
    assert "artifact-index.json" in links.hrefs
    assert (
        "https://github.com/johnhughes3/LegalForecastBench/blob/main/docs/METHODS.md"
        in links.hrefs
    )
    for href in links.hrefs:
        if href.startswith("#"):
            assert f"id='{href[1:]}'" in rendered
            continue
        if href.startswith("https://"):
            continue
        assert not href.startswith("http://")
        assert (output_dir / href).resolve().is_file()


def test_official_results_site_does_not_imply_skill_without_frozen_baseline(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path, include_baseline=False)

    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "site",
    )

    rendered = result.index_path.read_text(encoding="utf-8")
    assert "No frozen empirical baseline is present" in rendered
    assert "no Brier skill claim is shown" in rendered
    assert "Brier skill score" not in rendered


def test_official_results_site_rejects_public_arithmetic_drift(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    leaderboard_path = official_dir / "report" / "leaderboard.json"
    leaderboard = _read_json(leaderboard_path)
    rows = cast(list[JsonRecord], leaderboard["rows"])
    rows[0]["micro_brier"] = 0.13
    _write_json(leaderboard_path, leaderboard)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="micro-Brier mismatch for model-a"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("run_type", "community", "run_type=official"),
        ("allow_incomplete_model_set", True, "incomplete model sets"),
        ("expected_matrix_rows", 99, "expected model matrix"),
    ],
)
def test_official_results_site_rejects_nonofficial_or_incomplete_run_cards(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "run-cards" / "aggregate-run-card.json"
    run_card = _read_json(path)
    run_card[field] = value
    _write_json(path, run_card)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match=message):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_rejects_cycle_provenance_and_manifest_drift(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    scores_path = official_dir / "scores.json"
    scores = _read_json(scores_path)
    scores["cycle_id"] = "different-cycle"
    _write_json(scores_path, scores)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="cycle_id mismatch"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )

    write_official_report_fixture(tmp_path)
    _write_json(
        official_dir / "artifact-manifest.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "artifacts": [],
        },
    )
    with pytest.raises(ValueError, match="artifact manifest"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site-2",
        )


def test_official_results_site_requires_exact_100_for_cycle_one(tmp_path: Path) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    for relative in (
        "report/leaderboard.json",
        "scores.json",
        "run-cards/aggregate-run-card.json",
        "cycle-power.json",
    ):
        path = official_dir / relative
        record = _read_json(path)
        record["cycle_id"] = "cycle-1-2026-06-30"
        nested_cycle_power = record.get("cycle_power")
        if isinstance(nested_cycle_power, dict):
            nested_cycle_power["cycle_id"] = "cycle-1-2026-06-30"
        _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="exactly 100 cases"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_does_not_treat_cycle_ten_as_cycle_one(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    for relative in (
        "report/leaderboard.json",
        "scores.json",
        "run-cards/aggregate-run-card.json",
        "cycle-power.json",
    ):
        path = official_dir / relative
        record = _read_json(path)
        record["cycle_id"] = "cycle-10"
        nested_cycle_power = record.get("cycle_power")
        if isinstance(nested_cycle_power, dict):
            nested_cycle_power["cycle_id"] = "cycle-10"
        _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)

    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "site",
    )

    assert result.index_path.is_file()


def test_official_summary_validation_accepts_homogeneous_outcomes() -> None:
    records = [
        _fixture_unit_score(
            model_id="model-a",
            index=index,
            probability=1.0,
            outcome=1,
        )
        for index in (1, 2)
    ]
    scores = tuple(_unit_score_from_record(record) for record in records)
    summary = {
        "case_count": 2,
        "unit_count": 2,
        "micro_brier": 0.0,
        "macro_brier": 0.0,
        "log_loss": scores[0].log_loss,
        "base_rate": 1.0,
        "base_rate_brier": 0.0,
        "brier_skill_score": 0.0,
        "invalid_output_rate": 0.0,
        "refusal_rate": 0.0,
        "defaulted_prediction_rate": 0.0,
        "ece": 0.0,
        "ece_bins": [
            {
                "bin_index": 0,
                "lower": 0.0,
                "upper": 1.0,
                "unit_count": 2,
                "mean_probability": 1.0,
                "observed_rate": 1.0,
                "absolute_calibration_error": 0.0,
            }
        ],
    }

    _validate_model_summary(
        "model-a",
        summary,
        scores,
        prevalence=1.0,
        expected_case_count=2,
        expected_unit_count=2,
    )


def test_official_results_site_rejects_invented_baseline_reference(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "run-cards" / "aggregate-run-card.json"
    run_card = _read_json(path)
    run_card["brier_skill_score_reference_model_id"] = "invented-baseline"
    _write_json(path, run_card)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="baseline reference"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_does_not_link_unindexed_artifacts(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    (official_dir / "unindexed-private-debug.txt").write_text(
        "not part of the public release bundle\n",
        encoding="utf-8",
    )
    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "site",
    )

    links = _LinkCollector()
    links.feed(result.index_path.read_text(encoding="utf-8"))
    assert all("unindexed-private-debug" not in href for href in links.hrefs)


def test_official_results_site_binds_frozen_models_to_evaluated_solvers(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "run-cards" / "aggregate-run-card.json"
    run_card = _read_json(path)
    run_card["expected_model_keys"] = ["unrelated-a", "unrelated-b"]
    run_card["registry_model_keys"] = ["unrelated-a", "unrelated-b"]
    _write_json(path, run_card)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="evaluated score-summary solvers"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_rejects_unknown_row_types(tmp_path: Path) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    for relative, collection in (
        ("report/leaderboard.json", "rows"),
        ("scores.json", "summaries"),
    ):
        path = official_dir / relative
        record = _read_json(path)
        rows = cast(list[JsonRecord], record[collection])
        rows[0]["row_type"] = "community"
        _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="unsupported official row_type=community"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


@pytest.mark.parametrize(
    ("model_id", "message"),
    [
        ("model-a", "best model row"),
        ("global_base_rate", "baseline rows"),
    ],
)
def test_official_results_site_rejects_intervals_on_best_or_baseline_rows(
    tmp_path: Path,
    model_id: str,
    message: str,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "report" / "leaderboard.json"
    report = _read_json(path)
    rows = cast(list[JsonRecord], report["rows"])
    row = next(item for item in rows if item["model_id"] == model_id)
    row.update(
        {
            "delta_vs_best": 0.123,
            "delta_vs_best_ci_low": 0.1,
            "delta_vs_best_ci_high": 0.2,
        }
    )
    _write_json(path, report)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match=message):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_binds_scored_case_and_unit_counts(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    run_card_path = official_dir / "run-cards" / "aggregate-run-card.json"
    run_card = _read_json(run_card_path)
    run_card["case_count"] = 6
    run_card["expected_matrix_rows"] = 12
    _write_json(run_card_path, run_card)
    for relative in ("report/leaderboard.json", "cycle-power.json"):
        path = official_dir / relative
        record = _read_json(path)
        cycle_power = cast(JsonRecord, record["cycle_power"])
        cycle_power["clean_motion_count"] = 6
        _write_json(path, record)
    run_card["cycle_power"] = _read_json(official_dir / "cycle-power.json")[
        "cycle_power"
    ]
    _write_json(run_card_path, run_card)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="scored case set"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )

    official_dir = write_official_report_fixture(tmp_path)
    for relative in (
        "report/leaderboard.json",
        "run-cards/aggregate-run-card.json",
        "cycle-power.json",
    ):
        path = official_dir / relative
        record = _read_json(path)
        cycle_power = cast(JsonRecord, record["cycle_power"])
        cycle_power["prediction_unit_count"] = 6
        _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)
    with pytest.raises(ValueError, match="scored unit set"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site-2",
        )

    official_dir = write_official_report_fixture(tmp_path)
    unit_scores_path = official_dir / "unit-scores.jsonl"
    records = unit_scores_path.read_text(encoding="utf-8").splitlines()
    unit_scores_path.write_text("\n".join([*records, records[0]]) + "\n", "utf-8")
    _refresh_official_artifact_manifests(official_dir)
    with pytest.raises(ValueError, match="duplicate public unit score"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site-3",
        )


def test_official_results_site_reconstructs_public_accounting_ratios(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    for relative, collection in (
        ("report/leaderboard.json", "rows"),
        ("scores.json", "summaries"),
    ):
        path = official_dir / relative
        record = _read_json(path)
        rows = cast(list[JsonRecord], record[collection])
        rows[0]["cost_per_case"] = 999.0
        rows[0]["cost_per_prediction_unit"] = 999.0
        _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="cost_per_case mismatch"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_binds_cycle_power_claims_across_artifacts(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "cycle-power.json"
    record = _read_json(path)
    cycle_power = cast(JsonRecord, record["cycle_power"])
    cycle_power["claim_strength"] = "Universal ranking claim permitted."
    _write_json(path, record)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="cycle-power records differ"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_validates_and_displays_baseline_training_evidence(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "run-cards" / "aggregate-run-card.json"
    run_card = _read_json(path)
    run_card["cycle_baseline_training_example_count"] = 999
    _write_json(path, run_card)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="declared baseline training count"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )

    official_dir = write_official_report_fixture(tmp_path)
    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "site-2",
    )
    rendered = result.index_path.read_text(encoding="utf-8")
    assert (
        "Frozen historical training period: 2024-01-01 through 2024-12-31" in rendered
    )
    assert "Public cycle baseline evidence rows: 5" in rendered


@pytest.mark.parametrize("collection", ["pairwise_deltas", "calibration_tables"])
def test_official_results_site_rejects_duplicate_display_records(
    tmp_path: Path,
    collection: str,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    path = official_dir / "report" / "leaderboard.json"
    report = _read_json(path)
    records = cast(list[JsonRecord], report[collection])
    forged = dict(records[0])
    if collection == "pairwise_deltas":
        forged.update({"observed_delta": 99.0, "ci_low": 98.0, "ci_high": 100.0})
    else:
        forged["ece"] = 0.999
    records.insert(0, forged)
    _write_json(path, report)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="duplicate"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )


def test_official_results_site_reconstructs_brier_and_intervals(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    unit_scores_path = official_dir / "unit-scores.jsonl"
    records = [json.loads(line) for line in unit_scores_path.read_text().splitlines()]
    records[0]["brier"] = 0.99
    unit_scores_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="reconstructed Brier mismatch"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site",
        )

    official_dir = write_official_report_fixture(tmp_path)
    leaderboard_path = official_dir / "report" / "leaderboard.json"
    leaderboard = _read_json(leaderboard_path)
    deltas = cast(list[JsonRecord], leaderboard["pairwise_deltas"])
    deltas[0]["ci_low"] = -0.99
    _write_json(leaderboard_path, leaderboard)
    _refresh_official_artifact_manifests(official_dir)

    with pytest.raises(ValueError, match="bootstrap interval mismatch"):
        render_official_results_site(
            official_artifacts_dir=official_dir,
            output_dir=tmp_path / "site-2",
        )


def test_official_results_site_meets_semantic_and_contrast_contract(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    output_dir = tmp_path / "site"
    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=output_dir,
    )
    rendered = result.index_path.read_text(encoding="utf-8")

    assert rendered.count("<main ") == 1
    assert rendered.count("<h1>") == 1
    assert rendered.count("<nav ") == 1
    assert "<caption>Evaluated model results</caption>" in rendered
    assert "<caption>Calibration bins for model-a</caption>" in rendered
    assert "<th scope='row'>" in rendered
    assert "<th scope='col'>" in rendered
    assert "aria-labelledby=" in rendered
    assert "aria-label='Report navigation'" in rendered

    assert _contrast_ratio("#17202a", "#ffffff") >= 4.5
    assert _contrast_ratio("#5d6975", "#ffffff") >= 4.5
    assert _contrast_ratio("#075f57", "#ffffff") >= 4.5


def test_community_results_site_uses_non_official_sections(tmp_path: Path) -> None:
    aggregate_dir = _write_community_aggregate(tmp_path)
    output_dir = aggregate_dir / "site"

    render_community_results_site(
        community_aggregate_dir=aggregate_dir,
        output_dir=output_dir,
    )

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "LegalForecastBench Community Harness Comparisons" in html
    assert "non-official community results" in html.lower()
    assert "Harvey LAB (lab_native)" in html
    assert "LegalForecastBench/LFB (lfb_brier)" in html
    assert "Adapter and Conformance Cards" in html
    assert "Conformance (self-reported)" in html
    assert "passed (self-reported)" in html
    assert "Coverage matrices and shard/composite views" in html
    assert "Official Results" not in html
    assert "href='../reports/community-comparison.json'" in html
    assert "href='reports/community-comparison.json'" not in html


def test_static_site_guardrails_reject_secret_content(tmp_path: Path) -> None:
    aggregate_dir = _write_community_aggregate(tmp_path)
    _write_json(
        aggregate_dir / "registry" / "site-summary.json",
        {
            "rows": [
                {
                    "row_id": "leaky",
                    "row_type": "single-shard",
                    "family": "harvey_lab",
                    "scoring_mode": "lab_native",
                    "adapter_id": "fixture",
                    "model_key": "OPENAI_API_KEY=sk-secretsecret",
                }
            ]
        },
    )

    with pytest.raises(PublicationGuardrailError, match="secret"):
        render_community_results_site(
            community_aggregate_dir=aggregate_dir,
            output_dir=tmp_path / "community-site",
        )


def _write_community_aggregate(tmp_path: Path) -> Path:
    aggregate_dir = tmp_path / "community-aggregate"
    rows = [
        {
            "row_id": "lab-submission:shard-001",
            "row_type": "single-shard",
            "submission_ids": ["lab-submission"],
            "shard_ids": ["shard-001"],
            "family": "harvey_lab",
            "scoring_mode": "lab_native",
            "selection_sha256": "sha256:" + "1" * 64,
            "selection_label": "fixture-selection",
            "suite_version": "harvey-lab-fixture",
            "adapter_id": "fixture-cli",
            "adapter_version": "0.1.0",
            "model_key": "fixture-model",
            "conformance_status": "passed",
            "task_count": 1,
            "coverage_percentage": 50.0,
        },
        {
            "row_id": "lfb-submission:shard-001",
            "row_type": "single-shard",
            "submission_ids": ["lfb-submission"],
            "shard_ids": ["shard-001"],
            "family": "legalforecast_mtd",
            "scoring_mode": "lfb_brier",
            "selection_sha256": "sha256:" + "2" * 64,
            "selection_label": "fixture-selection",
            "suite_version": "lfb-fixture",
            "adapter_id": "fixture-cli",
            "adapter_version": "0.1.0",
            "model_key": "fixture-model",
            "conformance_status": "passed",
            "task_count": 1,
            "coverage_percentage": 100.0,
        },
    ]
    _write_json(
        aggregate_dir / "registry" / "site-summary.json",
        {
            "schema_version": (
                "legalforecast.multiharness.community_aggregate_bundle.v1"
            ),
            "submission_count": 2,
            "row_count": 2,
            "families": ["harvey_lab", "legalforecast_mtd"],
            "scoring_modes": ["lab_native", "lfb_brier"],
            "rows": rows,
            "compatible_shard_groups": [],
        },
    )
    _write_json(
        aggregate_dir / "reports" / "community-comparison.json",
        {"rows": rows},
    )
    return aggregate_dir


def write_official_report_fixture(
    tmp_path: Path,
    *,
    include_baseline: bool = True,
) -> Path:
    official_dir = tmp_path / "official"
    cycle_id = "fixture-cycle"
    cycle_power_record = {
        "cycle_id": cycle_id,
        "series": "official",
        "clean_motion_count": 5,
        "prediction_unit_count": 5,
        "claim_strength": "Descriptive fixture result only.",
        "warnings": ["Fixture intervals are not publication evidence."],
    }
    outcomes = (1, 1, 0, 0, 0)
    probabilities = {
        "model-a": (0.8, 0.6, 0.4, 0.2, 0.2),
        "model-b": (0.7, 0.5, 0.3, 0.3, 0.3),
        **({"global_base_rate": (0.4,) * 5} if include_baseline else {}),
    }
    unit_records = [
        _fixture_unit_score(
            model_id=model_id,
            index=index,
            probability=probability,
            outcome=outcome,
        )
        for model_id, model_probabilities in probabilities.items()
        for index, (probability, outcome) in enumerate(
            zip(model_probabilities, outcomes, strict=True),
            start=1,
        )
    ]
    score_rows = [
        _fixture_score_summary(
            model_id,
            [record for record in unit_records if record["model_id"] == model_id],
            row_type=("baseline" if model_id == "global_base_rate" else "model"),
        )
        for model_id in probabilities
    ]
    inference = paired_clustered_bootstrap(
        tuple(
            ModelScoreInput(
                model_id=model_id,
                unit_scores=tuple(
                    _unit_score_from_record(record)
                    for record in unit_records
                    if record["model_id"] == model_id
                ),
            )
            for model_id in probabilities
        )
    )
    report_rows: list[JsonRecord] = []
    for rank, score_row in enumerate(score_rows, start=1):
        model_id = cast(str, score_row["model_id"])
        row = {
            key: score_row[key]
            for key in (
                "model_id",
                "row_type",
                "micro_brier",
                "brier_skill_score",
                "log_loss",
                "ece",
                "macro_brier",
                "capped_case_micro_brier",
                "related_family_capped_micro_brier",
                "mdl_family_capped_micro_brier",
                "invalid_output_rate",
                "refusal_rate",
                "defaulted_prediction_rate",
                "cost_per_case",
                "cost_per_prediction_unit",
                "mean_tool_calls_per_case",
                "p95_tool_calls_per_case",
                "mean_latency_ms",
                "p95_latency_ms",
            )
        }
        row.update({"rank": rank, "rank_tier": None})
        if model_id == "model-b":
            delta = next(
                item
                for item in inference.pairwise_deltas
                if {item.model_a, item.model_b} == {"model-a", "model-b"}
            )
            direction = 1.0 if delta.model_a == "model-b" else -1.0
            row.update(
                {
                    "delta_vs_best": direction * delta.observed_delta,
                    "delta_vs_best_ci_low": (
                        delta.ci_low if direction > 0 else -delta.ci_high
                    ),
                    "delta_vs_best_ci_high": (
                        delta.ci_high if direction > 0 else -delta.ci_low
                    ),
                }
            )
        else:
            row.update(
                {
                    "delta_vs_best": None,
                    "delta_vs_best_ci_low": None,
                    "delta_vs_best_ci_high": None,
                }
            )
        report_rows.append(row)
    _write_json(
        official_dir / "report" / "leaderboard.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "title": "Cycle 1 fixture report",
            "cycle_id": cycle_id,
            "cycle_power": cycle_power_record,
            "rows": report_rows,
            "pairwise_deltas": [
                delta.to_record() for delta in inference.pairwise_deltas
            ],
            "calibration_tables": [
                {
                    "model_id": row["model_id"],
                    "ece": row["ece"],
                    "bins": row["ece_bins"],
                }
                for row in score_rows
            ],
            "calibration_plot_svg": (
                '<svg role="img" aria-label="Calibration reliability plot"></svg>'
            ),
            "rank_tier_caveat": "Fixture interval caveat.",
            "small_cluster_warning": None,
        },
    )
    _write_json(
        official_dir / "scores.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "cycle_id": cycle_id,
            "summaries": score_rows,
        },
    )
    baseline_ids = ["global_base_rate"] if include_baseline else []
    _write_json(
        official_dir / "run-cards" / "aggregate-run-card.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "cycle_id": cycle_id,
            "run_type": "official",
            "model_keys": ["fixture:model-a", "fixture:model-b"],
            "registry_model_keys": ["fixture:model-a", "fixture:model-b"],
            "expected_model_keys": ["fixture:model-a", "fixture:model-b"],
            "allow_incomplete_model_set": False,
            "allow_no_baselines": not include_baseline,
            "expected_matrix_rows": 10,
            "case_count": 5,
            "ablation_count": 1,
            "model_count": len(score_rows),
            "accounting_record_count": 5 * len(score_rows),
            "labels_sha256": "sha256:" + "a" * 64,
            "baseline_model_ids": baseline_ids,
            "baseline_training_period": (
                {
                    "training_period_start": "2024-01-01",
                    "training_period_end": "2024-12-31",
                    "judge_history_usage": json.dumps(
                        {
                            "unit_count": 5,
                            "judge_prior_units": 5,
                            "court_or_district_fallback_units": 0,
                            "global_fallback_units": 0,
                        },
                        sort_keys=True,
                    ),
                }
                if include_baseline
                else None
            ),
            "cycle_baseline_training_example_count": 5 if include_baseline else 0,
            "brier_skill_score_reference_model_id": (
                "global_base_rate" if include_baseline else None
            ),
            "cycle_power": cycle_power_record,
            "notes": ["Fixture public aggregate."],
        },
    )
    _write_json(
        official_dir / "cycle-power.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "cycle_id": cycle_id,
            "cycle_power": cycle_power_record,
        },
    )
    (official_dir / "unit-scores.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in unit_records),
        encoding="utf-8",
    )
    (official_dir / "report" / "leaderboard.html").write_text(
        "<!doctype html><title>Audit table</title>",
        encoding="utf-8",
    )
    if include_baseline:
        (official_dir / "baseline-training-examples.jsonl").write_text(
            "".join(
                json.dumps(_fixture_baseline_training_example(index), sort_keys=True)
                + "\n"
                for index in range(1, 6)
            ),
            encoding="utf-8",
        )
    _refresh_official_artifact_manifests(official_dir)
    return official_dir


def _fixture_baseline_training_example(index: int) -> JsonRecord:
    return {
        "features": {
            "unit_id": f"unit-{index}",
            "case_id": f"case-{index}",
            "court": "Fixture Court",
            "district": "Fixture District",
            "circuit": "Fixture Circuit",
            "nos_macro_category": "civil",
            "motion_type": "motion_to_dismiss",
            "judge_id": f"judge-{index}",
            "represented_party_status": None,
            "government_party_status": None,
            "claim_count": 1,
            "defendant_count": 1,
            "motion_length_tokens": 100,
            "complaint_length_tokens": 200,
            "case_age_days": 30,
            "docket_entry_count": 10,
        },
        "fully_dismissed": index <= 2,
        "decision_date": "2026-05-17",
    }


def _fixture_unit_score(
    *,
    model_id: str,
    index: int,
    probability: float,
    outcome: int,
) -> JsonRecord:
    bounded = min(max(probability, 1e-15), 1 - 1e-15)
    return {
        "case_id": f"case-{index}",
        "candidate_id": f"candidate-{index}",
        "related_family_id": None,
        "mdl_family_id": None,
        "unit_id": f"unit-{index}",
        "model_id": model_id,
        "probability_fully_dismissed": probability,
        "outcome": outcome,
        "brier": (probability - outcome) ** 2,
        "log_loss": -(
            outcome * math.log(bounded) + (1 - outcome) * math.log(1 - bounded)
        ),
        "parser_status": "valid",
        "raw_output_sha256": "0" * 64,
        "defaulted_prediction": False,
        "invalid_reason": None,
        "label_confidence": 1.0,
    }


def _unit_score_from_record(record: JsonRecord) -> UnitScore:
    return UnitScore(
        case_id=cast(str, record["case_id"]),
        candidate_id=cast(str, record["candidate_id"]),
        related_family_id=None,
        mdl_family_id=None,
        model_id=cast(str, record["model_id"]),
        unit_id=cast(str, record["unit_id"]),
        probability_fully_dismissed=cast(float, record["probability_fully_dismissed"]),
        outcome=cast(int, record["outcome"]),
        brier=cast(float, record["brier"]),
        log_loss=cast(float, record["log_loss"]),
        parser_status=ParserStatus.VALID,
        raw_output_sha256=cast(str, record["raw_output_sha256"]),
        defaulted_prediction=False,
        invalid_reason=None,
        label_confidence=1.0,
    )


def _fixture_score_summary(
    model_id: str,
    records: list[JsonRecord],
    *,
    row_type: str,
) -> JsonRecord:
    micro_brier = sum(cast(float, record["brier"]) for record in records) / len(records)
    log_loss = sum(cast(float, record["log_loss"]) for record in records) / len(records)
    mean_probability = sum(
        cast(float, record["probability_fully_dismissed"]) for record in records
    ) / len(records)
    observed_rate = sum(cast(int, record["outcome"]) for record in records) / len(
        records
    )
    ece = abs(mean_probability - observed_rate)
    base_rate_brier = 0.24
    is_baseline = row_type == "baseline"
    total_cost = 0.0 if is_baseline else 0.25
    tool_call_count = 0 if is_baseline else 10
    return {
        "model_id": model_id,
        "row_type": row_type,
        "case_count": 5,
        "unit_count": 5,
        "micro_brier": micro_brier,
        "macro_brier": micro_brier,
        "brier_skill_score": 1 - (micro_brier / base_rate_brier),
        "log_loss": log_loss,
        "ece": ece,
        "capped_case_micro_brier": micro_brier,
        "related_family_capped_micro_brier": micro_brier,
        "mdl_family_capped_micro_brier": micro_brier,
        "case_unit_cap": 10,
        "family_unit_cap": 20,
        "dominance_threshold": 0.25,
        "dominance_sensitivity_reports": [],
        "invalid_output_rate": 0.0,
        "refusal_rate": 0.0,
        "defaulted_prediction_rate": 0.0,
        "base_rate": 0.4,
        "base_rate_brier": base_rate_brier,
        "ece_bins": [
            {
                "bin_index": 0,
                "lower": 0.0,
                "upper": 1.0,
                "unit_count": 5,
                "mean_probability": mean_probability,
                "observed_rate": observed_rate,
                "absolute_calibration_error": ece,
            }
        ],
        "unit_scores": records,
        "solver_id": (
            f"fixture:{model_id}" if not is_baseline else f"baseline:{model_id}"
        ),
        "provider": "legalforecast-baseline" if is_baseline else "fixture-provider",
        "model_version_or_snapshot": "2026-07-16",
        "run_label": "full_packet",
        "run_count": 5,
        "request_count": 5,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
        "tool_call_count": tool_call_count,
        "allowed_tool_call_count": tool_call_count,
        "denied_tool_call_count": 0,
        "mean_tool_calls_per_case": tool_call_count / 5,
        "median_tool_calls_per_case": 0.0 if is_baseline else 2.0,
        "p95_tool_calls_per_case": 0.0 if is_baseline else 2.0,
        "mean_latency_ms": 1000.0,
        "p95_latency_ms": 1200.0,
        "total_estimated_cost": total_cost,
        "cost_per_case": total_cost / 5,
        "cost_per_prediction_unit": total_cost / 5,
        "content_filter_rate": 0.0,
    }


def _refresh_official_artifact_manifests(official_dir: Path) -> None:
    paths = sorted(
        path.relative_to(official_dir).as_posix()
        for path in official_dir.rglob("*")
        if path.is_file()
        and path.name not in {"artifact-index.json", "artifact-manifest.json"}
    )
    _write_json(
        official_dir / "artifact-index.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "artifact_count": len(paths),
            "artifacts": [
                {
                    "path": relative,
                    "sha256": hashlib.sha256(
                        (official_dir / relative).read_bytes()
                    ).hexdigest(),
                    "size_bytes": (official_dir / relative).stat().st_size,
                    "bundle_role": "fixture",
                }
                for relative in paths
            ],
        },
    )
    _write_json(
        official_dir / "artifact-manifest.json",
        {
            "schema_version": "legalforecast-official-aggregate-v1",
            "artifacts": paths,
        },
    )


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        components = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            component / 12.92
            if component <= 0.04045
            else ((component + 0.055) / 1.055) ** 2.4
            for component in components
        ]
        return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2])

    first, second = sorted(
        (luminance(foreground), luminance(background)),
        reverse=True,
    )
    return (first + 0.05) / (second + 0.05)


def _write_json(path: Path, payload: JsonRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text("utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)

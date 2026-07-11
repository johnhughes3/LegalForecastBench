from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.publication.publication_guardrails import PublicationGuardrailError
from legalforecast.publication.static_sites import (
    render_community_results_site,
    render_official_results_site,
)

JsonRecord = dict[str, Any]


def test_official_results_site_uses_official_only_copy(tmp_path: Path) -> None:
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
    _write_json(official_dir / "run-cards" / "cycle.json", {"cycle": "official"})
    output_dir = tmp_path / "official-site"

    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=output_dir,
    )

    html = result.index_path.read_text(encoding="utf-8")
    assert "LegalForecastBench Official Results" in html
    assert "protected LegalForecastBench evaluation workflow" in html
    assert "official-model" in html
    assert "Community Harness" not in html
    assert "non-official community" not in html.lower()
    assert (output_dir / "assets" / "site.css").is_file()
    assert _read_json(output_dir / "artifact-index.json")["artifacts"]


def test_official_results_site_reads_current_aggregate_score_summaries(
    tmp_path: Path,
) -> None:
    official_dir = tmp_path / "official"
    _write_json(
        official_dir / "scores.json",
        {
            "summaries": [
                {
                    "model_id": "current-aggregate-model",
                    "micro_brier": 0.08,
                }
            ]
        },
    )

    result = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "site",
    )

    rendered = result.index_path.read_text(encoding="utf-8")
    assert "current-aggregate-model" in rendered
    assert "0.08" in rendered
    assert "No official score rows" not in rendered


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


def _write_json(path: Path, payload: JsonRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text("utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)

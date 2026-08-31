from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from legalforecast.cli import main

MODULES = [
    "legalforecast.ingestion",
    "legalforecast.ingestion.canonical_json",
    "legalforecast.ingestion.provenance",
    "legalforecast.evals.inspect_task",
    "legalforecast.evals.output_parser",
    "legalforecast.evals.tools",
    "legalforecast.evals.scorers",
    "legalforecast.evals.baselines",
    "legalforecast.evals.bootstrap",
    "legalforecast.evals.model_registry",
    "legalforecast.evals.human_baseline",
    "legalforecast.reporting.leaderboard",
    "legalforecast.reporting.contamination_tiers",
    "legalforecast.reporting.calibration",
    "legalforecast.reporting.pareto",
    "legalforecast.reporting.result_class",
    "legalforecast.publication.official_aggregate",
    "legalforecast.publication.publication_guardrails",
    "legalforecast.publication.withdrawal",
    "legalforecast.unitization.schemas",
    "legalforecast.labeling.label_outcomes",
]


def test_skeleton_modules_import() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)


def test_cli_placeholder_prints_help(capsys) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "LegalForecast-MTD benchmark utilities" in captured.out
    assert "preregistration" not in captured.out.lower()
    assert importlib.util.find_spec("legalforecast.protocol.evaluation_gate") is None
    assert importlib.util.find_spec("legalforecast.protocol.preregistration") is None


def test_expected_placeholder_directories_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "tests" / "fixtures" / "case_packet",
        root / "tests" / "fixtures" / "manifests",
    ]
    for path in expected:
        assert path.is_dir()


def test_empty_fixture_directories_are_documented_from_fixture_root() -> None:
    root = Path(__file__).resolve().parents[1]
    fixture_readme = (root / "tests" / "fixtures" / "README.md").read_text(
        encoding="utf-8"
    )

    for fixture_name in ("case_packet", "manifests"):
        assert f"`{fixture_name}/`" in fixture_readme
        assert not (root / "tests" / "fixtures" / fixture_name / "README.md").exists()

    assert not (root / "tests" / "fixtures" / "protocols").exists()

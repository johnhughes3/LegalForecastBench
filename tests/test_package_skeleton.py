from __future__ import annotations

import importlib
from pathlib import Path

from legalforecast.cli import main

MODULES = [
    "legalforecast.ingestion.acquisition_contract",
    "legalforecast.ingestion.case_dev_client",
    "legalforecast.ingestion.case_dev_purchase",
    "legalforecast.ingestion.core_document_filter",
    "legalforecast.ingestion.courtlistener_client",
    "legalforecast.ingestion.courtlistener_web",
    "legalforecast.ingestion.docket_markdown",
    "legalforecast.ingestion.fallback_retrieval",
    "legalforecast.ingestion.free_document_downloader",
    "legalforecast.ingestion.missing_core_budget",
    "legalforecast.ingestion.mistral_markdown_parser",
    "legalforecast.ingestion.model_packet_assembly",
    "legalforecast.ingestion.mtd_acquisition_screen",
    "legalforecast.ingestion.purchased_document_recovery",
    "legalforecast.ingestion.recap_client",
    "legalforecast.ingestion.docket_sync",
    "legalforecast.extraction.pdf_text",
    "legalforecast.extraction.ocr",
    "legalforecast.extraction.normalize_text",
    "legalforecast.selection.candidate_discovery",
    "legalforecast.selection.eligibility",
    "legalforecast.selection.contamination_filters",
    "legalforecast.selection.exclusion_ledger",
    "legalforecast.selection.motion_linkage",
    "legalforecast.selection.case_mix_diagnostics",
    "legalforecast.protocol.evaluation_gate",
    "legalforecast.protocol.preregistration",
    "legalforecast.protocol.freeze",
    "legalforecast.unitization.construct_units",
    "legalforecast.unitization.schemas",
    "legalforecast.unitization.adjudication",
    "legalforecast.labeling.label_outcomes",
    "legalforecast.labeling.ensemble",
    "legalforecast.labeling.llm_pipeline",
    "legalforecast.labeling.lawyer_review",
    "legalforecast.evals.inspect_task",
    "legalforecast.evals.output_parser",
    "legalforecast.evals.tools",
    "legalforecast.evals.scorers",
    "legalforecast.evals.baselines",
    "legalforecast.evals.bootstrap",
    "legalforecast.evals.human_baseline",
    "legalforecast.reporting.leaderboard",
    "legalforecast.reporting.calibration",
    "legalforecast.reporting.pareto",
    "legalforecast.reporting.fallback_pilot",
    "legalforecast.reporting.pilot_readiness",
    "legalforecast.publication.official_aggregate",
    "legalforecast.publication.private_store_export",
    "legalforecast.publication.publication_guardrails",
    "legalforecast.publication.run_cards",
    "legalforecast.publication.withdrawal",
]


def test_skeleton_modules_import() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)


def test_cli_placeholder_prints_help(capsys) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "LegalForecast-MTD benchmark utilities" in captured.out


def test_expected_placeholder_directories_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "tests" / "fixtures" / "case_packet",
        root / "tests" / "fixtures" / "manifests",
        root / "tests" / "fixtures" / "protocols",
    ]
    for path in expected:
        assert path.is_dir()


def test_empty_fixture_directories_are_documented_from_fixture_root() -> None:
    root = Path(__file__).resolve().parents[1]
    fixture_readme = (root / "tests" / "fixtures" / "README.md").read_text(
        encoding="utf-8"
    )

    for fixture_name in ("case_packet", "manifests", "protocols"):
        assert f"`{fixture_name}/`" in fixture_readme
        assert not (root / "tests" / "fixtures" / fixture_name / "README.md").exists()

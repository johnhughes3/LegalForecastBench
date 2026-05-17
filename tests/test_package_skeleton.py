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
        root / "docs",
        root / "manifests",
        root / "protocols",
        root / "docker" / "docket_tool",
        root / "tests" / "fixtures" / "case_packet",
        root / "tests" / "fixtures" / "manifests",
        root / "tests" / "fixtures" / "protocols",
    ]
    for path in expected:
        assert path.is_dir()

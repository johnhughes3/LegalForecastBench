from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/official_aggregation.md").read_text(encoding="utf-8")
DOCS_README = (ROOT / "docs/README.md").read_text(encoding="utf-8")


def test_official_aggregation_docs_describe_command_and_inputs() -> None:
    assert "python -m legalforecast.publication.official_aggregate" in DOC
    assert "--per-case-dir" in DOC
    assert "--run-input-manifest" in DOC
    assert "--labels" in DOC
    assert "--ablation full_packet" in DOC
    assert "gh run download" in DOC
    assert "publication_guardrails" in DOC
    assert "Official Aggregation" in DOCS_README


def test_official_aggregation_docs_pin_validation_failures() -> None:
    for phrase in (
        "missing from the downloaded artifacts",
        "unexpected or duplicate case/ablation output",
        "legalforecast.per_case_metrics.v1",
        "packet object key",
        "raw_output_sha256",
        "Locked labels",
    ):
        assert phrase.lower() in DOC.lower()


def test_official_aggregation_docs_keep_public_private_split_explicit() -> None:
    assert "public/" in DOC
    assert "private-debug/" in DOC
    assert "artifact-index.json" in DOC
    assert "aggregate-run-card.json" in DOC
    assert "raw court documents" in DOC
    assert "credentials" in DOC
    assert "provider account IDs" in DOC

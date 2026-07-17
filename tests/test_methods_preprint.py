from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/preprint/legalforecast-mtd-cycle-1.md"
PACKAGE_README = ROOT / "docs/preprint/README.md"
MANIFEST = ROOT / "docs/preprint/package-manifest.json"
AUDIT = ROOT / "docs/preprint/citation-audit.json"
RENDERER = ROOT / "scripts/render_methods_preprint.py"
PDF = ROOT / "output/pdf/legalforecast-mtd-cycle-1-draft.pdf"

OFFICIAL_LABEL = "Official LegalForecast-MTD Cycle 1 result"
PENDING = "Pending audited Cycle 1 aggregate"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_manuscript_covers_required_methods_without_claiming_results() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert source.startswith("# LegalForecast-MTD Cycle 1")
    assert "Pre-results methods draft - no Cycle 1 result claimed" in source
    assert "\u2013" not in source
    assert "\u2014" not in source
    assert "John J. Hughes III" in source
    for heading in (
        "## Abstract",
        "## 1. Research question and intended use",
        "## 2. Benchmark design",
        "## 3. Contamination resistance",
        "## 4. Model execution and recovery",
        "## 5. Metrics and statistical analysis",
        "## 6. Cycle 1 results",
        "## 7. Limitations",
        "## 8. Reproducibility and audit",
        "## References",
    ):
        assert heading in source

    results = source.split("## 6. Cycle 1 results", 1)[1].split("## 7. Limitations", 1)[
        0
    ]
    assert results.count(PENDING) >= 8
    assert OFFICIAL_LABEL in results
    assert "micro-Brier" in results
    assert "calibration" in results.lower()
    assert "refusal" in results.lower()
    assert "realized prevalence" in results.lower()
    assert "baseline" in results.lower()
    assert not re.search(r"(?:micro-Brier|Brier)\s*(?:=|of)\s*0\.\d+", results)

    assert "Harness-comparison appendix" not in source
    assert "LegalForecastBench is an independent project." in source
    assert "not legal advice" in source.lower()

    assert "recompute each unit loss from" in source
    assert "probability_fully_dismissed" in source
    assert "reject the aggregate if any published `brier` value differs" in source
    assert "Public accounting reports attempts" not in source
    assert "Preoțiuc-Pietro" not in source

    accounting = source.split("### 5.4 Accounting", 1)[1].split(
        "## 6. Cycle 1 results", 1
    )[0]
    for public_field in (
        "run count",
        "request count",
        "prompt tokens",
        "completion tokens",
        "total tokens",
        "mean latency",
        "95th-percentile latency",
        "estimated cost",
    ):
        assert public_field in accounting.lower()
    for private_field in ("attempts", "retries", "failures"):
        assert private_field not in accounting.lower()


def test_package_manifest_freezes_result_bindings_and_submission_boundary() -> None:
    manifest = _manifest()

    assert manifest["schema_version"] == "legalforecast-methods-preprint-package-v1"
    assert manifest["status"] == "draft_waiting_on_audited_results"
    assert manifest["submission_authorized"] is False
    assert manifest["submission_authority"] == "John J. Hughes III"
    assert manifest["remaining_manuscript_input"] == [
        "audited_official_cycle_1_public_aggregate"
    ]
    assert manifest["community_appendix_included"] is False
    assert manifest["evidence_tier_after_population"] == OFFICIAL_LABEL

    slots = cast(list[dict[str, str]], manifest["result_slots"])
    assert len(slots) >= 8
    slot_ids = {slot["id"] for slot in slots}
    assert len(slot_ids) == len(slots)
    for slot in slots:
        assert slot["draft_display"] == PENDING
        assert slot["source_path"].startswith("public/")
        assert slot["source_field"]
        assert slot["verification"]

    slots_by_id = {slot["id"]: slot for slot in slots}
    micro_brier = slots_by_id["micro_brier"]
    assert micro_brier["source_path"] == "public/unit-scores.jsonl"
    assert micro_brier["source_field"] == (
        "probability_fully_dismissed, outcome, and brier for each public unit row"
    )
    assert "(probability_fully_dismissed - outcome)^2" in micro_brier["verification"]
    assert "reject any brier mismatch" in micro_brier["verification"]

    uncertainty = slots_by_id["clustered_uncertainty"]
    assert uncertainty["source_path"] == "public/variance/repeat-sampling.json"

    accounting = slots_by_id["accounting"]
    assert accounting["source_path"] == "public/scores.json"
    for public_field in (
        "run_count",
        "request_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "mean_latency_ms",
        "p95_latency_ms",
        "total_estimated_cost",
        "cost_per_case",
        "cost_per_prediction_unit",
    ):
        assert public_field in accounting["source_field"]
    for private_field in ("attempt", "retry", "failure"):
        assert private_field not in accounting["source_field"].lower()
        assert private_field not in accounting["verification"].lower()


def test_citation_audit_covers_every_reference_and_sizes_claims() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    entries = audit["entries"]

    reference_ids = set(re.findall(r"^\[(R\d+)\]:", source, flags=re.MULTILINE))
    audit_ids = {entry["reference_id"] for entry in entries}
    assert len(reference_ids) >= 10
    assert reference_ids == audit_ids
    manuscript_body = source.split("## References", 1)[0]
    for reference_id in reference_ids:
        assert f"[{reference_id}]" in manuscript_body
    for entry in entries:
        assert entry["source"]
        assert entry["citation_author"]
        assert entry["citation_title"]
        assert entry["supports"]
        assert entry["claim_scope"] in {"direct", "design_analogy", "context_only"}
        assert entry["checked_on"] == "2026-07-17"

    forecastbench = next(entry for entry in entries if entry["reference_id"] == "R8")
    assert forecastbench["citation_author"] == "Ezra Karger et al."
    assert forecastbench["citation_title"] == (
        "ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities"
    )


def test_package_documents_audited_population_and_no_submission() -> None:
    readme = PACKAGE_README.read_text(encoding="utf-8")

    assert "does not authorize SSRN or arXiv submission" in readme
    assert "audited official aggregate" in readme
    assert "table reconstruction" in readme
    assert "independent methods review" in readme
    assert "uv run scripts/render_methods_preprint.py" in readme
    assert "(probability_fully_dismissed - outcome)^2" in readme
    assert "reject any supplied `brier` mismatch" in readme
    assert "results/community/" not in readme


def test_rendered_pdf_is_stable_legible_six_to_ten_page_draft(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    command = [
        sys.executable,
        str(RENDERER),
        "--source",
        str(SOURCE),
        "--output",
    ]
    subprocess.run([*command, str(first)], cwd=ROOT, check=True)
    subprocess.run([*command, str(second)], cwd=ROOT, check=True)

    assert (
        hashlib.sha256(first.read_bytes()).digest()
        == hashlib.sha256(second.read_bytes()).digest()
    )
    reader = PdfReader(first)
    assert 6 <= len(reader.pages) <= 10
    assert reader.metadata is not None
    assert reader.metadata.title == "LegalForecast-MTD Cycle 1"

    text = _pdf_text(first)
    assert "Pre-results methods draft" in text
    assert "no Cycle 1 result claimed" in text
    assert PENDING in text
    assert "Research question and intended use" in text
    assert "Reproducibility and audit" in text
    assert "References" in text
    for forbidden in ("BEGIN PRIVATE KEY", "AWS_SECRET", "private-debug/"):
        assert forbidden not in text


def test_committed_pdf_matches_renderer_and_page_contract(tmp_path: Path) -> None:
    rendered = tmp_path / "rendered.pdf"
    subprocess.run(
        [
            sys.executable,
            str(RENDERER),
            "--source",
            str(SOURCE),
            "--output",
            str(rendered),
        ],
        cwd=ROOT,
        check=True,
    )

    assert PDF.read_bytes() == rendered.read_bytes()
    assert 6 <= len(PdfReader(PDF).pages) <= 10

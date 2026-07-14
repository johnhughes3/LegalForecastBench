"""Canonical noncharging preparation commands for a 100-case acquisition.

Discovery and strict screening remain provider-specific, durable phases.  This
module begins at their common, immutable boundary: a complete saturated
snapshot.  It composes only noncharging stages and deliberately has no paid
purchase operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class Target100PreparationError(ValueError):
    """Raised when a target-100 preparation cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class Target100PreparationConfig:
    """Inputs for the resumable, noncharging target-100 preparation."""

    output_root: Path
    snapshot: Path
    expected_cycle_hash: str
    candidate_pool_size: int = 165
    target_case_count: int = 100
    cost_per_document_usd: str = "3.05"
    max_projected_budget_usd: str = "2250.00"
    max_missing_core_documents_per_case: int = 24
    raw_html_dir: Path | None = None
    use_embedded_entries: bool = False
    live_public_download: bool = False
    fixture_documents: Path | None = None
    live_case_dev: bool = False
    case_dev_fixture: Path | None = None
    resume: bool = True

    def validate(self) -> None:
        if self.target_case_count != 100:
            raise Target100PreparationError("target case count must be exactly 100")
        if self.candidate_pool_size < self.target_case_count:
            raise Target100PreparationError(
                "candidate pool size cannot be smaller than the 100-case target"
            )
        if self.live_public_download == (self.fixture_documents is not None):
            raise Target100PreparationError(
                "choose exactly one public download source: live CourtListener/RECAP "
                "or --fixture-documents"
            )
        if self.live_case_dev == (self.case_dev_fixture is not None):
            raise Target100PreparationError(
                "choose exactly one free identity source: live Case.dev or "
                "--case-dev-fixture"
            )


@dataclass(frozen=True, slots=True)
class Target100StageCommand:
    """One existing acquisition subcommand in the canonical preparation."""

    stage: str
    argv: tuple[str, ...]


def build_target_100_stage_commands(
    config: Target100PreparationConfig,
) -> tuple[Target100StageCommand, ...]:
    """Compose the existing CLI stages without any paid-operation flags."""

    config.validate()
    root = config.output_root
    public_plan_root = root / "01-public-plan"
    free_download_root = root / "02-free-download"
    bridge_root = root / "03-gap-bridge"
    filter_root = root / "04-core-filter"
    budget_root = root / "05-budget"
    resume_flag = "--resume" if config.resume else "--no-resume"

    public_plan = [
        "acquisition",
        "plan-public-downloads",
        "--output-root",
        str(public_plan_root),
        "--execute",
        resume_flag,
        "--snapshot",
        str(config.snapshot),
        "--expected-cycle-hash",
        config.expected_cycle_hash,
        "--target-clean-cases",
        str(config.candidate_pool_size),
        "--cost-per-missing-document-usd",
        config.cost_per_document_usd,
    ]
    if config.raw_html_dir is not None:
        public_plan.extend(("--raw-html-dir", str(config.raw_html_dir)))
    if config.use_embedded_entries:
        public_plan.append("--use-embedded-entries")

    download_free = [
        "acquisition",
        "download-free",
        "--output-root",
        str(free_download_root),
        "--execute",
        resume_flag,
        "--requests",
        str(public_plan_root / "free-document-requests.jsonl"),
    ]
    if config.live_public_download:
        download_free.append("--live-public-download")
    else:
        assert config.fixture_documents is not None
        download_free.extend(("--fixture-documents", str(config.fixture_documents)))

    bridge = [
        "acquisition",
        "bridge-pacer-gaps",
        "--output-root",
        str(bridge_root),
        "--execute",
        resume_flag,
        "--screened-cases",
        str(config.snapshot / "screened-cases.jsonl"),
        "--target-clean-cases",
        str(config.candidate_pool_size),
        "--public-selection",
        str(public_plan_root / "public-packet-selection.jsonl"),
        "--paid-gaps",
        str(public_plan_root / "public-packet-paid-gaps.jsonl"),
        "--free-download-manifest",
        str(free_download_root / "free-document-downloads.jsonl"),
    ]
    if config.raw_html_dir is not None:
        bridge.extend(("--raw-html-dir", str(config.raw_html_dir)))
    if config.use_embedded_entries:
        bridge.append("--use-embedded-entries")
    if config.live_case_dev:
        bridge.append("--live-case-dev")
    else:
        assert config.case_dev_fixture is not None
        bridge.extend(("--case-dev-fixture", str(config.case_dev_fixture)))

    filter_core = (
        "acquisition",
        "filter-core-documents",
        "--output-root",
        str(filter_root),
        "--execute",
        resume_flag,
        "--case-relevance",
        str(bridge_root / "case-relevance.jsonl"),
    )
    budget = (
        "acquisition",
        "plan",
        "--output-root",
        str(budget_root),
        "--execute",
        resume_flag,
        "--core-filter-results",
        str(filter_root / "core-filter-results.jsonl"),
        "--cost-per-document-usd",
        config.cost_per_document_usd,
        "--max-projected-budget-usd",
        config.max_projected_budget_usd,
        "--max-missing-core-documents-per-case",
        str(config.max_missing_core_documents_per_case),
        "--truncate-to-budget",
        "--target-case-count",
        str(config.target_case_count),
    )
    return (
        Target100StageCommand("plan-public-downloads", tuple(public_plan)),
        Target100StageCommand("download-free", tuple(download_free)),
        Target100StageCommand("bridge-pacer-gaps", tuple(bridge)),
        Target100StageCommand("filter-core-documents", filter_core),
        Target100StageCommand("plan", budget),
    )

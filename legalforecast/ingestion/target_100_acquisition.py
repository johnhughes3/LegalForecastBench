"""Canonical noncharging preparation commands for a target cohort.

Discovery and strict screening remain provider-specific, durable phases.  This
module begins at their common, immutable boundary: a complete saturated
snapshot. It composes only noncharging stages, produces a provisional
pre-clearance budget, and deliberately has no paid purchase operation. The
exact cohort is projected only after authenticated disclosure clearance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_LOWERCASE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class TargetCohortPreparationError(ValueError):
    """Raised when a target-cohort preparation cannot proceed safely."""


class Target100PreparationError(TargetCohortPreparationError):
    """Raised when a target-100 preparation cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class TargetCohortPreparationConfig:
    """Inputs for a resumable, noncharging, explicitly sized preparation."""

    output_root: Path
    snapshot: Path
    expected_cycle_hash: str
    expected_snapshot_manifest_sha256: str
    candidate_pool_size: int
    target_case_count: int
    authenticated_screened_cases: Path
    screened_cases_sha256: str
    cost_per_document_usd: str = "3.05"
    max_projected_budget_usd: str = "2250.00"
    max_missing_core_documents_per_case: int = 24
    raw_html_dir: Path | None = None
    authenticated_raw_html_manifest: Path | None = None
    authenticated_raw_html_manifest_sha256: str | None = None
    requested_raw_html_dir: Path | None = None
    use_embedded_entries: bool = False
    live_public_download: bool = False
    fixture_documents: Path | None = None
    live_courtlistener: bool = False
    courtlistener_fixture: Path | None = None
    request_ledger: Path | None = None
    courtlistener_rate_profile: str = "base"
    request_budget_max_wait_seconds: float = 120.0
    resume: bool = True

    def validate(self) -> None:
        _validate_preparation_config(self, TargetCohortPreparationError)


@dataclass(frozen=True, slots=True)
class Target100PreparationConfig:
    """Inputs for the resumable, noncharging target-100 preparation."""

    output_root: Path
    snapshot: Path
    expected_cycle_hash: str
    expected_snapshot_manifest_sha256: str
    candidate_pool_size: int
    authenticated_screened_cases: Path
    screened_cases_sha256: str
    target_case_count: int = 100
    cost_per_document_usd: str = "3.05"
    max_projected_budget_usd: str = "2250.00"
    max_missing_core_documents_per_case: int = 24
    raw_html_dir: Path | None = None
    authenticated_raw_html_manifest: Path | None = None
    authenticated_raw_html_manifest_sha256: str | None = None
    requested_raw_html_dir: Path | None = None
    use_embedded_entries: bool = False
    live_public_download: bool = False
    fixture_documents: Path | None = None
    live_courtlistener: bool = False
    courtlistener_fixture: Path | None = None
    request_ledger: Path | None = None
    courtlistener_rate_profile: str = "base"
    request_budget_max_wait_seconds: float = 120.0
    resume: bool = True

    def validate(self) -> None:
        if self.target_case_count != 100:
            raise Target100PreparationError("target case count must be exactly 100")
        _validate_preparation_config(self, Target100PreparationError)


@dataclass(frozen=True, slots=True)
class Target100StageCommand:
    """One existing acquisition subcommand in the canonical preparation."""

    stage: str
    argv: tuple[str, ...]


def _require_validated[T](value: T | None, *, message: str) -> T:
    """Defensively enforce an invariant already checked by config validation."""

    if value is None:
        raise TargetCohortPreparationError(message)
    return value


def build_target_cohort_stage_commands(
    config: TargetCohortPreparationConfig,
) -> tuple[Target100StageCommand, ...]:
    """Compose generic target-cohort stages without a paid operation."""

    config.validate()
    return _build_target_stage_commands(config)


def build_target_100_stage_commands(
    config: Target100PreparationConfig,
) -> tuple[Target100StageCommand, ...]:
    """Compose the existing CLI stages without any paid-operation flags."""

    config.validate()
    return _build_target_stage_commands(config)


def _build_target_stage_commands(
    config: TargetCohortPreparationConfig | Target100PreparationConfig,
) -> tuple[Target100StageCommand, ...]:
    """Compose the shared public-first preparation stages."""

    root = config.output_root
    public_plan_root = root / "01-public-plan"
    free_download_root = root / "02-free-download"
    bridge_root = root / "03-gap-bridge"
    bridge_free_download_root = root / "03b-bridge-free-download"
    merged_download_root = root / "03c-merged-downloads"
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
        "--expected-snapshot-manifest-sha256",
        config.expected_snapshot_manifest_sha256,
        "--screened-cases",
        str(config.authenticated_screened_cases),
        "--expected-screened-cases-sha256",
        config.screened_cases_sha256,
        "--target-clean-cases",
        str(config.candidate_pool_size),
        "--cost-per-missing-document-usd",
        config.cost_per_document_usd,
    ]
    if config.raw_html_dir is not None:
        raw_manifest = _require_validated(
            config.authenticated_raw_html_manifest,
            message="authenticated raw-HTML manifest is required with raw HTML",
        )
        raw_manifest_sha256 = _require_validated(
            config.authenticated_raw_html_manifest_sha256,
            message="authenticated raw-HTML manifest SHA-256 is required with raw HTML",
        )
        public_plan.extend(
            (
                "--raw-html-dir",
                str(config.raw_html_dir),
                "--authenticated-raw-html-manifest",
                str(raw_manifest),
                "--expected-authenticated-raw-html-manifest-sha256",
                raw_manifest_sha256,
            )
        )
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
        "--document-output-root",
        str(root / "documents/free"),
    ]
    if config.live_public_download:
        download_free.append("--live-public-download")
    else:
        fixture_documents = _require_validated(
            config.fixture_documents,
            message="fixture documents are required without live public download",
        )
        download_free.extend(("--fixture-documents", str(fixture_documents)))

    bridge = [
        "acquisition",
        "bridge-pacer-gaps",
        "--output-root",
        str(bridge_root),
        "--execute",
        resume_flag,
        "--screened-cases",
        str(config.authenticated_screened_cases),
        "--expected-screened-cases-sha256",
        config.screened_cases_sha256,
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
        raw_manifest = _require_validated(
            config.authenticated_raw_html_manifest,
            message="authenticated raw-HTML manifest is required with raw HTML",
        )
        raw_manifest_sha256 = _require_validated(
            config.authenticated_raw_html_manifest_sha256,
            message="authenticated raw-HTML manifest SHA-256 is required with raw HTML",
        )
        bridge.extend(
            (
                "--authenticated-raw-html-manifest",
                str(raw_manifest),
                "--expected-authenticated-raw-html-manifest-sha256",
                raw_manifest_sha256,
            )
        )
    if config.use_embedded_entries:
        bridge.append("--use-embedded-entries")
    if config.live_courtlistener:
        request_ledger = _require_validated(
            config.request_ledger,
            message="request ledger is required with live CourtListener REST",
        )
        bridge.extend(
            (
                "--live-courtlistener",
                "--request-ledger",
                str(request_ledger),
                "--courtlistener-rate-profile",
                config.courtlistener_rate_profile,
                "--request-budget-max-wait-seconds",
                str(config.request_budget_max_wait_seconds),
            )
        )
    else:
        courtlistener_fixture = _require_validated(
            config.courtlistener_fixture,
            message="CourtListener fixture is required without live CourtListener REST",
        )
        bridge.extend(("--courtlistener-fixture", str(courtlistener_fixture)))

    download_bridge_free = [
        "acquisition",
        "download-free",
        "--output-root",
        str(bridge_free_download_root),
        "--execute",
        resume_flag,
        "--requests",
        str(bridge_root / "pacer-gap-free-document-requests.jsonl"),
        "--document-output-root",
        str(root / "documents/free"),
    ]
    if config.live_public_download:
        download_bridge_free.append("--live-public-download")
    else:
        fixture_documents = _require_validated(
            config.fixture_documents,
            message="fixture documents are required without live public download",
        )
        download_bridge_free.extend(("--fixture-documents", str(fixture_documents)))

    merge_free_downloads = (
        "acquisition",
        "merge-download-manifests",
        "--output-root",
        str(merged_download_root),
        "--execute",
        resume_flag,
        "--download-manifest",
        str(free_download_root / "free-document-downloads.jsonl"),
        "--download-manifest",
        str(bridge_free_download_root / "free-document-downloads.jsonl"),
        "--candidate-selection",
        str(bridge_root / "public-packet-selection-reconciled.jsonl"),
    )

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
        Target100StageCommand(
            "download-bridge-free",
            tuple(download_bridge_free),
        ),
        Target100StageCommand("merge-free-downloads", merge_free_downloads),
        Target100StageCommand("filter-core-documents", filter_core),
        Target100StageCommand("plan", budget),
    )


def _validate_preparation_config(
    config: TargetCohortPreparationConfig | Target100PreparationConfig,
    error_type: type[TargetCohortPreparationError],
) -> None:
    if config.target_case_count < 1:
        raise error_type("target case count must be positive")
    if config.candidate_pool_size < 1:
        raise error_type("candidate pool size must be positive")
    if config.candidate_pool_size < config.target_case_count:
        raise error_type("candidate pool size must be at least target case count")
    if _LOWERCASE_SHA256.fullmatch(config.expected_snapshot_manifest_sha256) is None:
        raise error_type(
            "expected snapshot manifest SHA-256 must be 64 lowercase hex digits"
        )
    if _LOWERCASE_SHA256.fullmatch(config.screened_cases_sha256) is None:
        raise error_type("screened-cases SHA-256 must be 64 lowercase hex digits")
    raw_inputs = (
        config.raw_html_dir,
        config.authenticated_raw_html_manifest,
        config.authenticated_raw_html_manifest_sha256,
    )
    if any(value is not None for value in raw_inputs) and not all(
        value is not None for value in raw_inputs
    ):
        raise error_type(
            "raw HTML directory, authenticated manifest, and expected manifest "
            "SHA-256 must be provided together"
        )
    if (
        config.authenticated_raw_html_manifest_sha256 is not None
        and _LOWERCASE_SHA256.fullmatch(config.authenticated_raw_html_manifest_sha256)
        is None
    ):
        raise error_type(
            "authenticated raw-HTML manifest SHA-256 must be 64 lowercase hex digits"
        )
    if config.live_public_download == (config.fixture_documents is not None):
        raise error_type(
            "choose exactly one public download source: live CourtListener/RECAP "
            "or --fixture-documents"
        )
    if config.live_courtlistener == (config.courtlistener_fixture is not None):
        raise error_type(
            "choose exactly one authoritative paid-gap source: live "
            "CourtListener REST or --courtlistener-fixture"
        )
    if config.live_courtlistener and config.request_ledger is None:
        raise error_type("--request-ledger is required with live CourtListener REST")
    if not config.live_courtlistener and config.request_ledger is not None:
        raise error_type("--request-ledger is only valid with live CourtListener REST")

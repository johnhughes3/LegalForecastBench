"""Command-line orchestration for LegalForecast-MTD benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast import __version__
from legalforecast.evals.accounting import (
    OutputValidityStatus,
    accounting_records_from_inspect_run,
)
from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    BootstrapInferenceResult,
    ModelScoreInput,
    paired_clustered_bootstrap,
)
from legalforecast.evals.inspect_task import (
    OfflineMockSolver,
    build_inspect_samples,
    run_inspect_fixture,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    earliest_eligible_decision_date,
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.evals.output_parser import (
    ParserIssueCode,
    ParserStatus,
    parse_model_output,
)
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
    PacketText,
    build_model_packet,
    texts_from_mapping,
)
from legalforecast.evals.per_case_runner import (
    PerCaseExecutionBackend,
    PerCaseRunnerConfig,
    run_per_case_evaluation,
)
from legalforecast.evals.scorers import (
    CalibrationBin,
    DominanceSensitivityReport,
    RobustnessDimension,
    ScoreSummary,
    ScoringCase,
    UnitScore,
    score_cases,
)
from legalforecast.extraction.pdf_text import extract_pdf_text_with_ocr_fallback
from legalforecast.ingestion.budgeted_courtlistener_html_source import (
    DurableBudgetedCourtListenerHTMLSource,
)
from legalforecast.ingestion.budgeted_docket_acquisition import (
    acquire_ranked_dockets,
    materialize_selected_slice_batch,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlCircuitOpenError,
    FirecrawlPageRecord,
    FirecrawlTargetSpec,
    load_successful_firecrawl_pages,
)
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevClientError,
    CaseDevFixtureTransport,
    CaseDevRateLimiter,
    CaseDevRateLimitError,
    CaseDevServerError,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_discovery import (
    CaseDevDiscoverySource,
    case_dev_firecrawl_candidate_record,
)
from legalforecast.ingestion.case_dev_firecrawl import (
    CaseDevFirecrawlBatchError,
    acquire_case_dev_firecrawl_html,
    screen_case_dev_firecrawl_successes,
)
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseClient,
    CaseDevPacerPurchaseResult,
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    generate_case_dev_purchase_policy,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_journal_initialization,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
    write_case_dev_purchase_policy,
)
from legalforecast.ingestion.case_dev_recap_batch import enrich_recap_discovery_batch
from legalforecast.ingestion.case_dev_smoke import (
    CaseDevSmokeConfig,
    case_dev_smoke_query_terms,
    plan_case_dev_smoke,
    render_case_dev_smoke_markdown,
    run_case_dev_smoke,
)
from legalforecast.ingestion.clearance_replacement import (
    ClearanceReplacementError,
    build_broad_broker_allowlist_plan,
    build_replacement_frontier,
    plan_clearance_replacements,
    write_replacement_frontier,
)
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    export_observation_manifest,
    generate_cohort_policy,
    read_observation_manifest,
    verify_cohort_policy,
    verify_observation_manifest,
    write_cohort_policy,
)
from legalforecast.ingestion.core_document_filter import (
    CoreDocumentFilterResult,
    filter_core_documents,
    read_case_relevance_jsonl,
    write_core_document_filter_results,
)
from legalforecast.ingestion.corpus_readiness import (
    CorpusReadinessReport,
    build_clean_corpus_readiness,
    require_clean_corpus_ready,
)
from legalforecast.ingestion.courtlistener_acquisition import (
    DEFAULT_COURTLISTENER_MTD_QUERY_TERMS,
    FixtureCourtListenerDocketHTMLSource,
    LiveCourtListenerDocketHTMLSource,
    discover_courtlistener_mtd_candidates,
    validate_courtlistener_discovery_limits,
)
from legalforecast.ingestion.courtlistener_case_dev_bridge import (
    CourtListenerCaseDevBridgeError,
    CourtListenerCaseDevBridgeResult,
    bridge_courtlistener_case_dev_documents,
    bridge_free_download_requests_from_selection,
    bridge_public_plan_paid_gap_candidate,
    bridge_public_plan_paid_gap_candidate_via_courtlistener,
    bridge_public_plan_paid_gaps,
    bridge_public_plan_paid_gaps_via_courtlistener,
    case_dev_bridge_exclusion_record,
    merge_download_manifest_records,
    validate_public_plan_bridge_inputs,
)
from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_API_TOKEN_ENV,
    CourtListenerAuthError,
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    CourtListenerRateLimitError,
    CourtListenerResponseError,
    CourtListenerServerError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    UrlLibRecapFetchTransport,
    public_documents_from_selection,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudget,
    CourtListenerRequestBudgetError,
    CourtListenerRequestLimits,
)
from legalforecast.ingestion.courtlistener_snapshot_materialization import (
    CourtListenerSnapshotMaterializationError,
    VerifiedCourtListenerDiscovery,
    verify_courtlistener_discovery,
)
from legalforecast.ingestion.cycle_acquisition_assembler import (
    COMPONENT_PROVENANCE_FILENAME,
    COMPONENT_STAGE_ORDER,
    CycleAssembly,
    assemble_cycle_acquisition,
    write_component_provenance,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    FirecrawlAttempt,
    SnapshotVerificationError,
    cohort_reason_policy_taxonomy,
    verify_snapshot,
)
from legalforecast.ingestion.disclosure_clearance import (
    DisclosureClearanceError,
    build_clearance_records,
    require_cleared_documents,
    require_cleared_parse_requests,
    require_cleared_parser_records,
    validate_review_receipt,
    verify_parse_request_bytes,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    DiscoverySchedulerError,
    TermTerminalStatus,
    materialize_independent_term_sets,
)
from legalforecast.ingestion.docket_live_fetch import (
    DocketLiveFetchError,
    DocketLiveFetchExecutionResult,
    execute_docket_live_fetch_plan,
    load_docket_live_fetch_plan,
    plan_docket_live_fetches,
)
from legalforecast.ingestion.docket_markdown import ControlledDocketMarkdownArtifacts
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    NormalizedDocketEntry,
)
from legalforecast.ingestion.firecrawl_recap_decision_discovery import (
    DECISION_FIRST_RECAP_MAX_AUTHORIZED_CREDITS,
    DECISION_FIRST_RECAP_MAX_PAGES_PER_TERM,
    DECISION_FIRST_RECAP_QUERY_PLAN_VERSION,
    DECISION_FIRST_RECAP_SEARCH_TERMS,
    FROZEN_COMBINED_FIRECRAWL_CREDIT_CEILING,
    FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS,
    FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS,
    decision_recap_query_expression,
    decision_rescue_worst_case_credits,
    discover_decision_recap_entries,
    parse_decision_recap_search_html,
    parse_decision_recap_search_url,
)
from legalforecast.ingestion.firecrawl_recap_discovery import (
    COURTLISTENER_QUERY_PLAN_VERSION,
    FROZEN_MTD_SEARCH_TERMS,
    RecapDiscoveredEntry,
    RecapSearchError,
    RecapSearchHit,
    RecapSearchPage,
    RecapSearchTarget,
    courtlistener_query_expression,
    discover_recap_mtd_entries,
    parse_recap_search_html,
    parse_recap_search_url,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlError,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlProxy,
)
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadError,
    FreeDocumentDownloadRequest,
    FreeDocumentSource,
    UrlLibFreeDocumentSource,
    download_free_docket_documents,
)
from legalforecast.ingestion.funnel_report import (
    FunnelReportError,
    build_acquisition_funnel_report,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
    PurchaseFrontierRow,
    plan_missing_core_document_budget,
    rank_missing_core_document_plans,
    write_missing_core_budget_plan,
)
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRecord,
    MistralMarkdownConversionRequest,
    MistralMarkdownConversionStatus,
    MistralParserConfig,
    convert_documents_to_markdown,
)
from legalforecast.ingestion.model_packet_assembly import (
    ModelPacketAssembly,
    ParsedMarkdownDocument,
    assemble_model_packet,
    parsed_markdown_documents_from_conversion_records,
)
from legalforecast.ingestion.packet_input_planner import plan_packet_build_inputs
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    RedactionOrSealStatus,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads
from legalforecast.ingestion.purchased_document_recovery import (
    PurchasedDocumentDownloadError,
    PurchasedDocumentRecoveryError,
    PurchasedDocumentRecoveryStatus,
    UrlLibPurchasedDocumentSource,
    purchased_document_download_manifest_records,
    purchased_document_recovery_requests_from_records,
    recover_purchased_documents,
)
from legalforecast.ingestion.readiness_provenance import (
    ReadinessProvenanceError,
    verify_stage_a_readiness_provenance,
    verify_stage_b_readiness_provenance,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    RecapApiBatchDriverError,
    read_batch_001_enrichment_failure_leads,
    read_saturated_direct_search_leads,
    run_discover,
    run_observe,
    seed_batch_001_leads,
    seed_direct_search_leads,
)
from legalforecast.ingestion.recap_api_discovery import (
    RecapApiDiscoveryError,
    RequestPacer,
)
from legalforecast.ingestion.recap_fetch_broker import (
    RecapFetchBrokerConfig,
    SignedRecapFetchPurchaseBroker,
)
from legalforecast.ingestion.recap_fetch_broker_policy import (
    RecapFetchBrokerPolicyError,
    broker_policy_sha256,
    generate_recap_fetch_broker_policy,
    write_recap_fetch_broker_policy,
)
from legalforecast.ingestion.recap_partial_checkpoint import (
    RecapPartialProjectionError,
    project_partial_recap_checkpoint,
)
from legalforecast.ingestion.retained_cohort_extension import (
    BASE_CASE_COUNT,
    BASE_PROJECTION_ARTIFACT_NAMES,
    AuthenticatedPoolLineage,
    RetainedCohortExtension,
    RetainedCohortExtensionError,
    extend_target_cohort,
    purchase_obligation_snapshot,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)
from legalforecast.ingestion.snapshot_quarantine import (
    SnapshotQuarantineError,
    quarantine_orphan_snapshot,
)
from legalforecast.ingestion.snapshot_replay import (
    SnapshotReplayBundle,
    SnapshotReplayError,
    SupplementalReplaySource,
    collect_snapshot_replay_bundle,
    firecrawl_screen_input_commitments,
    read_verified_replay_raw,
    source_replay_commitment,
)
from legalforecast.ingestion.target_100_acquisition import (
    Target100PreparationConfig,
    Target100PreparationError,
    TargetCohortPreparationConfig,
    TargetCohortPreparationError,
    build_target_100_stage_commands,
    build_target_cohort_stage_commands,
)
from legalforecast.ingestion.target_cohort_projection import (
    TargetCohortProjectionError,
    project_target_cohort,
    restriction_evidence_from_case_relevance,
)
from legalforecast.labeling.cycle_label_audit import (
    CycleLabelAuditError,
    evaluate_cycle_label_audit,
    plan_cycle_label_audit,
)
from legalforecast.labeling.label_outcomes import (
    AmendmentClass,
    AmendmentSignal,
    OutcomeCitation,
    OutcomeLabel,
    StageBDecisionText,
    StageBLabelingInput,
    StageBMissingUnitFlag,
    StageBUnitFinding,
    UnitResolution,
    label_stage_b_outcomes,
)
from legalforecast.labeling.llm_pipeline import (
    DEFAULT_LABEL_AUDIT_SAMPLE_SIZE,
    LlmConsensusPolicy,
    apply_adjudicated_reviews,
    lawyer_review_queue_records,
    llm_label_cases,
    llm_review_stage_a_units,
    llm_unitize_cases,
    merge_structural_flags_into_review_queue,
    unitization_review_queue_records,
)
from legalforecast.labeling.provider_journal import (
    ProviderCycleCaps,
    ProviderJournalError,
    load_provider_cycle_caps,
)
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.path_safety import safe_path_component
from legalforecast.protocol import (
    FrozenArtifactName,
    build_candidate_manifest_record,
    freeze_cycle,
    generate_execution_policy,
    generate_labeling_policy,
    sha256_file,
    verify_labeling_policy,
    write_labeling_policy,
)
from legalforecast.publication.static_sites import render_official_results_site
from legalforecast.reporting.fallback_pilot import (
    FallbackCredentialStatus,
    build_fallback_reconstruction_pilot_report,
    parse_case_dev_fallback_candidates,
    render_fallback_reconstruction_pilot_markdown,
    run_courtlistener_fallback_attempts,
)
from legalforecast.reporting.leaderboard import (
    BenchmarkLeaderboardReport,
    build_benchmark_leaderboard_report,
    summarize_accounting_leaderboard,
)
from legalforecast.reporting.pilot_readiness import (
    build_pilot_readiness_report,
    render_pilot_readiness_markdown,
)
from legalforecast.selection.candidate_discovery import (
    discover_mtd_candidates,
    mtd_discovery_search_terms,
)
from legalforecast.selection.case_mix_diagnostics import (
    CaseMixCandidate,
    DocumentCompleteness,
    build_case_mix_diagnostics,
)
from legalforecast.selection.eligibility import (
    ContaminationMetadata,
    ContaminationRisk,
    ModelRunMetadata,
    PressPublicityTag,
    SeriesCaseTiming,
    TrainingCutoffStatus,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionStage,
    merge_exclusion_ledger_records,
)
from legalforecast.selection.motion_linkage import link_mtd_dispositions
from legalforecast.unitization.construct_units import (
    StageAConstructionInput,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    UnitizationReviewReason,
    construct_stage_a_units,
)
from legalforecast.unitization.review import (
    UnitizationReviewError,
    apply_unitization_reviews,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)

JsonRecord = dict[str, Any]
CommandHandler = Callable[[argparse.Namespace], int]


class CommandError(RuntimeError):
    """Raised when CLI inputs are invalid or incomplete."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast",
        description="LegalForecast-MTD benchmark utilities.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"legalforecast-mtd {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    discover = subparsers.add_parser(
        "discover",
        help="Find MTD candidates from docket-entry search records.",
    )
    discover.add_argument("--input", type=Path, required=True)
    discover.add_argument("--output", type=Path, required=True)
    discover.add_argument("--dry-run", action="store_true")
    discover.add_argument("--print-search-terms", action="store_true")
    discover.set_defaults(handler=_cmd_discover)

    retrieve = subparsers.add_parser(
        "retrieve",
        help="Retrieve candidate dockets and source-document provenance.",
    )
    retrieve.add_argument("--candidates", type=Path, required=True)
    retrieve.add_argument("--output", type=Path, required=True)
    retrieve.add_argument("--case-dev-fixture", type=Path)
    retrieve.add_argument("--live", action="store_true")
    retrieve.add_argument("--dry-run", action="store_true")
    retrieve.set_defaults(handler=_cmd_retrieve)

    smoke = subparsers.add_parser(
        "case-dev-smoke",
        help="Run a bounded case.dev Phase 0 smoke pass and write markdown.",
    )
    smoke.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Markdown report path to write, usually tmp/case-dev-smoke.md.",
    )
    smoke.add_argument(
        "--case-dev-fixture",
        type=Path,
        help="Replay recorded case.dev JSONL responses without network access.",
    )
    smoke.add_argument(
        "--live",
        action="store_true",
        help="Use the live case.dev API with CASE_DEV_API_KEY from the environment.",
    )
    smoke.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the planned report skeleton without fixture or live requests.",
    )
    smoke.add_argument(
        "--query-term",
        action="append",
        dest="query_terms",
        help=(
            "Docket search term to run; repeat to override the default optimized "
            "MTD decision-term set."
        ),
    )
    smoke.add_argument(
        "--date-window-start",
        help="Inclusive filed_at lower bound for counted docket hits, YYYY-MM-DD.",
    )
    smoke.add_argument(
        "--date-window-end",
        help="Inclusive filed_at upper bound for counted docket hits, YYYY-MM-DD.",
    )
    smoke.add_argument(
        "--per-query-limit",
        type=int,
        default=10,
        help="Maximum docket-entry search hits requested for each query term.",
    )
    smoke.add_argument(
        "--candidate-retrieval-limit",
        type=int,
        default=10,
        help="Maximum discovered candidate cases to retrieve and summarize.",
    )
    smoke.set_defaults(handler=_cmd_case_dev_smoke)

    extract = subparsers.add_parser(
        "extract",
        help="Extract PDF text artifacts for source documents.",
    )
    extract.add_argument("--documents", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--text-output-dir", type=Path)
    extract.add_argument("--dry-run", action="store_true")
    extract.set_defaults(handler=_cmd_extract)

    link = subparsers.add_parser(
        "link",
        help="Link target MTD docket entries to written dispositions.",
    )
    link.add_argument("--retrievals", type=Path, required=True)
    link.add_argument("--output", type=Path, required=True)
    link.add_argument("--dry-run", action="store_true")
    link.set_defaults(handler=_cmd_link)

    unitize = subparsers.add_parser(
        "unitize",
        help="Construct frozen Stage A prediction units.",
    )
    unitize.add_argument("--input", type=Path, required=True)
    unitize.add_argument("--output", type=Path, required=True)
    unitize.add_argument("--dry-run", action="store_true")
    unitize.set_defaults(handler=_cmd_unitize)

    label = subparsers.add_parser(
        "label",
        help="Create Stage B outcome labels for frozen units.",
    )
    label.add_argument("--input", type=Path, required=True)
    label.add_argument("--output", type=Path, required=True)
    label.add_argument("--dry-run", action="store_true")
    label.set_defaults(handler=_cmd_label)

    packet_alias = subparsers.add_parser(
        "packet-build",
        help="Build model-visible packet artifacts from frozen inputs.",
    )
    _add_packet_build_arguments(packet_alias)

    packet = subparsers.add_parser(
        "packet",
        help="Packet artifact commands.",
    )
    packet_subparsers = packet.add_subparsers(dest="packet_command", metavar="COMMAND")
    packet_build = packet_subparsers.add_parser(
        "build",
        help="Build model-visible packet artifacts from frozen inputs.",
    )
    _add_packet_build_arguments(packet_build)

    model_run_alias = subparsers.add_parser(
        "model-run",
        help="Run no-network fixture solvers over packet artifacts.",
    )
    _add_model_run_arguments(model_run_alias)

    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluation run commands.",
    )
    eval_subparsers = eval_parser.add_subparsers(
        dest="eval_command",
        metavar="COMMAND",
    )
    eval_run = eval_subparsers.add_parser(
        "run",
        help="Run no-network fixture solvers over packet artifacts.",
    )
    _add_model_run_arguments(eval_run)
    eval_run_case = eval_subparsers.add_parser(
        "run-case",
        help="Run one isolated official model-packet shard.",
    )
    _add_eval_run_case_arguments(eval_run_case)

    score = subparsers.add_parser(
        "score",
        help="Parse model outputs and score them against locked labels.",
    )
    score.add_argument("--runs", type=Path, required=True)
    score.add_argument("--labels", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    score.add_argument("--unit-scores-output", type=Path)
    score.add_argument("--base-rate", type=float)
    score.add_argument("--dry-run", action="store_true")
    score.set_defaults(handler=_cmd_score)

    report = subparsers.add_parser(
        "report",
        help="Render leaderboard artifacts from score summaries.",
    )
    report.add_argument("--scores", type=Path, required=True)
    report.add_argument("--output-dir", type=Path, required=True)
    report.add_argument("--accounting", type=Path)
    report.add_argument("--title", default="LegalForecast-MTD Leaderboard")
    report.add_argument("--bootstrap-replicates", type=int, default=5000)
    report.add_argument("--bootstrap-seed", type=int, default=20260514)
    report.add_argument("--dry-run", action="store_true")
    report.set_defaults(handler=_cmd_report)

    publish = subparsers.add_parser(
        "publish",
        help="Aggregate and render official publication artifacts.",
    )
    publish_subparsers = publish.add_subparsers(
        dest="publish_command",
        metavar="COMMAND",
    )
    publish_subparsers.add_parser(
        "aggregate",
        add_help=False,
        help="Aggregate downloaded official per-case artifacts locally.",
    )
    publish_site = publish_subparsers.add_parser(
        "site",
        help="Render the official results site from public aggregate artifacts.",
    )
    publish_site.add_argument(
        "--official-artifacts-dir",
        type=Path,
        required=True,
        help="Public directory written by publish aggregate.",
    )
    publish_site.add_argument("--output-dir", type=Path, required=True)
    publish_site.set_defaults(handler=_cmd_publish_site)

    fixture_alias = subparsers.add_parser(
        "fixture-e2e",
        help="Run a deterministic no-network benchmark fixture end to end.",
    )
    _add_fixture_e2e_arguments(fixture_alias)

    fixture = subparsers.add_parser(
        "fixture",
        help="Fixture workflow commands.",
    )
    fixture_subparsers = fixture.add_subparsers(
        dest="fixture_command",
        metavar="COMMAND",
    )
    fixture_e2e = fixture_subparsers.add_parser(
        "e2e",
        help="Run a deterministic no-network benchmark fixture end to end.",
    )
    _add_fixture_e2e_arguments(fixture_e2e)

    pilot = subparsers.add_parser(
        "pilot",
        help="Pilot readiness commands.",
    )
    pilot_subparsers = pilot.add_subparsers(dest="pilot_command", metavar="COMMAND")
    pilot_readiness = pilot_subparsers.add_parser(
        "readiness",
        help="Render a post-feasibility pilot/readiness report.",
    )
    _add_pilot_readiness_arguments(pilot_readiness)
    pilot_fallback = pilot_subparsers.add_parser(
        "fallback-reconstruction",
        help="Render or run an optional bounded fallback reconstruction pilot.",
    )
    _add_pilot_fallback_arguments(pilot_fallback)

    add_multiharness_parser(subparsers)

    batch_002 = subparsers.add_parser(
        "batch-002",
        help=(
            "Cycle 1 batch-002 decision-first RECAP REST v4 acquisition driver "
            "(discover / seed-direct-search / observe / seed-batch-001-leads / "
            "snapshot)."
        ),
    )
    batch_002_subparsers = batch_002.add_subparsers(
        dest="batch_002_command",
        metavar="COMMAND",
    )
    batch_002_discover = batch_002_subparsers.add_parser(
        "discover",
        help=(
            "Attach batch-002 and materialize each frozen decision-first term's "
            "own top-K, printing a discovery funnel."
        ),
    )
    _add_batch_002_discover_arguments(batch_002_discover)
    batch_002_observe = batch_002_subparsers.add_parser(
        "observe",
        help=(
            "Reconstruct and strictly screen every candidate lacking a current "
            "observation; token-gated, politely paced, resumable."
        ),
    )
    _add_batch_002_observe_arguments(batch_002_observe)
    batch_002_seed = batch_002_subparsers.add_parser(
        "seed-batch-001-leads",
        help=(
            "Seed batch-001 Case.dev enrichment-failure dockets into batch-002 "
            "as re-observation leads (idempotent)."
        ),
    )
    _add_batch_002_seed_arguments(batch_002_seed)
    batch_002_direct_seed = batch_002_subparsers.add_parser(
        "seed-direct-search",
        help=(
            "Transfer a saturated direct CourtListener search docket union into "
            "a source-bound authenticated REST screening batch without network use."
        ),
    )
    _add_batch_002_direct_seed_arguments(batch_002_direct_seed)
    batch_002_snapshot = batch_002_subparsers.add_parser(
        "snapshot",
        help=(
            "Publish and verify one immutable, saturated REST acquisition "
            "snapshot after every candidate is terminal."
        ),
    )
    _add_batch_002_snapshot_arguments(batch_002_snapshot)

    acquisition = subparsers.add_parser(
        "acquisition",
        help="Production acquisition pipeline commands.",
        description=(
            "CourtListener REST is the only production final authority for paid "
            "document gaps. Legacy Case.dev paid commands are disabled for live use."
        ),
    )
    acquisition_subparsers = acquisition.add_subparsers(
        dest="acquisition_command",
        metavar="COMMAND",
    )
    acquisition_init_cycle = acquisition_subparsers.add_parser(
        "init-cycle",
        help=(
            "Freeze or verify the acquisition cycle identity without contacting "
            "any provider."
        ),
        description=(
            "Freeze or verify the acquisition cycle identity without contacting "
            "any provider. This command performs no Firecrawl, Case.dev, "
            "CourtListener, RECAP, or PACER activity."
        ),
    )
    _add_acquisition_init_cycle_arguments(acquisition_init_cycle)
    acquisition_discover_case_dev = acquisition_subparsers.add_parser(
        "discover-case-dev",
        help=(
            "Materialize an exploratory Case.dev case/party metadata lead pool "
            "without purchasing documents; this is not anchored disposition "
            "discovery."
        ),
    )
    _add_acquisition_discover_case_dev_arguments(acquisition_discover_case_dev)
    acquisition_discover_firecrawl_recap = acquisition_subparsers.add_parser(
        "discover-firecrawl-recap",
        help=(
            "Discover anchored MTD docket entries from CourtListener RECAP "
            "through a cycle-budgeted Firecrawl route."
        ),
    )
    _add_acquisition_discover_firecrawl_recap_arguments(
        acquisition_discover_firecrawl_recap
    )
    acquisition_discover_firecrawl_recap_decisions = acquisition_subparsers.add_parser(
        "discover-firecrawl-recap-decisions",
        help=(
            "Recover frozen decision-first type=r CourtListener results "
            "through cycle-budgeted Firecrawl for free Case.dev enrichment."
        ),
        description=(
            "Scrape the frozen eight decision-first CourtListener type=r "
            "HTML searches only through Firecrawl. Emits docket IDs accepted "
            "by acquisition enrich-recap-case-dev, then the existing ranked "
            "docket acquisition and strict screen; no CourtListener API token, "
            "PACER fee acknowledgment, or screening relaxation is used."
        ),
    )
    _add_acquisition_discover_firecrawl_recap_arguments(
        acquisition_discover_firecrawl_recap_decisions,
        decision_first=True,
    )
    acquisition_project_firecrawl_recap_checkpoint = acquisition_subparsers.add_parser(
        "project-firecrawl-recap-checkpoint",
        help=(
            "Recover verified durable Firecrawl RECAP search pages into "
            "explicitly partial entry and potential-docket checkpoints."
        ),
    )
    _add_acquisition_project_firecrawl_recap_checkpoint_arguments(
        acquisition_project_firecrawl_recap_checkpoint
    )
    acquisition_enrich_recap_case_dev = acquisition_subparsers.add_parser(
        "enrich-recap-case-dev",
        help=(
            "Enrich discovered CourtListener docket IDs through free Case.dev "
            "includeEntries lookups and rank verified free-document coverage."
        ),
    )
    _add_acquisition_enrich_recap_case_dev_arguments(acquisition_enrich_recap_case_dev)
    acquisition_acquire_ranked_dockets = acquisition_subparsers.add_parser(
        "acquire-ranked-firecrawl-dockets",
        help=(
            "Acquire free-ranked RECAP dockets through the canonical Firecrawl "
            "ledger and complete newest-first pagination."
        ),
    )
    _add_acquisition_acquire_ranked_dockets_arguments(
        acquisition_acquire_ranked_dockets
    )
    acquisition_discover_courtlistener = acquisition_subparsers.add_parser(
        "discover-courtlistener",
        help=(
            "Discover live post-anchor CourtListener MTD candidates and emit "
            "screened cases."
        ),
    )
    _add_acquisition_discover_courtlistener_arguments(
        acquisition_discover_courtlistener
    )
    acquisition_materialize_courtlistener_snapshot = acquisition_subparsers.add_parser(
        "materialize-courtlistener-snapshot",
        help=(
            "Verify a completed direct CourtListener discovery transcript and "
            "publish a complete saturated cycle snapshot without provider access."
        ),
        description=(
            "Provider-free materialization of hash-bound discover-courtlistener "
            "outputs. Limit-bound or unreconciled discovery fails closed."
        ),
    )
    _add_acquisition_materialize_courtlistener_snapshot_arguments(
        acquisition_materialize_courtlistener_snapshot
    )
    acquisition_union_screening_snapshots = acquisition_subparsers.add_parser(
        "union-screening-snapshots",
        help=(
            "Publish one provider-free saturated union of two or more "
            "same-cycle screening snapshots."
        ),
    )
    _add_acquisition_union_screening_snapshots_arguments(
        acquisition_union_screening_snapshots
    )
    acquisition_funnel_report = acquisition_subparsers.add_parser(
        "funnel-report",
        help="Reconcile discovery exclusions into a versioned acquisition funnel.",
    )
    _add_acquisition_funnel_report_arguments(acquisition_funnel_report)
    acquisition_generate_labeling_policy = acquisition_subparsers.add_parser(
        "generate-labeling-policy",
        help=(
            "Generate the immutable pre-labeling policy without freezing or "
            "dispatching a cycle."
        ),
    )
    _add_acquisition_generate_labeling_policy_arguments(
        acquisition_generate_labeling_policy
    )
    acquisition_verify_labeling_policy = acquisition_subparsers.add_parser(
        "verify-labeling-policy",
        help="Verify a pre-labeling policy without touching official freeze state.",
    )
    _add_acquisition_verify_labeling_policy_arguments(
        acquisition_verify_labeling_policy
    )
    acquisition_generate_cohort_policy = acquisition_subparsers.add_parser(
        "generate-cohort-policy",
        help="Generate a hash-bound cohort precommitment from supplied decisions.",
    )
    _add_generate_cohort_policy_arguments(acquisition_generate_cohort_policy)
    acquisition_verify_cohort_policy = acquisition_subparsers.add_parser(
        "verify-cohort-policy",
        help="Verify a cohort precommitment and optional expected hash.",
    )
    _add_verify_cohort_policy_arguments(acquisition_verify_cohort_policy)
    acquisition_generate_purchase_policy = acquisition_subparsers.add_parser(
        "generate-purchase-policy",
        help=(
            "Generate an immutable Case.dev document-purchase cap and canonical "
            "journal policy from approved decisions."
        ),
    )
    _add_generate_purchase_policy_arguments(acquisition_generate_purchase_policy)
    acquisition_init_purchase_ledger = acquisition_subparsers.add_parser(
        "init-purchase-ledger",
        help=(
            "Exclusively initialize the policy-bound purchase ledger without "
            "contacting any provider or acknowledging fees."
        ),
        description=(
            "Create exactly one new canonical purchase ledger under its lock, "
            "bind it to the verified purchase and cohort policies, and emit an "
            "authenticated initialization receipt. This command performs no "
            "provider request, fee acknowledgment, or purchase."
        ),
    )
    _add_init_purchase_ledger_arguments(acquisition_init_purchase_ledger)
    acquisition_build_clearance_replacement_frontier = (
        acquisition_subparsers.add_parser(
            "build-clearance-replacement-frontier",
            help=(
                "Freeze the complete post-clearance replacement frontier, "
                "source hashes, case-mix caps, and initial selected cohort."
            ),
        )
    )
    _add_build_clearance_replacement_frontier_arguments(
        acquisition_build_clearance_replacement_frontier
    )
    acquisition_plan_clearance_replacements = acquisition_subparsers.add_parser(
        "plan-clearance-replacements",
        help=(
            "Append replay-safe quarantine replacement decisions and emit a "
            "narrow next-iteration plan without any provider request or purchase."
        ),
    )
    _add_plan_clearance_replacements_arguments(acquisition_plan_clearance_replacements)
    acquisition_generate_recap_fetch_broker_policy = acquisition_subparsers.add_parser(
        "generate-recap-fetch-broker-policy",
        help=(
            "Derive an immutable secure-gate RECAP Fetch allowlist from a "
            "verified purchase policy and executable purchase plan. CourtListener "
            "REST is the paid-gap authority; Case.dev remains noncharging "
            "search/enrichment only and is never purchase authority."
        ),
    )
    _add_generate_recap_fetch_broker_policy_arguments(
        acquisition_generate_recap_fetch_broker_policy
    )
    acquisition_reconcile_purchase = acquisition_subparsers.add_parser(
        "reconcile-purchase",
        help=(
            "Record provider billing evidence or a cap-counted write-off for an "
            "ambiguous document purchase."
        ),
    )
    _add_reconcile_purchase_arguments(acquisition_reconcile_purchase)
    acquisition_export_cohort_observations = acquisition_subparsers.add_parser(
        "export-cohort-observations",
        help="Append complete cycle-store snapshots to the observation manifest.",
    )
    _add_export_cohort_observations_arguments(acquisition_export_cohort_observations)
    acquisition_verify_cohort_observations = acquisition_subparsers.add_parser(
        "verify-cohort-observations",
        help="Verify the append-only cohort observation hash chain.",
    )
    _add_verify_cohort_observations_arguments(acquisition_verify_cohort_observations)
    acquisition_fetch_firecrawl = acquisition_subparsers.add_parser(
        "fetch-firecrawl-dockets",
        help=(
            "Resolve Case.dev candidates to CourtListener URLs and fetch bounded "
            "public docket HTML through Firecrawl."
        ),
    )
    _add_acquisition_fetch_firecrawl_arguments(acquisition_fetch_firecrawl)
    acquisition_screen_firecrawl = acquisition_subparsers.add_parser(
        "screen-firecrawl-dockets",
        help=(
            "Apply strict MTD eligibility, linkage, contamination, and privacy "
            "gates to persisted Firecrawl docket pages."
        ),
    )
    _add_acquisition_screen_firecrawl_arguments(acquisition_screen_firecrawl)
    acquisition_replay_screening = acquisition_subparsers.add_parser(
        "replay-screening-snapshots",
        help=(
            "Re-screen verified historical snapshots into one target-cycle "
            "snapshot without contacting any provider."
        ),
        description=(
            "Verify a source assembly and optional target-cycle snapshots, copy "
            "their committed raw docket HTML into a synthetic target batch, and "
            "run the current strict screen. This command never contacts a provider "
            "and never performs paid activity."
        ),
    )
    _add_acquisition_replay_screening_arguments(acquisition_replay_screening)
    acquisition_quarantine_snapshot = acquisition_subparsers.add_parser(
        "quarantine-orphan-snapshot",
        help=(
            "Verify and optionally atomically quarantine an unregistered snapshot "
            "directory without changing the cycle store."
        ),
    )
    _add_acquisition_quarantine_snapshot_arguments(acquisition_quarantine_snapshot)
    acquisition_bridge_pacer_gaps = acquisition_subparsers.add_parser(
        "bridge-pacer-gaps",
        help=(
            "Resolve paid gaps to authoritative CourtListener RECAP document IDs; "
            "Case.dev fixture support is legacy compatibility only."
        ),
    )
    _add_acquisition_bridge_pacer_gaps_arguments(acquisition_bridge_pacer_gaps)
    acquisition_filter_core = acquisition_subparsers.add_parser(
        "filter-core-documents",
        help="Build missing-core purchase inputs from setup-runner relevance JSONL.",
    )
    _add_acquisition_filter_core_documents_arguments(acquisition_filter_core)
    acquisition_plan = acquisition_subparsers.add_parser(
        "plan",
        help="Plan missing-core paid recovery from core-document filter results.",
    )
    _add_acquisition_plan_arguments(acquisition_plan)
    acquisition_prepare_target_cohort = acquisition_subparsers.add_parser(
        "prepare-target-cohort",
        help=(
            "Prepare the full resolved pool and a provisional pre-clearance "
            "budget for an explicit target size."
        ),
        description=(
            "Starting from a complete saturated screened snapshot, carry every "
            "viable candidate through the noncharging public-first acquisition "
            "chain, resolve document gaps through CourtListener REST, and retain "
            "a full untruncated per-candidate frontier. --target-case-count is "
            "required and hash-bound. Case.dev is permitted upstream only for an "
            "equivalent free lookup; Firecrawl is permitted only for a documented "
            "CourtListener decision-search surface gap. This command never "
            "purchases documents or acknowledges fees."
        ),
    )
    _add_acquisition_prepare_target_cohort_arguments(acquisition_prepare_target_cohort)
    acquisition_materialize_target_frontier = acquisition_subparsers.add_parser(
        "materialize-target-cohort-frontier",
        help=(
            "Build a verified full frontier from a completed preparation root "
            "without rerunning providers."
        ),
        description=(
            "Verify an immutable completed prepare-target-100 or prepare-target-"
            "cohort root, including its summary, self-hashed config, exhaustive "
            "stage commitments, resolved success run card, and snapshot lineage. "
            "Then write the full self-hashed candidate frontier to a separate "
            "output root. This command never constructs a provider client, "
            "downloads a document, acknowledges fees, or purchases anything."
        ),
    )
    _add_acquisition_materialize_target_frontier_arguments(
        acquisition_materialize_target_frontier
    )
    acquisition_prepare_target_100 = acquisition_subparsers.add_parser(
        "prepare-target-100",
        help=(
            "Prepare the full resolved pool and a provisional pre-clearance "
            "100-case budget."
        ),
        description=(
            "Starting from the complete saturated screened snapshot produced by "
            "batch-002 discover, observe, and snapshot, run the resumable public-"
            "first acquisition chain, resolve every paid gap through CourtListener "
            "REST, and emit disclosure-review inputs plus a provisional 100-case "
            "budget. The exact downstream cohort is frozen only by "
            "project-target-cohort after authenticated clearance. Case.dev may be "
            "used upstream only where its free API is equivalent, and Firecrawl "
            "remains a compatibility fallback. This command performs no discovery "
            "and never purchases documents."
        ),
    )
    _add_acquisition_prepare_target_100_arguments(acquisition_prepare_target_100)
    acquisition_project_target_cohort = acquisition_subparsers.add_parser(
        "project-target-cohort",
        help=("Freeze an exact post-clearance cheapest cohort for downstream stages."),
        description=(
            "Consume the full CourtListener-resolved pool plus authenticated "
            "disclosure clearance, remove quarantined cases, recompute the "
            "cheapest complete frontier, and emit exact hash-bound downstream "
            "artifacts. This command never calls a provider or purchases documents."
        ),
    )
    _add_acquisition_project_target_cohort_arguments(acquisition_project_target_cohort)
    acquisition_extend_target_cohort = acquisition_subparsers.add_parser(
        "extend-target-cohort",
        help="Retain an exact 100-case prefix and add 50 omitted candidates.",
        description=(
            "Verify a frozen target-100 projection against the full resolved "
            "post-clearance pool, preserve every selected-candidate base JSONL "
            "byte as a prefix, "
            "rank only the eligible omitted frontier, and emit an exact combined "
            "150-case budget. This command never calls a provider, purchases a "
            "document, or acknowledges fees."
        ),
    )
    _add_acquisition_extend_target_cohort_arguments(acquisition_extend_target_cohort)
    acquisition_public_downloads = acquisition_subparsers.add_parser(
        "plan-public-downloads",
        help="Plan free public CourtListener/RECAP packet-document downloads.",
    )
    _add_acquisition_plan_public_downloads_arguments(acquisition_public_downloads)
    acquisition_download = acquisition_subparsers.add_parser(
        "download-free",
        help="Download free public docket documents.",
    )
    _add_acquisition_download_free_arguments(acquisition_download)
    acquisition_purchase = acquisition_subparsers.add_parser(
        "purchase-missing",
        help=(
            "DISABLED for live use: legacy Case.dev/PACER purchase compatibility "
            "fixtures only."
        ),
    )
    _add_acquisition_purchase_missing_arguments(acquisition_purchase)
    acquisition_recap_fetch_purchase = acquisition_subparsers.add_parser(
        "purchase-missing-recap-fetch",
        help=(
            "Execute individual-document purchases through a budget-enforcing "
            "CourtListener RECAP Fetch broker."
        ),
    )
    _add_acquisition_purchase_missing_recap_fetch_arguments(
        acquisition_recap_fetch_purchase
    )
    acquisition_docket_fetch_plan = acquisition_subparsers.add_parser(
        "plan-docket-live-fetches",
        help=("DEPRECATED: build a no-provider legacy Case.dev docket-fetch frontier."),
    )
    _add_acquisition_plan_docket_live_fetches_arguments(acquisition_docket_fetch_plan)
    acquisition_docket_fetch = acquisition_subparsers.add_parser(
        "execute-docket-live-fetches",
        help=("DISABLED for live use: legacy Case.dev docket-refresh fixtures only."),
    )
    _add_acquisition_execute_docket_live_fetches_arguments(acquisition_docket_fetch)
    acquisition_recover_purchased = acquisition_subparsers.add_parser(
        "recover-purchased",
        help=("Recover already-purchased case.dev documents into parser manifests."),
    )
    _add_acquisition_recover_purchased_arguments(acquisition_recover_purchased)
    acquisition_merge_downloads = acquisition_subparsers.add_parser(
        "merge-download-manifests",
        help=("Merge free and purchased document manifests for parser planning."),
    )
    _add_acquisition_merge_download_manifests_arguments(acquisition_merge_downloads)
    acquisition_bind_component = acquisition_subparsers.add_parser(
        "bind-acquisition-component",
        help=(
            "Bind one immutable downstream artifact root into a snapshot-derived "
            "component provenance chain."
        ),
    )
    _add_acquisition_bind_component_arguments(acquisition_bind_component)
    acquisition_assemble_cycle = acquisition_subparsers.add_parser(
        "assemble-cycle-acquisition",
        help=(
            "Assemble immutable acquisition batches into one content-addressed "
            "cycle root."
        ),
    )
    _add_acquisition_assemble_cycle_arguments(acquisition_assemble_cycle)
    acquisition_clearance = acquisition_subparsers.add_parser(
        "clear-disclosures",
        help="Scan and record hash-bound disclosure clearance per document.",
    )
    _add_acquisition_disclosure_clearance_arguments(acquisition_clearance)
    acquisition_parse_plan = acquisition_subparsers.add_parser(
        "plan-parse-documents",
        help="Plan Markdown parser requests from downloaded document manifests.",
    )
    _add_acquisition_plan_parse_documents_arguments(acquisition_parse_plan)
    acquisition_parse = acquisition_subparsers.add_parser(
        "parse-documents",
        help="Convert acquired documents to Markdown parser artifacts.",
    )
    _add_acquisition_parse_documents_arguments(acquisition_parse)
    acquisition_llm_unitize = acquisition_subparsers.add_parser(
        "llm-unitize",
        help="Use a registry-backed LLM to construct frozen Stage A units.",
    )
    _add_acquisition_llm_unitize_arguments(acquisition_llm_unitize)
    acquisition_review_stage_a = acquisition_subparsers.add_parser(
        "llm-review-stage-a",
        help="Flag structural Stage A defects without rewriting frozen units.",
    )
    _add_acquisition_llm_review_stage_a_arguments(acquisition_review_stage_a)
    acquisition_apply_unitization_review = acquisition_subparsers.add_parser(
        "apply-unitization-review",
        help="Apply checked-in Stage A adjudications and finalize prediction units.",
    )
    _add_acquisition_apply_unitization_review_arguments(
        acquisition_apply_unitization_review
    )
    acquisition_llm_label = acquisition_subparsers.add_parser(
        "llm-label",
        help="Use registry-backed LLM judges to create Stage B labels.",
    )
    _add_acquisition_llm_label_arguments(acquisition_llm_label)
    acquisition_plan_label_audit = acquisition_subparsers.add_parser(
        "plan-label-audit",
        help="Freeze one stratified cycle-level audit sample after Stage B labeling.",
    )
    _add_acquisition_plan_label_audit_arguments(acquisition_plan_label_audit)
    acquisition_apply_lawyer_review = acquisition_subparsers.add_parser(
        "apply-lawyer-review",
        help="Apply checked-in lawyer adjudications to pending Stage B labels.",
    )
    _add_acquisition_apply_lawyer_review_arguments(acquisition_apply_lawyer_review)
    acquisition_packet_inputs = acquisition_subparsers.add_parser(
        "plan-packet-inputs",
        help="Plan packet-build and private-store inputs from acquisition manifests.",
    )
    _add_acquisition_plan_packet_inputs_arguments(acquisition_packet_inputs)
    acquisition_build = acquisition_subparsers.add_parser(
        "build-packets",
        help="Build final model packets from acquisition artifacts.",
    )
    _add_acquisition_build_packets_arguments(acquisition_build)
    acquisition_finalize = acquisition_subparsers.add_parser(
        "finalize-corpus",
        help="Consolidate exclusions and verify the clean labeled packet corpus.",
    )
    _add_acquisition_finalize_corpus_arguments(acquisition_finalize)
    acquisition_merge = acquisition_subparsers.add_parser(
        "merge-artifacts",
        help="Merge packet-buildable acquisition roots for a pilot cycle.",
    )
    _add_acquisition_merge_artifacts_arguments(acquisition_merge)

    return parser


def _add_packet_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ablation",
        choices=[ablation.value for ablation in PacketAblation],
        default=PacketAblation.FULL_PACKET.value,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(handler=_cmd_packet_build)


def _add_model_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accounting-output", type=Path)
    parser.add_argument("--solver-id", default="offline:fixture")
    mock_output_group = parser.add_mutually_exclusive_group(required=True)
    mock_output_group.add_argument(
        "--mock-output",
        help="Literal offline fixture solver output text.",
    )
    mock_output_group.add_argument(
        "--mock-output-file",
        type=Path,
        help="File containing offline fixture solver output text.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(handler=_cmd_model_run)


def _add_eval_run_case_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Run-input manifest path, file:// URI, or s3:// URI.",
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--ablation",
        choices=[ablation.value for ablation in PacketAblation],
        default=PacketAblation.FULL_PACKET.value,
    )
    parser.add_argument(
        "--packet-store-root",
        help="Local root, file:// root, or s3:// root for manifest object keys.",
    )
    parser.add_argument(
        "--expected-packet-object-key",
        help=(
            "Exact model-packets/ object key committed by the pre-fanout matrix; "
            "required with --expected-packet-sha256 for live runs."
        ),
    )
    parser.add_argument(
        "--expected-packet-sha256",
        help=(
            "Exact lowercase SHA-256 committed by the pre-fanout matrix; required "
            "with --expected-packet-object-key for live runs."
        ),
    )
    parser.add_argument(
        "--results-store-root",
        help="Optional local root, file:// root, or s3:// root for safe outputs.",
    )
    parser.add_argument(
        "--repeat-count",
        type=int,
        default=1,
        help=(
            "Number of independent provider calls to run for this case/model row. "
            "Use values greater than 1 only for a pre-budgeted repeat-sampling "
            "subset."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-id", default="offline:fixture")
    parser.add_argument(
        "--backend",
        choices=[backend.value for backend in PerCaseExecutionBackend],
        default=PerCaseExecutionBackend.FIXTURE.value,
        help=(
            "Execution backend: fixture for no-network tests, live for "
            "registry-backed provider calls."
        ),
    )
    parser.add_argument(
        "--model-registry",
        help="Frozen model registry path, file:// URI, or s3:// URI.",
    )
    parser.add_argument(
        "--model-key",
        help="Registry key in provider:model_id form.",
    )
    mock_output_group = parser.add_mutually_exclusive_group()
    mock_output_group.add_argument(
        "--mock-output",
        help=(
            "Literal offline fixture solver output used by the dependency-light runner."
        ),
    )
    mock_output_group.add_argument(
        "--mock-output-file",
        type=Path,
        help=(
            "File containing offline fixture solver output used by the "
            "dependency-light runner."
        ),
    )
    parser.add_argument("--max-tool-calls", type=int, default=10)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-provider-request timeout for the registry-backed live model call.",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help=(
            "Reuse a complete matching per-case output already present in "
            "--results-store-root or --output-dir instead of calling the provider."
        ),
    )
    parser.add_argument(
        "--no-docket-tool",
        action="store_true",
        help="Disable the controlled docket tool for this packet shard.",
    )
    parser.add_argument(
        "--evaluation-timestamp",
        help="Deterministic UTC timestamp for accounting artifacts.",
    )
    parser.set_defaults(handler=_cmd_eval_run_case)


def _add_fixture_e2e_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(handler=_cmd_fixture_e2e)


def _add_pilot_readiness_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--smoke-report",
        type=Path,
        required=True,
        help="Markdown report from legalforecast case-dev-smoke.",
    )
    parser.add_argument(
        "--fixture-output-dir",
        type=Path,
        help="Optional legalforecast fixture e2e output directory to inspect.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Markdown pilot/readiness report path to write.",
    )
    parser.add_argument(
        "--generated-at",
        help="Deterministic report timestamp, ISO 8601. Defaults to now.",
    )
    parser.set_defaults(handler=_cmd_pilot_readiness)


def _add_pilot_fallback_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--smoke-report",
        type=Path,
        required=True,
        help="Markdown report from legalforecast case-dev-smoke.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Markdown optional fallback reconstruction pilot report path to write.",
    )
    parser.add_argument(
        "--attempt-limit",
        type=int,
        default=10,
        help="Maximum fallback-needed case.dev candidates to evaluate.",
    )
    parser.add_argument(
        "--courtlistener-fixture",
        type=Path,
        help="Replay recorded CourtListener JSONL responses without network access.",
    )
    parser.add_argument(
        "--live-courtlistener",
        action="store_true",
        help=(
            "Attempt live CourtListener reconstruction when fallback is explicitly "
            "enabled and a token is configured."
        ),
    )
    parser.add_argument(
        "--courtlistener-page-size",
        type=int,
        default=100,
        help="CourtListener docket-entry page size for live or fixture attempts.",
    )
    parser.add_argument(
        "--generated-at",
        help="Deterministic report timestamp, ISO 8601. Defaults to now.",
    )
    parser.set_defaults(handler=_cmd_pilot_fallback)


def _add_acquisition_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Root directory for acquisition artifacts, logs, and run cards.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the stage. Omitted means dry-run planning only.",
    )
    parser.add_argument(
        "--log-output",
        type=Path,
        help="Structured JSONL stage log. Defaults under --output-root/logs/.",
    )
    parser.add_argument(
        "--run-card-output",
        type=Path,
        help=(
            "Machine-readable stage run card. Defaults under --output-root/run-cards/."
        ),
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        default=True,
        help="Reuse existing deterministic artifacts when the stage supports it.",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Fail instead of reusing existing deterministic artifacts.",
    )


def _add_acquisition_init_cycle_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--eligibility-anchor",
        required=True,
        help=(
            "Immutable first-written-disposition eligibility anchor as an ISO "
            "date (YYYY-MM-DD). Reusing a store with a different anchor fails."
        ),
    )
    parser.add_argument(
        "--cycle-store",
        type=Path,
        help=(
            "Cycle acquisition SQLite store. Defaults to "
            "<output-root>/cycle-acquisition.sqlite3."
        ),
    )
    parser.add_argument(
        "--identity-output",
        type=Path,
        help=(
            "Hash-bound cycle identity JSON. Defaults to "
            "<output-root>/cycle-identity.json."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_init_cycle)


def _add_acquisition_plan_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--core-filter-results", type=Path, required=True)
    parser.add_argument("--budget-plan-output", type=Path)
    parser.add_argument(
        "--exclusions-output",
        type=Path,
        help="Ledgered per-case planning exclusions; defaults under output root.",
    )
    parser.add_argument("--max-missing-core-documents-per-case", type=int, default=24)
    parser.add_argument("--cost-per-document-usd", default="3.05")
    parser.add_argument("--max-projected-budget-usd", default="2250.00")
    parser.add_argument(
        "--target-case-count",
        type=int,
        help=(
            "Emit at most this many cheapest complete cases after exclusions; "
            "the plan records whether the requested count was met."
        ),
    )
    parser.add_argument(
        "--truncate-to-budget",
        action="store_true",
        help=(
            "Rank by missing-core purchase count and candidate ID, then emit only "
            "the largest deterministic frontier prefix within the projected cap."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_plan)


def _add_acquisition_prepare_target_100_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_prepare_target_arguments(parser)
    parser.set_defaults(handler=_cmd_acquisition_prepare_target_100)


def _add_acquisition_prepare_target_cohort_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_prepare_target_arguments(parser)
    parser.add_argument(
        "--target-case-count",
        type=int,
        required=True,
        help="Required positive target size, frozen into the preparation config.",
    )
    parser.set_defaults(handler=_cmd_acquisition_prepare_target_cohort)


def _add_acquisition_prepare_target_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help=(
            "Complete saturated snapshot from `batch-002 snapshot`; all viable "
            "rows are carried through authoritative resolution before ranking."
        ),
    )
    parser.add_argument(
        "--expected-cycle-hash",
        required=True,
        help="Exact cycle_hash committed by the batch-002 snapshot manifest.",
    )
    parser.add_argument("--raw-html-dir", type=Path)
    parser.add_argument("--use-embedded-entries", action="store_true")
    parser.add_argument("--cost-per-document-usd", default="3.05")
    parser.add_argument("--max-projected-budget-usd", default="2250.00")
    parser.add_argument("--max-missing-core-documents-per-case", type=int, default=24)
    public_source = parser.add_mutually_exclusive_group(required=True)
    public_source.add_argument("--live-public-download", action="store_true")
    public_source.add_argument("--fixture-documents", type=Path)
    bridge_source = parser.add_mutually_exclusive_group(required=True)
    bridge_source.add_argument(
        "--live-courtlistener",
        action="store_true",
        help=(
            "Use authenticated noncharging CourtListener REST as final paid-gap "
            "authority. Requires --request-ledger."
        ),
    )
    bridge_source.add_argument("--courtlistener-fixture", type=Path)
    parser.add_argument(
        "--request-ledger",
        type=Path,
        help="Shared CourtListener request ledger; required for live REST.",
    )
    parser.add_argument(
        "--courtlistener-rate-profile",
        choices=("base", "temporary-doubled"),
        default="base",
    )
    parser.add_argument("--request-budget-max-wait-seconds", type=float, default=120.0)
    parser.add_argument("--summary-output", type=Path)


def _add_acquisition_materialize_target_frontier_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--preparation-root",
        type=Path,
        required=True,
        help="Immutable completed target-100 or generic preparation root.",
    )
    parser.add_argument(
        "--preparation-summary",
        type=Path,
        required=True,
        help="Exact completed preparation summary committed by the success run card.",
    )
    parser.add_argument(
        "--preparation-config",
        type=Path,
        required=True,
        help="Exact self-hashed preparation config inside the immutable root.",
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        required=True,
        help="Exact snapshot manifest committed by the config and summary.",
    )
    parser.set_defaults(handler=_cmd_acquisition_materialize_target_frontier)


def _add_acquisition_project_target_cohort_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="Full CourtListener-resolved public-packet selection JSONL.",
    )
    parser.add_argument(
        "--case-relevance",
        type=Path,
        required=True,
        help="Full resolved-pool case relevance JSONL.",
    )
    parser.add_argument(
        "--download-manifest",
        type=Path,
        required=True,
        help="Acquired-document manifest whose bytes passed disclosure review.",
    )
    parser.add_argument(
        "--disclosure-clearance",
        type=Path,
        required=True,
        help="Authenticated hash-bound clearance rows for every manifest document.",
    )
    parser.add_argument(
        "--clearance-run-card",
        type=Path,
        required=True,
        help="Completed clear-disclosures run card binding the authenticated review.",
    )
    parser.add_argument(
        "--restriction-evidence",
        type=Path,
        required=True,
        help="Prepared docket-derived restriction evidence reviewed by clearance.",
    )
    parser.add_argument(
        "--preparation-summary",
        type=Path,
        required=True,
        help=(
            "Completed noncharging prepare-target-cohort summary, or the exact-100 "
            "compatibility summary, for the full pool."
        ),
    )
    parser.add_argument(
        "--preparation-config",
        type=Path,
        required=True,
        help=(
            "Frozen generic or exact-100 preparation config whose target and caps "
            "projection must preserve."
        ),
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        required=True,
        help="Immutable screened snapshot manifest committed by preparation.",
    )
    parser.add_argument("--target-case-count", type=int, default=100)
    parser.add_argument("--cost-per-document-usd", default="3.05")
    parser.add_argument("--max-projected-budget-usd", default="2250.00")
    parser.add_argument("--max-missing-core-documents-per-case", type=int, default=24)
    parser.set_defaults(handler=_cmd_acquisition_project_target_cohort)


def _add_acquisition_extend_target_cohort_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--base-cohort-root",
        type=Path,
        required=True,
        help="Executed exact target-100 project-target-cohort output root.",
    )
    parser.add_argument(
        "--preparation-root",
        type=Path,
        required=True,
        help="Completed immutable preparation root supplying the full pool.",
    )
    parser.add_argument("--preparation-summary", type=Path, required=True)
    parser.add_argument("--preparation-config", type=Path, required=True)
    parser.add_argument(
        "--full-candidate-frontier",
        type=Path,
        required=True,
        help="Provider-free self-hashed untruncated frontier artifact.",
    )
    parser.add_argument(
        "--frontier-run-card",
        type=Path,
        required=True,
        help="Completed materialize-target-cohort-frontier run card.",
    )
    parser.add_argument("--clearance-run-card", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--review-receipt", type=Path, required=True)
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen target-150 cohort policy with immutable purchase caps.",
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        required=True,
        help="Frozen full-pool snapshot manifest supplying cycle lineage.",
    )
    parser.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help="Verified canonical cycle purchase-policy artifact.",
    )
    parser.add_argument(
        "--purchase-ledger",
        type=Path,
        required=True,
        help="Canonical SQLite purchase journal named by --purchase-policy.",
    )
    parser.add_argument(
        "--combined-max-projected-budget-usd",
        required=True,
        help=(
            "Explicit combined target-150 projection cap. The frozen base cap is "
            "derived from authenticated target-100 artifacts; this cap may be "
            "larger but cannot exceed the cohort-policy cycle ceiling."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_extend_target_cohort)


def _add_acquisition_filter_core_documents_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--case-relevance",
        type=Path,
        required=True,
        help="Setup-runner case/document relevance JSONL.",
    )
    parser.add_argument(
        "--results-output",
        type=Path,
        help="Core-document filter JSONL; defaults under --output-root.",
    )
    parser.set_defaults(handler=_cmd_acquisition_filter_core_documents)


def _add_acquisition_discover_case_dev_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--cycle-store",
        type=Path,
        help="Cycle-scoped SQLite store; defaults under --output-root.",
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="Stable batch identifier used for safe resume.",
    )
    parser.add_argument(
        "--decision-filed-on-or-after",
        required=True,
        metavar="YYYY-MM-DD",
        help="Immutable first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--decision-filed-on-or-before",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive batch observation-window upper bound.",
    )
    parser.add_argument(
        "--query-term",
        dest="query_terms",
        action="append",
        help=(
            "Case.dev legal docket search term. Repeat to override the default "
            "MTD decision-oriented term set."
        ),
    )
    parser.add_argument(
        "--per-term-limit",
        type=int,
        default=500,
        help=(
            "Independent durable top-K limit for each query term. A term that "
            "hits this bound is a checkpoint, not a saturated planner input."
        ),
    )
    parser.add_argument(
        "--search-page-size",
        type=int,
        default=50,
        help="Case.dev page size; the final page is reduced to the remaining top-K.",
    )
    parser.add_argument("--case-dev-fixture", type=Path)
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Use CASE_DEV_API_KEY for non-purchasing legal search. No document "
            "lookup or PACER endpoint is called."
        ),
    )
    parser.add_argument(
        "--candidates-output",
        type=Path,
        help="Partial checkpoint JSONL for fetch-firecrawl-dockets.",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_discover_case_dev)


def _add_acquisition_discover_firecrawl_recap_arguments(
    parser: argparse.ArgumentParser,
    *,
    decision_first: bool = False,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--cycle-store",
        type=Path,
        help="Cycle-scoped SQLite store; defaults under --output-root.",
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--run-id",
        required=True,
        help="Stable Firecrawl run identity used for crash-safe resume.",
    )
    parser.add_argument(
        "--recover-terminal-errors-from-run",
        metavar="RUN_ID",
        help=(
            "Run one bounded fallback generation after RUN_ID ended with terminal "
            "target errors. The new --run-id must be unique, --proxy enhanced and "
            "--force-browser are required, verified parent successes are reused, "
            "and fallback runs cannot be chained."
        ),
    )
    parser.add_argument(
        "--reuse-verified-pages-from-run",
        dest="recovery_source_run_ids",
        action="append",
        default=[],
        metavar="RUN_ID",
        help=(
            "Additional bounded same-batch run whose verified successful pages "
            "are unioned into terminal recovery. Repeatable; conflicting bytes "
            "for one search URL fail closed."
        ),
    )
    parser.add_argument(
        "--eligibility-anchor",
        required=True,
        metavar="YYYY-MM-DD",
        help="Immutable fail-closed first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--search-window-start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive per-batch RECAP search-window lower bound.",
    )
    parser.add_argument(
        "--search-window-end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive per-batch RECAP search-window upper bound.",
    )
    parser.add_argument(
        "--query-term",
        dest="query_terms",
        action="append",
        help=(
            "Frozen decision-first type=r query. Repeat to replace the eight-term "
            "default with a frozen subset."
            if decision_first
            else "MTD or eligible Rule 12(c) RECAP entry-search term. Repeat to "
            "replace the frozen default set."
        ),
    )
    parser.add_argument(
        "--max-pages-per-term",
        type=int,
        default=100 if decision_first else 1_000,
        help=(
            "Fail-closed pagination ceiling per decision term; default and hard "
            "maximum 100."
            if decision_first
            else "Fail-closed pagination ceiling per term; default 1000."
        ),
    )
    parser.add_argument(
        "--credit-cap",
        type=int,
        default=45_000,
        help=(
            "Cycle-wide permanent Firecrawl authorization cap. Must not exceed "
            "45000, preserving at least 5000 credits below the requested limit."
        ),
    )
    parser.add_argument(
        "--max-attempts-per-page",
        type=int,
        default=3,
        help="Maximum separately reserved attempts per page; default 3.",
    )
    parser.add_argument(
        "--provider-breaker-threshold",
        type=int,
        default=5,
        help="Stop after this many consecutive Firecrawl provider 5xx responses.",
    )
    parser.add_argument(
        "--proxy",
        choices=("basic", "auto", "enhanced"),
        default="auto",
        help=(
            "Firecrawl proxy mode; auto and enhanced are permanently reserved "
            "at five credits per request."
        ),
    )
    parser.add_argument(
        "--force-browser",
        action="store_true",
        help=(
            "Force Firecrawl onto an actions-capable browser engine with a "
            "one-millisecond wait action; the five-credit reservation is unchanged."
        ),
    )
    parser.add_argument("--firecrawl-fixture", type=Path)
    parser.add_argument(
        "--live-firecrawl",
        action="store_true",
        help="Use FIRECRAWL_API_KEY; no CourtListener token or PACER path is used.",
    )
    parser.add_argument("--entries-output", type=Path)
    parser.add_argument("--dockets-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument(
        "--raw-search-html-dir",
        type=Path,
        help=(
            "Raw Firecrawl search-page artifact directory. Defaults to "
            "<output-root>/raw-recap-search-html/<run-id>; an explicit path is "
            "used exactly as supplied."
        ),
    )
    parser.set_defaults(
        handler=_cmd_acquisition_discover_firecrawl_recap,
        recap_search_plan="decision-first-r" if decision_first else "mtd-entry-r",
    )


def _add_acquisition_project_firecrawl_recap_checkpoint_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help="Existing cycle-scoped SQLite store containing the durable run.",
    )
    parser.add_argument(
        "--run-id",
        dest="run_ids",
        action="append",
        required=True,
        help=(
            "Firecrawl run whose successful search artifacts will be verified. "
            "Repeat to union bounded runs from the same frozen batch; conflicting "
            "bytes for one term/page fail closed."
        ),
    )
    parser.add_argument("--pages-output", type=Path)
    parser.add_argument("--entries-output", type=Path)
    parser.add_argument("--dockets-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_project_firecrawl_recap_checkpoint)


def _add_acquisition_discover_courtlistener_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--eligibility-anchor",
        required=True,
        metavar="YYYY-MM-DD",
        help="Immutable fail-closed first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--search-window-start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive rolling RECAP search-window lower bound.",
    )
    parser.add_argument(
        "--search-window-end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive rolling RECAP search-window upper bound.",
    )
    parser.add_argument(
        "--cycle-store",
        type=Path,
        help="Cycle store that freezes the anchor and per-batch window digest.",
    )
    parser.add_argument(
        "--batch-id",
        help="Batch identity; required when --cycle-store is supplied.",
    )
    parser.add_argument(
        "--query-term",
        dest="query_terms",
        action="append",
        help=(
            "MTD disposition phrase to search. Repeat to override the default "
            "decision-oriented query set."
        ),
    )
    parser.add_argument(
        "--target-clean-cases",
        type=int,
        default=150,
        help=(
            "Accepted-case stop/diagnostic bound. A materializable saturated run "
            "must set this above the possible window yield; hitting it is "
            "explicitly non-saturated."
        ),
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=3000,
        help=(
            "Hard candidate and durable per-term pagination bound. A materializable "
            "run must exhaust below this value; hitting it fails closed."
        ),
    )
    parser.add_argument(
        "--search-page-size",
        type=int,
        default=50,
        help="CourtListener RECAP search page size, from 1 through 100.",
    )
    parser.add_argument(
        "--request-ledger",
        type=Path,
        help=(
            "Crash-durable SQLite ledger for every physical CourtListener REST "
            "attempt. With --live, defaults under --output-root."
        ),
    )
    parser.add_argument(
        "--courtlistener-rate-profile",
        choices=tuple(_COURTLISTENER_RATE_PROFILES),
        default="base",
        help=(
            "Provider ceiling profile with headroom. Use temporary-doubled only "
            "while CourtListener has explicitly doubled this account's limits."
        ),
    )
    parser.add_argument(
        "--request-budget-max-wait-seconds",
        type=float,
        default=120.0,
        help=(
            "Maximum cumulative wait for one CourtListener request reservation "
            "before failing closed; default 120."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Query CourtListener and fetch public docket HTML over HTTPS. Requires "
            f"{COURTLISTENER_API_TOKEN_ENV}."
        ),
    )
    parser.add_argument(
        "--live-firecrawl-docket-html",
        action="store_true",
        help=(
            "Keep authenticated CourtListener REST as the search authority but "
            "fetch each strictly allowlisted public docket HTML page through "
            "Firecrawl. Requires --live and FIRECRAWL_API_KEY. Basic proxy mode "
            "is capped at one reported credit per attempt and three bounded "
            "attempts per candidate; live attempts and source-bound resume "
            "artifacts are journaled in the required cycle store."
        ),
    )
    parser.add_argument(
        "--firecrawl-credit-cap",
        type=int,
        default=45_000,
        help=(
            "Cycle-wide Firecrawl authorization cap for hybrid docket HTML, from "
            "1 through 45000 credits. The store freezes the first value used."
        ),
    )
    parser.add_argument(
        "--courtlistener-fixture",
        type=Path,
        help="Replay recorded CourtListener API JSONL responses without network use.",
    )
    parser.add_argument(
        "--docket-html-fixture-dir",
        type=Path,
        help="Read public docket HTML fixtures named <docket_id>.html.",
    )
    parser.add_argument("--screened-cases-output", type=Path)
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--raw-html-dir", type=Path)
    parser.add_argument(
        "--search-pages-output",
        type=Path,
        help="Canonical per-page CourtListener discovery transcript JSONL.",
    )
    parser.add_argument(
        "--raw-artifacts-output",
        type=Path,
        help="Hash manifest for every persisted raw docket HTML artifact.",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_discover_courtlistener)


def _add_acquisition_materialize_courtlistener_snapshot_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--discovery-run-card",
        type=Path,
        required=True,
        help="Completed discover-courtlistener run card with committed outputs.",
    )
    parser.add_argument(
        "--expected-discovery-run-card-sha256",
        required=True,
        help="Externally pinned lowercase SHA-256 of --discovery-run-card.",
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        required=True,
        help="Immutable snapshot parent directory.",
    )
    parser.add_argument("--snapshot-id", required=True)
    parser.set_defaults(handler=_cmd_acquisition_materialize_courtlistener_snapshot)


def _add_acquisition_union_screening_snapshots_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--expected-cycle-hash", required=True)
    parser.add_argument(
        "--source-snapshot",
        type=Path,
        action="append",
        required=True,
        help="Complete saturated same-cycle snapshot; repeat at least twice.",
    )
    parser.add_argument(
        "--expected-source-snapshot-manifest-sha256",
        action="append",
        required=True,
        help=(
            "Pinned lowercase SHA-256 for the corresponding --source-snapshot; "
            "repeat in the same order."
        ),
    )
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.set_defaults(handler=_cmd_acquisition_union_screening_snapshots)


def _add_acquisition_funnel_report_arguments(parser: argparse.ArgumentParser) -> None:
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument(
        "--discovery-summary",
        type=Path,
        help="Legacy discovery summary containing counts and per-term diagnostics.",
    )
    sources.add_argument(
        "--firecrawl-screening-summary",
        type=Path,
        help="Canonical Firecrawl screening summary containing terminal counts.",
    )
    parser.add_argument(
        "--recap-discovery-summary",
        type=Path,
        help=(
            "RECAP discovery diagnostics; required with --firecrawl-screening-summary."
        ),
    )
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--public-download-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_cmd_acquisition_funnel_report)


def _add_acquisition_generate_labeling_policy_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("cycle_id")
    parser.add_argument("--judge-registry", type=Path, required=True)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--threshold-source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_cmd_acquisition_generate_labeling_policy)


def _add_acquisition_verify_labeling_policy_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--judge-registry", type=Path, required=True)
    parser.add_argument("--cycle-id")
    parser.set_defaults(handler=_cmd_acquisition_verify_labeling_policy)


# ---------------------------------------------------------------------------
# batch-002 RECAP API acquisition driver arguments.
# ---------------------------------------------------------------------------

_BATCH_002_DEFAULT_BATCH_ID = "batch-002"
_BATCH_002_DEFAULT_ANCHOR = "2026-06-30"
_BATCH_002_DEFAULT_WINDOW_START = "2026-06-30"
_BATCH_002_DEFAULT_WINDOW_END = "2026-07-14"
_COURTLISTENER_RATE_PROFILES = {
    "base": CourtListenerRequestLimits(
        per_minute=24,
        per_hour=290,
        per_day=1_350,
    ),
    "temporary-doubled": CourtListenerRequestLimits(),
}


def _add_batch_002_source_arguments(
    parser: argparse.ArgumentParser, *, live_help: str
) -> None:
    """Add the mutually-exclusive live/fixture CourtListener source flags."""

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--live",
        action="store_true",
        help=live_help,
    )
    source.add_argument(
        "--courtlistener-fixture",
        type=Path,
        help="Replay recorded CourtListener API JSONL responses without network use.",
    )
    parser.add_argument(
        "--request-ledger",
        type=Path,
        help=(
            "Crash-durable SQLite ledger for every physical CourtListener HTTP "
            "attempt. Required with --live; omitted for fixtures."
        ),
    )
    parser.add_argument(
        "--courtlistener-rate-profile",
        choices=tuple(_COURTLISTENER_RATE_PROFILES),
        default="base",
        help=(
            "Provider ceiling profile with headroom. Use temporary-doubled only "
            "while CourtListener has explicitly doubled this account's limits."
        ),
    )
    parser.add_argument(
        "--request-budget-max-wait-seconds",
        type=float,
        default=120.0,
        help=(
            "Maximum cumulative wait for one HTTP-attempt reservation before "
            "failing closed; default 120."
        ),
    )


def _add_batch_002_discover_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help=(
            "Acquisition store sqlite path (for example "
            "artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3). "
            "Never a batch-001 store."
        ),
    )
    parser.add_argument("--batch-id", default=_BATCH_002_DEFAULT_BATCH_ID)
    parser.add_argument(
        "--eligibility-anchor",
        default=_BATCH_002_DEFAULT_ANCHOR,
        metavar="YYYY-MM-DD",
        help="Immutable first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--decision-window-start",
        default=_BATCH_002_DEFAULT_WINDOW_START,
        metavar="YYYY-MM-DD",
        help="Inclusive entry_date_filed lower bound for decision discovery.",
    )
    parser.add_argument(
        "--decision-window-end",
        default=_BATCH_002_DEFAULT_WINDOW_END,
        metavar="YYYY-MM-DD",
        help="Inclusive entry_date_filed upper bound for decision discovery.",
    )
    parser.add_argument("--top-k-per-term", type=int, default=5_000)
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="CourtListener search page size, from 1 through 100.",
    )
    parser.add_argument(
        "--min-interval-seconds",
        type=float,
        default=None,
        help=(
            "Minimum spacing between logical search-page requests. The live "
            "default is derived from the selected profile's hourly ceiling "
            "(12.5s base; 6.25s temporary-doubled); fixtures are unpaced. The "
            "durable attempt ledger independently enforces all windows."
        ),
    )
    _add_batch_002_source_arguments(
        parser,
        live_help=(
            "Disabled for discovery: CourtListener does not expose this REST-only "
            "type=rd plan through the supported web route. Use `legalforecast "
            "acquisition discover-courtlistener` or seed-direct-search."
        ),
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_batch_002_discover)


def _add_batch_002_observe_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help="Acquisition store sqlite path holding the attached batch.",
    )
    parser.add_argument("--batch-id", default=_BATCH_002_DEFAULT_BATCH_ID)
    parser.add_argument(
        "--eligibility-anchor",
        default=_BATCH_002_DEFAULT_ANCHOR,
        metavar="YYYY-MM-DD",
        help="Immutable first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--min-interval-seconds",
        type=float,
        default=None,
        help=(
            "Minimum spacing between logical requests. The live default is "
            "derived from the selected profile's hourly ceiling (12.5s base; "
            "6.25s temporary-doubled); fixtures are unpaced."
        ),
    )
    parser.add_argument(
        "--jitter-seconds",
        type=float,
        default=0.25,
        help="Uniform random jitter added to each pause; default 0.25.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=2.0,
        help="Backoff between 429/5xx retries; reuses the client retry loop.",
    )
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Observe at most N candidates this pass (smoke runs); default all.",
    )
    parser.add_argument(
        "--refresh-reason-code",
        action="append",
        choices=cohort_reason_policy_taxonomy()["refreshable_reason_codes"],
        default=[],
        help=(
            "Re-observe current terminal candidates carrying this refreshable "
            "reason code after a documented screening correction. Repeat for "
            "multiple codes; immutable exclusions cannot be refreshed."
        ),
    )
    parser.add_argument(
        "--revalidate-candidate-id",
        action="append",
        default=[],
        help=(
            "Re-observe this exact currently accepted batch candidate after a "
            "documented false-positive screening correction. Repeat for multiple "
            "candidate ids."
        ),
    )
    parser.add_argument(
        "--refresh-campaign-cutoff",
        help=(
            "Frozen timezone-aware ISO-8601 cutoff for a refresh/revalidation "
            "campaign. Required with --refresh-reason-code or "
            "--revalidate-candidate-id; reuse the exact value on every limited "
            "resume so already refreshed observations are not selected again."
        ),
    )
    _add_batch_002_source_arguments(
        parser,
        live_help=(
            "Reconstruct and screen through authenticated CourtListener REST. "
            "Requires COURTLISTENER_API_TOKEN and --request-ledger."
        ),
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_batch_002_observe)


def _add_batch_002_seed_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-store",
        type=Path,
        required=True,
        help=(
            "Batch-001 store sqlite path, opened read-only (for example "
            "artifacts/cycle-1/batch-001-zero-paid/cycle-acquisition.sqlite3)."
        ),
    )
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help="Target batch-002 acquisition store; the batch must already exist.",
    )
    parser.add_argument("--batch-id", default=_BATCH_002_DEFAULT_BATCH_ID)
    parser.add_argument(
        "--source-batch-id",
        default=None,
        help="Optional batch-001 first_batch_id filter; default all unresolved.",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_batch_002_seed)


def _add_batch_002_direct_seed_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-store",
        type=Path,
        required=True,
        help="Store containing the saturated direct CourtListener search batch.",
    )
    parser.add_argument(
        "--source-batch-id",
        required=True,
        help="Exact saturated source batch identifier.",
    )
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help=(
            "Target REST acquisition store. It may be the source store; the source "
            "is opened read-only and closed before transfer."
        ),
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="New REST screening batch identifier; must differ from the source batch.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Durable transfer page size, from 1 through 100; default 100.",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_batch_002_direct_seed)


def _add_batch_002_snapshot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help="Acquisition store sqlite path holding the completed REST batch.",
    )
    parser.add_argument("--batch-id", default=_BATCH_002_DEFAULT_BATCH_ID)
    parser.add_argument(
        "--snapshot-id",
        required=True,
        help="Immutable snapshot identifier; safe filename characters only.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Directory in which the immutable snapshot directory is created.",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_batch_002_snapshot)


def _add_generate_cohort_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help="JSON object containing John-approved cohort policy values.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_cmd_generate_cohort_policy)


def _add_verify_cohort_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    parser.set_defaults(handler=_cmd_verify_cohort_policy)


def _add_generate_purchase_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help=(
            "JSON object containing the cycle ID, cohort-policy hash, canonical "
            "absolute ledger path, hard caps, and verified fee schedule."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen cohort policy whose purchase caps this artifact must consume.",
    )
    parser.set_defaults(handler=_cmd_generate_purchase_policy)


def _add_init_purchase_ledger_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help="Frozen purchase policy containing the canonical ledger locator.",
    )
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen cohort policy whose purchase caps must match exactly.",
    )
    parser.add_argument(
        "--purchase-ledger",
        type=Path,
        required=True,
        help=(
            "Exact absolute canonical ledger path from the purchase policy. "
            "An unreceipted existing path is never initialized or repaired."
        ),
    )
    parser.add_argument(
        "--initialization-receipt-output",
        type=Path,
        help=(
            "Immutable hash-bound initialization receipt. Defaults to "
            "<output-root>/purchase-ledger-initialization.json."
        ),
    )
    parser.set_defaults(handler=_cmd_init_purchase_ledger)


def _add_build_clearance_replacement_frontier_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen legalforecast.cohort_policy.v1 artifact.",
    )
    parser.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help="Frozen Cycle-wide purchase policy with the canonical journal path.",
    )
    parser.add_argument(
        "--projection",
        type=Path,
        required=True,
        help=(
            "Frozen target-cohort projection artifact. Its exact file bytes are "
            "committed as projection_sha256; the command does not infer or alter rank."
        ),
    )
    parser.add_argument(
        "--initial-selection",
        type=Path,
        required=True,
        help=(
            "JSON/JSONL initial cohort. Supply selected_candidate_ids or one "
            "candidate_id object per selected case."
        ),
    )
    parser.add_argument(
        "--candidate-frontier",
        type=Path,
        required=True,
        help=(
            "Complete canonical ranked JSON/JSONL frontier. Prefer the verified "
            "full-candidate artifact emitted by prepare-target-cohort. Rows must "
            "include frozen case-mix metadata; this command preserves their order "
            "and refuses truncation."
        ),
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help=(
            "Additional frozen source artifact to hash-bind. Repeat for snapshot, "
            "selection, relevance, or other frontier authorities."
        ),
    )
    parser.add_argument(
        "--case-mix-max-per-bucket",
        type=int,
        help=(
            "Frozen maximum selected cases in each non-null court, NOS macro, "
            "related-family, and MDL-family bucket. Omit for an explicit null cap."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--broker-allowlist-plan-output",
        type=Path,
        required=True,
        help=(
            "Broad dry-run full-frontier plan to activate at the broker before "
            "the first purchase. It is never a narrow executable iteration."
        ),
    )
    parser.set_defaults(handler=_cmd_build_clearance_replacement_frontier)


def _add_plan_clearance_replacements_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--cohort-policy", type=Path, required=True)
    parser.add_argument("--purchase-policy", type=Path, required=True)
    parser.add_argument(
        "--frontier",
        type=Path,
        required=True,
        help="Verified full replacement frontier from the builder command.",
    )
    parser.add_argument(
        "--purchase-ledger",
        type=Path,
        required=True,
        help=(
            "Canonical Cycle purchase SQLite journal. It remains the single writer "
            "for purchase and hash-chained replacement state."
        ),
    )
    parser.add_argument(
        "--purchased-clearance",
        type=Path,
        required=True,
        help=(
            "Complete purchased-document clearance JSON/JSONL. Coverage must exactly "
            "match confirmed journal rows; free-document clearance is not accepted."
        ),
    )
    parser.add_argument(
        "--clearance-run-card",
        type=Path,
        required=True,
        help="Authenticated disclosure-clearance run card whose bytes are hash-bound.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Hash-bound replacement-loop summary JSON.",
    )
    parser.add_argument(
        "--replacement-budget-plan-output",
        type=Path,
        required=True,
        help=(
            "Narrow executable budget plan for only the replacement candidates "
            "selected by the durable iteration ledger."
        ),
    )
    parser.add_argument(
        "--broker-allowlist-plan-output",
        type=Path,
        required=True,
        help=(
            "Broad dry-run allowlist plan for every eligible frozen frontier "
            "document. It is not an executable purchase plan."
        ),
    )
    parser.add_argument(
        "--exclusions-output",
        type=Path,
        required=True,
        help="Derived JSONL exclusions for every frontier candidate skipped in replay.",
    )
    parser.set_defaults(handler=_cmd_plan_clearance_replacements)


def _add_generate_recap_fetch_broker_policy_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help=(
            "Verified immutable legalforecast.case_dev_purchase_policy.v1 "
            "artifact; its digest and every cap/opening field are copied exactly."
        ),
    )
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help=(
            "Frozen cohort policy whose hash and purchase caps the verified "
            "purchase policy must consume."
        ),
    )
    parser.add_argument(
        "--budget-plan",
        type=Path,
        required=True,
        help=(
            "Narrow executable non-dry-run plan by default, or an explicitly "
            "dry-run full-frontier scope with --broad-frontier-allowlist; only "
            "case_plans.purchase_document_ids may enter the broker allowlist."
        ),
    )
    parser.add_argument(
        "--broad-frontier-allowlist",
        action="store_true",
        help=(
            "Treat --budget-plan as an explicitly dry-run, full-frontier broker "
            "allowlist rather than a narrow executable iteration. Aggregate "
            "hypothetical cost may exceed the Cycle cap, but the signed broker "
            "still enforces the unchanged cap and per-case limits on every request."
        ),
    )
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help=(
            "Final selection JSON/JSONL containing candidate_id, documents, and "
            "explicit-public or exact CourtListener REST restriction evidence for "
            "every planned ID; sealed, private, and restricted documents are "
            "rejected. Case.dev is never purchase authority."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "Immutable courtlistener-recap-fetch-policy-v1 JSON output; an "
            "existing different-byte file is never overwritten."
        ),
    )
    parser.set_defaults(handler=_cmd_generate_recap_fetch_broker_policy)


def _add_reconcile_purchase_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--purchase-policy", type=Path, required=True)
    parser.add_argument("--cohort-policy", type=Path, required=True)
    parser.add_argument("--purchase-ledger", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help=(
            "JSON provider evidence: document ID, confirmed/failed/write_off "
            "disposition, billing source type/reference, and PACER fees when confirmed."
        ),
    )
    parser.set_defaults(handler=_cmd_reconcile_purchase)


def _add_export_cohort_observations_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_cmd_export_cohort_observations)


def _add_verify_cohort_observations_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.set_defaults(handler=_cmd_verify_cohort_observations)


def _add_acquisition_enrich_recap_case_dev_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--dockets",
        type=Path,
        required=True,
        help="Potential-docket JSONL from discover-firecrawl-recap.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Free Case.dev includeEntries page size; default 100.",
    )
    parser.add_argument(
        "--max-pages-per-docket",
        type=int,
        default=100,
        help="Fail-closed free lookup ceiling per docket; default 100.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Concurrent live Case.dev docket lookups; 1-2, default 1. "
            "CASE_DEV_RATE_LIMIT_PER_MINUTE is one aggregate process-wide "
            "allowance shared across all workers. Checkpoint writes remain "
            "serialized. Fixtures require 1."
        ),
    )
    parser.add_argument("--case-dev-fixture", type=Path)
    parser.add_argument(
        "--live-case-dev",
        action="store_true",
        help=(
            "Use CASE_DEV_API_KEY for free lookup/includeEntries requests only; "
            "this command never sends live:true or acknowledges PACER fees."
        ),
    )
    parser.add_argument("--ranked-output", type=Path)
    parser.add_argument("--failures-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_enrich_recap_case_dev)


def _add_acquisition_acquire_ranked_dockets_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument("--parent-batch-id", required=True)
    parser.add_argument("--selected-batch-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ranked", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, required=True)
    parser.add_argument("--max-pages-per-docket", type=int, default=1000)
    parser.add_argument(
        "--workers",
        type=int,
        choices=range(1, 11),
        default=10,
        metavar="1-10",
        help=(
            "Concurrent live Firecrawl docket requests; default 10. SQLite "
            "authorization and artifact commits remain serialized. Fixtures "
            "require 1 when executing."
        ),
    )
    parser.add_argument("--decision-filed-on-or-after", required=True)
    parser.add_argument("--credit-cap", type=int, default=45_000)
    parser.add_argument("--max-attempts-per-page", type=int, default=3)
    parser.add_argument("--provider-breaker-threshold", type=int, default=5)
    parser.add_argument(
        "--proxy",
        choices=("basic", "auto", "enhanced"),
        default="auto",
        help=(
            "Firecrawl proxy mode; auto and enhanced reserve five credits per request."
        ),
    )
    parser.add_argument(
        "--force-browser",
        action="store_true",
        help="Force Firecrawl onto its actions-capable browser engine.",
    )
    parser.add_argument("--firecrawl-fixture", type=Path)
    parser.add_argument("--live-firecrawl", action="store_true")
    parser.add_argument("--raw-html-dir", type=Path)
    parser.add_argument("--successes-output", type=Path)
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_acquire_ranked_dockets)


def _add_acquisition_plan_public_downloads_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Complete cycle snapshot directory; partial checkpoints are rejected.",
    )
    parser.add_argument(
        "--expected-cycle-hash",
        required=True,
        help="Frozen cycle-policy SHA-256 reported by discover-case-dev.",
    )
    parser.add_argument(
        "--screened-cases",
        type=Path,
        help="Defaults to screened-cases.jsonl inside the verified snapshot.",
    )
    parser.add_argument(
        "--raw-html-dir",
        type=Path,
        help=(
            "Optional explicit raw-HTML directory; when provided it must exactly "
            "match the directory committed by the verified snapshot."
        ),
    )
    parser.add_argument(
        "--use-embedded-entries",
        action="store_true",
        help=(
            "If saved raw docket HTML is missing, plan from embedded "
            "selected_entries records in the screened-cases JSONL."
        ),
    )
    parser.add_argument("--target-clean-cases", type=int, default=25)
    parser.add_argument(
        "--cost-per-missing-document-usd",
        type=Decimal,
        default=Decimal("3.05"),
        help=(
            "Projected PACER cost for each missing required document; used only "
            "to rank the full candidate pool and never authorizes a purchase."
        ),
    )
    parser.add_argument(
        "--max-case-mix-share",
        type=_case_mix_share_argument,
        default=None,
        help=(
            "Target-relative allowance used to derive an absolute cap for each "
            "non-null court, NOS macro, related-family, and MDL-family bucket. "
            "Omitted means no automatic cap. The exact per-bucket cap is "
            "floor(target clean cases multiplied by this decimal share); shares "
            "producing a zero cap are rejected. 0.4 matches the case-mix "
            "dominance review threshold."
        ),
    )
    parser.add_argument(
        "--allow-inferred-target-mtd",
        action="store_true",
        help=(
            "When target entry numbers are missing or stale, allow the planner to "
            "use free pre-decision MTD entries inferred from docket text."
        ),
    )
    parser.add_argument("--requests-output", type=Path)
    parser.add_argument("--selection-output", type=Path)
    parser.add_argument(
        "--paid-gaps-output",
        type=Path,
        help=(
            "Recoverable PACER-gap candidates. Run download-free before passing "
            "this JSONL to bridge-pacer-gaps."
        ),
    )
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_plan_public_downloads)


def _add_acquisition_fetch_firecrawl_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="Case.dev candidate JSONL containing case_id and optional candidate_id.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        required=True,
        help=(
            "Hard cap on unique candidates resolved by this legacy preliminary "
            "docket fetch. Use discover-firecrawl-recap for cycle-budgeted, "
            "entry-date-anchored discovery."
        ),
    )
    parser.add_argument("--case-dev-fixture", type=Path)
    parser.add_argument(
        "--live-case-dev",
        action="store_true",
        help=(
            "Resolve candidate metadata using CASE_DEV_API_KEY. This command "
            "does not call document purchase endpoints."
        ),
    )
    parser.add_argument(
        "--firecrawl-fixture",
        type=Path,
        help="Replay ordered Firecrawl HTTP response records from JSONL.",
    )
    parser.add_argument(
        "--live-firecrawl",
        action="store_true",
        help=(
            "Fetch public CourtListener docket HTML using FIRECRAWL_API_KEY with "
            "the legacy one-page basic/no-cache request contract. This path does "
            "not prove complete pagination."
        ),
    )
    parser.add_argument("--raw-html-dir", type=Path)
    parser.add_argument("--successes-output", type=Path)
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_fetch_firecrawl)


def _add_acquisition_screen_firecrawl_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--successes",
        type=Path,
        required=True,
        help="Success JSONL from acquisition fetch-firecrawl-dockets.",
    )
    parser.add_argument(
        "--fetch-exclusions",
        type=Path,
        required=True,
        help="Exclusion JSONL from the matching fetch-firecrawl-dockets run.",
    )
    parser.add_argument(
        "--raw-html-dir",
        type=Path,
        required=True,
        help="Directory containing persisted <CourtListener docket ID>.html files.",
    )
    parser.add_argument(
        "--decision-filed-on-or-after",
        required=True,
        metavar="YYYY-MM-DD",
        help="Fail-closed anchor for the first written MTD disposition.",
    )
    parser.add_argument("--screened-cases-output", type=Path)
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        help="Immutable snapshot parent; defaults under --output-root.",
    )
    parser.add_argument(
        "--snapshot-id",
        required=True,
        help="Immutable complete snapshot directory name.",
    )
    parser.set_defaults(handler=_cmd_acquisition_screen_firecrawl)


def _add_acquisition_replay_screening_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--cycle-store", type=Path, required=True)
    parser.add_argument(
        "--batch-id",
        required=True,
        help="Synthetic target-cycle batch receiving every replayed candidate.",
    )
    parser.add_argument(
        "--source-assembly-run-card",
        type=Path,
        required=True,
        help=(
            "Prior assemble-cycle-acquisition run card recursively expanded into "
            "verified screening snapshots; downstream-only roots are ignored."
        ),
    )
    parser.add_argument(
        "--expected-source-assembly-sha256",
        required=True,
        help="Exact lowercase SHA-256 of --source-assembly-run-card.",
    )
    parser.add_argument(
        "--expected-source-closure-sha256",
        required=True,
        help=(
            "Exact lowercase SHA-256 of the recursive source closure: every "
            "assembly run card and every assembly/supplemental snapshot manifest."
        ),
    )
    parser.add_argument(
        "--expected-source-cycle-hash",
        required=True,
        help="Required cycle hash for every snapshot expanded from the assembly.",
    )
    parser.add_argument(
        "--expected-legacy-screen-inputs-sha256",
        help=(
            "Aggregate SHA-256 frozen for historical assembly snapshots that "
            "predate per-snapshot firecrawl_screen_inputs commitments. Required "
            "only when such snapshots are present; a mismatch fails closed."
        ),
    )
    parser.add_argument(
        "--source-snapshot",
        type=Path,
        action="append",
        default=[],
        help=(
            "Additional complete historical snapshot, such as a JOP or adversary "
            "batch. Repeatable; each occurrence requires a corresponding "
            "--expected-source-snapshot-cycle-hash in the same order."
        ),
    )
    parser.add_argument(
        "--expected-source-snapshot-cycle-hash",
        action="append",
        default=[],
        help=(
            "Exact cycle hash for the corresponding --source-snapshot. "
            "Repeat once per supplemental snapshot, in the same order."
        ),
    )
    parser.add_argument(
        "--source-snapshot-screen-run-card",
        type=Path,
        action="append",
        default=[],
        help=(
            "Exact screen-firecrawl-dockets run card for the corresponding "
            "supplemental snapshot. Repeat once per --source-snapshot."
        ),
    )
    parser.add_argument(
        "--expected-source-snapshot-screen-run-card-sha256",
        action="append",
        default=[],
        help=(
            "Exact lowercase SHA-256 for the corresponding supplemental screen "
            "run card. Repeat once per --source-snapshot."
        ),
    )
    parser.add_argument(
        "--source-snapshot-bundle-root",
        type=Path,
        action="append",
        default=[],
        help=(
            "Self-contained durable root holding the corresponding snapshot, "
            "screen inputs, and raw HTML at their original relative paths. "
            "Repeat once per --source-snapshot."
        ),
    )
    parser.add_argument(
        "--expected-target-cycle-hash",
        required=True,
        help="Required target-store cycle hash.",
    )
    parser.add_argument(
        "--decision-filed-on-or-after",
        required=True,
        metavar="YYYY-MM-DD",
        help="Fail-closed first-written-disposition eligibility anchor.",
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        help="Immutable snapshot parent; defaults under --output-root.",
    )
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--screened-cases-output", type=Path)
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_replay_screening_snapshots)


def _add_acquisition_quarantine_snapshot_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--cycle-store",
        type=Path,
        required=True,
        help="Cycle acquisition SQLite store, opened immutable and read-only.",
    )
    parser.add_argument(
        "--orphan-snapshot",
        type=Path,
        required=True,
        help=(
            "Unregistered snapshot directory inside the cycle-store root to "
            "verify and quarantine."
        ),
    )
    parser.add_argument(
        "--quarantine-root",
        type=Path,
        required=True,
        help=(
            "Existing same-filesystem directory outside the cycle-store root; "
            "the orphan is atomically renamed beneath it."
        ),
    )
    parser.add_argument(
        "--receipt-output",
        type=Path,
        required=True,
        help=(
            "Durable JSON audit receipt outside the cycle-store root. Dry runs "
            "write a verification receipt without moving the orphan."
        ),
    )
    parser.add_argument("--expected-snapshot-id", required=True)
    parser.add_argument(
        "--expected-orphan-manifest-sha256",
        required=True,
        help="Expected SHA-256 of the orphan's manifest.json bytes.",
    )
    parser.add_argument(
        "--expected-canonical-manifest-sha256",
        required=True,
        help="Expected SHA-256 of the registered snapshot's manifest.json bytes.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Perform the atomic quarantine move after all proofs pass. Omit for "
            "a receipt-producing dry run."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_quarantine_snapshot)


def _add_acquisition_bridge_pacer_gaps_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--screened-cases",
        type=Path,
        required=True,
        help="Screened CourtListener cases from acquisition discover-courtlistener.",
    )
    parser.add_argument(
        "--raw-html-dir",
        type=Path,
        help="Saved raw CourtListener docket HTML directory.",
    )
    parser.add_argument(
        "--use-embedded-entries",
        action="store_true",
        help=(
            "Use the discovery record's embedded selected_entries only when saved "
            "raw CourtListener HTML is unavailable."
        ),
    )
    parser.add_argument(
        "--case-dev-fixture",
        type=Path,
        help="Replay recorded case.dev search and docket-lookup responses.",
    )
    parser.add_argument(
        "--live-case-dev",
        action="store_true",
        help=(
            "Resolve identities using live case.dev search/lookup. Requires "
            "CASE_DEV_API_KEY and never invokes a PACER purchase endpoint."
        ),
    )
    parser.add_argument(
        "--courtlistener-fixture",
        type=Path,
        help=(
            "Replay noncharging CourtListener REST docket, entry, and RECAP "
            "document metadata for public-first paid gaps."
        ),
    )
    parser.add_argument(
        "--live-courtlistener",
        action="store_true",
        help=(
            "Resolve public-first paid gaps with authenticated noncharging "
            "CourtListener REST GETs. Never invokes RECAP Fetch or PACER."
        ),
    )
    parser.add_argument(
        "--request-ledger",
        type=Path,
        help=(
            "Crash-durable SQLite ledger for every physical CourtListener HTTP "
            "attempt. Required with --live-courtlistener; omitted for fixtures."
        ),
    )
    parser.add_argument(
        "--courtlistener-rate-profile",
        choices=tuple(_COURTLISTENER_RATE_PROFILES),
        default="base",
        help=(
            "Provider ceiling profile with headroom. Use temporary-doubled only "
            "while CourtListener has explicitly doubled this account's limits."
        ),
    )
    parser.add_argument(
        "--request-budget-max-wait-seconds",
        type=float,
        default=120.0,
        help=(
            "Maximum cumulative wait for one HTTP-attempt reservation before "
            "failing closed; default 120."
        ),
    )
    parser.add_argument("--target-clean-cases", type=int, default=150)
    parser.add_argument(
        "--public-selection",
        type=Path,
        help="Fully-free selection JSONL from plan-public-downloads.",
    )
    parser.add_argument(
        "--paid-gaps",
        type=Path,
        help="Paid-gap JSONL from plan-public-downloads; only these cases bridge.",
    )
    parser.add_argument(
        "--free-download-manifest",
        type=Path,
        help=(
            "download-free manifest proving planned public documents were "
            "acquired before paid-gap routing."
        ),
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help=(
            "Atomic per-candidate public-gap checkpoints. Defaults under "
            "--output-root/checkpoints; resume skips terminal candidates."
        ),
    )
    parser.add_argument(
        "--checkpoint-config-output",
        type=Path,
        help=(
            "Input/source commitment for public-gap checkpoint resume. Defaults "
            "under --output-root/checkpoints."
        ),
    )
    parser.add_argument(
        "--requests-output",
        type=Path,
        help=(
            "Free-only download requests. Run download-free on this artifact "
            "before planning or executing any paid recovery."
        ),
    )
    parser.add_argument("--selection-output", type=Path)
    parser.add_argument(
        "--case-relevance-output",
        type=Path,
        help="Authoritative-ID input for filter-core-documents.",
    )
    parser.add_argument("--exclusions-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_bridge_pacer_gaps)


def _add_acquisition_download_free_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--document-output-root", type=Path)
    parser.add_argument(
        "--fixture-documents",
        type=Path,
        help="JSON mapping of source URL to fixture document text or bytes text.",
    )
    parser.add_argument(
        "--live-public-download",
        action="store_true",
        help=(
            "Fetch HTTPS CourtListener/RECAP free public documents. This never "
            "uses PACER or paid case.dev purchase endpoints."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_download_free)


def _add_acquisition_purchase_missing_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--budget-plan", type=Path, required=True)
    parser.add_argument("--purchase-output", type=Path)
    parser.add_argument(
        "--purchase-policy",
        type=Path,
        required=True,
        help="Immutable hash-bound cycle document-purchase policy artifact.",
    )
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen cohort policy that owns the cycle purchase cap.",
    )
    parser.add_argument(
        "--purchase-ledger",
        type=Path,
        required=True,
        help=(
            "Cycle-global SQLite journal; its normalized absolute path must equal "
            "the canonical locator frozen in --purchase-policy."
        ),
    )
    parser.add_argument("--case-dev-fixture", type=Path)
    parser.add_argument(
        "--live-purchase",
        action="store_true",
        help=(
            "Disabled legacy path. Live paid acquisition is supported only by "
            "purchase-missing-recap-fetch."
        ),
    )
    parser.add_argument(
        "--acknowledge-pacer-fees",
        action="store_true",
        help="Acknowledge that PACER fees may be charged.",
    )
    parser.add_argument(
        "--capability",
        choices=[capability.value for capability in CaseDevPacerCapability],
        default=CaseDevPacerCapability.UNKNOWN.value,
    )
    parser.set_defaults(handler=_cmd_acquisition_purchase_missing)


def _add_acquisition_purchase_missing_recap_fetch_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--budget-plan", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--purchase-output", type=Path)
    parser.add_argument("--purchase-policy", type=Path, required=True)
    parser.add_argument("--cohort-policy", type=Path, required=True)
    parser.add_argument("--purchase-ledger", type=Path, required=True)
    parser.add_argument(
        "--courtlistener-fixture",
        type=Path,
        help="Offline JSONL for noncharging document verification and queue polling.",
    )
    parser.add_argument(
        "--purchase-broker-fixture",
        type=Path,
        help=(
            "Offline JSON array of budget-broker receipts; never contains "
            "PACER credentials."
        ),
    )
    parser.add_argument(
        "--request-ledger",
        type=Path,
        help=(
            "Crash-durable SQLite ledger for every physical CourtListener "
            "verification or polling attempt. Required with --live-purchase."
        ),
    )
    parser.add_argument(
        "--courtlistener-rate-profile",
        choices=tuple(_COURTLISTENER_RATE_PROFILES),
        default="base",
        help=(
            "Provider ceiling profile with headroom. Use temporary-doubled only "
            "while CourtListener has explicitly doubled this account's limits."
        ),
    )
    parser.add_argument(
        "--request-budget-max-wait-seconds",
        type=float,
        default=120.0,
        help=(
            "Maximum cumulative wait for one CourtListener request reservation "
            "before failing closed; default 120."
        ),
    )
    parser.add_argument(
        "--live-purchase",
        action="store_true",
        help=(
            "Request the production signed budget broker using only the "
            "stage-scoped RECAP_FETCH_BROKER_* identity configuration."
        ),
    )
    parser.add_argument(
        "--acknowledge-pacer-fees",
        action="store_true",
        help="Acknowledge that the brokered request may incur PACER fees.",
    )
    parser.set_defaults(handler=_cmd_acquisition_purchase_missing_recap_fetch)


def _add_acquisition_plan_docket_live_fetches_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--screening-candidates",
        type=Path,
        action="append",
        required=True,
        help=(
            "Repeatable immutable screening candidates.jsonl input; only "
            "strict no_target_motion exclusions are considered."
        ),
    )
    parser.add_argument(
        "--fetch-successes",
        type=Path,
        action="append",
        required=True,
        help="Repeatable matching Firecrawl docket-success JSONL input.",
    )
    parser.add_argument(
        "--case-dev-ranking",
        type=Path,
        action="append",
        default=[],
        help="Repeatable free Case.dev coverage ranking JSONL used only for ordering.",
    )
    parser.add_argument(
        "--advisory-candidates",
        type=Path,
        action="append",
        default=[],
        help=(
            "Repeatable advisory recovery JSONL. When supplied, only "
            "recovery_class=high_confidence rows are eligible, and every row "
            "must rejoin to the persisted strict exclusion and cited raw entry."
        ),
    )
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        required=True,
        help="Frozen cohort-policy.json supplying anchor and immutable purchase caps.",
    )
    parser.add_argument(
        "--docket-fetch-reservation-usd",
        default="3.05",
        help=(
            "Verified worst-case docket-sheet reservation including service fee; "
            "defaults to the documented Case.dev maximum of 3.05."
        ),
    )
    parser.add_argument(
        "--cycle-committed-spend-usd",
        required=True,
        help=(
            "Verified spend already committed across all docket-live-fetch "
            "journals for this cycle; used to enforce the frozen cycle cap."
        ),
    )
    parser.add_argument(
        "--daily-budget-usd",
        default="25.00",
        help="Immutable Case.dev organization daily cap; cannot exceed 25.00.",
    )
    parser.add_argument(
        "--daily-committed-spend-usd",
        required=True,
        help=(
            "Verified Case.dev spend already committed for --spend-date-utc; "
            "used to derive remaining daily headroom."
        ),
    )
    parser.add_argument(
        "--spend-date-utc",
        required=True,
        help="UTC date (YYYY-MM-DD) for the executable daily tranche.",
    )
    parser.add_argument("--plan-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_plan_docket_live_fetches)


def _add_acquisition_execute_docket_live_fetches_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--docket-live-fetch-plan", type=Path, required=True)
    parser.add_argument(
        "--journal",
        type=Path,
        help="Canonical cycle-wide SQLite journal; defaults under --output-root.",
    )
    parser.add_argument("--result-output", type=Path)
    parser.add_argument(
        "--case-dev-fixture",
        type=Path,
        help="Offline Case.dev response fixture; mutually exclusive with live access.",
    )
    parser.add_argument(
        "--live-case-dev",
        action="store_true",
        help=(
            "Disabled legacy fee-bearing path. Use CourtListener REST discovery "
            "and purchase-missing-recap-fetch."
        ),
    )
    parser.add_argument(
        "--acknowledge-pacer-fees",
        action="store_true",
        help="Acknowledge that each submitted docket lookup may incur PACER fees.",
    )
    parser.set_defaults(handler=_cmd_acquisition_execute_docket_live_fetches)


def _add_acquisition_recover_purchased_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--purchase-result",
        type=Path,
        required=True,
        help="Guarded JSON result from acquisition purchase-missing.",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="Packet-selection JSONL containing purchased document metadata.",
    )
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--recovery-output", type=Path)
    parser.add_argument("--document-output-root", type=Path)
    parser.add_argument(
        "--fixture-documents",
        type=Path,
        help="JSON mapping of purchase download URL to offline fixture content.",
    )
    parser.add_argument(
        "--live-case-dev-download",
        action="store_true",
        help=(
            "Download only URLs returned by successful case.dev purchases. "
            "Requires CASE_DEV_API_KEY and never calls a purchase endpoint."
        ),
    )
    parser.add_argument(
        "--live-courtlistener-download",
        action="store_true",
        help=(
            "Download only public CourtListener/RECAP URLs returned by a "
            "successful brokered purchase; never calls a purchase endpoint."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_recover_purchased)


def _add_acquisition_merge_download_manifests_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--download-manifest",
        type=Path,
        action="append",
        required=True,
        help=(
            "Document-download JSONL to merge. Repeat for the free manifest and "
            "the recover-purchased manifest. Conflicting document keys fail closed."
        ),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        help="Merged parser-consumable JSONL; defaults under --output-root.",
    )
    parser.set_defaults(handler=_cmd_acquisition_merge_download_manifests)


def _add_acquisition_assemble_cycle_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--expected-cycle-hash",
        required=True,
        help=(
            "Frozen cycle-policy SHA-256. Every screening snapshot and downstream "
            "component must be cryptographically bound to this cycle."
        ),
    )
    parser.add_argument(
        "--batch-root",
        type=Path,
        action="append",
        required=True,
        help=(
            "Immutable acquisition artifact root. Repeat in chronological order; "
            "later evidenced records supersede refreshable earlier records. For "
            "split batches, pass a non-empty screening snapshot followed by its "
            "ordered plan/download/bridge/filter component roots. Every downstream-"
            "only root remains tied to the most recent snapshot until the next "
            "snapshot."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_assemble_cycle)


def _add_acquisition_bind_component_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Complete, saturated screening snapshot that owns this component.",
    )
    parser.add_argument(
        "--expected-cycle-hash",
        required=True,
        help="Frozen cycle-policy SHA-256 committed by the snapshot.",
    )
    parser.add_argument(
        "--component-stage",
        choices=tuple(COMPONENT_STAGE_ORDER),
        required=True,
        help="Canonical semantic stage represented by --output-root.",
    )
    parser.add_argument(
        "--component-ordinal",
        type=int,
        required=True,
        help="One-based position of this component after its screening snapshot.",
    )
    parser.add_argument(
        "--predecessor-provenance",
        type=Path,
        help=(
            "Prior component provenance JSON. Forbidden for ordinal 1 and required "
            "for later components. Each stage must use a separate immutable root."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_bind_component)


def _add_acquisition_disclosure_clearance_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--download-manifest", type=Path, required=True)
    parser.add_argument("--document-root", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--review-receipt", type=Path, required=True)
    parser.add_argument(
        "--restriction-evidence",
        type=Path,
        required=True,
        help="Docket/case relevance JSONL with derived seal and restriction evidence.",
    )
    parser.add_argument("--clearance-output", type=Path)
    parser.add_argument("--quarantine-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_disclosure_clearance)


def _add_acquisition_plan_parse_documents_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--download-manifest", type=Path, required=True)
    parser.add_argument("--disclosure-clearance", type=Path, required=True)
    parser.add_argument("--document-root", type=Path)
    parser.add_argument("--requests-output", type=Path)
    parser.add_argument(
        "--markdown-output-root",
        type=Path,
        default=Path("markdown"),
        help=(
            "Markdown output root, relative to --output-root unless absolute. "
            "Defaults to markdown/."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_plan_parse_documents)


def _add_acquisition_parse_documents_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--disclosure-clearance", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--parser-root", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--fixture-markdown-dir",
        type=Path,
        help="Directory with <source_document_id>.md files for fixture runs.",
    )
    parser.set_defaults(handler=_cmd_acquisition_parse_documents)


def _add_acquisition_llm_unitize_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="JSONL from acquisition plan-public-downloads.",
    )
    parser.add_argument(
        "--parser-manifest",
        type=Path,
        required=True,
        help="JSONL from acquisition parse-documents.",
    )
    parser.add_argument(
        "--markdown-root",
        type=Path,
        help="Root for parser Markdown artifacts; defaults to markdown.",
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help="Frozen model registry JSON used as the model source of truth.",
    )
    parser.add_argument(
        "--model-key",
        required=True,
        help="Registry key in provider:model_id form for the Stage A unitizer.",
    )
    _add_provider_cycle_caps_argument(parser)
    parser.add_argument(
        "--prediction-units-output",
        type=Path,
        help="Output JSONL with candidate_id and prediction_units.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        help="Output JSONL with LLM unitization audit/accounting rows.",
    )
    parser.add_argument(
        "--unitization-review-queue-output",
        type=Path,
        help="Output immutable JSONL queue of blinded Stage A reviews for John.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to later candidates after a model/validation failure.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-provider-request timeout for the registry-backed LLM call.",
    )
    parser.set_defaults(handler=_cmd_acquisition_llm_unitize)


def _add_acquisition_llm_label_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="JSONL from acquisition plan-public-downloads.",
    )
    parser.add_argument(
        "--parser-manifest",
        type=Path,
        required=True,
        help="JSONL from acquisition parse-documents.",
    )
    parser.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help="Finalized prediction-units JSONL from apply-unitization-review.",
    )
    parser.add_argument(
        "--markdown-root",
        type=Path,
        help="Root for parser Markdown artifacts; defaults to markdown.",
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help="Frozen model registry JSON used as the model source of truth.",
    )
    parser.add_argument(
        "--model-key",
        action="append",
        required=True,
        help=(
            "Registry key in provider:model_id form for one LLM label judge. "
            "Repeat for an ensemble; bare all-registry labeling is refused."
        ),
    )
    parser.add_argument(
        "--evaluated-model-registry",
        type=Path,
        required=True,
        help=(
            "Frozen candidate-model registry. Every judge must be exact-model "
            "disjoint from these evaluated models."
        ),
    )
    _add_provider_cycle_caps_argument(parser)
    parser.add_argument(
        "--labels-output",
        type=Path,
        help="Output JSONL with locked Stage B outcome labels.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        help="Output JSONL with LLM label judge audit/accounting rows.",
    )
    parser.add_argument(
        "--lawyer-review-queue-output",
        type=Path,
        help="Output JSONL with units pending lawyer adjudication.",
    )
    parser.add_argument(
        "--consensus-policy",
        choices=[policy.value for policy in LlmConsensusPolicy],
        default=LlmConsensusPolicy.UNANIMOUS.value,
        help=(
            "How to choose labels from multiple LLM judges. Unanimous is the "
            "default for LLM-only pilot labels."
        ),
    )
    parser.add_argument(
        "--high-confidence-threshold",
        type=float,
        default=0.85,
        help="Confidence threshold used in the ensemble audit record.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to later candidates after a model/validation failure.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-provider-request timeout for each registry-backed LLM judge call.",
    )
    parser.set_defaults(handler=_cmd_acquisition_llm_label)


def _add_provider_cycle_caps_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider-cycle-caps",
        type=Path,
        help=(
            "Frozen legalforecast.provider_cycle_caps.v1 JSON artifact. Required "
            "with --execute; each provider reservation cap must not exceed its "
            "recorded external spend limit."
        ),
    )


def _add_acquisition_llm_review_stage_a_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--selection", type=Path, required=True, help="JSONL acquisition selection."
    )
    parser.add_argument(
        "--parser-manifest", type=Path, required=True, help="JSONL parser manifest."
    )
    parser.add_argument(
        "--markdown-root", type=Path, help="Root for predecision Markdown artifacts."
    )
    parser.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help="Immutable raw units from llm-unitize.",
    )
    parser.add_argument(
        "--unitization-review-queue",
        type=Path,
        required=True,
        help="Existing immutable Stage A review queue.",
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help="Frozen reviewer model registry.",
    )
    parser.add_argument(
        "--model-key",
        required=True,
        help="Registry key for the structural reviewer (for Cycle 1, Gemini Flash).",
    )
    _add_provider_cycle_caps_argument(parser)
    parser.add_argument(
        "--structural-flags-output",
        type=Path,
        help="Hash-linked structured flags JSONL.",
    )
    parser.add_argument(
        "--review-queue-output",
        type=Path,
        help="Union of existing queue and structural flags for John.",
    )
    parser.add_argument(
        "--audit-output", type=Path, help="Reviewer call accounting JSONL."
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-provider request timeout.",
    )
    parser.set_defaults(handler=_cmd_acquisition_llm_review_stage_a)


def _add_acquisition_apply_unitization_review_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help="Raw prediction-units JSONL emitted by acquisition llm-unitize.",
    )
    parser.add_argument(
        "--unitization-review-queue",
        type=Path,
        required=True,
        help="Immutable Stage A review queue emitted by acquisition llm-unitize.",
    )
    parser.add_argument(
        "--adjudications",
        type=Path,
        required=True,
        help="Checked-in Stage A adjudications; never edit the review queue.",
    )
    parser.add_argument(
        "--finalized-prediction-units-output",
        type=Path,
        help="Hash-linked Stage A units required by labeling and readiness.",
    )
    parser.set_defaults(handler=_cmd_acquisition_apply_unitization_review)


def _add_acquisition_apply_lawyer_review_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="Existing labels.jsonl containing auto-accepted labels.",
    )
    parser.add_argument(
        "--adjudications",
        type=Path,
        required=True,
        help="Checked-in lawyer adjudication JSONL.",
    )
    parser.add_argument(
        "--decision-texts",
        type=Path,
        required=True,
        help=(
            "JSONL of first-written-disposition decision texts (one record per "
            "document_id, with document_id/entered_date/text). Adjudicated "
            "citation excerpts are validated verbatim against these."
        ),
    )
    parser.add_argument(
        "--llm-label-audit",
        type=Path,
        required=True,
        help="Cycle-planned audit JSONL emitted by acquisition plan-label-audit.",
    )
    parser.add_argument(
        "--cycle-label-audit-plan",
        type=Path,
        help="Frozen cycle-level audit plan; required for production cycle audits.",
    )
    parser.add_argument(
        "--labeling-policy",
        type=Path,
        help="Pinned pre-labeling policy; required with --cycle-label-audit-plan.",
    )
    parser.add_argument(
        "--labels-output",
        type=Path,
        help="Output JSONL with auto labels plus adjudicated labels.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        help="Output JSONL with lawyer-review resume audit rows.",
    )
    parser.add_argument(
        "--audit-sample-size",
        type=int,
        default=DEFAULT_LABEL_AUDIT_SAMPLE_SIZE,
        help="Deterministic unanimous-label audit sample size to enforce.",
    )
    parser.add_argument(
        "--human-blind-disagreement-rate",
        type=float,
        default=0.0,
        help="Human-human blind disagreement rate ceiling for label-audit acceptance.",
    )
    parser.set_defaults(handler=_cmd_acquisition_apply_lawyer_review)


def _add_acquisition_plan_label_audit_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--llm-label-audit", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--prediction-units", type=Path, required=True)
    parser.add_argument("--decision-texts", type=Path, required=True)
    parser.add_argument("--labeling-policy", type=Path, required=True)
    parser.add_argument(
        "--lawyer-review-queue",
        type=Path,
        required=True,
        help="Existing disagreement/ambiguity queue emitted by llm-label.",
    )
    parser.add_argument("--cycle-label-audit-plan-output", type=Path)
    parser.add_argument("--cycle-label-audit-summary-output", type=Path)
    parser.add_argument("--adjudication-routing-summary-output", type=Path)
    parser.add_argument("--planned-llm-label-audit-output", type=Path)
    parser.add_argument("--lawyer-review-queue-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_plan_label_audit)


def _add_acquisition_plan_packet_inputs_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="JSONL from acquisition plan-public-downloads.",
    )
    parser.add_argument(
        "--download-manifest",
        type=Path,
        required=True,
        help="JSONL from acquisition download-free.",
    )
    parser.add_argument(
        "--parser-manifest",
        type=Path,
        required=True,
        help="JSONL from acquisition parse-documents.",
    )
    parser.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help=(
            "JSONL with candidate_id and locked prediction_units; placeholder "
            "units are not appropriate for real pilots."
        ),
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help=(
            "Frozen model registry; plan-packet-inputs uses it to enforce the "
            "first-deployment decision window for official runs."
        ),
    )
    parser.add_argument(
        "--raw-html-dir",
        type=Path,
        required=True,
        help=(
            "Containment root for saved CourtListener docket HTML. Without "
            "--raw-artifacts-manifest, files must use <candidate_id>.html."
        ),
    )
    parser.add_argument(
        "--raw-artifacts-manifest",
        type=Path,
        help=(
            "Canonical raw-artifacts.jsonl binding namespaced candidate IDs to "
            "verified docket HTML paths. When omitted, the legacy "
            "<candidate_id>.html fixture layout is used."
        ),
    )
    parser.add_argument(
        "--document-root",
        type=Path,
        help="Root for downloaded source documents; defaults to documents/free.",
    )
    parser.add_argument(
        "--markdown-root",
        type=Path,
        help="Root for parser Markdown artifacts; defaults to markdown.",
    )
    parser.add_argument(
        "--packet-build-input-output",
        type=Path,
        help="Output JSONL for acquisition build-packets.",
    )
    parser.add_argument(
        "--document-manifest-output",
        type=Path,
        help="Output document-manifest.jsonl for private-store export.",
    )
    parser.add_argument(
        "--candidate-manifest-output",
        type=Path,
        help="Output candidate-manifest.jsonl for private-store export.",
    )
    parser.add_argument(
        "--extracted-texts-output",
        type=Path,
        help="Output extracted_texts.jsonl for private-store export.",
    )
    parser.add_argument(
        "--exclusion-ledger-output",
        type=Path,
        help="Output exclusion-ledger.jsonl for packet-time leakage/date gates.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional UTC timestamp for deterministic packet input records.",
    )
    parser.add_argument(
        "--search-query",
        default="refined MTD decision terms",
        help="Search-query provenance string for controlled docket markdown.",
    )
    parser.add_argument(
        "--search-window",
        default="not recorded",
        help="Search-window provenance string for controlled docket markdown.",
    )
    parser.set_defaults(handler=_cmd_acquisition_plan_packet_inputs)


def _add_acquisition_build_packets_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--packets-output", type=Path)
    parser.add_argument("--case-packets-output", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument(
        "--ablation",
        choices=[ablation.value for ablation in PacketAblation],
        default=PacketAblation.FULL_PACKET.value,
    )
    parser.set_defaults(handler=_cmd_acquisition_build_packets)


def _add_acquisition_finalize_corpus_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--parser-manifest", type=Path, required=True)
    parser.add_argument("--disclosure-clearance", type=Path, required=True)
    parser.add_argument(
        "--markdown-root",
        type=Path,
        required=True,
        help="Root containing parse-documents Markdown used to verify label excerpts.",
    )
    parser.add_argument("--raw-prediction-units", type=Path, required=True)
    parser.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help="Finalized prediction units emitted by apply-unitization-review.",
    )
    parser.add_argument("--llm-unitization-audit", type=Path, required=True)
    parser.add_argument(
        "--original-unitization-review-queue",
        type=Path,
        required=True,
        help="Immutable queue emitted by llm-unitize before structural review.",
    )
    parser.add_argument("--stage-a-structural-flags", type=Path, required=True)
    parser.add_argument("--stage-a-structural-review-audit", type=Path, required=True)
    parser.add_argument("--stage-a-review-model-registry", type=Path, required=True)
    parser.add_argument("--stage-a-review-model-key", required=True)
    parser.add_argument("--unitization-review-queue", type=Path, required=True)
    parser.add_argument(
        "--unitization-review-adjudications",
        type=Path,
        required=True,
        help=(
            "Checked-in John adjudications for Stage A reviews; never mutate "
            "the generated queue."
        ),
    )
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--llm-label-audit", type=Path, required=True)
    parser.add_argument("--stage-b-judge-registry", type=Path, required=True)
    parser.add_argument("--labeling-policy", type=Path, required=True)
    parser.add_argument("--lawyer-review-queue", type=Path, required=True)
    parser.add_argument(
        "--lawyer-review-audit",
        type=Path,
        required=True,
        help="JSONL from apply-lawyer-review proving review and audit-gate outcomes.",
    )
    parser.add_argument("--packet-build-input", type=Path, required=True)
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument(
        "--screened-cases",
        type=Path,
        required=True,
        help="Accepted JSONL from acquisition discover-courtlistener.",
    )
    parser.add_argument(
        "--discovery-summary",
        type=Path,
        required=True,
        help="Summary JSON from acquisition discover-courtlistener.",
    )
    parser.add_argument(
        "--discovery-exclusions",
        type=Path,
        required=True,
        help="Exclusion JSONL from acquisition discover-courtlistener.",
    )
    parser.add_argument(
        "--exclusion-source",
        type=Path,
        action="append",
        default=[],
        help="Stage exclusion JSONL to merge. Repeat for every exclusion source.",
    )
    parser.add_argument("--target-clean-cases", type=int, default=150)
    parser.add_argument("--complete-exclusion-ledger-output", type=Path)
    parser.add_argument("--readiness-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_finalize_corpus)


def _add_acquisition_merge_artifacts_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument(
        "--source-root",
        type=Path,
        action="append",
        required=True,
        help="Packet-buildable acquisition root to merge. Repeat in order.",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        action="append",
        help=(
            "Locked labels JSONL to merge into labels.jsonl. Repeat for each "
            "label source; defaults to source-root/labels.jsonl files."
        ),
    )
    parser.add_argument(
        "--prediction-units",
        type=Path,
        action="append",
        help=(
            "Prediction units JSONL to merge into prediction-units.jsonl. "
            "Defaults to source-root/prediction-units.jsonl files."
        ),
    )
    parser.add_argument(
        "--selection",
        type=Path,
        action="append",
        help=(
            "Public packet selection JSONL to merge into "
            "public-packet-selection.jsonl. Defaults to each source root's "
            "packet-buildable selection when present."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_merge_artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] == "freeze":
        from legalforecast.protocol.freeze import cli_freeze

        return cli_freeze(args[1:])
    if args[:2] == ["publish", "aggregate"]:
        from legalforecast.publication.official_aggregate import main as aggregate_main

        return aggregate_main(args[2:])

    parser = build_parser()
    parsed = parser.parse_args(args)
    handler = cast(CommandHandler | None, getattr(parsed, "handler", None))
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(parsed)
    except CommandError as exc:
        print(f"legalforecast: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"legalforecast: missing file: {exc.filename}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"legalforecast: {exc}", file=sys.stderr)
        return 2


def _cmd_discover(args: argparse.Namespace) -> int:
    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)
    records = _read_records(input_path)
    if cast(bool, args.print_search_terms):
        print(json.dumps({"search_terms": list(mtd_discovery_search_terms())}))
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "discover",
            output_path,
            input_path=input_path,
            output_paths=(output_path,),
            record_count=len(records),
            log_record_count=len(records),
            search_terms=mtd_discovery_search_terms(),
        )

    candidates = [
        candidate.to_record() for candidate in discover_mtd_candidates(records)
    ]
    _write_jsonl(output_path, candidates)
    _log_event("discover", "artifact_written", output_path, len(candidates))
    return 0


def _cmd_publish_site(args: argparse.Namespace) -> int:
    result = render_official_results_site(
        official_artifacts_dir=cast(Path, args.official_artifacts_dir),
        output_dir=cast(Path, args.output_dir),
    )
    print(
        json.dumps(
            {
                "artifact_index": str(result.artifact_index_path),
                "index": str(result.index_path),
                "output_dir": str(result.output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_retrieve(args: argparse.Namespace) -> int:
    candidates_path = cast(Path, args.candidates)
    output_path = cast(Path, args.output)
    candidate_records = _read_records(candidates_path)
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "retrieve",
            output_path,
            input_path=candidates_path,
            output_paths=(output_path,),
            record_count=len(candidate_records),
            log_record_count=len(candidate_records),
            case_dev_fixture=str(cast(Path | None, args.case_dev_fixture)),
            live=cast(bool, args.live),
        )

    client = _case_dev_client(
        command="retrieve",
        fixture_path=cast(Path | None, args.case_dev_fixture),
        live=cast(bool, args.live),
    )
    pipeline = DocketRetrievalPipeline(client)
    retrievals = [
        pipeline.retrieve_candidate(
            candidate_id=_candidate_id(record),
            case_id=_required_str(record, "case_id"),
        ).to_record()
        for record in candidate_records
    ]
    _write_jsonl(output_path, retrievals)
    _log_event("retrieve", "artifact_written", output_path, len(retrievals))
    return 0


def _cmd_case_dev_smoke(args: argparse.Namespace) -> int:
    output_path = cast(Path, args.output)
    query_terms = tuple(cast(list[str] | None, args.query_terms) or ())
    config = CaseDevSmokeConfig(
        query_terms=query_terms or case_dev_smoke_query_terms(),
        date_window_start=cast(str | None, args.date_window_start),
        date_window_end=cast(str | None, args.date_window_end),
        per_query_limit=cast(int, args.per_query_limit),
        candidate_retrieval_limit=cast(int, args.candidate_retrieval_limit),
    )
    if cast(bool, args.dry_run):
        result = plan_case_dev_smoke(config)
    else:
        client = _case_dev_client(
            command="case-dev-smoke",
            fixture_path=cast(Path | None, args.case_dev_fixture),
            live=cast(bool, args.live),
        )
        result = run_case_dev_smoke(client, config=config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_case_dev_smoke_markdown(result), encoding="utf-8")
    _log_event(
        "case-dev-smoke",
        "artifact_written",
        output_path,
        result.total_hit_count,
    )
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    documents_path = cast(Path, args.documents)
    output_path = cast(Path, args.output)
    text_output_dir = cast(Path | None, args.text_output_dir)
    document_records = _read_records(documents_path)
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "extract",
            output_path,
            input_path=documents_path,
            output_paths=(output_path,),
            record_count=len(document_records),
            log_record_count=len(document_records),
            text_output_dir=(
                str(text_output_dir) if text_output_dir is not None else None
            ),
        )

    artifacts: list[JsonRecord] = []
    for record in document_records:
        source_document_id = _required_str(record, "source_document_id")
        document_path = Path(_required_str(record, "path"))
        result = extract_pdf_text_with_ocr_fallback(document_path.read_bytes())
        artifact = result.to_text_artifact(source_document_id=source_document_id)
        artifact_record = artifact.to_record()
        artifact_record["source_sha256"] = result.source_sha256
        artifacts.append(artifact_record)
        if text_output_dir is not None:
            safe_document_id = safe_path_component(
                source_document_id,
                field_name="source_document_id",
            )
            text_filename = f"{safe_document_id}.txt"
            _write_text(text_output_dir / text_filename, result.text)
    _write_jsonl(output_path, artifacts)
    _log_event("extract", "artifact_written", output_path, len(artifacts))
    return 0


def _cmd_link(args: argparse.Namespace) -> int:
    retrievals_path = cast(Path, args.retrievals)
    output_path = cast(Path, args.output)
    retrieval_records = _read_records(retrievals_path)
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "link",
            output_path,
            input_path=retrievals_path,
            output_paths=(output_path,),
            record_count=len(retrieval_records),
            log_record_count=len(retrieval_records),
        )

    linkage_records: list[JsonRecord] = []
    for record in retrieval_records:
        entries = tuple(
            _normalized_docket_entry(entry)
            for entry in _required_record_sequence(record, "docket_entries")
        )
        linkage_records.append(
            link_mtd_dispositions(
                entries,
                candidate_id=_required_str(record, "candidate_id"),
                case_id=_required_str(record, "case_id"),
            ).to_record()
        )
    _write_jsonl(output_path, linkage_records)
    _log_event("link", "artifact_written", output_path, len(linkage_records))
    return 0


def _cmd_unitize(args: argparse.Namespace) -> int:
    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)
    records = _read_records(input_path)
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "unitize",
            output_path,
            input_path=input_path,
            output_paths=(output_path,),
            record_count=len(records),
            log_record_count=len(records),
        )

    units: list[JsonRecord] = []
    for record in records:
        result = construct_stage_a_units(_stage_a_input(record))
        units.extend(cast(list[JsonRecord], result.to_record()["units"]))
    _write_jsonl(output_path, units)
    _log_event("unitize", "artifact_written", output_path, len(units))
    return 0


def _cmd_label(args: argparse.Namespace) -> int:
    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)
    records = _read_records(input_path)
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "label",
            output_path,
            input_path=input_path,
            output_paths=(output_path,),
            record_count=len(records),
            log_record_count=len(records),
        )

    labels: list[JsonRecord] = []
    for record in records:
        result = label_stage_b_outcomes(_stage_b_input(record))
        labels.extend(cast(list[JsonRecord], result.to_record()["labels"]))
    _write_jsonl(output_path, labels)
    _log_event("label", "artifact_written", output_path, len(labels))
    return 0


def _cmd_packet_build(args: argparse.Namespace) -> int:
    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)
    records = _read_records(input_path)
    ablation = PacketAblation(cast(str, args.ablation))
    if cast(bool, args.dry_run):
        return _write_dry_run_plan(
            "packet-build",
            output_path,
            input_path=input_path,
            output_paths=(output_path,),
            record_count=len(records),
            log_record_count=len(records),
            ablation=ablation.value,
        )

    packets: list[JsonRecord] = []
    for record in records:
        case_packet = _case_packet(_required_record(record, "case_packet"))
        packet = build_model_packet(
            case_packet=case_packet,
            prediction_units=tuple(
                _prediction_unit(unit)
                for unit in _required_record_sequence(record, "prediction_units")
            ),
            texts=_packet_texts(record, case_packet),
            metadata=_optional_str_mapping(record.get("metadata", {}), "metadata"),
            ablation=ablation,
            target_docket_entry_numbers=_optional_int_tuple(
                record.get("target_docket_entry_numbers")
            ),
            decision_date=_optional_str(record, "decision_date")
            or _optional_str(
                _optional_record(record.get("metadata"), "metadata"),
                "decision_date",
            ),
            related_family_id=_optional_str(record, "related_family_id"),
            mdl_family_id=_optional_str(record, "mdl_family_id"),
        )
        packets.append(packet.to_record())
    _write_jsonl(output_path, packets)
    _log_event("packet-build", "artifact_written", output_path, len(packets))
    return 0


def _cmd_model_run(args: argparse.Namespace) -> int:
    packets_path = cast(Path, args.packets)
    output_path = cast(Path, args.output)
    accounting_output = cast(Path | None, args.accounting_output)
    packet_records = _read_records(packets_path)
    if cast(bool, args.dry_run):
        output_paths = (
            (output_path,)
            if accounting_output is None
            else (
                output_path,
                accounting_output,
            )
        )
        return _write_dry_run_plan(
            "model-run",
            output_path,
            input_path=packets_path,
            output_paths=output_paths,
            record_count=len(packet_records),
            log_record_count=len(packet_records),
            solver_id=cast(str, args.solver_id),
        )

    packets = tuple(_model_packet(record) for record in packet_records)
    mock_output = _mock_output_text(args)
    samples = build_inspect_samples(packets)
    run = run_inspect_fixture(
        samples,
        (
            OfflineMockSolver(
                solver_id=cast(str, args.solver_id),
                raw_output=mock_output,
                input_tokens=100,
                output_tokens=25,
                estimated_cost=0.0,
            ),
        ),
    )
    _write_jsonl(output_path, run.to_records())
    _log_event("model-run", "artifact_written", output_path, len(run.results))
    if accounting_output is not None:
        statuses = _output_statuses(run.to_records())
        accounting = accounting_records_from_inspect_run(
            run,
            evaluation_timestamp=datetime.now(UTC),
            output_status_by_raw_hash=statuses,
        )
        _write_jsonl(
            accounting_output,
            [record.to_record() for record in accounting],
        )
        _log_event(
            "model-run",
            "artifact_written",
            accounting_output,
            len(accounting),
        )
    return 0


def _cmd_eval_run_case(args: argparse.Namespace) -> int:
    timestamp_text = cast(str | None, args.evaluation_timestamp)
    backend = PerCaseExecutionBackend(cast(str, args.backend))
    mock_output = _optional_mock_output_text(args)
    if backend is PerCaseExecutionBackend.FIXTURE and mock_output is None:
        print(
            "legalforecast: eval run-case fixture backend requires --mock-output or "
            "--mock-output-file",
            file=sys.stderr,
        )
        return 2
    if backend is PerCaseExecutionBackend.LIVE and mock_output is not None:
        print(
            "legalforecast: eval run-case live backend must not use fixture "
            "mock output",
            file=sys.stderr,
        )
        return 2
    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=cast(str, args.manifest),
            case_id=cast(str, args.case_id),
            ablation=cast(str, args.ablation),
            output_dir=cast(Path, args.output_dir),
            mock_output=mock_output,
            packet_store_root=cast(str | None, args.packet_store_root),
            results_store_root=cast(str | None, args.results_store_root),
            repeat_count=cast(int, args.repeat_count),
            solver_id=cast(str, args.solver_id),
            backend=backend,
            model_registry_uri=cast(str | None, args.model_registry),
            model_key=cast(str | None, args.model_key),
            expected_packet_object_key=cast(
                str | None,
                args.expected_packet_object_key,
            ),
            expected_packet_sha256=cast(str | None, args.expected_packet_sha256),
            max_tool_calls=cast(int, args.max_tool_calls),
            use_docket_tool=not cast(bool, args.no_docket_tool),
            evaluation_timestamp=(
                _parse_datetime(timestamp_text) if timestamp_text is not None else None
            ),
            timeout_seconds=cast(float, args.timeout_seconds),
            resume_existing=cast(bool, args.resume_existing),
        )
    )
    _log_event(
        "eval-run-case",
        "artifact_written",
        cast(Path, args.output_dir) / "metrics.json",
        len(artifacts.local_paths),
    )
    print(json.dumps(artifacts.to_record(), sort_keys=True))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    runs_path = cast(Path, args.runs)
    labels_path = cast(Path, args.labels)
    output_path = cast(Path, args.output)
    unit_scores_output = cast(Path | None, args.unit_scores_output)
    run_records = _read_records(runs_path)
    label_records = _read_records(labels_path)
    if cast(bool, args.dry_run):
        output_paths = (
            (output_path,)
            if unit_scores_output is None
            else (
                output_path,
                unit_scores_output,
            )
        )
        return _write_dry_run_plan(
            "score",
            output_path,
            input_path=runs_path,
            output_paths=output_paths,
            record_count=len(run_records),
            log_record_count=len(run_records),
            label_count=len(label_records),
        )

    summaries = _score_run_records(
        run_records,
        tuple(_outcome_label(record) for record in label_records),
        base_rate=cast(float | None, args.base_rate),
    )
    _write_json(
        output_path,
        {
            "generated_at": _iso_datetime(datetime.now(UTC)),
            "summaries": [summary.to_record() for summary in summaries],
        },
    )
    _log_event("score", "artifact_written", output_path, len(summaries))
    if unit_scores_output is not None:
        unit_score_records = [
            unit_score.to_record()
            for summary in summaries
            for unit_score in summary.unit_scores
        ]
        _write_jsonl(unit_scores_output, unit_score_records)
        _log_event(
            "score",
            "artifact_written",
            unit_scores_output,
            len(unit_score_records),
        )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    scores_path = cast(Path, args.scores)
    output_dir = cast(Path, args.output_dir)
    score_payload = _read_json_object(scores_path)
    summary_records = _required_record_sequence(score_payload, "summaries")
    accounting_records = (
        _read_records(cast(Path, args.accounting))
        if cast(Path | None, args.accounting) is not None
        else []
    )
    if cast(bool, args.dry_run):
        plan_path = output_dir / "report.plan.json"
        return _write_dry_run_plan(
            "report",
            plan_path,
            input_path=scores_path,
            output_paths=_report_paths(output_dir),
            record_count=len(summary_records),
            accounting_count=len(accounting_records),
        )

    summaries = tuple(_score_summary(record) for record in summary_records)
    accounting_rows = (
        summarize_accounting_leaderboard(accounting_records)
        if accounting_records
        else ()
    )
    inference = _report_inference(
        summaries,
        replicates=cast(int, args.bootstrap_replicates),
        seed=cast(int, args.bootstrap_seed),
    )
    title = cast(str, args.title)
    json_path, csv_path, markdown_path, html_path = _report_paths(output_dir)
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=accounting_rows,
        inference=inference,
        title=title,
    )
    _write_report_artifacts(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        html_path=html_path,
        generated_at=datetime.now(UTC),
    )
    for path in (json_path, csv_path, markdown_path, html_path):
        _log_event("report", "artifact_written", path, len(report.rows))
    return 0


def _cmd_fixture_e2e(args: argparse.Namespace) -> int:
    output_dir = cast(Path, args.output_dir)
    if cast(bool, args.dry_run):
        plan_path = output_dir / "fixture-e2e.plan.json"
        return _write_dry_run_plan(
            "fixture-e2e",
            plan_path,
            output_paths=_fixture_artifact_paths(output_dir),
            record_count=1,
        )

    _run_fixture_e2e(output_dir)
    _log_event(
        "fixture-e2e",
        "artifact_written",
        output_dir / "artifact-manifest.json",
    )
    return 0


def _cmd_pilot_readiness(args: argparse.Namespace) -> int:
    smoke_report_path = cast(Path, args.smoke_report)
    output_path = cast(Path, args.output)
    generated_at_text = cast(str | None, args.generated_at)
    report = build_pilot_readiness_report(
        smoke_report_path.read_text(encoding="utf-8"),
        fixture_output_dir=cast(Path | None, args.fixture_output_dir),
        generated_at=(
            _parse_datetime(generated_at_text)
            if generated_at_text is not None
            else datetime.now(UTC)
        ),
    )
    _write_text(output_path, render_pilot_readiness_markdown(report))
    _log_event(
        "pilot-readiness",
        "artifact_written",
        output_path,
        report.smoke_metrics.clean_mtd_candidate_count,
    )
    return 0


def _cmd_pilot_fallback(args: argparse.Namespace) -> int:
    smoke_report_path = cast(Path, args.smoke_report)
    output_path = cast(Path, args.output)
    generated_at_text = cast(str | None, args.generated_at)
    attempt_limit = cast(int, args.attempt_limit)
    page_size = cast(int, args.courtlistener_page_size)
    smoke_report_text = smoke_report_path.read_text(encoding="utf-8")
    credentials = FallbackCredentialStatus.from_env()
    fallback_candidates = tuple(
        candidate
        for candidate in parse_case_dev_fallback_candidates(smoke_report_text)
        if candidate.needs_docket_fallback
    )
    attempts = None
    courtlistener_fixture = cast(Path | None, args.courtlistener_fixture)
    live_courtlistener = cast(bool, args.live_courtlistener)
    if courtlistener_fixture is not None:
        attempts = run_courtlistener_fallback_attempts(
            fallback_candidates,
            client=CourtListenerClient(
                config=CourtListenerConfig.from_env(),
                transport=CourtListenerFixtureTransport.from_jsonl(
                    courtlistener_fixture
                ),
            ),
            attempt_limit=attempt_limit,
            page_size=page_size,
        )
    elif live_courtlistener and credentials.courtlistener_token_present:
        attempts = run_courtlistener_fallback_attempts(
            fallback_candidates,
            client=CourtListenerClient(config=CourtListenerConfig.from_env()),
            attempt_limit=attempt_limit,
            page_size=page_size,
        )

    report = build_fallback_reconstruction_pilot_report(
        smoke_report_text,
        credentials=credentials,
        attempts=attempts,
        attempt_limit=attempt_limit,
        generated_at=(
            _parse_datetime(generated_at_text)
            if generated_at_text is not None
            else datetime.now(UTC)
        ),
        live_courtlistener_requested=live_courtlistener,
    )
    _write_text(output_path, render_fallback_reconstruction_pilot_markdown(report))
    _log_event(
        "pilot-fallback-reconstruction",
        "artifact_written",
        output_path,
        len(report.attempts),
    )
    return 0


def _cmd_acquisition_plan(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    input_path = cast(Path, args.core_filter_results)
    output_path = _acquisition_path(
        args,
        "budget_plan_output",
        output_root / "missing-core-budget-plan.json",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "missing-core-budget-exclusions.jsonl",
    )
    records = _read_records(input_path)
    dry_run = _acquisition_dry_run(args)
    plan = plan_missing_core_document_budget(
        (_core_document_filter_result(record) for record in records),
        dry_run=dry_run,
        max_missing_core_documents_per_case=cast(
            int,
            args.max_missing_core_documents_per_case,
        ),
        cost_per_document_usd=cast(str, args.cost_per_document_usd),
        max_projected_budget_usd=cast(str, args.max_projected_budget_usd),
        truncate_to_budget=cast(bool, args.truncate_to_budget),
        target_case_count=cast(int | None, args.target_case_count),
    )
    write_missing_core_budget_plan(plan, output_path)
    exclusion_ledger = merge_exclusion_ledger_records(
        ExclusionLedgerEntry(
            candidate_id=case_plan.candidate_id,
            case_id=case_plan.candidate_id,
            stage=ExclusionStage.EXTRACTION,
            reason=case_plan.exclusion_reasons[0],
            secondary_reasons=case_plan.exclusion_reasons[1:],
            source_entry_ids=(),
            source_document_ids=case_plan.purchase_document_ids,
            notes=_missing_core_exclusion_notes(case_plan, plan),
        ).to_record()
        for case_plan in plan.excluded_case_plans
    )
    exclusion_ledger.write_jsonl(exclusions_path)
    _write_acquisition_completion(
        args,
        stage="acquisition-plan",
        input_paths=(input_path,),
        output_paths=(output_path, exclusions_path),
        record_count=len(plan.case_plans),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "total_missing_core_documents": plan.total_missing_core_documents,
            "total_estimated_cost_usd": plan.total_estimated_cost_usd,
            "frontier_truncated": plan.frontier_truncated,
            "target_case_count": plan.target_case_count,
            "target_case_count_met": plan.target_case_count_met,
            "omitted_candidate_count": len(plan.omitted_candidate_ids),
            "excluded_case_count": len(plan.excluded_case_plans),
        },
    )
    return 0


@dataclass(frozen=True, slots=True)
class _TargetPreparationProfile:
    stage: str
    label: str
    summary_filename: str
    config_filename: str
    summary_schema: str
    config_schema: str
    attempt_schema: str
    exact_target_case_count: int | None
    emit_full_candidate_frontier: bool

    def target_case_count(self, args: argparse.Namespace) -> int:
        if self.exact_target_case_count is not None:
            return self.exact_target_case_count
        return cast(int, args.target_case_count)


_TARGET_100_PREPARATION = _TargetPreparationProfile(
    stage="prepare-target-100",
    label="target-100",
    summary_filename="target-100-preparation-summary.json",
    config_filename="target-100-config.json",
    summary_schema="legalforecast.target_100_preparation.v1",
    config_schema="legalforecast.target_100_config.v1",
    attempt_schema="legalforecast.target_100_attempt.v1",
    exact_target_case_count=100,
    emit_full_candidate_frontier=False,
)
_TARGET_COHORT_PREPARATION = _TargetPreparationProfile(
    stage="prepare-target-cohort",
    label="target-cohort",
    summary_filename="target-cohort-preparation-summary.json",
    config_filename="target-cohort-config.json",
    summary_schema="legalforecast.target_cohort_preparation.v1",
    config_schema="legalforecast.target_cohort_config.v1",
    attempt_schema="legalforecast.target_cohort_attempt.v1",
    exact_target_case_count=None,
    emit_full_candidate_frontier=True,
)


def _cmd_acquisition_prepare_target_100(args: argparse.Namespace) -> int:
    """Run the exact-100 compatibility preparation command."""

    return _cmd_acquisition_prepare_target(args, profile=_TARGET_100_PREPARATION)


def _cmd_acquisition_prepare_target_cohort(args: argparse.Namespace) -> int:
    """Run generic noncharging preparation for an explicit target size."""

    return _cmd_acquisition_prepare_target(args, profile=_TARGET_COHORT_PREPARATION)


def _cmd_acquisition_prepare_target(
    args: argparse.Namespace,
    *,
    profile: _TargetPreparationProfile,
) -> int:
    """Run the shared public-first chain and emit clearance inputs."""

    output_root = cast(Path, args.output_root)
    target_case_count = profile.target_case_count(args)
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / profile.summary_filename,
    )
    snapshot = cast(Path, args.snapshot)
    expected_cycle_hash = cast(str, args.expected_cycle_hash)
    try:
        _validate_target_100_paths(
            args=args,
            profile=profile,
            output_root=output_root,
            summary_path=summary_path,
            snapshot=snapshot,
            raw_html_dir=cast(Path | None, args.raw_html_dir),
            fixture_documents=cast(Path | None, args.fixture_documents),
            courtlistener_fixture=cast(Path | None, args.courtlistener_fixture),
            request_ledger=cast(Path | None, args.request_ledger),
        )
    except CommandError as exc:
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=str(exc),
            protected_paths=_target_100_protected_paths(args),
        )
        raise
    try:
        snapshot_manifest = verify_snapshot(
            snapshot,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=str(exc),
            protected_paths=_target_100_protected_paths(args),
        )
        raise CommandError(str(exc)) from exc
    candidate_pool_size = len(_read_records(snapshot / "screened-cases.jsonl"))
    config_type = (
        Target100PreparationConfig
        if profile.exact_target_case_count is not None
        else TargetCohortPreparationConfig
    )
    config = config_type(
        output_root=output_root,
        snapshot=snapshot,
        expected_cycle_hash=expected_cycle_hash,
        candidate_pool_size=candidate_pool_size,
        target_case_count=target_case_count,
        cost_per_document_usd=cast(str, args.cost_per_document_usd),
        max_projected_budget_usd=cast(str, args.max_projected_budget_usd),
        max_missing_core_documents_per_case=cast(
            int, args.max_missing_core_documents_per_case
        ),
        raw_html_dir=cast(Path | None, args.raw_html_dir),
        use_embedded_entries=cast(bool, args.use_embedded_entries),
        live_public_download=cast(bool, args.live_public_download),
        fixture_documents=cast(Path | None, args.fixture_documents),
        live_courtlistener=cast(bool, args.live_courtlistener),
        courtlistener_fixture=cast(Path | None, args.courtlistener_fixture),
        request_ledger=cast(Path | None, args.request_ledger),
        courtlistener_rate_profile=cast(str, args.courtlistener_rate_profile),
        request_budget_max_wait_seconds=cast(
            float, args.request_budget_max_wait_seconds
        ),
        resume=cast(bool, args.resume),
    )
    try:
        commands = (
            build_target_100_stage_commands(cast(Target100PreparationConfig, config))
            if profile.exact_target_case_count is not None
            else build_target_cohort_stage_commands(
                cast(TargetCohortPreparationConfig, config)
            )
        )
    except (Target100PreparationError, TargetCohortPreparationError) as exc:
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=str(exc),
            protected_paths=_target_100_protected_paths(args),
        )
        raise CommandError(str(exc)) from exc
    command_records = [
        {"stage": command.stage, "argv": list(command.argv)} for command in commands
    ]
    config_path = output_root / profile.config_filename
    success_run_card_path = _acquisition_path(
        args,
        "run_card_output",
        output_root / f"run-cards/{profile.stage}.json",
    )
    success_log_path = _acquisition_path(
        args,
        "log_output",
        output_root / f"logs/{profile.stage}.jsonl",
    )
    try:
        config_record = _target_100_config_record(
            config,
            profile=profile,
            snapshot_manifest=snapshot_manifest,
            stage_commands=command_records,
            driver_execute=not _acquisition_dry_run(args),
            wrapper_artifact_paths={
                "summary": summary_path,
                "run_card": success_run_card_path,
                "log": success_log_path,
            },
        )
        if cast(bool, args.resume):
            completed_evidence_exists = (
                summary_path.exists() or success_run_card_path.exists()
            )
            if completed_evidence_exists:
                if not config_path.is_file():
                    raise CommandError(
                        f"{profile.label} committed config is missing; refusing "
                        "completed-run reconstruction"
                    )
                if not summary_path.is_file():
                    raise CommandError(
                        f"{profile.label} committed success summary is missing; "
                        "refusing child-stage resume"
                    )
                if not success_run_card_path.is_file():
                    raise CommandError(
                        f"{profile.label} committed success run card is missing"
                    )
                _ensure_target_100_config(
                    config_path,
                    config_record,
                    profile=profile,
                    resume=True,
                )
                _verify_completed_preparation_for_frontier(
                    preparation_root=output_root,
                    preparation_summary_path=summary_path,
                    preparation_config_path=config_path,
                    snapshot_manifest_path=snapshot / "manifest.json",
                )
                return 0
        _ensure_target_100_config(
            config_path,
            config_record,
            profile=profile,
            resume=cast(bool, args.resume),
        )
    except (CommandError, OSError, UnicodeError, ValueError) as exc:
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=str(exc),
            protected_paths=_target_100_protected_paths(args),
        )
        if isinstance(exc, CommandError):
            raise
        raise CommandError(str(exc)) from exc
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_json(
            summary_path,
            {
                "schema_version": profile.summary_schema,
                "dry_run": True,
                "target_case_count": target_case_count,
                "candidate_pool_size": config.candidate_pool_size,
                "config_sha256": config_record["config_sha256"],
                "stage_commands": command_records,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
        )
        _write_acquisition_completion(
            args,
            stage=profile.stage,
            input_paths=(config.snapshot,),
            output_paths=(summary_path,),
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
        )
        return 0

    if candidate_pool_size < target_case_count:
        reason = (
            f"complete snapshot contains only {candidate_pool_size} viable cases; "
            f"{target_case_count} are required"
        )
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=reason,
            extra={"config_sha256": config_record["config_sha256"]},
            protected_paths=_target_100_protected_paths(args),
        )
        raise CommandError(reason)

    for command in commands:
        result = main(command.argv)
        if result != 0:
            reason = (
                f"{profile.label} preparation stopped at {command.stage}; "
                "fix the recorded failure and rerun with --resume"
            )
            _write_target_100_attempt_failure(
                args,
                profile=profile,
                reason=reason,
                extra={"config_sha256": config_record["config_sha256"]},
                protected_paths=_target_100_protected_paths(args),
            )
            raise CommandError(reason)

    try:
        _prepare_target_100_clearance_inputs(
            output_root,
            resume=cast(bool, args.resume),
        )
    except (CommandError, TargetCohortProjectionError) as exc:
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=str(exc),
            extra={"config_sha256": config_record["config_sha256"]},
            protected_paths=_target_100_protected_paths(args),
        )
        if isinstance(exc, CommandError):
            raise
        raise CommandError(str(exc)) from exc

    budget_plan_path = output_root / "05-budget" / "missing-core-budget-plan.json"
    budget_plan = _missing_core_budget_plan(_read_json_object(budget_plan_path))
    if budget_plan.dry_run:
        raise CommandError("target-100 budget plan must be executable, not dry-run")
    if (
        not budget_plan.target_case_count_met
        or len(budget_plan.case_plans) != target_case_count
    ):
        reason = (
            f"{profile.label} preparation did not produce exactly "
            f"{target_case_count} complete cases; "
            "acquire additional screened candidates without relaxing any gate"
        )
        _write_target_100_attempt_failure(
            args,
            profile=profile,
            reason=reason,
            extra={"config_sha256": config_record["config_sha256"]},
            protected_paths=_target_100_protected_paths(args),
        )
        raise CommandError(reason)
    full_frontier: tuple[Path, int, str] | None = None
    if profile.emit_full_candidate_frontier:
        try:
            full_frontier = _prepare_full_candidate_frontier(
                output_root,
                budget_plan=budget_plan,
                target_case_count=config.target_case_count,
                cost_per_document_usd=config.cost_per_document_usd,
                max_missing_core_documents_per_case=(
                    config.max_missing_core_documents_per_case
                ),
                snapshot_manifest_path=config.snapshot / "manifest.json",
                preparation_config_path=config_path,
                frontier_path=(output_root / "05-budget/full-candidate-frontier.json"),
                resume=cast(bool, args.resume),
            )
        except (CommandError, OSError, UnicodeError, ValueError) as exc:
            _write_target_100_attempt_failure(
                args,
                profile=profile,
                reason=str(exc),
                extra={"config_sha256": config_record["config_sha256"]},
                protected_paths=_target_100_protected_paths(args),
            )
            if isinstance(exc, CommandError):
                raise
            raise CommandError(str(exc)) from exc
    stage_commitments = _target_100_stage_commitments(output_root)
    stage_input_commitments = _target_100_stage_input_commitments(
        output_root, config=config
    )
    selected_ids = [plan.candidate_id for plan in budget_plan.case_plans]
    _write_json(
        summary_path,
        {
            "schema_version": profile.summary_schema,
            "dry_run": False,
            "target_case_count": target_case_count,
            "candidate_pool_size": config.candidate_pool_size,
            "snapshot_manifest_sha256": "sha256:"
            + hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest(),
            "snapshot_batch_digest": snapshot_manifest["batch_digest"],
            "config_sha256": config_record["config_sha256"],
            "stage_input_commitments": stage_input_commitments,
            "stage_commitments": stage_commitments,
            "selected_candidate_ids_sha256": _canonical_json_sha256(selected_ids),
            "frontier_sha256": _canonical_json_sha256(
                [row.to_record() for row in budget_plan.frontier_rows]
            ),
            "selected_case_count": len(budget_plan.case_plans),
            "total_missing_core_documents": (budget_plan.total_missing_core_documents),
            "total_estimated_cost_usd": budget_plan.total_estimated_cost_usd,
            "cost_per_document_usd": str(budget_plan.cost_per_document),
            "max_projected_budget_usd": budget_plan.max_projected_budget_usd,
            "max_missing_core_documents_per_case": (
                budget_plan.max_missing_core_documents_per_case
            ),
            **(
                {
                    "full_candidate_frontier": str(full_frontier[0]),
                    "full_candidate_frontier_count": full_frontier[1],
                    "full_candidate_frontier_sha256": full_frontier[2],
                }
                if full_frontier is not None
                else {}
            ),
            "budget_plan": str(budget_plan_path),
            "stage_commands": command_records,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "budget_status": "provisional_pre_clearance",
            "next_stage": "clear-disclosures",
            "next_stage_blocked_until": (
                "authenticated human review receipts exist for every free "
                "document; then project-target-cohort must recompute the exact "
                "post-clearance frontier before any purchase"
            ),
        },
    )
    _write_acquisition_completion(
        args,
        stage=profile.stage,
        input_paths=(config.snapshot,),
        output_paths=(config_path, summary_path, budget_plan_path),
        record_count=target_case_count,
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "selected_case_count": target_case_count,
            "total_estimated_cost_usd": budget_plan.total_estimated_cost_usd,
            "config_sha256": config_record["config_sha256"],
            "completed_stages": list(stage_commitments),
            "zero_paid_activity_evidence": True,
        },
    )
    return 0


@dataclass(frozen=True, slots=True)
class _VerifiedPreparationForFrontier:
    target_case_count: int
    cost_per_document_usd: str
    max_missing_core_documents_per_case: int
    budget_plan: MissingCoreBudgetPlan
    success_run_card_path: Path
    protected_paths: tuple[Path, ...]


def _cmd_acquisition_materialize_target_frontier(
    args: argparse.Namespace,
) -> int:
    """Materialize a full frontier without mutating or rerunning preparation."""

    output_root = cast(Path, args.output_root)
    preparation_root = cast(Path, args.preparation_root)
    preparation_summary_path = cast(Path, args.preparation_summary)
    preparation_config_path = cast(Path, args.preparation_config)
    snapshot_manifest_path = cast(Path, args.snapshot_manifest)
    frontier_path = output_root / "full-candidate-frontier.json"
    base_input_paths = (
        preparation_root,
        preparation_summary_path,
        preparation_config_path,
        snapshot_manifest_path,
    )
    verified = _verify_completed_preparation_for_frontier(
        preparation_root=preparation_root,
        preparation_summary_path=preparation_summary_path,
        preparation_config_path=preparation_config_path,
        snapshot_manifest_path=snapshot_manifest_path,
    )
    input_paths = (*base_input_paths, verified.success_run_card_path)
    _validate_materializer_output_paths(
        args,
        output_root=output_root,
        frontier_path=frontier_path,
        input_paths=verified.protected_paths,
    )
    dry_run = _acquisition_dry_run(args)
    run_card_path = _acquisition_path(
        args,
        "run_card_output",
        output_root / "run-cards/materialize-target-cohort-frontier.json",
    )
    if not dry_run and cast(bool, args.resume) and run_card_path.exists():
        _, expected_frontier_count, expected_frontier_sha256 = (
            _prepare_full_candidate_frontier(
                preparation_root,
                budget_plan=verified.budget_plan,
                target_case_count=verified.target_case_count,
                cost_per_document_usd=verified.cost_per_document_usd,
                max_missing_core_documents_per_case=(
                    verified.max_missing_core_documents_per_case
                ),
                snapshot_manifest_path=snapshot_manifest_path,
                preparation_config_path=preparation_config_path,
                frontier_path=frontier_path,
                resume=True,
                additional_source_commitments={
                    "preparation_summary_sha256": preparation_summary_path,
                    "preparation_success_run_card_sha256": (
                        verified.success_run_card_path
                    ),
                },
                write=False,
            )
        )
        _verify_completed_materializer_run_card(
            run_card_path=run_card_path,
            frontier_path=frontier_path,
            input_paths=input_paths,
            target_case_count=verified.target_case_count,
            preparation_summary_path=preparation_summary_path,
            preparation_config_path=preparation_config_path,
            snapshot_manifest_path=snapshot_manifest_path,
            preparation_success_run_card_path=verified.success_run_card_path,
            expected_frontier_sha256=expected_frontier_sha256,
            expected_frontier_count=expected_frontier_count,
        )
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    _, frontier_count, _ = _prepare_full_candidate_frontier(
        preparation_root,
        budget_plan=verified.budget_plan,
        target_case_count=verified.target_case_count,
        cost_per_document_usd=verified.cost_per_document_usd,
        max_missing_core_documents_per_case=(
            verified.max_missing_core_documents_per_case
        ),
        snapshot_manifest_path=snapshot_manifest_path,
        preparation_config_path=preparation_config_path,
        frontier_path=frontier_path,
        resume=cast(bool, args.resume),
        additional_source_commitments={
            "preparation_summary_sha256": preparation_summary_path,
            "preparation_success_run_card_sha256": verified.success_run_card_path,
        },
        write=not dry_run,
    )
    _write_acquisition_completion(
        args,
        stage="materialize-target-cohort-frontier",
        input_paths=input_paths,
        output_paths=(frontier_path,),
        record_count=frontier_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "target_case_count": verified.target_case_count,
            "frontier_sha256": (_path_sha256(frontier_path) if not dry_run else None),
            "source_commitments": {
                "preparation_summary": _path_sha256(preparation_summary_path),
                "preparation_config": _path_sha256(preparation_config_path),
                "snapshot_manifest": _path_sha256(snapshot_manifest_path),
                "preparation_success_run_card": _path_sha256(
                    verified.success_run_card_path
                ),
            },
            "output_commitments": {
                "full_candidate_frontier": (
                    _path_sha256(frontier_path) if not dry_run else None
                )
            },
            "zero_provider_activity_evidence": True,
        },
    )
    return 0


def _verify_completed_preparation_for_frontier(
    *,
    preparation_root: Path,
    preparation_summary_path: Path,
    preparation_config_path: Path,
    snapshot_manifest_path: Path,
) -> _VerifiedPreparationForFrontier:
    summary = _read_json_object(preparation_summary_path)
    config = _read_json_object(preparation_config_path)
    snapshot_manifest = _read_json_object(snapshot_manifest_path)
    summary_schema = summary.get("schema_version")
    config_schema = config.get("schema_version")
    if not isinstance(summary_schema, str) or not isinstance(config_schema, str):
        raise CommandError("preparation schema versions must be strings")
    schema_pair = (summary_schema, config_schema)
    profile_by_schema = {
        (
            "legalforecast.target_100_preparation.v1",
            "legalforecast.target_100_config.v1",
        ): _TARGET_100_PREPARATION,
        (
            "legalforecast.target_cohort_preparation.v1",
            "legalforecast.target_cohort_config.v1",
        ): _TARGET_COHORT_PREPARATION,
    }
    profile = profile_by_schema.get(schema_pair)
    if profile is None:
        raise CommandError("unsupported or mismatched preparation schema pair")
    config_payload = dict(config)
    committed_config_sha256 = config_payload.pop("config_sha256", None)
    if committed_config_sha256 != _canonical_json_sha256(config_payload):
        raise CommandError("preparation config self-hash mismatch")
    if summary.get("config_sha256") != committed_config_sha256:
        raise CommandError("preparation summary config commitment mismatch")
    if (
        summary.get("dry_run") is not False
        or summary.get("paid_activity_executed") is not False
        or config.get("driver_execute") is not True
    ):
        raise CommandError(
            "frontier materialization requires executed nonpaid preparation"
        )
    target_case_count = _target_case_count_for_materialized_frontier(
        profile=profile,
        config=config,
        summary=summary,
    )
    expected_config_path = preparation_root / profile.config_filename
    if preparation_config_path.resolve() != expected_config_path.resolve():
        raise CommandError("preparation config is outside its canonical root path")
    wrapper_paths = config.get("wrapper_artifact_paths")
    if not isinstance(wrapper_paths, Mapping):
        raise CommandError("preparation config lacks wrapper artifact paths")
    typed_wrapper_paths = cast(Mapping[str, object], wrapper_paths)
    if typed_wrapper_paths.get("summary") != str(preparation_summary_path.resolve()):
        raise CommandError("preparation summary path differs from frozen config")
    configured_snapshot = config.get("snapshot")
    if not isinstance(configured_snapshot, str):
        raise CommandError("preparation config lacks snapshot path")
    if (
        snapshot_manifest_path.resolve()
        != (Path(configured_snapshot) / "manifest.json").resolve()
    ):
        raise CommandError("snapshot manifest path differs from frozen config")
    snapshot_sha256 = _path_sha256(snapshot_manifest_path)
    if (
        config.get("snapshot_manifest_sha256") != snapshot_sha256
        or summary.get("snapshot_manifest_sha256") != snapshot_sha256
        or config.get("snapshot_cycle_hash") != snapshot_manifest.get("cycle_hash")
        or config.get("snapshot_batch_digest") != snapshot_manifest.get("batch_digest")
        or summary.get("snapshot_batch_digest") != snapshot_manifest.get("batch_digest")
    ):
        raise CommandError("preparation snapshot lineage commitment mismatch")
    committed_inputs = summary.get("stage_input_commitments")
    committed_outputs = summary.get("stage_commitments")
    if not isinstance(committed_inputs, Mapping) or not isinstance(
        committed_outputs, Mapping
    ):
        raise CommandError("preparation summary lacks exhaustive stage commitments")
    expected_inputs, independent_inputs = _expected_preparation_input_commitments(
        preparation_root=preparation_root,
        config=config,
    )
    if dict(cast(Mapping[str, Any], committed_inputs)) != expected_inputs:
        raise CommandError(
            "preparation stage input commitment mismatch or non-exhaustive mapping"
        )
    actual_outputs = _target_100_stage_commitments(preparation_root)
    if dict(cast(Mapping[str, Any], committed_outputs)) != actual_outputs:
        raise CommandError(
            "preparation stage output commitment mismatch; mutated or unexpected "
            "stage artifact"
        )
    budget_path = preparation_root / "05-budget/missing-core-budget-plan.json"
    budget_record = _read_json_object(budget_path)
    budget_plan = _missing_core_budget_plan(budget_record)
    recomputed_budget = plan_missing_core_document_budget(
        (
            _core_document_filter_result(record)
            for record in _read_records(
                preparation_root / "04-core-filter/core-filter-results.jsonl"
            )
        ),
        dry_run=False,
        max_missing_core_documents_per_case=_required_int(
            config, "max_missing_core_documents_per_case"
        ),
        cost_per_document_usd=_required_str(config, "cost_per_document_usd"),
        max_projected_budget_usd=_required_str(config, "max_projected_budget_usd"),
        truncate_to_budget=True,
        target_case_count=target_case_count,
    )
    if budget_record != recomputed_budget.to_record():
        raise CommandError("preparation budget differs from canonical core-filter plan")
    budget_plan = recomputed_budget
    selected_ids = [plan.candidate_id for plan in budget_plan.case_plans]
    candidate_pool_size = len(
        _read_records(Path(configured_snapshot) / "screened-cases.jsonl")
    )
    raw_summary_budget_path = summary.get("budget_plan")
    if (
        not isinstance(raw_summary_budget_path, str)
        or Path(raw_summary_budget_path).resolve() != budget_path.resolve()
    ):
        raise CommandError("preparation summary budget path differs")
    if (
        len(selected_ids) != target_case_count
        or summary.get("selected_candidate_ids_sha256")
        != _canonical_json_sha256(selected_ids)
        or summary.get("frontier_sha256")
        != _canonical_json_sha256(
            [row.to_record() for row in budget_plan.frontier_rows]
        )
    ):
        raise CommandError(
            "preparation budget or selected frontier commitment mismatch"
        )
    if (
        summary.get("stage_commands") is None
        or _semantic_preparation_stage_commands(summary.get("stage_commands"))
        != config.get("stage_commands")
        or summary.get("paid_activity_requested") is not False
        or summary.get("budget_status") != "provisional_pre_clearance"
        or summary.get("next_stage") != "clear-disclosures"
        or summary.get("selected_case_count") != target_case_count
        or summary.get("candidate_pool_size") != candidate_pool_size
        or config.get("candidate_pool_size") != candidate_pool_size
        or summary.get("total_missing_core_documents")
        != budget_plan.total_missing_core_documents
        or summary.get("total_estimated_cost_usd")
        != budget_plan.total_estimated_cost_usd
        or summary.get("cost_per_document_usd") != budget_plan.cost_per_document_usd
        or summary.get("max_projected_budget_usd")
        != budget_plan.max_projected_budget_usd
        or summary.get("max_missing_core_documents_per_case")
        != budget_plan.max_missing_core_documents_per_case
    ):
        raise CommandError("preparation summary differs from frozen canonical plan")
    if profile.emit_full_candidate_frontier:
        _verify_generic_preparation_frontier(
            preparation_root=preparation_root,
            preparation_summary=summary,
            preparation_config_path=preparation_config_path,
            snapshot_manifest_path=snapshot_manifest_path,
            candidate_pool_size=candidate_pool_size,
        )
    raw_run_card_path = typed_wrapper_paths.get("run_card")
    if not isinstance(raw_run_card_path, str):
        raise CommandError("preparation config lacks success run-card path")
    success_run_card_path = Path(raw_run_card_path)
    if not _completed_stage_run_card_exists(success_run_card_path, stage=profile.stage):
        raise CommandError(
            "completed preparation success run card is missing or invalid"
        )
    success_card = _read_json_object(success_run_card_path)
    if (
        success_card.get("dry_run") is not False
        or success_card.get("execute") is not True
        or success_card.get("paid_activity_requested") is not False
        or success_card.get("paid_activity_executed") is not False
        or success_card.get("record_count") != target_case_count
        or success_card.get("config_sha256") != committed_config_sha256
        or success_card.get("selected_case_count") != target_case_count
        or success_card.get("total_estimated_cost_usd")
        != budget_plan.total_estimated_cost_usd
        or success_card.get("completed_stages") != list(actual_outputs)
        or success_card.get("zero_paid_activity_evidence") is not True
    ):
        raise CommandError("completed preparation success run card is inconsistent")
    committed_output_paths = success_card.get("output_paths")
    if not isinstance(committed_output_paths, Sequence) or isinstance(
        committed_output_paths, (str, bytes)
    ):
        raise CommandError("preparation success run card lacks output paths")
    raw_output_paths = cast(Sequence[object], committed_output_paths)
    if any(not isinstance(path, str) for path in raw_output_paths):
        raise CommandError("preparation success run-card output paths are malformed")
    actual_output_paths = [
        Path(path).resolve() for path in cast(Sequence[str], raw_output_paths)
    ]
    required_output_paths = [
        preparation_config_path.resolve(),
        preparation_summary_path.resolve(),
        budget_path.resolve(),
    ]
    if actual_output_paths != required_output_paths:
        raise CommandError("preparation success run card output paths differ")
    raw_input_paths = success_card.get("input_paths")
    if not isinstance(raw_input_paths, Sequence) or isinstance(
        raw_input_paths, (str, bytes)
    ):
        raise CommandError("preparation success run card lacks input paths")
    expected_success_inputs = [Path(configured_snapshot).resolve()]
    if [
        Path(str(path)).resolve() for path in cast(Sequence[object], raw_input_paths)
    ] != expected_success_inputs:
        raise CommandError("preparation success run card input paths differ")
    wrapper_protected_paths = tuple(
        Path(value) for value in typed_wrapper_paths.values() if isinstance(value, str)
    )
    protected_paths = (
        preparation_root,
        preparation_summary_path,
        preparation_config_path,
        snapshot_manifest_path,
        Path(configured_snapshot),
        success_run_card_path,
        *wrapper_protected_paths,
        *(
            Path(path)
            for stage_paths in expected_inputs.values()
            for path in stage_paths
        ),
        *independent_inputs,
    )
    return _VerifiedPreparationForFrontier(
        target_case_count=target_case_count,
        cost_per_document_usd=_required_str(config, "cost_per_document_usd"),
        max_missing_core_documents_per_case=_required_int(
            config, "max_missing_core_documents_per_case"
        ),
        budget_plan=budget_plan,
        success_run_card_path=success_run_card_path,
        protected_paths=tuple(dict.fromkeys(protected_paths)),
    )


def _verify_completed_materializer_run_card(
    *,
    run_card_path: Path,
    frontier_path: Path,
    input_paths: Sequence[Path],
    target_case_count: int,
    preparation_summary_path: Path,
    preparation_config_path: Path,
    snapshot_manifest_path: Path,
    preparation_success_run_card_path: Path,
    expected_frontier_sha256: str,
    expected_frontier_count: int,
) -> None:
    if run_card_path.is_symlink() or not run_card_path.is_file():
        raise CommandError("completed materializer run card is not a regular file")
    card = _read_json_object(run_card_path)
    expected_inputs = [str(path) for path in input_paths]
    expected_outputs = [str(frontier_path)]
    expected_sources = {
        "preparation_summary": _path_sha256(preparation_summary_path),
        "preparation_config": _path_sha256(preparation_config_path),
        "snapshot_manifest": _path_sha256(snapshot_manifest_path),
        "preparation_success_run_card": _path_sha256(preparation_success_run_card_path),
    }
    if (
        card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "materialize-target-cohort-frontier"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or card.get("record_count") != expected_frontier_count
        or card.get("target_case_count") != target_case_count
        or card.get("input_paths") != expected_inputs
        or card.get("output_paths") != expected_outputs
        or card.get("source_commitments") != expected_sources
        or card.get("zero_provider_activity_evidence") is not True
    ):
        raise CommandError("completed materializer run card contract mismatch")
    if frontier_path.is_symlink() or not frontier_path.is_file():
        raise CommandError("completed materializer frontier output is missing")
    frontier_sha256 = _path_sha256(frontier_path)
    if (
        frontier_sha256 != expected_frontier_sha256
        or card.get("frontier_sha256") != frontier_sha256
        or card.get("output_commitments")
        != {"full_candidate_frontier": frontier_sha256}
    ):
        raise CommandError("completed materializer frontier commitment mismatch")


def _verify_generic_preparation_frontier(
    *,
    preparation_root: Path,
    preparation_summary: Mapping[str, Any],
    preparation_config_path: Path,
    snapshot_manifest_path: Path,
    candidate_pool_size: int,
) -> None:
    frontier_path = preparation_root / "05-budget/full-candidate-frontier.json"
    if frontier_path.is_symlink() or not frontier_path.is_file():
        raise CommandError("generic preparation full frontier is missing")
    frontier_sha256 = _path_sha256(frontier_path)
    raw_frontier_path = preparation_summary.get("full_candidate_frontier")
    if (
        not isinstance(raw_frontier_path, str)
        or Path(raw_frontier_path).resolve() != frontier_path.resolve()
        or preparation_summary.get("full_candidate_frontier_sha256") != frontier_sha256
        or preparation_summary.get("full_candidate_frontier_count")
        != candidate_pool_size
    ):
        raise CommandError("generic preparation full frontier summary mismatch")
    artifact = _read_json_object(frontier_path)
    candidates = _verified_target_cohort_frontier_rows(artifact)
    if len(candidates) != candidate_pool_size:
        raise CommandError("generic preparation full frontier count mismatch")
    policy = cast(Mapping[str, Any], artifact["policy"])
    expected_commitments = {
        "snapshot_manifest_sha256": _path_sha256(snapshot_manifest_path),
        "preparation_config_sha256": _path_sha256(preparation_config_path),
        "reconciled_selection_sha256": _path_sha256(
            preparation_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
        ),
        "case_relevance_sha256": _path_sha256(
            preparation_root / "03-gap-bridge/case-relevance.jsonl"
        ),
        "download_manifest_sha256": _path_sha256(
            preparation_root / "03c-merged-downloads/document-downloads-merged.jsonl"
        ),
        "core_filter_results_sha256": _path_sha256(
            preparation_root / "04-core-filter/core-filter-results.jsonl"
        ),
        "provisional_budget_plan_sha256": _path_sha256(
            preparation_root / "05-budget/missing-core-budget-plan.json"
        ),
        "restriction_evidence_sha256": _path_sha256(
            preparation_root / "06-clearance-inputs/restriction-evidence.jsonl"
        ),
        "disclosure_review_requests_sha256": _path_sha256(
            preparation_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
    }
    if policy.get("source_commitments") != expected_commitments:
        raise CommandError("generic preparation full frontier lineage mismatch")


def _target_case_count_for_materialized_frontier(
    *,
    profile: _TargetPreparationProfile,
    config: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> int:
    config_count = config.get("target_case_count")
    summary_count = summary.get("target_case_count")
    if (
        not isinstance(summary_count, int)
        or isinstance(summary_count, bool)
        or summary_count < 1
    ):
        raise CommandError("preparation target case count is missing or invalid")
    if profile.exact_target_case_count is not None:
        exact_count = profile.exact_target_case_count
        if summary_count != exact_count or config_count != exact_count:
            raise CommandError("preparation target case count commitment mismatch")
        return exact_count
    if (
        not isinstance(config_count, int)
        or isinstance(config_count, bool)
        or config_count < 1
        or config_count != summary_count
    ):
        raise CommandError("preparation target case count commitment mismatch")
    return config_count


def _semantic_preparation_stage_commands(raw_commands: object) -> list[JsonRecord]:
    if not isinstance(raw_commands, Sequence) or isinstance(raw_commands, (str, bytes)):
        raise CommandError("preparation stage commands are malformed")
    commands: list[Mapping[str, Any]] = []
    for raw_command in cast(Sequence[object], raw_commands):
        if not isinstance(raw_command, Mapping):
            raise CommandError("preparation stage command is malformed")
        command = cast(Mapping[str, Any], raw_command)
        argv = command.get("argv")
        if (
            not isinstance(command.get("stage"), str)
            or not isinstance(argv, Sequence)
            or isinstance(argv, (str, bytes))
            or any(not isinstance(value, str) for value in cast(Sequence[object], argv))
        ):
            raise CommandError("preparation stage command is malformed")
        commands.append(command)
    return _semantic_target_100_stage_commands(commands)


def _frozen_preparation_flag_path(
    config: Mapping[str, Any], *, flag: str
) -> Path | None:
    commands = _semantic_preparation_stage_commands(config.get("stage_commands"))
    values: list[str] = []
    for command in commands:
        argv = cast(Sequence[str], command["argv"])
        for index, argument in enumerate(argv):
            if argument == flag:
                if index + 1 >= len(argv):
                    raise CommandError(f"frozen preparation flag lacks value: {flag}")
                values.append(argv[index + 1])
    if not values:
        return None
    unique_values = set(values)
    if len(unique_values) != 1:
        raise CommandError(f"frozen preparation flag is ambiguous: {flag}")
    return Path(unique_values.pop())


def _expected_preparation_input_commitments(
    *,
    preparation_root: Path,
    config: Mapping[str, Any],
) -> tuple[JsonRecord, tuple[Path, ...]]:
    snapshot_value = config.get("snapshot")
    if not isinstance(snapshot_value, str):
        raise CommandError("preparation config lacks snapshot path")
    snapshot = Path(snapshot_value)
    paths: dict[str, tuple[Path, ...]] = {
        "01-public-plan": (
            snapshot / "manifest.json",
            snapshot / "screened-cases.jsonl",
        ),
        "02-free-download": (
            preparation_root / "01-public-plan/free-document-requests.jsonl",
        ),
        "03-gap-bridge": (
            snapshot / "screened-cases.jsonl",
            preparation_root / "01-public-plan/public-packet-selection.jsonl",
            preparation_root / "01-public-plan/public-packet-paid-gaps.jsonl",
            preparation_root / "02-free-download/free-document-downloads.jsonl",
        ),
        "04-core-filter": (preparation_root / "03-gap-bridge/case-relevance.jsonl",),
        "03b-bridge-free-download": (
            preparation_root / "03-gap-bridge/pacer-gap-free-document-requests.jsonl",
        ),
        "03c-merged-downloads": (
            preparation_root / "02-free-download/free-document-downloads.jsonl",
            preparation_root / "03b-bridge-free-download/free-document-downloads.jsonl",
        ),
        "05-budget": (preparation_root / "04-core-filter/core-filter-results.jsonl",),
        "06-clearance-inputs": (
            preparation_root / "03-gap-bridge/case-relevance.jsonl",
            preparation_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        ),
    }
    independent_inputs: list[Path] = []
    courtlistener_fixture = _frozen_preparation_flag_path(
        config, flag="--courtlistener-fixture"
    )
    expected_courtlistener_sha256 = config.get("courtlistener_fixture_sha256")
    if courtlistener_fixture is not None:
        if _path_sha256(courtlistener_fixture) != expected_courtlistener_sha256:
            raise CommandError("frozen CourtListener fixture commitment mismatch")
        paths["03-gap-bridge"] += (courtlistener_fixture,)
        independent_inputs.append(courtlistener_fixture)
    elif expected_courtlistener_sha256 is not None:
        raise CommandError("frozen CourtListener fixture path is missing")
    fixture_documents = _frozen_preparation_flag_path(
        config, flag="--fixture-documents"
    )
    expected_fixture_sha256 = config.get("fixture_documents_sha256")
    if fixture_documents is not None:
        if _path_sha256(fixture_documents) != expected_fixture_sha256:
            raise CommandError("frozen fixture-document commitment mismatch")
        independent_inputs.append(fixture_documents)
    elif expected_fixture_sha256 is not None:
        raise CommandError("frozen fixture-document path is missing")
    for key in ("request_ledger", "raw_html_dir"):
        value = config.get(key)
        if isinstance(value, str):
            independent_inputs.append(Path(value))
    expected = {
        stage: {str(path.resolve()): _path_sha256(path) for path in stage_paths}
        for stage, stage_paths in paths.items()
    }
    if config.get("snapshot_screened_cases_sha256") != _path_sha256(
        snapshot / "screened-cases.jsonl"
    ):
        raise CommandError("preparation screened-case commitment mismatch")
    return expected, tuple(independent_inputs)


def _completed_stage_run_card_exists(path: Path, *, stage: str) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    card = _read_json_object(path)
    return (
        card.get("schema_version") == "legalforecast.acquisition_run_card.v1"
        and card.get("stage") == stage
        and card.get("status") == "completed"
    )


def _validate_materializer_output_paths(
    args: argparse.Namespace,
    *,
    output_root: Path,
    frontier_path: Path,
    input_paths: Sequence[Path],
) -> None:
    _validate_projection_output_scope(output_root, input_paths=input_paths)
    writable_paths = (
        frontier_path,
        _acquisition_path(
            args,
            "run_card_output",
            output_root / "run-cards/materialize-target-cohort-frontier.json",
        ),
        _acquisition_path(
            args,
            "log_output",
            output_root / "logs/materialize-target-cohort-frontier.jsonl",
        ),
    )
    resolved_inputs = tuple(path.resolve() for path in input_paths)
    for index, path in enumerate(writable_paths):
        resolved = path.resolve()
        _reject_hardlinked_writable_replay_scope(
            label="materialize-target-cohort-frontier output",
            path=resolved,
            is_tree=False,
        )
        for source in resolved_inputs:
            if _replay_scopes_overlap(
                left_label="materialize-target-cohort-frontier output",
                left=resolved,
                left_tree=False,
                right_label="immutable preparation input",
                right=source,
                right_tree=source.is_dir(),
            ):
                raise CommandError(
                    "materialize-target-cohort-frontier output overlaps immutable input"
                )
        for other in writable_paths[index + 1 :]:
            if _replay_scopes_overlap(
                left_label="materialize-target-cohort-frontier output",
                left=resolved,
                left_tree=False,
                right_label="materialize-target-cohort-frontier output",
                right=other.resolve(),
                right_tree=False,
            ):
                raise CommandError("materialize-target-cohort-frontier outputs alias")


def _prepare_target_100_clearance_inputs(
    output_root: Path,
    *,
    resume: bool,
) -> None:
    relevance = _read_records(output_root / "03-gap-bridge/case-relevance.jsonl")
    manifest = _read_records(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
    )
    restrictions = restriction_evidence_from_case_relevance(relevance)
    restriction_index = {
        (
            cast(str, row["candidate_id"]),
            cast(str, row["source_document_id"]),
        ): row
        for row in restrictions
    }
    manifest_keys = {
        (
            cast(str, row.get("candidate_id")),
            cast(str, row.get("source_document_id")),
        )
        for row in manifest
    }
    if any(
        not candidate_id or not document_id
        for candidate_id, document_id in manifest_keys
    ):
        raise CommandError("free document manifest contains an invalid document key")
    missing = sorted(manifest_keys - set(restriction_index))
    if missing:
        raise CommandError(
            "free document lacks case-relevance restriction evidence: "
            + ", ".join(f"{candidate}/{document}" for candidate, document in missing)
        )
    exact_restrictions = tuple(restriction_index[key] for key in sorted(manifest_keys))
    manifest_index = {
        (cast(str, row["candidate_id"]), cast(str, row["source_document_id"])): row
        for row in manifest
    }
    review_requests: list[JsonRecord] = []
    for candidate_id, document_id in sorted(manifest_keys):
        manifest_record = manifest_index[(candidate_id, document_id)]
        sha256 = _required_str(manifest_record, "sha256")
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise CommandError(
                "free document manifest has invalid sha256: "
                f"{candidate_id}/{document_id}"
            )
        byte_count = _required_int(manifest_record, "byte_count")
        if byte_count < 0:
            raise CommandError(
                "free document manifest has negative byte_count: "
                f"{candidate_id}/{document_id}"
            )
        free_or_purchased = _required_str(manifest_record, "free_or_purchased")
        if free_or_purchased not in {"free", "purchased"}:
            raise CommandError(
                "free document manifest has invalid free_or_purchased: "
                f"{candidate_id}/{document_id}"
            )
        review_requests.append(
            {
                "schema_version": "legalforecast.disclosure_review_request.v1",
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "sha256": sha256,
                "byte_count": byte_count,
                "free_or_purchased": free_or_purchased,
                "restriction_status": restriction_index[(candidate_id, document_id)][
                    "restriction_status"
                ],
                "restriction_evidence": restriction_index[(candidate_id, document_id)][
                    "restriction_evidence"
                ],
                "required_human_decision": "cleared_or_quarantined",
            }
        )
    clearance_root = output_root / "06-clearance-inputs"
    _ensure_projection_artifact(
        clearance_root / "restriction-evidence.jsonl",
        _projection_jsonl_bytes(exact_restrictions),
        resume=resume,
    )
    _ensure_projection_artifact(
        clearance_root / "disclosure-review-requests.jsonl",
        _projection_jsonl_bytes(review_requests),
        resume=resume,
    )


def _prepare_full_candidate_frontier(
    output_root: Path,
    *,
    budget_plan: MissingCoreBudgetPlan,
    target_case_count: int,
    cost_per_document_usd: str,
    max_missing_core_documents_per_case: int,
    snapshot_manifest_path: Path,
    preparation_config_path: Path,
    frontier_path: Path,
    resume: bool,
    additional_source_commitments: Mapping[str, Path] | None = None,
    write: bool = True,
) -> tuple[Path, int, str]:
    """Freeze every ranked candidate without changing the provisional plan."""

    selection_path = (
        output_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
    )
    case_relevance_path = output_root / "03-gap-bridge/case-relevance.jsonl"
    download_manifest_path = (
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
    )
    filter_path = output_root / "04-core-filter/core-filter-results.jsonl"
    budget_path = output_root / "05-budget/missing-core-budget-plan.json"
    restriction_evidence_path = (
        output_root / "06-clearance-inputs/restriction-evidence.jsonl"
    )
    disclosure_requests_path = (
        output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
    )
    selections = _read_records(selection_path)
    case_relevance_records = _read_records(case_relevance_path)
    download_manifest_records = _read_records(download_manifest_path)
    restriction_records = _read_records(restriction_evidence_path)
    disclosure_request_records = _read_records(disclosure_requests_path)
    filter_records = _read_records(filter_path)
    selection_index: dict[str, JsonRecord] = {}
    for record in selections:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in selection_index:
            raise CommandError(
                f"full candidate frontier has duplicate selection: {candidate_id}"
            )
        selection_index[candidate_id] = record
    ranked_plans = rank_missing_core_document_plans(
        (_core_document_filter_result(record) for record in filter_records),
        dry_run=False,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        cost_per_document_usd=cost_per_document_usd,
    )
    ranked_ids = [plan.candidate_id for plan in ranked_plans]
    if len(ranked_ids) != len(set(ranked_ids)):
        raise CommandError("full candidate frontier contains duplicate candidate IDs")
    selection_ids = set(selection_index)
    ranked_id_set = set(ranked_ids)
    if selection_ids != ranked_id_set:
        missing = sorted(selection_ids - ranked_id_set)
        extra = sorted(ranked_id_set - selection_ids)
        raise CommandError(
            "full candidate frontier does not reconcile resolved selection; "
            f"missing={missing}; extra={extra}"
        )
    relevance_ids = _unique_frontier_candidate_ids(
        case_relevance_records, label="case relevance"
    )
    if relevance_ids != selection_ids:
        raise CommandError(
            "full candidate frontier case relevance does not reconcile resolved "
            f"selection; missing={sorted(selection_ids - relevance_ids)}; "
            f"extra={sorted(relevance_ids - selection_ids)}"
        )
    manifest_keys = _unique_frontier_document_keys(
        download_manifest_records, label="download manifest"
    )
    orphan_manifest_candidates = sorted(
        {candidate_id for candidate_id, _ in manifest_keys} - selection_ids
    )
    if orphan_manifest_candidates:
        raise CommandError(
            "full candidate frontier rejects orphan download-manifest candidates: "
            + ", ".join(orphan_manifest_candidates)
        )
    restriction_keys = _unique_frontier_document_keys(
        restriction_records, label="restriction evidence"
    )
    request_keys = _unique_frontier_document_keys(
        disclosure_request_records, label="disclosure review requests"
    )
    if restriction_keys != manifest_keys or request_keys != manifest_keys:
        raise CommandError(
            "full candidate frontier clearance inputs do not exactly reconcile "
            "the download manifest"
        )
    selected_ids = {plan.candidate_id for plan in budget_plan.case_plans}
    candidates: list[JsonRecord] = []
    for rank, plan in enumerate(ranked_plans, start=1):
        selection = selection_index[plan.candidate_id]
        if plan.exclusion_reasons:
            selection_status = "excluded"
        elif plan.candidate_id in selected_ids:
            selection_status = "selected"
        else:
            selection_status = "eligible_omitted"
        candidates.append(
            {
                "rank": rank,
                "candidate_id": plan.candidate_id,
                "purchase_document_ids": list(plan.purchase_document_ids),
                "missing_core_document_count": plan.missing_core_document_count,
                "estimated_purchase_count": plan.estimated_purchase_count,
                "missing_core_roles": list(plan.missing_core_roles),
                "estimated_cost_usd": plan.estimated_cost_usd,
                "exclusion_reasons": list(plan.exclusion_reasons),
                "court": _optional_str(selection, "court"),
                "nos_macro_category": _optional_str(selection, "nos_macro_category"),
                "related_family_id": _optional_str(selection, "related_family_id"),
                "mdl_family_id": _optional_str(selection, "mdl_family_id"),
                "selection_status": selection_status,
            }
        )
    source_commitments = {
        "snapshot_manifest_sha256": _path_sha256(snapshot_manifest_path),
        "preparation_config_sha256": _path_sha256(preparation_config_path),
        "reconciled_selection_sha256": _path_sha256(selection_path),
        "case_relevance_sha256": _path_sha256(case_relevance_path),
        "download_manifest_sha256": _path_sha256(download_manifest_path),
        "core_filter_results_sha256": _path_sha256(filter_path),
        "provisional_budget_plan_sha256": _path_sha256(budget_path),
        "restriction_evidence_sha256": _path_sha256(restriction_evidence_path),
        "disclosure_review_requests_sha256": _path_sha256(disclosure_requests_path),
    }
    if additional_source_commitments is not None:
        for name, path in sorted(additional_source_commitments.items()):
            if name in source_commitments:
                raise CommandError(
                    f"duplicate full-frontier source commitment name: {name}"
                )
            source_commitments[name] = _path_sha256(path)
    policy: JsonRecord = {
        "target_case_count": target_case_count,
        "candidate_count": len(candidates),
        "selected_candidate_count": len(selected_ids),
        "frontier_truncated": False,
        "source_commitments": source_commitments,
        "clearance_contract": {
            "run_card_schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "clear-disclosures",
            "required_status": "completed",
            "required_dry_run": False,
            "required_execute": True,
            "required_paid_activity_executed": False,
            "download_manifest_sha256": _path_sha256(download_manifest_path),
            "restriction_evidence_sha256": _path_sha256(restriction_evidence_path),
            "required_source_commitments": [
                "download_manifest",
                "restriction_evidence",
                "reviews",
                "review_receipt",
            ],
            "required_output_commitments": ["disclosure_clearance"],
            "required_review_authority_fields": [
                "reviewer_id",
                "controlled_store_uri",
                "authentication_method",
                "authenticated_at",
                "review_artifact_sha256",
            ],
            "orphan_clearance_rows_allowed": False,
        },
        "candidates": candidates,
    }
    artifact: JsonRecord = {
        "schema_version": "legalforecast.target_cohort_candidate_frontier.v1",
        "policy": policy,
        "policy_sha256": _canonical_json_sha256(policy),
    }
    payload = _projection_json_bytes(artifact)
    if write:
        _ensure_projection_artifact(
            frontier_path,
            payload,
            resume=resume,
        )
    return frontier_path, len(candidates), _bytes_sha256(payload)


def _unique_frontier_candidate_ids(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> set[str]:
    candidate_ids: list[str] = [
        _required_str(record, "candidate_id") for record in records
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise CommandError(f"full candidate frontier has duplicate {label} candidate")
    return set(candidate_ids)


def _unique_frontier_document_keys(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> set[tuple[str, str]]:
    keys = [
        (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        for record in records
    ]
    if len(keys) != len(set(keys)):
        raise CommandError(f"full candidate frontier has duplicate {label} document")
    return set(keys)


def _cmd_acquisition_project_target_cohort(args: argparse.Namespace) -> int:
    """Freeze exact post-clearance artifacts from the resolved candidate pool."""

    output_root = _acquisition_output_root(args)
    source_paths = {
        "selection": cast(Path, args.selection),
        "case_relevance": cast(Path, args.case_relevance),
        "download_manifest": cast(Path, args.download_manifest),
        "disclosure_clearance": cast(Path, args.disclosure_clearance),
        "clearance_run_card": cast(Path, args.clearance_run_card),
        "restriction_evidence": cast(Path, args.restriction_evidence),
        "preparation_summary": cast(Path, args.preparation_summary),
        "preparation_config": cast(Path, args.preparation_config),
        "snapshot_manifest": cast(Path, args.snapshot_manifest),
    }
    input_paths = tuple(source_paths.values())
    _validate_projection_output_scope(output_root, input_paths=input_paths)
    try:
        source_bytes = {name: path.read_bytes() for name, path in source_paths.items()}
    except OSError as exc:
        raise CommandError(str(exc)) from exc
    source_sha256 = {
        name: _bytes_sha256(payload) for name, payload in source_bytes.items()
    }
    preparation_summary = _projection_json_object(
        source_bytes["preparation_summary"],
        source=source_paths["preparation_summary"],
    )
    preparation_config = _projection_json_object(
        source_bytes["preparation_config"],
        source=source_paths["preparation_config"],
    )
    snapshot_manifest = _projection_json_object(
        source_bytes["snapshot_manifest"],
        source=source_paths["snapshot_manifest"],
    )
    clearance_run_card = _projection_json_object(
        source_bytes["clearance_run_card"],
        source=source_paths["clearance_run_card"],
    )
    _projection_jsonl_records(
        source_bytes["restriction_evidence"],
        source=source_paths["restriction_evidence"],
    )
    _validate_projection_source_commitments(
        preparation_summary=preparation_summary,
        preparation_config=preparation_config,
        snapshot_manifest=snapshot_manifest,
        clearance_run_card=clearance_run_card,
        source_paths=source_paths,
        source_sha256=source_sha256,
        target_case_count=cast(int, args.target_case_count),
        cost_per_document_usd=cast(str, args.cost_per_document_usd),
        max_projected_budget_usd=cast(str, args.max_projected_budget_usd),
        max_missing_core_documents_per_case=cast(
            int, args.max_missing_core_documents_per_case
        ),
    )
    try:
        projection = project_target_cohort(
            selections=_projection_jsonl_records(
                source_bytes["selection"], source=source_paths["selection"]
            ),
            case_relevance=_projection_jsonl_records(
                source_bytes["case_relevance"],
                source=source_paths["case_relevance"],
            ),
            download_manifest=_projection_jsonl_records(
                source_bytes["download_manifest"],
                source=source_paths["download_manifest"],
            ),
            clearance_records=_projection_jsonl_records(
                source_bytes["disclosure_clearance"],
                source=source_paths["disclosure_clearance"],
            ),
            target_case_count=cast(int, args.target_case_count),
            cost_per_document_usd=cast(str, args.cost_per_document_usd),
            max_projected_budget_usd=cast(str, args.max_projected_budget_usd),
            max_missing_core_documents_per_case=cast(
                int,
                args.max_missing_core_documents_per_case,
            ),
        )
    except TargetCohortProjectionError as exc:
        raise CommandError(str(exc)) from exc

    manifest_records = projection.download_manifest
    free_manifest = tuple(
        record
        for record in manifest_records
        if record.get("free_or_purchased") == "free"
    )
    purchased_manifest = tuple(
        record
        for record in manifest_records
        if record.get("free_or_purchased") == "purchased"
    )
    if len(free_manifest) + len(purchased_manifest) != len(manifest_records):
        raise CommandError(
            "projected manifest contains an invalid free_or_purchased value"
        )

    output_records: dict[Path, bytes] = {
        output_root / "target-cohort-selection.jsonl": _projection_jsonl_bytes(
            projection.selections
        ),
        output_root / "case-relevance.jsonl": _projection_jsonl_bytes(
            projection.case_relevance
        ),
        output_root / "free-document-downloads.jsonl": _projection_jsonl_bytes(
            free_manifest
        ),
        output_root / "purchased-document-downloads.jsonl": (
            _projection_jsonl_bytes(purchased_manifest)
        ),
        output_root / "document-downloads-merged.jsonl": _projection_jsonl_bytes(
            manifest_records
        ),
        output_root / "disclosure-clearance.jsonl": _projection_jsonl_bytes(
            projection.clearance_records
        ),
        output_root / "restriction-evidence.jsonl": _projection_jsonl_bytes(
            projection.restriction_evidence
        ),
        output_root / "core-filter-results.jsonl": _projection_jsonl_bytes(
            tuple(row.to_record() for row in projection.core_filter_results)
        ),
        output_root / "target-cohort-exclusions.jsonl": _projection_jsonl_bytes(
            projection.exclusions
        ),
        output_root / "missing-core-budget-plan.json": _projection_json_bytes(
            projection.budget_plan.to_record()
        ),
    }
    summary = dict(projection.summary)
    summary.update(
        {
            "snapshot_cycle_hash": snapshot_manifest["cycle_hash"],
            "snapshot_batch_digest": snapshot_manifest["batch_digest"],
            "preparation_summary_sha256": source_sha256["preparation_summary"],
            "preparation_config_sha256": source_sha256["preparation_config"],
            "snapshot_manifest_sha256": source_sha256["snapshot_manifest"],
            "clearance_run_card_sha256": source_sha256["clearance_run_card"],
            "input_commitments": {
                str(path.resolve()): source_sha256[name]
                for name, path in source_paths.items()
            },
            "output_commitments": {
                str(path.relative_to(output_root)): "sha256:"
                + hashlib.sha256(payload).hexdigest()
                for path, payload in sorted(
                    output_records.items(),
                    key=lambda item: str(item[0]),
                )
            },
            "next_stage": "generate-recap-fetch-broker-policy",
            "next_stage_blocked_until": (
                "explicit human approval of this post-clearance budget and the "
                "bounded signed RECAP Fetch broker deployment"
            ),
        }
    )
    summary_path = output_root / "target-cohort-projection.json"
    output_records[summary_path] = _projection_json_bytes(summary)

    dry_run = _acquisition_dry_run(args)
    if not dry_run:
        for path, payload in output_records.items():
            _ensure_projection_artifact(
                path,
                payload,
                resume=cast(bool, args.resume),
            )
    _write_acquisition_completion(
        args,
        stage="project-target-cohort",
        input_paths=input_paths,
        output_paths=tuple(output_records),
        record_count=len(projection.selected_candidate_ids),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "selected_case_count": len(projection.selected_candidate_ids),
            "excluded_case_count": len(projection.exclusions),
            "projection_sha256": projection.summary["projection_sha256"],
            "total_estimated_cost_usd": (
                projection.budget_plan.total_estimated_cost_usd
            ),
        },
    )
    return 0


def _cmd_acquisition_extend_target_cohort(args: argparse.Namespace) -> int:
    """Retain target 100 and emit a provider-free exact target-150 extension."""

    output_root = _acquisition_output_root(args)
    base_root = cast(Path, args.base_cohort_root)
    base_paths = {name: base_root / name for name in BASE_PROJECTION_ARTIFACT_NAMES}
    preparation_root = cast(Path, args.preparation_root)
    preparation_summary_path = cast(Path, args.preparation_summary)
    preparation_config_path = cast(Path, args.preparation_config)
    frontier_path = cast(Path, args.full_candidate_frontier)
    frontier_run_card_path = cast(Path, args.frontier_run_card)
    clearance_run_card_path = cast(Path, args.clearance_run_card)
    reviews_path = cast(Path, args.reviews)
    review_receipt_path = cast(Path, args.review_receipt)
    restriction_evidence_path = (
        preparation_root / "06-clearance-inputs/restriction-evidence.jsonl"
    )
    full_paths = {
        "selection.jsonl": preparation_root
        / "03-gap-bridge/public-packet-selection-reconciled.jsonl",
        "case-relevance.jsonl": preparation_root / "03-gap-bridge/case-relevance.jsonl",
        "document-downloads-merged.jsonl": preparation_root
        / "03c-merged-downloads/document-downloads-merged.jsonl",
    }
    cohort_policy_path = cast(Path, args.cohort_policy)
    snapshot_path = cast(Path, args.snapshot_manifest)
    purchase_policy_path = cast(Path, args.purchase_policy)
    purchase_ledger_path = cast(Path, args.purchase_ledger)
    run_card_path = _acquisition_path(
        args,
        "run_card_output",
        output_root / "run-cards/extend-target-cohort.json",
    )
    log_path = _acquisition_path(
        args,
        "log_output",
        output_root / "logs/extend-target-cohort.jsonl",
    )
    input_paths = (
        *base_paths.values(),
        *full_paths.values(),
        restriction_evidence_path,
        preparation_root,
        preparation_summary_path,
        preparation_config_path,
        frontier_path,
        frontier_run_card_path,
        clearance_run_card_path,
        reviews_path,
        review_receipt_path,
        cohort_policy_path,
        snapshot_path,
        purchase_policy_path,
        purchase_ledger_path,
    )
    expected_output_paths = _retained_extension_output_paths(output_root)
    _validate_retained_extension_output_scope(
        output_root,
        input_paths=input_paths,
        additional_output_paths=(
            run_card_path,
            log_path,
            *expected_output_paths,
        ),
    )
    if run_card_path.exists():
        if not cast(bool, args.resume):
            raise CommandError(
                "extend-target-cohort run card already exists and --no-resume was set"
            )
        _validate_retained_extension_completed_resume(
            run_card_path,
            output_root=output_root,
            input_path_prefix=input_paths,
            expected_output_paths=expected_output_paths,
            dry_run=_acquisition_dry_run(args),
            combined_max_projected_budget_usd=cast(
                str, args.combined_max_projected_budget_usd
            ),
        )
        return 0
    try:
        clearance_run_card_bytes = _read_retained_extension_artifact(
            clearance_run_card_path
        )
        clearance_run_card = _projection_json_object(
            clearance_run_card_bytes, source=clearance_run_card_path
        )
        disclosure_clearance_path = _named_committed_path(
            clearance_run_card,
            commitment_group="output_commitments",
            name="disclosure_clearance",
        )
        full_paths["disclosure-clearance.jsonl"] = disclosure_clearance_path
        input_paths = (*input_paths, disclosure_clearance_path)
        _validate_retained_extension_output_scope(
            output_root,
            input_paths=input_paths,
            additional_output_paths=(run_card_path, log_path),
        )
        base_artifacts = {
            name: _read_retained_extension_artifact(path)
            for name, path in base_paths.items()
        }
        full_artifacts = {
            name: _read_retained_extension_artifact(path)
            for name, path in full_paths.items()
        }
        cohort_policy_bytes = _read_retained_extension_artifact(cohort_policy_path)
        snapshot_bytes = _read_retained_extension_artifact(snapshot_path)
        purchase_policy_bytes = _read_retained_extension_artifact(purchase_policy_path)
        lineage_bytes = {
            "preparation_summary": _read_retained_extension_artifact(
                preparation_summary_path
            ),
            "preparation_config": _read_retained_extension_artifact(
                preparation_config_path
            ),
            "frontier": _read_retained_extension_artifact(frontier_path),
            "frontier_run_card": _read_retained_extension_artifact(
                frontier_run_card_path
            ),
            "clearance_run_card": clearance_run_card_bytes,
            "reviews": _read_retained_extension_artifact(reviews_path),
            "review_receipt": _read_retained_extension_artifact(review_receipt_path),
            "restriction_evidence": _read_retained_extension_artifact(
                restriction_evidence_path
            ),
        }
    except OSError as exc:
        raise CommandError(str(exc)) from exc
    cohort_policy = _projection_json_object(
        cohort_policy_bytes, source=cohort_policy_path
    )
    snapshot = _projection_json_object(snapshot_bytes, source=snapshot_path)
    purchase_policy_artifact = _projection_json_object(
        purchase_policy_bytes, source=purchase_policy_path
    )
    cycle_hash = snapshot.get("cycle_hash")
    batch_digest = snapshot.get("batch_digest")
    if not isinstance(cycle_hash, str) or not cycle_hash:
        raise CommandError("snapshot manifest lacks cycle_hash")
    if not isinstance(batch_digest, str) or not batch_digest:
        raise CommandError("snapshot manifest lacks batch_digest")
    authenticated_lineage = _authenticated_extension_lineage(
        preparation_root=preparation_root,
        preparation_summary_path=preparation_summary_path,
        preparation_config_path=preparation_config_path,
        snapshot_path=snapshot_path,
        frontier_path=frontier_path,
        frontier_run_card_path=frontier_run_card_path,
        clearance_run_card_path=clearance_run_card_path,
        reviews_path=reviews_path,
        review_receipt_path=review_receipt_path,
        restriction_evidence_path=restriction_evidence_path,
        disclosure_clearance_path=disclosure_clearance_path,
        full_paths=full_paths,
        full_artifacts=full_artifacts,
        lineage_bytes=lineage_bytes,
        snapshot_bytes=snapshot_bytes,
        preparation_target_case_count=BASE_CASE_COUNT,
    )
    try:
        purchase_policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        _validate_existing_purchase_ledger(purchase_ledger_path, purchase_policy)
        with CaseDevPurchaseJournal(
            purchase_ledger_path, policy=purchase_policy
        ) as purchase_journal:
            obligations = purchase_obligation_snapshot(
                policy=purchase_policy,
                journal=purchase_journal,
                cohort_policy_artifact=cohort_policy,
            )
            extension = extend_target_cohort(
                base_projection_artifacts=base_artifacts,
                full_pool_artifacts=full_artifacts,
                cohort_policy_artifact=cohort_policy,
                snapshot_manifest_sha256=_bytes_sha256(snapshot_bytes),
                snapshot_cycle_hash=cycle_hash,
                snapshot_batch_digest=batch_digest,
                combined_max_projected_budget_usd=cast(
                    str, args.combined_max_projected_budget_usd
                ),
                purchase_obligations=obligations,
                authenticated_lineage=authenticated_lineage,
            )
            return _publish_retained_cohort_extension(
                args=args,
                extension=extension,
                output_root=output_root,
                input_paths=input_paths,
                run_card_path=run_card_path,
                log_path=log_path,
            )
    except (
        RetainedCohortExtensionError,
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
    ) as exc:
        raise CommandError(str(exc)) from exc


def _named_committed_path(
    run_card: Mapping[str, Any], *, commitment_group: str, name: str
) -> Path:
    raw_group = run_card.get(commitment_group)
    if not isinstance(raw_group, Mapping):
        raise CommandError(f"run card lacks {commitment_group}")
    raw_commitment = cast(Mapping[str, object], raw_group).get(name)
    if not isinstance(raw_commitment, Mapping):
        raise CommandError(f"run card lacks {commitment_group}.{name}")
    raw_path = cast(Mapping[str, object], raw_commitment).get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise CommandError(f"run card has invalid {commitment_group}.{name} path")
    return Path(raw_path)


def _authenticated_extension_lineage(
    *,
    preparation_root: Path,
    preparation_summary_path: Path,
    preparation_config_path: Path,
    snapshot_path: Path,
    frontier_path: Path,
    frontier_run_card_path: Path,
    clearance_run_card_path: Path,
    reviews_path: Path,
    review_receipt_path: Path,
    restriction_evidence_path: Path,
    disclosure_clearance_path: Path,
    full_paths: Mapping[str, Path],
    full_artifacts: Mapping[str, bytes],
    lineage_bytes: Mapping[str, bytes],
    snapshot_bytes: bytes,
    preparation_target_case_count: int,
) -> AuthenticatedPoolLineage:
    """Verify the provider-free preparation/frontier/clearance chain."""

    preparation_summary = _projection_json_object(
        lineage_bytes["preparation_summary"], source=preparation_summary_path
    )
    preparation_config = _projection_json_object(
        lineage_bytes["preparation_config"], source=preparation_config_path
    )
    snapshot = _projection_json_object(snapshot_bytes, source=snapshot_path)
    clearance_run_card = _projection_json_object(
        lineage_bytes["clearance_run_card"], source=clearance_run_card_path
    )
    frontier = _projection_json_object(lineage_bytes["frontier"], source=frontier_path)
    frontier_run_card = _projection_json_object(
        lineage_bytes["frontier_run_card"], source=frontier_run_card_path
    )
    preparation_cost_per_document_usd = _required_str(
        preparation_config, "cost_per_document_usd"
    )
    preparation_max_projected_budget_usd = _required_str(
        preparation_config, "max_projected_budget_usd"
    )
    preparation_max_missing_core_documents_per_case = preparation_config.get(
        "max_missing_core_documents_per_case"
    )
    if (
        isinstance(preparation_max_missing_core_documents_per_case, bool)
        or not isinstance(preparation_max_missing_core_documents_per_case, int)
        or preparation_max_missing_core_documents_per_case < 1
    ):
        raise CommandError(
            "preparation config has invalid max_missing_core_documents_per_case"
        )
    source_paths = {
        "selection": full_paths["selection.jsonl"],
        "case_relevance": full_paths["case-relevance.jsonl"],
        "download_manifest": full_paths["document-downloads-merged.jsonl"],
        "disclosure_clearance": disclosure_clearance_path,
        "clearance_run_card": clearance_run_card_path,
        "restriction_evidence": restriction_evidence_path,
        "preparation_summary": preparation_summary_path,
        "preparation_config": preparation_config_path,
        "snapshot_manifest": snapshot_path,
    }
    source_payloads = {
        "selection": full_artifacts["selection.jsonl"],
        "case_relevance": full_artifacts["case-relevance.jsonl"],
        "download_manifest": full_artifacts["document-downloads-merged.jsonl"],
        "disclosure_clearance": full_artifacts["disclosure-clearance.jsonl"],
        "clearance_run_card": lineage_bytes["clearance_run_card"],
        "restriction_evidence": lineage_bytes["restriction_evidence"],
        "preparation_summary": lineage_bytes["preparation_summary"],
        "preparation_config": lineage_bytes["preparation_config"],
        "snapshot_manifest": snapshot_bytes,
    }
    source_sha256 = {
        name: _bytes_sha256(payload) for name, payload in source_payloads.items()
    }
    _validate_projection_source_commitments(
        preparation_summary=preparation_summary,
        preparation_config=preparation_config,
        snapshot_manifest=snapshot,
        clearance_run_card=clearance_run_card,
        source_paths=source_paths,
        source_sha256=source_sha256,
        target_case_count=preparation_target_case_count,
        cost_per_document_usd=preparation_cost_per_document_usd,
        max_projected_budget_usd=preparation_max_projected_budget_usd,
        max_missing_core_documents_per_case=(
            preparation_max_missing_core_documents_per_case
        ),
    )
    if clearance_run_card.get("paid_activity_requested") is not False:
        raise CommandError("clear-disclosures run card requested paid activity")
    clearance_sources = clearance_run_card.get("source_commitments")
    if not isinstance(clearance_sources, Mapping):
        raise CommandError("clear-disclosures run card lacks source commitments")
    for name, path, digest in (
        ("reviews", reviews_path, _bytes_sha256(lineage_bytes["reviews"])),
        (
            "review_receipt",
            review_receipt_path,
            _bytes_sha256(lineage_bytes["review_receipt"]),
        ),
    ):
        _validate_named_path_commitment(
            cast(Mapping[str, object], clearance_sources),
            name=name,
            expected_path=path,
            expected_sha256=digest,
        )
    try:
        review_authority = validate_review_receipt(
            lineage_bytes["reviews"],
            _projection_json_object(
                lineage_bytes["review_receipt"], source=review_receipt_path
            ),
        )
        frontier_rows = _verified_target_cohort_frontier_rows(frontier)
    except (DisclosureClearanceError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    authority = clearance_run_card.get("review_authority")
    expected_authority = {
        "reviewer_id": review_authority.reviewer_id,
        "controlled_store_uri": review_authority.controlled_store_uri,
        "authentication_method": review_authority.authentication_method,
        "authenticated_at": review_authority.authenticated_at,
        "review_artifact_sha256": ("sha256:" + review_authority.review_artifact_sha256),
    }
    if (
        not isinstance(authority, Mapping)
        or dict(cast(Mapping[str, object], authority)) != expected_authority
    ):
        raise CommandError("clear-disclosures review authority differs from receipt")

    policy = cast(Mapping[str, Any], frontier["policy"])
    commitments = cast(Mapping[str, object], policy["source_commitments"])
    expected_frontier_commitments = {
        "snapshot_manifest_sha256": _bytes_sha256(snapshot_bytes),
        "preparation_config_sha256": _bytes_sha256(lineage_bytes["preparation_config"]),
        "preparation_summary_sha256": _bytes_sha256(
            lineage_bytes["preparation_summary"]
        ),
        "reconciled_selection_sha256": _bytes_sha256(full_artifacts["selection.jsonl"]),
        "case_relevance_sha256": _bytes_sha256(full_artifacts["case-relevance.jsonl"]),
        "download_manifest_sha256": _bytes_sha256(
            full_artifacts["document-downloads-merged.jsonl"]
        ),
        "restriction_evidence_sha256": _bytes_sha256(
            lineage_bytes["restriction_evidence"]
        ),
    }
    for name, expected in expected_frontier_commitments.items():
        if commitments.get(name) != expected:
            raise CommandError(f"full candidate frontier {name} mismatch")
    selection_rows = _projection_jsonl_records(
        full_artifacts["selection.jsonl"], source=full_paths["selection.jsonl"]
    )
    selection_ids = {_required_str(row, "candidate_id") for row in selection_rows}
    frontier_id_order = tuple(
        _required_str(row, "candidate_id") for row in frontier_rows
    )
    frontier_ids = set(frontier_id_order)
    if frontier_ids != selection_ids or len(frontier_rows) != len(selection_ids):
        raise CommandError("full candidate frontier differs from resolved selection")
    relevance_rows = _projection_jsonl_records(
        full_artifacts["case-relevance.jsonl"],
        source=full_paths["case-relevance.jsonl"],
    )
    filter_results = filter_core_documents(relevance_rows)
    ranked_ids = tuple(
        plan.candidate_id
        for plan in rank_missing_core_document_plans(
            filter_results,
            dry_run=False,
            max_missing_core_documents_per_case=(
                preparation_max_missing_core_documents_per_case
            ),
            cost_per_document_usd=preparation_cost_per_document_usd,
        )
    )
    if frontier_id_order != ranked_ids:
        raise CommandError(
            "full candidate frontier order does not derive from case relevance"
        )
    raw_frontier_candidates = cast(
        Sequence[object], cast(Mapping[str, Any], frontier["policy"])["candidates"]
    )
    selected_frontier_ids = tuple(
        _required_str(cast(Mapping[str, Any], row), "candidate_id")
        for row in raw_frontier_candidates
        if isinstance(row, Mapping)
        and cast(Mapping[str, object], row).get("selection_status") == "selected"
    )
    canonical_preparation_plan = plan_missing_core_document_budget(
        filter_results,
        dry_run=False,
        max_missing_core_documents_per_case=(
            preparation_max_missing_core_documents_per_case
        ),
        cost_per_document_usd=preparation_cost_per_document_usd,
        max_projected_budget_usd=preparation_max_projected_budget_usd,
        truncate_to_budget=True,
        target_case_count=preparation_target_case_count,
    )
    if selected_frontier_ids != tuple(
        plan.candidate_id for plan in canonical_preparation_plan.case_plans
    ):
        raise CommandError("full candidate frontier selected boundary is not canonical")

    success_run_card_path = _validate_frontier_materialization_run_card(
        frontier_run_card,
        preparation_root=preparation_root,
        preparation_summary_path=preparation_summary_path,
        preparation_config_path=preparation_config_path,
        snapshot_path=snapshot_path,
        frontier_path=frontier_path,
        frontier_sha256=_bytes_sha256(lineage_bytes["frontier"]),
    )
    success_run_card_sha256 = _path_sha256(success_run_card_path)
    if commitments.get("preparation_success_run_card_sha256") != (
        success_run_card_sha256
    ):
        raise CommandError("frontier preparation success run-card mismatch")
    return AuthenticatedPoolLineage(
        preparation_summary_sha256=expected_frontier_commitments[
            "preparation_summary_sha256"
        ],
        preparation_config_sha256=expected_frontier_commitments[
            "preparation_config_sha256"
        ],
        snapshot_manifest_sha256=expected_frontier_commitments[
            "snapshot_manifest_sha256"
        ],
        full_candidate_frontier_sha256=_bytes_sha256(lineage_bytes["frontier"]),
        frontier_policy_sha256=cast(str, frontier["policy_sha256"]),
        frontier_run_card_sha256=_bytes_sha256(lineage_bytes["frontier_run_card"]),
        clearance_run_card_sha256=_bytes_sha256(lineage_bytes["clearance_run_card"]),
        clearance_reviews_sha256=_bytes_sha256(lineage_bytes["reviews"]),
        clearance_review_receipt_sha256=_bytes_sha256(lineage_bytes["review_receipt"]),
        restriction_evidence_sha256=_bytes_sha256(
            lineage_bytes["restriction_evidence"]
        ),
        preparation_cost_per_document_usd=preparation_cost_per_document_usd,
        preparation_max_projected_budget_usd=(preparation_max_projected_budget_usd),
        preparation_max_missing_core_documents_per_case=(
            preparation_max_missing_core_documents_per_case
        ),
    )


def _validate_frontier_materialization_run_card(
    run_card: Mapping[str, Any],
    *,
    preparation_root: Path,
    preparation_summary_path: Path,
    preparation_config_path: Path,
    snapshot_path: Path,
    frontier_path: Path,
    frontier_sha256: str,
) -> Path:
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "materialize-target-cohort-frontier"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or run_card.get("zero_provider_activity_evidence") is not True
        or run_card.get("frontier_sha256") != frontier_sha256
        or run_card.get("output_paths") != [str(frontier_path)]
    ):
        raise CommandError("invalid completed frontier-materialization run card")
    raw_inputs = run_card.get("input_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise CommandError("frontier-materialization run card lacks inputs")
    input_values = tuple(cast(Sequence[object], raw_inputs))
    if not all(isinstance(path, str) for path in input_values):
        raise CommandError("frontier-materialization run card has invalid input path")
    input_paths = tuple(Path(cast(str, path)) for path in input_values)
    required = {
        preparation_root.resolve(),
        preparation_summary_path.resolve(),
        preparation_config_path.resolve(),
        snapshot_path.resolve(),
    }
    resolved = {path.resolve() for path in input_paths}
    remaining = resolved - required
    if not required.issubset(resolved) or len(remaining) != 1 or len(resolved) != 5:
        raise CommandError("frontier-materialization source lineage differs")
    success_run_card_path = next(iter(remaining))
    if success_run_card_path.is_symlink() or not success_run_card_path.is_file():
        raise CommandError("preparation success run card is missing")
    return success_run_card_path


def _publish_retained_cohort_extension(
    *,
    args: argparse.Namespace,
    extension: RetainedCohortExtension,
    output_root: Path,
    input_paths: Sequence[Path],
    run_card_path: Path,
    log_path: Path,
) -> int:
    """Publish or validate extension outputs while the journal lock is held."""

    output_records = {
        **{
            output_root / name: payload
            for name, payload in extension.combined_artifacts.items()
        },
        **{
            output_root / "incremental" / name: payload
            for name, payload in extension.incremental_artifacts.items()
        },
    }
    _validate_retained_extension_output_scope(
        output_root,
        input_paths=input_paths,
        additional_output_paths=(run_card_path, log_path, *output_records),
    )
    metadata_outputs = {run_card_path.resolve(), log_path.resolve()}
    artifact_outputs = {path.resolve() for path in output_records}
    collision = metadata_outputs & artifact_outputs
    if collision:
        raise CommandError(
            "extend-target-cohort metadata output aliases cohort artifact: "
            f"{sorted(str(path) for path in collision)}"
        )
    dry_run = _acquisition_dry_run(args)
    if run_card_path.exists():
        if not cast(bool, args.resume):
            raise CommandError(
                "extend-target-cohort run card already exists and --no-resume was set"
            )
        _validate_retained_extension_successful_resume(
            run_card_path,
            input_paths=input_paths,
            expected_outputs=output_records,
            dry_run=dry_run,
            extension_sha256=cast(str, extension.extension_record["extension_sha256"]),
            cumulative_obligation_usd=cast(
                str, extension.combined_budget["cumulative_obligation_usd"]
            ),
            remaining_headroom_usd=cast(
                str, extension.combined_budget["remaining_headroom_usd"]
            ),
        )
        return 0
    if not dry_run:
        for path, payload in output_records.items():
            _ensure_projection_artifact(
                path,
                payload,
                resume=cast(bool, args.resume),
                stage="extend-target-cohort",
            )
    _write_acquisition_completion(
        args,
        stage="extend-target-cohort",
        input_paths=input_paths,
        output_paths=tuple(output_records),
        record_count=len(extension.combined_candidate_ids),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "base_case_count": len(extension.base_candidate_ids),
            "incremental_case_count": len(extension.incremental_candidate_ids),
            "combined_case_count": len(extension.combined_candidate_ids),
            "extension_sha256": extension.extension_record["extension_sha256"],
            "cumulative_obligation_usd": extension.combined_budget[
                "cumulative_obligation_usd"
            ],
            "remaining_headroom_usd": extension.combined_budget[
                "remaining_headroom_usd"
            ],
            "output_commitments": {
                str(path): _bytes_sha256(payload)
                for path, payload in output_records.items()
            },
        },
    )
    return 0


def _validate_retained_extension_successful_resume(
    run_card_path: Path,
    *,
    input_paths: Sequence[Path],
    expected_outputs: Mapping[Path, bytes],
    dry_run: bool,
    extension_sha256: str,
    cumulative_obligation_usd: str,
    remaining_headroom_usd: str,
) -> None:
    run_card = _read_json_object(run_card_path)
    expected = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "extend-target-cohort",
        "status": "completed",
        "dry_run": dry_run,
        "execute": not dry_run,
        "record_count": 150,
        "input_paths": [str(path) for path in input_paths],
        "output_paths": [str(path) for path in expected_outputs],
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "base_case_count": 100,
        "incremental_case_count": 50,
        "combined_case_count": 150,
        "extension_sha256": extension_sha256,
        "cumulative_obligation_usd": cumulative_obligation_usd,
        "remaining_headroom_usd": remaining_headroom_usd,
    }
    for field, value in expected.items():
        if run_card.get(field) != value:
            raise CommandError(
                f"extend-target-cohort resume run-card mismatch: {field}"
            )
    commitments = run_card.get("output_commitments")
    if not isinstance(commitments, Mapping):
        raise CommandError(
            "extend-target-cohort resume run card lacks output commitments"
        )
    expected_commitments = {
        str(path): _bytes_sha256(payload) for path, payload in expected_outputs.items()
    }
    typed_commitments = cast(Mapping[str, object], commitments)
    if dict(typed_commitments) != expected_commitments:
        raise CommandError("extend-target-cohort resume output commitments differ")
    if not dry_run:
        for path, payload in expected_outputs.items():
            if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
                raise CommandError(
                    f"extend-target-cohort committed output changed: {path}"
                )


def _retained_extension_output_paths(output_root: Path) -> tuple[Path, ...]:
    combined_names = (
        "target-cohort-selection.jsonl",
        "case-relevance.jsonl",
        "document-downloads-merged.jsonl",
        "disclosure-clearance.jsonl",
        "restriction-evidence.jsonl",
        "core-filter-results.jsonl",
        "free-document-downloads.jsonl",
        "purchased-document-downloads.jsonl",
        "target-cohort-exclusions.jsonl",
        "missing-core-budget-plan.json",
        "retained-cohort-budget.json",
        "retained-cohort-extension.json",
    )
    incremental_names = (
        "target-cohort-selection.jsonl",
        "case-relevance.jsonl",
        "document-downloads-merged.jsonl",
        "free-document-downloads.jsonl",
        "purchased-document-downloads.jsonl",
        "disclosure-clearance.jsonl",
        "restriction-evidence.jsonl",
        "core-filter-results.jsonl",
        "target-cohort-exclusions.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-projection.json",
    )
    return (
        *(output_root / name for name in combined_names),
        *(output_root / "incremental" / name for name in incremental_names),
    )


def _validate_retained_extension_completed_resume(
    run_card_path: Path,
    *,
    output_root: Path,
    input_path_prefix: Sequence[Path],
    expected_output_paths: Sequence[Path],
    dry_run: bool,
    combined_max_projected_budget_usd: str,
) -> None:
    """Validate committed outputs before touching mutable acquisition inputs."""

    try:
        combined_cap = Decimal(combined_max_projected_budget_usd)
    except InvalidOperation as exc:
        raise CommandError(
            "combined_max_projected_budget_usd is not valid USD"
        ) from exc
    if (
        not combined_cap.is_finite()
        or combined_cap <= 0
        or combined_cap != combined_cap.quantize(Decimal("0.01"))
    ):
        raise CommandError(
            "combined_max_projected_budget_usd must be positive USD cents"
        )
    normalized_combined_cap = f"{combined_cap:.2f}"
    run_card = _read_json_object(run_card_path)
    expected_fields = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "extend-target-cohort",
        "status": "completed",
        "dry_run": dry_run,
        "execute": not dry_run,
        "record_count": 150,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "base_case_count": 100,
        "incremental_case_count": 50,
        "combined_case_count": 150,
    }
    for field, expected in expected_fields.items():
        if run_card.get(field) != expected:
            raise CommandError(
                f"extend-target-cohort resume run-card mismatch: {field}"
            )
    raw_inputs = run_card.get("input_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise CommandError("extend-target-cohort resume run card lacks input paths")
    committed_inputs = tuple(cast(Sequence[object], raw_inputs))
    expected_prefix = tuple(str(path) for path in input_path_prefix)
    if (
        len(committed_inputs) != len(expected_prefix) + 1
        or committed_inputs[: len(expected_prefix)] != expected_prefix
        or not isinstance(committed_inputs[-1], str)
    ):
        raise CommandError("extend-target-cohort resume input paths differ")
    raw_outputs = run_card.get("output_paths")
    expected_output_strings = tuple(str(path) for path in expected_output_paths)
    if (
        not isinstance(raw_outputs, Sequence)
        or isinstance(raw_outputs, (str, bytes))
        or set(cast(Sequence[object], raw_outputs)) != set(expected_output_strings)
        or len(cast(Sequence[object], raw_outputs)) != len(expected_output_strings)
    ):
        raise CommandError("extend-target-cohort resume output paths differ")
    if dry_run:
        return
    commitments = run_card.get("output_commitments")
    if not isinstance(commitments, Mapping):
        raise CommandError(
            "extend-target-cohort resume run card lacks exact output commitments"
        )
    typed_commitments = cast(Mapping[object, object], commitments)
    if set(typed_commitments) != set(expected_output_strings):
        raise CommandError(
            "extend-target-cohort resume run card lacks exact output commitments"
        )
    output_payloads: dict[Path, bytes] = {}
    for path in expected_output_paths:
        payload = _read_retained_extension_artifact(path)
        if typed_commitments.get(str(path)) != _bytes_sha256(payload):
            raise CommandError(f"extend-target-cohort committed output changed: {path}")
        output_payloads[path] = payload
    extension_path = output_root / "retained-cohort-extension.json"
    budget_path = output_root / "retained-cohort-budget.json"
    expected_set = set(expected_output_paths)
    if extension_path not in expected_set or budget_path not in expected_set:
        raise CommandError("extend-target-cohort resume metadata paths differ")
    extension = _projection_json_object(
        output_payloads[extension_path], source=extension_path
    )
    extension_sha256 = extension.get("extension_sha256")
    unsigned_extension = dict(extension)
    unsigned_extension.pop("extension_sha256", None)
    if (
        not isinstance(extension_sha256, str)
        or extension_sha256 != _canonical_json_sha256(unsigned_extension)
        or run_card.get("extension_sha256") != extension_sha256
    ):
        raise CommandError("extend-target-cohort resume extension hash mismatch")
    budget = _projection_json_object(output_payloads[budget_path], source=budget_path)
    budget_sha256 = budget.get("budget_sha256")
    unsigned_budget = dict(budget)
    unsigned_budget.pop("budget_sha256", None)
    if (
        not isinstance(budget_sha256, str)
        or budget_sha256 != _canonical_json_sha256(unsigned_budget)
        or budget.get("combined_max_projected_budget_usd") != normalized_combined_cap
        or run_card.get("cumulative_obligation_usd")
        != budget.get("cumulative_obligation_usd")
        or run_card.get("remaining_headroom_usd")
        != budget.get("remaining_headroom_usd")
    ):
        raise CommandError("extend-target-cohort resume budget mismatch")
    output_commitments = extension.get("output_commitments")
    if not isinstance(output_commitments, Mapping):
        raise CommandError("retained extension lacks output commitments")
    for name, digest in cast(Mapping[str, object], output_commitments).items():
        path = output_root / name
        if path not in output_payloads or digest != _bytes_sha256(
            output_payloads[path]
        ):
            raise CommandError(f"retained extension output commitment mismatch: {name}")


def _read_retained_extension_artifact(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise CommandError(
            f"extend-target-cohort input must be a regular non-symlink file: {path}"
        )
    return path.read_bytes()


def _validate_existing_purchase_ledger(
    path: Path, policy: CaseDevPurchasePolicy
) -> None:
    """Authenticate the canonical journal read-only before its lock is opened."""

    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise CommandError(
            "extend-target-cohort requires a preexisting nonempty canonical "
            f"purchase ledger: {path}"
        )
    expected = (
        policy.cycle_id,
        policy.cohort_policy_sha256,
        policy.policy_sha256,
        str(policy.canonical_ledger_path),
        f"{policy.hard_cap_usd:.2f}",
        f"{policy.opening_committed_spend_usd:.2f}",
        f"{policy.max_per_case_usd:.2f}",
        f"{policy.per_document_reservation_usd:.2f}",
    )
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as ledger:
            ledger.row_factory = sqlite3.Row
            quick_check = ledger.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or str(quick_check[0]) != "ok":
                raise CommandError("purchase ledger failed SQLite quick_check")
            tables = {
                str(row[0])
                for row in ledger.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required_tables = {
                "purchase_ledger",
                "purchase_operations",
                "replacement_events",
            }
            if not required_tables.issubset(tables):
                raise CommandError("purchase ledger schema is incomplete")
            operation_schema = ledger.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='purchase_operations'"
            ).fetchone()
            if operation_schema is None or "'queued'" not in str(operation_schema[0]):
                raise CommandError("purchase ledger schema is not current")
            row = ledger.execute(
                "SELECT * FROM purchase_ledger WHERE singleton=1"
            ).fetchone()
            if row is None:
                raise CommandError("purchase ledger lacks immutable policy identity")
            actual = tuple(
                str(row[field])
                for field in (
                    "cycle_id",
                    "cohort_policy_sha256",
                    "purchase_policy_sha256",
                    "canonical_ledger_path",
                    "hard_cap_usd",
                    "opening_committed_spend_usd",
                    "max_per_case_usd",
                    "per_document_reservation_usd",
                )
            )
            if actual != expected:
                raise CommandError(
                    "purchase ledger identity conflicts with immutable policy"
                )
    except sqlite3.Error as exc:
        raise CommandError(f"invalid canonical purchase ledger: {exc}") from exc


def _validate_retained_extension_output_scope(
    output_root: Path,
    *,
    input_paths: Sequence[Path],
    additional_output_paths: Sequence[Path] = (),
) -> None:
    outputs = (
        output_root.resolve(),
        *(path.resolve() for path in additional_output_paths),
    )
    for output in outputs[1:]:
        try:
            metadata = output.stat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise CommandError(
                f"cannot inspect extend-target-cohort writable output: {output}: {exc}"
            ) from exc
        if output.is_file() and metadata.st_nlink > 1:
            raise CommandError(
                f"extend-target-cohort writable output has hard-link aliases: {output}"
            )
    for output in outputs:
        for path in input_paths:
            source = path.resolve()
            if (
                output == source
                or output.is_relative_to(source)
                or source.is_relative_to(output)
            ):
                raise CommandError(
                    "extend-target-cohort output overlaps immutable input: "
                    f"{output} vs {source}"
                )
            if output.exists() and path.exists() and output.samefile(path):
                raise CommandError(
                    "extend-target-cohort output hard-links immutable input: "
                    f"{output} vs {source}"
                )
    for index, output in enumerate(outputs):
        for other in outputs[index + 1 :]:
            if (
                output == other
                or output.is_relative_to(other)
                or other.is_relative_to(output)
            ):
                # The default run card and log are expected children of output_root.
                if output == output_root.resolve() or other == output_root.resolve():
                    continue
                raise CommandError(
                    f"extend-target-cohort writable outputs alias: {output} vs {other}"
                )
            if output.exists() and other.exists() and output.samefile(other):
                raise CommandError(
                    "extend-target-cohort writable outputs share an inode: "
                    f"{output} vs {other}"
                )


def _validate_projection_output_scope(
    output_root: Path,
    *,
    input_paths: Sequence[Path],
) -> None:
    output = output_root.resolve()
    for path in input_paths:
        source = path.resolve()
        if (
            output == source
            or output.is_relative_to(source)
            or source.is_relative_to(output)
        ):
            raise CommandError(
                "project-target-cohort output overlaps immutable input: "
                f"{output} vs {source}"
            )


def _validate_projection_source_commitments(
    *,
    preparation_summary: Mapping[str, Any],
    preparation_config: Mapping[str, Any],
    snapshot_manifest: Mapping[str, Any],
    clearance_run_card: Mapping[str, Any],
    source_paths: Mapping[str, Path],
    source_sha256: Mapping[str, str],
    target_case_count: int,
    cost_per_document_usd: str,
    max_projected_budget_usd: str,
    max_missing_core_documents_per_case: int,
) -> None:
    schema_pair = (
        preparation_summary.get("schema_version"),
        preparation_config.get("schema_version"),
    )
    supported_schema_pairs = {
        (
            "legalforecast.target_100_preparation.v1",
            "legalforecast.target_100_config.v1",
        ),
        (
            "legalforecast.target_cohort_preparation.v1",
            "legalforecast.target_cohort_config.v1",
        ),
    }
    if schema_pair not in supported_schema_pairs:
        raise CommandError("unsupported or mismatched preparation schema pair")
    if preparation_summary.get("dry_run") is not False:
        raise CommandError("projection requires an executed preparation summary")
    if preparation_summary.get("paid_activity_executed") is not False:
        raise CommandError("preparation summary unexpectedly claims paid activity")
    if (
        preparation_summary.get("budget_status") != "provisional_pre_clearance"
        or preparation_summary.get("next_stage") != "clear-disclosures"
    ):
        raise CommandError("preparation summary is not at the clearance boundary")
    committed_config_sha256 = preparation_config.get("config_sha256")
    config_payload = dict(preparation_config)
    config_payload.pop("config_sha256", None)
    if committed_config_sha256 != _canonical_json_sha256(config_payload):
        raise CommandError("target-100 preparation config self-hash mismatch")
    if preparation_summary.get("config_sha256") != committed_config_sha256:
        raise CommandError("preparation summary config commitment mismatch")
    if preparation_config.get("driver_execute") is not True:
        raise CommandError("projection requires an executed target-100 config")

    _validate_projection_semantic_config(
        preparation_summary=preparation_summary,
        preparation_config=preparation_config,
        target_case_count=target_case_count,
        cost_per_document_usd=cost_per_document_usd,
        max_projected_budget_usd=max_projected_budget_usd,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
    )

    expected_snapshot_hash = preparation_summary.get("snapshot_manifest_sha256")
    if expected_snapshot_hash != source_sha256["snapshot_manifest"]:
        raise CommandError("preparation summary snapshot commitment mismatch")
    cycle_hash = snapshot_manifest.get("cycle_hash")
    batch_digest = snapshot_manifest.get("batch_digest")
    if not isinstance(cycle_hash, str) or not cycle_hash:
        raise CommandError("snapshot manifest lacks cycle_hash")
    if not isinstance(batch_digest, str) or not batch_digest:
        raise CommandError("snapshot manifest lacks batch_digest")
    if preparation_summary.get("snapshot_batch_digest") != batch_digest:
        raise CommandError("preparation summary batch digest mismatch")
    if (
        preparation_config.get("snapshot_manifest_sha256")
        != source_sha256["snapshot_manifest"]
        or preparation_config.get("snapshot_cycle_hash") != cycle_hash
        or preparation_config.get("snapshot_batch_digest") != batch_digest
    ):
        raise CommandError("target-100 config snapshot commitment mismatch")

    _validate_prepared_stage_commitment(
        preparation_summary,
        stage="03-gap-bridge",
        relative_path="public-packet-selection-reconciled.jsonl",
        actual_sha256=source_sha256["selection"],
    )
    _validate_prepared_stage_commitment(
        preparation_summary,
        stage="03-gap-bridge",
        relative_path="case-relevance.jsonl",
        actual_sha256=source_sha256["case_relevance"],
    )
    _validate_prepared_stage_commitment(
        preparation_summary,
        stage="03c-merged-downloads",
        relative_path="document-downloads-merged.jsonl",
        actual_sha256=source_sha256["download_manifest"],
    )
    _validate_prepared_stage_commitment(
        preparation_summary,
        stage="06-clearance-inputs",
        relative_path="restriction-evidence.jsonl",
        actual_sha256=source_sha256["restriction_evidence"],
    )
    _validate_clearance_run_card_commitments(
        clearance_run_card,
        source_paths=source_paths,
        source_sha256=source_sha256,
    )


def _validate_projection_semantic_config(
    *,
    preparation_summary: Mapping[str, Any],
    preparation_config: Mapping[str, Any],
    target_case_count: int,
    cost_per_document_usd: str,
    max_projected_budget_usd: str,
    max_missing_core_documents_per_case: int,
) -> None:
    if (
        preparation_summary.get("target_case_count") != target_case_count
        or preparation_config.get("target_case_count") != target_case_count
    ):
        raise CommandError("projection target_case_count differs from prepared config")
    exact_values = {
        "max_missing_core_documents_per_case": max_missing_core_documents_per_case,
    }
    for field, actual in exact_values.items():
        if (
            preparation_config.get(field) != actual
            or preparation_summary.get(field) != actual
        ):
            raise CommandError(f"projection {field} differs from prepared config")
    money_values = {
        "cost_per_document_usd": cost_per_document_usd,
        "max_projected_budget_usd": max_projected_budget_usd,
    }
    for field, actual in money_values.items():
        try:
            actual_decimal = Decimal(actual)
            config_decimal = Decimal(str(preparation_config.get(field)))
            summary_decimal = Decimal(str(preparation_summary.get(field)))
        except InvalidOperation as exc:
            raise CommandError(f"projection {field} is invalid") from exc
        if actual_decimal != config_decimal or actual_decimal != summary_decimal:
            raise CommandError(f"projection {field} differs from prepared config")


def _validate_prepared_stage_commitment(
    preparation_summary: Mapping[str, Any],
    *,
    stage: str,
    relative_path: str,
    actual_sha256: str,
) -> None:
    stages = preparation_summary.get("stage_commitments")
    if not isinstance(stages, Mapping):
        raise CommandError("preparation summary lacks stage commitments")
    stage_record = cast(Mapping[str, object], stages).get(stage)
    if not isinstance(stage_record, Mapping):
        raise CommandError(f"preparation summary lacks {stage} commitment")
    if cast(Mapping[str, object], stage_record).get(relative_path) != actual_sha256:
        raise CommandError(f"prepared {stage}/{relative_path} commitment mismatch")


def _validate_clearance_run_card_commitments(
    run_card: Mapping[str, Any],
    *,
    source_paths: Mapping[str, Path],
    source_sha256: Mapping[str, str],
) -> None:
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "clear-disclosures"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("paid_activity_executed") is not False
    ):
        raise CommandError("projection requires an executed clear-disclosures run card")
    source_commitments = run_card.get("source_commitments")
    output_commitments = run_card.get("output_commitments")
    if not isinstance(source_commitments, Mapping) or not isinstance(
        output_commitments, Mapping
    ):
        raise CommandError("clear-disclosures run card lacks commitments")
    for card_name, source_name in (
        ("download_manifest", "download_manifest"),
        ("restriction_evidence", "restriction_evidence"),
    ):
        _validate_named_path_commitment(
            cast(Mapping[str, object], source_commitments),
            name=card_name,
            expected_path=source_paths[source_name],
            expected_sha256=source_sha256[source_name],
        )
    _validate_named_path_commitment(
        cast(Mapping[str, object], output_commitments),
        name="disclosure_clearance",
        expected_path=source_paths["disclosure_clearance"],
        expected_sha256=source_sha256["disclosure_clearance"],
    )
    for name in ("reviews", "review_receipt"):
        commitment = cast(Mapping[str, object], source_commitments).get(name)
        if not isinstance(commitment, Mapping) or not _valid_prefixed_sha256(
            cast(Mapping[str, object], commitment).get("sha256")
        ):
            raise CommandError(f"clear-disclosures run card lacks {name} commitment")
    authority = run_card.get("review_authority")
    if not isinstance(authority, Mapping):
        raise CommandError("clear-disclosures run card lacks review authority")
    authority_record = cast(Mapping[str, object], authority)
    for field in (
        "reviewer_id",
        "controlled_store_uri",
        "authentication_method",
        "authenticated_at",
    ):
        value = authority_record.get(field)
        if not isinstance(value, str) or not value:
            raise CommandError(
                "clear-disclosures run card has invalid review authority"
            )
    if not cast(str, authority_record["controlled_store_uri"]).startswith(
        "private-store://"
    ) or authority_record["authentication_method"] not in {
        "cloudflare_access_oidc",
        "controlled_store_service_identity",
        "github_verified_signature",
    }:
        raise CommandError("clear-disclosures run card has invalid review authority")
    reviews_commitment = cast(
        Mapping[str, object],
        cast(Mapping[str, object], source_commitments)["reviews"],
    )
    if authority_record.get("review_artifact_sha256") != reviews_commitment.get(
        "sha256"
    ):
        raise CommandError("clear-disclosures review authority hash mismatch")


def _validate_named_path_commitment(
    commitments: Mapping[str, object],
    *,
    name: str,
    expected_path: Path,
    expected_sha256: str,
) -> None:
    commitment = commitments.get(name)
    if not isinstance(commitment, Mapping):
        raise CommandError(f"clear-disclosures run card lacks {name} commitment")
    record = cast(Mapping[str, object], commitment)
    if (
        record.get("path") != str(expected_path.resolve())
        or record.get("sha256") != expected_sha256
    ):
        raise CommandError(f"clear-disclosures {name} commitment mismatch")


def _valid_prefixed_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
    )


def _projection_jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    ).encode("utf-8")


def _projection_jsonl_records(payload: bytes, *, source: Path) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CommandError(f"projection input is not UTF-8: {source}") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            loaded = _loads_json(line)
        except ValueError as exc:
            raise CommandError(
                f"projection input has invalid JSON: {source}:{line_number}"
            ) from exc
        if not isinstance(loaded, Mapping):
            raise CommandError(
                f"projection input must contain JSON objects: {source}:{line_number}"
            )
        records.append(dict(cast(Mapping[str, Any], loaded)))
    return records


def _projection_json_object(payload: bytes, *, source: Path) -> JsonRecord:
    try:
        loaded = _loads_json(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CommandError(
            f"projection input has invalid JSON object: {source}"
        ) from exc
    if not isinstance(loaded, Mapping):
        raise CommandError(f"projection input must be a JSON object: {source}")
    return dict(cast(Mapping[str, Any], loaded))


def _bytes_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _projection_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _ensure_projection_artifact(
    path: Path,
    payload: bytes,
    *,
    resume: bool,
    stage: str = "project-target-cohort",
) -> None:
    if path.exists():
        if not resume:
            raise CommandError(f"{stage} output already exists: {path}")
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise CommandError(f"{stage} resume artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _target_100_protected_scopes(
    args: argparse.Namespace,
) -> list[tuple[str, Path, bool]]:
    snapshot = cast(Path, args.snapshot)
    scopes: list[tuple[str, Path, bool]] = [("--snapshot", snapshot, True)]
    for label, path, is_tree in (
        ("snapshot manifest", snapshot / "manifest.json", False),
        ("--raw-html-dir", cast(Path | None, args.raw_html_dir), True),
        ("--fixture-documents", cast(Path | None, args.fixture_documents), False),
        (
            "--courtlistener-fixture",
            cast(Path | None, args.courtlistener_fixture),
            False,
        ),
        ("--request-ledger", cast(Path | None, args.request_ledger), False),
    ):
        if path is not None:
            scopes.append((label, path, is_tree))
    request_ledger = cast(Path | None, args.request_ledger)
    if request_ledger is not None:
        scopes.extend(
            (f"--request-ledger {suffix}", Path(f"{request_ledger}{suffix}"), False)
            for suffix in ("-wal", "-shm", "-journal")
        )
    return scopes


def _target_100_protected_paths(args: argparse.Namespace) -> tuple[Path, ...]:
    return tuple(path for _, path, _ in _target_100_protected_scopes(args))


def _validate_target_100_paths(
    *,
    args: argparse.Namespace,
    profile: _TargetPreparationProfile,
    output_root: Path,
    summary_path: Path,
    snapshot: Path,
    raw_html_dir: Path | None,
    fixture_documents: Path | None,
    courtlistener_fixture: Path | None,
    request_ledger: Path | None,
) -> None:
    """Reject every preparation writable/protected alias before writing."""

    del snapshot, raw_html_dir, fixture_documents, courtlistener_fixture, request_ledger
    writable_scopes: list[tuple[str, Path, bool]] = [
        ("--output-root", output_root, True),
        (f"{profile.label} attempt tree", output_root / "attempts", True),
        ("--summary-output", summary_path, False),
        (
            "--run-card-output",
            _acquisition_path(
                args,
                "run_card_output",
                output_root / f"run-cards/{profile.stage}.json",
            ),
            False,
        ),
        (
            "--log-output",
            _acquisition_path(
                args,
                "log_output",
                output_root / f"logs/{profile.stage}.jsonl",
            ),
            False,
        ),
    ]
    protected_scopes = _target_100_protected_scopes(args)
    controlled_defaults = {
        "summary_output": output_root / profile.summary_filename,
        "run_card_output": output_root / f"run-cards/{profile.stage}.json",
        "log_output": output_root / f"logs/{profile.stage}.jsonl",
    }
    for attribute, default in controlled_defaults.items():
        configured = cast(Path | None, getattr(args, attribute))
        if (
            configured is not None
            and configured.resolve() != default.resolve()
            and configured.resolve().is_relative_to(output_root.resolve())
        ):
            raise CommandError(
                f"--{attribute.replace('_', '-')} custom path must be outside the "
                f"controlled {profile.label} output tree"
            )
    for writable_label, writable_path, writable_tree in writable_scopes:
        writable = writable_path.resolve()
        if not writable_tree:
            _reject_hardlinked_writable_replay_scope(
                label=writable_label,
                path=writable,
                is_tree=False,
            )
        for protected_label, protected_path, protected_tree in protected_scopes:
            protected = protected_path.resolve()
            if _replay_scopes_overlap(
                left_label=writable_label,
                left=writable,
                left_tree=writable_tree,
                right_label=protected_label,
                right=protected,
                right_tree=protected_tree,
            ):
                raise CommandError(
                    f"{profile.label} writable output overlaps protected input: "
                    f"{writable_label} vs {protected_label}: "
                    f"{writable} vs {protected}"
                )

    file_writes = [scope for scope in writable_scopes if not scope[2]]
    for index, (label, path, _) in enumerate(file_writes):
        resolved = path.resolve()
        for other_label, other_path, _ in file_writes[index + 1 :]:
            other = other_path.resolve()
            if _replay_scopes_overlap(
                left_label=label,
                left=resolved,
                left_tree=False,
                right_label=other_label,
                right=other,
                right_tree=False,
            ):
                raise CommandError(
                    f"{profile.label} writable outputs alias: "
                    f"{label} vs {other_label}: {resolved} vs {other}"
                )

    _reject_target_100_tree_hardlink_aliases(
        output_root=output_root,
        protected_scopes=protected_scopes,
    )


def _reject_target_100_tree_hardlink_aliases(
    *,
    output_root: Path,
    protected_scopes: Sequence[tuple[str, Path, bool]],
) -> None:
    if not output_root.exists() or not output_root.is_dir():
        return
    protected_identities: dict[tuple[int, int], str] = {}
    for label, path, is_tree in protected_scopes:
        candidates = path.rglob("*") if is_tree and path.is_dir() else (path,)
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                metadata = candidate.stat()
            except OSError as exc:
                raise CommandError(
                    f"cannot inspect {label} for hard-link aliases: {candidate}: {exc}"
                ) from exc
            protected_identities[(metadata.st_dev, metadata.st_ino)] = label
    for candidate in output_root.rglob("*"):
        if not candidate.is_file():
            continue
        try:
            metadata = candidate.stat()
        except OSError as exc:
            raise CommandError(
                f"cannot inspect --output-root for hard-link aliases: "
                f"{candidate}: {exc}"
            ) from exc
        protected_label = protected_identities.get((metadata.st_dev, metadata.st_ino))
        if protected_label is not None:
            raise CommandError(
                "target-100 output tree contains a hard-link alias to protected "
                f"input {protected_label}: {candidate}"
            )


def _write_target_100_attempt_failure(
    args: argparse.Namespace,
    *,
    profile: _TargetPreparationProfile,
    reason: str,
    protected_paths: Sequence[Path],
    extra: Mapping[str, Any] | None = None,
) -> Path:
    """Write a unique nonpaid failure card without replacing canonical success."""

    output_root = cast(Path, args.output_root).resolve()
    candidates = (
        (output_root / "attempts").resolve(),
        (Path(tempfile.gettempdir()) / "legalforecast-attempts").resolve(),
        (Path.cwd() / ".legalforecast-attempts").resolve(),
        (Path.home() / ".cache/legalforecast/attempts").resolve(),
    )
    protected = tuple(path.resolve() for path in protected_paths)
    output_tree_safe = all(
        output_root != path
        and not output_root.is_relative_to(path)
        and not path.is_relative_to(output_root)
        for path in protected
    )
    attempt_parent = next(
        (
            candidate
            for candidate in candidates
            if (candidate != candidates[0] or output_tree_safe)
            and all(
                candidate != path
                and not candidate.is_relative_to(path)
                and not path.is_relative_to(candidate)
                for path in protected
            )
        ),
        None,
    )
    if attempt_parent is None:
        raise CommandError(
            f"{profile.label} failure could not select a safe attempt-card directory"
        )
    attempt_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid.uuid4().hex}"
    attempt_root = attempt_parent / profile.stage / attempt_id
    run_card_path = attempt_root / "run-card.json"
    record: JsonRecord = {
        "schema_version": profile.attempt_schema,
        "attempt_id": attempt_id,
        "stage": profile.stage,
        "status": "failed",
        "failure_reason": reason,
        "dry_run": _acquisition_dry_run(args),
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "requested_output_root": str(output_root),
        "generated_at": _iso_datetime(datetime.now(UTC)),
    }
    if extra is not None:
        record.update(extra)
    _write_json(run_card_path, record)
    _log_event(profile.stage, "attempt_failed", run_card_path, 0)
    return run_card_path


def _target_100_config_record(
    config: TargetCohortPreparationConfig | Target100PreparationConfig,
    *,
    profile: _TargetPreparationProfile,
    snapshot_manifest: Mapping[str, Any],
    stage_commands: Sequence[Mapping[str, Any]],
    driver_execute: bool,
    wrapper_artifact_paths: Mapping[str, Path],
) -> JsonRecord:
    snapshot_manifest_path = config.snapshot / "manifest.json"
    record: JsonRecord = {
        "schema_version": profile.config_schema,
        "snapshot": str(config.snapshot.resolve()),
        "snapshot_manifest_sha256": _path_sha256(snapshot_manifest_path),
        "snapshot_screened_cases_sha256": _path_sha256(
            config.snapshot / "screened-cases.jsonl"
        ),
        "snapshot_cycle_hash": snapshot_manifest["cycle_hash"],
        "snapshot_batch_digest": snapshot_manifest["batch_digest"],
        "candidate_pool_size": config.candidate_pool_size,
        "target_case_count": config.target_case_count,
        "cost_per_document_usd": config.cost_per_document_usd,
        "max_projected_budget_usd": config.max_projected_budget_usd,
        "max_missing_core_documents_per_case": (
            config.max_missing_core_documents_per_case
        ),
        "use_embedded_entries": config.use_embedded_entries,
        "raw_html_dir": (
            str(config.raw_html_dir.resolve())
            if config.raw_html_dir is not None
            else None
        ),
        "public_download_provider": (
            "courtlistener_live" if config.live_public_download else "fixture"
        ),
        "fixture_documents_sha256": (
            _path_sha256(config.fixture_documents)
            if config.fixture_documents is not None
            else None
        ),
        "paid_gap_authority": "courtlistener_rest",
        "courtlistener_mode": ("live" if config.live_courtlistener else "fixture"),
        "courtlistener_fixture_sha256": (
            _path_sha256(config.courtlistener_fixture)
            if config.courtlistener_fixture is not None
            else None
        ),
        "request_ledger": (
            str(config.request_ledger.resolve())
            if config.request_ledger is not None
            else None
        ),
        "courtlistener_rate_profile": config.courtlistener_rate_profile,
        "request_budget_max_wait_seconds": config.request_budget_max_wait_seconds,
        "driver_execute": driver_execute,
        "wrapper_artifact_paths": {
            name: str(path.resolve())
            for name, path in sorted(wrapper_artifact_paths.items())
        },
        "stage_commands": _semantic_target_100_stage_commands(stage_commands),
    }
    record["config_sha256"] = _canonical_json_sha256(record)
    return record


def _ensure_target_100_config(
    path: Path,
    record: Mapping[str, Any],
    *,
    profile: _TargetPreparationProfile,
    resume: bool,
) -> None:
    if path.exists():
        if not resume:
            raise CommandError(
                f"{profile.label} config already exists; use --resume or a new "
                "output root"
            )
        existing = _read_json_object(path)
        if existing != record:
            raise CommandError(
                f"{profile.label} config mismatch: refusing changed-config resume"
            )
        return
    _atomic_write_json(path, record)


def _path_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _replacement_source_commitments(
    values: Sequence[str], *, fixed: Mapping[str, Path]
) -> dict[str, str]:
    commitments = {name: _path_sha256(path) for name, path in fixed.items()}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if (
            not separator
            or not name
            or name.strip() != name
            or not raw_path
            or name in commitments
        ):
            raise ValueError("--source must be a unique canonical NAME=PATH commitment")
        path = Path(raw_path)
        commitments[name] = _path_sha256(path)
    return commitments


def _replacement_initial_candidate_ids(path: Path) -> tuple[str, ...]:
    loaded = _loads_json(path.read_text(encoding="utf-8"))
    if isinstance(loaded, Mapping):
        mapping = cast(Mapping[object, object], loaded)
        raw_ids = mapping.get("selected_candidate_ids")
        if isinstance(raw_ids, Sequence) and not isinstance(raw_ids, (str, bytes)):
            ids = tuple(cast(Sequence[object], raw_ids))
            if all(isinstance(item, str) for item in ids):
                return cast(tuple[str, ...], ids)
    return tuple(
        _required_str(record, "candidate_id") for record in _read_records(path)
    )


def _replacement_frontier_rows(path: Path) -> tuple[JsonRecord, ...]:
    if path.suffix != ".jsonl":
        loaded = _loads_json(path.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            mapping = cast(Mapping[object, object], loaded)
            if mapping.get("schema_version") == (
                "legalforecast.target_cohort_candidate_frontier.v1"
            ):
                return _verified_target_cohort_frontier_rows(
                    cast(Mapping[str, Any], loaded)
                )
            raw_rows = mapping.get("case_plans")
            if isinstance(raw_rows, Sequence) and not isinstance(
                raw_rows, (str, bytes)
            ):
                return tuple(
                    _mapping(item, "candidate frontier case_plan")
                    for item in cast(Sequence[object], raw_rows)
                )
    return tuple(_read_records(path))


def _verified_target_cohort_frontier_rows(
    artifact: Mapping[str, Any],
) -> tuple[JsonRecord, ...]:
    if set(artifact) != {"schema_version", "policy", "policy_sha256"}:
        raise ValueError("target-cohort frontier artifact fields differ")
    policy = artifact.get("policy")
    if not isinstance(policy, Mapping):
        raise ValueError("target-cohort frontier policy must be an object")
    typed_policy = cast(Mapping[str, Any], policy)
    expected_policy_fields = {
        "target_case_count",
        "candidate_count",
        "selected_candidate_count",
        "frontier_truncated",
        "source_commitments",
        "clearance_contract",
        "candidates",
    }
    if set(typed_policy) != expected_policy_fields:
        raise ValueError("target-cohort frontier policy fields differ")
    if artifact.get("policy_sha256") != _canonical_json_sha256(typed_policy):
        raise ValueError("target-cohort frontier policy hash mismatch")
    if typed_policy.get("frontier_truncated") is not False:
        raise ValueError("target-cohort candidate frontier must be untruncated")
    commitments = typed_policy.get("source_commitments")
    if not isinstance(commitments, Mapping):
        raise ValueError("target-cohort candidate frontier lacks source commitments")
    typed_commitments = cast(Mapping[str, object], commitments)
    required_commitments = {
        "snapshot_manifest_sha256",
        "preparation_config_sha256",
        "reconciled_selection_sha256",
        "case_relevance_sha256",
        "download_manifest_sha256",
        "core_filter_results_sha256",
        "provisional_budget_plan_sha256",
        "restriction_evidence_sha256",
        "disclosure_review_requests_sha256",
    }
    posthoc_commitments = {
        "preparation_summary_sha256",
        "preparation_success_run_card_sha256",
    }
    commitment_keys = frozenset(typed_commitments)
    if commitment_keys not in {
        frozenset(required_commitments),
        frozenset(required_commitments | posthoc_commitments),
    }:
        raise ValueError("target-cohort frontier source commitments differ")
    for digest in typed_commitments.values():
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        ):
            raise ValueError(
                "target-cohort candidate frontier has invalid source commitment"
            )
    clearance_contract = typed_policy.get("clearance_contract")
    if not isinstance(clearance_contract, Mapping):
        raise ValueError("target-cohort frontier lacks clearance contract")
    typed_contract = cast(Mapping[str, Any], clearance_contract)
    expected_contract = {
        "run_card_schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "required_status": "completed",
        "required_dry_run": False,
        "required_execute": True,
        "required_paid_activity_executed": False,
        "download_manifest_sha256": typed_commitments["download_manifest_sha256"],
        "restriction_evidence_sha256": typed_commitments["restriction_evidence_sha256"],
        "required_source_commitments": [
            "download_manifest",
            "restriction_evidence",
            "reviews",
            "review_receipt",
        ],
        "required_output_commitments": ["disclosure_clearance"],
        "required_review_authority_fields": [
            "reviewer_id",
            "controlled_store_uri",
            "authentication_method",
            "authenticated_at",
            "review_artifact_sha256",
        ],
        "orphan_clearance_rows_allowed": False,
    }
    if dict(typed_contract) != expected_contract:
        raise ValueError("target-cohort frontier clearance contract differs")
    raw_candidates = typed_policy.get("candidates")
    if not isinstance(raw_candidates, Sequence) or isinstance(
        raw_candidates, (str, bytes)
    ):
        raise ValueError("target-cohort frontier candidates must be a list")
    candidates: list[JsonRecord] = []
    selected_count = 0
    for expected_rank, raw_candidate in enumerate(
        cast(Sequence[object], raw_candidates), start=1
    ):
        if not isinstance(raw_candidate, Mapping):
            raise ValueError("target-cohort frontier candidate must be an object")
        candidate = dict(cast(Mapping[str, Any], raw_candidate))
        status = candidate.pop("selection_status", None)
        if status not in {
            "selected",
            "eligible_omitted",
            "excluded",
        }:
            raise ValueError("target-cohort frontier selection_status is invalid")
        if status == "selected":
            selected_count += 1
        exclusions = candidate.get("exclusion_reasons")
        if not isinstance(exclusions, Sequence) or isinstance(exclusions, (str, bytes)):
            raise ValueError("target-cohort frontier exclusions must be a list")
        if (status == "excluded") != bool(cast(Sequence[object], exclusions)):
            raise ValueError(
                "target-cohort frontier exclusion status conflicts with reasons"
            )
        if candidate.get("rank") != expected_rank:
            raise ValueError("target-cohort frontier rank sequence is not canonical")
        candidates.append(candidate)
    if typed_policy.get("candidate_count") != len(candidates):
        raise ValueError("target-cohort frontier candidate_count mismatch")
    if typed_policy.get("selected_candidate_count") != selected_count:
        raise ValueError("target-cohort frontier selected count mismatch")
    target_case_count = typed_policy.get("target_case_count")
    if (
        not isinstance(target_case_count, int)
        or isinstance(target_case_count, bool)
        or target_case_count < 1
        or target_case_count != selected_count
    ):
        raise ValueError("target-cohort frontier target count mismatch")
    return tuple(candidates)


def _semantic_target_100_stage_commands(
    stage_commands: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    """Exclude execution-only resume toggles from the frozen semantic config."""

    return [
        {
            "stage": command["stage"],
            "argv": [
                argument
                for argument in cast(Sequence[str], command["argv"])
                if argument not in {"--resume", "--no-resume"}
            ],
        }
        for command in stage_commands
    ]


def _target_100_stage_commitments(output_root: Path) -> JsonRecord:
    commitments: JsonRecord = {}
    for stage_name in (
        "01-public-plan",
        "02-free-download",
        "03-gap-bridge",
        "03b-bridge-free-download",
        "03c-merged-downloads",
        "04-core-filter",
        "05-budget",
        "06-clearance-inputs",
        "documents",
    ):
        stage_root = output_root / stage_name
        commitments[stage_name] = {
            str(path.relative_to(stage_root)): _path_sha256(path)
            for path in sorted(stage_root.rglob("*"))
            if path.is_file()
        }
    return commitments


def _target_100_stage_input_commitments(
    output_root: Path,
    *,
    config: TargetCohortPreparationConfig | Target100PreparationConfig,
) -> JsonRecord:
    """Hash the authoritative inputs consumed at each preparation boundary."""

    paths: dict[str, tuple[Path, ...]] = {
        "01-public-plan": (
            config.snapshot / "manifest.json",
            config.snapshot / "screened-cases.jsonl",
        ),
        "02-free-download": (
            output_root / "01-public-plan/free-document-requests.jsonl",
        ),
        "03-gap-bridge": (
            config.snapshot / "screened-cases.jsonl",
            output_root / "01-public-plan/public-packet-selection.jsonl",
            output_root / "01-public-plan/public-packet-paid-gaps.jsonl",
            output_root / "02-free-download/free-document-downloads.jsonl",
        ),
        "04-core-filter": (output_root / "03-gap-bridge/case-relevance.jsonl",),
        "03b-bridge-free-download": (
            output_root / "03-gap-bridge/pacer-gap-free-document-requests.jsonl",
        ),
        "03c-merged-downloads": (
            output_root / "02-free-download/free-document-downloads.jsonl",
            output_root / "03b-bridge-free-download/free-document-downloads.jsonl",
        ),
        "05-budget": (output_root / "04-core-filter/core-filter-results.jsonl",),
        "06-clearance-inputs": (
            output_root / "03-gap-bridge/case-relevance.jsonl",
            output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        ),
    }
    if config.courtlistener_fixture is not None:
        paths["03-gap-bridge"] += (config.courtlistener_fixture,)
    return {
        stage: {str(path.resolve()): _path_sha256(path) for path in stage_paths}
        for stage, stage_paths in paths.items()
    }


def _missing_core_exclusion_notes(
    case_plan: CaseMissingCorePurchasePlan,
    plan: MissingCoreBudgetPlan,
) -> str:
    if "missing_core_document_cap_exceeded" in case_plan.exclusion_reasons:
        return (
            f"Candidate requires {case_plan.missing_core_document_count} missing "
            "core documents; configured per-case cap is "
            f"{plan.max_missing_core_documents_per_case}."
        )
    return "Candidate failed the core-document acquisition gate."


def _cmd_acquisition_filter_core_documents(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    input_path = cast(Path, args.case_relevance)
    output_path = _acquisition_path(
        args,
        "results_output",
        output_root / "core-filter-results.jsonl",
    )
    results = filter_core_documents(read_case_relevance_jsonl(input_path))
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            output_path,
            [
                {
                    "stage": "filter-core-documents",
                    "dry_run": True,
                    "result_count": len(results),
                }
            ],
        )
    else:
        write_core_document_filter_results(results, output_path)
    _write_acquisition_completion(
        args,
        stage="filter-core-documents",
        input_paths=(input_path,),
        output_paths=(output_path,),
        record_count=len(results),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "purchase_document_count": sum(
                len(result.purchase_document_ids) for result in results
            ),
            "excluded_case_count": sum(result.excluded for result in results),
        },
    )
    return 0


def _cmd_acquisition_discover_case_dev(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    batch_id = cast(str, args.batch_id)
    store_path = _acquisition_path(
        args,
        "cycle_store",
        output_root / "cycle-acquisition.sqlite3",
    )
    candidates_path = _acquisition_path(
        args,
        "candidates_output",
        output_root / "checkpoints" / f"{batch_id}-case-dev-candidates.partial.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / f"{batch_id}-case-dev-summary.partial.json",
    )
    anchor = _iso_date_argument(
        cast(str, args.decision_filed_on_or_after),
        "--decision-filed-on-or-after",
    )
    window_end = _iso_date_argument(
        cast(str, args.decision_filed_on_or_before),
        "--decision-filed-on-or-before",
    )
    if window_end < anchor:
        raise CommandError(
            "--decision-filed-on-or-before cannot precede the eligibility anchor"
        )
    query_terms = tuple(cast(Sequence[str] | None, args.query_terms) or ())
    if not query_terms:
        query_terms = case_dev_smoke_query_terms()
    per_term_limit = cast(int, args.per_term_limit)
    search_page_size = cast(int, args.search_page_size)
    if per_term_limit <= 0:
        raise CommandError("--per-term-limit must be positive")
    if search_page_size <= 0:
        raise CommandError("--search-page-size must be positive")
    fixture_path = cast(Path | None, args.case_dev_fixture)
    live = cast(bool, args.live)
    dry_run = _acquisition_dry_run(args)
    input_paths = () if fixture_path is None else (fixture_path,)
    output_paths = (store_path, candidates_path, summary_path)
    policy = _cycle_acquisition_policy(anchor=anchor)
    batch_config: JsonRecord = {
        "provider": "case.dev",
        "decision_window_start": anchor.isoformat(),
        "decision_window_end": window_end.isoformat(),
        "query_terms": list(query_terms),
        "query_term_order_is_frozen": True,
        "per_term_limit": per_term_limit,
        "search_page_size": search_page_size,
    }

    if dry_run:
        _write_json(
            summary_path,
            {
                "schema_version": "legalforecast.case_dev_discovery_summary.v1",
                "dry_run": True,
                "batch_id": batch_id,
                "query_terms": list(query_terms),
                "checkpoint_only": True,
                "complete": False,
                "saturated": False,
                "anchored_disposition_discovery": False,
                **batch_config,
            },
        )
        _write_acquisition_completion(
            args,
            stage="discover-case-dev",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra={"batch_id": batch_id, "per_term_limit": per_term_limit},
        )
        return 0

    if live and fixture_path is not None:
        raise CommandError("choose --case-dev-fixture or --live, not both")
    try:
        client = _case_dev_client(
            command="discover-case-dev",
            fixture_path=fixture_path,
            live=live,
        )
        with CycleAcquisitionStore(store_path) as store:
            cycle_hash = store.ensure_cycle(policy)
            batch_digest = store.ensure_batch(batch_id, batch_config)
            result = materialize_independent_term_sets(
                source=CaseDevDiscoverySource(client),
                store=store,
                batch_id=batch_id,
                query_terms=query_terms,
                top_k_per_term=per_term_limit,
                page_size=search_page_size,
            )
            checkpoint_records = [
                case_dev_firecrawl_candidate_record(hit)
                for hit in store.candidate_discovery_hits(batch_id)
            ]
    except (
        CaseDevClientError,
        ConfigMismatchError,
        CycleAcquisitionStoreError,
        DiscoverySchedulerError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="discover-case-dev",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc

    _write_jsonl(candidates_path, checkpoint_records)
    summary: JsonRecord = {
        "schema_version": "legalforecast.case_dev_discovery_summary.v1",
        "dry_run": False,
        "batch_id": batch_id,
        "cycle_hash": cycle_hash,
        "batch_digest": batch_digest,
        "query_terms": list(query_terms),
        "candidate_count": len(checkpoint_records),
        "complete": False,
        "saturated": False,
        "provider_pagination_end_observed": result.complete,
        "provider_completeness_status": "unknown",
        "provider_saturation_status": "unproven",
        "anchored_disposition_discovery": False,
        "candidate_count_semantics": (
            "exploratory case/party metadata leads only; not post-anchor "
            "dispositions or clean corpus cases"
        ),
        "terminal_status_by_term": {
            term: status.value
            for term, status in result.terminal_status_by_term.items()
        },
        "checkpoint_only": True,
        "case_dev_request_count": client.request_count,
        **batch_config,
    }
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="discover-case-dev",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(checkpoint_records),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=summary,
    )
    return 0


def _validate_decision_recap_artifact(raw_html: str, source_url: str) -> None:
    """Reject malformed decision-search HTML before it becomes a success."""

    parse_decision_recap_search_html(raw_html, source_url=source_url)


class _BudgetedRecapSearchTransport:
    """Adapt page-at-a-time RECAP discovery to the durable scheduler."""

    def __init__(
        self,
        scheduler: BudgetedFirecrawlScheduler,
        *,
        inherited_pages: Sequence[FirecrawlPageRecord] = (),
        continuation_scheduler: BudgetedFirecrawlScheduler | None = None,
        fallback_source_urls: frozenset[str] = frozenset(),
        parse_search_url: Callable[[str], RecapSearchTarget] = parse_recap_search_url,
    ) -> None:
        self.scheduler = scheduler
        self.continuation_scheduler = continuation_scheduler or scheduler
        self._fallback_source_urls = fallback_source_urls
        self._parse_search_url = parse_search_url
        self._traversed_fallback_urls: set[str] = set()
        self._ordinals: dict[str, int] = {}
        self._pages: dict[str, FirecrawlPageRecord] = {}
        self._inherited_pages = {page.source_url: page for page in inherited_pages}
        if len(self._inherited_pages) != len(inherited_pages):
            raise ValueError("recovery parent contains duplicate successful page URLs")

    @property
    def pages(self) -> tuple[FirecrawlPageRecord, ...]:
        return tuple(
            self._pages[url]
            for url, _ordinal in sorted(
                self._ordinals.items(), key=lambda item: item[1]
            )
        )

    @property
    def unrecovered_fallback_urls(self) -> frozenset[str]:
        return self._fallback_source_urls - self._traversed_fallback_urls

    def fetch(self, *, source_url: str) -> str:
        target = self._parse_search_url(source_url)
        ordinal = self._ordinals.setdefault(source_url, len(self._ordinals))
        inherited = self._inherited_pages.get(source_url)
        if inherited is not None:
            if inherited.target_kind != "search":
                raise RecapSearchError(
                    "recovery parent page is not a RECAP search target"
                )
            self._pages[source_url] = inherited
            return inherited.raw_html
        target_id = (
            "recap-search-"
            + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
        )
        use_fallback = source_url in self._fallback_source_urls
        selected_scheduler = (
            self.scheduler if use_fallback else self.continuation_scheduler
        )
        result = selected_scheduler.run(
            (
                FirecrawlTargetSpec(
                    target_id=target_id,
                    target_kind="search",
                    source_url=source_url,
                    page_number=target.page,
                    ordinal=ordinal,
                ),
            )
        )
        page = next(
            (record for record in result.pages if record.target_id == target_id),
            None,
        )
        if page is None:
            raise RecapSearchError(
                "Firecrawl retries were exhausted before a complete RECAP page "
                f"was acquired: {target.term} page {target.page}"
            )
        if use_fallback:
            self._traversed_fallback_urls.add(source_url)
        self._pages[source_url] = page
        return page.raw_html


def _cmd_acquisition_project_firecrawl_recap_checkpoint(
    args: argparse.Namespace,
) -> int:
    """Materialize verified successful pages without claiming search completion."""

    output_root = _acquisition_output_root(args)
    store_path = cast(Path, args.cycle_store)
    run_ids = tuple(cast(Sequence[str], args.run_ids))
    if len(set(run_ids)) != len(run_ids):
        raise CommandError("--run-id values must be unique")
    run_id = run_ids[0]
    projection_id = run_id
    if len(run_ids) > 1:
        digest = hashlib.sha256("\0".join(run_ids).encode("utf-8")).hexdigest()[:12]
        projection_id = f"{run_id}-union-{digest}"
    pages_path = _acquisition_path(
        args,
        "pages_output",
        output_root / "checkpoints" / f"{projection_id}-partial-recap-pages.jsonl",
    )
    entries_path = _acquisition_path(
        args,
        "entries_output",
        output_root / "checkpoints" / f"{projection_id}-partial-recap-entries.jsonl",
    )
    dockets_path = _acquisition_path(
        args,
        "dockets_output",
        output_root / "checkpoints" / f"{projection_id}-partial-recap-dockets.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / f"{projection_id}-partial-recap-summary.json",
    )
    input_paths = (store_path,)
    output_paths = (pages_path, entries_path, dockets_path, summary_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.recap_partial_checkpoint_summary.v1",
            "dry_run": True,
            "run_id": run_id,
            "run_ids": list(run_ids),
            "store_projection_committed": False,
            "acquired_page_count": 0,
            "raw_hit_count": 0,
            "unique_entry_count": 0,
            "duplicate_entry_count": 0,
            "unique_docket_count": 0,
            "potential_candidate_count": 0,
            "clean_corpus_count": 0,
            "provider_completeness_status": "unproven",
            "provider_saturation_status": "unproven",
            "checkpoint_only": True,
            "complete": False,
            "saturated": False,
            "candidate_count_semantics": (
                "potential dockets only; full eligibility, documents, leakage, "
                "parsing, unitization, and labeling remain required"
            ),
            "firecrawl_metered_activity_requested": False,
            "firecrawl_metered_activity_executed": False,
            "pacer_paid_activity_requested": False,
            "pacer_paid_activity_executed": False,
        }
        _write_jsonl(pages_path, [])
        _write_jsonl(entries_path, [])
        _write_jsonl(dockets_path, [])
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="project-firecrawl-recap-checkpoint",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    try:
        with CycleAcquisitionStore(store_path) as store:
            credit_summaries = {
                source_run_id: dict(store.firecrawl_run_summary(source_run_id))
                for source_run_id in run_ids
            }
            credit_summary = credit_summaries[run_id]
            batch_id_value = credit_summary.get("batch_id")
            if not isinstance(batch_id_value, str) or not batch_id_value:
                raise CycleAcquisitionStoreError(
                    "durable Firecrawl run has no valid batch identity"
                )
            batch_id = batch_id_value
            pages_by_url: dict[str, FirecrawlPageRecord] = {}
            for source_run_id in run_ids:
                source_summary = credit_summaries[source_run_id]
                if source_summary.get("batch_id") != batch_id:
                    raise ConfigMismatchError(
                        "Firecrawl checkpoint union crosses frozen batches"
                    )
                for page in load_successful_firecrawl_pages(
                    store=store, run_id=source_run_id
                ):
                    prior = pages_by_url.get(page.source_url)
                    if (
                        prior is not None
                        and prior.artifact_sha256 != page.artifact_sha256
                    ):
                        raise FirecrawlArtifactError(
                            "conflicting verified bytes for checkpoint search URL "
                            f"{page.source_url}"
                        )
                    pages_by_url.setdefault(page.source_url, page)
            pages = tuple(pages_by_url.values())
            if not pages:
                raise RecapPartialProjectionError(
                    "durable Firecrawl run contains no successful search pages"
                )
            frozen_config = store.batch_config(batch_id)
            frozen_terms_value = frozen_config.get("query_terms")
            if frozen_terms_value is None:
                frozen_terms_value = frozen_config.get("terms")
            if not isinstance(frozen_terms_value, list):
                raise ConfigMismatchError(
                    "frozen batch has no valid ordered search-term plan"
                )
            frozen_term_items = cast(list[object], frozen_terms_value)
            frozen_terms = tuple(
                term for term in frozen_term_items if isinstance(term, str)
            )
            if len(frozen_terms) != len(frozen_term_items):
                raise ConfigMismatchError(
                    "frozen batch has no valid ordered search-term plan"
                )
            frozen_term_ordinals = {
                term: ordinal for ordinal, term in enumerate(frozen_terms)
            }
            frozen_query_plan = frozen_config.get("courtlistener_query_plan_version")
            if frozen_query_plan == DECISION_FIRST_RECAP_QUERY_PLAN_VERSION:
                parse_search_url = parse_decision_recap_search_url
                parse_search_html = parse_decision_recap_search_html
            elif frozen_query_plan in (None, COURTLISTENER_QUERY_PLAN_VERSION):
                parse_search_url = parse_recap_search_url
                parse_search_html = parse_recap_search_html
            else:
                raise ConfigMismatchError(
                    "frozen batch has an unknown CourtListener query plan"
                )
            parsed_targets = {
                page.source_url: parse_search_url(page.source_url) for page in pages
            }
            if any(
                target.term not in frozen_term_ordinals
                for target in parsed_targets.values()
            ):
                raise ConfigMismatchError(
                    "verified page term is absent from the frozen batch plan"
                )
            pages = tuple(
                replace(page, ordinal=ordinal)
                for ordinal, page in enumerate(
                    sorted(
                        pages,
                        key=lambda item: (
                            frozen_term_ordinals[parsed_targets[item.source_url].term],
                            parsed_targets[item.source_url].page,
                            item.source_url,
                        ),
                    )
                )
            )
            projection = project_partial_recap_checkpoint(
                pages,
                parse_search_html=parse_search_html,
            )
            _commit_recap_discovery_pages(
                store=store,
                batch_id=batch_id,
                pages=pages,
                parse_search_html=parse_search_html,
            )
            projected_candidate_ids = {
                candidate.candidate_id for candidate in projection.candidates
            }
            stored_candidate_ids = set(store.candidate_ids(batch_id))
            if stored_candidate_ids != projected_candidate_ids:
                raise CycleAcquisitionStoreError(
                    "partial checkpoint candidates do not reconcile to the "
                    "durable batch projection"
                )
            cycle_hash = store.cycle_hash
            batch_digest = store.batch_digest(batch_id)
            cycle_policy = store.cycle_policy
            frozen_batch_config = store.batch_config(batch_id)
    except (
        CycleAcquisitionStoreError,
        FirecrawlArtifactError,
        KeyError,
        OSError,
        RecapPartialProjectionError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="project-firecrawl-recap-checkpoint",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra={
                "run_id": run_id,
                "run_ids": list(run_ids),
                "checkpoint_only": True,
                "complete": False,
                "saturated": False,
                "firecrawl_metered_activity_requested": False,
                "firecrawl_metered_activity_executed": False,
                "pacer_paid_activity_requested": False,
                "pacer_paid_activity_executed": False,
            },
        )
        raise CommandError(str(exc)) from exc

    page_records = [asdict(page) for page in projection.pages]
    entry_records = [asdict(entry) for entry in projection.entries]
    docket_records = [
        {**asdict(candidate), "eligibility_status": "potential_unverified"}
        for candidate in projection.candidates
    ]
    summary = {
        "schema_version": "legalforecast.recap_partial_checkpoint_summary.v1",
        "dry_run": False,
        "cycle_hash": cycle_hash,
        "batch_digest": batch_digest,
        "eligibility_anchor": cycle_policy.get("eligibility_anchor"),
        "search_window_start": frozen_batch_config.get("search_window_start"),
        "search_window_end": frozen_batch_config.get("search_window_end"),
        "store_projection_committed": True,
        "run_ids": list(run_ids),
        "source_run_credit_summaries": credit_summaries,
        "potential_candidate_count": len(docket_records),
        "clean_corpus_count": 0,
        "candidate_count_semantics": (
            "potential dockets only; full eligibility, documents, leakage, parsing, "
            "unitization, and labeling remain required"
        ),
        "firecrawl_metered_activity_requested": False,
        "firecrawl_metered_activity_executed": False,
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
        **asdict(projection.summary),
        **credit_summary,
    }
    _write_jsonl(pages_path, page_records)
    _write_jsonl(entries_path, entry_records)
    _write_jsonl(dockets_path, docket_records)
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="project-firecrawl-recap-checkpoint",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(docket_records),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=summary,
    )
    return 0


def _cmd_acquisition_init_cycle(args: argparse.Namespace) -> int:
    """Freeze or verify acquisition identity before any provider-backed stage."""

    output_root = _acquisition_output_root(args)
    store_path = _acquisition_path(
        args,
        "cycle_store",
        output_root / "cycle-acquisition.sqlite3",
    )
    identity_path = _acquisition_path(
        args,
        "identity_output",
        output_root / "cycle-identity.json",
    )
    anchor = _iso_date_argument(
        cast(str, args.eligibility_anchor),
        "--eligibility-anchor",
    )
    policy = _cycle_acquisition_policy(anchor=anchor)
    dry_run = _acquisition_dry_run(args)
    output_paths = (store_path, identity_path)
    zero_activity: JsonRecord = {
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "firecrawl_metered_activity_requested": False,
        "firecrawl_metered_activity_executed": False,
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
    }
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.cycle_acquisition_identity.v1",
            "dry_run": True,
            "eligibility_anchor": anchor.isoformat(),
            "cycle_store": str(store_path),
            "policy": policy,
            "initialized_or_verified": False,
            **zero_activity,
        }
        _write_json(identity_path, summary)
        _write_acquisition_completion(
            args,
            stage="init-cycle",
            input_paths=(),
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    try:
        if store_path.exists() and not cast(bool, args.resume):
            raise CycleAcquisitionStoreError(
                "cycle store already exists and --no-resume forbids verification"
            )
        with CycleAcquisitionStore(store_path) as store:
            cycle_hash = store.ensure_cycle(policy)
            _validate_frozen_screening_policy(policy=store.cycle_policy, anchor=anchor)
    except (
        ConfigMismatchError,
        CycleAcquisitionStoreError,
        OSError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="init-cycle",
            input_paths=(),
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=zero_activity,
        )
        raise CommandError(str(exc)) from exc

    identity: JsonRecord = {
        "schema_version": "legalforecast.cycle_acquisition_identity.v1",
        "dry_run": False,
        "eligibility_anchor": anchor.isoformat(),
        "cycle_hash": cycle_hash,
        "cycle_store": str(store_path),
        "policy": policy,
        "initialized_or_verified": True,
        **zero_activity,
    }
    _write_json(identity_path, identity)
    _write_acquisition_completion(
        args,
        stage="init-cycle",
        input_paths=(),
        output_paths=output_paths,
        record_count=1,
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=identity,
    )
    return 0


def _cmd_acquisition_discover_firecrawl_recap(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    decision_first = cast(str, args.recap_search_plan) == "decision-first-r"
    stage_name = (
        "discover-firecrawl-recap-decisions"
        if decision_first
        else "discover-firecrawl-recap"
    )
    default_terms = (
        DECISION_FIRST_RECAP_SEARCH_TERMS if decision_first else FROZEN_MTD_SEARCH_TERMS
    )
    query_plan_version = (
        DECISION_FIRST_RECAP_QUERY_PLAN_VERSION
        if decision_first
        else COURTLISTENER_QUERY_PLAN_VERSION
    )
    query_expression: Callable[[str], str] = (
        decision_recap_query_expression
        if decision_first
        else courtlistener_query_expression
    )
    search_type = "r"
    run_purpose = (
        "anchored-recap-decision-discovery"
        if decision_first
        else "anchored-recap-entry-discovery"
    )
    batch_id = cast(str, args.batch_id)
    run_id = cast(str, args.run_id)
    recovery_of_run_id = cast(str | None, args.recover_terminal_errors_from_run)
    additional_recovery_source_run_ids = tuple(
        cast(Sequence[str], args.recovery_source_run_ids)
    )
    if additional_recovery_source_run_ids and recovery_of_run_id is None:
        raise CommandError(
            "--reuse-verified-pages-from-run requires "
            "--recover-terminal-errors-from-run"
        )
    recovery_source_run_ids = (
        ()
        if recovery_of_run_id is None
        else (recovery_of_run_id, *additional_recovery_source_run_ids)
    )
    if len(set(recovery_source_run_ids)) != len(recovery_source_run_ids):
        raise CommandError("terminal recovery source run IDs must be unique")
    if run_id in recovery_source_run_ids:
        raise CommandError("recovery --run-id must differ from every source run")
    default_output_identity = batch_id
    if recovery_of_run_id is not None:
        try:
            default_output_identity = safe_path_component(run_id, field_name="run_id")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if cast(Path | None, args.run_card_output) is None:
            args.run_card_output = (
                output_root
                / "run-cards"
                / f"{stage_name}-{default_output_identity}.json"
            )
        if cast(Path | None, args.log_output) is None:
            args.log_output = (
                output_root / "logs" / f"{stage_name}-{default_output_identity}.jsonl"
            )
    store_path = _acquisition_path(
        args, "cycle_store", output_root / "cycle-acquisition.sqlite3"
    )
    entries_path = _acquisition_path(
        args,
        "entries_output",
        output_root / "checkpoints" / f"{default_output_identity}-recap-entries.jsonl",
    )
    dockets_path = _acquisition_path(
        args,
        "dockets_output",
        output_root / "checkpoints" / f"{default_output_identity}-recap-dockets.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / f"{default_output_identity}-recap-summary.json",
    )
    configured_raw_search_html_dir = cast(Path | None, args.raw_search_html_dir)
    if configured_raw_search_html_dir is None:
        try:
            raw_run_id = safe_path_component(run_id, field_name="run_id")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        raw_search_html_dir = output_root / "raw-recap-search-html" / raw_run_id
    else:
        raw_search_html_dir = configured_raw_search_html_dir
    anchor = _iso_date_argument(
        cast(str, args.eligibility_anchor),
        "--eligibility-anchor",
    )
    window_start = _iso_date_argument(
        cast(str, args.search_window_start),
        "--search-window-start",
    )
    window_end = _iso_date_argument(
        cast(str, args.search_window_end),
        "--search-window-end",
    )
    if window_start < anchor:
        raise CommandError("--search-window-start cannot precede --eligibility-anchor")
    if window_end < window_start:
        raise CommandError("--search-window-end cannot precede --search-window-start")
    terms = tuple(cast(Sequence[str] | None, args.query_terms) or ())
    if not terms:
        terms = default_terms
    max_pages_per_term = cast(int, args.max_pages_per_term)
    max_attempts = cast(int, args.max_attempts_per_page)
    breaker_threshold = cast(int, args.provider_breaker_threshold)
    credit_cap = cast(int, args.credit_cap)
    if max_pages_per_term <= 0:
        raise CommandError("--max-pages-per-term must be positive")
    if max_attempts <= 0:
        raise CommandError("--max-attempts-per-page must be positive")
    if breaker_threshold <= 0:
        raise CommandError("--provider-breaker-threshold must be positive")
    if credit_cap <= 0 or credit_cap > 45_000:
        raise CommandError("--credit-cap must be between 1 and 45000")
    worst_case_authorized_credits: int | None = None
    frozen_combined_worst_case_credits: int | None = None
    if decision_first:
        if max_pages_per_term > DECISION_FIRST_RECAP_MAX_PAGES_PER_TERM:
            raise CommandError(
                "decision-first Firecrawl plan exceeds the frozen 12000-credit "
                "decision-rescue bound: --max-pages-per-term cannot exceed 100"
            )
        try:
            worst_case_authorized_credits = decision_rescue_worst_case_credits(
                terms=terms,
                max_pages_per_term=max_pages_per_term,
                max_attempts_per_page=max_attempts,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if worst_case_authorized_credits > DECISION_FIRST_RECAP_MAX_AUTHORIZED_CREDITS:
            raise CommandError(
                "decision-first Firecrawl plan exceeds the frozen 12000-credit "
                "decision-rescue bound"
            )
        frozen_combined_worst_case_credits = (
            worst_case_authorized_credits
            + FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS
            + FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS
        )
        if (
            frozen_combined_worst_case_credits
            >= FROZEN_COMBINED_FIRECRAWL_CREDIT_CEILING
        ):
            raise CommandError(
                "combined frozen Firecrawl plans must remain below 45000 credits"
            )
    proxy = cast(str, args.proxy)
    force_browser = cast(bool, args.force_browser)
    if recovery_of_run_id is not None and (proxy != "enhanced" or not force_browser):
        raise CommandError(
            "terminal target recovery requires --proxy enhanced --force-browser"
        )
    fixture_path = cast(Path | None, args.firecrawl_fixture)
    live = cast(bool, args.live_firecrawl)
    if live == (fixture_path is not None):
        raise CommandError(
            "choose exactly one of --firecrawl-fixture or --live-firecrawl"
        )
    dry_run = _acquisition_dry_run(args)
    input_paths = () if fixture_path is None else (fixture_path,)
    output_paths = (
        store_path,
        entries_path,
        dockets_path,
        summary_path,
        raw_search_html_dir,
    )
    policy = _cycle_acquisition_policy(anchor=anchor)
    batch_config: JsonRecord = {
        "provider": (
            "courtlistener-recap-decision-web-via-firecrawl"
            if decision_first
            else "courtlistener-recap-web-via-firecrawl"
        ),
        "eligibility_anchor": anchor.isoformat(),
        "search_window_start": window_start.isoformat(),
        "search_window_end": window_end.isoformat(),
        "query_terms": list(terms),
        "courtlistener_query_plan_version": query_plan_version,
        "courtlistener_query_expressions": [query_expression(term) for term in terms],
        "query_term_order_is_frozen": True,
        "max_pages_per_term": max_pages_per_term,
    }
    if decision_first:
        assert worst_case_authorized_credits is not None
        assert frozen_combined_worst_case_credits is not None
        batch_config.update(
            {
                "worst_case_authorized_credits": worst_case_authorized_credits,
                "courtlistener_search_type": search_type,
                "frozen_existing_firecrawl_commitment_credits": (
                    FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS
                ),
                "frozen_other_rescue_commitment_credits": (
                    FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS
                ),
                "frozen_combined_worst_case_credits": (
                    frozen_combined_worst_case_credits
                ),
                "next_stage": "acquisition enrich-recap-case-dev",
                "downstream_stages": [
                    "acquisition enrich-recap-case-dev",
                    "acquisition acquire-ranked-firecrawl-dockets",
                    "acquisition screen-firecrawl-dockets",
                ],
            }
        )
    run_config: JsonRecord = {
        "purpose": run_purpose,
        "proxy": proxy,
        "force_browser": force_browser,
        "max_attempts_per_page": max_attempts,
        "provider_breaker_threshold": breaker_threshold,
        "query_terms": list(terms),
        "courtlistener_query_plan_version": query_plan_version,
        "courtlistener_query_expressions": [query_expression(term) for term in terms],
        "raw_artifact_root": str(raw_search_html_dir.resolve()),
    }
    if decision_first:
        assert worst_case_authorized_credits is not None
        assert frozen_combined_worst_case_credits is not None
        run_config.update(
            {
                "worst_case_authorized_credits": worst_case_authorized_credits,
                "courtlistener_search_type": search_type,
                "frozen_existing_firecrawl_commitment_credits": (
                    FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS
                ),
                "frozen_other_rescue_commitment_credits": (
                    FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS
                ),
                "frozen_combined_worst_case_credits": (
                    frozen_combined_worst_case_credits
                ),
                "next_stage": "acquisition enrich-recap-case-dev",
                "downstream_stages": [
                    "acquisition enrich-recap-case-dev",
                    "acquisition acquire-ranked-firecrawl-dockets",
                    "acquisition screen-firecrawl-dockets",
                ],
            }
        )
    if recovery_of_run_id is not None:
        run_config["recovery_of_run_id"] = recovery_of_run_id
        run_config["recovery_source_run_ids"] = list(recovery_source_run_ids)
        run_config["recovery_generation"] = 1
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.firecrawl_recap_discovery_summary.v1",
            "dry_run": True,
            "batch_id": batch_id,
            "run_id": run_id,
            "query_terms": list(terms),
            "potential_candidate_count": 0,
            "clean_corpus_count": 0,
            "credit_cap": credit_cap,
            "reserved_credits_per_attempt": 5,
            **batch_config,
            **run_config,
        }
        _write_jsonl(entries_path, [])
        _write_jsonl(dockets_path, [])
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage=stage_name,
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    recovery_parent_credit_summary: Mapping[str, object] = {}
    try:
        fixture_transport = (
            None if live else _firecrawl_fixture_transport(cast(Path, fixture_path))
        )

        def make_source(
            *, source_proxy: str, source_force_browser: bool
        ) -> FirecrawlCourtListenerHTMLSource:
            if live:
                return FirecrawlCourtListenerHTMLSource(
                    FirecrawlConfig.from_env(
                        proxy=cast(Any, source_proxy),
                        force_browser=source_force_browser,
                    )
                )
            return FirecrawlCourtListenerHTMLSource(
                FirecrawlConfig(
                    api_key="offline-fixture",
                    proxy=cast(Any, source_proxy),
                    force_browser=source_force_browser,
                ),
                transport=fixture_transport,
            )

        source = make_source(source_proxy=proxy, source_force_browser=force_browser)
        with CycleAcquisitionStore(store_path) as store:
            cycle_hash = store.ensure_cycle(policy)
            batch_digest = store.ensure_batch(batch_id, batch_config)
            store.ensure_terms(batch_id, terms)
            inherited_pages: tuple[FirecrawlPageRecord, ...] = ()
            recovery_terminal_target_count = 0
            terminal_source_urls: frozenset[str] = frozenset()
            continuation_scheduler: BudgetedFirecrawlScheduler | None = None
            if recovery_of_run_id is not None:
                frozen_parent_run_fields = (
                    "query_terms",
                    "courtlistener_query_plan_version",
                    "courtlistener_query_expressions",
                )
                if decision_first:
                    frozen_parent_run_fields = (
                        *frozen_parent_run_fields,
                        "courtlistener_search_type",
                    )
                pages_by_url: dict[str, FirecrawlPageRecord] = {}
                all_terminal_source_urls: set[str] = set()
                primary_config: Mapping[str, object] | None = None
                primary_terminal_count = 0
                source_summaries: dict[str, Mapping[str, object]] = {}
                for source_run_id in recovery_source_run_ids:
                    source_summary = store.firecrawl_run_summary(source_run_id)
                    source_summaries[source_run_id] = source_summary
                    source_config = store.firecrawl_run_config(source_run_id)
                    if source_summary.get("batch_id") != batch_id:
                        raise ConfigMismatchError(
                            "recovery source does not belong to the frozen batch"
                        )
                    if "recovery_of_run_id" in source_config:
                        raise ConfigMismatchError(
                            "cannot recover a fallback run; recovery is limited to one "
                            "bounded generation"
                        )
                    if source_config.get("purpose") != run_purpose:
                        raise ConfigMismatchError(
                            "recovery source is not the same anchored RECAP "
                            "discovery plan"
                        )
                    if any(
                        source_config.get(field) != run_config.get(field)
                        for field in frozen_parent_run_fields
                    ):
                        raise ConfigMismatchError(
                            "recovery source query plan does not match the frozen batch"
                        )
                    terminal_targets = tuple(
                        target
                        for target in store.firecrawl_targets(source_run_id)
                        if target.status == "terminal_error"
                    )
                    if source_run_id == recovery_of_run_id:
                        primary_config = source_config
                        primary_terminal_count = len(terminal_targets)
                    if any(
                        target.target_kind != "search" for target in terminal_targets
                    ):
                        raise ConfigMismatchError(
                            "recovery source contains a non-search terminal target"
                        )
                    source_attempts = store.firecrawl_attempts(source_run_id)
                    terminal_target_ids = {
                        target.target_id for target in terminal_targets
                    }
                    evidenced_target_ids = {
                        attempt.target_id
                        for attempt in source_attempts
                        if attempt.target_id in terminal_target_ids
                        and attempt.status == "target_error"
                        and attempt.failure_transient is False
                    }
                    if evidenced_target_ids != terminal_target_ids:
                        raise ConfigMismatchError(
                            "recovery source terminal targets lack nontransient "
                            "target-error evidence"
                        )
                    all_terminal_source_urls.update(
                        target.source_url for target in terminal_targets
                    )
                    for page in load_successful_firecrawl_pages(
                        store=store, run_id=source_run_id
                    ):
                        prior = pages_by_url.get(page.source_url)
                        if (
                            prior is not None
                            and prior.artifact_sha256 != page.artifact_sha256
                        ):
                            raise FirecrawlArtifactError(
                                "conflicting verified bytes for recovery search URL "
                                f"{page.source_url}"
                            )
                        pages_by_url.setdefault(page.source_url, page)
                if primary_terminal_count == 0:
                    raise ConfigMismatchError(
                        "recovery parent has no terminal target errors"
                    )
                recovery_parent_credit_summary = {"source_runs": source_summaries}
                inherited_pages = tuple(pages_by_url.values())
                terminal_source_urls = frozenset(
                    all_terminal_source_urls - pages_by_url.keys()
                )
                recovery_terminal_target_count = len(terminal_source_urls)
                assert primary_config is not None
                parent_config = primary_config
                parent_proxy = parent_config.get("proxy")
                parent_force_browser = parent_config.get("force_browser")
                parent_max_attempts = parent_config.get("max_attempts_per_page")
                parent_breaker_threshold = parent_config.get(
                    "provider_breaker_threshold"
                )
                parent_artifact_root = parent_config.get("raw_artifact_root")
                if (
                    parent_proxy not in {"basic", "auto", "enhanced"}
                    or not isinstance(parent_force_browser, bool)
                    or not isinstance(parent_max_attempts, int)
                    or isinstance(parent_max_attempts, bool)
                    or not isinstance(parent_breaker_threshold, int)
                    or isinstance(parent_breaker_threshold, bool)
                    or not isinstance(parent_artifact_root, str)
                ):
                    raise ConfigMismatchError(
                        "recovery parent has an invalid immutable scheduler config"
                    )
                continuation_scheduler = BudgetedFirecrawlScheduler(
                    store=store,
                    source=make_source(
                        source_proxy=cast(str, parent_proxy),
                        source_force_browser=parent_force_browser,
                    ),
                    run_id=recovery_of_run_id,
                    artifact_dir=parent_artifact_root,
                    max_attempts=parent_max_attempts,
                    provider_5xx_circuit_threshold=parent_breaker_threshold,
                    artifact_validator=(
                        _validate_decision_recap_artifact if decision_first else None
                    ),
                    semantic_failure_quarantine_dir=(
                        raw_search_html_dir / "semantic-failure-quarantine"
                        if decision_first
                        else None
                    ),
                )
            run_digest = store.ensure_firecrawl_run(
                run_id,
                batch_id=batch_id,
                config=run_config,
                credit_cap=credit_cap,
                reserved_credits_per_attempt=5,
            )
            scheduler = BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id=run_id,
                artifact_dir=raw_search_html_dir,
                max_attempts=max_attempts,
                provider_5xx_circuit_threshold=breaker_threshold,
                artifact_validator=(
                    _validate_decision_recap_artifact if decision_first else None
                ),
                semantic_failure_quarantine_dir=(
                    raw_search_html_dir / "semantic-failure-quarantine"
                    if decision_first
                    else None
                ),
            )
            transport = _BudgetedRecapSearchTransport(
                scheduler,
                inherited_pages=inherited_pages,
                continuation_scheduler=continuation_scheduler,
                fallback_source_urls=terminal_source_urls,
                parse_search_url=(
                    parse_decision_recap_search_url
                    if decision_first
                    else parse_recap_search_url
                ),
            )
            if decision_first:
                discovery = discover_decision_recap_entries(
                    transport=transport,
                    entry_date_filed_after=window_start,
                    entry_date_filed_before=window_end,
                    terms=terms,
                    max_pages_per_term=max_pages_per_term,
                )
            else:
                discovery = discover_recap_mtd_entries(
                    transport=transport,
                    entry_date_filed_after=window_start,
                    entry_date_filed_before=window_end,
                    terms=terms,
                    max_pages_per_term=max_pages_per_term,
                )
            if transport.unrecovered_fallback_urls:
                raise RecapSearchError(
                    "recovery did not traverse every frozen terminal target"
                )
            if recovery_of_run_id is not None:
                fallback_targets = store.firecrawl_targets(run_id)
                if (
                    frozenset(target.source_url for target in fallback_targets)
                    != terminal_source_urls
                ):
                    raise RecapSearchError(
                        "fallback run acquired a target outside the frozen terminal set"
                    )
            _commit_recap_discovery_pages(
                store=store,
                batch_id=batch_id,
                pages=transport.pages,
                parse_search_html=(
                    parse_decision_recap_search_html
                    if decision_first
                    else parse_recap_search_html
                ),
            )
            credit_summary = dict(store.firecrawl_run_summary(run_id))
    except (
        ConfigMismatchError,
        CycleAcquisitionStoreError,
        FirecrawlArtifactError,
        FirecrawlCircuitOpenError,
        FirecrawlError,
        RecapSearchError,
        ValueError,
    ) as exc:
        failure_credit_summary = _firecrawl_credit_summary_if_available(
            store_path=store_path,
            run_id=run_id,
        )
        metered_executed = _firecrawl_metered_activity_executed(
            live=live,
            summary=failure_credit_summary,
        )
        _write_acquisition_failure(
            args,
            stage=stage_name,
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=live,
            paid_activity_executed=metered_executed,
            extra={
                "firecrawl_metered_activity_requested": live,
                "firecrawl_metered_activity_executed": metered_executed,
                "pacer_paid_activity_requested": False,
                "pacer_paid_activity_executed": False,
                "recovery_of_run_id": recovery_of_run_id,
                "recovery_parent_credit_summary": dict(recovery_parent_credit_summary),
                **failure_credit_summary,
            },
        )
        raise CommandError(str(exc)) from exc

    entry_records = [
        _recap_discovered_entry_record(entry) for entry in discovery.entries
    ]
    docket_records = [
        {
            "candidate_id": f"courtlistener-docket-{docket.docket_id}",
            "docket_id": docket.docket_id,
            "docket_url": docket.docket_url,
            "entry_keys": list(docket.entry_keys),
            "matched_terms": list(docket.matched_terms),
            "eligibility_status": "potential_unverified",
        }
        for docket in discovery.dockets
    ]
    _write_jsonl(entries_path, entry_records)
    _write_jsonl(dockets_path, docket_records)
    summary = {
        "schema_version": "legalforecast.firecrawl_recap_discovery_summary.v1",
        "dry_run": False,
        "batch_id": batch_id,
        "run_id": run_id,
        "cycle_hash": cycle_hash,
        "batch_digest": batch_digest,
        "run_digest": run_digest,
        "recovery_of_run_id": recovery_of_run_id,
        "recovery_terminal_target_count": recovery_terminal_target_count,
        "recovery_parent_credit_summary": dict(recovery_parent_credit_summary),
        "proxy": proxy,
        "force_browser": force_browser,
        "query_terms": list(discovery.terms),
        "pages_fetched": discovery.pages_fetched,
        "raw_hit_count": discovery.raw_hit_count,
        "duplicate_entry_count": discovery.duplicate_entry_count,
        "entry_count": len(entry_records),
        "potential_candidate_count": len(docket_records),
        "clean_corpus_count": 0,
        "complete": discovery.complete,
        "saturated": discovery.complete,
        "candidate_count_semantics": (
            "potential dockets only; full eligibility, documents, leakage, parsing, "
            "unitization, and labeling remain required"
        ),
        "firecrawl_metered_activity_requested": live,
        "firecrawl_metered_activity_executed": (
            _firecrawl_metered_activity_executed(
                live=live,
                summary=credit_summary,
            )
        ),
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
        **credit_summary,
        **batch_config,
    }
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage=stage_name,
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(docket_records),
        dry_run=False,
        paid_activity_requested=live,
        paid_activity_executed=_firecrawl_metered_activity_executed(
            live=live,
            summary=credit_summary,
        ),
        extra=summary,
    )
    return 0


def _commit_recap_discovery_pages(
    *,
    store: CycleAcquisitionStore,
    batch_id: str,
    pages: Sequence[FirecrawlPageRecord],
    parse_search_html: Callable[..., RecapSearchPage] = parse_recap_search_html,
) -> None:
    """Project verified raw RECAP pages into durable discovery progress."""

    for record in pages:
        page = parse_search_html(record.raw_html, source_url=record.source_url)
        hits = tuple(
            DiscoveryHit(
                provider_hit_id=_recap_provider_hit_id(hit),
                candidate_id=f"courtlistener-docket-{hit.docket_id}",
                payload=_recap_search_hit_record(hit),
            )
            for hit in page.hits
        )
        store.commit_search_page(
            batch_id,
            page.target.term,
            None if page.target.page == 1 else str(page.target.page),
            hits,
            next_cursor=(
                str(page.target.page + 1) if page.next_url is not None else None
            ),
            terminal_status=(
                None if page.next_url is not None else TermTerminalStatus.EXHAUSTED
            ),
        )


def _recap_provider_hit_id(hit: RecapSearchHit) -> str:
    # This identifies one provider occurrence, not the underlying docket entry.
    # CourtListener can repeat an entry at identical ordinal positions on later
    # pages; semantic entry reconciliation remains the checkpoint deduper's job.
    identity = "\0".join(
        (
            hit.entry_key,
            hit.document_url,
            hit.provenance.query_term,
            str(hit.provenance.page),
            str(hit.provenance.result_ordinal),
            str(hit.provenance.entry_ordinal),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _recap_search_hit_record(hit: RecapSearchHit) -> JsonRecord:
    return {
        "entry_key": hit.entry_key,
        "docket_id": hit.docket_id,
        "docket_entry_id": hit.docket_entry_id,
        "document_number": hit.document_number,
        "attachment_number": hit.attachment_number,
        "docket_url": hit.docket_url,
        "document_url": hit.document_url,
        "entry_date_filed": hit.entry_date_filed.isoformat(),
        "case_name": hit.case_name,
        "description": hit.description,
        "is_available": hit.is_available,
        "provenance": {
            "query_term": hit.provenance.query_term,
            "search_url": hit.provenance.search_url,
            "page": hit.provenance.page,
            "result_ordinal": hit.provenance.result_ordinal,
            "entry_ordinal": hit.provenance.entry_ordinal,
            "raw_html_sha256": hit.provenance.raw_html_sha256,
        },
    }


def _recap_discovered_entry_record(entry: RecapDiscoveredEntry) -> JsonRecord:
    return {
        "entry_key": entry.entry_key,
        "candidate_id": f"courtlistener-docket-{entry.docket_id}",
        "docket_id": entry.docket_id,
        "docket_entry_id": entry.docket_entry_id,
        "document_number": entry.document_number,
        "attachment_number": entry.attachment_number,
        "docket_url": entry.docket_url,
        "document_url": entry.document_url,
        "entry_date_filed": entry.entry_date_filed.isoformat(),
        "case_name": entry.case_name,
        "description": entry.description,
        "is_available": entry.is_available,
        "matched_terms": list(entry.matched_terms),
        "provenance": [
            {
                "query_term": provenance.query_term,
                "search_url": provenance.search_url,
                "page": provenance.page,
                "result_ordinal": provenance.result_ordinal,
                "entry_ordinal": provenance.entry_ordinal,
                "raw_html_sha256": provenance.raw_html_sha256,
            }
            for provenance in entry.provenances
        ],
        "eligibility_status": "potential_unverified",
    }


def _case_dev_progress_is_retryable(progress: Mapping[str, object]) -> bool:
    if progress.get("outcome") == "transient":
        return True
    payload = progress.get("payload")
    failure_payload = (
        cast(Mapping[str, object], payload) if isinstance(payload, Mapping) else None
    )
    return (
        progress.get("outcome") == "failure"
        and failure_payload is not None
        and failure_payload.get("reason")
        in {
            "case_dev_duplicate_entry_conflict",
            "case_dev_duplicate_entry_semantic_conflict",
        }
    )


_CASE_DEV_MAX_TRANSIENT_DOCKET_ATTEMPTS = 3


def _bound_case_dev_transient_progress(
    progress: JsonRecord,
    *,
    transient_attempts_by_index: Counter[int],
) -> JsonRecord:
    if progress.get("outcome") != "transient":
        return progress
    input_index = cast(int, progress["input_index"])
    transient_attempts_by_index[input_index] += 1
    attempt_count = transient_attempts_by_index[input_index]
    if attempt_count < _CASE_DEV_MAX_TRANSIENT_DOCKET_ATTEMPTS:
        return progress
    return {
        "input_index": input_index,
        "outcome": "failure",
        "payload": {
            "input_index": input_index,
            "reason": "case_dev_server_error_retries_exhausted",
            "detail": (
                "Case.dev docket enrichment exhausted "
                f"{attempt_count} resumable attempts"
            ),
        },
    }


def _enrich_case_dev_progress_record(
    *,
    input_index: int,
    record: Mapping[str, Any],
    fixture_path: Path | None,
    live: bool,
    page_size: int,
    max_pages: int,
    client: CaseDevClient | None = None,
    rate_limiter: CaseDevRateLimiter | None = None,
) -> tuple[JsonRecord, int]:
    active_client = client or _case_dev_client(
        command="enrich-recap-case-dev",
        fixture_path=fixture_path,
        live=live,
        rate_limiter=rate_limiter,
    )
    request_count_before = active_client.request_count
    try:
        one = enrich_recap_discovery_batch(
            client=active_client,
            records=(record,),
            page_size=page_size,
            max_pages=max_pages,
        )
    except CaseDevServerError as exc:
        return (
            {
                "input_index": input_index,
                "outcome": "transient",
                "payload": {
                    "reason": "case_dev_server_error",
                    "detail": str(exc),
                },
            },
            active_client.request_count - request_count_before,
        )
    if one.successes:
        progress: JsonRecord = {
            "input_index": input_index,
            "outcome": "success",
            "payload": one.successes[0].to_record(),
        }
    else:
        failure = one.failures[0].to_record()
        failure["input_index"] = input_index
        progress = {
            "input_index": input_index,
            "outcome": "failure",
            "payload": failure,
        }
    return progress, active_client.request_count - request_count_before


def _cmd_acquisition_enrich_recap_case_dev(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    dockets_path = cast(Path, args.dockets)
    fixture_path = cast(Path | None, args.case_dev_fixture)
    live = cast(bool, args.live_case_dev)
    page_size = cast(int, args.page_size)
    max_pages = cast(int, args.max_pages_per_docket)
    workers = cast(int, args.workers)
    if page_size <= 0 or page_size > 100:
        raise CommandError("--page-size must be between 1 and 100")
    if max_pages <= 0:
        raise CommandError("--max-pages-per-docket must be positive")
    if workers <= 0 or workers > 2:
        raise CommandError("--workers must be between 1 and 2")
    if live == (fixture_path is not None):
        raise CommandError(
            "choose exactly one of --case-dev-fixture or --live-case-dev"
        )
    if fixture_path is not None and workers != 1:
        raise CommandError("--workers must be 1 with --case-dev-fixture")
    ranked_path = _acquisition_path(
        args,
        "ranked_output",
        output_root / "checkpoints" / "case-dev-recap-ranked.jsonl",
    )
    failures_path = _acquisition_path(
        args,
        "failures_output",
        output_root / "checkpoints" / "case-dev-recap-failures.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / "case-dev-recap-summary.json",
    )
    progress_path = output_root / "checkpoints" / "case-dev-recap-progress.jsonl"
    progress_config_path = (
        output_root / "checkpoints" / "case-dev-recap-progress-config.json"
    )
    records = _read_records(dockets_path)
    input_paths = (
        (dockets_path,) if fixture_path is None else (dockets_path, fixture_path)
    )
    output_paths = (
        ranked_path,
        failures_path,
        summary_path,
        progress_path,
        progress_config_path,
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.case_dev_recap_batch_summary.v1",
            "dry_run": True,
            "input_record_count": len(records),
            "page_size": page_size,
            "max_pages_per_docket": max_pages,
            "free_lookup_only": True,
            "pacer_fee_acknowledgment_allowed": False,
        }
        _write_jsonl(ranked_path, [])
        _write_jsonl(failures_path, [])
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="enrich-recap-case-dev",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    progress_config: JsonRecord = {
        "schema_version": "legalforecast.case_dev_recap_progress.v1",
        "dockets_sha256": "sha256:"
        + hashlib.sha256(dockets_path.read_bytes()).hexdigest(),
        "input_record_count": len(records),
        "page_size": page_size,
        "max_pages_per_docket": max_pages,
        "free_lookup_only": True,
    }
    resume = cast(bool, args.resume)
    if progress_config_path.exists():
        if not resume:
            raise CommandError(
                "Case.dev enrichment progress exists; use --resume or remove it"
            )
        if _read_json_object(progress_config_path) != progress_config:
            raise CommandError(
                "Case.dev enrichment progress does not match the current input/config"
            )
    else:
        if progress_path.exists():
            raise CommandError("Case.dev enrichment progress is missing its config")
        _write_json(progress_config_path, progress_config)

    progress_records = _read_records(progress_path) if progress_path.exists() else []
    progress_by_index: dict[int, JsonRecord] = {}
    transient_attempts_by_index: Counter[int] = Counter()
    for progress in progress_records:
        input_index = progress.get("input_index")
        if (
            not isinstance(input_index, int)
            or isinstance(input_index, bool)
            or input_index < 0
            or input_index >= len(records)
            or progress.get("outcome") not in {"success", "failure", "transient"}
            or not isinstance(progress.get("payload"), Mapping)
        ):
            raise CommandError("Case.dev enrichment progress is invalid or duplicated")
        prior = progress_by_index.get(input_index)
        if prior is not None and not _case_dev_progress_is_retryable(prior):
            raise CommandError("Case.dev enrichment progress repeats a terminal index")
        if progress["outcome"] == "transient":
            transient_attempts_by_index[input_index] += 1
        progress_by_index[input_index] = progress

    for input_index, progress in tuple(progress_by_index.items()):
        attempt_count = transient_attempts_by_index[input_index]
        if (
            progress["outcome"] == "transient"
            and attempt_count >= _CASE_DEV_MAX_TRANSIENT_DOCKET_ATTEMPTS
        ):
            exhausted: JsonRecord = {
                "input_index": input_index,
                "outcome": "failure",
                "payload": {
                    "input_index": input_index,
                    "reason": "case_dev_server_error_retries_exhausted",
                    "detail": (
                        "Case.dev docket enrichment exhausted "
                        f"{attempt_count} resumable attempts"
                    ),
                },
            }
            _append_jsonl(progress_path, (exhausted,))
            progress_by_index[input_index] = exhausted

    try:
        pending = [
            (input_index, record)
            for input_index, record in enumerate(records)
            if input_index not in progress_by_index
            or _case_dev_progress_is_retryable(progress_by_index[input_index])
        ]
        request_count = 0
        if workers == 1:
            serial_client = _case_dev_client(
                command="enrich-recap-case-dev",
                fixture_path=fixture_path,
                live=live,
            )
            completed = (
                _enrich_case_dev_progress_record(
                    input_index=input_index,
                    record=record,
                    fixture_path=fixture_path,
                    live=live,
                    page_size=page_size,
                    max_pages=max_pages,
                    client=serial_client,
                )
                for input_index, record in pending
            )
            for progress, one_request_count in completed:
                request_count += one_request_count
                progress = _bound_case_dev_transient_progress(
                    progress,
                    transient_attempts_by_index=transient_attempts_by_index,
                )
                _append_jsonl(progress_path, (progress,))
                progress_by_index[cast(int, progress["input_index"])] = progress
        else:
            live_config = CaseDevConfig.from_env(require_api_key=True)
            aggregate_rate_limiter = (
                None
                if live_config.rate_limit_per_minute is None
                else CaseDevRateLimiter(
                    rate_limit_per_minute=live_config.rate_limit_per_minute
                )
            )
            with ThreadPoolExecutor(max_workers=workers) as executor:
                pending_iter = iter(pending)

                def submit_one() -> Future[tuple[JsonRecord, int]] | None:
                    try:
                        input_index, record = next(pending_iter)
                    except StopIteration:
                        return None
                    return executor.submit(
                        _enrich_case_dev_progress_record,
                        input_index=input_index,
                        record=record,
                        fixture_path=fixture_path,
                        live=live,
                        page_size=page_size,
                        max_pages=max_pages,
                        rate_limiter=aggregate_rate_limiter,
                    )

                futures = {
                    future
                    for _ in range(workers)
                    if (future := submit_one()) is not None
                }
                fatal_error: CaseDevClientError | ValueError | None = None
                while futures:
                    first_completed = next(as_completed(futures))
                    completed = {first_completed}
                    completed.update(future for future in futures if future.done())
                    futures.difference_update(completed)
                    available_slots = 0
                    for future in completed:
                        try:
                            progress, one_request_count = future.result()
                        except (CaseDevClientError, ValueError) as exc:
                            if fatal_error is None:
                                fatal_error = exc
                            continue
                        request_count += one_request_count
                        progress = _bound_case_dev_transient_progress(
                            progress,
                            transient_attempts_by_index=transient_attempts_by_index,
                        )
                        _append_jsonl(progress_path, (progress,))
                        progress_by_index[cast(int, progress["input_index"])] = progress
                        available_slots += 1
                    if fatal_error is None:
                        for _ in range(available_slots):
                            if (replacement := submit_one()) is not None:
                                futures.add(replacement)
                if fatal_error is not None:
                    raise fatal_error
    except (CaseDevClientError, ValueError) as exc:
        _write_acquisition_failure(
            args,
            stage="enrich-recap-case-dev",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc

    if len(progress_by_index) != len(records):
        raise CommandError("Case.dev enrichment progress did not reconcile to inputs")
    transient_count = sum(
        progress["outcome"] == "transient" for progress in progress_by_index.values()
    )
    if transient_count:
        reason = (
            f"Case.dev enrichment retained {transient_count} transient docket(s); "
            "rerun with --resume"
        )
        _write_acquisition_failure(
            args,
            stage="enrich-recap-case-dev",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=reason,
            paid_activity_requested=False,
            extra={"transient_docket_count": transient_count},
        )
        raise CommandError(reason)
    ranked_records = sorted(
        (
            dict(cast(Mapping[str, Any], progress["payload"]))
            for progress in progress_by_index.values()
            if progress["outcome"] == "success"
        ),
        key=lambda record: tuple(cast(Sequence[object], record["ranking_key"])),
    )
    failure_records = [
        dict(cast(Mapping[str, Any], progress_by_index[index]["payload"]))
        for index in sorted(progress_by_index)
        if progress_by_index[index]["outcome"] == "failure"
    ]
    conversion_failure_count = sum(
        record.get("stage") == "discovery_record" for record in failure_records
    )
    enrichment_failure_count = len(failure_records) - conversion_failure_count
    summary = {
        "schema_version": "legalforecast.case_dev_recap_batch_summary.v1",
        "dry_run": False,
        "case_dev_request_count": request_count,
        "page_size": page_size,
        "max_pages_per_docket": max_pages,
        "free_lookup_only": True,
        "pacer_fee_acknowledgment_allowed": False,
        "pacer_spend_usd": "0.00",
        "input_record_count": len(records),
        "converted_docket_count": len(ranked_records) + enrichment_failure_count,
        "enrichment_attempt_count": len(ranked_records) + enrichment_failure_count,
        "successful_docket_count": len(ranked_records),
        "failure_count": len(failure_records),
        "conversion_failure_count": conversion_failure_count,
        "enrichment_failure_count": enrichment_failure_count,
        "failure_reason_counts": dict(
            Counter(cast(str, record["reason"]) for record in failure_records)
        ),
        "structural_priority_tier_counts": dict(
            Counter(
                cast(str, record["structural_priority_reason"])
                for record in ranked_records
            )
        ),
        "decision_signal_priority_tier_counts": dict(
            Counter(
                cast(str, record["decision_signal_priority_reason"])
                for record in ranked_records
            )
        ),
        "actual_free_required_document_count": sum(
            cast(int, record["actual_free_required_document_count"])
            for record in ranked_records
        ),
        "missing_required_document_count": sum(
            cast(int, record["missing_required_document_count"])
            for record in ranked_records
        ),
        "resumed_terminal_record_count": len(progress_records),
        "reconciled": True,
    }
    _write_jsonl(ranked_path, ranked_records)
    _write_jsonl(failures_path, failure_records)
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="enrich-recap-case-dev",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(ranked_records),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=summary,
    )
    return 0


def _cmd_acquisition_acquire_ranked_dockets(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    store_path = cast(Path, args.cycle_store)
    ranked_path = cast(Path, args.ranked)
    fixture_path = cast(Path | None, args.firecrawl_fixture)
    live = cast(bool, args.live_firecrawl)
    workers = cast(int, args.workers)
    if live == (fixture_path is not None):
        raise CommandError(
            "choose exactly one of --firecrawl-fixture or --live-firecrawl"
        )
    if not _acquisition_dry_run(args) and fixture_path is not None and workers != 1:
        raise CommandError("--firecrawl-fixture execution requires --workers 1")
    credit_cap = cast(int, args.credit_cap)
    if credit_cap <= 0 or credit_cap > 45_000:
        raise CommandError("--credit-cap must be between 1 and 45000")
    anchor = _iso_date_argument(
        cast(str, args.decision_filed_on_or_after),
        "--decision-filed-on-or-after",
    )
    raw_dir = _acquisition_path(args, "raw_html_dir", output_root / "raw-docket-html")
    successes_path = _acquisition_path(
        args, "successes_output", output_root / "firecrawl-docket-successes.jsonl"
    )
    exclusions_path = _acquisition_path(
        args, "exclusions_output", output_root / "firecrawl-docket-exclusions.jsonl"
    )
    summary_path = _acquisition_path(
        args, "summary_output", output_root / "firecrawl-docket-summary.json"
    )
    records = _read_records(ranked_path)
    input_paths = (
        (ranked_path,) if fixture_path is None else (ranked_path, fixture_path)
    )
    output_paths = (successes_path, exclusions_path, summary_path)
    metadata_by_docket: dict[str, Mapping[str, object]] = {}
    for record in records:
        identity = record.get("identity")
        metadata = record.get("screening_metadata")
        if not isinstance(identity, Mapping) or not isinstance(metadata, Mapping):
            raise CommandError(
                "ranked records require identity and screening_metadata objects"
            )
        docket_id = cast(Mapping[str, object], identity).get("courtlistener_docket_id")
        if not isinstance(docket_id, str):
            raise CommandError("ranked record has invalid CourtListener docket ID")
        metadata_by_docket[docket_id] = cast(Mapping[str, object], metadata)
    proxy = cast(FirecrawlProxy, args.proxy)
    force_browser = cast(bool, args.force_browser)
    if _acquisition_dry_run(args):
        summary: JsonRecord = {
            "dry_run": True,
            "selected_batch_id": cast(str, args.selected_batch_id),
            "input_record_count": len(records),
            "max_candidates": cast(int, args.max_candidates),
            "workers": workers,
            "credit_cap": credit_cap,
            "firecrawl_proxy": proxy,
            "firecrawl_force_browser": force_browser,
            "reserved_credits": 0,
            "success_count": 0,
            "exclusion_count": 0,
            "pagination_complete_before_screening": False,
        }
        _write_jsonl(successes_path, [])
        _write_jsonl(exclusions_path, [])
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="acquire-ranked-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=live,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0
    config = (
        FirecrawlConfig.from_env(proxy=proxy, force_browser=force_browser)
        if live
        else FirecrawlConfig(
            api_key="offline-fixture",
            proxy=proxy,
            force_browser=force_browser,
        )
    )
    source = FirecrawlCourtListenerHTMLSource(
        config,
        **(
            {"transport": _firecrawl_fixture_transport(cast(Path, fixture_path))}
            if not live
            else {}
        ),
    )
    with CycleAcquisitionStore(store_path) as store:
        materialize_selected_slice_batch(
            store=store,
            parent_batch_id=cast(str, args.parent_batch_id),
            selected_batch_id=cast(str, args.selected_batch_id),
            records=records,
            limit=cast(int, args.max_candidates),
        )
        run_config: JsonRecord = {
            "purpose": "ranked-complete-docket-acquisition",
            "decision_anchor": anchor.isoformat(),
            "max_pages_per_docket": cast(int, args.max_pages_per_docket),
            "raw_artifact_root": str(raw_dir.resolve()),
            "firecrawl_proxy": config.proxy,
            "firecrawl_force_browser": config.force_browser,
            "firecrawl_max_credits_per_scrape": config.max_credits_per_scrape,
        }
        run_id = cast(str, args.run_id)
        try:
            existing_run_config = store.firecrawl_run_config(run_id)
        except KeyError:
            run_config["workers"] = workers
        else:
            if "workers" in existing_run_config:
                run_config["workers"] = workers
            elif workers != 1:
                raise CommandError(
                    "legacy Firecrawl runs require --workers 1; use a new --run-id "
                    "to freeze concurrent acquisition"
                )
        store.ensure_firecrawl_run(
            run_id,
            batch_id=cast(str, args.selected_batch_id),
            config=run_config,
            credit_cap=credit_cap,
            reserved_credits_per_attempt=config.max_credits_per_scrape,
        )
        result = acquire_ranked_dockets(
            records=records,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id=run_id,
                artifact_dir=raw_dir / "pages",
                max_attempts=cast(int, args.max_attempts_per_page),
                provider_5xx_circuit_threshold=cast(
                    int, args.provider_breaker_threshold
                ),
                max_workers=workers,
            ),
            limit=cast(int, args.max_candidates),
            max_pages_per_docket=cast(int, args.max_pages_per_docket),
            decision_anchor=anchor,
        )
    successes: list[JsonRecord] = []
    retrieved_at = datetime.now(UTC).isoformat()
    for bundle in result.bundles:
        raw_html = render_complete_docket_html(bundle)
        raw_bytes = raw_html.encode()
        raw_path = raw_dir / f"{bundle.docket_id}.html"
        _write_text(raw_path, raw_html)
        metadata = dict(metadata_by_docket[bundle.docket_id])
        candidate_id = f"courtlistener-docket-{bundle.docket_id}"
        metadata["case_id"] = candidate_id
        successes.append(
            {
                "case_id": candidate_id,
                "candidate_id": candidate_id,
                "source_url": bundle.base_url,
                "docket_id": bundle.docket_id,
                "raw_html_path": str(raw_path.resolve()),
                "case_metadata": metadata,
                "raw_html_sha256": "sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
                "raw_html_bytes": len(raw_bytes),
                "retrieved_at": retrieved_at,
                "pagination_complete_for_anchor_window": True,
                "page_count": len(bundle.pages),
            }
        )
    exclusions = [failure.as_record() for failure in result.failures]
    _write_jsonl(successes_path, successes)
    _write_jsonl(exclusions_path, exclusions)
    summary = {
        **dict(result.credit_summary),
        "selected_batch_id": cast(str, args.selected_batch_id),
        "success_count": len(successes),
        "exclusion_count": len(exclusions),
        "failure_reason_counts": dict(
            Counter(failure.failure_reason for failure in result.failures)
        ),
        "pagination_complete_before_screening": True,
        "workers": workers,
    }
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="acquire-ranked-firecrawl-dockets",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(successes),
        dry_run=False,
        paid_activity_requested=live,
        paid_activity_executed=_firecrawl_metered_activity_executed(
            live=live, summary=summary
        ),
        extra=summary,
    )
    return 0


def _cmd_acquisition_funnel_report(args: argparse.Namespace) -> int:
    try:
        discovery_path = cast(Path | None, args.discovery_summary)
        screening_path = cast(Path | None, args.firecrawl_screening_summary)
        recap_path = cast(Path | None, args.recap_discovery_summary)
        if screening_path is not None and recap_path is None:
            raise FunnelReportError(
                "--recap-discovery-summary is required with "
                "--firecrawl-screening-summary"
            )
        if discovery_path is not None and recap_path is not None:
            raise FunnelReportError(
                "--recap-discovery-summary is only valid with "
                "--firecrawl-screening-summary"
            )
        report = build_acquisition_funnel_report(
            discovery_summary=(
                _read_json_object(discovery_path)
                if discovery_path is not None
                else None
            ),
            firecrawl_screening_summary=(
                _read_json_object(screening_path)
                if screening_path is not None
                else None
            ),
            recap_discovery_summary=(
                _read_json_object(recap_path) if recap_path is not None else None
            ),
            exclusions=_read_records(cast(Path, args.exclusions)),
            public_download_summary=_read_json_object(
                cast(Path, args.public_download_summary)
            ),
        )
    except (FunnelReportError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    _write_json(cast(Path, args.output), report)
    return 0


def _cmd_acquisition_generate_labeling_policy(args: argparse.Namespace) -> int:
    """Publish the canonical pre-labeling policy without invoking freeze state."""

    artifact = generate_labeling_policy(
        cycle_id=cast(str, args.cycle_id),
        judge_registry_path=cast(Path, args.judge_registry),
        published_at=_parse_datetime(cast(str, args.published_at)),
        threshold_source=cast(str, args.threshold_source),
    )
    output = cast(Path, args.output)
    write_labeling_policy(output, artifact)
    verify_labeling_policy(
        _read_json_object(output),
        judge_registry_path=cast(Path, args.judge_registry),
        expected_cycle_id=cast(str, args.cycle_id),
    )
    print(json.dumps(artifact, sort_keys=True))
    return 0


def _cmd_acquisition_verify_labeling_policy(args: argparse.Namespace) -> int:
    policy_sha256 = verify_labeling_policy(
        _read_json_object(cast(Path, args.artifact)),
        judge_registry_path=cast(Path, args.judge_registry),
        expected_cycle_id=cast(str | None, args.cycle_id),
    )
    print(policy_sha256)
    return 0


# ---------------------------------------------------------------------------
# batch-002 RECAP API acquisition driver handlers.
# ---------------------------------------------------------------------------


def _batch_002_client(
    args: argparse.Namespace,
    *,
    require_token: bool,
) -> tuple[CourtListenerClient, CourtListenerRequestBudget | None]:
    """Build a live or fixture CourtListener client for a batch-002 phase."""

    live = cast(bool, args.live)
    fixture = cast(Path | None, args.courtlistener_fixture)
    config = CourtListenerConfig.from_env()
    max_retries = cast(int, getattr(args, "max_retries", 2))
    retry_backoff = cast(float, getattr(args, "retry_backoff_seconds", 0.0))
    if require_token and config.api_token is None:
        raise CommandError(f"{COURTLISTENER_API_TOKEN_ENV} is required")
    if live:
        ledger_path = cast(Path | None, args.request_ledger)
        if ledger_path is None:
            raise CommandError("--request-ledger is required with --live")
        max_wait = cast(float, args.request_budget_max_wait_seconds)
        if max_wait < 0:
            raise CommandError("--request-budget-max-wait-seconds cannot be negative")
        profile = cast(str, args.courtlistener_rate_profile)
        if profile == "temporary-doubled" and config.api_token is None:
            raise CommandError(
                "--courtlistener-rate-profile temporary-doubled requires "
                f"{COURTLISTENER_API_TOKEN_ENV}"
            )
        try:
            budget = CourtListenerRequestBudget(
                ledger_path,
                limits=_COURTLISTENER_RATE_PROFILES[profile],
                max_wait_seconds=max_wait,
            )
        except (CourtListenerRequestBudgetError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        return (
            CourtListenerClient(
                config=config,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff,
                before_request=budget.before_request,
            ),
            budget,
        )
    assert fixture is not None
    return (
        CourtListenerClient(
            config=config,
            transport=CourtListenerFixtureTransport.from_jsonl(fixture),
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff,
        ),
        None,
    )


def _courtlistener_bridge_client(
    args: argparse.Namespace,
    *,
    fixture_path: Path | None,
    live: bool,
) -> tuple[CourtListenerClient, CourtListenerRequestBudget | None]:
    """Build the paid-gap metadata client with durable live request accounting."""

    config = CourtListenerConfig.from_env()
    if fixture_path is not None:
        return (
            CourtListenerClient(
                config=config,
                transport=CourtListenerFixtureTransport.from_jsonl(fixture_path),
            ),
            None,
        )
    if not live:
        raise CommandError(
            "CourtListener bridge requires --courtlistener-fixture or "
            "--live-courtlistener"
        )
    if config.api_token is None:
        raise CommandError(
            f"{COURTLISTENER_API_TOKEN_ENV} is required with --live-courtlistener"
        )
    ledger_path = cast(Path | None, args.request_ledger)
    if ledger_path is None:
        raise CommandError("--request-ledger is required with --live-courtlistener")
    max_wait = cast(float, args.request_budget_max_wait_seconds)
    if max_wait < 0:
        raise CommandError("--request-budget-max-wait-seconds cannot be negative")
    profile = cast(str, args.courtlistener_rate_profile)
    try:
        budget = CourtListenerRequestBudget(
            ledger_path,
            limits=_COURTLISTENER_RATE_PROFILES[profile],
            max_wait_seconds=max_wait,
        )
    except (CourtListenerRequestBudgetError, OSError) as exc:
        raise CommandError(str(exc)) from exc
    return (
        CourtListenerClient(config=config, before_request=budget.before_request),
        budget,
    )


def _courtlistener_bridge_rate_evidence(
    args: argparse.Namespace,
    client: CourtListenerClient,
    budget: CourtListenerRequestBudget | None,
) -> JsonRecord:
    if budget is None:
        return {
            "courtlistener_live": False,
            "courtlistener_physical_requests": client.request_count,
        }
    return {
        "courtlistener_live": True,
        "courtlistener_rate_profile": cast(str, args.courtlistener_rate_profile),
        "courtlistener_request_ledger": str(budget.path.resolve()),
        "courtlistener_physical_requests": client.request_count,
        "courtlistener_reservations_this_phase": budget.local_reservations,
        "courtlistener_reservations_total": budget.total_reservations(),
        "courtlistener_limits": {
            "per_minute": budget.limits.per_minute,
            "per_hour": budget.limits.per_hour,
            "per_day": budget.limits.per_day,
        },
    }


def _recap_fetch_rate_evidence(
    args: argparse.Namespace,
    *,
    client: CourtListenerRecapFetchClient | None,
    budget: CourtListenerRequestBudget | None,
    live: bool,
) -> JsonRecord:
    """Return request-ledger evidence for RECAP verification and polling GETs."""

    evidence: JsonRecord = {
        "courtlistener_live": live,
        "courtlistener_physical_requests": (
            0 if client is None else client.courtlistener_request_count
        ),
    }
    if not live:
        return evidence
    evidence.update(
        {
            "courtlistener_rate_profile": cast(str, args.courtlistener_rate_profile),
            "courtlistener_request_budget_max_wait_seconds": cast(
                float, args.request_budget_max_wait_seconds
            ),
        }
    )
    request_ledger = cast(Path | None, args.request_ledger)
    if request_ledger is not None:
        evidence["courtlistener_request_ledger"] = str(request_ledger.resolve())
    if budget is not None:
        evidence.update(
            {
                "courtlistener_reservations_this_phase": budget.local_reservations,
                "courtlistener_reservations_total": budget.total_reservations(),
                "courtlistener_limits": {
                    "per_minute": budget.limits.per_minute,
                    "per_hour": budget.limits.per_hour,
                    "per_day": budget.limits.per_day,
                },
            }
        )
    return evidence


def _batch_002_rate_evidence(
    args: argparse.Namespace,
    client: CourtListenerClient,
    budget: CourtListenerRequestBudget | None,
) -> dict[str, object]:
    """Return auditable request-budget evidence for a phase summary."""

    if budget is None:
        return {
            "courtlistener_live": False,
            "courtlistener_physical_requests": client.request_count,
        }
    total = budget.total_reservations()
    return {
        "courtlistener_live": True,
        "courtlistener_rate_profile": cast(str, args.courtlistener_rate_profile),
        "courtlistener_request_ledger": str(budget.path.resolve()),
        "courtlistener_physical_requests": client.request_count,
        "courtlistener_reservations_this_phase": budget.local_reservations,
        "courtlistener_reservations_total": total,
        "courtlistener_limits": {
            "per_minute": budget.limits.per_minute,
            "per_hour": budget.limits.per_hour,
            "per_day": budget.limits.per_day,
        },
    }


def _batch_002_default_live_interval(args: argparse.Namespace) -> float:
    """Return quarter-second-rounded spacing that honors the hourly profile."""

    profile = cast(str, args.courtlistener_rate_profile)
    per_hour = _COURTLISTENER_RATE_PROFILES[profile].per_hour
    return math.ceil((3_600.0 / per_hour) * 4.0) / 4.0


def _batch_002_observe_pacer(args: argparse.Namespace) -> RequestPacer | None:
    """Build a conservatively spaced pacer, or None when pacing is disabled."""

    configured = cast(float | None, args.min_interval_seconds)
    jitter = cast(float, args.jitter_seconds)
    if configured is not None and configured < 0:
        raise CommandError("--min-interval-seconds cannot be negative")
    if jitter < 0:
        raise CommandError("--jitter-seconds cannot be negative")
    if configured is None and not cast(bool, args.live):
        return None
    min_interval = (
        _batch_002_default_live_interval(args) if configured is None else configured
    )
    if min_interval <= 0 and jitter <= 0:
        return None
    if jitter <= 0:
        return RequestPacer(min_interval_seconds=max(min_interval, 0.0))
    rng = random.Random()
    base_sleep = time.sleep

    def jittered_sleep(seconds: float) -> None:
        base_sleep(seconds + rng.uniform(0.0, jitter))

    return RequestPacer(
        min_interval_seconds=max(min_interval, 0.0),
        sleep=jittered_sleep,
    )


def _cmd_batch_002_discover(args: argparse.Namespace) -> int:
    cycle_store = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    anchor = _iso_date_argument(
        cast(str, args.eligibility_anchor), "--eligibility-anchor"
    )
    window_start = _iso_date_argument(
        cast(str, args.decision_window_start), "--decision-window-start"
    )
    window_end = _iso_date_argument(
        cast(str, args.decision_window_end), "--decision-window-end"
    )
    if window_end < window_start:
        raise CommandError(
            "--decision-window-end cannot precede --decision-window-start"
        )
    override = cast(float | None, args.min_interval_seconds)
    if override is not None and override < 0:
        raise CommandError("--min-interval-seconds cannot be negative")
    client, budget = _batch_002_client(args, require_token=False)
    if override is not None:
        pacer: RequestPacer | None = RequestPacer(min_interval_seconds=override)
    elif cast(bool, args.live):
        pacer = RequestPacer(
            min_interval_seconds=_batch_002_default_live_interval(args)
        )
    else:
        pacer = None
    try:
        with CycleAcquisitionStore(cycle_store) as store:
            store.ensure_cycle(_cycle_acquisition_policy(anchor=anchor))
            funnel = run_discover(
                store,
                batch_id=batch_id,
                client=client,
                decision_window_start=window_start,
                decision_window_end=window_end,
                top_k_per_term=cast(int, args.top_k_per_term),
                page_size=cast(int, args.page_size),
                pacer=pacer,
            )
    except (
        CycleAcquisitionStoreError,
        CourtListenerRequestBudgetError,
        RecapApiBatchDriverError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    record = {
        **funnel.to_record(),
        **_batch_002_rate_evidence(args, client, budget),
    }
    summary_output = cast(Path | None, args.summary_output)
    if summary_output is not None:
        _write_json(summary_output, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _cmd_batch_002_observe(args: argparse.Namespace) -> int:
    cycle_store = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    anchor = _iso_date_argument(
        cast(str, args.eligibility_anchor), "--eligibility-anchor"
    )
    limit = cast(int | None, args.limit)
    refresh_reason_codes = tuple(cast(list[str], args.refresh_reason_code))
    revalidate_candidate_ids = tuple(cast(list[str], args.revalidate_candidate_id))
    refresh_campaign_cutoff = cast(str | None, args.refresh_campaign_cutoff)
    if limit is not None and limit <= 0:
        raise CommandError("--limit must be a positive integer")
    if (
        refresh_reason_codes or revalidate_candidate_ids
    ) and refresh_campaign_cutoff is None:
        raise CommandError(
            "--refresh-campaign-cutoff is required with refresh/revalidation"
        )
    client, budget = _batch_002_client(args, require_token=True)
    pacer = _batch_002_observe_pacer(args)
    try:
        with CycleAcquisitionStore(cycle_store) as store:
            tally = run_observe(
                store,
                batch_id=batch_id,
                client=client,
                eligibility_anchor=anchor,
                pacer=pacer,
                limit=limit,
                refresh_reason_codes=refresh_reason_codes,
                revalidate_candidate_ids=revalidate_candidate_ids,
                refresh_campaign_cutoff=refresh_campaign_cutoff,
            )
    except (
        CycleAcquisitionStoreError,
        CourtListenerRequestBudgetError,
        RecapApiBatchDriverError,
        RecapApiDiscoveryError,
        KeyError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    record = {
        **tally.to_record(),
        "refresh_reason_codes": list(refresh_reason_codes),
        "revalidate_candidate_ids": list(revalidate_candidate_ids),
        "refresh_campaign_cutoff": refresh_campaign_cutoff,
        **_batch_002_rate_evidence(args, client, budget),
    }
    summary_output = cast(Path | None, args.summary_output)
    if summary_output is not None:
        _write_json(summary_output, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _cmd_batch_002_seed(args: argparse.Namespace) -> int:
    source_store = cast(Path, args.source_store)
    cycle_store = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    source_batch_id = cast(str | None, args.source_batch_id)
    try:
        leads = read_batch_001_enrichment_failure_leads(
            source_store, source_batch_id=source_batch_id
        )
        with CycleAcquisitionStore(cycle_store) as store:
            result = seed_batch_001_leads(store, batch_id=batch_id, leads=leads)
    except (
        CycleAcquisitionStoreError,
        RecapApiBatchDriverError,
        KeyError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    record = result.to_record()
    summary_output = cast(Path | None, args.summary_output)
    if summary_output is not None:
        _write_json(summary_output, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _cmd_batch_002_direct_seed(args: argparse.Namespace) -> int:
    source_store = cast(Path, args.source_store)
    source_batch_id = cast(str, args.source_batch_id)
    cycle_store = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    try:
        source = read_saturated_direct_search_leads(
            source_store,
            source_batch_id=source_batch_id,
        )
        with CycleAcquisitionStore(cycle_store) as store:
            result = seed_direct_search_leads(
                store,
                batch_id=batch_id,
                source=source,
                page_size=cast(int, args.page_size),
            )
    except (
        CycleAcquisitionStoreError,
        RecapApiBatchDriverError,
        KeyError,
        OSError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    record = result.to_record()
    summary_output = cast(Path | None, args.summary_output)
    if summary_output is not None:
        _write_json(summary_output, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _cmd_batch_002_snapshot(args: argparse.Namespace) -> int:
    cycle_store = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    snapshot_id = cast(str, args.snapshot_id)
    output_root = cast(Path, args.output_root)
    try:
        with CycleAcquisitionStore(cycle_store) as store:
            cycle_hash = store.cycle_hash
            batch_digest = store.batch_digest(batch_id)
            if not store.snapshot_is_saturated(batch_id):
                raise SnapshotVerificationError(
                    "batch-002 snapshot requires every discovery term to be "
                    "exhausted before publication"
                )
            snapshot_path = store.export_snapshot(
                output_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
                complete=True,
            )
        manifest = verify_snapshot(
            snapshot_path,
            expected_cycle_hash=cycle_hash,
            expected_batch_digest=batch_digest,
            require_complete=True,
            require_saturated=True,
        )
    except (
        CycleAcquisitionStoreError,
        FileExistsError,
        KeyError,
        OSError,
        SnapshotVerificationError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    record = {
        "schema_version": "legalforecast.batch_002_snapshot_result.v1",
        "batch_id": batch_id,
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshot_path.resolve()),
        "cycle_hash": cycle_hash,
        "batch_digest": batch_digest,
        "verified": True,
        "saturated": manifest.get("saturated") is True,
    }
    summary_output = cast(Path | None, args.summary_output)
    if summary_output is not None:
        _write_json(summary_output, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _cmd_generate_cohort_policy(args: argparse.Namespace) -> int:
    try:
        artifact = generate_cohort_policy(_read_json_object(cast(Path, args.decisions)))
        write_cohort_policy(cast(Path, args.output), artifact)
    except (CohortPolicyError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_verify_cohort_policy(args: argparse.Namespace) -> int:
    try:
        verify_cohort_policy(
            _read_json_object(cast(Path, args.policy)),
            expected_sha256=cast(str | None, args.expected_sha256),
        )
    except (CohortPolicyError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_generate_purchase_policy(args: argparse.Namespace) -> int:
    try:
        artifact = generate_case_dev_purchase_policy(
            _read_json_object(cast(Path, args.decisions))
        )
        policy = verify_case_dev_purchase_policy(artifact)
        verify_case_dev_purchase_policy_cohort_binding(
            policy,
            _read_json_object(cast(Path, args.cohort_policy)),
        )
        write_case_dev_purchase_policy(cast(Path, args.output), artifact)
    except (CaseDevPurchasePolicyError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_init_purchase_ledger(args: argparse.Namespace) -> int:
    """Exclusively initialize or authenticate one pristine purchase ledger."""

    output_root = cast(Path, args.output_root)
    purchase_policy_path = cast(Path, args.purchase_policy)
    cohort_policy_path = cast(Path, args.cohort_policy)
    ledger_path = cast(Path, args.purchase_ledger)
    receipt_path = _acquisition_path(
        args,
        "initialization_receipt_output",
        output_root / "purchase-ledger-initialization.json",
    )
    run_card_path = _acquisition_path(
        args,
        "run_card_output",
        output_root / "run-cards/init-purchase-ledger.json",
    )
    log_path = _acquisition_path(
        args,
        "log_output",
        output_root / "logs/init-purchase-ledger.jsonl",
    )
    input_paths = (purchase_policy_path, cohort_policy_path)
    output_paths = (ledger_path, receipt_path)
    zero_activity: JsonRecord = {
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    try:
        _validate_init_purchase_ledger_no_mutation_paths(
            output_root=output_root,
            ledger_path=ledger_path,
            purchase_policy_path=purchase_policy_path,
            cohort_policy_path=cohort_policy_path,
            receipt_path=receipt_path,
            run_card_path=run_card_path,
            log_path=log_path,
        )
    except (OSError, ValueError) as exc:
        # These paths carry the failure record itself. If they are unsafe, do
        # not touch them in an attempt to report that they are unsafe.
        raise CommandError(str(exc)) from exc
    try:
        purchase_policy = verify_case_dev_purchase_policy(
            _read_json_object(purchase_policy_path)
        )
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy,
            _read_json_object(cohort_policy_path),
        )
        _validate_init_purchase_ledger_paths(
            ledger_path=ledger_path,
            canonical_ledger_path=purchase_policy.canonical_ledger_path,
            purchase_policy_path=purchase_policy_path,
            cohort_policy_path=cohort_policy_path,
            receipt_path=receipt_path,
            run_card_path=run_card_path,
            log_path=log_path,
        )
    except (
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="init-purchase-ledger",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=zero_activity,
        )
        raise CommandError(str(exc)) from exc

    if _acquisition_dry_run(args):
        _write_acquisition_completion(
            args,
            stage="init-purchase-ledger",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra={
                **zero_activity,
                "canonical_ledger_path": str(ledger_path),
                "purchase_policy_sha256": purchase_policy.policy_sha256,
                "cohort_policy_sha256": purchase_policy.cohort_policy_sha256,
                "initialized_or_verified": False,
            },
        )
        return 0

    try:
        if receipt_path.exists() or receipt_path.is_symlink():
            if not cast(bool, args.resume):
                raise CaseDevPurchaseLedgerError(
                    "initialization receipt already exists and --no-resume "
                    "forbids verification"
                )
            receipt = verify_case_dev_purchase_journal_initialization(
                ledger_path,
                policy=purchase_policy,
                receipt_path=receipt_path,
                purchase_policy_file_sha256=_path_sha256(purchase_policy_path),
                cohort_policy_file_sha256=_path_sha256(cohort_policy_path),
            )
        else:
            receipt = initialize_case_dev_purchase_journal(
                ledger_path,
                policy=purchase_policy,
                receipt_path=receipt_path,
                purchase_policy_file_sha256=_path_sha256(purchase_policy_path),
                cohort_policy_file_sha256=_path_sha256(cohort_policy_path),
                initialized_at=_iso_datetime(datetime.now(UTC)),
            )
    except (
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        OSError,
        sqlite3.Error,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="init-purchase-ledger",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=zero_activity,
        )
        raise CommandError(str(exc)) from exc

    try:
        _write_acquisition_completion(
            args,
            stage="init-purchase-ledger",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=1,
            dry_run=False,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra={**receipt, **zero_activity},
        )
    except (OSError, ValueError) as exc:
        raise CommandError(
            "purchase ledger initialization is durable, but completion "
            f"artifact publication failed: {exc}"
        ) from exc
    return 0


def _validate_init_purchase_ledger_no_mutation_paths(
    *,
    output_root: Path,
    ledger_path: Path,
    purchase_policy_path: Path,
    cohort_policy_path: Path,
    receipt_path: Path,
    run_card_path: Path,
    log_path: Path,
) -> None:
    named = {
        "purchase policy": purchase_policy_path,
        "cohort policy": cohort_policy_path,
        "initialization receipt": receipt_path,
        "run card": run_card_path,
        "stage log": log_path,
    }
    ledger = ledger_path.resolve(strict=False)
    output = output_root.resolve(strict=False)
    if output == ledger or ledger in output.parents:
        raise ValueError(
            "--output-root must not equal or descend from --purchase-ledger"
        )
    reserved = tuple(
        path.resolve(strict=False)
        for path in (
            ledger_path,
            Path(f"{ledger_path}.lock"),
            Path(f"{ledger_path}-wal"),
            Path(f"{ledger_path}-shm"),
            Path(f"{ledger_path}-journal"),
        )
    )
    resolved: dict[Path, str] = {}
    existing: list[tuple[str, Path]] = []
    for label, path in named.items():
        identity = path.resolve(strict=False)
        for reserved_path in reserved:
            if (
                identity == reserved_path
                or identity in reserved_path.parents
                or reserved_path in identity.parents
            ):
                raise ValueError(
                    "init-purchase-ledger path conflicts with reserved ledger "
                    f"namespace: {label}: {path}"
                )
        previous = resolved.get(identity)
        if previous is not None:
            raise ValueError(
                f"init-purchase-ledger writable paths alias: {previous} and {label}"
            )
        resolved[identity] = label
        if path.is_symlink():
            raise ValueError(
                f"init-purchase-ledger writable path must not be a symlink: "
                f"{label}: {path}"
            )
        if path.exists():
            metadata = path.stat()
            if not path.is_file() or metadata.st_nlink != 1:
                raise ValueError(
                    "init-purchase-ledger writable path must be a singly linked "
                    f"regular file: {label}: {path}"
                )
            existing.append((label, path))
    for index, (left_label, left_path) in enumerate(existing):
        for right_label, right_path in existing[index + 1 :]:
            if left_path.samefile(right_path):
                raise ValueError(
                    f"init-purchase-ledger writable paths alias: {left_label} and "
                    f"{right_label}"
                )


def _validate_init_purchase_ledger_paths(
    *,
    ledger_path: Path,
    canonical_ledger_path: Path,
    purchase_policy_path: Path,
    cohort_policy_path: Path,
    receipt_path: Path,
    run_card_path: Path,
    log_path: Path,
) -> None:
    if not ledger_path.is_absolute() or ledger_path != canonical_ledger_path:
        raise CaseDevPurchasePolicyError(
            "purchase ledger path conflicts with canonical policy locator"
        )
    named_paths = {
        "purchase ledger": ledger_path,
        "purchase policy": purchase_policy_path,
        "cohort policy": cohort_policy_path,
        "initialization receipt": receipt_path,
        "run card": run_card_path,
        "stage log": log_path,
    }
    resolved: dict[Path, str] = {}
    for label, path in named_paths.items():
        identity = path.resolve()
        previous = resolved.get(identity)
        if previous is not None:
            raise CaseDevPurchaseLedgerError(
                f"init-purchase-ledger paths alias: {previous} and {label}"
            )
        resolved[identity] = label
    existing = [(label, path) for label, path in named_paths.items() if path.exists()]
    for index, (left_label, left_path) in enumerate(existing):
        left_stat = left_path.stat()
        if (
            left_label
            in {
                "purchase ledger",
                "initialization receipt",
                "run card",
                "stage log",
            }
            and left_stat.st_nlink > 1
        ):
            raise CaseDevPurchaseLedgerError(
                f"{left_label} must not be hard-linked: {left_path}"
            )
        for right_label, right_path in existing[index + 1 :]:
            if left_path.samefile(right_path):
                raise CaseDevPurchaseLedgerError(
                    f"init-purchase-ledger paths alias: {left_label} and {right_label}"
                )


def _cmd_build_clearance_replacement_frontier(args: argparse.Namespace) -> int:
    projection_path = cast(Path, args.projection)
    initial_selection_path = cast(Path, args.initial_selection)
    candidate_frontier_path = cast(Path, args.candidate_frontier)
    try:
        commitments = _replacement_source_commitments(
            cast(Sequence[str], args.source),
            fixed={
                "projection_artifact": projection_path,
                "initial_selection": initial_selection_path,
                "candidate_frontier": candidate_frontier_path,
            },
        )
        artifact = build_replacement_frontier(
            cohort_policy_artifact=_read_json_object(cast(Path, args.cohort_policy)),
            purchase_policy_artifact=_read_json_object(
                cast(Path, args.purchase_policy)
            ),
            projection_sha256=_path_sha256(projection_path),
            initial_selected_candidate_ids=_replacement_initial_candidate_ids(
                initial_selection_path
            ),
            candidate_rows=_replacement_frontier_rows(candidate_frontier_path),
            case_mix_max_per_bucket=cast(int | None, args.case_mix_max_per_bucket),
            source_commitments=commitments,
        )
        write_replacement_frontier(cast(Path, args.output), artifact)
        broad_allowlist = build_broad_broker_allowlist_plan(
            cohort_policy_artifact=_read_json_object(cast(Path, args.cohort_policy)),
            purchase_policy_artifact=_read_json_object(
                cast(Path, args.purchase_policy)
            ),
            frontier_artifact=artifact,
        )
        _atomic_write_json(
            cast(Path, args.broker_allowlist_plan_output),
            broad_allowlist.to_record(),
        )
    except (
        ClearanceReplacementError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    print(
        json.dumps(
            {
                "output": str(cast(Path, args.output)),
                "frontier_sha256": artifact["policy_sha256"],
                "candidate_count": artifact["policy"]["candidate_count"],
                "frontier_truncated": artifact["policy"]["frontier_truncated"],
                "broad_allowlist_candidate_count": len(broad_allowlist.case_plans),
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_plan_clearance_replacements(args: argparse.Namespace) -> int:
    output = cast(Path, args.output)
    replacement_output = cast(Path, args.replacement_budget_plan_output)
    allowlist_output = cast(Path, args.broker_allowlist_plan_output)
    exclusions_output = cast(Path, args.exclusions_output)
    try:
        purchase_artifact = _read_json_object(cast(Path, args.purchase_policy))
        purchase_policy = verify_case_dev_purchase_policy(purchase_artifact)
        with CaseDevPurchaseJournal(
            cast(Path, args.purchase_ledger).resolve(), policy=purchase_policy
        ) as journal:
            result = plan_clearance_replacements(
                cohort_policy_artifact=_read_json_object(
                    cast(Path, args.cohort_policy)
                ),
                purchase_policy_artifact=purchase_artifact,
                frontier_artifact=_read_json_object(cast(Path, args.frontier)),
                purchase_journal=journal,
                purchased_clearance_records=_read_records(
                    cast(Path, args.purchased_clearance)
                ),
                clearance_run_card_sha256=_path_sha256(
                    cast(Path, args.clearance_run_card)
                ),
            )
        _atomic_write_json(output, result.to_record())
        _atomic_write_json(replacement_output, result.replacement_plan.to_record())
        _atomic_write_json(allowlist_output, result.broker_allowlist_plan.to_record())
        _write_jsonl(exclusions_output, result.derived_exclusions)
    except (
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        ClearanceReplacementError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    print(
        json.dumps(
            {
                "output": str(output),
                "active_candidate_count": len(result.active_candidate_ids),
                "replacement_candidate_count": len(result.replacement_plan.case_plans),
                "broad_allowlist_candidate_count": len(
                    result.broker_allowlist_plan.case_plans
                ),
                "stop_reason": result.stop_reason,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_generate_recap_fetch_broker_policy(args: argparse.Namespace) -> int:
    output = cast(Path, args.output)
    try:
        budget_plan_artifact = _read_json_object(cast(Path, args.budget_plan))
        policy = generate_recap_fetch_broker_policy(
            purchase_policy_artifact=_read_json_object(
                cast(Path, args.purchase_policy)
            ),
            cohort_policy_artifact=_read_json_object(cast(Path, args.cohort_policy)),
            budget_plan=_missing_core_budget_plan(budget_plan_artifact),
            budget_plan_artifact=budget_plan_artifact,
            selection_records=_read_records(cast(Path, args.selection)),
            broad_frontier_allowlist=cast(bool, args.broad_frontier_allowlist),
        )
        write_recap_fetch_broker_policy(output, policy)
    except (
        RecapFetchBrokerPolicyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    print(
        json.dumps(
            {
                "output": str(output),
                "broker_policy_sha256": broker_policy_sha256(policy),
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_reconcile_purchase(args: argparse.Namespace) -> int:
    ledger_path = cast(Path, args.purchase_ledger).resolve()
    try:
        policy = verify_case_dev_purchase_policy(
            _read_json_object(cast(Path, args.purchase_policy))
        )
        verify_case_dev_purchase_policy_cohort_binding(
            policy,
            _read_json_object(cast(Path, args.cohort_policy)),
        )
        with CaseDevPurchaseJournal(ledger_path, policy=policy) as journal:
            journal.reconcile(_read_json_object(cast(Path, args.evidence)))
    except (
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_export_cohort_observations(args: argparse.Namespace) -> int:
    try:
        policy = _read_json_object(cast(Path, args.policy))
        with CycleAcquisitionStore(cast(Path, args.cycle_store)) as store:
            export_observation_manifest(
                store=store,
                policy_artifact=policy,
                destination=cast(Path, args.output),
            )
    except (
        CohortPolicyError,
        CycleAcquisitionStoreError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_verify_cohort_observations(args: argparse.Namespace) -> int:
    try:
        verify_observation_manifest(
            read_observation_manifest(cast(Path, args.manifest)),
            policy_artifact=_read_json_object(cast(Path, args.policy)),
        )
    except (CohortPolicyError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    return 0


def _firecrawl_docket_html_audit(
    *,
    requested: bool,
    credit_cap: int,
    source: DurableBudgetedCourtListenerHTMLSource | None,
    store: CycleAcquisitionStore | None,
    run_id: str | None,
) -> JsonRecord:
    """Return conservative metered-activity evidence for hybrid discovery."""

    durable_summary: JsonRecord = {}
    if source is not None:
        durable_summary.update(source.audit_summary())
    elif store is not None and run_id is not None:
        try:
            durable_summary.update(store.firecrawl_run_summary(run_id))
        except KeyError:
            # Initialization can fail before the durable run row is created.
            pass
    audit_schema_version = durable_summary.pop("schema_version", None)
    firecrawl_run_status = durable_summary.pop("status", None)
    executed = _firecrawl_metered_activity_executed(
        live=requested,
        summary=durable_summary,
    )
    return {
        "docket_html_source": "firecrawl",
        "firecrawl_metered_activity_requested": requested,
        "firecrawl_metered_activity_executed": executed,
        "firecrawl_max_credits_per_new_candidate": 3,
        "firecrawl_cycle_credit_cap": credit_cap,
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
        **(
            {"firecrawl_audit_schema_version": audit_schema_version}
            if audit_schema_version is not None
            else {}
        ),
        **(
            {"firecrawl_run_status": firecrawl_run_status}
            if firecrawl_run_status is not None
            else {}
        ),
        **durable_summary,
    }


def _courtlistener_discovery_rate_audit(
    *,
    client: CourtListenerClient | None,
    budget: CourtListenerRequestBudget | None,
) -> JsonRecord:
    """Return durable REST-attempt evidence for discovery run artifacts."""

    if client is None or budget is None:
        return {
            "courtlistener_request_budget_enabled": False,
            "courtlistener_physical_requests": 0
            if client is None
            else client.request_count,
        }
    return {
        "courtlistener_request_budget_enabled": True,
        "courtlistener_request_ledger": str(budget.path.resolve()),
        "courtlistener_physical_requests": client.request_count,
        "courtlistener_reservations_this_run": budget.local_reservations,
        "courtlistener_reservations_total": budget.total_reservations(),
        "courtlistener_limits": {
            "per_minute": budget.limits.per_minute,
            "per_hour": budget.limits.per_hour,
            "per_day": budget.limits.per_day,
        },
    }


def _cmd_acquisition_discover_courtlistener(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    screened_cases_path = _acquisition_path(
        args,
        "screened_cases_output",
        output_root / "courtlistener-screened-cases.jsonl",
    ).resolve()
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "courtlistener-discovery-exclusions.jsonl",
    ).resolve()
    raw_html_dir = _acquisition_path(
        args,
        "raw_html_dir",
        output_root / "raw-courtlistener-html",
    ).resolve()
    search_pages_path = _acquisition_path(
        args,
        "search_pages_output",
        output_root / "courtlistener-search-pages.jsonl",
    ).resolve()
    raw_artifacts_path = _acquisition_path(
        args,
        "raw_artifacts_output",
        output_root / "courtlistener-raw-artifacts.jsonl",
    ).resolve()
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "courtlistener-discovery-summary.json",
    ).resolve()
    anchor = _iso_date_argument(
        cast(str, args.eligibility_anchor), "--eligibility-anchor"
    )
    search_window_start = _iso_date_argument(
        cast(str, args.search_window_start), "--search-window-start"
    )
    search_window_end = _iso_date_argument(
        cast(str, args.search_window_end), "--search-window-end"
    )
    if search_window_end < search_window_start:
        raise CommandError("--search-window-end cannot precede --search-window-start")
    if search_window_end < anchor:
        raise CommandError("--search-window-end cannot precede --eligibility-anchor")
    cycle_store_path = cast(Path | None, args.cycle_store)
    batch_id = cast(str | None, args.batch_id)
    if (cycle_store_path is None) != (batch_id is None):
        raise CommandError("--cycle-store and --batch-id must be supplied together")
    query_terms = tuple(cast(Sequence[str] | None, args.query_terms) or ())
    if not query_terms:
        query_terms = DEFAULT_COURTLISTENER_MTD_QUERY_TERMS
    target_clean_cases = cast(int, args.target_clean_cases)
    max_candidates = cast(int, args.max_candidates)
    search_page_size = cast(int, args.search_page_size)
    dry_run = _acquisition_dry_run(args)
    fixture_path = cast(Path | None, args.courtlistener_fixture)
    html_fixture_dir = cast(Path | None, args.docket_html_fixture_dir)
    live = cast(bool, args.live)
    live_firecrawl_docket_html = cast(bool, args.live_firecrawl_docket_html)
    firecrawl_credit_cap = cast(int, args.firecrawl_credit_cap)
    if live_firecrawl_docket_html and not live:
        raise CommandError("--live-firecrawl-docket-html requires --live")
    if live_firecrawl_docket_html and not 1 <= firecrawl_credit_cap <= 45_000:
        raise CommandError("--firecrawl-credit-cap must be between 1 and 45000")
    if (
        live_firecrawl_docket_html
        and not dry_run
        and (cycle_store_path is None or batch_id is None)
    ):
        raise CommandError(
            "--live-firecrawl-docket-html execution requires --cycle-store and "
            "--batch-id for durable credit authorization"
        )
    firecrawl_run_id = (
        f"{batch_id}-courtlistener-docket-html-v1"
        if live_firecrawl_docket_html and batch_id is not None
        else None
    )
    input_paths = tuple(
        path for path in (fixture_path, html_fixture_dir) if path is not None
    )
    output_paths = (
        screened_cases_path,
        exclusions_path,
        raw_html_dir,
        summary_path,
        search_pages_path,
        raw_artifacts_path,
    )

    if dry_run:
        dry_run_firecrawl_audit = (
            _firecrawl_docket_html_audit(
                requested=False,
                credit_cap=firecrawl_credit_cap,
                source=None,
                store=None,
                run_id=firecrawl_run_id,
            )
            if live_firecrawl_docket_html
            else None
        )
        summary: JsonRecord = {
            "schema_version": "legalforecast.courtlistener_discovery_summary.v1",
            "dry_run": True,
            "anchor_date": anchor.isoformat(),
            "search_window_start": search_window_start.isoformat(),
            "search_window_end": search_window_end.isoformat(),
            "query_terms": list(query_terms),
            "target_clean_cases": target_clean_cases,
            "max_candidates": max_candidates,
            "search_page_size": search_page_size,
            "live": live,
        }
        if live_firecrawl_docket_html:
            summary.update(
                {
                    "docket_html_source": "firecrawl",
                    "firecrawl_run_id": firecrawl_run_id,
                    "firecrawl_credit_cap": firecrawl_credit_cap,
                    **cast(JsonRecord, dry_run_firecrawl_audit),
                }
            )
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra={
                "anchor_date": anchor.isoformat(),
                "target_clean_cases": target_clean_cases,
                **({} if dry_run_firecrawl_audit is None else dry_run_firecrawl_audit),
            },
        )
        return 0

    fixture_pair_present = fixture_path is not None and html_fixture_dir is not None
    fixture_pair_partial = (fixture_path is None) != (html_fixture_dir is None)
    if live and (fixture_path is not None or html_fixture_dir is not None):
        raise CommandError("--live cannot be combined with CourtListener fixtures")
    if fixture_pair_partial:
        raise CommandError(
            "discover-courtlistener requires --live or both "
            "--courtlistener-fixture and --docket-html-fixture-dir"
        )
    if not live and not fixture_pair_present:
        raise CommandError(
            "discover-courtlistener requires --live or both "
            "--courtlistener-fixture and --docket-html-fixture-dir"
        )

    try:
        validate_courtlistener_discovery_limits(
            query_terms=query_terms,
            target_clean_cases=target_clean_cases,
            max_candidates=max_candidates,
            search_page_size=search_page_size,
        )
    except ValueError as exc:
        _write_acquisition_failure(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=live_firecrawl_docket_html,
            extra=(
                _firecrawl_docket_html_audit(
                    requested=live_firecrawl_docket_html,
                    credit_cap=firecrawl_credit_cap,
                    source=None,
                    store=None,
                    run_id=firecrawl_run_id,
                )
                if live_firecrawl_docket_html
                else None
            ),
        )
        raise CommandError(str(exc)) from exc

    cycle_hash: str | None = None
    batch_digest: str | None = None
    if cycle_store_path is not None and batch_id is not None:
        try:
            with CycleAcquisitionStore(cycle_store_path) as store:
                cycle_hash = store.ensure_cycle(
                    _cycle_acquisition_policy(anchor=anchor)
                )
                frozen_batch_config: JsonRecord = {
                    "provider": "courtlistener",
                    "search_window_start": search_window_start.isoformat(),
                    "search_window_end": search_window_end.isoformat(),
                    "query_terms": list(query_terms),
                    "target_clean_cases": target_clean_cases,
                    "max_candidates": max_candidates,
                    "search_page_size": search_page_size,
                }
                if live_firecrawl_docket_html:
                    assert firecrawl_run_id is not None
                    frozen_batch_config.update(
                        {
                            "docket_html_source": "firecrawl",
                            "firecrawl_run_id": firecrawl_run_id,
                            "firecrawl_credit_cap": firecrawl_credit_cap,
                        }
                    )
                batch_digest = store.ensure_batch(
                    batch_id,
                    frozen_batch_config,
                )
        except CycleAcquisitionStoreError as exc:
            raise CommandError(str(exc)) from exc

    config = CourtListenerConfig.from_env()
    courtlistener_request_budget: CourtListenerRequestBudget | None = None
    durable_firecrawl_store: CycleAcquisitionStore | None = None
    durable_firecrawl_source: DurableBudgetedCourtListenerHTMLSource | None = None
    firecrawl_source_receipts: dict[str, Mapping[str, object]] = {}
    if live:
        if config.api_token is None:
            raise CommandError(f"{COURTLISTENER_API_TOKEN_ENV} is required with --live")
        request_ledger = cast(Path | None, args.request_ledger) or (
            output_root / "courtlistener-requests.sqlite3"
        )
        max_wait = cast(float, args.request_budget_max_wait_seconds)
        if max_wait < 0:
            raise CommandError("--request-budget-max-wait-seconds cannot be negative")
        rate_profile = cast(str, args.courtlistener_rate_profile)
        try:
            courtlistener_request_budget = CourtListenerRequestBudget(
                request_ledger,
                limits=_COURTLISTENER_RATE_PROFILES[rate_profile],
                max_wait_seconds=max_wait,
            )
        except (CourtListenerRequestBudgetError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        client = CourtListenerClient(
            config=config,
            before_request=courtlistener_request_budget.before_request,
        )
        if live_firecrawl_docket_html:
            assert cycle_store_path is not None
            assert batch_id is not None
            assert batch_digest is not None
            assert firecrawl_run_id is not None
            try:
                durable_firecrawl_store = CycleAcquisitionStore(cycle_store_path)
                durable_firecrawl_store.ensure_firecrawl_run(
                    firecrawl_run_id,
                    batch_id=batch_id,
                    config={
                        "schema_version": (
                            "legalforecast.firecrawl_docket_html_run.v1"
                        ),
                        "batch_digest": batch_digest,
                        "docket_html_source": "firecrawl",
                        "proxy": "basic",
                        "max_attempts_per_target": 3,
                        "raw_html_dir": str(raw_html_dir),
                    },
                    credit_cap=firecrawl_credit_cap,
                    reserved_credits_per_attempt=1,
                )
                durable_firecrawl_source = DurableBudgetedCourtListenerHTMLSource(
                    store=durable_firecrawl_store,
                    source=FirecrawlCourtListenerHTMLSource(FirecrawlConfig.from_env()),
                    run_id=firecrawl_run_id,
                    raw_html_dir=raw_html_dir,
                )
                html_source = durable_firecrawl_source
            except (CycleAcquisitionStoreError, FirecrawlError, ValueError) as exc:
                firecrawl_audit = _firecrawl_docket_html_audit(
                    requested=True,
                    credit_cap=firecrawl_credit_cap,
                    source=None,
                    store=durable_firecrawl_store,
                    run_id=firecrawl_run_id,
                )
                if durable_firecrawl_store is not None:
                    durable_firecrawl_store.close()
                _write_acquisition_failure(
                    args,
                    stage="discover-courtlistener",
                    input_paths=input_paths,
                    output_paths=output_paths,
                    reason=str(exc),
                    paid_activity_requested=True,
                    paid_activity_executed=cast(
                        bool,
                        firecrawl_audit["firecrawl_metered_activity_executed"],
                    ),
                    extra=firecrawl_audit,
                )
                raise CommandError(str(exc)) from exc
        else:
            html_source = LiveCourtListenerDocketHTMLSource(
                timeout_seconds=config.timeout_seconds
            )
    else:
        assert fixture_path is not None
        assert html_fixture_dir is not None
        client = CourtListenerClient(
            config=config,
            transport=CourtListenerFixtureTransport.from_jsonl(fixture_path),
        )
        html_source = FixtureCourtListenerDocketHTMLSource(html_fixture_dir)

    try:
        if (
            live
            and durable_firecrawl_store is None
            and cycle_store_path is not None
            and batch_id is not None
        ):
            durable_firecrawl_store = CycleAcquisitionStore(cycle_store_path)
        result = discover_courtlistener_mtd_candidates(
            client=client,
            html_source=html_source,
            raw_html_dir=raw_html_dir,
            decision_filed_on_or_after=anchor,
            search_window_start=search_window_start,
            search_window_end=search_window_end,
            query_terms=query_terms,
            target_clean_cases=target_clean_cases,
            max_candidates=max_candidates,
            search_page_size=search_page_size,
            resume=cast(bool, args.resume),
            verify_existing_raw_html=(
                None
                if durable_firecrawl_source is None
                else durable_firecrawl_source.verify_existing_raw_html
            ),
            progress_store=durable_firecrawl_store,
            batch_id=batch_id if durable_firecrawl_store is not None else None,
        )
        courtlistener_rate_audit = _courtlistener_discovery_rate_audit(
            client=client,
            budget=courtlistener_request_budget,
        )
        firecrawl_audit = (
            _firecrawl_docket_html_audit(
                requested=True,
                credit_cap=firecrawl_credit_cap,
                source=durable_firecrawl_source,
                store=durable_firecrawl_store,
                run_id=firecrawl_run_id,
            )
            if live_firecrawl_docket_html
            else None
        )
        if durable_firecrawl_source is not None:
            assert batch_digest is not None
            firecrawl_source_receipts = dict(
                durable_firecrawl_source.successful_artifact_receipts(
                    batch_digest=batch_digest
                )
            )
    except (
        CourtListenerClientError,
        CycleAcquisitionStoreError,
        CourtListenerRequestBudgetError,
        FirecrawlArtifactError,
        FirecrawlError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        courtlistener_rate_audit = _courtlistener_discovery_rate_audit(
            client=client,
            budget=courtlistener_request_budget,
        )
        firecrawl_audit = (
            _firecrawl_docket_html_audit(
                requested=True,
                credit_cap=firecrawl_credit_cap,
                source=durable_firecrawl_source,
                store=durable_firecrawl_store,
                run_id=firecrawl_run_id,
            )
            if live_firecrawl_docket_html
            else None
        )
        _write_acquisition_failure(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=live_firecrawl_docket_html,
            paid_activity_executed=(
                False
                if firecrawl_audit is None
                else cast(bool, firecrawl_audit["firecrawl_metered_activity_executed"])
            ),
            extra={
                **courtlistener_rate_audit,
                **({} if firecrawl_audit is None else firecrawl_audit),
            },
        )
        raise CommandError(str(exc)) from exc
    finally:
        if durable_firecrawl_store is not None:
            durable_firecrawl_store.close()

    try:
        _write_jsonl(screened_cases_path, list(result.screened_cases))
        _write_jsonl(
            exclusions_path,
            [exclusion.to_record() for exclusion in result.exclusions],
        )
        _write_jsonl(search_pages_path, list(result.search_pages))
        raw_artifacts = _courtlistener_raw_artifact_records(
            raw_html_dir=raw_html_dir,
            screened_cases=result.screened_cases,
            exclusions=tuple(exclusion.to_record() for exclusion in result.exclusions),
        )
        if live_firecrawl_docket_html:
            raw_artifact_ids = {
                _required_str(record, "candidate_id") for record in raw_artifacts
            }
            receipt_ids = set(firecrawl_source_receipts)
            if raw_artifact_ids != receipt_ids:
                missing_receipts = sorted(raw_artifact_ids - receipt_ids)
                orphan_receipts = sorted(receipt_ids - raw_artifact_ids)
                raise FirecrawlArtifactError(
                    "Firecrawl raw artifact receipts do not reconcile: "
                    f"missing={missing_receipts!r}, orphan={orphan_receipts!r}"
                )
            for record in raw_artifacts:
                candidate_id = _required_str(record, "candidate_id")
                record["source_receipt"] = dict(firecrawl_source_receipts[candidate_id])
        _write_jsonl(raw_artifacts_path, raw_artifacts)
        summary: JsonRecord = {
            **result.summary,
            "dry_run": False,
            "live": live,
            **courtlistener_rate_audit,
        }
        if firecrawl_audit is not None:
            summary.update(
                {
                    "docket_html_source": "firecrawl",
                    "firecrawl_run_id": firecrawl_run_id,
                    "firecrawl_credit_cap": firecrawl_credit_cap,
                    "firecrawl_source_receipt_count": len(firecrawl_source_receipts),
                    **firecrawl_audit,
                }
            )
        _write_json(summary_path, summary)
        output_commitments = {
            "screened_cases": _file_commitment(screened_cases_path),
            "exclusions": _file_commitment(exclusions_path),
            "summary": _file_commitment(summary_path),
            "search_pages": _file_commitment(search_pages_path),
            "raw_artifacts": _file_commitment(raw_artifacts_path),
        }
        _write_acquisition_completion(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=len(result.screened_cases),
            dry_run=False,
            paid_activity_requested=live_firecrawl_docket_html,
            paid_activity_executed=(
                False
                if firecrawl_audit is None
                else cast(
                    bool,
                    firecrawl_audit["firecrawl_metered_activity_executed"],
                )
            ),
            extra={
                "anchor_date": anchor.isoformat(),
                "target_clean_cases": target_clean_cases,
                "accepted_case_count": len(result.screened_cases),
                "excluded_case_count": len(result.exclusions),
                "cycle_hash": cycle_hash,
                "batch_digest": batch_digest,
                **courtlistener_rate_audit,
                **(
                    {"firecrawl_source_receipt_count": len(firecrawl_source_receipts)}
                    if live_firecrawl_docket_html
                    else {}
                ),
                "output_commitments": output_commitments,
                **({} if firecrawl_audit is None else firecrawl_audit),
            },
        )
    except (FirecrawlArtifactError, OSError, UnicodeError, ValueError) as exc:
        if (
            live_firecrawl_docket_html
            and cycle_store_path is not None
            and firecrawl_run_id is not None
        ):
            durable_summary = _firecrawl_credit_summary_if_available(
                store_path=cycle_store_path,
                run_id=firecrawl_run_id,
            )
            durable_summary.pop("schema_version", None)
            durable_run_status = durable_summary.pop("status", None)
            assert firecrawl_audit is not None
            firecrawl_audit.update(durable_summary)
            if durable_run_status is not None:
                firecrawl_audit["firecrawl_run_status"] = durable_run_status
            firecrawl_audit["firecrawl_metered_activity_executed"] = (
                _firecrawl_metered_activity_executed(
                    live=True,
                    summary=firecrawl_audit,
                )
            )
        _write_acquisition_failure(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=live_firecrawl_docket_html,
            paid_activity_executed=(
                False
                if firecrawl_audit is None
                else cast(
                    bool,
                    firecrawl_audit["firecrawl_metered_activity_executed"],
                )
            ),
            extra=firecrawl_audit,
        )
        raise CommandError(str(exc)) from exc
    return 0


def _cmd_acquisition_materialize_courtlistener_snapshot(
    args: argparse.Namespace,
) -> int:
    output_root = _acquisition_output_root(args)
    cycle_store_path = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    run_card_path = cast(Path, args.discovery_run_card)
    expected_run_card_sha256 = cast(str, args.expected_discovery_run_card_sha256)
    snapshot_root = cast(Path, args.snapshot_root)
    snapshot_id = cast(str, args.snapshot_id)
    snapshot_path = snapshot_root / snapshot_id
    summary_path = output_root / "courtlistener-snapshot-materialization-summary.json"
    input_paths = (cycle_store_path, run_card_path)
    output_paths = (snapshot_path, summary_path)
    if _acquisition_dry_run(args):
        summary: JsonRecord = {
            "schema_version": (
                "legalforecast.courtlistener_snapshot_materialization_summary.v1"
            ),
            "dry_run": True,
            "batch_id": batch_id,
            "snapshot_id": snapshot_id,
            "provider_access_requested": False,
            "paid_activity_requested": False,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="materialize-courtlistener-snapshot",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    try:
        with CycleAcquisitionStore(cycle_store_path) as store:
            cycle_hash = store.cycle_hash
            batch_digest = store.batch_digest(batch_id)
            batch_config = store.batch_config(batch_id)
            firecrawl_attempts: Sequence[FirecrawlAttempt] = ()
            firecrawl_run_summary: Mapping[str, object] | None = None
            if batch_config.get("docket_html_source") == "firecrawl":
                firecrawl_run_id = _required_str(
                    batch_config,
                    "firecrawl_run_id",
                )
                firecrawl_attempts = store.firecrawl_attempts(firecrawl_run_id)
                firecrawl_run_summary = store.firecrawl_run_summary(firecrawl_run_id)
            verified = verify_courtlistener_discovery(
                run_card_path=run_card_path,
                expected_run_card_sha256=expected_run_card_sha256,
                expected_cycle_hash=cycle_hash,
                expected_batch_id=batch_id,
                expected_batch_digest=batch_digest,
                cycle_policy=store.cycle_policy,
                batch_config=batch_config,
                firecrawl_attempts=firecrawl_attempts,
                firecrawl_run_summary=firecrawl_run_summary,
                durable_candidate_observations=(
                    store.batch_terminal_observations(batch_id)
                ),
            )
            _validate_frozen_screening_policy(
                policy=store.cycle_policy,
                anchor=verified.eligibility_anchor,
            )
            existing = store.existing_complete_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
            )
            if existing is not None:
                if not cast(bool, args.resume):
                    raise CycleAcquisitionStoreError(
                        "complete snapshot already exists and --no-resume forbids reuse"
                    )
                committed = existing[1].get("stage_commitments")
                expected_commitment = {
                    "courtlistener_discovery_inputs": dict(verified.stage_commitment)
                }
                if committed != expected_commitment:
                    raise CycleAcquisitionStoreError(
                        "existing snapshot discovery commitment does not match inputs"
                    )
                snapshot_path = existing[0]
                snapshot_manifest = verify_snapshot(
                    snapshot_path,
                    expected_cycle_hash=cycle_hash,
                    expected_batch_digest=batch_digest,
                    require_complete=True,
                    require_saturated=True,
                )
                resumed = True
            else:
                _record_courtlistener_discovery_snapshot(
                    store=store,
                    batch_id=batch_id,
                    verified=verified,
                )
                if not store.snapshot_is_saturated(
                    batch_id,
                    use_batch_terminal_observations=True,
                ):
                    raise CycleAcquisitionStoreError(
                        "verified CourtListener discovery did not saturate the store"
                    )
                snapshot_path = store.export_snapshot(
                    snapshot_root,
                    snapshot_id=snapshot_id,
                    batch_id=batch_id,
                    complete=True,
                    stage_commitments={
                        "courtlistener_discovery_inputs": dict(
                            verified.stage_commitment
                        )
                    },
                    use_batch_terminal_observations=True,
                )
                snapshot_manifest = verify_snapshot(
                    snapshot_path,
                    expected_cycle_hash=cycle_hash,
                    expected_batch_digest=batch_digest,
                    require_complete=True,
                    require_saturated=True,
                )
                resumed = False
        snapshot_summary = _read_json_object(snapshot_path / "summary.json")
        summary = {
            "schema_version": (
                "legalforecast.courtlistener_snapshot_materialization_summary.v1"
            ),
            "dry_run": False,
            "batch_id": batch_id,
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_path),
            "cycle_hash": snapshot_manifest["cycle_hash"],
            "batch_digest": snapshot_manifest["batch_digest"],
            "snapshot_complete": snapshot_manifest["complete"],
            "snapshot_saturated": snapshot_manifest["saturated"],
            "reconciled": snapshot_summary.get("reconciliation_complete") is True,
            "accepted_case_count": snapshot_summary["accepted_count"],
            "excluded_case_count": snapshot_summary["excluded_count"],
            "resumed_existing_snapshot": resumed,
            "provider_access_requested": False,
            "paid_activity_requested": False,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="materialize-courtlistener-snapshot",
            input_paths=input_paths,
            output_paths=(snapshot_path, summary_path),
            record_count=cast(int, snapshot_summary["accepted_count"]),
            dry_run=False,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
    except (
        CourtListenerSnapshotMaterializationError,
        CycleAcquisitionStoreError,
        SnapshotVerificationError,
        FileExistsError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="materialize-courtlistener-snapshot",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    return 0


def _record_courtlistener_discovery_snapshot(
    *,
    store: CycleAcquisitionStore,
    batch_id: str,
    verified: VerifiedCourtListenerDiscovery,
) -> None:
    store.ensure_terms(batch_id, verified.query_terms)
    for page in verified.search_pages:
        term = _required_str(page, "term")
        request_cursor_value = page.get("request_cursor")
        next_cursor_value = page.get("next_cursor")
        terminal_value = page.get("terminal_status")
        request_cursor = (
            request_cursor_value if isinstance(request_cursor_value, str) else None
        )
        next_cursor = next_cursor_value if isinstance(next_cursor_value, str) else None
        terminal = terminal_value if isinstance(terminal_value, str) else None
        hits_value = page.get("hits")
        assert isinstance(hits_value, list)
        hits: list[DiscoveryHit] = []
        for hit_value in cast(list[object], hits_value):
            assert isinstance(hit_value, Mapping)
            hit = cast(Mapping[str, Any], hit_value)
            payload = hit["payload"]
            assert isinstance(payload, Mapping)
            hits.append(
                DiscoveryHit(
                    provider_hit_id=_required_str(hit, "provider_hit_id"),
                    candidate_id=_required_str(hit, "candidate_id"),
                    payload=cast(Mapping[str, Any], payload),
                )
            )
        store.commit_search_page(
            batch_id,
            term,
            request_cursor,
            tuple(hits),
            next_cursor=next_cursor,
            terminal_status=terminal,
        )
    for artifact in verified.raw_artifacts:
        store.write_raw_artifact(
            artifact.candidate_id,
            artifact.path,
            artifact.content,
            retrieved_at=artifact.retrieved_at,
            validator=_validate_raw_docket_bytes,
        )
    for screened in verified.screened_cases:
        candidate_id = _courtlistener_candidate_id(screened)
        evidence = dict(screened)
        evidence["candidate_id"] = candidate_id
        _record_identical_or_new_observation(
            store=store,
            batch_id=batch_id,
            candidate_id=candidate_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence=evidence,
        )
    for exclusion in verified.exclusions:
        candidate_id = _required_str(exclusion, "candidate_id")
        evidence = dict(exclusion)
        evidence["candidate_id"] = candidate_id
        _record_identical_or_new_observation(
            store=store,
            batch_id=batch_id,
            candidate_id=candidate_id,
            state="excluded",
            reason_code=_canonical_screen_exclusion_reason(
                _required_str(exclusion, "reason")
            ),
            evidence=evidence,
        )


def _record_identical_or_new_observation(
    *,
    store: CycleAcquisitionStore,
    batch_id: str,
    candidate_id: str,
    state: str,
    reason_code: str,
    evidence: Mapping[str, object],
) -> None:
    batch_observation = store.batch_terminal_observation(batch_id, candidate_id)
    if batch_observation is not None:
        if (
            batch_observation.state == state
            and batch_observation.reason_code == reason_code
            and dict(batch_observation.evidence) == dict(evidence)
        ):
            return
        raise CycleAcquisitionStoreError(
            f"candidate {candidate_id} already has conflicting batch evidence"
        )
    current = store.current_observation(candidate_id)
    if current is not None:
        if (
            current.state == state
            and current.reason_code == reason_code
            and dict(current.evidence) == dict(evidence)
        ):
            return
        raise CycleAcquisitionStoreError(
            f"candidate {candidate_id} already has conflicting terminal evidence"
        )
    store.record_observation(
        candidate_id,
        batch_id=batch_id,
        state=state,
        reason_code=reason_code,
        evidence=evidence,
        observed_at=verified_observation_timestamp(evidence),
    )


def verified_observation_timestamp(evidence: Mapping[str, object]) -> str:
    """Return a stable source timestamp for direct-discovery observations."""

    disposition = evidence.get("first_written_mtd_disposition_date")
    if isinstance(disposition, str):
        return f"{disposition}T00:00:00Z"
    decision_date = evidence.get("decision_date")
    if isinstance(decision_date, str):
        return f"{decision_date}T00:00:00Z"
    return "1970-01-01T00:00:00Z"


def _cmd_acquisition_union_screening_snapshots(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    cycle_store_path = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    expected_cycle_hash = cast(str, args.expected_cycle_hash)
    source_snapshots = tuple(cast(Sequence[Path], args.source_snapshot))
    expected_source_hashes = tuple(
        cast(Sequence[str], args.expected_source_snapshot_manifest_sha256)
    )
    snapshot_root = cast(Path, args.snapshot_root)
    snapshot_id = cast(str, args.snapshot_id)
    snapshot_path = snapshot_root / snapshot_id
    owned_raw_dir = output_root / "union-raw-artifacts"
    owned_raw_manifest_path = output_root / "union-raw-artifacts.jsonl"
    summary_path = output_root / "screening-snapshot-union-summary.json"
    input_paths = (cycle_store_path, *source_snapshots)
    output_paths = (
        snapshot_path,
        owned_raw_dir,
        owned_raw_manifest_path,
        summary_path,
    )
    if _acquisition_dry_run(args):
        summary: JsonRecord = {
            "schema_version": "legalforecast.screening_snapshot_union_summary.v1",
            "dry_run": True,
            "source_count": len(source_snapshots),
            "provider_access_requested": False,
            "paid_activity_requested": False,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="union-screening-snapshots",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0
    try:
        union = load_screening_snapshot_union(
            source_snapshots,
            expected_manifest_sha256=expected_source_hashes,
            expected_cycle_hash=expected_cycle_hash,
        )
        batch_config = {
            "stage": "provider-free-screening-snapshot-union",
            "source_commitment": dict(union.stage_commitment),
        }
        with CycleAcquisitionStore(cycle_store_path) as store:
            if store.cycle_hash != expected_cycle_hash:
                raise CycleAcquisitionStoreError("snapshot union cycle hash mismatch")
            batch_digest = store.ensure_batch(batch_id, batch_config)
            existing = store.existing_complete_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
            )
            if existing is not None:
                if not cast(bool, args.resume):
                    raise CycleAcquisitionStoreError(
                        "complete union snapshot exists and --no-resume forbids reuse"
                    )
                owned_raw_records = _owned_raw_records_from_snapshot(existing[0])
                _write_jsonl(owned_raw_manifest_path, owned_raw_records)
                owned_raw_commitment = _file_commitment(owned_raw_manifest_path)
                expected_commitments = {
                    "screening_snapshot_union_inputs": dict(union.stage_commitment),
                    "owned_raw_artifacts": owned_raw_commitment,
                }
                if existing[1].get("stage_commitments") != expected_commitments:
                    raise CycleAcquisitionStoreError(
                        "existing union snapshot commitment does not match inputs"
                    )
                snapshot_path = existing[0]
                manifest = verify_snapshot(
                    snapshot_path,
                    expected_cycle_hash=expected_cycle_hash,
                    expected_batch_digest=batch_digest,
                    require_complete=True,
                    require_saturated=True,
                )
                resumed = True
            else:
                term = "provider-free-screening-snapshot-union"
                store.ensure_terms(batch_id, (term,))
                store.commit_search_page(
                    batch_id,
                    term,
                    None,
                    (
                        DiscoveryHit(
                            provider_hit_id=f"snapshot-union:{candidate.candidate_id}",
                            candidate_id=candidate.candidate_id,
                            payload=dict(candidate.evidence),
                        )
                        for candidate in union.candidates
                    ),
                    next_cursor=None,
                    terminal_status=TermTerminalStatus.EXHAUSTED,
                )
                owned_raw_records: list[JsonRecord] = []
                for artifact in union.raw_artifacts:
                    destination = (
                        owned_raw_dir
                        / safe_path_component(
                            artifact.candidate_id,
                            field_name="union raw-artifact candidate_id",
                        )
                        / f"{artifact.sha256}.html"
                    )
                    committed = store.write_raw_artifact(
                        artifact.candidate_id,
                        destination,
                        artifact.content,
                        retrieved_at=artifact.retrieved_at,
                        validator=_validate_raw_docket_bytes,
                    )
                    if committed.path.resolve() != destination.resolve():
                        committed = store.rehome_raw_artifact(
                            artifact.candidate_id,
                            destination,
                            artifact.content,
                            validator=_validate_raw_docket_bytes,
                        )
                    owned_raw_records.append(
                        {
                            "candidate_id": committed.candidate_id,
                            "path": str(committed.path),
                            "sha256": committed.sha256,
                            "byte_count": committed.byte_count,
                            "retrieved_at": committed.retrieved_at,
                        }
                    )
                _write_jsonl(owned_raw_manifest_path, owned_raw_records)
                owned_raw_commitment = _file_commitment(owned_raw_manifest_path)
                expected_commitments = {
                    "screening_snapshot_union_inputs": dict(union.stage_commitment),
                    "owned_raw_artifacts": owned_raw_commitment,
                }
                for candidate in union.candidates:
                    _record_identical_or_new_observation(
                        store=store,
                        batch_id=batch_id,
                        candidate_id=candidate.candidate_id,
                        state=candidate.state,
                        reason_code=candidate.reason_code,
                        evidence=candidate.evidence,
                    )
                if not store.snapshot_is_saturated(batch_id):
                    raise CycleAcquisitionStoreError(
                        "provider-free snapshot union did not saturate the store"
                    )
                snapshot_path = store.export_snapshot(
                    snapshot_root,
                    snapshot_id=snapshot_id,
                    batch_id=batch_id,
                    complete=True,
                    stage_commitments=expected_commitments,
                )
                manifest = verify_snapshot(
                    snapshot_path,
                    expected_cycle_hash=expected_cycle_hash,
                    expected_batch_digest=batch_digest,
                    require_complete=True,
                    require_saturated=True,
                )
                resumed = False
        snapshot_summary = _read_json_object(snapshot_path / "summary.json")
        summary = {
            "schema_version": "legalforecast.screening_snapshot_union_summary.v1",
            "dry_run": False,
            "source_count": len(source_snapshots),
            "candidate_count": len(union.candidates),
            "accepted_case_count": snapshot_summary["accepted_count"],
            "excluded_case_count": snapshot_summary["excluded_count"],
            "snapshot_path": str(snapshot_path),
            "snapshot_complete": manifest["complete"],
            "snapshot_saturated": manifest["saturated"],
            "reconciled": snapshot_summary.get("reconciliation_complete") is True,
            "resumed_existing_snapshot": resumed,
            "provider_access_requested": False,
            "paid_activity_requested": False,
            "output_commitments": {
                "owned_raw_artifacts": _file_commitment(owned_raw_manifest_path)
            },
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="union-screening-snapshots",
            input_paths=input_paths,
            output_paths=(
                snapshot_path,
                owned_raw_dir,
                owned_raw_manifest_path,
                summary_path,
            ),
            record_count=cast(int, snapshot_summary["accepted_count"]),
            dry_run=False,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
    except (
        ScreeningSnapshotUnionError,
        CycleAcquisitionStoreError,
        SnapshotVerificationError,
        FileExistsError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="union-screening-snapshots",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    return 0


def _owned_raw_records_from_snapshot(snapshot_path: Path) -> list[JsonRecord]:
    """Regenerate the auxiliary owned-raw manifest from immutable snapshot rows."""

    records: list[JsonRecord] = []
    for record in _read_records(snapshot_path / "raw-artifacts.jsonl"):
        byte_count = record.get("byte_count")
        if not isinstance(byte_count, int) or isinstance(byte_count, bool):
            raise CycleAcquisitionStoreError(
                "snapshot owned raw artifact has an invalid byte count"
            )
        records.append(
            {
                "candidate_id": _required_str(record, "candidate_id"),
                "path": _required_str(record, "path"),
                "sha256": _required_str(record, "sha256"),
                "byte_count": byte_count,
                "retrieved_at": _required_str(record, "retrieved_at"),
            }
        )
    return records


def _cmd_acquisition_plan_public_downloads(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    snapshot_path = cast(Path, args.snapshot)
    expected_cycle_hash = cast(str, args.expected_cycle_hash)
    canonical_screened_cases_path = snapshot_path / "screened-cases.jsonl"
    requested_screened_cases_path = cast(Path | None, args.screened_cases)
    if requested_screened_cases_path is not None and (
        requested_screened_cases_path.resolve()
        != canonical_screened_cases_path.resolve()
    ):
        raise CommandError(
            "--screened-cases must be the screened-cases.jsonl inside --snapshot"
        )
    screened_cases_path = canonical_screened_cases_path
    requested_raw_html_dir = cast(Path | None, args.raw_html_dir)
    requests_path = _acquisition_path(
        args,
        "requests_output",
        output_root / "free-document-requests.jsonl",
    )
    selection_path = _acquisition_path(
        args,
        "selection_output",
        output_root / "public-packet-selection.jsonl",
    )
    paid_gaps_path = _acquisition_path(
        args,
        "paid_gaps_output",
        output_root / "public-packet-paid-gaps.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "public-packet-exclusions.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "public-packet-plan-summary.json",
    )
    try:
        snapshot_manifest = verify_snapshot(
            snapshot_path,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        _write_acquisition_failure(
            args,
            stage="plan-public-downloads",
            input_paths=(snapshot_path,),
            output_paths=(
                requests_path,
                selection_path,
                paid_gaps_path,
                exclusions_path,
                summary_path,
            ),
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    raw_html_dir, raw_html_paths_by_candidate = _verified_snapshot_raw_html_sources(
        snapshot_path,
        requested=requested_raw_html_dir,
        use_embedded_entries=cast(bool, args.use_embedded_entries),
    )
    records = _read_records(screened_cases_path)
    dry_run = _acquisition_dry_run(args)
    plan = plan_public_packet_downloads(
        records,
        raw_html_dir=raw_html_dir,
        raw_html_paths_by_candidate=raw_html_paths_by_candidate,
        target_clean_cases=cast(int, args.target_clean_cases),
        allow_inferred_target_mtd=cast(bool, args.allow_inferred_target_mtd),
        use_embedded_entries=cast(bool, args.use_embedded_entries),
        cost_per_missing_document_usd=cast(Decimal, args.cost_per_missing_document_usd),
        max_case_mix_share=cast(Decimal | None, args.max_case_mix_share),
    )
    summary = {
        **plan.summary_record(),
        "dry_run": dry_run,
        "raw_html_dir": str(raw_html_dir) if raw_html_dir is not None else None,
        "requested_raw_html_dir": (
            str(requested_raw_html_dir) if requested_raw_html_dir is not None else None
        ),
        "raw_html_source_mode": (
            "verified_artifact_map"
            if raw_html_paths_by_candidate is not None
            else "single_directory"
            if raw_html_dir is not None
            else "embedded_entries"
        ),
        "raw_html_artifact_count": (
            len(raw_html_paths_by_candidate)
            if raw_html_paths_by_candidate is not None
            else len(_read_records(snapshot_path / "raw-artifacts.jsonl"))
        ),
        "use_embedded_entries": cast(bool, args.use_embedded_entries),
        "verified_snapshot": str(snapshot_path.resolve()),
        "cycle_hash": snapshot_manifest["cycle_hash"],
        "batch_digest": snapshot_manifest["batch_digest"],
    }
    _write_json(summary_path, summary)
    if dry_run:
        _write_jsonl(
            requests_path,
            [
                {
                    "stage": "plan-public-downloads",
                    "dry_run": True,
                    "request_count": plan.download_request_count,
                    "selected_case_count": plan.selected_case_count,
                }
            ],
        )
    else:
        _write_jsonl(
            requests_path,
            [request.to_record() for request in plan.download_requests],
        )
        _write_jsonl(
            selection_path,
            [candidate.to_record() for candidate in plan.selected_cases],
        )
        _write_jsonl(
            paid_gaps_path,
            [candidate.to_record() for candidate in plan.paid_gap_cases],
        )
        _write_jsonl(
            exclusions_path,
            [candidate.to_record() for candidate in plan.final_exclusions],
        )
    _write_acquisition_completion(
        args,
        stage="plan-public-downloads",
        input_paths=(
            (snapshot_path, screened_cases_path)
            if requested_raw_html_dir is None
            else (snapshot_path, screened_cases_path, requested_raw_html_dir)
        ),
        output_paths=(
            requests_path,
            selection_path,
            paid_gaps_path,
            exclusions_path,
            summary_path,
        ),
        record_count=len(plan.planned_cases),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "target_clean_cases": plan.target_clean_cases,
            "selected_case_count": plan.selected_case_count,
            "paid_gap_case_count": len(plan.paid_gap_cases),
            "planned_case_count": len(plan.planned_cases),
            "download_request_count": plan.download_request_count,
            "shortfall": max(0, plan.target_clean_cases - plan.selected_case_count),
        },
    )
    return 0


def _cmd_acquisition_fetch_firecrawl(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    candidates_path = cast(Path, args.candidates)
    case_dev_fixture = cast(Path | None, args.case_dev_fixture)
    firecrawl_fixture = cast(Path | None, args.firecrawl_fixture)
    raw_html_dir = _acquisition_path(
        args,
        "raw_html_dir",
        output_root / "raw-docket-html",
    )
    successes_path = _acquisition_path(
        args,
        "successes_output",
        output_root / "firecrawl-docket-successes.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "firecrawl-docket-exclusions.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "firecrawl-docket-summary.json",
    )
    max_candidates = cast(int, args.max_candidates)
    if max_candidates <= 0:
        raise CommandError("--max-candidates must be positive")
    candidate_records = _read_records(candidates_path)
    dry_run = _acquisition_dry_run(args)
    input_paths = tuple(
        path
        for path in (candidates_path, case_dev_fixture, firecrawl_fixture)
        if path is not None
    )
    output_paths = (successes_path, exclusions_path, summary_path, raw_html_dir)
    if dry_run:
        summary = {
            "dry_run": True,
            "input_candidate_count": len(candidate_records),
            "max_candidates": max_candidates,
            "scrape_count": 0,
            "paid_activity_requested": False,
        }
        _write_jsonl(successes_path, [])
        _write_jsonl(exclusions_path, [])
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="fetch-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    if cast(bool, args.resume) and successes_path.is_file():
        candidate_records = _merge_firecrawl_resume_commitments(
            candidate_records,
            _read_records(successes_path),
        )

    live_case_dev = cast(bool, args.live_case_dev)
    live_firecrawl = cast(bool, args.live_firecrawl)
    if case_dev_fixture is not None and live_case_dev:
        raise CommandError("choose --case-dev-fixture or --live-case-dev, not both")
    if firecrawl_fixture is not None and live_firecrawl:
        raise CommandError("choose --firecrawl-fixture or --live-firecrawl, not both")
    if firecrawl_fixture is None and not live_firecrawl:
        raise CommandError(
            "fetch-firecrawl-dockets requires --firecrawl-fixture or "
            "--live-firecrawl with FIRECRAWL_API_KEY configured"
        )
    try:
        client = _case_dev_client(
            command="fetch-firecrawl-dockets",
            fixture_path=case_dev_fixture,
            live=live_case_dev,
        )
        source = (
            FirecrawlCourtListenerHTMLSource(FirecrawlConfig.from_env())
            if live_firecrawl
            else FirecrawlCourtListenerHTMLSource(
                FirecrawlConfig(api_key="offline-fixture"),
                transport=_firecrawl_fixture_transport(cast(Path, firecrawl_fixture)),
            )
        )
        result = acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=candidate_records,
            raw_html_directory=raw_html_dir,
            max_candidates=max_candidates,
        )
    except CaseDevFirecrawlBatchError as exc:
        partial = exc.partial_result
        _write_jsonl(
            successes_path,
            [record.to_record() for record in partial.successes],
        )
        _write_jsonl(
            exclusions_path,
            [record.to_record() for record in partial.exclusions],
        )
        _write_json(
            summary_path,
            {
                "dry_run": False,
                "status": "blocked",
                "input_candidate_count": len(candidate_records),
                "unique_candidate_count": partial.unique_candidate_count,
                "processed_candidate_count": partial.processed_candidate_count,
                "success_count": len(partial.successes),
                "exclusion_count": len(partial.exclusions),
                "scrape_count": partial.scrape_count,
                "max_candidates": max_candidates,
                "blocker_type": type(exc.provider_error).__name__,
            },
        )
        _write_acquisition_failure(
            args,
            stage="fetch-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    except (CaseDevClientError, FirecrawlError) as exc:
        _write_acquisition_failure(
            args,
            stage="fetch-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc

    _write_jsonl(successes_path, [record.to_record() for record in result.successes])
    _write_jsonl(exclusions_path, [record.to_record() for record in result.exclusions])
    summary = {
        "dry_run": False,
        "input_candidate_count": len(candidate_records),
        "unique_candidate_count": result.unique_candidate_count,
        "processed_candidate_count": result.processed_candidate_count,
        "success_count": len(result.successes),
        "exclusion_count": len(result.exclusions),
        "scrape_count": result.scrape_count,
        "max_candidates": max_candidates,
        "firecrawl_proxy": "basic",
        "firecrawl_max_credits_per_scrape": 1,
        "paid_activity_requested": False,
    }
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="fetch-firecrawl-dockets",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(result.successes),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=summary,
    )
    return 0


def _cmd_acquisition_quarantine_snapshot(args: argparse.Namespace) -> int:
    try:
        quarantine_orphan_snapshot(
            cycle_store=cast(Path, args.cycle_store),
            orphan_snapshot=cast(Path, args.orphan_snapshot),
            quarantine_root=cast(Path, args.quarantine_root),
            receipt_output=cast(Path, args.receipt_output),
            expected_snapshot_id=cast(str, args.expected_snapshot_id),
            expected_orphan_manifest_sha256=cast(
                str, args.expected_orphan_manifest_sha256
            ),
            expected_canonical_manifest_sha256=cast(
                str, args.expected_canonical_manifest_sha256
            ),
            execute=cast(bool, args.execute),
        )
    except (OSError, SnapshotQuarantineError) as error:
        raise CommandError(str(error)) from error
    return 0


def _cmd_acquisition_screen_firecrawl(args: argparse.Namespace) -> int:
    output_root = cast(Path, args.output_root)
    cycle_store_path = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    successes_path = cast(Path, args.successes)
    fetch_exclusions_path = cast(Path, args.fetch_exclusions)
    raw_html_dir = cast(Path, args.raw_html_dir)
    snapshot_root = _acquisition_path(
        args,
        "snapshot_root",
        output_root / "snapshots",
    )
    snapshot_id = cast(str, args.snapshot_id)
    snapshot_path = snapshot_root / snapshot_id
    screened_cases_path = _acquisition_path(
        args,
        "screened_cases_output",
        output_root / "firecrawl-screened-cases.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "firecrawl-screening-exclusions.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "firecrawl-screening-summary.json",
    )
    anchor = _iso_date_argument(
        cast(str, args.decision_filed_on_or_after),
        "--decision-filed-on-or-after",
    )
    success_records = _read_records(successes_path)
    fetch_exclusion_records = _read_records(fetch_exclusions_path)
    dry_run = _acquisition_dry_run(args)
    input_paths = (
        cycle_store_path,
        successes_path,
        fetch_exclusions_path,
        raw_html_dir,
    )
    output_paths = (
        screened_cases_path,
        exclusions_path,
        summary_path,
        snapshot_path,
    )
    _validate_screen_resume_output_paths(
        args=args,
        snapshot_path=snapshot_path,
        output_root=output_root,
        screened_cases_path=screened_cases_path,
        exclusions_path=exclusions_path,
        summary_path=summary_path,
    )
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.firecrawl_screening_summary.v1",
            "dry_run": True,
            "anchor_date": anchor.isoformat(),
            "input_success_count": len(success_records),
            "input_fetch_exclusion_count": len(fetch_exclusion_records),
            "accepted_case_count": 0,
            "excluded_case_count": 0,
            "reconciled": False,
            "paid_activity_requested": False,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="screen-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=0,
            dry_run=True,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    try:
        _validate_firecrawl_success_commitments(success_records)
        input_commitments = firecrawl_screen_input_commitments(
            success_records=success_records,
            fetch_exclusion_records=fetch_exclusion_records,
        )
        with CycleAcquisitionStore(cycle_store_path) as store:
            _validate_frozen_screening_policy(
                policy=store.cycle_policy,
                anchor=anchor,
            )
            existing_snapshot = store.existing_complete_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
            )
    except (
        CycleAcquisitionStoreError,
        SnapshotVerificationError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="screen-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    if existing_snapshot is not None:
        snapshot_path, snapshot_manifest = existing_snapshot
        resumed_output_paths = (*output_paths[:-1], snapshot_path)
        _validate_screen_resume_output_paths(
            args=args,
            snapshot_path=snapshot_path,
            output_root=output_root,
            screened_cases_path=screened_cases_path,
            exclusions_path=exclusions_path,
            summary_path=summary_path,
        )
        if not cast(bool, args.resume):
            exc = FileExistsError(
                "complete snapshot already exists and --no-resume forbids reuse: "
                f"{existing_snapshot[0]}"
            )
            _write_acquisition_failure(
                args,
                stage="screen-firecrawl-dockets",
                input_paths=input_paths,
                output_paths=output_paths,
                reason=str(exc),
                paid_activity_requested=False,
            )
            raise CommandError(str(exc)) from exc
        try:
            _validate_firecrawl_snapshot_resume_inputs(
                success_records=success_records,
                fetch_exclusion_records=fetch_exclusion_records,
                input_commitments=input_commitments,
                raw_html_directory=raw_html_dir,
                snapshot_path=snapshot_path,
                snapshot_manifest=snapshot_manifest,
            )
        except (CycleAcquisitionStoreError, KeyError, OSError, ValueError) as exc:
            _write_acquisition_failure(
                args,
                stage="screen-firecrawl-dockets",
                input_paths=input_paths,
                output_paths=output_paths,
                reason=str(exc),
                paid_activity_requested=False,
            )
            raise CommandError(str(exc)) from exc
        screened_cases = _read_records(snapshot_path / "screened-cases.jsonl")
        all_exclusions = _read_records(snapshot_path / "exclusions.jsonl")
        snapshot_summary = _read_json_object(snapshot_path / "summary.json")
        _write_jsonl(screened_cases_path, screened_cases)
        _write_jsonl(exclusions_path, all_exclusions)
        summary = {
            "schema_version": "legalforecast.firecrawl_screening_summary.v1",
            "dry_run": False,
            "anchor_date": anchor.isoformat(),
            "input_success_count": len(success_records),
            "input_fetch_exclusion_count": len(fetch_exclusion_records),
            "accepted_case_count": len(screened_cases),
            "excluded_case_count": len(all_exclusions),
            "reconciled": snapshot_summary.get("reconciliation_complete") is True,
            "paid_activity_requested": False,
            "snapshot_path": str(snapshot_path),
            "cycle_hash": snapshot_manifest["cycle_hash"],
            "batch_digest": snapshot_manifest["batch_digest"],
            "snapshot_complete": snapshot_manifest["complete"],
            "snapshot_saturated": snapshot_manifest["saturated"],
            "resumed_existing_snapshot": True,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="screen-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=resumed_output_paths,
            record_count=len(screened_cases),
            dry_run=False,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0

    try:
        with CycleAcquisitionStore(cycle_store_path) as store:
            batch_digest = store.batch_digest(batch_id)
            cycle_hash = store.cycle_hash
            _validate_frozen_screening_policy(
                policy=store.cycle_policy,
                anchor=anchor,
            )
            result = screen_case_dev_firecrawl_successes(
                successes=success_records,
                raw_html_directory=raw_html_dir,
                decision_filed_on_or_after=anchor,
            )
            rescreen_metadata_by_candidate = _rescreen_metadata_by_candidate(
                success_records
            )
            for record in success_records:
                candidate_id = _required_str(record, "case_id")
                docket_id = _required_str(record, "docket_id")
                if not docket_id.isdigit():
                    continue
                raw_path = raw_html_dir / f"{docket_id}.html"
                if not raw_path.is_file():
                    continue
                raw_bytes = raw_path.read_bytes()
                expected_bytes = cast(int, record["raw_html_bytes"])
                expected_sha256 = cast(str, record["raw_html_sha256"])
                actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                if expected_bytes != len(raw_bytes):
                    raise CycleAcquisitionStoreError(
                        f"Firecrawl byte-count commitment mismatch for {candidate_id}"
                    )
                if expected_sha256 != f"sha256:{actual_sha256}":
                    raise CycleAcquisitionStoreError(
                        f"Firecrawl SHA-256 commitment mismatch for {candidate_id}"
                    )
                retrieved_at = cast(str, record["retrieved_at"])
                store.write_raw_artifact(
                    candidate_id,
                    raw_path,
                    raw_bytes,
                    retrieved_at=retrieved_at,
                    validator=_validate_raw_docket_bytes,
                )

            for screened in result.screened_cases:
                candidate_id = _screened_case_dev_id(screened)
                evidence = dict(screened)
                evidence["candidate_id"] = candidate_id
                store.record_observation(
                    candidate_id,
                    batch_id=batch_id,
                    state="accepted",
                    reason_code="strict_clean_screen_passed",
                    evidence=evidence,
                    metadata_repair_evidence=rescreen_metadata_by_candidate[
                        candidate_id
                    ],
                )
            for exclusion in result.exclusions:
                evidence = exclusion.to_record()
                candidate_id = exclusion.case_id
                evidence["candidate_id"] = candidate_id
                reason_code = _canonical_screen_exclusion_reason(exclusion.reason)
                store.record_observation(
                    candidate_id,
                    batch_id=batch_id,
                    state="excluded",
                    reason_code=reason_code,
                    evidence=evidence,
                    metadata_repair_evidence=rescreen_metadata_by_candidate[
                        candidate_id
                    ],
                )
            for exclusion in fetch_exclusion_records:
                _record_fetch_exclusion(
                    store,
                    batch_id=batch_id,
                    record=exclusion,
                )

            snapshot_path = store.export_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
                complete=True,
                stage_commitments={
                    "firecrawl_screen_inputs": input_commitments,
                },
            )
            snapshot_manifest = verify_snapshot(
                snapshot_path,
                expected_cycle_hash=cycle_hash,
                expected_batch_digest=batch_digest,
                require_complete=True,
            )
    except (
        CycleAcquisitionStoreError,
        SnapshotVerificationError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="screen-firecrawl-dockets",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    _write_jsonl(screened_cases_path, result.screened_cases)
    screening_exclusions = [exclusion.to_record() for exclusion in result.exclusions]
    all_exclusions = [*fetch_exclusion_records, *screening_exclusions]
    _write_jsonl(exclusions_path, all_exclusions)
    summary = {
        "schema_version": "legalforecast.firecrawl_screening_summary.v1",
        "dry_run": False,
        "anchor_date": anchor.isoformat(),
        "input_success_count": result.input_success_count,
        "input_fetch_exclusion_count": len(fetch_exclusion_records),
        "accepted_case_count": len(result.screened_cases),
        "excluded_case_count": len(all_exclusions),
        "reconciled": result.reconciled,
        "paid_activity_requested": False,
        "snapshot_path": str(snapshot_path),
        "cycle_hash": snapshot_manifest["cycle_hash"],
        "batch_digest": snapshot_manifest["batch_digest"],
        "snapshot_complete": snapshot_manifest["complete"],
        "snapshot_saturated": snapshot_manifest["saturated"],
    }
    _write_json(summary_path, summary)
    _write_acquisition_completion(
        args,
        stage="screen-firecrawl-dockets",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(result.screened_cases),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra=summary,
    )
    return 0


def _cmd_acquisition_replay_screening_snapshots(args: argparse.Namespace) -> int:
    """Re-screen cryptographically bound snapshots without provider activity."""

    output_root = cast(Path, args.output_root)
    cycle_store_path = cast(Path, args.cycle_store)
    batch_id = cast(str, args.batch_id)
    source_assembly_run_card = cast(Path, args.source_assembly_run_card)
    additional_source_snapshots = tuple(cast(Sequence[Path], args.source_snapshot))
    additional_source_cycle_hashes = tuple(
        cast(Sequence[str], args.expected_source_snapshot_cycle_hash)
    )
    additional_source_screen_run_cards = tuple(
        cast(Sequence[Path], args.source_snapshot_screen_run_card)
    )
    additional_source_screen_run_card_hashes = tuple(
        cast(Sequence[str], args.expected_source_snapshot_screen_run_card_sha256)
    )
    additional_source_bundle_roots = tuple(
        cast(Sequence[Path], args.source_snapshot_bundle_root)
    )
    snapshot_root = _acquisition_path(
        args,
        "snapshot_root",
        output_root / "snapshots",
    )
    snapshot_id = cast(str, args.snapshot_id)
    snapshot_path = snapshot_root / snapshot_id
    raw_html_dir = output_root / "raw-docket-html" / snapshot_id
    screened_cases_path = _acquisition_path(
        args,
        "screened_cases_output",
        output_root / "replay-screened-cases.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "replay-screening-exclusions.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "replay-screening-summary.json",
    )
    anchor = _iso_date_argument(
        cast(str, args.decision_filed_on_or_after),
        "--decision-filed-on-or-after",
    )
    expected_source_assembly_sha256 = cast(str, args.expected_source_assembly_sha256)
    expected_source_closure_sha256 = cast(str, args.expected_source_closure_sha256)
    expected_source_cycle_hash = cast(str, args.expected_source_cycle_hash)
    expected_legacy_screen_inputs_sha256 = cast(
        str | None, args.expected_legacy_screen_inputs_sha256
    )
    expected_target_cycle_hash = cast(str, args.expected_target_cycle_hash)
    input_paths = (
        cycle_store_path,
        source_assembly_run_card,
        *additional_source_snapshots,
        *additional_source_screen_run_cards,
        *additional_source_bundle_roots,
    )
    output_paths = (
        screened_cases_path,
        exclusions_path,
        summary_path,
        raw_html_dir,
        snapshot_path,
    )
    _validate_replay_output_paths(
        args=args,
        snapshot_path=snapshot_path,
        screened_cases_path=screened_cases_path,
        exclusions_path=exclusions_path,
        summary_path=summary_path,
        raw_html_dir=raw_html_dir,
        cycle_store_path=cycle_store_path,
    )
    provider_flags: JsonRecord = {
        "provider_activity_requested": False,
        "provider_activity_executed": False,
    }

    try:
        supplemental_counts = {
            len(additional_source_snapshots),
            len(additional_source_cycle_hashes),
            len(additional_source_screen_run_cards),
            len(additional_source_screen_run_card_hashes),
            len(additional_source_bundle_roots),
        }
        if len(supplemental_counts) != 1:
            raise SnapshotReplayError(
                "each --source-snapshot requires exactly one cycle hash, screen "
                "run card, screen run-card SHA-256, and bundle root"
            )
        bundle = collect_snapshot_replay_bundle(
            source_assembly_run_card=source_assembly_run_card,
            expected_source_assembly_sha256=expected_source_assembly_sha256,
            expected_source_closure_sha256=expected_source_closure_sha256,
            expected_source_cycle_hash=expected_source_cycle_hash,
            expected_legacy_screen_inputs_sha256=(expected_legacy_screen_inputs_sha256),
            additional_source_snapshots=tuple(
                SupplementalReplaySource(
                    snapshot=snapshot,
                    expected_cycle_hash=cycle_hash,
                    screen_run_card=screen_run_card,
                    expected_screen_run_card_sha256=screen_run_card_sha256,
                    bundle_root=bundle_root,
                )
                for (
                    snapshot,
                    cycle_hash,
                    screen_run_card,
                    screen_run_card_sha256,
                    bundle_root,
                ) in zip(
                    additional_source_snapshots,
                    additional_source_cycle_hashes,
                    additional_source_screen_run_cards,
                    additional_source_screen_run_card_hashes,
                    additional_source_bundle_roots,
                    strict=True,
                )
            ),
        )
    except (SnapshotReplayError, SnapshotVerificationError, OSError, ValueError) as exc:
        raise CommandError(str(exc)) from exc

    _validate_replay_output_paths(
        args=args,
        snapshot_path=snapshot_path,
        screened_cases_path=screened_cases_path,
        exclusions_path=exclusions_path,
        summary_path=summary_path,
        raw_html_dir=raw_html_dir,
        cycle_store_path=cycle_store_path,
        source_bundle=bundle,
    )

    try:
        success_records = [dict(success.record) for success in bundle.successes]
        fetch_exclusion_records = [
            dict(exclusion.record) for exclusion in bundle.exclusions
        ]
        _validate_firecrawl_success_commitments(success_records)
        with CycleAcquisitionStore(cycle_store_path) as store:
            if store.cycle_hash != expected_target_cycle_hash:
                raise CycleAcquisitionStoreError(
                    "target cycle hash mismatch: "
                    f"expected {expected_target_cycle_hash}, got {store.cycle_hash}"
                )
            _validate_frozen_screening_policy(
                policy=store.cycle_policy,
                anchor=anchor,
            )

        if _acquisition_dry_run(args):
            summary: JsonRecord = {
                "schema_version": "legalforecast.snapshot_replay_summary.v1",
                "dry_run": True,
                "anchor_date": anchor.isoformat(),
                "source_snapshot_count": len(bundle.sources),
                "source_candidate_count": bundle.candidate_count,
                "source_success_count": len(bundle.successes),
                "source_fetch_exclusion_count": len(bundle.exclusions),
                "accepted_case_count": 0,
                "excluded_case_count": 0,
                "reconciled": False,
                **provider_flags,
            }
            _write_json(summary_path, summary)
            _write_acquisition_completion(
                args,
                stage="replay-screening-snapshots",
                input_paths=input_paths,
                output_paths=output_paths,
                record_count=0,
                dry_run=True,
                paid_activity_requested=False,
                paid_activity_executed=False,
                extra=summary,
            )
            return 0

        if snapshot_path.exists():
            raise FileExistsError(
                "target replay snapshot already exists; immutable replay outputs "
                f"cannot be overwritten: {snapshot_path}"
            )
        commitment = source_replay_commitment(bundle)
        with CycleAcquisitionStore(cycle_store_path) as store:
            batch_digest = store.ensure_batch(
                batch_id,
                {
                    "stage": "provider-free-source-bound-snapshot-replay",
                    "anchor_date": anchor.isoformat(),
                    "source_bound_replay": commitment,
                },
            )
            cycle_hash = store.cycle_hash
            store.ensure_terms(batch_id, ("source-bound-snapshot-replay",))
            store.commit_search_page(
                batch_id,
                "source-bound-snapshot-replay",
                None,
                (
                    DiscoveryHit(
                        provider_hit_id=f"source-replay:{candidate_id}",
                        candidate_id=candidate_id,
                        payload=dict(record),
                    )
                    for candidate_id, record in (
                        *(
                            (success.candidate_id, success.record)
                            for success in bundle.successes
                        ),
                        *(
                            (exclusion.candidate_id, exclusion.record)
                            for exclusion in bundle.exclusions
                        ),
                    )
                ),
                next_cursor=None,
                terminal_status=TermTerminalStatus.EXHAUSTED,
            )
            for success in bundle.successes:
                destination = raw_html_dir / f"{success.docket_id}.html"
                store.write_raw_artifact(
                    success.candidate_id,
                    destination,
                    read_verified_replay_raw(success),
                    retrieved_at=_required_str(success.record, "retrieved_at"),
                    validator=_validate_raw_docket_bytes,
                )
            result = screen_case_dev_firecrawl_successes(
                successes=success_records,
                raw_html_directory=raw_html_dir,
                decision_filed_on_or_after=anchor,
            )
            rescreen_metadata_by_candidate = _rescreen_metadata_by_candidate(
                success_records
            )
            for screened in result.screened_cases:
                candidate_id = _screened_case_dev_id(screened)
                evidence = dict(screened)
                evidence["candidate_id"] = candidate_id
                store.record_observation(
                    candidate_id,
                    batch_id=batch_id,
                    state="accepted",
                    reason_code="strict_clean_screen_passed",
                    evidence=evidence,
                    metadata_repair_evidence=rescreen_metadata_by_candidate[
                        candidate_id
                    ],
                )
            for exclusion in result.exclusions:
                evidence = exclusion.to_record()
                candidate_id = exclusion.case_id
                evidence["candidate_id"] = candidate_id
                store.record_observation(
                    candidate_id,
                    batch_id=batch_id,
                    state="excluded",
                    reason_code=_canonical_screen_exclusion_reason(exclusion.reason),
                    evidence=evidence,
                    metadata_repair_evidence=rescreen_metadata_by_candidate[
                        candidate_id
                    ],
                )
            for exclusion in fetch_exclusion_records:
                _record_fetch_exclusion(store, batch_id=batch_id, record=exclusion)
            snapshot_path = store.export_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
                complete=True,
                stage_commitments={"source_bound_replay": commitment},
            )
            snapshot_manifest = verify_snapshot(
                snapshot_path,
                expected_cycle_hash=cycle_hash,
                expected_batch_digest=batch_digest,
                require_complete=True,
                require_saturated=True,
            )
        screened_cases = _read_records(snapshot_path / "screened-cases.jsonl")
        all_exclusions = _read_records(snapshot_path / "exclusions.jsonl")
        snapshot_summary = _read_json_object(snapshot_path / "summary.json")
        _write_jsonl(screened_cases_path, screened_cases)
        _write_jsonl(exclusions_path, all_exclusions)
        summary = {
            "schema_version": "legalforecast.snapshot_replay_summary.v1",
            "dry_run": False,
            "anchor_date": anchor.isoformat(),
            "source_snapshot_count": len(bundle.sources),
            "source_candidate_count": bundle.candidate_count,
            "source_success_count": len(bundle.successes),
            "source_fetch_exclusion_count": len(bundle.exclusions),
            "accepted_case_count": len(screened_cases),
            "excluded_case_count": len(all_exclusions),
            "reconciled": snapshot_summary.get("reconciliation_complete") is True,
            "snapshot_path": str(snapshot_path),
            "cycle_hash": snapshot_manifest["cycle_hash"],
            "batch_digest": snapshot_manifest["batch_digest"],
            "snapshot_complete": snapshot_manifest["complete"],
            "snapshot_saturated": snapshot_manifest["saturated"],
            **provider_flags,
        }
        _write_json(summary_path, summary)
        _write_acquisition_completion(
            args,
            stage="replay-screening-snapshots",
            input_paths=input_paths,
            output_paths=output_paths,
            record_count=len(screened_cases),
            dry_run=False,
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=summary,
        )
        return 0
    except (
        CycleAcquisitionStoreError,
        SnapshotReplayError,
        SnapshotVerificationError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
        RuntimeError,
    ) as exc:
        _write_acquisition_failure(
            args,
            stage="replay-screening-snapshots",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
            paid_activity_executed=False,
            extra=provider_flags,
        )
        raise CommandError(str(exc)) from exc


_PACER_GAP_MAX_RESUMABLE_ATTEMPTS = 3
_PACER_GAP_LEGACY_CHECKPOINT_SCHEMA = (
    "legalforecast.pacer_gap_bridge_candidate_checkpoint.v1"
)
_PACER_GAP_CHECKPOINT_SCHEMA = "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2"
_PACER_GAP_LEGACY_PROGRESS_CONFIG_SCHEMA = (
    "legalforecast.pacer_gap_bridge_progress_config.v1"
)
_PACER_GAP_PROGRESS_CONFIG_SCHEMA = "legalforecast.pacer_gap_bridge_progress_config.v2"


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _bridge_candidate_id(record: Mapping[str, Any]) -> str:
    candidate = _mapping(record.get("candidate"), "candidate")
    for field_name in ("docket_id", "candidate_key"):
        candidate_id = _optional_str(candidate, field_name)
        if candidate_id is not None:
            return candidate_id
    raise CommandError("candidate docket_id or candidate_key is required")


def _bridge_source_commitments(
    *,
    screened_records: Sequence[Mapping[str, Any]],
    routed_candidate_ids: Sequence[str],
    raw_html_dir: Path | None,
    use_embedded_entries: bool,
) -> list[JsonRecord]:
    screened_by_id = {
        _bridge_candidate_id(record): record for record in screened_records
    }
    if len(screened_by_id) != len(screened_records):
        raise CommandError("screened cases repeat a candidate identity")
    commitments: list[JsonRecord] = []
    for candidate_id in routed_candidate_ids:
        record = screened_by_id.get(candidate_id)
        if record is None:
            raise CommandError(
                f"public plan candidate is missing from screened cases: {candidate_id}"
            )
        raw_path = (
            None if raw_html_dir is None else raw_html_dir / f"{candidate_id}.html"
        )
        if raw_path is not None and raw_path.is_file():
            commitments.append(
                {
                    "candidate_id": candidate_id,
                    "source": "raw_html",
                    "sha256": "sha256:"
                    + hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                }
            )
            continue
        if not use_embedded_entries:
            raise CommandError(
                f"raw CourtListener HTML is missing for candidate {candidate_id}"
            )
        selected_entries = record.get("selected_entries")
        if (
            isinstance(selected_entries, (str, bytes))
            or not isinstance(selected_entries, Sequence)
            or not selected_entries
        ):
            raise CommandError(
                "selected_entries must be a non-empty list of records for "
                f"candidate {candidate_id}"
            )
        selected_entry_records = cast(Sequence[object], selected_entries)
        if any(not isinstance(entry, Mapping) for entry in selected_entry_records):
            raise CommandError(
                "selected_entries must be a non-empty list of records for "
                f"candidate {candidate_id}"
            )
        commitments.append(
            {
                "candidate_id": candidate_id,
                "source": "embedded_entries",
                "sha256": _canonical_json_sha256(selected_entry_records),
            }
        )
    return commitments


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(dict(payload), handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _bridge_checkpoint_path(
    checkpoint_dir: Path,
    *,
    input_index: int,
    candidate_id: str,
) -> Path:
    identity = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    return checkpoint_dir / f"{input_index:06d}-{identity}.json"


def _validate_bridge_checkpoint(
    checkpoint: JsonRecord,
    *,
    input_index: int,
    candidate_id: str,
    candidate_input_sha256: str,
) -> None:
    outcome = checkpoint.get("outcome")
    attempt_count = checkpoint.get("resumable_attempt_count")
    if (
        checkpoint.get("schema_version")
        not in {_PACER_GAP_LEGACY_CHECKPOINT_SCHEMA, _PACER_GAP_CHECKPOINT_SCHEMA}
        or checkpoint.get("input_index") != input_index
        or checkpoint.get("candidate_id") != candidate_id
        or checkpoint.get("candidate_input_sha256") != candidate_input_sha256
        or outcome not in {"success", "exclusion", "retryable"}
        or type(attempt_count) is not int
        or attempt_count < 1
        or attempt_count > _PACER_GAP_MAX_RESUMABLE_ATTEMPTS
        or not _bridge_checkpoint_payload_matches_candidate(
            checkpoint.get("payload"),
            outcome=outcome,
            candidate_id=candidate_id,
        )
    ):
        raise CommandError(f"PACER-gap bridge checkpoint is invalid for {candidate_id}")
    if outcome == "retryable" and attempt_count >= _PACER_GAP_MAX_RESUMABLE_ATTEMPTS:
        raise CommandError(
            f"PACER-gap bridge retryable checkpoint is exhausted for {candidate_id}"
        )


def _normalize_bridge_checkpoint(checkpoint: JsonRecord) -> JsonRecord:
    """Upgrade a verified v1 checkpoint without repeating provider requests."""

    schema = checkpoint.get("schema_version")
    candidate_id = _required_str(checkpoint, "candidate_id")
    normalized: JsonRecord = {
        **checkpoint,
        "schema_version": _PACER_GAP_CHECKPOINT_SCHEMA,
    }
    if checkpoint.get("outcome") != "success":
        return normalized

    payload = _mapping(checkpoint.get("payload"), "payload")
    selection = _mapping(payload.get("selection_record"), "selection_record")
    relevance = _mapping(payload.get("case_relevance_record"), "case_relevance_record")
    selection_documents = _mapping_sequence_for_bridge_normalization(
        selection.get("documents"), candidate_id=candidate_id, source="selection"
    )
    relevance_documents = _mapping_sequence_for_bridge_normalization(
        relevance.get("documents"), candidate_id=candidate_id, source="case_relevance"
    )

    def pending_ids(documents: Sequence[Mapping[str, Any]]) -> set[str]:
        return {
            _required_str(document, "source_document_id")
            for document in documents
            if document.get("requires_paid_recovery") is True
            and document.get("availability_status") == "unavailable"
        }

    def recovered_free_ids(documents: Sequence[Mapping[str, Any]]) -> set[str]:
        return {
            _required_str(document, "source_document_id")
            for document in documents
            if document.get("resolved_from_paid_gap") is True
            and document.get("requires_paid_recovery") is False
            and document.get("availability_status") == "available"
        }

    selection_pending = pending_ids(selection_documents)
    relevance_pending = pending_ids(relevance_documents)
    selection_free = recovered_free_ids(selection_documents)
    relevance_free = recovered_free_ids(relevance_documents)
    request_records = _optional_record_sequence(payload, "free_download_requests")
    try:
        derived_request_records = tuple(
            request.to_record()
            for request in bridge_free_download_requests_from_selection(selection)
        )
    except CourtListenerCaseDevBridgeError as exc:
        raise CommandError(
            f"PACER-gap free recovery checkpoint is invalid for {candidate_id}: {exc}"
        ) from exc
    if tuple(dict(record) for record in request_records) != derived_request_records:
        raise CommandError(
            f"PACER-gap free recovery request drifted for {candidate_id}"
        )
    request_ids = {
        _required_str(record, "source_document_id") for record in request_records
    }
    selection_free_by_id = {
        _required_str(document, "source_document_id"): document
        for document in selection_documents
        if _required_str(document, "source_document_id") in selection_free
    }
    relevance_free_by_id = {
        _required_str(document, "source_document_id"): document
        for document in relevance_documents
        if _required_str(document, "source_document_id") in relevance_free
    }
    shared_free_fields = (
        "candidate_id",
        "source_document_id",
        "document_role",
        "docket_entry_number",
        "availability_status",
        "requires_paid_recovery",
        "redaction_or_seal_status",
        "restriction_evidence",
        "is_private",
        "is_sealed",
        "contains_target_outcome",
        "model_visible",
        "resolved_from_paid_gap",
        "source_url_or_reference",
    )
    free_bindings_match = all(
        all(
            selection_free_by_id[source_document_id].get(field_name)
            == relevance_free_by_id[source_document_id].get(field_name)
            for field_name in shared_free_fields
        )
        for source_document_id in selection_free & relevance_free
    )
    resolved_reasons = selection.get("resolved_paid_gap_reasons")
    shared_evidence_is_valid = (
        selection.get("selected") is True
        and isinstance(selection.get("identity_resolution"), Mapping)
        and selection.get("paid_gap_reasons") == []
        and _is_nonempty_string_list(resolved_reasons)
        and bool(selection_pending or selection_free)
        and selection_pending == relevance_pending
        and selection_free == relevance_free
        and selection_free == request_ids
        and free_bindings_match
    )
    if schema == _PACER_GAP_CHECKPOINT_SCHEMA:
        paid_status_valid = bool(selection_pending) and (
            selection.get("paid_recovery_required") is True
            and selection.get("planning_status")
            == "identity_resolved_paid_recovery_required"
            and selection.get("document_recovery_status") == "paid_recovery_required"
        )
        free_status_valid = (
            not selection_pending
            and bool(selection_free)
            and (
                selection.get("paid_recovery_required") is False
                and selection.get("planning_status") == "free_recovery_required"
                and selection.get("document_recovery_status")
                == "free_recovery_required"
            )
        )
        if (
            not shared_evidence_is_valid
            or selection.get("identity_resolution_status") != "resolved"
            or not (paid_status_valid or free_status_valid)
        ):
            raise CommandError(
                f"PACER-gap v2 success checkpoint is ambiguous for {candidate_id}"
            )
        return checkpoint
    if (
        not shared_evidence_is_valid
        or selection.get("paid_recovery_required") is not False
        or selection.get("planning_status") != "selected_after_paid_recovery"
    ):
        raise CommandError(
            f"legacy PACER-gap success checkpoint is ambiguous for {candidate_id}"
        )
    normalized_selection = {
        **selection,
        "paid_recovery_required": True,
        "planning_status": "identity_resolved_paid_recovery_required",
        "identity_resolution_status": "resolved",
        "document_recovery_status": "paid_recovery_required",
    }
    normalized["payload"] = {
        **payload,
        "selection_record": normalized_selection,
        "case_relevance_record": relevance,
    }
    return normalized


def _mapping_sequence_for_bridge_normalization(
    value: object,
    *,
    candidate_id: str,
    source: str,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise CommandError(
            f"legacy PACER-gap success checkpoint has malformed {source} documents "
            f"for {candidate_id}"
        )
    items = cast(list[object], value)
    if not items or not all(isinstance(item, Mapping) for item in items):
        raise CommandError(
            f"legacy PACER-gap success checkpoint has malformed {source} documents "
            f"for {candidate_id}"
        )
    return tuple(cast(Mapping[str, Any], item) for item in items)


def _is_nonempty_string_list(value: object) -> bool:
    if not isinstance(value, list):
        return False
    values = cast(list[object], value)
    return bool(values) and all(isinstance(item, str) and bool(item) for item in values)


def _bridge_progress_config_matches(existing: JsonRecord, current: JsonRecord) -> bool:
    schema = existing.get("schema_version")
    if schema not in {
        _PACER_GAP_LEGACY_PROGRESS_CONFIG_SCHEMA,
        _PACER_GAP_PROGRESS_CONFIG_SCHEMA,
    }:
        return False
    return {**existing, "schema_version": _PACER_GAP_PROGRESS_CONFIG_SCHEMA} == current


def _bridge_checkpoint_payload_matches_candidate(
    payload: object,
    *,
    outcome: object,
    candidate_id: str,
) -> bool:
    if not isinstance(payload, Mapping):
        return False
    payload_record = cast(Mapping[str, object], payload)
    if outcome == "retryable":
        return True
    field_names = (
        ("selection_record", "case_relevance_record")
        if outcome == "success"
        else ("exclusion_record",)
    )
    for field_name in field_names:
        record = payload_record.get(field_name)
        if (
            not isinstance(record, Mapping)
            or cast(Mapping[str, object], record).get("candidate_id") != candidate_id
        ):
            return False
    free_requests = payload_record.get("free_download_requests", [])
    if not isinstance(free_requests, list):
        return False
    for request in cast(list[object], free_requests):
        if (
            not isinstance(request, Mapping)
            or cast(Mapping[str, object], request).get("candidate_id") != candidate_id
        ):
            return False
    return True


def _bridge_checkpoint_requires_semantic_replay(
    checkpoint: Mapping[str, Any], *, bridge_provider: str
) -> bool:
    """Replay exclusions made terminal by superseded bridge semantics."""

    if (
        bridge_provider != "courtlistener_rest"
        or checkpoint.get("outcome") != "exclusion"
    ):
        return False
    payload = checkpoint.get("payload")
    if not isinstance(payload, Mapping):
        return False
    payload_record = cast(Mapping[str, object], payload)
    exclusion = payload_record.get("exclusion_record")
    if not isinstance(exclusion, Mapping):
        return False
    exclusion_record = cast(Mapping[str, object], exclusion)
    reasons = exclusion_record.get("exclusion_reasons")
    return (
        isinstance(reasons, list) and "courtlistener_recap_already_available" in reasons
    )


def _public_first_bridge_with_checkpoints(
    *,
    args: argparse.Namespace,
    records: Sequence[Mapping[str, Any]],
    client: CaseDevClient | CourtListenerClient,
    bridge_provider: str,
    raw_html_dir: Path | None,
    public_selection_path: Path,
    paid_gaps_path: Path,
    free_download_manifest_path: Path,
    fixture_path: Path | None,
    checkpoint_dir: Path,
    checkpoint_config_path: Path,
) -> tuple[CourtListenerCaseDevBridgeResult | None, JsonRecord]:
    public_selections = _read_records(public_selection_path)
    paid_gaps = _read_records(paid_gaps_path)
    free_downloads = _read_records(free_download_manifest_path)
    validate_public_plan_bridge_inputs(
        public_selection_records=public_selections,
        paid_gap_records=paid_gaps,
        free_download_records=free_downloads,
    )
    public_ids = [_required_str(record, "candidate_id") for record in public_selections]
    gap_ids = [_required_str(record, "candidate_id") for record in paid_gaps]
    routed_ids = [*public_ids, *gap_ids]
    if len(set(routed_ids)) != len(routed_ids):
        raise CommandError("public selection and paid gaps repeat a candidate route")
    source_commitments = _bridge_source_commitments(
        screened_records=records,
        routed_candidate_ids=routed_ids,
        raw_html_dir=raw_html_dir,
        use_embedded_entries=cast(bool, args.use_embedded_entries),
    )
    if bridge_provider not in {"case.dev", "courtlistener_rest"}:
        raise CommandError("unsupported paid-gap bridge provider")
    config: JsonRecord = {
        "schema_version": _PACER_GAP_PROGRESS_CONFIG_SCHEMA,
        "mode": "public_first",
        "screened_cases_sha256": "sha256:"
        + hashlib.sha256(cast(Path, args.screened_cases).read_bytes()).hexdigest(),
        "public_selection_sha256": "sha256:"
        + hashlib.sha256(public_selection_path.read_bytes()).hexdigest(),
        "paid_gaps_sha256": "sha256:"
        + hashlib.sha256(paid_gaps_path.read_bytes()).hexdigest(),
        "free_download_manifest_sha256": "sha256:"
        + hashlib.sha256(free_download_manifest_path.read_bytes()).hexdigest(),
        "screened_case_count": len(records),
        "public_selection_count": len(public_selections),
        "paid_gap_count": len(paid_gaps),
        "use_embedded_entries": cast(bool, args.use_embedded_entries),
        "transport_mode": "fixture" if fixture_path is not None else "live",
        "source_commitments": source_commitments,
        "free_lookup_only": True,
        "pacer_fee_acknowledgment_allowed": False,
    }
    if bridge_provider == "courtlistener_rest":
        config["bridge_provider"] = bridge_provider
        if fixture_path is None:
            request_ledger = cast(Path, args.request_ledger)
            profile = cast(str, args.courtlistener_rate_profile)
            limits = _COURTLISTENER_RATE_PROFILES[profile]
            config.update(
                {
                    "courtlistener_request_ledger": str(request_ledger.resolve()),
                    "courtlistener_rate_profile": profile,
                    "courtlistener_limits": {
                        "per_minute": limits.per_minute,
                        "per_hour": limits.per_hour,
                        "per_day": limits.per_day,
                    },
                    "request_budget_max_wait_seconds": cast(
                        float, args.request_budget_max_wait_seconds
                    ),
                }
            )
    resume = cast(bool, args.resume)
    existing_checkpoint_paths = {
        path.resolve()
        for path in checkpoint_dir.glob("*.json")
        if path.resolve() != checkpoint_config_path.resolve()
    }
    screened_by_id = {_bridge_candidate_id(record): record for record in records}
    expected_paths = {
        _bridge_checkpoint_path(
            checkpoint_dir,
            input_index=input_index,
            candidate_id=_required_str(gap, "candidate_id"),
        ).resolve()
        for input_index, gap in enumerate(paid_gaps)
    }
    unexpected_paths = existing_checkpoint_paths - expected_paths
    if unexpected_paths:
        raise CommandError("PACER-gap bridge checkpoint directory has unexpected files")
    if checkpoint_config_path.exists():
        if not resume:
            raise CommandError(
                "PACER-gap bridge progress exists; use --resume or remove it"
            )
        if not _bridge_progress_config_matches(
            _read_json_object(checkpoint_config_path), config
        ):
            raise CommandError(
                "PACER-gap bridge progress does not match the current input/config"
            )
    else:
        if existing_checkpoint_paths:
            raise CommandError("PACER-gap bridge checkpoints are missing their config")
        _atomic_write_json(checkpoint_config_path, config)

    checkpoints: list[JsonRecord] = []
    resumed_terminal_count = 0
    semantic_replay_count = 0
    request_count_before = client.request_count
    for input_index, gap in enumerate(paid_gaps):
        candidate_id = _required_str(gap, "candidate_id")
        record = screened_by_id[candidate_id]
        candidate_input_sha256 = _canonical_json_sha256(
            {"screened_case": record, "paid_gap": gap}
        )
        checkpoint_path = _bridge_checkpoint_path(
            checkpoint_dir,
            input_index=input_index,
            candidate_id=candidate_id,
        )
        prior: JsonRecord | None = None
        semantic_replay = False
        if checkpoint_path.exists():
            prior = _read_json_object(checkpoint_path)
            _validate_bridge_checkpoint(
                prior,
                input_index=input_index,
                candidate_id=candidate_id,
                candidate_input_sha256=candidate_input_sha256,
            )
            prior = _normalize_bridge_checkpoint(prior)
            if prior["outcome"] in {"success", "exclusion"}:
                if _bridge_checkpoint_requires_semantic_replay(
                    prior, bridge_provider=bridge_provider
                ):
                    semantic_replay = True
                    semantic_replay_count += 1
                else:
                    resumed_terminal_count += 1
                    checkpoints.append(prior)
                    continue
        attempt_count = (
            1
            if semantic_replay
            else cast(int, prior["resumable_attempt_count"]) + 1
            if prior is not None
            else 1
        )
        one_request_count_before = client.request_count
        request_count_field = (
            "cumulative_courtlistener_request_count"
            if bridge_provider == "courtlistener_rest"
            else "cumulative_case_dev_request_count"
        )
        try:
            if bridge_provider == "courtlistener_rest":
                if not isinstance(client, CourtListenerClient):
                    raise CommandError("CourtListener bridge client type mismatch")
                selection, relevance = (
                    bridge_public_plan_paid_gap_candidate_via_courtlistener(
                        record,
                        paid_gap_record=gap,
                        free_download_records=free_downloads,
                        client=client,
                        raw_html_dir=raw_html_dir,
                        use_embedded_entries=cast(bool, args.use_embedded_entries),
                        validate_free_downloads=False,
                    )
                )
            else:
                if not isinstance(client, CaseDevClient):
                    raise CommandError("Case.dev bridge client type mismatch")
                selection, relevance = bridge_public_plan_paid_gap_candidate(
                    record,
                    paid_gap_record=gap,
                    free_download_records=free_downloads,
                    client=client,
                    raw_html_dir=raw_html_dir,
                    use_embedded_entries=cast(bool, args.use_embedded_entries),
                    validate_free_downloads=False,
                )
            free_requests = bridge_free_download_requests_from_selection(selection)
            checkpoint: JsonRecord = {
                "schema_version": _PACER_GAP_CHECKPOINT_SCHEMA,
                "input_index": input_index,
                "candidate_id": candidate_id,
                "candidate_input_sha256": candidate_input_sha256,
                "outcome": "success",
                "resumable_attempt_count": attempt_count,
                request_count_field: (
                    (cast(int, prior.get(request_count_field, 0)) if prior else 0)
                    + client.request_count
                    - one_request_count_before
                ),
                "payload": {
                    "selection_record": selection,
                    "case_relevance_record": relevance,
                    "free_download_requests": [
                        request.to_record() for request in free_requests
                    ],
                },
            }
        except CourtListenerCaseDevBridgeError as exc:
            reason, _, detail = str(exc).partition(":")
            checkpoint = {
                "schema_version": _PACER_GAP_CHECKPOINT_SCHEMA,
                "input_index": input_index,
                "candidate_id": candidate_id,
                "candidate_input_sha256": candidate_input_sha256,
                "outcome": "exclusion",
                "resumable_attempt_count": attempt_count,
                request_count_field: (
                    (cast(int, prior.get(request_count_field, 0)) if prior else 0)
                    + client.request_count
                    - one_request_count_before
                ),
                "payload": {
                    "exclusion_record": case_dev_bridge_exclusion_record(
                        record,
                        reason=reason,
                        detail=detail.strip() or str(exc),
                    )
                },
            }
        except (CourtListenerResponseError, CourtListenerUnavailableError) as exc:
            reason = (
                "courtlistener_rest_unavailable"
                if isinstance(exc, CourtListenerUnavailableError)
                else "courtlistener_rest_response_invalid"
            )
            checkpoint = {
                "schema_version": _PACER_GAP_CHECKPOINT_SCHEMA,
                "input_index": input_index,
                "candidate_id": candidate_id,
                "candidate_input_sha256": candidate_input_sha256,
                "outcome": "exclusion",
                "resumable_attempt_count": attempt_count,
                request_count_field: (
                    (cast(int, prior.get(request_count_field, 0)) if prior else 0)
                    + client.request_count
                    - one_request_count_before
                ),
                "payload": {
                    "exclusion_record": case_dev_bridge_exclusion_record(
                        record,
                        reason=reason,
                        detail=str(exc),
                    )
                },
            }
        except CourtListenerAuthError:
            raise
        except (
            CaseDevRateLimitError,
            CaseDevServerError,
            CourtListenerRateLimitError,
            CourtListenerServerError,
            CourtListenerClientError,
        ) as exc:
            rate_limited = isinstance(
                exc, CaseDevRateLimitError | CourtListenerRateLimitError
            )
            is_courtlistener = isinstance(exc, CourtListenerClientError)
            if rate_limited:
                reason = (
                    "courtlistener_rest_rate_limit_retries_exhausted"
                    if is_courtlistener
                    else "case_dev_rate_limit_retries_exhausted"
                )
            elif isinstance(exc, CaseDevServerError):
                reason = "case_dev_server_error_retries_exhausted"
            elif isinstance(exc, CourtListenerServerError):
                reason = "courtlistener_rest_server_error_retries_exhausted"
            else:
                reason = "courtlistener_rest_client_error_retries_exhausted"
            exhausted = attempt_count >= _PACER_GAP_MAX_RESUMABLE_ATTEMPTS
            payload: JsonRecord
            if exhausted:
                payload = {
                    "exclusion_record": case_dev_bridge_exclusion_record(
                        record,
                        reason=reason,
                        detail=(
                            f"{exc}; exhausted {attempt_count} resumable candidate "
                            "attempts"
                        ),
                    )
                }
            else:
                payload = {"reason": reason, "detail": str(exc)}
            checkpoint = {
                "schema_version": _PACER_GAP_CHECKPOINT_SCHEMA,
                "input_index": input_index,
                "candidate_id": candidate_id,
                "candidate_input_sha256": candidate_input_sha256,
                "outcome": "exclusion" if exhausted else "retryable",
                "resumable_attempt_count": attempt_count,
                request_count_field: (
                    (cast(int, prior.get(request_count_field, 0)) if prior else 0)
                    + client.request_count
                    - one_request_count_before
                ),
                "payload": payload,
            }
        _atomic_write_json(checkpoint_path, checkpoint)
        checkpoints.append(checkpoint)

    terminal_count = sum(
        record["outcome"] in {"success", "exclusion"} for record in checkpoints
    )
    retryable_count = sum(record["outcome"] == "retryable" for record in checkpoints)
    request_count_field = (
        "cumulative_courtlistener_request_count"
        if bridge_provider == "courtlistener_rest"
        else "cumulative_case_dev_request_count"
    )
    cumulative_requests = sum(
        cast(int, record.get(request_count_field, 0)) for record in checkpoints
    )
    evidence: JsonRecord = {
        "input_route_count": len(routed_ids),
        "bridge_provider": bridge_provider,
        (
            "courtlistener_request_count"
            if bridge_provider == "courtlistener_rest"
            else "case_dev_request_count"
        ): client.request_count - request_count_before,
        request_count_field: cumulative_requests,
        (
            "courtlistener_max_http_attempts_per_request"
            if bridge_provider == "courtlistener_rest"
            else "case_dev_max_http_attempts_per_request"
        ): client.max_retries + 1,
        "max_resumable_candidate_attempts": _PACER_GAP_MAX_RESUMABLE_ATTEMPTS,
        "checkpoint_terminal_candidate_count": terminal_count,
        "resumed_terminal_candidate_count": resumed_terminal_count,
        "semantic_replay_candidate_count": semantic_replay_count,
        "retryable_candidate_count": retryable_count,
        "free_lookup_only": True,
        "pacer_fee_acknowledgment_allowed": False,
        "pacer_spend_usd": "0.00",
        "reconciled": False,
    }
    if isinstance(client, CaseDevClient):
        evidence["case_dev_rate_limit_per_minute"] = client.config.rate_limit_per_minute
        evidence["case_dev_rate_limit_enforced"] = (
            client.config.rate_limit_per_minute is not None
        )
    if retryable_count:
        return None, evidence

    if bridge_provider == "courtlistener_rest":
        if not isinstance(client, CourtListenerClient):
            raise CommandError("CourtListener bridge client type mismatch")
        public_result = bridge_public_plan_paid_gaps_via_courtlistener(
            records,
            public_selection_records=public_selections,
            paid_gap_records=(),
            free_download_records=free_downloads,
            client=client,
            raw_html_dir=raw_html_dir,
            use_embedded_entries=cast(bool, args.use_embedded_entries),
        )
    else:
        if not isinstance(client, CaseDevClient):
            raise CommandError("Case.dev bridge client type mismatch")
        public_result = bridge_public_plan_paid_gaps(
            records,
            public_selection_records=public_selections,
            paid_gap_records=(),
            free_download_records=free_downloads,
            client=client,
            raw_html_dir=raw_html_dir,
            use_embedded_entries=cast(bool, args.use_embedded_entries),
            validate_free_downloads=False,
        )
    selections = list(public_result.selection_records)
    relevance = list(public_result.case_relevance_records)
    free_requests = list(public_result.free_download_requests)
    exclusions: list[Mapping[str, Any]] = []
    for checkpoint in sorted(
        checkpoints, key=lambda item: cast(int, item["input_index"])
    ):
        checkpoint_payload = cast(Mapping[str, Any], checkpoint["payload"])
        if checkpoint["outcome"] == "success":
            selections.append(
                _mapping(checkpoint_payload.get("selection_record"), "selection_record")
            )
            relevance.append(
                _mapping(
                    checkpoint_payload.get("case_relevance_record"),
                    "case_relevance_record",
                )
            )
            free_requests.extend(
                _free_document_download_request(record)
                for record in _optional_record_sequence(
                    checkpoint_payload, "free_download_requests"
                )
            )
        else:
            exclusions.append(
                _mapping(checkpoint_payload.get("exclusion_record"), "exclusion_record")
            )
    selected_ids = [_required_str(record, "candidate_id") for record in selections]
    excluded_ids = [_required_str(record, "candidate_id") for record in exclusions]
    relevance_ids = [_required_str(record, "candidate_id") for record in relevance]
    if (
        len(set(selected_ids)) != len(selected_ids)
        or len(set(excluded_ids)) != len(excluded_ids)
        or set(selected_ids) & set(excluded_ids)
        or set(selected_ids) | set(excluded_ids) != set(routed_ids)
        or set(relevance_ids) != set(selected_ids)
        or len(relevance_ids) != len(selected_ids)
    ):
        raise CommandError("PACER-gap bridge checkpoints did not exactly reconcile")
    result = CourtListenerCaseDevBridgeResult(
        selection_records=tuple(selections),
        case_relevance_records=tuple(relevance),
        free_download_requests=tuple(free_requests),
        exclusions=tuple(exclusions),
        screened_case_count=len(routed_ids),
        public_first_reconciled=True,
        bridge_provider=bridge_provider,
    )
    evidence["reconciled"] = True
    return result, evidence


def _validate_pacer_gap_bridge_paths(
    *,
    args: argparse.Namespace,
    output_root: Path,
    screened_cases_path: Path,
    raw_html_dir: Path | None,
    fixture_path: Path | None,
    courtlistener_fixture_path: Path | None,
    public_selection_path: Path | None,
    paid_gaps_path: Path | None,
    free_download_manifest_path: Path | None,
    requests_path: Path,
    selection_path: Path,
    case_relevance_path: Path,
    exclusions_path: Path,
    summary_path: Path,
    checkpoint_dir: Path,
    checkpoint_config_path: Path,
    public_first: bool,
) -> None:
    """Reject bridge path aliases before any writable or provider activity."""

    protected_scopes: list[tuple[str, Path, bool]] = [
        ("--screened-cases", screened_cases_path, False)
    ]
    protected_scopes.extend(
        (label, path, is_tree)
        for label, path, is_tree in (
            ("--raw-html-dir", raw_html_dir, True),
            ("--case-dev-fixture", fixture_path, False),
            ("--courtlistener-fixture", courtlistener_fixture_path, False),
            ("--public-selection", public_selection_path, False),
            ("--paid-gaps", paid_gaps_path, False),
            ("--free-download-manifest", free_download_manifest_path, False),
        )
        if path is not None
    )
    writable_scopes: list[tuple[str, Path, bool]] = [
        ("--requests-output", requests_path, False),
        ("--selection-output", selection_path, False),
        ("--case-relevance-output", case_relevance_path, False),
        ("--exclusions-output", exclusions_path, False),
        ("--summary-output", summary_path, False),
        (
            "--run-card-output",
            _acquisition_path(
                args,
                "run_card_output",
                output_root / "run-cards" / "bridge-pacer-gaps.json",
            ),
            False,
        ),
        (
            "--log-output",
            _acquisition_path(
                args,
                "log_output",
                output_root / "logs" / "bridge-pacer-gaps.jsonl",
            ),
            False,
        ),
    ]
    if public_first:
        writable_scopes.extend(
            (
                ("--checkpoint-dir", checkpoint_dir, True),
                ("--checkpoint-config-output", checkpoint_config_path, False),
            )
        )

    for writable_label, writable_path, writable_tree in writable_scopes:
        writable = writable_path.resolve()
        if not writable_tree:
            _reject_hardlinked_writable_replay_scope(
                label=writable_label,
                path=writable,
                is_tree=False,
            )
        for protected_label, protected_path, protected_tree in protected_scopes:
            protected = protected_path.resolve()
            if _replay_scopes_overlap(
                left_label=writable_label,
                left=writable,
                left_tree=writable_tree,
                right_label=protected_label,
                right=protected,
                right_tree=protected_tree,
            ):
                raise CommandError(
                    f"bridge output overlaps input: {writable_label} vs "
                    f"{protected_label}: {writable} vs {protected}"
                )

    for index, (label, path, is_tree) in enumerate(writable_scopes):
        resolved = path.resolve()
        for other_label, other_path, other_is_tree in writable_scopes[index + 1 :]:
            other = other_path.resolve()
            if _replay_scopes_overlap(
                left_label=label,
                left=resolved,
                left_tree=is_tree,
                right_label=other_label,
                right=other,
                right_tree=other_is_tree,
            ):
                raise CommandError(
                    f"bridge writable outputs overlap: {label} vs {other_label}: "
                    f"{resolved} vs {other}"
                )


def _cmd_acquisition_bridge_pacer_gaps(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    screened_cases_path = cast(Path, args.screened_cases)
    raw_html_dir = cast(Path | None, args.raw_html_dir)
    fixture_path = cast(Path | None, args.case_dev_fixture)
    courtlistener_fixture_path = cast(Path | None, args.courtlistener_fixture)
    public_selection_path = cast(Path | None, args.public_selection)
    paid_gaps_path = cast(Path | None, args.paid_gaps)
    free_download_manifest_path = cast(Path | None, args.free_download_manifest)
    public_first_inputs = (
        public_selection_path,
        paid_gaps_path,
        free_download_manifest_path,
    )
    public_first = all(path is not None for path in public_first_inputs)
    if any(path is not None for path in public_first_inputs) and not public_first:
        raise CommandError(
            "--public-selection, --paid-gaps, and --free-download-manifest "
            "must be provided together"
        )
    requests_path = _acquisition_path(
        args,
        "requests_output",
        output_root
        / (
            "pacer-gap-free-document-requests.jsonl"
            if public_first
            else "free-document-requests.jsonl"
        ),
    )
    selection_path = _acquisition_path(
        args,
        "selection_output",
        output_root
        / (
            "public-packet-selection-reconciled.jsonl"
            if public_first
            else "public-packet-selection.jsonl"
        ),
    )
    case_relevance_path = _acquisition_path(
        args,
        "case_relevance_output",
        output_root / "case-relevance.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "pacer-gap-bridge-exclusions.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "pacer-gap-bridge-summary.json",
    )
    checkpoint_dir = _acquisition_path(
        args,
        "checkpoint_dir",
        output_root / "checkpoints" / "pacer-gap-bridge",
    )
    checkpoint_config_path = _acquisition_path(
        args,
        "checkpoint_config_output",
        output_root / "checkpoints" / "pacer-gap-bridge-progress-config.json",
    )
    _validate_pacer_gap_bridge_paths(
        args=args,
        output_root=output_root,
        screened_cases_path=screened_cases_path,
        raw_html_dir=raw_html_dir,
        fixture_path=fixture_path,
        courtlistener_fixture_path=courtlistener_fixture_path,
        public_selection_path=public_selection_path,
        paid_gaps_path=paid_gaps_path,
        free_download_manifest_path=free_download_manifest_path,
        requests_path=requests_path,
        selection_path=selection_path,
        case_relevance_path=case_relevance_path,
        exclusions_path=exclusions_path,
        summary_path=summary_path,
        checkpoint_dir=checkpoint_dir,
        checkpoint_config_path=checkpoint_config_path,
        public_first=public_first,
    )
    records = _read_records(screened_cases_path)
    dry_run = _acquisition_dry_run(args)
    live = cast(bool, args.live_case_dev)
    live_courtlistener = cast(bool, args.live_courtlistener)
    courtlistener_mode = courtlistener_fixture_path is not None or live_courtlistener
    case_dev_mode = fixture_path is not None or live
    if courtlistener_fixture_path is not None and live_courtlistener:
        raise CommandError(
            "choose --courtlistener-fixture or --live-courtlistener, not both"
        )
    if courtlistener_mode and case_dev_mode:
        raise CommandError(
            "choose a Case.dev bridge provider or CourtListener REST, not both"
        )
    if courtlistener_mode and not public_first:
        raise CommandError(
            "CourtListener REST bridge mode requires --public-selection, "
            "--paid-gaps, and --free-download-manifest"
        )
    if not courtlistener_mode and not case_dev_mode and not dry_run:
        raise CommandError(
            "bridge-pacer-gaps requires a fixture or live flag for one provider"
        )
    input_paths = tuple(
        path
        for path in (
            screened_cases_path,
            raw_html_dir,
            fixture_path,
            courtlistener_fixture_path,
            public_selection_path,
            paid_gaps_path,
            free_download_manifest_path,
        )
        if path is not None
    )
    output_paths = (
        requests_path,
        selection_path,
        case_relevance_path,
        exclusions_path,
        summary_path,
        *((checkpoint_dir, checkpoint_config_path) if public_first else ()),
    )
    bridge_evidence: JsonRecord = {}
    if dry_run:
        dry_run_summary = CourtListenerCaseDevBridgeResult(
            selection_records=(),
            case_relevance_records=(),
            free_download_requests=(),
            exclusions=(),
            screened_case_count=len(records),
            public_first_reconciled=public_first,
        ).summary_record()
        _write_jsonl(
            requests_path,
            [
                {
                    "stage": "bridge-pacer-gaps",
                    "dry_run": True,
                    "screened_case_count": len(records),
                    "free_first_required": True,
                }
            ],
        )
        _write_json(
            summary_path,
            {
                **dry_run_summary,
                "dry_run": True,
            },
        )
        selected_count = 0
        paid_document_count = 0
        paid_recovery_required_case_count = 0
        identity_resolved_paid_gap_case_count = 0
        document_bytes_ready_case_count = 0
        free_request_count = 0
        excluded_count = 0
    else:
        if courtlistener_mode:
            courtlistener_client, request_budget = _courtlistener_bridge_client(
                args,
                fixture_path=courtlistener_fixture_path,
                live=live_courtlistener,
            )
            assert public_selection_path is not None
            assert paid_gaps_path is not None
            assert free_download_manifest_path is not None
            try:
                result_or_none, bridge_evidence = _public_first_bridge_with_checkpoints(
                    args=args,
                    records=records,
                    client=courtlistener_client,
                    bridge_provider="courtlistener_rest",
                    raw_html_dir=raw_html_dir,
                    public_selection_path=public_selection_path,
                    paid_gaps_path=paid_gaps_path,
                    free_download_manifest_path=free_download_manifest_path,
                    fixture_path=courtlistener_fixture_path,
                    checkpoint_dir=checkpoint_dir,
                    checkpoint_config_path=checkpoint_config_path,
                )
            except CourtListenerRequestBudgetError as exc:
                raise CommandError(str(exc)) from exc
            bridge_evidence.update(
                _courtlistener_bridge_rate_evidence(
                    args, courtlistener_client, request_budget
                )
            )
            if result_or_none is None:
                reason = (
                    "PACER-gap bridge retained retryable CourtListener candidates; "
                    "rerun with --resume"
                )
                _write_acquisition_failure(
                    args,
                    stage="bridge-pacer-gaps",
                    input_paths=input_paths,
                    output_paths=output_paths,
                    reason=reason,
                    paid_activity_requested=False,
                    extra=bridge_evidence,
                )
                raise CommandError(reason)
            result = result_or_none
        else:
            client = _case_dev_client(
                command="acquisition bridge-pacer-gaps",
                fixture_path=fixture_path,
                live=live,
            )
            if public_first:
                assert public_selection_path is not None
                assert paid_gaps_path is not None
                assert free_download_manifest_path is not None
                result_or_none, bridge_evidence = _public_first_bridge_with_checkpoints(
                    args=args,
                    records=records,
                    client=client,
                    bridge_provider="case.dev",
                    raw_html_dir=raw_html_dir,
                    public_selection_path=public_selection_path,
                    paid_gaps_path=paid_gaps_path,
                    free_download_manifest_path=free_download_manifest_path,
                    fixture_path=fixture_path,
                    checkpoint_dir=checkpoint_dir,
                    checkpoint_config_path=checkpoint_config_path,
                )
                if result_or_none is None:
                    reason = (
                        "PACER-gap bridge retained retryable Case.dev candidates; "
                        "rerun with --resume"
                    )
                    _write_acquisition_failure(
                        args,
                        stage="bridge-pacer-gaps",
                        input_paths=input_paths,
                        output_paths=output_paths,
                        reason=reason,
                        paid_activity_requested=False,
                        extra=bridge_evidence,
                    )
                    raise CommandError(reason)
                result = result_or_none
            else:
                result = bridge_courtlistener_case_dev_documents(
                    records,
                    client=client,
                    raw_html_dir=raw_html_dir,
                    use_embedded_entries=cast(bool, args.use_embedded_entries),
                    target_clean_cases=cast(int, args.target_clean_cases),
                )
        _write_jsonl(
            requests_path,
            [request.to_record() for request in result.free_download_requests],
        )
        _write_jsonl(selection_path, result.selection_records)
        _write_jsonl(case_relevance_path, result.case_relevance_records)
        _write_jsonl(exclusions_path, result.exclusions)
        next_stage = (
            "download-free"
            if result.free_download_requests
            else "filter-core-documents"
            if public_first
            else "download-free"
        )
        _write_json(
            summary_path,
            {
                **result.summary_record(),
                "dry_run": False,
                "next_stage": next_stage,
                **bridge_evidence,
            },
        )
        selected_count = result.selected_case_count
        paid_document_count = result.paid_document_count
        paid_recovery_required_case_count = result.paid_recovery_required_case_count
        identity_resolved_paid_gap_case_count = (
            result.identity_resolved_paid_gap_case_count
        )
        document_bytes_ready_case_count = result.document_bytes_ready_case_count
        free_request_count = len(result.free_download_requests)
        excluded_count = len(result.exclusions)
    _write_acquisition_completion(
        args,
        stage="bridge-pacer-gaps",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=selected_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "selected_case_count": selected_count,
            "excluded_case_count": excluded_count,
            "free_download_request_count": free_request_count,
            "paid_document_count": paid_document_count,
            "paid_recovery_required_document_count": paid_document_count,
            "paid_recovery_required_case_count": paid_recovery_required_case_count,
            "identity_resolved_paid_gap_case_count": (
                identity_resolved_paid_gap_case_count
            ),
            "document_bytes_ready_case_count": document_bytes_ready_case_count,
            "free_first_required": True,
            "next_stage": (
                "download-free"
                if free_request_count
                else "filter-core-documents"
                if public_first
                else "download-free"
            ),
            **bridge_evidence,
        },
    )
    return 0


def _cmd_acquisition_merge_download_manifests(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    manifest_paths = tuple(cast(Sequence[Path], args.download_manifest))
    output_path = _acquisition_path(
        args,
        "manifest_output",
        output_root / "document-downloads-merged.jsonl",
    )
    merged = merge_download_manifest_records(
        _read_records(path) for path in manifest_paths
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            output_path,
            [
                {
                    "stage": "merge-download-manifests",
                    "dry_run": True,
                    "manifest_count": len(manifest_paths),
                    "record_count": len(merged),
                }
            ],
        )
    else:
        _write_jsonl(output_path, merged)
    _write_acquisition_completion(
        args,
        stage="merge-download-manifests",
        input_paths=manifest_paths,
        output_paths=(output_path,),
        record_count=len(merged),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_assemble_cycle(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    batch_roots = tuple(cast(Sequence[Path], args.batch_root))
    dry_run = _acquisition_dry_run(args)
    assembly = assemble_cycle_acquisition(
        batch_roots,
        expected_cycle_hash=cast(str, args.expected_cycle_hash),
        output_root=output_root,
        copy_documents=not dry_run,
    )
    output_paths = _write_cycle_assembly(
        output_root,
        assembly=assembly,
        dry_run=dry_run,
    )
    _write_acquisition_completion(
        args,
        stage="assemble-cycle-acquisition",
        input_paths=batch_roots,
        output_paths=output_paths,
        record_count=len(assembly.screened_cases),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={"record_counts": assembly.summary["record_counts"]},
    )
    return 0


def _cmd_acquisition_bind_component(args: argparse.Namespace) -> int:
    component_root = _acquisition_output_root(args)
    snapshot = cast(Path, args.snapshot)
    expected_cycle_hash = cast(str, args.expected_cycle_hash)
    component_ordinal = cast(int, args.component_ordinal)
    predecessor_path = cast(Path | None, args.predecessor_provenance)
    try:
        snapshot_manifest = verify_snapshot(
            snapshot,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        raise CommandError(str(exc)) from exc
    if component_ordinal == 1:
        if predecessor_path is not None:
            raise CommandError(
                "--predecessor-provenance is forbidden for component ordinal 1"
            )
        predecessor_sha256 = hashlib.sha256(
            (snapshot / "manifest.json").read_bytes()
        ).hexdigest()
        input_paths = (snapshot, component_root)
    elif component_ordinal > 1:
        if predecessor_path is None:
            raise CommandError(
                "--predecessor-provenance is required after component ordinal 1"
            )
        predecessor_sha256 = hashlib.sha256(predecessor_path.read_bytes()).hexdigest()
        input_paths = (snapshot, predecessor_path, component_root)
    else:
        raise CommandError("--component-ordinal must be positive")
    output_path = component_root / COMPONENT_PROVENANCE_FILENAME
    dry_run = _acquisition_dry_run(args)
    if not dry_run:
        write_component_provenance(
            component_root,
            source_snapshot_manifest=snapshot / "manifest.json",
            component_ordinal=component_ordinal,
            predecessor_sha256=predecessor_sha256,
            component_stage=cast(str, args.component_stage),
        )
    _write_acquisition_completion(
        args,
        stage="bind-acquisition-component",
        input_paths=input_paths,
        output_paths=(output_path,),
        record_count=1,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "cycle_hash": snapshot_manifest["cycle_hash"],
            "batch_digest": snapshot_manifest["batch_digest"],
            "component_stage": cast(str, args.component_stage),
            "component_ordinal": component_ordinal,
            "predecessor_sha256": predecessor_sha256,
        },
    )
    return 0


def _write_cycle_assembly(
    output_root: Path, *, assembly: CycleAssembly, dry_run: bool
) -> tuple[Path, ...]:
    paths = (
        output_root / "screened-cases.jsonl",
        output_root / "discovery-exclusions.jsonl",
        output_root / "public-packet-selection.jsonl",
        output_root / "public-packet-paid-gaps.jsonl",
        output_root / "case-relevance.jsonl",
        output_root / "core-filter-results.jsonl",
        output_root / "document-downloads-merged.jsonl",
        output_root / "cycle-acquisition-summary.json",
    )
    if dry_run:
        return paths
    for path, records in zip(
        paths[:-1],
        (
            assembly.screened_cases,
            assembly.discovery_exclusions,
            assembly.selections,
            assembly.paid_gaps,
            assembly.case_relevance,
            assembly.core_filter_results,
            assembly.document_manifest,
        ),
        strict=True,
    ):
        _write_jsonl(path, records)
    _write_json(paths[-1], assembly.summary)
    return paths


_ACQUISITION_MERGE_JSONL_FILES = (
    "free-document-requests.jsonl",
    "free-document-downloads.jsonl",
    "parse-document-requests.jsonl",
    "mistral-markdown-conversions.jsonl",
    "document-manifest.jsonl",
    "candidate-manifest.jsonl",
    "extracted_texts.jsonl",
    "packet-build-input.jsonl",
    "packets.jsonl",
    "case-packets.jsonl",
    "packet-audit.jsonl",
    "llm-unitization-audit.jsonl",
    "unitization-review-queue.jsonl",
    "unitization-review-adjudications.jsonl",
    "llm-label-audit.jsonl",
    "lawyer-review-queue.jsonl",
    "lawyer-review-resume-audit.jsonl",
)


def _cmd_acquisition_merge_artifacts(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    source_roots = tuple(cast(Sequence[Path], args.source_root))
    labels_paths = _explicit_or_default_merge_paths(
        cast(Sequence[Path] | None, args.labels),
        source_roots=source_roots,
        filenames=("labels-packet-buildable.jsonl", "labels.jsonl"),
    )
    unit_paths = _explicit_or_default_merge_paths(
        cast(Sequence[Path] | None, args.prediction_units),
        source_roots=source_roots,
        filenames=(
            "prediction-units-packet-buildable-labeled.jsonl",
            "prediction-units.jsonl",
        ),
    )
    dry_run = _acquisition_dry_run(args)

    _validate_merge_sources(source_roots)
    selection_paths = _explicit_or_default_merge_paths(
        cast(Sequence[Path] | None, args.selection),
        source_roots=source_roots,
        filenames=(
            "public-packet-selection-packet-buildable-labeled.jsonl",
            "public-packet-selection.jsonl",
        ),
    )
    jsonl_outputs: list[Path] = []
    record_counts: dict[str, int] = {}
    packet_count = 0
    for filename in _ACQUISITION_MERGE_JSONL_FILES:
        records = _merge_records_from_roots(source_roots, filename=filename)
        if filename in {"packets.jsonl", "case-packets.jsonl"}:
            packet_count = len(records)
        if not records:
            continue
        _validate_acquisition_merge_records(filename, records)
        record_counts[filename] = len(records)
        output_path = output_root / filename
        jsonl_outputs.append(output_path)
        if not dry_run:
            _write_jsonl(output_path, records)

    labels = _merge_records_from_paths(labels_paths)
    _validate_acquisition_merge_records("labels.jsonl", labels)
    units = _merge_records_from_paths(unit_paths)
    _validate_acquisition_merge_records("prediction-units.jsonl", units)
    selections = _merge_records_from_paths(selection_paths)
    _validate_acquisition_merge_records("public-packet-selection.jsonl", selections)
    record_counts["labels.jsonl"] = len(labels)
    record_counts["prediction-units.jsonl"] = len(units)
    record_counts["public-packet-selection.jsonl"] = len(selections)
    if not dry_run:
        _write_jsonl(output_root / "labels.jsonl", labels)
        _write_jsonl(output_root / "prediction-units.jsonl", units)
        _write_jsonl(output_root / "public-packet-selection.jsonl", selections)
        for directory_name in ("documents", "markdown"):
            _copy_merge_directory(source_roots, output_root, directory_name)

    summary_path = output_root / "merge-artifacts-summary.json"
    summary = {
        "dry_run": dry_run,
        "source_roots": [str(root) for root in source_roots],
        "labels": [str(path) for path in labels_paths],
        "prediction_units": [str(path) for path in unit_paths],
        "selection": [str(path) for path in selection_paths],
        "record_counts": record_counts,
    }
    _write_json(summary_path, summary)

    _write_acquisition_completion(
        args,
        stage="merge-artifacts",
        input_paths=(*source_roots, *labels_paths, *unit_paths, *selection_paths),
        output_paths=(
            *jsonl_outputs,
            output_root / "labels.jsonl",
            output_root / "prediction-units.jsonl",
            output_root / "public-packet-selection.jsonl",
            output_root / "documents",
            output_root / "markdown",
            summary_path,
        ),
        record_count=packet_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={"record_counts": record_counts},
    )
    return 0


def _validate_merge_sources(source_roots: Sequence[Path]) -> None:
    if not source_roots:
        raise CommandError("at least one --source-root is required")
    seen: set[Path] = set()
    for source_root in source_roots:
        if not source_root.is_dir():
            raise CommandError(f"merge source root is not a directory: {source_root}")
        resolved = source_root.resolve()
        if resolved in seen:
            raise CommandError(f"duplicate merge source root: {source_root}")
        seen.add(resolved)


def _explicit_or_default_merge_paths(
    explicit_paths: Sequence[Path] | None,
    *,
    source_roots: Sequence[Path],
    filenames: Sequence[str],
) -> tuple[Path, ...]:
    if explicit_paths:
        paths = tuple(explicit_paths)
    else:
        paths = tuple(
            _default_merge_path(source_root, filenames=filenames)
            for source_root in source_roots
        )
    for path in paths:
        if not path.is_file():
            raise CommandError(f"merge input does not exist: {path}")
    return paths


def _default_merge_path(source_root: Path, *, filenames: Sequence[str]) -> Path:
    for filename in filenames:
        path = source_root / filename
        if path.is_file():
            return path
    candidates = ", ".join(filenames)
    raise CommandError(f"merge source {source_root} has none of: {candidates}")


def _merge_records_from_roots(
    source_roots: Sequence[Path],
    *,
    filename: str,
) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for source_root in source_roots:
        path = source_root / filename
        if path.is_file():
            records.extend(_read_records(path))
    return records


def _merge_records_from_paths(paths: Sequence[Path]) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for path in paths:
        records.extend(_read_records(path))
    if not records:
        raise CommandError("merge inputs produced no records")
    return records


def _copy_merge_directory(
    source_roots: Sequence[Path],
    output_root: Path,
    directory_name: str,
) -> None:
    for source_root in source_roots:
        source_dir = source_root / directory_name
        if not source_dir.is_dir():
            continue
        shutil.copytree(source_dir, output_root / directory_name, dirs_exist_ok=True)


def _validate_acquisition_merge_records(
    filename: str,
    records: Sequence[Mapping[str, Any]],
) -> None:
    if not records:
        raise CommandError(f"{filename} must contain at least one record")
    if filename in {"packets.jsonl", "case-packets.jsonl"}:
        _require_unique_merge_keys(
            filename,
            (
                (
                    _required_str(record, "case_id"),
                    _optional_str(record, "ablation")
                    or PacketAblation.FULL_PACKET.value,
                )
                for record in records
            ),
        )
    if filename in {
        "candidate-manifest.jsonl",
        "public-packet-selection.jsonl",
        "packet-build-input.jsonl",
        "prediction-units.jsonl",
    }:
        _require_unique_merge_keys(
            filename,
            (_required_str(record, "case_id") for record in records),
        )
    if filename in {"document-manifest.jsonl", "extracted_texts.jsonl"}:
        _require_unique_merge_keys(
            filename,
            (_required_str(record, "source_document_id") for record in records),
        )
    if filename == "mistral-markdown-conversions.jsonl":
        _require_unique_merge_keys(
            filename,
            (
                (
                    _optional_str(record, "candidate_id")
                    or _optional_str(record, "case_id")
                    or "unknown",
                    _required_str(record, "source_document_id"),
                )
                for record in records
            ),
        )
    if filename == "labels.jsonl":
        _require_unique_merge_keys(
            filename,
            (_required_str(record, "unit_id") for record in records),
        )
    if filename in {"prediction-units.jsonl", "packets.jsonl", "case-packets.jsonl"}:
        _require_unique_merge_keys(
            f"{filename} nested prediction units",
            (
                _required_str(unit, "unit_id")
                for record in records
                for unit in _merge_prediction_unit_records(record)
            ),
        )


def _merge_prediction_unit_records(
    record: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    units = record.get("prediction_units")
    if units is None:
        return ()
    if not isinstance(units, list):
        raise CommandError("prediction_units must be a list")
    merged: list[Mapping[str, Any]] = []
    for unit in cast(list[object], units):
        if not isinstance(unit, Mapping):
            raise CommandError("prediction_units items must be objects")
        merged.append(cast(Mapping[str, Any], unit))
    return tuple(merged)


def _require_unique_merge_keys(
    filename: str,
    keys: Iterable[object],
) -> None:
    seen: set[object] = set()
    duplicates: set[object] = set()
    for key in keys:
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    if duplicates:
        sample = ", ".join(str(key) for key in sorted(duplicates, key=str)[:5])
        raise CommandError(f"{filename} has duplicate merge key(s): {sample}")


def _cmd_acquisition_download_free(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    requests_path = cast(Path, args.requests)
    manifest_path = _acquisition_path(
        args,
        "manifest_output",
        output_root / "free-document-downloads.jsonl",
    )
    document_root = _acquisition_path(
        args,
        "document_output_root",
        output_root / "documents" / "free",
    )
    request_records = _read_records(requests_path)
    requests = tuple(
        _free_document_download_request(record) for record in request_records
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            manifest_path,
            [
                {
                    "stage": "download-free",
                    "dry_run": True,
                    "request_count": len(requests),
                    "document_output_root": str(document_root),
                }
            ],
        )
    else:
        fixture_path = cast(Path | None, args.fixture_documents)
        live_public_download = cast(bool, args.live_public_download)
        source = _free_document_source(
            fixture_path=fixture_path,
            live_public_download=live_public_download,
        )
        try:
            records = download_free_docket_documents(
                requests,
                output_root=document_root,
                source=source,
                allow_existing=cast(bool, args.resume),
            )
        except FreeDocumentDownloadError as exc:
            _write_acquisition_failure(
                args,
                stage="download-free",
                input_paths=(requests_path,),
                output_paths=(manifest_path, document_root),
                reason=str(exc),
                paid_activity_requested=False,
            )
            raise CommandError(str(exc)) from exc
        _write_jsonl(manifest_path, [record.to_record() for record in records])
    _write_acquisition_completion(
        args,
        stage="download-free",
        input_paths=(requests_path,),
        output_paths=(manifest_path, document_root),
        record_count=len(requests),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_purchase_missing(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    plan_path = cast(Path, args.budget_plan)
    output_path = _acquisition_path(
        args,
        "purchase_output",
        output_root / "case-dev-pacer-purchases.json",
    )
    plan = _missing_core_budget_plan(_read_json_object(plan_path))
    policy_path = cast(Path, args.purchase_policy)
    cohort_policy_path = cast(Path, args.cohort_policy)
    ledger_path = cast(Path, args.purchase_ledger).resolve()
    try:
        purchase_policy = verify_case_dev_purchase_policy(
            _read_json_object(policy_path)
        )
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy,
            _read_json_object(cohort_policy_path),
        )
    except (CaseDevPurchasePolicyError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    if ledger_path != purchase_policy.canonical_ledger_path:
        raise CommandError(
            "--purchase-ledger conflicts with the canonical policy locator"
        )
    dry_run = _acquisition_dry_run(args)
    live_purchase = cast(bool, args.live_purchase)
    acknowledge_fees = cast(bool, args.acknowledge_pacer_fees)
    capability = CaseDevPacerCapability(cast(str, args.capability))
    if live_purchase and cast(Path | None, args.case_dev_fixture) is None:
        raise CommandError(
            "legacy Case.dev live document purchase is disabled; use "
            "purchase-missing-recap-fetch"
        )
    if not dry_run and plan.dry_run:
        _write_acquisition_failure(
            args,
            stage="purchase-missing",
            input_paths=(plan_path,),
            output_paths=(output_path,),
            reason="budget_plan_is_dry_run",
            paid_activity_requested=live_purchase,
        )
        raise CommandError(
            "purchase-missing requires a non-dry-run budget plan from "
            "acquisition plan --execute"
        )
    if not dry_run and (not live_purchase or not acknowledge_fees):
        _write_acquisition_failure(
            args,
            stage="purchase-missing",
            input_paths=(plan_path,),
            output_paths=(output_path,),
            reason="live_purchase_and_fee_acknowledgment_required",
            paid_activity_requested=live_purchase,
        )
        raise CommandError(
            "purchase-missing requires --execute, --live-purchase, and "
            "--acknowledge-pacer-fees before any paid request"
        )

    execution_plan = _dry_run_missing_core_budget_plan(plan) if dry_run else plan
    client = (
        _dry_run_case_dev_client()
        if dry_run
        else _case_dev_client(
            command="acquisition purchase-missing",
            fixture_path=cast(Path | None, args.case_dev_fixture),
            live=live_purchase,
        )
    )
    try:
        if dry_run:
            result = CaseDevPacerPurchaseClient(
                client,
                capability=capability,
            ).execute_purchase_plan(
                execution_plan,
                live=False,
                acknowledge_pacer_fees=acknowledge_fees,
            )
        else:
            with CaseDevPurchaseJournal(
                ledger_path,
                policy=purchase_policy,
            ) as journal:
                result = CaseDevPacerPurchaseClient(
                    client,
                    capability=capability,
                    journal=journal,
                ).execute_purchase_plan(
                    execution_plan,
                    live=live_purchase,
                    acknowledge_pacer_fees=acknowledge_fees,
                )
    except (CaseDevPurchaseLedgerError, CaseDevPurchasePolicyError) as exc:
        _write_acquisition_failure(
            args,
            stage="purchase-missing",
            input_paths=(plan_path, policy_path),
            output_paths=(output_path, ledger_path),
            reason=str(exc),
            paid_activity_requested=live_purchase,
            paid_activity_executed=client.request_count > 0,
        )
        raise CommandError(str(exc)) from exc
    _write_json(output_path, result.to_record())
    paid_activity_executed = client.request_count > 0
    _write_acquisition_completion(
        args,
        stage="purchase-missing",
        input_paths=(plan_path, policy_path),
        output_paths=(output_path,) if dry_run else (output_path, ledger_path),
        record_count=result.intended_purchase_count,
        dry_run=dry_run,
        paid_activity_requested=live_purchase,
        paid_activity_executed=paid_activity_executed,
        extra={
            "executed_purchase_count": result.executed_purchase_count,
            "projected_cost_usd": result.projected_cost_usd,
        },
    )
    if not dry_run and result.executed_purchase_count != result.intended_purchase_count:
        return 2
    return 0


def _cmd_acquisition_purchase_missing_recap_fetch(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    plan_path = cast(Path, args.budget_plan)
    selection_path = cast(Path, args.selection)
    policy_path = cast(Path, args.purchase_policy)
    cohort_policy_path = cast(Path, args.cohort_policy)
    ledger_path = cast(Path, args.purchase_ledger).resolve()
    output_path = _acquisition_path(
        args,
        "purchase_output",
        output_root / "courtlistener-recap-fetch-purchases.json",
    )
    dry_run = _acquisition_dry_run(args)
    live_purchase = cast(bool, args.live_purchase)
    acknowledge_fees = cast(bool, args.acknowledge_pacer_fees)
    courtlistener_fixture = cast(Path | None, args.courtlistener_fixture)
    broker_fixture = cast(Path | None, args.purchase_broker_fixture)
    input_paths = (plan_path, selection_path, policy_path, cohort_policy_path)
    client: CourtListenerRecapFetchClient | None = None
    request_budget: CourtListenerRequestBudget | None = None
    try:
        plan = _missing_core_budget_plan(_read_json_object(plan_path))
        purchase_policy = verify_case_dev_purchase_policy(
            _read_json_object(policy_path)
        )
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy, _read_json_object(cohort_policy_path)
        )
        public_documents = public_documents_from_selection(
            _read_records(selection_path)
        )
        if ledger_path != purchase_policy.canonical_ledger_path:
            raise CommandError(
                "--purchase-ledger conflicts with the canonical policy locator"
            )
        if dry_run:
            attempts = tuple(
                CaseDevPacerPurchaseAttempt(
                    candidate_id=case_plan.candidate_id,
                    source_document_id=document_id,
                    status=CaseDevPacerPurchaseStatus.PLANNED_DRY_RUN,
                    reason="dry_run_no_paid_request",
                    source_provider="courtlistener.recap-fetch+pacer",
                )
                for case_plan in plan.case_plans
                for document_id in case_plan.purchase_document_ids
            )
            result = CaseDevPacerPurchaseResult(
                live=False,
                acknowledge_pacer_fees=acknowledge_fees,
                capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
                dry_run=True,
                projected_cost_usd=plan.total_estimated_cost_usd,
                max_projected_budget_usd=plan.max_projected_budget_usd,
                attempts=attempts,
            )
        else:
            if plan.dry_run:
                raise CommandError(
                    "purchase-missing-recap-fetch requires a non-dry-run budget plan"
                )
            if not acknowledge_fees:
                raise CommandError(
                    "purchase-missing-recap-fetch --execute requires "
                    "--acknowledge-pacer-fees"
                )
            if live_purchase:
                if courtlistener_fixture is not None or broker_fixture is not None:
                    raise CommandError(
                        "--live-purchase cannot be combined with offline fixtures"
                    )
                request_ledger = cast(Path | None, args.request_ledger)
                if request_ledger is None:
                    raise CommandError(
                        "--request-ledger is required with --live-purchase"
                    )
                max_wait = cast(float, args.request_budget_max_wait_seconds)
                if max_wait < 0:
                    raise CommandError(
                        "--request-budget-max-wait-seconds cannot be negative"
                    )
                courtlistener_config = CourtListenerRecapFetchConfig.from_env()
                # Validate the allowlisted, redirect-refusing transport before the
                # purchase journal is opened or any paid operation can be reserved.
                courtlistener_transport = UrlLibRecapFetchTransport(
                    courtlistener_config.base_url
                )
                purchase_broker = SignedRecapFetchPurchaseBroker(
                    RecapFetchBrokerConfig.from_env()
                )
                profile = cast(str, args.courtlistener_rate_profile)
                request_budget = CourtListenerRequestBudget(
                    request_ledger,
                    limits=_COURTLISTENER_RATE_PROFILES[profile],
                    max_wait_seconds=max_wait,
                )
                with CaseDevPurchaseJournal(
                    ledger_path, policy=purchase_policy
                ) as journal:
                    client = CourtListenerRecapFetchClient(
                        courtlistener_config,
                        journal=journal,
                        transport=courtlistener_transport,
                        purchase_broker=purchase_broker,
                        before_request=request_budget.before_request,
                    )
                    result = client.execute_purchase_plan(
                        plan,
                        public_documents=public_documents,
                        live=True,
                        acknowledge_pacer_fees=True,
                    )
            else:
                if courtlistener_fixture is None or broker_fixture is None:
                    raise CommandError(
                        "offline execution requires --courtlistener-fixture and "
                        "--purchase-broker-fixture"
                    )
                raw_broker_responses = _loads_json(
                    broker_fixture.read_text(encoding="utf-8")
                )
                if isinstance(raw_broker_responses, str) or not isinstance(
                    raw_broker_responses, Sequence
                ):
                    raise CommandError("purchase broker fixture must be a JSON array")
                broker_responses = tuple(
                    _mapping(item, "purchase broker fixture response")
                    for item in cast(Sequence[object], raw_broker_responses)
                )
                courtlistener_transport = FixtureRecapFetchTransport.from_jsonl(
                    courtlistener_fixture
                )
                purchase_broker = FixtureRecapFetchPurchaseBroker(broker_responses)
                with CaseDevPurchaseJournal(
                    ledger_path, policy=purchase_policy
                ) as journal:
                    client = CourtListenerRecapFetchClient(
                        CourtListenerRecapFetchConfig(api_token="offline-fixture"),
                        journal=journal,
                        transport=courtlistener_transport,
                        purchase_broker=purchase_broker,
                    )
                    result = client.execute_purchase_plan(
                        plan,
                        public_documents=public_documents,
                        live=True,
                        acknowledge_pacer_fees=True,
                    )
    except (
        CommandError,
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        CourtListenerRecapFetchError,
        CourtListenerRequestBudgetError,
        OSError,
        sqlite3.Error,
        UnicodeError,
        ValueError,
    ) as exc:
        if live_purchase:
            _write_acquisition_failure(
                args,
                stage="purchase-missing-recap-fetch",
                input_paths=input_paths,
                output_paths=(output_path, ledger_path),
                reason=str(exc),
                paid_activity_requested=True,
                paid_activity_executed=(
                    client is not None and client.paid_request_count > 0
                ),
                extra=_recap_fetch_rate_evidence(
                    args,
                    client=client,
                    budget=request_budget,
                    live=True,
                ),
            )
        elif not dry_run:
            _write_acquisition_failure(
                args,
                stage="purchase-missing-recap-fetch",
                input_paths=input_paths,
                output_paths=(output_path, ledger_path),
                reason=str(exc),
                paid_activity_requested=False,
                paid_activity_executed=False,
                extra=_recap_fetch_rate_evidence(
                    args,
                    client=client,
                    budget=None,
                    live=False,
                ),
            )
        raise CommandError(str(exc)) from exc

    paid_executed = (
        live_purchase and client is not None and client.paid_request_count > 0
    )
    rate_evidence = _recap_fetch_rate_evidence(
        args,
        client=client,
        budget=request_budget,
        live=live_purchase,
    )
    _write_json(output_path, result.to_record())
    _write_acquisition_completion(
        args,
        stage="purchase-missing-recap-fetch",
        input_paths=(plan_path, selection_path, policy_path),
        output_paths=(output_path,) if dry_run else (output_path, ledger_path),
        record_count=result.intended_purchase_count,
        dry_run=dry_run,
        paid_activity_requested=live_purchase,
        paid_activity_executed=paid_executed,
        extra={
            "executed_purchase_count": result.executed_purchase_count,
            **rate_evidence,
        },
    )
    return 0 if result.executed_purchase_count == result.intended_purchase_count else 2


def _cmd_acquisition_plan_docket_live_fetches(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    screening_paths = tuple(cast(list[Path], args.screening_candidates))
    fetch_paths = tuple(cast(list[Path], args.fetch_successes))
    ranking_paths = tuple(cast(list[Path], args.case_dev_ranking))
    advisory_paths = tuple(cast(list[Path], args.advisory_candidates))
    policy_path = cast(Path, args.cohort_policy)
    output_path = _acquisition_path(
        args,
        "plan_output",
        output_root / "docket-live-fetch-plan.json",
    )
    policy = _read_json_object(policy_path)
    try:
        verify_cohort_policy(policy)
    except CohortPolicyError as exc:
        raise CommandError(str(exc)) from exc
    dry_run = _acquisition_dry_run(args)
    input_paths = (
        *screening_paths,
        *fetch_paths,
        *ranking_paths,
        *advisory_paths,
        policy_path,
    )
    if dry_run:
        _write_json(
            output_path,
            {
                "stage": "plan-docket-live-fetches",
                "dry_run": True,
                "provider_requests": 0,
            },
        )
        record_count = 0
        projected_cost = "0.00"
        executable_count = 0
        executable_cost = "0.00"
    else:
        plan = plan_docket_live_fetches(
            screening_records=(
                record for path in screening_paths for record in _read_records(path)
            ),
            fetch_success_records=(
                record for path in fetch_paths for record in _read_records(path)
            ),
            ranking_records=(
                record for path in ranking_paths for record in _read_records(path)
            ),
            advisory_records=(
                record for path in advisory_paths for record in _read_records(path)
            ),
            cohort_policy=policy,
            docket_fetch_reservation_usd=cast(str, args.docket_fetch_reservation_usd),
            cycle_committed_spend_usd=cast(str, args.cycle_committed_spend_usd),
            daily_budget_usd=cast(str, args.daily_budget_usd),
            daily_committed_spend_usd=cast(str, args.daily_committed_spend_usd),
            spend_date_utc=cast(str, args.spend_date_utc),
            canonical_journal_path=str(
                (output_root / "case-dev-docket-live-fetch.sqlite3").resolve()
            ),
        )
        _write_json(output_path, plan.to_record())
        record_count = len(plan.items)
        projected_cost = plan.total_projected_cost_usd
        executable_count = len(plan.executable_items)
        executable_cost = plan.executable_projected_cost_usd
    _write_acquisition_completion(
        args,
        stage="plan-docket-live-fetches",
        input_paths=input_paths,
        output_paths=(output_path,),
        record_count=record_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "provider_requests": 0,
            "projected_cost_usd": projected_cost,
            "executable_count": executable_count,
            "executable_projected_cost_usd": executable_cost,
        },
    )
    return 0


def _cmd_acquisition_execute_docket_live_fetches(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    plan_path = cast(Path, args.docket_live_fetch_plan)
    journal_path = _acquisition_path(
        args,
        "journal",
        output_root / "case-dev-docket-live-fetch.sqlite3",
    )
    result_path = _acquisition_path(
        args,
        "result_output",
        output_root / "case-dev-docket-live-fetch-result.json",
    )
    plan = load_docket_live_fetch_plan(_read_json_object(plan_path))
    dry_run = _acquisition_dry_run(args)
    fixture_path = cast(Path | None, args.case_dev_fixture)
    live_case_dev = cast(bool, args.live_case_dev)
    acknowledge_fees = cast(bool, args.acknowledge_pacer_fees)
    if live_case_dev and fixture_path is None:
        raise CommandError(
            "legacy fee-bearing Case.dev docket fetch is disabled; use the "
            "CourtListener-first acquisition path"
        )
    if fixture_path is not None and live_case_dev:
        raise CommandError("case-dev fixture and live access are mutually exclusive")
    if not dry_run and not acknowledge_fees:
        raise CommandError(
            "execute-docket-live-fetches requires --acknowledge-pacer-fees"
        )
    if not dry_run and fixture_path is None and not live_case_dev:
        raise CommandError(
            "execute-docket-live-fetches requires --case-dev-fixture or --live-case-dev"
        )
    if dry_run:
        result = DocketLiveFetchExecutionResult(
            plan_sha256=plan.plan_sha256,
            intended_count=len(plan.executable_items),
            confirmed_count=0,
            statuses={
                item.docket_id: "planned_dry_run" for item in plan.executable_items
            },
            confirmed_candidates=(),
        )
        paid_requested = False
        paid_executed = False
    else:
        client = _case_dev_client(
            command="acquisition execute-docket-live-fetches",
            fixture_path=fixture_path,
            live=live_case_dev,
        )
        try:
            result = execute_docket_live_fetch_plan(
                plan,
                client=client,
                journal_path=journal_path,
                live=True,
                acknowledge_pacer_fees=True,
            )
        except (CaseDevClientError, DocketLiveFetchError, ValueError) as exc:
            paid_post_sent = live_case_dev and client.request_count > 0
            _write_acquisition_failure(
                args,
                stage="execute-docket-live-fetches",
                input_paths=(plan_path,),
                output_paths=(journal_path, result_path),
                reason=str(exc),
                paid_activity_requested=live_case_dev,
                paid_activity_executed=paid_post_sent,
            )
            raise CommandError(str(exc)) from exc
        paid_requested = live_case_dev
        paid_executed = live_case_dev and client.request_count > 0
    _write_json(result_path, result.to_record())
    outputs = (result_path,) if dry_run else (result_path, journal_path)
    _write_acquisition_completion(
        args,
        stage="execute-docket-live-fetches",
        input_paths=(plan_path,),
        output_paths=outputs,
        record_count=result.intended_count,
        dry_run=dry_run,
        paid_activity_requested=paid_requested,
        paid_activity_executed=paid_executed,
        extra={"confirmed_count": result.confirmed_count},
    )
    return 0


def _cmd_acquisition_recover_purchased(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    purchase_result_path = cast(Path, args.purchase_result)
    selection_path = cast(Path, args.selection)
    manifest_path = _acquisition_path(
        args,
        "manifest_output",
        output_root / "purchased-document-downloads.jsonl",
    )
    recovery_path = _acquisition_path(
        args,
        "recovery_output",
        output_root / "purchased-document-recovery.jsonl",
    )
    document_root = _acquisition_path(
        args,
        "document_output_root",
        output_root / "documents" / "purchased",
    )
    dry_run = _acquisition_dry_run(args)
    try:
        requests = purchased_document_recovery_requests_from_records(
            _read_json_object(purchase_result_path),
            _read_records(selection_path),
        )
    except PurchasedDocumentRecoveryError as exc:
        _write_acquisition_failure(
            args,
            stage="recover-purchased",
            input_paths=(purchase_result_path, selection_path),
            output_paths=(manifest_path, recovery_path, document_root),
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc
    if dry_run:
        _write_jsonl(
            manifest_path,
            [
                {
                    "stage": "recover-purchased",
                    "dry_run": True,
                    "request_count": len(requests),
                    "document_output_root": str(document_root),
                }
            ],
        )
        _write_jsonl(recovery_path, [])
        recovered_count = 0
    else:
        try:
            source = _purchased_document_source(
                fixture_path=cast(Path | None, args.fixture_documents),
                live_case_dev_download=cast(bool, args.live_case_dev_download),
                live_courtlistener_download=cast(
                    bool, args.live_courtlistener_download
                ),
            )
            records = recover_purchased_documents(
                requests,
                output_root=document_root,
                source=source,
                retrieved_at=datetime.now(UTC),
            )
            _write_jsonl(recovery_path, [record.to_record() for record in records])
            manifest = purchased_document_download_manifest_records(records)
            _write_jsonl(manifest_path, manifest)
        except (
            CommandError,
            PurchasedDocumentDownloadError,
            PurchasedDocumentRecoveryError,
        ) as exc:
            _write_acquisition_failure(
                args,
                stage="recover-purchased",
                input_paths=(purchase_result_path, selection_path),
                output_paths=(manifest_path, recovery_path, document_root),
                reason=str(exc),
                paid_activity_requested=False,
            )
            raise CommandError(str(exc)) from exc
        recovered_count = sum(
            record.status
            in {
                PurchasedDocumentRecoveryStatus.RECOVERED,
                PurchasedDocumentRecoveryStatus.RECOVERED_AUDIT_ONLY,
            }
            for record in records
        )
    intended_recovery_count = sum(
        request.purchase_attempt.status.value == "purchased" for request in requests
    )
    if not dry_run and recovered_count != intended_recovery_count:
        reason = (
            f"recovered {recovered_count} of {intended_recovery_count} "
            "purchased documents"
        )
        _write_acquisition_failure(
            args,
            stage="recover-purchased",
            input_paths=(purchase_result_path, selection_path),
            output_paths=(manifest_path, recovery_path, document_root),
            reason=reason,
            paid_activity_requested=False,
        )
        raise CommandError(reason)
    _write_acquisition_completion(
        args,
        stage="recover-purchased",
        input_paths=(purchase_result_path, selection_path),
        output_paths=(manifest_path, recovery_path, document_root),
        record_count=len(requests),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "intended_recovery_count": intended_recovery_count,
            "recovered_count": recovered_count,
        },
    )
    return 0


def _cmd_acquisition_disclosure_clearance(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    manifest_path = cast(Path, args.download_manifest)
    document_root = cast(Path, args.document_root)
    reviews_path = cast(Path, args.reviews)
    review_receipt_path = cast(Path, args.review_receipt)
    restriction_path = cast(Path, args.restriction_evidence)
    clearance_path = _acquisition_path(
        args, "clearance_output", output_root / "disclosure-clearance.jsonl"
    )
    quarantine_path = _acquisition_path(
        args, "quarantine_output", output_root / "disclosure-quarantine.jsonl"
    )
    documents = _read_records(manifest_path)
    reviews = _read_records(reviews_path)
    restrictions = _read_records(restriction_path)
    try:
        review_authority = validate_review_receipt(
            reviews_path.read_bytes(), _read_json_object(review_receipt_path)
        )
        records = build_clearance_records(
            documents,
            document_root=document_root,
            reviews=reviews,
            review_authority=review_authority,
            restriction_records=restrictions,
        )
    except (DisclosureClearanceError, OSError) as exc:
        raise CommandError(str(exc)) from exc
    clearance_rows = [record.to_record() for record in records]
    quarantined = [row for row in clearance_rows if row["status"] != "cleared"]
    dry_run = _acquisition_dry_run(args)
    if not dry_run:
        _write_jsonl(clearance_path, clearance_rows)
        _write_jsonl(quarantine_path, quarantined)
    source_commitments = {
        "download_manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": _path_sha256(manifest_path),
        },
        "reviews": {
            "path": str(reviews_path.resolve()),
            "sha256": _path_sha256(reviews_path),
        },
        "review_receipt": {
            "path": str(review_receipt_path.resolve()),
            "sha256": _path_sha256(review_receipt_path),
        },
        "restriction_evidence": {
            "path": str(restriction_path.resolve()),
            "sha256": _path_sha256(restriction_path),
        },
    }
    output_commitments = (
        {}
        if dry_run
        else {
            "disclosure_clearance": {
                "path": str(clearance_path.resolve()),
                "sha256": _path_sha256(clearance_path),
            },
            "disclosure_quarantine": {
                "path": str(quarantine_path.resolve()),
                "sha256": _path_sha256(quarantine_path),
            },
        }
    )
    _write_acquisition_completion(
        args,
        stage="clear-disclosures",
        input_paths=(
            manifest_path,
            reviews_path,
            review_receipt_path,
            restriction_path,
            document_root,
        ),
        output_paths=(clearance_path, quarantine_path),
        record_count=len(records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "quarantined_document_count": len(quarantined),
            "source_commitments": source_commitments,
            "output_commitments": output_commitments,
            "review_authority": {
                "reviewer_id": review_authority.reviewer_id,
                "controlled_store_uri": review_authority.controlled_store_uri,
                "authentication_method": review_authority.authentication_method,
                "authenticated_at": review_authority.authenticated_at,
                "review_artifact_sha256": (
                    "sha256:" + review_authority.review_artifact_sha256
                ),
            },
        },
    )
    return 0


def _cmd_acquisition_plan_parse_documents(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    download_manifest_path = cast(Path, args.download_manifest)
    clearance_path = cast(Path, args.disclosure_clearance)
    document_root = _acquisition_path(
        args,
        "document_root",
        output_root / "documents" / "free",
    )
    requests_path = _acquisition_path(
        args,
        "requests_output",
        output_root / "parse-document-requests.jsonl",
    )
    markdown_output_root = cast(Path, args.markdown_output_root)
    records = _read_records(download_manifest_path)
    try:
        require_cleared_documents(
            records,
            document_root=document_root,
            clearance_records=_read_records(clearance_path),
        )
    except (DisclosureClearanceError, OSError) as exc:
        raise CommandError(str(exc)) from exc
    request_records = tuple(
        _planned_parse_document_request(
            record,
            document_root=document_root,
            markdown_output_root=markdown_output_root,
        )
        for record in records
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            requests_path,
            [
                {
                    "stage": "plan-parse-documents",
                    "dry_run": True,
                    "request_count": len(request_records),
                }
            ],
        )
    else:
        _write_jsonl(requests_path, request_records)
    _write_acquisition_completion(
        args,
        stage="plan-parse-documents",
        input_paths=(download_manifest_path, clearance_path),
        output_paths=(requests_path,),
        record_count=len(request_records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_parse_documents(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    requests_path = cast(Path, args.requests)
    clearance_path = cast(Path, args.disclosure_clearance)
    manifest_path = _acquisition_path(
        args,
        "manifest_output",
        output_root / "mistral-markdown-conversions.jsonl",
    )
    request_records = _read_records(requests_path)
    if not _acquisition_dry_run(args):
        try:
            require_cleared_parse_requests(
                request_records, _read_records(clearance_path)
            )
            for request_record in request_records:
                verify_parse_request_bytes(request_record)
        except DisclosureClearanceError as exc:
            raise CommandError(str(exc)) from exc
    requests = tuple(
        _mistral_markdown_request(record, output_root=output_root)
        for record in request_records
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            manifest_path,
            [
                {
                    "stage": "parse-documents",
                    "dry_run": True,
                    "request_count": len(requests),
                    "parser_root": str(cast(Path | None, args.parser_root)),
                }
            ],
        )
    else:
        fixture_markdown_dir = cast(Path | None, args.fixture_markdown_dir)
        if fixture_markdown_dir is None:
            parser_root = cast(Path | None, args.parser_root)
            records = convert_documents_to_markdown(
                requests,
                config=MistralParserConfig(
                    parser_root=(
                        MistralParserConfig().parser_root
                        if parser_root is None
                        else parser_root
                    ),
                    timeout_seconds=cast(int, args.timeout_seconds),
                ),
            )
        else:
            records = _fixture_markdown_conversion_records(
                requests,
                fixture_markdown_dir=fixture_markdown_dir,
                generated_at=datetime.now(UTC),
            )
        _write_jsonl(
            manifest_path,
            [
                {
                    **record.to_record(),
                    "source_sha256": _required_str(request, "expected_sha256"),
                    "source_byte_count": _required_int(request, "expected_byte_count"),
                }
                for record, request in zip(records, request_records, strict=True)
            ],
        )
    _write_acquisition_completion(
        args,
        stage="parse-documents",
        input_paths=(requests_path, clearance_path),
        output_paths=(manifest_path,),
        record_count=len(requests),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _official_provider_cycle_caps(args: argparse.Namespace) -> ProviderCycleCaps:
    path = cast(Path | None, getattr(args, "provider_cycle_caps", None))
    if path is None:
        raise CommandError(
            "live LLM acquisition requires --provider-cycle-caps with a frozen "
            "externally bounded caps artifact"
        )
    try:
        return load_provider_cycle_caps(path)
    except ProviderJournalError as exc:
        raise CommandError(str(exc)) from exc


def _cmd_acquisition_llm_unitize(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    provider_journal_path = output_root / "provider-attempts.sqlite3"
    selection_path = cast(Path, args.selection)
    parser_manifest_path = cast(Path, args.parser_manifest)
    markdown_root = cast(Path | None, args.markdown_root) or (output_root / "markdown")
    model_registry_path = cast(Path, args.model_registry)
    provider_caps_path = cast(Path | None, args.provider_cycle_caps)
    prediction_units_path = _acquisition_path(
        args,
        "prediction_units_output",
        output_root / "prediction-units.jsonl",
    )
    audit_path = _acquisition_path(
        args,
        "audit_output",
        output_root / "llm-unitization-audit.jsonl",
    )
    review_queue_path = _acquisition_path(
        args,
        "unitization_review_queue_output",
        output_root / "unitization-review-queue.jsonl",
    )
    selection_records = _read_records(selection_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            prediction_units_path,
            [
                {
                    "stage": "llm-unitize",
                    "dry_run": True,
                    "selection_count": len(selection_records),
                    "model_registry": str(model_registry_path),
                    "model_key": cast(str, args.model_key),
                }
            ],
        )
        _write_jsonl(review_queue_path, [])
    else:
        registry_entry, registry_sha256 = _registry_entry_for_key(
            model_registry_path,
            cast(str, args.model_key),
        )
        provider_caps = _official_provider_cycle_caps(args)
        result = llm_unitize_cases(
            selection_records=selection_records,
            parser_records=_read_records(parser_manifest_path),
            markdown_root=markdown_root,
            registry_entry=registry_entry,
            model_registry_sha256=registry_sha256,
            timeout_seconds=cast(float, args.timeout_seconds),
            continue_on_error=cast(bool, args.continue_on_error),
            provider_journal_path=provider_journal_path,
            provider_cycle_caps_usd={
                registry_entry.provider: provider_caps.cap_usd(registry_entry.provider)
            },
        )
        _write_jsonl(prediction_units_path, result.records)
        _write_jsonl(audit_path, result.audit_records)
        _write_jsonl(
            review_queue_path,
            unitization_review_queue_records(result.audit_records),
        )
    _write_acquisition_completion(
        args,
        stage="llm-unitize",
        input_paths=(
            selection_path,
            parser_manifest_path,
            model_registry_path,
            *((provider_caps_path,) if provider_caps_path is not None else ()),
        ),
        output_paths=(
            prediction_units_path,
            audit_path,
            review_queue_path,
            provider_journal_path,
        ),
        record_count=len(selection_records),
        dry_run=dry_run,
        paid_activity_requested=not dry_run,
        paid_activity_executed=not dry_run,
    )
    return 0


def _cmd_acquisition_llm_label(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    provider_journal_path = output_root / "provider-attempts.sqlite3"
    selection_path = cast(Path, args.selection)
    parser_manifest_path = cast(Path, args.parser_manifest)
    prediction_units_path = cast(Path, args.prediction_units)
    markdown_root = cast(Path | None, args.markdown_root) or (output_root / "markdown")
    model_registry_path = cast(Path, args.model_registry)
    evaluated_registry_path = cast(Path, args.evaluated_model_registry)
    provider_caps_path = cast(Path | None, args.provider_cycle_caps)
    labels_path = _acquisition_path(
        args,
        "labels_output",
        output_root / "labels.jsonl",
    )
    audit_path = _acquisition_path(
        args,
        "audit_output",
        output_root / "llm-label-audit.jsonl",
    )
    lawyer_review_queue_path = _acquisition_path(
        args,
        "lawyer_review_queue_output",
        output_root / "lawyer-review-queue.jsonl",
    )
    selection_records = _read_records(selection_path)
    model_keys = tuple(cast(list[str], args.model_key))
    _require_explicit_unique_model_keys(model_keys)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            labels_path,
            [
                {
                    "stage": "llm-label",
                    "dry_run": True,
                    "selection_count": len(selection_records),
                    "model_registry": str(model_registry_path),
                    "model_keys": list(model_keys),
                }
            ],
        )
        _write_jsonl(lawyer_review_queue_path, [])
    else:
        registry_entries, registry_sha256 = _registry_entries_for_keys(
            model_registry_path,
            model_keys,
        )
        _require_complete_registry_panel(
            registry_entries,
            model_registry_path=model_registry_path,
        )
        _require_exact_model_disjoint_judges(
            registry_entries,
            evaluated_model_registry_path=evaluated_registry_path,
        )
        provider_caps = _official_provider_cycle_caps(args)
        caps_by_provider = {
            entry.provider: provider_caps.cap_usd(entry.provider)
            for entry in registry_entries
        }
        result = llm_label_cases(
            selection_records=selection_records,
            parser_records=_read_records(parser_manifest_path),
            prediction_unit_records=_read_records(prediction_units_path),
            markdown_root=markdown_root,
            registry_entries=registry_entries,
            model_registry_sha256=registry_sha256,
            consensus_policy=LlmConsensusPolicy(cast(str, args.consensus_policy)),
            high_confidence_threshold=cast(float, args.high_confidence_threshold),
            timeout_seconds=cast(float, args.timeout_seconds),
            continue_on_error=cast(bool, args.continue_on_error),
            provider_journal_path=provider_journal_path,
            provider_cycle_caps_usd=caps_by_provider,
        )
        _write_jsonl(labels_path, result.records)
        _write_jsonl(audit_path, result.audit_records)
        _write_jsonl(
            lawyer_review_queue_path,
            lawyer_review_queue_records(result.audit_records),
        )
    _write_acquisition_completion(
        args,
        stage="llm-label",
        input_paths=(
            selection_path,
            parser_manifest_path,
            prediction_units_path,
            model_registry_path,
            evaluated_registry_path,
            *((provider_caps_path,) if provider_caps_path is not None else ()),
        ),
        output_paths=(
            labels_path,
            audit_path,
            lawyer_review_queue_path,
            provider_journal_path,
        ),
        record_count=len(selection_records),
        dry_run=dry_run,
        paid_activity_requested=not dry_run,
        paid_activity_executed=not dry_run,
    )
    return 0


def _require_exact_model_disjoint_judges(
    judge_entries: Sequence[ModelRegistryEntry],
    *,
    evaluated_model_registry_path: Path,
) -> None:
    evaluated_entries = load_model_registry(evaluated_model_registry_path).entries
    evaluated_identities = {
        (entry.provider, entry.model_id, entry.model_version_or_snapshot)
        for entry in evaluated_entries
    }
    overlaps = sorted(
        entry.registry_key
        for entry in judge_entries
        if (entry.provider, entry.model_id, entry.model_version_or_snapshot)
        in evaluated_identities
    )
    if overlaps:
        raise CommandError(
            "Stage B judge panel is not exact-model disjoint from the evaluated "
            f"registry: {', '.join(overlaps)}"
        )


def _require_explicit_unique_model_keys(model_keys: Sequence[str]) -> None:
    normalized = tuple(key.strip() for key in model_keys)
    if not normalized or any(not key for key in normalized):
        raise CommandError("llm-label requires explicit non-empty --model-key values")
    if len(set(normalized)) != len(normalized):
        raise CommandError("llm-label judge --model-key values must be unique")


def _require_complete_registry_panel(
    judge_entries: Sequence[ModelRegistryEntry],
    *,
    model_registry_path: Path,
) -> None:
    frozen_keys = {
        entry.registry_key for entry in load_model_registry(model_registry_path).entries
    }
    selected_keys = {entry.registry_key for entry in judge_entries}
    if selected_keys != frozen_keys:
        raise CommandError(
            "llm-label must explicitly select every judge in the dedicated frozen "
            "judge registry"
        )


def _cmd_acquisition_llm_review_stage_a(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    provider_journal_path = output_root / "provider-attempts.sqlite3"
    selection_path = cast(Path, args.selection)
    parser_path = cast(Path, args.parser_manifest)
    units_path = cast(Path, args.prediction_units)
    existing_queue_path = cast(Path, args.unitization_review_queue)
    registry_path = cast(Path, args.model_registry)
    provider_caps_path = cast(Path | None, args.provider_cycle_caps)
    markdown_root = cast(Path | None, args.markdown_root) or output_root / "markdown"
    flags_path = _acquisition_path(
        args, "structural_flags_output", output_root / "stage-a-structural-flags.jsonl"
    )
    queue_path = _acquisition_path(
        args,
        "review_queue_output",
        output_root / "unitization-review-queue-reviewed.jsonl",
    )
    audit_path = _acquisition_path(
        args, "audit_output", output_root / "stage-a-structural-review-audit.jsonl"
    )
    selections = _read_records(selection_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(flags_path, [])
        _write_jsonl(queue_path, _read_records(existing_queue_path))
        _write_jsonl(
            audit_path,
            [
                {
                    "stage": "llm-review-stage-a",
                    "dry_run": True,
                    "selection_count": len(selections),
                }
            ],
        )
    else:
        entry, registry_sha = _registry_entry_for_key(
            registry_path, cast(str, args.model_key)
        )
        provider_caps = _official_provider_cycle_caps(args)
        result = llm_review_stage_a_units(
            selection_records=selections,
            parser_records=_read_records(parser_path),
            prediction_unit_records=_read_records(units_path),
            markdown_root=markdown_root,
            registry_entry=entry,
            model_registry_sha256=registry_sha,
            timeout_seconds=cast(float, args.timeout_seconds),
            provider_journal_path=provider_journal_path,
            provider_cycle_caps_usd={
                entry.provider: provider_caps.cap_usd(entry.provider)
            },
        )
        _write_jsonl(flags_path, result.records)
        _write_jsonl(audit_path, result.audit_records)
        _write_jsonl(
            queue_path,
            merge_structural_flags_into_review_queue(
                _read_records(existing_queue_path), result.records
            ),
        )
    _write_acquisition_completion(
        args,
        stage="llm-review-stage-a",
        input_paths=(
            selection_path,
            parser_path,
            units_path,
            existing_queue_path,
            registry_path,
            *((provider_caps_path,) if provider_caps_path is not None else ()),
        ),
        output_paths=(flags_path, queue_path, audit_path, provider_journal_path),
        record_count=len(selections),
        dry_run=dry_run,
        paid_activity_requested=not dry_run,
        paid_activity_executed=not dry_run,
    )
    return 0


def _cmd_acquisition_apply_unitization_review(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    prediction_units_path = cast(Path, args.prediction_units)
    review_queue_path = cast(Path, args.unitization_review_queue)
    adjudications_path = cast(Path, args.adjudications)
    finalized_path = _acquisition_path(
        args,
        "finalized_prediction_units_output",
        output_root / "finalized-prediction-units.jsonl",
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        record_count = 0
        _write_jsonl(finalized_path, [])
    else:
        try:
            finalized = apply_unitization_reviews(
                prediction_unit_records=_read_records(prediction_units_path),
                review_records=_read_records(review_queue_path),
                adjudication_records=_read_records(adjudications_path),
            )
        except UnitizationReviewError as exc:
            raise CommandError(str(exc)) from exc
        _write_jsonl(finalized_path, finalized)
        record_count = len(finalized)
    _write_acquisition_completion(
        args,
        stage="apply-unitization-review",
        input_paths=(prediction_units_path, review_queue_path, adjudications_path),
        output_paths=(finalized_path,),
        record_count=record_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_apply_lawyer_review(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    labels_path = cast(Path, args.labels)
    adjudications_path = cast(Path, args.adjudications)
    decision_texts_path = cast(Path, args.decision_texts)
    llm_label_audit_path = cast(Path, args.llm_label_audit)
    cycle_label_audit_plan_path = cast(Path | None, args.cycle_label_audit_plan)
    labeling_policy_path = cast(Path | None, args.labeling_policy)
    if cycle_label_audit_plan_path is not None and labeling_policy_path is None:
        raise CommandError(
            "--labeling-policy is required with --cycle-label-audit-plan"
        )
    labels_output_path = _acquisition_path(
        args,
        "labels_output",
        output_root / "labels-adjudicated.jsonl",
    )
    audit_path = _acquisition_path(
        args,
        "audit_output",
        output_root / "lawyer-review-resume-audit.jsonl",
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            labels_output_path,
            [
                {
                    "stage": "apply-lawyer-review",
                    "dry_run": True,
                    "labels": str(labels_path),
                    "adjudications": str(adjudications_path),
                    "llm_label_audit": str(llm_label_audit_path),
                }
            ],
        )
        _write_jsonl(audit_path, [])
    else:
        llm_label_audit_records = _read_records(llm_label_audit_path)
        if not llm_label_audit_records:
            raise CommandError("llm-label audit must include at least one record")
        adjudication_records = _read_records(adjudications_path)
        result = apply_adjudicated_reviews(
            label_records=_read_records(labels_path),
            adjudication_records=adjudication_records,
            decision_texts=_load_decision_texts(decision_texts_path),
            label_audit_records=(
                ()
                if cycle_label_audit_plan_path is not None
                else llm_label_audit_records
            ),
            audit_sample_size=cast(int, args.audit_sample_size),
            human_blind_disagreement_rate=cast(
                float,
                args.human_blind_disagreement_rate,
            ),
        )
        cycle_gate_records: tuple[JsonRecord, ...] = ()
        if cycle_label_audit_plan_path is not None:
            try:
                adjudications_by_review_id: dict[str, Mapping[str, Any]] = {}
                for record in adjudication_records:
                    review_id = _required_str(record, "review_id")
                    if review_id in adjudications_by_review_id:
                        raise CommandError(
                            f"duplicate lawyer adjudication row: {review_id}"
                        )
                    adjudications_by_review_id[review_id] = record
                validated_labeling_policy_path = cast(Path, labeling_policy_path)
                cycle_gate_records = evaluate_cycle_label_audit(
                    plan=_read_json_object(cycle_label_audit_plan_path),
                    label_audit_records=llm_label_audit_records,
                    adjudications_by_review_id=adjudications_by_review_id,
                    policy_record=_read_json_object(validated_labeling_policy_path),
                )
            except CycleLabelAuditError as exc:
                raise CommandError(str(exc)) from exc
        _write_jsonl(labels_output_path, result.records)
        _write_jsonl(audit_path, (*result.audit_records, *cycle_gate_records))
    _write_acquisition_completion(
        args,
        stage="apply-lawyer-review",
        input_paths=(
            labels_path,
            adjudications_path,
            decision_texts_path,
            llm_label_audit_path,
            *((cycle_label_audit_plan_path,) if cycle_label_audit_plan_path else ()),
            *((labeling_policy_path,) if labeling_policy_path else ()),
        ),
        output_paths=(labels_output_path, audit_path),
        record_count=len(_read_records(adjudications_path)) if not dry_run else 0,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_plan_label_audit(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    llm_audit_path = cast(Path, args.llm_label_audit)
    selection_path = cast(Path, args.selection)
    prediction_units_path = cast(Path, args.prediction_units)
    decision_texts_path = cast(Path, args.decision_texts)
    policy_path = cast(Path, args.labeling_policy)
    existing_queue_path = cast(Path, args.lawyer_review_queue)
    plan_path = _acquisition_path(
        args,
        "cycle_label_audit_plan_output",
        output_root / "cycle-label-audit-plan.json",
    )
    summary_path = _acquisition_path(
        args,
        "cycle_label_audit_summary_output",
        output_root / "cycle-label-audit-summary.json",
    )
    routing_summary_path = _acquisition_path(
        args,
        "adjudication_routing_summary_output",
        output_root / "adjudication-routing-summary.json",
    )
    planned_audit_path = _acquisition_path(
        args,
        "planned_llm_label_audit_output",
        output_root / "llm-label-audit-cycle-planned.jsonl",
    )
    queue_path = _acquisition_path(
        args,
        "lawyer_review_queue_output",
        output_root / "lawyer-review-queue-cycle-planned.jsonl",
    )
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_json(
            plan_path,
            {
                "stage": "plan-label-audit",
                "dry_run": True,
                "llm_label_audit": str(llm_audit_path),
                "labeling_policy": str(policy_path),
            },
        )
        _write_jsonl(planned_audit_path, [])
        _write_jsonl(queue_path, _read_records(existing_queue_path))
        _write_json(summary_path, {"stage": "plan-label-audit", "dry_run": True})
        _write_json(
            routing_summary_path,
            {"stage": "plan-label-audit", "dry_run": True},
        )
        record_count = 0
    else:
        try:
            plan, planned_audits, audit_queue = plan_cycle_label_audit(
                label_audit_records=_read_records(llm_audit_path),
                selection_records=_read_records(selection_path),
                finalized_prediction_unit_records=_read_records(prediction_units_path),
                decision_text_records=_read_records(decision_texts_path),
                policy_record=_read_json_object(policy_path),
            )
        except (CycleLabelAuditError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        existing_queue = _read_records(existing_queue_path)
        queue_by_review_id: dict[str, Mapping[str, Any]] = {}
        for record in (*existing_queue, *audit_queue):
            review_id = _required_str(record, "review_id")
            if review_id in queue_by_review_id:
                raise CommandError(f"duplicate lawyer review queue row: {review_id}")
            queue_by_review_id[review_id] = record
        _write_json(plan_path, plan)
        _write_jsonl(planned_audit_path, planned_audits)
        _write_jsonl(
            queue_path,
            [queue_by_review_id[key] for key in sorted(queue_by_review_id)],
        )
        _write_json(
            summary_path,
            {
                "schema_version": "legalforecast.cycle_label_audit_summary.v1",
                "cycle_id": plan["cycle_id"],
                "plan_sha256": plan["plan_sha256"],
                "labeling_policy_sha256": plan["labeling_policy_sha256"],
                "judge_registry_sha256": plan["judge_registry_sha256"],
                "ensemble_corpus_sha256": plan["ensemble_corpus_sha256"],
                "seed_sha256": plan["seed_sha256"],
                "population_count": plan["population_count"],
                "sample_count": plan["sample_count"],
                "strata": plan["strata"],
                "redacted": True,
            },
        )
        route_counts = Counter(
            _required_str(record, "route_reason")
            for record in queue_by_review_id.values()
        )
        _write_json(
            routing_summary_path,
            {
                "schema_version": "legalforecast.adjudication_routing_summary.v1",
                "cycle_id": plan["cycle_id"],
                "plan_sha256": plan["plan_sha256"],
                "total_routed_count": sum(route_counts.values()),
                "counts_by_reason": dict(sorted(route_counts.items())),
                "redacted": True,
            },
        )
        record_count = len(audit_queue)
    _write_acquisition_completion(
        args,
        stage="plan-label-audit",
        input_paths=(
            llm_audit_path,
            selection_path,
            prediction_units_path,
            decision_texts_path,
            policy_path,
            existing_queue_path,
        ),
        output_paths=(
            plan_path,
            summary_path,
            routing_summary_path,
            planned_audit_path,
            queue_path,
        ),
        record_count=record_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_plan_packet_inputs(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    selection_path = cast(Path, args.selection)
    download_manifest_path = cast(Path, args.download_manifest)
    parser_manifest_path = cast(Path, args.parser_manifest)
    prediction_units_path = cast(Path, args.prediction_units)
    model_registry_path = cast(Path, args.model_registry)
    raw_html_dir = cast(Path, args.raw_html_dir)
    raw_artifacts_manifest_path = cast(Path | None, args.raw_artifacts_manifest)
    document_root = cast(Path | None, args.document_root) or (
        output_root / "documents" / "free"
    )
    markdown_root = cast(Path | None, args.markdown_root) or (output_root / "markdown")
    packet_build_input_path = _acquisition_path(
        args,
        "packet_build_input_output",
        output_root / "packet-build-input.jsonl",
    )
    document_manifest_path = _acquisition_path(
        args,
        "document_manifest_output",
        output_root / "document-manifest.jsonl",
    )
    candidate_manifest_path = _acquisition_path(
        args,
        "candidate_manifest_output",
        output_root / "candidate-manifest.jsonl",
    )
    extracted_texts_path = _acquisition_path(
        args,
        "extracted_texts_output",
        output_root / "extracted_texts.jsonl",
    )
    exclusion_ledger_path = _acquisition_path(
        args,
        "exclusion_ledger_output",
        output_root / "exclusion-ledger.jsonl",
    )
    records = _read_records(selection_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            packet_build_input_path,
            [
                {
                    "stage": "plan-packet-inputs",
                    "dry_run": True,
                    "selection_count": len(records),
                }
            ],
        )
    else:
        generated_at = (
            _parse_datetime(cast(str, args.generated_at))
            if cast(str | None, args.generated_at)
            else datetime.now(UTC)
        )
        registry = load_model_registry(model_registry_path)
        official_entries = require_official_registry_entries(registry.entries)
        decision_filed_on_or_after = earliest_eligible_decision_date(official_entries)
        plan = plan_packet_build_inputs(
            selection_records=records,
            download_records=_read_records(download_manifest_path),
            parser_records=_read_records(parser_manifest_path),
            prediction_unit_records=_read_records(prediction_units_path),
            raw_html_dir=raw_html_dir,
            raw_artifact_records=(
                _read_records(raw_artifacts_manifest_path)
                if raw_artifacts_manifest_path is not None
                else None
            ),
            document_root=document_root,
            markdown_root=markdown_root,
            source_dir=output_root,
            generated_at=generated_at,
            search_query=cast(str, args.search_query),
            search_window=cast(str, args.search_window),
            decision_filed_on_or_after=decision_filed_on_or_after,
        )
        _write_jsonl(packet_build_input_path, plan.packet_build_records)
        _write_jsonl(document_manifest_path, plan.document_manifest_records)
        _write_jsonl(candidate_manifest_path, plan.candidate_manifest_records)
        _write_jsonl(extracted_texts_path, plan.extracted_text_records)
        _write_jsonl(exclusion_ledger_path, plan.exclusion_ledger_records)
    _write_acquisition_completion(
        args,
        stage="plan-packet-inputs",
        input_paths=(
            selection_path,
            download_manifest_path,
            parser_manifest_path,
            prediction_units_path,
            model_registry_path,
            *(
                (raw_artifacts_manifest_path,)
                if raw_artifacts_manifest_path is not None
                else ()
            ),
            raw_html_dir,
        ),
        output_paths=(
            packet_build_input_path,
            document_manifest_path,
            candidate_manifest_path,
            extracted_texts_path,
            exclusion_ledger_path,
        ),
        record_count=len(records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "model_registry_path": str(model_registry_path.resolve()),
            "model_registry_sha256": sha256_file(model_registry_path),
            **(
                {
                    "raw_artifacts_manifest_path": str(
                        raw_artifacts_manifest_path.resolve()
                    ),
                    "raw_artifacts_manifest_sha256": sha256_file(
                        raw_artifacts_manifest_path
                    ),
                }
                if raw_artifacts_manifest_path is not None
                else {}
            ),
        },
    )
    return 0


def _cmd_acquisition_build_packets(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    input_path = cast(Path, args.input)
    packets_path = _acquisition_path(
        args,
        "packets_output",
        output_root / "packets.jsonl",
    )
    case_packets_path = _acquisition_path(
        args,
        "case_packets_output",
        output_root / "case-packets.jsonl",
    )
    audit_path = _acquisition_path(
        args,
        "audit_output",
        output_root / "packet-audit.jsonl",
    )
    records = _read_records(input_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        _write_jsonl(
            packets_path,
            [
                {
                    "stage": "build-packets",
                    "dry_run": True,
                    "record_count": len(records),
                    "case_packets_output": str(case_packets_path),
                    "audit_output": str(audit_path),
                }
            ],
        )
    else:
        assemblies = tuple(
            _model_packet_assembly(
                record,
                ablation=PacketAblation(cast(str, args.ablation)),
            )
            for record in records
        )
        _write_jsonl(
            packets_path,
            [assembly.model_packet.to_record() for assembly in assemblies],
        )
        _write_jsonl(
            case_packets_path,
            [assembly.case_packet.to_record() for assembly in assemblies],
        )
        _write_jsonl(
            audit_path,
            [assembly.audit_bundle for assembly in assemblies],
        )
    _write_acquisition_completion(
        args,
        stage="build-packets",
        input_paths=(input_path,),
        output_paths=(packets_path, case_packets_path, audit_path),
        record_count=len(records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
    )
    return 0


def _cmd_acquisition_finalize_corpus(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    selection_path = cast(Path, args.selection)
    parser_manifest_path = cast(Path, args.parser_manifest)
    disclosure_clearance_path = cast(Path, args.disclosure_clearance)
    markdown_root = cast(Path, args.markdown_root)
    raw_prediction_units_path = cast(Path, args.raw_prediction_units)
    prediction_units_path = cast(Path, args.prediction_units)
    unitization_audit_path = cast(Path, args.llm_unitization_audit)
    original_unitization_review_path = cast(
        Path, args.original_unitization_review_queue
    )
    structural_flags_path = cast(Path, args.stage_a_structural_flags)
    structural_review_audit_path = cast(Path, args.stage_a_structural_review_audit)
    structural_review_registry_path = cast(Path, args.stage_a_review_model_registry)
    structural_review_model_key = cast(str, args.stage_a_review_model_key)
    unitization_review_path = cast(Path, args.unitization_review_queue)
    unitization_adjudications_path = cast(
        Path,
        args.unitization_review_adjudications,
    )
    labels_path = cast(Path, args.labels)
    label_audit_path = cast(Path, args.llm_label_audit)
    stage_b_judge_registry_path = cast(Path, args.stage_b_judge_registry)
    labeling_policy_path = cast(Path, args.labeling_policy)
    lawyer_review_path = cast(Path, args.lawyer_review_queue)
    lawyer_review_audit_path = cast(Path, args.lawyer_review_audit)
    packet_build_input_path = cast(Path, args.packet_build_input)
    packets_path = cast(Path, args.packets)
    model_registry_path = cast(Path, args.model_registry)
    screened_cases_path = cast(Path, args.screened_cases)
    discovery_summary_path = cast(Path, args.discovery_summary)
    discovery_exclusions_path = cast(Path, args.discovery_exclusions)
    exclusion_paths = tuple(cast(list[Path], args.exclusion_source))
    complete_ledger_path = _acquisition_path(
        args,
        "complete_exclusion_ledger_output",
        output_root / "complete-exclusion-ledger.jsonl",
    )
    readiness_path = _acquisition_path(
        args,
        "readiness_output",
        output_root / "corpus-readiness.json",
    )
    input_paths = (
        selection_path,
        parser_manifest_path,
        disclosure_clearance_path,
        markdown_root,
        raw_prediction_units_path,
        prediction_units_path,
        unitization_audit_path,
        original_unitization_review_path,
        structural_flags_path,
        structural_review_audit_path,
        structural_review_registry_path,
        unitization_review_path,
        unitization_adjudications_path,
        labels_path,
        label_audit_path,
        stage_b_judge_registry_path,
        labeling_policy_path,
        lawyer_review_path,
        lawyer_review_audit_path,
        packet_build_input_path,
        packets_path,
        model_registry_path,
        screened_cases_path,
        discovery_summary_path,
        discovery_exclusions_path,
        *exclusion_paths,
    )
    dry_run = _acquisition_dry_run(args)
    target_clean_cases = cast(int, args.target_clean_cases)
    if dry_run:
        _write_jsonl(complete_ledger_path, [])
        _write_json(
            readiness_path,
            {
                "stage": "finalize-corpus",
                "dry_run": True,
                "required_clean_count": target_clean_cases,
                "exclusion_source_count": len(exclusion_paths),
            },
        )
        clean_count = 0
        meets_target = False
    else:
        selection_records = _read_records(selection_path)
        parser_records = _read_records(parser_manifest_path)
        clearance_records = _read_records(disclosure_clearance_path)
        try:
            require_cleared_parser_records(parser_records, clearance_records)
        except DisclosureClearanceError as exc:
            raise CommandError(str(exc)) from exc
        prediction_unit_records = _read_records(prediction_units_path)
        raw_prediction_unit_records = _read_records(raw_prediction_units_path)
        unitization_audit_records = _read_records(unitization_audit_path)
        original_unitization_review_records = _read_records(
            original_unitization_review_path
        )
        structural_flag_records = _read_records(structural_flags_path)
        structural_review_audit_records = _read_records(structural_review_audit_path)
        unitization_review_records = _read_records(unitization_review_path)
        unitization_adjudication_records = _read_records(unitization_adjudications_path)
        try:
            structural_review_registry = load_model_registry(
                structural_review_registry_path
            )
            verify_stage_a_readiness_provenance(
                selection_records=selection_records,
                raw_prediction_unit_records=raw_prediction_unit_records,
                original_review_records=original_unitization_review_records,
                structural_flag_records=structural_flag_records,
                structural_review_audit_records=structural_review_audit_records,
                merged_review_records=unitization_review_records,
                finalized_prediction_unit_records=prediction_unit_records,
                adjudication_records=unitization_adjudication_records,
                reviewer_registry_entries=structural_review_registry.entries,
                reviewer_registry_sha256=sha256_file(structural_review_registry_path),
                reviewer_model_key=structural_review_model_key,
            )
        except (ReadinessProvenanceError, UnitizationReviewError) as exc:
            raise CommandError(str(exc)) from exc
        label_records = _read_records(labels_path)
        label_audit_records = _read_records(label_audit_path)
        lawyer_review_records = _read_records(lawyer_review_path)
        lawyer_review_audit_records = _read_records(lawyer_review_audit_path)
        packet_build_records = _read_records(packet_build_input_path)
        packet_records = _read_records(packets_path)
        screened_case_records = _read_records(screened_cases_path)
        discovery_summary = _read_json_object(discovery_summary_path)
        discovery_exclusion_records = _read_records(discovery_exclusions_path)
        exclusion_groups = tuple(_read_records(path) for path in exclusion_paths)
        ledger = merge_exclusion_ledger_records(
            discovery_exclusion_records,
            *exclusion_groups,
            parser_records,
            label_audit_records,
            lawyer_review_records,
        )
        complete_ledger_records = ledger.to_records()
        _write_jsonl(complete_ledger_path, complete_ledger_records)
        try:
            _validate_acquisition_discovery_reconciliation(
                screened_case_records=screened_case_records,
                discovery_summary=discovery_summary,
                discovery_exclusion_records=discovery_exclusion_records,
                selection_records=selection_records,
                complete_ledger_records=complete_ledger_records,
            )
        except CommandError as exc:
            _write_acquisition_failure(
                args,
                stage="finalize-corpus",
                input_paths=input_paths,
                output_paths=(complete_ledger_path, readiness_path),
                reason=str(exc),
                paid_activity_requested=False,
            )
            raise

        registry = load_model_registry(model_registry_path)
        official_entries = require_official_registry_entries(registry.entries)
        decision_texts = _load_readiness_decision_texts(
            selection_records=selection_records,
            parser_records=parser_records,
            prediction_unit_records=prediction_unit_records,
            label_records=label_records,
            markdown_root=markdown_root,
        )
        try:
            stage_b_judge_registry = load_model_registry(stage_b_judge_registry_path)
            verify_labeling_policy(
                _read_json_object(labeling_policy_path),
                judge_registry_path=stage_b_judge_registry_path,
            )
            verify_stage_b_readiness_provenance(
                finalized_prediction_unit_records=prediction_unit_records,
                label_audit_records=label_audit_records,
                judge_registry_entries=stage_b_judge_registry.entries,
                judge_registry_sha256=sha256_file(stage_b_judge_registry_path),
                decision_text_by_candidate_and_document=decision_texts,
            )
        except (ReadinessProvenanceError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        report = build_clean_corpus_readiness(
            selection_records=selection_records,
            parser_records=parser_records,
            prediction_unit_records=prediction_unit_records,
            unitization_audit_records=unitization_audit_records,
            unitization_review_records=unitization_review_records,
            unitization_adjudication_records=unitization_adjudication_records,
            label_records=label_records,
            label_audit_records=label_audit_records,
            lawyer_review_records=lawyer_review_records,
            lawyer_review_audit_records=lawyer_review_audit_records,
            packet_build_records=packet_build_records,
            packet_records=packet_records,
            exclusion_records=complete_ledger_records,
            decision_text_by_candidate_and_document=decision_texts,
            decision_filed_on_or_after=earliest_eligible_decision_date(
                official_entries
            ),
            required_clean_count=target_clean_cases,
        )
        readiness_exclusion_records = _readiness_exclusion_records(
            report,
            selection_records=selection_records,
            existing_ledger_records=complete_ledger_records,
        )
        if readiness_exclusion_records:
            ledger = merge_exclusion_ledger_records(
                complete_ledger_records,
                readiness_exclusion_records,
            )
            complete_ledger_records = ledger.to_records()
            _write_jsonl(complete_ledger_path, complete_ledger_records)
            report = build_clean_corpus_readiness(
                selection_records=selection_records,
                parser_records=parser_records,
                prediction_unit_records=prediction_unit_records,
                unitization_audit_records=unitization_audit_records,
                unitization_review_records=unitization_review_records,
                unitization_adjudication_records=unitization_adjudication_records,
                label_records=label_records,
                label_audit_records=label_audit_records,
                lawyer_review_records=lawyer_review_records,
                lawyer_review_audit_records=lawyer_review_audit_records,
                packet_build_records=packet_build_records,
                packet_records=packet_records,
                exclusion_records=complete_ledger_records,
                decision_text_by_candidate_and_document=decision_texts,
                decision_filed_on_or_after=earliest_eligible_decision_date(
                    official_entries
                ),
                required_clean_count=target_clean_cases,
            )
        _write_json(readiness_path, report.to_record())
        clean_count = report.clean_count
        meets_target = report.meets_target
        if not meets_target:
            _write_acquisition_failure(
                args,
                stage="finalize-corpus",
                input_paths=input_paths,
                output_paths=(complete_ledger_path, readiness_path),
                reason=(
                    f"corpus requires {target_clean_cases} clean motions; "
                    f"found {clean_count}"
                ),
                paid_activity_requested=False,
            )
        require_clean_corpus_ready(report)

    _write_acquisition_completion(
        args,
        stage="finalize-corpus",
        input_paths=input_paths,
        output_paths=(complete_ledger_path, readiness_path),
        record_count=clean_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "target_clean_cases": target_clean_cases,
            "clean_count": clean_count,
            "meets_target": meets_target,
        },
    )
    return 0


def _readiness_exclusion_records(
    report: CorpusReadinessReport,
    *,
    selection_records: Sequence[Mapping[str, Any]],
    existing_ledger_records: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    selections = {
        _required_str(record, "candidate_id"): record for record in selection_records
    }
    recorded_reasons: dict[str, set[str]] = {}
    for record in existing_ledger_records:
        candidate_id = _required_str(record, "candidate_id")
        reasons = recorded_reasons.setdefault(candidate_id, set())
        reasons.add(_required_str(record, "primary_exclusion_reason"))
        reasons.update(_required_str_tuple(record, "secondary_exclusion_reasons"))

    records: list[JsonRecord] = []
    for candidate_id in report.excluded_candidate_ids:
        reasons = report.exclusion_reasons.get(candidate_id, ())
        missing_reasons = tuple(
            reason
            for reason in reasons
            if reason not in recorded_reasons.get(candidate_id, set())
        )
        if not missing_reasons:
            continue
        selection = selections[candidate_id]
        primary_reason = missing_reasons[0]
        records.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "court": _optional_str(selection, "court"),
                "stage": _readiness_exclusion_stage(primary_reason),
                "primary_exclusion_reason": primary_reason,
                "reason": primary_reason,
                "secondary_exclusion_reasons": list(missing_reasons[1:]),
                "source_entry_ids": [],
                "source_document_ids": [],
                "notes": (
                    "Final clean-corpus readiness excluded the candidate: "
                    + "; ".join(missing_reasons)
                    + "."
                ),
            }
        )
    return records


def _readiness_exclusion_stage(reason: str) -> str:
    if reason.startswith(("required_document_", "parse_")):
        return "extraction"
    if reason.startswith("stage_a_"):
        return "unitization"
    if reason.startswith(
        ("stage_b_", "label_", "labeling_", "first_written_", "lawyer_review_")
    ):
        return "labeling"
    if reason in {"packet_build_input_missing", "built_packet_missing"}:
        return "case_mix"
    if reason == "outcome_leakage":
        return "leakage"
    return "eligibility"


def _validate_acquisition_discovery_reconciliation(
    *,
    screened_case_records: Sequence[Mapping[str, Any]],
    discovery_summary: Mapping[str, Any],
    discovery_exclusion_records: Sequence[Mapping[str, Any]],
    selection_records: Sequence[Mapping[str, Any]],
    complete_ledger_records: Sequence[Mapping[str, Any]],
) -> None:
    screened_ids = tuple(
        _required_str(_required_record(record, "candidate"), "docket_id")
        for record in screened_case_records
    )
    discovery_exclusion_ids = tuple(
        _required_str(record, "candidate_id") for record in discovery_exclusion_records
    )
    selection_ids = tuple(
        _required_str(record, "candidate_id") for record in selection_records
    )
    ledger_ids = tuple(
        _required_str(record, "candidate_id") for record in complete_ledger_records
    )
    for label, candidate_ids in (
        ("screened cases", screened_ids),
        ("discovery exclusions", discovery_exclusion_ids),
        ("selection", selection_ids),
        ("complete exclusion ledger", ledger_ids),
    ):
        if len(candidate_ids) != len(set(candidate_ids)):
            raise CommandError(f"duplicate candidate_id in {label}")

    accepted_count = _required_int(discovery_summary, "accepted_case_count")
    excluded_count = _required_int(discovery_summary, "excluded_case_count")
    processed_count = _required_int(discovery_summary, "processed_candidate_count")
    if accepted_count != len(screened_ids):
        raise CommandError(
            "discovery accepted_case_count does not match screened-cases JSONL"
        )
    if excluded_count != len(discovery_exclusion_ids):
        raise CommandError(
            "discovery excluded_case_count does not match discovery-exclusions JSONL"
        )
    if processed_count != accepted_count + excluded_count:
        raise CommandError(
            "discovery processed_candidate_count must equal accepted plus excluded"
        )

    screened = set(screened_ids)
    discovery_excluded = set(discovery_exclusion_ids)
    if screened & discovery_excluded:
        raise CommandError(
            "candidate appears in both screened and discovery exclusions"
        )
    discovered = screened | discovery_excluded
    if len(discovered) != processed_count:
        raise CommandError(
            "discovery candidate IDs do not reconcile to processed count"
        )

    selected = set(selection_ids)
    ledgered = set(ledger_ids)
    unknown_selected = sorted(selected - screened)
    if unknown_selected:
        raise CommandError(
            "selected candidates absent from screened discovery: "
            + ", ".join(unknown_selected)
        )
    unknown_ledgered = sorted(ledgered - discovered)
    if unknown_ledgered:
        raise CommandError(
            "ledger candidates absent from discovery: " + ", ".join(unknown_ledgered)
        )
    unreconciled = sorted(screened - selected - ledgered)
    if unreconciled:
        raise CommandError(
            "unreconciled screened candidates: " + ", ".join(unreconciled)
        )


def _load_readiness_decision_texts(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    prediction_unit_records: Sequence[Mapping[str, Any]],
    label_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
) -> dict[tuple[str, str], str]:
    selections = {
        _required_str(record, "candidate_id"): record for record in selection_records
    }
    parser_by_key = {
        (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        ): record
        for record in parser_records
    }
    candidate_by_unit: dict[str, str] = {}
    for record in prediction_unit_records:
        candidate_id = _required_str(record, "candidate_id")
        units = (
            _required_record_sequence(record, "prediction_units")
            if "prediction_units" in record
            else (record,)
        )
        for unit in units:
            unit_id = _required_str(unit, "unit_id")
            if unit_id in candidate_by_unit:
                raise CommandError(f"duplicate prediction unit: {unit_id}")
            candidate_by_unit[unit_id] = candidate_id

    root = markdown_root.expanduser().resolve()
    decision_texts: dict[tuple[str, str], str] = {}
    for label in label_records:
        unit_id = _required_str(label, "unit_id")
        try:
            candidate_id = candidate_by_unit[unit_id]
            selection = selections[candidate_id]
        except KeyError as exc:
            raise CommandError(
                f"label unit is not joined to a selected candidate: {unit_id}"
            ) from exc
        document_id = _required_str(label, "first_written_disposition_id")
        documents = {
            _required_str(document, "source_document_id"): document
            for document in _required_record_sequence(selection, "documents")
        }
        try:
            document = documents[document_id]
        except KeyError as exc:
            raise CommandError(
                "locked first disposition is absent from selection: "
                f"{candidate_id}/{document_id}"
            ) from exc
        role = _required_str(document, "document_role")
        if not _optional_bool(
            document,
            "contains_target_outcome",
            default=role in {DocumentRole.DECISION.value, DocumentRole.ORDER.value},
        ):
            raise CommandError(
                "locked first disposition is not marked as target-outcome material: "
                f"{candidate_id}/{document_id}"
            )
        parser_record = parser_by_key.get((candidate_id, document_id))
        if parser_record is None or parser_record.get("status") != "succeeded":
            continue
        markdown_path = Path(_required_str(parser_record, "markdown_path"))
        resolved = (
            markdown_path.expanduser().resolve()
            if markdown_path.is_absolute()
            else (root / markdown_path).resolve()
        )
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise CommandError(
                f"parser Markdown escapes --markdown-root: {resolved}"
            ) from exc
        if not resolved.is_file():
            raise CommandError(f"parser Markdown is missing: {resolved}")
        text = resolved.read_text(encoding="utf-8")
        if not text.strip():
            raise CommandError(f"parser Markdown is empty: {resolved}")
        key = (candidate_id, document_id)
        existing = decision_texts.get(key)
        if existing is not None and existing != text:
            raise CommandError(
                f"conflicting parser Markdown for {candidate_id}/{document_id}"
            )
        decision_texts[key] = text
    return decision_texts


def _registry_entry_for_key(
    model_registry_path: Path,
    model_key: str,
) -> tuple[ModelRegistryEntry, str]:
    entries, digest = _registry_entries_for_keys(model_registry_path, (model_key,))
    return entries[0], digest


def _registry_entries_for_keys(
    model_registry_path: Path,
    model_keys: Sequence[str],
) -> tuple[tuple[ModelRegistryEntry, ...], str]:
    registry = load_model_registry(model_registry_path)
    digest = sha256_file(model_registry_path)
    keys = tuple(key for key in model_keys if key.strip())
    if not keys:
        return registry.entries, digest
    entries: list[ModelRegistryEntry] = []
    for key in keys:
        provider, separator, model_id = key.partition(":")
        if not separator or not provider or not model_id:
            raise CommandError("model-key must use provider:model_id")
        try:
            entries.append(registry.get(provider, model_id))
        except KeyError as exc:
            raise CommandError(f"model-key not found in registry: {key}") from exc
    return tuple(entries), digest


def _case_dev_client(
    *,
    command: str,
    fixture_path: Path | None,
    live: bool,
    rate_limiter: CaseDevRateLimiter | None = None,
) -> CaseDevClient:
    if fixture_path is not None:
        return CaseDevClient(
            config=CaseDevConfig.from_env(),
            transport=CaseDevFixtureTransport.from_jsonl(fixture_path),
        )
    if not live:
        raise CommandError(
            f"{command} requires --case-dev-fixture for offline runs or --live "
            "with CASE_DEV_API_KEY configured"
        )
    return CaseDevClient(
        config=CaseDevConfig.from_env(require_api_key=True),
        rate_limiter=rate_limiter,
    )


def _dry_run_case_dev_client() -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=CaseDevFixtureTransport([]),
    )


def _firecrawl_fixture_transport(path: Path) -> FirecrawlFixtureTransport:
    responses: list[FirecrawlHTTPResponse] = []
    for record in _read_records(path):
        status_code = record.get("status_code")
        payload = record.get("payload")
        headers = record.get("headers", {})
        if (
            not isinstance(status_code, int)
            or isinstance(status_code, bool)
            or not isinstance(payload, Mapping)
            or not isinstance(headers, Mapping)
        ):
            raise CommandError(
                "Firecrawl fixture records require integer status_code and "
                "object payload/headers"
            )
        header_mapping = cast(Mapping[object, object], headers)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in header_mapping.items()
        ):
            raise CommandError("Firecrawl fixture headers must map strings to strings")
        normalized_headers = {
            cast(str, key): cast(str, value) for key, value in header_mapping.items()
        }
        responses.append(
            FirecrawlHTTPResponse(
                status_code=status_code,
                payload=cast(Mapping[str, Any], payload),
                headers=normalized_headers,
            )
        )
    return FirecrawlFixtureTransport(responses)


def _acquisition_output_root(args: argparse.Namespace) -> Path:
    root = cast(Path, args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _acquisition_path(
    args: argparse.Namespace,
    attribute_name: str,
    default_path: Path,
) -> Path:
    value = cast(Path | None, getattr(args, attribute_name))
    return default_path if value is None else value


def _acquisition_dry_run(args: argparse.Namespace) -> bool:
    return not cast(bool, args.execute)


def _iso_date_argument(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"{flag} must be an ISO date (YYYY-MM-DD)") from exc


def _case_mix_share_argument(value: str) -> Decimal:
    try:
        share = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "must be a finite decimal greater than 0 and at most 1"
        ) from exc
    if not share.is_finite() or share <= 0 or share > 1:
        raise argparse.ArgumentTypeError(
            "must be a finite decimal greater than 0 and at most 1"
        )
    return share


def _cycle_acquisition_policy(*, anchor: date) -> JsonRecord:
    """Return source-neutral identity shared by every Cycle 1 acquisition stage."""

    return {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": anchor.isoformat(),
        "screening_source_sha256": _current_screening_source_sha256(),
    }


def _current_screening_source_sha256() -> dict[str, str]:
    package_root = Path(__file__).resolve().parent
    screening_sources = {
        "mtd_acquisition_screen": package_root
        / "ingestion"
        / "mtd_acquisition_screen.py",
        "courtlistener_acquisition": package_root
        / "ingestion"
        / "courtlistener_acquisition.py",
        "restricted_material": package_root / "ingestion" / "restricted_material.py",
        "contamination_filters": package_root
        / "selection"
        / "contamination_filters.py",
        "motion_linkage": package_root / "selection" / "motion_linkage.py",
    }
    return {name: sha256_file(path) for name, path in sorted(screening_sources.items())}


def _file_commitment(path: Path) -> JsonRecord:
    payload = path.read_bytes()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": payload.count(b"\n"),
    }


def _courtlistener_candidate_id(record: Mapping[str, Any]) -> str:
    candidate_value = record.get("candidate")
    if not isinstance(candidate_value, Mapping):
        raise ValueError("screened CourtListener case is missing candidate metadata")
    candidate = cast(Mapping[str, object], candidate_value)
    docket_id = candidate.get("docket_id")
    if not isinstance(docket_id, str) or not docket_id.strip():
        raise ValueError("screened CourtListener case is missing its docket ID")
    return docket_id.strip()


def _courtlistener_raw_artifact_records(
    *,
    raw_html_dir: Path,
    screened_cases: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    candidate_ids = {
        *(_courtlistener_candidate_id(record) for record in screened_cases),
        *(_required_str(record, "candidate_id") for record in exclusions),
    }
    records: list[JsonRecord] = []
    if not raw_html_dir.is_dir():
        if screened_cases:
            raise ValueError(
                f"raw CourtListener HTML directory is missing: {raw_html_dir}"
            )
        return records
    for path in sorted(raw_html_dir.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file() or path.suffix != ".html":
            raise ValueError(f"unexpected raw CourtListener artifact: {path}")
        candidate_id = path.stem
        if candidate_id not in candidate_ids:
            raise ValueError(
                f"raw CourtListener artifact has no reconciled outcome: {path}"
            )
        payload = path.read_bytes()
        _validate_raw_docket_bytes(payload)
        records.append(
            {
                "candidate_id": candidate_id,
                "relative_path": path.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_count": len(payload),
            }
        )
    raw_candidate_ids = {_required_str(record, "candidate_id") for record in records}
    missing_accepted = sorted(
        _courtlistener_candidate_id(record)
        for record in screened_cases
        if _courtlistener_candidate_id(record) not in raw_candidate_ids
    )
    if missing_accepted:
        raise ValueError(
            "accepted CourtListener cases are missing raw HTML: "
            + ", ".join(missing_accepted)
        )
    return records


def _validate_frozen_screening_policy(
    *,
    policy: Mapping[str, object],
    anchor: date,
) -> None:
    frozen_anchor = policy.get("eligibility_anchor")
    if frozen_anchor != anchor.isoformat():
        raise ConfigMismatchError(
            "screening anchor does not match frozen cycle policy: "
            f"expected {frozen_anchor!r}, got {anchor.isoformat()!r}"
        )
    frozen_hashes = policy.get("screening_source_sha256")
    current_hashes = _current_screening_source_sha256()
    if frozen_hashes != current_hashes:
        raise ConfigMismatchError(
            "current screening sources do not match frozen cycle policy"
        )


def _validate_firecrawl_success_commitments(
    success_records: Sequence[Mapping[str, Any]],
) -> None:
    for row_number, record in enumerate(success_records, start=1):
        if record.get("pagination_complete_for_anchor_window") is not True:
            raise ValueError(
                "Firecrawl success rows must prove paginated completeness for the "
                f"anchor window; row {row_number} is legacy or incomplete"
            )
        sha256_value = record.get("raw_html_sha256")
        if (
            not isinstance(sha256_value, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", sha256_value) is None
        ):
            raise ValueError(
                "raw_html_sha256 must be a canonical sha256:<lowercase-hex> "
                f"commitment in Firecrawl success row {row_number}"
            )
        byte_count = record.get("raw_html_bytes")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ValueError(
                "raw_html_bytes must be a non-negative integer in Firecrawl "
                f"success row {row_number}"
            )
        retrieved_at = record.get("retrieved_at")
        if not isinstance(retrieved_at, str) or not retrieved_at.strip():
            raise ValueError(
                "retrieved_at must be a canonical UTC ISO timestamp in Firecrawl "
                f"success row {row_number}"
            )
        try:
            parsed = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "retrieved_at must be a canonical UTC ISO timestamp in Firecrawl "
                f"success row {row_number}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError(
                "retrieved_at must be a canonical UTC ISO timestamp in Firecrawl "
                f"success row {row_number}"
            )
        canonical_values = {
            parsed.astimezone(UTC).isoformat(),
            _iso_datetime(parsed),
        }
        if retrieved_at not in canonical_values:
            raise ValueError(
                "retrieved_at must be a canonical UTC ISO timestamp in Firecrawl "
                f"success row {row_number}"
            )


def _validate_firecrawl_snapshot_resume_inputs(
    *,
    success_records: Sequence[Mapping[str, Any]],
    fetch_exclusion_records: Sequence[Mapping[str, Any]],
    input_commitments: Mapping[str, object],
    raw_html_directory: Path,
    snapshot_path: Path,
    snapshot_manifest: Mapping[str, Any],
) -> None:
    stage_commitments = snapshot_manifest.get("stage_commitments")
    if not isinstance(stage_commitments, Mapping):
        raise CycleAcquisitionStoreError(
            "snapshot lacks committed screening stage inputs"
        )
    committed_inputs = cast(Mapping[str, object], stage_commitments).get(
        "firecrawl_screen_inputs"
    )
    if not isinstance(committed_inputs, Mapping):
        raise CycleAcquisitionStoreError(
            "snapshot lacks a normalized screening input commitment"
        )
    if dict(cast(Mapping[str, object], committed_inputs)) != dict(input_commitments):
        raise CycleAcquisitionStoreError(
            "snapshot resume outcome classes or normalized input records do not "
            "match the committed screening stage inputs"
        )
    input_candidate_ids = [
        *(_required_str(record, "case_id") for record in success_records),
        *(_required_str(record, "case_id") for record in fetch_exclusion_records),
    ]
    snapshot_candidates = _read_records(snapshot_path / "candidates.jsonl")
    snapshot_candidate_ids = {
        _required_str(record, "candidate_id") for record in snapshot_candidates
    }
    if set(input_candidate_ids) != snapshot_candidate_ids:
        raise CycleAcquisitionStoreError(
            "snapshot resume input candidate IDs do not match the committed snapshot"
        )
    artifact_commitments: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for artifact in _read_records(snapshot_path / "raw-artifacts.jsonl"):
        candidate_id = _required_str(artifact, "candidate_id")
        digest = _required_str(artifact, "sha256")
        byte_count = artifact.get("byte_count")
        if not isinstance(byte_count, int) or isinstance(byte_count, bool):
            raise CycleAcquisitionStoreError(
                f"snapshot raw artifact byte count is invalid for {candidate_id}"
            )
        artifact_commitments[candidate_id].add((digest, byte_count))

    for record in success_records:
        candidate_id = _required_str(record, "case_id")
        docket_id = _required_str(record, "docket_id")
        if not docket_id.isdigit():
            continue
        raw_path = raw_html_directory / f"{docket_id}.html"
        try:
            raw_bytes = raw_path.read_bytes()
        except OSError as error:
            raise CycleAcquisitionStoreError(
                f"snapshot resume raw HTML is unavailable for {candidate_id}"
            ) from error
        expected_bytes = cast(int, record["raw_html_bytes"])
        expected_sha256 = cast(str, record["raw_html_sha256"])
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        if len(raw_bytes) != expected_bytes or expected_sha256 != (
            f"sha256:{actual_sha256}"
        ):
            raise CycleAcquisitionStoreError(
                f"snapshot resume raw HTML commitment mismatch for {candidate_id}"
            )
        if (actual_sha256, expected_bytes) not in artifact_commitments.get(
            candidate_id, set()
        ):
            raise CycleAcquisitionStoreError(
                "snapshot resume raw HTML is not committed by the snapshot for "
                f"{candidate_id}"
            )


def _validate_screen_resume_output_paths(
    *,
    args: argparse.Namespace,
    snapshot_path: Path,
    output_root: Path,
    screened_cases_path: Path,
    exclusions_path: Path,
    summary_path: Path,
) -> None:
    snapshot_root = snapshot_path.resolve()
    writable_paths = {
        "--output-root": output_root,
        "--screened-cases-output": screened_cases_path,
        "--exclusions-output": exclusions_path,
        "--summary-output": summary_path,
        "--run-card-output": _acquisition_path(
            args,
            "run_card_output",
            output_root / "run-cards" / "screen-firecrawl-dockets.json",
        ),
        "--log-output": _acquisition_path(
            args,
            "log_output",
            output_root / "logs" / "screen-firecrawl-dockets.jsonl",
        ),
    }
    for flag, path in writable_paths.items():
        resolved = path.resolve()
        if resolved == snapshot_root or resolved.is_relative_to(snapshot_root):
            raise CommandError(
                f"{flag} must be outside the committed snapshot tree: {snapshot_root}"
            )


def _validate_replay_output_paths(
    *,
    args: argparse.Namespace,
    snapshot_path: Path,
    screened_cases_path: Path,
    exclusions_path: Path,
    summary_path: Path,
    raw_html_dir: Path,
    cycle_store_path: Path,
    source_bundle: SnapshotReplayBundle | None = None,
) -> None:
    snapshot_tree = snapshot_path.resolve()
    output_root = cast(Path, args.output_root)
    writable_paths = {
        "--screened-cases-output": screened_cases_path,
        "--exclusions-output": exclusions_path,
        "--summary-output": summary_path,
        "replayed raw HTML directory": raw_html_dir,
        "--run-card-output": _acquisition_path(
            args,
            "run_card_output",
            output_root / "run-cards" / "replay-screening-snapshots.json",
        ),
        "--log-output": _acquisition_path(
            args,
            "log_output",
            output_root / "logs" / "replay-screening-snapshots.jsonl",
        ),
    }
    for flag, path in writable_paths.items():
        resolved = path.resolve()
        if resolved == snapshot_tree or resolved.is_relative_to(snapshot_tree):
            raise CommandError(
                f"{flag} must be outside the committed snapshot tree: {snapshot_tree}"
            )
    writable_scopes: list[tuple[str, Path, bool, str]] = [
        ("--cycle-store", cycle_store_path, False, "cycle-store"),
        (
            "--cycle-store WAL",
            Path(f"{cycle_store_path}-wal"),
            False,
            "cycle-store",
        ),
        (
            "--cycle-store SHM",
            Path(f"{cycle_store_path}-shm"),
            False,
            "cycle-store",
        ),
        (
            "--cycle-store journal",
            Path(f"{cycle_store_path}-journal"),
            False,
            "cycle-store",
        ),
        ("--screened-cases-output", screened_cases_path, False, "screened"),
        ("--exclusions-output", exclusions_path, False, "exclusions"),
        ("--summary-output", summary_path, False, "summary"),
        ("replayed raw HTML directory", raw_html_dir, True, "raw-html"),
        ("target snapshot", snapshot_path, True, "snapshot"),
        ("target snapshot staging root", snapshot_path.parent, True, "snapshot"),
        (
            "--run-card-output",
            _acquisition_path(
                args,
                "run_card_output",
                output_root / "run-cards" / "replay-screening-snapshots.json",
            ),
            False,
            "run-card",
        ),
        (
            "--log-output",
            _acquisition_path(
                args,
                "log_output",
                output_root / "logs" / "replay-screening-snapshots.jsonl",
            ),
            False,
            "log",
        ),
    ]
    for label, path, is_tree, _ in writable_scopes:
        _reject_hardlinked_writable_replay_scope(
            label=label,
            path=path.resolve(),
            is_tree=is_tree,
        )
    for index, (label, path, is_tree, family) in enumerate(writable_scopes):
        resolved = path.resolve()
        for other_label, other_path, other_is_tree, other_family in writable_scopes[
            index + 1 :
        ]:
            if family == other_family == "snapshot":
                continue
            other = other_path.resolve()
            if _replay_scopes_overlap(
                left_label=label,
                left=resolved,
                left_tree=is_tree,
                right_label=other_label,
                right=other,
                right_tree=other_is_tree,
            ):
                raise CommandError(
                    f"writable replay outputs overlap: {label} vs {other_label}: "
                    f"{resolved} vs {other}"
                )

    if source_bundle is None:
        return

    protected_scopes: list[tuple[str, Path, bool]] = [
        ("source assembly run card", path, False)
        for path in source_bundle.source_assembly_run_cards
    ]
    for source in source_bundle.sources:
        protected_scopes.extend(
            (
                ("source snapshot", source.path, True),
                ("source screen run card", source.screen_run_card, False),
            )
        )
        protected_scopes.extend(
            ("source snapshot file", path, False)
            for path in source.path.rglob("*")
            if path.is_file()
        )
        protected_scopes.extend(
            ("source screen input", path, path.is_dir()) for path in source.input_paths
        )
        if source.input_paths:
            source_store = source.input_paths[0]
            protected_scopes.extend(
                (
                    ("source cycle-store WAL", Path(f"{source_store}-wal"), False),
                    ("source cycle-store SHM", Path(f"{source_store}-shm"), False),
                    (
                        "source cycle-store journal",
                        Path(f"{source_store}-journal"),
                        False,
                    ),
                )
            )
        if source.bundle_root is not None:
            protected_scopes.append(
                ("supplemental source bundle", source.bundle_root, True)
            )
    protected_scopes.extend(
        ("source raw artifact", success.raw_path, False)
        for success in source_bundle.successes
    )

    for writable_label, writable_path, writable_tree, _ in writable_scopes:
        writable = writable_path.resolve()
        for protected_label, protected_path, protected_tree in protected_scopes:
            protected = protected_path.resolve()
            if _replay_scopes_overlap(
                left_label=writable_label,
                left=writable,
                left_tree=writable_tree,
                right_label=protected_label,
                right=protected,
                right_tree=protected_tree,
            ):
                raise CommandError(
                    f"{writable_label} overlaps {protected_label}: "
                    f"{writable} vs {protected}"
                )


def _replay_scopes_overlap(
    *,
    left_label: str,
    left: Path,
    left_tree: bool,
    right_label: str,
    right: Path,
    right_tree: bool,
) -> bool:
    if left == right:
        return True
    if left_tree and right.is_relative_to(left):
        return True
    if right_tree and left.is_relative_to(right):
        return True
    left_identity = _existing_replay_scope_identity(left, label=left_label)
    right_identity = _existing_replay_scope_identity(right, label=right_label)
    return left_identity is not None and left_identity == right_identity


def _existing_replay_scope_identity(
    path: Path, *, label: str
) -> tuple[int, int] | None:
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CommandError(
            f"cannot inspect {label} for output overlap: {path}: {exc}"
        ) from exc
    return metadata.st_dev, metadata.st_ino


def _reject_hardlinked_writable_replay_scope(
    *, label: str, path: Path, is_tree: bool
) -> None:
    if is_tree:
        return
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise CommandError(
            f"cannot inspect {label} for hard-link aliases: {path}: {exc}"
        ) from exc
    if metadata.st_nlink > 1:
        raise CommandError(
            f"writable replay output overlap via hard-link aliases: {label}: {path}"
        )


_IMMUTABLE_ACQUISITION_EXCLUSIONS = frozenset(
    {
        "decision_before_release_anchor",
        "bankruptcy_court",
        "not_federal_district_court",
        "missing_docket_number",
        "placeholder_or_sealed_docket_number",
        "not_civil_cv_docket",
        "criminal_style_caption",
        "non_civil_case",
        "non_civil_metadata",
        "criminal_case",
        "bankruptcy_case",
        "administrative_case",
        "appellate_case",
        "missing_civil_case_metadata",
        "invalid_civil_case_metadata",
    }
)
_TRANSIENT_FETCH_EXCLUSIONS: Mapping[str, str] = {
    "candidate_limit_deferred": "temporarily_unavailable",
    "provider_blocker_deferred": "temporarily_unavailable",
    "case_dev_provider_blocker": "case_dev_provider_blocker",
    "firecrawl_provider_blocker": "firecrawl_provider_blocker",
    "raw_html_path_exists": "temporarily_unavailable",
    "raw_html_hash_conflict": "temporarily_unavailable",
    "raw_html_resume_invalid": "parse_failure",
}


def _validate_raw_docket_bytes(payload: bytes) -> None:
    raw_html = payload.decode("utf-8")
    if not raw_html.strip():
        raise ValueError("raw docket HTML is empty")


def _screened_case_dev_id(record: Mapping[str, Any]) -> str:
    candidate_value = record.get("candidate")
    if not isinstance(candidate_value, Mapping):
        raise ValueError("screened case is missing candidate metadata")
    candidate = cast(Mapping[str, object], candidate_value)
    metadata_value = candidate.get("metadata")
    if not isinstance(metadata_value, Mapping):
        raise ValueError("screened case is missing Case.dev metadata")
    metadata = cast(Mapping[str, object], metadata_value)
    case_id = metadata.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("screened case is missing its Case.dev case ID")
    return case_id.strip()


def _rescreen_metadata_by_candidate(
    success_records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, object] | None]:
    """Return the complete Case.dev metadata that justifies a metadata rescreen."""

    metadata_by_candidate: dict[str, Mapping[str, object] | None] = {}
    for record in success_records:
        candidate_id = _required_str(record, "case_id")
        metadata_value = record.get("case_metadata")
        metadata = (
            dict(cast(Mapping[str, object], metadata_value))
            if isinstance(metadata_value, Mapping)
            else None
        )
        if candidate_id in metadata_by_candidate:
            metadata_by_candidate[candidate_id] = None
            continue
        if metadata is None or metadata.get("case_id") != candidate_id:
            metadata_by_candidate[candidate_id] = None
            continue
        court = metadata.get("court_id") or metadata.get("court")
        docket_number = metadata.get("docket_number")
        if not isinstance(court, str) or not court.strip():
            metadata_by_candidate[candidate_id] = None
            continue
        if not isinstance(docket_number, str) or not docket_number.strip():
            metadata_by_candidate[candidate_id] = None
            continue
        metadata_by_candidate[candidate_id] = metadata
    return metadata_by_candidate


def _canonical_screen_exclusion_reason(reason: str) -> str:
    if reason in _IMMUTABLE_ACQUISITION_EXCLUSIONS:
        return reason
    if reason in {"bankruptcy_posture", "criminal_posture"}:
        return reason
    if reason == "habeas_or_immigration_detention_posture":
        return reason
    return "strict_clean_screen_failed"


def _record_fetch_exclusion(
    store: CycleAcquisitionStore,
    *,
    batch_id: str,
    record: Mapping[str, Any],
) -> None:
    candidate_id = _required_str(record, "case_id")
    reason = _required_str(record, "reason")
    evidence = dict(record)
    evidence["candidate_id"] = candidate_id
    if reason in _IMMUTABLE_ACQUISITION_EXCLUSIONS:
        store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="excluded",
            reason_code=reason,
            evidence=evidence,
        )
        return
    transient_reason = _TRANSIENT_FETCH_EXCLUSIONS.get(reason)
    if transient_reason is not None:
        store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="transient_failure",
            reason_code=transient_reason,
            evidence=evidence,
        )
        return
    store.record_observation(
        candidate_id,
        batch_id=batch_id,
        state="excluded",
        reason_code="strict_clean_screen_failed",
        evidence=evidence,
    )


def _merge_firecrawl_resume_commitments(
    candidates: Sequence[JsonRecord],
    prior_successes: Sequence[JsonRecord],
) -> list[JsonRecord]:
    commitments: dict[str, tuple[str, str, str]] = {}
    for success in prior_successes:
        case_id = _required_str(success, "case_id")
        docket_id = _required_str(success, "docket_id")
        source_url = _required_str(success, "source_url")
        raw_sha256 = _required_str(success, "raw_html_sha256")
        if (
            not raw_sha256.startswith("sha256:")
            or len(raw_sha256) != 71
            or any(character not in "0123456789abcdef" for character in raw_sha256[7:])
        ):
            raise CommandError(
                f"prior Firecrawl success has invalid SHA-256 for {case_id}"
            )
        prior = commitments.get(case_id)
        commitment = (docket_id, source_url, raw_sha256)
        if prior is not None and prior != commitment:
            raise CommandError(
                f"prior Firecrawl successes conflict for Case.dev case {case_id}"
            )
        commitments[case_id] = commitment

    merged: list[JsonRecord] = []
    for candidate in candidates:
        updated = dict(candidate)
        case_id = _required_str(updated, "case_id")
        commitment = commitments.get(case_id)
        if commitment is not None:
            docket_id, source_url, raw_sha256 = commitment
            candidate_docket_id = updated.get("courtlistener_docket_id")
            candidate_source_url = updated.get("courtlistener_url")
            if (
                candidate_docket_id is not None and candidate_docket_id != docket_id
            ) or (
                candidate_source_url is not None and candidate_source_url != source_url
            ):
                raise CommandError(
                    f"prior Firecrawl success identity conflicts for {case_id}"
                )
            updated["courtlistener_docket_id"] = docket_id
            updated["courtlistener_url"] = source_url
            updated["raw_html_sha256"] = raw_sha256
        merged.append(updated)
    return merged


def _verified_snapshot_raw_html_sources(
    snapshot_path: Path,
    *,
    requested: Path | None,
    use_embedded_entries: bool,
) -> tuple[Path | None, Mapping[str, Path] | None]:
    screened_path = snapshot_path / "screened-cases.jsonl"
    screened_records = _read_records(screened_path) if screened_path.is_file() else []
    for record in screened_records:
        selected_entries = record.get("selected_entries")
        selected_entry_records = (
            cast(list[object], selected_entries)
            if isinstance(selected_entries, list)
            else []
        )
        if record.get("provider") == "courtlistener-recap-rest-v4" and (
            record.get("canonical_rest_screen_complete") is not True
            or not isinstance(selected_entries, list)
            or not selected_entry_records
            or not all(isinstance(entry, dict) for entry in selected_entry_records)
        ):
            raise CommandError(
                "verified snapshot contains preliminary REST evidence without "
                "canonical linkage, leakage, and embedded entries"
            )
    artifact_records = _read_records(snapshot_path / "raw-artifacts.jsonl")
    artifact_paths: list[tuple[str, Path]] = []
    for record in artifact_records:
        candidate_id = record.get("candidate_id")
        raw_path = record.get("path")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id.strip()
            or not isinstance(raw_path, str)
            or not raw_path.strip()
        ):
            raise CommandError(
                "verified snapshot contains an invalid raw artifact path"
            )
        resolved_path = Path(raw_path).resolve()
        artifact_paths.append(
            (
                _raw_html_lookup_id(candidate_id.strip(), resolved_path),
                resolved_path,
            )
        )
    if not artifact_paths:
        if requested is not None:
            raise CommandError(
                "--raw-html-dir is not allowed when the verified snapshot has no "
                "committed raw artifacts"
            )
        if not use_embedded_entries:
            raise CommandError(
                "verified snapshot has no raw docket artifacts; use embedded entries "
                "only for canonical authenticated REST evidence or an explicitly "
                "authorized fixture path"
            )
        return None, None
    parents = {path.parent for _candidate_id, path in artifact_paths}
    requested_directory: Path | None = None
    if requested is not None:
        requested_directory = requested.resolve()
        if requested_directory not in parents:
            raise CommandError(
                "--raw-html-dir must exactly match a committed verified snapshot "
                "artifact directory"
            )
    if len(parents) == 1 and all(
        path.stem == candidate_id for candidate_id, path in artifact_paths
    ):
        return next(iter(parents)), None

    paths_by_candidate: dict[str, list[Path]] = defaultdict(list)
    for candidate_id, path in artifact_paths:
        if path.suffix.casefold() != ".html" or not path.is_file():
            raise CommandError(
                "verified snapshot contains an invalid raw HTML artifact path"
            )
        paths_by_candidate[candidate_id].append(path)

    by_candidate: dict[str, Path] = {}
    for candidate_id, candidate_paths in paths_by_candidate.items():
        if len(candidate_paths) == 1:
            by_candidate[candidate_id] = candidate_paths[0]
            continue
        requested_paths = [
            path
            for path in candidate_paths
            if requested_directory is not None and path.parent == requested_directory
        ]
        if len(requested_paths) != 1:
            raise CommandError(
                f"verified snapshot raw artifacts conflict for candidate {candidate_id}"
            )
        by_candidate[candidate_id] = requested_paths[0]
    return None, by_candidate


def _raw_html_lookup_id(candidate_id: str, path: Path) -> str:
    """Preserve the planner's docket-ID lookup while trusting snapshot identity."""

    if path.stem.isdigit():
        return path.stem
    prefix = "courtlistener-docket-"
    if candidate_id.startswith(prefix) and candidate_id[len(prefix) :].isdigit():
        return candidate_id[len(prefix) :]
    return candidate_id


def _firecrawl_credit_summary_if_available(
    *,
    store_path: Path,
    run_id: str,
) -> JsonRecord:
    """Read already-authorized credit evidence without masking the stage failure."""

    try:
        with CycleAcquisitionStore(store_path) as store:
            return dict(store.firecrawl_run_summary(run_id))
    except (CycleAcquisitionStoreError, KeyError, OSError, ValueError):
        return {}


def _firecrawl_metered_activity_executed(
    *,
    live: bool,
    summary: Mapping[str, object],
) -> bool:
    reserved = summary.get("run_reserved_credits")
    return live and type(reserved) is int and reserved > 0


def _write_acquisition_completion(
    args: argparse.Namespace,
    *,
    stage: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    record_count: int,
    dry_run: bool,
    paid_activity_requested: bool,
    paid_activity_executed: bool,
    extra: Mapping[str, Any] | None = None,
) -> None:
    _write_acquisition_stage_record(
        args,
        stage=stage,
        status="completed",
        event="stage_completed",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=record_count,
        dry_run=dry_run,
        paid_activity_requested=paid_activity_requested,
        paid_activity_executed=paid_activity_executed,
        extra=extra,
    )


def _write_acquisition_failure(
    args: argparse.Namespace,
    *,
    stage: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    reason: str,
    paid_activity_requested: bool,
    paid_activity_executed: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> None:
    failure_extra: JsonRecord = {"failure_reason": reason}
    if extra is not None:
        failure_extra.update(extra)
    _write_acquisition_stage_record(
        args,
        stage=stage,
        status="failed",
        event="stage_failed",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=0,
        dry_run=_acquisition_dry_run(args),
        paid_activity_requested=paid_activity_requested,
        paid_activity_executed=paid_activity_executed,
        extra=failure_extra,
    )


def _write_acquisition_stage_record(
    args: argparse.Namespace,
    *,
    stage: str,
    status: str,
    event: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    record_count: int,
    dry_run: bool,
    paid_activity_requested: bool,
    paid_activity_executed: bool,
    extra: Mapping[str, Any] | None,
) -> None:
    output_root = _acquisition_output_root(args)
    run_card_path = _acquisition_path(
        args,
        "run_card_output",
        output_root / "run-cards" / f"{stage}.json",
    )
    log_path = _acquisition_path(
        args,
        "log_output",
        output_root / "logs" / f"{stage}.jsonl",
    )
    run_card: JsonRecord = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": stage,
        "status": status,
        "dry_run": dry_run,
        "execute": not dry_run,
        "resume": cast(bool, args.resume),
        "record_count": record_count,
        "input_paths": [str(path) for path in input_paths],
        "output_paths": [str(path) for path in output_paths],
        "paid_activity_requested": paid_activity_requested,
        "paid_activity_executed": paid_activity_executed,
        "generated_at": _iso_datetime(datetime.now(UTC)),
    }
    if extra is not None:
        run_card.update(extra)
    _write_json(run_card_path, run_card)
    _append_jsonl(
        log_path,
        [
            {
                "schema_version": "legalforecast.acquisition_stage_log.v1",
                "event": event,
                "stage": stage,
                "status": status,
                "dry_run": dry_run,
                "run_card_path": str(run_card_path),
                "record_count": record_count,
                "paid_activity_requested": paid_activity_requested,
                "paid_activity_executed": paid_activity_executed,
            }
        ],
    )
    _log_event(stage, event, run_card_path, record_count)


def _core_document_filter_result(
    record: Mapping[str, Any],
) -> CoreDocumentFilterResult:
    return CoreDocumentFilterResult(
        candidate_id=_required_str(record, "candidate_id"),
        purchase_document_ids=_required_str_tuple(record, "purchase_document_ids"),
        core_mtd_documents=_required_str_tuple(record, "core_mtd_documents"),
        core_exhibit_documents=_required_str_tuple(record, "core_exhibit_documents"),
        model_visible_document_ids=_required_str_tuple(
            record,
            "model_visible_document_ids",
        ),
        operative_complaint_document_id=_optional_str(
            record,
            "operative_complaint_document_id",
        ),
        operative_complaint_documents=_required_str_tuple(
            record,
            "operative_complaint_documents",
        ),
        audit_only_document_ids=_required_str_tuple(record, "audit_only_document_ids"),
        core_missing_documents=_required_str_tuple(record, "core_missing_documents"),
        exclusion_reasons=_required_str_tuple(record, "exclusion_reasons"),
        missing_core_roles=_optional_str_tuple(record, "missing_core_roles"),
    )


def _missing_core_budget_plan(record: Mapping[str, Any]) -> MissingCoreBudgetPlan:
    dry_run = _required_bool(record, "dry_run")
    return MissingCoreBudgetPlan(
        case_plans=tuple(
            _case_missing_core_purchase_plan(case_record, default_dry_run=dry_run)
            for case_record in _required_record_sequence(record, "case_plans")
        ),
        cost_per_document=Decimal(_required_str(record, "cost_per_document_usd")),
        max_projected_budget=Decimal(_required_str(record, "max_projected_budget_usd")),
        max_missing_core_documents_per_case=_required_int(
            record,
            "max_missing_core_documents_per_case",
        ),
        dry_run=dry_run,
        # These fields are absent from plans written before purchase frontiers.
        frontier_rows=tuple(
            _purchase_frontier_row(row)
            for row in _optional_record_sequence(record, "frontier_rows")
        ),
        omitted_candidate_ids=_optional_str_tuple(record, "omitted_candidate_ids"),
        excluded_case_plans=tuple(
            _case_missing_core_purchase_plan(row, default_dry_run=dry_run)
            for row in _optional_record_sequence(record, "excluded_case_plans")
        ),
        target_case_count=(
            _required_int(record, "target_case_count")
            if record.get("target_case_count") is not None
            else None
        ),
    )


def _purchase_frontier_row(record: Mapping[str, Any]) -> PurchaseFrontierRow:
    return PurchaseFrontierRow(
        max_missing_core_documents_per_case=_required_int(
            record, "max_missing_core_documents_per_case"
        ),
        complete_case_count=_required_int(record, "complete_case_count"),
        incremental_case_count=_required_int(record, "incremental_case_count"),
        purchase_document_count=_required_int(record, "purchase_document_count"),
        estimated_spend=Decimal(_required_str(record, "estimated_spend_usd")),
    )


def _case_missing_core_purchase_plan(
    record: Mapping[str, Any],
    *,
    default_dry_run: bool,
) -> CaseMissingCorePurchasePlan:
    return CaseMissingCorePurchasePlan(
        candidate_id=_required_str(record, "candidate_id"),
        purchase_document_ids=_required_str_tuple(record, "purchase_document_ids"),
        missing_core_document_count=_required_int(
            record,
            "missing_core_document_count",
        ),
        estimated_cost=Decimal(_required_str(record, "estimated_cost_usd")),
        audit_only_document_count=_required_int(record, "audit_only_document_count"),
        dry_run=_optional_bool(record, "dry_run", default=default_dry_run),
        exclusion_reasons=_required_str_tuple(record, "exclusion_reasons"),
        missing_core_roles=_optional_str_tuple(record, "missing_core_roles"),
    )


def _dry_run_missing_core_budget_plan(
    plan: MissingCoreBudgetPlan,
) -> MissingCoreBudgetPlan:
    return MissingCoreBudgetPlan(
        case_plans=tuple(
            CaseMissingCorePurchasePlan(
                candidate_id=case_plan.candidate_id,
                purchase_document_ids=case_plan.purchase_document_ids,
                missing_core_document_count=case_plan.missing_core_document_count,
                estimated_cost=case_plan.estimated_cost,
                audit_only_document_count=case_plan.audit_only_document_count,
                dry_run=True,
                exclusion_reasons=case_plan.exclusion_reasons,
                missing_core_roles=case_plan.missing_core_roles,
            )
            for case_plan in plan.case_plans
        ),
        cost_per_document=plan.cost_per_document,
        max_projected_budget=plan.max_projected_budget,
        max_missing_core_documents_per_case=(plan.max_missing_core_documents_per_case),
        dry_run=True,
        frontier_rows=plan.frontier_rows,
        omitted_candidate_ids=plan.omitted_candidate_ids,
        excluded_case_plans=tuple(
            CaseMissingCorePurchasePlan(
                candidate_id=case_plan.candidate_id,
                purchase_document_ids=case_plan.purchase_document_ids,
                missing_core_document_count=case_plan.missing_core_document_count,
                estimated_cost=case_plan.estimated_cost,
                audit_only_document_count=case_plan.audit_only_document_count,
                dry_run=True,
                exclusion_reasons=case_plan.exclusion_reasons,
                missing_core_roles=case_plan.missing_core_roles,
            )
            for case_plan in plan.excluded_case_plans
        ),
    )


def _free_document_download_request(
    record: Mapping[str, Any],
) -> FreeDocumentDownloadRequest:
    extension = (
        _optional_str(record, "file_extension")
        or _optional_str(record, "output_extension")
        or "pdf"
    )
    return FreeDocumentDownloadRequest(
        candidate_id=_required_str(record, "candidate_id"),
        source_provider=_optional_str(record, "source_provider") or "courtlistener",
        source_document_id=_required_str(record, "source_document_id"),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        document_role=DocumentRole(_required_str(record, "document_role")),
        source_url=_required_str(record, "source_url"),
        file_extension=extension,
    )


def _fixture_free_document_source(path: Path) -> FixtureFreeDocumentSource:
    loaded = _loads_json(path.read_text(encoding="utf-8"))
    documents_by_url: dict[str, bytes] = {}
    if isinstance(loaded, Mapping):
        payload = cast(Mapping[object, object], loaded)
        documents_value = payload.get("documents")
        if isinstance(documents_value, Sequence) and not isinstance(
            documents_value,
            str,
        ):
            for item in cast(Sequence[object], documents_value):
                record = _mapping(item, "fixture document")
                documents_by_url[_required_str(record, "source_url")] = (
                    _fixture_document_content(record)
                )
        else:
            for url, content in payload.items():
                if not isinstance(url, str) or not url.strip():
                    raise ValueError("fixture document URLs must be non-empty strings")
                documents_by_url[url] = _fixture_content_bytes(content)
    else:
        raise ValueError("fixture documents must be a JSON object")
    return FixtureFreeDocumentSource(documents_by_url)


def _free_document_source(
    *,
    fixture_path: Path | None,
    live_public_download: bool,
) -> FreeDocumentSource:
    if fixture_path is not None and live_public_download:
        raise CommandError(
            "acquisition download-free accepts either --fixture-documents or "
            "--live-public-download, not both"
        )
    if fixture_path is not None:
        return _fixture_free_document_source(fixture_path)
    if live_public_download:
        return UrlLibFreeDocumentSource()
    raise CommandError(
        "acquisition download-free --execute requires --fixture-documents for "
        "offline fixtures or --live-public-download for free public "
        "CourtListener/RECAP documents"
    )


def _purchased_document_source(
    *,
    fixture_path: Path | None,
    live_case_dev_download: bool,
    live_courtlistener_download: bool = False,
) -> FreeDocumentSource:
    selected_modes = sum(
        (
            fixture_path is not None,
            live_case_dev_download,
            live_courtlistener_download,
        )
    )
    if selected_modes > 1:
        raise CommandError(
            "acquisition recover-purchased accepts exactly one download source"
        )
    if fixture_path is not None:
        return _fixture_free_document_source(fixture_path)
    if live_case_dev_download:
        config = CaseDevConfig.from_env(require_api_key=True)
        api_key = config.api_key
        if api_key is None:  # pragma: no cover - enforced by require_api_key
            raise PurchasedDocumentRecoveryError(
                "CASE_DEV_API_KEY is required for live purchased-document recovery"
            )
        return UrlLibPurchasedDocumentSource(
            api_key=api_key,
            timeout_seconds=config.timeout_seconds,
        )
    if live_courtlistener_download:
        return UrlLibFreeDocumentSource()
    raise CommandError(
        "acquisition recover-purchased --execute requires --fixture-documents "
        "for offline fixtures, --live-case-dev-download for case.dev documents, "
        "or --live-courtlistener-download for public RECAP documents"
    )


def _fixture_document_content(record: Mapping[str, Any]) -> bytes:
    for field_name in ("content", "text", "body"):
        if field_name in record:
            return _fixture_content_bytes(record[field_name])
    raise ValueError("fixture document must include content, text, or body")


def _fixture_content_bytes(value: object) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("fixture document content must be a string")


def _mistral_markdown_request(
    record: Mapping[str, Any],
    *,
    output_root: Path,
) -> MistralMarkdownConversionRequest:
    candidate_id = _required_str(record, "candidate_id")
    source_document_id = _required_str(record, "source_document_id")
    markdown_output = _optional_str(record, "markdown_output_path")
    safe_document_id = safe_path_component(
        source_document_id,
        field_name="source_document_id",
    )
    markdown_output_path = _resolve_under(
        output_root,
        Path(markdown_output)
        if markdown_output is not None
        else Path("markdown")
        / safe_path_component(candidate_id, field_name="candidate_id")
        / f"{safe_document_id}.md",
        field_name="markdown_output_path",
    )
    return MistralMarkdownConversionRequest(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        input_path=Path(_required_str(record, "input_path")),
        markdown_output_path=markdown_output_path,
        expected_sha256=_required_str(record, "expected_sha256"),
        expected_byte_count=_required_int(record, "expected_byte_count"),
    )


def _planned_parse_document_request(
    record: Mapping[str, Any],
    *,
    document_root: Path,
    markdown_output_root: Path,
) -> JsonRecord:
    candidate_id = _required_str(record, "candidate_id")
    source_document_id = _required_str(record, "source_document_id")
    local_path = Path(_required_str(record, "local_path"))
    input_path = local_path if local_path.is_absolute() else document_root / local_path
    safe_candidate_id = safe_path_component(candidate_id, field_name="candidate_id")
    safe_document_id = safe_path_component(
        source_document_id,
        field_name="source_document_id",
    )
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "input_path": str(input_path),
        "expected_sha256": _required_str(record, "sha256").removeprefix("sha256:"),
        "expected_byte_count": _required_int(record, "byte_count"),
        "markdown_output_path": str(
            markdown_output_root / safe_candidate_id / f"{safe_document_id}.md"
        ),
    }


def _fixture_markdown_conversion_records(
    requests: Sequence[MistralMarkdownConversionRequest],
    *,
    fixture_markdown_dir: Path,
    generated_at: datetime,
) -> tuple[MistralMarkdownConversionRecord, ...]:
    records: list[MistralMarkdownConversionRecord] = []
    for request in requests:
        safe_document_id = safe_path_component(
            request.source_document_id,
            field_name="source_document_id",
        )
        source_path = fixture_markdown_dir / f"{safe_document_id}.md"
        markdown_path = request.markdown_output_path
        metadata_path = markdown_path.with_suffix(".metadata.json")
        parser_config = {
            "engine": "fixture_markdown",
            "fixture_markdown_dir": str(fixture_markdown_dir),
        }
        if source_path.exists():
            markdown = source_path.read_text(encoding="utf-8")
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(markdown, encoding="utf-8")
            quality_flags = () if markdown.strip() else ("empty_markdown",)
            record = MistralMarkdownConversionRecord(
                candidate_id=request.candidate_id,
                source_document_id=request.source_document_id,
                status=MistralMarkdownConversionStatus.SUCCEEDED,
                input_path=str(request.input_path),
                markdown_path=str(markdown_path),
                metadata_path=str(metadata_path),
                parser_config=parser_config,
                quality_flags=quality_flags,
                extracted_text=ExtractedTextArtifact(
                    source_document_id=request.source_document_id,
                    extracted_at=generated_at,
                    extraction_method="fixture_markdown",
                    text_sha256=sha256_text(markdown),
                    quality_flags=quality_flags,
                ),
                source_sha256=request.expected_sha256,
                source_byte_count=request.expected_byte_count,
            )
        else:
            record = MistralMarkdownConversionRecord(
                candidate_id=request.candidate_id,
                source_document_id=request.source_document_id,
                status=MistralMarkdownConversionStatus.FAILED,
                input_path=str(request.input_path),
                markdown_path=str(markdown_path),
                metadata_path=str(metadata_path),
                parser_config=parser_config,
                quality_flags=("fixture_markdown_missing",),
                extracted_text=None,
                source_sha256=request.expected_sha256,
                source_byte_count=request.expected_byte_count,
                error_message=f"fixture markdown missing: {source_path}",
            )
        _write_json(metadata_path, record.to_record())
        records.append(record)
    return tuple(records)


def _model_packet_assembly(
    record: Mapping[str, Any],
    *,
    ablation: PacketAblation,
) -> ModelPacketAssembly:
    exclusion_entries = _optional_record_sequence(record, "exclusion_ledger_entries")
    if exclusion_entries:
        raise CommandError(
            "packet-build input contains exclusion-ledger entries; excluded "
            "candidates must not be assembled into model-visible packets"
        )
    parsed_documents = tuple(
        _parsed_markdown_document(item)
        for item in _optional_record_sequence(record, "parsed_documents")
    )
    conversion_records = tuple(
        _mistral_markdown_conversion_record(item)
        for item in _optional_record_sequence(record, "parser_records")
    )
    if conversion_records:
        parsed_documents = (
            *parsed_documents,
            *parsed_markdown_documents_from_conversion_records(
                conversion_records,
                markdown_root=Path(_required_str(record, "markdown_root"))
                if "markdown_root" in record
                else None,
            ),
        )
    return assemble_model_packet(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        court=_required_str(record, "court"),
        docket_number=_required_str(record, "docket_number"),
        generated_at=_parse_datetime(_required_str(record, "generated_at")),
        docket_markdown=_controlled_docket_markdown_artifacts(
            _required_record(record, "docket_markdown")
        ),
        documents=tuple(
            _source_provenance(document)
            for document in _required_record_sequence(record, "documents")
        ),
        parsed_documents=parsed_documents,
        prediction_units=tuple(
            _model_packet_prediction_unit(unit)
            for unit in _required_record_sequence(record, "prediction_units")
        ),
        source_case_id=_optional_str(record, "source_case_id"),
        metadata=_optional_str_mapping(record.get("metadata", {}), "metadata"),
        ablation=ablation,
        target_docket_entry_numbers=_optional_int_tuple(
            record.get("target_docket_entry_numbers")
        ),
        decision_date=_optional_str(record, "decision_date")
        or _optional_str(
            _optional_record(record.get("metadata"), "metadata"),
            "decision_date",
        ),
        related_family_id=_optional_str(record, "related_family_id"),
        mdl_family_id=_optional_str(record, "mdl_family_id"),
    )


def _controlled_docket_markdown_artifacts(
    record: Mapping[str, Any],
) -> ControlledDocketMarkdownArtifacts:
    return ControlledDocketMarkdownArtifacts(
        model_visible_markdown=_required_str(record, "model_visible_markdown"),
        audit_markdown=_required_str(record, "audit_markdown"),
    )


def _parsed_markdown_document(record: Mapping[str, Any]) -> ParsedMarkdownDocument:
    markdown = _optional_str(record, "markdown")
    markdown_path = _optional_str(record, "markdown_path")
    if markdown is None:
        if markdown_path is None:
            raise ValueError("parsed_documents require markdown or markdown_path")
        markdown = Path(markdown_path).read_text(encoding="utf-8")
    return ParsedMarkdownDocument(
        source_document_id=_required_str(record, "source_document_id"),
        markdown=markdown,
        extracted_text=(
            _extracted_text_artifact(_required_record(record, "extracted_text"))
            if "extracted_text" in record and record["extracted_text"] is not None
            else None
        ),
        quality_flags=_required_str_tuple(record, "quality_flags")
        if "quality_flags" in record
        else (),
        extraction_method=_optional_str(record, "extraction_method")
        or "provided_markdown",
    )


def _mistral_markdown_conversion_record(
    record: Mapping[str, Any],
) -> MistralMarkdownConversionRecord:
    extracted_record = record.get("extracted_text")
    return MistralMarkdownConversionRecord(
        candidate_id=_required_str(record, "candidate_id"),
        source_document_id=_required_str(record, "source_document_id"),
        status=MistralMarkdownConversionStatus(_required_str(record, "status")),
        input_path=_required_str(record, "input_path"),
        markdown_path=_required_str(record, "markdown_path"),
        metadata_path=_required_str(record, "metadata_path"),
        parser_config=_required_record(record, "parser_config"),
        quality_flags=_required_str_tuple(record, "quality_flags"),
        extracted_text=(
            _extracted_text_artifact(_mapping(extracted_record, "extracted_text"))
            if extracted_record is not None
            else None
        ),
        stdout=_optional_str(record, "stdout") or "",
        stderr=_optional_str(record, "stderr") or "",
        error_message=_optional_str(record, "error_message"),
    )


def _score_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    base_rate: float | None,
) -> tuple[ScoreSummary, ...]:
    if not run_records:
        raise ValueError("at least one run record is required")
    labels_by_unit_id = {label.unit_id: label for label in labels}
    if not labels_by_unit_id:
        raise ValueError("at least one outcome label is required")
    effective_base_rate = (
        _computed_base_rate(labels) if base_rate is None else base_rate
    )

    cases_by_model: dict[str, list[ScoringCase]] = defaultdict(list)
    for record in run_records:
        required_unit_ids = _required_str_tuple(record, "required_unit_ids")
        missing_labels = sorted(set(required_unit_ids) - set(labels_by_unit_id))
        if missing_labels:
            raise ValueError(f"labels missing for required units: {missing_labels}")
        model_id = _record_model_id(record)
        parsed = parse_model_output(
            _required_str(record, "raw_output"),
            required_unit_ids=required_unit_ids,
        )
        cases_by_model[model_id].append(
            ScoringCase(
                case_id=_required_str(record, "case_id"),
                candidate_id=_optional_str(record, "candidate_id"),
                model_id=model_id,
                related_family_id=_optional_str(record, "related_family_id"),
                mdl_family_id=_optional_str(record, "mdl_family_id"),
                parsed_output=parsed,
                outcome_labels=tuple(
                    labels_by_unit_id[unit_id] for unit_id in required_unit_ids
                ),
            )
        )

    return tuple(
        score_cases(tuple(cases), base_rate=effective_base_rate)
        for _model_id, cases in sorted(cases_by_model.items())
    )


def _write_report_artifacts(
    report: BenchmarkLeaderboardReport,
    *,
    json_path: Path,
    csv_path: Path,
    markdown_path: Path,
    html_path: Path,
    generated_at: datetime,
) -> None:
    _write_json(
        json_path,
        {
            "generated_at": _iso_datetime(generated_at),
            **report.to_record(),
        },
    )
    _write_text(csv_path, report.to_csv())
    _write_text(markdown_path, report.to_markdown())
    _write_text(html_path, report.to_html())


def _score_summary(record: Mapping[str, Any]) -> ScoreSummary:
    return ScoreSummary(
        model_id=_required_str(record, "model_id"),
        case_count=_required_int(record, "case_count"),
        unit_count=_required_int(record, "unit_count"),
        micro_brier=_required_float(record, "micro_brier"),
        macro_brier=_required_float(record, "macro_brier"),
        brier_skill_score=_required_float(record, "brier_skill_score"),
        log_loss=_required_float(record, "log_loss"),
        ece=_required_float(record, "ece"),
        capped_case_micro_brier=_required_float(record, "capped_case_micro_brier"),
        related_family_capped_micro_brier=_required_float(
            record,
            "related_family_capped_micro_brier",
        ),
        mdl_family_capped_micro_brier=_required_float(
            record,
            "mdl_family_capped_micro_brier",
        ),
        case_unit_cap=_required_int(record, "case_unit_cap"),
        family_unit_cap=_required_int(record, "family_unit_cap"),
        dominance_threshold=_required_float(record, "dominance_threshold"),
        dominance_sensitivity_reports=tuple(
            _dominance_sensitivity_report(item)
            for item in _required_record_sequence(
                record,
                "dominance_sensitivity_reports",
            )
        ),
        invalid_output_rate=_required_float(record, "invalid_output_rate"),
        refusal_rate=_required_float(record, "refusal_rate"),
        defaulted_prediction_rate=_required_float(
            record,
            "defaulted_prediction_rate",
        ),
        base_rate=_required_float(record, "base_rate"),
        base_rate_brier=_required_float(record, "base_rate_brier"),
        ece_bins=tuple(
            _calibration_bin(item)
            for item in _required_record_sequence(record, "ece_bins")
        ),
        unit_scores=tuple(
            _unit_score(item)
            for item in _required_record_sequence(record, "unit_scores")
        ),
    )


def _dominance_sensitivity_report(
    record: Mapping[str, Any],
) -> DominanceSensitivityReport:
    return DominanceSensitivityReport(
        dimension=RobustnessDimension(_required_str(record, "dimension")),
        bucket=_required_str(record, "bucket"),
        unit_count=_required_int(record, "unit_count"),
        unit_share=_required_float(record, "unit_share"),
        bucket_brier=_required_float(record, "bucket_brier"),
        excluded_micro_brier=_optional_number(record, "excluded_micro_brier"),
        capped_micro_brier=_required_float(record, "capped_micro_brier"),
        unit_cap=_required_int(record, "unit_cap"),
        recommended_action=_required_str(record, "recommended_action"),
    )


def _calibration_bin(record: Mapping[str, Any]) -> CalibrationBin:
    return CalibrationBin(
        bin_index=_required_int(record, "bin_index"),
        lower=_required_float(record, "lower"),
        upper=_required_float(record, "upper"),
        unit_count=_required_int(record, "unit_count"),
        mean_probability=_optional_number(record, "mean_probability"),
        observed_rate=_optional_number(record, "observed_rate"),
        absolute_calibration_error=_optional_number(
            record,
            "absolute_calibration_error",
        ),
    )


def _unit_score(record: Mapping[str, Any]) -> UnitScore:
    invalid_reason = _optional_str(record, "invalid_reason")
    return UnitScore(
        case_id=_required_str(record, "case_id"),
        candidate_id=_optional_str(record, "candidate_id"),
        related_family_id=_optional_str(record, "related_family_id"),
        mdl_family_id=_optional_str(record, "mdl_family_id"),
        model_id=_required_str(record, "model_id"),
        unit_id=_required_str(record, "unit_id"),
        probability_fully_dismissed=_required_float(
            record,
            "probability_fully_dismissed",
        ),
        outcome=_required_int(record, "outcome"),
        brier=_required_float(record, "brier"),
        log_loss=_required_float(record, "log_loss"),
        parser_status=ParserStatus(_required_str(record, "parser_status")),
        raw_output_sha256=_required_str(record, "raw_output_sha256"),
        defaulted_prediction=_required_bool(record, "defaulted_prediction"),
        invalid_reason=(
            ParserIssueCode(invalid_reason) if invalid_reason is not None else None
        ),
        label_confidence=_optional_number(record, "label_confidence"),
    )


def _report_inference(
    summaries: Sequence[ScoreSummary],
    *,
    replicates: int,
    seed: int,
) -> BootstrapInferenceResult | None:
    if len(summaries) < 2:
        return None
    return paired_clustered_bootstrap(
        tuple(
            ModelScoreInput(summary.model_id, summary.unit_scores)
            for summary in summaries
        ),
        config=BootstrapConfig(replicates=replicates, seed=seed),
    )


def _run_fixture_e2e(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    document_texts = {
        "doc-1": "Complaint alleges Count I for breach of contract.",
        "doc-12": "Defendant moves to dismiss Count I.",
        "doc-18": "Plaintiff opposes dismissal of Count I.",
        "doc-35": "The Court denies dismissal of Count I as to Example LLC.",
    }
    for document_id, text in document_texts.items():
        (documents_dir / f"{document_id}.pdf").write_bytes(_fixture_pdf(text))

    docket_entries = [
        _case_dev_discovery_payload(12, "Motion to dismiss complaint"),
        _case_dev_discovery_payload(
            35,
            "Opinion and order denying motion to dismiss at ECF No. 12",
        ),
    ]
    _write_jsonl(output_dir / "docket_entries.jsonl", docket_entries)
    candidates = [
        candidate.to_record() for candidate in discover_mtd_candidates(docket_entries)
    ]
    _write_jsonl(output_dir / "candidates.jsonl", candidates)
    _log_event(
        "discover", "artifact_written", output_dir / "candidates.jsonl", len(candidates)
    )

    client = CaseDevClient(
        config=CaseDevConfig(api_key=None, estimated_cost_per_request_usd=0.01),
        transport=CaseDevFixtureTransport(_fixture_case_dev_responses(document_texts)),
    )
    retrieval = DocketRetrievalPipeline(client).retrieve_candidate(
        candidate_id="cand_case_1",
        case_id="case-1",
    )
    _write_jsonl(output_dir / "retrievals.jsonl", [retrieval.to_record()])
    _log_event("retrieve", "artifact_written", output_dir / "retrievals.jsonl", 1)

    extraction_artifacts: list[ExtractedTextArtifact] = []
    document_manifest: list[JsonRecord] = []
    for document_id in document_texts:
        document_manifest.append(
            {
                "source_document_id": document_id,
                "path": str(documents_dir / f"{document_id}.pdf"),
            }
        )
        result = extract_pdf_text_with_ocr_fallback(
            (documents_dir / f"{document_id}.pdf").read_bytes()
        )
        extraction_artifacts.append(
            result.to_text_artifact(source_document_id=document_id)
        )
    _write_jsonl(output_dir / "document-manifest.jsonl", document_manifest)
    _write_jsonl(
        output_dir / "extracted_texts.jsonl",
        [artifact.to_record() for artifact in extraction_artifacts],
    )
    _log_event(
        "extract",
        "artifact_written",
        output_dir / "extracted_texts.jsonl",
        len(extraction_artifacts),
    )

    linkage = link_mtd_dispositions(
        retrieval.docket_entries,
        candidate_id=retrieval.candidate_id,
        case_id=retrieval.case_id,
    )
    _write_jsonl(output_dir / "linkage.jsonl", [linkage.to_record()])
    _log_event("link", "artifact_written", output_dir / "linkage.jsonl", 1)

    unit_result = construct_stage_a_units(_fixture_stage_a_input())
    units = unit_result.units
    unit_records = [unit.to_record() for unit in units]
    _write_jsonl(output_dir / "units.jsonl", unit_records)
    _log_event("unitize", "artifact_written", output_dir / "units.jsonl", len(units))

    label_result = label_stage_b_outcomes(_fixture_stage_b_input(units))
    labels = label_result.labels
    label_records = [label.to_record() for label in labels]
    _write_jsonl(output_dir / "labels.jsonl", label_records)
    _log_event("label", "artifact_written", output_dir / "labels.jsonl", len(labels))

    contamination = _fixture_contamination_metadata()
    _write_json(
        output_dir / "eligibility.json",
        {
            "candidate_id": retrieval.candidate_id,
            "case_id": retrieval.case_id,
            "is_eligible": contamination.is_eligible,
            "eligibility_status": contamination.eligibility_status.value,
            "contamination_metadata": contamination.to_manifest_record(),
        },
    )
    _log_event("eligibility", "artifact_written", output_dir / "eligibility.json", 1)

    case_mix_candidate = _fixture_case_mix_candidate(unit_count=len(units))
    case_mix_diagnostics = build_case_mix_diagnostics(
        (case_mix_candidate,),
        cycle_id="cycle_fixture_e2e",
    )
    _write_json(
        output_dir / "case-mix-diagnostics.json",
        case_mix_diagnostics.to_record(),
    )
    _write_jsonl(output_dir / "exclusion-ledger.jsonl", [])
    _log_event(
        "case_mix",
        "artifact_written",
        output_dir / "case-mix-diagnostics.json",
        1,
    )

    candidate_manifest = build_candidate_manifest_record(
        protocol_version="cycle_fixture_e2e",
        candidate_id=retrieval.candidate_id,
        case_id=retrieval.case_id,
        court=retrieval.court,
        docket_number=retrieval.docket_number,
        decision_date=date(2026, 5, 18),
        source_case_id=retrieval.case_id,
        documents=(filing.provenance for filing in retrieval.filings),
        unit_records=unit_records,
        label_records=label_records,
        contamination_metadata=contamination,
        case_mix_candidate=case_mix_candidate,
    )
    _write_jsonl(
        output_dir / "candidate-manifest.jsonl",
        [candidate_manifest.to_record()],
    )
    _log_event(
        "manifest",
        "artifact_written",
        output_dir / "candidate-manifest.jsonl",
        1,
    )

    case_packet = CasePacketSchema(
        candidate_id=retrieval.candidate_id,
        case_id=retrieval.case_id,
        court=retrieval.court,
        docket_number=retrieval.docket_number,
        generated_at=datetime(2026, 5, 14, tzinfo=UTC),
        documents=tuple(filing.provenance for filing in retrieval.filings),
        extracted_texts=tuple(extraction_artifacts),
    )
    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=units,
        texts=texts_from_mapping(document_texts, artifacts=extraction_artifacts),
        metadata={"judge": "Judge Fixture", "nos_macro_category": "contract"},
        target_docket_entry_numbers=(12,),
        related_family_id="fixture-related-family",
        mdl_family_id="fixture-mdl-family",
    )
    _write_jsonl(output_dir / "packets.jsonl", [packet.to_record()])
    _log_event("packet-build", "artifact_written", output_dir / "packets.jsonl", 1)

    samples = build_inspect_samples((packet,))
    run = run_inspect_fixture(
        samples,
        (
            OfflineMockSolver(
                solver_id="fixture:model-a",
                raw_output=_fixture_raw_output("fixture_unit_count_i", 0.10),
                input_tokens=100,
                output_tokens=25,
                estimated_cost=0.01,
            ),
            OfflineMockSolver(
                solver_id="fixture:model-b",
                raw_output=_fixture_raw_output("fixture_unit_count_i", 0.80),
                input_tokens=100,
                output_tokens=25,
                estimated_cost=0.02,
            ),
        ),
    )
    run_records = run.to_records()
    _write_jsonl(output_dir / "runs.jsonl", run_records)
    _log_event(
        "model-run", "artifact_written", output_dir / "runs.jsonl", len(run_records)
    )
    accounting = accounting_records_from_inspect_run(
        run,
        evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        output_status_by_raw_hash=_output_statuses(run_records),
    )
    _write_jsonl(
        output_dir / "accounting.jsonl",
        [record.to_record() for record in accounting],
    )
    _log_event(
        "model-run",
        "artifact_written",
        output_dir / "accounting.jsonl",
        len(accounting),
    )

    summaries = _score_run_records(run_records, labels, base_rate=None)
    _write_json(
        output_dir / "scores.json",
        {
            "generated_at": "2026-05-14T12:00:00Z",
            "summaries": [summary.to_record() for summary in summaries],
        },
    )
    _log_event("score", "artifact_written", output_dir / "scores.json", len(summaries))
    report_dir = output_dir / "report"
    json_path, csv_path, markdown_path, html_path = _report_paths(report_dir)
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=summarize_accounting_leaderboard(
            tuple(record.to_record() for record in accounting)
        ),
        inference=_report_inference(summaries, replicates=30, seed=20260514),
        title="Fixture Leaderboard",
    )
    _write_report_artifacts(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        html_path=html_path,
        generated_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )
    for path in (json_path, csv_path, markdown_path, html_path):
        _log_event("report", "artifact_written", path, len(report.rows))

    prompt_path = output_dir / "prompt.md"
    scorer_path = output_dir / "scorer.py"
    harness_path = output_dir / "harness.txt"
    model_registry_path = output_dir / "model-registry.json"
    baselines_path = output_dir / "baselines.json"
    labeling_policy_path = output_dir / "labeling-policy.json"
    cohort_policy_path = output_dir / "cohort-policy.json"
    execution_policy_path = output_dir / "execution-policy.json"
    bundle_path = output_dir / "manifests" / "cycle_fixture_e2e.freeze.json"
    _write_text(prompt_path, _fixture_prompt_text())
    _write_text(scorer_path, _fixture_scorer_text())
    _write_text(harness_path, _fixture_harness_text())
    _write_text(
        model_registry_path,
        json.dumps(_fixture_model_registry_records(), indent=2, sort_keys=True) + "\n",
    )
    _write_json(baselines_path, _fixture_baselines_record(labels))
    labeling_policy = generate_labeling_policy(
        cycle_id="cycle_fixture_e2e",
        judge_registry_path=model_registry_path,
        published_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
        threshold_source="fixture protocol decision",
    )
    _write_json(labeling_policy_path, labeling_policy)
    cohort_policy = generate_cohort_policy(_fixture_cohort_policy_decisions())
    _write_json(cohort_policy_path, cohort_policy)
    execution_policy = generate_execution_policy(
        {
            "cycle_id": "cycle_fixture_e2e",
            "cycle_series": "rapid",
            "allow_no_baselines": False,
            "labeling_policy_sha256": sha256_file(labeling_policy_path),
            "cohort_policy_sha256": sha256_file(cohort_policy_path),
            "cohort_observation_manifest_sha256": "c" * 64,
            "lifecycle": {
                "labeling_policy_published_at": "2026-05-12T12:00:00Z",
                "production_labeling_started_at": "2026-05-13T12:00:00Z",
                "cohort_policy_published_at": "2026-05-11T12:00:00Z",
                "batch_002_started_at": "2026-05-12T12:00:00Z",
            },
            "shard_schedule": {
                "shard_count": 8,
                "dispatch_unit": "model_key_ablation",
            },
            "concurrency_policy": {
                "mode": "shard_identity",
                "identity_fields": ["cycle_id", "model_key", "ablation"],
            },
            "receipt_policy": {
                "write_once_per_attempt": True,
                "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
                "result_commitment_required": True,
            },
            "attempt_policy": {
                "reservation_ledger_sha256": "d" * 64,
                "max_billable_attempts": 2,
            },
            "repeat_policy": {"case_ids": ["case-1"], "count": 1},
            "cadence_counts": {
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count_source": "frozen_units",
                "reject_operator_mismatch": True,
            },
        }
    )
    _write_json(execution_policy_path, execution_policy)
    bundle = freeze_cycle(
        "cycle_fixture_e2e",
        {
            FrozenArtifactName.MANIFEST: output_dir / "candidate-manifest.jsonl",
            FrozenArtifactName.UNITS: output_dir / "units.jsonl",
            FrozenArtifactName.LABELS: output_dir / "labels.jsonl",
            FrozenArtifactName.PROMPT: prompt_path,
            FrozenArtifactName.SCORER: scorer_path,
            FrozenArtifactName.HARNESS: harness_path,
            FrozenArtifactName.MODEL_REGISTRY: model_registry_path,
            FrozenArtifactName.BASELINES: baselines_path,
            FrozenArtifactName.EXCLUSION_LEDGER: output_dir / "exclusion-ledger.jsonl",
            FrozenArtifactName.EXECUTION_POLICY: execution_policy_path,
            FrozenArtifactName.LABELING_POLICY: labeling_policy_path,
            FrozenArtifactName.COHORT_POLICY: cohort_policy_path,
        },
        freeze_timestamp=datetime(2026, 5, 14, 12, 5, tzinfo=UTC),
        bundle_output_path=bundle_path,
    )
    _log_event("freeze", "artifact_written", bundle_path, len(bundle.artifacts))

    artifact_paths = _fixture_artifact_paths(output_dir)
    _write_json(
        output_dir / "artifact-manifest.json",
        {
            "generated_at": "2026-05-14T12:00:00Z",
            "artifacts": [str(path.relative_to(output_dir)) for path in artifact_paths],
        },
    )
    _write_json(
        output_dir / "artifact-index.json",
        _fixture_artifact_index(output_dir, artifact_paths),
    )


def _fixture_case_mix_candidate(*, unit_count: int) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id="cand_case_1",
        case_id="case-1",
        district="S.D.N.Y.",
        circuit="2d",
        nos_code="190",
        nos_macro_category="contract",
        represented_party_status="all_represented",
        government_party_status="no_government_party",
        mdl_flag=True,
        public_company_flag=True,
        claim_count=1,
        defendant_count=1,
        defendant_group_count=1,
        prediction_unit_count=unit_count,
        document_completeness=DocumentCompleteness.MISSING_REPLY,
        motion_available=True,
        opposition_available=True,
        reply_available=False,
        fallback_used=False,
        press_publicity_tags=(PressPublicityTag.MAJOR_PUBLIC_COMPANY_PARTY,),
        related_family_id="fixture-related-family",
        mdl_family_id="fixture-mdl-family",
    )


def _fixture_contamination_metadata() -> ContaminationMetadata:
    return ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
            case_filed_at=date(2026, 5, 1),
            motion_filed_at=date(2026, 5, 3),
            briefing_completed_at=date(2026, 5, 10),
        ),
        model_run=ModelRunMetadata(
            provider="fixture",
            model_name="model-a",
            model_version_or_snapshot="2026-05-14-fixture",
            evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
            network_disabled=True,
            search_disabled=True,
            provider_training_cutoff_status=TrainingCutoffStatus.UNKNOWN,
        ),
        publicity_or_related_case_risk=ContaminationRisk.PUBLIC_REPORTING,
        press_publicity_tags=(PressPublicityTag.MAJOR_PUBLIC_COMPANY_PARTY,),
        notes="Fixture uses public-company publicity tagging without outcome leakage.",
    )


def _fixture_model_registry_records() -> list[JsonRecord]:
    return [
        {
            "provider": "fixture",
            "model_id": model_id,
            "display_name": display_name,
            "model_version_or_snapshot": "2026-05-14-fixture",
            "release_timestamp": "2026-05-14T09:00:00Z",
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": TrainingCutoffStatus.UNKNOWN.value,
            "provider_training_cutoff": None,
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "no_tools",
            "context_limit": 200000,
            "pricing_source": "fixture-price-sheet-2026-05-14",
            "input_token_price": 0,
            "output_token_price": 0,
            "known_cutoff_publicity_caveats": [],
        }
        for model_id, display_name in (
            ("model-a", "Fixture Model A"),
            ("model-b", "Fixture Model B"),
        )
    ]


def _fixture_baselines_record(labels: tuple[OutcomeLabel, ...]) -> JsonRecord:
    scored = [
        label.primary_outcome for label in labels if label.primary_outcome is not None
    ]
    base_rate = sum(scored) / len(scored) if scored else None
    return {
        "generated_at": "2026-05-14T12:00:00Z",
        "baseline_ids": [
            "global_base_rate",
            "court_nos_motion_base_rate",
            "metadata_only",
        ],
        "fixture_base_rate": base_rate,
        "training_scope": "synthetic_fixture_only",
    }


def _fixture_prompt_text() -> str:
    return (
        "Predict the probability that each frozen claim-defendant unit is fully "
        "dismissed on the target motion to dismiss. Return strict JSON with one "
        "probability_fully_dismissed value per required unit_id.\n"
    )


def _fixture_scorer_text() -> str:
    return (
        "# Fixture scorer lock\n"
        "primary_metric = 'micro_brier'\n"
        "parser = 'legalforecast.evals.output_parser.parse_model_output'\n"
        "scorer = 'legalforecast.evals.scorers.score_cases'\n"
    )


def _fixture_harness_text() -> str:
    return (
        "legalforecast fixture e2e\n"
        "backend=local_fixture\n"
        "network_disabled=true\n"
        "search_disabled=true\n"
        "tool_policy=no_tools\n"
    )


def _fixture_artifact_index(output_dir: Path, paths: Sequence[Path]) -> JsonRecord:
    index_path = output_dir / "artifact-index.json"
    artifact_records: list[JsonRecord] = []
    for path in paths:
        if path == index_path or not path.is_file():
            continue
        relative_path = str(path.relative_to(output_dir))
        artifact_records.append(
            {
                "path": relative_path,
                "category": _fixture_artifact_category(relative_path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "generated_at": "2026-05-14T12:00:00Z",
        "artifact_count": len(artifact_records),
        "artifacts": artifact_records,
    }


def _fixture_artifact_category(relative_path: str) -> str:
    if relative_path.startswith("report/"):
        return "leaderboard_report"
    if relative_path.startswith("manifests/"):
        return "freeze_bundle"
    if relative_path in {"scores.json", "runs.jsonl", "accounting.jsonl"}:
        return "evaluation"
    if relative_path in {"candidate-manifest.jsonl", "artifact-manifest.json"}:
        return "manifest"
    if (
        relative_path.endswith("diagnostics.json")
        or relative_path == "eligibility.json"
    ):
        return "diagnostics"
    return "workflow"


def _fixture_stage_a_input() -> StageAConstructionInput:
    return StageAConstructionInput(
        candidate_id="cand_case_1",
        case_id="case-1",
        source_documents=(
            StageASourceDocument(
                document_id="doc-1",
                role=StageADocumentRole.COMPLAINT,
                docket_entry_number=1,
                title="Complaint",
            ),
            StageASourceDocument(
                document_id="doc-12",
                role=StageADocumentRole.MTD_NOTICE,
                docket_entry_number=12,
                title="Motion to dismiss",
            ),
        ),
        unit_seeds=(
            StageAUnitSeed(
                unit_id="fixture_unit_count_i",
                count="Count I",
                claim_name="Breach of contract",
                defendant_names=("Example LLC",),
                source_document_ids=("doc-1", "doc-12"),
                citation_page=1,
            ),
        ),
    )


def _fixture_stage_b_input(units: tuple[PredictionUnit, ...]) -> StageBLabelingInput:
    excerpt = "denies dismissal of Count I"
    return StageBLabelingInput(
        candidate_id="cand_case_1",
        case_id="case-1",
        frozen_units=units,
        decision_text=StageBDecisionText(
            document_id="doc-35",
            entered_date="2026-05-18",
            text="The Court denies dismissal of Count I as to Example LLC.",
        ),
        unit_findings=(
            StageBUnitFinding(
                unit_id="fixture_unit_count_i",
                resolution=UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
                amendment_signal=AmendmentSignal.NOT_APPLICABLE,
                supporting_excerpt=excerpt,
                labeler_confidence=0.98,
                page=1,
            ),
        ),
    )


def _fixture_case_dev_responses(
    document_texts: Mapping[str, str],
) -> tuple[RecordedCaseDevResponse, ...]:
    return (
        RecordedCaseDevResponse(
            method="POST",
            path="/legal/v1/docket",
            params={"type": "lookup", "docketId": "case-1"},
            status_code=200,
            payload={
                "docket": {
                    "id": "case-1",
                    "caseName": "Fixture v. Example",
                    "court": "S.D.N.Y.",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        ),
        RecordedCaseDevResponse(
            method="POST",
            path="/legal/v1/docket",
            params={
                "type": "lookup",
                "docketId": "case-1",
                "includeEntries": True,
            },
            status_code=200,
            payload={
                "docket": {
                    "id": "case-1",
                    "entries": [
                        _case_dev_docket_payload(1, "Complaint", "doc-1"),
                        _case_dev_docket_payload(
                            12,
                            "Motion to dismiss complaint",
                            "doc-12",
                        ),
                        _case_dev_docket_payload(
                            18,
                            "Opposition to motion to dismiss",
                            "doc-18",
                        ),
                        _case_dev_docket_payload(
                            35,
                            "Opinion and order denying motion to dismiss at ECF No. 12",
                            "doc-35",
                        ),
                    ],
                }
            },
        ),
        *(
            RecordedCaseDevResponse(
                method="GET",
                path=f"/v1/documents/{document_id}",
                params={},
                status_code=200,
                payload={
                    "document_id": document_id,
                    "case_id": "case-1",
                    "text": text,
                },
            )
            for document_id, text in document_texts.items()
        ),
    )


def _case_dev_docket_payload(
    entry_number: int,
    text: str,
    document_id: str,
) -> JsonRecord:
    return {
        "entryNumber": entry_number,
        "description": text,
        "date": "2026-05-14",
        "documents": [{"id": document_id}],
    }


def _case_dev_discovery_payload(
    entry_number: int,
    text: str,
) -> JsonRecord:
    return {
        "case_id": "case-1",
        "docket_entry_id": f"entry-{entry_number}",
        "entry_number": str(entry_number),
        "entry_text": text,
        "filed_at": "2026-05-14",
    }


def _fixture_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    body = stream.encode("utf-8")
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj",
        "3 0 obj << /Type /Page /Contents 23 0 R >> endobj",
        f"23 0 obj << /Length {len(body)} >> stream\n{stream}\nendstream endobj",
    ]
    return ("%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF").encode()


def _fixture_raw_output(unit_id: str, probability: float) -> str:
    return json.dumps(
        {
            "case_assessment": "Fixture prediction.",
            "predictions": [
                {
                    "unit_id": unit_id,
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _output_statuses(
    run_records: Sequence[Mapping[str, Any]],
) -> dict[str, OutputValidityStatus]:
    statuses: dict[str, OutputValidityStatus] = {}
    for record in run_records:
        parsed = parse_model_output(
            _required_str(record, "raw_output"),
            required_unit_ids=_required_str_tuple(record, "required_unit_ids"),
        )
        statuses[parsed.raw_output_sha256] = OutputValidityStatus(
            invalid_output=parsed.invalid_output,
            refusal=parsed.status is ParserStatus.REFUSAL,
            content_filter=False,
            invalid_output_reason=(
                parsed.status.value if parsed.invalid_output else None
            ),
        )
    return statuses


def _stage_a_input(record: Mapping[str, Any]) -> StageAConstructionInput:
    return StageAConstructionInput(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        source_documents=tuple(
            _stage_a_source(document)
            for document in _required_record_sequence(record, "source_documents")
        ),
        unit_seeds=tuple(
            _stage_a_seed(seed)
            for seed in _required_record_sequence(record, "unit_seeds")
        ),
        metadata=_optional_str_mapping(record.get("metadata"), "metadata"),
    )


def _stage_a_source(record: Mapping[str, Any]) -> StageASourceDocument:
    return StageASourceDocument(
        document_id=_required_str(record, "document_id"),
        role=StageADocumentRole(_required_str(record, "role")),
        is_predecision_material=_optional_bool(
            record,
            "is_predecision_material",
            default=True,
        ),
        contains_target_outcome=_optional_bool(
            record,
            "contains_target_outcome",
            default=False,
        ),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        title=_optional_str(record, "title"),
    )


def _stage_a_seed(record: Mapping[str, Any]) -> StageAUnitSeed:
    return StageAUnitSeed(
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_names=_required_str_tuple(record, "defendant_names"),
        source_document_ids=_required_str_tuple(record, "source_document_ids"),
        challenged_by_motion=_optional_bool(
            record,
            "challenged_by_motion",
            default=True,
        ),
        challenge_scope=ChallengeScope(
            _optional_str(record, "challenge_scope")
            or ChallengeScope.ENTIRE_CLAIM.value
        ),
        unit_confidence=_optional_float(record, "unit_confidence", default=0.8),
        grouping=DefendantGrouping(
            _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=_optional_str(record, "grouping_rationale"),
        group_label=_optional_str(record, "group_label"),
        separable_subclaim=_optional_str(record, "separable_subclaim"),
        uncertainty_notes=_optional_str(record, "uncertainty_notes"),
        unit_id=_optional_str(record, "unit_id"),
        citation_page=_optional_int(record, "citation_page"),
        citation_paragraph=_optional_int(record, "citation_paragraph"),
        citation_excerpt=_optional_str(record, "citation_excerpt"),
        review_reason=(
            UnitizationReviewReason(_required_str(record, "review_reason"))
            if record.get("review_reason") is not None
            else None
        ),
    )


def _stage_b_input(record: Mapping[str, Any]) -> StageBLabelingInput:
    return StageBLabelingInput(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        frozen_units=tuple(
            _prediction_unit(unit)
            for unit in _required_record_sequence(record, "frozen_units")
        ),
        decision_text=_stage_b_decision(_required_record(record, "decision_text")),
        unit_findings=tuple(
            _stage_b_finding(finding)
            for finding in _required_record_sequence(record, "unit_findings")
        ),
        missing_unit_flags=tuple(
            _stage_b_missing_flag(flag)
            for flag in _optional_record_sequence(record, "missing_unit_flags")
        ),
    )


def _load_decision_texts(path: Path) -> dict[str, StageBDecisionText]:
    decision_texts: dict[str, StageBDecisionText] = {}
    for record in _read_records(path):
        decision_text = _stage_b_decision(record)
        if decision_text.document_id in decision_texts:
            raise CommandError(
                f"duplicate decision text for document_id {decision_text.document_id!r}"
            )
        decision_texts[decision_text.document_id] = decision_text
    return decision_texts


def _stage_b_decision(record: Mapping[str, Any]) -> StageBDecisionText:
    return StageBDecisionText(
        document_id=_required_str(record, "document_id"),
        entered_date=_required_str(record, "entered_date"),
        text=_required_str(record, "text"),
        is_first_written_disposition=_optional_bool(
            record,
            "is_first_written_disposition",
            default=True,
        ),
    )


def _stage_b_finding(record: Mapping[str, Any]) -> StageBUnitFinding:
    return StageBUnitFinding(
        unit_id=_required_str(record, "unit_id"),
        resolution=UnitResolution(_required_str(record, "resolution")),
        amendment_signal=AmendmentSignal(_required_str(record, "amendment_signal")),
        supporting_excerpt=_required_str(record, "supporting_excerpt"),
        labeler_confidence=_required_float(record, "labeler_confidence"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        notes=_optional_str(record, "notes"),
    )


def _stage_b_missing_flag(record: Mapping[str, Any]) -> StageBMissingUnitFlag:
    return StageBMissingUnitFlag(
        missing_unit_description=_required_str(record, "missing_unit_description"),
        supporting_excerpt=_required_str(record, "supporting_excerpt"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        notes=_optional_str(record, "notes"),
    )


def _case_packet(record: Mapping[str, Any]) -> CasePacketSchema:
    return CasePacketSchema(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        court=_required_str(record, "court"),
        docket_number=_required_str(record, "docket_number"),
        generated_at=_parse_datetime(_required_str(record, "generated_at")),
        documents=tuple(
            _source_provenance(document)
            for document in _required_record_sequence(record, "documents")
        ),
        extracted_texts=tuple(
            _extracted_text_artifact(artifact)
            for artifact in _optional_record_sequence(record, "extracted_texts")
        ),
    )


def _source_provenance(record: Mapping[str, Any]) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider=_required_str(record, "source_provider"),
        source_case_id=_required_str(record, "source_case_id"),
        source_document_id=_required_str(record, "source_document_id"),
        court=_required_str(record, "court"),
        docket_number=_required_str(record, "docket_number"),
        document_role=DocumentRole(_required_str(record, "document_role")),
        retrieved_at=_parse_datetime(_required_str(record, "retrieved_at")),
        source_url_or_reference=_required_str(record, "source_url_or_reference"),
        sha256=_required_str(record, "sha256"),
        is_predecision_material=_required_bool(record, "is_predecision_material"),
        is_mounted_for_model=_required_bool(record, "is_mounted_for_model"),
        availability_status=AvailabilityStatus(
            _optional_str(record, "availability_status")
            or AvailabilityStatus.AVAILABLE.value
        ),
        redaction_or_seal_status=RedactionOrSealStatus(
            _optional_str(record, "redaction_or_seal_status")
            or RedactionOrSealStatus.PUBLIC.value
        ),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        contains_target_outcome=_optional_bool(
            record,
            "contains_target_outcome",
            default=False,
        ),
        packet_section=_optional_str(record, "packet_section"),
        notes=_optional_str(record, "notes"),
    )


def _extracted_text_artifact(record: Mapping[str, Any]) -> ExtractedTextArtifact:
    return ExtractedTextArtifact(
        source_document_id=_required_str(record, "source_document_id"),
        extracted_at=_parse_datetime(_required_str(record, "extracted_at")),
        extraction_method=_required_str(record, "extraction_method"),
        text_sha256=_required_str(record, "text_sha256"),
        page_count=_optional_int(record, "page_count"),
        quality_flags=_required_str_tuple(record, "quality_flags")
        if "quality_flags" in record
        else (),
        notes=_optional_str(record, "notes"),
    )


def _packet_texts(
    record: Mapping[str, Any],
    case_packet: CasePacketSchema,
) -> tuple[PacketText, ...]:
    texts_value = record.get("texts")
    if isinstance(texts_value, Mapping):
        return texts_from_mapping(
            _optional_str_mapping(cast(object, texts_value), "texts"),
            artifacts=case_packet.extracted_texts,
        )
    if isinstance(texts_value, Sequence) and not isinstance(texts_value, str):
        packet_texts: list[PacketText] = []
        for item in cast(Sequence[object], texts_value):
            text_record = _mapping(item, "texts item")
            packet_texts.append(
                PacketText(
                    source_document_id=_required_str(
                        text_record,
                        "source_document_id",
                    ),
                    text=_required_str(text_record, "text"),
                    text_sha256=_optional_str(text_record, "text_sha256"),
                    quality_flags=_required_str_tuple(
                        text_record,
                        "quality_flags",
                    )
                    if "quality_flags" in text_record
                    else (),
                    extraction_method=_optional_str(
                        text_record,
                        "extraction_method",
                    ),
                )
            )
        return tuple(packet_texts)
    raise ValueError("packet-build input must include texts as an object or list")


def _model_packet(record: Mapping[str, Any]) -> ModelPacket:
    return ModelPacket(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        court=_required_str(record, "court"),
        docket_number=_required_str(record, "docket_number"),
        ablation=PacketAblation(_required_str(record, "ablation")),
        metadata=_optional_str_mapping(record.get("metadata", {}), "metadata"),
        documents=tuple(
            _packet_document(document)
            for document in _required_record_sequence(record, "documents")
        ),
        prediction_units=tuple(
            _model_packet_prediction_unit(unit)
            for unit in _required_record_sequence(record, "prediction_units")
        ),
        excluded_document_ids=_required_str_tuple(record, "excluded_document_ids")
        if "excluded_document_ids" in record
        else (),
        decision_date=_optional_str(record, "decision_date"),
        missing_optional_sections=_required_str_tuple(
            record,
            "missing_optional_sections",
        )
        if "missing_optional_sections" in record
        else (),
        related_family_id=_optional_str(record, "related_family_id"),
        mdl_family_id=_optional_str(record, "mdl_family_id"),
    )


def _model_packet_prediction_unit(record: Mapping[str, Any]) -> PredictionUnit:
    unit_id = _required_str(record, "unit_id")
    source_citations = tuple(
        _source_citation(citation)
        for citation in _optional_record_sequence(record, "source_citations")
    ) or (
        SourceCitation(
            document_id="model_packet",
            excerpt=f"model-visible prediction unit: {unit_id}",
        ),
    )
    return PredictionUnit(
        unit_id=unit_id,
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_group=_required_str(record, "defendant_group"),
        challenged_by_motion=_optional_bool(
            record,
            "challenged_by_motion",
            default=True,
        ),
        challenge_scope=ChallengeScope(
            _optional_str(record, "challenge_scope")
            or ChallengeScope.ENTIRE_CLAIM.value
        ),
        unit_confidence=_optional_float(record, "unit_confidence", default=1.0),
        source_citations=source_citations,
        grouping=DefendantGrouping(
            _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=_optional_str(record, "grouping_rationale"),
        separable_subclaim=_optional_str(record, "separable_subclaim"),
        uncertainty_notes=_optional_str(record, "uncertainty_notes"),
    )


def _packet_document(record: Mapping[str, Any]) -> PacketDocument:
    return PacketDocument(
        source_document_id=_required_str(record, "source_document_id"),
        document_role=DocumentRole(_required_str(record, "document_role")),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        source_provider=_required_str(record, "source_provider"),
        source_url_or_reference=_required_str(record, "source_url_or_reference"),
        source_sha256=_required_str(record, "source_sha256"),
        text=_required_str(record, "text"),
        text_sha256=_required_str(record, "text_sha256"),
        quality_flags=_required_str_tuple(record, "quality_flags")
        if "quality_flags" in record
        else (),
        extraction_method=_optional_str(record, "extraction_method"),
        packet_section=_optional_str(record, "packet_section"),
    )


def _prediction_unit(record: Mapping[str, Any]) -> PredictionUnit:
    return PredictionUnit(
        unit_id=_required_str(record, "unit_id"),
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_group=_required_str(record, "defendant_group"),
        challenged_by_motion=_required_bool(record, "challenged_by_motion"),
        challenge_scope=ChallengeScope(_required_str(record, "challenge_scope")),
        unit_confidence=_required_float(record, "unit_confidence"),
        source_citations=tuple(
            _source_citation(citation)
            for citation in _required_record_sequence(record, "source_citations")
        ),
        grouping=DefendantGrouping(
            _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=_optional_str(record, "grouping_rationale"),
        separable_subclaim=_optional_str(record, "separable_subclaim"),
        uncertainty_notes=_optional_str(record, "uncertainty_notes"),
    )


def _source_citation(record: Mapping[str, Any]) -> SourceCitation:
    return SourceCitation(
        document_id=_required_str(record, "document_id"),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _outcome_label(record: Mapping[str, Any]) -> OutcomeLabel:
    fully_dismissed = record.get("fully_dismissed")
    if fully_dismissed is not None and not isinstance(fully_dismissed, bool):
        raise ValueError("fully_dismissed must be a boolean or null")
    return OutcomeLabel(
        unit_id=_required_str(record, "unit_id"),
        unit_resolution=UnitResolution(_required_str(record, "unit_resolution")),
        fully_dismissed=fully_dismissed,
        amendment_class=AmendmentClass(_required_str(record, "amendment_class")),
        ambiguous=_required_bool(record, "ambiguous"),
        label_confidence=_required_float(record, "label_confidence"),
        supporting_citations=tuple(
            _outcome_citation(citation)
            for citation in _required_record_sequence(record, "supporting_citations")
        ),
        first_written_disposition_id=_required_str(
            record,
            "first_written_disposition_id",
        ),
        first_written_disposition_date=_required_str(
            record,
            "first_written_disposition_date",
        ),
        first_written_disposition_locked=_optional_bool(
            record,
            "first_written_disposition_locked",
            default=True,
        ),
        notes=_optional_str(record, "notes"),
    )


def _outcome_citation(record: Mapping[str, Any]) -> OutcomeCitation:
    return OutcomeCitation(
        document_id=_required_str(record, "document_id"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _normalized_docket_entry(record: Mapping[str, Any]) -> NormalizedDocketEntry:
    return NormalizedDocketEntry(
        source_provider=_required_str(record, "source_provider"),
        source_case_id=_required_str(record, "source_case_id"),
        docket_entry_id=_required_str(record, "docket_entry_id"),
        entry_number=_optional_str(record, "entry_number"),
        entry_text=_required_str(record, "entry_text"),
        filed_at=_optional_str(record, "filed_at"),
        document_role=DocumentRole(_required_str(record, "document_role")),
        source_document_ids=_required_str_tuple(record, "source_document_ids"),
        source_url=_optional_str(record, "source_url"),
    )


def _computed_base_rate(labels: Iterable[OutcomeLabel]) -> float:
    outcomes = tuple(label.primary_outcome for label in labels)
    scored = tuple(outcome for outcome in outcomes if outcome is not None)
    if not scored:
        raise ValueError("cannot compute base rate without scored labels")
    return sum(scored) / len(scored)


def _record_model_id(record: Mapping[str, Any]) -> str:
    model_id = _optional_str(record, "model_id")
    if model_id is not None:
        return model_id
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        metadata_mapping = cast(Mapping[object, object], metadata)
        metadata_model = metadata_mapping.get("model_id")
        if isinstance(metadata_model, str) and metadata_model.strip():
            return metadata_model
    solver_id = _required_str(record, "solver_id")
    if ":" in solver_id:
        return solver_id.split(":", maxsplit=1)[1]
    return solver_id


def _candidate_id(record: Mapping[str, Any]) -> str:
    return _optional_str(record, "candidate_id") or (
        f"cand_{_required_str(record, 'case_id')}"
    )


def _read_records(path: Path) -> list[JsonRecord]:
    if path.suffix == ".jsonl":
        records: list[JsonRecord] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                loaded = _loads_json(line)
                if not isinstance(loaded, Mapping):
                    raise ValueError(f"{path}:{line_number} must contain a JSON object")
                records.append(dict(cast(Mapping[str, Any], loaded)))
        return records

    text = path.read_text(encoding="utf-8")
    loaded = _loads_json(text)
    if isinstance(loaded, list):
        return [_mapping(item, f"{path} item") for item in cast(list[object], loaded)]
    if isinstance(loaded, Mapping):
        mapping = dict(cast(Mapping[str, Any], loaded))
        records_value = mapping.get("records")
        if isinstance(records_value, list):
            return [
                _mapping(item, "records item")
                for item in cast(list[object], records_value)
            ]
        return [mapping]
    raise ValueError(f"{path} must contain a JSON object, array, or JSONL records")


def _read_json_object(path: Path) -> JsonRecord:
    loaded = _loads_json(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, Any], loaded))


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    )
    path.write_text(payload, encoding="utf-8")


def _append_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


def _loads_json(payload: str) -> object:
    return json.loads(
        payload,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"JSON numeric constant {value} is not supported")
        ),
    )


def _mock_output_text(args: argparse.Namespace) -> str:
    mock_output = _optional_mock_output_text(args)
    if mock_output is None:
        raise ValueError("mock output is required")
    return mock_output


def _optional_mock_output_text(args: argparse.Namespace) -> str | None:
    mock_output_file = cast(Path | None, getattr(args, "mock_output_file", None))
    if mock_output_file is not None:
        return mock_output_file.read_text(encoding="utf-8")
    return cast(str | None, getattr(args, "mock_output", None))


def _resolve_under(root: Path, child: Path, *, field_name: str) -> Path:
    resolved_root = root.resolve()
    resolved_child = (
        child.resolve() if child.is_absolute() else (resolved_root / child).resolve()
    )
    if not resolved_child.is_relative_to(resolved_root):
        raise ValueError(f"{field_name} must stay under {resolved_root}")
    return resolved_child


def _write_dry_run_plan(
    command: str,
    plan_path: Path,
    *,
    output_paths: Sequence[Path],
    record_count: int,
    input_path: Path | None = None,
    log_record_count: int | None = None,
    **extra: Any,
) -> int:
    _write_json(
        plan_path,
        _dry_run_record(
            command,
            input_path=input_path,
            output_paths=output_paths,
            record_count=record_count,
            **extra,
        ),
    )
    _log_event(command, "dry_run", plan_path, log_record_count)
    return 0


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_event(
    stage: str,
    event: str,
    artifact_path: Path,
    record_count: int | None = None,
) -> None:
    payload: JsonRecord = {
        "stage": stage,
        "event": event,
        "artifact_path": str(artifact_path),
    }
    if record_count is not None:
        payload["record_count"] = record_count
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)


def _dry_run_record(
    command: str,
    *,
    output_paths: Sequence[Path],
    input_path: Path | None = None,
    record_count: int,
    **extra: Any,
) -> JsonRecord:
    record: JsonRecord = {
        "command": command,
        "dry_run": True,
        "record_count": record_count,
        "output_paths": [str(path) for path in output_paths],
    }
    if input_path is not None:
        record["input_path"] = str(input_path)
    record.update(extra)
    return record


def _report_paths(output_dir: Path) -> tuple[Path, Path, Path, Path]:
    return (
        output_dir / "leaderboard.json",
        output_dir / "leaderboard.csv",
        output_dir / "leaderboard.md",
        output_dir / "leaderboard.html",
    )


def _fixture_cohort_policy_decisions() -> JsonRecord:
    taxonomy = cohort_reason_policy_taxonomy()
    return {
        "cycle_id": "cycle_fixture_e2e",
        "cycle_acquisition_hash": "e" * 64,
        "eligibility_anchor": "2026-05-14",
        "stop_rule": {
            "mode": "target_or_deadline",
            "target_clean_cases": 1,
            "search_window_end": "2026-05-18",
            "stop_on_frontier_exhaustion": True,
            "stop_on_budget_headroom_exhaustion": True,
        },
        "window_policy": {
            "overlap_days": 1,
            "backfill_late_indexed": True,
            "refresh_before_purchase": True,
        },
        "refresh_policy": {
            **{field: list(codes) for field, codes in taxonomy.items()},
            "evidence_precedence": {
                "transient": 0,
                "excluded_refreshable": 10,
                "accepted": 20,
                "newly_free": 30,
                "excluded_immutable": 100,
            },
            "transition_semantics": {
                "immutable_reconsideration": "never",
                "transient_supersedes_evidenced": False,
                "higher_rank_supersedes_lower_rank": True,
                "latest_wins_equal_rank": True,
            },
        },
        "packet_completeness": {
            "motion_or_combined_memorandum_required": True,
            "opposition_required_if_docketed": True,
            "reply_required": False,
        },
        "target_motion": {
            "selector": "earliest_eligible_mtd_then_lowest_entry_number",
            "exactly_one_per_candidate": True,
        },
        "purchase_policy": {
            "rule": "buy_cheapest_complete",
            "cycle_budget_usd": "0.00",
            "max_per_case_usd": "0.00",
            "reservation_headroom_required": True,
        },
        "disclosure_clearance": {
            "all_documents_require_clearance": True,
            "unknown_or_unscannable": "quarantine",
            "replacement_rule": "next_cheapest_eligible_under_same_cap",
        },
        "reduced_n": {
            "target_clean_cases": 1,
            "claim_tiers": [
                {
                    "minimum_clean_cases": 1,
                    "maximum_clean_cases": 1,
                    "claim_class": "target",
                    "minimum_prediction_units": None,
                    "insufficient_units_action": None,
                }
            ],
            "below_minimum_action": "pilot_only_no_official_cycle",
        },
    }


def _fixture_artifact_paths(output_dir: Path) -> tuple[Path, ...]:
    return (
        output_dir / "docket_entries.jsonl",
        output_dir / "candidates.jsonl",
        output_dir / "retrievals.jsonl",
        output_dir / "document-manifest.jsonl",
        output_dir / "extracted_texts.jsonl",
        output_dir / "linkage.jsonl",
        output_dir / "eligibility.json",
        output_dir / "case-mix-diagnostics.json",
        output_dir / "exclusion-ledger.jsonl",
        output_dir / "units.jsonl",
        output_dir / "labels.jsonl",
        output_dir / "candidate-manifest.jsonl",
        output_dir / "packets.jsonl",
        output_dir / "runs.jsonl",
        output_dir / "accounting.jsonl",
        output_dir / "scores.json",
        output_dir / "prompt.md",
        output_dir / "scorer.py",
        output_dir / "harness.txt",
        output_dir / "model-registry.json",
        output_dir / "baselines.json",
        output_dir / "labeling-policy.json",
        output_dir / "cohort-policy.json",
        output_dir / "execution-policy.json",
        output_dir / "manifests" / "cycle_fixture_e2e.freeze.json",
        output_dir / "report" / "leaderboard.json",
        output_dir / "report" / "leaderboard.csv",
        output_dir / "report" / "leaderboard.md",
        output_dir / "report" / "leaderboard.html",
        output_dir / "artifact-manifest.json",
        output_dir / "artifact-index.json",
    )


def _mapping(value: object, field_name: str) -> JsonRecord:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return dict(cast(Mapping[str, Any], value))


def _optional_record(value: object, field_name: str) -> JsonRecord:
    if value is None:
        return {}
    return _mapping(value, field_name)


def _required_record(record: Mapping[str, Any], field_name: str) -> JsonRecord:
    return _mapping(_required(record, field_name), field_name)


def _required_record_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[JsonRecord, ...]:
    value = _required(record, field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    return tuple(
        _mapping(item, f"{field_name} item") for item in cast(Sequence[object], value)
    )


def _optional_record_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[JsonRecord, ...]:
    if field_name not in record or record[field_name] is None:
        return ()
    return _required_record_sequence(record, field_name)


def _required(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in record:
        raise ValueError(f"{field_name} is required")
    return record[field_name]


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _required(record, field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_str_tuple(record: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = _required(record, field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list of strings")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        strings.append(item)
    return tuple(strings)


def _optional_str_tuple(record: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    if field_name not in record:
        return ()
    return _required_str_tuple(record, field_name)


def _optional_str_mapping(value: object, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    mapping = cast(Mapping[object, object], value)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{key}] must be a non-empty string")
        result[key] = item
    return result


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = _required(record, field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_bool(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool,
) -> bool:
    value = record.get(field_name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = _required(record, field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _optional_int_tuple(value: object) -> tuple[int, ...] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("integer tuple field must be a list")
    values: list[int] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError("integer tuple field must contain integers")
        values.append(item)
    return tuple(values)


def _required_float(record: Mapping[str, Any], field_name: str) -> float:
    value = _required(record, field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return _finite_float(float(value), field_name)


def _optional_float(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: float,
) -> float:
    value = record.get(field_name)
    if value is None:
        return default
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return _finite_float(float(value), field_name)


def _optional_number(record: Mapping[str, Any], field_name: str) -> float | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return _finite_float(float(value), field_name)


def _finite_float(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

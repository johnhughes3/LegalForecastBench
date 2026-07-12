"""Command-line orchestration for LegalForecast-MTD benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict
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
    CaseDevPacerPurchaseClient,
)
from legalforecast.ingestion.case_dev_recap_batch import enrich_recap_discovery_batch
from legalforecast.ingestion.case_dev_smoke import (
    CaseDevSmokeConfig,
    case_dev_smoke_query_terms,
    plan_case_dev_smoke,
    render_case_dev_smoke_markdown,
    run_case_dev_smoke,
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
    bridge_courtlistener_case_dev_documents,
    bridge_public_plan_paid_gaps,
    merge_download_manifest_records,
)
from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_API_TOKEN_ENV,
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
)
from legalforecast.ingestion.cycle_acquisition_assembler import (
    CycleAssembly,
    assemble_cycle_acquisition,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
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
from legalforecast.ingestion.docket_markdown import ControlledDocketMarkdownArtifacts
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    NormalizedDocketEntry,
)
from legalforecast.ingestion.firecrawl_recap_discovery import (
    FROZEN_MTD_SEARCH_TERMS,
    RecapDiscoveredEntry,
    RecapSearchError,
    RecapSearchHit,
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
    plan_missing_core_document_budget,
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
from legalforecast.ingestion.recap_partial_checkpoint import (
    RecapPartialProjectionError,
    project_partial_recap_checkpoint,
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
    llm_unitize_cases,
    unitization_review_queue_records,
)
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.path_safety import safe_path_component
from legalforecast.protocol import (
    FrozenArtifactName,
    build_candidate_manifest_record,
    freeze_cycle,
    sha256_file,
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
from legalforecast.selection.exclusion_ledger import merge_exclusion_ledger_records
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
    verify_finalized_prediction_units,
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

    acquisition = subparsers.add_parser(
        "acquisition",
        help="Production acquisition pipeline commands.",
    )
    acquisition_subparsers = acquisition.add_subparsers(
        dest="acquisition_command",
        metavar="COMMAND",
    )
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
    acquisition_funnel_report = acquisition_subparsers.add_parser(
        "funnel-report",
        help="Reconcile discovery exclusions into a versioned acquisition funnel.",
    )
    _add_acquisition_funnel_report_arguments(acquisition_funnel_report)
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
    acquisition_bridge_pacer_gaps = acquisition_subparsers.add_parser(
        "bridge-pacer-gaps",
        help=(
            "Resolve CourtListener candidates to authoritative case.dev document "
            "IDs and emit free-first recovery inputs."
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
        help="Execute guarded case.dev/PACER missing-core purchases.",
    )
    _add_acquisition_purchase_missing_arguments(acquisition_purchase)
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


def _add_acquisition_plan_arguments(parser: argparse.ArgumentParser) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--core-filter-results", type=Path, required=True)
    parser.add_argument("--budget-plan-output", type=Path)
    parser.add_argument("--max-missing-core-documents-per-case", type=int, default=24)
    parser.add_argument("--cost-per-document-usd", default="3.05")
    parser.add_argument("--max-projected-budget-usd", default="2250.00")
    parser.set_defaults(handler=_cmd_acquisition_plan)


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
        "--decision-filed-on-or-after",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive docket-entry disposition discovery anchor.",
    )
    parser.add_argument(
        "--decision-filed-on-or-before",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive docket-entry discovery upper bound.",
    )
    parser.add_argument(
        "--query-term",
        dest="query_terms",
        action="append",
        help=(
            "MTD or eligible Rule 12(c) RECAP entry-search term. Repeat to "
            "replace the frozen default set."
        ),
    )
    parser.add_argument(
        "--max-pages-per-term",
        type=int,
        default=1_000,
        help="Fail-closed pagination ceiling per term; default 1000.",
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
    parser.add_argument("--raw-search-html-dir", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_discover_firecrawl_recap)


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
        required=True,
        help="Firecrawl run whose successful search artifacts will be verified.",
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
    parser.add_argument("--target-clean-cases", type=int, default=150)
    parser.add_argument("--max-candidates", type=int, default=3000)
    parser.add_argument(
        "--search-page-size",
        type=int,
        default=50,
        help="CourtListener RECAP search page size, from 1 through 100.",
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
    parser.add_argument("--summary-output", type=Path)
    parser.set_defaults(handler=_cmd_acquisition_discover_courtlistener)


def _add_acquisition_funnel_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--discovery-summary", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--public-download-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_cmd_acquisition_funnel_report)


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
            "Checkpoint writes remain serialized. Fixtures require 1."
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
    parser.add_argument("--case-dev-fixture", type=Path)
    parser.add_argument(
        "--live-purchase",
        action="store_true",
        help="Allow live paid case.dev/PACER purchase requests.",
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
        "--batch-root",
        type=Path,
        action="append",
        required=True,
        help=(
            "Immutable acquisition batch root. Repeat in chronological order; "
            "later evidenced records supersede refreshable earlier records."
        ),
    )
    parser.set_defaults(handler=_cmd_acquisition_assemble_cycle)


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
        default=[],
        help=(
            "Registry key in provider:model_id form for one LLM label judge. "
            "Repeat for an ensemble; omitted means all entries in the registry."
        ),
    )
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
        help="Audit JSONL emitted by acquisition llm-label.",
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
        help="Directory containing saved CourtListener docket HTML by candidate ID.",
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
    )
    write_missing_core_budget_plan(plan, output_path)
    _write_acquisition_completion(
        args,
        stage="acquisition-plan",
        input_paths=(input_path,),
        output_paths=(output_path,),
        record_count=len(plan.case_plans),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "total_missing_core_documents": plan.total_missing_core_documents,
            "total_estimated_cost_usd": plan.total_estimated_cost_usd,
        },
    )
    return 0


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


class _BudgetedRecapSearchTransport:
    """Adapt page-at-a-time RECAP discovery to the durable scheduler."""

    def __init__(self, scheduler: BudgetedFirecrawlScheduler) -> None:
        self.scheduler = scheduler
        self._ordinals: dict[str, int] = {}
        self._pages: dict[str, FirecrawlPageRecord] = {}

    @property
    def pages(self) -> tuple[FirecrawlPageRecord, ...]:
        return tuple(
            self._pages[url]
            for url, _ordinal in sorted(
                self._ordinals.items(), key=lambda item: item[1]
            )
        )

    def fetch(self, *, source_url: str) -> str:
        target = parse_recap_search_url(source_url)
        ordinal = self._ordinals.setdefault(source_url, len(self._ordinals))
        target_id = (
            "recap-search-"
            + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
        )
        result = self.scheduler.run(
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
        self._pages[source_url] = page
        return page.raw_html


def _cmd_acquisition_project_firecrawl_recap_checkpoint(
    args: argparse.Namespace,
) -> int:
    """Materialize verified successful pages without claiming search completion."""

    output_root = _acquisition_output_root(args)
    store_path = cast(Path, args.cycle_store)
    run_id = cast(str, args.run_id)
    pages_path = _acquisition_path(
        args,
        "pages_output",
        output_root / "checkpoints" / f"{run_id}-partial-recap-pages.jsonl",
    )
    entries_path = _acquisition_path(
        args,
        "entries_output",
        output_root / "checkpoints" / f"{run_id}-partial-recap-entries.jsonl",
    )
    dockets_path = _acquisition_path(
        args,
        "dockets_output",
        output_root / "checkpoints" / f"{run_id}-partial-recap-dockets.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / f"{run_id}-partial-recap-summary.json",
    )
    input_paths = (store_path,)
    output_paths = (pages_path, entries_path, dockets_path, summary_path)
    dry_run = _acquisition_dry_run(args)
    if dry_run:
        summary: JsonRecord = {
            "schema_version": "legalforecast.recap_partial_checkpoint_summary.v1",
            "dry_run": True,
            "run_id": run_id,
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
            credit_summary = dict(store.firecrawl_run_summary(run_id))
            batch_id_value = credit_summary.get("batch_id")
            if not isinstance(batch_id_value, str) or not batch_id_value:
                raise CycleAcquisitionStoreError(
                    "durable Firecrawl run has no valid batch identity"
                )
            batch_id = batch_id_value
            pages = load_successful_firecrawl_pages(store=store, run_id=run_id)
            if not pages:
                raise RecapPartialProjectionError(
                    "durable Firecrawl run contains no successful search pages"
                )
            projection = project_partial_recap_checkpoint(pages)
            _commit_recap_discovery_pages(
                store=store,
                batch_id=batch_id,
                pages=pages,
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
        "store_projection_committed": True,
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


def _cmd_acquisition_discover_firecrawl_recap(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    batch_id = cast(str, args.batch_id)
    run_id = cast(str, args.run_id)
    store_path = _acquisition_path(
        args, "cycle_store", output_root / "cycle-acquisition.sqlite3"
    )
    entries_path = _acquisition_path(
        args,
        "entries_output",
        output_root / "checkpoints" / f"{batch_id}-recap-entries.jsonl",
    )
    dockets_path = _acquisition_path(
        args,
        "dockets_output",
        output_root / "checkpoints" / f"{batch_id}-recap-dockets.jsonl",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "checkpoints" / f"{batch_id}-recap-summary.json",
    )
    raw_search_html_dir = _acquisition_path(
        args,
        "raw_search_html_dir",
        output_root / "raw-recap-search-html",
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
    terms = tuple(cast(Sequence[str] | None, args.query_terms) or ())
    if not terms:
        terms = FROZEN_MTD_SEARCH_TERMS
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
    proxy = cast(str, args.proxy)
    force_browser = cast(bool, args.force_browser)
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
        "provider": "courtlistener-recap-web-via-firecrawl",
        "decision_window_start": anchor.isoformat(),
        "decision_window_end": window_end.isoformat(),
        "query_terms": list(terms),
        "query_term_order_is_frozen": True,
        "max_pages_per_term": max_pages_per_term,
    }
    run_config: JsonRecord = {
        "purpose": "anchored-recap-entry-discovery",
        "proxy": proxy,
        "force_browser": force_browser,
        "max_attempts_per_page": max_attempts,
        "provider_breaker_threshold": breaker_threshold,
        "query_terms": list(terms),
        "raw_artifact_root": str(raw_search_html_dir.resolve()),
    }
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
            stage="discover-firecrawl-recap",
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
        source = (
            FirecrawlCourtListenerHTMLSource(
                FirecrawlConfig.from_env(
                    proxy=cast(Any, proxy), force_browser=force_browser
                )
            )
            if live
            else FirecrawlCourtListenerHTMLSource(
                FirecrawlConfig(
                    api_key="offline-fixture",
                    proxy=cast(Any, proxy),
                    force_browser=force_browser,
                ),
                transport=_firecrawl_fixture_transport(cast(Path, fixture_path)),
            )
        )
        with CycleAcquisitionStore(store_path) as store:
            cycle_hash = store.ensure_cycle(policy)
            batch_digest = store.ensure_batch(batch_id, batch_config)
            store.ensure_terms(batch_id, terms)
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
            )
            transport = _BudgetedRecapSearchTransport(scheduler)
            discovery = discover_recap_mtd_entries(
                transport=transport,
                entry_date_filed_after=anchor,
                entry_date_filed_before=window_end,
                terms=terms,
                max_pages_per_term=max_pages_per_term,
            )
            _commit_recap_discovery_pages(
                store=store,
                batch_id=batch_id,
                pages=transport.pages,
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
            stage="discover-firecrawl-recap",
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
        stage="discover-firecrawl-recap",
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
) -> None:
    """Project verified raw RECAP pages into durable discovery progress."""

    for record in pages:
        page = parse_recap_search_html(record.raw_html, source_url=record.source_url)
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
    identity = "\0".join(
        (
            hit.entry_key,
            hit.document_url,
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
) -> tuple[JsonRecord, int]:
    active_client = client or _case_dev_client(
        command="enrich-recap-case-dev", fixture_path=fixture_path, live=live
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
                    )

                futures = {
                    future
                    for _ in range(workers)
                    if (future := submit_one()) is not None
                }
                while futures:
                    future = next(as_completed(futures))
                    futures.remove(future)
                    progress, one_request_count = future.result()
                    request_count += one_request_count
                    progress = _bound_case_dev_transient_progress(
                        progress,
                        transient_attempts_by_index=transient_attempts_by_index,
                    )
                    _append_jsonl(progress_path, (progress,))
                    progress_by_index[cast(int, progress["input_index"])] = progress
                    if (replacement := submit_one()) is not None:
                        futures.add(replacement)
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
    exclusions = [
        {"candidate_id": f"courtlistener-docket-{docket_id}", "reason": "fetch_failed"}
        for docket_id in result.failed_docket_ids
    ]
    _write_jsonl(successes_path, successes)
    _write_jsonl(exclusions_path, exclusions)
    summary = {
        **dict(result.credit_summary),
        "selected_batch_id": cast(str, args.selected_batch_id),
        "success_count": len(successes),
        "exclusion_count": len(exclusions),
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
        report = build_acquisition_funnel_report(
            discovery_summary=_read_json_object(cast(Path, args.discovery_summary)),
            exclusions=_read_records(cast(Path, args.exclusions)),
            public_download_summary=_read_json_object(
                cast(Path, args.public_download_summary)
            ),
        )
    except (FunnelReportError, OSError, UnicodeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc
    _write_json(cast(Path, args.output), report)
    return 0


def _cmd_acquisition_discover_courtlistener(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    screened_cases_path = _acquisition_path(
        args,
        "screened_cases_output",
        output_root / "courtlistener-screened-cases.jsonl",
    )
    exclusions_path = _acquisition_path(
        args,
        "exclusions_output",
        output_root / "courtlistener-discovery-exclusions.jsonl",
    )
    raw_html_dir = _acquisition_path(
        args,
        "raw_html_dir",
        output_root / "raw-courtlistener-html",
    )
    summary_path = _acquisition_path(
        args,
        "summary_output",
        output_root / "courtlistener-discovery-summary.json",
    )
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
    input_paths = tuple(
        path for path in (fixture_path, html_fixture_dir) if path is not None
    )
    output_paths = (
        screened_cases_path,
        exclusions_path,
        raw_html_dir,
        summary_path,
    )

    if dry_run:
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
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc

    if cycle_store_path is not None and batch_id is not None:
        try:
            with CycleAcquisitionStore(cycle_store_path) as store:
                store.ensure_cycle(_cycle_acquisition_policy(anchor=anchor))
                store.ensure_batch(
                    batch_id,
                    {
                        "provider": "courtlistener",
                        "search_window_start": search_window_start.isoformat(),
                        "search_window_end": search_window_end.isoformat(),
                        "query_terms": list(query_terms),
                        "target_clean_cases": target_clean_cases,
                        "max_candidates": max_candidates,
                        "search_page_size": search_page_size,
                    },
                )
        except CycleAcquisitionStoreError as exc:
            raise CommandError(str(exc)) from exc

    config = CourtListenerConfig.from_env()
    if live:
        if config.api_token is None:
            raise CommandError(f"{COURTLISTENER_API_TOKEN_ENV} is required with --live")
        client = CourtListenerClient(config=config)
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
        )
    except (CourtListenerClientError, ValueError) as exc:
        _write_acquisition_failure(
            args,
            stage="discover-courtlistener",
            input_paths=input_paths,
            output_paths=output_paths,
            reason=str(exc),
            paid_activity_requested=False,
        )
        raise CommandError(str(exc)) from exc

    _write_jsonl(screened_cases_path, list(result.screened_cases))
    _write_jsonl(
        exclusions_path,
        [exclusion.to_record() for exclusion in result.exclusions],
    )
    _write_json(summary_path, {**result.summary, "dry_run": False, "live": live})
    _write_acquisition_completion(
        args,
        stage="discover-courtlistener",
        input_paths=input_paths,
        output_paths=output_paths,
        record_count=len(result.screened_cases),
        dry_run=False,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "anchor_date": anchor.isoformat(),
            "target_clean_cases": target_clean_cases,
            "accepted_case_count": len(result.screened_cases),
            "excluded_case_count": len(result.exclusions),
        },
    )
    return 0


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
    raw_html_dir = cast(Path | None, args.raw_html_dir)
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
    raw_html_dir = _verified_snapshot_raw_html_directory(
        snapshot_path,
        requested=raw_html_dir,
        use_embedded_entries=cast(bool, args.use_embedded_entries),
    )
    records = _read_records(screened_cases_path)
    dry_run = _acquisition_dry_run(args)
    plan = plan_public_packet_downloads(
        records,
        raw_html_dir=raw_html_dir,
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
            if raw_html_dir is None
            else (snapshot_path, screened_cases_path, raw_html_dir)
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


def _cmd_acquisition_screen_firecrawl(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
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
        if snapshot_path.exists():
            raise FileExistsError(
                f"snapshot target already exists; refusing stale reuse: {snapshot_path}"
            )
        _validate_firecrawl_success_commitments(success_records)
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


def _cmd_acquisition_bridge_pacer_gaps(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    screened_cases_path = cast(Path, args.screened_cases)
    raw_html_dir = cast(Path | None, args.raw_html_dir)
    fixture_path = cast(Path | None, args.case_dev_fixture)
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
    records = _read_records(screened_cases_path)
    dry_run = _acquisition_dry_run(args)
    live = cast(bool, args.live_case_dev)
    input_paths = tuple(
        path
        for path in (
            screened_cases_path,
            raw_html_dir,
            fixture_path,
            public_selection_path,
            paid_gaps_path,
            free_download_manifest_path,
        )
        if path is not None
    )
    if dry_run:
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
                "schema_version": ("legalforecast.courtlistener_case_dev_bridge.v1"),
                "dry_run": True,
                "screened_case_count": len(records),
                "free_first_required": True,
            },
        )
        selected_count = 0
        paid_document_count = 0
        free_request_count = 0
        excluded_count = 0
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
            result = bridge_public_plan_paid_gaps(
                records,
                public_selection_records=_read_records(public_selection_path),
                paid_gap_records=_read_records(paid_gaps_path),
                free_download_records=_read_records(free_download_manifest_path),
                client=client,
                raw_html_dir=raw_html_dir,
                use_embedded_entries=cast(bool, args.use_embedded_entries),
            )
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
        _write_json(summary_path, {**result.summary_record(), "dry_run": False})
        selected_count = result.selected_case_count
        paid_document_count = result.paid_document_count
        free_request_count = len(result.free_download_requests)
        excluded_count = len(result.exclusions)
    _write_acquisition_completion(
        args,
        stage="bridge-pacer-gaps",
        input_paths=input_paths,
        output_paths=(
            requests_path,
            selection_path,
            case_relevance_path,
            exclusions_path,
            summary_path,
        ),
        record_count=selected_count,
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={
            "selected_case_count": selected_count,
            "excluded_case_count": excluded_count,
            "free_download_request_count": free_request_count,
            "paid_document_count": paid_document_count,
            "free_first_required": True,
            "next_stage": (
                "filter-core-documents" if public_first else "download-free"
            ),
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
    dry_run = _acquisition_dry_run(args)
    live_purchase = cast(bool, args.live_purchase)
    acknowledge_fees = cast(bool, args.acknowledge_pacer_fees)
    capability = CaseDevPacerCapability(cast(str, args.capability))
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
    result = CaseDevPacerPurchaseClient(
        client,
        capability=capability,
    ).execute_purchase_plan(
        execution_plan,
        live=live_purchase and not dry_run,
        acknowledge_pacer_fees=acknowledge_fees,
    )
    _write_json(output_path, result.to_record())
    paid_activity_executed = result.executed_purchase_count > 0
    _write_acquisition_completion(
        args,
        stage="purchase-missing",
        input_paths=(plan_path,),
        output_paths=(output_path,),
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
    if not _acquisition_dry_run(args):
        _write_jsonl(clearance_path, clearance_rows)
        _write_jsonl(quarantine_path, quarantined)
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
        dry_run=_acquisition_dry_run(args),
        paid_activity_requested=False,
        paid_activity_executed=False,
        extra={"quarantined_document_count": len(quarantined)},
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


def _cmd_acquisition_llm_unitize(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    provider_journal_path = output_root / "provider-attempts.sqlite3"
    selection_path = cast(Path, args.selection)
    parser_manifest_path = cast(Path, args.parser_manifest)
    markdown_root = cast(Path | None, args.markdown_root) or (output_root / "markdown")
    model_registry_path = cast(Path, args.model_registry)
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
        result = llm_unitize_cases(
            selection_records=selection_records,
            parser_records=_read_records(parser_manifest_path),
            markdown_root=markdown_root,
            registry_entry=registry_entry,
            model_registry_sha256=registry_sha256,
            timeout_seconds=cast(float, args.timeout_seconds),
            continue_on_error=cast(bool, args.continue_on_error),
            provider_journal_path=provider_journal_path,
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
        input_paths=(selection_path, parser_manifest_path, model_registry_path),
        output_paths=(
            prediction_units_path,
            audit_path,
            review_queue_path,
            provider_journal_path,
        ),
        record_count=len(selection_records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
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
        ),
        output_paths=(
            labels_path,
            audit_path,
            lawyer_review_queue_path,
            provider_journal_path,
        ),
        record_count=len(selection_records),
        dry_run=dry_run,
        paid_activity_requested=False,
        paid_activity_executed=False,
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
        result = apply_adjudicated_reviews(
            label_records=_read_records(labels_path),
            adjudication_records=_read_records(adjudications_path),
            decision_texts=_load_decision_texts(decision_texts_path),
            label_audit_records=llm_label_audit_records,
            audit_sample_size=cast(int, args.audit_sample_size),
            human_blind_disagreement_rate=cast(
                float,
                args.human_blind_disagreement_rate,
            ),
        )
        _write_jsonl(labels_output_path, result.records)
        _write_jsonl(audit_path, result.audit_records)
    _write_acquisition_completion(
        args,
        stage="apply-lawyer-review",
        input_paths=(
            labels_path,
            adjudications_path,
            decision_texts_path,
            llm_label_audit_path,
        ),
        output_paths=(labels_output_path, audit_path),
        record_count=len(_read_records(adjudications_path)) if not dry_run else 0,
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
    raw_html_dir = cast(Path, args.raw_html_dir)
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
        model_registry_path = cast(Path, args.model_registry)
        registry = load_model_registry(model_registry_path)
        official_entries = require_official_registry_entries(registry.entries)
        decision_filed_on_or_after = earliest_eligible_decision_date(official_entries)
        plan = plan_packet_build_inputs(
            selection_records=records,
            download_records=_read_records(download_manifest_path),
            parser_records=_read_records(parser_manifest_path),
            prediction_unit_records=_read_records(prediction_units_path),
            raw_html_dir=raw_html_dir,
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
    unitization_review_path = cast(Path, args.unitization_review_queue)
    unitization_adjudications_path = cast(
        Path,
        args.unitization_review_adjudications,
    )
    labels_path = cast(Path, args.labels)
    label_audit_path = cast(Path, args.llm_label_audit)
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
        unitization_review_path,
        unitization_adjudications_path,
        labels_path,
        label_audit_path,
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
        unitization_review_records = _read_records(unitization_review_path)
        unitization_adjudication_records = _read_records(unitization_adjudications_path)
        try:
            verify_finalized_prediction_units(
                prediction_unit_records,
                raw_prediction_unit_records,
                unitization_adjudication_records,
            )
        except UnitizationReviewError as exc:
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
    return CaseDevClient.live_from_env()


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


def _verified_snapshot_raw_html_directory(
    snapshot_path: Path,
    *,
    requested: Path | None,
    use_embedded_entries: bool,
) -> Path | None:
    artifact_records = _read_records(snapshot_path / "raw-artifacts.jsonl")
    artifact_paths: list[Path] = []
    for record in artifact_records:
        raw_path = record.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandError(
                "verified snapshot contains an invalid raw artifact path"
            )
        artifact_paths.append(Path(raw_path).resolve())
    if not artifact_paths:
        if requested is not None:
            raise CommandError(
                "--raw-html-dir is not allowed when the verified snapshot has no "
                "committed raw artifacts"
            )
        if not use_embedded_entries:
            raise CommandError(
                "verified snapshot has no raw docket artifacts; use embedded entries "
                "only for an explicitly authorized fixture path"
            )
        return None
    parents = {path.parent for path in artifact_paths}
    if len(parents) != 1:
        raise CommandError(
            "verified snapshot raw artifacts do not share one planner directory"
        )
    committed_directory = next(iter(parents))
    if requested is not None and requested.resolve() != committed_directory:
        raise CommandError(
            "--raw-html-dir must exactly match the verified snapshot artifact directory"
        )
    return committed_directory


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
    reserved = summary.get("reserved_credits")
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
            )
            for case_plan in plan.case_plans
        ),
        cost_per_document=plan.cost_per_document,
        max_projected_budget=plan.max_projected_budget,
        max_missing_core_documents_per_case=(plan.max_missing_core_documents_per_case),
        dry_run=True,
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
) -> FreeDocumentSource:
    if fixture_path is not None and live_case_dev_download:
        raise CommandError(
            "acquisition recover-purchased accepts either --fixture-documents "
            "or --live-case-dev-download, not both"
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
    raise CommandError(
        "acquisition recover-purchased --execute requires --fixture-documents "
        "for offline fixtures or --live-case-dev-download for already-purchased "
        "case.dev documents"
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
    bundle_path = output_dir / "manifests" / "cycle_fixture_e2e.freeze.json"
    _write_text(prompt_path, _fixture_prompt_text())
    _write_text(scorer_path, _fixture_scorer_text())
    _write_text(harness_path, _fixture_harness_text())
    _write_text(
        model_registry_path,
        json.dumps(_fixture_model_registry_records(), indent=2, sort_keys=True) + "\n",
    )
    _write_json(baselines_path, _fixture_baselines_record(labels))
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

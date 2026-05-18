"""Command-line orchestration for LegalForecast-MTD benchmark artifacts."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
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
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseClient,
)
from legalforecast.ingestion.case_dev_smoke import (
    CaseDevSmokeConfig,
    plan_case_dev_smoke,
    render_case_dev_smoke_markdown,
    run_case_dev_smoke,
)
from legalforecast.ingestion.core_document_filter import CoreDocumentFilterResult
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
)
from legalforecast.ingestion.docket_markdown import ControlledDocketMarkdownArtifacts
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    NormalizedDocketEntry,
)
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadError,
    FreeDocumentDownloadRequest,
    download_free_docket_documents,
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
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    RedactionOrSealStatus,
    SourceDocumentProvenance,
    sha256_text,
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
from legalforecast.path_safety import safe_path_component
from legalforecast.protocol import (
    FrozenArtifactName,
    build_candidate_manifest_record,
    freeze_cycle,
    load_preregistration,
    sha256_file,
    validate_preregistration_record,
)
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
from legalforecast.selection.motion_linkage import link_mtd_dispositions
from legalforecast.unitization.construct_units import (
    StageAConstructionInput,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    UnitizationReviewReason,
    construct_stage_a_units,
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
            "Docket search term to run; repeat to override the default MTD/Rule 12 "
            "term set."
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

    acquisition = subparsers.add_parser(
        "acquisition",
        help="Production acquisition pipeline commands.",
    )
    acquisition_subparsers = acquisition.add_subparsers(
        dest="acquisition_command",
        metavar="COMMAND",
    )
    acquisition_plan = acquisition_subparsers.add_parser(
        "plan",
        help="Plan missing-core paid recovery from core-document filter results.",
    )
    _add_acquisition_plan_arguments(acquisition_plan)
    acquisition_download = acquisition_subparsers.add_parser(
        "download-free",
        help="Download fixture-safe free public docket documents.",
    )
    _add_acquisition_download_free_arguments(acquisition_download)
    acquisition_purchase = acquisition_subparsers.add_parser(
        "purchase-missing",
        help="Execute guarded case.dev/PACER missing-core purchases.",
    )
    _add_acquisition_purchase_missing_arguments(acquisition_purchase)
    acquisition_parse = acquisition_subparsers.add_parser(
        "parse-documents",
        help="Convert acquired documents to Markdown parser artifacts.",
    )
    _add_acquisition_parse_documents_arguments(acquisition_parse)
    acquisition_build = acquisition_subparsers.add_parser(
        "build-packets",
        help="Build final model packets from acquisition artifacts.",
    )
    _add_acquisition_build_packets_arguments(acquisition_build)

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
        "--results-store-root",
        help="Optional local root, file:// root, or s3:// root for safe outputs.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-id", default="offline:fixture")
    mock_output_group = parser.add_mutually_exclusive_group(required=True)
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


def _add_acquisition_parse_documents_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_acquisition_common_arguments(parser)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--parser-root", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--fixture-markdown-dir",
        type=Path,
        help="Directory with <source_document_id>.md files for fixture runs.",
    )
    parser.set_defaults(handler=_cmd_acquisition_parse_documents)


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


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] == "freeze":
        from legalforecast.protocol.freeze import cli_freeze

        return cli_freeze(args[1:])
    if args and args[0] == "validate-preregistration":
        from legalforecast.protocol.preregistration import cli_validate_preregistration

        return cli_validate_preregistration(args[1:])

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
        query_terms=query_terms or mtd_discovery_search_terms(),
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
    mock_output = _mock_output_text(args)
    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=cast(str, args.manifest),
            case_id=cast(str, args.case_id),
            ablation=cast(str, args.ablation),
            output_dir=cast(Path, args.output_dir),
            mock_output=mock_output,
            packet_store_root=cast(str | None, args.packet_store_root),
            results_store_root=cast(str | None, args.results_store_root),
            solver_id=cast(str, args.solver_id),
            max_tool_calls=cast(int, args.max_tool_calls),
            use_docket_tool=not cast(bool, args.no_docket_tool),
            evaluation_timestamp=(
                _parse_datetime(timestamp_text) if timestamp_text is not None else None
            ),
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
        if fixture_path is None:
            raise CommandError(
                "acquisition download-free requires --fixture-documents in this "
                "alpha CLI path"
            )
        try:
            records = download_free_docket_documents(
                requests,
                output_root=document_root,
                source=_fixture_free_document_source(fixture_path),
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


def _cmd_acquisition_parse_documents(args: argparse.Namespace) -> int:
    output_root = _acquisition_output_root(args)
    requests_path = cast(Path, args.requests)
    manifest_path = _acquisition_path(
        args,
        "manifest_output",
        output_root / "mistral-markdown-conversions.jsonl",
    )
    request_records = _read_records(requests_path)
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
        _write_jsonl(manifest_path, [record.to_record() for record in records])
    _write_acquisition_completion(
        args,
        stage="parse-documents",
        input_paths=(requests_path,),
        output_paths=(manifest_path,),
        record_count=len(requests),
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
) -> None:
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
        paid_activity_executed=False,
        extra={"failure_reason": reason},
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
    )


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
    protocol_path = output_dir / "protocols" / "cycle_fixture_e2e.preregistration.yaml"
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
        },
        freeze_timestamp=datetime(2026, 5, 14, 12, 5, tzinfo=UTC),
        base_protocol_record=_fixture_base_protocol_record(),
        protocol_output_path=protocol_path,
        bundle_output_path=bundle_path,
    )
    _log_event("freeze", "artifact_written", bundle_path, len(bundle.artifacts))

    validation = validate_preregistration_record(
        load_preregistration(protocol_path),
        expected_hashes=bundle.frozen_artifact_hashes(),
        template_text=_fixture_preregistration_template_text(),
    )
    validation_path = output_dir / "preregistration-validation.json"
    _write_json(validation_path, validation.to_record())
    validation.raise_for_errors()
    _log_event("preregistration", "artifact_written", validation_path, 1)

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


def _fixture_base_protocol_record() -> JsonRecord:
    return {
        "cycle_id": "cycle_fixture_e2e",
        "claim_level": "official_descriptive",
        "public_registration": {
            "provider": "osf",
            "url": "https://osf.io/legalforecast-fixture/",
            "timestamp": "2026-05-14T12:00:00Z",
        },
        "freeze_timestamp": "",
        "anchors": {
            "model_release": "2026-05-14T09:00:00Z",
            "decision_window_start": "2026-05-14",
            "decision_window_end": "2026-06-14",
            "candidate_source_provider": "case.dev",
        },
        "eligibility_rules": ["post_release_decision", "outcome_leakage_exclusion"],
        "exclusion_rules": ["ambiguous_linkage", "missing_core_filing"],
        "contamination_filters": ["related_case_publicity"],
        "unitization_rules": ["frozen_stage_a_units"],
        "labeling_rules": ["first_written_disposition_lock"],
        "metrics": {"primary": "micro_brier"},
        "inference": {
            "method": "paired_clustered_bootstrap",
            "bootstrap_replicates": 30,
        },
        "model_registry": {
            "path": "",
            "sha256": "",
            "models": ["fixture:model-a", "fixture:model-b"],
        },
        "baselines": {
            "path": "",
            "sha256": "",
        },
        "frozen_artifacts": {
            "manifest_sha256": "",
            "units_sha256": "",
            "labels_sha256": "",
            "prompt_sha256": "",
            "scorer_sha256": "",
            "harness_sha256": "",
        },
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


def _fixture_preregistration_template_text() -> str:
    return """
Cycle ID
Public registration provider
Candidate manifest
Prediction units
Outcome labels
Model registry SHA-256
Case-mix diagnostics
"""


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
    if relative_path.startswith("protocols/"):
        return "preregistration"
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
        challenged_by_motion=_required_bool(record, "challenged_by_motion"),
        challenge_scope=ChallengeScope(_required_str(record, "challenge_scope")),
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
    mock_output_file = cast(Path | None, getattr(args, "mock_output_file", None))
    if mock_output_file is not None:
        return mock_output_file.read_text(encoding="utf-8")
    return cast(str, args.mock_output)


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
        output_dir / "protocols" / "cycle_fixture_e2e.preregistration.yaml",
        output_dir / "manifests" / "cycle_fixture_e2e.freeze.json",
        output_dir / "preregistration-validation.json",
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

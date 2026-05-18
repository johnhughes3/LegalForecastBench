from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from legalforecast.evals.accounting import (
    ModelRunAccountingRecord,
    OutputValidityStatus,
    accounting_records_from_harness_records,
    accounting_result_key,
)
from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    ModelScoreInput,
    paired_clustered_bootstrap,
)
from legalforecast.evals.inspect_task import (
    ConfiguredModelStubSolver,
    HarnessRequest,
    InspectTaskSample,
    SolverKind,
    SolverResponse,
    build_inspect_samples,
    run_inspect_fixture,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParserStatus,
    parse_model_output,
)
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.evals.scorers import ScoreSummary, ScoringCase, score_cases
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.reporting.leaderboard import (
    AccountingLeaderboardRow,
    BenchmarkLeaderboardReport,
    build_benchmark_leaderboard_report,
    summarize_accounting_leaderboard,
)
from legalforecast.testing import (
    BASE_RATE_PROBABILITY,
    REQUIRED_MOCK_UNIT_IDS,
    get_mock_model_output,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "integrated_pipeline"
EXPECTED_SNAPSHOT_PATH = FIXTURE_DIR / "expected_report_snapshot.json"
EVALUATION_TIMESTAMP = datetime(2026, 5, 14, 20, 0, tzinfo=UTC)

DECISION_SECRET = "GA7_SECRET_DECISION_TEXT: first disposition grants dismissal"
LABEL_SECRET = "GA7_SECRET_LABEL: locked fully_dismissed outcomes"


def test_integrated_fixture_pipeline_enforces_sandbox_and_reporting_outputs() -> None:
    artifacts = _build_integrated_fixture_artifacts()
    prompt_payloads = [json.loads(sample.prompt) for sample in artifacts.samples]

    assert artifacts.run_case_count == 2
    assert artifacts.run_solver_count == 3
    assert len(artifacts.harness_records) == 6
    assert {
        document["source_document_id"]
        for payload in prompt_payloads
        for document in payload["documents"]
    } == {"complaint", "mtd-memo"}
    assert all(sample.allowed_entry_numbers == (1, 34) for sample in artifacts.samples)

    _assert_no_secret_material([sample.prompt for sample in artifacts.samples])
    _assert_no_secret_material([sample.to_record() for sample in artifacts.samples])
    _assert_no_secret_material(artifacts.harness_records)

    denied_logs = [
        log
        for record in artifacts.harness_records
        for log in record["tool_call_logs"]
        if log["status"] == "denied"
    ]
    assert len(denied_logs) == 4
    assert {log["entry_number"] for log in denied_logs} == {50, 99}
    assert all(log["denial_reason"] == "entry_not_found" for log in denied_logs)

    statuses_by_model = _statuses_by_model(artifacts)
    assert statuses_by_model["calibrated"] == {ParserStatus.VALID}
    assert statuses_by_model["overconfident"] == {ParserStatus.VALID}
    assert statuses_by_model["refusal"] == {ParserStatus.REFUSAL}

    summary_by_model = {summary.model_id: summary for summary in artifacts.summaries}
    assert summary_by_model["calibrated"].micro_brier < (
        summary_by_model["overconfident"].micro_brier
    )
    assert summary_by_model["refusal"].invalid_output_rate == 1
    assert summary_by_model["refusal"].refusal_rate == 1
    assert summary_by_model["refusal"].defaulted_prediction_rate == 1
    assert {
        report.dimension.value
        for report in summary_by_model["calibrated"].dominance_sensitivity_reports
    } == {"case", "related_case_family", "mdl_family"}

    accounting_by_model = {
        row.model_id: row for row in artifacts.accounting_leaderboard_rows
    }
    assert accounting_by_model["calibrated"].cost_per_case > 0
    assert accounting_by_model["calibrated"].mean_tool_calls_per_case == 2
    assert accounting_by_model["overconfident"].mean_tool_calls_per_case == 4
    assert accounting_by_model["refusal"].invalid_output_rate == 1
    assert accounting_by_model["refusal"].refusal_rate == 1
    assert any(record.denied_tool_call_count == 2 for record in artifacts.accounting)

    report_record = artifacts.report.to_record()
    assert [row["model_id"] for row in report_record["rows"]] == [
        "calibrated",
        "refusal",
        "overconfident",
    ]
    assert len(report_record["pairwise_deltas"]) == 3
    assert report_record["calibration_plot_svg"].startswith("<svg")
    assert {point["model_id"] for point in report_record["pareto_accuracy_cost"]} == {
        "calibrated",
        "refusal",
    }

    assert json.loads(artifacts.report.to_json()) == report_record
    csv_rows = tuple(csv.DictReader(StringIO(artifacts.report.to_csv())))
    assert csv_rows[0]["model_id"] == "calibrated"
    assert "# GA7 Integrated Fixture Leaderboard" in artifacts.report.to_markdown()
    assert "<svg" in artifacts.report.to_html()
    _assert_no_secret_material(
        [
            artifacts.report.to_json(),
            artifacts.report.to_csv(),
            artifacts.report.to_markdown(),
            artifacts.report.to_html(),
        ]
    )

    expected_snapshot = json.loads(EXPECTED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert _report_snapshot(report_record) == expected_snapshot


@dataclass(frozen=True, slots=True)
class _IntegratedArtifacts:
    samples: tuple[InspectTaskSample, ...]
    harness_records: list[dict[str, Any]]
    parsed_outputs: dict[tuple[str, str], ParsedModelOutput]
    summaries: tuple[ScoreSummary, ...]
    accounting: tuple[ModelRunAccountingRecord, ...]
    accounting_leaderboard_rows: tuple[AccountingLeaderboardRow, ...]
    report: BenchmarkLeaderboardReport

    @property
    def run_case_count(self) -> int:
        return len({record["case_id"] for record in self.harness_records})

    @property
    def run_solver_count(self) -> int:
        return len({record["solver_id"] for record in self.harness_records})


@dataclass(frozen=True, slots=True)
class _LeakageProbeConfiguredSolver:
    registry_entry: ModelRegistryEntry
    raw_output: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float

    def __post_init__(self) -> None:
        if not self.registry_entry.network_disabled:
            raise ValueError("leakage probe fixtures require network_disabled=True")
        if not self.registry_entry.search_disabled:
            raise ValueError("leakage probe fixtures require search_disabled=True")

    @property
    def solver_id(self) -> str:
        return self.registry_entry.registry_key

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.CONFIGURED_MODEL_STUB

    def solve(self, request: HarnessRequest) -> SolverResponse:
        request.docket_tool.list_available_docket_entries()
        request.docket_tool.read_docket_entry(34)
        request.docket_tool.read_docket_entry(50)
        request.docket_tool.read_docket_entry(99)
        return SolverResponse(
            raw_output=self.raw_output,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            estimated_cost=self.estimated_cost,
            metadata=_registry_metadata(self.registry_entry, "leakage_probe_fixture"),
        )


def _build_integrated_fixture_artifacts() -> _IntegratedArtifacts:
    packets = (_packet(1), _packet(2))
    samples = build_inspect_samples(packets, max_tool_calls=6, run_label="full_packet")
    solvers = (
        _configured_solver("calibrated", "mock_calibrated_predictions"),
        _leakage_probe_solver("overconfident", "mock_overconfident_predictions"),
        _configured_solver("refusal", "mock_refusal_plain_text"),
    )
    run = run_inspect_fixture(samples, solvers)
    harness_records = run.to_records()
    parsed_outputs = _parse_harness_records(harness_records)
    summaries = _score_harness_outputs(harness_records, parsed_outputs)
    status_by_hash = {
        parsed.raw_output_sha256: _output_status(parsed)
        for parsed in parsed_outputs.values()
    }
    accounting_records = accounting_records_from_harness_records(
        harness_records,
        evaluation_timestamp=EVALUATION_TIMESTAMP,
        latency_ms_by_result_key={
            accounting_result_key(record): 100.0 + (index * 5)
            for index, record in enumerate(harness_records)
        },
        output_status_by_raw_hash=status_by_hash,
    )
    accounting_rows = summarize_accounting_leaderboard(
        tuple(record.to_record() for record in accounting_records)
    )
    inference = paired_clustered_bootstrap(
        tuple(
            ModelScoreInput(summary.model_id, summary.unit_scores)
            for summary in summaries
        ),
        config=BootstrapConfig(replicates=30, seed=20260514),
    )
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=accounting_rows,
        inference=inference,
        title="GA7 Integrated Fixture Leaderboard",
    )
    return _IntegratedArtifacts(
        samples=samples,
        harness_records=harness_records,
        parsed_outputs=parsed_outputs,
        summaries=summaries,
        accounting=accounting_records,
        accounting_leaderboard_rows=accounting_rows,
        report=report,
    )


def _parse_harness_records(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], ParsedModelOutput]:
    parsed: dict[tuple[str, str], ParsedModelOutput] = {}
    for record in records:
        parsed[(record["sample_id"], record["solver_id"])] = parse_model_output(
            record["raw_output"],
            required_unit_ids=tuple(record["required_unit_ids"]),
        )
    return parsed


def _score_harness_outputs(
    records: Sequence[Mapping[str, Any]],
    parsed_outputs: Mapping[tuple[str, str], ParsedModelOutput],
) -> tuple[ScoreSummary, ...]:
    cases_by_model: dict[str, list[ScoringCase]] = {}
    for record in records:
        model_id = _report_model_id(record)
        parsed = parsed_outputs[(record["sample_id"], record["solver_id"])]
        cases_by_model.setdefault(model_id, []).append(
            ScoringCase(
                case_id=record["case_id"],
                candidate_id=record["candidate_id"],
                model_id=model_id,
                parsed_output=parsed,
                outcome_labels=_labels_for_case(record["case_id"]),
                related_family_id="related-ga7-family",
                mdl_family_id="mdl-ga7-family",
            )
        )

    return tuple(
        score_cases(
            tuple(cases_by_model[model_id]),
            base_rate=BASE_RATE_PROBABILITY,
            case_unit_cap=2,
            family_unit_cap=3,
            dominance_threshold=0.49,
        )
        for model_id in sorted(cases_by_model)
    )


def _statuses_by_model(
    artifacts: _IntegratedArtifacts,
) -> dict[str, set[ParserStatus]]:
    statuses: dict[str, set[ParserStatus]] = {}
    for record in artifacts.harness_records:
        model_id = _report_model_id(record)
        parsed = artifacts.parsed_outputs[(record["sample_id"], record["solver_id"])]
        statuses.setdefault(model_id, set()).add(parsed.status)
    return statuses


def _output_status(parsed: ParsedModelOutput) -> OutputValidityStatus:
    first_issue = parsed.issues[0].code.value if parsed.issues else None
    return OutputValidityStatus(
        invalid_output=parsed.invalid_output,
        refusal=parsed.status is ParserStatus.REFUSAL,
        invalid_output_reason=first_issue if parsed.invalid_output else None,
    )


def _configured_solver(
    model_id: str,
    fixture_id: str,
) -> ConfiguredModelStubSolver:
    fixture = get_mock_model_output(fixture_id)
    return ConfiguredModelStubSolver(
        registry_entry=_registry_entry(model_id),
        stub_raw_output=fixture.raw_output,
        input_tokens=fixture.input_tokens,
        output_tokens=fixture.output_tokens,
        estimated_cost=fixture.estimated_cost,
    )


def _leakage_probe_solver(
    model_id: str,
    fixture_id: str,
) -> _LeakageProbeConfiguredSolver:
    fixture = get_mock_model_output(fixture_id)
    return _LeakageProbeConfiguredSolver(
        registry_entry=_registry_entry(model_id),
        raw_output=fixture.raw_output,
        input_tokens=fixture.input_tokens,
        output_tokens=fixture.output_tokens,
        estimated_cost=fixture.estimated_cost,
    )


def _registry_entry(model_id: str) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "fixture-provider",
            "model_id": model_id,
            "display_name": f"Fixture {model_id}",
            "model_version_or_snapshot": "2026-05-14",
            "release_timestamp": "2026-05-14T09:00:00Z",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-04-01",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "fixture-price-sheet-2026-05-14",
            "input_token_price": 0.25,
            "output_token_price": 1.0,
            "known_cutoff_publicity_caveats": [],
        }
    )


def _registry_metadata(
    entry: ModelRegistryEntry,
    solver_mode: str,
) -> dict[str, str]:
    return {
        "provider": entry.provider,
        "model_id": entry.model_id,
        "model_version_or_snapshot": entry.model_version_or_snapshot,
        "tool_policy": entry.tool_policy.value,
        "solver_mode": solver_mode,
    }


def _report_model_id(record: Mapping[str, Any]) -> str:
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        model_id = metadata.get("model_id")
        if isinstance(model_id, str) and model_id.strip():
            return model_id
    solver_id = record["solver_id"]
    if ":" in solver_id:
        return solver_id.split(":", maxsplit=1)[1]
    return solver_id


def _packet(case_number: int):
    case_id = f"case-ga7-{case_number}"
    docket_number = f"1:26-cv-{case_number:04d}"
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id=f"cand-ga7-{case_number}",
            case_id=case_id,
            court="S.D.N.Y.",
            docket_number=docket_number,
            generated_at=EVALUATION_TIMESTAMP,
            documents=(
                _document(
                    case_id,
                    docket_number,
                    "complaint",
                    DocumentRole.COMPLAINT,
                    1,
                ),
                _document(
                    case_id,
                    docket_number,
                    "mtd-memo",
                    DocumentRole.MTD_MEMORANDUM,
                    34,
                ),
                _document(
                    case_id,
                    docket_number,
                    "decision",
                    DocumentRole.DECISION,
                    50,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                    packet_section="post_decision",
                ),
                _document(
                    case_id,
                    docket_number,
                    "labels-jsonl",
                    DocumentRole.EXCLUSION_NOTE,
                    51,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                    packet_section="labels",
                ),
            ),
        ),
        prediction_units=_prediction_units(),
        texts=(
            PacketText(
                source_document_id="complaint",
                text=f"Complaint allegations for GA7 fixture case {case_number}.",
            ),
            PacketText(
                source_document_id="mtd-memo",
                text=f"Motion-to-dismiss briefing for GA7 fixture case {case_number}.",
            ),
            PacketText(
                source_document_id="decision",
                text=f"{DECISION_SECRET} case={case_number}",
            ),
            PacketText(
                source_document_id="labels-jsonl",
                text=f"{LABEL_SECRET} case={case_number}",
            ),
        ),
        metadata={"judge": "Judge Fixture", "nos_macro_category": "securities"},
        target_docket_entry_numbers=(34,),
        related_family_id="related-ga7-family",
    )


def _document(
    case_id: str,
    docket_number: str,
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
    packet_section: str = "filings",
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="fixture",
        source_case_id=case_id,
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number=docket_number,
        document_role=role,
        retrieved_at=EVALUATION_TIMESTAMP,
        source_url_or_reference=f"fixture://{case_id}/{document_id}",
        sha256=sha256_text(f"{case_id}:{document_id}"),
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
        packet_section=packet_section,
    )


def _prediction_units() -> tuple[PredictionUnit, ...]:
    unit_specs = (
        (REQUIRED_MOCK_UNIT_IDS[0], "I", "Section 10(b)", "Issuer"),
        (REQUIRED_MOCK_UNIT_IDS[1], "II", "Section 20(a)", "Officers"),
        (REQUIRED_MOCK_UNIT_IDS[2], "III", "Section 11", "Underwriters"),
    )
    return tuple(
        PredictionUnit(
            unit_id=unit_id,
            count=count,
            claim_name=claim_name,
            defendant_group=defendant_group,
            challenged_by_motion=True,
            challenge_scope=ChallengeScope.ENTIRE_CLAIM,
            unit_confidence=0.96,
            source_citations=(
                SourceCitation(document_id="complaint", docket_entry_number=1, page=1),
            ),
        )
        for unit_id, count, claim_name, defendant_group in unit_specs
    )


def _labels_for_case(case_id: str) -> tuple[OutcomeLabel, ...]:
    outcomes = (True, False, False)
    return tuple(
        _label(case_id, unit_id, dismissed)
        for unit_id, dismissed in zip(REQUIRED_MOCK_UNIT_IDS, outcomes, strict=True)
    )


def _label(case_id: str, unit_id: str, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.97,
        supporting_citations=(
            OutcomeCitation(document_id=f"decision-{case_id}", page=1),
        ),
        first_written_disposition_id=f"decision-{case_id}",
        first_written_disposition_date="2026-05-20",
    )


def _assert_no_secret_material(value: object) -> None:
    serialized = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    assert DECISION_SECRET not in serialized
    assert LABEL_SECRET not in serialized
    assert "post_decision" not in serialized


def _report_snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": record["title"],
        "row_order": [row["model_id"] for row in record["rows"]],
        "rows": [
            {
                "model_id": row["model_id"],
                "rank": row["rank"],
                "rank_tier": row["rank_tier"],
                "micro_brier": _round_metric(row["micro_brier"]),
                "brier_skill_score": _round_metric(row["brier_skill_score"]),
                "capped_case_micro_brier": _round_metric(
                    row["capped_case_micro_brier"]
                ),
                "related_family_capped_micro_brier": _round_metric(
                    row["related_family_capped_micro_brier"]
                ),
                "mdl_family_capped_micro_brier": _round_metric(
                    row["mdl_family_capped_micro_brier"]
                ),
                "invalid_output_rate": _round_metric(row["invalid_output_rate"]),
                "refusal_rate": _round_metric(row["refusal_rate"]),
                "defaulted_prediction_rate": _round_metric(
                    row["defaulted_prediction_rate"]
                ),
                "cost_per_case": _round_metric(row["cost_per_case"]),
                "mean_tool_calls_per_case": _round_metric(
                    row["mean_tool_calls_per_case"]
                ),
            }
            for row in record["rows"]
        ],
        "pairwise_deltas": [
            {
                "model_a": delta["model_a"],
                "model_b": delta["model_b"],
                "observed_delta": _round_metric(delta["observed_delta"]),
                "ci_low": _round_metric(delta["ci_low"]),
                "ci_high": _round_metric(delta["ci_high"]),
                "probability_a_better": _round_metric(delta["probability_a_better"]),
            }
            for delta in record["pairwise_deltas"]
        ],
        "calibration_models": sorted(
            {table["model_id"] for table in record["calibration_tables"]}
        ),
        "pareto_accuracy_cost": [
            point["model_id"] for point in record["pareto_accuracy_cost"]
        ],
        "pareto_accuracy_tool_calls": [
            point["model_id"] for point in record["pareto_accuracy_tool_calls"]
        ],
    }


def _round_metric(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return round(float(value), 6)
    raise TypeError(f"expected numeric metric or None, got {value!r}")

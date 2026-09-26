"""Export native score artifacts through the public site contract.

The input producer is ``legalforecast score``, also used by fan-in-publish.
Only explicitly selected fields cross this boundary. Withdrawals rescore the
remaining units with the existing scorer, so charts and aggregates agree.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast import cli_support
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    load_model_registry_bytes,
    model_registry_sha256,
)
from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParsedPrediction,
    ParserStatus,
)
from legalforecast.evals.run_record_scoring import ReleaseOutcomeLabel
from legalforecast.evals.scorers import (
    ScoreSummary,
    ScoringCase,
    UnitScore,
    score_cases,
)
from legalforecast.publication.site_export_models import (
    SiteCalibrationBin,
    SiteCosts,
    SiteExport,
    SiteModelMetadata,
    SiteResult,
    SiteSource,
    SiteUnit,
)
from legalforecast.publication.withdrawal import load_withdrawal_ledger
from legalforecast.reporting.contamination_tiers import (
    ContaminationTier,
    classify_registry_entry,
)
from legalforecast.reporting.leaderboard import summarize_accounting_leaderboard
from legalforecast.reporting.score_summary_codec import score_summary_from_record


def _rescore(summary: ScoreSummary, excluded: set[str]) -> ScoreSummary | None:
    """Reconstruct the scorer's minimal inputs from its own public unit rows."""

    by_case: dict[str, list[UnitScore]] = defaultdict(list)
    seen: set[str] = set()
    for unit in summary.unit_scores:
        if unit.unit_id in seen or unit.model_id != summary.model_id:
            raise ValueError("score units must be unique and match their model")
        seen.add(unit.unit_id)
        if (
            unit.defaulted_prediction
            or unit.invalid_reason is not None
            or unit.parser_status
            not in {ParserStatus.VALID, ParserStatus.REPAIRED_VALID}
        ):
            raise ValueError("site export refuses failed or defaulted predictions")
        # Validate probabilities, binary outcomes, and finite metrics before use.
        SiteUnit.model_validate(
            {
                "case_id": unit.case_id,
                "unit_id": unit.unit_id,
                "probability_fully_dismissed": unit.probability_fully_dismissed,
                "outcome": unit.outcome,
                "brier": unit.brier,
            }
        )
        if not math.isclose(
            unit.brier,
            (unit.probability_fully_dismissed - unit.outcome) ** 2,
            abs_tol=1e-12,
        ):
            raise ValueError("unit Brier score differs from probability and outcome")
        by_case[unit.case_id].append(unit)
    if summary.unit_count != len(seen) or summary.case_count != len(by_case):
        raise ValueError("score counts differ from unit rows")
    cases: list[ScoringCase] = []
    for case_id, units in sorted(by_case.items()):
        if case_id in excluded:
            continue
        first = units[0]
        if any(unit.parser_status != first.parser_status for unit in units):
            raise ValueError("case units disagree on parser status")
        cases.append(
            ScoringCase(
                case_id=case_id,
                model_id=summary.model_id,
                candidate_id=first.candidate_id,
                related_family_id=first.related_family_id,
                mdl_family_id=first.mdl_family_id,
                parsed_output=ParsedModelOutput(
                    status=first.parser_status,
                    raw_output_sha256=first.raw_output_sha256,
                    required_unit_ids=tuple(unit.unit_id for unit in units),
                    predictions=tuple(
                        ParsedPrediction(
                            unit_id=unit.unit_id,
                            probability_fully_dismissed=unit.probability_fully_dismissed,
                            defaulted=unit.defaulted_prediction,
                            invalid_reason=unit.invalid_reason,
                        )
                        for unit in units
                    ),
                    issues=(),
                ),
                outcome_labels=tuple(
                    ReleaseOutcomeLabel(
                        unit.unit_id, unit.outcome, unit.label_confidence
                    )
                    for unit in units
                ),
            )
        )
    if not cases:
        return None
    return score_cases(
        tuple(cases),
        base_rate=summary.base_rate,
        ece_bin_count=len(summary.ece_bins),
        case_unit_cap=summary.case_unit_cap,
        family_unit_cap=summary.family_unit_cap,
        dominance_threshold=summary.dominance_threshold,
    )


def _metadata(
    model_id: str,
    registry: ModelRegistry | None,
    boundary: date | None,
) -> SiteModelMetadata:
    base_id, _, ablation = model_id.partition("::")
    entry: ModelRegistryEntry | None = None
    if registry is not None:
        matches = [
            candidate
            for candidate in registry.entries
            if base_id in (candidate.registry_key, candidate.model_id)
        ]
        if len(matches) != 1:
            raise ValueError(f"model {base_id!r} must match exactly one registry entry")
        entry = matches[0]
    eligibility = "unknown"
    reason = "missing_registry_or_decision_boundary"
    if entry is not None and boundary is not None:
        decision = classify_registry_entry(entry, contamination_boundary=boundary)
        eligibility = (
            "eligible" if decision.tier is ContaminationTier.RESISTANT else "qualified"
        )
        reason = decision.reason.value
    condition = "unknown"
    if entry is not None:
        if entry.jev_input_mode is not None:
            condition = (
                "summary" if "summar" in entry.jev_input_mode else "full_text_one_shot"
            )
        elif entry.tool_policy.value == "controlled_docket_tool_only":
            condition = "agentic"
    return SiteModelMetadata.model_validate(
        {
            "display_name": entry.display_name if entry else base_id,
            "provider": entry.provider if entry else None,
            "model_version": entry.model_version_or_snapshot if entry else None,
            "condition": condition,
            "ablation": ablation or None,
            "reasoning_effort": (
                entry.reasoning_effort.value
                if entry and entry.reasoning_effort
                else None
            ),
            "thinking_level": (
                entry.thinking_level.value if entry and entry.thinking_level else None
            ),
            "training_cutoff": entry.provider_training_cutoff if entry else None,
            "comparison_eligibility": eligibility,
            "eligibility_reason": reason,
        }
    )


def _costs(summary: ScoreSummary, accounting: Sequence[Mapping[str, Any]]) -> SiteCosts:
    cases = {unit.case_id for unit in summary.unit_scores}
    records = [
        record
        for record in accounting
        if record.get("model_id") == summary.model_id and record.get("case_id") in cases
    ]
    if not records:
        return SiteCosts(
            basis="unavailable",
            total_cost=None,
            cost_per_case=None,
            covered_case_count=0,
            missing_case_count=len(cases),
        )
    covered = {record["case_id"] for record in records}
    if len(covered) != len(records):
        raise ValueError(
            "accounting must contain exactly one record per model and case"
        )
    rows = summarize_accounting_leaderboard(records)
    if len(rows) != 1:
        raise ValueError("accounting mixes configurations for one score summary")
    row = rows[0]
    return SiteCosts(
        basis="estimated_accounting",
        total_cost=row.total_estimated_cost,
        cost_per_case=row.cost_per_case,
        covered_case_count=len(covered),
        missing_case_count=len(cases - covered),
    )


def build_site_export(
    score_payload: Mapping[str, Any],
    *,
    registry: ModelRegistry | None = None,
    contamination_boundary: date | None = None,
    excluded_case_ids: Sequence[str] = (),
    accounting: Sequence[Mapping[str, Any]] = (),
) -> SiteExport:
    """Validate native score rows and recompute the public retained cohort."""

    records = cli_support.required_record_sequence(score_payload, "summaries")
    if not records:
        raise ValueError("score artifact must contain at least one summary")
    excluded = set(excluded_case_ids)
    seen_models: set[str] = set()
    removed: set[str] = set()
    results: list[SiteResult] = []
    for record in records:
        source = score_summary_from_record(record)
        if source.model_id in seen_models:
            raise ValueError("score artifact contains duplicate model summaries")
        seen_models.add(source.model_id)
        validated = _rescore(source, set())
        if validated is None:
            raise ValueError("score summary has no units")
        for field in ("micro_brier", "macro_brier", "ece"):
            if not math.isclose(
                getattr(source, field), getattr(validated, field), abs_tol=1e-12
            ):
                raise ValueError(f"score summary {field} differs from unit rows")
        removed.update(
            unit.case_id for unit in source.unit_scores if unit.case_id in excluded
        )
        retained = _rescore(source, excluded) if excluded else validated
        if retained is None:
            continue
        results.append(
            SiteResult(
                model_id=source.model_id,
                metadata=_metadata(source.model_id, registry, contamination_boundary),
                case_count=retained.case_count,
                unit_count=retained.unit_count,
                micro_brier=retained.micro_brier,
                equal_case_brier=retained.macro_brier,
                calibration=[
                    SiteCalibrationBin(
                        lower=bin.lower,
                        upper=bin.upper,
                        unit_count=bin.unit_count,
                        mean_probability=bin.mean_probability,
                        observed_rate=bin.observed_rate,
                    )
                    for bin in retained.ece_bins
                ],
                costs=_costs(retained, accounting),
                units=[
                    SiteUnit.model_validate(
                        {
                            "case_id": unit.case_id,
                            "unit_id": unit.unit_id,
                            "probability_fully_dismissed": (
                                unit.probability_fully_dismissed
                            ),
                            "outcome": unit.outcome,
                            "brier": unit.brier,
                        }
                    )
                    for unit in retained.unit_scores
                ],
            )
        )
    identity = score_payload.get("identity", {})
    if not isinstance(identity, Mapping):
        raise ValueError("score identity must be an object")
    identity = cast(Mapping[str, Any], identity)
    return SiteExport(
        schema_version="legalforecast-site-export-v1",
        source=SiteSource.model_validate(
            {
                "run_identity_sha256": identity.get("run_identity_sha256"),
                "model_registry_sha256": identity.get("model_registry_sha256"),
                "generated_at": score_payload.get("generated_at"),
            }
        ),
        contamination_boundary=contamination_boundary,
        excluded_case_count=len(removed),
        results=sorted(results, key=lambda row: row.model_id),
    )


def export_site(
    *,
    scores_path: Path,
    output_path: Path,
    registry_path: Path | None = None,
    report_path: Path | None = None,
    contamination_boundary: date | None = None,
    withdrawal_ledger_path: Path | None = None,
    cycle_id: str | None = None,
    excluded_case_ids: Sequence[str] = (),
    accounting_path: Path | None = None,
) -> SiteExport:
    """Load local scored inputs and write a deterministic, whitelisted bundle."""

    payload = cli_support.read_json_object(scores_path)
    if report_path is not None:
        report = cli_support.read_json_object(report_path)
        if (
            not isinstance(payload.get("identity"), dict)
            or report.get("provenance") != payload["identity"]
        ):
            raise ValueError("report provenance does not match score artifact identity")
        classification = report.get("result_classification")
        if classification is not None:
            if not isinstance(classification, Mapping):
                raise ValueError("report result classification must be an object")
            anchor = cast(Mapping[str, Any], classification).get("corpus_anchor")
            if not isinstance(anchor, str):
                raise ValueError("report corpus_anchor must be an ISO decision date")
            report_boundary = date.fromisoformat(anchor)
            if (
                contamination_boundary is not None
                and contamination_boundary != report_boundary
            ):
                raise ValueError("explicit contamination boundary differs from report")
            contamination_boundary = report_boundary
    registry = None
    if registry_path is not None:
        raw = registry_path.read_bytes()
        identity = payload.get("identity")
        if not isinstance(identity, dict) or cast(Mapping[str, Any], identity).get(
            "model_registry_sha256"
        ) != model_registry_sha256(raw):
            raise ValueError("model registry does not match score artifact identity")
        registry = load_model_registry_bytes(raw)
    excluded = set(excluded_case_ids)
    if withdrawal_ledger_path is not None:
        if cycle_id is None:
            raise ValueError("--withdrawal-ledger requires --cycle-id")
        for entry in load_withdrawal_ledger(withdrawal_ledger_path).entries:
            if entry.cycle_id != cycle_id:
                continue
            if entry.case_id is None:
                raise ValueError(
                    "withdrawal without case_id requires a replacement score artifact"
                )
            excluded.add(entry.case_id)
    result = build_site_export(
        payload,
        registry=registry,
        contamination_boundary=contamination_boundary,
        excluded_case_ids=sorted(excluded),
        accounting=cli_support.read_records(accounting_path) if accounting_path else (),
    )
    cli_support.write_json(output_path, result.model_dump(mode="json"))
    return result

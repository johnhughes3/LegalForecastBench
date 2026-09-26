"""Public site exports exercise the real scoring producer and typed boundary."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    ToolPolicy,
    TrainingCutoffStatus,
)
from legalforecast.evals.output_parser import parse_model_output
from legalforecast.evals.run_record_scoring import ReleaseOutcomeLabel
from legalforecast.evals.scorers import ScoringCase, score_cases
from legalforecast.publication.site_export import build_site_export, export_site
from legalforecast.publication.site_export_models import SiteExport
from legalforecast.publication.withdrawal import (
    WithdrawalLedger,
    WithdrawalLedgerEntry,
    WithdrawalScope,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def synthetic_scores() -> dict[str, Any]:
    """Produce native scores with unequal units per synthetic case."""
    cases = []
    for case_id, units in (
        (
            "synthetic-case-a",
            (("synthetic-unit-a1", 0.8, 1), ("synthetic-unit-a2", 0.4, 0)),
        ),
        ("synthetic-case-b", (("synthetic-unit-b1", 0.7, 0),)),
    ):
        parsed = parse_model_output(
            json.dumps(
                {
                    "case_assessment": "Synthetic example.",
                    "predictions": [
                        {"unit_id": unit_id, "probability_fully_dismissed": probability}
                        for unit_id, probability, _ in units
                    ],
                }
            ),
            required_unit_ids=tuple(unit_id for unit_id, _, _ in units),
        )
        cases.append(
            ScoringCase(
                case_id=case_id,
                model_id="synthetic-model",
                parsed_output=parsed,
                outcome_labels=tuple(
                    ReleaseOutcomeLabel(unit_id, outcome)
                    for unit_id, _, outcome in units
                ),
            )
        )
    return {
        "generated_at": "2026-01-01T00:00:00Z",
        "summaries": [score_cases(tuple(cases), base_rate=0.5).to_record()],
    }


def test_export_matches_native_scores_and_generated_types_fixture() -> None:
    payload = synthetic_scores()
    payload["private_provider_receipts"] = {"token": "never publish"}
    payload["summaries"][0]["unit_scores"][0]["private_document"] = "never publish"
    result = build_site_export(payload)
    source = payload["summaries"][0]
    row = result.results[0]
    assert row.micro_brier == pytest.approx(source["micro_brier"])
    assert row.equal_case_brier == pytest.approx(source["macro_brier"])
    assert row.micro_brier != row.equal_case_brier
    assert row.case_count == 2 and row.unit_count == 3
    assert row.costs.total_cost is None and row.costs.missing_case_count == 2
    assert row.metadata.condition == "unknown"
    assert row.metadata.comparison_eligibility == "unknown"
    serialized = result.model_dump(mode="json")
    assert "never publish" not in json.dumps(serialized)
    assert serialized == json.loads(
        (ROOT / "site/src/data/fixtures/site-export.json").read_text()
    )
    assert SiteExport.model_validate(serialized) == result


def test_withdrawal_rescores_aggregates_calibration_and_removes_unit_ids() -> None:
    result = build_site_export(
        synthetic_scores(), excluded_case_ids=["synthetic-case-b"]
    )
    row = result.results[0]
    assert result.excluded_case_count == 1
    assert row.case_count == 1 and row.unit_count == 2
    assert row.micro_brier == pytest.approx(0.1)
    assert row.equal_case_brier == pytest.approx(0.1)
    assert sum(bin.unit_count for bin in row.calibration) == 2
    assert "synthetic-case-b" not in result.model_dump_json()
    assert "synthetic-unit-b1" not in result.model_dump_json()
    empty = build_site_export(
        synthetic_scores(), excluded_case_ids=["synthetic-case-a", "synthetic-case-b"]
    )
    assert empty.results == [] and empty.excluded_case_count == 2


@pytest.mark.parametrize(
    "mutation",
    ["bad_count", "duplicate_unit", "bad_aggregate", "infinity", "bad_outcome"],
)
def test_corrupt_scores_are_rejected(mutation: str) -> None:
    payload = synthetic_scores()
    summary = payload["summaries"][0]
    if mutation == "bad_count":
        summary["case_count"] += 1
    elif mutation == "duplicate_unit":
        summary["unit_scores"][1]["unit_id"] = summary["unit_scores"][0]["unit_id"]
    elif mutation == "bad_aggregate":
        summary["macro_brier"] = 0.9
    elif mutation == "infinity":
        summary["micro_brier"] = float("inf")
    else:
        summary["unit_scores"][0]["outcome"] = 2
    with pytest.raises(ValueError):
        build_site_export(payload)


def _registry() -> ModelRegistry:
    return ModelRegistry(
        (
            ModelRegistryEntry(
                provider="synthetic-provider",
                model_id="synthetic-model",
                display_name="Synthetic Model",
                model_version_or_snapshot="synthetic-v1",
                provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
                provider_training_cutoff=date(2025, 1, 1),
                max_output_tokens=1000,
                network_disabled=True,
                search_disabled=True,
                tool_policy=ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY,
                context_limit=10000,
                pricing_source="synthetic-prices",
                input_token_price=1,
                output_token_price=2,
            ),
        )
    )


def test_registry_condition_and_cutoff_policy_are_reused() -> None:
    row = build_site_export(
        synthetic_scores(),
        registry=_registry(),
        contamination_boundary=date(2025, 1, 2),
    ).results[0]
    assert row.metadata.condition == "agentic"
    assert row.metadata.comparison_eligibility == "eligible"
    row = build_site_export(
        synthetic_scores(),
        registry=_registry(),
        contamination_boundary=date(2025, 1, 1),
    ).results[0]
    assert row.metadata.comparison_eligibility == "qualified"
    assert row.metadata.eligibility_reason == "known_cutoff_does_not_predate_boundary"


def test_partial_accounting_keeps_coverage_and_estimate_label() -> None:
    record = {
        "solver_id": "synthetic-solver",
        "provider": "synthetic-provider",
        "model_id": "synthetic-model",
        "model_version_or_snapshot": "synthetic-v1",
        "case_id": "synthetic-case-a",
        "tool_call_count": 2,
        "latency_ms": 100,
        "estimated_cost": 0.25,
        "prediction_unit_count": 2,
        "invalid_output": False,
        "refusal": False,
        "content_filter": False,
    }
    row = build_site_export(synthetic_scores(), accounting=[record]).results[0]
    assert row.costs.total_cost == 0.25
    assert row.costs.basis == "estimated_accounting"
    assert row.costs.covered_case_count == 1 and row.costs.missing_case_count == 1
    assert row.costs.standard_rate_total_cost is None
    with pytest.raises(ValueError, match="exactly one record"):
        build_site_export(synthetic_scores(), accounting=[record, record])


def test_cli_and_schema_are_reproducible(tmp_path: Path) -> None:
    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps(synthetic_scores()))
    output = tmp_path / "public/site-export.json"
    assert (
        main(["site", "export", "--scores", str(scores), "--output", str(output)]) == 0
    )
    assert json.loads(output.read_text()) == build_site_export(
        synthetic_scores()
    ).model_dump(mode="json")
    schema = tmp_path / "schema.json"
    assert main(["site", "schema", "--output", str(schema)]) == 0
    assert json.loads(schema.read_text()) == json.loads(
        (ROOT / "docs/schemas/site-export-v1.schema.json").read_text()
    )
    assert "schema_version" in json.loads(schema.read_text())["required"]
    bad = copy.deepcopy(json.loads(output.read_text()))
    bad["private_raw_output"] = "no"
    with pytest.raises(ValidationError):
        SiteExport.model_validate(bad)


def test_report_identity_boundary_and_withdrawal_ledger(tmp_path: Path) -> None:
    payload = synthetic_scores()
    payload["identity"] = {
        "run_identity_sha256": "a" * 64,
        "model_registry_sha256": "b" * 64,
    }
    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps(payload))
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "provenance": payload["identity"],
                "result_classification": {"corpus_anchor": "2025-01-02"},
            }
        )
    )
    ledger = tmp_path / "withdrawals.jsonl"
    WithdrawalLedger(
        (
            WithdrawalLedgerEntry(
                withdrawal_id="synthetic-withdrawal",
                cycle_id="synthetic-cycle",
                scope=WithdrawalScope.CASE,
                reason="correction",
                public_reason="correction",
                effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                case_id="synthetic-case-b",
            ),
        )
    ).write_jsonl(ledger)
    result = export_site(
        scores_path=scores,
        report_path=report,
        output_path=tmp_path / "site.json",
        withdrawal_ledger_path=ledger,
        cycle_id="synthetic-cycle",
    )
    assert result.contamination_boundary == date(2025, 1, 2)
    assert result.results[0].case_count == 1
    assert result.source.run_identity_sha256 == "a" * 64
    with pytest.raises(ValueError, match="differs from report"):
        export_site(
            scores_path=scores,
            report_path=report,
            output_path=tmp_path / "site.json",
            contamination_boundary=date(2025, 1, 3),
        )
    report.write_text(json.dumps({"provenance": {"run_identity_sha256": "wrong"}}))
    with pytest.raises(ValueError, match="provenance"):
        export_site(
            scores_path=scores, report_path=report, output_path=tmp_path / "site.json"
        )


def test_defaulted_prediction_cannot_appear_as_clean_result() -> None:
    payload = synthetic_scores()
    unit = payload["summaries"][0]["unit_scores"][0]
    unit["defaulted_prediction"] = True
    unit["invalid_reason"] = "missing_required_unit"
    unit["parser_status"] = "missing_unit"
    with pytest.raises(ValueError, match="failed or defaulted"):
        build_site_export(payload)


def test_file_export_binds_registry_and_refuses_unmapped_withdrawals(
    tmp_path: Path,
) -> None:
    from legalforecast.evals.model_registry import model_registry_sha256

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(_registry().to_records()))
    payload = synthetic_scores()
    payload["identity"] = {
        "model_registry_sha256": model_registry_sha256(registry_path.read_bytes())
    }
    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps(payload))
    output = tmp_path / "site.json"
    result = export_site(
        scores_path=scores, registry_path=registry_path, output_path=output
    )
    assert result.results[0].metadata.provider == "synthetic-provider"
    registry_path.write_text(registry_path.read_text() + "\n")
    with pytest.raises(ValueError, match="registry does not match"):
        export_site(scores_path=scores, registry_path=registry_path, output_path=output)
    ledger = tmp_path / "withdrawals.jsonl"
    WithdrawalLedger(
        (
            WithdrawalLedgerEntry(
                withdrawal_id="synthetic-document-withdrawal",
                cycle_id="synthetic-cycle",
                scope=WithdrawalScope.DOCUMENT,
                source_document_ids=("synthetic-document",),
                reason="correction",
                public_reason="correction",
                effective_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )
    ).write_jsonl(ledger)
    with pytest.raises(ValueError, match="replacement score artifact"):
        export_site(
            scores_path=scores,
            output_path=output,
            withdrawal_ledger_path=ledger,
            cycle_id="synthetic-cycle",
        )

"""Successful receipt charges remain distinct from reproducible estimates."""

import copy
from dataclasses import replace

import pytest
from legalforecast.evals.model_registry import ModelRegistry
from legalforecast.publication.receipt_accounting import build_public_accounting
from legalforecast.publication.site_export import build_site_export

from test_site_export import _registry, synthetic_scores


def receipt() -> dict:
    return {
        "model_key": "synthetic-provider:synthetic-model",
        "case_id": "synthetic-case-a",
        "run_identity_sha256": "run-a",
        "raw_output": "private text must not be exported",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "estimated_cost_microusd": 250000,
        },
        "cost_evidence": {
            "basis": "provider_reported",
            "method": "gateway_reported_charge",
            "charged_cost_microusd": 250000,
            "rate_provenance": "recorded provider charge",
            "response_usage_details": [
                {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_tokens": 40,
                    "reasoning_tokens": 10,
                }
            ],
        },
    }


def registry() -> ModelRegistry:
    entry = _registry().entries[0]
    return ModelRegistry(
        entries=(
            replace(
                entry,
                provider="synthetic-provider",
                model_id="synthetic-model",
                input_token_price=2,
                output_token_price=10,
                cache_read_token_price=0.2,
                pricing_source="Standard published rates",
            ),
        )
    )


def test_reported_charge_is_preserved_and_repricing_is_separate() -> None:
    records = build_public_accounting([receipt()], registry())
    assert records[0]["estimated_cost"] == 0.25
    assert records[0]["cost_basis"] == "provider_reported"
    # Missing write dimension: conservative uncached pricing; reasoning not added.
    assert records[0]["standard_rate_cost"] == pytest.approx(0.0004)
    assert records[0]["missing_cache_write_response_count"] == 1
    assert "raw_output" not in str(records)
    records[0]["model_id"] = "synthetic-model"
    costs = build_site_export(synthetic_scores(), accounting=records).results[0].costs
    assert costs.basis == "provider_reported"
    assert costs.missing_case_count == 1
    assert costs.standard_rate_status == "partial"
    assert costs.standard_rate_covered_case_count == 1
    assert costs.standard_rate_total_cost == pytest.approx(0.0004)


def test_missing_historical_usage_preserves_cost_and_missing_repricing() -> None:
    record = receipt()
    record.pop("cost_evidence")
    output = build_public_accounting([record], registry())[0]
    assert output["estimated_cost"] == 0.25
    assert output["cost_basis"] == "estimated_from_pricing_snapshot"
    assert output["standard_rate_cost"] is None
    assert output["missing_response_usage_case_count"] == 1
    record["usage"].pop("estimated_cost_microusd")
    assert build_public_accounting([record], registry()) == []


def test_join_refuses_duplicates_wrong_models_and_inconsistent_amounts() -> None:
    record = receipt()
    with pytest.raises(ValueError, match="one successful receipt"):
        build_public_accounting([record, record], registry())
    with pytest.raises(ValueError, match="expected model"):
        build_public_accounting([record], registry(), expected_model_key="other")
    changed = copy.deepcopy(record)
    changed["case_id"] = "synthetic-case-b"
    changed["run_identity_sha256"] = "run-b"
    with pytest.raises(ValueError, match="run identities"):
        build_public_accounting([record, changed], registry())
    record["cost_evidence"]["charged_cost_microusd"] = 1
    with pytest.raises(ValueError, match="amounts differ"):
        build_public_accounting([record], registry())


def test_flex_reprices_only_from_explicit_frozen_basis() -> None:
    entry = replace(registry().entries[0], pricing_source="Flex is 50% of Standard")
    output = build_public_accounting([receipt()], ModelRegistry(entries=(entry,)))[0]
    assert output["standard_rate_cost"] == pytest.approx(0.0008)
    entry = replace(entry, pricing_source="Unknown rate basis")
    assert (
        build_public_accounting([receipt()], ModelRegistry(entries=(entry,)))[0][
            "standard_rate_cost"
        ]
        is None
    )


def test_module_cli_produces_accounting_consumable_by_export(tmp_path) -> None:
    import json
    import subprocess
    import sys

    from legalforecast.cli_support import read_records

    receipts = tmp_path / "receipts.jsonl"
    frozen = tmp_path / "registry.json"
    output = tmp_path / "accounting.jsonl"
    receipts.write_text(json.dumps(receipt()) + "\n")
    frozen.write_text(json.dumps(registry().to_records()))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "legalforecast.publication.receipt_accounting",
            "--receipts",
            str(receipts),
            "--registry",
            str(frozen),
            "--model-key",
            "synthetic-provider:synthetic-model",
            "--output",
            str(output),
        ],
        check=True,
    )
    assert read_records(output) == build_public_accounting([receipt()], registry())
    before = output.read_bytes()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "legalforecast.publication.receipt_accounting",
            "--receipts",
            str(receipts),
            "--registry",
            str(frozen),
            "--output",
            str(output),
        ],
        check=True,
    )
    assert output.read_bytes() == before


def test_report_command_accepts_receipt_costs_without_inventing_efficiency(
    tmp_path,
) -> None:
    import json
    import subprocess
    import sys
    from pathlib import Path

    scores = tmp_path / "scores.json"
    records = tmp_path / "accounting.jsonl"
    report_dir = tmp_path / "report"
    scores.write_text(json.dumps(synthetic_scores()))
    accounting = build_public_accounting([receipt()], registry())
    accounting[0]["model_id"] = "synthetic-model"
    records.write_text("".join(json.dumps(row) + "\n" for row in accounting))
    subprocess.run(
        [
            str(Path(sys.executable).with_name("legalforecast")),
            "report",
            "--scores",
            str(scores),
            "--accounting",
            str(records),
            "--output-dir",
            str(report_dir),
            "--bootstrap-replicates",
            "10",
        ],
        check=True,
    )
    payload = json.loads((report_dir / "leaderboard.json").read_text())
    cost = payload["cost_accounting"][0]
    assert cost["basis"] == "provider_reported"
    assert cost["total_cost"] == 0.25
    assert cost["standard_rate_total_cost"] == pytest.approx(0.0004)
    assert cost["standard_rate_status"] == "partial"
    model = next(row for row in payload["rows"] if row["row_type"] == "model")
    assert model["mean_latency_ms"] is None
    assert model["mean_tool_calls_per_case"] is None
    assert model["cost_per_case"] is None
    assert "total_estimated_cost" not in cost
    assert "Missing latency" in (report_dir / "leaderboard.md").read_text()
    assert "provider_reported" in (report_dir / "leaderboard.html").read_text()

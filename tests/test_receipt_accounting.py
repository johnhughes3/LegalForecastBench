"""Successful receipt charges remain distinct from reproducible estimates."""

import copy
from dataclasses import replace

import pytest
from legalforecast.evals.model_registry import ModelRegistry, ToolPolicy
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model_key", "other:model", "outside registry"),
        ("cost_evidence", [], "cost evidence must be an object"),
        ("cost_evidence.basis", "invoice_paid", "unsupported receipt cost basis"),
        ("cost_evidence.response_usage_details", {}, "must be a list"),
        ("cost_evidence.response_usage_details", ["invalid"], "must be an object"),
        ("usage.estimated_cost_microusd", -1, "nonnegative integer"),
        ("usage.input_tokens", 99, "differs from receipt total"),
    ],
)
def test_invalid_receipt_evidence_cannot_become_public_cost(
    field, value, message
) -> None:
    record = receipt()
    if "." in field:
        parent, key = field.split(".", 1)
        record[parent][key] = value
    else:
        record[field] = value
    with pytest.raises(ValueError, match=message):
        build_public_accounting([record], registry())


def test_reported_charge_requires_explicit_amount_and_missing_usage_is_not_free() -> (
    None
):
    record = receipt()
    record["cost_evidence"].pop("charged_cost_microusd")
    with pytest.raises(ValueError, match="recorded charged amount"):
        build_public_accounting([record], registry())
    record.pop("usage")
    assert build_public_accounting([record], registry()) == []


def test_native_anthropic_cache_repricing_uses_reported_buckets() -> None:
    entry = replace(
        registry().entries[0],
        provider="anthropic",
        model_id="claude-opus-5-5",
        input_token_price=4,
        output_token_price=20,
        cache_read_token_price=None,
        cache_write_token_price=None,
    )
    record = receipt()
    record["model_key"] = entry.registry_key
    record["cost_evidence"]["method"] = "anthropic_cache_aware_usage_reconstruction"
    row = record["cost_evidence"]["response_usage_details"][0]
    row["cache_write_tokens"] = 10
    output = build_public_accounting([record], ModelRegistry(entries=(entry,)))[0]
    # 50 uncached*4 +40 read*.20 +10 write*5 +20 output*20, per million.
    assert output["standard_rate_cost"] == pytest.approx(0.000658)
    assert output["estimated_cost"] == 0.25
    assert output["missing_cache_rate_response_count"] == 0
    row.pop("cache_read_tokens")
    assert (
        build_public_accounting([record], ModelRegistry(entries=(entry,)))[0][
            "standard_rate_cost"
        ]
        is None
    )


def test_cost_only_report_renders_mixed_evidence_and_unknown_repricing(
    tmp_path,
) -> None:
    import argparse
    import json

    from legalforecast.cli_commands import report

    scores = tmp_path / "scores.json"
    records = tmp_path / "accounting.jsonl"
    directory = tmp_path / "report"
    scores.write_text(json.dumps(synthetic_scores()))
    accounting = build_public_accounting([receipt()], registry())
    accounting[0]["model_id"] = "synthetic-model"
    accounting[0]["standard_rate_cost"] = None
    second = {
        **accounting[0],
        "case_id": "synthetic-case-b",
        "cost_basis": "estimated_from_pricing_snapshot",
        "estimated_cost": 0.5,
    }
    records.write_text(
        "".join(json.dumps(row) + "\n" for row in [accounting[0], second])
    )
    parser = argparse.ArgumentParser()
    report.register(parser.add_subparsers())
    args = parser.parse_args(
        [
            "report",
            "--scores",
            str(scores),
            "--accounting",
            str(records),
            "--output-dir",
            str(directory),
            "--bootstrap-replicates",
            "10",
        ]
    )
    assert report.run(args) == 0
    payload = json.loads((directory / "leaderboard.json").read_text())
    assert payload["cost_accounting"][0]["basis"] == "mixed_receipt_evidence"
    assert payload["cost_accounting"][0]["total_cost"] == 0.75
    assert payload["cost_accounting"][0]["standard_rate_total_cost"] is None
    assert payload["cost_accounting"][0]["covered_case_count"] == 2
    assert payload["cost_accounting"][0]["missing_case_count"] == 0
    assert "mixed_receipt_evidence" in (directory / "leaderboard.html").read_text()
    assert "unavailable" in (directory / "leaderboard.md").read_text()
    assert (
        next(row for row in payload["rows"] if row["row_type"] == "model")[
            "mean_latency_ms"
        ]
        is None
    )
    # A cost-only input must never silently accept a legacy efficiency record.
    second.pop("cost_scope")
    records.write_text(
        "".join(json.dumps(row) + "\n" for row in [accounting[0], second])
    )
    with pytest.raises(ValueError, match="cannot mix receipt cost accounting"):
        report.run(args)


def test_accounting_module_cli_preserves_missing_usage_in_jsonl(
    tmp_path, monkeypatch
) -> None:
    import json
    import sys

    from legalforecast.cli_support import read_records
    from legalforecast.publication.receipt_accounting import main

    record = receipt()
    record["cost_evidence"].pop("response_usage_details")
    receipts = tmp_path / "receipts.jsonl"
    frozen = tmp_path / "registry.json"
    output = tmp_path / "nested/accounting.jsonl"
    receipts.write_text(json.dumps(record) + "\n")
    frozen.write_text(json.dumps(registry().to_records()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "receipt_accounting",
            "--receipts",
            str(receipts),
            "--registry",
            str(frozen),
            "--output",
            str(output),
        ],
    )
    main()
    saved = read_records(output)[0]
    assert saved["standard_rate_cost"] is None
    assert saved["estimated_cost"] == 0.25
    assert saved["missing_response_usage_case_count"] == 1
    assert "raw_output" not in saved


@pytest.mark.parametrize("value", [-0.5, float("inf"), float("nan"), True])
def test_public_cost_export_refuses_invalid_accounting_amounts(value) -> None:
    accounting = build_public_accounting([receipt()], registry())
    accounting[0]["model_id"] = "synthetic-model"
    for field in ("estimated_cost", "standard_rate_cost"):
        corrupted = copy.deepcopy(accounting)
        corrupted[0][field] = value
        with pytest.raises(ValueError, match="finite and nonnegative"):
            build_site_export(synthetic_scores(), accounting=corrupted)


def test_withdrawn_case_costs_do_not_enter_retained_workload_or_repricing() -> None:
    accounting = build_public_accounting([receipt()], registry())
    accounting[0]["model_id"] = "synthetic-model"
    second = {
        **accounting[0],
        "case_id": "synthetic-case-b",
        "estimated_cost": 1.5,
        "standard_rate_cost": 2.0,
    }
    output = build_site_export(
        synthetic_scores(),
        accounting=[accounting[0], second],
        excluded_case_ids=["synthetic-case-b"],
    )
    costs = output.results[0].costs
    assert costs.total_cost == 0.25
    assert costs.covered_case_count == 1
    assert costs.missing_case_count == 0
    assert costs.standard_rate_status == "complete"
    assert costs.standard_rate_total_cost == pytest.approx(0.0004)
    assert costs.response_count == 1
    assert "synthetic-case-b" not in output.model_dump_json()


def jev_receipt_and_registry():
    entry = replace(
        registry().entries[0],
        provider="vercel_ai_gateway",
        model_id="typesafe-ai/jev",
        jev_input_mode="grok_summaries",
        tool_policy=ToolPolicy.NO_TOOLS,
        jev_summaries_sha256="a" * 64,
        input_token_price=0.042,
        output_token_price=0,
        pricing_source="https://vercel.com/ai-gateway/models/jev",
    )
    record = receipt()
    record.pop("cost_evidence")
    record["model_key"] = entry.registry_key
    record["jev_request_count"] = 1
    record["usage"] = {
        "input_tokens": 6692,
        "output_tokens": 169,
        "estimated_cost_microusd": 282,
    }
    record["jev_provider_metadata"] = {
        "gateway": {"gatewayCost": "0.000281064", "cost": "0.000281064"}
    }
    return record, ModelRegistry(entries=(entry,))


def test_jev_exact_gateway_charge_and_one_shot_repricing():
    record, frozen = jev_receipt_and_registry()
    output = build_public_accounting([record], frozen)[0]
    assert output["estimated_cost"] == 0.000281064
    assert output["cost_basis"] == "provider_reported"
    assert output["cost_method"] == "gateway_reported_charge"
    assert output["standard_rate_cost"] == pytest.approx(0.000281064)
    assert output["response_count"] == 1
    assert output["missing_response_usage_case_count"] == 0
    assert output["missing_cache_read_response_count"] == 1
    record["jev_provider_metadata"]["gateway"]["gatewayCost"] = "0.0003"
    output = build_public_accounting([record], frozen)[0]
    assert output["estimated_cost"] == 0.0003
    assert output["standard_rate_cost"] == pytest.approx(0.000281064)


@pytest.mark.parametrize(
    "amount", [None, True, "bad", "NaN", "Infinity", "-0.01", "1e10000"]
)
def test_jev_malformed_present_gateway_charge_refuses_fallback(amount):
    record, frozen = jev_receipt_and_registry()
    record["jev_provider_metadata"]["gateway"]["gatewayCost"] = amount
    with pytest.raises(ValueError, match="Gateway metadata cost"):
        build_public_accounting([record], frozen)


def test_jev_missing_charge_falls_back_without_losing_usage_coverage():
    record, frozen = jev_receipt_and_registry()
    record["jev_provider_metadata"] = {}
    output = build_public_accounting([record], frozen)[0]
    assert output["estimated_cost"] == 0.000282
    assert output["cost_basis"] == "estimated_from_pricing_snapshot"
    assert output["standard_rate_cost"] == pytest.approx(0.000281064)
    record["jev_request_count"] = 2
    output = build_public_accounting([record], frozen)[0]
    assert output["response_count"] == 0
    assert output["standard_rate_cost"] is None


def test_jev_older_cost_field_is_supported_without_rounding():
    record, frozen = jev_receipt_and_registry()
    record["jev_provider_metadata"]["gateway"].pop("gatewayCost")
    assert build_public_accounting([record], frozen)[0]["estimated_cost"] == 0.000281064

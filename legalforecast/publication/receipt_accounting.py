"""Sanitized case accounting from validated forecast receipts and frozen prices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    load_model_registry,
)
from legalforecast.runner.anthropic_cache import anthropic_cache_cost
from legalforecast.runner.gateway import gateway_total_cost_usd
from legalforecast.runner.managed_cost import (
    ManagedResponseUsage,
    managed_usage_cost,
)

COST_SCOPE = "successful_case_workload"
COST_CAVEAT = (
    "Successful case receipts only; excludes failed attempts, retries, unresolved "
    "charges and summary preparation. These are workload charges or usage estimates, "
    "not provider invoice totals. Standard repricing uses ordinary input estimates "
    "when cache dimensions or frozen cache rates are missing."
)


def _count(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _standard_cost(
    entry: ModelRegistryEntry, details: Sequence[ManagedResponseUsage], method: str
) -> float | None:
    """Reprice only when frozen evidence identifies the rate basis."""
    if not details:
        return None  # Aggregates cannot reproduce per-response context surcharges.
    if (
        entry.provider == "anthropic"
        and method == "anthropic_cache_aware_usage_reconstruction"
    ):
        if any(
            row.cache_read_tokens is None or row.cache_write_tokens is None
            for row in details
        ):
            return None
        return anthropic_cache_cost(
            entry,
            [(row.input_tokens, row.output_tokens) for row in details],
            [
                (row.cache_read_tokens or 0, row.cache_write_tokens or 0)
                for row in details
            ],
        )[0]
    if entry.jev_input_mode is not None and entry.provider in {
        "vercel_ai_gateway",
        "typesafe",
    }:
        # Native Jev is a single request priced by the frozen input/output rates.
        return managed_usage_cost(entry, details)
    source = entry.pricing_source.lower()
    multiplier: float | None = None
    if "flex is 50% of standard" in source or (
        "flex rates" in source and "half" in source
    ):
        multiplier = 2.0
    elif "standard" in source and "flex is 50%" not in source:
        multiplier = 1.0
    if multiplier is None:
        return None
    return multiplier * managed_usage_cost(entry, details)


def build_public_accounting(
    receipts: Sequence[Mapping[str, Any]],
    registry: ModelRegistry,
    *,
    expected_model_key: str | None = None,
) -> list[dict[str, object]]:
    """Project validated successful receipts without prompts, predictions or secrets.

    Call after the scoring path's receipt identity/coverage validation. Duplicate
    cases and mixed run identities are refused to prevent joining another run's
    charges or double-counting case calls. Missing cost evidence stays missing.
    """
    entries = {entry.registry_key: entry for entry in registry.entries}
    seen: set[tuple[str, str]] = set()
    identities: set[object] = set()
    records: list[dict[str, object]] = []
    for receipt in receipts:
        model = receipt.get("model_key", receipt.get("model_id"))
        case = receipt.get("case_id")
        if (
            not isinstance(model, str)
            or model not in entries
            or not isinstance(case, str)
            or not case
        ):
            raise ValueError(
                "receipt model/case identity is missing or outside registry"
            )
        if expected_model_key is not None and model != expected_model_key:
            raise ValueError("receipt differs from expected model key")
        if (model, case) in seen:
            raise ValueError(
                "accounting requires one successful receipt per model/case"
            )
        seen.add((model, case))
        identities.add(receipt.get("run_identity_sha256"))
        if len(identities) > 1:
            raise ValueError("accounting mixes forecast run identities")
        usage = receipt.get("usage")
        if not isinstance(usage, Mapping):
            continue
        usage = cast(Mapping[str, Any], usage)
        amount = usage.get("estimated_cost_microusd")
        if amount is None:
            continue
        amount = _count(amount, "estimated_cost_microusd")
        evidence = receipt.get("cost_evidence", {})
        if not isinstance(evidence, Mapping):
            raise ValueError("cost evidence must be an object")
        evidence = cast(Mapping[str, Any], evidence)
        basis = evidence.get("basis", "estimated_from_pricing_snapshot")
        if basis not in {"provider_reported", "estimated_from_pricing_snapshot"}:
            raise ValueError("unsupported receipt cost basis")
        method = str(evidence.get("method", "legacy_uncached_usage_estimate"))
        if basis == "provider_reported" and "charged_cost_microusd" not in evidence:
            raise ValueError(
                "provider-reported cost requires a recorded charged amount"
            )
        evidence_amount = evidence.get(
            "charged_cost_microusd"
            if basis == "provider_reported"
            else "estimated_cost_microusd",
            amount,
        )
        if _count(evidence_amount, "cost evidence amount") != amount:
            raise ValueError("receipt usage and cost evidence amounts differ")
        raw_details = evidence.get("response_usage_details", [])
        if not isinstance(raw_details, list):
            raise ValueError("response usage details must be a list")
        details: list[ManagedResponseUsage] = []
        for raw in cast(list[object], raw_details):
            if not isinstance(raw, Mapping):
                raise ValueError("response usage detail must be an object")
            raw = cast(Mapping[str, Any], raw)
            optional = {
                key: _count(raw[key], key) if key in raw else None
                for key in (
                    "cache_read_tokens",
                    "cache_write_tokens",
                    "reasoning_tokens",
                )
            }
            details.append(
                ManagedResponseUsage(
                    input_tokens=_count(raw.get("input_tokens"), "input_tokens"),
                    output_tokens=_count(raw.get("output_tokens"), "output_tokens"),
                    **optional,
                )
            )
        for field in ("input_tokens", "output_tokens"):
            if details and sum(getattr(row, field) for row in details) != _count(
                usage.get(field), field
            ):
                raise ValueError(f"response usage {field} differs from receipt total")
        public_amount = amount / 1_000_000
        entry = entries[model]
        if entry.jev_input_mode is not None and entry.provider in {
            "vercel_ai_gateway",
            "typesafe",
        }:
            # Only the native one-shot contract identifies aggregate usage as one
            # response. Do not invent per-response details for agentic receipts.
            if (
                not details
                and type(receipt.get("jev_request_count")) is int
                and receipt.get("jev_request_count") == 1
            ):
                details = [
                    ManagedResponseUsage(
                        input_tokens=_count(usage.get("input_tokens"), "input_tokens"),
                        output_tokens=_count(
                            usage.get("output_tokens"), "output_tokens"
                        ),
                    )
                ]
            metadata = receipt.get("jev_provider_metadata", {})
            if not isinstance(metadata, Mapping):
                raise ValueError("Jev provider metadata must be an object")
            metadata = cast(Mapping[str, object], metadata)
            gateway = metadata.get("gateway", {})
            if not isinstance(gateway, Mapping):
                raise ValueError("Jev Gateway metadata must be an object")
            gateway = cast(Mapping[str, object], gateway)
            # gatewayCost includes surcharges; cost is the older transport field.
            # A malformed present preferred amount must never fall through.
            field = next(
                (key for key in ("gatewayCost", "cost") if key in gateway), None
            )
            if field is not None:
                public_amount = gateway_total_cost_usd([{"cost_usd": gateway[field]}])
                basis = "provider_reported"
                method = "gateway_reported_charge"
        records.append(
            {
                "model_id": model,
                "case_id": case,
                "estimated_cost": public_amount,
                "cost_basis": basis,
                "cost_method": method,
                "rate_provenance": str(
                    evidence.get("rate_provenance", entries[model].pricing_source)
                ),
                "standard_rate_cost": _standard_cost(entries[model], details, method),
                "response_count": len(details),
                "missing_cache_read_response_count": sum(
                    row.cache_read_tokens is None for row in details
                ),
                "missing_cache_write_response_count": sum(
                    row.cache_write_tokens is None for row in details
                ),
                "missing_cache_rate_response_count": sum(
                    bool(
                        (
                            (row.cache_read_tokens or 0) > 0
                            and entries[model].cache_read_token_price is None
                        )
                        or (
                            (row.cache_write_tokens or 0) > 0
                            and entries[model].cache_write_token_price is None
                        )
                    )
                    for row in details
                )
                if method != "anthropic_cache_aware_usage_reconstruction"
                else 0,
                "missing_response_usage_case_count": int(not details),
                "cost_scope": COST_SCOPE,
            }
        )
    return sorted(records, key=lambda row: (str(row["model_id"]), str(row["case_id"])))


def main() -> None:
    """Write reproducible accounting from the validated scoring records."""
    import argparse
    import json
    from pathlib import Path

    from legalforecast.cli_support import read_records

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--model-key")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    registry = load_model_registry(args.registry)
    records = build_public_accounting(
        read_records(args.receipts), registry, expected_model_key=args.model_key
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

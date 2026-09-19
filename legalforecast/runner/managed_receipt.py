"""Public receipt projection for managed runner cost evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from legalforecast.runner.ledger import RunValidationError


def add_managed_cost_evidence(
    receipt: dict[str, object], metadata: Mapping[str, str] | None
) -> None:
    """Carry managed usage dimensions and cost provenance into the receipt."""

    if metadata is None or "cost_basis" not in metadata:
        return
    required = ("cost_basis", "cost_method", "rate_provenance", "service_tier")
    if any(key not in metadata or not metadata[key] for key in required):
        raise RunValidationError("managed cost evidence metadata is incomplete")
    raw_details = metadata.get("response_usage_details")
    details: list[Mapping[str, object]] = []
    if raw_details is not None and raw_details != "not_reported":
        try:
            decoded: object = json.loads(raw_details)
        except json.JSONDecodeError as exc:
            raise RunValidationError(
                "managed response usage details are invalid JSON"
            ) from exc
        if not isinstance(decoded, list):
            raise RunValidationError("managed response usage details are invalid")
        for raw_row in cast(list[object], decoded):
            if not isinstance(raw_row, Mapping):
                raise RunValidationError("managed response usage detail is invalid")
            details.append(cast(Mapping[str, object], raw_row))
    evidence: dict[str, object] = {
        "basis": metadata["cost_basis"],
        "method": metadata["cost_method"],
        "rate_provenance": metadata["rate_provenance"],
        "service_tier": metadata["service_tier"],
    }
    amount_key = (
        "charged_cost_microusd"
        if metadata["cost_basis"] == "provider_reported"
        else "estimated_cost_microusd"
    )
    evidence[amount_key] = cast(dict[str, object], receipt["usage"])[
        "estimated_cost_microusd"
    ]
    if details:
        evidence["response_usage_details"] = [dict(row) for row in details]
        usage = cast(dict[str, object], receipt["usage"])
        for field_name in (
            "cache_read_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        ):
            values = [row.get(field_name) for row in details]
            # Missing historical dimensions remain absent.  A partial list
            # cannot be safely aggregated into a total.
            if all(type(value) is int and value >= 0 for value in values):
                usage[field_name] = sum(cast(int, value) for value in values)
    receipt["cost_evidence"] = evidence

"""Public, frontend-independent JSON contract for benchmark results."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Probability = Annotated[float, Field(ge=0, le=1)]
Nonnegative = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class PublicModel(BaseModel):
    """Reject accidental fields and non-finite numbers at the public boundary."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SiteUnit(PublicModel):
    """A public prediction unit, with no document content or execution details."""

    case_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    probability_fully_dismissed: Probability
    outcome: Literal[0, 1]
    brier: Probability


class SiteCalibrationBin(PublicModel):
    """Calibration values computed by the Python scorer."""

    lower: Probability
    upper: Probability
    unit_count: Count
    mean_probability: Probability | None
    observed_rate: Probability | None


class SiteCosts(PublicModel):
    """Cost availability; missing accounting is never interpreted as free usage."""

    currency: Literal["USD"] = "USD"
    basis: Literal["unavailable", "estimated_accounting"]
    total_cost: Nonnegative | None
    cost_per_case: Nonnegative | None
    covered_case_count: Count
    missing_case_count: Count
    standard_rate_total_cost: Nonnegative | None = None
    standard_rate_status: Literal["unavailable"] = "unavailable"


class SiteModelMetadata(PublicModel):
    """A whitelist of display and experimental settings from a frozen registry."""

    display_name: str = Field(min_length=1)
    provider: str | None
    model_version: str | None
    condition: Literal["agentic", "summary", "full_text_one_shot", "unknown"]
    ablation: str | None
    reasoning_effort: str | None
    thinking_level: str | None
    training_cutoff: date | None
    comparison_eligibility: Literal["eligible", "qualified", "unknown"]
    eligibility_reason: str


class SiteResult(PublicModel):
    """One model/condition row, including its public unit-level explorer data."""

    model_id: str = Field(min_length=1)
    metadata: SiteModelMetadata
    case_count: Count
    unit_count: Count
    micro_brier: Probability
    equal_case_brier: Probability
    calibration: list[SiteCalibrationBin]
    costs: SiteCosts
    units: list[SiteUnit]


class SiteSource(PublicModel):
    """Existing score provenance, without local paths or new identity machinery."""

    run_identity_sha256: str | None
    model_registry_sha256: str | None
    generated_at: datetime | None


class SiteExport(PublicModel):
    """Versioned site data generated only from scored, public benchmark outputs."""

    schema_version: Literal["legalforecast-site-export-v1"]
    source: SiteSource
    contamination_boundary: date | None
    excluded_case_count: Count
    results: list[SiteResult]

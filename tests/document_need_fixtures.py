"""CycleConfig fixtures for document-need tests.

Constructs D1 types in ``tests/`` only (the acquisition-config fence scans
``legalforecast/`` and ``scripts/``). Live Cycle 2 stays inert; these copies
set ``activated=True`` for estimator unit tests.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from legalforecast.config import (
    CYCLE_1_ID,
    CYCLE_2_ID,
    EvaluationRegistryPin,
    SelectorModel,
    SelectorModelPolicy,
    SpendCeiling,
    StratificationPolicy,
    load_cycle,
    usd,
)
from legalforecast.config.types import CycleConfig

ROOT = Path(__file__).resolve().parents[1]
CYCLE_1_REGISTRY = "model_registries/cycle-1-2026-06-30.json"

HAIKU = SelectorModel(
    provider="anthropic",
    model_id="claude-haiku-4-5-20251001",
    model_version_or_snapshot="claude-haiku-4-5-20251001",
)


def activated_haiku_config(
    *,
    spend: SpendCeiling | None = None,
    stratification: StratificationPolicy | None = None,
    selector_model_policy: SelectorModelPolicy | None = None,
    evaluation_registry: EvaluationRegistryPin | None = None,
) -> CycleConfig:
    """Activated Cycle 2 draft: cleared Haiku selector, Cycle 1 registry pin."""

    base = load_cycle(CYCLE_2_ID)
    return replace(
        base,
        activated=True,
        activation_blocker=None,
        evaluation_registry=evaluation_registry
        or EvaluationRegistryPin(path=CYCLE_1_REGISTRY),
        selector_model_policy=selector_model_policy
        or SelectorModelPolicy(primary=HAIKU, alternates=()),
        spend=spend
        if spend is not None
        else SpendCeiling(hard_cap_usd=usd("500.00"), max_per_case_usd=usd("500.00")),
        stratification=stratification
        if stratification is not None
        else base.stratification,
    )


def luna_on_cycle1_registry() -> CycleConfig:
    """Activated draft that keeps Cycle 2's Luna/Sonnet selectors on the Cycle 1 pin."""

    return replace(
        load_cycle(CYCLE_2_ID),
        activated=True,
        activation_blocker=None,
        evaluation_registry=EvaluationRegistryPin(path=CYCLE_1_REGISTRY),
        spend=SpendCeiling(hard_cap_usd=usd("500.00"), max_per_case_usd=usd("500.00")),
    )


def inert_cycle_2() -> CycleConfig:
    return load_cycle(CYCLE_2_ID)


def cycle_1() -> CycleConfig:
    return load_cycle(CYCLE_1_ID)

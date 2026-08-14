"""Blessed registry of per-cycle acquisition/selection configs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from legalforecast.config.cycles.cycle_1 import CYCLE_1
from legalforecast.config.cycles.cycle_2 import CYCLE_2
from legalforecast.config.errors import (
    CycleConfigNotActivatedError,
    UnknownCycleConfigError,
)
from legalforecast.config.types import CycleConfig

CYCLE_CONFIGS: Mapping[str, CycleConfig] = {
    CYCLE_1.cycle_id: CYCLE_1,
    CYCLE_2.cycle_id: CYCLE_2,
}


def repository_root() -> Path:
    """Return the repository root that contains ``legalforecast/``."""

    return Path(__file__).resolve().parents[2]


def load_cycle(cycle_id: str) -> CycleConfig:
    """Return a registered cycle config, including inert drafts.

    This does not activate the cycle and does not run registry preflight.
    """

    try:
        return CYCLE_CONFIGS[cycle_id]
    except KeyError as exc:
        known = ", ".join(sorted(CYCLE_CONFIGS))
        raise UnknownCycleConfigError(
            f"unknown cycle config {cycle_id!r}; known cycles: {known}"
        ) from exc


def require_activated(config: CycleConfig) -> CycleConfig:
    """Refuse a config that is not activated for live acquisition/selection."""

    if not config.activated:
        blocker = config.activation_blocker or "activated=false"
        kind = "legacy-pinned" if config.legacy_pinned else "draft"
        raise CycleConfigNotActivatedError(
            f"{kind} cycle {config.cycle_id!r} is not activated ({blocker}). "
            "No live acquisition or selection path may use it as authority."
        )
    if config.spend.hard_cap_usd is None:
        raise CycleConfigNotActivatedError(
            f"cycle {config.cycle_id!r} cannot be activated with unresolved "
            "spend.hard_cap_usd. Draft None is only valid while activated=false."
        )
    return config


def load_activated_cycle(cycle_id: str) -> CycleConfig:
    """Load a registered cycle and refuse it unless ``activated`` is true."""

    return require_activated(load_cycle(cycle_id))

"""Errors for the per-cycle acquisition/selection configuration home."""

from __future__ import annotations


class CycleConfigError(ValueError):
    """Base error for cycle-config load, validation, or preflight failures."""


class UnknownCycleConfigError(CycleConfigError):
    """Raised when a cycle id is not in the blessed registry."""


class CycleConfigNotActivatedError(CycleConfigError):
    """Raised when a live selection entrypoint asks for an inert cycle config."""


class SelectorRegistryCollisionError(CycleConfigError):
    """Raised when a selector model appears in the cycle's evaluation registry."""


class EvaluationRegistryPinError(CycleConfigError):
    """Raised when the cycle's pinned evaluation registry cannot be used."""

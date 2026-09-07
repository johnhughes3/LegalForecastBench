"""Small public scoring predicates shared across release producers and consumers."""

from __future__ import annotations

from collections.abc import Iterable


def case_has_scored_units(scoreability: Iterable[bool | None]) -> bool:
    """Return whether a case has at least one explicitly scoreable unit."""

    return any(flag is True for flag in scoreability)

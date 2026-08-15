"""Paid CourtListener RECAP Fetch client construction policy."""

from __future__ import annotations

from collections.abc import Callable


def build_paid_recap[ClientT](
    client_type: Callable[..., ClientT], config: object, **kwargs: object
) -> ClientT:
    """Build every paid executor with a 16-minute queue-lag window."""

    return client_type(
        config,
        **kwargs,
        poll_attempts=120,
        poll_backoff_seconds=8.0,
    )

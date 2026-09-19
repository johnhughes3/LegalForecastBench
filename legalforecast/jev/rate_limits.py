"""Bounded retries of rejected Jev requests under one case reservation."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from legalforecast.evals.live_model_solver import LiveModelProviderError


def call_with_rate_limit_retries(
    call: Callable[[], Mapping[str, object]],
) -> Mapping[str, object]:
    """Retry every HTTP 429; return the first response without answer selection.

    The case reservation covers the entire operation. Rejected requests cannot
    produce an accepted prediction; any other failure remains ambiguous under
    the existing spend handler. Persist the request count with a successful
    response so crash recovery retains the retry evidence.
    """

    attempts = 0

    def request() -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        try:
            payload = call()
        except LiveModelProviderError as exc:
            if exc.status_code == 429:
                # Owner policy: HTTP status is authoritative even when an SDK
                # labels a quota/capacity rejection nonretryable.
                exc.retryable = True
                # Successful CLI stdout/stderr is saved as JSON by Actions.
                # Retain exhaustion detail on the exception without polluting
                # successful run summaries with retry log lines.
                exc.add_note(f"Jev HTTP 429: request {attempts} of 8 rejected")
            raise
        return {**payload, "_jev_request_count": attempts}

    retry = Retrying(
        retry=retry_if_exception(
            lambda exc: (
                isinstance(exc, LiveModelProviderError) and exc.status_code == 429
            )
        ),
        wait=wait_exponential(multiplier=30, max=300),
        stop=stop_after_attempt(8),
        sleep=time.sleep,
        reraise=True,
    )
    return retry(request)

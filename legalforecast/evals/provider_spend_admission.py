"""Wait for concurrent reservations before authorizing a first provider call."""

from __future__ import annotations

import logging
from collections.abc import Callable

from tenacity import Retrying, retry_if_exception, stop_before_delay, wait_fixed

from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    ProviderCapExceededError,
    ProviderSpendAuthority,
    ProviderSpendKey,
    SpendControlSnapshot,
)

_LOG = logging.getLogger(__name__)


def authorize_when_capacity_available(
    authority: ProviderSpendAuthority,
    key: ProviderSpendKey,
    *,
    reservation_microusd: int,
    snapshot: Callable[[], SpendControlSnapshot],
    max_wait_seconds: float = 900,
) -> AttemptLease:
    """Retry only pretransport admission while other reservations can settle.

    Ambiguous charges are retained, never considered releasable capacity. The
    authority still atomically enforces its original cap on every authorization.
    This function never invokes a model or retries a provider request.
    """

    def can_wait(error: BaseException) -> bool:
        if not isinstance(error, ProviderCapExceededError):
            return False
        current = snapshot()
        return (
            current.reserved_attempt_count > 0
            and reservation_microusd <= current.cap_microusd
            and not current.authority_poisoned
        )

    for attempt in Retrying(
        retry=retry_if_exception(can_wait),
        wait=wait_fixed(5),
        stop=stop_before_delay(max_wait_seconds),
        reraise=True,
        before_sleep=lambda _: _LOG.info(
            "Waiting for concurrent provider reservations to settle before transport"
        ),
    ):
        with attempt:
            return authority.authorize_attempt(
                key, reservation_microusd=reservation_microusd
            )
    raise AssertionError("reservation retry finished without a lease or error")

"""Bind individual live-model HTTP attempts to the frozen spend authority."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    ProviderSpendAuthority,
    ProviderSpendKey,
)

JsonRecord = Mapping[str, object]


class AttemptHandler(Protocol):
    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord: ...

    def durable_attempt_ordinal(self, local_ordinal: int) -> int: ...

    def adopt_attempt(
        self,
        local_ordinal: int,
        *,
        durable_attempt_ordinal: int | None = None,
    ) -> None: ...

    def bind_authority_attempt(
        self,
        local_ordinal: int,
        authority_attempt_ordinal: int,
    ) -> None: ...

    def authority_attempt_ordinal(self, local_ordinal: int) -> int: ...

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None: ...

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None: ...


@dataclass(slots=True)
class ProviderSpendAttemptHandler:
    """Authorize immediately pre-call and conservatively account every outcome."""

    authority: ProviderSpendAuthority
    key: ProviderSpendKey
    reservation_microusd: int
    _leases_by_local_ordinal: dict[int, AttemptLease] = field(
        default_factory=dict[int, AttemptLease]
    )
    _leases_by_durable_ordinal: dict[int, AttemptLease] = field(
        default_factory=dict[int, AttemptLease]
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.reservation_microusd, bool)
            or self.reservation_microusd <= 0
        ):
            raise ValueError("reservation_microusd must be a positive integer")

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        """Persist authorization immediately before invoking provider transport."""

        if attempt_ordinal in self._leases_by_local_ordinal:
            raise RuntimeError("local provider attempt ordinal was reused")
        lease = self.authority.authorize_attempt(
            self.key,
            reservation_microusd=self.reservation_microusd,
        )
        self._leases_by_local_ordinal[attempt_ordinal] = lease
        self._leases_by_durable_ordinal[lease.attempt_ordinal] = lease
        try:
            return call()
        except BaseException as exc:
            # Once transport begins, a missing response can still be billable. Keep
            # the reservation until immutable provider usage data reconciles it.
            self.authority.record_failure(
                lease,
                failure_type=type(exc).__name__,
                ambiguous=True,
            )
            raise

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        """Return the authority-assigned ordinal for solver settlement."""

        try:
            return self._leases_by_local_ordinal[local_ordinal].attempt_ordinal
        except KeyError as exc:
            raise RuntimeError(
                "provider attempt lacks a durable authorization"
            ) from exc

    def adopt_attempt(
        self,
        local_ordinal: int,
        *,
        durable_attempt_ordinal: int | None = None,
    ) -> None:
        """Recover the unique crash-reserved authority attempt for a replay."""

        if local_ordinal in self._leases_by_local_ordinal:
            return
        if durable_attempt_ordinal is None:
            raise RuntimeError("provider replay lacks an exact durable attempt ordinal")
        lease = self.authority.adopt_attempt(
            self.key,
            attempt_ordinal=durable_attempt_ordinal,
        )
        self._leases_by_local_ordinal[local_ordinal] = lease
        self._leases_by_durable_ordinal[lease.attempt_ordinal] = lease

    def bind_authority_attempt(
        self,
        local_ordinal: int,
        authority_attempt_ordinal: int,
    ) -> None:
        """Verify this handler's in-memory local-to-authority binding."""

        if self.durable_attempt_ordinal(local_ordinal) != authority_attempt_ordinal:
            raise RuntimeError("provider authority attempt binding differs")

    def authority_attempt_ordinal(self, local_ordinal: int) -> int:
        """Return the exact authority ordinal bound to one local attempt."""

        return self.durable_attempt_ordinal(local_ordinal)

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        """Retain reservation when response parsing or verification fails."""

        lease = self._durable_lease(durable_attempt_ordinal)
        self.authority.record_failure(
            lease,
            failure_type=failure_type,
            ambiguous=True,
        )

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        """Settle exact usage, rounding fractional microdollars upward."""

        actual_microusd = math.ceil(actual_cost_usd * 1_000_000)
        self.authority.record_response(
            self._durable_lease(attempt_ordinal),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_microusd=actual_microusd,
            response_sha256=hashlib.sha256(raw_output.encode()).hexdigest(),
        )

    def _durable_lease(self, durable_attempt_ordinal: int) -> AttemptLease:
        try:
            return self._leases_by_durable_ordinal[durable_attempt_ordinal]
        except KeyError as exc:
            raise RuntimeError(
                "provider attempt lacks a durable authorization"
            ) from exc


@dataclass(slots=True)
class CompositeProviderAttemptHandler:
    """Preserve local replay while authorizing only real remote calls."""

    replay_handler: AttemptHandler
    spend_handler: AttemptHandler
    _spend_authorized_local_ordinals: set[int] = field(default_factory=set[int])

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        def authorized_call() -> JsonRecord:
            self._spend_authorized_local_ordinals.add(attempt_ordinal)
            result = self.spend_handler.run_attempt(attempt_ordinal, call)
            self.replay_handler.bind_authority_attempt(
                attempt_ordinal,
                self.spend_handler.authority_attempt_ordinal(attempt_ordinal),
            )
            return result

        result = self.replay_handler.run_attempt(attempt_ordinal, authorized_call)
        if attempt_ordinal not in self._spend_authorized_local_ordinals:
            # A replay hit means the prior process persisted a usable response.
            # Adopt its still-reserved remote attempt before settlement rather
            # than silently skipping shared accounting or consuming a new attempt.
            self.spend_handler.adopt_attempt(
                attempt_ordinal,
                durable_attempt_ordinal=(
                    self.replay_handler.authority_attempt_ordinal(attempt_ordinal)
                ),
            )
            self._spend_authorized_local_ordinals.add(attempt_ordinal)
        return result

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        # The local ordinal is a stable composite handle; each store may map it
        # to a different durable ordinal after a prior ambiguous attempt.
        return local_ordinal

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        # Persist the replayable response first. If the process then dies before
        # observing remote settlement, the next run adopts the reserved/settled
        # remote attempt and retries settlement idempotently without another call.
        self.replay_handler.settle_attempt(
            self.replay_handler.durable_attempt_ordinal(attempt_ordinal),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=actual_cost_usd,
            raw_output=raw_output,
        )
        if attempt_ordinal in self._spend_authorized_local_ordinals:
            self.spend_handler.settle_attempt(
                self.spend_handler.durable_attempt_ordinal(attempt_ordinal),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                actual_cost_usd=actual_cost_usd,
                raw_output=raw_output,
            )

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        # Make the captured response non-replayable first. If the process dies
        # before the shared transition, its remote reservation remains intact and
        # a restarted process allocates a fresh attempt instead of adopting a
        # remote attempt that may already be ambiguous.
        self.replay_handler.record_post_response_failure(
            self.replay_handler.durable_attempt_ordinal(durable_attempt_ordinal),
            failure_type=failure_type,
        )
        if durable_attempt_ordinal in self._spend_authorized_local_ordinals:
            self.spend_handler.record_post_response_failure(
                self.spend_handler.durable_attempt_ordinal(durable_attempt_ordinal),
                failure_type=failure_type,
            )


def conservative_reservation_microusd(
    *,
    context_limit: int,
    max_output_tokens: int,
    input_token_price: float,
    output_token_price: float,
) -> int:
    """Return a ceiling reservation from registry prices per million tokens."""

    if context_limit <= 0 or max_output_tokens <= 0:
        raise ValueError("provider token limits must be positive")
    if input_token_price < 0 or output_token_price < 0:
        raise ValueError("provider token prices cannot be negative")
    reservation = math.ceil(
        context_limit * input_token_price + max_output_tokens * output_token_price
    )
    return max(reservation, 1)

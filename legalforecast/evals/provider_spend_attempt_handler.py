"""Bind individual live-model HTTP attempts to the frozen spend authority."""

from __future__ import annotations

import hashlib
import math
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, cast

from legalforecast.evals.model_registry import LongContextSurcharge
from legalforecast.evals.provider_spend_control import (
    RETRYABLE_HTTP_429_FAILURE_TYPE,
    AdditionalAttemptPermit,
    AttemptLease,
    AttemptLimitExceededError,
    ProviderSpendAuthority,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)

JsonRecord = Mapping[str, object]
ResponseObserver = Callable[[AttemptLease, JsonRecord], None]
RunAttemptWithPreflight = Callable[
    [int, Callable[[], None], Callable[[], JsonRecord]],
    JsonRecord,
]


class AttemptHandler(Protocol):
    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        raise NotImplementedError

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        raise NotImplementedError

    def adopt_attempt(
        self,
        local_ordinal: int,
        *,
        durable_attempt_ordinal: int | None = None,
    ) -> None:
        raise NotImplementedError

    def bind_authority_attempt(
        self,
        local_ordinal: int,
        authority_attempt_ordinal: int,
    ) -> None:
        raise NotImplementedError

    def authority_attempt_ordinal(self, local_ordinal: int) -> int:
        raise NotImplementedError

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        raise NotImplementedError

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class ProviderSpendAttemptHandler:
    """Authorize immediately pre-call and conservatively account every outcome."""

    authority: ProviderSpendAuthority
    key: ProviderSpendKey
    reservation_microusd: int
    additional_attempt_permit: AdditionalAttemptPermit | None = None
    before_authorize: Callable[[sqlite3.Connection, AttemptLease], None] | None = None
    after_authorize: Callable[[AttemptLease], None] | None = None
    failure_observer: Callable[[bool], None] | None = None
    allow_retryable_nonbillable_replacement: bool = False
    retryable_nonbillable_prior_attempt: AttemptLease | None = None
    replayable_attempt: AttemptLease | None = None
    replayable_response: JsonRecord | None = None
    pretransport_attempt_ordinal: int | None = None
    pretransport_attempt: AttemptLease | None = None
    pretransport_attempt_observer: Callable[[AttemptLease], None] | None = None
    transport_start_observer: Callable[[AttemptLease], None] | None = None
    response_observer: ResponseObserver | None = None
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
        if (self.replayable_attempt is None) != (self.replayable_response is None):
            raise ValueError("provider replay requires both attempt and response")
        if (
            self.replayable_attempt is not None
            and self.pretransport_attempt_ordinal is not None
        ):
            raise ValueError(
                "provider replay and pretransport reuse are mutually exclusive"
            )
        if self.pretransport_attempt is not None and (
            self.pretransport_attempt_ordinal is None
            or self.pretransport_attempt.attempt_ordinal
            != self.pretransport_attempt_ordinal
        ):
            raise ValueError(
                "pretransport lease and ordinal must identify the same attempt"
            )

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        """Persist authorization immediately before invoking provider transport."""

        if attempt_ordinal in self._leases_by_local_ordinal:
            raise RuntimeError("local provider attempt ordinal was reused")
        if self.replayable_attempt is not None:
            if attempt_ordinal != 1 or self.replayable_response is None:
                raise RuntimeError("provider replay state is incomplete")
            lease = self.replayable_attempt
            self._leases_by_local_ordinal[attempt_ordinal] = lease
            self._leases_by_durable_ordinal[lease.attempt_ordinal] = lease
            return self.replayable_response
        if self.pretransport_attempt_ordinal is not None and attempt_ordinal == 1:
            lease = self.pretransport_attempt
            if lease is None:
                lease = self.authority.adopt_attempt(
                    self.key,
                    attempt_ordinal=self.pretransport_attempt_ordinal,
                )
        else:
            try:
                replacement_ordinal = attempt_ordinal in {1, 2}
                if (
                    self.allow_retryable_nonbillable_replacement
                    and replacement_ordinal
                    and isinstance(self.authority, SqliteProviderSpendAuthority)
                    and self.before_authorize is not None
                    and (
                        attempt_ordinal == 2
                        or self.retryable_nonbillable_prior_attempt is not None
                    )
                ):
                    prior_attempt = (
                        self.retryable_nonbillable_prior_attempt
                        if attempt_ordinal == 1
                        else self._leases_by_local_ordinal.get(1)
                    )
                    if prior_attempt is None:
                        raise RuntimeError(
                            "retryable replacement lacks the exact prior attempt"
                        )
                    lease = self._authorize_nonbillable_replacement(prior_attempt)
                elif self.before_authorize is None:
                    lease = self.authority.authorize_attempt(
                        self.key,
                        reservation_microusd=self.reservation_microusd,
                    )
                elif isinstance(self.authority, SqliteProviderSpendAuthority):
                    lease = self.authority.authorize_attempt_with_transaction(
                        self.key,
                        reservation_microusd=self.reservation_microusd,
                        before_commit=self.before_authorize,
                    )
                else:
                    raise RuntimeError(
                        "atomic caller reservation requires SQLite spend authority"
                    )
            except AttemptLimitExceededError:
                permit = self.additional_attempt_permit
                authorize_additional = getattr(
                    self.authority, "authorize_additional_attempt", None
                )
                if permit is None or not callable(authorize_additional):
                    raise
                lease = cast(
                    AttemptLease,
                    authorize_additional(
                        self.key,
                        reservation_microusd=min(
                            self.reservation_microusd,
                            permit.reservation_cap_microusd,
                        ),
                        permit=permit,
                    ),
                )
        self._leases_by_local_ordinal[attempt_ordinal] = lease
        self._leases_by_durable_ordinal[lease.attempt_ordinal] = lease
        if self.after_authorize is not None:
            self.after_authorize(lease)
        if (
            self.pretransport_attempt_ordinal is not None
            and attempt_ordinal == 1
            and self.pretransport_attempt_observer is not None
        ):
            self.pretransport_attempt_observer(lease)
        if self.transport_start_observer is not None:
            self.transport_start_observer(lease)
        try:
            response = call()
            if self.response_observer is not None:
                self.response_observer(lease, response)
            return response
        except BaseException as exc:
            # Once transport begins, a missing response can still be billable. Keep
            # the reservation until immutable provider usage data reconciles it.
            # Only an explicitly retryable HTTP 429 proves a pre-generation
            # rejection. Missing retryability evidence remains fail-closed.
            retryable_nonbillable = (
                getattr(exc, "status_code", None) == 429
                and getattr(exc, "retryable", None) is True
            )
            ambiguous = not retryable_nonbillable
            self.authority.record_failure(
                lease,
                failure_type=(
                    RETRYABLE_HTTP_429_FAILURE_TYPE
                    if retryable_nonbillable
                    else type(exc).__name__
                ),
                ambiguous=ambiguous,
            )
            if self.failure_observer is not None:
                self.failure_observer(ambiguous)
            raise

    def _authorize_nonbillable_replacement(
        self,
        prior_attempt: AttemptLease,
    ) -> AttemptLease:
        if not isinstance(self.authority, SqliteProviderSpendAuthority):
            raise RuntimeError("nonbillable replacement requires SQLite authority")
        if self.before_authorize is None:
            raise RuntimeError("nonbillable replacement requires caller reservation")
        return self.authority.authorize_nonbillable_replacement_with_transaction(
            self.key,
            prior_attempt=prior_attempt,
            reservation_microusd=self.reservation_microusd,
            before_commit=self.before_authorize,
        )

    def run_attempt_with_preflight(
        self,
        attempt_ordinal: int,
        preflight: Callable[[], None],
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        """Validate request construction before reserving shared spend."""

        if self.replayable_attempt is not None:
            return self.run_attempt(attempt_ordinal, call)
        preflight()
        return self.run_attempt(attempt_ordinal, call)

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
        if self.failure_observer is not None:
            self.failure_observer(True)

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
        return self._run_attempt(attempt_ordinal, call, preflight=None)

    def run_attempt_with_preflight(
        self,
        attempt_ordinal: int,
        preflight: Callable[[], None],
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        """Replay without credentials, or preflight before fresh spend."""

        return self._run_attempt(attempt_ordinal, call, preflight=preflight)

    def _run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
        *,
        preflight: Callable[[], None] | None,
    ) -> JsonRecord:
        def authorized_call() -> JsonRecord:
            try:
                result = self.spend_handler.run_attempt(attempt_ordinal, call)
            except BaseException:
                self._bind_authority_attempt(attempt_ordinal, required=False)
                raise
            self._bind_authority_attempt(attempt_ordinal, required=True)
            return result

        run_with_preflight = getattr(
            self.replay_handler,
            "run_attempt_with_preflight",
            None,
        )
        if preflight is not None and callable(run_with_preflight):
            result = cast(RunAttemptWithPreflight, run_with_preflight)(
                attempt_ordinal,
                preflight,
                authorized_call,
            )
        else:
            if preflight is not None:
                preflight()
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

    def _bind_authority_attempt(
        self,
        local_ordinal: int,
        *,
        required: bool,
    ) -> None:
        """Persist an available remote ordinal before replay records the outcome."""

        try:
            authority_ordinal = self.spend_handler.authority_attempt_ordinal(
                local_ordinal
            )
        except RuntimeError:
            if required:
                raise
            return
        self.replay_handler.bind_authority_attempt(
            local_ordinal,
            authority_ordinal,
        )
        self._spend_authorized_local_ordinals.add(local_ordinal)

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
    long_context_surcharge: LongContextSurcharge | None = None,
) -> int:
    """Return a ceiling reservation from registry prices per million tokens."""

    if context_limit <= 0 or max_output_tokens <= 0:
        raise ValueError("provider token limits must be positive")
    if max_output_tokens >= context_limit:
        raise ValueError("max_output_tokens must be less than context_limit")
    if input_token_price < 0 or output_token_price < 0:
        raise ValueError("provider token prices cannot be negative")
    max_input_tokens = context_limit - max_output_tokens
    if (
        long_context_surcharge is not None
        and max_input_tokens > long_context_surcharge.threshold_input_tokens
    ):
        input_token_price *= long_context_surcharge.input_price_multiplier
        output_token_price *= long_context_surcharge.output_price_multiplier
    reservation = math.ceil(
        max_input_tokens * input_token_price + max_output_tokens * output_token_price
    )
    return max(reservation, 1)


def max_output_tokens_for_reservation_cap(
    *,
    context_limit: int,
    max_output_tokens: int,
    input_tokens: int,
    input_token_price: float,
    output_token_price: float,
    reservation_cap_microusd: int,
    long_context_surcharge: LongContextSurcharge | None = None,
) -> int:
    """Return a request output bound that fits a fixed micro-USD ceiling.

    The input token count must be a conservative bound for the exact prompt.
    Prices are expressed in provider dollars per million tokens, so multiplying
    a token count by a price yields micro-USD.  The returned bound is also
    constrained by the registry context window; a non-positive result fails
    closed before any provider transport is constructed.
    """

    if type(context_limit) is not int or context_limit <= 0:
        raise ValueError("context_limit must be a positive integer")
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    if max_output_tokens >= context_limit:
        raise ValueError("max_output_tokens must be less than context_limit")
    if type(input_tokens) is not int or input_tokens < 0:
        raise ValueError("input_tokens must be a non-negative integer")
    if input_tokens >= context_limit:
        raise ValueError("input_tokens must be less than context_limit")
    if input_token_price < 0 or output_token_price < 0:
        raise ValueError("provider token prices cannot be negative")
    if type(reservation_cap_microusd) is not int or reservation_cap_microusd <= 0:
        raise ValueError("reservation_cap_microusd must be a positive integer")

    effective_input_price = input_token_price
    effective_output_price = output_token_price
    if (
        long_context_surcharge is not None
        and input_tokens > long_context_surcharge.threshold_input_tokens
    ):
        effective_input_price *= long_context_surcharge.input_price_multiplier
        effective_output_price *= long_context_surcharge.output_price_multiplier

    input_cost_microusd = math.ceil(input_tokens * effective_input_price)
    remaining_microusd = reservation_cap_microusd - input_cost_microusd
    context_bound = min(max_output_tokens, context_limit - input_tokens)
    if remaining_microusd <= 0:
        raise ValueError(
            "reservation cap cannot cover the conservative prompt input cost"
        )
    if effective_output_price == 0:
        output_bound = context_bound
    else:
        output_bound = min(
            context_bound,
            math.floor(remaining_microusd / effective_output_price),
        )
        # Correct any binary-float boundary round-down/up without making the
        # request less conservative than the authenticated cap.
        while (
            output_bound > 0
            and math.ceil(output_bound * effective_output_price) > remaining_microusd
        ):
            output_bound -= 1
    if output_bound <= 0:
        raise ValueError("reservation cap cannot cover one conservative output token")
    return output_bound

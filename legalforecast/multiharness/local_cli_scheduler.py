"""Requested-versus-actual concurrency and ordering for local CLI runs.

A request for parallelism cannot silently execute serially or exceed the
scheduler cap. Divergence is recorded on the receipt; over-subscribe either
refuses before spend or is disclosed, never swallowed.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal, Protocol

ORDERING_SERIAL = "serial"
ORDERING_PARALLEL = "parallel"
ORDERINGS = frozenset({ORDERING_SERIAL, ORDERING_PARALLEL})
OVERSUBSCRIBE_REFUSE = "refuse"
OVERSUBSCRIBE_RECORD = "record"


class LocalCliSchedulerError(RuntimeError):
    """Raised when requested scheduling cannot be honored before spend."""

    def __init__(self, message: str, *, failure_class: str) -> None:
        super().__init__(message)
        self.failure_class = failure_class


class ScheduledSpec(Protocol):
    """Duck-typed run spec fields the scheduler needs."""

    @property
    def spec_id(self) -> str: ...

    @property
    def max_concurrency(self) -> int: ...

    @property
    def ordering(self) -> str: ...


@dataclass(frozen=True, slots=True)
class SchedulingEvidence:
    """Path-free scheduling evidence copied onto an execution receipt."""

    requested_max_concurrency: int
    requested_ordering: str
    observed_concurrency: int
    schedule_sequence: int
    peak_concurrency: int
    divergence: str | None

    def to_public_record(self) -> dict[str, object]:
        """Return the secret-free scheduling audit record."""

        return {
            "requested_max_concurrency": self.requested_max_concurrency,
            "requested_ordering": self.requested_ordering,
            "observed_concurrency": self.observed_concurrency,
            "schedule_sequence": self.schedule_sequence,
            "peak_concurrency": self.peak_concurrency,
            "divergence": self.divergence,
        }


def unevaluated_scheduling(
    *,
    requested_max_concurrency: int,
    requested_ordering: str,
) -> SchedulingEvidence:
    """Placeholder evidence used before a scheduler records an observation."""

    return SchedulingEvidence(
        requested_max_concurrency=requested_max_concurrency,
        requested_ordering=requested_ordering,
        observed_concurrency=0,
        schedule_sequence=0,
        peak_concurrency=0,
        divergence=None,
    )


class NullScheduler:
    """No-op scheduler that still returns unevaluated evidence on release."""

    def before_execute(self, spec: ScheduledSpec) -> None:
        del spec

    def after_execute(self, spec: ScheduledSpec, result: object) -> SchedulingEvidence:
        del result
        return unevaluated_scheduling(
            requested_max_concurrency=spec.max_concurrency,
            requested_ordering=spec.ordering,
        )


class LocalCliScheduler:
    """Shared scheduler that measures and enforces requested concurrency."""

    def __init__(
        self,
        *,
        max_concurrency: int | None = None,
        on_oversubscribe: Literal["refuse", "record"] = OVERSUBSCRIBE_REFUSE,
    ) -> None:
        if max_concurrency is not None and max_concurrency < 1:
            raise LocalCliSchedulerError(
                "scheduler max_concurrency must be positive",
                failure_class="invalid_cap",
            )
        if on_oversubscribe not in {OVERSUBSCRIBE_REFUSE, OVERSUBSCRIBE_RECORD}:
            raise LocalCliSchedulerError(
                "unsupported parallelism policy",
                failure_class="invalid_cap",
            )
        self.max_concurrency = max_concurrency
        self.on_oversubscribe = on_oversubscribe
        self._lock = threading.Lock()
        self._inflight = 0
        self._peak = 0
        self._next_sequence = 1
        self._tls = threading.local()

    @property
    def peak_concurrency(self) -> int:
        """Highest in-flight count observed on this scheduler."""

        with self._lock:
            return self._peak

    def before_execute(self, spec: ScheduledSpec) -> None:
        """Acquire a slot or refuse/record over-subscribe before spend."""

        requested = spec.max_concurrency
        ordering = spec.ordering
        if requested < 1:
            raise LocalCliSchedulerError(
                "requested_concurrency must be positive",
                failure_class="invalid_request",
            )
        if ordering not in ORDERINGS:
            raise LocalCliSchedulerError(
                "requested ordering is not recognized",
                failure_class="invalid_request",
            )
        if ordering == ORDERING_SERIAL and requested != 1:
            raise LocalCliSchedulerError(
                "serial ordering requires max_concurrency=1",
                failure_class="invalid_request",
            )
        cap = self.max_concurrency if self.max_concurrency is not None else requested
        if requested > cap:
            raise LocalCliSchedulerError(
                "unsupported parallelism exceeds scheduler cap",
                failure_class="unsupported_parallelism",
            )
        with self._lock:
            next_inflight = self._inflight + 1
            divergence = self._divergence_locked(
                ordering=ordering,
                requested=requested,
                cap=cap,
                next_inflight=next_inflight,
            )
            if divergence is not None and self.on_oversubscribe == OVERSUBSCRIBE_REFUSE:
                raise LocalCliSchedulerError(
                    "scheduler would over-subscribe",
                    failure_class=divergence,
                )
            self._inflight = next_inflight
            if next_inflight > self._peak:
                self._peak = next_inflight
            sequence = self._next_sequence
            self._next_sequence += 1
            evidence = SchedulingEvidence(
                requested_max_concurrency=requested,
                requested_ordering=ordering,
                observed_concurrency=next_inflight,
                schedule_sequence=sequence,
                peak_concurrency=self._peak,
                divergence=divergence,
            )
        self._tls.evidence = evidence

    def after_execute(self, spec: ScheduledSpec, result: object) -> SchedulingEvidence:
        """Release the slot and return requested-versus-actual evidence."""

        del result
        evidence = getattr(self._tls, "evidence", None)
        if not isinstance(evidence, SchedulingEvidence):
            evidence = unevaluated_scheduling(
                requested_max_concurrency=spec.max_concurrency,
                requested_ordering=spec.ordering,
            )
        with self._lock:
            if self._inflight > 0:
                self._inflight -= 1
            peak = self._peak
        undersubscribed = (
            evidence.divergence is None
            and evidence.requested_ordering == ORDERING_PARALLEL
            and peak < evidence.requested_max_concurrency
        )
        divergence = evidence.divergence
        if undersubscribed:
            divergence = "observed_concurrency_below_requested"
        return SchedulingEvidence(
            requested_max_concurrency=evidence.requested_max_concurrency,
            requested_ordering=evidence.requested_ordering,
            observed_concurrency=evidence.observed_concurrency,
            schedule_sequence=evidence.schedule_sequence,
            peak_concurrency=peak,
            divergence=divergence,
        )

    def _divergence_locked(
        self,
        *,
        ordering: str,
        requested: int,
        cap: int,
        next_inflight: int,
    ) -> str | None:
        if ordering == ORDERING_SERIAL and self._inflight > 0:
            return "serial_overlap"
        if next_inflight > cap:
            return "observed_concurrency_exceeds_cap"
        if next_inflight > requested:
            return "observed_concurrency_exceeds_requested"
        return None


ConcurrencyScheduler = LocalCliScheduler
SchedulingSnapshot = SchedulingEvidence
SERIAL_ORDERING = ORDERING_SERIAL
CONCURRENT_ORDERING = ORDERING_PARALLEL

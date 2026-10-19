"""Durable per-criterion spend settlement for protected Harvey LAB judging."""

from __future__ import annotations

import hashlib
import math
from decimal import Decimal

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    ProviderSpendAuthority,
)
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    ProtectedPaidGatewayConfig,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionJudgeResponse,
)
from legalforecast.multiharness.spend import UsageObservation


class ProtectedHarveyLabSpendError(RuntimeError):
    """A protected LAB judge request cannot be authorized or settled."""


class ProtectedHarveyLabJudgeBoundary(HarveyLabJudgeRequestBoundary):
    """Reserve and settle every judge request in the solver's durable journal."""

    def __init__(
        self,
        *,
        authority: ProviderSpendAuthority,
        config: ProtectedPaidGatewayConfig,
    ) -> None:
        self._authority = authority
        self._config = config
        self._leases: dict[tuple[int, int], AttemptLease] = {}

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        key = self._config.spend.key_for_gateway_request(
            f"harvey-lab-judge-{request.ordinal}",
            request.attempt_index + 1,
        )
        lease = self._authority.authorize_attempt(
            key,
            reservation_microusd=self._config.reservation_microusd,
        )
        self._leases[(request.ordinal, request.attempt_index)] = lease
        return lease

    def mark_transport_started(self, request: HarveyLabJudgeRequest) -> None:
        lease = self._lease_for(request)
        marker = getattr(self._authority, "mark_transport_started", None)
        if not callable(marker):
            raise ProtectedHarveyLabSpendError(
                "protected judge authority cannot mark transport start"
            )
        marker(lease)

    def after_judge_response(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        response: ProductionJudgeResponse,
    ) -> None:
        lease = self._matching_lease(request, reservation)
        usage = response.usage
        actual_microusd = usage_cost_microusd(usage, self._config.registry_entry)
        if usage.input_tokens is None or usage.output_tokens is None:
            raise ProtectedHarveyLabSpendError(
                "protected judge response omitted token usage"
            )
        self._authority.record_response(
            lease,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            actual_microusd=actual_microusd,
            response_sha256=hashlib.sha256(response.raw_response).hexdigest(),
        )
        self._leases.pop((request.ordinal, request.attempt_index))

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        del request, reservation, observation
        raise ProtectedHarveyLabSpendError(
            "protected judge settlement requires the retained provider response"
        )

    def record_judge_failure(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
    ) -> None:
        lease = self._matching_lease(request, reservation)
        self._authority.record_failure(
            lease,
            failure_type="harvey_lab_judge_transport_failed",
            ambiguous=True,
        )
        self._leases.pop((request.ordinal, request.attempt_index))

    def _lease_for(self, request: HarveyLabJudgeRequest) -> AttemptLease:
        try:
            return self._leases[(request.ordinal, request.attempt_index)]
        except KeyError as exc:
            raise ProtectedHarveyLabSpendError(
                "protected judge request has no active spend lease"
            ) from exc

    def _matching_lease(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
    ) -> AttemptLease:
        lease = self._lease_for(request)
        if not isinstance(reservation, AttemptLease) or reservation != lease:
            raise ProtectedHarveyLabSpendError(
                "protected judge response does not match its spend lease"
            )
        return lease


def usage_cost_microusd(
    usage: UsageObservation,
    entry: ModelRegistryEntry,
) -> int:
    """Price a judge response from reported cost or frozen registry rates."""

    if usage.reported_cost_usd is not None:
        return math.ceil(Decimal(usage.reported_cost_usd) * Decimal(1_000_000))
    if usage.input_tokens is None or usage.output_tokens is None:
        raise ProtectedHarveyLabSpendError("protected judge usage cannot be priced")
    return registry_cost_microusd(
        entry,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


def registry_cost_microusd(
    entry: ModelRegistryEntry,
    *,
    input_tokens: int,
    output_tokens: int,
) -> int:
    """Apply the frozen model registry's base and long-context prices."""

    input_price = Decimal(str(entry.input_token_price))
    output_price = Decimal(str(entry.output_token_price))
    surcharge = entry.long_context_surcharge
    if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
        input_price *= Decimal(str(surcharge.input_price_multiplier))
        output_price *= Decimal(str(surcharge.output_price_multiplier))
    return math.ceil(
        Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price
    )


__all__ = [
    "ProtectedHarveyLabJudgeBoundary",
    "ProtectedHarveyLabSpendError",
    "registry_cost_microusd",
    "usage_cost_microusd",
]

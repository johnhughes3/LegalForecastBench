"""Provider-free, fail-closed spend ceilings for Tier-0 execution.

This module deliberately remains a non-authoritative sidecar.  It does not
extend ``RunSpec``, ``ExecutionReceipt``, or any authenticated Cycle 1
contract.  A caller binds its records to the exact executable specification
and a dated pricing snapshot, then uses :class:`SpendController` immediately
before credential resolution and every paid request.

The controller reserves each request's worst-case cost before a request is
started.  Reservations are released only when a request settles.  A missing,
unknown, or subscription-unallocable cost is never interpreted as zero; it
terminalizes the experiment and prevents another paid request.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal, Self, cast

from legalforecast._hashing import is_sha256_digest

Surface = Literal["solver", "judge"]
EnforcementMode = Literal["adapter_argument", "controller_reservation"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]*\Z")
_USD_QUANTUM = Decimal("0.000001")


class SpendFailureClass(StrEnum):
    """Closed classes recorded when a paid call cannot proceed."""

    OVER_BUDGET = "over_budget"
    REQUEST_CAP = "request_cap_exhausted"
    RETRY_CAP = "retry_cap_exhausted"
    PARALLELISM_CAP = "parallelism_cap_exhausted"
    UNKNOWN_COST = "unknown_cost"
    SUBSCRIPTION_UNALLOCABLE = "subscription_unallocable"
    MISSING_PRICING = "missing_pricing"
    UNENFORCED_BUDGET = "unenforced_budget"
    SPEC_MISMATCH = "executable_spec_mismatch"
    PRICING_MISMATCH = "pricing_snapshot_mismatch"
    IDENTITY_MISMATCH = "provider_model_mismatch"


class SpendConfigurationError(ValueError):
    """Raised when a spend policy cannot be audited before credentials."""


class SpendDeniedError(RuntimeError):
    """Raised before a paid request when a policy denies it."""

    def __init__(self, evidence: SpendEvidence) -> None:
        self.evidence = evidence
        super().__init__(evidence.reason)


class SpendSettlementError(RuntimeError):
    """Raised when a reservation cannot be settled safely."""


def _require_token(value: str, field_name: str) -> str:
    if _TOKEN_RE.fullmatch(value) is None:
        raise SpendConfigurationError(f"{field_name} must be a public opaque token")
    return value


def _require_digest(value: str, field_name: str) -> str:
    if not is_sha256_digest(value, allow_prefix=True):
        raise SpendConfigurationError(
            f"{field_name} must be a lowercase SHA-256 digest"
        )
    return value


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SpendConfigurationError("spend record is not canonical JSON") from exc


# contract-ratchet: allow non-persisted spend-sidecar digest
def _record_sha256(payload: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _parse_date(value: str, field_name: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SpendConfigurationError(f"{field_name} must be an ISO date") from exc
    canonical = parsed.isoformat()
    if value != canonical:
        raise SpendConfigurationError(f"{field_name} must use YYYY-MM-DD")
    return canonical


def _parse_usd(value: str | Decimal | int, field_name: str) -> tuple[str, int]:
    if isinstance(value, bool):
        raise SpendConfigurationError(f"{field_name} must be a non-negative USD amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SpendConfigurationError(f"{field_name} must be a USD amount") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(_USD_QUANTUM):
        raise SpendConfigurationError(
            f"{field_name} must be finite and have at most six decimal places"
        )
    micros = int(amount * 1_000_000)
    return format(amount, "f"), micros


def _require_positive_int(value: int, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise SpendConfigurationError(f"{field_name} must be a positive integer")
    return value


def _require_non_negative_int(value: int, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise SpendConfigurationError(f"{field_name} must be a non-negative integer")
    return value


def _usd_from_microusd(value: int) -> str:
    return format(Decimal(value) / 1_000_000, "f")


@dataclass(frozen=True, slots=True)
class PricingRate:
    """Auditable API pricing and usage fields for one provider/model."""

    provider: str
    model: str
    input_microusd_per_token: int
    output_microusd_per_token: int
    request_microusd: int = 0
    usage_fields: tuple[str, ...] = ("input_tokens", "output_tokens")

    def __post_init__(self) -> None:
        _require_token(self.provider, "provider")
        _require_token(self.model, "model")
        _require_non_negative_int(
            self.input_microusd_per_token, "input_microusd_per_token"
        )
        _require_non_negative_int(
            self.output_microusd_per_token, "output_microusd_per_token"
        )
        _require_non_negative_int(self.request_microusd, "request_microusd")
        if not self.usage_fields:
            raise SpendConfigurationError("usage_fields must not be empty")
        if len(set(self.usage_fields)) != len(self.usage_fields):
            raise SpendConfigurationError("usage_fields must be unique")
        for field_name in self.usage_fields:
            _require_token(field_name, "usage_fields entry")
        if not {"input_tokens", "output_tokens"}.issubset(self.usage_fields):
            raise SpendConfigurationError(
                "pricing requires auditable input_tokens and output_tokens fields"
            )

    def worst_case_microusd(self, *, input_tokens: int, output_tokens: int) -> int:
        _require_non_negative_int(input_tokens, "input_tokens")
        _require_non_negative_int(output_tokens, "output_tokens")
        return (
            self.request_microusd
            + input_tokens * self.input_microusd_per_token
            + output_tokens * self.output_microusd_per_token
        )

    def to_record(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_microusd_per_token": self.input_microusd_per_token,
            "output_microusd_per_token": self.output_microusd_per_token,
            "request_microusd": self.request_microusd,
            "usage_fields": list(self.usage_fields),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        fields = record.get("usage_fields")
        if not isinstance(fields, Sequence) or isinstance(fields, str | bytes):
            raise SpendConfigurationError("usage_fields must be an array")
        return cls(
            provider=_required_str(record, "provider"),
            model=_required_str(record, "model"),
            input_microusd_per_token=_required_int(record, "input_microusd_per_token"),
            output_microusd_per_token=_required_int(
                record, "output_microusd_per_token"
            ),
            request_microusd=_optional_int(record, "request_microusd", default=0),
            usage_fields=tuple(
                _required_field_str(item, "usage_fields entry")
                for item in cast(Sequence[object], fields)
            ),
        )


@dataclass(frozen=True, slots=True)
class PricingSnapshot:
    """Dated, hashed pricing inputs required before any paid call."""

    snapshot_id: str
    as_of_date: str
    rates: tuple[PricingRate, ...]
    snapshot_sha256: str = ""

    def __post_init__(self) -> None:
        _require_token(self.snapshot_id, "snapshot_id")
        _parse_date(self.as_of_date, "as_of_date")
        if not self.rates:
            raise SpendConfigurationError("pricing snapshot must include rates")
        keys = [(rate.provider, rate.model) for rate in self.rates]
        if len(set(keys)) != len(keys):
            raise SpendConfigurationError("pricing snapshot contains duplicate models")
        expected = _record_sha256(self._hash_payload())
        if self.snapshot_sha256:
            _require_digest(self.snapshot_sha256, "snapshot_sha256")
            if self.snapshot_sha256 != expected:
                raise SpendConfigurationError("snapshot_sha256 does not match rates")
        else:
            object.__setattr__(self, "snapshot_sha256", expected)

    def _hash_payload(self) -> dict[str, object]:
        return {
            # contract-ratchet: allow non-authoritative pricing sidecar
            "schema_version": "legalforecast.multiharness.pricing_snapshot.v1",
            "snapshot_id": self.snapshot_id,
            "as_of_date": self.as_of_date,
            "rates": [
                rate.to_record()
                for rate in sorted(
                    self.rates, key=lambda item: (item.provider, item.model)
                )
            ],
        }

    def to_record(self) -> dict[str, object]:
        return self._hash_payload() | {"snapshot_sha256": self.snapshot_sha256}

    def rate_for(self, provider: str, model: str) -> PricingRate:
        for rate in self.rates:
            if rate.provider == provider and rate.model == model:
                return rate
        raise SpendConfigurationError(
            f"pricing snapshot has no auditable rate for {provider}/{model}"
        )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        rates = record.get("rates")
        if not isinstance(rates, Sequence) or isinstance(rates, str | bytes):
            raise SpendConfigurationError("rates must be an array")
        schema = _required_str(record, "schema_version")
        if schema != (
            # contract-ratchet: allow non-authoritative pricing sidecar
            "legalforecast.multiharness.pricing_snapshot.v1"
        ):
            raise SpendConfigurationError("unsupported pricing snapshot schema")
        return cls(
            snapshot_id=_required_str(record, "snapshot_id"),
            as_of_date=_required_str(record, "as_of_date"),
            rates=tuple(
                PricingRate.from_record(cast(Mapping[str, Any], item))
                for item in cast(Sequence[object], rates)
            ),
            snapshot_sha256=_required_str(record, "snapshot_sha256"),
        )


@dataclass(frozen=True, slots=True)
class InvocationBudget:
    """How a paid adapter proves that its per-call monetary cap is enforced."""

    mode: EnforcementMode
    argument_name: str | None = None
    argument_value_usd: str | None = None
    # This is intentionally informational.  It is never used as a ceiling.
    advertised_budget_usd: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"adapter_argument", "controller_reservation"}:
            raise SpendConfigurationError("unsupported invocation budget mode")
        if self.mode == "adapter_argument":
            if not self.argument_name or not self.argument_name.startswith("--"):
                raise SpendConfigurationError(
                    "adapter_argument mode requires an argument name"
                )
            if self.argument_value_usd is None:
                raise SpendConfigurationError(
                    "adapter_argument mode requires an enforced amount"
                )
            canonical, micros = _parse_usd(
                self.argument_value_usd, "argument_value_usd"
            )
            object.__setattr__(self, "argument_value_usd", canonical)
            if micros <= 0:
                raise SpendConfigurationError("argument_value_usd must be positive")
        elif self.argument_name is not None or self.argument_value_usd is not None:
            raise SpendConfigurationError(
                "controller_reservation mode cannot claim an adapter argument"
            )
        if self.advertised_budget_usd is not None:
            canonical, _ = _parse_usd(
                self.advertised_budget_usd, "advertised_budget_usd"
            )
            object.__setattr__(self, "advertised_budget_usd", canonical)

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {"mode": self.mode}
        if self.argument_name is not None:
            record["argument_name"] = self.argument_name
        if self.argument_value_usd is not None:
            record["argument_value_usd"] = self.argument_value_usd
        if self.advertised_budget_usd is not None:
            record["advertised_budget_usd"] = self.advertised_budget_usd
        return record


@dataclass(frozen=True, slots=True)
class _CallCeiling:
    surface: Surface
    arm_id: str
    provider: str
    model: str
    max_cost_usd: str
    max_requests: int
    max_retries: int
    max_parallelism: int
    max_input_tokens: int
    max_output_tokens: int
    invocation_budget: InvocationBudget

    def _validate_common(self) -> None:
        if self.surface not in {"solver", "judge"}:
            raise SpendConfigurationError("surface must be solver or judge")
        _require_token(self.arm_id, "arm_id")
        _require_token(self.provider, "provider")
        _require_token(self.model, "model")
        canonical, micros = _parse_usd(self.max_cost_usd, "max_cost_usd")
        object.__setattr__(self, "max_cost_usd", canonical)
        if micros <= 0:
            raise SpendConfigurationError("max_cost_usd must be positive")
        _require_positive_int(self.max_requests, "max_requests")
        _require_non_negative_int(self.max_retries, "max_retries")
        if self.max_retries >= self.max_requests:
            raise SpendConfigurationError("max_retries must be less than max_requests")
        _require_positive_int(self.max_parallelism, "max_parallelism")
        _require_positive_int(self.max_input_tokens, "max_input_tokens")
        _require_positive_int(self.max_output_tokens, "max_output_tokens")

    @property
    def max_cost_microusd(self) -> int:
        return _parse_usd(self.max_cost_usd, "max_cost_usd")[1]

    def worst_case_microusd(self, pricing: PricingRate) -> int:
        return pricing.worst_case_microusd(
            input_tokens=self.max_input_tokens,
            output_tokens=self.max_output_tokens,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "arm_id": self.arm_id,
            "provider": self.provider,
            "model": self.model,
            "max_cost_usd": self.max_cost_usd,
            "max_requests": self.max_requests,
            "max_retries": self.max_retries,
            "max_parallelism": self.max_parallelism,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "invocation_budget": self.invocation_budget.to_record(),
        }


@dataclass(frozen=True, slots=True)
class SolverCeiling(_CallCeiling):
    """Per-arm solver monetary, request, retry, and parallelism cap."""

    surface: Surface = field(default="solver", init=False)

    def __post_init__(self) -> None:
        self._validate_common()
        if self.surface != "solver":
            raise SpendConfigurationError("solver ceiling has invalid surface")
        if self.invocation_budget.mode != "adapter_argument":
            raise SpendConfigurationError(
                "every paid solver arm requires a supported enforced budget argument"
            )
        if self.invocation_budget.argument_value_usd != self.max_cost_usd:
            raise SpendConfigurationError(
                "solver invocation budget must equal the solver dollar ceiling"
            )


@dataclass(frozen=True, slots=True)
class JudgeCriterionCeiling(_CallCeiling):
    """Per-arm, per-criterion judge-call cap."""

    criterion_id: str = ""
    surface: Surface = field(default="judge", init=False)

    def __post_init__(self) -> None:
        self._validate_common()
        if self.surface != "judge":
            raise SpendConfigurationError("judge ceiling has invalid surface")
        _require_token(self.criterion_id, "criterion_id")
        if self.invocation_budget.mode == "adapter_argument":
            if self.invocation_budget.argument_value_usd != self.max_cost_usd:
                raise SpendConfigurationError(
                    "judge invocation budget must equal the judge dollar ceiling"
                )

    def to_record(self) -> dict[str, object]:
        return super().to_record() | {"criterion_id": self.criterion_id}


@dataclass(frozen=True, slots=True)
class ExperimentCeiling:
    """One hard experiment-wide monetary/request/parallelism stop."""

    max_cost_usd: str
    max_requests: int
    max_retries: int
    max_parallelism: int

    def __post_init__(self) -> None:
        canonical, micros = _parse_usd(self.max_cost_usd, "experiment.max_cost_usd")
        object.__setattr__(self, "max_cost_usd", canonical)
        if micros <= 0:
            raise SpendConfigurationError("experiment.max_cost_usd must be positive")
        _require_positive_int(self.max_requests, "experiment.max_requests")
        _require_non_negative_int(self.max_retries, "experiment.max_retries")
        if self.max_retries >= self.max_requests:
            raise SpendConfigurationError(
                "experiment.max_retries must be less than max_requests"
            )
        _require_positive_int(self.max_parallelism, "experiment.max_parallelism")

    @property
    def max_cost_microusd(self) -> int:
        return _parse_usd(self.max_cost_usd, "experiment.max_cost_usd")[1]

    def to_record(self) -> dict[str, object]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "max_requests": self.max_requests,
            "max_retries": self.max_retries,
            "max_parallelism": self.max_parallelism,
        }


@dataclass(frozen=True, slots=True)
class SpendPolicy:
    """Hash-bound sidecar policy for a complete paid experiment."""

    experiment_id: str
    executable_spec_sha256: str
    pricing_snapshot_sha256: str
    experiment: ExperimentCeiling
    solver_ceilings: tuple[SolverCeiling, ...]
    judge_ceilings: tuple[JudgeCriterionCeiling, ...]

    def __post_init__(self) -> None:
        _require_token(self.experiment_id, "experiment_id")
        _require_digest(self.executable_spec_sha256, "executable_spec_sha256")
        _require_digest(self.pricing_snapshot_sha256, "pricing_snapshot_sha256")
        if not self.solver_ceilings:
            raise SpendConfigurationError("at least one solver ceiling is required")
        solver_ids = [item.arm_id for item in self.solver_ceilings]
        if len(set(solver_ids)) != len(solver_ids):
            raise SpendConfigurationError("solver arm IDs must be unique")
        judge_ids = [(item.arm_id, item.criterion_id) for item in self.judge_ceilings]
        if len(set(judge_ids)) != len(judge_ids):
            raise SpendConfigurationError("judge criterion IDs must be unique per arm")

    def validate_before_credentials(self, pricing: PricingSnapshot | None) -> None:
        """Validate every paid path before a credential resolver may run."""

        if pricing is None:
            raise SpendConfigurationError(
                "dated pricing snapshot is required before credential resolution"
            )
        if pricing.snapshot_sha256 != self.pricing_snapshot_sha256:
            raise SpendConfigurationError(
                "pricing snapshot identity does not match the spend policy"
            )
        for ceiling in (*self.solver_ceilings, *self.judge_ceilings):
            rate = pricing.rate_for(ceiling.provider, ceiling.model)
            if not rate.usage_fields:
                raise SpendConfigurationError(
                    f"{ceiling.provider}/{ceiling.model} has no auditable usage fields"
                )
            worst_case = ceiling.worst_case_microusd(rate)
            if worst_case > ceiling.max_cost_microusd:
                raise SpendConfigurationError(
                    f"{ceiling.surface} ceiling is below one worst-case paid request"
                )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        """Load a policy sidecar without widening the frozen run contracts."""

        if (
            record.get("schema_version")
            # contract-ratchet: allow non-authoritative spend ceiling sidecar
            != "legalforecast.multiharness.spend_ceiling.v1"
        ):
            raise SpendConfigurationError("unsupported spend policy schema")
        required = {
            "schema_version",
            "experiment_id",
            "executable_spec_sha256",
            "pricing_snapshot_sha256",
            "experiment",
            "solver_ceilings",
            "judge_ceilings",
        }
        if set(record) != required:
            raise SpendConfigurationError(
                "spend policy contains unknown or missing fields"
            )

        def mapping(value: object, field_name: str) -> Mapping[str, Any]:
            if not isinstance(value, Mapping):
                raise SpendConfigurationError(f"{field_name} must be an object")
            return cast(Mapping[str, Any], value)

        def ceiling(
            value: object, field_name: str
        ) -> SolverCeiling | JudgeCriterionCeiling:
            item = mapping(value, field_name)
            invocation = mapping(
                item.get("invocation_budget"), f"{field_name}.invocation_budget"
            )
            allowed_invocation = {
                "mode",
                "argument_name",
                "argument_value_usd",
                "advertised_budget_usd",
            }
            if set(invocation) - allowed_invocation:
                raise SpendConfigurationError(
                    f"{field_name}.invocation_budget contains unknown fields"
                )
            budget = InvocationBudget(
                mode=cast(EnforcementMode, _required_str(invocation, "mode")),
                argument_name=_optional_str(invocation, "argument_name"),
                argument_value_usd=_optional_str(invocation, "argument_value_usd"),
                advertised_budget_usd=_optional_str(
                    invocation, "advertised_budget_usd"
                ),
            )
            common: dict[str, Any] = {
                "arm_id": _required_str(item, "arm_id"),
                "provider": _required_str(item, "provider"),
                "model": _required_str(item, "model"),
                "max_cost_usd": _required_str(item, "max_cost_usd"),
                "max_requests": _required_int(item, "max_requests"),
                "max_retries": _required_int(item, "max_retries"),
                "max_parallelism": _required_int(item, "max_parallelism"),
                "max_input_tokens": _required_int(item, "max_input_tokens"),
                "max_output_tokens": _required_int(item, "max_output_tokens"),
                "invocation_budget": budget,
            }
            surface = _required_str(item, "surface")
            if surface == "solver":
                if set(item) != {
                    "surface",
                    "arm_id",
                    "provider",
                    "model",
                    "max_cost_usd",
                    "max_requests",
                    "max_retries",
                    "max_parallelism",
                    "max_input_tokens",
                    "max_output_tokens",
                    "invocation_budget",
                }:
                    raise SpendConfigurationError(
                        f"{field_name} contains unknown or missing fields"
                    )
                return SolverCeiling(**common)
            if surface == "judge":
                if set(item) != {
                    "surface",
                    "arm_id",
                    "criterion_id",
                    "provider",
                    "model",
                    "max_cost_usd",
                    "max_requests",
                    "max_retries",
                    "max_parallelism",
                    "max_input_tokens",
                    "max_output_tokens",
                    "invocation_budget",
                }:
                    raise SpendConfigurationError(
                        f"{field_name} contains unknown or missing fields"
                    )
                return JudgeCriterionCeiling(
                    **common,
                    criterion_id=_required_str(item, "criterion_id"),
                )
            raise SpendConfigurationError(f"{field_name}.surface is unsupported")

        experiment = mapping(record.get("experiment"), "experiment")
        if set(experiment) != {
            "max_cost_usd",
            "max_requests",
            "max_retries",
            "max_parallelism",
        }:
            raise SpendConfigurationError(
                "experiment contains unknown or missing fields"
            )
        solver_records = record.get("solver_ceilings")
        judge_records = record.get("judge_ceilings")
        if not isinstance(solver_records, Sequence) or isinstance(
            solver_records, str | bytes
        ):
            raise SpendConfigurationError("solver_ceilings must be an array")
        if not isinstance(judge_records, Sequence) or isinstance(
            judge_records, str | bytes
        ):
            raise SpendConfigurationError("judge_ceilings must be an array")
        solver_values = cast(Sequence[object], solver_records)
        judge_values = cast(Sequence[object], judge_records)
        parsed_solver = tuple(
            cast(SolverCeiling, ceiling(item, f"solver_ceilings[{index}]"))
            for index, item in enumerate(solver_values)
        )
        parsed_judge = tuple(
            cast(JudgeCriterionCeiling, ceiling(item, f"judge_ceilings[{index}]"))
            for index, item in enumerate(judge_values)
        )
        return cls(
            experiment_id=_required_str(record, "experiment_id"),
            executable_spec_sha256=_required_str(record, "executable_spec_sha256"),
            pricing_snapshot_sha256=_required_str(record, "pricing_snapshot_sha256"),
            experiment=ExperimentCeiling(
                max_cost_usd=_required_str(experiment, "max_cost_usd"),
                max_requests=_required_int(experiment, "max_requests"),
                max_retries=_required_int(experiment, "max_retries"),
                max_parallelism=_required_int(experiment, "max_parallelism"),
            ),
            solver_ceilings=parsed_solver,
            judge_ceilings=parsed_judge,
        )

    def solver_for(self, arm_id: str) -> SolverCeiling:
        for ceiling in self.solver_ceilings:
            if ceiling.arm_id == arm_id:
                return ceiling
        raise SpendConfigurationError(f"unknown solver arm {arm_id!r}")

    def judge_for(self, arm_id: str, criterion_id: str) -> JudgeCriterionCeiling:
        for ceiling in self.judge_ceilings:
            if ceiling.arm_id == arm_id and ceiling.criterion_id == criterion_id:
                return ceiling
        raise SpendConfigurationError(
            f"unknown judge criterion {arm_id!r}/{criterion_id!r}"
        )

    def to_record(self) -> dict[str, object]:
        return {
            # contract-ratchet: allow non-authoritative spend ceiling sidecar
            "schema_version": "legalforecast.multiharness.spend_ceiling.v1",
            "experiment_id": self.experiment_id,
            "executable_spec_sha256": self.executable_spec_sha256,
            "pricing_snapshot_sha256": self.pricing_snapshot_sha256,
            "experiment": self.experiment.to_record(),
            "solver_ceilings": [item.to_record() for item in self.solver_ceilings],
            "judge_ceilings": [item.to_record() for item in self.judge_ceilings],
        }

    @property
    def policy_sha256(self) -> str:
        """Canonical digest of every ceiling this policy actually enforces.

        The detached approval only binds the executable spec, so the spec must
        be able to pin this sidecar in turn.  Without that second binding an
        operator could raise the request and dollar ceilings after approval and
        still satisfy every remaining identity check.  ``from_record`` rejects
        unknown and missing fields, so the canonical round trip is exact and
        this digest is a total function of the sidecar's enforced content.
        """

        return _record_sha256(self.to_record())


@dataclass(frozen=True, slots=True)
class PaidCall:
    """Identity supplied to the controller immediately before a paid call."""

    call_id: str
    surface: Surface
    arm_id: str
    provider: str
    model: str
    executable_spec_sha256: str
    pricing_snapshot_sha256: str
    attempt_index: int = 0
    criterion_id: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.call_id, "call_id")
        _require_token(self.arm_id, "arm_id")
        _require_token(self.provider, "provider")
        _require_token(self.model, "model")
        _require_digest(self.executable_spec_sha256, "executable_spec_sha256")
        _require_digest(self.pricing_snapshot_sha256, "pricing_snapshot_sha256")
        _require_non_negative_int(self.attempt_index, "attempt_index")
        if self.surface == "judge":
            if self.criterion_id is None:
                raise SpendConfigurationError("judge calls require criterion_id")
            _require_token(self.criterion_id, "criterion_id")
        elif self.surface == "solver":
            if self.criterion_id is not None:
                raise SpendConfigurationError("solver calls cannot set criterion_id")
        else:
            raise SpendConfigurationError("surface must be solver or judge")


@dataclass(frozen=True, slots=True)
class UsageObservation:
    """Provider usage/cost observation; unknown costs remain nonnumeric."""

    basis: str
    pricing_snapshot_sha256: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reported_cost_usd: str | None = None
    unknown_reason: str | None = None

    def __post_init__(self) -> None:
        allowed = {
            "provider_reported",
            "estimated_from_pricing_snapshot",
            "subscription_unallocable",
            "unknown",
        }
        if self.basis not in allowed:
            raise SpendSettlementError("unsupported usage basis")
        for value, name in (
            (self.input_tokens, "input_tokens"),
            (self.output_tokens, "output_tokens"),
        ):
            if value is not None:
                _require_non_negative_int(value, name)
        if self.reported_cost_usd is not None:
            _parse_usd(self.reported_cost_usd, "reported_cost_usd")
        if self.basis in {"unknown", "subscription_unallocable"}:
            if self.reported_cost_usd is not None:
                raise SpendSettlementError("unknown cost must remain nonnumeric")
            if not self.unknown_reason:
                raise SpendSettlementError("unknown cost requires unknown_reason")
        else:
            if self.pricing_snapshot_sha256 is None:
                raise SpendSettlementError(
                    "numeric usage requires pricing snapshot identity"
                )
            _require_digest(self.pricing_snapshot_sha256, "pricing_snapshot_sha256")
            if self.input_tokens is None or self.output_tokens is None:
                raise SpendSettlementError(
                    "numeric usage requires auditable input and output tokens"
                )

    @classmethod
    def unknown(cls, reason: str, *, subscription: bool = False) -> Self:
        return cls(
            basis="subscription_unallocable" if subscription else "unknown",
            unknown_reason=reason,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "basis": self.basis,
            "pricing_snapshot_sha256": self.pricing_snapshot_sha256,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reported_cost_usd": self.reported_cost_usd,
            "unknown_reason": self.unknown_reason,
        }


@dataclass(frozen=True, slots=True)
class SpendEvidence:
    """Durable decision/settlement evidence for an archive sidecar."""

    decision: str
    call_id: str
    surface: Surface
    arm_id: str
    criterion_id: str | None
    attempt_index: int
    executable_spec_sha256: str
    pricing_snapshot_sha256: str
    failure_class: str | None
    terminal: bool
    reason: str
    max_cost_usd: str | None = None
    reserved_cost_usd: str | None = None
    observed_cost_usd: str | None = None
    unknown_reason: str | None = None

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "decision": self.decision,
            "call_id": self.call_id,
            "surface": self.surface,
            "arm_id": self.arm_id,
            "criterion_id": self.criterion_id,
            "attempt_index": self.attempt_index,
            "executable_spec_sha256": self.executable_spec_sha256,
            "pricing_snapshot_sha256": self.pricing_snapshot_sha256,
            "failure_class": self.failure_class,
            "terminal": self.terminal,
            "reason": self.reason,
            "max_cost_usd": self.max_cost_usd,
            "reserved_cost_usd": self.reserved_cost_usd,
            "observed_cost_usd": self.observed_cost_usd,
            "unknown_reason": self.unknown_reason,
        }
        return record


@dataclass(frozen=True, slots=True)
class SpendReservation:
    """Pre-call reservation returned only after all ceilings allow a call."""

    reservation_id: str
    call: PaidCall
    worst_case_cost_usd: str
    max_cost_usd: str
    sequence: int

    def to_record(self) -> dict[str, object]:
        return {
            "reservation_id": self.reservation_id,
            "call": {
                "call_id": self.call.call_id,
                "surface": self.call.surface,
                "arm_id": self.call.arm_id,
                "criterion_id": self.call.criterion_id,
                "provider": self.call.provider,
                "model": self.call.model,
                "attempt_index": self.call.attempt_index,
                "executable_spec_sha256": self.call.executable_spec_sha256,
                "pricing_snapshot_sha256": self.call.pricing_snapshot_sha256,
            },
            "worst_case_cost_usd": self.worst_case_cost_usd,
            "max_cost_usd": self.max_cost_usd,
            "sequence": self.sequence,
        }


@dataclass(slots=True)
class _ScopeState:
    requests: int = 0
    retries: int = 0
    active: int = 0
    reserved_microusd: int = 0
    spent_microusd: int = 0


class SpendController:
    """Thread-safe pre-call budget controller with durable denial evidence."""

    def __init__(self, policy: SpendPolicy, pricing: PricingSnapshot | None) -> None:
        policy.validate_before_credentials(pricing)
        assert pricing is not None
        self.policy = policy
        self.pricing = pricing
        self._lock = threading.RLock()
        self._states: dict[tuple[str, str, str | None], _ScopeState] = {}
        self._active: dict[str, tuple[tuple[str, str, str | None], int]] = {}
        self._events: list[SpendEvidence] = []
        self._sequence = 0
        self._spent_microusd = 0
        self._observed_microusd = 0
        self._reserved_microusd = 0
        self._requests = 0
        self._retries = 0
        self._active_count = 0
        self._terminal_reason: str | None = None
        self._unknown_cost_reason: str | None = None

    @property
    def terminal(self) -> bool:
        return self._terminal_reason is not None

    @property
    def events(self) -> tuple[SpendEvidence, ...]:
        with self._lock:
            return tuple(self._events)

    def reserve(self, call: PaidCall) -> SpendReservation:
        """Reserve worst-case cost, or raise before any provider invocation."""

        with self._lock:
            if self._terminal_reason is not None:
                evidence = self._deny(
                    call,
                    SpendFailureClass.OVER_BUDGET,
                    self._terminal_reason,
                    terminal=True,
                )
                raise SpendDeniedError(evidence)
            ceiling = self._ceiling_for(call)
            if call.executable_spec_sha256 != self.policy.executable_spec_sha256:
                evidence = self._deny(
                    call,
                    SpendFailureClass.SPEC_MISMATCH,
                    "paid call does not match executable specification",
                    terminal=True,
                    max_cost_usd=ceiling.max_cost_usd,
                )
                raise SpendDeniedError(evidence)
            if call.pricing_snapshot_sha256 != self.policy.pricing_snapshot_sha256:
                evidence = self._deny(
                    call,
                    SpendFailureClass.PRICING_MISMATCH,
                    "paid call does not match dated pricing snapshot",
                    terminal=True,
                    max_cost_usd=ceiling.max_cost_usd,
                )
                raise SpendDeniedError(evidence)
            if (call.provider, call.model) != (ceiling.provider, ceiling.model):
                evidence = self._deny(
                    call,
                    SpendFailureClass.IDENTITY_MISMATCH,
                    "paid call provider/model differs from the executable policy",
                    terminal=True,
                    max_cost_usd=ceiling.max_cost_usd,
                )
                raise SpendDeniedError(evidence)
            rate = self.pricing.rate_for(call.provider, call.model)
            worst_case = ceiling.worst_case_microusd(rate)
            scope_key = (call.surface, call.arm_id, call.criterion_id)
            state = self._states.setdefault(scope_key, _ScopeState())
            denial = self._check_caps(call, ceiling, state, worst_case)
            if denial is not None:
                evidence = self._deny(
                    call,
                    denial[0],
                    denial[1],
                    terminal=denial[2],
                    max_cost_usd=ceiling.max_cost_usd,
                )
                if denial[2] and denial[0] == SpendFailureClass.OVER_BUDGET:
                    self._terminal_reason = denial[1]
                raise SpendDeniedError(evidence)
            self._sequence += 1
            reservation_id = f"reservation-{self._sequence:06d}"
            state.requests += 1
            state.retries += int(call.attempt_index > 0)
            state.active += 1
            state.reserved_microusd += worst_case
            self._active[reservation_id] = (scope_key, worst_case)
            self._reserved_microusd += worst_case
            self._requests += 1
            self._retries += int(call.attempt_index > 0)
            self._active_count += 1
            return SpendReservation(
                reservation_id=reservation_id,
                call=call,
                worst_case_cost_usd=_usd_from_microusd(worst_case),
                max_cost_usd=ceiling.max_cost_usd,
                sequence=self._sequence,
            )

    def settle(
        self,
        reservation: SpendReservation,
        observation: UsageObservation,
    ) -> SpendEvidence:
        """Settle one reservation and retain unknown/terminal evidence."""

        with self._lock:
            active = self._active.pop(reservation.reservation_id, None)
            if active is None:
                raise SpendSettlementError("reservation is unknown or already settled")
            scope_key, reserved = active
            state = self._states[scope_key]
            state.active -= 1
            state.reserved_microusd -= reserved
            self._reserved_microusd -= reserved
            self._active_count -= 1
            call = reservation.call
            ceiling = self._ceiling_for(call)
            if observation.basis in {"unknown", "subscription_unallocable"}:
                failure = (
                    SpendFailureClass.SUBSCRIPTION_UNALLOCABLE
                    if observation.basis == "subscription_unallocable"
                    else SpendFailureClass.UNKNOWN_COST
                )
                reason = observation.unknown_reason or "paid cost is not allocable"
                self._terminal_reason = reason
                self._unknown_cost_reason = reason
                self._settled(
                    call,
                    ceiling,
                    failure_class=failure,
                    terminal=True,
                    reason=reason,
                    reserved=reserved,
                    unknown_reason=observation.unknown_reason,
                )
                raise SpendSettlementError(reason)
            if (
                observation.pricing_snapshot_sha256
                != self.policy.pricing_snapshot_sha256
            ):
                self._terminal_reason = "numeric usage has the wrong pricing snapshot"
                evidence = self._settled(
                    call,
                    ceiling,
                    failure_class=SpendFailureClass.PRICING_MISMATCH,
                    terminal=True,
                    reason=self._terminal_reason,
                    reserved=reserved,
                )
                raise SpendSettlementError(evidence.reason)
            assert observation.input_tokens is not None
            assert observation.output_tokens is not None
            rate = self.pricing.rate_for(call.provider, call.model)
            estimated = rate.worst_case_microusd(
                input_tokens=observation.input_tokens,
                output_tokens=observation.output_tokens,
            )
            actual = (
                _parse_usd(observation.reported_cost_usd, "reported_cost_usd")[1]
                if observation.reported_cost_usd is not None
                else estimated
            )
            self._observed_microusd += actual
            if actual > ceiling.max_cost_microusd or (
                self._spent_microusd + actual > self.policy.experiment.max_cost_microusd
            ):
                self._terminal_reason = "observed paid cost exceeded a hard ceiling"
                evidence = self._settled(
                    call,
                    ceiling,
                    failure_class=SpendFailureClass.OVER_BUDGET,
                    terminal=True,
                    reason=self._terminal_reason,
                    reserved=reserved,
                    observed=actual,
                )
                raise SpendSettlementError(evidence.reason)
            self._spent_microusd += actual
            state.spent_microusd += actual
            return self._settled(
                call,
                ceiling,
                failure_class=None,
                terminal=False,
                reason="paid call settled",
                reserved=reserved,
                observed=actual,
            )

    def archive_record(self) -> dict[str, object]:
        """Return a reproducible non-authoritative archive sidecar."""

        with self._lock:
            return {
                # contract-ratchet: allow non-authoritative spend archive sidecar
                "schema_version": "legalforecast.multiharness.spend_ceiling.v1",
                "experiment_id": self.policy.experiment_id,
                "executable_spec_sha256": self.policy.executable_spec_sha256,
                "pricing_snapshot": self.pricing.to_record(),
                "policy": self.policy.to_record(),
                "terminal": self.terminal,
                "terminal_reason": self._terminal_reason,
                # A numeric zero would falsely turn a timeout or subscription
                # into a dollar ceiling.  Preserve nonnumeric cost state.
                "spent_usd": (
                    None
                    if self._unknown_cost_reason is not None
                    else _usd_from_microusd(self._spent_microusd)
                ),
                "observed_cost_usd": (
                    None
                    if self._unknown_cost_reason is not None
                    else _usd_from_microusd(self._observed_microusd)
                ),
                "cost_unknown_reason": self._unknown_cost_reason,
                "reserved_usd": _usd_from_microusd(self._reserved_microusd),
                "requests": self._requests,
                "retries": self._retries,
                "active": self._active_count,
                "events": [event.to_record() for event in self._events],
            }

    def _ceiling_for(self, call: PaidCall) -> _CallCeiling:
        if call.surface == "solver":
            return self.policy.solver_for(call.arm_id)
        assert call.criterion_id is not None
        return self.policy.judge_for(call.arm_id, call.criterion_id)

    def _check_caps(
        self,
        call: PaidCall,
        ceiling: _CallCeiling,
        state: _ScopeState,
        worst_case: int,
    ) -> tuple[SpendFailureClass, str, bool] | None:
        if (
            state.active >= ceiling.max_parallelism
            or self._active_count >= self.policy.experiment.max_parallelism
        ):
            return (
                SpendFailureClass.PARALLELISM_CAP,
                "paid call would exceed parallelism cap",
                False,
            )
        if state.requests >= ceiling.max_requests:
            return (
                SpendFailureClass.REQUEST_CAP,
                "paid call would exceed request cap",
                True,
            )
        if call.attempt_index > ceiling.max_retries:
            return (
                SpendFailureClass.RETRY_CAP,
                "paid call would exceed retry cap",
                True,
            )
        if self._requests >= self.policy.experiment.max_requests:
            return (
                SpendFailureClass.REQUEST_CAP,
                "paid call would exceed experiment request cap",
                True,
            )
        if (
            self._retries >= self.policy.experiment.max_retries
            and call.attempt_index > 0
        ):
            return (
                SpendFailureClass.RETRY_CAP,
                "paid call would exceed experiment retry cap",
                True,
            )
        if (
            state.spent_microusd + state.reserved_microusd + worst_case
            > ceiling.max_cost_microusd
        ):
            return (
                SpendFailureClass.OVER_BUDGET,
                "paid call would exceed per-scope dollar ceiling",
                True,
            )
        if (
            self._spent_microusd + self._reserved_microusd + worst_case
            > self.policy.experiment.max_cost_microusd
        ):
            return (
                SpendFailureClass.OVER_BUDGET,
                "paid call would exceed experiment-wide dollar ceiling",
                True,
            )
        return None

    def _deny(
        self,
        call: PaidCall,
        failure_class: SpendFailureClass,
        reason: str,
        *,
        terminal: bool,
        max_cost_usd: str | None = None,
    ) -> SpendEvidence:
        evidence = SpendEvidence(
            decision="denied",
            call_id=call.call_id,
            surface=call.surface,
            arm_id=call.arm_id,
            criterion_id=call.criterion_id,
            attempt_index=call.attempt_index,
            executable_spec_sha256=call.executable_spec_sha256,
            pricing_snapshot_sha256=call.pricing_snapshot_sha256,
            failure_class=failure_class.value,
            terminal=terminal,
            reason=reason,
            max_cost_usd=max_cost_usd,
        )
        self._events.append(evidence)
        return evidence

    def _settled(
        self,
        call: PaidCall,
        ceiling: _CallCeiling,
        *,
        failure_class: SpendFailureClass | None,
        terminal: bool,
        reason: str,
        reserved: int,
        observed: int | None = None,
        unknown_reason: str | None = None,
    ) -> SpendEvidence:
        evidence = SpendEvidence(
            decision="settled",
            call_id=call.call_id,
            surface=call.surface,
            arm_id=call.arm_id,
            criterion_id=call.criterion_id,
            attempt_index=call.attempt_index,
            executable_spec_sha256=call.executable_spec_sha256,
            pricing_snapshot_sha256=call.pricing_snapshot_sha256,
            failure_class=None if failure_class is None else failure_class.value,
            terminal=terminal,
            reason=reason,
            max_cost_usd=ceiling.max_cost_usd,
            reserved_cost_usd=_usd_from_microusd(reserved),
            observed_cost_usd=None
            if observed is None
            else _usd_from_microusd(observed),
            unknown_reason=unknown_reason,
        )
        self._events.append(evidence)
        return evidence


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value:
        raise SpendConfigurationError(f"{field_name} must be a non-empty string")
    return value


def _required_field_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise SpendConfigurationError(f"{field_name} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is not None and (not isinstance(value, str) or not value):
        raise SpendConfigurationError(f"{field_name} must be a non-empty string")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int:
        raise SpendConfigurationError(f"{field_name} must be an integer")
    return value


def _optional_int(record: Mapping[str, Any], field_name: str, *, default: int) -> int:
    value = record.get(field_name, default)
    if type(value) is not int:
        raise SpendConfigurationError(f"{field_name} must be an integer")
    return value


__all__ = [
    "ExperimentCeiling",
    "InvocationBudget",
    "JudgeCriterionCeiling",
    "PaidCall",
    "PricingRate",
    "PricingSnapshot",
    "SolverCeiling",
    "SpendConfigurationError",
    "SpendController",
    "SpendDeniedError",
    "SpendEvidence",
    "SpendFailureClass",
    "SpendPolicy",
    "SpendReservation",
    "SpendSettlementError",
    "UsageObservation",
]

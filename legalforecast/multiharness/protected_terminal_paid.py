"""Protected paid execution primitives for the Claude terminal treatment.

The public ``release-run`` command stays provider-free by default.  A future
protected workflow may opt into this module after the native Claude sandbox
probe succeeds.  The workflow supplies the existing GitHub Environment secret
and AWS OIDC-backed DynamoDB authority; this module does not accept a free-form
approval string and never falls back to Infisical or an ambient credential.

The execution service that owns the child boundary should call
``ProtectedSpendController.execute`` immediately around one CLI attempt.  The
controller reserves before the child starts and records either validated usage
or an ambiguous failure.  An ambiguous failure intentionally retains the
reservation for later reconciliation.
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final, Protocol

from legalforecast.evals.provider_spend_control import (
    AttemptLease,
    FrozenAttemptPolicy,
    ProviderSpendAuthority,
    ProviderSpendKey,
)
from legalforecast.evals.provider_spend_dynamodb import DynamoDbProviderSpendAuthority
from legalforecast.multiharness.auth_profiles import (
    PUBLISHED_API_KEY,
    AuthProfileError,
    ResolvedAuthProfile,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_environment import CredentialSource

UPSTREAM_API_KEY_ENV: Final[str] = "LFB_MODEL_GATEWAY_UPSTREAM_API_KEY"
PROTECTED_WORKFLOW_MARKER: Final[str] = "LFB_PROTECTED_TERMINAL_RELEASE"
PROTECTED_WORKFLOW_MARKER_VALUE: Final[str] = "1"
PROTECTED_ANTHROPIC_ENV: Final[str] = "ANTHROPIC_API_KEY"
PROTECTED_AUTHORITY_TABLE_ENV: Final[str] = "LFB_PROVIDER_AUTHORITY_TABLE"
PROTECTED_AUTHORITY_REGION_ENV: Final[str] = "LFB_AWS_REGION"
PROTECTED_AUTHORITY_RESOURCE_ENV: Final[str] = (
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256"
)


class ProtectedTerminalPaidError(RuntimeError):
    """Raised when protected paid execution is not authorized or reconcilable."""


class GatewaySpendController(Protocol):
    """Contract implemented by the bounded gateway request handler."""

    def authorize_request(
        self,
        *,
        request_id: str,
        body: bytes,
        model: str,
        max_tokens: int,
    ) -> object:
        """Reserve before forwarding a validated request upstream."""
        raise NotImplementedError

    def settle_response(
        self,
        lease: object,
        *,
        response_body: bytes,
        response_status: int,
        content_type: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        """Return false when bounded charge evidence is unavailable."""
        raise NotImplementedError

    def record_failure(
        self,
        lease: object,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        """Record failure without releasing uncertain provider spend."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class GitHubEnvironmentCredentialSource(CredentialSource):
    """Project only the Anthropic secret injected by the protected workflow.

    ``parent_env`` is injectable for tests, but production callers must pass
    the process environment created by the GitHub Environment job.  The
    marker is deliberately an additional fail-closed check: local commands do
    not become paid merely because a developer has an Anthropic key set.
    """

    parent_env: Mapping[str, str] | None = None

    def fetch_projected_env(
        self,
        profile: ResolvedAuthProfile,
    ) -> Mapping[str, str]:
        if profile.profile_id != PUBLISHED_API_KEY:
            raise AuthProfileError(
                "protected terminal credentials require published-api-key"
            )
        if profile.projected_env_vars != (PROTECTED_ANTHROPIC_ENV,):
            raise AuthProfileError(
                "protected terminal credentials allow only ANTHROPIC_API_KEY"
            )
        environment = os.environ if self.parent_env is None else self.parent_env
        try:
            _require_protected_workflow(environment, "terminal credentials")
        except ProtectedTerminalPaidError as exc:
            raise AuthProfileError(str(exc)) from exc
        value = environment.get(PROTECTED_ANTHROPIC_ENV)
        if not value:
            raise AuthProfileError("protected terminal credentials are unavailable")
        return {PROTECTED_ANTHROPIC_ENV: value}


@dataclass(frozen=True, slots=True)
class GitHubEnvironmentGatewayCredentialSource:
    """Project the GitHub Environment key into the gateway sidecar only."""

    parent_env: Mapping[str, str] | None = None

    def upstream_environment(self) -> Mapping[str, str]:
        """Return the sidecar-only key name without exposing it to the harness."""

        environment = os.environ if self.parent_env is None else self.parent_env
        _require_protected_workflow(environment, "gateway credentials")
        value = environment.get(PROTECTED_ANTHROPIC_ENV)
        if not value:
            raise ProtectedTerminalPaidError(
                "protected gateway credentials are unavailable"
            )
        return {UPSTREAM_API_KEY_ENV: value}


@dataclass(frozen=True, slots=True)
class ProtectedTerminalSpendConfig:
    """Immutable identity and cap inputs for one protected terminal run."""

    cycle_id: str
    account: str
    model_key: str
    ceiling_microusd: int
    authority_identity_sha256: str
    reservation_ledger_sha256: str
    provider_authority_table: str
    provider_authority_region: str
    provider_authority_resource_identity_sha256: str
    stage: str = "official"
    ablation: str = "none"
    repeat_index: int = 1

    def __post_init__(self) -> None:
        _non_empty(self.cycle_id, "cycle_id")
        _non_empty(self.account, "account")
        if not self.model_key.startswith("anthropic:"):
            raise ProtectedTerminalPaidError(
                "protected terminal paid execution requires an Anthropic model key"
            )
        _positive_int(self.ceiling_microusd, "ceiling_microusd")
        _sha256(self.authority_identity_sha256, "authority_identity_sha256")
        _sha256(self.reservation_ledger_sha256, "reservation_ledger_sha256")
        _non_empty(self.provider_authority_table, "provider_authority_table")
        _non_empty(self.provider_authority_region, "provider_authority_region")
        _sha256(
            self.provider_authority_resource_identity_sha256,
            "provider_authority_resource_identity_sha256",
        )
        _non_empty(self.stage, "stage")
        _non_empty(self.ablation, "ablation")
        _positive_int(self.repeat_index, "repeat_index")

    def key_for(self, spec: RunSpec) -> ProviderSpendKey:
        """Bind one CLI spec to a durable provider-spend logical cell."""

        return ProviderSpendKey(
            cycle_id=self.cycle_id,
            provider="anthropic",
            account=self.account,
            stage=self.stage,
            model_key=self.model_key,
            case_id=spec.spec_id,
            ablation=self.ablation,
            repeat_index=self.repeat_index,
        )

    def key_for_gateway_request(
        self,
        request_id: str,
        request_ordinal: int,
    ) -> ProviderSpendKey:
        """Bind each recursive CLI/Bash gateway request to its own cell."""

        _non_empty(request_id, "request_id")
        _positive_int(request_ordinal, "request_ordinal")
        return ProviderSpendKey(
            cycle_id=self.cycle_id,
            provider="anthropic",
            account=self.account,
            stage=self.stage,
            model_key=self.model_key,
            case_id=f"{request_id}:gateway:{request_ordinal}",
            ablation=self.ablation,
            repeat_index=self.repeat_index,
        )


def build_dynamodb_spend_authority(
    config: ProtectedTerminalSpendConfig,
    *,
    max_billable_attempts: int = 1,
    failure_threshold: int = 8,
    failure_window_seconds: int = 86_400,
) -> ProviderSpendAuthority:
    """Construct the existing remote authority without reading any secret.

    Construction performs the authority's table identity and ledger checks.
    Callers must invoke this only inside the protected GitHub Environment job
    after OIDC credentials have been configured.
    """

    table, region, resource = protected_authority_environment()
    if (
        table != config.provider_authority_table
        or region != config.provider_authority_region
        or resource != config.provider_authority_resource_identity_sha256
    ):
        raise ProtectedTerminalPaidError(
            "protected authority configuration does not match the workflow"
        )

    policy = FrozenAttemptPolicy(
        reservation_ledger_sha256=config.reservation_ledger_sha256,
        max_billable_attempts=max_billable_attempts,
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window_seconds,
    )
    return DynamoDbProviderSpendAuthority(
        table_name=config.provider_authority_table,
        authority_identity_sha256=config.authority_identity_sha256,
        resource_identity_sha256=config.provider_authority_resource_identity_sha256,
        cycle_id=config.cycle_id,
        provider="anthropic",
        account=config.account,
        cap_microusd=config.ceiling_microusd,
        policy=policy,
        region=config.provider_authority_region,
    )


def uniform_case_reservation_microusd(
    ceiling_microusd: int,
    case_count: int,
) -> int:
    """Return a positive per-case hold that cannot exceed the run ceiling."""

    _positive_int(ceiling_microusd, "ceiling_microusd")
    _positive_int(case_count, "case_count")
    if ceiling_microusd < case_count:
        raise ProtectedTerminalPaidError(
            "ceiling_microusd must cover at least one micro-dollar per case"
        )
    return ceiling_microusd // case_count


@dataclass(slots=True)
class ProtectedSpendController:
    """Reserve and settle one protected local-CLI provider attempt."""

    authority: ProviderSpendAuthority
    config: ProtectedTerminalSpendConfig
    reservation_microusd: int
    _key_for_spec: Callable[[RunSpec], ProviderSpendKey] | None = None

    def __post_init__(self) -> None:
        _positive_int(self.reservation_microusd, "reservation_microusd")
        if self.reservation_microusd > self.config.ceiling_microusd:
            raise ProtectedTerminalPaidError(
                "reservation_microusd cannot exceed ceiling_microusd"
            )

    def execute(
        self,
        spec: RunSpec,
        delegate: Callable[[RunSpec], ExecutionReceipt],
    ) -> ExecutionReceipt:
        """Authorize, execute, and durably reconcile one CLI invocation."""

        key = self.key_for_spec(spec)
        lease = self.authority.authorize_attempt(
            key,
            reservation_microusd=self.reservation_microusd,
        )
        try:
            receipt = delegate(spec)
        except BaseException:
            self.authority.record_failure(
                lease,
                failure_type="terminal_exception",
                ambiguous=True,
            )
            raise
        if receipt.status == "succeeded":
            self._settle_success(lease, receipt)
        else:
            # Once the child was launched, a non-success receipt cannot prove
            # that no provider request was accepted. Preserve the reservation
            # for the existing reconciliation path instead of releasing it.
            self.authority.record_failure(
                lease,
                failure_type="terminal_receipt_failed",
                ambiguous=True,
            )
        return receipt

    def key_for_spec(self, spec: RunSpec) -> ProviderSpendKey:
        if self._key_for_spec is not None:
            return self._key_for_spec(spec)
        return self.config.key_for(spec)

    def _settle_success(
        self,
        lease: AttemptLease,
        receipt: ExecutionReceipt,
    ) -> None:
        if receipt.cost_usd is None or not math.isfinite(receipt.cost_usd):
            self.authority.record_failure(
                lease,
                failure_type="terminal_receipt_missing_cost",
                ambiguous=True,
            )
            return
        try:
            input_tokens = _usage_token_count(receipt.usage, "input_tokens")
            output_tokens = _usage_token_count(receipt.usage, "output_tokens")
        except ProtectedTerminalPaidError:
            self.authority.record_failure(
                lease,
                failure_type="terminal_receipt_missing_usage",
                ambiguous=True,
            )
            return
        actual_microusd = math.ceil(receipt.cost_usd * 1_000_000)
        response_sha256 = hashlib.sha256(receipt.stdout.encode("utf-8")).hexdigest()
        self.authority.record_response(
            lease,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_microusd=actual_microusd,
            response_sha256=response_sha256,
        )


GatewayChargeExtractor = Callable[
    [bytes, int, str | None],
    int | None,
]


@dataclass(frozen=True, slots=True)
class GatewaySpendLease:
    """One gateway request's durable provider-attempt lease."""

    lease: AttemptLease
    request_id: str


@dataclass(slots=True)
class ProviderGatewaySpendController(GatewaySpendController):
    """DynamoDB spend control for every accepted gateway request.

    The gateway calls this object after request validation and before its
    upstream HTTP request.  ``charge_extractor`` must return a provider charge
    in micro-USD from bounded gateway evidence.  Missing charge or usage
    evidence is retained as ambiguous instead of being treated as zero.
    """

    authority: ProviderSpendAuthority
    config: ProtectedTerminalSpendConfig
    reservation_microusd: int
    charge_extractor: GatewayChargeExtractor
    _request_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _request_ordinal: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        _positive_int(self.reservation_microusd, "reservation_microusd")
        if self.reservation_microusd > self.config.ceiling_microusd:
            raise ProtectedTerminalPaidError(
                "reservation_microusd cannot exceed ceiling_microusd"
            )
        if not callable(self.charge_extractor):
            raise ProtectedTerminalPaidError("charge_extractor must be callable")

    def authorize_request(
        self,
        *,
        request_id: str,
        body: bytes,
        model: str,
        max_tokens: int,
    ) -> GatewaySpendLease:
        del body, model, max_tokens
        with self._request_lock:
            self._request_ordinal += 1
            ordinal = self._request_ordinal
        key = self.config.key_for_gateway_request(request_id, ordinal)
        lease = self.authority.authorize_attempt(
            key,
            reservation_microusd=self.reservation_microusd,
        )
        return GatewaySpendLease(lease=lease, request_id=request_id)

    def settle_response(
        self,
        lease: object,
        *,
        response_body: bytes,
        response_status: int,
        content_type: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        if not isinstance(lease, GatewaySpendLease):
            raise ProtectedTerminalPaidError("gateway spend lease has the wrong type")
        if response_status < 200 or response_status >= 300:
            self.record_failure(
                lease,
                failure_type="gateway_upstream_error",
                ambiguous=True,
            )
            return False
        if input_tokens is None or output_tokens is None:
            self.record_failure(
                lease,
                failure_type="gateway_usage_missing",
                ambiguous=True,
            )
            return False
        actual_microusd = self.charge_extractor(
            response_body,
            response_status,
            content_type,
        )
        if actual_microusd is None or actual_microusd < 0:
            self.record_failure(
                lease,
                failure_type="gateway_charge_missing",
                ambiguous=True,
            )
            return False
        response_sha256 = hashlib.sha256(response_body).hexdigest()
        self.authority.record_response(
            lease.lease,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_microusd=actual_microusd,
            response_sha256=response_sha256,
        )
        return True

    def record_failure(
        self,
        lease: object,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        if not isinstance(lease, GatewaySpendLease):
            raise ProtectedTerminalPaidError("gateway spend lease has the wrong type")
        self.authority.record_failure(
            lease.lease,
            failure_type=failure_type,
            ambiguous=ambiguous,
        )


def protected_authority_environment(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, str, str]:
    """Read the existing protected authority identity without secret values."""

    source = os.environ if environment is None else environment
    _require_protected_workflow(source, "terminal authority")
    table = source.get(PROTECTED_AUTHORITY_TABLE_ENV, "")
    region = source.get(PROTECTED_AUTHORITY_REGION_ENV, "")
    resource = source.get(PROTECTED_AUTHORITY_RESOURCE_ENV, "")
    values = (table, region, resource)
    if any(not value for value in values):
        raise ProtectedTerminalPaidError(
            "protected terminal authority configuration is incomplete"
        )
    return table, region, resource


def _require_protected_workflow(
    environment: Mapping[str, str],
    description: str,
) -> None:
    if environment.get("GITHUB_ACTIONS") != "true":
        raise ProtectedTerminalPaidError(
            f"protected {description} requires GitHub Actions"
        )
    if environment.get(PROTECTED_WORKFLOW_MARKER) != PROTECTED_WORKFLOW_MARKER_VALUE:
        raise ProtectedTerminalPaidError(
            f"protected {description} requires the official workflow marker"
        )


def _usage_token_count(usage: Mapping[str, int], name: str) -> int:
    value = usage.get(name)
    if type(value) is not int or value < 0:
        raise ProtectedTerminalPaidError(
            f"successful terminal receipt lacks non-negative {name}"
        )
    return value


def _non_empty(value: str, name: str) -> None:
    if not value.strip():
        raise ProtectedTerminalPaidError(f"{name} must be non-empty")


def _positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ProtectedTerminalPaidError(f"{name} must be a positive integer")


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ProtectedTerminalPaidError(f"{name} must be a lowercase SHA-256")


__all__ = [
    "PROTECTED_ANTHROPIC_ENV",
    "PROTECTED_AUTHORITY_REGION_ENV",
    "PROTECTED_AUTHORITY_RESOURCE_ENV",
    "PROTECTED_AUTHORITY_TABLE_ENV",
    "PROTECTED_WORKFLOW_MARKER",
    "PROTECTED_WORKFLOW_MARKER_VALUE",
    "UPSTREAM_API_KEY_ENV",
    "GatewayChargeExtractor",
    "GatewaySpendController",
    "GatewaySpendLease",
    "GitHubEnvironmentCredentialSource",
    "GitHubEnvironmentGatewayCredentialSource",
    "ProtectedSpendController",
    "ProtectedTerminalPaidError",
    "ProtectedTerminalSpendConfig",
    "ProviderGatewaySpendController",
    "build_dynamodb_spend_authority",
    "protected_authority_environment",
    "uniform_case_reservation_microusd",
]

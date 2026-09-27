"""Bind externally verified hard-stop evidence to the actual solver credential.

This does not provision or independently attest a provider limit. The operator
must retain the referenced provider evidence privately. A billing alert, a
turn limit, or a locally declared number is not an eligible hard stop. The
whole provider limit, not a possibly delayed remaining-balance observation,
must fit the run ceiling and remain non-renewing for the complete run window.
"""

from __future__ import annotations

import hmac
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.multiharness.auth_profiles import ResolvedAuthProfile
from legalforecast.multiharness.local_cli_environment import CredentialSource


class ProviderCapError(ValueError):
    """Cap evidence is absent, stale, incompatible, or for another credential."""


@dataclass(frozen=True, slots=True)
class ProviderSpendCap:
    provider: str
    auth_profile: str
    credential_env_var: str
    credential_sha256: str
    hard_limit_usd: str
    observed_at: str
    enforced_until: str
    enforcement: str
    evidence_reference: str

    def __post_init__(self) -> None:
        if self.enforcement != "hard_stop_no_auto_recharge":
            raise ProviderCapError(
                "provider cap must be a hard stop without auto recharge"
            )
        if self.auth_profile != "published-api-key":
            raise ProviderCapError("provider cap requires a published API key profile")
        if not self.provider.strip() or not self.evidence_reference.strip():
            raise ProviderCapError(
                "provider cap requires provider and evidence reference"
            )
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.credential_env_var):
            raise ProviderCapError(
                "provider cap credential environment name is invalid"
            )
        if not is_lowercase_sha256(self.credential_sha256):
            raise ProviderCapError(
                "provider cap requires the exact credential fingerprint"
            )
        try:
            amount = Decimal(self.hard_limit_usd)
            exponent = amount.as_tuple().exponent
            if (
                not amount.is_finite()
                or amount <= 0
                or not isinstance(exponent, int)
                or exponent < -6
            ):
                raise ValueError
            start = datetime.fromisoformat(self.observed_at)
            end = datetime.fromisoformat(self.enforced_until)
            if start.utcoffset() is None or end.utcoffset() is None or end <= start:
                raise ValueError
        except (ValueError, InvalidOperation) as exc:
            raise ProviderCapError(
                "provider cap requires a positive USD limit and dated window"
            ) from exc

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> ProviderSpendCap:
        if set(record) != set(cls.__dataclass_fields__) or not all(
            isinstance(value, str) for value in record.values()
        ):
            raise ProviderCapError(
                "provider cap has missing, unknown, or non-string fields"
            )
        return cls(**{key: str(value) for key, value in record.items()})

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    def validate_compatibility(
        self,
        *,
        provider: str,
        auth_profile: str,
        max_cost_usd: str,
    ) -> None:
        """Check immutable identities and ceiling without consulting the clock."""

        if provider != self.provider or auth_profile != self.auth_profile:
            raise ProviderCapError(
                "provider cap does not match the provider/auth profile"
            )
        if Decimal(self.hard_limit_usd) > Decimal(max_cost_usd):
            raise ProviderCapError(
                "whole provider hard limit exceeds the solver ceiling"
            )

    def validate_for_run(
        self,
        *,
        provider: str,
        auth_profile: str,
        max_cost_usd: str,
        timeout_seconds: float,
        now: datetime | None = None,
    ) -> None:
        """Require compatibility and current evidence before live admission."""

        self.validate_compatibility(
            provider=provider, auth_profile=auth_profile, max_cost_usd=max_cost_usd
        )
        now = now or datetime.now(UTC)
        observed = datetime.fromisoformat(self.observed_at)
        expires = datetime.fromisoformat(self.enforced_until)
        if observed > now or now - observed > timedelta(minutes=15):
            raise ProviderCapError(
                "provider cap observation must be current (within 15 minutes)"
            )
        if expires <= now + timedelta(seconds=timeout_seconds):
            raise ProviderCapError(
                "provider cap may renew or expire before the solver stops"
            )


@dataclass(frozen=True, slots=True)
class CapBoundCredentialSource:
    """Check the projected key before the runtime can launch any solver process."""

    cap: ProviderSpendCap
    source: CredentialSource
    timeout_seconds: float

    def fetch_projected_env(self, profile: ResolvedAuthProfile) -> Mapping[str, str]:
        self.cap.validate_for_run(
            provider=self.cap.provider,
            auth_profile=profile.profile_id,
            max_cost_usd=self.cap.hard_limit_usd,
            timeout_seconds=self.timeout_seconds,
        )
        if set(profile.projected_env_vars) != {self.cap.credential_env_var}:
            raise ProviderCapError(
                "provider cap must cover the sole projected credential"
            )
        values = self.source.fetch_projected_env(profile)
        if set(values) != {self.cap.credential_env_var}:
            raise ProviderCapError("provider cap received unexpected credentials")
        actual = sha256(values[self.cap.credential_env_var].encode()).hexdigest()
        if not hmac.compare_digest(actual, self.cap.credential_sha256):
            raise ProviderCapError("provider cap is bound to a different credential")
        return values

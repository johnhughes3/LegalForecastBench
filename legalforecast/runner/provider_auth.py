"""Explicit authentication for managed document-tool provider routes.

Provider SDKs own exchange, caching and refresh. Selection never falls back from
workload identity to a static credential, even when one exists in the process.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from openai import AsyncOpenAI
from pydantic import SecretStr

from legalforecast.runner.ledger import RunValidationError

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

AuthMode = Literal["api_key", "workload_identity"]
_KEY_NAMES = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "vercel_ai_gateway": "AI_GATEWAY_API_KEY",
}


@dataclass(frozen=True)
class ProviderAuthentication:
    """Selected authentication, with credentials excluded from representations."""

    provider: str
    mode: AuthMode
    api_key: SecretStr | None = field(default=None, repr=False)
    audience: str = ""
    identity_provider_id: str = ""
    service_account_id: str = ""
    organization_id: str = ""
    workspace_id: str = ""
    request_url: str = field(default="", repr=False)
    request_token: SecretStr = field(default_factory=lambda: SecretStr(""), repr=False)

    def provenance(self) -> dict[str, str]:
        """Describe the mode without tokens, raw assertions or local paths."""
        return {
            "authentication_mode": self.mode,
            "authentication_provider": self.provider,
            "authentication_endpoint": (
                "gateway" if self.provider == "vercel_ai_gateway" else "direct"
            ),
            "authentication_issuer": (
                "https://token.actions.githubusercontent.com"
                if self.mode == "workload_identity"
                else "not_applicable"
            ),
        }

    def subject_token(self) -> str:
        """Request a fresh audience-bound assertion each time the SDK refreshes."""
        parts = urlsplit(self.request_url)
        query = [
            (key, value) for key, value in parse_qsl(parts.query) if key != "audience"
        ]
        query.append(("audience", self.audience))
        url = urlunsplit(parts._replace(query=urlencode(query)))
        try:
            with httpx.Client(follow_redirects=False, timeout=15) as client:
                response = client.get(
                    url,
                    headers={
                        "Authorization": (
                            f"Bearer {self.request_token.get_secret_value()}"
                        )
                    },
                )
            response.raise_for_status()
            body: object = response.json()
            token = (
                cast(dict[str, object], body).get("value")
                if isinstance(body, dict)
                else None
            )
            if not isinstance(token, str) or not token.strip():
                raise ValueError("missing assertion")
            return token
        except (httpx.HTTPError, ValueError):
            # Neither provider response bodies nor request URLs belong in logs:
            # they can contain the assertion or the GitHub request credential.
            raise RunValidationError(
                "GitHub workload identity request failed"
            ) from None

    def openai_client(self) -> AsyncOpenAI:
        """Create a native SDK client whose explicit WIF overrides ambient keys."""
        if self.provider != "openai" or self.mode != "workload_identity":
            raise RunValidationError("OpenAI workload identity mode is required")
        return AsyncOpenAI(
            workload_identity={
                "identity_provider_id": self.identity_provider_id,
                "service_account_id": self.service_account_id,
                "provider": {"token_type": "jwt", "get_token": self.subject_token},
            },
            base_url="https://api.openai.com/v1",
            max_retries=0,
        )

    def anthropic_client(self) -> AsyncAnthropic:
        """Use the SDK's bearer credential path, never its legacy x-api-key path."""
        from anthropic import AsyncAnthropic
        from anthropic.lib.credentials import AccessToken, WorkloadIdentityCredentials

        if self.provider != "anthropic" or self.mode != "workload_identity":
            raise RunValidationError("Anthropic workload identity mode is required")

        class CheckedCredentials(WorkloadIdentityCredentials):
            def __call__(self, *, force_refresh: bool = False) -> AccessToken:
                try:
                    token = super().__call__(force_refresh=force_refresh)
                    raw_token = cast(object, token.token)
                    if (
                        not isinstance(raw_token, str)
                        or not raw_token.strip()
                        or token.expires_at is None
                        or token.expires_at <= time.time()
                    ):
                        raise ValueError("unusable token")
                    return token
                except Exception:
                    raise RunValidationError(
                        "Anthropic workload identity exchange failed"
                    ) from None

        return AsyncAnthropic(
            credentials=CheckedCredentials(
                identity_token_provider=self.subject_token,
                federation_rule_id=self.identity_provider_id,
                organization_id=self.organization_id,
                service_account_id=self.service_account_id,
                workspace_id=self.workspace_id,
            ),
            base_url="https://api.anthropic.com",
            max_retries=0,
        )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise RunValidationError(f"{name} is required")
    return value


def authentication_provenance(value: object, *, provider: str) -> dict[str, str] | None:
    """Validate persisted provenance against the finite credential-free vocabulary."""
    if value is None:
        return None
    for mode in ("api_key", "workload_identity"):
        expected = ProviderAuthentication(provider, mode).provenance()
        if value == expected:
            return expected
    raise RunValidationError("invalid managed authentication provenance")


def select_provider_authentication(
    provider: str, environ: Mapping[str, str]
) -> ProviderAuthentication:
    """Select one provider independently, preserving the accepted API-key default.

    The default remains temporary migration compatibility, not a fallback after
    federation failure. Official WIF activation is a separate protected rollout.
    """
    provider = provider.strip().lower()
    if provider not in _KEY_NAMES:
        raise RunValidationError("unsupported managed authentication provider")
    prefix = f"LEGALFORECAST_{provider.upper()}"
    mode = environ.get(f"{prefix}_AUTH_MODE", "api_key")
    if mode == "api_key":
        return ProviderAuthentication(
            provider,
            "api_key",
            api_key=SecretStr(_required(environ, _KEY_NAMES[provider])),
        )
    if mode != "workload_identity" or provider not in {"openai", "anthropic"}:
        raise RunValidationError("unsupported provider authentication mode")
    # Anthropic accepts ambient custom headers separately from credentials.
    # Reject that override rather than permit it to smuggle a static key.
    if provider == "anthropic" and (
        environ.get("ANTHROPIC_CUSTOM_HEADERS")
        or os.environ.get("ANTHROPIC_CUSTOM_HEADERS")
    ):
        raise RunValidationError("custom Anthropic headers are incompatible with WIF")
    request_url = _required(environ, "ACTIONS_ID_TOKEN_REQUEST_URL")
    try:
        parts = urlsplit(request_url)
        port = parts.port
    except ValueError:
        raise RunValidationError("invalid GitHub workload identity endpoint") from None
    if (
        parts.scheme != "https"
        or not (parts.hostname or "").endswith(".actions.githubusercontent.com")
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
        or parts.fragment
    ):
        raise RunValidationError("invalid GitHub workload identity endpoint")
    return ProviderAuthentication(
        provider=provider,
        mode="workload_identity",
        audience=_required(environ, f"{prefix}_WIF_AUDIENCE"),
        identity_provider_id=_required(environ, f"{prefix}_WIF_PROVIDER_ID"),
        service_account_id=_required(environ, f"{prefix}_WIF_SERVICE_ACCOUNT_ID"),
        organization_id=(
            _required(environ, f"{prefix}_WIF_ORGANIZATION_ID")
            if provider == "anthropic"
            else ""
        ),
        workspace_id=(
            _required(environ, f"{prefix}_WIF_WORKSPACE_ID")
            if provider == "anthropic"
            else ""
        ),
        request_url=request_url,
        request_token=SecretStr(_required(environ, "ACTIONS_ID_TOKEN_REQUEST_TOKEN")),
    )

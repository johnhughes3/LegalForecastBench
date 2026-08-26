"""Shared OpenAI Responses transport selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

OPENAI_RESPONSES_URL: Final = "https://api.openai.com/v1/responses"
VERCEL_AI_GATEWAY_RESPONSES_URL: Final = "https://ai-gateway.vercel.sh/v1/responses"
OPENAI_SERVICE_TIER: Final = "flex"
OPENAI_SOL_MODEL_ID: Final = "gpt-5.6-sol"
OPENAI_TRANSPORT_CONTRACT_VERSION: Final = "vercel-sol-flex-v1"
VERCEL_SOL_PROMOTION_LAST_DATE_UTC: Final = date(2026, 9, 18)
VERCEL_OPENAI_PROVIDER: Final = "openai"


@dataclass(frozen=True, slots=True)
class OpenAITransportRoute:
    """Resolved endpoint, model identifier, and upstream provider policy."""

    responses_url: str
    request_model_id: str
    gateway_provider: str | None = None

    @property
    def uses_vercel_gateway(self) -> bool:
        """Return whether the request is billed through Vercel AI Gateway."""

        return self.gateway_provider is not None

    @property
    def transport_name(self) -> str:
        """Return the public-safe transport identifier for result provenance."""

        if self.uses_vercel_gateway:
            return "vercel_ai_gateway"
        return "direct_openai"

    def gateway_extra_body(self) -> dict[str, object]:
        """Return the OpenAI-SDK extra body that forbids provider fallback."""

        if self.gateway_provider is None:
            return {}
        return {
            "providerOptions": {
                "gateway": {"only": [self.gateway_provider]},
            }
        }


def resolve_openai_transport(
    model_id: str,
    *,
    on_date_utc: date | None = None,
    use_vercel_gateway: bool | None = None,
) -> OpenAITransportRoute:
    """Route Sol through OpenAI-on-Vercel for the selected promo window."""

    normalized_model_id = model_id.removeprefix("openai/")
    today = on_date_utc or datetime.now(UTC).date()
    if use_vercel_gateway is True and normalized_model_id != OPENAI_SOL_MODEL_ID:
        raise ValueError("Vercel AI Gateway override is only valid for gpt-5.6-sol")
    within_promotion = today <= VERCEL_SOL_PROMOTION_LAST_DATE_UTC
    route_through_gateway = (
        within_promotion if use_vercel_gateway is None else use_vercel_gateway
    )
    if normalized_model_id == OPENAI_SOL_MODEL_ID and route_through_gateway:
        return OpenAITransportRoute(
            responses_url=VERCEL_AI_GATEWAY_RESPONSES_URL,
            request_model_id=f"openai/{normalized_model_id}",
            gateway_provider=VERCEL_OPENAI_PROVIDER,
        )
    return OpenAITransportRoute(
        responses_url=OPENAI_RESPONSES_URL,
        request_model_id=normalized_model_id,
    )

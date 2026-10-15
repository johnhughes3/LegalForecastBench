"""Ultramarine's native Messages adapter for the managed document-tool agent."""

from typing import Literal, cast

from pydantic_ai import ModelSettings
from pydantic_ai.models import Model

from legalforecast.evals.model_registry import ModelRegistryEntry

BASE_URL = "https://api.paperinstruments.com"
MODEL_ID = "ultramarine-1-flash"


def paperinstruments_model(entry: ModelRegistryEntry, *, api_key: str | None) -> Model:
    """Use the managed SDK against the provider's fixed direct endpoint."""
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.profiles.anthropic import AnthropicModelProfile
    from pydantic_ai.providers.anthropic import AnthropicProvider

    if entry.model_id != MODEL_ID:
        raise ValueError("unsupported Paper Instruments model")
    return AnthropicModel(
        entry.model_id,
        provider=AnthropicProvider(api_key=api_key, base_url=BASE_URL),
        profile=AnthropicModelProfile(
            supports_json_schema_output=True,
            supports_thinking=True,
            thinking_always_enabled=True,
            anthropic_supports_adaptive_thinking=True,
            anthropic_supports_effort=True,
            anthropic_disallows_budget_thinking=True,
            anthropic_max_output_tokens=32768,
            context_window=131072,
        ),
    )


def paperinstruments_settings(entry: ModelRegistryEntry) -> ModelSettings:
    """Avoid unsupported cache TTLs and thinking blocks in subsequent history.

    The provider supports ephemeral caching without a TTL, and adaptive thinking
    with display omitted. The SDK retains the full conversation and owns its loop.
    https://docs.paperinstruments.com/docs/ultramarine/messages
    """
    from pydantic_ai.models.anthropic import AnthropicModelSettings

    return cast(
        ModelSettings,
        AnthropicModelSettings(
            max_tokens=entry.max_output_tokens,
            anthropic_thinking={"type": "adaptive", "display": "omitted"},
            anthropic_effort=cast(
                Literal["low", "high", "max"], entry.reasoning_effort.value
            )
            if entry.reasoning_effort is not None
            else "high",
            parallel_tool_calls=False,
            extra_body={"cache_control": {"type": "ephemeral"}},
        ),
    )

"""Optional native Anthropic adapter for document-tool forecasts."""

from typing import cast

from pydantic_ai import ModelSettings
from pydantic_ai.models import Model

from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    OpenAIReasoningEffort,
    ToolPolicy,
)


def anthropic_model(entry: ModelRegistryEntry, *, api_key: str | None) -> Model:
    """Build the optional native Anthropic model adapter on demand.

    Anthropic is an optional Pydantic AI provider because the public benchmark
    package also supports provider-free and non-Anthropic environments. Keeping
    this import on the selected provider branch lets those environments retain
    their existing dependency surface while the Anthropic workflow installs its
    dedicated extra.
    """

    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    return AnthropicModel(
        entry.model_id,
        provider=AnthropicProvider(api_key=api_key),
    )


def anthropic_model_settings(
    entry: ModelRegistryEntry,
) -> ModelSettings:
    """Configure adaptive thinking and five-minute conversation-prefix caching.

    The runner explicitly selects native JSON output so provider profile defaults
    cannot force workspace tool calls when the model is ready to finish.
    """

    from pydantic_ai.models.anthropic import AnthropicModelSettings

    explicit_opus_effort = entry.reasoning_effort is not None
    if explicit_opus_effort and not (
        entry.provider.strip().lower() == "anthropic"
        and entry.model_id == "claude-opus-5-5"
        and entry.reasoning_effort is OpenAIReasoningEffort.HIGH
        and entry.jev_input_mode is None
        and entry.tool_policy is ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY
    ):
        raise ValueError(
            "Explicit Anthropic managed effort is supported only for agentic "
            "claude-opus-5-5 at high effort"
        )

    settings = AnthropicModelSettings(
        max_tokens=entry.max_output_tokens,
        anthropic_thinking={"type": "adaptive"},
        anthropic_cache=True,
        parallel_tool_calls=False,
    )
    if explicit_opus_effort:
        cast(dict[str, object], settings)["anthropic_effort"] = "high"
    return cast(
        ModelSettings,
        settings,
    )

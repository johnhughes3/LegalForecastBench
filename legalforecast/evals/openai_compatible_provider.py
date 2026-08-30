"""Generic OpenAI-compatible chat-completions adapter for live provider runs.

Several providers expose an endpoint that speaks OpenAI's ``/chat/completions``
shape, so one parameterized adapter serves them all rather than a bespoke
function per provider.  What this module does **not** assume is that
"OpenAI-compatible" means "identical".  It does not, and the differences are the
expensive kind:

* **The reasoning knob is not one parameter.**  xAI takes a top-level
  ``reasoning_effort``; other vendors nest a ``thinking`` object, or expose an
  adaptive on/off toggle with no effort levels at all.  A wrong spelling is
  either a loud 400 or -- far worse -- a silently ignored field that runs the
  model at a provider default.  So the spelling is declared per provider here
  and pinned by tests, never inferred.
* **Reasoning tokens are not accounted the same way.**  Despite the OpenAI-style
  ``completion_tokens_details.reasoning_tokens`` nesting, which conventionally
  means *included in* ``completion_tokens``, xAI's own documented examples show
  them **excluded** and additive.  Reading only ``completion_tokens`` there
  under-reports billed spend against an owner cost cap.  Each provider therefore
  declares ``reasoning_token_accounting`` explicitly -- including the honest
  third state for a provider that does not document it at all.
* **On a shared host the reasoning knob belongs to the MODEL, not the provider.**
  A single endpoint can serve one model that takes ``reasoning_effort``, another
  that nests a ``thinking`` toggle, and a third with no effort levels at all --
  and several silently remap an unsupported effort to the nearest supported one
  rather than rejecting it, so a benchmark sweeping effort levels can collapse
  to one configuration with no error anywhere.
* **The answer may not be in ``content``.**  Reasoning models on several stacks
  return their thinking in a separate ``reasoning_content`` field.  This adapter
  reads ``content`` only, and refuses an empty one rather than returning ""
  or silently concatenating reasoning text into the graded output.

This mirrors the two real defects found on the Gemini lane -- a reasoning
parameter nested differently than the docs first suggested, and thinking tokens
reported in a usage field the accounting never read.  Every value here is
sourced from provider documentation and pinned by a payload-shape test; the
one-call shape probe in ``scripts/probe_openai_compatible_provider.py`` is what
confirms it against the live API before any paid dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

XAI_API_KEY_ENV: Final = "XAI_API_KEY"
XAI_CHAT_COMPLETIONS_URL: Final = "https://api.x.ai/v1/chat/completions"
DEEPINFRA_API_KEY_ENV: Final = "DEEPINFRA_API_KEY"
DEEPINFRA_CHAT_COMPLETIONS_URL: Final = (
    "https://api.deepinfra.com/v1/openai/chat/completions"
)
DEEPINFRA_MODEL_METADATA_URL_TEMPLATE: Final = (
    "https://api.deepinfra.com/models/{model}"
)
"""Free, unauthenticated endpoint returning a model's ``version`` and ``quantization``.

This is the drift-detection surface. DeepInfra does not offer request-level
version pinning -- no host does for these models -- but it is the only one that
publishes machine-readable serving identity without a key, which lets a preflight
refuse a dispatch whose served artifact has changed since the freeze. Detection,
not a pin: it makes a substitution loud instead of silent.
"""


class ReasoningTokenAccounting(StrEnum):
    """Whether a provider's reasoning tokens are already in ``completion_tokens``.

    A three-state answer, not a boolean, because "we have not verified this"
    is a real and common state that must not be silently collapsed into either
    confident answer. Guessing wrong in one direction under-reports billed spend
    against an owner cost cap; guessing wrong in the other over-reports it. Only
    the first failure is dangerous, so the unverified state deliberately behaves
    like the conservative one while still reporting itself as unverified.
    """

    ADDITIVE = "additive"
    """Documented as excluded from ``completion_tokens``; must be added."""

    INCLUDED_IN_COMPLETION = "included_in_completion"
    """Documented as already inside ``completion_tokens``; must not be added."""

    UNVERIFIED_CONSERVATIVE = "unverified_conservative"
    """Undocumented. Counted as additive so spend is never under-reported.

    Must be resolved by the one-call shape probe before any paid dispatch. The
    adapter stamps this state into response metadata so a run executed on an
    unverified accounting shape cannot later be mistaken for a verified one.
    """


class ReasoningParameterStyle(StrEnum):
    """How a provider spells its reasoning control in the request body."""

    TOP_LEVEL_REASONING_EFFORT = "top_level_reasoning_effort"
    """Top-level ``{"reasoning_effort": "<value>"}``.

    xAI's Chat Completions spelling. Note the sibling Responses API nests the
    same setting as ``reasoning: {"effort": ...}`` instead; this adapter calls
    Chat Completions, so the flat spelling is the correct one here.
    """


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    """One provider's documented deviations from the plain OpenAI shape.

    Every field is a statement about a specific provider's API that was read
    from its documentation, not a default inherited from OpenAI.
    """

    provider: str
    api_key_env: str
    chat_completions_url: str
    reasoning_parameter_style: ReasoningParameterStyle | None
    reasoning_token_accounting: ReasoningTokenAccounting
    supports_response_json_schema: bool
    extra_body: Mapping[str, object] = field(default_factory=lambda: {})
    """Provider-specific request fields sent on every call.

    Used for settings that have no OpenAI equivalent, such as xAI's explicit
    search off-switch. Kept as data so the payload-shape test can pin it.
    """

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.api_key_env.strip():
            raise ValueError("api_key_env is required")
        if not self.chat_completions_url.strip():
            raise ValueError("chat_completions_url is required")

    @property
    def adds_reasoning_tokens(self) -> bool:
        """Whether reasoning tokens must be added to the billed output count.

        Unverified accounting counts as additive: over-reporting spend against a
        cap is recoverable, under-reporting it is not.
        """

        return self.reasoning_token_accounting in {
            ReasoningTokenAccounting.ADDITIVE,
            ReasoningTokenAccounting.UNVERIFIED_CONSERVATIVE,
        }


XAI_PROVIDER: Final = OpenAICompatibleProvider(
    provider="xai",
    api_key_env=XAI_API_KEY_ENV,
    chat_completions_url=XAI_CHAT_COMPLETIONS_URL,
    # Verified 2026-08-30 from
    # https://docs.x.ai/developers/model-capabilities/text/reasoning :
    # "grok-4.6 and grok-4.5 support the reasoning_effort parameter", values
    # low / medium / high (default) / xhigh, and "Reasoning cannot be disabled".
    # The Chat Completions spelling is the flat top-level field; the Responses
    # API nests it as reasoning.effort. We always send it explicitly rather than
    # relying on the documented default, because the REST reference page
    # disagrees with the capability page about what that default is.
    reasoning_parameter_style=ReasoningParameterStyle.TOP_LEVEL_REASONING_EFFORT,
    # Verified 2026-08-30 from the worked examples in
    # https://docs.x.ai/developers/rest-api-reference/inference/chat :
    # prompt 32 + completion 9 + reasoning 94 == total 135, and on the Responses
    # API 32 + 9 + 110 == 151. Reasoning tokens are EXCLUDED from
    # completion_tokens despite the OpenAI-style nesting, so they must be added
    # or billed spend is under-reported.
    reasoning_token_accounting=ReasoningTokenAccounting.ADDITIVE,
    # Verified 2026-08-30 from
    # https://docs.x.ai/developers/model-capabilities/text/structured-outputs :
    # response_format.type "json_schema" with the schema under
    # response_format.json_schema, strict mode supported.
    supports_response_json_schema=True,
    # Verified 2026-08-30 from https://docs.x.ai/developers/models : Grok has no
    # realtime access unless server-side search tools are enabled, so the
    # default is already search-free. We still send the explicit off-switch
    # because the registry declares search_disabled and a benchmark should not
    # depend on a default staying put.
    # https://docs.x.ai/developers/tools/web-search documents mode "off":
    # "no search performed and no external will be considered".
    extra_body={"search_parameters": {"mode": "off"}},
)


DEEPINFRA_PROVIDER: Final = OpenAICompatibleProvider(
    provider="deepinfra",
    api_key_env=DEEPINFRA_API_KEY_ENV,
    chat_completions_url=DEEPINFRA_CHAT_COMPLETIONS_URL,
    # DeepInfra's OpenAI-compatible API documents a top-level reasoning_effort
    # accepting none/minimal/low/medium/high/xhigh/max. Checked 2026-08-30.
    #
    # IMPORTANT: on a shared host the reasoning knob is a property of the MODEL,
    # not of the provider. This spec describes what the *endpoint* accepts; what
    # a given model does with it varies sharply. Kimi K3 accepts only low, high
    # and max (default max) and always reasons. GLM 5.2 nests a separate
    # thinking:{type} toggle and collapses its seven effort values to
    # effectively high and max. MiniMax M3 has no effort selection at all --
    # only an adaptive thinking on/off toggle -- so an entry for it could not
    # satisfy this style's explicit-effort requirement and would need a second
    # ReasoningParameterStyle. Only Kimi K3 rides this provider today, and
    # "high" is valid for it, so the per-model gap is recorded rather than
    # abstracted over. Do not add a model here without re-checking its knob.
    reasoning_parameter_style=ReasoningParameterStyle.TOP_LEVEL_REASONING_EFFORT,
    # NOT DOCUMENTED. As of 2026-08-30 DeepInfra's documentation contains no
    # occurrence of completion_tokens_details.reasoning_tokens and no response
    # example showing where reasoning tokens are counted; it states only that
    # "Reasoning tokens count toward output token billing". Together documents
    # the same model's tokens as INCLUDED in completion_tokens, and xAI
    # documents its own as EXCLUDED, so neither neighbour settles DeepInfra.
    # Counted conservatively until the shape probe resolves it, because
    # under-reporting spend against an owner cap is the unrecoverable direction.
    reasoning_token_accounting=ReasoningTokenAccounting.UNVERIFIED_CONSERVATIVE,
    # DeepInfra's OpenAI-compatible endpoint documents response_format with
    # json_object, json_schema and regex modes. Checked 2026-08-30.
    supports_response_json_schema=True,
)


_PROVIDERS: Final[Mapping[str, OpenAICompatibleProvider]] = {
    XAI_PROVIDER.provider: XAI_PROVIDER,
    DEEPINFRA_PROVIDER.provider: DEEPINFRA_PROVIDER,
}


def deepinfra_model_metadata_url(model_id: str) -> str:
    """Return the free drift-detection URL for one DeepInfra model.

    The response carries ``version`` and ``quantization``. Freezing both in a
    registry entry and re-reading this URL before dispatch is what converts a
    silent re-quantization or point-release swap into a loud refusal. It is not
    a request-level pin, and must never be described as one.
    """

    return DEEPINFRA_MODEL_METADATA_URL_TEMPLATE.format(model=model_id)


def openai_compatible_provider(provider: str) -> OpenAICompatibleProvider | None:
    """Return the adapter spec for ``provider``, or ``None`` if it has none."""

    return _PROVIDERS.get(provider.strip().lower())


def openai_compatible_provider_names() -> tuple[str, ...]:
    """Return every provider served by this adapter, sorted."""

    return tuple(sorted(_PROVIDERS))

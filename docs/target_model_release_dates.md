# Target Model Release Dates

This note records the initial frontier-model targets for the first full
LegalForecast-MTD benchmark run. The model registry should use provider
snapshots that are available to the evaluator at run time, but the eligibility
and contamination analysis should anchor on the public release dates below.

| Provider | Initial target | Public release date | Initial-run status | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.5 / GPT-5.5 Pro | April 23, 2026; API availability updated April 24, 2026 | Target if `gpt-5.5` or `gpt-5.5-pro` is available to the evaluator account at freeze time. Use the API-availability date for API-only run eligibility notes. | OpenAI, "Introducing GPT-5.5" |
| Anthropic | Claude Opus 4.7 | April 16, 2026 | Target frontier Claude run. The launch note says Opus 4.7 is generally available across Claude products, the Claude API, Amazon Bedrock, Vertex AI, and Microsoft Foundry. | Anthropic, "Introducing Claude Opus 4.7" |
| Google | Gemini 3.1 Pro Preview | February 19, 2026 | Target latest Gemini Pro run. Google describes 3.1 Pro as rolling out to developers in preview through Gemini API / AI Studio and as the latest Pro model; the older Gemini 3 Pro Preview should not be used as the primary target after deprecation. | Google, "Gemini 3.1 Pro"; Google AI Developer model docs |

## Source Evidence

- OpenAI published "Introducing GPT-5.5" on April 23, 2026 and updated it on
  April 24, 2026 to state that GPT-5.5 and GPT-5.5 Pro are available in the API:
  <https://openai.com/index/introducing-gpt-5-5/>.
- Anthropic published "Introducing Claude Opus 4.7" on April 16, 2026 and states
  that Opus 4.7 is generally available and available through `claude-opus-4-7`:
  <https://www.anthropic.com/news/claude-opus-4-7>.
- Google announced Gemini 3.1 Pro on February 19, 2026 and says it is rolling out
  in preview through Gemini API / AI Studio, Vertex AI, Gemini Enterprise, the
  Gemini app, and NotebookLM:
  <https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/>.
- Google DeepMind's Gemini 3.1 Pro model card was published February 19, 2026 and
  describes it as Google's most advanced model for complex tasks as of that date:
  <https://deepmind.google/models/model-cards/gemini-3-1-pro/>.
- Google AI Developer model docs list Gemini 3.1 Pro under Gemini 3 and warn that
  Gemini 3 Pro Preview was shut down March 9, 2026 with migration to Gemini 3.1
  Pro Preview:
  <https://ai.google.dev/gemini-api/docs/models>.

## Registry Guidance

The frozen model registry should include these entries only after the exact
provider model IDs and pricing sheet are confirmed at protocol-freeze time.
Release dates alone do not establish training cutoffs. Keep
`provider_training_cutoff_status` separate from `release_timestamp`, and record
any provider caveats in `known_cutoff_publicity_caveats`.

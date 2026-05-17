# LegalForecast-MTD Model Card Template

Use one model card for each evaluated provider/model/snapshot. The card is the
human-readable companion to the machine run card; values should come from the
frozen model registry, run card, accounting records, and leaderboard output.

## Identity

| Field | Value |
| --- | --- |
| Provider |  |
| Model ID |  |
| Display name |  |
| Model version or snapshot |  |
| Release timestamp, if available |  |
| Registry key | `provider:model_id` |
| Model registry SHA-256 | `sha256:` |

## Training Cutoff and Contamination Notes

| Field | Value |
| --- | --- |
| Provider training cutoff status | known / unknown / not_disclosed |
| Provider training cutoff date, if known |  |
| Known cutoff or publicity caveats |  |
| Model-release anchor used for this cycle |  |
| Decision-date window |  |
| Contamination filter notes |  |

Explain any public reporting, provider cutoff ambiguity, or model-specific
publicity caveat that affects interpretation. Do not omit unknown cutoff status;
unknown is a disclosed state, not a blank field.

## Run Configuration

| Field | Value |
| --- | --- |
| Run ID |  |
| Run type | official / rapid / pilot |
| Evaluation timestamp |  |
| Harness version or hash |  |
| Prompt SHA-256 | `sha256:` |
| Scorer SHA-256 | `sha256:` |
| Manifest SHA-256 | `sha256:` |
| Prediction-unit SHA-256 | `sha256:` |
| Label SHA-256 | `sha256:` |
| Network disabled confirmed | true / false |
| Search disabled confirmed | true / false |
| Tool policy | no_tools / controlled_docket_tool_only |
| Tool-call cap |  |
| Context limit |  |

## Sampling Parameters

| Field | Value |
| --- | --- |
| Temperature |  |
| Top-p |  |
| Max output tokens |  |
| Provider-equivalent deterministic setting notes |  |

## Cost Assumptions and Accounting

| Field | Value |
| --- | --- |
| Pricing source |  |
| Input-token price, USD per 1M tokens |  |
| Output-token price, USD per 1M tokens |  |
| Cases evaluated |  |
| Prediction units evaluated |  |
| Mean tool calls per case |  |
| Median tool calls per case |  |
| 95th percentile tool calls per case |  |
| Cost per case |  |
| Cost per prediction unit |  |
| Mean latency, ms |  |
| 95th percentile latency, ms |  |

## Headline Results

| Metric | Value |
| --- | --- |
| Micro-Brier |  |
| Brier Skill Score vs. base rate |  |
| Log loss |  |
| ECE / calibration |  |
| Macro-Brier |  |
| Capped per-case micro-Brier |  |
| Related-family capped sensitivity |  |
| Rank tier |  |

## Reliability

| Metric | Value |
| --- | --- |
| Invalid-output rate |  |
| Refusal rate |  |
| Content-filter rate |  |
| Defaulted-prediction rate |  |
| Denied tool-call rate or count |  |

## Limitations

- Training-cutoff limitations:
- Case-mix limitations:
- Tool-use or no-tool condition limitations:
- Cost/pricing limitations:
- Known failure modes:
- Human review or audit caveats:

## Required Attachments

- Run card JSON validated against `docs/run_card_schema.json`.
- Frozen model registry entry.
- Leaderboard row and accounting summary.
- Calibration and Pareto reporting artifacts.
- Preregistration and freeze-bundle references.

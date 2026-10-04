# Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

[Read the GPT-6 Sol report](gpt-6-sol-audit.md) · [Read the Claude Opus 5.5 report](claude-opus-5-5-audit.md) · [Pinned upstream task and documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines)

**Rubric criteria:** 57. **Audit batch:** 4.

The report records the AI reviewers' conclusions and source-review limits. Labels such as “confirmed” are the AI's own classifications, not human verification or accepted score corrections.

Supporting report files:

- [findings.json](gpt-6-sol-audit.json)

## Pinned upstream sources

- [Task instructions and rubric (`task.json`)](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json)
- [billing-guidelines.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/documents/billing-guidelines.docx)
- [hwk-engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/documents/hwk-engagement-letter.docx)
- [hwk-invoice-may-2025.xlsx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/documents/hwk-invoice-may-2025.xlsx)
- [pre-approval-log.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/documents/pre-approval-log.docx)

<!-- dual-audit:start -->
## Dual-audit comparison

Reports: [GPT-6 Sol](gpt-6-sol-audit.md) · [Claude Opus 5.5](claude-opus-5-5-audit.md). Criteria flagged by either model: 9 of 57. both models: problematic: 4; both models: arguable: 2; both flagged, different strength (one problematic, one arguable): 1; flagged by gpt-6 sol only: 0; flagged by claude opus 5.5 only: 2.

Model runs: [GPT-6 Luna (xhigh)](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md) · [Claude Opus 5.5 (low)](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md). The Runs column gives each run's native verdicts (P pass, F fail) from Sonnet 4.6 / GPT-5.5 and links to the judges' reasoning.

| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement | Runs |
|---|---|---|---|---|---|
| [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162) | arguable | arguable | arguable | Both models: arguable | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-019) · Opus [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-019) |
| [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266) | problematic | problematic | problematic | Both models: problematic | Luna [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-032) · Opus [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-032) |
| [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L274) | — | problematic | problematic | Flagged by Claude Opus 5.5 only | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-033) · Opus [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-033) |
| [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282) | problematic | problematic | problematic | Both models: problematic | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-034) · Opus [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-034) |
| [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338) | problematic | problematic | problematic | Both models: problematic | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-041) · Opus [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-041) |
| [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362) | arguable | arguable | — | Both models: arguable | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-044) · Opus [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-044) |
| [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370) | problematic | problematic | problematic | Both models: problematic | Luna [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-045) · Opus [F/F](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-045) |
| [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) | Luna [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-050) · Opus [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-050) |
| [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L426) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/gpt6luna-xhigh/README.md#c-052) · Opus [P/P](../../model-runs/verify-disbursement-charges-against-billing-guidelines/opus55-low/README.md#c-052) |

<!-- dual-audit:end -->

# Extract Scope Terms from Matter Plan — Structured Extraction Report

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

[Read the GPT-6 Sol report](gpt-6-sol-audit.md) · [Read the Claude Opus 5.5 report](claude-opus-5-5-audit.md) · [Pinned upstream task and documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan)

**Rubric criteria:** 76. **Audit batch:** 3.

The report records the AI reviewers' conclusions and source-review limits. Labels such as “confirmed” are the AI's own classifications, not human verification or accepted score corrections.

Supporting report files:

- [audit.json](gpt-6-sol-audit.json)

## Pinned upstream sources

- [Task instructions and rubric (`task.json`)](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json)
- [budget-summary.xlsx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/budget-summary.xlsx)
- [engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/engagement-letter.docx)
- [matter-plan-revision-1.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan-revision-1.docx)
- [matter-plan.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan.docx)
- [outside-counsel-guidelines.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/outside-counsel-guidelines.docx)
- [scope-negotiation-emails.eml](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/scope-negotiation-emails.eml)

<!-- dual-audit:start -->
## Dual-audit comparison

Reports: [GPT-6 Sol](gpt-6-sol-audit.md) · [Claude Opus 5.5](claude-opus-5-5-audit.md). Criteria flagged by either model: 9 of 76. both models: problematic: 1; both models: arguable: 0; both flagged, different strength (one problematic, one arguable): 0; flagged by gpt-6 sol only: 4; flagged by claude opus 5.5 only: 4.

Model runs: [GPT-6 Luna (xhigh)](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md) · [Claude Opus 5.5 (low)](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md). The Runs column gives each run's native verdicts (P pass, F fail) from Sonnet 4.6 / GPT-5.5 and links to the judges' reasoning.

| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement | Runs |
|---|---|---|---|---|---|
| [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L451) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [P/P](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-055) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-055) |
| [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L459) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [P/P](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-056) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-056) |
| [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L467) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [F/F](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-057) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-057) |
| [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L491) | problematic | — | — | Flagged by GPT-6 Sol only | Luna [F/F](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-060) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-060) |
| [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L499) | problematic | problematic | arguable | Both models: problematic | Luna [F/F](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-061) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-061) |
| [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L507) | arguable | — | — | Flagged by GPT-6 Sol only | Luna [P/P](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-062) · Opus [P/P](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-062) |
| [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L515) | arguable | — | — | Flagged by GPT-6 Sol only | Luna [P/P](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-063) · Opus [P/P](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-063) |
| [C-066](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L539) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [F/F](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-066) · Opus [F/F](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-066) |
| [C-069](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L563) | arguable | — | — | Flagged by GPT-6 Sol only | Luna [P/P](../../model-runs/extract-scope-terms-from-matter-plan/gpt6luna-xhigh/README.md#c-069) · Opus [P/P](../../model-runs/extract-scope-terms-from-matter-plan/opus55-low/README.md#c-069) |

<!-- dual-audit:end -->

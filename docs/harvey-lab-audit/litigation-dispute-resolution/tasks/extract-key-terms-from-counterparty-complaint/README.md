# Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

[Read the GPT-6 Sol report](gpt-6-sol-audit.md) · [Read the Claude Opus 5.5 report](claude-opus-5-5-audit.md) · [Pinned upstream task and documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint)

**Rubric criteria:** 75. **Audit batch:** 1.

The report records the AI reviewers' conclusions and source-review limits. Labels such as “confirmed” are the AI's own classifications, not human verification or accepted score corrections.

## Pinned upstream sources

- [Task instructions and rubric (`task.json`)](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json)
- [apex-v-greenfield-complaint.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/documents/apex-v-greenfield-complaint.docx)
- [client-initial-email.eml](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/documents/client-initial-email.eml)
- [service-confirmation.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/documents/service-confirmation.docx)

<!-- dual-audit:start -->
## Dual-audit comparison

Reports: [GPT-6 Sol](gpt-6-sol-audit.md) · [Claude Opus 5.5](claude-opus-5-5-audit.md). Criteria flagged by either model: 13 of 75. both models: problematic: 1; both models: arguable: 2; both flagged, different strength (one problematic, one arguable): 4; flagged by gpt-6 sol only: 1; flagged by claude opus 5.5 only: 5.

| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement |
|---|---|---|---|---|
| [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L75) | — | problematic | problematic | Flagged by Claude Opus 5.5 only |
| [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L83) | — | — | problematic | neither (final) |
| [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L163) | arguable | — | — | Flagged by GPT-6 Sol only |
| [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L187) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L227) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) |
| [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L339) | problematic | arguable | — | Both flagged, different strength (one problematic, one arguable) |
| [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L411) | — | — | arguable | neither (final) |
| [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L443) | arguable | arguable | arguable | Both models: arguable |
| [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L451) | — | — | arguable | neither (final) |
| [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L459) | problematic | problematic | problematic | Both models: problematic |
| [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L499) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L507) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L515) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-065](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L531) | problematic | arguable | — | Both flagged, different strength (one problematic, one arguable) |
| [C-066](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L539) | problematic | arguable | — | Both flagged, different strength (one problematic, one arguable) |
| [C-068](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L555) | arguable | arguable | arguable | Both models: arguable |

<!-- dual-audit:end -->

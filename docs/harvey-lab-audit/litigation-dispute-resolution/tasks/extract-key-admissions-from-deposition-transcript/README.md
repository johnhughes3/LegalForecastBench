# Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

[Read the GPT-6 Sol report](gpt-6-sol-audit.md) · [Read the Claude Opus 5.5 report](claude-opus-5-5-audit.md) · [Pinned upstream task and documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript)

**Rubric criteria:** 46. **Audit batch:** 5.

The report records the AI reviewers' conclusions and source-review limits. Labels such as “confirmed” are the AI's own classifications, not human verification or accepted score corrections.

Supporting report files:

- [audit.json](gpt-6-sol-audit.json)

## Pinned upstream sources

- [Task instructions and rubric (`task.json`)](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json)
- [cms-cease-desist-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/cms-cease-desist-letter.docx)
- [forensic-report.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/forensic-report.docx)
- [separation-acknowledgment.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/separation-acknowledgment.docx)
- [yoon-deposition-vol1.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/yoon-deposition-vol1.docx)
- [yoon-deposition-vol2.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/yoon-deposition-vol2.docx)
- [yoon-employment-agreement.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/yoon-employment-agreement.docx)
- [yoon-interrogatory-answers.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/documents/yoon-interrogatory-answers.docx)

<!-- dual-audit:start -->
## Dual-audit comparison

Reports: [GPT-6 Sol](gpt-6-sol-audit.md) · [Claude Opus 5.5](claude-opus-5-5-audit.md). Criteria flagged by either model: 13 of 46. both models: problematic: 0; both models: arguable: 1; both flagged, different strength (one problematic, one arguable): 3; flagged by gpt-6 sol only: 2; flagged by claude opus 5.5 only: 7.

| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement |
|---|---|---|---|---|
| [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L19) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) |
| [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L27) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L35) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) |
| [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) |
| [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L83) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L123) | arguable | — | — | Flagged by GPT-6 Sol only |
| [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L147) | arguable | — | — | Flagged by GPT-6 Sol only |
| [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L235) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267) | arguable | arguable | arguable | Both models: arguable |
| [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L323) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |
| [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L347) | — | arguable | arguable | Flagged by Claude Opus 5.5 only |

<!-- dual-audit:end -->

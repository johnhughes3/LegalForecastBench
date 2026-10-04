# Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

[Read the GPT-6 Sol report](gpt-6-sol-audit.md) · [Read the Claude Opus 5.5 report](claude-opus-5-5-audit.md) · [Pinned upstream task and documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification)

**Rubric criteria:** 50. **Audit batch:** 4.

The report records the AI reviewers' conclusions and source-review limits. Labels such as “confirmed” are the AI's own classifications, not human verification or accepted score corrections.

Supporting report files:

- [findings.json](gpt-6-sol-audit.json)

## Pinned upstream sources

- [Task instructions and rubric (`task.json`)](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json)
- [brashear-tran-nguyen-emails.eml](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/brashear-tran-nguyen-emails.eml)
- [demand-letter-stadler-raines.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/demand-letter-stadler-raines.docx)
- [internal-investigation-summary.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/internal-investigation-summary.docx)
- [it-infrastructure-memo.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/it-infrastructure-memo.docx)
- [kovach-personnel-file-summary.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/kovach-personnel-file-summary.docx)
- [nexfield-retention-policy.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/nexfield-retention-policy.docx)
- [pinnacle-hartwell-engagement.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/pinnacle-hartwell-engagement.docx)
- [sec-informal-inquiry-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/documents/sec-informal-inquiry-letter.docx)

<!-- dual-audit:start -->
## Dual-audit comparison

Reports: [GPT-6 Sol](gpt-6-sol-audit.md) · [Claude Opus 5.5](claude-opus-5-5-audit.md). Criteria flagged by either model: 3 of 50. both models: problematic: 0; both models: arguable: 1; both flagged, different strength (one problematic, one arguable): 1; flagged by gpt-6 sol only: 0; flagged by claude opus 5.5 only: 1.

Model runs: [GPT-6 Luna (xhigh)](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/README.md) · [Claude Opus 5.5 (low)](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/opus55-low/README.md). The Runs column gives each run's native verdicts (P pass, F fail) from Sonnet 4.6 / GPT-5.5 and links to the judges' reasoning.

| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement | Runs |
|---|---|---|---|---|---|
| [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83) | problematic | arguable | arguable | Both flagged, different strength (one problematic, one arguable) | Luna [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/README.md#c-009) · Opus [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/opus55-low/README.md#c-009) |
| [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L131) | — | — | arguable | neither (final) | Luna [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/README.md#c-015) · Opus [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/opus55-low/README.md#c-015) |
| [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L235) | — | arguable | arguable | Flagged by Claude Opus 5.5 only | Luna [F/F](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/README.md#c-028) · Opus [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/opus55-low/README.md#c-028) |
| [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283) | arguable | arguable | arguable | Both models: arguable | Luna [F/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/README.md#c-034) · Opus [P/P](../../model-runs/assess-litigation-hold-scope-for-custodian-identification/opus55-low/README.md#c-034) |

<!-- dual-audit:end -->

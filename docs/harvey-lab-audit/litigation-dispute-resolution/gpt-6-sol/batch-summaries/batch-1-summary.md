# Batch 1 blind audit summary

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Completed nine assigned tasks. Read all **474 criteria** and all nine prompts. Extracted all **69 source files**, including two XLSX workbooks, with targeted substantive cross-checks documented per task. This is full rubric-reading coverage, not exhaustive source-page, layout, citation, or invoice-narrative validation. No solver outputs or grades read; no task/rubric/runtime changes, paid calls, publication, or tracker edits made.

## Most consequential definite findings

| Task | Criteria | Finding |
|---|---|---|
| extract-key-terms-from-counterparty-complaint | [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L459) | Requires saying Georgia exemplary-damages cap is 1x actual; §10-1-763(b) allows up to 2x subsection(a) award. |
| analyze-counterparty-motion-to-dismiss | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L108)/C-024 | Requires categorical fraud exception to merger clauses although actual MSA contains express nonreliance language; Georgia law allows reliance foreclosure and Texas requires disclaimer-specific analysis. |
| review-litigation-invoice-against-outside-counsel-billing-guidelines | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220)/C-027 | Cho detailed and LEDES rows sum to 214h/$41,730, while rubric mandates 186h/$36,270 from conflicting summary. |
| review-litigation-invoice-against-outside-counsel-billing-guidelines | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164)/C-020/C-042 | Requires “borderline” business class despite explicit ≥4h permission; actual schedule absent, rubric assumes 4h20. |
| identify-issues-in-counterparty-interrogatories | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-counterparty-interrogatories/task.json#L190) | November14 is expert deposition completion; actual report dates are September15/October15. |
| identify-issues-in-counterparty-interrogatories | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-counterparty-interrogatories/task.json#L214)/C-026/C-030 | Forces invalid categorical objections to document-identification and law-to-fact contention interrogatories. |
| build-litigation-case-timeline | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L83)/C-050 | March14,2023 minus 90 days is December14,2022, not required December15. |
| extract-key-terms-from-counterparty-complaint | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L227) | February28,2024 minus 180 days is September1,2023, not required August31. |
| draft-conflict-check-memorandum | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/task.json#L186)/C-037 | Illinois 1.8(i) is proprietary litigation interests, not related persons; lateral screening is 1.10(e), not 1.10(a)(2). |
| draft-interrogatories | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L267) | Requires an unnecessary judicial-deferral disclaimer for otherwise proper contention interrogatories. |
| draft-requests-for-production | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-requests-for-production/task.json#L315) | Mandatory protective-order designation reference conflicts with strategy memo's express permission to omit it. |

The invoice's original stated $487,329.14 differs from the detailed combined $514,206.14: fees differ by $26,867 and expenses by $10. This source inconsistency matters for C-038/C-039's mandatory final revised figure. Recalculation is in the invoice subdirectory's `recomputed-fees.json`.

## Per-task reports

- [Motion to dismiss](../../tasks/analyze-counterparty-motion-to-dismiss/gpt-6-sol-audit.md) — all 34 criteria; legal and hidden-severity findings, with qualified forum/limitations concerns.
- [Timeline](../../tasks/build-litigation-case-timeline/gpt-6-sol-audit.md) — all 64 criteria; date arithmetic, unnecessary limitations-rescue framing, hidden formatting thresholds and qualified causation issues. Initial preservation concern was withdrawn after finding supporting source facts.
- [Conflicts](../../tasks/draft-conflict-check-memorandum/gpt-6-sol-audit.md) — all 56 criteria; rule miscitation, inconsistent scoring branches and qualified screening/waiver/billing-scope concerns.
- [Draft interrogatories](../../tasks/draft-interrogatories/gpt-6-sol-audit.md) — all 50 criteria; unsupported procedural disclaimer, boilerplate and related-subpart-count cautions.
- [Motion in limine](../../tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt-6-sol-audit.md) — all 49 criteria; heightened scrutiny based on no prior federal testimony is unsupported; otherwise many strategies are explicitly source-backed, with qualified evidentiary concerns.
- [RFPs](../../tasks/draft-requests-for-production/gpt-6-sol-audit.md) — all 50 criteria; source-instruction conflict and inconsistent scoring thresholds; most constraints explicitly supplied.
- [Complaint summary](../../tasks/extract-key-terms-from-counterparty-complaint/gpt-6-sol-audit.md) — all 75 criteria; wrong statute, date arithmetic, hidden format and qualified waiver/response strategy issues.
- [Interrogatory objections](../../tasks/identify-issues-in-counterparty-interrogatories/gpt-6-sol-audit.md) — all 47 criteria; wrong deadline, invalid categorical objections, misattributed request and scoring ambiguity.
- [Invoice](../../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt-6-sol-audit.md) — all 49 criteria; substantive source reconciliation, airfare policy, unsupported budget conclusion and qualified reduction/notification concerns.

## Interpretation and limitations

A rubric may reasonably require an issue or defensive argument grounded in the source without guaranteeing that argument wins. The reports distinguish definite legal/factual/source mismatches from contestable advocacy, tactical preferences, and incomplete verification. Generic or numerical presentation demands are flagged where absent from prompt and reviewed source instructions; they should not be equated with major substantive legal errors.

DOCX paragraphs are extraction order, labeled P#, including table cells; workbook references are XML worksheet number and Excel row/cell. Extracted originals are saved alongside each audit. Native formatting/checkmarks were not rendered. Legal links point to statutes, rules or judicial opinions, including reproductions of primary text. These are agent audit findings for parent integration, not human legal sign-off.

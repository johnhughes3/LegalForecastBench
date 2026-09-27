# Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

Rendered from [findings.json](gpt-6-sol-audit.json); the original AI classifications and qualifications are retained.

**Id:** B6-PT-1

**Status:** confirmed

**Severity:** high

## Criteria

- [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L150)

**Issue:** Accepts corporate-style LLC citizenship in jurisdictional statement.

**Basis:** Formation in Delaware and North Carolina offices do not establish an LLC citizenship or complete diversity. Court-required format specifically calls for citizenship. No member citizenship census supplied. Correct reservation of missing member facts should pass.

## Source pointers

- [pretrial-order-and-rules.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/pretrial-order-and-rules.docx) §III.A, sources.txt:2052
- task [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L150)

## Legal urls

- https://www2.ca3.uscourts.gov/opinarch/122561p.pdf

**Repair:** Require member citizenship analysis or explicit missing-information qualification; do not equate offices with citizenship.


**Id:** B6-PT-2

**Status:** confirmed

**Severity:** medium

## Criteria

- [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L382)

**Issue:** Conflates remaining three-year term with 2.5-year mitigation period.

**Basis:** EDA runs March 2021–February 2026. At March 2023 termination, Years 3–5 are three years. The 2.5 years starts when replacement distributor begins September 2023. [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L382) expressly labels 2.5 years the remainder of contract term; [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L294) correctly uses all three future MAPCs. Supplied summary-judgment opinion repeats the mistake.

## Source pointers

- [deposition-excerpts.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/deposition-excerpts.docx) Prescott testimony, sources.txt:678–686
- [summary-judgment-ruling.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/summary-judgment-ruling.docx) sources.txt:2402–2404
- task [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L294)/C-044/C-046

## Legal urls



**Repair:** Allow explicit correction: three-year gross loss horizon and 2.5-year replacement offset; accurately describe Holt argument.


**Id:** B6-PT-3

**Status:** arguable

**Severity:** medium

## Criteria

- [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L270)
- [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L278)
- [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L286)

**Issue:** Total-damages benchmark preserves full revenue shortfalls despite source recognizing margin issue.

**Basis:** [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L278)/C-034 correctly state revenue shortfalls, but [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L270) target total includes them at 100% and expressly permits only lease correction. Prescott concedes margin-adjusted past losses total $1,363,400, versus $4,010,000 revenue shortfall, pending legal ruling. A corrected past-profit damages figure should not be penalized.

## Source pointers

- [deposition-excerpts.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/deposition-excerpts.docx) Prescott, sources.txt:667–674
- [prescott-expert-report.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/prescott-expert-report.docx) damages calculation; task [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L270)

## Legal urls

- https://www.govinfo.gov/content/pkg/USCOURTS-paed-2_12-cv-01922/pdf/USCOURTS-paed-2_12-cv-01922-4.pdf

**Repair:** Accept a justified margin adjustment and distinguish purchase shortfall from lost profits or separately supported price recovery.


**Id:** B6-PT-4

**Status:** arguable

**Severity:** low

## Criteria

- [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L54)

**Issue:** Required earliest discovery date excludes record-supported fall 2022 inquiry notice.

**Basis:** Hausman says concerns arose in fall 2022, and fraud was added by amendment after late-2023 discovery. [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L54) demands discovery no earlier than early 2023. Filing remains plausibly timely even if inquiry notice occurred fall 2022; exact date is a disputed diligence question.

## Source pointers

- [deposition-excerpts.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/deposition-excerpts.docx) Hausman, sources.txt:540–554
- [summary-judgment-ruling.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/documents/summary-judgment-ruling.docx) reserved limitations issue

## Legal urls

- https://www.paed.uscourts.gov/sites/paed/files/opinions/15-1063_opinion.pdf

**Repair:** Accept supported discovery-rule position without insisting on an unnecessarily late knowledge date.

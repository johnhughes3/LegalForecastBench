# Batch 3 blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Reviewed 9 tasks, 575 criteria, and 133 supplied source files. Blind rubric/prompt/source audit. All criteria considered; relevant source passages inspected, not a verbatim audit of all documents. No solver outputs read or source repository edits. Findings count groups rather than unique underlying legal doctrines; affected criterion categories may overlap. No confirmed defect identified does not mean independently certified correct.

Findings: 30 confirmed, 29 arguable, 2 unverified. Counts represent grouped findings, not tasks or unique legal doctrines.

| Task | Criteria | Files | Confirmed | Arguable | Unverified |
|---|---:|---:|---:|---:|---:|
| [analyze-counterpartys-motion-for-summary-judgment](../../tasks/analyze-counterpartys-motion-for-summary-judgment/gpt-6-sol-audit.md) | 32 | 9 | 1 | 1 | 1 |
| [compare-document-production-against-discovery-requests](../../tasks/compare-document-production-against-discovery-requests/gpt-6-sol-audit.md) | 46 | 8 | 4 | 2 | 0 |
| [draft-defective-industrial-equipment-product-liability](../../tasks/draft-defective-industrial-equipment-product-liability/gpt-6-sol-audit.md) | 79 | 9 | 4 | 4 | 1 |
| [draft-litigation-discovery-responses](../../tasks/draft-litigation-discovery-responses/gpt-6-sol-audit.md) | 61 | 7 | 4 | 2 | 0 |
| [draft-motion-to-dismiss-brief](../../tasks/draft-motion-to-dismiss-brief/gpt-6-sol-audit.md) | 89 | 24 | 4 | 5 | 0 |
| [draft-responses-to-requests-for-production](../../tasks/draft-responses-to-requests-for-production/gpt-6-sol-audit.md) | 45 | 7 | 2 | 2 | 0 |
| [extract-scope-terms-from-matter-plan](../../tasks/extract-scope-terms-from-matter-plan/gpt-6-sol-audit.md) | 76 | 6 | 2 | 3 | 0 |
| [research-corporate-veil-piercing-standards-across-target-jurisdictions](../../tasks/research-corporate-veil-piercing-standards-across-target-jurisdictions/gpt-6-sol-audit.md) | 65 | 8 | 5 | 3 | 0 |
| [review-privilege-log-clawback-review](../../tasks/review-privilege-log-clawback-review/gpt-6-sol-audit.md) | 82 | 55 | 4 | 7 | 0 |

Highest priority repairs:

- Texas DTPA exemptions conflated; wrong thresholds and legal tests in MTD packet.
- Discovery-production census requires zero RFP16 despite 36 coded entries and wrong overall counts.
- Ohio veil test superseded; Texas independent single-business-enterprise rejection understated; financial ratio denominator incorrect.
- UCC industrial-goods consequential-damage rule, warranty accrual and LLC citizenship errors.
- Privilege former-employee and work-product rules overbroad; mandatory deadline absent.

Each task folder contains audit.md, audit.json, criteria.txt and extracted sources.txt. Paragraph pointers refer to extracted DOCX paragraph numbering; spreadsheet pointers identify worksheet XML and cells. Primary legal URLs appear in each audit. No edits were made to the supplied repository. No paid API calls, solver-output inspection, publication, runtime edits, or beads changes occurred.

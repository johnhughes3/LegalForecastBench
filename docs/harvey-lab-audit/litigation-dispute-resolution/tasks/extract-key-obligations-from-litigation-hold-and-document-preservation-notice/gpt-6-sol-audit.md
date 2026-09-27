# Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

Rendered from [findings.json](gpt-6-sol-audit.json); the original AI classifications and qualifications are retained.

**Id:** B6-LH-1

**Status:** confirmed

**Severity:** high

## Criteria

- [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22)
- [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30)

**Issue:** Mandates a nonexistent date-range contradiction.

**Basis:** Notice ¶12 defines 2019 onward unless otherwise specified. ¶47 expressly says notwithstanding ¶12 and extends financial records to 2017. This is an explicit exception, not conflicting instructions. Additional burden [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L38) remains valid.

## Source pointers

- [doj-preservation-notice.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents/doj-preservation-notice.docx) ¶12 and ¶47, sources.txt:70–71,166–167

## Legal urls



**Repair:** Credit extracting the clear financial-record exception; do not require DOJ clarification of a manufactured inconsistency.


**Id:** B6-LH-2

**Status:** confirmed

**Severity:** high

## Criteria

- [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46)
- [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54)
- [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62)

**Issue:** Mandates a false contradiction between all-HCP and five-HCP requirements.

**Basis:** ¶23 explicitly covers all HCPs whether named or not. ¶24 starts Without limiting any other provision and adds duties for Exhibit D contacts. Nothing limits ¶23 to five. Broader coverage remains required directly, not merely a conservative interim interpretation.

## Source pointers

- [doj-preservation-notice.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents/doj-preservation-notice.docx) ¶23–24, sources.txt:103–106

## Legal urls



**Repair:** Accept cumulative broad and named-contact obligations; remove required narrow-reading counterfactual and contradiction.


**Id:** B6-LH-3

**Status:** confirmed

**Severity:** low

## Criteria

- [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70)

**Issue:** Destruction period source is internally inconsistent.

**Basis:** Destruction email summary says 4.2M records from 2019–2021, but category 2 includes 1.4M sales/field records through December 2022. Rubric repeats the narrower summary as fact without accepting reconciliation.

## Source pointers

- [records-destruction-confirmation.eml](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents/records-destruction-confirmation.eml) Categories and Volume of Records Destroyed, category 2; sources.txt:574–587

## Legal urls



**Repair:** Allow 2019–2022, with source-conflict note; retain 4.2M approximate total.


**Id:** B6-LH-4

**Status:** arguable

**Severity:** low

## Criteria

- [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L182)
- [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214)

**Issue:** Legal analogies need limits for private-employer imaging and criminal investigation preservation.

**Basis:** Privacy/consent analysis is warranted, but Fourth Amendment requires government action and civil-discovery backup cases do not displace notice terms or criminal preservation duties. Criteria offer alternatives, so a careful answer can pass without error.

## Source pointers

- [doj-preservation-notice.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents/doj-preservation-notice.docx) mobile imaging and backup obligations
- task [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L182)/C-025

## Legal urls



**Repair:** Preserve criteria as risk spotting while accepting state-action qualification and distinction between preservation and production proportionality.

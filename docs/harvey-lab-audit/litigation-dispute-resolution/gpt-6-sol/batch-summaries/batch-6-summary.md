# Batch 6 independent blind audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Eight tasks; 413 of 413 criteria read. All 87 supplied documents text-extracted and inventoried; targeted relevant passages reviewed. This is not a full line-by-line or rendered-document review. Original supplied pleadings were inspected; no solver outputs were accessed.

Findings: 18 confirmed clusters and 14 arguable clusters. A cluster may cover several criteria; these are not per-criterion error counts.

Most consequential confirmed findings:

- draft-complaint [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228) invents NC TSPA preemption under nonexistent §66-157(a); [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194) imposes an unsupported exfiltration causation story.
- draft-federal-complaint-drafting [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L21) requires unsupported member citizenship; source memo cites a personal-guaranty section absent from PAA.
- draft-motion-for-summary-judgment mixes 11 unrelated employment-case documents into a 17-document contract-case packet; [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L77)/C-009 ignore an express nonreliance clause; local-rule number is wrong.
- draft-pretrial-statement [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L150) accepts an incorrect LLC citizenship formula; [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L382) conflates remaining contract term and mitigation period.
- preservation task C-001/C-002 and C-004–C-006 demand identifying contradictions expressly resolved by the notice itself.
- counterparty-complaint C-008 requires denying specific pleaded misappropriation facts; C-012 invents spouse membership; C-005 arithmetic exemplar is slightly wrong.
- privilege review C-014 requires unsupported no-need-to-know findings for regulatory analysts; C-043/C-045 have unmatched PASS/FAIL thresholds.

Calibration: settlement C-019 is arguable, not confirmed: reduction can be correct for noneconomic damages, but cannot be applied mechanically to economic loss when Greenfield exceeds 50% fault. Most privilege-waiver outcomes, common-interest writing concerns, and in-camera recommendations are arguable, with law and factual qualifications in the task findings.

Per-task findings.json contains exact criterion IDs, source pointers, primary legal URLs where researched, and proposed repair. coverage.json explicitly lists each criterion. sources.txt preserves extracted searchable text, not rendered originals.

Unverified: no comprehensive visual review, embedded-image review, native spreadsheet-formula review, or separate legal research for every unflagged criterion. These limitations should accompany any synthesis; no clean bill of health is claimed for unflagged criteria.

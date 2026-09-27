# Extract Scope Terms from Matter Plan — Structured Extraction Report

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

All76 criteria read; all6 files extracted and relevant sections/spreadsheet data/negotiation-email text inspected. No external law required to resolve these contract extraction findings; no legal enforceability opinion offered. No solver output accessed.

## F1 — confirmed false gap

Criteria: [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L491)

Elaine Marchetti rate is expressly assigned in engagement letter itself and repeated in matter plan. Absence of an Of Counsel row does not leave her rate ambiguous; rubric demands artificial uncertainty.

Evidence: [engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/engagement-letter.docx) p97 authorizes Marchetti onlyWS4/5,billed Partner rate; [matter-plan.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan.docx) p227 specifies$685.

Repair: Extract express named authorization and distinguish individual rate schedule administration from missing rate.

## F2 — confirmed source contradiction

Criteria: [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L499)

Rubric says$55 contract reviewer rate not listed in engagement-letter rate schedule, but ExhibitA has express note listing$55 and cross-reference. Individual reviewer approval may still need verification; categorical rate omission is false.

Evidence: [engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/engagement-letter.docx) p47 and ExhibitA p213; OCG p40 permits attached schedule OR subsequent written approval.

Repair: Replace missing-rate finding with conditional unnamed-timekeeper approval inquiry.

## F3 — arguable resolved conflict

Criteria: [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L515)

There is a literal general-guideline/specific-engagement difference, but engagement expressly controls; compelling unresolved conflict characterization would mislead. Criterion can be satisfied by flagging and resolving the hierarchy.

Evidence: [engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/engagement-letter.docx) p144,p150-p151; [matter-plan.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan.docx) p420; OCG p66-p67.

Repair: Credit resolved express override; do not require obtaining redundant new approval.

## F4 — arguable compatible deadlines

Criteria: [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L507)

Feb28 completion satisfies no later than90days before June1 (Mar3). Different listed dates warrant clarification, but an earlier operational deadline does not inherently conflict with outside limit.

Evidence: [matter-plan.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan.docx) p170,p246,p275.

Repair: Allow explaining earlier target versus latest permissible date; avoid forced contradiction.

## F5 — arguable incomplete payment phrasing

Criteria: [C-069](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L563)

Criterion says accrued fees payable within45days upon termination; source measures45days from final invoice submission, which may be up to30days after termination.

Evidence: [engagement-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/engagement-letter.docx) p127; [matter-plan.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/documents/matter-plan.docx) p434.

Repair: State triggering event explicitly and credit accurate potentially75day timeline.

## Source cross-checks

- [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L19)-C-013: all sevenWS and sixexclusions checked against matter-plan§§3-4 and revision1; WS4 allocation/coordinating counsel source-supported.
- [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L123)-C-038/C-049-C-057/C-067-C-070/C-072/C-074: engagement letter rates,caps,settlement tiers,staffing,termination,waiver and budget workbook inspected. Contract reviewer accounting differs: feeWS6 in spreadsheet vs disbursement in matter-plan p155,p335; additional discrepancy worth flagging.
- [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L323)-C-048/C-068/C-073/C-075-C-076: matter-plan timeline/reporting and matter number checked; dates are source extraction,not endorsement of actual docket dates.
- [C-058](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L475)-C-059/C-064-C-066/C-071: genuine780K/760K difference; WS4 added320K exceeds212.5K threshold and addendum signed deputy/billing partner; aggregate-payments definition unresolved in negotiation emails; affiliate definition absent. EX6 futureMDL scope ambiguity reasonable.
- Additional source discrepancy: wind-down threshold engagement p129 >$2M versus matter-plan p436 ≥$2M, with engagement controlling. Criterion054 follows controlling version.

## Legal sources



## Criterion census

- [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L19): no confirmed defect identified in targeted audit
- [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L27): no confirmed defect identified in targeted audit
- [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L35): no confirmed defect identified in targeted audit
- [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L43): no confirmed defect identified in targeted audit
- [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L51): no confirmed defect identified in targeted audit
- [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L59): no confirmed defect identified in targeted audit
- [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L67): no confirmed defect identified in targeted audit
- [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L75): no confirmed defect identified in targeted audit
- [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L83): no confirmed defect identified in targeted audit
- [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L91): no confirmed defect identified in targeted audit
- [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L99): no confirmed defect identified in targeted audit
- [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L107): no confirmed defect identified in targeted audit
- [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L115): no confirmed defect identified in targeted audit
- [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L123): no confirmed defect identified in targeted audit
- [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L131): no confirmed defect identified in targeted audit
- [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L139): no confirmed defect identified in targeted audit
- [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L147): no confirmed defect identified in targeted audit
- [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L155): no confirmed defect identified in targeted audit
- [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L163): no confirmed defect identified in targeted audit
- [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L171): no confirmed defect identified in targeted audit
- [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L179): no confirmed defect identified in targeted audit
- [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L187): no confirmed defect identified in targeted audit
- [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L195): no confirmed defect identified in targeted audit
- [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L203): no confirmed defect identified in targeted audit
- [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L211): no confirmed defect identified in targeted audit
- [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L219): no confirmed defect identified in targeted audit
- [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L227): no confirmed defect identified in targeted audit
- [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L235): no confirmed defect identified in targeted audit
- [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L243): no confirmed defect identified in targeted audit
- [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L251): no confirmed defect identified in targeted audit
- [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L259): no confirmed defect identified in targeted audit
- [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L267): no confirmed defect identified in targeted audit
- [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L275): no confirmed defect identified in targeted audit
- [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L283): no confirmed defect identified in targeted audit
- [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L291): no confirmed defect identified in targeted audit
- [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L299): no confirmed defect identified in targeted audit
- [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L307): no confirmed defect identified in targeted audit
- [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L315): no confirmed defect identified in targeted audit
- [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L323): no confirmed defect identified in targeted audit
- [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L331): no confirmed defect identified in targeted audit
- [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L339): no confirmed defect identified in targeted audit
- [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L347): no confirmed defect identified in targeted audit
- [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L355): no confirmed defect identified in targeted audit
- [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L363): no confirmed defect identified in targeted audit
- [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L371): no confirmed defect identified in targeted audit
- [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L379): no confirmed defect identified in targeted audit
- [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L387): no confirmed defect identified in targeted audit
- [C-048](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L395): no confirmed defect identified in targeted audit
- [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L403): no confirmed defect identified in targeted audit
- [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L411): no confirmed defect identified in targeted audit
- [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L419): no confirmed defect identified in targeted audit
- [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L427): no confirmed defect identified in targeted audit
- [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L435): no confirmed defect identified in targeted audit
- [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L443): no confirmed defect identified in targeted audit
- [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L451): no confirmed defect identified in targeted audit
- [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L459): no confirmed defect identified in targeted audit
- [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L467): no confirmed defect identified in targeted audit
- [C-058](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L475): no confirmed defect identified in targeted audit
- [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L483): no confirmed defect identified in targeted audit
- [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L491): confirmed false gap
- [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L499): confirmed source contradiction
- [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L507): arguable compatible deadlines
- [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L515): arguable resolved conflict
- [C-064](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L523): no confirmed defect identified in targeted audit
- [C-065](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L531): no confirmed defect identified in targeted audit
- [C-066](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L539): no confirmed defect identified in targeted audit
- [C-067](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L547): no confirmed defect identified in targeted audit
- [C-068](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L555): no confirmed defect identified in targeted audit
- [C-069](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L563): arguable incomplete payment phrasing
- [C-070](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L571): no confirmed defect identified in targeted audit
- [C-071](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L579): no confirmed defect identified in targeted audit
- [C-072](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L587): no confirmed defect identified in targeted audit
- [C-073](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L595): no confirmed defect identified in targeted audit
- [C-074](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L603): no confirmed defect identified in targeted audit
- [C-075](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L611): no confirmed defect identified in targeted audit
- [C-076](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L619): no confirmed defect identified in targeted audit

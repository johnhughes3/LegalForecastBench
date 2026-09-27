# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

**F1 — confirmed — [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L260)**

Rubric requires finding a hardcopy preservation gap contradicted by actual hold.

Evidence: [hartwell-litigation-hold-memo.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/documents/hartwell-litigation-hold-memo.docx) section 2(b),(e) preserves inspection and QA records; section 5 paragraph 55 expressly prohibits discarding paper files, binders, notebooks or physical materials, and paragraph 59 directs segregation of physical files. Aldersgate assessment paragraphs 22,47 incorrectly says hardcopy materials are outside preservation scope. A specific inventory is prudent but absence of exact binder name does not mean no preservation directive.

Repair: Accept recognition that existing hold covers binders, with practical inventory/confirmation recommendation.

**F2 — arguable — [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L212), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L356)**

Conflates pleading particularity with evidence-based summary judgment strategy.

Evidence: [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L212) gives Rule 9(b) particularity as an example basis for early partial summary judgment. FRCP 9(b) governs pleading; Rule 56 asks whether genuine material factual dispute exists. Case-management order paragraphs 83–84 itself encourages early sufficiency issues, but a correct plan may use Rule 12(c) for pleading and Rule 56 for merits.

Repair: Explicitly accept correct procedural vehicle and allow assessment that particularity is adequately pleaded.

**F3 — arguable — [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L236), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L244)**

Overstates waiver risk from internal employee consultation or mentioning that consultation.

Evidence: Pre-litigation letter April 22 says counsel consulted QA; [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L236) refers broadly to sharing with non-attorney personnel. Upjohn protects qualifying confidential employee-counsel communications; adversary disclosure is distinct. Mere consultation statement does not necessarily reveal privileged substance or create subject-matter waiver.

Repair: Require distinguishing internal privileged consultation from disclosure of substance to adversaries; accept reasoned no-waiver conclusion.

**F4 — arguable — [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L196), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L204), [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L300)**

Mandatory phasing and custodian rankings are unrequested strategic choices.

Evidence: Prompt requests Rule 26(f) discovery plan; case-management order section VII encourages parties to discuss whether phasing helps, but does not order a liability-first plan. A supported integrated schedule could be sound.

Repair: Allow a reasoned alternative schedule and prioritization expressed without tiers.

**F5 — unverified — [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L124)**

General Ohio fraud exception not independently resolved to controlling case in this audit.

Evidence: Complaint paragraph 91 asserts the proposition and the rubric uses qualified generally/potentially language. Primary court search located relevant litigation over willful/wanton limits, but not sufficiently specific controlling authority to mark this broad proposition correct or defective.

Repair: Validate against controlling Ohio decisions before revising.

Coverage: 65/65 criteria, 10/10 documents, criterion-directed source inspection. 65 criterion wordings examined; 10 documents inspected by criterion-directed search/read. Source report supports installation-defense discovery as a possible secondary factor despite primary foundry defect. FRCP preservation, proportionality and subpoena provisions checked; Ohio cap proposition remains unverified.

Legal sources:
- https://www.uscourts.gov/sites/default/files/2025-02/federal-rules-of-civil-procedure-dec-1-2024.pdf
- https://www.govinfo.gov/content/pkg/USREPORTS-449/pdf/USREPORTS-449-383.pdf

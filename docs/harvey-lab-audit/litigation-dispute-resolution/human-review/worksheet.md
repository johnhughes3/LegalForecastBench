# Human review worksheet: sampled AI-flagged criteria

Seeded draw of 25 criteria; see the [review protocol](README.md) before starting. Fill in each item's three fields in place, replacing the italic placeholder with one listed value. `uv run python scripts/harvey_review_sample.py tally` counts the verdicts.

## 1. Assess Reasonableness of Staffing Levels on Litigation Invoice — C-049

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-reasonableness-of-staffing-levels-on-litigation-invoice/task.json#L403) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-reasonableness-of-staffing-levels-on-litigation-invoice/documents) · [Task audit page](../tasks/assess-reasonableness-of-staffing-levels-on-litigation-invoice/README.md)

**Calculates budget overage percentage as approximately 17%**

> PASS if the memo calculates the percentage by which the attorney fee subtotal ($193,372.50) exceeds the approved budget ceiling ($165,000) as approximately 17% (exact figure is 17.2%). FAIL if no percentage overage calculation is provided or if the percentage stated is materially incorrect (off by more than 2 percentage points).

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both flagged, different strength (one problematic, one arguable). GPT-6 Sol: problematic; Claude Opus 5.5: arguable (blind pass: problematic).

- **GPT-6 Sol:** F1: Mandatory figures follow inconsistent invoice summaries without allowing reconciliation to line entries. (confirmed)
- **Claude Opus 5.5:** O2: The invoice-level fee and budget figures follow the invoice face amount, which does not reconcile to its own line items
- **Claude Opus 5.5 on GPT-6 Sol:** F1 → arguable: I re-ran the check. The 117 Time Detail entries total 483.5 hrs and $215,680. The Summary and the hardcoded SUBTOTAL show 422.5 hrs and $193,372.50. Barros comes to 49 hrs in the detail (45 in the Summary), Sengupta 27 (27.5), Tate 154.5 (120). The per-timekeeper criteria fix the Summary figures, so a reviewer who works from the line items fails them. The face-amount criteria (C-028/032/045/046/049) report what was actually billed, which a competent memo usually states. Those carry lower risk, so I rate them arguable.

Full reports: [GPT-6 Sol](../tasks/assess-reasonableness-of-staffing-levels-on-litigation-invoice/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/assess-reasonableness-of-staffing-levels-on-litigation-invoice/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 2. Categorize Document Production Set by Relevance and Privilege — Privilege Log and Relevance Classification Report — C-012

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/categorize-document-production-set-by-relevance-and-privilege/task.json#L110) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/categorize-document-production-set-by-relevance-and-privilege/documents) · [Task audit page](../tasks/categorize-document-production-set-by-relevance-and-privilege/README.md)

**ISSUE_003: DOC_012 identified as Partially Privileged**

> PASS if DOC_012 (chandrasekaran-meeting-notes-aug28.docx, Chandrasekaran's handwritten meeting notes from August 28, 2023) is classified as Partially Privileged. FAIL if classified as fully Privileged or Not Privileged.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: arguable).

- **GPT-6 Sol:** Arguable / needs jurisdiction-specific verification: item 2: C-012–014
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable / needs jurisdiction-specific verification: item 2 → not_a_defect: On Sol's theory, no defect. The notes put 'Ops Discussion' sections (deliverables, PIP policy, restructuring) under headings separate from 'Legal Strategy', so partial privilege with redaction is the mainstream call, and C-012 is sound. C-013/C-014 remain arguable for a different reason: they read only privilege-log.docx. Dual-purpose and redaction analysis placed in the report would not be seen (see O7).

Full reports: [GPT-6 Sol](../tasks/categorize-document-production-set-by-relevance-and-privilege/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/categorize-document-production-set-by-relevance-and-privilege/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 3. Compare Document Production Against Discovery Requests — Discovery Gap Analysis Memorandum — C-029

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/compare-document-production-against-discovery-requests/task.json#L243) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/compare-document-production-against-discovery-requests/documents) · [Task audit page](../tasks/compare-document-production-against-discovery-requests/README.md)

**ISSUE_011: Notes only 5 documents actually relate to counterclaim damages**

> PASS if the memorandum notes that only 5 of the 14 documents coded to RFP 27 (MLC-004056 through MLC-004102) actually relate to Pacific Corridor's volume shortfall and the counterclaim damages calculation, meaning the counterclaim damages support is thin. FAIL if this is not noted.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: problematic. GPT-6 Sol: problematic; Claude Opus 5.5: problematic (blind pass: problematic).

- **GPT-6 Sol:** F2: Index lists 332 numbered documents, not 312. RFP27 has 15 coded rows: 8 Greystone rows and 7 Pacific Corridor rows (including two earlier entries), not requi… (confirmed count contradiction)
- **Claude Opus 5.5:** O1: RFP 27 counts ('9 of 14' Greystone; 'only 5' relate to damages) contradict the row-level production index
- **Claude Opus 5.5 on GPT-6 Sol:** F2 → problematic: I re-counted the index. 15 rows carry an RFP 27 code: rows 118 ('16, 27'), 306 ('25, 27') and 309-321. Of these, 8 concern Greystone (MLC-003980 to MLC-004055), not 9. Row 306 is itself the counterclaim damages spreadsheet, so 'only 5 relate' is false. The index has 332 numbered rows, while the summary says 312. C-043's 'at least two of' condition lets a memo pass using the correct page count and Bates range, so it carries only minor risk.

Full reports: [GPT-6 Sol](../tasks/compare-document-production-against-discovery-requests/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/compare-document-production-against-discovery-requests/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 4. Draft Case Assessment Memorandum — Litigation Risk Analysis for Distribution Agreement Dispute — C-025

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-case-assessment-memorandum/task.json#L213) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-case-assessment-memorandum/documents) · [Task audit page](../tasks/draft-case-assessment-memorandum/README.md)

**ISSUE_007: Recommends motion to dismiss on unjust enrichment**

> PASS if the memo recommends filing a motion to dismiss (or motion for judgment on the pleadings, or similar dispositive motion) targeting the unjust enrichment claim (Count IV) on the ground that an express contract governs the parties' relationship. FAIL if no such motion recommendation is made regarding the unjust enrichment claim.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: arguable. GPT-6 Sol: arguable; Claude Opus 5.5: arguable (blind pass: arguable).

- **GPT-6 Sol:** F2: Compels dismissal recommendation despite an expressly alternative unjust-enrichment pleading. (arguable)
- **Claude Opus 5.5:** O8: C-025 requires recommending a motion to dismiss an unjust-enrichment claim pleaded in the alternative
- **Claude Opus 5.5 on GPT-6 Sol:** F2 → arguable: C-024 only requires spotting the express-contract vulnerability. Its FAIL condition is 'does not identify this vulnerability', which is sound. C-025 requires recommending a dispositive motion. Complaint ¶127 pleads unjust enrichment expressly in the alternative, and Rule 8(d) alternative pleading often survives at the pleading stage. A competent memo could flag the weakness and defer the challenge to summary judgment, or rely on OUTSA displacement instead. I did not verify Sol's case citation.

Full reports: [GPT-6 Sol](../tasks/draft-case-assessment-memorandum/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-case-assessment-memorandum/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 5. Draft Conflict Check Memorandum for Litigation Engagement Clearance — C-030

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/task.json#L250) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/documents) · [Task audit page](../tasks/draft-conflict-check-memorandum/README.md)

**ISSUE_005: Recommends screening or removal of Caleb Strand**

> PASS if the memo recommends that Caleb Strand be screened from the engagement or removed from the proposed staffing. FAIL if no such recommendation is made.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: arguable. GPT-6 Sol: arguable; Claude Opus 5.5: arguable (blind pass: not flagged).

- **GPT-6 Sol:** Arguable concerns: item 2: C-030 mandates removal/screening of Caleb rather than allowing reasoned safeguards.
- **Claude Opus 5.5:** O6: C-030 accepts only screening or removal for Caleb Strand, while C-024 accepts clearance with conditions for Chow
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable concerns: item 2 → arguable: Caleb is a staffed associate. His sister is an IP paralegal at the adverse party in a trade-secret case, and they share an apartment with separate workspaces. Screening or removing him is the prudent call, but clearing him with a home-confidentiality protocol and Verano's informed consent is a defensible minority position. C-024, the Chow criterion, expressly accepts 'clearance with conditions', and C-030 does not. That asymmetry could fail a reasoned conditional clearance.

Full reports: [GPT-6 Sol](../tasks/draft-conflict-check-memorandum/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-conflict-check-memorandum/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 6. Draft Conflict Check Memorandum for Litigation Engagement Clearance — C-049

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/task.json#L402) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/documents) · [Task audit page](../tasks/draft-conflict-check-memorandum/README.md)

**ISSUE_011: Recommends integrating annual disclosure questionnaires with ConflictTracker**

> PASS if the memo recommends that annual conflict-disclosure questionnaires be cross-referenced with or integrated into the ConflictTracker system. FAIL if no recommendation about integrating disclosure questionnaires with the conflicts database is made.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O5: Three criteria each require a specific firm-wide process reform beyond clearing this engagement

Full reports: [GPT-6 Sol](../tasks/draft-conflict-check-memorandum/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-conflict-check-memorandum/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 7. Draft Counterclaim Against Plaintiff for Breach of Joint Development Agreement — C-045

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/task.json#L372) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/documents) · [Task audit page](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md)

**Count: Patent Infringement (ISSUE_005)**

> PASS if the counterclaim includes a separate count for patent infringement under 35 U.S.C. § 271, alleging that the LumiSense 400 infringes U.S. Patent No. 11,234,567 covering the SensorCore™ architecture. FAIL if no patent infringement counterclaim is asserted.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** Arguable / unverified concerns: item 4: C-045–047
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable / unverified concerns: item 4 → not_a_defect: The memo does not list a patent count. But it tells the team to 'independently evaluate whether other theories are available,' and the Ayers report (§ 8, Opinion 3) compares Claim 1 element by element and concludes the LumiSense 400 practices '287 at least the independent claims. JDA § 13.2 expressly contemplates patent infringement claims. A competent drafter would plead it. Sol's point that the patent was not independently verified is not a rubric defect.

Full reports: [GPT-6 Sol](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 8. Draft Counterclaim Against Plaintiff for Breach of Joint Development Agreement — C-046

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/task.json#L380) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/documents) · [Task audit page](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md)

**Patent Infringement Count: Patent Number Cited**

> PASS if the patent infringement count specifically identifies U.S. Patent No. 11,234,567. FAIL if the patent number is omitted or incorrect in the patent infringement count.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** Arguable / unverified concerns: item 4: C-045–047
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable / unverified concerns: item 4 → not_a_defect: The memo does not list a patent count. But it tells the team to 'independently evaluate whether other theories are available,' and the Ayers report (§ 8, Opinion 3) compares Claim 1 element by element and concludes the LumiSense 400 practices '287 at least the independent claims. JDA § 13.2 expressly contemplates patent infringement claims. A competent drafter would plead it. Sol's point that the patent was not independently verified is not a rubric defect.

Full reports: [GPT-6 Sol](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 9. Draft Case Assessment Memorandum for Defective Industrial Equipment Product Liability Claim — C-003

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-defective-industrial-equipment-product-liability/task.json#L36) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-defective-industrial-equipment-product-liability/documents) · [Task audit page](../tasks/draft-defective-industrial-equipment-product-liability/README.md)

**Executive Summary mentions death of Marco Reyes**

> PASS if the Executive Summary mentions the death of Marco Reyes. FAIL if the fatality is not mentioned in the Executive Summary.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** F7: Prompt requests case assessment but no Executive Summary; five criteria mandate placement there rather than substantively accurate discussion elsewhere. (arguable formatting overconstraint)
- **Claude Opus 5.5 on GPT-6 Sol:** F7 → not_a_defect: An executive summary is a standard part of a case assessment memo, so it is implicit rather than hidden; C-067 lists it too. C-002 through C-005 ask for facts any competent summary of this matter would contain: the incident, the death, the injuries and Dalton's losses. These criteria are demanding checklist items, not defects.

Full reports: [GPT-6 Sol](../tasks/draft-defective-industrial-equipment-product-liability/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-defective-industrial-equipment-product-liability/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 10. Draft Case Assessment Memorandum for Defective Industrial Equipment Product Liability Claim — C-026

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-defective-industrial-equipment-product-liability/task.json#L220) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-defective-industrial-equipment-product-liability/documents) · [Task audit page](../tasks/draft-defective-industrial-equipment-product-liability/README.md)

**OSHA LOTO citation identified with specific violation and penalty**

> PASS if the memo identifies the OSHA serious citation for LOTO deficiency under 29 CFR 1910.147(c)(4)(i) with a penalty of $18,900. FAIL if this specific citation, regulation, or penalty amount is not referenced.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: problematic; Claude Opus 5.5: not flagged (blind pass: arguable).

- **GPT-6 Sol:** F5: Source purports to issue private-employer OSHA citations and require contest/payment to Ohio Division of Safety & Hygiene. Ohio has no OSHA-approved State Pl… (confirmed source-law inconsistency)
- **Claude Opus 5.5 on GPT-6 Sol:** F5 → not_a_defect: The document defect is real: osha.gov confirms Ohio has no OSHA-approved State Plan and is under federal jurisdiction, yet the citation comes from an Ohio agency under R.C. Ch. 4167. But C-026 and C-027 only require reciting the regulation and penalty. C-073's 15-working-day contest window matches federal practice. A memo that flags the anomaly still passes all three. I keep the defect as a finding tied to no criterion.

Full reports: [GPT-6 Sol](../tasks/draft-defective-industrial-equipment-product-liability/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-defective-industrial-equipment-product-liability/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 11. Draft Discovery Plan Memorandum for Breach of Contract and Fraud Defense — C-036

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/task.json#L300) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-discovery-plan-memorandum/documents) · [Task audit page](../tasks/draft-discovery-plan-memorandum/README.md)

**Provides custodian priority rankings**

> PASS if the memo provides priority rankings or tiers for custodians (e.g., high/medium/low priority, or Tier 1/Tier 2, or similar prioritization). FAIL if custodians are listed without any indication of relative priority.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** F4: Mandatory phasing and custodian rankings are unrequested strategic choices. (arguable)
- **Claude Opus 5.5 on GPT-6 Sol:** F4 → not_a_defect: CMO §VII encourages parties to discuss phasing but does not require it. With the Ostrowski emails undercutting any early fraud motion, a defense lawyer could reasonably consider phasing and decline it, and C-023/C-024 would fail that memo. So arguable. C-036 is implicit: CMO ESI topic 8 is 'Custodian identification and prioritization', Aldersgate supplies tiers, and the criterion accepts any 'similar prioritization'.

Full reports: [GPT-6 Sol](../tasks/draft-discovery-plan-memorandum/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-discovery-plan-memorandum/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 12. Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute — C-025

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L214) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/documents) · [Task audit page](../tasks/draft-federal-complaint-drafting/README.md)

**ISSUE_012: Complaint requests injunctive relief**

> PASS if the prayer for relief includes a request for preliminary and/or permanent injunctive relief — specifically to enforce the non-solicitation provision and prevent Graydon from continuing to divert Fund III investor prospects to competing funds. FAIL if no injunctive relief is requested.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O8: Injunctive relief made mandatory although the intake memo leaves it as an open question for the partner

Full reports: [GPT-6 Sol](../tasks/draft-federal-complaint-drafting/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-federal-complaint-drafting/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 13. Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case — C-008

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L75) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/documents) · [Task audit page](../tasks/draft-interrogatories/README.md)

**Definitions section defines 'Document' or 'Documents'**

> PASS if the Definitions section includes a definition of 'Document' or 'Documents' that is broad enough to encompass electronically stored information (ESI), emails, and physical documents. FAIL if there is no definition of 'Document' or it is so narrow as to exclude electronic records.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** Arguable/format concerns: item 1: C-007–010/C-015 require named Definitions-section boilerplate.
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable/format concerns: item 1 → not_a_defect: Definitions of Identify (name, position, employer, contact), Document (including ESI), Communication, and You/Your are standard components of a federal interrogatory set. They are implicit in the requested work product, not hidden requirements. A standalone 'Describe' definition is common but optional, and C-015 fails a set that puts narrative requirements elsewhere. So only C-015 is arguable.

Full reports: [GPT-6 Sol](../tasks/draft-interrogatories/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-interrogatories/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 14. Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case — C-026

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L219) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/documents) · [Task audit page](../tasks/draft-interrogatories/README.md)

**Interrogatory re: USB drive or CMT files on Veridian systems**

> PASS if at least one interrogatory asks whether Oshiro's USB drive (referencing serial number CX-8827491 or otherwise describing the external storage device) was ever connected to, accessed from, or present on any Veridian system, device, or network, or asks whether any CMT files or materials were ever possessed, accessed, viewed, or copied by Veridian or its employees. FAIL if no interrogatory addresses the USB drive or CMT files on Veridian systems.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** Arguable/format concerns: item 3: C-026/C-048 minor internal tension.
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable/format concerns: item 3 → not_a_defect: The two criteria do not conflict. C-026 tests topic coverage; C-048 tests precision, and one interrogatory can meet both. Serial CX-8827491 appears consistently in the complaint, TRO, hold letter, Ashcroft report and Yilmaz report. Using the record identifier to prevent evasive answers is ordinary good drafting. The criterion is demanding but reasonable.

Full reports: [GPT-6 Sol](../tasks/draft-interrogatories/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-interrogatories/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 15. Draft Discovery Responses and Objections to RFAs and RFPs in Breach of Supply Agreement Litigation — C-028

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-discovery-responses/task.json#L234) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-discovery-responses/documents) · [Task audit page](../tasks/draft-litigation-discovery-responses/README.md)

**ISSUE_011: Identifies RFA No. 20 as calling for a legal conclusion**

> PASS if the plan identifies that RFA No. 20 (asking Prismavale to admit the products were 'not merchantable as defined by the Uniform Commercial Code') calls for a legal conclusion regarding UCC § 2-314 merchantability and recommends objecting on that basis. FAIL if the plan does not identify the legal conclusion problem with RFA No. 20.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both flagged, different strength (one problematic, one arguable). GPT-6 Sol: problematic; Claude Opus 5.5: arguable (blind pass: arguable).

- **GPT-6 Sol:** F1: Merchantability of these identified products is application of law to fact, expressly permitted by Rule36(a)(1)(A). Rubric mandates an objection specifically… (confirmed legal defect)
- **Claude Opus 5.5:** O4: C-029 fails a straight, well-grounded denial of RFA 20 because it lacks a 'legal conclusion' objection
- **Claude Opus 5.5 on GPT-6 Sol:** F1 → arguable: I read Rule 36(a)(1)(A) in this session. It expressly permits requests about 'the application of law to fact,' so C-029's alternative objection ground is invalid, and a straight denial of RFA 20 grounded in conformance at shipment fully complies with Rule 36(a)(4). But the firm's precedent objects on this basis, courts split on 'legal conclusion' objections to UCC-merchantability requests, and most competent drafters would add the objection defensively. The criteria therefore misgrade only some competent answers. I rate this arguable, not confirmed.

Full reports: [GPT-6 Sol](../tasks/draft-litigation-discovery-responses/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-litigation-discovery-responses/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 16. Draft Motion in Limine to Exclude Expert Testimony and Prejudicial Evidence in Commercial Breach of Contract Case — C-009

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L84) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/documents) · [Task audit page](../tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/README.md)

**ISSUE_004: Identifies the $11,000 arithmetic discrepancy**

> PASS if the motion identifies that the sum of Marchetti's five itemized damages categories totals $14,211,000, but her report states total damages as $14,200,000, creating an $11,000 discrepancy. FAIL if this arithmetic error is not identified.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** Arguable concerns: item 4: C-009–010 arithmetic discrepancy is real but minor.
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable concerns: item 4 → not_a_defect: The $14,211,000 vs $14,200,000 gap is accurate (Dep. 92–93). Memo §III.F tells the drafter to use it as the closing cumulative-reliability point in the Daubert section. C-010 asks for exactly that link, and it does not require arguing that the error alone warrants exclusion or penalize a proportionate description. A brief but explicit cumulative link is not 'only in passing', so a memo-following motion passes.

Full reports: [GPT-6 Sol](../tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 17. Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute — C-037

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/documents) · [Task audit page](../tasks/draft-motion-to-dismiss-brief/README.md)

**ISSUE_008 — Cites Delaware parol evidence authority**

> PASS if the motion brief cites relevant Delaware authority on the parol evidence rule and integration clauses, such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. FAIL if no Delaware parol evidence authority is cited.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O9: C-037 lists SIGA v. PharmAthene as Delaware parol-evidence authority, but that opinion does not address integration or parol evidence

Full reports: [GPT-6 Sol](../tasks/draft-motion-to-dismiss-brief/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-motion-to-dismiss-brief/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 18. Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute — C-045

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/documents) · [Task audit page](../tasks/draft-motion-to-dismiss-brief/README.md)

**ISSUE_010 — References Arcadia's own delays contributing to Go-Live delay**

> PASS if the motion brief identifies Arcadia's own contributing failures, including the 45-day Project Manager gap (Kevin Liu's departure) and/or the 75-day late API specifications, as causes of the Go-Live delay. FAIL if Arcadia's own contributory delays are not mentioned.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: arguable. GPT-6 Sol: arguable; Claude Opus 5.5: arguable (blind pass: arguable).

- **GPT-6 Sol:** F6: Criterion requires favorable extrinsic facts in a pleadings motion: internal investigation memo,status reports,ticket resolution,and negotiation history. Con… (arguable mandatory factual advocacy)
- **Claude Opus 5.5:** O12: The causation criteria require a 12(b)(6) brief to adopt the disputed version of a status report the FAC contests
- **Claude Opus 5.5 on GPT-6 Sol:** F6 → arguable: CO-004 is a signed contract document the FAC references (Exhibit C, ¶47(d)), and its §5.1 contains Arcadia's own acknowledgment about Linden Park, so C-043 is proper. C-054 requires an internal Arcadia memo the FAC never references, which a 12(b)(6) brief should not rely on. C-045 and C-041 require adopting disputed status-report causation. C-075 relies on a counsel-commissioned report and is unclear when tickets are omitted. The negotiation facts in C-082 are partly pleaded (FAC ¶32), so it is arguable rather than fatal.

Full reports: [GPT-6 Sol](../tasks/draft-motion-to-dismiss-brief/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-motion-to-dismiss-brief/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 19. Draft Verified Responses and Objections to Plaintiff's First Set of Interrogatories in Commercial Breach of Contract and Fraud Action — C-028

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/task.json#L236) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/documents) · [Task audit page](../tasks/draft-responses-to-interrogatories/README.md)

**Correct financial figures for Tri-Basin purchase history**

> PASS if any purchase history figures cited in the responses are consistent with the canonical data: 2015: $9.2M; 2016: $10.1M; 2017: $10.8M; 2018: $12.4M; 2019: $13.6M; 2020: $9.7M; 2021: $15.3M; 2022: $16.8M; 2023 (Jan–Aug): $11.9M. Minor rounding differences are acceptable. Also PASS if the response invokes Rule 33(d) rather than citing specific figures. FAIL if specific purchase figures are cited but are materially incorrect.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O7: The purchase-history spreadsheet has two conflicting 2020 monthly series ($8.7M vs $9.7M subtotals)

Full reports: [GPT-6 Sol](../tasks/draft-responses-to-interrogatories/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-responses-to-interrogatories/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 20. Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum — C-002

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/documents) · [Task audit page](../tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md)

**ISSUE_001: Flags financial records date discrepancy as requiring DOJ clarification**

> PASS if the memo recommends seeking clarification from the DOJ regarding the conflicting date ranges (Jan 1, 2017 vs. Jan 1, 2019) for financial records. FAIL if no recommendation to seek clarification is made.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: problematic. GPT-6 Sol: problematic; Claude Opus 5.5: problematic (blind pass: problematic).

- **GPT-6 Sol:** B6-LH-1: Mandates a nonexistent date-range contradiction. (confirmed)
- **Claude Opus 5.5:** O3: C-002 requires asking DOJ to clarify an express carve-out (¶47 'Notwithstanding' ¶12)
- **Claude Opus 5.5 on GPT-6 Sol:** B6-LH-1 → problematic: ¶12 defines the period 'unless otherwise specified herein.' ¶47 opens 'Notwithstanding the Relevant Period defined in Paragraph 12' and extends financial records to 2017. That is an express carve-out, not a conflict. C-002 fails any memo that correctly treats ¶47 as binding and asks DOJ nothing, so it is problematic. C-001 is only arguable: a memo that names both paragraphs and the two-year extension gives the judge everything the PASS text lists, and the risk is limited to the 'inconsistency' framing.

Full reports: [GPT-6 Sol](../tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 21. Identify Excessive or Duplicative Research Charges in Litigation Invoice — C-013

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L114) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/documents) · [Task audit page](../tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md)

**Issue 3: Identifies duplicative MTCA research across Takahashi and Wendt**

> PASS if the memo identifies that multiple attorneys (Kenji Takahashi and Tyler Wendt) billed for overlapping MTCA liability/contractor liability/summary judgment research during July 2024, citing Section 6.4 (Duplicative Research Prohibition). FAIL if the MTCA duplication across timekeepers is not identified.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: not flagged).

- **GPT-6 Sol:** arguable/1: Overlap warrants scrutiny under strict guidelines, but labels alone do not establish identical work. Lost-profit proof versus broader consequential-damage fo… (arguable)
- **Claude Opus 5.5 on GPT-6 Sol:** arguable/1 → not_a_defect: Section 6.4 puts the burden on outside counsel to show that apparently duplicative entries addressed genuinely distinct questions. The client's reviewer is right to flag these overlaps, and most of these criteria accept 'any reasonable adjustment'. The DOE summary itself says both matters center on MTCA contractor strict liability. Only C-016 (required subset framing), C-017 (an excess judgment call) and C-019 (a model remedy contrary to 6.4) are arguable.

Full reports: [GPT-6 Sol](../tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 22. Identify Issues in Litigation Matter Budget Proposal — C-029

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/documents) · [Task audit page](../tasks/identify-issues-in-matter-budget-proposal/README.md)

**Budget inconsistency rated as Critical or High severity**

> PASS if the fee total reconciliation discrepancy ($116,050 difference between phase-based and staffing-model totals) is assigned a severity of Critical or High (or the highest or second-highest tier in whatever severity scale is used). FAIL if it is assigned a lower severity level or no severity level.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both flagged, different strength (one problematic, one arguable). GPT-6 Sol: problematic; Claude Opus 5.5: arguable (blind pass: arguable).

- **GPT-6 Sol:** Confirmed defects: item 2: C-028–030 (moderate, extra grading constraint)
- **Claude Opus 5.5:** O6: Requires severity ratings although the instructions ask only for a 'categorized' issue memo
- **Claude Opus 5.5 on GPT-6 Sol:** Confirmed defects: item 2 → arguable: The instructions ask only for a 'categorized issue memorandum.' That most naturally means grouping by issue type, but reading it as severity tiers is plausible, and priority ratings are common in issue memos. Omitting ratings fails three criteria at once, but the instructions really are ambiguous, so arguable rather than confirmed.

Full reports: [GPT-6 Sol](../tasks/identify-issues-in-matter-budget-proposal/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/identify-issues-in-matter-budget-proposal/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 23. Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial — C-020

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L170) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/documents) · [Task audit page](../tasks/review-counterpartys-proposed-jury-instructions/README.md)

**Explains distinction between tortious interference with contract vs. business relations**

> PASS if the memo explains that under Georgia law, tortious interference with an existing contract does not require a separately/independently wrongful act — the knowing inducement of the breach is sufficient — and that the 'independently wrongful act' element applies to the distinct tort of tortious interference with business relations. FAIL if this legal distinction is not articulated.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: problematic. GPT-6 Sol: problematic; Claude Opus 5.5: problematic (blind pass: problematic).

- **GPT-6 Sol:** F1: The supplied summary-judgment order and rubric use an incorrect categorical Georgia-law distinction: contract interference supposedly needs only knowing indu… (confirmed)
- **Claude Opus 5.5:** O1: C-020 requires a Georgia contract-vs-business-relations distinction on wrongful conduct that Georgia courts reject
- **Claude Opus 5.5 on GPT-6 Sol:** F1 → problematic: I agree that Georgia puts 'improper action or wrongful conduct without privilege' into contract-interference claims as well (Fortson, Rowell, Tribeca Homes). C-020 therefore requires a false contract-vs-business-relations rule. C-019 is only arguable. No. 27's 'separate from the interference itself' framing is objectionable, and the SJ order's four-element list supports flagging it. A memo that calls element 3 substantially correct Georgia law would still fail C-019.

Full reports: [GPT-6 Sol](../tasks/review-counterpartys-proposed-jury-instructions/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/review-counterpartys-proposed-jury-instructions/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 24. Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report — C-024

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L204) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/documents) · [Task audit page](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md)

**Recommends full disallowance of black car service: $387.00**

> PASS if the report recommends disallowing the full $387.00 for black car service (or reducing it to a reasonable taxi/ride-share equivalent). FAIL if no disallowance or reduction is recommended.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Flagged by GPT-6 Sol only. GPT-6 Sol: arguable; Claude Opus 5.5: not flagged (blind pass: arguable).

- **GPT-6 Sol:** Arguable/qualified concerns: item 5: C-024 permits taxi-equivalent allowance despite guideline P142 stating black cars never reimbursable.
- **Claude Opus 5.5 on GPT-6 Sol:** Arguable/qualified concerns: item 5 → not_a_defect: §6.1 says black car services are 'not reimbursable under any circumstances,' and full disallowance passes C-024. The alternative taxi-equivalent path is lenient but reflects client discretion ('VIH may apply' remedies, §11.2). It fails no correct answer.

Full reports: [GPT-6 Sol](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

## 25. Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report — C-042

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/documents) · [Task audit page](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md)

**Classifies business class airfare as borderline/requires discussion**

> PASS if the report classifies the business class airfare issue (Messina's $2,847.00 flight) as a borderline or 'requires discussion' issue rather than a clear-cut mandatory reduction, given the 4-hour-20-minute flight duration and the 4-hour threshold. FAIL if it is classified as a clear mandatory reduction without acknowledging the ambiguity, OR if it is entirely dismissed as compliant.

<details><summary>AI findings (open after forming your own view)</summary>

Agreement group: Both models: problematic. GPT-6 Sol: problematic; Claude Opus 5.5: problematic (blind pass: problematic).

- **GPT-6 Sol:** Definite defects: item 1: C-019/C-020/C-042 force an incorrect “borderline” airfare determination.
- **Claude Opus 5.5:** O1: Business-class airfare must be called 'borderline' although §6.1(b) plainly permits it on a ≥4h flight (rubric says ~4h20m)
- **Claude Opus 5.5 on GPT-6 Sol:** Definite defects: item 1 → problematic: §6.1(b): 'For domestic flights with a scheduled duration of four (4) hours or more, business class may be booked without prior approval.' The rubric's own ~4h20m figure clears that line. C-020 and C-042 fail a report that calls the fare compliant, which is the correct reading. C-019's FAIL condition is only 'not flagged at all'. But its PASS text requires 'potentially violates', so a report that analyzes the fare and finds it compliant may still fail. That makes C-019 arguable.

Full reports: [GPT-6 Sol](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/claude-opus-5-5-audit.md).

</details>

- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_
- **AI reasoning:** _(Correct / Partly correct / Wrong)_
- **Note and source locator:**

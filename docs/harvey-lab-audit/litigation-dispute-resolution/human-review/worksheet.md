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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/gpt6luna-xhigh/README.md#c-049) | Fail | Fail | 7 / 8 |
| [Claude Opus 5.5 (low)](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/opus55-low/README.md#c-049) | Pass | Pass | 4 / 2 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/assess-reasonableness-of-staffing-levels-on-litigation-invoice/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo does not calculate the percentage by which the attorney fee subtotal ($193,372.50) exceeds the approved budget ceiling ($165,000). It calculates the 115% ceiling ($189,750) and the excess over that ceiling ($3,622.50), and it mentions a variance over the monthly midpoint of 48.75%, but it never computes the ~17.2% overage of $193,372.50 relative to the $165,000 approved budget. The criterion requires this specific percentage calculation to be present and approximately correct.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The memo identifies the approved monthly high end of $165,000 and the billed fees of $193,372.50, but it does not calculate or state the overage percentage of approximately 17.2%. Instead, it calculates the excess over the 115% ceiling and a 48.75% variance over the midpoint, which does not satisfy the specified criterion.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In Part IX of the memo, the agent states: 'Fees billed were $193,372.50, which is $28,372.50 (17.2%) above the $165,000 high end.' This directly calculates the percentage overage of the fee subtotal over the approved budget ceiling as 17.2%, which matches the exact figure specified in the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo explicitly states that fees billed were $193,372.50, which is $28,372.50 or 17.2% above the $165,000 high end, matching the required approximately 17% overage calculation.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the invoice's 117 time entries add up to $215,680.00, while its summary and subtotal show $193,372.50.
- **Note and source locator:** JOHN HUGHES: Defective / AI is correct. The rubric is testing the AI on a specific percentage calculation from an invoice, but the document in the environment is internally inconsistent. The invoice’s summary page and its subtotal row show fees of $193,372.50 (17.2% over the $165,000 budget), but the 117 detailed time entries add up to $215,680.00, which puts the overage at $50,680, or 30.7% (13.5 points from the rubric’s required 17.2% answer and far outside the 2-point tolerance).
- **Category**: unambiguous objective error, deficiency in task environment.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/categorize-document-production-set-by-relevance-and-privilege/gpt6luna-xhigh/README.md#c-012) | Pass | Pass | 9 / 8 |
| [Claude Opus 5.5 (low)](../model-runs/categorize-document-production-set-by-relevance-and-privilege/opus55-low/README.md#c-012) | Pass | Pass | 14 / 16 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/categorize-document-production-set-by-relevance-and-privilege/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/categorize-document-production-set-by-relevance-and-privilege/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/categorize-document-production-set-by-relevance-and-privilege/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/categorize-document-production-set-by-relevance-and-privilege/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/categorize-document-production-set-by-relevance-and-privilege/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/categorize-document-production-set-by-relevance-and-privilege/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** RC-24 (chandrasekaran-meeting-notes-aug28.docx) is classified in the relevance report as 'R1 — Core (partially withheld)' and in the privilege log as PL-007, where only the sections headed 'Legal Strategy — Retaliation Exposure' and 'Legal Strategy — Separation & Documentation' are withheld, while operational discussion, meeting facts, and action items are explicitly not claimed as privileged. This is a partial privilege classification, not full privilege or no privilege.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The agent identifies chandrasekaran-meeting-notes-aug28.docx as RC-24 and expressly marks it as partially withheld/partially privileged, with only legal-strategy portions redacted under PL-007 while operational facts are not withheld.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In the relevance classification report, MPI-REV-011 (chandrasekaran-meeting-notes-aug28.docx) is classified as 'Partially privileged: Legal Strategy sections Attorney-Client/Work Product' with treatment 'Produce with redactions.' In the privilege log, Log Entry 3 for MPI-REV-011 confirms it is 'Produced with redactions,' with only the 'Legal Strategy' sections redacted while business discussion portions are produced. This clearly reflects a Partially Privileged classification, satisfying the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The August 28 Chandrasekaran meeting notes (chandrasekaran-meeting-notes-aug28.docx) are expressly classified as partially privileged, with legal-strategy sections redacted and business portions produced; the privilege log also lists them as produced with redactions.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:**  Defective / AI is Correct. JOHN HUGHES: The rubric is wrong because it fails fully Privileged, which is the better answer here (even if Partially Privileged is defensible).
- The documents are handwritten lawyer notes from a fictitious meeting discussing problems with the R&D Department. The headings on individual topics seem intended to create the impression that there is a discussion of business topics (which would not be privileged) followed by a separate discussion of legal topics (privileged), so from a superficial glance, the rubric does seem to match the topic headings. However, the bullets under each heading make clear that the entire meeting is just dedicated to the topic of the company’s desire to find a way to fire the head of R&D without getting sued. The business topics (which look to be nonprivileged) are discusisons of how the R&D department is a bit of a disaster, such that management wants to fire the head. The legal sections then involve discussion of the fact that the R&D head has some sort of environmental whistleblower status, so termination is likely to trigger a lawsuit/whistleblower retaliation claim.
- The meeting was specifically convened because outside counsel was concerned about the retaliation claim, and even some of the 'ops' sections that are supposed to be nonprivileged reflect counsel's advice, so they cannot be cleanly treated as nonlegal business discussions. For example, the 'Ops' sections record HR "compiling the file" of performance documentation and lay out a "Performance improvement plan first" / "Documentation period" sequence, which carries out outside counsel's recommendation, recorded in the legal section, to build a "contemporaneous performance record to insulate against retaliation" claims.
- While partially privileged might be defensible, my preferred answer would be fully privileged, which the rubric incorrectly fails.
- **Category**: low-quality professional judgment, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/compare-document-production-against-discovery-requests/gpt6luna-xhigh/README.md#c-029) | Fail | Pass | 14 / 15 |
| [Claude Opus 5.5 (low)](../model-runs/compare-document-production-against-discovery-requests/opus55-low/README.md#c-029) | Fail | Fail | 6 / 6 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/compare-document-production-against-discovery-requests/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/compare-document-production-against-discovery-requests/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/compare-document-production-against-discovery-requests/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/compare-document-production-against-discovery-requests/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/compare-document-production-against-discovery-requests/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/compare-document-production-against-discovery-requests/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The criterion requires the memorandum to note that only 5 of the 14 documents coded to RFP 27 actually relate to Pacific Corridor's volume shortfall and counterclaim damages. The agent's output states in the RFP 27 row: 'Only five entries expressly described as PC volume/damages support are identified in MLC-004056--004102.' However, it does not mention that there are 14 documents total coded to RFP 27, nor does it characterize this as '5 of 14.' The Greystone issue is noted separately (8 entries relate to Greystone), but the memo does not explicitly frame this as '5 of 14 documents coded to RFP 27 actually relate to counterclaim damages.' The criterion specifically requires noting that only 5 of the 14 documents coded to RFP 27 actually relate to Pacific Corridor's volume shortfall and counterclaim damages calculation. The agent notes 5 entries but doesn't establish the denominator of 14 or make the explicit comparison that would show the counterclaim damages support is thin in those specific terms.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The memorandum expressly states under RFP 27 that only five entries are described as Pacific Corridor volume/damages support, while other documents in the relevant counterclaim-damages grouping relate to Greystone rather than PC. It also flags the counterclaim damages support as thin/incomplete and calls for source data and corrected coding. This satisfies the criterion.
- **Claude Opus 5.5 (low), Sonnet 4.6: Fail.** The memorandum discusses RFP 27 and notes that MLC-003681--003820 and MLC-004056--004102 were produced as Pacific Corridor-related counterclaim documents, and that 9 documents (MLC-003980--004055) concern Greystone Distribution Partners. However, it does not specifically note that only 5 of the 14 documents coded to RFP 27 (MLC-004056 through MLC-004102) actually relate to Pacific Corridor's volume shortfall and counterclaim damages calculation. The criterion requires the memo to identify that the counterclaim damages support is thin because only 5 of 14 documents in that Bates range actually relate to the counterclaim. This specific finding is absent from the agent's output.
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The memorandum discusses RFP 27 and notes that some documents are unrelated Greystone materials and that model inputs/consultant files are missing, but it does not state that only 5 of the 14 documents coded to RFP 27 in the MLC-004056 through MLC-004102 range actually relate to Pacific Corridor volume shortfall/counterclaim damages, nor does it make the specific point that the counterclaim damages support is thin on that basis.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the production index codes 15 rows to RFP 27, but its summary tab gives a count of 14 for a range that contains 13.
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: This task requires models to make the point that “only” five documents in the bundle “actually relate to Pacific Corridor's volume shortfall and the counterclaim damages calculation, meaning the counterclaim damages support is thin.” This rubric is flawed on multiple levels.
- First, it overlooks MLC-003781, a sixth document that plainly relates to the volume shortfall, so the count is objectively wrong (and the agents pointed to several other examples, at least some of which also seem to fit within the stated criteria). There is a document in the bundle that claims that only five documents concern the volume shortfall, but that assertion is undercut by other evidence supplied in the environment.
- Second, this rubric is someone’s argumentative characterization of the documents and probably would not hold up under adversarial testing. For example, there is case law that the term “relate to” is fairly broad and flexible, so quite plausibly a number of other documents would apply.
- Third, the premise underlying this rubric–that “only” five documents is such “thin” evidence that it must be called out–is wrong. Even one document could constitute conclusive proof of damages (the general rule is that damages only need to be reasonably estimated; courts do not require great precision); to my mind, this is actually quite a lot of evidence at the fact stage compared to what one would normally see.
- **Category**: unambiguous objective error, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-case-assessment-memorandum/gpt6luna-xhigh/README.md#c-025) | Fail | Fail | 13 / 10 |
| [Claude Opus 5.5 (low)](../model-runs/draft-case-assessment-memorandum/opus55-low/README.md#c-025) | Pass | Pass | 4 / 5 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-case-assessment-memorandum/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-case-assessment-memorandum/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-case-assessment-memorandum/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-case-assessment-memorandum/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-case-assessment-memorandum/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-case-assessment-memorandum/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo discusses unjust enrichment in Section 3D, noting that 'the written agreement governs much of the relationship, which ordinarily makes quasi-contract restitution difficult for matters within its scope.' However, this is framed as a caution to Cascade (the plaintiff) about the weakness of its own unjust enrichment claim, not as a recommendation to file a motion to dismiss or any dispositive motion targeting the unjust enrichment claim. The memo advises to 'preserve it for benefits outside the contract or if the agreement is held not to govern the specific benefit.' There is no recommendation anywhere in the memo to file a motion to dismiss, motion for judgment on the pleadings, or similar dispositive motion targeting the unjust enrichment claim on the basis that an express contract governs the relationship.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The memo notes that unjust enrichment is vulnerable because the written agreement governs much of the relationship, but it recommends preserving the claim in the alternative rather than filing a motion to dismiss or similar dispositive motion targeting Count IV.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** Section 9.2 of the memo explicitly states under the Fourth Cause of Action (Unjust Enrichment): 'Move to dismiss, or at least expect it to be limited to duplicate relief.' The memo also reiterates this in Section 9.2 (Pleadings stage): 'Partial motion to dismiss / strike: ... (ii) unjust enrichment (express contract; displacement).' The memo clearly recommends filing a motion to dismiss the unjust enrichment claim on the ground that an express contract governs the relationship (and also OUTSA displacement).
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo expressly assesses Count IV unjust enrichment as low risk because a valid express contract governs the subject matter and recommends moving to dismiss it. It reiterates this in the pleadings strategy, recommending a partial motion to dismiss unjust enrichment based on the express contract and displacement.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: A different rubric on this task concludes that plaintiff has a strong breach of contract claim. (See id: C-006.) The prompt instructs models to review case documents and “prepare a comprehensive case assessment memo,” and models are dinged on this rubric if they do not “recommend[] filing a motion to dismiss” on the unjust enrichment claim, which is expressly pled in the alternative to the (strong) breach of contract claim.
- The rubric is wrong because a careful litigator could reasonably conclude that a motion to dismiss that claim is not a good idea: Count IV is pleaded in the alternative (Complaint ¶127) and seeks restitution of “no less than $22,521,312.50” (¶135), which is exactly the Count I contract damages ($17,721,312.50, ¶94) plus the Count III trade-secret damages ($4,800,000, ¶120). Counts I and III would survive the motion and double recovery is barred, so dismissing Count IV would not reduce the defendant’s net exposure; and the factual underpinnings of both claims are the same so a successful motion would not reduce the scope of discovery. Filing a dispositive motion is costly and, on these facts, there seems to be no benefit to doing so. So the required recommendation would fail many thoughtful analyses that could discuss the pros and cons and recommend against filing such a motion.
- **Category**: low-quality professional judgment, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/README.md#c-030) | Pass | Pass | 6 / 6 |
| [Claude Opus 5.5 (low)](../model-runs/draft-conflict-check-memorandum/opus55-low/README.md#c-030) | Pass | Pass | 2 / 3 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-conflict-check-memorandum/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-conflict-check-memorandum/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-conflict-check-memorandum/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The memo explicitly recommends excluding and screening Caleb Strand in multiple places. Section 2 states 'Exclude and screen Strand.' Section 4D states 'Strand should not be on the matter team' and the interim direction says 'Exclude Strand from all case communications and materials, establish a documented screen.' Section 5 item 2 lists Strand among those to be isolated and screened. The criterion is clearly satisfied.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The memo explicitly recommends excluding Caleb Strand from all case communications and materials, establishing a documented screen, and notes he should not be on the matter team.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The memo explicitly recommends removing Caleb Strand from the team and imposing a full ethical screen (Section IV.B, items 14-19, and Tier 1 condition #5). This clearly satisfies the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo explicitly identifies Caleb Strand’s sister’s TriPoint role as a high-risk conflict and recommends removing Strand from the team and imposing a full ethical screen with access restrictions and written acknowledgment.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The rubric requires the model to recommend that an associate who shares an apartment with his sister (an in-house IP paralegal at TriPoint, the adverse party) be screened from the matter. Screening is generally used in certain specific situations where required by the professional conduct rules, but no rule requires screening in this scenario.
- I agree that a prudent memo would flag the fact that a junior team member is sharing an apartment with an employee of the adverse party, but that is covered by other rubrics (C-026 through C-029). This rubric specifically fails the work product (and results in a 0 for all work on this task) even if the model recommended, say, obtaining the client’s informed consent, which would be perfectly permissible and appropriate here.
- Other rubrics in this task resolve similar kinds of conflicts with informed consent (C-024 accepts "clearance with conditions (such as obtaining informed consent)" for Lisa Chow's spousal conflict, and C-016 recommends informed consent for the Ridgeline conflict). Accordingly, informed consent plus a home confidentiality protocol could suffice as an alternative to screening.
- **Category**: low-quality professional judgment, rubric is incorrect.

## 6. Draft Conflict Check Memorandum for Litigation Engagement Clearance — C-049

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/task.json#L402) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-conflict-check-memorandum/documents) · [Task audit page](../tasks/draft-conflict-check-memorandum/README.md)

**ISSUE_011: Recommends integrating annual disclosure questionnaires with ConflictTracker**

> PASS if the memo recommends that annual conflict-disclosure questionnaires be cross-referenced with or integrated into the ConflictTracker system. FAIL if no recommendation about integrating disclosure questionnaires with the conflicts database is made.

<details><summary>AI findings (open after forming your own view)</summary>


Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O5: Three criteria each require a specific firm-wide process reform beyond clearing this engagement

Full reports: [GPT-6 Sol](../tasks/draft-conflict-check-memorandum/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-conflict-check-memorandum/claude-opus-5-5-audit.md).

</details>

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/README.md#c-049) | Fail | Pass | 5 / 6 |
| [Claude Opus 5.5 (low)](../model-runs/draft-conflict-check-memorandum/opus55-low/README.md#c-049) | Pass | Pass | 2 / 3 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-conflict-check-memorandum/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-conflict-check-memorandum/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-conflict-check-memorandum/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-conflict-check-memorandum/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo explicitly notes in Section 4H that 'ConflictTracker expressly excludes annual attorney disclosures, HR/family records and board memberships from automated cross-reference; the unindexed Chow, Strand and Voss facts demonstrate that a database "no hit" is not a complete clearance.' While this identifies the problem, the criterion asks whether the memo *recommends* integrating annual disclosure questionnaires with ConflictTracker. Looking at Section 5 (Required actions), items 5 and 6 mention 'Confirm and correct the missing ConflictTracker entry' and 'update the annual disclosure record,' but these are record-correction steps for specific instances, not a systemic recommendation to integrate annual disclosures with ConflictTracker going forward. The memo does not make a forward-looking recommendation to integrate or cross-reference annual conflict-disclosure questionnaires with the ConflictTracker system as a process improvement. It only notes the gap and addresses specific missing entries, without recommending systemic integration.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The memo expressly notes that ConflictTracker does not automatically cross-reference annual disclosures and recommends verifying/correcting missing annual-disclosure entries, updating the annual disclosure/ConflictTracker records, and updating ConflictTracker after updated conflict certifications. This satisfies the requirement to recommend cross-referencing or integrating annual disclosure questionnaires with the conflicts database.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In Part VI (Tier 3 — Process Remediation), the memo explicitly states: 'Add questionnaires, family and household ties, and board and trade-association roles to ConflictTracker's search index, or require a manual cross-check on every intake.' This directly recommends integrating annual disclosure questionnaires with the ConflictTracker system. Additionally, the memo notes throughout that the Chow and Strand disclosures were never entered into ConflictTracker despite being disclosed on annual/new-hire questionnaires, and recommends entering them immediately. The recommendation to integrate questionnaires with ConflictTracker is clearly present.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo expressly recommends process remediation to enter annual disclosure information into ConflictTracker and to add questionnaires, family/household ties, and board/trade-association roles to ConflictTracker’s search index or require manual cross-checks. This satisfies the criterion.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The assignment in the prompt is to draft a “comprehensive conflict check memorandum for the proposed engagement.” The rubric requires that the memo contain suggested firm-wide process improvements (memo must “recommend[] that annual conflict-disclosure questionnaires be cross-referenced with or integrated into the ConflictTracker system”). That’s simply not the assignment, and there’s many reasons why it’s undesirable to jam broad process suggestions into a conflicts memo for one specific case. This rubric actually failed work product from Luna that did everything a clearance memo needs on this point. The two judges split on that same Luna memo (Sonnet 4.6 failed it; GPT-5.5 passed it), which shows the criterion does not grade reliably.
- **Category**: requires specific outputs not expressly or impliedly requested in the prompt.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/README.md#c-045) | Pass | Pass | 3 / 2 |
| [Claude Opus 5.5 (low)](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/README.md#c-045) | Pass | Pass | 6 / 6 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The agent's output includes COUNT V — PATENT INFRINGEMENT (35 U.S.C. §§ 271, 281; against Lumenara), which explicitly alleges that LumiSense 400 infringes U.S. Patent No. 11,234,567 covering the SensorCore™ architecture. The count references Dr. Ayers' expert analysis confirming the product meets each claim limitation, seeks damages under 35 U.S.C. § 284, injunctive relief under § 283, and attorneys' fees under § 285. This fully satisfies the criterion.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The counterclaim includes a separate Count V titled Patent Infringement under 35 U.S.C. §§ 271 and 281, alleging that Lumenara’s LumiSense 400 infringes U.S. Patent No. 11,234,567 covering the SensorCore™ substrate architecture.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** COUNT VII of the counterclaim is explicitly titled 'Patent Infringement: U.S. Patent No. 11,234,567 (35 U.S.C. § 271)' and alleges that the LumiSense 400 directly infringes at least claim 1 of the '567 Patent covering the SensorCore™ architecture. The count includes claim mapping, willfulness allegations, and requests for damages and injunctive relief under 35 U.S.C. §§ 283-285.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The counterclaim includes a separate Count VII titled “Patent Infringement: U.S. Patent No. 11,234,567 (35 U.S.C. § 271),” alleging that Lumenara’s LumiSense 400 directly infringes the ’567 Patent covering the SensorCore™ architecture by making, using, selling, offering to sell, and/or importing the accused product.

</details>
<!-- runs:end -->

- **Verdict:** Arguable
- **AI reasoning:** Correct
- **Environment:** Defective: the record lacks the patent the counterclaim must plead, and the two expert reports give different titles for it.
- **Note and source locator:** Arguable / AI is correct. JOHN HUGHES: The task is to draft a counterclaim based on a handful of documents (including an expert report, some emails, and a counterclaim strategy memo that another lawyer prepared). The rubric dings the AI if the courtclaims do not include “a separate count for patent infringement under 35 U.S.C. § 271, alleging that the LumiSense 400 infringes U.S. Patent No. 11,234,567.”
- The environment does not contain the allegedly infringed patent, which one would need to review in order to have a sufficient basis for drafting that counterclaim, so this environment appears to be incomplete. That said, a defensible approach might be for the agent to draft the counterclaim but flag in brackets that it requires verification.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/README.md#c-046) | Pass | Pass | 3 / 2 |
| [Claude Opus 5.5 (low)](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/README.md#c-046) | Pass | Pass | 6 / 6 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** Count V (Patent Infringement) explicitly identifies U.S. Patent No. 11,234,567 in paragraph 59: 'Vantage owns all right, title, and interest in U.S. Patent No. 11,234,567, entitled "Multi-Layer Copper-Pillar Micro-Bump Interconnect Architecture for Integrated Optical Sensor Substrates," which issued on January 10, 2023 (the "'567 patent").' The patent number is correctly and specifically cited in the patent infringement count.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The patent infringement count (Count V) specifically identifies U.S. Patent No. 11,234,567 and refers to it as the '567 patent.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** COUNT VII (Patent Infringement) explicitly identifies 'U.S. Patent No. 11,234,567' and refers to it as 'the '567 Patent' throughout the count, including in paragraphs 101, 102, 103, 104, 105, 106, and 107.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The patent infringement count is titled “Patent Infringement: U.S. Patent No. 11,234,567 (35 U.S.C. § 271)” and repeatedly identifies the ’567 Patent as U.S. Patent No. 11,234,567.

</details>
<!-- runs:end -->

- **Verdict:** Arguable
- **AI reasoning:** Partly correct
- **Environment:** Defective: same task environment as item 7.
- **Note and source locator:** Arguable / AI is partly correct. JOHN HUGHES: Same issue as prior rubric. This one is essentially derivative because it depends on pleading the patent count that was required in the prior rubric.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/README.md#c-003) | Pass | Fail | 30 / 27 |
| [Claude Opus 5.5 (low)](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/README.md#c-003) | Fail | Fail | 19 / 17 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The Executive Summary (labeled 'Executive assessment') states: 'Marco Reyes was killed; Kevin Trask and Priya Anand suffered serious injuries.' This clearly mentions the death of Marco Reyes in the executive summary section.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The Executive Summary/Executive assessment does not specifically mention that Marco Reyes died. His death is mentioned later in the record/incident section, but not in the executive summary section.
- **Claude Opus 5.5 (low), Sonnet 4.6: Fail.** The criterion requires that the Executive Summary mentions the death of Marco Reyes. Looking at the agent's output, Section 1 ('Bottom Line') serves as the executive summary. It mentions 'Reyes killed' in the Key Facts table (Section 3), and in Section 1 (Bottom Line/Executive Summary), it does not explicitly mention Marco Reyes or his death. The Bottom Line section discusses liability, contract obstacles, HydraCore as a target, Dalton's net exposure, and urgent deadlines, but does not mention the death of Marco Reyes. The fatality is only mentioned in the Key Facts table in Section 3, not in the executive summary (Section 1/Bottom Line).
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The executive-summary equivalent ('Bottom Line') discusses employee tort claims and exposure but does not mention Marco Reyes or his death. The fatality is mentioned later in Key Facts, not in the Executive Summary.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: same task environment as item 10 (Ohio state agency issuing OSHA citations).
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The case involved a (fictitious) safety incident at a manufacturing plant that killed one employee and seriously injured two others. The rubric requires the fact that one employee died be discussed specifically in the “executive summary.” When we tested Opus 5.5 and GPT-6-Luna on this benchmark, both discussed the death in several places in their memo, especially the factual background section, but the executive summary consisted of an overview of the legal analysis that did not restate the fact of the death. They were failed by one or more judges.
- This fails perfectly competent and appropriate work product. The company CEO who retained counsel to advise on this incident is the same person who delivered news of the (fictitious) tragic death to the decedent’s widow and surviving family members, so the most senior management of the company is obviously very familiar with the incident and the agents’ approach of focusing the executive summary on the legal exposure is appropriate.
- The two judges reached opposite results on Luna’s memo: GPT-5.5 failed it, while Sonnet 4.6 passed it only by quoting a sentence from the memo’s facts section as if it appeared in the executive summary.
- **Category**: requires specific outputs not expressly or impliedly requested in the prompt.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/README.md#c-026) | Fail | Fail | 29 / 27 |
| [Claude Opus 5.5 (low)](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/README.md#c-026) | Pass | Pass | 20 / 18 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-defective-industrial-equipment-product-liability/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-defective-industrial-equipment-product-liability/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo references OSHA citations and penalties (including a $31,400 OSHA penalties line in the damages section), but never specifically identifies the LOTO citation under 29 CFR 1910.147(c)(4)(i) nor mentions the specific penalty amount of $18,900. The memo discusses LOTO deficiencies and citation disputes in general terms but lacks the specific regulatory citation and penalty amount required by the criterion.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The memo references OSHA LOTO deficiencies and total OSHA penalties of $31,400, but it does not identify the specific LOTO citation under 29 CFR 1910.147(c)(4)(i) or the specific $18,900 penalty.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The memo explicitly identifies the OSHA LOTO citation as 'Item 1, LOTO (1910.147(c)(4)(i), $18,900)' in Section 9, matching the specific regulation 29 CFR 1910.147(c)(4)(i) and the penalty amount of $18,900.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo specifically identifies the OSHA LOTO citation as Item 1, cites 29 CFR 1910.147(c)(4)(i), and lists the penalty as $18,900.

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Defective: Ohio's Division of Safety & Hygiene cannot issue OSHA citations to this private employer. The criterion itself does not misgrade work (environment-only defect).
- **Note and source locator:** Not defective (criterion); defective environment / AI is wrong (as to the criterion). JOHN HUGHES: Although the specific rubric being tested does not fail work product incorrectly, the environment is defective in an unintended way. The environment contains an OSHA citation from Ohio’s Division of Safety & Hygiene. But Ohio does not have an OSHA-approved State Plan, so only federal regulators  have jurisdiction to issue OSHA citations against this company. The environment does not test that so it is not being presented as a “mistake” by one’s adversary that the agents should pick up on.
- The rubric itself is not wrong because it simply wants a memo to address the purported citation, so an agent could write the memo while noticing that the task is obviously a fictitious evaluation with an incoherent environment.
- **Category**: defective environment, but rubric does not fail correct work product.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-discovery-plan-memorandum/gpt6luna-xhigh/README.md#c-036) | Pass | Pass | 15 / 14 |
| [Claude Opus 5.5 (low)](../model-runs/draft-discovery-plan-memorandum/opus55-low/README.md#c-036) | Pass | Pass | 11 / 9 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-discovery-plan-memorandum/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-discovery-plan-memorandum/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-discovery-plan-memorandum/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-discovery-plan-memorandum/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-discovery-plan-memorandum/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-discovery-plan-memorandum/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** In Section II, the memo states: 'Tier collection toward Brecker, Kowalski, Fenton, Ostrowski, and Liu; preserve and assess the CEO's records (including archived mailbox) without prematurely excluding them.' This establishes a tiered prioritization, identifying Brecker, Kowalski, Fenton, Ostrowski, and Liu as higher-priority custodians for collection, while treating the CEO's records as secondary. This constitutes a priority ranking/tiering of custodians.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The memo does more than merely list custodians: it instructs counsel to “Tier collection toward Brecker, Kowalski, Fenton, Ostrowski, and Liu,” while separately identifying other custodians to add/preserve and the CEO to assess. This provides a relative prioritization/tiering for custodian collection, even if not in a formal high/medium/low table.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The memo does provide some prioritization of custodians. In Part VIII.B (Key Protocol Terms), it distinguishes between Tier 1 custodians and Tier 2 custodians, specifically noting 'Gerald Hartwell as a Tier 2 custodian with keyword filtering' while listing others (Brecker, Kowalski, Fenton, Ostrowski, Liu, etc.) as the primary/Tier 1 group. Additionally, in Part VI.C (Depositions), custodians/witnesses are ranked 1-10 by priority. These tiering and ranking systems satisfy the criterion of providing priority rankings for custodians.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo provides custodian prioritization by identifying initial Hartwell custodians and specifically designating Gerald Hartwell as a Tier 2 custodian; it also references Tier 1 custodians/QA engineers in preservation and ESI sections.

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Correct
- **Note and source locator:** Not defective / AI is wrong. JOHN HUGHES: The AI agent is right that the rubric is really enforcing a stylistic choice, but the choice here is well-grounded in convention and an appropriate expectation for quality work product. The case file contains a court order where the judge encouraged the parties to discuss whether phased discovery would be appropriate at the Rule 26(f) conference, and there is some existing prioritization work in the environment. The rubric requires that the agent’s discovery plan include some kind of prioritization or phasing of custodians, which is a common expectation in these cases. I think it’s fair to judge anything that lacks any form of prioritization as deficient given the context.

## 12. Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute — C-025

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L214) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/documents) · [Task audit page](../tasks/draft-federal-complaint-drafting/README.md)

**ISSUE_012: Complaint requests injunctive relief**

> PASS if the prayer for relief includes a request for preliminary and/or permanent injunctive relief — specifically to enforce the non-solicitation provision and prevent Graydon from continuing to divert Fund III investor prospects to competing funds. FAIL if no injunctive relief is requested.

<details><summary>AI findings (open after forming your own view)</summary>


Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O8: Injunctive relief made mandatory although the intake memo leaves it as an open question for the partner

Full reports: [GPT-6 Sol](../tasks/draft-federal-complaint-drafting/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-federal-complaint-drafting/claude-opus-5-5-audit.md).

</details>

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-federal-complaint-drafting/gpt6luna-xhigh/README.md#c-025) | Pass | Pass | 6 / 7 |
| [Claude Opus 5.5 (low)](../model-runs/draft-federal-complaint-drafting/opus55-low/README.md#c-025) | Pass | Pass | 1 / 0 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-federal-complaint-drafting/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-federal-complaint-drafting/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-federal-complaint-drafting/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-federal-complaint-drafting/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-federal-complaint-drafting/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-federal-complaint-drafting/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The prayer for relief in section E explicitly requests 'appropriate declaratory and permanent injunctive relief to enforce the PAA's surviving non-solicitation obligations through their lawful expiration.' This directly addresses injunctive relief to enforce the non-solicitation provision and prevent Graydon from continuing to divert Fund III investor prospects to competing funds. The criterion is satisfied.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The prayer for relief expressly requests “permanent injunctive relief to enforce the PAA’s surviving non-solicitation obligations” and ties it to ongoing or imminent violations. The complaint also alleges continuing prohibited solicitation/diversion activity under the non-solicitation provision. This satisfies the criterion requiring injunctive relief to enforce the non-solicitation provision and prevent further diversion.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The complaint includes Count VI titled 'PERMANENT INJUNCTION TO ENFORCE PAA SECTION 7.4' (paragraphs 74-76) which explicitly requests injunctive relief to enforce the non-solicitation provision and prevent Defendants from diverting Fund III investors to competing funds. The prayer for relief at paragraph (g) also requests 'A permanent injunction as described in Count VI.' Count VI also reserves the right to move for preliminary relief. This clearly satisfies the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The complaint expressly includes Count VI seeking a permanent injunction to enforce PAA Section 7.4, the non-solicitation provision, and to enjoin Defendants from soliciting/diverting Fund III investors to competing funds. The prayer for relief also requests “a permanent injunction as described in Count VI.”

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Correct
- **Note and source locator:** Not defective / agent is wrong. JOHN HUGHES: The client intake memo specifically describes an interest in seeking injunctive relief (“We may also wish to seek preliminary and permanent injunctive relief to enforce the twelve-month non-solicitation tail”), and the client’s demand letter threatens it. While it’s true that the intake memo flags the topic for discussion, the correct approach is to include the proposed prayer for relief in the draft, so the case team can see how it reads and discuss any downsides. As a practical matter, there’s unlikely to be much downside to including this prayer for relief in the complaint. (Whether it’s worth the cost of actually pursuing a preliminary injunction on this is debatable, so the rubric’s approach makes sense.)

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-interrogatories/gpt6luna-xhigh/README.md#c-008) | Fail | Fail | 10 / 8 |
| [Claude Opus 5.5 (low)](../model-runs/draft-interrogatories/opus55-low/README.md#c-008) | Pass | Pass | 1 / 1 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-interrogatories/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-interrogatories/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-interrogatories/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-interrogatories/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-interrogatories/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-interrogatories/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The Definitions section in the agent's output contains six definitions: 'Veridian,' 'Oshiro,' 'CMT Trade Secrets,' 'CMT Materials,' 'SynapticEdge,' and 'Identify.' There is no definition of 'Document' or 'Documents' anywhere in the Definitions section. The criterion requires a definition of 'Document' or 'Documents' broad enough to encompass ESI, emails, and physical documents. Since no such definition exists in the output, the criterion is not satisfied.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The Definitions section does not define “Document” or “Documents” at all, and therefore does not expressly encompass ESI, emails, and physical documents.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** Definition 14 in the Definitions section defines 'Document' as having 'the full meaning ascribed to "documents or electronically stored information" in Fed. R. Civ. P. 34(a)(1)(A), and includes every draft and non-identical copy.' This is a broad definition that explicitly encompasses ESI by reference to Rule 34, and also covers physical documents and drafts. It clearly satisfies the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The Definitions section expressly defines “Document” to have the full meaning of “documents or electronically stored information” under Fed. R. Civ. P. 34(a)(1)(A), including drafts and non-identical copies. This is broad enough to encompass ESI, emails, and physical documents.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Partly correct
- **Environment:** Defective: the supplied documents mischaracterize or miscite case law (citation sweep; peripheral to this criterion).
- **Note and source locator:** Defective / AI is Partly Correct. JOHN HUGHES: The rubric fails any draft that does not supply a definition of “document” encompassing electronically stored information (ESI). There are two problems:
- First, these are interrogatories, not document requests. Well-drafted interrogatories do not necessarily need to use the word “document.” The rubric does not really make sense as a requirement for this kind of work product.
- Second, even if were dealing with document requests here (which we are not), the local rules of many courts, including the Western District of Texas (where this fictitious case is being litigated), define the term “document” for all discovery requests served by litigants in those cases. There is thus no requirement to define the term “documents,” and in fact, supplying a definition could just trigger objections from the other side that the local rule controls. See Local Rule CV-26, available at https://www.txwd.uscourts.gov/court-information/lcr-civil-rules/ (“The term ‘document’ means any document or electronically stored information as described in Federal Rule of Civil Procedure 34(a). A draft of a nonidentical copy is a separate document within the meaning of this term.”). 
- The rubric does demonstrably fail rules-compliant work product. For example, Luna was failed for not including a definition of the term “Document” but that’s actually what the local rules encourage in this Court. 
- **Category**: unambiguous objective error, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-interrogatories/gpt6luna-xhigh/README.md#c-026) | Pass | Pass | 11 / 9 |
| [Claude Opus 5.5 (low)](../model-runs/draft-interrogatories/opus55-low/README.md#c-026) | Pass | Pass | 1 / 1 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-interrogatories/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-interrogatories/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-interrogatories/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-interrogatories/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-interrogatories/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-interrogatories/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** Interrogatory No. 9 specifically asks about the custody and disposition of the '2TB Corsair USB drive bearing serial number CX-8827491' after Oshiro began working for Veridian. Interrogatory No. 10 asks Veridian to identify all CMT Materials presently within its possession, custody, or control. Interrogatory No. 8 asks whether Oshiro or any other person provided or made available any CMT Materials to Veridian. These interrogatories collectively address both the USB drive (by serial number) and CMT files on Veridian systems, satisfying the criterion.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The interrogatories address both the USB drive and CMT materials: Interrogatory No. 9 asks about the 2TB Corsair USB drive with serial number CX-8827491 after Oshiro began working for Veridian, and Interrogatories Nos. 8, 10, and 11 ask whether CMT Materials were provided to, possessed by, reviewed, used, copied, or relied on by Veridian.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** Interrogatory No. 5 explicitly addresses both the USB Drive (defined as 'the 2TB Corsair portable external storage device bearing serial number CX-8827491') and CMT Materials on Veridian systems. It asks Veridian to identify every instance in which CMT Materials were brought onto Veridian premises, transmitted to, stored on, accessed from, or connected to any Veridian computer, server, network, cloud account, code repository, or device, and specifically asks whether the USB Drive was ever connected to any such device or system, with details on each connection by date, device, and user. This clearly satisfies the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** Interrogatory No. 5 specifically asks whether CMT Materials were brought onto, transmitted to, stored on, accessed from, or connected to Veridian systems/devices, and whether the USB Drive was ever connected to any such device or system, referencing the defined USB Drive with serial number CX-8827491.

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Defective: same task environment as item 13 (environment-only defect).
- **Note and source locator:** Not defective / AI is wrong. JOHN HUGHES: This one does not really belong on the list, as GPT-6-Sol was complaining about a different rubric (C-048) which it argues is inconsistent with this one. It does not identify any issue in this rubric, standing alone, so this counts as an instance where Sol added something to the “flagged” list that does not belong.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-litigation-discovery-responses/gpt6luna-xhigh/README.md#c-028) | Fail | Fail | 18 / 15 |
| [Claude Opus 5.5 (low)](../model-runs/draft-litigation-discovery-responses/opus55-low/README.md#c-028) | Pass | Pass | 5 / 4 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-litigation-discovery-responses/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-litigation-discovery-responses/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-litigation-discovery-responses/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-litigation-discovery-responses/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-litigation-discovery-responses/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-litigation-discovery-responses/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The agent's output does not specifically identify RFA No. 20 as calling for a legal conclusion regarding UCC § 2-314 merchantability. While the plan mentions denying RFAs 19-23 'insofar as they ask Prismavale to concede accuracy of Greenleaf's test results, nonconformity at shipment, causation, merchantability, or damages,' it does not specifically call out RFA No. 20 as presenting a legal conclusion problem, nor does it recommend objecting on the basis that the request calls for a legal conclusion regarding UCC § 2-314. The mention of 'merchantability' is bundled with other issues and does not identify the specific legal conclusion objection basis for RFA No. 20.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The plan discusses denying RFAs 19–23 to the extent they seek concessions on merchantability, but it does not specifically identify RFA No. 20 as calling for a legal conclusion regarding UCC § 2-314 merchantability or recommend objecting on that basis.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In Section 5.1 (RFAs), the table entry for RFA 20 states: 'Objection (the question mixes law and fact, and lumps two products together); deny.' This identifies that RFA 20 calls for a legal conclusion (mixing law and fact) and recommends objecting on that basis, which satisfies the criterion.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The plan specifically addresses RFA No. 20 and recommends an objection because it “mixes law and fact,” while also noting that Rule 36 permits application of law to fact. Although it does not expressly cite UCC § 2-314, it identifies the legal-conclusion/legal-standard issue with the merchantability request and recommends objecting on that basis.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the supplied Answer cites complaint paragraph ranges that do not match the complaint (e.g. Count III as ¶¶ 88–94; the complaint's Count III is ¶¶ 86–96).
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: Plaintiff served a request for admission on the defendant that says, “Admit that the SB-102 and PS-302 products shipped by Prismavale to Greenleaf were not merchantable as defined by the Uniform Commercial Code.” The prompt asks the agent to “prepare a discovery strategy memo and formal RFA/RFP responses.” The rubric requires “the plan” (i.e., the strategy memo) to recommend objecting to the request on the grounds that it calls for a legal conclusion. The rubric is wrong for two main reasons:
- First, the modern view is requests for admissions can call for application of law to facts. While it is within acceptable professional norms for a lawyer to object on the ground that such a request calls for a legal conclusion, and then proceed to answer, the better reading of the law is that this request is not objectionable such that the party should simply answer. On this legal conclusion in particular, there’s really no reason why one would prefer to object rather than simply deny the requested admission. So this rubric fails competent work product (and probably the better answer than the one the rubric calls for).
- Second, even assuming one should include the objection at all, the task fails the model if the issue is not expressly addressed in the strategy memo. Luna made the “legal conclusion” objection in the draft responses and then proceeded a substantive denial (an acceptable approach), but did not discuss the “legal conclusion” objection in the memo. That was judged a failure. That’s really requiring duplicative responses on a very minor point that probably shouldn’t be in the drafts at all.
- **Category**: low-quality professional judgment, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt6luna-xhigh/README.md#c-009) | Pass | Pass | 6 / 4 |
| [Claude Opus 5.5 (low)](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/opus55-low/README.md#c-009) | Pass | Pass | 1 / 1 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The motion explicitly identifies the arithmetic discrepancy in Section III.A.4: 'the five itemized amounts in the report total $14,211,000, not the stated $14,200,000. Dr. Marchetti acknowledged the discrepancy and could not explain it at deposition.' This clearly identifies the $11,000 difference between the sum of itemized categories ($14,211,000) and the stated total ($14,200,000).
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The motion expressly states that the five itemized damages amounts total $14,211,000, not the reported $14,200,000, and notes this as a discrepancy. Although it does not spell out '$11,000,' the discrepancy is clearly identified by the stated figures.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The motion explicitly identifies the $11,000 arithmetic discrepancy. In the Factual Background section (Section II.C), the motion includes a table showing the five components summing to $14,211,000, with a note that the 'Actual sum of components' is $14,211,000 versus the 'Stated total' of $14,200,000. It further states: 'The five components sum to $14,211,000, not $14,200,000; Dr. Marchetti could not explain the $11,000 discrepancy at deposition.' This is also addressed in Section IV.E ('The Unexplained Arithmetic Error Confirms the Absence of Rigor'), which explicitly discusses the $11,000 error and cites deposition testimony where Dr. Marchetti could not explain it.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The motion expressly states that the five damages components sum to $14,211,000 rather than the stated $14,200,000, and identifies the resulting $11,000 discrepancy multiple times.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the task directs advocacy outside professional norms (an $11,000 rounding point offered as a *Daubert* ground) and labels a rounding difference an "arithmetic error."
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The damages expert includes a summary table in her report listing various items of damages, which collectively add up to $14,211,000; the Total Damages line lists the total as $14,200,000. Opposing counsel questioned the expert about it at her deposition, and the expert calls it “a rounding discrepancy.” An internal strategy memo highlights the issue as a ground for seeking to exclude the expert’s testimony under *Daubert*, arguing “the arithmetic error supports a cumulative argument that the report was prepared without the rigor required of expert testimony in federal court.”
- This task is poorly specified, and the recommended strategy of raising this with the judge is a poor one:
- First, the task environment repeatedly states that this is an “arithmetic error.” That is false. The expert has rounded the total in the table to the nearest $100,000. While that is somewhat unorthodox in an expert report (particularly since it is written out as $14,200,000 not $14.2 million), numbers often are rounded in court filings so the judge is unlikely to agree that this is an error.
- Second, even if there were an error (which there is not), that is generally not a basis for excluding the expert’s testimony under *Daubert*. At most one could move to exclude the erroneous version and ask for more accurate testimony, but that does nothing to help the hypothetical client here; it just raises their damages exposure by the $11,000 that the expert was willing to round off.
- Third, the proposed framing of the argument comes very close to a breach of decorum and carries a real risk of drawing a rebuke from the judge. The strategy memo wants the motion to argue the expert’s 30 prior engagements were “in state courts and arbitrations that do not impose the same methodological gatekeeping requirements” as federal courts. While some state courts use the *Frye* standard instead of *Daubert*, many federal judges would take offense at the suggestion that state courts do not observe adequate methodological rigor. Many busy judges could be annoyed at spending time on an argument that literally just amounts to a rounding error.
- This rubric is scored as Defective, as a professional-judgment call rather than an objective error. Our view is that the better approach is to drop this issue entirely, and the sampled rubric (C-009) fails a motion that does so, even though a motion that merely mentions the discrepancy in a footnote would pass. The companion rubric, C-010, is in my view objectively wrong because it requires that this issue be presented as a basis for excluding the expert's testimony under *Daubert*. Luna was failed incorrectly on C-010 (by the Sonnet 4.6 judge) for downplaying this issue; in fact, Luna was right to do so, as it should not be raised at all. But since that's not the sampled criterion, we do not mark it here.
- **Category**: low-quality professional judgment, rubric is incorrect (a judgment call, not an objective error); defective environment (directs advocacy outside professional norms); companion rubric C-010 also incorrect (not sampled).

## 17. Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute — C-037

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/documents) · [Task audit page](../tasks/draft-motion-to-dismiss-brief/README.md)

**ISSUE_008 — Cites Delaware parol evidence authority**

> PASS if the motion brief cites relevant Delaware authority on the parol evidence rule and integration clauses, such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. FAIL if no Delaware parol evidence authority is cited.

<details><summary>AI findings (open after forming your own view)</summary>


Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O9: C-037 lists SIGA v. PharmAthene as Delaware parol-evidence authority, but that opinion does not address integration or parol evidence

Full reports: [GPT-6 Sol](../tasks/draft-motion-to-dismiss-brief/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-motion-to-dismiss-brief/claude-opus-5-5-audit.md).

</details>

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/README.md#c-037) | Fail | Fail | 29 / 30 |
| [Claude Opus 5.5 (low)](../model-runs/draft-motion-to-dismiss-brief/opus55-low/README.md#c-037) | Fail | Fail | 19 / 21 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-motion-to-dismiss-brief/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-to-dismiss-brief/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-to-dismiss-brief/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The motion brief does not cite any Delaware parol evidence authority such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. While the brief mentions that Delaware law governs the agreement under §12.7, it only cites Texas cases (Schlumberger, Forest Oil, Italian Cowboy Partners) for the non-reliance/integration clause arguments. No Delaware parol evidence rule cases are cited anywhere in the brief.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The brief notes that Delaware law governs the agreement but does not cite any Delaware authority on the parol evidence rule or integration clauses, such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care.
- **Claude Opus 5.5 (low), Sonnet 4.6: Fail.** The criterion requires citation of relevant Delaware authority on the parol evidence rule and integration clauses, specifically mentioning cases like SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. The motion cites Delaware cases including Abry Partners V, L.P. v. F & W Acquisition LLC (891 A.2d 1032, Del. Ch. 2006), Kuroda v. SPJS Holdings, L.L.C. (971 A.2d 872, Del. Ch. 2009), and VLIW Tech., LLC v. Hewlett-Packard Co. (840 A.2d 606, Del. 2003). While Abry Partners and Kuroda are cited for anti-reliance/non-reliance clauses and unjust enrichment, neither SIGA Technologies v. PharmAthene nor Eagle Industries v. DeVilbiss Health Care (the specific cases mentioned in the criterion) are cited. The criterion explicitly asks for those specific cases or similar Delaware parol evidence rule authority. The cases cited (Abry Partners, Kuroda) touch on related but distinct issues (anti-reliance clauses, unjust enrichment) rather than the parol evidence rule and integration clauses specifically. The criterion fails because the specifically named cases are not present and no Delaware authority specifically addressing the parol evidence rule and integration clauses is cited.
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The brief cites Delaware cases such as Abry, Kuroda, and VLIW, but it does not cite Delaware parol-evidence/integration-clause authority like SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care, nor any equivalent Delaware parol evidence rule case.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the supplied research memo cites fabricated or mischaracterized authority (citation sweep: 28 of 53 citations in this task have problems).
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The rubric here involves a legal error, and the task environment contains hallucinations about case law. This one is extremely defective for multiple reasons:
- First, the rubric is demanding case law on the wrong legal doctrine. Under Delaware law,  the parol evidence rule and an integration clause do not preclude fraud claims. The issue here is whether the plaintiff can reasonably allege that they relied on their counterparty’s pre-signing representations despite their agreement in the contract that they were not relying on any representations other than those written in the contract itself.
- Second, the cases in the environment appear to contain multiple hallucinations. The rubric refers to SIGA v. PharmAthene, but Opus noted that case does not address integration or parol evidence. The task environment contains a legal research memo that cites *SIGA Technologies, Inc. v. PharmAthene, Inc.*, 67 A.3d 330 (Del. 2013), and claims that it states (at page 344), "an integration clause is the clearest declaration that the parties intend the writing to be the complete and final expression of their agreement." The quoted language does not appear in the cited case. Page 344 of that case addresses the duty to negotiation in good faith, not integration clauses. Similarly, the memo cites *Eagle Industries, Inc. v. DeVilbiss Health Care, Inc.*, 702 A.2d 1228 (Del. 1997) and says: “The Delaware Supreme Court held that ‘a party to a contract cannot promise, in a clear integration clause of a negotiated agreement, that it is not relying on promises or representations made by the other party outside of the agreement, and then assert a claim for fraud based on those very representations.’ *Id.* at 1232.” The quoted language does not appear in the cited case.
- Third, the rubric failed responses that stated the correct law on this point. In our tests, Opus reviewed SIGA and Eagle, correctly realized they were inapposite and declined to cite them, cited more on-point and accurate authority, and was then failed for doing a better job than the rubric's author did at this task.
- **Category**: unambiguous objective error (including halluciations), rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/README.md#c-045) | Fail | Fail | 29 / 30 |
| [Claude Opus 5.5 (low)](../model-runs/draft-motion-to-dismiss-brief/opus55-low/README.md#c-045) | Fail | Fail | 19 / 21 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-to-dismiss-brief/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-motion-to-dismiss-brief/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-motion-to-dismiss-brief/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-motion-to-dismiss-brief/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The brief mentions MSLSA §3.5 adjusting milestones 'day-for-day when Arcadia's failure to perform its responsibilities causes delay,' but does not specifically identify the 45-day Project Manager gap (Kevin Liu's departure) or the 75-day late API specifications as concrete examples of Arcadia's contributory delays. The criterion requires that these specific contributing failures be identified. The brief's general reference to Arcadia's failure to perform responsibilities is insufficient to satisfy the criterion's requirement for specific mention of these delays.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The brief generally notes that milestones could adjust for Arcadia-caused delays, but it does not identify the specific Arcadia contributing failures required by the criterion, such as the 45-day Project Manager gap after Kevin Liu’s departure or the 75-day late API specifications.
- **Claude Opus 5.5 (low), Sonnet 4.6: Fail.** The motion brief does not mention Arcadia's own contributing delays to the Go-Live delay, such as the 45-day Project Manager gap (Kevin Liu's departure) or the 75-day late API specifications. The brief discusses the Go-Live delay (September 1, 2022 target vs. January 15, 2023 actual) but does not attribute any portion of that delay to Arcadia's own failures or contributory conduct.
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The brief mentions that Go-Live occurred later than the target date and argues generally that data migration was Arcadia’s responsibility, but it does not identify Arcadia’s own contributing delay facts, such as the 45-day Project Manager gap from Kevin Liu’s departure or the 75-day late API specifications, as causes of the Go-Live delay.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: same task environment as item 17.
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The rubric makes a rookie mistake, demanding that the agent argue a factual dispute on a motion to dismiss, where the court is required to assume the plaintiff’s allegations are true and cannot consider factual dispute. The 45-day and 75-day delays complained of come from the defendant’s internal report, which the plaintiff’s complaint disputes. Moreover, courts generally cannot resolve messy fact disputes over “causation” on a motion to dismiss.
- The criterion failed agents that correctly recognized that this argument was outside the scope of what can be argued on a motion to dismiss and thus decided to excluded it.
- **Category**: unambiguous objective error, rubric is incorrect.

## 19. Draft Verified Responses and Objections to Plaintiff's First Set of Interrogatories in Commercial Breach of Contract and Fraud Action — C-028

[Criterion in pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/task.json#L236) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/documents) · [Task audit page](../tasks/draft-responses-to-interrogatories/README.md)

**Correct financial figures for Tri-Basin purchase history**

> PASS if any purchase history figures cited in the responses are consistent with the canonical data: 2015: $9.2M; 2016: $10.1M; 2017: $10.8M; 2018: $12.4M; 2019: $13.6M; 2020: $9.7M; 2021: $15.3M; 2022: $16.8M; 2023 (Jan–Aug): $11.9M. Minor rounding differences are acceptable. Also PASS if the response invokes Rule 33(d) rather than citing specific figures. FAIL if specific purchase figures are cited but are materially incorrect.

<details><summary>AI findings (open after forming your own view)</summary>


Agreement group: Flagged by Claude Opus 5.5 only. GPT-6 Sol: not flagged; Claude Opus 5.5: arguable (blind pass: arguable).

- **Claude Opus 5.5:** O7: The purchase-history spreadsheet has two conflicting 2020 monthly series ($8.7M vs $9.7M subtotals)

Full reports: [GPT-6 Sol](../tasks/draft-responses-to-interrogatories/gpt-6-sol-audit.md) · [Claude Opus 5.5](../tasks/draft-responses-to-interrogatories/claude-opus-5-5-audit.md).

</details>

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/draft-responses-to-interrogatories/gpt6luna-xhigh/README.md#c-028) | Pass | Pass | 3 / 2 |
| [Claude Opus 5.5 (low)](../model-runs/draft-responses-to-interrogatories/opus55-low/README.md#c-028) | Pass | Pass | 1 / 3 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/draft-responses-to-interrogatories/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-responses-to-interrogatories/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-responses-to-interrogatories/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/draft-responses-to-interrogatories/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/draft-responses-to-interrogatories/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/draft-responses-to-interrogatories/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The agent's output in Interrogatory No. 14 provides a detailed table of Tri-Basin purchase figures: 2015: $9.2M, 2016: $10.1M, 2017: $10.8M, 2018: $12.4M, 2019: $13.6M, 2020: $9.7M, 2021: $15.3M, 2022: $16.8M, Jan–Aug 2023: $11.9M. These match exactly the canonical figures specified in the criterion. The figures are also referenced consistently in other interrogatory responses (e.g., Nos. 4, 17, 22). All figures are accurate and consistent with the canonical data.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The responses cite Tri-Basin purchase history figures that match the canonical data: 2015 $9.2M, 2016 $10.1M, 2017 $10.8M, 2018 $12.4M, 2019 $13.6M, 2020 $9.7M, 2021 $15.3M, 2022 $16.8M, and Jan.–Aug. 2023 $11.9M. Other references to these figures are consistent.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The agent's output in Interrogatory No. 14 provides a detailed table of Tri-Basin's annual purchases: 2015: $9,200,000; 2016: $10,100,000; 2017: $10,800,000; 2018: $12,400,000; 2019: $13,600,000; 2020: $9,700,000; 2021: $15,300,000; 2022: $16,800,000; 2023 (Jan.–Aug.): $11,900,000. These figures match exactly the canonical data provided in the criterion. The agent also invokes Rule 33(d) to refer to underlying SAP records. All figures are consistent with the canonical data.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The responses cite Tri-Basin purchase history figures in Interrogatory No. 14 that match the canonical data exactly, including 2015 $9.2M, 2016 $10.1M, 2017 $10.8M, 2018 $12.4M, 2019 $13.6M, 2020 $9.7M, 2021 $15.3M, 2022 $16.8M, and 2023 Jan–Aug $11.9M. Other cited related figures appear consistent or are provided via Rule 33(d).

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Partly correct
- **Environment:** Defective: the purchase-history spreadsheet is internally inconsistent (three 2020 series; line items that do not sum to subtotals), and the record has no contract-year data.
- **Note and source locator:** Defective / AI is partly correct. JOHN HUGHES: There are two issues:
- First, Interrogatory No. 4(b) asks for Tri-Basin’s actual purchases for the 2020 contract year (the contract year runs from January 15 through January 14 of the following year; Interrogatory No. 14 separately asks for calendar-year totals), but the canonical data referred to in the rubric is calendar year data, so the rubric's numbers are not correct for that request. The correct value cannot be discerned from the environment: the monthly data cannot be split at January 15, and nothing in the record supports assuming purchases are spread evenly within January (seasonal variation would make that unlikely). The rubric therefore grades wrong in the opposite direction from most of the other items: rather than failing good work product, it passes responses that supply the calendar-year figure for a contract-year request without acknowledging that the record does not contain the requested data. That is approving fundamentally deficient work product.
- Second, the data that is provided has some internal inconsistencies. For example, an “annual summary” tab lists 2020 purchases at $9.7 million, but the monthly detail lists 2020 three times, with totals of $8,700,000, $8,549,400 and $9,700,000. The units sold do not match up between those two sheets for 2021, 2022, 2023, and series 3 of 2020. One of the monthly rows does not add up (gross $1,210,000 + credits −$17,400 = $1,192,600, but the net shown is $1,192,500). The annual summary minimums do not add up. In the Product Line Breakdown, line-item net revenue never sums to the subtotal. So a response that relied on the line items would get graded as a failure.
- The environment contains law firm discovery guidelines that recommend that interrogatory responses match the client's Answer, but the Answer here contains only approximate figures, which is consistent with the Answer using calendar year data as a rough approximation instead of providing the contract year data requested.
- **Category**: unambiguous objective error, deficiency in task environment; rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/gpt6luna-xhigh/README.md#c-002) | Fail | Fail | 12 / 12 |
| [Claude Opus 5.5 (low)](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/opus55-low/README.md#c-002) | Pass | Fail | 3 / 2 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo acknowledges the two different time periods (January 1, 2017 for financial records and January 1, 2019 as the general relevant period) in Section 3.3, but it treats them as complementary rather than conflicting, simply stating to 'preserve earlier-period archives and backups with the same rigor.' The memo does not recommend seeking clarification from DOJ about this date discrepancy. It only recommends seeking DOJ clarification for the Exhibit B category count discrepancy (36 vs. 34 categories) and for the deadline receipt date. There is no recommendation to seek DOJ clarification specifically about the conflicting financial records date ranges (2017 vs. 2019).
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The memo identifies both the general Jan. 1, 2019 relevant period and an extended Jan. 1, 2017 financial-records period, but it treats the 2017 period as controlling/extended rather than flagging a conflict and recommending DOJ clarification regarding the date discrepancy for financial records.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The memo addresses the financial records date discrepancy in multiple places. In Section VI (Reconciling the Notice's Category Numbering), it identifies the ¶47 cross-reference issue and recommends: 'Also consider preserving 2017–2018 Velcara pre-launch marketing materials (Area 7 in Exhibit B) until DOJ clarifies in writing.' In Section XI (Points to Clarify With DOJ), item 18 explicitly lists 'The 36 vs. 34 categories, and whether HCP communications (¶¶23–24) are the two unnumbered categories. The ¶47 reference to "Area 7"' as a point to raise with DOJ in writing before March 13. The memo thus recommends seeking written clarification from DOJ regarding the ¶47 numbering discrepancy, which relates to the financial records date range conflict.
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The memo identifies the general relevant period as Jan. 1, 2019 and financial records as Jan. 1, 2017, and it recommends preserving the broader financial period. It also recommends asking DOJ to clarify ¶47’s Area 7/category inconsistency, but it does not specifically recommend DOJ clarification of a conflicting Jan. 1, 2017 vs. Jan. 1, 2019 date range for financial records.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The task involves a document preservation notice from federal criminal authorities that defines the relevant period (for which the recipient must preserve documents) as January 1, 2019, through March 3, 2025 “unless otherwise specified herein.” For one specific category of documents, the notice states that, “Notwithstanding the Relevant Period defined in Paragraph 12 of this Notice, Ridgeline shall preserve [certain kinds of] records . . . from January 1, 2017 to the present date. ”
- The rubric suggests that the agent should seek clarification of the “conflicting” date ranges but there is no conflict. The notice quite clearly imposed a longer period for one specific category of documents, while all the other categories are subject to a shorter period. This is a fairly common request.
- All the models were failed on this criterion, but the criterion makes no sense.
- **Category**: unambiguous objective error, rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/gpt6luna-xhigh/README.md#c-013) | Pass | Pass | 12 / 10 |
| [Claude Opus 5.5 (low)](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/opus55-low/README.md#c-013) | Pass | Pass | 13 / 9 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The memo explicitly identifies in Section 2.2 that Wendt (July 1, 3.2h and July 5, 4.0h) and Takahashi both researched the MTCA contractor-liability framework during July 1-2, citing Section 6.4 as the basis for the duplicative research prohibition. The memo recommends a $3,060.00 credit for this overlap and instructs to retain the most junior qualified researcher's work. This directly satisfies the criterion of identifying overlapping MTCA liability/contractor liability research billed by both Takahashi and Wendt.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The memo explicitly identifies overlapping MTCA contractor-liability research by Wendt on July 1 and July 5 and Takahashi on July 1–2, references summary-judgment-related overlap, and invokes Section 6.4’s duplicative research rule to recommend retaining only the junior qualified researcher’s work.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** The memo explicitly identifies in Section 3.2 that both Takahashi and Wendt billed for overlapping MTCA contractor liability/SJ standards research, with Takahashi L1 and L6 allowed as the most junior qualified researcher, while Wendt L2 ($1,360.00) and L15 ($1,700.00) are disallowed under §6.4. The memo also references Hargrove L24 as duplicating MTCA preemption/contractor defense research by Takahashi. This clearly identifies the duplicative MTCA research across multiple timekeepers including Takahashi and Wendt, citing Section 6.4.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The memo expressly identifies overlapping MTCA contractor liability / summary judgment research by Kenji Takahashi and Tyler Wendt in July 2024, allows Takahashi L1/L6 as the most junior researcher, disallows Wendt L2/L15, and cites Guidelines §6.4 on duplicative research.

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Correct
- **Note and source locator:** Not defective / AI is wrong. JOHN HUGHES: While Sol is right that the facts here are insufficient to establish that the client’s billing guidelines were violated, for purposes of the task (a client-side memo identifying changes to dispute). it seems reasonable to flag that multiple attorneys were doing research into closely related issues. The task requested a memo “a memo identifying all non-compliant or excessive charges with recommended adjustments,” so flagging potential violations (even if they were not clearly proven from the face of the time entries) is a standard approach a client would take here.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/identify-issues-in-matter-budget-proposal/gpt6luna-xhigh/README.md#c-029) | Pass | Pass | 5 / 5 |
| [Claude Opus 5.5 (low)](../model-runs/identify-issues-in-matter-budget-proposal/opus55-low/README.md#c-029) | Pass | Pass | 2 / 2 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/identify-issues-in-matter-budget-proposal/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/identify-issues-in-matter-budget-proposal/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/identify-issues-in-matter-budget-proposal/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/identify-issues-in-matter-budget-proposal/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/identify-issues-in-matter-budget-proposal/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/identify-issues-in-matter-budget-proposal/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The agent's output uses a three-tier severity scale: Critical, High, and Medium. The fee budget reconciliation discrepancy ($116,050 difference between phase-based fees and staffing-table fees) is listed in the 'Priority findings at a glance' table under the 'Critical' severity level, which is the highest tier in the scale used. This satisfies the criterion that the issue be assigned Critical or High severity.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The output identifies the $116,050 fee reconciliation discrepancy and labels the issue 'Critical' in the priority findings table, satisfying the requirement that it be rated Critical or High.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** Issue C-1 in the agent's output explicitly addresses the $116,050 fee reconciliation discrepancy between the phase table ($1,708,950) and the staffing table ($1,825,000). It is assigned a severity of 'High' in the issue summary table, which is the second-highest tier in the two-tier severity scale used (High and Medium, with High being the top tier). This satisfies the criterion requiring the discrepancy to be rated Critical or High (or the highest/second-highest tier).
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The output explicitly identifies the $116,050 fee reconciliation discrepancy between the phase table and staffing/hourly totals as Issue C-1 and assigns it a High severity rating.

</details>
<!-- runs:end -->

- **Verdict:** Arguable
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Arguable / AI is correct. JOHN HUGHES: The prompt requested “a categorized issue memorandum” but didn’t specify what the categories should be. The rubric fails the model if it does not break issues into severity levels or it does not assign a critical or high severity level to a specific issue. While it appears that models often do volunteer this kind of severity assessment, it’s not requested by the prompt and competent work product could decline to include it.
- **Category**: requires specific outputs not expressly or impliedly requested in the prompt.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/review-counterpartys-proposed-jury-instructions/gpt6luna-xhigh/README.md#c-020) | Fail | Fail | 9 / 6 |
| [Claude Opus 5.5 (low)](../model-runs/review-counterpartys-proposed-jury-instructions/opus55-low/README.md#c-020) | Fail | Fail | 1 / 1 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/review-counterpartys-proposed-jury-instructions/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-counterpartys-proposed-jury-instructions/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/review-counterpartys-proposed-jury-instructions/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/review-counterpartys-proposed-jury-instructions/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-counterpartys-proposed-jury-instructions/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/review-counterpartys-proposed-jury-instructions/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Fail.** The memo objects to the 'independently wrongful act' element in Instruction No. 27 and states that the Court's four-element formulation does not include it, but it does not explain *why* that element is wrong as a matter of Georgia law. Specifically, it never articulates the legal distinction that the 'independently wrongful act' requirement belongs to tortious interference with business relations (a prospective economic advantage tort), not to tortious interference with an existing contract, where knowing inducement of breach is sufficient. The memo simply says 'do not add an independent-wrongful-act prerequisite' without explaining that this element applies to a different tort. The criterion requires that this legal distinction be articulated.
- **GPT-6 Luna (xhigh), GPT-5.5: Fail.** The memo correctly states that tortious interference with an existing contract under Georgia law uses the four elements of valid contract, knowledge, intentional inducement to breach, and damages, and objects to adding an independently wrongful act requirement. However, it does not articulate the specific distinction that the independently wrongful act element belongs to the separate tort of tortious interference with business relations. The criterion requires that distinction to be explained.
- **Claude Opus 5.5 (low), Sonnet 4.6: Fail.** The memo's Section K (Instruction No. 27) objects to the 'independently wrongful act' element and cites the SJ Order's four-element formulation, but it does not explain that the 'independently wrongful act' requirement belongs to the distinct tort of tortious interference with business relations (as opposed to interference with an existing contract). The memo simply says the added elements 'go beyond the elements the Court identified' without articulating the legal distinction between the two torts under Georgia law. The criterion requires the memo to explain that for tortious interference with an existing contract, knowing inducement of breach is sufficient and the independently wrongful act element applies only to the separate tort of interference with business relations. This distinction is not articulated in the memo.
- **Claude Opus 5.5 (low), GPT-5.5: Fail.** The memo correctly objects that the proposed tortious-interference-with-contract instruction improperly adds an “independently wrongful act” element and states that the Court identified only the four existing-contract elements, including knowing inducement of breach. However, it does not articulate the requested distinction that the independently wrongful act requirement belongs to the separate tort of tortious interference with business relations, not interference with an existing contract.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Defective: the fictional summary-judgment order cites a case for the opposite of its holding and a case that cannot be found (citation sweep: 10 of 21 citations in this task have problems).
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: Multiple issues:
- First, this is a clear legal error. Georgia applies the same elements to interference with contractual and business relations. The rubric says the opposite of what Georgia law is. *Disaster Services, Inc. v. ERC P'ship*, 228 Ga. App. 739, 740–41 (1997) (“Tortious interference claims, whether asserting interference with contractual relations, business relations, or potential business relations, share certain common essential elements: (1) improper action or wrongful conduct by the defendant without privilege; (2) the defendant acted purposely and with malice with the intent to injure; (3) the defendant induced a breach of contractual obligations or caused a party or third parties to discontinue or fail to enter into an anticipated business relationship with the plaintiff; and (4) the defendant's tortious conduct proximately caused damage to the plaintiff.”). 
- Second, the fictional summary judgment order (from which the rubric’s legal position seems to be taken) appears to contain several hallucinations. For example, the order paraphrases the third and fourth element described in *Disaster Services* approximately correctly, but the first two elements are erroneously listed as “(1) the existence of a valid contract between the plaintiff and a third party; (2) the defendant's knowledge of the contract.” The fictional order also cites *Valdosta Livestock, Inc. v. Furst*, 342 Ga. App. 25, 28 (2017), which is not found in any legal databases.
- **Category**: unambiguous objective error (including halluciations), rubric is incorrect.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/README.md#c-024) | Pass | Pass | 11 / 8 |
| [Claude Opus 5.5 (low)](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/README.md#c-024) | Pass | Pass | 2 / 3 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The report explicitly states in the expense table for E-011: 'Messina's $387 black car is prohibited' and includes the $387 black car in the expense adjustment snapshot as a recommended disallowance. This satisfies the criterion of recommending full disallowance of the $387 black car service.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The report explicitly identifies Messina's $387 black car charge as prohibited and recommends reducing/disallowing the full $387.00, including it in the expense adjustment snapshot.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In Section 4.4, the report explicitly addresses E-011 (Messina black car service) and recommends a full disallowance of $387.00, citing §6.1 which states it is 'never reimbursable'. The adjustment schedule in Section 7 also includes this amount within the SF travel expenses disallowance (D-7, $7,234.00 total). The criterion is satisfied.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The report specifically identifies E-011 as “Messina black car service” billed at $387.00, marks the compliant amount as $0.00, and recommends a $387.00 reduction because it is never reimbursable. It also disallows all related SF travel expenses in the main adjustment schedule.

</details>
<!-- runs:end -->

- **Verdict:** Not defective
- **AI reasoning:** Wrong
- **Environment:** Correct
- **Note and source locator:** Not defective / AI is wrong. JOHN HUGHES: The billing guidelines state that “Reimbursable ground transportation is limited to ride-share … or taxi” and “Limousine services and black car services are not reimbursable under any circumstances.” Sol’s critique of the rubric is that the policy requires disallowing black car reimbursement, not reducing the reimbursement amount to what a taxi or ride share would have cost. The rubric’s interpretation (that either disallowing the expense entirely or capping reimbursement at the amount a taxi would have cost) seems reasonable and closer to the likely real-world application of a policy like this.

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

<!-- runs:start -->
<details><summary>How the model runs were graded (open after forming your own view)</summary>

Native LAB grades of the published runs; the judges are AI models and can misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a judge only if every criterion passes, so a Fail here with 0 other failures would by itself have zeroed that judge's score. Each run link opens the deliverables and every criterion's grades.

| Run | Sonnet 4.6 | GPT-5.5 | Other criteria failed (Sonnet 4.6 / GPT-5.5) |
|---|---|---|---|
| [GPT-6 Luna (xhigh)](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/README.md#c-042) | Pass | Pass | 11 / 8 |
| [Claude Opus 5.5 (low)](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/README.md#c-042) | Pass | Pass | 2 / 3 |

Raw files:

- GPT-6 Luna (xhigh): [Sonnet 4.6 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/scores_gpt-5.5.json) · [deliverables](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/gpt6luna-xhigh/README.md#deliverables)
- Claude Opus 5.5 (low): [Sonnet 4.6 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/scores_claude-sonnet-4-6.json) · [GPT-5.5 score file](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/scores_gpt-5.5.json) · [deliverables](../model-runs/review-litigation-invoice-against-outside-counsel-billing-guidelines/opus55-low/README.md#deliverables)

- **GPT-6 Luna (xhigh), Sonnet 4.6: Pass.** The report states: 'Business class on the domestic Chicago–San Francisco itinerary is allowable only if scheduled flight duration was at least four hours; obtain itinerary.' This treats the business class airfare as a borderline/requires discussion issue rather than a clear mandatory reduction. It does not automatically disallow the business class fare; instead, it conditions allowability on whether the scheduled flight duration meets the 4-hour threshold and requests the itinerary to verify. This acknowledges the ambiguity (the flight duration is close to the threshold) and defers the determination pending documentation, which satisfies the criterion.
- **GPT-6 Luna (xhigh), GPT-5.5: Pass.** The report does not treat Messina’s business-class airfare as a clear mandatory reduction or simply compliant. It flags the issue as conditional, stating that business class on the Chicago–San Francisco itinerary is allowable only if the scheduled flight duration was at least four hours and requests the itinerary, which effectively classifies it as requiring documentation/discussion given the threshold issue.
- **Claude Opus 5.5 (low), Sonnet 4.6: Pass.** In Section 4.4, the report explicitly addresses Messina's business-class airfare (E-008, $2,847.00) and states: 'business class is allowed only if the scheduled flight is 4+ hours. ORD–SFO is typically scheduled at about 4h15m–4h45m, so it may qualify. Ask for the itinerary; if under 4 hours, reduce to the economy fare.' This clearly treats the issue as borderline/requires discussion rather than a mandatory reduction or dismissing it as compliant. The action column says 'Verify' for both the compliant amount and the reduction, confirming the ambiguity is acknowledged.
- **Claude Opus 5.5 (low), GPT-5.5: Pass.** The report treats Messina’s $2,847 business-class airfare as a verification/discussion item, noting that business class is allowed only for scheduled flights of 4+ hours, that ORD–SFO typically may qualify, and requesting the itinerary before any reduction. It does not classify the airfare as a clear mandatory reduction or dismiss it as fully compliant.

</details>
<!-- runs:end -->

- **Verdict:** Defective
- **AI reasoning:** Correct
- **Environment:** Correct
- **Note and source locator:** Defective / AI is correct. JOHN HUGHES: The rubric’s analysis is wrong. The travel policy included in the environment states, “For domestic flights with a scheduled duration of four (4) hours or more, business class may be booked without prior approval.”  The record does not state the flight’s duration (the invoice lists only the route and fare class). The only basis for raising this seems to be in the rubric itself, which says the flight could take 4h20m, but even under that view, there’s nothing to discuss, as the policy allows business class for that duration.
- **Category**: unambiguous objective error, rubric is incorrect.

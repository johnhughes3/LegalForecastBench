# Claude Opus 5.5 audit: Build Litigation Case Timeline — Chronological Event Summary for Breach of Contract and Fraud Defense

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 64. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly well grounded. The timeline-entry criteria and numeric criteria track the record, and the analytic issues are supported by the documents: selective QA enforcement, the causation loop, speculative 5-year damages, spoliation, and auto-renewal. Three criteria would misgrade competent work. C-045 rests on a wrong premise, because the fraud claim is timely without any discovery rule and the posited post-filing discovery date is impossible. C-009 and C-050 fix the non-renewal deadline at Dec 15 when the EDA arithmetic and the Holcomb summary give Dec 14. C-052 demands a ranked top-5 summary the instructions never request. C-053 to C-057 (a claim-by-claim assessment in a 'summary section') and C-047 (a mismatch between its PASS and FAIL conditions) are arguable. Under all-pass scoring across 64 criteria, these defects make a perfect score depend on matching the rubric author's template.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L371) | C-045 assumes the fraud claim needs a discovery rule to be timely; it is timely on its face and the posited discovery date is impossible | blind |
| [O2](#o2) | problematic | source_conflict | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L83), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L411) | Non-renewal deadline fixed at Dec 15, 2022; the EDA arithmetic and the Holcomb summary give Dec 14 | blind |
| [O3](#o3) | problematic | unrequested_requirement | [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L427) | Requires a ranked 'top 5 critical issues' summary the one-line instructions never ask for | blind |
| [O4](#o4) | arguable | unrequested_requirement | [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L435), [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L443), [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L451), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L459), [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L467) | Hidden 'summary section' with claim-by-claim exposure assessments and pre-filing next steps; client side never stated | blind |
| [O5](#o5) | arguable | ambiguous_or_unjudgeable | [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L387) | C-047's PASS ('consciousness of guilt') and FAIL ('spoliation or evidentiary integrity') conditions do not align | blind |

<a id="o1"></a>
### O1. C-045 assumes the fraud claim needs a discovery rule to be timely; it is timely on its face and the posited discovery date is impossible

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L371)

All alleged fraud conduct runs from June 2022 to Feb 2023. The Complaint was filed Feb 28, 2024, less than two years after even the earliest act (June 8, 2022). Under ORS 12.110(1) the claim is timely without any discovery rule, and the statute's discovery clause sets accrual rather than tolling. C-045 requires the answer to say discovery 'potentially mak[es] the fraud claim timely despite the 2-year statute.' It also suggests Harborview may not have discovered the fraud until the Sept 30, 2024 production, which is impossible because the Feb 2024 Complaint quotes the June 8, Sept 14, Oct 3 and Dec 1 emails. A competent answer that says SOL is not a viable defense because everything falls within two years of filing, and builds no tolling theory, would fail.

Evidence:
- `C-045`: “Harborview may not have discovered the selective QA enforcement and Cascade diversion until the September 30, 2024 document production or some earlier point, potentially making the fraud claim timely despite the 2-year statute”
- `plaintiff-complaint.docx.txt`: “Harborview filed this action on February 28, 2024. This filing is within two years of the last acts of diversion and fabricated quality-control rejections”
- `plaintiff-complaint.docx.txt`: “On or about June 8, 2022, Holcomb sent an email to Nolan Yee of Cascade stating: "Let's start with a small trial run”

Authorities (✓ = primary text checked in the auditing session):
- ORS 12.110(1) (unverified): Two-year limitation; in an action based on fraud or deceit the limitation is deemed to commence only from discovery of the fraud.

Suggested fix: PASS if the output assesses timeliness correctly: timely because it was filed within two years of all alleged conduct, with the discovery-based accrual as further support. Delete the post-filing discovery date and the 'despite the 2-year statute' premise.

Related GPT-6 Sol findings: Definite defects: item 2.

<a id="o2"></a>
### O2. Non-renewal deadline fixed at Dec 15, 2022; the EDA arithmetic and the Holcomb summary give Dec 14

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L83), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L411)

EDA §9.3 requires notice 'at least ninety (90) days prior to the expiration' of a term that expires March 14, 2023 (§9.1). Dec 14 to Mar 14 is exactly 90 days (17+31+28+14), so Dec 14 is the last compliant date and a Dec 15 notice would be 89 days. The Holcomb deposition summary says Dec 14. The Complaint ¶49, the Chakrabarti report and the Dec 1 internal email say Dec 15. C-009 makes Dec 15 the PASS anchor, and C-050 states Dec 15 as the deadline. A solver who computes the date correctly or follows the deposition summary risks a literal-minded FAIL on C-009, and C-050 rewards a wrong fact.

Evidence:
- `exclusive-distribution-agreement.docx.txt`: “expiring on March 14, 2023”
- `deposition-summary-holcomb.docx.txt`: “the December 14, 2022 date would have been the 90-day deadline for non-renewal notice prior to the March 14, 2023 expiration”
- `plaintiff-complaint.docx.txt`: “any notice of non-renewal had to be sent no later than December 15, 2022”
- `C-009`: “PASS if the timeline includes an entry for December 15, 2022 (or references this date) as the deadline”

Suggested fix: In C-009 and C-050, accept Dec 14 or Dec 15, 2022 (or mid-December), and credit an answer that notes the discrepancy. The core point is that no notice was sent, so the EDA auto-renewed.

Related GPT-6 Sol findings: Definite defects: item 1.

<a id="o3"></a>
### O3. Requires a ranked 'top 5 critical issues' summary the one-line instructions never ask for

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L427)

The only instruction is to build a detailed litigation case timeline with strategic annotations for SJ preparation. Inline strategic annotations fully satisfy that. A separate summary section ranking about five issues by importance is a template feature, not an implicit part of a case timeline. A thorough annotated timeline with no ranked list, or with unranked issue groupings, is competent work, yet it fails this criterion and scores zero under all-pass.

Evidence:
- `instructions`: “Review the attached documents and build a detailed litigation case timeline with strategic annotations for summary judgment preparation.”
- `C-052`: “PASS if the output includes a summary section that identifies and ranks the top 5 (or approximately 5) most critical issues for summary judgment by importance.”

Suggested fix: Drop C-052, or pass any output that identifies the most significant SJ issues anywhere, with no count, ranking or section requirement.

Related GPT-6 Sol findings: Definite defects: item 3.

<a id="o4"></a>
### O4. Hidden 'summary section' with claim-by-claim exposure assessments and pre-filing next steps; client side never stated

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L435), [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L443), [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L451), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L459), [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L467)

'Strategic annotations for summary judgment preparation' arguably implies assessing claims and next steps, so the substance is not clearly hidden. But the criteria tie the assessment to 'the summary section,' require separate coverage of all four claims, and frame it as Greenleaf's exposure. The instructions never say which side the solver represents. The side is inferable, since Greenleaf's counsel prepared the Holcomb summary. A solver who analyzes the claims only in entry-level annotations or in a differently named section, or who writes neutrally, risks failing up to five criteria under a literal judge.

Evidence:
- `C-053`: “PASS if the summary section includes an assessment of Greenleaf's exposure on Harborview's Breach of Contract (exclusivity violation) claim.”
- `C-057`: “PASS if the summary section includes recommended next steps before filing the summary judgment motion”
- `deposition-summary-holcomb.docx.txt`: “This deposition summary was prepared by Colin Rourke, Senior Associate, Ashford, Kline & Pryor LLP”

Suggested fix: Pass equivalent claim assessments and next steps wherever they appear in the output, or state in the instructions that the user is Greenleaf's counsel and wants a closing claim-by-claim assessment.

Related GPT-6 Sol findings: Definite defects: item 3.

<a id="o5"></a>
### O5. C-047's PASS ('consciousness of guilt') and FAIL ('spoliation or evidentiary integrity') conditions do not align

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L387)

The Dec 1, 2022 'supply chain issues' email is most naturally analyzed as an affirmative misrepresentation, as concealment, and as impeachment material, and C-008 and C-049 already credit those uses. C-047's PASS accepts a link to 'consciousness of guilt,' but its FAIL condition requires a link to 'spoliation or evidentiary integrity concerns.' An answer that calls the email a knowing cover story evidencing fraudulent intent, without tying it to preservation, falls between the two conditions. Judges may split on it. The record does support a spoliation issue (a March 2024 hold and vague retention testimony), so the criterion is defensible but inconsistently framed.

Evidence:
- `C-047`: “FAIL if the false supply chain explanation is not connected to spoliation or evidentiary integrity concerns.”
- `deposition-summary-holcomb.docx.txt`: “"I follow company retention policies. I don't recall deleting anything specific."”

Suggested fix: Pass if the output treats the Dec 1 email as evidence of knowing concealment or falsity (fraud intent, consciousness of guilt, impeachment, or spoliation risk), and align the FAIL condition with that.

Related GPT-6 Sol findings: Arguable/qualified concerns: item 1.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Definite defects: item 1 | confirmed | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L83), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L411) | problematic | EDA §9.1 has the term expiring March 14, 2023, and §9.3 requires notice 'at least ninety (90) days prior.' Counting back gives Dec 14 (17+31+28+14=90), and the Holcomb deposition summary says Dec 14. The Complaint ¶49, the Chakrabarti report and the Dec 1 email say Dec 15. C-009 makes Dec 15 the PASS anchor and C-050 states it as fact. A solver who computes the date correctly risks failing C-009. |
| Definite defects: item 2 | confirmed | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L371) | problematic | The earliest alleged conduct is June 8, 2022 and the Complaint was filed Feb 28, 2024. The claim is inside two years on its face, and the Complaint itself pleads this. C-045 requires a discovery or tolling theory making the claim timely 'despite the 2-year statute.' It also floats a discovery date of Sept 30, 2024, which is impossible because the Complaint already quotes the emails. The premise is wrong. |
| Definite defects: item 3 | confirmed | [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L235) (not_a_defect), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L243) (not_a_defect), [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L427) (problematic), [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L435) (arguable), [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L443) (arguable), [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L451) (arguable), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L459) (arguable), [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L467) (arguable) | mixed | Source cites and named actors are standard parts of a litigation chronology for SJ, and competent timelines clear 80% easily, so C-028 and C-029 are sound. A ranked top-5 list (C-052) is a hidden template feature. Claim-by-claim exposure assessments and next steps (C-053 to C-057) are arguably implicit in 'strategic annotations for summary judgment preparation.' But the 'summary section' placement and the unstated client side make them debatable. |
| Arguable/qualified concerns: item 1 | qualified_check | [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L379) (not_a_defect), [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L387) (arguable) | mixed | C-046 is well grounded. The record has Harborview's Feb 2023 preservation demand, a litigation hold only in March 2024, and Holcomb's vague retention testimony. C-047's PASS accepts 'consciousness of guilt,' but its FAIL requires a 'spoliation or evidentiary integrity' link. An answer that treats the Dec 1 email as a fraudulent cover story or impeachment material, without linking it to evidence integrity, falls between the two conditions. |
| Arguable/qualified concerns: item 2 | arguable | [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L299), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L307), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L315) | not_a_defect | The criteria are hedged: 'contributed to or caused' and 'could have been as high as approximately $9.1M.' The $9.1M arithmetic appears in the Complaint, the Harborview response, the Chakrabarti report, and the Greenleaf-counsel Holcomb summary, which itself says it 'directly undermines Greenleaf's stated basis for termination.' Noting the 3-of-14 and rework-adjustment caveats does not prevent a pass, and flagging a risk to the client's counterclaim is exactly what candid SJ prep does. |
| Arguable/qualified concerns: item 3 | arguable | [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L347), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L355) | not_a_defect | Chakrabarti admits the renewals were one-year terms and pre-emptively rebuts a 'speculative' challenge, so the record itself flags the vulnerability. C-042 accepts 'speculative or unsupported,' which a defense-oriented annotation would naturally say. C-043 accepts SJ, Daubert, or exclusion. Both are reasonable defense analysis, not a hidden advocacy mandate. |
| Arguable/qualified concerns: item 4 | arguable | [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L283), [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L499), [C-064](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/build-litigation-case-timeline/task.json#L523) | not_a_defect | The graded figures are consistent across sources: 14 vs 2 (Chakrabarti, Buckley), 11 of 14 inconsistent and 3 consistent (Buckley), and 14 notices worth $1.4M (Chakrabarti, and the QA log's adjusted total). The spreadsheet's internal inconsistencies, such as sheet2 E25=4 against five listed lots and the lot and denominator mismatches, do not change what these criteria require. |

## Blind pass and what changed

I dropped blind O6, the document_defect on C-064 and C-007. On re-checking, every figure those criteria grade is consistent across sources: the Fong email's four rejected lots, 14 notices, $1.4M, 14 vs 2, and Buckley's 11/3 split. The lot-level and denominator mismatches in the QA log are real but do not change any criterion's correct answer, which matches Sol's qualified item 4. After reviewing Sol, I rejected its C-028 and C-029 finding: source citations and named actors are implicit in a litigation chronology. I also rejected its C-036 to C-038 finding, because the criteria are hedged and the $9.1M arithmetic appears throughout the record, including the Greenleaf-counsel summary. I rejected its C-042 and C-043 finding as well, because Chakrabarti himself anticipates the 'speculative' challenge. I kept C-053 to C-057 as arguable rather than adopting Sol's 'confirmed,' because claim assessment is arguably implicit in SJ-prep annotations. I kept C-047 as arguable, where Sol found no defect. I strengthened O2 with the day count (Dec 14 to Mar 14 is exactly 90 days) and the Complaint ¶49 Dec 15 statement. I could not re-verify the ORS 12.110 primary text because the web fetch was blocked by a spend limit, so that authority stays verified=false.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-045): Discovery-rule criterion assumes the fraud claim needs tolling to be timely; it is timely on its face
- **O2** (problematic; C-009, C-050): Non-renewal deadline fixed at Dec 15, 2022, but the record also gives Dec 14 and the contract arithmetic supports Dec 14
- **O3** (problematic; C-052): Requires a ranked 'top 5 critical issues' summary that the one-line instructions never ask for
- **O4** (arguable; C-053, C-054, C-055, C-056, C-057): Hidden 'summary section' with a claim-by-claim exposure assessment and pre-filing next steps; client side is never stated
- **O5** (arguable; C-047): Requires linking the 'supply chain' cover story specifically to spoliation or evidentiary-integrity concerns
- **O6** (arguable; C-064, C-007): QA rejection records conflict on lot identities, dates, values and denominators

## Coverage and limits

Blind pass: Read all 64 criteria and the instructions (one sentence plus the output filename). Read in full: the EDA, the Notice of Material Breach, the Notice of Termination, the Stanton-to-Ivers email, both internal email threads, the Scheduling Order, and Holcomb deposition summary sections I-VII. Searched the rest by keyword: the Complaint (causes of action, filing date, SOL allegations, damages, direct-sales allegations), the Answer/Counterclaim (Year 1-3 figures, $408K/$792K breakdown, affirmative defenses), the QA log totals, the Buckley report (14 vs 2, 11 of 14, who retained him), the Chakrabarti report (diversion table, 5-year projection, dates, list of depositions), the Fong deposition (privilege exchange), the Harborview response (preservation demand, $5.8M figure), and spoliation facts. Verified the ORS 12.110(1) fraud discovery clause through a public.law fetch, which returned a model summary quoting the clause, not a full primary-text read. Did not read the Fong deposition summary or the Harborview response line by line. Did not run the legal research needed to confirm how Oregon courts count the 90-day non-renewal period.

Reconciliation: Covered all 64 criteria and the instructions. In the blind pass I read the key documents in full: the EDA, the notices, the emails, the scheduling order, and the Holcomb summary. On this pass I re-checked the Dec 14/15 references across the Complaint ¶49, the Chakrabarti report, the Holcomb summary and the Dec 1 email; the $9.1M and $3.3M causation sources; the QA log's adjusted total note and sheet2 E25/J25; Buckley's 11/3 findings; Chakrabarti's five-year rationale; and the Answer's affirmative defenses. I also read Sol's full report and index. The ORS 12.110(1) primary text was not read in this session because the fetch was blocked, so that citation stays unverified. I did not independently recalculate the expert damages models.

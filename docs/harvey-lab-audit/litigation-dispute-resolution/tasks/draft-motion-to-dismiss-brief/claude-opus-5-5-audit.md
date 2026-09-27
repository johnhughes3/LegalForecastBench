# Claude Opus 5.5 audit: Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 89. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

Most of the rubric is accurate against the record, but several criteria can zero out a correct answer under the all-pass metric. The confirmed defects are:
- C-016 states a false fact: the FAC and the operating agreement name Schreiber and Apex.
- The DTPA criteria (C-025, C-026, C-027, C-089) misstate Tex. Bus. & Com. Code §17.49 by merging §17.49(f), §17.49(g) and the §17.45(4) asset test. C-027 also makes a legally irrelevant asset argument mandatory.
- C-084 rewards an acceptance-defeats-warranty argument that the MSLSA's 90-day post-Go-Live warranty contradicts.
- C-054 requires a confidential Arcadia memo, outside the pleadings, in a 12(b)(6) brief.
- C-023 cites Delaware economic-loss 'authorities' taken from the planted memo, one of which is an arbitration case.
The arguable issues are:
- C-022 rewards applying the economic loss rule to fraud, contrary to Formosa.
- Negligent-misrepresentation duty (C-038, C-039) and puffery for quantified claims (C-046).
- Contested causation at the pleading stage (C-041, C-045) and extrinsic-evidence reliance (C-075, C-082).
- The acceptance-window trigger (C-034, C-035) and with-prejudice relief (C-012, C-063).
- The contingent diversity framing (C-013), the conflicting orders on post-answer motions (C-078), and the §12.3 checklist item (C-058).
Sol's audit overlaps substantially with mine. I rejected its C-007, C-008, C-019, C-024, C-030, C-043, C-052, C-053, C-077, C-080 and C-083 as not defects.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | source_conflict | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L145) | C-016 falsely says the record never names Schreiber or Apex Medical Ventures as members of Arcadia | blind |
| [O2](#o2) | problematic | legal_error | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L217), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L225), [C-089](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L729) | The DTPA exemption is misstated: §17.49(f) has no $500K/$25M-asset test; the $500K rule is §17.49(g) and the $25M test is §17.45(4) | blind |
| [O3](#o3) | problematic | legal_error | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233) | C-027 requires an asset argument that is irrelevant to the $500K exemption and draws on figures from outside the pleadings | blind |
| [O4](#o4) | problematic | legal_error | [C-084](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L689) | C-084 rewards arguing deemed acceptance defeats the warranty claim, but the §9.1 warranty runs 90 days from Go-Live and the March 8 notice falls inside it | blind |
| [O5](#o5) | problematic | legal_error | [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L449) | C-054 requires a 12(b)(6) brief to rely on Arcadia's confidential internal memo, which the FAC never references | revised |
| [O6](#o6) | arguable | legal_error | [C-075](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L617), [C-082](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L673) | C-075 and C-082 draw on material outside the pleadings, and C-075 has no outcome for a brief that omits ticket data | revised |
| [O7](#o7) | problematic | legal_error | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L201) | C-023's example Delaware economic-loss authorities are wrong: Kuhn is an arbitration case, and 'Brasby v. Morris Dynamics (Del. 2008)' is a misstated citation | blind |
| [O8](#o8) | arguable | legal_error | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L193) | C-022's 'purely economic loss' rationale would reward applying the economic loss rule to fraudulent inducement, contrary to Formosa | adopted_after_reading_sol |
| [O9](#o9) | arguable | legal_error | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313) | C-037 lists SIGA v. PharmAthene as Delaware parol-evidence authority, but that opinion does not address integration or parol evidence | blind |
| [O10](#o10) | arguable | legal_error | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L321), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L329) | Texas negligent misrepresentation (Restatement §552) needs no fiduciary or special relationship | blind |
| [O11](#o11) | arguable | legal_error | [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L385) | C-046 treats the quantified '30-40% improvement' statement as puffery, contrary to the Fifth Circuit's 'specific and measurable' test | blind |
| [O12](#o12) | arguable | legal_error | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L345), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377) | The causation criteria require a 12(b)(6) brief to adopt the disputed version of a status report the FAC contests | blind |
| [O13](#o13) | arguable | ambiguous_or_unjudgeable | [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L289), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L297) | The deemed-acceptance window runs from a Deployment Notice under §5.3, not from Go-Live, and the record has no Deployment Notice date | blind |
| [O14](#o14) | arguable | internal_inconsistency | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L112), [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L521) | Criteria disagree on relief: C-012 and C-063 require every count dismissed with prejudice, while C-076 and C-079 accept partial relief | blind |
| [O15](#o15) | arguable | legal_error | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L120) | The diversity defect is framed as contingent on Delaware overlap, though the notice of removal itself shows shared Texas citizenship | blind |
| [O16](#o16) | arguable | document_defect | [C-078](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L641) | The standing order and scheduling order conflict on whether a post-answer motion is treated as 12(b)(6) or 12(c) | revised |
| [O17](#o17) | arguable | unrequested_requirement | [C-058](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L481) | C-058 requires the no-oral-modification clause for pre-contract statements, but §12.3 governs post-formation amendments | blind |

<a id="o1"></a>
### O1. C-016 falsely says the record never names Schreiber or Apex Medical Ventures as members of Arcadia

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L145)

C-016 says: 'The documents do not mention members named Schreiber or Apex Medical Ventures, LP.' That is false. FAC ¶7, the operating-agreement member schedule and research memo §XV all name exactly these members, and they settle citizenship. Apex's general partner is a Delaware corporation, which makes Arcadia a Delaware citizen. Okonkwo and Schreiber make it a Texas citizen. The judge sees only the deliverable and the criterion, so the false sentence is the only 'fact' the judge has. A correct memo that traces citizenship through Schreiber and Apex may be marked down as inventing members, while a vaguer memo that names no one passes.

Evidence:
- `task.json C-016`: “The documents do not mention members named Schreiber or Apex Medical Ventures, LP.”
- `first-amended-complaint.docx.txt`: “Arcadia's operating agreement identifies three members: (a) Dr. Rachel Okonkwo ... (b) Martin Schreiber ... and (c) Apex Medical Ventures, LP, a Delaware limited partnership.”
- `arcadia-operating-agreement-relevant-excerpts.docx.txt`: “General Partner: Apex Medical Ventures GP, Inc., a Delaware corporation”

Suggested fix: Delete the false sentence. Instead require the memo to trace citizenship through Okonkwo (TX), Schreiber (TX) and Apex LP (Delaware GP; Texas trust partner), as FAC ¶¶7–8 and the operating agreement show.

Related GPT-6 Sol findings: F2.

<a id="o2"></a>
### O2. The DTPA exemption is misstated: §17.49(f) has no $500K/$25M-asset test; the $500K rule is §17.49(g) and the $25M test is §17.45(4)

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L217), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L225), [C-089](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L729)

C-025 requires arguing a '§ 17.49(f) exemption for transactions exceeding $500,000 where the claiming party has assets of $25 million or more.' No such provision exists. §17.49(f) covers written contracts over $100K where the consumer had independent counsel; Wexford Hale negotiated the MSLSA, so that exemption is met. §17.49(g) covers transactions over $500K and has no asset condition. The $25M test appears only in the §17.45(4) definition of 'consumer.' C-026 puts the $500K threshold 'under § 17.49(f).' C-089 adds a non-existent 'not an individual' condition. The Answer, both DTPA letters and the research memo repeat the conflation. A brief that copies the Answer matches the rubric, while one that states the statute correctly contradicts the criterion's description and risks failing.

Evidence:
- `task.json C-025`: “§ 17.49(f) exemption for transactions exceeding $500,000 where the claiming party has assets of $25 million or more”
- `task.json C-089`: “§ 17.49(f) exemption for transactions exceeding $500,000 where the consumer is not an individual”
- `meridians-answer-to-first-amended-complaint.docx.txt`: “involving total consideration by the consumer of more than \$500,000, where the consumer has assets of \$25 million or more”

Authorities (✓ = primary text checked in the auditing session):
- Tex. Bus. & Com. Code § 17.49(f) (✓): Exempts claims arising from a written contract over $100,000 where the consumer was represented by independent legal counsel (non-residence).
- Tex. Bus. & Com. Code § 17.49(g) (✓): Exempts transactions with total consideration over $500,000 (non-residence); there is no asset condition.
- Tex. Bus. & Com. Code § 17.45(4) (✓): 'Consumer' excludes a business consumer with assets of $25 million or more.

Suggested fix: Accept §17.49(g) (over $500K) and/or §17.49(f) (over $100K plus counsel) as independent bars, and place the $25M test under §17.45(4).

Related GPT-6 Sol findings: F1.

<a id="o3"></a>
### O3. C-027 requires an asset argument that is irrelevant to the $500K exemption and draws on figures from outside the pleadings

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233)

C-027 fails any brief that does not use the FAC's '$30 million infrastructure investments' or the $23.8M figure 'to support the § 17.49(f) argument.' Assets are irrelevant to both real exemptions: (g) turns only on consideration and (f) on counsel. They matter only under §17.45(4). Money spent on infrastructure (FAC ¶83, which includes hiring and training) is not a measure of balance-sheet assets, and on a 12(b)(6) motion inferences run in the plaintiff's favour. The $23.8M figure comes from a pre-suit letter outside the pleadings, and Arcadia's damages report puts total assets at about $41M. A competent brief would win Count V on (g)/(f) and skip the disputed asset question, and it would fail this criterion.

Evidence:
- `task.json C-027`: “FAIL if neither the FAC's $30 million allegation nor the inconsistency with the $23.8 million figure is used to support the § 17.49(f) argument.”
- `arcadias-damages-report-executive-summary.docx.txt`: “Arcadia's total assets as of its most recent audited financial statements are approximately \$41 million”

Authorities (✓ = primary text checked in the auditing session):
- Tex. Bus. & Com. Code §§ 17.45(4), 17.49(f)-(g) (✓): The asset threshold appears only in the consumer definition, not in the transaction exemptions.

Suggested fix: Make this an optional alternative argument under §17.45(4), or drop it.

Related GPT-6 Sol findings: F1, F7.

<a id="o4"></a>
### O4. C-084 rewards arguing deemed acceptance defeats the warranty claim, but the §9.1 warranty runs 90 days from Go-Live and the March 8 notice falls inside it

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-084](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L689)

C-084 requires arguing that deemed acceptance under §5.3 means Arcadia 'acknowledged the software performed substantially in accordance with documentation, undermining any warranty breach claim.' Under the MSLSA, the §9.1 warranty covers performance for 90 days after Go-Live (January 15 to April 15, 2023), which outlasts any acceptance period. Arcadia's March 8 written notice falls within that period, as Meridian's own ticket report and DTPA response concede. Acceptance therefore does not undercut a timely warranty claim; at most §9.1(b) channels the claim to repair or refund. A careful brief that keeps the two provisions separate fails, and a brief making the contractually wrong argument passes.

Evidence:
- `task.json C-084`: “arguing that deemed acceptance means Arcadia acknowledged the software performed substantially in accordance with documentation, undermining any warranty breach claim”
- `master-software-license-and-services-agreement.docx.txt`: “for a period of ninety (90) days following the Go-Live Date (the "**Warranty Period**"), the Licensed Software will perform substantially in accordance with the Documentation”
- `support-ticket-summary-report.docx.txt`: “The Section 9.1 limited warranty period ran from Go-Live (January 15, 2023) through April 15, 2023.”

Suggested fix: Delete this criterion, or accept an argument that §9.1(b) limits warranty remedies to repair/replace or a pro-rata refund.

<a id="o5"></a>
### O5. C-054 requires a 12(b)(6) brief to rely on Arcadia's confidential internal memo, which the FAC never references

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L449)

Standing order §3.4 bars matters outside the pleadings. It allows only documents attached to the complaint, documents referenced in it and central to the claims, and judicially noticeable matter. The Schreiber memo is an internal Arcadia document marked 'CONFIDENTIAL.' The FAC does not reference it: ¶31 mentions Schreiber's reference calls, not a memo. Citing it risks conversion to summary judgment. A competent practitioner would keep it for the cover memo or for summary judgment. C-054's FAIL condition ('if the Schreiber memo is not cited') fails exactly that brief.

Evidence:
- `judge-alvarezs-standing-order-on-motion-practice.docx.txt`: “(ii) documents attached to the motion to dismiss that are referenced in the complaint and central to the plaintiff's claims”
- `martin-schreiber-internal-memo.docx.txt`: “ARCADIA HEALTH SYSTEMS, LLC** **INTERNAL MEMORANDUM --- CONFIDENTIAL”
- `task.json C-054`: “FAIL if the Schreiber memo is not cited.”

Suggested fix: Allow the memo in the cover memo, or credit a brief that flags the conversion risk or relies on the FAC's own due-diligence allegations.

Related GPT-6 Sol findings: F6.

<a id="o6"></a>
### O6. C-075 and C-082 draw on material outside the pleadings, and C-075 has no outcome for a brief that omits ticket data

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-075](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L617), [C-082](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L673)

C-082 requires the Meridian-produced negotiation email chain, cited by Bates range. FAC ¶32 pleads the same negotiation facts, so a brief citing ¶32 may still pass under the 'negotiation history is not cited' FAIL condition, but a literal judge may demand the emails. C-075 rewards ticket figures from a report 'prepared at the request of outside litigation counsel.' A disciplined 12(b)(6) brief might omit those figures. C-075's PASS condition requires citing them, while its FAIL condition covers only misstatement, so a brief that omits them falls between the two conditions.

Evidence:
- `support-ticket-summary-report.docx.txt`: “This report has been prepared at the request of outside litigation counsel, Stonebridge & Calloway LLP”
- `first-amended-complaint.docx.txt`: “Arcadia engaged outside counsel to assist in the negotiation process. Despite Arcadia's efforts to negotiate more favorable terms”
- `task.json C-075`: “FAIL if the ticket data is cited but materially misstated.”

Suggested fix: Accept FAC ¶32 for negotiation history. Make C-075 pass (or not apply) when ticket data is not cited.

Related GPT-6 Sol findings: F6.

<a id="o7"></a>
### O7. C-023's example Delaware economic-loss authorities are wrong: Kuhn is an arbitration case, and 'Brasby v. Morris Dynamics (Del. 2008)' is a misstated citation

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L201)

C-023 offers 'Brasby v. Morris Dynamics or Kuhn Construction v. Diamond State Port Corp.' as Delaware economic-loss authority. Both come from the seeded research memo. Kuhn, 990 A.2d 393 (Del. 2010), decides whether a referee clause compels arbitration and never mentions economic loss. The real Brasby is Brasby v. Morris, an unpublished 2007 Superior Court opinion. The judge treats the examples as correct, so the criterion rewards briefs that repeat the miscitations. Its 'more robust/defendant-friendly' framing also skips over the fact that Delaware applies the doctrine mainly to negligence-type claims, not intentional fraud.

Evidence:
- `task.json C-023`: “citing relevant authority such as Brasby v. Morris Dynamics or Kuhn Construction v. Diamond State Port Corp.”

Authorities (✓ = primary text checked in the auditing session):
- Kuhn Construction, Inc. v. Diamond State Port Corp., 990 A.2d 393 (Del. 2010) (✓): Decides whether a referee clause requires arbitration; does not address the economic loss doctrine.
- Brasby v. Morris, 2007 WL 949485 (Del. Super. Mar. 29, 2007) (unverified): Delaware Superior Court opinion applying the economic loss doctrine.

Suggested fix: Remove Kuhn, correct the Brasby citation, and tell the judge not to credit authorities cited for propositions they do not support.

<a id="o8"></a>
### O8. C-022's 'purely economic loss' rationale would reward applying the economic loss rule to fraudulent inducement, contrary to Formosa

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L193)

C-022 passes a brief arguing that the economic loss rule bars Count II (fraud) because 'all alleged damages are purely economic losses arising from the contractual relationship.' Under Texas law, which the FAC pleads for the tort counts, Formosa holds the opposite: fraud-in-the-inducement tort damages are recoverable even when the loss is purely economic and relates to the contract's subject matter. The 'and/or' lets a correct brief aim the rule only at Count III, so correct work is not failed. But the criterion rewards the wrong argument, and a brief that drops the doctrine altogether in favour of stronger grounds fails.

Evidence:
- `task.json C-022`: “bars Counts II (Fraud) and/or III (Negligent Misrepresentation) because all alleged damages are purely economic losses arising from the contractual relationship”

Authorities (✓ = primary text checked in the auditing session):
- Formosa Plastics Corp. USA v. Presidio Eng'rs & Contractors, Inc., 960 S.W.2d 41, 47 (Tex. 1998) (✓): 'tort damages are recoverable for a fraudulent inducement claim irrespective of whether ... the plaintiff only suffers an economic loss related to the subject matter of the contract.'

Suggested fix: Limit C-022 to Count III, or require that any Texas-law application to fraud acknowledge Formosa.

Related GPT-6 Sol findings: F5.

<a id="o9"></a>
### O9. C-037 lists SIGA v. PharmAthene as Delaware parol-evidence authority, but that opinion does not address integration or parol evidence

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313)

C-037 names SIGA, 67 A.3d 330 (Del. 2013), as Delaware authority on parol evidence and integration clauses. A full-text search finds no occurrence of 'integration' or 'parol'; the case concerns bad-faith negotiation, promissory estoppel and damages. Eagle Industries is a proper alternative, so a correct brief passes. But a brief citing only SIGA, as the memo does, is rewarded.

Evidence:
- `task.json C-037`: “such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care”

Authorities (✓ = primary text checked in the auditing session):
- SIGA Techs., Inc. v. PharmAthene, Inc., 67 A.3d 330 (Del. 2013) (✓): Contains no discussion of integration clauses or the parol evidence rule.

Suggested fix: Drop SIGA from the example list.

<a id="o10"></a>
### O10. Texas negligent misrepresentation (Restatement §552) needs no fiduciary or special relationship

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L321), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L329)

C-039 requires arguing that no fiduciary or special relationship existed. C-038 says that in arm's-length deals between sophisticated parties 'no such duty exists.' Under Texas §552 law, the duty arises from supplying information in the course of business for the guidance of others. McCamish describes that duty as independent of privity, and it does not require a special relationship. The stronger Texas grounds are promissory statements, benefit-of-bargain damages (Sloane) and the anti-reliance clause. A brief that correctly omits the special-relationship argument under Texas law fails C-039.

Evidence:
- `task.json C-039`: “PASS if the motion brief argues that no fiduciary or special relationship existed between Meridian and Arcadia”
- `task.json C-038`: “in arm's-length commercial transactions between sophisticated parties, no such duty exists”

Authorities (✓ = primary text checked in the auditing session):
- McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests, 991 S.W.2d 787 (Tex. 1999) (✓): Negligent-misrepresentation liability rests on an independent duty arising from awareness of reliance, not on privity or a special relationship.

Suggested fix: Accept any sound Count III ground, and make the special-relationship argument optional or Delaware-specific.

Related GPT-6 Sol findings: F7.

<a id="o11"></a>
### O11. C-046 treats the quantified '30-40% improvement' statement as puffery, contrary to the Fifth Circuit's 'specific and measurable' test

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L385)

'Industry-leading' is classic puffery. 'Our clients typically see 30-40% improvement' is a quantified statement about other clients' results that can be proved false. Pizza Hut treats specific, measurable claims as actionable statements of fact. A careful brief would call only the general statements puffery and attack the 30–40% claim through the 'typically' qualifier, the proposal's disclaimer and the anti-reliance clause. A judge reading C-046 literally may fail that brief.

Evidence:
- `task.json C-046`: “argues that statements like 'industry-leading performance' and 'Our clients typically see 30-40% improvement in reporting efficiency' are non-actionable puffery”

Authorities (✓ = primary text checked in the auditing session):
- Pizza Hut, Inc. v. Papa John's Int'l, Inc., 227 F.3d 489 (5th Cir. 2000) (✓): An actionable statement is a 'specific and measurable claim, capable of being proved false.'

Suggested fix: Pass a brief that argues puffery for the general statements and non-reliance or non-actionability for the quantified one.

Related GPT-6 Sol findings: F7.

<a id="o12"></a>
### O12. The causation criteria require a 12(b)(6) brief to adopt the disputed version of a status report the FAC contests

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L345), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377)

C-045 requires the brief to attribute the Go-Live delay to Arcadia's 45-day project-manager gap and its late API specifications. Those facts come from Meridian's August 2022 status report, which the FAC expressly disputes (¶44). A referenced document can be considered but not taken as true over the complaint's contrary allegations, and proximate cause is ordinarily a fact question. C-041 frames the point as a failure to plead proximate cause, which is weak at the pleading stage. The contractual points are better grounded and sound: SOW-1 §3.2 and CO-004 §5.1, which is Arcadia's own acknowledgment. A brief that leaves the delay-causation facts to the cover memo fails C-045.

Evidence:
- `first-amended-complaint.docx.txt`: “The report identified various purported causes for the delay but failed to acknowledge Meridian's own responsibility”
- `task.json C-045`: “FAIL if Arcadia's own contributory delays are not mentioned.”

Suggested fix: Allow the delay facts in either deliverable, and frame C-041 around the SOW-1 §3.2 and CO-004 allocation.

Related GPT-6 Sol findings: F6.

<a id="o13"></a>
### O13. The deemed-acceptance window runs from a Deployment Notice under §5.3, not from Go-Live, and the record has no Deployment Notice date

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L289), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L297)

Under §5.3(a), the 30-day window starts when Meridian delivers a 'Deployment Notice,' after staging testing under §5.2. §5.3(d) separately treats production use as acceptance. No Deployment Notice date appears in the record; the Go-Live keying comes from Meridian's litigation report. A brief that keys the window to the contractual trigger, or relies on production-use acceptance, would be graded against dates the contract does not fix.

Evidence:
- `master-software-license-and-services-agreement.docx.txt`: “Following Licensor's delivery of a Deployment Notice with respect to each module or Deliverable, Licensee shall have thirty (30) calendar days”
- `task.json C-035`: “the acceptance window end as approximately February 14, 2023 (30 days later)”

Suggested fix: Also accept analysis keyed to the Deployment Notice or production-use acceptance.

<a id="o14"></a>
### O14. Criteria disagree on relief: C-012 and C-063 require every count dismissed with prejudice, while C-076 and C-079 accept partial relief

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L112), [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L521)

C-012 fails a brief that does not seek dismissal of 'all five counts with prejudice,' and C-063 requires the proposed order to match. C-076 accepts with-prejudice dismissal 'at minimum' for the barred counts, and C-079 contemplates 'narrowing' Count I. 9(b) particularity dismissals are commonly without prejudice with leave to amend. A calibrated brief that seeks with-prejudice dismissal of Counts IV and V and alternative relief on Count II satisfies C-076 but fails C-012 and C-063.

Evidence:
- `task.json C-012`: “FAIL if no conclusion/prayer is present or if it does not request dismissal with prejudice.”
- `task.json C-076`: “or at minimum for the counts where dismissal with prejudice is appropriate, such as unjust enrichment and DTPA”

Suggested fix: Align C-012 and C-063 with C-076.

Related GPT-6 Sol findings: F8.

<a id="o15"></a>
### O15. The diversity defect is framed as contingent on Delaware overlap, though the notice of removal itself shows shared Texas citizenship

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L120)

C-013 frames diversity as something that 'may be lacking' and turns on whether a member 'shares citizenship with Meridian in Delaware.' The Notice itself alleges Meridian is a citizen of 'both Delaware and Texas' (¶11) and Arcadia 'a citizen of the State of Texas' (¶14). That alone defeats complete diversity, and the member schedule adds overlap in both states. A memo that calls diversity definitively absent on the Texas overlap may be marked down by a literal judge for not tracking the Delaware-contingent theory.

Evidence:
- `notice-of-removal.docx.txt`: “Defendant Meridian Cloud Solutions, Inc. is therefore a citizen of both Delaware and Texas for diversity jurisdiction purposes.”
- `task.json C-013`: “The memo should note that if any member of Arcadia shares citizenship with Meridian in Delaware, complete diversity would be destroyed.”

Suggested fix: Pass a memo that identifies shared Texas and/or Delaware citizenship traced through Arcadia's members.

Related GPT-6 Sol findings: F2.

<a id="o16"></a>
### O16. The standing order and scheduling order conflict on whether a post-answer motion is treated as 12(b)(6) or 12(c)

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-078](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L641)

Standing order §3.4 treats a post-answer motion as 12(b)(6), 'not as a motion for judgment on the pleadings under Rule 12(c).' The scheduling order says the Court 'will treat any such motion as a Rule 12(c) motion.' Rule 12(b)'s timing requirement supports the scheduling order. C-078 anchors propriety to the standing order, so a brief that relies on the scheduling order or on Rule 12(h)(2)/(c) may be graded unevenly. The impact is low because both orders apply the same standard. C-077 is not affected, since the instructions ask for a Rule 12(b)(6) motion.

Evidence:
- `judge-alvarezs-standing-order-on-motion-practice.docx.txt`: “the Court shall treat such motion as a motion to dismiss, not as a motion for judgment on the pleadings under Rule 12(c)”
- `scheduling-order.docx.txt`: “The Court will treat any such motion as a Rule 12(c) motion for judgment on the pleadings, evaluated under the same standard”

Suggested fix: Pass C-078 when the brief addresses post-answer propriety under either order or under Rule 12(c)/(h)(2).

Related GPT-6 Sol findings: F3.

<a id="o17"></a>
### O17. C-058 requires the no-oral-modification clause for pre-contract statements, but §12.3 governs post-formation amendments

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-058](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L481)

§12.3 governs later amendments. Pre-signing statements are handled by §12.1's integration and express anti-reliance language. A disciplined brief under the 25-page limit could rely on §12.1 alone and fail this hidden checklist item. The stakes are low.

Evidence:
- `master-software-license-and-services-agreement.docx.txt`: “This Agreement may not be amended, modified, or supplemented except by a written instrument duly executed”
- `task.json C-058`: “FAIL if Section 12.3 is not cited.”

Suggested fix: Make §12.3 optional, or accept reliance on §12.1.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L217) (problematic), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L225) (problematic), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233) (problematic), [C-083](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L681) (not_a_defect), [C-089](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L729) (problematic) | mixed | I read the statute. §17.49(f) is the >$100K written-contract exemption, which requires independent counsel. §17.49(g) is the >$500K exemption and has no asset test. The $25M test sits in §17.45(4). C-025, C-026 and C-089 each state wrong law about (f). C-027 ties an asset argument to an exemption that has no asset element. C-083 only demands an extra non-exemption DTPA argument, such as puffery or producing cause. That demand is sound, and the (f) label does not change pass/fail for a competent brief. |
| F2 | confirmed | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L120) (arguable), [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L145) (problematic), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L153) (not_a_defect) | mixed | C-016 is false: FAC ¶7 and the operating agreement name Schreiber and Apex. C-013 is arguable. It frames diversity as contingent and turning on Delaware, but Notice ¶¶11 and 14 already allege that both parties are Texas citizens. C-017 accurately describes the Notice (¶¶12-14 identify Arcadia only as a Texas LLC with Okonkwo as managing member), and it passes on 'notes or implies'. A competent memo satisfies it. |
| F3 | confirmed | [C-077](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L633) (not_a_defect), [C-078](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L641) (arguable) | mixed | The instructions expressly ask for 'a Rule 12(b)(6) motion', so C-077 cannot misgrade. Standing order §3.4 says post-answer motions are 12(b)(6), not 12(c). The scheduling order says it will treat them as 12(c). C-078 ties propriety to the standing order, so a brief that follows the scheduling order or Rule 12(h)(2)/(c) could be graded unevenly. The impact is low because both orders apply the same standard. |
| F4 | arguable | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L169) | not_a_defect | The FAC names Poletti as present (¶¶22, 24, 78), but every quoted statement is attributed to 'Meridian's sales team' (¶¶23, 25, 28, 79). C-019 asks the brief to argue that statements are attributed generically rather than to specific speakers. That is an accurate and standard 9(b) argument, and a brief can make it while acknowledging Poletti's presence. |
| F5 | confirmed | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L193) (arguable), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L209) (not_a_defect), [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L433) (not_a_defect) | mixed | I read Formosa (960 S.W.2d at 47): fraud-in-the-inducement tort damages are recoverable 'irrespective of whether ... the plaintiff only suffers an economic loss.' C-022's 'and/or' lets a correct brief aim the rule only at Count III, but it also rewards the wrong argument that the rule bars fraud. C-024 only requires Texas economic-loss analysis, which a brief can do accurately, including by noting Formosa. C-052 is a general 'where relevant' alternative-law requirement and is not defective. |
| F6 | arguable | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L345) (arguable), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L361) (not_a_defect), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377) (arguable), [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L449) (problematic), [C-075](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L617) (arguable), [C-082](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L673) (arguable) | mixed | CO-004 is a signed contract document the FAC references (Exhibit C, ¶47(d)), and its §5.1 contains Arcadia's own acknowledgment about Linden Park, so C-043 is proper. C-054 requires an internal Arcadia memo the FAC never references, which a 12(b)(6) brief should not rely on. C-045 and C-041 require adopting disputed status-report causation. C-075 relies on a counsel-commissioned report and is unclear when tickets are omitted. The negotiation facts in C-082 are partly pleaded (FAC ¶32), so it is arguable rather than fatal. |
| F7 | arguable | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233) (problematic), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L321) (arguable), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L329) (arguable), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L385) (arguable), [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L441) (not_a_defect), [C-080](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L657) (not_a_defect) | mixed | C-027 is worse than arguable. Assets are legally irrelevant to §17.49(f)/(g), and spending is not assets. The §552 duty in C-038 and C-039 does not require a special relationship under Texas law. The quantified 30–40% claim in C-046 is arguably verifiable fact under Pizza Hut. C-053 and C-080 ask for a reliance challenge. Because MSLSA §12.1 is an express anti-reliance clause, that is a strong standard defense argument, and the listed factors are illustrative. |
| F8 | arguable | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L112) (arguable), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L257) (not_a_defect), [C-063](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L521) (arguable), [C-076](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L625) (not_a_defect) | mixed | C-012 and C-063 require with-prejudice dismissal of every count. 9(b) dismissals are often without prejudice, and C-076 itself accepts partial with-prejudice relief. C-030 only asks the brief to argue that the express contract precludes unjust enrichment. FAC ¶99 pleads unjust enrichment in the alternative while suing on the admittedly valid MSLSA, so this is standard defense advocacy (Fortune Production) and does not misgrade competent work. C-076 is the permissive standard. |
| F9 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L72), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L80) | not_a_defect | Standing order §3.2 excludes 'table of contents, table of authorities' from the 25-page limit, which assumes they exist. A formal federal motion brief of this kind customarily includes both. They are standard components of the named document, not hidden requirements. |

## Blind pass and what changed

1. Split blind O5. C-054 stays problematic (O5). C-075 and C-082 drop to arguable (O6), because FAC ¶32 pleads the negotiation history and C-082's FAIL condition turns on 'negotiation history' being cited at all.
2. Adopted from Sol F5 (C-022 only), as arguable O8. After reading Formosa (960 S.W.2d at 47), I agree C-022 rewards applying the economic loss rule to fraud based on 'purely economic' loss. I rejected Sol's C-024 and C-052.
3. Dropped C-077 from the post-answer finding (now O16). The instructions expressly request a Rule 12(b)(6) motion, so C-077 cannot misgrade.
4. Dropped C-040 from the negligent-misrepresentation finding (now O10). Any Texas negligent-misrepresentation authority passes it.
5. Dropped C-076 and C-079 as flagged criteria in the relief finding (now O14). They are the permissive benchmark, not the defect.
6. C-017 stays unflagged. The Notice ¶¶12–14 does identify Arcadia only through Okonkwo.
7. Rejected these Sol items after checking the record:
   - C-019: every quoted statement is attributed to the 'sales team', not to Poletti.
   - C-043: CO-004 §5.1 is Arcadia's own signed acknowledgment in a referenced document.
   - C-030: an unjust-enrichment claim pleaded in the alternative alongside an admitted valid contract is standard defense advocacy.
   - C-053 and C-080: §12.1 is an express anti-reliance clause, and the listed factors are illustrative.
   - C-083: its substantive demand for an extra non-exemption DTPA ground is sound.
   - C-007 and C-008: the standing order's page-limit carve-out presupposes a table of contents and a table of authorities.
8. Renumbered findings O1–O17.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-016): C-016 falsely says the record never names Schreiber or Apex Medical Ventures as members of Arcadia
- **O2** (problematic; C-025, C-026, C-089): The DTPA exemption is misstated: §17.49(f) has no $500K/$25M-asset test; the $500K rule is §17.49(g) and the $25M test is §17.45(4)
- **O3** (problematic; C-027): C-027 requires an asset argument that is irrelevant to the $500K exemption and draws on figures from outside the pleadings
- **O4** (problematic; C-084): C-084 rewards arguing deemed acceptance defeats the warranty claim, but the §9.1 warranty runs 90 days from Go-Live and the March 8 notice falls inside it
- **O5** (problematic; C-054, C-075, C-082): The rubric requires a 12(b)(6) brief to rely on discovery documents outside the pleadings, contrary to Rule 12(d) and the standing order
- **O6** (problematic; C-023): C-023's example Delaware economic-loss authorities are wrong: Kuhn is an arbitration case, and 'Brasby v. Morris Dynamics (Del. 2008)' is a misstated citation
- **O7** (arguable; C-037): C-037 lists SIGA v. PharmAthene as Delaware parol-evidence authority, but that opinion does not address integration or parol evidence
- **O8** (arguable; C-038, C-039, C-040): Texas negligent misrepresentation (Restatement §552) needs no fiduciary or special relationship, and McCamish cuts against the rubric's duty theory
- **O9** (arguable; C-046): C-046 treats the quantified '30-40% improvement' statement as puffery, contrary to the Fifth Circuit's 'specific and measurable' test
- **O10** (arguable; C-041, C-045): The causation criteria require a 12(b)(6) brief to adopt the disputed version of a status report the FAC contests
- **O11** (arguable; C-034, C-035): The deemed-acceptance window runs from a Deployment Notice under §5.3, not from Go-Live, and the record has no Deployment Notice date
- **O12** (arguable; C-012, C-063, C-076, C-079): Criteria disagree on relief: C-012/C-063 require every count dismissed with prejudice, while C-076 and C-079 accept partial relief
- **O13** (arguable; C-013, C-017): The diversity defect is framed as contingent on Delaware overlap, though the notice of removal itself shows shared Texas citizenship
- **O14** (arguable; C-077, C-078): The standing order and scheduling order conflict on whether a post-answer motion is treated as 12(b)(6) or 12(c)
- **O15** (arguable; C-058): C-058 requires the no-oral-modification clause for pre-contract statements, but §12.3 governs post-formation amendments

## Coverage and limits

Blind pass: I read all 89 criteria, the instructions, the judge prompt (rubric_criterion.txt) and the solver system prompt. Read in full: the First Amended Complaint, Judge Alvarez's standing order, the notice of removal, the scheduling order, the March 8, 2023 Okonkwo email, and the key sections of the support-ticket report (summary, SLA, defects, conclusions). Read by targeted section: MSLSA §§5.3, 6.1–6.2, 8.1–8.5, 9.1, 9.4, 12.1, 12.3 and 12.7; and the research memo (outline, DTPA, jurisdiction note). Searched with grep only: operating agreement excerpts (member schedule read), Answer, DTPA letters, damages report, status report, SOW-1, change orders, proposal (disclaimer), Schreiber memo (opening and quote), and the negotiation emails (header and first email). Not read: the sales presentation slides. Law checked: I read the official text of Tex. Bus. & Com. Code §§17.45(4) and 17.49 (tcss.legis.texas.gov). On CourtListener I read Chapman Custom Homes and Kuhn Construction v. Diamond State Port, and ran text searches of SIGA v. PharmAthene (67 A.3d 330), McCamish and Pizza Hut. I saw Brasby v. Morris only as cited in later Delaware Superior Court opinions. Not verified: Formosa Plastics, Eagle Industries, Sloane, Sharyland (seen only as quoted in Chapman), and the Fifth Circuit post-answer 12(c) case law. Minor record defects that change no correct answer: the Answer's paragraph numbers do not track the FAC's, and exhibit letters differ between documents (FAC Exhibit D is the status report; the email chain is also labelled "Exhibit D").

Reconciliation: Read all 89 criteria, the instructions, the judge prompt and the solver prompt, plus Sol's index entry and full report. In the blind pass I read the FAC, standing order, notice of removal, scheduling order and March 8 email in full, and read key sections of the MSLSA, ticket report and research memo. This pass re-checked: FAC speaker attribution (¶¶22–28, 78–84), FAC ¶¶32, 46–47 and 99, Notice ¶¶9–14, standing order §3.2 table-of-contents and table-of-authorities language, and CO-004 §§1.2–1.3 and 5.1. I also grepped Linden Park across all documents. Law verified this session: Tex. Bus. & Com. Code §§17.45(4) and 17.49(f)-(g) (blind pass), Formosa Plastics 960 S.W.2d 41 (text search on CourtListener), and Kuhn, SIGA, McCamish, Pizza Hut and Chapman (blind pass). Not verified: Sloane, Sharyland, Eagle Industries, Brasby (seen only as cited), and Fortune Production. The sales presentation slides were not read.

# Claude Opus 5.5 audit: Draft Motion for Summary Judgment — Breach of Contract, Fraudulent Inducement, and Negligent Misrepresentation in Failed ERP Implementation

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 69. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric mostly tracks the Ridgeline record accurately: the caption, damages arithmetic, termination sequence, and evidence citations all check out. Its central legal defect is C-008 and C-009. They require arguing that fraud claims survive MSA §14.1, but under Pennsylvania law (SodexoMAGIC, Yocca) §14.1 is a fraud-insulating clause that supersedes prior representations and disclaims reliance on them. A candid, correct brief could therefore fail the all-pass metric on those two criteria alone. The record is badly contaminated: 11 of 17 files come from an unrelated N.D. Ill. employment case, and no Ridgeline pleadings are supplied, which also explains the 'Local Rule 56.1' mislabel. Several other criteria are arguable because they make strategic choices mandatory (counterclaim, punitive damages, the 12-month statement) or import weak work-product premises (the cap 'silent' on consequential damages, the 'partly' causation qualifier). Sol's core findings on contamination and the non-reliance clause match mine. I reject Sol's findings on the caption criteria, on C-014, and on C-026.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L77), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L85) | Rubric requires arguing fraud claims survive §14.1, but that clause is a PA fraud-insulating non-reliance clause | revised |
| [O2](#o2) | problematic | document_defect | — | 11 of 17 supplied documents are from unrelated Huang v. Whitaker (N.D. Ill.); no Ridgeline pleadings supplied | blind |
| [O3](#o3) | arguable | legal_error | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L205) | Reliance criterion targets the minor reference-check issue and ignores the §14.1 non-reliance clause | revised |
| [O4](#o4) | arguable | legal_error | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L141) | Example authorities for 'LOL clauses unenforceable as to fraud' are inapposite; Werwinski is adverse | blind |
| [O5](#o5) | arguable | internal_inconsistency | [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L349), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L309) | Rubric treats contract damages as direct-only, though §11.2 caps all theories and the rubric claims consequential damages | revised |
| [O6](#o6) | arguable | unsupported_fact | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L229) | C-027 keys on a 'partly' qualifier that appears nowhere in the record | blind |
| [O7](#o7) | arguable | unrequested_requirement | [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L61), [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L69), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L237), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L245) | Counterclaim coverage is mandatory although neither the instructions nor any supplied pleading mention it | revised |
| [O8](#o8) | arguable | internal_inconsistency | [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L453) | 'Local Rule 56.1' is not the W.D. Pa. rule; W.D. Pa. uses a LCvR 56(B)(1) Concise Statement | blind |
| [O9](#o9) | arguable | unrequested_requirement | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L269), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L277) | Punitive damages are mandatory in a plaintiff's MSJ; C-033 assumes a jury despite the MSA's jury waiver | blind |
| [O10](#o10) | arguable | unrequested_requirement | [C-068](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L557) | Requires citing the proposal's '12-month go-live' confidence statement, a forward-looking prediction | blind |
| [O11](#o11) | arguable | document_defect | [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L93), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L109), [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L501) | Witness names and facts are inconsistent across the Ridgeline documents | blind |

<a id="o1"></a>
### O1. Rubric requires arguing fraud claims survive §14.1, but that clause is a PA fraud-insulating non-reliance clause

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L77), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L85)

C-008 requires arguing that the integration clause 'does not bar' the fraud claims. C-009 requires arguing that such claims 'can survive an integration clause', and it fails a brief that says the clause bars them. Pennsylvania draws a line here. Under SodexoMAGIC, reading Yocca and HCB, a bare integration clause does not bar fraudulent-inducement proof, but a clause that supersedes or disclaims prior representations does. MSA §14.1 supersedes all prior 'representations' and adds an express non-reliance acknowledgment. The MSA recitals also cover Apex's experience. A candid brief that concedes the parol-evidence and reliance bar and relies on the §5.1 warranties would fail C-008 and C-009. An overbroad 'Toy says fraud survives' argument would pass. The 'gist of the action' route in C-009 does not answer the integration question at all, and eToll applied that doctrine against the fraud plaintiff. Under all-pass scoring, this alone can zero a correct answer.

Evidence:
- `master-services-agreement.docx.txt`: “supersedes all prior negotiations, representations, warranties, commitments, offers, and agreements, whether written or oral. Each Party acknowledges that it has not relied upon any statement, representation, promise, or agreement not expressly set forth in this Agreement”
- `C-009`: “FAIL if the motion does not articulate this legal principle or misstates it by claiming integration clauses bar all fraud claims under Pennsylvania law.”
- `C-008`: “preemptively argues why the integration clause does not bar those claims”
- `master-services-agreement.docx.txt`: “Apex represents that it is an experienced ERP implementation services provider ... possesses the requisite skill, experience, personnel, and technical expertise”

Authorities (✓ = primary text checked in the auditing session):
- SodexoMAGIC, LLC v. Drexel Univ., 24 F.4th 183 (3d Cir. 2022) (✓): Under PA law, the parol evidence rule does not bar a fraudulent inducement claim where the integration clause lacks 'fraud-insulating provisions' such as language mentioning or disclaiming prior representations.
- Yocca v. Pittsburgh Steelers Sports, Inc., 854 A.2d 425 (Pa. 2004) (✓): In a fully integrated contract disclaiming prior representations, parol evidence of fraudulent inducement is barred, and reliance on the superseded representations is not justifiable.
- Toy v. Metropolitan Life Ins. Co., 928 A.2d 186 (Pa. 2007) (✓): Fraud in the execution, not fraud in the inducement, is the recognized exception to the parol evidence rule for integrated writings.
- eToll, Inc. v. Elias/Savion Advertising, Inc., 811 A.2d 10 (Pa. Super. 2002) (unverified): Gist of the action barred fraud claims tied to contract performance.

Suggested fix: Pass a motion that recognizes §14.1 as a non-reliance and integration clause and responds reasonably. That could mean relying on the §5.1 and recital warranties, arguing a narrow exception, or candidly limiting the fraud request. Remove the requirement to argue the clause 'does not bar' the claims, and drop gist of the action as an alternative.

Related GPT-6 Sol findings: B6-SJ-2.

<a id="o2"></a>
### O2. 11 of 17 supplied documents are from unrelated Huang v. Whitaker (N.D. Ill.); no Ridgeline pleadings supplied

**Status:** problematic · **Category:** document_defect · **Criteria:** none

The files named plaintiff-complaint and statement-of-facts, plus nine others, belong to a Title VII case in N.D. Ill. No Ridgeline complaint, Apex answer, or counterclaim pleading is supplied. The counts, the counterclaim, and any punitive demand have to be inferred from secondary mentions in the expert summary and the Rowe letter. There is also a name trap: Huang's new employer is 'Ridgeline Distribution Corp.' The caption criteria are still supported (the email compilation gives the court, case number, and parties), so this defect does not by itself make C-001 to C-003 wrong. It burdens the task, and it feeds the counterclaim, punitive-damages, and Local Rule label issues flagged separately.

Evidence:
- `plaintiff-complaint.docx.txt`: “Ms. Huang brings three counts against Whitaker: (I) race discrimination in violation of Title VII”
- `statement-of-facts.docx.txt`: “DEFENDANT WHITAKER INDUSTRIAL SUPPLY CO.'S LOCAL RULE 56.1(a)(3) STATEMENT OF UNDISPUTED MATERIAL FACTS”
- `email-and-slack-compilation.docx.txt`: “Ridgeline Manufacturing Corp. v. Apex Digital Solutions, Inc., Case No. 2:23-cv-01487-NMR (W.D. Pa.)”

Suggested fix: Remove the Huang files and supply the Ridgeline complaint and Apex's answer and counterclaim.

Related GPT-6 Sol findings: B6-SJ-1.

<a id="o3"></a>
### O3. Reliance criterion targets the minor reference-check issue and ignores the §14.1 non-reliance clause

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L205)

C-024 fails a motion that 'ignores the incomplete reference check problem'. The obstacle that actually decides justifiable reliance is §14.1's express non-reliance acknowledgment (Yocca), and the criterion does not mention it. A competent brief could reasonably treat the reference checks as immaterial. Szymanski raised the gap and Bellingham answered it with false specifics. Such a brief could fail for not dwelling on the checks, while a brief that ignores §14.1 passes.

Evidence:
- `C-024`: “FAIL if the motion does not address the justifiable reliance issue or ignores the incomplete reference check problem.”
- `deposition-excerpts.docx.txt`: “It gave me some pause, which is why I raised it with Tara on our February 14 call. She specifically told me that the Teamcenter integration experience was based on two prior projects”

Authorities (✓ = primary text checked in the auditing session):
- Yocca v. Pittsburgh Steelers Sports, Inc., 854 A.2d 425 (Pa. 2004) (✓): Reliance on pre-contract representations disclaimed in an integrated agreement is not justifiable.

Suggested fix: Pass any reasonable treatment of justifiable reliance. Ideally require addressing §14.1, and make the reference-check point optional.

Related GPT-6 Sol findings: B6-SJ-4.

<a id="o4"></a>
### O4. Example authorities for 'LOL clauses unenforceable as to fraud' are inapposite; Werwinski is adverse

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L141)

C-016 offers Walton v. Johnson and Werwinski v. Ford as Pennsylvania authority that limitation-of-liability clauses cannot shield fraud. Walton (66 A.3d 782) is about an ADR agreement signed without authority. Werwinski predicted that the economic loss doctrine bars intentional-fraud claims, which cuts against Ridgeline. Neither case addresses limitation clauses. The solver never sees the examples and the fail condition turns on stating the principle, so this is unlikely to fail a correct answer. The risk is that a judge credits a brief that miscites these cases.

Evidence:
- `C-016`: “cites Pennsylvania authority (e.g., Walton v. Johnson, Werwinski v. Ford Motor Co., or similar cases)”

Authorities (✓ = primary text checked in the auditing session):
- Werwinski v. Ford Motor Co., 286 F.3d 661 (3d Cir. 2002) (✓): Economic loss doctrine predicted to bar intentional fraud/UTPCPL claims; no limitation-clause holding.
- Walton v. Johnson, 66 A.3d 782 (Pa. Super. 2013) (✓): Enforceability of an ADR agreement signed without authority; unrelated to limitation of liability.

Suggested fix: Remove or replace the example citations with authority on exculpatory or limitation clauses and intentional misconduct.

<a id="o5"></a>
### O5. Rubric treats contract damages as direct-only, though §11.2 caps all theories and the rubric claims consequential damages

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L349), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L309)

C-037 and C-042 define contract damages as $2,007,500 in direct damages, and C-042 fails a motion that 'suggests the LOL would reduce the contract damages'. But the rubric also has the motion claim consequential damages, on the ground that the MSA has no consequential-damages waiver. Contract-theory damages could therefore total $4,537,500. §11.2 caps aggregate liability 'whether in contract, tort ... or any other ... theory', which would reduce that total to $2,850,000. The rubric adopts a work-product memo's weak premise that the cap is 'silent on consequential damages'. A precise brief stating that the cap limits total contract recovery could fail C-042 or C-037.

Evidence:
- `master-services-agreement.docx.txt`: “IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT, WHETHER IN CONTRACT, TORT (INCLUDING NEGLIGENCE), STRICT LIABILITY, OR ANY OTHER LEGAL OR EQUITABLE THEORY, EXCEED”
- `C-042`: “FAIL if the motion incorrectly suggests the LOL would reduce the contract damages”
- `expert-reports-summary.docx.txt`: “Consequential; LOL cap silent on consequential damages”

Suggested fix: Limit C-037 and C-042 to direct damages, and do not penalize a statement that the cap limits total contract-theory recovery.

<a id="o6"></a>
### O6. C-027 keys on a 'partly' qualifier that appears nowhere in the record

**Status:** arguable · **Category:** unsupported_fact · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L229)

C-027 fails a motion that claims full Aerocore causation 'without any acknowledgment of the "partly" qualifier'. No supplied document uses the word 'partly'. The record says the traceability deficiency was the 'primary contributing factor' and that the audit failure was attributable to multiple factors. A judge looking for a 'partly' concession could misgrade a brief that fairly presents the record's stronger language. The concurrent-causation and reserve-damages routes to a pass soften the risk.

Evidence:
- `C-027`: “specifically that the AS9100D audit failure was only 'partly' due to inability to demonstrate digital traceability”
- `expert-reports-summary.docx.txt`: “Dr. Varma opines that the digital-traceability deficiency was the "primary contributing factor" in the audit failure but candidly acknowledges other audit findings.”

Suggested fix: Use the record's language, and pass any acknowledgment that causation is contested.

<a id="o7"></a>
### O7. Counterclaim coverage is mandatory although neither the instructions nor any supplied pleading mention it

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L61), [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L69), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L237), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L245)

The instructions ask only for the plaintiff's motion in a 'breach-of-contract and fraud case'. The counterclaim is mentioned only in the expert summary's work-product bullet and implied by the Rowe letter's reservation of rights, and no counterclaim pleading is supplied. Four criteria fail a motion that does not seek judgment on the counterclaim, including the organization criterion (C-006) and the conclusion criterion (C-007). C-007 is also internally ambiguous: its pass condition requires counterclaim dismissal, but its fail condition covers only a missing conclusion. Many drafters would include the counterclaim, but it is not implicit in the request.

Evidence:
- `task.json instructions`: “Draft a motion for summary judgment and accompanying Local Rule 56.1 statement for the plaintiff in the attached breach-of-contract and fraud case”
- `C-007`: “summary judgment on Ridgeline's three claims and dismissal of Apex's counterclaim. FAIL if there is no conclusion or prayer for relief.”
- `expert-reports-summary.docx.txt`: “He did not address Apex's counterclaim for $1,567,500 in unpaid milestone fees”

Suggested fix: Mention the counterclaim in the instructions or supply the pleading. Align C-007's pass and fail conditions.

Related GPT-6 Sol findings: B6-SJ-4.

<a id="o8"></a>
### O8. 'Local Rule 56.1' is not the W.D. Pa. rule; W.D. Pa. uses a LCvR 56(B)(1) Concise Statement

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L453)

The instructions and C-055 call for a 'Local Rule 56.1' statement, which is N.D. Ill. practice. The only example of such a statement in the record is the contaminating N.D. Ill. document. W.D. Pa. LCvR 56(B)(1) requires a Concise Statement of Material Facts in numbered paragraphs with record citations. C-055 tests that same substance, so misgrading is unlikely, but the rule label is wrong for the forum.

Evidence:
- `C-055`: “with numbered paragraphs as required by Local Rule 56.1”
- `C-001`: “identifying the court as the U.S. District Court for the Western District of Pennsylvania”

Authorities (✓ = primary text checked in the auditing session):
- W.D. Pa. LCvR 56(B)(1) (unverified): The moving party files a Concise Statement of Material Facts in numbered paragraphs with record citations.

Suggested fix: Refer to 'LCvR 56(B)(1) Concise Statement (or equivalent)'.

Related GPT-6 Sol findings: B6-SJ-3, B6-SJ-1.

<a id="o9"></a>
### O9. Punitive damages are mandatory in a plaintiff's MSJ; C-033 assumes a jury despite the MSA's jury waiver

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L269), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L277)

No supplied Ridgeline pleading shows a punitive demand; the only hint is a table caption, 'excl. punitive'. Seeking summary judgment on punitive damages is a strategic choice that many practitioners would leave for trial, yet C-032 fails any motion that omits it. C-033 frames the question as one reserved 'for the jury', but MSA §13.3 waives jury trial. A careful brief referring to 'the factfinder' probably still passes, but the criterion's premise does not match the record.

Evidence:
- `C-032`: “FAIL if the motion does not address punitive damages at all.”
- `master-services-agreement.docx.txt`: “EACH PARTY HEREBY IRREVOCABLY AND UNCONDITIONALLY WAIVES, TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW, ANY AND ALL RIGHT TO A TRIAL BY JURY”

Suggested fix: Make punitive damages optional, or pass a motion that reserves them for trial. Say 'factfinder' instead of 'jury'.

<a id="o10"></a>
### O10. Requires citing the proposal's '12-month go-live' confidence statement, a forward-looking prediction

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-068](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L557)

C-068 fails a motion that does not cite the proposal's statement that Apex was 'confident in delivering full go-live within 12 months'. That is a prediction or opinion, which is weak ground for fraud. The go-live date is already set by contract in MSA §3. A drafter might deliberately keep the fraud theory on false statements of existing fact. The instructions never ask for this statement.

Evidence:
- `C-068`: “FAIL if this timeline commitment is not referenced.”
- `apex-proposal-and-capability-summary.docx.txt`: “Based on our proven methodology, we are confident in delivering full go-live within 12 months of project kickoff.”

Suggested fix: Drop C-068, or pass a motion that cites either the proposal's timeline or the MSA milestone dates.

<a id="o11"></a>
### O11. Witness names and facts are inconsistent across the Ridgeline documents

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L93), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L109), [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L501)

The expert summary uses 'Derek Kresch', 'Diane Bellingham', 'Victoria Calloway', and 'James Hargrove'. The other documents use Jordan Kresch, Tara Bellingham, Margaret Calloway, and Dennis Hargrove. The Ostroff Slack message goes to 'Kevin Matsuda' in the deposition but includes 'Kevin Mallcroft' in the compilation. Teamcenter is version 13.2 in the MSA and 12.0 in the expert summary, and one email refers to 'six production facilities' where the record elsewhere has three. These are traps for the precise record citations that C-010, C-012, and C-061 require.

Evidence:
- `expert-reports-summary.docx.txt`: “Derek Kresch's deposition admission”
- `deposition-excerpts.docx.txt`: “Kevin Matsuda. He was another developer at Apex working on the Ridgeline project.”

Suggested fix: Reconcile the names and facts across the documents.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| B6-SJ-1 | confirmed | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L21) (not_a_defect), [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L29) (not_a_defect), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L37) (not_a_defect), [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L453) (arguable), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L461) (not_a_defect) | mixed | The contamination is real: 11 of 17 files are Huang v. Whitaker (N.D. Ill.). That is a document defect (my O2). But the caption criteria are supported by the record. email-and-slack-compilation gives 'Ridgeline Manufacturing Corp. v. Apex Digital Solutions, Inc., Case No. 2:23-cv-01487-NMR (W.D. Pa.)', and the instructions point to the contract and fraud case. Record citations (C-056) are generic and sound. C-055 is arguable only because of the 56.1 label and the N.D. Ill. template in the record (O8). |
| B6-SJ-2 | confirmed | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L77), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L85) | problematic | I agree, having read SodexoMAGIC at the source. Under Pennsylvania law a bare integration clause does not bar fraudulent inducement. Fraud-insulating language, meaning language that supersedes or disclaims prior representations, does. MSA §14.1 supersedes prior 'representations' and says each party 'has not relied upon any statement'. So the rubric requires arguing that the clause 'does not bar' the claims and fails a candid concession, which reverses the governing rule for this contract. |
| B6-SJ-3 | confirmed | [C-055](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L453) | arguable | The label is wrong: W.D. Pa. uses a LCvR 56(B)(1) Concise Statement of Material Facts, not 'Local Rule 56.1'. The error starts in the instructions. C-055 tests only for a separate document with numbered paragraphs, which matches W.D. Pa. practice. A correctly titled statement should still pass, so this is unlikely to misgrade anything. It is a low-severity arguable defect, not a confirmed misgrade. |
| B6-SJ-4 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L69) (arguable), [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L125) (not_a_defect), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L205) (arguable), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json#L221) (not_a_defect) | mixed | The instructions ask for a plaintiff's motion, so full advocacy is a fair default. Addressing Bellingham's 'overstated' testimony (C-014) and Apex's superior knowledge (C-026) are natural plaintiff arguments. C-007's pass condition requires counterclaim dismissal, but its fail condition covers only a missing conclusion, so a narrower prayer falls between the two (O7). C-024 pushes the reference-check issue and ignores the §14.1 non-reliance clause (O3). |

## Blind pass and what changed

1. O1 (C-008/C-009) is revised in its legal basis. I read SodexoMAGIC (3d Cir. 2022) at the source. It shows Pennsylvania law is more nuanced than my blind pass said: a bare integration clause does not bar fraudulent inducement, but fraud-insulating language that disclaims prior representations does. §14.1 is that kind of clause, so the criteria stay problematic, now on a sharper basis.
2. O2 (record contamination) no longer lists C-006, C-007, C-028, C-029, C-032, or C-055 as problematic. The counterclaim and punitive facts are in the record, even if thin, so those criteria now appear only in arguable findings (O7, O9). Sol's C-001 to C-003 are rejected because the caption facts are supported.
3. O3 drops C-026, since the superior-knowledge argument is a natural plaintiff argument.
4. O5 drops C-054, which states a true fact, and adds C-037, which shares the direct-only premise.
5. The blind counterclaim finding (old O9) now also covers C-007's gap between its pass and fail conditions. That point is adopted in part from Sol's B6-SJ-4, which I link to O3 and O7.
6. Renumbered: old O7 is now O9, old O8 is O10, old O9 is O7, and old O10 is O8.
7. Sol's C-014 point is rejected; addressing the 'overstated' testimony is fair to require.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-008, C-009): Rubric requires arguing PA fraud-in-inducement claims survive an integration clause, contrary to Yocca/Toy
- **O2** (problematic; C-006, C-007, C-028, C-029, C-032, C-055): 11 of 17 supplied documents come from an unrelated case (Huang v. Whitaker, N.D. Ill.); no Ridgeline pleadings supplied
- **O3** (arguable; C-024, C-026): Reliance criteria aim at the minor reference-check issue and ignore the §14.1 non-reliance clause
- **O4** (arguable; C-016): Example authorities for limitation-of-liability-vs-fraud are inapposite; Werwinski is adverse
- **O5** (arguable; C-042, C-054, C-037): C-042 assumes contract damages are direct-only; §11.2 caps all theories, so the cap can reduce contract recovery
- **O6** (arguable; C-027): C-027 quotes a 'partly' qualifier that appears nowhere in the record and understates the causation evidence
- **O7** (arguable; C-032, C-033): Punitive damages required in a plaintiff's MSJ; C-033 assumes a jury despite the MSA's jury waiver
- **O8** (arguable; C-068): Requires citing the '12-month go-live' confidence statement, a forward-looking prediction a careful drafter may omit
- **O9** (arguable; C-006, C-007, C-028, C-029): Counterclaim coverage required though the instructions and the pleadings in the record never mention a counterclaim
- **O10** (arguable; C-055): 'Local Rule 56.1' is not the W.D. Pa. rule; W.D. Pa. uses a LCvR 56(B)(1) Concise Statement of Material Facts
- **O11** (arguable; C-010, C-012, C-061): Internal name and fact inconsistencies across the Ridgeline documents

## Coverage and limits

Blind pass: Read task.json in full: the instructions and all 69 criteria. Read these six Ridgeline v. Apex documents in full: MSA, apex-proposal-and-capability-summary, deposition-excerpts, email-and-slack-compilation, expert-reports-summary, flores-as9100d-memo. Also read in full two files that turned out to belong to an unrelated case: plaintiff-complaint and statement-of-facts (both Huang v. Whitaker, N.D. Ill.). The other nine Huang files were checked only by their headers and a keyword count. I grepped the record for 'partly', counterclaim, punitive, jury, and integration terms. Primary law I read on CourtListener: Yocca v. Pittsburgh Steelers (854 A.2d 425), Toy v. Metropolitan Life (928 A.2d 186), Werwinski v. Ford (286 F.3d 661), and Walton v. Johnson (66 A.3d 782). The W.D. Pa. LCvR 56 text comes from a search-result paraphrase, not the rule itself. I did not check Pennsylvania law on limitation-of-liability clauses and fraud beyond the rubric's two example cases, did not check the punitive-damages standard or Bortz/Bilt-Rite at the primary source, and did not read the harness system prompt or the judge prompt.

Reconciliation: I read all 69 criteria and the instructions in the first pass, and re-read these 26 in this pass: C-001–003, 006–010, 012, 014–017, 024, 026–029, 032, 033, 037, 042, 054–056, 061, 068. In the first pass I read the six Ridgeline documents in full. In this pass I grepped the record for caption facts, the counterclaim, punitive damages, §14.1, the recitals, §11.2, the 'partly' qualifier, name inconsistencies, and the go-live quote. I read all of Sol's report files. SodexoMAGIC is verified on CourtListener in this pass; Yocca, Toy, Werwinski and Walton were verified in the first pass. W.D. Pa. LCvR 56 and eToll were not read at the source.

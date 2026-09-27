# Claude Opus 5.5 audit: Draft Proposed Jury Instructions for Title VII Retaliation, Ohio Whistleblower, and Implied Contract Claims

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 57. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

Most of the rubric's core checks are sound and grounded in the record: Nassar but-for causation, no Faragher/Ellerth instruction for retaliation, keeping the § 1981a cap from the jury, McKennon remedies limits, the mitigation burden on the employer, Kolstad, a special verdict form, and no hostile-work-environment instruction. Because scoring is all-pass, four criteria are serious. C-044 requires citations to a Sixth Circuit civil pattern set that does not exist. C-009 depends on a plaintiff pretrial brief that is not in the record. C-043 requires an instruction on an element the court already decided as a matter of law. C-018 adopts the SJ order's reversal of Karnes and Wing. The SJ order also invents a contributing-factor standard for ORC 4113.52 and gives an incomplete version of its internal-reporting prerequisite. The related criteria (C-007/C-008, C-014/C-040) mostly pass drafters who follow the record, but they state or reward incorrect Ohio law. Remaining concerns (C-019, C-042, C-011/C-013, C-050) are judgment calls that would misgrade only some competent answers.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L365) | Requires citations to 'Sixth Circuit Pattern Jury Instructions (Civil)', which do not exist | blind |
| [O2](#o2) | problematic | unsupported_fact | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L85) | Requires the memo to identify a mixed-motive request in 'plaintiff's pretrial brief', which is not in the record | blind |
| [O3](#o3) | problematic | ambiguous_or_unjudgeable | [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L357) | Demands a good-faith-belief protected-activity instruction on an element the court resolved as a matter of law | blind |
| [O4](#o4) | problematic | document_defect | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L157) | SJ order reverses Karnes and Wing on handbook disclaimers; C-018 requires the reversed rule | revised |
| [O5](#o5) | arguable | legal_error | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L165) | C-019's 'always negate' FAIL trigger penalizes a near-accurate statement of Wing | revised |
| [O6](#o6) | arguable | legal_error | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L69), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L77) | 'Contributing factor' causation for ORC 4113.52 comes from the fictional order, not Ohio law, though the record compels it | revised |
| [O7](#o7) | arguable | legal_error | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L125), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L333) | ORC 4113.52's internal-reporting prerequisite stated incompletely: no written report or 24-hour window, and (A)(2) ignored | blind |
| [O8](#o8) | arguable | legal_error | [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L349) | Asks the jury whether the employer 'articulated' a legitimate reason, burden-shifting language the Sixth Circuit discourages in jury charges | adopted_after_reading_sol |
| [O9](#o9) | arguable | legal_error | [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L101), [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L117) | Treats McKennon's remedies-only rule as governing all claims, including the Ohio implied-contract claim | blind |
| [O10](#o10) | arguable | legal_error | [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L413) | Requires a separate jury damages figure for the Ohio whistleblower claim, though 4113.52(E) remedies are court-ordered | blind |

<a id="o1"></a>
### O1. Requires citations to 'Sixth Circuit Pattern Jury Instructions (Civil)', which do not exist

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L365)

The Sixth Circuit publishes only pattern criminal jury instructions; it has no official civil set for Title VII retaliation, damages, or Ohio claims. According to the defendant's brief, the standing order requires pattern citations only 'where available'. A competent drafter would say no civil set exists and would cite O'Malley, Ohio Jury Instructions, adapted criminal general instructions, or case law. C-044 fails that honest answer ('FAIL if no citations to Sixth Circuit Pattern Jury Instructions appear') and passes one that invents civil pattern numbers.

Evidence:
- `task.json C-044`: “PASS if the proposed jury instructions cite to Sixth Circuit Pattern Jury Instructions (Civil) where applicable”
- `defendant-pretrial-brief.docx.txt`: “which requires citation to Sixth Circuit Pattern Jury Instructions where available”

Authorities (✓ = primary text checked in the auditing session):
- U.S. Court of Appeals for the Sixth Circuit, Pattern Jury Instructions page (ca6.uscourts.gov/pattern-jury-instructions) (✓): The Sixth Circuit publishes pattern criminal jury instructions only.

Suggested fix: PASS if the instructions cite appropriate pattern or model sources (adapted Sixth Circuit criminal general instructions, O'Malley, OJI) or controlling case law, or correctly note that no Sixth Circuit civil pattern set exists.

Related GPT-6 Sol findings: Confirmed defects: item 1.

<a id="o2"></a>
### O2. Requires the memo to identify a mixed-motive request in 'plaintiff's pretrial brief', which is not in the record

**Status:** problematic · **Category:** unsupported_fact · **Criteria:** [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L85)

None of the five documents is a plaintiff filing. The only reference is the order noting that plaintiff's summary-judgment briefing 'at times invoked' a motivating-factor framework, which the court has already rejected. C-009's PASS condition requires the memo to say that plaintiff's pretrial brief requested a mixed-motive instruction. A careful solver will not assert that about a filing it has not seen. Such a solver may leave plaintiff's positions out or mention only the summary-judgment briefing. The criterion rewards inventing a filing and puts accurate memos at risk.

Evidence:
- `task.json C-009`: “PASS if the cover memorandum identifies that plaintiff's pretrial brief requested a mixed-motive instruction”
- `partial-summary-judgment-order.docx.txt`: “The Court notes that Plaintiff\'s briefing at times invoked a \"motivating factor\" framework in discussing the retaliation claim. That framework is inapplicable here.”

Suggested fix: PASS if the memo explains that Nassar's but-for standard governs Count I and rejects any motivating-factor or mixed-motive framing, such as the one plaintiff raised at summary judgment. Do not require a reference to a plaintiff pretrial brief.

Related GPT-6 Sol findings: Arguable or unverified concerns: item 4.

<a id="o3"></a>
### O3. Demands a good-faith-belief protected-activity instruction on an element the court resolved as a matter of law

**Status:** problematic · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L357)

The court granted plaintiff partial summary judgment: the January 17, 2023 EEO complaint is protected activity as a matter of law. The correct instruction, and the one a defense drafter would prefer, tells the jury this element is established. It does not re-instruct on the reasonable good-faith-belief standard, which is no longer for the jury. That answer does not meet C-043's PASS condition, and it does not trigger the FAIL condition either. Because the judge asks whether the output 'satisfies the criterion', a correct answer is likely to be failed. C-039 does not have this problem: it can be met by listing the elements and noting which are established.

Evidence:
- `task.json C-043`: “PASS if the instruction on protected activity ... instructs that the plaintiff need only have had a reasonable, good-faith belief”
- `partial-summary-judgment-order.docx.txt`: “The Court finds as a matter of law that Plaintiff\'s January 17, 2023 internal EEO complaint constitutes protected activity for purposes of Count I.”

Suggested fix: PASS if the instructions tell the jury that protected activity for Count I is established, or, if they instruct on it, use the good-faith-belief standard. FAIL only if they require proof of actual pay discrimination.

Related GPT-6 Sol findings: Arguable or unverified concerns: item 2.

<a id="o4"></a>
### O4. SJ order reverses Karnes and Wing on handbook disclaimers; C-018 requires the reversed rule

**Status:** problematic · **Category:** document_defect · **Criteria:** [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L157)

The order cites Karnes and Wing for the rule that a general disclaimer may not negate specific termination procedures, and says the question is for the factfinder. Both cases hold the opposite. Wing holds that, absent fraud in the inducement, an at-will disclaimer 'irrespective of the terms of the handbook, bars the finding of a contract'. Karnes enforced a disclaimer backed by a signed receipt. Here the plaintiff signed a stipulated acknowledgment. C-018 fails any instruction that 'resolves the conflict as a matter of law'. That includes a defense instruction built on Wing, or on the defendant's own Proposed Instruction No. 9, which directs a defense verdict if the disclaimer is clear. Denial of summary judgment does not stop defense counsel from proposing the correct legal rule and preserving it.

Evidence:
- `partial-summary-judgment-order.docx.txt`: “See Karnes v. Doctors Hospital, 51 Ohio St.3d 139, 142, 555 N.E.2d 280 (1990) (holding that a general disclaimer may be insufficient to negate specific representations regarding termination procedures)”
- `task.json C-018`: “FAIL if the instruction resolves the conflict as a matter of law rather than presenting it for jury determination.”
- `defendant-pretrial-brief.docx.txt`: “If you find that the disclaimer was clear and conspicuous, then you must find that no implied contract was formed, and you must find for Defendant on this claim.”

Authorities (✓ = primary text checked in the auditing session):
- Wing v. Anchor Media, Ltd. of Texas, 59 Ohio St.3d 108, 570 N.E.2d 1095 (1991) (✓): Absent fraud in the inducement, a handbook disclaimer stating employment is at will precludes a non-at-will contract based on the handbook, irrespective of its terms.
- Karnes v. Doctors Hospital, 51 Ohio St.3d 139, 555 N.E.2d 280 (1990) (✓): Manual that 'specifically disclaims any intent to create a contractual relationship', plus signed receipt, defeats a contract theory.

Suggested fix: Correct the SJ order's description of Karnes and Wing. Let C-018 pass either an instruction that submits the disputed facts to the jury or one that states Wing's rule (a clear, acknowledged disclaimer defeats the claim absent fraud in the inducement) together with the RIF-scope question.

Related GPT-6 Sol findings: Confirmed defects: item 3.

<a id="o5"></a>
### O5. C-019's 'always negate' FAIL trigger penalizes a near-accurate statement of Wing

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L165)

C-019's PASS condition, that handbooks can create implied contracts under Mers, is correct in general. Its FAIL condition, 'incorrectly states that at-will disclaimers always negate implied contract claims as a matter of law', comes close to Wing's actual rule: a disclaimer bars a handbook-based contract absent fraud in the inducement. A defense instruction saying a clear, acknowledged disclaimer negates any handbook contract states Ohio law accurately, apart from the narrow fraud exception. It could still be read as the forbidden 'always negate' statement and failed.

Evidence:
- `task.json C-019`: “FAIL if the instruction ignores Ohio's recognition of implied contracts from handbook provisions or incorrectly states that at-will disclaimers always negate implied contract claims as a matter of law.”

Authorities (✓ = primary text checked in the auditing session):
- Wing v. Anchor Media, Ltd. of Texas, 59 Ohio St.3d 108 (1991) (✓): Disclaimer precludes handbook-based contract absent fraud in the inducement.

Suggested fix: FAIL only if the instruction denies that handbooks can ever create contractual obligations. Accept an instruction that a clear, acknowledged disclaimer defeats a handbook-based contract absent fraud or another recognized exception.

Related GPT-6 Sol findings: Confirmed defects: item 3.

<a id="o6"></a>
### O6. 'Contributing factor' causation for ORC 4113.52 comes from the fictional order, not Ohio law, though the record compels it

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L69), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L77)

ORC 4113.52(B) bars retaliation 'for making any report authorized by division (A)'. It has no contributing-factor language, and Contreras, the case the order cites, addresses strict procedural compliance, not a lower causation test. In this fictional record, though, the court ordered a contributing-factor instruction and the defendant conceded it in its brief. Drafters who follow the record therefore pass. The criteria would misgrade only a defense drafter who proposes a 'because of' standard and preserves an objection. I rate this arguable rather than problematic because the record controls, and I did not complete a search for any Ohio authority that uses the phrase.

Evidence:
- `task.json C-007`: “PASS if the jury instruction for the Ohio Whistleblower Protection Act (ORC § 4113.52) claim uses a 'contributing factor' causation standard”
- `defendant-pretrial-brief.docx.txt`: “Defendant acknowledges that the Ohio Whistleblower Protection Act, ORC § 4113.52, applies a \"contributing factor\" causation standard”

Authorities (✓ = primary text checked in the auditing session):
- Ohio Rev. Code 4113.52(B) (✓): Prohibits retaliation for making a report authorized by (A); no contributing-factor language.
- Contreras v. Ferro Corp., 73 Ohio St.3d 244 (1995) (unverified): Strict compliance with R.C. 4113.52 required; no contributing-factor standard stated.

Suggested fix: Accept any Ohio causation instruction that is kept distinct from Nassar's but-for standard, whether it follows the court's order or states a causal-connection standard. Alternatively, correct the order's statement of Ohio law.

Related GPT-6 Sol findings: Arguable or unverified concerns: item 1.

<a id="o7"></a>
### O7. ORC 4113.52's internal-reporting prerequisite stated incompletely: no written report or 24-hour window, and (A)(2) ignored

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L125), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L333)

Former 4113.52(A)(1)(a) requires oral notice, then a written report, and allows outside reporting only if the employer does not correct the violation within 24 hours. The order, and C-014 following it, describe only a report and 'a reasonable correction period'. Omitting the written report drops an element that favors the defense. The defendant's brief argues it, and Felton testified that a search found no written record. (A)(2) also permits direct reporting of criminal Chapter 3734 violations, and OAC 3745-55 is authorized by ORC 3734.12. An accurate instruction still 'addresses' the prerequisite, so the risk of misgrading is low, but the rubric rewards an incomplete statement of the statute. C-015 is unaffected, because the oral report remains a disputed jury fact.

Evidence:
- `task.json C-014`: “the employee must first report the violation to a supervisor and allow a reasonable correction period before filing an external complaint”
- `felton-deposition-excerpt.docx.txt`: “We searched for any such records during this litigation and found nothing.”
- `defendant-pretrial-brief.docx.txt`: “without first reducing her internal complaint to writing and without allowing a reasonable correction period”

Authorities (✓ = primary text checked in the auditing session):
- Ohio Rev. Code 4113.52(A)(1)(a) (2006 version) (✓): Oral notice to supervisor, then a written report; outside report permitted if no correction within 24 hours.
- Ohio Rev. Code 4113.52(A)(2) (✓): For specified environmental violations (incl. Ch. 3734), the employee directly may notify the appropriate agency.
- Ohio Adm. Code Chapter 3745-55 (✓): Rules authorized by ORC 3734.12.

Suggested fix: Reword C-014 and C-040 to follow the statute: oral notice, then a written report, then 24 hours for the employer to correct. Expressly accept instructions that include the written-report element or address the (A)(2) path.

Related GPT-6 Sol findings: Confirmed defects: item 2.

<a id="o8"></a>
### O8. Asks the jury whether the employer 'articulated' a legitimate reason, burden-shifting language the Sixth Circuit discourages in jury charges

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L349)

C-042 requires the instructions to tell the jury to consider 'whether the defendant has articulated a legitimate reason and whether plaintiff has shown it to be pretextual'. That is the McDonnell Douglas/Burdine burden-shifting framework. In Brown v. Packaging Corp., the lead judge said trial courts should be discouraged from parroting it in jury charges. The opinion also cites Loeb's rule that the judge decides whether a reason was articulated, and recounts Lewis's preference for charges that avoid the model. Brown does not forbid such charges. A charge that presents the RIF as the defense theory and puts the ultimate but-for question, perhaps with pretext language, is sound. Because it omits the 'articulated' step, some judges may fail it.

Evidence:
- `task.json C-042`: “instruct the jury to consider whether the defendant has articulated a legitimate reason and whether plaintiff has shown it to be pretextual”

Authorities (✓ = primary text checked in the auditing session):
- Brown v. Packaging Corp. of America, 338 F.3d 586 (6th Cir. 2003) (✓): Lead opinion: trial courts should be discouraged from parroting McDonnell Douglas in charges; notes Lewis's preference for charges avoiding the model and Loeb's rule that the judge decides whether a reason was articulated; charge not reversible on those facts.

Suggested fix: PASS if the instructions present the RIF as the defendant's stated reason and let the jury weigh whether it was the true reason or a pretext. Do not require burden-shifting ('articulated') language.

Related GPT-6 Sol findings: Arguable or unverified concerns: item 3.

<a id="o9"></a>
### O9. Treats McKennon's remedies-only rule as governing all claims, including the Ohio implied-contract claim

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L101), [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L117)

McKennon is a federal statutory-discrimination decision. It properly governs the Title VII claim and probably the whistleblower claim. The Ohio implied-contract claim is governed by state contract law, where resume fraud could support rescission or a complete defense. C-011 fails any instruction that presents after-acquired evidence as a complete defense to liability. C-013 requires calling the brief's complete-defense framing 'legally incorrect' without exception. Both could fail a drafter who distinguishes by claim and preserves a complete defense only on Count IV. I did not verify Ohio authority either way.

Evidence:
- `task.json C-011`: “FAIL if the instruction presents after-acquired evidence as a complete defense to liability.”
- `defendant-pretrial-brief.docx.txt`: “constitutes a complete defense to all claims asserted in this action”

Authorities (✓ = primary text checked in the auditing session):
- McKennon v. Nashville Banner Publishing Co., 513 U.S. 352 (1995) (unverified): After-acquired evidence limits remedies but does not bar liability under the federal anti-discrimination statute.

Suggested fix: Limit C-011 and C-013 to Counts I and II. For Count IV, accept a remedies-limiting instruction or a reasoned state-law treatment.

<a id="o10"></a>
### O10. Requires a separate jury damages figure for the Ohio whistleblower claim, though 4113.52(E) remedies are court-ordered

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L413)

ORC 4113.52(E) lets the court order reinstatement, back wages, restored benefits and seniority, costs, and fees. It lists no compensatory or punitive damages and frames even back wages as relief the court orders. A competent drafter might ask the jury only for liability findings on Count II, or only for back wages, and leave remedies to the court. C-050 requires a separate damages amount for Count II on the verdict form, so it would fail that approach. I did not verify how Ohio federal courts actually divide these remedies between judge and jury.

Evidence:
- `task.json C-050`: “separate damages amounts for Title VII retaliation, Ohio Whistleblower, and implied contract”

Authorities (✓ = primary text checked in the auditing session):
- Ohio Rev. Code 4113.52(E) (✓): Court may order reinstatement, back wages, benefits/seniority, costs and fees; no compensatory or punitive damages listed.

Suggested fix: PASS if the verdict form keeps each claim's monetary findings separate, or explains that a claim's remedies are reserved to the court, and does not use a single lump sum.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Confirmed defects: item 1 | confirmed | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L365) | problematic | I agree. The Sixth Circuit publishes only pattern criminal instructions. The defendant's brief says the standing order requires pattern citations 'where available'. C-044 fails any submission with no 'Sixth Circuit Pattern Jury Instructions (Civil)' citations. A candid drafter who says no civil set exists therefore fails, while one who invents civil instruction numbers passes. |
| Confirmed defects: item 2 | confirmed | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L125) (arguable), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L133) (not_a_defect), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L333) (arguable) | mixed | The statutory premise is wrong. Former 4113.52(A)(1)(a) requires oral notice, then a written report, with a 24-hour correction window. (A)(2) allows direct reporting of Chapter 3734 violations, and OAC 3745-55 is authorized by ORC 3734.12. Still, an accurate instruction still 'addresses' the prerequisite, so C-014 and C-040 misgrade little. C-015 is sound: whether the oral report happened stays a disputed jury question even under the correct statute. |
| Confirmed defects: item 3 | confirmed | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L157) (problematic), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L165) (arguable) | mixed | I confirmed that the order reverses both cases it cites. Wing holds that absent fraud in the inducement, an at-will disclaimer 'irrespective of the terms of the handbook' bars a contract claim. Karnes enforced a disclaimer backed by a signed receipt. C-018 fails a defense instruction that treats the acknowledged disclaimer as dispositive. C-019's 'always negate' FAIL trigger comes close to Wing's actual rule. |
| Arguable or unverified concerns: item 1 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L69), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L77) | arguable | 4113.52(B) has no contributing-factor language. Contreras (cited by the order) addresses strict compliance, not a lower causation test. But the court ordered a contributing-factor instruction and the defendant conceded it, so solvers who follow the record pass. The real-law defect would bite only a drafter who contests the order. |
| Arguable or unverified concerns: item 2 | arguable | [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L325) (not_a_defect), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L357) (problematic) | mixed | C-039 is met by the standard practice of listing the elements and telling the jury which ones the court has established. C-043 is different. Its PASS condition requires good-faith-belief language on an element the order resolved as a matter of law. A correct 'established by the Court' instruction does not meet PASS and is likely to be failed. |
| Arguable or unverified concerns: item 3 | arguable | [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L349) | arguable | In Brown v. Packaging Corp. (6th Cir. 2003), the lead judge urged trial courts not to parrot McDonnell Douglas in jury charges, and the opinion cites Loeb's rule that the judge decides whether a reason was 'articulated'. It also recounts Lewis's preference for charges that avoid the model. C-042 requires asking the jury whether the defendant 'articulated' a reason. That could fail a charge that addresses the RIF and pretext without the burden-shifting language. |
| Arguable or unverified concerns: item 4 | arguable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json#L85) | problematic | The record contains no plaintiff pretrial brief. The only reference is the order noting that plaintiff's summary-judgment briefing 'at times invoked' a motivating-factor framework. The PASS condition requires the memo to identify a request in 'plaintiff's pretrial brief'. That rewards inventing a filing and puts accurate memos at risk. I rate it higher than Sol does because the criterion's premise is not in the record. |

## Blind pass and what changed

Upgraded C-018 from arguable to problematic, now a separate finding (O4). This pass I read Wing v. Anchor Media, which holds that absent fraud in the inducement a disclaimer bars a handbook contract 'irrespective of the terms of the handbook'. So the SJ order reverses both cases it cites, and the defendant's own Proposed Instruction No. 9 is the kind of instruction C-018 fails. Upgraded C-019 from mostly sound to arguable (O5), because its 'always negate' FAIL trigger comes close to Wing's actual rule. Downgraded C-007/C-008 from problematic to arguable (O6): the court's order and the defendant's concession make the contributing-factor instruction what a drafter following the record would write, and my search for Ohio authority was not exhaustive. Adopted C-042 as arguable from Sol (O8), based on my reading of Brown v. Packaging Corp. Dropped blind O7 (memo-audience criteria C-002/C-004/C-013/C-022). On reflection, a defense cover memo that flags where the proposals depart from the client's flawed pretrial brief is implicit in the task; those criteria are demanding, not hidden. Removed C-033 from the C-050 finding. Kept C-009 as problematic, one level above Sol's rating. Rated C-015 and C-039 not defects, contrary to Sol's grouping. Verified OAC 3745-55 is authorized by ORC 3734.12, which strengthens the (A)(2) point in O7.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-044): Requires citations to 'Sixth Circuit Pattern Jury Instructions (Civil)', which do not exist
- **O2** (problematic; C-009): Requires the memo to identify a mixed-motive request in 'plaintiff's pretrial brief', which is not in the record
- **O3** (problematic; C-043): Demands a good-faith-belief protected-activity instruction although the court already found protected activity as a matter of law
- **O4** (problematic; C-007, C-008): Requires a 'contributing factor' causation standard for ORC 4113.52, a standard Ohio law does not supply
- **O5** (arguable; C-018, C-019): SJ order cites Karnes for the opposite of its holding on handbook disclaimers; C-018 penalizes the defense's strongest position
- **O6** (arguable; C-014, C-040): States ORC 4113.52's internal-reporting prerequisite incompletely: omits the written report and 24-hour window, and ignores (A)(2)
- **O7** (arguable; C-002, C-004, C-013, C-022, C-009): Memo criteria assume an internal audience that critiques the client's own filed brief; the one-line instructions never say this
- **O8** (arguable; C-011, C-013): Treats McKennon's remedies-only rule as governing all claims, including the Ohio implied-contract claim
- **O9** (arguable; C-050, C-033): Requires a separate jury damages figure for the Ohio whistleblower claim, though 4113.52(E) remedies are court-ordered

## Coverage and limits

Blind pass: I read task.json (the instructions and all 57 criteria), the judge prompt, the solver system prompt, and all five supplied documents in full: the summary-judgment order, the defendant's pretrial brief, the handbook excerpts, the Felton deposition excerpt, and the Cavender email. I read these primary sources in this session: the ORC 4113.52 text on codes.ohio.gov (current version effective March 2024; the substance of former (A)(1)(a) and (A)(2) is unchanged), Karnes v. Doctors Hospital in full, and passages of Contreras v. Ferro, Brown v. Packaging Corp. and Bennett v. Columbiana Cty. Coroner. I also checked the Sixth Circuit's pattern-instructions page and a law-library guide. I did not read Nassar, McKennon, Kolstad, Ford Motor v. EEOC, Mers, Wing, 42 U.S.C. 1981a, or any Ohio authority on after-acquired evidence in contract claims; propositions resting on those are marked unverified. I did not verify that OAC 3745-55 was promulgated under ORC Chapter 3734, or that the alleged disposal would be a criminal offense. The record has minor inconsistencies: the acknowledgment date (Sept. 14 vs. 15); the position she was hired into (Account Manager vs. Senior Account Manager); the length of Felton's vacation; the SJ order's wording of Felton's quote; and the SJ order calling the Cavender email quoted 'in its entirety' when the exhibit is longer. None of these changes what a correct answer is, so none is raised as a finding.

Reconciliation: In the blind pass I read all 57 criteria, the instructions, the judge and solver prompts, and all five documents in full. This pass I re-read the SJ order's Count II and Count IV sections, the defendant's brief sections on 4113.52 and the handbook, and the Felton deposition on written records, plus Sol's full report and index entry. Primary sources read this session: ORC 4113.52 (2006 version) via codes.ohio.gov; the OAC 3745-55 chapter page, showing authority under ORC 3734.12; Wing v. Anchor Media and Karnes v. Doctors Hospital (disclaimer passages); and Brown v. Packaging Corp. (6th Cir. 2003), on McDonnell Douglas charges. Not verified: McKennon, Contreras (re-read only in the blind pass), any Ohio authority on after-acquired evidence in contract claims, and how Ohio courts divide 4113.52(E) remedies between judge and jury.

# Claude Opus 5.5 audit: Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 33. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric follows the planted errors and most criteria have solid record support. Examples:
- SignalSift's dismissal
- the novelty requirement
- the omitted use/disclosure prong
- 'adequate' vs 'reasonable'
- the damages election
- the narrowed contract claim
- the withdrawn mitigation defense
- the conflict with the sanctions order
- 'particular skepticism'

Two criteria state wrong Georgia law. C-020 requires a contract-vs-business-relations distinction on wrongful conduct that Georgia courts reject. C-016 attributes a nonexistent 'actual fraud and specific intent' standard to §51-12-5.1. C-023's blanket rule on intentional torts is debatable after Couch. C-027 misnumbers and misdescribes the Eleventh Circuit pattern instruction. Several gating criteria add presentation demands the one-line instructions never make: C-029, C-032 and C-033. The record also carries an unflagged caption error (Ridgemont vs Oakvale). Under all-pass scoring, these defects make it likely that a strong memo is zeroed out.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L170) | C-020 requires a Georgia contract-vs-business-relations distinction on wrongful conduct that Georgia courts reject | revised |
| [O2](#o2) | arguable | legal_error | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L162) | C-019 treats No. 27's wrongful-conduct element as plainly improper, though Georgia law includes a version of it | blind |
| [O3](#o3) | problematic | legal_error | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L138) | C-016 attributes 'actual fraud and specific intent to injure' to O.C.G.A. §51-12-5.1, which contains no such standard | adopted_after_reading_sol |
| [O4](#o4) | arguable | legal_error | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L194) | C-023's blanket rule that comparative fault never applies to intentional torts in Georgia is overbroad after Couch | adopted_after_reading_sol |
| [O5](#o5) | arguable | legal_error | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L226) | C-027 cites the wrong pattern number and misdescribes the Eleventh Circuit pattern as neutral on compensation | blind |
| [O6](#o6) | arguable | document_defect | [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L250) | All captions and the agreement's signature block name 'Ridgemont Technologies' while the body text says Oakvale | blind |
| [O7](#o7) | arguable | ambiguous_or_unjudgeable | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L242) | C-029 demands a list of acceptable instructions an issues memo need not include, and its PASS/FAIL thresholds leave a gap | revised |
| [O8](#o8) | arguable | ambiguous_or_unjudgeable | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L266) | C-032 counts prejudice analysis against '12 planted issues' that the judge cannot see | revised |
| [O9](#o9) | arguable | unrequested_requirement | [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L274) | C-033 requires severity tiers ('flatly wrong' vs 'subtly misleading') that the instructions never request | blind |
| [O10](#o10) | arguable | ambiguous_or_unjudgeable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L66) | C-007 ties the harm from No. 16's missing use/disclosure prong only to Axial, though it hurts the case against Voss most | blind |

<a id="o1"></a>
### O1. C-020 requires a Georgia contract-vs-business-relations distinction on wrongful conduct that Georgia courts reject

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L170)

C-020 passes a memo only if it says interference with an existing contract needs no wrongful act beyond knowing inducement, and that the wrongful-act element belongs only to interference with business relations. The Georgia Court of Appeals holds that claims for interference with contractual relations, business relations or potential business relations all share the element 'improper action or wrongful conduct by the defendant without privilege' (conduct wrongful in itself). The supplied SJ order drops that element from its list, which is the likely source of the rubric's rule, but it never states the distinction C-020 demands. A memo that states Georgia law accurately fails C-020. The sound objections to No. 27 are different: its 'separate from the interference itself' framing, its departure from the SJ order's elements, and the point that inducing misuse of confidential information is itself improper conduct.

Evidence:
- `C-020`: “tortious interference with an existing contract does not require a separately/independently wrongful act ... the 'independently wrongful act' element applies to the distinct tort of tortious interference with business relations”
- `summary-judgment-order.docx.txt`: “(1) the existence of a valid contract between the plaintiff and a third party; (2) the defendant's knowledge of the contract; (3) the defendant's intentional inducement of the third party to breach the contract; and (4) damages”

Authorities (✓ = primary text checked in the auditing session):
- Fortson v. Brown, 302 Ga. App. 89 (2010) (unverified): Claims for interference with contractual relations, business relations or potential business relations share the element of improper action or wrongful conduct without privilege.
- Tribeca Homes, LLC v. Marathon Inv. Corp., 322 Ga. App. 596 (2013) (unverified): The same four elements apply across the tortious-interference variants.

Suggested fix: Reword C-020 to pass a memo that objects to No. 27 on any of these grounds: inconsistency with the SJ order's elements, the misframed 'separate from the interference itself' requirement, or that inducing use of confidential information is itself wrongful conduct. Drop the contract-vs-business-relations distinction, and correct the SJ order's element list.

Related GPT-6 Sol findings: F1.

<a id="o2"></a>
### O2. C-019 treats No. 27's wrongful-conduct element as plainly improper, though Georgia law includes a version of it

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L162)

Georgia requires improper or wrongful conduct without privilege for interference with a contract. No. 27's element 3 is therefore close to Georgia law. Its real faults are the 'separate from the interference itself' framing and the omitted privilege element. A careful memo might call element 3 substantially correct and object only to its phrasing, or might argue the element is easily met because Axial induced use of confidential information. Either memo could fail C-019. The criterion has record support, because the SJ order's element list omits the element, so a law-of-the-case objection is defensible.

Evidence:
- `defense-proposed-jury-instructions.docx.txt`: “Axial Systems Corp. committed an independently wrongful act, separate from the interference itself, that induced or caused Dr. Voss to breach the contract”
- `C-019`: “improperly requires Oakvale to prove Axial committed an 'independently wrongful act' separate from the interference itself”

Authorities (✓ = primary text checked in the auditing session):
- Fortson v. Brown, 302 Ga. App. 89 (2010) (unverified): Improper conduct includes wrongful acts such as use of confidential information and applies to contractual-relations claims.

Suggested fix: Pass a memo that objects to No. 27's framing or its departure from the SJ order, including a memo that concedes some wrongful-conduct element exists but argues it is misstated or satisfied.

Related GPT-6 Sol findings: F1.

<a id="o3"></a>
### O3. C-016 attributes 'actual fraud and specific intent to injure' to O.C.G.A. §51-12-5.1, which contains no such standard

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L138)

C-016 rightly requires the §10-1-763(b) 'willful and malicious misappropriation' standard. It then says 'actual fraud and specific intent to injure' is 'found in the general Georgia punitive damages statute'. In fact §51-12-5.1(b) allows punitive damages on clear and convincing proof of 'willful misconduct, malice, fraud, wantonness, oppression, or ... conscious indifference'. 'Specific intent to cause harm' appears only in (f), as an exception to the cap, and 'actual fraud' appears in neither. Measured against the real (b) standard, 'willful and malicious' is not clearly 'lower'. A memo that states the statute accurately, for example that No. 32 invents a conjunctive standard found in neither statute, risks failing a judge who reads the PASS text literally. Meanwhile the criterion rewards the plaintiff brief's muddled attribution.

Evidence:
- `C-016`: “a different (and lower) standard than 'actual fraud and specific intent to injure' found in the general Georgia punitive damages statute (O.C.G.A. § 51-12-5.1)”
- `plaintiff-trial-brief-damages.docx.txt`: “requires proof of "wilful misconduct, malice, fraud, wantonness, oppression, or that entire want of care which would raise the presumption of a conscious indifference to consequences." O.C.G.A. § 51-12-5.1(b)”

Authorities (✓ = primary text checked in the auditing session):
- Reid v. Morris, 309 Ga. 230 (2020) (quoting O.C.G.A. § 51-12-5.1(b), (f)) (✓): Section 51-12-5.1(b) lists alternative grounds proven by clear and convincing evidence. 'Specific intent to cause harm' appears in (f) only as a cap exception, and 'actual fraud' does not appear.

Suggested fix: Require the §10-1-763(b) 'willful and malicious' standard and an objection that No. 32's 'actual fraud and specific intent' conjunction is wrong. Remove the claim that the general statute contains that conjunction, and the 'lower' comparison.

Related GPT-6 Sol findings: F3.

<a id="o4"></a>
### O4. C-023's blanket rule that comparative fault never applies to intentional torts in Georgia is overbroad after Couch

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L194)

C-023 requires the memo to say comparative fault does not apply to intentional torts under Georgia law. That was the common-law rule, and §51-11-7, which No. 29 cites, concerns avoiding consequences of the defendant's 'negligence'. But the Georgia Supreme Court holds that 'fault' in the apportionment statute §51-12-33 'encompasses intentional torts', and Alston & Bird extended apportionment to claims for injury to property. Whether a plaintiff's own fault can reduce recovery against an intentional tortfeasor under §51-12-33(a) is therefore at least unsettled. A careful memo might rest the objection to No. 29 on the withdrawn mitigation defense, the lack of any pleaded apportionment defense, and §51-11-7 not fitting. By hedging the blanket proposition, it could fail C-023.

Evidence:
- `C-023`: “comparative fault does not apply to intentional tort claims (such as misappropriation or tortious interference) under Georgia law”
- `pretrial-conference-minutes.docx.txt`: “Defendants may not raise failure to mitigate at any stage of the trial proceedings, including in proposed jury instructions or closing arguments.”

Authorities (✓ = primary text checked in the auditing session):
- Welch v. Pappas Restaurants, Inc. (Ga. June 29, 2023) (quoting Couch v. Red Roof Inns, 291 Ga. 359, 365 (2012)) (✓): "'fault,' as used in OCGA § 51-12-33, encompasses intentional torts."

Suggested fix: Pass a memo that explains why No. 29's reduction is improper here (withdrawn mitigation defense, §51-11-7 inapplicable to intentional conduct, no pleaded apportionment) without requiring the categorical intentional-tort statement.

Related GPT-6 Sol findings: F2.

<a id="o5"></a>
### O5. C-027 cites the wrong pattern number and misdescribes the Eleventh Circuit pattern as neutral on compensation

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L226)

The Eleventh Circuit places its expert instructions at 3.6.1 and 3.6.2. The '3.5' comes from the defense's own citation, and 3.5 concerns impeachment. The general expert instruction does not mention fees. The fee instruction directs caution where court testimony is regular and a significant part of the expert's income. C-027 says the pattern 'allows consideration of compensation as one factor without directing skepticism'. A memo that describes the pattern accurately, saying caution is allowed only on that factual predicate and applied even-handedly to both sides' experts, fits the criterion's description awkwardly. The 'or equivalent / correct neutral standard' fallback will pass most competent memos.

Evidence:
- `C-027`: “the proper, neutral instruction on expert witness credibility that allows consideration of compensation as one factor without directing skepticism”
- `defense-proposed-jury-instructions.docx.txt`: “You should view her testimony with particular skepticism given her financial relationship with the plaintiff. ... Authority: Eleventh Circuit Pattern Jury Instruction 3.5.”

Authorities (✓ = primary text checked in the auditing session):
- Eleventh Circuit Pattern Jury Instructions (Civil) §§ 3.6.1–3.6.2 (unverified): The general expert instruction does not mention fees. The fee instruction permits caution where court testimony is regular and a significant part of the expert's income.

Suggested fix: Pass any memo that objects to singling out one party's expert and invokes the pattern expert instructions (3.6.1/3.6.2) or an even-handed standard. Drop the characterization of the pattern as silent on caution.

Related GPT-6 Sol findings: F4.

<a id="o6"></a>
### O6. All captions and the agreement's signature block name 'Ridgemont Technologies' while the body text says Oakvale

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L250)

All six documents caption the plaintiff as 'RIDGEMONT TECHNOLOGIES, INC.', and the agreement's signature block also says Ridgemont. The body text of every document says Oakvale. C-030 fails a memo whose parties are 'materially incorrect'. A solver that follows the caption, or treats the discrepancy as unresolved, risks failing, and flagging the conflict earns nothing. The record has other inconsistencies:
- Litigation hold: October 14, 2022 in the SJ order, April 2023 in the sanctions order.
- Confidentiality clause: §5(a) in the SJ order, §4.1 in the agreement.
- Sanctions order docket number: Dkt. 117 vs. Dkt. 142.
- Charge conference and trial dates differ across documents.
These mostly add noise, but they can affect C-018 and C-025.

Evidence:
- `defense-proposed-jury-instructions.docx.txt`: “**RIDGEMONT TECHNOLOGIES, INC.,** ... Plaintiff,”
- `voss-employment-agreement.docx.txt`: “by and between Oakvale Technologies, Inc. ... **RIDGEMONT TECHNOLOGIES, INC.** By:”

Suggested fix: Fix the captions and signature block to read Oakvale and reconcile the dates and section numbers, or make C-030 accept a memo that flags the caption discrepancy.

Related GPT-6 Sol findings: F5.

<a id="o7"></a>
### O7. C-029 demands a list of acceptable instructions an issues memo need not include, and its PASS/FAIL thresholds leave a gap

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L242)

An 'issues memo' is organized around problems. Noting which instructions are acceptable is helpful but not clearly implicit in the request, and C-029 fails a memo that covers only the objectionable instructions. The thresholds also mismatch: PASS requires at least two approved instructions, while FAIL covers only a memo that approves none, so a memo approving exactly one falls between them. One of the examples is also doubtful. No. 15 cites Penalty Kick at '318 Ga. App. 586 (2012)', but the plaintiff's brief cites the case as 318 F.3d 1284 (11th Cir. 2003), so a careful reviewer might flag No. 15's authority rather than approve it.

Evidence:
- `C-029`: “PASS if the memo affirmatively identifies at least two defense proposed instructions as proper ... FAIL if the memo does not identify any instructions as proper or unobjectionable.”
- `defense-proposed-jury-instructions.docx.txt`: “*Penalty Kick Mgmt. Ltd. v. Coca Cola Co.*, 318 Ga. App. 586 (2012)”

Suggested fix: Align the PASS and FAIL thresholds, and either make C-029 non-gating or have the instructions ask the solver to note which instructions are acceptable.

Related GPT-6 Sol findings: F6.

<a id="o8"></a>
### O8. C-032 counts prejudice analysis against '12 planted issues' that the judge cannot see

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L266)

C-032 requires prejudice analysis for 'at least 8 of the 12 planted issues that are identified'. The judge has no list of planted issues. It cannot tell which issues count, or how to score a memo that raises issues outside the hidden list or finds fewer than 12. A per-issue prejudice discussion is a common practice but was not requested. A memo that identifies each error, gives the correct law and proposes replacement language could still fail.

Evidence:
- `C-032`: “PASS if the memo includes a description of potential prejudice to Oakvale for at least 8 of the 12 planted issues that are identified.”
- `task.json instructions`: “Review the defense's proposed jury instructions against the court's prior orders and case documents, and prepare an issues memo.”

Suggested fix: List the 12 instruction numbers in the criterion, or restate it as 'explains the practical impact on Oakvale for most identified issues'.

Related GPT-6 Sol findings: F9.

<a id="o9"></a>
### O9. C-033 requires severity tiers ('flatly wrong' vs 'subtly misleading') that the instructions never request

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L274)

The instructions ask only for an issues memo. Sorting errors into severity levels is a stylistic choice, not a standard component of an objections memo. A memo that treats every listed instruction as objectionable and gives the basis and replacement language for each would fail C-033 despite being correct. The bar is low, but under all-pass scoring this one criterion can still zero out a sound answer.

Evidence:
- `C-033`: “FAIL if all identified issues are treated with identical severity without any differentiation.”
- `task.json instructions`: “prepare an issues memo”

Suggested fix: Drop C-033, or make it a non-gating quality criterion.

Related GPT-6 Sol findings: F9.

<a id="o10"></a>
### O10. C-007 ties the harm from No. 16's missing use/disclosure prong only to Axial, though it hurts the case against Voss most

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L66)

Voss obtained the information lawfully as an employee, so his liability depends mainly on the use/disclosure prong of §10-1-761(2). Axial remains reachable under the acquisition prong, because it acquired the information from Voss knowing of his duty of secrecy. A memo that explains the omission guts the claim against Voss, or against 'defendants' generally, without naming Axial could fail C-007's Axial-specific wording.

Evidence:
- `C-007`: “FAIL if the memo does not connect the omission to the impact on Oakvale's case theory against Axial.”

Suggested fix: Pass a memo that explains the omission removes Oakvale's use/disclosure theory against either or both defendants.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L162) (arguable), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L170) (problematic) | mixed | I agree that Georgia puts 'improper action or wrongful conduct without privilege' into contract-interference claims as well (Fortson, Rowell, Tribeca Homes). C-020 therefore requires a false contract-vs-business-relations rule. C-019 is only arguable. No. 27's 'separate from the interference itself' framing is objectionable, and the SJ order's four-element list supports flagging it. A memo that calls element 3 substantially correct Georgia law would still fail C-019. |
| F2 | confirmed | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L194) | arguable | Before tort reform, Georgia treated comparative negligence as no defense to intentional torts. Section 51-11-7, which No. 29 cites, speaks of the defendant's negligence. Couch, as quoted in Welch v. Pappas (Ga. 2023), holds that 'fault' in §51-12-33 encompasses intentional torts, so the blanket rule is at least unsettled under statutory apportionment. I found no case applying plaintiff fault against an intentional tortfeasor. Overbroad and debatable, not clearly wrong. |
| F3 | confirmed | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L138) | problematic | Reid v. Morris (Ga. 2020) quotes §51-12-5.1. Under (b), clear and convincing proof of 'willful misconduct, malice, fraud, wantonness, oppression, or ... conscious indifference' supports punitive damages. 'Specific intent to cause harm' appears only in (f), as an exception to the cap, and 'actual fraud' appears in neither. C-016 attributes the defense's conjunctive standard to the general statute, which is wrong law, and it may fail a memo that states the statute accurately. |
| F4 | confirmed | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L226) | arguable | The Eleventh Circuit places its expert instructions at 3.6.1 and 3.6.2, not 3.5. The general instruction does not mention fees. The fee instruction allows a caution when testimony fees are regular and a significant part of the expert's income. C-027 misdescribes the pattern, but 'or equivalent / correct neutral standard' will pass most competent memos, so the risk is limited. |
| F5 | confirmed | [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L250) | arguable | The captions and the agreement's signature block say RIDGEMONT TECHNOLOGIES, INC., while every body text says Oakvale. Most memos will say Oakvale, but a memo that follows the caption, or treats the discrepancy as unresolved, risks failing, and the rubric gives no credit for flagging it. This is a real document defect with moderate grading impact. |
| F6 | confirmed | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L242) | arguable | The PASS/FAIL gap is real: PASS needs at least two approved instructions, while FAIL covers only 'any', so a memo approving exactly one falls between them. The criterion also demands a list of acceptable instructions that an 'issues memo' request does not clearly require. Both points are defensible but debatable, so arguable, not confirmed. |
| F7 | arguable | [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L90), [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L98) | not_a_defect | No. 13 uses 'reasonable' in its first sentence. The operative sentence then says 'if ... inadequate ... you must find that category is not a trade secret' and omits 'under the circumstances'. Flagging 'inadequate' as a departure from the statutory standard is exactly what a competent memo does. C-011's totality / not-perfect-security point is the natural companion argument. Demanding, not defective. |
| F8 | unverified | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L122) | not_a_defect | The plaintiff's trial brief, which is in the record, expressly makes this Rule 48(b) point. The proposition that jurors need not agree unanimously on the theory behind a damages figure, as opposed to the verdict, is a reasonable statement of federal practice. A careful reviewer of the case documents would be expected to raise it. It is a narrow sub-point, but not a defect. |
| F9 | arguable | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L266), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L274) | arguable | The instructions ask only for an issues memo. C-032 counts prejudice analysis against '12 planted issues' that the judge cannot see. C-033 requires severity tiers. Both are presentation preferences that can zero out a substantively complete memo under all-pass scoring, but many good memos would satisfy them. |

## Blind pass and what changed

- Adopted from Sol F3 (C-016), rated problematic. I read §51-12-5.1(b) and (f) as quoted in Reid v. Morris (Ga. 2020). The statute has no conjunctive 'actual fraud and specific intent' standard: specific intent to harm appears only in (f), as a cap exception, and 'actual fraud' does not appear. My blind pass had left this unverified.
- Adopted from Sol F2 (C-023), rated arguable rather than confirmed. My blind pass treated C-023 as supported by the pre-tort-reform cases. Welch v. Pappas (2023), quoting Couch, confirms that 'fault' in §51-12-33 encompasses intentional torts, so the blanket rule is at least unsettled. I found no case holding that plaintiff fault reduces recovery against an intentional tortfeasor, so it is not clearly wrong.
- Merged Sol F6's PASS/FAIL threshold gap into my C-029 finding (O7).
- Dropped C-003 from the old O3. Explaining why including a dismissed claim hurts Oakvale is inherent in objecting to it, so C-003 is not a hidden requirement. C-032 remains, as O8.
- Rejected Sol F7 (C-010, C-011) and F8 (C-014) as not defects. Flagging 'inadequate' and the missing 'under the circumstances' language is the natural objection to No. 13. The plaintiff's brief expressly makes the Rule 48(b) point that C-014 requires.
- Softened C-020 slightly (O1) to note that the SJ order's incomplete element list is the likely source of the error. It stays problematic.
- Renumbered all findings.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-020): C-020 requires a Georgia contract-vs-business-relations distinction that Georgia courts do not draw
- **O2** (arguable; C-019): C-019 treats No. 27's wrongful-conduct element as plainly improper, but Georgia law includes a version of it
- **O3** (arguable; C-032, C-003): C-032 counts against '12 planted issues' the judge cannot see, and prejudice analysis was not requested
- **O4** (arguable; C-027): C-027 misdescribes the Eleventh Circuit pattern expert instruction as neutral on compensation
- **O5** (arguable; C-030, C-018): Every caption names 'Ridgemont Technologies' as plaintiff while the text says Oakvale; other record facts conflict
- **O6** (arguable; C-033): C-033 requires severity tiers ('flatly wrong' vs 'subtly misleading') that the instructions never ask for
- **O7** (arguable; C-029): C-029 requires naming at least two instructions as unobjectionable, which an issues memo need not do
- **O8** (arguable; C-007): C-007 ties the harm from No. 16's missing use/disclosure prong only to Axial, though Voss is the defendant it hurts most

## Coverage and limits

Blind pass: I read all six documents in full: the defense proposed instructions, the SJ order, the sanctions order, the pretrial minutes, the plaintiff's damages trial brief, and the Employment Agreement (§4 and signature block closely). I checked every criterion against the record. CourtListener checks, read in this session: (1) Georgia tortious-interference elements in Fortson v. Brown, Rowell v. Phoebe Putney and Tribeca Homes; (2) Georgia authority that comparative or contributory negligence is no defense to an intentional tort (McEachern v. Muldovan, Soundara), which supports C-023; (3) AcryliCon v. Silikal (11th Cir. 2021), which confirms that §10-1-763(b) exemplary damages for 'willful and malicious misappropriation' are awarded at the district court's discretion; (4) the 11th Cir. civil pattern expert instructions, but only as reproduced in a 2016 S.D. Fla. filing, not the official publication. WebSearch hit its spend limit and Justia returned 403, so I could not read the primary text of O.C.G.A. §§10-1-761, 10-1-763 or 51-12-5.1. Two points are therefore unverified: whether 'actual fraud' appears anywhere in §51-12-5.1, which C-016 attributes to it and the plaintiff's brief echoes; and whether Georgia's §10-1-761(4)(A) omits the word 'independent', which C-005 uses. I also did not verify the current numbering of the 11th Cir. pattern edition.

Reconciliation: I reviewed all 33 criteria and all 9 Sol findings, and re-read the relevant passages of all six documents: defense Instructions 13, 27, 29–32, the SJ order's tortious-interference and disposition sections, the plaintiff brief's unanimity and punitive sections, and the pretrial minutes. Legal checks run on CourtListener in this session:
- Reid v. Morris (Ga. 2020), for the text of §51-12-5.1(b) and (f): verified.
- Welch v. Pappas (Ga. 2023), quoting Couch that §51-12-33 'fault' encompasses intentional torts: verified.
- I searched for, but did not find, direct authority on whether plaintiff fault reduces recovery against an intentional tortfeasor after Couch.
The Georgia tortious-interference cases (Fortson, Rowell, Tribeca) and the Eleventh Circuit pattern numbering were checked in the blind pass, not re-read here, so they are marked unverified.

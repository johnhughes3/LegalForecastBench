# Claude Opus 5.5 audit: Research Corporate Veil Piercing Standards Across Target Jurisdictions — In-House Legal Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 65. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly sound, record-tied fact and issue checks. Its main defects come from adopting legal errors in the Birchfield preliminary assessment. The most serious is C-036, which requires advising Cascade to argue for Delaware law even though TBOC §§ 1.102/1.104 point to Ohio law, Pryor's state of formation. C-023 states Ohio's second prong in the form Dombroski rejected. C-003 labels $4.2M of retained earnings as equity, against a balance sheet showing $21.7M. Several criteria are debatable: the Delaware-strictest cluster (C-025, C-026, C-049), C-033's 'worsen' logic, which conflicts with C-045, C-021's understatement and misdating of SSP Partners, C-019's wrong statute section, and C-008's gross-versus-net total. Under the all-pass metric, C-036, C-023 and C-003 alone could zero out a legally correct, careful memo.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L300) | C-036 requires advocating Delaware law, but TBOC §§ 1.102/1.104 send the question of piercing Pryor's veil to Ohio law | blind |
| [O2](#o2) | problematic | source_conflict | [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L36) | C-003 labels $4.2M of retained earnings as 'equity'; the balance sheet shows $21.7M total member's equity (D/E 1.90x) | blind |
| [O3](#o3) | problematic | legal_error | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L196) | C-023 states Ohio's second prong as a 'wrongful or unjust act,' which Dombroski rejected in 2008 | blind |
| [O4](#o4) | arguable | internal_inconsistency | [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L276) | C-033 says recharacterizing the debt as equity 'worsens' undercapitalization; the record and C-045 treat conversion as raising equity | revised |
| [O5](#o5) | arguable | legal_error | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L212), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L220), [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L404) | C-025, C-026 and C-049 require Delaware to be strictly the most demanding and lowest-risk state; after Dombroski, Ohio is at least as strict | blind |
| [O6](#o6) | arguable | legal_error | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L164) | C-019 cites R.C. 1706.29 (distributions) for the LLC formalities rule; the correct section is 1706.26, which is current law | revised |
| [O7](#o7) | arguable | legal_error | [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L180) | C-021 credits mere 'skepticism' of SBE and misdates SSP Partners; the Texas Supreme Court held SBE cannot impose liability (2008) | revised |
| [O8](#o8) | arguable | ambiguous_or_unjudgeable | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L76) | C-008 fixes 'total net extraction' at $31.6M; the record also supports $34.3M including interest, or a lower net flow | blind |
| [O9](#o9) | arguable | document_defect | — | Pryor's workbook deducts the $12.6M distribution both before and after net income, so retained earnings don't roll forward | revised |
| [O10](#o10) | arguable | document_defect | — | The IEPA complaint is anachronistic and has a thin Illinois nexus to storage at an Ohio plant | revised |

<a id="o1"></a>
### O1. C-036 requires advocating Delaware law, but TBOC §§ 1.102/1.104 send the question of piercing Pryor's veil to Ohio law

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L300)

The veil at issue is Pryor's, and Pryor is an Ohio LLC. Under TBOC § 1.104, a member's liability for the entity's obligations is governed by the law that governs the entity. Under § 1.102, that is the law of the jurisdiction where the entity was formed, which here is Ohio. Delaware, where Cascade is incorporated, has no real claim to govern. C-036 takes over Birchfield's theory that the claim 'targets Cascade's corporate separateness,' and its PASS requires advising that Delaware law is the one Cascade should favor. A memo that correctly concludes Ohio law governs, and tells Cascade to push Ohio over Texas, may fail unless it also calls Delaware the preferred law. A memo that repeats outside counsel's weak Delaware theory passes. So the criterion rewards the wrong choice-of-law advice.

Evidence:
- `task.json C-036`: “PASS if the memorandum advises that Delaware law is the most favorable to Cascade for veil piercing purposes”
- `birchfield-novak-preliminary-assessment.docx.txt`: “For Cascade, a Delaware corporation, the doctrine could point to Delaware law --- particularly where the veil piercing claim targets Cascade's corporate separateness”

Authorities (✓ = primary text checked in the auditing session):
- Tex. Bus. Orgs. Code § 1.104 (✓): The law of the jurisdiction that governs an entity applies to an owner's or member's liability, in that capacity, for the entity's obligations.
- Tex. Bus. Orgs. Code § 1.102 (✓): For an entity formed by filing with a foreign governmental authority, that jurisdiction's law governs its formation and internal affairs.

Suggested fix: PASS if the memo reasons to a law Cascade should advocate. Accept Ohio (Pryor's state of formation under TBOC §§ 1.102/1.104). Do not require Delaware; noting that Delaware's standard is favorable but unlikely to apply is fine.

Related GPT-6 Sol findings: F06.

<a id="o2"></a>
### O2. C-003 labels $4.2M of retained earnings as 'equity'; the balance sheet shows $21.7M total member's equity (D/E 1.90x)

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L36)

C-003 requires a ratio of about 9.81:1, described as '$41.2M debt / $4.2M equity,' and fails any answer off by more than 0.5. The workbook shows that 9.81x is IC debt divided by retained earnings. It separately reports total member's equity of $21.7M and a D/E of 1.90x. A careful analyst who reports the true D/E (1.90:1) and treats 9.81 as a debt-to-retained-earnings metric risks failing. The criterion also states a wrong fact, since $4.2M is not Pryor's equity. Many memos will repeat the 9.81 figure that the narrative documents use and pass, but the criterion is built on the mislabel.

Evidence:
- `pryor-financial-summary-fy2020-fy2024.xlsx.txt`: “A43="Debt-to-Equity (IC Debt / Total Member's Equity)" \| ... F43='1.90x'”
- `pryor-financial-summary-fy2020-fy2024.xlsx.txt`: “A37="Total Member's Equity" \| ... F37='21,700'”
- `task.json C-003`: “(or $41.2M debt / $4.2M equity). FAIL if the ratio is missing or materially incorrect (e.g., wrong by more than 0.5).”

Suggested fix: PASS for 9.81:1 described as IC debt to retained earnings, or 1.90:1 as IC debt to total member's equity. Remove the '$4.2M equity' label.

Related GPT-6 Sol findings: F01.

<a id="o3"></a>
### O3. C-023 states Ohio's second prong as a 'wrongful or unjust act,' which Dombroski rejected in 2008

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L196)

Dombroski modified Belvedere. Piercing now requires control exercised 'to commit fraud, an illegal act, or a similarly unlawful act,' and the Court expressly answered 'in the negative' the question whether unjust or inequitable acts suffice. Dombroski was a tort case, so it applies directly to the Delgado product-liability claims. C-023 uses the superseded 'wrongful or unjust act' wording and cites only Belvedere, adopting Birchfield's error. The result is that it rewards a memo that misstates Ohio law. A correct memo can pass only if the judge treats the narrower Dombroski prong as 'substantially equivalent,' and the criterion's own FAIL clause ('misstates the elements') could be turned against a memo that departs from the criterion's formulation.

Evidence:
- `task.json C-023`: “(1) control/domination, (2) wrongful or unjust act, and (3) proximate causation of injury”
- `birchfield-novak-preliminary-assessment.docx.txt`: “(2) that the control was used to commit a wrongful or unjust act”

Authorities (✓ = primary text checked in the auditing session):
- Dombroski v. WellPoint, Inc., 119 Ohio St.3d 506, 2008-Ohio-4827, syllabus and ¶2 (✓): The second Belvedere prong requires control exercised to commit fraud, an illegal act, or a similarly unlawful act; unjust or inequitable acts do not suffice.

Suggested fix: State element (2) as 'fraud, an illegal act, or a similarly unlawful act (Belvedere as modified by Dombroski)'. Treat 'unjust act' wording as a misstatement.

Related GPT-6 Sol findings: F03.

<a id="o4"></a>
### O4. C-033 says recharacterizing the debt as equity 'worsens' undercapitalization; the record and C-045 treat conversion as raising equity

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L276)

The GC summary and the workbook risk note say that recharacterizing the debt raises Pryor's equity to about $45.4M. The harm is that recharacterization is evidence of disregard for separateness. C-045 credits converting the intercompany debt to equity as a way to restore capitalization, which is also Birchfield's recommendation. A precise memo that says recharacterization improves the ratio but is adverse alter-ego evidence does not literally 'note this would worsen the undercapitalization analysis.' Two things make this arguable rather than problematic: petition ¶28 frames recharacterization as 'further evidencing ... artificial undercapitalization,' and the FAIL clause triggers only if recharacterization is not discussed.

Evidence:
- `cascade-corporate-structure-summary.docx.txt`: “Pryor's equity base would increase to approximately $45.4 million ... However, the recharacterization itself would constitute evidence of disregard for entity separateness”
- `birchfield-novak-preliminary-assessment.docx.txt`: “converting some or all of the $41.2 million intercompany debt to equity, which would simultaneously reduce the undercapitalization concern”
- `task.json C-033`: “notes this would worsen the undercapitalization analysis”

Suggested fix: PASS if the memo flags recharacterization risk and explains why it hurts Cascade: it is evidence of disregard for separateness, or it shows funding was disguised equity used to keep stated capital thin. Drop the 'worsen' requirement.

Related GPT-6 Sol findings: F02.

<a id="o5"></a>
### O5. C-025, C-026 and C-049 require Delaware to be strictly the most demanding and lowest-risk state; after Dombroski, Ohio is at least as strict

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L212), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L220), [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L404)

C-025 requires Delaware's standard to be called more demanding than all three other states. C-026 fails a memo that suggests any other state is more favorable. C-049 fails a memo that rates Delaware equal to any other state. As the record describes it, Delaware requires fraud 'or an overall element of injustice or unfairness.' Ohio after Dombroski requires fraud, an illegal act, or a similarly unlawful act and excludes merely unjust acts, and R.C. 1706.26 bars formalities failures as a ground for member liability. A competent memo could rate Delaware and Ohio as comparably strict, or rank Ohio as more protective for an LLC. And because Delaware likely does not govern (O1), a memo might decline to single it out. Delaware's general reputation makes the rubric's view defensible, which is why this is arguable.

Evidence:
- `task.json C-049`: “FAIL if Delaware is rated equal to or higher risk than Ohio, Texas, or Illinois.”
- `task.json C-026`: “suggests another jurisdiction is more favorable to Cascade for veil piercing defense”
- `birchfield-novak-preliminary-assessment.docx.txt`: “generally requiring a showing of fraud or something akin to fraud, coupled with an overall element of injustice or unfairness”

Authorities (✓ = primary text checked in the auditing session):
- Dombroski v. WellPoint, Inc., 2008-Ohio-4827, syllabus (✓): Ohio requires fraud, an illegal act, or a similarly unlawful act; unjust or inequitable acts are not enough.
- Ohio R.C. 1706.26 (✓): A failure to observe LLC formalities is not a factor in, or ground for, imposing liability on members.

Suggested fix: PASS if the memo places Delaware among the least risky standards, ties included. Accept a memo that notes Delaware is favorable but unlikely to govern.

Related GPT-6 Sol findings: F06.

<a id="o6"></a>
### O6. C-019 cites R.C. 1706.29 (distributions) for the LLC formalities rule; the correct section is 1706.26, which is current law

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L164)

C-019 points to 'O.R.C. § 1705.48 or § 1706.29 under the revised act' and says the statute 'historically did not require' formalities. Section 1706.29 governs distributions. The formalities rule is § 1706.26, which currently provides that a failure to observe formalities 'is not a factor to consider in, or a ground for, imposing liability on the members.' The substantive requirement is correct and the citation is a parenthetical example, so a correct memo will very likely pass. But the criterion states a wrong citation and understates the rule as historical.

Evidence:
- `task.json C-019`: “O.R.C. § 1705.48 or § 1706.29 under the revised act) historically did not require LLCs to observe the same formal corporate formalities”

Authorities (✓ = primary text checked in the auditing session):
- Ohio R.C. 1706.26 (✓): A failure to observe formalities is not a factor in, or ground for, imposing liability on members.
- Ohio R.C. 1706.29 (✓): Governs LLC distributions ('All members shall share equally in any distributions ...').

Suggested fix: Cite R.C. 1706.26 (and former 1705.48) and describe it as a current statutory bar.

Related GPT-6 Sol findings: F05.

<a id="o7"></a>
### O7. C-021 credits mere 'skepticism' of SBE and misdates SSP Partners; the Texas Supreme Court held SBE cannot impose liability (2008)

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L180)

SSP Partners, delivered November 14, 2008 (argued in 2007), held that 'the single business enterprise liability theory ... will not support the imposition of one corporation's obligations on another.' The Birchfield letter wrongly says the Court 'declined to definitively abolish' the theory. C-021 credits memos that describe only 'skepticism' or 'doubt,' so it rewards the record's understatement, and it gives the year as 2007. A correct memo that says SBE was rejected still satisfies 'limitation' and does not treat SBE as settled, so it would pass. The defect is rewarding incomplete law, not failing correct work.

Evidence:
- `task.json C-021`: “either by citing SSP Partners v. Gladstrong Investments (2007) or by accurately describing that the Texas Supreme Court has cast doubt on SBE”
- `birchfield-novak-preliminary-assessment.docx.txt`: “the Court declined to definitively abolish the SBE theory but expressed pronounced skepticism”

Authorities (✓ = primary text checked in the auditing session):
- SSP Partners v. Gladstrong Invs. (USA) Corp., 275 S.W.3d 444 (Tex. 2008) (✓): The single business enterprise liability theory will not support imposing one corporation's obligations on another; decided Nov. 14, 2008.

Suggested fix: PASS if the memo states that SSP Partners (2008) rejected SBE as a basis for imposing liability, with any remaining lower-court treatment noted. Correct the year.

Related GPT-6 Sol findings: F04.

<a id="o8"></a>
### O8. C-008 fixes 'total net extraction' at $31.6M; the record also supports $34.3M including interest, or a lower net flow

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L76)

The core rule, that the $5.3M and $12.6M are inside the $31.6M sweep and $49.5M is a double count, is sound. But C-008 calls $31.6M the 'total net extraction.' The Intercompany tab reports 34,278 transferred including interest and a lower net flow after Cascade's loan advances. Cash Management Agreement §5.1 ('In addition to the Cash Sweeps') and §5.2 ('included within, and not in addition to') also contradict each other. A literal judge could fail a memo that nets out the fees correctly but reports a different, correctly derived total.

Evidence:
- `pryor-financial-summary-fy2020-fy2024.xlsx.txt`: “A11='TOTAL CASH TRANSFERRED FROM PRYOR TO CASCADE' \| ... F11='34,278'”
- `intercompany-cash-management-agreement.docx.txt`: “the Management Fee Distribution is included within, and not in addition to, the Cash Sweep amounts”

Suggested fix: Label $31.6M as the gross sweep. PASS any memo that recognizes the overlap and does not present $49.5M.

Related GPT-6 Sol findings: F08.

<a id="o9"></a>
### O9. Pryor's workbook deducts the $12.6M distribution both before and after net income, so retained earnings don't roll forward

**Status:** arguable · **Category:** document_defect · **Criteria:** none

The P&L note says the management fee distribution is booked as an operating expense and already reduces net income to $16.8M. Yet the workbook and three narrative documents compute '$16.8M − $12.6M = $4.2M retained,' which deducts it a second time. FY2024 shows 'Current Year Net Income — Undistributed' of 14,000 alongside retained earnings that fall from 17,700 to 4,200. This confuses the capitalization figures underlying C-003 and C-009. A careful analyst who restates the figures could appear 'incorrect' to a literal judge, though C-059 ($16.8M) matches the reported P&L and is unlikely to be misgraded.

Evidence:
- `pryor-financial-summary-fy2020-fy2024.xlsx.txt`: “management fee distribution ($12.6M) and corporate services fee ($5.3M) are included as operating expenses above and reduce net income”
- `pryor-financial-summary-fy2020-fy2024.xlsx.txt`: “A36='Current Year Net Income — Undistributed' \| ... F36='14,000' \| G36='... FY2024 net income of $16.8M less $12.6M management fee distribution = $4.2M net retention'”

Suggested fix: Move the distribution below net income and make retained earnings roll forward. Otherwise accept memos that flag the inconsistency.

<a id="o10"></a>
### O10. The IEPA complaint is anachronistic and has a thin Illinois nexus to storage at an Ohio plant

**Status:** arguable · **Category:** document_defect · **Criteria:** none

The complaint is dated October 3, 2024 but pleads figures 'as of December 31, 2024.' It asserts Illinois permit jurisdiction over storage at a Canton, Ohio facility, resting on manifests received in Peoria. No criterion depends on either flaw: operator liability (C-037, C-038, C-041) is expressly pleaded in Count III, and C-058 accepts the action number. So I do not treat these criteria as defective. But a strong memo that challenges Illinois's authority over the Ohio storage counts gets no credit, and the record muddies which facts are operative.

Evidence:
- `iepa-enforcement-complaint.docx.txt`: “Jurisdiction over the storage violations at the Canton Facility is properly invoked under 415 ILCS 5/21(d) and (e)”
- `iepa-enforcement-complaint.docx.txt`: “at its manufacturing facility located in Canton, Ohio (the "Canton Facility")”

Suggested fix: Fix the date inconsistency and either relocate the storage facility or add a criterion crediting the jurisdictional defense.

Related GPT-6 Sol findings: F07.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F01 | confirmed | [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L36) | problematic | The workbook reports total member's equity of 21,700 (F37) and a D/E of 1.90x (F43). The 9.81x figure is IC debt divided by retained earnings of 4,200 (F42). C-003 calls $4.2M 'equity' and fails any ratio off by more than 0.5. So a memo that reports the balance-sheet D/E of 1.90:1 fails, and the criterion rests on a misstated fact. |
| F02 | confirmed | [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L276) | arguable | The GC summary says recharacterization would raise equity to about $45.4M, and C-045 credits converting the debt to equity as a remedy. That conflicts with 'worsen undercapitalization.' But petition ¶28 frames recharacterization as 'further evidencing ... artificial undercapitalization,' and the FAIL clause triggers only if recharacterization is not discussed. I rate it arguable, not confirmed. |
| F03 | confirmed | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L196) | problematic | I read Dombroski (2008-Ohio-4827) this session. At ¶2 and the syllabus, the second prong is limited to 'fraud, an illegal act, or a similarly unlawful act,' and the Court answers the unjust/inequitable question 'in the negative.' C-023 states the element as a 'wrongful or unjust act,' which is superseded law, and it rewards memos that repeat Birchfield's error. |
| F04 | confirmed | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L172) (not_a_defect), [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L180) (arguable) | mixed | I verified SSP Partners (Tex., delivered Nov. 14, 2008): 'we hold that the single business enterprise liability theory ... will not support the imposition of one corporation's obligations on another.' C-021 misdates the case (it was argued in 2007) and credits mere 'skepticism,' but a correct memo that says 'rejected' still satisfies 'limitation.' C-020 requires only discussing SBE, which the petition pleads. A memo that discusses SBE and calls it rejected passes. |
| F05 | confirmed | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L164) | arguable | I confirmed that R.C. 1706.29 governs distributions and 1706.26 holds the formalities rule, which is current law. The citation in C-019 is wrong and its 'historically' framing is off. But the operative requirement (discuss the Ohio LLC formalities defense) is correct and the citation sits in a parenthetical, so a correct memo will very likely pass. Arguable, not confirmed. |
| F06 | arguable | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L212) (arguable), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L220) (arguable), [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L300) (problematic), [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L404) (arguable), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L412) (not_a_defect) | mixed | C-036 affirmatively rewards advising Cascade to argue for Delaware law. Under TBOC §§ 1.102/1.104 (verified), Ohio law, as Pryor's state of formation, governs member liability, so C-036 is problematic. The Delaware-strictest rankings are debatable after Dombroski, so C-025, C-026 and C-049 are arguable. C-050 (Ohio or Texas rated high) fits the record's control, sweep and override facts. |
| F07 | arguable | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L308), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L316), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L340), [C-054](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L444) | not_a_defect | IEPA Count III expressly pleads direct operator liability, citing Bestfoods. C-038 accepts discussion of the parent-operator principle and does not require a RCRA holding. C-054 is a generic Illinois-analysis item that Count IV supports. The complaint's weak Illinois nexus to the Ohio storage is a record flaw, but none of these criteria depends on it, and a memo can challenge jurisdiction and still pass. |
| F08 | arguable | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json#L76) | arguable | The core rule (the fees sit inside the $31.6M sweep, so $49.5M double counts) is sound. But C-008 calls $31.6M the 'total net extraction,' while the Intercompany tab shows 34,278 transferred including interest and a lower net flow after loan advances. Cash Management Agreement §5.1 and §5.2 also conflict with each other. A literal judge could fail a correct alternative total. |

## Blind pass and what changed

1. Split blind O6: C-019 (the R.C. 1706.29 citation) is now O6, and C-021 (SSP Partners) is now O7. I read SSP Partners this session and confirmed it actually held that SBE cannot impose liability. So C-021's flaw is broader than the year: it credits the record's 'skepticism' understatement. That point comes from Sol F04; I still reject Sol's C-020 flag.
2. Revised C-033 (O4) to note two things: its tension with C-045, which credits debt-to-equity conversion, and petition ¶28's partial support for the 'worsening' framing. It stays arguable.
3. Removed C-052 from the Ohio-test finding (O3), because it carries no misstatement. Removed C-059 and C-009 from the financial document-defect finding (O9), which now has criteria [], because those figures match the reported workbook and are unlikely to be misgraded.
4. Removed C-037, C-055 and C-058 from the IEPA document-defect finding (O10, criteria []). Count III pleads operator liability expressly, and C-058 accepts the action number, so none of these criteria misgrades.
5. Rejected Sol F07 (C-037, C-038, C-041, C-054) and Sol's C-020 and C-050 flags as not defects.
6. Kept C-036 as problematic, where Sol has arguable. I re-verified TBOC §§ 1.102/1.104 this session.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-036): C-036 requires advising Cascade to argue for Delaware law, but Texas law points to Ohio law for piercing Pryor's veil
- **O2** (problematic; C-003): C-003 treats $4.2M of retained earnings as 'equity', but the balance sheet shows total member's equity of $21.7M (D/E 1.90x)
- **O3** (problematic; C-023, C-052): C-023 states Ohio's second element as a 'wrongful or unjust act', which the Ohio Supreme Court rejected in Dombroski
- **O4** (arguable; C-033): C-033 says recharacterizing the debt as equity would 'worsen' undercapitalization; the record says it would raise equity
- **O5** (arguable; C-025, C-026, C-049): Three criteria fix Delaware as strictly 'more demanding' than every other state; after Dombroski, Ohio is arguably as strict
- **O6** (arguable; C-019, C-021): Citation errors: Ohio's formalities rule is R.C. 1706.26, not 1706.29; SSP Partners was decided in 2008, not 2007
- **O7** (arguable; C-059, C-009, C-003): Pryor's financial statements don't reconcile: the distribution is deducted before net income and again after it
- **O8** (arguable; C-008): C-008 fixes 'total net extraction' at $31.6M, but the record also supports $34.3M (with interest) or $27.9M net
- **O9** (arguable; C-037, C-055, C-058): The IEPA record has jurisdiction and timing flaws: an Illinois agency pleads storage violations at an Ohio plant, citing year-end figures

## Coverage and limits

Blind pass: I read all 65 criteria and the instructions. Six documents were read in full: the corporate structure summary, the Birchfield & Novak preliminary assessment, the IEPA complaint, the insurance summary, the Orvis email chain, and the financial spreadsheet (every sheet). I searched the plaintiffs' petition and the cash management agreement for the facts the criteria rely on (single business enterprise pleading, overruling, damages, fee and sweep clauses, governing law) but did not read them end to end. Primary law I read this session: Tex. Bus. Orgs. Code §§ 1.102, 1.104, 1.105 (official Texas site); Ohio R.C. §§ 1706.26 and 1706.29 (codes.ohio.gov); and the syllabus and ¶¶1-2 of Dombroski v. WellPoint, 2008-Ohio-4827 (text extracted from the Ohio Supreme Court PDF). I did not read primary text for these, and mark them unverified: former R.C. 1705.48 (search summary only), the SSP Partners opinion (decision date from search results only), any Delaware veil-piercing opinion (the Delaware standard is described as the record states it), Bestfoods, and the Illinois law on who assesses penalties. I did not open any other Harvey LAB audit.

Reconciliation: I reviewed all 65 criteria and the instructions. I re-checked every criterion Sol flagged against the documents: the SBE passages in the Birchfield letter and the petition; the recharacterization passages in the GC summary, workbook, petition and Birchfield recommendation 5; the IEPA complaint's jurisdiction paragraphs and Counts III-IV; and the workbook balance sheet, ratios, P&L note and retained earnings rows. Primary law I read this session: SSP Partners, 275 S.W.3d 444 (holding and decision date, via CourtListener); Dombroski, 2008-Ohio-4827 (syllabus and ¶2, local text of the Ohio Supreme Court PDF); Ohio R.C. 1706.26 and 1706.29 (codes.ohio.gov); and TBOC §§ 1.102 and 1.104 (statutory text via texas.public.law, because the official site is a JavaScript app). I did not read Delaware veil-piercing opinions, Bestfoods, or the Illinois penalty-assessment provisions, and no finding relies on them as verified.

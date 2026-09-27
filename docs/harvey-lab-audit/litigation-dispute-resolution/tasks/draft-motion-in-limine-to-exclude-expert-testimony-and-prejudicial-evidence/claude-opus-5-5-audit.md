# Claude Opus 5.5 audit: Draft Motion in Limine to Exclude Expert Testimony and Prejudicial Evidence in Commercial Breach of Contract Case

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 49. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is largely sound and closely tracks the record and the defense strategy memo the solver receives. The deposition admissions, figures, dates, OSHA details and the 37-day notice all check out, and the FRE 407, 403 and 404(b) propositions are correct. The weak spots are all arguable, none problematic. The criteria describe §7.2 as a plain $2M cap when it is an outright exclusion with a fallback cap (C-020, C-045, C-019). C-022 requires tying the no-federal-Daubert fact to 'heightened scrutiny', a standard Rule 702 does not contain. C-043 assumes a full-exclusion request that the targeted strategy never makes. Of Sol's five arguable findings, I agree only on C-022, and on C-019/020 for a different reason. Its C-023, C-007/008, C-021 and C-009/010 concerns are not defects because the criteria track memo-directed advocacy that the record supports. The record also has minor document inconsistencies (exhibit numbering, the impact-period table, the 'product liability' label), but none of them misgrades a criterion.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | arguable | source_conflict | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L172), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L372), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L164) | Rubric calls §7.2 a '$2M cap on consequential damages'; the clause first excludes them entirely, with the $2M cap only as a fallback | revised |
| [O2](#o2) | arguable | legal_error | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L188) | C-022 requires using Marchetti's lack of prior federal Daubert qualification to argue 'heightened scrutiny', which Rule 702 does not provide | blind |
| [O3](#o3) | arguable | ambiguous_or_unjudgeable | [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L356) | C-043 assumes a full-exclusion request first; the record-directed strategy is targeted, severable exclusion from the start | blind |
| [O4](#o4) | arguable | document_defect | — | Record inconsistencies: OSHA exhibit numbering, the '24-month' lost-profits table, and Marchetti's report vs. her deposition on industry data | blind |
| [O5](#o5) | arguable | document_defect | — | Instructions call this a 'product liability defense'; the record is a commercial breach-of-contract and warranty case | blind |

<a id="o1"></a>
### O1. Rubric calls §7.2 a '$2M cap on consequential damages'; the clause first excludes them entirely, with the $2M cap only as a fallback

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L172), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L372), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L164)

Section 7.2 first provides that neither party is liable for consequential damages at all. It expressly lists lost profits, cost of substitute goods and reputational harm. The $2,000,000 aggregate cap applies only if a court holds consequential damages recoverable despite that disclaimer. The criteria follow the memo's shorthand ('capping consequential damages at $2,000,000'), not the contract. A competent motion could make the stronger and accurate argument that the $10.29M of consequential testimony is barred outright and therefore irrelevant under FRE 401–403. If that motion does not also frame §7.2 as a '$2M cap', a judge could fail it on C-045 ('caps consequential damages at $2,000,000') or C-020 ('substantially exceed the $2,000,000 contractual cap'). C-019's 'or otherwise argues the cap is relevant' makes it the lowest risk of the three. Answers that mention both tiers pass, so this misgrades only some competent work.

Evidence:
- `supply-agreement.docx.txt`: “IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER PARTY FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ... INCLUDING WITHOUT LIMITATION LOST PROFITS ... COST OF SUBSTITUTE GOODS OR SERVICES, REPUTATIONAL HARM”
- `supply-agreement.docx.txt`: “IN THE EVENT THAT ANY COURT OF COMPETENT JURISDICTION DETERMINES THAT CONSEQUENTIAL DAMAGES ARE RECOVERABLE ... SHALL NOT EXCEED TWO MILLION DOLLARS ($2,000,000)”
- `C-045`: “PASS if the motion correctly states that the Supply Agreement's limitation-of-liability clause caps consequential damages at $2,000,000.”

Suggested fix: Describe §7.2 as an exclusion of consequential damages with a $2,000,000 fallback cap. Accept either framing: a total bar or the fallback cap.

Related GPT-6 Sol findings: Arguable concerns: item 3.

<a id="o2"></a>
### O2. C-022 requires using Marchetti's lack of prior federal Daubert qualification to argue 'heightened scrutiny', which Rule 702 does not provide

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L188)

Rule 702 and Daubert apply one reliability standard to every proffered expert. Whether an expert has testified in federal court before is not a Daubert factor and does not raise the standard. The memo itself warns against a credentialism argument and treats the fact only as 'relevant context'. C-022 fails any motion that omits the fact, and it rewards a legally inaccurate framing. A careful drafter might leave it out as irrelevant, or as an invitation to a weight-not-admissibility response, and would then fail an all-pass criterion. The fact appears in the memo, so many solvers will include it, and 'heightened scrutiny' can be read as rhetoric. That keeps this arguable rather than problematic.

Evidence:
- `C-022`: “uses this fact to support the argument for heightened scrutiny of her methodology. FAIL if this fact is not mentioned.”
- `defense-strategy-memo.docx.txt`: “We should not make a credentialism argument --- her academic and professional credentials in forensic economics are not genuinely in dispute”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Evid. 702 (unverified): The same admissibility standard applies to every expert. It has no forum-history or 'heightened scrutiny' component.

Suggested fix: Make the point optional context. Drop the 'heightened scrutiny' requirement, or pass a motion that omits it or mentions it only as background.

Related GPT-6 Sol findings: Arguable mandatory-advocacy concern: item 1.

<a id="o3"></a>
### O3. C-043 assumes a full-exclusion request first; the record-directed strategy is targeted, severable exclusion from the start

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L356)

The memo tells the drafter not to challenge the $1,578,500 resin cost or the $512,500 premium. It seeks exclusion of 'specified portions' of Marchetti's testimony through severable, category-by-category arguments. A motion drafted that way never asks the court to exclude all of her testimony, so it has no 'alternative' to full exclusion to offer. C-043 passes only an alternative request made 'if the court declines to exclude all', and fails only 'all-or-nothing' relief. A targeted motion without a separate fallback fits neither condition, and the two judges may split. Its 'or that the testimony be limited in some way' clause will rescue many answers, so this is arguable.

Evidence:
- `C-043`: “PASS if the motion requests, in the alternative, that if the court declines to exclude all of Marchetti's testimony, specific opinion categories ... be excluded individually”
- `defense-strategy-memo.docx.txt`: “We should draft the motion with clear, severable arguments for each damages category so the court can grant relief on a category-by-category basis.”

Suggested fix: PASS if the motion either (a) requests alternative or limiting relief, or (b) structures its Marchetti requests as severable, category-by-category exclusions.

<a id="o4"></a>
### O4. Record inconsistencies: OSHA exhibit numbering, the '24-month' lost-profits table, and Marchetti's report vs. her deposition on industry data

**Status:** arguable · **Category:** document_defect · **Criteria:** none

(1) Solano's email calls the OSHA citation 'Exhibit 18'. On Plaintiff's exhibit list, PX-18 is the audited financials. (2) Marchetti's report states a 24-month impact period, Aug 2023 to Jul 2025, but its table runs only to Jul 2024, and the report is dated Oct 2024. (3) The report says she considered regional industry conditions, while at deposition she said she was unaware of the Q2 2023 downturn. None of these misgrades a criterion as written. They do affect what an accurate motion should say about exhibit numbers and facts.

Evidence:
- `solano-trial-strategy-email.eml.txt`: “Exhibit 18 is the OSHA Citation and Notification of Penalty dated April 10, 2023”
- `plaintiff-exhibit-list.docx.txt`: “PX-18             **Ridgeline Audited Financial Statements (FY 2022--2023)**”
- `marchetti-expert-report.docx.txt`: “for the 24-month impact period from August 2023 through July 2025”

Suggested fix: Make the exhibit numbers consistent across the documents. Make the impact-period table match its stated span.

<a id="o5"></a>
### O5. Instructions call this a 'product liability defense'; the record is a commercial breach-of-contract and warranty case

**Status:** arguable · **Category:** document_defect · **Criteria:** none

The instructions ask for a motion 'for our product liability defense'. The memo and the expert report describe claims for breach of contract and breach of the implied warranty of merchantability under a supply agreement, and no product-liability claim appears. A solver who follows the instructions literally could mis-frame the introduction. No criterion turns on the framing, so the impact on grading is low.

Evidence:
- `task.json instructions`: “Draft a motion in limine based on the attached case files for our product liability defense.”
- `defense-strategy-memo.docx.txt`: “alleges breach of contract and breach of the implied warranty of merchantability arising from deliveries of CascadeMax 7200 polymer resin”

Suggested fix: Change the instructions to 'for our defense in this breach-of-contract/warranty action'.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Arguable mandatory-advocacy concern: item 1 | arguable | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L188) | arguable | I agree, and it matches my blind O2. The memo calls the fact 'relevant context' and warns against a credentialism argument. C-022 requires using the fact to support 'heightened scrutiny', a standard Rule 702 does not contain, and it fails any motion that leaves the fact out. A careful drafter might leave out a legally irrelevant point, so this misgrades some competent work. It is not a flat misstatement of law, because 'heightened scrutiny' can be read as rhetoric. |
| Arguable concerns: item 1 | arguable | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L196) | not_a_defect | The FRE govern evidence in federal court, and the criterion targets only Washington 'evidence rules... for evidentiary rulings'. Washington substantive law under the §9.1 choice-of-law clause (UCC notice, cap enforceability) is not an evidence rule, so citing it does not trigger FAIL. Nothing in the record invokes Washington ER, and a competent federal motion would not cite ER 407/404 alongside the FRE. The chance of a hypothetical 'comparison' citation is too small to call this a defect. |
| Arguable concerns: item 2 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L68), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L76) | not_a_defect | C-007/008 require the motion to make an advocacy argument, not to state a rule that unverified client data is always inadmissible. The record strongly supports the argument. Marchetti admitted she did not check Cho's spreadsheet against production logs or the audited financials (Dep. 56–58). Gerhardt Opinion No. 2 and memo §III.D both direct it. C-008 also accepts the 'parrot a party's self-serving calculations' framing, which courts regularly use. Rule 703 reliance is the opponent's response, and the rubric does not have to adopt it. |
| Arguable concerns: item 3 | arguable | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L164) (arguable), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L172) (arguable), [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L180) (not_a_defect) | mixed | Sol's merits-versus-admissibility concern mostly fails. Memo §§III.G and VI tell the drafter to raise the cap and the notice issues briefly as FRE 403 sequencing points, and C-019 accepts any argument that the cap bears on presentation. Sol's claim that the resin premium is not consequential is contradicted by §7.2, which lists 'COST OF SUBSTITUTE GOODS'. C-019 and C-020 are still arguable on a different ground (my O1): §7.2 first excludes consequential damages outright and makes the $2M cap only a fallback. C-021 simply tracks the memo. |
| Arguable concerns: item 4 | arguable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L84), [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json#L92) | not_a_defect | The $14,211,000 vs $14,200,000 gap is accurate (Dep. 92–93). Memo §III.F tells the drafter to use it as the closing cumulative-reliability point in the Daubert section. C-010 asks for exactly that link, and it does not require arguing that the error alone warrants exclusion or penalize a proportionate description. A brief but explicit cumulative link is not 'only in passing', so a memo-following motion passes. |

## Blind pass and what changed

I kept all five blind findings. I revised O1 to link it to Sol's item 3 and to rank C-019 below C-020 and C-045, since C-019's 'or otherwise argues the cap is relevant' clause makes it the lowest risk. I also added the fact that §7.2 expressly lists 'cost of substitute goods', which rebuts Sol's side point that the resin premium is not inherently consequential. I adopted none of Sol's other findings. I rejected C-023 because it targets only Washington evidence rules, and Washington substantive law is not covered. I rejected C-007/008 because the criteria require a well-supported advocacy argument, not a per-se rule. I rejected C-021 because the memo expressly directs the brief notice point. I rejected C-009/010 because C-010 asks only for the cumulative-reliability link the memo prescribes. Sol's C-022 finding matches my blind O2.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (arguable; C-019, C-020, C-045): Rubric calls Section 7.2 a '$2M cap on consequential damages'; the clause first excludes them entirely, with the $2M cap only as a fallback
- **O2** (arguable; C-022): C-022 rewards using Marchetti's lack of prior federal Daubert qualification to argue for 'heightened scrutiny', which Rule 702 does not provide
- **O3** (arguable; C-043): C-043 assumes the motion first seeks to exclude all of Marchetti's testimony; the record-directed strategy is targeted exclusion from the start
- **O4** (arguable; no criterion): Record inconsistencies: exhibit numbering, the '24-month' lost-profits table, and Marchetti's report vs. her deposition on industry reports
- **O5** (arguable; no criterion): Instructions call this a 'product liability defense'; the record is a commercial breach-of-contract and warranty case

## Coverage and limits

Blind pass: Read all 49 criteria and the instructions. Read all 8 supplied documents in full: the Solano meet-and-confer email, the defense strategy memo, the Marchetti deposition excerpts, the Marchetti expert report, the Gerhardt rebuttal report, the OSHA citation, the Supply Agreement, and Plaintiff's exhibit list. Checked every figure and date the criteria rely on against the record: $14,211,000 vs $14,200,000; the Aug 22 to Sept 28, 2023 notice interval of 37 days; the December 2023 Northline order; the deposition page cites; OSHA No. 2023-OR-00487 and the $14,502 penalty. Read the text of FRE 407 on Cornell LII. Did not pull case law on the feasibility-controverted split, or on whether an expert's lack of prior federal testimony is relevant under Rule 702. Did not verify the W.D. Wash. local-rule page limits for motions in limine; no criterion depends on them. I did not read the generic system prompt or the judge prompt closely, since no finding turns on them.

Reconciliation: Read all 49 criteria and the instructions. In the blind pass I read all 8 documents in full. In this pass I re-checked the record facts behind each Sol finding: §7.2 in full, §9.1 governing law, the memo's sections on scrap, mitigation, the arithmetic gap, the notice issue, the cap and FRE 407, the deposition on the Cho spreadsheet and the $11,000 gap, and a grep for any Washington evidence-rule citation (none found). I read Sol's audit markdown and index entry. I tried to fetch the text of Rules 702 and 703 from Cornell LII, but WebFetch was blocked by a spend limit, so those authorities are marked unverified. I did no case-law research on the reliance-on-client-data doctrine or the feasibility exception.

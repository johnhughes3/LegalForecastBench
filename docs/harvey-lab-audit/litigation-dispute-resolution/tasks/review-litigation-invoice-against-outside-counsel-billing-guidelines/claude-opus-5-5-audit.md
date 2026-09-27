# Claude Opus 5.5 audit: Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 49. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly sound, and I confirmed its core dollar figures against the record: Kwan, block billing, deposition, photocopying, Westlaw, overhead, hotel, meals, travel time. Four defects can zero out a correct report under all-pass scoring:
- C-020 and C-042 require calling a business-class fare 'borderline' although §6.1(b) expressly permits it on the rubric's own ~4h20m flight.
- C-027 fixes Cho's at-risk amount at a $36,270 subtotal that the invoice's own 23 line entries contradict ($41,730). The invoice fails to foot overall by $26,877.
- C-041 imposes a hidden three-tier severity taxonomy.
- C-040 requires treating the 2024 annual budget as covering work through an April 2025 trial.

Lesser, arguable issues: C-019, C-026/C-039 (footing), C-010 (Kwan headcount), C-017 (Relativity prior approval), C-030 (notification timing), C-044 (mandated Cho re-authorization) and C-022/C-033 (the full-disallowance alternative). Of Sol's findings, I agree on the airfare, Cho, budget and severity issues. I reject C-046, C-005/C-029, C-031, C-009/C-038, C-024 and the naming-drift point as not defects.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | source_conflict | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L172), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348) | Business-class airfare must be called 'borderline' although §6.1(b) plainly permits it on a ≥4h flight (rubric says ~4h20m) | revised |
| [O2](#o2) | arguable | source_conflict | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164) | C-019 frames the business-class fare as a 'potential violation' even though the rubric's own flight time complies | revised |
| [O3](#o3) | problematic | document_defect | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L228) | Cho line entries total 214.0 hrs/$41,730, not the 186.0/$36,270 subtotal the rubric treats as the only correct at-risk figure | revised |
| [O4](#o4) | arguable | document_defect | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L324) | C-026 hard-codes the 186.0-hour figure, and C-039 fixes the revised total's base at the stated total, despite the footing error | revised |
| [O5](#o5) | problematic | unrequested_requirement | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L340) | Requires a three-tier severity taxonomy the instructions never request | revised |
| [O6](#o6) | problematic | unsupported_fact | [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L332) | Requires concluding the 2024 annual budget is insufficient for work 'through trial in April 2025' | revised |
| [O7](#o7) | arguable | ambiguous_or_unjudgeable | [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L92) | Oct 28 headcount criterion counts a law student as an 'attorney'; excluding Kwan, attendance equals the cap | blind |
| [O8](#o8) | arguable | source_conflict | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L148) | Relativity criterion ignores prior approval Entry No. 4 for third-party Relativity hosting | blind |
| [O9](#o9) | arguable | unsupported_fact | [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L252) | 'Failed to provide' the 75% notification is premature: this invoice crossed the threshold and the 5-business-day window had not run | blind |
| [O10](#o10) | arguable | ambiguous_or_unjudgeable | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L364) | Mandates a retroactive/renewed-approval recommendation for Cho, though the Guidelines make disallowance the stated consequence | blind |
| [O11](#o11) | arguable | internal_inconsistency | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L188), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L276) | Overage-specific hotel/meal figures required even though the unapproved out-of-forum trip supports full disallowance | revised |

<a id="o1"></a>
### O1. Business-class airfare must be called 'borderline' although §6.1(b) plainly permits it on a ≥4h flight (rubric says ~4h20m)

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L172), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348)

§6.1 is a bright line. Flights scheduled under 4 hours fly coach, and business class 'may be booked without prior approval' on flights of 4 hours or more. The rubric's own ~4h20m figure clears the line. C-020 fails a report that treats the fare as 'clearly compliant.' C-042 fails a report where the fare is 'entirely dismissed as compliant.' Both would fail the correct reading. A strong answer finds the cabin class compliant and still flags the whole trip as unapproved out-of-forum travel under §9.1(3) (C-018). The 4h20m figure is not in the record, so the criteria also depend on an outside fact. With all-pass scoring, this alone can zero out a correct report.

Evidence:
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “For domestic flights with a scheduled duration of four (4) hours or more, business class may be booked without prior approval.”
- `C-020`: “FAIL if the report treats the business class airfare as either clearly compliant or clearly non-compliant without noting the borderline nature.”
- `C-042`: “OR if it is entirely dismissed as compliant.”

Suggested fix: Accept either (a) cabin class compliant under §6.1(b) because the flight is 4 hours or more (optionally subject to itinerary confirmation), with the trip flagged under §9.1, or (b) a request to verify the scheduled duration. Drop the mandatory 'borderline' label.

Related GPT-6 Sol findings: Definite defects: item 1.

<a id="o2"></a>
### O2. C-019 frames the business-class fare as a 'potential violation' even though the rubric's own flight time complies

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164)

C-019's FAIL condition is lenient ('not flagged at all'). But its PASS text says the fare 'potentially violates' §6.1 and requires noting the borderline 4h20m duration. A report that analyzes the fare and concludes it complies with §6.1(b) arguably 'flags' it. A judge reading PASS literally could still fail it. The premise is the same as in O1, with lower misgrade risk.

Evidence:
- `C-019`: “potentially violates Guidelines §6.1, which requires coach/economy for domestic flights under 4 hours. The report should note that the Chicago-to-San Francisco flight is approximately 4 hours and 20 minutes, making it a borderline case.”

Suggested fix: PASS if the report addresses the business-class fare against §6.1, whatever its conclusion.

Related GPT-6 Sol findings: Definite defects: item 1.

<a id="o3"></a>
### O3. Cho line entries total 214.0 hrs/$41,730, not the 186.0/$36,270 subtotal the rubric treats as the only correct at-risk figure

**Status:** problematic · **Category:** document_defect · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L228)

I re-summed Cho's 23 fee entries this session: 214.0 hours and $41,730.00. Subtotal row G146 and Timekeeper Summary E7/F7 state 186.0 / $36,270.00. The invoice fails to foot more broadly: all 139 entries total $269,554 against a stated $242,687, and expense lines total $244,652.14 against $244,642.14. C-027 fails any 'materially incorrect' amount, so an auditor who sums Cho's actual entries, arguably the more careful answer, fails. No criterion gives credit for catching the footing error, which is itself a core deviation.

Evidence:
- `bs-vih-invoice-october-2024.xlsx.txt`: “G146='SUBTOTAL — Elaine Cho (Contract Attorney)' \| H146='186.0' \| I146='195.00' \| J146='36,270.00'”
- `bs-vih-invoice-october-2024.xlsx.txt`: “G24='244,642.14'”
- `C-027`: “FAIL if the amount is materially incorrect or not quantified.”

Suggested fix: Fix the workbook so the entries match the subtotals, or accept $36,270 (as summarized) or $41,730 (per line items), and add credit for identifying the footing discrepancy.

Related GPT-6 Sol findings: Definite defects: item 2.

<a id="o4"></a>
### O4. C-026 hard-codes the 186.0-hour figure, and C-039 fixes the revised total's base at the stated total, despite the footing error

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L324)

C-026's PASS text embeds '186.0 hours ($36,270.00)', but its FAIL applies only when the expiry is not flagged. It misgrades only if a judge reads the figure as mandatory. C-039 requires the revised total to be $487,329.14 minus adjustments. The line-item population actually totals $514,206.14. A report that withholds a final payable figure pending a corrected invoice, or recomputes from the line items, could fail. Most reports will use the stated total, so the risk is limited to some competent answers.

Evidence:
- `C-026`: “her 186.0 hours ($36,270.00) billed in October 2024 lack current authorization”
- `C-039`: “calculated as the original $487,329.14 minus the total recommended adjustments. FAIL if no revised invoice total is provided.”

Suggested fix: Accept either Cho figure. For C-039, accept a clearly labeled provisional revised total or reconciliation scenarios pending invoice correction.

Related GPT-6 Sol findings: Definite defects: item 2, Definite defects: item 3.

<a id="o5"></a>
### O5. Requires a three-tier severity taxonomy the instructions never request

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L340)

The instructions ask only for 'a full deviation report.' C-041 fails any report that does not sort violations into at least three severity levels 'similar to' Mandatory Reduction / Requires Discussion / Process Failure. Severity tiering is a stylistic choice, not a standard component of an invoice deviation report. Reports organized by Guideline section, by fees versus expenses, or by line item, each with an adjustment and rationale, are competent and common. The solver gets no signal that tiers are needed. Under all-pass scoring, this hidden format requirement zeroes out otherwise correct reports.

Evidence:
- `task.json instructions`: “produce a full deviation report. Output: `invoice-compliance-deviation-report.docx`.”
- `C-041`: “FAIL if violations are not categorized by severity.”

Suggested fix: Delete C-041, or pass any report that separates clear reductions from items needing discussion or approval, in any structure.

Related GPT-6 Sol findings: Definite defects: item 5.

<a id="o6"></a>
### O6. Requires concluding the 2024 annual budget is insufficient for work 'through trial in April 2025'

**Status:** problematic · **Category:** unsupported_fact · **Criteria:** [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L332)

The $2.8M figure is the 2024 annual budget. §10.1 sets budgets per calendar year and requires a revised estimate 'for the remainder of the calendar year.' January–April 2025 work, including trial, falls under a 2025 budget. C-040's PASS requires stating that the remaining budget is insufficient 'through trial in April 2025,' which treats the 2024 budget as covering the whole case. A careful report that confines the analysis to 2024 ($569k left for Nov–Dec against a ~$487k monthly run rate) may fail. The misgrade depends on the judge reading PASS conjunctively, because the FAIL clause ('budget concerns are not discussed') is lenient. But the criterion requires a wrong premise.

Evidence:
- `blackwell-stanhope-engagement-letter.docx.txt`: “The 2024 annual budget for this Matter is \$2,800,000.00”
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “a revised budget estimate for the remainder of the calendar year”
- `C-040`: “and that remaining budget is insufficient for the work remaining through trial in April 2025.”

Suggested fix: Change it to: discusses cumulative spend against the 75% threshold and whether the remaining 2024 budget is adequate through year-end, with optional comment on 2025 and trial.

Related GPT-6 Sol findings: Definite defects: item 4.

<a id="o7"></a>
### O7. Oct 28 headcount criterion counts a law student as an 'attorney'; excluding Kwan, attendance equals the cap

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L92)

§5.1 limits internal strategy meetings to four attorneys. Kwan is a summer associate and law student, not an attorney. Excluding him, exactly four attorneys attended, which meets the limit. Yet C-010 passes a report that flags '4 excluding Kwan' against a cap of 4, rewarding a non-violation. A competent answer might say the headcount limit is met once Kwan's time is disallowed under §3.1, or might not discuss headcount at all. That answer falls between PASS and FAIL ('does not mention the attendance count issue'). The note's reference to 'C-007' should be C-008.

Evidence:
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “No more than **four (4) attorneys** may attend any single internal strategy meeting or conference.”
- `bs-vih-invoice-october-2024.xlsx.txt`: “B6='Timothy Kwan' \| C6='Summer Associate' \| D6='N/A — Law Student'”
- `C-010`: “identifies that 5 attorneys (or 4 excluding Kwan) attended”

Suggested fix: Pass a report that addresses attendance either way: over the cap if Kwan is counted, or compliant or moot once he is excluded and disallowed. Fix the cross-reference.

<a id="o8"></a>
### O8. Relativity criterion ignores prior approval Entry No. 4 for third-party Relativity hosting

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L148)

The prior approval log approves continued Relativity hosting through the vendor CloudStar at an estimated $12,000–$15,000 a month. §7.1(c) makes third-party vendor charges reimbursable. A careful answer may treat the $18,500 as approved in principle, flag the $3,500–$6,500 over the estimate, and request the vendor invoice. C-017 passes only 'non-reimbursable overhead' or 'borderline substantive-vs-storage.' So the approved-but-over-estimate answer falls between PASS and FAIL. Option (a) also rewards full disallowance, which ignores the documented approval.

Evidence:
- `vih-prior-approval-log.docx.txt`: “Approval for continued use of Relativity-hosted document review platform for Phase II production. Monthly hosting and processing fees through third-party vendor CloudStar Technologies, LLC.”
- `C-017`: “FAIL if the Relativity charge is not mentioned at all.”

Suggested fix: Add a PASS path: approved under the prior approval, flagged for exceeding the estimate, with vendor backup requested.

<a id="o9"></a>
### O9. 'Failed to provide' the 75% notification is premature: this invoice crossed the threshold and the 5-business-day window had not run

**Status:** arguable · **Category:** unsupported_fact · **Criteria:** [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L252)

Cumulative spend crosses $2.1M only with this invoice dated November 4, 2024 (September YTD was $1,743,612). §10.1 allows five business days from the crossing date, which is about November 11. On the invoice date the firm had not yet missed the deadline. The Matter Status sheet also gives a budget status line, though without the required contents. A report saying the notice is 'due / not yet received / deficient' is accurate, but a strict judge could fail it under 'failed to provide.'

Evidence:
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “This notification must be provided within five (5) business days of the date on which cumulative invoiced fees and expenses reach the 75% threshold.”
- `C-030`: “Blackwell Stanhope failed to provide the required written notification per Guidelines §10.1.”

Suggested fix: Pass any report that flags the missing, due or deficient §10.1 notification.

Related GPT-6 Sol findings: Arguable/qualified concerns: item 2.

<a id="o10"></a>
### O10. Mandates a retroactive/renewed-approval recommendation for Cho, though the Guidelines make disallowance the stated consequence

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L364)

§9.1(6) says failure to renew 'will result in disallowance of all time billed after the expiration date.' §9.3 allows retroactive approval only in extraordinary circumstances. A reviewer for VIH can reasonably recommend full disallowance of Cho's October time without offering re-authorization. C-044 fails any report without a re-authorization recommendation. That turns a client business decision into a required element. The premise 'her work may have been valuable' is speculation.

Evidence:
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “Failure to obtain renewal before the expiration of the approval period will result in disallowance of all time billed after the expiration date.”
- `C-044`: “FAIL if no recommendation is made regarding Cho's re-authorization.”

Suggested fix: Pass any clear disposition of Cho's post-expiration time: disallow, or disallow pending a renewal or retroactive request.

<a id="o11"></a>
### O11. Overage-specific hotel/meal figures required even though the unapproved out-of-forum trip supports full disallowance

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L188), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L276)

The San Francisco trip lacked the prior approval §9.1(3) requires (C-018). §11.2(e) allows 'Full disallowance of expenses incurred without required prior approval.' A report that disallows all trip expenses, noting the cap breaches as aggravating factors, may never compute the $984 hotel or $87.40 meal overage. C-022 and C-033 could then fail it as 'materially incorrect,' even though its adjustment is larger and grounded in the Guidelines. Many strong reports will give both figures, so only some competent answers are affected.

Evidence:
- `vih-outside-counsel-billing-guidelines-v4.2.docx.txt`: “Full disallowance of expenses incurred without required prior approval per §9.1”
- `C-022`: “FAIL if the overage is materially incorrect.”

Suggested fix: Also pass a report that recommends full disallowance of the unapproved trip's expenses while noting each cap overage.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Definite defects: item 1 | confirmed | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164) (arguable), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L172) (problematic), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348) (problematic) | mixed | §6.1(b): 'For domestic flights with a scheduled duration of four (4) hours or more, business class may be booked without prior approval.' The rubric's own ~4h20m figure clears that line. C-020 and C-042 fail a report that calls the fare compliant, which is the correct reading. C-019's FAIL condition is only 'not flagged at all'. But its PASS text requires 'potentially violates', so a report that analyzes the fare and finds it compliant may still fail. That makes C-019 arguable. |
| Definite defects: item 2 | confirmed | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220) (arguable), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L228) (problematic) | mixed | I re-summed this session: 23 Cho entries total 214.0 hrs / $41,730, but subtotal row G146 and Timekeeper Summary E7/F7 say 186.0 / $36,270. C-027 fails a 'materially incorrect' amount, so a solver who uses the line items fails it. C-026's FAIL applies only if the expiry is not flagged, so it is at risk only when its 186.0 figure is read into PASS. That makes C-026 arguable. |
| Definite defects: item 3 | confirmed | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L316) (not_a_defect), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L324) (arguable) | mixed | C-038 tests only internal consistency: the total must equal the sum of the listed adjustments. The footing error does not affect that. C-039 fixes the base at the stated $487,329.14. The line items actually total $514,206.14. A report that declines to give a final payable figure until the firm corrects the invoice, or computes from the line-item base, could fail. Most reports will use the stated total, so C-039 is arguable, not problematic. |
| Definite defects: item 4 | confirmed | [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L332) | problematic | The engagement letter says 'The 2024 annual budget for this Matter is $2,800,000.00'. §10.1 ties the revised estimate to 'the remainder of the calendar year.' C-040's PASS requires saying the remaining budget is insufficient 'through trial in April 2025.' That treats the 2024 budget as covering 2025 work, which is a wrong premise. The misgrade depends on the judge reading PASS conjunctively, because the FAIL clause is lenient. |
| Definite defects: item 5 | confirmed | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L340) (problematic), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L380) (not_a_defect) | mixed | C-041 requires at least three severity tiers. The instructions never ask for that, and a deviation report organized by section or line item is standard. C-046 asks for Guideline section citations, which are implicit in a guidelines deviation report. Its 75% threshold is a grading tolerance, and it absorbs the §3.1/§9.1 overlap for Cho and Kwan. |
| Arguable/qualified concerns: item 1 | arguable | [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L52), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L244) | not_a_defect | §4.2 says VIH 'reserves the right' to reduce by 30%, and §11.2(b) lists that reduction as a remedy. Recommending the available remedy is the reviewer's job, and C-037 asks for recommended adjustments. A report that makes the 30% reduction conditional on itemization still applies it and states the figure. The arithmetic ($1,276.50; $1,557.30) is correct. |
| Arguable/qualified concerns: item 2 | arguable | [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L252) | arguable | The October invoice dated Nov 4 is what crosses the $2.1M threshold (September YTD was $1,743,612). §10.1 allows 'five (5) business days of the date on which cumulative invoiced fees and expenses reach the 75% threshold.' So 'failed to provide' is premature on the invoice date. A report that says 'due / not yet received' could be failed by a strict judge. |
| Arguable/qualified concerns: item 3 | arguable | [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L260) | not_a_defect | The transmittal has a 'Matter Status Summary' and a 'Looking Ahead' section. It lacks the §10.1 content: 'key drivers of cost', necessity, and 'expected trajectory of spending'. A report calling the explanation absent or deficient flags the gap and passes. The criterion's wording is slightly loose, but no competent answer fails because of it. |
| Arguable/qualified concerns: item 4 | arguable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L84), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L316) | not_a_defect | C-009 already computes the overage excluding Kwan (15.2 hours, 11.2 over the cap). It requires only some specific dollar reduction, with no fixed figure, so overlap with the Kwan disallowance is left to the solver. C-038 checks only that the total equals the sum of the parts. Neither fails a report that avoids double-counting. |
| Arguable/qualified concerns: item 5 | arguable | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L204) | not_a_defect | §6.1 says black car services are 'not reimbursable under any circumstances,' and full disallowance passes C-024. The alternative taxi-equivalent path is lenient but reflects client discretion ('VIH may apply' remedies, §11.2). It fails no correct answer. |
| Arguable/qualified concerns: item 6 | arguable | [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L44), [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L52), [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L156) | not_a_defect | The record itself alternates between Pryor-Hall and Pryce-Hall, and each criterion identifies the entry clearly by date, hours and tasks. LLM judges will not fail a report over the spelling. No correct answer changes. |

## Blind pass and what changed

1. Upgraded C-041 (severity tiers) from arguable to problematic. The requirement is plainly hidden and fails common competent structures under all-pass scoring. Sol concurs.
2. Upgraded C-040 from arguable to problematic, on the wrong-fact prong: the 2024 annual budget does not govern work through an April 2025 trial. The misgrade depends on a conjunctive reading of PASS.
3. Split blind O1 by status. C-020 and C-042 stay problematic. C-019 is now a separate arguable finding because its FAIL clause is lenient.
4. Split blind O2. C-027 is problematic (re-summed this session: Cho 214.0 hrs / $41,730). C-026 and C-039 are arguable.
5. Removed C-038 and C-047 from the footing finding. C-038 checks only internal consistency, and C-047 correctly states the stated total.
6. Removed C-018 and C-024 from the full-disallowance finding (now O11), leaving C-022 and C-033.
7. Dropped blind O10 (Pryor-Hall/Pryce-Hall, Vanguard/Saxonbrook, Rosenberg/DeVries approval dates). None of these changes a correct answer, and judges will not penalize the spelling.
8. After reading Sol, I rejected its C-046, C-005/C-029, C-031, C-009/C-038, C-024 and naming-drift points as not defects. I adopted no new criteria from Sol.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-020, C-042, C-019): Business-class airfare forced into 'borderline' although the rubric's own 4h20m flight clearly qualifies under §6.1(b)
- **O2** (problematic; C-026, C-027, C-047, C-039, C-038): Invoice does not foot: fee entries total $269,554.00, not $242,687.00; Cho's entries total 214.0 hrs/$41,730, not 186.0/$36,270
- **O3** (arguable; C-041): Requires a three-tier severity taxonomy the instructions never request
- **O4** (arguable; C-010): Oct 28 headcount criterion counts a law student as an 'attorney'; excluding Kwan, attendance equals the cap
- **O5** (arguable; C-017): Relativity criterion ignores prior approval Entry No. 4 for third-party Relativity hosting
- **O6** (arguable; C-030): 'Failed to provide' 75% notification is premature: this invoice crossed the threshold and the 5-business-day window had not run
- **O7** (arguable; C-040): Requires concluding the 2024 annual budget is insufficient for work 'through trial in April 2025'
- **O8** (arguable; C-044): Mandates recommending retroactive/renewed approval for Cho despite Guidelines language making disallowance the stated consequence
- **O9** (arguable; C-022, C-033, C-024, C-018): Overage-specific figures required even though the unapproved out-of-forum trip supports full disallowance
- **O10** (arguable; C-005, C-018, C-021, C-034, C-035): Record inconsistencies in names (Vanguard vs Saxonbrook; Pryor-Hall vs Pryce-Hall) carried into the criteria

## Coverage and limits

Blind pass: I read all 49 criteria and the instructions. I read four documents in full: the Guidelines v4.2, the engagement letter with Exhibits A and B, the prior approval log, and the transmittal email. I parsed the XLSX invoice with scripts. That covered all 139 fee entries (each hours x rate checked), the 22 expense lines, the Timekeeper Summary, Matter Status, YTD Summary, Rate Schedule and LEDES sheets. I recomputed the figures behind every dollar criterion: Kwan, both block-billing reductions, Tanaka, photocopying, Westlaw, hotel, meals, travel time, the surcharge and the YTD total. I also footed the fee and expense totals. I did no case-law research because no criterion turns on external law; everything depends on the supplied Guidelines. I did not check real ORD-SFO scheduled flight times. The record contains no flight duration, and the finding uses the rubric's own 4h20m figure. The advisor review was rate-limited and did not run.

Reconciliation: In the blind pass I read all 49 criteria, the instructions and all five documents, and parsed the XLSX with scripts: 139 fee entries, 22 expense lines, and the summary sheets. In this pass I:
- read Sol's index entry and full audit report;
- re-read the Guidelines provisions on block-billing remedies, §5.1 staffing, §6.1 travel and black cars, §9.1(6) contract attorneys, §10.1 budget and the $350k threshold, and §11.2 remedies, plus the full transmittal email;
- re-summed Cho's 23 entries (214.0 hrs / $41,730).

No external case law was needed, because every criterion turns on the supplied Guidelines. I did not verify actual ORD-SFO scheduled flight durations.

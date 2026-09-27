# Claude Opus 5.5 audit: Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 57. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric tracks the guidelines and pre-approval log accurately for most line items. Three criteria would fail correct work under the all-pass metric. C-041 depends on a $0.11 total discrepancy that the spreadsheet does not contain: the lines sum to $145,404.30 against a hardcoded $86,742.19. C-034 requires a $357 partial reduction on a dinner attended only by firm staff, which §5.7 disallows in full. C-045 divides a dinner of at least three people by two. Sol and I agree on all three. C-019, C-032, C-033, C-044, C-050 and C-052 are debatable. The rubric also omits real violations (the Line 37 lunch over the cap, and the Line 43 conferencing license, which is overhead), but no criterion fixes a total reduction, so those gaps do not cause misgrading.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | document_defect | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338) | Disbursement lines sum to $145,404.30, not $86,742.30; the true discrepancy is $58,662.11, not $0.11 | blind |
| [O2](#o2) | problematic | legal_error | [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L274) | Line 38 dinner was attended only by firm personnel, so §5.7 disallows all $612; C-034 requires a $357 partial reduction | blind |
| [O3](#o3) | problematic | source_conflict | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370) | Line 40 dinner had at least three diners ($82.33 per person, under the $85 cap); C-045 divides by two | blind |
| [O4](#o4) | arguable | ambiguous_or_unjudgeable | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362) | C-044 assumes a settlement dinner with plaintiff's counsel is presumptively entertainment or ineligible, but §5.7(b) covers parties relevant to the Matter | adopted_after_reading_sol |
| [O5](#o5) | arguable | source_conflict | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162) | C-019 treats the $25K GC threshold as unmet, but GC Cha had already approved Hartsfield up to $35K/month | blind |
| [O6](#o6) | arguable | unrequested_requirement | [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L426) | C-052 requires a pending-approval total, but the guidelines also allow rejecting unapproved items outright | blind |
| [O7](#o7) | arguable | document_defect | [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410) | C-050 accepts only $86,742.19 or $86,742.30 as the billed total; the true line-item sum is $145,404.30 | blind |

<a id="o1"></a>
### O1. Disbursement lines sum to $145,404.30, not $86,742.30; the true discrepancy is $58,662.11, not $0.11

**Status:** problematic · **Category:** document_defect · **Criteria:** [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338)

C-041 passes only if the report finds a $0.11 gap between the stated total ($86,742.19) and a line-item sum of $86,742.30. The 47 amounts on the Disbursements sheet actually sum to $145,404.30. Expert/Consultant ($76,800) plus Contract Attorneys ($27,810) alone exceed the stated total. G50 is hardcoded, not a formula. A solver that adds the lines correctly will report a $58,662.11 understatement and fail. Judges see only the criterion, not the spreadsheet, so they will treat $0.11 as correct.

Evidence:
- `hwk-invoice-may-2025.xlsx.txt`: “D50='TOTAL DISBURSEMENTS' \| G50=86742.19”
- `C-041`: “does not match the sum of the 47 line items (which totals $86,742.30), resulting in an $0.11 discrepancy”
- `billing-guidelines.docx.txt`: “Invoice totals must accurately reflect the sum of all individual line items.”

Suggested fix: Either fix the record so the lines reconcile, or change C-041 to require identifying the $58,662.11 gap between the stated $86,742.19 and the $145,404.30 line-item sum.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o2"></a>
### O2. Line 38 dinner was attended only by firm personnel, so §5.7 disallows all $612; C-034 requires a $357 partial reduction

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L274)

All five Line 38 attendees work for HWK: Aldridge, Beale, Palermo and two summer associates. §5.7 says meals attended solely by firm personnel are not reimbursable, regardless of whether case work was discussed. The correct reduction is therefore $612. C-034 treats three firm lawyers as eligible (compliant amount 3 × $85 = $255) and fails any reduction more than $20 from $357, so it fails the correct answer (problematic). C-032 carries the same premise that only the summer associates are ineligible. A solver who says every attendee is firm personnel probably still passes it (arguable). C-033 requires per-person cap math for a meal that is wholly non-reimbursable, so a solver that rejects it outright without that math could fail (arguable).

Evidence:
- `billing-guidelines.docx.txt`: “Meals attended solely by Firm personnel --- without Pinnacle personnel or third-party witnesses present --- are NOT reimbursable as disbursements, regardless of whether case-related work was discussed during the meal.”
- `hwk-invoice-may-2025.xlsx.txt`: “Working dinner, C. Aldridge, M. Beale, J. Palermo, and two summer associates, brief preparation at Carmichael's Steakhouse, Charlotte”
- `C-034`: “compliant amount = 3 × $85 = $255; reduction = $612 − $255 = $357”

Suggested fix: C-034: require rejecting the full $612 under the all-firm-personnel rule. C-032: treat all attendees as ineligible. C-033: make the cap arithmetic an optional alternative ground.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o3"></a>
### O3. Line 40 dinner had at least three diners ($82.33 per person, under the $85 cap); C-045 divides by two

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370)

The invoice lists Aldridge and Beale 'with plaintiff's counsel', which is at least three people. $247/3 = $82.33, under the $85 cap. C-045 requires the finding that $123.50 per person exceeds the cap, a headcount the record contradicts. A careful solver either finds no per-person violation or rejects or holds the meal on eligibility or documentation grounds. Either way it fails C-045.

Evidence:
- `hwk-invoice-may-2025.xlsx.txt`: “Working dinner, C. Aldridge and M. Beale, with plaintiff's counsel settlement discussion at The Piedmont Room”
- `C-045`: “PASS if the report identifies that $247 / 2 = $123.50 per person exceeds the $85/person working dinner cap”

Suggested fix: Delete C-045, or accept any of: full rejection, a hold pending the attendee list, or a cap analysis on the actual headcount.

Related GPT-6 Sol findings: confirmed_defects/2.

<a id="o4"></a>
### O4. C-044 assumes a settlement dinner with plaintiff's counsel is presumptively entertainment or ineligible, but §5.7(b) covers parties relevant to the Matter

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362)

§5.7(b) makes meals with 'parties relevant to the Matter' eligible. The entertainment clause turns on whether substantive case work is conducted with third parties, and a settlement discussion is substantive. A competent reviewer could find Line 40 eligible, or flag it only because the description omits attendee names and titles. That report is neither 'not flagged at all' nor flagged on the grounds C-044's PASS text names, so judges may disagree.

Evidence:
- `billing-guidelines.docx.txt`: “(b) Third-party witnesses, potential witnesses, or parties relevant to the Matter.”
- `C-044`: “noting that a dinner with opposing counsel may constitute client entertainment (which is not reimbursable under Section 5.7) or does not meet the working meal criteria”

Suggested fix: Pass any report that flags Line 40 for review on any ground, including incomplete attendee documentation or uncertain eligibility.

Related GPT-6 Sol findings: arguable/1.

<a id="o5"></a>
### O5. C-019 treats the $25K GC threshold as unmet, but GC Cha had already approved Hartsfield up to $35K/month

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162)

The log shows Cha's approval for the $25K threshold 'has been obtained', with a $35,000 monthly cap. The real violation is the $5,900 above that cap, which needed advance GC sign-off. Most solvers will mention the GC requirement and pass. One that says the threshold was satisfied and frames the problem only as a cap overrun could be marked down.

Evidence:
- `pre-approval-log.docx.txt`: “Because the anticipated monthly fees exceed the \$25,000 threshold under Section 5.4 of our Billing Guidelines, Lorraine\'s approval was required and has been obtained.”
- `C-019`: “exceed the $25,000/month threshold requiring General Counsel (Lorraine Cha) pre-approval under Section 5.4”

Suggested fix: Reword C-019: the $5,900 above the GC-approved $35,000 cap required advance GC authorization, which the log does not show.

Related GPT-6 Sol findings: arguable/0.

<a id="o6"></a>
### O6. C-052 requires a pending-approval total, but the guidelines also allow rejecting unapproved items outright

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-052](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L426)

§5.1 and §5.4 allow outright rejection of charges incurred without pre-approval. A report that recommends rejecting Voss, GraphicWorks, Brooks and DataScan outright has no 'held pending' bucket and fails C-052. Other criteria (C-023, C-028, C-040) accept either hold or rejection, so C-052 is less flexible than the rest of the rubric.

Evidence:
- `billing-guidelines.docx.txt`: “Failure to obtain Pre-Approval may result in rejection of the charge in its entirety.”
- `C-052`: “FAIL if no pending-approval amount is provided.”

Suggested fix: Pass a report that totals the pre-approval failures, whether it recommends holding them or rejecting them.

<a id="o7"></a>
### O7. C-050 accepts only $86,742.19 or $86,742.30 as the billed total; the true line-item sum is $145,404.30

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410)

Because of the O1 defect, a report that gives only the recomputed billed total ($145,404.30) fails C-050, and the criterion wrongly calls $86,742.30 the arithmetic sum. Most reports will also quote the stated $86,742.19, so few will actually misgrade.

Evidence:
- `C-050`: “approximately $86,742.19 as stated on the invoice or $86,742.30 as the arithmetic sum”

Suggested fix: Accept $86,742.19 (stated) or $145,404.30 (line-item sum), or fix the record.

Related GPT-6 Sol findings: confirmed_defects/0.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| confirmed_defects/0 | confirmed | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338) (problematic), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410) (arguable) | mixed | I re-summed the Disbursements sheet: 47 lines (G2:G48) total $145,404.30, and G50 is a hardcoded $86,742.19. C-041 passes only a report that finds a $0.11 gap, so a solver that adds correctly and reports $58,662.11 fails. C-050 accepts the stated $86,742.19, which most reports will quote. It fails only a report that gives just the true sum, and it wrongly calls $86,742.30 the arithmetic sum. So C-050 is arguable, not confirmed. |
| confirmed_defects/1 | confirmed | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266) (arguable), [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282) (problematic) | mixed | All five Line 38 attendees are HWK personnel. §5.7 says meals attended solely by Firm personnel are not reimbursable, so the correct reduction is the full $612. C-034 requires about $357, allowing $255 for three supposedly eligible firm lawyers, and it fails the correct answer. C-032 rests on the same wrong premise, but a solver who says every attendee, summer associates included, is ineligible should still pass. So C-032 is arguable. |
| confirmed_defects/2 | confirmed | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370) | problematic | Invoice D41 reads 'C. Aldridge and M. Beale, with plaintiff's counsel', so at least three people dined. $247/3 = $82.33, under the $85 cap. C-045 requires the per-person figure $247/2 = $123.50, a headcount the record contradicts. A careful solver will either find no cap violation or reject the meal on eligibility grounds, and fails either way. |
| arguable/0 | arguable | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162) | arguable | The pre-approval log (Entry 2, Feb 12 email) says Cha's approval for the $25K threshold 'has been obtained', with a $35,000 cap. The real gap is the missing GC sign-off for the $5,900 overage. C-019's wording implies the $25K GC threshold was never met. Most solvers will mention GC approval and pass, but one that says only that the threshold was satisfied could fail. |
| arguable/1 | arguable | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362) | arguable | §5.7(b) makes meals with 'parties relevant to the Matter' eligible, and the entertainment clause turns on substantive case work. A settlement dinner with plaintiff's counsel can reasonably qualify. C-044 passes only a report that flags the meal as entertainment or as failing the attendee test. A solver that finds it eligible, or flags it only for the missing attendee names required by §5.7 Descriptions, falls between its PASS and FAIL conditions. |

## Blind pass and what changed

I adopted C-044 as arguable (new O4) from Sol arguable/1. §5.7(b)'s 'parties relevant to the Matter' clause makes a settlement dinner with plaintiff's counsel plausibly eligible, which I had missed in the blind pass. I made the C-032 and C-033 statuses explicit inside O2: C-034 is problematic, C-032 and C-033 are arguable. I disagree with Sol on C-050: it is arguable, not confirmed, because the stated total is accepted. I dropped no blind findings. C-052 (arguable) is not in Sol's audit and I keep it.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-041): Invoice lines sum to $145,404.30, not $86,742.30; the real discrepancy is $58,662.11, not $0.11
- **O2** (problematic; C-034, C-032, C-033): Line 38 dinner was attended only by firm personnel, so §5.7 disallows all $612; C-034 requires a $357 partial reduction
- **O3** (problematic; C-045): Line 40 dinner had at least three diners, so it was $82.33 per person, under the $85 cap; C-045 divides by two
- **O4** (arguable; C-019): C-019 treats the $25K GC threshold as unmet, but GC Cha had already approved Hartsfield up to $35K/month
- **O5** (arguable; C-052): C-052 requires a pending-approval total, but the guidelines also let a reviewer reject unapproved items outright
- **O6** (arguable; C-050): C-050 accepts only $86,742.19 or $86,742.30 as the billed total; the lines actually sum to $145,404.30

## Coverage and limits

Blind pass: I read all four supplied documents in full: the billing guidelines, the engagement letter, the pre-approval log, and the invoice XLSX (Summary, Professional Fees and Disbursements sheets). I also read the instructions and all 57 criteria. I recomputed the Disbursements sheet with a script: the 47 line items sum to $145,404.30. By category: Travel 3,788.30, Document Production 14,940, Expert/Consultant 76,800, Court Costs 511, Courier 159, Meals 1,001, Technology 20,395, Contract Attorneys 27,810. The Professional Fees lines sum to $161,698.50. I checked each criterion's facts, amounts and section references against the documents. No case law or statute controls the result, since this is interpretation of a private billing guideline, so I consulted no external legal sources and cite no authorities. I did not open the harness system prompt or judge prompt beyond the task description. I did not look at any other audit.

Reconciliation: I re-checked Sol's five findings against the record. I recomputed the 47 disbursement lines ($145,404.30) and confirmed that G50 is hardcoded at $86,742.19. I re-read the §5.7 attendee, entertainment and description text, the Line 38 and Line 40 descriptions, and pre-approval log Entry 2 (Hartsfield GC approval, $35K cap). I re-read the target criteria: C-019, C-032, C-033, C-034, C-041, C-044, C-045, C-050 and C-052. I carried forward my blind-pass review of all 57 criteria. No external legal authority applies, since this is the interpretation of a private billing guideline.

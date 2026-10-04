# Claude Opus 5.5 (low): Identify Issues in Litigation Matter Budget Proposal

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/identify-issues-in-matter-budget-proposal/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 37 of 39 criteria; GPT-5.5 passed 37 of 39 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [budget-issue-memorandum.docx](output/budget-issue-memorandum.docx) ([read as Markdown](output/budget-issue-memorandum.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Identifies fee total reconciliation discrepancy (ISSUE_001) | Pass | Pass |
| [C-002](#c-002) | Correctly quantifies fee discrepancy as $116,050 | Pass | Pass |
| [C-003](#c-003) | Identifies Croft's rate exceeds OCG partner cap (ISSUE_002) | Pass | Pass |
| [C-004](#c-004) | Quantifies Croft rate overage at $25/hr over $825 cap | Pass | Pass |
| [C-005](#c-005) | Identifies Okeke's rate exceeds OCG senior associate cap (ISSUE_003) | Pass | Pass |
| [C-006](#c-006) | Quantifies Okeke rate overage at $25/hr over $550 cap | Pass | Pass |
| [C-007](#c-007) | Identifies Okeke's rate increase exceeds 3% annual cap (ISSUE_013) | Pass | Pass |
| [C-008](#c-008) | States correct OCG-compliant max rate for Okeke ($566.50) | **Fail** | **Fail** |
| [C-009](#c-009) | Identifies insufficient rate increase notice period (ISSUE_004) | Pass | Pass |
| [C-010](#c-010) | Identifies paralegal rate exceeds OCG cap (ISSUE_005) | Pass | Pass |
| [C-011](#c-011) | Quantifies Hu paralegal rate overage at $25/hr over $200 cap | Pass | Pass |
| [C-012](#c-012) | Identifies inadequate notice for Hu's addition to matter (ISSUE_006) | Pass | Pass |
| [C-013](#c-013) | Identifies e-discovery vendor sole-source violation (ISSUE_007) | Pass | Pass |
| [C-014](#c-014) | Identifies expert witness fees exceed pre-approval threshold (ISSUE_008) | Pass | Pass |
| [C-015](#c-015) | Identifies business class travel without pre-approval (ISSUE_009) | Pass | Pass |
| [C-016](#c-016) | Identifies internal copying/printing as non-reimbursable (ISSUE_010) | Pass | Pass |
| [C-017](#c-017) | Recommends removal of $15,000 copying/printing from budget | Pass | Pass |
| [C-018](#c-018) | Identifies unauthorized post-trial/appeal reserve (ISSUE_011) | Pass | Pass |
| [C-019](#c-019) | Identifies Boyd Whitaker as unbudgeted phantom timekeeper (ISSUE_012) | Pass | Pass |
| [C-020](#c-020) | Notes Whitaker addition would require GC notice under OCGs | Pass | Pass |
| [C-021](#c-021) | Identifies mock trial/jury consulting expense as requiring GC pre-approval | Pass | Pass |
| [C-022](#c-022) | Does NOT flag two-partner limit as violated (DISTRACTOR_005) | Pass | Pass |
| [C-023](#c-023) | Recommends reducing Croft's rate to $825/hr or obtaining waiver | Pass | Pass |
| [C-024](#c-024) | Recommends reducing Okeke's rate to comply with OCG caps | Pass | Pass |
| [C-025](#c-025) | Recommends reducing Hu's rate to $200/hr or obtaining waiver | Pass | Pass |
| [C-026](#c-026) | Recommends competitive bidding for e-discovery vendor | Pass | Pass |
| [C-027](#c-027) | Recommends submitting expert CVs and scope for GC pre-approval | Pass | Pass |
| [C-028](#c-028) | Assigns severity levels to identified issues | Pass | Pass |
| [C-029](#c-029) | Budget inconsistency rated as Critical or High severity | Pass | Pass |
| [C-030](#c-030) | Rate cap violations rated as Critical or High severity | Pass | Pass |
| [C-031](#c-031) | Notes at least two compliant budget areas | Pass | Pass |
| [C-032](#c-032) | Recommends removal or separate approval for L700 appeal reserve | Pass | Pass |
| [C-033](#c-033) | Cites OCG rate cap provisions specifically | Pass | Pass |
| [C-034](#c-034) | Cites OCG 60-day notice requirement for rate increases | Pass | Pass |
| [C-035](#c-035) | Cites OCG 10-business-day notice requirement for new timekeepers | Pass | Pass |
| [C-036](#c-036) | Recommends reconciling the two fee totals before approval | Pass | Pass |
| [C-037](#c-037) | Identifies Croft's rate increase notice also has percentage issue | Pass | Pass |
| [C-038](#c-038) | Recommends obtaining pre-approval for business class travel | Pass | Pass |
| [C-039](#c-039) | Quantifies expert fee per-expert average as ~$87,500 | **Fail** | **Fail** |

## Judge reasoning

### C-001

Identifies fee total reconciliation discrepancy (ISSUE_001) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L18))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the reconciliation discrepancy in multiple places: the Executive Summary states 'The phase table shows $1,708,950 in fees, but the staffing table (hours × rates) comes to $1,825,000. The $116,050 gap is not explained.' Issue C-1 in the Issue Summary table is titled 'Phase fees ($1,708,950) do not reconcile to staffing fees ($1,825,000); $116,050 unexplained, and proposal claims reconciliation' rated High severity. Section 4 Category C provides detailed analysis of this discrepancy. The financial tables also show both figures clearly.
- **GPT-5.5: Pass.** The memorandum explicitly states that the phase table fee total is $1,708,950 while the staffing table / hours-times-rates total is $1,825,000, identifies the $116,050 unexplained gap, and flags it as a high-severity reconciliation issue.

### C-002

Correctly quantifies fee discrepancy as $116,050 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L26))

- **Sonnet 4.6: Pass.** The memorandum explicitly states the $116,050 discrepancy multiple times: in the Executive Summary ('The $116,050 gap is not explained'), in Issue C-1 ('$116,050 unexplained'), and in Table 3.3. It correctly identifies $1,825,000 - $1,708,950 = $116,050.
- **GPT-5.5: Pass.** The memorandum explicitly states that the phase table shows $1,708,950 while the staffing table totals $1,825,000, identifying the unexplained gap/understatement as $116,050.

### C-003

Identifies Croft's rate exceeds OCG partner cap (ISSUE_002) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L34))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies in Issue A-1 that Croft's rate of $850 exceeds the $825 Equity Partner cap, with a financial impact of $15,500 (620 hrs × $25 excess). This is also reflected in Table 3.2 and the executive summary.
- **GPT-5.5: Pass.** The memorandum explicitly states that Croft’s proposed rate is $850 against an $825 Equity Partner cap, identifies this as an OCG rate-cap violation, and quantifies the impact.

### C-004

Quantifies Croft rate overage at $25/hr over $825 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L42))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Table 3.2: 'Croft (Equity Partner) ... $25 × 620 = $15,500' and in issue A-1: 'Croft rate $850 exceeds $825 Equity Partner cap ... $15,500 (620 hrs)'. Both the per-hour overage ($25/hr) and total impact ($15,500) are quantified.
- **GPT-5.5: Pass.** The memorandum explicitly quantifies Croft’s overage as $850 versus an $825 cap and states the impact as $15,500 for 620 hours; it also shows $25 × 620 = $15,500 in the rates table.

### C-005

Identifies Okeke's rate exceeds OCG senior associate cap (ISSUE_003) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L50))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in issue A-2 that Okeke's rate of $575 exceeds the $550 Senior Associate cap, noting a 4.5% increase without GC-approved justification. This is clearly documented in the issue summary table and detailed findings.
- **GPT-5.5: Pass.** The memorandum explicitly states that Okeke’s proposed rate of $575 exceeds the $550 Senior Associate cap, including in the executive summary and Issue A-2.

### C-006

Quantifies Okeke rate overage at $25/hr over $550 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L58))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Table 3.2: 'Okeke (Sr. Assoc., 8th yr) | $550 | $575 | $550 | $550.00 | $25 × 980 = $24,500'. This quantifies both the per-hour overage ($25/hr) and the total financial impact ($24,500 for 980 hours). The criterion is satisfied.
- **GPT-5.5: Pass.** The memorandum explicitly states Okeke's proposed $575 rate exceeds the $550 cap and quantifies the overage as $25 × 980 hours = $24,500 in the rates table and issue summary.

### C-007

Identifies Okeke's rate increase exceeds 3% annual cap (ISSUE_013) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L66))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Issue A-2 that Okeke's rate increase from $550 to $575 is 4.5%, which exceeds the 3% annual cap, and notes that this requires written justification and advance GC approval under §3.2(a). This is clearly identified as a violation.
- **GPT-5.5: Pass.** The memorandum expressly identifies Okeke’s rate increase from $550 to $575 as a 4.5% increase and states that it exceeds the OCG’s 3% annual cap without GC-approved justification, both in the issue summary and detailed analysis.

### C-008

States correct OCG-compliant max rate for Okeke ($566.50) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L74))

- **Sonnet 4.6: Fail.** The memorandum addresses Okeke's rate issue (A-2) by stating the OCG cap is $550 and that the rate should be reset to $550. It never calculates or mentions the 3% increase figure of $566.50 ($550 × 1.03). The criterion requires that the memo compute or state the maximum permissible rate under the 3% cap (~$566.50), not just cite the absolute cap of $550. The memo only cites $550 as the cap without addressing what a 3% increase over $550 would yield.
- **GPT-5.5: Fail.** The memorandum does not calculate or state Okeke’s 3% increase maximum as $566.50 ($550 × 1.03). It instead treats $550 as the maximum permitted rate due to the OCG cap and lists Okeke’s max as $550.

### C-009

Identifies insufficient rate increase notice period (ISSUE_004) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L82))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Issue A-6 that the rate increase notice was emailed on December 15, 2024, which is 17 days before the January 1 effective date, and that the OCG requires 60 days' advance notice (November 1 deadline). This is clearly stated: 'The notice was emailed on Sunday, December 15, 2024, 17 days before the effective date. The deadline for January 1 increases is November 1, and the notice period is 60 days.'
- **GPT-5.5: Pass.** The memorandum explicitly states that the rate notice was emailed on December 15, 2024, 17 days before the January 1 effective date, and identifies that the OCG required 60 days’ advance notice / a November 1 deadline.

### C-010

Identifies paralegal rate exceeds OCG cap (ISSUE_005) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L90))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies in Issue A-3 that paralegal Hu's proposed rate of $225/hr exceeds the OCG paralegal cap of $200/hr, with a calculated impact of $18,500 (740 hrs × $25 excess). This is also reflected in Table 3.2 and the executive summary.
- **GPT-5.5: Pass.** The memorandum explicitly states that Hu/Hsu's proposed paralegal rate is $225/hr and exceeds the $200 OCG paralegal cap, including in the executive summary, issue A-3, and rate table.

### C-011

Quantifies Hu paralegal rate overage at $25/hr over $200 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L98))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Table 3.2 that Hu's excess is '$25 × 740 = $18,500', and in issue A-3 it states 'Cap Hu at $200 or lower ($18,500 reduction)'. Both the per-hour overage ($25) and total impact ($18,500) are quantified.
- **GPT-5.5: Pass.** The memorandum explicitly states Hu’s proposed $225 rate exceeds the $200 paralegal cap by $25/hour and quantifies the impact as $18,500 for 740 hours.

### C-012

Identifies inadequate notice for Hu's addition to matter (ISSUE_006) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Issue B-1 that Hu was added with only one business day's notice (request sent Friday April 25 at 3:47 pm for a start on Monday April 28), violating the OCG requirement of ten business days' notice and written GC approval. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the Hu/Hsu addition issue: notice sent Friday April 25 for a Monday April 28 start, only one business day’s notice, with no GC approval and missing required details, violating the 10-business-day notice requirement under OCG §4.3.

### C-013

Identifies e-discovery vendor sole-source violation (ISSUE_007) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L114))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies this issue in section D-1 (Issue D-1), stating that the $285,000 Clearpoint e-discovery cost exceeds the $200,000 threshold requiring competitive bids from three vendors, and that no competitive bids are documented. It also notes the vendor was already 'engaged' without prior approval.
- **GPT-5.5: Pass.** The memorandum expressly identifies the $285,000 Clearpoint e-discovery cost, states it exceeds the $200,000 threshold, notes that no competitive bids are documented, and explains that three vendor bids or a sole-source justification with GC approval are required.

### C-014

Identifies expert witness fees exceed pre-approval threshold (ISSUE_008) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L122))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies this issue in section D-2, noting that the damages expert ($90,000) and forensics expert ($85,000) each exceed the $75,000 pre-approval threshold, that no CVs, scope, or fee schedules have been submitted, and that GC pre-approval is required before retention. This matches all elements of the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly identifies two expert budgets of $90,000 and $85,000, totaling $175,000, states that each exceeds the $75,000 pre-approval threshold, and notes that no CVs, scope, or fee schedules were provided, requiring GC pre-approval.

### C-015

Identifies business class travel without pre-approval (ISSUE_009) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L130))

- **Sonnet 4.6: Pass.** The agent's output clearly identifies the business class travel issue in Issue D-3, noting that the proposal plans business class for Croft to Miami and New York 'to accommodate scheduling demands' without pre-approval, and that domestic trips of this length do not meet the 'extraordinary circumstances' standard required by OCG §7.4(a),(c),(d),(e). The recommendation is to deny business class and require economy fares.
- **GPT-5.5: Pass.** The memorandum explicitly flags that the proposal includes business-class airfare for the lead partner on domestic travel without pre-approval, states this violates OCG economy-class/travel approval requirements, and recommends denying the business-class fare premium.

### C-016

Identifies internal copying/printing as non-reimbursable (ISSUE_010) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L138))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the $15,000 internal copying/printing issue in multiple places: Issue D-5 in the summary table (marked High severity, citing OCG §7.5 and §7.8(a), with 'Remove $15,000' as impact), and in Section 4 Category D under 'D-5. Internal copying/printing' which states 'Internal copying is overhead and is not reimbursable regardless of how labeled.' The issue is also included in the financial impact tables and recommended actions.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the $15,000 “internal document reproduction” / copying-printing line item as non-reimbursable under OCG §§7.5 and 7.8(a), states internal copying is overhead regardless of label, and recommends removing it.

### C-017

Recommends removal of $15,000 copying/printing from budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L146))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the $15,000 internal copying/printing issue in Issue D-5 and recommends: 'Remove the $15,000. Only third-party vendor costs with invoices may be claimed.' This is a clear remediation recommendation to remove the internal copying cost and replace it with third-party copying only. It is also listed in the Executive Summary and in the mandatory corrections list in Section 6.
- **GPT-5.5: Pass.** The memorandum specifically identifies the $15,000 internal copying/printing budget as non-reimbursable and recommends removing it, allowing only third-party vendor costs with invoices.

### C-018

Identifies unauthorized post-trial/appeal reserve (ISSUE_011) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L154))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the unauthorized L700 post-trial/appeal reserve in multiple places: Issue C-2 in the issue summary table (High severity, OCG §5.4, App. A, $92,000 impact), the executive summary noting it was never requested by the client, and Section 4 Category C detailed findings explaining that the reserve requires specific GC authorization and a supporting memorandum. The firm's own workbook is cited as confirming 'No appellate planning was requested by the client.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies the L700 post-trial/appeal reserve as 200 hours / $92,000, states it was not requested by the client, cites the relevant OCG requirement, and recommends removing it unless separately authorized by the GC.

### C-019

Identifies Boyd Whitaker as unbudgeted phantom timekeeper (ISSUE_012) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L162))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies Boyd Whitaker in Issue B-2 as an undisclosed potential second partner with approximately 60 hours in L400 (summary judgment/motion practice phase), noting that he is mentioned in the narrative and biographies but excluded from the staffing table and totals with no rate disclosed. This matches the criterion's requirements about an unbudgeted cost risk from an omitted timekeeper.
- **GPT-5.5: Pass.** The memorandum expressly identifies Boyd Whitaker as an undisclosed/unbudgeted potential second partner, notes he is mentioned for about 60 hours in L400, that he is omitted from the staffing table and totals, no rate is provided, and quantifies the unbudgeted risk up to approximately $49,500.

### C-020

Notes Whitaker addition would require GC notice under OCGs ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L170))

- **Sonnet 4.6: Pass.** In section B-2, the memorandum explicitly states that Whitaker 'still needs a §4.3 notice and approval' and recommends requiring the firm to 'file a §4.3 request' for Whitaker. Section 4.3 is the OCG timekeeper addition requirement that mandates 10 business days' notice and written GC approval. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum specifically flags Boyd Whitaker as an undisclosed potential second partner, states he was “not noticed,” cites OCG §4.3, and explains that he “still needs a §4.3 notice and approval,” with a recommendation to file a §4.3 request or remove him. It also identifies the possible second partner as needing GC approval. This satisfies the requirement to note the GC notice/approval procedural requirement for Whitaker.

### C-021

Identifies mock trial/jury consulting expense as requiring GC pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L178))

- **Sonnet 4.6: Pass.** The memorandum explicitly flags the $95,000 mock trial/jury consulting expense (Silvermark) as requiring advance written GC pre-approval under OCG §7.7 in Issue D-4, and also lists it as pending GC pre-approval in the financial summary tables and recommended actions.
- **GPT-5.5: Pass.** The memorandum explicitly flags the $95,000 mock trial/jury consulting expense as requiring advance written GC approval under OCG §7.7, including in the executive summary, issue table, and detailed finding D-4.

### C-022

Does NOT flag two-partner limit as violated (DISTRACTOR_005) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L186))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in B-2: 'He would be the second partner, which is within the two-partner limit, but he still needs a §4.3 notice and approval.' This correctly acknowledges that having both Croft and Whitaker does not violate the two-partner cap. The agent flags Whitaker's unbudgeted hours and notice requirements, but does not claim the two-partner limit is exceeded.
- **GPT-5.5: Pass.** The memorandum flags Whitaker as undisclosed/unbudgeted and requiring notice/approval, but explicitly states that adding him would make him the second partner and is within the two-partner limit. It does not claim Croft plus Whitaker violates the partner staffing cap.

### C-023

Recommends reducing Croft's rate to $825/hr or obtaining waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L194))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses Croft's rate in Issue A-1 and in the recommendation for A-1/A-2: 'Reset Croft to $825 and Okeke to $550 throughout the budget ($40,000 in total). Tell the firm that Lexera will automatically reduce any over-cap entries.' This clearly recommends reducing Croft's rate to $825/hr, the OCG cap.
- **GPT-5.5: Pass.** The memorandum specifically identifies Croft’s proposed $850 rate as exceeding the $825 cap and recommends resetting Croft to $825 throughout the budget.

### C-024

Recommends reducing Okeke's rate to comply with OCG caps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L202))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies Okeke's rate of $575 as exceeding the $550 Senior Associate cap (Issue A-2, severity High) and in Section 4 (A-1/A-2) recommends: 'Reset Croft to $825 and Okeke to $550 throughout the budget ($40,000 in total). Tell the firm that Lexera will automatically reduce any over-cap entries.' This clearly recommends reducing Okeke's rate to $550/hr to comply with the OCG cap.
- **GPT-5.5: Pass.** The memorandum specifically identifies Okeke’s proposed $575/hr rate as exceeding the $550 senior associate cap and recommends resetting Okeke to $550 throughout the budget.

### C-025

Recommends reducing Hu's rate to $200/hr or obtaining waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L210))

- **Sonnet 4.6: Pass.** The memorandum explicitly recommends in Section A-3: 'Cap Hu at $200 or lower ($18,500 reduction). Ask the firm to correct Appendix A and explain the $215 figure.' Additionally, in Section 6 (Recommended Actions), item 4 states: 'approval is withheld until a compliant §4.3 notice is received at a rate of $200 or less.' This clearly recommends reducing Hu's rate to the $200/hr OCG cap.
- **GPT-5.5: Pass.** The memorandum specifically identifies Hu/Hsu's proposed $225 paralegal rate as exceeding the $200 OCG cap and recommends capping/reducing her rate to $200 or lower before approval.

### C-026

Recommends competitive bidding for e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L218))

- **Sonnet 4.6: Pass.** In Section D-1, the memorandum explicitly states: 'Hold the $285,000 until the firm submits bids or a sole-source justification, and support for the volume estimate.' It references the OCG requirement for 'bids from three vendors, or a documented sole-source justification with written GC approval, before the vendor is engaged.' This directly recommends competitive bidding among at least 3 vendors (or a documented sole-source justification) and requires documentation to be submitted before approval. The recommendation satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum specifically flags the e-discovery spend as exceeding the $200,000 threshold, states that the OCG requires bids from three vendors or a documented sole-source justification with written GC approval, and recommends holding the $285,000 until the firm submits bids or a sole-source justification. This satisfies the required remediation for competitive bidding/documentation to the GC.

### C-027

Recommends submitting expert CVs and scope for GC pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L226))

- **Sonnet 4.6: Pass.** In section D-2, the memorandum explicitly states: 'Approve these amounts only provisionally, pending §7.3 packages.' The §7.3 packages are described as requiring 'CV, scope, fee schedule, justification' before retention. The issue summary table also lists D-2 with the recommendation that '$175,000 pending approval' and references §7.3(a),(c). This clearly recommends submitting expert CVs and scope documents to the GC for pre-approval.
- **GPT-5.5: Pass.** The memorandum specifically identifies the two experts exceeding the $75,000 threshold, notes the absence of CVs, scope, and fee schedules, states that each expert needs pre-approval with CV, scope, fee schedule, and justification before retention, and recommends approval only provisionally pending the required §7.3 packages.

### C-028

Assigns severity levels to identified issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L234))

- **Sonnet 4.6: Pass.** The memorandum explicitly assigns severity levels (High, Medium, Low) to each identified issue in the Issue Summary table (Section 2) and repeats those severity designations in the detailed findings sections (Category A through F). The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memorandum includes an explicit severity classification system (High, Medium, Low) and assigns a severity level to each identified issue in the issue summary table and detailed findings.

### C-029

Budget inconsistency rated as Critical or High severity ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242))

- **Sonnet 4.6: Pass.** Issue C-1 in the agent's output explicitly addresses the $116,050 fee reconciliation discrepancy between the phase table ($1,708,950) and the staffing table ($1,825,000). It is assigned a severity of 'High' in the issue summary table, which is the second-highest tier in the two-tier severity scale used (High and Medium, with High being the top tier). This satisfies the criterion requiring the discrepancy to be rated Critical or High (or the highest/second-highest tier).
- **GPT-5.5: Pass.** The output explicitly identifies the $116,050 fee reconciliation discrepancy between the phase table and staffing/hourly totals as Issue C-1 and assigns it a High severity rating.

### C-030

Rate cap violations rated as Critical or High severity ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L250))

- **Sonnet 4.6: Pass.** The agent's output assigns 'High' severity to all three rate cap violations: A-1 (Croft at $850 vs $825 cap), A-2 (Okeke at $575 vs $550 cap), and A-3 (Hu at $225 vs $200 cap). The severity scale used is High/Medium/Low, making High the highest tier. All three rate cap violations are explicitly rated as High severity, satisfying the criterion.
- **GPT-5.5: Pass.** The output identifies Croft, Okeke, and Hu as exceeding OCG rate caps and assigns each of those rate cap violations a severity of High.

### C-031

Notes at least two compliant budget areas ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L258))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies two compliant areas in issue B-6: 'Staffing efficiency (46.7%) and diversity (Okeke 32.7%) thresholds met; confirm quarterly' with severity 'Low' and impact 'Compliant'. This affirmatively notes both (a) the staffing efficiency ratio (~46.7% vs. 40% minimum) and (b) diversity staffing (Okeke at 32.7% vs. 15% threshold) as compliant. That satisfies the criterion of at least two compliant areas being affirmatively identified.
- **GPT-5.5: Pass.** The memorandum affirmatively identifies two compliant areas: staffing efficiency ratio of 46.7% meeting the threshold and diversity staffing with Okeke's share of attorney hours at 32.7% meeting the threshold. This satisfies the requirement to note at least two compliant budget areas.

### C-032

Recommends removal or separate approval for L700 appeal reserve ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L266))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the L700 post-trial/appeal reserve in multiple places. In the Executive Summary, it states the budget 'includes a $92,000 L700 post-trial/appeal reserve that the Company never requested.' In Issue C-2, it recommends 'Remove L700 in full. Any future appellate reserve should come only at the GC's request, as a separate line item.' In Section 6 (Recommended Actions), item 1 lists C-2 as a mandatory correction requiring the budget to be returned. The financial tables also show L700 removed (showing $0) in both Scenario A and B. This clearly satisfies the criterion of recommending removal or separate approval for the L700 reserve.
- **GPT-5.5: Pass.** The memorandum specifically identifies the unauthorized L700 post-trial/appeal reserve, recommends removing the $92,000/200-hour L700 reserve in full, and states that any future appellate reserve should require specific GC authorization as a separate line item.

### C-033

Cites OCG rate cap provisions specifically ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L274))

- **Sonnet 4.6: Pass.** The memorandum explicitly cites specific OCG rate cap amounts throughout. In the executive summary it states 'Croft at $850 against an $825 cap, Okeke at $575 against a $550 cap, and Hu at $225 against a $200 cap.' Table 3.2 lists the OCG Cap column with $825, $550, $425, $375, and $200 for each timekeeper. The detailed findings sections A-1/A-2 state 'Reset Croft to $825 and Okeke to $550' and A-3 states 'All paralegals are capped at $200.' The issue summary table also lists specific cap amounts in the Impact column. The memorandum clearly references specific dollar cap amounts when discussing each rate violation rather than making only generic statements.
- **GPT-5.5: Pass.** The memorandum specifically identifies the relevant OCG cap amounts when discussing rate violations, including Croft at $850 against the $825 equity partner cap, Okeke at $575 against the $550 senior associate cap, and Hu at $225 against the $200 paralegal cap, with a rates table listing these caps.

### C-034

Cites OCG 60-day notice requirement for rate increases ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L282))

- **Sonnet 4.6: Pass.** In section A-6/A-7, the memorandum states: 'The deadline for January 1 increases is November 1, and the notice period is 60 days.' It also notes the notice was sent on December 15, 2024, '17 days before the effective date.' This explicitly references both the 60-day notice requirement and the actual ~17-day notice period provided, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically states that the Dec. 15 notice was sent 17 days before the Jan. 1 effective date and expressly says the OCG deadline is Nov. 1 with a 60-day notice period.

### C-035

Cites OCG 10-business-day notice requirement for new timekeepers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290))

- **Sonnet 4.6: Pass.** The memorandum discusses the Hu/Hsu addition issue in section B-1 and states 'Ten business days' notice and written GC approval are both prerequisites.' It also notes the request was sent on Friday April 25 for a Monday April 28 start, which is 'one business day's notice.' This satisfies the criterion of citing the 10-business-day OCG requirement and noting the actual notice was approximately 1 business day (the criterion says approximately 2 business days, but the memo says 1 business day - the criterion says 'approximately 2 business days' which is close enough to 'one business day' as described in the memo). The key requirements are met: the 10-business-day requirement is cited and the actual notice period is noted as being far short of that requirement.
- **GPT-5.5: Pass.** The memorandum discusses Margaret Hu/Hsu’s addition, cites OCG §4.3, expressly states that “Ten business days’ notice and written GC approval are both prerequisites,” and notes the actual notice was only one business day from Friday Apr. 25 to Monday Apr. 28. Although it characterizes the actual notice as 1 business day rather than approximately 2, it satisfies the core requirement by citing the 10-business-day notice and GC approval requirement in that discussion.

### C-036

Recommends reconciling the two fee totals before approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L298))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the $116,050 discrepancy between the phase table ($1,708,950) and the staffing table ($1,825,000) as Issue C-1 with High severity. In Section 4 (Category C, C-1), it recommends: 'Return the budget. Require corrected phase fees calculated from hours × approved rates, and a restated grand total.' Additionally, in Section 6 (Recommended Actions), item 1 states: 'Return the budget for revision under §§5.2 and 5.4, listing Issues A-1--A-5, C-1, C-2 and D-5 as mandatory corrections.' This clearly recommends reconciliation of the two fee totals before approval.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the discrepancy between the phase fee total ($1,708,950) and staffing-model total ($1,825,000), recommends returning the budget, and requires corrected phase fees calculated from hours × approved rates with a restated grand total before approval.

### C-037

Identifies Croft's rate increase notice also has percentage issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L306))

- **Sonnet 4.6: Pass.** The memorandum addresses Croft's rate issue in section A-1. It notes that Croft's rate goes from $825 to $850, described as the firm's 'standard 3% annual increase.' The analysis explicitly states that under §3.2(c), 'a permitted percentage increase cannot take a rate above the cap; if it would, the rate is set at the cap.' It further notes that the 2024 workbook itself states 'both 2024 rates were already at the cap and that any 2025 increase would exceed the cap.' This directly addresses the interaction between the percentage increase and the absolute cap - even if the 3% increase is within the percentage limit, the resulting rate ($850) exceeds the absolute cap of $825, so the rate must be set at the cap. The criterion asks whether the memo notes that while the 3% increase is within the percentage cap, the resulting rate still exceeds the absolute OCG partner cap of $825/hr. The memo does address this interaction clearly.
- **GPT-5.5: Pass.** The memorandum expressly states Croft’s rate increased from $825 to $850 as the firm’s “standard 3% annual increase,” but explains that the OCG caps are absolute ceilings and that even a permitted percentage increase cannot raise the rate above the $825 partner cap. This addresses the interaction between the percentage increase and the absolute cap.

### C-038

Recommends obtaining pre-approval for business class travel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L314))

- **Sonnet 4.6: Pass.** In Section D-3 and in the Recommended Actions (item 5), the memorandum explicitly recommends denying business-class airfare and requiring a revised travel estimate based on economy fares and OCG caps. This constitutes a specific remediation action for the business class travel issue, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically identifies business-class airfare as lacking pre-approval and recommends denying business class and requiring a revised travel estimate based on economy fares and OCG caps. This satisfies the criterion’s alternative remediation of revising the budget to economy-class-only travel.

### C-039

Quantifies expert fee per-expert average as ~$87,500 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L322))

- **Sonnet 4.6: Fail.** The memorandum states the two experts cost $90,000 and $85,000 respectively, totaling $175,000, and notes each exceeds the $75,000 pre-approval threshold. However, it never calculates or states a per-expert average of ~$87,500. The criterion specifically requires that the per-expert average (~$87,500 = $175,000 ÷ 2) be calculated or stated. The memo only lists the individual amounts and the total, not the average.
- **GPT-5.5: Fail.** The output identifies two experts at $90,000 and $85,000 and compares each to the $75,000 pre-approval threshold, but it does not calculate or state the per-expert average of approximately $87,500 ($175,000 / 2).

# GPT-6 Luna (xhigh): Identify Issues in Litigation Matter Budget Proposal

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/identify-issues-in-matter-budget-proposal/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 34 of 39 criteria; GPT-5.5 passed 34 of 39 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-009](#c-009) | Identifies insufficient rate increase notice period (ISSUE_004) | **Fail** | Pass |
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
| [C-020](#c-020) | Notes Whitaker addition would require GC notice under OCGs | **Fail** | **Fail** |
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
| [C-034](#c-034) | Cites OCG 60-day notice requirement for rate increases | **Fail** | **Fail** |
| [C-035](#c-035) | Cites OCG 10-business-day notice requirement for new timekeepers | Pass | **Fail** |
| [C-036](#c-036) | Recommends reconciling the two fee totals before approval | Pass | Pass |
| [C-037](#c-037) | Identifies Croft's rate increase notice also has percentage issue | Pass | Pass |
| [C-038](#c-038) | Recommends obtaining pre-approval for business class travel | Pass | Pass |
| [C-039](#c-039) | Quantifies expert fee per-expert average as ~$87,500 | **Fail** | **Fail** |

## Judge reasoning

### C-001

Identifies fee total reconciliation discrepancy (ISSUE_001) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L18))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the discrepancy between the phase fee total ($1,708,950) and the staffing-table-derived fee total ($1,825,000), noting a $116,050 gap. This is prominently featured in section 1.1 with a detailed table showing the difference by phase, and is also highlighted in the Executive Conclusion as 'the most material quantified issue.'
- **GPT-5.5: Pass.** The memorandum explicitly identifies the fee reconciliation discrepancy, stating that the phase fee estimate is $1,708,950 while the staffing-table fees are $1,825,000, a $116,050 gap, and includes a table showing the inconsistent internal budget totals.

### C-002

Correctly quantifies fee discrepancy as $116,050 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L26))

- **Sonnet 4.6: Pass.** The memorandum explicitly states '$116,050 gap between the phase fee estimate ($1,708,950) and the staffing-table fees ($1,825,000)' in the executive conclusion, and the reconciliation table shows TOTAL difference of $116,050 ($1,825,000 - $1,708,950). This matches the criterion exactly.
- **GPT-5.5: Pass.** The memorandum explicitly identifies a $116,050 gap/discrepancy between the phase fee estimate of $1,708,950 and staffing-table fees of $1,825,000, including the calculation in the reconciliation section.

### C-003

Identifies Croft's rate exceeds OCG partner cap (ISSUE_002) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L34))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Section 2 (Rates and timekeeper approvals) that Nathaniel Croft's proposed rate of $850 exceeds the OCG cap of $825 by $25/hr, stating 'Above absolute cap by $25/hr; a 3% increase from $825 would still be capped at $825.' It also quantifies the direct excess as $15,500 (620 hours × $25).
- **GPT-5.5: Pass.** The memorandum explicitly lists Nathaniel Croft's proposed rate as $850, the OCG cap as $825, and states it is above the absolute cap by $25/hr.

### C-004

Quantifies Croft rate overage at $25/hr over $825 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L42))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'Croft \ $15,500 (620 × \ $25)' in Section 2, and also notes the cap is \ $825 with the proposed rate at \ $850, making the overage \ $25/hr. Both the per-hour overage and total financial impact are quantified.
- **GPT-5.5: Pass.** The memorandum explicitly states Croft's proposed $850 rate is above the $825 cap by $25/hr and also quantifies the total impact as $15,500 based on 620 hours × $25.

### C-005

Identifies Okeke's rate exceeds OCG senior associate cap (ISSUE_003) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L50))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies Samara Okeke's proposed rate of $575 as exceeding the $550 cap, noting it is 'Above cap by $25/hr' and that the increase 'exceeds both the cap and annual limit.' This is clearly stated in the rates table in Section 2.
- **GPT-5.5: Pass.** The memorandum explicitly states in the rates table that Samara Okeke's proposed rate is $575, the OCG cap is $550, and that the rate is above the cap by $25/hr.

### C-006

Quantifies Okeke rate overage at $25/hr over $550 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L58))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'Okeke \ $24,500 (980 × \ $25)' in Section 2, and also notes 'Above cap by \ $25/hr' in the rates table. Both the per-hour overage ($25/hr) and the total financial impact ($24,500) are quantified.
- **GPT-5.5: Pass.** The memorandum explicitly states Okeke’s proposed $575 rate is above the $550 cap by $25/hr and also quantifies the planned-hours impact as $24,500 (980 × $25).

### C-007

Identifies Okeke's rate increase exceeds 3% annual cap (ISSUE_013) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L66))

- **Sonnet 4.6: Pass.** The memorandum explicitly states for Okeke: 'Above cap by $25/hr; increase is about 4.55% and exceeds both the cap and annual limit.' This clearly identifies that Okeke's rate increase exceeds the 3% annual cap, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically states that Samara Okeke’s proposed rate of $575 compared to the 2024 approved $550 is an increase of about 4.55% and exceeds the annual 3% increase limit, as well as the rate cap.

### C-008

States correct OCG-compliant max rate for Okeke ($566.50) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L74))

- **Sonnet 4.6: Fail.** The memorandum states that Okeke's proposed rate of $575 is above the $550 cap by $25/hr and that the increase is about 4.55%, exceeding both the cap and annual limit. However, it never calculates or states the maximum permissible rate under the 3% annual increase limit, which would be $550 × 1.03 = $566.50. The criterion requires that the memo compute or state approximately $566.50 as the OCG-compliant maximum. The memo only cites the $550 cap without addressing what the 3% increase calculation would yield as a maximum compliant rate.
- **GPT-5.5: Fail.** The memorandum does not calculate or state Okeke’s 3% increase maximum of approximately $566.50 ($550 × 1.03). It only cites a $550 category cap and says the proposed $575 exceeds the cap and annual limit.

### C-009

Identifies insufficient rate increase notice period (ISSUE_004) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L82))

- **Sonnet 4.6: Fail.** The criterion requires the memorandum to identify that the December 15, 2024 rate notice was submitted only 17 days before the January 1, 2025 effective date, violating a 60-day advance written notice requirement. The memorandum does state that the December 15, 2024 notice is 'after the November 1 deadline' and that 'OCG §§3.1--3.3 ... require notice by November 1 for a January 1 increase.' However, it does not specify the 60-day advance notice requirement, nor does it calculate the 17-day gap. The criterion specifically requires identification of the 60-day requirement and the 17-day shortfall. The memorandum only references a November 1 deadline without quantifying the notice period as 60 days or noting the 17-day gap. This is a partial match but does not fully satisfy the criterion as described.
- **GPT-5.5: Pass.** The memorandum states that the December 15, 2024 rate notice was late for January 1 increases, noting the OCG required notice by November 1 and that the December notice could not make the rates effective. Although it does not expressly say “17 days” or “60 days,” it identifies the insufficient advance notice procedural violation.

### C-010

Identifies paralegal rate exceeds OCG cap (ISSUE_005) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L90))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies that Margaret Hsu's proposed rate of $225/hr exceeds the OCG paralegal cap of $200/hr. This appears in the rates table (Section 2) noting '$225 — $200 paralegal cap — Above cap by $25/hr' and again in Section 3.1 stating '$225 exceeds the $200 paralegal cap.'
- **GPT-5.5: Pass.** The memorandum explicitly states that Margaret Hsu/Hu’s proposed paralegal rate is $225 and exceeds the $200 paralegal cap, including in the rates table and Hsu/Hu discussion.

### C-011

Quantifies Hu paralegal rate overage at $25/hr over $200 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L98))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 2 that Hsu/Hu is 'Above cap by $25/hr' and in the quantification paragraph: 'Hsu/Hu $18,500 (740 × $25)'. Both the per-hour overage ($25/hr) and the total financial impact ($18,500) are provided.
- **GPT-5.5: Pass.** The memorandum explicitly states that Margaret Hsu/Hu's proposed $225 rate is above the $200 paralegal cap by $25/hr and also quantifies the planned-hours impact as $18,500 (740 × $25).

### C-012

Identifies inadequate notice for Hu's addition to matter (ISSUE_006) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106))

- **Sonnet 4.6: Pass.** Section 3.1 explicitly states: 'The April 25, 2025 email requests approval to add "Margaret Hsu" effective April 28---approximately one business day later---and asks the GC to confirm... OCG §4.3 requires at least ten business days' advance notice and written approval.' This directly identifies the inadequate notice issue (approximately 1-2 business days vs. the required 10 business days).
- **GPT-5.5: Pass.** The memorandum expressly states that the April 25 email requested adding Margaret Hsu/Hu effective April 28, giving only about one business day’s notice, and explains this violates the OCG requirement of at least 10 business days’ advance notice and written GC approval.

### C-013

Identifies e-discovery vendor sole-source violation (ISSUE_007) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L114))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the Clearpoint e-discovery issue in Section 5 (Expenses). It states that the $285,000 exceeds the $200,000 life-of-matter threshold, that OCG §7.2(a) requires bids from at least three qualified vendors and documented GC approval before selection, that sole source requires express written approval and justification, and that bid/approval records are absent. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states that the Clearpoint e-discovery cost exceeds the $200,000 life-of-matter threshold, that OCG requires bids from at least three qualified vendors and GC approval, and that bid/approval records are absent.

### C-014

Identifies expert witness fees exceed pre-approval threshold (ISSUE_008) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L122))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Section 5 (Expenses table) that the two proposed experts at $90,000 and $85,000 each exceed the $75,000 per-expert threshold under OCG §7.3(a), and notes that pre-approval with CV, scope, fee schedule/estimated total and written selection justification is required before retention. It also notes that no approval package has been submitted ('The proposal says selection is underway and details will follow'). This satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies the two expert budgets ($90,000 and $85,000, totaling $175,000) as each exceeding the $75,000 per-expert threshold, states that GC pre-approval is required with CV, scope, fee schedule/estimate, and selection justification, and notes that the proposal only says details will follow/no approval package is shown.

### C-015

Identifies business class travel without pre-approval (ISSUE_009) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L130))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the business-class travel issue in Section 5 under the Travel expense row: 'The narrative budgets business-class airfare for Croft to Miami/New York based on scheduling demands. OCG §7.4(a) reimburses economy only; business class requires advance written approval and extraordinary circumstances.' It also requires removal of the business-class premium unless advance GC approval is obtained. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies that the travel budget includes business-class airfare for lead partner Croft and states that the OCG reimburses economy only unless advance written approval for business class is obtained.

### C-016

Identifies internal copying/printing as non-reimbursable (ISSUE_010) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L138))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the $15,000 internal copying/printing line item as non-reimbursable under OCG §§7.5 and 7.8(a), stating 'OCG §§7.5 and 7.8(a) prohibit reimbursement of internal copying/printing regardless of label' and directs to 'Delete the $15,000.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the $15,000 internal copying/printing/internal document reproduction line item as non-reimbursable, cites the OCG prohibition on internal copying/printing, and instructs that it be deleted/removed.

### C-017

Recommends removal of $15,000 copying/printing from budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L146))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the $15,000 internal copying/printing line item in Section 5 (Expenses), stating 'Delete the $15,000. Only third-party reproduction may be considered, with vendor, purpose, volume, unit cost and supporting third-party invoice.' This clearly recommends removal of the $15,000 internal copying/printing from the budget, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically identifies the $15,000 internal copying/printing charge as prohibited and recommends deleting/removing it from the budget, allowing only properly supported third-party reproduction costs if applicable.

### C-018

Identifies unauthorized post-trial/appeal reserve (ISSUE_011) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L154))

- **Sonnet 4.6: Pass.** Section 4 of the memorandum explicitly addresses the L700 reserve, stating that OCG §5.4 and Appendix A prohibit post-trial/appellate reserves unless the Company expressly requests appellate planning in writing, that no such written request or approval is included, and that the $92,000 L700 phase must be removed unless the GC first requests appellate planning in writing and separately approves a supported L700 budget. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the L700 post-trial/appellate reserve of $92,000/200 hours, states that no client request or approval is included, and explains that the OCGs prohibit such reserves unless expressly requested in writing and separately approved by the GC.

### C-019

Identifies Boyd Whitaker as unbudgeted phantom timekeeper (ISSUE_012) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L162))

- **Sonnet 4.6: Pass.** Section 1.2 of the memorandum explicitly addresses Boyd Whitaker as a 'disclosed but unpriced/unreconciled resource,' noting that the proposal describes approximately 60 hours of possible partner time in L400 but expressly excludes him from staffing totals and fee estimates, with no rate, detailed hours by phase, or GC approval provided. This directly identifies the phantom timekeeper issue described in the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies Boyd Whitaker as a disclosed but unpriced/unreconciled resource, notes approximately 60 hours of possible partner time in L400/summary judgment-related work, and states that his rate, phase hours, and fees are excluded from the staffing totals and budget, creating an unbudgeted cost risk.

### C-020

Notes Whitaker addition would require GC notice under OCGs ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L170))

- **Sonnet 4.6: Fail.** In section 1.2, the memorandum discusses Boyd Whitaker and states that OCG §§2.1 and 5.2 require the anticipated team and associated rates/hours to be budgeted, and that OCG §4.2 permits at most two partners but requires advance approval to add a second partner. However, the memorandum does not explicitly mention the 10 business days' notice requirement in connection with Whitaker's addition. The 10 business days' notice requirement is mentioned only in section 3.1 in connection with Margaret Hsu/Hu (OCG §4.3). The Whitaker discussion references needing 'advance approval' and 'written' approval, but does not cite the specific 10 business day notice requirement under the timekeeper addition provisions. The criterion specifically asks whether the memorandum notes that adding Whitaker would require written notice to and approval from the GC under the OCG timekeeper addition requirements (10 business days' notice). Since the 10 business days' notice requirement is not mentioned in connection with Whitaker, this criterion is not fully satisfied.
- **GPT-5.5: Fail.** The memorandum says Whitaker is unpriced/unapproved and should be added only if approved in writing, and references advance approval for a second partner. However, it does not connect Whitaker’s addition to the OCG timekeeper-addition procedure requiring written notice and GC approval with 10 business days’ advance notice. The 10-business-day requirement is discussed only for Hsu/Hu, not Whitaker.

### C-021

Identifies mock trial/jury consulting expense as requiring GC pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L178))

- **Sonnet 4.6: Pass.** The memorandum explicitly flags the $95,000 Silvermark mock trial/jury consulting expense in Section 5 (Expenses), noting that mock trials/jury consultants require advance GC approval above $10,000 under §7.7, and that no approval package is shown. The required action states to 'Obtain advance written approval and provide scope, fee basis, deliverables and justification.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum specifically identifies the Silvermark mock trial / jury consulting expense of $95,000 and states that mock trials/jury consultants require advance GC approval under the OCGs, with required action to obtain advance written approval.

### C-022

Does NOT flag two-partner limit as violated (DISTRACTOR_005) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L186))

- **Sonnet 4.6: Pass.** In section 1.2, the memorandum explicitly states: 'OCG §4.2 permits at most two partners (including partner-level of counsel), but requires advance approval to add a second partner if the approved plan included only one. Croft plus Whitaker would be two partners---not automatically a numerical breach.' The memo correctly notes that having both Croft and Whitaker does NOT violate the two-partner limit, and flags only the approval/notice requirements and the unbudgeted hours issue. It does not claim the two-partner cap is exceeded.
- **GPT-5.5: Pass.** The memorandum explicitly states that Croft plus Whitaker would be two partners and “not automatically a numerical breach,” while appropriately flagging Whitaker as unpriced/unapproved. It does not claim the two-partner cap is exceeded.

### C-023

Recommends reducing Croft's rate to $825/hr or obtaining waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L194))

- **Sonnet 4.6: Pass.** In Section 2, the memorandum explicitly states for Nathaniel Croft: 'Above absolute cap by $25/hr; a 3% increase from $825 would still be capped at $825.' The Action item then states: 'Use only the last rate actually approved in writing, subject to the applicable cap, until the GC confirms otherwise in writing.' This directs that Croft's rate be reduced to $825 (the last approved rate and the cap), and that any exception requires written GC confirmation. This satisfies the criterion of recommending reducing Croft's rate to $825/hr or obtaining a written waiver/exception.
- **GPT-5.5: Pass.** The memorandum specifically identifies Nathaniel Croft’s proposed $850/hr rate as above the $825 OCG cap and directs that only approved rates subject to the cap be used, which would reduce Croft’s rate to $825/hr.

### C-024

Recommends reducing Okeke's rate to comply with OCG caps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L202))

- **Sonnet 4.6: Pass.** The memorandum identifies Okeke's proposed rate of $575 as above the $550 cap by $25/hr and exceeding the 3% annual increase limit. In Section 2, the action item states: 'Use only the last rate actually approved in writing, subject to the applicable cap, until the GC confirms otherwise in writing.' This effectively recommends reducing Okeke's rate to the last approved rate ($550) or obtaining written GC approval. The memorandum clearly identifies the issue and recommends a specific remediation action (use only the approved rate subject to the cap, or get written GC approval), which satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum specifically identifies Samara Okeke’s proposed $575 rate as exceeding the $550 OCG cap and states that only the last written-approved rate, subject to the cap, should be used. This is a specific remediation that would reduce Okeke’s rate to $550 absent written GC approval.

### C-025

Recommends reducing Hu's rate to $200/hr or obtaining waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L210))

- **Sonnet 4.6: Pass.** The memorandum identifies that Margaret Hsu/Hu's proposed rate of $225 exceeds the $200 paralegal cap. In Section 2 (Rates and timekeeper approvals), it states '$225 exceeds the $200 paralegal cap' and notes the issue. In Section 3.1, it states 'Do not authorize/bill those hours until the timekeeper identity, qualifications, role, capped rate and GC approval are documented.' The action required is to use only the capped rate ($200) with GC approval. The memorandum also states in Section 2's action item: 'Use only the last rate actually approved in writing, subject to the applicable cap, until the GC confirms otherwise in writing.' This effectively recommends reducing to the $200 cap or obtaining written GC approval for any exception. The criterion is satisfied.
- **GPT-5.5: Pass.** The memorandum specifically identifies Hsu/Hu’s proposed $225/hr paralegal rate as above the $200 cap and recommends using only approved rates subject to the cap, documenting a capped rate and GC approval before billing. This satisfies the required remediation of reducing the rate to the $200 cap or obtaining approval/exception.

### C-026

Recommends competitive bidding for e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L218))

- **Sonnet 4.6: Pass.** In Section 5 (Expenses), the memorandum explicitly addresses the Clearpoint e-discovery issue and states: 'OCG §7.2(a) requires bids from at least three qualified vendors and documented GC approval before selection; sole source requires express written approval and justification.' The required action column states: 'Provide three-bid/evaluation record and approval, or a documented sole-source exception.' This clearly recommends competitive bidding among at least three vendors and submission of documentation to the GC, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically flags the Clearpoint e-discovery spend as exceeding the $200,000 threshold and states that the OCG requires bids from at least three qualified vendors plus documented GC approval. It recommends providing the three-bid/evaluation record and approval, or a documented sole-source exception, and repeats this in the required resubmission package.

### C-027

Recommends submitting expert CVs and scope for GC pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L226))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the expert witness fee issue in Section 5 (Expenses). For the two experts at $90,000 and $85,000, it notes that each exceeds the $75,000 per expert threshold under OCG §7.3(a), which requires pre-approval before retention with CV, scope, fee schedule/estimated total and written selection justification. The required action states: 'Submit a separate complete approval package for each expert before retention.' This directly recommends submitting expert CVs and scope documents for GC pre-approval, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum identifies the expert fees over the $75,000 threshold and states that OCG §7.3(a) requires GC pre-approval before retention with the expert’s CV, scope, fee schedule/estimated total, and selection justification. It also directs submission of a separate complete approval package for each expert before retention.

### C-028

Assigns severity levels to identified issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L234))

- **Sonnet 4.6: Pass.** The memorandum includes a 'Priority findings at a glance' table that explicitly assigns severity levels (Critical, High, Medium) to each identified issue. This satisfies the criterion of assigning severity levels to identified issues.
- **GPT-5.5: Pass.** The memorandum includes a 'Priority findings at a glance' table that assigns severity/priority levels such as Critical, High, and Medium to the identified issues.

### C-029

Budget inconsistency rated as Critical or High severity ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242))

- **Sonnet 4.6: Pass.** The agent's output uses a three-tier severity scale: Critical, High, and Medium. The fee budget reconciliation discrepancy ($116,050 difference between phase-based fees and staffing-table fees) is listed in the 'Priority findings at a glance' table under the 'Critical' severity level, which is the highest tier in the scale used. This satisfies the criterion that the issue be assigned Critical or High severity.
- **GPT-5.5: Pass.** The output identifies the $116,050 fee reconciliation discrepancy and labels the issue 'Critical' in the priority findings table, satisfying the requirement that it be rated Critical or High.

### C-030

Rate cap violations rated as Critical or High severity ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L250))

- **Sonnet 4.6: Pass.** The agent's output groups rate cap violations (Croft, Okeke, Hsu/Hu exceeding OCG caps) under the 'Critical' priority finding: 'Rates late, unapproved and/or above caps; Hsu not approved' is listed as Critical in the priority findings table. This satisfies the criterion that at least one rate cap violation is assigned Critical or High severity.
- **GPT-5.5: Pass.** The output assigns a Critical priority to the issue 'Rates late, unapproved and/or above caps; Hsu not approved,' which encompasses the Croft, Okeke, and Hsu/Hu rate cap violations. Thus at least one rate cap violation is rated Critical/High.

### C-031

Notes at least two compliant budget areas ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L258))

- **Sonnet 4.6: Pass.** The memorandum affirmatively identifies multiple compliant areas. In Section 3.5, it states the efficiency ratio passes: 'Yoon and Novak total 1,400 of 3,000 attorney hours (46.67%), above the 40% threshold' and 'Okeke is budgeted at 980/3,000 attorney hours (32.67%), above the 15% significant-role threshold.' In Section 7, it also notes 'The proposal uses the standard Appendix A codes L200--L700 and the phase-hour totals tie to the timekeeper hours.' That gives at least three compliant areas: (a) staffing efficiency ratio, (b) Okeke's diversity/significant-role percentage, and (e) UTBMS phase code usage. The criterion requires at least two, so this passes.
- **GPT-5.5: Pass.** The memorandum affirmatively identifies multiple compliant areas: it states the staffing efficiency ratio is correct at 46.67% above the 40% threshold, Okeke's significant-role percentage is 32.67% above the 15% threshold, and also notes use of standard Appendix A phase codes. Thus it notes at least two compliant budget areas.

### C-032

Recommends removal or separate approval for L700 appeal reserve ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L266))

- **Sonnet 4.6: Pass.** Section 4 of the memorandum explicitly addresses the L700 reserve, stating that OCG §5.4 and Appendix A prohibit post-trial/appellate reserves unless expressly requested in writing by the client. It recommends removing the $92,000 L700 phase and all corresponding staffing hours unless the GC first requests appellate planning in writing and separately approves a supported L700 budget. This directly satisfies the criterion of recommending removal or separate express written approval for the L700 appeal reserve.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the $92,000 L700 post-trial/appellate reserve as prohibited absent express written request/approval, recommends removing the L700 phase and corresponding staffing hours unless the GC requests appellate planning in writing and separately approves a supported L700 budget, and reiterates this in the resubmission requirements.

### C-033

Cites OCG rate cap provisions specifically ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L274))

- **Sonnet 4.6: Pass.** The memorandum explicitly references specific OCG rate cap amounts when discussing rate violations. In Section 2, the table lists the OCG cap for each timekeeper: Croft's cap is $825, Okeke's cap is $550, Yoon's cap is $425, Novak's cap is $375, and Hsu/Hu's paralegal cap is $200. These specific dollar amounts are cited alongside the proposed rates and the identified violations. The memorandum does not merely make generic statements about rates being too high but provides the actual cap figures for each timekeeper category.
- **GPT-5.5: Pass.** The memorandum specifically cites OCG rate cap amounts when discussing rate violations, including the $825 partner cap, $550 senior associate cap, $425/$375 associate caps, and $200 paralegal cap, and applies them to individual timekeepers.

### C-034

Cites OCG 60-day notice requirement for rate increases ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L282))

- **Sonnet 4.6: Fail.** The memorandum discusses the late rate increase notice in Section 2, noting that the December 15, 2024 notice is after the November 1 deadline and that it does not constitute approval. However, it references a 'November 1' deadline for notice (implying a ~45-day notice period before January 1) rather than a specific '60-day advance written notice requirement.' The criterion requires the memorandum to specifically reference the OCG's 60-day advance written notice requirement and note that the actual notice period was approximately 17 days. Neither the 60-day requirement nor the ~17-day actual notice period is mentioned anywhere in the document.
- **GPT-5.5: Fail.** The memorandum discusses the rate notice as late and says notice was required by November 1 for a January 1 increase, but it does not specifically cite a 60-day advance written notice requirement or state that the actual notice period was approximately 17 days.

### C-035

Cites OCG 10-business-day notice requirement for new timekeepers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290))

- **Sonnet 4.6: Pass.** Section 3.1 of the memorandum explicitly states: 'OCG §4.3 requires at least ten business days' advance notice and written approval' when discussing Margaret Hsu's addition. It also notes the actual notice was approximately one business day ('requests approval to add
- **GPT-5.5: Fail.** The memorandum does cite OCG §4.3’s requirement for at least ten business days’ advance notice and written GC approval for Hsu/Hu’s addition. However, it states the actual notice was “approximately one business day later,” not approximately two business days as required by the criterion.

### C-036

Recommends reconciling the two fee totals before approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L298))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the $116,050 gap between the phase fee total ($1,708,950) and the staffing-table total ($1,825,000) in section 1.1, and in the Action item states: 'Require one revised fee schedule in which each phase total equals the allocated hours times the applicable approved rates, and the grand total rolls through to expenses. Do not approve either fee total until corrected.' This directly recommends reconciling the two fee totals before approval.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the $116,050 gap between the phase fee estimate ($1,708,950) and staffing-table fees ($1,825,000), states not to approve either fee total until corrected, and directs the firm to rebuild/reconcile the phase-by-phase fees to staffing hours and approved rates in a revised submission.

### C-037

Identifies Croft's rate increase notice also has percentage issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L306))

- **Sonnet 4.6: Pass.** The memorandum addresses Croft's rate issue in Section 2 (Rates and timekeeper approvals). It states: 'Nathaniel Croft: $850 proposed, $825 cap; 2024 approved $825. Above absolute cap by $25/hr; a 3% increase from $825 would still be capped at $825.' This explicitly notes that even if a 3% increase were applied to $825 (which would yield $849.75, rounded to ~$850), the result would still be capped at $825 because $825 is the absolute OCG partner cap. The memorandum thus addresses the interaction between the percentage increase and the absolute rate cap, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum states Croft’s proposed $850 rate is above the absolute $825 partner cap and adds that “a 3% increase from $825 would still be capped at $825,” thereby addressing the interaction between the annual percentage increase and the absolute cap, even though it does not spell out the $849.75 rounding detail.

### C-038

Recommends obtaining pre-approval for business class travel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L314))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses business-class travel in Section 5 under the Travel expense line item. It states: 'Remove business-class premium unless advance GC approval is obtained on an extraordinary-circumstances basis; otherwise limit reimbursement to lowest available economy fare.' This clearly recommends either obtaining written pre-approval from the GC for business class travel or revising the budget to economy-class-only travel, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum specifically flags business-class airfare and recommends removing the premium unless advance written GC approval is obtained, otherwise limiting reimbursement to economy fare.

### C-039

Quantifies expert fee per-expert average as ~$87,500 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L322))

- **Sonnet 4.6: Fail.** The memorandum mentions the two expert fees ($90,000 and $85,000) and notes that each exceeds the $75,000 per-expert threshold, but it never calculates or states a per-expert average of ~$87,500 ($175,000 ÷ 2). The criterion specifically requires that the per-expert average be calculated or stated as approximately $87,500 and compared against the $75,000 threshold. The agent only lists the individual amounts and compares each individually to the threshold, without computing the average.
- **GPT-5.5: Fail.** The memorandum identifies two expert amounts ($90,000 and $85,000) and notes each exceeds the $75,000 pre-approval threshold, but it does not calculate or state the per-expert average of approximately $87,500 ($175,000 / 2).

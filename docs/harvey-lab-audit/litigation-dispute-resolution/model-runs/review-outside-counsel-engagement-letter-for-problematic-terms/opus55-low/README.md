# Claude Opus 5.5 (low): Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 42 of 45 criteria; GPT-5.5 passed 42 of 45 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [engagement-review-memo.docx](output/engagement-review-memo.docx) ([read as Markdown](output/engagement-review-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Identifies Morrow's rate ($1,050/hr) exceeds OCG partner cap ($850/hr) | Pass | Pass |
| [C-002](#c-002) | Identifies Alcott's rate ($975/hr) exceeds OCG partner cap ($850/hr) | Pass | Pass |
| [C-003](#c-003) | Identifies Dasgupta's rate ($625/hr) exceeds OCG senior associate cap ($575/hr) | Pass | Pass |
| [C-004](#c-004) | Identifies Marsh's rate ($475/hr) exceeds OCG junior associate cap ($425/hr) | Pass | Pass |
| [C-005](#c-005) | Identifies Solano's paralegal rate ($275/hr) exceeds OCG cap ($225/hr) | Pass | Pass |
| [C-006](#c-006) | Identifies blended rate ($685/hr) exceeds OCG blended rate cap ($625/hr) | Pass | Pass |
| [C-007](#c-007) | Identifies 5% automatic annual rate escalation as problematic | Pass | Pass |
| [C-008](#c-008) | Notes 5% escalation is above market standard (3-4%) | **Fail** | **Fail** |
| [C-009](#c-009) | Flags non-refundable $250,000 retainer as ethically problematic | Pass | Pass |
| [C-010](#c-010) | Identifies invoice submission timeline deviation (60 vs. 45 days) | Pass | Pass |
| [C-011](#c-011) | Identifies expense threshold deviation ($15,000 vs. $5,000) | Pass | Pass |
| [C-012](#c-012) | Identifies business-class travel provision conflicts with OCG economy-only policy | Pass | Pass |
| [C-013](#c-013) | Flags firm's sole staffing discretion vs. OCG 14-day notice requirement | Pass | Pass |
| [C-014](#c-014) | Flags contract attorney usage at $350/hr as unaddressed by OCG | Pass | Pass |
| [C-015](#c-015) | Identifies work product lien conflicts with OCG ownership provision | Pass | Pass |
| [C-016](#c-016) | Notes work product lien could prejudice client's defense in active litigation | **Fail** | **Fail** |
| [C-017](#c-017) | Flags 15% client termination fee as problematic | Pass | Pass |
| [C-018](#c-018) | Flags malpractice liability cap as disproportionate to matter size and potentially ethically impermissible | Pass | Pass |
| [C-019](#c-019) | Flags client indemnification of law firm as unusual and ethically suspect | Pass | Pass |
| [C-020](#c-020) | Notes willful misconduct carve-out is narrower than negligence standard | Pass | Pass |
| [C-021](#c-021) | Identifies MedBridge/NovaTech conflict of interest | Pass | Pass |
| [C-022](#c-022) | Notes firm's 'no conflict' characterization is inadequate | Pass | Pass |
| [C-023](#c-023) | Flags broad adverse-representation waiver as compounding conflict risk | Pass | Pass |
| [C-024](#c-024) | Identifies firm insurance ($10M/$20M) is below OCG minimum ($25M/$50M) | Pass | Pass |
| [C-025](#c-025) | Identifies success fee embedded in engagement letter vs. OCG separate agreement requirement | Pass | Pass |
| [C-026](#c-026) | Notes success fee is uncapped and potentially very large (up to ~$1.42M) | Pass | Pass |
| [C-027](#c-027) | Flags affiliated e-discovery vendor (CrossPoint) as financial conflict | Pass | Pass |
| [C-028](#c-028) | Identifies $380K e-discovery cost excluded from $2.4M budget | Pass | Pass |
| [C-029](#c-029) | Identifies scope ambiguity regarding appeals | **Fail** | **Fail** |
| [C-030](#c-030) | Flags mandatory arbitration in D.C. as disadvantageous to NC-based client | Pass | Pass |
| [C-031](#c-031) | Flags marketing use of client name without adequate consent | Pass | Pass |
| [C-032](#c-032) | Identifies firm termination notice period (30 days) vs. OCG (60 days + consent) | Pass | Pass |
| [C-033](#c-033) | Recommendations are provided and differentiated across issues | Pass | Pass |
| [C-034](#c-034) | Cross-references Morrow email to engagement letter conflict waiver | Pass | Pass |
| [C-035](#c-035) | Cross-references CrossPoint proposal to budget exclusion in engagement letter | Pass | Pass |
| [C-036](#c-036) | Cross-references staffing plan rates against OCG rate caps | Pass | Pass |
| [C-037](#c-037) | Identifies inadequacy of conflicts clearance in Alcott email | Pass | Pass |
| [C-038](#c-038) | Correctly identifies case as NovaTech v. Pinnacle with $14.2M exposure | Pass | Pass |
| [C-039](#c-039) | Recommends requiring competitive bidding for e-discovery vendor | Pass | Pass |
| [C-040](#c-040) | Recommends requiring informed written consent for conflict/adverse representation | Pass | Pass |
| [C-041](#c-041) | Recommends reducing or eliminating the malpractice liability cap | Pass | Pass |
| [C-042](#c-042) | Recommends removing or restructuring client indemnification clause | Pass | Pass |
| [C-043](#c-043) | Recommends removing or restructuring the 15% termination fee | Pass | Pass |
| [C-044](#c-044) | Recommends requiring firm insurance to meet OCG minimums | Pass | Pass |
| [C-045](#c-045) | Recommends removing or restructuring the work product lien | Pass | Pass |

## Judge reasoning

### C-001

Identifies Morrow's rate ($1,050/hr) exceeds OCG partner cap ($850/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L18))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Sandra K. Morrow's proposed rate of $1,050/hr against the OCG cap of $850/hr, noting a $200 excess (23.5%) in the rates table under Section IV.B.4, and also lists this in the Issues Matrix as item #10.
- **GPT-5.5: Pass.** The memo specifically identifies Sandra K. Morrow’s proposed rate as $1,050/hr, the OCG cap as $850/hr, and the $200/hr overage in the hourly rates table.

### C-002

Identifies Alcott's rate ($975/hr) exceeds OCG partner cap ($850/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L26))

- **Sonnet 4.6: Pass.** The memo explicitly identifies James Alcott's rate in the rates table under Section IV.B.4: 'James Alcott | Equity Partner | 19 | $975 | $850 | $125 (14.7%) | 120 | $15,000'. This clearly shows the $975/hr proposed rate, the $850 OCG cap, and the $125 excess, satisfying the criterion.
- **GPT-5.5: Pass.** The memo specifically lists James Alcott as an Equity Partner with a proposed rate of $975, the OCG cap of $850, and an excess of $125 (14.7%), and also recommends restating Alcott's rate at $850.

### C-003

Identifies Dasgupta's rate ($625/hr) exceeds OCG senior associate cap ($575/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L34))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Priya Dasgupta's proposed rate of $625/hr against an OCG cap of $575/hr, noting a $50 excess (8.7%) in the rates table in Section IV.B.4, and again in Section VII where it states the required rate for Dasgupta is $575.
- **GPT-5.5: Pass.** The memo explicitly identifies Priya Dasgupta as a Senior Associate with a proposed rate of $625, an OCG cap of $575, and a $50/hour overage.

### C-004

Identifies Marsh's rate ($475/hr) exceeds OCG junior associate cap ($425/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L42))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Kevin Marsh's rate in the rates table under Section IV.B.4: 'Kevin Marsh | Junior Associate (<5) | 3 | $475 | $425 | $50 (11.8%) | 480 | $24,000'. This clearly shows the proposed rate of $475/hr exceeds the OCG cap of $425/hr by $50/hr.
- **GPT-5.5: Pass.** The memo expressly identifies Kevin Marsh as a junior associate with a proposed rate of $475/hr, an OCG cap of $425/hr, and a $50/hr overage.

### C-005

Identifies Solano's paralegal rate ($275/hr) exceeds OCG cap ($225/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L50))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Rita Solano's paralegal rate in the rates table under Section IV.B.4, showing her proposed rate of $275 vs. the OCG cap of $225, with a $50 excess (22.2%) and estimated excess cost of $17,500. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies Rita Solano as a paralegal with a proposed rate of $275, an OCG cap of $225, and a $50/hr (22.2%) excess in the hourly rates table, and also restates her capped rate as $225 in the required revisions.

### C-006

Identifies blended rate ($685/hr) exceeds OCG blended rate cap ($625/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L58))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Issue #12 of the Issues Matrix that the blended rate of $685 exceeds the $625 cap, and further elaborates in Section IV.B.6 ('Blended Rate Alternative') that '$685/hour blended rate exceeds the $625 cap in OCG §§ 3.3 and 9.3.'
- **GPT-5.5: Pass.** The memo explicitly identifies the proposed $685/hour blended rate as exceeding the OCG $625/hour cap, including in the issues matrix and detailed blended-rate analysis.

### C-007

Identifies 5% automatic annual rate escalation as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L66))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the 5% automatic annual rate escalation in Section B.5 ('Automatic 5% Annual Rate Escalation (High)'), noting that EL § 3.3, Exhibit A and Staffing Plan § 5 impose a 5% increase every January 1 'automatically' and 'without prior notice to or approval by the Client,' and that OCG § 3.2 gives automatic escalation clauses 'no force or effect.' It also appears in the Issues Matrix as item #11. The memo clearly flags this as problematic and recommends deleting the clause.
- **GPT-5.5: Pass.** The memo explicitly flags the automatic 5% annual rate escalation as a high-severity issue, noting it applies without notice or approval, conflicts with OCG § 3.2, and should be deleted or subject to written approval/client consent.

### C-008

Notes 5% escalation is above market standard (3-4%) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L74))

- **Sonnet 4.6: Fail.** The memo discusses the 5% automatic annual rate escalation in Section B.5 and elsewhere, but it only notes that the clause is prohibited by OCG § 3.2 and calculates the financial impact. It never compares the 5% rate to market-standard escalation rates (typically 3-4%) or characterizes 5% as above-market or excessive relative to industry norms. The criterion specifically requires the memo to note or imply that 5% is above typical market rates of 3-4%.
- **GPT-5.5: Fail.** The memo identifies the 5% annual escalation as problematic under the OCG, automatic, unapproved, and budget-impacting, but it does not compare 5% to typical market escalation rates of 3–4% or characterize the 5% escalation as above-market or excessive.

### C-009

Flags non-refundable $250,000 retainer as ethically problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L82))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the $250,000 non-refundable retainer in Section IV.B (Issue #8, 'Non-Refundable Engagement Retainer'). It flags it as 'High' severity, notes that OCG § 3.6 requires retainers to be held in trust and be refundable, and specifically cites 'N.C. RPC 1.5 and 1.16(d), and the parallel D.C. rules' stating that 'a fee labeled "non-refundable" must still be reasonable and any unearned part refunded.' It also notes the retainer is deposited into the firm's operating account rather than trust, and that it would be forfeited on early termination. The memo recommends deleting it or replacing it with a refundable trust-account deposit. This clearly satisfies the criterion of flagging the non-refundable retainer as ethically problematic under fee reasonableness rules.
- **GPT-5.5: Pass.** The memo expressly flags the $250,000 non-refundable, earned-upon-receipt retainer as a high-severity issue, cites ethical rules including fee reasonableness/refund obligations, notes the risk if the engagement ends early, and recommends deleting it or restructuring as a refundable trust-account deposit.

### C-010

Identifies invoice submission timeline deviation (60 vs. 45 days) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L90))

- **Sonnet 4.6: Pass.** The memo explicitly identifies this deviation in Section C (Billing, Payment and Expenses) in the table, noting 'Invoice submission: Within 60 days of month-end' vs. OCG requirement of 'Within 45 days; >45 may be reduced; >90 not paid' under § 3.4. This clearly identifies the 60 vs. 45 day discrepancy.
- **GPT-5.5: Pass.** The memo explicitly identifies the invoice submission deviation, noting that the engagement letter permits submission within 60 days of month-end while the OCG requires submission within 45 days, including in the issues matrix and billing table.

### C-011

Identifies expense threshold deviation ($15,000 vs. $5,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L98))

- **Sonnet 4.6: Pass.** The memo explicitly identifies this issue in Issue #20 of the Issues Matrix: 'Expenses: $15,000 pre-approval threshold vs. $5,000' rated as High severity. It is also detailed in the billing/expenses table in Section C, which states 'Expense pre-approval: Only above $15,000 per item' vs. OCG requirement of 'Any single expense above $5,000, all categories' under § 5.2. The Required Revisions section also includes '$5,000 pre-approval threshold' as a required change. This clearly identifies the $15,000 vs. $5,000 deviation.
- **GPT-5.5: Pass.** The memo expressly identifies the expense pre-approval deviation: the engagement letter sets a $15,000 per-item threshold while the OCG requires prior approval for any single expense above $5,000, and it recommends revising to the $5,000 threshold. Although it does not spell out the $10,000 gap in those exact words, the deviation is clearly identified.

### C-012

Identifies business-class travel provision conflicts with OCG economy-only policy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L106))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the business-class travel conflict in the billing/expenses table under Section C, noting 'Business-class air for partners on flights >2 hrs' versus the OCG requirement of 'Economy only, "under any circumstances"' (§ 5.3). This is also listed in the required revisions section as 'economy airfare.'
- **GPT-5.5: Pass.** The memo explicitly identifies that the engagement letter permits business-class airfare for partners and contrasts it with the OCG requirement of economy-only travel, including in the issues matrix and billing/expenses table.

### C-013

Flags firm's sole staffing discretion vs. OCG 14-day notice requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L114))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section D (Staffing) that 'Sole discretion over staffing (EL § 2; Staffing Plan §§ 3, 6)' contradicts OCG § 6.2, which states outside counsel 'does not have unilateral discretion.' It further specifies that 'Changes at the senior associate level or above require 14 days' written notice and Pinnacle's approval.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly flags that the engagement letter/staffing plan gives the firm “sole discretion” over staffing and explains this contradicts the OCG requirement that changes at the senior associate level or above require 14 days’ written notice and Pinnacle approval.

### C-014

Flags contract attorney usage at $350/hr as unaddressed by OCG ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L122))

- **Sonnet 4.6: Pass.** The memo explicitly addresses contract attorney usage at $350/hr in multiple places. In the Issues Matrix (item 14), it flags 'Contract attorneys at up to $350/hr without prior approval' as a High severity issue citing OCG § 6.3. In Section D (Staffing), it states contract attorneys 'need prior written approval with qualifications, scope and duration (§ 6.3). Rates are capped at $225 for document review and $425 for substantive work.' The memo identifies that the proposed $350/hr rate is problematic and requires prior approval, satisfying the criterion.
- **GPT-5.5: Pass.** The memo explicitly raises the contract attorney issue, noting contract attorneys at up to $350/hr without prior approval, stating they require prior written approval/client approval, and discussing applicable rate caps and usage controls.

### C-015

Identifies work product lien conflicts with OCG ownership provision ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L130))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this in Section H (Work Product, Confidentiality and Marketing): 'OCG § 7.1 provides that Pinnacle owns all work product absolutely, "not contingent upon payment." OCG § 7.2 prohibits any lien, and asserting one is a material breach. Replace § 15 with the OCG language and an express lien waiver.' It also appears in the Issues Matrix as item #6 (Critical): 'Work product becomes Pinnacle's only on full payment; retaining lien (EL § 15)' citing OCG §§ 7.1, 7.2. This clearly identifies the conflict between the firm's retaining lien and the OCG's ownership provision.
- **GPT-5.5: Pass.** The memo expressly identifies that the engagement letter’s Section 15 makes work product/files contingent on full payment and asserts a retaining lien, and states this conflicts with OCG §§ 7.1 and 7.2, under which Pinnacle owns all work product absolutely and liens on files/work product are prohibited.

### C-016

Notes work product lien could prejudice client's defense in active litigation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L138))

- **Sonnet 4.6: Fail.** The memo discusses the retaining lien in Section III (Issue #6, Critical severity) and Section IV.H, noting that OCG §§ 7.1 and 7.2 prohibit any lien and that asserting one is a material breach. However, the memo does not explain the practical prejudice to Pinnacle's defense in the active litigation — for example, that a billing dispute could result in HB&C withholding files, work product, or case materials mid-litigation, leaving Pinnacle unable to defend itself effectively. The memo treats the lien primarily as a contractual/OCG compliance issue and an ownership issue, without connecting it to the specific risk that arises when a lien is asserted during pending litigation (i.e., that Pinnacle could lose access to critical defense materials at a vulnerable moment). The criterion requires explanation of the practical prejudice or risk of the lien during active litigation, which is absent.
- **GPT-5.5: Fail.** The memo identifies the retaining lien as problematic and states it conflicts with the OCG, including that file transfer on termination would be subject to the lien. However, it does not explain the practical risk that withholding files during a billing dispute could prejudice Pinnacle’s defense in the active litigation or impair transition to new counsel during the pending case.

### C-017

Flags 15% client termination fee as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L146))

- **Sonnet 4.6: Pass.** The memo clearly identifies the 15% termination fee in multiple places. In the Issues Matrix (item #7), it is listed as 'Critical' severity: '15% termination fee on Client termination (EL § 9)' against OCG § 8.1. In Section G (Termination and Withdrawal), it explicitly states: 'A 15% fee on all fees billed, payable within 30 days, is void under OCG § 8.1. The OCG allows no termination fee, penalty, wind-down surcharge or minimum fee, and Pinnacle's only obligation is to pay for services properly rendered. Calling it "not intended as a penalty" does not change that. Delete.' This satisfies the criterion by flagging the termination fee as problematic and noting it functions as a penalty clause that restricts the client's right to terminate.
- **GPT-5.5: Pass.** The memo explicitly identifies the 15% termination fee as a critical issue, describes it as a fee on all fees billed, states it is void under the OCG, and notes that calling it not a penalty does not change its nature. It recommends deletion and ties it to Pinnacle's right to terminate/change counsel.

### C-018

Flags malpractice liability cap as disproportionate to matter size and potentially ethically impermissible ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L154))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the malpractice liability cap in Section IV.A.3, noting it is 'the lesser of $1M or fees actually paid' and that 'At signing, that is effectively $0.' It also references the $14.2M damages claim in the context of the insurance discussion, making the disproportionality clear. Additionally, it cites N.C. RPC 1.8(h)(1) and D.C. RPC 1.8(g)(1) as prohibiting agreements that prospectively limit malpractice liability without independent representation, directly addressing the ethical impermissibility angle. The issue is rated 'Critical' in the issues matrix.
- **GPT-5.5: Pass.** The memo explicitly identifies Engagement Letter § 13 as capping malpractice liability at the lesser of $1M or fees paid, notes this is effectively $0 at signing and inadequate relative to the $14.2M claim, and states that prospective malpractice limitations are prohibited/restricted under RPC 1.8(h) unless the client is independently represented. It flags the issue as Critical and recommends deletion.

### C-019

Flags client indemnification of law firm as unusual and ethically suspect ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L162))

- **Sonnet 4.6: Pass.** The memo explicitly flags the client indemnification clause (EL § 14) as a Critical issue. It notes that Pinnacle would indemnify and defend the firm against all claims except those arising 'solely' from willful misconduct, which would cover the firm's own negligence and malpractice claims. The memo states this is inconsistent with the OCG framework and, combined with § 13's liability cap, would shift essentially all professional risk to Pinnacle. It also references RPC 1.8(h) in the issues matrix for the liability cap section, and the detailed analysis ties the indemnification clause to the liability cap as together creating an impermissible risk shift. The memo recommends deleting § 14 in full. This clearly satisfies the criterion of flagging the indemnification as unusual, risk-shifting, and ethically suspect.
- **GPT-5.5: Pass.** The memo expressly flags the indemnification clause as a critical problem, explaining that Pinnacle would indemnify and defend the firm for claims arising from the engagement except those arising solely from willful misconduct, thereby covering the firm’s own negligence/malpractice and shifting professional risk from the firm to the client. It also frames the related liability-shifting provisions as ethically questionable and discusses RPC 1.8(h) in connection with the liability cap.

### C-020

Notes willful misconduct carve-out is narrower than negligence standard ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L170))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this in Section IV.A.3 (Limitation of Liability and Indemnification): '§ 14 Indemnification. Pinnacle would indemnify and defend the firm against all claims "arising out of or relating to the engagement," except those arising "solely" from willful misconduct. That would cover the firm's own negligence and malpractice claims.' This directly identifies that the 'solely willful misconduct' carve-out is too narrow and fails to exclude negligence or malpractice, meaning Pinnacle would be indemnifying the firm for its own negligent acts.
- **GPT-5.5: Pass.** The memo explicitly states that the indemnification clause excepts only claims arising 'solely' from willful misconduct and would therefore cover the firm’s own negligence and malpractice, shifting professional risk to Pinnacle. This directly identifies the willful misconduct carve-out as narrower than a negligence standard.

### C-021

Identifies MedBridge/NovaTech conflict of interest ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L178))

- **Sonnet 4.6: Pass.** The memo extensively identifies and analyzes the MedBridge/NovaTech conflict of interest. It is listed as Issue #1 in the Issues Matrix with 'Critical' severity, and Section IV.A.1 provides detailed analysis explaining that HB&C currently represents MedBridge Therapeutics, which holds approximately 8% equity in NovaTech (the adverse party), exceeding the OCG's 5% material financial interest threshold. The memo discusses the OCG requirements, the defective conflicts clearance, and the substantive risks of this concurrent representation.
- **GPT-5.5: Pass.** The memo explicitly identifies HB&C's concurrent representation of MedBridge Therapeutics, notes MedBridge holds approximately 8% equity in NovaTech, and characterizes this as an undisclosed/defective conflict requiring disclosure and GC consent.

### C-022

Notes firm's 'no conflict' characterization is inadequate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L186))

- **Sonnet 4.6: Pass.** The memo extensively challenges the firm's 'no conflict' characterization. It specifically notes that Ms. Morrow called the MedBridge relationship a 'non-issue,' that Mr. Alcott's conflicts clearance email only searched NovaTech, its principals, and Prescott Lane without mentioning MedBridge at all, and that EL §11 states there are 'no current conflicts' — which directly contradicts the firm's own October 3 disclosure. The memo calls this a 'candor concern as well as a compliance defect' and details why the clearance is inadequate under OCG §2.2(a)-(d). It also raises substantive conflict-of-interest concerns under N.C. RPC 1.7(a)(2) regarding the 8% equity stake exceeding the 5% threshold.
- **GPT-5.5: Pass.** The memo expressly challenges the firm's 'no current conflicts' / 'no issues' characterization, noting that Morrow dismissed the MedBridge issue as a 'non-issue,' Alcott's clearance omitted MedBridge, and the engagement letter's 'no current conflicts' statement contradicts the disclosed MedBridge/NovaTech equity connection. It analyzes why this is inadequate under the OCG and requires formal disclosure and GC consent.

### C-023

Flags broad adverse-representation waiver as compounding conflict risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L194))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the blanket advance waiver in EL § 11 as a Critical issue (Issue #2 in the Issues Matrix). In Section IV.A.1, the memo discusses the advance waiver in detail, noting it asks Pinnacle to consent in advance to 'any unrelated adverse representation, specifically including other healthcare companies, healthcare litigation, and related regulatory matters, with no notice.' It connects this directly to the MedBridge/NovaTech conflict context, noting that Ms. Morrow described it as the firm's 'customary provision' and that OCG § 2.2 states 'Blanket or advance waivers of future conflicts are not acceptable.' The memo treats the advance waiver as compounding the existing MedBridge conflict risk by requiring deletion of the clause as part of the required actions. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly flags EL § 11’s blanket advance waiver permitting unrelated adverse representations, including other healthcare companies/litigation, without notice, labels it a critical conflicts issue, and discusses it in the same conflicts section as the MedBridge/NovaTech conflict with a required deletion. This satisfies the criterion.

### C-024

Identifies firm insurance ($10M/$20M) is below OCG minimum ($25M/$50M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L202))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Issue #3 of the Issues Matrix that HB&C carries '$10M/$20M coverage vs. required $25M/$50M' and further elaborates in Section IV.A.2 that 'Engagement letter § 12 discloses $10M per occurrence / $20M aggregate. That is 40% of each OCG minimum ($25M / $50M).' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies that HB&C carries $10M per occurrence / $20M aggregate professional liability insurance and states this is below the OCG-required $25M / $50M minimum, including in the executive summary, issues matrix, and detailed insurance section.

### C-025

Identifies success fee embedded in engagement letter vs. OCG separate agreement requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L210))

- **Sonnet 4.6: Pass.** The memo explicitly identifies this issue in Section IV.B.7 (Success Fee), stating that 'OCG § 9.2 prohibits this: success fees must be in a separate written agreement approved by the General Counsel before execution. It also says a success-fee provision in an engagement letter does not bind Pinnacle.' The memo also notes the fee structure (10% of savings below $7M) and lists it as a High severity issue (#8) in the Issues Matrix with the note 'Success fee embedded in the letter; no cap; cliff structure; not a separate GC-approved agreement (EL § 10)'. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that the success fee is embedded in the engagement letter, that OCG § 9.2 requires success fees to be in a separate written agreement approved by the General Counsel, and that the proposed 10% savings-based bonus lacks required procedural compliance.

### C-026

Notes success fee is uncapped and potentially very large (up to ~$1.42M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L218))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section IV.B.7 that the success fee has 'No dollar cap (§ 9.2(c))' and that 'The fee is 10% × ($14.2M − resolution amount), so the maximum is $1,420,000 if Pinnacle pays nothing.' The success fee table in Section V also shows '$0 (dismissal / defense verdict)' yields '$1,420,000' with the note 'Maximum; no cap stated.' The Executive Summary also references 'Up to $1,420,000' as the success fee. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies the success fee as uncapped/no cap and calculates the maximum as 10% × $14.2M = $1,420,000 if Pinnacle pays nothing, including in the executive summary, issues matrix, detailed analysis, and financial illustration.

### C-027

Flags affiliated e-discovery vendor (CrossPoint) as financial conflict ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L226))

- **Sonnet 4.6: Pass.** The memo explicitly identifies CrossPoint Analytics as a 'strategic partner' of HB&C, notes the possible financial interest not disclosed, flags that no competitive bid was conducted, and raises OCG § 1.2 concerns about vendors in which the firm may have a financial interest. Section E (E-Discovery Vendor) is entirely dedicated to this issue, including requiring HB&C to certify whether it or any attorney has 'any ownership, revenue-share, referral, rebate or other financial arrangement with CrossPoint.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies CrossPoint as HB&C’s “strategic partner,” notes possible financial interests such as ownership/revenue-share/referral arrangements, states no competitive bid or Pinnacle approval occurred, and recommends disclosure and competitive bidding to address the conflict/cost-control issue.

### C-028

Identifies $380K e-discovery cost excluded from $2.4M budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L234))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the $380,000 CrossPoint e-discovery cost as excluded from the $2.4M litigation budget in multiple places. In the Executive Summary financial impact table, it lists 'CrossPoint e-discovery (outside budget): $380,000' and notes 'Firm-affiliated strategic partner; no competitive bid.' In Section F (Budget and Cost Management), it states 'The OCG requires all cost categories to be included' and notes e-discovery is excluded. In the Budget reconciliation table in Section V, it shows a total of $2,400,000 for the budget. In Section F it also states 'Total spend is about $2.78M including e-discovery.' The memo clearly identifies that the $380K e-discovery cost is excluded from the $2.4M budget and that the true total is approximately $2.78M.
- **GPT-5.5: Pass.** The memo expressly states that CrossPoint e-discovery is $380,000 and outside/excluded from the $2.4M litigation budget, and it identifies total spend as approximately $2.78M including e-discovery.

### C-029

Identifies scope ambiguity regarding appeals ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L242))

- **Sonnet 4.6: Fail.** The memo does mention that Exhibit B adds 'interlocutims appeals' to the budget exclusions (in Section VI's inconsistencies table and briefly in Section F), but it does not identify the specific internal contradiction between the broad scope provision covering 'all matters relating to the NovaTech dispute, including any counterclaims, cross-claims, or related proceedings' and the separate statement that 'appellate work [is] scoped separately.' The memo never discusses how 'all matters' and 'related proceedings' could logically include appeals, creating ambiguity about whether appeals are in or out of scope. The criterion specifically requires identification of this scope ambiguity, which the memo does not address.
- **GPT-5.5: Fail.** The memo mentions appeals only in the context of budget omissions/exclusions, such as Exhibit B adding interlocutory appeals and the budget lacking appeals/post-judgment phases. It does not identify the specific scope ambiguity between a broad scope covering “all matters” or “related proceedings” and a separate statement that appellate work is scoped separately, nor does it explain that appeals could logically fall within the broad scope language.

### C-030

Flags mandatory arbitration in D.C. as disadvantageous to NC-based client ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L250))

- **Sonnet 4.6: Pass.** Section I.D (Dispute Resolution and Governing Law) explicitly identifies that EL §17 requires binding AAA arbitration in Washington, D.C., including malpractice claims, with a jury waiver, and contrasts this with the OCG requirement for litigation in Mecklenburg County (Charlotte) courts under North Carolina law. The memo notes the engagement is Charlotte-centered and that mandatory arbitration of malpractice claims raises informed-consent issues. This clearly flags the D.C. arbitration clause as disadvantageous to the NC-based client by forcing dispute resolution in an inconvenient forum and stripping jury trial rights.
- **GPT-5.5: Pass.** The memo expressly flags the engagement letter’s mandatory binding AAA arbitration in Washington, D.C., including malpractice claims, with a jury waiver and D.C. law/courts. It notes the matter is Charlotte-centered and recommends replacing the clause with North Carolina law and Mecklenburg County courts, thereby identifying the clause as problematic and disadvantageous to the NC-based client.

### C-031

Flags marketing use of client name without adequate consent ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L258))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the marketing/client name use provision in Section H ('Work Product, Confidentiality and Marketing'), flagging that EL § 16's standing consent to name Pinnacle in marketing materials, the website, client lists and pitches violates OCG § 10.1, which requires the General Counsel's prior written consent for each use and bars even disclosing the existence of the engagement. The memo recommends deleting the marketing consent and notes confidentiality concerns. This satisfies the criterion of flagging the marketing use of client name without adequate consent as problematic.
- **GPT-5.5: Pass.** The memo explicitly flags the engagement letter’s standing consent for HB&C to use Pinnacle’s name in marketing materials, website, client lists, and pitches as problematic. It ties the issue to confidentiality obligations, notes that even disclosing the existence of the engagement is barred absent prior GC written consent, and recommends deleting/replacing the provision with OCG-compliant confidentiality language.

### C-032

Identifies firm termination notice period (30 days) vs. OCG (60 days + consent) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L266))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this issue in Section G (Termination and Withdrawal): 'Mutual 30-day termination. Pinnacle may terminate at any time (§ 8.1). The firm must give 60 days' notice and obtain Pinnacle's consent (§ 8.2), with a transition plan and full staffing during the notice period. Revise.' This identifies that the engagement letter allows the firm to withdraw on 30 days' notice, while the OCG requires 60 days' notice plus client consent. The discrepancy is clearly identified and flagged as needing revision.
- **GPT-5.5: Pass.** The memo expressly identifies the discrepancy: the engagement letter permits mutual 30-day termination/firm withdrawal on 30 days' notice, while the OCG requires the firm to give 60 days' notice and obtain Pinnacle's consent, with transition obligations. It also notes this is less protective and should be revised.

### C-033

Recommendations are provided and differentiated across issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L274))

- **Sonnet 4.6: Pass.** The memo provides recommendations for virtually all identified issues (well above 75%). The recommendation types are highly varied and include: (1) outright deletion/rejection of terms (e.g., delete §§ 4, 9, 10, 13, 14, 15, 16, 3.3 escalation clause); (2) specific revised language or replacement terms (e.g., replace liability cap with OCG language, replace integration clause, replace confidentiality clause with OCG § X); (3) requests for additional information (e.g., require formal conflicts clearance letter, require disclosure of HB&C-CrossPoint financial relationship, confirm what data has been shared with CrossPoint); (4) requirements for separate agreements (e.g., success fee must be in a separate GC-approved agreement per § 9.2); (5) requirements for OCG compliance (e.g., LEDES 1998B billing, rate caps, staffing approval process, BAA); (6) competitive bidding requirements; (7) escalation to General Counsel for consent decisions. The memo's Section VII explicitly lists required revisions across all major issue areas, and Section VIII provides a prioritized action plan. All three-plus distinct recommendation types are clearly present and applied across the full range of issues.
- **GPT-5.5: Pass.** The memo provides actionable recommendations for well over 75% of the identified issues, including a dedicated Required Revisions section that addresses conflicts, insurance, fee terms, budget, staffing, billing, e-discovery, confidentiality, termination, dispute resolution, and form issues. It also uses many distinct recommendation types, such as rejecting/deleting terms outright, requiring formal disclosures or additional information, requiring OCG-compliant revisions, demanding proof of insurance, requiring separate GC-approved agreements, proposing specific rate caps, and recommending competitive bidding or backup counsel.

### C-034

Cross-references Morrow email to engagement letter conflict waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L282))

- **Sonnet 4.6: Pass.** The memo explicitly connects Morrow's October 3 email (disclosing MedBridge's 8% equity stake in NovaTech) with the engagement letter's advance waiver provision in Section 11. In Section IV.A.1, the memo notes that Morrow raised the MedBridge issue informally, that the firm's clearance email omits MedBridge, and that EL §11 states 'no current conflicts' — directly contradicting the firm's own disclosure. The memo then separately addresses the advance waiver in §11 (blanket consent to future adverse representations), quoting Morrow's email describing it as 'customary,' and cross-references OCG §2.2's prohibition on blanket waivers. The Issues Matrix also lists both as separate Critical items (rows 1 and 2) but the detailed analysis synthesizes them together under the same subsection. The memo clearly treats these as related and cross-references the Morrow email to the engagement letter's conflict waiver language.
- **GPT-5.5: Pass.** The memo expressly synthesizes Morrow’s email disclosure about MedBridge’s 8% NovaTech equity stake with Engagement Letter § 11, noting both the contradictory “no current conflicts” statement and the broad advance waiver in the same conflict analysis. It also states Morrow described the waiver as customary and requires deletion alongside formal MedBridge disclosure/GC consent.

### C-035

Cross-references CrossPoint proposal to budget exclusion in engagement letter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L290))

- **Sonnet 4.6: Pass.** The memo explicitly connects the CrossPoint Analytics e-discovery proposal ($380,000) to the engagement letter's exclusion of e-discovery from the $2.4M litigation budget. In the Issues Matrix (item 16), it notes that 'E-discovery ($380K), success fee and "extraordinary" costs excluded; budget "not a cap".' In Section E (E-Discovery Vendor), it states 'E-discovery is excluded from the litigation budget, contrary to § 4.1(c), which specifically requires e-discovery processing and hosting to be budgeted.' In Section F (Budget), it references the total spend as 'about $2.78M including e-discovery.' The financial summary table also shows CrossPoint e-discovery as '$380,000 — outside budget.' The memo clearly synthesizes information across both documents.
- **GPT-5.5: Pass.** The memo expressly links the CrossPoint Analytics proposal to the engagement letter’s budget exclusion: it identifies CrossPoint as a firm-affiliated “strategic partner,” states the e-discovery estimate is $380,000, and notes that e-discovery is excluded from the $2.4M litigation budget, including in the executive summary, issues matrix, and detailed e-discovery/budget analysis.

### C-036

Cross-references staffing plan rates against OCG rate caps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L298))

- **Sonnet 4.6: Pass.** The memo explicitly references the Staffing Plan in its rate analysis. In Section IV.B (Issue 4, 'Hourly Rates Exceed OCG Caps'), the table lists timekeepers with their proposed rates and OCG caps, and the narrative states 'Core-team fees at the proposed rates total $1,141,500 (1,880 hours)' derived from the staffing plan hours. Section IV.D (Staffing) also references 'Staffing Plan §§ 3, 6' and 'Staffing Plan § 5' for the automatic escalation clause. The memo explicitly cites the Staffing Plan as a source document and uses its hour estimates to calculate fee totals, demonstrating cross-document analysis between the staffing plan and the OCG rate caps.
- **GPT-5.5: Pass.** The memo includes a detailed individual timekeeper rate comparison table with proposed rates, corresponding OCG caps, excess amounts, and estimated hours, and elsewhere uses the staffing plan’s hours and budget data in the analysis. Although the table cites the engagement letter/rate exhibit as the source for rates, the memo demonstrates cross-document analysis using staffing plan information alongside OCG caps rather than relying only on the engagement letter.

### C-037

Identifies inadequacy of conflicts clearance in Alcott email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L306))

- **Sonnet 4.6: Pass.** The memo extensively discusses the inadequacy of the Alcott conflicts clearance email. In Section IV.A.1, it explicitly states that the Alcott October 4 email 'says the check was run only against NovaTech, its principals and Prescott Lane, and does not mention MedBridge at all.' It further notes the clearance 'does not meet § 2.2(a)-(d)' because 'It is an informal email, not a clearance letter. It was run against only three names (it did not search NovaTech's equity holders or affiliates). It omits the known MedBridge relationship.' The memo also flags that EL § 11 states 'no current conflicts' despite the firm's own prior disclosure of the MedBridge connection, calling this 'a candor concern as well as a compliance defect.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that Alcott’s Oct. 4 conflicts email is inadequate because it only checked NovaTech, its principals, and opposing counsel, omits the MedBridge relationship despite MedBridge’s 8% NovaTech stake, and does not satisfy the OCG’s required formal conflicts clearance/disclosure before engagement.

### C-038

Correctly identifies case as NovaTech v. Pinnacle with $14.2M exposure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L314))

- **Sonnet 4.6: Pass.** The memo correctly identifies the matter as 'NovaTech Solutions, LLC v. Pinnacle Health Systems, Inc., No. 3:25-cv-01847-MRD (W.D.N.C.)' and repeatedly references the $14.2M damages claim throughout the document (e.g., 'NovaTech's $14.2M damages claim', '10% × $14.2M', 'a $14.2M commercial case'). Both the case name and damages amount are accurately stated.
- **GPT-5.5: Pass.** The memo correctly identifies the matter as NovaTech Solutions, LLC v. Pinnacle Health Systems, Inc., No. 3:25-cv-01847-MRD, and repeatedly states the claimed damages/exposure as $14.2 million.

### C-039

Recommends requiring competitive bidding for e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L322))

- **Sonnet 4.6: Pass.** The memo explicitly recommends competitive bidding for the e-discovery vendor in multiple places. In Section IV.E (E-Discovery Vendor — CrossPoint Analytics), it states: 'We recommend competitive bids, including any Pinnacle-preferred e-discovery vendor.' In Section VII (Required Revisions), under e-discovery: 'run a competitive bid (including any Pinnacle-preferred vendor).' In Section VIII (Next Steps), action item 6: 'Launch e-discovery vendor competitive bid.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly recommends subjecting CrossPoint to competitive bidding, including obtaining bids from Pinnacle-preferred or alternative e-discovery vendors, rather than accepting the affiliated vendor without comparison.

### C-040

Recommends requiring informed written consent for conflict/adverse representation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L330))

- **Sonnet 4.6: Pass.** The memo extensively addresses the MedBridge/NovaTech conflict. It identifies the issue as Critical, explains that OCG § 2.2 requires 'a detailed written disclosure' and 'informed written consent' from the General Counsel, notes the informal email is insufficient, and in the Required Action section explicitly states: (i) require a formal conflicts clearance letter, (ii) require detailed written disclosure of the MedBridge relationship, (iii) the General Counsel should decide whether to consent in a separate signed writing or decline the engagement, and (iv) delete the advance waiver. This goes well beyond merely noting the conflict's existence—it makes specific recommendations for informed written consent and a more thorough conflicts analysis, and recommends removing the broad advance waiver.
- **GPT-5.5: Pass.** The memo explicitly identifies the MedBridge/NovaTech conflict as a critical issue, states that HB&C cannot proceed without detailed written disclosure and informed written consent from the General Counsel, recommends a formal conflicts clearance and more thorough analysis, and directs deletion of the blanket advance waiver of future adverse representations.

### C-041

Recommends reducing or eliminating the malpractice liability cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L338))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the malpractice liability cap in Section IV.A.3 (Issue #4 in the matrix, rated Critical), stating the cap at 'the lesser of $1M or fees paid' is impermissible under RPC 1.8(h)(1) and concluding 'Delete in full.' Section VII's required revisions list also includes '§ 13 (liability cap)' among items to delete. The memo clearly recommends eliminating the cap entirely, which satisfies the criterion of recommending reducing or eliminating the malpractice liability cap given the $14.2M matter exposure.
- **GPT-5.5: Pass.** The memo explicitly identifies the malpractice liability cap (lesser of $1M or fees paid) as a critical issue given the $14.2M exposure and recommends deleting it in full, satisfying the requirement to eliminate or renegotiate the cap.

### C-042

Recommends removing or restructuring client indemnification clause ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L346))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the client indemnification clause in Section IV.A.3 (Issue #5 in the matrix, labeled Critical). It states that Section 14 requires Pinnacle to indemnify the firm for everything except 'solely' willful misconduct, which would cover the firm's own negligence, and recommends it be 'Delete[d] in full.' This satisfies the criterion of recommending removal of the indemnification obligation entirely.
- **GPT-5.5: Pass.** The memo specifically identifies the client indemnification clause (§ 14) as unacceptable because it would cover the firm’s own negligence/malpractice and recommends deleting it in full. This satisfies the criterion.

### C-043

Recommends removing or restructuring the 15% termination fee ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L354))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the 15% termination fee in multiple places. In the Issues Matrix (Issue #7), it flags the termination fee as 'Critical' severity. In Section IV.G, it states the termination fee is 'void under OCG § 8.1' and that 'Pinnacle's only obligation is to pay for services properly rendered,' concluding with 'Delete.' In Section VII (Required Revisions), it lists 'Delete: § 4 (non-refundable retainer), § 9 termination fee...' The memo clearly recommends removing the termination fee entirely.
- **GPT-5.5: Pass.** The memo repeatedly identifies the 15% termination fee as problematic and expressly recommends deleting it/removing it, including stating it is void under the OCG and that Pinnacle may terminate at will with no fee.

### C-044

Recommends requiring firm insurance to meet OCG minimums ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L362))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the insurance shortfall as a Critical issue (#3 in the Issues Matrix) and in Section IV.A.2 states that HB&C must provide proof of coverage meeting the $25M/$50M minimums before the engagement begins, noting that otherwise the engagement cannot proceed unless the General Counsel signs a separate written waiver. The Required Revisions section (VII) also lists 'Certificate showing $25M/$50M with an A- or better carrier before any work starts' as a required change. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies HB&C’s $10M/$20M insurance as below the OCG-required $25M per occurrence / $50M aggregate, states the firm must provide proof of coverage meeting those minimums before engagement, and notes that otherwise a separate GC waiver would be required though not recommended.

### C-045

Recommends removing or restructuring the work product lien ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L370))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the work product lien in multiple places. In Section IV.H, it states: 'OCG § 7.1 provides that Pinnacle owns all work product absolutely, "not contingent upon payment." OCG § 7.2 prohibits any lien, and asserting one is a material breach. Replace § 15 with the OCG language and an express lien waiver.' The Issues Matrix also lists the lien as a Critical issue (#6). Section VII's Required Revisions explicitly states to 'Delete: § 4 (non-refundable retainer), § 9 termination fee, § 10 (success fee), § 13 (liability cap), § 14 (indemnity), the lien in § 15...' This clearly recommends removing the lien and replacing it with OCG-compliant language including an express lien waiver.
- **GPT-5.5: Pass.** The memo explicitly identifies the firm's retaining lien over Pinnacle's files/work product as a critical issue, states that work product ownership cannot be contingent on payment, and recommends replacing the provision with OCG language and an express lien waiver. It also lists deletion of the lien in the required revisions.

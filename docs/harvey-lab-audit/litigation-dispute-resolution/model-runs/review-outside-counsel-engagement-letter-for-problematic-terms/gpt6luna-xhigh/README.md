# GPT-6 Luna (xhigh): Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 43 of 45 criteria; GPT-5.5 passed 44 of 45 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-016](#c-016) | Notes work product lien could prejudice client's defense in active litigation | Pass | Pass |
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
| [C-029](#c-029) | Identifies scope ambiguity regarding appeals | **Fail** | Pass |
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

- **Sonnet 4.6: Pass.** The memo explicitly identifies in the rate table under Issue 5 that Morrow (equity partner) has a proposed rate of $1,050, an OCG cap of $850, and an excess of $200/hr. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo specifically identifies Morrow’s proposed rate as $1,050/hr, the OCG cap as $850/hr, and the excess as $200/hr in the rates table.

### C-002

Identifies Alcott's rate ($975/hr) exceeds OCG partner cap ($850/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L26))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Alcott's rate in the rate comparison table under Issue 5: 'Alcott --- equity partner: Proposed $975, OCG cap $850, Excess $125/hr'. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo specifically includes a rates table listing “Alcott — equity partner” with a proposed rate of $975, an OCG cap of $850, and an excess of $125/hr.

### C-003

Identifies Dasgupta's rate ($625/hr) exceeds OCG senior associate cap ($575/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L34))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Dasgupta's rate in the rate table under Issue 5: 'Dasgupta --- senior associate (7 yrs): Proposed $625, OCG cap $575, Excess $50/hr.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies “Dasgupta — senior associate (7 yrs)” with a proposed rate of $625, an OCG cap of $575, and a $50/hr excess.

### C-004

Identifies Marsh's rate ($475/hr) exceeds OCG junior associate cap ($425/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L42))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Marsh as a junior associate (3 yrs) with a proposed rate of $475/hr against an OCG cap of $425/hr, noting a $50/hr excess in the rate comparison table in Issue 5.
- **GPT-5.5: Pass.** The memo explicitly includes a rates table listing “Marsh — junior associate (3 yrs)” with proposed rate $475, OCG cap $425, and excess $50/hr, satisfying the criterion.

### C-005

Identifies Solano's paralegal rate ($275/hr) exceeds OCG cap ($225/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L50))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Solano as a senior paralegal with a proposed rate of $275 and an OCG cap of $225, noting a $50/hr excess in the rate comparison table in Issue 5.
- **GPT-5.5: Pass.** The memo explicitly lists “Solano — senior paralegal” with a proposed rate of $275, an OCG cap of $225, and an excess of $50/hr.

### C-006

Identifies blended rate ($685/hr) exceeds OCG blended rate cap ($625/hr) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L58))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the blended rate issue in Section 5, including a table row showing 'Blended option' at $685 proposed vs $625 OCG cap with $60/hr excess. It also states 'The $685 blended option is above the $625 limit' in the narrative text.
- **GPT-5.5: Pass.** The memo explicitly states that the blended option is $685/hr, the OCG cap is $625/hr, and the excess is $60/hr, including both a table entry and explanatory text.

### C-007

Identifies 5% automatic annual rate escalation as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L66))

- **Sonnet 4.6: Pass.** In Issue 5, the memo explicitly states: 'The letter and staffing plan also make a 5% automatic increase effective Jan. 1, 2026. That is ineffective under the OCG; any 2026 proposal had to be submitted by Nov. 1, 2025 and is not effective absent prior written GC approval.' The required action also states 'Remove automatic escalation.' This clearly identifies the 5% automatic annual rate escalation as problematic because it conflicts with the OCG's requirement for prior written GC approval for any rate increases.
- **GPT-5.5: Pass.** The memo explicitly identifies the proposed 5% automatic increase effective Jan. 1, 2026 as problematic, states it is ineffective under the OCG absent prior written GC approval, and requires removal of automatic escalation.

### C-008

Notes 5% escalation is above market standard (3-4%) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L74))

- **Sonnet 4.6: Fail.** The memo discusses the 5% automatic rate escalation in Section 5, noting it is 'ineffective under the OCG' and requires prior written GC approval. However, it does not compare the 5% rate to market-standard escalation rates (typically 3-4%) or characterize 5% as excessive or above-market. The memo's objection is purely procedural (OCG compliance) rather than substantive (market comparison).
- **GPT-5.5: Fail.** The memo identifies the 5% automatic annual rate increase as noncompliant with the OCG and requiring approval, but it does not compare it to typical market escalation rates of 3–4% or characterize it as above-market or excessive.

### C-009

Flags non-refundable $250,000 retainer as ethically problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L82))

- **Sonnet 4.6: Pass.** The memo does flag the $250,000 non-refundable retainer as problematic in Section 7. It notes that the retainer conflicts with the OCG, which requires retainers to go to client trust and be refundable to the extent unearned, and that non-refundable treatment requires 'extraordinary circumstances and express written GC approval.' It also notes that calling it 'earned/non-refundable on receipt' and forfeiting unused balance on termination are problematic. However, the criterion specifically asks whether the memo identifies ethical concerns such as fee reasonableness rules (e.g., ABA Model Rule 1.5) or the risk that a non-refundable retainer could be deemed unreasonable. The memo frames the issue primarily as an OCG compliance problem rather than an ethical/professional responsibility concern under rules like ABA Model Rule 1.5. It does not cite fee reasonableness rules or professional conduct rules regarding non-refundable retainers. That said, the criterion says 'PASS if the memo identifies that the $250,000 non-refundable retainer raises ethical concerns, such as potential issues under fee reasonableness rules... or that it should be restructured as a refundable security retainer or a properly justified earned-upon-receipt fee.' The memo does recommend restructuring it as a refundable deposit held in trust, which aligns with the 'restructured as a refundable security retainer' prong. The criterion uses 'such as' indicating these are examples, not exhaustive requirements. The memo does flag the non-refundable nature as problematic and recommends it be made refundable. However, it lacks explicit ethical framing (no mention of Rule 1.5 or fee reasonableness). The criterion's pass condition includes 'or that it should be restructured as a refundable security retainer' - the memo does recommend this. I'll consider this a borderline case but lean toward PASS since the memo does flag the non-refundable retainer as problematic and recommends restructuring as a refundable trust deposit, which satisfies at least one of the criterion's stated examples.
- **GPT-5.5: Pass.** The memo specifically identifies the $250,000 retainer as problematic because it is deposited to the operating account, deemed earned/non-refundable on receipt, and forfeits any unused balance on termination. It recommends deleting it or restructuring any advance deposit as held in trust and refundable to the extent unearned, with non-refundable treatment only under extraordinary circumstances and express approval. This satisfies the criterion, even though it does not expressly cite Model Rule 1.5.

### C-010

Identifies invoice submission timeline deviation (60 vs. 45 days) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L90))

- **Sonnet 4.6: Pass.** In Section 6 of the memo, the agent explicitly states: 'The letter permits submission within 60 days' and contrasts this with the OCG requirement, noting the OCG requires invoices 'submitted within 45 days after month-end.' This directly identifies the 60 vs. 45 day discrepancy.
- **GPT-5.5: Pass.** The memo explicitly states that the OCG requires invoices to be submitted within 45 days after month-end and that the engagement letter permits submission within 60 days, identifying the timing deviation.

### C-011

Identifies expense threshold deviation ($15,000 vs. $5,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L98))

- **Sonnet 4.6: Pass.** In Issue 13 (Expense, travel, and disbursement terms conflict with OCG thresholds and prohibitions), the memo explicitly states: 'The letter allows expenses up to $15,000 per item without approval' and contrasts this with the OCG requirement of 'Prior written approval is required before any individual expense over $5,000.' This directly identifies the $15,000 vs. $5,000 threshold deviation and the resulting $10,000 gap in client cost control.
- **GPT-5.5: Pass.** The memo expressly states that the engagement letter allows expenses up to $15,000 per item without approval, while the OCG requires prior written approval for any single expense over $5,000. Although it does not spell out the $10,000 difference, it identifies the threshold deviation required by the criterion.

### C-012

Identifies business-class travel provision conflicts with OCG economy-only policy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L106))

- **Sonnet 4.6: Pass.** In Issue 13, the memo explicitly states: 'The letter allows expenses up to $15,000 per item without approval and allows partners business-class airfare for flights over two hours.' It then requires replacement with OCG terms including 'economy only.' This directly identifies the conflict between the engagement letter's business-class airfare provision and the OCG's economy/coach requirement.
- **GPT-5.5: Pass.** The memo explicitly states that the engagement letter allows partners business-class airfare for flights over two hours and contrasts this with the OCG requirement of economy/coach travel only, recommending replacement with economy-only terms.

### C-013

Flags firm's sole staffing discretion vs. OCG 14-day notice requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L114))

- **Sonnet 4.6: Pass.** Section 12 of the memo explicitly identifies that both engagement documents 'reserve sole discretion to add, substitute, or remove timekeepers and use contract attorneys' and contrasts this with the OCG requirement of '14-day notice/approval for lead partner, partner, senior associate and specialist changes.' The required action also states to 'Replace sole-discretion language with OCG notice/approval rules' and 'Require 14-day notice/approval for lead partner, partner, senior associate and specialist changes.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that the engagement documents reserve sole discretion to add, substitute, or remove timekeepers and states this conflicts with the OCG requirement for 14-day advance notice/approval for lead partner, partner, senior associate, and specialist staffing changes.

### C-014

Flags contract attorney usage at $350/hr as unaddressed by OCG ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L122))

- **Sonnet 4.6: Pass.** The memo explicitly addresses contract attorney rates in multiple sections. In Issue 5, it identifies that the proposed contract attorney rate of $350/hr exceeds the OCG ceiling of $225/hr for document review, and notes that substantive contract-attorney work may be billed up to the $425 junior-associate ceiling only with prior approval. In Issue 12, it further flags that the engagement documents reserve sole discretion to use contract attorneys up to $350/hour, that no contract-attorney names, qualifications, duration or scope are supplied, and that prior written approval is required with qualifications, task, rate, estimated hours and duration, applying $225/hour for document review. The memo clearly identifies the $350/hr rate as problematic and requiring separate approval, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies the staffing plan/engagement provision allowing contract attorneys at up to $350/hr as problematic, compares it to OCG limits, and states contract/temporary attorneys require prior client approval with qualifications, scope, rate, hours, and duration; it also recommends applying the $225/hr document review rate and obtaining written approval.

### C-015

Identifies work product lien conflicts with OCG ownership provision ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L130))

- **Sonnet 4.6: Pass.** Section 14 of the memo explicitly addresses the work-product ownership and lien provisions. It states that the engagement letter 'grants HB&C a retaining lien on files/work product until all amounts are paid,' which 'is directly contrary to the OCG' that provides Pinnacle owns all work product/files regardless of payment and that no lien may be asserted. The required action calls for deleting all lien/ownership/payment conditions and waiving any retaining, charging, possessory, or other lien. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that HB&C's retaining lien on files/work product until payment conflicts with the OCG's requirement that Pinnacle owns all work product/files regardless of payment and that no lien may be asserted.

### C-016

Notes work product lien could prejudice client's defense in active litigation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L138))

- **Sonnet 4.6: Pass.** The memo discusses the retaining lien in Issue 14, noting that 'Termination cooperation is expressly subject to Section 15' and that the lien 'could impair continuity or court deadlines during a billing dispute.' This directly addresses the practical prejudice of a lien on files during active litigation—specifically that a billing dispute could impair continuity and court deadlines, which is the core concern about prejudicing the client's defense in active litigation.
- **GPT-5.5: Pass.** The memo specifically identifies the retaining lien as conflicting with Pinnacle’s ownership rights and explains the practical risk: it “could impair continuity or court deadlines during a billing dispute,” which addresses prejudice to Pinnacle’s defense in active litigation.

### C-017

Flags 15% client termination fee as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L146))

- **Sonnet 4.6: Pass.** Section 15 of the memo explicitly flags the 15% termination fee as problematic, stating: 'The letter requires either party to give 30 days' notice and imposes a 15% termination fee on Pinnacle.' The required action states: 'Give Pinnacle immediate termination rights by written notice, with only properly rendered fees and approved/properly incurred expenses through the effective date payable. Delete the 15% fee.' This clearly identifies the termination fee as a problem that restricts the client's right to terminate and functions as a penalty clause inconsistent with the OCG.
- **GPT-5.5: Pass.** The memo expressly flags the 15% termination fee as problematic in the executive assessment and in Section 15, stating it conflicts with Pinnacle’s right to terminate at any time with no termination penalty and requiring deletion of the fee.

### C-018

Flags malpractice liability cap as disproportionate to matter size and potentially ethically impermissible ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L154))

- **Sonnet 4.6: Pass.** Section 20 of the memo explicitly addresses the liability cap, noting that HB&C limits all liability including malpractice to the lesser of $1m or fees actually paid, and states this could be 'potentially very low early in the case.' It also notes that 'Professional-responsibility rules may also restrict prospective malpractice limitations,' which addresses the ethical impermissibility angle. The memo recommends deleting the cap and requiring independent ethics/insurance review. The $14.2m matter exposure context is established throughout the memo (the success fee formula references $14.2m as the claimed damages). The criterion is satisfied: the cap is flagged as disproportionate (potentially very low relative to matter size) and as potentially ethically impermissible (professional-responsibility rules may restrict it).
- **GPT-5.5: Pass.** The memo flags the malpractice liability cap (lesser of $1 million or fees paid) as a serious issue, notes it applies to malpractice, and states that professional-responsibility rules may restrict prospective malpractice limitations, with a recommendation for ethics review. This satisfies the criterion even though it does not expressly compare the cap to the $14.2 million exposure.

### C-019

Flags client indemnification of law firm as unusual and ethically suspect ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L162))

- **Sonnet 4.6: Pass.** Section 20 of the memo explicitly flags the client indemnity provision as problematic. It notes that 'Pinnacle separately indemnifies the firm for essentially all engagement-related claims, including third-party claims, with an exception only for claims arising solely from willful misconduct.' It further states that 'the indemnity could cover the firm's own negligence or malpractice and substantially undermine the protection expected from required insurance,' and that these provisions 'are not required by the OCG and should not be accepted as routine boilerplate.' The required action directs deletion of the liability cap and client indemnity, and specifically states 'do not agree to indemnify HB&C for its own negligence, malpractice, gross negligence, willful misconduct, breach of duties, confidentiality/security failures, or legal violations' and to 'require independent ethics/insurance review of any limitation.' This satisfies the criterion: the memo identifies the indemnification as unusual, risk-shifting, and ethically suspect (referencing ethics/insurance review), even if it does not cite Model Rule 1.8(h) by name.
- **GPT-5.5: Pass.** The memo expressly flags the broad client indemnity as a serious risk transfer, notes it covers third-party claims and could indemnify the firm for its own negligence or malpractice, says it is not routine boilerplate, and warns that professional-responsibility rules may restrict prospective malpractice limitations. It recommends deleting the indemnity.

### C-020

Notes willful misconduct carve-out is narrower than negligence standard ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L170))

- **Sonnet 4.6: Pass.** In Issue 20, the memo explicitly states: 'Pinnacle separately indemnifies the firm for essentially all engagement-related claims, including third-party claims, with an exception only for claims arising solely from willful misconduct. As written, the indemnity could cover the firm's own negligence or malpractice and substantially undermine the protection expected from required insurance.' This directly identifies that the willful misconduct carve-out is too narrow and does not cover negligence or malpractice, meaning Pinnacle would be indemnifying HB&C even for negligent acts.
- **GPT-5.5: Pass.** The memo expressly states that the indemnity exception is only for claims arising solely from willful misconduct and that, as drafted, the indemnity could cover the firm’s own negligence or malpractice. It also recommends not indemnifying HB&C for its own negligence, malpractice, gross negligence, or willful misconduct.

### C-021

Identifies MedBridge/NovaTech conflict of interest ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L178))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the MedBridge conflict in multiple places. In the Executive Assessment, it states: 'HB&C's current representation of MedBridge Therapeutics, which Morrow disclosed as an 8% equity investor in NovaTech. That exceeds the OCG's 5% material financial interest threshold.' Section 2 is entirely dedicated to this conflict, labeled CRITICAL, and details that MedBridge holds approximately 8% equity in NovaTech, that HB&C currently represents MedBridge in a reimbursement dispute, and that Alcott's clearance was materially incomplete because it omitted MedBridge. The memo treats this as a stop issue requiring full resolution before engagement.
- **GPT-5.5: Pass.** The memo explicitly identifies HB&C's current representation of MedBridge Therapeutics and MedBridge's approximately 8% equity stake in NovaTech, states this exceeds the OCG's material financial interest threshold, and treats it as a critical conflict requiring disclosure and GC consent or declining the engagement.

### C-022

Notes firm's 'no conflict' characterization is inadequate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L186))

- **Sonnet 4.6: Pass.** The memo explicitly challenges the firm's conflict clearance as inadequate. In Section 2, it states that 'Alcott's follow-up says the check covered NovaTech, known principals, and Prescott Lane, but omits MedBridge and material investors; it is not a clearance letter and is materially incomplete on the known issue.' The executive assessment also notes that 'Alcott's purported clearance does not address MedBridge or material investors and is not the required comprehensive clearance letter.' The memo treats this as a 'CRITICAL' stop issue and directly challenges the firm's dismissal of the conflict as insufficient.
- **GPT-5.5: Pass.** The memo directly challenges the firm's conflict clearance/no-conflict characterization, emphasizing that MedBridge's 8% stake creates a material financial interest under the OCG and that Alcott's clearance omits MedBridge/material investors and is inadequate. It treats the issue as a stop issue requiring full disclosure and GC consent.

### C-023

Flags broad adverse-representation waiver as compounding conflict risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L194))

- **Sonnet 4.6: Pass.** In Section 2 of the memo, the agent explicitly states: 'The draft's blanket waiver of future unrelated adverse representations is expressly unacceptable.' This directly flags the broad adverse-representation waiver. The memo also connects this to the MedBridge conflict issue, as the entire section discusses how the MedBridge/NovaTech conflict is unresolved and how the blanket waiver compounds the problem by allowing HB&C to represent clients adverse to Pinnacle in unrelated matters without further consent. The required action states to 'Strike the blanket waiver.' The connection between the waiver and the conflict risk (MedBridge representing an 8% equity stake in NovaTech while HB&C represents MedBridge) is made clear throughout Section 2. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo discusses the MedBridge/NovaTech material conflict in the conflicts section and specifically flags the engagement letter's blanket waiver of future unrelated adverse representations as expressly unacceptable/prohibited, directing that it be struck. This connects the broad adverse-representation waiver to the conflict concern, satisfying the criterion.

### C-024

Identifies firm insurance ($10M/$20M) is below OCG minimum ($25M/$50M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L202))

- **Sonnet 4.6: Pass.** Section 4 of the memo explicitly states: 'HB&C represents coverage of only $10m per occurrence/$20m aggregate---less than half the OCG minimum---and provides no certificate, carrier rating, or exclusions information.' The OCG minimum of $25m per occurrence and $50m aggregate is also clearly stated in the guideline portion of that section. The memo directly identifies the shortfall between the firm's $10M/$20M coverage and the required $25M/$50M minimum.
- **GPT-5.5: Pass.** The memo explicitly states that HB&C’s professional liability coverage is only $10M per occurrence / $20M aggregate and that this is below the OCG minimum of $25M per occurrence / $50M aggregate.

### C-025

Identifies success fee embedded in engagement letter vs. OCG separate agreement requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L210))

- **Sonnet 4.6: Pass.** Section 16 of the memo explicitly identifies that the success fee is 'embedded' in the engagement letter (§10) rather than in a separate written agreement, and states the OCG requires 'a separate written agreement reviewed and approved by the GC before execution.' The required action instructs to 'Strike §10 from the engagement letter' and require 'a separate standalone proposal and GC approval before execution.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that the OCG requires any success/performance fee to be in a separate written agreement reviewed and approved by the GC, and states that the engagement letter improperly embeds a 10% success fee for resolutions below $7 million directly in the engagement letter.

### C-026

Notes success fee is uncapped and potentially very large (up to ~$1.42M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L218))

- **Sonnet 4.6: Pass.** The memo explicitly states in section 16: 'If the matter resolves for $0, the formula yields $1.42m; at $4m it yields $1.02m' and also notes 'no express dollar cap.' The budget table also shows 'Formula maximum if resolution amount is $0: $1,420,000.' This clearly identifies the uncapped nature and the potential magnitude of approximately $1.42M.
- **GPT-5.5: Pass.** The memo explicitly states that the success fee has no stated dollar cap and calculates that if the matter resolves for $0, the formula yields $1.42 million, also noting a $1.02 million example at a $4 million resolution.

### C-027

Flags affiliated e-discovery vendor (CrossPoint) as financial conflict ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L226))

- **Sonnet 4.6: Pass.** In Issue 9, the memo explicitly states that 'CrossPoint is an HB&C "strategic partner"' and notes that 'HB&C's recommendation and history of 40 engagements do not equal Pinnacle approval or a competitive-cost analysis.' It also requires disclosure of 'whether HB&C or any timekeeper has a financial interest in CrossPoint' and mandates a competitive bid process. This directly identifies the affiliated vendor relationship and the financial conflict/cost-control circumvention concern.
- **GPT-5.5: Pass.** The memo specifically identifies CrossPoint as HB&C’s “strategic partner,” notes the lack of Pinnacle approval or competitive-cost analysis/competitive bid for the $380,000 vendor proposal, and calls for disclosure of any HB&C/timekeeper financial interest in CrossPoint and compliance with vendor cost controls. This raises the affiliated vendor/cost-control conflict issue required by the criterion.

### C-028

Identifies $380K e-discovery cost excluded from $2.4M budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L234))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Issue 8 that 'CrossPoint's $380,000 excluded from HB&C budget' and shows a table with 'Stated subtotal before success fee / extras: $2,780,000'. This clearly identifies that the $380,000 e-discovery cost is excluded from the $2.4 million budget and that the combined total is approximately $2,780,000.
- **GPT-5.5: Pass.** The memo explicitly states that CrossPoint's $380,000 e-discovery proposal is excluded from HB&C's $2.4 million budget and identifies a stated subtotal before success fee/extras of $2,780,000.

### C-029

Identifies scope ambiguity regarding appeals ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L242))

- **Sonnet 4.6: Fail.** In Section 8 (Budget is an estimate, excludes major costs, and lacks required controls), the memo states: 'The scope includes related proceedings, but the budget excludes government inquiries/third-party interventions; appellate work is separately scoped.' This briefly notes that appellate work is separately scoped, but it does not identify the internal contradiction between the broad scope provision ('all matters relating to the NovaTech dispute, including any counterclaims, cross-claims, or related proceedings') and the separate statement that appellate work is scoped separately. The memo does not flag that 'all matters' and 'related proceedings' could logically include appeals, creating ambiguity about whether appeals are in or out of scope. The mention is incidental and does not constitute identification of the scope ambiguity as required by the criterion.
- **GPT-5.5: Pass.** The memo notes that the scope includes related proceedings while appellate work is separately scoped, which identifies the relevant inconsistency/ambiguity between broad dispute-related scope language and separate appellate treatment, even though it does not elaborate extensively.

### C-030

Flags mandatory arbitration in D.C. as disadvantageous to NC-based client ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L250))

- **Sonnet 4.6: Pass.** Issue 19 of the memo explicitly flags the D.C. arbitration and governing-law terms as conflicting with the OCG. It notes that the letter imposes exclusive AAA binding arbitration in Washington, D.C. for all disputes including fee and malpractice claims, waives jury and class rights, and selects D.C. law and courts. It identifies these as directly displacing the OCG's Charlotte mediation, North Carolina court venue, and North Carolina law, which is disadvantageous to the NC-based client. The required action calls for deletion of those provisions and use of the OCG's Mecklenburg County venue and North Carolina law.
- **GPT-5.5: Pass.** The memo explicitly flags the D.C. mandatory AAA arbitration and D.C. law/courts provisions as problematic, noting they apply to fee and malpractice claims, waive jury rights, and conflict with the North Carolina/Mecklenburg County dispute path in the OCG.

### C-031

Flags marketing use of client name without adequate consent ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L258))

- **Sonnet 4.6: Pass.** Section 17 of the memo explicitly addresses the marketing consent issue. It identifies that the engagement letter gives HB&C 'continuing consent to identify Pinnacle and the general commercial-litigation engagement in website/client lists/pitches without case details, until revoked,' characterizes this as 'a standing advance authorization, not prior written consent for a specific use,' and requires deletion of the marketing carve-out with replacement by 'separate, prior, written GC approval for the specific disclosure.' The memo also references OCG §X.1 which prohibits use of Pinnacle's name/logo for marketing absent prior written GC consent. While the memo could have more explicitly invoked Model Rule 1.6 or Pinnacle's healthcare sensitivity, it clearly flags the provision as problematic due to confidentiality concerns and inadequate consent, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly flags the engagement letter’s marketing/client-name provision as problematic, noting HB&C’s continuing consent to identify Pinnacle and the engagement on websites/client lists/pitches, that this conflicts with confidentiality restrictions, and that separate prior written GC approval for each specific disclosure is required. This satisfies the criterion.

### C-032

Identifies firm termination notice period (30 days) vs. OCG (60 days + consent) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L266))

- **Sonnet 4.6: Pass.** Section 15 of the memo explicitly addresses the termination notice discrepancy. It states that the engagement letter 'requires either party to give 30 days' notice' while the OCG requires '60 days' notice and Pinnacle's written consent for firm withdrawal.' The required action also states to 'Require 60 days' notice and Pinnacle's written consent for firm withdrawal.' This directly identifies the 30-day vs. 60-day discrepancy and the consent requirement, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that the engagement letter requires either party to give 30 days' notice, while the OCG requires the firm to provide 60 days' advance notice and obtain Pinnacle's written consent before withdrawal. It also notes this inconsistency and recommends revision.

### C-033

Recommendations are provided and differentiated across issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L274))

- **Sonnet 4.6: Pass.** The memo provides recommendations for all 21 identified issues (well above the 75% threshold). The recommendations employ multiple distinct types: (1) outright rejection/deletion of terms (e.g., delete the retaining lien, delete the liability cap, strike the success fee from the engagement letter, delete the marketing carve-out, delete D.C. arbitration clauses); (2) require specific revised language/OCG-compliant replacements (e.g., replace expense clause with OCG terms, replace §5 with OCG-compliant invoice terms, replace rate schedule with capped rates); (3) request additional information/documentation (e.g., require insurance certificate with carrier rating, require unit-based CrossPoint estimate with sensitivity cases, require complete conflicts clearance letter addressing MedBridge); (4) require separate agreements/approvals (e.g., success fee must be in a separate standalone agreement with GC approval, any retainer exception requires separate express GC approval, vendor approval through competitive-bid process); (5) require OCG incorporation and compliance (e.g., revise opening provisions to incorporate OCG, add matter number, flow down OCG provisions to CrossPoint). These clearly exceed three distinct recommendation types and cover all identified issues.
- **GPT-5.5: Pass.** The memo provides a specific “Required action” for essentially every identified issue, far exceeding the 75% threshold. It also differentiates recommendation types across issues, including rejecting/deleting terms outright, requiring OCG-compliant revisions, requesting additional information or documentation, requiring separate GC approvals or separate agreements, pausing work/vendor authorization, and negotiating vendor/security terms.

### C-034

Cross-references Morrow email to engagement letter conflict waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L282))

- **Sonnet 4.6: Pass.** The memo explicitly connects Morrow's email disclosure of MedBridge's 8% equity stake to the engagement letter's conflict waiver. In Section 2, the memo states: 'Morrow disclosed HB&C's current representation of MedBridge in a reimbursement dispute and MedBridge's approximately 8% equity stake in NovaTech' (from the Morrow email) and then directly links this to the engagement letter by stating 'The draft's blanket waiver of future unrelated adverse representations is expressly unacceptable.' The documents section for Issue 2 cites both 'Morrow email Oct. 3' and 'engagement letter §11' together, and the required action says to 'Strike the blanket waiver.' This clearly synthesizes the MedBridge disclosure from Morrow's email with the engagement letter's conflict waiver provision, treating them as related issues requiring coordinated resolution.
- **GPT-5.5: Pass.** The memo expressly combines the Morrow email disclosure about MedBridge’s 8% equity stake with the engagement letter’s conflict provision in the same conflicts issue, citing both documents and stating that the draft’s blanket waiver of future unrelated adverse representations is unacceptable and must be struck. This synthesizes the email disclosure and the waiver rather than treating them as unrelated.

### C-035

Cross-references CrossPoint proposal to budget exclusion in engagement letter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L290))

- **Sonnet 4.6: Pass.** The memo explicitly connects CrossPoint's $380,000 estimate to the engagement letter's budget exclusion in multiple places. In the executive assessment, it states 'CrossPoint's $380,000 proposal is neither within the $2.4 million budget nor approved.' In Issue 8 (Budget), it directly states the $2.4m budget 'excludes CrossPoint's $380,000' and includes a table showing 'CrossPoint e-discovery: $380,000 excluded from HB&C budget' with a stated subtotal of $2,780,000. Issue 9 also cross-references the CrossPoint proposal to the engagement letter §7 and OCG provisions, noting the $380,000 estimate and HB&C's 'strategic partner' relationship. The memo clearly synthesizes information across both documents.
- **GPT-5.5: Pass.** The memo expressly connects CrossPoint Analytics’ $380,000 e-discovery proposal and HB&C strategic-partner relationship to the engagement letter/budget’s exclusion of CrossPoint/e-discovery costs from the stated $2.4 million litigation budget, including in the executive assessment and detailed budget/vendor sections.

### C-036

Cross-references staffing plan rates against OCG rate caps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L298))

- **Sonnet 4.6: Pass.** The memo explicitly references both the staffing plan and the engagement letter when analyzing rates. In Issue 5, it states 'Documents: Engagement letter §§3, Exhibit A; staffing plan §§2, 5; OCG §§III.1--3' and uses the staffing plan's 1,880 core-team hours figure to calculate cost comparisons. The rate table lists timekeepers (Morrow, Alcott, Dasgupta, Marsh, Solano, contract attorneys) with proposed vs. OCG cap rates, and the memo explicitly references the staffing plan's 750--1,000 document-review hours estimate. This demonstrates cross-document analysis between the staffing plan and the OCG, not just the engagement letter alone.
- **GPT-5.5: Pass.** The memo expressly cites both the staffing plan and OCG in the rate issue, lists individual timekeeper/category rates against OCG caps in a comparison table, and uses staffing-plan hours to calculate the impact. This demonstrates cross-document analysis rather than relying solely on the engagement letter.

### C-037

Identifies inadequacy of conflicts clearance in Alcott email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L306))

- **Sonnet 4.6: Pass.** The memo extensively discusses the inadequacy of the Alcott email's conflicts clearance in Section 2 (labeled CRITICAL). It specifically notes that 'Alcott's follow-up says the check covered NovaTech, known principals, and Prescott Lane, but omits MedBridge and material investors; it is not a clearance letter and is materially incomplete on the known issue.' It also notes that substantive work began before an executed engagement letter and before conflict resolution. The memo clearly identifies that the OCG requires a comprehensive written conflicts clearance letter that has not been properly provided, and that the Alcott email fails to address the MedBridge/NovaTech connection despite Morrow having disclosed it.
- **GPT-5.5: Pass.** The memo expressly states that Alcott's purported standard conflicts clearance is inadequate because it does not address MedBridge or material investors despite Morrow's disclosure of MedBridge's 8% NovaTech stake, and notes that the OCG requires a comprehensive written conflicts clearance before work begins.

### C-038

Correctly identifies case as NovaTech v. Pinnacle with $14.2M exposure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L314))

- **Sonnet 4.6: Pass.** The memo correctly identifies the matter as 'NovaTech Solutions, LLC v. Pinnacle Health Systems, Inc.' in the header. It also references the $14.2 million figure in the success fee discussion (Section 16): '10% of $14.2m less resolution amount when resolution is below $7m.' Both the case name and the damages amount are correctly stated.
- **GPT-5.5: Pass.** The memo correctly names the matter as “NovaTech Solutions, LLC v. Pinnacle Health Systems, Inc.” and references the $14.2 million amount as the basis for the success-fee formula, reflecting the claimed exposure/damages amount.

### C-039

Recommends requiring competitive bidding for e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L322))

- **Sonnet 4.6: Pass.** In Issue 9, the memo explicitly states: 'Obtain Pinnacle's written approval and conduct a competitive bid if required by Pinnacle.' This directly recommends requiring competitive bidding for the CrossPoint e-discovery vendor selection rather than accepting the affiliated vendor without comparison. The memo also notes that CrossPoint is an 'HB&C strategic partner' and that HB&C's recommendation and history do not equal Pinnacle approval or a competitive-cost analysis, reinforcing the need for a competitive process.
- **GPT-5.5: Pass.** The memo expressly recommends not accepting CrossPoint yet and requiring Pinnacle approval plus a competitive bid/competitive-cost review where required, including in the priority actions and vendor approval sequence.

### C-040

Recommends requiring informed written consent for conflict/adverse representation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L330))

- **Sonnet 4.6: Pass.** The memo extensively addresses the MedBridge conflict in multiple sections. In the Executive Assessment, it states the conflict 'must be fully disclosed and resolved before acceptance' and that 'if the conflict is not consentable or Pinnacle does not give a specific informed written consent, HB&C should not be engaged.' In Priority Action #1, it requires 'a separate, specific informed written consent signed by the GC only if acceptable and ethically permissible; otherwise decline HB&C.' In Issue #2, it requires 'a written, fact-complete disclosure' and states 'Obtain a separate, matter-specific GC consent only after evaluating the full facts and applicable ethics rules. Strike the blanket waiver. If consent is unavailable or the conflict is nonconsentable, do not retain HB&C.' The memo also explicitly calls for striking the blanket advance waiver of future adverse representations. This clearly satisfies the criterion of recommending informed written consent, a more thorough conflicts analysis, and removal of the broad adverse-representation waiver.
- **GPT-5.5: Pass.** The memo specifically identifies the MedBridge/NovaTech conflict as a stop issue, calls for complete conflict disclosure and analysis, recommends separate matter-specific informed written GC consent if ethically permissible, and instructs that the blanket future adverse-representation waiver be struck.

### C-041

Recommends reducing or eliminating the malpractice liability cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L338))

- **Sonnet 4.6: Pass.** Section 20 of the memo explicitly states 'Delete the liability cap and client indemnity' and discusses how HB&C limits all liability including malpractice to the lesser of $1m or fees actually paid. The required action clearly recommends removing the liability cap entirely, which satisfies the criterion of recommending reducing or eliminating the malpractice liability cap given the $14.2 million matter exposure.
- **GPT-5.5: Pass.** The memo expressly identifies the $1 million/fees-paid liability cap as applying to malpractice and recommends deleting the liability cap, or at minimum not accepting it without review and carve-outs. This satisfies the criterion to remove or renegotiate the malpractice liability cap.

### C-042

Recommends removing or restructuring client indemnification clause ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L346))

- **Sonnet 4.6: Pass.** Section 20 of the memo explicitly addresses the client indemnification clause. It recommends deleting the client indemnity entirely ('Delete the liability cap and client indemnity'). It also specifies that at minimum, Pinnacle should not agree to indemnify HB&C for its own negligence, malpractice, gross negligence, willful misconduct, breach of duties, confidentiality/security failures, or legal violations. This clearly satisfies the criterion of recommending removal or restructuring to exclude coverage for the firm's negligent acts beyond just willful misconduct.
- **GPT-5.5: Pass.** The memo expressly identifies the broad client indemnity as problematic and recommends deleting the client indemnity entirely. It also provides a fallback restructuring that excludes indemnification for the firm's negligence, malpractice, gross negligence, willful misconduct, breaches, confidentiality/security failures, and legal violations.

### C-043

Recommends removing or restructuring the 15% termination fee ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L354))

- **Sonnet 4.6: Pass.** Section 15 of the memo explicitly addresses the termination fee. It states 'Delete the 15% fee' and requires that Pinnacle have immediate termination rights with only properly rendered fees and approved expenses payable through the effective date. This clearly recommends removing the 15% termination fee entirely.
- **GPT-5.5: Pass.** The memo explicitly identifies the 15% termination fee as inconsistent with the client's termination rights and recommends deleting it entirely, including in the required action and negotiation sequence.

### C-044

Recommends requiring firm insurance to meet OCG minimums ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L362))

- **Sonnet 4.6: Pass.** Section 4 of the memo explicitly addresses the insurance shortfall. It notes HB&C's coverage of $10m per occurrence/$20m aggregate is below the OCG minimum of $25m per occurrence/$50m aggregate, and requires a current certificate showing at least $25m/$50m coverage. It states 'Do not engage/continue unless compliant; any exception must be separately documented and approved by the GC if the OCG permits it.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies HB&C's professional liability coverage as below the OCG minimum and recommends requiring proof of at least $25 million per occurrence / $50 million aggregate coverage, with any exception separately documented and approved by the GC.

### C-045

Recommends removing or restructuring the work product lien ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L370))

- **Sonnet 4.6: Pass.** Section 14 of the memo explicitly addresses the work product lien. It identifies that the engagement letter grants HB&C a retaining lien on files/work product until all amounts are paid, notes this directly contradicts the OCG, and under 'Required action' states: 'Delete all lien/ownership/payment conditions and waive any retaining, charging, possessory, or other lien.' This clearly recommends removing the lien, consistent with the OCG's requirement that Pinnacle owns all work product with no firm lien.
- **GPT-5.5: Pass.** The memo expressly identifies the retaining/work-product lien as conflicting with the OCG and recommends deleting all lien/ownership/payment conditions, waiving any retaining/charging/possessory lien, and confirming Pinnacle’s unconditional ownership and file delivery rights.

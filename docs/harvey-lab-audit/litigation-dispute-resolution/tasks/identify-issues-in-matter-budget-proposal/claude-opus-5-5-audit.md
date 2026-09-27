# Claude Opus 5.5 audit: Identify Issues in Litigation Matter Budget Proposal

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 39. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric largely tracks the record. The $116,050 fee-total gap, the three absolute rate-cap breaches, Okeke's 4.5% increase, the late rate notice, the e-discovery bidding threshold, travel, copying, the appeal reserve and the staffing checks are all correct against the OCG. Two defects can zero out correct work under all-pass grading. C-008 and C-024 treat $566.50 as a compliant rate for Okeke, which OCG 3.2(c) and the workbook contradict. C-039 insists on an averaged per-expert figure when the budget gives each expert's actual estimate. The softer problems are: the business-day count for the paralegal notice (C-012 and C-035), severity ratings the instructions never ask for (C-028 to C-030), C-037's claim that a 3.03% increase is 'within 3%', C-031's crediting of Yoon's and Novak's rates while their increases exceed 3%, and C-026 leaving out the sole-source route. The record's inconsistent 2024 rate baselines are an unaddressed trap. Sol and I agree on nearly every affected criterion. We differ mainly on severity: I rate C-028 to C-030 and C-037 arguable rather than confirmed, and I treat C-008 as problematic alongside C-024.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L74), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L202) | $566.50 treated as Okeke's 'OCG-compliant max rate' although OCG 3.2(c) caps her at $550 | revised |
| [O2](#o2) | problematic | source_conflict | [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L322) | Requires an $87,500 per-expert average when the budget states each expert's actual estimate ($90,000 and $85,000) | revised |
| [O3](#o3) | arguable | unsupported_fact | [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106) | 'Approximately 2 business days' notice' misstates Friday-afternoon-for-Monday notice (about 1 business day) | revised |
| [O4](#o4) | arguable | source_conflict | [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L258) | C-031 counts Yoon's and Novak's rates as 'compliant' although their increases over approved 2024 rates exceed 3%, and it requires findings the instructions never ask for | revised |
| [O5](#o5) | arguable | document_defect | — | Documents disagree on 2024 rate baselines (Yoon $410/$415; Novak $360/$365) and on the paralegal's name (Hu/Hsu) | revised |
| [O6](#o6) | arguable | unrequested_requirement | [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L234), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L250) | Requires severity ratings although the instructions ask only for a 'categorized' issue memo | blind |
| [O7](#o7) | arguable | internal_inconsistency | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L306) | C-037 requires calling Croft's $825-to-$850 increase 'within 3%' although it is 3.03%, and its title says 'percentage issue' | blind |
| [O8](#o8) | arguable | ambiguous_or_unjudgeable | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L218) | Remedy criterion names only competitive bidding, though OCG 7.2(a) also allows a justified sole-source approval | blind |

<a id="o1"></a>
### O1. $566.50 treated as Okeke's 'OCG-compliant max rate' although OCG 3.2(c) caps her at $550

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L74), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L202)

Okeke's approved 2024 rate of $550 was already at the Senior Associate cap. OCG 3.2(c) bars any increase, even one within 3%, from taking a rate above the cap. The workbook says expressly that $566.50 'exceeds the $550 cap.' So the maximum compliant rate is $550. C-008 calls $566.50 the 'correct OCG-compliant max rate.' It also FAILs a memo that correctly states $550 by applying 3.2(c) without computing $566.50. C-024 accepts cutting Okeke to $566.50 as adequate remediation, which rewards a recommendation that would still breach the absolute cap.

Evidence:
- `C-008`: “States correct OCG-compliant max rate for Okeke ($566.50)”
- `C-008`: “FAIL if no correct maximum compliant rate is computed or if only the $550 cap is cited without addressing the 3% increase calculation.”
- `C-024`: “recommends reducing Samara Okeke's rate to $550/hr (the OCG senior associate cap) or $566.50 (the 3% increase maximum)”
- `colton-ocg-v4.2.docx.txt`: “No rate increase, even if within the 3% annual cap described in subsection (a) above, may cause a timekeeper's rate to exceed the applicable maximum rate set forth in Section 3.1.”
- `prior-year-budget-actuals.xlsx.txt`: “A 3% increase would yield $566.50/hr, which exceeds the $550 cap.”

Suggested fix: C-008: PASS if the memo concludes Okeke's maximum permissible 2025 rate is $550 (a 3% increase to $566.50 is capped at $550 under 3.2(c)). C-024: accept only $550 or a written GC exception, and allow $566.50 only as an intermediate calculation.

Related GPT-6 Sol findings: Confirmed defects: item 1.

<a id="o2"></a>
### O2. Requires an $87,500 per-expert average when the budget states each expert's actual estimate ($90,000 and $85,000)

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L322)

OCG 7.3(a) applies the $75,000 threshold per expert. Budget 5.2 gives individual estimates: $90,000 for the damages expert and $85,000 for the forensics expert. A careful memo will cite those figures and show that each exceeds $75,000. It has no reason to average them, and averaging could hide an expert who falls below the threshold. C-039 PASSes only on the ~$87,500 average and FAILs if 'the per-expert amount is not calculated,' so a memo using the precise individual figures risks failing.

Evidence:
- `C-039`: “PASS if the memorandum calculates or states the per-expert average cost as approximately $87,500 ($175,000 divided by 2 experts)”
- `matter-budget-proposal.docx.txt`: “estimated at \$90,000 for the engagement through trial testimony; and (2) a data forensics and trade secrets expert ... estimated at \$85,000”
- `colton-ocg-v4.2.docx.txt`: “estimated to exceed Seventy-Five Thousand Dollars (\$75,000) per expert or consultant over the life of the matter require the GC's pre-approval”

Suggested fix: PASS if the memo shows that each expert's estimate ($90,000; $85,000), or alternatively the ~$87,500 average, exceeds the $75,000 per-expert threshold.

Related GPT-6 Sol findings: Arguable / minor source issues: item 3.

<a id="o3"></a>
### O3. 'Approximately 2 business days' notice' misstates Friday-afternoon-for-Monday notice (about 1 business day)

**Status:** arguable · **Category:** unsupported_fact · **Criteria:** [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106)

The addition request was sent Fri, Apr 25, 2025 at 3:47 pm, for a start on Monday, Apr 28. That is one business day of notice, or two business dates only if counted inclusively. C-035's PASS text requires the memo to note that notice was 'approximately 2 business days,' and C-012 builds in the same count. A precise memo saying one business day could be failed for contradicting the criterion. Both FAIL conditions turn on the core violation or on citing the 10-day rule, and 'approximately' gives some room, so the misgrading risk applies only to some answers.

Evidence:
- `timekeeper-addition-notice.eml.txt`: “Date: Fri, 25 Apr 2025 15:47:00 -0400”
- `timekeeper-addition-notice.eml.txt`: “We would like to add Ms. Hu to the matter team effective Monday, April 28, 2025.”
- `C-035`: “notes the actual notice was approximately 2 business days”

Suggested fix: Accept any accurate description of the short notice (e.g., Friday-to-Monday, one business day, three calendar days) that falls far short of 10 business days.

Related GPT-6 Sol findings: Confirmed defects: item 4.

<a id="o4"></a>
### O4. C-031 counts Yoon's and Novak's rates as 'compliant' although their increases over approved 2024 rates exceed 3%, and it requires findings the instructions never ask for

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L258)

The workbook records approved 2024 rates of $410 (Yoon) and $360 (Novak) under OCG v4.1. Moving to $425 and $375 means increases of 3.66% and 4.17%, above the 3% limit in 3.2(a), and there is no GC approval on record. The workbook's own notes compute those percentages. Items (c) and (d) credit these rates as compliant because they equal the absolute caps. That is literally true, but it can reward a memo that misses the percentage breach. C-031 also requires affirmative compliance findings, which an issues-focused 'categorized issue memorandum' need not include. Items (a), (b) and (e) are genuinely compliant, so many competent memos will pass, which is why this is arguable rather than problematic.

Evidence:
- `C-031`: “(c) Yoon's rate matching the $425/hr mid-level associate cap, (d) Novak's rate matching the $375/hr junior associate cap”
- `prior-year-budget-actuals.xlsx.txt`: “Derrick Yoon 2024 rate ($410/hr) → proposed 2025 rate $425/hr = 3.66% increase”
- `prior-year-budget-actuals.xlsx.txt`: “Tara Novak 2024 rate ($360/hr) → proposed 2025 rate $375/hr = 4.17% increase”
- `colton-ocg-v4.2.docx.txt`: “Annual rate increases shall not exceed three percent (3%) of the prior year's approved rate for any individual timekeeper.”

Suggested fix: Remove items (c) and (d), or credit them only when qualified as absolute-cap compliance. Consider making C-031 lenient (e.g., PASS if the memo does not wrongly flag the staffing ratio or diversity staffing as violations).

Related GPT-6 Sol findings: Arguable / minor source issues: item 2.

<a id="o5"></a>
### O5. Documents disagree on 2024 rate baselines (Yoon $410/$415; Novak $360/$365) and on the paralegal's name (Hu/Hsu)

**Status:** arguable · **Category:** document_defect · **Criteria:** none

Budget Appendix A gives Yoon's 2024 rate as $415 (a 2.4% increase). The rate email and the workbook say $410 (3.66%). For Novak, the email and Appendix say $365 (2.7%), while the workbook's approved rate is $360 (4.17%). Appendix A also shows Hu at a $215 2024 rate. The paralegal appears as both 'Hsu' and 'Hu', even within one email. These may be intentional traps, but the correct answer on the Yoon/Novak increases depends on which baseline controls, and no criterion addresses it (see O4). The name variance is unlikely to affect grading.

Evidence:
- `matter-budget-proposal.docx.txt`: “Derrick Yoon      Mid-Level Associate (4th Year)   \$415/hr        \$425/hr        2.4%”
- `rate-increase-notice.eml.txt`: “Derrick Yoon's adjustment from $410 to $425 per hour and Tara Novak's from $365 to $375 per hour”
- `prior-year-budget-actuals.xlsx.txt`: “A7='Tara Novak' \| B7='Junior Associate' \| C7='2nd year (1st year in 2024)' \| D7='$360/hr'”
- `timekeeper-addition-notice.eml.txt`: “Margaret Hsu is an experienced litigation paralegal ... We would like to add Ms. Hu to the matter team”

Suggested fix: Reconcile the baselines, or add a criterion that rewards spotting the inconsistent 2024 rates and the resulting over-3% increases for Yoon and Novak.

Related GPT-6 Sol findings: Arguable / minor source issues: item 1.

<a id="o6"></a>
### O6. Requires severity ratings although the instructions ask only for a 'categorized' issue memo

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L234), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L250)

'Categorized issue memorandum' most naturally means grouping issues by type (rates, staffing, expenses, budget structure). Severity tiers are common but not inherent to this document type. A memo organized by category with full analysis and remedies but no priority labels fails C-028, and C-029 and C-030 fail with it: one format choice costs three criteria under all-pass grading. Reading 'categorized' as covering severity is plausible, and the substance of C-029/C-030 is reasonable once severity is used, so this is arguable.

Evidence:
- `task.json instructions`: “produce a categorized issue memorandum”
- `C-028`: “FAIL if no severity or priority classification is provided for the issues.”
- `C-029`: “FAIL if it is assigned a lower severity level or no severity level.”

Suggested fix: Add 'with severity ratings' to the instructions, or have C-029/C-030 accept any clear signal of seriousness (e.g., 'must be resolved before approval').

Related GPT-6 Sol findings: Confirmed defects: item 2.

<a id="o7"></a>
### O7. C-037 requires calling Croft's $825-to-$850 increase 'within 3%' although it is 3.03%, and its title says 'percentage issue'

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L306)

$825 x 1.03 = $849.75, and rounding up to $850 is a 3.03% increase. OCG 3.2(a) allows no rounding. The PASS text requires the memo to describe the increase as 'at or within the 3% annual cap percentage-wise,' while the title calls it a 'percentage issue.' A careful memo that flags the small percentage breach alongside the absolute-cap breach contradicts the PASS premise and could be failed. Most memos just say '3%' and pass, so only some are misgraded.

Evidence:
- `C-037`: “Identifies Croft's rate increase notice also has percentage issue”
- `C-037`: “while Croft's 3% increase from $825 to $850 (rounded from $849.75) is at or within the 3% annual cap percentage-wise”
- `rate-increase-notice.eml.txt`: “calculated as $849.75, rounded to $850”

Suggested fix: PASS if the memo explains that, whatever the percentage (about 3%, or 3.03% after rounding), OCG 3.2(c) caps Croft at $825 because his 2024 rate was already at the cap.

Related GPT-6 Sol findings: Confirmed defects: item 3.

<a id="o8"></a>
### O8. Remedy criterion names only competitive bidding, though OCG 7.2(a) also allows a justified sole-source approval

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L218)

OCG 7.2(a) lets a sole-source e-discovery engagement over $200,000 go ahead with express written GC approval supported by documented justification. Clearpoint's incumbency since the matter began is a plausible basis for that. C-026's PASS names only bidding among 3+ vendors, while its FAIL applies only when no remedy is recommended. A memo recommending a documented sole-source request falls between the two.

Evidence:
- `colton-ocg-v4.2.docx.txt`: “Sole-source engagements for e-discovery services exceeding the \$200,000 threshold are not permitted without express written GC approval, which must be supported by documented justification”
- `C-026`: “PASS if the memorandum recommends conducting competitive bidding among at least 3 e-discovery vendors and submitting documentation to the GC”

Suggested fix: PASS if the memo recommends either competitive bidding (3+ vendors, documentation to the GC) or a documented sole-source justification submitted for express written GC approval.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Confirmed defects: item 1 | confirmed | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L202) | problematic | OCG 3.2(c): no increase, even within 3%, may take a rate above the 3.1 cap; if it would, the rate is set at the cap. The workbook's Note 9 says $566.50 'exceeds the $550 cap.' C-024 therefore rewards recommending $566.50, which would still breach the absolute cap. C-008 has the same error (see O1). |
| Confirmed defects: item 2 | confirmed | [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L234), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L242), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L250) | arguable | The instructions ask only for a 'categorized issue memorandum.' That most naturally means grouping by issue type, but reading it as severity tiers is plausible, and priority ratings are common in issue memos. Omitting ratings fails three criteria at once, but the instructions really are ambiguous, so arguable rather than confirmed. |
| Confirmed defects: item 3 | confirmed | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L306) | arguable | $825 x 1.03 = $849.75, so $850 is a 3.03% increase, and OCG 3.2(a) has no rounding allowance. The PASS text requires saying the increase is 'at or within' 3%, while the title calls it a 'percentage issue.' A memo that flags the 3.03% breach may be failed. Most memos just say '3%' and pass, so only some answers are misgraded. |
| Confirmed defects: item 4 | confirmed | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290) | arguable | Notice was sent Fri Apr 25, 2025 at 3:47 pm for a start on Monday Apr 28. That is one business day, or two business dates if counted inclusively. 'Approximately 2' is imprecise. However, both FAIL conditions turn only on identifying the violation or citing the 10-day rule, and 'approximately' gives some room. The risk is real but hits only some answers. |
| Arguable / minor source issues: item 1 | arguable | [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L90), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L106), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L290) | not_a_defect | The name inconsistency is real: the email reads 'Margaret Hsu ... add Ms. Hu' and the budget uses 'Hu.' But judges will recognize the same paralegal under either spelling, so the name does not misgrade anything. C-012/C-035 are still arguable, but for the business-day count (O3), not the name. The source inconsistency is recorded in O5. |
| Arguable / minor source issues: item 2 | arguable | [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L258) | arguable | Items (c) and (d) are literally true, since the rates equal the absolute caps. But the approved 2024 rates in the workbook ($410, $360) make the increases 3.66% and 4.17%, above the 3% limit in 3.2(a). A competent memo can pass through items (a), (b), or (e), so C-031 rarely fails correct work. The main risk is that it requires affirmative compliance findings the instructions never ask for, and item (c)/(d) could reward calling non-compliant increases compliant. |
| Arguable / minor source issues: item 3 | arguable | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L122) (not_a_defect), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L226) (not_a_defect), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-matter-budget-proposal/task.json#L322) (problematic) | mixed | Budget 5.2 gives each expert's estimate ($90,000 and $85,000), and OCG 7.3(a) applies the threshold per expert. C-014's '$87,500 average' is only descriptive, and C-027 fails only when no remedy is given, so neither misgrades. C-039, however, requires the ~$87,500 average and fails a memo that uses the correct individual figures instead. |

## Blind pass and what changed

O1: added the Sol locator; substance unchanged (C-008 and C-024 problematic). O2: dropped C-014, because its '$87,500 average' is only a descriptive parenthetical and its PASS condition turns on identifying the exceedance; C-039 alone stays problematic. O3: downgraded C-035 from problematic to arguable. Both FAIL conditions turn on the core violation or the 10-day citation, 'approximately' gives some room, and inclusive counting gives two business dates, so only some answers are at risk. O4: downgraded C-031 from problematic to arguable, agreeing with Sol that items (c) and (d) are literally true (rate equals cap) and that items (a), (b) and (e) give competent memos a genuine path to pass. O5: removed C-007, which is sound because Okeke's $550-to-$575 figures are consistent across all documents; O5 is now a document defect not tied to a criterion, and I folded the baseline point into O4. O6 (C-028 to C-030) and O7 (C-037): stayed arguable rather than adopting Sol's 'confirmed', because 'categorized' could reasonably mean severity and C-037 misgrades only memos that flag the 3.03% figure. O8: unchanged. Sol raised no criterion I had missed. C-005, C-023 and C-033, which Sol mentioned in passing, are sound.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-008, C-024): $566.50 treated as Okeke's 'OCG-compliant max rate' although OCG 3.2(c) caps her at $550
- **O2** (problematic; C-039, C-014): Requires an $87,500 per-expert average when the budget states each expert's actual estimate ($90,000 and $85,000)
- **O3** (problematic; C-035, C-012): 'Approximately 2 business days' notice' is wrong: notice came Friday afternoon for a Monday start (1 business day)
- **O4** (problematic; C-031): Credits Yoon's and Novak's rates as 'compliant' even though their approved-rate increases exceed the 3% cap
- **O5** (arguable; C-031, C-007): Documents disagree on 2024 rates (Yoon $410 vs $415; Novak $360 vs $365) and on the paralegal's name (Hu vs Hsu)
- **O6** (arguable; C-028, C-029, C-030): Requires severity ratings although the instructions ask only for a 'categorized' issue memo
- **O7** (arguable; C-037): C-037's title says Croft has a 'percentage issue' but its PASS text says his increase is within 3%; $850 is 3.03%
- **O8** (arguable; C-026): Remedy criterion names only competitive bidding, though OCG 7.2(a) also allows a justified sole-source approval

## Coverage and limits

Blind pass: I read all 39 criteria and the instructions. I read all five documents in full: the budget proposal, the OCG v4.2, the rate-increase email, the timekeeper-addition email, and the prior-year actuals XLSX, including its Notes cells. I re-added both fee totals and the per-timekeeper overage totals, recomputed the rate-increase percentages, and checked the weekdays for Apr 25 and Apr 28, 2025. No external legal authority was needed, since every rule at issue is a contractual OCG provision in the record. I did not read the system prompt or judge prompt files beyond the description given in the task. I could not consult the advisor because it was rate-limited.

Reconciliation: Second pass. I re-read the instructions and the text of all criteria at issue (C-004 to C-008, C-010, C-012, C-014, C-023, C-024, C-026 to C-031, C-033, C-035, C-037, C-039). I re-checked the record for each: OCG 3.2(a) and (c), the 10-business-day addition rule, 7.2(a) and 7.3(a); budget Appendix A, the rate narrative and 5.2 expert estimates; both emails' dates and figures; and the workbook's 2024 rates and Notes 2, 3 and 9 to 11. I read Sol's full report and index entry. No external legal authority was needed, since every rule at issue is a contractual OCG provision in the record. I did not consult the advisor.

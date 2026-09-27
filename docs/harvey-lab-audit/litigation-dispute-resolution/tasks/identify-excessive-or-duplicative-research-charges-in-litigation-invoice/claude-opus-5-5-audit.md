# Claude Opus 5.5 audit: Identify Excessive or Duplicative Research Charges in Litigation Invoice

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 46. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric correctly targets the main planted issues: the 12% cap exceedance, partner research at partner rates, the Westlaw pass-through, the discount arithmetic, within-matter and cross-matter duplication, and the database-hosting distractor. Most of the duplication criteria are sound, because 6.4 puts the burden on counsel. The largest defect is in the record: the itemized fees ($243,080.50) do not support the stated $349,552.50 gross, so the hard-coded 13.56%, 15.83% and $41,018 figures (C-002, C-003, C-006) rest on $106K of fees with no time entries behind them. C-025 misstates Section 6.5 by copying Holt's paraphrase. C-038 (severity ratings) and C-003 (a mixed-basis gross ratio) require unrequested content that can zero out a competent memo under all-pass grading. The Section 4.3 onboarding criteria, the block-billing examples, the damages-subset framing, Osei's 'excessive' hours, the economic-loss remedy and the C-036 total are defensible but brittle for careful answers.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | document_defect | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L26), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L58) | Fee detail totals $243,080.50, not the stated $349,552.50 gross; hard-coded research percentages and cap rest on the unsupported total | revised |
| [O2](#o2) | problematic | source_conflict | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L210) | C-025 misstates Section 6.5: no '50% must be non-research' requirement and no 'research cap rate' | blind |
| [O3](#o3) | problematic | unrequested_requirement | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L314) | Severity ratings are required but never requested | blind |
| [O4](#o4) | problematic | unrequested_requirement | [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34) | C-003 requires a pre-discount research percentage the guideline does not use, on a mixed denominator | blind |
| [O5](#o5) | arguable | document_defect | [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L298) | C-036 calls $387,420.50 the 'correct' invoice total, but the line items support only about $281K | revised |
| [O6](#o6) | arguable | ambiguous_or_unjudgeable | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L202) | Block-billing criterion requires Osei research-memo entries already coded RES and omits the clearest 6.5 problem | blind |
| [O7](#o7) | arguable | source_conflict | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L186), [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L194), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L338) | Section 4.3 covers newly assigned timekeepers; Wendt has been staffed since January, and his July 15 entry may be substantive update research | revised |
| [O8](#o8) | arguable | ambiguous_or_unjudgeable | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146) | C-017 requires the 13 Osei hours be called excessive on 'one research question', though July 10 also covers the economic loss rule | adopted_after_reading_sol |
| [O9](#o9) | arguable | ambiguous_or_unjudgeable | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L138) | Damages-duplication criterion requires the 'lost profits is a subset' framing and skips Takahashi's July 3 consequential-damages entry | blind |
| [O10](#o10) | arguable | legal_error | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L162) | C-019's model remedy disallows the junior attorney's time, contrary to Section 6.4's pay-the-junior rule | blind |

<a id="o1"></a>
### O1. Fee detail totals $243,080.50, not the stated $349,552.50 gross; hard-coded research percentages and cap rest on the unsupported total

**Status:** problematic · **Category:** document_defect · **Criteria:** [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L26), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L58)

Each of the 160 Fee Detail rows checks out at rate × hours, and together they sum to $243,080.50. The Summary states $349,552.50 gross, which leaves $106,472 in fees with no time entries behind them. Research hours also conflict: 142.3 on the Summary versus 137.6 in the detail and on the discount sheet. C-002, C-003 and C-006 hard-code 13.56%, 15.83% and $41,018, all computed on the unsupported $341,820.50 net figure. A careful reviewer who recomputes from the line items gets research at about 19.7% of net fees and a cap of about $28,242, and fails all three criteria. The rubric also gives no credit for flagging the unsupported $106K, which is arguably a non-compliant charge under an instruction to find 'all non-compliant or excessive charges.'

Evidence:
- `hl-july-2024-invoice.xlsx.txt`: “A19='Total Professional Fees (Gross):' \| B19='$349,552.50'”
- `hl-july-2024-invoice.xlsx.txt`: “A28='Total Research Hours:' \| B28='142.3'”
- `C-002`: “net research charges ($46,372.50) as a percentage of total fees ($341,820.50) is approximately 13.5%-13.6%”

Suggested fix: Fix the invoice so the detail rows sum to the stated gross fees. Otherwise, let C-002, C-003 and C-006 accept figures computed on either the stated or the itemized fees, and give credit for flagging the gap.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o2"></a>
### O2. C-025 misstates Section 6.5: no '50% must be non-research' requirement and no 'research cap rate'

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L210)

Section 6.5 requires block-billed research entries to allocate time clearly. If research is more than 50% of the entry, or the allocation is unclear, the whole entry counts toward the 6.2 cap. If clearly allocated non-research time is 50% or more, only the research portion counts. Nothing requires firms to put 50% of the time on non-research work, and no 'research cap rate' exists; the engagement letter expressly rules out a separate research rate. C-025 takes its wording from Holt's inaccurate paraphrase. It rewards a memo that repeats the misstatement and may fail one that states the guideline accurately.

Evidence:
- `terraverde-billing-guidelines.docx.txt`: “If the research component constitutes more than fifty percent (50%) of the block-billed entry's total time, or if the allocation between research and non-research tasks is unclear from the description, the entire entry will be treated as a Legal Research entry and will count in full toward the Research Cap”
- `C-025`: “must allocate at least 50% of the time to the non-research component, or the entire entry will be reduced to the research cap rate”
- `engagement-letter-cascade.docx.txt`: “No alternative or reduced rates (including any separate "research rate") are established under this schedule”

Suggested fix: PASS if the memo explains 6.5's 50% threshold: research-predominant or unallocated entries count in full toward the 12% cap. Delete the 'research cap rate' language.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o3"></a>
### O3. Severity ratings are required but never requested

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L314)

The instructions ask for a memo that identifies non-compliant or excessive charges with recommended adjustments. Neither the instructions nor Holt's email asks for severity or priority ratings, and they are not a standard part of an invoice-adjustment memo; the dollar adjustments already convey magnitude. A memo that lists every violation with its guideline citation and dollar adjustment, but without labels such as Critical or Minor, fails C-038 and therefore scores zero on the all-pass metric.

Evidence:
- `instructions`: “prepare a memo identifying all non-compliant or excessive charges with recommended adjustments”
- `C-038`: “FAIL if no severity assessments or priority rankings are provided.”

Suggested fix: Delete C-038, or make it non-gating.

Related GPT-6 Sol findings: arguable/2.

<a id="o4"></a>
### O4. C-003 requires a pre-discount research percentage the guideline does not use, on a mixed denominator

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34)

Section 6.2 measures research charges after voluntary discounts, so the governing figure is the net ratio that C-002 already tests. C-003 also requires 'gross research ÷ net fees' at 15.8–15.9%. That ratio mixes a pre-discount numerator with a post-discount denominator, and no instruction or guideline asks for it. A memo that correctly applies 6.2 and reports only the net figure fails. A memo that computes the natural pre-discount comparison, gross over gross (54,104.50 / 349,552.50 = 15.48%), falls outside the band.

Evidence:
- `terraverde-billing-guidelines.docx.txt`: “"total Legal Research charges" means ... after application of any voluntary discounts or write-downs by outside counsel”
- `C-003`: “approximately 15.8%-15.9% (the exact figure is 15.83%). FAIL if the gross percentage is not calculated.”

Suggested fix: Delete C-003, or make it optional credit that accepts any clearly labeled pre-discount ratio.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o5"></a>
### O5. C-036 calls $387,420.50 the 'correct' invoice total, but the line items support only about $281K

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L298)

Because of the $106,472 gap described in O1, the $387,420.50 total is correct only as the amount billed. C-036 probably passes a memo that quotes the billed total and flags the gap. But a memo that states only the reconciled total, calling the stated total unsupported, could be marked 'materially incorrect'.

Evidence:
- `C-036`: “PASS if the memo states the invoice total as $387,420.50 (or separately states $341,820.50 in fees and $45,600.00 in disbursements)”
- `hl-july-2024-invoice.xlsx.txt`: “A19='Total Professional Fees (Gross):' \| B19='$349,552.50'”

Suggested fix: Accept either the billed total or a reconciled total that is clearly explained.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o6"></a>
### O6. Block-billing criterion requires Osei research-memo entries already coded RES and omits the clearest 6.5 problem

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L202)

Under the Section 2 definition, drafting a research memorandum that compiles findings is itself Legal Research. The three required entries (Osei July 3, 8 and 16) are all coded RES and already count in full toward the cap, so 6.5 changes nothing for them. The clearest 6.5 problem is Osei's July 11 entry, coded DRF, whose research component escapes the cap. A memo that flags only that entry, or Wendt's July 11 'research and prepare opposition arguments', fails C-024.

Evidence:
- `terraverde-billing-guidelines.docx.txt`: “preparing research summaries or memoranda to the extent such memoranda primarily compile or synthesize research findings”
- `hl-july-2024-invoice.xlsx.txt`: “H122='DRF' \| I122='Assist with drafting meet-and-confer letter; research local rules on meet-and-confer requirements for discovery motions.'”

Suggested fix: Accept any entry that is plausibly block-billed research under 6.5, including Osei July 11 (DRF).

<a id="o7"></a>
### O7. Section 4.3 covers newly assigned timekeepers; Wendt has been staffed since January, and his July 15 entry may be substantive update research

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L186), [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L194), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L338)

Section 4.3 applies to 'a newly assigned Timekeeper', and 6.4 speaks of 'new or rotating team members'. Wendt has been staffed since January 2024. His July 15 entry ('familiarize with MTCA amendments and recent regulatory guidance') could reasonably be read as substantive research on legal developments. A memo that queries or conditionally holds that entry fails C-022 and C-023. A memo that rests the disallowance on 6.4, 6.1 or the reasonableness reservation instead of 4.3 fails C-041. The July 25 entry (C-021) uses 4.3(e) phrases verbatim, and C-046 expressly allows other provisions, so I do not flag either.

Evidence:
- `terraverde-billing-guidelines.docx.txt`: “Time spent by a newly assigned Timekeeper reviewing the existing file, getting up to speed on the Matter, performing background research ... is not billable”
- `hl-july-2024-invoice.xlsx.txt`: “I43='Research background on Washington environmental regulatory framework; familiarize with MTCA amendments and recent regulatory guidance.'”
- `C-041`: “FAIL if Section 4.3 is not cited in connection with these entries.”

Suggested fix: PASS if the entries are flagged as familiarization or background research under 4.3 (directly or by analogy), 6.4, 6.1 or the reasonableness provisions, and accept a conditional hold on the July 15 entry.

Related GPT-6 Sol findings: arguable/0.

<a id="o8"></a>
### O8. C-017 requires the 13 Osei hours be called excessive on 'one research question', though July 10 also covers the economic loss rule

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146)

Osei's July 10 entry also analyzes the economic loss rule, and July 8 includes memo drafting, so '13 hours on one question' overstates the record. Whether 13 first-year hours on damages research, including a memo, is disproportionate under 6.1 is a judgment call. A memo that treats these entries as duplicative under 6.4 (C-016) but does not also call them intrinsically excessive may fail C-017.

Evidence:
- `hl-july-2024-invoice.xlsx.txt`: “I30='Continue research on consequential damages limitations in Washington; analyze economic loss rule applicability to environmental remediation contracts.'”
- `C-017`: “on what is essentially one research question (Washington consequential damages law) as excessive”

Suggested fix: PASS if the memo questions Osei's July 8 and 10 hours as either excessive or duplicative.

Related GPT-6 Sol findings: confirmed_defects/2, arguable/1.

<a id="o9"></a>
### O9. Damages-duplication criterion requires the 'lost profits is a subset' framing and skips Takahashi's July 3 consequential-damages entry

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L138)

The clearest damages duplications are two pairs. Takahashi on July 3 (consequential damages in remediation contracts) overlaps Osei on July 8 and 10. Wendt and Takahashi both researched lost profits on July 18. C-016 requires the memo to link Osei's work to the July 18 entries and to say lost profits is a subset of consequential damages. A memo that flags both pairs separately, without the subset language, could fail even though it finds more duplication than the criterion lists.

Evidence:
- `hl-july-2024-invoice.xlsx.txt`: “I12='Research Washington law on consequential damages in breach of remediation contracts; survey damages limitations.'”
- `C-016`: “noting that lost profits is a subset of consequential damages”

Suggested fix: PASS if the memo identifies duplicative damages research among any of these timekeepers; make the subset framing optional.

Related GPT-6 Sol findings: arguable/1.

<a id="o10"></a>
### O10. C-019's model remedy disallows the junior attorney's time, contrary to Section 6.4's pay-the-junior rule

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L162)

Section 6.4 says TerraVerde pays the most junior qualified attorney and disallows higher-rate timekeepers. For the July 12 economic loss rule entries, that means paying Osei ($295) and disallowing Takahashi (6.0 × $340 = $2,040). C-019 instead names Osei's $1,327.50 as the minimum disallowance. Its lenient FAIL condition (fail only if no adjustment) will probably pass a correct $2,040 disallowance. But it models the wrong remedy, and a judge could read 'comparable amount' narrowly.

Evidence:
- `terraverde-billing-guidelines.docx.txt`: “TerraVerde will pay for the time of the most junior qualified attorney who performed the research, and charges for higher-rate Timekeepers performing overlapping research will be disallowed.”
- `C-019`: “At minimum, Osei's 4.5 hours at $295/hr = $1,327.50 should be recommended for disallowance or a comparable amount.”

Suggested fix: Name Takahashi's $2,040 as the 6.4-consistent adjustment, and accept any reasonable dollar adjustment.

Related GPT-6 Sol findings: arguable/1.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| confirmed_defects/0 | confirmed | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L210) | problematic | Section 6.5 has no rule that at least 50% of an entry must be non-research, and it has no 'research cap rate'. Research-predominant or unclearly allocated entries count in full toward the 12% cap. The engagement letter expressly says there is no separate research rate. C-025 takes its wording from Holt's inaccurate paraphrase, so it rewards the misstatement and can fail a memo that states the rule correctly. |
| confirmed_defects/1 | confirmed | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L26) (problematic), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34) (problematic), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L58) (problematic), [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L298) (arguable) | mixed | I independently confirmed the gap: the 160 detail rows sum to $243,080.50, against $349,552.50 stated on the Summary. C-002, C-003 and C-006 hard-code percentages and a cap figure that rest on $106K of fees with no supporting entries, so a reconciling memo can fail. C-036 only asks the memo to state the invoice total. Quoting the billed total while noting the gap would still pass, so C-036 is merely arguable. |
| confirmed_defects/2 | confirmed | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146) | arguable | Osei's July 10 entry also covers the economic loss rule, and July 8 includes memo drafting, so '13 hours on one question' overstates it. But research-memo drafting falls within the Section 2 research definition, and flagging 13 hours as disproportionate under 6.1 is a reasonable position. The problem is that the rubric demands one judgment call, which is debatable rather than clearly wrong. I see no real conflict with C-024, because 6.5 treats unallocated entries as research. |
| arguable/0 | arguable | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L186), [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L194), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L338) | arguable | Section 4.3 covers a 'newly assigned Timekeeper', and Wendt has been staffed since January 2024. The July 15 entry ('familiarize with MTCA amendments and recent regulatory guidance') could be substantive update research. A memo that queries or conditionally holds that entry, or rests its objection on 6.4, 6.1 or the reasonableness reservation instead of 4.3, risks failing C-022, C-023 or C-041. I exclude C-021, because the July 25 entry literally uses the 4.3(e) phrases 'review file materials' and 'get up to speed'. |
| arguable/1 | arguable | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L114) (not_a_defect), [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L122) (not_a_defect), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L130) (not_a_defect), [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L138) (arguable), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146) (arguable), [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L154) (not_a_defect), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L162) (arguable), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L170) (not_a_defect), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L234) (not_a_defect), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L266) (not_a_defect), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L362) (not_a_defect), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L370) (not_a_defect) | mixed | Section 6.4 puts the burden on outside counsel to show that apparently duplicative entries addressed genuinely distinct questions. The client's reviewer is right to flag these overlaps, and most of these criteria accept 'any reasonable adjustment'. The DOE summary itself says both matters center on MTCA contractor strict liability. Only C-016 (required subset framing), C-017 (an excess judgment call) and C-019 (a model remedy contrary to 6.4) are arguable. |
| arguable/2 | arguable | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L314) | problematic | Neither the instructions nor Holt's email asks for severity or priority ratings, and they are not a standard part of an invoice-adjustment memo, where dollar adjustments already show magnitude. C-038 fails any memo without rankings. Under all-pass grading, that zeroes out a complete, correct memo, so I rate it problematic rather than arguable. |

## Blind pass and what changed

1. I split C-036 out of blind O1 into its own arguable finding (O5). Stating the billed total while flagging the gap would still pass C-036, so it is less brittle than C-002, C-003 and C-006.
2. From Sol, I adopted C-017 as arguable (O8), not problematic. The July 10 entry does add economic-loss-rule work, but calling the hours excessive is a defensible 6.1 judgment.
3. I narrowed blind O6 to C-022, C-023 and C-041, following Sol's point that the July 15 update research may be substantive. I dropped C-021, whose entry uses the 4.3(e) phrases verbatim, and C-046, which expressly accepts other provisions or 'excessive'.
4. I dropped blind O10 (C-028). The DOE summary says both matters center on MTCA contractor strict liability, and the July 15 and July 22 DOE entries continue that research. The 12.5-hour DOE total is a fair characterization, and the PASS condition requires only identifying the cross-matter duplication.
5. I dropped blind O9 (C-005, C-033, C-034). The inconsistencies in the reply-brief filing dates and the June email are real, but they do not change what a correct answer is or cause any criterion to misgrade.
6. I rejected Sol's broad arguable/1 cluster except for C-016, C-017 and C-019. Section 6.4 shifts the burden to outside counsel, so flagging the MTCA, economic-loss, spoliation and unjust-enrichment overlaps is right, and the adjustment criteria accept any reasonable amount.
7. I kept C-038 as problematic, which is more severe than Sol's rating.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-002, C-003, C-006, C-036): Itemized fee entries total $243,080.50, not the invoice's stated $349,552.50 gross; rubric percentages assume the unsupported total
- **O2** (problematic; C-025): C-025 misstates Section 6.5: no '50% must be non-research' requirement and no 'research cap rate' exists
- **O3** (problematic; C-038): Severity ratings are required but never requested
- **O4** (problematic; C-003): C-003 requires a pre-discount research percentage the guideline does not use, with a mixed denominator
- **O5** (arguable; C-024): Block-billing criterion demands three Osei entries that are research-memo work already coded RES, while better examples are excluded
- **O6** (arguable; C-021, C-022, C-041, C-046): Section 4.3 by its terms covers only newly assigned timekeepers; Wendt and Osei have been staffed since January 2024
- **O7** (arguable; C-019): C-019's model remedy disallows the junior attorney's time, contrary to Section 6.4's pay-the-junior rule
- **O8** (arguable; C-016): Damages-duplication criterion requires the 'lost profits is a subset' framing and skips Takahashi's July 3 consequential-damages entry
- **O9** (arguable; C-005, C-033, C-034): Record conflicts on reply-brief filing date and on the timing and content of Holt's review of the June invoice
- **O10** (arguable; C-028): C-028 overstates the cross-matter overlap: only about 7.5 of Takahashi's 12.5 DOE research hours match the Cascade research

## Coverage and limits

Blind pass: I read all six supplied documents in full: the July invoice (all 160 fee-detail rows, the disbursements, the discount sheet and the summary), the billing guidelines, the engagement letter, the June invoice summary, Holt's June 28 email and the DOE-matter invoice. I also read all 46 criteria and the instructions. I recomputed the invoice arithmetic with a script: the fee-detail total, research totals by timekeeper, the discount and the percentages. I read the grading prompts only as described in the task and did not open them. No external legal authority was needed, because every criterion turns on the client's own billing guidelines, a contract document, not on statute or case law. I cite no outside authorities. Not verified: whether the $106K gap between the fee detail and the stated fees is an artifact of how the task was built (for example, detail that was left out on purpose). Either way the supplied record is what the solver and the judges see.

Reconciliation: I reviewed all 46 criteria and the instructions. In the blind pass I read all six documents in full and recomputed the invoice arithmetic. In this pass I re-checked every RES entry, the guideline text of 4.3, 6.1, 6.4 and 6.6, and the DOE-matter research entries against each Sol finding. I read Sol's full markdown and JSON audit. No external legal authority was needed, because every criterion turns on the client's billing guidelines, a contract document, and I cite none.
